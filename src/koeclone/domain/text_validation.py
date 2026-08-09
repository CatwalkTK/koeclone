from koeclone.config import AppConfig
from koeclone.errors import ErrorCode


def validate_text(
    text: str,
    *,
    config: AppConfig | None = None,
) -> ErrorCode | None:
    settings = config or AppConfig()
    if not text:
        return ErrorCode.ERR_TEXT_EMPTY
    if len(text) > settings.max_text_length:
        return ErrorCode.ERR_TEXT_TOO_LONG
    if not text.strip():
        return ErrorCode.ERR_TEXT_WHITESPACE_ONLY
    return None
