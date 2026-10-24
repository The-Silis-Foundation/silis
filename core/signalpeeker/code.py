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
    """
    def __init__(self, ide):
        super().__init__()
        self.ide = ide
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # ROHD Wave Viewer Web Container (fills 100% viewport)
        self.web_container = QWidget(self)
        web_container_layout = QVBoxLayout(self.web_container)
        web_container_layout.setContentsMargins(0, 0, 0, 0)
        web_container_layout.setSpacing(0)
        self.layout.addWidget(self.web_container)

        self.current_vcd_path = None
        self._server = LocalWaveServer.get_instance()
        self._is_initialized = False

        # Register bridge handler for saveSignalList, loadSignalList, savePng, etc.
        web_mgr = SharedWebEngineManager.get_instance()
        web_mgr.add_console_handler(self._on_bridge_message)

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

        self.ensure_viewer()
        self._send_vcd_to_webview(self.current_vcd_path)

    def _send_vcd_to_webview(self, path):
        web_mgr = SharedWebEngineManager.get_instance()
        view = web_mgr.get_view()
        if view and os.path.isfile(path):
            try:
                base_name = os.path.basename(path)
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                escaped_content = json.dumps(content)
                escaped_name = json.dumps(base_name)
                js_code = f"window.loadVcdContent({escaped_content}, {escaped_name});"
                view.page().runJavaScript(js_code)
            except Exception as e:
                print(f"[SILIS] Failed to load VCD into ROHD: {e}")
