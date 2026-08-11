from __future__ import annotations

import hashlib
import shutil
import sys
import wave
from array import array
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from koeclone.domain.audio_quality import AudioSourceMode, validate_audio_quality
from koeclone.domain.consent import ConsentMethod, build_consent_record
from koeclone.domain.file_probe import validate_audio_file
from koeclone.domain.synthesis_text import build_synthesis_text
from koeclone.errors import ErrorCode, KoecloneError
from koeclone.media.ffmpeg import (
    detect_silence_ranges,
    extract_reference_segment,
    make_probe,
    normalize_to_reference_wav,
    probe_audio,
    select_reference_window,
    wav_duration_ms,
)
from koeclone.storage.db import StorageError, SynthesisJob, VoiceProfile
from koeclone.storage.files import storage_path

router = APIRouter()

TEST_SENTENCE = "これはテスト用の音声です。声の確認にお使いください。"
_DIRECT_MIMES = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "application/ogg": "ogg",
    "audio/mp4": "mp4",
    "video/mp4": "mp4",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
}
_UPLOAD_MIMES = {
    ".wav": {"audio/wav", "audio/wave", "audio/x-wav"},
    ".mp3": {"audio/mpeg", "audio/mp3"},
}


@dataclass(frozen=True)
class VoiceDraft:
    draft_id: str
    source_mode: str
    source_format: str
    source_sha256: str
    reference_path: Path
    duration_ms: int
    sample_rate: int
    channels: int
    consent_text: str
    consent_method: ConsentMethod
    consent_audio_path: Path | None
    temporary_paths: tuple[Path, ...]


@router.post("/voices")
async def create_voice(
    request: Request,
    stage: str = Form(...),
    source_mode: str | None = Form(None),
    consent_accepted: str | None = Form(None),
    consent_text: str | None = Form(None),
    draft_id: str | None = Form(None),
    display_name: str | None = Form(None),
    audio: Annotated[UploadFile | None, File()] = None,
    consent_audio: Annotated[UploadFile | None, File()] = None,
) -> JSONResponse:
    if stage not in {"validate", "confirm"}:
        raise KoecloneError(ErrorCode.ERR_BAD_REQUEST)
    if stage == "confirm":
        return _confirm(request, draft_id, consent_accepted, display_name)
    return await _validate(
        request,
        source_mode,
        consent_accepted,
        consent_text,
        audio,
        consent_audio,
    )


@router.get("/voices/draft/{draft_id}/audio")
def get_draft_audio(request: Request, draft_id: UUID) -> FileResponse:
    draft = request.app.state.drafts.get(str(draft_id))
    if draft is None:
        raise KoecloneError(ErrorCode.ERR_DRAFT_NOT_FOUND)
    if not draft.reference_path.is_file():
        raise KoecloneError(ErrorCode.ERR_INTERNAL)
    return FileResponse(draft.reference_path, media_type="audio/wav")


async def _validate(
    request: Request,
    source_mode: str | None,
    consent_accepted: str | None,
    consent_text: str | None,
    audio: UploadFile | None,
    consent_audio: UploadFile | None,
) -> JSONResponse:
    if source_mode not in {"direct_recording", "file_upload"} or audio is None:
        raise KoecloneError(ErrorCode.ERR_BAD_REQUEST)
    if (consent_accepted or "").strip().casefold() != "true":
        raise KoecloneError(ErrorCode.ERR_NO_CONSENT)
    if not (consent_text or "").strip():
        raise KoecloneError(ErrorCode.ERR_NO_CONSENT)
    consent_bytes = await consent_audio.read() if consent_audio is not None else None
    if source_mode == "direct_recording" and not consent_bytes:
        raise KoecloneError(ErrorCode.ERR_NO_CONSENT)
    if source_mode == "file_upload" and consent_audio is not None:
        raise KoecloneError(ErrorCode.ERR_BAD_REQUEST)

    mime = _mime(audio.content_type)
    suffix, source_format = _source_format(source_mode, audio.filename, mime)
    source_bytes = await audio.read()
    paths = request.app.state.paths
    temporary: list[Path] = []
    try:
        source_path = storage_path(paths.temporary, uuid4(), suffix)
        temporary.append(source_path)
        source_path.write_bytes(source_bytes)
        config = request.app.state.config
        if source_path.stat().st_size > config.max_upload_bytes:
            raise KoecloneError(ErrorCode.ERR_FILE_TOO_LARGE)
        if source_mode == "file_upload":
            error = validate_audio_file(
                source_path,
                mime,
                make_probe(),
                config=config,
            )
            if error is not None:
                raise KoecloneError(error)
        else:
            _validate_recording(source_path, config)

        normalized = storage_path(paths.temporary, uuid4(), ".wav")
        temporary.append(normalized)
        normalize_to_reference_wav(source_path, normalized)
        reference = normalized
        if source_mode == "file_upload":
            total_seconds = wav_duration_ms(normalized) / 1_000
            if total_seconds < 10.0:
                raise KoecloneError(ErrorCode.ERR_AUDIO_TOO_SHORT)
            ranges = detect_silence_ranges(normalized)
            start, duration = select_reference_window(total_seconds, ranges)
            reference = storage_path(paths.temporary, uuid4(), ".wav")
            temporary.append(reference)
            extract_reference_segment(
                normalized,
                reference,
                start_seconds=start,
                duration_seconds=duration,
            )

        normalized_consent: Path | None = None
        if consent_bytes is not None and consent_audio is not None:
            normalized_consent = _normalize_consent(
                paths.temporary,
                consent_audio,
                consent_bytes,
                temporary,
                config,
            )

        samples, sample_rate = _read_wav_samples(reference)
        quality_error = validate_audio_quality(
            samples,
            sample_rate,
            AudioSourceMode(source_mode),
            config=config,
        )
        if quality_error is not None:
            raise KoecloneError(quality_error)
        with wave.open(str(reference), "rb") as wav:
            channels = wav.getnchannels()
        identifier = str(uuid4())
        draft = VoiceDraft(
            identifier,
            source_mode,
            source_format,
            hashlib.sha256(source_bytes).hexdigest(),
            reference,
            wav_duration_ms(reference),
            sample_rate,
            channels,
            (consent_text or "").strip(),
            ConsentMethod.LIVE_CHALLENGE
            if source_mode == "direct_recording"
            else ConsentMethod.UPLOAD_DECLARATION,
            normalized_consent,
            tuple(temporary),
        )
        request.app.state.drafts[identifier] = draft
        return JSONResponse(
            {
                "draft_id": identifier,
                "duration_ms": draft.duration_ms,
                "sample_rate": draft.sample_rate,
                "channels": draft.channels,
                "preview_url": f"/api/voices/draft/{identifier}/audio",
            }
        )
    except Exception:
        for path in temporary:
            path.unlink(missing_ok=True)
        raise


def _confirm(
    request: Request,
    draft_id: str | None,
    consent_accepted: str | None,
    display_name: str | None,
) -> JSONResponse:
    draft = request.app.state.drafts.get(draft_id or "")
    if draft is None:
        raise KoecloneError(ErrorCode.ERR_DRAFT_NOT_FOUND)
    if (consent_accepted or "").strip().casefold() != "true":
        raise KoecloneError(ErrorCode.ERR_NO_CONSENT)
    name = (display_name or "").strip() or "マイボイス"
    if len(name) > 50:
        raise KoecloneError(ErrorCode.ERR_BAD_REQUEST)
    database = request.app.state.database
    if database.get_current_voice_profile() is not None:
        raise KoecloneError(ErrorCode.ERR_PROFILE_ALREADY_EXISTS)

    profile_id = str(uuid4())
    paths = request.app.state.paths
    reference = storage_path(paths.references, profile_id, ".wav")
    shutil.copyfile(draft.reference_path, reference)
    consent_wav: Path | None = None
    if draft.consent_audio_path is not None:
        consent_wav = storage_path(paths.consent, profile_id, ".wav")
        shutil.copyfile(draft.consent_audio_path, consent_wav)
    consent_hash = _file_sha256(consent_wav) if consent_wav is not None else None
    record = build_consent_record(
        method=draft.consent_method,
        consent_text=draft.consent_text,
        source_audio_sha256=draft.source_sha256,
        app_version=request.app.state.config.app_version,
        consent_audio_sha256=consent_hash,
    )
    profile = VoiceProfile(
        profile_id,
        name,
        draft.source_mode,
        draft.source_format,
        draft.source_sha256,
        str(reference),
        _file_sha256(reference),
        draft.consent_method.value,
        draft.consent_text,
        str(consent_wav) if consent_wav is not None else None,
        consent_hash,
        record.consented_at,
        request.app.state.engine.engine_name,
        request.app.state.engine.model_version,
    )
    try:
        database.create_voice_profile(profile)
    except StorageError as error:
        reference.unlink(missing_ok=True)
        if consent_wav is not None:
            consent_wav.unlink(missing_ok=True)
        raise KoecloneError(error.code) from error

    for path in draft.temporary_paths:
        path.unlink(missing_ok=True)
    del request.app.state.drafts[draft.draft_id]
    synthesis_text, error = build_synthesis_text(
        TEST_SENTENCE,
        [],
        config=request.app.state.config,
    )
    if error is not None or synthesis_text is None:
        raise KoecloneError(ErrorCode.ERR_INTERNAL)
    job_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    database.create_synthesis_job(
        SynthesisJob(
            job_id,
            profile_id,
            TEST_SENTENCE,
            _text_sha256(TEST_SENTENCE),
            synthesis_text,
            _text_sha256(synthesis_text),
            "[]",
            "ja",
            "queued",
            None,
            None,
            None,
            None,
            None,
            now,
            None,
        )
    )
    request.app.state.queue.submit(job_id)
    return JSONResponse(
        status_code=201,
        content={
            "voice": _voice_response(profile),
            "test_synthesis_id": job_id,
        },
    )


def _source_format(mode: str, filename: str | None, mime: str) -> tuple[str, str]:
    if mode == "direct_recording":
        source_format = _DIRECT_MIMES.get(mime)
        if source_format is None:
            raise KoecloneError(ErrorCode.ERR_FILE_UNSUPPORTED_FORMAT)
        return ".tmp", source_format
    suffix = Path(filename or "").suffix.casefold()
    if suffix not in _UPLOAD_MIMES or mime not in _UPLOAD_MIMES[suffix]:
        raise KoecloneError(ErrorCode.ERR_FILE_UNSUPPORTED_FORMAT)
    return suffix, suffix.removeprefix(".")


def _validate_recording(path: Path, config) -> None:
    try:
        result = probe_audio(path)
    except (OSError, ValueError) as error:
        raise KoecloneError(ErrorCode.ERR_FILE_CORRUPTED) from error
    if (
        result.encrypted
        or result.duration_seconds is None
        or result.duration_seconds <= 0
    ):
        raise KoecloneError(ErrorCode.ERR_FILE_CORRUPTED)
    if not result.has_audio:
        raise KoecloneError(ErrorCode.ERR_FILE_NO_AUDIO)
    minimum, maximum = config.direct_recording_seconds
    if result.duration_seconds < minimum:
        raise KoecloneError(ErrorCode.ERR_AUDIO_TOO_SHORT)
    if result.duration_seconds > maximum:
        raise KoecloneError(ErrorCode.ERR_AUDIO_TOO_LONG)


def _normalize_consent(directory, upload, content, temporary, config) -> Path:
    mime = _mime(upload.content_type)
    if mime not in _DIRECT_MIMES:
        raise KoecloneError(ErrorCode.ERR_FILE_UNSUPPORTED_FORMAT)
    source = storage_path(directory, uuid4(), ".tmp")
    temporary.append(source)
    source.write_bytes(content)
    if source.stat().st_size > config.max_upload_bytes:
        raise KoecloneError(ErrorCode.ERR_FILE_TOO_LARGE)
    try:
        result = probe_audio(source)
    except (OSError, ValueError) as error:
        raise KoecloneError(ErrorCode.ERR_FILE_CORRUPTED) from error
    if result.duration_seconds is None or result.duration_seconds <= 0:
        raise KoecloneError(ErrorCode.ERR_FILE_CORRUPTED)
    if not result.has_audio:
        raise KoecloneError(ErrorCode.ERR_FILE_NO_AUDIO)
    destination = storage_path(directory, uuid4(), ".wav")
    temporary.append(destination)
    normalize_to_reference_wav(source, destination)
    return destination


def _read_wav_samples(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise KoecloneError(ErrorCode.ERR_INTERNAL)
        sample_rate = source.getframerate()
        frames = source.readframes(source.getnframes())
    pcm = array("h")
    pcm.frombytes(frames)
    if sys.byteorder != "little":
        pcm.byteswap()
    return [value / 32768.0 for value in pcm], sample_rate


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mime(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().casefold()


def _voice_response(profile: VoiceProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "display_name": profile.display_name,
        "source_mode": profile.source_mode,
        "source_format": profile.source_format,
        "consent_method": profile.consent_method,
        "has_consent_audio": profile.consent_audio_path is not None,
        "created_at": profile.created_at,
        "engine": profile.engine,
        "model_version": profile.model_version,
    }
