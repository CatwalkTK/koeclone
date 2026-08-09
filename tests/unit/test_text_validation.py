import pytest

from koeclone.domain.text_validation import validate_text
from koeclone.errors import ErrorCode


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ErrorCode.ERR_TEXT_EMPTY),
        ("あ" * 1_001, ErrorCode.ERR_TEXT_TOO_LONG),
        (" \t\n　", ErrorCode.ERR_TEXT_WHITESPACE_ONLY),
    ],
)
def test_rejects_invalid_text(text: str, expected: ErrorCode) -> None:
    assert validate_text(text) is expected


@pytest.mark.parametrize("text", ["あ", "あ" * 1_000])
def test_accepts_length_boundaries(text: str) -> None:
    assert validate_text(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "制御文字\x00を文字列として保持する",
        '<script>alert("実行しない")</script>',
    ],
)
def test_treats_control_characters_and_html_as_plain_text(text: str) -> None:
    original = text

    assert validate_text(text) is None
    assert text == original
