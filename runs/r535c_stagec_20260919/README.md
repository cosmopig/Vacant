# R535 Stage C 歸檔：「檔案從不被讀」是不是 pi 專屬的？

> ## ⚠⚠ 這**不是**預註冊實驗，所以判準更嚴
>
> 預註冊 `decisions/DECISION_20260919_R535_RETRY_CHANNEL_PREREG.md` **L-6** 逐字：
>
> > **Stage C（第二基質 10 題、只跑 RF／RP，看「file 從不被讀」是不是 pi 專屬）
> > ＝選配、不進預註冊。** S1／S2 歸檔後才准動；接不上就丟，不補。
>
> ⇒ 本目錄的數字**只能描述**：「在這 10 題上，agent X 的 `M7_file` 是 a/b」。
>
> **禁止**：拿它做任何統計檢定、跟 S1／S2 合併、說「效果複製了」或「沒複製」。
> 這句話跟著每一份產物走（`stagec_meta.json` 與每一個 `cell.json` 的 `not_a_test` 欄位）。

- 跑的日期 2026-09-19｜機器 vacant-dev（`100.124.254.83`）｜上游 1003（`100.119.113.56:1234`）
- 模型 `gemma-4-12b-it-qat`｜`reasoning_effort: "none"`（注入，見下方「殘餘 2」）
- agent：OpenCode **1.18.31**（設定路線）／Claude Code **2.1.278**（零接線）
- 發射 worktree `9eeb1d9`｜`bank_manifest` `5e727b2e…c0794`｜`plan_sha256` `bb489c55…95dc6`
- 驅動與量具：[`ops/gain/r535c/`](../../ops/gain/r535c/)
- S1／S2 的正典歸檔在 [`runs/r535_retry_channel_20260918/`](../r535_retry_channel_20260918/)

---

## 〇、`report.json` 的 `by_agent` **是兩臂合併的，不可單獨引用**

2026-09-19 已經被讀錯過一次，所以放在最前面。合併之後會出現一個**看起來像矛盾
但不是**的形狀：**OpenCode 的 `M7_name` 是 0%、`M7_file` 卻是 50%**
（「檔名從沒進 wire，內容卻讀到了？」）。

**不是量具盲點。** 兩個數字各由一個臂主導，而那兩個值都是**設計上的必然**：

| | RP 臂為什麼是那個值 | 逐格可查的證據 |
|---|---|---|
| `M7_file = 9/9`、`10/10` | `--feedback-into prompt` 把回饋接在 **argv 尾端** ⇒ 一定進得了輸入。**這是本輪的正控制** | `cell.json` 的 `attempts[2].feedback_in_prompt_bytes = 586`（OpenCode）／`584`（Claude Code） |
| `M7_name = 0/9`、`0/10` | 同一條管道**不把 `VACANT_FEEDBACK.md` 寫進工作區** ⇒ 那個檔根本不存在，檔名當然不會出現 | 凍結快照：`cells/*__RF/run/_frozen_RUN-ON_a2/` 有 `VACANT_FEEDBACK.md`；`cells/*__RP/run/_frozen_RUN-ON_a2/` **沒有** |

⇒ **要判讀一律看逐臂那張表**（下一節，或 `report.json` 的 `by_agent_arm`）。
`by_agent` 只拿來看 n 與健康檢查。
在 `RF`（唯一有那個檔存在的臂）裡，OpenCode 是 `M7_name 0/9` **且** `M7_file 0/9`
——兩個都是 0，沒有任何矛盾。

## 一、40 格的 M7 三層（逐 agent、逐臂）

分母是「有第 2 次嘗試、而且 wire 對得起來」的格數；**`null` 不進分母**
（本輪 2 格：`opencode__s1_07_flipwords__{RF,RP}` 第 1 次就過，沒有第 2 次嘗試）。

| agent | 臂 | n | `M7_name` | `M7_file` | `M7_ws` | `M7_ws_solution` | 最終 `accepted` |
|---|---|---:|---|---|---|---|---|
| **OpenCode** | RF | 10 | **0/9** | **0/9** | 9/9 | 0/9 | 1/10 |
| **OpenCode** | RP | 10 | 0/9 †  | 9/9 ‡ | 9/9 | 4/9 | 10/10 |
| **Claude Code** | RF | 10 | **10/10** | **0/10** | 10/10 | 4/10 | 0/10 |
| **Claude Code** | RP | 10 | 0/10 † | 10/10 ‡ | 3/10 | 3/10 | 10/10 |

† **RP 的 `M7_name = 0` 是機制上的必然，不是觀測**：`--feedback-into prompt`
  不把 `VACANT_FEEDBACK.md` 寫進工作區，那個檔根本不存在。
  （pi 的 S1／S2 也是 0/46、0/22 ——跨三個 agent 的同一個機制檢查。）

‡ **RP 的 `M7_file = 100%` 是本輪的正控制**：回饋接在 argv 尾端，一定進得了輸入。
  它證明「特徵字串比對這把尺在這兩條 wire 上都量得到東西」
  ——所以 RF 的 0 不是尺壞了。

### 跟 S1／S2（pi 0.85.1）擺在一起看

⚠ **這張表是並排，不是對照組。** 題不同（Stage C 只有 S1 前 10 題）、n 不同、
agent 不同，**不准相減、不准檢定**。

| 來源 | agent | 臂 | n | `M7_name` | `M7_file` | `M7_ws` | `M7_ws_solution` |
|---|---|---|---:|---|---|---|---|
| R535 S1 | pi 0.85.1 | RF | 50 | 46/46 | **1/46** | 46/46 | 34/46 |
| R535 S2 | pi 0.85.1 | RF | 40 | 22/22 | **0/22** | 22/22 | 14/22 |
| Stage C | OpenCode | RF | 10 | 0/9 | **0/9** | 9/9 | 0/9 |
| Stage C | Claude Code | RF | 10 | 10/10 | **0/10** | 10/10 | 4/10 |

---

## 二、本輪唯一要回答的問題：`M7_file` 跨 agent 一不一致？

**一致。** `RF` 臂第 ≥2 次嘗試裡，回饋**內容**進入模型輸入的格數：

```
OpenCode     0 / 9
Claude Code  0 / 10
             ─────
合計         0 / 19        rule-of-three 上界 3/19 ＝ 0.158
```

19 格 × 每格 2 個第 ≥2 次嘗試 ＝ **38 個逐次檢查，全部 `found: false`**，
沒有一個是「特徵字串不具鑑別力」之類的跳過（`m7_file_by_attempt` 的
`reason` 38 次都是 `null`），**leaky needle 0 個**。

⇒ **「回饋寫進工作區、agent 不去打開它」在 pi 以外的兩個 agent 上同樣量到了。**
那個 0 **不是 pi 的怪癖**。

### 但「為什麼是 0」在三個 agent 上**不是同一件事**

這是本輪最有意思的一格，而它只在 `M7_name` 上看得出來：

| agent | `M7_name`（RF） | 它實際做了什麼（`tools.jsonl` 逐通） |
|---|---|---|
| pi 0.85.1 | 46/46 ＝ **100%** | 看了目錄、檔名進了輸入、**沒打開** |
| Claude Code 2.1.278 | 10/10 ＝ **100%** | `Bash ls -F` → 檔名進了輸入 → `Read TASK.md` → `Write solution.py`，**沒打開** |
| OpenCode 1.18.31 | **0/9 ＝ 0%** | `glob TASK.md` → `read TASK.md` → `write solution.py`，**目錄從頭到尾沒被列過** |

⇒ **pi 與 Claude Code 是「看見了檔名，沒有讀」；OpenCode 是「連檔名都沒進到輸入」。**
兩種形狀導致同一個 `M7_file = 0`，但它們是不同的失效，補法也不會一樣。
**單看 `M7_file` 說不出這件事**——這正是 R535 把 `M7_name` 從 `M7_file` 拆出來的理由
（預註冊 §`measure_m7_name` 的 ⚠）。

### `M7_ws_solution`（讀自己上一份錯碼）跨 agent **不一致**

| agent | RF | RP |
|---|---|---|
| pi（S1／S2） | 34/46、14/22 | 46/46、22/22 |
| OpenCode | **0/9** | 4/9 |
| Claude Code | 4/10 | 3/10 |

`M7_ws_solution` 是「保留工作區」的**實際通道**（`revise` 臂的工作區沒有被重置，
上一份錯碼還躺在那裡）。**OpenCode 在 RF 的 10 格裡一次都沒有讀回它**——
它每一次嘗試都用 `glob`＋`read TASK.md` 重新開始，然後寫出**位元組相同**的錯碼
（`s1_01` 三次 `ws_end_sha256` 都是同一個值）。
pi 在同一個位置是 34/46。**這一格三個 agent 的行為明顯不同。**

---

## 三、⚠ 這個結果**不能**被讀成什麼（比能讀成什麼重要）

1. **不能讀成「效果複製了」或「沒複製」。** L-6 寫死本輪不進預註冊 ⇒ 它沒有
   假說、沒有預先寫死的判準、沒有檢定力計算。`accepted` 那一欄（RF 1/10、0/10
   vs RP 10/10、10/10）**不是效果量**，本輪不對它做任何推論。
2. **不能跟 S1／S2 合併算一個總數。** 題庫是 S1 的**子集**（前 10 題）、
   agent 不同、n 不同。合併會把「選過的 10 題」當成隨機樣本。
3. **`M7_file = 0` 是單邊的。** 它只說明那幾條特徵字串沒出現在 request body 裡，
   **不說明 agent 沒有以任何方式受到那個檔的影響**（例如它 `ls` 看到檔名而
   改變了行為——pi 與 Claude Code 的 `M7_name = 100%` 正好是那個可能性）。
4. **不能讀成「OpenCode 比較差」或「Claude Code 比較好」。** 本輪沒有任何一格
   是為了比較 agent 品質設計的：同一題、同一個 prompt、同一顆模型，
   量的是**通道**不是能力。而且 n=10 題、每格 1 次、沒有重複。
5. **不能讀成「這 10 題有代表性」。** 它們是 S1 的前 10 題，S1 的設計目標就是
   「回饋充分決定修法」。S2（介面已給、坑在別處）本輪**沒跑**。
6. **不能讀成「Claude Code 那 20 格也確認了不思考」。** 只確認到「旗標送出去了」：
   LM Studio 的 `/v1/messages` 在 `usage` 裡不報 `reasoning_tokens`
   ⇒ 那 20 格的回應端是 `unmeasured_rt`，**不是 0**。
7. **不能讀成「OpenCode 不會列目錄」。** 量到的是**這 10 題、這個 prompt 下**
   它沒有列。換 prompt、換題、換模型都可能漂。
8. 沿用 `docs/AGENT_COMPAT.md` §7／§8.4／§9.6 的所有邊界：
   proxy **records，不 verifies**；`vacant run` 單獨只有 L3。
9. 口徑是**可究責性**（讓依賴有根據），不是「信任」。

---

## 四、量具與接線的健康檢查（40 格逐格）

| 檢查 | 結果 |
|---|---|
| `cell_status` | `measured` **40/40**（0 個 `infra_void`、0 個 `driver_bug`） |
| `requests_seen == 0`（＝沒被中介到） | **0 格** |
| `upstreams_defaulted` 非空（＝有東西走公開 API 預設值出網） | **0 格**（兩條路由都釘到本地；Claude Code 的 `/api/hello` 也是） |
| `reasoning_tokens > 0` 的通數 | **0**（OpenAI wire 逐通量到 0；Anthropic wire 量不到，見殘餘 2） |
| shim 注入 | **468 / 468** 通帶 `model` 的請求 |
| `m7_file` 逐次檢查 | 38 次全部 `found: false`，0 次跳過，0 個 leaky needle |
| `agent_timed_out` | 1 次（`claude__s1_02_span__RP` 的某一次嘗試；該格仍 `accepted`。逾時是正常的嘗試結果不 void） |
| `suspect_timeout`（可見結果裡有 timeout case） | **0 格** |

### 殘餘（兩條，都寫在這裡而不是只寫在程式碼裡）

1. **`M7_ws` 的解析器為了 Claude Code 擴充過。** Anthropic Messages 的工具呼叫是
   `content` 裡的 `tool_use` block，r535 原件只認 OpenAI 形狀。擴充只在「怎麼把
   呼叫撈出來」那一步，**分類仍是 r535 那一份**，而且 `--selftest` 有三條負控制
   （認不出來就紅）。`M7_file`／`M7_name` **沒有動**——它們比的是位元組。
2. **`reasoning_effort: "none"` 是注入的，不是 agent 自己送的。**
   兩個 agent 的設定路線裡沒有那個欄位；不補的話 1003 預設會思考
   （實測 `reasoning_tokens` 5 ⇒ 0）。注入層在 wireproxy **之後**
   ⇒ 落盤的 `*.req.bin` 是 agent 的原文，M7 沒有被汙染。
   代價是 Anthropic wire 上驗不到回應端（殘餘寫在上面第 6 條）。

---

## 五、收據驗證（先負控制，再驗該跑）

```
$ python3 -m vacant.vrun.verify_receipts --selftest
selftest: PASS                                   ← 負控制：它抓得到壞鏈

$ python3 -m vacant.vrun.verify_receipts --glob '/var/tmp/vacant_stagec/run/cells/*/run'
run 40　鏈 40　entries 141　驗過 141　失敗 0　壞鏈 0
總判：OK
```

逐鏈明細在 `receipts_verify.json`（每一鏈都有 `chain_ok` 與
`logbook_verify_chain` 兩個欄位，兩者必須一致）。

---

## 六、怎麼從本目錄自己重算（零模型呼叫、零網路）

```bash
# 1. 檔案沒被換過
cd runs/r535c_stagec_20260919 && sha256sum -c SHA256SUMS

# 2. 收據鏈（負控制在前）
python3 -m vacant.vrun.verify_receipts --selftest
python3 -m vacant.vrun.verify_receipts --glob 'runs/r535c_stagec_20260919/cells/*/run'

# 3. 表格從 cell.json 重算
python3 ops/gain/r535c/run_stagec.py --out runs/r535c_stagec_20260919 --report

# 4. M7 三層從 wire 原始位元組重算，跟 cell.json 逐格比（本輪 40/40 OK）
tar xzf runs/r535c_stagec_20260919/wire.tar.gz -C runs/r535c_stagec_20260919
python3 ops/gain/r535c/run_stagec.py --out runs/r535c_stagec_20260919 --rescan
```

**驗不到的**：隱藏套件沒有跑（本輪主軸是 M7 不是 `M1`，`accepted` 只記可見驗收
的結果）；模型那一端重現不了（同一顆模型再跑一次不會逐字相同）。
**這不是「完全可驗證」。**

沒有進 repo 的東西（活工作區、agent console 輸出、launcher stderr）
連同它們的 manifest sha256 記在 `NOT_IN_REPO.json`。
