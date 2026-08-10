from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import pytest

import koeclone.engines.chatterbox as chatterbox_module
from koeclone.config import AppConfig
from koeclone.engines.base import EngineError, SpeechEngine
from koeclone.engines.chatterbox import (
    ENGINE_NAME,
    EXPECTED_MODEL_REVISION,
    ChatterboxEngine,
)
from koeclone.errors import ErrorCode

REAL_MODEL_ENV = "KOECLONE_REAL_MODEL"

real_model = pytest.mark.skipif(
    os.environ.get(REAL_MODEL_ENV) != "1",
    reason="実モデル契約テストは KOECLONE_REAL_MODEL=1 の環境でのみ実行する",
)


def test_implements_speech_engine_without_loading_model() -> None:
    assert isinstance(ChatterboxEngine(), SpeechEngine)
    assert "chatterbox.mtl_tts" not in sys.modules


def test_identifies_pinned_multilingual_v3() -> None:
    engine = ChatterboxEngine()

    assert engine.engine_name == ENGINE_NAME == "chatterbox-multilingual-v3"
    assert engine.model_version == EXPECTED_MODEL_REVISION


def test_no_watermark_disable_surface() -> None:
    forbidden = {
        "disable_watermark",
        "no_watermark",
        "skip_watermark",
        "watermark_enabled",
    }
    public_names = {name for name in dir(ChatterboxEngine) if not name.startswith("_")}
    parameter_names: set[str] = set()
    for method_name in ("load", "synthesize", "detect_watermark"):
        parameter_names.update(
            inspect.signature(getattr(ChatterboxEngine, method_name)).parameters
        )

    assert forbidden.isdisjoint(public_names)
    assert forbidden.isdisjoint(parameter_names)


def test_source_has_lazy_model_imports_and_no_disable_surface() -> None:
    source = inspect.getsource(chatterbox_module)

    assert "import librosa" not in source
    assert all(
        value not in source
        for value in (
            "disable_watermark",
            "no_watermark",
            "skip_watermark",
            "watermark_enabled",
        )
    )
    tree_prefix = source.split("class ChatterboxEngine", maxsplit=1)[0]
    assert "import torch" not in tree_prefix
    assert "import torchaudio" not in tree_prefix
    assert "import perth" not in tree_prefix
    assert "from chatterbox" not in tree_prefix


def test_synthesize_before_load_maps_to_internal(tmp_path: Path) -> None:
    engine = ChatterboxEngine()

    with pytest.raises(EngineError) as captured:
        engine.synthesize(
            "こんにちは",
            tmp_path / "reference.wav",
            "ja",
            output_path=tmp_path / "output.wav",
        )

    assert captured.value.code is ErrorCode.ERR_INTERNAL


def test_unsupported_language_is_rejected_before_load(tmp_path: Path) -> None:
    engine = ChatterboxEngine()

    with pytest.raises(ValueError):
        engine.synthesize(
            "hello",
            tmp_path / "reference.wav",
            "en",
            output_path=tmp_path / "output.wav",
        )


def test_from_config_copies_device_policy() -> None:
    config = AppConfig(device="mps", allow_cpu_fallback=False)

    engine = ChatterboxEngine.from_config(config)

    assert engine.device == "mps"
    assert engine.allow_cpu_fallback is False


def test_snapshot_resolution_requests_only_required_model_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / EXPECTED_MODEL_REVISION
    snapshot.mkdir()
    captured: dict[str, object] = {}

    def fake_snapshot_download(**kwargs: object) -> str:
        captured.update(kwargs)
        return str(snapshot)

    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)

    assert chatterbox_module._resolve_local_snapshot() == snapshot
    assert captured["revision"] == EXPECTED_MODEL_REVISION
    assert captured["local_files_only"] is True
    assert captured["allow_patterns"] == list(chatterbox_module.MODEL_ALLOW_PATTERNS)


def _reference_wav() -> Path:
    configured = os.environ.get("KOECLONE_REFERENCE_WAV")
    path = Path(configured) if configured else Path("tmp/reference_kyoko.wav")
    if not path.is_file():
        pytest.skip("実モデルテスト用の合成参照WAVがない")
    return path


@pytest.fixture(scope="module")
def loaded_engine() -> ChatterboxEngine:
    engine = ChatterboxEngine(device="mps", allow_cpu_fallback=True)
    engine.load()
    return engine


@pytest.fixture(scope="module")
def synthesized_wav(
    loaded_engine: ChatterboxEngine,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    destination = tmp_path_factory.mktemp("chatterbox") / "sample.wav"
    return loaded_engine.synthesize(
        "これは音声クローンの動作確認です。",
        _reference_wav(),
        "ja",
        output_path=destination,
    )


@pytest.mark.real_model
@real_model
def test_load_is_idempotent(loaded_engine: ChatterboxEngine) -> None:
    model = loaded_engine._model

    loaded_engine.load()

    assert loaded_engine._model is model
    assert loaded_engine.active_device in {"mps", "cpu"}


@pytest.mark.real_model
@real_model
def test_revision_mismatch_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chatterbox_module, "EXPECTED_MODEL_REVISION", "0" * 40)
    engine = ChatterboxEngine(device="cpu")

    with pytest.raises(EngineError) as captured:
        engine.load()

    assert captured.value.code is ErrorCode.ERR_INTERNAL


@pytest.mark.real_model
@real_model
def test_synthesizes_mono_24khz_wav(synthesized_wav: Path) -> None:
    import wave

    with wave.open(str(synthesized_wav), "rb") as output:
        assert output.getnchannels() == 1
        assert output.getframerate() == 24_000
        assert output.getsampwidth() == 2
        assert output.getnframes() > 0


@pytest.mark.real_model
@real_model
def test_generated_wav_has_watermark(
    loaded_engine: ChatterboxEngine,
    synthesized_wav: Path,
) -> None:
    assert loaded_engine.detect_watermark(synthesized_wav) is True


@pytest.mark.real_model
@real_model
def test_mps_unavailable_without_fallback_is_rejected() -> None:
    import torch

    if torch.backends.mps.is_available():
        pytest.skip("基準MacではMPSが利用可能")

    engine = ChatterboxEngine(device="mps", allow_cpu_fallback=False)
    with pytest.raises(EngineError):
        engine.load()


@pytest.mark.real_model
@real_model
def test_real_model_run_is_explicitly_offline() -> None:
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
