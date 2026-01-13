import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import subprocess
import os
import shutil
import threading
import queue
import json
import datetime
import re
from contextlib import suppress

# =============================================================================
#                                CONFIGURATION
# =============================================================================

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "github_user": "",
    "repo_url": "https://github.com/JeromeAntonyRobin/silis.git",
    "run_cmd": "python3",
    "last_dir": os.getcwd(),
    "keybinds": {
        "focus_tree": "v",
        "focus_editor": "c",
        "focus_todo": "b",
        "focus_complaints": "n",
        "focus_term": "x",
        "stash": "s",
        "push": "p",
        "pull": "l",
        "run": "r",
        "promote": "m",
        "add_dev": "a"
    }
}

# =============================================================================
#                                 HELPER UTILS
# =============================================================================

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f: json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f: 
            cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg: cfg[k] = v
            return cfg
    except: return DEFAULT_CONFIG

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f: json.dump(cfg, f, indent=4)

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

# =============================================================================
#                           SILIS CODE EDITOR ENGINE
# =============================================================================

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
    def insert_tab_spaces(self, event): self.text.insert(tk.INSERT, "    "); return "break"

    def auto_indent(self, event):
        cursor_pos = self.text.index(tk.INSERT)
        line_num = int(cursor_pos.split('.')[0])
        line_text = self.text.get(f"{line_num}.0", f"{line_num}.end")
        indent = ""
        for char in line_text:
            if char in " \t": indent += char
            else: break
        self.text.insert(tk.INSERT, "\n" + indent)
        self.text.see(tk.INSERT)
        return "break"

    def setup_tags(self):
        self.text.tag_configure("KEYWORD", foreground="#0000FF", font=(self.font[0], self.font[1], "bold"))
        self.text.tag_configure("COMMENT", foreground="#008000")
        self.text.tag_configure("STRING", foreground="#A31515")
        self.text.tag_configure("NUMBER", foreground="#800080")
        self.text.tag_configure("ERROR", background="#FFCCCC")

    def on_scroll(self, *args): self.text.yview(*args); self.gutter.yview(*args)
    def sync_scroll(self, event): self.gutter.yview_moveto(self.text.yview()[0])
    def on_content_changed(self, event=None): 
        self.text.edit_separator() 
        self.update_line_numbers()
        self.highlight_syntax()

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
        keywords = r"\b(module|endmodule|input|output|wire|reg|always|initial|begin|end|assign|posedge|negedge|if|else|case|endcase|default|parameter|def|class|return|import|from|while|for|in)\b"
        for match in re.finditer(keywords, text_content): self.text.tag_add("KEYWORD", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        numbers = r"\b\d+'[bh]\w+|\b\d+\b"
        for match in re.finditer(numbers, text_content): self.text.tag_add("NUMBER", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        strings = r"\".*?\""
        for match in re.finditer(strings, text_content): self.text.tag_add("STRING", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        comments = r"//.*|#.*"
        for match in re.finditer(comments, text_content): self.text.tag_add("COMMENT", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

    def get(self, *args): return self.text.get(*args)
    def delete(self, *args): self.text.delete(*args); self.on_content_changed()
    def insert(self, *args): self.text.insert(*args); self.on_content_changed()
    def focus_set(self): self.text.focus_set()

# =============================================================================
#                                 MAIN APPLICATION
# =============================================================================

class DevCtrl:
    def __init__(self, root):
        self.root = root
        self.root.title("DevCtrl v5 (Generic)")
        self.root.geometry("1400x900")
        
        self.cfg = load_config()
        self.cwd = self.cfg["last_dir"]
        self.current_file = None
        self.sk_active = False 
        self.queue = queue.Queue()

        # Styles
        style = ttk.Style()
        style.theme_use('clam')
        
        # --- TOOLBAR ---
        self.toolbar = tk.Frame(root, bg="#e1e1e1", bd=1, relief=tk.RAISED)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        
        def btn(txt, cmd, bg="#f0f0f0"):
            tk.Button(self.toolbar, text=txt, command=cmd, bg=bg, relief="flat", padx=10).pack(side=tk.LEFT, padx=1, pady=1)

        btn("📦 Stash", lambda: self.run_threaded(self.action_stash), "#fff3cd")
        tk.Frame(self.toolbar, width=10, bg="#e1e1e1").pack(side=tk.LEFT)
        btn("⬇️ Pull", lambda: self.run_threaded(self.action_destructive_pull), "#f8d7da")
        btn("⬆️ Push (Locked)", lambda: self.run_threaded(self.action_destructive_push), "#d4edda")
        tk.Frame(self.toolbar, width=10, bg="#e1e1e1").pack(side=tk.LEFT)
        btn("Promote", lambda: self.run_threaded(self.action_promote), "#d1ecf1")
        btn("▶️ Run", lambda: self.run_threaded(self.action_run_code), "#cff4fc")
        
        tk.Button(self.toolbar, text="⚙ Settings", command=self.open_settings, bg="#e2e3e5", relief="flat").pack(side=tk.RIGHT, padx=5)
        tk.Button(self.toolbar, text="➕ Add Dev", command=self.action_add_dev, bg="#e2e3e5", relief="flat").pack(side=tk.RIGHT, padx=5)

        # --- MAIN SPLIT ---
        self.main_split = ttk.PanedWindow(root, orient=tk.VERTICAL)
        self.main_split.pack(fill=tk.BOTH, expand=True)
        
        # --- TOP AREA ---
        self.top_pane = ttk.PanedWindow(self.main_split, orient=tk.HORIZONTAL)
        self.main_split.add(self.top_pane, weight=5)

        # 1. EXPLORER
        self.tree_frame = tk.LabelFrame(self.top_pane, text="Explorer")
        self.top_pane.add(self.tree_frame, weight=1)
        self.tree = ttk.Treeview(self.tree_frame, show='tree')
        self.tree.pack(fill=tk.BOTH, expand=True)
        bridge_numpad(self.tree)
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_expand)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Return>", self.on_tree_enter_key)
        self.tree.bind("<Escape>", self.on_tree_up_dir)
        self.tree.bind("<FocusIn>", self.on_tree_focus)
        self.tree.bind("<Delete>", self.delete_file_prompt)

        # 2. EDITOR
        self.editor_frame = tk.LabelFrame(self.top_pane, text="Code Editor")
        self.top_pane.add(self.editor_frame, weight=3)
        self.status_bar = tk.Frame(self.editor_frame, bg="#f0f0f0", height=20)
        self.status_bar.pack(fill=tk.X, side=tk.TOP)
        self.lbl_file = tk.Label(self.status_bar, text="[No File]", bg="#f0f0f0", fg="blue", font=("Consolas", 9))
        self.lbl_file.pack(side=tk.LEFT, padx=5)
        self.lbl_unsaved = tk.Label(self.status_bar, text="", bg="#f0f0f0", fg="red", font=("Consolas", 9, "bold"))
        self.lbl_unsaved.pack(side=tk.LEFT)
        self.editor = CodeEditor(self.editor_frame)
        self.editor.text.bind("<Key>", self.on_edit_key)

        # 3. RIGHT PANEL (SPLIT)
        self.right_frame = tk.Frame(self.top_pane)
        self.top_pane.add(self.right_frame, weight=1)
        self.right_split = ttk.PanedWindow(self.right_frame, orient=tk.VERTICAL)
        self.right_split.pack(fill=tk.BOTH, expand=True)

        # 3a. To-Do
        self.todo_frame = tk.LabelFrame(self.right_split, text="To-Do (Private)")
        self.right_split.add(self.todo_frame, weight=1)
        self.todo_text = tk.Text(self.todo_frame, font=("Consolas", 10), bg="#fffff0", spacing1=5)
        self.todo_text.pack(fill=tk.BOTH, expand=True)
        self.todo_text.bind("<KeyRelease>", self.save_right_panel)

        # 3b. Complaints
        self.comp_frame = tk.LabelFrame(self.right_split, text="Complaints (Public)")
        self.right_split.add(self.comp_frame, weight=1)
        self.comp_text = tk.Text(self.comp_frame, font=("Consolas", 10), bg="#fff0f0", spacing1=5)
        self.comp_text.pack(fill=tk.BOTH, expand=True)
        self.comp_btn = tk.Button(self.comp_frame, text="🛑 Log Complaint (Commit & Push)", command=lambda: self.run_threaded(self.action_log_complaint), bg="#dc3545", fg="white")
        self.comp_btn.pack(fill=tk.X)

        # --- BOTTOM AREA (Terminal) ---
        self.term_frame = tk.LabelFrame(self.main_split, text="Terminal")
        self.main_split.add(self.term_frame, weight=1)
        self.term_log = scrolledtext.ScrolledText(self.term_frame, bg="#1e1e1e", fg="#e0e0e0", font=("Consolas", 10), height=8)
        self.term_log.pack(fill=tk.BOTH, expand=True)
        self.term_log.tag_config("SYS", foreground="#00FFFF")
        self.term_log.tag_config("ERR", foreground="#FF5555")
        self.term_log.tag_config("CMD", foreground="#F1FA8C")
        self.term_log.tag_config("INPUT", foreground="#FFFFFF")
        
        input_frame = tk.Frame(self.term_frame, bg="#333")
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(input_frame, text=" > ", bg="#333", fg="white", font=("Consolas", 10, "bold")).pack(side=tk.LEFT)
        self.term_input = tk.Entry(input_frame, bg="#333", fg="white", font=("Consolas", 10), insertbackground="white")
        self.term_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.term_input.bind("<Return>", self.handle_terminal_input)
        self.term_input.bind("<Tab>", self.handle_tab_autocomplete)

        # --- BINDINGS ---
        self.root.bind("<grave>", self.activate_superkey)
        self.root.bind("<Key>", self.handle_global_key)
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-n>", lambda e: self.new_file())

        # --- INIT ---
        self.refresh_file_tree()
        self.update_labels()
        self.log("DevCtrl v5 Online.", "SYS")
        self.root.after(100, self.process_queue)
        self.root.after(500, self.check_first_run) 

    # =========================================================================
    #                         FIRST RUN & ONBOARDING
    # =========================================================================

    def check_first_run(self):
        if not self.cfg.get("github_user"):
            self.log("First Run Detected. Starting Onboarding...", "SYS")
            user = simpledialog.askstring("Welcome to DevCtrl", "Please enter your GitHub Username:")
            repo = simpledialog.askstring("Repo Setup", "Enter Repository URL:", initialvalue=self.cfg["repo_url"])
            
            if user:
                self.cfg["github_user"] = user
                if repo: self.cfg["repo_url"] = repo
                save_config(self.cfg)
                self.log(f"Welcome, {user}!", "SYS")
                self.ensure_dev_environment(user)
            else:
                self.log("Setup Cancelled. Features may be limited.", "ERR")
        else:
            self.run_threaded(self.setup_repo)

    def ensure_dev_environment(self, user):
        self.run_threaded(self.setup_repo)
        dev_dir_name = f"dev_{user}"
        dev_path = os.path.join(self.cfg["last_dir"], dev_dir_name)
        
        if not os.path.exists(dev_path):
            try:
                os.makedirs(dev_path)
                self.log(f"Created workspace: {dev_dir_name}", "SYS")
                with open(os.path.join(dev_path, "README.md"), "w") as f:
                    f.write(f"# Dev Space for {user}\nManaged by DevCtrl.")
            except Exception as e:
                self.log(f"Could not create workspace: {e}", "ERR")
        
        self.change_directory_silent(dev_path)

    # =========================================================================
    #                               CORE LOGIC
    # =========================================================================

    def log(self, msg, tag="CMD"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.term_log.insert(tk.END, f"[{ts}] {msg}\n", tag)
        self.term_log.see(tk.END)
    
    def print_grid(self, items):
        self.log("Options:", "SYS")
        max_len = max(len(i) for i in items) + 2; cols = max(1, 80 // max_len)
        line = ""
        for i, item in enumerate(items):
            line += f"{item:<{max_len}}"
            if (i + 1) % cols == 0: self.term_log.insert(tk.END, line + "\n", "SYS"); line = ""
        if line: self.term_log.insert(tk.END, line + "\n", "SYS")
        self.term_log.see(tk.END)

    def process_queue(self):
        while not self.queue.empty():
            msg, tag = self.queue.get()
            self.log(msg, tag)
        self.root.after(100, self.process_queue)

    def run_threaded(self, target_func, *args):
        t = threading.Thread(target=target_func, args=args, daemon=True)
        t.start()
        
    def save_right_panel(self, event=None):
        if not os.path.exists(self.cwd): return
        # Save To-Do
        with open(os.path.join(self.cwd, "todo.txt"), "w") as f:
            f.write(self.todo_text.get("1.0", tk.END))
        # Save Complaints (Local save only, push is manual)
        with open(os.path.join(self.cwd, "complaints.txt"), "w") as f:
            f.write(self.comp_text.get("1.0", tk.END))

    def load_right_panel(self):
        self.todo_text.delete(1.0, tk.END)
        self.comp_text.delete(1.0, tk.END)
        
        todo_p = os.path.join(self.cwd, "todo.txt")
        comp_p = os.path.join(self.cwd, "complaints.txt")
        
        if os.path.exists(todo_p):
            with open(todo_p, "r") as f: self.todo_text.insert(1.0, f.read())
        
        if os.path.exists(comp_p):
            with open(comp_p, "r") as f: self.comp_text.insert(1.0, f.read())

    # =========================================================================
    #                         WORKFLOW ACTIONS
    # =========================================================================

    def action_destructive_push(self):
        # SAFETY LOCK: Enforce push from /dev_user
        user = self.cfg.get("github_user", "")
        if not user:
            self.queue.put(("PUSH ABORTED: No GitHub user configured.", "ERR"))
            return

        # Locate the user's dev folder by scanning up/down or assuming structure
        # Best guess: It's in the repo root named dev_user.
        # We need to find repo root first.
        
        # 1. Find Repo Root
        repo_root = self.cwd
        while not os.path.exists(os.path.join(repo_root, ".git")):
            parent = os.path.dirname(repo_root)
            if parent == repo_root: break # Hit fs root
            repo_root = parent
        
        target_dir = os.path.join(repo_root, f"dev_{user}")
        
        if not os.path.exists(target_dir):
             self.queue.put((f"PUSH ABORTED: Dev folder {f'dev_{user}'} not found.", "ERR"))
             return

        self.queue.put((f"🔒 LOCKED PUSH: Syncing only {f'dev_{user}'}...", "SYS"))
        
        cmds = [
            ["git", "add", "-A"], 
            ["git", "commit", "-m", f"DevCtrl Push by {user}"], 
            ["git", "push", "-u", "origin", "main"]
        ]
        
        for cmd in cmds:
            try:
                res = subprocess.run(cmd, cwd=target_dir, capture_output=True, text=True)
                if res.returncode != 0 and "nothing to commit" not in res.stdout:
                    self.queue.put((f"GIT ERROR: {res.stderr}", "ERR")); return
                if res.stdout.strip(): self.queue.put((res.stdout.strip(), "CMD"))
            except Exception as e: self.queue.put((f"EXEC ERROR: {e}", "ERR")); return
        self.queue.put(("✅ SECURE PUSH COMPLETE.", "SYS"))

    def action_promote(self):
        if not self.current_file:
            self.queue.put(("PROMOTE ERROR: No file open.", "ERR")); return

        user = self.cfg.get("github_user", "unknown")
        
        # 1. Find Repo Root
        repo_root = self.cwd
        while not os.path.exists(os.path.join(repo_root, ".git")):
            parent = os.path.dirname(repo_root)
            if parent == repo_root: break 
            repo_root = parent

        # 2. Construct Dest
        dest_dir = os.path.join(repo_root, "experimental", "promoted", f"by_{user}")
        if not os.path.exists(dest_dir): os.makedirs(dest_dir)
        
        filename = os.path.basename(self.current_file)
        dest_path = os.path.join(dest_dir, filename)
        
        try:
            # Copy
            shutil.copy2(self.current_file, dest_path)
            self.queue.put((f"Promoted {filename} -> experimental/promoted/by_{user}", "SYS"))
            
            # Surgical Push
            cmds = [
                ["git", "add", dest_path],
                ["git", "commit", "-m", f"Promote {filename} by {user}"],
                ["git", "push"]
            ]
            for cmd in cmds:
                 subprocess.run(cmd, cwd=repo_root, capture_output=True) # Run from root to catch the path
            self.queue.put(("✅ PROMOTION PUSHED.", "SYS"))
            
        except Exception as e:
            self.queue.put((f"Promote Failed: {e}", "ERR"))

    def action_log_complaint(self):
        # Saves current complaint text and pushes ONLY that file
        complaint_file = os.path.join(self.cwd, "complaints.txt")
        self.save_right_panel() # Ensure saved to disk
        
        if not os.path.exists(complaint_file):
            self.queue.put(("No complaints file to log.", "ERR")); return

        user = self.cfg.get("github_user", "Anon")
        
        # Append Signature
        with open(complaint_file, "a") as f:
            f.write(f"\n-- Logged by {user} at {datetime.datetime.now()}\n")
            
        self.queue.put((f"Logging complaint in {os.path.basename(self.cwd)}...", "SYS"))
        
        # Surgical Push
        cmds = [
            ["git", "add", complaint_file],
            ["git", "commit", "-m", f"Complaint logged by {user}"],
            ["git", "push"]
        ]
        
        for cmd in cmds:
            try:
                # Run from CWD (where complaint file is)
                res = subprocess.run(cmd, cwd=self.cwd, capture_output=True, text=True)
                if res.returncode != 0 and "nothing to commit" not in res.stdout:
                     self.queue.put((f"GIT ERROR: {res.stderr}", "ERR")); return
            except Exception as e: self.queue.put((f"EXEC ERROR: {e}", "ERR")); return
            
        self.queue.put(("✅ COMPLAINT LOGGED & PUSHED.", "SYS"))

    def action_destructive_pull(self):
        self.queue.put(("PULL: Overwriting Local...", "SYS"))
        cmds = [["git", "fetch", "--all"], ["git", "reset", "--hard", "origin/main"]]
        for cmd in cmds:
            try:
                res = subprocess.run(cmd, cwd=self.cwd, capture_output=True, text=True)
                if res.returncode != 0: self.queue.put((f"GIT ERROR: {res.stderr}", "ERR")); return
                self.queue.put((res.stdout or "Reset Complete", "CMD"))
            except Exception as e: self.queue.put((f"EXEC ERROR: {e}", "ERR")); return
        self.queue.put(("✅ PULL COMPLETE.", "SYS")); self.root.after(100, self.refresh_file_tree)
        
    def action_run_code(self):
        if not self.current_file: self.queue.put(("RUN ERROR: No file open.", "ERR")); return
        self.root.after(0, self.save_file)
        cmd_base = self.cfg["run_cmd"]; filename = os.path.basename(self.current_file)
        self.queue.put((f"RUNNING: {cmd_base} {filename} ...", "SYS"))
        try:
            cmd = f"{cmd_base} {filename}"
            res = subprocess.run(cmd, shell=True, cwd=self.cwd, capture_output=True, text=True)
            if res.stdout: self.queue.put((res.stdout, "CMD"))
            if res.stderr: self.queue.put((res.stderr, "ERR"))
            self.queue.put(("[Finished]", "SYS"))
        except Exception as e: self.queue.put((f"RUN ERROR: {e}", "ERR"))

    def action_stash(self):
        self.queue.put(("STASH: Initiating snapshot...", "SYS"))
        stash_root = os.path.join(self.cwd, "stash")
        if not os.path.exists(stash_root): os.makedirs(stash_root)
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        ver_name = f"snap_{ts}"
        dest_path = os.path.join(stash_root, ver_name)
        try:
            os.makedirs(dest_path)
            for item in os.listdir(self.cwd):
                if item == "stash": continue
                s = os.path.join(self.cwd, item); d = os.path.join(dest_path, item)
                if os.path.isdir(s): shutil.copytree(s, d)
                else: shutil.copy2(s, d)
            self.queue.put((f"STASH SAVED: {ver_name}", "SYS"))
        except Exception as e: self.queue.put((f"STASH FAILED: {e}", "ERR"))
        self.root.after(100, self.refresh_file_tree)

    def action_add_dev(self):
        username = simpledialog.askstring("Add Dev", "Enter GitHub Username:")
        if not username: return
        self.queue.put(f"Inviting {username}...", "SYS")
        def _invite():
            url = self.cfg["repo_url"]
            repo_slug = "JeromeAntonyRobin/silis" 
            if "github.com/" in url:
                parts = url.split("github.com/")[-1].replace(".git", "").split("/")
                if len(parts) >= 2: repo_slug = f"{parts[0]}/{parts[1]}"
            cmd = ["gh", "repo", "collaborator", "add", username, "--repo", repo_slug]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0: self.queue.put((f"SUCCESS: Invite sent to {username}", "SYS"))
                else: self.queue.put((f"FAILED: {res.stderr}", "ERR"))
            except Exception as e: self.queue.put((f"EXEC ERROR: {e}", "ERR"))
        self.run_threaded(_invite)

    # =========================================================================
    #                               NAV & FILES
    # =========================================================================

    def setup_repo(self):
        if not os.path.exists(os.path.join(self.cwd, ".git")):
            self.queue.put(("Repo not found. Initializing...", "SYS"))
            subprocess.run(["git", "init"], cwd=self.cwd)
            subprocess.run(["git", "remote", "add", "origin", self.cfg["repo_url"]], cwd=self.cwd)
            self.queue.put(("Repo Init Complete.", "SYS"))
        else:
            self.queue.put(("Repo Connected.", "SYS"))

    def refresh_file_tree(self):
        self.tree.delete(*self.tree.get_children())
        root_node = self.tree.insert("", tk.END, text=os.path.basename(self.cwd) or self.cwd, open=True, values=(self.cwd, "dir"))
        self.populate_node(root_node, self.cwd)
        self.on_tree_focus(None)
        self.load_right_panel() # Auto-load todo/complaints for this folder

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
        item_id = self.tree.focus()
        if not item_id: return
        path, ftype = self.tree.item(item_id, "values")
        if ftype == "dir": self.populate_node(item_id, path)

    def on_tree_enter_key(self, event):
        item_id = self.tree.focus()
        if not item_id: return
        path, ftype = self.tree.item(item_id, "values")
        if ftype == "file": self.open_file_in_editor(path)
        else:
            self.change_directory_silent(path)
            if not self.tree.item(item_id, "open"): 
                self.populate_node(item_id, path)
                self.tree.item(item_id, open=True)
            else: self.tree.item(item_id, open=False)
        return "break"

    def on_tree_double_click(self, event): self.on_tree_enter_key(event)

    def on_tree_up_dir(self, event):
        try: 
            os.chdir("..")
            self.cwd = os.getcwd()
            self.refresh_file_tree()
            self.log(f"CD .. -> {self.cwd}", "SYS")
        except Exception as e: self.log(f"Error: {e}", "ERR")

    def change_directory_silent(self, new_dir):
        try:
            os.chdir(new_dir)
            self.cwd = os.getcwd()
            if "stash" not in self.cwd: 
                self.cfg["last_dir"] = self.cwd
                save_config(self.cfg)
            self.refresh_file_tree()
        except Exception as e: self.log(f"CD Error: {e}", "ERR")

    def open_file_in_editor(self, path):
        try:
            with open(path, "r") as f: content = f.read()
            self.editor.delete(1.0, tk.END); self.editor.insert(tk.END, content)
            self.current_file = path; self.lbl_file.config(text=os.path.basename(path)); self.lbl_unsaved.config(text=""); self.log(f"Opened {os.path.basename(path)}", "SYS")
        except: pass
        
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
                self.log(f"Deleted: {path}", "SUCCESS")
                self.refresh_file_tree()
            except Exception as e: self.log(f"Delete Failed: {e}", "ERR")

    def new_file(self):
        self.current_file = None
        self.editor.delete(1.0, tk.END)
        self.lbl_file.config(text="[New File]")
        self.log("New File Created", "SYS")

    def save_file(self):
        if not self.current_file:
            f = filedialog.asksaveasfilename(initialdir=self.cwd)
            if not f: return
            self.current_file = f
        try:
            content = self.editor.get(1.0, tk.END)
            if content.endswith("\n"): content = content[:-1]
            with open(self.current_file, "w") as f: f.write(content)
            self.lbl_unsaved.config(text="")
            self.lbl_file.config(text=os.path.basename(self.current_file))
            self.log(f"Saved: {os.path.basename(self.current_file)}", "SYS")
        except Exception as e: self.log(f"Save Error: {e}", "ERR")

    def on_edit_key(self, event):
        if self.current_file:
            self.lbl_unsaved.config(text="*")

    # --- TERMINAL ---
    def handle_terminal_input(self, event):
        cmd = self.term_input.get()
        self.term_input.delete(0, tk.END)
        self.term_log.insert(tk.END, f"$ {cmd}\n", "INPUT")
        if cmd.startswith("cd "):
            target = cmd[3:].strip()
            self.change_directory_silent(target)
            return
        if cmd == "clear": self.term_log.delete(1.0, tk.END); return
        def _exec():
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=self.cwd)
                if res.stdout: self.queue.put((res.stdout.strip(), "CMD"))
                if res.stderr: self.queue.put((res.stderr.strip(), "ERR"))
            except Exception as e: self.queue.put((f"Exec Error: {e}", "ERR"))
        self.run_threaded(_exec)

    def handle_tab_autocomplete(self, event):
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
        except Exception as e: self.log(f"Autocomplete Error: {e}", "ERR")
        return "break"

    def update_labels(self):
        b = self.cfg["keybinds"]
        self.tree_frame.config(text=f"Explorer (` + {b['focus_tree']})")
        self.editor_frame.config(text=f"Code Editor (` + {b['focus_editor']})")
        self.todo_frame.config(text=f"To-Do (` + {b['focus_todo']})")
        self.comp_frame.config(text=f"Complaints (` + {b['focus_complaints']})")
        self.term_frame.config(text=f"Terminal (` + {b['focus_term']})")

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("400x650")
        tk.Label(win, text="Settings", font=("Arial", 14, "bold")).pack(pady=10)
        form = tk.Frame(win)
        form.pack(fill=tk.BOTH, expand=True, padx=20)
        entries = {}
        def add_entry(label, key, is_bind=False):
            f = tk.Frame(form); f.pack(fill=tk.X, pady=2)
            tk.Label(f, text=label, width=20, anchor="w").pack(side=tk.LEFT)
            val = self.cfg["keybinds"][key] if is_bind else self.cfg.get(key, "")
            e = tk.Entry(f); e.insert(0, val); e.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            entries[key] = (e, is_bind)
        tk.Label(form, text="User & Repo", font=("Arial", 10, "bold", "underline")).pack(pady=5, anchor="w")
        add_entry("GitHub User", "github_user")
        add_entry("Repo URL", "repo_url")
        add_entry("Run Command", "run_cmd")
        tk.Label(form, text="Keybinds", font=("Arial", 10, "bold", "underline")).pack(pady=5, anchor="w")
        add_entry("Focus Explorer", "focus_tree", True)
        add_entry("Focus Editor", "focus_editor", True)
        add_entry("Focus To-Do", "focus_todo", True)
        add_entry("Focus Complaints", "focus_complaints", True)
        add_entry("Focus Terminal", "focus_term", True)
        def save():
            for key, (e, is_bind) in entries.items():
                if is_bind: self.cfg["keybinds"][key] = e.get()
                else: self.cfg[key] = e.get()
            save_config(self.cfg)
            self.update_labels()
            self.log("Settings Saved.", "SYS")
            win.destroy()
        tk.Button(win, text="Save Configuration", command=save, bg="#d4edda", height=2).pack(pady=20, fill=tk.X, padx=20)

    # --- SUPERKEY SYSTEM ---
    def activate_superkey(self, event):
        self.sk_active = True
        self.toolbar.config(bg="#00FFFF")
        self.root.after(1500, self.reset_superkey)
        return "break"
    def reset_superkey(self):
        self.sk_active = False
        self.toolbar.config(bg="#e1e1e1")
    def handle_global_key(self, event):
        if not self.sk_active: return
        key = event.keysym.lower()
        binds = self.cfg["keybinds"]
        if key == binds["focus_tree"]: self.tree.focus_set(); self.log("Focus -> Tree", "SYS")
        elif key == binds["focus_editor"]: self.editor.focus_set(); self.log("Focus -> Editor", "SYS")
        elif key == binds["focus_term"]: self.term_input.focus_set(); self.log("Focus -> Terminal", "SYS")
        elif key == binds["focus_todo"]: self.todo_text.focus_set(); self.log("Focus -> To-Do", "SYS")
        elif key == binds["focus_complaints"]: self.comp_text.focus_set(); self.log("Focus -> Complaints", "SYS")
        elif key == binds["stash"]: self.run_threaded(self.action_stash)
        elif key == binds["push"]: self.run_threaded(self.action_destructive_push)
        elif key == binds["pull"]: self.run_threaded(self.action_destructive_pull)
        elif key == binds["run"]: self.run_threaded(self.action_run_code)
        elif key == binds["promote"]: self.run_threaded(self.action_promote)
        elif key == binds["add_dev"]: self.action_add_dev()
        self.reset_superkey()
        return "break"

if __name__ == "__main__":
    root = tk.Tk()
    app = DevCtrl(root)
    root.mainloop()
