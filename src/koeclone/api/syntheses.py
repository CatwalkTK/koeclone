from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from koeclone.domain.pronunciation import (
    PronunciationOverride,
    validate_pronunciation_overrides,
)
from koeclone.domain.synthesis_text import build_synthesis_text
from koeclone.domain.text_validation import validate_text
from koeclone.errors import ErrorCode, KoecloneError
from koeclone.storage.db import SynthesisJob
from koeclone.storage.files import download_filename

router = APIRouter()


class OverrideBody(BaseModel):
    surface: str
    start: int
    end: int
    reading: str


class PreviewBody(BaseModel):
    text: str
    overrides: list[OverrideBody] = Field(default_factory=list)


class CreateBody(PreviewBody):
    ai_disclosure_acknowledged: bool | None = None


@router.post("/syntheses/preview")
def preview_synthesis(request: Request, body: PreviewBody) -> dict[str, object]:
    overrides = _overrides(body.overrides)
    synthesis_text = _validate_synthesis(request, body.text, overrides)
    return {
        "synthesis_text": synthesis_text,
        "original_segments": _segments(body.text, overrides, use_reading=False),
        "synthesis_segments": _segments(body.text, overrides, use_reading=True),
        "override_count": len(overrides),
        "text_length": len(body.text),
        "synthesis_text_length": len(synthesis_text),
    }


@router.post("/syntheses")
def create_synthesis(request: Request, body: CreateBody) -> JSONResponse:
    database = request.app.state.database
    profile = database.get_current_voice_profile()
    if profile is None:
        raise KoecloneError(ErrorCode.ERR_PROFILE_NOT_FOUND)
    if not profile.consent_text.strip():
        raise KoecloneError(ErrorCode.ERR_NO_CONSENT)
    if body.ai_disclosure_acknowledged is not True:
        raise KoecloneError(ErrorCode.ERR_AI_DISCLOSURE_REQUIRED)

    overrides = _overrides(body.overrides)
    synthesis_text = _validate_synthesis(request, body.text, overrides)
    job_id = str(uuid4())
    created_at = datetime.now(UTC).isoformat()
    job = SynthesisJob(
        id=job_id,
        voice_id=profile.id,
        text=body.text,
        text_sha256=_sha256(body.text),
        synthesis_text=synthesis_text,
        synthesis_text_sha256=_sha256(synthesis_text),
        pronunciation_overrides=json.dumps(
            [asdict(override) for override in overrides],
            ensure_ascii=False,
            separators=(",", ":"),
        ),
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
    database.create_synthesis_job(job)
    try:
        request.app.state.queue.submit(job_id)
    except Exception:
        database.delete_synthesis_job(job_id)
        raise
    return JSONResponse(
        status_code=201,
        content={"id": job_id, "status": "queued", "created_at": created_at},
    )


@router.get("/syntheses/{job_id}")
def get_synthesis(request: Request, job_id: UUID) -> dict[str, object]:
    job = _get_job(request, job_id)
    return _job_response(job)


@router.get("/syntheses/{job_id}/audio")
def get_synthesis_audio(request: Request, job_id: UUID) -> FileResponse:
    job = _get_job(request, job_id)
    if (
        job.status != "succeeded"
        or job.watermark_detected is not True
        or job.audio_path is None
    ):
        raise KoecloneError(ErrorCode.ERR_AUDIO_NOT_READY)
    return FileResponse(
        job.audio_path,
        media_type="audio/wav",
        filename=download_filename(job.id, datetime.fromisoformat(job.created_at)),
    )


def _validate_synthesis(
    request: Request,
    text: str,
    overrides: list[PronunciationOverride],
) -> str:
    text_error = validate_text(text, config=request.app.state.config)
    if text_error is not None:
        raise KoecloneError(text_error)
    override_error = validate_pronunciation_overrides(text, overrides)
    if override_error is not None:
        raise KoecloneError(override_error)
    synthesis_text, synthesis_error = build_synthesis_text(
        text,
        overrides,
        config=request.app.state.config,
    )
    if synthesis_error is not None:
        raise KoecloneError(synthesis_error)
    if synthesis_text is None:
        raise KoecloneError(ErrorCode.ERR_INTERNAL)
    return synthesis_text


def _overrides(items: list[OverrideBody]) -> list[PronunciationOverride]:
    return [
        PronunciationOverride(item.surface, item.start, item.end, item.reading)
        for item in items
    ]


def _segments(
    text: str,
    overrides: list[PronunciationOverride],
    *,
    use_reading: bool,
) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    cursor = 0
    for index, override in sorted(
        enumerate(overrides),
        key=lambda indexed: indexed[1].start,
    ):
        if cursor < override.start:
            segments.append(
                {"text": text[cursor : override.start], "override_index": None}
            )
        segments.append(
            {
                "text": override.reading if use_reading else override.surface,
                "override_index": index,
            }
        )
        cursor = override.end
    if cursor < len(text):
        segments.append({"text": text[cursor:], "override_index": None})
    return segments


def _get_job(request: Request, job_id: UUID) -> SynthesisJob:
    job = request.app.state.database.get_synthesis_job(str(job_id))
    if job is None:
        raise KoecloneError(ErrorCode.ERR_JOB_NOT_FOUND)
    return job


def _job_response(job: SynthesisJob) -> dict[str, object]:
    return {
        "id": job.id,
        "status": job.status,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "duration_ms": job.duration_ms,
        "watermark_detected": job.watermark_detected,
        "error_code": job.error_code,
        "text_preview": job.text[:80],
        "override_count": len(json.loads(job.pronunciation_overrides)),
        "audio_available": (
            job.status == "succeeded" and job.watermark_detected is True
        ),
    }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
