# round350：跨 run 彙總 OFF 基準，用大樣本重新核對判準 1——不是新實驗，是既有結論的加固

## 為什麼做這個

`g_r348_3arm_20260830`（post-fix 決定性 run）本輪只從 10 列長到 11 列
（PID 2256011，`etimes`≈58 分鐘），單一 run 太慢，量不出新的配對比較。
與其空等，本輪核對「判準 1：OFF 失敗率 20–60%」能不能用**所有歷史 OFF
資料**（不只 `CONCLUSION_20260830_G_EXPERIMENT.md` 引用的兩個子集）加固到
更穩的信賴區間。

**前提檢查（先確認可以合併，不是假設）**：round347 修的 `codebench.py`
dedent bug 只影響 `verify_review_counterexample`（`gain_run.py:310`），
只在 ON 臂的 review 路徑被呼叫（`gain_run.py:483`）。`meets_demand`
（`gain_run.py:96`）走的是 `hidden_check`，跟 `verify_review_counterexample`
完全是兩條獨立路徑——grep 全檔確認 `meets_demand` 的定義與呼叫點都不
經過 `verify_review_counterexample`。**OFF 臂本來就不呼叫 review**，
所以 OFF 的 `meets_demand` 結果在 pre-fix／post-fix 之間沒有差異，可以
直接合併當同一個母體的獨立抽樣。

## 方法

掃描 `runs/g_*/rows.jsonl`（純離線讀檔，不呼叫任何模型），對每一列
`arm=="OFF"` 取 `meets_demand`，跨 12 個 run 彙總：

```
g_het2_r263_20260829      n=177  pass=128  rate=0.723
g_local_smoke_20260824    n=3    pass=3    rate=1.000
g_off371_20260825         n=367  pass=288  rate=0.785
g_off60_local_20260824    n=13   pass=11   rate=0.846
g_off60_qwenonly_20260824 n=60   pass=47   rate=0.783
g_off60_relay2_20260824   n=8    pass=7    rate=0.875
g_off60_relay_20260824    n=42   pass=30   rate=0.714
g_onr_r212_20260828       n=179  pass=145  rate=0.810
g_r342_3arm_20260830      n=7    pass=3    rate=0.429
g_r345_3arm_20260830      n=5    pass=3    rate=0.600
g_r348_3arm_20260830      n=5    pass=1    rate=0.200  ← 本輪查時的即時進度
g_smoke_20260820          n=6    pass=6    rate=1.000

TOTAL  n=872  pass=672  fail=200  fail_rate=22.94%
Wilson 95% CI（z=1.96）: [20.27%, 25.84%]
```

## 結論

判準 1（OFF 失敗率 20–60%）在 n=872 的信賴區間 [20.27%, 25.84%] **完全
落在窗口內**，比 `CONCLUSION_20260830_G_EXPERIMENT.md` 原引用的兩個子集
（n=362／n=177）樣本大 2.4–4.9 倍，結論不變但更穩固。**注意下界貼近
20%**——這些 run 橫跨不同 model pool（有些純 qwen、有些 het2/het3 混合
gemma）、不同 seed，異質性本身就是彙總樣本比單一 run 更能代表「這個
量測窗口普遍存在」的證據，但也意味著若之後只用單一模型池重跑，失敗率
可能會落在區間邊緣甚至略低於 20%——不是這個彙總本身有問題，是不同池子
難度不同。

## 附帶檢查：post-fix run 目前 3 筆 ON 列的 review 邏輯讀碼確認

順手讀了 `g_r348_3arm_20260830/rows.jsonl` 目前僅有的 3 筆 ON 列
（`Mbpp/296`／`Mbpp/425`／`Mbpp/615`），其中 `Mbpp/615` 有兩個 reviewer
給出 `raw_pass=false` 但 `status=unparseable_claim`（反例文字無法被
機器解析執行），`counterexample_confirmed=false`，因此
`grounded_pass=true`。**這不是新 bug**——讀 `gain_run.py:487-490` 的
程式碼註解確認這是刻意設計：「PASS remains approval. FAIL counts only
with a machine-confirmed counterexample; unsupported accusations are
abstentions resolved in favor of the submitted code.」round347 修的是
`verify_review_counterexample` 內部因縮排導致**保證**回傳 unconfirmed
的 bug，不是「unconfirmed 時要不要 abstain in favor of candidate」這條
設計本身。3 筆樣本太小，看不出 post-fix 之後 `counterexample_confirmed`
的真實觸發率有沒有變高，需要等 `g_r348` 累積更多 ON 列。

## 沒做的事

- 沒有動 `g_r348_3arm_20260830`（PID 2256011）——健康繼續跑，本輪純離線
  分析既有落盤資料，不影響它。
- 沒有把這個彙總數字寫進 `CONCLUSION_20260830_G_EXPERIMENT.md` 取代原數字
  ——原文件的兩個子集數字是特定 run 的乾淨配對分析基礎，這裡的 872 是
  跨異質池彙總，用途不同（判準 1 的穩健性檢查，不是配對比較的分母），
  兩者並存，不覆寫。
- 沒有因為看到 `unparseable_claim` 就當成新發現去修——讀程式碼註解確認
  是既有設計後就停手，避免把一個本來就對的設計誤判成 bug。

## 下一輪要做的

1. 繼續監看 `g_r348_3arm_20260830`（PID 應仍是 2256011，不要重開除非死了）。
2. ON 列數 ≥10 之後，可以開始看 `counterexample_confirmed=true` 的觸發率
   是否明顯高於 round347 反事實重算算出的 pre-fix 38.4%（R278 子集）——
   但要記得那是離線重算不是即時 run 出來的，量測方式不同，只能當方向性
   對照，不是同一把尺。
