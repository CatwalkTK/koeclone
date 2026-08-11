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


def _wav(duration: float, *, amplitude: int = 3_000) -> bytes:
    sample_rate = 24_000
    frames = [
        round(amplitude * math.sin(2 * math.pi * 440 * index / sample_rate))
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


def _validate_upload(
    client: TestClient,
    audio: bytes | None = None,
    **data: str,
):
    form = {
        "stage": "validate",
        "source_mode": "file_upload",
        "consent_accepted": "true",
        "consent_text": "自分の声の登録に同意します。",
        **data,
    }
    files = {"audio": ("voice.wav", audio or _wav(12), "audio/wav")}
    return client.post("/api/voices", data=form, files=files)


def _validate_recording(
    client: TestClient,
    audio: bytes,
    *,
    consent_audio: bytes | None = None,
):
    files = {"audio": ("recording", audio, "audio/wav")}
    if consent_audio is not None:
        files["consent_audio"] = ("consent", consent_audio, "audio/wav")
    return client.post(
        "/api/voices",
        data={
            "stage": "validate",
            "source_mode": "direct_recording",
            "consent_accepted": "true",
            "consent_text": "読み上げた同意文です。",
        },
        files=files,
    )


def _confirm(client: TestClient, draft_id: str, display_name: str = "マイボイス"):
    return client.post(
        "/api/voices",
        data={
            "stage": "confirm",
            "draft_id": draft_id,
            "consent_accepted": "true",
            "display_name": display_name,
        },
    )


def _code(response) -> str:
    return response.json()["error"]["code"]


def test_validate_rejects_missing_consent(client: TestClient) -> None:
    response = _validate_upload(client, consent_accepted="false")
    assert response.status_code == 403
    assert _code(response) == "ERR_NO_CONSENT"


def test_validate_rejects_recording_shorter_than_10s(client: TestClient) -> None:
    response = _validate_recording(client, _wav(5), consent_audio=_wav(1))
    assert response.status_code == 422
    assert _code(response) == "ERR_AUDIO_TOO_SHORT"


def test_validate_rejects_recording_longer_than_60s(client: TestClient) -> None:
    response = _validate_recording(client, _wav(70), consent_audio=_wav(1))
    assert response.status_code == 422
    assert _code(response) == "ERR_AUDIO_TOO_LONG"


def test_validate_rejects_upload_longer_than_180s(client: TestClient) -> None:
    response = _validate_upload(client, _wav(200))
    assert response.status_code == 422
    assert _code(response) == "ERR_AUDIO_TOO_LONG"


def test_validate_rejects_extension_spoofing(client: TestClient) -> None:
    response = _validate_upload(client, b"not a wav")
    assert response.status_code == 422
    assert _code(response) in {"ERR_FILE_FORMAT_MISMATCH", "ERR_FILE_CORRUPTED"}


def test_validate_rejects_unsupported_upload_format(client: TestClient) -> None:
    response = client.post(
        "/api/voices",
        data={
            "stage": "validate",
            "source_mode": "file_upload",
            "consent_accepted": "true",
            "consent_text": "同意します。",
        },
        files={"audio": ("voice.webm", b"webm", "audio/webm")},
    )
    assert response.status_code == 422
    assert _code(response) == "ERR_FILE_UNSUPPORTED_FORMAT"


def test_validate_rejects_silent_audio(client: TestClient) -> None:
    response = _validate_upload(client, _wav(12, amplitude=0))
    assert response.status_code == 422
    assert _code(response) == "ERR_AUDIO_MOSTLY_SILENT"


def test_validate_rejects_clipping_audio(client: TestClient) -> None:
    response = _validate_upload(client, _wav(12, amplitude=32_767))
    assert response.status_code == 422
    assert _code(response) == "ERR_AUDIO_CLIPPING"


def test_validate_returns_playable_draft(client: TestClient) -> None:
    response = _validate_upload(client)
    assert response.status_code == 200
    payload = response.json()
    preview = client.get(payload["preview_url"])
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("audio/wav")
    with wave.open(io.BytesIO(preview.content), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 24_000


def test_confirm_creates_single_profile_and_test_job(client: TestClient) -> None:
    draft_id = _validate_upload(client).json()["draft_id"]
    response = _confirm(client, draft_id)
    assert response.status_code == 201
    payload = response.json()
    assert client.app.state.database.get_current_voice_profile() is not None
    assert client.app.state.database.get_synthesis_job(payload["test_synthesis_id"])


def test_confirm_removes_temporary_files(client: TestClient) -> None:
    draft_id = _validate_upload(client).json()["draft_id"]
    payload = _confirm(client, draft_id).json()
    client.app.state.queue.wait_for(payload["test_synthesis_id"])
    assert list(client.app.state.paths.temporary.rglob("*")) == []


def test_second_profile_is_rejected(client: TestClient) -> None:
    first = _validate_upload(client).json()["draft_id"]
    second = _validate_upload(client).json()["draft_id"]
    assert _confirm(client, first).status_code == 201
    response = _confirm(client, second)
    assert response.status_code == 409
    assert _code(response) == "ERR_PROFILE_ALREADY_EXISTS"


def test_confirm_with_unknown_draft_returns_404(client: TestClient) -> None:
    response = _confirm(client, "00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404
    assert _code(response) == "ERR_DRAFT_NOT_FOUND"


def test_response_does_not_leak_paths_or_hashes(client: TestClient) -> None:
    draft_id = _validate_upload(client).json()["draft_id"]
    response = _confirm(client, draft_id)
    body = response.text
    assert "reference_path" not in body
    assert "sha256" not in body
    assert str(client.app.state.config.data_dir) not in body


def test_display_name_is_not_used_in_file_path(client: TestClient) -> None:
    draft_id = _validate_upload(client).json()["draft_id"]
    response = _confirm(client, draft_id, "../../etc/passwd")
    assert response.status_code == 201
    profile = client.app.state.database.get_current_voice_profile()
    assert profile is not None
    assert Path(profile.reference_path).is_relative_to(client.app.state.paths.root)
    assert "passwd" not in Path(profile.reference_path).name


def test_direct_recording_requires_consent_audio(client: TestClient) -> None:
    response = _validate_recording(client, _wav(12))
    assert response.status_code == 403
    assert _code(response) == "ERR_NO_CONSENT"


def test_unknown_stage_is_bad_request(client: TestClient) -> None:
    response = client.post("/api/voices", data={"stage": "publish"})
    assert response.status_code == 400
    assert _code(response) == "ERR_BAD_REQUEST"


def test_display_name_over_50_chars_is_rejected(client: TestClient) -> None:
    draft_id = _validate_upload(client).json()["draft_id"]
    response = _confirm(client, draft_id, "声" * 51)
    assert response.status_code == 400
    assert _code(response) == "ERR_BAD_REQUEST"


def test_upload_mode_rejects_consent_audio(client: TestClient) -> None:
    response = client.post(
        "/api/voices",
        data={
            "stage": "validate",
            "source_mode": "file_upload",
            "consent_accepted": "true",
            "consent_text": "同意します。",
        },
        files={
            "audio": ("voice.wav", _wav(12), "audio/wav"),
            "consent_audio": ("consent.wav", _wav(1), "audio/wav"),
        },
    )
    assert response.status_code == 400
    assert _code(response) == "ERR_BAD_REQUEST"
