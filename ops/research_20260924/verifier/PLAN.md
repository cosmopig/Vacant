# 問題二試驗計畫（評審呼叫**之前**凍結，2026-09-24）

> 這不是「證明」用的預註冊（鐵律 5：證明保留給預註冊 batch run），是**探索性量測**的
> 分析計畫。寫死它的理由是：評審的數字一出來，最容易動的就是門檻與口徑。
> 本檔與 `exp_*.py` 在任何評審呼叫之前 commit；之後改動要在 DECISION 裡寫明。

⚠ 已經先跑、而且不花 token 的：`exp_visible_gate.py`（V0，只讀歸檔）、
`exp_ifeval.py gt`（官方檢查器算真值）、`exp_ragtruth.py sample`／`dev`（抽樣與確定性門檻）。
dev 的判準（precision ≥ 0.9 且至少 5 次觸發，否則該層停用）**寫在 `cmd_dev` 裡、先於執行**；
結果：三個型別的兩個確定性層**全部沒過門檻 ⇒ 全部停用**（`results/ragtruth_dev_thresholds.json`）。
這個結果**不改門檻去救**。

## V0 可見測試當驗證器（零 token）
- 資料：`runs/INDEX.json` kind=real_run、OFF 臂、有 `visible_ok`／`meets_demand` 的列。
- 指標：接受者的 precision（＝1−洩漏率）、拒絕者的誤殺率、準確度。

## V1 IFEval（n=540；1 筆因 prompt 被改過而排除）
- GT：官方 strict 檢查器；loose 只報分歧數。
- 策略：D（自寫通用檢查，編譯不到 ⇒ unknown）、J（評審逐條）、C（D＋殘差才問評審；D 已 reject ⇒ 不問）。
- 評審：Haiku 4.5 全部 540；Sonnet 5 抽 150（seed 20260924）。thinking 關、工具關。
- 主要指標（prompt 層）：接受者中的錯誤率（false accept rate）、已判定準確度、覆蓋率、
  unknown 當錯的準確度、每題 token（raw 與扣固定開銷的 net）、每題評審呼叫數、美元。
- 次要：逐條（instruction 層）一致率、逐型別。

## V2 RAGTruth（test 300 = 3 型別 × 50 有幻覺 × 50 無，seed 20260924）
- GT：人工標註，回應有任何標註片段 ⇒ 有幻覺。
- 策略：D、J、Jq（rejected 要附逐字存在於回應的引文）、C、Cq；預算上限掃描
  cap ∈ {0, 250, 500, 750, 1000, 1500, 2000, 3000, ∞}（呼叫前用字元數估）。
- 評審：Haiku 4.5 全 300；Sonnet 5 全 300。
- 主要指標：同 V1；另給「依 test split 自然盛行率重新加權」的接受者錯誤率。
- ⚠ D 在 dev 上全部停用 ⇒ C＝J（級聯退化）。這本身是要報的結果。

## V3 附證據的交付物（D 在自由文本上失敗之後的追加；**評審呼叫前寫定**）
問題：自由文本上便宜的檢查不夠準（V2 dev）。假說：要求交付物**附上逐字引文**
（每一句後面附一段來源原文），確定性層就能做兩件事：(a) 引文不在來源裡 ⇒ rejected；
(b) 評審只需看「句子＋引文」而不是整份來源 ⇒ token 少。
- 材料：RAGTruth test 的 Summary 與 Data2txt 來源各 30 個（seed 20260924，與 V2 樣本無關的抽法）。
- 產生：Haiku 4.5 依「每句附 [[quote: 來源原文]]」格式寫摘要／概述（60 通）。
- 受驗集：每份產出一個「原樣」版本，加一個**人為注入錯誤**版本（隨機一句裡把一個數字或
  專有名詞換掉，錯誤注入是確定性的程式，不用 LLM）⇒ 120 筆，真值來自構造。
  ⚠ 這是**合成真值**，不是人工標註，只能講「對這種注入錯誤」。
- 策略：J-full（評審看整份來源＋產出）vs E（確定性：每句都有引文、引文逐字在來源、
  句中數字都在自己那段引文裡）→ 殘差再問 J-claim（評審只看各句＋其引文）。
- 指標：同上，外加每題 token 比。

## 共通
- 三值：unknown 永遠不算通過；報告「unknown 當錯」的準確度當保守數字。
- 評審失敗（四次重試都失敗）⇒ unknown，計入 `J_calls_failed`。
- 全 I/O 落盤：`results/judge_calls_*.jsonl`。
- KS-1：評審 system prompt 經 `judge_claude.assert_clean`。
- 不准說：「驗證器證明了正確」「評審準確率 X%」而不帶資料集、模型、GT 定義。
