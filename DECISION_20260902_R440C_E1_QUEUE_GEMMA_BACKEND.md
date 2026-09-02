# R440C：E1（gemma-only）排隊——後端實況、與 R463 的次序衝突、發射條件

（2026-09-02 01:40 UTC，Fable 5.1，Mac 端 session「vacant」。依 session
「調查架構信任度並提出測試計劃」轉達的人類 2026-09-01 指令執行 R440／R440B
的 E1(L0)。本文件在發射前寫定＝預註冊；發射由 `ops/gain/queue_e1_after_scale2.sh`
在 scale2 ON 自然收完後自動執行，每一步都寫進 `~/vacant/logs/queue_e1.log`。）

## 一、量到什麼（2026-09-02 01:27–01:40 UTC，全部是直接探測，不是讀文件）

**8765 中轉的實際拓撲**（`C:\Users\w401\lmstudio-monitor\config.yaml`，
`lmsmon hub`，PID 21112 on win1003）：

| backend | url | hub 回報 | 實況 |
|---|---|---|---|
| `1003` | `http://100.119.113.56:1234` | `reachable: false` | win1003 的 LM Studio 只綁 `127.0.0.1:1234`，`lms ps` 無模型，磁碟上**沒有 gemma**（只有 qwen3.8-27b＋nomic） |
| `1004` | `http://100.86.226.21:1234`（w401c-15，Windows） | `reachable: true` | **所有模型呼叫實際都落在這台** |

也就是說「8765 中轉池（qwen3.6-35b + gemma-4-12b）」現在是**一台 GPU**，
不是兩台。1004 目前：

```
qwen_qwen3.6-35b-a3b   loaded   22.3 GB (Q4_K_M)  context_length=262144  parallel=4  ttl=3600s
gemma-4-12b-it-qat     not-loaded   7.2 GB (Q4_0)
qwen/qwen3.8-27b       not-loaded  17.7 GB
```

gemma 經 hub 呼叫 → `HTTP 400 Failed to load model "gemma-4-12b-it-qat".
Error: Operation canceled.`（2.5s 回，跟 round446/447 量到的一模一樣，
從 2026-09-01 09:00 UTC 起未曾恢復）。qwen 經 hub 的 8-token 探針 **90s 逾時**
——scale2 ON 正在把它打滿，與 round459–463 的 77% void 平台一致。

**可用的替代路徑**：1004 的 LM Studio 開了 REST v1，`POST /api/v1/models/load`
存在（空 body 回 `Missing required field 'model'`，路由確認、未觸發任何載入）。
SSH 到 1004 不通（port 22 逾時），REST 是唯一遠端操作手段。

**win1003:1234 不可用**：`/d/lock_scene` 存在（2026-09-02 09:21 CST 建立），
ComfyUI（PID 35448）＋`D:/night_scene.py`（PID 1540）在跑，GPU 6.8/24 GB。
R440B／LOOP_PROMPT 平行規則明文：lock 存在時不得在 1234 起模型。**且該機
根本沒有 gemma 檔**，就算沒 lock 也要先下載。

**8765 上的現役 run**：`g_on_qwen_only_scale2_20260901`（PID 2513538，
vacant-dev，21:43:55 UTC 起）01:36 UTC 時 rows 11／notes 40（39 void＋1 量具行）
＝50/60 處理，rows.jsonl 上次寫入 01:10:20（26 分鐘無新成功列）。round463
外推剩餘約 70–80 分鐘。

**迴圈狀態**：vacant-dev 第 4844 輪（`local`）01:12 UTC 開始、還在跑，
repo 在 538b744（round463），**尚未 pull 到 round440b**。
`~/vacant/bin/loop.sh`（Aug 28 的副本）的 NEXT_MODEL 只認 `opus|sonnet|local`
——round440b 改的是 repo 內 `ops/loop.sh`，**運行中的那份沒有 `fable` 分支**，
寫 `fable` 會被當成未知值退回 sonnet。

## 二、衝突：round463 的「下一輪」vs R440 人類指令

round463 給下一輪的指令：scale2 ON 跑完 → 立刻起同 seed 的 OFF5（qwen）。
那會佔 8765 再 5–6 小時，E1 就得再等。R440 是人類 2026-09-01 的即時指令，
R456/R463 是迴圈自己的決定（擴大 qwen-only 配對樣本補檢定力）。
人類指令優先；而且 R440 的 H-A 直指 qwen-only 這整條線的前提（35b 太強
⇒ 沒有真失敗可攔），繼續堆 qwen-only 樣本在 H-A 未答之前是低優先。

## 三、決定

**選了什麼**：
1. **不殺 scale2 ON**。已收 50/60，剩約 1 小時；殺掉損失 4 小時資料，
   等待成本 1 小時。等它自然退出。
2. **scale2 ON 退出後，8765 的下一個 run 是 E1（gemma-only），不是 OFF5-scale2。**
   OFF5-scale2 延後到 E1 之後；round456 §四的 CMH 合併規劃跟著延後，
   不取消。
3. **gemma 的載入走 1004 的 REST**，兩步：
   - A：在 qwen 仍載入時試載 gemma（`context_length=32768`）。成功＝零擾動。
   - B：A 失敗（幾乎確定是 VRAM：22.3 GB＋262k KV 已經吃滿一張卡）→
     **卸載 qwen 實例** → 再載 gemma。qwen 的完整載入設定已存
     `~/vacant/logs/queue_e1_models_before.json`，本文件 §六 有還原步驟。
4. **發射前健康探針**：經 hub 8765 對 gemma 連問 3 次，**3/3 要 200**
   （round447 推翻條件的口徑：「連續 3 次呼叫不逾時」）。不到 3/3 不發射，
   把結果寫進 log 停下。
5. **E1 指令列**（R440 §執行序＋決定性 run 的 request_policy）：
   ```
   VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
   VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions \
   CLINE_KEYS=/nonexistent \
   python3 ops/gain/gain_run.py --out runs/g_r441_gemma_only_mbpp --n 179 \
     --seed g-r212-route-20260828 --models gemma-4-12b-it-qat \
     --request-timeout-s 600 --review-timeout-s 380
   ```
   request_policy 對齊決定性 run（g_r342/345/348/356 與 r439 的 summary.json：
   `timeout_s=600, retries=4, backoff_s=2.0, review_timeout_s=380,
   review_retries=2`）。**注意 qwen-only 那批（round447–463）用的是
   `review_timeout_s=60`，不是決定性 run 的 380**——E1 對照的是決定性 run，
   所以取 380。唯一差異＝`--models`。

**放棄了什麼**：
- 殺掉 scale2 立刻發射——省 1 小時、丟 4 小時資料，不划算。
- 在 win1003:1234 平行跑 E1——lock_scene 在、GPU 被展覽夜班占用、沒有 gemma 檔，
  三個理由任一都夠。
- 等 gemma「自己恢復」——它從 09-01 09:00 起沒恢復過；原因不是後端壞了，
  是 qwen 佔著 VRAM 讓 JIT 載入被取消（qwen ttl=3600s，只有 qwen 閒置一小時
  自動卸載後 gemma 才載得進，而 qwen-only 的 run 讓它永遠不閒置——這解釋了
  het 池 8/29–8/31 能跑、9/1 起 gemma 全死的時間線）。
- 一次全開（L0–L5 全做）——R440B 已寫明階梯理由，不重複。

**根據什麼**：上面 §一 全是量測。「A 會失敗、要走 B」是判斷（VRAM 容量
沒有直接讀到，1004 的 GPU 型號未知），watcher 會把 A 的實際回應寫進 log。

**什麼情況下該推翻**：
- 若 watcher log 出現 `E1_LAUNCH_RESULT=abort_*`：E1 沒發射，原因在 log。
  `abort_gemma_load_failed`＝連卸載 qwen 後 gemma 都載不進，那是 1004 本機
  問題（磁碟、驅動、LM Studio 設定），需要人到那台機器前面；此時應回到
  round463 的計畫（重載 qwen、跑 OFF5-scale2），不要空等。
- 若 E1 任一臂 infra_void 率 >20%（R440 中止準則）：中止，先修 infra。
  gemma 上次乾淨的 review 成功率未知（round442 的 22% 是在 400 風暴中量的），
  **第一個 20 題檢查點就要看 ON 臂的 void 率**。
- 若 E1 的 OFF 失敗率 <15%：天花板重現（R440 準則），照實記錄。

## 四、預註冊預測（沿用 R440 P1–P4，加 E1 發射專屬）

- P1：E1 OFF 失敗率 >26.44%（窗 35–60%）。
- P2：評審準確率仍 ≈ almost-PASS ±2pp ⇒ R438 結論加強。
- P3（翻盤窗）：評審準確率顯著上升且 ON>OFF5 配對顯著。
- P0（本文件新增）：**gemma 單獨載入時 ON 臂 void 率 <35%**（round456 qwen 的
  參考點）。若 gemma 單獨在卡上還 >35% void，round442「瓶頸在 review 長
  context 被拒」的假說要重開，不能再歸咎壅塞。

## 五、對迴圈的影響（先寫明，不讓它變成下一輪的謎）

- E1 發射後，vacant-dev 迴圈開場的「重複 run 檢查」會看到 1 個 gain_run
  在跑——**那是 E1，不是孤兒**，不要照 round460 的邏輯殺它。
- 若走了步驟 B，qwen 在 E1 期間（~35h）不在卡上：迴圈的 `local` 層
  （`localagent.py` 預設 `qwen/qwen3.6-35b-a3b`）會失敗，loop.sh 內建
  「local 失敗→下一輪退回 sonnet」，自動恢復，代價是一輪空轉。
- `~/vacant/bin/loop.sh` 要從 repo `ops/loop.sh` 同步並重啟迴圈
  （`touch ~/vacant/STOP` 等當輪收尾再起新的），`fable` 層才會生效。
  本 session **沒有做**：這是 round440b 的作者（peer session）改的東西，
  重啟迴圈會中斷正在跑的第 4844 輪，交回給 peer／人類決定時機。

## 六、qwen 還原（E1 收完後，或推翻條件觸發時）

```
curl -X POST http://100.86.226.21:1234/api/v1/models/load \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen_qwen3.6-35b-a3b","context_length":262144}'
```
原始載入設定（供比對）：`context_length=262144, eval_batch_size=2048,
physical_batch_size=512, parallel=4, flash_attention=true,
speculative_draft_mtp=true, num_experts=8, offload_kv_cache_to_gpu=true,
ttl=3600`。若 REST 不接受某些欄位，至少 context_length 要一致，其餘由
1004 的 LM Studio 預設補。**262k context 本身是不是 77% void 平台的原因**
（KV 預留＋parallel=4 把 22 GB 模型擠到卸載）是個值得人類看一眼的問題，
本文件只記不改。

## 七、沒做的事（照實寫）

- 沒有發射任何 run（scale2 ON 還在跑；§7 一端點一 run）。
- 沒有改任何實驗程式碼（`gain_run.py`／`brain_cline.py` 零改動）。
- 沒有動 1004 的模型狀態——watcher 在 scale2 退出前不會碰它。
- 沒有同步／重啟 vacant-dev 的 loop.sh（§五）。
- 沒有回寫 vacant-dev 的 `GAIN_STATE.md`（那是迴圈的檔，第 4844 輪正在寫；
  迴圈下一輪 pull 會拿到本文件與 watcher 腳本）。
- 沒有做 L1–L5 的任何準備——階梯規則：上一階沒訊號不准跳。
