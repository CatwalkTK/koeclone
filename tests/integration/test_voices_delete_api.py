from __future__ import annotations

import io
import math
import struct
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from koeclone.api.app import create_app
from koeclone.config import AppConfig
from koeclone.engines.fake import FakeEngine
from koeclone.storage.files import storage_path


def _wav(duration: float) -> bytes:
    sample_rate = 24_000
    frames = [
        round(3_000 * math.sin(2 * math.pi * 440 * index / sample_rate))
        for index in range(round(duration * sample_rate))
    ]
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(struct.pack(f"<{len(frames)}h", *frames))
    return output.getvalue()


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("koeclone", encoding="utf-8")
    app = create_app(
        AppConfig(data_dir=tmp_path / "data", engine="fake"),
        engine=FakeEngine(),
        web_dir=web,
    )
    return TestClient(app)


def _create_profile(client: TestClient) -> tuple[dict[str, object], str]:
    validated = client.post(
        "/api/voices",
        data={
            "stage": "validate",
            "source_mode": "file_upload",
            "consent_accepted": "true",
            "consent_text": "自分の声の登録に同意します。",
        },
        files={"audio": ("voice.wav", _wav(12), "audio/wav")},
    )
    assert validated.status_code == 200
    confirmed = client.post(
        "/api/voices",
        data={
            "stage": "confirm",
            "draft_id": validated.json()["draft_id"],
            "consent_accepted": "true",
            "display_name": "私の声",
        },
    )
    assert confirmed.status_code == 201
    payload = confirmed.json()
    job_id = payload["test_synthesis_id"]
    client.app.state.queue.wait_for(job_id)
    return payload["voice"], job_id


def _code(response) -> str:
    return response.json()["error"]["code"]


def test_get_current_returns_404_when_absent(client: TestClient) -> None:
    response = client.get("/api/voices/current")
    assert response.status_code == 404
    assert _code(response) == "ERR_PROFILE_NOT_FOUND"


def test_get_current_returns_profile_without_secrets(client: TestClient) -> None:
    expected, _ = _create_profile(client)
    response = client.get("/api/voices/current")
    assert response.status_code == 200
    assert response.json() == expected
    assert "path" not in response.text
    assert "sha256" not in response.text
    assert "consent_text" not in response.text


def test_delete_removes_profile_and_all_generated_files(client: TestClient) -> None:
    _, _ = _create_profile(client)
    profile = client.app.state.database.get_current_voice_profile()
    assert profile is not None
    storage_path(client.app.state.paths.consent, profile.id, ".wav").write_bytes(
        _wav(1)
    )
    storage_path(client.app.state.paths.cache, profile.id, ".cache").write_bytes(
        b"cache"
    )
    storage_path(
        client.app.state.paths.temporary,
        "00000000-0000-4000-8000-000000000001",
        ".tmp",
    ).write_bytes(b"temporary")

    response = client.delete("/api/voices/current")
    assert response.status_code == 204
    assert response.content == b""
    assert list(client.app.state.paths.root.rglob("*.wav")) == []
    assert list(client.app.state.paths.root.rglob("*.json")) == []
    assert list(client.app.state.paths.root.rglob("*.cache")) == []
    assert list(client.app.state.paths.root.rglob("*.tmp")) == []


def test_delete_removes_database_rows(client: TestClient) -> None:
    _create_profile(client)
    assert client.delete("/api/voices/current").status_code == 204
    assert client.app.state.database.get_current_voice_profile() is None
    assert client.app.state.database.list_synthesis_jobs() == []


def test_endpoints_return_404_after_delete(client: TestClient) -> None:
    _, job_id = _create_profile(client)
    assert client.delete("/api/voices/current").status_code == 204
    assert client.get("/api/voices/current").status_code == 404
    assert client.get(f"/api/syntheses/{job_id}").status_code == 404
    assert client.get(f"/api/syntheses/{job_id}/audio").status_code == 404


def test_delete_is_404_when_absent(client: TestClient) -> None:
    response = client.delete("/api/voices/current")
    assert response.status_code == 404
    assert _code(response) == "ERR_PROFILE_NOT_FOUND"
