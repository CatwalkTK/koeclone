import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from koeclone.domain.pronunciation import PronunciationOverride
from koeclone.domain.sidecar import REQUIRED_SIDECAR_KEYS, write_sidecar

GENERATED_AT = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_writes_required_ai_metadata_and_hashes(tmp_path: Path) -> None:
    audio_path = tmp_path / "voice.wav"
    original = "明日は日本橋へ行きます"
    synthesis_text = "明日はにほんばしへ行きます"
    override = PronunciationOverride("日本橋", 3, 6, "にほんばし")

    path = write_sidecar(
        audio_path,
        engine="chatterbox-multilingual-v3",
        model_version="5bb1f6ee",
        voice_id="voice-1",
        original_text=original,
        synthesis_text=synthesis_text,
        pronunciation_overrides=[override],
        generated_at=GENERATED_AT,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert set(payload) == REQUIRED_SIDECAR_KEYS
    assert payload["ai_generated"] is True
    assert payload["generated_at"] == "2026-08-10T12:00:00+00:00"
    assert payload["engine"] == "chatterbox-multilingual-v3"
    assert payload["model_version"] == "5bb1f6ee"
    assert payload["voice_id"] == "voice-1"
    assert payload["text_sha256"] == sha256(original)
    assert payload["synthesis_text_sha256"] == sha256(synthesis_text)
    assert payload["pronunciation_overrides"] == [
        {"surface": "日本橋", "start": 3, "end": 6, "reading": "にほんばし"}
    ]


def test_uses_audio_stem_for_sidecar_path(tmp_path: Path) -> None:
    audio_path = tmp_path / "foo.wav"

    path = write_sidecar(
        audio_path,
        engine="engine",
        model_version="version",
        voice_id="voice",
        original_text="本文",
        synthesis_text="本文",
        pronunciation_overrides=[],
        generated_at=GENERATED_AT,
    )

    assert path == tmp_path / "foo.json"


def test_writes_empty_override_list_without_ascii_escaping(tmp_path: Path) -> None:
    path = write_sidecar(
        tmp_path / "foo.wav",
        engine="エンジン",
        model_version="版",
        voice_id="自分",
        original_text="本文",
        synthesis_text="本文",
        pronunciation_overrides=[],
        generated_at=GENERATED_AT,
    )
    content = path.read_text(encoding="utf-8")

    assert json.loads(content)["pronunciation_overrides"] == []
    assert "エンジン" in content
    assert "\\u30a8" not in content
