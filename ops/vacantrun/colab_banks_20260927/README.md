# 五組既有題庫 → agent 工作區任務（Colab 上 pi A/B 用，2026-09-27）

這一份講**題目**：五組題庫從哪來、渲染成什麼形狀、可見／隱藏怎麼切、量具量到什麼、
排除了什麼、哪些話不能說。Colab 上的 A/B 怎麼跑（A＝只有 pi；C＝pi＋`vacant install`）
不在這一份裡。**零模型呼叫**：這裡的每個數字都是量具量的，沒有一個是模型跑出來的。

形狀照 R534（[`ops/gain/r534/BANK_README.md`](../../gain/r534/BANK_README.md)）：
`templates/<dir>/` 是工作區樣板，`hidden/<dir>/` 是**另一棵樹**，只給計分用。

```
templates/<dir>/                              hidden/<dir>/
    goal.md          題目原文（逐位元組）          test_hidden.py   可見 ∪ 隱藏（計分用）
    contract.md      solution.py／函式名／呼叫方式／判等規則／怎麼跑可見檢查（不提隱藏測試）
    tests_visible/test_visible.py   check_*()（＝出貨閘門，agent 跑得到）
    run_tests.sh     R534 的 RUN_TESTS_SH 逐字（＝r530 export_bank.py 那一支）
```

## 一、檔案在哪（⚠ 兩組是私有的）

| 組 | 兩棵樹 | 進版控 | 為什麼 |
|---|---|---|---|
| `lcb_v1`／`lcb_v2`／`lcb_v3` | 本目錄的 `lcb_v*/templates`、`lcb_v*/hidden` | **是** | 題庫檔本身已在 `ops/gain/data/` 進版控；R534 的前例就是整棵進版控 |
| `mbppplus`／`humanevalplus` | `.vacant-private/colab_banks_20260927/<bank>/`（gitignore） | **否**，本目錄只有 `bank_manifest.json`＋`.sha256` | EvalPlus 官方包在本 repo 是**私有、不轉散布**（`.gitignore` 的 `.vacant-private/`、`.github/workflows/ci.yml` 的守門、`runs/INDEX.md` §七），而 GitHub 上這個 repo 是公開的。兩份 manifest **不含任何題目、測資、參考解的位元組**（量具的失敗訊息也拿掉了，因為裡面有 `args=… want=…`） |

給 Colab 的兩個 tar（**可重現**：排序、固定 mtime/uid/gid、gzip mtime=0；只放在 `.vacant-private/colab_banks_20260927/`）：

| 檔 | 內容 | sha256 |
|---|---|---|
| `colab_banks_private_20260927.tar.gz`（2,641 個檔、3,149,278 B） | 兩組的 `templates/`、`hidden/`、`bank_manifest.json(.sha256)`、`render_manifest.json` | `6d5bf331f4d075e5c54d508ba5c28f7e95c65aa254b89fedb18704aed8ff6043` |
| `colab_banks_private_reference_20260927.tar.gz`（1,054 個檔、69,714 B） | 兩組的 `reference/<dir>/{solution.py,stub.py}`（參考解＋退化樁，**只給 selfcheck**，跑完就刪） | `774f5935a5c921bc3805940b2a7854af197295c01c90e7e161d5195dba38537b` |

（兩次 `pack` 的 sha256 逐字相同；解開主包後 `build_banks.py check` 兩組逐檔 sha256 全對。）

解開後是 `colab_banks_20260927/<bank>/…`。兩個 tar 分開，是因為參考解跟隱藏測試一樣是 GT，
而且比隱藏測試更危險（整份答案）——實驗那台機器上只該在 selfcheck 那幾分鐘存在。

## 二、每組題數

| 組 | 來源檔 sha256（前 16） | 上游 | 政策排除 | 建庫排除 | 量具排除 | **可用** | 可見條數 最少／中位／最多（合計） | 隱藏檔條數 最少／中位／最多（合計） |
|---|---|---:|---:|---:|---:|---:|---|---|
| LCB v1 | `eb2a58760818d54b…` | 91 | 2 | 0 | 0 | **89** | 2／2／4（228） | 26／26／28（2,364） |
| LCB v2 | `b98f027213e2469a…` | 120 | 2 | 0 | 0 | **118** | 2／3／4（305） | 23／27／28（3,130） |
| LCB v3 | `bd3dffebb1b16bc7…` | 189 | 0 | 0 | 0 | **189** | 2／2／4（458） | 8／14／28（2,978） |
| MBPP+ v0.2.0 | `af43697e8791c4c1…` | 378 | 7 | 0 | 0 | **371** | 3／3／7（1,153） | 3／108／150（40,259） |
| HumanEval+ v0.1.10 | `272720b90ac37550…` | 164 | 8 | 0 | 0 | **156** | 1／7／105（1,526） | 50／984／1,100（122,166） |

sha256 全文與逐題欄位在各組的 `bank_manifest.json`（`source.sha256` 就是 `codebench.py` 的釘值；
loader 是 fail-closed 的，對不上就停）。「隱藏檔條數」是**可見 ∪ 隱藏**；只在隱藏裡的條數是
`n_hidden_only`（`Mbpp/793` 的 plus 是空集合，隱藏檔＝可見那 3 條）。

- **政策排除**（渲染前，沿用 repo 既有名單，一題都沒有新增）：
  - LCB v1／v2：`lcb_3613`、`lcb_3763`——`ops/gain/check_bank_precision.py:93-94` 的 `KNOWN_BAD`。
    dataset 的 expected 只存到 5 位小數，判準容差 1e-6 ⇒ **精確解也必敗**
    （`decisions/DECISION_20260903_R440T_LCB_UNPASSABLE_TASKS.md`）。v3 沒有已知壞題。
  - MBPP+：7 題，`ops/gain/gain_run.py:54-62` 的 `GAIN_EVALPLUS_RESOURCE_EXCLUSIONS`
    （`Mbpp/255`、`/271`、`/392`、`/599`、`/603`、`/630`、`/644`；canonical 自己跑不完 10 秒／128 MiB）。
    ⇒ 與 G 實驗、R529、R532 同一個分母 **371**。
  - HumanEval+：8 題，`ops/gain/gain_run.py:82-91` 的 `GAIN_HUMANEVAL_EXCLUSIONS`
    （`HumanEval/39`、`/160`、`/162` 需要 `random`／`eval()`／`hashlib`；`/83`、`/100`、`/130`、`/139`
    超出 128 MiB；`/15` 沒有 2× 時間餘裕）。⇒ **分母是 156 不是 164**。
    ⚠ 這 8 題在本題庫的閘門信封（30 秒、512 MiB、只限標準函式庫）下**有些可能是做得出來的**
    （`random`／`hashlib` 都是標準函式庫）。仍然排除，是為了跟既有 run 同一個分母；
    這是本專題自訂的門檻，引用 HumanEval+ 的數字要一起講。
- **建庫排除**：0 題（規則見第四節：期望值寫不成等值字面值、canonical 不確定性、canonical 自己丟例外）。
- **量具排除**：0 題（五組都沒有：有參考解的全過、每題的樁都在可見被擋）。

## 三、可見／隱藏怎麼切（沿用 repo 既有的 V/GT 定義，沒有發明新切法）

| 組 | 可見（`tests_visible/`） | 隱藏檔（`hidden/test_hidden.py`） | 出處 |
|---|---|---|---|
| LCB v1/v2/v3 | 題庫的 `visible_tests` | `visible_tests + hidden_tests` | `vacant_network/codebench.py:1126-1127`（`LiveCodeBenchLoader.iter_tasks`）→ `:1136-1145` 的 `visible_check`／`hidden_check`；R534 同一條 |
| MBPP+ | EvalPlus `base_input` | `base_input + plus_input` | `codebench.py:650-651`（`_norm_inputs` 型別還原）→ `:686-695`（`EvalPlusMBPPLoader`）；G 實驗 `ops/gain/gain_run.py:144-145` |
| HumanEval+ | EvalPlus `base_input` | `base_input + plus_input` | `codebench.py:881-882`（`_he_norm_inputs`）→ `:908-918`（`EvalPlusHumanEvalLoader`）；G 實驗 `gain_run.py:146-153` |

G 實驗（`gain_run.py::load_tasks`）、R529、R532、R534 走的都是這三顆 loader，所以
「可見」＝它們的 `visible_check` 那組輸入，「隱藏檔」＝`hidden_check` 那組輸入（**超集**）。
「隱藏全過」的意思因此跟既有 run 的 `meets_demand` 一樣：整組 case 全過。

## 四、每一題長什麼樣

- **`goal.md`＝loader 吐給 G 實驗的 `prompt` 逐位元組**。LCB＝題庫 `prompt` 欄（尾端那三行中文
  是題庫產生器加的，照留）；MBPP+＝官方 prompt ＋ G 實驗用的 `expose_contract=True` 那段
  「Formal input contract」（`gain_run.py:145`，只有輸入前提、沒有期望輸出）；HumanEval+＝官方
  prompt（簽名＋docstring，`expose_contract=False`）。
- **`contract.md`**：答案寫在工作區根目錄的 `solution.py`、頂層函式名、`f(*args)` 位置呼叫、
  要 return、只准標準函式庫、判等規則、`sh run_tests.sh`。**不提隱藏測試**（有沒有、幾條都不提）。
  LCB 的 contract 是 R534 的 `CONTRACT_TMPL` 逐字；EvalPlus 兩組依每題的判等旗標寫（見下）。
- **判等規則逐行沿用既有判準**，寫進每個測試檔的 `_aeq`：
  - LCB：`codebench.py::_lcb_check_code` 的 `__aeq`（先 `==`、bool 不與數值混談、數值 1e-6、
    list/tuple 遞迴）——直接 import R534 的 `AEQ_SRC`，沒有重寫。
  - MBPP+／HumanEval+：`codebench.py::_check_code`（`:477-524`）的 `__aeq`：set 等價名單
    （MBPP+ 7 題）、regex 題只比真值（MBPP+ 9 題）、`atol`（MBPP+ 13 題、HumanEval+ 3 題）、
    list/tuple 遞迴。旗標逐題寫在 manifest 的 `comparator`。
- **MBPP+／HumanEval+ 跟既有判準唯一的形狀差異：期望值是字面值。** 既有的 `_check_code` 把
  canonical 解**內嵌**進檢查碼、當場算期望值；那不能原樣放進工作區（等於把參考解交給 agent）。
  所以這裡在建庫時跑 canonical、把期望值寫成字面值，並且：
  1. 輸入的「值」＝既有判準實際餵進去的值 `eval(_python_expr(inp))`，不是官方原始值——兩者在
     complex 的 `-0.0` 上會不同（`Mbpp/124` 有 44 條、`/252` 有 33 條實部的 `-0` 變成 `+0`）。
     **跟既有判準走**，逐題條數記在 `n_inputs_gain_literal_differs_from_official`；
  2. 期望值寫成字面值後 `eval` 回來，逐型別、逐元素要**完全相同**（nan、-0.0、tuple/list、
     `collections.Counter` 都分得出來；`Mbpp/88` 回的是 `Counter`，照原型別寫回，因為 `Counter`
     的 `==` 語意跟 dict 不同）；
  3. canonical 在兩個 `PYTHONHASHSEED` 底下各算一次，兩次在該題判等規則下必須相等
     （`Mbpp/2`、`/579`、`/769` 字面值順序不同，但三題都是 set 等價題，判等下相等）；
  4. regex 題的期望值若是 `re.Match`（`Mbpp/737`、`/787`、`/794`）寫成 `_MatchStandIn()`：
     真值為真、`==` 只認自己，與 `re.Match` 在 `__aeq` 裡的每一條路徑行為相同；
  5. 超過約 3600 位的整數寫成十六進位字面值（Python 3.11+ 編譯十進位大整數字面值有 4300 位上限）。
  這五條任何一條做不到就**具名排除**（`expected_not_literal`／`canonical_nondeterministic`／
  `canonical_raises`／`gain_input_literal_unevaluable`），不猜。這一批實際排除 0 題。
- 每個 `check_*()` 是一條 case，失敗訊息 `args=… got=… want=…`（R534 的三欄位逐字）。
  測試檔用 `import solution` ＋ `solution.<entry>(*args)`，agent 在 `solution.py` 裡自己寫的
  `check_*` helper 不會被 driver 收進來。
- 樣板大小：LCB 4.1–7.1 KB、MBPP+ 4.2–7.1 KB、HumanEval+ 4.0–24.2 KB（`HumanEval/32`、`/38`、
  `/50`、`/53` 的可見 base 輸入本來就有 100 條上下）。全部低於 R534 的理智上界 100 KB。
  隱藏檔最大：LCB 98 KB、MBPP+ 808 KB（`Mbpp/462`）、HumanEval+ 3.6 MB（`HumanEval/14`）。
- 樣板路徑沒有任何 `hidden` 字樣；`goal.md` 內文也沒有（`goal_mentions_hidden_word` 全 false）。

## 五、量具（`gauge_banks.py`，零模型呼叫）

**判準只有一份**：直接呼叫 `vacant_network/vrun/acceptance.py::run_suite`——閘門用的那一條
`python3 driver.py <ws> <testfile> <nonce>`，每個測試檔一個子行程。設定＝閘門預設：
後端 `none`（`gateshim.py` 固定）、每檔逾時 **30 秒**（`gateshim.py:764`
`VACANT_TEST_TIMEOUT` 未設＝30）、記憶體 512 MiB（`VACANT_ACCEPT_MEMORY_MB` 未設）、
PATH＝`sandbox._BASE_PATH`（這台 Mac 上 `python3`＝`/usr/local/bin/python3` 3.13.1）。
`acceptance.py`／`sandbox.py` 的 sha256 寫在每份 manifest 的 `gauge.vrun_sources_sha256`。

每題量三件事：

1. **參考解** ⇒ 可見全過、隱藏全過（隱藏跑 2 次，抓不穩的題）。MBPP+＝官方 `canonical_solution`；
   HumanEval+＝`prompt + canonical_solution`（`EvalPlusHumanEvalLoader.canonical_source`）；
   LCB 沒有官方參考解，用 repo 既有的手寫探針解（`ops/gain/data/lcb_probe_solutions.json`＝v1/v2、
   `lcb_v3_probe_solutions.json`＝v3，各 12 題）。**其餘 LCB 題沒有參考解，只驗樁**。
2. **退化樁** `def <entry>(*a, **k): return None` ⇒ 可見至少擋下一條（隱藏也記）。
3. **與既有判準逐份比對**：從已歸檔 run 的 `calls.jsonl` 抽**模型真的寫過的**候選碼（每題最多 6 份，
   從至多 40 份裡等距挑，跨 run、跨臂），同一份碼同時餵既有判準
   `gain_run.meets_demand(code, loader 的 visible_check／hidden_check, 10)` 與渲染出來的兩個測試檔，
   逐一比對。只比沙箱 AST 政策收得下的候選（R534 同一條理由）。兩邊都判隱藏過的候選另外計數
   ＝「歷史候選正控制」——LCB 沒有參考解的題靠它補「正確解會被判過」的證據。

結果：

| 組 | 有參考解 | 參考解 可見＋隱藏×2 全過 | 樁在可見被擋 | 樁可見全擋 | 樁在隱藏被擋 | 正控制：參考解／歷史候選／**無** | 參考解單檔牆鐘 中位／p99／最大 | 樁單檔最大 |
|---|---:|---:|---:|---:|---:|---|---|---:|
| LCB v1 | 12 | 12/12 | 89/89 | 89/89 | 89/89 | 12／63／**14** | 180／818／818 ms | 272 ms |
| LCB v2 | 12 | 12/12 | 118/118 | 118/118 | 118/118 | 12／87／**19** | 116／564／564 ms | 178 ms |
| LCB v3 | 12 | 12/12 | 189/189 | 189/189 | 189/189 | 12／167／**10** | 233／945／945 ms | 613 ms |
| MBPP+ | 371 | 371/371 | 371/371 | 358/371 | 371/371 | 371／0／**0** | 140／3,149／5,371 ms | 627 ms |
| HumanEval+ | 156 | 156/156 | 156/156 | 152/156 | 156/156 | 156／0／**0** | 273／3,446／4,518 ms | 687 ms |

- 量具在 2026-09-27 22:42–23:31（+0800）跑完，Mac（macOS 15.7.3）、沙箱裡 `python3`＝3.13.1。
- **Python 3.12 交叉檢查**（`crosscheck_python.py`，同一份 driver、`.venv` 的 3.12.10）：
  參考解可見＋隱藏全過 12/12、12/12、12/12、371/371、156/156。
  ⚠ 為什麼要另外一支：閘門那條路是 `bash -lc`，macOS 的 `/etc/profile`（`path_helper`）會把 PATH
  重排 ⇒ **`VACANT_ACCEPT_PATH_PREPEND` 在 Mac 上換不掉直譯器**（實測 PATH 前面是 `.venv/bin`，
  沙箱裡照樣是 `/usr/local/bin/python3`）。Linux 上 `/etc/profile` 會不會改 PATH 看發行版——
  **Colab 上一定要看 selfcheck 印出來的那一行 `python3＝…`**，不要假設。
- **樁沒有在可見全擋的題**（至少擋一條，仍算通過）：MBPP+ 13 題（`Mbpp/16`、`/160`、`/285`、`/395`、
  `/602`、`/626`、`/643`、`/737`、`/755`、`/759`、`/773`、`/787`、`/794`——多半是 regex 題或期望值本來就有
  `None`／`False` 的 case）；HumanEval+ 4 題（`HumanEval/12`、`/90`、`/128`、`/137`，期望值裡有 `None`）。
- **參考解最慢的單一測試檔**：MBPP+ `Mbpp/592` 5.4 秒、`/589` 4.2 秒、`/123` 4.0 秒；HumanEval+ `HumanEval/59`
  4.5 秒、`/94` 3.7 秒、`/36` 3.4 秒；LCB 全部 < 1 秒。都在負載下量的（見第七節第 8 條），但離閘門
  預設 30 秒都有 5 倍以上餘裕。
- **LCB 沒有任何正控制的題**（`positive_control=none`）：
  v1 14 題 `lcb_3631`、`3638`、`3674`、`3683`、`3686`、`3687`、`3696`、`3699`、`3700`、`3701`、`3762`、`3765`、`3776`、`3795`；
  v2 19 題＝上面 14 題＋`lcb_3531`、`3552`、`3575`、`3722`、`3786`；
  v3 10 題 `lcb_2849`、`3025`、`3047`、`3230`、`3233`、`3327`、`3354`、`3402`、`3411`、`3478`。
  （`lcb_3722`／`3786` 在 v2 的抽樣裡有候選被渲染檔判過、但既有判準逾時，所以不算「兩邊都過」；
  在 v1 的抽樣裡有。正控制的定義是保守的那一邊。）`lcb_3686`、`lcb_3700` 與 R534 一樣：
  **歷史上沒有任何臂過過**。

**與既有判準逐份比對**（每題最多 6 份已歸檔候選）：

| 組 | 有候選的題 | 比對份數 | 一致 | 不一致 | 信封 | 別名入口 | 當場跑 canonical | 逾時線上 | **未解釋** | 兩邊都判隱藏過 | 政策擋掉（不比） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LCB v1 | 89 | 534 | 520 | 14 | 5 | 0 | 0 | 9 | **0** | 292 | 289 |
| LCB v2 | 118 | 708 | 690 | 18 | 13 | 0 | 0 | 5 | **0** | 402 | 441 |
| LCB v3 | 189 | 1,134 | 1,126 | 8 | 6 | 0 | 0 | 2 | **0** | 807 | 41 |
| MBPP+ | 371 | 2,119 | 2,117 | 2 | 0 | 2 | 0 | 0 | **0** | 1,582 | 17 |
| HumanEval+ | 156 | 855 | 854 | 1 | 0 | 0 | 1 | 0 | **0** | 765 | 56 |

- **43 份分歧全部是同一個方向：既有判準判 False、渲染檔判 True**（渲染檔比較寬），沒有一份反過來
  ——**沒有任何一份候選，在任何一個套件上，是既有判準判過而渲染檔判不過的**。case 集合與比對器
  沒有讓尺變嚴；變寬的地方都在下面四種原因裡。
- 每一份分歧都有解釋（`n_disagree_by_explanation`，定義在 manifest 的 `equivalence.explanations`）：
  - **信封**（24 份）：同一份碼、同一個渲染檔，改用既有判準的信封（10 秒、128 MiB）重跑，判決就回到
    既有判準那一邊 ⇒ 差在逾時／記憶體信封（閘門 30 秒、512 MiB 比較寬），不是題目。
  - **逾時線上**（16 份，全在 LCB）：既有判準撞到它自己的逾時（`checks.py:580` 的
    `call_timeout = timeout*0.9`＝9 秒），渲染檔跑同一份碼本身就要 ≥ 4.5 秒 ⇒ 判決由負載決定。
    同一批候選在不同負載下重跑，分歧份數會變（LCB v1 三次量具跑出 15、20、14 份，本表是最後一次）。
  - **別名入口**（2 份，`Mbpp/20`）：候選寫 `is_woodall = is_woodball`。既有判準只把頂層 `def`／lambda
    的名字交給 verifier ⇒ 找不到入口、連可見都判 False；渲染檔 `import solution` 找得到。
  - **當場跑 canonical**（1 份，`HumanEval/94`）：既有判準每條 case 都當場再跑一次 canonical，
    渲染檔的期望值是字面值 ⇒ 同一份候選在既有判準多花 canonical 那份時間，撞到 9 秒。
- 被沙箱 AST 政策擋掉的候選不比（既有判準連跑都不跑就判 False）：LCB 的數目大（v1 289、v2 441），
  是 `typing`／`list.remove` 那一類，R534 已記過。

## 六、Colab 上怎麼用

```bash
# 0. repo（LCB 三組在這個分支裡）＋兩個私有 tar 與它們的 .sha256（從 Mac 的 .vacant-private/colab_banks_20260927/ 上傳）
sha256sum -c colab_banks_private_20260927.tar.gz.sha256 colab_banks_private_reference_20260927.tar.gz.sha256
mkdir -p /content/vp && tar -xzf colab_banks_private_20260927.tar.gz -C /content/vp

# 1. 逐檔驗 sha256（五組；私有兩組指 --private-root）
python3 ops/vacantrun/colab_banks_20260927/build_banks.py check --bank all --private-root /content/vp

# 2. 在實驗那台機器、那個 python3 上，用已知答案再試一次尺（參考解＋樁；零模型呼叫）
tar -xzf colab_banks_private_reference_20260927.tar.gz -C /content/vp
python3 ops/vacantrun/colab_banks_20260927/gauge_banks.py --selfcheck --bank all --private-root /content/vp
rm -rf /content/vp/colab_banks_20260927/*/reference     # ⚠ 參考解跑完就刪，不准留在實驗機上
```

- `check` 只用標準函式庫（Python 3.11+）；`--selfcheck` 會 import `vacant_network.vrun`，
  所以要先 `pip install -e .`（runtime 依賴只有 `cryptography`）。selfcheck 結果寫到
  `<tree>/selfcheck_<host>.json`，本機跑出來是五組全過（參考解 12/12、12/12、12/12、371/371、156/156，
  樁在可見被擋 89/89、118/118、189/189、371/371、156/156）。
- 工作區＝把 `templates/<dir>/` 整個複製成 agent 的工作目錄。**`hidden/` 與 `reference/` 永遠不進工作區**。
- 計分＝`acceptance.run_suite(sb, ws, "<tree>/hidden/<dir>", suite="hidden", …)`（或
  `python3 -m vacant_network.vrun.acceptance --suite hidden --suite-dir …`），`all_pass` 就是「隱藏全過」。
- 逾時：量具用的是閘門預設 30 秒；參考解最慢的單一測試檔見上表。**建議兩臂都不設
  `VACANT_TEST_TIMEOUT`（＝30）**，A 臂事後計分也用 30。⚠ 參考解只給**地板**：模型寫的慢解會比
  參考解慢（等價比對的分歧裡就有 41 份模型寫的候選，跑完隱藏檔要 5.5–29.4 秒），逾時該設多少要看真跑前幾格的 `wall_ms`，
  不能拿「參考解最慢 × 幾倍」來定。逾時一改，渲染檔與既有判準的差距也跟著變（見第五節「信封」）。
- Python 版本：量具在 Mac 的 3.13.1 上跑，另用 3.12.10 交叉檢查過參考解；Colab 的 `python3`
  是哪一版要以 selfcheck 印出來的為準，**一定要先跑 selfcheck** 再開 A/B。

## 七、誠實邊界（不准省略）

1. **可見測試是單邊的**。「參考解全過＋樁被擋」只保證擋得住 `return None`，**不等於**可見測試涵蓋
   真需求（`vacant_network/suitegauge.py` 那句逐字適用）。CLAUDE.md 記過：`return None` 在某些分支上
   活著（`mbppplus_Mbpp/260`、`humanevalplus_HumanEval/154`、`/106`）——整支回 None 會被擋，某一條
   分支回 None 擋不住。
2. **可見／隱藏的切法是既有的，不是這次定的**，但它不是隨機抽樣：LCB 的可見＝題目敘述裡的範例
   （2–4 條），EvalPlus 的可見＝base（MBPP+ 3–7 條、HumanEval+ 1–105 條）。**可見條數差很多**：
   HumanEval+ 中位數 7 條，有些題的 base 幾乎把大部分行為都測了 ⇒ 閘門在那些題上能擋的東西更少。
   HumanEval+ 在 `ops/vacantrun/humaneval_ab_20260922/` 已經量到兩臂 20/20 的天花板（agent 自己反覆跑
   可見測試），這一組很可能再撞一次。
3. **LCB 沒有官方參考解**。「參考解全過」只覆蓋 12/89、12/118、12/189 題；歷史候選正控制補上一部分，
   但 `positive_control=none` 的題（數目見第五節表）**沒有任何證據證明一個正確解會被判過**。
4. **日期窗與汙染風險**：
   - LCB v1：2024-10-12 → 2025-04-05（全部晚於 2024-08）。
   - LCB v2：2023-08-26 → 2025-04-05；`lcb_3026` 一題是 2023-08-26，其餘 28 題新增在 2024-08→2024-10。
     要主張「晚於訓練截止」得把 `lcb_3026` 另外列。
   - LCB v3：2023-05-07 → 2024-08-10，189 題**全部不晚於 2024-08-10**（184 題早於 2024-08）
     ⇒ **不能**宣稱晚於訓練截止，汙染風險比 v1/v2 高（R460 C3；`codebench.py` 有同一句）。
     v3 與 v2 零交集（樣本外複製集），v1 ⊂ v2 ⇒ **v1 與 v2 的 89 題是同一批題，兩組數字不可相加**。
   - MBPP+／HumanEval+：題目 2021 年公開（MBPP、HumanEval），EvalPlus 擴增測資 2023 年公開，
     網路上到處都是解答 ⇒ **汙染風險最高**。只能說「在這些題上」，不能說「模型沒看過」。
   - 沒有一組能保證晚於 gemma-4-12b-it-qat 的訓練截止（模型卡未公開精確 cutoff）。
5. **題目與既有 G 實驗同一批**：好處是可以對照歷史的 `meets_demand`；壞處是這些題在本專題已經被
   反覆使用（MBPP+ 71 個 run、HumanEval+ 16 個、LCB v2 44 個，見 `runs/INDEX.md` §七），
   選題、排除名單、判準都是**看過資料之後**調過的。
6. **渲染檔比既有判準寬**（兩條路徑的數字不可混報，R534 §五同一條）：
   - 既有判準的 AST 政策（`checks.py::_candidate_functions`）擋 `list.remove` 之類的屬性、只准 11 個
     import；渲染檔只要求「標準函式庫」，而且根本沒有政策。
   - 既有判準只把頂層 `def`／lambda 的名字交給 verifier；`alias = func` 定義的入口在既有判準是 False、
     在渲染檔是 True（`Mbpp/20` 就是這樣，見第五節）。
   - 信封：既有判準 10 秒、128 MiB、EvalPlus 還要當場跑 canonical；閘門 30 秒、512 MiB、期望值是字面值
     ⇒ 慢但正確的候選在這裡會過。
7. **`none` 後端沒有隔離**：驗收直接跑在主機上，cwd＝`HOME`＝工作區，網路是通的。量具量到參考解
   沒有寫任何檔進工作區（`reference_wrote_to_workspace` 全空），但 agent 自己的碼會不會寫就不知道。
8. **牆鐘是在負載下量的**（本機 4 條並行、其他 agent 同時在跑，load average 14–20）。只當量級參考；
   等價比對裡跟逾時有關的分歧數會隨負載浮動（LCB v1 同一批候選三次跑出 15、20、14）。
   MBPP+ 在負載較重的那一輪另有 10 份 `Mbpp/123`、`/592` 的「既有判準逾時」分歧，最後一輪沒有出現。

## 八、重跑

```bash
PY=.venv/bin/python; PR=/path/to/.vacant-private          # 私有包根目錄（含 evalplus/）
$PY ops/vacantrun/colab_banks_20260927/build_banks.py render --bank all --private-root $PR   # 確定性
$PY ops/vacantrun/colab_banks_20260927/gauge_banks.py --bank all --equiv 6 --workers 4 --private-root $PR
$PY ops/vacantrun/colab_banks_20260927/build_banks.py refs --bank all --private-root $PR
$PY ops/vacantrun/colab_banks_20260927/build_banks.py pack --private-root $PR
$PY ops/vacantrun/colab_banks_20260927/build_banks.py check --bank all --private-root $PR
```

`render` 重跑是逐位元組相同的（`check` 會驗）；`gauge` 會重寫 manifest（時間戳與牆鐘會變，
判定欄位不該變）。
