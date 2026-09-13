# round347：`input_contract` dedent bug——評審機制的「反例驗證關卡」對 77.2% 的題目一直是壞的

## 這不是判斷，是可重現的 bug（先講結論）

`vacant/codebench.py:632`（修前）：

```python
contract = rec.get("contract", "").replace("# $_CONTRACT_$", "").strip()
```

EvalPlus 官方資料把每個 `contract` 存成**每一行都預先縮排 4 格**（設計上是要直接
貼進函式主體，例如 `def f(...):\n    assert ...\n    assert ...`）。整條字串只做
一次 `.strip()`，只會削掉**整條字串頭尾**的空白——第一行的縮排因此被削掉、
第二行以後的縮排原封不動留著。任何有 **兩條以上 assert** 的 contract，`.strip()`
之後長這樣：

```
assert isinstance(words, list), "invalid inputs"
    assert all(isinstance(x, str) for x in words), "invalid inputs"
```

這段文字被 `verify_review_counterexample`（`gain_run.py:347-352`）接到一段
賦值敘述後面、當「頂層程式碼」`compile()`／執行：

```python
contract_check = f"""
{assignments}
{input_contract}
"""
in_domain, _ = meets_demand(code, contract_check, timeout_s, entry_point=entry_point)
```

第二行以後的縮排在頂層是 `unexpected indent`——**保證是 SyntaxError**，跟
`assignments` 裡的實際引數值完全無關。`meets_demand` 把這個執行失敗當成
「不通過」＝`in_domain=False`，於是 `verify_review_counterexample` 回傳
`(False, "outside_input_contract")`——**不管評審給的反例引數是不是真的在合法
定義域內，只要 contract 有 ≥2 條 assert，這條路徑保證回傳「域外」。**

## 量到的規模

378 題官方 MBPP+ 資料裡，**292 題（77.2%）的 contract 有 ≥2 條 assert**——
這是全庫的常態，不是邊緣案例。

## 用 production 函式直接重現（不是用手寫字串猜的）

用真實資料跑 `mbppplus_Mbpp/305`（`start_withp`，contract 有 2 條 assert）：

```
review TEST_ARGS=[["Python", "Java"]]（words=["Python","Java"]，isinstance list
且全是 str ⇒ 明明在合法域內）

修前：verify_review_counterexample(...) → (False, "outside_input_contract")
修後：verify_review_counterexample(...) → (False, "candidate_passed_claim")
```

同一份 code、同一份 review、同一組引數，唯一變數是 `input_contract` 字串本身
有沒有被正確 dedent。修前保證回傳域外（不管值），修後才真的去執行檢查、
給出跟引數值相符的答案。用 `git stash` 切回修前版本重跑同一支重現腳本，
確認 `compile()` 丟 `unexpected indent`；修後 `compile()` 過——雙向都驗證過，
不是單向巧合。

## 這對 round345/346 的結論有什麼影響——修正，不是推翻

round345/346 量到「reviewer 原始判斷（raw_pass）常常抓到錯初稿（raw TN
7.6%-32.3%），但 grounded 層級幾乎從不投 FAIL（TN≈0%）」，並把落差歸因於
「`outside_input_contract` 主因是 domain_violation（93.2%-100%，round346 的
`analyze_contract_reject_split.py`），reviewer 常常懷疑對了方向、但舉的反例
落在題目自訂的合法域外——模型能力層級落差，不是關卡設計缺陷」。

**這個解釋現在要打折扣，但方向沒有整個錯**。用同一支 `analyze_contract_reject_
split.py` 的邏輯、額外查每個 `domain_violation` 樣本的 task 對應 contract
有幾條 assert，拆出「bug 保證觸發（≥2 條 assert）」vs「單條 assert（bug 不
介入，若真的判定域外就是真訊號）」：

| run | domain_violation 總數 | 多 assert（bug 保證觸發）| 單 assert（bug 不介入）|
|---|---|---|---|
| g_het3_r278 | 55 | 53（96.4%）| 2（3.6%）|
| g_on371 | 5 | 4（80.0%）| 1（20.0%）|
| g_onoff5_371_r123 | 39 | 20（51.3%）| 19（48.7%）|

**多 assert 那一塊——三個 run 都是壓倒性或至少過半——保證是 bug 觸發的，
跟 reviewer 反例的引數值完全無關，不是「reviewer 懷疑對方向、舉證落在域外」
的證據，是純粹的字串格式 bug。單 assert 那一塊（bug 不介入的路徑）才是
round345/346 那個「reviewer 常舉出真正域外反例」解釋還站得住腳的部分——
且 `g_onoff5_371_r123` 這個最大樣本的 run 裡，單 assert 佔了近半，不是零，
所以「reviewer 有時真的會舉出域外反例」這件事本身**沒有被推翻**，只是
「domain_violation 是壓倒性主因」這句話裡有一大塊（尤其 R278 的 96.4%）
其實是量具壞掉，不是模型能力落差。

## 更重要的下一層：這不只是診斷用的離線分析工具的 bug，是 runtime 本身的 bug

`analyze_contract_reject_split.py` 只是離線重算診斷分類，本身不影響任何一次
run 的實際產出。但 `verify_review_counterexample` 的 `confirmed` 布林值會**直接
餵進 runtime 的核心決策**（`gain_run.py:490-499`）：

```python
grounded_pass = raw_pass or not confirmed
votes.append((aid, grounded_pass))
...
passed_review = sum(1 for _, ok in votes) >= (len(votes) + 1) // 2
```

`confirmed=False`（bug 觸發時保證如此）⇒ `not confirmed=True` ⇒
**不管 reviewer 原始判斷是不是 FAIL，這一票在 grounded 層級一律變成 True
（等於棄權變成同意通過）**。`passed_review` 這個多數決接著直接決定
`selected_version`（`gain_run.py:531-545`）是保留 initial 還是觸發 revision。

**這代表 ON 臂的「審核→修訂」自我修正機制，對全庫 77.2% 的題目，
從一開始就被這個 bug 打了折扣**——不是 reviewer 找不到域內反例才沒觸發修訂，
是即使 reviewer 找到了域內的合法反例，只要它撞進這個 SyntaxError 路徑，
系統也會把這一票當成「反例不成立」處理，跟反例本身對不對無關。round345/346
把 TN=0 完全歸因於「模型能力層級落差」，**現在看至少有一部分（R278 那樣
高達 96.4% 的 domain_violation 樣本）該歸因於這個 bug，而不是模型能力**。

## 已修（round347，這一輪做的）

`vacant/codebench.py`：把 `.strip()` 前先 `textwrap.dedent()`，讓多 assert 的
contract 正確去除共同縮排後才拼進 top-level 程式碼。新增回歸測試
`tests/test_evalplus_loader.py::test_multiline_contract_dedents_to_valid_
standalone_code`，用真實 EvalPlus 的縮排格式（每行都預縮排 4 格）當 fixture，
斷言 `input_contract` 拼進頂層賦值後可以 `compile()`。**雙向驗證**：
用 `git stash` 切回修前的 `codebench.py` 重跑同一支測試，確認它會丟
`SyntaxError: unexpected indent`（植入缺陷會 FAIL）；修後重新驗證通過。

**已知環境限制**：這台機器沒有 `pip`／`pytest`（`python3 -m pip` 與
`ensurepip` 都不存在），無法用 `pytest tests/test_evalplus_loader.py` 跑
完整套件驗證沒有連帶破壞其他測試。改用**手動直接呼叫**同等邏輯
（複製 `_write_pack`/`_loader`/`_REC1` 的最小片段，繞開整份測試檔案頂部
`import pytest` 造成的 ImportError）驗證新測試本身的行為，另外讀過
`test_gain_mode_exposes_input_contract_but_not_ground_truth`（既有測試，
contract fixture 本身兩行都沒有縮排）確認 `textwrap.dedent()` 對已經沒有
共同縮排的字串是恆等操作，不會改變既有測試的斷言結果——**但沒有實際跑過
pytest 驗證這句話**，是讀程式碼＋人工推理，不是跑出來的證據，照實記錄。

## 沒做的事（照實寫，不是本輪職權範圍）

- **沒有動或重啟正在跑的決定性 run**（`g_r345_3arm_20260830`，PID 2248124）。
  它已經把舊版 `codebench.py` 讀進行程記憶體，之後改磁碟上的檔案不會影響
  它——這是好事，這個 run 的資料內部前後一致（全程用同一版壞掉的 dedent
  邏輯），可以照原樣分析完，只是**它的「審核機制有沒有效」這個診斷結論
  要註明「在這個 bug 修好之前量的」**。
- **沒有為了這個發現去重跑或啟動新的決定性 3-arm run**。修這個 bug 改變了
  ON 臂 revision 觸發的實際行為（更多真域內反例會真的觸發修訂），這是
  貨真價實的實驗條件改變，比照 round342/345 的慣例，這需要另開一輪寫
  prereg 決策文再啟動，不是本輪能力範圍內可以順手做的事。
- **沒有推翻三條「有成效」判準的達成狀態**——三條判準看的是各臂
  `meets_demand` 比較，不是 review gate 的診斷分類，這個 bug 目前沒有
  證據顯示會反過來讓某一臂的 `meets_demand` 分子分母算錯（`meets_demand`
  本身走的是 `hidden_check`，跟 `verify_review_counterexample` 是分開的
  程式碼路徑）。這是對「機制為什麼沒展現加值」這個解釋層的修正，不是對
  主結論的推翻。

## 反事實重算（本輪做了，不是留給下一輪）：用修好的關卡重跑三個 run 的舊資料

`analyze_contract_reject_split.py` 只分類、不重算。本輪額外寫了一段一次性腳本
（純離線，讀已落盤的 `initial_code`／review 全文，直接呼叫修好之後的
`verify_review_counterexample`，**不呼叫任何模型**），把三個 run 裡所有原本被
runtime 判成 `outside_input_contract` 且 arity 對得上的 (task_id, agent_id) 全部
重跑一次（`g_on371` 沒有落盤 `entry_point` 供部分題目查找，count 略低於
`analyze_contract_reject_split.py` 的分類數，屬於同一批已知的缺資料限制）：

| run | 重算樣本數 | → counterexample_confirmed（真反例，原本被吃掉） | → candidate_passed_claim（原本判斷仍對）| → 仍是 outside_input_contract（bug 修好後依然域外，是真的域外）|
|---|---|---|---|---|
| g_het3_r278 | 55 | 26（47.3%）| 20（36.4%）| 9（16.4%）|
| g_on371 | 5 | 0 | 0 | 5（100%）|
| g_onoff5_371_r123 | 39 | 12（30.8%）| 0 | 27（69.2%）|
| **合計** | **99** | **38（38.4%）** | **20（20.2%）** | **41（41.4%）** |

**38/99（38.4%）原本被這個 bug 吃掉的「域外」判定，修好之後變成
`counterexample_confirmed`——這些是 reviewer 找到的真反例，原本因為
SyntaxError 被系統誤判成「反例不成立」，`grounded_pass` 因此被錯誤地
記成 True（等同棄權變同意），該觸發的 revision 沒有觸發。** 這不是
「reviewer 常常聞到不對但抓不準域內反例」的能力落差故事能解釋的——
這 38 筆是 reviewer 抓對了、系統自己把答案弄丟了。

同時，41/99（41.4%）修好之後依然是域外（`g_onoff5_371_r123` 佔了其中
27 筆）——說明 round345/346「reviewer 有時真的會舉出域外反例」這件事
本身沒有被推翻，是兩種現象同時存在、比例上這次量到「真反例被誤殺」
（38.4%）跟「reviewer 真的舉錯」（41.4%）大致同量級，`candidate_passed_
claim`（20.2%）則是「反例不成立，維持原判無影響」。

**這把round345/346「TN=0 完全是模型能力層級落差」的結論從「解釋了大部分」
下修到「解釋了大約四成、另外四成是這個 bug 造成的、剩下兩成不受影響」**——
是本輪最重要的量化更正。

## 下一輪可以做的（不是必做，是判斷）

1. **修 bug 後另開一輪決定性 3-arm run**，寫 prereg 決策文，比較
   revision 觸發率／`passed_review` FAIL 率修前修後有沒有差、有沒有差到
   足以改變 ON 對 OFF5 的等預算勝負。這是本輪發現裡最值得追的方向，但
   量級是「新的一輪決定性實驗」，不是本輪能力範圍內的收尾動作。
2. （已完成，見上面「反事實重算」一節，不再是待辦）
3. 確認這台機器要不要想辦法裝 `pytest`（或找一台有網路的機器跑一次
   完整測試套件），把「新測試沒有連帶弄壞別的測試」從人工推理升級成
   真的跑過的證據。
