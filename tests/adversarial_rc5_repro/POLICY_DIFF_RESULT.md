# rc4（652c50d36）對 rc5 的交件政策差分

`python3 tests/adversarial_rc5_repro/policy_diff_rc4_rc5.py <rc4 worktree> <rc5 worktree> <out>`：同一組情境、
同一個照劇本動作的假 agent（`vacant do --cmd`），分別用兩版跑，比較結束碼、accepted、delivered_attempt、
每次嘗試的 (accept, passed, run)、agent 被呼叫次數、跑完後專案樹的逐檔 sha256。

2026-11-21 最後凍結時的結果（rc5 重新凍結點，見 RELEASE_PREP；rc4 = 652c50d36）：

```
SAME           py_fix_first: exit 0/0 accepted True/True delivered 1/1 calls 1/1 attempts [(1, True, 3, 3)]
SAME           py_fail_then_fix: exit 0/0 accepted True/True delivered 2/2 calls 2/2 attempts [(1, False, 0, 3), (2, True, 3, 3)]
SAME           py_never_best_is_2: exit 40/40 accepted False/False delivered 2/2 calls 3/3 attempts [(1, False, 1, 3), (2, False, 2, 3), (3, False, 1, 3)]
SAME           py_tamper_test: exit 40/40 accepted False/False delivered 3/3 calls 3/3 attempts [(1, False, 0, 3), (2, False, 0, 3), (3, False, 0, 3)]
SAME           py_rc_nonzero_but_pass: exit 0/0 accepted True/True delivered 1/1 calls 1/1 attempts [(1, True, 3, 3)]
SAME           py_delete_subdir_file: exit 0/0 accepted True/True delivered 1/1 calls 1/1 attempts [(1, True, 3, 3)]
SAME           py_new_module: exit 0/0 accepted True/True delivered 1/1 calls 1/1 attempts [(1, True, 1, 1)]
SAME           none_add: exit 0/0 accepted None/None delivered 1/1 calls 1/1 attempts [(1, None, None, None)]
SAME           check_fix_second: exit 0/0 accepted True/True delivered 2/2 calls 2/2 attempts [(1, False, None, None), (2, True, None, None)]
SAME           npm_fix_second: exit 0/0 accepted True/True delivered 2/2 calls 2/2 attempts [(1, False, None, None), (2, True, None, None)]
EXPECTED-DIFF  py_stdlib_name_fixed: exit 40/0 accepted False/True delivered 3/1 calls 3/1 attempts rc4=[(1, False, None, 0), (2, False, None, 0), (3, False, None, 0)] rc5=[(1, True, 1, 1)]
EXPECTED-DIFF  py_stdlib_name_broken: exit 0/40 accepted True/False delivered 1/3 calls 1/3 attempts rc4=[(1, True, 1, 1)] rc5=[(1, False, 0, 1), (2, False, 0, 1), (3, False, 0, 1)]
EXPECTED-DIFF  py_tests_package: exit 40/0 accepted False/True delivered 3/1 calls 3/1 attempts rc4=[(1, False, None, 0), (2, False, None, 0), (3, False, None, 0)] rc5=[(1, True, 1, 1)]

10/10 identical; 3/3 expected differences correct
```

前 10 個情境逐項相同；最後 3 個（py_stdlib_name_fixed／broken 是 P1、py_tests_package 是 N1）是修正，**預期不同**，腳本另外驗證 rc5 判對：
修對 ⇒ 放行、exit 0；改壞 ⇒ 不放行、exit 40。rc4（以及 37005ec2）在這三個情境判錯了。
涵蓋：第一次就過、失敗後第二次過、都沒過交「通過最多」的那次、改測試檔、agent 非零結束但測試過、刪檔（含子目錄）、
新建測試要 import 的模組（py_new_module）、沒有測試、`--check`、npm，專案模組與標準函式庫同名（P1）、測試放在 tests/ 套件裡（N1）。
沒涵蓋：cargo／go（沒裝）、逾時切斷（要真的跑滿 600 秒）。pytest 由獨立查證在專案 .venv 裡實測（verify_rc5/u_d2）。
