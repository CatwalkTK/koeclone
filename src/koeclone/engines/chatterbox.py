from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from koeclone.config import AppConfig
from koeclone.engines.base import EngineError
from koeclone.errors import ErrorCode

ENGINE_NAME = "chatterbox-multilingual-v3"
EXPECTED_MODEL_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
MODEL_REPO_ID = "ResembleAI/chatterbox"
SUPPORTED_LANGUAGE = "ja"
MODEL_T3_FILENAME = "t3_mtl23ls_v3.safetensors"
MODEL_ALLOW_PATTERNS = (
    "ve.pt",
    MODEL_T3_FILENAME,
    "s3gen.pt",
    "grapheme_mtl_merged_expanded_v1.json",
    "conds.pt",
)

logger = logging.getLogger(__name__)


@dataclass
class ChatterboxEngine:
    device: str = "mps"
    allow_cpu_fallback: bool = False
    engine_name: str = ENGINE_NAME
    model_version: str = EXPECTED_MODEL_REVISION
    active_device: str | None = None
    fallback_reason: str | None = None
    _model: Any | None = field(default=None, init=False, repr=False)
    _watermarker: Any | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_config(cls, config: AppConfig) -> ChatterboxEngine:
        return cls(
            device=config.device,
            allow_cpu_fallback=config.allow_cpu_fallback,
        )

    def load(self) -> None:
        if self._model is not None:
            return
        if self.device not in {"mps", "cpu"}:
            raise ValueError("device must be mps or cpu")

        import torch

        snapshot = _resolve_local_snapshot()
        target = self.device
        if target == "mps" and not torch.backends.mps.is_available():
            if not self.allow_cpu_fallback:
                raise EngineError(ErrorCode.ERR_INTERNAL)
            target = "cpu"
            self.fallback_reason = "mps_unavailable"
            logger.warning("MPS unavailable; using CPU fallback")

        try:
            model = _load_local_model(snapshot, target)
        except Exception as error:
            if target != "mps" or not self.allow_cpu_fallback:
                raise EngineError(ErrorCode.ERR_INTERNAL) from error
            self.fallback_reason = "mps_initialization_failed"
            logger.warning("MPS model initialization failed; using CPU fallback")
            try:
                model = _load_local_model(snapshot, "cpu")
            except Exception as fallback_error:
                raise EngineError(ErrorCode.ERR_INTERNAL) from fallback_error
            target = "cpu"

        self._model = model
        self.active_device = target

    def synthesize(
        self,
        text: str,
        reference_wav: Path,
        language: str,
        *,
        output_path: Path,
    ) -> Path:
        if language != SUPPORTED_LANGUAGE:
            raise ValueError("Only Japanese synthesis is supported")
        if self._model is None:
            raise EngineError(ErrorCode.ERR_INTERNAL)

        import torchaudio

        try:
            waveform = self._model.generate(
                text,
                language_id=SUPPORTED_LANGUAGE,
                audio_prompt_path=str(reference_wav),
            )
            waveform = waveform.detach().cpu()
            if waveform.ndim == 1:
                waveform = waveform.unsqueeze(0)
            elif waveform.shape[0] != 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            torchaudio.save(
                str(output_path),
                waveform,
                self._model.sr,
                encoding="PCM_S",
                bits_per_sample=16,
            )
        except Exception as error:
            raise EngineError(ErrorCode.ERR_INTERNAL) from error
        return output_path

    def detect_watermark(self, wav: Path) -> bool:
        import perth
        import torchaudio

        try:
            waveform, sample_rate = torchaudio.load(str(wav))
            if waveform.shape[0] != 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            audio = waveform.squeeze(0).detach().cpu().numpy()
            if self._watermarker is None:
                self._watermarker = perth.PerthImplicitWatermarker()
            score = self._watermarker.get_watermark(
                audio,
                sample_rate=sample_rate,
            )
        except Exception as error:
            raise EngineError(ErrorCode.ERR_INTERNAL) from error
        return bool(score >= 0.5)


def _resolve_local_snapshot() -> Path:
    from huggingface_hub import snapshot_download

    try:
        snapshot = snapshot_download(
            repo_id=MODEL_REPO_ID,
            revision=EXPECTED_MODEL_REVISION,
            local_files_only=True,
            allow_patterns=list(MODEL_ALLOW_PATTERNS),
        )
    except Exception as error:
        raise EngineError(ErrorCode.ERR_INTERNAL) from error
    resolved = Path(snapshot)
    if resolved.name != EXPECTED_MODEL_REVISION:
        raise EngineError(ErrorCode.ERR_INTERNAL)
    return resolved


def _load_local_model(snapshot: Path, device: str) -> Any:
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    return ChatterboxMultilingualTTS.from_local(
        snapshot,
        device,
        t3_model="v3",
    )
