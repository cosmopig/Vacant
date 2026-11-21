# rc4（652c50d36）對 rc5 的交件政策差分

`python3 tests/adversarial_rc5_repro/policy_diff_rc4_rc5.py <rc4 worktree> <rc5 worktree> <out>`：同一組情境、
同一個照劇本動作的假 agent（`vacant do --cmd`），分別用兩版跑，比較結束碼、accepted、delivered_attempt、
每次嘗試的 (accept, passed, run)、agent 被呼叫次數、跑完後專案樹的逐檔 sha256。

2026-11-21 結果（rc5 = a97cd53de）：

```
SAME  py_fix_first: exit 0/0 accepted True/True delivered 1/1 calls 1/1 attempts [(1, True, 3, 3)]
SAME  py_fail_then_fix: exit 0/0 accepted True/True delivered 2/2 calls 2/2 attempts [(1, False, 0, 3), (2, True, 3, 3)]
SAME  py_never_best_is_2: exit 40/40 accepted False/False delivered 2/2 calls 3/3 attempts [(1, False, 1, 3), (2, False, 2, 3), (3, False, 1, 3)]
SAME  py_tamper_test: exit 40/40 accepted False/False delivered 3/3 calls 3/3 attempts [(1, False, 0, 3), (2, False, 0, 3), (3, False, 0, 3)]
SAME  py_rc_nonzero_but_pass: exit 0/0 accepted True/True delivered 1/1 calls 1/1 attempts [(1, True, 3, 3)]
SAME  py_delete_subdir_file: exit 0/0 accepted True/True delivered 1/1 calls 1/1 attempts [(1, True, 3, 3)]
SAME  none_add: exit 0/0 accepted None/None delivered 1/1 calls 1/1 attempts [(1, None, None, None)]
SAME  check_fix_second: exit 0/0 accepted True/True delivered 2/2 calls 2/2 attempts [(1, False, None, None), (2, True, None, None)]
SAME  npm_fix_second: exit 0/0 accepted True/True delivered 2/2 calls 2/2 attempts [(1, False, None, None), (2, True, None, None)]

9/9 scenarios identical
```

涵蓋：第一次就過、失敗後第二次過、都沒過交「通過最多」的那次、改測試檔、agent 非零結束但測試過、刪檔（含子目錄）、
沒有測試、`--check`（rc5 會自動保護 check.py，但 agent 沒碰它，結果相同）、npm（rc5 給 agent 獨立的 node_modules 副本）。
沒涵蓋：pytest 路徑（本機 venv 沒裝 pytest）、cargo／go（沒裝）、逾時切斷（要真的跑滿 600 秒）。
