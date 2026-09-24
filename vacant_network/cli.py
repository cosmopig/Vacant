"""vacant CLI — 產品強制入口、究責生態維運、demo 與自我檢測。

    vacant run "<task>" --test "assert ..." [--agent hermes]
    vacant run -- <任何 agent 命令>                            # V0 launcher，見 docs/VACANT_RUN.md
                                                              # （有裸 `--` 就走這條；vacant_network/vrun/launcher.py）
    vacant init <name> [--niche reverse --niche caesar3] [--root DIR]
    vacant info  <name> [--root DIR]
    vacant call  <caller> <niche> --input <s> [--root DIR]   # 需先 init 出 caller + 一個能解該 niche 的 expert
    vacant demo gate                                          # 30 秒：假 agent 宣告完成 → 閘門拒交 → 收據
                                                              # （零設定／零模型／零網路；vacant_network/vrun/demo.py）
    vacant demo                                               # 跑 §11 對照實驗（原樣保留，預設 kind=eco）
    vacant selftest                                           # 端到端冒煙測試（暫存目錄）

預設 root = ~/.vacant（`trust/` 金鑰與究責紀錄 + HERMES_HOME 都在此；睡著的 vacant 就是這包檔）。

生態子命令（12 §5；MCP 究責閘道的整個居民生態變成可跑 CLI，預設 root=~/.vacant-mcp）：
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
import os
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


# --- 生態子命令（12 §5：把究責閘道的整個生態變成可跑的 CLI）------------------
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
    離線可跑、可驗、可上鏈——用來看究責機制（路由/互審/稽核/信譽），不是看腦力。"""

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
          "（只驗究責機制，非腦力）", file=sys.stderr)
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
        print(f"無法載入 vacant_network.dashboard（{e}）；可先用 `vacant up --no-dashboard`",
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

    def _live(fn_name: str):
        """每次取數前先重載狀態——面板要反映磁碟真相，不是行程啟動時的快照。"""
        def _call(*a: object) -> object:
            eco._load_state()
            return getattr(eco, fn_name)(*a)
        return _call

    server = make_dashboard(
        eco.root, _live_roster, _live_scoreboard, port=args.port,
        providers={
            "identities": _live("identities"),
            "identity_detail": _live("identity_detail"),
            "activity": _live("activity"),
            "integrity": _live("integrity"),
            "counters": _live("counters"),
            "system_info": _live("system_info"),
            "cost": _live("cost"),
            "trust_card": _live("trust_card"),
        },
    )
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
    print(f"    trust/  金鑰與究責紀錄（keypair / logbook / reputation）")
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
    if getattr(args, "kind", "eco") == "gate":
        return _demo_gate(args)
    from .experiment import run

    # 寫進全新暫存目錄（實驗是拋棄式的）：不污染、也不 rmtree 使用者的 ~/.vacant。
    root = Path(tempfile.mkdtemp(prefix="vacant-demo-")) / "exp"
    print(run(root))
    print(f"\n（實驗資料寫在暫存目錄：{root}）")
    return 0


def _demo_gate(args: argparse.Namespace) -> int:
    """`vacant demo gate`：裝完之後的第一幕（`vacant_network/vrun/demo.py`）。

    2026-09-18 之前這條路徑只在 repo checkout 裡有（判斷層住在 `ops/`，
    而 `ops/` 不進 wheel）。現在判斷層住在 `vacant_network/vrun/`，**`pip install
    vacant-network` 就跑得動**——而且與 R530 共用的仍然是同一份
    `acceptance`／`receipts`／`wshash`（`ops/gain/r530/*` 改成 re-export），
    **沒有第二把尺**。
    """
    argv: list[str] = ["--sandbox", args.sandbox]
    if args.root:
        argv += ["--root", args.root]
    if args.demo_json:
        argv.append("--json")
    from .vrun.demo import main as _main
    return _main(argv)


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

    # `demo` 的 `kind` 是**位置引數＋預設值**而不是巢狀子命令：`vacant demo`
    # （生態對照實驗）在外面被引用了好幾年，改成必給子命令會把它打斷。
    pd = sub.add_parser(
        "demo", help="gate＝30 秒看到閘門擋下交付（預設 eco＝§11 C0/C1/C2/C3 對照實驗）")
    pd.add_argument("kind", nargs="?", choices=["eco", "gate"], default="eco",
                    help="gate：零設定零模型零網路，假 agent 走完整條 `vacant run` 路徑")
    pd.add_argument("--root", default=None, help="（gate）落點，每次執行會先清空")
    pd.add_argument("--sandbox", default="auto",
                    help="（gate）驗收沙箱後端：auto／bwrap／unshare／none")
    pd.add_argument("--json", dest="demo_json", action="store_true",
                    help="（gate）只印 JSON summary")
    pd.set_defaults(func=cmd_demo)

    ps = sub.add_parser("selftest", help="端到端冒煙測試（暫存目錄）")
    ps.set_defaults(func=cmd_selftest)

    # 產品主入口：Vacant 自己先 delegate，簽章 gate 過後才啟動外部 agent。
    # ⚠ `vacant run` 有**兩種模式**，分水嶺是 argv 裡有沒有 `--`（見 `main()`）：
    #   有 `--` ⇒ 包住任意 CLI agent 的收件口（`vacant_network/vrun/launcher.py`）
    #   沒有   ⇒ 下面這個舊的 eco 版
    #   ⚠ `--help` 只印得出其中一個（argparse 在看到 `--help` 時就停了），
    #     而它印的是舊的那個 ⇒ **外人照著 help 讀永遠找不到收件口**。
    #     所以把另一條路寫進 description，`vacant run --help` 一定看得到。
    prun = sub.add_parser(
        "run",
        help="包住任意 CLI agent：先驗證交付才放行（用 `--` 分隔）；"
             "不給 `--` 則走舊的 eco 版",
        description=(
            "vacant run 有兩種模式，分水嶺是 argv 裡有沒有 `--`。\n"
            "\n"
            "【一】收件口（V0/V1/V2，**主要用法**）——`--` 之後是整條 agent 命令：\n"
            "\n"
            "    vacant run --workspace ./ws --suite ./acceptance -- pi -p '做這件事'\n"
            "\n"
            "  它把 agent 包起來、中介模型通道、在行程結束那一刻跑驗收、簽收據、\n"
            "  沒過就擋下交付（exit 20）。旗標有 --workspace/--suite/--run-dir/\n"
            "  --retry/--max-attempts/--feedback-into/--sandbox/--json 等。\n"
            "  ⚠ **完整說明要用** `python -m vacant_network.vrun.launcher --help`\n"
            "     （argparse 在這裡看到 --help 就停了，印不出那一組）。\n"
            "  文件：docs/VACANT_RUN.md\n"
            "\n"
            "【二】舊的 eco 版（沒有 `--` 時走這條）——下面列的就是它的旗標。\n"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    prun.add_argument("task", nargs="?", help="任務文字；長任務可改用 --task-file")
    prun.add_argument("--task-file", help="UTF-8 任務檔")
    prun.add_argument("--root", dest="eco_root", default=str(_eco_default_root()),
                      help="產品究責生態目錄（預設 ~/.vacant-mcp）")
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


def _bench_void_report(args: argparse.Namespace, rep: dict, brain_name: str) -> None:
    """一次都沒量到時的診斷（寫 stderr）。訊息品質對齊 `vacant record check`。

    為什麼要這麼囉唆：使用者第一次跑 `vacant bench` 用的是預設 `--base`
    （`http://localhost:1234`），端點沒開是**最可能**的第一次體驗。這一段必須
    當場說出「哪個端點、失敗幾次、錯誤原文是什麼」，否則「沒量到」會被讀成
    「模型很爛」。
    """
    n = rep["n"]
    sys.stdout.flush()   # 讓逐題表與診斷在終端機上仍是這個順序（stdout/stderr 兩條管）
    print("✗ FAIL：一次都沒量到（infra_void，09 §3.5），不輸出任何比較數字",
          file=sys.stderr)
    print(f"  · 端點        : {args.base}   模型 {args.model!r}   brain={brain_name}",
          file=sys.stderr)
    print(f"  · 題數        : {n}", file=sys.stderr)
    print(f"  · plain 臂    : 量到 {rep['plain_measured']}/{n}，沒量到 {rep['plain_void']}/{n}",
          file=sys.stderr)
    print(f"  · vacant 臂   : 量到 {rep['vacant_measured']}/{n}，沒量到 {rep['vacant_void']}/{n}",
          file=sys.stderr)
    print(f"  · 兩臂都量到  : {rep['paired_measured']}/{n}（成對比較的分母）",
          file=sys.stderr)
    print(f"  · 第一個錯誤  : {rep['first_error'] or '（無——題數為 0？）'}",
          file=sys.stderr)
    print("  提示：確認端點起著（LM Studio 預設 http://localhost:1234）、模型 id 正確；"
          "換端點用 --base，換模型用 --model。", file=sys.stderr)
    print("  「沒量到」與「量到 0%」是兩件事：前者是基建故障，後者是資料。"
          "本次全部是前者，所以這裡沒有正確率可以印。", file=sys.stderr)


def cmd_bench(args: argparse.Namespace) -> int:
    """量 plain vs vacant。**一次都沒量到 ⇒ 不印比較數字、exit 非 0**（09 §3.5）。

    這支在架構裡承重的是「對外那一個可以被截圖的數字」。所以它要守的紅線跟
    `vacant record check` 同一條：`infra_void`（這一格沒有量到）不准被折進
    「量到 0」。把端點關著的一次跑渲染成「兩臂各 0%、差 +0%」並 exit 0，
    是用一個沒發生的量測去支撐一個比較——那比不印還糟。
    """
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
    for prompt, pv, vv, calls, p_void, v_void in rep["rows"]:
        # 三種結局要在同一張表上分得開：OK＝答對、x＝答錯、—＝這一格沒量到。
        vm = "—" if v_void else ("OK" if vv else "x")
        pm = "— " if p_void else ("OK" if pv else "x ")
        print(f"  {vm:2} (plain {pm}) {calls}calls  {prompt}")
    if rep["infra_void"]:
        _bench_void_report(args, rep, brain.name)
        return 2
    n = rep["n"]
    print("\n================ 結果 ================")
    print(f"  plain（無 vacant）   正確率 {rep['plain_acc']*100:3.0f}%"
          f"（{rep['plain_measured']}/{n} 量到）   算力 {rep['plain_calls_per']:.1f} 次/題")
    print(f"  vacant（verify-fix） 正確率 {rep['vacant_acc']*100:3.0f}%"
          f"（{rep['vacant_measured']}/{n} 量到）   算力 {rep['vacant_calls_per']:.1f} 次/題")
    print(f"  → vacant 讓你的模型 {rep['gain']*100:+.0f}%"
          f"（成對分母 {rep['paired_measured']}/{n}；簽章鏈究責：{v.verify_chain()}）")
    # infra_void 的格數**單獨印**，而且講明分母是哪一個——折進正確率就等於
    # 把「沒量到」講成「量到 0」。
    if rep["plain_void"] or rep["vacant_void"]:
        print(f"  ⚠ infra_void（沒量到，不進上面任何分子分母）："
              f"plain {rep['plain_void']}/{n}、vacant {rep['vacant_void']}/{n}")
        print(f"     第一個錯誤：{rep['first_error']}")
        print(f"     端點 {args.base}；「沒量到」是基建故障，不是模型答錯。")
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
    n = len(body.logbook)
    print(f"vacant     : {args.name}  (…{body.identity.vacant_id[-12:]})")
    print(f"logbook    : {n} 筆  事件分布 {kinds or '（空）'}")
    if not ok:
        print("簽章鏈究責 : ✗ FAIL（鏈被竄改或不完整）")
        return 1
    if n == 0:
        # ⚠ 空鏈是**恆真**的：沒有東西可以驗，不是「驗過了」。
        #   印成 `✓ PASS（…每筆簽章過）` 會讓外人以為究責發生過——
        #   那是「沒量到」被寫成「量到 0」的同一種混淆（09 §3.5）。
        #   仍然回 0：剛 `init` 出來的身體本來就是空的，那不是錯誤。
        print("簽章鏈究責 : —（空鏈，沒有東西可驗；這不是通過，是沒發生）")
        return 0
    print(f"簽章鏈究責 : ✓ PASS（{n} 筆：seq 連續、prev_hash 串對、每筆簽章過）")
    # ⚠ **驗不到的那一半也要說。** `verify_chain` 沒有長度承諾也沒有外部錨點
    #   ⇒ 從**鏈尾**砍掉幾筆之後它照樣 PASS（截斷／省略攻擊，
    #   Ma & Tsudik 2009，DOI 10.1145/1502777.1502779：完整性 ≠ 完備性）。
    #   抓得到的是**竄改與抽掉中間**，抓不到的是**尾巴被剪短**。
    print("　　　　　　 ⚠ 抓得到竄改與抽掉中間；**抓不到從鏈尾截斷**"
          "（無長度承諾／無外部錨點）")
    return 0


def cmd_verify_att(args: argparse.Namespace) -> int:
    """獨立驗一張 attestation 憑證 —— 不必採信送方，只靠票上的 pub + 簽章。"""
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


def _agent_run_shim(argv: list[str]) -> int:
    """`vacant run -- <任何 agent 命令>`：V0 launcher 的入口。

    **為什麼用 `--` 當分岔而不是新開一個子命令名**：`vacant run "<task>"`
    （controller 那條產品入口）已經佔著 `run` 這個名字，而人類要的介面字面上
    就是 `vacant run -- <cmd>`。兩者用 `--` 分得開——controller 那條從來不需要
    一個裸的 `--`（它的下游 argv 走 `--agent-argv` 的 JSON 陣列）。

    launcher 住在 `vacant_network/vrun/launcher.py`（2026-09-18 從 `ops/vacantrun/`
    搬進套件）。它的判斷層仍然與 R530 實驗共用同一份程式碼——只是方向反過來：
    `ops/gain/r530/{acceptance,receipts,wshash}` 現在 re-export 到
    `vacant_network/vrun/`，所以 `pip install` 的人跑得動，而判準只有一份。
    """
    from .vrun.launcher import main as _main
    return _main(argv)


#: 附身層（`vacant_network/vrun/possess.py`）自己有一套很細的參數
#: （`--agent`／`--upstream`／`--dry-run`／`--service` …），而且它的 usage 行
#: 早就自稱 `vacant install`。**在 argparse 之前攔截**、原封不動轉過去，
#: 比在這裡重寫一份 parser 好：重寫一定會漂。
#:
#: 🔴 為什麼要接：2026-09-22 查到那 2399 行**從 `vacant` 指令根本叫不到**，
#:    使用者得打 `python -m vacant_network.vrun.possess install`。
#:    一個裝得起來卻叫不出來的功能，等於沒有。
#:
#: ⚠ `status` 不在這裡：`vacant status` 已經是 trust 開關的狀態（另一件事）。
#:    附身的狀態走 `vacant possess status`，不搶那個名字。
_POSSESS_TOP: tuple[str, ...] = ("install", "uninstall")


def _possess_shim(raw: list[str]) -> int:
    from .vrun import possess as _possess
    return _possess.main(raw)


def _guided_install(_possess) -> int | None:
    """沒裝過 ⇒ 偵測本機 agent、問一句、跑 `possess.install`。回 `None` ＝已經裝過，往下走。

    ⚠ 引導只涵蓋 `possess.INSTALL_GUIDED_AGENTS`（今天只有 pi：那是唯一走 extension、
      不改寫使用者既有 provider 的一格）。其他 agent 仍走 `vacant install --agent <x>`。
    ⚠ 裝完印的是 `possess.status()`，它的 `wired`／`proven` 兩欄分開——
      **裝好不等於被中介**，唯一算數的是之後 proxyd journal 的 `requests_seen`。
    """
    import pathlib as _pl
    if (_possess.state_home(_pl.Path.home()) / "state.json").is_file():
        return None
    det = _possess.detect(_pl.Path.home(), probe_shell=True)
    cands = [a for a in _possess.INSTALL_GUIDED_AGENTS if det[a].present]
    if not cands:
        sys.stderr.write(
            "Vacant 還沒裝進任何 agent，而且本機沒偵測到可引導的 agent"
            f"（可引導：{', '.join(_possess.INSTALL_GUIDED_AGENTS)}）。\n"
            "  其他 agent：vacant install --agent <codex|opencode|claude|hermes>\n")
        return 2
    print("Vacant 還沒裝進 agent。本機偵測到：")
    for a in cands:
        d = det[a]
        print(f"  {a:<9} {d.binary or '（設定目錄在，PATH 上沒有可執行檔）'}"
              f"  {d.version or ''}")
    print("\n裝進去之後：打開 agent 就預設經過 Vacant，輸入框 /vacant on|off|status；"
          "\n`vacant uninstall` 逐位元還原。**裝好 ≠ 被中介**，之後看 `vacant possess status`。")
    try:
        ans = input(f"把 Vacant 裝進 {', '.join(cands)}？[y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return 130
    if ans not in ("y", "yes"):
        print("沒動任何檔案。要手動裝：vacant install --agent pi")
        return 0
    try:
        r = _possess.install(agents=cands)
    except Exception as e:                                  # noqa: BLE001
        sys.stderr.write(f"🔴 安裝失敗（一個設定檔都沒動，preflight 擋下）：{e}\n")
        return 1
    print(_possess._fmt_status(_possess.status()))
    ws = r.get("warnings") or []
    for w in ws:
        print(w, file=sys.stderr)
    # 🔴 上游是 sink ⇒ 裝好了但每一通都會被擋。**不准以一個乾淨的成功收尾**
    #   （2026-09-24 code review：只裝 pi、沒設 OPENAI_BASE_URL 的人會安靜落到這裡）。
    if any(w.startswith(_possess.SINK_WARNING_HEAD) for w in ws):
        print("\n🔴 裝好了，但**還不能用**：常駐 proxy 沒有真上游，agent 的每一通模型呼叫"
              "都會被擋（fail-closed，不會偷偷直連公開 API）。\n"
              "   修法：vacant uninstall，然後\n"
              "         vacant install --agent " + cands[0] + " --upstream openai=<你的端點>\n"
              "   （或先 export OPENAI_BASE_URL=<你的端點> 再裝；"
              "pi 的話也可以在 ~/.pi/agent/models.json 設一個 provider 的 baseUrl）\n"
              "   在那之前要用原模型：pi 裡打 /vacant off。")
        return 1
    return 0 if not r.get("error") else 1


def _on_shim(raw: list[str]) -> int:
    """`vacant` / `vacant on [agent]` —— 選一個本機有的 CLI agent，在 Vacant 底下開。

    這是「B 路」：**不改使用者任何常駐設定**，只在這一跑之內把 agent 的
    base url 接到中介上。關掉就沒了。與 `vacant install`（改常駐設定、
    裝 proxyd 服務、動 shell rc）是兩件事，證據等級也不同——
    B 這條的中介是量過的（600 格 abpi ＋ pi_tty 兩批），
    A 那條的 pi 通道至今**沒有被 `requests_seen` 證實過**。

    ⚠ 互動模式的三個條件（`DECISION_20260920_PI_TTY_VS_PRINT_MODE.md` 量出來的）
      缺一就**安靜**落回 print：stdin 是 tty、stdout 是 tty、真的有一張 pty。
      這裡把前兩個釘死（`--stdin inherit`、**不給 `--json`**），
      第三個靠使用者本來就在終端機裡。
    """
    import pathlib as _pl
    import shutil as _sh
    from .vrun import agentwrap as _aw
    from .vrun import possess as _possess

    want = raw[0] if raw and not raw[0].startswith("-") else None
    passthru = raw[1:] if want else raw

    # ── 裸 `vacant`、還沒裝過 ⇒ 引導安裝（2026-09-22 人類要的「打開就引導綁定」）──
    #   只在互動終端機問；非 tty **不問也不裝**（安裝會動使用者的檔案與常駐服務，
    #   不可以在腳本裡安靜發生）。裝過了就直接走下面的選單／`vacant on`。
    if not raw and sys.stdin.isatty() and sys.stdout.isatty():
        rc = _guided_install(_possess)
        if rc is not None:
            return rc

    # 偵測：**不要只看 PATH**。「設定目錄在、PATH 上沒有」是實測過的形狀，
    # possess 為此誤判過兩次，所以借它那一套（含 login shell 探測與
    # 終端機跳脫序列剝除）。
    home = _pl.Path.home()
    found: list[tuple[str, str]] = []
    for name in _aw.SUPPORTED:
        spec = _possess.AGENTS.get(name)
        if spec is None:
            continue
        try:
            det = _possess.detect_one(spec, home, probe_shell=True)
        except Exception:                                   # noqa: BLE001
            det = None
        binary = getattr(det, "binary", None) or _sh.which(name)
        if binary:
            found.append((name, str(binary)))

    if not found:
        sys.stderr.write(
            "找不到任何接得動的 CLI agent。\n"
            f"  接得動的：{', '.join(_aw.SUPPORTED)}\n"
            "  ⚠ 「裝了但不在 PATH 上」是常見狀況——先確認 `command -v <agent>`。\n")
        return 2

    if want and want not in dict(found):
        sys.stderr.write(f"{want} 沒有偵測到。本機有的：{', '.join(n for n, _ in found)}\n")
        return 2

    if not want:
        if not sys.stdin.isatty():
            # 🔴 非互動時**不要替人選**。選單的意義就是讓人挑。
            sys.stderr.write(
                "不是互動終端機 ⇒ 不出選單，也不替你挑一個。\n"
                f"  直接指定：vacant on <{'|'.join(n for n, _ in found)}>\n")
            return 2
        print("在 Vacant 底下開哪一個？\n")
        for i, (name, binary) in enumerate(found, 1):
            m = _aw.CHANNEL_MEASURED.get(name)
            # 🔴 把「這條通道驗到什麼程度」講出來。使用者有權知道
            #    自己選的那一條是量過的還是沒量過的。
            tag = f"通道已驗：{m}" if m else "⚠ 通道**沒量過**——跑完請看 requests_seen"
            print(f"  {i}) {name:10s} {binary}")
            print(f"     {tag}")
        print()
        try:
            raw_in = input(f"選 1-{len(found)}（Enter 取消）： ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 130
        if not raw_in:
            return 130
        if not raw_in.isdigit() or not (1 <= int(raw_in) <= len(found)):
            sys.stderr.write("不是有效的選項\n")
            return 2
        want = found[int(raw_in) - 1][0]

    # ⚠ launcher 會 chdir 到 workspace ⇒ 從**原始碼樹**跑的話子行程 import
    #   不到 `vacant_network`（pip 裝好的沒這問題）。把套件的父目錄補進
    #   PYTHONPATH——不補的話失敗訊息是 `No module named 'vacant_network'`，
    #   而外層只會看到 `agent_rc: 1`，看起來像 agent 自己壞掉。
    _pkg_parent = str(_pl.Path(__file__).resolve().parent.parent)
    _pp = os.environ.get("PYTHONPATH", "")
    if _pkg_parent not in _pp.split(os.pathsep):
        os.environ["PYTHONPATH"] = (_pkg_parent + os.pathsep + _pp) if _pp else _pkg_parent

    argv = ["--stdin", "inherit", *passthru, "--",
            sys.executable, "-m", "vacant_network.vrun.agentwrap", want]
    return _agent_run_shim(argv)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw[:1] == ["run"] and "--" in raw[1:]:
        return _agent_run_shim(raw[1:])
    if raw[:1] and raw[0] in _POSSESS_TOP:
        return _possess_shim(raw)
    if raw[:1] == ["possess"]:
        # `vacant possess <install|uninstall|status|detect>` —— 完整轉發。
        return _possess_shim(raw[1:] or ["status"])
    if raw[:1] == ["on"]:
        return _on_shim(raw[1:])
    if not raw:
        # 裸 `vacant` ＝ 選單。這是使用者最可能敲的東西，不該是一頁 usage。
        return _on_shim([])
    args = build_parser().parse_args(raw)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
