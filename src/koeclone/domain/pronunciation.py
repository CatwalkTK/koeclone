from dataclasses import dataclass
from itertools import pairwise

from koeclone.errors import ErrorCode


@dataclass(frozen=True)
class PronunciationOverride:
    surface: str
    start: int
    end: int
    reading: str


def validate_pronunciation_overrides(
    text: str,
    overrides: list[PronunciationOverride],
) -> ErrorCode | None:
    for override in overrides:
        if not override.reading or not override.reading.strip():
            return ErrorCode.ERR_READING_EMPTY
        if not all(_is_reading_character(char) for char in override.reading):
            return ErrorCode.ERR_READING_INVALID_CHARS
        if not 0 <= override.start < override.end <= len(text):
            return ErrorCode.ERR_OVERRIDE_RANGE_INVALID
        if text[override.start : override.end] != override.surface:
            return ErrorCode.ERR_OVERRIDE_SURFACE_MISMATCH
        if not any(_is_kanji(char) for char in override.surface):
            return ErrorCode.ERR_OVERRIDE_NO_KANJI

    ordered = sorted(overrides, key=lambda item: item.start)
    if any(left.end > right.start for left, right in pairwise(ordered)):
        return ErrorCode.ERR_OVERRIDE_OVERLAP
    return None


def _is_reading_character(character: str) -> bool:
    return (
        character.isspace()
        or "\u3040" <= character <= "\u309f"
        or "\u30a0" <= character <= "\u30ff"
        or "\u31f0" <= character <= "\u31ff"
    )


def _is_kanji(character: str) -> bool:
    return (
        "\u3400" <= character <= "\u4dbf"
        or "\u4e00" <= character <= "\u9fff"
        or "\uf900" <= character <= "\ufaff"
        or "\U00020000" <= character <= "\U0002fa1f"
        or "\U00030000" <= character <= "\U000323af"
        or character == "々"
    )
