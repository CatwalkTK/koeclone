# フェーズゲート判定記録

本書はフェーズゲートの**正式判定記録**である。判定はClaude（指揮官）のみが行い、
判定時点のコミットハッシュと再現可能な検証証跡を残す。

判定区分は「合格」「条件付き合格」「不合格（差戻し）」の3種。
`docs/implementation-plan.md` §7 のゲート定義を判定基準とする。

| ゲート | 対象フェーズ | 判定 | 判定日 | 判定時HEAD | 記録場所 |
|---|---|---|---|---|---|
| G-C0 | 環境準備 | 合格 | 2026-07-24 | `b743ebc` | `docs/implementation-plan.md` §7 |
| G0 | Phase 0 実機PoC | 合格 | 2026-07-24 | `d1b6a9c` | `docs/poc-results.md`、`docs/adr/0001-speech-engine.md` |
| G1 | Phase 1 ドメイン・ストレージ | 合格 | 2026-07-24 | `35d8310` | `docs/task-contract-phase2.md` 冒頭「前提ゲート」 |
| G2 | Phase 2 音声エンジン・ジョブ | **合格** | 2026-08-10 | `7fc2423` | 本書 §1 |
| G3 | Phase 3 API・UI・E2E | **条件付き合格** | 2026-08-12 | `f5be6e5` | 本書 §2 |
| G4 | リリース品質 | 未判定 | — | — | 判定時に本書へ追記 |

---

## 1. G2 判定（Phase 2: 音声エンジン・ジョブ実行）

| 項目 | 内容 |
|---|---|
| 判定 | **合格** |
| 判定日 | 2026-08-10 |
| 判定者 | Claude（指揮官） |
| 判定時HEAD | `7fc2423 feat(worker): add synthesis pipeline` |
| ブランチ | `agent/phase2-engine-worker`（作業ツリーclean） |
| 対象タスク | T-201, T-202, T-203, T-204, T-205（全5件完了） |
| 基準 | `docs/implementation-plan.md` §7「ゲート G2: 偽エンジンでの全テスト成功 + 実モデル契約テスト成功（Claudeが基準Macで実行・記録）」 |

### 1.1 判定基準と充足状況

| # | G2基準 | 結果 | 証跡 |
|---|---|---|---|
| 1 | 偽エンジンでの全テスト成功 | 充足 | `pytest -q` → **177 passed, 6 skipped**（0.82秒） |
| 2 | 実モデル契約テスト成功（基準Mac） | 充足 | `pytest tests/engine_contract -q -m real_model` → **5 passed, 1 skipped** |
| 3 | Blocking / Major 指摘ゼロ | 充足 | T-201〜T-205 の各タスクレビューで Blocking 0件・Major 0件 |
| 4 | 静的解析クリーン | 充足 | `ruff check .` → `All checks passed!` |

### 1.2 通常テスト（偽エンジン）の再現手順と結果

```bash
.venv/bin/python -m pytest -q
# 177 passed, 6 skipped in 0.82s

.venv/bin/python -m ruff check .
# All checks passed!
```

- 実行時間 **0.82秒**は、通常実行で実モデル（Chatterbox Multilingual V3）を
  **一切ロードしていない**ことの証跡である（実モデルロードは初回数十秒規模）。
- skip 6件はすべて `tests/engine_contract/test_chatterbox.py` の実モデル契約テストであり、
  skip理由は「実モデル契約テストは `KOECLONE_REAL_MODEL=1` の環境でのみ実行する」。
  偽環境でのスキップ動作（T-203 完了条件）が満たされている。

### 1.3 実モデル契約テスト（基準Mac・完全オフライン）

| 項目 | 実測 |
|---|---|
| 実行環境 | 基準Mac（Apple M4 Pro） |
| 実行コマンド | `KOECLONE_REAL_MODEL=1 pytest tests/engine_contract -q -m real_model` |
| 結果 | **5 passed, 1 skipped** |
| ネットワーク | 完全オフラインで成功（外部接続 **0件**） |
| デバイス | MPS（CPUフォールバック不使用） |
| 出力形式 | モノラル / 24,000Hz / 16bit |
| ウォーターマーク | PerTh検出 **True** |

skip 1件は `test_mps_unavailable_without_fallback_is_rejected`。
基準MacではMPSが利用可能なため、当該分岐は設計どおりスキップされる
（skip理由: 「基準MacではMPSが利用可能」）。CPUフォールバック禁止時の拒否経路は
偽環境側のユニットテストで別途担保されている。

### 1.4 安全要件（FR-006 / FR-008 / AC-10）の確認

| 要件 | 確認内容 | 結果 |
|---|---|---|
| FR-006 | ウォーターマーク除去・無効化に相当する引数・設定・環境変数が実装に存在しないこと | 該当なし（`src/` 全体を検索し、無効化スイッチ0件）。契約テスト `test_no_watermark_disable_surface` / `test_source_has_lazy_model_imports_and_no_disable_surface` で恒久的に固定 |
| FR-008 | 生成直後のウォーターマーク検出。不検出時は `failed` とし音声を残さない | `worker/pipeline.py` で不検出時に生成WAVを削除し `ERR_WATERMARK_NOT_DETECTED` で `failed` 化。`tests/integration/test_pipeline.py` で検証済み |
| AC-10 | 音声・テキストの外部送信なし | `src/koeclone/` 配下に外向きHTTPクライアント（`requests` / `urllib` / `httpx` / URL直書き）の使用が **0件**。実モデル契約テストも完全オフラインで成功 |
| §7.1 | FFmpegを引数配列＋固定オプションで実行、`shell=True` 不使用 | `media/ffmpeg.py` は `subprocess` を引数配列で実行。`shell=True` の使用なし |

### 1.5 判定

上記1.1〜1.4のとおり、`docs/implementation-plan.md` §7 の **G2 完了条件をすべて充足**し、
Blocking / Major 指摘は 0 件である。よって **G2 を合格と判定する**。

Phase 3（T-301〜T-313）の委譲を許可する。実装契約は
`docs/task-contract-phase3.md` を正とする。

### 1.6 Phase 3 への申し送り

| # | 申し送り事項 |
|---|---|
| 1 | 通常テストで実モデルをロードしない構成（`real_model` マーカー分離）を Phase 3 でも維持する。API統合テスト・E2Eは **必ず `FakeEngine`** を使う |
| 2 | `worker/pipeline.py`・`worker/queue.py`・`engines/`・`media/`・`storage/`・`domain/` は Phase 2 以前で確定済み。Phase 3 のAPI層は**これらを呼ぶ薄い層**とし、ドメインロジックをAPI層へ再実装しない |
| 3 | `SynthesisPipeline.run()` は `status="running"` への更新から開始する。API層はジョブ行を `queued` で先に作成しておく必要がある |
| 4 | ファイルパス生成は必ず `storage/files.py` の `storage_path()`（UUID＋許可拡張子のみ）を使う。ユーザー入力から直接パスを組み立てない |
| 5 | `python-multipart`（ファイルアップロード）と Playwright（E2E）は未宣言。Claudeが Phase 3 着手前に導入する（Codexの作業ではない） |

---

## 2. G3 判定（Phase 3: API・UI・E2E）

| 項目 | 内容 |
|---|---|
| 判定 | **条件付き合格** |
| 判定日 | 2026-08-12 |
| 判定者 | Claude（指揮官） |
| 判定時HEAD | `f5be6e5 test(e2e): cover phase 3 user flows` |
| ブランチ | `agent/phase3-api-ui`（作業ツリーclean） |
| 対象タスク | T-301〜T-313（全13件完了） |
| 基準 | `docs/task-contract-phase3.md` §4（`docs/implementation-plan.md` §7 の G3 定義を細分化したもの） |
| 条件 | **T-314（音声プロフィール削除のUI導線）を G4 判定前に完了すること**（§2.6-1） |

### 2.1 G3 受入条件11件の充足状況

| # | 受入条件 | 結果 | 証跡（Claudeが再実行） |
|---|---|---|---|
| 1 | T-301〜T-306 の全API統合テスト成功 | 充足 | `pytest tests/integration -q` → **100 passed in 3.84s** |
| 2 | 全体回帰に劣化がない（Phase 2 の177件を下回らない） | 充足 | `pytest -q` → **248 passed, 6 skipped**。skipは実モデル契約テスト6件のみ |
| 3 | 通常実行で実モデルをロードしない | 充足 | `pytest -q --ignore=tests/e2e` → **238 passed, 6 skipped in 3.95s**。§2.2 参照 |
| 4 | 静的解析クリーン | 充足 | `ruff check .` → `All checks passed!` / `ruff format --check tests/e2e` → 差分なし |
| 5 | E2E 10シナリオ全件成功 | 充足 | `pytest tests/e2e -q` → **10 passed in 34.54s** |
| 6 | UC-01 を手動で通し確認 | 充足 | §2.3（アップロード・直接録音の両経路） |
| 7 | UC-02 を手動で通し確認 | 充足 | §2.3 |
| 8 | UC-03 を手動で通し確認 | 充足（限定） | §2.3。履歴削除経路は画面で確認。プロフィール削除は**UI導線が無く**API経由で確認（§2.6-1） |
| 9 | AC-01〜AC-10 のAPI/UI側が満たされている | 充足（AC-09のUI導線のみ未実装） | §2.4 突合表 |
| 10 | セキュリティ条件 S-1〜S-11 に違反がない | 充足 | §2.5 突合表 |
| 11 | 各タスクレビューで Blocking / Major 指摘ゼロ | 充足 | T-301〜T-312 は各レビューで0件。T-313 はレビューで Major 3件を検出し、**判定前に是正済み**（§2.6） |

### 2.2 実モデル非ロードの証跡（G3 #3 の解釈）

契約 §4 #3 は「`pytest -q` の実行時間が数秒以内」と書かれているが、T-313 で実ブラウザを
起動するE2E（10秒の実録音待ちを含む）が全体回帰に加わったため、`pytest -q` 全体では
**38.7秒**を要する。本条件の趣旨は「実モデル（Chatterbox Multilingual V3）をロードしない」
ことの担保であり、次の分離計測で充足を確認した。

```bash
uv run pytest -q --ignore=tests/e2e   # 238 passed, 6 skipped in 3.95s
uv run pytest tests/e2e -q            # 10 passed in 34.54s（ブラウザ起動と実録音待ち）
uv run pytest -q                      # 248 passed, 6 skipped in 38.74s
```

E2E以外が **3.95秒**であること、E2Eサーバーが `KOECLONE_ENGINE=fake` 固定で起動することから、
通常実行で実モデルをロードしていないと判定する。

### 2.3 UC-01〜03 の手動通し確認（Claude実施）

`KOECLONE_ENGINE=fake KOECLONE_DATA_DIR=/tmp/koe-manual/data KOECLONE_PORT=8231 ./scripts/run.sh`
で実サーバーを起動し、Chromium（偽メディアストリーム）で画面を操作して確認した。
確認はスクリーンショットと実測値で裏取りしている。

| UC | 手順 | 実測 |
|---|---|---|
| UC-01 (1) | 同意前は録音・ファイル選択が不可 | `#record-start` / `#voice-file` ともに `disabled=true` |
| UC-01 (1) | 同意後に有効化・リロード後も保持 | 両方 `enabled`、リロード後も `#usage-consent` checked |
| UC-01 (3) | 直接録音: 同意文の表示 | 「…確認語は「こもれび」、確認番号は03769796です。」（都度生成） |
| UC-01 (3) | 録音・経過表示 | `#record-time` が `00:10` まで進行 |
| UC-01 (5) | validate | `200` / `duration_ms=10260` / `sample_rate=24000` / `channels=1` |
| UC-01 (6) | 正規化音声の試聴 | `#record-playback` に `/api/voices/draft/{id}/audio` |
| UC-01 (7) | プロフィール作成（直接録音） | `source_mode=direct_recording` / `consent_method=live_challenge` / `has_consent_audio=true` |
| UC-01 (4)(6)(7) | ファイル登録（2回の権利確認） | 確認①未チェックで `音声を確認する` が `disabled`、確認②未チェックで `この声で確定` が `disabled`。作成後 `source_mode=file_upload` |
| UC-01 | テスト音声の再生 | `200` / `audio/wav` / `Content-Disposition: attachment; filename="koeclone_…wav"` / 先頭 `RIFF`…`WAVE` / 124,844 bytes |
| UC-02 (1) | 原文入力とカウンタ | 「明日は日本橋へ行きます」→ `11 / 1,000文字` |
| UC-02 (3) | 範囲選択 | `#selected-surface` = `日本橋` |
| UC-02 (4) | プレビュー（強調と合成用テキスト） | `mark=['日本橋']`、`読み上げ: 明日はにほんばしへ行きます`、`合成用 13 / 2,000文字` |
| UC-02 (6) | AI生成確認 | 未チェックで `音声を生成` が `disabled` |
| UC-02 (8) | 進行表示 | `あなたの声で生成しています…` → `音声が完成しました` |
| UC-02 (9) | 再生・ダウンロード | 新ジョブURLに配線、`200` / `audio/wav` / `Content-Disposition` 付き / 先頭 `RIFF` |
| UC-02 (7) | 原文保持 | 画面の原文は `明日は日本橋へ行きます` のまま。保存側も `text_preview=明日は日本橋へ行きます` / `override_count=1` |
| UC-03 (1)(2)(3) | 履歴の個別削除 | 2件→1件（画面操作） |
| UC-03 (1)(2)(3) | 履歴の全削除 | 確認ダイアログ「生成した音声をすべて削除します。元に戻せません。よろしいですか？」→ 承認後0件・空状態表示 |
| UC-03 | 履歴全削除がプロフィールを消さない | `GET /api/voices/current` → `200` |
| UC-03 | プロフィール削除の連鎖削除 | `DELETE /api/voices/current` → `204`、以後 `voices/current` `404` / `syntheses/{id}` `404` / `syntheses/{id}/audio` `404`、画面の履歴も空 |

ブラウザコンソールエラー・未捕捉例外は**0件**だった。

### 2.4 AC-01〜AC-10 突合表

| AC | 判定 | 根拠 |
|---|---|---|
| AC-01 初回同意 | 充足 | 同意画面に「本人の声のみ登録可能」「禁止用途」を表示。同意まで `#record-start` / `#voice-file` が `disabled`。E2E #1 ＋ 手動確認 |
| AC-02 音声プロフィール作成（録音） | 充足 | 10〜60秒の判定（クライアント事前警告＋サーバー最終判定）、試聴、確定、テスト音声の生成・再生。E2E #2 ＋ 手動確認（`direct_recording` / `live_challenge`） |
| AC-03 ファイル登録 | 充足 | WAV / MP3 の両形式、2回の権利確認、正規化後の試聴、確定。E2E #3・#4 ＋ 手動確認 |
| AC-04 不正音声の拒否 | 充足 | 無音WAVで `#upload-error` に「…別のファイルを選んで…」を表示し `別のファイルを選ぶ` 導線を提示。プロフィールは作成されない。E2E #5。長さ・容量・形式偽装・破損は T-303 の統合テストで担保 |
| AC-05 音声生成 | 充足 | 生成→進行表示→再生→ダウンロード。E2E #6 は**今回作成されたジョブID**でプレイヤーとダウンロードURLが配線されることを確認し、実体を取得して `200` / `audio/wav` / `Content-Disposition` / `RIFF…WAVE` を検証 |
| AC-06 部分読み修正 | 充足 | 合成用テキスト全体が `明日はにほんばしへ行きます` になること、`日本橋` のみ強調、原文不変、保存側 `text_preview` が原文のまま・`override_count=1`。E2E #7 ＋ 手動確認 |
| AC-07 入力・読み修正制限 | 充足 | AI生成確認なしでは生成ボタンが `disabled`（E2E #8）。空白・文字数超過・無効な読み・重複範囲・元文字列不一致・プロフィール未作成の拒否は T-305 統合テスト。S-4 の上限は `domain/text_validation.py` / `domain/synthesis_text.py` で強制 |
| AC-08 AI生成表示 | 充足 | `watermark_detected=true` を E2E #6 と手動確認で実測。不検出時に `failed` 化してWAVを残さない実装は Phase 2 で固定（G2 §1.4） |
| AC-09 完全削除 | **API側充足 / UI導線のみ未実装** | `DELETE /api/voices/current` → `204` 後、参照音声・同意録音・生成音声・DB行が取得不能（`404`×3）。E2E #10 ＋ 手動確認。**ただし画面に「プロフィールを削除する」操作要素が存在しない**（§2.6-1） |
| AC-10 ローカル限定 | 充足 | `scripts/run.sh` が `--host 127.0.0.1` 固定、`AppConfig.host` は `init=False`＋env未参照。`src/` に外向きHTTPクライアント0件、UIに外部CDN参照0件（§2.5 S-1 / S-11） |

### 2.5 セキュリティ条件 S-1〜S-11 突合表

| S | 判定 | 根拠 |
|---|---|---|
| S-1 | 充足 | `scripts/run.sh:6` が `--host 127.0.0.1` 固定。`AppConfig.host` は `field(default="127.0.0.1", init=False)` で `from_env()` にホスト読取なし。`test_run_script_binds_loopback_only` / `test_app_config_host_cannot_be_overridden_by_env` |
| S-2 | 充足 | `src/` 全体に `CORS` の出現0件。`test_no_cors_headers_are_exposed` |
| S-3 | 充足 | 50MB超を `413 ERR_REQUEST_TOO_LARGE`。宣言値と受信バイト数の両方で打ち切り（`test_request_body_over_50mb_is_rejected` / `test_request_body_limit_stops_spoofed_stream`） |
| S-4 | 充足 | 原文1,000／合成用2,000を `domain/text_validation.py` `domain/synthesis_text.py` で生成前に拒否。UIカウンタと `maxlength` も併設 |
| S-5 | 充足 | `api/voices.py` `api/syntheses.py` のファイルパスは全て `storage_path()` 経由。`storage_path()` は識別子をUUIDに強制変換し、拡張子を許可リスト照合するため `../` 混入や利用者文字列のパス連結が成立しない。利用者由来のファイル名は `Path(...).suffix` の判定のみに使用 |
| S-6 | 充足 | `src/` の `subprocess` 使用は `media/ffmpeg.py`（Phase 2 確定）のみ。`shell=True` 0件。Phase 3 のAPI層は新規に呼んでいない |
| S-7 | 充足 | `api/` のログ出力は `app.py:209` の1箇所のみで、内容は `error_id` と `code` だけ。音声・テキスト・絶対パスの出力なし |
| S-8 | 充足 | `openapi_url` / `docs_url` / `redoc_url` はフラグ無効時 `None`。`test_openapi_is_disabled_by_default` |
| S-9 | 充足 | catch-all が `500 ERR_INTERNAL` ＋ `error_id` のみを返す。`test_internal_error_hides_details_and_returns_error_id` / `test_unexpected_error_uses_stable_internal_shape` |
| S-10 | 充足 | `api/syntheses.py:153` が `status != "succeeded" or watermark_detected is not True` で配信を拒否。一覧の `audio_available` も同条件 |
| S-11 | 充足 | `src/` に外向きHTTPクライアント（`requests` / `httpx` / `urllib` / URL直書き）0件。`web/` に外部CDN・外部フォント・外部画像の参照0件（`link`/`script` は同梱のみ） |

**テスト側の補足**: `tests/e2e/conftest.py` は実サーバー起動に `subprocess.Popen(scripts/run.sh)` を、
MP3生成に `media/ffmpeg.py` のラッパを使用する。S-6 は製品コードの音声処理経路に対する条件であり、
E2Eのサーバー起動はこれに該当しない。音声変換は所定のラッパ経由であるため違反はない。

### 2.6 T-313 レビューで検出した指摘と是正

Claudeが T-313 を独立レビューし、**Major 3件**を検出した。いずれも「テストが通っているのに
ACを実質検証していない（空振りする）」類のものである。判定前に**所有ファイル
`tests/e2e/test_flows.py` の内部で是正**し、再検証した（`f5be6e5`）。

| # | 重大度 | 指摘 | 是正 |
|---|---|---|---|
| 1 | Major | 生成の完了判定が `#synthesis-progress` の「音声が完成しました」だったため、**登録時テスト音声の文言が残っている**状態で即座に成立し得た。ダウンロード検証も `href` が `/audio$` に一致するだけで、前ジョブのURLでも通ってしまう | 生成時の `POST /api/syntheses` 応答からジョブIDを取得し、`#synthesis-player` の `src` と `#synthesis-download` の `href` が**そのジョブID**であることを条件にした。さらに音声実体を取得して `200` / `audio/wav` / `Content-Disposition` / `RIFF…WAVE` を検証し、`watermark_detected` と `override_count` も照合 |
| 2 | Major | シナリオ7が契約 §2.13「プレビュー確認 → **生成**（原文が変わらないこと）」の生成段を実施しておらず、検証も `にほんばし` の部分一致のみで AC-06 の合成用テキスト全体・強調表示を確認していなかった | プレビューで `読み上げ: 明日はにほんばしへ行きます` の完全一致、`mark` が `日本橋` のみ、`合成用 13` を検証。続けて生成を実行し、画面の原文が不変であること、保存側 `text_preview` が原文・`override_count=1` であることを検証 |
| 3 | Major | シナリオ10が削除と検証を全て `page.request`（生API）で行っており、UC-03 のユーザーフローではなく T-304 のAPIを再テストしていた。**UIが存在しなくても通る** | 事前状態を画面の履歴2件で確認し、削除後はリロードして画面の履歴が空になることまで検証。プロフィール削除の実行だけはUI導線が無いためAPI経由とし、その旨と申し送り（§2.6-1）をテスト内に明記 |

是正の有効性は変異テストで確認した。`synthesis.js` の成功時 `download.href` 更新を一時的に
削除するとシナリオ6が `FAILED` になり（是正前は通過し得た）、復元後は再び10件成功する。

さらに、E2Eを収集順で最後に回す `pytest_collection_modifyitems` が必要であることを、
並び順を反転させる一時改変で確認した（`tests/integration/test_app.py::test_request_body_limit_stops_spoofed_stream`
が `RuntimeError: asyncio.run() cannot be called from a running event loop` で失敗する）。
既存テストを変更せずに解消する妥当な手段と判断し、意図をコメントとして残させた。
一時改変はいずれも検証後に復元し、`git diff` が空であることを確認している。

### 2.6-1 条件（G4 判定前に解消すること）

| # | 重大度 | 内容 |
|---|---|---|
| 1 | Major（契約の欠落） | **音声プロフィール削除のUI導線が存在しない。** 画面上の全操作要素を列挙して確認した結果、削除系は履歴の「削除」「すべて削除」のみで、`DELETE /api/voices/current` を呼ぶ操作が無い。仕様 §4 スコープ6「1件の音声プロフィールの作成・再録音・再アップロード・**削除**」と AC-09「利用者がプロフィール削除を確定する」を満たすには UI が必要である。原因は **Phase 3 契約 §2.7〜§2.12 のタスク分解にプロフィール削除UIを含めなかったこと（Claudeの契約起草漏れ）** であり、Codex側の逸脱ではない（§0.6-5 は契約外の画面機能の追加を禁じている）。**T-314 として起票し、G4 判定前に完了・検証すること。** UC-03 は「プロフィールまたは生成履歴を削除する」と定義されており、履歴削除経路は画面で確認済みのため、G3 は条件付き合格とする |

### 2.7 Phase 4 への申し送り（Minor 以下・是正不要だが記録する）

| # | 重大度 | 対象 | 内容 |
|---|---|---|---|
| 1 | Minor | `web/js/synthesis.js`（T-311） | 2回目以降の生成で、最初の状態取得応答が返るまで `#synthesis-progress` に前ジョブの「音声が完成しました」が残る。プレイヤーとダウンロードリンクは `hidden` のため誤ったファイルを取得する経路は無く、実測の残存時間もローカルでは十数msだが、`pollJob` 開始時に文言を初期化するのが望ましい（ルート遅延3秒を挿入した検証で再現を確認） |
| 2 | Minor | `web/js/record.js`（T-308） | 停止直後の検証POSTが飛んでいる間に「録音を開始」を押せる（`stop` ハンドラが即座に `start.disabled=false` にする）。この窓で再録音を始めると、先行応答が後から `draftId` を上書きし得る。単一利用者・約1秒の窓で影響は限定的 |
| 3 | Minor | `web/js/record.js`（T-308） | 同意文の取得に失敗した場合、メッセージは表示されるが**再取得の導線が無く**、録音開始も有効なまま（`consent_text` 空でサーバーが400で拒否する）。再試行ボタンが望ましい |
| 4 | Minor | `web/js/synthesis.js`（T-310） | 合成用カウンタ `#synthesis-count` が `#pronunciation-editor` の内側にあり、通常モードでは非表示。通常モードでは合成用＝原文であり S-4 はサーバー側で強制されるため実害は無い |
| 5 | Info | `web/index.html` / `style.css`（T-307） | 「読み上げる文章」ラベルがモード切替タブと同じ行に回り込んで表示される（体裁のみ） |
| 6 | Info | `tests/e2e/`（T-313） | E2Eは偽エンジンが高速なため `queued` / `running` の中間表示を決定的に観測できない。進行表示の中間状態の自動検証は T-401 でルート遅延等を用いて追加するのが望ましい（手動確認では `あなたの声で生成しています…` を観測済み） |
| 7 | 情報 | 全体 | Phase 3 は `tests/e2e/` 以外で Blocking / Major 0件。T-401（セキュリティ自動テスト）で S-1〜S-11 の自動化を行う予定は契約 §4 #10 のとおり |

### 2.8 判定

契約 §4 の受入条件11件はすべて充足し、Phase 3 の実装（T-301〜T-312）に Blocking / Major の
未是正指摘は無い。T-313 で検出した Major 3件は判定前に是正し、再検証済みである。

一方で、仕様 §4 スコープ6 と AC-09 が求める**プロフィール削除のUI導線が実装されていない**。
これは契約起草時の欠落であり、リリース前に必ず解消する必要がある。

よって **G3 を条件付き合格と判定する**。条件は §2.6-1 の T-314（プロフィール削除UI）の完了であり、
**G4 判定前に完了・検証すること**を必須とする。Phase 4（T-401 以降）の着手は許可する。
