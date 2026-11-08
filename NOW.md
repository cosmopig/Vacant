# NOW.md — r1262（2026-11-08，第 1262 輪）

## 本輪結論（一句）
GitHub auto CI 26 跑全紅（round-head 的本地 CI 報表遮蔽了它）；根因＝一測試在啟動的直譯器斷言 scipy/numpy（不在安裝合約），HEAD 已修；新增安裝合約守門測試，讓這類缺陷以後在本地就紅。

## 事實（證據）
- GitHub API：26 個 auto 跑（11-07 07:27→13:22）全 failure，全敗「pytest — ReqLoop (test_reqloop*)」步（抽查最舊 run 42351331975 與最末 f03d1177/check-run 128415593693）。
- 乾淨 venv（`pip install -e ".[dev]"` @ f03d1177）複現：1 failed＝`test_reqloop_repair.py::test_pin_survives_venv_symlink`（`import scipy, numpy` → ModuleNotFoundError）。
- 3db4a7f3（11-07 13:49）改用 pytest：在 HEAD、不在 f03d1177 → GitHub 紅是 **STALE**（紅在舊 commit）。
- HEAD（69b62a9b）乾淨 venv 三步全綠：ReqLoop 379 passed/3 skipped（host 資料）＋新守門 2；frozen 1 passed；stepchain 37 passed/1 skipped。
- 新增 `tests/test_reqloop_ci_contract.py`：實際經 subprocess 啟動的 `-c` 片段 import ⊆ vacant-network（deps＋[dev]）∪ stdlib；scipy/numpy 負向控制；回歸模擬（改回 scipy）→ 守門紅並點名包與片段。
- Actions 自 11-07 13:22 無新跑（stalled）；下一觸發＝迴圈自動 push。

## 下一輪先做
1. 自動 push 後查 Actions 有沒有新跑（API `workflow_runs`，`curl -m`，別 sleep 輪詢）：綠→CI 紅解除；仍無跑→Actions infra 問題，需人工（本地無解）。
2. 若新跑仍紅：用本輪方法乾淨 venv 複現（worktree＋fresh venv＋HOME 隔離），修準則＝只准斷言安裝合約內的包（見 test_reqloop_ci_contract.py）。
3. 主線仍是 G2.5（vq-el4）：queue 空、0 model calls、等工單。G3（vq-1zf）仍未發——等 RLOOP_PLAN.md 人批。

## 紅線（本輪全守）
0 model calls（vibe_calls 無 11-07 後新條）·G3 未發未入隊·本輪無 git push·無 reset/rebase/branch -f·未讀 /srv/eval hidden 與 scorer.py·repair.py(2795)・extract.py(901)・checks.py・run_eval.py・filing（code 51abfec3/checks c7589c61/run_eval 332cd324）未改·.github/workflows/ 未改·無 sleep 輪詢。

## 檔案清單（本輪）
＋ `tests/test_reqloop_ci_contract.py`（新，2 tests）
～ `STATE.md`／`NOW.md`（簿記）
＝ 工單 `vq-el4.22`（建→帶證據關）；memory `github-actions-stalled-2026-11-07-13-22`（已更正）
