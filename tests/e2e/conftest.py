from __future__ import annotations

import math
import os
import socket
import struct
import subprocess
import time
import urllib.request
import wave
from collections.abc import Iterator
from pathlib import Path

import pytest

from koeclone.media.ffmpeg import _run, resolve_ffmpeg_paths


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """E2Eを常に最後に実行する。

    pytest-playwright はセッション全体でイベントループを保持するため、E2Eが先に
    走ると `tests/integration/test_app.py` の `asyncio.run()` が
    「cannot be called from a running event loop」で失敗する。既存テストを
    変更せずに解消するため、収集順で分離する（安定ソートなので相対順序は保つ）。
    """
    items.sort(key=lambda item: "/tests/e2e/" in str(item.path))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def live_url(tmp_path: Path) -> Iterator[str]:
    port = _free_port()
    environment = {
        **os.environ,
        "KOECLONE_ENGINE": "fake",
        "KOECLONE_DATA_DIR": str(tmp_path / "data"),
        "KOECLONE_PORT": str(port),
    }
    process = subprocess.Popen(
        [str(Path.cwd() / "scripts" / "run.sh")],
        cwd=Path.cwd(),
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                with urllib.request.urlopen(f"{url}/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("E2E server did not start")
                process.poll()
                if process.returncode is not None:
                    raise RuntimeError("E2E server exited during startup")
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture(scope="session")
def audio_files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    directory = tmp_path_factory.mktemp("generated-audio")
    wav = directory / "voice.wav"
    silent = directory / "silent.wav"
    _write_wav(wav, silent_audio=False)
    _write_wav(silent, silent_audio=True)
    mp3 = directory / "voice.mp3"
    paths = resolve_ffmpeg_paths()
    _run(
        paths,
        [
            str(paths.ffmpeg),
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-i",
            str(wav),
            str(mp3),
        ],
    )
    return {"wav": wav, "mp3": mp3, "silent": silent}


def _write_wav(path: Path, *, silent_audio: bool) -> None:
    sample_rate = 24_000
    frames = [
        0
        if silent_audio
        else round(8_000 * math.sin(2 * math.pi * 440 * index / sample_rate))
        for index in range(12 * sample_rate)
    ]
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(struct.pack(f"<{len(frames)}h", *frames))


@pytest.fixture(scope="session")
def browser_type_launch_args(
    browser_type_launch_args: dict[str, object],
    audio_files: dict[str, Path],
):
    return {
        **browser_type_launch_args,
        "args": [
            "--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream",
            f"--use-file-for-fake-audio-capture={audio_files['wav']}",
            "--autoplay-policy=no-user-gesture-required",
        ],
    }
