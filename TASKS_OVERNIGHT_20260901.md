# 過夜任務單（2026-09-01 → 09-02 早上；主 session 的 Mac 18:00 關機，迴圈接手）

給 vacant-dev 迴圈（每輪 pull 會看到）。**做完一項就在本檔打勾並 commit**，
沒做到的寫原因，不要刪任務。模型分工照 LOOP_PROMPT 政策：收數字 sonnet、
裁決/稽核 fable、改碼 opus。

## A. G 實驗（feat/v2-four-stages）
- [x] A1 E1 發射狀態：依 R440E 人類三選一的結果，記錄實際發生的（載入結果、探針 3/3、
      發射時間、PID）。人類未決前**不動 1004**。
      **round466 (2026-09-02 ~04:45 UTC) 複查：仍未決。** 1004 現況
      （`curl .../api/v1/models`）：`qwen_qwen3.6-35b-a3b` 已載入
      （非 R440E 記錄的 qwen3.8——已換過一次，但同樣不是 gemma）、
      `qwen/qwen3.8-27b` 與 `gemma-4-12b-it-qat` 均未載入。gemma 未載入
      ⇒ E1（以及同樣需要 gemma 的 E2/E3）都還沒能發射。round466 沒有對
      1004 做任何載入/卸載嘗試（遵守「1004 只能人類動」）。改跑不需要
      gemma 的 E2q（qwen-only + LCB bank）先答 H-B 半題，見
      `DECISION_20260902_R466_E2Q_QWEN_ONLY_LCB_WHILE_1004_BLOCKED.md`。
      **round467 (2026-09-02 ~04:49-05:0x UTC) 更新：round466 收尾沒做完
      （沒 commit/push），peer session（Fable，round440f）透過遠端只看
      到「無 DECISION 的孤兒 run」，正確地依當時可見資訊判定違規並要求
      處置。round467 核對後：E2q 的實測延遲（289秒/呼叫）是 round466
      估計（10秒/呼叫）的 29 倍，91 題 ETA 從「15-25 分鐘」變成
      「~7.3 小時」——且它佔用的正是 1004 上擋住 gemma 的那個模型實例。
      **已 `kill -TERM` 終止**（1/91 題已寫入，目錄保留未刪）。1004 仍是
      `qwen_qwen3.6-35b-a3b` 已載入、gemma 未載入，仍在等人類三選一。
      詳見 `DECISION_20260902_R467_RECONCILE_R440F_AND_TERMINATE_E2Q.md`。
      **round468 (~05:04-05:1x UTC) 複查：1004 狀態不變，仍在等人類。
      同時讀到 peer session（Fable）又推的三個 commit
      （round440e/f/g/g-fix/h）：E1 發射不歸迴圈已明文寫進
      `ops/LOOP_PROMPT.md`（第 6 點：人類決定落地前 8765 上不得起任何
      gain_run），且新增了 `--decision` 硬閘門到 `gain_run.py`。本輪
      未起任何 run、未動 1004。**
      **round472 (09:33 UTC) 更新：人類已完成三選一，1004 切成 gemma-only，
      E1（`runs/g_r441_gemma_only_mbpp_b`，PID 2572085）成功發射。**
- [x] A2 E1 每 60 題一個檢查點（sonnet）：OFF 失敗率、void 率、ON/OFF5 配對 b/c、
      評審準確率−almost-PASS；void>20% 立刻停手寫 DECISION（R440 中止準則）。
      **round473-481：9 次淺層同步（複製 summary.json 數字）。round482：第一次
      完整檢查點——OFF 失敗率 33.0%（在窗口內）、ON void 3.1%（遠低於中止線）、
      ON/OFF5 配對 b=8/c=5/p=0.5811、評審準確率(grounded) 0.7708 vs 基線
      0.7083（差 +6.25pp，數字見 GAIN_STATE.md round482）。**
- [x] A3 E1 ≥90 題時起一次 **fable 稽核輪**：重算配對表、核 rows.jsonl 行數＋sha256 前 8 碼、
      對照 R440 的 P1–P4 逐條打分。
      **round482 複查：295 行早過 90 題門檻，但至今零次由 fable 執行。
      本輪（sonnet）不越權代做判斷，已把 `下一輪模型` 設為 fable。仍未完成，
      不打勾。**
      **round516（Fable 5.1，21:00 UTC）補做：`DECISION_20260902_R516_E1_FINAL_WRAPUP.md`。
      E1 終態（179/167/179，ON void 6.70%≤10%）套用 R483 §3d 判準：grounded 評審
      bootstrap 下界=0.00（不>0）、ON vs OFF5 McNemar p=1.0000（不贏 self-consistency）
      ⇒ CONCLUSION 不動。round529 補打勾（此前漏更新）。**
- [x] A4 07:00（台北）寫 `MORNING_20260902.md`：一頁摘要——E1 進度、階梯下一階建議、
      被擋的指令清單（如有）。
      **round482 更新：round466 版內容已過期（寫於 E1 發射前），本輪重寫反映
      E1 已發射且健康的現況。**

- [x] A5 **兩個 Mac session（本單作者與「vacant」稽核 session）都在 18:00（台北）隨 Mac 下線；
      過夜只有迴圈。** 迴圈在**下線後的下一個 07:00（台北）**寫 `MORNING_<當天 YYYYMMDD>.md`
      （日期用 vacant-dev 本機 `date +%Y%m%d` 換算台北時間，不要猜），格式同 A4，
      **每個數字附 rows.jsonl 行數＋sha256 前 8 碼**；E1 若已由人類發射，A2/A3 由迴圈執行
      （fable 層、閘門、E1 視窗規則六條都已就位）。人類未發射則寫「E1 未發射，等 1004 決定」。
      **round482：MORNING 檔已補寫（見上），數字附 rows.jsonl 行數(295)＋sha256
      前 8 碼(59a35fd6)。A3 仍待 fable 執行，見上。**

## B. 展覽產線（vacant_hm，win1003 自立收割）
- [ ] B1 win1003 會把 A14B 場景 loop 推到 `vacant_hm` 分支 `night-scene-20260901`
      （含 world3/scenes/MANIFEST.json）。迴圈只做**唯讀驗證**：`git ls-remote` 看到分支後，
      pull 到暫存目錄，核 MANIFEST 的 ok 數／幀數，寫進 MORNING 摘要。**不 merge、不改 main**
      （目檢是 Mac 早上的事）。
- [ ] B2 若 09-02 05:00 前分支仍未出現，記「win1003 產線可能卡住」＋
      `D:/wan_out/night_scene.log` 最後幾行（用 ssh w401-win 看，唯讀）。

## C. 邊界（重申）
- 不碰 8766；1004 的 load/unload 只在人類決定後由人類或其指定腳本執行。
- 任何被權限擋住的動作：寫「確切指令＋為什麼需要」到 MORNING 摘要，不繞。
