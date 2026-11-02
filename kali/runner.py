#!/opt/playwright-venv/bin/python
from __future__ import annotations

import hmac
import json
import os
import re
import shutil
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

MAX_BODY = 32 * 1024
MAX_JSON = 64 * 1024
TARGET_ORIGIN = "http://target:9090"
TARGET_PREFIX = "/VulnerableApp/"
SECRET_FILE = Path(os.environ.get("RUNNER_SECRET_FILE", "/run/academy-secrets/harness.key"))
HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
BLOCKED_HEADERS = {
    "host",
    "connect",
    "proxy",
    "proxy-authorization",
    "proxy-authenticate",
    "proxy-connection",
    "content-length",
    "transfer-encoding",
}
ALLOWED_METHODS = {"GET", "POST", "PUT"}
INVENTORY = {
    "curl": (["curl", "--version"], "curl"),
    "nmap": (["nmap", "--version"], "nmap"),
    "sqlmap": (["sqlmap", "--version"], "sqlmap"),
    "zaproxy": (["zaproxy", "--version"], "zaproxy"),
    "ldapsearch": (["ldapsearch", "-VV"], "ldapsearch"),
    "python3": (["python3", "--version"], "python3"),
    "chromium": (["chromium", "--version"], "chromium"),
    "firefox": (["firefox-esr", "--version"], "firefox-esr"),
    "jq": (["jq", "--version"], "jq"),
    "openssl": (["openssl", "version"], "openssl"),
    "ip": (["ip", "-Version"], "ip"),
    "nc": (["nc", "-h"], "nc"),
    "websockify": (["websockify", "--version"], "websockify"),
}


def _load_secret() -> bytes:
    try:
        value = SECRET_FILE.read_bytes().strip()
    except OSError:
        return b""
    return value


SECRET = _load_secret()


def _bad(message: str) -> ValueError:
    return ValueError(message)


def _validate_path(path: Any) -> str:
    if not isinstance(path, str) or not path.startswith(TARGET_PREFIX):
        raise _bad("path must stay under /VulnerableApp/")
    if len(path) > 2048 or any(ord(char) < 0x20 for char in path):
        raise _bad("unsafe path")
    if any(token in path for token in ("?", "#", "\\", "//", "@", "://")):
        raise _bad("path contains a forbidden URL delimiter")
    if re.search(r"%(?:2f|2F|5c|5C|3f|3F|23|40|3a|3A)", path):
        raise _bad("encoded URL delimiters are not allowed")
    parsed = urlsplit(TARGET_ORIGIN + path)
    if parsed.scheme != "http" or parsed.netloc != "target:9090" or parsed.query or parsed.fragment:
        raise _bad("invalid target URL")
    return path


def _pairs(value: Any, label: str) -> list[tuple[str, str]]:
    if value is None:
        return []
    if not isinstance(value, dict):
        raise _bad(f"{label} must be an object")
    pairs: list[tuple[str, str]] = []
    for key, item in value.items():
        if not isinstance(key, str) or not key or len(key) > 128:
            raise _bad(f"invalid {label} key")
        items = item if isinstance(item, list) else [item]
        if len(items) > 16:
            raise _bad(f"too many {label} values")
        for part in items:
            if not isinstance(part, (str, int, float, bool)):
                raise _bad(f"invalid {label} value")
            text = str(part)
            if len(text) > 16384 or (label == "headers" and any(ord(char) < 0x20 for char in text)):
                raise _bad(f"invalid {label} value")
            pairs.append((key, text))
    if len(pairs) > 64:
        raise _bad(f"too many {label} pairs")
    return pairs


def _headers(value: Any) -> list[tuple[str, str]]:
    result = []
    for key, text in _pairs(value, "headers"):
        if not HEADER_NAME.fullmatch(key) or key.lower() in BLOCKED_HEADERS or key.lower().startswith("proxy-"):
            raise _bad("forbidden header")
        if "\r" in text or "\n" in text:
            raise _bad("header contains a line break")
        result.append((key, text))
    return result


def _url(path: str, params: Any) -> str:
    pairs = _pairs(params, "params")
    suffix = urlencode(pairs, doseq=True, safe="")
    return TARGET_ORIGIN + path + (("?" + suffix) if suffix else "")


def _display_command(method: str, url: str, headers: list[tuple[str, str]], has_body: bool) -> list[str]:
    command = ["curl", "--config", "/dev/null", "--request", method, url]
    for key, _ in headers:
        command.extend(["--header", f"{key}: <redacted>"])
    if has_body:
        command.extend(["--data-binary", "<stdin>"])
    return command


def _parse_headers(raw: bytes) -> tuple[int, dict[str, str]]:
    text = raw.decode("iso-8859-1", errors="replace")[:MAX_BODY]
    blocks = re.split(r"\r?\n\r?\n", text)
    status = 0
    headers: dict[str, str] = {}
    for block in blocks:
        lines = block.splitlines()
        if not lines or not lines[0].startswith("HTTP/"):
            continue
        match = re.match(r"HTTP/\S+\s+(\d{3})", lines[0])
        if match:
            status = int(match.group(1))
        headers = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()[:4096]
    return status, headers


def _http_request(args: dict[str, Any], forced_method: str | None = None) -> dict[str, Any]:
    allowed = {"method", "path", "params", "headers", "body", "content_type"}
    unknown = set(args) - allowed
    if unknown:
        raise _bad("unsupported request field")
    if forced_method and "method" in args and args["method"] != forced_method:
        raise _bad("inspect_headers only accepts GET")
    method = forced_method or args.get("method", "GET")
    if not isinstance(method, str) or method.upper() not in ALLOWED_METHODS:
        raise _bad("method is not allowed")
    method = method.upper()
    path = _validate_path(args.get("path"))
    url = _url(path, args.get("params"))
    headers = _headers(args.get("headers"))
    body_value = args.get("body")
    if body_value is not None and not isinstance(body_value, str):
        raise _bad("body must be text")
    body = body_value.encode("utf-8") if body_value is not None else None
    if body is not None and len(body) > MAX_BODY:
        raise _bad("body exceeds 32 KiB")
    content_type = args.get("content_type")
    if content_type is not None:
        if not isinstance(content_type, str) or len(content_type) > 256 or any(char in content_type for char in "\r\n"):
            raise _bad("invalid content type")
        headers.append(("Content-Type", content_type))

    safe_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/runner",
        "LANG": "C",
        "LC_ALL": "C",
        "NO_PROXY": "*",
        "no_proxy": "*",
        "http_proxy": "",
        "https_proxy": "",
        "HTTP_PROXY": "",
        "HTTPS_PROXY": "",
    }
    with tempfile.NamedTemporaryFile(prefix="va-runner-", delete=False) as header_file:
        header_path = header_file.name
    with tempfile.NamedTemporaryFile(prefix="va-runner-body-", delete=False) as body_file:
        body_path = body_file.name
    try:
        command = [
            "curl",
            "--config",
            "/dev/null",
            "--silent",
            "--show-error",
            "--max-time",
            "10",
            "--connect-timeout",
            "5",
            "--max-filesize",
            str(MAX_BODY),
            "--proto",
            "=http",
            "--noproxy",
            "*",
            "--no-keepalive",
            "--request",
            method,
            "--dump-header",
            header_path,
            "--output",
            body_path,
            "--write-out",
            "%{http_code}",
        ]
        for key, value in headers:
            command.extend(["--header", f"{key}: {value}"])
        if body is not None:
            command.extend(["--data-binary", "@-"])
        command.append(url)
        try:
            completed = subprocess.run(
                command,
                input=body,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=safe_env,
                shell=False,
                timeout=15,
                check=False,
            )
            exit_code = int(completed.returncode)
            curl_status = completed.stdout.decode("ascii", errors="ignore").strip()[:3]
            stderr = completed.stderr.decode("utf-8", errors="replace")[:1024]
        except subprocess.TimeoutExpired:
            exit_code = 124
            curl_status = ""
            stderr = "request timeout"
        try:
            raw_headers = Path(header_path).read_bytes()[:MAX_BODY]
        except OSError:
            raw_headers = b""
        status, response_headers = _parse_headers(raw_headers)
        if not status and curl_status.isdigit():
            status = int(curl_status)
        try:
            raw_body = Path(body_path).read_bytes()[: MAX_BODY + 1]
        except OSError:
            raw_body = b""
        truncated = len(raw_body) > MAX_BODY
        if truncated:
            raw_body = raw_body[:MAX_BODY]
        body_text = raw_body.decode("utf-8", errors="replace")
        if not body_text and exit_code != 0 and stderr:
            body_text = stderr
        return {
            "status": status,
            "headers": response_headers,
            "body": body_text,
            "command": _display_command(method, url, headers, body is not None),
            "exit_code": exit_code,
            **({"truncated": True} if truncated else {}),
        }
    finally:
        try:
            os.unlink(header_path)
        except OSError:
            pass
        try:
            os.unlink(body_path)
        except OSError:
            pass


def _browser_probe(args: dict[str, Any]) -> dict[str, Any]:
    if set(args) - {"path", "params"}:
        raise _bad("browser_probe accepts only path and params")
    path = _validate_path(args.get("path"))
    url = _url(path, args.get("params"))
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {
            "status": 0,
            "headers": {},
            "body": "Playwright is unavailable",
            "browser_dataset": {"vaLab": ""},
            "command": ["playwright", "chromium", url],
            "exit_code": 127,
        }

    result: dict[str, Any] = {
        "status": 0,
        "headers": {},
        "body": "",
        "browser_dataset": {"vaLab": ""},
        "command": ["playwright", "chromium", url],
        "exit_code": 1,
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context()
        page = context.new_page()

        def allow_only_target(route: Any, request: Any) -> None:
            parsed = urlsplit(request.url)
            allowed = (
                parsed.scheme == "data"
                or (
                    parsed.scheme == "http"
                    and parsed.hostname == "target"
                    and parsed.port == 9090
                    and parsed.path.startswith(TARGET_PREFIX)
                )
            )
            if allowed:
                route.continue_()
            else:
                route.abort()

        page.route("**/*", allow_only_target)
        response = None
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(1000)
            if response is not None:
                result["status"] = response.status
                result["headers"] = {key: value[:4096] for key, value in response.all_headers().items()}
            dataset = page.evaluate("document.body ? (document.body.dataset.vaLab || '') : ''")
            result["browser_dataset"] = {"vaLab": str(dataset)[:4096]}
            result["body"] = page.content()[:MAX_BODY]
            result["exit_code"] = 0 if result["status"] else 1
        except Exception:
            result["body"] = "browser navigation failed"
        finally:
            context.close()
            browser.close()
    return result


def _inventory(args: dict[str, Any]) -> dict[str, Any]:
    names = args.get("commands") if args else None
    if names is None:
        names = list(INVENTORY)
    if not isinstance(names, list) or any(name not in INVENTORY for name in names):
        raise _bad("inventory command is not allowlisted")
    items = []
    for name in names:
        command, binary = INVENTORY[name]
        path = shutil.which(binary)
        if not path:
            items.append({"name": name, "available": False, "version": "not installed"})
            continue
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=5, shell=False, check=False)
            output = (completed.stdout or completed.stderr).strip().replace("\n", " ")[:512]
            items.append({"name": name, "available": True, "version": output, "exit_code": completed.returncode})
        except Exception:
            items.append({"name": name, "available": True, "version": "version check failed"})
    return {"status": 200, "headers": {}, "body": json.dumps(items), "command": ["inventory"], "exit_code": 0}


def dispatch(tool: Any, args: Any) -> dict[str, Any]:
    if not isinstance(tool, str) or not isinstance(args, dict):
        raise _bad("tool and args are required")
    if tool == "http_request":
        return _http_request(args)
    if tool == "inspect_headers":
        return _http_request(args, forced_method="GET")
    if tool == "browser_probe":
        return _browser_probe(args)
    if tool == "inventory":
        return _inventory(args)
    raise _bad("unknown tool")


class RunnerHandler(BaseHTTPRequestHandler):
    server_version = "VA-Lab-Runner/1.0"

    def _json(self, status: int, value: dict[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "").encode("utf-8")
        expected = b"Bearer " + SECRET
        return bool(SECRET) and hmac.compare_digest(supplied, expected)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"status": "ok", "service": "runner"})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path not in {"/run", "/tools/run"}:
            self._json(404, {"error": "not found"})
            return
        if not self._authorized():
            self._json(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_JSON:
                raise _bad("invalid request size")
            payload = json.loads(self.rfile.read(length))
            tool = payload.get("tool")
            args = payload.get("arguments", payload.get("args", {}))
            result = dispatch(tool, args)
            self._json(200, result)
        except ValueError as exc:
            self._json(400, {"error": str(exc)[:256]})
        except Exception:
            self._json(500, {"error": "tool execution failed"})

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    bind, _, port_text = os.environ.get("RUNNER_BIND", "0.0.0.0:9001").rpartition(":")
    server = ThreadingHTTPServer((bind or "0.0.0.0", int(port_text or "9001")), RunnerHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
