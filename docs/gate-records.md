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
| G3 | Phase 3 API・UI・E2E | 未判定 | — | — | 判定時に本書へ追記 |
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
