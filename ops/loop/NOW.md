# NOW.md — 当前状态与下一步

## 当前状态（r1300，2026-11-09）
- vq-el4.45 开→关（diff 假绿洞闭环；1 文件、1 测试、1 命令输出改善）：
  - 缺陷（沙盒实证，TDD RED 先于修复）：CI（ci.sh）detached checkout 被测 commit，repo 内分支 ref 指向执行时点 live 分支 HEAD——旧 check_diff 用 `git diff <worktree> auto/qwen27b` 量的是 tip 状态而非被测 commit：worktree 已同步新 tip 时，旧 commit 自己的 in-scope 文件与 worktree 不同仍判 0 files OK＝假绿（H-0 同构：量错对象的绿灯就是漏洞成因）。实证：被测 commit ops/STATE.md=v1、两 ref 指 v2 tip → ref 基 0 files OK／HEAD 基 1 file BROKEN。
  - 修复：ops/reqloop/freeze_check.py 新增 `_diff_base()`——HEAD detached（CI 沙盒）时 base=HEAD（被测 commit），否则 base=auto/qwen27b（本地 dev/worktree 旧口径不变）；check_diff 用该 base、detail 点名。
  - 测试：tests/test_reqloop_freeze_check.py 新增 `test_diff_anchor_negative_control`（detached 旧 commit→BROKEN 且点名差异文件；detached 同步 commit→OK；attached HEAD→OK 口径不变）。
  - 验收：18 passed（freeze_check 11／anchors 5／ci_contract 2，was 17）＋freeze_check live 9/9 OK VERDICT: FROZEN_STATE_OK rc=0。
- vq-el4 全 45 项已关闭（bd list --parent vq-el4 --all：0 open）。
- CI：新 HEAD（7a228d6a8/f0e46db71/04ac6417e）+ 本轮 commit 在 runner 队列；旧 CI RED（90a5fbc4/eafda98f5/39ccc65ea）＝pre-sync 时点，非代码缺陷。
- beads 队列空、tickets/open 空、无新人类指示。

## Next（按优先级）
1. CI：新 HEAD（含 r1300 commit）跑完读一次结果（不 poll）。绿→闭环；红→按证据诊断（不猜）。r1300 起新 HEAD 的 diff 项锚定被测 commit；旧 SHA 的 CI 用旧码旧口径。
2. vq-1zf G3：等人类明确批准后开 fire（红线：不自行开）。
3. CI 通道/auto-ci.yml disabled 状态：等人类裁决，不重诊断。

## 边界（不变）
- 红线：不 push（loop 自推）、.github/workflows/ 只读、hidden/scorer 不读、G3 未批准不发射、冻结 4 文件（repair/extract/checks/run_eval）＋filing 不动。
- 模型调用只走 `glm` CLI。
