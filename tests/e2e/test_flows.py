from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page, expect


def _open(page: Page, live_url: str) -> None:
    page.goto(live_url)
    expect(
        page.get_by_role("heading", name="あなたの声を、安全に扱うために")
    ).to_be_visible()


def _accept(page: Page) -> None:
    page.get_by_label("登録するのは自分の声であり").check()
    page.get_by_role("button", name="同意して声を登録する").click()


def _register_upload(page: Page, live_url: str, path: Path) -> None:
    _open(page, live_url)
    _accept(page)
    page.get_by_role("tab", name="ファイル").click()
    page.locator("#voice-file").set_input_files(path)
    page.get_by_label("この音声は自分の声で").check()
    page.get_by_role("button", name="音声を確認する").click()
    expect(page.locator("#upload-playback")).to_be_visible()
    page.get_by_label("試聴した音声を自分の声として登録します").check()
    page.locator("#upload-confirm").click()
    expect(page.locator("#synthesis-player")).to_be_visible(timeout=10_000)


def _await_generation(page: Page) -> str:
    """生成を実行し、**今回作成されたジョブ**のIDを返す。

    進行表示の文言は前ジョブ（登録時のテスト音声）の「音声が完成しました」が
    残るため、完成判定には使えない。今回のジョブIDでプレイヤーが配線される
    ことを完成条件とする。
    """
    page.get_by_label("AI生成音声として利用することを確認しました").check()
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/syntheses")
            and response.request.method == "POST"
        )
    ) as created:
        page.locator("#synthesize").click()
    job_id = str(created.value.json()["id"])
    expect(page.locator("#synthesis-player")).to_have_attribute(
        "src", f"/api/syntheses/{job_id}/audio", timeout=10_000
    )
    expect(page.locator("#synthesis-progress")).to_have_text("音声が完成しました")
    return job_id


def _generate(page: Page, text: str) -> str:
    page.locator("#synthesis-text").fill(text)
    return _await_generation(page)


def test_consent_unlocks_recording_and_upload(page: Page, live_url: str) -> None:
    _open(page, live_url)
    expect(page.locator("#record-start")).to_be_disabled()
    expect(page.locator("#voice-file")).to_be_disabled()
    page.get_by_label("登録するのは自分の声であり").check()
    expect(page.locator("#record-start")).to_be_enabled()
    expect(page.locator("#voice-file")).to_be_enabled()


def test_direct_recording_registers_and_plays_test_voice(
    page: Page, live_url: str
) -> None:
    _open(page, live_url)
    _accept(page)
    # 都度生成された同意文が実際に取得できていること（FR-003）。
    # placeholder / 取得失敗メッセージでは満たせない条件にする。
    expect(page.locator("#consent-challenge")).to_have_text(
        re.compile(r"確認語は「.+」、確認番号は\d{8}です。$")
    )
    page.locator("#record-start").click()
    expect(page.locator("#record-time")).to_have_text("00:10", timeout=15_000)
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/voices") and response.request.method == "POST"
        )
    ) as validation:
        page.locator("#record-stop").click()
    assert validation.value.status == 200, validation.value.json()
    expect(page.locator("#record-playback")).to_be_visible(timeout=10_000)
    page.locator("#record-confirm").click()
    expect(page.locator("#synthesis-player")).to_be_visible(timeout=10_000)


def test_wav_upload_requires_two_confirmations(
    page: Page, live_url: str, audio_files: dict[str, Path]
) -> None:
    _register_upload(page, live_url, audio_files["wav"])


def test_mp3_upload_requires_two_confirmations(
    page: Page, live_url: str, audio_files: dict[str, Path]
) -> None:
    _register_upload(page, live_url, audio_files["mp3"])


def test_silent_upload_shows_reselection_guidance(
    page: Page, live_url: str, audio_files: dict[str, Path]
) -> None:
    _open(page, live_url)
    _accept(page)
    page.get_by_role("tab", name="ファイル").click()
    page.locator("#voice-file").set_input_files(audio_files["silent"])
    page.get_by_label("この音声は自分の声で").check()
    page.locator("#upload-validate").click()
    expect(page.locator("#upload-error")).to_contain_text("別のファイルを選んで")
    expect(page.locator("#upload-discard")).to_be_visible()


def test_normal_generation_plays_and_downloads(
    page: Page, live_url: str, audio_files: dict[str, Path]
) -> None:
    _register_upload(page, live_url, audio_files["wav"])
    job_id = _generate(page, "通常モードで音声を生成します。")
    expect(page.locator("#synthesis-player")).to_be_visible()
    expect(page.locator("#synthesis-download")).to_be_visible()
    # ダウンロード先が今回のジョブであること（前ジョブのURLが残っていないこと）
    expect(page.locator("#synthesis-download")).to_have_attribute(
        "href", f"/api/syntheses/{job_id}/audio"
    )
    audio = page.request.get(f"{live_url}/api/syntheses/{job_id}/audio")
    assert audio.status == 200, audio.text()
    assert audio.headers["content-type"] == "audio/wav"
    # ファイル名はサーバーの Content-Disposition に従う（FR-209）
    assert audio.headers["content-disposition"].startswith("attachment;")
    body = audio.body()
    assert body[:4] == b"RIFF" and body[8:12] == b"WAVE"
    job = page.request.get(f"{live_url}/api/syntheses/{job_id}").json()
    assert job["watermark_detected"] is True, job  # AC-08 / S-10
    assert job["override_count"] == 0, job  # 通常モードは読み修正を送らない（FR-218）


def test_pronunciation_preview_and_generation_keep_original_text(
    page: Page, live_url: str, audio_files: dict[str, Path]
) -> None:
    _register_upload(page, live_url, audio_files["wav"])
    text = "明日は日本橋へ行きます"
    page.locator("#synthesis-text").fill(text)
    expect(page.locator("#original-count")).to_have_text("11")
    page.get_by_role("tab", name="読み修正モード").click()
    page.locator("#synthesis-text").evaluate(
        "(node) => { node.setSelectionRange(3, 6); node.dispatchEvent(new Event('select')); }"
    )
    expect(page.locator("#selected-surface")).to_have_value("日本橋")
    page.locator("#override-reading").fill("にほんばし")
    page.locator("#override-add").click()
    page.locator("#preview-synthesis").click()
    # AC-06: 合成用テキスト全体が「明日はにほんばしへ行きます」になること
    expect(page.locator("#preview-reading")).to_have_text(
        "読み上げ: 明日はにほんばしへ行きます"
    )
    # 修正部分だけが強調されること（FR-215）
    expect(page.locator("#preview-original mark")).to_have_text("日本橋")
    expect(page.locator("#synthesis-count")).to_have_text("13")
    # 契約 §2.13 シナリオ7: プレビュー確認のあと生成まで通す
    job_id = _await_generation(page)
    expect(page.locator("#synthesis-text")).to_have_value(text)
    job = page.request.get(f"{live_url}/api/syntheses/{job_id}").json()
    assert job["override_count"] == 1, job
    # 保存された原文が置換されていないこと（AC-06「原文は変更されず」）
    assert job["text_preview"] == text, job


def test_ai_disclosure_is_required(
    page: Page, live_url: str, audio_files: dict[str, Path]
) -> None:
    _register_upload(page, live_url, audio_files["wav"])
    page.locator("#synthesis-text").fill("確認が必要です。")
    expect(page.locator("#synthesize")).to_be_disabled()
    page.locator("#ai-disclosure").check()
    expect(page.locator("#synthesize")).to_be_enabled()


def test_history_individual_and_all_delete(
    page: Page, live_url: str, audio_files: dict[str, Path]
) -> None:
    _register_upload(page, live_url, audio_files["wav"])
    _generate(page, "履歴から削除します。")
    page.get_by_role("button", name="履歴").click()
    expect(page.locator(".history-item")).to_have_count(2)
    page.locator(".history-item").first.get_by_role("button", name="削除").click()
    expect(page.locator(".history-item")).to_have_count(1)
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#history-delete-all").click()
    expect(page.locator(".history-item")).to_have_count(0)


def test_profile_delete_removes_history_and_audio(
    page: Page, live_url: str, audio_files: dict[str, Path]
) -> None:
    _register_upload(page, live_url, audio_files["wav"])
    job_id = _generate(page, "完全削除する音声です。")
    page.get_by_role("button", name="履歴").click()
    expect(page.locator(".history-item")).to_have_count(2)
    assert page.request.get(f"{live_url}/api/voices/current").status == 200
    # UI にプロフィール削除の操作要素が存在しないため、AC-09 の削除確定は API で行う。
    # UI導線の欠落はゲートレビューの申し送り（T-314）として記録済み。
    assert page.request.delete(f"{live_url}/api/voices/current").status == 204
    assert page.request.get(f"{live_url}/api/voices/current").status == 404
    assert page.request.get(f"{live_url}/api/syntheses/{job_id}").status == 404
    assert page.request.get(f"{live_url}/api/syntheses/{job_id}/audio").status == 404
    # 画面からも関連生成物が消えていること
    page.reload()
    page.get_by_role("button", name="履歴").click()
    expect(page.locator(".history-item")).to_have_count(0)
    expect(page.locator("#history-list .empty")).to_be_visible()
