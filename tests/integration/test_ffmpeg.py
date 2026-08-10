from __future__ import annotations

import inspect
import math
import os
import random
import struct
import subprocess
import wave
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path

import pytest

from koeclone.domain.file_probe import validate_audio_file
from koeclone.errors import ErrorCode
from koeclone.media.ffmpeg import (
    FFmpegError,
    FFmpegPaths,
    concat_wavs,
    detect_silence_ranges,
    extract_reference_segment,
    make_probe,
    normalize_to_reference_wav,
    probe_audio,
    resolve_ffmpeg_paths,
    select_reference_window,
    wav_duration_ms,
)


@pytest.fixture(scope="module")
def ffmpeg_paths() -> FFmpegPaths:
    return resolve_ffmpeg_paths()


def _write_wav(
    path: Path,
    *,
    segments: list[tuple[float, float]],
    sample_rate: int = 24_000,
    channels: int = 1,
) -> Path:
    samples: list[int] = []
    for duration, frequency in segments:
        frame_count = round(duration * sample_rate)
        for index in range(frame_count):
            value = (
                0
                if frequency == 0
                else round(
                    8_000 * math.sin(2 * math.pi * frequency * index / sample_rate)
                )
            )
            samples.extend([value] * channels)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return path


@pytest.fixture
def stereo_wav(tmp_path: Path) -> Path:
    return _write_wav(
        tmp_path / "source.wav",
        segments=[(1.0, 440.0)],
        sample_rate=44_100,
        channels=2,
    )


@pytest.fixture
def mp3_file(
    stereo_wav: Path,
    ffmpeg_paths: FFmpegPaths,
    tmp_path: Path,
) -> Path:
    destination = tmp_path / "source.mp3"
    result = subprocess.run(
        [
            str(ffmpeg_paths.ffmpeg),
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-i",
            str(stereo_wav),
            str(destination),
        ],
        shell=False,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    return destination


def test_resolve_ffmpeg_paths_returns_executable_files(
    ffmpeg_paths: FFmpegPaths,
) -> None:
    assert ffmpeg_paths.ffmpeg.is_file()
    assert ffmpeg_paths.ffprobe.is_file()
    assert os.access(ffmpeg_paths.ffmpeg, os.X_OK)
    assert os.access(ffmpeg_paths.ffprobe, os.X_OK)


def test_normalizes_stereo_wav_to_reference_format(
    stereo_wav: Path,
    ffmpeg_paths: FFmpegPaths,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "normalized.wav"

    result = normalize_to_reference_wav(stereo_wav, destination, paths=ffmpeg_paths)

    assert result == destination
    with wave.open(str(destination), "rb") as normalized:
        assert normalized.getnchannels() == 1
        assert normalized.getframerate() == 24_000
        assert normalized.getsampwidth() == 2
    with pytest.raises(ValueError):
        normalize_to_reference_wav(
            stereo_wav,
            tmp_path / "invalid.wav",
            sample_rate=16_000,
            paths=ffmpeg_paths,
        )


def test_normalizes_mp3(
    mp3_file: Path,
    ffmpeg_paths: FFmpegPaths,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "normalized.wav"

    normalize_to_reference_wav(mp3_file, destination, paths=ffmpeg_paths)

    with wave.open(str(destination), "rb") as normalized:
        assert normalized.getnchannels() == 1
        assert normalized.getframerate() == 24_000
        assert normalized.getsampwidth() == 2


def test_probe_audio_reports_generated_wav_and_mp3(
    stereo_wav: Path,
    mp3_file: Path,
    ffmpeg_paths: FFmpegPaths,
) -> None:
    wav_result = probe_audio(stereo_wav, paths=ffmpeg_paths)
    mp3_result = probe_audio(mp3_file, paths=ffmpeg_paths)

    assert wav_result.has_audio is True
    assert wav_result.codec_name is not None
    assert wav_result.codec_name.startswith("pcm_")
    assert wav_result.duration_seconds == pytest.approx(1.0, abs=0.2)
    assert mp3_result.codec_name == "mp3"


def test_probe_audio_rejects_random_bytes(
    ffmpeg_paths: FFmpegPaths,
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid.wav"
    source.write_bytes(random.Random(0).randbytes(128))

    with pytest.raises((OSError, ValueError)):
        probe_audio(source, paths=ffmpeg_paths)


def test_make_probe_integrates_with_file_validation(
    ffmpeg_paths: FFmpegPaths,
    tmp_path: Path,
) -> None:
    source = _write_wav(tmp_path / "valid.wav", segments=[(12.0, 440.0)])

    result = validate_audio_file(source, "audio/wav", make_probe(ffmpeg_paths))

    assert result is None


def test_detects_leading_and_trailing_silence(
    ffmpeg_paths: FFmpegPaths,
    tmp_path: Path,
) -> None:
    source = _write_wav(
        tmp_path / "silence.wav",
        segments=[(1.0, 0.0), (2.0, 440.0), (1.0, 0.0)],
    )

    ranges = detect_silence_ranges(source, paths=ffmpeg_paths)

    assert ranges[0] == pytest.approx((0.0, 1.0), abs=0.1)
    assert ranges[-1] == pytest.approx((3.0, 4.0), abs=0.1)


@pytest.mark.parametrize(
    ("total", "silences", "minimum", "maximum", "expected"),
    [
        (30.0, [(0.0, 2.0), (12.0, 14.0), (28.0, 30.0)], 10.0, 30.0, (14.0, 14.0)),
        (60.0, [(35.0, 40.0)], 10.0, 30.0, (0.0, 30.0)),
        (20.0, [(2.0, 12.0)], 10.0, 30.0, (0.0, 20.0)),
        (30.0, [(10.0, 20.0)], 10.0, 30.0, (0.0, 10.0)),
    ],
)
def test_select_reference_window(
    total: float,
    silences: list[tuple[float, float]],
    minimum: float,
    maximum: float,
    expected: tuple[float, float],
) -> None:
    assert select_reference_window(
        total,
        silences,
        min_seconds=minimum,
        max_seconds=maximum,
    ) == pytest.approx(expected)


def test_select_reference_window_rejects_short_audio() -> None:
    with pytest.raises(ValueError):
        select_reference_window(9.9, [], min_seconds=10.0)


def test_extracts_ten_second_reference_segment(
    ffmpeg_paths: FFmpegPaths,
    tmp_path: Path,
) -> None:
    source = _write_wav(tmp_path / "source.wav", segments=[(12.0, 440.0)])
    destination = tmp_path / "reference.wav"

    extract_reference_segment(
        source,
        destination,
        start_seconds=1.0,
        duration_seconds=10.0,
        paths=ffmpeg_paths,
    )

    assert wav_duration_ms(destination) == pytest.approx(10_000, abs=200)
    for invalid_duration in (5.0, 31.0):
        with pytest.raises(ValueError):
            extract_reference_segment(
                source,
                tmp_path / f"invalid-{invalid_duration}.wav",
                start_seconds=0.0,
                duration_seconds=invalid_duration,
                paths=ffmpeg_paths,
            )


def _zero_crossings(samples: Iterator[int]) -> int:
    values = list(samples)
    return sum(
        (left < 0 <= right) or (left >= 0 > right) for left, right in pairwise(values)
    )


def test_concat_wavs_preserves_duration_and_order(
    ffmpeg_paths: FFmpegPaths,
    tmp_path: Path,
) -> None:
    sources = [
        _write_wav(tmp_path / f"part-{index}.wav", segments=[(duration, frequency)])
        for index, (duration, frequency) in enumerate(
            [(0.5, 220.0), (0.75, 440.0), (1.0, 880.0)]
        )
    ]
    destination = tmp_path / "joined.wav"

    concat_wavs(sources, destination, paths=ffmpeg_paths)

    assert wav_duration_ms(destination) == pytest.approx(2_250, abs=200)
    with wave.open(str(destination), "rb") as joined:
        samples = struct.unpack(
            f"<{joined.getnframes()}h",
            joined.readframes(joined.getnframes()),
        )
    boundaries = (0, 12_000, 30_000, 54_000)
    crossings = [
        _zero_crossings(iter(samples[start:end])) for start, end in pairwise(boundaries)
    ]
    assert crossings[0] < crossings[1] < crossings[2]
    with pytest.raises(ValueError):
        concat_wavs([], tmp_path / "empty.wav", paths=ffmpeg_paths)


def test_wav_duration_ms_uses_wave_frames(tmp_path: Path) -> None:
    source = _write_wav(tmp_path / "duration.wav", segments=[(1.25, 440.0)])

    assert wav_duration_ms(source) == 1_250


def test_source_avoids_unsafe_process_apis_and_fixed_paths() -> None:
    import koeclone.media.ffmpeg as module

    source = inspect.getsource(module)
    forbidden = (
        "shell=True",
        "os.system",
        "os.popen",
        "subprocess.getoutput",
        "darwin_arm64",
        "site-packages",
    )

    assert all(value not in source for value in forbidden)


def test_ffmpeg_failure_is_sanitized(
    ffmpeg_paths: FFmpegPaths,
    tmp_path: Path,
) -> None:
    with pytest.raises(FFmpegError) as captured:
        normalize_to_reference_wav(
            tmp_path / "missing.wav",
            tmp_path / "output.wav",
            paths=ffmpeg_paths,
        )

    assert captured.value.code is ErrorCode.ERR_INTERNAL
    assert "No such file" not in str(captured.value)
