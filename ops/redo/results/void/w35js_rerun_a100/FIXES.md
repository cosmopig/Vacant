# W3-5 JS 重跑 VOID 的四個根因：修正（2026-11-24；修完才准再用 Colab）

| 根因 | 修正 | 位置 | 驗證 |
|---|---|---|---|
| 1 結果包約 6.5 GB（整個 run root 連工作區副本、node_modules 一起打包） | 結果包與快照都排除 `node_modules`、`attempt_*/w`、`snap-*`、`start-copy-*`、`start-snap-*`、`bkp-*`、`__pycache__`；保留 cell.json、result.json、日誌、REPORT | `ops/redo/colab/vm_run_batch.sh`、`ops/redo/colab/fetch_batch.sh`（`--force` 的打包）、`~/dev/ops/colab_snapshot2.sh` v2.2 | 本機模擬：含 3 MB `node_modules` 的 run root 打包後 0 個 node_modules 成員 |
| 2 取回要整個檔進記憶體（`colab download` 被 OOM 殺 14 次） | 在 VM 上 `split` 成 `FETCH_PART_MB`（預設 256 MB）分段，逐段下載、在本機接回，再驗整包 sha256（與 BATCH_DONE 的雜湊比對照舊） | `ops/redo/colab/fetch_batch.sh` | 假 colab 指令端到端：4 段接回、sha256 相符、FETCH_OK |
| 3 快照 148/149 次失敗（tar 回 1 就算失敗、`colab exec` 30 秒沒輸出就放棄、包太大） | 排除同一份清單；tar 回 1（file changed）照常接受；`colab exec --timeout 1800` | `~/dev/ops/colab_snapshot2.sh` v2.2（舊版 v2.1 留存） | VM 端指令在本機模擬：SNAP_RC 0、sha256 輸出正確 |
| 4 預算看門只看 confirm3；取回失敗的 VM 沒人關，空燒到餘額 0 | 新看門 `colab_budget_watch.py`：看帳號上**所有**未取回、未停機的批次，直到帳號上沒有批次 session 才結束；取回失敗或跑完沒人取回超過 2 小時 ⇒ 快照後 `colab stop`；預估超支先停不受保護的；餘額低於 5 單元全部停。`colab_launch.sh` 每次 LAUNCH_OK 時自動確保該帳號的看門在跑 | `~/dev/ops/colab_budget_watch.py`、`~/dev/ops/colab_launch.sh` | 乾跑（假帳號、兩批）：取回失敗那批在 grace 後被停；受保護批只記警告；餘額低於地板時全部停 |

另外記下、但這次不改的：
- 簽章鏈（VM 上的 `$VACANT_HOME/trace`）沒有隨結果包取回，所以 Colab 批次無法在本機跑 `vacant audit list --strict`（confirm3 結論已註明）。下一次發 Colab 前把它加進結果包。
- keepalive 在 FETCH_FAILED 時仍「留著 session 等人工檢查」；現在由看門在 2 小時後收掉。
