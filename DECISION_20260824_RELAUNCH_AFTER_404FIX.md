# DECISION 2026-08-24（本輪）：接手一個沒人在跑的中斷 run，重跑乾淨的一份

## 一、開場看到的狀態

- `git log` 最新是 `1e29749`（+0800 16:01 ＝ UTC 08:01，**本輪開場前 3 分鐘**），
  訊息是「404 要重試，而且要換另一種模型命名再試」，改了
  `ops/gain/brain_cline.py`（404 從不重試移出來、輪替 `qwen/xxx` ↔ `qwen_xxx`
  兩種模型 ID 命名）＋新增 `tests/test_gain_runner.py` 的對應測試。
  這不是本輪做的——是本輪開場前，另一個正在跑同一個 repo 的行程做的
  （見 `~/vacant/GAIN_STATE.md` round 2 已經記過「這台機器有別的東西在寫同一個
  repo」，這次又發生一次）。
- `runs/g_off60_relay_20260824/summary.json`：`run_complete=false`、
  `OFF.tasks=60 calls=42 infra_void=18 correct_delivery_rate=0.714`。
  `infra_void=18 > 6` ⇒ 撞到 baseline 判決表的擋門，**這一份的 f 不算數**
  （commit 1e29749 的訊息裡也是這樣寫的：18 格裡 17 格是 404）。
- `pgrep -af gain_run.py` 在本輪開場**是空的**——那份 run 已經停了（最後一次
  寫檔是 07:49:55 UTC，本輪開場 08:04，中間 15 分鐘沒有新資料），
  不是「還在跑，等它」，是真的斷在那裡。
- `~/vacant/GAIN_STATE.md` 停在 round 2（06:11–06:5x UTC），但 git log 顯示
  round 2 之後至少還有 8 個 commit（backend switch、endpoint blocked、
  8765 中轉更正、404 修復…）。**狀態檔沒跟上**——下一輪要注意這一點，
  不能只信 GAIN_STATE.md 的「下一步」欄位，要對照 `git log` 的時間戳。

## 二、本輪的判斷

404 修復已經有測試（`test_404_is_retried_because_the_relay_swaps_nodes`），
diff 本身邏輯清楚（405/403/402/401/400 仍不重試，只把 404 移出不可重試集合，
且重試時輪替兩種模型 ID 命名）。**本環境沒有 pytest 可用**
（`python3 -m pytest` ⇒ `No module named pytest`，且找不到 `.venv`）——
這是本輪的量測缺口，照實寫：**沒有親自重跑測試套件驗證這次修復**，
只讀了 diff 判斷合理。下一輪如果找得到 pytest 環境，應該補跑一次。

**中斷的那份 `g_off60_relay_20260824`（42/60, infra_void=18）已經因為擋門
判定不算數**——不管修不修都救不回來（前 25 格是用舊的不重試 404 邏輯量到的，
跟修復後的行為不是同一個實驗條件）。所以不是「續跑」，是重開一份新的，
用同一組 seed／n／模型／request policy，只有程式碼裡 404 的處理不同。

## 三、本輪做的事

啟動 `runs/g_off60_relay2_20260824`（沒有覆蓋任何舊資料，舊的兩份
`g_off60_local_20260824`、`g_off60_relay_20260824` 原樣保留當證據）：

```
VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions \
CLINE_KEYS=/nonexistent \
python3 ops/gain/gain_run.py --out runs/g_off60_relay2_20260824 --n 60 \
  --seed g-smoke-20260820 --arms OFF --probe-sample 0 --calibration-n 0 \
  --models qwen/qwen3.6-35b-a3b,nvidia/nemotron-3-nano-omni \
  --request-timeout-s 600
```

（`--seed` 沿用 baseline 決定書訂的 `g-smoke-20260820`，跟前兩份 60 題 run
同一個題序，`summary.json.seed` 已核對一致。）

跑在 `setsid nohup ... & disown` 底下、寫 `/tmp/off60_relay2.log`，
launch 後量到：
- instrument（量具雙向驗證）：`n=60 ref_pass=60 broken_rejected=60`，
  跟前兩份 60 題 run 一致，尺沒壞。
- `pgrep` 確認 PID 存活（背景生成中）。

**本輪不等它跑完**——人類本輪明文指示長跑要在輪次之外，這一輪的工作是
「啟動」與「收拾已產出的東西」，不是「等」。`setsid`＋`disown` 讓行程脫離
本次 session，下一輪不論是不是同一個 session 都能接手看結果。

## 四、下一輪要做什麼

1. 先 `pgrep -af "gain_run.py --out runs/g_off60_relay2_20260824"`：
   - 還活著 ⇒ 看 `/tmp/off60_relay2.log` 有沒有 traceback、看
     `runs/g_off60_relay2_20260824/rows.jsonl` 累積到幾筆，決定等或不等。
   - 死了但 `summary.json.run_complete=true` ⇒ 跑完了，直接對
     `DECISION_20260824_OFF_BASELINE.md` §3 判決表。
   - 死了但沒跑完 ⇒ 看 `notes.jsonl`／`calls.jsonl` 最後幾筆的 `error`，
     判斷是不是 404 又發生（如果是，代表這次的修復也不夠，8765 中轉可能
     换了第三種命名法，不要照抄 round 之前的修法，先看新的錯誤字串）。
2. `infra_void ≤ 6` 且 `run_complete=true` ⇒ 直接對判決表出結論，
   不准改表。
3. 記得把這份文件、`runs/g_off60_relay_20260824/`（中斷的舊份）、
   `runs/g_off60_local_20260824/` 剩下的未提交變動一起收進本輪 commit。

## 五、什麼條件下這份決定該被推翻

- 若 `g_off60_relay2` 也在 404 上卡住（`infra_void` 佔比類似）⇒ 表示
  8765 中轉的節點命名問題比 commit 1e29749 想的更複雜（可能超過兩種命名），
  要重新盯 `calls.jsonl` 裡實際送出的 `model` 欄位分佈，不要照抄同一個修法再試一次。
- 若這環境後來找得到 pytest ⇒ 應該補跑 `tests/test_gain_runner.py`，
  不要繼續用「讀 diff 判斷合理」代替真的測試結果。
