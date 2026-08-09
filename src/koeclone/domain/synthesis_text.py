from koeclone.config import AppConfig
from koeclone.domain.pronunciation import PronunciationOverride
from koeclone.errors import ErrorCode

SENTENCE_BOUNDARIES = frozenset("。、！？.!?，,")


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
