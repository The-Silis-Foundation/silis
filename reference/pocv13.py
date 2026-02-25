import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, Menu
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
        
        self.gutter = tk.Text(self, width=4, padx=4, takefocus=0, border=0, background="#f0f0f0", state="disabled", font=self.font)
        self.gutter.pack(side=tk.LEFT, fill=tk.Y)
        
        self.text = tk.Text(self, font=self.font, undo=True, wrap="none")
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        bridge_numpad(self.text)
        
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.on_scroll)
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.configure(yscrollcommand=self.vsb.set)
        
        self.text.bind("<KeyRelease>", self.on_content_changed)
        self.text.bind("<MouseWheel>", self.sync_scroll)
        self.text.bind("<Button-4>", self.sync_scroll)
        self.text.bind("<Button-5>", self.sync_scroll)
        self.text.bind("<Tab>", self.insert_tab_spaces)
        self.setup_tags()

    def insert_tab_spaces(self, event):
        self.text.insert(tk.INSERT, "    "); return "break"

    def setup_tags(self):
        self.text.tag_configure("KEYWORD", foreground="#0000FF", font=(self.font[0], self.font[1], "bold"))
        self.text.tag_configure("COMMENT", foreground="#008000")
        self.text.tag_configure("STRING", foreground="#A31515")
        self.text.tag_configure("NUMBER", foreground="#800080")
        self.text.tag_configure("ERROR", background="#FFCCCC")

    def on_scroll(self, *args): self.text.yview(*args); self.gutter.yview(*args)
    def sync_scroll(self, event): self.gutter.yview_moveto(self.text.yview()[0])
    def on_content_changed(self, event=None): self.update_line_numbers(); self.highlight_syntax()
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


# ================= MAIN IDE =================

class SilisIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("Silis v22 (Surgical VCD)")
        self.root.geometry("1400x900")
        
        # --- NO CURSOR LOGIC HERE (Fix for WSL) ---

        self.key_map = {"focus_editor":"c", "focus_terminal":"x", "focus_files":"v", "focus_schem":"z", "term_toggle":"s"}
        self.term_colors = {"SYS":"#00FFFF", "INPUT":"#FFFFFF", "ERROR":"#FF5555", "SUCCESS":"#50FA7B", "WARN":"#F1FA8C"}
        
        self.schem_engine = "Auto"; self.schem_theme = "Standard"
        self.sk_active = False; self.sk_timeout = 1000 
        self.current_file = None; self.cwd = os.getcwd(); self.process = None; self.queue = queue.Queue()
        self.term_mode = "SHELL" 
        
        style = ttk.Style(); style.theme_use('clam')
        
        self.create_toolbar() # Creates self.toolbar
        
        self.main_split = ttk.PanedWindow(root, orient=tk.VERTICAL); self.main_split.pack(fill=tk.BOTH, expand=True)
        self.middle_pane = ttk.PanedWindow(self.main_split, orient=tk.HORIZONTAL); self.main_split.add(self.middle_pane, weight=4)
        
        self.file_frame = tk.LabelFrame(self.middle_pane, text="Explorer"); self.middle_pane.add(self.file_frame, weight=1)
        self.tree = ttk.Treeview(self.file_frame, show='tree'); self.tree.pack(fill=tk.BOTH, expand=True)
        bridge_numpad(self.tree)
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_expand); self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Return>", self.on_tree_enter_key); self.tree.bind("<Escape>", self.on_tree_up_dir); self.tree.bind("<FocusIn>", self.on_tree_focus) 
        self.tree.bind("<Delete>", self.delete_file_prompt)
        self.tree_menu = Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="Delete", command=self.delete_file_prompt)
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
        
        # --- GLOBAL BINDINGS (EFFICIENCY) ---
        self.root.bind_all("<F1>", lambda e: self.run_simulation())
        self.root.bind_all("<F2>", lambda e: self.open_waves())
        self.root.bind_all("<F3>", lambda e: self.generate_schematic())
        self.root.bind_all("<Control-n>", lambda e: self.new_file())
        self.root.bind_all("<Control-s>", lambda e: self.save_file())
        self.root.bind_all("<grave>", self.activate_sk_mode)
        self.root.bind_all("<Key>", self.handle_widget_key_intercept)

        self.refresh_file_tree(); self.update_ui_labels()
        self.log_system(f"Silis v22 Ready. CWD: {self.cwd}", "SYS")
        self.check_dependencies()
        self.root.after(100, self.process_queue)

    def check_dependencies(self):
        has_node = shutil.which("netlistsvg") is not None
        has_rsvg = shutil.which("rsvg-convert") is not None
        if has_node and has_rsvg: self.log_system("NetlistSVG Engine: Ready", "SUCCESS")
        else: self.log_system("NetlistSVG Engine: Missing (Falling back to Graphviz)", "WARN")

    def update_term_colors(self):
        for tag, color in self.term_colors.items(): self.term_log.tag_config(tag, foreground=color)

    # ================= CONTEXT LOGIC (SMART TARGET) =================
    
    def get_context_target(self):
        """ Determines the 'DUT' name from the open file. """
        content = self.editor.get(1.0, tk.END)
        # Find module name
        match = re.search(r'module\s+(\w+)', content)
        if not match: return None, None
        module_name = match.group(1)
        
        # Determine if TB or Design
        is_tb = "tb" in module_name.lower() or "test" in module_name.lower()
        
        target_base = module_name
        if is_tb:
            # Try to strip tb_ or _tb to guess the design name (for naming artifacts)
            clean = module_name.replace("tb_", "").replace("_tb", "").replace("test_", "")
            if clean: target_base = clean
            
        return module_name, target_base

    def find_associated_testbench(self, design_name):
        """ If design is open, looks for tb_design.v """
        candidates = [f"tb_{design_name}.v", f"{design_name}_tb.v", f"test_{design_name}.v"]
        for c in candidates:
            if os.path.exists(os.path.join(self.cwd, c)): return c
        return None

    # ================= SIMULATION (SURGICAL VCD) =================

    def run_simulation(self):
        if self.current_file: self.save_file()
        self.term_mode = "SIM"; self.mode_btn.config(text="[SIM]", bg="#198754")
        
        module_name, target_base = self.get_context_target()
        if not module_name: self.log_system("No module found in current file.", "ERROR"); return

        # TARGETED CLEANUP (Only delete THIS module's artifacts)
        self.log_system(f"Target: {target_base}...", "SYS")
        for ext in [".out", ".vcd", ".png"]:
            with suppress(OSError): os.remove(os.path.join(self.cwd, f"{target_base}{ext}"))

        # DETERMINE TB FILE
        tb_file = None
        if "tb" in module_name.lower() or "test" in module_name.lower():
            # Current file is likely the TB
            if self.current_file: tb_file = os.path.basename(self.current_file)
        else:
            # Current file is Design, look for TB
            tb_file = self.find_associated_testbench(module_name)

        if not tb_file:
            self.log_system("No Testbench found. Compiling design only (Syntax Check).", "WARN")
            self.run_simple_compile(target_base)
            return

        # SURGICAL VCD INJECTION
        temp_tb = "._temp_tb.v"
        try:
            with open(os.path.join(self.cwd, tb_file), 'r') as f: tb_content = f.read()
            
            # Regex to find initial begin and inject
            # Finds 'initial begin' and appends the dump lines immediately after
            # Only injects if $dumpfile isn't already there
            if "$dumpfile" not in tb_content:
                pattern = r"(initial\s+begin)"
                injection = f'\\1\n        $dumpfile("{target_base}.vcd"); $dumpvars(0);'
                new_content = re.sub(pattern, injection, tb_content, count=1, flags=re.IGNORECASE)
            else:
                new_content = tb_content # User manually added it, respect that
            
            with open(os.path.join(self.cwd, temp_tb), 'w') as f: f.write(new_content)
            
            # COMPILE (All .v files except the original TB to avoid collision)
            all_v = glob.glob(os.path.join(self.cwd, "*.v"))
            # Exclude original TB, Include Temp TB
            compile_list = [f for f in all_v if os.path.basename(f) != tb_file] + [temp_tb]
            
            outfile = f"{target_base}.out"
            cmd = ["iverilog", "-o", outfile] + compile_list
            
            self.log_system("Compiling with Auto-VCD...", "SYS")
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=self.cwd)
            
            # Clean temp immediately
            if os.path.exists(os.path.join(self.cwd, temp_tb)): os.remove(os.path.join(self.cwd, temp_tb))
            
            if res.returncode != 0:
                self.log_system(f"COMPILE ERROR:\n{res.stderr}", "ERROR")
                return

            self.log_system("Running Simulation...", "SUCCESS")
            self.run_process_threaded(["vvp", outfile])
            
        except Exception as e:
            self.log_system(f"Build Error: {e}", "ERROR")
            if os.path.exists(os.path.join(self.cwd, temp_tb)): os.remove(os.path.join(self.cwd, temp_tb))

    def run_simple_compile(self, target_base):
        all_v = glob.glob(os.path.join(self.cwd, "*.v"))
        outfile = f"{target_base}.out"
        res = subprocess.run(["iverilog", "-o", outfile] + all_v, capture_output=True, text=True, cwd=self.cwd)
        if res.returncode != 0: self.log_system(f"SYNTAX ERROR:\n{res.stderr}", "ERROR")
        else: self.log_system("Syntax OK (No TB found to run).", "SUCCESS")

    # ================= SCHEMATICS (CONTEXT AWARE) =================
    
    def generate_schematic(self):
        if self.current_file: self.save_file()
        module_name, target_base = self.get_context_target()
        if not target_base: self.log_system("No module found.", "ERROR"); return

        # Filter out TBs for schematic generation
        all_v = glob.glob(os.path.join(self.cwd, "*.v"))
        synth_files = [f for f in all_v if not ("tb_" in f or "_tb" in f or "test_" in f)]
        
        self.log_system(f"Generating Schematic for {target_base}...", "SYS")
        
        # TARGETED NAMING
        prefix = target_base # e.g. "alu" -> alu.dot, alu.png
        
        use_netlist = (self.schem_engine == "NetlistSVG") or (self.schem_engine == "Auto" and shutil.which("netlistsvg"))

        if use_netlist:
            cmd = f"yosys -p 'read_verilog {' '.join(synth_files)}; hierarchy -check -top {module_name}; proc; opt; autoname; write_json {prefix}.json' -q"
            subprocess.run(cmd, shell=True, cwd=self.cwd, capture_output=True)
            if os.path.exists(os.path.join(self.cwd, f"{prefix}.json")):
                subprocess.run(f"netlistsvg {prefix}.json -o {prefix}.svg", shell=True, cwd=self.cwd, capture_output=True)
                if os.path.exists(os.path.join(self.cwd, f"{prefix}.svg")):
                    self.inject_svg_css(os.path.join(self.cwd, f"{prefix}.svg"))
                    subprocess.run(f"rsvg-convert {prefix}.svg -o {prefix}.png", shell=True, cwd=self.cwd, capture_output=True)
                    self.schematic_viewer.load_image(os.path.join(self.cwd, f"{prefix}.png"))
        else:
            cmd = f"yosys -p 'read_verilog {' '.join(synth_files)}; hierarchy -check -top {module_name}; proc; opt; autoname; show -format dot -prefix {prefix}' -q"
            subprocess.run(cmd, shell=True, cwd=self.cwd, capture_output=True)
            if os.path.exists(os.path.join(self.cwd, f"{prefix}.dot")):
                self.patch_graphviz_style(os.path.join(self.cwd, f"{prefix}.dot"))
                subprocess.run(f"dot -Tpng {prefix}.dot -o {prefix}.png", shell=True, cwd=self.cwd, capture_output=True)
                self.schematic_viewer.load_image(os.path.join(self.cwd, f"{prefix}.png"))

    # ================= LOGIC & INTERCEPT (BEACON FIX) =================
    
    def activate_sk_mode(self, event):
        self.sk_active = True
        # VISUAL BEACON: Flash Toolbar CYAN
        self.toolbar.config(bg="#00FFFF") 
        self.root.after(self.sk_timeout, self.reset_sk)
        return "break"

    def reset_sk(self):
        self.sk_active = False
        self.toolbar.config(bg="#e1e1e1") # Reset Color

    def handle_widget_key_intercept(self, event):
        if not self.sk_active: return None
        key = event.keysym.lower()
        if key == self.key_map["focus_editor"]: self.editor.focus_set(); self.log_system("Focus: Editor", "SYS")
        elif key == self.key_map["focus_terminal"]: self.term_input.focus_set(); self.log_system("Focus: Terminal", "SYS")
        elif key == self.key_map["focus_files"]: self.tree.focus_set(); self.log_system("Focus: Files", "SYS")
        elif key == self.key_map["focus_schem"]: self.schematic_viewer.focus_set(); self.log_system("Focus: Schematic", "SYS")
        elif key == self.key_map["term_toggle"]: self.toggle_term_mode(); self.log_system("Mode Toggled", "SYS")
        self.reset_sk(); return "break"

    # ================= UTILS =================

    def on_tree_double_click(self, event):
        item_id = self.tree.selection()[0]; path, ftype = self.tree.item(item_id, "values")
        if ftype == "dir": self.change_directory_silent(path)
        else: 
            # GTKWAVE LAUNCHER
            if path.endswith(".vcd"):
                subprocess.Popen(["gtkwave", path], cwd=self.cwd)
                self.log_system(f"Opening Waves: {os.path.basename(path)}", "SYS")
            else:
                parent_dir = os.path.dirname(path); self.change_directory_silent(parent_dir); self.open_file_in_editor(path)

    def open_waves(self):
        # Open the specific VCD for the current module if it exists
        _, target_base = self.get_context_target()
        if target_base:
            vcd = os.path.join(self.cwd, f"{target_base}.vcd")
            if os.path.exists(vcd):
                subprocess.Popen(["gtkwave", vcd], cwd=self.cwd)
                return
        
        # Fallback
        vcds = glob.glob(os.path.join(self.cwd, "*.vcd"))
        if vcds: subprocess.Popen(["gtkwave", max(vcds, key=os.path.getctime)], cwd=self.cwd)
        else: self.log_system("No .vcd files found.", "WARN")

    # [Standard Methods: create_toolbar, run_process_threaded, process_queue, clean_products, etc.]
    # (Included in full structure, condensed here for length but fully functional in logic)
    def create_toolbar(self):
        self.toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED, bg="#e1e1e1"); self.toolbar.pack(side=tk.TOP, fill=tk.X)
        tk.Button(self.toolbar, text="New", command=self.new_file).pack(side=tk.LEFT, padx=2)
        tk.Button(self.toolbar, text="Save", command=self.save_file).pack(side=tk.LEFT, padx=2)
        tk.Frame(self.toolbar, width=20, bg="#e1e1e1").pack(side=tk.LEFT)
        tk.Button(self.toolbar, text="F1 Compile", bg="#d4edda", command=self.run_simulation).pack(side=tk.LEFT, padx=2)
        tk.Button(self.toolbar, text="F2 Waves", bg="#cff4fc", command=self.open_waves).pack(side=tk.LEFT, padx=2)
        tk.Button(self.toolbar, text="F3 Schem", bg="#fff3cd", command=self.generate_schematic).pack(side=tk.LEFT, padx=2)
        tk.Button(self.toolbar, text="Clean", bg="#f8d7da", command=self.clean_products).pack(side=tk.RIGHT, padx=5)
        tk.Button(self.toolbar, text="⚙ Settings", command=self.open_settings).pack(side=tk.RIGHT, padx=5)

    def run_process_threaded(self, command):
        def target():
            try:
                self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=self.cwd)
                for line in iter(self.process.stdout.readline, ''): self.queue.put(line)
                self.process.stdout.close(); self.process.wait(); self.process = None; self.queue.put("\n[Finished]\n")
            except Exception as e: self.queue.put(f"\n[Error]: {e}\n")
        threading.Thread(target=target, daemon=True).start()

    def process_queue(self):
        while not self.queue.empty():
            msg = self.queue.get()
            tag = "SUCCESS" 
            if "error" in msg.lower() or "syntax" in msg.lower(): tag = "ERROR"
            elif "warning" in msg.lower(): tag = "WARN"
            elif "[sys]" in msg.lower(): tag = "SYS"
            self.term_log.insert(tk.END, msg, tag); self.term_log.see(tk.END)
        self.root.after(100, self.process_queue)

    def clean_products(self):
        exts = ["*.out", "*.vvp", "*.vcd", "*.dot", "*.png", "*.svg", "*.history", "*.json"]
        count = 0
        for ext in exts:
            for f in glob.glob(os.path.join(self.cwd, ext)):
                with suppress(OSError): os.remove(f); count += 1
        self.log_system(f"Cleaned {count} artifacts.", "SUCCESS"); self.refresh_file_tree()

    # [Re-include patch_graphviz_style and inject_svg_css from v20 unchanged]
    def patch_graphviz_style(self, dot_path):
        with open(dot_path, 'r') as f: content = f.read()
        if self.schem_theme == "Dark":
            content = re.sub(r'(graph\s*\[)', r'\1 bgcolor="#1e1e1e", fontcolor="white",', content)
            content = re.sub(r'(node\s*\[)', r'\1 color="#00FFFF", fontcolor="white",', content)
            content = re.sub(r'(edge\s*\[)', r'\1 color="white",', content)
        elif self.schem_theme == "Blueprint":
            content = re.sub(r'(graph\s*\[)', r'\1 bgcolor="#003366", fontcolor="white",', content)
            content = re.sub(r'(node\s*\[)', r'\1 color="white", fontcolor="white",', content)
            content = re.sub(r'(edge\s*\[)', r'\1 color="white",', content)
        if "Standard" not in self.schem_theme:
             content = re.sub(r'label="\$_(AND|NAND)_', r'shape=box, style=filled, fillcolor="#007ACC", label="$_\1_', content)
             content = re.sub(r'label="\$_(OR|NOR)_', r'shape=box, style=filled, fillcolor="#D65D0E", label="$_\1_', content)
             content = re.sub(r'label="\$_(NOT|BUF)_', r'shape=triangle, style=filled, fillcolor="#98971a", label="$_\1_', content)
        with open(dot_path, 'w') as f: f.write(content)

    def inject_svg_css(self, svg_path):
        if self.schem_theme == "Standard": return
        bg_color = "#1e1e1e" if self.schem_theme == "Dark" else "#003366"
        line_color = "white"
        with open(svg_path, 'r') as f: svg = f.read()
        if '<style>' not in svg: svg = svg.replace('<svg ', f'<svg style="background-color: {bg_color};" ')
        else: svg = svg.replace('<svg ', f'<svg style="background-color: {bg_color};" ')
        style_block = f"""<style> svg {{ background-color: {bg_color}; }} text {{ fill: {line_color}; font-family: Consolas, sans-serif; }} .edge path {{ stroke: {line_color}; }} .node rect, .node circle, .node path {{ stroke: {line_color}; fill: none; }} .pin {{ stroke: {line_color}; }} </style>"""
        svg = svg.replace('>', f'>{style_block}', 1)
        with open(svg_path, 'w') as f: f.write(svg)
    
    # [Standard: change_directory_silent, open_file_in_editor, new_file, save_file, toggle_term_mode, handle_terminal_input, run_shell_command, send_sim_input, log_system, print_grid, handle_tab_autocomplete, open_settings, check_dependencies, update_ui_labels]
    # (Implicitly present as they were in v21)
    def change_directory_silent(self, new_dir):
        try: os.chdir(new_dir); self.cwd = os.getcwd()
        except Exception as e: self.log_system(f"Error: {e}", "ERROR")

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

    def on_tree_up_dir(self, event):
        try: os.chdir(".."); self.cwd = os.getcwd(); self.refresh_file_tree(); self.log_system(f"CD .. -> {self.cwd}", "SYS")
        except Exception as e: self.log_system(f"Error: {e}", "ERROR")

    def open_file_in_editor(self, path):
        try:
            with open(path, "r") as f: content = f.read()
            self.editor.delete(1.0, tk.END); self.editor.insert(tk.END, content)
            self.current_file = path; self.root.title(f"Silis - {os.path.basename(path)}")
        except: pass

    def new_file(self): self.current_file = None; self.editor.delete(1.0, tk.END)
    def save_file(self):
        if not self.current_file:
            f = filedialog.asksaveasfilename(initialdir=self.cwd); 
            if not f: return
            self.current_file = f
        with open(self.current_file, "w") as f: f.write(self.editor.get(1.0, tk.END))
        self.refresh_file_tree()

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
            try: os.chdir(target); self.cwd = os.getcwd(); self.refresh_file_tree()
            except Exception as e: self.log_system(f"Error: {e}", "ERROR")
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
        tk.Label(win, text="Terminal Colors", font=("Arial", 10, "bold")).pack(pady=5)
        color_entries = {}
        for tag, color in self.term_colors.items():
            f = tk.Frame(win); f.pack(fill=tk.X, padx=10)
            tk.Label(f, text=tag, width=15, anchor="w", fg=color).pack(side=tk.LEFT)
            e = tk.Entry(f, width=10); e.insert(0, color); e.pack(side=tk.RIGHT); color_entries[tag] = e
        tk.Label(win, text="Schematic Engine", font=("Arial", 10, "bold")).pack(pady=5)
        eng_var = tk.StringVar(value=self.schem_engine)
        eng_menu = ttk.OptionMenu(win, eng_var, self.schem_engine, "Auto", "Graphviz", "NetlistSVG")
        eng_menu.pack()
        tk.Label(win, text="Schematic Theme", font=("Arial", 10, "bold")).pack(pady=5)
        theme_var = tk.StringVar(value=self.schem_theme)
        theme_menu = ttk.OptionMenu(win, theme_var, self.schem_theme, "Standard", "Dark", "Blueprint")
        theme_menu.pack()
        def save():
            for action, e in entries.items(): self.key_map[action] = e.get()
            for tag, e in color_entries.items(): self.term_colors[tag] = e.get()
            self.schem_engine = eng_var.get()
            self.schem_theme = theme_var.get()
            self.update_ui_labels(); self.update_term_colors()
            self.log_system("Settings Saved.", "SUCCESS")
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
            
    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.tree_menu.post(event.x_root, event.y_root)

if __name__ == "__main__":
    root = tk.Tk()
    app = SilisIDE(root)
    root.mainloop()
