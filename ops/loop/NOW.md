# NOW.md — 当前状态与下一步

## 当前状态（r1302，2026-11-09）
- CI 红灯根因收口：qwen27b@bd93d42e2（r1301）RED（2 failed＝两 live 测 verdict/covers，822s）——根因按证据非猜测：CI detached 下 _diff_base() 锚定被测 commit（r1300/vq-el4.45 防假绿设计），r1301 redo 簿记已推进三分支（worker@569d7f625／argon@8ee9fe968）→ 被测 commit 的簿记必然落后＝真实陈述非误报；其余 7 项全 OK（anchors 5／ci_contract 2／filing 6/6 MATCH／g3gate NOT_FIRED+PLAN_OK／bk 同步）。不弱化守卫（弱化＝复活假绿洞）。
- 现三分支状态绿（本轮新跑）：freeze_check 9/9 OK FROZEN_STATE_OK rc=0；18 passed；in-scope diff 0×2；两 worktree 干净、0 staged。
- r1300 SHAs（c3e918308/d894dffc/3395dd32）无 CI 工件＝runner 只测当时 HEAD（ci.sh 每 10 分钟 rev-parse 分支），r1301 先取代——定性「被取代」非「遗漏」；上轮未验证项以此收口。
- CI 收口（本轮一次读取）：argon@8ee9fe968（现 tip）GREEN——5077 passed／0 failed／74 skipped（831s）＝现 tip 绿灯实证，与根因分析互证；runner 继测 worker@368768d77（本轮 sync HEAD）。
- vq-el4 45/45 全闭（0 open）；唯一 ready＝vq-1zf（G3）待人类核准；/srv/vlab/queue 空；tickets/open 空；无新人类指示（ops/ 最新仍 11-07）。

## Next（按优先级）
1. CI：下轮首一次读 worker@368768d77＋本轮簿记新 HEAD 之 CI（不 poll）。三分支已同步，预期绿；若 diff 项因簿记推进而红＝r1302 条目①同型真实陈述（非缺陷）；其他红→按证据诊断（不猜）。
2. vq-1zf G3：等人类明确批准后开 fire（红线：不自行开、不入 /srv/vlab/queue）。
3. CI 通道／auto-ci.yml disabled 状态：等人类裁决，不重诊断、不翻开关。

## 边界（不变）
- 红线：不 push（loop 自推）、.github/workflows/ 只读、hidden/scorer 不读、G3 未批准不发射、冻结 4 文件（repair/extract/checks/run_eval）＋filing 不动。
- 模型调用只走 `glm` CLI。
