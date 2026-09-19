# DECISION 2026-08-24（round 12）：`--review-timeout-s` 沒跟著 `--request-timeout-s` 一起調，殺掉重開

**寫這份文件的時刻：已經 kill 掉舊的 `g_onoff5_qwenonly_20260824`（PID 1781453，
跑了約 9 分鐘）、已經用修好的參數重新啟動 `g_onoff5_qwenonly_v2_20260824`
（PID 1782584），本文寫於確認新行程活著、preflight 過關之後。**

## 一、發現了什麼（實測，不是推論）

round 11 啟動 ON/OFF5 時只覆蓋了 `--request-timeout-s 600`，沒有覆蓋
`--review-timeout-s`（`gain_run.py` 預設 60，`--review-retries` 預設 2＝
**總共 2 次嘗試**，不是「重試 2 次再 2 次」——見 `brain_cline.py:117`
`for attempt in range(1, effective_retries + 1)`）。

`g_off60_qwenonly_20260824`（本輪之前跑完的 OFF baseline，60 題全用同一個
qwen-only 池、同一個中轉端點）量到的成功呼叫延遲分佈：

```
endpoint_latency_ms.all = {p50: 71736, p95: 205032, max: 358838}  (n=60, 0 失敗)
```

**p50 就已經超過 60s**——代表這個中轉端點下，超過一半的單次呼叫本來就要
71.7 秒以上才有回應。`review-timeout-s=60` 是給一個明顯比這個端點快的假設
調的（見 `gain_run.py:671` 註解「clinepass-clean-v2 的死因修復」——那是
原本 cline 官方端點時代的調法，沒人跟著這次換端點重新校準）。

`g_onoff5_qwenonly_20260824` 實際觀察（kill 之前，8 筆呼叫）：
**第一題的所有 review 呼叫（careful-1、hasty-2、hasty-1）第一次嘗試全部卡在
60015–60061ms、`ok=false`**，hasty-2 兩次嘗試都失敗 ⇒ 整題直接記
`infra_void`（`notes.jsonl`：`"hasty-2 重試 2 次仍失敗：TimeoutError: timed out"`）。
**6/6 觀察到的 review 呼叫全部逾時**，0 個成功。

## 二、為什麼這是問題，不是雜訊

`arm_on()` 裡三個 reviewer 用 `ThreadPoolExecutor.map`（`gain_run.py:445-447`）
平行送出，`with` 區塊結束前會等全部 thread 收斂（`shutdown(wait=True)` 是
預設行為）——**任一個 reviewer 耗盡重試次數就丟例外，整題記 infra_void**，
不是「那一票沒投到」。

粗估：若單次嘗試在 60s 內成功的機率 p（p50=71.7s ⇒ p 明顯 <50%，保守抓
p≈0.35~0.4，因為分佈右偏、59s 前只覆蓋不到一半），2 次嘗試都失敗的機率
≈(1-p)² ≈ 0.36~0.42；3 個 reviewer 都要在各自 2 次嘗試內至少成功一次，
整題不 void 的機率 ≈ (1-0.4)³ ≈ 0.22——**估計約 7~8 成的 ON 題目會在
review 階段直接 void**，而 15 小時的預算會被大量花在「跑到 review 才失敗」
的死路上（gen 呼叫仍要花 ~72–90s 才走到 review 這步）。跑到最後很可能撞上
`infra_void>10%` 的擋門，整臂作廢——15 小時等於白跑。

## 三、做了什麼（動作，不是只寫報告）

1. `kill -TERM -1781453`（process group，因為是 `setsid` 開的獨立 session）。
   舊行程確認死亡；**舊的 `runs/g_onoff5_qwenonly_20260824/` 目錄原樣保留**
   （8 筆 calls.jsonl、1 筆 notes.jsonl），不刪——它本身就是這個 bug 的證據。
2. 用新的 `--review-timeout-s 250` 重開，目錄換一個新名字
   `runs/g_onoff5_qwenonly_v2_20260824`（occupied 檢查會擋掉沿用舊目錄）：
   ```
   setsid nohup env \
     VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
     VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions \
     CLINE_KEYS=/nonexistent \
     python3 ops/gain/gain_run.py \
     --out runs/g_onoff5_qwenonly_v2_20260824 --n 60 --seed g-smoke-20260820 \
     --arms ON,OFF5 --models qwen/qwen3.6-35b-a3b --request-timeout-s 600 \
     --review-timeout-s 250 \
     > /tmp/onoff5_qwenonly_v2.log 2>&1 < /dev/null &
   ```
3. **250s 是怎麼選的**：介於 p95（205032ms）與 max（358838ms）之間，
   讓單次嘗試的成功機率覆蓋到 ~95%+ 而不是 <50%；`--review-retries` 沒動
   （維持預設 2 次），worst case 每個 reviewer ≈ 2×250+backoff ≈ 502s，
   仍然是有界的（呼應原設計「bounded deadline 避免尾延遲支配整條臂」的初衷，
   只是把界調到符合這個端點的實測分佈，不是調到無界）。
4. 啟動後驗證：preflight 第一次嘗試在 120s 上限內逾時（另一個獨立問題，
   見下），第二次嘗試 43.2s 成功；行程存活（PID 1782584，`ps` 確認）。

## 四、順帶量到的第二件事：preflight 也有一個沒對齊的短 deadline

`gain_run.py:754`：`timeout_s=min(args.request_timeout_s, 120)`——preflight
探測**永遠**封頂在 120s，不管 `--request-timeout-s` 傳多少。本輪啟動時
preflight 第一次嘗試就卡滿 120s 逾時，第二次才過（43.2s）。同時間我
直接對端點 `curl -m 30` 送一個 5-token 的極短請求，**30 秒內完全沒有任何
回應**（不是慢，是連第一個位元組都沒有）——這代表**端點當下正處於一段
明顯壅塞的時窗**，不只是「review deadline 設太短」這一件事，而是這個共用
中轉本身的延遲會隨時間大幅波動。

**這件事本輪沒有動 preflight 的程式碼**——它自己在第二次嘗試就過了，
沒有卡住整個啟動流程，且它只發生一次（一個 model、一次預檢），不像
review deadline 是每題都會踩到的系統性問題，成本量級不同。**留給下一輪
判斷要不要一起調**（如果之後每次啟動都要靠運氣撐過 preflight，才值得動）。

## 五、什麼條件下這份決定該被推翻

- 若 `g_onoff5_qwenonly_v2_20260824` 跑到一段之後 infra_void 依然大量出現
  （> 10% 那個既有擋門），代表 250s 還是不夠，或者端點的壅塞是結構性的
  不是偶發——那時候應該考慮的不是再加大 timeout（已經逼近 max=358.8s），
  而是重新檢討這個共用中轉在目前負載下適不適合拿來跑 15 小時等級的實驗。
- 若這次也在 review 階段觀察到系統性逾時（不是零星 1-2 題），代表問題
  不是「60s 太短」而是「review 呼叫本質上比 gen 呼叫慢」（例如 prompt
  更長、或被路由到更忙的 worker）——那要重新量 review 呼叫自己的延遲分佈，
  不能沿用 gen 呼叫（OFF baseline）的分佈當代理。
- 若之後想比較「舊跑法 vs 新跑法」的差異，**不能**把舊目錄
  （`g_onoff5_qwenonly_20260824`，8 筆全 review-timeout 底下的資料）跟新
  目錄的資料混在一起算同一臂的統計——舊資料的實驗條件（review timeout）
  跟新資料不同，混算會污染「等預算比較」。

## 六、成本

殺掉的舊行程只跑了 ~9 分鐘（1 個 preflight + 1 題 gen + 6 個逾時 review
嘗試，全部 $0，本機端點免費），沉沒成本可忽略。新行程從頭開始跑 60 題
ON/OFF5，估時量級不變（~15 小時，見 round 11 `DECISION_20260824_F_THRESHOLD_REACHED.md`
§3），但**這次的估時前提（review 呼叫能在合理時間內成功）現在才第一次
成立**——round 11 那個 15 小時估計其實隱含了「review 會成功」的假設，
而舊配置下這個假設是錯的，實際上大部分時間會被 void 迴圈吃掉。
