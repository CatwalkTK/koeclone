import pytest

from koeclone.domain.pronunciation import (
    PronunciationOverride,
    validate_pronunciation_overrides,
)
from koeclone.errors import ErrorCode


def test_accepts_japanese_pronunciation_override() -> None:
    text = "明日は日本橋へ行きます"
    override = PronunciationOverride("日本橋", 3, 6, "にほんばし")

    assert validate_pronunciation_overrides(text, [override]) is None


@pytest.mark.parametrize(
    ("reading", "expected"),
    [
        ("", ErrorCode.ERR_READING_EMPTY),
        ("　 \t", ErrorCode.ERR_READING_EMPTY),
        ("日本ばし", ErrorCode.ERR_READING_INVALID_CHARS),
        ("にほんbashi", ErrorCode.ERR_READING_INVALID_CHARS),
        ("にほん、ばし", ErrorCode.ERR_READING_INVALID_CHARS),
    ],
)
def test_rejects_invalid_reading(reading: str, expected: ErrorCode) -> None:
    override = PronunciationOverride("日本橋", 3, 6, reading)

    assert validate_pronunciation_overrides(
        "明日は日本橋へ行きます", [override]
    ) is expected


def test_accepts_supported_reading_characters() -> None:
    override = PronunciationOverride("東京", 0, 2, "とうきょう・トーキョー　")

    assert validate_pronunciation_overrides("東京", [override]) is None


def test_accepts_cjk_extension_kanji_surface() -> None:
    extension_b_kanji = "\U0002000b"
    override = PronunciationOverride(extension_b_kanji, 0, 1, "よし")

    assert validate_pronunciation_overrides(extension_b_kanji, [override]) is None


@pytest.mark.parametrize(
    ("start", "end"),
    [(-1, 2), (2, 2), (3, 2), (0, 4)],
)
def test_rejects_invalid_ranges(start: int, end: int) -> None:
    override = PronunciationOverride("東京", start, end, "とうきょう")

    assert (
        validate_pronunciation_overrides("東京", [override])
        is ErrorCode.ERR_OVERRIDE_RANGE_INVALID
    )


def test_rejects_surface_mismatch() -> None:
    override = PronunciationOverride("大阪", 0, 2, "おおさか")

    assert (
        validate_pronunciation_overrides("東京", [override])
        is ErrorCode.ERR_OVERRIDE_SURFACE_MISMATCH
    )


def test_rejects_surface_without_kanji() -> None:
    override = PronunciationOverride("あした", 0, 3, "あした")

    assert (
        validate_pronunciation_overrides("あした", [override])
        is ErrorCode.ERR_OVERRIDE_NO_KANJI
    )


def test_rejects_overlapping_ranges() -> None:
    overrides = [
        PronunciationOverride("日本橋", 3, 6, "にほんばし"),
        PronunciationOverride("橋へ", 5, 7, "はしへ"),
    ]

    assert (
        validate_pronunciation_overrides("明日は日本橋へ行きます", overrides)
        is ErrorCode.ERR_OVERRIDE_OVERLAP
    )


def test_allows_adjacent_ranges() -> None:
    overrides = [
        PronunciationOverride("東京", 0, 2, "とうきょう"),
        PronunciationOverride("日本橋", 2, 5, "にほんばし"),
    ]

    assert validate_pronunciation_overrides("東京日本橋", overrides) is None
