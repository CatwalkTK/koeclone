# タスク契約 Phase 2: 音声エンジン・ジョブ実行（T-201〜T-205 統合契約）

| 項目 | 内容 |
|---|---|
| 契約ID | PHASE2（T-201〜T-205 の統合契約） |
| 文書所有者 | Claude（唯一の指揮官）。本文書の変更はClaudeのみが行う |
| 実装担当 | Codex |
| 上位文書 | `docs/implementation-plan.md` §7 Phase 2 / §8、`docs/system-specification.md` §6・§7・§10・§11 |
| 参照文書 | `docs/poc-results.md`（P0-C1 §2/§3/§7、P0-C2 §5/§8）、`docs/adr/0001-speech-engine.md`、`docs/task-contract-phase1.md` |
| 前提ゲート | G1 合格済み（T-101〜T-110 完了、`pytest -q` 109 passed、`ruff check src tests` 指摘ゼロ） |
| ブランチ | `agent/phase2-engine-worker`（Git操作は全てClaudeが実施） |
| 見積 | 合計24h（T-201 3h / T-202 5h / T-203 6h / T-204 4h / T-205 6h） |

本契約は実装計画 §7 Phase 2 の5タスクを1文書に統合したものである。
計画・仕様と本契約が矛盾した場合、または本契約に矛盾・算術ミス・実装不能な指示を見つけた場合は、
**黙って直さず作業を止めてClaudeへ報告する**（§1.4 停止条件）。

---

## 0. 委譲プロセスと依存順

### 0.1 依存グラフ（この順序以外で着手しない）

```text
T-201（SpeechEngineプロトコル・FakeEngine・例外基底）
  ├→ T-202（FFmpegラッパー）─┐
  ├→ T-204（単一ジョブキュー）─┼→ T-205（生成パイプライン統合 + チャンク再結合）
  └→ T-203（Chatterboxアダプター）  ※T-205とは互いに素、並行可
```

- **T-201 が最初。** T-201 は `src/koeclone/errors.py` に共通例外基底を追加するため、
  T-202 / T-203 / T-204 はいずれも T-201 完了後に着手する。
- T-202 と T-204 は互いに素なファイルを所有するため **並行可**。
- T-205 は T-202・T-204 完了後。T-203 とは所有ファイルが互いに素なため **並行可**
  （T-205 は FakeEngine のみを使い、Chatterbox に依存しない）。
- 1タスク = 1委譲 = 1報告 = 1コミット。複数タスクをまとめて報告しない。
  タスク完了ごとにClaudeがレビューし、所有ファイルを個別に `git add <file>` してコミットする。

### 0.2 委譲前提（Claudeが整備済み。Codexの作業ではない）

コミット `35b9c83`（`chore: prepare phase 2 packages and test marker`）で以下を整備済み:

- 空のパッケージ骨格: `src/koeclone/engines/__init__.py`、`src/koeclone/media/__init__.py`、
  `src/koeclone/worker/__init__.py`、`tests/engine_contract/__init__.py`
- `pyproject.toml` の `[tool.pytest.ini_options]` に `real_model` マーカーを登録
  （`markers = ["real_model: 実モデル（Chatterbox Multilingual V3）をロードする契約テスト。基準Macでのみ実行する"]`）

**Codexはこれらのファイルを変更しない**（`__init__.py` は空のまま。`pyproject.toml` は触らない）。

### 0.3 依存関係の状態（Claude確認済み・2026-08-10）

Phase 2 に必要な依存は**すべて導入済みであり、追加・変更は不要**である。
Codexが依存不足を理由に停止する必要はない。不足を発見した場合は §1.4 に従い報告する。

| パッケージ | 版 | 区分 | Phase 2 での用途 |
|---|---|---|---|
| `torch` | 2.6.0 | 直接依存 | T-203（デバイス判定・テンソル） |
| `torchaudio` | 2.6.0 | 直接依存 | T-203（WAV保存・読み込み） |
| `resemble-perth` | 1.0.1 | 直接依存 | T-203（ウォーターマーク検出） |
| `chatterbox-tts` | git `5de7a54a` | 直接依存 | T-203（`ChatterboxMultilingualTTS`） |
| `static-ffmpeg` | 3.0 | 直接依存 | T-202（ffmpeg/ffprobe の解決） |
| `pytest` / `ruff` | 8.4+ / 0.12+ | dev依存 | 全タスク |

- **`librosa` / `soundfile` / `numpy` は `chatterbox-tts` 経由の推移的依存であり、直接依存ではない。**
  T-203 の音声読み込みには **`torchaudio.load`（直接依存）を使い、`librosa` を import しない。**
  `numpy` は `torch` 同梱のため、テンソル→ndarray 変換（`.numpy()`）での利用のみ許可する。
- T-201 / T-202 / T-204 / T-205 の実装は **Python標準ライブラリのみ**で書く
  （`wave`、`subprocess`、`queue`、`threading`、`json`、`pathlib`、`uuid`、`math` 等）。
  サードパーティが必要だと判断した場合は実装せず停止して報告する。

### 0.4 FFmpeg 実バイナリの状態（Claude確認済み・2026-08-10）

`static_ffmpeg` の実バイナリは取得済みで、ネットワークアクセスなしに利用できる。

| 項目 | 実測値 |
|---|---|
| 解決API | `static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()` → `(ffmpeg, ffprobe)` のタプル |
| ffmpeg 実体 | `<venv>/lib/python3.11/site-packages/static_ffmpeg/bin/darwin_arm64/ffmpeg`（存在確認済み） |
| ffprobe 実体 | `<venv>/lib/python3.11/site-packages/static_ffmpeg/bin/darwin_arm64/ffprobe`（存在確認済み） |
| バージョン | ffmpeg / ffprobe とも 7.0（arm64 静的ビルド） |

**この絶対パスをソースコード・テストコードへ書いてはならない**（§1.2-7）。
必ず上記APIで解決し、かつ呼び出し側から注入できる形にする（詳細は T-202）。

---

## 1. 共通規定（全タスク厳守）

### 1.1 TDD（RED → GREEN → REFACTOR）

- **RED**: 各タスクに記載のテストを先に書き、**未実装状態で失敗する実出力を確認**してから実装に進む。
- **GREEN**: テストが通る最小限の実装のみ。テストを通す以上の機能を追加しない。
- **REFACTOR**: 各タスクの「許容範囲」まで。毎回テストが通ったままであることを確認する。

### 1.2 禁止事項（違反は契約違反として差し戻す）

1. **契約外ファイルの作成・変更・削除の禁止。** 各タスクの「所有ファイル」以外は一切触らない。
   特に `pyproject.toml`、`uv.lock`、`.gitignore`、`docs/` 配下、`scripts/` 配下、
   各 `__init__.py`、Phase 1 の既存実装・既存テスト。
   - **例外は2件のみ**（いずれも**追記のみ**。既存の関数・クラス・列挙メンバーの
     改名・削除・シグネチャ変更・振る舞い変更は禁止）:
     T-201 が `src/koeclone/errors.py` に例外基底を追加する。
     T-205 が `src/koeclone/domain/synthesis_text.py` にチャンク再結合関数を追加する。
2. **一切のGit操作の禁止**: `git add` / `commit` / `checkout` / `switch` / `merge` / `rebase` /
   `reset` / `stash` / worktree 操作を含む全て。コミットはClaudeのみが行う。
3. **依存関係の導入・更新・削除の禁止**（`pip install`、`uv add`、`uv sync`、`uv lock` 等）。
   §0.3 のとおり追加は不要である。
4. **実モデルのロード・実行の禁止（Codex）。** `chatterbox` / `torch` / `torchaudio` / `perth` を
   **実行時に import・ロードしない**。T-203 の実装ではこれらを**関数内の遅延 import** として
   記述するのみで、Codexの検証実行では一度もロードされてはならない。
   モデル重みのダウンロード・更新も禁止。**実モデルでの実行はClaudeのみが行う**（§5.6）。
5. **ウォーターマークを無効化・除去できる引数・設定・環境変数・分岐を作らない（FR-006、MVP範囲外）。**
   `disable_watermark` / `watermark=False` / `skip_watermark` 等に相当するものを、
   公開API・内部関数・設定・環境変数のいずれにも設けない。
   （T-201 の FakeEngine が持つ**検出結果スタブ**のみ例外。§3.3 の条件を厳守すること。）
6. **`shell=True` の禁止。** 外部プロセス起動は `subprocess.run(<リスト>, shell=False, ...)` に限る。
   コマンド**文字列**の組み立て、`os.system`、`os.popen`、`subprocess.getoutput`、
   `subprocess.call("...", shell=True)`、シェルメタ文字を含む引数の生成をすべて禁止する。
   ユーザー由来文字列（テキスト・表示名・元ファイル名）を外部コマンドの引数に渡さない。
7. **FFmpeg / FFprobe の固定絶対パスをソースへ書くことの禁止。** §0.4 の実測パスは
   環境確認の記録であって実装値ではない。実装は `static_ffmpeg` のAPIで解決し、
   かつ**呼び出し側から注入できる**ようにする（テストではその注入点を使う）。
8. **ネットワーク送信・取得コードの禁止。** 実装・テストのいずれからも外部通信を行わない
   （Hugging Face を含む）。T-203 はキャッシュ済みスナップショットのみを参照する。
9. **実在人物の音声をテストfixtureに使うことの禁止。** fixtureは全てテスト内でプログラム生成する。
   音声バイナリをリポジトリへ追加しない（`.gitignore` により `*.wav` はコミット不可）。
10. **タイミング依存テストの禁止。** `time.sleep` による待ち合わせでスレッドの完了を判定しない。
    `threading.Event` / `queue.join()` / 本契約が定める `join(timeout=...)` を使い、決定的にする。
11. **ログ・エラーへの機微情報の出力禁止。** 音声データ、原文・合成用テキストの全文、
    外部コマンドの生 stderr、スタックトレースを、利用者に返る値へ含めない（§7.1）。
12. **仕様外機能の追加禁止**（設定項目・引数・エンドポイント・エラーコードを勝手に増やさない）。

### 1.3 エラー返却の統一方針（Phase 2 全タスク共通・必読）

Phase 1（ドメイン層）と Phase 2（実行層）で返し方が異なる。**混在させないこと。**

| 層 | 失敗の表し方 |
|---|---|
| ドメイン層（Phase 1 既存: `text_validation` / `pronunciation` / `synthesis_text` / `audio_quality` / `file_probe` / `consent`） | **例外を投げず `ErrorCode \| None` を返す**（既存方針を変えない） |
| ストレージ層（Phase 1 既存: `storage/db.py`） | `StorageError(code)` を送出（既存方針を変えない） |
| **Phase 2 実行層（engines / media / worker）** | **`KoecloneError` のサブクラスを送出する** |

規定:

1. T-201 が `src/koeclone/errors.py` に次を**追記**する（既存 `ErrorCode` は一切変更しない）:

   ```python
   class KoecloneError(Exception):
       """安定エラーコードを持つアプリ内例外の基底。"""

       def __init__(self, code: ErrorCode) -> None:
           self.code = code
           super().__init__(code.value)
   ```

   既存の `StorageError`（`storage/db.py`）は Phase 1 の所有物であり、**本契約では変更しない**
   （基底の差し替えもしない）。Phase 2 側で `StorageError` を捕捉する場合は `except StorageError` を使う。

2. Phase 2 の各層は自分の所有ファイル内でサブクラスを定義する:
   `EngineError(KoecloneError)`（`engines/base.py`）、`FFmpegError(KoecloneError)`（`media/ffmpeg.py`）、
   `PipelineError(KoecloneError)`（`worker/pipeline.py`）。いずれも **`code: ErrorCode` 属性を必ず持つ**。
3. **`ErrorCode` へ新しいメンバーを追加しない。** Phase 2 で新たに必要になる失敗はすべて
   既存メンバーへ写像する。写像表:

   | 失敗事象 | 使用する ErrorCode |
   |---|---|
   | 同意記録なしでの生成要求 | `ERR_NO_CONSENT` |
   | 読み修正・テキスト検証の失敗 | ドメイン関数が返した ErrorCode をそのまま使う |
   | ウォーターマーク不検出 | `ERR_WATERMARK_NOT_DETECTED` |
   | FFmpeg 実行失敗・出力不正 | `ERR_INTERNAL` |
   | モデルロード失敗・デバイス不可・リビジョン不一致 | `ERR_INTERNAL` |
   | 上記以外の想定外例外 | `ERR_INTERNAL` |

4. **日本語の利用者向け文言を Phase 2 に持たせない。** `ErrorCode` → 利用者向けメッセージの変換は
   Phase 3（API層 T-301）の責務である。Phase 2 が返すのは `ErrorCode` と内部エラーID のみ（FR-206）。
5. 例外メッセージには `code.value` 以外を入れない。原因の詳細はログ（WARN/ERROR）にのみ記録し、
   そこにも音声データ・テキスト全文・生 stderr を含めない。

### 1.4 停止条件（該当したら作業を止め、実出力とともに報告する）

- 本契約と上位文書（実装計画・仕様書・ADR・PoC結果）の間に矛盾・算術ミス・実装不能な指示を発見した場合
- 所有ファイル以外を変更しなければテストを通せないと判明した場合
- import不能・依存不足など、Claudeの責務（依存導入・環境整備）が必要になった場合
- 同じテスト失敗が2回の修正試行後も解消しない場合
- サンドボックス制約・権限エラーで作業が進められない場合
- 実モデルのロードが必要だと判断した場合（**Codexは実行しない**。Claudeへ引き渡す）

### 1.5 報告フォーマット（タスクごと）

1. タスクID と変更ファイル一覧（所有ファイルのみであること）
2. 検証コマンドの生出力（RED時の失敗出力と、完了時の成功出力）
3. ブロッカーの有無と内容
4. 契約からの逸脱があればその理由（原則として逸脱禁止）

---

## 2. G1 からの申し送り事項（Phase 2 で必ず守る）

### 2.1 T-111: 話者キャッシュのファイル命名（AC-09 完全削除との整合）

T-108（`src/koeclone/storage/files.py`）の `collect_deletion_targets` は、話者キャッシュを
**次の命名で削除対象に含める**実装になっている:

```python
cache=(storage_path(paths.cache, reference_id, ".cache"),)
# → <data_root>/cache/<reference_id の UUID hex（32桁・ハイフンなし）>.cache
```

したがって **Phase 2 で話者キャッシュ（話者埋め込み・条件付けの中間表現等）を書き出す実装を
入れる場合は、必ず `storage_path(paths.cache, reference_id, ".cache")` が返すパスに書く。**

- 禁止: 独自命名（`<voice_id>.pt`、`speaker_<name>.bin` 等）、
  データディレクトリ外への書き出し（`~/.cache/...`、`/tmp/...`、モデルライブラリ既定のキャッシュ等）。
  これらは AC-09（プロフィール削除で話者情報が残らないこと）を破る。
- `ALLOWED_SUFFIXES` は `.wav` / `.mp3` / `.json` / `.tmp` / `.cache` のみを許可する。
  他の拡張子を使いたくなった場合は停止して報告する（`files.py` は Phase 1 の所有物であり変更禁止）。

**MVP の方針（本契約の範囲）**: T-203 のアダプターは**話者キャッシュを作らない**。
毎回 `audio_prompt_path` に正規化済み参照WAVを渡して条件付けする（PoC の実測どおりで性能基準を満たす）。
キャッシュ導入は本契約の範囲外であり、Codexが独自に追加してはならない。
将来導入する場合の命名契約が上記である。

### 2.2 読点による細切れチャンクの再結合（60〜120文字目標）

T-104 の `split_synthesis_text` は `。、！？.!?，,` の**すべて**を境界として分割するため、
読点（`、`）が多い日本語文では 1チャンクが数文字という細切れになる。
このままエンジンへ渡すと、(a) 句の途中で切れてプロソディ（抑揚・間）が不自然になり、
(b) 呼び出し回数が増えて MPS ウォームアップ相当のオーバーヘッドが累積する。

**T-205 で、分割後のチャンクを 60〜120文字（Unicodeコードポイント）を目標に再結合する。**
根拠: PoC実測の発話速度は 5.2〜6.0 字/秒（`docs/poc-results.md` P0-C2 §3）であり、
60〜120文字は 1チャンクあたり約10〜23秒の音声に相当する。参照区間長（FR-107: 10〜30秒）と
同程度の粒度に揃えることで、自然な区切りと呼び出し回数削減を両立する。

仕様の詳細と不変条件は §7.2 に定める。**既存の `split_synthesis_text` / `build_synthesis_text` の
シグネチャと振る舞いは変更しない**（新関数の追加のみ）。

---

## 3. T-201: エンジンインターフェースと偽エンジン

| 項目 | 内容 |
|---|---|
| 依存 | G1 |
| 所有ファイル | `src/koeclone/engines/base.py`, `src/koeclone/engines/fake.py`, `src/koeclone/errors.py`（**追記のみ**）, `tests/unit/test_fake_engine.py` |
| 見積 | 3h |

**目的**: 音声エンジンを抽象化する `SpeechEngine` プロトコルと、決定的な短いWAVを生成する
`FakeEngine` を作る。以降の全テスト（T-205、Phase 3、Phase 4）は実モデルを使わず本エンジンで動く。

### 3.1 `src/koeclone/errors.py` への追記

§1.3-1 の `KoecloneError` のみを追記する。既存 `ErrorCode` のメンバー・値・順序は変更しない。

### 3.2 `src/koeclone/engines/base.py`（API契約）

```python
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from koeclone.errors import ErrorCode, KoecloneError


class EngineError(KoecloneError):
    """音声エンジン層の失敗。"""


@runtime_checkable
class SpeechEngine(Protocol):
    engine_name: str
    model_version: str

    def load(self) -> None:
        """モデルをロードする。プロセス内で1回だけ実効し、2回目以降は何もしない（冪等）。"""

    def synthesize(
        self,
        text: str,
        reference_wav: Path,
        language: str,
        *,
        output_path: Path,
    ) -> Path:
        """text を reference_wav の声で合成し、output_path へモノラルWAVを書いて返す。

        - language が "ja" 以外なら ValueError を送出する（MVPは ja 固定）。
        - load() 未実行で呼ばれた場合は EngineError(ErrorCode.ERR_INTERNAL) を送出する。
        - output_path の親ディレクトリは呼び出し側が用意する。
        """

    def detect_watermark(self, wav: Path) -> bool:
        """wav からウォーターマークを検出できたら True を返す。"""
```

**計画 §5.2 からの精緻化（Claude決定・要遵守）**: 計画の
`synthesize(self, text, reference_wav, language) -> Path` に対し、キーワード専用引数
`output_path: Path` を追加した。理由は、ファイル名・保存場所の決定は storage 層
（`storage/files.py` の UUID由来命名、§7.1 パストラバーサル防止）の責務であり、
エンジンに出力先を選ばせないためである。戻り値が `Path` である点は計画どおり
（`output_path` と同一の Path を返す）。

### 3.3 `src/koeclone/engines/fake.py`（API契約）

```python
@dataclass
class FakeEngine:
    engine_name: str = "fake"
    model_version: str = "fake-1"
    sample_rate: int = 24_000
    detect_result: bool = True          # §3.3 注記を厳守
    # 観測用（テスト専用）
    load_count: int = 0
    calls: list[tuple[str, Path, str]] = field(default_factory=list)
```

要件:

1. `load()` は `load_count` を +1 する。複数回呼んでも例外にしない（冪等性の確認に使う）。
2. `synthesize()` は
   - `load_count == 0` なら `EngineError(ErrorCode.ERR_INTERNAL)` を送出する。
   - `language != "ja"` なら `ValueError` を送出する。
   - `(text, reference_wav, language)` を `calls` へ**呼び出し順に**追記する
     （AC-07 の「エンジンを呼び出さない」検証に Phase 3 が使う）。
   - `output_path` へ **16bit PCM・モノラル・`sample_rate` Hz** のWAVを標準ライブラリ `wave` で書く。
   - 波形は**決定的**であること: 同じ `text` を与えたら**バイト列が完全に一致**する。
     無音でない固定波形とし、クリッピングしない（ピークは概ね -10 dBFS 程度）。
     長さは `text` のコードポイント数から決定論的に決める（例: 0.1秒/文字、下限0.2秒、上限5秒）。
   - `output_path` を返す。
3. `detect_watermark(wav)` は `wav` が存在しなければ `EngineError(ErrorCode.ERR_INTERNAL)`、
   存在すれば `self.detect_result` を返す。

**`detect_result` に関する注記（FR-006 との関係。厳守）**:
`detect_result` は **検出器の戻り値を差し替えるテスト専用スタブ**であり、
「ウォーターマークの付与を無効化する設定」ではない。したがって、

- `synthesize()` にウォーターマーク付与を制御する引数・分岐を**作らない**。
- `detect_result` に相当するものを `ChatterboxEngine`（T-203）へ**作らない**。
- 環境変数・`AppConfig` から `detect_result` を設定できるようにしない
  （production 経路から到達可能にしない）。

### 3.4 RED（先に書いて失敗を確認するテスト）

`tests/unit/test_fake_engine.py`:

1. `isinstance(FakeEngine(), SpeechEngine)` が True（`runtime_checkable` プロトコル準拠）
2. `engine_name` / `model_version` が非空文字列
3. `load()` 前の `synthesize()` が `EngineError` を送出し、`error.code is ErrorCode.ERR_INTERNAL`
4. `load()` 後の `synthesize()` が `output_path` を返し、ファイルが存在する
5. 生成WAVがモノラル・16bit・24,000Hz（`wave` モジュールで検査）で、フレーム数 > 0
6. 生成WAVが**無音でない**（絶対値の最大が 0 より十分大きい）かつ**クリッピングしない**
7. **決定性**: 同じ text で2回生成したファイルのバイト列が一致する。異なる text では長さが異なる
8. `language="en"` で `ValueError`
9. `calls` に呼び出しが順序どおり記録される
10. `detect_watermark` が `detect_result=True/False` に従って `True/False` を返す。
    存在しないファイルでは `EngineError`
11. **FR-006 の表層検査**: `inspect.signature(FakeEngine.synthesize)` の引数名、および
    `dir(FakeEngine)` に、`watermark` を無効化する意味の名前
    （`disable_watermark` / `no_watermark` / `skip_watermark` / `watermark_enabled` など）が
    **存在しない**こと

**GREEN**: 上記を満たす最小実装（標準ライブラリ `wave` / `math` / `struct` のみ）。
**REFACTOR**: WAV書き出し補助関数の切り出しまで。機能追加禁止。

**検証**: `.venv/bin/python -m pytest tests/unit/test_fake_engine.py -q`
**受入条件**: 全テスト成功。`ruff check src tests` 指摘ゼロ。以降のテストが FakeEngine で実行可能。

---

## 4. T-202: FFmpegラッパー（FR-107、§7.1）

| 項目 | 内容 |
|---|---|
| 依存 | T-201 |
| 所有ファイル | `src/koeclone/media/ffmpeg.py`, `tests/integration/test_ffmpeg.py` |
| 見積 | 5h |

**目的**: デコード、モノラル・24kHz WAVへの正規化、参照区間の抽出、分割合成結果のWAV結合、
および ffprobe による実デコード情報の取得を、**すべて引数配列と固定オプション**で行う。

### 4.1 バイナリ解決と注入（§1.2-7 の具体化）

```python
@dataclass(frozen=True)
class FFmpegPaths:
    ffmpeg: Path
    ffprobe: Path


def resolve_ffmpeg_paths() -> FFmpegPaths:
    """static_ffmpeg から ffmpeg / ffprobe の実体パスを解決する。

    static_ffmpeg.run.get_or_fetch_platform_executables_else_raise() を使う。
    解決に失敗した場合は FFmpegError(ErrorCode.ERR_INTERNAL) を送出する。
    """
```

- **本モジュールの全公開関数は `paths: FFmpegPaths | None = None` をキーワード引数で受け取り、
  `None` のときだけ `resolve_ffmpeg_paths()` で解決する。** これが注入点である。
- **絶対パス文字列をソース・テストへ書かない。** モジュールレベルで解決を実行しない
  （import 時に副作用を起こさない。遅延解決とする）。
- テストは `resolve_ffmpeg_paths()` で得た実パスを fixture 経由で明示注入して使う。

### 4.2 プロセス起動の規約（§1.2-6 の具体化）

```python
def _run(paths: FFmpegPaths, args: Sequence[str], *, timeout: float = 120.0) -> bytes:
    """引数配列で外部プロセスを実行し、stdout を返す。"""
```

- `subprocess.run(list(args), shell=False, capture_output=True, check=False, timeout=timeout)` を使う。
  `shell=True` / 文字列コマンド / `os.system` / `os.popen` は禁止。
- `args[0]` は必ず `str(paths.ffmpeg)` または `str(paths.ffprobe)`。
- ffmpeg 呼び出しには常に `-nostdin` と `-y`、および `-v error` を付ける。
- 戻り値が 0 以外、または期待する出力ファイルが生成されていない場合は
  `FFmpegError(ErrorCode.ERR_INTERNAL)` を送出する。**stderr を例外メッセージへ入れない**
  （必要ならログにのみ、先頭数百文字を上限として記録する）。
- `subprocess.TimeoutExpired` は `FFmpegError(ErrorCode.ERR_INTERNAL)` へ変換する。
- **ユーザー由来文字列を引数に渡さない。** 入出力パスは storage 層が生成した UUID 由来パスのみ。
  `-metadata` 等でテキストを渡さない。

### 4.3 公開API（正確な契約）

```python
def normalize_to_reference_wav(
    source: Path,
    destination: Path,
    *,
    sample_rate: int = 24_000,
    paths: FFmpegPaths | None = None,
) -> Path:
    """任意入力（WAV/MP3/録音コンテナ）を単一チャンネル・sample_rate Hz・16bit PCM の WAV へ正規化する。

    ffmpeg 引数（固定オプション。順序も固定）:
      -nostdin -y -v error -i <source> -vn -map a:0 -ac 1 -ar <sample_rate>
      -c:a pcm_s16le -f wav <destination>
    sample_rate は 24_000 未満を受け付けない（FR-107「24kHz以上」）。違反は ValueError。
    """


def probe_audio(source: Path, *, paths: FFmpegPaths | None = None) -> ProbeResult:
    """ffprobe で実デコード情報を取得し、T-106 の ProbeResult を返す。

    戻り値の型は koeclone.domain.file_probe.ProbeResult をそのまま使う（新しい型を作らない）。
    make_probe() が返す callable は T-106 の Probe = Callable[[Path], ProbeResult] を満たす。

    ffprobe 引数:
      -v error -print_format json -show_format -show_streams <source>
    - 最初の音声ストリームの codec_name を採用する。音声ストリームが無ければ has_audio=False。
    - duration は format.duration を優先し、無ければ音声ストリームの duration を使う。
      いずれも取れなければ None。
    - 実行失敗・JSON解析失敗は OSError または ValueError を送出する
      （T-106 の validate_audio_file がこれを捕捉して ERR_FILE_CORRUPTED に変換するため）。
    - 暗号化の判定材料が得られない場合 encrypted=False のままとする。
    """


def make_probe(paths: FFmpegPaths | None = None) -> Probe:
    """T-106 へ注入できる Probe callable を返す。"""


def detect_silence_ranges(
    source: Path,
    *,
    noise_dbfs: float = -50.0,
    min_silence_seconds: float = 0.5,
    paths: FFmpegPaths | None = None,
) -> list[tuple[float, float]]:
    """ffmpeg の silencedetect フィルタで無音区間 [(start, end), ...] を昇順で返す。

    ffmpeg 引数:
      -nostdin -y -v info -i <source>
      -af silencedetect=noise=<noise_dbfs>dB:d=<min_silence_seconds> -f null -
    stderr の silence_start / silence_end 行を解析する。
    末尾が silence_start のみで終わる場合、区間の終端は音声全体の長さとする。
    noise_dbfs の既定 -50.0 は AppConfig.silence_rms_dbfs（P0-C2 §5 の確定値）と整合させる。
    """


def select_reference_window(
    total_seconds: float,
    silence_ranges: Sequence[tuple[float, float]],
    *,
    min_seconds: float = 10.0,
    max_seconds: float = 30.0,
) -> tuple[float, float]:
    """参照区間の (start, duration) を決める純関数（外部プロセスを呼ばない）。

    - 無音区間で区切られた「非無音スパン」のうち最長のものを選ぶ。
    - 長さが max_seconds を超える場合はスパンの先頭から max_seconds だけ使う。
    - 最長スパンが min_seconds 未満の場合は、音声全体の先頭から
      min(total_seconds, max_seconds) を採用する（無音を含みうるフォールバック）。
    - total_seconds < min_seconds なら ValueError（呼び出し側が ERR_AUDIO_TOO_SHORT へ写像する）。
    - 同着の場合は開始が早い方を選ぶ（決定的であること）。
    """


def extract_reference_segment(
    source: Path,
    destination: Path,
    *,
    start_seconds: float,
    duration_seconds: float,
    sample_rate: int = 24_000,
    paths: FFmpegPaths | None = None,
) -> Path:
    """参照区間を切り出して正規化済みWAVとして書き出す。

    ffmpeg 引数:
      -nostdin -y -v error -ss <start> -t <duration> -i <source>
      -vn -map a:0 -ac 1 -ar <sample_rate> -c:a pcm_s16le -f wav <destination>
    duration_seconds が 10.0 未満または 30.0 超なら ValueError（FR-107）。
    start_seconds が負なら ValueError。
    """


def concat_wavs(
    sources: Sequence[Path],
    destination: Path,
    *,
    paths: FFmpegPaths | None = None,
) -> Path:
    """同一フォーマットの WAV を順序どおり連結する。

    - sources が空なら ValueError。1件なら ffmpeg を起動せず copy でよい。
    - concat demuxer を使う: 一時ディレクトリ（tempfile.TemporaryDirectory）に
      リストファイルを作り、-nostdin -y -v error -f concat -safe 0 -i <list> -c copy <destination>
    - リストファイルに書くのは sources の絶対パスのみ（UUID由来。ユーザー由来文字列を含めない）。
    - 一時ディレクトリは必ず後始末する。
    """


def wav_duration_ms(path: Path) -> int:
    """標準ライブラリ wave で WAV の長さをミリ秒（四捨五入した整数）で返す。外部プロセス不使用。"""
```

### 4.4 RED（先に書いて失敗を確認するテスト）

`tests/integration/test_ffmpeg.py`（fixture は**すべてプログラム生成**）:

1. `resolve_ffmpeg_paths()` が返す2つのパスが存在し、実行可能である
2. `normalize_to_reference_wav`: stdlib `wave` で作ったステレオ44.1kHzのWAVを入力すると、
   出力が **モノラル / 24,000Hz / 16bit** になる（`wave` で検査）。`sample_rate=16_000` は `ValueError`
3. MP3 経路: 上記WAVを ffmpeg 自身でMP3へ変換した fixture を入力にしても正規化が成功する
4. `probe_audio`: 生成WAVで `has_audio=True`、`codec_name` が `pcm_` で始まり、
   `duration_seconds` が実長と ±0.2秒で一致。MP3 fixture では `codec_name == "mp3"`
5. `probe_audio`: 音声を含まないファイル（ランダムバイト列）で `OSError` または `ValueError`
6. `make_probe()` の戻り値を T-106 の `validate_audio_file` に注入して、正常WAVで `None`（合格）が返る
7. `detect_silence_ranges`: 「無音1秒 + 正弦波2秒 + 無音1秒」の合成WAVで、
   先頭と末尾に無音区間が検出される
8. `select_reference_window`（純関数・外部プロセス不要）:
   最長非無音スパンの選択 / `max_seconds` での切り詰め / フォールバック /
   `total_seconds < min_seconds` の `ValueError` / 同着時に開始が早い方
9. `extract_reference_segment`: 12秒の合成WAVから `duration_seconds=10.0` を切り出すと
   出力長が 10.0秒 ±0.2秒。`duration_seconds=5.0` と `31.0` は `ValueError`
10. `concat_wavs`: 3つのWAV（長さの異なる正弦波）を連結すると、出力長が合計 ±0.2秒。
    **順序が維持される**こと（各チャンクを異なる周波数にして、連結後の各区間のゼロ交差数で確認する等、
    決定的な方法で検証する）。空リストは `ValueError`
11. `wav_duration_ms` が `wave` の実測と一致する
12. **セキュリティ検査**: `src/koeclone/media/ffmpeg.py` のソースを読み込み、
    `shell=True` / `os.system` / `os.popen` / `subprocess.getoutput` の文字列が**含まれない**こと。
    併せて `darwin_arm64` / `site-packages` を含む絶対パス文字列が**含まれない**こと
13. ffmpeg 失敗時（存在しない入力パス）に `FFmpegError` が送出され、`code is ErrorCode.ERR_INTERNAL` で、
    例外の文字列表現に stderr 由来の内容が含まれないこと

**GREEN**: subprocess ラッパーと各関数の最小実装。
**REFACTOR**: 引数配列組み立ての共通化（`_run` と共通オプション定数）まで。

**検証**: `.venv/bin/python -m pytest tests/integration/test_ffmpeg.py -q`
**受入条件**: 全テスト成功。`shell=True` 不使用。固定絶対パスなし。ネットワークアクセスなし。

---

## 5. T-203: Chatterboxアダプター（§7.4、FR-006/008）

| 項目 | 内容 |
|---|---|
| 依存 | T-201、G0（ADR-0001 / PoC で API 形状確定済み） |
| 所有ファイル | `src/koeclone/engines/chatterbox.py`, `tests/engine_contract/test_chatterbox.py` |
| 見積 | 6h |

**目的**: Chatterbox Multilingual V3 の `SpeechEngine` 実装。プロセス内1回ロード、`ja` 固定合成、
MPS初期化失敗時の理由記録と設定許可時のみのCPUフォールバック、生成直後の PerTh 検出。

**Codexは実モデルをロードしない（§1.2-4）。** 実動作の合否判定は Claude が §5.6 で行う。

### 5.1 確定済みの外部API（PoC実測。推測で変えない）

`docs/poc-results.md` P0-C1 §2/§3、ADR-0001 より:

```python
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

model = ChatterboxMultilingualTTS.from_pretrained(device="mps", t3_model="v3")  # V3は明示必須
wav = model.generate(text, language_id="ja", audio_prompt_path=<参照WAVのstr>)
# model.sr == 24000。generate() 内で常に PerTh ウォーターマークが付与される（無効化引数なし）
```

```python
import perth
watermarker = perth.PerthImplicitWatermarker()
score = watermarker.get_watermark(audio_ndarray, sample_rate=sr)   # 0.0 / 1.0
```

- HFモデルリビジョン（P0-C1 §4）: `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`
- 音声の読み書きは **`torchaudio`** を使う（`librosa` を import しない。§0.3）。

### 5.2 `src/koeclone/engines/chatterbox.py`（API契約）

```python
ENGINE_NAME = "chatterbox-multilingual-v3"
EXPECTED_MODEL_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
MODEL_REPO_ID = "ResembleAI/chatterbox"
SUPPORTED_LANGUAGE = "ja"


@dataclass
class ChatterboxEngine:
    device: str = "mps"
    allow_cpu_fallback: bool = False
    engine_name: str = ENGINE_NAME
    model_version: str = EXPECTED_MODEL_REVISION
    # 内部状態（公開しても可。ただし production から書き換えられる設定にしない）
    active_device: str | None = None
    fallback_reason: str | None = None

    @classmethod
    def from_config(cls, config: AppConfig) -> ChatterboxEngine: ...

    def load(self) -> None: ...
    def synthesize(self, text, reference_wav, language, *, output_path) -> Path: ...
    def detect_watermark(self, wav: Path) -> bool: ...
```

要件:

1. **遅延 import**: `chatterbox` / `torch` / `torchaudio` / `perth` を**モジュールトップで import しない**。
   `load()` / `detect_watermark()` の**関数内**で import する。
   これにより `import koeclone.engines.chatterbox` 自体は実モデルをロードせず、
   §5.5 の静的検査テストが軽量に実行できる。
2. **プロセス内1回ロード**（§7.4）: `load()` は初回のみ実際にロードし、2回目以降は即 return する。
3. **デバイス選択**:
   - `device == "mps"` のとき `torch.backends.mps.is_available()` を確認する。
   - 利用不可で `allow_cpu_fallback is True` → `active_device = "cpu"`、
     `fallback_reason` に理由を記録し、WARN ログを1行出す（音声・テキストを含めない）。
   - 利用不可で `allow_cpu_fallback is False` → `EngineError(ErrorCode.ERR_INTERNAL)` を送出する
     （黙って CPU へ落ちない。§7.4 / R-09）。
   - `device == "cpu"` のときはそのまま CPU を使う。
4. **リビジョン検証**: ロード前に、ローカルHFキャッシュが解決するリビジョンが
   `EXPECTED_MODEL_REVISION` と一致することを検証する。不一致・未取得なら
   `EngineError(ErrorCode.ERR_INTERNAL)`。
   **検証はネットワークへ出ずに行う**（`local_files_only=True` 相当、またはキャッシュの
   `refs/main` 参照）。実現方法は Codex が選んでよいが、外部通信を発生させないこと。
5. **`synthesize`**:
   - `load()` 未実行なら `EngineError(ErrorCode.ERR_INTERNAL)`。
   - `language != "ja"` なら `ValueError`。
   - `ChatterboxMultilingualTTS.from_pretrained(..., t3_model="v3")` で得たモデルの
     `generate(text, language_id="ja", audio_prompt_path=str(reference_wav))` を呼ぶ。
   - 結果テンソルを `torchaudio.save(str(output_path), wav, model.sr)` で
     **モノラル・model.sr（24,000Hz）** の WAV として書き、`output_path` を返す（FR-207）。
   - `generate()` の `exaggeration` / `cfg_weight` / `temperature` 等は**既定値のまま**とし、
     設定項目として外へ出さない（仕様外機能の追加禁止）。
6. **`detect_watermark`**:
   - `torchaudio.load(str(wav))` で読み、モノラル化して `numpy` 配列にする。
   - `perth.PerthImplicitWatermarker` のインスタンスを**保持して再利用**する（毎回生成しない）。
   - `get_watermark(audio, sample_rate=sr)` の戻り値が **0.5 以上なら True**、未満なら False。
   - 読み込み失敗は `EngineError(ErrorCode.ERR_INTERNAL)`。
7. **FR-006（厳守）**: ウォーターマークの付与・検出を無効化・迂回する引数、属性、設定、
   環境変数、条件分岐を**一切作らない**。`AppConfig` にも追加しない。

### 5.3 RED / GREEN / REFACTOR

- **RED**: §5.5 のテストを先に書き、`chatterbox.py` 未実装で失敗することを確認する
  （静的検査テストは `ModuleNotFoundError` で失敗する）。
- **GREEN**: PoCスクリプト（`scripts/poc_generate.py`）の呼び出し形を基にした最小実装。
  `scripts/poc_generate.py` は**変更しない**（所有外）。
- **REFACTOR**: デバイス選択とリビジョン検証の関数分割まで。

### 5.4 テストの分離設計（`tests/engine_contract/test_chatterbox.py`）

本ファイルは **2種類のテスト**を持つ。混在させ方を以下に固定する。

```python
import os
import pytest

REAL_MODEL_ENV = "KOECLONE_REAL_MODEL"

real_model = pytest.mark.skipif(
    os.environ.get(REAL_MODEL_ENV) != "1",
    reason="実モデル契約テストは KOECLONE_REAL_MODEL=1 の環境でのみ実行する",
)

# (A) 常時実行される静的検査（実モデルをロードしない）
def test_no_watermark_disable_surface() -> None: ...

# (B) 実モデル契約テスト（Claudeのみ実行）
@pytest.mark.real_model
@real_model
def test_loads_and_synthesizes_japanese(tmp_path) -> None: ...
```

- (B) の各テストには **`@pytest.mark.real_model` と skipif の両方**を付ける。
- モジュールトップでは `koeclone.engines.chatterbox` のみ import する
  （`chatterbox` / `torch` / `perth` は (B) の関数内で import する）。
- `KOECLONE_REAL_MODEL` 未設定の既定実行では (B) が全て skip され、実モデルはロードされない。

### 5.5 テスト項目

**(A) 常時実行（Codexが GREEN を確認する対象）**

1. `isinstance(ChatterboxEngine(), SpeechEngine)` が True
2. `engine_name == "chatterbox-multilingual-v3"`、`model_version == EXPECTED_MODEL_REVISION`
3. **FR-006 表層検査**: `ChatterboxEngine` の全公開属性名・`load` / `synthesize` /
   `detect_watermark` の全引数名に、`disable_watermark` / `no_watermark` / `skip_watermark` /
   `watermark_enabled` / `watermark=` に相当する名前が**存在しない**こと
4. **ソース検査**: `chatterbox.py` のソース文字列に `watermark` を無効化する意図の
   代入・引数（上記の名前）が現れないこと。併せて `import librosa` を含まないこと
5. `synthesize` を `load()` 前に呼ぶと `EngineError`（`code is ERR_INTERNAL`）。
   実モデルをロードしないことを保証するため、この検査は load 未実行の分岐のみを通ること
6. `language="en"` で `ValueError`（同上、モデルロード前の引数検証で弾くこと）
7. `AppConfig(device="mps", allow_cpu_fallback=False)` から `from_config` が
   期待どおりのフィールドを持つインスタンスを作ること

**(B) 実モデル（`@pytest.mark.real_model` + skipif。Claudeのみ実行）**

8. `load()` が成功し、`active_device` が `"mps"` または `"cpu"` であること。2回呼んでも再ロードしない
9. リビジョン一致検証が通ること。`EXPECTED_MODEL_REVISION` を書き換えた場合に `EngineError` になること
10. `synthesize()` が日本語テキストからWAVを生成し、モノラル・24,000Hz であること
11. 生成WAVに対し `detect_watermark()` が **True** を返すこと（AC-08 / FR-008）
12. `allow_cpu_fallback=False` で MPS 不可を模した場合に `EngineError` になること
    （実機で MPS が使える場合はこのケースを skip 理由付きで明示スキップしてよい）
13. **完全オフライン確認**: ネットワーク遮断状態で 8〜11 が成功すること
    （P0-C2 §8 引き継ぎ事項2。Claude が §5.6 で実施・記録する）

**検証（Codex）**: `.venv/bin/python -m pytest tests/engine_contract -q`
→ **(A) が passed、(B) が全て skipped** になること。実モデルが1度もロードされないこと。

**受入条件（Codex分）**: (A) 全成功・(B) 全スキップ。`ruff check src tests` 指摘ゼロ。
**受入条件（全体）**: §5.6 の Claude 実行で (B) が全成功すること。

### 5.6 実モデル実行はClaudeのみ（Codex禁止）

```bash
# Claude が基準Mac（MacBook Pro / Apple M4 Pro）で実行し、生出力を記録する
KOECLONE_REAL_MODEL=1 HF_HUB_OFFLINE=1 \
  .venv/bin/python -m pytest tests/engine_contract -q -m real_model
```

- 実行結果（合否・所要時間・検出結果）は Claude が `docs/poc-results.md` へ追記する
  （Codexは `docs/` を変更しない）。
- 完全ネットワーク遮断下での確認も Claude が実施する。

---

## 6. T-204: 単一ジョブキュー（FR-204/205/206）

| 項目 | 内容 |
|---|---|
| 依存 | T-201 |
| 所有ファイル | `src/koeclone/worker/queue.py`, `tests/unit/test_queue.py` |
| 見積 | 4h |

**目的**: 同時実行1件のジョブキューと状態遷移。**キューはDB・ファイル・エンジンを知らない**
（層分離。永続化は T-205 の責務）。

### 6.1 API契約

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from koeclone.errors import ErrorCode, KoecloneError

JobStatus = Literal["queued", "running", "succeeded", "failed"]

JobHandler = Callable[[str], None]        # 引数は job_id。戻り値は使わない
StateListener = Callable[["JobState"], None]


@dataclass(frozen=True)
class JobState:
    job_id: str
    status: JobStatus
    error_code: ErrorCode | None = None
    error_id: str | None = None           # 内部エラーID（uuid4().hex）。失敗時のみ非None


class JobQueue:
    def __init__(
        self,
        handler: JobHandler,
        *,
        listener: StateListener | None = None,
    ) -> None: ...

    def start(self) -> None:
        """ワーカースレッド（daemon）を1本だけ起動する。2回目以降の呼び出しは何もしない。"""

    def submit(self, job_id: str) -> JobState:
        """ジョブを投入し、status="queued" の JobState を返す。同一 job_id の重複投入は ValueError。"""

    def state(self, job_id: str) -> JobState | None:
        """現在の状態を返す。未知の job_id は None。"""

    def wait_for(self, job_id: str, timeout: float = 5.0) -> JobState:
        """テスト・呼び出し側用。終了状態（succeeded/failed）になるまで待つ。
        タイムアウトしたら TimeoutError を送出する。time.sleep のポーリングで実装しない
        （threading.Event を使う）。"""

    def shutdown(self, *, wait: bool = True) -> None:
        """新規受付を止め、wait=True なら実行中・待機中のジョブ完了後にワーカーを終了する。"""
```

### 6.2 振る舞い要件

1. **同時実行は常に1件**（FR-204）。ワーカースレッドは1本。後続は FIFO で待つ。
2. **状態遷移**（FR-205）: `submit` で `queued` → 取り出し時に `running` →
   handler が正常終了で `succeeded` → handler が例外で `failed`。
   遷移のたびに `listener` があれば新しい `JobState` で呼ぶ（listener 内の例外は握りつぶさず
   ログに残すが、ワーカーを止めない）。
3. **失敗時の情報**（FR-206）:
   - handler が `KoecloneError` を投げた → `error_code = 例外の code`
   - それ以外の例外 → `error_code = ErrorCode.ERR_INTERNAL`
   - `error_id = uuid4().hex`（毎回異なる）
   - **例外の文字列・スタックトレースを `JobState` に含めない**（§1.3-5）。詳細はログのみ。
4. **1件の失敗で停止しない**: 失敗の次のジョブも処理される。
5. **投入順が維持される**（handler の呼び出し順が submit 順と一致する）。
6. `submit` は `start()` 前でも受け付ける（`start()` 後に処理される）。
7. `shutdown()` 後の `submit` は `RuntimeError`。

### 6.3 RED（先に書いて失敗を確認するテスト）

`tests/unit/test_queue.py`（**`time.sleep` による待ちを使わない**。`threading.Event` / `wait_for` を使う）:

1. `submit` 直後の状態が `queued`
2. handler 実行中に観測した状態が `running`（handler 内で Event をセットし、その時点で `state()` を確認）
3. 正常終了で `succeeded`、`error_code is None`、`error_id is None`
4. handler が `KoecloneError(ERR_WATERMARK_NOT_DETECTED)` を投げると `failed` かつ
   `error_code is ErrorCode.ERR_WATERMARK_NOT_DETECTED`、`error_id` が非空
5. handler が素の `RuntimeError` を投げると `failed` かつ `error_code is ErrorCode.ERR_INTERNAL`
6. `error_id` が呼び出しごとに異なる
7. `JobState` に例外メッセージ・トレースバック文字列が含まれない
   （`repr(state)` に投げた例外メッセージが現れない）
8. **直列実行**: 2件同時に投入しても handler の同時実行数が最大1（handler 内でカウンタを
   インクリメント／デクリメントし、最大値が1であることを確認）
9. **順序維持**: 3件投入したときの handler 呼び出し順が submit 順と一致
10. **失敗後の継続**: 1件目が失敗しても2件目が `succeeded` になる
11. 同一 job_id の重複 `submit` で `ValueError`
12. `wait_for` がタイムアウトで `TimeoutError`
13. `shutdown()` 後の `submit` で `RuntimeError`
14. `listener` が各遷移で呼ばれ、受け取った status の系列が `["queued", "running", "succeeded"]`

**GREEN**: `queue.Queue` + `threading.Thread(daemon=True)` + `threading.Event` の最小実装。
**REFACTOR**: 状態遷移の集約（`_transition` ヘルパー）まで。

**検証**: `.venv/bin/python -m pytest tests/unit/test_queue.py -q`
**受入条件**: 全テスト成功。テストが 3秒以内に完了し、実行のたびに安定して成功する（フレーキーでない）。

---

## 7. T-205: 生成パイプライン統合（FR-005/007/008/203/206/207）

| 項目 | 内容 |
|---|---|
| 依存 | T-104, T-107, T-108, T-109, T-110（G1 完了済み）, T-201, T-202, T-204 |
| 所有ファイル | `src/koeclone/worker/pipeline.py`, `tests/integration/test_pipeline.py`, `src/koeclone/domain/synthesis_text.py`（**追記のみ**）, `tests/unit/test_synthesis_text.py`（**追記のみ**） |
| 見積 | 6h |

**目的**: 同意確認 → 合成用テキスト生成 → チャンク計画 → エンジン合成 → WAV結合 →
ウォーターマーク検出 → サイドカー生成 → DB/ファイル保存 を1ジョブとして統合する。
**エンジンは FakeEngine で検証する**（実モデル不使用）。

### 7.1 所有ファイルの追記制限

- `src/koeclone/domain/synthesis_text.py`: §7.2 の `plan_synthesis_chunks` と関連定数の**追加のみ**。
  既存 `build_synthesis_text` / `split_synthesis_text` / `SENTENCE_BOUNDARIES` の
  シグネチャ・振る舞い・戻り値を変更しない。既存テストは変更せず、通ったままであること。
- `tests/unit/test_synthesis_text.py`: `plan_synthesis_chunks` のテストの**追加のみ**。既存テストを消さない。

### 7.2 `plan_synthesis_chunks`（読点細切れの再結合。§2.2 の実装契約）

```python
TARGET_MIN_CHARS = 60
TARGET_MAX_CHARS = 120


def plan_synthesis_chunks(
    text: str,
    *,
    target_min: int = TARGET_MIN_CHARS,
    target_max: int = TARGET_MAX_CHARS,
) -> list[str]:
    """split_synthesis_text の結果を target_min〜target_max 文字を目標に再結合する。"""
```

アルゴリズム（決定的。この規則どおりに実装する）:

1. まず既存の `split_synthesis_text(text)` で断片列を得る。
2. 空文字列 `""` は空リストを返す。
3. 断片を先頭から順にバッファへ足していく:
   - バッファが空なら、その断片をバッファにする（**単一断片が `target_max` を超えても分割しない**。
     句読点境界がない以上、分割すると内容・順序を壊すため）。
   - バッファが空でなく、`len(バッファ) + len(断片) <= target_max` なら連結する。
   - 連結すると `target_max` を超えるなら、バッファを1チャンクとして確定し、断片を新しいバッファにする。
   - 連結後にバッファ長が `target_min` 以上になったら、そのバッファを確定する。
4. 最後に残ったバッファがあれば、それを最終チャンクとして確定する
   （`target_min` 未満でもよい。直前チャンクへ足すと `target_max` を超える場合があるため、
   単純に独立チャンクとする）。
5. `target_min <= 0` / `target_max < target_min` は `ValueError`。

**不変条件（必ずテストで保証する）**:

- `"".join(plan_synthesis_chunks(t)) == t` — 文字の欠落・重複・並べ替え・空白の増減が一切ない（FR-203）
- 返り値に空文字列を含まない
- 単一断片が `target_max` を超えるケースを除き、各チャンクは `target_max` 以下

### 7.3 `src/koeclone/worker/pipeline.py`（API契約）

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from koeclone.config import AppConfig
from koeclone.domain.pronunciation import PronunciationOverride
from koeclone.engines.base import SpeechEngine
from koeclone.errors import ErrorCode, KoecloneError
from koeclone.media.ffmpeg import FFmpegPaths
from koeclone.storage.db import Database
from koeclone.storage.files import DataPaths


class PipelineError(KoecloneError):
    """生成パイプラインの失敗。"""


@dataclass(frozen=True)
class SynthesisRequest:
    job_id: str                                    # 既存 synthesis_jobs 行の id（UUID文字列）
    voice_id: str
    text: str                                      # 原文
    overrides: tuple[PronunciationOverride, ...] = ()
    language: str = "ja"


@dataclass(frozen=True)
class SynthesisPipeline:
    engine: SpeechEngine
    database: Database
    paths: DataPaths
    config: AppConfig
    ffmpeg_paths: FFmpegPaths | None = None        # None なら ffmpeg 側で遅延解決

    def run(self, request: SynthesisRequest) -> None:
        """1ジョブを実行する。成功時は何も返さず、DBが succeeded になる。
        失敗時は DB を failed に更新したうえで PipelineError を再送出する
        （JobQueue が error_code / error_id を組み立てるため）。"""
```

`run()` の手順（**この順序を厳守**）:

1. **running へ更新**: `database.update_synthesis_job(job_id, status="running")`。
   対象行が無ければ `PipelineError(ERR_INTERNAL)`。
2. **言語検証**: `request.language != "ja"` → `PipelineError(ERR_INTERNAL)`。
3. **同意確認（FR-005）**: `database.get_current_voice_profile()` を取得し、
   - `None`、または `profile.id != request.voice_id`、
   - または `profile.consent_text` が空文字列
   のいずれかなら `PipelineError(ERR_NO_CONSENT)`。
4. **読み修正検証**: `validate_pronunciation_overrides(request.text, list(request.overrides))` が
   `ErrorCode` を返したら `PipelineError(そのコード)`（API層でも検証済みだが防御的に再検証する）。
5. **合成用テキスト生成**: `build_synthesis_text(request.text, list(request.overrides), config=self.config)`。
   `ErrorCode` が返ったら `PipelineError(そのコード)`。
6. **チャンク計画**: `plan_synthesis_chunks(synthesis_text)`。空リストなら `PipelineError(ERR_TEXT_EMPTY)`。
7. **エンジン準備**: `self.engine.load()`（冪等）。
8. **チャンク合成**: 一時ディレクトリ（`paths.temporary` 配下、`tempfile.mkdtemp(dir=...)`）に
   `<job_id hex>_<連番4桁>.wav` を作り、**チャンク順に** `engine.synthesize(chunk,
   Path(profile.reference_path), "ja", output_path=...)` を呼ぶ。
   ファイル名にユーザー由来文字列を使わない。
9. **結合**: チャンクが1件ならコピー、複数なら `concat_wavs(chunk_paths, final_path,
   paths=self.ffmpeg_paths)`。`final_path = storage_path(self.paths.generated, job_id, ".wav")`
   （FR-207: モノラル・モデル標準サンプルレート維持。エンジン出力の形式を変換しない）。
10. **ウォーターマーク検出（FR-008）**: `engine.detect_watermark(final_path)`。
    **False の場合は `final_path` を削除**し、`PipelineError(ERR_WATERMARK_NOT_DETECTED)` を送出する
    （`audio_path` を DB に書かない＝再生・DL不可）。
11. **サイドカー生成（FR-007）**: `write_sidecar(final_path, engine=self.engine.engine_name,
    model_version=self.engine.model_version, voice_id=request.voice_id,
    original_text=request.text, synthesis_text=synthesis_text,
    pronunciation_overrides=request.overrides)`。
12. **succeeded 更新**: `database.update_synthesis_job(job_id, status="succeeded",
    audio_path=str(final_path), sidecar_path=str(sidecar_path),
    duration_ms=wav_duration_ms(final_path), watermark_detected=True,
    completed_at=<ISO 8601 UTC>)`。
13. **後始末（成功・失敗を問わず `finally`）**: 手順8の一時チャンクWAVと一時ディレクトリを
    必ず削除する（部分音声を残さない。FR-206）。

**失敗時の共通処理**（`PipelineError` / 想定外例外の両方）:

- 生成途中の成果物（チャンクWAV、結合途中の `final_path`、サイドカー）を削除する。
- `database.update_synthesis_job(job_id, status="failed", error_code=<code>.value,
  watermark_detected=<検出を実行して False だった場合のみ False、それ以外は更新しない>,
  completed_at=<ISO 8601 UTC>)`。
- **`audio_path` / `sidecar_path` は書かない**（NULL のまま）。
- 想定外例外は `PipelineError(ERR_INTERNAL)` へ変換して再送出する。
  元の例外メッセージを `PipelineError` に含めない（§1.3-5）。

### 7.4 削除順の厳守（プロフィール削除時。AC-09 / FR-113）

パイプラインとは別に、**プロフィール削除の削除順**を本契約で固定する。
Phase 3（T-304）が API から呼ぶ流れだが、順序の契約はここで定義する。
T-205 は**この順序を守るヘルパーを `pipeline.py` に置かない**（責務外）。
**削除を実装する側（T-304）はこの順序に従う**こと:

```text
1. collect_deletion_targets(paths, reference_id=..., consent_id=..., job_ids=[...])
   ── DBから必要な id 群を読み、削除対象パスを「先に」全て確定する
2. delete_targets(data_root, targets)
   ── ファイルを削除する
3. database.delete_voice_profile(profile_id) / delete_all_synthesis_jobs()
   ── DB行を削除する（外部キー ON DELETE CASCADE でジョブ行も消える）
```

**理由**: DB行を先に消すと `job_ids` / `reference_id` / `consent_id` を失い、
どのファイルを消すべきか復元できなくなって**孤児ファイルが残る**（AC-09 違反）。
したがって **collect → ファイル削除 → DB削除 の順を逆転させてはならない。**
手順2で例外が起きた場合は手順3を実行せず、失敗として返す（DBに情報を残して再試行可能にする）。

### 7.5 RED（先に書いて失敗を確認するテスト）

`tests/unit/test_synthesis_text.py`（追記分）:

1. 読点だらけの文（例: 「あ、い、う、…」を200文字分）で `plan_synthesis_chunks` の各チャンクが
   `target_max` 以下、かつ最終チャンク以外が `target_min` 以上
2. **不変条件**: `"".join(...) == text`（複数パターン：短文／長文／句読点なし／読点のみ）
3. 句読点が無い 300文字の文は 1チャンクのまま（分割されない）
4. 空文字列 → `[]`
5. 返り値に空文字列を含まない
6. `target_min=0` / `target_max < target_min` で `ValueError`
7. 既存 `split_synthesis_text` / `build_synthesis_text` の振る舞いが変わっていない（既存テストが通る）

`tests/integration/test_pipeline.py`（FakeEngine + 一時ディレクトリ + 一時DB）:

8. **成功系**: 有効プロフィールとジョブ行を用意して `run()` すると、
   - `generated/<job_id>.wav` が存在しモノラル・24,000Hz
   - `generated/<job_id>.json` が存在し `ai_generated` が `true`、`text_sha256` /
     `synthesis_text_sha256` が期待値と一致
   - DBが `status="succeeded"`、`audio_path` / `sidecar_path` / `duration_ms` が非NULL、
     `watermark_detected is True`、`completed_at` が非NULL
9. **一時ファイルが残らない**: 成功後、`paths.temporary` 配下にファイルが1つも残っていない
10. **検出失敗系**: `FakeEngine(detect_result=False)` で
    - `PipelineError` が送出され `code is ErrorCode.ERR_WATERMARK_NOT_DETECTED`
    - DBが `status="failed"`、`error_code == "ERR_WATERMARK_NOT_DETECTED"`、
      **`audio_path` が NULL**、`sidecar_path` が NULL
    - `generated/` 配下に WAV もサイドカーも残っていない（再生・DL不可を物理的に保証）
11. **同意なし拒否**: プロフィールが存在しない場合に `PipelineError(ERR_NO_CONSENT)` となり、
    **エンジンが1度も呼ばれない**（`engine.calls == []`、`engine.load_count == 0`）
12. **voice_id 不一致**: 別IDのプロフィールしか無い場合も `ERR_NO_CONSENT`
13. **読み修正の適用**: AC-06 の例（原文「明日は日本橋へ行きます」＋
    `PronunciationOverride("日本橋", 3, 6, "にほんばし")`）で、
    サイドカーの `synthesis_text_sha256` が「明日はにほんばしへ行きます」のSHA-256と一致し、
    DBの `text` が**原文のまま**であること
14. **分割・結合の順序**: 複数チャンクになる長文で、`engine.calls` のテキスト系列が
    `plan_synthesis_chunks` の結果と**完全一致**し、結合後WAVの長さが各チャンクWAVの合計と
    ±50ms で一致すること
15. **読み修正エラーの伝播**: 範囲不一致の override で `PipelineError(ERR_OVERRIDE_SURFACE_MISMATCH)`
    となり、DBが failed、エンジン未呼出
16. **想定外例外の写像**: `synthesize` が `RuntimeError` を投げる engine スタブで
    `PipelineError(ERR_INTERNAL)` となり、例外文字列に元の例外メッセージが含まれないこと
17. **JobQueue との結合**: `JobQueue(handler=lambda job_id: pipeline.run(...))` で投入した
    ジョブが `succeeded` になり、失敗ジョブは `failed` かつ `error_code` が写像されること
18. **削除順の契約テスト**: `collect_deletion_targets` → `delete_targets` → `delete_voice_profile`
    の順で実行すると、参照音声・同意録音・キャッシュ・生成WAV・サイドカー・一時ファイルが
    すべて存在しなくなり、DBからもプロフィールとジョブが取得できないこと。
    併せて、**DB削除を先に行うと job_ids が取得できず削除対象が欠落する**ことを
    テストで明示する（順序の必要性の回帰防止）

**GREEN**: 各ドメイン部品を呼ぶ直列パイプラインの最小実装。
**REFACTOR**: ステップ関数への分割（`_prepare` / `_synthesize_chunks` / `_finalize` 等）まで。

**検証**:

```bash
.venv/bin/python -m pytest tests/unit/test_synthesis_text.py tests/integration/test_pipeline.py -q
```

**受入条件**: 全テスト成功。AC-05 / AC-08 のサーバー側動作が FakeEngine で保証される。
実モデルが一度もロードされない。

---

## 8. 全体検証（G2ゲート入力）

T-201〜T-205 完了後、リポジトリルートで以下を実行し、**生出力を最終報告に含める**。

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
```

完了条件（Codex分）:

- 全テスト成功（Phase 1 の既存109テストを含む）。`tests/engine_contract` の実モデルテストは skipped。
- `ruff check src tests` 指摘ゼロ。
- 実行中に `chatterbox` / `torch` / `torchaudio` / `perth` が**一度もロードされない**こと
  （実行時間が Phase 1 と同程度に収まることで確認できる。数十秒かかる場合はロードを疑い報告する）。

Claude が実施する追加検証（Codexの作業ではない）:

- §5.6 の実モデル契約テスト（`-m real_model`）を基準Macで実行し、結果を記録する。
- 完全ネットワーク遮断下での実モデル動作確認（P0-C2 §8 引き継ぎ事項2）。
- 差分レビュー（Blocking / Major ゼロの確認）、`shell=True` 不使用・固定絶対パス不在の再確認。

**ゲート G2**: 偽エンジンでの全テスト成功 + 実モデル契約テスト成功（Claudeが基準Macで実行・記録）
+ Blocking/Major 指摘ゼロ。

---

## 9. Git・依存導入・実モデル実行の禁止（再掲・厳守）

Codexは本契約において、**いかなるGit操作も、依存関係の導入・変更も、実モデルの実行・ロードも行わない。**
コミットはClaudeがタスクごとにレビュー後、所有ファイルを個別に `git add <file>` して行う
（`git add .` / `git add -A` 禁止）。実モデルの実行は Claude が §5.6 の手順でのみ実施する。
