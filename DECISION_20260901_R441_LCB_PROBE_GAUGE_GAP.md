# R441：LCB bank 的量具驗證從沒真的接上——找到、修好、驗證

（2026-09-01，Sonnet 5。round440（Fable 5，人類即時指令）造好了 LCB bank
並寫好 E1/E2/E3 三個實驗條件的執行序，但 `r439` 驗證 run 仍在跑，§7 端點
紀律不准同時發第二個 run，所以本輪不能真的發射任何一條 E。這份文件記的是
「發射前又找到一個會讓 E2/E3 當場失敗的洞，順手補上」。）

## 開場

```
hostname            → user1 ✓
git pull --ff-only  → already up to date（HEAD 已經在 round440 的 12af64a，
                       GAIN_STATE.md 落後——round440 沒回填，本輪先讀
                       DECISION_20260901_R440_...md 補上下文再往下做）
r439 process        → PID 2488949 存活，elapsed ~2h07m（開場時）
                       calls.jsonl 129→149 之間持續在動，rate≈1 call/min，
                       跟決定性 run（20-35h）的歷史速率一致，不是卡住
重複 run 檢查        → ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py" = 1
                       （就是 r439 自己，沒有第二個）
df -h /             → 38G 總量、18G avail、52% used，正常
```

## 發現：`probe_instrument` 從沒真的支援過 `--bank lcb`

round440 的計畫（`DECISION_20260901_R440_...md` §E2/E3）打算之後用
`--bank lcb` 發射，且文件宣稱「91/91 arity 驗證、壞候選 fail-closed 驗證」
——但那個驗證是在 `build_lcb_bank.py` 轉換階段做的（arity 比對、測資解析
失敗即丟題），**跟 `gain_run.py` 實際發射前必跑的量具閘門
（`probe_instrument`／`--arms probe`）是兩件事**。

直接跑一次量具閘門：

```
$ python3 ops/gain/gain_run.py --out /tmp/... --n 91 --arms probe --bank lcb --seed g-r442-lcb
91 題（lcb）　輸出 /tmp/g_probe_lcb_check
── 量具驗證（先答已知答案）
   參考解通過 0/0　壞解被擋 0/0
量具驗證一題都沒驗到——這不是通過，是沒接上。停。
```

**根因**：`_canonical_solutions()` 只認 `mbppplus_{task_id}` 這個 key（從
EvalPlus 的 gzip 讀 `canonical_solution` 欄位），LCB bank 的 task_id 是
`lcb_{question_id}` 格式，永遠對不上，`refs.get(t["task_id"])` 對每一題
都是 `None` ⇒ 全部 `continue` ⇒ `n=0`。

**這不是資料錯誤，是結構性缺口**：LCB 的原始資料本來就沒有官方參考解
欄位——`vacant/codebench.py` 的 `_lcb_check_code()` 自己在 docstring 寫
「LCB 的 GT 是 dataset 的 expected output，無 canonical」。round440 造 bank
時已經知道這件事、也因此選擇不去讀不存在的欄位，但沒有同步把
`probe_instrument`／`_canonical_solutions` 改成支援這個沒有官方解的 bank
——量具閘門本身還停在只認 evalplus 的舊版本。

**好消息**：這條路是 **fail-closed，不是 fail-silent**。`main()` 裡
`pr["n"]==0` 會硬 `SystemExit`，發生在任何模型呼叫、任何金鑰載入之前
（`probe_instrument` 是零 API 呼叫的本地檢查）。也就是說，如果沒人修這個，
下一輪照 round440 給的指令發射 E2 只會**立刻**打槍停下，不會浪費任何
8765 端點呼叫、不會污染任何資料——但會浪費一輪去診斷「為什麼失敗」。
本輪判斷值得現在修掉，因為 r439 佔用端點期間本來就不能發射任何東西，
正好是修這類「發射前才會炸」的洞的空檔。

## 修法：手寫並自我驗證一批 LCB 參考解，只給量具用

LCB 沒有官方解，所以不能像 evalplus 分支一樣直接讀資料庫欄位。做法：

1. 從 91 題 LCB bank 裡挑一批小測資（先用 `hidden_check.code` 的長度當
   複雜度代理，之後又直接量了每題測資裡 list/str 的最大長度，發現
   **實際測資都很小**——`longestPalindrome` 最長 30、`minArraySum` 100、
   多數個位數到二十幾，跟原題目 constraints 寫的 1e5 量級完全不成比例，
   猜測是 `build_lcb_bank.py` 的 `MAX_ARG_CHARS=20000` 把大測資都濾掉了）。
2. 對挑中的每一題手寫 Python 解，**不追求跟 LeetCode 官方題解一樣的漸進
   複雜度**——既然這批題目的真實測資都是個位數到幾十的量級，brute force
   在正確性風險上比巧妙演算法低很多，而且反正只給量具用，不進實驗。
3. **每一題都用 `meets_demand()` 直接對真正的 `hidden_check.code` 本地
   跑過**（零 API 呼叫）——先答對再收進參考解字典，不是憑印象寫完就信。
4. 12 題全數通過（好解全過、壞樁全被擋）：`lcb_3653` `lcb_3791` `lcb_3809`
   `lcb_3760` `lcb_3629` `lcb_3607` `lcb_3737` `lcb_3594` `lcb_3779`
   `lcb_3771` `lcb_3805` `lcb_3793`，存進新檔
   `ops/gain/data/lcb_probe_solutions.json`。

## 順手量到的第二個問題：`separateSquares`（lcb_3763）本身可能量不準

嘗試解 `lcb_3763`（幾何線掃、二分搜尋切割線）時，寫的解在**理論上正確**
（二分搜尋收斂到浮點精度極限），但對真實測資跑 `meets_demand` 卻判失敗。
追下去發現：`_lcb_check_code()` 的比較容忍度是 `abs(a-b) <= 1e-6`，但
bank 裡 `expected` 值只存到小數 5 位（例如 `1.16667`，真值是
`7/6=1.16666666...7`，兩者差 `0.0000033` > `1e-6`）——**連精確解都會被這個
容忍度判錯，因為誤差來源是資料集自己的四捨五入，不是解法的誤差**。

沒有嘗試修這個（改容忍度或改資料屬於改題庫本身，本輪只在修量具閘門，
範圍要分開）。**已知後果**：`separateSquares` 這一題如果之後在 E2/E3
的真實 ON/OFF/OFF5 跑裡出現，任何解法（不管多正確）大概率都會被判
`meets_demand=False`——這會把這一題的失敗率往上推、但那是量具的假陽性
不是模型真的答錯。**這題沒有被排除出 91 題的實驗池**（只是沒被收進
probe 的參考解），如果下一輪分析發現某題目異常地全軍覆沒，先查是不是
這一題。

## 改動（`ops/gain/gain_run.py`）

1. `_canonical_solutions(bank="evalplus", path=None)`：新增 `bank` 參數，
   `bank="lcb"` 分支讀 `ops/gain/data/lcb_probe_solutions.json`
   （純 JSON，不是 gzip，不需要 V/GT 分離考量——這批解本來就只給量具用，
   從沒進過任何 prompt）。
2. `probe_instrument(tasks, log, *, sample=12, bank="evalplus")`：新增
   `bank` 參數往下傳給 `_canonical_solutions`。
3. **抽樣邏輯改了語意**：原本是「取 `tasks[:sample]`，每題查有沒有參考解，
   沒有就跳過」——這在 evalplus 上沒差（幾乎每題都有官方解），但在 lcb 上
   會出大問題：`tasks` 的順序由 `seed` 決定（`hashlib.sha256(f"{seed}:
   {task_id}")` 排序），我只手寫了 12/91 題的參考解，若這 12 題剛好沒排進
   `tasks[:12]`，`n` 照樣是 0，跟原始 bug 長得一模一樣，只是原因換了一個。
   改成**先篩出「有參考解」的題目、再取前 `sample` 個**，這樣量具閘門的
   通過與否不再看運氣（不依賴 seed 怎麼排）。
4. 呼叫端 `probe_instrument(tasks, note, sample=probe_sample, bank=args.bank)`
   ——原本沒傳 `bank`。

## 驗證

```
── evalplus（迴歸；round437/438/439 賴以成立的路徑不能被本輪動到）
$ python3 ops/gain/gain_run.py --out /tmp/... --n 179 --arms probe --seed g-r212-route-20260828
179 題（evalplus）　輸出 /tmp/g_probe_evalplus_check
── 量具驗證（先答已知答案）
   參考解通過 12/12　壞解被擋 12/12          ← 跟改動前逐字元相同輸出

── lcb（本輪要修的路徑；round440 給 E2/E3 用的確切指令列）
$ python3 ops/gain/gain_run.py --out /tmp/... --n 91 --arms probe --bank lcb --seed g-r442-lcb
91 題（lcb）　輸出 /tmp/g_probe_lcb_check2
── 量具驗證（先答已知答案）
   參考解通過 12/12　壞解被擋 12/12          ← 改動前是 0/0 SystemExit

── 負向測試（證明閘門真的會抓錯，不是永遠綠燈）：
   把其中一題（lcb_3653）的參考解故意換成回傳常數的錯誤實作，
   重跑 probe_instrument → 參考解通過 11/12（不再是 12/12），
   證明閘門對「參考解本身壞了」敏感,不是隨便什麼字串塞進去都判過。

── r439（本輪不准動到的背景 run）在整個過程中全程存活、持續前進：
   改動前 elapsed 02:07:45／17 rows；驗證後 elapsed 02:19:15／19 rows。
   `gain_run.py` 已經被 r439 的 Python 行程載進記憶體跑著，磁碟上的原始碼
   改動不會回頭影響它（Python 不會重新讀已 import 的模組原始碼）。
```

`pytest` 在這台機器仍不可用（沿用 round439 的既有限制：無 `.venv`、無
`pip3`），用等價的直接函式呼叫＋CLI 全流程驗證代替，兩者都跑了。

## 沒做的事（照實寫）

- 沒有發射 E1/E2/E3 中任何一條——r439 仍在端點上，§7 紀律不准同時發第二個
  run。這份修法是**發射前的準備工作**，不是本輪的主線產出。
- 沒有修 `separateSquares`（lcb_3763）的容忍度/資料問題——範圍屬於題庫本身
  的資料品質，跟本輪「量具閘門接不接得上」是兩個問題，留給要用到這題時
  再處理；已排除在 12 題參考解之外，但**沒有**從 91 題實驗池移除。
- 沒有幫另外 91-12=79 題都寫參考解——`probe_instrument` 的 `sample`
  預設只需要 12 題涵蓋率，12 題已經足夠通過閘門；為每一題都寫解法的成本
  跟量具驗證本身的邊際價值不成比例。
- 沒有更新 `GAIN_STATE.md` 到 round440（發現正本落後一輪，已在下面
  「開場」段落回填，但沒有把 round440 的完整內容複製過來——那份決定的
  完整脈絡以 `DECISION_20260901_R440_...md` 為準，`GAIN_STATE.md` 只記
  本輪摘要，不重複貼一次）。

## 推翻條件

- 若 `_canonical_solutions` 之後被人接進任何會產出 prompt 的路徑（不只
  `probe_instrument`），round441 的「這批解只給量具用，不算作弊」的理由
  就不成立了——V/GT 分離的紀律會被打破，要當場停下來。
- 若 LCB 官方資料集之後有版本更新、真的補上了 canonical solution 欄位，
  `lcb_probe_solutions.json` 這個手寫檔案應該淘汰，改讀官方欄位（跟
  evalplus 分支統一）。
- 若下一輪要用到 `separateSquares` 這題的結果做結論，先重新檢查
  `_lcb_check_code` 的容忍度問題有沒有被處理，否則這題的「失敗」不能算
  模型的錯。

## 下一輪

1. 確認 r439 進度（`ps -p 2488949`、`rows.jsonl` 行數、`calls.jsonl`
   最新時間戳）——**還沒到能下結論的樣本量**（本輪結束時只有 19/179 行
   落盤），純同步進度可以是 local。
2. r439 完整跑完（歷史上 20-35h，本輪開場才過 2 小時多）才能真正回答
   round439 寫死的判準（`discarded_win` 有沒有轉正）。
3. r439 跑完、round437/438/439 的判準都有答案之後，才輪到照
   `DECISION_20260901_R440_...md` §「給迭代圈的執行序」發射 E1
   （`g_r441_gemma_only_mbpp`，evalplus bank，量具閘門本來就沒問題，
   不需要再等這份修法）。E2/E3 現在量具閘門已經接上，發射前只需要照
   常跑一次 `--arms probe` 確認（例行動作，不是本輪這種要修 code 的
   工作）。
