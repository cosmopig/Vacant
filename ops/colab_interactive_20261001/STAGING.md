# i1001 題池 staging（資料側）

> 這一份只講**題目怎麼備**：題池從哪來、怎麼重算、怎麼證明它跟 C5 跑的是同一批、四個題庫的計分器量具量到什麼、
> 哪些題庫能跑 K 組。Colab 上怎麼跑（互動式 pi、驅動、A／C／R／K 臂）不在這一份。
> **零模型呼叫、不碰 Colab、不碰金鑰。** 題目內容（敘述、隱藏測資、參考解、staged 目錄）**不進 repo**，放在 scratchpad 的
> `i1001/staged/`；repo 裡只有工具與這份說明。

## 一、來源（全部取自 `origin/feat/colab-campaign-20260927`，用 `git archive` 取出，沒有 checkout）

| 內容 | 路徑（該分支上） | 備註 |
|---|---|---|
| LCB v1／v2／v3 的 `templates/`＋`hidden/` | `ops/vacantrun/colab_banks_20260927/lcb_v{1,2,3}/` | 本來就在版控（題庫檔 `ops/gain/data/lcb_bank_v*.jsonl` 已進版控；R534 同一個前例） |
| dabench／databench／polyglot_py | `ops/vacantrun/task_banks_20260927/<bank>/{templates,hidden,reference}` | `reference/` 只給量具（含參考解與答案），**不進 staged** |
| C5 的逐題結果 | `ops/colab_campaign_20260927/results_c5/cells.jsonl`、`launch_record_c5.json` | 1,840 格 |
| C5 的原始紀錄 | `scratchpad/colab_raw/`（43 個 tar.xz） | 只解出 LCB 各格的 `app_final/solution.py`＋`score.json`＋`meta.json`（792 格，16 MB），**沒有讀 auth.json 等金鑰檔** |

MBPP+／HumanEval+ 不在池裡（官方 EvalPlus 包在本容器沒有；HumanEval+ 本來就在天花板）。

## 二、題池（`build_pool_lcb.py` → `pool_lcb.json`）

- C5 的 A 組沒過的 LCB 題**全部** 93 題（v1 27、v2 30、v3 36）＋ A 組過了的 LCB 題裡固定種子 **20261001** 抽 40 題
  （v1 5、v2 16、v3 19；回歸／傷害對照）＝ **133 題**。
  抽法寫死：A 過的 (bank, unit) 依字串排序 → `random.Random(20261001).sample(list, 40)` → 排序。
- 93 題 A 失敗的拆解（C5 的描述欄位）：撞 1800 秒且沒交 29、撞時限但有交 28、沒交但沒撞時限 5、可見全過隱藏沒過（假完成）23、其他可見沒過 8。
- C5 沒有 void 格（`launch_record`／report 一致），池裡沒有因 void 排除的題。
- 池裡有 5 題在 C5 的計分裡**撞到隱藏檔 60 秒整檔時限**（`lcb_v1-lcb_3686`、`3692`、`3699`、`lcb_v3-lcb_3000`、`3244`，全是 A 失敗題）：
  這幾題的判決受機器速度影響（見第四節 3），`pool_lcb.json` 的 `c5.<arm>.suite_timed_out` 標出。

## 三、staged 樹（`stage_pool.py`）

格式＝`cell.sh` 吃的：每題 `instruction.txt`（C5 同一句）、`workspace/`、`hidden/`、`scorer.py`。
- LCB：`stage_code_bank.py`（C5 同一支，逐字複製）＋`scorers/code_suite.py`（sha256 `298396bc…`，與 C5 發射紀錄一致）。
- 任務題庫：`stage_task_bank.py`＋`scorers/{dabench,databench,polyglot_py}.py`（第二批的，逐字複製）。
- **與 C5 逐位元組相同的證明**：發射紀錄釘的 `staged_tree_sha256`（`launch_batch.sh` 的 `tree()`）是整個題庫一個值。
  `stage_pool.py --c5-launch-record` 把三個 LCB 題庫**整庫**重新 staged 到暫存、用同一個 `tree()` 算，
  三個都**逐一相同**（v1 `c1ff347f…`、v2 `f5294430…`、v3 `73004ec4…`；89／118／189 題），再刪掉暫存。
  整庫相同 ⇒ 池裡每一題的目錄與 C5 跑的相同；MANIFEST 另記每題自己的 `tree_sha256`。
  （`stage_code_bank.py` 的 `--manifest` 旗標對 dict 形狀的 manifest 會選到 0 題，**不要用**；C5 當時也沒用。）
- 任務題庫**全部題**都 staged（dabench 30、databench 30、polyglot_py 34）；篩選抽樣（SPEC：A 組只跑 10 題，≥9/10 過就丟掉整個題庫）
  `random.Random(f"i1001-{seed}-{bank}").sample(排序後的 id, 10)`，寫在 MANIFEST 的 `screen_sample`。抽到的分層：dabench easy 3／medium 3／hard 4；databench list[category] 3、boolean 2、list[number] 2、number 2、category 1；
  polyglot 10 題（`pg_affine_cipher`、`beer_song`、`connect`、`dot_dsl`、`food_chain`、`phone_number`、`pov`、`react`、`sgf_parsing`、`wordy`）。
  ⚠ databench 的 boolean 有 50% 猜中率，五個型別要分開看；polyglot 可能落在地板（README §七-1）。
- 洩漏掃描（`stage_pool.leak_scan`，有負控制：故意放進去會被抓）：工作區沒有 hidden／reference／example／expected／solution 之類的檔名；
  LCB「只在隱藏裡的 case」的 `args` 行不出現在工作區任何檔；dabench 的 `@名[答案]` 不在 goal／contract；databench 非 boolean 的答案文字不在 goal／contract
  （boolean 的 True／False 是 contract 本來就寫的）；polyglot 的工作區沒有解答檔。0 個違規。
  ⚠ 這不是「資料檔裡找不到答案」的證明：DABench／DataBench 的答案是算出來的，公開上游 repo／HF 上有答案，**agent 若有外網就查得到**；
  polyglot 的 `example.py` 在公開 repo 裡。這是汙染面，沒有擋。

## 四、量具（零模型呼叫；本機 Python 3.11.15、Linux；VM 上要再跑一次）

### 1. LCB（`verify_lcb_scorer.py`，對 staged 的計分器）
跑兩次：整庫 396 題（`_fullcheck`，與 C5 樹逐位元組相同）與 staged 池 133 題。
| | 整庫 396 題 | staged 池 133 題 |
|---|---|---|
| 負控制 `return None` 樁 → `pass:false` | 396／396 | 133／133 |
| 負控制沒交 → `pass:false`（有 `note`） | 396／396 | 133／133 |
| 正控制：repo 既有手寫探針解 → `pass:true`（v1／v2 12 題＋v3 12 題；**其餘 LCB 題沒有參考解**，C5 時就是這樣） | 24／24 | 7／7（池裡只有這 7 題有探針解） |
| 重算 C5：歸檔 `app_final/solution.py`（沒交＝沒檔）餵進同一份計分器、與歸檔 `score.json` 逐欄比 | 792 格中 785 格完全一致 | 266 格中 264 格完全一致；**`pass` 欄 266／266 一致** |
- 整庫 7 格不一致、池裡 2 格不一致，**全部是隱藏檔 60 秒整檔時限**：`lcb_v1-lcb_3699`（A、C）、`lcb_v2-lcb_3686`（A、C）、
  `lcb_v3-lcb_2849`（C）、`lcb_v3-lcb_3442`（A）、`lcb_v3-lcb_3517`（C）。這些解本身很慢（O(n³) 之類），在這台 4 核機器上整檔要 80–190 秒。
  整庫那次 4 個一起跑（比 G4 忙）、池那次 2 個一起跑，所以池裡只剩 `lcb_3699` 兩格差在「逾時前跑到第幾條」（歸檔 6／7、17／18，這裡 3／4；`pass` 都是 false）。
  單獨跑、時限放到 600 秒（`verify_lcb_mismatch_rerun.json`）：7 格裡 5 格的 `pass` 與歸檔相同；`lcb_3699` 兩格反過來——**歸檔在 G4 上逾時判不過，
  這裡 600 秒內（177–193 秒）全過**，也就是解是對的、只是慢。
  ⇒ 結論：計分器邏輯重現得了；**少數慢解的判決取決於機器速度與負載**，是計分器既有的性質（C5 的 `SUITE_TIMEOUT_S=60`），
  不是這一批新增的偏差。互動批次要用同一個 60 秒才跟 C5 可比；這 5＋幾題的 pass／fail 讀的時候要帶這一句。

### 2. 任務題庫（`verify_task_banks.py`，對 staged 樹裡的 `scorer.py`＋`hidden/`）
| 題庫 | 題數 | 正控制 | 負控制（沒交／空檔／錯答案／stub） |
|---|---:|---|---|
| dabench | 30 | 60／60（標準答案原文 30＋題庫參考解實際輸出 30） | 120／120 |
| databench | 30 | 60／60（同上） | 120／120 |
| polyglot_py | 34 | 68／68（官方參考解 34＋參考解配被改壞的工作區測試檔 34，計分只用原件） | 136／136（stub＝contract 裡的官方骨架） |
計分器每格都有輸出 JSON；0 個失敗。databench 的計分器用 pandas＋numpy：本機是 pandas 3.0.6，**Colab 的系統 python 3.13 要實際 import 一次**
（selfcheck 的一行：`python3 -c "import pandas, numpy"`；dabench／databench 的 agent 端還要 scipy）。

### 3. K 組（`native_acceptance_bridge.py conform`）能不能跑
- **LCB：能。** 池裡 133 題的 `workspace/tests_visible/` 全部通過橋的 `_suite_files()` 檢查（頂層 `test_*.py`、`check_*` 無必要參數；`sh run_tests.sh` 就是在跑它）。
- **dabench／databench：沒有**可見的 `check_*` 驗收（答案只在 hidden；工作區只有 goal／contract／資料）。K 不跑。
- **polyglot_py：沒有。** 工作區有官方測試檔 `<slug>_test.py`，但是 `unittest.TestCase` 形狀、檔名也不是 `test_*.py`，橋會拒收
  （要有頂層 `check_*` 或 `main`）。要跑 K 得另外包一層 `tests_visible/test_visible.py`（把原件測試檔用 unittest 跑起來、失敗就 assert）——
  **這是新的設計、沒有做、沒有驗**，而且會改變工作區的樣子；預設不做。⇒ **K 只跑 LCB。**

## 五、重做

```bash
B=origin/feat/colab-campaign-20260927
git archive $B ops/vacantrun/colab_banks_20260927 ops/vacantrun/task_banks_20260927 | tar -x -C <src>
python3 build_pool_lcb.py --cells <results_c5/cells.jsonl> --out pool_lcb.json --c5x <解開的 c5 cells 根>
python3 stage_pool.py --pool pool_lcb.json --lcb-src <src>/ops/vacantrun/colab_banks_20260927 \
    --task-src <src>/ops/vacantrun/task_banks_20260927 --c5-launch-record <results_c5/launch_record_c5.json> \
    --out <staged> --source-ref "$B@$(git rev-parse $B)" --verify <verify_*.json …>
python3 verify_lcb_scorer.py --staged <staged> --ids-from pool_lcb.json --manifests <src>/…/colab_banks_20260927 \
    --c5x <c5x> --probe-v12 ops/gain/data/lcb_probe_solutions.json --probe-v3 ops/gain/data/lcb_v3_probe_solutions.json --out verify_lcb_pool.json
python3 verify_task_banks.py --staged <staged> --reference-root <src>/ops/vacantrun/task_banks_20260927 --out verify_task_banks.json
```
`MANIFEST.json`（在 staged 根）：每題的 tree sha256／檔數／位元組／角色、每個題庫的子集雜湊、工具 sha256、C5 樹對照、量具輸出的 sha256 與摘要。
`tasks_index.json`：`{bank,id,dir,role}`，`dir` 是 VM 上的 `/srv/eval/staged/<bank>/<id>`。
