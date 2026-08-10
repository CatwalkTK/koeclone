from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    host: str = field(default="127.0.0.1", init=False)
    port: int = 8000
    data_dir: Path = field(default_factory=lambda: Path.home() / "koeclone-data")
    device: str = "mps"
    allow_cpu_fallback: bool = False
    engine: str = "chatterbox"
    app_version: str = "0.1.0"

    silence_window_ms: int = 20
    silence_rms_dbfs: float = -50.0
    max_silence_ratio: float = 0.80
    peak_limit_dbfs: float = -1.0
    absolute_sample_limit: float = 0.999
    min_rms_dbfs: float = -35.0
    max_rms_dbfs: float = -10.0

    direct_recording_seconds: tuple[float, float] = (10.0, 60.0)
    upload_seconds: tuple[float, float] = (10.0, 180.0)
    max_upload_bytes: int = 50 * 1024 * 1024
    max_text_length: int = 1_000
    max_synthesis_text_length: int = 2_000

    @classmethod
    def from_env(cls) -> AppConfig:
        data_dir = Path(
            os.environ.get("KOECLONE_DATA_DIR", Path.home() / "koeclone-data")
        ).expanduser()
        port = int(os.environ.get("KOECLONE_PORT", "8000"))
        allow_cpu_fallback = os.environ.get(
            "KOECLONE_ALLOW_CPU_FALLBACK", "false"
        ).casefold() in {"1", "true", "yes", "on"}
        engine = os.environ.get("KOECLONE_ENGINE", "chatterbox")
        if engine not in {"chatterbox", "fake"}:
            raise ValueError("KOECLONE_ENGINE must be chatterbox or fake")
        return cls(
            port=port,
            data_dir=data_dir,
            allow_cpu_fallback=allow_cpu_fallback,
            engine=engine,
        )
