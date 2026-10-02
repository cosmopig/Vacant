# P10 線 F：命盤的真跑（2026-10-02，舊 VM 100.124.254.83，暫存目錄，enclose=on）

- `final/`：最後一輪（r9，命盤卡第二版，見決議檔第十一節）8 組合成人格各 1 跑。`f1.json`–`f8.json`（每跑的信全文／命盤段／命盤卡原稿與通過後全文／被拿掉的句子／地點順序／
  先寫計畫或先逛／四格窗逐次結果／旁註與撤回結果）、`fNN.lifecycle.jsonl`＋`fNN.lifecycle.sidecar.jsonl`（原封不動的事件流，含 `twin_fortune`）、`SUMMARY.json`。
- `iterations/r1`–`r6`：前 6 輪（r6＝命盤卡第一版的最後一輪，決議檔第六節那張表）；`r7_r8`：第二版開發中的一輪（同一批人格、反覆調指令）的 `f*.json`，只為說明決裁文件第六節那張表怎麼來；r1 的紀錄沒有 `flags`（當時還沒收）。
- 合成人格（不是真人）；每跑跑完撤回（`erased_left` 全 false）；程式：`ops/exhibit/twin/fortune_samples.py`；決議：`decisions/DECISION_20261002_TWIN_FORTUNE.md`。
- 模型 gemma-4-12b-it-qat 經 1003 的中繼 100.119.113.56:5500；沒碰 `~/vacant/`、.102、1003 服務；沒有任何觀眾資料送外部服務。
