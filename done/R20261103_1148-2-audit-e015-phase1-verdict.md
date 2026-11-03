# 工單 R20261103_1148-2：獨立複核 e015 Phase 1 裁決數字與 32 件 artifact 證據鏈

## 背景與目標
實驗 `e015_h_multi_review`（Phase 1 裁決者校準）已完賽。
請獨立複核其裁決計算邏輯與結果落盤數據，確保與預註冊標準逐筆一致。

## 執行步驟
1. 執行官方裁決管線自檢：
   `python3 ~/dev/ops/audits/e015_verdict_pipeline.py --selftest`
   確認 12 項 selftest 全部 exit 0。
2. 檢查產物 `/srv/vlab/runs/e015_h_multi_review/VERDICT.json` 與 `audits/e015_h_multi_review.md`：
   - 核實 BAD 側（16 件）之 REJECT 數 X 是否為 15/16（P(≥15)=0.0003，顯著）。
   - 核實 GOOD 側（16 件中 15 件有效）之 ACCEPT 數 Y 是否為 7/15（P(≥7)=0.696，未達）。
   - 核實缺證據格數為 1/32（`dabench-dab_057-pi-A-r1`，UNPARSED），未超過門檻（>6 格）。
   - 核實狀態表裁決為 `NOT_BETTER_THAN_RANDOM`，且 Phase 2 不發射。
3. 驗收判準：
   - 裁決管線自檢 exit 0。
   - 逐筆確認 32 件 artifact 裁決與預註冊狀態表相符。
4. 完成後將工單移至 `~/dev/ops/tickets/done/` 並註明複核結論。
