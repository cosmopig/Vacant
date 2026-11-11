# NOW.md — 現況（≤3KB）

## 輪次／階段／狀態
r1427（2026-11-11）：**G3 發射收案完成**（vq-1zf 關；工單 P20261111_0512-1 → done；0 產品碼）。
- 發射（r1426）：05:41:18Z 起、06:02:37Z 完成（systemd 一次性 unit、無 [Install]）；out=~/dev/ops/g3_fire_20261111（repo 外）；核准=~/dev/ops/approvals/g3_vq-1zf_fire_20261111.json（未改）。
- 結果（一次讀取）：12 格、1 ok／11 error——dab_129/native_pi ok（answer @mean_fare[32.20]/@std_dev_fare[49.67]、20887 tok）；3×native_pi（dab_144/176/216）'pi timed out after 300s'；8×reqlist_only/full_rloop 'glm rc=4 token_limit'（停、不重試；known 49744 tok≪2M/日、非本地額度）；hidden_after 12/12 UNKNOWN；totals 11 calls/49744 tok。
- 收案：驗收綠（g3_result.json＝vacant.reqloop.g3.result/1 12 格）；審計摘要 ops/audits/g3_fire_20261111_summary.{py,json} 入 repo（G3_FIRE_SUMMARY_OK；raw 留 ~/dev/ops）；簿記 4 檔＋三分支同步（in-scope diff 0×2）；vq-1zf close；ticket mv done。

## 下一步（下一輪）
- 待人類/vlab 側：① hidden 打分（12 格 hidden_after 全 UNKNOWN；打分照 /srv/vlab 慣例；本迴圈不自己打分、不寫 /srv/vlab/queue）② CI 通道裁決。
- 若再發射 G3（如 glm token_limit 解決後重跑）：須新人類核准檔（不自改自簽）；同批重跑簿記如實標記、不得當獨立樣本；不得宣稱效果改善。
- bd ready 空；下一輪待人類指示/vlab 結果（輪首協議照工單/prompt）。

## 關鍵約束（紅線）
- 無 push（loop 自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1419/r1420/r1421 解凍已釘（g3.py 2ba95fe5…／test_reqloop_g3.py b07ce47e…／g3_conformance a7507f6a…／g3gate.py a1b10e2e…／test_reqloop_g3gate.py 86bac89d…；r1420＝AMEND-1 人類裁決之合法解凍、記錄在 GUARD_CONTENT_PIN r1420 條目）。
- /srv/eval/hidden/、scorer.py 不讀；anchors 5＋filing 3/3+3/3 每輪複驗。
- /srv/vlab/queue 不寫（0 項含隱藏）；送件照 vlab 慣例；無 poll CI；無 full pytest。

## 證據與下輪驗證點
- 驗收：`.venv/bin/python -c "import json;d=json.load(open('$HOME/dev/ops/g3_fire_20261111/g3_result.json'));print(d['schema'],len(d['cells']),d['stop_reason'],d['totals'])"` → `vacant.reqloop.g3.result/1 12 None {'cells': 12, 'cells_run': 12, 'model_calls': 11, 'tokens': 49744, 'tokens_missing': False}`（本輪重跑）。
- `journalctl --user -u vacant-g3-fire-20261111` → 尾行 G3 FIRE DONE（06:02:37）；unit inactive (dead)。
- `.venv/bin/python ops/audits/g3_fire_20261111_summary.py` → VERDICT: G3_FIRE_SUMMARY_OK rc=0（answer sha256/tokens 獨立重算）。
- 本輪改動＝審計摘要 2 檔＋簿記 4 檔×3 分支＋bd close＋ticket done；0 產品碼、0 model calls。
