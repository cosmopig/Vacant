# NOW.md（r1241 收尾，2026-11-08 ~06:50 UTC）

## 主线
G2.5（vq-el4）18/18 完成；G3（vq-1zf）等人类批准（/srv/vlab/queue 空→0 呼叫）。
**唯一待办动作：合并 argon（vq-1zf.2）**——代码已审查、预演全绿，只欠 CI 绿灯。

## r1241 成果
- 审查点名 6 档全数补开并接地：builder（diff 仅 REPO 1 行 parents[2]，正确）；g3gate hermetic 守卫（前后集合差，逐行核）；extract_run_eval 新测试 worktree_isolation（＋25 行，r1240 未开→本轮补审，逻辑正确）；extract.py（quote_is_verbatim:132、白名單 736-755、GlmClient:927 唯一 glm 入口）；repair.py（頭部規則、detect_crash_giveup:1290）；effects summary（per_arm 全數重驗：w2r 7/6/7/4、still 3/4/3/6、r2w 0、tokens 四組加總全 MATCH、api 915=365+550、457=165+292）。
- filing 重算：code 三檔＋sources 三檔 sha256 全 MATCH；三門 PASS（39/39・9/9・errors0）。
- 一條指令比上輪好：預演在**精確終樹** 178a2800＋1d78a8f4（簿記 commit 後複做）與 bd63231d＋1d78a8f4 兩棵皆 RC0、範圍 4 檔、驗收 **53 passed**（0.59s／0.65s）；污染條件（/tmp 6 殘留＝e847c56e 紅燈場景）hermetic 守衛 **1 passed**；錨點 5147f8c3/2795、e757aec5/1217、f3525b01 全一致。
- 51 vs 53 解明：51＝合併前 qwen27b（36+15）、53＝合併後（37+16，argon ＋2 測試）——非矛盾。
- DECISION：合併順延 r1242（本輪 1800s 硬限內 qwen27b HEAD 178a2800 不可能出燈；不輪詢、不繞 CI 門）。

## CI 實況（06:2x）
- 491c1828 🟢（5051 passed）；1d78a8f4 跑中（ETA ~06:42）；13dd10fb 其後（~06:56）；qwen27b HEAD（178a2800，本輪簿記 commit）下一 pass（~07:1x）。
- ci.sh 序列跑於 /var/tmp/ci-wt——未觸。

## 下一步（r1242，照序）
1. `ls ~/dev/ops/ci/1d78a8f4*.json ~/dev/ops/ci/178a2800*.json` 且兩份 green=true（178a2800＝qwen27b 當前 HEAD，以 `git rev-parse auto/qwen27b` 為準）（或用 `python3 ~/dev/ops/ci_status.py` 若存在）。
2. 綠 → `cd ~/dev/Vacant && git merge --no-edit auto/argon`（RC0 預演已證）→ 驗收 `~/dev/Vacant/.venv/bin/python -m pytest tests/test_reqloop_extract_run_eval.py tests/test_reqloop_g3gate.py -v` 期望 **53 passed** → `ls /tmp/g3gate_*` 須空（合併前 qwen27b 的 CI 跑會產 3 殘留，驗收前先清）→ 錨點複核 → `bd close vq-1zf.2 --reason ...` → 簿記 commit。
3. 紅/缺 → STATE 記 DECISION 續等；不輪詢。
4. 之後：等 G3 人類批准（不發射、不排隊）。

## 紅線
queue 空・0 模型呼叫・main 未動・/tmp g3gate 殘留 0・repair 2795 行/5147f8c3、extract 1217 行/e757aec5、checks f3525b01・不讀 hidden/scorer。
