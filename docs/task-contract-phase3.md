# タスク契約 Phase 3: API・UI・E2E（T-301〜T-313 統合契約）

| 項目 | 内容 |
|---|---|
| 契約ID | PHASE3（T-301〜T-313 の統合契約） |
| 文書所有者 | Claude（唯一の指揮官）。本文書の変更はClaudeのみが行う |
| 実装担当 | Codex |
| 上位文書 | `docs/implementation-plan.md` §7 Phase 3 / §8、`docs/system-specification.md` §6・§7・§9・§10・§11 |
| 参照文書 | `docs/gate-records.md` §1（G2判定）、`docs/task-contract-phase1.md`、`docs/task-contract-phase2.md` |
| 前提ゲート | **G2 合格済み**（2026-08-10 / HEAD `7fc2423` / `pytest -q` 177 passed・6 skipped、`ruff check .` 指摘ゼロ、実モデル契約 5 passed・1 skipped） |
| ブランチ | `agent/phase3-api-ui`（**Git操作は全てClaudeが実施。Codexはgitコマンドを一切実行しない**） |
| 見積 | 合計60h（T-301 4h / T-302 1h / T-303 8h / T-304 3h / T-305 6h / T-306 3h / T-307 4h / T-308 6h / T-309 4h / T-310 6h / T-311 4h / T-312 3h / T-313 8h） |

本契約は実装計画 §7 Phase 3 の13タスクを1文書に統合したものである。
**本契約は実装計画に定義された機能のみを対象とし、新機能を追加しない。**
計画・仕様と本契約が矛盾した場合、または本契約に矛盾・算術ミス・実装不能な指示を見つけた場合は、
**黙って直さず作業を止めてClaudeへ報告する**（§0.6 停止条件）。

---

## 0. 委譲プロセスと依存順

### 0.1 依存グラフ（この順序以外で着手しない）

```text
T-301（FastAPI基盤・エラー基盤・起動スクリプト）
  ├→ T-302（同意API）
  ├→ T-303（プロフィール作成API）→ T-304（プロフィール取得・削除API）  ※同一ファイル・順次
  ├→ T-305（合成API）           → T-306（履歴API）                    ※同一ファイル・順次
  └→ T-307（UI基盤・同意画面。T-302完了後）
        ├→ T-308（直接録音UI。T-303完了後）
        ├→ T-309（アップロードUI。T-303完了後）
        ├→ T-310（テキスト入力・読み修正UI。T-305完了後）→ T-311（進行・再生・DL UI）※同一ファイル・順次
        └→ T-312（履歴UI。T-306完了後）
              └→ T-313（E2E。T-307〜T-312完了後）
```

**並行可能な組み合わせ**（互いに素なファイルのみ）:

| 段 | 並行可能なタスク |
|---|---|
| 1 | T-301（単独。最初に必ず完了させる） |
| 2 | {T-302} / {T-303→T-304} / {T-305→T-306} の3系列を並行可 |
| 3 | T-307（単独） |
| 4 | {T-308} / {T-309} / {T-310→T-311} / {T-312} の4系列を並行可 |
| 5 | T-313（単独） |

- **T-301 が最初。** T-301 は `src/koeclone/errors.py` と `src/koeclone/config.py` を変更するため、
  他の全タスクは T-301 完了後に着手する。
- 矢印「→」で結ばれたタスクは**同一ファイルを所有するため必ず順次**実行する。
- 1タスク = 1委譲 = 1報告 = 1コミット。複数タスクをまとめて報告しない。
  タスク完了ごとにClaudeがレビューし、所有ファイルを個別に `git add <file>` してコミットする。

### 0.2 委譲前提（Claudeが着手前に整備する。Codexの作業ではない）

以下は **Claudeが別コミットで事前に整備する**。Codexはこれらを理由に停止せず、
未整備を発見した場合は §0.6 に従い報告する。

| # | 整備物 | 対象タスク | 内容 |
|---|---|---|---|
| 1 | `python-multipart` を `pyproject.toml` の `dependencies` に追加 | T-303 | FastAPI の `UploadFile` / `Form` に必須。現在は間接的に存在するのみで未宣言 |
| 2 | 空パッケージ骨格 `src/koeclone/api/__init__.py` | T-301 | 空ファイルのまま。Codexは変更しない |
| 3 | `src/koeclone/web/` ディレクトリ（空） | T-307 | 静的ファイル配置先 |
| 4 | Playwright 導入（`pytest-playwright` + ブラウザバイナリ）と `tests/e2e/__init__.py` | T-313 | 導入形態はClaudeが確定。Codexは `pyproject.toml` を触らない |

### 0.3 依存関係の状態（Claude確認済み・2026-08-10）

| パッケージ | 版 | 区分 | Phase 3 での用途 |
|---|---|---|---|
| `fastapi` | >=0.116 | 直接依存 | 全API |
| `uvicorn` | >=0.35 | 直接依存 | T-301 起動 |
| `httpx` | >=0.28 | dev | `TestClient` の実体 |
| `pytest` | >=8.4 | dev | 全テスト |
| `ruff` | >=0.12 | dev | 静的解析 |
| `python-multipart` | 導入予定 | 直接依存（Claudeが追加） | T-303 multipart受信 |
| `pytest-playwright` | 導入予定 | dev（Claudeが追加） | T-313 |

**Codexは `pyproject.toml` / `uv.lock` を変更しない。** 依存追加が必要と判断した場合は停止して報告する。

### 0.4 変更禁止ファイル（全タスク共通）

Codexは以下を**一切変更しない**。変更が必要と判断した場合は停止して報告する。

```text
pyproject.toml, uv.lock, .gitignore
docs/**（全ドキュメント）
scripts/poc_generate.py
src/koeclone/domain/**      （Phase 1 で確定）
src/koeclone/storage/**     （Phase 1 で確定）
src/koeclone/engines/**     （Phase 2 で確定）
src/koeclone/media/**       （Phase 2 で確定）
src/koeclone/worker/**      （Phase 2 で確定）
src/koeclone/__init__.py
tests/unit/**               （既存の全ファイル）
tests/integration/test_db.py, test_ffmpeg.py, test_pipeline.py
tests/engine_contract/**
```

**例外は T-301 のみ**: T-301 は `src/koeclone/errors.py`（列挙子の追加のみ）と
`src/koeclone/config.py`（フィールドの追加のみ）を変更できる。§2.1 に定める追加以外は行わない。
既存の列挙子・フィールドの**改名・削除・既定値変更は禁止**。

### 0.5 報告フォーマット（タスクごとに必ずこの形式で報告）

```markdown
## T-3xx 完了報告
- 実装ファイル: <所有ファイルのみ列挙>
- RED: <最初に書いた失敗テストと、失敗を確認したコマンド出力の要約>
- GREEN: <通した実装の要点>
- REFACTOR: <実施範囲。未実施なら「なし」>
- 検証コマンドと結果:
  $ <コマンド>
  <実出力の末尾>
- 全体回帰: $ pytest -q → <実出力>
- 静的解析: $ ruff check . → <実出力>
- 契約からの逸脱: <なし / あれば内容と理由>
- 未解決事項: <なし / あれば内容>
```

- **実行していないコマンドの結果を書かない。予測値を実測値として報告しない。**
- 「完了」と書く前に、必ず検証コマンドと `pytest -q` を実行して出力を確認する。

### 0.6 停止条件（下記に該当したら作業を止めてClaudeへ報告）

1. 本契約に矛盾・算術ミス・実装不能な指示を見つけた。
2. 変更禁止ファイルの変更が必要になった。
3. 依存パッケージの追加・変更が必要になった。
4. 同一のテスト失敗を3回連続で解消できない。
5. 契約に定義のないAPI・データ項目・画面機能が必要だと判断した
   （**推測で機能を追加しない**）。
6. セキュリティ条件（§1.4）を満たせない実装しか思いつかない。

---

## 1. 全タスク共通規約

### 1.1 エラーレスポンス形式（全APIで統一）

```json
{
  "error": {
    "code": "ERR_TEXT_TOO_LONG",
    "message": "本文は1,000文字以内で入力してください。",
    "error_id": null
  }
}
```

| フィールド | 型 | 内容 |
|---|---|---|
| `error.code` | string | `ErrorCode` の値。安定識別子（FR §7.4「全APIエラーは安定したエラーコードを持つ」） |
| `error.message` | string | 利用者向け日本語メッセージ。**内部情報（例外文言・スタックトレース・ファイルパス・SQL）を含めない** |
| `error.error_id` | string \| null | `ERR_INTERNAL` のときのみ UUID4 文字列。他は `null`。同じIDでサーバーログに1行だけ記録する |

### 1.2 エラーコード → HTTPステータス対応表（この表以外の対応を作らない）

| HTTP | ErrorCode |
|---|---|
| 400 | `ERR_BAD_REQUEST` |
| 403 | `ERR_NO_CONSENT`, `ERR_AI_DISCLOSURE_REQUIRED` |
| 404 | `ERR_PROFILE_NOT_FOUND`, `ERR_JOB_NOT_FOUND`, `ERR_DRAFT_NOT_FOUND` |
| 409 | `ERR_PROFILE_ALREADY_EXISTS`, `ERR_AUDIO_NOT_READY` |
| 413 | `ERR_REQUEST_TOO_LARGE` |
| 422 | `ERR_TEXT_EMPTY`, `ERR_TEXT_TOO_LONG`, `ERR_TEXT_WHITESPACE_ONLY`, `ERR_SYNTHESIS_TEXT_TOO_LONG`, `ERR_READING_EMPTY`, `ERR_READING_INVALID_CHARS`, `ERR_OVERRIDE_RANGE_INVALID`, `ERR_OVERRIDE_SURFACE_MISMATCH`, `ERR_OVERRIDE_OVERLAP`, `ERR_OVERRIDE_NO_KANJI`, `ERR_AUDIO_TOO_SHORT`, `ERR_AUDIO_TOO_LONG`, `ERR_AUDIO_MOSTLY_SILENT`, `ERR_AUDIO_CLIPPING`, `ERR_AUDIO_LEVEL_OUT_OF_RANGE`, `ERR_FILE_TOO_LARGE`, `ERR_FILE_FORMAT_MISMATCH`, `ERR_FILE_CORRUPTED`, `ERR_FILE_NO_AUDIO`, `ERR_FILE_UNSUPPORTED_FORMAT` |
| 500 | `ERR_INTERNAL`, `ERR_WATERMARK_NOT_DETECTED`（API直接返却はせず、ジョブの `error_code` として保持） |

### 1.3 命名・型の規約

- JSONのフィールド名は **snake_case**（既存 `SynthesisJob` / `VoiceProfile` のフィールド名に一致させる）。
- 日時は **ISO 8601 UTC 文字列**（既存 `datetime.now(UTC).isoformat()` と同形式）。
- ID は **UUID4 の文字列**。パスパラメータは `uuid.UUID` 型で受け取り、
  不正形式は `400 ERR_BAD_REQUEST` に変換する（FastAPI 既定の422をそのまま返さない）。
- 真偽値はJSON boolean。文字列 `"true"` を使うのは multipart フォーム値のみ。

### 1.4 セキュリティ条件（全タスクで必ず満たす。違反はBlocking）

| # | 条件 | 根拠 |
|---|---|---|
| S-1 | バインドは `127.0.0.1` 固定。**ホストを外部公開へ変更する設定項目・環境変数・CLI引数を作らない** | AC-10 / §7.1 |
| S-2 | `CORSMiddleware` を**追加しない**。`Origin` 付きリクエストでも `access-control-allow-origin` 応答ヘッダが存在しないこと | §7.1 |
| S-3 | リクエストボディは最大 **50MB**（`52,428,800` バイト）。超過は `413 ERR_REQUEST_TOO_LARGE`。`Content-Length` 詐称に備え**受信バイト数でも計測**して打ち切る | FR-104 / §7.1 |
| S-4 | 原文テキストは最大 **1,000文字**、合成用テキストは最大 **2,000文字**。超過は生成前に拒否 | FR-201 / FR-217 |
| S-5 | ファイルパスは **`storage/files.py` の `storage_path()` のみ**で生成する。ユーザー入力（ファイル名・表示名・ID文字列）を `Path` 連結に使わない。`../` を含む入力で保存先が `data_dir` 外に出ないこと | §7.1 |
| S-6 | `subprocess` を新規に呼ばない。音声処理は `media/ffmpeg.py` の関数経由のみ。`shell=True` 禁止 | §7.1 |
| S-7 | ログに**音声データ・原文全文・合成用テキスト全文・同意文全文・ファイルの絶対パス**を出力しない。ログ可なのは「エラーコード・`error_id`・ジョブID・処理時間・文字数」まで | §7.1 |
| S-8 | OpenAPI（`/openapi.json`・`/docs`・`/redoc`）は**既定で無効**。開発時のみ明示フラグで有効化 | 実装計画 T-301 |
| S-9 | エラーレスポンスに例外メッセージ・スタックトレース・内部パスを含めない | §7.1 |
| S-10 | 生成音声の配信は `status == "succeeded"` **かつ** `watermark_detected is True` のときのみ | FR-008 / AC-08 |
| S-11 | 外部ネットワークへの送信を行うコードを書かない（HTTPクライアント・テレメトリ・CDN参照を含む）。**UIは外部CDNを参照せず、CSS/JSは同梱ファイルのみ** | AC-10 / §7.1 |

### 1.5 テスト規約

- API統合テストは **`FakeEngine` を使用**し、実モデルを絶対にロードしない。
  `pytest -q` の実行時間が数秒を超える実装にしない。
- テストは `tmp_path` を使い、`AppConfig(data_dir=tmp_path/...)` でデータディレクトリを隔離する。
  利用者のホーム配下（`~/koeclone-data`）を汚さない。
- 各テストは独立させる（実行順に依存しない）。
- テスト名は `test_<期待される振る舞い>` とし、日本語コメントで意図を補足してよい。
- 音声fixtureは**プログラム生成**する（実在人物の音声を使わない）。
  既存 `tests/integration/test_ffmpeg.py` のfixture生成手法を参考にしてよいが、同ファイルは変更しない。

### 1.6 アプリ構成（T-301で確立し、以降のタスクはこれに従う）

```python
# src/koeclone/api/app.py
def create_app(config: AppConfig, *, engine: SpeechEngine, docs_enabled: bool = False) -> FastAPI: ...
def create_default_app() -> FastAPI: ...  # 環境変数から構築。uvicorn --factory 用
```

`app.state` に以下を保持し、各ルータはここから取得する（グローバル変数を使わない）:

| `app.state` の属性 | 型 |
|---|---|
| `config` | `AppConfig` |
| `paths` | `DataPaths` |
| `database` | `Database` |
| `engine` | `SpeechEngine` |
| `pipeline` | `SynthesisPipeline` |
| `queue` | `JobQueue` |
| `drafts` | `dict[str, VoiceDraft]`（プロセス内のみ。永続化しない） |

---

## 2. タスク定義

### 2.1 T-301: FastAPI基盤（4h）

**目的**: アプリファクトリ、共通エラー基盤、サイズ制限、静的配信、ヘルス、起動スクリプトを作る。

**依存**: G2（前提ゲート合格済み）

**所有ファイル**:
```text
src/koeclone/api/app.py         （新規）
scripts/run.sh                  （新規・実行権限 755）
tests/integration/test_app.py   （新規）
src/koeclone/errors.py          （列挙子の追加のみ）
src/koeclone/config.py          （フィールドの追加のみ）
```

**`errors.py` へ追加する列挙子（この7件のみ。既存は一切変更しない）**:

```python
ERR_BAD_REQUEST = "ERR_BAD_REQUEST"
ERR_REQUEST_TOO_LARGE = "ERR_REQUEST_TOO_LARGE"
ERR_DRAFT_NOT_FOUND = "ERR_DRAFT_NOT_FOUND"
ERR_PROFILE_NOT_FOUND = "ERR_PROFILE_NOT_FOUND"
ERR_JOB_NOT_FOUND = "ERR_JOB_NOT_FOUND"
ERR_AUDIO_NOT_READY = "ERR_AUDIO_NOT_READY"
ERR_AI_DISCLOSURE_REQUIRED = "ERR_AI_DISCLOSURE_REQUIRED"
```

**`config.py` へ追加するフィールド（この2件のみ）**:

```python
engine: str = "chatterbox"      # "chatterbox" | "fake"
app_version: str = "0.1.0"
```
`from_env()` は `KOECLONE_ENGINE`（既定 `"chatterbox"`、`"fake"` のみ許容。他値は `ValueError`）を読む。
`app_version` は環境変数から読まない（固定値）。
**変更後に `pytest tests/unit/test_config.py -q` が引き続き成功すること。失敗したら停止して報告。**

**API仕様**:

`GET /api/health` → `200`
```json
{"status": "ok", "app_version": "0.1.0", "engine": "fake", "model_loaded": false}
```
`model_loaded` は「エンジンの `load()` が完了済みか」。エンジンをロードさせない（呼ぶだけで副作用を起こさない）。

**RED（先に書いて失敗を確認するテスト）**:

| # | テスト関数名 | 検証内容 |
|---|---|---|
| 1 | `test_health_returns_ok_without_loading_model` | `200` / 上記JSON形状 / `FakeEngine.load_count == 0` |
| 2 | `test_no_cors_headers_are_exposed` | `Origin: http://evil.example` 付きGETで `access-control-allow-origin` ヘッダが**存在しない**（S-2） |
| 3 | `test_request_body_over_50mb_is_rejected` | 50MB+1バイトのPOSTが `413` / `ERR_REQUEST_TOO_LARGE`（S-3） |
| 4 | `test_error_response_shape_is_stable` | 未知パス `GET /api/unknown` が `404` かつ `{"error":{"code","message","error_id"}}` 形状 |
| 5 | `test_internal_error_hides_details_and_returns_error_id` | 意図的に `KoecloneError(ERR_INTERNAL)` を投げるテスト用ルートで `500` / `error_id` がUUID / メッセージに例外文言・パスを含まない（S-9） |
| 6 | `test_openapi_is_disabled_by_default` | `GET /openapi.json` と `GET /docs` が `404`。`docs_enabled=True` では `200`（S-8） |
| 7 | `test_static_web_directory_is_served` | `GET /` が `200` かつ `text/html`（`web/index.html` が無い段階は暫定ファイルをtmpに用意して検証してよい） |
| 8 | `test_invalid_uuid_path_becomes_bad_request` | `GET /api/syntheses/not-a-uuid` が `400 ERR_BAD_REQUEST`（§1.3） |
| 9 | `test_run_script_binds_loopback_only` | `scripts/run.sh` が `127.0.0.1` を含み、`0.0.0.0` と `--host` の外部指定を含まない（S-1） |
| 10 | `test_app_config_host_cannot_be_overridden_by_env` | `KOECLONE_HOST=0.0.0.0` を設定しても `AppConfig.from_env().host == "127.0.0.1"`（S-1） |

**GREEN**: 最小のアプリファクトリ、`KoecloneError` → JSON のグローバル例外ハンドラ、
`RequestValidationError` → `400 ERR_BAD_REQUEST` ハンドラ、サイズ制限ミドルウェア、
`StaticFiles(directory=web, html=True)` を `/` へ**最後にマウント**（`/api/*` を先に登録）。

**REFACTOR**: 例外ハンドラとメッセージ表の整理まで。

**`scripts/run.sh` の内容（この形を守る）**:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PWD}/src"
exec .venv/bin/python -m uvicorn koeclone.api.app:create_default_app \
  --factory --host 127.0.0.1 --port "${KOECLONE_PORT:-8000}"
```

**検証**: `pytest tests/integration/test_app.py -q`
**完了条件**: 全テスト成功。バインド先を外部公開へ変える設定項目が存在しない。`ruff check .` 指摘ゼロ。

---

### 2.2 T-302: 同意API（1h）

**目的**: `GET /api/consent/challenge` で毎回異なる同意文を返す（FR-003）。

**依存**: T-301
**所有ファイル**: `src/koeclone/api/consent.py`, `tests/integration/test_consent_api.py`

**API仕様**: `GET /api/consent/challenge` → `200`
```json
{"consent_text": "わたしは わたし自身の声で 音声クローンを作成することに同意します。合言葉は 3417 です。"}
```
`domain/consent.py` の `generate_consent_challenge()` をそのまま呼ぶ薄い層とする。

**RED**:
| # | テスト関数名 | 検証内容 |
|---|---|---|
| 1 | `test_challenge_returns_consent_text` | `200` / `consent_text` が非空文字列 |
| 2 | `test_challenge_differs_between_requests` | 連続10回取得して2種類以上（同一値の連続返却でない） |

**GREEN**: ドメイン関数を呼ぶルータのみ。**API層でロジックを再実装しない。**
**REFACTOR**: なし（薄い層を維持）。
**検証**: `pytest tests/integration/test_consent_api.py -q`

---

### 2.3 T-303: プロフィール作成API（8h）

**目的**: `POST /api/voices` の2段階（`validate` → `confirm`）作成。直接録音とWAV/MP3アップロードの両対応。

**依存**: T-301
**所有ファイル**: `src/koeclone/api/voices.py`（作成部）, `tests/integration/test_voices_create_api.py`

**API仕様**: `POST /api/voices`（`multipart/form-data`）

*stage=validate*

| フォーム項目 | 型 | 必須 | 内容 |
|---|---|---|---|
| `stage` | str | ✅ | `"validate"` |
| `source_mode` | str | ✅ | `"direct_recording"` \| `"file_upload"` |
| `consent_accepted` | str | ✅ | `"true"` 以外は `403 ERR_NO_CONSENT`（FR-002/004） |
| `consent_text` | str | ✅ | 空文字は `403 ERR_NO_CONSENT` |
| `audio` | file | ✅ | 参照用サンプル |
| `consent_audio` | file | `direct_recording` のみ✅ | 同意文のライブ録音（FR-003/009） |

処理順（この順序を守る。**先に落ちた検証のコードを返す**）:
1. サイズ 50MB 超 → `413 ERR_REQUEST_TOO_LARGE`
2. 形式照合（`domain/file_probe.validate_audio_file`。probeは `media/ffmpeg.make_probe()`）
   - `file_upload`: **WAV / MP3 のみ**許可。それ以外は `ERR_FILE_UNSUPPORTED_FORMAT`
   - `direct_recording`: ブラウザ録音コンテナ（webm / ogg / mp4 / wav）を許可。デコード不能は `ERR_FILE_CORRUPTED`
3. 長さ検証（`direct_recording` 10〜60秒 / `file_upload` 10〜180秒）→ `ERR_AUDIO_TOO_SHORT` / `ERR_AUDIO_TOO_LONG`
4. 正規化（`media/ffmpeg.normalize_to_reference_wav`、モノラル24kHz）。
   `file_upload` はさらに `detect_silence_ranges` → `select_reference_window` → `extract_reference_segment` で
   10〜30秒の参照区間を抽出（FR-107）
5. 品質検査（`domain/audio_quality.validate_audio_quality`、正規化後サンプルに対して実施）
   → `ERR_AUDIO_MOSTLY_SILENT` / `ERR_AUDIO_CLIPPING` / `ERR_AUDIO_LEVEL_OUT_OF_RANGE`

成功時 `200`:
```json
{
  "draft_id": "3f2a...-uuid",
  "duration_ms": 18240,
  "sample_rate": 24000,
  "channels": 1,
  "preview_url": "/api/voices/draft/3f2a...-uuid/audio"
}
```

*ドラフト試聴（FR-108）* `GET /api/voices/draft/{draft_id}/audio` → `200 audio/wav`、
未知IDは `404 ERR_DRAFT_NOT_FOUND`。ドラフトは `app.state.drafts`（プロセス内）と
`paths.temporary` の一時WAVで保持し、**永続化しない**。

*stage=confirm*

| フォーム項目 | 型 | 必須 | 内容 |
|---|---|---|---|
| `stage` | str | ✅ | `"confirm"` |
| `draft_id` | str | ✅ | validate で得たID。未知は `404 ERR_DRAFT_NOT_FOUND` |
| `consent_accepted` | str | ✅ | `"true"` 以外は `403 ERR_NO_CONSENT`（FR-004 の2回目確認） |
| `display_name` | str | 任意 | 既定 `"マイボイス"`。50文字上限。**ファイル名には使わない**（S-5） |

処理順:
1. 既存プロフィールあり → `409 ERR_PROFILE_ALREADY_EXISTS`（FR-110）
2. 正規化済み参照音声を `paths.references` へ `storage_path()` で保存
3. 同意録音（直接録音時）を `paths.consent` へ保存
4. `domain/consent.build_consent_record()` で同意記録を作成し、`VoiceProfile` 行を作成（FR-009/109）
5. 一時ファイル（元録音・アップロード元・ドラフト）を削除（FR-112）
6. テスト文生成ジョブを `queued` で作成し `JobQueue.submit()`（FR-111）

成功時 `201`:
```json
{
  "voice": {
    "id": "uuid", "display_name": "マイボイス",
    "source_mode": "file_upload", "source_format": "wav",
    "consent_method": "upload_declaration", "has_consent_audio": false,
    "created_at": "2026-08-10T04:00:00+00:00",
    "engine": "fake", "model_version": "fake-1"
  },
  "test_synthesis_id": "uuid"
}
```
**レスポンスに `reference_path` / `consent_audio_path` / 各SHA-256 を含めない**（S-7・S-9）。
テスト文は固定文字列 `"これはテスト用の音声です。声の確認にお使いください。"` とする。

**RED**:
| # | テスト関数名 | 検証内容 |
|---|---|---|
| 1 | `test_validate_rejects_missing_consent` | `consent_accepted="false"` → `403 ERR_NO_CONSENT` |
| 2 | `test_validate_rejects_recording_shorter_than_10s` | 5秒録音 → `422 ERR_AUDIO_TOO_SHORT` |
| 3 | `test_validate_rejects_recording_longer_than_60s` | 70秒録音 → `422 ERR_AUDIO_TOO_LONG` |
| 4 | `test_validate_rejects_upload_longer_than_180s` | 200秒アップロード → `422 ERR_AUDIO_TOO_LONG` |
| 5 | `test_validate_rejects_extension_spoofing` | 中身がテキストの `.wav` → `422 ERR_FILE_FORMAT_MISMATCH` または `ERR_FILE_CORRUPTED` |
| 6 | `test_validate_rejects_unsupported_upload_format` | `file_upload` に webm → `422 ERR_FILE_UNSUPPORTED_FORMAT` |
| 7 | `test_validate_rejects_silent_audio` | 無音WAV → `422 ERR_AUDIO_MOSTLY_SILENT` |
| 8 | `test_validate_rejects_clipping_audio` | 振幅1.0飽和WAV → `422 ERR_AUDIO_CLIPPING` |
| 9 | `test_validate_returns_playable_draft` | `200` / `draft_id` / `preview_url` を `GET` して `audio/wav` かつモノラル24kHz |
| 10 | `test_confirm_creates_single_profile_and_test_job` | `201` / DBにプロフィール1件 / `test_synthesis_id` のジョブが存在 |
| 11 | `test_confirm_removes_temporary_files` | 確定後 `paths.temporary` が空（FR-112） |
| 12 | `test_second_profile_is_rejected` | 2件目 `confirm` → `409 ERR_PROFILE_ALREADY_EXISTS`（FR-110） |
| 13 | `test_confirm_with_unknown_draft_returns_404` | `404 ERR_DRAFT_NOT_FOUND` |
| 14 | `test_response_does_not_leak_paths_or_hashes` | 応答本文に `reference_path` / `sha256` / `data_dir` の文字列が現れない（S-9） |
| 15 | `test_display_name_is_not_used_in_file_path` | `display_name="../../etc/passwd"` で確定しても保存先が `data_dir` 配下のUUID名（S-5） |
| 16 | `test_direct_recording_requires_consent_audio` | `consent_audio` 欠落 → `403 ERR_NO_CONSENT` |

**GREEN**: 既存ドメイン部品を順に呼ぶ薄いルータ。**判定ロジックをAPI層に再実装しない。**
**REFACTOR**: 検証呼び出し列の関数分割まで。
**検証**: `pytest tests/integration/test_voices_create_api.py -q`（FFmpeg必須）
**完了条件**: AC-02 / AC-03 / AC-04 のAPI側が成功。

---

### 2.4 T-304: プロフィール取得・削除API（3h）

**目的**: `GET /api/voices/current`、`DELETE /api/voices/current`（FR-113 / AC-09）。

**依存**: **T-303（同一ファイル `voices.py` のため順次）**
**所有ファイル**: `src/koeclone/api/voices.py`（取得・削除部を追記）, `tests/integration/test_voices_delete_api.py`

**API仕様**:
- `GET /api/voices/current` → `200` に T-303 の `voice` オブジェクトと同一形状。未作成は `404 ERR_PROFILE_NOT_FOUND`
- `DELETE /api/voices/current` → `204`（本文なし）。未作成は `404 ERR_PROFILE_NOT_FOUND`

削除は `storage/files.collect_deletion_targets()` → `delete_targets()` を使い、
参照音声・同意録音・キャッシュ・**関連する全生成音声とサイドカー**・一時ファイル・DB行（プロフィールと全ジョブ）を消す。

**RED**:
| # | テスト関数名 | 検証内容 |
|---|---|---|
| 1 | `test_get_current_returns_404_when_absent` | `404 ERR_PROFILE_NOT_FOUND` |
| 2 | `test_get_current_returns_profile_without_secrets` | `200` / パス・ハッシュを含まない |
| 3 | `test_delete_removes_profile_and_all_generated_files` | `204` 後、`data_dir` 配下に `.wav` / `.json` が1件も残らない |
| 4 | `test_delete_removes_database_rows` | 削除後 `get_current_voice_profile()` が `None`、`list_synthesis_jobs()` が空 |
| 5 | `test_endpoints_return_404_after_delete` | 削除後、`GET /api/voices/current`・`GET /api/syntheses/{id}`・`.../audio` が全て `404` |
| 6 | `test_delete_is_404_when_absent` | 未作成時 `404 ERR_PROFILE_NOT_FOUND` |

**GREEN**: 削除対象計算を呼ぶ最小実装。**REFACTOR**: なし。
**検証**: `pytest tests/integration/test_voices_delete_api.py -q`
**完了条件**: AC-09 のAPI側が成功。

---

### 2.5 T-305: 合成API（6h）

**目的**: プレビュー・ジョブ作成・状態取得・音声配信（FR-201〜218 / AC-05・06・07）。

**依存**: T-301
**所有ファイル**: `src/koeclone/api/syntheses.py`（preview / 作成 / 状態 / audio部）, `tests/integration/test_syntheses_api.py`

**共通の `override` 形（FR-214）**:
```json
{"surface": "日本橋", "start": 3, "end": 6, "reading": "にほんばし"}
```
`start` / `end` は **Unicodeコードポイント単位の半開区間**。

**`POST /api/syntheses/preview`**（`application/json`）
```json
{"text": "明日は日本橋へ行きます", "overrides": [{"surface":"日本橋","start":3,"end":6,"reading":"にほんばし"}]}
```
→ `200`
```json
{
  "synthesis_text": "明日はにほんばしへ行きます",
  "original_segments": [
    {"text": "明日は", "override_index": null},
    {"text": "日本橋", "override_index": 0},
    {"text": "へ行きます", "override_index": null}
  ],
  "synthesis_segments": [
    {"text": "明日は", "override_index": null},
    {"text": "にほんばし", "override_index": 0},
    {"text": "へ行きます", "override_index": null}
  ],
  "override_count": 1,
  "text_length": 11,
  "synthesis_text_length": 13
}
```
検証は `domain/text_validation.validate_text` → `domain/pronunciation.validate_pronunciation_overrides`
→ `domain/synthesis_text.build_synthesis_text` の順。失敗は §1.2 の 422 系コード。
**プレビューではエンジンを呼ばない。**

**`POST /api/syntheses`**（`application/json`）
```json
{"text": "...", "overrides": [], "ai_disclosure_acknowledged": true}
```
生成前検証の順序（**すべて通過するまでエンジンを呼ばない** = AC-07）:
1. プロフィール未作成 → `404 ERR_PROFILE_NOT_FOUND`
2. 同意記録なし → `403 ERR_NO_CONSENT`（FR-005）
3. `ai_disclosure_acknowledged != true` → `403 ERR_AI_DISCLOSURE_REQUIRED`
4. `validate_text` → 422系
5. `validate_pronunciation_overrides` → 422系
6. `build_synthesis_text`（2,000文字上限） → `422 ERR_SYNTHESIS_TEXT_TOO_LONG`

通過後、`SynthesisJob` 行を **`status="queued"`** で作成し（`text_sha256` / `synthesis_text_sha256` /
`pronunciation_overrides`(JSON文字列) / `language="ja"` を埋める）、`JobQueue.submit(job_id)` する。
→ `201`
```json
{"id": "uuid", "status": "queued", "created_at": "2026-08-10T04:00:00+00:00"}
```

**`GET /api/syntheses/{id}`** → `200`
```json
{
  "id": "uuid", "status": "succeeded",
  "created_at": "...", "completed_at": "...",
  "duration_ms": 4200, "watermark_detected": true,
  "error_code": null, "text_preview": "明日は日本橋へ行きます",
  "override_count": 1, "audio_available": true
}
```
`text_preview` は原文の**先頭80文字**（FR-302）。未知IDは `404 ERR_JOB_NOT_FOUND`。
`audio_available` は `status=="succeeded" and watermark_detected is True`。

**`GET /api/syntheses/{id}/audio`** → `200 audio/wav`
- ヘッダ `Content-Disposition: attachment; filename="koeclone_YYYYMMDD_HHMMSS_<short-id>.wav"`
  （`storage/files.download_filename()` を使用。FR-209）
- `status != "succeeded"` または `watermark_detected is not True` → `409 ERR_AUDIO_NOT_READY`（S-10）
- 未知ID → `404 ERR_JOB_NOT_FOUND`

**RED**:
| # | テスト関数名 | 検証内容 |
|---|---|---|
| 1 | `test_preview_applies_overrides_without_changing_original` | AC-06 の例で `synthesis_text == "明日はにほんばしへ行きます"`、`original_segments` の強調位置が正しい |
| 2 | `test_preview_rejects_invalid_reading` | 読みに漢字 → `422 ERR_READING_INVALID_CHARS` |
| 3 | `test_preview_does_not_call_engine` | `FakeEngine.calls == []` |
| 4 | `test_create_rejects_whitespace_only_text` | `422 ERR_TEXT_WHITESPACE_ONLY` かつ `FakeEngine.calls == []` |
| 5 | `test_create_rejects_text_over_1000_chars` | `422 ERR_TEXT_TOO_LONG` かつエンジン未呼出 |
| 6 | `test_create_rejects_synthesis_text_over_2000_chars` | `422 ERR_SYNTHESIS_TEXT_TOO_LONG` かつエンジン未呼出 |
| 7 | `test_create_rejects_overlapping_overrides` | `422 ERR_OVERRIDE_OVERLAP` かつエンジン未呼出 |
| 8 | `test_create_rejects_surface_mismatch` | `422 ERR_OVERRIDE_SURFACE_MISMATCH` かつエンジン未呼出 |
| 9 | `test_create_rejects_without_profile` | `404 ERR_PROFILE_NOT_FOUND` かつエンジン未呼出 |
| 10 | `test_create_rejects_without_ai_disclosure` | `403 ERR_AI_DISCLOSURE_REQUIRED` かつエンジン未呼出 |
| 11 | `test_create_and_complete_job_returns_wav` | `201` → 完了待ち → `GET .../audio` が `200 audio/wav`、`Content-Disposition` が FR-209 命名 |
| 12 | `test_audio_is_forbidden_while_queued_or_running` | 完了前は `409 ERR_AUDIO_NOT_READY` |
| 13 | `test_audio_is_forbidden_when_watermark_missing` | `FakeEngine(detect_result=False)` → ジョブ `failed`・`error_code=ERR_WATERMARK_NOT_DETECTED`・音声 `409`・WAV未残置（AC-08） |
| 14 | `test_unknown_job_returns_404` | `404 ERR_JOB_NOT_FOUND` |
| 15 | `test_status_exposes_text_preview_80_chars` | 100文字入力で `text_preview` が80文字 |

**GREEN**: 薄いルータ＋キュー投入。**REFACTOR**: レスポンス整形の共通化まで。
**検証**: `pytest tests/integration/test_syntheses_api.py -q`
**完了条件**: AC-05 / AC-06 / AC-07 のAPI側が成功。

---

### 2.6 T-306: 履歴API（3h）

**目的**: 一覧・個別削除・全削除（FR-301〜304）。

**依存**: **T-305（同一ファイル `syntheses.py` のため順次）**
**所有ファイル**: `src/koeclone/api/syntheses.py`（履歴部を追記）, `tests/integration/test_history_api.py`

**API仕様**:
- `GET /api/syntheses` → `200`
```json
{"items": [
  {"id":"uuid","created_at":"...","text_preview":"明日は…","override_count":1,
   "duration_ms":4200,"status":"succeeded","audio_available":true}
]}
```
**`created_at` の降順（新しい順）**。`text_preview` は原文先頭80文字（FR-302）。
- `DELETE /api/syntheses/{id}` → `204`。音声・サイドカー・DB行を削除。未知IDは `404 ERR_JOB_NOT_FOUND`
- `DELETE /api/syntheses` → `204`。全生成音声・全サイドカー・全ジョブ行を削除（**プロフィールは残す**）

**RED**:
| # | テスト関数名 | 検証内容 |
|---|---|---|
| 1 | `test_history_is_sorted_newest_first` | 3件作成し降順 |
| 2 | `test_history_item_fields_match_requirements` | 5項目（生成日時・原文先頭80文字・読み修正件数・音声長・状態）が揃う |
| 3 | `test_delete_single_removes_audio_and_sidecar` | `204` 後にWAV・JSON・DB行が消え、他ジョブは残る |
| 4 | `test_delete_all_removes_every_job_but_keeps_profile` | `204` 後に一覧が空、プロフィールは `200` |
| 5 | `test_delete_unknown_job_returns_404` | `404 ERR_JOB_NOT_FOUND` |

**GREEN**: 最小実装。**REFACTOR**: なし。
**検証**: `pytest tests/integration/test_history_api.py -q`

---

### 2.7 T-307: UI基盤・同意画面（4h）

**目的**: 画面骨格（同意→登録→合成→履歴）、初回同意画面、APIクライアント共通JS（FR-001/002 / AC-01）。

**依存**: T-301, T-302
**所有ファイル**:
```text
src/koeclone/web/index.html
src/koeclone/web/style.css
src/koeclone/web/js/app.js
src/koeclone/web/js/api.js
```

**要件**:
- 素のHTML / CSS / Vanilla JS のみ。**ビルド不要。外部CDN・外部フォント・外部画像を参照しない**（S-11）。
- 4つのセクション（`#consent` / `#register` / `#synthesis` / `#history`）をタブ切替。
- 同意画面に「本人の声のみ登録可能」「禁止用途」を明示表示（FR-001）。
- **同意チェックが完了するまで、登録セクションの録音ボタン・ファイル選択を `disabled` にする**（FR-002 / AC-01）。
  同意状態は `sessionStorage` に保持（永続化しない）。
- `api.js` は共通関数を提供する（他タスクはこれを使う）:
  ```js
  export async function apiGet(path)
  export async function apiJson(method, path, body)
  export async function apiForm(path, formData)   // multipart
  export function errorMessage(error)             // {code,message} → 表示文字列
  ```
  非2xxは `{code, message}` を持つ例外にして投げる。**エラーは必ず画面に表示し、握りつぶさない。**
- アクセシビリティ: 各入力に `<label for>`、エラー表示に `role="alert"`、
  フォーカスリングを消さない（`:focus-visible` を残す）。

**検証**: `pytest tests/integration/test_app.py -q`（静的配信が通ること。**既存テストを壊さない**）
＋ 下記の手動確認手順を**報告に含める**（実行はClaude）:
1. `./scripts/run.sh` を起動し `http://127.0.0.1:8000/` を開く
2. 同意前: 録音ボタンとファイル選択が押せないことを確認
3. 同意チェック後: 両方が有効化されることを確認
4. リロード後も同一セッション内では同意状態が保持されることを確認

**完了条件**: 同意前に登録UIが無効であることをClaudeが手動確認。
**注**: 本タスクの自動検証はT-313のE2Eで行う（実装計画T-307の方針どおり）。

---

### 2.8 T-308: 直接録音UI（6h）

**目的**: マイク権限、同意文表示、録音操作、2段階登録フロー（FR-102/103/108 / AC-02）。

**依存**: T-307, T-303
**所有ファイル**: `src/koeclone/web/js/record.js`

**要件**:
- `GET /api/consent/challenge` の同意文を画面に表示し、**その文を読み上げて録音**させる。
- `navigator.mediaDevices.getUserMedia({audio:true})` → `MediaRecorder`。
  権限拒否（`NotAllowedError`）時は復旧手順（ブラウザ設定からマイクを許可する手順）を表示する。
- 録音開始 / 経過時間の秒表示 / 停止 / 試聴 / 破棄 / 再録音を提供。
- **クライアント側で10〜60秒の範囲外を事前に警告**するが、**最終判定はサーバー**。
- フロー: 録音 → `POST /api/voices`(`stage=validate`) → `preview_url` を `<audio>` で試聴
  → 「この声で確定」→ `POST /api/voices`(`stage=confirm`) → テスト音声のジョブIDを T-311 の進行表示へ渡す。
- サーバーのエラーコードを日本語メッセージで表示し、**再録音への導線を必ず出す**（AC-04）。
- 副作用のない純関数（経過時間整形・長さ判定・エラーコード→メッセージ）を分離して実装する。

**検証**: T-313 のE2E（Playwright の偽メディアストリーム `--use-fake-device-for-media-stream`）＋手動確認
**完了条件**: AC-02 のUIフローがE2Eで成功。

---

### 2.9 T-309: アップロードUI（4h）

**目的**: WAV/MP3登録と2回の権利確認（FR-104 / FR-004 / AC-03）。

**依存**: T-307, T-303
**所有ファイル**: `src/koeclone/web/js/upload.js`

**要件**:
- `<input type="file" accept=".wav,.mp3,audio/wav,audio/mpeg">`。
- **権利確認は2回**: ①アップロード前 ②登録確定前（FR-004）。各回チェックしないと次へ進めない。
- クライアント事前チェック: 50MB超・拡張子不一致は送信前に警告（**最終判定はサーバー**）。
- フロー: 選択 → 確認① → `stage=validate` → 正規化後音声を試聴 → 確認② → `stage=confirm`。
- 試聴画面から「破棄」「別のファイルを選ぶ」を提供（FR-108）。
- 拒否時はサーバーのエラーコードに対応する具体的な対処（別ファイル選択・録り直し）を表示（AC-04）。

**検証**: T-313 のE2E ＋手動確認
**完了条件**: AC-03 のUIフローがE2Eで成功。

---

### 2.10 T-310: テキスト入力・読み修正モードUI（6h）

**目的**: モード切替・範囲選択・読み修正管理・プレビュー（FR-210〜215 / AC-06）。

**依存**: T-307, T-305
**所有ファイル**: `src/koeclone/web/js/synthesis.js`（入力・修正部）

**要件**:
- 「通常モード」「読み修正モード」のトグル。通常モードでは読み修正を送信しない（FR-218）。
- 読み修正モード: 原文の範囲を選択 → 読みを入力 → 一覧へ追加。
  範囲は **Unicodeコードポイント単位**で算出する（サロゲートペア対策に `Array.from(text)` を使い、
  `String.prototype.length` に依存しない）。
- 一覧で各修正の**追加・編集・削除**が可能（FR-215）。
- `POST /api/syntheses/preview` を呼び、`original_segments` の強調表示と `synthesis_text` を表示。
- 文字数カウンタ（原文 /1,000、合成用 /2,000）を表示。
- 「**AI生成音声として利用する**」チェックを必須にし、未チェックでは生成ボタンを `disabled`。
- 生成は `POST /api/syntheses`（`ai_disclosure_acknowledged: true`）。

**検証**: T-313 のE2E ＋手動確認
**完了条件**: AC-06 のUIフローがE2Eで成功。

---

### 2.11 T-311: 進行表示・プレイヤー・ダウンロードUI（4h）

**目的**: 1秒間隔のポーリング、再生、ダウンロード（FR-205/208/209）。

**依存**: **T-310（同一ファイル `synthesis.js` のため順次）**
**所有ファイル**: `src/koeclone/web/js/synthesis.js`（進行・再生部を追記）

**要件**:
- `GET /api/syntheses/{id}` を **1秒間隔**でポーリングし `queued` / `running` / `succeeded` / `failed` を表示。
  `succeeded` / `failed` で**必ずポーリングを停止**する（リーク禁止）。
- `failed` 時は利用者向けメッセージと `error_id`（あれば）を表示し、**部分音声を再生可能にしない**（FR-206）。
- `succeeded` 時のみ `<audio controls>` を表示（再生・一時停止・シーク・音量＝ブラウザ標準コントロールで可）。
- ダウンロードは `GET /api/syntheses/{id}/audio` へのリンク。**ファイル名はサーバーの
  `Content-Disposition` に従う**（クライアントで名前を組み立てない。FR-209）。

**検証**: T-313 のE2E ＋手動確認
**完了条件**: AC-05 のUI側がE2Eで成功。

---

### 2.12 T-312: 履歴UI（3h）

**目的**: 一覧・再生・DL・個別削除・全削除（FR-301〜304 / UC-03）。

**依存**: T-307, T-306
**所有ファイル**: `src/koeclone/web/js/history.js`

**要件**:
- `GET /api/syntheses` を表示（新しい順、5項目）。
- 各行に再生・ダウンロード・削除。`audio_available === false` の行は再生・DLを `disabled`。
- 「すべて削除」は**確認ダイアログ**を経てから `DELETE /api/syntheses`。
- 削除後は一覧を再取得して反映。

**検証**: T-313 のE2E ＋手動確認
**完了条件**: 履歴フローがE2Eで成功。

---

### 2.13 T-313: E2Eテスト（8h）

**目的**: 主要フローをPlaywrightで自動化。

**依存**: T-307〜T-312（Playwright導入はClaudeが事前実施 §0.2）
**所有ファイル**: `tests/e2e/`（配下全ファイル）

**前提**: サーバーは **`FakeEngine`（`KOECLONE_ENGINE=fake`）** と一時 `KOECLONE_DATA_DIR` で起動する。
**実在人物の音声fixtureを使わない**（プログラム生成音声・偽メディアストリームのみ）。

**必須シナリオ**:
| # | シナリオ | 対応AC |
|---|---|---|
| 1 | 同意前は録音・アップロードが不可 → 同意後に有効化 | AC-01 |
| 2 | 直接録音（偽メディアストリーム）で validate → 試聴 → confirm → テスト音声再生 | AC-02 |
| 3 | WAVアップロードで2回の権利確認 → validate → 試聴 → confirm | AC-03 |
| 4 | MP3アップロードで同上 | AC-03 |
| 5 | 不正音声（無音）の拒否と再選択導線の表示 | AC-04 |
| 6 | 通常モードで生成 → 進行表示 → 再生 → ダウンロード | AC-05 |
| 7 | 読み修正モードでプレビュー確認 → 生成（原文が変わらないこと） | AC-06 |
| 8 | AI生成確認チェックなしでは生成ボタンが押せない | AC-07 |
| 9 | 履歴の個別削除と全削除 | FR-303/304 |
| 10 | プロフィール完全削除後、履歴・音声が取得できない | AC-09 |

**RED**: 各シナリオを先に書き、UI未完部分の失敗を確認しながら T-307〜T-312 と往復する。
**GREEN**: セレクタ・待機の最小実装。**固定 `sleep` を使わず、条件待ち（`expect`/`wait_for`）を使う。**
**REFACTOR**: Page Object化まで。
**検証**: `pytest tests/e2e -q`
**完了条件**: 全シナリオ成功。

---

## 3. 起動コマンド（M4 Mac ローカル）

```bash
# 依存の同期（Claudeが実施済みの想定）
uv sync

# 本番相当（実モデル。初回はモデル取得のためネットワークが必要）
./scripts/run.sh
# → http://127.0.0.1:8000/ をブラウザで開く

# 偽エンジン（UI確認・E2E用。モデルをロードしない）
KOECLONE_ENGINE=fake KOECLONE_DATA_DIR="$PWD/tmp/e2e-data" ./scripts/run.sh

# ポート変更
KOECLONE_PORT=8123 ./scripts/run.sh

# 開発時のみ OpenAPI を見る（既定は無効）
KOECLONE_DOCS=1 ./scripts/run.sh
```

| 環境変数 | 既定 | 用途 |
|---|---|---|
| `KOECLONE_ENGINE` | `chatterbox` | `fake` で偽エンジン |
| `KOECLONE_DATA_DIR` | `~/koeclone-data` | データ保存先 |
| `KOECLONE_PORT` | `8000` | 待受ポート |
| `KOECLONE_ALLOW_CPU_FALLBACK` | `false` | MPS失敗時のCPU許可 |
| `KOECLONE_DOCS` | 未設定（無効） | OpenAPI有効化（開発時のみ） |

**ホストを変更する環境変数は存在しない（S-1）。**

---

## 4. G3 受入条件（Claudeが判定）

`docs/implementation-plan.md` §7「ゲート G3: API統合テストと主要E2Eが全件成功。Claudeが手動でUC-01〜03を通しで確認」を判定基準とし、下記をすべて満たすこと。

| # | 受入条件 | 検証方法 |
|---|---|---|
| 1 | T-301〜T-306 の全API統合テストが成功 | `pytest tests/integration -q` |
| 2 | 全体回帰に劣化がない | `pytest -q`（Phase 2 の 177 passed を下回らない。skipは実モデル6件のみ） |
| 3 | 通常実行で実モデルをロードしない | `pytest -q` の実行時間が数秒以内 |
| 4 | 静的解析クリーン | `ruff check .` → 指摘ゼロ |
| 5 | E2E 10シナリオが全件成功 | `pytest tests/e2e -q` |
| 6 | UC-01（プロフィール作成）を手動で通し確認 | Claudeがブラウザで実施 |
| 7 | UC-02（テキスト読み上げ）を手動で通し確認 | Claudeがブラウザで実施 |
| 8 | UC-03（データ削除）を手動で通し確認 | Claudeがブラウザで実施 |
| 9 | AC-01〜AC-10 のAPI/UI側が満たされている | 突合表をClaudeが作成 |
| 10 | セキュリティ条件 S-1〜S-11 に違反がない | Claudeがコードレビューで確認（自動テストはT-401で追加） |
| 11 | 各タスクレビューで Blocking / Major 指摘ゼロ | Claudeのレビュー記録 |

判定結果は `docs/gate-records.md` に追記する。

---

## 5. 仕様との差分（Claudeが承認済み。Codexは勝手に増やさない）

| # | 差分 | 理由 |
|---|---|---|
| 1 | `GET /api/voices/draft/{draft_id}/audio` を追加（仕様§9の12エンドポイントに含まれない） | FR-108「登録確定前に正規化後の参照音声を試聴できる」を実現するために必要な `/api/voices` のサブリソース。**新機能ではなく既存要件の実装手段**。ドラフトはプロセス内保持で永続化しない |
| 2 | `ErrorCode` に7件追加（§2.1） | 仕様§7.4「全APIエラーは安定したエラーコードを持つ」を満たすために必要。既存コードは変更しない |
| 3 | `AppConfig` に `engine` / `app_version` を追加 | 偽エンジン切替（テスト・E2E必須）と同意記録の `app_version`（FR-009）に必要 |

上記3件以外の追加・変更は**契約違反**として差戻す。
