# round524（2026-09-02，Sonnet 5）：實作 P-R523-1——修 REVIEWER_SYSTEM 的範例，加單元測試

## 觸發

`DECISION_20260902_R523_ACURVE_FABLE_AUDIT.md` §八 P-R523-1：`ops/gain/brain_cline.py:283-285`
的範例 `TEST_ARGS: [[-1, 0, 2]] 與 EXPECTED: 1` 是給單一 list 引數的函式寫的，但 qwen3.6-35b
把它讀成「所有引數都要再包一層 list」的通用慣例——108 張可解析票裡 95 張（round523 S1 量到
60/95 屬於「重試後 exc→ok」，另 35 張原本就沒被這個誤讀命中或屬於別的失敗模式）套用了這個雙層
包裝。round523 fable 稽核輪判定：解一層包裝後 `A_qwen` 從 0.185 上升到 0.667，但**這是格式假象，
不是能力**——閘門判準（Wilson 上界 < 0.80）在兩種算法下都不改變裁決（R522/R523 已定案，本輪不重算）。

human handoff（round523 交棒）：「若無回應：實作 P-R523-1……這是改碼，先寫 DECISION 再動」。
round524 開場檢查人類對 round518-523 六個問題**仍無新回應**（第 7 輪）。照交棒做這件事。

## 這是實驗條件的改變（R440G / KS-1 同一精神）

改 `REVIEWER_SYSTEM` 的措辭會改變評審模型看到的 prompt，之後任何以 qwen（或其他把雙層包裝
讀成慣例的模型）為評審的 run，其 claim_rate／A 都**不能**與此改動之前的 run 直接合併比較。
`R522`／`R523` 的 A_qwen 數字是在**舊版**範例下量到的，本次修改後不會、也不該回填改寫那兩輪的
結論——它們的裁決（梯子停在 L0）本身不受這個 bug 影響（兩種算法上界都 < 0.80）。

## 判準（先寫，動碼之前）

1. 新增單元測試：把 `REVIEWER_SYSTEM` 裡的範例字串（`TEST_ARGS` 那一行的值）丟進
   `ops.gain.gain_run.parse_review_claim`，解析出的 `args` 長度必須等於範例函式的 arity
   （新範例函式若接兩個 positional argument，`len(args)` 必須是 2）。
2. 範例要**明確是多引數**（不能像舊範例一樣「唯一引數恰好是 list」，那正是歧義的來源）。
3. 加一句自然語言澄清：「list 的每個元素對應一個 positional argument；函式只有一個引數時
   list 長度為 1」。
4. `pytest tests/test_gain_runner.py -q` 全數通過（不只新測試，整份都要過，因為
   `REVIEWER_SYSTEM` 被別的測試字串比對用到）。
5. 量具雙向驗證：**不需要**，這次沒有動 `_GAIN_ALLOWED_IMPORTS`／checks.py／sandbox，
   只動了 prompt 字串與測試，不影響 `verify_review_counterexample` 的執行路徑。

## 推翻條件

- 若新範例本身又造出另一種可被誤讀成別的慣例的格式（例如被讀成「TEST_ARGS 永遠兩個元素」）
  ⇒ 下一輪要再做一次像 round523 S1 那樣的「解包裝重算」。
- 若之後的 run 發現 claim_rate 沒有隨這個修正上升（即誤讀假說本身是錯的）⇒ 撤回本文件的因果
  歸因，但範例本身仍然更精確，不必回退。

## 下一步

不需要 run 就完成。下一次啟動 qwen 評審的 run 時，這個 prompt 版本已經生效；那個 run 的
`calls.jsonl` 落盤的 system prompt 全文可以直接核對版本（KS-1 三臂逐字相同的要求不受影響，
這裡改的是 REVIEWER_SYSTEM 不是 WORKER 三臂模板）。
