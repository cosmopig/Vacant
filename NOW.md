# NOW — 第 1175 輪（2026-11-07，≤ 3 KB、覆寫不追加；細節放 bd）

## 現在：R-loop G2.5 自動擷取需求（vq-el4 epic）

- **r1175**：vq-el4.1 完成——`vacant_network/reqloop/extract.py`（quote 逐字檢查＋
  verifier 白名單＋`unverified=True`，fail-closed；假 client 測試
  `tests/test_reqloop_extract.py` 全綠；checks.py 加單一事實來源
  `SUPPORTED_VERIFIERS`/`KV_RECOMPUTE_TYPES`/`PLAIN_RECOMPUTE_TYPES`，分派行為不變）。
- **下一步＝vq-el4.2**：OpenAI 相容 client（`~/dev/ops/secrets/extract.env` 已建、未用；
  注入式，不硬編碼）。做完後 el4.3 用 dab055 真原文量測。
- 輸入只給使用者原文＋資料檔欄位/前幾列；**不給 hidden/scorer/答案**；沿用現有
  RequirementSet 與 checks.py。防「模型自己發明好過的條件」靠程式檢查（逐字 quote、
  白名單、unverified），不靠提示詞。
- dab055 四項修正已閉（r1174，STATE 250-263）；argonaut 已 merge。

## 紅線（不變）
main 不動；不手動 push；不讀 `/srv/eval` hidden/scorer；不洩露 `secrets/extract.env`；
el4.1 未呼叫真模型；不發 frozen 實驗、不做大重跑。
