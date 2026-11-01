"""Carga del catálogo y evaluación determinista de evidencias HTTP.

El catálogo es código de control del servidor. Ningún campo enviado por el
cliente puede cambiar ruta, método, check o puntos. Los verificadores leen
únicamente la respuesta devuelta por el runner; nunca inspeccionan ``command``
ni ecos de la solicitud.
"""

from __future__ import annotations

import copy
import json
import os
import re
from urllib.parse import urlsplit
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


CATALOG_PATH = Path(
    os.getenv("CATALOG_PATH", str(Path(__file__).resolve().parent / "data" / "catalog.json"))
)
MAX_EVIDENCE_BODY = 8 * 1024
_ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
_SAFE_ROUTE = re.compile(r"^[^\x00?#\\]+$")


class CatalogError(ValueError):
    """El catálogo no cumple el contrato seguro del taller."""


@dataclass(frozen=True)
class Evaluation:
    success: bool
    message: str
    check: dict[str, Any]


def load_catalog(path: Optional[Path | str] = None) -> dict[str, Any]:
    """Load a catalog, returning an empty but valid catalog when absent.

    During the initial project bootstrap the parent agent may create the
    catalog after the backend. An absent file therefore exposes no missions,
    while a malformed file fails loudly instead of silently weakening checks.
    """

    source = Path(path or CATALOG_PATH)
    if not source.exists():
        return {"families": [], "missions": []}
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogError("El catálogo no se puede leer") from exc
    if not isinstance(value, dict):
        raise CatalogError("El catálogo debe ser un objeto")
    families = value.get("families", [])
    missions = value.get("missions", [])
    if not isinstance(families, list) or not isinstance(missions, list):
        raise CatalogError("families y missions deben ser listas")
    for mission in missions:
        _validate_mission(mission)
    return value


def catalog_copy() -> dict[str, Any]:
    """Return a detached source-controlled catalog for API serialization."""

    return copy.deepcopy(load_catalog())


def _validate_mission(mission: Any) -> None:
    if not isinstance(mission, dict):
        raise CatalogError("Cada misión debe ser un objeto")
    for required in ("id", "route", "method", "check"):
        if required not in mission:
            raise CatalogError(f"La misión no tiene {required}")
    mission_id = mission.get("id")
    if not isinstance(mission_id, str) or not 1 <= len(mission_id) <= 128:
        raise CatalogError("Identificador de misión inválido")
    route = normalize_route(mission.get("route"))
    if route is None:
        raise CatalogError(f"Ruta inválida en {mission_id}")
    methods = mission_methods(mission)
    if not methods:
        raise CatalogError(f"Método inválido en {mission_id}")
    check = mission.get("check")
    if not isinstance(check, dict):
        raise CatalogError(f"Check inválido en {mission_id}")


def mission_methods(mission: Mapping[str, Any]) -> list[str]:
    raw = mission.get("method")
    values = raw if isinstance(raw, list) else [raw]
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        # Manual catalog entries can describe a sequence (for example,
        # "POST DE PREPARACIÓN Y GET DE VERIFICACIÓN"). Extracting only the
        # HTTP verbs keeps that metadata non-executable while allowing the
        # actual request method to be checked against a source-controlled
        # allowlist.
        for candidate in re.findall(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b", value.upper()):
            if candidate in _ALLOWED_METHODS and candidate not in result:
                result.append(candidate)
    return result


def normalize_route(route: Any) -> Optional[str]:
    """Normalize a source route and reject traversal or external destinations."""

    if not isinstance(route, str) or len(route) > 512:
        return None
    route = route.strip()
    if "://" in route:
        parsed = urlsplit(route)
        # A catalog entry may carry the original target's fixed host. The
        # backend discards that host and forwards only its path; all other
        # hosts/schemes are rejected rather than becoming SSRF destinations.
        if parsed.scheme != "http" or parsed.netloc.lower() not in {"target:9090", "target"}:
            return None
        route = parsed.path
        if parsed.query or parsed.fragment:
            return None
    if route.startswith("/VulnerableApp/"):
        route = route[len("/VulnerableApp/") :]
    elif route == "/VulnerableApp":
        route = ""
    route = route.lstrip("/")
    if route and not _SAFE_ROUTE.fullmatch(route):
        return None
    if any(part in {".", ".."} for part in route.split("/")):
        return None
    if "//" in route:
        return None
    return route


def target_path(mission: Mapping[str, Any]) -> str:
    route = normalize_route(mission.get("route"))
    if route is None:
        raise CatalogError("La ruta de la misión no es segura")
    return "/VulnerableApp/" + route


def mission_by_id(catalog: Mapping[str, Any], mission_id: str) -> Optional[dict[str, Any]]:
    for mission in catalog.get("missions", []):
        if isinstance(mission, dict) and mission.get("id") == mission_id:
            _validate_mission(mission)
            return mission
    return None


def check_kind(check: Any) -> str:
    return check.get("kind", "").lower() if isinstance(check, dict) and isinstance(check.get("kind"), str) else ""


def is_scoreable(check: Any) -> bool:
    """Manual checks and ``all`` groups containing one are never scoreable."""

    kind = check_kind(check)
    if kind == "manual":
        return False
    if kind == "all":
        checks = check.get("checks")
        return isinstance(checks, list) and bool(checks) and all(is_scoreable(item) for item in checks)
    return kind in {
        "contains",
        "not_contains",
        "header",
        "header_contains",
        "json",
        "absent_header",
        "browser_dataset",
    }


def mission_points(mission: Mapping[str, Any]) -> int:
    if not is_scoreable(mission.get("check")):
        return 0
    value = mission.get("points", 0)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(value, 100_000))


def _response_body(response: Mapping[str, Any]) -> Optional[str]:
    if "body" not in response:
        return None
    value = response.get("body")
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (dict, list, int, float, bool)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _headers(response: Mapping[str, Any]) -> dict[str, str]:
    raw = response.get("headers")
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        elif not isinstance(value, str):
            value = str(value)
        result[key.lower()] = value
    return result


def _status(response: Mapping[str, Any]) -> Optional[int]:
    value = response.get("status")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _exit_code(response: Mapping[str, Any]) -> Optional[int]:
    value = response.get("exit_code")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _expected_statuses(check: Mapping[str, Any]) -> Optional[set[int]]:
    if "status" not in check:
        return None
    raw = check.get("status")
    values = raw if isinstance(raw, list) else [raw]
    parsed: set[int] = set()
    for value in values:
        if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
            parsed.add(value)
    return parsed


def _status_gate(response: Mapping[str, Any], check: Mapping[str, Any]) -> Optional[str]:
    """Apply runner-success and explicit-status rules before content checks."""

    exit_code = _exit_code(response)
    status = _status(response)
    if exit_code != 0:
        return "El runner no terminó correctamente"
    if status is None or status <= 0:
        return "La respuesta HTTP no tiene un status válido"
    expected = _expected_statuses(check)
    if "status" in check and (not expected or status not in expected):
        return "El status HTTP no coincide con el criterio de la misión"
    # A failed HTTP response cannot accidentally satisfy not_contains. A
    # mission may explicitly allow it with status: 404 (or another 4xx/5xx).
    if status >= 400 and expected is None:
        return "La misión no autoriza evaluar un error HTTP sin status explícito"
    return None


def _split_path(path: Any) -> Optional[list[str]]:
    if not isinstance(path, str) or not path or len(path) > 512:
        return None
    path = path.strip()
    if path.startswith("$"):
        if path == "$":
            return []
        if not path.startswith("$."):
            return None
        path = path[2:]
    elif path.startswith("/"):
        path = path[1:]
    path = path.lstrip(".")
    if not path:
        return []
    pieces: list[str] = []
    for piece in path.split("."):
        if not piece or not re.fullmatch(r"[A-Za-z0-9_-]+|\d+", piece):
            return None
        pieces.append(piece)
    return pieces


def _parse_json(value: Any) -> tuple[bool, Any]:
    if isinstance(value, (dict, list)):
        return True, value
    if isinstance(value, str):
        try:
            return True, json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return False, None
    return False, None


def _json_path(body: str, path: Any) -> tuple[bool, Any]:
    """Resolve a small JSON path, parsing embedded JSON strings as needed."""

    pieces = _split_path(path)
    if pieces is None:
        return False, None
    ok, current = _parse_json(body)
    if not ok:
        return False, None
    if not pieces:
        return True, current
    for index, piece in enumerate(pieces):
        # Some vulnerable endpoints put a JSON document in ``content``. When
        # traversal continues, decode that string instead of treating it as a
        # scalar; a missing key remains missing, never null/empty.
        if isinstance(current, str) and index < len(pieces):
            parsed, decoded = _parse_json(current)
            if not parsed:
                return False, None
            current = decoded
        if isinstance(current, dict) and piece in current:
            current = current[piece]
        elif isinstance(current, list) and piece.isdigit() and int(piece) < len(current):
            current = current[int(piece)]
        else:
            return False, None
    return True, current


def _value_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _dataset_path(dataset: Any, path: Any) -> tuple[bool, Any]:
    """Resolve a bounded dotted path in the runner's browser dataset only."""

    if not isinstance(path, str) or not path or len(path) > 256:
        return False, None
    pieces = path[2:].split(".") if path.startswith("$.") else path.split(".")
    if not pieces or any(not re.fullmatch(r"[A-Za-z0-9_-]+", piece) for piece in pieces):
        return False, None
    current = dataset
    for piece in pieces:
        if not isinstance(current, Mapping) or piece not in current:
            return False, None
        current = current[piece]
    return True, current


def _contains_like(response: Mapping[str, Any], check: Mapping[str, Any], negate: bool) -> Evaluation:
    body = _response_body(response)
    if body is None:
        return Evaluation(False, "La respuesta no contiene body evaluable", dict(check))
    path = check.get("path")
    if path is not None:
        exists, selected = _json_path(body, path)
        if not exists:
            return Evaluation(False, "El path JSON no existe en la respuesta", dict(check))
        haystack = _value_text(selected)
    else:
        haystack = body
    expected = check.get("value")
    if not isinstance(expected, (str, int, float, bool)):
        return Evaluation(False, "El valor del criterio no es textual", dict(check))
    needle = str(expected).lower() if isinstance(expected, bool) else str(expected)
    found = needle in haystack
    success = not found if negate else found
    if success:
        message = "Evidencia verificada: el texto esperado no aparece" if negate else "Evidencia verificada: contenido encontrado"
    else:
        message = "El texto prohibido aparece en la respuesta" if negate else "El contenido esperado no aparece"
    return Evaluation(success, message, dict(check))


def _header_value(response: Mapping[str, Any], header: Any) -> tuple[bool, Optional[str]]:
    if not isinstance(header, str) or not header.strip():
        return False, None
    values = _headers(response)
    key = header.strip().lower()
    return key in values, values.get(key)


def evaluate_response(response: Mapping[str, Any], check: Mapping[str, Any]) -> Evaluation:
    """Evaluate one catalog check against a runner response.

    ``response`` is intentionally treated as an untrusted mapping. Only
    status, exit_code, headers and body are consumed. The runner command and
    request echo are never part of any success decision.
    """

    if not isinstance(response, Mapping) or not isinstance(check, Mapping):
        return Evaluation(False, "Respuesta o criterio inválido", dict(check) if isinstance(check, Mapping) else {})
    gate = _status_gate(response, check)
    if gate:
        return Evaluation(False, gate, dict(check))
    kind = check_kind(check)
    if kind == "manual":
        return Evaluation(False, "Esta misión requiere verificación manual y no otorga puntos", dict(check))
    if kind == "contains":
        return _contains_like(response, check, negate=False)
    if kind == "not_contains":
        return _contains_like(response, check, negate=True)
    if kind == "header":
        exists, actual = _header_value(response, check.get("header"))
        expected = check.get("value")
        success = exists and (expected is None or str(actual) == str(expected))
        return Evaluation(success, "Header verificado" if success else "El header no coincide", dict(check))
    if kind == "header_contains":
        exists, actual = _header_value(response, check.get("header"))
        expected = check.get("value")
        success = exists and isinstance(expected, (str, int, float)) and str(expected).lower() in str(actual).lower()
        return Evaluation(
            success,
            "Contenido del header verificado" if success else "El contenido del header no coincide",
            dict(check),
        )
    if kind == "absent_header":
        exists, _ = _header_value(response, check.get("header"))
        success = not exists
        return Evaluation(success, "Header ausente verificado" if success else "El header no debería estar presente", dict(check))
    if kind == "json":
        body = _response_body(response)
        if body is None:
            return Evaluation(False, "La respuesta no tiene JSON", dict(check))
        exists, actual = _json_path(body, check.get("path"))
        if not exists:
            return Evaluation(False, "El path JSON no existe en la respuesta", dict(check))
        expected = check.get("value")
        success = actual == expected or str(actual) == str(expected)
        return Evaluation(success, "JSON verificado" if success else "El valor JSON no coincide", dict(check))
    if kind == "browser_dataset":
        # This is intentionally a separate namespace. A browser probe may
        # report a benign lab observation, but request echoes and response
        # bodies must never be accepted as a substitute for that observation.
        if "browser_dataset" not in response:
            return Evaluation(False, "El runner no devolvió browser_dataset", dict(check))
        exists, actual = _dataset_path(response.get("browser_dataset"), check.get("path"))
        if not exists:
            return Evaluation(False, "El path browser_dataset no existe", dict(check))
        expected = check.get("value")
        success = actual == expected or str(actual) == str(expected)
        return Evaluation(
            success,
            "Evidencia del navegador verificada" if success else "El dataset del navegador no coincide",
            dict(check),
        )
    if kind == "all":
        children = check.get("checks")
        if not isinstance(children, list) or not children:
            return Evaluation(False, "El grupo all no tiene checks", dict(check))
        results = [evaluate_response(response, child) for child in children]
        success = all(result.success for result in results)
        message = "Todos los criterios fueron verificados" if success else next(
            (result.message for result in results if not result.success), "Falló un criterio"
        )
        return Evaluation(success, message, dict(check))
    return Evaluation(False, "Tipo de criterio no implementado", dict(check))


def response_evidence(response: Mapping[str, Any]) -> dict[str, Any]:
    """Return a bounded, non-command view suitable for API and event storage."""

    body = _response_body(response)
    if body is not None:
        body = body[:MAX_EVIDENCE_BODY]
    evidence = {
        "status": _status(response),
        "headers": {key: value[:1024] for key, value in _headers(response).items()},
        "body": body,
        "exit_code": _exit_code(response),
    }
    if isinstance(response.get("browser_dataset"), Mapping):
        # Dataset values are runner-produced, but still bounded before being
        # returned to the browser or persisted in SQLite.
        dataset: dict[str, Any] = {}
        for key, value in list(response["browser_dataset"].items())[:64]:
            if not isinstance(key, str):
                continue
            if isinstance(value, str):
                dataset[key[:128]] = value[:1_024]
            elif isinstance(value, (int, float, bool)) or value is None:
                dataset[key[:128]] = value
            else:
                dataset[key[:128]] = str(value)[:1_024]
        evidence["browser_dataset"] = dataset
    return evidence


def bounded_request_size(params: Mapping[str, Any], headers: Mapping[str, Any], body: Optional[str]) -> int:
    value = {"params": dict(params), "headers": dict(headers), "body": body or ""}
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
