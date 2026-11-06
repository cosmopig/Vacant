# NOW

## 現在在哪（r1137）
- r1137：審查點名兩檔補實讀＋redo 依賴部分——effects_20261105_summary.json（舊 50 格參考數 7/6・7/4、r2w 0、current_code 50/50、scope_note 開發選樣／單 rep／缺值 None／hidden_after UNKNOWN，與 11-06#6 完全一致）＋ repair.py（exit 0/20/22 語義、min_rounds g1/l0、stall=2、authoritative snapshot＋保留約束，與 baseline 記錄一致）；皆無須更正。另修狀態檔分叉：~/dev/ops/loop/NOW.md＋~/dev/ops/STATE.md 原為 r1134 舊內容（loop hook 讀的就是它），備份後改 symlink 指 repo 檔。199 passed；--baseline EXIT=0。
- effects2_20261106（28 格 @4d4b8102）已於 r1135 彙整（ops/audits/effects2_20261106_analysis.json）：bad9 l 9/9 vs g 7/9、對→錯 0、tamper 0；成本差 112 calls/4.11M tok 買 +2 題（集中 dabstep-10）；開發選樣單 rep 不宣稱較好。
- 6550d7a8 真實切片（e013 dab_055＋e014 dabstep-1273、4 格）凍結 **NOT_fired**；離線三門 verify_frozen＋--dry-run＋--baseline 全過。
- HEAD 6c770fee（r1136 自動提交；CI 未跑完、不阻塞）；/srv/vlab/queue 空；tickets doing/open 空。

## 下一步
- 若授權：fire 6550d7a8 切片（要模型流量，屬新成本、先另報）；未授權：effects2 維持不動、只核對＋收尾，0 新 per-error 票、不製造工作。
- 候需求端點名：vq-6rp（dabstep-1753 硬缺口）；G3 vq-5nz.6（未點名不擴量）。

## 紅線
不碰 main、不自 push（loop 自動推 auto/qwen27b）、不讀 /srv/eval hidden／scorer 源、缺值＝UNKNOWN 不填 0、不為「每輪有 commit」加 regex／靜態 prompt／未授權重跑／純文件修補、批內開發選樣不宣稱 localized 較好、兩臂起始 hash 不一致不稱同草稿公平比較、tamper/UNKNOWN 不算成功。
