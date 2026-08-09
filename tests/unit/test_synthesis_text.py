from koeclone.domain.pronunciation import PronunciationOverride
from koeclone.domain.synthesis_text import (
    build_synthesis_text,
    split_synthesis_text,
)
from koeclone.errors import ErrorCode


def test_applies_partial_reading_without_changing_original() -> None:
    original = "明日は日本橋へ行きます"
    override = PronunciationOverride("日本橋", 3, 6, "にほんばし")

    synthesis_text, error = build_synthesis_text(original, [override])

    assert error is None
    assert synthesis_text == "明日はにほんばしへ行きます"
    assert original == "明日は日本橋へ行きます"


def test_applies_multiple_overrides_from_the_end() -> None:
    original = "東京と日本橋"
    overrides = [
        PronunciationOverride("東京", 0, 2, "とうきょう"),
        PronunciationOverride("日本橋", 3, 6, "にほんばし"),
    ]

    synthesis_text, error = build_synthesis_text(original, overrides)

    assert error is None
    assert synthesis_text == "とうきょうとにほんばし"


def test_rejects_synthesis_text_over_limit() -> None:
    override = PronunciationOverride("漢", 0, 1, "あ" * 2_001)

    synthesis_text, error = build_synthesis_text("漢", [override])

    assert synthesis_text is None
    assert error is ErrorCode.ERR_SYNTHESIS_TEXT_TOO_LONG


def test_accepts_synthesis_text_at_limit() -> None:
    override = PronunciationOverride("漢", 0, 1, "あ" * 2_000)

    synthesis_text, error = build_synthesis_text("漢", [override])

    assert error is None
    assert synthesis_text == "あ" * 2_000


def test_splits_at_punctuation_and_preserves_order() -> None:
    text = "第一。第二！第三？第四、第五。"

    chunks = split_synthesis_text(text)

    assert chunks == ["第一。", "第二！", "第三？", "第四、", "第五。"]
    assert "".join(chunks) == text


def test_normal_mode_passes_original_text_through() -> None:
    original = "通常モードの文章です。"

    synthesis_text, error = build_synthesis_text(original, [])

    assert error is None
    assert synthesis_text == original
