# NOW.md（r1242 收尾，2026-11-08 ~06:5x UTC）

## 主線
G2.5（vq-el4）18/18；**argon 合併完成（vq-1zf.2 已 close，merge ab3b6a67）**；G3（vq-1zf）等人類核准（queue 空→0 呼叫）。

## r1242 成果
- CI 門：1d78a8f4 🟢 5053 passed/5126 collected ≥ 491c1828 5124 collected；bf8a9a59 純簿記（diff 178a2800＝僅 NOW/STATE→產品碼樹＝已驗收預演樹）。
- merge RC0（ab3b6a67）範圍恰 4 檔；驗收 **53 passed in 0.71s**；/tmp g3gate_* 空。
- 錨點：repair 2795/5147f8c3、extract 1217/e757aec5、checks f3525b01；三分支 g3gate 6f93f4e5 全對齊（worker 13dd10fb 已同步）。
- bd close vq-1zf.2；tickets/open 空（審查 #2 三分支同步已滿足、無新工單）。

## 下一步（r1243，照序）
1. 輪首核 CI：ab3b6a67（qwen27b 新 HEAD）、13dd10fb（worker）、bf8a9a59 依 ci.sh 順序出燈；紅燈先查是否 g3gate/extract_run_eval 範圍（環境類才 skip＋原因，不刪測試）。
2. G3：仍等人類核准——不發射、不入 /srv/vlab/queue、0 模型呼叫。
3. 無其他產品工單（審查範圍限 R-loop 與產品行為）。

## 紅線
queue 空・0 模型呼叫・main 未動・/tmp g3gate 殘留 0・repair 2795 行/5147f8c3、extract 1217 行/e757aec5、checks f3525b01・不讀 hidden/scorer・不自 git push（迴圈自動推）。
