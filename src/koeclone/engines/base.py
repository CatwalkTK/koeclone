from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from koeclone.errors import KoecloneError


class EngineError(KoecloneError):
    """音声エンジン層の失敗。"""


@runtime_checkable
class SpeechEngine(Protocol):
    engine_name: str
    model_version: str

    def load(self) -> None: ...

    def synthesize(
        self,
        text: str,
        reference_wav: Path,
        language: str,
        *,
        output_path: Path,
    ) -> Path: ...

    def detect_watermark(self, wav: Path) -> bool: ...
