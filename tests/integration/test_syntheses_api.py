from __future__ import annotations

import re
from dataclasses import dataclass
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


@dataclass
class ApiSetup:
    client: TestClient
    engine: FakeEngine


@pytest.fixture
def api(tmp_path: Path) -> ApiSetup:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("koeclone", encoding="utf-8")
    engine = FakeEngine()
    app = create_app(
        AppConfig(data_dir=tmp_path / "data", engine="fake"),
        engine=engine,
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
    with TestClient(app) as client:
        yield ApiSetup(client, engine)
    app.state.queue.shutdown()


def _override(
    surface: str = "日本橋",
    start: int = 3,
    end: int = 6,
    reading: str = "にほんばし",
) -> dict[str, object]:
    return {"surface": surface, "start": start, "end": end, "reading": reading}


def _create(
    api: ApiSetup,
    *,
    text: str = "明日は日本橋へ行きます",
    overrides: list[dict[str, object]] | None = None,
    acknowledged: bool = True,
):
    return api.client.post(
        "/api/syntheses",
        json={
            "text": text,
            "overrides": overrides or [],
            "ai_disclosure_acknowledged": acknowledged,
        },
    )


def _code(response) -> str:
    return response.json()["error"]["code"]


class _HoldingQueue:
    def __init__(self) -> None:
        self.job_ids: list[str] = []

    def submit(self, job_id: str) -> None:
        self.job_ids.append(job_id)


def _hold_jobs(api: ApiSetup) -> object:
    original = api.client.app.state.queue
    api.client.app.state.queue = _HoldingQueue()
    return original


def test_preview_applies_overrides_without_changing_original(api: ApiSetup) -> None:
    response = api.client.post(
        "/api/syntheses/preview",
        json={
            "text": "明日は日本橋へ行きます",
            "overrides": [_override()],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["synthesis_text"] == "明日はにほんばしへ行きます"
    assert payload["original_segments"] == [
        {"text": "明日は", "override_index": None},
        {"text": "日本橋", "override_index": 0},
        {"text": "へ行きます", "override_index": None},
    ]
    assert payload["synthesis_segments"][1] == {
        "text": "にほんばし",
        "override_index": 0,
    }
    assert payload["override_count"] == 1
    assert payload["text_length"] == 11
    assert payload["synthesis_text_length"] == 13


def test_preview_rejects_invalid_reading(api: ApiSetup) -> None:
    response = api.client.post(
        "/api/syntheses/preview",
        json={
            "text": "明日は日本橋へ行きます",
            "overrides": [_override(reading="日本ばし")],
        },
    )
    assert response.status_code == 422
    assert _code(response) == "ERR_READING_INVALID_CHARS"


def test_preview_does_not_call_engine(api: ApiSetup) -> None:
    assert (
        api.client.post(
            "/api/syntheses/preview",
            json={"text": "音声の確認です。", "overrides": []},
        ).status_code
        == 200
    )
    assert api.engine.calls == []
    assert api.engine.load_count == 0


def test_create_rejects_whitespace_only_text(api: ApiSetup) -> None:
    response = _create(api, text=" \n\t")
    assert response.status_code == 422
    assert _code(response) == "ERR_TEXT_WHITESPACE_ONLY"
    assert api.engine.calls == []


def test_create_rejects_text_over_1000_chars(api: ApiSetup) -> None:
    response = _create(api, text="あ" * 1001)
    assert response.status_code == 422
    assert _code(response) == "ERR_TEXT_TOO_LONG"
    assert api.engine.calls == []


def test_create_rejects_synthesis_text_over_2000_chars(api: ApiSetup) -> None:
    response = _create(
        api,
        text="漢" * 1000,
        overrides=[_override("漢" * 1000, 0, 1000, "あ" * 2001)],
    )
    assert response.status_code == 422
    assert _code(response) == "ERR_SYNTHESIS_TEXT_TOO_LONG"
    assert api.engine.calls == []


def test_create_rejects_overlapping_overrides(api: ApiSetup) -> None:
    response = _create(
        api,
        text="東京日本橋",
        overrides=[
            _override("東京日", 0, 3, "とうきょうにち"),
            _override("日本橋", 2, 5, "にほんばし"),
        ],
    )
    assert response.status_code == 422
    assert _code(response) == "ERR_OVERRIDE_OVERLAP"
    assert api.engine.calls == []


def test_create_rejects_surface_mismatch(api: ApiSetup) -> None:
    response = _create(api, overrides=[_override(surface="東京")])
    assert response.status_code == 422
    assert _code(response) == "ERR_OVERRIDE_SURFACE_MISMATCH"
    assert api.engine.calls == []


def test_create_rejects_without_profile(api: ApiSetup) -> None:
    api.client.app.state.database.delete_voice_profile(VOICE_ID)
    response = _create(api)
    assert response.status_code == 404
    assert _code(response) == "ERR_PROFILE_NOT_FOUND"
    assert api.engine.calls == []


def test_create_rejects_without_ai_disclosure(api: ApiSetup) -> None:
    response = _create(api, acknowledged=False)
    assert response.status_code == 403
    assert _code(response) == "ERR_AI_DISCLOSURE_REQUIRED"
    assert api.engine.calls == []


def test_create_and_complete_job_returns_wav(api: ApiSetup) -> None:
    response = _create(api, overrides=[_override()])
    assert response.status_code == 201
    job_id = response.json()["id"]
    api.client.app.state.queue.wait_for(job_id)

    status = api.client.get(f"/api/syntheses/{job_id}")
    audio = api.client.get(f"/api/syntheses/{job_id}/audio")
    assert status.status_code == 200
    assert status.json()["status"] == "succeeded"
    assert status.json()["watermark_detected"] is True
    assert status.json()["audio_available"] is True
    assert audio.status_code == 200
    assert audio.headers["content-type"].startswith("audio/wav")
    assert re.fullmatch(
        r'attachment; filename="koeclone_\d{8}_\d{6}_[0-9a-f]{8}\.wav"',
        audio.headers["content-disposition"],
    )


def test_audio_is_forbidden_while_queued_or_running(api: ApiSetup) -> None:
    original = _hold_jobs(api)
    try:
        response = _create(api)
        assert response.status_code == 201
        audio = api.client.get(f"/api/syntheses/{response.json()['id']}/audio")
        assert audio.status_code == 409
        assert _code(audio) == "ERR_AUDIO_NOT_READY"
    finally:
        api.client.app.state.queue = original


def test_audio_is_forbidden_when_watermark_missing(api: ApiSetup) -> None:
    api.engine.detect_result = False
    response = _create(api)
    job_id = response.json()["id"]
    api.client.app.state.queue.wait_for(job_id)
    status = api.client.get(f"/api/syntheses/{job_id}")
    audio = api.client.get(f"/api/syntheses/{job_id}/audio")
    assert status.json()["status"] == "failed"
    assert status.json()["error_code"] == "ERR_WATERMARK_NOT_DETECTED"
    assert audio.status_code == 409
    assert not storage_path(
        api.client.app.state.paths.generated, job_id, ".wav"
    ).exists()


def test_unknown_job_returns_404(api: ApiSetup) -> None:
    response = api.client.get("/api/syntheses/22222222-2222-4222-8222-222222222222")
    assert response.status_code == 404
    assert _code(response) == "ERR_JOB_NOT_FOUND"


def test_status_exposes_text_preview_80_chars(api: ApiSetup) -> None:
    original = _hold_jobs(api)
    try:
        text = "声" * 100
        created = _create(api, text=text)
        status = api.client.get(f"/api/syntheses/{created.json()['id']}")
        assert status.status_code == 200
        assert status.json()["text_preview"] == text[:80]
    finally:
        api.client.app.state.queue = original


def test_invalid_uuid_in_synthesis_path_returns_400(api: ApiSetup) -> None:
    response = api.client.get("/api/syntheses/not-a-uuid")
    assert response.status_code == 400
    assert _code(response) == "ERR_BAD_REQUEST"
