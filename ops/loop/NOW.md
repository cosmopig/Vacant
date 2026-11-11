# NOW.md — 現況（≤3KB）

## 輪次／階段／狀態
r1423（2026-11-11）：工單 P20261111_0315-1 收案——G3 分支（d13bac4be P0＋9327dffb5 AMEND-1、base r1418）已併入 auto/qwen27b（r1421 auto-commit 1af7aecf1；本輪 redo 收案）。
- 主線：G2.5（凍結、已收案）；G3（vq-1zf）接線完成、待人類 `--fire`（AMEND-1＝接線核准、非發射核准；/srv/vlab/queue 空）；僅餘 vq-el4.95（CI 覆蓋跟進、次輪一次讀收口）。
- 本輪驗收（全數新跑）：G3 trio 70 passed（g3 25／conformance 18／g3gate 27）；freeze_check 27 passed（含 3 GUARD_CONTENT_PIN）；g3gate --plan NOT FIRED＋PLAN OK（入口=glm+local_pi）；g3 --dry-run 12 cells＋arm conformance OK、0 模型呼叫。

## 下一步（下一輪）
- 常規：輪首 ci_tip_check 一次讀取（不 poll）——現三分支 HEAD（qwen27b 簿記 commit／worker 33759b498／argon b718a96ee）CI pending、次輪一次讀。
- freeze_check 12 項複驗；實質新任務待人類核准或新產品 bug。

## 近期關鍵事件
- r1423：工單 P20261111_0315-1 收案——merge 已在樹內驗證（1af7aecf1、parents 9504e6270+9327dffb5）；tests 檔開啟（r1419 local／r1419 branch／r1420／r1421 解凍記錄全數保留）；5 pins 磁碟複驗 2ba95fe5…／b07ce47e…／a7507f6a…／a1b10e2e…／86bac89d…；紅線行更新 r1420 值＋AMEND-1 註記；in-scope diff 0×2（docs 檔非 in-scope、qwen27b 獨有）。
- r1421（rc=124 未收尾）：merge 入樹（1af7aecf1）＋pins 更新磁碟實值（r1421 合併記錄）＋worker／argon 6 檔同步（33759b498／b718a96ee）——簿記與結案當時未做、本輪補完。
- r1420-redo：審查點名 3 檔開啟＋重算、主張全成立、0 重做。
- r1420：vq-el4.94 閉——GlmChannel total_tokens strict int≥0、否則 UNKNOWN（fail-closed）；121 passed＋freeze 12/12。

## 關鍵約束（紅線）
- 無 push（loop 自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1419/r1420/r1421 解凍已釘（g3.py 2ba95fe5…／test_reqloop_g3.py b07ce47e…／g3_conformance a7507f6a…／g3gate.py a1b10e2e…／test_reqloop_g3gate.py 86bac89d…；r1420＝AMEND-1 人類裁決之合法解凍、記錄在 GUARD_CONTENT_PIN r1420 條目）。
- /srv/eval/hidden/、scorer.py 不讀；anchors 5＋filing 3/3+3/3 每輪複驗。
- G3 未發射（queue 空、NOT_FIRED）；無 sleep poll CI；無 full pytest；本輪 0 model calls。

## 證據與下輪驗證點
- `python3 ops/reqloop/freeze_check.py` → VERDICT: FROZEN_STATE_OK 12/12（本輪簿記後重跑、綠）。
- 守衛套件：freeze 27／anchors 5／ci 2／ves 19／g3 25／conformance 18／g3gate 27／now_redline 5／ci_tip 12（本輪新跑）。
