from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from koeclone.domain.pronunciation import PronunciationOverride

REQUIRED_SIDECAR_KEYS = frozenset(
    {
        "ai_generated",
        "generated_at",
        "engine",
        "model_version",
        "voice_id",
        "text_sha256",
        "synthesis_text_sha256",
        "pronunciation_overrides",
    }
)


def write_sidecar(
    audio_path: Path,
    *,
    engine: str,
    model_version: str,
    voice_id: str,
    original_text: str,
    synthesis_text: str,
    pronunciation_overrides: Sequence[PronunciationOverride],
    generated_at: datetime | None = None,
) -> Path:
    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("generated_at must include a timezone")
    payload = {
        "ai_generated": True,
        "generated_at": timestamp.astimezone(UTC).isoformat(),
        "engine": engine,
        "model_version": model_version,
        "voice_id": voice_id,
        "text_sha256": _sha256(original_text),
        "synthesis_text_sha256": _sha256(synthesis_text),
        "pronunciation_overrides": [
            asdict(override) for override in pronunciation_overrides
        ],
    }
    path = audio_path.with_suffix(".json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
