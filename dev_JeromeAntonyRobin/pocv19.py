#!!!!!!!!!silently crashes with large verilog codes in report generation, hybterm is useless feature, schematic view is bugged!!!!!!!!!
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog, Menu
import subprocess
import os
import threading
import queue
import glob
import re
import shutil
from contextlib import suppress
from PIL import Image, ImageTk

# ================= HELPER: NUMPAD BRIDGE =================
def bridge_numpad(widget):
    key_map = {
        "<KP_Up>": "<Up>", "<KP_Down>": "<Down>",
        "<KP_Left>": "<Left>", "<KP_Right>": "<Right>",
        "<KP_Home>": "<Home>", "<KP_End>": "<End>",
        "<KP_Prior>": "<Prior>", "<KP_Next>": "<Next>"
    }
    def dispatch(event, key_name):
        widget.event_generate(key_name); return "break"
    for kp, std in key_map.items():
        widget.bind(kp, lambda e, k=std: dispatch(e, k))

# ================= CUSTOM WIDGETS =================

class CodeEditor(tk.Frame):
    def __init__(self, parent, font_size=12):
        super().__init__(parent)
        self.pack(fill=tk.BOTH, expand=True)
        self.font = ("Consolas", font_size)
        
        self.toolbar = tk.Frame(self, bg="#f0f0f0", height=25)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        tk.Button(self.toolbar, text="↶", width=3, command=self.undo, relief="flat").pack(side=tk.LEFT, padx=2)
        tk.Button(self.toolbar, text="↷", width=3, command=self.redo, relief="flat").pack(side=tk.LEFT, padx=2)

        container = tk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)

        self.gutter = tk.Text(container, width=4, padx=4, takefocus=0, border=0, background="#f0f0f0", state="disabled", font=self.font)
        self.gutter.pack(side=tk.LEFT, fill=tk.Y)
        
        self.text = tk.Text(container, font=self.font, undo=True, maxundo=-1, autoseparators=True, wrap="none")
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        bridge_numpad(self.text)
        
        self.vsb = ttk.Scrollbar(container, orient="vertical", command=self.on_scroll)
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.configure(yscrollcommand=self.vsb.set)
        
        self.text.bind("<KeyRelease>", self.on_content_changed)
        self.text.bind("<MouseWheel>", self.sync_scroll)
        self.text.bind("<Button-4>", self.sync_scroll)
        self.text.bind("<Button-5>", self.sync_scroll)
        self.text.bind("<Tab>", self.insert_tab_spaces)
        self.text.bind("<Return>", self.auto_indent)
        self.text.bind("<Control-z>", self.undo_event)
        self.text.bind("<Control-y>", self.redo_event) 
        self.setup_tags()

    def undo(self): 
        try: self.text.edit_undo()
        except: pass
    def redo(self): 
        try: self.text.edit_redo()
        except: pass
    def undo_event(self, event): self.undo(); return "break"
    def redo_event(self, event): self.redo(); return "break"
    def insert_tab_spaces(self, event):
        self.text.insert(tk.INSERT, "    "); return "break"
    def auto_indent(self, event):
        cursor_pos = self.text.index(tk.INSERT)
        line_num = int(cursor_pos.split('.')[0])
        line_text = self.text.get(f"{line_num}.0", f"{line_num}.end")
        indent = ""
        for char in line_text:
            if char in " \t": indent += char
            else: break
        stripped = line_text.strip()
        if stripped.endswith("begin") or stripped.endswith("module") or stripped.endswith("case") or stripped.endswith(")"):
            indent += "    " 
        self.text.insert(tk.INSERT, "\n" + indent); self.text.see(tk.INSERT); return "break"
    def setup_tags(self):
        self.text.tag_configure("KEYWORD", foreground="#0000FF", font=(self.font[0], self.font[1], "bold"))
        self.text.tag_configure("COMMENT", foreground="#008000")
        self.text.tag_configure("STRING", foreground="#A31515")
        self.text.tag_configure("NUMBER", foreground="#800080")
        self.text.tag_configure("ERROR", background="#FFCCCC")
    def on_scroll(self, *args): self.text.yview(*args); self.gutter.yview(*args)
    def sync_scroll(self, event): self.gutter.yview_moveto(self.text.yview()[0])
    def on_content_changed(self, event=None): 
        self.text.edit_separator(); self.update_line_numbers(); self.highlight_syntax()
    def update_line_numbers(self):
        line_count = int(self.text.index('end-1c').split('.')[0])
        self.gutter.config(state="normal")
        self.gutter.delete("1.0", tk.END)
        self.gutter.insert("1.0", "\n".join(str(i) for i in range(1, line_count + 1)))
        self.gutter.config(state="disabled")
        self.gutter.yview_moveto(self.text.yview()[0])
    def highlight_syntax(self):
        for tag in ["KEYWORD", "COMMENT", "STRING", "NUMBER", "ERROR"]: self.text.tag_remove(tag, "1.0", tk.END)
        text_content = self.text.get("1.0", tk.END)
        keywords = r"\b(module|endmodule|input|output|wire|reg|always|initial|begin|end|assign|posedge|negedge|if|else|case|endcase|default|parameter)\b"
        for match in re.finditer(keywords, text_content): self.text.tag_add("KEYWORD", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        numbers = r"\b\d+'[bh]\w+|\b\d+\b"
        for match in re.finditer(numbers, text_content): self.text.tag_add("NUMBER", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        strings = r"\".*?\""
        for match in re.finditer(strings, text_content): self.text.tag_add("STRING", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        comments = r"//.*"
        for match in re.finditer(comments, text_content): self.text.tag_add("COMMENT", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
    def highlight_error_line(self, line_num):
        self.text.tag_remove("ERROR", "1.0", tk.END); self.text.tag_add("ERROR", f"{line_num}.0", f"{line_num + 1}.0"); self.text.see(f"{line_num}.0")
    def get(self, *args): return self.text.get(*args)
    def delete(self, *args): self.text.delete(*args); self.on_content_changed()
    def insert(self, *args): self.text.insert(*args); self.on_content_changed()
    def focus_set(self): self.text.focus_set()


class ZoomableSchematic(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill=tk.BOTH, expand=True)
        self.v_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.h_scroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL)
        self.canvas = tk.Canvas(self, bg="#f0f0f0", yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)
        self.v_scroll.config(command=self.canvas.yview); self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y); self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.original_image = None; self.tk_image = None; self.zoom_level = 1.0
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<plus>", self.key_zoom_in); self.canvas.bind("<KP_Add>", self.key_zoom_in)
        self.canvas.bind("<minus>", self.key_zoom_out); self.canvas.bind("<KP_Subtract>", self.key_zoom_out)
        for k in ["<Left>", "<KP_Left>"]: self.canvas.bind(k, lambda e: self.canvas.xview_scroll(-1, "units"))
        for k in ["<Right>", "<KP_Right>"]: self.canvas.bind(k, lambda e: self.canvas.xview_scroll(1, "units"))
        for k in ["<Up>", "<KP_Up>"]: self.canvas.bind(k, lambda e: self.canvas.yview_scroll(-1, "units"))
        for k in ["<Down>", "<KP_Down>"]: self.canvas.bind(k, lambda e: self.canvas.yview_scroll(1, "units"))
    def load_image(self, path):
        try: self.original_image = Image.open(path); self.zoom_level = 1.0; self.show_image()
        except Exception as e: print(f"Image Error: {e}")
    def show_image(self):
        if not self.original_image: return
        w, h = self.original_image.size
        new_w = int(w * self.zoom_level); new_h = int(h * self.zoom_level)
        resized = self.original_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
    def on_button_press(self, event): self.canvas.scan_mark(event.x, event.y)
    def on_move_press(self, event): self.canvas.scan_dragto(event.x, event.y, gain=1)
    def on_zoom(self, event):
        if event.num == 4 or event.delta > 0: self.zoom_level *= 1.1
        elif event.num == 5 or event.delta < 0: self.zoom_level /= 1.1
        self.show_image()
    def key_zoom_in(self, event): self.zoom_level *= 1.1; self.show_image()
    def key_zoom_out(self, event): self.zoom_level /= 1.1; self.show_image()
    def focus_set(self): self.canvas.focus_set()


# =============================================================================
#                                 MAIN IDE APP
# =============================================================================

class SilisIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("Silis v40 (Stable Core)")
        self.root.geometry("1400x900")
        self.root.config(cursor="arrow") 
        
        # --- CONFIG ---
        self.key_map = {"focus_editor":"c", "focus_terminal":"x", "focus_files":"v", "focus_schem":"z", "term_toggle":"s"}
        self.term_colors = {"SYS":"#00FFFF", "INPUT":"#FFFFFF", "ERROR":"#FF5555", "SUCCESS":"#50FA7B", "WARN":"#F1FA8C"}
        self.schem_engine = "Auto"
        self.pdk_path = "" 
        
        self.sk_active = False; self.sk_timeout = 1000 
        self.current_file = None; self.cwd = os.getcwd()
        self.process = None; self.queue = queue.Queue()
        self.is_running_job = False # LOCK
        self.term_mode = "SHELL" 
        self.dir_history = [self.cwd]; self.history_index = 0
        
        style = ttk.Style(); style.theme_use('clam')
        
        # --- UI LAYOUT ---
        self.create_toolbar()
        
        self.main_split = ttk.PanedWindow(root, orient=tk.VERTICAL); self.main_split.pack(fill=tk.BOTH, expand=True)
        self.middle_pane = ttk.PanedWindow(self.main_split, orient=tk.HORIZONTAL); self.main_split.add(self.middle_pane, weight=4)
        
        self.file_frame = tk.LabelFrame(self.middle_pane, text="Explorer"); self.middle_pane.add(self.file_frame, weight=1)
        self.tree = ttk.Treeview(self.file_frame, show='tree'); self.tree.pack(fill=tk.BOTH, expand=True)
        bridge_numpad(self.tree)
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_expand); self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Return>", self.on_tree_enter_key); self.tree.bind("<Escape>", self.on_tree_up_dir); self.tree.bind("<FocusIn>", self.on_tree_focus) 
        self.tree.bind("<Delete>", self.delete_file_prompt)
        self.tree.bind("<Control-z>", self.nav_back); self.tree.bind("<Control-y>", self.nav_forward)
        self.tree.bind("<Button-3>", self.show_context_menu)

        self.editor_frame = tk.LabelFrame(self.middle_pane, text="Code"); self.middle_pane.add(self.editor_frame, weight=5)
        self.editor = CodeEditor(self.editor_frame)
        
        self.schem_frame = tk.LabelFrame(self.middle_pane, text="Schematic"); self.middle_pane.add(self.schem_frame, weight=2)
        self.schematic_viewer = ZoomableSchematic(self.schem_frame)
        
        self.term_frame = tk.LabelFrame(self.main_split, text="Terminal"); self.main_split.add(self.term_frame, weight=1)
        self.term_log = scrolledtext.ScrolledText(self.term_frame, bg="#1e1e1e", fg="#e0e0e0", font=("Consolas", 10), height=8)
        self.term_log.pack(fill=tk.BOTH, expand=True)
        self.update_term_colors()

        input_frame = tk.Frame(self.term_frame, bg="#333"); input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.mode_btn = tk.Button(input_frame, text="[SHELL]", bg="#0d6efd", fg="white", command=self.toggle_term_mode, font=("Consolas", 9, "bold"))
        self.mode_btn.pack(side=tk.LEFT, padx=2)
        tk.Label(input_frame, text=" > ", bg="#333", fg="white").pack(side=tk.LEFT)
        self.term_input = tk.Entry(input_frame, bg="#333", fg="white", font=("Consolas", 10), insertbackground="white")
        self.term_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.term_input.bind("<Return>", self.handle_terminal_input); self.term_input.bind("<Tab>", self.handle_tab_autocomplete) 
        
        # --- GLOBAL BINDINGS ---
        self.root.bind_all("<F1>", lambda e: self.run_simulation())
        self.root.bind_all("<F2>", lambda e: self.open_waves())
        self.root.bind_all("<F3>", lambda e: self.generate_schematic())
        self.root.bind_all("<F4>", lambda e: self.run_synthesis_flow())
        self.root.bind_all("<Control-n>", lambda e: self.new_file())
        self.root.bind_all("<Control-s>", lambda e: self.save_file())
        self.root.bind_all("<grave>", self.activate_sk_mode)
        self.root.bind_all("<Key>", self.handle_widget_key_intercept)

        self.refresh_file_tree(); self.update_ui_labels()
        self.log_system(f"Silis v40 Ready. CWD: {self.cwd}", "SYS")
        self.check_dependencies()
        self.root.after(100, self.update_log_view) # START FIREHOSE

    # =========================================================================
    #                     UI BUILDERS & CORE ACTIONS
    # =========================================================================
    
    def create_toolbar(self):
        self.toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED, bg="#e1e1e1"); self.toolbar.pack(side=tk.TOP, fill=tk.X)
        tk.Button(self.toolbar, text="New", command=self.new_file).pack(side=tk.LEFT, padx=2)
        tk.Button(self.toolbar, text="Save", command=self.save_file).pack(side=tk.LEFT, padx=2)
        tk.Frame(self.toolbar, width=20, bg="#e1e1e1").pack(side=tk.LEFT)
        
        self.btn_f1 = tk.Button(self.toolbar, text="F1 Compile", bg="#d4edda", command=self.run_simulation)
        self.btn_f1.pack(side=tk.LEFT, padx=2)
        tk.Button(self.toolbar, text="F2 Waves", bg="#cff4fc", command=self.open_waves).pack(side=tk.LEFT, padx=2)
        self.btn_f3 = tk.Button(self.toolbar, text="F3 Schem", bg="#fff3cd", command=self.generate_schematic)
        self.btn_f3.pack(side=tk.LEFT, padx=2)
        self.btn_f4 = tk.Button(self.toolbar, text="F4 Synth", bg="#ffeebb", command=self.run_synthesis_flow)
        self.btn_f4.pack(side=tk.LEFT, padx=2)
        
        # EMERGENCY STOP BUTTON
        self.btn_stop = tk.Button(self.toolbar, text="🛑 STOP", bg="#ffcccc", fg="red", command=self.stop_process, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=10)
        
        tk.Button(self.toolbar, text="⚙ Settings", command=self.open_settings).pack(side=tk.RIGHT, padx=5)

    def set_running_state(self, is_running):
        self.is_running_job = is_running
        state = "disabled" if is_running else "normal"
        stop_state = "normal" if is_running else "disabled"
        self.btn_f1.config(state=state)
        self.btn_f3.config(state=state)
        self.btn_f4.config(state=state)
        self.btn_stop.config(state=stop_state)

    def stop_process(self):
        if self.process:
            self.log_system("Sending Kill Signal...", "ERROR")
            self.process.kill()
            self.process = None
        self.set_running_state(False)

    def new_file(self): 
        self.current_file = None; self.editor.delete(1.0, tk.END)
        self.log_system("New File Created", "SYS")

    def save_file(self):
        if not self.current_file:
            f = filedialog.asksaveasfilename(initialdir=self.cwd); 
            if not f: return
            self.current_file = f
        try:
            with open(self.current_file, "w") as f: f.write(self.editor.get(1.0, tk.END))
            self.refresh_file_tree()
            self.log_system(f"Saved: {os.path.basename(self.current_file)}", "SUCCESS")
        except PermissionError:
            self.log_system(f"Permission Denied: Cannot save {os.path.basename(self.current_file)}", "ERROR")
            messagebox.showerror("Permission Error", f"Cannot save to {self.current_file}.\nTry saving as a new file.")
            self.current_file = None 
            self.save_file()
        except Exception as e:
            self.log_system(f"Save Error: {e}", "ERROR")

    def check_dependencies(self):
        has_node = shutil.which("netlistsvg") is not None
        has_rsvg = shutil.which("rsvg-convert") is not None
        has_sta  = shutil.which("sta") is not None
        
        if has_node and has_rsvg: self.log_system("NetlistSVG: Ready", "SUCCESS")
        else: self.log_system("NetlistSVG: Missing (Fallback: Graphviz)", "WARN")
        
        if has_sta: self.log_system("OpenSTA: Ready", "SUCCESS")
        else: self.log_system("OpenSTA: Missing (F4 STA will fail)", "ERROR")

    def update_term_colors(self):
        for tag, color in self.term_colors.items(): self.term_log.tag_config(tag, foreground=color)
    
    def update_ui_labels(self):
        self.file_frame.config(text=f"Explorer (`+{self.key_map['focus_files']})")
        self.editor_frame.config(text=f"Code (`+{self.key_map['focus_editor']})")
        self.schem_frame.config(text=f"Schematic (`+{self.key_map['focus_schem']})")
        self.term_frame.config(text=f"Terminal (`+{self.key_map['focus_terminal']})")

    # =========================================================================
    #                    SMART PARSING & ORGANIZER
    # =========================================================================
    
    def find_top_module(self):
        search_dirs = [self.cwd]
        if os.path.exists(os.path.join(self.cwd, "source")): search_dirs.append(os.path.join(self.cwd, "source"))
        
        all_v = []
        for d in search_dirs: all_v.extend(glob.glob(os.path.join(d, "*.v")))
        
        defined = set(); instantiated = set()
        for fpath in all_v:
            if "tb_" in fpath or "_tb" in fpath or "test_" in fpath: continue
            with open(fpath, 'r') as f: content = f.read()
            defs = re.findall(r'module\s+(\w+)', content)
            for d in defs: defined.add(d)
            insts = re.findall(r'(\w+)\s+\w+\s*\(', content)
            for i in insts: instantiated.add(i)
        candidates = list(defined - instantiated)
        if len(candidates) == 1: return candidates[0]
        if len(candidates) > 1:
            self.log_system(f"Ambiguous Top: {candidates}. Using first.", "WARN")
            return candidates[0]
        return None

    def get_context_target(self):
        content = self.editor.get(1.0, tk.END)
        match = re.search(r'module\s+(\w+)', content)
        if not match: return None, None
        module_name = match.group(1)
        is_tb = "tb" in module_name.lower() or "test" in module_name.lower()
        target_base = module_name
        if is_tb:
            clean = module_name.replace("tb_", "").replace("_tb", "").replace("test_", "")
            if clean: target_base = clean
        return module_name, target_base

    def ensure_project_workspace(self, target_base):
        project_dir_name = f"{target_base}_project"
        cwd_abs = os.path.abspath(self.cwd)
        
        if os.path.basename(cwd_abs) == project_dir_name:
            project_root = cwd_abs
        elif os.path.basename(cwd_abs) in ["source", "netlist", "reports"] and os.path.basename(os.path.dirname(cwd_abs)) == project_dir_name:
             project_root = os.path.dirname(cwd_abs)
        else:
             project_root = os.path.join(cwd_abs, project_dir_name)

        source_dir = os.path.join(project_root, "source")
        for d in ["source", "netlist", "reports"]:
            path = os.path.join(project_root, d)
            if not os.path.exists(path): os.makedirs(path)

        files_to_organize = [f"{target_base}.v", f"tb_{target_base}.v", f"{target_base}_tb.v", f"test_{target_base}.v"]
        search_dirs = list(set([cwd_abs, project_root])) 
        
        for fname in files_to_organize:
            if os.path.exists(os.path.join(source_dir, fname)): continue 
            
            found_src = None
            for s_dir in search_dirs:
                possible = os.path.join(s_dir, fname)
                if os.path.exists(possible): found_src = possible; break
            
            if found_src:
                dest = os.path.join(source_dir, fname)
                try:
                    if self.current_file and os.path.abspath(self.current_file) == found_src:
                         shutil.move(found_src, dest)
                         self.current_file = dest
                         self.root.title(f"Silis - {fname} (Moved)")
                         self.log_system(f"Moved active {fname} to source/", "SYS")
                    else:
                         shutil.move(found_src, dest)
                         self.log_system(f"Moved {fname} to source/", "SYS")
                except Exception as e: self.log_system(f"Failed to move {fname}: {e}", "ERROR")

        self.refresh_file_tree()
        return project_root

    # =========================================================================
    #                    SYNTHESIS ENGINE (F4) + OPENSTA
    # =========================================================================

    def run_synthesis_flow(self):
        if self.is_running_job: return
        if not self.pdk_path or not os.path.exists(self.pdk_path):
            messagebox.showerror("Error", "No PDK Library selected.\nPlease go to Settings.")
            return

        target_base = self.find_top_module()
        if not target_base: 
            _, target_base = self.get_context_target()
            if not target_base: self.log_system("No Top Module.", "ERROR"); return

        self.set_running_state(True)
        self.log_system(f"Starting Implementation for: {target_base}", "SYS")
        work_dir = self.ensure_project_workspace(target_base)
        
        # 1. SDC Generation
        sdc_path = os.path.join(work_dir, "netlist", f"{target_base}.sdc")
        if not os.path.exists(sdc_path):
             sdc_data = self.open_constraint_wizard(target_base)
             if not sdc_data: 
                 self.log_system("Synthesis Cancelled (No SDC).", "WARN"); self.set_running_state(False); return
             with open(sdc_path, 'w') as f: f.write(sdc_data)
        
        src_dir = os.path.join(work_dir, "source")
        sources = glob.glob(os.path.join(src_dir, "*.v"))
        sources = [s for s in sources if "tb_" not in s] 
        if not sources: self.log_system("No source files found.", "ERROR"); self.set_running_state(False); return

        # 2. Yosys Synthesis
        netlist_path = f"netlist/{target_base}_netlist.v"
        cmd_synth = f"""
        read_liberty -lib {self.pdk_path}
        read_verilog {' '.join(sources)}
        synth -top {target_base}
        dfflibmap -liberty {self.pdk_path}
        abc -liberty {self.pdk_path}
        stat -liberty {self.pdk_path} -json
        write_verilog -noattr {netlist_path}
        """
        
        self.log_system("Yosys Synthesis...", "SYS")
        
        # 3. OpenSTA (Preparation)
        tcl_script = f"""
        read_liberty {self.pdk_path}
        read_verilog {netlist_path}
        link_design {target_base}
        read_sdc netlist/{target_base}.sdc
        report_checks -fields {{capacitance slew input_pins fanout}}
        report_power
        exit
        """
        tcl_path = os.path.join(work_dir, "reports", "sta.tcl")
        with open(tcl_path, "w") as f: f.write(tcl_script)

        # 4. CHAINED EXECUTION THREAD
        def synth_thread():
            try:
                # RUN YOSYS
                res = subprocess.run(["yosys", "-p", cmd_synth], cwd=work_dir, capture_output=True, text=True)
                with open(os.path.join(work_dir, "reports", "synthesis.log"), 'w') as f: f.write(res.stdout + res.stderr)
                
                if res.returncode != 0:
                    self.queue.put("[ERROR] Synthesis Failed.\n")
                    self.queue.put(res.stderr + "\n")
                    self.queue.put("STOP_SIGNAL")
                    return

                area_match = re.search(r"Chip area for module.*:\s+([\d\.]+)", res.stdout)
                if area_match:
                    area = area_match.group(1)
                    with open(os.path.join(work_dir, "reports", "area.rpt"), 'w') as f: f.write(f"Module: {target_base}\nChip Area: {area} sq units\n")
                    self.queue.put(f"[SUCCESS] Area: {area} sq units\n")

                # RUN STA
                self.queue.put("[SYS] Running OpenSTA...\n")
                res = subprocess.run(["sta", tcl_path], cwd=work_dir, capture_output=True, text=True)
                
                log_path = os.path.join(work_dir, "reports", "sta.log")
                with open(log_path, "w") as f:
                    f.write("--- OpenSTA STDOUT ---\n" + res.stdout + "\n--- OpenSTA STDERR ---\n" + res.stderr)
                
                self.queue.put("[SUCCESS] Implementation Complete.\n")
                self.parse_and_show_summary(log_path)
                
            except Exception as e:
                self.queue.put(f"[ERROR] Exception: {e}\n")
            finally:
                self.queue.put("STOP_SIGNAL")

        self.process = threading.Thread(target=synth_thread, daemon=True)
        self.process.start()

    def parse_and_show_summary(self, log_path):
        wns = "N/A"
        pwr = "N/A"
        if os.path.exists(log_path):
            with open(log_path, 'r') as f: content = f.read()
            if "No paths found" in content: wns = "No Paths (Comb.)"
            else:
                match = re.search(r"slack\s+\((.*?)\)\s+([-\d\.]+)", content)
                if match: wns = f"{match.group(2)} ({match.group(1)})"
            
            match = re.search(r"Total\s+[-\d\.e]+\s+[-\d\.e]+\s+[-\d\.e]+\s+([-\d\.e]+)", content)
            if match: 
                val = float(match.group(1))
                if val < 1e-3: pwr = f"{val*1e6:.2f} uW"
                elif val < 1: pwr = f"{val*1e3:.2f} mW"
                else: pwr = f"{val:.4f} W"

        summary = f"\n[IMPL SUMMARY]\nTiming (Slack): {wns}\nTotal Power:    {pwr}\nSee reports/sta.log for details.\n"
        self.queue.put(summary)

    def open_constraint_wizard(self, module_name):
        wiz = tk.Toplevel(self.root); wiz.title("Constraint Wizard"); wiz.geometry("400x500")
        wiz.transient(self.root); wiz.grab_set()
        fields = {}
        def add_field(label, tooltip):
            f = tk.Frame(wiz); f.pack(fill=tk.X, padx=10, pady=5)
            tk.Label(f, text=label, width=20, anchor="w", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
            e = tk.Entry(f); e.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            tk.Label(wiz, text=tooltip, font=("Arial", 8, "italic"), fg="gray").pack(anchor="w", padx=10)
            fields[label] = e; return e

        e1 = add_field("Clock Port", "Name of the clock input (e.g. clk)")
        e1.insert(0, "clk"); e1.focus_set()
        add_field("Frequency (MHz)", "Target clock speed")
        add_field("Input Delay (ns)", "External logic delay arrival time")
        add_field("Output Delay (ns)", "Time required by external destination")
        add_field("Max Fanout", "Maximum loads a single cell can drive")
        add_field("Load Cap (pF)", "Capacitance on output pins")

        entries = list(fields.values())
        for i, ent in enumerate(entries):
            if i < len(entries) - 1: ent.bind("<Return>", lambda e, next_ent=entries[i+1]: next_ent.focus_set())
        
        result_data = [None] 

        def generate():
            if not fields["Frequency (MHz)"].get():
                if not messagebox.askyesno("Warning", "Clock Frequency not set. Continue?"): return
            
            sdc = f"# SDC Constraints for {module_name}\ncurrent_design {module_name}\n\n"
            clk = fields["Clock Port"].get(); freq = fields["Frequency (MHz)"].get()
            if clk and freq:
                period = 1000.0 / float(freq)
                sdc += f"create_clock -name {clk} -period {period} [get_ports {clk}]\n"
            in_d = fields["Input Delay (ns)"].get()
            if in_d: sdc += f"set_input_delay -clock {clk} -max {in_d} [all_inputs]\n"
            out_d = fields["Output Delay (ns)"].get()
            if out_d: sdc += f"set_output_delay -clock {clk} -max {out_d} [all_outputs]\n"
            fan = fields["Max Fanout"].get()
            if fan: sdc += f"set_max_fanout {fan} [current_design]\n"
            load = fields["Load Cap (pF)"].get()
            if load: sdc += f"set_load {load} [all_outputs]\n"
            result_data[0] = sdc; wiz.destroy()

        entries[-1].bind("<Return>", lambda e: generate())
        wiz.bind("<Escape>", lambda e: wiz.destroy())
        tk.Button(wiz, text="Generate Constraints", bg="#d4edda", command=generate).pack(pady=20, fill=tk.X, padx=10)
        self.root.wait_window(wiz)
        return result_data[0]

    # =========================================================================
    #                          SIMULATION & EXECUTION
    # =========================================================================

    def run_simulation(self):
        if self.is_running_job: return
        if self.current_file: self.save_file()
        
        self.term_mode = "SIM"; self.mode_btn.config(text="[SIM]", bg="#198754")
        module_name, target_base = self.get_context_target()
        if not module_name: self.log_system("No module found.", "ERROR"); return
        
        self.set_running_state(True)
        work_dir = self.ensure_project_workspace(target_base)
        src_dir = os.path.join(work_dir, "source")
        
        tb_file = None
        candidates = [f"tb_{target_base}.v", f"{target_base}_tb.v", f"test_{target_base}.v"]
        if self.current_file and os.path.basename(self.current_file) in candidates:
             tb_file = os.path.basename(self.current_file)
        else:
             for c in candidates:
                 if os.path.exists(os.path.join(src_dir, c)): tb_file = c; break
        
        if not tb_file:
            self.log_system(f"No TB found. Syntax Check.", "WARN")
            self.run_simple_compile(work_dir, target_base); return
        
        temp_tb = "._temp_tb.v"
        try:
            read_path = os.path.join(src_dir, tb_file)
            if not os.path.exists(read_path): 
                 self.log_system(f"Error: TB {tb_file} not found.", "ERROR"); self.set_running_state(False); return

            with open(read_path, 'r') as f: tb_content = f.read()
            if "$dumpfile" not in tb_content:
                pattern = r"(initial\s+begin)"
                injection = f'\\1\n        $dumpfile("{target_base}.vcd"); $dumpvars(0);'
                new_content = re.sub(pattern, injection, tb_content, count=1, flags=re.IGNORECASE)
            else: new_content = tb_content 
            
            with open(os.path.join(work_dir, temp_tb), 'w') as f: f.write(new_content)
            all_v = glob.glob(os.path.join(src_dir, "*.v"))
            compile_list = [f for f in all_v if os.path.basename(f) != tb_file] + [os.path.join(work_dir, temp_tb)]
            
            if not compile_list:
                self.log_system("Error: No sources.", "ERROR"); self.set_running_state(False); return

            outfile = f"{target_base}.out"
            cmd = ["iverilog", "-o", outfile] + compile_list
            self.log_system(f"Compiling...", "SYS")
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
            
            if os.path.exists(os.path.join(work_dir, temp_tb)): os.remove(os.path.join(work_dir, temp_tb))
            if res.returncode != 0: 
                self.log_system(f"COMPILE ERROR:\n{res.stderr}", "ERROR"); self.set_running_state(False); return
            
            self.log_system("Running Simulation...", "SUCCESS")
            self.run_process_threaded(["vvp", outfile], cwd=work_dir)
        except Exception as e: self.log_system(f"Build Error: {e}", "ERROR"); self.set_running_state(False)

    def run_simple_compile(self, work_dir, target_base):
        src_dir = os.path.join(work_dir, "source")
        all_v = glob.glob(os.path.join(src_dir, "*.v"))
        outfile = f"{target_base}.out"
        res = subprocess.run(["iverilog", "-o", outfile] + all_v, capture_output=True, text=True, cwd=work_dir)
        if res.returncode != 0: self.log_system(f"SYNTAX ERROR:\n{res.stderr}", "ERROR")
        else: self.log_system("Syntax OK.", "SUCCESS")
        self.set_running_state(False)

    def generate_schematic(self):
        if self.is_running_job: return
        if self.current_file: self.save_file()
        module_name, target_base = self.get_context_target()
        if not target_base: self.log_system("No module found.", "ERROR"); return
        
        self.set_running_state(True)
        work_dir = self.ensure_project_workspace(target_base)
        src_dir = os.path.join(work_dir, "source")
        all_v = glob.glob(os.path.join(src_dir, "*.v"))
        synth_files = [f for f in all_v if not ("tb_" in f or "_tb" in f or "test_" in f)]
        self.log_system(f"Schematic for {target_base}...", "SYS")
        prefix = target_base
        use_netlist = (self.schem_engine == "NetlistSVG") or (self.schem_engine == "Auto" and shutil.which("netlistsvg"))
        
        def schem_thread():
            try:
                if use_netlist:
                    cmd = f"yosys -p 'read_verilog {' '.join(synth_files)}; hierarchy -check -auto-top; proc; opt; autoname; write_json {prefix}.json' -q"
                    subprocess.run(cmd, shell=True, cwd=work_dir, capture_output=True)
                    if os.path.exists(os.path.join(work_dir, f"{prefix}.json")):
                        subprocess.run(f"netlistsvg {prefix}.json -o {prefix}.svg", shell=True, cwd=work_dir, capture_output=True)
                        if os.path.exists(os.path.join(work_dir, f"{prefix}.svg")):
                            self.inject_svg_css(os.path.join(work_dir, f"{prefix}.svg"))
                            subprocess.run(f"rsvg-convert {prefix}.svg -o {prefix}.png", shell=True, cwd=work_dir, capture_output=True)
                            self.queue.put("LOAD_IMAGE")
                else:
                    cmd = f"yosys -p 'read_verilog {' '.join(synth_files)}; hierarchy -check -auto-top; proc; opt; autoname; show -format dot -prefix {prefix}' -q"
                    subprocess.run(cmd, shell=True, cwd=work_dir, capture_output=True)
                    if os.path.exists(os.path.join(work_dir, f"{prefix}.dot")):
                        self.patch_graphviz_style(os.path.join(work_dir, f"{prefix}.dot"))
                        subprocess.run(f"dot -Tpng {prefix}.dot -o {prefix}.png", shell=True, cwd=work_dir, capture_output=True)
                        self.queue.put("LOAD_IMAGE")
            except Exception as e: self.queue.put(f"[ERROR] Schem Error: {e}\n")
            finally: self.queue.put("STOP_SIGNAL")

        threading.Thread(target=schem_thread, daemon=True).start()

    def open_waves(self):
        _, target_base = self.get_context_target()
        if target_base:
            possible_path = os.path.join(self.cwd, f"{target_base}_project", f"{target_base}.vcd")
            if os.path.exists(possible_path):
                subprocess.Popen(["gtkwave", possible_path], cwd=os.path.dirname(possible_path))
                return
        vcds = glob.glob(os.path.join(self.cwd, "*.vcd"))
        if vcds: subprocess.Popen(["gtkwave", max(vcds, key=os.path.getctime)], cwd=self.cwd)
        else: self.log_system("No .vcd files found.", "WARN")

    # =========================================================================
    #                                  LOGIC
    # =========================================================================

    def activate_sk_mode(self, event):
        self.sk_active = True
        self.toolbar.config(bg="#00FFFF") # VISUAL BEACON
        self.root.after(self.sk_timeout, self.reset_sk)
        return "break"

    def reset_sk(self):
        self.sk_active = False
        self.toolbar.config(bg="#e1e1e1")

    def handle_widget_key_intercept(self, event):
        if not self.sk_active: return None
        key = event.keysym.lower()
        if key == self.key_map["focus_editor"]: self.editor.focus_set(); self.log_system("Focus: Editor", "SYS")
        elif key == self.key_map["focus_terminal"]: self.term_input.focus_set(); self.log_system("Focus: Terminal", "SYS")
        elif key == self.key_map["focus_files"]: self.tree.focus_set(); self.log_system("Focus: Files", "SYS")
        elif key == self.key_map["focus_schem"]: self.schematic_viewer.focus_set(); self.log_system("Focus: Schematic", "SYS")
        elif key == self.key_map["term_toggle"]: self.toggle_term_mode(); self.log_system("Mode Toggled", "SYS")
        self.reset_sk(); return "break"
        
    def run_process_threaded(self, command, cwd):
        def target():
            try:
                self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=cwd)
                for line in iter(self.process.stdout.readline, ''): self.queue.put(line)
                self.process.stdout.close(); self.process.wait()
            except Exception as e: self.queue.put(f"\n[Error]: {e}\n")
            finally: self.queue.put("STOP_SIGNAL")
        threading.Thread(target=target, daemon=True).start()

    # --- FIREHOSE VALVE: THROTTLED UPDATE ---
    def update_log_view(self):
        # Read everything currently in queue to prevent backlog
        lines = []
        try:
            while not self.queue.empty():
                msg = self.queue.get_nowait()
                if msg == "STOP_SIGNAL":
                    self.set_running_state(False)
                    self.process = None
                elif msg == "LOAD_IMAGE":
                    _, target_base = self.get_context_target()
                    path = os.path.join(self.cwd, f"{target_base}_project", f"{target_base}.png")
                    self.schematic_viewer.load_image(path)
                else:
                    lines.append(msg)
        except queue.Empty: pass
        
        if lines:
            big_text = "".join(lines)
            self.term_log.insert(tk.END, big_text)
            self.term_log.see(tk.END)
            
        self.root.after(50, self.update_log_view) # Check again in 50ms

    def patch_graphviz_style(self, dot_path):
        with open(dot_path, 'r') as f: content = f.read()
        content = re.sub(r'label="\$_(AND|NAND)_', r'shape=box, style=filled, fillcolor="#007ACC", label="$_\1_', content)
        content = re.sub(r'label="\$_(OR|NOR)_', r'shape=box, style=filled, fillcolor="#D65D0E", label="$_\1_', content)
        content = re.sub(r'label="\$_(NOT|BUF)_', r'shape=triangle, style=filled, fillcolor="#98971a", label="$_\1_', content)
        with open(dot_path, 'w') as f: f.write(content)

    def inject_svg_css(self, svg_path):
        bg_color = "white"; line_color = "black"
        with open(svg_path, 'r') as f: svg = f.read()
        if '<style>' not in svg: svg = svg.replace('<svg ', f'<svg style="background-color: {bg_color};" ')
        else: svg = svg.replace('<svg ', f'<svg style="background-color: {bg_color};" ')
        style_block = f"""<style> svg {{ background-color: {bg_color} !important; }} text {{ fill: {line_color} !important; font-family: Consolas, sans-serif; }} .edge path {{ stroke: {line_color} !important; }} .node rect, .node circle, .node path {{ stroke: {line_color} !important; fill: none; }} .pin {{ stroke: {line_color} !important; }} </style>"""
        svg = svg.replace('>', f'>{style_block}', 1)
        with open(svg_path, 'w') as f: f.write(svg)

    def change_directory_silent(self, new_dir, record=True):
        try: 
            os.chdir(new_dir); self.cwd = os.getcwd()
            if record:
                if self.history_index < len(self.dir_history) - 1:
                    self.dir_history = self.dir_history[:self.history_index+1]
                if not self.dir_history or self.dir_history[-1] != self.cwd:
                    self.dir_history.append(self.cwd)
                    self.history_index = len(self.dir_history) - 1
        except Exception as e: self.log_system(f"Error: {e}", "ERROR")

    def nav_back(self, event=None):
        if self.history_index > 0:
            self.history_index -= 1
            path = self.dir_history[self.history_index]
            self.change_directory_silent(path, record=False)
            self.refresh_file_tree()
            self.log_system(f"Back -> {os.path.basename(path)}", "SYS")
        return "break"

    def nav_forward(self, event=None):
        if self.history_index < len(self.dir_history) - 1:
            self.history_index += 1
            path = self.dir_history[self.history_index]
            self.change_directory_silent(path, record=False)
            self.refresh_file_tree()
            self.log_system(f"Forward -> {os.path.basename(path)}", "SYS")
        return "break"

    def refresh_file_tree(self):
        self.tree.delete(*self.tree.get_children())
        root_node = self.tree.insert("", tk.END, text=os.path.basename(self.cwd) or self.cwd, open=True, values=(self.cwd, "dir"))
        self.populate_node(root_node, self.cwd); self.on_tree_focus(None)

    def populate_node(self, parent_id, path):
        self.tree.delete(*self.tree.get_children(parent_id))
        try: items = os.listdir(path)
        except: return
        items.sort(key=lambda x: (not os.path.isdir(os.path.join(path, x)), x))
        for item in items:
            full_path = os.path.join(path, item)
            is_dir = os.path.isdir(full_path)
            oid = self.tree.insert(parent_id, tk.END, text=item, values=(full_path, "dir" if is_dir else "file"))
            if is_dir: self.tree.insert(oid, tk.END, text="dummy")

    def on_tree_focus(self, event):
        def _select():
            if not self.tree.selection():
                c = self.tree.get_children()
                if c: self.tree.selection_set(c[0]); self.tree.focus(c[0])
        self.root.after(10, _select)

    def on_tree_expand(self, event):
        item_id = self.tree.focus(); 
        if not item_id: return
        path, ftype = self.tree.item(item_id, "values")
        if ftype == "dir": self.change_directory_silent(path); self.populate_node(item_id, path)
    
    def on_tree_enter_key(self, event):
        item_id = self.tree.focus(); 
        if not item_id: return
        path, ftype = self.tree.item(item_id, "values")
        if ftype == "file": self.open_file_in_editor(path)
        else: 
            self.change_directory_silent(path)
            if not self.tree.item(item_id, "open"): self.populate_node(item_id, path); self.tree.item(item_id, open=True)
            else: self.tree.item(item_id, open=False)
        return "break"
    
    def on_tree_double_click(self, event):
        item_id = self.tree.selection()[0]; path, ftype = self.tree.item(item_id, "values")
        if ftype == "dir": self.change_directory_silent(path)
        else:
            if path.endswith(".vcd"):
                subprocess.Popen(["gtkwave", path], cwd=os.path.dirname(path))
            else:
                parent_dir = os.path.dirname(path); self.change_directory_silent(parent_dir); self.open_file_in_editor(path)

    def on_tree_up_dir(self, event):
        try: os.chdir(".."); self.cwd = os.getcwd(); self.refresh_file_tree(); self.log_system(f"CD .. -> {self.cwd}", "SYS")
        except Exception as e: self.log_system(f"Error: {e}", "ERROR")

    def open_file_in_editor(self, path):
        try:
            with open(path, "r") as f: content = f.read()
            self.editor.delete(1.0, tk.END); self.editor.insert(tk.END, content)
            self.current_file = path; self.root.title(f"Silis - {os.path.basename(path)}")
        except: pass

    def toggle_term_mode(self):
        if self.term_mode == "SHELL": self.term_mode = "SIM"; self.mode_btn.config(text="[SIM]", bg="#198754") 
        else: self.term_mode = "SHELL"; self.mode_btn.config(text="[SHELL]", bg="#0d6efd")

    def handle_terminal_input(self, event):
        cmd = self.term_input.get(); self.term_input.delete(0, tk.END)
        if self.term_mode == "SHELL": self.run_shell_command(cmd)
        else: self.send_sim_input(cmd)

    def run_shell_command(self, cmd):
        self.term_log.insert(tk.END, f"$ {cmd}\n", "INPUT")
        if cmd.startswith("cd "):
            target = cmd[3:].strip()
            self.change_directory_silent(target)
            self.refresh_file_tree()
            return
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=self.cwd)
            if res.stdout: self.term_log.insert(tk.END, res.stdout, "SUCCESS")
            if res.stderr: self.term_log.insert(tk.END, res.stderr, "ERROR")
        except Exception as e: self.log_system(f"Exec Error: {e}", "ERROR")
        self.term_log.see(tk.END)

    def send_sim_input(self, text):
        if self.process and self.process.stdin:
            try: self.process.stdin.write(text + "\n"); self.process.stdin.flush(); self.term_log.insert(tk.END, f"[INPUT]: {text}\n", "INPUT")
            except Exception as e: self.log_system(f"Input Error: {e}", "ERROR")
        else: self.log_system("Error: No simulation running.", "ERROR")
    
    def log_system(self, msg, tag="SYS"): 
        self.term_log.insert(tk.END, f"[SYS]: {msg}\n", tag); self.term_log.see(tk.END)

    def print_grid(self, items):
        self.log_system("Options:", "SYS")
        max_len = max(len(i) for i in items) + 2; cols = max(1, 80 // max_len)
        line = ""
        for i, item in enumerate(items):
            line += f"{item:<{max_len}}"
            if (i + 1) % cols == 0: self.term_log.insert(tk.END, line + "\n", "SYS"); line = ""
        if line: self.term_log.insert(tk.END, line + "\n", "SYS")
        self.term_log.see(tk.END)

    def handle_tab_autocomplete(self, event):
        if self.term_mode != "SHELL": return "break"
        full_text = self.term_input.get()
        if " " in full_text: base, prefix = full_text.rsplit(" ", 1); base += " "
        else: base, prefix = "", full_text
        head, tail = os.path.split(prefix)
        search_dir = os.path.join(self.cwd, head) if head else self.cwd
        try:
            if not os.path.isdir(search_dir): return "break"
            matches = [f for f in os.listdir(search_dir) if f.startswith(tail)]
            if len(matches) == 1:
                match = matches[0]; full_path = os.path.join(head, match)
                if os.path.isdir(os.path.join(self.cwd, full_path)): full_path += "/"
                self.term_input.delete(0, tk.END); self.term_input.insert(0, base + full_path)
            elif len(matches) > 1: self.print_grid(matches)
        except Exception as e: self.log_system(f"Autocomplete Error: {e}", "ERROR")
        return "break"
        
    def open_settings(self):
        win = tk.Toplevel(self.root); win.title("Settings"); win.geometry("300x600")
        tk.Label(win, text="Superkey (` + ...)", font=("Arial", 10, "bold")).pack(pady=5)
        entries = {}
        for action, key in self.key_map.items():
            f = tk.Frame(win); f.pack(fill=tk.X, padx=10)
            tk.Label(f, text=action, width=20, anchor="w").pack(side=tk.LEFT)
            e = tk.Entry(f, width=5); e.insert(0, key); e.pack(side=tk.RIGHT); entries[action] = e
        
        # PDK SELECTOR
        tk.Label(win, text="PDK Library (.lib)", font=("Arial", 10, "bold")).pack(pady=5)
        f_pdk = tk.Frame(win); f_pdk.pack(fill=tk.X, padx=10)
        e_pdk = tk.Entry(f_pdk); e_pdk.insert(0, self.pdk_path); e_pdk.pack(side=tk.LEFT, fill=tk.X, expand=True)
        def browse_pdk():
            path = filedialog.askopenfilename(filetypes=[("Liberty", "*.lib")])
            if path: e_pdk.delete(0, tk.END); e_pdk.insert(0, path)
        tk.Button(f_pdk, text="...", command=browse_pdk).pack(side=tk.RIGHT)

        tk.Label(win, text="Schematic Engine", font=("Arial", 10, "bold")).pack(pady=5)
        eng_var = tk.StringVar(value=self.schem_engine)
        ttk.OptionMenu(win, eng_var, self.schem_engine, "Auto", "Graphviz", "NetlistSVG").pack()
        
        # CLEAR ROOT BUTTON
        tk.Label(win, text="Maintenance", font=("Arial", 10, "bold")).pack(pady=10)
        def clear_root():
            count = 0
            for ext in ["*.out", "*.vcd", "*.json", "*.log", "*.history"]:
                for f in glob.glob(os.path.join(self.cwd, ext)):
                    with suppress(OSError): os.remove(f); count += 1
            messagebox.showinfo("Done", f"Cleaned {count} root files.\nProject folders were NOT touched.")
            self.refresh_file_tree()
        tk.Button(win, text="Clear Root Directory", bg="#f8d7da", fg="red", command=clear_root).pack(pady=5)

        def save():
            for action, e in entries.items(): self.key_map[action] = e.get()
            self.schem_engine = eng_var.get()
            self.pdk_path = e_pdk.get()
            self.update_ui_labels(); self.log_system("Settings Saved.", "SUCCESS")
            if os.path.exists(os.path.join(self.cwd, "schematic.dot")) or os.path.exists(os.path.join(self.cwd, "schematic.svg")):
                self.generate_schematic()
            win.destroy()
        tk.Button(win, text="Save", command=save, bg="#d4edda").pack(pady=15)
        
    def update_ui_labels(self):
        self.file_frame.config(text=f"Explorer (`+{self.key_map['focus_files']})")
        self.editor_frame.config(text=f"Code (`+{self.key_map['focus_editor']})")
        self.schem_frame.config(text=f"Schematic (`+{self.key_map['focus_schem']})")
        self.term_frame.config(text=f"Terminal (`+{self.key_map['focus_terminal']})")
        
    def delete_file_prompt(self, event=None):
        sel = self.tree.selection()
        if not sel: return
        path, ftype = self.tree.item(sel[0], "values")
        if not path or path == "dir": return
        confirm = messagebox.askyesno("Delete", f"Are you sure you want to delete:\n{os.path.basename(path)}?")
        if confirm:
            try:
                if ftype == "dir": shutil.rmtree(path)
                else: os.remove(path)
                self.log_system(f"Deleted: {path}", "SUCCESS")
                self.refresh_file_tree()
            except Exception as e: self.log_system(f"Delete Failed: {e}", "ERROR")
            
    # --- Context Menu with Rename ---
    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            menu = Menu(self.root, tearoff=0)
            menu.add_command(label="Delete", command=self.delete_file_prompt)
            menu.add_command(label="Rename", command=self.rename_file_prompt)
            menu.post(event.x_root, event.y_root)

    def rename_file_prompt(self):
        sel = self.tree.selection()
        if not sel: return
        path, ftype = self.tree.item(sel[0], "values")
        if not path: return
        
        old_name = os.path.basename(path)
        new_name = simpledialog.askstring("Rename", "New Name:", initialvalue=old_name)
        if not new_name: return
        
        dir_name = os.path.dirname(path)
        new_path = os.path.join(dir_name, new_name)
        
        try:
            os.rename(path, new_path)
            self.log_system(f"Renamed {old_name} -> {new_name}", "SUCCESS")
            if self.current_file == path:
                self.current_file = new_path
                self.root.title(f"Silis - {new_name}")
            self.refresh_file_tree()
        except Exception as e:
            self.log_system(f"Rename Error: {e}", "ERROR")

    def clean_products(self):
        exts = ["*.out", "*.vvp", "*.vcd", "*.dot", "*.png", "*.svg", "*.history", "*.json"]
        count = 0
        for ext in exts:
            for f in glob.glob(os.path.join(self.cwd, ext)):
                with suppress(OSError): os.remove(f); count += 1
        self.log_system(f"Cleaned {count} artifacts.", "SUCCESS"); self.refresh_file_tree()

if __name__ == "__main__":
    root = tk.Tk()
    app = SilisIDE(root)
    root.mainloop()
