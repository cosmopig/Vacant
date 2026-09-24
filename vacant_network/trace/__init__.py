"""trace — **可究責追緝**：每一步誰做了什麼（病歷）→ 出錯時追到那一步 → 事實回饋 → 信譽與路由。

這支在架構裡承重什麼（`ops/accountability/LOOP.md`；裁決
`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md`）：

`intake/` 回答「這份繳付物合不合格」。人類 2026-09-24 指出那只是「本機多個驗證器」，
不是咎責、不是抓出錯誤點。本套件補上 0924 論文一句話定位的前半——「**誰做了什麼**」
——的步驟層版本，並把它接回繳付物：

    workspace.py   每一步前後的工作區（增量索引、差異、內容定址版本庫）
    recorder.py    每一次工具呼叫一筆簽章事件：行動者、工具、輸入、輸出、寫了什麼；缺口
    capture.py     四個 agent 的原生掛鉤 → recorder（行動者、步驟 id、逐字稿封存）
    locate.py      不過的主張 → 檔案：行：錯的值
    rerun.py       在重建出來的某一步狀態上重跑一條主張（同一套驗證器）
    blame.py       錯的值 → 寫下它的那一步 → 重跑證明 → 從哪裡讀來（兩層、五級）
    feedback.py    給 agent 的事實回饋（無行動者、KS-1）；給人的未解問題清單
    stopcheck.py   回合結束那一刻：驗 → 追緝 → 回饋 → 報告 → 後果
    actors.py      後果：只有事實層進信譽（可撤銷）；輸入錯記來源；路由＝給人的建議＋auto
    cli.py         `vacant trace show|verify|report|blame|actors`、`vacant flag`

原則（論文）：執行取代意見（錯誤點由重跑與紀錄比對決定）；KS-1（給 agent 的文字只有事實）；
竄改可察覺≠不可竄改；完整性≠完備性（沒被記錄的改動明講是究責缺口）。
"""
from __future__ import annotations
