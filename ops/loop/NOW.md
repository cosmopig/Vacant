# NOW.md（r1239，2026-11-08 06:0x UTC）

## 主線
G2.5（vq-el4）18/18 完結；G3（vq-1zf）仍待人類核准（queue 空→0 呼叫）。
**argon 合併（vq-1zf.2）：e847c56e CI 紅燈已根因＋hermetic 守衛修正落地（argon 1d78a8f4／worker 13dd10fb）；合併順延 r1240——等 argon 新 sha CI 🟢。**

## 本輪成果（r1239）
- **一條指令（比上輪好）**：reviewer 驗收指令 `pytest tests/test_reqloop_extract_run_eval.py tests/test_reqloop_g3gate.py`，「/tmp 仍有污染」同環境：上輪 e847c56e CI＝**1 failed**（5052 passed）；本輪修正後＝**53 passed in 0.52s**。
- 紅燈根因（三證據）：ci.sh 共享 worktree 依 qwen27b→argon→worker 跑各分支 HEAD、對已有結果的 sha 不重跑（`if [ -e $CI/$sha.json ]`）；同輪 qwen27b（1d560930 舊 mkdtemp 版 `_tmp_manifest`，green 5051）先跑，05:30 留 3 個 /tmp/g3gate_*（各 manifest.json+tasks）→ argon 守衛斷言 /tmp 絕對乾淨被「別分支舊碼殘留」誤傷。清 /tmp 重跑舊 sha 不可行＋下一輪 qwen27b 必然再污染→hermetic 唯一穩解。
- 修正＝1 檔 1 測試：守衛改前後集合差（只在 `_tmp_manifest` 新建洩漏時失敗）。負控（還原 mkdtemp 版）→守衛命中 1 failed→偵測力不變；還原→53 passed、/tmp 無 g3gate_*。
- 落地：argon **1d78a8f4**（14+/3-、測試碼、不 push）；cherry-pick worker **13dd10fb**（乾淨、g3gate 16 passed）——防 worker 同競態誤傷。
- 紅線核對：/srv/vlab/queue 空（0 模型呼叫）；錨點 qwen27b 樹重驗 repair 2795 行/5147f8c3、extract 1217/e757aec5、reqloop checks f3525b01；合併範圍不觸 vacant_network/；main 未動。

## 下一步（r1240）
`python3 ~/dev/ops/ci_status.py`→**argon 1d78a8f4 🟢**（ci.sh 下輪順序：qwen27b b391818f→argon 1d78a8f4→worker 13dd10fb）→`git merge --no-edit auto/argon`＋53 passed 驗收＋`/tmp` g3gate_* 檢查＋錨點重驗＋`bd close vq-1zf.2`；紅則根因。G3 續等人類核准。
