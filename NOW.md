# NOW.md — 現況（≤3KB）

## 輪次／階段／狀態
r1424 redo（2026-11-11）：審查點名 4 檔（effects summary／g25 filing／extract.py／repair.py）逐檔開啟＋依賴值獨立重算——0 更正（值全成立、4 檔未改）；vq-el4.95 已結案、vq-el4 全數關；全庫僅餘 vq-1zf（G3，待人類 `--fire`）。
- 主線：G2.5（凍結、已收案）；G3 接線完成、待人類 `--fire`（queue 空、NOT_FIRED）。
- 本輪驗收（全數新跑）：4 檔開啟＋重算全 MATCH（repair 148101B/2795 行/5147f8c3…、extract 57363B/1217 行/e757aec5…、filing 6 sha256 code 3/3+sources 3/3、effects 60228B/a710f7e44c…）；56 passed（now_redline 5/anchors 5/freeze 27/ves 19）；freeze_check 12/12 FROZEN_STATE_OK。

## 下一步（下一輪）
- 常規：輪首 ci_tip_check 一次讀取（不 poll）——本輪已 CI_TIP_OK；簿記 commit 使三分支 tip 前移（純簿記 diff 應仍 covered）；若紅燈查因（勿改 .github/workflows/）。
- freeze_check 12 項複驗；守衛複跑；實質新任務待人類核准。
- 待人類：① G3 `--fire`（vq-1zf；全庫唯一 open）② CI 通道裁決（現三分支全覆蓋）。

## 近期關鍵事件
- r1424 redo：審查點名 4 檔未開啟——逐檔開啟（head＋載入）＋重算：repair/extract 行數·blob·位元組、filing 6 sha256（code 3/3+sources 3/3）、effects summary（60228B、50 格、13w/11w）全 MATCH——0 更正、56 passed＋freeze 12/12。
- r1424：vq-el4.95 開→關——輪首一次讀 ci_tip_check → CI_TIP_OK rc=0（三分支全覆蓋）；9311ef8a（vq-el4.94）在綠祖先 1af7aecf1 內（merge-base）；守衛 140 passed；freeze 12/12；0 產品改動。
- r1423：G3 合併在樹內驗證（1af7aecf1）；G3 trio 70 passed；紅線行更新 r1420 值＋AMEND-1 註記。

## 關鍵約束（紅線）
- 無 push（loop 自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1419/r1420/r1421 解凍已釘（g3.py 2ba95fe5…／test_reqloop_g3.py b07ce47e…／g3_conformance a7507f6a…／g3gate.py a1b10e2e…／test_reqloop_g3gate.py 86bac89d…；r1420＝AMEND-1 人類裁決之合法解凍、記錄在 GUARD_CONTENT_PIN r1420 條目）。
- /srv/eval/hidden/、scorer.py 不讀；anchors 5＋filing 3/3+3/3 每輪複驗。
- G3 未發射（queue 空、NOT_FIRED）；無 sleep poll CI；無 full pytest；本輪 0 model calls。

## 證據與下輪驗證點
- `python3 ops/reqloop/ci_tip_check.py` → VERDICT: CI_TIP_OK rc=0（本輪一次讀取；三分支 COVERED）。
- `python3 ops/reqloop/freeze_check.py` → VERDICT: FROZEN_STATE_OK 12/12（redo 簿記後重跑、綠）。
- 守衛（redo 重跑）：now_redline 5／anchors 5／freeze 27／ves 19＝56 passed（本輪新跑、0 排除 0 弱化）。
