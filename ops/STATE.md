
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

## round 413 (2026-10-31 00:4x) · P20261031_0033-1 同步 e006 第三格 C 臂真實用量至 disk_top_priority §2 總覽表（結案）
- 主軸：ASSIGNMENT 🔴最優先用量上限與驗收條件 4(b)；人類在 §2 總覽表看到 OpenCode 真實 agent 3 個 C 臂格子的最新合規數據。
- 做了：disk_top_priority.md §2-4(b) 欄 e006 段「2 格實測」→「3 格實測」：追加「③ pg_book_store vacant_home_bytes 50,155 B（49.0 KB，vacant_objects_bytes 31,139 B、ratio 0.000187）」、尾段「C 臂 min 49,903 B／max 116,444 B」→「C 臂 3 格 min 49,903 B／med 50,155 B／max 116,444 B 均遠低於 256 MiB 穩態封頂（最高 0.043%）」、完賽標記 pg_beer_song 00:01 → pg_book_store 00:22；(a)/(c) 欄與 e001-e003/e005 既有數據零改動、256 MiB 封頂常數未動；~/dev/ops/packets/ 主副本與 repo 副本 cp 同步 bit-identical（1 檔 +1/−1）。
- 驗證：數字先經 cell.json 實跑核實（vacant_home_bytes=50,155、vacant_objects_bytes=31,139、vacant_sha=bf1a9f1a…、finished 2026-10-31T00:22:50、score 20/20 pass）＋envelope_compliance.py 實跑（overall PASS、C 臂 3/3 PASS、home_bytes_min_med_max=[49903,50155,116444]、NA 1=infra）；驗收 diff 空＋grep「pg_book_store vacant_home_bytes 50,155 B」命中 RC=0（改前舊文僅 2 格、必 0 命中）。commit dbe8fd50；工單→done/、doing/ 0 張（順手刪 1 個空檔 typo 工單殘件）。
- DECISION: 驗收指令首路徑 dev/ops/… 係 ~/dev 相對、次路徑 repo 相對（基準點混用），在 repo 內逐字執行會 diff rc=2｜兩路徑指向同一對檔案且語義無歧義，屬路徑基準點筆誤而非驗收壞掉；用絕對路徑等效執行並已註明於工單檔尾，未走 bounced。
- 沒驗證：dbe8fd50 CI 未出（純文檔 1 行）；e006 全盤未完賽（C 臂 4 格中 1 infra、REPORT cells_scored=15），正式判定仍待全盤完賽。
- 下一步：查 /srv/vlab/done 之 07_e006_* 格；全盤完賽跑 e006_verdict＋opencode_cell_audit 出判定；M 臂 34 格出分即複測樣本。
