# R523（fable 稽核輪）：對 R522「A 曲線第二點」的獨立重算——判準寫在任何數字算出來之前

（2026-09-02 UTC 22:15 起，Fable 5.1。round522 交棒的稽核重點：R522 **刻意沿用** R519 的
parser 與參考解執行器（`exec` 逐字取用），所以它的 G1 只證明「同一把尺套到別的模型上沒套歪」，
**沒有**證明尺本身對 qwen 的輸出格式是對的。本輪用**第三條程式路徑**重算 A_qwen。）

## 一、稽核輪的限制（照模型政策）

- **不改任何實驗程式碼**（`ops/gain/`、`vacant/`）。只新增 `runs/analysis_round523_audit/` 下的稽核腳本與輸出。
- 不起 run、零 API 呼叫、不動 1004／8765、不刪任何 run 目錄。
- 每個數字附 rows/votes 檔的行數與 sha256 前 8 碼。

## 二、開場對帳（DECISION 寫之前已看過的東西，照實列）

- `acurve_r522.json` sha8 `b1132799`（與 GAIN_STATE 一致）、`votes_r522.jsonl` 3388 行 sha8 `bbccb6d9`、
  題庫 `MbppPlus-v0.2.0.jsonl.gz` sha8 `af43697e`。
- 全部 44 個 run 的 ok review 呼叫：**每個 (run, arm, task, agent, model) 剛好 1 票，沒有重複計票**（3388/3388）。
- `model` 欄有 `qwen_qwen3.6-35b-a3b` 62 張，其 `model_configured` 全是 `qwen/qwen3.6-35b-a3b` ⇒ R522 的
  `norm_model` 合併有據。cline-pass 三顆 `model_configured=None`，n≤1，事前就不進曲線。
- **無法核的**：所有 run 都早於 round520 的 `server_model` 落盤，`model` 是**請求的**模型名，不是伺服器回報的。
  這是 R520 已記錄的缺口，本輪不能補、也不當作推翻理由（8765 依名載模型，沒有證據顯示替換）。

## 三、第三條路徑的定義（與 R518 §十一 同義，實作零共用）

- **parser**：逐行找 `TEST_ARGS:` 與 `EXPECTED:`（大小寫不敏感、允許前導空白），值 `NONE` ⇒ 不可解析；
  `ast.literal_eval`；args 必須是 list/tuple。**不 `exec` R519 的程式碼，不 import R522 的模組。**
- **harness 相等**：數值 `math.isclose(rel=abs=1e-9)`；list/tuple 互通、逐元；dict 鍵集相同、遞迴；其餘 `==`。
- **參考解執行**：`canonical_solution` 在**同一個直譯器**內 `exec` ＋ `signal.alarm(10)`（R519/R522 用子行程；
  路徑刻意不同）。任何例外 ⇒ harness=False。
- **vote_pass**：第一個非空行去空白後大小寫不敏感等於 `VERDICT: PASS`（R522 用「第一行」不是「第一個非空行」；
  qwen 的回應常以 `\n\n` 開頭，這個差異**必須**量出來，見 C4）。

## 四、判準（先寫）

| 檢查 | PASS 條件 | 不過的後果 |
|---|---|---|
| C1 A_qwen 第三路徑 | harness 計數 = **20/108**，逐位 | 列出每一張不一致的票並判定哪條路徑對；以**本輪路徑**重算 Wilson 上界 |
| C1' A_gemma 第三路徑 | = **162/305** | 同上 |
| C2 逐票對帳 | 3388 張的 (parseable, harness) 與 `votes_r522.jsonl` 不一致數 = 0 | 每一張列出、歸類（parser／相等判定／執行器） |
| C3 R522 裁決是否站得住 | 以本輪路徑算出的 A_qwen **Wilson95 上界 < 0.80** | 上界 ≥ 0.80 ⇒ R522 §九-4 裁決降級為「懸而未決」，CONCLUSION 追補段要改 |
| C4 PASS 率 | qwen 投 PASS 的比例以「第一個非空行」重算；與 R522 的 95.5% 差 < 1pp | 差 ≥ 1pp ⇒ R522 「95.5%」要改成本輪數字（不影響 A） |
| C5 分母補報 | A_qwen 限制在 `in_rows=True`（非 void 題）的版本；以及分 vote_pass 兩群（R518 §十一 要求報的） | 只報，不當閘門 |

**C3 是唯一會動裁決的閘門。** C1/C2 的不一致若能歸因且不改變 C3，裁決維持；若不能歸因，
本輪只寫「無法重現」，不寫「推翻」也不寫「確認」。

## 五、推翻本輪的條件

- 若本輪 parser 在 qwen 的**不可解析**票裡多解析出 ≥ 3 張具體反例（R522 §七 的門檻），A_qwen 要用擴大的分母重算；
  若擴大後 Wilson 上界 ≥ 0.80，C3 失敗。
- 若 in-process 執行器與子行程執行器在同一張票上給出不同 harness 值，以**人眼核參考解實際輸出**為準，不是以票數多者為準。

## 六、量測結果

（量完補。）

## 六之前的追加預註冊：S1（commit d3aa6b7，22:21 UTC；S1 的任何 A 都還沒算）

C1/C2/C3/C4 已跑（結果見 §六），過程中看到一個 R522 沒拆的數字：**qwen 108 張可解析票裡 69 張是參考解拋例外
（TypeError 60）**，而評審 prompt 的範例是 `TEST_ARGS: [[-1, 0, 2]]`。用「最後一個 TEST_ARGS」（runtime 慣例）
數形狀：qwen 108 張裡 **95 張是「單一 list 再包一層」**（`[[2]]`、`[["abc"]]`），其中 68 張拋例外。
這是**格式慣例**（照抄範例的雙括號），不是「算不出正確答案」。R522 §七 只在**不可解析**那一側查了
「解析器對 qwen 不友善」，**可解析但包錯層**這一側沒查。以下判準在算之前寫死：

- **S1 規則（兩個模型對稱套用）**：parser 用 runtime 慣例（最後一個 TEST_ARGS／EXPECTED）。先以 `fn(*args)` 跑參考解；
  **若且唯若**拋 `TypeError` 且 `len(args)==1` 且 `args[0]` 是 list/tuple，改以 `fn(*args[0])` 重跑一次（只解一層，不再遞迴）。
  其他例外不重試。
- **報**：A_repacked（qwen、gemma）＋ Wilson95、以及 exc→ok／exc→wrong／exc→exc 的票數。
- **閘門 S1**：A_qwen(repacked) 的 **Wilson95 上界 ≥ 0.80 ⇒ R522 §九-4 裁決降級為「懸而未決」**，CONCLUSION 追補段要改。
  上界 < 0.80 ⇒ R522 裁決維持，但 CONCLUSION 的「qwen 每 120 張票才一個有用反對」與 0.185 這兩個數字**要加註**
  「含 N 張格式包錯層的票；解層後 A=…」——因為 0.185 這個數字混了格式與能力。
- **不管 S1 落哪邊都要另報**：runtime `verify_review_counterexample` 把 TypeError 歸成哪一類——這決定 qwen ON 臂的
  revise 有沒有被格式假象觸發。這一項不是本輪閘門，是給下一輪的線索。

## 六、量測結果（fable，第三條路徑；零 API 呼叫）

腳本 `runs/analysis_round523_audit/audit_r523.py`（10.4 s）→ `audit_r523.json` sha8 `a6880e1a`、逐票 `votes_r523.jsonl` 3388 行 sha8 `e9b203cf`；
S1 腳本 `s1_repack_r523.py` → `s1_r523.json` sha8 `cf34d5b3`、逐票 `s1_votes_r523.jsonl` 413 行 sha8 `868fd189`。
輸入：`votes_r522.jsonl` sha8 `bbccb6d9`、題庫 sha8 `af43697e`。

| 檢查 | 結果 | 判定 |
|---|---|---|
| C1 A_qwen 第三路徑 | **20/108 = 0.1852**，Wilson [0.1232, 0.2688] | **PASS**（逐位＝R522） |
| C1' A_gemma | 163/306（R522：162/305） | 不逐位；兩張差異全部歸因，見 C2 |
| C2 逐票對帳 | 3388 張裡 **2 張不一致，都是 gemma、都是同一個原因**：評審在同一份回應裡寫了 ≥2 行 `TEST_ARGS`（全庫只有 3 張，全 gemma），本輪 parser 取**第一個**、R519／R522／runtime `parse_review_claim` 取**最後一個**（dict 覆寫）。Mbpp/722（第一個 claim 對、最後一個錯）、Mbpp/165（最後一行含 `*`/`+` 運算式，`literal_eval` 失敗 ⇒ 不可解析）。**runtime 慣例是「最後一個」，本輪的偏差在我這邊**，qwen 零影響 | 歸因完畢，不影響 C3 |
| C3 裁決 | A_qwen 上界 0.2688 < 0.80 | **PASS** |
| C4 PASS 率 | 「第一個非空行」與「第一行」兩種算法**都是 0.95456**（qwen 回應的前導 `\n\n` 被 `strip()` 吃掉） | PASS |
| C5 補報 | A_qwen 限 `in_rows` 100 張：15/100 = 0.150 [0.093, 0.233]；qwen 108 張可解析票**全部**是非 PASS 票（PASS 票裡 0 張可解析，定義上如此）；gemma 限 `in_rows` 158/293 = 0.539 | 只報 |

### S1（預註冊在算之前，見上一節）

```
                      as-is（R522 定義）           解一層包裝後                 重試張數   轉移
qwen3.6-35b-a3b       20/108 = 0.185 [0.123,0.269]   72/108 = 0.667 [0.573,0.748]    60      exc→ok 52、exc→wrong 8
gemma-4-12b-it-qat   162/305 = 0.531 [0.475,0.586]  162/305 = 0.531（不變）            4      exc→exc 4
兩比例檢定 gemma vs qwen：as-is p=4.9e-10  →  解層後 p=0.0146，且方向反轉（qwen 0.667 > gemma 0.531）
```

**S1 閘門：A_qwen(repacked) 上界 0.748 < 0.80 ⇒ 不降級，R522 §九-4 裁決 1–3 維持。**

但 R522 §九-5(a) 與 CONCLUSION 追補段的**兩個次要陳述是格式假象，要改**：
1. 「qwen 開口之後只有 0.185 對」——108 張裡 60 張是 `[[x]]` 雙層包裝（照抄 prompt 範例 `TEST_ARGS: [[-1, 0, 2]]`），
   解層後 52 張是對的。qwen「開口之後對不對」的乾淨數字是 **0.667**，與 E1 gemma 的 0.609 同級、高於 gemma 池化的 0.531。
2. 「每 120 張票才一個有用反對」→ 解層後 **每 34 張票一個**（72/2421 = 3.0%）。gemma 是每 5.9 張一個（17.1%）。
   **qwen 真正壞的地方只有一件：claim rate 4.5%（95.5% 投 PASS）**，不是「開口也不準」。
3. 「兩個模型壞在不同的地方」這句**仍成立**但理由要改：gemma 敢開口、開口一半對；qwen 幾乎不開口、開口三分之二對（解層後）。

### runtime 歸類（不是閘門，給下一輪）

qwen 108 張可解析票在 rows.jsonl 的 `review_evidence.status`：`outside_input_contract` **91**、`counterexample_confirmed` 8、
`candidate_passed_claim` 1、不在 rows 8。69 張拋例外的票裡 67 張被 input contract 擋掉 ⇒ **格式假象沒有污染 revise 觸發**
（qwen ON 臂的反例機制本來就幾乎沒動：2421 張票只有 8 張 confirmed）。gemma 有 11 張「參考解拋例外」被算成 confirmed
（R519 已拆過的那一類，例如 0 個引數、除以零）——這是 runtime 把「參考解在該輸入上也炸」當成反例，**R519 §七第2項的提案就是為這個**。

## 七、裁決

1. **R522 的主裁決維持**：兩個家族的 A 上界（0.269／解層後 0.748）都 < 0.80，L3 不復活，梯子停在 L0。
2. **R522 的 0.185 這個數字不能單獨引用**——它混了格式與能力。引用時要寫成「as-is 0.185／解層後 0.667」。
   CONCLUSION 追補段本輪加註（不改 R522 的原文，只加稽核註記）。
3. **「gemma 比 qwen 準」這個方向不成立**（解層後反向、p=0.015、且 qwen 的 108 張是自選的 4.5%，有選擇效應）。
   R522 §九-1 的 p=4.9e-10 是在量「兩個模型有沒有照範例雙層包裝」，不是在量 A。

## 八、提案（給 opus／sonnet 輪；稽核輪不改碼）

**P-R523-1 修 REVIEWER_SYSTEM 的範例**（`ops/gain/brain_cline.py:283-285`）：`TEST_ARGS: [[-1, 0, 2]]` 對「單一 list 引數」是對的，
但被 qwen 讀成「所有引數再包一層」。改法：範例改成多引數的 `TEST_ARGS: [3, "abc"]` 並加一句「list 的每個元素對應一個
positional argument；函式只有一個引數時 list 長度為 1」。**這是實驗條件的改變**（R440G：要 DECISION、要 commit、之後的 run 與
之前的 qwen run 不可直接合併）。附帶單元測試：把範例字串丟進 `parse_review_claim` 後 `len(args)` 必須等於範例函式的 arity。
**不需要 run 就能做、也不需要 1004。** 但在人類回應 R440E 之前，改了也只是為下一個 run 準備。

**P-R523-2 R519 §七第2項**（runtime 把「參考解在該輸入也拋例外」當 confirmed）本輪又多了 gemma 11 張的證據，維持提案、不升級。

## 九、推翻本輪的條件

- 若有人指出 S1 的「只解一層」對某個模型不夠（例如三層包裝），要量出那一類的票數；qwen 8 張 exc→wrong 本輪看過樣本：
  `[['123_a_b']]` 解成 `'123_a_b'` 後參考解回傳值與 EXPECTED 不同，是**真的答錯**不是包裝問題。
- 若 R519／R522 那條子行程路徑與本輪 in-process 路徑在任何一張 qwen 票上 harness 值不同 ⇒ 以人眼核參考解輸出為準。本輪 **0 張不同**。
