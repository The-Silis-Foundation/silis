import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import subprocess
import os
import threading
import queue
import glob
from PIL import Image, ImageTk  # Requires: sudo dnf install python3-pillow-tk

class ZoomableSchematic(tk.Frame):
    """ A custom widget that allows panning and zooming of the schematic image """
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        self.v_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.h_scroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL)
        
        # Canvas
        self.canvas = tk.Canvas(self, bg="#f0f0f0", 
                                yscrollcommand=self.v_scroll.set, 
                                xscrollcommand=self.h_scroll.set)
        
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # State
        self.image_path = None
        self.original_image = None
        self.tk_image = None
        self.img_id = None
        self.zoom_level = 1.0

        # Bindings for Pan/Zoom
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<MouseWheel>", self.on_zoom)  # Windows/MacOS
        self.canvas.bind("<Button-4>", self.on_zoom)    # Linux Scroll Up
        self.canvas.bind("<Button-5>", self.on_zoom)    # Linux Scroll Down

    def load_image(self, path):
        self.image_path = path
        try:
            self.original_image = Image.open(path)
            self.zoom_level = 1.0
            self.show_image()
        except Exception as e:
            print(f"Image Load Error: {e}")

    def show_image(self):
        if not self.original_image: return
        
        # Calculate new size
        w, h = self.original_image.size
        new_w = int(w * self.zoom_level)
        new_h = int(h * self.zoom_level)
        
        # Resize safely
        resized = self.original_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)
        
        # Clear and redraw
        self.canvas.delete("all")
        # Draw image at center of canvas coordinate system
        self.img_id = self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def on_button_press(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def on_move_press(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_zoom(self, event):
        if event.num == 4 or event.delta > 0:
            self.zoom_level *= 1.1
        elif event.num == 5 or event.delta < 0:
            self.zoom_level /= 1.1
        self.show_image()


class VerilogIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("WSL Verilog Workbench v3.1")
        self.root.geometry("1400x900")
        
        # --- FIX: FORCE CURSOR VISIBILITY ---
        # This forces the X Server to use the standard arrow, preventing the "invisible cursor" bug
        self.root.config(cursor="arrow")
        # ------------------------------------
        
        # Threading Queue
        self.queue = queue.Queue()
        self.process = None
        
        # ================= STYLES =================
        style = ttk.Style()
        style.theme_use('clam')
        
        # ================= TOP TOOLBAR =================
        toolbar = tk.Frame(root, bd=1, relief=tk.RAISED, bg="#e1e1e1")
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # File Group
        tk.Label(toolbar, text=" FILE: ", bg="#e1e1e1", fg="#555").pack(side=tk.LEFT)
        tk.Button(toolbar, text="New", command=self.new_file).pack(side=tk.LEFT, padx=1)
        tk.Button(toolbar, text="Save", command=self.save_file).pack(side=tk.LEFT, padx=1)
        
        tk.Frame(toolbar, width=20, bg="#e1e1e1").pack(side=tk.LEFT) # Spacer
        
        # Tool Group
        tk.Label(toolbar, text=" TOOLS: ", bg="#e1e1e1", fg="#555").pack(side=tk.LEFT)
        tk.Button(toolbar, text="Run (Iverilog)", bg="#d4edda", command=self.run_simulation).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Waves (GTK)", bg="#cff4fc", command=self.open_waves).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Schematic (Yosys)", bg="#fff3cd", command=self.generate_schematic).pack(side=tk.LEFT, padx=2)
        
        # Clean Group
        tk.Button(toolbar, text="🧹 Clean", bg="#f8d7da", command=self.clean_products).pack(side=tk.RIGHT, padx=10)
        tk.Button(toolbar, text="Refresh", command=self.populate_file_list).pack(side=tk.RIGHT, padx=2)

        # ================= LAYOUT MANAGER =================
        # Master Split: Top (Work Area) vs Bottom (Terminal)
        self.main_split = ttk.PanedWindow(root, orient=tk.VERTICAL)
        self.main_split.pack(fill=tk.BOTH, expand=True)
        
        # Middle Split: Files | Code | Schematic
        self.middle_pane = ttk.PanedWindow(self.main_split, orient=tk.HORIZONTAL)
        self.main_split.add(self.middle_pane, weight=4) # Top part gets 4x space
        
        # 1. LEFT PANE: FILES
        file_frame = tk.LabelFrame(self.middle_pane, text="Project Files")
        self.middle_pane.add(file_frame, weight=1)
        self.tree = ttk.Treeview(file_frame, show='tree')
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_file_double_click)
        
        # 2. CENTER PANE: EDITOR
        editor_frame = tk.LabelFrame(self.middle_pane, text="Verilog Editor")
        self.middle_pane.add(editor_frame, weight=5) # Editor gets most space
        self.editor = scrolledtext.ScrolledText(editor_frame, undo=True, font=("Consolas", 12))
        self.editor.pack(fill=tk.BOTH, expand=True)
        
        # 3. RIGHT PANE: SCHEMATIC
        schem_frame = tk.LabelFrame(self.middle_pane, text="Schematic (Drag to Pan, Scroll to Zoom)")
        self.middle_pane.add(schem_frame, weight=2)
        self.schematic_viewer = ZoomableSchematic(schem_frame)

        # ================= BOTTOM: INTERACTIVE TERMINAL =================
        term_container = tk.LabelFrame(self.main_split, text="Terminal")
        self.main_split.add(term_container, weight=1)
        
        # Output Log (Read Only-ish)
        self.term_log = scrolledtext.ScrolledText(term_container, bg="#1e1e1e", fg="#00ff00", 
                                                  font=("Consolas", 10), height=8)
        self.term_log.pack(fill=tk.BOTH, expand=True)
        
        # Input Bar
        input_frame = tk.Frame(term_container, bg="#333")
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(input_frame, text=" INPUT > ", bg="#333", fg="white").pack(side=tk.LEFT)
        
        self.term_input = tk.Entry(input_frame, bg="#333", fg="white", font=("Consolas", 10), insertbackground="white")
        self.term_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.term_input.bind("<Return>", self.send_input)

        # ================= INIT =================
        self.current_file = None
        self.populate_file_list()
        self.log_system("Workbench v3.1 Initialized.")
        self.root.after(100, self.process_queue)

    # ================= LOGIC: FILE SYSTEM =================
    def populate_file_list(self):
        self.tree.delete(*self.tree.get_children())
        for f in glob.glob("*.v"):
            self.tree.insert("", tk.END, text=f, values=(f,))

    def new_file(self):
        self.current_file = None
        self.editor.delete(1.0, tk.END)
        self.root.title("WSL Verilog Workbench - New File")

    def save_file(self):
        if not self.current_file:
            f = filedialog.asksaveasfilename(defaultextension=".v", filetypes=[("Verilog", "*.v")])
            if not f: return
            self.current_file = f
        with open(self.current_file, "w") as f:
            f.write(self.editor.get(1.0, tk.END))
        self.log_system(f"Saved: {self.current_file}")
        self.populate_file_list()

    def on_file_double_click(self, event):
        item = self.tree.selection()[0]
        fname = self.tree.item(item, "text")
        self.current_file = fname
        with open(fname, "r") as f:
            self.editor.delete(1.0, tk.END)
            self.editor.insert(tk.END, f.read())
        self.log_system(f"Opened: {fname}")

    def clean_products(self):
        exts = ["*.out", "*.vvp", "*.vcd", "*.dot", "*.png", "*.history"]
        count = 0
        for ext in exts:
            for f in glob.glob(ext):
                try: os.remove(f); count+=1
                except: pass
        self.log_system(f"Cleaned {count} artifacts.")

    # ================= LOGIC: TERMINAL & PROCESSES =================
    def log_system(self, msg):
        self.term_log.insert(tk.END, f"[SYS]: {msg}\n")
        self.term_log.see(tk.END)

    def process_queue(self):
        while not self.queue.empty():
            msg = self.queue.get()
            self.term_log.insert(tk.END, msg)
            self.term_log.see(tk.END)
        self.root.after(100, self.process_queue)

    def run_process_threaded(self, command):
        """ Run a command and pipe output to queue """
        def target():
            try:
                # Using Popen to keep stdin open for interaction
                self.process = subprocess.Popen(
                    command, 
                    stdin=subprocess.PIPE, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True, 
                    bufsize=1,
                    shell=False
                )
                for line in iter(self.process.stdout.readline, ''):
                    self.queue.put(line)
                self.process.stdout.close()
                self.process.wait()
                self.process = None
                self.queue.put("\n[Finished]\n")
            except Exception as e:
                self.queue.put(f"\n[Error]: {e}\n")
        
        threading.Thread(target=target, daemon=True).start()

    def send_input(self, event):
        """ Send text from Input Bar to running process """
        text = self.term_input.get()
        self.term_input.delete(0, tk.END)
        
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(text + "\n")
                self.process.stdin.flush()
                self.log_system(f"Sent Input: {text}")
            except Exception as e:
                self.log_system(f"Input Error: {e}")
        else:
            self.log_system("No active simulation to receive input.")

    # ================= LOGIC: TOOLS =================
    def run_simulation(self):
        if self.current_file: self.save_file()
        
        # Compile ALL .v files
        v_files = glob.glob("*.v")
        if not v_files:
            self.log_system("No .v files found.")
            return
        
        outfile = "design.out"
        cmd_compile = ["iverilog", "-o", outfile] + v_files
        
        res = subprocess.run(cmd_compile, capture_output=True, text=True)
        if res.returncode != 0:
            self.log_system(f"COMPILE ERROR:\n{res.stderr}")
            return
            
        self.log_system("Compile OK. Running Simulation...")
        self.run_process_threaded(["vvp", outfile])

    def open_waves(self):
        # Find latest VCD
        vcds = glob.glob("*.vcd")
        if not vcds:
            self.log_system("No .vcd found. (Did you use $dumpfile?)")
            return
        latest = max(vcds, key=os.path.getctime)
        self.log_system(f"Opening GTKWave: {latest}")
        subprocess.Popen(["gtkwave", latest], stderr=subprocess.PIPE)

    def generate_schematic(self):
        if self.current_file: self.save_file()
        self.log_system("Generating Schematic...")
        
        # 1. Yosys (Generate DOT)
        # hierarchy -auto-top finds the top module automatically
        cmd = "yosys -p 'read_verilog *.v; hierarchy -auto-top; proc; opt; show -format dot -prefix schematic' -q"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if res.returncode != 0:
            self.log_system(f"Yosys Error:\n{res.stderr}")
            return
            
        # 2. Graphviz (DOT -> PNG)
        if os.path.exists("schematic.dot"):
            subprocess.run("dot -Tpng schematic.dot -o schematic.png", shell=True)
            if os.path.exists("schematic.png"):
                self.schematic_viewer.load_image("schematic.png")
                self.log_system("Schematic loaded.")
            else:
                self.log_system("Error: 'dot' command failed. Install graphviz.")
        else:
            self.log_system("Error: Yosys failed to output .dot file.")

if __name__ == "__main__":
    root = tk.Tk()
    app = VerilogIDE(root)
    root.mainloop()
