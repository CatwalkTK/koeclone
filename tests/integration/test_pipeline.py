from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import astuple
from pathlib import Path

import pytest

from koeclone.config import AppConfig
from koeclone.domain.pronunciation import PronunciationOverride
from koeclone.domain.synthesis_text import (
    build_synthesis_text,
    plan_synthesis_chunks,
)
from koeclone.engines.fake import FakeEngine
from koeclone.errors import ErrorCode
from koeclone.media.ffmpeg import resolve_ffmpeg_paths, wav_duration_ms
from koeclone.storage.db import Database, SynthesisJob, VoiceProfile
from koeclone.storage.files import (
    collect_deletion_targets,
    create_data_directories,
    delete_targets,
    storage_path,
)
from koeclone.worker.pipeline import PipelineError, SynthesisPipeline, SynthesisRequest
from koeclone.worker.queue import JobQueue

VOICE_ID = "11111111-1111-4111-8111-111111111111"
OTHER_VOICE_ID = "33333333-3333-4333-8333-333333333333"
JOB_ID = "22222222-2222-4222-8222-222222222222"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _profile(reference_path: Path) -> VoiceProfile:
    return VoiceProfile(
        id=VOICE_ID,
        display_name="自分の声",
        source_mode="direct_recording",
        source_format="wav",
        source_sha256="source-hash",
        reference_path=str(reference_path),
        reference_sha256="reference-hash",
        consent_method="live_challenge",
        consent_text="私は自分の声を登録します。",
        consent_audio_path=None,
        consent_audio_sha256=None,
        created_at="2026-08-10T00:00:00+00:00",
        engine="fake",
        model_version="fake-1",
    )


def _job(text: str, *, voice_id: str = VOICE_ID, job_id: str = JOB_ID) -> SynthesisJob:
    return SynthesisJob(
        id=job_id,
        voice_id=voice_id,
        text=text,
        text_sha256=_sha256(text),
        synthesis_text=text,
        synthesis_text_sha256=_sha256(text),
        pronunciation_overrides="[]",
        language="ja",
        status="queued",
        audio_path=None,
        sidecar_path=None,
        duration_ms=None,
        watermark_detected=None,
        error_code=None,
        created_at="2026-08-10T00:01:00+00:00",
        completed_at=None,
    )


@pytest.fixture
def pipeline_setup(tmp_path: Path) -> tuple[SynthesisPipeline, Database, FakeEngine]:
    paths = create_data_directories(tmp_path / "data")
    reference = storage_path(paths.references, VOICE_ID, ".wav")
    reference.write_bytes(b"reference")
    database = Database(tmp_path / "db.sqlite3")
    database.create_voice_profile(_profile(reference))
    engine = FakeEngine()
    pipeline = SynthesisPipeline(
        engine=engine,
        database=database,
        paths=paths,
        config=AppConfig(data_dir=paths.root),
        ffmpeg_paths=resolve_ffmpeg_paths(),
    )
    return pipeline, database, engine


def _insert_without_foreign_key(database: Database, job: SynthesisJob) -> None:
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            "INSERT INTO synthesis_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            astuple(job),
        )


def test_pipeline_success_writes_audio_sidecar_and_database(
    pipeline_setup: tuple[SynthesisPipeline, Database, FakeEngine],
) -> None:
    pipeline, database, _ = pipeline_setup
    text = "音声を生成します。"
    database.create_synthesis_job(_job(text))

    pipeline.run(SynthesisRequest(JOB_ID, VOICE_ID, text))

    audio = storage_path(pipeline.paths.generated, JOB_ID, ".wav")
    sidecar = storage_path(pipeline.paths.generated, JOB_ID, ".json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    job = database.get_synthesis_job(JOB_ID)
    assert audio.is_file()
    assert payload["ai_generated"] is True
    assert payload["text_sha256"] == _sha256(text)
    assert payload["synthesis_text_sha256"] == _sha256(text)
    assert job is not None
    assert job.status == "succeeded"
    assert job.audio_path == str(audio)
    assert job.sidecar_path == str(sidecar)
    assert job.duration_ms == wav_duration_ms(audio)
    assert job.watermark_detected is True
    assert job.completed_at is not None
    assert list(pipeline.paths.temporary.rglob("*")) == []


def test_watermark_failure_removes_every_generated_artifact(
    pipeline_setup: tuple[SynthesisPipeline, Database, FakeEngine],
) -> None:
    pipeline, database, engine = pipeline_setup
    engine.detect_result = False
    database.create_synthesis_job(_job("検出失敗。"))

    with pytest.raises(PipelineError) as captured:
        pipeline.run(SynthesisRequest(JOB_ID, VOICE_ID, "検出失敗。"))

    job = database.get_synthesis_job(JOB_ID)
    assert captured.value.code is ErrorCode.ERR_WATERMARK_NOT_DETECTED
    assert job is not None
    assert job.status == "failed"
    assert job.error_code == ErrorCode.ERR_WATERMARK_NOT_DETECTED.value
    assert job.watermark_detected is False
    assert job.audio_path is None
    assert job.sidecar_path is None
    assert list(pipeline.paths.generated.iterdir()) == []
    assert list(pipeline.paths.temporary.rglob("*")) == []


def test_missing_consent_rejects_before_engine_call(
    pipeline_setup: tuple[SynthesisPipeline, Database, FakeEngine],
) -> None:
    pipeline, database, engine = pipeline_setup
    database.delete_voice_profile(VOICE_ID)
    _insert_without_foreign_key(database, _job("同意なし。"))

    with pytest.raises(PipelineError) as captured:
        pipeline.run(SynthesisRequest(JOB_ID, VOICE_ID, "同意なし。"))

    assert captured.value.code is ErrorCode.ERR_NO_CONSENT
    assert engine.calls == []
    assert engine.load_count == 0


def test_voice_id_mismatch_is_no_consent(
    pipeline_setup: tuple[SynthesisPipeline, Database, FakeEngine],
) -> None:
    pipeline, database, _ = pipeline_setup
    _insert_without_foreign_key(database, _job("別の声。", voice_id=OTHER_VOICE_ID))

    with pytest.raises(PipelineError) as captured:
        pipeline.run(SynthesisRequest(JOB_ID, OTHER_VOICE_ID, "別の声。"))

    assert captured.value.code is ErrorCode.ERR_NO_CONSENT


def test_pronunciation_override_changes_only_synthesis_metadata(
    pipeline_setup: tuple[SynthesisPipeline, Database, FakeEngine],
) -> None:
    pipeline, database, _ = pipeline_setup
    text = "明日は日本橋へ行きます"
    override = PronunciationOverride("日本橋", 3, 6, "にほんばし")
    database.create_synthesis_job(_job(text))

    pipeline.run(SynthesisRequest(JOB_ID, VOICE_ID, text, (override,)))

    sidecar = storage_path(pipeline.paths.generated, JOB_ID, ".json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    job = database.get_synthesis_job(JOB_ID)
    assert payload["synthesis_text_sha256"] == _sha256("明日はにほんばしへ行きます")
    assert job is not None
    assert job.text == text


def test_multiple_chunks_are_synthesized_and_joined_in_order(
    pipeline_setup: tuple[SynthesisPipeline, Database, FakeEngine],
) -> None:
    pipeline, database, engine = pipeline_setup
    text = "これは長い文章です。" * 30
    database.create_synthesis_job(_job(text))
    synthesis_text, error = build_synthesis_text(text, [], config=pipeline.config)
    assert error is None and synthesis_text is not None
    expected_chunks = plan_synthesis_chunks(synthesis_text)

    pipeline.run(SynthesisRequest(JOB_ID, VOICE_ID, text))

    assert [call[0] for call in engine.calls] == expected_chunks
    expected_ms = sum(
        round(max(0.2, min(5.0, len(chunk) * 0.1)) * engine.sample_rate)
        / engine.sample_rate
        * 1_000
        for chunk in expected_chunks
    )
    output = storage_path(pipeline.paths.generated, JOB_ID, ".wav")
    assert wav_duration_ms(output) == pytest.approx(expected_ms, abs=50)


def test_invalid_override_fails_without_loading_engine(
    pipeline_setup: tuple[SynthesisPipeline, Database, FakeEngine],
) -> None:
    pipeline, database, engine = pipeline_setup
    text = "明日は日本橋へ行きます"
    invalid = PronunciationOverride("東京", 3, 6, "とうきょう")
    database.create_synthesis_job(_job(text))

    with pytest.raises(PipelineError) as captured:
        pipeline.run(SynthesisRequest(JOB_ID, VOICE_ID, text, (invalid,)))

    assert captured.value.code is ErrorCode.ERR_OVERRIDE_SURFACE_MISMATCH
    assert engine.calls == []
    assert engine.load_count == 0
    assert database.get_synthesis_job(JOB_ID).status == "failed"  # type: ignore[union-attr]


def test_unexpected_engine_error_is_sanitized(
    pipeline_setup: tuple[SynthesisPipeline, Database, FakeEngine],
) -> None:
    pipeline, database, _ = pipeline_setup
    secret = "full secret input"

    class BrokenEngine(FakeEngine):
        def synthesize(self, *args: object, **kwargs: object) -> Path:
            raise RuntimeError(secret)

    pipeline = SynthesisPipeline(
        BrokenEngine(),
        database,
        pipeline.paths,
        pipeline.config,
        pipeline.ffmpeg_paths,
    )
    database.create_synthesis_job(_job("内部失敗。"))

    with pytest.raises(PipelineError) as captured:
        pipeline.run(SynthesisRequest(JOB_ID, VOICE_ID, "内部失敗。"))

    assert captured.value.code is ErrorCode.ERR_INTERNAL
    assert secret not in str(captured.value)
    assert list(pipeline.paths.temporary.rglob("*")) == []


def test_pipeline_maps_through_job_queue(
    pipeline_setup: tuple[SynthesisPipeline, Database, FakeEngine],
) -> None:
    pipeline, database, _ = pipeline_setup
    text = "キュー統合。"
    database.create_synthesis_job(_job(text))
    request = SynthesisRequest(JOB_ID, VOICE_ID, text)
    queue = JobQueue(lambda _: pipeline.run(request))
    queue.submit(JOB_ID)
    queue.start()

    state = queue.wait_for(JOB_ID)
    queue.shutdown()

    assert state.status == "succeeded"
    assert database.get_synthesis_job(JOB_ID).status == "succeeded"  # type: ignore[union-attr]


def test_pipeline_failure_maps_through_job_queue(
    pipeline_setup: tuple[SynthesisPipeline, Database, FakeEngine],
) -> None:
    pipeline, database, engine = pipeline_setup
    engine.detect_result = False
    text = "検出できません。"
    database.create_synthesis_job(_job(text))
    request = SynthesisRequest(JOB_ID, VOICE_ID, text)
    queue = JobQueue(lambda _: pipeline.run(request))
    queue.submit(JOB_ID)
    queue.start()

    state = queue.wait_for(JOB_ID)
    queue.shutdown()

    assert state.status == "failed"
    assert state.error_code is ErrorCode.ERR_WATERMARK_NOT_DETECTED


def test_collect_delete_then_database_delete_removes_everything(tmp_path: Path) -> None:
    consent_id = "44444444-4444-4444-8444-444444444444"
    paths = create_data_directories(tmp_path / "data")
    reference = storage_path(paths.references, VOICE_ID, ".wav")
    consent = storage_path(paths.consent, consent_id, ".wav")
    cache = storage_path(paths.cache, VOICE_ID, ".cache")
    audio = storage_path(paths.generated, JOB_ID, ".wav")
    sidecar = storage_path(paths.generated, JOB_ID, ".json")
    temporary = paths.temporary / "partial.tmp"
    for path in (reference, consent, cache, audio, sidecar, temporary):
        path.write_bytes(b"fixture")
    database = Database(tmp_path / "db.sqlite3")
    profile = _profile(reference)
    database.create_voice_profile(
        VoiceProfile(
            **{
                **profile.__dict__,
                "consent_audio_path": str(consent),
                "consent_audio_sha256": "consent-hash",
            }
        )
    )
    database.create_synthesis_job(_job("削除対象。"))

    targets = collect_deletion_targets(
        paths,
        reference_id=VOICE_ID,
        consent_id=consent_id,
        job_ids=[job.id for job in database.list_synthesis_jobs()],
    )
    delete_targets(paths.root, targets)
    database.delete_voice_profile(VOICE_ID)

    assert all(not path.exists() for path in targets.all_paths())
    assert database.get_current_voice_profile() is None
    assert database.list_synthesis_jobs() == []

    missing_job_ids = [job.id for job in database.list_synthesis_jobs()]
    incomplete = collect_deletion_targets(
        paths,
        reference_id=VOICE_ID,
        consent_id=consent_id,
        job_ids=missing_job_ids,
    )
    assert incomplete.generated_audio == ()
    assert incomplete.sidecars == ()
