# タスク契約 Phase 1: ドメイン・ストレージ（T-101〜T-110 統合契約）

| 項目 | 内容 |
|---|---|
| 契約ID | PHASE1（T-101〜T-110 の統合契約） |
| 文書所有者 | Claude（唯一の指揮官）。本文書の変更はClaudeのみが行う |
| 実装担当 | Codex |
| 上位文書 | `docs/implementation-plan.md` §7 Phase 1 / §8、`docs/system-specification.md` §6・§10・§11 |
| 参照文書 | `docs/poc-results.md` P0-C2 §5（FR-106確定閾値）、`docs/adr/0001-speech-engine.md` |
| 前提ゲート | G0 合格済み（2026-07-24、Chatterbox Multilingual V3 採用確定） |
| ブランチ | `agent/phase1-domain-storage`（Git操作は全てClaudeが実施） |
| 見積 | 合計31h（タスク別は各節に記載） |

本契約は実装計画 §7 Phase 1 の10タスクを1文書に統合したものである。
計画と本契約が矛盾した場合は作業を止めてClaudeへ報告する（黙って直さない）。

---

## 0. 委譲プロセスと依存順

### 0.1 依存グラフ（この順序以外で着手しない）

```text
T-101（設定・エラーコード基盤）
  ├→ T-102（テキスト入力検証）
  ├→ T-103（読み修正検証）──→ T-104（合成用テキスト・分割）
  ├→ T-105（音声品質判定）
  ├→ T-106（ファイル形式照合）
  ├→ T-107（SQLiteストレージ）
  ├→ T-108（ファイルストレージ・完全削除）
  ├→ T-109（サイドカー生成）
  └→ T-110（同意文・同意記録）
全タスク完了 → 全体検証（§13）→ G1判定（Claude）
```

- **T-101 が最初。** T-102〜T-110 は T-101 完了後に着手可（互いに素なファイルを所有するため順不同）。
- **T-104 のみ T-103 完了後。**
- 1タスク = 1委譲 = 1報告。タスク完了ごとにClaudeがレビューし、対象ファイルを個別に
  `git add <file>` してコミットする。複数タスクをまとめて報告しない。

### 0.2 委譲前提（Claudeが T-101 委譲前に整備する。Codexの作業ではない）

- `src/koeclone/`・`src/koeclone/domain/`・`src/koeclone/storage/` のパッケージ骨格
  （空の `__init__.py`）と、`pyproject.toml` への pytest import 解決設定（`pythonpath = ["src"]` 相当）。
- `import koeclone` が解決できない場合、Codexは `pyproject.toml` を触らず停止条件（§1.3）に従い報告する。

---

## 1. 共通規定（全タスク厳守）

### 1.1 禁止事項（違反は契約違反として差し戻す）

1. **契約外ファイルの作成・変更・削除の禁止。** 各タスクの「所有ファイル」以外は一切触らない。
   特に `pyproject.toml`、`uv.lock`、`.gitignore`、`docs/` 配下、`scripts/` 配下、
   既存の `tests/unit/test_poc_args.py`、各 `__init__.py`。
2. **一切のGit操作の禁止**: `git add` / `commit` / `checkout` / `switch` / `merge` / `rebase` /
   `reset` / `stash` / worktree 操作を含む全て。コミットはClaudeのみが行う。
3. **依存関係の導入・更新・削除の禁止**（`pip install`、`uv add`、`uv sync` 等）。依存導入はClaudeのみ。
4. **実モデルの実行・ロードの禁止。** Phase 1 の実装・テストで `chatterbox` / `torch` /
   `torchaudio` / `perth` を import しない。モデル重みのダウンロード・更新も禁止。
   Phase 1 のコードは Python 標準ライブラリのみで実装する（サードパーティが必要になったら停止して報告）。
5. **ネットワークへ音声・テキストを送信するコードの追加禁止。**
6. **実在人物の音声をテストfixtureに使うことの禁止。** fixtureは全てテスト内でプログラム生成する
   （`.gitignore` が `*.wav` を除外するため、バイナリ音声ファイルのコミット自体が不可能な構成である）。
7. 仕様外機能の追加禁止（設定項目・引数・エンドポイント等を勝手に増やさない）。

### 1.2 TDD（RED → GREEN → REFACTOR）

- RED: 各タスクに記載のテストを先に書き、**未実装状態で失敗する実出力を確認**してから実装に進む。
- GREEN: テストが通る最小限の実装のみ。テストを通す以上の機能を追加しない。
- REFACTOR: 各タスクの「許容範囲」まで。毎回テストが通ったままであることを確認する。

### 1.3 停止条件（該当したら作業を止め、実出力とともに報告する）

- 本契約と上位文書（実装計画・仕様書）の間に矛盾・算術ミス・実装不能な指示を発見した場合
- 所有ファイル以外を変更しなければテストを通せないと判明した場合
- import不能・依存不足など、Claudeの責務（依存導入・環境整備）が必要になった場合
- 同じテスト失敗が2回の修正試行後も解消しない場合
- サンドボックス制約・権限エラーで作業が進められない場合

### 1.4 報告フォーマット（タスクごと）

1. タスクID と変更ファイル一覧（所有ファイルのみであること）
2. 検証コマンドの生出力（RED時の失敗出力と、完了時の成功出力）
3. ブロッカーの有無と内容
4. 契約からの逸脱があればその理由（原則として逸脱禁止）

---

## 2. G0確定値（本契約で使用する定数）

### 2.1 FR-106 品質閾値（`docs/poc-results.md` P0-C2 §5 で実測確定済み）

T-105 の設定既定値として **必ず以下の値を使用する**（閾値は設定注入とし、これを既定値にする）:

| 判定 | 確定既定値 |
|---|---|
| 無音率拒否 | **20ms窓のRMSが -50 dBFS 未満**を無音窓と判定し、無音窓の比率が **80%以上**で拒否 |
| クリッピング拒否 | **ピークが -1.0 dBFS を超える**、または **\|sample\| ≥ 0.999** のサンプルが1つでも存在すれば拒否 |
| 平均音量拒否 | 全体RMSが **-35 dBFS 未満**、または **-10 dBFS 超**で拒否（許容範囲: -35〜-10 dBFS） |

### 2.2 長さ制限（FR-103 / FR-104）

| 登録方式 | 許容再生時間 |
|---|---|
| 直接録音 | 10〜60秒 |
| ファイルアップロード | 10〜180秒（ファイルサイズ最大50MB） |

### 2.3 テキスト制限（FR-201 / FR-217）

- 原文: 1〜1,000文字（Unicodeコードポイント単位）。空白のみは拒否。
- 読み置換後の合成用テキスト: 最大2,000文字。超過は拒否。

---

## 3. T-101: 設定・エラーコード基盤

| 項目 | 内容 |
|---|---|
| 依存 | なし（Phase 1の起点） |
| 所有ファイル | `src/koeclone/config.py`, `src/koeclone/errors.py`, `tests/unit/test_config.py` |
| 見積 | 2h |

**目的**: アプリ全体が参照する設定モジュールと安定エラーコード列挙を作る。

**設定（`config.py`）の要件**:

- `host` は **`"127.0.0.1"` 固定**。変更する手段（引数・環境変数・setter）を一切提供しない。
- `port` は既定 8000（int、環境変数 `KOECLONE_PORT` で上書き可）。
- データディレクトリ: 既定はホームディレクトリ配下の `koeclone-data`
  （`Path.home() / "koeclone-data"`）。環境変数 **`KOECLONE_DATA_DIR`** で上書き可。
- FR-106 閾値（§2.1 の無音判定窓 20ms / 無音RMS閾値 -50 dBFS / 無音率 0.80 /
  ピーク上限 -1.0 dBFS / サンプル絶対値上限 0.999 / RMS範囲 -35〜-10 dBFS）と
  長さ制限（§2.2）・テキスト制限（§2.3）を既定値として保持する。
- デバイス設定: `device` 既定 `"mps"`、**CPUフォールバック許可フラグ** `allow_cpu_fallback`
  既定 `False`（環境変数 `KOECLONE_ALLOW_CPU_FALLBACK` で上書き可）。
- frozen dataclass ベースとし、環境変数からの生成関数を提供する。

**エラーコード（`errors.py`）の要件**:

- `str` 値を持つ Enum（または同等の定数群）。**全コード値が一意**で、`ERR_` プレフィックスの
  大文字スネークケースとする。
- 最低限、次のコードを定義する（後続タスク・フェーズが参照する。名称はこのとおりとする）:
  `ERR_TEXT_EMPTY` / `ERR_TEXT_TOO_LONG` / `ERR_TEXT_WHITESPACE_ONLY` /
  `ERR_SYNTHESIS_TEXT_TOO_LONG` /
  `ERR_READING_EMPTY` / `ERR_READING_INVALID_CHARS` / `ERR_OVERRIDE_RANGE_INVALID` /
  `ERR_OVERRIDE_SURFACE_MISMATCH` / `ERR_OVERRIDE_OVERLAP` / `ERR_OVERRIDE_NO_KANJI` /
  `ERR_AUDIO_TOO_SHORT` / `ERR_AUDIO_TOO_LONG` / `ERR_AUDIO_MOSTLY_SILENT` /
  `ERR_AUDIO_CLIPPING` / `ERR_AUDIO_LEVEL_OUT_OF_RANGE` /
  `ERR_FILE_TOO_LARGE` / `ERR_FILE_FORMAT_MISMATCH` / `ERR_FILE_CORRUPTED` /
  `ERR_FILE_NO_AUDIO` / `ERR_FILE_UNSUPPORTED_FORMAT` /
  `ERR_NO_CONSENT` / `ERR_PROFILE_ALREADY_EXISTS` / `ERR_WATERMARK_NOT_DETECTED` /
  `ERR_INTERNAL`
- 追加コードが必要になった場合はここへ追記してよい（一意性・命名規則を維持）。

**RED**（`tests/unit/test_config.py` を先に書き、失敗を確認）:

1. `host` が常に `"127.0.0.1"` であり、変更手段が存在しない
2. `KOECLONE_DATA_DIR` でデータディレクトリを上書きできる（monkeypatch使用）
3. 環境変数未設定時に既定値（データディレクトリ・port・デバイス・閾値）が返る
4. エラーコードの値が全件一意である
5. FR-106閾値の既定値が §2.1 の確定値と一致する

**GREEN**: frozen dataclass + Enum の最小実装。
**REFACTOR**: 定数整理まで。

**受入条件**: 上記テスト全成功。host変更手段が存在しない。
**検証**: `pytest tests/unit/test_config.py -q`

---

## 4. T-102: テキスト入力検証（FR-201/202/217）

| 項目 | 内容 |
|---|---|
| 依存 | T-101 |
| 所有ファイル | `src/koeclone/domain/text_validation.py`, `tests/unit/test_text_validation.py` |
| 見積 | 2h |

**目的**: 原文テキストの検証関数を作る。1〜1,000文字（Unicodeコードポイント単位、
`len(text)` で判定）、空白のみ（全角空白・タブ・改行含む）を拒否、制御文字・HTML・スクリプトを
**実行せず単なる文字列として扱う**（サニタイズや除去はせず、検証のみ。FR-202）。
エラーは `errors.py` のコード（`ERR_TEXT_EMPTY` / `ERR_TEXT_TOO_LONG` /
`ERR_TEXT_WHITESPACE_ONLY`）で返す。

**RED**: 次のケースを先に書き失敗を確認 — 0文字 / 1,001文字 / 空白のみ（半角・全角・改行混在）/
制御文字混在（検証は通し、文字列として保持されること）/ HTMLタグ文字列（同上）/
1文字・1,000文字ちょうどの正常系境界。

**GREEN**: 長さ・空白判定の最小実装。
**REFACTOR**: 判定関数の分割まで。

**受入条件**: 全テスト成功。AC-07 の入力系拒否ケース（空白のみ・1,001文字以上）を網羅。
**検証**: `pytest tests/unit/test_text_validation.py -q`

---

## 5. T-103: 読み修正の検証（FR-211〜215, R-10）

| 項目 | 内容 |
|---|---|
| 依存 | T-101 |
| 所有ファイル | `src/koeclone/domain/pronunciation.py`, `tests/unit/test_pronunciation.py` |
| 見積 | 3h |

**目的**: 読み修正 `PronunciationOverride` の定義と検証を作る。

```python
@dataclass(frozen=True)
class PronunciationOverride:
    surface: str      # 原文の該当文字列（漢字を1文字以上含む）
    start: int        # Unicodeコードポイント単位・半開区間
    end: int
    reading: str      # ひらがな/カタカナ/長音記号/中点/空白のみ
```

**検証規則（全て必須）**:

1. `reading` はひらがな・カタカナ・長音記号（ー）・中点（・）・空白のみ許可。
   空文字、漢字・英数字・記号を含む読みは拒否（`ERR_READING_EMPTY` / `ERR_READING_INVALID_CHARS`）。
2. `0 <= start < end <= len(text)`（コードポイント半開区間）。範囲外・逆転は拒否
   （`ERR_OVERRIDE_RANGE_INVALID`）。
3. `text[start:end] == surface` をサーバー側で検証。不一致は拒否（`ERR_OVERRIDE_SURFACE_MISMATCH`）。
4. `surface` は漢字（CJK統合漢字。「々」等の反復記号を漢字扱いに含めてよい）を1文字以上含む。
   含まなければ拒否（`ERR_OVERRIDE_NO_KANJI`）。
5. 複数修正の範囲重複は拒否（`ERR_OVERRIDE_OVERLAP`）。隣接（`a.end == b.start`）は重複ではない。

**RED**: 正常系（原文「明日は日本橋へ行きます」の「日本橋」→「にほんばし」）/ 漢字を含む読み /
空読み / 範囲外・start≧end / 元文字列不一致 / 重複範囲（隣接は許可）/ surfaceに漢字なし、
の各テストを先に書き失敗を確認。

**GREEN**: 文字種正規表現と範囲検証の最小実装。
**REFACTOR**: 検証順序の整理まで。

**受入条件**: AC-06 / AC-07 の読み修正系ケースを網羅して成功。
**検証**: `pytest tests/unit/test_pronunciation.py -q`

---

## 6. T-104: 合成用テキスト生成と長文分割（FR-203/216/217/218）

| 項目 | 内容 |
|---|---|
| 依存 | **T-103**（Phase 1 で唯一の後続タスク） |
| 所有ファイル | `src/koeclone/domain/synthesis_text.py`, `tests/unit/test_synthesis_text.py` |
| 見積 | 3h |

**目的**:

1. 検証済みの読み修正を**原文の後方の範囲から順に**（`start` 降順で）指定読みへ置換して
   合成用テキストを作る。**原文文字列は変更しない**（FR-216）。
2. 置換後の合成用テキストが2,000文字を超えたら拒否（`ERR_SYNTHESIS_TEXT_TOO_LONG`、FR-217）。
3. 合成用テキストを句読点境界（。、！？等）で分割し、**順序を維持**して返す（FR-203）。
4. 通常モード（修正リストが空）では原文をそのまま合成用テキストとして使用する（FR-218）。

**RED**: AC-06 の例（「明日は日本橋へ行きます」+「日本橋」→「にほんばし」で
合成用テキストが「明日はにほんばしへ行きます」になり、**原文が不変**であること）/
複数修正（置換で後方インデックスがずれないこと＝後方から置換）/ 2,001文字拒否・2,000文字許可 /
句読点分割の順序維持と結合時の全文一致 / 修正なし時の原文パススルー、を先に書き失敗を確認。

**GREEN**: 逆順置換と句読点分割の最小実装。
**REFACTOR**: 分割規則の関数化まで。

**受入条件**: 全テスト成功。原文が変更されないことをテストで保証。
**検証**: `pytest tests/unit/test_synthesis_text.py -q`

---

## 7. T-105: 音声品質判定（FR-103/104/106）

| 項目 | 内容 |
|---|---|
| 依存 | T-101（閾値既定値は §2.1 のG0実測確定値） |
| 所有ファイル | `src/koeclone/domain/audio_quality.py`, `tests/unit/test_audio_quality.py` |
| 見積 | 4h |

**目的**: PCMサンプル列（float、-1.0〜1.0、サンプルレート引数付き）に対して以下を判定し、
合格または**拒否理由コード**を返す。閾値は設定（T-101）から注入し、既定値は §2.1 / §2.2 の確定値とする。

1. **長さ**: 登録方式に応じ 録音10〜60秒 / アップロード10〜180秒。範囲外は
   `ERR_AUDIO_TOO_SHORT` / `ERR_AUDIO_TOO_LONG`。
2. **無音率**: 20ms窓のRMSが -50 dBFS 未満を無音窓とし、無音窓比率 ≥ 80% で
   `ERR_AUDIO_MOSTLY_SILENT`。
3. **クリッピング**: ピーク > -1.0 dBFS、または |sample| ≥ 0.999 のサンプルが存在で
   `ERR_AUDIO_CLIPPING`。
4. **平均音量**: 全体RMSが -35 dBFS 未満または -10 dBFS 超で `ERR_AUDIO_LEVEL_OUT_OF_RANGE`。

**RED**: fixtureを**全てテスト内でプログラム生成**（正弦波・無音・スケーリング。
実在人物の音声・外部ファイル不使用）し、次を先に書き失敗を確認 —
ほぼ無音（無音率>80%）拒否 / クリッピング波形拒否 / 低音量（RMS<-35dBFS）拒否 /
過大音量（RMS>-10dBFS）拒否 / 短すぎ・長すぎ拒否（両方式の境界）/
正常波形（PoC実測相当: ピーク≈-10dBFS、RMS≈-25dBFS、無音率≈25%）合格。

**GREEN**: RMS・ピーク・無音率計算の最小実装（標準ライブラリのみ。numpy等は使わない）。
**REFACTOR**: 数値計算の共通化まで。

**受入条件**: AC-04 の品質系拒否（ほぼ無音・クリッピング・短すぎ・長すぎ）を網羅して成功。
**検証**: `pytest tests/unit/test_audio_quality.py -q`

---

## 8. T-106: ファイル形式照合（FR-104/105）

| 項目 | 内容 |
|---|---|
| 依存 | T-101 |
| 所有ファイル | `src/koeclone/domain/file_probe.py`, `tests/unit/test_file_probe.py` |
| 見積 | 4h |

**目的**: 拡張子を信用せず、次の3情報を照合してWAV/MP3を検証する。

1. **ファイルシグネチャ**: WAV = `RIFF....WAVE`、MP3 = MP3フレーム同期（`0xFFEx`）または `ID3` タグ。
2. **申告MIMEタイプ**: シグネチャ判定と矛盾しないこと。
3. **実デコード結果**: ffprobe相当の情報（コーデック・音声ストリーム有無・再生時間）。
   **ffprobe呼び出しは注入可能な関数**とし、単体テストでは偽実装を注入する
   （本タスクで実ffprobeバイナリを実行しない）。

**拒否対象**: 形式偽装（拡張子とシグネチャ/デコード結果の不一致 → `ERR_FILE_FORMAT_MISMATCH`）、
破損・デコード不能・暗号化（`ERR_FILE_CORRUPTED`）、音声ストリームなし（`ERR_FILE_NO_AUDIO`）、
WAV/MP3以外（`ERR_FILE_UNSUPPORTED_FORMAT`）、50MB超（`ERR_FILE_TOO_LARGE`）、
再生時間10〜180秒範囲外（`ERR_AUDIO_TOO_SHORT` / `ERR_AUDIO_TOO_LONG`）。

**RED**: fixture（テスト内でバイト列を直接生成。偽装拡張子 = MP3シグネチャ+`.wav` 申告 /
破損ヘッダ / 空ファイル / 50MB超サイズ / 音声なしデコード結果 / 正常WAV・MP3ヘッダ）で
拒否・合格テストを先に書き失敗を確認。

**GREEN**: シグネチャ判定 + 注入されたprobe結果照合の最小実装。将来の実行に備える
コマンド組み立てがある場合も**引数配列のみ**とし、シェル文字列連結・`shell=True` を書かない。

**REFACTOR**: 判定の表駆動化まで。

**受入条件**: AC-04 の形式系拒否（容量超過・形式偽装・破損）を網羅して成功。
シェル文字列連結が存在しない。
**検証**: `pytest tests/unit/test_file_probe.py -q`

---

## 9. T-107: SQLiteストレージ（仕様書§10）

| 項目 | 内容 |
|---|---|
| 依存 | T-101 |
| 所有ファイル | `src/koeclone/storage/db.py`, `tests/integration/test_db.py` |
| 見積 | 4h |

**目的**: 標準ライブラリ `sqlite3` + 生SQLで、仕様書§10 の2テーブルのスキーマ作成と
リポジトリ（CRUD）を実装する。**列の追加・削除・改名は禁止**（仕様書§10 が唯一の正）。

**`voice_profiles` テーブル（VoiceProfile。全14列）**:

| 列 | SQLite型 | 内容・制約 |
|---|---|---|
| `id` | TEXT PRIMARY KEY | UUID文字列 |
| `display_name` | TEXT NOT NULL | 画面表示名 |
| `source_mode` | TEXT NOT NULL | `direct_recording` または `file_upload`（CHECK制約） |
| `source_format` | TEXT NOT NULL | 録音コンテナ、WAV、MP3 |
| `source_sha256` | TEXT NOT NULL | 元音声のハッシュ |
| `reference_path` | TEXT NOT NULL | 正規化済み参照音声のパス |
| `reference_sha256` | TEXT NOT NULL | 改ざん・重複確認用 |
| `consent_method` | TEXT NOT NULL | `live_challenge` または `upload_declaration`（CHECK制約） |
| `consent_text` | TEXT NOT NULL | 同意文または権利確認文 |
| `consent_audio_path` | TEXT NULL | 直接録音モードの同意録音パス |
| `consent_audio_sha256` | TEXT NULL | 直接録音モードの同意録音ハッシュ |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `engine` | TEXT NOT NULL | エンジン識別子 |
| `model_version` | TEXT NOT NULL | モデル版 |

**`synthesis_jobs` テーブル（SynthesisJob。全16列）**:

| 列 | SQLite型 | 内容・制約 |
|---|---|---|
| `id` | TEXT PRIMARY KEY | UUID文字列 |
| `voice_id` | TEXT NOT NULL | `voice_profiles.id` への外部キー |
| `text` | TEXT NOT NULL | 原文 |
| `text_sha256` | TEXT NOT NULL | 原文ハッシュ |
| `synthesis_text` | TEXT NOT NULL | 読み修正適用済み合成用テキスト |
| `synthesis_text_sha256` | TEXT NOT NULL | 合成用テキストハッシュ |
| `pronunciation_overrides` | TEXT NOT NULL | `surface`/`start`/`end`/`reading` 一覧のJSON文字列（空は `[]`） |
| `language` | TEXT NOT NULL | MVPでは `ja` 固定 |
| `status` | TEXT NOT NULL | `queued`/`running`/`succeeded`/`failed`（CHECK制約） |
| `audio_path` | TEXT NULL | 成功時のWAVパス |
| `sidecar_path` | TEXT NULL | AI生成情報JSONパス |
| `duration_ms` | INTEGER NULL | 生成音声長 |
| `watermark_detected` | INTEGER NULL | 0/1/NULL（boolean/null） |
| `error_code` | TEXT NULL | 失敗分類 |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `completed_at` | TEXT NULL | 完了日時 |

**リポジトリ要件**:

- VoiceProfile: 作成・現在プロフィール取得・削除。**有効プロフィールは1件のみ**（FR-110）:
  既に1件存在する状態での2件目作成は `ERR_PROFILE_ALREADY_EXISTS` 相当のエラーで拒否。
- SynthesisJob: 作成・ID取得・状態/結果更新・**新しい順（`created_at` 降順）一覧**（FR-301）・
  個別削除・全削除。
- 外部キー有効化（`PRAGMA foreign_keys = ON`）。DBパスは引数注入（テストは一時ディレクトリのDBを使用）。

**RED**: 一時DBで、スキーマ作成 / プロフィール作成・取得 / 2件目プロフィール拒否 /
ジョブ作成・状態遷移更新 / 履歴が新しい順 / 個別・全削除後の不存在、を先に書き失敗を確認。

**GREEN**: 生SQLでのスキーマとリポジトリ最小実装（ORM禁止）。
**REFACTOR**: SQL定数の整理まで。

**受入条件**: 全テスト成功。**全列が上表（=仕様書§10）と一致**し、追加列がない。
**検証**: `pytest tests/integration/test_db.py -q`

---

## 10. T-108: ファイルストレージと完全削除（FR-112/113、§7.1）

| 項目 | 内容 |
|---|---|
| 依存 | T-101 |
| 所有ファイル | `src/koeclone/storage/files.py`, `tests/unit/test_files.py` |
| 見積 | 4h |

**目的**:

1. **データディレクトリ作成**: 設定のデータディレクトリ配下にサブディレクトリ
   （参照音声・同意録音・生成音声・一時領域）を作成し、**権限を 700（0o700）**にする。
2. **ファイル名生成**: **UUIDのみから生成**し、ユーザー入力（表示名・元ファイル名等）を
   ファイル名・パスに一切使わない（パストラバーサル防止、§7.1）。
3. **ダウンロード名生成**: `koeclone_YYYYMMDD_HHMMSS_<short-id>.wav`（FR-209）。
   `<short-id>` はジョブUUIDの先頭8文字とする。
4. **削除対象計算と一括削除**（AC-09、FR-113）: プロフィール削除時の削除対象として
   **正規化済み参照音声・同意録音・キャッシュ・関連生成音声・サイドカーJSON・一時ファイル**を
   全て列挙し、一括削除する関数。削除後に対象が存在しないことを保証する。

**RED**: ディレクトリ権限が0o700 / ファイル名がUUID由来のみ / `../` や `/etc/passwd` 等を含む
入力を与えてもデータディレクトリ外のパスが生成されない / ダウンロード名の形式
（正規表現 `koeclone_\d{8}_\d{6}_[0-9a-f]{8}\.wav`）/ 削除対象計算が6分類を網羅 /
一括削除後に全対象が不存在、を先に書き失敗を確認。

**GREEN**: pathlibベースの最小実装。
**REFACTOR**: パス組み立ての共通化まで。

**受入条件**: AC-09 の削除対象計算がテストで保証される。パストラバーサル不能。
**検証**: `pytest tests/unit/test_files.py -q`

---

## 11. T-109: サイドカー生成（FR-007）

| 項目 | 内容 |
|---|---|
| 依存 | T-101 |
| 所有ファイル | `src/koeclone/domain/sidecar.py`, `tests/unit/test_sidecar.py` |
| 見積 | 2h |

**目的**: 生成WAVと**同名（拡張子のみ `.json`）**のサイドカーJSONを作る。必須キー:

| キー | 内容 |
|---|---|
| `ai_generated` | 常に `true` |
| `generated_at` | 生成日時（ISO 8601 UTC） |
| `engine` | エンジン名 |
| `model_version` | モデル版 |
| `voice_id` | 音声プロフィールID |
| `text_sha256` | 原文のSHA-256 |
| `synthesis_text_sha256` | 合成用テキストのSHA-256 |
| `pronunciation_overrides` | 読み修正一覧（`surface`/`start`/`end`/`reading`） |

**RED**: 必須8キーの網羅 / `ai_generated` が `true` 固定 / 原文・合成用テキストから計算した
SHA-256とキー値の一致 / `foo.wav` → `foo.json` のパス生成 / 読み修正なし時は空配列、
を先に書き失敗を確認。

**GREEN**: dict構築とJSON書き出し（`ensure_ascii=False`）の最小実装。
**REFACTOR**: スキーマ定数化まで。

**受入条件**: AC-08 のサイドカー要件を満たす。
**検証**: `pytest tests/unit/test_sidecar.py -q`

---

## 12. T-110: 同意文チャレンジと同意記録（FR-001〜005/009）

| 項目 | 内容 |
|---|---|
| 依存 | T-101 |
| 所有ファイル | `src/koeclone/domain/consent.py`, `tests/unit/test_consent.py` |
| 見積 | 3h |

**目的**:

1. **同意文チャレンジ生成**（FR-003）: セッション（取得）ごとに**異なる**日本語同意文を生成する。
   本人の声の登録への同意を宣言する定型文 + ランダム要素（日時・乱数語句等）で構成する。
2. **アップロード時の権利確認文**（FR-004）: 「自分自身の声であり、クローン作成の権利を持つ」
   ことを明示する固定文言を提供する。
3. **同意記録の構築**（FR-009）: 次の必須項目を持つ frozen dataclass —
   同意日時（ISO 8601 UTC）/ 同意方式（`live_challenge` または `upload_declaration`）/
   同意文 / 元音声SHA-256 / アプリバージョン / 直接録音時のみ同意録音SHA-256（それ以外は None）。
4. **生成拒否判定**（FR-005）: 同意記録を持たないプロフィールでの音声生成を拒否する判定関数
   （拒否時 `ERR_NO_CONSENT`）。

**RED**: 連続取得した同意文が互いに異なる / 記録必須項目の網羅（直接録音時は同意録音SHA-256必須、
アップロード時はNone許可）/ 同意記録なしでの生成要求が `ERR_NO_CONSENT` で拒否される、
を先に書き失敗を確認。

**GREEN**: テンプレート+乱数要素の同意文生成と記録dataclassの最小実装。
**REFACTOR**: 文言定数の整理まで。

**受入条件**: AC-01 / FR-005 の判定ロジックがテストで保証される。
**検証**: `pytest tests/unit/test_consent.py -q`

---

## 13. 全体検証（G1ゲート入力。Phase 1 の最終確認）

T-101〜T-110 の全タスク完了後、リポジトリルートの仮想環境で以下を実行し、
**生出力を最終報告に含める**。

```bash
pytest tests/unit tests/integration -q
ruff check src tests
```

- 完了条件: 全テスト成功（既存 `tests/unit/test_poc_args.py` を含む）かつ ruff 指摘ゼロ。
- 実モデル（chatterbox / torch / perth）がテスト収集・実行で一切ロードされないこと。
- G1判定（削除対象計算の漏れ確認・Blocking/Major レビュー）はClaudeが実施する。
  Codexの自己申告のみで完了とはしない。

## 14. Git・依存導入の禁止(再掲・厳守)

Codexは本契約において、いかなるGit操作も依存関係の導入・変更も実モデルの実行も行わない。
コミットはClaudeがタスクごとにレビュー後、所有ファイルを個別に `git add <file>` して行う
（`git add .` / `-A` 禁止）。
