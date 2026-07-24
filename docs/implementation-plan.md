# koeclone 実装計画書

## 1. 文書メタデータと計画ステータス

| 項目 | 内容 |
|---|---|
| 文書名 | koeclone 実装計画書 |
| バージョン | 1.0 |
| ステータス | Draft（実装開始前レビュー待ち） |
| 作成日 | 2026-07-24 |
| 作成者 | Claude（唯一の指揮官） |
| 実装担当 | Codex |
| 上位文書 | `docs/system-specification.md`（Draft 0.1） |
| 対象ディレクトリ | `/Users/Jobs1/AI/koeclone` |
| リモート | `https://github.com/CatwalkTK/koeclone`（public / default branch: main / 現在空） |

本計画は仕様書のMVP範囲を過不足なく実装するためのものであり、仕様外の機能追加を含まない。
仕様書と本計画が矛盾した場合は仕様書を正とし、本計画を改訂する。

---

## 2. 現状と前提

### 2.1 現状

- ローカル `/Users/Jobs1/AI/koeclone` には `docs/system-specification.md` のみが存在する。コード、Git管理、依存関係は未整備。
- GitHubリポジトリ `CatwalkTK/koeclone` は空（size 0、コミットなし）。
- 音声エンジン（Chatterbox Multilingual V3）の対象Macでの動作は未検証。**PoC合格前に本実装へ進まない。**

### 2.2 前提

- macOS上の単一ユーザー向けローカルWebアプリ。対象言語は日本語のみ（`ja` 固定）。
- 本人の声のみを登録・複製する。他者の声のクローンは対象外。
- 音声・テキスト・同意記録を外部送信しない。サーバーは `127.0.0.1` のみにバインドする。
- 初回の依存・モデル取得後はオフラインで登録・生成・再生・保存・削除が完結する。
- 技術スタックは Python 3.11 + FastAPI + Vanilla JS + FFmpeg + SQLite + pytest/Playwright（仕様書 §8）。

### 2.3 役割分担（責務境界）

| 担当 | 責務 |
|---|---|
| Claude（指揮官） | 要件確定、設計判断、タスク分解と委譲、**リポジトリ初期化・remote設定・全Git操作**、**依存関係・モデルの導入**、PoC実施と判定、レビュー、独立検証、ユーザー報告 |
| Codex（実装者） | Claudeが指定したタスク契約の範囲内でのTDD実装、テスト作成・実行、結果とブロッカーの報告 |

**Codexへの禁止事項（全タスク共通・厳守）:**

- `git add`、`git commit`、`git checkout`、`git switch`、`git merge`、`git rebase`、`git reset`、`git stash`、`git worktree` を含む一切のGit操作の実行
- `pip install` / `uv add` 等による依存関係の導入・更新・削除（依存導入はClaudeのみ）
- モデル重みのダウンロード・更新
- タスク契約の「所有ファイル」以外の作成・変更・削除
- ネットワークへ音声・テキストを送信するコードの追加

ClaudeはCodexの自己申告のみで完了判定せず、差分・テスト実行・生成物を独立に確認する。
コミットはClaudeが対象ファイルを個別に `git add <file>` してから行う（`git add .` / `-A` 禁止）。

---

## 3. 成功条件とMVPスコープ外

### 3.1 成功条件（リリース判定）

1. 仕様書の受入条件 AC-01〜AC-10 を全て満たす。
2. 機能要件 FR-001〜FR-009 / FR-101〜FR-113 / FR-201〜FR-218 / FR-301〜FR-304 が実装・テスト済みである。
3. Unit / Integration / エンジン契約 / E2E テストが全件成功し、通常CI相当の実行は偽エンジンで完結する。
4. 品質基準（仕様書 §7.3）: 20評価文で異常継続0件・明瞭性95%以上、部分読み10文全件正解、本人らしさ5段階中4以上。
5. セキュリティ確認（仕様書 §7.1）: localhost限定、CORS無効/同一オリジン、50MB・1,000文字制限、パストラバーサル防止、ログ漏えいなし、完全削除。
6. Blocking / Major のレビュー指摘が残っていない。

### 3.2 MVPスコープ外（実装禁止）

仕様書 §4.2 のとおり。特に以下は計画上も一切のタスクを設けない。

- 他人・有名人・故人・キャラクターの声のクローン
- 複数ユーザー、ログイン、クラウド同期、外部共有、SNS投稿
- モデル追加学習、感情編集、MP3/AAC出力、バッチ生成、API外部公開
- **ウォーターマークの除去・無効化（設定項目としても提供しない）**
- 自動読み推定、アクセント辞書、読み修正の共通辞書

---

## 4. 採用アーキテクチャと技術スタック

### 4.1 採用スタック（仕様書 §8.1 準拠）

| 領域 | 採用 | 補足 |
|---|---|---|
| 音声エンジン | Chatterbox Multilingual V3 | Phase 0 PoC合格を条件に確定。PerThウォーターマーク内蔵 |
| バックエンド | Python 3.11 + FastAPI | uvicorn を `127.0.0.1` 固定で起動 |
| フロントエンド | FastAPI配信の静的 HTML/CSS/Vanilla JS | ビルドツールなし。MediaRecorderで録音 |
| 音声変換 | FFmpeg（引数配列・固定オプションで実行） | デコード、モノラル24kHz正規化、参照区間抽出、WAV結合 |
| メタデータ | SQLite（標準ライブラリ `sqlite3`） | 単一ユーザー・ローカル用途に十分 |
| ファイル保存 | ローカルデータディレクトリ（権限700） | UUID由来のファイル名のみ使用 |
| テスト | pytest + FastAPI TestClient + Playwright | 実モデル試験はマーカー付き分離 |

### 4.2 代替案比較

| 領域 | 採用案 | 代替案 | 不採用理由 / 切替条件 |
|---|---|---|---|
| 音声エンジン | Chatterbox Multilingual V3 | Coqui XTTS v2 | PoC不合格（macOS互換・速度・音質・ライセンス）の場合のみ、同一基準で比較して切替。ADRで記録 |
| 演算デバイス | MPS優先 | CPUフォールバック | MPS初期化失敗を記録し、設定で許可された場合のみCPUへ（FR/§7.4） |
| フロントエンド | Vanilla JS | React/Next.js | 単一ユーザーMVPには過剰。ビルド依存を増やさない |
| DB | SQLite | JSONファイル / PostgreSQL | JSONは同時更新・整合性に弱く、PostgreSQLは運用過剰 |
| ORM | 生SQL + 薄いリポジトリ層 | SQLAlchemy | 2テーブルのみで依存追加に見合わない |
| キュー | プロセス内単一ワーカースレッド | Celery/Redis | 同時ジョブ1件（FR-204）のみで外部ミドルウェア不要 |

### 4.3 アーキテクチャ方針（仕様書 §7.4 / §8.2）

- ドメイン層・HTTP層・ストレージ層・音声エンジン層を分離する。
- 音声エンジンは `SpeechEngine` インターフェースで抽象化し、テストは `FakeEngine` に置換する。
- モデルロードはプロセス内1回。単一ジョブキューで生成を直列化する。
- 全APIエラーは安定したエラーコード（例: `ERR_TEXT_TOO_LONG`、`ERR_NO_CONSENT`、`ERR_WATERMARK_NOT_DETECTED`）を持つ。

---

## 5. ディレクトリ・主要インターフェース・API・データモデル

### 5.1 ディレクトリ構成（仕様書 §8.3 準拠 + 具体化）

```text
koeclone/
├── docs/
│   ├── system-specification.md
│   ├── implementation-plan.md        # 本書
│   ├── poc-results.md                # Phase 0 で作成
│   └── adr/
│       └── 0001-speech-engine.md     # Phase 0 で作成
├── src/koeclone/
│   ├── config.py                     # データディレクトリ、host/port、閾値、デバイス設定
│   ├── errors.py                     # 安定エラーコード定義
│   ├── api/
│   │   ├── app.py                    # FastAPIアプリ生成、静的配信、エラーハンドラ
│   │   ├── consent.py                # /api/consent/challenge
│   │   ├── voices.py                 # /api/voices*
│   │   └── syntheses.py              # /api/syntheses*
│   ├── domain/
│   │   ├── text_validation.py        # FR-201/202/217
│   │   ├── pronunciation.py          # FR-211〜215（読み修正の検証）
│   │   ├── synthesis_text.py         # FR-216/218 + FR-203（分割）
│   │   ├── audio_quality.py          # FR-106（無音率・クリッピング・音量）
│   │   ├── file_probe.py             # FR-105（形式照合）
│   │   ├── consent.py                # FR-003/009（同意文生成・同意記録）
│   │   └── sidecar.py                # FR-007
│   ├── engines/
│   │   ├── base.py                   # SpeechEngine インターフェース
│   │   ├── fake.py                   # テスト用偽エンジン
│   │   └── chatterbox.py             # 実エンジンアダプター + ウォーターマーク検出
│   ├── media/
│   │   └── ffmpeg.py                 # デコード・正規化・参照区間抽出・WAV結合
│   ├── storage/
│   │   ├── db.py                     # SQLite接続・スキーマ・リポジトリ
│   │   └── files.py                  # データディレクトリ、UUID命名、完全削除
│   ├── worker/
│   │   ├── queue.py                  # 単一ジョブキュー・状態遷移
│   │   └── pipeline.py               # 生成パイプライン統合
│   └── web/                          # 静的UI（index.html, css, js/）
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── engine_contract/              # 実モデル試験（マーカー @pytest.mark.real_model）
│   └── e2e/                          # Playwright
├── scripts/
│   ├── poc_generate.py               # Phase 0 PoC計測
│   └── run.sh                        # 127.0.0.1 起動スクリプト
└── pyproject.toml
```

### 5.2 主要インターフェース

```python
# engines/base.py
class SpeechEngine(Protocol):
    engine_name: str
    model_version: str
    def load(self) -> None: ...                     # プロセス内1回のみ
    def synthesize(self, text: str, reference_wav: Path, language: str) -> Path: ...
    def detect_watermark(self, wav: Path) -> bool: ...

# domain/pronunciation.py
@dataclass(frozen=True)
class PronunciationOverride:
    surface: str      # 原文の該当文字列（漢字を1文字以上含む）
    start: int        # Unicodeコードポイント単位・半開区間
    end: int
    reading: str      # ひらがな/カタカナ/長音/中点/空白のみ

# worker/queue.py
JobStatus = Literal["queued", "running", "succeeded", "failed"]
```

### 5.3 API（仕様書 §9 のまま。追加・変更なし）

| Method | Path | 用途 |
|---|---|---|
| GET | `/api/health` | アプリ・モデル準備状態 |
| GET | `/api/consent/challenge` | ランダム同意文の取得 |
| POST | `/api/voices` | プロフィール作成（直接録音 / WAV・MP3アップロード + 同意情報） |
| GET | `/api/voices/current` | 現在のプロフィール取得 |
| DELETE | `/api/voices/current` | プロフィールと関連データの完全削除 |
| POST | `/api/syntheses/preview` | 読み修正の検証と合成用テキストプレビュー |
| POST | `/api/syntheses` | 生成ジョブ作成 |
| GET | `/api/syntheses/{id}` | ジョブ状態・結果メタデータ |
| GET | `/api/syntheses/{id}/audio` | 生成WAV取得 |
| GET | `/api/syntheses` | 履歴一覧（新しい順） |
| DELETE | `/api/syntheses/{id}` | 生成結果の個別削除 |
| DELETE | `/api/syntheses` | 生成履歴の全削除 |

OpenAPI画面は開発環境のみ有効化する。

補足（仕様の運用詳細。API追加ではない）:

- プロフィール作成は「検査→正規化→試聴→確定」の2段階が必要（FR-108）なため、`POST /api/voices` を `stage=validate`（検査・正規化・試聴用音声返却）と `stage=confirm`（確定）のパラメータで実現する。中間成果物は一時領域に置き、確定時に本登録・一時ファイル削除（FR-112）を行う。

### 5.4 データモデル

仕様書 §10 の `VoiceProfile` / `SynthesisJob` をそのままSQLiteテーブルにマップする（列の追加・削除なし）。
`pronunciation_overrides` はJSON文字列列として保存する。

---

## 6. フェーズ構成

| フェーズ | 内容 | 担当 | ゲート |
|---|---|---|---|
| **Phase C0** | リポジトリ初期化・remote設定・開発環境整備（**Claude専用**） | Claude | G-C0 |
| **Phase 0** | Chatterbox Multilingual V3 実機PoC | Claude主導（計測スクリプトのみCodex） | G0 |
| **Phase 1** | ドメイン・ストレージ（TDD） | Codex | G1 |
| **Phase 2** | 音声エンジン・ジョブ実行 | Codex（実モデル検証はClaude） | G2 |
| **Phase 3** | API・UI・E2E | Codex | G3 |
| **Phase 4** | 安全性・品質検証・リリース判定 | Claude（自動テスト追加のみCodex） | G4 |

各ゲートは「該当フェーズの完了条件を満たし、Blocking/Major指摘ゼロ」で通過。未達なら次フェーズへ進まない。

---

## 7. タスク一覧

記法: 各Codexタスクは **ID / 目的 / 依存 / 所有ファイル / 変更禁止範囲 / RED / GREEN / REFACTOR / 検証コマンド / 完了条件 / 見積もり** を持つ。
共通の変更禁止範囲: 所有ファイル以外の全ファイル、`pyproject.toml`（依存追加はClaude）、`docs/`、Git関連の一切。
検証コマンドはリポジトリルートの仮想環境で実行する前提。

### Phase C0: リポジトリ初期化と環境整備（Claude専用・Codex委譲禁止）

| ID | 内容 | 完了条件 | 見積 |
|---|---|---|---|
| C0-1 | `git init` → default branch `main` → `.gitignore`（venv, `__pycache__`, `.DS_Store`, データディレクトリ, モデルキャッシュ, `node_modules` 等）作成 → `docs/` を個別 `git add` してinitial commit → `git remote add origin https://github.com/CatwalkTK/koeclone.git` → push | GitHub `main` に docs 一式が反映。音声・モデル・データディレクトリがignore対象 | 0.5h |
| C0-2 | Python 3.11 venv作成、`pyproject.toml` 雛形（プロジェクトメタ + dev依存: pytest, httpx, fastapi, uvicorn, ruff）、依存導入 | `python -c "import fastapi"` と `pytest --version` が成功 | 0.5h |
| C0-3 | FFmpeg導入確認（未導入ならHomebrewで導入）とバージョン記録 | `ffmpeg -version` / `ffprobe -version` が成功 | 0.5h |
| C0-4 | feature ブランチ運用開始（`feat/phase0-poc` 等）。main直接コミット禁止の徹底 | ブランチ作成済み | 0.1h |

**ゲート G-C0:** リモートpush成功、venvでpytestが動く、FFmpegが利用可能。

### Phase 0: 技術PoC（仕様書 §13 Phase 0）

| ID | 担当 | 内容 |
|---|---|---|
| P0-C1 | Claude | Chatterbox Multilingual V3 と依存（torch含む）を導入し、モデル重みを取得。モデル版・取得元・ファイルハッシュを記録して固定。コードとモデル重み双方のライセンス条件を確認・記録 |
| P0-X1 | Codex | PoC計測スクリプト実装（下記契約） |
| P0-C2 | Claude | 基準Mac上でMPS/CPU両方で日本語参照音声から5文以上生成。速度・RTF・ピークメモリ・音質・異常継続・**ウォーターマーク検出可否**を計測し `docs/poc-results.md` に記録。品質閾値（FR-106の無音率・音量基準）の実測確定。`docs/adr/0001-speech-engine.md` を作成・承認 |

**タスク契約 P0-X1: PoC計測スクリプト**

- 目的: 参照WAVと評価文リストを受け取り、MPS/CPU指定で合成し、所要時間・RTF・ピークメモリ・出力パス・ウォーターマーク検出結果をJSONで出力するスクリプトを作る。
- 依存: P0-C1（依存導入済み環境）
- 所有ファイル: `scripts/poc_generate.py`, `tests/unit/test_poc_args.py`
- 変更禁止範囲: 共通規定どおり。モデルのダウンロード処理を書かない（ロードのみ）。
- RED: 引数解析（デバイス指定 `cpu`/`mps`、参照WAVパス、出力先）と結果JSONスキーマの単体テストを先に書き、スクリプト未実装で失敗することを確認。
- GREEN: 引数解析・計測ループ・JSON出力の最小実装。エンジン呼び出しは注入可能な関数に分離し、テストでは偽実装を注入。
- REFACTOR: 計測部の関数分割まで。機能追加禁止。
- 検証コマンド: `pytest tests/unit/test_poc_args.py -q`
- 完了条件: テスト成功。実行自体（実モデル）はClaudeがP0-C2で実施。
- 見積: 2h

**ゲート G0（Phase 0 完了条件）:**

- `docs/poc-results.md` が実測値付きで作成済み。
- 10秒相当の日本語音声を基準Macで60秒以内に生成（暫定合格基準、§7.2）。
- ウォーターマークが生成音声から検出できる。
- ライセンス上、本用途での利用に支障がない。
- ADR-0001 が承認済み。**不合格時は Coqui XTTS v2 等を同一基準で比較し、本計画の該当箇所を改訂してから再ゲート。**

### Phase 1: ドメイン・ストレージ（TDD / 全てCodex）

> 各タスクは互いに素なファイルを所有するため、依存が満たされれば並行委譲可。

**T-101: 設定・エラーコード基盤**
- 目的: データディレクトリ（既定 `~/…/koeclone-data` 相当、設定可能）、host=127.0.0.1固定、閾値、デバイス設定、CPUフォールバック許可フラグを持つ設定モジュールと、安定エラーコード列挙を作る。
- 依存: G-C0
- 所有: `src/koeclone/config.py`, `src/koeclone/errors.py`, `tests/unit/test_config.py`
- RED: 「hostは常に127.0.0.1」「環境変数でデータディレクトリを上書き可能」「エラーコードが一意」のテストが未実装で失敗。
- GREEN: dataclassベースの最小設定 + Enum定義。
- REFACTOR: 定数整理まで。
- 検証: `pytest tests/unit/test_config.py -q`
- 完了: テスト成功。host変更手段が存在しない。
- 見積: 2h

**T-102: テキスト入力検証（FR-201/202/217）**
- 目的: 1〜1,000文字（コードポイント）、空白のみ拒否、制御文字・HTMLを実行せず文字列として扱う検証関数。
- 依存: T-101
- 所有: `src/koeclone/domain/text_validation.py`, `tests/unit/test_text_validation.py`
- RED: 0字・1,001字・空白のみ・制御文字混在・正常系のテストが失敗。
- GREEN: 長さ・空白判定の最小実装。エラーは `errors.py` のコードで返す。
- REFACTOR: 判定関数の分割まで。
- 検証: `pytest tests/unit/test_text_validation.py -q`
- 完了: 全テスト成功。AC-07の入力系拒否ケースを網羅。
- 見積: 2h

**T-103: 読み修正の検証（FR-211〜215, R-10）**
- 目的: `PronunciationOverride` の検証。読み文字種（ひらがな/カタカナ/長音/中点/空白のみ、空文字拒否）、範囲がコードポイント半開区間で原文内、`text[start:end] == surface`、surfaceに漢字1文字以上、複数修正の重複拒否。
- 依存: T-101
- 所有: `src/koeclone/domain/pronunciation.py`, `tests/unit/test_pronunciation.py`
- RED: 漢字を含む読み・空読み・範囲外・元文字列不一致・重複範囲・正常系（「日本橋」→「にほんばし」）のテストが失敗。
- GREEN: 文字種正規表現と範囲検証の最小実装。
- REFACTOR: 検証順序の整理まで。
- 検証: `pytest tests/unit/test_pronunciation.py -q`
- 完了: AC-06/AC-07の読み修正系ケースを網羅して成功。
- 見積: 3h

**T-104: 合成用テキスト生成と長文分割（FR-203/216/217/218）**
- 目的: 検証済み修正を**後方の範囲から順に**置換して合成用テキストを作る（原文不変）。置換後2,000字超を拒否。句読点境界での分割（順序維持）。通常モードは原文をそのまま使用。
- 依存: T-103
- 所有: `src/koeclone/domain/synthesis_text.py`, `tests/unit/test_synthesis_text.py`
- RED: AC-06の例（「明日は日本橋へ行きます」→「明日はにほんばしへ行きます」）、複数修正、2,001字拒否、分割順序のテストが失敗。
- GREEN: 逆順置換と句読点分割の最小実装。
- REFACTOR: 分割規則の関数化まで。
- 検証: `pytest tests/unit/test_synthesis_text.py -q`
- 完了: 全テスト成功。原文が変更されないことをテストで保証。
- 見積: 3h

**T-105: 音声品質判定（FR-103/104/106）**
- 目的: PCMサンプル列に対し、長さ（録音10〜60秒 / アップロード10〜180秒）、無音率80%以上拒否、ピーク>-1dBFSのクリッピング拒否、平均音量基準外拒否を判定し、拒否理由コードを返す。閾値は設定注入（PoC実測で確定）。
- 依存: T-101（閾値既定値はG0の実測を反映）
- 所有: `src/koeclone/domain/audio_quality.py`, `tests/unit/test_audio_quality.py`
- RED: 合成した無音・クリッピング・低音量・正常波形のfixture（プログラム生成。実在人物の音声は使わない）で判定テストが失敗。
- GREEN: RMS/ピーク/無音率計算の最小実装。
- REFACTOR: 数値計算の共通化まで。
- 検証: `pytest tests/unit/test_audio_quality.py -q`
- 完了: AC-04の品質系拒否を網羅して成功。
- 見積: 4h

**T-106: ファイル形式照合（FR-104/105）**
- 目的: 拡張子を信用せず、ファイルシグネチャ（RIFF/WAVE、MP3フレーム/ID3）、申告MIME、実デコード結果（ffprobe）を照合。形式偽装・破損・暗号化・音声なし・50MB超・時間範囲外を拒否。
- 依存: T-101
- 所有: `src/koeclone/domain/file_probe.py`, `tests/unit/test_file_probe.py`
- RED: 偽装拡張子・破損ヘッダ・空ファイル・サイズ超過のfixtureで拒否テストが失敗。ffprobe呼び出しは注入可能にし単体テストでは偽実装。
- GREEN: シグネチャ判定 + ffprobe結果照合の最小実装。ffprobeは**引数配列**で実行。
- REFACTOR: 判定の表駆動化まで。
- 検証: `pytest tests/unit/test_file_probe.py -q`
- 完了: AC-04の形式系拒否を網羅して成功。シェル文字列連結が存在しない。
- 見積: 4h

**T-107: SQLiteストレージ（§10）**
- 目的: `VoiceProfile` / `SynthesisJob` のスキーマ作成、CRUD、有効プロフィール1件制約（FR-110）、履歴の新しい順取得（FR-301）。
- 依存: T-101
- 所有: `src/koeclone/storage/db.py`, `tests/integration/test_db.py`
- RED: 一時DBでの作成・取得・2件目プロフィール拒否・履歴順序・削除のテストが失敗。
- GREEN: 生SQLでのスキーマとリポジトリ最小実装。
- REFACTOR: SQL定数の整理まで。
- 検証: `pytest tests/integration/test_db.py -q`
- 完了: 全テスト成功。全列が仕様§10と一致。
- 見積: 4h

**T-108: ファイルストレージと完全削除（FR-112/113、§7.1）**
- 目的: データディレクトリ作成（権限700）、UUID由来のファイル名生成（ユーザー入力不使用）、ダウンロード名 `koeclone_YYYYMMDD_HHMMSS_<short-id>.wav`（FR-209）の生成、削除対象計算（参照音声・同意録音・キャッシュ・生成音声・サイドカー・一時ファイル）と一括削除。
- 依存: T-101
- 所有: `src/koeclone/storage/files.py`, `tests/unit/test_files.py`
- RED: 権限・命名形式・パストラバーサル不能（`../` を含む入力がパスに影響しない）・削除対象の網羅・削除後の不存在テストが失敗。
- GREEN: pathlibベースの最小実装。
- REFACTOR: パス組み立ての共通化まで。
- 検証: `pytest tests/unit/test_files.py -q`
- 完了: AC-09の削除対象計算がテストで保証される。
- 見積: 4h

**T-109: サイドカー生成（FR-007）**
- 目的: 生成WAVと同名のJSONサイドカーを作る。`ai_generated=true`、生成日時、エンジン名、モデル版、音声ID、原文SHA-256、合成用テキストSHA-256、読み修正一覧を含む。
- 依存: T-101
- 所有: `src/koeclone/domain/sidecar.py`, `tests/unit/test_sidecar.py`
- RED: 必須キーの網羅・ハッシュ一致・同名`.json`パスのテストが失敗。
- GREEN: dict構築とJSON書き出しの最小実装。
- REFACTOR: スキーマ定数化まで。
- 検証: `pytest tests/unit/test_sidecar.py -q`
- 完了: AC-08のサイドカー要件を満たす。
- 見積: 2h

**T-110: 同意文チャレンジと同意記録（FR-001〜005/009）**
- 目的: セッションごとに異なる同意文の生成（FR-003）、アップロード時の権利確認文、同意記録（同意日時・方式・同意文・元音声SHA-256・アプリ版・直接録音時は同意録音SHA-256）の構築、同意記録なしプロフィールでの生成拒否判定。
- 依存: T-101
- 所有: `src/koeclone/domain/consent.py`, `tests/unit/test_consent.py`
- RED: 連続取得で同意文が異なる・記録必須項目の網羅・同意なし拒否のテストが失敗。
- GREEN: テンプレート+乱数要素の同意文生成と記録dataclassの最小実装。
- REFACTOR: 文言定数の整理まで。
- 検証: `pytest tests/unit/test_consent.py -q`
- 完了: AC-01/FR-005の判定ロジックがテストで保証される。
- 見積: 3h

**ゲート G1:** T-101〜T-110 の全テスト成功（`pytest tests/unit tests/integration -q`）、削除対象計算に漏れなし、Claudeレビューで Blocking/Major ゼロ。

### Phase 2: 音声エンジン・ジョブ（Codex。実モデル実行のみClaude）

**T-201: エンジンインターフェースと偽エンジン**
- 目的: `SpeechEngine` プロトコル（§5.2）と、決定的な短いWAVを生成しウォーターマーク検出を設定どおり返す `FakeEngine` を作る。**ウォーターマーク無効化に相当する引数・設定を持たせない（FR-006）。**
- 依存: G1
- 所有: `src/koeclone/engines/base.py`, `src/koeclone/engines/fake.py`, `tests/unit/test_fake_engine.py`
- RED: インターフェース準拠・生成WAVの存在・検出結果制御のテストが失敗。
- GREEN: 無音でない固定波形WAVを書き出す最小実装。
- REFACTOR: WAV書き出し補助の整理まで。
- 検証: `pytest tests/unit/test_fake_engine.py -q`
- 完了: 以降の全テストが偽エンジンで実行可能。
- 見積: 3h

**T-202: FFmpegラッパー（FR-107、§7.1）**
- 目的: デコード、モノラル・24kHz以上WAVへの正規化、無音・異常音を避けた10〜30秒参照区間の抽出、分割合成結果のWAV結合。**全て引数配列+固定オプションで実行し、ユーザー由来文字列をコマンドへ連結しない。**
- 依存: G1
- 所有: `src/koeclone/media/ffmpeg.py`, `tests/integration/test_ffmpeg.py`
- RED: プログラム生成WAV/MP3 fixtureに対する正規化出力仕様（モノラル・サンプルレート）、参照区間長、結合後長のテストが失敗。
- GREEN: subprocessラッパーの最小実装。
- REFACTOR: コマンド組み立ての共通化まで。
- 検証: `pytest tests/integration/test_ffmpeg.py -q`（FFmpeg必須）
- 完了: 全テスト成功。`shell=True` 不使用。
- 見積: 5h

**T-203: Chatterboxアダプター（§7.4、FR-008）**
- 目的: Chatterbox Multilingual V3 のロード（プロセス内1回）、`ja` 固定合成、MPS初期化失敗時の理由記録と設定許可時のみのCPUフォールバック、生成直後のPerThウォーターマーク検出。
- 依存: T-201、G0（PoCでAPI形状確定済み）
- 所有: `src/koeclone/engines/chatterbox.py`, `tests/engine_contract/test_chatterbox.py`
- RED: 契約テスト（`@pytest.mark.real_model` マーカー付き）: 入出力型、モデル版文字列、ウォーターマーク無効化設定が存在しないこと、生成音声から検出成功。マーカーなし環境ではスキップされることを先に確認。
- GREEN: PoCコードを基にしたアダプター最小実装。
- REFACTOR: デバイス選択ロジックの整理まで。
- 検証: `pytest tests/engine_contract -q`（通常はスキップ）。実モデル実行はClaudeが `pytest tests/engine_contract -q -m real_model` を基準Macで実施。
- 完了: 偽環境でスキップ動作、実機で契約テスト成功（Claude確認）。
- 見積: 6h

**T-204: 単一ジョブキュー（FR-204/205/206）**
- 目的: 同時実行1件のキュー、`queued → running → succeeded/failed` の状態遷移、失敗時の利用者向けメッセージ+内部エラーID、部分音声を完成扱いにしない後始末。
- 依存: G1
- 所有: `src/koeclone/worker/queue.py`, `tests/unit/test_queue.py`
- RED: 直列実行・状態遷移・例外時failed・後続ジョブ継続のテストが失敗。
- GREEN: スレッド+Queueの最小実装。
- REFACTOR: 状態遷移の集約まで。
- 検証: `pytest tests/unit/test_queue.py -q`
- 完了: 全テスト成功。
- 見積: 4h

**T-205: 生成パイプライン統合（FR-005/007/008/207）**
- 目的: 同意確認 → 合成用テキスト（読み修正適用済み）分割 → エンジン合成 → WAV結合（モノラル、モデル標準サンプルレート維持）→ **ウォーターマーク検出（不検出なら failed とし再生・DL不可）** → サイドカー生成 → DB/ファイル保存、を1ジョブとして統合。
- 依存: T-104, T-107, T-108, T-109, T-110, T-201, T-202, T-204
- 所有: `src/koeclone/worker/pipeline.py`, `tests/integration/test_pipeline.py`
- RED: 偽エンジンで、成功系（WAV+サイドカー+succeeded）、検出失敗系（failed・音声非公開）、同意なし拒否、分割結合順序のテストが失敗。
- GREEN: 各ドメイン部品を呼ぶ直列パイプラインの最小実装。
- REFACTOR: ステップ関数分割まで。
- 検証: `pytest tests/integration/test_pipeline.py -q`
- 完了: AC-05/AC-08のサーバー側動作が偽エンジンで保証される。
- 見積: 6h

**ゲート G2:** 偽エンジンでの全テスト成功 + 実モデル契約テスト成功（Claudeが基準Macで実行・記録）。

### Phase 3: API・UI・E2E（Codex）

**T-301: FastAPI基盤（§7.1、AC-10）**
- 目的: アプリ生成、`127.0.0.1` 固定バインドの起動スクリプト、CORS無効（ミドルウェア不追加＝同一オリジンのみ）、リクエストサイズ50MB制限、静的`web/`配信、`GET /api/health`、AppError→安定エラーコードJSONのグローバルハンドラ、OpenAPIは開発時のみ。ログに音声データ・全文テキスト・秘密情報を出さないログ設定。
- 依存: G2
- 所有: `src/koeclone/api/app.py`, `scripts/run.sh`, `tests/integration/test_app.py`
- RED: health応答・サイズ超過413・エラー形式・CORSヘッダ不在のテストが失敗。
- GREEN: 最小のアプリファクトリ実装。
- REFACTOR: ハンドラ整理まで。
- 検証: `pytest tests/integration/test_app.py -q`
- 完了: 全テスト成功。バインド先を外部公開へ変える設定項目がない。
- 見積: 4h

**T-302: 同意API（FR-003）**
- 目的: `GET /api/consent/challenge` でセッションごとに異なる同意文を返す。
- 依存: T-301, T-110
- 所有: `src/koeclone/api/consent.py`, `tests/integration/test_consent_api.py`
- RED: 2回取得で異なる文・形式のテストが失敗。
- GREEN: ドメイン関数を呼ぶ薄いルータ。
- REFACTOR: なし（薄い層を維持）。
- 検証: `pytest tests/integration/test_consent_api.py -q`
- 完了: テスト成功。
- 見積: 1h

**T-303: プロフィール作成API（FR-101〜109/111/112、AC-02/03/04）**
- 目的: `POST /api/voices` を実装。直接録音（10〜60秒）/WAV・MP3アップロード（50MB・10〜180秒）両対応。同意情報必須（FR-002/004）。`stage=validate` で形式照合→品質検査→正規化→試聴用音声返却、`stage=confirm` で確定・同意記録保存・テスト文生成ジョブ投入（FR-111）・一時ファイル削除（FR-112）。拒否時は理由コードを返す（AC-04）。
- 依存: T-301, T-105, T-106, T-110, T-202, T-205, T-107, T-108
- 所有: `src/koeclone/api/voices.py`（作成部）, `tests/integration/test_voices_create_api.py`
- RED: 同意なし拒否、短すぎ/長すぎ/偽装/無音/クリッピング拒否、正常2段階作成、2件目拒否（FR-110）のテストが偽エンジン+fixtureで失敗。
- GREEN: ドメイン部品を組み合わせる薄いルータ実装。
- REFACTOR: バリデーション呼び出しの整理まで。
- 検証: `pytest tests/integration/test_voices_create_api.py -q`
- 完了: AC-02/03/04のAPI側が成功。
- 見積: 8h

**T-304: プロフィール取得・削除API（FR-113、AC-09）**
- 目的: `GET /api/voices/current`、`DELETE /api/voices/current`（参照音声・同意録音・キャッシュ・関連生成音声・サイドカー・DB行の一括削除）。
- 依存: T-303（同一ファイルのため**順次**）
- 所有: `src/koeclone/api/voices.py`（取得・削除部）, `tests/integration/test_voices_delete_api.py`
- RED: 削除後にプロフィール・生成物・音声取得が全て404/不存在になるテストが失敗。
- GREEN: `storage/files.py` の削除対象計算を呼ぶ実装。
- REFACTOR: なし。
- 検証: `pytest tests/integration/test_voices_delete_api.py -q`
- 完了: AC-09のAPI側が成功。
- 見積: 3h

**T-305: 合成API（FR-201〜218、AC-05/06/07）**
- 目的: `POST /api/syntheses/preview`（読み修正検証+強調用メタ付き合成用テキスト返却）、`POST /api/syntheses`（生成前検証+「AI生成音声として利用する」確認フラグ必須+ジョブ作成）、`GET /api/syntheses/{id}`、`GET /api/syntheses/{id}/audio`（succeeded かつ watermark_detected=true のみ配信）。
- 依存: T-301, T-102, T-103, T-104, T-205
- 所有: `src/koeclone/api/syntheses.py`（preview/作成/状態/audio部）, `tests/integration/test_syntheses_api.py`
- RED: AC-07の全拒否ケース（エンジン未呼出をFakeEngineの呼出回数で検証）、AC-06プレビュー、正常ジョブ完了とWAV取得、未完成音声の403/404のテストが失敗。
- GREEN: 薄いルータ+キュー投入の実装。
- REFACTOR: レスポンス整形の共通化まで。
- 検証: `pytest tests/integration/test_syntheses_api.py -q`
- 完了: AC-05/06/07のAPI側が成功。
- 見積: 6h

**T-306: 履歴API（FR-301〜304）**
- 目的: `GET /api/syntheses`（新しい順、生成日時・原文先頭80文字・読み修正件数・音声長・状態）、`DELETE /api/syntheses/{id}`、`DELETE /api/syntheses`（全削除。音声・サイドカー・DB行）。
- 依存: T-305（同一ファイルのため**順次**）
- 所有: `src/koeclone/api/syntheses.py`（履歴部）, `tests/integration/test_history_api.py`
- RED: 並び順・表示項目・個別/全削除後の不存在テストが失敗。
- GREEN: 最小実装。
- REFACTOR: なし。
- 検証: `pytest tests/integration/test_history_api.py -q`
- 完了: FR-301〜304が成功。
- 見積: 3h

**T-307: UI基盤・同意画面（FR-001/002、AC-01）**
- 目的: 画面骨格（同意→登録→合成→履歴のタブ/ステップ）、初回同意画面（規約・禁止用途表示、同意チェック完了まで録音・アップロードを無効化）、APIクライアント共通JS。
- 依存: T-301, T-302
- 所有: `src/koeclone/web/index.html`, `src/koeclone/web/style.css`, `src/koeclone/web/js/app.js`, `src/koeclone/web/js/api.js`
- RED: E2E（T-313）で検証するため、本タスクではJSの純粋関数（状態判定）に対する軽量テストを `tests/unit/` 相当のNode不使用構成では置けない → **UIタスクの検証はT-313のPlaywrightテストと手動確認手順で行う**（本タスクは確認手順書きをタスク報告に含める）。
- GREEN: 静的ファイルの最小実装。
- REFACTOR: CSS整理まで。
- 検証: `pytest tests/integration/test_app.py -q`（静的配信）+ ブラウザ手動確認手順の提出
- 完了: 同意前に登録UIが無効であることをClaudeが手動確認。
- 見積: 4h

**T-308: 直接録音UI（FR-102/103/108、AC-02）**
- 目的: マイク権限要求、権限拒否時の復旧手順表示、同意文表示、録音開始/経過時間/停止/試聴/破棄/再録音、`stage=validate`→試聴→`stage=confirm` のフロー。
- 依存: T-307, T-303
- 所有: `src/koeclone/web/js/record.js`
- RED/GREEN/REFACTOR: T-307と同様、検証はE2E+手動。MediaRecorder操作を関数分離して実装。
- 検証: T-313のE2E（録音はPlaywrightの偽メディアストリームを使用）+ 手動確認
- 完了: AC-02のUIフローがE2Eで成功。
- 見積: 6h

**T-309: アップロードUI（FR-104、FR-004、AC-03）**
- 目的: WAV/MP3選択、アップロード前と確定前の2回の本人権利確認、クライアント側の事前サイズ・拡張子チェック（最終判定はサーバー）、正規化後音声の試聴と確定/破棄/別ファイル選択。
- 依存: T-307, T-303
- 所有: `src/koeclone/web/js/upload.js`
- 検証: T-313のE2E + 手動確認
- 完了: AC-03のUIフローがE2Eで成功。
- 見積: 4h

**T-310: テキスト入力・読み修正モードUI(FR-210〜215、AC-06)**
- 目的: 通常/読み修正モード切替、原文からの範囲選択、読み入力、修正一覧の追加・編集・削除、修正部分を強調した原文と合成用テキストのプレビュー（`/api/syntheses/preview` 使用）、「AI生成音声として利用する」確認。
- 依存: T-307, T-305
- 所有: `src/koeclone/web/js/synthesis.js`（入力・修正部）
- 検証: T-313のE2E + 手動確認
- 完了: AC-06のUIフローがE2Eで成功。
- 見積: 6h

**T-311: 進行表示・プレイヤー・ダウンロードUI（FR-205/208/209）**
- 目的: ジョブ状態の1秒間隔ポーリング表示、生成完了後の再生・一時停止・シーク・音量、WAVダウンロード（FR-209の命名）。
- 依存: T-310（同一ファイル `synthesis.js` のため**順次**）
- 所有: `src/koeclone/web/js/synthesis.js`（進行・再生部）
- 検証: T-313のE2E + 手動確認
- 完了: AC-05のUI側がE2Eで成功。
- 見積: 4h

**T-312: 履歴UI（FR-301〜304）**
- 目的: 履歴一覧表示、再生、ダウンロード、個別削除、全削除（確認ダイアログ付き、UC-03）。
- 依存: T-307, T-306
- 所有: `src/koeclone/web/js/history.js`
- 検証: T-313のE2E + 手動確認
- 完了: 履歴フローがE2Eで成功。
- 見積: 3h

**T-313: E2Eテスト（Playwright）**
- 目的: 偽エンジン+テストデータで、直接録音登録（偽メディアストリーム）、WAV/MP3アップロード登録、通常生成、部分読み修正生成、再生、ダウンロード、個別削除、プロフィール完全削除のE2Eを自動化。実在人物の音声fixtureは使わない。
- 依存: T-307〜T-312（Playwright導入はClaudeが事前に実施）
- 所有: `tests/e2e/`（配下全ファイル）
- RED: 各シナリオを先に書き、UI未完部分の失敗を確認しながらT-307〜312と往復。
- GREEN: セレクタ・待機の最小実装。
- REFACTOR: Page Object化まで。
- 検証: `pytest tests/e2e -q`（または `playwright test`。導入形態はClaudeが確定）
- 完了: 全シナリオ成功。
- 見積: 8h

**ゲート G3:** API統合テストと主要E2Eが全件成功。Claudeが手動でUC-01〜03を通しで確認。

### Phase 4: 安全性・品質検証（Claude主導）

**T-401（Codex）: セキュリティ自動テスト**
- 目的: localhostバインド検証、CORSヘッダ不在、50MB/1,000文字制限、パストラバーサル試行（`../` を含むID・ファイル名）、エラーレスポンスに内部情報が含まれない、ログに音声・全文テキストが出ない、のテストを追加。
- 依存: G3
- 所有: `tests/integration/test_security.py`
- RED: 各検査を先に書き、未対応箇所があれば失敗として報告（**修正は該当ファイル所有タスクとしてClaudeが別途契約を発行**。本タスクで他ファイルを直さない）。
- GREEN: テスト自体の完成。
- REFACTOR: 共通fixture化まで。
- 検証: `pytest tests/integration/test_security.py -q`
- 完了: 全テスト成功（不合格項目の修正完了後）。
- 見積: 4h

| ID | 担当 | 内容 |
|---|---|---|
| P4-C1 | Claude | セキュリティレビュー（コード全体）、依存監査（`pip-audit` 相当）、ライセンス最終確認（依存とモデル重み） |
| P4-C2 | Claude+利用者 | 実モデルでの手動品質評価: 日本語20評価文（異常継続0件・明瞭性95%以上）、固有名詞等10文の部分読み全件正解、本人らしさ4/5以上。未達時は再録音・別ファイルを案内し低品質プロフィールを自動採用しない |
| P4-C3 | Claude | オフライン動作確認（ネットワーク遮断状態で登録・生成・再生・保存・削除）、完全削除の実ファイル検証、AC-01〜AC-10の最終突合、リリース判定 |

**ゲート G4（リリース品質ゲート）:** §3.1 の成功条件を全て満たす。

---

## 8. 依存関係と並行実行ルール

- **同一ファイルを所有するタスクは必ず順次実行**: T-303→T-304（`voices.py`）、T-305→T-306（`syntheses.py`）、T-310→T-311（`synthesis.js`）。
- **互いに素なファイル群のみ並行委譲可**。並行可能な代表例:
  - Phase 1: {T-102, T-103, T-105, T-106, T-107, T-108, T-109, T-110}（T-104のみT-103の後）
  - Phase 2: {T-201, T-202, T-204} 並行 → T-203, T-205
  - Phase 3: T-301後に {T-302, T-305系} と {T-303系}、UIは T-307 後に {T-308, T-309, T-310系, T-312}
- フェーズゲート未通過のまま次フェーズのタスクを委譲しない。

```text
C0 → P0(C1→X1→C2) → G0
G0 → T-101 → [T-102,T-103,T-105,T-106,T-107,T-108,T-109,T-110] → T-104 → G1
G1 → [T-201,T-202,T-204] → T-203, T-205 → G2
G2 → T-301 → T-302 / (T-303→T-304) / (T-305→T-306) → T-307 → [T-308,T-309,(T-310→T-311),T-312] → T-313 → G3
G3 → T-401 + P4-C1〜C3 → G4
```

---

## 9. ClaudeからCodexへの委譲単位

- 委譲単位は §7 のタスク1件とする。1委譲 = 1タスク契約 = 完了後にClaudeが1コミット（対象ファイルを個別 `git add`）。
- 各委譲時にClaudeは次を明記した契約文書を渡す: 目的、受入条件、所有ファイル、変更禁止ファイル、RED/GREEN/REFACTORの期待、検証コマンド、報告フォーマット。
- Codexは実装完了時に、テスト実行結果の生出力、変更ファイル一覧、ブロッカー有無を報告する。
- Claudeは委譲前に `codex-companion status <job> --json` の `workspaceRoot` が対象を含むことを確認する（Claude Codeは `/Users/Jobs1/AI` から起動する運用）。
- Codexがサンドボックス等でブロックされた場合はClaudeが直接実装で代替する（同一契約・同一規律）。

---

## 10. テスト戦略と品質ゲート

| 種別 | 対象 | 実行タイミング |
|---|---|---|
| Unit | 入力検証、読み修正、合成用テキスト、品質判定、形式照合、分割、状態遷移、削除対象計算、サイドカー、同意 | 各タスクのRED/GREEN、G1以降常時 |
| Integration | SQLite、FFmpeg、API全エンドポイント、偽エンジンでのパイプライン | G1〜G3 |
| Engine contract | Chatterboxアダプターの入出力・モデル版・**ウォーターマーク無効化設定の不在**・検出成功。`real_model` マーカーで分離し基準Macのみ実行 | G0、G2、G4 |
| E2E | 直接録音・WAV/MP3登録、通常生成、部分読み修正、再生、ダウンロード、削除 | G3 |
| Security | localhost限定、CORS、サイズ制限、パストラバーサル、ログ漏えい、完全削除 | T-401 + P4-C1 |
| Manual quality | 20文明瞭性、読み修正10文、本人らしさ、異常継続、処理時間、ピークメモリ | P0-C2、P4-C2 |

- 通常のテスト実行は偽エンジンのみを使い、実モデルをロードしない。
- 実在人物の音声をテストfixtureやGitへ含めない。fixtureは全てプログラム生成音とする。
- 実機PoC・実モデル評価の実測値は `docs/poc-results.md` に追記して履歴を残す。

---

## 11. リスク・ロールバック・撤退基準

### 11.1 リスク（仕様書 §14 を計画へ反映）

| ID | リスク | 計画上の対応 |
|---|---|---|
| R-01 | macOS/MPSで依存が動かない | Phase 0 を最初に実施。CPUフォールバック（T-203）と代替エンジン切替基準を明記 |
| R-02 | 日本語の類似度・明瞭性不足 | P0-C2/P4-C2 の評価文ゲート、低品質プロフィール不採用 |
| R-03 | 入力外発話・反復 | 文字数上限（T-102/104）、分割合成（T-104/205）、20文ゲート、異常時failed破棄（T-205） |
| R-04 | 他人の声のアップロード登録 | 同意2段階確認（T-303/309）、同意記録とハッシュ保存（T-110）、外部公開機能を作らない |
| R-05 | 音声データ漏えい | localhost固定（T-301）、外部送信コード禁止、権限700（T-108）、ログ抑制（T-301/401）、完全削除（T-108/304） |
| R-06 | ライセンス変更 | P0-C1でバージョン・ハッシュ固定、P4-C1で再確認 |
| R-07 | 生成待ち時間 | 単一ロード、キュー、1秒間隔の進行表示（T-311）、G0性能ゲート |
| R-08 | ウォーターマーク検出器の仕様変更 | モデル版固定、契約テスト（T-203）を実モデルゲートに含める |
| R-09 | MPS初期化失敗 | 理由記録+設定許可時のみCPUフォールバック（T-203） |
| R-10 | 読み修正範囲のずれ | コードポイント範囲+`surface`同時検証（T-103）、不一致は拒否 |

### 11.2 ロールバック / 撤退基準

- **エンジン撤退（G0）**: Chatterboxが速度（10秒音声/60秒以内）・音質・ウォーターマーク検出・ライセンスのいずれかで不合格 → Coqui XTTS v2 等を同一基準で比較。全候補不合格ならMVP保留をユーザーへ報告。
- **タスク単位のロールバック**: 1タスク=1コミットのため、問題コミットを `git revert`（Claudeのみ）で戻せる。Codexにリセット系操作はさせない。
- **品質撤退（G4）**: P4-C2の品質基準未達が録音品質起因なら再録音を案内。エンジン起因ならG0へ戻り代替比較。
- **フェーズ差戻し**: ゲートでBlocking/Major指摘が出た場合、指摘解消タスクを発行し同一ゲートを再判定する。

---

## 12. 未決事項（実装開始前またはPhase 0で確定）

| # | 事項 | 種別 | 確定方法 |
|---|---|---|---|
| 1 | 基準Macの機種・メモリ・空きディスク | ユーザー確認事項 | Phase 0開始前にユーザーへ確認 |
| 2 | 生成音声の保存期間（現案: 利用者が削除するまで） | ユーザー確認事項 | 現案で仮確定。異議なければそのまま |
| 3 | 類似度と速度の優先順位 | ユーザー確認事項 | P0-C2の実測を見せて判断を仰ぐ |
| 4 | 将来の多言語対応 | ユーザー確認事項 | MVPは `ja` 固定。設計はengineのlanguage引数で拡張余地のみ確保 |
| 5 | WAV以外の出力 | ユーザー確認事項 | MVPはWAVのみ。要望があれば次期 |
| 6 | アプリ内ロックの要否 | ユーザー確認事項 | MVPはOSログイン依存 |
| 7 | FR-106の閾値（無音率・音量・クリッピング判定の実数値） | PoC確認事項 | P0-C2で実測確定し、T-105の設定既定値へ反映 |
| 8 | ChatterboxのPythonバージョン・torch/MPS互換 | PoC確認事項 | P0-C1/C2で確認 |
| 9 | PerThウォーターマーク検出APIの利用方法 | PoC確認事項 | P0-C2で確認しT-203契約へ反映 |
| 10 | `POST /api/voices` の2段階化（stage方式）は仕様§9の範囲内の実装詳細とする | 仮定 | 仕様書改訂時に追認を求める |
| 11 | Playwrightの導入形態（pytest-playwright想定） | 仮定 | T-313委譲前にClaudeが確定・導入 |

---

## 13. 全体見積もりと推奨実装順序

### 13.1 見積もり合計

| フェーズ | Codex実装 | Claude作業（初期化・依存・PoC・レビュー・検証・Git） | 小計 |
|---|---|---|---|
| Phase C0 | — | 1.6h | 1.6h |
| Phase 0 | 2h | 8h（導入・実測・ADR） | 10h |
| Phase 1 | 31h | 6h | 37h |
| Phase 2 | 24h | 6h（実モデル検証含む） | 30h |
| Phase 3 | 60h | 10h | 70h |
| Phase 4 | 4h | 12h（レビュー・品質評価・最終判定） | 16h |
| **合計** | **121h** | **43.6h** | **約165h** |

見積もりは1タスクずつの直列実行を仮定した保守的な値。並行委譲により暦日ベースでは短縮可能。

### 13.2 推奨実装順序

1. **C0-1〜C0-4**（Claude）: リポジトリ・環境
2. **P0-C1 → P0-X1 → P0-C2 → G0**: エンジン合否を最初に確定（最大リスクの先行検証）
3. **T-101 →（並行: T-102/103/105/106/107/108/109/110）→ T-104 → G1**
4. **（並行: T-201/202/204）→ T-203・T-205 → G2**
5. **T-301 →（並行: T-302 / T-303→T-304 / T-305→T-306）→ T-307 →（並行: T-308/309/(310→311)/312）→ T-313 → G3**
6. **T-401 + P4-C1〜C3 → G4 → リリース判定・ユーザー報告**

---

## 14. 実装開始前チェックリスト

- [ ] 本計画書がユーザーに承認されている
- [ ] 仕様書のMVP範囲・本人限定方針・保存方針が承認されている（仕様書 §16）
- [ ] 未決事項 #1（基準Mac情報）がユーザーから得られている
- [ ] C0-1: ローカルGit初期化・`.gitignore`・initial commit・remote設定・push が完了している
- [ ] C0-2: Python 3.11 venv と開発依存が導入され `pytest` が動く
- [ ] C0-3: FFmpeg / ffprobe が利用可能
- [ ] Codexの書込範囲（workspaceRoot）に `/Users/Jobs1/AI/koeclone` が含まれることを確認済み
- [ ] Codex向け共通禁止事項（Git操作・依存導入・所有外ファイル変更の禁止）が各契約テンプレートに記載済み
- [ ] Phase 0 タスク契約（P0-X1）と検証コマンドが作成済み
- [ ] 既存ユーザー差分と変更予定ファイルが競合していない（現状ファイルは docs のみで競合なし）

---

*本計画は Phase 0 の実測結果および未決事項の確定に応じて改訂する。改訂時はバージョンを上げ、変更点を本節に追記する。*
