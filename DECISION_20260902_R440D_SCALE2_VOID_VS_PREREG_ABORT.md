# R440D：scale2 ON 的 void 率對照預註冊中止準則——資料不可用於判準，且 OFF5-scale2 不應啟動

（2026-09-02 01:55 UTC，Fable 5.1 稽核輪，Mac 端 session「vacant」。依 peer session
2026-09-02 的要求把數字放到人類面前。本輪**不改碼、不殺 run、不動迴圈**——
這三件都在人類手上，理由見 §四。）

## 一、量到什麼（01:53:55 UTC，逐行讀 rows/notes/calls，不是讀 summary）

`g_on_qwen_only_scale2_20260901`（PID 2513538，elapsed 15000s ≈ 4h10m）：

| 項目 | 數字 |
|---|---|
| rows.jsonl（成功處理） | 11（11/11 meets_demand） |
| notes.jsonl infra_void | 42（TimeoutError 38、HTTP 400 4） |
| 已處理 | 53/60 |
| **void 率** | **42/53 = 79.2%**（round459 66.7% → 461 76.7% → 463 77.3% → 現在 79.2%） |
| calls.jsonl | 216 通；gen 70（err 18＝25.7%）、**review 134（err 86＝64.2%）**、revise 11（err 0） |
| 上一筆成功列 | 01:10:20 UTC——**之後 43 分鐘只有 void** |

## 二、對照預註冊中止準則

1. **R440**（2026-09-01 07:29 UTC，早於 R456 的 21:47 UTC）§「中止與地板/天花板
   準則」：**infra_void 率 >20%（任一臂）：中止，先修 infra 再跑（R356 教訓）。**
   scale2 ON 從第一個檢查點（round459，66.7%）起就超過這條三倍以上。
2. **R456** 自己的推翻條件：「若 scale2 的 ON void 率遠高於 35% …要重新評估是否
   值得繼續加碼」。round459 就觸發了，round459/461/462/463 四輪都選擇「續跑、
   不介入」，理由是「平台不是趨勢」——但 R456 的條件寫的是**高於 35% 就重評**，
   不是「持續惡化才重評」。平台在 77–79% 恰恰證明不會自己好。
3. **R456 的目的**（把配對樣本推到 ~70 對以補檢定力）在這個 void 率下**算術上
   不可達**：60 題 × (1−0.79) ≈ 13 個 ON 成功樣本，就算 OFF5-scale2 零 void，
   配對 n 上限也只有 ~13，比 round456 那批的 35 對還少。再跑一個 OFF5 只會
   多一批配不上對的資料。

## 三、裁決

- **scale2 ON 違反預註冊中止準則（R440 >20%；R456 >35% 重評）。其資料不得進入
  三條「有成效」判準的任何一條**；只能作為「1004 在 qwen 262k-context 設定下
  的 review 失敗率」這個 infra 觀察保存（不刪，鐵律：run 目錄不刪）。
- **推翻 round463 的「跑完就起同 seed 的 OFF5」**：在 infra 未修的狀態下再起
  任何 qwen run 都違反 R440 的「先修 infra 再跑」。8765 收完 scale2 後的
  下一個 run 依 R440C 是 E1（gemma-only）。
- infra 的嫌疑點（判斷，不是量測）：1004 的 qwen 實例 `context_length=262144,
  parallel=4`，22.3 GB 模型在單卡上幾乎必然部分卸載到 CPU；review 呼叫
  64% 失敗、38/42 void 是逾時而非 400，跟「模型本身在慢速路徑上」一致。
  **這需要人到 1004 前面看 GPU 型號與 VRAM，本 session 讀不到。**

## 四、給人類的決定（數字在前，選項在後）

兩個選項都被**同一件事**綁住：R440C 的 watcher 還沒起（本 session 被權限擋）。
殺不殺 scale2 只差約 40 分鐘；起不起 watcher 差 5–6 小時（否則迴圈下一個
sonnet 輪照 round463 起 OFF5-scale2）。

| 選項 | 做什麼 | 得失 |
|---|---|---|
| A 等它跑完 | 不動；剩 7 題，外推 35–60 分鐘 | 預期再得 1–2 成功列（無判準價值）；卡晚 ~40 分鐘讓出 |
| B 提前殺 | 先起 watcher，再 `kill -TERM 2513538`（watcher 等 PID 退出後自動接手） | 省 ~40 分鐘，損失 ≤2 列；summary.json 由 TERM 正常落盤（round446 做過） |

兩者都要的那一行（vacant-dev）：
```
cd ~/vacant/Vacant && git pull -q --ff-only origin feat/v2-four-stages && \
setsid nohup bash ops/gain/queue_e1_after_scale2.sh 2513538 >/dev/null 2>&1 < /dev/null &
```
選 B 再加：`kill -TERM 2513538`（**不要 -9**）。

第三個決定（與上面獨立）：**迴圈的 `fable` 層要生效必須重啟迴圈**——
`touch ~/vacant/STOP` → 等當輪收尾 → `cp ~/vacant/Vacant/ops/loop.sh ~/vacant/bin/loop.sh`
→ 重新啟動。這會中斷正在跑的那一輪，本 session 與 peer session 都不自己動。

## 五、本 session 被擋的確切指令（給 peer 彙整，不繞）

1. `scp ops/gain/queue_e1_after_scale2.sh user1@100.124.254.83:~/vacant/bin/`（連檔案複製都擋）
2. `ssh user1@100.124.254.83 'setsid nohup bash ~/vacant/bin/queue_e1_after_scale2.sh 2513538 >/dev/null 2>&1 < /dev/null &'`
3. 未嘗試（不可逆／人類邊界）：`kill -TERM 2513538`、`touch ~/vacant/STOP`、
   對 1004 的任何 `POST /api/v1/models/load|unload`（watcher 內含，隨 watcher 一起交人類）。

允許的動作（本輪實際做的）：唯讀 ssh 探測、`git commit`／`git push` 到
feat/v2-four-stages、寫 DECISION。

## 六、推翻條件

- 若人類到 1004 前面確認 GPU 足以同時放 qwen(262k) 與 gemma，§三第三點的
  infra 嫌疑作廢，void 平台要另找原因（hub 的 `force_thinking: true`＋
  `default_max_tokens: -1` 讓 review 回覆無上限，是下一個嫌疑）。
- 若 E1 在 gemma 單獨載入時 ON void 仍 >35%（R440C 的 P0 失敗），則 void
  問題不在 qwen 的設定，在 harness 的 review 路徑本身（round442 假說重開）。
