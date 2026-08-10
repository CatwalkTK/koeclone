from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass, field
from pathlib import Path

from koeclone.engines.base import EngineError
from koeclone.errors import ErrorCode


@dataclass
class FakeEngine:
    engine_name: str = "fake"
    model_version: str = "fake-1"
    sample_rate: int = 24_000
    detect_result: bool = True
    load_count: int = 0
    calls: list[tuple[str, Path, str]] = field(default_factory=list)

    def load(self) -> None:
        self.load_count += 1

    def synthesize(
        self,
        text: str,
        reference_wav: Path,
        language: str,
        *,
        output_path: Path,
    ) -> Path:
        if self.load_count == 0:
            raise EngineError(ErrorCode.ERR_INTERNAL)
        if language != "ja":
            raise ValueError("FakeEngine supports Japanese only")

        self.calls.append((text, reference_wav, language))
        duration_seconds = min(5.0, max(0.2, len(text) * 0.1))
        _write_sine_wav(output_path, self.sample_rate, duration_seconds)
        return output_path

    def detect_watermark(self, wav: Path) -> bool:
        if not wav.is_file():
            raise EngineError(ErrorCode.ERR_INTERNAL)
        return self.detect_result


def _write_sine_wav(path: Path, sample_rate: int, duration_seconds: float) -> None:
    frame_count = round(sample_rate * duration_seconds)
    amplitude = round(32_767 * 10 ** (-10 / 20))
    frames = bytearray()
    for index in range(frame_count):
        sample = round(amplitude * math.sin(2 * math.pi * 220 * index / sample_rate))
        frames.extend(struct.pack("<h", sample))

    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(frames)
