# G3 重發（20261111b）full_rloop content_reverify 逐條差異解讀

- 對應：2026-11-11 人類常設定案第 2.a 條——full_rloop 的 content_reverify 逐條差異是否支持
  「需求驅動 R-loop 在未見題上抓到並修好內容錯誤」；4 題只出方向性結論、每個數字帶分母、不做普遍宣稱。
- 數據來源（本輪實際開啟核驗）：
  - `ops/audits/g3_fire_20261111b_summary.json`（10803 B；identity.result_sha256 `613919ede3334c0b…`，
    raw `~/dev/ops/g3_fire_20261111b/g3_result.json` 11477 B、sha256 與 identity pin 一致）
  - `~/dev/ops/g3_fire_20261111b/g3_result.json` cells 原始欄位（rounds／error／content_reverify 逐格）
  - `ops/audits/g3_fire_20261111_summary.json`（首發 20261111，05:41:18Z；供兩發對比）
  - `vacant_network/reqloop/g3.py`：`content_recheck`（行 251–260，草稿落盤 answer.txt 後由
    `checks.run_requirement_checks` 程式重算，模型自評不算數）、cell 主循環（行 986 `except G3CallError`、
    行 1001 `if reverify_on:`、行 1004 `content_recheck(...)` 呼叫點）
- 成本：31 次呼叫、132917 tokens（cell 104525＋extract 28392，known_usages=8、缺值 UNKNOWN 不填 0）；
  hidden_after 12/12 UNKNOWN（打分在人類/vlab 側，本輪未做）。

## 0. 總表（12 格）

| 臂 | ok | error | not_run | content_reverify 完成輪數 |
|---|---|---|---|---|
| native_pi（qwen3.8-27b，pi agent） | 4/4 | 0 | 0 | 不適用（該臂 `enabled=false`，非 full_rloop） |
| reqlist_only（deepseek41 臂） | 0/4 | 3/4（glm rc=4 turn_limit） | 1/4（quota） | 0/4（`enabled=false`） |
| full_rloop（deepseek41 臂） | 0/4 | 3/4（glm rc=4 turn_limit） | 1/4（dab_216，quota） | **0/4（`enabled=true`，rounds 全為 `[]`）** |

全批唯一 ok 臂是基線臂 native_pi；需求驅動臂（reqlist_only/full_rloop）0/8 格產出任何 answer。

## 1. full_rloop 4 格 content_reverify 逐格記錄（重發 b）

| task | status | rounds | gap_reason | diff（fixed/regressed/unresolved） |
|---|---|---|---|---|
| dab_129 | error（turn_limit，round 1 答題階段） | `[]`（0 輪） | 無（`null`） | 無（`null`） |
| dab_144 | error（turn_limit，round 1 答題階段） | `[]`（0 輪） | 無（`null`） | 無（`null`） |
| dab_176 | error（turn_limit，round 1 答題階段） | `[]`（0 輪） | 無（`null`） | 無（`null`） |
| dab_216 | not_run（quota 兜底：呼叫數 31 ≥ 後備上限 28） | `[]`（0 輪） | 無（`null`） | 無（`null`） |

四格 `content_reverify` 皆為 `{"enabled": true, "rounds": [], "final_verdict": null, "diff": null, "error": null}`。
**沒有任何一格進入過「反例→修復→重驗」循環，因此 fixed/regressed/unresolved 三欄皆無值（0/4），
不是「0 個錯誤被抓到」。**

### 為什麼 0 輪——代碼路徑（g3.py）

1. cell 主循環 round 1 先 `guard.call(prompt, model=answer_model, …)` 產出草稿（行 968–986）。
2. 只有呼叫成功、`cell["answer"]` 落位之後，才到行 1001 `if reverify_on:` 的
   `content_recheck(task_ws, req_set, rd, text)`（行 1004）：把草稿寫成 answer.txt，
   由 checks 程式從任務資料重算各 claim（PASS/FAIL/UNKNOWN/CONFLICT），再
   `confirmed_gap`（必需 FAIL 或缺必要答案項）決定是否進 round 2 帶 `build_repair_feedback` 修復。
3. 本批 6 格 glm 臂全部在第 1 步以 `glm rc=4 … Stopped: turn_limit`（G3CallError）終止（行 986 分支：
   `status="error"`、break）——**失敗發生在答題階段，content_recheck 在控制流上根本未被觸及**。
   這是基礎設施/通道失敗，不是「檢查器跑完發現無缺口」。

## 2. 逐題方向性結論（每題帶分母；4/4 題結論相同）

問題：「需求驅動 R-loop 在該未見題上抓到並修好內容錯誤」？

| task（需求數／答案項） | full_rloop 產出 answer | content_reverify 輪數 | 抓到內容錯誤 | 修好（fixed） | 方向性結論 |
|---|---|---|---|---|---|
| dab_129（4 req：mean_fare、std_dev_fare） | 0/1 | 0/1 | 0/1（未測得） | 0/1（未測得） | **未測得（UNKNOWN），無支持證據** |
| dab_144（14 req：dem/gop 的 mean/std/dist） | 0/1 | 0/1 | 0/1（未測得） | 0/1（未測得） | **未測得（UNKNOWN），無支持證據** |
| dab_176（5 req：median_age） | 0/1 | 0/1 | 0/1（未測得） | 0/1（未測得） | **未測得（UNKNOWN），無支持證據** |
| dab_216（10 req：mean、std_dev） | 0/1（not_run/quota） | 0/1 | 0/1（未測得） | 0/1（未測得） | **未測得（UNKNOWN），無支持證據** |

- 4/4 題的方向：**沒有證據支持**「R-loop 在未見題抓到並修好內容錯誤」；同時**也沒有證據反對**——
  機制在兩臂（reqlist_only、full_rloop）8/8 格都死在答題通道（fire b：6/8 turn_limit＋2/8 quota；
  fire a：8/8 token_limit），content_reverify 0/8 格運行過（兩發合計 0/8 輪）。
- 口徑：未測得＝UNKNOWN，不是 PASS、也不是「沒有內容錯誤」；不得改寫為「R-loop 無效」或「無效」——
  前者需要 hidden 打分與 ≥2 rep（本批 1 rep、hidden_after 全 UNKNOWN），後者需要機制先跑完。
- native_pi 4/4 ok（21971/44174/23922/14458 tok）是基線臂產出，其內容對錯未打分（UNKNOWN），
  不能與 full_rloop 的 0/4 相比得出任何臂 superiority。

## 3. 兩發對比（fire a → fire b）

| 項 | fire a（20261111，05:41Z） | fire b（20261111b，07:30Z） |
|---|---|---|
| 總 ok | 1/12（僅 dab_129/native_pi） | 4/12（native_pi 全 4 題） |
| full_rloop | 4/4 error（glm rc=4 token_limit） | 3/4 error（turn_limit）＋1/4 not_run（quota） |
| full_rloop content_reverify 輪數 | 0/4 | 0/4 |
| pi 臂 | 3/4 timeout（300s） | 0/4 timeout（AMEND-2 每格 600s） |
| tokens | 49744（known_usages=5） | 132917（known_usages=8） |

- pi 臂的 timeout 在 b 發消失（4/4 ok）；**glm 答題臂的失敗從 token_limit 換成 turn_limit，位置不變：
  都在 round 1 答題階段、content_recheck 之前**。故障模式一致＝答題通道在產出 answer 前終止。
- 這支持 vq-kax（AMEND-3 已核准）的修法方向：`build_cell_prompt`（含修復輪）頂部加顯式無工具覆寫
  ＋`max_calls` 依 pi 臂實際 ~7 calls/格重測，再發一次（20261111c、同批 4 題、不重試、預算欄位不動）。

## 4. 本報告不做的事（紅線複述）

- 不宣稱任何臂 superiority、不宣稱「R-loop 無效／有效」；不填 0、不把 UNKNOWN 當 PASS。
- 未讀 /srv/eval hidden/ 與 scorer.py；未改凍結四檔（repair/extract/checks/run_eval）；
  未改 g3.py；0 model calls（純本地靜態審計）。
- 同批重發（a、b、將來的 c）不得當獨立樣本；本批 1 rep、本地模型（H-12 口徑）。

## 5. 下一步（閉環）

1. vq-kax（已獲 AMEND-3 核准）：修法 a＋b → g3_fire_20261111c 重發一次——**G3.1 的 H1
   （機制可達性）只有在這之後才可判定**。
2. G3.1 預註冊假說與候選題單：`ops/reqloop/g3_1_candidate_hypothesis.md`（本輪產出，待人類核准後凍結 manifest）。
3. hidden 打分（a 發 1 ok＋b 發 4 ok 共 5 格 answer）——人類/vlab 側；CI 裁決仍待。
