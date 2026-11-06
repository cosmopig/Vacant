# STATE
- r1136：補上 g2 **--baseline** 離線 baseline 命令（11-06#4「獨立可見檢查給出可重現內容反例」＋工單「目前行為」）：1 檔（g2.py +98）＋1 測試（test_reqloop_g2.py +49），純新增、不改既有行為。兩草稿皆真壞（各有 required FAIL）、整段 JSON 無洩漏（1628/0.020500 缺席、草稿自身錯值在場）、pytest 40/40。離線、不呼叫模型、不發射；改動限 g2.py＋測試（未動 ops 數據/審計）。真實 6550d7a8 切片仍 NOT_fired（發射要授權）。
- r1135 完成：effects2_20261106（28 格 @4d4b8102）彙整必答（11-06#2）：同草稿已核對（14 題雙臂起始草稿 hash 相等、16 檔 pin 相符）、tamper 0、bad9 localized 9/9 vs generic 7/9、對→錯 0；成本差 112 calls/4.11M tok 買 +2 題（集中在 dabstep-10），開發選樣單 rep 不宣稱較好。
- 交付：ops/audits/effects2_20261106_analyze.py（--selftest 負控通過）＋ effects2_20261106_analysis.json（RC=0 ANALYSIS_OK）。
- 9329be88 manifest 待辦已核實解除：ops/reqloop/g2/effect_manifest.json 實際 sha 即 9329be88…，NOW.md 舊待辦已不存在，無新待辦。
- 未動 main、未 push（loop 自動 push auto/qwen27b）、未讀 hidden/scorer、未改產品碼、未加 regex/prompt/重跑。
- 下一步候選：11-06#4 真實 CSV/JSON 任務切片（manifest sha 6550d7a8… 已凍結 NOT_fired；離線三門 verify_frozen＋--dry-run＋--baseline 已就緒，待授權才 fire）；bd vq-5nz.49 已關。
