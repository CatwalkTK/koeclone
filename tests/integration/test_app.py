import asyncio
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from koeclone.api.app import create_app
from koeclone.config import AppConfig
from koeclone.engines.fake import FakeEngine
from koeclone.errors import ErrorCode, KoecloneError


def _client(tmp_path: Path, *, docs: bool = False) -> tuple[TestClient, FakeEngine]:
    web = tmp_path / "web"
    web.mkdir(parents=True)
    (web / "index.html").write_text("<h1>koeclone</h1>", encoding="utf-8")
    engine = FakeEngine()
    app = create_app(
        AppConfig(data_dir=tmp_path / "data", engine="fake"),
        engine=engine,
        docs_enabled=docs,
        web_dir=web,
    )
    return TestClient(app), engine


def test_health_returns_ok_without_loading_model(tmp_path: Path) -> None:
    client, engine = _client(tmp_path)
    response = client.get("/api/health")
    assert response.json() == {
        "status": "ok",
        "app_version": "0.1.0",
        "engine": "fake",
        "model_loaded": False,
    }
    assert engine.load_count == 0


def test_no_cors_headers_are_exposed(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    response = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_request_body_over_50mb_is_rejected(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    response = client.post("/api/unknown", content=b"x" * (52_428_800 + 1))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "ERR_REQUEST_TOO_LARGE"


def test_request_body_limit_stops_spoofed_stream(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    app = client.app

    async def consume(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    app.add_api_route("/api/_test/consume", consume, methods=["POST"])
    app.router.routes.insert(0, app.router.routes.pop())
    pulled = 0
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        nonlocal pulled
        pulled += 1_048_576
        return {"type": "http.request", "body": b"x" * 1_048_576, "more_body": True}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/_test/consume",
        "raw_path": b"/api/_test/consume",
        "query_string": b"",
        "headers": [(b"content-length", b"10")],
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 8000),
    }
    asyncio.run(client.app(scope, receive, send))  # type: ignore[arg-type]
    start = next(
        message for message in sent if message["type"] == "http.response.start"
    )
    assert start["status"] == 413
    assert pulled <= 52_428_800 + 1_048_576


def test_error_response_shape_is_stable(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    response = client.get("/api/unknown")
    assert response.status_code == 404
    assert set(response.json()) == {"error"}
    assert set(response.json()["error"]) == {"code", "message", "error_id"}
    assert response.json()["error"]["code"] == "ERR_ROUTE_NOT_FOUND"
    assert "detail" not in response.json()


def test_method_not_allowed_keeps_405_status(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    response = client.post("/api/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "ERR_ROUTE_NOT_FOUND"


def test_internal_error_hides_details_and_returns_error_id(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    app = client.app

    async def fail() -> None:
        raise KoecloneError(ErrorCode.ERR_INTERNAL)

    app.add_api_route("/api/_test/internal", fail)
    app.router.routes.insert(0, app.router.routes.pop())
    response = client.get("/api/_test/internal")
    payload = response.json()["error"]
    assert response.status_code == 500
    UUID(payload["error_id"])
    assert "path" not in payload["message"].casefold()


def test_unexpected_error_uses_stable_internal_shape(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    client = TestClient(client.app, raise_server_exceptions=False)

    async def fail() -> None:
        raise RuntimeError("secret path /private/data")

    client.app.add_api_route("/api/_test/unexpected", fail)
    client.app.router.routes.insert(0, client.app.router.routes.pop())
    response = client.get("/api/_test/unexpected")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "ERR_INTERNAL"
    UUID(response.json()["error"]["error_id"])
    assert "secret" not in response.text


def test_openapi_is_disabled_by_default(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    enabled, _ = _client(tmp_path / "enabled", docs=True)
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404
    assert enabled.get("/openapi.json").status_code == 200
    assert enabled.get("/docs").status_code == 200


def test_static_web_directory_is_served(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_invalid_uuid_path_becomes_bad_request(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    app = client.app

    async def uuid_route(value: UUID) -> dict[str, str]:
        return {"value": str(value)}

    app.add_api_route("/api/_test/uuid/{value}", uuid_route)
    app.router.routes.insert(0, app.router.routes.pop())
    response = client.get("/api/_test/uuid/not-a-uuid")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ERR_BAD_REQUEST"


def test_run_script_binds_loopback_only() -> None:
    script = (Path(__file__).parents[2] / "scripts" / "run.sh").read_text()
    assert "127.0.0.1" in script
    assert "0.0.0.0" not in script
    assert "${KOECLONE_HOST" not in script


def test_app_config_host_cannot_be_overridden_by_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KOECLONE_HOST", "0.0.0.0")
    assert AppConfig.from_env().host == "127.0.0.1"
