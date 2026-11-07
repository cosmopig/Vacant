# NOW — R-loop (auto/qwen27b)

## 第 1153 輪 (2026-11-07)
**工單 P20261107_0041-2：真實 CSV 切片端到端管線測試（保留/拒收/exit 碼）→ commit 247309e4**

- test_reqloop_real_slice.py 新增 test_real_slice_smoke_preservation_and_exit_codes：假代理 run_g2_smoke 實跑 dab_378 4 格（0 模型呼叫）——C×generic 正確修復 kurtosis⇒gap_closed/exit 0/8 鍵 preserved；C×localized 竄改 pre_mean⇒satisfied_mutated 精確偵測、exit 20 拒收；A 正確草稿兩臂 exit 0、right_to_wrong=0。
- g2.py CLI 人讀輸出補 SATISFIED_PRESERVED 行（與 SATISFIED_MUTATED 同格式）。
- 驗收：5 檔 checks/g2/repair/real_slice/g1_gate＝**223 passed**（222 既有＋1 新增、無回歸）。
- 紅線：0 模型呼叫、0 發射、0 元；未動 main、未自 push（loop 自動推）、未讀 hidden/scorer、未加 regex/靜態 prompt/重試、未動凍結 manifest/快照。
- 沒驗證：真實模型行為（本票為離線管線測試、無新效果數字）。

## 待辦
- [ ] vq-6rp（dabstep-1753 模型側硬缺口）／vq-5nz.6（停滯草稿換方法）仍候需求端點名。
- [ ] 是否擴量＝新決策、需另行授權（11-06#4「證明可修回後再擴量」）。
