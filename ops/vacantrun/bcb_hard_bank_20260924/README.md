# BigCodeBench-Hard 題庫（2026-09-24）：選了什麼、怎麼切、怎麼量

這一份講**題目**：從哪裡來、渲染成什麼形狀、可見／隱藏怎麼切、量具量到什麼、
排除了什麼。今晚 A/B 實驗的跑法不在這一份裡。

形狀與 R534 題庫（`ops/gain/r534/BANK_README.md`）相同：`templates/<id>/` 是
工作區樣板，`hidden/<id>/` 是**另一棵樹**，只給計分用。

## 一、為什麼選 BigCodeBench-Hard

R534 的 LCB 題有兩個已知弱點：

1. **沒有參考解**：正控制只有 1/20，有兩題我們根本沒有證據證明「正確的解會被判過」。
2. **只考純演算法、只准用標準函式庫**：跟 agent 平常做的事（呼叫 pandas／requests／
   檔案系統）差很遠。

BigCodeBench-Hard（`bigcode/bigcodebench-hard`，148 題）這兩格都補得上：題目要用真的
函式庫做事，而且**每題都有 `canonical_solution`**。所以 r530 那一套雙向量具
（參考解全過、退化樁被擋）在這裡每一題都做得到。

## 二、來源（釘死）

| 項目 | 值 |
|---|---|
| 資料集 | `bigcode/bigcodebench-hard`，split `v0.1.4`（最新） |
| 原始檔 | `https://huggingface.co/datasets/bigcode/bigcodebench-hard/resolve/main/data/v0.1.4-00000-of-00001.parquet` |
| sha256 | `73a4270b43feb81abefad7bb1b592937c768ea45c3263bedc1cabd30a9a6ce79`（＝HF 的 LFS oid） |
| HF repo commit | `298d2cc7b96612e15e47313c3603ee124cee0c1f`（lastModified 2025-02-23） |
| 官方 eval 需求 | `bigcode-project/bigcodebench` `Requirements/requirements-eval.txt`（sha256 `a4d01fb1…`，下載於 2026-09-24） |

sha256 對不上，`build_bank.py` 就停（fail-closed），不會安靜地換成另一份題庫。

## 三、檔案形狀

```
bank/templates/<bcb_N>/                     bank/hidden/<bcb_N>/
    goal.md       ← instruct_prompt 逐位元組     test_hidden.py  ← TestCases 全部方法
    contract.md   ← 介面／imports／可用函式庫
    tests_visible/test_visible.py  ← 只含可見的那幾個方法
    run_tests.sh  ← R534 的 RUN_TESTS_SH 逐字
```

- `goal.md` 是題庫 `instruct_prompt` 原文，結尾本來就附了 `You should write
  self-contained code starting with: ```import … def task_func(…):````。
- `contract.md` 照 R534 的語氣寫：答案寫在工作區根目錄的 `solution.py`、定義頂層
  `task_func`、imports 與簽名照 `code_prompt`（逐字貼上）、列出這題用到的函式庫、
  可見檢查怎麼跑。**不提隱藏測試**（有沒有、幾條、長什麼樣都不提）。
- 測試檔的形狀：

  ```python
  from solution import *          # BigCodeBench 的測試假設它跟解答在同一個命名空間
  sys.modules.setdefault(__name__, solution)   # 讓 patch(__name__ + '.x') 打到解答（見第六節）
  <上游 test 原文（可見檔已刪掉非可見的方法）>
  <把命名空間裡所有 check_* 名字清掉>
  def check_<method>(): _vacant_run("<method>")   # 每個選中的方法各一個
  ```

  `_vacant_run` 用 `unittest.TestSuite([TestCases(m)]).run(unittest.TestResult())`
  跑那一個方法（setUp／tearDown／setUpClass 都會跑），`wasSuccessful() and testsRun == 1`
  才算過。其他情況都 `raise AssertionError("FAIL|ERROR <method>: <traceback 最後幾行>")`，
  長度上限 700 字元。官方評測也是用 `TestResult`＋`suite.run`，skip 一樣不算失敗。
- **為什麼要清 `check_*`**：`acceptance.py` 的 driver 會收模組裡**所有**以 `check_`
  開頭的 callable。如果 agent 在 `solution.py` 裡寫了一個 helper 叫 `check_input(x)`，
  `from solution import *` 會把它一起帶進來，driver 用零個引數呼叫它就會 TypeError，
  一份正確的解因此被判失敗。清掉之後才定義我們自己的 `check_*`，contract 也寫明了
  「`check_` 開頭的名字會被忽略」。上游 test 原文如果在模組層級定義了 `check_*`，
  builder 會直接停下來（148 題實測沒有這種題）。

## 四、可見／隱藏怎麼切（這是我們定的，不是官方的）

上游只有一個 `TestCases`，沒有可見／隱藏的區分。規則寫死在
`build_bank.py::SPLIT_RULE`，manifest 另外記它的 sha256：

> TestCases 中名字以 `test` 開頭的方法（unittest 預設 loader 會收的那些），依方法名
> **字典序**排序，取前 ⌈n/3⌉ 個（至少 1 個）當可見；隱藏檔收全部 n 個（可見 ∪ 隱藏）。

- n 的範圍是 3–12，沒有 n=1 的題。n=1 時規則會讓可見＝隱藏，這批沒有碰到。
- 字典序的意思是 `test_case_10` 排在 `test_case_2` 前面。規則是確定的，但**不是隨機
  抽樣**：如果上游作者習慣把簡單的例子放在 `test_case_1`，可見那一側就會偏向簡單題。
- 刪掉非可見方法時用的是**行區間**：把方法連同它的 decorator、緊貼在上方的註解行
  一起刪掉，其餘位元組照抄。刪完再 parse 一次，確認剩下的 test 方法剛好就是可見那一組。
- 重名方法（例如 `BigCodeBench/1006`）：Python 只認最後一個定義，所以方法名去重之後，
  才是實際會跑的那組方法。manifest 的 `duplicate_method_names` 有記。
- **隱藏檔 ＝ 可見 ∪ 隱藏**：「隱藏全過」的意思就是上游整份 `TestCases` 全過，
  跟 BigCodeBench 官方 pass 的定義一樣（在我們的環境下）。

## 五、環境（vacant-dev）

- venv：`/var/tmp/vacant_piext_20260924/bcb/venv`（`/usr/bin/python3` 3.12.3 建立）。
  python 路徑是 `…/bcb/venv/bin/python3`。
- 版本盡量對齊官方 `requirements-eval.txt`。官方的版本是替 Python 3.10 釘的，其中幾個
  在 3.12 上沒有 wheel，改用**最近一個有 cp312 wheel 的版本**：

  | 套件 | 官方 | 這裡 | 理由 |
  |---|---|---|---|
  | numpy | 1.21.2 | 1.26.4 | 3.12 最早的系列 |
  | scipy | 1.7.2 | 1.11.4 | 同上 |
  | pandas | 2.0.3 | 2.1.4 | 同上 |
  | matplotlib | 3.7.0 | 3.8.4 | 同上 |
  | scikit-learn | 1.3.1 | 1.3.2 | 同上 |
  | statsmodels | 0.14.0 | 0.14.1 | 同上 |
  | gensim | 4.3.2 | 4.3.3 | 同上 |
  | numba／llvmlite | 0.55.0 | pip 依 numpy 1.26.4 解出來的版本 | librosa 的依賴 |
  | fiona | （未釘） | 1.9.6 | geopandas 0.13.2 遇到 fiona 1.10 會壞 |

  其餘（requests 2.31.0、bs4 4.8.2、Faker 20.1.0、nltk 3.8、cryptography 38.0.0、
  flask 3.0.3、Pillow 10.3.0、opencv-python-headless 4.9.0.80、lxml 4.9.3、librosa
  0.10.1、…）跟官方一致。完整的 `pip freeze` 在 `bank_manifest.json` 的
  `gauge.pip_freeze` 裡，sha256 也一併記了。
- **沒有裝**：`tensorflow`／`keras`（約 2GB，超出這台 4G 的磁碟預算）⇒
  `BigCodeBench/417`、`/418` 在渲染之前就排除（`POLICY_EXCLUDE`，具名）。
- **NLTK 資料**：`punkt`、`stopwords` 預先下載到 `venv/nltk_data`。NLTK 會搜尋
  `sys.prefix/nltk_data`，所以離線也找得到。題目裡的 `nltk.download(...)` 在沒有網路時
  只會印錯誤、不會 raise。兩臂共用同一個 venv，所以這一點對 A/B 是公平的。

## 六、量具（`gauge_bank.py`，零模型呼叫）

每一題量三件事：

1. **參考解**（官方組法：`complete_prompt + "\n" + canonical_solution`）⇒ 可見要全過，
   隱藏要全過，**隱藏跑兩次**（用來抓不穩的題）；
2. **退化樁** `def task_func(*a, **k): return None` ⇒ 可見至少要有一個失敗（隱藏的結果也有記）；
3. **離線檢查**：參考解在網路隔離的後端（`bwrap --unshare-all`）再跑一次隱藏檔。

**判準只有一份**：量具直接載入 `vacant_network/vrun/acceptance.py`＋`sandbox.py`
（兩份原始碼的 sha256 寫在 manifest 的 `gauge.vrun_sources_sha256`），呼叫
`acceptance.run_suite(...)`。這就是閘門用的那條 `python3 driver.py <ws> <testfile> <nonce>`，
沒有另外寫第二套判準。

量具跟閘門**預設值**不同的地方（都是「量得動」的前提，manifest 的
`gauge.deviations_from_gate_defaults` 逐字記下）：

| 項目 | 閘門預設 | 量具 | 為什麼 |
|---|---|---|---|
| PATH | `_clean_env` 寫死 `/usr/local/sbin:…:/bin` ⇒ `/usr/bin/python3` | 前面加上 `venv/bin` | 預設的 python 沒有 pandas，參考解一題都跑不起來 |
| RLIMIT_AS | 512 MiB | 2048 MiB | 512 MiB 實測在 `import matplotlib` 就 `failed to map segment from shared object` |
| 每檔逾時 | 10 秒（launcher） | 120 秒 | 用來量 wall time；建議值見第七節 |
| 後端 | `auto` | `none`（跟實驗閘門一樣，gateshim 固定 `none`） | — |

⇒ **實驗的閘門必須用同一組 PATH 與記憶體設定**，這份量具結果才適用
（`VACANT_ACCEPT_PATH_PREPEND=/var/tmp/vacant_piext_20260924/bcb/venv/bin`、
`VACANT_ACCEPT_MEMORY_MB=2048`）。

排除規則（依序判定）：

| exclude_reason | 意思 |
|---|---|
| `policy_tensorflow_keras` | 渲染前就排除（tensorflow 沒裝） |
| `timeout`／`missing_lib`／`memory`／`network`／`flaky`／`reference_fails_other` | 參考解沒有全過，依失敗訊息歸類（`classify()`）。`flaky`＝同一個隱藏檔跑兩次，結果不一致 |
| `network` | 參考解在 `none`（有網路）下全過，但在網路隔離後端失敗，而且失敗訊息是網路類 ⇒ 這題能不能過要看外部伺服器 |
| `flaky`（離線檢查） | 參考解在 `none` 下全過，換到網路隔離後端再跑一次隱藏檔卻沒過，而且訊息**不是**網路類 ⇒ 同一份參考解、同一個隱藏檔，換一次執行就不過 |
| `stub_not_blocked` | `return None` 的樁，可見測試一條都沒擋下 |

`Connection refused` **刻意不算**網路標記：localhost 的 socket 測試也會丟這個錯。
自動分類之外，人讀過失敗訊息後補的具體說明寫在 `KNOWN_DETAIL`，進 manifest 的
`exclude_detail`。**它只補說明，不改分類結果。**

量具跑了四輪（前三輪的 manifest 留在 vacant-dev 的 `logs/bank_manifest_run{1,2,3}.json`）。第一輪抓到兩個
**環境缺件**：`xlrd`（`BigCodeBench/501`）和 `pkg_resources`（librosa 要）。補裝之後 501
就過了。第一輪也抓到一個**跑法差異**：`BigCodeBench/593` 的測試寫了
`patch(__name__ + '.randint')`，driver 沒有把測試模組註冊進 `sys.modules`，所以 import 不到。
現在測試檔在 `from solution import *` 之後，把 `solution` 登記在 `__name__` 底下
（`build_bank.py::NAMESPACE_SHIM`）。這三行對其餘 145 題沒有作用，因為只有 593 用了
`__name__`。第二輪抓到的是 classify 的 bug：可見過、隱藏不過被誤判成 `flaky`；另外
`Connection refused` 被誤當成網路標記。兩個都修了。第三輪 `BigCodeBench/1040` 在離線後端又過了，但它已經有一輪失敗的實測紀錄，所以用 `MANUAL_EXCLUDE` 加上證據出處排除（只准往排除那一側用）。第四輪才是正式結果。

## 七、量到的結果

（由 `gauge_bank.py` 產出；數字以 `bank_manifest.json` 為準，下面是摘要）

第四輪（正式）：`bank_manifest.json` sha256 `eb145430e7b29f496bc25326380bec09029336f8dcb6ee9ebd6bc230acbe1a6b`。

**可用 139 題**。上游 148 題 → 渲染前排除 2 題 → 渲染 146 題 → 量具排除 7 題：

| exclude_reason | 題 | 具體原因 |
|---|---|---|
| `policy_tensorflow_keras` | 417、418 | 要 tensorflow／keras，沒裝（約 2GB） |
| `network` | 590 | 測試真的連到 en.wikibooks.org，對方回 HTTP 403，有網路也過不了 |
| `network` | 1012 | 測試真的從 drive.google.com 下載，離線就 NameResolutionError |
| `reference_fails_other` | 101 | matplotlib 3.8 的 QuadMesh.get_array() 回 2-D，測試期望 1-D（官方釘 3.7.0）；另外會下載 Boston 資料集 |
| `reference_fails_other` | 227 | 測試用了 `assertAlmostEquals`，這個名字在 Python 3.12 已經移除 |
| `reference_fails_other` | 1085 | 參考解用了 `punctuation` 卻沒有 import，只靠官方評測共用命名空間才過得了 |
| `timeout` | 461 | 整檔超過 120 秒（測試在等子行程逾時） |
| `flaky`（人工、跨輪） | 1040 | localhost socket 伺服器測試：bwrap 後端三輪有一輪參考解失敗；單檔 60 秒 |

`stub_not_blocked` 是 0 題。

**量具結果（139 題全部）**：

- 參考解：可見全過、隱藏兩次全過、離線（bwrap）隱藏全過 ⇒ 139/139。
- 退化樁：可見至少擋下一條 ⇒ 139/139；隱藏也擋下 ⇒ 139/139。
  樁在可見側擋下的條數：全擋 132 題；只擋下 2 條可見中的 1 條，6 題；
  可見只有 1 條、而且擋下了，1 題。
- 方法數分布（`n_methods_total`）：3→1、4→1、5→93、6→21、7→9、8→3、9→4、10→4、11→1、12→2。
  可見方法數：1→1 題、2→115 題、3→16 題、4→7 題。只在隱藏裡的方法數：2–8，中位數 3。
  總計可見 307 條、隱藏檔 796 條。
- 參考解**單一測試檔**的 wall（none 後端，4 個 worker 並行）：中位數 0.49s、
  p90 1.2s、p95 1.9s、p99 8.4s、最大 15.1s（`bcb_17`）。超過閘門預設 10 秒的只有 `bcb_17`。
  退化樁最慢 1.2s。⇒ **建議 `VACANT_TEST_TIMEOUT=120`**（＝量具實際用的值；
  最慢那題有 8 倍餘裕）。
- 用到的第三方函式庫（可用題）：pandas 59、matplotlib 49、numpy 47、sklearn 16、scipy 11、
  requests 10、seaborn 8、bs4 6、nltk 3，其餘都是 1–2 題。只用標準函式庫的題有 36 題。

**會影響實驗公平性的東西**：

1. **測試會寫進工作區（cwd＝`HOME`＝工作區）**：51 題的 matplotlib 會把字型快取寫到
   `.cache/matplotlib/fontlist-v330.json`；`bcb_199`、`bcb_424` 會留下 `df_contents.txt`，
   `bcb_287` 會留下 `test_output.json`。launcher 是在**凍結的快照**上跑驗收，這一點不受影響；
   但 agent 自己跑 `sh run_tests.sh` 時，這些檔案會出現在它的工作區。
2. **寫死 `/tmp` 路徑**：`bcb_785` 用 `/tmp/archive`。none 後端的 `/tmp` 是整台機器共用的，
   同一題兩格同時跑可能互撞。每一格包在自己的 bwrap（私有 tmpfs `/tmp`）裡就沒這個問題。
3. **有網路的題（測試有 mock）**：`requests`／`urllib`／`smtplib`／`ftplib`／`socket` 相關的題，
   上游測試都是 mock，離線也過。但 agent 寫的解如果真的去連網，none 後端底下會真的連出去。
4. **慢題**：`bcb_17` 單檔 15s，`bcb_99` 8s，`bcb_857` 5s，`bcb_324` 4s。其餘都在 2.2s 以內。
5. **Python 3.12 與新版函式庫**：題目裡如果寫「用 X 版的行為」，agent 在這裡照做可能會失敗。
   參考解全過只證明參考解相容。
6. **agent 那一側也要用這個 venv**：`sh run_tests.sh` 用的是 PATH 上的 `python3`。
   agent 的 shell 找不到 venv 的話，可見檢查在 import pandas 那一步就會失敗。
   這件事會讓兩臂都退化成「看不到可見檢查結果」，但兩臂受的影響不一定相同。

## 八、誠實邊界（不准省略）

1. **可見測試是單邊的**。「參考解全過＋樁被擋」只保證擋得住 `return None`，
   **不等於**可見測試涵蓋了真正的需求。一份過了可見、卻在隱藏失敗的解，正是這個題庫
   要讓閘門「看不到」的東西。這是設計本身，不是缺陷，但數字要照這個意思讀。
2. **切法是我們定的，不是官方的**。上游沒有可見／隱藏之分，⌈n/3⌉＋字典序是事前寫死的
   規則，不是隨機抽樣。換一種切法，可見那一側的強度就不一樣，閘門能擋下多少也跟著變。
   這個題庫量到的「閘門擋下幾件」，綁在這個切法上。
3. **排除用到網路／缺函式庫的題，會讓子集偏向某些函式庫**：被排除的題集中在
   tensorflow／keras、需要外部服務的題（590／1012），以及跟新版 Python／matplotlib
   不相容的題（101／227）。所以剩下的子集偏向
   pandas／matplotlib／numpy 這一類「本機就算得完」的工作，**不能代表 BigCodeBench-Hard
   整體**，也不能拿去跟官方排行榜的 pass@1 相比（環境版本也不同，見第五節）。
4. **版本不是官方版本**。numpy／pandas／matplotlib／scipy 都比官方新一個大版本系列。
   參考解在這裡全過，只代表參考解相容；上游某些測試對浮點數或繪圖細節很敏感，
   模型寫的解如果依賴舊版行為，可能在這裡失敗、在官方環境通過（反過來也有可能）。
5. **可見檔可能帶出一點隱藏的線索**：非 test 的 helper 方法、`setUp`、模組層級程式碼
   是整份保留的。如果某個 helper 只有隱藏方法會用到，它還是會出現在可見檔裡。
   隱藏方法**本身的內容**不會出現在工作區。
6. **`none` 後端沒有隔離**：驗收時測試直接跑在主機上，cwd＝工作區，`HOME`＝工作區，
   `/tmp` 是整台機器共用的，網路也是通的。見第七節列出的「會寫檔」「固定 /tmp 路徑」
   那幾題。

## 九、檔案在哪

- vacant-dev：`/var/tmp/vacant_piext_20260924/bcb/bank/{templates,hidden}`、
  `bank/bank_manifest.json`（＋`.sha256`）、`bank/render_manifest.json`；
  排除題的兩棵樹放在 `bcb/excluded/`；venv 在 `bcb/venv`（1.3GB）。
- repo：`ops/vacantrun/bcb_hard_bank_20260924/bank/`，是上面那一份的逐位元組副本
  （`shasum -a 256 -c bank_manifest.sha256` 會過）。
- 目錄名是 `bcb_<N>`，N＝BigCodeBench 題號（`bcb_13` ↔ `BigCodeBench/13`）。
- `requirements_venv_freeze.txt`＝venv 的 `pip freeze`；`setup_venv.sh`＝實際下過的安裝指令。

## 十、重跑

```bash
cd /var/tmp/vacant_piext_20260924/bcb
venv/bin/python src/build_bank.py --parquet raw/bcb_hard_v0.1.4.parquet --out bank   # 重新渲染（確定性）
venv/bin/python src/gauge_bank.py --root "$PWD" --workers 4 --timeout-s 120 --prune   # 量具＋把排除題搬到 excluded/
venv/bin/python src/build_bank.py --parquet raw/bcb_hard_v0.1.4.parquet --out bank --check  # 驗沒漂（prune 之後只驗可用題）
```

`src/vrun/{acceptance,sandbox}.py` 是這個分支上 `vacant_network/vrun/` 那兩支的逐位元組
副本，manifest 有記 sha256。
