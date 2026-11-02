#!/usr/bin/env python3
"""End-to-end checks for the closed Kali harness tools.

This file is intentionally self-contained: it uses only the Python standard
library, talks to Academy through its internal service name, and invokes the
real ``lab-harness-tools`` executable.  It is meant to run as uid 1000 inside
Kali, not on the Compose host.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import pwd
import secrets
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


API_ROOT = "http://academy:8000"
HELPER = "/usr/local/bin/lab-harness-tools"
LAB_CLIENT = "/usr/local/bin/lab"
CATALOG = "/opt/academy-harness/catalog.json"
REPORT = "/tmp/harness-tools-e2e.json"
HELPER_TIMEOUT = 90
API_TIMEOUT = 30
MISSING = object()

SERVICE_PORTS = {
    "target": 9090,
    "receiver": 8081,
    "mailpit": 8025,
    "academy": 8000,
    "ollama": 11434,
}

# Credentials are kept only in memory, and every report/progress path below
# excludes these values.  The redactor is a last-resort guard for a future
# helper/API response accidentally echoing one of them.
SENSITIVE: list[str] = []
RESULTS: list[dict[str, Any]] = []
LAST_TOOL_RESULT: dict[str, Any] | None = None


class SkipTest(Exception):
    pass


class CheckFailure(Exception):
    def __init__(self, code: str = "assertion_failed") -> None:
        super().__init__(code)
        self.code = code


def progress(message: str) -> None:
    print(f"[harness-tools-e2e] {message}", flush=True)


def check(condition: Any) -> None:
    if not condition:
        raise CheckFailure("assertion_failed")


def redact(value: Any) -> Any:
    """Remove ephemeral account material without changing ordinary evidence."""

    if isinstance(value, dict):
        return {str(key): redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        result = value
        for secret in SENSITIVE:
            if secret:
                result = result.replace(secret, "<redacted>")
        return result
    return value


def load_catalog() -> dict[str, Any]:
    try:
        with open(CATALOG, "r", encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, UnicodeError, ValueError) as exc:
        raise CheckFailure("catalog_unavailable") from exc
    check(isinstance(value, dict) and isinstance(value.get("missions"), list))
    return value


def mission(catalog: dict[str, Any], mission_id: str) -> dict[str, Any]:
    for item in catalog["missions"]:
        if isinstance(item, dict) and item.get("id") == mission_id:
            return item
    raise CheckFailure("mission_missing")


def mission_has_method(item: dict[str, Any], method: str) -> bool:
    raw = item.get("method")
    values = raw if isinstance(raw, list) else [raw]
    for value in values:
        if isinstance(value, str) and method in value.upper().split():
            return True
    return False


def api_json(method: str, path: str, payload: Any = None, token: str | None = None) -> tuple[int, Any]:
    """Make a fixed internal Academy request without inheriting proxies."""

    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    request = Request(API_ROOT + path, data=data, headers=headers, method=method)
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=API_TIMEOUT) as response:
            raw = response.read(2 * 1024 * 1024)
            code = int(response.status)
    except HTTPError as exc:
        # Do not return or print an error body: it is not needed for this
        # harness and could echo a future credential-bearing diagnostic.
        try:
            exc.read(128 * 1024)
        except OSError:
            pass
        return int(exc.code), None
    except (OSError, URLError, TimeoutError) as exc:
        raise CheckFailure("academy_unavailable") from exc
    try:
        return code, json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return code, None


def create_account() -> dict[str, str]:
    # Neither username nor password is ever printed or put into the report.
    username = "va_e2e_" + secrets.token_hex(10)
    password = secrets.token_urlsafe(24)
    SENSITIVE.extend((username, password))
    code, value = api_json(
        "POST",
        "/api/auth/register",
        {"username": username, "password": password},
    )
    check(code == 200 and isinstance(value, dict))
    token = value.get("token")
    check(isinstance(token, str) and bool(token))
    SENSITIVE.append(token)
    return {"username": username, "token": token}


def save_session(account: dict[str, str]) -> dict[str, Any]:
    """Use the installed lab client's _save_session exactly as the harness does."""

    loader = importlib.machinery.SourceFileLoader("va_lab_e2e_session", LAB_CLIENT)
    spec = importlib.util.spec_from_file_location("va_lab_e2e_session", LAB_CLIENT, loader=loader)
    check(spec is not None and spec.loader is not None)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    save = getattr(module, "_save_session", None)
    check(callable(save))
    save({"token": account["token"], "username": account["username"]})

    try:
        home = Path(pwd.getpwuid(1000).pw_dir)
    except KeyError as exc:
        raise CheckFailure("uid1000_missing") from exc
    session_path = home / ".config" / "va-lab" / "session.json"
    info = session_path.stat()
    check(stat.S_ISREG(info.st_mode))
    check(info.st_uid == 1000)
    check((info.st_mode & 0o077) == 0)
    return {"uid": info.st_uid, "mode": oct(stat.S_IMODE(info.st_mode))}


def invoke_helper(action: str, payload: Any) -> dict[str, Any]:
    """Invoke the actual helper with JSON stdin, shell disabled, and 90s cap."""

    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    global LAST_TOOL_RESULT
    try:
        completed = subprocess.run(
            [HELPER, action],
            input=encoded,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=HELPER_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CheckFailure("helper_timeout") from exc
    except OSError as exc:
        raise CheckFailure("helper_unavailable") from exc

    raw = completed.stdout.strip()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise CheckFailure("helper_invalid_json") from exc
    check(isinstance(value, dict))
    # Keep the exact parsed helper envelope in the report, while never storing
    # stderr (which is operational noise and could contain an accidental echo).
    result = {"returncode": completed.returncode, "tool": value}
    LAST_TOOL_RESULT = result
    return result


def expect_rejected(action: str, payload: Any) -> dict[str, Any]:
    result = invoke_helper(action, payload)
    tool = result["tool"]
    check(result["returncode"] != 0)
    check(tool.get("action") == action)
    check(tool.get("ok") is False)
    check(isinstance(tool.get("error"), str) and bool(tool["error"]))
    return result


def body_as_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def body_field(value: Any, name: str) -> Any:
    value = body_as_json(value)
    if isinstance(value, dict):
        return value.get(name, MISSING)
    return MISSING


def sql_request(params: dict[str, str]) -> dict[str, Any]:
    # The nested catalog control/payload metadata is deliberately not sent.
    return {"method": "GET", "params": params, "headers": {}, "body": None}


def command_request() -> dict[str, Any]:
    return {
        "method": "GET",
        "params": {"ipaddress": "127.0.0.1|printf VA_LAB_OK"},
        "headers": {},
        "body": None,
    }


def ssrf_request() -> dict[str, Any]:
    return {
        "method": "GET",
        "params": {"fileurl": "http://receiver:8081/"},
        "headers": {},
        "body": None,
    }


def record(name: str, function: Callable[[], Any]) -> None:
    global LAST_TOOL_RESULT
    LAST_TOOL_RESULT = None
    progress(f"START {name}")
    started = time.monotonic()
    row: dict[str, Any] = {"name": name}
    try:
        details = function()
        row["status"] = "pass"
        if details is not None:
            row["details"] = redact(details)
        progress(f"PASS  {name}")
    except SkipTest as exc:
        row["status"] = "skipped"
        row["reason"] = str(exc) if str(exc) else "dependency_unavailable"
        progress(f"SKIP  {name}")
    except CheckFailure as exc:
        row["status"] = "fail"
        row["reason"] = exc.code
        if LAST_TOOL_RESULT is not None:
            row["details"] = redact(LAST_TOOL_RESULT)
        progress(f"FAIL  {name}")
    except Exception as exc:  # collect later tests instead of aborting the run
        row["status"] = "fail"
        row["reason"] = type(exc).__name__
        progress(f"FAIL  {name}")
    row["elapsed_seconds"] = round(time.monotonic() - started, 3)
    RESULTS.append(row)


def require_catalog_missions(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    selected = {
        key: mission(catalog, key)
        for key in ("sqlInjection-01", "commandInjection-02", "ssrf-01")
    }
    check(all(mission_has_method(item, "GET") for item in selected.values()))
    check(int(selected["sqlInjection-01"].get("points", -1)) == 0)
    check(int(selected["commandInjection-02"].get("points", -1)) == 100)
    check(int(selected["ssrf-01"].get("points", -1)) == 100)
    return selected


def test_catalog() -> dict[str, Any]:
    catalog = load_catalog()
    selected = require_catalog_missions(catalog)
    return {
        "version": catalog.get("version"),
        "mission_count": len(catalog["missions"]),
        "selected": sorted(selected),
    }


def test_discover() -> dict[str, Any]:
    result = invoke_helper("discover", {"service": "all"})
    tool = result["tool"]
    try:
        check(result["returncode"] == 0)
        check(tool.get("action") == "discover" and tool.get("ok") is True)
        services = tool.get("services")
        check(isinstance(services, list) and len(services) == len(SERVICE_PORTS))
        by_name = {item.get("service"): item for item in services if isinstance(item, dict)}
        check(set(by_name) == set(SERVICE_PORTS))
        for name, port in SERVICE_PORTS.items():
            item = by_name[name]
            ips = item.get("ips")
            check(isinstance(ips, list) and bool(ips))
            check(item.get("port") == port)
            opened = item.get("open")
            check(isinstance(opened, list) and bool(opened))
            check(
                any(
                    isinstance(scan, dict)
                    and any(
                        isinstance(open_port, dict)
                        and open_port.get("port") == port
                        and open_port.get("state") == "open"
                        for open_port in scan.get("open", [])
                    )
                    for scan in opened
                )
            )
    except CheckFailure as exc:
        raise CheckFailure("discover_port_not_open") from exc
    return result


def test_sql_http() -> dict[str, Any]:
    control = invoke_helper("http", {"mission_id": "sqlInjection-01", "request": sql_request({"id": "999"})})
    payload = invoke_helper(
        "http",
        {"mission_id": "sqlInjection-01", "request": sql_request({"id": "100 OR 2=2"})},
    )
    for item in (control, payload):
        check(item["returncode"] == 0)
        tool = item["tool"]
        check(tool.get("action") == "http" and tool.get("ok") is True)
        check(tool.get("status") == 200 or tool.get("code") == 200)
    control_body = control["tool"].get("body")
    payload_body = payload["tool"].get("body")
    control_value = body_field(control_body, "isValid")
    payload_value = body_field(payload_body, "isValid")
    if control_value is MISSING or payload_value is MISSING:
        control_value = body_field(control_body, "isCarPresent")
        payload_value = body_field(payload_body, "isCarPresent")
    check(control_value is not MISSING and payload_value is not MISSING)
    check(control_value is False and payload_value is True)
    check(body_as_json(control_body) != body_as_json(payload_body))
    return {
        "control": control,
        "payload": payload,
        "compared_field": "isValid" if body_field(control_body, "isValid") is not MISSING else "isCarPresent",
        "control_value": control_value,
        "payload_value": payload_value,
    }


def test_command_http() -> dict[str, Any]:
    result = invoke_helper(
        "http",
        {"mission_id": "commandInjection-02", "request": command_request()},
    )
    tool = result["tool"]
    check(result["returncode"] == 0)
    check(tool.get("action") == "http" and tool.get("ok") is True)
    body = tool.get("body")
    check("VA_LAB_OK" in (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)))
    return result


def test_submit_first(account: dict[str, str] | None) -> dict[str, Any]:
    if account is None:
        raise SkipTest("first_account_unavailable")
    result = invoke_helper("submit", {"mission_id": "ssrf-01", "request": ssrf_request()})
    tool = result["tool"]
    try:
        check(result["returncode"] == 0)
        check(tool.get("action") == "submit" and tool.get("ok") is True)
        check(tool.get("success") is True)
        check(tool.get("awarded") == 100)
        server = tool.get("server")
        check(isinstance(server, dict))
        check(server.get("success") is True)
        check(server.get("awarded") == 100)
        check(isinstance(server.get("score"), int) and server.get("score") >= 100)
    except CheckFailure as exc:
        raise CheckFailure("submit_first_not_success_100") from exc
    return result


def test_submit_duplicate(account: dict[str, str] | None) -> dict[str, Any]:
    if account is None:
        raise SkipTest("first_account_unavailable")
    result = invoke_helper("submit", {"mission_id": "ssrf-01", "request": ssrf_request()})
    tool = result["tool"]
    try:
        check(result["returncode"] == 0)
        check(tool.get("action") == "submit" and tool.get("ok") is True)
        check(tool.get("success") is True)
        check(tool.get("awarded") == 0)
        server = tool.get("server")
        check(isinstance(server, dict))
        check(server.get("awarded") == 0)
    except CheckFailure as exc:
        raise CheckFailure("submit_repeat_not_zero_awarded") from exc
    return result


def test_second_account_initial(account: dict[str, str] | None) -> dict[str, Any]:
    if account is None:
        raise SkipTest("second_account_unavailable")
    code, value = api_json("GET", "/api/me", token=account["token"])
    check(code == 200 and isinstance(value, dict))
    check(value.get("score") == 0)
    completed = value.get("completed")
    if completed is not None:
        check(isinstance(completed, list) and not completed)
    return {"score": value.get("score"), "completed_count": len(completed) if isinstance(completed, list) else 0}


def test_key_unreadable() -> dict[str, Any]:
    path = Path("/run/academy-secrets/harness.key")
    try:
        with path.open("rb") as source:
            source.read(1)
    except (PermissionError, OSError):
        return {"readable_as_uid1000": False}
    raise CheckFailure("secret_key_readable")


def test_capabilities_zero() -> dict[str, Any]:
    values: dict[str, int] = {}
    for line in Path("/proc/self/status").read_text(encoding="ascii", errors="replace").splitlines():
        if line.startswith(("CapEff:", "CapPrm:")):
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip(), 16)
    check(values.get("CapEff") == 0 and values.get("CapPrm") == 0)
    return {"effective_zero": True, "permitted_zero": True}


def test_external_egress_denied() -> dict[str, Any]:
    env = dict(os.environ)
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        env[key] = ""
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"
    command = [
        "curl",
        "--config",
        "/dev/null",
        "--noproxy",
        "*",
        "--silent",
        "--show-error",
        "--connect-timeout",
        "2",
        "--max-time",
        "4",
        "--output",
        "/dev/null",
        "http://1.1.1.1/",
    ]
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        shell=False,
        timeout=6,
        check=False,
    )
    check(completed.returncode != 0)
    return {"blocked": True, "returncode": completed.returncode}


def main() -> int:
    progress("begin uid=%d" % os.geteuid())
    record("catalog_contract", test_catalog)

    # Runtime identity and installed interfaces are checked without exposing
    # any file contents or account material.
    record("uid_1000", lambda: (check(os.geteuid() == 1000), {"uid": os.geteuid()})[1])
    record("helper_installed", lambda: (check(Path(HELPER).is_file() and os.access(HELPER, os.X_OK)), {"present": True})[1])
    record("discover_all", test_discover)
    record("http_sql_control_vs_payload", test_sql_http)
    record("http_command_marker", test_command_http)

    sql_empty = sql_request({})
    record("guard_unknown_service", lambda: expect_rejected("discover", {"service": "not-a-compose-service"}))
    record("guard_unknown_ip", lambda: expect_rejected("discover", {"service": "127.0.0.1"}))
    record(
        "guard_unknown_mission",
        lambda: expect_rejected("http", {"mission_id": "not-in-catalog", "request": sql_empty}),
    )
    record(
        "guard_path_traversal_mission",
        lambda: expect_rejected("http", {"mission_id": "../../etc/passwd", "request": sql_empty}),
    )
    record(
        "guard_host_header",
        lambda: expect_rejected(
            "http",
            {"mission_id": "sqlInjection-01", "request": {**sql_request({"id": "999"}), "headers": {"Host": "evil.test"}}},
        ),
    )
    record(
        "guard_header_crlf",
        lambda: expect_rejected(
            "http",
            {
                "mission_id": "sqlInjection-01",
                "request": {**sql_request({"id": "999"}), "headers": {"X-Test": "ok\r\nInjected: yes"}},
            },
        ),
    )
    record(
        "guard_body_over_16k",
        lambda: expect_rejected(
            "http",
            {
                "mission_id": "commandInjection-02",
                "request": {**command_request(), "body": "A" * (16 * 1024 + 1)},
            },
        ),
    )
    record("guard_unknown_action", lambda: expect_rejected("shell", {}))
    record("secret_key_unreadable", test_key_unreadable)
    record("capabilities_zero", test_capabilities_zero)
    record("external_egress_denied", test_external_egress_denied)

    first_account: dict[str, str] | None = None

    def register_first() -> dict[str, Any]:
        nonlocal first_account
        first_account = create_account()
        session = save_session(first_account)
        return {"session": session}

    record("register_first_and_save_session", register_first)
    record("submit_ssrf_first_100_xp", lambda: test_submit_first(first_account))
    record("submit_ssrf_repeat_zero_awarded", lambda: test_submit_duplicate(first_account))

    second_account: dict[str, str] | None = None

    def register_second() -> dict[str, Any]:
        nonlocal second_account
        second_account = create_account()
        session = save_session(second_account)
        return {"session": session}

    # This is deliberately the final session write: the parent flow can reuse
    # the uid-1000 session and no logout is performed here.
    record("register_second_and_save_session", register_second)
    record("second_account_score_zero_before_attempt", lambda: test_second_account_initial(second_account))

    summary = {
        "passed": sum(1 for row in RESULTS if row.get("status") == "pass"),
        "failed": sum(1 for row in RESULTS if row.get("status") == "fail"),
        "skipped": sum(1 for row in RESULTS if row.get("status") == "skipped"),
        "total": len(RESULTS),
    }
    report = {
        "format": 1,
        "ok": summary["failed"] == 0 and summary["skipped"] == 0,
        "uid": os.geteuid(),
        "summary": summary,
        "tests": redact(RESULTS),
    }
    try:
        fd, temporary = tempfile.mkstemp(prefix="harness-tools-e2e-", suffix=".json", dir="/tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(report, output, ensure_ascii=False, indent=2, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, REPORT)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    except OSError:
        progress("FAIL  write_report")
        return 1

    progress("REPORT /tmp/harness-tools-e2e.json")
    progress("SUMMARY passed=%d failed=%d skipped=%d total=%d" % tuple(summary[key] for key in ("passed", "failed", "skipped", "total")))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
