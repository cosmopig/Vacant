# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1506；票 P20261112_1125-2 done：L008 發射前檢定力量具＋報告＋單元測試，commit 565730bc8，驗收 VERDICT: L008_POWER_OK RC=0＋2 passed，票在 done/）
- **較上輪好的命令：** `python3 ops/audits/l008_power_analysis.py --selftest` 由檔案不存在 exit 1 → `VERDICT: L008_POWER_OK` RC=0（正3＋負3全生效）；`pytest tests/test_reqloop_l008_power.py` 由檔案不存在 → 2 passed。
- **關鍵發現：** n=60 全 12 格 power 0.110–0.685 皆 <0.80（最小 n 77–460）——Phase 1 樣本量不足 80% power；發射前需人類裁決加題或降 power 目標（票尾已記；量具中立、不改 L008 設計）。
- **誠實記帳：** 0 model calls；新增腳本 120 行＋測試 48 行＋報告 1；0 行產品碼改動（新增檔 only）；mde n_required 只核格式（O(n²) 單格 12.6s、docstring 明示），n=60 power 全格重算核對。
- **紅線：** 無 push（loop 自推 auto/qwen27b）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、未跑 full pytest。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。

## 未完（≤3、交下輪）
1. CI 一次讀取（三分支新 HEAD：qwen 565730bc8＋簿記 commit／argon、worker 同步 commit；不 poll；紅→讀 log 根因不猜）。
2. wt_clean：worker 在途輪收斂檢查（f1-f4 不再出現）→freeze_check 12/12 複核。
3. e013 票（bounced/）候規劃者修驗收 grep；G 系列候人類裁決（vq-kax、0 呼叫）。

## 下輪入口（≤3）
- ci_status.py 一次讀取；紅→log 根因。
- 下張票：`bd list --parent vq-el4 --all` 照順序；呼叫 GLM／DeepSeek 一律用 `glm` 指令。
- 守衛：NOW.md ≤3KB、ops/loop/NOW.md 與 root byte-identical、ops/STATE.md＝canonical Current State 最新條目（bk_state 契約）。
