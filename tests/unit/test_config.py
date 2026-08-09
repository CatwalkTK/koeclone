from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from koeclone.config import AppConfig
from koeclone.errors import ErrorCode


def test_host_is_fixed_to_loopback() -> None:
    config = AppConfig()

    assert config.host == "127.0.0.1"
    with pytest.raises(TypeError):
        AppConfig(host="0.0.0.0")  # type: ignore[call-arg]
    with pytest.raises(FrozenInstanceError):
        config.host = "0.0.0.0"  # type: ignore[misc]


def test_data_directory_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_dir = tmp_path / "private-data"
    monkeypatch.setenv("KOECLONE_DATA_DIR", str(data_dir))

    assert AppConfig.from_env().data_dir == data_dir


def test_default_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KOECLONE_DATA_DIR", raising=False)
    monkeypatch.delenv("KOECLONE_PORT", raising=False)
    monkeypatch.delenv("KOECLONE_ALLOW_CPU_FALLBACK", raising=False)

    config = AppConfig.from_env()

    assert config.data_dir == Path.home() / "koeclone-data"
    assert config.port == 8000
    assert config.device == "mps"
    assert config.allow_cpu_fallback is False
    assert config.direct_recording_seconds == (10.0, 60.0)
    assert config.upload_seconds == (10.0, 180.0)
    assert config.max_text_length == 1_000
    assert config.max_synthesis_text_length == 2_000


def test_environment_overrides_supported_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KOECLONE_PORT", "9000")
    monkeypatch.setenv("KOECLONE_ALLOW_CPU_FALLBACK", "true")

    config = AppConfig.from_env()

    assert config.port == 9000
    assert config.allow_cpu_fallback is True


def test_error_codes_are_unique_and_stable() -> None:
    values = [code.value for code in ErrorCode]

    assert len(ErrorCode.__members__) == len(values)
    assert len(values) == len(set(values))
    assert values
    assert all(value.startswith("ERR_") and value.isupper() for value in values)


def test_audio_quality_thresholds_match_g0_measurements() -> None:
    config = AppConfig()

    assert config.silence_window_ms == 20
    assert config.silence_rms_dbfs == -50.0
    assert config.max_silence_ratio == 0.80
    assert config.peak_limit_dbfs == -1.0
    assert config.absolute_sample_limit == 0.999
    assert config.min_rms_dbfs == -35.0
    assert config.max_rms_dbfs == -10.0
