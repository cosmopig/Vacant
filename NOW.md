# NOW.md（r1240，2026-11-08 06:1x UTC）

## 主線
G2.5（vq-el4）18/18 完結；G3（vq-1zf）發射前置門已交付（88697cd6），仍待人類核准（queue 空→0 呼叫）。
**argon 合併（vq-1zf.2）目標改為 1d78a8f4**：e847c56e CI 🔴（qwen27b 舊 mkdtemp 殘留 /tmp/g3gate_* 被絕對乾淨守衛誤傷）→ argon 1d78a8f4 守衛改 hermetic（前後集合差）、worker 同步 13dd10fb。

## 本輪成果（r1240）
- 審查 1d78a8f4（1 檔 1 測試）：baseline 集合差邏輯正確，對 mkdtemp 回歸偵測力保留；不觸 repair/extract。
- 合併預演樹（qwen27b 491c1828＋argon 1d78a8f4，RC0 無衝突、範圍＝r1238 同 4 檔）：reviewer 驗收指令 **53 passed in 0.56s**。
- **比上輪好**：/tmp 污染（＝e847c56e 紅燈條件）下 hermetic 守衛 **1 passed**（舊版同條件＝紅燈）；負控（還原 mkdtemp 版）**1 failed**（命中）。收尾清乾淨、/tmp 無殘留。
- 錨點重驗（合併樹）：repair 2795 行/5147f8c3、extract 1217 行/e757aec5、checks f3525b01 全一致。
- 紅線：/srv/vlab/queue 空（G3 未發射、0 呼叫）；main 未動。

## 下一步（r1241）
`python3 ~/dev/ops/ci_status.py` → **`ci/1d78a8f4.json` 🟢**（且 qwen27b 491c1828 🟢）→ `git merge --no-edit auto/argon`＋53 passed 驗收＋`ls /tmp/g3gate_*` 空＋錨點重驗＋`bd close vq-1zf.2`；紅/缺則 DECISION 入 STATE 續等（CI 10 分鐘週期、每支 ~14 分鐘，預計 ~06:4x 起逐支出燈；不輪詢）。之後續等 G3 人類核准。
