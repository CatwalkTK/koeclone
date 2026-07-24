import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
poc_generate = importlib.import_module("scripts.poc_generate")
REQUIRED_RESULT_KEYS = poc_generate.REQUIRED_RESULT_KEYS
MeasurementResult = poc_generate.MeasurementResult
parse_args = poc_generate.parse_args
run_measurements = poc_generate.run_measurements


@pytest.mark.parametrize("device", ["cpu", "mps"])
def test_parse_args_accepts_supported_devices(device: str, tmp_path: Path) -> None:
    reference = tmp_path / "reference.wav"
    texts = tmp_path / "sentences.txt"
    output = tmp_path / "results"

    args = parse_args(
        [
            "--device",
            device,
            "--reference",
            str(reference),
            "--texts",
            str(texts),
            "--output",
            str(output),
        ]
    )

    assert args.device == device
    assert args.reference == reference
    assert args.texts == texts
    assert args.output == output


@pytest.mark.parametrize("device", ["cuda", ""])
def test_parse_args_rejects_unsupported_devices(
    device: str, tmp_path: Path
) -> None:
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--device",
                device,
                "--reference",
                str(tmp_path / "reference.wav"),
                "--texts",
                str(tmp_path / "sentences.txt"),
                "--output",
                str(tmp_path / "results"),
            ]
        )


@pytest.mark.parametrize(
    "arguments",
    [
        ["--texts", "sentences.txt", "--output", "results"],
        ["--reference", "reference.wav", "--output", "results"],
        ["--reference", "reference.wav", "--texts", "sentences.txt"],
    ],
)
def test_parse_args_requires_reference_texts_and_output(
    arguments: list[str],
) -> None:
    with pytest.raises(SystemExit):
        parse_args(arguments)


def test_measurement_result_contains_required_json_keys() -> None:
    result = MeasurementResult(
        text="テストです。",
        elapsed_seconds=1.25,
        audio_duration_seconds=2.5,
        rtf=0.5,
        peak_memory_mb=128.0,
        output_path=Path("output.wav"),
        watermark_detected=True,
    )

    assert REQUIRED_RESULT_KEYS <= result.to_dict().keys()


def test_run_measurements_returns_one_result_per_text(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_synthesizer(text: str, output_path: Path) -> tuple[float, bool]:
        calls.append(text)
        output_path.write_bytes(b"fake wav")
        return 2.0, True

    results = run_measurements(
        ["一つ目。", "二つ目。"],
        output_dir=tmp_path,
        synthesize=fake_synthesizer,
        clock=iter([10.0, 11.0, 20.0, 21.5]).__next__,
        peak_memory_mb=lambda: 256.0,
    )

    assert calls == ["一つ目。", "二つ目。"]
    assert len(results) == 2
    assert [result.rtf for result in results] == [0.5, 0.75]
    assert all(REQUIRED_RESULT_KEYS <= result.to_dict().keys() for result in results)
