# Vacant repo — 工作約束（2026-07-04 起）

## 現在是什麼

本 repo 是 Vacant 的**程式碼本體**：信任層（Phase-1）＋ credit-memory 改動1/3 ＋
W1 實驗基建。規劃與理論的正典在
`~/Library/Mobile Documents/com~apple~CloudDocs/專題/`（尤其
`Vacant_最新成果彙整_2026-07-03/`）；**與規劃衝突時以 15 號判決文為準**
（其裁決凌駕 09–14）。

## 雙軌交付（15 §2，需教授簽字）

- **畢業軌（必要）**：修正版 demo ＋ X1 主臂＋1 消融（−稽核結論）＋ B 層機制
  驗收六情境 ＋ THEORY_V5 回灌＋網站改版。
- **投稿軌（時間允許）**：MPS ＝ X1＋X3 前緣曲線含 H2＋X4 m*/slash＋cost-Pareto；
  首選加 X2 去相關。E3 已砍；X5 凍結。

## 程式碼地圖（實驗承重件）

- `vacant/logbook.py` — 簽章 hash-chain；stream_id＝創世 hash、真 head()（改動1）
- `vacant/envelope.py` — Envelope＋**ReviewEnvelope**（改動3 的簽章 review）
- `vacant/registry.py` — record_review 只收驗簽＋head 新鮮＋去重；weight 內生；
  同源非線性降權 floor/k＋**行為推斷同源降權**（鑑別題一致率，零 controller_id）
- `vacant/reputation.py` — 五維 Beta；**改動2 三元組 key**(stream,branch,substrate)＋
  牙齒（decay 半衰期 200 事件向先驗回歸、slash 乘法扣減）
- `vacant/memory.py` — MemoryStream（episode 上鏈）＋MemoryManager M0/M1/M2
  （X1 的實驗處理本身）＋KS-1／A4 可執行防呆
- `vacant/auditor.py` — 確定性稽核（sha256 抽樣、checks.py 沙箱、provable-fault）
- `vacant/router.py` — trust on/off 單開關（on＝UCB、off＝確定性隨機）；
  probation 路由端牙齒（蓋 0.55＋每 10 筆見習配額）
- `vacant/batch.py` — RunLedger 斷點續跑＋Watchdog（裁決 B4）
- `vacant/x1.py` — X1 任務族＋run_x1 三臂迴圈＋transfer_curve＋pilot_report
  （一票否決）＋finalize_run_package（RECORD_SPEC 合格包）＋require_usage 成本紀律
- `vacant/codebench.py` — 六坑型族程序生成＋**EvalPlusMBPPLoader**（378 題
  sha256 釘死、V/GT 分離、fail-closed）
- `vacant/research.py` — M1–M6＋McNemar＋bootstrap＋**預註冊四函式**
  （holm_bonferroni／tost_equiv_boot／wilcoxon_signed_rank_exact／mcnemar_power）
- `vacant/record.py` — RECORD_SPEC pack/check（紀錄紅線：不 pack＝沒跑過；
  私鑰 identity.key 排除，SPEC §7）
- `vacant/blayer.py` — B 層機制驗收六情境（0→70% 步進 × on/off 雙組，判準寫死）
- `vacant/checkpoint.py` — V1 存檔點認證＋回溯稽核（18 §2；存檔點自身成鏈）
- `vacant/dashboard.py` — 觀測台＋/api/roster/scoreboard/**snapshot**（面板非信任來源）
- `examples/x1_pilot.py` — 遷移 pilot 進入點（--loader x1|builtin|evalplus、--stub 閘門）
- `examples/b_layer.py` — B 層六情境掃描 runner（預設每格 1000 seeds）
- `docs/PREREG_V2.md` — 預註冊凍結總表（草稿待人類簽字＋ledger 簽入）

## 鐵律（違反＝run 作廢）

1. **KS-1**：任何 prompt 模板禁止「你有責任／會被懲罰」類措辭；三臂模板逐字
   相同，唯一差異＝MemoryManager 注入的記憶區塊（`memory.assert_ks1_clean`
   是可執行防呆，不要繞過）。
2. **A4**：教訓只准坑型層級抽象、禁止逐字測資（`lesson_leaks_test_data`）。
3. **全 I/O JSONL 落盤**、retry×4、`infra_void` 規則（09 §3.5；06-30 稽核紀律）。
4. 記憶**不跨臂共享**、行為依賴歷史的部分禁用快取。
5. demo 只能說「看得到提升」；「證明提升」保留給預註冊 batch run。
6. wire-format：logbook 已 break（2026-07）；`~/.vacant-mcp` 等舊資料要清掉重鑄。

## 後推項（不要提前做）

~~改動2~~、~~牙齒~~、~~B 層六情境~~、~~V1 存檔點~~——**已於 2026-07-21 落地**
（feat/complete-vacant-p0-p1-p4 分支，經人類裁決提前 P4）。仍後推：
Thompson 路由、工具面 v2 再擴、V0 離線重放（掛 P7）、V2 +retro 臂
（條件：V0 正訊號＋B 層全過＋投稿軌）、X2/X3/X4 主跑、THEORY_V5 回灌＋
網站改版（P7/P8）。

## 已完成缺口（2026-07-21 對帳 19 號圖 G1–G12）

G1 EvalPlus loader ✓（整合門在本機 skip——官方包在 VM）· G7 統計四函式 ✓ ·
G8 舊 wire-format ✓（本機 tar 備份於 ~/vacant-mcp-backup-2026-07-21.tgz 後清掉）·
G9 死碼 ✓ · G10 硬編 IP ✓（VACANT_ENDPOINT 單一真相）· P0-3 /api/snapshot ✓ ·
T5 record 排私鑰 ✓ · G5 PREREG v2 草稿 ✓（**待人類簽字凍結**）。
未動（機時／人類事項）：P1-0 思考探針、X1 pilot 真跑（harness 已就緒）、
G12 行政（教授簽字、倫理遞件、AAMAS 死線、文獻直驗、機時裁決）。

## 慣例

- Python 3.11+；runtime 依賴只有 `cryptography`；測試 `.venv/bin/python -m pytest tests/ -q`。
- 模組 docstring 用中文寫「這支在架構裡承重什麼」，並引規劃文件編號（如 12 §4.3）。
- 誠實邊界句（raises-cost 非 prevents 等）是規格的一部分，改碼時保留。
