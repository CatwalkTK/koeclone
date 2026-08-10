from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from koeclone.config import AppConfig
from koeclone.domain.pronunciation import (
    PronunciationOverride,
    validate_pronunciation_overrides,
)
from koeclone.domain.sidecar import write_sidecar
from koeclone.domain.synthesis_text import (
    build_synthesis_text,
    plan_synthesis_chunks,
)
from koeclone.engines.base import SpeechEngine
from koeclone.errors import ErrorCode, KoecloneError
from koeclone.media.ffmpeg import FFmpegPaths, concat_wavs, wav_duration_ms
from koeclone.storage.db import Database
from koeclone.storage.files import DataPaths, storage_path


class PipelineError(KoecloneError):
    """生成パイプラインの失敗。"""


@dataclass(frozen=True)
class SynthesisRequest:
    job_id: str
    voice_id: str
    text: str
    overrides: tuple[PronunciationOverride, ...] = ()
    language: str = "ja"


@dataclass(frozen=True)
class SynthesisPipeline:
    engine: SpeechEngine
    database: Database
    paths: DataPaths
    config: AppConfig
    ffmpeg_paths: FFmpegPaths | None = None

    def run(self, request: SynthesisRequest) -> None:
        temporary_directory: Path | None = None
        final_path: Path | None = None
        watermark_failed = False
        running_updated = False
        try:
            self.database.update_synthesis_job(request.job_id, status="running")
            running_updated = True
            if request.language != "ja":
                raise PipelineError(ErrorCode.ERR_INTERNAL)

            profile = self.database.get_current_voice_profile()
            if (
                profile is None
                or profile.id != request.voice_id
                or profile.consent_text == ""
            ):
                raise PipelineError(ErrorCode.ERR_NO_CONSENT)

            override_error = validate_pronunciation_overrides(
                request.text,
                list(request.overrides),
            )
            if override_error is not None:
                raise PipelineError(override_error)

            synthesis_text, text_error = build_synthesis_text(
                request.text,
                list(request.overrides),
                config=self.config,
            )
            if text_error is not None:
                raise PipelineError(text_error)
            if synthesis_text is None:
                raise PipelineError(ErrorCode.ERR_INTERNAL)

            chunks = plan_synthesis_chunks(synthesis_text)
            if not chunks:
                raise PipelineError(ErrorCode.ERR_TEXT_EMPTY)

            self.engine.load()
            job_hex = UUID(request.job_id).hex
            temporary_directory = Path(
                tempfile.mkdtemp(prefix=f"{job_hex}_", dir=self.paths.temporary)
            )
            chunk_paths: list[Path] = []
            for index, chunk in enumerate(chunks, start=1):
                chunk_path = temporary_directory / f"{job_hex}_{index:04d}.wav"
                self.engine.synthesize(
                    chunk,
                    Path(profile.reference_path),
                    "ja",
                    output_path=chunk_path,
                )
                chunk_paths.append(chunk_path)

            expected_duration_ms = sum(wav_duration_ms(path) for path in chunk_paths)
            final_path = storage_path(self.paths.generated, request.job_id, ".wav")
            if len(chunk_paths) == 1:
                shutil.copyfile(chunk_paths[0], final_path)
            else:
                concat_wavs(chunk_paths, final_path, paths=self.ffmpeg_paths)
            if abs(wav_duration_ms(final_path) - expected_duration_ms) > 50:
                raise PipelineError(ErrorCode.ERR_INTERNAL)

            if not self.engine.detect_watermark(final_path):
                watermark_failed = True
                final_path.unlink(missing_ok=True)
                raise PipelineError(ErrorCode.ERR_WATERMARK_NOT_DETECTED)

            sidecar_path = write_sidecar(
                final_path,
                engine=self.engine.engine_name,
                model_version=self.engine.model_version,
                voice_id=request.voice_id,
                original_text=request.text,
                synthesis_text=synthesis_text,
                pronunciation_overrides=request.overrides,
            )
            self.database.update_synthesis_job(
                request.job_id,
                status="succeeded",
                audio_path=str(final_path),
                sidecar_path=str(sidecar_path),
                duration_ms=wav_duration_ms(final_path),
                watermark_detected=True,
                error_code=None,
                completed_at=_utc_now(),
            )
        except Exception as error:
            failure = _as_pipeline_error(error)
            _remove_generated_artifacts(final_path)
            if running_updated:
                update_fields: dict[str, object] = {
                    "status": "failed",
                    "audio_path": None,
                    "sidecar_path": None,
                    "duration_ms": None,
                    "error_code": failure.code.value,
                    "completed_at": _utc_now(),
                }
                if watermark_failed:
                    update_fields["watermark_detected"] = False
                try:
                    self.database.update_synthesis_job(
                        request.job_id,
                        **update_fields,
                    )
                except Exception as update_error:
                    raise PipelineError(ErrorCode.ERR_INTERNAL) from update_error
            raise failure from error
        finally:
            if temporary_directory is not None:
                shutil.rmtree(temporary_directory, ignore_errors=True)


def _as_pipeline_error(error: Exception) -> PipelineError:
    if isinstance(error, PipelineError):
        return error
    if isinstance(error, KoecloneError):
        return PipelineError(error.code)
    return PipelineError(ErrorCode.ERR_INTERNAL)


def _remove_generated_artifacts(final_path: Path | None) -> None:
    if final_path is None:
        return
    final_path.unlink(missing_ok=True)
    final_path.with_suffix(".json").unlink(missing_ok=True)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
