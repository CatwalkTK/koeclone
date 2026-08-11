from pathlib import Path

from fastapi.testclient import TestClient

from koeclone.api.app import create_app
from koeclone.config import AppConfig
from koeclone.engines.fake import FakeEngine


def _client(tmp_path: Path) -> TestClient:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("koeclone", encoding="utf-8")
    app = create_app(
        AppConfig(data_dir=tmp_path / "data", engine="fake"),
        engine=FakeEngine(),
        web_dir=web,
    )
    return TestClient(app)


def test_challenge_returns_consent_text(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/consent/challenge")

    assert response.status_code == 200
    assert isinstance(response.json()["consent_text"], str)
    assert response.json()["consent_text"]


def test_challenge_differs_between_requests(tmp_path: Path) -> None:
    client = _client(tmp_path)

    challenges = {
        client.get("/api/consent/challenge").json()["consent_text"] for _ in range(10)
    }

    assert len(challenges) >= 2
