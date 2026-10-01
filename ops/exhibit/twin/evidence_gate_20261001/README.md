# 根據閘門真跑覆蓋（2026-10-01，舊 VM 100.124.254.83，真 pi 0.8x＋gemma-4-12b-it-qat 經 100.119.113.56:5500）

- `batch1/`：g01–g30（30 跑，閘門第一版；中途修過窗 2 的檔名規則與窗 3／窗 4 的誤擋，所以 batch1 的 ✗ 裡
  有已修掉的誤擋，見裁決檔「誤擋清單」）。
- `batch2/`：h01–h12＋b7（縮短時限 12 秒）＋b8（`VACANT_TWIN_PI` 指到不存在的檔），閘門最終版（只差一條：
  窗 2 放過「讀過的數字加 1」的下一號，由 h04／h11 的誤擋回推，離線重算確認）。
- `rXX/`（batch3）：g02／g06／g08／h07 的重跑（旁註 attempt 編號修正後）。
- 每一跑：`<name>.json`（抽到的組、每一次嘗試的四格結果與訊息、每個 ✗ 的證據、秒數、分支）、
  `<name>.lifecycle.jsonl`＋`<name>.lifecycle.sidecar.jsonl`（原封不動，可餵 `serve_twin --live`／重播）。
- ⚠ batch1 的 g02／g06／g08 與 batch2 的 h07 的旁註 `twin_gate.attempt` 在存檔時被改正過一次：
  原本的編號是 `prepare` 被呼叫的次數，被牆鐘砍掉的那一次沒有 prepare 就讓後面的編號錯位
  （修在 `grounding_gate._learn_run`，回歸測試 `test_e2e_sidecar_attempt_numbers_…`）。改正規則：
  第 k 筆旁註＝第 k 個**沒被砍掉**的嘗試的編號。其餘欄位原樣。
- 合成特質（不是真人）；每一跑跑完就撤回（`erased_left=false`）。
