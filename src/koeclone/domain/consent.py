from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from itertools import count

from koeclone.errors import ErrorCode

UPLOAD_RIGHTS_DECLARATION = (
    "この音声は自分自身の声であり、音声クローンを作成して利用する権利を持つことを確認します。"
)
_CHALLENGE_WORDS = ("あおぞら", "こもれび", "さくら", "しおかぜ", "ひまわり")
_CHALLENGE_SEQUENCE = count(1)


class ConsentMethod(StrEnum):
    LIVE_CHALLENGE = "live_challenge"
    UPLOAD_DECLARATION = "upload_declaration"


@dataclass(frozen=True)
class ConsentRecord:
    consented_at: str
    method: ConsentMethod
    consent_text: str
    source_audio_sha256: str
    app_version: str
    consent_audio_sha256: str | None


def generate_consent_challenge() -> str:
    word = secrets.choice(_CHALLENGE_WORDS)
    random_number = secrets.randbelow(1_000_000)
    sequence = next(_CHALLENGE_SEQUENCE)
    return (
        "私は自分自身の声をこの端末の音声クローンとして登録することに同意します。"
        f"確認語は「{word}」、確認番号は{random_number:06d}-{sequence}です。"
    )


def build_consent_record(
    *,
    method: ConsentMethod,
    consent_text: str,
    source_audio_sha256: str,
    app_version: str,
    consent_audio_sha256: str | None,
    consented_at: datetime | None = None,
) -> ConsentRecord:
    timestamp = consented_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("consented_at must include a timezone")
    if method is ConsentMethod.LIVE_CHALLENGE and not consent_audio_sha256:
        raise ValueError("Live challenge consent requires a consent audio hash")
    if method is ConsentMethod.UPLOAD_DECLARATION and consent_audio_sha256 is not None:
        raise ValueError("Upload declaration must not include a consent audio hash")
    return ConsentRecord(
        consented_at=timestamp.astimezone(UTC).isoformat(),
        method=method,
        consent_text=consent_text,
        source_audio_sha256=source_audio_sha256,
        app_version=app_version,
        consent_audio_sha256=consent_audio_sha256,
    )


def validate_generation_consent(
    consent_record: ConsentRecord | None,
) -> ErrorCode | None:
    if consent_record is None:
        return ErrorCode.ERR_NO_CONSENT
    return None
