from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_DEVICES = ("cpu", "mps")
REQUIRED_RESULT_KEYS = {
    "text",
    "elapsed_seconds",
    "audio_duration_seconds",
    "rtf",
    "peak_memory_mb",
    "output_path",
    "watermark_detected",
}


@dataclass(frozen=True)
class MeasurementResult:
    text: str
    elapsed_seconds: float
    audio_duration_seconds: float
    rtf: float
    peak_memory_mb: float
    output_path: Path
    watermark_detected: bool

    def to_dict(self) -> dict[str, str | float | bool]:
        return {
            "text": self.text,
            "elapsed_seconds": self.elapsed_seconds,
            "audio_duration_seconds": self.audio_duration_seconds,
            "rtf": self.rtf,
            "peak_memory_mb": self.peak_memory_mb,
            "output_path": str(self.output_path),
            "watermark_detected": self.watermark_detected,
        }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark Chatterbox Multilingual V3 voice cloning."
    )
    parser.add_argument(
        "--device",
        choices=SUPPORTED_DEVICES,
        default="mps",
        help="Inference device (default: mps).",
    )
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--texts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def current_peak_memory_mb() -> float:
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return peak_rss / divisor


def run_measurements(
    texts: Sequence[str],
    *,
    output_dir: Path,
    synthesize: Callable[[str, Path], tuple[float, bool]],
    clock: Callable[[], float] = time.perf_counter,
    peak_memory_mb: Callable[[], float] = current_peak_memory_mb,
) -> list[MeasurementResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[MeasurementResult] = []

    for index, text in enumerate(texts, start=1):
        output_path = output_dir / f"sample_{index:02d}.wav"
        started_at = clock()
        audio_duration_seconds, watermark_detected = synthesize(text, output_path)
        elapsed_seconds = clock() - started_at
        if audio_duration_seconds <= 0:
            raise ValueError("Synthesized audio duration must be positive.")

        results.append(
            MeasurementResult(
                text=text,
                elapsed_seconds=elapsed_seconds,
                audio_duration_seconds=audio_duration_seconds,
                rtf=elapsed_seconds / audio_duration_seconds,
                peak_memory_mb=peak_memory_mb(),
                output_path=output_path,
                watermark_detected=watermark_detected,
            )
        )

    return results


def load_texts(path: Path) -> list[str]:
    texts = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not texts:
        raise ValueError(f"No evaluation text found in {path}")
    return texts


def build_synthesizer(
    *, device: str, reference_path: Path
) -> Callable[[str, Path], tuple[float, bool]]:
    import torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    from perth import PerthImplicitWatermarker

    model = ChatterboxMultilingualTTS.from_pretrained(
        device=device,
        t3_model="v3",
    )
    watermarker = PerthImplicitWatermarker()

    def synthesize(text: str, output_path: Path) -> tuple[float, bool]:
        if device == "mps":
            import torch

            torch.mps.synchronize()

        waveform = model.generate(
            text,
            language_id="ja",
            audio_prompt_path=str(reference_path),
        )

        if device == "mps":
            import torch

            torch.mps.synchronize()

        waveform = waveform.detach().cpu()
        torchaudio.save(str(output_path), waveform, model.sr)
        audio_duration_seconds = waveform.shape[-1] / model.sr
        detected = watermarker.get_watermark(
            waveform.squeeze(0).numpy(),
            sample_rate=model.sr,
        )
        return audio_duration_seconds, bool(detected)

    return synthesize


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.reference.is_file():
        raise SystemExit(f"Reference audio not found: {args.reference}")
    if not args.texts.is_file():
        raise SystemExit(f"Evaluation text file not found: {args.texts}")

    texts = load_texts(args.texts)
    synthesizer = build_synthesizer(
        device=args.device,
        reference_path=args.reference,
    )
    results = run_measurements(
        texts,
        output_dir=args.output,
        synthesize=synthesizer,
    )

    result_path = args.output / f"results-{args.device}.json"
    payload = {
        "device": args.device,
        "reference_path": str(args.reference),
        "model": "Chatterbox Multilingual V3",
        "results": [result.to_dict() for result in results],
    }
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(result_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
