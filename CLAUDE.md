# Vacant repo — 工作約束（2026-07-04 起；交付定位 2026-08-06 更正）

## 現在是什麼

本 repo 是 Vacant 的**程式碼本體**：可究責層（Phase-1）＋ credit-memory 改動1/3 ＋
實驗基建。規劃與理論的正典在
`~/Library/Mobile Documents/com~apple~CloudDocs/專題/`（尤其
`Vacant_最新成果彙整_2026-07-03/` 與 `Vacant_展望_2026-08-06/`）；
**與規劃衝突時以 15 號判決文為準**（其裁決凌駕 09–14），
**唯獨交付定位以下面這一節為準**。

## 唯一交付物：畢業專題 ＝ 實體場地展覽

**不產出畢業論文，也不投稿。**（2026-08-06 人類明確更正）

舊版這裡寫的是「雙軌交付：畢業軌／投稿軌（MPS、AAMAS、X2–X5 主跑）」。那個描述
已經不成立，而且它會主動製造發散——照著它規劃，工作會一路長向「論文貢獻」
「有沒有被先行研究搶先」「統計顯著性」。2026-08-06 就這樣把工作誤拆成畢業／投稿／
展覽三個身分，被當場糾正。**判斷任何工作要不要做，問的是「觀眾走到展場前面時，
這件事有沒有差別」，不是「審稿人會不會問」。**

具體後果，每一條都會改變技術決策：

1. **實體場地 ⇒ 秒級互動是硬需求。** 真模型每題實測約 114 秒（E10），現場不可能等。
   展件跑機制模擬（`entrycost`）或預跑重放，**畫面上必須明講「這是機制模擬」**——
   把模擬講成證明是鐵律 5 的展場版本。
2. **實體場地 ⇒ 離線可跑、可無人值守循環。** 不能假設網路、不能假設有解說員。
   任何依賴外部端點的東西都要有 fallback。
3. **先行研究仍然重要，但理由變了。** 不是新穎性，是**不能對觀眾說錯話**。
   展場說「我們發現脈衝攻擊」而它 2005 年就有名字（Srivatsa），那是騙不懂的人。
4. **統計檢定力不必到發表標準。** E10 的 p=0.332 對展覽不是問題；能讓外行一眼看懂
   的反事實對照比 p 值重要。
5. **口徑用「可究責性 / 讓依賴有根據」，不要用「信任」。** 經典定義（Gambetta 1988、
   Mayer 1995）把「不依賴監督」寫進信任的必要條件，而監督正是本系統的全部。
   觀眾比口委更容易被誤導，所以展場的措辭要求**更嚴格**不是更寬鬆。
6. **倫理是第一線需求不是附錄。** 展覽用真人資料生成分身。Hollanek 2024：
   **捐贈者同意不夠，互動者也必須能同意**——動物園的性質就是有人在旁邊看。
   詳見 `專題/Vacant_展望_2026-08-06/03_人類動物園_展覽設計.md` 第五節。

展件施工順序與凍結清單見 `專題/Vacant_展望_2026-08-06/04_接下來的步驟.md`。
**凍結不等於刪掉**：通道分離那六個改動、X-cap／X-check 等證據都很強，但它們不影響
展場，排在展件可運作之後。

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
- `ops/gain/gain_run.py`＋`ops/gain/brain_cline.py` — G 實驗（SPEC_GAIN.md，
  2026-08-17 定調為主張本身）三臂等預算 runner 與 Cline 後端；
  OFF5 多數決走與 ON 相同的受限 worker（2026-08-20 修正）。
  `ops/gain/VERIFICATION_2026-08-20.md`＝外部交付包 22db0d7 的獨立驗證紀錄，
  含「敘述超出實際交付」清單（deadline quorum、五呼叫重配、corpus 13/4/9
  都不在交付物內，引用時不可當成已存在）

### 展件可直接複用的（實體場地，秒級互動）

- `vacant/entrycost.py` — 機制模擬。**現場的雙世界對照跑這個**，不跑真模型
  （真模型每題約 114 秒，展場等不起）。畫面上必須標明是機制模擬。
- `vacant/logbook.py` ＋ `vacant/checkpoint.py` — 出口那張「可驗證收據」的機制；
  同一套也用來做展覽自己的同意／刪除證明（用自己展示的機制證明自己守約）。
- `真模型_2026-07-26/E10/{on,off}/rows.jsonl` — 主視覺的資料來源。兩行路由序列
  （`X`＝工作被交給破壞者）是手上最容易被外行看懂的東西，且是真模型真資料：
  ```
  關  ......X.....X.XXX.X.X..X....X.X.X.X..XXX..X....XX....X..X...
  開  ....XX....XX......XX..X.....X.....X...X..X..................
  ```
- `examples/e10_mediator.py` — 重算上面那兩行（零機時，只讀已歸檔 JSONL）。

### 對外發布與存證

- `examples/publish_now.py` — 產出 `now.html` 的三類資料（現有知識／走過的路／
  還沒走的路）。**未來方向那組刻意沒有 result 欄位**，`future_run` 寫死 0——
  沒跑就是沒跑，資料結構不該給「填上結果」留一個看起來很自然的空格。
- `examples/publish_archive.py`、`examples/build_archive_index.py`、
  `examples/verdicts.py` — 檔案庫資料與機器可讀索引；裁決的**單一真相來源**在
  `verdicts.py`，兩支腳本共讀，否則索引會比網頁樂觀。
- `examples/archive_citations.py` — 引用備份。**用過、引用過的東西都要有落盤證據**
  （A 全文／B 僅摘要／人工核對引文三級，含 sha256）。拿不到也要記下拿不到。

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
Thompson 路由、工具面 v2 再擴、V0 離線重放、X2/X3/X4 主跑、THEORY_V5 回灌。

**2026-08-06 加上的凍結項**（證據都很強，但不影響展場，排在展件可運作之後）：
通道分離六改（commit-reveal 評審、專長 profile、拒絕原語＋calibration 維、
面板拓撲控制、Delphi 第二輪、評審期間不揭露信譽）、X-attr 跨基質遷移、
X-cap 能力階梯、X-check 可查證度分層、`slash` 改成只動均值不動 n
（會改變牙齒形狀 ⇒ 要重跑 B 層六情境，現在動不划算）。
理由與最小可行試驗設計寫在 `專題/Vacant_展望_2026-08-06/04_接下來的步驟.md`。

## 已完成缺口（2026-07-21 對帳 19 號圖 G1–G12）

G1 EvalPlus loader ✓（整合門在本機 skip——官方包在 VM）· G7 統計四函式 ✓ ·
G8 舊 wire-format ✓（本機 tar 備份於 ~/vacant-mcp-backup-2026-07-21.tgz 後清掉）·
G9 死碼 ✓ · G10 硬編 IP ✓（VACANT_ENDPOINT 單一真相）· P0-3 /api/snapshot ✓ ·
T5 record 排私鑰 ✓ · G5 PREREG v2 草稿 ✓（**待人類簽字凍結**）。
未動（機時／人類事項）：P1-0 思考探針、X1 pilot 真跑（harness 已就緒；
展覽不強制需要它，v1 不排）、G12 行政（教授簽字、倫理遞件、機時裁決）。
~~AAMAS 死線~~、~~文獻直驗~~ 已不適用：不投稿；文獻已於 2026-08-06 直驗
（236 筆進 `參考文獻/_引用備份/MANIFEST.json`，全文 197、僅摘要 39）。

## 慣例

- Python 3.11+；runtime 依賴只有 `cryptography`；測試 `.venv/bin/python -m pytest tests/ -q`。
- 模組 docstring 用中文寫「這支在架構裡承重什麼」，並引規劃文件編號（如 12 §4.3）。
- 誠實邊界句（raises-cost 非 prevents 等）是規格的一部分，改碼時保留。
