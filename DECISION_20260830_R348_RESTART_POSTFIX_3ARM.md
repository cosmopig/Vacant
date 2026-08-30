# round348：殺掉 pre-fix 的決定性 run，重開 post-fix 版本——prereg

## 為什麼（承接 round347 留的判斷題）

round347 修好 `vacant/codebench.py` 的 contract dedent bug（commit `057cc01`）。
這個 bug 讓 `verify_review_counterexample` 對 378 題裡 292 題（77.2%，contract
有 ≥2 條 assert）**保證**回傳 `(False, "outside_input_contract")`，跟 reviewer
舉的反例引數值完全無關（純粹是 `.strip()` 沒有先 `textwrap.dedent()`，多行
contract 拼進頂層程式碼時 `unexpected indent` SyntaxError）。這個布林值直接
餵進 `grounded_pass = raw_pass or not confirmed`（`gain_run.py:490`）——
bug 觸發時 `confirmed=False` 保證讓這一票變成「同意通過」，等於**ON 臂的
審核→修訂自我修正機制對 77.2% 的題目從一開始就被打了折扣**。完整重現與
反事實重算見 `DECISION_20260830_R347_CONTRACT_DEDENT_BUG.md`。

round347 明確把「要不要為此重開決定性 3-arm run」列為判斷題、留給下一輪
（本輪），理由是這是貨真價實的實驗條件改變，需要另開一輪寫 prereg。

## 決定：殺掉 g_r345_3arm_20260830（PID 2248124），重開 post-fix 版本

**判斷根據（不是量出來的，是取捨）**：

1. **這個 run 從頭到尾都在跑壞掉的邏輯。** `codebench.py` 在 Python 匯入時
   讀進行程記憶體，round347 修改磁碟上的檔案不會影響已經在跑的行程
   （round347 自己記錄過這點）。PID 2248124 是 round345 啟動的，早於
   round347 的修復（round347 的 commit 時間晚於這個 PID 的啟動時間）——
   **這個 run 全程只可能是 pre-fix 資料**，沒有任何一筆是 post-fix 的。
2. **沉沒成本極低**：殺掉前用
   `python3 -c "..."` 逐列數 `rows.jsonl`：`OFF=5, ON=6, OFF5=5`，
   合計 16/537（179×3）＝**2.98%**，`etimes`＝4315s（71.9 分鐘）只換到
   16 列——這個量級（round344/346/347 都記過的長尾）代表就算不殺、
   要跑完全部 537 列也是數十小時級，而且從頭到尾量的是被打折扣的機制。
   殺掉重開的機會成本遠小於「跑完一個已知在測壞掉的東西的 run」。
3. **不殺，等它跑完，得到的答案沒有意義**：三條「有成效」判準的第三條
   （等預算下 ON 打不打得贏 OFF5）如果拿一個「ON 臂自我修正機制被打七折」
   的 run 去回答，答案本身就是被污染的——就算 ON 贏了 OFF5，也答不出
   「修好之後」的機制設計有沒有用；就算 ON 輸了，也可能只是因為 bug
   讓修訂沒有被觸發，不是模型能力不足。

**推翻條件（若以下任一條成立，這個決定本身要被重新檢討）**：
- 若新開的 post-fix run 也在类似的早期進度（<5%）就發現後端不健康或
  跑出無法解釋的錯誤率飆升，代表殺掉舊 run 換來的不是乾淨資料而是新的
  雜訊來源，這時候該做的是先修後端問題，不是又殺一次重開。
- 若之後有人翻案認為 round347 的 bug 修復本身有誤（例如 dedent 弄壞了
  某些單行 contract 的邊界情況），這個決定連帶要撤銷。

## 沒有做的取捨

- **沒有改變 n、seed、models、arms 等任何實驗參數**——只換了程式碼版本
  （codebench.py 的 bug fix），其他全部原封不動延用 g_r345 的命令列，
  維持跟 round342/345 那條實驗線的可比性。
- **沒有刪除 `runs/g_r345_3arm_20260830/`**——那 16 列是 pre-fix 資料，
  round347 的反事實重算已經用過其中一部分，保留當歷史紀錄，不是這輪
  決定性比較的資料來源。

## 新 run

```
python3 ops/gain/gain_run.py --out runs/g_r348_3arm_20260830 \
  --arms OFF,ON,OFF5 --n 179 --probe-sample 0 \
  --seed g-r212-route-20260828 \
  --models qwen/qwen3.6-35b-a3b,gemma-4-12b-it-qat \
  --request-timeout-s 600 --retries 4 --retry-backoff-s 2.0 \
  --review-timeout-s 380 --review-retries 2
```

同一個 seed／同一組 models／同一個 n——跟 g_r345 唯一的差異變數就是
`codebench.py` 有沒有 dedent fix。跑在背景（`setsid nohup`），本輪不等它。

## 下一輪要做什麼

1. 先查 `ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py"` 應為 1，
   PID 應是本輪記錄的新 PID。**不要重開**，除非它死了。
2. 等有足夠列數後，比較 `passed_review` FAIL 率／revision 觸發率
   （post-fix）vs g_r345 的 16 列＋g_het3_r278／g_onoff5_371_r123
   （pre-fix）——**樣本數不對等，這個比較只能當方向性訊號，不能當
   決定性證據**，決定性證據要等 post-fix run 累積到跟舊 run 相近的量級。
