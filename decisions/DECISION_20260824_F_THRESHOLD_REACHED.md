# DECISION 2026-08-24（round 11）：f=0.217 達標，依 baseline 判決表啟動 ON/OFF5

**寫這份文件的時刻：`g_off60_qwenonly_20260824` 剛跑完（60/60），
`g_onoff5_qwenonly_20260824` 已啟動、尚在跑，本文寫於啟動之後、
第一批任務結果出來之前——不是看到 ON/OFF5 的數字才寫。**

## 一、OFF n=60 的最終結果（實測）

```
python3 ops/gain/analyze_off_baseline.py runs/g_off60_qwenonly_20260824
```

```
tasks=60  infra_void=0  measured=60
f = 13/60 = 0.2167
f_wilson_95ci = [0.131, 0.336]
gate_blocked_infra_void_gt_6 = false
verdict = "f>=0.20: 量測窗口可用 ⇒ 直接在這批題上跑三臂（ON/OFF5），worker 池不動"
failure_concentration_flag = false
worst_worker = hasty-1（19 次嘗試、5 敗，26%；其餘 worker 14–25% 均有失敗）
```

失敗題全部 13 題的 `err` 欄位逐條核對（`rows.jsonl`，非抽樣，全查）：
**13/13 都是 `sandbox_check_failed`，0 筆 timeout／空回應／infra 類錯誤。**
`endpoint_latency_ms.failed_attempts = 0`（summary.json）—— 失敗不是端點不穩造成。

對照 `DECISION_20260824_OFF_BASELINE.md` §4 的推翻條件：
- 「失敗全部來自同一個 worker」—— 不成立（6 個 worker 都有失敗，`failure_concentration_flag=false`）。
- 「err 大量是 sandbox timeout/記憶體」—— 不成立（全是 `sandbox_check_failed`，即測資判定失敗，不是資源耗盡）。

⇒ **baseline §4 的兩個推翻條件都沒觸發，f 量到的是題目難度，不是後端故障。判決表原樣適用。**

## 二、依判決表的動作

`f ≥ 0.20` 那格：「直接在這 60 題上跑三臂（ON／OFF5），worker 池不動」。
本文寫下時已依 round 10 事先擬好的指令啟動（PID 見下），**沒有等 f 數字出來才臨時決定要不要跑**——
指令內容 round 10 就已經寫進 `GAIN_STATE.md`，本輪只是等 OFF 跑完、核對推翻條件、然後執行。

```bash
setsid nohup env \
  VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
  VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions \
  CLINE_KEYS=/nonexistent \
  python3 ops/gain/gain_run.py \
  --out runs/g_onoff5_qwenonly_20260824 --n 60 --seed g-smoke-20260820 \
  --arms ON,OFF5 --models qwen/qwen3.6-35b-a3b --request-timeout-s 600 \
  > /tmp/onoff5_qwenonly.log 2>&1 < /dev/null &
```

新目錄（`g_onoff5_qwenonly_20260824`，不是 `g_off60_qwenonly_20260824`）——
沿用同一個會擋 append 的 occupied 檢查（`gain_run.py:695-704`），OFF 那個目錄
五個產物檔已存在，不能再對它跑 ON/OFF5。同 `seed`（`g-smoke-20260820`）⇒
`load_tasks` 會取到同一批 60 題（seed 排序取前 n 是確定性的），可與 OFF 逐題比對。

啟動後確認：preflight 量具通過（`instrument.n=12, ref_pass=12, broken_rejected=12`
—— 這次沒帶 `--probe-sample 0`，用預設值，跟 OFF 那支的 n=60 全量不同是預期內，
不是漏配置：預設抽樣一樣要求雙向滿分，滿分了）；40 秒後行程仍在跑
（`ps -p <pid>` 存活）；`calls.jsonl` 已有第一筆記錄，代表 ON 臂已在發真的呼叫。

## 三、成本與時間量級（先寫，不是跑完才估）

ON 每題 5 呼叫、OFF5 每題 5 呼叫，60 題兩臂合計 600 次呼叫。
沿用本輪與前幾輪收斂的速率 71.7–97s/題中位數（`endpoint_latency_ms.all.p50=71736ms`，
本次 OFF 60 題實測），**估 600 × ~90s ≈ 15 小時**，跨越遠超過一輪、甚至十輪的量級。
**本輪只負責啟動，之後每輪只做「還活著嗎／有沒有新錯誤／快照進度」，
不 block-wait 到跑完。**

## 四、什麼條件下這份決定該被推翻

- 若 ON/OFF5 跑到一半 `infra_void` 大量出現（端點不穩）⇒ 停止硬等，
  比照 OFF baseline 的擋門邏輯（>10% 記 incomplete）。
- 若 `equal_budget_comparison_valid` 最終為 false（`calls_per_task` 沒有兩臂都精確等於 5）
  ⇒ 「等預算比較」這個框架本身要重新檢查，不能直接拿 correct_delivery_rate 比。
- 若過程中又出現第二個背景 `gain_run.py` 行程（別的 session 或別的機器啟動）
  ⇒ 立刻停手核對是否打中同一個 `--out` 目錄，避免重複計數或互相拖慢延遲。
