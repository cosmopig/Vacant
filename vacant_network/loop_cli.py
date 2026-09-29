"""loop_cli — `vacant loop …`：把迴圈放在父行程的指令列。

這支在架構裡承重什麼（`decisions/DECISION_20260929_LOOP_WITHOUT_POSSESSION.md` §三）

現有的兩種接線都要求**平台配合**：`vrun` 的通道中介要求 agent 用白名單上的金鑰變數，
`adapters` 的回合結束回饋要求平台有 stop 等價事件。量到的後果是**靜默無效**——
病歷與簽據都正常，零個裁決（`decision` §一 W1／W2）。

`vacant loop` 兩樣都不要：它不碰網路、不掛鉤，只把 agent 當子行程 spawn，
在退出碼上判斷回合結束，在行程**之外**做裁決。所以任何「是一個可 spawn 的 CLI」
的 agent 平台都直接獲得完整能力（`loop.py` 的誠實邊界 1–5）。

退出碼（與 `vacant run` 的 20–26 分開，那一套的語意不動）：

| 碼 | 意思 |
|---|---|
| 0 | accept：最後一次嘗試通過可見套件，且放行讀回成立 |
| 20 | refuse：裁決拒絕（accept 之前就擋下） |
| 21 | exhausted：預算用完仍未通過。**不是通過** |
| 22 | infra_void：裁決點自己壞掉。既不是成功也不是成果的錯 |
| 2 | 用法錯誤 |
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

from . import loop as L

EXIT = {"accept": L.EXIT_ACCEPT, "refuse": L.EXIT_REFUSE,
        "exhausted": L.EXIT_EXHAUSTED, "infra": L.EXIT_INFRA}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="vacant loop",
        description=(
            "把任意 CLI agent 放進一個由收件端擁有的迴圈：跑、驗收、不合格就把"
            "可見套件自己的失敗原文送回下一次嘗試，通過才放行。\n"
            "不中介模型通道、不掛鉤 —— 任何可 spawn 的 agent 都適用。\n\n"
            "    vacant loop --suite ./acceptance --attempts 3 -- opencode run \"做這件事\"\n\n"
            "⚠ --suite 必須在工作區外：agent 改得到的驗收不是驗收。"),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd(),
                    help="agent 的工作區（預設目前目錄）")
    ap.add_argument("--suite", type=pathlib.Path, required=True,
                    help="可見驗收目錄（內含 test_*.py），必須在工作區外")
    ap.add_argument("--attempts", type=int, default=L.DEFAULT_ATTEMPTS,
                    help=f"嘗試上限（預設 {L.DEFAULT_ATTEMPTS}）。成本上限不是目標值")
    ap.add_argument("--feedback", choices=L.FEEDBACK_MODES, default="prompt",
                    help="回饋走哪條管道：prompt（預設，接在下一個提示詞尾端）／"
                         "file（寫進工作區 VACANT_FEEDBACK.md）／both／none")
    ap.add_argument("--timeout", type=float, default=L.DEFAULT_TIMEOUT_S,
                    help="每次嘗試的時限秒數")
    ap.add_argument("--intake-root", type=pathlib.Path, default=None,
                    help="收件口的 home（簽章金鑰、帳本、隔離區）。"
                         "沒有它就用注入的裁決點，不能走 intake")
    ap.add_argument("--json", action="store_true", help="輸出機器可讀 JSON")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="`--` 之後的整條 agent 命令")
    return ap


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    ap = build_parser()
    args = ap.parse_args(raw)
    cmd = list(args.cmd)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("vacant loop: 缺少 agent 命令（用 `--` 分隔）", file=sys.stderr)
        return 2

    import os
    env = dict(os.environ)
    if args.intake_root:
        env["VACANT_INTAKE_ROOT"] = str(args.intake_root.resolve())

    def emit(obj: dict[str, Any]) -> None:
        if args.json:
            print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
        else:
            for a in obj["attempts"]:
                print(f"attempt {a['n']}: agent_rc={a['agent_rc']} "
                      f"outcome={a['outcome']} wall={a['wall_s']}s")
                if a["outcome"] != "accept" and a.get("detail_head"):
                    print("   " + str(a["detail_head"])[:200].replace("\n", " "))
            print(f"{obj['verdict']}: {obj['attempts_used']} attempt(s), "
                  f"{obj['wall_s']}s, exit {obj['exit_code']}")

    try:
        r = L.run_loop(workspace=args.workspace, suite=args.suite, cmd=cmd,
                       attempts=args.attempts, feedback=args.feedback,
                       timeout_s=args.timeout, env=env)
    except ValueError as e:
        print(f"vacant loop: {e}", file=sys.stderr)
        return 2

    verdict = ("infra_void" if r.accepted is None
               else "accept" if r.accepted
               else "exhausted" if r.total_attempts_used >= args.attempts
               else "refuse")
    emit({"verdict": verdict, "exit_code": r.exit_code,
          "attempts_used": r.total_attempts_used,
          "attempts": [{"n": a.n, "agent_rc": a.agent_rc, "timed_out": a.timed_out,
                        "wall_s": a.wall_s, "outcome": a.outcome,
                        "detail_head": a.detail[:400]} for a in r.attempts],
          "wall_s": r.wall_s, "artifact_sha256": r.artifact_sha256})
    return r.exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
