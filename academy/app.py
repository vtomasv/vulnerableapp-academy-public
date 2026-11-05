"""Backend FastAPI de VulnerableApp Academy.

El servidor es deliberadamente un gateway: jamás llama directamente al
objetivo vulnerable. Toda solicitud de laboratorio pasa por el runner de Kali,
cuya credencial se lee de un archivo montado en runtime.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from .auth import TokenRecord, hash_password, parse_bearer, token_digest, verify_password
from .grading import (
    CatalogError,
    bounded_request_size,
    catalog_copy,
    evaluate_response,
    mission_by_id,
    mission_methods,
    mission_points,
    response_evidence,
    target_path,
)
from . import tutor


DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "academy.sqlite3"
RUNNER_URL = os.getenv("KALI_RUNNER_URL", "http://kali:9001").rstrip("/")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "huihui_ai/qwen3-abliterated:4b-v2-q4_K_M")
HARNESS_KEY_PATH = Path(os.getenv("HARNESS_KEY_PATH", "/run/academy-secrets/harness.key"))
TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
PENDING_TTL_SECONDS = 5 * 60
MAX_BODY = 16 * 1024
MAX_INPUT_COLLECTION = 16 * 1024
MAX_API_OUTPUT = 32 * 1024
_RUNNER_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
_USERNAME_RE = re.compile(r"^[^\s\x00-\x1f\x7f]{3,32}$")


class RunnerUnavailable(RuntimeError):
    pass


class RateLimiter:
    """Small in-process sliding-window limiter for auth and tutor endpoints."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[tuple[str, str], list[float]] = {}

    def allow(self, scope: str, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        bucket_key = (scope, key)
        with self._lock:
            values = [item for item in self._events.get(bucket_key, []) if item > now - window]
            if len(values) >= limit:
                self._events[bucket_key] = values
                return False
            values.append(now)
            self._events[bucket_key] = values
            return True


rate_limiter = RateLimiter()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Docker creates/chowns /data before running uid 1001. A local
            # source checkout may not be allowed to create /data; use a
            # clearly non-source fallback only for that development case.
            fallback = Path(os.getenv("TMPDIR", "/tmp")) / "vulnerableapp-academy-data"
            fallback.mkdir(parents=True, exist_ok=True)
            self.path = fallback / "academy.sqlite3"
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tokens_user ON tokens(user_id);
                CREATE TABLE IF NOT EXISTS completions (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    mission_id TEXT NOT NULL,
                    points INTEGER NOT NULL,
                    completed_at INTEGER NOT NULL,
                    PRIMARY KEY(user_id, mission_id)
                );
                CREATE TABLE IF NOT EXISTS attempt_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    mission_id TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    awarded INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_attempt_events_user ON attempt_events(user_id, id DESC);
                CREATE TABLE IF NOT EXISTS pending_tools (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    mission_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_pending_user ON pending_tools(user_id, created_at DESC);
                """
            )

    def create_user(self, username: str, password: str) -> Optional[dict[str, Any]]:
        now = int(time.time())
        encoded = hash_password(password)
        try:
            with self.connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",
                    (username, encoded, now),
                )
                user_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError:
            return None
        return {"id": user_id, "username": username}

    def get_user_by_username(self, username: str) -> Optional[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()

    def issue_token(self, user_id: int) -> TokenRecord:
        token = TokenRecord.create()
        now = int(time.time())
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO tokens(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)",
                (token.digest, user_id, now, now + TOKEN_TTL_SECONDS),
            )
        return token

    def user_by_token(self, token: str) -> Optional[dict[str, Any]]:
        now = int(time.time())
        digest = token_digest(token)
        with self.connect() as connection:
            connection.execute("DELETE FROM tokens WHERE expires_at <= ?", (now,))
            row = connection.execute(
                "SELECT users.id, users.username FROM tokens JOIN users ON users.id=tokens.user_id "
                "WHERE tokens.token_hash=? AND tokens.expires_at>?",
                (digest, now),
            ).fetchone()
        return dict(row) if row else None

    def record_attempt(
        self,
        user_id: int,
        mission_id: str,
        success: bool,
        points: int,
        message: str,
        evidence: Mapping[str, Any],
        request_summary: Mapping[str, Any],
    ) -> int:
        """Record an event and award a completion atomically exactly once."""

        now = int(time.time())
        awarded = 0
        evidence_text = json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))[:MAX_API_OUTPUT]
        request_text = json.dumps(request_summary, ensure_ascii=False, separators=(",", ":"))[:8_192]
        with self.connect() as connection:
            event_cursor = connection.execute(
                "INSERT INTO attempt_events(user_id,mission_id,success,awarded,message,evidence_json,request_json,created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (user_id, mission_id, int(success), 0, message[:1_000], evidence_text, request_text, now),
            )
            if success and points > 0:
                cursor = connection.execute(
                    "INSERT OR IGNORE INTO completions(user_id,mission_id,points,completed_at) VALUES(?,?,?,?)",
                    (user_id, mission_id, points, now),
                )
                if cursor.rowcount == 1:
                    awarded = points
                    connection.execute(
                        "UPDATE attempt_events SET awarded=? WHERE id=?", (awarded, event_cursor.lastrowid)
                    )
        return awarded

    def progress(self, user_id: int, catalog: Mapping[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            completed_rows = connection.execute(
                "SELECT mission_id FROM completions WHERE user_id=? ORDER BY completed_at, mission_id", (user_id,)
            ).fetchall()
            score_row = connection.execute(
                "SELECT COALESCE(SUM(points),0) AS score FROM completions WHERE user_id=?", (user_id,)
            ).fetchone()
            event_rows = connection.execute(
                "SELECT mission_id,success,awarded,message,evidence_json,created_at FROM attempt_events "
                "WHERE user_id=? ORDER BY id DESC LIMIT 20",
                (user_id,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in event_rows:
            try:
                evidence = json.loads(row["evidence_json"])
            except (TypeError, ValueError, json.JSONDecodeError):
                evidence = {}
            events.append(
                {
                    "mission_id": row["mission_id"],
                    "success": bool(row["success"]),
                    "awarded": int(row["awarded"]),
                    "message": row["message"],
                    "evidence": evidence,
                    "created_at": row["created_at"],
                }
            )
        maximum = sum(mission_points(mission) for mission in catalog.get("missions", []) if isinstance(mission, dict))
        return {
            "score": int(score_row["score"] if score_row else 0),
            "maximum": maximum,
            "completed": [row["mission_id"] for row in completed_rows],
            "events": events,
        }

    def add_pending(
        self,
        pending_id: str,
        user_id: int,
        mission_id: str,
        tool: str,
        arguments: Mapping[str, Any],
        explanation: str,
    ) -> None:
        now = int(time.time())
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO pending_tools(id,user_id,mission_id,tool,arguments_json,explanation,created_at,expires_at,used) "
                "VALUES(?,?,?,?,?,?,?,?,0)",
                (
                    pending_id,
                    user_id,
                    mission_id,
                    tool,
                    json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
                    explanation[:500],
                    now,
                    now + PENDING_TTL_SECONDS,
                ),
            )

    def claim_pending(self, user_id: int, pending_id: str) -> Optional[dict[str, Any]]:
        now = int(time.time())
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM pending_tools WHERE id=? AND user_id=? AND used=0 AND expires_at>?",
                (pending_id, user_id, now),
            ).fetchone()
            if row is None:
                return None
            cursor = connection.execute(
                "UPDATE pending_tools SET used=1 WHERE id=? AND user_id=? AND used=0 AND expires_at>?",
                (pending_id, user_id, now),
            )
            if cursor.rowcount != 1:
                return None
        value = dict(row)
        try:
            value["arguments"] = json.loads(value.pop("arguments_json"))
        except (ValueError, TypeError, json.JSONDecodeError):
            value["arguments"] = {}
        return value


DB = Database(DB_PATH)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthInput(StrictModel):
    username: StrictStr = Field(min_length=3, max_length=32)
    password: StrictStr = Field(min_length=8, max_length=128)


class LabRequest(StrictModel):
    method: StrictStr = Field(min_length=1, max_length=16)
    params: dict[StrictStr, StrictStr] = Field(default_factory=dict)
    headers: dict[StrictStr, StrictStr] = Field(default_factory=dict)
    body: Optional[StrictStr] = Field(default=None, max_length=MAX_BODY)
    content_type: Optional[StrictStr] = Field(default=None, max_length=256)


class AttemptInput(StrictModel):
    mission_id: StrictStr = Field(min_length=1, max_length=128)
    request: LabRequest


class TutorInput(StrictModel):
    mission_id: StrictStr = Field(min_length=1, max_length=128)
    message: StrictStr = Field(min_length=1, max_length=tutor.MAX_MESSAGE)
    allow_tools: bool = False


class ApproveInput(StrictModel):
    pending_id: Optional[StrictStr] = Field(default=None, min_length=1, max_length=128)
    pending_ids: list[StrictStr] = Field(default_factory=list, max_length=3)


app = FastAPI(title="VulnerableApp Academy", docs_url=None, redoc_url=None, openapi_url=None)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _catalog_or_500() -> dict[str, Any]:
    try:
        return catalog_copy()
    except CatalogError as exc:
        raise HTTPException(status_code=500, detail="El catálogo del laboratorio no es válido") from exc


def _safe_user(row: Mapping[str, Any]) -> dict[str, Any]:
    return {"id": int(row["id"]), "username": str(row["username"])}


def _auth_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autenticación requerida",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def current_user(authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    token = parse_bearer(authorization)
    if token is None:
        raise _auth_error()
    user = DB.user_by_token(token)
    if user is None:
        raise _auth_error()
    return user


def _validate_username(username: str) -> str:
    username = username.strip()
    if not _USERNAME_RE.fullmatch(username):
        raise HTTPException(status_code=400, detail="Usuario inválido (3-32 caracteres sin espacios)")
    return username


def _validate_lab_input(request: LabRequest, mission: Mapping[str, Any]) -> tuple[str, dict[str, str], dict[str, str], Optional[str], Optional[str]]:
    methods = mission_methods(mission)
    method = request.method.upper()
    if not methods or method not in methods:
        raise HTTPException(status_code=400, detail="El método no coincide con la misión")
    if len(request.params) > 128 or len(request.headers) > 128:
        raise HTTPException(status_code=413, detail="Demasiados parámetros o headers")
    for key, value in [*request.params.items(), *request.headers.items()]:
        if len(key) > 256 or len(value) > 8_192 or "\x00" in key:
            raise HTTPException(status_code=413, detail="Parámetro o header fuera de límites")
    for key, value in request.headers.items():
        if any(ord(c) < 32 for c in value):
            raise HTTPException(status_code=400, detail="Header con caracteres de control")
    if request.body is not None and len(request.body.encode("utf-8")) > MAX_BODY:
        raise HTTPException(status_code=413, detail="Body demasiado grande")
    if bounded_request_size(request.params, request.headers, request.body) > MAX_INPUT_COLLECTION:
        raise HTTPException(status_code=413, detail="Solicitud de laboratorio demasiado grande")
    return method, dict(request.params), dict(request.headers), request.body, request.content_type


def _read_harness_key() -> str:
    try:
        value = HARNESS_KEY_PATH.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise RunnerUnavailable("Credencial del runner no disponible")
    if not value or len(value) > 512:
        raise RunnerUnavailable("Credencial del runner inválida")
    return value


async def execute_runner(arguments: Mapping[str, Any], tool: str = "http_request") -> dict[str, Any]:
    """Call only the private Kali runner, with redirects disabled."""

    key = _read_harness_key()
    arguments_value = dict(arguments)
    payload = {"tool": tool, "arguments": arguments_value}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=3.0), follow_redirects=False) as client:
            response = await client.post(
                RUNNER_URL + "/run",
                json=payload,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
        if response.status_code < 200 or response.status_code >= 300:
            raise RunnerUnavailable("El runner rechazó la solicitud")
        data = response.json()
    except RunnerUnavailable:
        raise
    except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RunnerUnavailable("No se pudo conectar con el runner") from exc
    if not isinstance(data, dict):
        raise RunnerUnavailable("El runner devolvió una respuesta inválida")
    return data


def _runner_arguments(mission: Mapping[str, Any], request: LabRequest) -> tuple[str, dict[str, Any]]:
    method, params, headers, body, content_type = _validate_lab_input(request, mission)
    return "http_request", {
        "path": target_path(mission),
        "method": method,
        "params": params,
        "headers": headers,
        "body": body,
        "content_type": content_type,
    }


def _browser_arguments(mission: Mapping[str, Any], route: Optional[Any] = None) -> dict[str, Any]:
    if route is None:
        path = target_path(mission)
    else:
        source = dict(mission)
        source["route"] = route
        path = target_path(source)
    # browser_probe performs a fixed GET internally and accepts only path and
    # params in the runner schema; neither field comes from the client.
    return {"path": path, "params": {}}


def _fixed_request_arguments(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Build a source-controlled before/probe request, never from the client."""

    if not isinstance(spec, Mapping):
        raise CatalogError("Solicitud fija inválida")
    route = spec.get("route")
    source = {"route": route}
    method = spec.get("method")
    if not isinstance(method, str) or method.upper() not in _RUNNER_METHODS:
        raise CatalogError("Método de solicitud fija inválido")
    params = spec.get("params", {})
    headers = spec.get("headers", {})
    body = spec.get("body")
    content_type = spec.get("content_type")
    if not isinstance(params, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in params.items()):
        raise CatalogError("Parámetros de solicitud fija inválidos")
    if not isinstance(headers, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in headers.items()):
        raise CatalogError("Headers de solicitud fija inválidos")
    if body is not None and (not isinstance(body, str) or len(body.encode("utf-8")) > MAX_BODY):
        raise CatalogError("Body de solicitud fija fuera de límites")
    if content_type is not None and not isinstance(content_type, str):
        raise CatalogError("Content type de solicitud fija inválido")
    if bounded_request_size(params, headers, body) > MAX_INPUT_COLLECTION:
        raise CatalogError("Solicitud fija fuera de límites")
    return {
        "path": target_path(source),
        "method": method.upper(),
        "params": params,
        "headers": headers,
        "body": body,
        "content_type": content_type,
    }


def _baseline_arguments(mission: Mapping[str, Any], baseline: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(baseline, Mapping):
        raise CatalogError("Baseline inválida")
    if mission.get("tool") == "browser_probe":
        return "browser_probe", _browser_arguments(mission, baseline.get("route", mission.get("route")))
    source = dict(mission)
    source["route"] = baseline.get("route", mission.get("route"))
    raw_method = baseline.get("method")
    methods = mission_methods(source)
    method = str(raw_method or (methods[0] if methods else "GET")).upper()
    if method not in methods:
        raise CatalogError("Método de baseline no permitido")
    params = baseline.get("params", {})
    headers = baseline.get("headers", {})
    body = baseline.get("body")
    content_type = baseline.get("content_type")
    if not isinstance(params, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in params.items()):
        raise CatalogError("Parámetros de baseline inválidos")
    if not isinstance(headers, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
        raise CatalogError("Headers de baseline inválidos")
    if body is not None and not isinstance(body, str):
        raise CatalogError("Body de baseline inválido")
    if content_type is not None and not isinstance(content_type, str):
        raise CatalogError("Content type de baseline inválido")
    if bounded_request_size(params, headers, body) > MAX_INPUT_COLLECTION or (body is not None and len(body.encode("utf-8")) > MAX_BODY):
        raise CatalogError("Baseline fuera de límites")
    return "http_request", {
        "path": target_path(source),
        "method": method,
        "params": params,
        "headers": headers,
        "body": body,
        "content_type": content_type,
    }


def _bounded_json(value: Any, limit: int = MAX_API_OUTPUT) -> Any:
    """Keep API responses below the output contract without exposing secrets."""

    def compact(item: Any, string_limit: int, list_limit: int) -> Any:
        if isinstance(item, dict):
            return {str(key)[:128]: compact(child, string_limit, list_limit) for key, child in item.items()}
        if isinstance(item, list):
            return [compact(child, string_limit, list_limit) for child in item[:list_limit]]
        if isinstance(item, str):
            return item[:string_limit]
        return item

    result = compact(value, 1_024, 20)

    def size(item: Any) -> int:
        try:
            return len(json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        except (TypeError, ValueError):
            return limit + 1

    if size(result) <= limit:
        return result
    result = compact(value, 256, 8)
    if size(result) <= limit:
        return result
    # Keep contract-critical scalar fields and a small amount of evidence;
    # this branch is reached only for unusually large runner/event payloads.
    if isinstance(result, dict):
        keep = {
            key: result[key]
            for key in ("success", "awarded", "message", "score", "user", "reply", "runner", "ollama")
            if key in result
        }
        if "evidence" in result:
            keep["evidence"] = result["evidence"]
        elif "events" in result:
            keep["events"] = result["events"][:1] if isinstance(result["events"], list) else []
        elif "audit" in result:
            keep["audit"] = result["audit"][:1] if isinstance(result["audit"], list) else []
        result = compact(keep, 128, 1)
    if size(result) <= limit:
        return result
    # The values above are all bounded; this final response remains valid JSON
    # even if a future endpoint adds a large, unexpected field.
    return {key: result[key] for key in ("success", "awarded", "message", "score") if key in result}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "academy"}


@app.post("/api/auth/register")
async def register(payload: AuthInput, request: Request) -> dict[str, Any]:
    if not rate_limiter.allow("auth", _client_key(request), 30):
        raise HTTPException(status_code=429, detail="Demasiados intentos de autenticación")
    username = _validate_username(payload.username)
    user = DB.create_user(username, payload.password)
    if user is None:
        raise HTTPException(status_code=409, detail="Ese usuario ya existe")
    token = DB.issue_token(int(user["id"]))
    return {"token": token.token, "user": user}


@app.post("/api/auth/login")
async def login(payload: AuthInput, request: Request) -> dict[str, Any]:
    if not rate_limiter.allow("auth", _client_key(request), 30):
        raise HTTPException(status_code=429, detail="Demasiados intentos de autenticación")
    username = _validate_username(payload.username)
    row = DB.get_user_by_username(username)
    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    token = DB.issue_token(int(row["id"]))
    return {"token": token.token, "user": {"id": int(row["id"]), "username": row["username"]}}


@app.get("/api/me")
async def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    progress = DB.progress(int(user["id"]), _catalog_or_500())
    return {"user": _safe_user(user), **progress}


@app.get("/api/catalog")
async def catalog() -> dict[str, Any]:
    return _catalog_or_500()


@app.post("/api/attempt")
async def attempt(payload: AttemptInput, user: dict[str, Any] = Depends(current_user)) -> JSONResponse:
    catalog_value = _catalog_or_500()
    mission = mission_by_id(catalog_value, payload.mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    tool_name = "browser_probe" if mission.get("tool") == "browser_probe" else "http_request"
    try:
        if tool_name == "browser_probe":
            method, params, headers, body, content_type = _validate_lab_input(payload.request, mission)
            if method != "GET" or headers or body is not None or content_type is not None:
                raise HTTPException(status_code=400, detail="La prueba de navegador solo acepta GET y parámetros de la misión")
            actual_arguments = {"path": target_path(mission), "params": params}
        else:
            _, actual_arguments = _runner_arguments(mission, payload.request)
        baseline = mission.get("baseline")
        executions: dict[str, Any] = {}
        if isinstance(baseline, Mapping):
            baseline_tool, baseline_arguments = _baseline_arguments(mission, baseline)
            executions["baseline"] = await execute_runner(baseline_arguments, baseline_tool)
            baseline_result = evaluate_response(executions["baseline"], baseline.get("check", {}))
        else:
            baseline_result = None
        # Cache exercises deliberately separate a server-controlled warm-up,
        # the student's attack request, and a fresh visitor probe. The probe
        # is fixed by the catalog and is the only response evaluated by the
        # mission check; a successful attack response alone is insufficient.
        before_specs = mission.get("before", [])
        if before_specs is not None and not isinstance(before_specs, list):
            raise CatalogError("before debe ser una lista")
        if before_specs:
            executions["before"] = []
            for fixed_spec in before_specs:
                fixed_arguments = _fixed_request_arguments(fixed_spec)
                executions["before"].append(await execute_runner(fixed_arguments, "http_request"))
        executions["attack"] = await execute_runner(actual_arguments, tool_name)
        probe_spec = mission.get("probe")
        if probe_spec is not None:
            if mission.get("probe_tool") == "browser_probe":
                probe_arguments = {"path": target_path(probe_spec), "params": probe_spec.get("params", {})}
                executions["probe"] = await execute_runner(probe_arguments, "browser_probe")
            else:
                probe_arguments = _fixed_request_arguments(probe_spec)
                executions["probe"] = await execute_runner(probe_arguments, "http_request")
            evaluated_response = executions["probe"]
        else:
            evaluated_response = executions["attack"]
        actual_result = evaluate_response(evaluated_response, mission.get("check", {}))
    except (RunnerUnavailable, CatalogError) as exc:
        message = "El laboratorio no está disponible" if isinstance(exc, RunnerUnavailable) else "La misión tiene una configuración inválida"
        evidence = {"error": message}
        points_awarded = DB.record_attempt(
            int(user["id"]), payload.mission_id, False, 0, message, evidence, {"method": payload.request.method}
        )
        progress = DB.progress(int(user["id"]), catalog_value)
        return JSONResponse(
            _bounded_json({"success": False, "awarded": points_awarded, "message": message, "evidence": evidence, "score": progress["score"]})
        )

    evidence: dict[str, Any] = response_evidence(evaluated_response)
    for key, value in executions.items():
        if key == "before" and isinstance(value, list):
            evidence[key] = [response_evidence(item) for item in value]
        elif isinstance(value, Mapping):
            evidence[key] = response_evidence(value)
    success = actual_result.success and (baseline_result is None or baseline_result.success)
    if baseline_result is not None and not baseline_result.success:
        message = "La condición baseline no se verificó; no se otorgan puntos"
    else:
        message = actual_result.message
    points = mission_points(mission) if success else 0
    request_summary = {
        "method": payload.request.method.upper(),
        "params_keys": sorted(payload.request.params.keys()),
        "header_keys": sorted(payload.request.headers.keys()),
        "body_length": len(payload.request.body.encode("utf-8")) if payload.request.body else 0,
    }
    points_awarded = DB.record_attempt(
        int(user["id"]), payload.mission_id, success, points, message, evidence, request_summary
    )
    progress = DB.progress(int(user["id"]), catalog_value)
    return JSONResponse(
        _bounded_json(
            {
                "success": success,
                "awarded": points_awarded,
                "message": message,
                "evidence": evidence,
                "score": progress["score"],
            }
        )
    )


@app.get("/api/export")
async def export_progress(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    progress = DB.progress(int(user["id"]), _catalog_or_500())
    # Las listas de completados no se recortan. El historial reciente se
    # exporta sin cuerpos extensos, manteniendo todos sus IDs y resultados.
    progress["events"] = [{k: v for k, v in event.items() if k not in {"evidence", "request"}}
                          for event in progress.get("events", [])]
    return {"user": _safe_user(user), **progress, "export_version": 1}


@app.post("/api/tutor")
async def tutor_chat(payload: TutorInput, request: Request, user: dict[str, Any] = Depends(current_user)) -> JSONResponse:
    if not rate_limiter.allow("tutor", _client_key(request), 20):
        raise HTTPException(status_code=429, detail="Demasiadas consultas al tutor")
    if payload.allow_tools:
        raise HTTPException(status_code=400, detail="Las herramientas requieren aprobación explícita")
    catalog_value = _catalog_or_500()
    mission = mission_by_id(catalog_value, payload.mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    try:
        model_data = await tutor.ask_ollama(mission, payload.message)
    except (tutor.TutorUnavailable, ValueError):
        raise HTTPException(status_code=503, detail="El tutor local no está disponible; no se simuló una respuesta")
    reply, proposals = tutor.normalize_proposals(model_data, mission)
    pending_tools: list[dict[str, Any]] = []
    # Browser probes are never exposed through tutor approvals.
    if mission.get("tool") != "browser_probe":
        for proposal in proposals[:3]:
            pending_id = __import__("secrets").token_urlsafe(18)
            DB.add_pending(
                pending_id,
                int(user["id"]),
                payload.mission_id,
                proposal.tool,
                proposal.arguments,
                proposal.explanation,
            )
            arguments = dict(proposal.arguments)
            if proposal.tool == "inspect_headers":
                arguments = {"path": target_path(mission)}
            pending_tools.append(
                {
                    "id": pending_id,
                    "tool": proposal.tool,
                    "arguments": arguments,
                    "explanation": proposal.explanation,
                }
            )
    audit = [{"event": "tutor_response", "mission_id": payload.mission_id, "proposed": len(pending_tools)}]
    return JSONResponse(_bounded_json({"reply": reply, "pending_tools": pending_tools, "audit": audit}))


@app.post("/api/tutor/approve")
async def tutor_approve(payload: ApproveInput, user: dict[str, Any] = Depends(current_user)) -> JSONResponse:
    ids: list[str] = []
    if payload.pending_id:
        ids.append(payload.pending_id)
    ids.extend(payload.pending_ids)
    ids = list(dict.fromkeys(ids))
    if not ids or len(ids) > 3:
        raise HTTPException(status_code=400, detail="Aprueba entre 1 y 3 herramientas pendientes")
    catalog_value = _catalog_or_500()
    audit: list[dict[str, Any]] = []
    for pending_id in ids:
        pending = DB.claim_pending(int(user["id"]), pending_id)
        if pending is None:
            audit.append({"pending_id": pending_id, "error": "Pendiente inexistente, usada o expirada"})
            continue
        mission = mission_by_id(catalog_value, pending["mission_id"])
        if mission is None or mission.get("tool") == "browser_probe":
            audit.append({"pending_id": pending_id, "tool": pending["tool"], "error": "Herramienta no permitida"})
            continue
        tool_name = pending["tool"]
        arguments = pending.get("arguments") if isinstance(pending.get("arguments"), dict) else {}
        try:
            if tool_name == "inspect_headers":
                runner_tool = "http_request"
                runner_arguments = {
                    "path": target_path(mission),
                    "method": (mission_methods(mission) or ["GET"])[0],
                    "params": {},
                    "headers": {},
                    "body": None,
                    "content_type": None,
                }
            elif tool_name == "lab_request":
                runner_tool = "http_request"
                proposed = LabRequest(method=(mission_methods(mission) or ["GET"])[0],
                                      params=arguments.get("params", {}),
                                      headers=arguments.get("headers", {}),
                                      body=arguments.get("body"),
                                      content_type=arguments.get("content_type"))
                _, runner_arguments = _runner_arguments(mission, proposed)
            else:
                raise ValueError("Herramienta no allowlisted")
            result = await execute_runner(runner_arguments, runner_tool)
            audit.append(
                {
                    "pending_id": pending_id,
                    "tool": tool_name,
                    "status": result.get("status"),
                    "evidence": response_evidence(result),
                }
            )
        except (RunnerUnavailable, CatalogError, ValueError, HTTPException):
            audit.append({"pending_id": pending_id, "tool": tool_name, "error": "No se pudo ejecutar la herramienta"})
    return JSONResponse(_bounded_json({"reply": "Herramientas aprobadas ejecutadas sin puntuar.", "pending_tools": [], "audit": audit}))


async def _service_status(url: str, path: str, headers: Optional[dict[str, str]] = None) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=3.0), follow_redirects=False) as client:
            response = await client.get(url + path, headers=headers or {})
        return {"ok": 200 <= response.status_code < 300, "status": response.status_code}
    except httpx.HTTPError:
        return {"ok": False, "status": None}


@app.get("/api/status")
async def service_status(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        key = _read_harness_key()
        runner_headers = {"Authorization": f"Bearer {key}"}
    except RunnerUnavailable:
        runner_headers = {}
    runner_result, ollama_result = await asyncio.gather(
        _service_status(RUNNER_URL, "/health", runner_headers),
        _service_status(OLLAMA_URL, "/api/tags"),
    )
    return {
        "runner": runner_result,
        "ollama": {**ollama_result, "model": OLLAMA_MODEL},
    }


# Serve the classroom storefront after the API routes so it cannot shadow them.
_STORE_DIR = Path(__file__).resolve().parent.parent / "target-ui" / "mercado"
app.mount("/", StaticFiles(directory=str(_STORE_DIR), html=True, check_dir=False), name="store")
