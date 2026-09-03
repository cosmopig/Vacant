# R440R：CONFORM 實跑預註冊——`runs/g_r444_conform_mbpp`

（2026-09-03，Fable 5.1。**發射前寫定，預測寫在前面，跑完不准改。**
run 名 `runs/g_r444_conform_mbpp` 即 R440G 閘門所需的授權。
機制與證據見 `DECISION_20260903_R440P_CONFORMANCE_GATE.md`，實作見 round440q。）

## 一、這個 run 要回答什麼

R440P 的所有數字都來自**離線重放**（拿 OFF5 已經抽好的 5 個候選來模擬 CONFORM 的選擇）。
重放有兩個它自己答不了的問題：

1. **真跑是循序抽樣**，每次揭露一位 worker、拿到草稿才決定要不要再抽下一位；
   重放是在「已經抽完 5 個」的池子上倒推。抽樣過程一樣，但**信譽路由與 rng 消耗不同**。
2. **收據鏈只有真跑才有**。重放沒有簽章，也就沒有「可事後查核」這件事。

因此：**唯一與 E1 不同的是把 ON 換成 CONFORM，其餘逐字相同**（同 seed、同題庫、同模型、
同 request_policy、同 `--probe-sample 0`）。這讓 CONFORM 可以同時對照 E1 的 ON 與本 run 的 OFF5。

## 二、發射指令

```
cd ~/vacant/Vacant && \
PYTHONUNBUFFERED=1 VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions CLINE_KEYS=/nonexistent \
setsid nohup python3 ops/gain/gain_run.py --out runs/g_r444_conform_mbpp --n 179 \
  --decision DECISION_20260903_R440R_CONFORM_LIVE_PREREG.md \
  --seed g-r212-route-20260828 --arms OFF,CONFORM,OFF5 --bank evalplus \
  --models gemma-4-12b-it-qat \
  --request-timeout-s 600 --review-timeout-s 380 --probe-sample 0 \
  >>runs/g_r444_conform_mbpp.launch.log 2>&1 < /dev/null &
```

E1 的對照組（`runs/g_r441_gemma_only_mbpp_b`）：OFF 68.16%／ON 73.05%／OFF5 73.74%，
ON vs OFF5 b=11 c=12 p=1.0000。

## 三、預註冊預測（跑完對答案）

| # | 預測 | 根據 |
|---|---|---|
| **P-C1**（主結論，等預算） | CONFORM 通過率 **高於 OFF5 +3 到 +6pp** | 重放在同一批候選上量到 +4.47pp（b=13 c=5） |
| **P-C1b**（顯著性） | McNemar **p 落在 0.02–0.20**，很可能仍不顯著 | 重放 p=0.0963；n=179 的檢定力就是這樣 |
| **P-C2**（預算軸） | CONFORM 的 `calls_per_task` **≤ 2.0** | 重放 1.34；真跑循序抽樣應相近 |
| **P-C3**（拒交） | 拒交率 **3–10%**；`leaked` **明顯低於 OFF5**（E1 的 OFF5 是 47） | 重放 8/179 題無任何候選通過可見驗收 |
| **P-C4**（收據） | 收官時每一列都有 `receipt_head`，且該臂的鏈 `verify_chain` 為真 | round440q 的單元測試已驗過機制 |
| **P-C5**（infra） | CONFORM 臂 void 率 **< 20%** | E1 gemma 單獨在卡上是 6.70%；CONFORM 沒有 review 那條長 context 路徑，應更低 |

**這個 run 算成功的定義（R440B「足夠有效」的本階版本）**：
P-C1 **且** P-C2 同時成立——**在等預算下贏，而且實際只花了 1/4 的預算**。
只有 P-C2 成立（便宜但沒比較準）也是有價值的結果，但那時要照實說「CONFORM 買到的是成本
不是準確率」，不准講成機制有效。

## 四、中止準則

- 任一臂 infra_void > 20% ⇒ 中止，先修 infra（R440 沿用）。
- CONFORM 的 `calls_per_task` > 4.5 ⇒ 早停沒有發生（多數題目都要抽滿），
  重放與真跑有結構性差異，停下來查為什麼。
- 收官時 `verify_chain` 為假 ⇒ 收據鏈壞了，這個 run 的究責宣稱全部作廢。

## 五、誠實邊界（沿用 R440P §五，逐條有效，不重寫）

需求必須可編譯成可執行驗收；「可見篩選無損」部分是 MBPP+ 題庫性質；準確率提升可能不顯著；
與 E1 共用 seed 但不是獨立樣本；重放與真跑的標籤來源不同。
**額外一條**：CONFORM 沒有 review 呼叫，所以它**不產生**評審準確率、反例精確度那些指標——
summary 裡那些欄位會是 null，不是壞掉。

## 六、什麼條件下這個裁決該被推翻

- CONFORM 在真跑打不贏 OFF5 ⇒ 以真跑為準，R440P §四 的裁決要重開，
  並去查重放與真跑差在哪（最可能是循序抽樣的 worker 分佈與 OFF5 不同）。
- `calls_per_task` 接近 5 ⇒ 早停的節省是重放的假象。
- 若之後在 LCB（可見／隱藏關係不同的題庫）量到「可見篩選無損」被打破，
  拒交規則要改成「交出最佳者並標記未驗收」而不是純拒交（R440P §七 第一條）。

## 七、排程

`ops/gain/launch_conform.sh` 在 vacant-dev 背景等 E3（`g_r443_gemma_lcb`）自然退出，
然後：單 run 檢查 → gemma 探針 3/3（驗 body 非只驗 200）→ 目錄與 launch.log 未占用 →
發射 → 等 preflight ✓。全程寫 `~/vacant/logs/launch_conform.log`，
最後一行 `CONFORM_LAUNCH_RESULT=...` 是機器可讀結論。
**E3 未收官前不發射**（SPEC_GAIN §7 一端點一 run）。
