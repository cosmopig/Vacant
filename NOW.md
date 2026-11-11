# NOW.md — 現況（≤3KB）

## 輪次／階段／狀態
r1424（2026-11-11）：vq-el4.95 以 CI 證據結案（輪首一次讀 ci_tip_check → VERDICT: CI_TIP_OK rc=0；bd close）；vq-el4 epic 95/95 全數關。
- 主線：G2.5（凍結、已收案）；G3（vq-1zf）接線完成、待人類 `--fire`（queue 空、NOT_FIRED）；vq-el4 下無 open 項。
- 本輪驗收（全數新跑）：ci_tip_check CI_TIP_OK（qwen27b@95fc4130 COVERED／worker@e6fd3e69 PEER_COVERED／argon@c73990cf COVERED）；9311ef8a（vq-el4.94）為綠祖先 1af7aecf1 之祖先（merge-base）；守衛 9 檔 140 passed；freeze_check 12/12 FROZEN_STATE_OK。

## 下一步（下一輪）
- 常規：輪首 ci_tip_check 一次讀取（不 poll）——本輪已 CI_TIP_OK；本輪簿記 commit 使三分支 tip 前移（純簿記 diff 應仍 covered）；若紅燈查因（勿改 .github/workflows/）。
- freeze_check 12 項複驗；守衛 8 檔（＋conformance）複跑；實質新任務待人類核准。
- 待人類：① G3 `--fire`（vq-1zf；全庫唯一 open）② CI 通道裁決（現三分支全覆蓋）。

## 近期關鍵事件
- r1424：vq-el4.95 開→關——輪首一次讀 ci_tip_check（不 poll）→ CI_TIP_OK rc=0（三分支全覆蓋）；9311ef8a（vq-el4.94）經 `git merge-base` 驗證在綠祖先 1af7aecf1 內；守衛 9 檔 140 passed（審查 8 檔基線 122＋conformance 18，0 排除 0 弱化）；freeze_check 12/12；bd close（reason 含驗收命令＋SHA）；0 產品改動、0 model calls。
- r1423：G3 merge 在樹內驗證（1af7aecf1）；G3 trio 70 passed；紅線行更新 r1420 值＋AMEND-1 註記。
- r1420：vq-el4.94 閉——GlmChannel total_tokens strict int≥0、否則 UNKNOWN（fail-closed）；121 passed＋freeze 12/12。

## 關鍵約束（紅線）
- 無 push（loop 自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1419/r1420/r1421 解凍已釘（g3.py 2ba95fe5…／test_reqloop_g3.py b07ce47e…／g3_conformance a7507f6a…／g3gate.py a1b10e2e…／test_reqloop_g3gate.py 86bac89d…；r1420＝AMEND-1 人類裁決之合法解凍、記錄在 GUARD_CONTENT_PIN r1420 條目）。
- /srv/eval/hidden/、scorer.py 不讀；anchors 5＋filing 3/3+3/3 每輪複驗。
- G3 未發射（queue 空、NOT_FIRED）；無 sleep poll CI；無 full pytest；本輪 0 model calls。

## 證據與下輪驗證點
- `python3 ops/reqloop/ci_tip_check.py` → VERDICT: CI_TIP_OK rc=0（本輪輪首一次讀取）。
- `python3 ops/reqloop/freeze_check.py` → VERDICT: FROZEN_STATE_OK 12/12（本輪簿記後重跑、綠）。
- 守衛套件：freeze 27／anchors 5／ci 2／ves 19／g3 25／conformance 18／g3gate 27／now_redline 5／ci_tip 12＝140 passed（本輪新跑、0 排除 0 弱化）。
