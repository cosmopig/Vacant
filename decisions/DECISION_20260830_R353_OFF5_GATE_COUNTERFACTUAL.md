# DECISION round353：CONCLUSION 點名的「最關鍵缺失對照臂」其實不用新開實驗

**2026-08-30 UTC ~17:00-17:10，Sonnet 5。**

## 背景

`CONCLUSION_20260830_G_EXPERIMENT.md` 第95-101行把「OFF5 + 同一道免費可見測試閘」
列為「最關鍵、目前不存在的對照臂」，並寫「這是下一個該跑的實驗，在跑完之前上面的
漏出量結論只能維持現在的措辭」——語氣上暗示需要**再開一個新的實驗跑**。

## 發現

讀 `ops/gain/gain_run.py:243-280`（`arm_off5`）發現 round342 已經把這件事的資料
收集埋好了：`behavior_signature()` 早就對多數決選出的候選跑過一次可見測資
（零額外模型呼叫），round342 把這個結果存進 `extra["visible_ok"]`，而
`extra` 字典會被原封不動寫進 `rows.jsonl`（`gain_run.py:1055-1058`，
排除清單只有 `votes`/`raw_reviews`/`initial_code`）。

驗證：
```
runs/g_onoff5_371_r123_20260825/rows.jsonl   OFF5 rows=353  有 visible_ok 欄位=0（round342 之前的 run）
runs/g_het3_r278_20260829/rows.jsonl         OFF5 rows=115  有 visible_ok 欄位=0（round342 之前的 run）
runs/g_r342_3arm_20260830/rows.jsonl         OFF5 rows=2    有 visible_ok 欄位=2
runs/g_r345_3arm_20260830/rows.jsonl         OFF5 rows=5    有 visible_ok 欄位=5
runs/g_r348_3arm_20260830/rows.jsonl         OFF5 rows=7    有 visible_ok 欄位=7（決定性 run，持續 append 中）
```

⇒ **不需要新開一個實驗**。決定性 3-arm run（PID 2256011，`runs/g_r348_3arm_20260830`）
本來就在累積這個對照臂需要的資料，只是還沒有人把它拿出來算。

## 本輪做的事

寫 `ops/gain/analyze_off5_gate_counterfactual.py`：純離線讀 `rows.jsonl`，
重算「若 OFF5 的 `accepted` 改用 `visible_ok`（現行程式碼裡沒被使用的欄位）
而不是恆真」的反事實漏出率，跟 OFF5 現行漏出率、ON 現行漏出率放同一張表。

首次執行結果（round342/345/348 三個 run 池化，OFF5 n=14，ON n=15）：

```
OFF5 現行（accepted 恆 True）      n_accepted=14/14  漏出=2  漏出率=0.1429
OFF5 反事實（accepted:=visible_ok） n_accepted=13/14  漏出=1  漏出率=0.0769
ON   現行                          n_accepted=10/15  漏出=0  漏出率=0.0000
```

## 為什麼現在不能下結論

n=14/15 是目前**所有**已收集資料，不是抽樣選擇——但這個量級任何方向的差異都在噪音
範圍內（1 個漏出 vs 0 個漏出）。這只是**管線驗證**：證明腳本邏輯正確、欄位確實
存在、可以隨決定性 run 累積直接重跑，不是一個可以拿來下結論的量測。

## 這條路徑會被什麼推翻 / 什麼時候可以下結論

- 決定性 run（PID 2256011）跑完或累積到 OFF5 n≥50 這個量級時，重跑
  `python3 ops/gain/analyze_off5_gate_counterfactual.py`。
- 若反事實漏出率收斂到接近 ON 現行漏出率 ⇒ CONCLUSION 第82-83行「這場比較
  實際上是有免費閘門的臂 vs 被禁止棄權的臂」的推論成立，Vacant 機制在漏出量
  這件事上不用新對照臂就能被證明沒有超出免費閘門的加值。
- 若反事實漏出率仍明顯高於 ON ⇒ 差額才是機制的真貢獻，這時候才需要考慮
  CONCLUSION 原本設想的「真的另開一個 OFF5+gate 專屬 run」（例如要更大 n
  才能達到統計檢定力，決定性 run 的 OFF5 臂樣本數受限於 `--n 179`）。
- 這個分析**不需要修改 `gain_run.py`**、**不需要新的模型呼叫**，純粹是
  離線重算已經落盤的資料，可以在任何一輪、任何模型層級（含 local）重跑。

## 沒做的事

- 沒有修改 `gain_run.py` 的 `accepted` 語意（那會改變決定性 run 進行中的
  runtime 行為，round342 註解已明講「只記錄，不改 accepted 語意」的理由）。
- 沒有等決定性 run 跑到 n≥50 才收工——那需要遠超過一輪的時間，照
  `vacant-loop-never-end-turn-to-wait` 的教訓不應該在回合內空等。
- 沒有動 PID 2256011、沒有重開任何 run。
