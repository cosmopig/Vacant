# NOW

## 現在在哪（r1139）
- 工單 P20261106_2040-1 完成：check_csv_structure 支援 JSON 交付物（records.json 物件陣列／records/rows/data 包裝）＋`table_structure` 別名分派。TDD 先紅（empty_csv）後綠。
- commit 51e3e5df（2 檔：checks.py 3 行＋1 新測試）。驗收 `1 passed, 51 deselected`；test_reqloop_checks.py 52 passed；g2/repair/real_slice 154 passed。0 模型呼叫、0 發射、未動 main、未自 push。
- 雙切片（皆 NOT_fired）：A=realtask_manifest.json（sha 6550d7a8、4 格）＋B=real_slice/manifest.json（dab_378、2 格）；離線三門 verify_frozen＋--dry-run＋--baseline 全綠。

## 下一步
- 若授權：fire A（候選）或 B（同口徑替代）——模型流量＝新成本、先另報；二擇一或分批、不並跑。
- 未授權：維持雙凍結、0 新票、不加 regex／靜態 prompt／重跑；候需求端點名 vq-6rp、vq-5nz.6。

## 紅線
不碰 main、不自 push（loop 自動推 auto/qwen27b）、不讀 /srv/eval hidden／scorer 源、缺值＝UNKNOWN 不填 0、不為「每輪有 commit」加 regex／靜態 prompt／未授權重跑／純文檔修補、批內開發選樣不宣稱 localized 較好、兩臂起始 hash 不一致不稱同草稿公平比較、tamper/UNKNOWN 不算成功。
