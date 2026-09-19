# R530 開放目標題庫 × `vacant run` 收件口

## ⚠⚠ 這不是預註冊實驗——先讀這一節

**沒有預註冊 ⇒ 這裡的數字不可以當假說檢定。**

能說的只有描述性的那一句：**「在這 20 題上，X 是 a/b」。**

**禁止**：

* 做任何統計檢定（p 值、信賴區間、等價檢定、檢定力）；
* 與 **R535** 或 **R530 原始結果**合併；
* 寫「複製」「效果消失」「等價」「一致」「不顯著」這類把兩批資料接起來的字。

本目錄借用了 `ops/gain/r535/run_r535.py` 的量測函式（`measure_m7_*`／`measure_f6`／
`measure_f3`）。**借的是尺，不是結果。** 用同一把尺是為了量測本身可比；
量出來的數字仍然不可以合併。

### ⚠ 還有一條：`M7_file` 的 0 **跨 agent 一致**，但**為什麼是 0** 不一致

> **這一節被改寫過一次，改寫本身才是重點。** 初版寫的是「`M7_file` 低是 pi 的
> 怪癖，OpenCode 與 Claude Code 都是 50%」——**那是讀錯的結論**，來源是把
> Stage C 的 `by_agent`（**RF＋RP 合併**）當成分層數字。RP 臂的回饋走 argv，
> `M7_file` 幾乎恆真；把它和 RF 平均起來就會得到一個誰都不是的 ~50%，
> 而且**方向剛好相反**。判讀一定要看 **`by_agent_arm`**。

2026-09-19 Stage C 收官 40/40 的分層數字：

| 量 | pi | Claude Code | OpenCode | 合計 |
|---|---|---|---|---|
| **RF 臂 `M7_file`** | — | — | — | **0/19**（rule-of-three 上界 **0.158**） |
| `M7_name`（看見檔名） | 46/46 | 10/10 | **0/9** | — |

⇒ **「RF 臂的回饋檔沒有進到 wire」這件事本身不是 pi 的怪癖**，三個 agent 都是 0。
⇒ **但機制是兩種**：pi 與 Claude Code 是「**看見了檔名，沒有去讀**」；
OpenCode 是「**連檔名都沒有進到輸入**」。那是兩個不同的失敗，修法也不同。

本輪用的 agent 是 **pi**。所以本目錄的措辭規則是：

* ✅ 「在這 20 題上、**用 pi**，RF 臂的 `M7_file` 是 a/b」
* ✅ 跨 agent 講的時候，**`M7_file` 一定要連 `M7_name` 一起講**
  ——只講 `M7_file=0` 會把「看見沒讀」與「根本沒看見」壓成同一句話。
* ❌ 「回饋檔沒有被讀，所以檔案通道無效」——`M7_name` 分得開的東西不要壓扁。

（附身矩陣的現況：**4 個 agent 有真模型證據**——pi／OpenCode／Claude Code／
**Codex（API key，2026-09-19 升 L-real）**。`docs/AGENT_COMPAT.md` 是單一真相。）

---

## 它為什麼存在（三個工程問題，不是科學主張）

`ops/gain/r530/bank/` 有 20 題開放目標題（`ow_01_csvjson` … `ow_20_slugify`），
參考解 16–200 行、可見驗收 2–4 條、隱藏驗收 6–16 條。它**從來沒有在 `vacant run`
的收件口下跑過**——R530 當初用的是自己的 harness（`ops/gain/r530/run_r530.py`）。

1. **重量級題庫上收件口撐不撐得住。** R535 全是秒級微型題，那是舒適區。
2. **`M7_file` 在更長、更難的任務上還是 ~0 嗎。**
3. **`--test-timeout` 要多少才不會製造假逾時。** r530 凍結的常數是 10 秒、
   R535 的發射腳本用 30 秒，**兩個都不是在這個題庫上量的**。

---

## 設計（20 × 2 ＝ 40 格）

| 臂 | 旗標 | 承重 |
|---|---|---|
| `RF` | `--retry revise --max-attempts 3 --feedback-into file` | 回饋走工作區檔案 |
| `RP` | `--retry revise --max-attempts 3 --feedback-into prompt` | 回饋走 argv 尾端 |

* **20 題全跑**——挑題是一個選擇點，這一輪不開那個選擇點。
* agent ＝ **pi**（三個 L-real 裡最便宜、最熟的那個）；
  模型 `gemma-4-12b-it-qat`、`reasoning_effort: "none"`。
* prompt 兩臂**逐字相同**，KS-1 乾淨（鐵律 1）：
  `Read goal.md and contract.md and do what they say. Use your tools to write the files.`
  （與 R535 那一句不同只因為這個題庫的樣板是兩個檔不是一個 `TASK.md`。）
* 發射順序：**同一題的兩格排在相鄰兩列**，`--shard k:2` ⇒ 兩條流同時在跑
  同一題的兩個臂，後端漂移不會變成臂與臂之間的時間混淆。

### 工作區、`--suite`、V/GT 紅線

R530 的題目結構與 R535 **不同**：`tests_visible/` 是**工作區的一部分**
（`TASK_FORMAT.md` §八-5：可見驗收的輸入與期望值 worker 看得到、跑得到，
還附一支 `run_tests.sh`）。所以：

| 東西 | 在哪 | 誰改得到 |
|---|---|---|
| `goal.md`／`contract.md`／`run_tests.sh`／`tests_visible/` | 工作區 | agent |
| **計分用的可見驗收** | `<out>/suites/<task>/tests_visible/`，**工作區外** | 沒有人 |
| **隱藏驗收** | `ops/gain/r530/hidden/<task>/`，**只在計分那一瞬間**掛進沙箱 | 沒有人 |

兩份可見驗收的 sha256 都逐格落盤（`suite_sha256`／`ws_suite_sha256`）。
不相等 ⇒ agent 動過他工作區裡那一份 ⇒ **那是觀測不是錯誤**，因為計分用的是
工作區外那一份，改了也騙不到閘門。

**隱藏驗收只計分不回饋**：它一個位元組都沒有進過工作區、也沒有進過 `--suite`。

---

## 三支程式

| 支 | 做什麼 | 燒機時嗎 |
|---|---|---|
| `probe_timeout.py` | 拿**參考解**跑一次全部驗收，量單檔牆鐘，`--test-timeout` ＝ 最慢那一檔 × 3 | 否（零模型呼叫） |
| `run_r530vrun.py` | 40 格逐格交給 `vacant/vrun/launcher.py`，逐格落盤 | 是 |
| `score_r530vrun.py` | 隱藏驗收計分＋收官表 | 否（零模型呼叫、可離線重跑） |

```bash
OUT=/var/tmp/vacant_r530vrun
PI=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin/pi
export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH
export VACANT_GAIN_API=http://<host>:1234/v1/chat/completions

python3 ops/gain/r530vrun/probe_timeout.py --out $OUT/probe
for i in 0 1; do
  python3 ops/gain/r530vrun/run_r530vrun.py --out $OUT --shard $i:2 \
    --stream s$i --pi-port 889$i --pi-bin $PI --test-timeout <量到的值> &
done; wait
python3 ops/gain/r530vrun/score_r530vrun.py --out $OUT
```

---

## 紀律（逐條對應人類指令）

* `requests_seen == 0` ⇒ **`infra_void` 不是 0 分**（`accepted` 落 `null`），重試 ×4。
* **load 監看**：每 15 分鐘記一次 `uptime`（`driver_*.jsonl` 的 `uptime` 事件）；
  1 分鐘 load > 8 就**暫停派工**，不是砍 run。那台機器剛從 load 71 救回來。
* 吞吐 4 串封頂，別的 agent 已經在用 ⇒ **最多開 2 串**。
* 牆鐘**印分佈不印均值**。
* 收據：先 `verify_receipts --selftest`（負控制）再驗該跑。
* 口徑用「**可究責性**」不用「信任」。

## 誠實邊界

* `--test-timeout` 是拿**參考解**量的。模型寫出來的解可能更慢 ⇒ 3 倍是工程餘裕
  **不是上界**，逾時格仍然可能出現，出現時是觀測不是 bug。
* `passed/total` 是「過了我們自己寫的幾條」，不是「做對了幾成」
  （`vacant/suitegauge.py` 的單邊保證逐字適用）。
* `hidden_frac` 與 `hidden_frac_delivered` **都不是主指標**——沒有預註冊，
  `score_r530vrun.py` 不指名。

## 結果

見 `RESULTS.md`（同目錄）。
