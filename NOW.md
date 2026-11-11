# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-11 r1467：1843-2 驗收核實（mainline＋argon 雙位綠）；票結案候 worker 收斂）
- 1843-2 實作＝r1466（rc=124 超時）遺留、本輪首驗：`python3 ops/audits/labd_instance_and_env_audit.py --audit-e016` → **VERDICT: E016_ENVLEAK_AUDIT_OK rc=0**（負控制 attempt1 14 格/11 洩/3 合規＋missing 2＝book_store-C、bowling-A；正控制 attempt2 102 格/0 洩；與 r1458 逐格實量吻合）；`pytest tests/test_labd_instance_and_env_audit.py` → 12 passed（mainline＋argon 皆 RC=0）；evidence JSON 重跑逐位元組一致（決定性）。
- argon（idle）全樹鏡像 mainline HEAD（3 檔：audit py／test py／evidence JSON）＋commit；先驗 0 独占檔；in-scope diff 0 → diff_argon OK。
- freeze_check 10 OK／2 紅（快照）：diff_worker（no sync counterpart）＋wt_clean——皆＝worker 於同票迭代（round 79 21:35 WIP commit、round 80 在進），非碼回歸。worker r79 在 worktree 根留空檔 test_audit.py（收編時須一併處置）。
- CI 直讀一次（不 poll）：f31bfb35 5232/2、c8124888d 5223/2（2 敗皆 test_reqloop_freeze_check 兩 verdict 案＝執行時 worker 在進狀態）；**4bfa4dab（mainline）無結果＝UNKNOWN**、下輪直讀。
- 票 1843-2 仍在 doing/（worker 在進）：本輪不碰在進產物——結案三件（票尾 3 行＋mv done/＋BACKLOG 項 10 註審計依據）延至 r1468。BACKLOG 項 10 現 [x]（21:14 worker round 77 期間所改、審計依據未註）。
- 誠實記帳：mainline（r1466）與 worker（rounds 74–79 WIP）對同票並行實作；canonical＝mainline（已驗）；worker WIP 收斂後同步收編、不宣稱雙線完成。

## 紅線（契約，不改）
- 不 push（loop 自動 push auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不變；g3.py 僅依核准工單改動。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值＝UNKNOWN 不 0；hidden_after=UNKNOWN。

## 下一步（r1468）
1. worker 收斂（現 rounds ≥80 於同票迭代）→串行審查：保留 mainline 實作（canonical、已驗），worker 並行實作留痕。
2. worker 同步至 mainline（git checkout auto/qwen27b -- .＋git rm 多餘 tracked 檔如 test_audit.py＋commit）→diff_worker/wt_clean 收斂。
3. 票 1843-2 結案：票尾 3 行＋mv done/＋BACKLOG 項 10 註審計依據（`--audit-e016` VERDICT OK＋evidence JSON＋commit）。
4. 三分支 freeze_check 復測（期望 12/12）＋test_reqloop_freeze_check verdict 綠＋4bfa4dab CI 直讀（一次、不 poll）。
5. G3.1 H2.0 重發＝人類裁決（H2_0_REFUTED r1447a 仍有效、不碰）。
