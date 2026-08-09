import math

import pytest

from koeclone.domain.audio_quality import AudioSourceMode, validate_audio_quality
from koeclone.errors import ErrorCode

SAMPLE_RATE = 1_000


def sine_wave(seconds: float, amplitude: float = 0.08) -> list[float]:
    sample_count = int(seconds * SAMPLE_RATE)
    return [
        amplitude * math.sin(2 * math.pi * 50 * index / SAMPLE_RATE)
        for index in range(sample_count)
    ]


def normal_wave(seconds: float = 12.0) -> list[float]:
    silent_count = int(seconds * SAMPLE_RATE * 0.25)
    samples = [0.0] * silent_count + sine_wave(seconds * 0.75)
    samples[-1] = 10 ** (-10 / 20)
    return samples


def test_accepts_poc_like_recording() -> None:
    assert (
        validate_audio_quality(
            normal_wave(), SAMPLE_RATE, AudioSourceMode.DIRECT_RECORDING
        )
        is None
    )


def test_rejects_mostly_silent_audio() -> None:
    samples = [0.0] * (11 * SAMPLE_RATE) + sine_wave(1)

    assert (
        validate_audio_quality(
            samples, SAMPLE_RATE, AudioSourceMode.DIRECT_RECORDING
        )
        is ErrorCode.ERR_AUDIO_MOSTLY_SILENT
    )


def test_rejects_clipping_audio() -> None:
    samples = normal_wave()
    samples[0] = 1.0

    assert (
        validate_audio_quality(
            samples, SAMPLE_RATE, AudioSourceMode.DIRECT_RECORDING
        )
        is ErrorCode.ERR_AUDIO_CLIPPING
    )


@pytest.mark.parametrize(
    ("amplitude", "expected"),
    [
        (0.01, ErrorCode.ERR_AUDIO_LEVEL_OUT_OF_RANGE),
        (0.7, ErrorCode.ERR_AUDIO_LEVEL_OUT_OF_RANGE),
    ],
)
def test_rejects_audio_outside_rms_range(
    amplitude: float, expected: ErrorCode
) -> None:
    samples = sine_wave(12, amplitude)

    assert (
        validate_audio_quality(
            samples, SAMPLE_RATE, AudioSourceMode.DIRECT_RECORDING
        )
        is expected
    )


@pytest.mark.parametrize(
    ("mode", "seconds", "expected"),
    [
        (AudioSourceMode.DIRECT_RECORDING, 9, ErrorCode.ERR_AUDIO_TOO_SHORT),
        (AudioSourceMode.DIRECT_RECORDING, 61, ErrorCode.ERR_AUDIO_TOO_LONG),
        (AudioSourceMode.FILE_UPLOAD, 9, ErrorCode.ERR_AUDIO_TOO_SHORT),
        (AudioSourceMode.FILE_UPLOAD, 181, ErrorCode.ERR_AUDIO_TOO_LONG),
    ],
)
def test_rejects_duration_outside_mode_range(
    mode: AudioSourceMode, seconds: int, expected: ErrorCode
) -> None:
    assert validate_audio_quality(sine_wave(seconds), SAMPLE_RATE, mode) is expected


@pytest.mark.parametrize(
    ("mode", "seconds"),
    [
        (AudioSourceMode.DIRECT_RECORDING, 10),
        (AudioSourceMode.DIRECT_RECORDING, 60),
        (AudioSourceMode.FILE_UPLOAD, 10),
        (AudioSourceMode.FILE_UPLOAD, 180),
    ],
)
def test_accepts_duration_boundaries(mode: AudioSourceMode, seconds: int) -> None:
    assert validate_audio_quality(sine_wave(seconds), SAMPLE_RATE, mode) is None
