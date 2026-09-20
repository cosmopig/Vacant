這一夾是「修之前」的重現紀錄，不是現況。

2026-09-20 第一次跑 resilience_check.sh（commit ba013d30 的 twinlink.py）的結果：
綠 93／紅 10。十個紅燈全部集中在第 6 節「畸形卡」，而且每一個紅燈的判準都一樣——
**loop 整個死掉，於是那一批裡那張乾淨的鄰居卡也拿不到分身**（neighbour=0）。

（放在這裡而不是 evidence_resilience_20260920/ 裡面，是因為那個目錄每次重跑
都會整個 rm -rf 重生；擺進去的話下一次重跑就把這份歷史安靜地刪掉了。）

d6_matrix.txt 是那一輪的完整矩陣（30 格＝15 種畸形卡 × 模型開／關）。
modelup_* / modeldown_* 是十個紅燈各自的 traceback。

三類死法：
  A 兩種後端狀態都死：idnewline（ValueError：sub_id 不可含換行）、
    cardstr／cardlist（AttributeError：card 不是 dict）、
    surrogate（UnicodeEncodeError：落單代理對過不了 sha256 的 utf-8 編碼）
  B **只有 1003 斷線時才死**：needint／vibedict（AttributeError：欄位不是字串，
    只有走 fallback_twin 才會碰到）——最壞的一種，正常測試時看不到，
    挑在展場已經斷線的那一刻才現身
  C 沒事：long／ctrl／emoji／fullwidth／empty／jsoninj／huge／idempty／notdict

publish_retry_growth.txt 是第 1 節量到的另一件事（沒有修，見 SUMMARY.txt 的記錄項）。

修法在 commit e8fd4646 的 twinlink.py（只動失效處理路徑）＋
tests/test_twinlink_resilience.py（25 項，含對測試自己的負控制：
把 twinlink.py 換回修前版本，其中 8 項會紅）。
修完重跑：綠 103／紅 0／記錄 6，在 evidence_resilience_20260920/SUMMARY.txt。
