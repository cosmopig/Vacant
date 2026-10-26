# 方向 B 實跑證據收口：乾淨重抽 EFFECTIVE（v4）、短失敗提示邊際貢獻 UNRESOLVED（v5）（2026-10-26）

> 一頁：方向 B「程式任務成果更好」在 live 上量到了什麼、哪些可引用、哪些不可引用、剩什麼。
> 兩批都在**第一次 model call 之前**凍結預註冊；本檔不重跑實驗，只做收口與引用口徑。
> 前導設計：`DECISION_20261025_REAL_SIGNAL_RESAMPLE_DESIGN.md`（真實訊號＝交件時重跑可見驗收，
> 不是讀 agent 的自我報告）。模型/槽位：qwen/qwen3.8-27b、單一上游槽位（100.119.113.56:1234）。

## 0. 問題鏈（同一 34 題 polyglot_py 全庫，逐批問下一層）

| 批 | 對照 | 主要結果（pooled，exact two-sided McNemar，(task, rep) pair 為單位） | 狀態 |
|---|---|---|---|
| v3（6 題子集） | A_none vs B_resample3 | b=0, c=5, p=0.0625，n=18 pairs | UNRESOLVED（α=0.05 未達） |
| **v4（34 題）** | A_none vs B_resample3 | **b=5, c=15, p=0.0414，n=102 pairs**（接受 A 56/102 vs B 66/102） | **EFFECTIVE per prereg** |
| **v5（34 題）** | B_resample3 vs C_fresh_hint3 | **b=6, c=8, p=0.7905，n=102 pairs**（接受 B 65/102 vs C 67/102） | **UNRESOLVED** |

方向 B 目前可說的：在真實訊號（可見驗收重跑）之上，**乾淨重抽優於一發**（v4，帶 §1 口徑）；
**重抽之上的短失敗提示**（≤380B、只含可見失敗行）在本批**沒有統計上確立的增益**（v5）。
scorer 兩批皆**未使用**（真實訊號列；`scorer_used=false`、`visible_equals_grader=true`）。

## 1. v4：乾淨重抽優於一發（EFFECTIVE per prereg）

- 預註冊：`ops/realrun/prereg_v4.json`，commit `7938f654`，**第一次 model call 前凍結**（`frozen_before_first_model_call: true`）。
- 臂：A_none（control）vs B_resample3（treatment）；34 題 × 3 reps；n=102 pairs、204 runs。
- pooled（primary）：b=5, c=15, p=0.0414 → **EFFECTIVE**；接受率 A 56/102 vs B 66/102。
- per-rep（描述性）：r1 (b=2, c=3, p=1.0) · r2 (b=2, c=4, p=0.6875) · r3 (b=1, c=8, p=0.039)。
- **口徑（引用必帶）**：EFFECTIVE＝「本批上 B 接受的比 A 多」，**不是「證明變好」**（單一模型、
  單一槽位、H-12）；per-rep 只有 r3 低於 raw α，Holm 校正在 3 rep 上**無一通過**——更嚴的
  per-rep 讀法是 UNRESOLVED，**兩種讀法都記在案**（STATE round 74–79 補記）；v4 與 v1/v2/v3 **不 pool**；
  scorer 未使用（真實訊號列）。
- 證據：`ops/realrun/analyze_v4.json`（＋ per-rep 鏡像）；ops-disk `runs_v4_r{1,2,3}`；
  0 infra_void、0 no_model_content、六不變量 204/204 PASS。
- 釘死：`tests/test_realrun_v4_prereg.py`（6/6，含負對照）。

## 2. v5：短失敗提示的邊際貢獻未確立（UNRESOLVED，合法結果）

- 預註冊：`ops/realrun/prereg_v5.json`，commit `fc4ac6a6`，**第一次 model call 前凍結**；
  primary＝exact two-sided McNemar on (task, rep) pairs, n=102, α=0.05。
- 臂：B_resample3（control）vs C_fresh_hint3（treatment）；34 題 × 3 reps；n=102 pairs、204 runs。
- pooled（primary）：b=6, c=8, p=0.7905 → **UNRESOLVED**（c>b 方向與假設一致但未達 α；
  null 不是 negative、也不是 positive）。
- per-rep（描述性）：r1 (b=2, c=3, p=1.0) · r2 (b=3, c=3, p=1.0) · r3 (b=1, c=2, p=1.0)。
- 口徑：UNRESOLVED 是**合法結果，不是失敗**（prereg honesty 條）；預期效應小於 v4 的 +10pp
  （hint 是重抽之上的**邊際**增益）；pilot（2026-09-25, n=6：fresh_hint 6/6 vs resample 5/6）**無統計力**；
  polyglot_py 無獨立 hidden suite，acceptance＝可見套件（與 v4 同）；scorer 未使用。
- agent 洞（已補，記錄）：round 72 的 mini_agent 不讀 `VACANT_FEEDBACK.md`（V1 的洞：模型可以不讀）；
  修為確定性讀檔＋append、無檔時逐位元組同 v4 agent（commit `889cd5ea`）；wire-log 實證 hint 逐字
  進入 model input（round 81 smoke）。
- 事故記錄：rep-1 首次啟動漏 `--arms` 過濾器、多跑 4 個 A_none cell（`runs_v5_r1/A_none`，
  out-of-prereg、不進 v5 分析、留盤作證據）；已殺掉重啟。
- 證據：`ops/realrun/analyze_v5.json`（repo 鏡像）；ops-disk `runs_v5_r{1,2,3}`；204/204 格、0 infra_void。
- 釘死：`tests/test_realrun_v5_prereg.py`（9/9；含 (b,c)→p 重算、狀態規則、rep 齊全、EFFECTIVE 文本禁 overclaim）。

## 3. 可引用／不可引用（統一口徑）

- **可引用**：「乾淨重抽優於一發」＝v4 EFFECTIVE per prereg（p=0.0414, n=102 pairs, scorer=false,
  單一模型單槽位；per-rep 披露在案、更嚴的 per-rep 讀法為 UNRESOLVED，兩種讀法都記）。
- **可引用**：「重抽之上的短失敗提示，在本批沒有統計上確立的增益」＝v5 UNRESOLVED
  （p=0.7905, n=102 pairs, scorer=false）——不是「hint 無用」。
- **不可引用**：v4 與 v5（及 v1–v3）合併成一個大 n；外推到其他模型／題庫（H-12）；
  任何超出預註冊狀態表的方向性結論（正向或負向）。
- 每個數字必帶：哪一列（真實訊號）、n（pairs）、有沒有用 scorer（沒有）。

## 4. 下一步（方向 B 剩下什麼）

1. **第二模型 cross-replication——不可行（2026-10-26 本輪實查）**：`/v1/models` @ 100.119.113.56:1234
   只列出 `qwen/qwen3.8-27b` 一個模型；端點上沒有第二模型可用。
2. **第二槽位複製**：需同模型第二個 slot/實例；現端點為單槽位（run_batch.py 註記「single slot」），不可行。
3. **按 ASSIGNMENT P1 轉非程式題**：只有「只看紀錄就能判斷」的檢查；新檢查先離線重播，
   對的零誤報才能併。
- 紀律不變：預註冊在第一次 model call 前 commit；v1–v5 互不 pool；UNRESOLVED 是合法狀態；
  引用必帶 §3 口徑。

## 5. 證據／重現

- 預註冊（repo 鏡像）：`ops/realrun/prereg_v4.json`、`ops/realrun/prereg_v5.json`（ops-disk `~/dev/ops/realrun/`）。
- 分析：`ops/realrun/analyze_v4.json`、`ops/realrun/analyze_v5.json`（p 可由 (b,c) 用 `mcnemar_exact` 重算）。
- 釘死測試：`tests/test_realrun_v4_prereg.py`（6/6）、`tests/test_realrun_v5_prereg.py`（9/9）、
  `tests/test_decision_live_v4v5_close.py`（本檔與落盤數據的一致性）。
- 執行：`ops/realrun/run_batch.py`＋`mini_agent.py`（`889cd5ea`）；離線重播（零 LLM）：
  `python3 ~/dev/ops/ref/offline_restart_sim.py ~/dev/ops/ref/c37_final.json 3`。
