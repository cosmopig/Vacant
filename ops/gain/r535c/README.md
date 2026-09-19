# Stage C（R535 L-6）——「檔案從不被讀」是不是 pi 專屬的？

> ## ⚠ 先讀這一段：**這不是預註冊實驗**
>
> 預註冊 `decisions/DECISION_20260919_R535_RETRY_CHANNEL_PREREG.md` **L-6** 逐字寫死：
>
> > **Stage C（第二基質 10 題、只跑 RF／RP，看「file 從不被讀」是不是 pi 專屬）
> > ＝選配、不進預註冊。** S1／S2 歸檔後才准動；接不上就丟，不補。
>
> ⇒ **本輪的數字不可以拿來當假說檢定。** 它能說的只有描述性的那一句：
> 「在這 10 題上，agent X 的 `M7_file` 是 a/b」。
>
> **禁止**：拿 Stage C 的數字做任何統計檢定、跟 S1／S2 合併、
> 說「效果複製了」或「沒複製」。收官句只能是描述。

## 為什麼現在才做

L-6 有兩個前提，2026-09-19 兩個都滿足了：

1. **S1／S2 已歸檔**（`runs/r535_retry_channel_20260918/`）。
2. **當初寫這條時只有 pi 一個 agent 到得了真模型**，現在有三個
   （pi／OpenCode／Claude Code，見 `docs/AGENT_COMPAT.md` §8／§9）
   ⇒ 「第二基質」那一格從一個變成兩個，兩個都跑。

## 設計（照 L-6，沒有自己加東西）

| | |
|---|---|
| 題 | `ops/gain/r535/bank/` 的 **S1 前 10 題**（`s1_01…s1_10`）。**不另外挑**——挑題本身就是一個選擇點 |
| 臂 | **只有 `RF`／`RP`**（L-6 逐字）。旗標從 `run_r535.ARMS` 原樣引用，本檔不重打字串 |
| agent | OpenCode **1.18.31**（設定路線）＋ Claude Code **2.1.278**（零接線） |
| 模型 | `gemma-4-12b-it-qat` @ `http://100.119.113.56:1234`（1003），`reasoning_effort: "none"` |
| 格數 | 10 題 × 2 臂 × 2 agent ＝ **40 格** |

## 檔案

| 檔 | 承重什麼 |
|---|---|
| `run_stagec.py` | 驅動＋量具。`--selftest`／`--write-plan`／`--report`／`--rescan` |
| `effort_shim.py` | **把 `reasoning_effort: "none"` 補進去**，因為兩個 agent 都不送它 |

## 兩件「為了照設計而必須加的東西」，兩件都要當成殘餘看

### 1. `effort_shim.py`——推論模式不是靠環境變數就拿得到的

R535 的 S1／S2 是驅動自己寫 pi 的 `models.json`
（`samplingParams: {"reasoning_effort": "none"}`）達成「不思考」的。
OpenCode 與 Claude Code 的設定路線裡沒有那個欄位。2026-09-19 在 1003 實測：

```
不帶旗標                        ⇒ completion_tokens_details.reasoning_tokens = 5
帶 "reasoning_effort": "none"   ⇒ reasoning_tokens = 0
```

⇒ **不補就是換了推論模式**，那會改變結論。所以加了一層只改一個欄位的轉送。

- **wireproxy 落的 `*.req.bin` 是 agent 送出來的原文（shim 之前）**
  ⇒ M7 三層量的仍然是 agent 自己的輸入，一個位元組都沒有被 shim 動過。
- 每一通注入都逐筆落盤（`shim_*.jsonl`）。本輪 **468/468 通帶 `model` 的請求
  都被注入**，40 格 `reasoning_tokens > 0` 的通數是 **0**。
- ⚠ **`/v1/messages` 那條路 LM Studio 不在 `usage` 裡報 `reasoning_tokens`**
  ⇒ Claude Code 那 20 格的驗證只做得到「旗標送出去了」，做不到「回來是 0」。
  那 20 格記 `unmeasured_rt`，**不准當成 0**。

### 2. `M7_ws` 的解析器要多認一種形狀

`run_r535._tool_calls_from_body` 只認 OpenAI 的
`messages[].tool_calls[].function`；Claude Code 走 Anthropic Messages
（`content` 裡的 `tool_use` block）。**不擴充的話那 20 格會全部落
`unparsable_tool_shape`（＝ `null`）**——而那不是「沒看工作區」，是量具不認得。

- 擴充只在「怎麼把工具呼叫撈出來」那一步（`_tool_calls_any`）；
  **分類仍然是 r535 那一份**（`classify_call`／`reads_own_solution`）。
- `--selftest` 兩種形狀各驗一輪，外加三條負控制
  （有痕跡撈不到 ⇒ `unparsable` 不是 0／body 不是 JSON ⇒ `None`／
  沒有痕跡 ⇒ 空陣列且不是 unparsable）。**紅了就不准發射**（`main()` 寫死）。
- `M7_file`／`M7_name` **是 r535 的原件**：它們比對的是位元組，與 wire 協定無關。

## 怎麼跑

```bash
# 量具自檢（負控制在前，不碰端點）
python3 ops/gain/r535c/run_stagec.py --selftest

# 計畫（確定性，n_cells=40，plan_sha256=bb489c55…95dc6）
python3 ops/gain/r535c/run_stagec.py --out <OUT> --write-plan

# 三條流（vacant-dev；node 不在預設 PATH 上）
export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH
export VACANT_GAIN_API=http://100.119.113.56:1234/v1/chat/completions
python3 ops/gain/r535c/run_stagec.py --out <OUT> --stream c0 --shard 0:3
```

`--report` 印逐 agent／逐臂的 M7 三層表；
`--rescan` **從落盤的 wire 重算 M7 三層並跟 `cell.json` 逐格比**
（＝「不必相信我寫的布林值」那一條；本輪 40/40 OK）。

## 落盤

`runs/r535c_stagec_20260919/`（含 README、`SHA256SUMS`、`NOT_IN_REPO.json`、
`wire.tar.gz`）。結果與「不能被讀成什麼」寫在那一份 README。
