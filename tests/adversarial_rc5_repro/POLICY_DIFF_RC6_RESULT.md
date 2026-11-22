# rc5-final（1d764cc69）對 rc6 的交件政策差分

`python3 tests/adversarial_rc5_repro/policy_diff_rc5_rc6.py ~/dev/ops/rc5final_venv/bin/vacant /home/user1/dev/wt/rc6 /tmp/pdiff_rc5_rc6`：同一組情境、同一個照劇本動作的假 agent（`vacant do --cmd`），分別用 `rc5-final` wheel 與 `redo/rc6` 分支跑，比較結束碼、`accepted`、`delivered_attempt`、每次嘗試的 `(accept, passed, run)`、agent 被呼叫次數、以及跑完後專案樹的逐檔 sha256。

2026-11-22 實測結果（rc5-final = `~/dev/ops/rc5final_venv/bin/vacant`；rc6 = `redo/rc6`）：

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
SAME           py_stdlib_name_fixed: exit 0/0 accepted True/True delivered 1/1 calls 1/1 attempts [(1, True, 1, 1)]
SAME           py_stdlib_name_broken: exit 40/40 accepted False/False delivered 3/3 calls 3/3 attempts [(1, False, 0, 1), (2, False, 0, 1), (3, False, 0, 1)]
SAME           py_tests_package: exit 0/0 accepted True/True delivered 1/1 calls 1/1 attempts [(1, True, 1, 1)]
SAME-POLICY    py_baseline_already_pass: exit 0/0 accepted True/True delivered 1/1 calls 1/1 attempts [(1, True, 3, 3)] (headline changed=True)
EXPECTED-DIFF  ctrl_c_interrupt: rc5={'exit': -2, 'tree_unchanged': True, 'has_traceback': True, 'has_interrupted_msg': False, 'has_interrupted_receipt': False} rc6={'exit': 130, 'tree_unchanged': True, 'has_traceback': False, 'has_interrupted_msg': True, 'has_interrupted_receipt': True}

13/13 original scenarios identical; 1/1 baseline-pass policy identical (message-only diff); 1/1 Ctrl-C expected diff correct
```

- 原有 **13/13** 情境（涵蓋第一次過、失敗後第二次過、都沒過交最多、改測試檔、非零退出但通過、刪子目錄檔、新建模組、無測試、`--check`、npm、stdlib 同名模組 P1、tests/ 套件 N1）：結束碼、交件決策、嘗試紀錄、呼叫次數與專案樹逐檔 sha256 **完全相同**。
- `py_baseline_already_pass`（基線已通過）：所有政策欄位與寫回結果**完全相同**（agent 仍跑 1 次、exit 0），只有標題改為先講「測試在 agent 跑之前就全過」。
- `ctrl_c_interrupt`（對前景行程群組送 `SIGINT`，模擬真 Ctrl-C）：**預期不同**——rc5-final 印出 Python traceback 且無收據；rc6 沒有 traceback、印出單行中斷訊息與工作目錄路徑、專案逐位元組不動、寫入標成 `interrupted` 的簽章收據並以 `130` 結束。
