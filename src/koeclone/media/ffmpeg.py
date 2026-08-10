from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import wave
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from koeclone.domain.file_probe import Probe, ProbeResult
from koeclone.errors import ErrorCode, KoecloneError


class FFmpegError(KoecloneError):
    """FFmpeg処理層の失敗。"""


@dataclass(frozen=True)
class FFmpegPaths:
    ffmpeg: Path
    ffprobe: Path


def resolve_ffmpeg_paths() -> FFmpegPaths:
    try:
        from static_ffmpeg.run import (
            get_or_fetch_platform_executables_else_raise,
        )

        ffmpeg, ffprobe = get_or_fetch_platform_executables_else_raise()
    except Exception as error:
        raise FFmpegError(ErrorCode.ERR_INTERNAL) from error
    return FFmpegPaths(Path(ffmpeg), Path(ffprobe))


def _run(
    paths: FFmpegPaths,
    args: Sequence[str],
    *,
    timeout: float = 120.0,
) -> bytes:
    return _run_process(paths, args, timeout=timeout).stdout


def _run_process(
    paths: FFmpegPaths,
    args: Sequence[str],
    *,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[bytes]:
    command = list(args)
    allowed_binaries = {str(paths.ffmpeg), str(paths.ffprobe)}
    if not command or command[0] not in allowed_binaries:
        raise ValueError("Command must use an injected FFmpeg binary")
    try:
        result = subprocess.run(
            command,
            shell=False,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise FFmpegError(ErrorCode.ERR_INTERNAL) from error
    if result.returncode != 0:
        raise FFmpegError(ErrorCode.ERR_INTERNAL)
    return result


def normalize_to_reference_wav(
    source: Path,
    destination: Path,
    *,
    sample_rate: int = 24_000,
    paths: FFmpegPaths | None = None,
) -> Path:
    if sample_rate < 24_000:
        raise ValueError("sample_rate must be at least 24000")
    resolved = paths or resolve_ffmpeg_paths()
    _run(
        resolved,
        [
            str(resolved.ffmpeg),
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-vn",
            "-map",
            "a:0",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(destination),
        ],
    )
    _require_output(destination)
    return destination


def probe_audio(
    source: Path,
    *,
    paths: FFmpegPaths | None = None,
) -> ProbeResult:
    resolved = paths or resolve_ffmpeg_paths()
    try:
        output = _run(
            resolved,
            [
                str(resolved.ffprobe),
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(source),
            ],
        )
    except FFmpegError as error:
        raise OSError("Audio probe failed") from error
    try:
        payload = json.loads(output)
        streams = payload.get("streams", [])
        audio_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"),
            None,
        )
        duration_value = payload.get("format", {}).get("duration")
        if duration_value is None and audio_stream is not None:
            duration_value = audio_stream.get("duration")
        duration = float(duration_value) if duration_value is not None else None
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Invalid ffprobe output") from error
    return ProbeResult(
        codec_name=audio_stream.get("codec_name") if audio_stream else None,
        has_audio=audio_stream is not None,
        duration_seconds=duration,
        encrypted=False,
    )


def make_probe(paths: FFmpegPaths | None = None) -> Probe:
    def probe(source: Path) -> ProbeResult:
        return probe_audio(source, paths=paths)

    return probe


def detect_silence_ranges(
    source: Path,
    *,
    noise_dbfs: float = -50.0,
    min_silence_seconds: float = 0.5,
    paths: FFmpegPaths | None = None,
) -> list[tuple[float, float]]:
    resolved = paths or resolve_ffmpeg_paths()
    result = _run_process(
        resolved,
        [
            str(resolved.ffmpeg),
            "-nostdin",
            "-y",
            "-v",
            "info",
            "-i",
            str(source),
            "-af",
            f"silencedetect=noise={noise_dbfs}dB:d={min_silence_seconds}",
            "-f",
            "null",
            "-",
        ],
    )
    starts = re.compile(r"silence_start:\s*([0-9]+(?:\.[0-9]+)?)")
    ends = re.compile(r"silence_end:\s*([0-9]+(?:\.[0-9]+)?)")
    ranges: list[tuple[float, float]] = []
    current_start: float | None = None
    for line in result.stderr.decode(errors="replace").splitlines():
        start_match = starts.search(line)
        if start_match:
            current_start = float(start_match.group(1))
        end_match = ends.search(line)
        if end_match and current_start is not None:
            ranges.append((current_start, float(end_match.group(1))))
            current_start = None
    if current_start is not None:
        duration = probe_audio(source, paths=resolved).duration_seconds
        if duration is not None:
            ranges.append((current_start, duration))
    return ranges


def select_reference_window(
    total_seconds: float,
    silence_ranges: Sequence[tuple[float, float]],
    *,
    min_seconds: float = 10.0,
    max_seconds: float = 30.0,
) -> tuple[float, float]:
    if total_seconds < min_seconds:
        raise ValueError("Audio is shorter than the minimum reference length")
    if min_seconds <= 0 or max_seconds < min_seconds:
        raise ValueError("Invalid reference duration bounds")

    merged: list[tuple[float, float]] = []
    for start, end in sorted(silence_ranges):
        start = max(0.0, min(start, total_seconds))
        end = max(start, min(end, total_seconds))
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        elif end > start:
            merged.append((start, end))

    spans: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in merged:
        if start > cursor:
            spans.append((cursor, start - cursor))
        cursor = max(cursor, end)
    if cursor < total_seconds:
        spans.append((cursor, total_seconds - cursor))

    longest = max(spans, key=lambda span: (span[1], -span[0]), default=None)
    if longest is None or longest[1] < min_seconds:
        return (0.0, min(total_seconds, max_seconds))
    return (longest[0], min(longest[1], max_seconds))


def extract_reference_segment(
    source: Path,
    destination: Path,
    *,
    start_seconds: float,
    duration_seconds: float,
    sample_rate: int = 24_000,
    paths: FFmpegPaths | None = None,
) -> Path:
    if start_seconds < 0:
        raise ValueError("start_seconds cannot be negative")
    if not 10.0 <= duration_seconds <= 30.0:
        raise ValueError("duration_seconds must be between 10 and 30")
    if sample_rate < 24_000:
        raise ValueError("sample_rate must be at least 24000")
    resolved = paths or resolve_ffmpeg_paths()
    _run(
        resolved,
        [
            str(resolved.ffmpeg),
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-ss",
            str(start_seconds),
            "-t",
            str(duration_seconds),
            "-i",
            str(source),
            "-vn",
            "-map",
            "a:0",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(destination),
        ],
    )
    _require_output(destination)
    return destination


def concat_wavs(
    sources: Sequence[Path],
    destination: Path,
    *,
    paths: FFmpegPaths | None = None,
) -> Path:
    if not sources:
        raise ValueError("At least one source WAV is required")
    if len(sources) == 1:
        shutil.copyfile(sources[0], destination)
        return destination

    resolved = paths or resolve_ffmpeg_paths()
    with tempfile.TemporaryDirectory() as temporary_directory:
        list_path = Path(temporary_directory) / "inputs.txt"
        lines = [
            f"file '{_escape_concat_path(source.resolve())}'" for source in sources
        ]
        list_path.write_text("\n".join(lines), encoding="utf-8")
        _run(
            resolved,
            [
                str(resolved.ffmpeg),
                "-nostdin",
                "-y",
                "-v",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(destination),
            ],
        )
    _require_output(destination)
    return destination


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as source:
        return round(source.getnframes() / source.getframerate() * 1_000)


def _require_output(path: Path) -> None:
    if not path.is_file():
        raise FFmpegError(ErrorCode.ERR_INTERNAL)


def _escape_concat_path(path: Path) -> str:
    return str(path).replace("'", "'\\''")
