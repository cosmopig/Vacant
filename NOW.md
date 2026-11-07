# 現在（第 1180 輪，2026-11-07）

## 這一輪（vq-el4.3：run_eval.py 第一項——G1 擷取需求 vs 手寫需求）
- **新工具**：`ops/reqloop/extract/run_eval.py`（離線、不呼叫模型）：兩套需求各跑
  `checks.py` 重算；good 三態 VERIFIED/FP/UNKNOWN；bad 任一 FAIL 即抓出；
  門禁＝抓錯 ≥70% 且 0 冤枉；退出碼 0/20/2（缺擷取 fail-closed）；
  成本讀 `~/dev/ops/state/vibe_calls.jsonl`，缺值 UNKNOWN 不填 0。
- **真實結果（G1，7 題、39 bad／7 good；glm53 重擷取 7 次呼叫、約 10.7 萬 token）**：
  - 抓錯：**手寫 39/39 vs 擷取 27/39（69.2%）**
  - 冤枉：**手寫 0 vs 擷取 4**
  - good VERIFIED：擷取 0/7（必要條目含 unverified → UNKNOWN）
  - **門禁 FAIL（RC=20）**——未達 70% 且 >0 冤枉。舊提示基線 12/39、冤枉 0（也在 STATE）。
- **根因與修**：模型把 input 來源參數寫成 `data_file`（rowset_filter/group_aggregate/
  summary_numbers 要 `input_csv|input_json`）→ 靜默 UNKNOWN。已修（TDD）：
  `_REQUIRED_PARAMS` 補三 verifier、`_INPUT_SOURCE_VERIFIERS` 靜態驗證（錯名→unverified）、
  `VERIFIER_HINTS` 標參數名；`checks.py` 兩個檢查器條目非物件 → UnknownSource 不 crash。
- **下一步（依 RLOOP_PLAN「沒過就改擷取方法，不寫報告」）**：
  1. 4 格冤枉的 claim 級對照（哪個 verifier 對 good 誤殺）→ 定 round2 改法；
  2. round2 擷取（改 prompt 或 verifier 選擇策略）＋重跑 run_eval；
  3. argon `7639e032`「12 checker 完整參數與子欄位驗證」待 CI 綠再合併（與本輪同向）。
- 驗證：`pytest tests/test_reqloop_extract.py tests/test_reqloop_run_eval.py` **47 passed**；
  run_eval RC=20（誠實 FAIL）。commit `bafa61bc`、`3d1b3969`。
- 未過 CI 故未合併 argon；未發射；effects2_20261106 未動、未重跑；dab_055 候點名；1753 排除。

## 紅線（不變）
main 不動；不手動 push；不讀 `/srv/eval` hidden/scorer；不洩露金鑰；不繞過 `glm` 直連 vibe；
不改 `repair.py`／G1 `requirements.json`／G1 資料／凍結快照；本輪 7 次 GLM 5.3 擷取（票內授權路徑）。
