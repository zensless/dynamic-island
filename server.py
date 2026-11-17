"""Server HTTP lokal (127.0.0.1) untuk menerima notifikasi dari skrip/program lain.

Kirim:  POST http://127.0.0.1:8765/notify   header "X-Island: 1"
        body JSON: {"app": "...", "title": "...", "body": "...", "url": "https://..."}
Atau pakai kirim_notif.py.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtCore import QObject, Signal


class NotifyHub(QObject):
    received = Signal(dict)

    def __init__(self, port: int):
        super().__init__()
        self.port = port
        self._srv = None

    def start(self) -> bool:
        hub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._send(200, {"ok": True, "app": "DynamicIsland"})

            def do_POST(self):
                # header kustom memblokir POST dari halaman web (butuh preflight CORS)
                if self.path != "/notify" or self.headers.get("X-Island") != "1":
                    return self._send(403, {"ok": False})
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                    data = json.loads(self.rfile.read(min(n, 65536)) or b"{}")
                except Exception:
                    return self._send(400, {"ok": False})
                hub.received.emit({k: str(data.get(k, ""))[:300] for k in ("app", "title", "body", "url")})
                self._send(200, {"ok": True})

        try:
            self._srv = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        except OSError:
            return False
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return True
