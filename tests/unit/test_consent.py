import re
from dataclasses import fields
from datetime import UTC, datetime

import pytest

from koeclone.domain.consent import (
    UPLOAD_RIGHTS_DECLARATION,
    ConsentMethod,
    build_consent_record,
    generate_consent_challenge,
    validate_generation_consent,
)
from koeclone.errors import ErrorCode

CONSENTED_AT = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def test_each_live_challenge_is_different() -> None:
    first = generate_consent_challenge()
    second = generate_consent_challenge()

    assert first != second
    assert "自分自身の声" in first
    assert "音声クローン" in first
    assert re.search(r"確認番号は\d{8}です", first)


def test_upload_declaration_states_ownership_and_rights() -> None:
    assert "自分自身の声" in UPLOAD_RIGHTS_DECLARATION
    assert "権利" in UPLOAD_RIGHTS_DECLARATION
    assert "クローン" in UPLOAD_RIGHTS_DECLARATION


def test_builds_live_challenge_consent_record() -> None:
    record = build_consent_record(
        method=ConsentMethod.LIVE_CHALLENGE,
        consent_text="チャレンジ文",
        source_audio_sha256="source-hash",
        app_version="0.1.0",
        consent_audio_sha256="consent-hash",
        consented_at=CONSENTED_AT,
    )

    assert {field.name for field in fields(record)} == {
        "consented_at",
        "method",
        "consent_text",
        "source_audio_sha256",
        "app_version",
        "consent_audio_sha256",
    }
    assert record.consented_at == "2026-08-10T12:00:00+00:00"
    assert record.method is ConsentMethod.LIVE_CHALLENGE
    assert record.consent_audio_sha256 == "consent-hash"


def test_live_challenge_requires_consent_audio_hash() -> None:
    with pytest.raises(ValueError):
        build_consent_record(
            method=ConsentMethod.LIVE_CHALLENGE,
            consent_text="チャレンジ文",
            source_audio_sha256="source-hash",
            app_version="0.1.0",
            consent_audio_sha256=None,
            consented_at=CONSENTED_AT,
        )


def test_upload_consent_allows_no_consent_audio() -> None:
    record = build_consent_record(
        method=ConsentMethod.UPLOAD_DECLARATION,
        consent_text=UPLOAD_RIGHTS_DECLARATION,
        source_audio_sha256="source-hash",
        app_version="0.1.0",
        consent_audio_sha256=None,
        consented_at=CONSENTED_AT,
    )

    assert record.consent_audio_sha256 is None


def test_rejects_generation_without_consent_record() -> None:
    assert validate_generation_consent(None) is ErrorCode.ERR_NO_CONSENT


def test_allows_generation_with_consent_record() -> None:
    record = build_consent_record(
        method=ConsentMethod.UPLOAD_DECLARATION,
        consent_text=UPLOAD_RIGHTS_DECLARATION,
        source_audio_sha256="source-hash",
        app_version="0.1.0",
        consent_audio_sha256=None,
        consented_at=CONSENTED_AT,
    )

    assert validate_generation_consent(record) is None
