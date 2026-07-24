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
