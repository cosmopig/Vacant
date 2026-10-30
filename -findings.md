# -findings.md — P20261030_0650-4 任務 findings 紀錄（e002 C 臂 12 題失敗型態）

> 本檔＝工單 `P20261030_0650-4-record-e002-carm-failures-in-findings.md` 的 findings artifact（審查點「-findings.md」之補寫）。
> 正式回寫位置：`ops/vlab/FINDINGS.md`「2026-10-30 · 主軸 2 · … e002 C 臂最終回寫」→「C 臂未通過 12 題型態分析」段（commit f3b7d430）。本檔與該段同口徑。

## 事實（來源＝`ops/vlab/tools/e002_carm_failures.py` EXIT=0；`/srv/vlab/runs/e002_hypothesis_arms` 唯讀）
- 範圍：e002_hypothesis_arms、C 臂、polyglot_py 34 格；12 格未通過＝4 逾時＋8 未收斂（22+12＝34，與 22/34 PASS 口徑一致）。
- **4 逾時格**（agent rc=124 牆鐘逾時）：forth 52/54、grep 17/25、hangman 5/7（最後 hint：`test_after_10_failures_the_game_is_over: 'ongoing' != 'lose'`）、sgf_parsing 17/23。
- **8 未收斂格**（agent rc=0、測試未過）：bottle_song 1/7、food_chain 3/10、go_counting 10/11、paasio 23/25、poker 33/37、rest_api 6/9、scale_generator 12/17、zipper 9/14。
- 退回次數：7 格 rejections=1（1 round 後仍 open，最後 hint「step N … had failed」）；**zipper 無 rounds 記錄＝UNKNOWN**（量具註明 null≠0），既不寫「退回 1 次」也不寫「未退回」。
- 更正：先前審查指示「第 4 逾時題＝react」為誤記——`pg_react-pi-C-r1` score.json `pass=true`（14/14）、timed_out=false，實為 PASS 格；第 4 逾時題實為 **sgf_parsing**。

## 口徑與邊界
- 以上為失敗格客觀型態記錄（哪題、測試進度、退回次數、最後 hint），可重算（重跑量具即得同輸出）；不宣稱 C 臂「可信」，亦非證明其較好。
- 未驗證（不屬於本工單範圍）：M/S 臂最終值（round 206 實測 M 臂 27/28 scored）、16 點／34.46h 最新序列同步（BACKLOG）。

## 狀態
- 工單驗收：`grep -F "sgf_parsing" ops/vlab/FINDINGS.md && grep -F "bottle_song" ops/vlab/FINDINGS.md` → 兩行俱命中、EXIT=0。
- 交付鏈：commit 9ed132d3（量具，round 201 工單 0601-3）＋ f3b7d430（FINDINGS 回寫，round 207）；工單已 mv `tickets/qwen/done/`。
