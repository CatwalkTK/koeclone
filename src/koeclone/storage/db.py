from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import astuple, dataclass
from pathlib import Path

from koeclone.errors import ErrorCode

VOICE_PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_profiles (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    source_mode TEXT NOT NULL CHECK (source_mode IN ('direct_recording', 'file_upload')),
    source_format TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    reference_path TEXT NOT NULL,
    reference_sha256 TEXT NOT NULL,
    consent_method TEXT NOT NULL CHECK (consent_method IN ('live_challenge', 'upload_declaration')),
    consent_text TEXT NOT NULL,
    consent_audio_path TEXT,
    consent_audio_sha256 TEXT,
    created_at TEXT NOT NULL,
    engine TEXT NOT NULL,
    model_version TEXT NOT NULL
)
"""

SYNTHESIS_JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS synthesis_jobs (
    id TEXT PRIMARY KEY,
    voice_id TEXT NOT NULL REFERENCES voice_profiles(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    synthesis_text TEXT NOT NULL,
    synthesis_text_sha256 TEXT NOT NULL,
    pronunciation_overrides TEXT NOT NULL,
    language TEXT NOT NULL CHECK (language = 'ja'),
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    audio_path TEXT,
    sidecar_path TEXT,
    duration_ms INTEGER,
    watermark_detected INTEGER CHECK (watermark_detected IN (0, 1) OR watermark_detected IS NULL),
    error_code TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
)
"""


@dataclass(frozen=True)
class VoiceProfile:
    id: str
    display_name: str
    source_mode: str
    source_format: str
    source_sha256: str
    reference_path: str
    reference_sha256: str
    consent_method: str
    consent_text: str
    consent_audio_path: str | None
    consent_audio_sha256: str | None
    created_at: str
    engine: str
    model_version: str


@dataclass(frozen=True)
class SynthesisJob:
    id: str
    voice_id: str
    text: str
    text_sha256: str
    synthesis_text: str
    synthesis_text_sha256: str
    pronunciation_overrides: str
    language: str
    status: str
    audio_path: str | None
    sidecar_path: str | None
    duration_ms: int | None
    watermark_detected: bool | None
    error_code: str | None
    created_at: str
    completed_at: str | None


class StorageError(Exception):
    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._initialize()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(VOICE_PROFILE_SCHEMA)
            connection.execute(SYNTHESIS_JOB_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_voice_profile(self, profile: VoiceProfile) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM voice_profiles LIMIT 1").fetchone():
                raise StorageError(ErrorCode.ERR_PROFILE_ALREADY_EXISTS)
            connection.execute(
                """
                INSERT INTO voice_profiles VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                astuple(profile),
            )

    def get_current_voice_profile(self) -> VoiceProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM voice_profiles LIMIT 1"
            ).fetchone()
        return VoiceProfile(**dict(row)) if row else None

    def delete_voice_profile(self, profile_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM voice_profiles WHERE id = ?", (profile_id,))

    def create_synthesis_job(self, job: SynthesisJob) -> None:
        values = list(astuple(job))
        if job.watermark_detected is not None:
            values[12] = int(job.watermark_detected)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO synthesis_jobs VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                values,
            )

    def get_synthesis_job(self, job_id: str) -> SynthesisJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM synthesis_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return _job_from_row(row) if row else None

    def update_synthesis_job(
        self,
        job_id: str,
        *,
        status: str,
        audio_path: str | None = None,
        sidecar_path: str | None = None,
        duration_ms: int | None = None,
        watermark_detected: bool | None = None,
        error_code: str | None = None,
        completed_at: str | None = None,
    ) -> None:
        watermark_value = (
            None if watermark_detected is None else int(watermark_detected)
        )
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE synthesis_jobs
                SET status = ?, audio_path = ?, sidecar_path = ?, duration_ms = ?,
                    watermark_detected = ?, error_code = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    audio_path,
                    sidecar_path,
                    duration_ms,
                    watermark_value,
                    error_code,
                    completed_at,
                    job_id,
                ),
            )

    def list_synthesis_jobs(self) -> list[SynthesisJob]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM synthesis_jobs ORDER BY created_at DESC"
            ).fetchall()
        return [_job_from_row(row) for row in rows]

    def delete_synthesis_job(self, job_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM synthesis_jobs WHERE id = ?", (job_id,))

    def delete_all_synthesis_jobs(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM synthesis_jobs")


def _job_from_row(row: sqlite3.Row) -> SynthesisJob:
    values = dict(row)
    if values["watermark_detected"] is not None:
        values["watermark_detected"] = bool(values["watermark_detected"])
    return SynthesisJob(**values)
