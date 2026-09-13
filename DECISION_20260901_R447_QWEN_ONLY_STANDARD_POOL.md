# round447 決定：暫時把 qwen-only 六人格池訂為標準實驗池

## 背景

`gemma-4-12b-it-qat` 後端從 round442 附近的某個時間點起持續回 HTTP 400
（"Failed to load model. Error: Operation canceled."）。round446 裸測過一次
確認掛掉，本輪（round447, 2026-09-01 ~11:2x UTC）再裸測一次，**仍然
400，尚未恢復**：

```
curl gemma-4-12b-it-qat → 400 Failed to load model
```

同時，round445 之後某個未留紀錄的 local 輪次已經啟動了
`runs/g_off_qwen_only_20260901`（PID 2498340，qwen-only、OFF-only、
n=60、seed `g-r212-route-20260828`），round446 判斷它不受 gemma 影響
後決定留著繼續跑。本輪（round447）接手時它已跑了 18/60（75.0% 需求=
產出率、infra_void=2），**這是本實驗第一次落在總綱定義的 20-60% 可用
失敗率窗口內的乾淨樣本**（25% 失敗率，且失敗全是真的
`sandbox_check_failed`，不是 infra 雜訊——見下方逐行檢查）。

## 決定

**在 gemma 恢復之前，ON 與 OFF5 兩臂也用同一個 qwen-only 六人格池
（careful-1/2、plain-1/2、hasty-1/2，全部指到
`qwen/qwen3.6-35b-a3b`）跑，且沿用同一個 seed
`g-r212-route-20260828`，以便跟這個 OFF 基準做同池、同題序的等預算
比較。**

放棄的選項：
- 等 gemma 恢復再跑三臂——不確定 gemma 何時恢復，round442 之後已經
  卡了至少 5 輪（round443-447），總綱的迴圈紀律是「不要停下來等」。
- 換一個完全不同的第二模型湊異質池——目前後端只有這兩個模型可用
  （見 `brain_cline.py` POOL 註解與 round442-446 的 calls.jsonl），
  沒有第三個選項；引入沒驗證過的新後端本身也是要記錄的實驗條件改變，
  本輪不做。

## 這是判斷不是量測

qwen-only 池讓 ON/OFF5 跟 OFF 的比較乾淨（同池同 seed），但**這不是
「Vacant 機制在異質池上的表現」的答案**——round442-446 已經証實混池
（qwen+gemma）在 review 階段有真實的模型家族差異（gemma review
success rate 過去量到 22-44%，明顯低於 qwen 的 71-100%）。qwen-only
的 ON 只能回答「同一個模型自己審自己時，Vacant 的多輪／多呼叫機制
有沒有用」，答不了「異質評審有沒有用」。這點差異要留在最終結論裡，
不能把 qwen-only 的結果直接當成完整答案。

## 什麼條件下要推翻

- gemma 裸測恢復 200 且連續 3 次呼叫不逾時 → 應該考慮至少跑一個
  混池的 ON 診斷做對照（不必砍掉 qwen-only 的資料，兩份都留）。
- 如果 qwen-only 的 ON/OFF5 也在 review 階段觀察到跟 gemma 類似的
  高失敗率（懷疑是不是這個後端/timeout 設定本身有問題，不是模型家族
  的問題）→ 要重新檢查是不是 `request_policy` 設定（timeout/retries）
  而不是模型能力的問題。

## OFF 失敗的逐行檢查（n=18 為止）

15 個非 void 的 processed 行裡 4 個 `meets_demand=false`，err 全部是
`sandbox_check_failed`（不是 timeout、不是 infra_void）：
`Mbpp/305`、`Mbpp/615`、`Mbpp/267`、`Mbpp/593`——都是真的程式碼在
`plus_input` 加強測資上跑不過，不是量測雜訊。4 個裡 3 個出自
`hasty-2` 人格（「快速給出答案，以最常見情況為主」），初步方向合理
（人格設定本身鼓勵跳過邊界情況）但 n 太小（該人格目前只跑了 6 題），
不構成結論，留給 n 更大時再看。

infra_void 的 2 筆（`Mbpp/123`、`Mbpp/773`）都是 qwen 本身重試 4 次
仍 400——證實 round446 記錄的「qwen 在 gemma 死亡期間也曾短暫回
400/500」不是巧合個案，是這個後端偶發的錯誤率，會持續產生一定比例
的 infra_void，需要繼續跟 accepted/meets_demand 分開算，不能混進失敗率。

## 下一步（不在本輪內做，避免跟現有 run 搶後端）

`g_off_qwen_only_20260901` 跑到 n=60（或至少 n≥40 有把握判斳窗口）
之後，**依序**（不要同時）啟動：

```bash
VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions \
CLINE_KEYS=/nonexistent \
python3 ops/gain/gain_run.py --out runs/g_on_qwen_only_20260901 \
  --n 60 --arms ON --seed g-r212-route-20260828 \
  --models qwen/qwen3.6-35b-a3b --request-timeout-s 600

# ON 跑完（或跑到夠大的 n）之後才跑 OFF5，同理不要並行：
python3 ops/gain/gain_run.py --out runs/g_off5_qwen_only_20260901 \
  --n 60 --arms OFF5 --seed g-r212-route-20260828 \
  --models qwen/qwen3.6-35b-a3b --request-timeout-s 600
```

啟動前務必按總綱的規則跑
`ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py"` 確認為 0
（不要用 `pgrep -f`，見總綱鐵律）。
