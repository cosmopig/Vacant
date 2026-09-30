# 發現：拿現成 agent 平台跑「有 Vacant / 沒 Vacant」量到了什麼

日期：2026-09-29
分支：`design/loop-without-possession`
原始資料：`ab_raw/runs/`（wave 1，60 格）、`ab_raw/runs2/`（wave 2 pilot，12 格）、
`ab_raw_20260929_0047.tar.gz`（118 MB 單檔封存）
環境：Ubuntu 24.04 / 8 core / 7.7 GB RAM / 無 GPU；opencode 1.18.33；
模型 `openrouter/stealth/space-bunny-alpha`（定價 0/0，`cost: 0` 逐格記錄）；
Vacant `fix/native-acceptance-bridge-audit-20260928`（3.7）從原始碼 `pip install`

這一份只寫**量到的**。沒量到的效果在
`decisions/prereg/PREREG_20260929_LOOP_WITHOUT_POSSESSION.md`，不混進來。

---

## 一、Wave 1：R534 題庫 20 題 × 三臂

| 臂 | 是什麼 | 隱藏檢查全對 | 交付 | 拒交 |
|---|---|---:|---:|---:|
| **A** plain | opencode，什麼都沒有 | 19/20 (95.0%) | 20/20 | 0 |
| **B** zero-cfg | `vacant install` 預設（`mode: evidence`）＋ opencode 原生 plugin | 17/20 (85.0%) | 19/20 | 1 |
| **C** bridge | 3.7 的 `native_acceptance_bridge`：prepare／judge／release | 17/20 (85.0%) | 17/20 | 3 |

配對 McNemar（A 對 B）：discordant 2 對，`p = 0.50`，**記為 unresolved，不是結果**。

### 這批數字不能支持任何關於 Vacant 的結論

1. **天花板效應。** A 臂 95.0%。閘門能改善的空間是 0。
2. **A 與 B 的 2 格差異全部來自 opencode 沒交出檔案**（`lcb_3584`、`lcb_3654`），
   其中 `lcb_3584__B` 的對應 agent 事件流裡沒有 429，也不是逾時。
3. **B 臂有 2 格吃到 429**（`lcb_3779__B`、`lcb_3789__B`，兩者仍有產出）。
   免費額度在 16:16 UTC 用盡，之後的格子全部受影響。
4. **C 臂 3 格是 harness bug**：`arm_c` 沒有用 `--dir`，opencode 掃錯的專案根，
   3 個 `step_start` 之後 rc=1、無 stderr。

**結論：wave 1 量到的是「這個題庫對這顆模型太簡單」，不是機制的效果。**

## 二、Wave 1 真正有價值的產出：三個可定位的缺口

這三個與模型表現無關，所以它們是可修的。

### W1 — 通道中介只支援兩種金鑰變數

`vacant_network/vrun/envmap.py:272-281` 的 `SECRET_VARS` 刪掉 `OPENROUTER_API_KEY`，
`build_child_env`（`:492-528`）只對 `("OPENAI_API_KEY", "ANTHROPIC_API_KEY")` 給 sentinel，
`discover_keys()`（`:485-489`）只讀 `KEY_VARS` 的 openai／anthropic 兩條。

量到的後果：opencode 的 openrouter provider **在本機 1.2 秒內 rc=1**，
`requests_seen = 0`，一次 wire 都沒發。
改用固定埠的 openai-compatible provider（讀 `{env:OPENAI_API_KEY}`）之後
`requests_seen` 確實變成 2 —— 通道中介本身對 opencode 是通的，**但 opencode 仍以
非零碼結束**。這條路沒有走完。

### W2 — opencode 沒有 stop 等價事件，v3.7 的回合結束檢查不可達

`~/.config/opencode/plugin/vacant.js`（`vacant install` 產出）只註冊
`chat.message`／`tool.execute.before`／`tool.execute.after`。
pi 的同名模板有 `ask("stop", …)`；opencode 模板沒有。
Python 端 `adapters/hook.py` 的 `EVENT_MAP` **有** `"opencode": {… "stop": "stop" …}`，
所以缺的是 plugin 側。

量到的後果（`lcb_3686__B`，`install.json` 為 `{"mode": "evidence"}`）：

```
chain.ndjson 事件統計： trace_genesis 1, prompt 3, session_seen 2, step 37,
                       session_closed 3, unrecorded_change 1
stop / finding / feedback 事件： 0
delivery.md / delivery.json： 不存在
perf.jsonl： prompt 3, session_end 3, pre_tool 37, post_tool 37
```

**37 個 step 的完整簽章病歷、零個裁決。** 這比不做更危險，因為鏈看起來是對的。
`vrun/launcher.py` 的 docstring §3 已經為 W1 的同型問題給了判準
（`requests_seen == 0` ⇒ 判 **VOID**）；**W2 目前沒有同型判準。**

### W3 — opencode 的專案根不由 cwd 決定（我自己的錯，已修）

agent 原話：「There is no `TASK.md` in the working directory
(`/home/user1/ab-20260928`)」。工作區只有一個檔時 100% 失敗。
repo 自己的 `adapters/agents.py::opencode_build` 用的是 `--dir` ＋ `git init`，
不是 `cwd`。已照那一形狀修（`ab_harness/wave2.py` 的 `run_attempt` 與 `stage`）。

## 三、成本硬上限

```
X-RateLimit-Limit:     1000     （帳戶層，免費模型每日）
X-RateLimit-Remaining:    0
X-RateLimit-Reset:    1790640000000  =  2026-09-29T00:00:00Z
每次 opencode 執行約 15–20 請求  ⇒  每日約 50–65 次 agent 執行
key 層： limit_remaining = 0，usage = 0（從未成功呼叫過付費模型）
帳戶層： total_credits 5.00，used 3.70478204
```

**90 題 × 3 臂 × 1–3 次嘗試，需要數天。** 這一條寫在預註冊裡，是為了不讓人把
「跑不完」讀成「跑不過」。

## 四、已建好、零成本、隨時可用的部分

| 東西 | 位置 | 狀態 |
|---|---|---|
| R535 題庫 90 題 | `ab_raw/r535_bank/` | 量具 7 項 × 90 題**全綠**（本地跑過） |
| `vacant loop` | `vacant_network/loop.py` + `loop_cli.py` | 28 條反證檢查**全過**（零模型呼叫） |
| `vacant loop` intake 路徑 | 遠端 `/tmp/looptest` | 端到端：reject→帶原文回饋→accept→放行 |
| 三臂 runner | `ab_harness/wave2.py` | RPL 臂呼叫**真的** `vacant loop` |
| 耐久 runner | `ab_harness/overnight.sh` | 遠端 PID 存活；按 triad 續跑；遇 429 等額度 |

`vacant loop` 的實測紀錄（mock agent，零模型呼叫，intake 裁決）：

```
attempt 1 -> reject | visible_acceptance=FAIL test_visible.py::check_01_add
                    — assert: add args=(2, 3) got=0
attempt 2 -> accept | visible_acceptance=PASS 2/2 checks passed
verdict: accept  exit 0  artifact ff05a68575030beb48303bce35ea63fe
released: <receiver_home>/released/s1_01_addmul
```

這是「閘門 → 帶可行動回饋的拒交 → 重試 → 接受 → 放行」第一次在 **opencode 這個
Vacant 無法附身的平台上**跑完。W1 與 W2 都不擋它，因為它不碰網路也不掛鉤。
