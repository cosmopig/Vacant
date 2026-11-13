# NOW.md — Vacant 現況（≤3KB；本檔每輪覆寫、歷史見 STATE.md）

## 現況（r1550、2026-11-13、0 model calls）
- 本輪實質＝票 P20261113_0344-1（D3b）done：checks.py 重算集合加 "pearson"（KV/PLAIN 雙分派、_pearson_pair 與 pearson2 同口徑）＋tests/test_reqloop_checks_pearson.py 3 測試（已知 r 正控制／錯值負控制／缺欄 UNKNOWN／重算值不進 detail）。零模型、只加法、預設＝舊行為（11-13 定案 §3 受控解凍）。
- 驗收（本輪新跑）：`pytest tests/test_reqloop_checks_pearson.py`→「3 passed」；`run_eval.py --all`→G1 39/39 冤枉0、REAL14 9/9 冤枉0/5、PHASE3 fixed7/unresolved2/rejected0/r2w0/held0＝g25 filing 三門數字一致；`replay_claims.py --selftest`→SELFTEST PASS（pearson 2 條翻 deterministic、K0=14/76、K1=66/76、unverified 7 條、負控制全紅位不變）。
- 隨行簿記：replay_claims.py 基線 12→14（D3b 後）＋tests/test_replay_claims.py 6 綠；frozen_anchors 重立 CHECKS 錨 764119e2…/2907 行（filing 仍記解冻前 c7589c61…）；NOW 紅線改「凍結／受控解凍」且全部數值自磁碟重算。
- 未驗證：CI 完成裁決（延下輪頭一次讀、不 poll）；成效門（11-13 定案 ≥30/76）K1=66 已達、K0=14 未達——最終裁決屬人類，本輪只報數不宣稱。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、run_eval.py 332cd324…（仍凍結）；extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob 764119e2…（受控解凍、只加法、再改須重立錨留記錄）；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- NOW.md ≤3KB；ops/loop/NOW.md cp 鏡像 byte-identical。
- 不以文書改動充實進度：本輪實質＝D3b 加法＋測試＋replay/錨/紅線更新＋票結案、全可機械複核。

## 下一步（2026-11-13 人類定案改寫，凌駕舊的下一步）
1. 照 tickets/qwen/open/ 的 D1→D2→D3→D4 做（需求→可檢查條件；成效門 2/76→≥30/76、0 錯判 PASS）。
2. 不再做任何 closure-check／結案量具／同步類工作（R20261113_0041-2 作廢）。
3. extract.py／checks.py 受控解凍：只加法、新參數預設＝舊行為、run_eval.py --all 三門數字與 g25 filing 相同。
