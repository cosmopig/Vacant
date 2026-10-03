"""finalize — **工作階段結束時的追緝**：沒有回合邊界可用的 agent，問題也要被提出來。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §4.4；LOOP §二-3）：

`opencode run` 在第一個 idle 就結束，沒有 Stop 檢查（既有邊界）；任何 agent 的工作階段也可能
在最後一次 Stop 之後才又改了檔。工作階段結束時，掛鉤在**背景**啟動這支（掛鉤本身的時間預算
Claude 1.5 秒、Codex 1–3 秒，跑不完追緝）：重驗一次契約 → 追緝 → 報告寫進病歷目錄 →
這一跑的結果記進行動者帳本並簽進病歷（同一個工作階段已經由 Stop 記過就不重記，冪等）。
結果只在 `accept`／有必要主張 FAIL 的 `reject` 時算進 adoption；hold／escalate 照記一筆但不算
（`actors.adoption_of`）——這裡的 `flow.check` 用暫存帳本，看不到人工審查。

    python -m vacant_network.trace.finalize <契約路徑> <平台> <工作階段> [<模型>]

## 誠實邊界（改碼請保留）

1. 這時 agent 已經走了：回饋送不到它，只進給人的報告（`vacant trace report`）。
2. 背景行程可能被使用者的關機、登出殺掉；那一次就沒有報告（病歷本身在掛鉤裡已經同步寫完）。
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 3:
        print("usage: python -m vacant_network.trace.finalize <contract> <platform> <session> "
              "[<model>]", file=sys.stderr)
        return 2
    from ..intake import contract as C
    from ..intake import flow
    from . import actors as A
    from .recorder import Recorder
    from .stopcheck import localize
    contract = C.load(args[0])
    platform, session = args[1], args[2]
    model = args[3] if len(args) > 3 and args[3] else None
    res = flow.check(contract, contract.base_dir)
    out = localize(contract, res, cwd=str(contract.base_dir),
                   why_open="the session ended with these open")
    if out is None:
        return 0
    rec = Recorder(contract.base_dir)
    model = model or rec.session_info(platform, session).get("model")
    # hold／escalate（這裡的 `flow.check` 看不到人工審查）不記 adoption（`actors.adoption_of`）
    A.record_run(rec, session_key=f"{platform}:{session}",
                 actor={"platform": platform, "session": session, "model": model},
                 outcome=res.get("outcome"), adoption=A.adoption_of(res), contract=contract,
                 session=session, at="session_end")
    print(out.get("summary") or "nothing open")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
