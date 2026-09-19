"""這支在架構裡承重什麼：**閘門層那一層「行程結束時接手」的東西**。

`vacant install` 在 `~/.vacant/possess/bin/` 放五支同名的小 shell 腳本，並且
把那個目錄加到 `PATH` 前面。使用者打 `pi -p "做這件事"` 時先打到 shim，
shim `exec` 進本模組，本模組才去找真正的 `pi` 並且把它包進 `launcher.run()`。

⚠ **打完整路徑（`/usr/local/bin/pi`）就跳過這一層。** 通道層仍然成立
（那是寫在 agent 自己的設定檔裡的），但**閘門不會跑、不會有裁決收據**。
本檔任何一處都不准把這一層寫成「不會被繞過」。

## 本模組的兩個階段（同一支檔，靠 `--exec` 分）

  · **外層**（shim 呼叫）：找真 binary → 決定要不要 gate → 找驗收套件 →
    `launcher.run()` → **把退出碼映射成裁決** → 落一份 `possess.json`。
  · **內層**（`--exec`，被 `launcher` 當成 agent 命令 spawn）：這時候
    `$VACANT_RUN_PROXY` 已經有值了，所以在這裡才寫得出 per-run 的
    relocate 設定（`CODEX_HOME`／`PI_CODING_AGENT_DIR`／`HERMES_HOME`／
    `OPENCODE_CONFIG_CONTENT`／`CLAUDE_CONFIG_DIR`），然後 `exec` 真 binary，
    **argv 逐位元照抄使用者打的那一串**。

  內層用 relocate 而不是靠使用者那份常駐設定，有一個**設計上的理由**：
  經過閘門的那一跑要指向**這一跑自己的 ephemeral proxy**（收據的 wire log
  才對得起來），不是常駐的那個共用端點。兩者的優先順序由 relocate 變數
  決定——relocate 把整份設定搬走，常駐那一份在那一跑裡根本不會被讀到。

## 退出碼（⚠ 這是本模組最重要的規格）

| 碼 | 意思 |
|---|---|
| `0` | **驗收真的跑了而且過了** |
| `20` | 驗收跑了沒過 ⇒ 拒交（`launcher.EXIT_REFUSED`） |
| `21` | **沒有驗收可跑**：只中介、沒閘門（`stop_reason="ungated"`） |
| `22` | `infra_void`（`launcher.EXIT_VOID`） |
| `23` | **`requests_seen == 0`**：這一跑沒有任何模型呼叫經過 proxy |
| 其他 | passthrough 模式：原樣透傳真 binary 的退出碼 |

`21` 是 2026-09-19 人類點名要的那一格：**「只中介不跑閘門」不可以長得像
「跑了驗收而且過了」**。`launcher.exit_code()` 現在把 `ungated` 判成 0
（因為 `refused` 是 False），本模組**不改 launcher**（那會動到已歸檔資料的
可比性），而是在 shim 這一層把它分出來。

`23` 是同一條紀律的另一面。2026-09-19 的負控制量到：
`rs=0`／`wire={}`／`agent_rc=0`／`stop_reason=visible_fail`／exit 20／
`chain_ok=true` —— **除了 `requests_seen`，每個欄位都跟一個合法的拒交格
一模一樣**。所以「沒量到中介」必須有自己的碼，不可以混進 20。

⚠ `23` 蓋過 `0`／`20`／`21`（`22` 除外）。理由：沒有中介的證據時，
那一格的裁決**不可歸因**——不是「拒交」也不是「通過」。
`VACANT_POSSESS_RS0=warn` 可以降級成只印警告（預設是 `fail`）。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import uuid

from . import launcher, possess

EXIT_UNGATED = 21
EXIT_NO_MEDIATION = 23

#: 自動找驗收套件的規則，**由近而遠，第一個命中就停**。
#: 每一條都要能在收據上被指名（`suite_source`）。
SUITE_DIRNAMES = (".vacant/suite", "tests_visible")
SUITE_TOML = (".vacant.toml",)


def resolve_suite(cwd: pathlib.Path) -> tuple[pathlib.Path | None, str]:
    """回 `(套件目錄, 是哪一條規則命中的)`。找不到回 `(None, "none")`。

    ⚠ **回 `None` 不是錯誤**，是「這一跑沒有閘門」——呼叫端要把它落成
      `ungated`／exit 21，**不准讓它長得像通過**。
    """
    env = os.environ.get("VACANT_SUITE")
    if env:
        p = pathlib.Path(env).expanduser()
        if p.is_dir():
            return p, "env:VACANT_SUITE"
    here = cwd.resolve()
    for d in [here, *here.parents]:
        for name in SUITE_DIRNAMES:
            cand = d / name
            if cand.is_dir() and any(cand.glob("test_*.py")):
                return cand, f"dir:{name}"
        for tname in SUITE_TOML:
            t = d / tname
            if t.is_file():
                try:
                    import tomllib
                    doc = tomllib.loads(t.read_text("utf-8"))
                except Exception:
                    continue
                s = (doc.get("suite")
                     or (doc.get("tool") or {}).get("vacant", {}).get("suite"))
                if s:
                    cand = (d / str(s)).resolve()
                    if cand.is_dir():
                        return cand, f"toml:{tname}"
        if (d / ".git").exists():
            break                       # 走到專案根就停，不要爬到 $HOME
    return None, "none"


def _inject_upstreams_from_state() -> dict[str, str]:
    """把 `vacant install` 當時記下來的上游補進環境變數，給 `launcher` 用。

    **只在那個變數還沒有值的時候補**——使用者明講的永遠優先。
    """
    out: dict[str, str] = {}
    sp = possess.state_home() / "state.json"
    if not sp.is_file():
        return out
    try:
        st = json.loads(sp.read_text("utf-8"))
    except (OSError, ValueError):
        return out
    for wire, var in (("openai", "VACANT_RUN_UPSTREAM_OPENAI"),
                      ("anthropic", "VACANT_RUN_UPSTREAM_ANTHROPIC")):
        url = ((st.get("upstreams") or {}).get(wire) or {}).get("url")
        if url and not os.environ.get(var):
            os.environ[var] = url
            out[wire] = url
    return out


def real_binary(agent: str, shim_dir: str | None) -> str | None:
    """找真正的可執行檔——**把 shim 目錄從 PATH 拿掉再找**，否則自己找到自己。

    `VACANT_POSSESS_REAL_BIN` 明講的優先（agent 不在 PATH 上時用得到，
    也是負控制把 `/bin/true` 放進 agent 位置的那個鉤子）。
    """
    explicit = os.environ.get("VACANT_POSSESS_REAL_BIN")
    if explicit and os.path.isfile(explicit) and os.access(explicit, os.X_OK):
        return explicit
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep)
             if p and (not shim_dir or os.path.abspath(p) !=
                       os.path.abspath(shim_dir))]
    found = shutil.which(agent, path=os.pathsep.join(parts))
    if found:
        return found
    spec = possess.AGENTS.get(agent)
    if spec:
        home = pathlib.Path.home()
        for hint in spec.bin_hints:
            p = pathlib.Path(hint) if hint.startswith("/") else home / hint
            if p.is_file() and os.access(p, os.X_OK):
                return str(p)
    return None


def is_passthrough(agent: str, argv: list[str]) -> bool:
    """這一次呼叫該不該被閘門包起來。

    `codex --version`／`claude mcp list`／`opencode auth` 這種**不是在交付工作**
    的呼叫要原樣放過去——包起來只會壞掉使用者的日常操作，然後 Vacant 被解除
    安裝。**這是一條已知的繞過路**（打 `--help` 當然不會被 gate），
    寫在這裡是為了它是明示的、數得出來的，而不是一個意外。
    """
    spec = possess.AGENTS.get(agent)
    if spec is None:
        return True
    if not argv:
        return True                     # 沒參數＝多半是互動 TUI，見下
    for a in argv:
        if a in spec.passthrough:
            return True
    if argv and not argv[0].startswith("-") and argv[0] in spec.passthrough:
        return True
    # 互動 TUI（stdin 是終端機）預設不 gate：把一個互動 session 凍結起來跑
    # 驗收會毀掉使用者的工作流。`VACANT_POSSESS_GATE_TTY=1` 可以打開。
    if sys.stdin.isatty() and os.environ.get(
            "VACANT_POSSESS_GATE_TTY", "") not in ("1", "true", "yes"):
        return True
    return False


# ── 內層：被 launcher spawn 的那一段 ───────────────────────────────────

def exec_inner(agent: str, argv: list[str]) -> int:
    """`$VACANT_RUN_PROXY` 已經有值了 ⇒ 現寫一份 per-run 設定，然後 exec 真 binary。

    ⚠ 這裡是 `ops/vacantrun/wrap_agent.sh` 那五段接線的 Python 版，**判準一樣**
      （`envmap.CONFIG_ROUTE`）。差別只有一個：wrap_agent.sh 自己組 argv，
      本函式**照抄使用者打的那一串**——「裝一次就在」的前提是使用者的命令
      一個字都不用改。
    """
    base = (os.environ.get("VACANT_RUN_PROXY") or "").rstrip("/")
    if not base:
        print("[gateshim] 沒有 $VACANT_RUN_PROXY，這一段要跑在 launcher 底下。停。",
              file=sys.stderr)
        return 2
    real = os.environ.get("VACANT_POSSESS_REAL_BIN") or real_binary(
        agent, os.environ.get("VACANT_POSSESS_SHIM_DIR"))
    if not real:
        print(f"[gateshim] 找不到真正的 {agent}。停。", file=sys.stderr)
        return 127
    cfg = pathlib.Path(os.environ.get("VACANT_POSSESS_CFG") or
                       (pathlib.Path(os.environ.get("TMPDIR", "/tmp")) /
                        f"vacant-possess-{uuid.uuid4().hex[:8]}"))
    cfg.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    model = env.get("VACANT_AGENT_MODEL", "")

    if agent == "codex":
        env["CODEX_HOME"] = str(cfg)
        lines = ['model_provider = "vacant"', 'approval_policy = "never"',
                 'sandbox_mode = "danger-full-access"', "",
                 "[model_providers.vacant]", 'name = "vacant possess"',
                 f'base_url = "{base}/v1"', 'wire_api = "responses"',
                 'env_key = "OPENAI_API_KEY"']
        if model:
            lines.insert(0, f'model = "{model}"')
        (cfg / "config.toml").write_text("\n".join(lines) + "\n", "utf-8")
    elif agent == "pi":
        env["PI_CODING_AGENT_DIR"] = str(cfg)
        env.setdefault("PI_OFFLINE", "1")
        env.setdefault("PI_SKIP_VERSION_CHECK", "1")
        (cfg / "models.json").write_text(json.dumps({"providers": {"vacant": {
            "baseUrl": f"{base}/v1", "api": "openai-completions",
            "apiKey": env.get("OPENAI_API_KEY", "sk-vacant-possess"),
            "compat": {"supportsDeveloperRole": False,
                       "supportsReasoningEffort": False},
            "models": [{"id": model or "gemma-4-12b-it-qat", "name": "m",
                        "contextWindow": 262144, "maxTokens": 16384}]}}},
            ensure_ascii=False), "utf-8")
    elif agent == "opencode":
        env["OPENCODE_CONFIG_DIR"] = str(cfg)
        env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps({
            "provider": {"vacant": {
                "name": "vacant possess", "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": f"{base}/v1",
                            "apiKey": env.get("OPENAI_API_KEY",
                                              "sk-vacant-possess")},
                "models": {(model or "gemma-4-12b-it-qat"): {"name": "m"}}}},
            "permission": {"edit": "allow", "bash": "allow",
                           "webfetch": "allow"}}, ensure_ascii=False)
    elif agent == "hermes":
        env["HERMES_HOME"] = str(cfg)
        ctx = env.get("VACANT_HERMES_CONTEXT", "65536")
        (cfg / "config.yaml").write_text(
            "model:\n  provider: custom\n"
            f"  default: {model or 'gemma-4-12b-it-qat'}\n"
            f"  base_url: {base}/v1\n  context_length: {ctx}\n", "utf-8")
    elif agent == "claude":
        env["CLAUDE_CONFIG_DIR"] = str(cfg)
        for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID",
                  "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
                  "CLAUDE_CODE_EXECPATH", "CLAUDE_PID", "AI_AGENT",
                  "CLAUDE_CODE_USE_OPENAI"):
            env.pop(k, None)
        env["DISABLE_TELEMETRY"] = "1"
        env["DISABLE_AUTOUPDATER"] = "1"
        if model:
            env["ANTHROPIC_MODEL"] = model
    try:
        os.execve(real, [real, *argv], env)
    except OSError as e:                        # pragma: no cover
        print(f"[gateshim] exec {real} 失敗：{e}", file=sys.stderr)
        return 126
    return 126                                  # pragma: no cover


# ── 外層：shim 呼叫的那一段 ────────────────────────────────────────────

def run_gate(agent: str, argv: list[str]) -> int:
    shim_dir = os.environ.get("VACANT_POSSESS_SHIM_DIR")
    real = real_binary(agent, shim_dir)
    if real is None:
        print(f"[vacant] 找不到真正的 {agent}（shim 目錄已從 PATH 排除）。",
              file=sys.stderr)
        return 127
    if os.environ.get("VACANT_POSSESS_BYPASS") in ("1", "true", "yes") or \
            is_passthrough(agent, argv):
        # ⚠ **明示的繞過路**：透傳，不 gate。通道層仍然是使用者自己那份
        #   常駐設定（也就是常駐 proxy），所以模型呼叫照樣被中介。
        return subprocess.run([real, *argv]).returncode

    cwd = pathlib.Path.cwd()
    suite, suite_source = resolve_suite(cwd)
    task_id = f"possess_{agent}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    run_dir = pathlib.Path.home() / ".vacant-run" / task_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # `--suite` 不可以在工作區底下（launcher 的擋門：agent 改得到的驗收不是
    # 驗收）。自動找到的那一份多半就在專案裡 ⇒ **複製一份到工作區外**，
    # 權威的是複製出來的這一份。
    suite_arg = None
    if suite is not None:
        suite_arg = run_dir / "suite"
        shutil.copytree(suite, suite_arg, dirs_exist_ok=True)

    # ⚠ **閘門那一跑用的是它自己的 ephemeral proxy，不是常駐那一支**
    #   （收據的 wire log 才對得起來）。但 `launcher` 是從環境變數推上游的，
    #   而使用者的 shell 裡通常什麼都沒有 ⇒ 會落到 `SINK_UPSTREAM`、
    #   每一通都被擋在本機。**上游要從 install 當時記下來的 state 補進去。**
    #   沒有 state（沒裝過、直接跑 gateshim）就維持原樣＝fail-closed。
    _inject_upstreams_from_state()

    inner = [sys.executable, "-m", "vacant_network.vrun.gateshim", "--exec",
             agent, *argv]
    os.environ["VACANT_POSSESS_REAL_BIN"] = real
    summary = launcher.run(
        inner, workspace=cwd, run_dir=run_dir, suite_dir=suite_arg,
        vacant_on=True, task_id=task_id, sandbox_name="none",
        allow_no_suite=(suite_arg is None),
        test_timeout_s=float(os.environ.get("VACANT_TEST_TIMEOUT", "30")),
        inherit_stdin=sys.stdin.isatty(),
    )
    rs = int(summary.get("requests_seen") or 0)
    possess.mark_proven(agent, rs)
    verdict = launcher.exit_code(summary)
    if summary.get("stop_reason") == "ungated":
        verdict = EXIT_UNGATED
    rs0_mode = os.environ.get("VACANT_POSSESS_RS0", "fail")
    if rs == 0 and verdict != launcher.EXIT_VOID:
        print("[vacant] ⚠ requests_seen = 0：這一跑**沒有任何模型呼叫經過 "
              "proxy**。那一格在收據上跟一個合法的拒交格只差這一個欄位，"
              "所以裁決不可歸因。", file=sys.stderr)
        if rs0_mode not in ("warn", "0", "off"):
            verdict = EXIT_NO_MEDIATION

    extra = {
        "possess_agent": agent, "suite_source": suite_source,
        "suite_dir": str(suite) if suite else None,
        "gate": "ran" if suite_arg is not None else "skipped",
        "requests_seen": rs, "stop_reason": summary.get("stop_reason"),
        "accepted": summary.get("accepted"), "shim_exit": verdict,
        "argv": argv, "real_binary": real, "cwd": str(cwd),
    }
    (run_dir / "possess.json").write_text(
        json.dumps(extra, ensure_ascii=False, indent=2), encoding="utf-8")
    mark = {0: "交付", 20: "拒交", EXIT_UNGATED: "**沒有閘門（只中介）**",
            launcher.EXIT_VOID: "infra_void",
            EXIT_NO_MEDIATION: "**沒量到中介**"}.get(verdict, str(verdict))
    print(f"[vacant] {agent}　{mark}　驗收來源 {suite_source}　"
          f"wire {rs} 通　收據 {run_dir}", file=sys.stderr)
    return verdict


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if a[:1] == ["--exec"]:
        return exec_inner(a[1], a[2:])
    if not a:
        print("用法：gateshim <agent> [agent 的參數…]", file=sys.stderr)
        return 2
    return run_gate(a[0], a[1:])


if __name__ == "__main__":
    raise SystemExit(main())
