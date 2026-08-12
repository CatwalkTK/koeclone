# タスク契約 Phase 3: API・UI・E2E（T-301〜T-313 統合契約）

| 項目 | 内容 |
|---|---|
| 契約ID | PHASE3（T-301〜T-314 の統合契約） |
| 文書所有者 | Claude（唯一の指揮官）。本文書の変更はClaudeのみが行う |
| 実装担当 | Codex |
| 上位文書 | `docs/implementation-plan.md` §7 Phase 3 / §8、`docs/system-specification.md` §6・§7・§9・§10・§11 |
| 参照文書 | `docs/gate-records.md` §1（G2判定）、`docs/task-contract-phase1.md`、`docs/task-contract-phase2.md` |
| 前提ゲート | **G2 合格済み**（2026-08-10 / HEAD `7fc2423` / `pytest -q` 177 passed・6 skipped、`ruff check .` 指摘ゼロ、実モデル契約 5 passed・1 skipped） |
| ブランチ | `agent/phase3-api-ui`（**Git操作は全てClaudeが実施。Codexはgitコマンドを一切実行しない**） |
| 見積 | 合計63h（T-301 4h / T-302 1h / T-303 8h / T-304 3h / T-305 6h / T-306 3h / T-307 4h / T-308 6h / T-309 4h / T-310 6h / T-311 4h / T-312 3h / T-313 8h / **T-314 3h**（改訂4で追加）） |

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
                    └→ T-314（プロフィール削除UI。T-304・T-313完了後 / 改訂4で追加）
```

**並行可能な組み合わせ**（互いに素なファイルのみ）:

| 段 | 並行可能なタスク |
|---|---|
| 1 | T-301（単独。最初に必ず完了させる） |
| 2 | {T-302} / {T-303→T-304} / {T-305→T-306} の3系列を並行可 |
| 3 | T-307（単独） |
| 4 | {T-308} / {T-309} / {T-310→T-311} / {T-312} の4系列を並行可 |
| 5 | T-313（単独） |
| 6 | T-314（単独。G4 判定前に完了させる） |

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
| 404 | `ERR_PROFILE_NOT_FOUND`, `ERR_JOB_NOT_FOUND`, `ERR_DRAFT_NOT_FOUND`, `ERR_ROUTE_NOT_FOUND` |
| 405 | `ERR_ROUTE_NOT_FOUND` |
| 409 | `ERR_PROFILE_ALREADY_EXISTS`, `ERR_AUDIO_NOT_READY` |
| 413 | `ERR_REQUEST_TOO_LARGE` |
| 422 | `ERR_TEXT_EMPTY`, `ERR_TEXT_TOO_LONG`, `ERR_TEXT_WHITESPACE_ONLY`, `ERR_SYNTHESIS_TEXT_TOO_LONG`, `ERR_READING_EMPTY`, `ERR_READING_INVALID_CHARS`, `ERR_OVERRIDE_RANGE_INVALID`, `ERR_OVERRIDE_SURFACE_MISMATCH`, `ERR_OVERRIDE_OVERLAP`, `ERR_OVERRIDE_NO_KANJI`, `ERR_AUDIO_TOO_SHORT`, `ERR_AUDIO_TOO_LONG`, `ERR_AUDIO_MOSTLY_SILENT`, `ERR_AUDIO_CLIPPING`, `ERR_AUDIO_LEVEL_OUT_OF_RANGE`, `ERR_FILE_TOO_LARGE`, `ERR_FILE_FORMAT_MISMATCH`, `ERR_FILE_CORRUPTED`, `ERR_FILE_NO_AUDIO`, `ERR_FILE_UNSUPPORTED_FORMAT` |
| 500 | `ERR_INTERNAL`, `ERR_WATERMARK_NOT_DETECTED`（API直接返却はせず、ジョブの `error_code` として保持） |

**`ERR_ROUTE_NOT_FOUND` の用途（限定）**: 存在しないパス、および既知パスへの許可されないメソッド**専用**。
リソース不在（プロフィール・ジョブ・ドラフト）には使わず、必ず個別コードを返す。
Starlette/FastAPI 既定の `{"detail": ...}` 応答を**そのまま返さない**。
未処理の `StarletteHTTPException` は例外ハンドラで §1.1 の形状へ変換する
（404・405 は `ERR_ROUTE_NOT_FOUND`。**405 は元の状態コード 405 を維持し、404 へ丸めない**。
それ以外の未マップ状態コードは `500 ERR_INTERNAL` として扱う）。

**catch-all**: 上記いずれのハンドラにも該当しない**未捕捉例外（`Exception`）も §1.1 の形状に統一する**。
`500 ERR_INTERNAL` ＋ UUID4 の `error_id` を返し、Starlette 既定のプレーンテキスト
`Internal Server Error` や例外文言・スタックトレースを応答本文に一切含めない（S-9）。
`error_id` と `ErrorCode` のみをサーバーログに1行記録する（S-7）。

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
def create_app(
    config: AppConfig,
    *,
    engine: SpeechEngine,
    docs_enabled: bool = False,
    web_dir: Path | None = None,   # 既定は src/koeclone/web。テストは tmp_path を渡す
) -> FastAPI: ...
def create_default_app() -> FastAPI: ...  # 環境変数から構築。uvicorn --factory 用
```

#### ルータ登録機構（T-301 が実装。T-302 以降は `app.py` を変更しない）

`create_app` は以下の**固定リスト**を順に走査し、モジュールが存在すれば登録する。

```python
_ROUTER_MODULES = ("consent", "voices", "syntheses")   # この3件で固定。増減しない

for name in _ROUTER_MODULES:
    if importlib.util.find_spec(f"koeclone.api.{name}") is None:
        continue                                   # 未実装タスクの分は飛ばす
    module = importlib.import_module(f"koeclone.api.{name}")
    app.include_router(module.router, prefix="/api")
```

- `find_spec` が `None` を返すのは**ファイルが存在しないときだけ**。
  モジュール内部の import エラー・構文エラーは**握り潰さず伝播させる**
  （`try/except ImportError` で囲まない。ルータが黙って無効化される事故を防ぐ）。
- **各ルータモジュールはモジュール直下に `router: APIRouter` を公開する**。
  パスは `/api` を**含めずに**定義する（例: `@router.get("/consent/challenge")` → 実パス `/api/consent/challenge`）。
- **登録順序**: `/api/health` → 上記ルータ群 → **最後に** `StaticFiles` を `/` へマウント。
  Starlette は定義順にマッチし `Mount("/")` は全パスに一致するため、
  **静的マウントより後に追加したルートは到達不能**になる。テストで一時ルートを足す場合も
  `app.router.routes.insert(0, ...)` で先頭に挿入する。

#### `app.state.queue` の初期化（T-301 が実装）

`JobQueue` のハンドラは `job_id` のみを受け取るため、T-301 は
「DB からジョブ行を読み、`SynthesisRequest` を組み立てて `pipeline.run()` を呼ぶ」
薄いハンドラを `app.py` に実装する。

- `pronunciation_overrides`（JSON文字列）を `tuple[PronunciationOverride, ...]` に復元する。
- 対象ジョブが存在しない場合は `KoecloneError(ERR_JOB_NOT_FOUND)` を送出する
  （`JobQueue` 側が `failed` へ遷移させる）。
- `create_app` の中で `queue.start()` を呼ぶ。**lifespan イベントに依存しない**
  （`TestClient` を `with` なしで使うテストでもジョブが処理されるようにするため）。

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

`VoiceDraft` は **T-303 が `src/koeclone/api/voices.py` に定義する**（§2.3.1）。
`app.py` は空辞書 `{}` を置くだけで `VoiceDraft` を import しない（T-301 実装済み。**T-303 は `app.py` を変更しない**）。

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

**`errors.py` へ追加する列挙子（この8件のみ。既存は一切変更しない）**:

```python
ERR_BAD_REQUEST = "ERR_BAD_REQUEST"
ERR_ROUTE_NOT_FOUND = "ERR_ROUTE_NOT_FOUND"
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
| 4 | `test_error_response_shape_is_stable` | 未知パス `GET /api/unknown` が `404` / `error.code == "ERR_ROUTE_NOT_FOUND"` / `{"error":{"code","message","error_id"}}` 形状（`error_id` は `null`）。`detail` キーを含まない |
| 5 | `test_internal_error_hides_details_and_returns_error_id` | 意図的に `KoecloneError(ERR_INTERNAL)` を投げるテスト用ルートで `500` / `error_id` がUUID / メッセージに例外文言・パスを含まない（S-9） |
| 6 | `test_openapi_is_disabled_by_default` | `GET /openapi.json` と `GET /docs` が `404`。`docs_enabled=True` では `200`（S-8） |
| 7 | `test_static_web_directory_is_served` | `create_app(..., web_dir=tmp_path)` に `index.html` を置き、`GET /` が `200` かつ `text/html`。**リポジトリ内の `src/koeclone/web/` にファイルを作らない**（T-307 の所有領域） |
| 8 | `test_invalid_uuid_path_becomes_bad_request` | **テスト専用ルート** `GET /api/_test/uuid/{value}`（`value: uuid.UUID`）をテスト内で `app.router.routes.insert(0, ...)` により登録し、`not-a-uuid` が `400 ERR_BAD_REQUEST`（§1.3）。**`/api/syntheses/*` の仮ルートを作らない**（T-305 の所有領域） |
| 9 | `test_run_script_binds_loopback_only` | `scripts/run.sh` が `127.0.0.1` を含み、`0.0.0.0` と `--host` の外部指定を含まない（S-1） |
| 10 | `test_app_config_host_cannot_be_overridden_by_env` | `KOECLONE_HOST=0.0.0.0` を設定しても `AppConfig.from_env().host == "127.0.0.1"`（S-1） |
| 11 | `test_request_body_limit_stops_spoofed_stream` | **`Content-Length` 詐称**（小さい値を宣言し実body を上限超まで送る）で `413 ERR_REQUEST_TOO_LARGE`。生ASGI呼び出しでボディをストリーム送出し、**実受信バイト数が上限＋1チャンク以内で打ち切られる**ことを確認する（S-3） |
| 12 | `test_method_not_allowed_keeps_405_status` | 既知パスへの許可されないメソッド（例 `POST /api/health`）が **`405`**（404 に丸めない）／`error.code == "ERR_ROUTE_NOT_FOUND"`（§1.2） |
| 13 | `test_unexpected_error_uses_stable_internal_shape` | `KoecloneError` 以外の未捕捉例外（内部パス文字列を含む `RuntimeError`）を投げるテスト用ルートで `500` / `ERR_INTERNAL` / `error_id` がUUID / **応答本文に例外文言・内部パスが現れない**（§1.2 catch-all・S-9） |

**GREEN**: 最小のアプリファクトリ（§1.6 のルータ登録機構・`queue.start()` を含む）、
`KoecloneError` → JSON のグローバル例外ハンドラ、
`RequestValidationError` → `400 ERR_BAD_REQUEST` ハンドラ、
`StarletteHTTPException` → §1.1 形状ハンドラ（404/405 は `ERR_ROUTE_NOT_FOUND`。405 は元status維持）、
`Exception` → `500 ERR_INTERNAL` の catch-all ハンドラ（§1.2）、
サイズ制限ミドルウェア（`Content-Length` と**実受信バイト数の両方**で計測し、超過時はボディ読取を打ち切る。
FastAPI の `BaseHTTPMiddleware` ではボディ全体を先に読んでしまうため、**純ASGIミドルウェアとして実装する**）、
`StaticFiles(directory=web_dir, html=True)` を `/` へ**最後にマウント**（`/api/*` を先に登録）。

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
1. サイズ 50MB 超 → `413 ERR_REQUEST_TOO_LARGE`（T-301 のミドルウェアが処理済み。ルータでは実装しない）
2. 形式照合（**モードで使う部品が異なる。§2.3.1-C を正とする**）
   - `file_upload`: `domain/file_probe.validate_audio_file`（probe は `media/ffmpeg.make_probe()`）。
     **WAV / MP3 のみ**許可。それ以外は `ERR_FILE_UNSUPPORTED_FORMAT`
   - `direct_recording`: `validate_audio_file` は **使わない**（WAV/MP3専用のため）。
     MIME許可表 → `media/ffmpeg.probe_audio` の順で判定する。デコード不能は `ERR_FILE_CORRUPTED`
3. 長さ検証（`direct_recording` 10〜60秒 / `file_upload` 10〜180秒）→ `ERR_AUDIO_TOO_SHORT` / `ERR_AUDIO_TOO_LONG`
   （`file_upload` は 2 の `validate_audio_file` が同時に判定する。`direct_recording` は §2.3.1-C で個別に判定する）
4. 正規化（`media/ffmpeg.normalize_to_reference_wav`、モノラル24kHz）。
   `file_upload` はさらに `detect_silence_ranges` → `select_reference_window` → `extract_reference_segment` で
   10〜30秒の参照区間を抽出（FR-107）
5. 品質検査（`domain/audio_quality.validate_audio_quality`、正規化後サンプルに対して実施。
   サンプル読み出し規約は §2.3.1-E）
   → `ERR_AUDIO_MOSTLY_SILENT` / `ERR_AUDIO_CLIPPING` / `ERR_AUDIO_LEVEL_OUT_OF_RANGE`

**完全な処理順（`consent_audio` と不正値の扱いを含む）は §2.3.1-B を正とする。**

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
| 11 | `test_confirm_removes_temporary_files` | 確定後 `paths.temporary` が空（FR-112）。**テスト文ジョブが `paths.temporary` に作業ディレクトリを作るため、`app.state.queue.wait_for(test_synthesis_id)` で終了を待ってから検査する**（待たないと競合で不安定になる） |
| 12 | `test_second_profile_is_rejected` | 2件目 `confirm` → `409 ERR_PROFILE_ALREADY_EXISTS`（FR-110） |
| 13 | `test_confirm_with_unknown_draft_returns_404` | `404 ERR_DRAFT_NOT_FOUND` |
| 14 | `test_response_does_not_leak_paths_or_hashes` | 応答本文に `reference_path` / `sha256` / `data_dir` の文字列が現れない（S-9） |
| 15 | `test_display_name_is_not_used_in_file_path` | `display_name="../../etc/passwd"` で確定しても保存先が `data_dir` 配下のUUID名（S-5） |
| 16 | `test_direct_recording_requires_consent_audio` | `consent_audio` 欠落 → `403 ERR_NO_CONSENT` |
| 17 | `test_unknown_stage_is_bad_request` | `stage="publish"` → `400 ERR_BAD_REQUEST`（§2.3.1-F） |
| 18 | `test_display_name_over_50_chars_is_rejected` | 51コードポイントの `display_name` で `confirm` → `400 ERR_BAD_REQUEST`（§2.3.1-F） |
| 19 | `test_upload_mode_rejects_consent_audio` | `file_upload` に `consent_audio` を付与 → `400 ERR_BAD_REQUEST`（§2.3.1-F） |

**GREEN**: 既存ドメイン部品を順に呼ぶ薄いルータ。**判定ロジックをAPI層に再実装しない。**
**REFACTOR**: 検証呼び出し列の関数分割まで。
**検証**: `pytest tests/integration/test_voices_create_api.py -q`（FFmpeg必須）
**完了条件**: AC-02 / AC-03 / AC-04 のAPI側が成功。

---

### 2.3.1 T-303 実装詳細（改訂3で確定。本節が T-303 の正）

本節は §2.3 を置き換えるものではなく、**§2.3 で未定義だった箇所を確定させる**。
§2.3 と本節が矛盾する場合は**本節を正**とする。
本節の実装は **`domain/**` / `storage/**` / `media/**` / `worker/**` / `api/app.py` を一切変更せずに完結する**
（使用する既存関数は §2.3.1-H に列挙。すべて現行シグネチャのまま呼べることを Claude が確認済み）。

#### A. `VoiceDraft` の定義（`src/koeclone/api/voices.py` に置く）

```python
@dataclass(frozen=True)
class VoiceDraft:
    draft_id: str                      # UUID4文字列。app.state.drafts のキーと同一
    source_mode: str                   # "direct_recording" | "file_upload"
    source_format: str                 # "wav" | "mp3" | "webm" | "ogg" | "mp4"
    source_sha256: str                 # 受信した元バイト列のSHA-256（FR-109「元音声SHA-256」）
    reference_path: Path               # paths.temporary 配下の正規化済み参照WAV（試聴もこれを返す）
    duration_ms: int                   # reference_path の長さ
    sample_rate: int                   # reference_path の実サンプリング周波数（24000）
    channels: int                      # reference_path の実チャンネル数（1）
    consent_text: str
    consent_method: ConsentMethod      # domain/consent.ConsentMethod
    consent_audio_path: Path | None    # paths.temporary 配下の正規化済み同意WAV（direct_recordingのみ）
    temporary_paths: tuple[Path, ...]  # confirm時に削除する全一時ファイル（上記2つを含む）
```

- **`reference_sha256` / `consent_audio_sha256` はドラフトに持たない。** confirm 時に
  **最終保存先のファイルから計算する**（保存前後でのハッシュ齟齬を構造的に排除するため）。
- ドラフトは `app.state.drafts[draft_id] = draft` で保持し、**永続化しない**。
  confirm 成功時に `del app.state.drafts[draft_id]` する。TTL・件数上限は設けない
  （単一利用者ローカルアプリのため。**新機能を足さない**）。

#### B. `stage=validate` の完全な処理順（この順序を守る）

| # | 処理 | 失敗時 |
|---|---|---|
| 1 | `stage` が `"validate"` / `"confirm"` 以外 | `400 ERR_BAD_REQUEST` |
| 2 | `source_mode` が `"direct_recording"` / `"file_upload"` 以外 | `400 ERR_BAD_REQUEST` |
| 3 | `consent_accepted.strip().casefold() != "true"` | `403 ERR_NO_CONSENT` |
| 4 | `consent_text.strip() == ""` | `403 ERR_NO_CONSENT` |
| 5 | `direct_recording` かつ `consent_audio` 欠落（またはバイト長0） | `403 ERR_NO_CONSENT`（RED#16） |
| 6 | `file_upload` かつ `consent_audio` が付与されている | `400 ERR_BAD_REQUEST`（RED#19） |
| 7 | `audio` の許可判定（§2.3.1-C の表） | `422 ERR_FILE_UNSUPPORTED_FORMAT` |
| 8 | 一時保存（§2.3.1-D）してサイズ確認 | `422 ERR_FILE_TOO_LARGE` |
| 9 | 形式・長さ検証（§2.3.1-C） | 各 `ERR_FILE_*` / `ERR_AUDIO_TOO_SHORT` / `ERR_AUDIO_TOO_LONG` |
| 10 | 正規化（`file_upload` は参照区間抽出まで。§2.3.1-C） | `500 ERR_INTERNAL` |
| 11 | `consent_audio` の検証・正規化（`direct_recording` のみ。§2.3.1-G） | §2.3.1-G の表 |
| 12 | 品質検査 `validate_audio_quality`（§2.3.1-E） | `422 ERR_AUDIO_*` |
| 13 | `VoiceDraft` を組み立てて `app.state.drafts` へ登録し `200` を返す | — |

**失敗した場合は、その時点までに作成した一時ファイルを削除してからエラーを返す**
（`try/finally` ではなく明示的な削除で可。`paths.temporary` に失敗残骸を残さない）。

#### C. 形式・長さ検証（モード別。ここが §2.3 の矛盾点の裁定）

**許可表**（`declared_mime` は `;` 以降を落とし `strip().casefold()` して比較する。
ブラウザは `audio/webm;codecs=opus` のように送るため）:

| `source_mode` | 拡張子の扱い | 許可する MIME | `source_format` |
|---|---|---|---|
| `file_upload` | `.wav` / `.mp3` のみ許可（`Path(filename).suffix.casefold()`。それ以外・空は `ERR_FILE_UNSUPPORTED_FORMAT`） | `audio/wav`, `audio/wave`, `audio/x-wav` / `audio/mpeg`, `audio/mp3` | `"wav"` / `"mp3"` |
| `direct_recording` | **判定に使わない**（ブラウザ録音にファイル名が無いため） | `audio/webm`, `video/webm`, `audio/ogg`, `application/ogg`, `audio/mp4`, `video/mp4`, `audio/wav`, `audio/wave`, `audio/x-wav` | MIMEサブタイプから `"webm"` / `"ogg"` / `"mp4"` / `"wav"` |

**`file_upload`（既存関数をそのまま使う）**

```python
error = validate_audio_file(
    temp_path,                 # 拡張子は .wav / .mp3（§2.3.1-D）
    declared_mime,             # ; 以降を落とした値
    make_probe(),              # media/ffmpeg.make_probe()
    config=request.app.state.config,
)
if error is not None:
    raise KoecloneError(error)
```
サイズ・拡張子・シグネチャ・MIME・probe・音声トラック有無・コーデック・長さ（10〜180秒）を
**この1回の呼び出しがすべて判定する**。API層で再実装しない。

**`direct_recording`（`validate_audio_file` は使えない。以下の順で判定する）**

| # | 判定 | 失敗時 |
|---|---|---|
| 1 | `temp_path.stat().st_size > config.max_upload_bytes` | `ERR_FILE_TOO_LARGE` |
| 2 | `probe_audio(temp_path)` が `OSError` / `ValueError` を送出 | `ERR_FILE_CORRUPTED` |
| 3 | `result.encrypted` | `ERR_FILE_CORRUPTED` |
| 4 | `not result.has_audio` | `ERR_FILE_NO_AUDIO` |
| 5 | `result.duration_seconds is None or <= 0` | `ERR_FILE_CORRUPTED` |
| 6 | `duration_seconds < config.direct_recording_seconds[0]`（10.0） | `ERR_AUDIO_TOO_SHORT` |
| 7 | `duration_seconds > config.direct_recording_seconds[1]`（60.0） | `ERR_AUDIO_TOO_LONG` |

**コーデック名の照合は行わない**（webm/ogg/mp4 の中身は opus / vorbis / aac と多様なため。
デコード可能であることを probe が保証すれば足りる）。

**正規化**

- 共通: `normalize_to_reference_wav(temp_source, normalized_path)`（モノラル24kHz・`pcm_s16le`）。
- `direct_recording`: これで確定。`reference_path = normalized_path`。
- `file_upload`（FR-107）:
  ```python
  total_seconds = wav_duration_ms(normalized_path) / 1000
  if total_seconds < 10.0:                      # 正規化での端数落ちを吸収
      raise KoecloneError(ErrorCode.ERR_AUDIO_TOO_SHORT)
  ranges = detect_silence_ranges(normalized_path)
  start, duration = select_reference_window(total_seconds, ranges)
  extract_reference_segment(
      normalized_path, reference_path,
      start_seconds=start, duration_seconds=duration,
  )
  ```
  `select_reference_window` は 10〜30秒に収めて返すため、`extract_reference_segment` の
  `ValueError`（10〜30秒外）は上の `total_seconds` ガードにより発生しない。

#### D. 一時ファイルの命名（S-5 厳守。利用者入力を `Path` 連結に使わない）

すべて `storage_path(paths.temporary, uuid4(), <suffix>)` で作る（`ALLOWED_SUFFIXES` の範囲内）。

| 用途 | suffix | 備考 |
|---|---|---|
| アップロード元（`file_upload`） | `.wav` または `.mp3` | **クライアント申告の拡張子に一致させる**。`validate_audio_file` が拡張子とシグネチャの不一致（偽装）を検出するため（RED#5） |
| 録音元（`direct_recording`） | `.tmp` | 拡張子は判定に使わない |
| 同意録音元 | `.tmp` | 同上 |
| 正規化フルWAV（`file_upload` の中間） | `.wav` | 参照区間抽出の入力。confirm 時に削除 |
| 参照WAV（ドラフト試聴の実体） | `.wav` | `VoiceDraft.reference_path` |
| 同意WAV（正規化後） | `.wav` | `VoiceDraft.consent_audio_path` |

**利用者が送ったファイル名・`display_name` は保存パスに一切使わない**（RED#15）。

#### E. 正規化WAVから float サンプルを読む規約

`validate_audio_quality(samples, sample_rate, source_mode, config=...)` へ渡す値は、
**`voices.py` 内の私的ヘルパで標準ライブラリのみを使って読む**（新規依存を足さない）。

```python
def _read_wav_samples(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise KoecloneError(ErrorCode.ERR_INTERNAL)   # 正規化済みなら起こらない
        sample_rate = source.getframerate()
        frames = source.readframes(source.getnframes())
    pcm = array("h")            # from array import array / 16bit signed
    pcm.frombytes(frames)
    return [value / 32768.0 for value in pcm], sample_rate
```

- **除数は `32768.0` 固定**（フルスケール `±32767` → `0.99997` となり
  `AppConfig.absolute_sample_limit = 0.999` を超えるので RED#8 のクリッピング検出が成立する）。
- リトルエンディアン前提。`array` は実行環境依存のため、
  `sys.byteorder != "little"` のときは `pcm.byteswap()` を呼ぶ。
- `source_mode` は `AudioSourceMode(draft の source_mode 文字列)` で変換する。
- `config` は `request.app.state.config` を渡す。
- **検査対象は §2.3.1-C で確定した `reference_path`**（`file_upload` は抽出後の10〜30秒区間）。
- テスト音声は処理コストを抑えるため **12秒以内**を推奨（10秒下限は満たすこと）。

#### F. 不正入力とエラーコードの完全表（この表以外の対応を作らない）

| 入力 | HTTP / ErrorCode |
|---|---|
| `stage` が `validate` / `confirm` 以外 | `400 ERR_BAD_REQUEST` |
| `source_mode` が2値以外 | `400 ERR_BAD_REQUEST` |
| 必須フォーム項目の欠落（`stage` / `source_mode` / `audio` / `draft_id` 等） | `400 ERR_BAD_REQUEST`（T-301 の `RequestValidationError` ハンドラ） |
| `consent_accepted != "true"`（前後空白を除去し casefold 比較） | `403 ERR_NO_CONSENT` |
| `consent_text` が空・空白のみ | `403 ERR_NO_CONSENT` |
| `direct_recording` で `consent_audio` 欠落・0バイト | `403 ERR_NO_CONSENT` |
| `file_upload` に `consent_audio` を付与 | `400 ERR_BAD_REQUEST` |
| `display_name` が strip 後 **50コードポイント超**（`len(value)` で数える） | `400 ERR_BAD_REQUEST` |
| `display_name` 未指定・strip後が空 | エラーにせず既定 `"マイボイス"` |
| `draft_id` が未知・UUID形式でない（**confirm のフォーム項目**） | `404 ERR_DRAFT_NOT_FOUND` |
| `draft_id` がUUID形式でない（**`GET /api/voices/draft/{draft_id}/audio` のパス**） | `400 ERR_BAD_REQUEST`（§1.3。`draft_id: uuid.UUID` で受ける） |
| 同パスで未知の `draft_id` | `404 ERR_DRAFT_NOT_FOUND` |
| ドラフトは存在するが一時ファイルが消えている | `500 ERR_INTERNAL` |
| confirm 時に既存プロフィールあり | `409 ERR_PROFILE_ALREADY_EXISTS` |

**`StorageError` の変換（見落とし注意）**: `storage/db.py` の `StorageError` は `KoecloneError` の
サブクラスではないため、T-301 の例外ハンドラでは `500 ERR_INTERNAL` になる。
`create_voice_profile()` を呼ぶ箇所で `StorageError` を捕捉し、
`raise KoecloneError(error.code) from error` へ変換すること（同時実行時の 409 を保証する）。
事前に `get_current_voice_profile() is not None` でも判定してよいが、**変換は必須**。

#### G. `consent_audio` の扱い（`direct_recording` のみ）

| # | 判定 | 失敗時 |
|---|---|---|
| 1 | MIME が §2.3.1-C の `direct_recording` 許可表にない | `422 ERR_FILE_UNSUPPORTED_FORMAT` |
| 2 | サイズ > `config.max_upload_bytes` | `422 ERR_FILE_TOO_LARGE` |
| 3 | `probe_audio` が `OSError` / `ValueError` を送出、または `duration_seconds is None or <= 0` | `422 ERR_FILE_CORRUPTED` |
| 4 | `not has_audio` | `422 ERR_FILE_NO_AUDIO` |
| 5 | 正規化 `normalize_to_reference_wav`（モノラル24kHz WAV） | `500 ERR_INTERNAL` |

- **長さの上下限検証・品質検査（`validate_audio_quality`）は行わない。**
  同意録音は合成の参照音声ではなく**同意の証跡**（FR-003 / FR-009）であり、
  仕様に長さ・品質の要件が無いため。**推測で閾値を作らない。**
- 保存形式は `.wav`（`storage_path` の `ALLOWED_SUFFIXES` と `collect_deletion_targets` の想定に一致）。
- `consent_method` は `direct_recording` → `ConsentMethod.LIVE_CHALLENGE`、
  `file_upload` → `ConsentMethod.UPLOAD_DECLARATION`。
- `consent_text` の内容は**非空であることのみ**を検証する（チャレンジ文との一致照合はしない。
  FR-003 は「毎回異なる同意文を提示して読み上げさせる」までを要求しており、
  音声認識による照合は MVP の要件に無い）。

#### H. `stage=confirm` のフィールド写像（この表のとおりに埋める）

**資産IDの規約（T-304 の削除処理が成立する前提）**:
参照音声・同意録音・キャッシュのファイル名はすべて **`voice_profiles.id`（= `profile_id`）**を識別子にする。

```python
profile_id  = str(uuid4())
reference   = storage_path(paths.references, profile_id, ".wav")   # 一時参照WAVをコピー
consent_wav = storage_path(paths.consent,    profile_id, ".wav")   # direct_recording のみ
# → T-304 は collect_deletion_targets(paths, reference_id=profile.id,
#      consent_id=profile.id if profile.consent_audio_path else None, job_ids=[...]) で削除できる
```

**`VoiceProfile`（14フィールド）**

| フィールド | 値 |
|---|---|
| `id` | `profile_id` |
| `display_name` | フォーム値を strip。空なら `"マイボイス"` |
| `source_mode` | `draft.source_mode` |
| `source_format` | `draft.source_format` |
| `source_sha256` | `draft.source_sha256`（**元バイト列**のハッシュ。FR-109） |
| `reference_path` | `str(reference)` |
| `reference_sha256` | **保存後の** `reference` から計算 |
| `consent_method` | `draft.consent_method.value` |
| `consent_text` | `draft.consent_text` |
| `consent_audio_path` | `str(consent_wav)` / `file_upload` は `None` |
| `consent_audio_sha256` | **保存後の** `consent_wav` から計算 / `file_upload` は `None` |
| `created_at` | `record.consented_at`（下の `ConsentRecord` と同一時刻。FR-009） |
| `engine` | `request.app.state.engine.engine_name` |
| `model_version` | `request.app.state.engine.model_version`（`load()` を呼ばずに読める） |

`ConsentRecord` は次で作る（戻り値は `created_at` の source としてのみ使い、**DBの独立テーブルは作らない**。
同意情報は `voice_profiles` の3列が保持する）:

```python
record = build_consent_record(
    method=draft.consent_method,
    consent_text=draft.consent_text,
    source_audio_sha256=draft.source_sha256,
    app_version=config.app_version,
    consent_audio_sha256=consent_audio_sha256,   # upload_declaration では必ず None
)
```

**SHA-256 の計算対象**（`hashlib.sha256` の16進小文字。1MiB チャンク読み）:

| 値 | 対象 |
|---|---|
| `source_sha256` | 受信した**元ファイルのバイト列**（正規化前。validate 時に算出） |
| `reference_sha256` | `paths.references` に**保存後**の参照WAV |
| `consent_audio_sha256` | `paths.consent` に**保存後**の同意WAV |

**テスト文ジョブ `SynthesisJob`（16フィールド。FR-111）**

```python
TEST_SENTENCE = "これはテスト用の音声です。声の確認にお使いください。"
synthesis_text, error = build_synthesis_text(TEST_SENTENCE, [], config=config)
if error is not None or synthesis_text is None:
    raise KoecloneError(ErrorCode.ERR_INTERNAL)
```

| フィールド | 値 |
|---|---|
| `id` | `str(uuid4())`（応答の `test_synthesis_id`） |
| `voice_id` | `profile_id` |
| `text` | `TEST_SENTENCE` |
| `text_sha256` | `sha256(TEST_SENTENCE.encode("utf-8")).hexdigest()` |
| `synthesis_text` | 上の `synthesis_text` |
| `synthesis_text_sha256` | `sha256(synthesis_text.encode("utf-8")).hexdigest()` |
| `pronunciation_overrides` | `"[]"`（JSON文字列） |
| `language` | `"ja"` |
| `status` | `"queued"` |
| `audio_path` | `None` |
| `sidecar_path` | `None` |
| `duration_ms` | `None` |
| `watermark_detected` | `None` |
| `error_code` | `None` |
| `created_at` | `datetime.now(UTC).isoformat()` |
| `completed_at` | `None` |

**confirm の実行順**（§2.3 の6ステップを詳細化。この順序を守る）:

1. `stage` 検証 → 2. `draft_id` 解決（404） → 3. `consent_accepted`（403） →
4. `display_name` 検証（400） → 5. 既存プロフィール判定（409） →
6. 参照WAVを `paths.references` へコピー → 7. 同意WAVを `paths.consent` へコピー →
8. `build_consent_record` → 9. `create_voice_profile`（`StorageError` → 409 変換） →
10. **一時ファイル全削除**（`draft.temporary_paths` を `unlink(missing_ok=True)`）＋ `app.state.drafts` から除去 →
11. `create_synthesis_job` → `app.state.queue.submit(job_id)` → `201` を返す

9 より後で失敗した場合も**プロフィールは残す**（ロールバックしない）。
`queue.submit` の失敗は `500 ERR_INTERNAL`。

#### I. 使用する既存関数（すべて現行のまま。変更禁止ファイルへの変更は不要）

| モジュール | 使う関数・型 |
|---|---|
| `domain/file_probe` | `validate_audio_file`（`file_upload` のみ） |
| `domain/audio_quality` | `validate_audio_quality`, `AudioSourceMode` |
| `domain/consent` | `ConsentMethod`, `build_consent_record` |
| `domain/synthesis_text` | `build_synthesis_text`（テスト文ジョブ用） |
| `media/ffmpeg` | `make_probe`, `probe_audio`, `normalize_to_reference_wav`, `detect_silence_ranges`, `select_reference_window`, `extract_reference_segment`, `wav_duration_ms` |
| `storage/files` | `storage_path`（`DataPaths` は `app.state.paths`） |
| `storage/db` | `VoiceProfile`, `SynthesisJob`, `StorageError`, `create_voice_profile`, `get_current_voice_profile`, `create_synthesis_job` |
| `worker/queue` | `JobQueue.submit`（`app.state.queue`） |
| `errors` | `ErrorCode`, `KoecloneError` |
| 標準ライブラリ | `wave`, `array`, `hashlib`, `shutil`, `uuid`, `datetime` |

**`subprocess` を直接呼ばない（S-6）。`pyproject.toml` を変更しない。**

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
| 16 | `test_invalid_uuid_in_synthesis_path_returns_400` | `GET /api/syntheses/not-a-uuid` が `400 ERR_BAD_REQUEST`（§1.3。T-301 のRED#8を実ルート上で確認する。**ハンドラは T-301 実装済みのものを使い、`syntheses.py` に個別実装しない**） |

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

### 2.14 T-314: 音声プロフィール削除UI（3h）

**目的**: 画面から音声プロフィールの削除を確定できるようにする（仕様 §4 スコープ6「1件の音声プロフィールの
作成・再録音・再アップロード・**削除**」／ AC-09「**利用者が**プロフィール削除を確定する」／ FR-113）。

#### 2.14.0 位置づけ（Codexは必ず先に読むこと）

- 本タスクは **新機能ではない。** 仕様 §4 スコープ6 と AC-09 に既に含まれている要件であり、
  **Phase 3 契約 §2.7〜§2.12 のUIタスク分解にプロフィール削除UIを書き落とした Claude の契約起草漏れ**を
  補完するものである（`docs/gate-records.md` §2.6-1）。Codex側の逸脱ではない。
- したがって **§5「仕様との差分」には追加しない。** 本タスクは仕様との差分ではなく契約の欠落補填である。
- サーバー側は **T-304 で実装済み**。**本タスクで `src/koeclone/api/**` を一切変更しない。**
  新しいエンドポイント・新しいデータ項目を作らない（必要だと判断したら §0.6-5 で停止して報告）。
- G3 は本タスクの完了を条件とする**条件付き合格**であり、**G4 判定前に完了・検証する**。

**依存**: T-304（`DELETE /api/voices/current`）, T-307（UI基盤）, T-308, T-309, T-311, T-312, T-313（すべて完了済み）
**段**: 6（単独。並行タスクなし）

#### 2.14.1 所有ファイル

| 区分 | ファイル | 権限 |
|---|---|---|
| 新規作成 | `src/koeclone/web/js/profile.js` | 全体を所有 |
| 既存へ追記 | `src/koeclone/web/index.html` | §2.14.2 のマークアップ追加のみ |
| 既存へ追記 | `src/koeclone/web/style.css` | §2.14.7 の1ルールのみ |
| 既存へ追記 | `src/koeclone/web/js/app.js` | 初期化リストに1行追加のみ |
| 既存へ追記 | `src/koeclone/web/js/record.js` / `upload.js` / `synthesis.js` / `history.js` | §2.14.5 の表に定めるイベント購読のみ（各1〜3行。`synthesis.js` のみ §2.14.5 の裁定により**最大4行**） |
| 既存へ追記 | `tests/e2e/test_flows.py` | §2.14.8 のシナリオ追加・改訂のみ |

**T-307〜T-313 の所有ファイルへ例外的に追記を許可する**が、許可範囲は上表と §2.14.5 / §2.14.8 に
明記した箇所に限る。**既存の関数・既存の振る舞いを書き換えない**（追加のみ。§0.4 の変更禁止ファイルは対象外のまま）。

#### 2.14.2 UI配置とマークアップ（`index.html`）

配置先は **`#register` セクションの先頭**（`<p class="lead">…</p>` の直後、`<div class="mode-tabs">` の直前）。
理由: 仕様 §4 スコープ6 が「作成・再録音・再アップロード・削除」を1つのまとまりとして定義しており、
削除後の導線（再登録）が同一セクション内で完結するため。**5番目のタブ／ステップを増やさない。**

```html
<section id="profile-card" class="workspace-card" aria-labelledby="profile-card-title" hidden>
  <h2 id="profile-card-title">登録済みの声</h2>
  <p id="profile-summary"></p>
  <p class="note">削除すると、参照音声・同意録音・生成した音声とサイドカー・生成履歴がすべて消えます。元に戻せません。</p>
  <button id="profile-delete" class="danger" type="button">登録した声を削除</button>
</section>
<p id="profile-status" role="status" tabindex="-1"></p>
<div id="profile-error" class="alert" role="alert" hidden></div>
```

- **`#profile-status` と `#profile-error` は `#profile-card` の外に置く。**
  カードは削除成功時・未登録時に `hidden` になるため、内側に置くと完了メッセージとエラーが見えなくなる。
- `#profile-status` に `hidden` を使わない（`role="status"` のライブリージョンは常時DOMに存在させる）。
  空のときの余白は §2.14.7 のCSSで消す。
- 見出しは `<h2>`。`#register` の `<h1 id="register-title">` の直下階層であり、見出しレベルを飛ばさない。
- `#profile-summary` の文言: `` `${display_name}（登録日時: ${created_at のローカル表示}）` ``。
  日時整形は `history.js` と同じ `Intl.DateTimeFormat("ja-JP", { dateStyle: "medium", timeStyle: "short" })` を使う。

#### 2.14.3 表示条件（`GET /api/voices/current`）

`initProfile()` は次のタイミングで `GET /api/voices/current` を呼ぶ。

1. 初期化時
2. `koeclone:section` イベントの `detail.name === "register"` のとき

| 応答 | `#profile-card` | `#profile-error` | `#profile-status` |
|---|---|---|---|
| `200` | 表示（summary を更新） | 非表示 | **空にする**（過去の削除完了文言を残さない） |
| `404 ERR_PROFILE_NOT_FOUND` | 非表示 | 非表示 | **変更しない** |
| その他（500 / 通信断など） | 非表示 | `errorMessage(error)` を表示 | **変更しない** |

- **未登録（404）はエラーではない。** `#profile-error` に出さない。既存の `<p class="lead">` の案内が
  登録導線として機能するため、追加の文言を出さない。
- 404 で `#profile-status` を変更しないのは、削除直後に本ルーチンが再実行されても
  完了メッセージ（§2.14.5）が消えないようにするため。

#### 2.14.4 確認ダイアログ（文言を確定する）

`window.confirm()` を使う。**カスタムモーダルを新規実装しない**（既存の「すべて削除」（§2.12）と同じ方式に揃え、
フォーカストラップ等を自作しないことでアクセシビリティ上の退行を避ける）。

表示文言は次のとおりとし、`{display_name}` に `GET /api/voices/current` の `display_name` を埋める。

```text
音声プロフィール「{display_name}」を削除します。
参照音声・同意録音・生成した音声とサイドカー・生成履歴がすべて削除され、元に戻せません。
削除しますか？
```

- 改行は `\n` で入れる（3行）。
- **キャンセル時（`false`）は `DELETE` を呼ばず、画面を一切変更しない。**
- 確認は**1回**。FR-004 の2段階確認はアップロードの権利確認に対する要件であり、削除には適用しない。

#### 2.14.5 削除の実行と成功後の初期化

**実行**: `apiJson("DELETE", "/voices/current")`（`api.js` は `204` を `null` として返す。**`api.js` を変更しない**）。
送信中は `#profile-delete` を `disabled` にして二重送信を防ぐ。

**成功後の処理順（この順序を守る）**:

1. `document.dispatchEvent(new CustomEvent("koeclone:profile-deleted"))`
2. `#profile-card` を `hidden = true`、`#profile-error` を `hidden = true`
3. `document.querySelector('[data-section="register"]').click()` で「声の登録」へ遷移
   （`record.js` / `upload.js` が既に使っているセクション遷移方法に揃える）
4. `#profile-status` に完了文言を設定し、**その後**に `#profile-status.focus()` を呼ぶ
   （空要素は §2.14.7 のCSSで `display: none` になるため、テキスト設定より前にフォーカスしない）

手順3が §2.14.3 の再取得（404）を誘発するが、404 は `#profile-status` を変更しないため完了文言は残る。

**各モジュールの購読（追記を許可する唯一の箇所）**:

| ファイル | `koeclone:profile-deleted` で行う処理 |
|---|---|
| `record.js` | 既存の `reset()` を呼び、`start.disabled` を同意状態に戻す（既存 `discard` ハンドラと同じ2行）。録音ドラフト（`draftId` / `blob` / 試聴 `<audio>` / 「この声で確定」）が消える |
| `upload.js` | 既存の `reset()` を呼ぶ。ファイル選択・権利確認2件・`draftId`・試聴・「この声で確定」が消える |
| `synthesis.js` | `pollGeneration` を1増やして進行中のポーリングを無効化し、`progress.hidden = true`、既存の `clearOutput()` を呼び、**続けて `download.removeAttribute("href")` を実行する**（計4行。下の「裁定」を参照） |
| `history.js` | 既存の `loadHistory()` を呼ぶ。一覧が空になり「すべて記録削除」ボタンが `disabled` になる |
| `profile.js` | 上記 手順2〜4 |

**裁定（`synthesis.js` の4行目 `download.removeAttribute("href")` を明示的に許可する）**

既存の `clearOutput()`（`synthesis.js:39`）は `download.hidden = true` のみで、成功時に設定された
`href`（`synthesis.js:131` の `/api/syntheses/{jobId}/audio`）を残す。したがって購読処理を
「`pollGeneration` / `progress.hidden` / `clearOutput()`」の3件に限ると、削除後も
`#synthesis-download` に前ジョブのURLが残り、§2.14.8(b) 手順6 の必須検証を満たせない。
`clearOutput()` 自体の書き換えは §2.14.1 の「既存の関数・既存の振る舞いを書き換えない」に反し、
生成フロー（`preview` / `generate` / `pollJob` の3経路）の振る舞いも変えてしまうため採らない。
よって**購読処理側に4行目 `download.removeAttribute("href")` を追加することのみを許可**し、
§2.14.1 の行数上限を `synthesis.js` に限り 4行へ整合させる。
`href` は空文字や `"#"` の再代入ではなく**属性ごと除去**すること（手順6 の判定式を決定的にするため）。
`download` は `initSynthesis()` スコープの既存 const（`synthesis.js:30`）をそのまま参照し、
購読は既存の `koeclone:synthesis-job` 購読（`synthesis.js:152`）と同じく `initSynthesis()` 末尾に置く。

- **`#synthesis-text` の本文と読み修正一覧は消さない。** 利用者が入力した文章はプロフィール由来のデータではなく、
  削除対象（AC-09）に含まれない。`#ai-disclosure` のチェック状態も変更しない。
- 進行中のポーリングを止めるのは、削除でジョブが消えて `GET /api/syntheses/{id}` が `404` になり、
  無効なエラーを表示し続けるため（リーク禁止＝§2.11 の方針を踏襲）。

#### 2.14.6 エラー処理（404 / その他）

| 事象 | 扱い |
|---|---|
| `DELETE` が `204` | §2.14.5。`#profile-status` = 「音声プロフィールを削除しました。参照音声・生成した音声・履歴もすべて削除されています。」 |
| `DELETE` が `404 ERR_PROFILE_NOT_FOUND` | **エラー表示にしない。** §2.14.5 と同じ初期化を実行し、`#profile-status` = 「音声プロフィールは既に削除されています。」（別タブ・別操作で先に削除された場合の競合。利用者から見た結果は同じなので、失敗として提示しない） |
| その他（500 / 通信断など） | `#profile-error` に `errorMessage(error)` を表示。**カードは表示したまま**、`#profile-delete` を再度有効化して再試行できるようにする。`koeclone:profile-deleted` は**発火しない**（実際には消えていないため） |

**エラーを握りつぶさない**（§2.7）。`catch` して何も表示しない実装は契約違反。

#### 2.14.7 アクセシビリティ

- 見出し階層を飛ばさない（`#register` の `h1` → カードの `h2`）。§2.14.2 のとおり。
- 削除ボタンのアクセシブル名は **「登録した声を削除」**。履歴の「削除」「すべて削除」と重複しない文言にする
  （E2E の `get_by_role("button", name=...)` が曖昧一致で誤爆しないようにするため）。
- `#profile-status` は `role="status"`（polite）、`#profile-error` は `role="alert"`（assertive）。
- 削除完了後は `#profile-status` へフォーカスを移す（`tabindex="-1"`）。
  スクリーンリーダー利用者が、消えたカードではなく結果に着地するようにする。
- `:focus-visible` の既存アウトライン（`style.css:21`）を打ち消さない。`outline: none` を書かない。
- 新しい色を定義しない。注意文は既存トークン `var(--muted)` を使う（`.rule-card p` と同一の配色で、
  カード背景 `#fafaf6` に対し 4.5:1 以上を満たす）。
- 追加するCSSは**次の1ルールのみ**:

```css
#profile-status:empty { display: none; }
#profile-status { margin: .75rem 0; color: var(--muted); line-height: 1.6; }
#profile-card .note { margin: 0; color: var(--muted); line-height: 1.6; }
```

#### 2.14.8 E2E 追加項目（`tests/e2e/test_flows.py`）

**(a) 既存シナリオ10 `test_profile_delete_removes_history_and_audio` の改訂（必須）**

- 削除の確定を `page.request.delete(...)` から **UI操作**（`#profile-delete` ＋ ダイアログ承諾）に置き換える。
- 「UI にプロフィール削除の操作要素が存在しないため…T-314」の申し送りコメント（現行 206〜207行目）を削除する。
- 削除後の `GET /api/voices/current` → `404`、`GET /api/syntheses/{id}` → `404`、`.../audio` → `404` の
  3件の検証と、リロード後に履歴が空であることの検証は**そのまま残す**（AC-09 の証跡）。

**(b) 新規シナリオ11 `test_profile_delete_from_ui_resets_screens`（必須）**

シナリオ10がリロードを挟むのに対し、本シナリオは**リロードせずに**画面が初期化されることを検証する
（リロードすれば何もしなくても初期化されてしまうため、シナリオ10だけでは §2.14.5 を検証できない）。

| # | 手順・検証 |
|---|---|
| 1 | `_register_upload(...)` → `_generate(page, "削除後に画面が初期化されること。")` |
| 2 | 「声の登録」へ遷移し、`#profile-card` が可視、`#profile-summary` に「マイボイス」が含まれること |
| 3 | **キャンセル経路**: `page.once("dialog", lambda d: d.dismiss())` → `#profile-delete` をクリック → `#profile-card` が可視のまま、`GET /api/voices/current` が `200` |
| 4 | **ダイアログ文言**: 承諾時に `dialog.message` を捕捉し、「マイボイス」と「元に戻せません」を含むこと |
| 5 | 承諾 → **リロードせずに** `#profile-card` が `hidden`、`#profile-status` が「音声プロフィールを削除しました」を含む、`#profile-status` にフォーカスがあること |
| 6 | 合成UI: `page.locator("#synthesis-player").evaluate("n => n.hidden && !n.getAttribute('src')")` が真。`#synthesis-download` は `page.locator("#synthesis-download").evaluate("n => n.hidden && n.getAttribute('href') === null")` が真（§2.14.5 の裁定により属性ごと除去されるため。`href` が前ジョブのURL `/api/syntheses/{id}/audio` のまま残っていれば失敗する） |
| 7 | 登録UI: `#upload-confirm` が `hidden`、`#voice-file` の値が空、`#record-confirm` が `hidden` |
| 8 | 「履歴」へ遷移し `.history-item` が0件、`#history-delete-all` が `disabled` |
| 9 | `GET /api/voices/current` が `404` |

- **手順6は `to_be_hidden()` で代用しない。** 削除後は `#synthesis` セクション自体が `hidden` になるため、
  `to_be_hidden()` は実装が無くても成立してしまう（T-313 レビュー Major#3 と同種の欠陥）。
  要素の `hidden` プロパティと `src` 属性を直接評価すること。
- 固定 `sleep` を使わない。条件待ち（`expect` / `wait_for`）を使う（§2.13 と同じ）。

#### 2.14.9 RED / GREEN / REFACTOR

- **RED**: 先に §2.14.8(b) のシナリオ11を書き、`#profile-delete` が存在しないことによる失敗を確認する。
  失敗出力（セレクタ未検出）を報告に含める。続いて (a) の改訂を行い、同じく失敗を確認する。
- **GREEN**: `profile.js` の新規作成と §2.14.1 の追記で2シナリオを通す最小実装。
- **REFACTOR**: **なし。** 純関数の切り出しは行わない。JSユニットテストの実行基盤が本リポジトリに存在せず
  （`tests/` は pytest のみ、`package.json` なし）、検証されない抽象を増やさないため。
  JS実行基盤の追加が必要だと判断した場合は §0.6-3 で停止して報告する。

#### 2.14.10 検証と完了条件

**検証コマンド（すべて実行し、実出力を報告する）**:

```bash
pytest tests/e2e -q          # 既存10シナリオ + 新規1シナリオ
pytest -q                    # 全体回帰（失敗0）
ruff check .                 # 指摘ゼロ
```

**完了条件（全て満たすこと）**:

1. `pytest tests/e2e -q` が全シナリオ成功（シナリオ10がUI操作経由で成功、シナリオ11が成功）。
2. `pytest -q` に失敗が無く、G3 判定時から失敗が増えていない。
3. `ruff check .` の指摘がゼロ。
4. Claude の手動確認: 画面から削除 → カード消滅・完了メッセージ表示・履歴が空・プレイヤーが消える。
   リロード後も `GET /api/voices/current` が `404`。
5. Claude の差分レビュー: `src/koeclone/api/**` と §0.4 の変更禁止ファイルが無変更、
   新規エンドポイント無し、外部CDN・外部フォント・外部画像の参照無し（S-11）、
   既存所有ファイルへの追記が §2.14.1 の表と §2.14.5 / §2.14.8 の範囲内。
6. レビューで Blocking / Major の指摘がゼロ。

**禁止事項（違反は差戻し）**:

- `src/koeclone/api/**` の変更、新しいAPIエンドポイント・データ項目の追加。
- 5番目のタブ／ステップの追加、既存セクション構成の変更。
- 履歴の「削除」「すべて削除」の既存挙動の変更。
- `window.confirm` に代わるカスタムモーダルの新規実装。
- `api.js` の共通関数の変更。

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
| 2 | `ErrorCode` に8件追加（§2.1） | 仕様§7.4「全APIエラーは安定したエラーコードを持つ」を満たすために必要。既存コードは変更しない |
| 3 | `AppConfig` に `engine` / `app_version` を追加 | 偽エンジン切替（テスト・E2E必須）と同意記録の `app_version`（FR-009）に必要 |

上記3件以外の追加・変更は**契約違反**として差戻す。

---

## 6. 契約改訂履歴

### 2026-08-10 改訂1（T-301 着手前 / Codex報告の§0.6停止に対するClaude裁定）

Codex から3件の矛盾報告を受け、Claude が本契約を以下のとおり修正した。**コード変更前**の修正であり、
既存の実装・テストへの影響はない。

| # | 報告された矛盾 | 裁定 | 変更箇所 |
|---|---|---|---|
| 1 | RED#4 の未知ルート404に割り当てられるコードが§1.2表に存在しない（`ERR_BAD_REQUEST` は400限定） | **`ERR_ROUTE_NOT_FOUND` を追加**（列挙子7件→8件）。`ERR_BAD_REQUEST` を404で返す例外扱いは、コード→ステータス対応の安定性（§7.4）を崩すため**採用しない** | §1.2 表・注記、§2.1 列挙子、RED#4、§5-2 |
| 2 | RED#8 が T-305 所有の `/api/syntheses/*` を要求する | 検証対象は**§1.3のUUID変換ハンドラ**であってルートではない。RED#5 と同じ「テスト専用ルート」方式に変更し、実ルート上の確認は T-305 の RED#16 として移設 | RED#8、T-305 RED#16 |
| 3 | 後続ルータを製品appへ登録する機構が未定義（T-302以降は `app.py` 変更禁止） | **T-301 が `find_spec` による固定リスト走査で遅延登録する**。各タスクへ `app.py` 追記所有を許可する案は、第2段の3系列並行（T-302 / T-303 / T-305）が同一ファイルを奪い合うため**採用しない** | §1.6 ルータ登録機構 |

あわせて、着手直後に停止を招く以下2点を先回りで確定した（Codexからの報告事項ではない）。

| # | 論点 | 裁定 | 変更箇所 |
|---|---|---|---|
| 4 | RED#7 の静的配信テストが `src/koeclone/web/index.html`（T-307所有）を必要としてしまう | `create_app` に `web_dir` 引数を追加し、テストは `tmp_path` を渡す | §1.6 シグネチャ、RED#7 |
| 5 | `JobQueue` のハンドラと起動タイミングが未定義（未起動だとジョブが永久に処理されない） | T-301 が DB→`SynthesisRequest` の薄いハンドラを実装し、`create_app` 内で `queue.start()` を呼ぶ | §1.6 `app.state.queue` の初期化 |

### 2026-08-10 改訂2（T-301 レビュー中 / Claudeが発見した契約の穴を明文化）

T-301 の実装レビューで、**契約に書かれていないために抜け落ちうる**穴を3件発見した。
いずれも実装済みの内容を契約へ追認するものであり、実装への新規要求は追加していない。

| # | 契約の穴 | 追記内容 | 変更箇所 |
|---|---|---|---|
| 1 | 未捕捉例外（`KoecloneError` / `StarletteHTTPException` 以外）の応答形が未定義。Starlette 既定のプレーンテキスト `Internal Server Error` が漏れても契約違反にならなかった | `Exception` の catch-all を必須化。`500 ERR_INTERNAL` ＋ `error_id`、本文に例外文言・内部パスを含めない | §1.2 catch-all、§2.1 GREEN、RED#13 |
| 2 | S-3 が「`Content-Length` 詐称に備え受信バイト数でも計測」を要求しているのに、対応する RED が存在せず、宣言値チェックのみでも RED#3 を通過できた | 生ASGI でボディをストリーム送出する詐称テストを RED に追加。純ASGIミドルウェア実装を明記 | §2.1 RED#11、GREEN |
| 3 | §1.2 表は 405 に `ERR_ROUTE_NOT_FOUND` を割り当てるが RED が無く、405 を 404 へ丸めても検出できなかった | 405 の状態コード維持を明記し RED を追加 | §1.2 注記、§2.1 RED#12 |

### 2026-08-12 改訂3（T-303 着手前 / Codex報告の§0.6停止に対するClaude裁定）

Codex から T-303 の未定義・矛盾6件の報告を受け、Claude が **§2.3.1 を新設**して確定した。
**コード変更前**の改訂であり、既存の実装・テストへの影響はない。
既存の `domain/**` / `storage/**` / `media/**` / `worker/**` / `api/app.py` は**変更不要**であることを確認した（§2.3.1-I）。

| # | 報告された未定義・矛盾 | 裁定 | 変更箇所 |
|---|---|---|---|
| 1 | `VoiceDraft` が §1.6 に名前だけ登場し、フィールド・所有場所・一時ファイル構成が未定義 | **T-303 が `api/voices.py` に定義**（`app.py` は空辞書のみで import しない）。11フィールドを確定。ハッシュ2件はドラフトに持たず confirm 時に最終ファイルから計算する | §1.6 注記、§2.3.1-A / -D |
| 2 | `validate_audio_file` は WAV/MP3 専用だが `direct_recording` は webm/ogg/mp4/wav を要求しており矛盾 | **モードで部品を分ける**。`file_upload` は `validate_audio_file` 1回で完結。`direct_recording` は同関数を**使わず**「MIME許可表 → `probe_audio` → 長さ判定」の7段で判定する。コーデック名照合は行わない | §2.3 処理順2・3、§2.3.1-C |
| 3 | `consent_audio` の形式検証・長さ・正規化・保存形式が未定義 | MIME許可表＋`probe_audio`＋正規化のみ。**長さ上下限と品質検査は課さない**（同意録音は証跡であり、仕様に閾値が無いため推測で作らない）。保存は `.wav` | §2.3.1-G |
| 4 | 正規化WAV → float サンプルの読み出し規約が未定義 | 標準ライブラリ `wave` + `array` の私的ヘルパ。**除数 `32768.0` 固定**（フルスケールが `absolute_sample_limit=0.999` を超え RED#8 が成立する）。バイトオーダー処理を明記 | §2.3.1-E |
| 5 | confirm 時の `VoiceProfile` 14項目・`SynthesisJob` 16項目の写像が未定義 | 全項目の写像表を確定。**参照音声・同意録音・キャッシュの識別子を `voice_profiles.id` に統一**し、T-304 の `collect_deletion_targets` が成立するようにした。`StorageError` は `KoecloneError` ではないため 409 への明示変換を必須化 | §2.3.1-F / -H |
| 6 | `stage` / `source_mode` / `display_name>50` 等の不正値に返すコードが未定義 | 不正入力の完全表を確定（いずれも既存の列挙子のみを使用。**`ErrorCode` は追加しない**）。対応する RED を3件追加 | §2.3.1-F、§2.3 RED#17〜19 |

あわせて、着手後に不安定化する以下1点を先回りで確定した（Codexからの報告事項ではない）。

| # | 論点 | 裁定 | 変更箇所 |
|---|---|---|---|
| 7 | RED#11（確定後 `paths.temporary` が空）は、テスト文ジョブが `paths.temporary` に作業ディレクトリを作るため競合で不安定になる | 検査前に `app.state.queue.wait_for(test_synthesis_id)` でジョブ終了を待つことを必須化 | §2.3 RED#11 |

### 2026-08-12 改訂4（G3 条件付き合格の条件対応 / T-314 の新設）

G3 レビューで、**画面に音声プロフィール削除の操作要素が存在しない**ことを検出した
（`docs/gate-records.md` §2.6-1）。仕様 §4 スコープ6 と AC-09 は利用者による削除確定を要求しており、
API（T-304）は実装済みである一方、**本契約 §2.7〜§2.12 のUIタスク分解に削除UIを含めていなかった**。
原因は Claude の契約起草漏れであり、Codex の逸脱ではない（§0.6-5 は契約外の画面機能追加を禁じている）。

| # | 内容 | 裁定 | 変更箇所 |
|---|---|---|---|
| 1 | プロフィール削除UIがどのタスクにも属していない | **T-314 として新設**（3h）。UI配置・確認文言・成功後の初期化・404/エラー・A11y・E2E追加項目まで契約で確定し、Codex が推測で設計する余地を残さない | §2.14 新設 |
| 2 | 本追加が「仕様との差分」に見える | **差分ではない。** 仕様 §4 スコープ6・AC-09 に既にある要件の実装であり、**§5 には追加しない**ことを明記 | §2.14.0 |
| 3 | 削除後の画面初期化が複数モジュール（record / upload / synthesis / history）に跨る | 既存の `koeclone:synthesis-job` と同じ **`document` の CustomEvent 方式**（`koeclone:profile-deleted`）で各モジュールが自分の既存 reset を呼ぶ。他タスク所有ファイルへの追記は各1〜3行の購読のみに限定 | §2.14.5 |
| 4 | T-313 シナリオ10 は削除を生APIで実行しており、UIが出来ても検証されない | シナリオ10 を **UI操作経由へ改訂**し、申し送りコメントを削除。加えて**リロードせずに**画面が初期化されることを検証するシナリオ11を新設（リロードすれば実装が無くても初期化されてしまうため） | §2.14.8 |

**コード変更前**の改訂であり、既存の実装・テストへの新規要求は T-314 の範囲に限られる。
本改訂に伴い、契約IDを T-301〜T-314、見積を合計63h、依存グラフに段6を追加した。
