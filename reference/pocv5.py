import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import subprocess
import os
import threading
import queue
import glob
import re
from PIL import Image, ImageTk  # sudo dnf install python3-pillow-tk

# ================= CUSTOM WIDGETS =================

class CodeEditor(tk.Frame):
    """ A Text Editor with Line Numbers, Syntax Highlighting, and Tab Fixes """
    def __init__(self, parent, font_size=12):
        super().__init__(parent)
        self.pack(fill=tk.BOTH, expand=True)
        self.font = ("Consolas", font_size)
        
        # 1. Line Number Gutter
        self.gutter = tk.Text(self, width=4, padx=4, takefocus=0, border=0,
                              background="#f0f0f0", state="disabled", font=self.font)
        self.gutter.pack(side=tk.LEFT, fill=tk.Y)
        
        # 2. Main Code Area
        self.text = tk.Text(self, font=self.font, undo=True, wrap="none")
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 3. Scrollbar
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.on_scroll)
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.configure(yscrollcommand=self.vsb.set)
        
        # Bindings
        self.text.bind("<KeyRelease>", self.on_content_changed)
        self.text.bind("<MouseWheel>", self.sync_scroll)
        self.text.bind("<Button-4>", self.sync_scroll)
        self.text.bind("<Button-5>", self.sync_scroll)
        
        # --- FIX: TAB KEY ---
        self.text.bind("<Tab>", self.insert_tab_spaces)

        # Tags for Syntax Highlighting
        self.setup_tags()

    def insert_tab_spaces(self, event):
        """ Inserts 4 spaces instead of moving focus """
        self.text.insert(tk.INSERT, "    ")
        return "break" # CRITICAL: Stops Tkinter from moving focus

    def setup_tags(self):
        # Colors
        self.text.tag_configure("KEYWORD", foreground="#0000FF", font=(self.font[0], self.font[1], "bold")) # Blue
        self.text.tag_configure("COMMENT", foreground="#008000") # Green
        self.text.tag_configure("STRING", foreground="#A31515")  # Red/Orange
        self.text.tag_configure("NUMBER", foreground="#800080")  # Purple
        self.text.tag_configure("ERROR", background="#FFCCCC")   # Light Red Background

    def on_scroll(self, *args):
        self.text.yview(*args)
        self.gutter.yview(*args)

    def sync_scroll(self, event):
        self.gutter.yview_moveto(self.text.yview()[0])

    def on_content_changed(self, event=None):
        self.update_line_numbers()
        self.highlight_syntax()

    def update_line_numbers(self):
        line_count = int(self.text.index('end-1c').split('.')[0])
        line_numbers = "\n".join(str(i) for i in range(1, line_count + 1))
        
        self.gutter.config(state="normal")
        self.gutter.delete("1.0", tk.END)
        self.gutter.insert("1.0", line_numbers)
        self.gutter.config(state="disabled")
        self.gutter.yview_moveto(self.text.yview()[0])

    def highlight_syntax(self):
        # Clear existing tags
        for tag in ["KEYWORD", "COMMENT", "STRING", "NUMBER", "ERROR"]:
            self.text.tag_remove(tag, "1.0", tk.END)

        text_content = self.text.get("1.0", tk.END)
        
        # 1. Keywords
        keywords = r"\b(module|endmodule|input|output|wire|reg|always|initial|begin|end|assign|posedge|negedge|if|else|case|endcase|default|parameter)\b"
        for match in re.finditer(keywords, text_content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.text.tag_add("KEYWORD", start, end)

        # 2. Numbers (Simple regex for hex/binary/decimal)
        numbers = r"\b\d+'[bh]\w+|\b\d+\b"
        for match in re.finditer(numbers, text_content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.text.tag_add("NUMBER", start, end)

        # 3. Strings
        strings = r"\".*?\""
        for match in re.finditer(strings, text_content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.text.tag_add("STRING", start, end)

        # 4. Comments (Last so they override keywords)
        comments = r"//.*"
        for match in re.finditer(comments, text_content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.text.tag_add("COMMENT", start, end)

    def highlight_error_line(self, line_num):
        self.text.tag_remove("ERROR", "1.0", tk.END)
        start = f"{line_num}.0"
        end = f"{line_num + 1}.0"
        self.text.tag_add("ERROR", start, end)
        self.text.see(start)

    # Proxy methods
    def get(self, *args): return self.text.get(*args)
    def delete(self, *args): 
        self.text.delete(*args)
        self.on_content_changed()
    def insert(self, *args): 
        self.text.insert(*args)
        self.on_content_changed()

class ZoomableSchematic(tk.Frame):
    """ (Unchanged) Pan/Zoom Logic """
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill=tk.BOTH, expand=True)
        self.v_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.h_scroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL)
        self.canvas = tk.Canvas(self, bg="#f0f0f0", yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.original_image = None
        self.tk_image = None
        self.zoom_level = 1.0

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)
        self.canvas.bind("<Button-5>", self.on_zoom)

    def load_image(self, path):
        try:
            self.original_image = Image.open(path)
            self.zoom_level = 1.0
            self.show_image()
        except Exception as e: print(f"Image Error: {e}")

    def show_image(self):
        if not self.original_image: return
        w, h = self.original_image.size
        new_w = int(w * self.zoom_level)
        new_h = int(h * self.zoom_level)
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


# ================= MAIN IDE =================

class VerilogIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("WSL Verilog Workbench v6.1 (Tab Fixed)")
        self.root.geometry("1400x900")
        self.root.config(cursor="arrow") 
        
        # State
        self.current_file = None
        self.cwd = os.getcwd() 
        self.process = None    
        self.queue = queue.Queue()
        self.term_mode = "SHELL" 
        
        style = ttk.Style()
        style.theme_use('clam')
        
        self.create_toolbar()
        
        # Layout
        self.main_split = ttk.PanedWindow(root, orient=tk.VERTICAL)
        self.main_split.pack(fill=tk.BOTH, expand=True)
        
        self.middle_pane = ttk.PanedWindow(self.main_split, orient=tk.HORIZONTAL)
        self.main_split.add(self.middle_pane, weight=4)
        
        # 1. File Tree
        file_frame = tk.LabelFrame(self.middle_pane, text="Project Explorer")
        self.middle_pane.add(file_frame, weight=1)
        
        self.tree_scroll = ttk.Scrollbar(file_frame)
        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = ttk.Treeview(file_frame, show='tree', yscrollcommand=self.tree_scroll.set)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree_scroll.config(command=self.tree.yview)
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_expand)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        
        # 2. PRO EDITOR (New Class)
        editor_frame = tk.LabelFrame(self.middle_pane, text="Verilog Source")
        self.middle_pane.add(editor_frame, weight=5)
        self.editor = CodeEditor(editor_frame) # Using Custom Widget
        
        # 3. Schematic
        schem_frame = tk.LabelFrame(self.middle_pane, text="Schematic")
        self.middle_pane.add(schem_frame, weight=2)
        self.schematic_viewer = ZoomableSchematic(schem_frame)
        
        # Terminal
        term_container = tk.LabelFrame(self.main_split, text="Terminal")
        self.main_split.add(term_container, weight=1)
        
        self.term_log = scrolledtext.ScrolledText(term_container, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 10), height=8)
        self.term_log.pack(fill=tk.BOTH, expand=True)
        
        input_frame = tk.Frame(term_container, bg="#333")
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.mode_btn = tk.Button(input_frame, text="[ MODE: SHELL ]", bg="#0d6efd", fg="white", 
                                  command=self.toggle_term_mode, font=("Consolas", 9, "bold"))
        self.mode_btn.pack(side=tk.LEFT, padx=2)
        
        tk.Label(input_frame, text=" > ", bg="#333", fg="white").pack(side=tk.LEFT)
        self.term_input = tk.Entry(input_frame, bg="#333", fg="white", font=("Consolas", 10), insertbackground="white")
        self.term_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.term_input.bind("<Return>", self.handle_terminal_input)
        self.term_input.bind("<Tab>", self.handle_tab_complete) 

        # Init
        self.refresh_file_tree()
        self.log_system(f"Workbench v6.1 Ready. CWD: {self.cwd}")
        self.root.after(100, self.process_queue)

    # ================= UI BUILDERS =================
    def create_toolbar(self):
        toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED, bg="#e1e1e1")
        toolbar.pack(side=tk.TOP, fill=tk.X)
        tk.Button(toolbar, text="New", command=self.new_file).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Save", command=self.save_file).pack(side=tk.LEFT, padx=2)
        tk.Frame(toolbar, width=20, bg="#e1e1e1").pack(side=tk.LEFT)
        tk.Button(toolbar, text="Compile & Run", bg="#d4edda", command=self.run_simulation).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Waves", bg="#cff4fc", command=self.open_waves).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Schematic", bg="#fff3cd", command=self.generate_schematic).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Clean", bg="#f8d7da", command=self.clean_products).pack(side=tk.RIGHT, padx=5)

    # ================= FILE LOGIC =================
    def change_directory_silent(self, new_dir):
        try:
            os.chdir(new_dir)
            self.cwd = os.getcwd()
            self.log_system(f"CD -> {self.cwd}")
        except Exception as e: self.log_system(f"Error: {e}")

    def refresh_file_tree(self):
        self.tree.delete(*self.tree.get_children())
        root_node = self.tree.insert("", tk.END, text=os.path.basename(self.cwd) or self.cwd, open=True, values=(self.cwd, "dir"))
        self.populate_node(root_node, self.cwd)

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

    def on_tree_expand(self, event):
        item_id = self.tree.focus()
        if not item_id: return
        path, ftype = self.tree.item(item_id, "values")
        if ftype != "dir": return
        self.change_directory_silent(path)
        children = self.tree.get_children(item_id)
        if len(children) == 1 and self.tree.item(children[0], "text") == "dummy":
            self.populate_node(item_id, path)

    def on_tree_double_click(self, event):
        item_id = self.tree.selection()[0]
        path, ftype = self.tree.item(item_id, "values")
        if ftype == "dir": self.change_directory_silent(path)
        else:
            parent_dir = os.path.dirname(path)
            if parent_dir != self.cwd: self.change_directory_silent(parent_dir)
            self.open_file_in_editor(path)

    def open_file_in_editor(self, path):
        try:
            with open(path, "r") as f: content = f.read()
            self.editor.delete(1.0, tk.END)
            self.editor.insert(tk.END, content)
            self.current_file = path
            self.log_system(f"Loaded: {os.path.basename(path)}")
            self.root.title(f"WSL Workbench - {os.path.basename(path)}")
        except: pass

    def new_file(self):
        self.current_file = None
        self.editor.delete(1.0, tk.END)
        self.log_system("New File created.")

    def save_file(self):
        if not self.current_file:
            f = filedialog.asksaveasfilename(initialdir=self.cwd)
            if not f: return
            self.current_file = f
        with open(self.current_file, "w") as f: f.write(self.editor.get(1.0, tk.END))
        self.log_system(f"Saved: {self.current_file}")
        self.refresh_file_tree()

    # ================= TERMINAL =================
    def toggle_term_mode(self):
        if self.term_mode == "SHELL":
            self.term_mode = "SIM"
            self.mode_btn.config(text="[ MODE: SIMULATION ]", bg="#198754") 
        else:
            self.term_mode = "SHELL"
            self.mode_btn.config(text="[ MODE: SHELL ]", bg="#0d6efd")
        self.log_system(f"Switched to {self.term_mode} Mode.")

    def handle_terminal_input(self, event):
        cmd = self.term_input.get()
        self.term_input.delete(0, tk.END)
        if self.term_mode == "SHELL": self.run_shell_command(cmd)
        else: self.send_sim_input(cmd)

    def handle_tab_complete(self, event):
        if self.term_mode != "SHELL": return "break"
        current_text = self.term_input.get()
        if " " in current_text: base, prefix = current_text.rsplit(" ", 1); base += " "
        else: base, prefix = "", current_text
        try: matches = [f for f in os.listdir(self.cwd) if f.startswith(prefix)]
        except: return "break"
        if len(matches) == 1:
            completion = matches[0]
            if os.path.isdir(os.path.join(self.cwd, completion)): completion += "/"
            self.term_input.delete(0, tk.END)
            self.term_input.insert(0, base + completion)
        elif len(matches) > 1: self.log_system(f"Ambiguous: {', '.join(matches)}")
        
        return "break" # CRITICAL: Prevents focus change

    def run_shell_command(self, cmd):
        self.term_log.insert(tk.END, f"$ {cmd}\n")
        if cmd.startswith("cd "):
            target = cmd[3:].strip()
            try:
                os.chdir(target)
                self.cwd = os.getcwd()
                self.log_system(f"Changed directory to: {self.cwd}")
                self.refresh_file_tree()
            except Exception as e: self.log_system(f"Error: {e}")
            return
        
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=self.cwd)
            if res.stdout: self.term_log.insert(tk.END, res.stdout)
            if res.stderr: self.term_log.insert(tk.END, res.stderr)
        except Exception as e: self.log_system(f"Exec Error: {e}")
        self.term_log.see(tk.END)

    def send_sim_input(self, text):
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(text + "\n")
                self.process.stdin.flush()
                self.term_log.insert(tk.END, f"[INPUT]: {text}\n")
            except Exception as e: self.log_system(f"Input Error: {e}")
        else: self.log_system("Error: No simulation running.")

    # ================= TOOLS & ERROR JUMPING =================
    def run_simulation(self):
        if self.current_file: self.save_file()
        self.term_mode = "SIM"
        self.mode_btn.config(text="[ MODE: SIMULATION ]", bg="#198754")
        
        v_files = glob.glob(os.path.join(self.cwd, "*.v"))
        if not v_files: return
        outfile = os.path.join(self.cwd, "design.out")
        
        self.log_system("Compiling...")
        res = subprocess.run(["iverilog", "-o", outfile] + v_files, capture_output=True, text=True, cwd=self.cwd)
        
        if res.returncode != 0:
            self.log_system(f"COMPILE ERROR:\n{res.stderr}")
            # SMART JUMP: Parse error for line number
            self.parse_and_highlight_error(res.stderr)
            return
            
        self.log_system("Running Simulation...")
        self.run_process_threaded(["vvp", outfile])

    def parse_and_highlight_error(self, error_log):
        # Look for "filename.v:12: syntax error"
        match = re.search(r":(\d+):", error_log)
        if match:
            line_num = int(match.group(1))
            self.log_system(f"Jumping to error on Line {line_num}...")
            self.editor.highlight_error_line(line_num)

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
            self.term_log.insert(tk.END, msg)
            self.term_log.see(tk.END)
        self.root.after(100, self.process_queue)

    def log_system(self, msg):
        self.term_log.insert(tk.END, f"[SYS]: {msg}\n")
        self.term_log.see(tk.END)

    def clean_products(self):
        exts = ["*.out", "*.vvp", "*.vcd", "*.dot", "*.png", "*.history"]
        count = 0
        for ext in exts:
            for f in glob.glob(os.path.join(self.cwd, ext)):
                try: os.remove(f); count+=1
                except: pass
        self.log_system(f"Cleaned {count} artifacts.")
        self.refresh_file_tree()

    def generate_schematic(self):
        if self.current_file: self.save_file()
        self.log_system("Generating Schematic...")
        all_v = glob.glob(os.path.join(self.cwd, "*.v"))
        synth_files = [f for f in all_v if not (os.path.basename(f).startswith("tb_") or os.path.basename(f).startswith("test_"))]
        if not synth_files: self.log_system("No design files (Skipped tb_*)"); return

        cmd = f"yosys -p 'read_verilog {' '.join(synth_files)}; hierarchy -auto-top; proc; opt; show -format dot -prefix schematic' -q"
        subprocess.run(cmd, shell=True, cwd=self.cwd)
        
        if os.path.exists(os.path.join(self.cwd, "schematic.dot")):
            subprocess.run("dot -Tpng schematic.dot -o schematic.png", shell=True, cwd=self.cwd)
            self.schematic_viewer.load_image(os.path.join(self.cwd, "schematic.png"))
            self.log_system("Schematic Loaded.")
        else: self.log_system("Error: Yosys failed.")

    def open_waves(self):
        vcds = glob.glob(os.path.join(self.cwd, "*.vcd"))
        if vcds:
            latest = max(vcds, key=os.path.getctime)
            subprocess.Popen(["gtkwave", latest], cwd=self.cwd)
        else: self.log_system("No .vcd files found.")

if __name__ == "__main__":
    root = tk.Tk()
    app = VerilogIDE(root)
    root.mainloop()
