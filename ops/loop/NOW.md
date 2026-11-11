# NOW.md — 現況（≤3KB）

## 輪次／階段／狀態
r1420（2026-11-11）：收斂態＋收口 r1419 殘留（vq-el4.94 驗證、同步、結案）。
- 主線：G2.5（凍結、閉）；G3（vq-1zf）待人類 `--fire`；vq-el4 全閉（0 open；vq-el4.94 r1420 閉）。
- r1419（9311ef8a，rc=124 殘留）代碼＋6 測＋pin 已在樹；r1420 驗證全綠：pin 2/2、RED 負控 4 FAIL＋正控 2 PASS（舊碼）→6/6（新碼）、護衛 121 passed、freeze 12/12、diff 0×2。

## 下一步（次輪）
- 常規：頭部 ci_tip_check 一次讀（不 poll）——qwen27b 代碼改動 CI 在跑（9311ef8a 在跑≠已綠）；綠後三分支應 covered。
- freeze_check 12 項全核；實質新任務以人類批核或新產品 bug 為準（11-06 指示仍有效：不加同線重試、不加大規模重跑）。

## 近期關鍵事件
- r1420：vq-el4.94 閉——GlmChannel total_tokens 收緊 strict int≥0、否則 UNKNOWN（不填 0）；r1419 代碼＋6 測＋GUARD_CONTENT_PIN 解凍記錄本輪驗收：pin sha 2/2 MATCH、RED 證據（舊碼 4 負控 FAIL／2 正控 PASS、還原 sha 復合）、護衛 8 檔 121 passed、freeze_check 12/12、worktree 同步 diff 0×2。
- r1419：（rc=124）auto-commit 9311ef8a 代碼＋測試＋pin 入樹、未同步 peer／未結案→r1420 紅燈源頭（diff_worker/diff_argon）。

## 關鍵約束（紅線）
- 不 push（loop 自動推 auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 唯讀。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1419 解凍 2 檔（g3.py ecac7879…／test_reqloop_g3.py c036e3cd…，vq-el4.94 記錄在案）已釘。
- /srv/eval/hidden/、scorer.py 不讀；anchors 5＋filing 3/3＋3/3 每輪複核。
- G3 未 fire（/srv/vlab/queue 空、NOT_FIRED）；不 sleep poll CI；不全量 pytest；本輪 0 model calls。

## 證據與次輪驗證點
- `python3 ops/reqloop/freeze_check.py` → VERDICT: FROZEN_STATE_OK 12/12（r1420 修後實測）。
- `python3 ops/reqloop/ci_tip_check.py` → 開輪一次讀；現 qwen27b 代碼 CI 在跑（在跑≠已綠、不 poll）。
- 護衛套件：8 檔 121 passed（27/5/2/19/27/24/5/12；g3 18→24＝r1419 6 新測）。
- RED 證據：舊碼 4 負控 FAILED＋2 正控 PASS；新碼 6/6 綠（r1420 實測、還原 sha256 復合 pin）。
