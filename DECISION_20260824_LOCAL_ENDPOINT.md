# DECISION 2026-08-24（第三份）：改用本機端點跑 OFF n=60——條件改變，先寫再跑

**寫這份的時刻：2026-08-24 06:2x UTC，本輪尚未對本機端點發出任何 n=60 的呼叫。**
先 commit 再跑，git 歷史可以證明條件改變的理由不是看到數字之後補的。

`DECISION_20260824_OFF_BASELINE.md` 第三節那張 **f 判決表一個字都沒動**。
這份只改「用哪個後端、哪個模型池」，判準照舊。

## 一、為什麼改（不是為了好看的數字）

`DECISION_20260824_ENDPOINT_BLOCKED.md` 量到的：Cline 兩個帳號額度耗盡
（餘額各約 $0.005，OFF n=60 需 $0.39），`cline-pass/*` 回 403 ENTITLEMENT_ERROR。
**花錢要問人類，所以那條路這一輪走不了。**

本輪進行中，Mac 端把 `0817edf` 推上 origin，其中第三項就是**端點可換**
（`VACANT_GAIN_API`）。本機網段有一台 OpenAI 相容端點
`http://100.119.113.56:1234/v1/chat/completions`（Tailscale IP ＝ Mac 端那台），
`GET /v1/models` 列出：`qwen/qwen3.6-35b-a3b`、`nvidia/nemotron-3-nano-omni`。

實測它會動（`runs/g_local_smoke_20260824/`，n=3，**不是我啟動的**，
06:15 由本機另一個行程 detached 跑的，我等它跑完才接手）：

```
OFF: tasks=3 calls=3 infra_void=0 correct_delivery_rate=1.0
     endpoint_latency_ms p50=119035 max=195240   wall_s=360.3
     cost_usd=0.0  market_cost_usd=0.0
量具：參考解通過 3/3　壞解被擋 3/3
```

⇒ **免費、可用、不必問人類要錢。** 這是本輪唯一能往前走的路。

## 二、改了什麼、沒改什麼

| 項目 | smoke／baseline | 本輪 | 動了嗎 |
|---|---|---|---|
| 端點 | `api.cline.bot` | `100.119.113.56:1234`（本機） | **動了** |
| 模型池 | glm-5.2／deepseek-v4-flash／kimi-k3 | qwen3.6-35b-a3b／nemotron-3-nano-omni | **動了** |
| POOL 的 6 個 system prompt | 6 個 | 逐字相同 | 沒動 |
| seed／題序 | `g-smoke-20260820` | 逐字相同 | 沒動 |
| n | 60 | 60 | 沒動 |
| `--calibration-n` | 0 | 0 | 沒動 |
| 量具（`hidden_check` = base+plus） | — | 逐字相同 | 沒動 |
| **f 判決表** | baseline §3 | **逐字相同** | 沒動 |

要跑的指令：

```
VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
VACANT_GAIN_API=http://100.119.113.56:1234/v1/chat/completions \
CLINE_KEYS=/nonexistent \
python3 ops/gain/gain_run.py \
  --out runs/g_off60_local_20260824 --n 60 --seed g-smoke-20260820 \
  --arms OFF --probe-sample 0 --calibration-n 0 \
  --models qwen/qwen3.6-35b-a3b,nvidia/nemotron-3-nano-omni \
  --request-timeout-s 600
```

（`CLINE_KEYS=/nonexistent` 是刻意的：本機端點不驗 key，指到不存在的路徑可以
**證明這一跑沒有動用任何 Cline 額度**。若 loader 因此炸掉，那也是明確的失敗
而不是安靜地回頭打付費端點。）

**預估 2 小時**（實測 120s/題 × 60）。本輪只剩約 30 分鐘 ⇒ **detached 背景跑，
下一輪收成績單**。下一輪開場看到它還活著就等它，不要重跑（會白燒 2 小時）。

## 三、⚠ 這個條件改變會帶來的偏誤——先寫下來，免得下一輪自我恭喜

本機這兩個模型（35B／nano）**幾乎確定比 glm-5.2／deepseek-v4／kimi-k3 弱**。
弱模型更容易掉進人類要的 20–60% 失敗窗口。所以：

1. **若這一跑量到 f 落在 0.20–0.60，那不是「找到了難題」，
   是「換了弱 worker」。** 人類明文警告過這件事：換 worker 池是實驗條件的改變，
   量到的差異會混進條件差異。這份文件就是那個記錄。
2. **這一跑的 f 不能拿來回答「cline 池有沒有天花板」。** 那個問題只有在
   cline 端點恢復之後、用原池重跑才答得了。兩個 f 是兩個不同實驗的數字，
   **不准混在同一張表裡比較**。
3. 但它**可以**回答一個真的問題：**在一個有失敗空間的池子上，
   ON 打不打得贏等預算的 OFF5。** 那才是 SPEC_GAIN 的主問題，
   而且它不要求 worker 一定要是最強的模型。
   ⇒ 換句話說：**弱池讓主問題變得可答，而不是讓答案變好看。**
4. 三臂必須跑在**同一個池**上才有意義。ON／OFF5 之後也要用這個本機池，
   不可以一臂 cline 一臂本機。

## 四、什麼條件下這份決定該被推翻

- 若本機端點的 `infra_void > 6`（baseline 擋門）⇒ 這條路也不通，回去等額度。
- 若 f < 0.05（本機弱池都還是滿分）⇒ 天花板是題庫造成的不是模型造成的，
  那時才輪到「換題庫」這個旋鈕，而且要另寫決定書。
- 若 f > 0.60 ⇒ 池子太弱，量不到「機制能不能救」，要換回強一點的 worker
  （baseline 判決表最後一列）。
- 若 Cline 額度恢復 ⇒ **原池重跑一次 OFF n=60 當對照**，
  兩個 f 並列報告，不是二選一。
