import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import subprocess
import os
import threading
import queue
import glob

class VerilogIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("WSL Verilog Workbench v2")
        self.root.geometry("1400x900")
        
        # State
        self.current_file = None
        self.process = None  # Holds the running subprocess
        self.queue = queue.Queue()
        
        # --- TOP TOOLBAR ---
        self.create_toolbar()
        
        # --- MAIN LAYOUT (Vertical Split: Top Middle / Bottom Terminal) ---
        self.main_split = ttk.PanedWindow(root, orient=tk.VERTICAL)
        self.main_split.pack(fill=tk.BOTH, expand=True)
        
        # --- MIDDLE SECTION (Horizontal Split: Files | Editor | Schematic) ---
        self.middle_pane = ttk.PanedWindow(self.main_split, orient=tk.HORIZONTAL)
        self.main_split.add(self.middle_pane, weight=3)
        
        # 1. Left: Files
        self.create_file_explorer()
        
        # 2. Center: Code Editor
        self.create_editor()
        
        # 3. Right: Schematic / Info
        self.create_schematic_viewer()
        
        # --- BOTTOM SECTION: TERMINAL ---
        self.create_terminal()
        self.main_split.add(self.term_frame, weight=1)

        # Initial Setup
        self.populate_file_list()
        self.log_system("Workbench Ready. Fedora WSL detected.")
        self.check_update_terminal()

    # ================= LAYOUT BUILDERS =================
    
    def create_toolbar(self):
        bar = tk.Frame(self.root, bd=1, relief=tk.RAISED, bg="#e0e0e0")
        bar.pack(side=tk.TOP, fill=tk.X)
        
        # File Ops
        tk.Button(bar, text="New", command=self.new_file).pack(side=tk.LEFT, padx=2)
        tk.Button(bar, text="Save", command=self.save_file).pack(side=tk.LEFT, padx=2)
        
        tk.Frame(bar, width=30, bg="#e0e0e0").pack(side=tk.LEFT) # Spacer
        
        # Tools
        tk.Button(bar, text="Compile & Run", bg="#d4edda", command=self.run_simulation).pack(side=tk.LEFT, padx=5)
        tk.Button(bar, text="Show Waves (GTK)", bg="#cff4fc", command=self.open_waves).pack(side=tk.LEFT, padx=5)
        tk.Button(bar, text="Gen Schematic", bg="#fff3cd", command=self.generate_schematic).pack(side=tk.LEFT, padx=5)
        
        # Utilities
        tk.Button(bar, text="🧹 Clean Artifacts", bg="#f8d7da", command=self.clean_products).pack(side=tk.RIGHT, padx=10)
        tk.Button(bar, text="Refresh Files", command=self.populate_file_list).pack(side=tk.RIGHT, padx=2)

    def create_file_explorer(self):
        frame = tk.LabelFrame(self.middle_pane, text="Files")
        self.middle_pane.add(frame, weight=1)
        
        self.tree = ttk.Treeview(frame, show='tree')
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_file_double_click)

    def create_editor(self):
        frame = tk.LabelFrame(self.middle_pane, text="Verilog Editor")
        self.middle_pane.add(frame, weight=4) # Priority width
        
        self.editor = scrolledtext.ScrolledText(frame, undo=True, font=("Consolas", 12))
        self.editor.pack(fill=tk.BOTH, expand=True)

    def create_schematic_viewer(self):
        frame = tk.LabelFrame(self.middle_pane, text="Schematic View")
        self.middle_pane.add(frame, weight=2)
        
        self.schematic_canvas = tk.Canvas(frame, bg="white")
        self.schematic_canvas.pack(fill=tk.BOTH, expand=True)
        # Label to hold image
        self.img_label = tk.Label(self.schematic_canvas, text="No Schematic Generated", bg="white")
        self.img_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def create_terminal(self):
        self.term_frame = tk.LabelFrame(self.main_split, text="Terminal (Read/Write)")
        
        # The text area
        self.term = scrolledtext.ScrolledText(self.term_frame, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 11), insertbackground="white")
        self.term.pack(fill=tk.BOTH, expand=True)
        
        # Bind Enter key to send input
        self.term.bind("<Return>", self.send_input_to_terminal)

    # ================= CORE LOGIC =================

    def log_system(self, msg):
        self.term.insert(tk.END, f"\n[SYSTEM]: {msg}\n")
        self.term.see(tk.END)

    def check_update_terminal(self):
        """ Checks the queue for output from background threads """
        try:
            while True:
                msg = self.queue.get_nowait()
                self.term.insert(tk.END, msg)
                self.term.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.check_update_terminal)

    def threaded_command(self, cmd_list):
        """ Runs a command in a thread so GUI doesn't freeze """
        def run():
            try:
                # Merge stderr into stdout
                process = subprocess.Popen(
                    cmd_list, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True, 
                    bufsize=1
                )
                self.process = process
                
                for line in iter(process.stdout.readline, ''):
                    self.queue.put(line)
                
                process.stdout.close()
                process.wait()
                self.process = None
                self.queue.put(f"\n[Process finished with exit code {process.returncode}]\n")
            except Exception as e:
                self.queue.put(f"\n[Error launching command]: {e}\n")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def send_input_to_terminal(self, event):
        """ Allows user to type in terminal and send to running process """
        # Only works if we are capturing a running process like 'vvp'
        # Currently, this is a basic implementation. 
        # Making a full interactive shell in Tkinter is complex, 
        # so this mainly logs what you type for now.
        pass 

    # ================= FILE OPERATIONS =================

    def populate_file_list(self):
        self.tree.delete(*self.tree.get_children())
        for file in os.listdir("."):
            if file.endswith(".v"):
                self.tree.insert("", tk.END, text=file, values=(file,))

    def new_file(self):
        self.current_file = None
        self.editor.delete(1.0, tk.END)
        self.root.title("WSL Verilog Workbench - New File")

    def save_file(self):
        if not self.current_file:
            filename = filedialog.asksaveasfilename(defaultextension=".v", filetypes=[("Verilog", "*.v")])
            if not filename: return
            self.current_file = filename
        
        with open(self.current_file, "w") as f:
            f.write(self.editor.get(1.0, tk.END))
        
        self.root.title(f"WSL Verilog Workbench - {os.path.basename(self.current_file)}")
        self.log_system(f"Saved {self.current_file}")
        self.populate_file_list()

    def on_file_double_click(self, event):
        item = self.tree.selection()[0]
        filename = self.tree.item(item, "text")
        self.current_file = filename
        with open(filename, "r") as f:
            self.editor.delete(1.0, tk.END)
            self.editor.insert(tk.END, f.read())
        self.log_system(f"Loaded {filename}")

    def clean_products(self):
        """ Deletes generated files to clean workspace """
        patterns = ["*.out", "*.vvp", "*.vcd", "*.dot", "*.png", "*.history"]
        count = 0
        for p in patterns:
            for f in glob.glob(p):
                try:
                    os.remove(f)
                    count += 1
                except: pass
        self.log_system(f"Cleaned {count} artifacts.")

    # ================= TOOL CHAINS =================

    def run_simulation(self):
        if not self.current_file: return
        self.save_file()
        
        outfile = "design.out"
        # 1. Compile
        cmd_compile = ["iverilog", "-o", outfile, self.current_file]
        self.log_system("Compiling...")
        
        # We run compile blocking because it's fast
        res = subprocess.run(cmd_compile, capture_output=True, text=True)
        if res.returncode != 0:
            self.log_system(f"COMPILE ERROR:\n{res.stderr}")
            return
        
        self.log_system("Compilation Successful. Running Simulation...")
        # 2. Run Simulation (Threaded)
        self.threaded_command(["vvp", outfile])

    def open_waves(self):
        # Finds the most recent .vcd file
        list_of_files = glob.glob('*.vcd')
        if not list_of_files:
            self.log_system("No .vcd file found. Did your simulation run '$dumpfile'?")
            return
        latest_file = max(list_of_files, key=os.path.getctime)
        
        self.log_system(f"Launching GTKWave for {latest_file}...")
        
        # Launch independently so it doesn't block
        try:
            subprocess.Popen(["gtkwave", latest_file])
        except FileNotFoundError:
            self.log_system("Error: 'gtkwave' not found in PATH.")

    def generate_schematic(self):
        if not self.current_file: return
        self.save_file()
        
        self.log_system("Generating Schematic (Yosys -> Graphviz)...")
        
        # 1. Yosys to Dot
        # Note: We use 'prefix' for split outputs, but 'show' usually dumps to show.dot
        cmd_yosys = f"yosys -p 'read_verilog {self.current_file}; proc; opt; show -format dot -prefix schematic' -q"
        
        res = subprocess.run(cmd_yosys, shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            self.log_system(f"Yosys Error:\n{res.stderr}")
            return
            
        # 2. Dot to PNG
        if os.path.exists("schematic.dot"):
            cmd_dot = "dot -Tpng schematic.dot -o schematic.png"
            subprocess.run(cmd_dot, shell=True)
            
            # 3. Display
            if os.path.exists("schematic.png"):
                self.display_image("schematic.png")
                self.log_system("Schematic updated in Right Pane.")
            else:
                self.log_system("Error: 'dot' command failed. Is Graphviz installed?")
        else:
            self.log_system("Error: Yosys did not generate a .dot file.")

    def display_image(self, path):
        try:
            # Tkinter needs PhotoImage to keep a reference or it gets garbage collected
            self.tk_image = tk.PhotoImage(file=path)
            # Scale down if too big (basic scaling)
            if self.tk_image.width() > 400:
                self.tk_image = self.tk_image.subsample(2, 2)
                
            self.img_label.config(image=self.tk_image, text="")
        except Exception as e:
            self.log_system(f"Image Error: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VerilogIDE(root)
    root.mainloop()
