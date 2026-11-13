# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1556、2026-11-13、0 model calls）
- 本輪實質＝合併 auto/argon 57bb13d7d（資深審查指示#1）：D3b pearson 重算原語（checks.py `_pearson_pair` 雙分派）＋D1-GATE 成效門工具（`replay_claims.py --gate`、全量負控制 0 假 PASS）＋受控解凍錨點（`test_frozen_anchors` CHECKS 錨、`freeze_check` HISTORICAL_CODE_FILING）＋NOW 紅線修復。衝突檔（checks.py／replay_claims.py／4 測試／g26 json）取 argon 版（審查點名 57bb13d7d、argon 為超集）。
- 紅線修復：`now_redline` 契約行改「凍結／受控解凍」前綴＋4 檔「N 行／blob」逐條自磁碟核（repair 5147f8c3／extract b502741b／checks d401a8ae／run_eval 332cd324）＋g25 filing 6 sha256；qwen 之 D4/G4/RequirementSet 工作全保留。
- 待驗（下條指令）：pearson/gate/anchors/now_redline 相關測試全綠；`replay_claims.py --selftest` 與 `--gate` 應 PASS（66/76、0 假 PASS）。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2/g3_3 歷史未動；4 規格自 hash 已被測試釘住。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- NOW.md ≤3KB；ops/loop/NOW.md cp 鏡像 byte-identical。
- 不以文書改動充實進度：本輪實質＝合併 argon pearson/gate/錨點/紅線（衝突檔取 argon 版）＋紅線行修正、全可機械複核。

## 下一步
1. 跑 pearson/gate/anchors/now_redline 相關測試確認合併後全綠；`replay_claims.py --selftest`／`--gate` 應 PASS（66/76、0 假 PASS）。
2. open/ 已空→依 11-13 定案§5 規劃者補票（每張動 vacant_network/reqloop/ 或 D1 重播器；<3 張就補、每次≤4 張）。
3. 不做 closure-check／結案量具／同步類（11-13 §1）；freeze_check 既有紅→上報規劃者、不代修。
4. G4 發射：人類簽核（填 manifest human_signoff）→重跑測試 0 model calls→才可排程；本輪 0 發射。
