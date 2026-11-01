#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

MAX_BODY = 32 * 1024
DATA_FILE = Path(os.environ.get("RECEIVER_DATA", "/data/requests.jsonl"))
_write_lock = threading.Lock()


def record(item: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        with DATA_FILE.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")


class ReceiverHandler(BaseHTTPRequestHandler):
    server_version = "VA-Lab-Receiver/1.0"

    def _safe_path(self) -> str | None:
        path = urlsplit(self.path).path
        if not path or len(path) > 2048 or any(ord(char) < 0x20 for char in path):
            return None
        if ".." in path.split("/"):
            return None
        return path

    def _send(self, status: int, payload: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _handle(self) -> None:
        path = self._safe_path()
        if path is None:
            self._send(400, b"unsafe path\n")
            return
        length = min(int(self.headers.get("Content-Length", "0") or "0"), MAX_BODY)
        body = self.rfile.read(length) if length else b""
        record(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "method": self.command,
                "path": self.path,
                "headers": {key: value for key, value in self.headers.items()},
                "body": body.decode("utf-8", errors="replace"),
            }
        )
        if path == "/health":
            self._send(200, b'{"status":"ok","service":"receiver"}\n', "application/json")
            return
        self._send(200, f"VA_LAB_RECEIVER\npath={path}\nmethod={self.command}\n".encode())

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_DELETE = _handle

    def log_message(self, format: str, *args: object) -> None:
        # Keep request records in the data volume; do not duplicate headers in logs.
        return


def main() -> None:
    bind = os.environ.get("RECEIVER_BIND", "0.0.0.0")
    port = int(os.environ.get("RECEIVER_PORT", "8081"))
    server = ThreadingHTTPServer((bind, port), ReceiverHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
