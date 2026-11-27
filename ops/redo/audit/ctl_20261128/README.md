# 控制器實驗稽核包（2026-11-28）

給獨立複核用（只讀推上去的檔）。三批分開：`ctl12_q9`（qwen3.5-9b，本機）、`ctl34_g12`（gemma-4-12b，本機）、`ctl12_colab_e4b`（gemma-4-E4B，Colab L4 vLLM）。
檔案裡沒有家目錄路徑、主機位址或帳號；主機只用 provider 名（lms1003*／lms1004*；Colab 是單一 VM）。

## 檔案
- `<batch>_cells.csv`／`_cells.json`：逐格結果（第二版加了 `started`／`ended` 與每次嘗試的 `started`，可以按時間檢查 OOM 續跑前後）。JSON 每格附 `attempts[]`，含每次嘗試的驗收通過數／總數、是否逾時、規則／動作（C 臂）、隱藏評分通過數／總數、token、呼叫數。
- `<batch>_controller_events.jsonl`：C 臂每個決策事件（規則編號、動作、理由、evidence 全部欄位）。
- `<batch>_chains/<題>__<重複>__C/controller_chain.ndjson`＋`.pub.json`：C 臂每格的簽章鏈原檔與公鑰（2026-11-28 第二版補上）。
- `<batch>_chain_anchors.json`：每格的事件數、整檔 sha256、stream_id、鏈頭（`Logbook.head()`）、公鑰、`verify_chain` 結果（140 格全部 true）。重驗：`Logbook([LogEntry.from_json(l) for l in 鏈檔]).verify_chain(PublicIdentity.from_hex(vacant_id, pub_hex))`。⚠ 每格是臨時金鑰、鏈頭在執行時沒有交給外部：簽章只證明鏈內一致。
- `<batch>_indistinguishability.json`：修正 5 的三個條件的原始計數。
- `<batch>_metrics.md`：`ops/redo/analysis/ctl_metrics.py <root>` 的輸出（五指標、C 對 B／R 的配對 McNemar 與成本差）。
- `<batch>_token_timeout_by_arm_host.json`：token、逾時、嘗試次數、第 1 次就過的格數，分臂、分主機。
- 匯出腳本：`ops/redo/analysis/export_ctl_audit.py`；分析腳本：`ops/redo/analysis/ctl_metrics.py`。

## 計畫、預註冊、附錄
- 計畫：`ops/redo/plans/ctl12_pi_qwen9b.json`、`ctl34_pi_gemma12b.json`、`ctl12_colab_e4b.json`（各自的 `prereg` 欄位）。
- 設計與附錄：`decisions/DECISION_20261127_EVIDENCE_CONTROLLER.md`（修正 1–5、凍結、各批紀錄、第十次稽核補註、Colab 事件更正）。
- 結論：`decisions/conclusions/CONCLUSION_20261128_EVIDENCE_CONTROLLER.md`。

## 結論數字對照
| 結論裡的數字 | 來源檔 | 欄位／算法 |
|---|---|---|
| 各批 A／R／B／C 的通過數 | `<batch>_cells.csv` | `hidden_pass==True`、`infra_void` 空，依 `arm` 計數（也見 `<batch>_metrics.md` 的 Hidden Pass） |
| C 對 B、C 對 R 的配對（b／c／p） | `<batch>_metrics.md` | Paired Comparisons 表，(task, rep) 配對、精確 McNemar |
| 無法區分條件 1／2／3 | `<batch>_indistinguishability.json` | `cond1_A_rate`、`cond2_rbc_ge2_attempts`（n_attempts≥2）、`cond3_rules_3to6` |
| 規則觸發次數 | `<batch>_controller_events.jsonl` | 依 `rule` 計數 |
| 弄壞已通過測試的比例 | `<batch>_metrics.md` | Broken-After-Pass 欄 |
| token 差、逾時分布 | `<batch>_token_timeout_by_arm_host.json` | `tokens_per_cell`、`timeouts`、`attempts`，分主機 |

## 第二版（2026-11-28，依 vacant-cloud 獨立複核）
- 補鏈檔、公鑰、真的鏈頭（第一版 `head` 與事件 `seq` 全是 null：匯出腳本找錯鍵名）。
- 逐格表加時間欄位。
- `_metrics.md` 的說明句不再寫死「16 題」（改由計畫算題數 × 重複）。
- Colab 批次的越界讀取掃描：`ops/redo/audit/colab_leak_scan_20261128/`（`ops/redo/analysis/scan_redo_leak.py`）。
- 條件 3 的原始計數含作廢格（ctl34 61 次；只算非作廢格 59 次），條件 2 的分母不含作廢格（102/202；含作廢 102/204）。判定不變。
