# R440Z：CONFORM 在 LCB v2（120 題）上的實跑預註冊——`runs/g_r447_conform_lcb2`

（2026-09-04，Fable 5.1。人類 09-04 指示「都做都做」；本文件在發射前寫定，預測寫在前面，
跑完不准改。run 名 `runs/g_r447_conform_lcb2` 即 R440G 閘門所需的授權。
排程：等 `g_r446_eq5_mbpp`（迴圈的等預算臂，371 題）自然退出後才發射——SPEC_GAIN §7 一端點一 run。）

## 一、要回答什麼

R440X §五 說 MBPP+ 這條路走到底（MDE 需 491 題 > 378）。換題庫是三條路之一。
LCB v2（round440y-b）＝v1 的 91 題＋test4 視窗新增 29 題＝120 題，sha256 `b98f0272…`，
v1 常數不動，12 題量具參考解全部落在 v2 內。

E3（v1，91 題）已量到：OFF 失敗率 48.4%、ON vs OFF5 p=0.4244、**可見篩選在 LCB 上無損 0/455、
早停 vs 單抽 +20.88pp b=19 c=0**（R440T §八）。但那是離線重放 OFF5 的候選，
**CONFORM 這條臂從沒在 LCB 上真跑過**。本 run 補這一塊，且 n 從 91 到 120。

## 二、發射指令（唯一與 E3 的差別＝把 ON 換成 CONFORM、bank 換成 lcb2）

```
cd ~/vacant/Vacant && \
PYTHONUNBUFFERED=1 VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions CLINE_KEYS=/nonexistent \
setsid nohup python3 ops/gain/gain_run.py --out runs/g_r447_conform_lcb2 --n 120 \
  --decision DECISION_20260904_R440Z_LCB2_PREREG.md \
  --seed g-r440-lcb2 --arms OFF,CONFORM,OFF5 --bank lcb2 --models gemma-4-12b-it-qat \
  --request-timeout-s 600 --review-timeout-s 380 --probe-sample 0 \
  >>runs/g_r447_conform_lcb2.launch.log 2>&1 < /dev/null &
```

量具：`--arms probe --bank lcb2 --probe-sample 0` 本機零 API 已過——參考解 12/12、壞解被擋 12/12、
可見閘門 12/12（覆蓋 12/12）。**覆蓋率只有 12/120，不是全題庫**（LCB 沒有官方解，R441 的邊界）。

## 三、預註冊預測

| # | 預測 | 根據 |
|---|---|---|
| **P-Z1**（H-B 前提再驗） | OFF 失敗率 **40–60%** | E3 v1 是 48.4% [38.4, 58.5]；新增 29 題含一題 2023 的（lcb_3026），難度分佈應相近 |
| **P-Z2**（主結論，早停 vs 單抽） | CONFORM 對 OFF 配對 **b ≫ c，p < 0.01**，差 **+12 到 +25pp** | E3 離線重放 +20.88pp b=19 c=0；真跑循序抽樣、worker 分佈不同，取寬一點 |
| **P-Z3**（vs OFF5） | CONFORM 對 OFF5 差 **+2 到 +8pp**，**p 很可能仍 > 0.05**（n=120） | E3 重放 +4.40pp p=0.424；MBPP+ 三個資料集都同號不顯著 |
| **P-Z4**（預算） | CONFORM `calls_per_task` **1.5–2.2** | E3 重放 1.78（難題通過率低 ⇒ 多抽） |
| **P-Z5**（拒交） | 拒交率 **5–12%**，且拒交的題目裡「五份全錯」佔 **≥ 80%** | E3 重放 6/91 全部本來就無解；真跑可能有少數可救的被拒 |
| **P-Z6**（無損性，真跑版） | rows 裡 **沒有** `visible_ok=False` 且 `meets_demand=True` 的列 | 三個資料集 0/2085；這是 R440P 拒交規則成立的前提 |
| **P-Z7**（infra） | 任一臂 void **< 20%**；CONFORM 臂 void **< 5%** | E3 ON 4.4%；CONFORM 沒有 review 長 context 路徑 |
| **P-Z8**（收據） | 每列有 `receipt_head`，`receipts_CONFORM.ndjson` 落盤且 `verify_chain` 為真 | round666 修好、r445 已驗過 482 條 |

**本階「足夠有效」**：P-Z2 成立（早停在難題上顯著贏單抽）**且** P-Z6 成立（無損）。
P-Z3 不顯著不算失敗——n=120 本來就分不出 ±5pp（R440 §誠實邊界 3）。

## 四、中止準則

- 任一臂 infra_void > 20% ⇒ 中止先修 infra。
- P-Z6 被推翻（出現可見沒過但隱藏過的列）⇒ **立刻**記錄，這是 R440P §七 第一條推翻條件在真跑上兌現，
  拒交規則要改成「交出最佳者並標記未驗收」。跑完再改，不中途改臂。
- OFF 失敗率 > 70% ⇒ 題庫太難，配對失去意義，照實記。

## 五、誠實邊界

1. n=120，McNemar 只辨得出 ~12pp 級不對稱；P-Z3 的「不顯著」不等於等效。
2. **量具只覆蓋 12/120**，其餘 108 題的隱藏測資沒有參考解證明「正解會通過」。
3. **lcb_3026 的 contest_date 是 2023-08-26**，比 v1 視窗早一年，污染定界對它無效（round440y-b）。
4. lcb_3763（separateSquares）浮點假陽性仍在池內；lcb_3613 亦在 `check_bank_precision` 的 KNOWN_BAD。
   若這兩題三臂全滅，先查量具不查模型。
5. 與 E3 共用 91 題，**不是獨立樣本**；跟 E3 的數字比較是「同題庫加了 29 題」不是複製。

## 六、推翻條件

- P-Z2 不成立（早停對單抽 p ≥ 0.05 或 c ≥ b/2）⇒ E3 那個 +20.88pp 是重放假象，
  真跑循序抽樣拿不到，R440P §三「題目越難早停越值錢」要收回。
- P-Z6 被推翻 ⇒ 見 §四。
