
## round 400 (2026-10-30 23:5x) · P20261030_2347-1 同步 e006 首格 C 臂真實用量至 disk_top_priority §2 總覽表 (b) 欄＋外部副本（結案）
- 主軸：ASSIGNMENT 🔴最優先「量它從零開始一天長多少」＋驗收條件 4(b)；e006 全盤首格 C 臂真機用量入總覽表。
- 做了：§2-4(b) 欄 e005 條目後追加 e006 OpenCode 五臂全盤 C 臂 1 格實測（49,903 B／25,829 B／ratio 0.000186／verdict=PASS／vacant_sha=bf1a9f1a）；外部副本 cp 同步、diff 空 rc=0。
- 驗證：數字逐項對 /srv/vlab/runs/e006_opencode_polyglot C-r1 cell.json 實測核實（49903/25829/bf1a9f1a 全中）；`envelope_compliance.py e006_opencode_polyglot` 現跑 verdict=PASS（C 臂 1/1 PASS）；驗收字面 diff 空 rc=0＋grep "49,903 B" 命中 rc=0（改前 0 命中已核）；(a)/(c) 欄、§1/§3 零改動；commit f4453acf；工單→done/（結果 3 欄）、doing/ 0 張。
- 沒驗證：f4453acf CI 未出（純文檔 1 行）；e006 其餘格仍跑中（/srv/vlab/done 無 07_e006_*），全盤判定仍待完賽；M 臂第二 agent 路徑仍 UNKNOWN。
- 下一步：查 /srv/vlab/done 之 07_e006_* 格與 infra 計數；全盤完賽跑 `opencode_cell_audit.py e006_opencode_polyglot`＋e006_verdict 對 REPORT.json 出判定；M 臂 34 格出分即複測樣本。

## round 412 (2026-10-31 00:4x) · P20261031_0018-5 e006_verdict 人讀模式 CLI 契約擴充至常規回歸測試（結案）
- 主軸：ASSIGNMENT「研發工具需納入回歸測試」＋主軸 1/3；把 e006_verdict.py 預設終端人讀模式（未帶 --json）輸出與退出碼 0 契約鎖進 pytest，防 e006 判定工具的人讀路徑退化。
- 做了：tests/test_vlab_tools.py::test_e006_verdict_selftest_and_cli 尾端純追加 8 行：capsys 排空後 main(["exp_mock","--runs-dir",tmp]) == 0，且 stdout 含「e006_verdict m=」「H-acc」「cost(2×A 紅線)」三項（先核 e006_verdict.py render_text L141-157 與 main L251 確認字面量與 print 路徑）。既有 JSON 與位置參數斷言零改動（1 檔 +8/−0）。
- 驗證：驗收字面 pytest -k test_e006_verdict_selftest_and_cli → 1 passed、EXIT=0；整檔 66 項 EXIT=0；git diff 純追加 0 刪除。commit 7df478a8；工單→done/、doing/ 0 張。
- 沒驗證：7df478a8 CI 未出（純測試 8 行）；人讀輸出以 mock REPORT 驗證，真實 e006 REPORT 待 170 格全盤完賽。
- 下一步：查 /srv/vlab/done 之 07_e006_* 格；全盤完賽跑 e006_verdict＋opencode_cell_audit 出判定；M 臂 34 格出分即複測樣本。
