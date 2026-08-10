# PoC結果記録 (Phase 0)

| 項目 | 内容 |
|---|---|
| 文書所有者 | Claude（唯一の指揮官）。本文書の変更はClaudeのみが行う |
| 上位文書 | `docs/implementation-plan.md` §7 Phase 0 |
| 対象マシン | MacBook Pro (Apple M4 Pro) / macOS (Darwin 25.5.0) |

## P0-C1: 依存導入・モデル取得・ライセンス確認（2026-07-24 実施）

### 1. 導入パッケージ

`uv add` でプロジェクト依存へ追加し `uv.lock` を更新した（Homebrew / sudo / pip直叩き不使用）。

| パッケージ | 版 | 取得元 | ライセンス |
|---|---|---|---|
| chatterbox-tts | 0.1.7（git） | `git+https://github.com/resemble-ai/chatterbox.git` @ `5de7a54aa4e5e2baadb0182dde554908b48b85c2` | MIT |
| resemble-perth | 1.0.1 | `git+https://github.com/resemble-ai/Perth.git` @ `ce86c49d029f42272c1902eccb675556b9ed2330`（chatterbox-tts の要求で解決） | MIT |
| torch | 2.6.0 | PyPI（chatterbox-tts が `==2.6.0` に固定） | BSD-3-Clause |
| torchaudio | 2.6.0 | PyPI（同上） | BSD-3-Clause |
| static-ffmpeg | 3.0 | PyPI | MIT（下記注記あり） |
| Python | 3.11.12 | 既存 `.venv`（uv管理） | — |

**PyPI版ではなくgitコミット固定にした理由**: PyPI最新の `chatterbox-tts==0.1.7`（2026-03-26）の
`ChatterboxMultilingualTTS.from_pretrained` は `t3_mtl23ls_v2.safetensors`（Multilingual **V2**）を
ハードコードしており `t3_model` 引数が存在しない。仕様（§8.1）が採用候補とする **Multilingual V3**
（`t3_model="v3"` → `t3_mtl23ls_v3.safetensors`）はGitHub masterのみが対応するため、
masterの現行コミット `5de7a54a` を `[tool.uv.sources]` で固定した。

### 2. 実際のモデルAPI（インストール済みソースで確認）

```python
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

model = ChatterboxMultilingualTTS.from_pretrained(device="mps", t3_model="v3")
# t3_model のデフォルトは None → V2 に解決されるため、V3は明示指定が必須
wav = model.generate(text, language_id="ja", audio_prompt_path=<参照WAV>)
# generate(text, language_id, audio_prompt_path=None, exaggeration=0.5,
#          cfg_weight=0.5, temperature=0.8, repetition_penalty=1.2,
#          min_p=0.05, top_p=1.0)
```

- `SUPPORTED_LANGUAGES` に `"ja": "Japanese"` を含む23言語。
- 出力サンプルレート `model.sr = 24000` Hz。
- `device="mps"` 指定時、`torch.backends.mps.is_available()` を確認し、不可ならCPUへ自動フォールバック
  （チェックポイントは `map_location="cpu"` で読み込み後 `.to(device)`）。
- 生成音声には `generate()` 内で常にPerThウォーターマークが適用される（無効化引数なし）。

### 3. PerThウォーターマーク検出API

```python
import perth
import librosa

audio, sr = librosa.load(path, sr=None)
watermarker = perth.PerthImplicitWatermarker()          # "loaded PerthNet (Implicit) at step 250,000"
result = watermarker.get_watermark(audio, sample_rate=sr)  # 0.0 / 1.0
```

- 実体クラス: `perth.perth_net.perth_net_implicit.perth_watermarker.PerthImplicitWatermarker`
- 検出器モデルはパッケージ同梱でロード時のネットワークアクセスなし（オフラインで初期化成功を確認）。
- 実音声での検出成否はP0-C2（生成時）で確認する。

### 4. モデル重み（取得・固定情報）

| 項目 | 内容 |
|---|---|
| 取得元 | Hugging Face `ResembleAI/chatterbox`（非gated、認証不要） |
| リビジョン | `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`（`revision="main"` の2026-07-24時点解決値） |
| 重みライセンス | MIT（HF APIの license タグで確認） |
| キャッシュ | `~/.cache/huggingface/hub/models--ResembleAI--chatterbox`（3.0 GB） |

SHA-256（スナップショット内の実ファイル）:

| ファイル | サイズ | SHA-256 |
|---|---|---|
| `t3_mtl23ls_v3.safetensors` | 2,143,989,928 | `5abca8321ede76f8e61f1cc0d19aea6c946b28871017ce8726f8a69203f05953` |
| `s3gen.pt` | 1,057,165,844 | `9b9ff07e60b20c136e2b1b3d7563a24604e8d2c4c267888d1ee929dd0151d2a3` |
| `ve.pt` | 5,698,626 | `4b16d836bc598509860f6fa068165a8bb5e9ac84f05582dfcf278a5a372879f1` |
| `conds.pt` | 107,374 | `6552d70568833628ba019c6b03459e77fe71ca197d5c560cef9411bee9d87f4e` |
| `grapheme_mtl_merged_expanded_v1.json` | 69,989 | `69632f47220a788a52ce2661d096453c5655e9bf25289d89a8d832c46ee07dbf` |
| `Cangjie5_TC.json` | 1,920,163 | `7073fd9de919443ae88e0bd2449917a65fe54898a4413ed1edcc4b67f28bce8c` |

`from_pretrained` は `revision="main"`（浮動）で取得するため、Phase 2のアダプター（T-203）では
上記リビジョンのスナップショットを `from_local` 相当で固定使用するか、ロード前にリビジョン一致を
検証する方針とする。

### 5. MPSロード結果（device=mps, t3_model="v3"）

| 項目 | 実測 |
|---|---|
| MPS利用可否 | `is_available=True` / `is_built=True` |
| ロード時間 | 初回12.5秒 / 2回目7.8秒 |
| 配置確認 | t3 / s3gen / ve すべて `mps:0` |
| ピークRSS | 約4.7 GB |
| 音声生成 | 未実施（P0-C2で実施） |

### 6. オフライン再ロード確認（HF_HUB_OFFLINE=1）

- モデル取得後、`HF_HUB_OFFLINE=1` で `from_pretrained(device="mps", t3_model="v3")` の再ロードに成功。
- 注意点2件（下記「P0-C2への確認事項」参照）:
  1. 初回ロード時のみ spacy-pkuseg が辞書 `spacy_ontonotes.zip` をGitHubから取得し
     `~/.pkuseg/`（91 MB）へ保存する。HF外のためHF_HUB_OFFLINEでは遮断されない。
     取得後はネットワークアクセスなしで再ロード可能（2回目実行で確認済み）。
  2. `Could not load Cangjie mapping` 警告がオン/オフライン両方で発生する。原因はupstreamの不具合で、
     tokenizerがスナップショットディレクトリを `hf_hub_download(cache_dir=...)` に渡すため
     キャッシュ解決に失敗する（`chatterbox/models/tokenizers/tokenizer.py`）。
     Cangjieは中国語（zh）専用機能であり、日本語MVPには影響しない見込み。

### 7. ffmpeg / ffprobe（static-ffmpeg経由・プロジェクト局所）

| 項目 | 内容 |
|---|---|
| 取得方法 | `static-ffmpeg` 3.0 の初回実行時自動取得 |
| 配置先 | `.venv/lib/python3.11/site-packages/static_ffmpeg/bin/darwin_arm64/`（94 MB、gitignore対象） |
| `ffmpeg -version` | `ffmpeg version 7.0`（arm64静的ビルド、Apple clang 13.1.6） |
| `ffprobe -version` | `ffprobe version 7.0`（同上） |
| ライセンス注記 | static-ffmpegパッケージ自体はMITだが、同梱ffmpegバイナリは `--enable-gpl --enable-libx264` 等を含むGPLビルド。本システムはローカル実行のみでバイナリを再配布しないため利用可。リリース前（P4-C1）に再確認する |

### 8. ディスク消費

| 対象 | サイズ |
|---|---|
| `.venv`（依存一式 + ffmpegバイナリ） | 1.3 GB |
| HFモデルキャッシュ | 3.0 GB |
| `~/.pkuseg` 辞書 | 91 MB |
| 合計 | 約4.4 GB |

### 9. 検証結果

| 検証 | 結果 |
|---|---|
| `import chatterbox / perth / static_ffmpeg / torch / torchaudio / fastapi` + `"ja" in SUPPORTED_LANGUAGES` | 成功 |
| `uv lock --check` | 整合（Resolved 169 packages） |
| `ruff check .` | All checks passed |
| `pytest -q` | no tests ran（テストはP0-X1以降で作成予定のため想定どおり） |

### 10. P0-C2への確認事項（引き継ぎ）

1. 実生成でのPerTh検出成否（`get_watermark` が生成WAVで1.0を返すか）。
2. 速度・RTF・ピークメモリの実測（MPS/CPU両方、日本語5文以上）。
3. Cangjie警告が日本語生成品質に影響しないことの確認（zh専用機能の想定を実測で裏取り）。
4. FR-106閾値（無音率・音量・クリッピング）の実測確定。
5. 完全オフライン（ネットワーク遮断）での生成一式の動作確認（`~/.pkuseg` 取得済み前提）。
6. `revision="main"` 浮動問題への対処方針（スナップショット固定 or リビジョン検証）のT-203契約への反映。

## P0-C2: MPS/CPU 実機ベンチマークと品質実測（2026-07-24 実施）

### 1. 実行条件

| 項目 | 内容 |
|---|---|
| モデル | Chatterbox Multilingual V3（P0-C1 で固定したコミット/リビジョン） |
| 参照音声 | `tmp/reference_kyoko.wav`（macOS内蔵TTS "Kyoko" による**合成参照**、26.5秒 / 24kHz / モノラル） |
| 評価文 | 日本語5文（27〜30文字/文、`tmp/eval_texts_5.txt`）。G0要件「5文以上」を満たす |
| 実行方法 | `HF_HUB_OFFLINE=1 uv run python scripts/poc_generate.py --device {mps,cpu} --reference ... --texts ... --output ...` |
| 備考 | **本人音声は未提供**のため合成参照で技術ゲート（速度・メモリ・音質異常・ウォーターマーク）のみ評価。**本人らしさ（話者類似度）・明瞭性の主観評価は録音UI実装後（P4-C2）の再評価事項** |

### 2. 速度・RTF・ピークメモリ（実測）

**MPS（`--device mps`）** — ピークRSS 5,021 MB（約4.9 GB）:

| 文 | 文字数 | 生成時間(s) | 音声長(s) | RTF | ウォーターマーク検出 |
|---|---|---|---|---|---|
| 1 | 28 | 13.75 | 5.04 | 2.73 | ✅ 1.0 |
| 2 | 27 | 8.32 | 5.08 | 1.64 | ✅ 1.0 |
| 3 | 29 | 7.49 | 5.08 | 1.47 | ✅ 1.0 |
| 4 | 29 | 8.36 | 5.16 | 1.62 | ✅ 1.0 |
| 5 | 30 | 10.01 | 5.48 | 1.83 | ✅ 1.0 |

- 合計: 生成47.9秒 / 音声25.8秒 → **集計RTF 1.86**（1文目のウォームアップ込み）。2文目以降の定常RTFは **1.64**。
- 1文目はMPSカーネルのウォームアップを含むため他文より遅い（P0-C1のロード計測と整合）。

**CPU（`--device cpu`）** — ピークRSS 6,845 MB（約6.7 GB）:

| 文 | 文字数 | 生成時間(s) | 音声長(s) | RTF | ウォーターマーク検出 |
|---|---|---|---|---|---|
| 1 | 28 | 15.37 | 5.40 | 2.85 | ✅ 1.0 |
| 2 | 27 | 13.76 | 4.88 | 2.82 | ✅ 1.0 |
| 3 | 29 | 14.38 | 5.36 | 2.68 | ✅ 1.0 |
| 4 | 29 | 13.69 | 4.84 | 2.83 | ✅ 1.0 |
| 5 | 30 | 14.79 | 5.36 | 2.76 | ✅ 1.0 |

- 合計: 生成72.0秒 / 音声25.8秒 → **集計RTF 2.79**。
- MPSの定常速度はCPU比 約1.7倍。CPUフォールバック（T-203）も暫定基準内で成立する。

**G0速度基準への換算**: 「10秒相当の日本語音声を60秒以内」＝ RTF ≤ 6.0。
実測ワーストはCPUの2.85（10秒音声 ≈ 28.5秒）、MPSウォームアップ込みでも2.73（≈ 27.3秒）で**両デバイス合格**。

### 3. 音質・異常継続の解析（tmp/analyze_wav.py、20ms窓RMS < -50dBFS を無音と判定）

**MPS生成5文:**

| 文 | 長さ(s) | ピーク(dBFS) | RMS(dBFS) | 無音率 | 末尾無音(s) | クリップ率 | 有限値 | 字/秒 |
|---|---|---|---|---|---|---|---|---|
| 1 | 5.04 | -11.06 | -25.34 | 25.4% | 0.50 | 0 | ✅ | 5.56 |
| 2 | 5.08 | -9.86 | -25.84 | 24.0% | 0.48 | 0 | ✅ | 5.31 |
| 3 | 5.08 | -11.18 | -25.26 | 17.7% | 0.42 | 0 | ✅ | 5.71 |
| 4 | 5.16 | -9.77 | -25.89 | 26.4% | 0.54 | 0 | ✅ | 5.62 |
| 5 | 5.48 | -11.44 | -26.50 | 28.1% | 0.52 | 0 | ✅ | 5.47 |

**CPU生成5文:**

| 文 | 長さ(s) | ピーク(dBFS) | RMS(dBFS) | 無音率 | 末尾無音(s) | クリップ率 | 有限値 | 字/秒 |
|---|---|---|---|---|---|---|---|---|
| 1 | 5.40 | -9.95 | -25.52 | 27.0% | 0.52 | 0 | ✅ | 5.19 |
| 2 | 4.88 | -9.20 | -25.54 | 23.0% | 0.52 | 0 | ✅ | 5.53 |
| 3 | 5.36 | -11.52 | -25.36 | 19.0% | 0.56 | 0 | ✅ | 5.41 |
| 4 | 4.84 | -10.01 | -25.96 | 24.0% | 0.38 | 0 | ✅ | 5.99 |
| 5 | 5.36 | -10.58 | -25.17 | 23.9% | 0.52 | 0 | ✅ | 5.60 |

判定:

- **異常継続・反復なし**: 音声長は文字数に比例（5.2〜6.0字/秒で安定）、末尾無音は最大0.56秒。入力外の発話継続は観測されない。
- **クリッピングなし**: 全10ファイルで |sample| ≥ 0.999 のサンプル0個、ピークは -9.2〜-11.5 dBFS。
- **数値異常なし**: 全ファイル NaN/Inf なし。
- **音量は安定**: RMS -25.2〜-26.5 dBFS（参照音声の -24.6 dBFS とほぼ同水準に追従）。
- Cangjie警告はMPS/CPU両ログで発生したが、上記のとおり日本語生成の全計測値は正常であり、**zh専用機能で日本語品質に影響しないことを実測で裏取りした**（P0-C1引き継ぎ事項3）。

### 4. PerThウォーターマーク検出（P0-C1引き継ぎ事項1）

生成10ファイル全てで `PerthImplicitWatermarker.get_watermark` が **1.0（検出）** を返した。10/10で合格。

### 5. FR-106品質閾値の実測確定（T-105設定既定値への反映値）

参照音声実測: ピーク -9.38 dBFS / RMS -24.62 dBFS / 無音率 19.2%。生成音声実測は上表のとおり。

| 判定 | 確定既定値 | 根拠（実測） |
|---|---|---|
| 無音率拒否 | 無音率 ≥ 80%（20ms窓RMS < -50 dBFS を無音窓と判定） | 正常発話の実測は 17.7〜28.1%。80%閾値に対し十分な分離幅がある |
| クリッピング拒否 | ピーク > -1.0 dBFS、または \|sample\| ≥ 0.999 のサンプルが存在 | 正常音声の実測ピークは -9.2 dBFS 以下 |
| 平均音量拒否 | RMS が **-35 dBFS 未満**または **-10 dBFS 超** | 正常音声の実測RMSは -24.6〜-26.5 dBFS。±10dB強のマージンを確保しつつ、無音同然（<-35）と過大入力（>-10、ピーク余裕喪失）を排除 |

閾値は T-105 で設定注入とし、上記を既定値とする。

### 6. オフライン動作

- `HF_HUB_OFFLINE=1` でモデルロード〜5文生成〜ウォーターマーク検出の一式がMPS/CPU両方で成功（`~/.pkuseg` 取得済み前提）。
- **完全なネットワーク遮断（インターフェース断）での確認は未実施。** P0-C1引き継ぎ事項5の完全版はT-203の実モデル契約テスト時に実施する。

### 7. G0判定

| G0基準 | 結果 | 判定 |
|---|---|---|
| `docs/poc-results.md` が実測値付きで作成済み | 本書 §P0-C1/P0-C2 | ✅ |
| 10秒相当の日本語音声を基準Macで60秒以内に生成 | MPS ≈ 16〜27秒、CPU ≈ 28.5秒（RTF換算） | ✅ |
| ウォーターマークが生成音声から検出できる | 10/10 検出 | ✅ |
| ライセンス上の支障がない | コード/重みともMIT（P0-C1 §1/§4） | ✅ |
| ADR-0001 承認済み | `docs/adr/0001-speech-engine.md` | ✅ |

**G0: 合格（Chatterbox Multilingual V3 を採用、Coqui XTTS v2 比較は不要）。**
ただし本人音声未提供のため、話者類似度・明瞭性の主観評価は録音UI実装後（P4-C2）に本人録音で再評価する。

### 8. Phase 2（T-203）への引き継ぎ

1. `revision="main"` 浮動問題: アダプターはP0-C1記載のスナップショット（`5bb1f6ee…`）を固定使用するか、ロード前にリビジョン一致を検証する（ADR-0001に方針記載）。
2. 完全ネットワーク遮断下での生成一式の動作確認（実モデル契約テストに含める）。
3. MPS 1文目のウォームアップ遅延（約1.7倍）: プロセス内1回ロード方針（T-203）で吸収されるが、初回リクエストの応答時間見積もりに反映する。
4. FR-106確定閾値（本書 §5）を T-105 の設定既定値へ反映する。

## T-203: Chatterboxアダプター 実モデル契約テスト実測（2026-08-10 実施）

Phase 2 T-203（`src/koeclone/engines/chatterbox.py`）に対し、Claudeが基準Macで実モデルを
ロードして実施した結果。Codexは実モデルを一度もロードしていない（契約 §1.2-4 / §5.6）。

### 1. 実行条件

| 項目 | 内容 |
|---|---|
| 実行コマンド | `KOECLONE_REAL_MODEL=1 HF_HUB_OFFLINE=1 .venv/bin/python -m pytest tests/engine_contract -q -m real_model` |
| 結果 | **5 passed / 1 skipped**（19.27s）。skip は「MPS利用可のためMPS不可ケースは対象外」の明示スキップ |
| モデル解決 | `snapshot_download(revision="5bb1f6ee…", local_files_only=True, allow_patterns=5ファイル)` → `ChatterboxMultilingualTTS.from_local(snapshot, device, t3_model="v3")` |
| 参照音声 | `tmp/reference_kyoko.wav`（P0-C2と同一の合成参照） |

`from_pretrained`（`revision="main"` 浮動）は使用しない方式へ確定した（P0-C2 §8 引き継ぎ事項1を解消）。
`allow_patterns` は `from_local` が実際に読む5ファイル（`ve.pt` / `t3_mtl23ls_v3.safetensors` /
`s3gen.pt` / `grapheme_mtl_merged_expanded_v1.json` / `conds.pt`）に限定し、日本語MVPに不要な
`Cangjie5_TC.json` を取得対象から外した。

### 2. 時間の実測（プロセス内1回ロード）

| 計測 | 実測 | 備考 |
|---|---|---|
| `load()`（MPS） | **10.60 s** / pytest fixture setup 10.84 s | `active_device="mps"`、`fallback_reason=None`（CPUフォールバックなし） |
| `load()` 2回目 | 即 return（同一モデルオブジェクト） | 冪等性テストで `_model` 同一性を確認 |
| `synthesize()` | **8.51 s** / pytest fixture setup 8.25 s | 17文字「これは音声クローンの動作確認です。」→ 音声3.04 s、**RTF 2.80**（プロセス内初回のためMPSウォームアップ込み。P0-C2の1文目2.73と整合） |
| `detect_watermark()` | **0.05 s** | 検出器インスタンスは保持・再利用 |

### 3. 出力形式の実測（`wave` モジュールで検証）

| 項目 | 実測 | 契約（FR-207） |
|---|---|---|
| チャンネル数 | 1（モノラル） | モノラル |
| サンプルレート | 24,000 Hz | `model.sr` = 24,000 Hz |
| サンプル幅 | **2 バイト（16bit PCM）** | `encoding="PCM_S", bits_per_sample=16` を明示指定 |
| フレーム数 / サイズ | 72,960 フレーム / 145,964 バイト（3.04 s） | — |

`torchaudio.save` は指定なしだと32bit floatで書き出す可能性があるため、16bit PCMを明示固定した。
テストは `getsampwidth() == 2` まで検証する。

### 4. ウォーターマーク・リビジョン検証

| 検証 | 結果 |
|---|---|
| 生成WAVの PerTh 検出（AC-08 / FR-008） | **True**（`get_watermark` ≥ 0.5） |
| `EXPECTED_MODEL_REVISION` を `"0"*40` に差し替えたロード | `EngineError(ERR_INTERNAL)` を送出（固定リビジョン以外を拒否） |
| FR-006 表層検査（無効化引数・属性・ソース文字列） | 該当なし |

### 5. 完全オフライン確認（P0-C2 §8 引き継ぎ事項2 → 解消）

`HF_HUB_OFFLINE=1` に加え、プロセス内で `socket.socket.connect` / `connect_ex` /
`socket.create_connection` / `socket.getaddrinfo` をフックし、**ループバック以外への接続を全て例外化**
した状態で `load()` → `synthesize()`（日本語）→ `detect_watermark()` を実行した。

- 結果: 全工程成功（`active_device=mps`、モノラル/24,000Hz/16bit、ウォーターマーク検出 True）。
- **遮断された接続試行は0件**（DNS解決の試行も0件）。モデル・トークナイザ・PerTh検出器の全てが
  ローカルキャッシュのみで完結することを実証した（`~/.pkuseg` 取得済み前提）。

### 6. 判定

T-203 の実モデル契約項目（契約 §5.5 の 8〜13）は全て合格。プロセス内1回ロード・`ja` 固定合成・
固定リビジョン強制・16bit PCM モノラル24kHz出力・PerTh検出・完全オフライン動作を実測で確認した。
