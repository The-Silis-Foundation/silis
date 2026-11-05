"""
tui_editor.py
A fast, beautiful, LazyVim-like terminal TUI editor for editing ASIC TCL scripts.
Supports modal editing (INSERT / NORMAL), syntax highlighting, line numbers,
status bar, and <Tab> autocomplete for ASIC / OpenROAD / Yosys commands and flags.
"""

import curses
import os
import re
import sys

# Comprehensive EDA & TCL Auto-completion dictionary
def _get_expanded_eda_keywords():
    try:
        from .tui_repl import SILIS_COMMANDS, TCL_KEYWORDS, BUILTIN_EDA_COMMANDS, EDA_FLAGS, load_dynamic_openroad_commands
        return sorted(list(set(SILIS_COMMANDS + TCL_KEYWORDS + BUILTIN_EDA_COMMANDS + EDA_FLAGS + load_dynamic_openroad_commands())))
    except Exception:
        pass
    return [

    # Silis High-Level ASIC commands
    "create_fence", "create_region", "place_macro", "create_blockage",
    "initialize_floorplan", "make_tracks", "set_thread_count",
    
    # OpenROAD Floorplanning & Placement
    "place_inst", "place_design", "global_placement", "detailed_placement",
    "create_voltage_domain", "define_corners", "read_lef", "read_def",
    "write_def", "write_db", "read_db", "read_sdc", "read_verilog",
    "link_design", "set_wire_rc",
    
    # CTS & Routing
    "clock_tree_synthesis", "repair_clock_nets", "repair_hold_violations",
    "global_route", "detailed_route", "estimate_parasitics",
    
    # Signoff & Timing (OpenSTA / Magic)
    "report_checks", "report_power", "report_tns", "report_wns",
    "report_worst_slack", "check_antennas", "check_placement",
    "drc_check", "gds_write",
    
    # Yosys Synthesis Commands
    "read_liberty", "synth", "dfflibmap", "abc", "stat", "write_verilog",
    "flatten", "clean", "opt", "techmap", "tee", "plugin", "ghdl",
    
    # Common EDA Flags
    "-module", "-box", "-density", "-halo", "-inst", "-cell", "-origin",
    "-orient", "-type", "-die_area", "-core_area", "-site", "-guide_file",
    "-congestion_iterations", "-output_drc", "-bottom_routing_layer",
    "-top_routing_layer", "-sink_clustering_enable", "-top", "-liberty",
    "-report_file", "-corner", "-path_delay", "-slack", "-endpoint"
]

EDA_KEYWORDS = _get_expanded_eda_keywords()


class LazyTclEditor:
    def __init__(self, initial_text="", title="TCL Script Editor"):
        self.lines = initial_text.splitlines() if initial_text else [""]
        if not self.lines:
            self.lines = [""]
        self.title = title
        self.mode = "INSERT"  # Default to INSERT so user can type immediately
        self.cursor_y = 0
        self.cursor_x = 0
        self.scroll_y = 0
        self.scroll_x = 0
        self.undo_stack = []
        self.cmd_buffer = ""
        self.status_msg = ""
        self.saved_text = None
        self.autocomplete_list = []
        self.autocomplete_idx = 0
        self.autocomplete_word = ""
        self.autocomplete_start_x = 0

    def run(self):
        return curses.wrapper(self._main)

    def _save_undo(self):
        self.undo_stack.append([list(self.lines), self.cursor_y, self.cursor_x])
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def _undo(self):
        if self.undo_stack:
            state = self.undo_stack.pop()
            self.lines = state[0]
            self.cursor_y = min(state[1], len(self.lines) - 1)
            self.cursor_x = min(state[2], len(self.lines[self.cursor_y]))
            self.status_msg = "-- UNDO --"

    def _init_colors(self):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)     # Keywords / Commands
        curses.init_pair(2, curses.COLOR_YELLOW, -1)   # Strings
        curses.init_pair(3, curses.COLOR_GREEN, -1)    # Comments
        curses.init_pair(4, curses.COLOR_MAGENTA, -1)  # Flags (-box, -density)
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Status Bar Normal
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_CYAN)  # Status Bar Insert
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_WHITE) # Line numbers / Menu sel
        curses.init_pair(8, curses.COLOR_WHITE, curses.COLOR_BLACK) # Menu normal

    def _get_current_word(self):
        line = self.lines[self.cursor_y]
        x = min(self.cursor_x, len(line))
        start = x
        while start > 0 and (line[start - 1].isalnum() or line[start - 1] in "_-"):
            start -= 1
        return line[start:x], start

    def _trigger_autocomplete(self):
        word, start_x = self._get_current_word()
        if not word:
            return
        matches = [kw for kw in EDA_KEYWORDS if kw.startswith(word) and kw != word]
        if not matches:
            matches = [kw for kw in EDA_KEYWORDS if word in kw and kw != word]
        if len(matches) == 1:
            # Direct complete
            completion = matches[0][len(word):]
            line = self.lines[self.cursor_y]
            self._save_undo()
            self.lines[self.cursor_y] = line[:self.cursor_x] + completion + line[self.cursor_x:]
            self.cursor_x += len(completion)
            self.status_msg = f"Completed: {matches[0]}"
        elif len(matches) > 1:
            self.autocomplete_list = matches[:8]
            self.autocomplete_idx = 0
            self.autocomplete_word = word
            self.autocomplete_start_x = start_x

    def _apply_autocomplete(self):
        if self.autocomplete_list:
            chosen = self.autocomplete_list[self.autocomplete_idx]
            line = self.lines[self.cursor_y]
            self._save_undo()
            self.lines[self.cursor_y] = line[:self.autocomplete_start_x] + chosen + line[self.cursor_x:]
            self.cursor_x = self.autocomplete_start_x + len(chosen)
            self.autocomplete_list = []
            self.status_msg = f"Selected: {chosen}"

    def insert_text_blob(self, text):
        """Insert arbitrary raw or pasted text without adding runaway auto-indentation."""
        if not text:
            return
        self._save_undo()
        norm_text = text.replace("\r\n", "\n").replace("\r", "\n")
        new_lines = norm_text.split("\n")
        
        cur = self.lines[self.cursor_y]
        prefix = cur[:self.cursor_x]
        suffix = cur[self.cursor_x:]
        
        if len(new_lines) == 1:
            self.lines[self.cursor_y] = prefix + new_lines[0] + suffix
            self.cursor_x = len(prefix) + len(new_lines[0])
        else:
            self.lines[self.cursor_y] = prefix + new_lines[0]
            for i in range(1, len(new_lines) - 1):
                self.lines.insert(self.cursor_y + i, new_lines[i])
            last_idx = self.cursor_y + len(new_lines) - 1
            self.lines.insert(last_idx, new_lines[-1] + suffix)
            self.cursor_y = last_idx
            self.cursor_x = len(new_lines[-1])
        # Reset horizontal scroll to keep start of line visible
        self.scroll_x = 0

    def _draw(self, stdscr):
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        text_h = h - 2  # 1 for header, 1 for status bar
        gutter_w = 6

        # Draw Header
        header = f" ⚡ SILIS ASIC TCL EDITOR — {self.title} "
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(0, 0, header.ljust(w)[:w], curses.color_pair(1))
        stdscr.attroff(curses.A_BOLD)

        # Scrolling adjustments
        if self.cursor_y < self.scroll_y:
            self.scroll_y = self.cursor_y
        if self.cursor_y >= self.scroll_y + text_h:
            self.scroll_y = self.cursor_y - text_h + 1

        edit_w = max(10, w - gutter_w)
        if self.cursor_x < self.scroll_x:
            self.scroll_x = self.cursor_x
        if self.cursor_x >= self.scroll_x + edit_w:
            self.scroll_x = self.cursor_x - edit_w + 1

        # Render Lines
        for idx in range(text_h):
            line_idx = self.scroll_y + idx
            screen_y = idx + 1
            if line_idx < len(self.lines):
                # Gutter
                gutter_text = f"{line_idx + 1:>4} │ "
                stdscr.addstr(screen_y, 0, gutter_text, curses.A_DIM)

                # Line content
                line_content = self.lines[line_idx]
                disp = line_content[self.scroll_x:self.scroll_x + edit_w]
                
                # Basic Highlighting
                cur_x = gutter_w
                if disp.strip().startswith("#"):
                    # Comment line
                    stdscr.addstr(screen_y, cur_x, disp[:edit_w], curses.color_pair(3))
                else:
                    # Token-level rendering
                    col = cur_x
                    words = re.split(r'(\s+|[{}";])', disp)
                    for token in words:
                        if not token:
                            continue
                        attr = 0
                        if token in EDA_KEYWORDS or token in ["set", "proc", "source", "if", "else", "foreach", "puts", "catch", "write_def"]:
                            attr = curses.color_pair(1) | curses.A_BOLD
                        elif token.startswith("-") and len(token) > 1:
                            attr = curses.color_pair(4)
                        elif token.startswith('"') or token.endswith('"'):
                            attr = curses.color_pair(2)
                        elif token.isdigit():
                            attr = curses.color_pair(2)
                        if col + len(token) <= w:
                            stdscr.addstr(screen_y, col, token, attr)
                        col += len(token)
            else:
                stdscr.addstr(screen_y, 0, "~".ljust(gutter_w), curses.A_DIM)

        # Autocomplete popup
        if self.autocomplete_list:
            popup_y = (self.cursor_y - self.scroll_y) + 2
            popup_x = gutter_w + (self.cursor_x - self.scroll_x)
            if popup_y + len(self.autocomplete_list) >= h - 1:
                popup_y = popup_y - len(self.autocomplete_list) - 2
            for i, opt in enumerate(self.autocomplete_list):
                py = popup_y + i
                if 0 <= py < h - 1:
                    style = curses.color_pair(7) if i == self.autocomplete_idx else curses.color_pair(8)
                    display_opt = f" {opt} ".ljust(25)
                    try:
                        stdscr.addstr(py, min(popup_x, w - 26), display_opt[:w-popup_x], style)
                    except:
                        pass

        # Draw Status Bar
        mode_str = f" {self.mode} "
        mode_pair = curses.color_pair(6) if self.mode == "INSERT" else curses.color_pair(5)
        pos_str = f" Ln {self.cursor_y + 1}, Col {self.cursor_x + 1} "
        hints = " <Tab> Autocomplete | Ctrl+S / :wq Run | Ctrl+C / :q! Cancel "
        if self.status_msg:
            hints = f" {self.status_msg} "
        
        status_bar = f"{mode_str} {hints}".ljust(w - len(pos_str)) + pos_str
        try:
            stdscr.addstr(h - 1, 0, status_bar[:w-1], mode_pair | curses.A_BOLD)
            stdscr.insstr(h - 1, w - 1, status_bar[-1] if len(status_bar) >= w else ' ', mode_pair | curses.A_BOLD)
        except Exception:
            pass

        # Position hardware cursor
        cy = (self.cursor_y - self.scroll_y) + 1
        cx = gutter_w + (self.cursor_x - self.scroll_x)
        stdscr.move(max(1, min(cy, h - 2)), max(gutter_w, min(cx, w - 1)))
        stdscr.refresh()

    def _main(self, stdscr):
        curses.raw()
        stdscr.keypad(True)
        if hasattr(curses, "set_escdelay"):
            try:
                curses.set_escdelay(25)
            except Exception:
                pass
        self._init_colors()

        # Enable bracketed paste mode in terminal emulator
        sys.stdout.write("[?2004h")
        sys.stdout.flush()

        in_bracketed_paste = False
        paste_buffer = []

        try:
            while True:
                self._draw(stdscr)
                try:
                    ch = stdscr.getch()
                except KeyboardInterrupt:
                    return None  # Cancel on Ctrl+C

                # Check for bracketed paste sequences ([200~ ... [201~)
                if ch == 27:
                    # Check if followed by [200~ or [201~
                    stdscr.nodelay(True)
                    chars = [27]
                    while True:
                        c2 = stdscr.getch()
                        if c2 == -1:
                            break
                        chars.append(c2)
                    stdscr.nodelay(False)

                    seq = "".join(chr(c) for c in chars if 0 <= c <= 255)
                    if seq == "[200~":
                        in_bracketed_paste = True
                        paste_buffer = []
                        continue
                    elif seq == "[201~":
                        in_bracketed_paste = False
                        if paste_buffer:
                            self.insert_text_blob("".join(paste_buffer))
                            paste_buffer = []
                        continue
                    elif "[200~" in seq or "[201~" in seq:
                        # Full paste chunk received in a single escape burst
                        parts = seq.split("[200~")
                        for part in parts:
                            if "[201~" in part:
                                pasted_content, remainder = part.split("[201~", 1)
                                self.insert_text_blob(pasted_content)
                        continue
                    elif len(chars) > 1:
                        # Other escape sequence
                        if in_bracketed_paste:
                            paste_buffer.append(seq)
                            continue
                        ch = 27
                    else:
                        ch = 27

                if in_bracketed_paste:
                    if ch in [10, 13]:
                        paste_buffer.append("\n")
                    elif 32 <= ch <= 126 or ch == 9:
                        paste_buffer.append(chr(ch))
                    continue

                # Rapid paste detection (when terminal doesn't use bracketed paste)
                # If there are characters immediately buffered in stdin queue, consume them as a chunk
                stdscr.nodelay(True)
                buffered_chars = [ch]
                while True:
                    next_ch = stdscr.getch()
                    if next_ch == -1:
                        break
                    buffered_chars.append(next_ch)
                stdscr.nodelay(False)

                if len(buffered_chars) > 1:
                    # Multi-character paste burst!
                    burst_str = ""
                    for bc in buffered_chars:
                        if bc in [10, 13]:
                            burst_str += "\n"
                        elif 32 <= bc <= 126 or bc == 9:
                            burst_str += chr(bc)
                    if burst_str:
                        self.insert_text_blob(burst_str)
                        continue

                # Single character input handling
                ch = buffered_chars[0]

                # Autocomplete navigation
                if self.autocomplete_list:
                    if ch in [9, curses.KEY_DOWN]:  # Tab or Down
                        self.autocomplete_idx = (self.autocomplete_idx + 1) % len(self.autocomplete_list)
                        continue
                    elif ch == curses.KEY_UP:
                        self.autocomplete_idx = (self.autocomplete_idx - 1) % len(self.autocomplete_list)
                        continue
                    elif ch in [10, 13]:  # Enter
                        self._apply_autocomplete()
                        continue
                    elif ch == 27:  # Escape
                        self.autocomplete_list = []
                        continue
                    else:
                        self.autocomplete_list = []

                # Global shortcuts
                if ch == 19:  # Ctrl+S -> Save & Run
                    return "\n".join(self.lines)
                if ch == 3:   # Ctrl+C -> Abort
                    return None

                # Mode Handling
                if self.mode == "INSERT":
                    if ch == 27:  # Escape -> Switch to NORMAL mode
                        self.mode = "NORMAL"
                        self.status_msg = "-- NORMAL MODE --"
                    elif ch in [10, 13]:  # Enter (Manual single enter typed)
                        self._save_undo()
                        cur_line = self.lines[self.cursor_y]
                        # Compute auto-indent for manual typing
                        indent = len(cur_line) - len(cur_line.lstrip(" "))
                        spaces = " " * indent
                        self.lines[self.cursor_y] = cur_line[:self.cursor_x]
                        self.lines.insert(self.cursor_y + 1, spaces + cur_line[self.cursor_x:])
                        self.cursor_y += 1
                        self.cursor_x = indent
                        self.scroll_x = 0
                    elif ch in [8, 127, curses.KEY_BACKSPACE]:  # Backspace
                        if self.cursor_x > 0:
                            self._save_undo()
                            line = self.lines[self.cursor_y]
                            self.lines[self.cursor_y] = line[:self.cursor_x - 1] + line[self.cursor_x:]
                            self.cursor_x -= 1
                        elif self.cursor_y > 0:
                            self._save_undo()
                            prev_len = len(self.lines[self.cursor_y - 1])
                            self.lines[self.cursor_y - 1] += self.lines[self.cursor_y]
                            self.lines.pop(self.cursor_y)
                            self.cursor_y -= 1
                            self.cursor_x = prev_len
                    elif ch == 9:  # Tab -> Trigger Autocomplete
                        self._trigger_autocomplete()
                    elif ch == curses.KEY_LEFT:
                        self.cursor_x = max(0, self.cursor_x - 1)
                    elif ch == curses.KEY_RIGHT:
                        self.cursor_x = min(len(self.lines[self.cursor_y]), self.cursor_x + 1)
                    elif ch == curses.KEY_UP:
                        if self.cursor_y > 0:
                            self.cursor_y -= 1
                            self.cursor_x = min(self.cursor_x, len(self.lines[self.cursor_y]))
                    elif ch == curses.KEY_DOWN:
                        if self.cursor_y < len(self.lines) - 1:
                            self.cursor_y += 1
                            self.cursor_x = min(self.cursor_x, len(self.lines[self.cursor_y]))
                    elif ch == curses.KEY_HOME:
                        self.cursor_x = 0
                    elif ch == curses.KEY_END:
                        self.cursor_x = len(self.lines[self.cursor_y])
                    else:
                        if 32 <= ch <= 126:  # Printable character
                            self._save_undo()
                            line = self.lines[self.cursor_y]
                            self.lines[self.cursor_y] = line[:self.cursor_x] + chr(ch) + line[self.cursor_x:]
                            self.cursor_x += 1
                
                elif self.mode == "NORMAL":
                    if ch in [ord('i'), ord('I')]:
                        self.mode = "INSERT"
                        self.status_msg = "-- INSERT MODE --"
                    elif ch == ord('a'):
                        self.mode = "INSERT"
                        self.cursor_x = min(self.cursor_x + 1, len(self.lines[self.cursor_y]))
                        self.status_msg = "-- INSERT MODE --"
                    elif ch == ord('o'):
                        self._save_undo()
                        self.lines.insert(self.cursor_y + 1, "")
                        self.cursor_y += 1
                        self.cursor_x = 0
                        self.scroll_x = 0
                        self.mode = "INSERT"
                        self.status_msg = "-- INSERT MODE --"
                    elif ch == ord('u'):
                        self._undo()
                    elif ch == ord('0') or ch == curses.KEY_HOME:
                        self.cursor_x = 0
                    elif ch == ord('$') or ch == curses.KEY_END:
                        self.cursor_x = len(self.lines[self.cursor_y])
                    elif ch == ord('h') or ch == curses.KEY_LEFT:
                        self.cursor_x = max(0, self.cursor_x - 1)
                    elif ch == ord('l') or ch == curses.KEY_RIGHT:
                        self.cursor_x = min(len(self.lines[self.cursor_y]), self.cursor_x + 1)
                    elif ch == ord('k') or ch == curses.KEY_UP:
                        if self.cursor_y > 0:
                            self.cursor_y -= 1
                            self.cursor_x = min(self.cursor_x, len(self.lines[self.cursor_y]))
                    elif ch == ord('j') or ch == curses.KEY_DOWN:
                        if self.cursor_y < len(self.lines) - 1:
                            self.cursor_y += 1
                            self.cursor_x = min(self.cursor_x, len(self.lines[self.cursor_y]))
                    elif ch == ord(':'):
                        # Enter command mode
                        cmd = self._prompt_command(stdscr)
                        if cmd in ["wq", "x", "w"]:
                            return "\n".join(self.lines)
                        elif cmd in ["q!", "q"]:
                            return None
                        elif cmd:
                            self.status_msg = f"Unknown command: :{cmd}"
        finally:
            # Disable bracketed paste mode when exiting editor
            sys.stdout.write("[?2004l")
            sys.stdout.flush()

    def _prompt_command(self, stdscr):
        h, w = stdscr.getmaxyx()
        cmd = ""
        while True:
            prompt = f":{cmd}"
            try:
                stdscr.addstr(h - 1, 0, prompt.ljust(w)[:w-1], curses.color_pair(5))
                stdscr.insstr(h - 1, w - 1, ' ', curses.color_pair(5))
            except Exception:
                pass
            stdscr.refresh()
            ch = stdscr.getch()
            if ch in [10, 13]:  # Enter
                return cmd
            elif ch == 27:      # Escape
                return ""
            elif ch in [8, 127, curses.KEY_BACKSPACE]:
                cmd = cmd[:-1]
            elif 32 <= ch <= 126:
                cmd += chr(ch)


def get_preferred_editor():
    """Detects user configured editor or falls back to nano / vi."""
    try:
        from config import USER_SETTINGS
        configured = USER_SETTINGS.get("external_editor", "").strip()
        if configured:
            # Check if command exists or is a path
            cmd_name = configured.split()[0]
            if shutil.which(cmd_name) or os.path.isfile(cmd_name):
                return configured
    except Exception:
        pass
    
    # Check standard Unix environment variables
    for env_var in ["EDITOR", "VISUAL"]:
        val = os.environ.get(env_var, "").strip()
        if val and shutil.which(val.split()[0]):
            return val

    # Default to nano with vi / vim fallback
    import shutil
    for cand in ["nano", "vi", "vim"]:
        if shutil.which(cand):
            return cand
    return None


def set_preferred_editor(editor_cmd):
    """Saves the user's preferred editor to ~/.silis_ui_settings.json."""
    try:
        from config import USER_SETTINGS, save_user_settings
        USER_SETTINGS["external_editor"] = editor_cmd.strip()
        save_user_settings(USER_SETTINGS)
        return True
    except Exception:
        return False


def open_terminal_editor(initial_text="", title="ASIC TCL Script"):
    """
    Spawns the user's preferred terminal editor (nano, vi, or custom configured)
    using a temporary TCL file. Returns the edited text, or None if cancelled/unchanged.
    """
    import tempfile
    import subprocess
    import shutil

    editor = get_preferred_editor()
    if not editor:
        # Fallback to LazyTclEditor if no terminal editor executable found
        return open_tui_editor(initial_text=initial_text, title=title)

    # Create temporary file with header and content
    with tempfile.NamedTemporaryFile(suffix=".tcl", mode="w", delete=False) as tf:
        temp_path = tf.name
        tf.write(initial_text)

    try:
        cmd_parts = editor.split() + [temp_path]
        ret = subprocess.run(cmd_parts)
        if ret.returncode == 0 and os.path.exists(temp_path):
            with open(temp_path, "r") as tf:
                edited_text = tf.read()
            return edited_text
        return None
    except Exception as e:
        print(f"[ERR] Failed to launch editor '{editor}': {e}")
        return open_tui_editor(initial_text=initial_text, title=title)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def open_tui_editor(initial_text="", title="ASIC TCL Script"):
    """Entry point: launches TUI editor and returns edited text, or None if cancelled."""
    try:
        editor = LazyTclEditor(initial_text=initial_text, title=title)
        return editor.run()
    except Exception as e:
        print(f"[ERR] TUI Editor error: {e}")
        return initial_text
