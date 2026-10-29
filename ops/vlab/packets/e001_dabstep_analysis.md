# e001-dabstep 子集分析（主軸 4：資料分析任務）— 預註冊分析計畫（round 141，2026-10-29 寫下，結果出來前不可改）

> 對應 ASSIGNMENT 主軸 4（「這些問題有沒有實際的幫助」）與 e001 的 dabstep 26 題。
> 本計畫在 e001 的 dabstep 格完成**之前**寫下，目的是：結果出來時，解讀只走這裡寫的路，不事後挑數字。

## 1. 問題

在真實使用者環境（乾淨 HOME、pi 0.87.1、C 臂只多 `vacant install --agents pi`），
對**資料分析任務**（DABstep 前 26 題，依名稱排序），裝 Vacant 有沒有改變通過率？代價多少？
如果沒有差別，機制上的原因是什麼？

## 2. 資料與切片

- 來源：`/srv/vlab/runs/e001_pi_AC_baseline/dabstep-*-pi-{A,C}-r1/`（26 對，同題配對）。
- 分數：`score.json` 的 pass/fail（root 側 scorer，隱藏測試；不讀 `/srv/eval`）。
- 代價：`cell.json` 的 wall time、`metrics.json` 的 token；C 臂另取 `vacant_home_bytes`（主軸 2）。
- 重驗：`python3 /srv/vlab/bin/report.py e001_pi_AC_baseline --rescore` 的 REPORT.json
  （dabstep 子集＝從 REPORT.json 的 per-task 行裡篩 `suite=="dabstep"`；若 report.py 沒有
  per-task 行，就從各格 `score.json` 直接彙整，並記在結論裡）。

## 3. 主要結果（只有一個）

**配對 A/C 的 discordant pair 數與方向**（A 對 C 錯＝a，C 對 A 錯＝c），附 McNemar exact p
（双侧）。26 對的檢定力有限（a=c=1 → p=1.0；a=2,c=0 → p=0.5），所以**主要讀法是描述性的**：
幾個 pair 分出勝負、朝哪邊、各 cell 的 wall time 與 token 差多少。不報「顯著/不顯著」之外的任何強結論。

## 4. 機制診斷（回答「為什麼有/沒有差別」）

對每一格 C 臂，從 `vacant_home.tgz` 的 `.vacant/intake/hooks/events.jsonl` 與
`.vacant/trace/projects/*/` 讀：

1. `zero_ran`：zerostop 有沒有真的跑（False → 這格的 C 臂等於 A 臂，代價只剩 trace 記錄）。
2. findings 清單（kind+sub）與 `action=continue` 的次數與 `sent`（退回給 agent 的發現）。
3. 交件說明（`delivery.json`/`delivery.md`）裡的 advisory findings（`unsourced`、
   `copy_of_inline` 等只寫給人的那批）。
4. A 臂同題對照：有沒有寫出要求的檔、有沒有空檔、有沒有沒讀點名檔（用同一份 evidence 邏輯
   離線重播 `tests/test_noncode_samples.py` 的樣式，不對模型做任何假設）。

## 5. 解讀框架（結果出來時照這個讀，不事後找）

機制事實（round 141 盤點，`docs/UNIVERSAL_TASKS.md` + `trace/zerostop.py:pushable_for`）：

- **Vacant 不判「答案內容對不對」**（UNIVERSAL_TASKS.md §2.3）：對資料分析任務，
  隱藏 scorer 才是裁判；Vacant 的檢查只看紀錄（缺檔、空檔、數值無來源、點名檔沒讀、指令失敗）。
- **可退回（會多跑一回合）的發現**：`missing_output`、`invalid_output/empty`、
  `unsourced`（寫入的數值/日期不在讀過/跑過的語料裡）、`unread`（≤1 回合）、
  `failed_step/test_failed`（≤1 回合）。其餘（`copy_of_task`、`skeleton`、`stale_output`、
  `copy_of_input`、`copy_of_inline`、`claimed_run`、`unfetched`、`claimed_write`）**只進交件說明，不退回**。
- dabstep 任務**沒有可見測試檔**的話（第一格 C 完成時用 `app_final.tgz` 內容確認；目前 UNKNOWN），
  `test_claim`/`failed_step` 實質休眠，C 臂的活躍介入只剩 §5 前兩行那種「缺/空/無來源/沒讀」。

因此：

| 觀察 | 唯一合理的解讀 |
|---|---|
| C ≈ A（discordant 對很少或兩邊各一兩對） | 模型大多用真實資料算數（`unsourced` 罕發），Vacant 的檢查全過、沒介入 ⇒ **在「內容正確」維度上，這個機制本來就不管，沒有幫助是預期的**（H-2 同構）。記為「無可測影響」，不是「失效」。 |
| C > A（c>a） | 只有一種解釋成立：模型原本 L-fake（編造數值/漏寫檔/沒讀輸入），`unsourced`/`missing_output` 退回後真的改對。必須逐 pair 對 §4 的 findings 記錄核實，否則不算。 |
| C < A（a>c） | 可能原因（依 §4 逐格核實）：(a) 退回吃掉回合/時限（對照 wall time 與 timeout）；(b) 被退回後模型改錯（對照該格最後交付）；(c) `unsourced` 誤報（模型用合理推導的數值但語料裡沒有）——若是 (c)，這是**檢查的誤報**，要回 `tests/test_noncode_samples.py` 補樣本，不是調 e001。 |

## 6. 不做的事

- 不把 dabstep 26 對跟 polyglot 34 對合併池化報一個 n。
- 不引用 `/srv/eval` 的隱藏測試內容來解釋任何一格。
- 不因為某一格 C 的 `vacant_home_bytes` 特別大就下主軸 2 的結論（那是另一條軸、另一份包）。
- 不報「證明有/沒有幫助」：報「在這個設定、這個模型、26 題、1 rep 下看到／沒看到差別」＋代價。

## 7. 觸發的下一步（只有這三條，先寫下）

1. 若 C < A 且核實是 `unsourced` 誤報 → BACKLOG P0：誤報樣本進 `test_noncode_samples.py`，修到零誤報再談 e003。
2. 若 C > A 且核實是 L-fake 被退回後改對 → e003：dabstep 全 79 題 ×2 rep、只比 A/C、加「L-fake 率」指標（`unsourced` 命中數/總數），預註冊後才發射。
3. 若 C ≈ A → 主軸 4 記「無可測影響（機制不判內容正確性）」，e003 不做，資源轉主軸 2（`~/.vacant` 成長）。

---

## 8. 實際結果與解讀（round 171，2026-10-29，依 §5 解讀框架填寫；§1–7 預註冊內容不改動）

**官方數據＝repo 已 commit 的 26 對版**（`ops/vlab/runs_e001_pi_AC_baseline/`，argon
`4f85e1d6` 刷新後）。⚠ `/srv/vlab/runs/e001_pi_AC_baseline/` 下的同名檔是 dabstep-2697
完成**之前**的舊 25 對快照（sha256 不同），**不可引用**；本包與 FINDINGS.md 一律引 repo 版。

- **A 13/26（50.0%）、C 14/26（53.8%）**；A_only＝0、C_only＝1（dabstep-24）、
  McNemar exact p（雙側）＝1.0；incomplete＝0。
- **成本**（描述性，n＝26、1 rep）：A 呼叫/成功 108.62、token/成功 3,057,129、均牆 228.5s、
  逾時 1；C 呼叫/成功 64.93、token/成功 1,645,720、均牆 169.6s、逾時 1；
  C 臂 `vacant_home_bytes` 總計 18,531,396 B（≈713 KB/格）。
- 來源 sha256：`REPORT_dabstep_subset.json` 83cebaf8…cd67d、
  `AUDIT_dabstep_mechanism.json` 79c0e7b4…caaddfe、`REPORT_dabstep_subset.md` dbcc0c85…e542dfdc4a。

**§5 要求的 discordant pair 逐格核實（dabstep-24）——已完成**：
- A 格：`score.json` `answer_exists=false`、app_final **零檔案**——agent rc=0 正常結束但
  從頭到尾沒寫 answer 檔（正是 L-fake 形狀：missing output）。
- C 格：`zero_ran=true, n_rounds=0, findings=[], final_action=allow`——**機制零介入**。
- ⇒ 依 §5「C > A 必須逐 pair 核實 L-fake 被退回後改對，**否則不算**」：這 1 對
  **不歸因機制**，是跨 run 隨機差（A 臂 agent 沒寫檔、C 臂 agent 寫了）。

**機制事實（描述，不判內容對錯；源＝AUDIT_dabstep_mechanism.json）**：
- 26 C 格 25 格 `zero_ran=true`；9 格觸發 `missing_output` kickback（另 2 格
  `invalid_output/contract_shape`），全部 `final_action=allow`（被退回後 agent 補了檔）。
- 該 9 格對隱藏 scorer：**1 過（dabstep-22）／8 掛**（10、17、19、23、1464、1681、1753、2697）
  ——gate 保住了「檔寫出來」，保不住「內容對」；dabstep-2697 被退回 2 回仍掛。
- **§5 的 UNKNOWN 已結**：26 格 C 臂 app_final.tgz **全部無可見測試檔**（只有 answer.txt
  ＋分析腳本）⇒ `test_claim`/`failed_step` 在該題庫確為休眠，與 §5 預測一致。

**結論（§7 分支 3；分支 2 前提不成立）**：
在此設定（gemma-4-12b-it-qat、pi、26 題、1 rep）對資料分析題，**看不到可歸因機制的
影響**；唯一 C 優勢格機制零介入。機制在「內容正確」維度本來就不管（H-2 同構），
沒有幫助是預期的——記為「無可測影響」，不是「失效」。「L-fake 被退回後改對」的
假說（分支 2）在本批**未被支持**：**e003（dabstep 全 79 題×2 rep）不發射**；
資源轉主軸 2（§7-3）。能說／不能說的句子見 repo `ops/vlab/FINDINGS.md`。
