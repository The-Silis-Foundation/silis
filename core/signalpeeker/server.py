import os
import threading
import http.server
import socketserver
from functools import partial


class LocalWaveServer:
    """
    Lightweight, reproducible local loopback HTTP server bound strictly to 127.0.0.1
    on an OS-assigned ephemeral port. Serves the full Intel ROHD Wave Viewer WebAssembly
    and Flutter CanvasKit bundle to Qt QWebEngineView with exact MIME types and zero
    external network dependencies.
    """
    _instance = None
    _server = None
    _thread = None
    _port = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = LocalWaveServer()
        return cls._instance

    def __init__(self):
        self.web_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "web", "rohd")
        )

    def start(self):
        if self._server is not None:
            return self._port

        if not os.path.exists(self.web_dir):
            return None

        class WaveHttpHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, directory=None, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)

            def end_headers(self):
                # Ensure WASM and multi-threading headers are compatible
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cross-Origin-Opener-Policy", "same-origin")
                self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
                super().end_headers()

            def guess_type(self, path):
                if path.endswith(".wasm"):
                    return "application/wasm"
                if path.endswith(".js") or path.endswith(".mjs"):
                    return "application/javascript"
                return super().guess_type(path)

            def log_message(self, format, *args):
                # Silent logging to prevent stdout noise
                pass

        handler = partial(WaveHttpHandler, directory=self.web_dir)
        try:
            self._server = socketserver.TCPServer(("127.0.0.1", 0), handler)
            self._port = self._server.server_address[1]
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            return self._port
        except Exception as e:
            print(f"[SILIS] LocalWaveServer failed to bind: {e}")
            return None

    def get_url(self):
        port = self.start()
        if port:
            return f"http://127.0.0.1:{port}/index.html"
        return None
