# NOW.md — 当前状态与下一步

## 当前状态（r1301，2026-11-09）
- 验证／维护轮（0 代码改动、0 model calls）：
  - CI 一次读（不 poll），上轮未验证项收口：worker@f0e46db71（r1299 sync HEAD）GREEN 5076 passed/0 failed/74 skipped（822s）——pre-sync 39ccc65ea 的 2 live 测红（freeze_check verdict/covers）经 sync 解消；上轮 LATEST_worker RED(2 failed)→本轮 GREEN＝本轮指令输出优于上轮。LATEST 三绿（qwen27b@26ed86a1c、argon@04ac6417e、worker@f0e46db71，皆 5076/0/74）。
  - r1300 SHAs（c3e918308/d894dffc/3395dd32）无 ci/<sha>.json；state.json idle（队列清完）；c3e918308 已在 origin（待 runner 取）、d894dffc/3395dd32 仅本地（loop 轮末自推→入 CI）；不 poll、不重诊断。
  - 审查指示 #1/#2/#3 本轮复核：freeze_check 9/9 OK VERDICT: FROZEN_STATE_OK rc=0；18 passed（freeze_check 11/anchors 5/ci_contract 2）；in-scope diff 0×2；两 worktree 干净、0 staged。
- vq-el4 全 45 项已关闭（0 open）；唯一 ready＝vq-1zf（G3，待人类核准）；/srv/vlab/queue 空；无新工单；无新人类指示（ops/ 最新仍 11-07）。

## Next（按优先级）
1. CI：下轮首一次读 r1300 SHAs（c3e918308/d894dffc/3395dd32）结果（不 poll）。绿→闭环；红→按证据诊断（不猜）。r1300 起新 HEAD 的 diff 项锚定被测 commit；旧 SHA 用旧码旧口径。
2. vq-1zf G3：等人类明确批准后开 fire（红线：不自行开、不入 /srv/vlab/queue）。
3. CI 通道／auto-ci.yml disabled 状态：等人类裁决，不重诊断、不翻开关。

## 边界（不变）
- 红线：不 push（loop 自推）、.github/workflows/ 只读、hidden/scorer 不读、G3 未批准不发射、冻结 4 文件（repair/extract/checks/run_eval）＋filing 不动。
- 模型调用只走 `glm` CLI。
