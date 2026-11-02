#!/usr/bin/env python3
"""Herramientas estructuradas y cerradas para VulnerableApp Academy.

El proceso se ejecuta dentro de Kali y sólo conoce los cinco nombres de servicio
estáticos del laboratorio. La interfaz de proceso es deliberadamente pequeña:
``lab-harness-tools ACTION`` recibe un objeto JSON por stdin y devuelve un
sobre JSON por stdout. Nunca se usa ``shell=True`` ni se acepta una URL del
agente.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import ipaddress
import json
import os
import pwd
import re
import shlex
import signal
import socket
import stat
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote_plus, unquote, urlencode, urlsplit


MAX_STDIN_BYTES = 32 * 1024
MAX_STDOUT_BYTES = 32 * 1024
MAX_ACTION_SECONDS = 80
MAX_BODY_BYTES = 16 * 1024
MAX_EVIDENCE_BODY_BYTES = 8 * 1024
MAX_RECORDS = 64
MAX_VALUE_BYTES = 16 * 1024
MAX_HEADER_VALUE_BYTES = 16 * 1024
MAX_HEADER_NAME_BYTES = 256
MAX_CATALOG_ROUTE_BYTES = 512
MAX_MISSION_LIST = 32
MAX_MISSION_SUMMARY_BYTES = 4 * 1024

CATALOG_PATH = Path("/opt/academy-harness/catalog.json")
LAB_CLIENT_PATH = Path("/usr/local/bin/lab")

SERVICES: tuple[str, ...] = ("target", "receiver", "mailpit", "academy", "ollama")
SERVICE_PORTS: dict[str, int] = {
    "target": 9090,
    "receiver": 8081,
    "mailpit": 8025,
    "academy": 8000,
    "ollama": 11434,
}
HTTP_METHODS = {"GET", "POST", "PUT"}
REQUEST_KEYS = {"method", "params", "headers", "body", "content_type"}
TOP_LEVEL_KEYS = {"mission_id", "request"}
HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
MISSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
HTTP_VERB_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b")
ROUTE_CHARS_RE = re.compile(r"^[A-Za-z0-9._~!$&'()*+,;=:@%/\-]+$")
NMAP_PORT_RE = re.compile(r"^\s*(\d+)/tcp\s+(\S+)(?:\s+(.*?))?\s*$")
VERSION_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])v?\d+(?:[._-]\d+)+(?:[-+._][A-Za-z0-9]+)*")
BLOCKED_HEADERS = {
    "host",
    "connection",
    "content-length",
    "transfer-encoding",
    "proxy",
    "proxy-authorization",
    "proxy-authenticate",
    "proxy-connection",
    "upgrade",
}
SENSITIVE_KEY_TOKENS = (
    "password",
    "passwd",
    "pwd",
    "authorization",
    "cookie",
    "setcookie",
    "token",
    "secret",
    "apikey",
    "credential",
    "session",
    "jwt",
    "bearer",
)
SENSITIVE_TEXT_RE = re.compile(
    r"(?i)(password|passwd|pwd|authorization|cookie|set-cookie|token|secret|api[_-]?key)"
    r"\s*([:=])\s*(['\"]?)([^'\"\s,;&}]+)"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


class ToolError(ValueError):
    """Untrusted input, unavailable lab resource, or unsafe catalog data."""


class ActionTimeout(ToolError):
    pass


class _Deadline:
    """Bound one complete action, including DNS, subprocesses, and API I/O."""

    def __enter__(self) -> "_Deadline":
        if not hasattr(signal, "SIGALRM"):
            return self
        self.previous = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, self._alarm)
        signal.setitimer(signal.ITIMER_REAL, MAX_ACTION_SECONDS)
        return self

    @staticmethod
    def _alarm(_signum: int, _frame: Any) -> None:
        raise ActionTimeout("la acción excedió 80 segundos")

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        if hasattr(signal, "SIGALRM"):
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, self.previous)


def _text_size(value: str) -> int:
    return len(value.encode("utf-8"))


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolError(f"{label} debe ser un objeto JSON")
    return value


def _reject_unknown(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ToolError(f"{label} contiene claves no permitidas: {', '.join(unknown)}")


def _sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    compact = re.sub(r"[^a-z0-9]", "", key.lower())
    return any(token in compact for token in SENSITIVE_KEY_TOKENS)


def _redact_text(value: str, limit: int = 1_024) -> str:
    value = BEARER_RE.sub("Bearer <redacted>", value)

    def replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)}{match.group(3)}<redacted>"

    return SENSITIVE_TEXT_RE.sub(replace, value)[:limit]


def _redact_display(value: Any, key: Any = None, *, depth: int = 0) -> Any:
    """Copy a value for model-facing display, redacting credential-like fields."""

    if _sensitive_key(key):
        return "<redacted>"
    if depth > 5:
        return "<nested value omitted>"
    if isinstance(value, Mapping):
        return {
            str(item_key)[:MAX_HEADER_NAME_BYTES]: _redact_display(item, item_key, depth=depth + 1)
            for item_key, item in list(value.items())[:MAX_RECORDS]
        }
    if isinstance(value, list):
        return [_redact_display(item, depth=depth + 1) for item in value[:8]]
    if isinstance(value, tuple):
        return [_redact_display(item, depth=depth + 1) for item in value[:8]]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _bounded_text(value: Any, limit: int = MAX_MISSION_SUMMARY_BYTES) -> str:
    text = value if isinstance(value, str) else json.dumps(
        _redact_display(value), ensure_ascii=False, separators=(",", ":"), default=str
    )
    return text[:limit] + ("…" if len(text) > limit else "")


def _request_display(mission_id: str, mission: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": mission_id,
        "route": _normalize_route(mission.get("route")),
        "method": request.get("method"),
        "params": _redact_display(request.get("params", {})),
        "headers": _redact_display(request.get("headers", {})),
        "body": _redact_display(request.get("body"), "body"),
        "content_type": _redact_display(request.get("content_type"), "content_type"),
    }


def _evidence_summary(value: Any) -> str:
    """Describe returned evidence without inventing a status or score."""

    if isinstance(value, Mapping) and isinstance(value.get("evidence"), Mapping):
        value = value["evidence"]
    if not isinstance(value, Mapping):
        return "Evidencia devuelta: " + _bounded_text(value, 1_500)
    parts: list[str] = []
    status = value.get("status", value.get("code"))
    if isinstance(status, int):
        parts.append(f"HTTP {status}")
    headers = value.get("headers")
    if isinstance(headers, Mapping):
        shown_headers = _redact_display(dict(list(headers.items())[:12]))
        parts.append("cabeceras=" + _bounded_text(shown_headers, 700))
    if "body" in value:
        parts.append("cuerpo=" + _bounded_text(_redact_display(value.get("body")), 1_800))
    if not parts and "message" in value:
        parts.append("mensaje=" + _bounded_text(value.get("message"), 1_000))
    return "; ".join(parts)[:MAX_MISSION_SUMMARY_BYTES] or "Evidencia devuelta sin campos resumibles"


def _safe_env() -> dict[str, str]:
    """Do not inherit proxy variables or unrelated runner credentials."""

    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": "/tmp",
        "LANG": "C",
        "LC_ALL": "C",
        "NO_PROXY": "*",
        "no_proxy": "*",
        "http_proxy": "",
        "https_proxy": "",
        "HTTP_PROXY": "",
        "HTTPS_PROXY": "",
        "ALL_PROXY": "",
        "all_proxy": "",
    }


def _validate_discover_args(args: Any) -> list[str]:
    value = _require_object(args, "discover")
    # The current plugin sends the singular compatibility form. The list form
    # remains the canonical CLI contract; accepting both is safe because both
    # are still closed over the same five service names and cannot be mixed.
    _reject_unknown(value, {"services", "service"}, "discover")
    if "service" in value and "services" in value:
        raise ToolError("discover usa services o service, no ambos")
    if "service" in value:
        service = value["service"]
        if service == "all":
            return list(SERVICES)
        if isinstance(service, list):
            if len(service) > len(SERVICES):
                raise ToolError("discover.service contiene demasiados servicios")
            result: list[str] = []
            for item in service:
                if not isinstance(item, str) or item not in SERVICE_PORTS or item in result:
                    raise ToolError("discover.service contiene un servicio no permitido")
                result.append(item)
            return result
        if not isinstance(service, str) or service not in SERVICE_PORTS:
            raise ToolError("discover.service no está permitido")
        return [service]
    if "services" not in value:
        return list(SERVICES)
    services = value["services"]
    if not isinstance(services, list):
        raise ToolError("discover.services debe ser una lista")
    if len(services) > len(SERVICES):
        raise ToolError("discover.services contiene demasiados servicios")
    result: list[str] = []
    for service in services:
        if not isinstance(service, str) or service not in SERVICE_PORTS:
            raise ToolError("discover.services contiene un servicio no permitido")
        if service in result:
            raise ToolError("discover.services no puede contener duplicados")
        result.append(service)
    return result


def _safe_ipv4(value: str) -> bool:
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        return False
    # Docker lab addresses are private IPv4 addresses. Explicitly exclude
    # special ranges and the conventional .1 gateway even when is_private
    # happens to classify a special address as private.
    return (
        address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_unspecified
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_global
        and int(str(address).rsplit(".", 1)[1]) != 1
    )


def _resolve_service(service: str) -> list[str]:
    if service not in SERVICE_PORTS:
        raise ToolError("hostname no permitido")
    try:
        records = socket.getaddrinfo(
            service,
            SERVICE_PORTS[service],
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    except (OSError, socket.gaierror) as exc:
        raise ToolError(f"no se pudo resolver {service}") from exc
    addresses = sorted({str(record[4][0]) for record in records if record[4]})
    safe = [address for address in addresses if _safe_ipv4(address)]
    if not safe:
        raise ToolError(f"{service} no resolvió una IPv4 privada segura")
    return safe


def _nmap_command(ip: str, port: int) -> list[str]:
    # Every option is source-controlled. In particular, the model cannot add
    # scripts, ranges, timing options, or an alternative target.
    return [
        "nmap",
        "-sT",
        "-n",
        "-Pn",
        "--version-light",
        "-sV",
        f"-p{port}",
        "--host-timeout",
        "15s",
        ip,
    ]


def _split_product_version(service: str, detail: str) -> tuple[str, str]:
    detail = detail.strip()
    if not detail:
        return "", ""
    match = VERSION_TOKEN_RE.search(detail)
    if match:
        product = detail[: match.start()].strip() or service
        return product[:256], detail[match.start() :].strip()[:256]
    return detail[:256], ""


def _parse_nmap_open(stdout: str, port: int) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for line in stdout.splitlines():
        match = NMAP_PORT_RE.match(line)
        if not match or int(match.group(1)) != port or match.group(2).lower() != "open":
            continue
        service = ""
        detail = (match.group(3) or "").strip()
        if detail:
            pieces = detail.split(None, 1)
            service = pieces[0]
            detail = pieces[1] if len(pieces) == 2 else ""
        product, version = _split_product_version(service or "unknown", detail)
        found.append(
            {
                "port": port,
                "state": "open",
                "service": service,
                "product": product,
                "version": version,
            }
        )
    return found


def _scan_ip(ip: str, port: int) -> dict[str, Any]:
    command = _nmap_command(ip, port)
    version_command = shlex.join(command)
    probe_note = None
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_safe_env(),
            shell=False,
            check=False,
            timeout=20,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        completed = subprocess.CompletedProcess(command, 124, stdout="", stderr="nmap excedió su límite de fingerprint")
    open_ports = _parse_nmap_open(completed.stdout[:64 * 1024], port)
    if not open_ports:
        # A slow fingerprint is not proof that the TCP port is closed. Confirm
        # liveness with a second fixed Nmap TCP-connect scan, never a guessed
        # result. Both scans cover the same approved IP and single port.
        fallback = ["nmap", "-sT", "-n", "-Pn", f"-p{port}", "--host-timeout", "5s", ip]
        try:
            confirmed = subprocess.run(fallback, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_safe_env(),
                shell=False, check=False, timeout=8, text=True,
                encoding="utf-8", errors="replace")
            open_ports = _parse_nmap_open(confirmed.stdout[:64 * 1024], port)
            command, completed = fallback, confirmed
            if open_ports:
                probe_note = {"command": version_command, "confirmed": False,
                    "reason": "El fingerprint no confirmó software/versión dentro del límite; el segundo Nmap confirmó solo el puerto TCP."}
        except subprocess.TimeoutExpired:
            return {"ip": ip, "port": port, "open": [], "error": "el Nmap TCP de confirmación excedió su límite", "command": shlex.join(fallback)}
    result: dict[str, Any] = {
        "ip": ip,
        "port": port,
        "open": open_ports,
        "command": shlex.join(command),
    }
    if probe_note:
        result["version_probe"] = probe_note
    if completed.returncode != 0 and not open_ports:
        error = completed.stderr.strip()[:512]
        if error:
            result["error"] = error
    return result


def _discover(args: Any) -> dict[str, Any]:
    services = _validate_discover_args(args)
    # Resolve only the fixed service names before starting bounded scans.
    resolved: dict[str, list[str]] = {}
    failures: dict[str, str] = {}
    for service in services:
        try:
            resolved[service] = _resolve_service(service)
        except ToolError as exc:
            failures[service] = str(exc)

    jobs: list[tuple[str, str]] = [
        (service, ip) for service in services for ip in resolved.get(service, [])
    ]
    scan_results: dict[tuple[str, str], dict[str, Any]] = {}
    if jobs:
        with ThreadPoolExecutor(max_workers=min(3, len(jobs))) as pool:
            futures = {
                pool.submit(_scan_ip, ip, SERVICE_PORTS[service]): (service, ip)
                for service, ip in jobs
            }
            for future, key in futures.items():
                try:
                    scan_results[key] = future.result()
                except Exception as exc:  # keep one failed scan from hiding others
                    scan_results[key] = {
                        "ip": key[1],
                        "port": SERVICE_PORTS[key[0]],
                        "open": [],
                        "error": "falló la comprobación nmap",
                        "command": shlex.join(_nmap_command(key[1], SERVICE_PORTS[key[0]])),
                    }

    output: list[dict[str, Any]] = []
    for service in services:
        addresses = resolved.get(service, [])
        item: dict[str, Any] = {
            "service": service,
            "hostname": service,
            "port": SERVICE_PORTS[service],
            "ips": addresses,
            "open": [scan_results[(service, ip)] for ip in addresses if (service, ip) in scan_results],
        }
        if service in failures:
            item["error"] = failures[service]
        output.append(item)
    lines = ["Descubrimiento real de servicios fijos:"]
    for item in output:
        opened = sum(
            1
            for scan in item.get("open", [])
            if isinstance(scan, Mapping)
            and any(isinstance(port, Mapping) and port.get("state") == "open" for port in scan.get("open", []))
        )
        suffix = f"; {opened} comprobación(es) confirmó/confirmaron puerto abierto" if opened else "; sin puerto confirmado"
        if item.get("error"):
            suffix += f"; error: {item['error']}"
        lines.append(f"- {item['service']}:{item['port']} ({item['hostname']}){suffix}")
    return {"action": "discover", "ok": True, "services": output, "summary": "\n".join(lines)}


def _load_catalog() -> dict[str, Any]:
    try:
        with CATALOG_PATH.open("r", encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ToolError("el catálogo fijo no se puede leer") from exc
    if not isinstance(value, dict) or not isinstance(value.get("missions"), list):
        raise ToolError("el catálogo fijo no tiene missions válidas")
    return value


def _catalog_mission(mission_id: str) -> dict[str, Any]:
    if not isinstance(mission_id, str) or not MISSION_ID_RE.fullmatch(mission_id):
        raise ToolError("mission_id no es un identificador permitido")
    catalog = _load_catalog()
    for mission in catalog["missions"]:
        if isinstance(mission, dict) and mission.get("id") == mission_id:
            return mission
    raise ToolError("misión no encontrada en el catálogo fijo")


def _mission_methods(mission: Mapping[str, Any]) -> set[str]:
    raw = mission.get("method")
    values = raw if isinstance(raw, list) else [raw]
    methods: set[str] = set()
    for value in values:
        if isinstance(value, str):
            methods.update(match.group(1) for match in HTTP_VERB_RE.finditer(value.upper()))
    return methods & HTTP_METHODS


MISSIONS_KEYS = {"mission_id", "family", "limit", "offset"}


def _validate_missions_args(args: Any) -> tuple[str | None, str | None, int, int]:
    value = _require_object(args, "missions")
    _reject_unknown(value, MISSIONS_KEYS, "missions")
    mission_id = value.get("mission_id")
    if mission_id is not None and (not isinstance(mission_id, str) or not MISSION_ID_RE.fullmatch(mission_id)):
        raise ToolError("missions.mission_id no es un identificador permitido")
    family = value.get("family")
    if family is not None and (
        not isinstance(family, str)
        or not family
        or _text_size(family) > MAX_HEADER_NAME_BYTES
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", family)
    ):
        raise ToolError("missions.family no es válida")
    limit = value.get("limit", MAX_MISSION_LIST)
    offset = value.get("offset", 0)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_MISSION_LIST:
        raise ToolError(f"missions.limit debe estar entre 1 y {MAX_MISSION_LIST}")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 256:
        raise ToolError("missions.offset debe estar entre 0 y 256")
    if mission_id is not None and (family is not None or "limit" in value or "offset" in value):
        raise ToolError("missions.mission_id no se combina con filtros o paginación")
    return mission_id, family, limit, offset


def _catalog_mission_brief(mission: Mapping[str, Any]) -> dict[str, Any]:
    methods = sorted(_mission_methods(mission))
    return {
        "id": mission.get("id"),
        "title": _bounded_text(_redact_display(mission.get("title", "")), 320),
        "family": mission.get("family"),
        "methods": methods,
        "route": _normalize_route(mission.get("route")),
        "tool": mission.get("tool"),
        "points": mission.get("points"),
    }


def _catalog_templates(mission: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_params = mission.get("params", {})
    if not isinstance(raw_params, Mapping):
        raw_params = {}
    nested = bool(raw_params) and all(isinstance(item, Mapping) for item in raw_params.values())
    variants: list[tuple[str, Mapping[str, Any]]] = []
    if nested:
        variants = [(str(name), item) for name, item in list(raw_params.items())[:8] if isinstance(item, Mapping)]
    else:
        variants = [("attack", raw_params)]
    methods = sorted(_mission_methods(mission))
    method = methods[0] if methods else "GET"
    templates: list[dict[str, Any]] = []
    for name, params in variants:
        templates.append(
            {
                "name": name,
                "request": {
                    "method": method,
                    "params": _redact_display(dict(params)),
                    "headers": _redact_display(mission.get("headers", {})),
                    "body": _redact_display(mission.get("body"), "body"),
                    "content_type": _redact_display(mission.get("content_type"), "content_type"),
                },
            }
        )
    return templates


def _catalog_mission_detail(mission: Mapping[str, Any]) -> dict[str, Any]:
    detail = _catalog_mission_brief(mission)
    detail.update(
        {
            "templates": _catalog_templates(mission),
            "commands": [
                _bounded_text(_redact_display(step), 1_024)
                for step in mission.get("steps", [])[:8]
                if isinstance(step, str)
            ],
            "hints": [_bounded_text(_redact_display(item), 700) for item in mission.get("hints", [])[:8]],
            "expected": _redact_display(mission.get("expected")),
            "mitigation": _bounded_text(_redact_display(mission.get("mitigation", "")), 1_500),
        }
    )
    return detail


def _missions(args: Any) -> dict[str, Any]:
    mission_id, family, limit, offset = _validate_missions_args(args)
    catalog = _load_catalog()
    all_missions = [item for item in catalog["missions"] if isinstance(item, Mapping)]
    if mission_id is not None:
        selected = _catalog_mission(mission_id)
        detail = _catalog_mission_detail(selected)
        summary = (
            f"Misión exacta {mission_id}: {detail.get('title', '')}. "
            f"Método(s): {', '.join(detail['methods']) or 'no declarado'}; "
            f"ruta fija: {detail['route']}. Se devolvieron las plantillas del catálogo; no se envió ninguna solicitud."
        )
        return {
            "action": "missions",
            "ok": True,
            "catalog_version": catalog.get("version"),
            "count": len(all_missions),
            "mission": detail,
            "summary": _bounded_text(summary),
        }
    filtered = [item for item in all_missions if family is None or item.get("family") == family]
    page = filtered[offset : offset + limit]
    rows = [_catalog_mission_brief(item) for item in page]
    summary = (
        f"Catálogo fijo v{catalog.get('version')}: {len(filtered)} misión(es)"
        + (f" de la familia {family}" if family else "")
        + f"; mostrando {offset + 1 if page else 0}-{offset + len(page)}. "
        "Elige un id exacto y vuelve a consultar lab_missions con mission_id para ver la receta; no se ejecutó ninguna solicitud."
    )
    return {
        "action": "missions",
        "ok": True,
        "catalog_version": catalog.get("version"),
        "count": len(filtered),
        "offset": offset,
        "limit": limit,
        "missions": rows,
        "summary": _bounded_text(summary),
    }


def _normalize_route(raw_route: Any) -> str:
    if not isinstance(raw_route, str) or not raw_route:
        raise ToolError("la misión no tiene una ruta válida")
    if _text_size(raw_route) > MAX_CATALOG_ROUTE_BYTES:
        raise ToolError("la ruta de catálogo es demasiado larga")
    route = raw_route.strip()
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in route):
        raise ToolError("la ruta contiene caracteres de control")
    if "://" in route:
        parsed = urlsplit(route)
        if parsed.scheme != "http" or parsed.netloc.lower() not in {"target:9090", "target"}:
            raise ToolError("la ruta de catálogo apunta fuera de target")
        if parsed.query or parsed.fragment:
            raise ToolError("la ruta de catálogo no puede tener query o fragmento")
        route = parsed.path
    if route == "/VulnerableApp":
        route = ""
    elif route.startswith("/VulnerableApp/"):
        route = route[len("/VulnerableApp/") :]
    route = route.lstrip("/")
    if not route or not ROUTE_CHARS_RE.fullmatch(route):
        raise ToolError("la ruta de catálogo no es segura")
    # Catalog routes are source-controlled plain paths. Reject all percent
    # encoding so an encoded slash, backslash, query delimiter, NUL, or dot
    # cannot acquire URL semantics after this validation step.
    if "%" in route:
        raise ToolError("la ruta de catálogo no puede usar percent-encoding")
    if "//" in route or any(piece in {".", ".."} for piece in route.split("/")):
        raise ToolError("la ruta de catálogo contiene traversal")
    decoded = unquote(route)
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in decoded):
        raise ToolError("la ruta codificada contiene controles")
    if decoded != route and (
        "//" in decoded
        or "\\" in decoded
        or "?" in decoded
        or "#" in decoded
        or any(piece in {".", ".."} for piece in decoded.split("/"))
    ):
        raise ToolError("la ruta codificada no es segura")
    return "/VulnerableApp/" + route


def _mission_url(mission: Mapping[str, Any], params: Mapping[str, str] | None = None) -> str:
    path = _normalize_route(mission.get("route"))
    query = urlencode(list((params or {}).items()), doseq=True, quote_via=quote_plus)
    return "http://target:9090" + path + (("?" + query) if query else "")


def _validate_string_dict(value: Any, label: str, *, header: bool = False) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ToolError(f"{label} debe ser un objeto de strings")
    if len(value) > MAX_RECORDS:
        raise ToolError(f"{label} supera el máximo de {MAX_RECORDS} entradas")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or _text_size(key) > MAX_HEADER_NAME_BYTES:
            raise ToolError(f"clave inválida en {label}")
        if not isinstance(item, str) or _text_size(item) > MAX_VALUE_BYTES:
            raise ToolError(f"valor inválido en {label}")
        if "\x00" in key:
            raise ToolError(f"clave NUL no permitida en {label}")
        if header:
            if not HEADER_NAME_RE.fullmatch(key) or key.lower() in BLOCKED_HEADERS or key.lower().startswith("proxy-"):
                raise ToolError("header reservado o inválido")
            if any(ord(char) < 0x20 or ord(char) == 0x7F for char in item):
                raise ToolError("header con caracteres de control")
        result[key] = item
    return result


def _validate_request(mission_id: Any, request: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    mission = _catalog_mission(mission_id)
    value = _require_object(request, "request")
    _reject_unknown(value, REQUEST_KEYS, "request")
    # workshop-plugin currently omits content_type and uses an explicit
    # Content-Type header for form/XML/JSON requests. The local `lab` client
    # includes the separate field, so normalize the omission to null.
    missing = sorted((REQUEST_KEYS - {"content_type"}) - set(value))
    if missing:
        raise ToolError("request requiere: " + ", ".join(missing))
    method = value["method"]
    if not isinstance(method, str) or method not in HTTP_METHODS:
        raise ToolError("request.method no está permitido")
    if method not in _mission_methods(mission):
        raise ToolError("request.method no coincide con la misión")
    params = _validate_string_dict(value["params"], "request.params")
    headers = _validate_string_dict(value["headers"], "request.headers", header=True)
    body = value["body"]
    if body is not None and (not isinstance(body, str) or _text_size(body) > MAX_BODY_BYTES):
        raise ToolError("request.body debe ser texto de hasta 16 KiB")
    content_type = value.get("content_type")
    if content_type is not None:
        if not isinstance(content_type, str) or not content_type or _text_size(content_type) > 256:
            raise ToolError("request.content_type no es válido")
        if any(ord(char) < 0x20 or ord(char) == 0x7F for char in content_type):
            raise ToolError("request.content_type contiene controles")
    # Route validation is performed before any network operation, and only the
    # catalog mission is used to construct the target URL.
    _normalize_route(mission.get("route"))
    normalized = {
        "method": method,
        "params": params,
        "headers": headers,
        "body": body,
        "content_type": content_type,
    }
    return mission, normalized


def _display_url(mission: Mapping[str, Any], params: Mapping[str, str]) -> str:
    # Keep benign values useful to the agent while redacting credentials and
    # token-like values in the copyable display command.
    redacted = {key: str(_redact_display(item, key)) for key, item in params.items()}
    return _mission_url(mission, redacted)


def _parse_response_headers(raw: bytes) -> tuple[int, dict[str, str]]:
    text = raw.decode("iso-8859-1", errors="replace")[:64 * 1024]
    status = 0
    headers: dict[str, str] = {}
    for block in re.split(r"\r?\n\r?\n", text):
        lines = block.splitlines()
        if not lines or not lines[0].startswith("HTTP/"):
            continue
        match = re.match(r"HTTP/\S+\s+(\d{3})", lines[0])
        if not match:
            continue
        status = int(match.group(1))
        headers = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            if key:
                headers[key] = value.strip()[:4096]
    return status, headers


def _response_body(raw: bytes) -> tuple[Any, bool]:
    truncated = len(raw) > MAX_EVIDENCE_BODY_BYTES
    text = raw[:MAX_EVIDENCE_BODY_BYTES].decode("utf-8", errors="replace")
    if not truncated:
        try:
            # Preserve genuine JSON as JSON instead of double-encoding it.
            return json.loads(text), False
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return text, truncated


def _http(args: Any) -> dict[str, Any]:
    value = _require_object(args, "http")
    _reject_unknown(value, TOP_LEVEL_KEYS, "http")
    if set(value) != TOP_LEVEL_KEYS:
        raise ToolError("http requiere mission_id y request")
    mission, request = _validate_request(value["mission_id"], value["request"])
    method = request["method"]
    params = request["params"]
    url = _mission_url(mission, params)
    headers: list[tuple[str, str]] = list(request["headers"].items())
    if request["content_type"] is not None:
        headers.append(("Content-Type", request["content_type"]))
    header_fd, header_path = tempfile.mkstemp(prefix="va-harness-", suffix=".headers")
    os.close(header_fd)
    command = [
        "curl",
        "--config",
        "/dev/null",
        "--silent",
        "--show-error",
        "--noproxy",
        "*",
        "--max-time",
        "15",
        "--max-redirs",
        "0",
        "--request",
        method,
        "--dump-header",
        header_path,
        "--output",
        "-",
        "--write-out",
        "%{http_code}",
    ]
    for key, item in headers:
        command.extend(["--header", f"{key}: {item}"])
    # Params are always query parameters, matching academy's fixed runner.
    # Body is sent over stdin, never interpolated into argv.
    if request["body"] is not None:
        command.extend(["--data-binary", "@-"])
    command.append(url)
    body_bytes = request["body"].encode("utf-8") if request["body"] is not None else None
    try:
        completed = subprocess.run(
            command,
            input=body_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_safe_env(),
            shell=False,
            check=False,
            timeout=20,
        )
        combined = completed.stdout
        status_text = b""
        # --write-out is appended after the response body. It is exactly three
        # ASCII digits for a normal curl response, or 000 on a transport error.
        if len(combined) >= 3 and combined[-3:].isdigit():
            status_text = combined[-3:]
            raw_body = combined[:-3]
        else:
            raw_body = combined
        status = int(status_text) if status_text else 0
        stderr = completed.stderr.decode("utf-8", errors="replace")[:1024]
        raw_headers = Path(header_path).read_bytes()[:64 * 1024]
        header_status, response_headers = _parse_response_headers(raw_headers)
        if header_status:
            status = header_status
        body, truncated = _response_body(raw_body)
        display_command = [
            "curl",
            "--config",
            "/dev/null",
            "--silent",
            "--show-error",
            "--noproxy",
            "*",
            "--max-time",
            "15",
            "--max-redirs",
            "0",
            "--request",
            method,
            "--dump-header",
            header_path,
            "--output",
            "-",
            "--write-out",
            "%{http_code}",
        ]
        for key, item in headers:
            display_command.extend(["--header", f"{key}: {_redact_display(item, key)}"])
        if request["body"] is not None:
            # The actual helper sends the body through stdin; keep the command
            # executable without pretending that a redacted placeholder is data.
            display_command.extend(["--data-binary", "@-"])
        display_command.extend(["--url", _display_url(mission, params)])
        request_summary = _request_display(value["mission_id"], mission, request)
        evidence_summary = _evidence_summary({"status": status, "headers": response_headers, "body": body})
        result: dict[str, Any] = {
            "action": "http",
            "ok": True,
            "code": status,
            "status": status,
            "headers": response_headers,
            "body": body,
            "command": shlex.join(display_command),
            "request_summary": request_summary,
            "evidence_summary": evidence_summary,
            "summary": (
                f"Solicitud real {request['method']} {request_summary['route']} con argumentos visibles en "
                f"request_summary. Respuesta real: {evidence_summary}"
            )[:MAX_MISSION_SUMMARY_BYTES],
            "exit_code": int(completed.returncode),
        }
        if truncated:
            result["truncated"] = True
        if completed.returncode != 0 and stderr:
            result["error"] = stderr
        return result
    except subprocess.TimeoutExpired as exc:
        raise ToolError("curl excedió el timeout de 15 segundos") from exc
    except OSError as exc:
        raise ToolError("no se pudo ejecutar curl") from exc
    finally:
        try:
            os.unlink(header_path)
        except OSError:
            pass


def _session_path() -> Path:
    try:
        home = Path(pwd.getpwuid(1000).pw_dir)
    except KeyError:
        home = Path("/home/kali")
    return home / ".config" / "va-lab" / "session.json"


def _load_lab_client() -> Any:
    if not LAB_CLIENT_PATH.is_file():
        raise ToolError("el cliente lab no está instalado")
    loader = importlib.machinery.SourceFileLoader("va_lab_client_for_harness", str(LAB_CLIENT_PATH))
    spec = importlib.util.spec_from_file_location("va_lab_client_for_harness", LAB_CLIENT_PATH, loader=loader)
    if spec is None or spec.loader is None:
        raise ToolError("no se pudo cargar el cliente lab")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    session_path = _session_path()
    # lab.py normally derives this from HOME. The plugin deliberately supplies
    # a sterile HOME, so pin the path to the uid-1000 lab account instead.
    module.SESSION_FILE = session_path
    return module


def _check_session(path: Path) -> None:
    try:
        info = path.stat()
    except OSError as exc:
        raise ToolError("no hay sesión individual de lab") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 1000:
        raise ToolError("la sesión de lab no pertenece al uid 1000")
    if info.st_mode & 0o077:
        raise ToolError("la sesión de lab tiene permisos demasiado amplios")


def _progress() -> dict[str, Any]:
    session_path = _session_path()
    _check_session(session_path)
    client = _load_lab_client()
    try:
        code, server_value = client._api("/api/me", "GET", auth=True, timeout=MAX_ACTION_SECONDS)
    except Exception as exc:
        raise ToolError("no se pudo leer el progreso del servidor Academy") from exc
    if not isinstance(code, int):
        raise ToolError("el servidor Academy devolvió un código inválido")
    if code >= 400:
        raise ToolError(f"el servidor Academy rechazó la lectura de progreso ({code})")
    if not isinstance(server_value, Mapping):
        raise ToolError("el servidor Academy devolvió un progreso inválido")
    score = server_value.get("score")
    maximum = server_value.get("maximum")
    completed = server_value.get("completed")
    events = server_value.get("events")
    summary_parts = [f"Academy devolvió HTTP {code}"]
    if isinstance(score, int):
        summary_parts.append(f"score actual reportado por Academy={score}")
    if isinstance(maximum, int):
        summary_parts.append(f"máximo reportado={maximum}")
    if isinstance(completed, list):
        summary_parts.append(f"misiones completadas={len(completed)}")
    if isinstance(events, list):
        recent = []
        for event in events[:5]:
            if isinstance(event, Mapping) and isinstance(event.get("mission_id"), str):
                recent.append(
                    f"{event['mission_id']}:{'éxito' if event.get('success') else 'fallo'}"
                    f"/awarded={event.get('awarded', '<sin dato>')}"
                )
        if recent:
            summary_parts.append("eventos recientes=" + ", ".join(recent))
    summary_parts.append("Los valores son de Academy; el helper no calcula ni concede XP.")
    return {
        "action": "progress",
        "ok": True,
        "code": code,
        "server": dict(server_value),
        "summary": _bounded_text("; ".join(summary_parts)),
    }


def _submit(args: Any) -> dict[str, Any]:
    value = _require_object(args, "submit")
    _reject_unknown(value, TOP_LEVEL_KEYS, "submit")
    if set(value) != TOP_LEVEL_KEYS:
        raise ToolError("submit requiere mission_id y request")
    # Validate mission, route, method, headers and size before loading the
    # session or making a network request.
    mission, request = _validate_request(value["mission_id"], value["request"])
    session_path = _session_path()
    _check_session(session_path)
    client = _load_lab_client()
    payload = {"mission_id": value["mission_id"], "request": request}
    try:
        code, server_value = client._api(
            "/api/attempt",
            "POST",
            payload,
            auth=True,
            timeout=MAX_ACTION_SECONDS,
        )
    except Exception as exc:
        # Do not expose a token or the serialized request in an operational
        # error; the agent can retry after fixing lab availability.
        raise ToolError("no se pudo enviar el intento al servidor Academy") from exc
    if not isinstance(code, int):
        raise ToolError("el servidor Academy devolvió un código inválido")
    if code >= 400:
        raise ToolError(f"el servidor Academy rechazó el intento ({code})")
    request_summary = _request_display(value["mission_id"], mission, request)
    evidence_summary = _evidence_summary(server_value.get("evidence") if isinstance(server_value, Mapping) else server_value)
    result: dict[str, Any] = {
        "action": "submit",
        "ok": True,
        "code": code,
        "mission": value["mission_id"],
        "server": server_value,
        "request_summary": request_summary,
        "evidence_summary": evidence_summary,
        "summary": (
            f"Academy recibió el intento de {value['mission_id']} con "
            f"{request['method']} y los argumentos visibles en request_summary. "
            f"Resultado real del servidor: {evidence_summary}"
        )[:MAX_MISSION_SUMMARY_BYTES],
    }
    if isinstance(server_value, dict):
        # These are server values only. No score, XP, or evidence is computed
        # locally; ``awarded`` is retained because the current Academy API
        # uses that name while newer APIs may expose ``points``.
        for key in ("success", "points", "awarded", "message", "evidence", "score"):
            if key in server_value:
                result[key] = server_value[key]
    return result


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _bounded_output(value: Any) -> bytes:
    raw = _json_bytes(value)
    # main() appends one framing newline; reserve that byte in the payload
    # limit so stdout as a whole remains at or below 32 KiB.
    payload_limit = MAX_STDOUT_BYTES - 1
    if len(raw) <= payload_limit:
        return raw
    # Normal HTTP bodies and commands are already bounded, but keep a final
    # fail-closed envelope in case a future catalog/API adds an oversized field.
    if isinstance(value, dict):
        minimal: dict[str, Any] = {
            key: value[key]
            for key in (
                "action", "ok", "code", "status", "success", "mission", "message", "error",
                "summary", "evidence_summary", "request_summary",
            )
            if key in value
        }
        if "body" in value:
            body = value["body"]
            minimal["body"] = body[:1024] if isinstance(body, str) else "<respuesta truncada>"
        minimal["truncated"] = True
        raw = _json_bytes(minimal)
    if len(raw) <= payload_limit:
        return raw
    return _json_bytes({"action": value.get("action") if isinstance(value, dict) else "unknown", "ok": False, "error": "salida excede 32 KiB"})


def _error(action: str, message: str) -> dict[str, Any]:
    return {"action": action, "ok": False, "error": message[:1024]}


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    action = args[0] if args else "unknown"
    if len(args) != 1 or action not in {"discover", "missions", "progress", "http", "submit"}:
        data = _error(action, "uso: lab-harness-tools discover|missions|progress|http|submit")
        sys.stdout.buffer.write(_bounded_output(data) + b"\n")
        return 1
    try:
        raw = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
        if len(raw) > MAX_STDIN_BYTES:
            raise ToolError("la entrada JSON excede 32 KiB")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ToolError("stdin no contiene un objeto JSON válido") from exc
        with _Deadline():
            if action == "discover":
                reply = _discover(parsed)
            elif action == "missions":
                reply = _missions(parsed)
            elif action == "progress":
                if parsed not in ({}, None):
                    raise ToolError("progress no acepta argumentos")
                reply = _progress()
            elif action == "http":
                reply = _http(parsed)
            else:
                reply = _submit(parsed)
        sys.stdout.buffer.write(_bounded_output(reply) + b"\n")
        return 0
    except (ToolError, OSError, ValueError) as exc:
        sys.stdout.buffer.write(_bounded_output(_error(action, str(exc))) + b"\n")
        return 1
    except Exception:
        # Never emit a traceback or accidental environment details to the
        # model-facing stream.
        sys.stdout.buffer.write(_bounded_output(_error(action, "falló la acción del laboratorio")) + b"\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
