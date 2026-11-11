# NOW.md — 現況（≤3KB）

## 輪次／階段／狀態
r1434（2026-11-11）：**P20261111_0710-2 G3 b重發 content_reverify 逐條差異解讀＋G3.1 預註冊完成**（票→done；0 model calls）。
- `ops/audits/g3_fire_20261111b_interpretation.md`：4/4 題方向性結論＝**未測得（UNKNOWN）**——full_rloop 0/4 格產出 answer、content_reverify 0/4 輪／0/4 gap_reason／0/4 diff（fixed/regressed/unresolved）；兩發合計 0/8 輪（a：4×token_limit；b：3×turn_limit＋1×quota），失敗全在 round 1 答題階段（g3.py:986 G3CallError→break）、控制流未達 content_recheck（1001–1004）＝基礎設施失敗、非「無缺口」；無支持亦無反對證據、不宣稱任何臂 superiority、UNKNOWN 不填 0。
- `ops/reqloop/g3_1_candidate_hypothesis.md`（候選、待人類核准才凍結 manifest 發射）：H1 機制可達性＝c 重發 full_rloop ≥1/4 格完成 ≥1 輪 content_reverify 且 ≥1 條 claim 由 checks 程式重算；**0/4 即證偽→停、升級人類**；H2 條件於 H1（round 1 缺口格 fixed≥1 且 regressed=0；無缺口＝not_applicable，非通過非否決）；候選題單＝同批 4 題（dab_129/144/176/216，非獨立樣本）＋2 題新未見描述統計題僅核准後入批。
- 重發經驗：extract 4/4（各 1 呼叫、6.6–7.9k tok）；pi 基線臂 b 發 4/4（600s/格消 a 發 3 timeout）；glm 答題通道 8/8 停滯＝**通道層**故障、與需求類型（均值/中位數/標準差/分布判斷 4 類）無關；「何類需求易修」數據點＝0，不預註冊。
- 驗收（本輪新跑）：一行 `INTERPRETATION_AND_PREREG_OK` rc=0；三源開啟核驗（b summary 10803 B／raw 11477 B sha＝identity pin／首發 summary／g3.py 行 251・986・1001・1004）。

## 下一步（下一輪）
- vq-kax（AMEND-3 已核准）：① build_cell_prompt（含修復輪）頂部加顯式無工具覆寫 ② QuotaGuard max_calls 依 pi 臂 ~7 calls/格重測（算式寫回票面）③ 20261111c 重發一次（同批 4 題×3 臂、不重試、預算欄位不動）→ 判 H1。
- hidden 打分（a 1＋b 4＝5 格 answer）——人類/vlab 側；CI 裁決仍待。

## 關鍵約束（紅線）
- 無 push（loop 自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（repair/extract/checks/run_eval）；g3.py 改動僅依 vq-kax 工單；G3.1 核准前未凍結未發射。
- /srv/eval/hidden/、scorer.py 不讀；缺值 UNKNOWN 不填 0；hidden_after＝UNKNOWN；同批重發非獨立樣本、不宣稱 superiority。
- /srv/vlab/queue 不寫；無 poll CI；無 full pytest；不新增錯誤字串 regex／靜態提示工單。

## 證據與下輪驗證點
- 解讀：`ops/audits/g3_fire_20261111b_interpretation.md`；預註冊：`ops/reqloop/g3_1_candidate_hypothesis.md`。
- 驗收：`python3 -c "import json, pathlib; assert pathlib.Path('ops/audits/g3_fire_20261111b_summary.json').exists(); interp=pathlib.Path('ops/audits/g3_fire_20261111b_interpretation.md').read_text(); prereg=pathlib.Path('ops/reqloop/g3_1_candidate_hypothesis.md').read_text(); assert 'content_reverify' in interp and 'G3.1' in prereg; print('INTERPRETATION_AND_PREREG_OK')"`。
- 本輪改動＝2 新 markdown＋簿記 4 檔；0 產品碼（g3.py 未動）、0 model calls。
