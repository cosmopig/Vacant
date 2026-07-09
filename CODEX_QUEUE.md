# Codex 任務佇列（狀態由 Codex 勾；文字由 Claude/人類維護）

> 作業手冊（必讀，含每張卡的完整驗收判準與禁區）：
> `~/Library/Mobile Documents/com~apple~CloudDocs/專題/Vacant_最新成果彙整_2026-07-03/20_Codex全天值守手冊_2026-07-09.md`
> 規則：由上而下領第一個 `[ ]`；兩次嘗試卡住→標 `[B]` 寫日誌跳下一個；完成→`[x]`＋分支名。

## Wave 1 — P0 收尾（本機、零模型呼叫）
- [ ] **T1** research.py 補四統計函式（holm/tost_boot/wilcoxon_exact/mcnemar_power；各≥3 手算對照測試；零 scipy）
- [ ] **T2** dashboard `GET /api/snapshot`（roster/scoreboard/ts_ms/ledger_seq/ledger_head_hash；≥3 測試）
- [ ] **T3** 清死碼（src/、alembic/、四個空測試目錄）＋ examples IP 改 VACANT_ENDPOINT
- [ ] **T4** 07-05 實錄 README 降級改寫（【單例演示】；grep 證明|proven|顯著 零命中）
- [ ] **T5** record pack 排除私鑰 identity.key（SPEC 補節；≥2 測試）

## Wave 2 — 資料層
- [ ] **T6** EvalPlusMBPPLoader 真資料（378 題 sha256 釘死；V/GT 分離；金標 50/50；≥5 測試）

## Wave 3 — 機時層（VM 100.77.224.99；每個 run 過 `vacant record check`）
- [ ] **T7** P1-0 思考模式探針（40 呼叫配對；延遲分布＋正確率帶分母；只寫觀測）
- [ ] **T8** X1 pilot 乾跑（oracle-lesson 50 題；KS-1/A4 斷言落盤；只交數據不做判定）｜前置：T6

## 佇列耗盡 → 手冊 §4「巡檢模式」，禁止自創任務
