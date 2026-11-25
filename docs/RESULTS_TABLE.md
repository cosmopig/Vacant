# Vacant 量測結果總表

> 由 `ops/redo/analysis/results_table.py` 從各批 REPORT.json、計畫檔與 run root 直接產生（2026-11-25 00:45Z）。**不要手改**；要改內容就改來源或 `ops/redo/results/batches.json`，再重跑。
> 引用規則照 REPORT 的 quoting_rule：只有 state=EFFECTIVE 且沒有 harness 中途變更的整批數字可以引用，引用時連同模型、agent、題庫、對數一起講；UNRESOLVED／INCOMPLETE 不是負結果。

## 已結案

通過數：對照 → 處理（各臂 通過/計分格數）。b＝只有對照過、c＝只有處理過、p＝精確雙尾 McNemar。後端速度：每輪模型回應 中位／平均／p90（秒）、處理臂內層撞單次上限的比例、對照臂單次的中位牆鐘與逾時數。「中位」是 turn_latency.py 的最近秩取法：n 為偶數時取上中位數（例如 confirm2 的 A 單次 300.1 秒，標準中位數 289.9 秒）；p90 同為最近秩。

| 批次 | 題庫 題數×重複 | 對照 對 處理 | 模型／後端 | 產品 wheel | 通過數 | b／c／p | state | 放行卻錯 | 後端速度 | 結論 |
|---|---|---|---|---|---|---|---|---|---|---|
| redo1 | polyglot_py 34×5 | 原生 pi 對 harness 重開×3 | gemma-4-12b-it-qat／1004 llama.cpp j1 | — | 84/170 → 113/168（2 對 infra_void 不計） | 7／36／9e-06 | **EFFECTIVE** | 0 | 每輪 6.3／11.6／21.5 s；P 撞上限 —；A 中位 285.7s、逾時 12/170 | [CONCLUSION_20261117_REDO1.md](../decisions/conclusions/CONCLUSION_20261117_REDO1.md) |
| redo1_opencode | polyglot_py 34×5 | 原生 opencode 對 harness 重開×3 | gemma-4-12b-it-qat／1003 llama.cpp j1 | — | 79/170 → 114/170 | 10／45／2e-06 | **EFFECTIVE** | 0 | 每輪 —／—／— s；P 撞上限 —；A 中位 225.5s、逾時 0/170 | [CONCLUSION_20261121_REDO1_OPENCODE.md](../decisions/conclusions/CONCLUSION_20261121_REDO1_OPENCODE.md) |
| screen16 | polyglot_py 16×1 | 原生 pi 對 harness 重開×3 | gemma-4-12b-it-qat／1004 llama.cpp j1 | — | 2/16 → 9/16 | 0／7／0.015625 | **EFFECTIVE** | 0 | 每輪 6.2／12.9／21.9 s；P 撞上限 —；A 中位 645.9s、逾時 1/16 | — |
| screen16_opencode | polyglot_py 16×1 | 原生 opencode 對 harness 重開×3 | gemma-4-12b-it-qat／1003 llama.cpp j1 | — | 4/16 → 9/16 | 2／7／0.179688 | **UNRESOLVED** | 0 | 每輪 —／—／— s；P 撞上限 —；A 中位 255.8s、逾時 0/16 | — |
| screen16_qwen27b | polyglot_py 16×1 | 原生 pi 對 harness 重開×3 | qwen/qwen3.8-27b／1003 llama.cpp j1 | — | 13/16 → 15/16 | 0／2／0.5 | **UNRESOLVED** | 0 | 每輪 3.5／15.4／55.2 s；P 撞上限 —；A 中位 79.9s、逾時 0/16 | — |
| screen16p4 | polyglot_py 16×1 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／1003 llama.cpp j1 | （本機 checkout） | 3/16 → 8/16 | 0／5／0.0625 | **UNRESOLVED** | 0 | 每輪 5.2／8.9／17.8 s；P 撞上限 68%；A 中位 1800.0s、逾時 9/16 | [CONCLUSION_20261120_CONFIRM1.md](../decisions/conclusions/CONCLUSION_20261120_CONFIRM1.md) |
| confirm1 | polyglot_py 34×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／1003 llama.cpp j2 | （本機 checkout） | 89/170 → 105/170 | 13／29／0.01952 | **EFFECTIVE** | 0 | 每輪 6.8／13.4／28.5 s；P 撞上限 67%；A 中位 474.9s、逾時 38/170 | [CONCLUSION_20261120_CONFIRM1.md](../decisions/conclusions/CONCLUSION_20261120_CONFIRM1.md) |
| confirm1c | polyglot_py 34×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／1004 llama.cpp j1 | （本機 checkout） | 80/170 → 103/170 | 6／29／0.000117 | **EFFECTIVE** | 0 | 每輪 5.6／11.8／21.8 s；P 撞上限 36%；A 中位 367.1s、逾時 19/170 | [CONCLUSION_20261121_CONFIRM1C.md](../decisions/conclusions/CONCLUSION_20261121_CONFIRM1C.md) |
| unused40 | exercism_py_unused 40×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／1004 llama.cpp j1 | 1aad1444（venv 已刪，依 rc1_dist） | 184/200 → 192/200 | 1／9／0.021484 | **EFFECTIVE** | 0 | 每輪 1.3／5.4／10.9 s；P 撞上限 6%；A 中位 12.1s、逾時 3/200 | [CONCLUSION_20261121_UNUSED40.md](../decisions/conclusions/CONCLUSION_20261121_UNUSED40.md) |
| hardpy26（Colab） | exercism_py_hard 26×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／Colab L4 vLLM j6 | 490a9051（計畫文字） | 114/130 → 116/130 | 3／5／0.726562 | **UNRESOLVED** | 0 | 每輪 6.7／24.5／57.9 s；P 撞上限 26%；A 中位 118.2s、逾時 6/130 | [CONCLUSION_20261121_HARDPY26_COLAB.md](../decisions/conclusions/CONCLUSION_20261121_HARDPY26_COLAB.md)、[CONCLUSION_20261122_E4B_HARDPY26.md](../decisions/conclusions/CONCLUSION_20261122_E4B_HARDPY26.md) |
| W3-5 Py 篩選 | exercism_py_pool 106×1 | 原生 pi 對 原生 pi | gemma-4-12b-it-qat／Colab L4 vLLM j6 | — | 101/106 → 99/106 | 4／2／0.6875 | **UNRESOLVED** | 0 | 每輪 5.4／19.1／33.1 s；P 撞上限 —；A 中位 55.2s、逾時 4/106 | [CONCLUSION_20261121_W35_PY.md](../decisions/conclusions/CONCLUSION_20261121_W35_PY.md) |
| W3-5 Py 確認 | exercism_py_pool 9×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／Colab L4 vLLM j6 | 28e5480c | 27/45 → 25/45 | 6／4／0.753906 | **UNRESOLVED** | 0 | 每輪 11.9／43.8／91.7 s；P 撞上限 63%；A 中位 791.3s、逾時 9/45 | [CONCLUSION_20261121_W35_PY.md](../decisions/conclusions/CONCLUSION_20261121_W35_PY.md) |
| W3-5 JS 篩選 | exercism_js_pool 137×1 | 原生 pi 對 原生 pi | gemma-4-12b-it-qat／Colab L4 vLLM j6 | — | 106/137 → 106/137 | 11／11／1.0 | **UNRESOLVED** | 0 | 每輪 4.0／31.4／75.2 s；P 撞上限 —；A 中位 123.3s、逾時 13/137 | [CONCLUSION_20261122_W35_JS.md](../decisions/conclusions/CONCLUSION_20261122_W35_JS.md) |
| confirm2c（Colab） | polyglot_py 34×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／Colab L4 vLLM j6 | 37005ec2 | 96/170 → 98/170 | 18／20／0.871415 | **UNRESOLVED** | 0 | 每輪 11.7／46.7／106.4 s；P 撞上限 75%；A 中位 1016.2s、逾時 51/170 | [CONCLUSION_20261122_CONFIRM2C.md](../decisions/conclusions/CONCLUSION_20261122_CONFIRM2C.md) |
| confirm2 | polyglot_py 34×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／1004 llama.cpp j1 | 37005ec2 | 86/170 → 109/170 | 11／34／0.000824 | **EFFECTIVE** | 0 | 每輪 5.8／11.1／20.9 s；P 撞上限 35%；A 中位 300.1s、逾時 12/170 | [CONCLUSION_20261124_CONFIRM2.md](../decisions/conclusions/CONCLUSION_20261124_CONFIRM2.md) |
| hardjs34 | exercism_js_d4 34×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／1003 llama.cpp j1 | 28e5480c | 124/170 → 140/170 | 1／17／0.000145 | **EFFECTIVE** | 0 | 每輪 3.4／8.2／18.7 s；P 撞上限 30%；A 中位 35.7s、逾時 22/170 | [CONCLUSION_20261124_HARDJS34.md](../decisions/conclusions/CONCLUSION_20261124_HARDJS34.md) |
| E4B hardpy26 | exercism_py_hard 26×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-e4b-it-qat／Colab L4 vLLM j2 | 5bbc57af | 61/130 → 84/130 | 8／31／0.000294 | **EFFECTIVE** | 0 | 每輪 3.6／10.3／28.6 s；P 撞上限 2%；A 中位 66.5s、逾時 0/130 | [CONCLUSION_20261122_E4B_HARDPY26.md](../decisions/conclusions/CONCLUSION_20261122_E4B_HARDPY26.md) |
| confirm3 | polyglot_py 34×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／Colab A100 vLLM j4 | 5bbc57af | 104/170 → 120/170 | 7／23／0.005223 | **EFFECTIVE** | 0 | 每輪 8.3／27.4／55.0 s；P 撞上限 43%；A 中位 375.6s、逾時 9/170 | [CONCLUSION_20261124_CONFIRM3.md](../decisions/conclusions/CONCLUSION_20261124_CONFIRM3.md) |

## 進行中／排隊／作廢／撤回

進行中的批次只顯示進度，不顯示通過數（預註冊：跑完之前不看數字）。

| 批次 | 狀態 | 題庫 題數×重複 | 對照 對 處理 | 模型／後端 | 產品 wheel | 進度 | 備註 | 文件 |
|---|---|---|---|---|---|---|---|---|
| W3-5 JS 確認（重跑） | 作廢 | （Colab 題庫：發射時指定） 30×3 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／Colab A100 vLLM j4 | 5bbc57af | — | 跑完但結果沒取回（取回 OOM、VM 消失），數字不可引用 | [VOID.md](../ops/redo/results/void/w35js_rerun_a100/VOID.md) |
| atimeout | 進行中 | py_mix_pg34_hard26 60×3 | vacant do pi（單次 600s） 對 vacant do pi（單次 900s） | gemma-4-12b-it-qat／1003 llama.cpp j2 | 5bbc57af | 46 對完成（runner.log） |  | — |
| confirm2oc | 進行中 | polyglot_py 34×5 | 原生 opencode 對 vacant do opencode（單次 600s） | gemma-4-12b-it-qat／1004 llama.cpp j1 | 5bbc57af | 31 對完成（runner.log） |  | — |
| confirm1b | 作廢 | polyglot_py 34×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／1004 llama.cpp j2 | （本機 checkout） | — |  | [VOID.md](../ops/redo/results/void/confirm1b/VOID.md) |
| W3-5 JS 確認（第一次） | 作廢 | exercism_js_pool 30×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／Colab L4 vLLM j6 | 28e5480c | — | 約 100/150 對時基礎設施中斷，數字不可引用 | [VOID.md](../ops/redo/results/void/w35js_confirm/VOID.md) |
| confirm2oc_vacantdo_rel092_opencode_gemma12b_1003 | 撤回 | polyglot_py 34×5 | 原生 opencode 對 vacant do opencode（單次 600s） | gemma-4-12b-it-qat／1003 llama.cpp j1 | 37005ec2 | — |  | [confirm2oc_vacantdo_rel092_opencode_gemma12b_1003.WITHDRAWN.md](../ops/redo/plans/confirm2oc_vacantdo_rel092_opencode_gemma12b_1003.WITHDRAWN.md) |
| unused40_vacantdo_rc1_pi_gemma12b_colab | 撤回 | （Colab 題庫：發射時指定） 40×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／Colab L4 vLLM j4 | （VM wheel，計畫未寫） | — |  | [unused40_vacantdo_rc1_pi_gemma12b_colab.WITHDRAWN.md](../ops/redo/plans/unused40_vacantdo_rc1_pi_gemma12b_colab.WITHDRAWN.md) |
| hardpy26_vacantdo_rc3_pi_gemma12b_1004 | 撤回 | exercism_py_hard 26×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-12b-it-qat／1004 llama.cpp j1 | 490a9051（venv 已刪，依 rc3_dist） | — |  | [hardpy26_vacantdo_rc3_pi_gemma12b_1004.WITHDRAWN.md](../ops/redo/plans/hardpy26_vacantdo_rc3_pi_gemma12b_1004.WITHDRAWN.md) |
| atimeout_p900_vs_p600_rel092_colab | 撤回 | （Colab 題庫：發射時指定） 60×3 | vacant do pi（單次 600s） 對 vacant do pi（單次 900s） | gemma-4-12b-it-qat／Colab L4 vLLM j6 | （VM wheel，計畫未寫） | — |  | [atimeout_p900_vs_p600_rel092_colab.WITHDRAWN.md](../ops/redo/plans/atimeout_p900_vs_p600_rel092_colab.WITHDRAWN.md) |
| e4b_hardpy26_vacantdo_rc4_colab | 撤回 | （Colab 題庫：發射時指定） 26×5 | 原生 pi 對 vacant do pi（單次 600s） | gemma-4-e4b-it-qat／Colab L4 vLLM j6 | （VM wheel，計畫未寫） | — |  | [e4b_hardpy26_vacantdo_rc4_colab.WITHDRAWN.md](../ops/redo/plans/e4b_hardpy26_vacantdo_rc4_colab.WITHDRAWN.md) |
