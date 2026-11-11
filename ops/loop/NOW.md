# NOW.md — 現況（≤3KB）

## 輪次／階段／狀態
r1432（2026-11-11）：**P20261111_0710-1 G3 重發（20261111b）審計摘要收案完成**（ticket→done；0 model calls）。
- 機械重算 b 12 格 → 新增 `ops/audits/g3_fire_20261111b_summary.json`：**4ok／6err／2not_run**——native_pi 4/4 ok（21971/44174/23922/14458 tok）；reqlist_only 0ok/3err/1not_run；full_rloop 0ok/3err/1not_run（dab_216）；stop_reason=quota。
- tokens 獨立重算：104525（4 pi 格）＋28392（4 擷取）＝**132917**＝totals.tokens；known_usages=8（非空守衛）；hidden_after 12×UNKNOWN（打分＝人類/vlab 側、本輪未做）。
- 腳本修（測試未動）：舊碼硬編碼首發敘事（cells_run==12、8×token_limit＋3×timeout、49744 note）→ 對重發照跑會把如實 not_run 判 BROKEN／寫假摘要；改 cells_run＝12-not_run、failures/scope_note/token note/fire 全資料驅動；首發 live raw 仍 VERDICT OK（正控制）。
- 驗收（本輪新跑）：`VERDICT: G3_FIRE_SUMMARY_OK` rc=0；9 passed；anchors 5 passed。
- **AMEND-3（08:40Z 人類裁決）已到**：授權 g3.py 修法 a（build_cell_prompt 顯式無工具覆寫）＋b（max_calls 依 pi ~7 calls/格重測）＋20261111c 重發一次（不重試、預算欄位不動）＝下輪工單（vq-kax），本輪未執行。

## 下一步（下一輪）
- vq-kax（已獲 AMEND-3 核准）：① build_cell_prompt（含修復輪）頂部加顯式無工具覆寫指令 ② QuotaGuard max_calls 依「pi ~7 calls/格」重測（算式寫回票面）③ 重發一次 → g3_fire_20261111c（同批 4題×3臂、不得當獨立樣本）。
- hidden 打分（首發 1＋重發 4 ok 格）——人類/vlab 側；CI 裁決。

## 關鍵約束（紅線）
- 無 push（loop 自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不改；g3.py 改動僅依 vq-kax 工單（AMEND-3 為其授權，執行順序照工單）。
- /srv/eval/hidden/、scorer.py 不讀；缺值 UNKNOWN 不填 0；hidden_after＝UNKNOWN；同批重發非獨立樣本、不宣稱臂 superiority。
- /srv/vlab/queue 不寫；無 poll CI；無 full pytest。

## 證據與下輪驗證點
- b 摘要：`ops/audits/g3_fire_20261111b_summary.json`（result 11477 B、sha256 613919ede3334c0b…）。
- 驗收指令：`python3 ops/audits/g3_fire_20261111_summary.py ~/dev/ops/g3_fire_20261111b/g3_result.json ops/audits/g3_fire_20261111b_summary.json` → VERDICT OK；`pytest tests/test_reqloop_g3_fire_summary.py` → 9 passed。
- 本輪改動＝審計腳本（敘事資料驅動化）＋b 摘要新檔＋簿記 4 檔×3 分支；0 產品碼（g3.py 未動）、0 model calls。
