from pathlib import Path

import pytest

from koeclone.domain.file_probe import ProbeResult, validate_audio_file
from koeclone.errors import ErrorCode

WAV_HEADER = b"RIFF\x24\x00\x00\x00WAVE"
MP3_HEADER = b"ID3\x04\x00\x00"


def write_file(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def valid_probe(codec_name: str) -> ProbeResult:
    return ProbeResult(codec_name=codec_name, has_audio=True, duration_seconds=20.0)


@pytest.mark.parametrize(
    ("filename", "content", "mime", "codec"),
    [
        ("voice.wav", WAV_HEADER, "audio/wav", "pcm_s16le"),
        ("voice.mp3", MP3_HEADER, "audio/mpeg", "mp3"),
        ("voice.mp3", b"\xff\xfb\x90\x64", "audio/mpeg", "mp3"),
    ],
)
def test_accepts_matching_wav_and_mp3(
    tmp_path: Path,
    filename: str,
    content: bytes,
    mime: str,
    codec: str,
) -> None:
    path = write_file(tmp_path / filename, content)

    assert validate_audio_file(path, mime, lambda _: valid_probe(codec)) is None


def test_rejects_disguised_extension(tmp_path: Path) -> None:
    path = write_file(tmp_path / "voice.wav", MP3_HEADER)

    assert (
        validate_audio_file(path, "audio/wav", lambda _: valid_probe("mp3"))
        is ErrorCode.ERR_FILE_FORMAT_MISMATCH
    )


def test_rejects_mime_mismatch(tmp_path: Path) -> None:
    path = write_file(tmp_path / "voice.wav", WAV_HEADER)

    assert (
        validate_audio_file(path, "audio/mpeg", lambda _: valid_probe("pcm_s16le"))
        is ErrorCode.ERR_FILE_FORMAT_MISMATCH
    )


@pytest.mark.parametrize("content", [b"", b"RIFFbroken"])
def test_rejects_empty_or_corrupted_header(tmp_path: Path, content: bytes) -> None:
    path = write_file(tmp_path / "voice.wav", content)

    assert (
        validate_audio_file(path, "audio/wav", lambda _: valid_probe("pcm_s16le"))
        is ErrorCode.ERR_FILE_CORRUPTED
    )


def test_rejects_unsupported_format(tmp_path: Path) -> None:
    path = write_file(tmp_path / "voice.flac", b"fLaC")

    assert (
        validate_audio_file(path, "audio/flac", lambda _: valid_probe("flac"))
        is ErrorCode.ERR_FILE_UNSUPPORTED_FORMAT
    )


def test_rejects_file_over_50_mb(tmp_path: Path) -> None:
    path = tmp_path / "large.wav"
    with path.open("wb") as output:
        output.write(WAV_HEADER)
        output.seek(50 * 1024 * 1024)
        output.write(b"\x00")

    assert (
        validate_audio_file(path, "audio/wav", lambda _: valid_probe("pcm_s16le"))
        is ErrorCode.ERR_FILE_TOO_LARGE
    )


def test_rejects_probe_failure(tmp_path: Path) -> None:
    path = write_file(tmp_path / "voice.wav", WAV_HEADER)

    def failing_probe(_: Path) -> ProbeResult:
        raise ValueError("decode failed")

    assert (
        validate_audio_file(path, "audio/wav", failing_probe)
        is ErrorCode.ERR_FILE_CORRUPTED
    )


def test_rejects_missing_audio_stream(tmp_path: Path) -> None:
    path = write_file(tmp_path / "voice.wav", WAV_HEADER)
    result = ProbeResult(codec_name=None, has_audio=False, duration_seconds=None)

    assert (
        validate_audio_file(path, "audio/wav", lambda _: result)
        is ErrorCode.ERR_FILE_NO_AUDIO
    )


def test_rejects_encrypted_audio(tmp_path: Path) -> None:
    path = write_file(tmp_path / "voice.mp3", MP3_HEADER)
    result = ProbeResult("mp3", True, 20.0, encrypted=True)

    assert (
        validate_audio_file(path, "audio/mpeg", lambda _: result)
        is ErrorCode.ERR_FILE_CORRUPTED
    )


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (9.9, ErrorCode.ERR_AUDIO_TOO_SHORT),
        (180.1, ErrorCode.ERR_AUDIO_TOO_LONG),
    ],
)
def test_rejects_duration_outside_upload_range(
    tmp_path: Path, duration: float, expected: ErrorCode
) -> None:
    path = write_file(tmp_path / "voice.mp3", MP3_HEADER)
    result = ProbeResult("mp3", True, duration)

    assert validate_audio_file(path, "audio/mpeg", lambda _: result) is expected


def test_rejects_codec_mismatch(tmp_path: Path) -> None:
    path = write_file(tmp_path / "voice.wav", WAV_HEADER)

    assert (
        validate_audio_file(path, "audio/wav", lambda _: valid_probe("mp3"))
        is ErrorCode.ERR_FILE_FORMAT_MISMATCH
    )
