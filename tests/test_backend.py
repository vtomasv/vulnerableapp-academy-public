from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# pytest installed outside the project can choose ``tests`` as import root;
# make the checkout location explicit without requiring a package marker.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from academy import app as backend
from academy import grading, tutor


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    catalog = {
        "families": [{"id": "test", "title": "Pruebas", "concept": "evidencia", "levels": []}],
        "missions": [
            {
                "id": "good",
                "title": "Contenido",
                "route": "Lab/GOOD",
                "method": "GET",
                "points": 10,
                "check": {"kind": "contains", "value": "VA_OK"},
            },
            {
                "id": "no200",
                "title": "No status genérico",
                "route": "Lab/NO200",
                "method": "GET",
                "points": 10,
                "check": {"kind": "contains", "value": "VA_OK"},
            },
            {
                "id": "manual",
                "title": "Manual",
                "route": "Lab/MANUAL",
                "method": "GET",
                "points": 50,
                "check": {"kind": "manual", "value": "revisión"},
            },
            {
                "id": "baseline",
                "title": "Control",
                "route": "Lab/BASE",
                "method": "GET",
                "points": 20,
                "check": {"kind": "contains", "value": "VA_GOOD"},
                "baseline": {
                    "route": "Lab/BASE",
                    "method": "GET",
                    "params": {"control": "1"},
                    "headers": {},
                    "body": None,
                    "content_type": None,
                    "check": {"kind": "not_contains", "value": "VA_GOOD"},
                },
            },
            {
                "id": "cache",
                "title": "Cache",
                "route": "Lab/CACHE",
                "method": "GET",
                "points": 25,
                "before": [
                    {
                        "route": "Lab/CACHE",
                        "method": "GET",
                        "params": {"mode": "warm"},
                        "headers": {},
                        "body": None,
                        "content_type": None,
                    }
                ],
                "probe": {
                    "route": "Lab/CACHE",
                    "method": "GET",
                    "params": {"visitor": "1"},
                    "headers": {},
                    "body": None,
                    "content_type": None,
                },
                "check": {"kind": "contains", "value": "VA_CACHED"},
            },
            {
                "id": "browser",
                "title": "Browser",
                "route": "Lab/XSS",
                "method": "GET",
                "tool": "browser_probe",
                "points": 15,
                "check": {"kind": "browser_dataset", "path": "vaLab", "value": "VA_XSS"},
            },
        ],
    }
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setattr(grading, "CATALOG_PATH", catalog_path)
    monkeypatch.setattr(backend, "DB", backend.Database(tmp_path / "academy.sqlite3"))
    monkeypatch.setattr(backend, "rate_limiter", backend.RateLimiter())
    secret_path = tmp_path / "harness.key"
    secret_path.write_text("unit-test-runner-key\n", encoding="utf-8")
    monkeypatch.setattr(backend, "HARNESS_KEY_PATH", secret_path)
    with TestClient(backend.app) as test_client:
        yield test_client


def register(client: TestClient, username: str = "alice") -> dict:
    response = client.post(
        "/api/auth/register", json={"username": username, "password": "correct-horse-123"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def request_json(mission_id: str, method: str = "GET", **kwargs) -> dict:
    value = {"method": method, "params": {}, "headers": {}, "body": None, "content_type": None}
    value.update(kwargs)
    return {"mission_id": mission_id, "request": value}


def response(body: str = "", status: int = 200, headers: dict | None = None, **extra) -> dict:
    return {
        "status": status,
        "headers": headers or {},
        "body": body,
        "command": "echo VA_OK",
        "exit_code": 0,
        **extra,
    }


def test_authentication_and_user_isolation(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    alice = register(client, "alice")
    bob = register(client, "bob")
    assert len(alice["token"]) >= 32
    assert client.get("/api/me").status_code == 401

    async def fake_runner(arguments, tool="http_request"):
        return response("VA_OK")

    monkeypatch.setattr(backend, "execute_runner", fake_runner)
    headers = {"Authorization": f"Bearer {alice['token']}"}
    attempt = client.post("/api/attempt", headers=headers, json=request_json("good"))
    assert attempt.status_code == 200
    assert attempt.json()["success"] is True
    assert attempt.json()["awarded"] == 10
    assert client.get("/api/me", headers=headers).json()["completed"] == ["good"]
    bob_me = client.get("/api/me", headers={"Authorization": f"Bearer {bob['token']}"}).json()
    assert bob_me["completed"] == []
    assert bob_me["score"] == 0


def test_scoring_is_idempotent_manual_and_200_without_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_runner(arguments, tool="http_request"):
        path = arguments["path"]
        if path.endswith("NO200"):
            return response("Invalid credentials")
        if path.endswith("MANUAL"):
            return response("revisión")
        return response("VA_OK")

    monkeypatch.setattr(backend, "execute_runner", fake_runner)
    auth = register(client)["token"]
    headers = {"Authorization": f"Bearer {auth}"}
    first = client.post("/api/attempt", headers=headers, json=request_json("good")).json()
    second = client.post("/api/attempt", headers=headers, json=request_json("good")).json()
    assert first["success"] is True and first["awarded"] == 10
    assert second["success"] is True and second["awarded"] == 0
    no200 = client.post("/api/attempt", headers=headers, json=request_json("no200")).json()
    manual = client.post("/api/attempt", headers=headers, json=request_json("manual")).json()
    assert no200["success"] is False and no200["score"] == 10
    assert manual["success"] is False and manual["awarded"] == 0
    assert client.get("/api/me", headers=headers).json()["maximum"] == 80


def test_baseline_and_fixed_cache_sequence(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def fake_runner(arguments, tool="http_request"):
        calls.append((tool, dict(arguments)))
        path = arguments["path"]
        if path.endswith("BASE"):
            return response("control" if arguments["params"].get("control") == "1" else "VA_GOOD")
        if path.endswith("CACHE"):
            if arguments["params"].get("mode") == "warm":
                return response("warm")
            if arguments["params"].get("visitor") == "1":
                return response("VA_CACHED")
            return response("VA_ATTACK")
        return response()

    monkeypatch.setattr(backend, "execute_runner", fake_runner)
    auth = register(client)["token"]
    headers = {"Authorization": f"Bearer {auth}"}
    baseline_result = client.post(
        "/api/attempt", headers=headers, json=request_json("baseline", params={"control": "client"})
    ).json()
    assert baseline_result["success"] is True
    assert baseline_result["awarded"] == 20
    assert calls[0][1]["params"] == {"control": "1"}
    calls.clear()
    cache_result = client.post("/api/attempt", headers=headers, json=request_json("cache")).json()
    assert cache_result["success"] is True and cache_result["awarded"] == 25
    assert [item[1]["params"] for item in calls] == [{"mode": "warm"}, {}, {"visitor": "1"}]
    assert set(cache_result["evidence"]) >= {"before", "attack", "probe"}


def test_limits_browser_dataset_and_fixed_target(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def fake_runner(arguments, tool="http_request"):
        calls.append((tool, dict(arguments)))
        return response("ignored", browser_dataset={"vaLab": "VA_XSS"})

    monkeypatch.setattr(backend, "execute_runner", fake_runner)
    auth = register(client)["token"]
    headers = {"Authorization": f"Bearer {auth}"}
    browser = client.post(
        "/api/attempt",
        headers=headers,
        json=request_json("browser", method="GET", params={"value": "benign-marker"}),
    )
    assert browser.status_code == 200 and browser.json()["success"] is True
    assert calls[0][0] == "browser_probe"
    assert calls[0][1] == {"path": "/VulnerableApp/Lab/XSS", "params": {"value": "benign-marker"}}
    assert client.post("/api/attempt", headers=headers, json=request_json("browser", method="POST")).status_code == 400
    too_large = client.post(
        "/api/attempt", headers=headers, json=request_json("good", body="x" * (16 * 1024 + 1))
    )
    assert too_large.status_code in {413, 422}
    assert client.post("/api/attempt", headers=headers, json=request_json("good", method="POST")).status_code == 400


def test_verifiers_status_paths_headers_all_and_no_command_echo() -> None:
    assert grading.evaluate_response(
        response("", status=200, headers={}), {"kind": "absent_header", "header": "Location", "status": 200}
    ).success
    assert grading.evaluate_response(
        response("", status=200, headers={"Set-Cookie": "JWT=abc; HttpOnly"}),
        {"kind": "header_contains", "header": "Set-Cookie", "value": "httponly"},
    ).success
    assert not grading.evaluate_response(
        response("", status=404), {"kind": "not_contains", "value": "VA_OK"}
    ).success
    assert grading.evaluate_response(
        response("", status=404), {"kind": "not_contains", "value": "VA_OK", "status": 404}
    ).success
    body = json.dumps({"content": "VA_OK", "nested": "{\"flag\":true}"})
    all_check = {"kind": "all", "checks": [{"kind": "contains", "path": "$.content", "value": "VA_OK"}, {"kind": "json", "path": "nested.flag", "value": True}]}
    assert grading.evaluate_response(response(body), all_check).success
    assert not grading.evaluate_response(response("no marker", **{"command": "VA_OK"}), {"kind": "contains", "value": "VA_OK"}).success


def test_tutor_proposes_only_safe_tools_and_approval_does_not_score(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_tutor(mission, message):
        return {
            "message": {
                "content": json.dumps(
                    {
                        "reply": "Observa primero los headers.",
                        "tools": [
                            {"tool": "inspect_headers", "arguments": {"path": "/evil"}, "explanation": "control"},
                            {"tool": "browser_probe", "arguments": {}},
                        ],
                    }
                )
            }
        }

    async def fake_runner(arguments, tool="http_request"):
        return response("tool output", headers={"X-Test": "yes"})

    monkeypatch.setattr(tutor, "ask_ollama", fake_tutor)
    monkeypatch.setattr(backend, "execute_runner", fake_runner)
    auth = register(client)["token"]
    headers = {"Authorization": f"Bearer {auth}"}
    tutor_result = client.post(
        "/api/tutor", headers=headers, json={"mission_id": "good", "message": "¿Qué observo?", "allow_tools": False}
    )
    assert tutor_result.status_code == 200
    pending = tutor_result.json()["pending_tools"]
    assert len(pending) == 1 and pending[0]["tool"] == "inspect_headers"
    assert pending[0]["arguments"]["path"] == "/VulnerableApp/Lab/GOOD"
    approved = client.post("/api/tutor/approve", headers=headers, json={"pending_id": pending[0]["id"]})
    assert approved.status_code == 200
    assert approved.json()["audit"][0]["status"] == 200
    assert client.get("/api/me", headers=headers).json()["score"] == 0


def test_export_preserves_more_than_twenty_completions(client: TestClient) -> None:
    account = register(client, 'export_student')
    for index in range(35):
        backend.DB.record_attempt(account['user']['id'], f'completed-{index:02d}', True, 10, 'ok', {}, {})
    headers = {'Authorization': f"Bearer {account['token']}"}
    data = client.get('/api/export', headers=headers).json()
    assert len(data['completed']) == 35
    assert data['score'] == 350


def test_tutor_approval_revalidates_parameter_count(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    account = register(client, 'tool_student')
    backend.DB.add_pending('oversized-proposal', account['user']['id'], 'good', 'lab_request',
                           {'params': {f'p{x}': 'v' for x in range(129)}, 'headers': {}}, 'prueba')
    called = []
    async def fake_runner(arguments, tool='http_request'):
        called.append(arguments)
        return response('VA_OK')
    monkeypatch.setattr(backend, 'execute_runner', fake_runner)
    headers = {'Authorization': f"Bearer {account['token']}"}
    result = client.post('/api/tutor/approve', headers=headers,
                         json={'pending_id': 'oversized-proposal'}).json()
    assert not called
    assert 'error' in result['audit'][0]


def test_store_is_the_landing_page_and_api_routes_keep_precedence(client: TestClient) -> None:
    assert "Mercado Cordillera" in client.get("/").text
    for asset in ("/store.js", "/store.css", "/contexts.json", "/assets/mochila.jpg"):
        assert client.get(asset).status_code == 200
    assert client.get("/api/catalog").json()["missions"][0]["id"] == "good"
    assert client.get("/static/app.js").status_code == 404
    assert client.get("/VulnerableApp/").status_code == 404


def test_native_ollama_tool_calls_are_pending_and_allowlisted() -> None:
    data = {'message': {'content': '', 'tool_calls': [
        {'function': {'name': 'inspect_headers', 'arguments': {}}},
        {'function': {'name': 'shell', 'arguments': {'command': 'anything'}}}]}}
    reply, proposals = tutor.normalize_proposals(data, {'id': 'test', 'route': 'Lab/GOOD', 'method': 'GET'})
    assert len(proposals) == 1 and proposals[0].tool == 'inspect_headers'
    assert proposals[0].arguments == {}
