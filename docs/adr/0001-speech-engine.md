# ADR-0001: 音声合成エンジンとして Chatterbox Multilingual V3 を採用する

| 項目 | 内容 |
|---|---|
| ステータス | 承認（Accepted） |
| 決定日 | 2026-07-24 |
| 決定者 | Claude（Phase 0 指揮官。`docs/implementation-plan.md` P0-C2 の権限に基づく） |
| 関連文書 | `docs/system-specification.md` §8.1、`docs/implementation-plan.md` §7 Phase 0 / G0、`docs/poc-results.md` |

## コンテキスト

本システム（koeclone）は、ユーザー本人の参照音声から日本語音声を**完全ローカル**（macOS / Apple Silicon、
外部送信なし）で合成する。エンジンには以下が求められる（仕様 §8.1、G0基準）:

1. 日本語のゼロショット音声クローンに対応すること。
2. 基準Mac（MacBook Pro, Apple M4 Pro）で 10秒相当の音声を60秒以内に生成できること（MPS、CPUフォールバック含む）。
3. 生成音声に検出可能なウォーターマークが入ること（悪用対策、FR-008）。
4. コード・モデル重みのライセンスが本用途（ローカル利用、再配布なし）に支障がないこと。

候補は第一候補 Chatterbox Multilingual V3、代替候補 Coqui XTTS v2（PoC不合格時のみ同一基準で比較）。

## 決定

**Resemble AI の Chatterbox Multilingual V3 を採用する。**

- 取得形態: GitHub master コミット `5de7a54aa4e5e2baadb0182dde554908b48b85c2` を `[tool.uv.sources]` で固定
  （PyPI版は V3 チェックポイント `t3_mtl23ls_v3.safetensors` に未対応のため。詳細は `docs/poc-results.md` P0-C1 §1）。
- モデル重み: Hugging Face `ResembleAI/chatterbox` リビジョン `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`、
  主要ファイルのSHA-256を `docs/poc-results.md` P0-C1 §4 に記録済み。
- 呼び出し: `ChatterboxMultilingualTTS.from_pretrained(device=..., t3_model="v3")` →
  `generate(text, language_id="ja", audio_prompt_path=<参照WAV>)`（`t3_model="v3"` の明示指定が必須）。

## 根拠（P0-C2 実測、2026-07-24、詳細は `docs/poc-results.md`）

| G0基準 | 実測 | 判定 |
|---|---|---|
| 速度（10秒音声/60秒以内） | MPS 定常RTF 1.64（ウォームアップ込みワースト2.73）、CPU RTF 2.68〜2.85。10秒音声換算で MPS ≈ 16〜27秒 / CPU ≈ 28.5秒 | 合格 |
| ウォーターマーク検出 | 生成10ファイル（MPS 5 + CPU 5）全てで PerTh 検出 1.0 | 合格 |
| 音質・異常継続 | クリッピング0、NaN/Inf なし、無音率 17.7〜28.1%、末尾無音 ≤0.56秒、5.2〜6.0字/秒で安定（入力外発話・反復なし） | 合格 |
| メモリ | ピークRSS: MPS 約4.9 GB / CPU 約6.7 GB（16GB級マシンで動作可能） | 合格 |
| ライセンス | コード（chatterbox-tts / resemble-perth）・モデル重みとも MIT | 合格 |

CPUフォールバックも暫定基準内（RTF < 6）で成立するため、MPS初期化失敗時のフォールバック方針（T-203、R-09）が有効。

**評価の限定**: 本人音声が未提供のため、本判定は合成参照音声（macOS TTS "Kyoko"）による
**技術ゲートのみ**の評価である。話者類似度（本人らしさ）・明瞭性の主観評価は、録音UI実装後に
本人録音を用いて P4-C2 で再評価する（不合格時は品質撤退基準 §11.2 に従う）。

## 代替案

- **Coqui XTTS v2**: G0全項目合格のため比較評価は実施しない（計画どおり）。ライセンスが
  CPML（非商用制限）である点も、MITのChatterboxに対する劣後要因。
- **クラウドTTS API**: 完全ローカル・外部送信禁止の要件（仕様 §2）に反するため対象外。

## 影響・結果

1. Phase 2 の T-203（エンジンアダプター）は本ADRのAPI形状・固定リビジョンを前提に実装する。
   `from_pretrained` は `revision="main"`（浮動）で取得するため、アダプターでは上記スナップショットを
   固定使用するか、ロード前にリビジョン一致を検証する。
2. FR-106 の品質閾値は P0-C2 実測により確定（無音率 ≥80% 拒否 / ピーク >-1dBFS 拒否 /
   RMS -35〜-10 dBFS 範囲外拒否）。T-105 の設定既定値に反映する。
3. 生成音声には PerTh ウォーターマークが常時付与される（無効化引数は存在しない）。FR-008 の
   検出ゲートは `perth.PerthImplicitWatermarker.get_watermark` を用いる。
4. モデルは MPS で約4.9 GB / CPU で約6.7 GB のRSSを要するため、プロセス内1回ロード（T-203）を維持する。
5. 完全ネットワーク遮断下での動作確認は未実施であり、T-203 の実モデル契約テストで実施する。
