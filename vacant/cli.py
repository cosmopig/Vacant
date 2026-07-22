"""vacant CLI — 產品強制入口、信任生態維運、demo 與自我檢測。

    vacant run "<task>" --test "assert ..." [--agent hermes]
    vacant init <name> [--niche reverse --niche caesar3] [--root DIR]
    vacant info  <name> [--root DIR]
    vacant call  <caller> <niche> --input <s> [--root DIR]   # 需先 init 出 caller + 一個能解該 niche 的 expert
    vacant demo  [--root DIR]                                 # 跑 §11 對照實驗
    vacant selftest                                           # 端到端冒煙測試（暫存目錄）

預設 root = ~/.vacant（信任庫 + HERMES_HOME 都在此；睡著的 vacant 就是這包檔）。

生態子命令（12 §5；MCP 信任閘道的整個居民生態變成可跑 CLI，預設 root=~/.vacant-mcp）：
    vacant up [--port 7777] [--no-dashboard]   # 建 6 居民生態 ＋ 前景 dashboard
    vacant toggle on|off                       # 翻 state.json 的 trust 開關
    vacant status                              # trust 開關 ＋ roster 表格
    vacant scoreboard                          # off/on n/pass/成本 ＋ paired_delta
    vacant resident inspect <name>             # 居民條目 ＋ 最近 5 episode
    vacant resident wipe <name>                # 抹記憶不抹 key
    vacant verify <name>                       # 重驗居民 logbook 簽章鏈
    vacant ledger tail [-n 20]                 # 印最後 n 行事件
腦：VACANT_MCP_MODEL/VACANT_MCP_BASE 都設 → LMStudioBrain；否則內建離線確定性假腦。
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


# --- 生態子命令（12 §5：把信任閘道的整個生態變成可跑的 CLI）------------------
# 生態預設 root（與單體 vacant 的 ~/.vacant 分開；MCP 閘道的居民住這）。
def _eco_default_root() -> Path:
    return Path.home() / ".vacant-mcp"


def _build_product_eco(args: argparse.Namespace):
    """產品 run 必須有真模型且只建全良性 roster；絕不退回 demo 假腦/saboteur。"""
    import os

    from .atomic import file_lock
    from .brains import LMStudioBrain
    from .ecosystem import Ecosystem, PRODUCT_ROSTER, assert_product_root

    model = args.model or os.environ.get("VACANT_MCP_MODEL")
    if not model:
        raise ValueError("缺模型：請傳 --model 或設定 VACANT_MCP_MODEL")
    base = args.base or os.environ.get("VACANT_MCP_BASE", "http://localhost:1234")
    api = args.api or os.environ.get("VACANT_MCP_API", "responses")
    if api not in ("responses", "openai"):
        raise ValueError("VACANT_MCP_API 必須是 responses 或 openai")
    if args.model_timeout <= 0:
        raise ValueError("--model-timeout 必須大於 0")
    api_key = os.environ.get("VACANT_MCP_API_KEY") or os.environ.get("VACANT_API_KEY")
    brain = LMStudioBrain(
        base, model, api=api, timeout=args.model_timeout,
        max_tokens=None, api_key=api_key)
    root = Path(args.eco_root)
    with file_lock(root / "controller" / "bootstrap.lock", timeout=30):
        assert_product_root(root)
        return Ecosystem(
            root, brain, roster=PRODUCT_ROSTER,
            k_reviewers=2, audit_rate=1.0, persist_artifacts=False,
            root_mode="product",
        )


def _run_task(args: argparse.Namespace) -> str:
    if args.task and args.task_file:
        raise ValueError("task 與 --task-file 只能擇一")
    if args.task_file:
        return Path(args.task_file).read_text(encoding="utf-8").strip()
    if args.task:
        return args.task.strip()
    raise ValueError("請提供 task 或 --task-file")


def _run_check(args: argparse.Namespace) -> dict:
    import json

    if args.check_file:
        spec = json.loads(Path(args.check_file).read_text(encoding="utf-8"))
    elif args.check_json:
        spec = json.loads(args.check_json)
    elif args.test:
        spec = {"type": "run_python", "code": "\n".join(args.test)}
    elif args.test_file:
        spec = {"type": "run_python", "code": Path(args.test_file).read_text(encoding="utf-8")}
    elif args.expect is not None:
        spec = {"type": "equals", "value": args.expect}
    elif args.contains is not None:
        spec = {"type": "contains", "value": args.contains}
    elif args.regex is not None:
        spec = {"type": "regex", "pattern": args.regex}
    elif args.schema is not None:
        spec = {"type": "json_schema", "schema": json.loads(args.schema)}
    else:  # argparse 的 required group 正常不會走到這裡
        raise ValueError("缺少客觀 check")
    if not isinstance(spec, dict):
        raise ValueError("check 必須是 JSON object")
    return spec


def _run_launch(args: argparse.Namespace):
    import json

    from .controller import ArgvTemplate, hermes_argv

    custom = None
    if args.agent_argv and args.agent_argv_file:
        raise ValueError("--agent-argv 與 --agent-argv-file 只能擇一")
    if args.agent_argv:
        custom = json.loads(args.agent_argv)
    elif args.agent_argv_file:
        custom = json.loads(Path(args.agent_argv_file).read_text(encoding="utf-8"))
    if custom is not None:
        if args.agent != "none":
            raise ValueError("自訂 argv 時不要同時指定 --agent")
        if not isinstance(custom, list) or not all(isinstance(x, str) for x in custom):
            raise ValueError("agent argv 必須是 JSON 字串陣列")
        return ArgvTemplate(tuple(custom))
    if args.agent == "hermes":
        return hermes_argv(args.hermes_bin)
    return None


def cmd_run(args: argparse.Namespace) -> int:
    """產品主入口：controller 直接委派，gate 過後才可啟動 agent。"""
    import json

    from .controller import (
        AgentEvidenceError, AgentRunFailed, GatePolicy, GateRejected, VacantFirstController,
    )
    from .trustcard import render_trust_card

    try:
        task = _run_task(args)
        tests = _run_check(args)
        launch = _run_launch(args)
        eco = _build_product_eco(args)
        controller = VacantFirstController(
            eco,
            policy=GatePolicy(
                max_attempts=args.attempts,
                min_reviews=args.min_reviews,
            ),
        )
        result = controller.delegate_then_run(
            task=task,
            tests=tests,
            risk=args.risk,
            launch=launch,
            cwd=args.cwd,
            timeout=args.agent_timeout,
        )
    except AgentEvidenceError as exc:
        result = exc.result
        print(f"VACANT_AGENT_RAN_EVIDENCE_FAILED：{exc}", file=sys.stderr)
        print("下游 agent 已執行；請先檢查工作區，勿直接重跑。", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return 4
    except AgentRunFailed as exc:
        result = exc.result
        print(f"VACANT_AGENT_FAILED：{exc}", file=sys.stderr)
        print(f"receipt：{result.receipt_path}", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return 3
    except (GateRejected, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"VACANT_GATE_REJECTED：{exc}", file=sys.stderr)
        print("外部 agent 未啟動。", file=sys.stderr)
        return 2

    if args.json_output:
        print(json.dumps({
            "request_id": result.request_id,
            "task_id": result.task_id,
            "answer": result.answer,
            "receipt_path": str(result.receipt_path),
            "context_path": str(result.context_path),
            "agent": {
                "ran": result.agent_argv is not None,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"✓ Vacant-first gate 通過｜task_id={result.task_id}｜"
          f"attempts={result.receipt['attempts']}")
    print(render_trust_card(result.trust_card))
    print(f"receipt：{result.receipt_path}")
    print("\n── agent output ──" if result.agent_argv else "\n── verified delivery ──")
    print(result.stdout.rstrip() if result.agent_argv else result.answer)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return 0


class EchoLikeBrain:
    """離線用的內建確定性假腦（未設模型端點時的 fallback）。

    誠實邊界：這**不是**推理模型，只是把輸入反轉包成 `solve`，讓 delegate 全迴圈
    離線可跑、可驗、可上鏈——用來看信任機制（路由/互審/稽核/信譽），不是看腦力。"""

    name = "echo-like(offline)"

    def generate(self, prompt: str) -> str:  # noqa: D401
        return "```python\ndef solve(s):\n    return s[::-1]\n```"


def _build_brain():
    """VACANT_MCP_MODEL/VACANT_MCP_BASE 兩者都設 → LMStudioBrain；否則離線假腦。"""
    import os

    base = os.environ.get("VACANT_MCP_BASE")
    model = os.environ.get("VACANT_MCP_MODEL")
    if base and model:
        from .brains import LMStudioBrain

        return LMStudioBrain(base, model)
    print("offline brain：未設 VACANT_MCP_MODEL/VACANT_MCP_BASE，改用內建確定性假腦"
          "（只驗信任機制，非腦力）", file=sys.stderr)
    return EchoLikeBrain()


def _build_eco(root: Path, *, demo: bool = False):
    """依磁碟既有 roster 重建；新產品 root 不再默認建立人工 saboteur。"""
    from .ecosystem import DEFAULT_ROSTER, PRODUCT_ROSTER, Ecosystem, ensure_root_mode

    residents = root / "residents"
    has_product = (residents / "resident_1" / "trust" / "vacant_id").exists()
    has_demo = (residents / "good_1" / "trust" / "vacant_id").exists()
    roster = DEFAULT_ROSTER if demo or (has_demo and not has_product) else PRODUCT_ROSTER
    mode = "demo" if roster is DEFAULT_ROSTER else "product"
    ensure_root_mode(root, mode)
    return Ecosystem(root, _build_brain(), roster=roster,
                     k_reviewers=min(3, max(0, len(roster) - 1)), root_mode=mode)


def _print_roster(rows: list) -> None:
    hdr = f"{'name':12} {'tier':9} {'credit':>7} {'n_obs':>6} {'deliv':>5} {'eps':>4} {'chain':>5}  flags"
    print(hdr)
    print("-" * len(hdr))
    for e in rows:
        print(f"{e['name']:12} {e['tier']:9} {e['credit']:>7} {e['n_obs']:>6} "
              f"{e['deliveries']:>5} {e['episodes']:>4} "
              f"{'ok' if e['chain_ok'] else 'BAD':>5}  {','.join(e['flags']) or '-'}")


def cmd_eco_up(args: argparse.Namespace) -> int:
    """建生態＋前景 dashboard；產品 roster 為預設，demo roster 必須顯式要求。"""
    root = Path(args.eco_root)
    if args.demo_roster and (root / "residents" / "resident_1").exists():
        print("demo roster 不可與 product residents 共用 root；請改用 --root ~/.vacant-demo",
              file=sys.stderr)
        return 1
    try:
        eco = _build_eco(root, demo=args.demo_roster)
    except ValueError as exc:
        print(f"無法建立生態：{exc}", file=sys.stderr)
        return 1
    print(f"生態就緒：root={root}  trust={'on' if eco.trust_on else 'off'}  "
          f"居民={len(eco.residents)}")
    if args.no_dashboard:
        print("（--no-dashboard：只建生態、不起 dashboard）")
        return 0
    try:
        from .dashboard import make_dashboard
    except Exception as e:  # dashboard 模組另有工序提供；缺了就講清楚
        print(f"無法載入 vacant.dashboard（{e}）；可先用 `vacant up --no-dashboard`",
              file=sys.stderr)
        return 1
    # dashboard 與 MCP server 是兩個行程、共用同一 root（磁碟即真相）。roster/
    # scoreboard 每次被讀前先從磁碟 reload 信譽/probation 狀態，讓面板即時反映
    # MCP server 每筆 delegate 的寫入（不只事件流即時，居民卡片也即時）。
    def _live_roster() -> list:
        eco._load_state()
        return eco.roster()

    def _live_scoreboard() -> dict:
        return eco.scoreboard()  # 本就每次讀 scoreboard.json，天然即時

    server = make_dashboard(eco.root, _live_roster, _live_scoreboard, port=args.port)
    print(f"dashboard → http://127.0.0.1:{args.port}   (Ctrl-C 退出)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n收到 Ctrl-C，優雅退出。")
        try:
            server.shutdown()
        except Exception:
            pass
    return 0


def cmd_eco_toggle(args: argparse.Namespace) -> int:
    """翻 root/state.json 的 trust_on（不必起整個生態，直接讀寫布林）。"""
    import json

    from .atomic import atomic_write_text, file_lock

    root = Path(args.eco_root)
    with file_lock(root / "controller" / "controller.lock", timeout=30):
        root.mkdir(parents=True, exist_ok=True)
        on = args.state == "on"
        atomic_write_text(root / "state.json", json.dumps({"trust_on": on}))
    print(f"trust → {'on' if on else 'off'}   (root={root})")
    return 0


def cmd_eco_status(args: argparse.Namespace) -> int:
    """trust 開關 ＋ roster 表格。"""
    root = Path(args.eco_root)
    eco = _build_eco(root)
    print(f"root  : {root}")
    print(f"trust : {'on' if eco.trust_on else 'off'}")
    print(f"substrate: {eco.substrate_id}")
    _print_roster(eco.roster())
    return 0


def cmd_eco_scoreboard(args: argparse.Namespace) -> int:
    """off/on 兩桶的 n/pass/成本 ＋ paired_delta。"""
    eco = _build_eco(Path(args.eco_root))
    sb = eco.scoreboard()
    for k in ("off", "on"):
        b = sb[k]
        acc = (b["pass"] / b["n"] * 100) if b["n"] else 0.0
        per = (b["calls"] / b["n"]) if b["n"] else 0.0
        print(f"  trust {k:3}: n={b['n']:4}  pass={b['pass']:4} ({acc:5.1f}%)  "
              f"calls={b['calls']:5} ({per:.2f}/題)")
    pd = sb.get("paired_delta")
    print(f"  paired_delta（on 正確率 − off 正確率）: "
          f"{pd if pd is not None else '—（尚缺配對資料）'}")
    return 0


def cmd_eco_resident_inspect(args: argparse.Namespace) -> int:
    """該居民 roster 條目 ＋ 最近 5 個 episode 摘要。"""
    eco = _build_eco(Path(args.eco_root))
    if args.name not in eco.residents:
        print(f"找不到居民：{args.name}（居民：{', '.join(eco.residents)}）", file=sys.stderr)
        return 1
    entry = next(e for e in eco.roster() if e["name"] == args.name)
    print(f"居民 : {entry['name']}  (…{entry['vacant_id']})  tier={entry['tier']}")
    print(f"信用 : {entry['credit']}  觀測={entry['n_obs']}  交付={entry['deliveries']}  "
          f"episode={entry['episodes']}  鏈={'ok' if entry['chain_ok'] else 'BAD'}")
    print(f"旗標 : {', '.join(entry['flags']) or '（無）'}")
    eps = eco.residents[args.name].stream.episodes()[-5:]
    print(f"最近 {len(eps)} 個 episode：")
    if not eps:
        print("  （無）")
    for ep in eps:
        au = ep.audit or {}
        au_txt = ("audit " + ("✓" if au.get("passed") else "✗")) if au.get("ran") else "no-audit"
        print(f"  · task=…{ep.task_id[-8:]}  outcome={ep.outcome or '-':4}  "
              f"reviews={len(ep.reviews)}  {au_txt}")
    return 0


def cmd_eco_resident_wipe(args: argparse.Namespace) -> int:
    """eco.wipe：抹記憶不抹 key。"""
    from .atomic import file_lock

    root = Path(args.eco_root)
    with file_lock(root / "controller" / "controller.lock", timeout=30):
        eco = _build_eco(root)
        if args.name not in eco.residents:
            print(f"找不到居民：{args.name}（居民：{', '.join(eco.residents)}）", file=sys.stderr)
            return 1
        res = eco.wipe(args.name)
    print(f"已抹記憶（key 保留）：{res['name']}  (…{res['vacant_id']})  "
          f"旗標={', '.join(res['flags']) or '（無）'}")
    return 0


def cmd_eco_verify(args: argparse.Namespace) -> int:
    """重驗該居民 logbook 簽章鏈（PASS/FAIL、entry 數）。"""
    eco = _build_eco(Path(args.eco_root))
    if args.name not in eco.residents:
        print(f"找不到居民：{args.name}（居民：{', '.join(eco.residents)}）", file=sys.stderr)
        return 1
    body = eco.residents[args.name].body
    ok = body.logbook.verify_chain(body.public_identity())
    print(f"居民 : {args.name}  (…{eco.residents[args.name].vacant_id[-12:]})")
    print(f"logbook: {len(body.logbook)} 筆")
    print(f"鏈驗 : {'✓ PASS' if ok else '✗ FAIL'}")
    return 0 if ok else 1


def cmd_eco_ledger_tail(args: argparse.Namespace) -> int:
    """印 ledger 最後 n 行事件。"""
    import json

    eco = _build_eco(Path(args.eco_root))
    p = eco.ledger_path
    if not p.exists():
        print("（ledger 為空）")
        return 0
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    tail = lines[-args.n:] if args.n > 0 else lines
    for ln in tail:
        try:
            rec = json.loads(ln)
        except Exception:
            print(ln)
            continue
        ts = rec.pop("ts_ms", "?")
        et = rec.pop("type", "?")
        rec.pop("trust_on", None)
        rest = "  ".join(f"{k}={v}" for k, v in rec.items())
        print(f"  [{ts}] {et:16} {rest}")
    return 0


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
    p = argparse.ArgumentParser(
        prog="vacant",
        description="Vacant — 先驗證交付，再啟動 AI agent",
    )
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

    # 產品主入口：Vacant 自己先 delegate，簽章 gate 過後才啟動外部 agent。
    prun = sub.add_parser(
        "run",
        help="Vacant-first 強制入口：先驗證交付，再啟動 Hermes／任意 CLI agent",
    )
    prun.add_argument("task", nargs="?", help="任務文字；長任務可改用 --task-file")
    prun.add_argument("--task-file", help="UTF-8 任務檔")
    prun.add_argument("--root", dest="eco_root", default=str(_eco_default_root()),
                      help="產品信任生態目錄（預設 ~/.vacant-mcp）")
    prun.add_argument("--base", default=None,
                      help="模型端點；預設 VACANT_MCP_BASE 或 http://localhost:1234")
    prun.add_argument("--model", default=None,
                      help="模型 id；預設 VACANT_MCP_MODEL（未提供則 fail-closed）")
    prun.add_argument("--api", choices=["responses", "openai"], default=None,
                      help="預設 VACANT_MCP_API 或 responses")
    prun.add_argument("--model-timeout", type=int, default=900,
                      help="單次模型呼叫逾時秒數（預設 900）")
    prun.add_argument("--attempts", type=int, default=3,
                      help="客觀 verify-fix 最大嘗試次數（1-10，預設 3）")
    prun.add_argument("--min-reviews", type=int, default=1,
                      help="啟動 agent 前至少需要的簽章 peer review 數（預設 1）")
    prun.add_argument("--risk", choices=["normal", "high"], default="normal")

    checks = prun.add_mutually_exclusive_group(required=True)
    checks.add_argument("--check-file", help="完整 check-spec JSON 檔")
    checks.add_argument("--check-json", help="行內完整 check-spec JSON")
    checks.add_argument("--test", action="append",
                        help="Python assert；可重複，會組成 run_python check")
    checks.add_argument("--test-file", help="Python assert 測試檔")
    checks.add_argument("--expect", help="答案必須精確等於此值")
    checks.add_argument("--contains", help="答案必須包含此字串")
    checks.add_argument("--regex", help="答案必須符合此正則")
    checks.add_argument("--schema", help="答案必須符合此 JSON Schema（行內 JSON）")

    prun.add_argument("--agent", choices=["none", "hermes"], default="none",
                      help="gate 後啟動的內建 adapter（預設只回 Vacant 交付）")
    prun.add_argument("--hermes-bin", default="hermes",
                      help="Hermes 執行檔（預設 hermes）")
    prun.add_argument("--agent-argv",
                      help="自訂 shell-free argv JSON 陣列；須含 {answer} 或 {context_path}")
    prun.add_argument("--agent-argv-file", help="自訂 argv JSON 陣列檔")
    prun.add_argument("--agent-timeout", type=float, default=900,
                      help="下游 agent 逾時秒數（預設 900）")
    prun.add_argument("--cwd", default=None, help="下游 agent 工作目錄（預設目前目錄）")
    prun.add_argument("--json", dest="json_output", action="store_true",
                      help="輸出機器可讀 JSON")
    prun.set_defaults(func=cmd_run)

    pb = sub.add_parser("bench", help="在你自己的模型上量 plain vs vacant（verify-fix）的效果")
    pb.add_argument("--base", default="http://localhost:1234", help="LM Studio / OpenAI 相容端點（預設 http://localhost:1234）")
    pb.add_argument("--model", required=True, help="模型 id（如 your-model）")
    pb.add_argument("--api", default="responses", choices=["responses", "openai"],
                    help="responses=/api/v1/chat（reasoning 模型）；openai=/v1/chat/completions")
    pb.add_argument("--brain", default="lmstudio", choices=["lmstudio", "openai", "hermes"])
    pb.add_argument("--suite", default="niche", choices=["niche", "code"],
                    help="niche=內建玩具可檢查任務；code=真實 code generation（跑測試當 verifier）")
    pb.add_argument("--max-tokens", type=int, default=0, help="0=依 suite 自動（niche 256 / code 1024）")
    pb.add_argument("-n", type=int, default=12, help="題數")
    pb.add_argument("-k", type=int, default=3, help="verify-fix 最大嘗試")
    pb.set_defaults(func=cmd_bench)

    pa = sub.add_parser("audit", help="重驗一個 vacant 的 logbook 簽章鏈（對外究責）")
    pa.add_argument("name")
    pa.set_defaults(func=cmd_audit)

    pv = sub.add_parser("verify-att", help="獨立驗一張 attestation 通過憑證（JSON 檔）")
    pv.add_argument("file")
    pv.add_argument("--answer", default=None, help="把實際答案餵進來，額外要求雜湊對得上")
    pv.set_defaults(func=cmd_verify_att)

    pt = sub.add_parser("trace", help="把 MCP tee-proxy 的 wire log 渲染成可讀的 Hermes↔vacant 時間軸")
    pt.add_argument("file")
    pt.set_defaults(func=cmd_trace)

    # record：一次 run 的最小證據包（17 §P0-2；docs/RECORD_SPEC.md）
    prec = sub.add_parser("record", help="run 證據包：pack（打包）／check（核對）")
    recsub = prec.add_subparsers(dest="record_cmd", required=True)
    prp = recsub.add_parser("pack", help="就地整理成 RECORD_SPEC 佈局＋SHA256SUMS")
    prp.add_argument("dir")
    prp.set_defaults(func=cmd_record_pack)
    prc = recsub.add_parser("check", help="對照 RECORD_SPEC 核對（失敗 exit 非 0）")
    prc.add_argument("dir")
    prc.set_defaults(func=cmd_record_check)

    # --- 生態子命令（12 §5）：每個都有自己的 --root（dest=eco_root，預設 ~/.vacant-mcp）
    eco_default = str(_eco_default_root())

    def _add_eco_root(pp: argparse.ArgumentParser) -> None:
        pp.add_argument("--root", dest="eco_root", default=eco_default,
                        help="生態根目錄（預設 ~/.vacant-mcp）")

    pup = sub.add_parser("up", help="建產品生態＋前景 dashboard")
    _add_eco_root(pup)
    pup.add_argument("--port", type=int, default=7777, help="dashboard 埠（預設 7777）")
    pup.add_argument("--no-dashboard", action="store_true", help="只建生態、不起 dashboard")
    pup.add_argument("--demo-roster", action="store_true",
                     help="研究展示才用：建立含人工 saboteur 的 6-resident roster")
    pup.set_defaults(func=cmd_eco_up)

    ptg = sub.add_parser("toggle", help="翻 root/state.json 的 trust 開關")
    _add_eco_root(ptg)
    ptg.add_argument("state", choices=["on", "off"])
    ptg.set_defaults(func=cmd_eco_toggle)

    pst = sub.add_parser("status", help="trust 開關 ＋ roster 表格")
    _add_eco_root(pst)
    pst.set_defaults(func=cmd_eco_status)

    psc = sub.add_parser("scoreboard", help="off/on 的 n/pass/成本 ＋ paired_delta")
    _add_eco_root(psc)
    psc.set_defaults(func=cmd_eco_scoreboard)

    pres = sub.add_parser("resident", help="居民操作（inspect / wipe）")
    rsub = pres.add_subparsers(dest="resident_cmd", required=True)
    pri = rsub.add_parser("inspect", help="roster 條目 ＋ 最近 5 episode")
    _add_eco_root(pri)
    pri.add_argument("name")
    pri.set_defaults(func=cmd_eco_resident_inspect)
    prw = rsub.add_parser("wipe", help="抹記憶不抹 key")
    _add_eco_root(prw)
    prw.add_argument("name")
    prw.set_defaults(func=cmd_eco_resident_wipe)

    pver = sub.add_parser("verify", help="重驗某居民的 logbook 簽章鏈")
    _add_eco_root(pver)
    pver.add_argument("name")
    pver.set_defaults(func=cmd_eco_verify)

    pled = sub.add_parser("ledger", help="ledger 操作（tail）")
    lsub = pled.add_subparsers(dest="ledger_cmd", required=True)
    plt = lsub.add_parser("tail", help="印最後 n 行事件")
    _add_eco_root(plt)
    plt.add_argument("-n", type=int, default=20, help="行數（預設 20）")
    plt.set_defaults(func=cmd_eco_ledger_tail)
    return p


def cmd_record_pack(args: argparse.Namespace) -> int:
    """就地把 run 目錄整理成 RECORD_SPEC 佈局（manifest＋驗證輸出＋SHA256SUMS）。"""
    from .record import pack

    manifest = pack(Path(args.dir))
    print(f"已打包證據包：{args.dir}")
    print(f"  repo_commit : {manifest['repo_commit']}")
    print(f"  python/os   : {manifest['python']} / {manifest['os']}")
    print(f"  pip_freeze  : {len(manifest['pip_freeze'])} 筆")
    miss = manifest.get("missing", {})
    print(f"  missing     : {', '.join(sorted(miss)) if miss else '（無缺項）'}")
    print("（誠實邊界：pack 只保證包完整自洽，內容真實性由簽章鏈與稽核承擔）")
    return 0


def cmd_record_check(args: argparse.Namespace) -> int:
    """對照 RECORD_SPEC 核對 run 目錄；有問題逐條印出、exit code 非 0。"""
    from .record import check

    ok, problems = check(Path(args.dir))
    if ok:
        print(f"✓ PASS：{args.dir} 符合 RECORD_SPEC（必要項齊、雜湊自洽、驗證輸出無 FAIL）")
        return 0
    print(f"✗ FAIL：{args.dir} 未過 RECORD_SPEC（記錄層 infra_void，不得進統計）",
          file=sys.stderr)
    for p in problems:
        print(f"  · {p}", file=sys.stderr)
    return 1


def cmd_bench(args: argparse.Namespace) -> int:
    from .agent import Vacant, checkable_cases
    from .brains import HermesBrain, LMStudioBrain, OpenAIBrain
    from .codebench import code_cases, code_system_prompt

    is_code = args.suite == "code"
    max_tokens = args.max_tokens or (1024 if is_code else 256)
    system = code_system_prompt() if is_code else "Output only the answer, nothing else."
    if args.brain == "hermes":
        brain = HermesBrain(model=args.model, base_url=args.base + "/v1")
    elif args.brain == "openai":
        brain = OpenAIBrain(args.base, args.model, max_tokens=max_tokens, system=system)
    else:
        brain = LMStudioBrain(args.base, args.model, api=args.api, max_tokens=max_tokens, system=system)
    cases = code_cases(args.n) if is_code else checkable_cases(args.n)
    print(f"brain={brain.name}  suite={args.suite}  n={args.n}  k={args.k}  （量 plain vs vacant verify-fix）", flush=True)
    v = Vacant(brain, k=args.k)
    rep = v.bench(cases, k=args.k)
    for prompt, pv, vv, calls in rep["rows"]:
        print(f"  {('OK' if vv else 'x'):2} (plain {'OK' if pv else 'x '}) {calls}calls  {prompt}")
    print("\n================ 結果 ================")
    print(f"  plain（無 vacant）   正確率 {rep['plain_acc']*100:3.0f}%   算力 {rep['plain_calls_per']:.1f} 次/題")
    print(f"  vacant（verify-fix） 正確率 {rep['vacant_acc']*100:3.0f}%   算力 {rep['vacant_calls_per']:.1f} 次/題")
    print(f"  → vacant 讓你的模型 {rep['gain']*100:+.0f}%（簽章鏈究責：{v.verify_chain()}）")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """重驗一個 vacant 的 logbook 簽章鏈 —— 把『可究責』變成對外可跑的命令。"""
    root = Path(args.root)
    try:
        body = VacantBody.load(args.name, root)
    except FileNotFoundError:
        print(f"找不到：{args.name}（root={root}）", file=sys.stderr)
        return 1
    ok = body.logbook.verify_chain(body.public_identity())
    kinds: dict[str, int] = {}
    for e in body.logbook.entries:
        kinds[e.type] = kinds.get(e.type, 0) + 1
    print(f"vacant     : {args.name}  (…{body.identity.vacant_id[-12:]})")
    print(f"logbook    : {len(body.logbook)} 筆  事件分布 {kinds or '（空）'}")
    print(f"簽章鏈究責 : {'✓ PASS（seq 連續、prev_hash 串對、每筆簽章過）' if ok else '✗ FAIL（鏈被竄改或不完整）'}")
    return 0 if ok else 1


def cmd_verify_att(args: argparse.Namespace) -> int:
    """獨立驗一張 attestation 憑證 —— 不必信任送方，只靠票上的 pub + 簽章。"""
    import json

    from .attest import verify_attestation

    att = json.loads(Path(args.file).read_text(encoding="utf-8"))
    ok = verify_attestation(att, answer=args.answer)
    print(f"attestation: …{str(att.get('vacant_id',''))[-12:]}  check={att.get('check')!r}  "
          f"verified={att.get('verified')}")
    if args.answer is not None:
        print(f"答案雜湊比對: {'（已要求）' if ok else '不符或驗章失敗'}")
    print(f"獨立驗章   : {'✓ VALID（vacant_id 由 pub 重算、簽章覆蓋整票）' if ok else '✗ INVALID'}")
    return 0 if ok else 1


_VACANT_TOOLS = (
    "delegate", "trust_card", "receipt", "residents", "report", "scoreboard", "verify_fix",
)


def _short(v, n: int = 140) -> str:
    import json as _j

    s = v if isinstance(v, str) else _j.dumps(v, ensure_ascii=False)
    s = s.replace("\n", "\\n")
    return s if len(s) <= n else s[:n] + "…"


def _tool_text(result) -> str:
    """從 MCP tools/call 結果取出文字內容（content[0].text）。"""
    import json as _j

    if isinstance(result, dict):
        c = result.get("content")
        if isinstance(c, list) and c and isinstance(c[0], dict):
            return c[0].get("text", "")
        return _j.dumps(result, ensure_ascii=False)
    return result if isinstance(result, str) else _j.dumps(result, ensure_ascii=False)


def cmd_trace(args: argparse.Namespace) -> int:
    """把 tee-proxy 側錄的 MCP JSON-RPC 渲染成「Hermes ↔ vacant」可讀時間軸。"""
    import json

    path = Path(args.file)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print(f"找不到 trace 檔：{path}", file=sys.stderr)
        return 1
    print(f"== MCP trace: {path} ==  (★=對 vacant 工具的呼叫/回覆)")
    pending: dict = {}      # JSON-RPC id → 工具名（標記回覆）
    n_calls = 0
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        t = rec.get("t", "--:--:--")
        # A 層：verify_fix 自記的迴圈追蹤
        if rec.get("tool") == "verify_fix":
            steps = rec.get("attempts", []) or []
            seq = " ".join(f"#{s.get('attempt')}{'✓' if s.get('passed') else '✗'}" for s in steps)
            seq = seq or ("draft✓" if rec.get("draft_used") else "—")
            print(f"  [{t}] (vacant 內) verify_fix check={rec.get('check')} 迴圈:[{seq}]"
                  f" → verified={rec.get('verified')} calls={rec.get('calls')}")
            continue
        d, msg = rec.get("dir"), rec.get("msg")
        if d == "proxy":
            print(f"  [{t}] · proxy {rec.get('raw', '')}")
            continue
        if not isinstance(msg, dict):
            continue
        method, mid = msg.get("method"), msg.get("id")
        if method:
            if method == "tools/call":
                params = msg.get("params", {}) or {}
                name = params.get("name", "")
                is_vac = any(v in name for v in _VACANT_TOOLS)
                n_calls += int(is_vac)
                arg_s = ", ".join(f"{k}={_short(v, 80)}" for k, v in (params.get("arguments", {}) or {}).items())
                print(f"{'★' if is_vac else ' '} [{t}] → Hermes 呼叫 {name}({arg_s})")
                if mid is not None:
                    pending[mid] = name
            elif method == "initialize":
                print(f"  [{t}] · MCP 握手 initialize")
            elif method == "tools/list":
                print(f"  [{t}] · Hermes 列工具 tools/list")
        elif mid is not None and ("result" in msg or "error" in msg):
            name = pending.pop(mid, None)
            if "error" in msg:
                print(f"  [{t}] ← error (id={mid}): {_short(msg.get('error'))}")
            elif name and any(v in name for v in _VACANT_TOOLS):
                print(f"★ [{t}] ← vacant 回覆 [{name}]: {_short(_tool_text(msg.get('result')), 320)}")
    print(f"\n結論：此 trace 中 Hermes 對 vacant 工具的呼叫 = {n_calls} 次"
          f"{'（✓ Hermes 確實用到 vacant）' if n_calls else '（未偵測到 vacant 呼叫）'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
