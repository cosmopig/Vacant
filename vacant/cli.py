"""vacant CLI — 生成 / 檢視 vacant，跑 demo 與自我檢測。架構總規格 §6.2。

    vacant init <name> [--niche reverse --niche caesar3] [--root DIR]
    vacant info  <name> [--root DIR]
    vacant call  <caller> <niche> --input <s> [--root DIR]   # 需先 init 出 caller + 一個能解該 niche 的 expert
    vacant demo  [--root DIR]                                 # 跑 §11 對照實驗
    vacant selftest                                           # 端到端冒煙測試（暫存目錄）

預設 root = ~/.vacant（信任庫 + HERMES_HOME 都在此；睡著的 vacant 就是這包檔）。
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .body import VacantBody
from .host import Host
from .tasks import NICHES, make_task


def _default_root() -> Path:
    return Path.home() / ".vacant"


def _load_host_with_existing(root: Path) -> Host:
    """把 root 下已存在的 vacant 身體全部 adopt 進一個 Host（供 call）。"""
    h = Host(root)
    for d in sorted(p for p in root.iterdir() if (p / "trust" / "vacant_id").exists()):
        h.adopt(d.name)
    return h


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if (root / args.name / "trust" / "vacant_id").exists():
        print(f"已存在：{args.name}（{root / args.name}）", file=sys.stderr)
        return 1
    body = VacantBody.create(args.name, root, niches=args.niche or [], controller=args.controller)
    print(f"鑄出 vacant：{args.name}")
    print(f"  vacant_id : {body.identity.vacant_id}")
    print(f"  niches    : {body.card.niches or '（無）'}")
    print(f"  身體位置  : {body.dir}")
    print(f"    trust/  信任庫（keypair / logbook / reputation）")
    print(f"    home/   HERMES_HOME（skills / memory，agent 的能力庫）")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    root = Path(args.root)
    try:
        body = VacantBody.load(args.name, root)
    except FileNotFoundError:
        print(f"找不到：{args.name}（root={root}）", file=sys.stderr)
        return 1
    from .substrate import load_skills

    ok = body.logbook.verify_chain(body.public_identity())
    print(f"vacant: {args.name}")
    print(f"  vacant_id   : {body.identity.vacant_id}")
    print(f"  niches      : {body.card.niches or '（無）'}")
    print(f"  logbook     : {len(body.logbook)} 筆，鏈驗 {'✓ OK' if ok else '✗ FAILED'}")
    print(f"  已習得 skills: {sorted(load_skills(body.home_dir)) or '（無）'}")
    if body.logbook.entries:
        kinds: dict[str, int] = {}
        for e in body.logbook.entries:
            kinds[e.type] = kinds.get(e.type, 0) + 1
        print(f"  事件分布    : {kinds}")
    return 0


def cmd_call(args: argparse.Namespace) -> int:
    root = Path(args.root)
    h = _load_host_with_existing(root)
    if not h.has(args.caller):
        print(f"找不到 caller：{args.caller}（先 vacant init {args.caller}）", file=sys.stderr)
        return 1
    if not h.registry.discover(args.niche):
        print(f"無人宣告能解 niche={args.niche}（先 init 一個 --niche {args.niche} 的 expert）", file=sys.stderr)
        return 1
    # 用一個確定性的可檢查任務（若給 --input 則覆寫題目輸入）
    task = make_task(0, args.niche)
    if args.input is not None:
        from .tasks import NICHE_SOLVERS

        task = dict(task)
        task["input"] = args.input
        task["expected"] = NICHE_SOLVERS[args.niche](args.input)
        task["prompt"] = f"[{args.niche}] {args.input}"
        task["check"] = lambda a, _e=task["expected"]: str(a) == _e
    oc = h.gateway(args.caller).call(args.niche, task, mode=args.mode)
    print(f"caller   : {args.caller}")
    print(f"niche    : {args.niche}  input={task['input']!r}")
    print(f"→ callee : …{oc.callee_id[-12:]}  substrate={oc.substrate}")
    print(f"  answer : {oc.answer!r}")
    print(f"  correct: {'✓' if oc.correct else '✗'}（自動 verifier 用環境真值判定 → 已簽 review 更新信譽）")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from .experiment import run

    # 寫進全新暫存目錄（實驗是拋棄式的）：不污染、也不 rmtree 使用者的 ~/.vacant。
    root = Path(tempfile.mkdtemp(prefix="vacant-demo-")) / "exp"
    print(run(root))
    print(f"\n（實驗資料寫在暫存目錄：{root}）")
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    tmp = Path(tempfile.mkdtemp(prefix="vacant-selftest-"))
    h = Host(tmp)
    req = h.mint("requester", niches=[])
    h.mint("expert", niches=list(NICHES))
    ok = True
    n_correct = 0
    for i in range(6):
        t = make_task(i)
        oc = req.call(t["niche"], t)  # 正確與否會隨機；這裡只測迴圈不爆、鏈可驗
        n_correct += int(oc.correct)
    exp_ok = h.body("expert").logbook.verify_chain(h.body("expert").public_identity())
    req_ok = h.body("requester").logbook.verify_chain(h.body("requester").public_identity())
    print(f"端到端迴圈    : ✓（6 次呼叫無例外，{n_correct}/6 答對）")
    print(f"expert 鏈驗   : {'✓' if exp_ok else '✗'}")
    print(f"requester 鏈驗: {'✓' if req_ok else '✗'}")
    print(f"暫存目錄      : {tmp}")
    return 0 if (exp_ok and req_ok) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vacant", description="Vacant — AI agent 之間的信任層（Phase 1）")
    p.add_argument("--root", default=str(_default_root()), help="vacant 身體根目錄（預設 ~/.vacant）")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="鑄出一個 vacant 身體")
    pi.add_argument("name")
    pi.add_argument("--niche", action="append", help="可重複；宣告能解的 niche")
    pi.add_argument("--controller", default="", help="同源降權用的 controller 標籤")
    pi.set_defaults(func=cmd_init)

    pf = sub.add_parser("info", help="檢視一個 vacant")
    pf.add_argument("name")
    pf.set_defaults(func=cmd_info)

    pc = sub.add_parser("call", help="從 caller 對某 niche 發一次 a2a_call")
    pc.add_argument("caller")
    pc.add_argument("niche", choices=list(NICHES))
    pc.add_argument("--input", default=None, help="任務輸入字串")
    pc.add_argument("--mode", default="reputation", choices=["reputation", "random"])
    pc.set_defaults(func=cmd_call)

    pd = sub.add_parser("demo", help="跑 §11 C0/C1/C2/C3 對照實驗")
    pd.set_defaults(func=cmd_demo)

    ps = sub.add_parser("selftest", help="端到端冒煙測試（暫存目錄）")
    ps.set_defaults(func=cmd_selftest)

    pb = sub.add_parser("bench", help="在你自己的模型上量 plain vs vacant（verify-fix）的效果")
    pb.add_argument("--base", default="http://localhost:1234", help="LM Studio / OpenAI 相容端點（預設 http://localhost:1234）")
    pb.add_argument("--model", required=True, help="模型 id（如 your-model）")
    pb.add_argument("--api", default="responses", choices=["responses", "openai"],
                    help="responses=/api/v1/chat（reasoning 模型）；openai=/v1/chat/completions")
    pb.add_argument("--brain", default="lmstudio", choices=["lmstudio", "openai", "hermes"])
    pb.add_argument("-n", type=int, default=12, help="題數")
    pb.add_argument("-k", type=int, default=3, help="verify-fix 最大嘗試")
    pb.set_defaults(func=cmd_bench)
    return p


def cmd_bench(args: argparse.Namespace) -> int:
    from .agent import Vacant, checkable_cases
    from .brains import HermesBrain, LMStudioBrain, OpenAIBrain
    if args.brain == "hermes":
        brain = HermesBrain(model=args.model, base_url=args.base + "/v1")
    elif args.brain == "openai":
        brain = OpenAIBrain(args.base, args.model)
    else:
        brain = LMStudioBrain(args.base, args.model, api=args.api)
    print(f"brain={brain.name}  n={args.n}  k={args.k}  （在可檢查任務上量 plain vs vacant verify-fix）", flush=True)
    v = Vacant(brain, k=args.k)
    rep = v.bench(checkable_cases(args.n), k=args.k)
    for prompt, pv, vv, calls in rep["rows"]:
        print(f"  {('OK' if vv else 'x'):2} (plain {'OK' if pv else 'x '}) {calls}calls  {prompt}")
    print("\n================ 結果 ================")
    print(f"  plain（無 vacant）   正確率 {rep['plain_acc']*100:3.0f}%   算力 {rep['plain_calls_per']:.1f} 次/題")
    print(f"  vacant（verify-fix） 正確率 {rep['vacant_acc']*100:3.0f}%   算力 {rep['vacant_calls_per']:.1f} 次/題")
    print(f"  → vacant 讓你的模型 {rep['gain']*100:+.0f}%（簽章鏈究責：{v.verify_chain()}）")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
