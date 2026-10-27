# 設計（未實作）：用「交件時重跑可見驗收」當真實訊號，驅動重抽／回饋（2026-10-25）

> 一頁設計＋擋門條件。照第 41 輪交接 (b)：**先寫設計、不實作**。
> 這是「候選 2 失敗之後、換的那一種訊號」（`DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §二／§七／§九），
> 與「候選 3」共用同一条邊界：**不預設、只能人明確選**。

## 0. 為什麼是這一種訊號（候選 2 的教訓）

候選 2 是**擴充現有的零設定證據檢查**（`trace/evidence.py` 的 `test_claim`／`failed_step`，
交件時測試在 `tests/test_zero_evidence.py`）：把「最後一次自己跑的測試失敗（或從沒跑）卻說做完」
變成退回訊號。擋門結果（`DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §七）：**沒有通過，不實作**。
- 離線重播（R530 SOLO）：可靠的失敗 7 格**全部「只寫給人」**（3 格之後改過檔、4 格最後訊息「提到失敗」）
  ⇒ 退回 0、**recall 0/39**。
- 程式題組（10 題）：說做完的 5 跑**最後一次測試都通過、都對**；候選 2 的目標（最後失敗卻說做完）**0/10**——
  這個模型說做完的那一刻**沒有到「測試失敗卻說做完」**，失敗全在之前（回合上限、輸出長度上限、卡住）。
- 兩個原因：這訊號在真實紀錄裡**很少以可靠形式出現**、出現時又幾乎伴隨 agent 自己的解釋或之後的修改；
  「有沒有揭露（提到失敗）」的判斷也不可靠（4 格「提到失敗」裡 3 格只是 agent 描述合約會丟 `ValueError`）。

所以：**「claim 與證據不合」的檢查（說測過有沒有真的跑、錯誤有沒有被忽略）產品已實作、已測**
（零設定證據檢查 → 交件說明／退回）。要拿**可靠訊號驅動重抽**，只能換一種訊號（決策文件原話）：
**Vacant 在交件時自己重跑那個指令**——不是讀 agent 說了什麼，而是再執行一次拿真實過／不過，
因此候選 2 那兩類錯（漏掉＋誤判）不會出現。

## 1. 這套機制其實已經存在、且已測（opt-in）

`vacant run --suite <dir> -- <agent 指令>`（`vacant_network/vrun/launcher.py`）就是這個設計：

- 觸發點＝**agent 行程結束**（不是線上的「done」訊息）；
- 在**凍結快照**上跑 `acceptance.run_suite(suite="visible")`（`launcher.py:605`）；
- 過 ⇒ `visible_pass`、`accepted=true`；不過 ⇒ `visible_fail`，把**可見驗收的失敗原文**
  （`acceptance.render_failures`）寫進 `VACANT_FEEDBACK.md`，交還給重抽臂
  （`retry.py`：`RETRY_ARMS=("none","resample","revise","fresh_hint")`）；
- 沒給 `--suite` 又沒 `--allow-no-suite` ⇒ **fail-closed**（`no_suite`）——量不到不是通過。

測試：`tests/test_vacant_run.py`、`tests/test_vacant_run_retry.py`（含 fail-open、KS-1、V/GT canary）。
⇒ 本文件**不是新發明**，是把它**命名、定位、並訂出何時可以擴成預設**的擋門條件。

## 2. 這是「真實訊號」，不是「評分器」（兩件事必須分開）

- **真實訊號（產品用的）**＝題目自帶的**可見驗收測試**，由 Vacant 自己重跑。
  它是任務的一部分、放在工作區，量的是「交回來的東西過不過題目自己的檢查」。
- **評分器／oracle（上限，不是產品效果）**＝隱藏 grader。
  離線重播（`~/dev/ops/ref/offline_restart_sim.py`）把兩者分欄：`flag-restart`（真實訊號）
  對 `test-restart`／`oracle@k`（用到隱藏結果＝上限）。**引用成效時只准引用真實訊號那一欄。**

## 3. 量過的數字（本輪重跑核對，離線、零 LLM、cap=3、n=331 個「批次×題」單位、每單位 ≥2 次獨立跑）

| 欄位 | 全體 | polyglot_py（可見測試＝評分器的題組） |
|---|---|---|
| pass@1（只抽一次） | 62.3% | 37.3% |
| **flag-restart（真實訊號驅動重抽）** | **66.4%（+4.1pp）**、1.17 次/題 | **47.0%（+9.7pp）**、1.49 次/題 |
| test-restart（用到隱藏結果＝**上限**） | 77.7%、1.56 次/題 | 55.9% |
| oracle@k（上限） | 78.2% | 55.9% |

- 可引用的成效＝**真實訊號那欄**：全體 +4.1pp、polyglot_py +9.7pp（分母 331 / 68 個單位、每單位 ≥2 跑、cap=3）。
- **不准**把 `test-restart`／`oracle@k`（+15 個百分點級）當產品效果引用——那是用到隱藏結果的上限。
- 前提（H-1）：**只在「有可執行驗收」的任務上成立**。DABstep 沒有可執行訊號（714 跑 0 跑跑過測試），
  同一套機制在那上面拿不到這個增益——那是量出來的，不是猜的。

## 4. 邊界（照實講，不美化）

- **opt-in、不是預設**：要傳 `--suite` 才啟用；維持「零必填設定」鐵律。
  要「自動偵測該跑哪組測試」＝新增行為，必須先過下面第 5 節的擋門。
- **generation 側**：交件時由 Vacant **執行程式**（沙箱內）。沙箱是**應用層加固、不是 OS 安全邊界**（H-6）；
  不可信程式應放容器／gVisor／獨立 VM。
- **H-2：過可見 ≠ 符合隱藏需求**。可見測試擋得住「全收」，不保證「覆蓋到真需求」。
  這套機制驅動的是**重抽／回饋**，不是對隱藏需求的**最終裁定**。
- **H-1：量不到 ≠ 通過**。沒有可執行驗收的任務上，這套機制不作用（不是失敗，是「沒有訊號」）。

## 5. 擋門條件（滿足才准把它擴成預設／自動偵測；逐條可驗證）

1. **訊號來源＝真實訊號**：觸發重抽的判據是「可見驗收重跑結果」，**不是**靠 agent 自我報告
   （說沒說測過、有沒有提到失敗）。（反例＝候選 2，recall 0/39、程式題 0/10，已擋門；
   守它的是 V/GT canary 測試：隱藏測資一律不進 `VACANT_FEEDBACK.md`。）
2. **成效可複算、分母齊全**：在程式題組（`polyglot_py`／`lcb_visible`）上，真實訊號驅動重抽
   要**贏過 pass@1**，且報出**分母＋欄位＋n**（本輪已核：331 單位、cap=3、+4.1pp / +9.7pp）。
3. **不增加誤退**：對「本來就對」的交件，重抽**不得**把它翻成錯的、也不得白燒預算。
   要單獨量「對的被重抽且翻錯」的次數，並小於它救回的「錯的被重抽且轉對」。
   **已量（2026-10-29，離線重播、零 LLM；cap=3、n=331 單位、每單位 ≥2 次獨立跑；
   `python3 ~/dev/ops/ref/gate3_breakdown.py ~/dev/ops/ref/c37_final.json 3`，
   輸出自檢與 `offline_restart_sim` 的 flag-restart／test-restart 欄位逐位一致）**：
   - flag-restart（真實訊號）：翻錯 **0**（各題組逐單位平均皆 0.000）＜ 救回
     逐單位平均 **0.040**（polyglot_py 0.097；trial 基數 49/1179）；對「本來就對」的起始
     **零**多餘重跑（白燒＝0）。**在本檔庫上本條門成立。**
   - test-restart（上限欄）：翻錯 0（**結構性**：對的交件不會被重抽）＜ 救回 0.153（polyglot_py 0.186）。
   - **未驗證殘留＝UNKNOWN，不是 PASS**：此檔庫 1187 跑裡 flagged∩對＝**0**（135 個被標記跑
     全錯：cell 級 precision 135/135、recall 135/423），「對的交件被標記→重抽→可能翻錯」
     這條路徑**沒被觀察到**。反事實界（重抽≈新抽一次的近似下）：對一個單位的一次誤標記，
     重抽落錯的機率≈該單位的錯誤率 1−pass@1（ALL 37.7%、polyglot_py 62.7%）——在難題組上
     一次誤標記的損失大於一次真標記的收益（0.373），**這條路徑要靠含「對的交件被標記」的
     live 資料閉合，不能拿本檔庫當 PASS**。
   - 池子口徑：重抽池是同 cell 的歷史獨立跑（同條件），不是新跑——量的是政策在檔庫上的行為，
     不是 live 分布。
4. **零必填設定**：若要做「自動偵測該跑哪組測試」，必須**不需要**新增必填設定／安裝步驟；
   偵測失敗時 **fail-open**（回到「沒有訊號、不裁定」），不得 fail-closed 卡住客戶。
5. **沙箱不越界**：重跑在沙箱內（H-6）；不開放網路、不讀工作區外、不可信程式進容器。
6. **不碰隱藏 grader**：全鏈路只用可見驗收；`test-restart`／`oracle@k` 只能作為**上限**出现在分析，
   不准出现在「產品效果」的敘述。

## 6. 不做（避免重走候選 2）

- 不靠 agent 自我報告（說沒說測過、有沒有提到失敗）來觸發退回／重抽（候選 2，recall 0/39、程式題 0/10，已擋門）——
  「claim 與證據不合」那類檢查已由交件時證據檢查實作（`tests/test_zero_evidence.py`）；重抽要的是重跑的真實過／不過。
- 不把 oracle／評分器的 +15pp 級數字當成效引用。
- 不在「沒有可執行驗收」的任務上聲稱這套機制有作用（H-1）。
- 不把它設成預設、或加必填設定，直到第 5 節六條都過。

## 7. 證據／重現

- 離線重播：`python3 ~/dev/ops/ref/offline_restart_sim.py ~/dev/ops/ref/c37_final.json 3`（零 LLM）。
- 擋門 3 分解（翻錯／救回／白燒，帶與上者一致的自檢）：
  `python3 ~/dev/ops/ref/gate3_breakdown.py ~/dev/ops/ref/c37_final.json 3`（零 LLM）。
- 機制代碼：`vacant_network/vrun/{launcher.py, retry.py, acceptance.py}`；
  測試：`tests/test_vacant_run.py`、`tests/test_vacant_run_retry.py`。
- 候選 2（擴充零設定證據檢查）擋門與「換一種訊號」的由來：`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §二／§七／§九。
- 零設定證據檢查（`test_claim`／`failed_step`，候選 2 所擴充者）的交件時測試：`tests/test_zero_evidence.py`。

## AMEND1（round 111，2026-10-27）— 移除與本決策矛盾的「第二把尺」

- round 23（`b4db1dfd`）曾另寫 `ops/eval/c37_offline_restart_sim.py`（及其 test）：flag-restart 列改為
  「前 cap 格任一 findings 為空即成功」（不看該跑是否過）＝同檔庫算出 97.1%（對本檔 66.4%，差 30pp）；
  且把 cell 的 C37/C37R 實驗系列當「suite」，使「可見測試＝評分器」守則（polyglot_py）永不命中；其
  docstring 自稱「唯一正典版」、稱本檔指定的 ref 工具「只是 shim」，均與事實相反。round 111 判定本檔
  （ref 工具 `~/dev/ops/ref/offline_restart_sim.py` ＋ repo 副本 `ops/realrun/offline_real_signal_replay.py`）
  為準，**刪除該第二實現與其 test**（repo commit，git 可還原）；本檔數字與引用口徑不變。
  若日後重現該類工具，先與本檔 §3 數字逐欄對齊，否則不得標「可引用」。
