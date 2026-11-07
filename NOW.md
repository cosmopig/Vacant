# 現在（第 1219 輪後，2026-11-07 23:2x UTC）

## r1219：產品真 bug 例外——repo 唯一 tracked 絕對 symlink → 真實檔＋CI 守護
- 授權依據：vq-el4 全閉、open 空 → 「CI 紅燈和產品真 bug 例外」＋執行器「本輪須一條指令輸出變好」。
- 缺陷：audits/e016…envleak_recompute.py 是 tracked 絕對 symlink（→/home/user1/dev/ops/audits/...）＝worker 紅燈同型（另一 checkout 必斷、FileNotFoundError）。
- TDD：新 tests/test_repo_no_absolute_symlinks.py（tracked symlink 目標不得以 / 開頭）→ 修前 1 failed 點名 → 修後 **1 passed**；`-k 'reqloop or beads'` 353 passed 0 failed；0 模型呼叫。
- commit auto/qwen27b **b5355486**（mode 120000→100644、內容 sha256 4c9f2731… 不變、ops/audits 原件未動）；未 push；vq-0tr close。

## CI（本地 vacant-ci）
- auto/worker aca58a95 🟢 5034/0（23:03）→ 審查指示4 達標，三分支已全綠過。
- auto/argon 05989682 🟢 5033/0；auto/qwen27b 05989682 🟢 5033/0；46e634b8＋b5355486 待 pickup（~14min/pass、自動）。

## 下一步
1. 下輪巡 b5355486 CI → 應 🟢（新測試純 git index 斷言、無模型/網絡）；若紅＝先查 CI 環境。
2. 等審查派工；G3 須派工，不自發射大成本。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden/scorer；不繞 glm 直連 vibe；
不改 repair.py／G1 requirements.json／凍結快照／官方鎖檔 eval_phase3_glm53.json；成本缺值＝UNKNOWN 不填 0。
