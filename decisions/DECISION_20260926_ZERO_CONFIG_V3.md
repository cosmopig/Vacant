# 裁決：零設定 v3——在預算用完之前先交（2026-09-26）

依據：`docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md`（付費批次為什麼沒有量到差別）；人類 2026-09-26：「總之你幫我把產品修更好迭代好
然後用這個去測試這是我本地算力」。設計 workflow（`zero-config-v3-design`，run `wf_cf88b8ac-9de`：三個唯讀研究 agent、三份獨立設計、一個評審）
全部輸出在 `ops/eval/evidence_20260926_local/design/`。

## 一、問題（付費批次的紀錄）

82 個失敗裡 55 個是「沒交」：agent 被回合上限切斷時答案檔還不存在，Vacant 的交件前檢查只在 agent 自己說做完時跑，永遠輪不到。
逐回合重建（`design/nudge_sim/`，316 跑、回合數與 runs.json 316/316 對得上）：gemma 有 26–30 跑在最後 2–3 回合之前已經說出正確答案、沒寫檔。
太早提醒反而有害：gemma 寫完檔幾乎就停（101 跑裡 85 跑在第一次寫檔後一回合內結束），第 8 回合提醒會多救 11 跑、最多弄壞 29 跑；
第 13 回合（上限 15）多救 28 跑、最多弄壞 3 跑。qwen 在任何時點都救不到也弄不壞。

## 二、v3 做什麼（全部在回合預算之內；沒問題時模型收到的東西逐位元組不變）

| 編號 | 做什麼 | 什麼時候 | 程式 |
|---|---|---|---|
| v3-1 | pi 的邊界處理器把 Vacant 的草稿**接在**別的擴充的草稿後面，不再蓋掉 | 永遠（修錯） | `adapters/agents.py` |
| v3-2 | **回合預算提醒**：agent 的系統提示寫了回合上限（`agents.BUDGET_RE_SRC`）、只剩 2 或 1 回合、這一回合有執行工具、人要求寫出的檔還不存在 ⇒ 一段 3 行的提醒搭在下一通本來就要送出的請求上（「先把目前最好的答案寫進去，之後還可以改」）。一個要求之內最多 2 次；不引用任何值 | 只在寫明上限時 | `adapters/agents.py`（`turn_end`）、`trace/budget.py`、`trace/review.render_nudge`、`adapters/hook.py`（`turn_check`） |
| v3-3 | **最後一回合**：只剩 1 回合時，交件前檢查只退回「要求的檔不存在」，並說還剩幾回合；其他發現照樣進交件說明 | 只在寫明上限時 | `trace/zerostop.stop(turns_left=…)`、`review.turns_left_note` |
| v3-4 | **還沒說做完就結束**（上限、Esc、關掉）也寫交件說明給人：要求的檔在不在、提醒過幾次。不送任何東西給模型 | 交件前檢查沒跑到的那一跑 | `trace/zerostop.ended`、`adapters/hook.py`（零設定的 `session_end`） |

字句（KS-1 與沒有行動者的檢查在載入時與測試裡都驗）：
```
Before the turn budget runs out: a requested output does not exist yet.
- The request asks for /app/answer.txt, and it does not exist yet. Model turns left in the stated budget: 2 of 15. Write your current best answer to /app/answer.txt now, in the format the request asks for; you can keep checking afterwards and overwrite it if the answer changes.
This reminder is only about the file; it does not say whether any answer is right.
```

## 三、不做（和理由）

- **中止之後再多問一次**（`agent_settled` 裡 `sendUserMessage`）：會超過人設的上限一通（16 對 15，`design/piexp/results.txt`），互動介面裡還會蓋過人按的 Esc。
- **沒交就重開一跑**：請求數 ×1.4、超過上限、在 Harbor 容器裡沒驗過；子 pi 在同一個資料夾會把自己當成子 agent、不跑檢查。等正式批次的 A 組多次樣本離線估過再說。
- **獨立再算一次＋投票**：成本 ×2 以上，會把對的第一次答案翻掉。
- **提早提醒**（沒有寫明上限時用固定回合數）：模擬顯示得不償失。
- **從模型的文字或思考猜答案、Vacant 自己寫答案**：Vacant 不替 agent 選答案；gemma 的中間回合幾乎沒有可見文字。
- **從人打的話讀上限**：沒有人執行那個上限；「讀前 5 個檔」這類字會誤判。

## 四、誠實邊界（口徑）

1. v3-2／v3-3 **只在 agent 被告知回合上限時**作用。一般互動使用（pi 預設沒有上限）幾乎不會觸發；它幫的是有預算上限的情境
   （評測、CI、headless 批次）。這一點在任何對外說法裡都要一起講。
2. 提醒只看檔在不在，不說答案對不對；模型收到之後會不會寫、寫的對不對，要真模型量。
3. 付費批次的模擬數字（多救 28、最多弄壞 3）假設模型照做，而且是 gemma-26b 開思考；本機的 gemma-4-12b 不思考是不同的模型，它最常見的失敗是
   「自己說做完卻沒寫檔」（現版已經在管），被上限切斷的跑多半在重複同一類指令、手上不一定有答案——v3 在本機能多救多少，要量。

## 五、產品等級（評測之前，全部 L-fake、不花錢）

- 單元與掛鉤測試：`tests/test_zero_budget.py`（10 條）；零設定、adapters、trace 相關 243 條全過。
- **閘門 3**（Harbor＋pi 0.87.1＋回合上限 15，假模型一直查、從不寫答案檔、看到提醒才寫；`ops/eval/gate3/`）：
  A＝0、C1（現版）＝0、C2（v3）＝1；三跑各 15 通請求（不超過上限）；C2 在第 13 回合後提醒一次、第 14 回合寫檔、交件說明寫了「被切斷、檔存在、內容沒查」。
  證據：`ops/eval/evidence_20260926_local/gate3/`。
- **模擬使用者**（乾淨 Ubuntu、只照 README 裝、pi 沒有上限）：三個情境結果和 v2 相同；`correct` 的 4 通請求 A／C **逐位元組相同**
  （`ops/eval/evidence_20260926_local/simuser_v3/`）。
