# VOID — W3-5 JS 確認批重跑（`w35confirm_js_vacantdo_rc5_a100`，Colab A100，rc5-final，30 題×3）

**狀態：作廢，沒有可引用的數字。** 批次在 VM 上跑完（11/22 23:26Z，90/90 對、infra_void 0），但結果包沒有取回、VM 之後消失。
本機只剩 poll 抓到的進度行（`poll/STATUS.txt`、`poll/runner.log` 的逐格行：A 38/90、P 50/90、b＝10、c＝22，重算 p≈0.050）——**沒有 REPORT.json、沒有 cells，不可引用、不與任何批合併**。
這批不再重跑：JS 產品臂在快後端上的依據是 1003 的 hardjs34（EFFECTIVE，124→140，`decisions/conclusions/CONCLUSION_20261124_HARDJS34.md`）。

## 經過

- 11/22 13:52Z 發射（第 4 次重試才配到 A100）、13:59Z VM 就緒；同帳號（colab2）同時跑 confirm3。
- 11/22 23:26Z 跑完、23:40Z VM 上寫好 BATCH_DONE 與結果包（sha256 `5061f29f…`，約 6.5 GB）。
- 11/23 凌晨起 keepalive 取回：`colab download` 被 OOM killer 殺掉 14 次（本機 7.7 GB 記憶體），最後連線中斷，07:36Z `FETCH_FAILED (session left running for manual check)`。當時兩個操作 session 都撞到每週額度上限，沒有人接手。
- 每小時快照從頭到尾只成功 1 次（13:53Z，0 格），之後 148 次失敗：`tar: file changed as we read it`，以及 `colab exec` 30 秒沒有輸出就放棄。
- colab2 的預算看門只在 confirm3 還沒取回時才看；confirm3 11/23 取回後看門自己結束，JS 的 VM 留著空燒，colab2 餘額歸零（0.00），之後 VM 被回收。

## 根因（下一次用 Colab 之前都要修掉）

1. **結果包太大（約 6.5 GB）**：`fetch_batch.sh` 把整個 run root（`tar -czf … -C run .`）打包。rc5 起 `vacant do` 每次嘗試給 agent 一份自己的 `node_modules` 副本（KNOWN_LIMITS 14），JS 題的每一格、每一次嘗試都留著 `attempt_*/w/node_modules`、`snap-*` 與工作區副本；結論用得到的只有 cell.json、result.json、日誌與 REPORT。
2. **取回要整個檔進記憶體**：`colab download` 在本機把整個檔放進記憶體，大於本機可用記憶體就被 OOM 殺掉；沒有分段、沒有大小上限。
3. **快照對這批幾乎全失敗**：同樣打包整個 run root；`tar` 在批次寫檔時回 1（file changed）就被當成失敗；`colab exec` 沒帶 `--timeout`，大包壓縮超過 30 秒沒有輸出就放棄。結果是 VM 消失時本機沒有任何可用的格。
4. **預算看門沒有涵蓋第二批**：`colab2_budget_watch.py` 只以 confirm3 是否取回決定結束；而 keepalive 在 FETCH_FAILED 時刻意「留著 session 等人工檢查」，兩者合起來沒有任何東西會關掉一台已經跑完、取回失敗的 VM。

修正記在 `ops/redo/colab/` 與 `~/dev/ops`（見同目錄 FIXES.md，修完才准再用 Colab）。
