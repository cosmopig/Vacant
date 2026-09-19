# DECISION 2026-08-30（round356，Sonnet 5 + Opus 5 子代理）：撤銷 round296「400 不重試」——三個 post-fix run 的 void 率全部撞穿 SPEC 10% 閘門，根因是重試從沒真的執行過

## 觸發：先查到 void 率，再查到根因

本輪原本只是例行監看 `runs/g_r348_3arm_20260830`（PID 2256011，round348 啟動的
post-round347-fix 決定性 run）。獨立驗證發現一件過去 8 輪（round348-355）
monitoring 都沒查的事：**這個 run 的 void 率遠超 SPEC 自己的 10% 閘門**，
而且不是新現象——池化全部三個 post-fix run（round347 修完 contract-dedent
bug之後開的 `g_r342`／`g_r345`／`g_r348`）之後，**每一臂都是**：

```
OFF:  void=12 rows=27 total=39  void_rate=30.8%
OFF5: void=23 rows=15 total=38  void_rate=60.5%
ON:   void=21 rows=17 total=38  void_rate=55.3%
```

（單一 run 內逐臂：g_r348 目前 OFF 37.5%／ON 60.9%／OFF5 65.2%；
g_r342 總體 59.3%；g_r345 總體 11.1%——run 之間會大幅擺動，不是單調惡化。）

SPEC_GAIN §7、`ops/gain/analyze_fullbank_off.py` 的 `VOID_GATE = 0.10`、
`gain_run.py:806` 的註解，都寫死同一條規則：「void/(measured+void) > 10%
⇒ 整條臂作廢，不分類」。round342-355 對這幾個 run 做的所有分析
（`analyze_off5_gate_counterfactual.py`、`analyze_reviewer_family.py`）
一直把它們的輸出描述成「n 太小、只做管線驗證」，**但從沒有人指出這些資料
本來就已經被自己專案的閘門判定作廢**——五輪的「n 太小」措辭其實掩蓋了
一個更嚴重的事實。

## 根因：`brain_cline.py` 的 400 從沒真的被重試過

`ops/gain/brain_cline.py:201-205`（修改前）把 `{400, 401, 402, 403}` 全部
列為 `non_retryable`，遇到就 `break`，不進入重試迴圈。逐筆核對三個
post-fix run 的 `calls.jsonl`：

```
56 個 400 錯誤，其中 51 個在 attempt=1 就結束（5 個在 attempt=2，
  推測是 attempt=1 先撞到別的暫時性錯誤，attempt=2 才撞到 400）
InfraVoid 訊息「重試 N 次仍失敗」印的是 effective_retries（設定值），
  不是實際嘗試次數——訊息本身是誤導性的、從沒真的重試過。
```

**這不是內容導致的穩定拒答**：三個 run 合併，29 個曾經 400-void 的
distinct task_id 裡，**24 個在同一個 run 的另一臂成功過**
（g_r342: 8 個中 7 個、g_r345: 2 個中 2 個、g_r348: 19 個中 15 個）。
同一題换一個臂（等於换一次呼叫/candidate）就過，代表 400 是暫時性的
路由/後端雜訊，不是這題內容本身有問題。

`DECISION_20260829_R296_HTTP400_NONRETRY_REVIEW.md` 當時定的重啟條件
（原文）：

> 若之後有證據顯示同一個 (agent, task) 重試後会成功⋯那時應該把 400
> 移出 `non_retryable`（但只針對 review 角色/這個中轉端點，不要動
> 401/402/403）。若下一輪要重啟或重跑這個實驗⋯適合在重啟前一併做這個
> 修正並在新的 DECISION 文件記錄，屆時就不受「run 正在跑」這條理由約束。

**兩個條件都已滿足**：24/29 是「換一個上下文就成功」的等價證據；且既有的
三個 post-fix run 全部因 void 率已經作廢，重啟本來就無可避免。

**範圍比 round296 預期的更大**：round296 把現象限定在「review 角色」，
但這次逐角色拆開，400 分布在 `OFF5/gen`（23）、`OFF/gen`（12）、
`ON/gen`（12）、`ON/review`（8）、`ON/revise`（1）——**OFF5 臂完全不叫
review，它的 400 全部發生在 gen 角色**，round296 的「只針對 review」
前提本身不成立。改成不分角色移出。401/402/403（認證／額度類）維持
不重試，語意上不像暫時性路由問題（且這三碼在本輪抽樣裡完全沒出現過，
沒有反例）。

## 修改

`ops/gain/brain_cline.py`：`non_retryable` 集合從 `{400, 401, 402, 403}`
改成 `{401, 402, 403}`（見程式碼內註解，2026-08-30 round356）。

## 後續動作

1. `python3 -m py_compile ops/gain/brain_cline.py` 通過，語法無誤。
2. 三個 post-fix run（`g_r342`／`g_r345`／`g_r348`）的資料**不刪**（鐵律：
   不准刪任何 run 目錄），但**標記為 void-gate-disqualified，不得用來
   支持 CONCLUSION 的任何數字結論**——round353/355 已經用它們做過的
   OFF5-gate-counterfactual／reviewer-family 分析結果需要重新標註成
   「探索性、資料本身已作廢」而非「n 太小待補」。
3. 殺掉 PID 2256011（`g_r348`，全部作廢資料，此後不會再被引用），
   用修好的 `brain_cline.py` 重開一個新的 post-fix 決定性 run，
   **其餘參數與 g_r348 完全相同**（`--arms OFF,ON,OFF5 --n 179
   --seed g-r212-route-20260828 --models qwen/qwen3.6-35b-a3b,
   gemma-4-12b-it-qat --request-timeout-s 600 --retries 4
   --retry-backoff-s 2.0 --review-timeout-s 380 --review-retries 2`），
   只有重試邏輯這一個變量改變，避免混淆多個實驗條件變動。
4. `analyze_off5_gate_counterfactual.py`／同類離線分析腳本應該加一道
   **void-gate 斷言**（若任一臂 void_rate > 10% 就印警告甚至拒絕輸出
   結論性文字），不能再讓「n 太小」的措辭悄悄蓋過「資料已作廢」——
   本輪沒有動這支腳本（範圍留給下一輪，這裡先記下）。

## 這個決定會被什麼推翻

- 若修好之後的新 run 400 void 率沒有顯著下降（例如新 run 跑到 n≥30
  時 void 率仍 >30%），代表 400 真的有一部分是永久性錯誤被誤放行重試，
  應該重新評估是否要把它加回不重試清單，或改用更細的判斷（例如檢查
  response body 內容而不是只看狀態碼）。
- 若之後在別的端點/別的模型池觀察到 400 是內容穩定觸發（同一 request
  body 換節點也一樣 400），那條「暫時性」證據就被推翻，400 應該按情況
  改回不重試。

## 沒做的事

- 沒有動 401/402/403 的不重試判斷。
- 沒有修改 `analyze_off5_gate_counterfactual.py` 加 void-gate 斷言
  （留給下一輪）。
- 沒有重算 round353/355 已發布的數字本身（那些數字沒錯，只是描述
  「資料有效性」的措辭需要更正，見上面第 2 點）。
- 沒有刪除任何 run 目錄。
