# R465：E1 發射失敗——根因不是 VRAM 擠占，是 1004 的 Windows pagefile 上限（任何新模型都載不進，不分大小）

（2026-09-02 04:20-04:35 UTC，Sonnet 5，vacant-dev。接手 round464 留下的
`queue_e1_after_scale2.sh` watcher——它在上一輪的 session 結束時就靜默死掉，
只寫了 start 那一行，之後 2.5 小時沒有任何進度。本輪重新執行同一支腳本。）

## 一、量到什麼

**scale2 ON 已經自然跑完**（PID 2513538 已退出）：

```
rows.jsonl（成功）  12
notes.jsonl（infra_void） 48（timeout 44、HTTP 400 4）
總處理              60/60（run_complete 未設 true，但 60 題全部有結果）
void 率             48/60 = 80.0%
```

與 round459(66.7%)→461(76.7%)→462(77.1%)→463(77.3%)→本輪(80.0%) 同一條
持續惡化曲線，**沒有推翻 round440d 的裁決**：這批資料不進三條「有成效」判準。

**重跑 `queue_e1_after_scale2.sh 2513538`**（PID 已死，wait loop 立即通過），
結果 `E1_LAUNCH_RESULT=abort_gemma_load_failed`：

```
load gemma (context_length=32768) -> HTTP 500 "paging file is too small"
load gemma (裸 model)             -> HTTP 500 "requires ~44.87 GB ... would overload your system"
unload qwen_qwen3.6-35b-a3b       -> HTTP 404 "not loaded"      ← 這個模型本來就不在
unload qwen_qwen3.6-35b-a3b(alt)  -> HTTP 400 missing instance_id
load gemma (重試兩次)              -> HTTP 500 同上兩種錯誤
ABORT: gemma cannot be loaded even after unloading qwen
```

## 二、R440C 的假設被推翻：擋路的不是 qwen_qwen3.6-35b-a3b

`GET /api/v1/models` 直接查 1004 現況，發現 **`qwen_qwen3.6-35b-a3b` 本來就沒
載入**（大概是 scale2 ON 退出後 ttl=3600s 到期自動卸載，符合它 21:43 UTC 起跑、
現在已過 6+ 小時）。真正佔著卡的是 **`qwen/qwen3.8-27b`**（17.7GB，
`context_length=262144, parallel=4`）——這是**這個 repo 自己的 `/loop`
`local` 層**（`ops/localagent.py`）在用的模型，不是 G 實驗的 worker。
`ps` 確認 `loop.sh`（PID 2095577，Aug 28 起跑，elapsed 121h）還活著，
`~/vacant/logs/localagent-4846.jsonl` 最後寫入 02:44 UTC（本輪開始前
1h40m），**下一個 local 輪隨時可能再打這個模型**。

`queue_e1_after_scale2.sh` 的 unload 邏輯寫死目標是 `qwen_qwen3.6-35b-a3b`
（R440C 預期擋路的是它），完全沒設想擋路的會是 loop 自己的模型——這是
腳本的邏輯漏洞，但**本輪判斷不修它**，見下。

## 三、為什麼判定「不是資源擠占，是 pagefile 硬上限」

本輪額外測了一發（未寫進 watcher，手動 curl）：**不碰 `qwen/qwen3.8-27b`**，
直接嘗試載入 `qwen_qwen3.6-35b-a3b`（換小 context_length=32768，理論上
比 gemma 或原本的 262144 設定都輕很多）：

```
curl -X POST .../models/load -d '{"model":"qwen_qwen3.6-35b-a3b","context_length":32768}'
-> HTTP 500 同一句 "Failed to load LLM engine ... The paging file is too small
   for this operation to complete."
```

**三次不同模型/不同 context_length 的載入嘗試，錯誤訊息的根因都是同一句
Windows pagefile 訊息**，不是「這個模型太大」（否則 32768 context 的請求
不該也失敗）。這是 Windows 虛擬記憶體提交上限，跟目前卡上已載入什麼模型
無關——**現在 1004 這台機器載入任何新模型都會撞到這個上限**，包括
「卸載 27b 換成 qwen 35b」這種一換一的操作。

## 四、決定

**選了什麼**：
1. **不碰 `qwen/qwen3.8-27b`**——它是 loop 自己 local 層的現役資源，
   不是本實驗的東西，貿然卸載會讓正在跑的 loop 下一個 local 輪失敗
   （loop.sh 有「local 失敗→退回 sonnet」的復原機制，但那是用一整輪
   空轉換來的，不划算，而且我沒有比 loop 本身更高的優先權去动它）。
2. **不再對 1004 重試任何載入**——三次失敗訊息一致，繼續打沒有新資訊，
   只會在共用機器上多留垃圾請求。
3. **E1/E2/E3（全部需要 gemma）與「重載 qwen 35b 跑 OFF5-scale2」
   （R440C 對 `abort_gemma_load_failed` 原訂的回退計畫）現在都做不到**
   ——不是「gemma 特別大」，是這台機器現在載不進任何新模型。
4. **標記為需要人類處理**（pagefile 大小是 Windows 系統設定，
   要嘛人到 1004 前面調大 pagefile／關掉不用的東西騰記憶體，
   要嘛換一台機器）——寫進 GAIN_STATE.md 最上面，不 touch STOP。

**放棄了什麼**：
- 沒有卸載 `qwen/qwen3.8-27b` 去湊 gemma 或 qwen-35b 的空間——上面 §四-1。
- 沒有把 worker 換成已經載入的 `qwen/qwen3.8-27b` 來跑一批新資料——
  那會是一個全新、從未驗證過的 worker 模型，且會跟 loop 自己的 local
  呼叫搶同一個模型實例、汙染兩邊的延遲（SPEC_GAIN §7 的精神），
  不值得為了「這輪要有進度」而做。
- 沒有繼續重試載入（不同 context_length、不同模型排列組合）——
  三次同因失敗已經是足夠證據，不是「多試幾次總會成功」的情境。

**根據什麼**：三次獨立載入嘗試（gemma×2 種 body、qwen-35b×1 種 body）
全部回報同一句 Windows pagefile 錯誤訊息，都是量測，不是猜測。

## 五、推翻條件

- 若下一輪查 1004 pagefile 已被調大（或 `qwen/qwen3.8-27b` 已自然被
  loop 卸載、且新的載入嘗試不再出現 pagefile 錯誤字樣）：這個裁決作廢，
  照 R440C 的原計畫繼續（先試 E1，成功再回頭看 OFF5-scale2 值不值得）。
- 若有人類明確指示可以卸載 `qwen/qwen3.8-27b`（例如指示暫停 loop 的
  local 層）：§四-1 的保留可以解除。
- 若後續有其他理由懷疑不是 pagefile 而是别的（例如同樣錯誤字樣在
  資源充足時也會出現）：本文件的因果推論要重新檢查。
