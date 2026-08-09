from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum

from koeclone.config import AppConfig
from koeclone.errors import ErrorCode


class AudioSourceMode(StrEnum):
    DIRECT_RECORDING = "direct_recording"
    FILE_UPLOAD = "file_upload"


def validate_audio_quality(
    samples: Sequence[float],
    sample_rate: int,
    source_mode: AudioSourceMode,
    *,
    config: AppConfig | None = None,
) -> ErrorCode | None:
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")

    settings = config or AppConfig()
    duration_seconds = len(samples) / sample_rate
    minimum, maximum = _duration_range(source_mode, settings)
    if duration_seconds < minimum:
        return ErrorCode.ERR_AUDIO_TOO_SHORT
    if duration_seconds > maximum:
        return ErrorCode.ERR_AUDIO_TOO_LONG

    if _silence_ratio(samples, sample_rate, settings) >= settings.max_silence_ratio:
        return ErrorCode.ERR_AUDIO_MOSTLY_SILENT

    peak = max(abs(sample) for sample in samples)
    peak_limit = 10 ** (settings.peak_limit_dbfs / 20)
    if peak > peak_limit or any(
        abs(sample) >= settings.absolute_sample_limit for sample in samples
    ):
        return ErrorCode.ERR_AUDIO_CLIPPING

    rms_dbfs = _to_dbfs(_rms(samples))
    if not settings.min_rms_dbfs <= rms_dbfs <= settings.max_rms_dbfs:
        return ErrorCode.ERR_AUDIO_LEVEL_OUT_OF_RANGE
    return None


def _duration_range(
    source_mode: AudioSourceMode,
    config: AppConfig,
) -> tuple[float, float]:
    if source_mode is AudioSourceMode.DIRECT_RECORDING:
        return config.direct_recording_seconds
    if source_mode is AudioSourceMode.FILE_UPLOAD:
        return config.upload_seconds
    raise ValueError(f"Unsupported audio source mode: {source_mode}")


def _silence_ratio(
    samples: Sequence[float],
    sample_rate: int,
    config: AppConfig,
) -> float:
    window_size = max(1, round(sample_rate * config.silence_window_ms / 1_000))
    window_starts = range(0, len(samples), window_size)
    silent_windows = sum(
        _to_dbfs(_rms(samples[start : start + window_size]))
        < config.silence_rms_dbfs
        for start in window_starts
    )
    window_count = math.ceil(len(samples) / window_size)
    return silent_windows / window_count


def _rms(samples: Sequence[float]) -> float:
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def _to_dbfs(amplitude: float) -> float:
    return 20 * math.log10(amplitude) if amplitude > 0 else -math.inf
