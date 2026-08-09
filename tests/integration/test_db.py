import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from koeclone.errors import ErrorCode
from koeclone.storage.db import Database, StorageError, SynthesisJob, VoiceProfile

VOICE_COLUMNS = [
    "id",
    "display_name",
    "source_mode",
    "source_format",
    "source_sha256",
    "reference_path",
    "reference_sha256",
    "consent_method",
    "consent_text",
    "consent_audio_path",
    "consent_audio_sha256",
    "created_at",
    "engine",
    "model_version",
]
JOB_COLUMNS = [
    "id",
    "voice_id",
    "text",
    "text_sha256",
    "synthesis_text",
    "synthesis_text_sha256",
    "pronunciation_overrides",
    "language",
    "status",
    "audio_path",
    "sidecar_path",
    "duration_ms",
    "watermark_detected",
    "error_code",
    "created_at",
    "completed_at",
]


def voice_profile(identifier: str = "voice-1") -> VoiceProfile:
    return VoiceProfile(
        id=identifier,
        display_name="自分の声",
        source_mode="direct_recording",
        source_format="wav",
        source_sha256="source-hash",
        reference_path="references/voice-1.wav",
        reference_sha256="reference-hash",
        consent_method="live_challenge",
        consent_text="私は自分の声を登録します。",
        consent_audio_path="consent/voice-1.wav",
        consent_audio_sha256="consent-hash",
        created_at="2026-08-10T01:00:00+00:00",
        engine="chatterbox-multilingual-v3",
        model_version="5bb1f6ee",
    )


def synthesis_job(
    identifier: str = "job-1",
    created_at: str = "2026-08-10T01:01:00+00:00",
) -> SynthesisJob:
    return SynthesisJob(
        id=identifier,
        voice_id="voice-1",
        text="明日は日本橋へ行きます",
        text_sha256="text-hash",
        synthesis_text="明日はにほんばしへ行きます",
        synthesis_text_sha256="synthesis-hash",
        pronunciation_overrides="[]",
        language="ja",
        status="queued",
        audio_path=None,
        sidecar_path=None,
        duration_ms=None,
        watermark_detected=None,
        error_code=None,
        created_at=created_at,
        completed_at=None,
    )


def test_schema_has_exact_contract_columns(tmp_path: Path) -> None:
    path = tmp_path / "koeclone.sqlite3"
    Database(path)

    with sqlite3.connect(path) as connection:
        voice_columns = [
            row[1] for row in connection.execute("PRAGMA table_info(voice_profiles)")
        ]
        job_columns = [
            row[1] for row in connection.execute("PRAGMA table_info(synthesis_jobs)")
        ]

    assert voice_columns == VOICE_COLUMNS
    assert job_columns == JOB_COLUMNS


def test_creates_and_gets_current_profile(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    profile = voice_profile()

    database.create_voice_profile(profile)

    assert database.get_current_voice_profile() == profile


def test_rejects_second_profile(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    database.create_voice_profile(voice_profile())

    with pytest.raises(StorageError) as error:
        database.create_voice_profile(voice_profile("voice-2"))

    assert error.value.code is ErrorCode.ERR_PROFILE_ALREADY_EXISTS


def test_creates_gets_and_updates_job(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    database.create_voice_profile(voice_profile())
    job = synthesis_job()
    database.create_synthesis_job(job)

    assert database.get_synthesis_job(job.id) == job

    database.update_synthesis_job(
        job.id,
        status="succeeded",
        audio_path="generated/job-1.wav",
        sidecar_path="generated/job-1.json",
        duration_ms=2_500,
        watermark_detected=True,
        completed_at="2026-08-10T01:02:00+00:00",
    )

    assert database.get_synthesis_job(job.id) == replace(
        job,
        status="succeeded",
        audio_path="generated/job-1.wav",
        sidecar_path="generated/job-1.json",
        duration_ms=2_500,
        watermark_detected=True,
        completed_at="2026-08-10T01:02:00+00:00",
    )


def test_lists_jobs_newest_first(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    database.create_voice_profile(voice_profile())
    older = synthesis_job("older", "2026-08-10T01:01:00+00:00")
    newer = synthesis_job("newer", "2026-08-10T01:03:00+00:00")
    database.create_synthesis_job(older)
    database.create_synthesis_job(newer)

    assert database.list_synthesis_jobs() == [newer, older]


def test_deletes_one_and_all_jobs(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    database.create_voice_profile(voice_profile())
    first = synthesis_job("first")
    second = synthesis_job("second", "2026-08-10T01:02:00+00:00")
    database.create_synthesis_job(first)
    database.create_synthesis_job(second)

    database.delete_synthesis_job(first.id)
    assert database.get_synthesis_job(first.id) is None
    assert database.list_synthesis_jobs() == [second]

    database.delete_all_synthesis_jobs()
    assert database.list_synthesis_jobs() == []


def test_deletes_profile_and_cascades_jobs(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")
    database.create_voice_profile(voice_profile())
    database.create_synthesis_job(synthesis_job())

    database.delete_voice_profile("voice-1")

    assert database.get_current_voice_profile() is None
    assert database.list_synthesis_jobs() == []


def test_foreign_keys_are_enabled(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3")

    with pytest.raises(sqlite3.IntegrityError):
        database.create_synthesis_job(synthesis_job())
