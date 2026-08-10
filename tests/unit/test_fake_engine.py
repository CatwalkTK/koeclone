import inspect
import struct
import wave
from pathlib import Path

import pytest

from koeclone.engines.base import EngineError, SpeechEngine
from koeclone.engines.fake import FakeEngine
from koeclone.errors import ErrorCode


def synthesize(engine: FakeEngine, tmp_path: Path, text: str = "テスト") -> Path:
    output = tmp_path / f"{len(engine.calls)}.wav"
    return engine.synthesize(
        text,
        tmp_path / "reference.wav",
        "ja",
        output_path=output,
    )


def test_fake_engine_satisfies_protocol() -> None:
    engine = FakeEngine()

    assert isinstance(engine, SpeechEngine)
    assert engine.engine_name
    assert engine.model_version


def test_synthesis_requires_load(tmp_path: Path) -> None:
    engine = FakeEngine()

    with pytest.raises(EngineError) as error:
        synthesize(engine, tmp_path)

    assert error.value.code is ErrorCode.ERR_INTERNAL


def test_load_is_safe_to_call_repeatedly() -> None:
    engine = FakeEngine()

    engine.load()
    engine.load()

    assert engine.load_count == 2


def test_synthesis_writes_expected_wav_format(tmp_path: Path) -> None:
    engine = FakeEngine()
    engine.load()

    output = synthesize(engine, tmp_path)

    assert output.exists()
    with wave.open(str(output), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 24_000
        assert audio.getnframes() > 0


def test_synthesized_wav_is_non_silent_and_not_clipped(tmp_path: Path) -> None:
    engine = FakeEngine()
    engine.load()
    output = synthesize(engine, tmp_path)

    with wave.open(str(output), "rb") as audio:
        frames = audio.readframes(audio.getnframes())
    samples = struct.unpack(f"<{len(frames) // 2}h", frames)

    assert max(abs(sample) for sample in samples) > 1_000
    assert max(abs(sample) for sample in samples) < 32_767


def test_output_is_deterministic_and_length_depends_on_text(tmp_path: Path) -> None:
    engine = FakeEngine()
    engine.load()

    first = synthesize(engine, tmp_path, "同じ文章")
    first_bytes = first.read_bytes()
    second = synthesize(engine, tmp_path, "同じ文章")
    third = synthesize(engine, tmp_path, "長さの異なる文章です")

    assert second.read_bytes() == first_bytes
    assert len(third.read_bytes()) != len(first_bytes)


def test_rejects_non_japanese_language(tmp_path: Path) -> None:
    engine = FakeEngine()
    engine.load()

    with pytest.raises(ValueError):
        engine.synthesize(
            "hello",
            tmp_path / "reference.wav",
            "en",
            output_path=tmp_path / "out.wav",
        )


def test_records_calls_in_order(tmp_path: Path) -> None:
    engine = FakeEngine()
    engine.load()
    reference = tmp_path / "reference.wav"

    engine.synthesize("一番", reference, "ja", output_path=tmp_path / "one.wav")
    engine.synthesize("二番", reference, "ja", output_path=tmp_path / "two.wav")

    assert engine.calls == [("一番", reference, "ja"), ("二番", reference, "ja")]


@pytest.mark.parametrize("detected", [True, False])
def test_watermark_detection_result_is_injectable(
    tmp_path: Path, detected: bool
) -> None:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"fixture")

    assert FakeEngine(detect_result=detected).detect_watermark(wav) is detected


def test_watermark_detection_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(EngineError) as error:
        FakeEngine().detect_watermark(tmp_path / "missing.wav")

    assert error.value.code is ErrorCode.ERR_INTERNAL


def test_has_no_watermark_disable_surface() -> None:
    forbidden = {
        "disable_watermark",
        "no_watermark",
        "skip_watermark",
        "watermark_enabled",
    }
    parameters = set(inspect.signature(FakeEngine.synthesize).parameters)

    assert forbidden.isdisjoint(parameters)
    assert forbidden.isdisjoint(dir(FakeEngine))
