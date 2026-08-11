from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from koeclone.api.app import create_app
from koeclone.config import AppConfig
from koeclone.engines.fake import FakeEngine
from koeclone.storage.db import VoiceProfile
from koeclone.storage.files import storage_path

VOICE_ID = "11111111-1111-4111-8111-111111111111"


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
    reference = storage_path(app.state.paths.references, VOICE_ID, ".wav")
    reference.write_bytes(b"reference")
    app.state.database.create_voice_profile(
        VoiceProfile(
            id=VOICE_ID,
            display_name="自分の声",
            source_mode="file_upload",
            source_format="wav",
            source_sha256="source-hash",
            reference_path=str(reference),
            reference_sha256="reference-hash",
            consent_method="upload_declaration",
            consent_text="自分の声の登録に同意します。",
            consent_audio_path=None,
            consent_audio_sha256=None,
            created_at=datetime.now(UTC).isoformat(),
            engine="fake",
            model_version="fake-1",
        )
    )
    with TestClient(app) as test_client:
        yield test_client
    app.state.queue.shutdown()


def _create_job(
    client: TestClient,
    text: str,
    *,
    overrides: list[dict[str, object]] | None = None,
) -> str:
    response = client.post(
        "/api/syntheses",
        json={
            "text": text,
            "overrides": overrides or [],
            "ai_disclosure_acknowledged": True,
        },
    )
    assert response.status_code == 201
    job_id = response.json()["id"]
    client.app.state.queue.wait_for(job_id)
    return job_id


def _code(response) -> str:
    return response.json()["error"]["code"]


def test_history_is_sorted_newest_first(client: TestClient) -> None:
    job_ids = [_create_job(client, f"履歴の音声{i}。") for i in range(3)]
    response = client.get("/api/syntheses")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == list(reversed(job_ids))


def test_history_item_fields_match_requirements(client: TestClient) -> None:
    text = "声" * 100
    job_id = _create_job(
        client,
        text,
        overrides=[{"surface": "声", "start": 0, "end": 1, "reading": "こえ"}],
    )
    response = client.get("/api/syntheses")
    job = client.app.state.database.get_synthesis_job(job_id)
    assert job is not None
    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": job_id,
            "created_at": job.created_at,
            "text_preview": text[:80],
            "override_count": 1,
            "duration_ms": job.duration_ms,
            "status": "succeeded",
            "audio_available": True,
        }
    ]


def test_delete_single_removes_audio_and_sidecar(client: TestClient) -> None:
    retained_id = _create_job(client, "残す音声です。")
    deleted_id = _create_job(client, "削除する音声です。")
    audio = storage_path(client.app.state.paths.generated, deleted_id, ".wav")
    sidecar = storage_path(client.app.state.paths.generated, deleted_id, ".json")
    assert audio.is_file()
    assert sidecar.is_file()

    response = client.delete(f"/api/syntheses/{deleted_id}")
    assert response.status_code == 204
    assert response.content == b""
    assert not audio.exists()
    assert not sidecar.exists()
    assert client.app.state.database.get_synthesis_job(deleted_id) is None
    assert client.app.state.database.get_synthesis_job(retained_id) is not None


def test_delete_all_removes_every_job_but_keeps_profile(client: TestClient) -> None:
    job_ids = [_create_job(client, f"すべて削除{i}。") for i in range(2)]
    response = client.delete("/api/syntheses")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/api/syntheses").json() == {"items": []}
    assert client.get("/api/voices/current").status_code == 200
    for job_id in job_ids:
        assert not storage_path(
            client.app.state.paths.generated, job_id, ".wav"
        ).exists()
        assert not storage_path(
            client.app.state.paths.generated, job_id, ".json"
        ).exists()


def test_delete_unknown_job_returns_404(client: TestClient) -> None:
    response = client.delete("/api/syntheses/22222222-2222-4222-8222-222222222222")
    assert response.status_code == 404
    assert _code(response) == "ERR_JOB_NOT_FOUND"
