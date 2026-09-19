# DECISION 2026-08-29（round263）: gemma-4-12b-it-qat 復活 — 重開異質池路徑

寫於 2026-08-29 UTC ~02:10，在啟動任何 calibration run 之前。

## 背景

`DECISION_20260828_R210_HET_POOL_PREREG.md`／`DECISION_20260828_R211_HET_POOL_ABORT.md`
（round210/211）結論：8765 中轉當時只有 `qwen/qwen3.6-35b-a3b` 真的能用——
`gemma-4-12b-it-qat` 因後端記憶體不足（需 44.87GB）400 拒載，
`qwen/qwen3.8-27b` 逾時（後來 round211 診斷是 model 本身沒在服務，不是併發問題）。
round260 因此把「能力異質池」判定為這個後端目前給不出來，轉而測「同一
model 換 persona」是否構成異質性——round260 用置換檢定＋可轉移性量測，
結論是 persona 差異統計上分不開，且 MBPP+ 題庫只有 378 題，永遠湊不出
證明所需的 281 個 discordant pair，這條路徑被數學鎖死。

round262 重試了一次異質池（含 qwen3.8-27b），模型池預檢再次因
qwen3.8-27b 逾時而 SystemExit。round262 沒有收尾就結束（本輪 round263 已
用另一個 commit 補上，見上一個 commit message）。

## 本輪量到的新事實

**四次獨立檢查，`qwen/qwen3.8-27b` 全部逾時，維持「這個 model 目前沒在
服務」的結論不變：**

```
round211（2026-08-28 ~12:03 UTC）solo curl：120s 逾時，0 bytes
round262（2026-08-29 ~01:55 UTC）runner 模型池預檢：TimeoutError
round263（2026-08-29 02:03 UTC）solo curl 60s：exit 124，0 bytes
round263（2026-08-29 02:03 UTC）solo curl 220s：exit 124，0 bytes（220s 都不夠）
```

**但 `gemma-4-12b-it-qat` 這次反過來了**——round210 的「後端記憶體不足
400 拒載」不再成立：

```
$ time curl -s -X POST http://100.119.113.56:8765/v1/chat/completions \
    -d '{"model":"gemma-4-12b-it-qat","messages":[{"role":"user","content":"reply with just: ok"}],"max_tokens":20}'
{"id":"chatcmpl-...","model":"gemma-4-12b-it-qat","choices":[{"message":{"content":"ok",...}}],...}
real 0m6.848s   ← HTTP 200，非 400，6.8 秒回應，跟 qwen3.6 solo 的量級相近
```

**這推翻了 round210 那條特定結論**（round211 決策文自己寫的推翻條件是
針對 qwen3.8-27b，但同一邏輯適用：後端狀態會變，不能沿用舊的「這個
model 死了」當事實引用，尤其那份判斷是一天前量的）。可能原因：對面機器
（LM Studio）目前沒有同時載入其他大模型，記憶體騰出來了；或 guardrail
設定被人類端調整過。**不知道原因，只知道現象變了，照量測寫。**

## 決定

**重開異質池路徑，但只用 `qwen/qwen3.6-35b-a3b` + `gemma-4-12b-it-qat`
兩個 model**（不含 qwen3.8-27b——四次獨立檢查一致，繼續排除）。

- **放棄了什麼**：三 model 池（原計畫含 qwen3.8-27b）放棄，因為那個 model
  目前無法服務，硬湊只會像 round211 一樣卡在 calibration 或預檢。
- **根據什麼選的**：solo curl 量測（見上），不是猜測。
- **什麼條件下該被推翻**：若 qwen3.8-27b 之後 solo curl 測試 <30s 內
  回應，要重新把它排進候選池；若 gemma 之後又變回 400/逾時，要立刻停用
  且不能拿本輪的健康快照當「它現在還活著」的證據。

## Gate H（沿用 round210 的門檻，未改）

`--calibration-n 12`，12 題與正式題不相交（`offset=len(tasks)`）。
用 round262 已修復的**序列化** `calibrate_pool()`（不再用
`ThreadPoolExecutor`，見上一個 commit），避免 round210 那次併發卡死
39 分鐘/題的重演。

- `accuracy_spread ≥ 10pp` 且兩個 model 的 `infra_void=0` ⇒ 池子有能力差可路由，
  讓後續 OFF/ON/OFF5 三臂跑下去。
- `< 10pp` 或任一 model 出現 `infra_void>0` ⇒ 前提不成立，停止，照實記。

10pp 門檻的根據沿用 round210：`--calibration-n 12` 只有 12 題／model，
樣本極小，這一步主要是**排除明顯不異質或明顯不穩定**的情況，不是精確
估計；真正的異質性量測要等主 OFF 臂（round210 prereg 的「量法二」）
在更大樣本上重新核對。

## 執行

```
VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions \
CLINE_KEYS=/nonexistent \
python3 ops/gain/gain_run.py \
  --out runs/g_het2_r263_20260829 --n 179 --seed g-r212-route-20260828 \
  --arms OFF --probe-sample 0 --calibration-n 12 \
  --models qwen/qwen3.6-35b-a3b,gemma-4-12b-it-qat \
  --request-timeout-s 600
```

`--n 179` 與 `--seed g-r212-route-20260828` 跟 `runs/g_onr_r212_20260828`
（round212 的同質池 OFF 基準）題序前綴相同，但**池子換了 ⇒ 不能跨池配對**
（round147/round155 的 G9 邊界規則同款：條件變了，基準要重量，不能比
整檔 sha 就假設一致）。這個 run 本身就是異質池的新 OFF 基準，不是要拿去
跟 r212 配對。

在背景執行（`setsid nohup ... &`），本輪之外繼續跑，下一輪先看
Gate H 結果（`summary.json.calibration`），過了才決定要不要接著跑 ON/OFF5。

## 沒做的事（照實寫）

- 沒有把 qwen3.8-27b 加回候選池。
- 沒有假設「gemma 現在能用」會一直持續——推翻條件已寫在上面。
- 沒有動 `gain_run.py`／`brain_cline.py` 除了 round262 已提交的序列化修復
  之外的任何一行。
- 沒有跳過 Gate H 直接跑正式三臂。
