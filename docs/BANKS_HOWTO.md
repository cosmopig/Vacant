# 五個題組的規格與自己重跑的方法

這份文件承重什麼：讓**不是我們的人**能在自己的機器上，把 G 系列實驗（R460／R529／R532）
用的五個題組逐字重建、驗證釘值、並自己跑一塊出來對帳。
所有數字都可以在自己的 checkout 上算出來，不必相信我們的話。

對應的實驗紀錄在 `runs/INDEX.md` §七（題庫）與各 `decisions/DECISION_*.md`。

---

## 一、五個題組一覽

| 我們叫它 | `--bank` 參數 | 來源 | 題數 | 實際用幾題 | 進版控？ |
|---|---|---|---:|---:|---|
| LCB v2 | `lcb2` | LiveCodeBench v2 | 120 | 120 | **是** |
| LCB v3 medium | `lcb3 --bank-filter difficulty=medium` | LiveCodeBench v3 | 189 | 135 | **是** |
| LCB v3 hard | `lcb3 --bank-filter difficulty=hard` | 同上 | 189 | 54 | **是** |
| HumanEval+ | `humanevalplus` | EvalPlus v0.1.10 | 164 | **156** | 否（授權） |
| MBPP+ | `evalplus` | EvalPlus v0.2.0 | 378 | 371 | 否（授權） |

合計 **836 題**。`lcb3` 的 medium 135 ＋ hard 54 ＝ 189，兩個 filter 把同一個檔切開，不重疊。

⚠ **`--bank evalplus` 指的是 MBPP+，不是「EvalPlus 全部」**。這個名字是歷史包袱，
HumanEval+ 走的是另一個名字 `humanevalplus`。看 `--bank` 參數時不要望文生義。

---

## 二、路徑與釘值（自己驗）

### 2-1　進版控的兩個（clone 下來就有）

```
ops/gain/data/lcb_bank_v2.jsonl    120 行   sha256 b98f027213e2469a…
ops/gain/data/lcb_bank_v3.jsonl    189 行   sha256 bd3dffebb1b16bc7…
```

自己驗：

```bash
wc -l ops/gain/data/lcb_bank_v2.jsonl ops/gain/data/lcb_bank_v3.jsonl
shasum -a 256 ops/gain/data/lcb_bank_v*.jsonl     # Linux 用 sha256sum
```

### 2-2　沒進版控的兩個（要自己去官方抓）

授權不允許我們轉散布，所以 repo 裡**一個位元組都沒有**，只有釘值。

```
.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz         sha256 af43697e8791c4c1…
.vacant-private/evalplus/HumanEvalPlus-v0.1.10.jsonl.gz   sha256 272720b90ac37550…
```

釘值的單一真相在 `vacant_network/codebench.py`：
`EVALPLUS_MBPP_PLUS_SHA256`（第 339 行）與 `EVALPLUS_HUMANEVAL_PLUS_SHA256`（第 735 行）。
loader 是 **fail-closed** 的：sha256 不符就直接拋例外，不會默默用別的版本跑下去
（負向測試在 `tests/test_x1_evalplus.py`）。

取得方式：從 EvalPlus 官方 release 下載對應版本，放到上面那兩個路徑，然後

```bash
mkdir -p .vacant-private/evalplus
# 放好檔案後驗釘值
shasum -a 256 .vacant-private/evalplus/*.jsonl.gz
python3 -c "from vacant_network.codebench import EVALPLUS_MBPP_PLUS_SHA256 as a, EVALPLUS_HUMANEVAL_PLUS_SHA256 as b; print(a); print(b)"
```

兩邊逐字相同才算數。`.gitignore` 擋住整個 `.vacant-private/`，不會不小心提交上去。

---

## 三、兩個會讓數字對不起來的地方（先看這節，不然你算出來的分母跟我們不一樣）

### 3-1　HumanEval+ 的分母是 **156 不是 164**

8 題被沙箱信封排除，名單寫死在 `ops/gain/gain_run.py::GAIN_HUMANEVAL_EXCLUSIONS`
（約第 83 行起），逐題理由：

| 題 | 為什麼排除 |
|---|---|
| `HumanEval/39` | 參考解需要 `random`（不在 import 白名單） |
| `HumanEval/160` | 參考解需要 `eval()`（信封禁止） |
| `HumanEval/162` | 參考解需要 `hashlib`（不在 import 白名單） |
| `HumanEval/83` | `10**(n-1)` 規模的整數超出 128 MiB 信封 |
| `HumanEval/100` | 等差級數堆疊超出 128 MiB 信封 |
| `HumanEval/130` | tribonacci 表超出 128 MiB 信封 |
| `HumanEval/139` | 階乘乘積超出 128 MiB 信封 |
| `HumanEval/15` | 參考解要吃掉 10 秒預算裡的 5.8–7.6 秒（沒有 2 倍餘裕） |

**排除是在看到任何結果之前定的**，但它仍然是本專題自訂的門檻，不是 EvalPlus 官方的。
引用 HumanEval+ 的數字時要一起講這件事。

MBPP+ 是 378 題、實際用 371，差額同理由自己跑 `--gauge-scope bank` 會列出來。

### 3-2　LCB v3 **不能**宣稱是訓練截止之後的題

v3 的 `contest_date` 全部不晚於 **2024-08-10**。它是刻意造出來的**樣本外複製集**
（v2 ∩ v3 ＝ 0 題），但污染風險比 v1／v2 高。這句警語同時寫在
`vacant_network/codebench.py` 與 R460 C3 判定裡。

已知壞題：v2 有 `lcb_3613`、`lcb_3763` 兩題（v3 無）。白名單在
`ops/gain/check_bank_precision.py::KNOWN_BAD`——**它是白名單不是消音器**，
冒出新的壞題照樣 FAIL。

---

## 四、自己跑一塊

### 4-1　先確認題庫本身是好的（零模型呼叫）

量具會對整個題庫驗兩個方向：**參考解要過、已知壞樁要被擋**。任一方向沒過就拒跑。

```bash
# 位置參數：<bank> <seed> [n]，不是旗標
python3 ops/gain/check_bank_precision.py lcb2 g-r440-lcb2
```

它印**三個**數字，不要只看一個（理由在該檔 docstring 與 R440T §二）：
`decisive_bad`（有參考解、實跑判錯＝確定壞）、`screened`（沒參考解、篩出可疑
＝線索不是判決，要人眼確認）、`unverifiable`（沒參考解、看起來正常＝不知道，
別當成好的）。LCB 沒有官方參考解，手寫的只有 12 題，所以量具覆蓋率本來就低。

### 4-2　跑一塊三臂

需要一個 OpenAI 相容端點（我們用 LM Studio）。

```bash
export VACANT_GAIN_API=http://<你的端點>:1234/v1/chat/completions   # ← 要完整路徑
python3 ops/gain/gain_run.py \
  --out runs/my_test --n 20 --offset 0 \
  --seed my-seed --arms OFF,CONFORM,HMIX \
  --bank humanevalplus \
  --record-bank-field --models <你的模型 id> \
  --reasoning-effort none \
  --probe-sample 0 --gauge-scope bank \
  --request-timeout-s 900 --review-timeout-s 380 --retries 4
```

⚠ **端點環境變數是 `VACANT_GAIN_API`，不是 `VACANT_ENDPOINT`**。
後者只管 `vacant_network/substrate.py`；`ops/gain/brain_cline.py:134` 讀的是前者，
沒設會去打 `api.cline.bot` 雲端（我們 2026-09-17 為此誤發兩次）。
值要是**完整的** `/v1/chat/completions`，不是基底 URL。

⚠ 我們的正式 run 多一個 `--decision <預註冊檔>` 參數：那是預註冊閘門，
會去 DECISION 檔裡比對逐字的 `R532_BLOCK:` 註冊行，少一格就發不出去。
你自己測不需要它。

### 4-3　三個臂是什麼

| 臂 | 做什麼 | 呼叫數 |
|---|---|---|
| `OFF` | 單發，寫完就交 | 每題 1 |
| `CONFORM` | 同預算重抽最多 5 份，每份跑**可見**驗收，挑過的交；都沒過就拒交 | 每題 1–5 |
| `HMIX` | 把可見驗收的失敗原文貼回去讓它改（回饋迴圈） | 每題 1–5 |

### 4-4　讀結果

```bash
python3 - <<'PY'
import json, collections
rows = [json.loads(l) for l in open("runs/my_test/rows.jsonl")]
agg = collections.defaultdict(lambda: [0, 0, 0])
for r in rows:
    a = r["arm"]; agg[a][0] += 1
    if r.get("accepted"):     agg[a][1] += 1     # 有沒有交付
    if r.get("meets_demand"): agg[a][2] += 1     # 隱藏測資有沒有過（真正的分子）
for a in ("OFF", "CONFORM", "HMIX"):
    n, d, p = agg[a]
    print("%-8s 題 %d  交付 %d  隱藏通過 %d (%.1f%%)" % (a, n, d, p, 100 * p / max(n, 1)))
PY
```

**欄位別搞錯**：`meets_demand` 才是隱藏測資的判定（真正的分子）；
`visible_ok` 是可見驗收，那是 harness **允許**看的東西；`accepted` 是有沒有交付。

---

## 五、V／GT 紅線（這條是整個實驗的地基）

harness **只准**用 `visible_check`；`hidden_check` 只用來算分，任何路徑都不得回饋給模型。
違反這條，CONFORM 與 H-MIX 的數字就等於偷看答案。

自己查：

```bash
# --run 是必填；--bank 要配對該 run 自己的題庫，否則 task_id 全部「不認得」
# 而 fail-closed 判 VIOLATION（那是工具在保護你，不是真的違規）
python3 ops/gain/harness_vgt_audit.py --run runs/<你的 run> --bank humanevalplus --scope v2
```

這是**動態**稽核（實際跑一遍、在模型看得到的文本裡搜隱藏測資的指紋），不是 grep。
輸出看三個數字：`needles_checked`（搜了幾個指紋，0 代表根本沒驗到）、
`unknown_task_ids`（題庫配錯就會塞滿這個）、`violations`。
`verdict` 要是 `CLEAN`，而且 `needles_checked` 不能是 0。

---

## 六、想完整重現我們某一輪

`runs/INDEX.md` 列了 598 個項目，標明哪些是證據（98 個 `real_run`）、
哪些是冒煙／中止、哪 136 個 `_analysis_*` 是衍生物**不可當原始資料**。
先讀它再引用任何 run。

```bash
python3 ops/gain/build_runs_index.py --check    # 驗索引沒漂掉

收據鏈（每個 run 每條臂一條 Ed25519 hash chain）自己驗：

```bash
python3 ops/gain/replay/verify_run_receipts.py --selftest          # 先過負控制
python3 ops/gain/replay/verify_run_receipts.py --glob 'runs/g_r532_*'
```

`--selftest` 要先 PASS 才有意義——它證明這支驗證器抓得到被竄改的鏈。
```

每個 run 的 `summary.json` 裡有 `seed`／`bank`／`offset`／`n`／`runner_git`，
照著填回 §4-2 的指令就是同一塊。**同 seed ＋ 同 bank ＋ 同 offset
⇒ persona 指派逐格相同**，與模型是哪一顆無關（離線可驗：
`python3 ops/gain/r532/check_persona_invariant.py`）。
