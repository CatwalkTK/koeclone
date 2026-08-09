from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from koeclone.config import AppConfig
from koeclone.errors import ErrorCode


class AudioFileFormat(StrEnum):
    WAV = "wav"
    MP3 = "mp3"


@dataclass(frozen=True)
class ProbeResult:
    codec_name: str | None
    has_audio: bool
    duration_seconds: float | None
    encrypted: bool = False


Probe = Callable[[Path], ProbeResult]

MIME_TYPES = {
    AudioFileFormat.WAV: frozenset({"audio/wav", "audio/wave", "audio/x-wav"}),
    AudioFileFormat.MP3: frozenset({"audio/mpeg", "audio/mp3"}),
}


def validate_audio_file(
    path: Path,
    declared_mime: str,
    probe: Probe,
    *,
    config: AppConfig | None = None,
) -> ErrorCode | None:
    settings = config or AppConfig()
    if path.stat().st_size > settings.max_upload_bytes:
        return ErrorCode.ERR_FILE_TOO_LARGE

    expected_format = _format_from_suffix(path.suffix)
    if expected_format is None:
        return ErrorCode.ERR_FILE_UNSUPPORTED_FORMAT

    detected_format = detect_audio_format(path)
    if detected_format is None:
        return ErrorCode.ERR_FILE_CORRUPTED
    if detected_format is not expected_format:
        return ErrorCode.ERR_FILE_FORMAT_MISMATCH
    if declared_mime.casefold() not in MIME_TYPES[detected_format]:
        return ErrorCode.ERR_FILE_FORMAT_MISMATCH

    try:
        result = probe(path)
    except (OSError, ValueError):
        return ErrorCode.ERR_FILE_CORRUPTED

    if result.encrypted:
        return ErrorCode.ERR_FILE_CORRUPTED
    if not result.has_audio:
        return ErrorCode.ERR_FILE_NO_AUDIO
    if not _codec_matches(detected_format, result.codec_name):
        return ErrorCode.ERR_FILE_FORMAT_MISMATCH
    if result.duration_seconds is None or result.duration_seconds <= 0:
        return ErrorCode.ERR_FILE_CORRUPTED
    if result.duration_seconds < settings.upload_seconds[0]:
        return ErrorCode.ERR_AUDIO_TOO_SHORT
    if result.duration_seconds > settings.upload_seconds[1]:
        return ErrorCode.ERR_AUDIO_TOO_LONG
    return None


def detect_audio_format(path: Path) -> AudioFileFormat | None:
    with path.open("rb") as source:
        header = source.read(12)
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return AudioFileFormat.WAV
    if header[:3] == b"ID3":
        return AudioFileFormat.MP3
    if len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0:
        return AudioFileFormat.MP3
    return None


def _format_from_suffix(suffix: str) -> AudioFileFormat | None:
    try:
        return AudioFileFormat(suffix.removeprefix(".").casefold())
    except ValueError:
        return None


def _codec_matches(
    audio_format: AudioFileFormat,
    codec_name: str | None,
) -> bool:
    if codec_name is None:
        return False
    if audio_format is AudioFileFormat.WAV:
        return codec_name.casefold().startswith("pcm_")
    return codec_name.casefold() == "mp3"
