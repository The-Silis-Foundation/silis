import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import subprocess
import os

class VerilogIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("WSL Verilog Studio (POC v1)")
        self.root.geometry("1200x800")
        
        # Current file tracking
        self.current_file = None
        
        # --- STYLES ---
        style = ttk.Style()
        style.theme_use('clam')
        
        # --- TOOLBAR ---
        toolbar = tk.Frame(root, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        btn_new = tk.Button(toolbar, text="New File", command=self.new_file)
        btn_new.pack(side=tk.LEFT, padx=2, pady=2)
        
        btn_save = tk.Button(toolbar, text="Save", command=self.save_file)
        btn_save.pack(side=tk.LEFT, padx=2, pady=2)
        
        tk.Frame(toolbar, width=20).pack(side=tk.LEFT) # Spacer
        
        btn_run = tk.Button(toolbar, text="Compile & Sim (Icarus)", command=self.run_simulation, bg="#d1e7dd")
        btn_run.pack(side=tk.LEFT, padx=2, pady=2)
        
        btn_wave = tk.Button(toolbar, text="Show Waves (GTK)", command=self.open_waves, bg="#cfe2ff")
        btn_wave.pack(side=tk.LEFT, padx=2, pady=2)
        
        btn_yosys = tk.Button(toolbar, text="Check Synth (Yosys)", command=self.run_yosys, bg="#fff3cd")
        btn_yosys.pack(side=tk.LEFT, padx=2, pady=2)

        btn_refresh = tk.Button(toolbar, text="Refresh Files", command=self.populate_file_list)
        btn_refresh.pack(side=tk.RIGHT, padx=2, pady=2)

        # --- MAIN SPLIT VIEW (Left: Dashboard, Right: Editor) ---
        self.main_pane = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)
        
        # --- LEFT PANE (Dashboard) ---
        self.left_pane = ttk.PanedWindow(self.main_pane, orient=tk.VERTICAL)
        self.main_pane.add(self.left_pane, weight=1)
        
        # 1. File Explorer (Top Left)
        file_frame = tk.LabelFrame(self.left_pane, text="Project Files (.v)")
        self.left_pane.add(file_frame, weight=3)
        
        self.tree = ttk.Treeview(file_frame, show='tree')
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_file_double_click)
        
        # 2. Terminal Output (Bottom Left)
        console_frame = tk.LabelFrame(self.left_pane, text="Terminal / Logs")
        self.left_pane.add(console_frame, weight=1)
        
        self.console = scrolledtext.ScrolledText(console_frame, bg="black", fg="#00ff00", font=("Consolas", 10))
        self.console.pack(fill=tk.BOTH, expand=True)

        # --- RIGHT PANE (Code Editor) ---
        editor_frame = tk.LabelFrame(self.main_pane, text="Code Editor")
        self.main_pane.add(editor_frame, weight=4) # Editor gets 4x width of left pane
        
        self.editor = scrolledtext.ScrolledText(editor_frame, undo=True, font=("Courier New", 12))
        self.editor.pack(fill=tk.BOTH, expand=True)

        # Initialize
        self.populate_file_list()
        self.log("System Ready. Select a file or create new.")

    # --- CORE LOGIC ---

    def log(self, message):
        """Prints to the internal console"""
        self.console.insert(tk.END, f"> {message}\n")
        self.console.see(tk.END)

    def populate_file_list(self):
        """Scans current folder for .v files"""
        self.tree.delete(*self.tree.get_children())
        path = "."
        for file in os.listdir(path):
            if file.endswith(".v"):
                self.tree.insert("", tk.END, text=file, values=(file,))

    def new_file(self):
        self.current_file = None
        self.editor.delete(1.0, tk.END)
        self.root.title("WSL Verilog Studio - New File")

    def save_file(self):
        if not self.current_file:
            filename = filedialog.asksaveasfilename(defaultextension=".v", filetypes=[("Verilog", "*.v")])
            if not filename: return
            self.current_file = filename
        
        with open(self.current_file, "w") as f:
            code = self.editor.get(1.0, tk.END)
            f.write(code)
        
        self.root.title(f"WSL Verilog Studio - {os.path.basename(self.current_file)}")
        self.log(f"Saved: {self.current_file}")
        self.populate_file_list()

    def on_file_double_click(self, event):
        item = self.tree.selection()[0]
        filename = self.tree.item(item, "text")
        self.current_file = filename
        
        with open(filename, "r") as f:
            self.editor.delete(1.0, tk.END)
            self.editor.insert(tk.END, f.read())
        
        self.root.title(f"WSL Verilog Studio - {filename}")
        self.log(f"Loaded: {filename}")

    # --- TOOLS INTERFACE ---

    def run_command(self, command):
        """Helper to run shell commands in WSL"""
        self.log(f"Executing: {command}")
        try:
            # Capture both stdout and stderr
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.stdout:
                self.console.insert(tk.END, result.stdout)
            if result.stderr:
                self.console.insert(tk.END, result.stderr)
            
            if result.returncode == 0:
                self.log("SUCCESS")
                return True
            else:
                self.log("FAILED (Exit Code: {})".format(result.returncode))
                return False
        except Exception as e:
            self.log(f"Error: {e}")
            return False

    def run_simulation(self):
        if not self.current_file:
            self.log("Error: Save file first.")
            return
        
        self.save_file() # Auto-save
        
        # 1. Compile (Iverilog)
        outfile = self.current_file.replace(".v", ".out")
        cmd_compile = f"iverilog -o {outfile} {self.current_file}"
        if self.run_command(cmd_compile):
            # 2. Run (VVP)
            cmd_run = f"vvp {outfile}"
            self.run_command(cmd_run)

    def open_waves(self):
        # Look for a .vcd file (usually generated by $dumpfile in testbench)
        # We try to find one matching the project or just any VCD
        found_vcd = None
        for file in os.listdir("."):
            if file.endswith(".vcd"):
                found_vcd = file
                break
        
        if found_vcd:
            self.log(f"Opening waves: {found_vcd}")
            subprocess.Popen(["gtkwave", found_vcd]) # Popen keeps it independent
        else:
            self.log("Error: No .vcd file found. Did you add $dumpfile to your testbench?")

    def run_yosys(self):
        if not self.current_file: return
        self.save_file()
        
        # Simple synthesis check command
        # read_verilog -> process -> optimize -> show stats
        cmd = f"yosys -p 'read_verilog {self.current_file}; proc; opt; stat' -q"
        self.log("Running Yosys Synthesis Check...")
        self.run_command(cmd)

if __name__ == "__main__":
    root = tk.Tk()
    app = VerilogIDE(root)
    root.mainloop()
