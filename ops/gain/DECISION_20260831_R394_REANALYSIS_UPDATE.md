# round394（2026-08-31）：round393 重放結果在更新的 n 下複驗，572 不吻合的成因排查

## 做了什麼

1. 決定性 run（PID 2266603）確認存活（開場 elapsed 60223s，收尾仍存活）。
2. 重跑 `ops/gain/reanalyze_typing_fix_r393.py`（零模型呼叫，離線重放
   `runs/g_r356_3arm_20260830/calls.jsonl`），資料進度從 round393 查證時的
   OFF=95/ON=76/OFF5=88 前進到 OFF=96/ON=77/OFF5=89。
3. 配對重算 ON vs OFF5 主判準。
4. 排查 round393 留下的 `mbppplus_Mbpp/572` 重放不吻合（bucket 重建近似
   誤差，見 round393 文件）。

## 結果 1：round393 的方向在 n 增加後複驗，數字幾乎沒動

```
                    n_paired=70(round393)   n_paired=71(本輪)
ON  需求=產出         57/70 = 81.4%           58/71 = 81.7%
OFF5 需求=產出        55/70 = 78.6%           56/71 = 78.9%
discordant (b,c)      (4, 2)                  (4, 2)
McNemar p              0.6875                  0.6875
gap (ON − OFF5)       +2.86pp                 +2.82pp
```

**discordant pair 完全沒變**（4,2 → 4,2，新增的 1 題是 concordant）。方向
與 round393 一致：typing 白名單修好後 gap 從偏誤前的 0.00pp 移動到約
+2.8pp，但 p 值仍遠不顯著。**這不是新結論，是既有結論在更多樣本下站得住。**

## 結果 2：`mbppplus_Mbpp/572` 的重放不吻合——排除了兩個假說，成因仍未定

現象：`arm_off5` 在決定性 run 實際跑出的紀錄是 `vote_agreement=4,
n_buckets=2`（5 份候選碼裡 4 份同票）；離線重放這 5 份已落盤的候選碼，
用同一套 `behavior_signature` 邏輯、同一份 `OLD_IMPORTS` 白名單，重建出
`n_buckets=2` 但票數是 `3+2`（3 份 Counter/一行版本同票、2 份 typing 版本
因白名單被擋同屬 EXEC_FAIL），不是 `4+1`。

排查了兩個可能成因，都排除：

1. **不是取碼順序或候選數量錯誤**——直接從 `calls.jsonl` 撈這題 OFF5 的
   5 筆 `role=gen, ok=True` 呼叫，agent 順序 `careful-2, careful-2,
   careful-2, plain-2, hasty-1` 與該列 `involved` 欄位逐字元相同，没有
   多餘或缺漏的呼叫。
2. **不是目前環境的沙箱非決定性**——把這 5 份候選碼在目前環境下重跑
   `behavior_signature` 三次，三次都得到一致的 `2+3` 分票，不是 `4+1`，
   排除「時序敏感、重跑會抖動」的假說。
3. **不是決定性 run 存活期間 `vacant/checks.py` 被改過**——
   `git log --since=2026-08-30 -- vacant/checks.py` 沒有任何提交；決定性
   run 於 2026-08-30 17:53:48 UTC 啟動，`checks.py` 的沙箱邏輯全程未變。

**成因仍未定**：唯一還沒排除的可能是決定性 run 實際執行當下的某種
一次性資源競爭（例如與同時段其他呼叫搶佔沙箱 worker、產生一次無法
重現的 transient 分類結果），但這是猜測，不是驗證過的結論。**不下
「就是這樣」的結論**，因為沒有辦法回頭重現當時的系統負載狀態。

## 影響評估：不改變任何結論

這是 89 題裡的 1 題（1.1%），且 `reanalyze_typing_fix_r393.py` 本來就只
拿這個自我檢查來**校準重放方法論的可信度**，不是用它去覆蓋正式結果。
`OFF5` 這題本身的 `old_truth=False`（決定性 run 記錄的官方結果）完全
沒有被本次排查更動；本文件只是誠實記錄「重建方法論在 88/89 題精確
吻合、1 題成因未明」，不影響上面「結果 1」的配對主判準。

## 推翻條件

若之後同一種不吻合在別的題目重複出現（不再是 1/N 而是一群），
表示這不是一次性事件，`reanalyze_typing_fix_r393.py` 的 OFF5 近似重建
方法論本身要重新檢討，而不是繼續當成可忽略的雜訊。

## 下一步（建議，非本輪已完成）

沿用 round393 的建議：等決定性 run 跑到 179/179 全量後重跑
`reanalyze_typing_fix_r393.py` 拿完整 n 的重放結果；是否要另開一支
在修好量具下從頭跑的乾淨 run，仍是待決策的判斷（見 round393 文件），
本輪未新開（避免跟決定性 run 搶同一個後端造成延遲污染，SPEC_GAIN §7）。
