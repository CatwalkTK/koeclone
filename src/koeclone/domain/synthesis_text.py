from koeclone.config import AppConfig
from koeclone.domain.pronunciation import PronunciationOverride
from koeclone.errors import ErrorCode

SENTENCE_BOUNDARIES = frozenset("。、！？.!?，,")
TARGET_MIN_CHARS = 60
TARGET_MAX_CHARS = 120


def build_synthesis_text(
    original: str,
    overrides: list[PronunciationOverride],
    *,
    config: AppConfig | None = None,
) -> tuple[str | None, ErrorCode | None]:
    result = original
    for override in sorted(overrides, key=lambda item: item.start, reverse=True):
        result = result[: override.start] + override.reading + result[override.end :]

    settings = config or AppConfig()
    if len(result) > settings.max_synthesis_text_length:
        return None, ErrorCode.ERR_SYNTHESIS_TEXT_TOO_LONG
    return result, None


def split_synthesis_text(text: str) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    for character in text:
        current.append(character)
        if character in SENTENCE_BOUNDARIES:
            chunks.append("".join(current))
            current.clear()
    if current:
        chunks.append("".join(current))
    return chunks


def plan_synthesis_chunks(
    text: str,
    *,
    target_min: int = TARGET_MIN_CHARS,
    target_max: int = TARGET_MAX_CHARS,
) -> list[str]:
    if target_min <= 0 or target_max < target_min:
        raise ValueError("Invalid synthesis chunk bounds")

    planned: list[str] = []
    buffer = ""
    for fragment in split_synthesis_text(text):
        if not buffer:
            buffer = fragment
            continue
        if len(buffer) + len(fragment) > target_max:
            planned.append(buffer)
            buffer = fragment
            continue
        buffer += fragment
        if len(buffer) >= target_min:
            planned.append(buffer)
            buffer = ""
    if buffer:
        planned.append(buffer)
    return planned
