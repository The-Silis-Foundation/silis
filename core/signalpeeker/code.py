"""
signalpeeker/code.py
Interactive Waveform Viewer powered by the Intel ROHD Wave Viewer UI
and the shared WebEngine architecture.
"""
import os
import glob
import json
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QMessageBox
)
from PyQt6.QtCore import QUrl
from gui_shared_webengine import SharedWebEngineManager
from signalpeeker.server import LocalWaveServer


class SignalPeeker(QWidget):
    """
    Full-featured waveform viewer providing 100% of the Intel ROHD Wave Viewer UI
    (hierarchy browser, signal grouping, time ruler, bus inspection, transition jumps,
    and save/load signal list) within Silis through a single shared hardware-accelerated QWebEngineView.
    Includes a vertical side-strip on the far right holding essential waveform controls.
    """
    def __init__(self, ide):
        super().__init__()
        self.ide = ide
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # ROHD Wave Viewer Web Container (fills viewport)
        self.web_container = QWidget(self)
        web_container_layout = QVBoxLayout(self.web_container)
        web_container_layout.setContentsMargins(0, 0, 0, 0)
        web_container_layout.setSpacing(0)
        self.main_layout.addWidget(self.web_container, stretch=1)

        # Vertical Action Strip on the rightmost edge
        from PyQt6.QtWidgets import QToolBar, QPushButton, QMenu
        from PyQt6.QtGui import QAction

        self.strip = QWidget(self)
        self.strip.setFixedWidth(30)
        self.strip.setStyleSheet("background: #181825; border-left: 1px solid #313244;")
        strip_lay = QVBoxLayout(self.strip)
        strip_lay.setContentsMargins(2, 4, 2, 4)
        strip_lay.setSpacing(4)

        btn_style = """
            QPushButton {
                background: transparent;
                color: #cdd6f4;
                border: none;
                border-radius: 3px;
                font-size: 13px;
                height: 24px;
            }
            QPushButton:hover {
                background: #313244;
                color: #89b4fa;
            }
        """

        # 1. Reload waveform
        self.btn_reload = QPushButton("↻", self.strip)
        self.btn_reload.setToolTip("Reload waveform from disk")
        self.btn_reload.setStyleSheet(btn_style)
        self.btn_reload.clicked.connect(self.auto_load)
        strip_lay.addWidget(self.btn_reload)

        # 2. Zoom Controls: Zoom In (+), Zoom Out (-), Zoom to Fit (<->)
        self.btn_zoom_in = QPushButton("+", self.strip)
        self.btn_zoom_in.setToolTip("Zoom in timeline")
        self.btn_zoom_in.setStyleSheet(btn_style)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        strip_lay.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QPushButton("-", self.strip)
        self.btn_zoom_out.setToolTip("Zoom out timeline")
        self.btn_zoom_out.setStyleSheet(btn_style)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        strip_lay.addWidget(self.btn_zoom_out)

        self.btn_fit = QPushButton("↔", self.strip)
        self.btn_fit.setToolTip("Zoom to fit all transitions")
        self.btn_fit.setStyleSheet(btn_style)
        self.btn_fit.clicked.connect(self._trigger_zoom_fit)
        strip_lay.addWidget(self.btn_fit)

        # 3. Save Signal List
        self.btn_save_signals = QPushButton("💾", self.strip)
        self.btn_save_signals.setToolTip("Save Signal List (.json)")
        self.btn_save_signals.setStyleSheet(btn_style)
        self.btn_save_signals.clicked.connect(self._trigger_save_signals)
        strip_lay.addWidget(self.btn_save_signals)

        # 4. Load Signal List
        self.btn_load_signals = QPushButton("📂", self.strip)
        self.btn_load_signals.setToolTip("Load Signal List (.json)")
        self.btn_load_signals.setStyleSheet(btn_style)
        self.btn_load_signals.clicked.connect(self._trigger_load_signals)
        strip_lay.addWidget(self.btn_load_signals)

        # 5. Export PNG Snapshot
        self.btn_export_png = QPushButton("📷", self.strip)
        self.btn_export_png.setToolTip("Export Waveform Snapshot (PNG)")
        self.btn_export_png.setStyleSheet(btn_style)
        self.btn_export_png.clicked.connect(self._trigger_export_png)
        strip_lay.addWidget(self.btn_export_png)

        strip_lay.addStretch()
        self.main_layout.addWidget(self.strip)

        self.current_vcd_path = None
        self._server = LocalWaveServer.get_instance()
        self._is_initialized = False

        # Register bridge handler for saveSignalList, loadSignalList, savePng, etc.
        web_mgr = SharedWebEngineManager.get_instance()
        web_mgr.add_console_handler(self._on_bridge_message)

    def zoom_in(self):
        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.get_view()
        if view:
            view.page().runJavaScript("if (typeof window.zoomInWaveform === 'function') { window.zoomInWaveform(); } else { window.dispatchEvent(new KeyboardEvent('keydown', {'key': '+', 'code': 'Equal', 'bubbles': true})); }")

    def zoom_out(self):
        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.get_view()
        if view:
            view.page().runJavaScript("if (typeof window.zoomOutWaveform === 'function') { window.zoomOutWaveform(); } else { window.dispatchEvent(new KeyboardEvent('keydown', {'key': '-', 'code': 'Minus', 'bubbles': true})); }")

    def _trigger_zoom_fit(self):
        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.get_view()
        if view:
            # ROHD keyboard shortcut for fit is 'f'
            view.page().runJavaScript("window.dispatchEvent(new KeyboardEvent('keydown', {'key': 'f'}));")

    def _trigger_save_signals(self):
        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.get_view()
        if view:
            self._on_bridge_message("SILIS_ROHD_MSG:{\"type\":\"saveSignalList\",\"content\":\"[]\"}")

    def _trigger_load_signals(self):
        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.get_view()
        if view:
            self._on_bridge_message("SILIS_ROHD_MSG:{\"type\":\"loadSignalList\"}")

    def _trigger_export_png(self):
        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.get_view()
        if view:
            view.page().runJavaScript("if (window.rohdEmbed) { window.rohdEmbed.postMessage({ type: 'savePng' }); }")

    def showEvent(self, event):
        super().showEvent(event)
        self.ensure_viewer()

    def ensure_viewer(self):
        if self._is_initialized:
            return

        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.attach_to(self.web_container, "rohd_wave_viewer")
        if view:
            url = self._server.get_url()
            if url:
                view.setUrl(QUrl(url))
                self._is_initialized = True
                # If a waveform was loaded prior to page readiness, push it on loadFinished
                view.loadFinished.connect(self._on_page_loaded)

    def _on_page_loaded(self, ok):
        if ok and self.current_vcd_path and os.path.isfile(self.current_vcd_path):
            self._send_vcd_to_webview(self.current_vcd_path)

    def _on_bridge_message(self, message):
        """
        Receives messages posted by rohdEmbed in the webview via console.log('SILIS_ROHD_MSG:...').
        Handles saving and loading signal list files and saving PNGs via native Qt dialogs.
        """
        if not message.startswith("SILIS_ROHD_MSG:"):
            return

        raw_json = message[len("SILIS_ROHD_MSG:"):]
        try:
            msg = json.loads(raw_json)
        except Exception as e:
            print(f"[SILIS ROHD Bridge] JSON parse error: {e}")
            return

        msg_type = msg.get("type")
        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.get_view()

        # 1. Save Signal List
        if msg_type == "saveSignalList":
            content = msg.get("content", "")
            suggested = msg.get("fileName", "signals.json")
            default_dir = os.path.dirname(self.current_vcd_path) if self.current_vcd_path else getattr(self.ide, "cwd", os.getcwd())
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Save Signal List", os.path.join(default_dir, suggested), "JSON Files (*.json);;All Files (*)"
            )
            if save_path:
                try:
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    if view:
                        resp = {"type": "saveSignalListResult", "success": True}
                        view.page().runJavaScript(f"window.deliverRohdResponse({json.dumps(resp)});")
                    if hasattr(self.ide, "log_system"):
                        self.ide.log_system(f"Signal list saved: {os.path.basename(save_path)}")
                except Exception as e:
                    if view:
                        resp = {"type": "saveSignalListResult", "success": False, "error": str(e)}
                        view.page().runJavaScript(f"window.deliverRohdResponse({json.dumps(resp)});")
            else:
                if view:
                    resp = {"type": "saveSignalListResult", "success": False, "cancelled": True}
                    view.page().runJavaScript(f"window.deliverRohdResponse({json.dumps(resp)});")

        # 2. Load Signal List
        elif msg_type == "loadSignalList":
            default_dir = os.path.dirname(self.current_vcd_path) if self.current_vcd_path else getattr(self.ide, "cwd", os.getcwd())
            open_path, _ = QFileDialog.getOpenFileName(
                self, "Load Signal List", default_dir, "JSON Files (*.json);;All Files (*)"
            )
            if open_path and os.path.isfile(open_path):
                try:
                    with open(open_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if view:
                        resp = {"type": "loadSignalListResult", "success": True, "content": content}
                        view.page().runJavaScript(f"window.deliverRohdResponse({json.dumps(resp)});")
                    if hasattr(self.ide, "log_system"):
                        self.ide.log_system(f"Signal list loaded: {os.path.basename(open_path)}")
                except Exception as e:
                    if view:
                        resp = {"type": "loadSignalListResult", "success": False, "error": str(e)}
                        view.page().runJavaScript(f"window.deliverRohdResponse({json.dumps(resp)});")
            else:
                if view:
                    resp = {"type": "loadSignalListResult", "success": False, "cancelled": True}
                    view.page().runJavaScript(f"window.deliverRohdResponse({json.dumps(resp)});")

        # 3. Save PNG Snapshot
        elif msg_type == "savePng":
            import base64
            b64_data = msg.get("data", "")
            suggested = msg.get("suggestedName", "waveform.png")
            default_dir = os.path.dirname(self.current_vcd_path) if self.current_vcd_path else getattr(self.ide, "cwd", os.getcwd())
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Save Waveform Snapshot", os.path.join(default_dir, suggested), "PNG Images (*.png);;All Files (*)"
            )
            if save_path and b64_data:
                try:
                    png_bytes = base64.b64decode(b64_data)
                    with open(save_path, "wb") as f:
                        f.write(png_bytes)
                    if view:
                        resp = {"type": "savePngResult", "success": True, "path": save_path}
                        view.page().runJavaScript(f"window.deliverRohdResponse({json.dumps(resp)});")
                except Exception as e:
                    if view:
                        resp = {"type": "savePngResult", "success": False, "error": str(e)}
                        view.page().runJavaScript(f"window.deliverRohdResponse({json.dumps(resp)});")
            else:
                if view:
                    resp = {"type": "savePngResult", "success": False, "error": "Cancelled"}
                    view.page().runJavaScript(f"window.deliverRohdResponse({json.dumps(resp)});")

        # 4. Request Reload
        elif msg_type == "requestReload":
            if self.current_vcd_path and os.path.isfile(self.current_vcd_path):
                self._send_vcd_to_webview(self.current_vcd_path)
            else:
                self.auto_load()

        # 5. Open Waveform File (Triggered via Ctrl+O or header)
        elif msg_type == "openWaveformFile":
            self.manual_load()

        # 6. Ping / Extension Handshake
        elif msg_type == "ping":
            if view:
                req_id = msg.get("requestId")
                resp = {"type": "pingResponse", "available": True}
                if req_id:
                    resp["requestId"] = req_id
                view.page().runJavaScript(f"window.deliverRohdResponse({json.dumps(resp)});")

        # 7. Request Repaint
        elif msg_type == "requestRepaint":
            if view:
                resp = {"type": "repaintAck", "timestamp": int(os.times().elapsed * 1000)}
                view.page().runJavaScript(f"window.deliverRohdResponse({json.dumps(resp)});")

        # 8. Cursor Moved - Live schematic wire value lighting
        elif msg_type == "cursorMoved":
            time_ps = msg.get("time")
            if time_ps is not None and getattr(self, "_vcd_tracker", None):
                updates_dict = self._vcd_tracker.get_all_values_at_ps(time_ps)
                if updates_dict:
                    # Format as expected by digitaljs/sv-pathfinder: [{ "name": "wire", "values": ["1"] }]
                    updates_list = [{"name": k, "values": [v]} for k, v in updates_dict.items()]
                    if hasattr(self.ide, "tab_compile") and hasattr(self.ide.tab_compile, "schem_view"):
                        schem_view = self.ide.tab_compile.schem_view
                        if hasattr(schem_view, "set_wire_values"):
                            schem_view.set_wire_values(updates_list)
                        elif hasattr(schem_view, "view") and hasattr(schem_view.view, "set_wire_values"):
                            schem_view.view.set_wire_values(updates_list)
                    # Forward wire values to Monaco Editor for live signal value hover inspection
                    if hasattr(self.ide, "tab_compile") and hasattr(self.ide.tab_compile, "editor"):
                        ed_tabs = self.ide.tab_compile.editor
                        if hasattr(ed_tabs, "set_hover_signal_values"):
                            ed_tabs.set_hover_signal_values(updates_dict)

        # 9. Jump to Assertion from Timeline Flag Marker
        elif msg_type == "jumpToAssertion":
            file_path = msg.get("file")
            line = msg.get("line")
            time_ps = msg.get("time_ps")
            
            # Synchronize cursor and light up wires at assertion timestamp
            if time_ps is not None and getattr(self, "_vcd_tracker", None):
                updates_dict = self._vcd_tracker.get_all_values_at_ps(time_ps)
                if updates_dict:
                    updates_list = [{"name": k, "values": [v]} for k, v in updates_dict.items()]
                    if hasattr(self.ide, "tab_compile") and hasattr(self.ide.tab_compile, "schem_view"):
                        schem_view = self.ide.tab_compile.schem_view
                        if hasattr(schem_view, "set_wire_values"):
                            schem_view.set_wire_values(updates_list)
                        elif hasattr(schem_view, "view") and hasattr(schem_view.view, "set_wire_values"):
                            schem_view.view.set_wire_values(updates_list)
                    if hasattr(self.ide, "tab_compile") and hasattr(self.ide.tab_compile, "editor"):
                        ed_tabs = self.ide.tab_compile.editor
                        if hasattr(ed_tabs, "set_hover_signal_values"):
                            ed_tabs.set_hover_signal_values(updates_dict)

            if file_path and line and hasattr(self.ide, "open_file_in_editor"):
                # Resolve relative path if needed
                abs_path = file_path
                if not os.path.isabs(abs_path):
                    cand = os.path.join(getattr(self.ide, "cwd", os.getcwd()), file_path)
                    if os.path.exists(cand): abs_path = cand
                    else:
                        cand2 = os.path.join(getattr(self.ide, "cwd", os.getcwd()), "source", os.path.basename(file_path))
                        if os.path.exists(cand2): abs_path = cand2
                self.ide.open_file_in_editor(abs_path, int(line), 1)

    def manual_load(self):
        start_dir = getattr(self.ide, "cwd", os.getcwd())
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Waveform (VCD / FST)", start_dir, "Waveforms (*.vcd *.fst *.ghw);;All Files (*)"
        )
        if path:
            self.load_file(path)

    def auto_load(self):
        cwd = getattr(self.ide, "cwd", os.getcwd())
        candidates = glob.glob(os.path.join(cwd, "*.vcd")) + glob.glob(os.path.join(cwd, "*.fst"))
        parent_dir = os.path.dirname(cwd)
        candidates += glob.glob(os.path.join(parent_dir, "*.vcd")) + glob.glob(os.path.join(parent_dir, "*.fst"))
        if candidates:
            self.load_file(max(candidates, key=os.path.getctime))

    def load_file(self, path):
        self.current_vcd_path = os.path.abspath(path)
        base_name = os.path.basename(self.current_vcd_path)
        if hasattr(self.ide, "log_system"):
            self.ide.log_system(f"Loading Waves: {base_name}")

        # Index VCD for timeline scrubbing and live schematic wire animations
        try:
            from signalpeeker.vcd_tracker import FastVcdTracker
            self._vcd_tracker = FastVcdTracker(self.current_vcd_path)
        except Exception as e:
            print(f"[SILIS] Could not initialize VCD tracker: {e}")
            self._vcd_tracker = None

        self.ensure_viewer()
        self._send_vcd_to_webview(self.current_vcd_path)

    def _send_vcd_to_webview(self, path):
        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.get_view()
        if view and os.path.isfile(path):
            try:
                base_name = os.path.basename(path)
                if path.lower().endswith(".fst"):
                    # Binary FST waveform: load raw bytes
                    with open(path, "rb") as f:
                        raw_bytes = list(f.read())
                    js_code = f"""
                    if (typeof window.loadWaveBytes === 'function') {{
                        window.loadWaveBytes({raw_bytes}, {json.dumps(base_name)});
                    }} else {{
                        window.deliverRohdResponse({{
                            type: 'vcdBytes',
                            bytes: {raw_bytes},
                            uri: {json.dumps(base_name)}
                        }});
                    }}
                    """
                else:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    escaped_content = json.dumps(content)
                    escaped_name = json.dumps(base_name)
                    js_code = f"""
                    if (typeof window.loadVcdContent === 'function') {{
                        window.loadVcdContent({escaped_content}, {escaped_name});
                    }} else {{
                        window.__pendingVcd = {{ text: {escaped_content}, fileName: {escaped_name} }};
                    }}
                    """
                view.page().runJavaScript(js_code)
            except Exception as e:
                print(f"[SILIS] Failed to load waveform into ROHD: {e}")

    def add_signal_by_name(self, signal_name):
        """
        Injects a signal into ROHD Wave Viewer display list by name without
        requiring the user to browse through the tree.
        """
        if not signal_name:
            return
        target = str(signal_name).strip()
        # Clean bus index suffixes like C[0] -> C
        target_clean = target.split('[')[0].strip()
        
        # Find exact or matching hierarchical path in vcd_tracker if available
        matched_path = target_clean
        if getattr(self, "_vcd_tracker", None) and hasattr(self._vcd_tracker, "var_aliases"):
            # 1. Exact match on short name first
            found = False
            for sym, aliases in self._vcd_tracker.var_aliases.items():
                for full, short, _ in aliases:
                    if short == target_clean:
                        matched_path = full
                        found = True
                        break
                if found: break
                
            # 2. Case-insensitive or suffix match
            if not found:
                target_lower = target_clean.lower()
                for sym, aliases in self._vcd_tracker.var_aliases.items():
                    for full, short, _ in aliases:
                        if short.lower() == target_lower or full.lower().endswith('.' + target_lower):
                            matched_path = full
                            found = True
                            break
                    if found: break
        
        # Build a valid ROHD signal session payload with both 'id' and 'name'
        payload = {
            "version": 6,
            "signals": [
                {
                    "id": matched_path,
                    "name": matched_path,
                    "radix": "hex"
                }
            ],
            "session": {}
        }
        
        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.get_view()
        if view:
            js = f"""
            (function() {{
                if (typeof window.addRohdSignal === 'function') {{
                    window.addRohdSignal({json.dumps(matched_path)});
                }} else {{
                    var resp = {{
                        type: 'loadSignalListResult',
                        success: true,
                        content: {json.dumps(json.dumps(payload))}
                    }};
                    if (typeof window.deliverRohdResponse === 'function') {{
                        window.deliverRohdResponse(resp);
                    }}
                }}
            }})();
            """
            view.page().runJavaScript(js)

    def set_assertion_markers(self, markers):
        """Pushes assertion failure & warning flags to the timeline ruler."""
        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.get_view()
        if view:
            js = f"if (typeof window.setTimelineMarkers === 'function') {{ window.setTimelineMarkers({json.dumps(markers)}); }}"
            view.page().runJavaScript(js)
