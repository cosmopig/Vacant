# DECISION 2026-08-31 round371 — ON 臂 void 率突破 10% 閘門，根因是呼叫量結構性曝險

## 背景

`g_r356_3arm_20260830` 這個決定性 run 在本輪（round371）首次三臂全部
達到 n≥30 的門檻（OFF=35, ON=30, OFF5=33），觸發跑正式分析
（`analyze_paired.py` ×2、`analyze_off5v.py`、`analyze_reviewer_family.py`）。

## 發現

`analyze_paired.py` 印出 `⚠ VOID-GATE-WARNING`：

- ON void 率 = 18.9%（7/37）—— **超過 SPEC_GAIN §7 的 10% 閘門**
- OFF void 率 = 5.4%（2/37）
- OFF5 void 率 = 8.3%（3/36）

逐筆核對 `notes.jsonl` 裡 ON 臂的 7 筆 `infra_void`：**全部 7 筆都是
`HTTPError: HTTP Error 400: Bad Request`**，跟 round370 在
`ops/localagent.py` 排查到的「同一 request body 重試全部 400（結構性，
不是暫時性路由雜訊）」是同一種錯誤代碼，但發生在
`ops/gain/brain_cline.py` 的呼叫路徑上（不是 `ops/localagent.py`）。

## 判斷：這是結構性曝險差異，不是隨機噪音

ON 臂平均每題 5 次呼叫（`avg_calls=5.00`），OFF 臂平均每題 1 次
（`avg_calls=1.00`），OFF5 也是約 5 次但用不同的路徑組合。**ON 每題
呼叫次數最多，命中「同一 body 觸發 400」這個結構性 bug 的機會也最多**
——這解釋了為何三臂的 void 率排序是 ON(18.9%) > OFF5(8.3%) > OFF(5.4%)，
跟三臂的呼叫量排序一致。這不是說 ON 本身比較容易失敗，而是**呼叫量
越大，越容易撞到這個獨立於實驗設計之外的後端 bug**。

## 這對三條「有成效」判準的影響

1. 量測有訊號 ✓（不受影響）
2. 三臂有差異：**本 run 內部尚不能下結論**——`analyze_paired.py` 兩次
   配對檢定（ON vs OFF、ON vs OFF5）McNemar p 都是 1.0000，**不顯著**；
   `analyze_off5v.py` 的 OFF5V vs ON 配對（n=27）gap=11.11pp 但
   `insufficient_n`（n<30，只能報點估計）。
3. 等預算答案：ON vs OFF5 在本 run 目前呼叫數相同（135 vs 135，
   `等預算：True`），ON 需求=產出 70.37% vs OFF5 66.67%，**方向上 ON
   略優但統計不顯著**（p=1.0000，n=27 太小）。**這是目前最接近「答出
   等預算問題」的證據，但因為 ON void 率超標，屬於探索性數字，不得
   引用為結論性判讀**（沿用 round357 `DECISION_20260830_R357_R278_VOID_BOUND_CAVEAT.md`
   訂的原則）。

`analyze_reviewer_family.py` 印出 `⚠ VOID-GATE-DISQUALIFIED`，其
same-family vs different-family 準確率數字（74.29% vs 69.09%，真失敗題
抓到率 30.77% vs 0%）**同樣只能當探索性線索**，不能拿來確認或推翻
round352 的「同家族盲區」假說。

## 決定：不暫停 run、不修 brain_cline.py 的 400 重試邏輯，繼續累積 n

理由：
- round356 已經判斷這類 400 是「同題換一次呼叫/context 通常會過」
  （24/29），`brain_cline.py` 這條路徑目前的重試邏輯（2-4 次）本身沒有
  被新證據推翻——本輪只是首次看到它在 ON 臂造成的**累積**曝險超過
  10% 閘門，不是重試邏輯本身失效。
- 繼續累積 n（run 目標是 179 題／臂約 60），void 率是否會隨 n 增加而
  改善或惡化，本身就是有用的資訊——不需要靠修改程式碼去人為壓低它。
- 若之後 void 率持續 >10% 且 n 已經足夠大到讓「探索性」變成「這就是
  常態」，才需要認真評估是否要在 `brain_cline.py` 加大重試次數或加入
  round370 討論過的對話歷史裁剪。

## 推翻條件

- 若 ON 臂 void 率隨 n 增加持續惡化（不是穩定在 15-20% 而是趨勢上升），
  代表不是隨機曝險而是某種隨 run 時間變化的後端劣化，屆時要重新評估
  是否暫停 run 排查。
- 若 OFF 或 OFF5 的 void 率也突破 10%，代表根因不是「呼叫量越大曝險
  越大」這個結構性解釋，要重新排查。
