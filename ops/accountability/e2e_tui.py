#!/usr/bin/env python3
"""e2e_tui — **人直接開 agent 的互動介面打字**：回饋有沒有到模型手上、人看不看得到。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §五；LOOP「互動 TUI 的回饋」）：

`e2e_trace.py` 的矩陣全部走 headless（`claude -p`、`codex exec`、`pi -p`、`opencode run`），但人類定的場景是
「**人直接用一個 agent**」——大多數時候就是開它的互動介面打字。這支把同樣的埋錯情境放進四個 agent 的
**真 TUI**（tmux 裡的偽終端機，像人一樣按鍵：打提示、按 Enter、做完之後下離開的指令），量：

- 追緝有沒有追到對的那一步（同 `e2e_trace` 的判準）；
- 回饋（有位置的版本）有沒有出現在下一次模型請求裡、改好之後過不過、收件的最後裁決；
- **人看不看得到**：回饋有沒有出現在畫面上（`capture-pane` 的文字，存成 `<agent>/<情境>.screen.txt`）；
- Vacant 的回饋有沒有被病歷記成「人說的話」（病歷裡 `source=user` 的提示只能是人打的那一則；
  OpenCode 的外掛不記提示，那一欄是 0）；
- OpenCode：`opencode run` 在第一個 idle 就結束、沒有交件前回饋；互動 TUI 靠外掛在 idle 時用 SDK
  把回饋送回（`adapters/agents.py`）——**這條路在這支之前沒有量過**。

每個 agent 一個隔離的「使用者」（同 `e2e_trace.Lab`：自己的 HOME、provider 指到假模型、假金鑰），
外加「這個人已經走過第一次開啟的對話框」的設定（Claude Code 的上手流程／信任這個資料夾／核可這把
假金鑰；Codex 的信任這個專案）。子行程用 `env -i` 起，只帶 `Lab.env()` 那一份環境。

輸出：`<out>/results.json`、`<out>/SUMMARY.md`、`<out>/<agent>/<情境>.screen.txt`。

## 誠實邊界

1. **L-fake**：模型照劇本回答（同 `e2e_trace`）。證明的是回饋在四個真 TUI 的真掛鉤上接得起來、
   模型與人都收得到——**不是**真模型下產出更接近需求。
2. 畫面是 tmux 抓到的**文字**，不是截圖；全螢幕的 TUI（OpenCode）只抓得到當下那一屏。
3. 按鍵時機靠「畫面上出現了就緒的字樣」＋固定等待；一個 TUI 還沒畫好就收到的按鍵會掉（OpenCode 實測過），
   所以送出提示後 30 秒內假模型沒收到任何請求就**重送一次**，結果裡記 `prompt_resent`。
4. 預設只跑不需要子 agent、也不需要兩跑的情境（B、A、C）：子 agent 與人的標記在 `e2e_trace` 的矩陣裡量過，
   那部分和介面無關（掛鉤是同一組）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shlex
import shutil
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ops" / "accountability"))
import e2e_trace as T  # noqa: E402

#: 畫面上出現這個字樣 ⇒ 介面畫好了、可以打字
READY = {"claude": "accept edits", "codex": "Ask Codex to do anything",
         "pi": "mock-model", "opencode": "Ask anything"}
#: 人離開的方式（tmux 的按鍵序列；字串＝照字打，其餘＝tmux 的鍵名）
EXIT = {"claude": [("l", "/exit"), ("k", "Enter")], "codex": [("l", "/quit"), ("k", "Enter")],
        "opencode": [("l", "/exit"), ("k", "Enter")], "pi": [("k", "C-d")]}
#: 回饋第一行（`adapters/hookpolicy.FEEDBACK_HEADER` 的開頭）：出現在畫面上 ⇒ 人看得到
SHOWN = "checks do not pass yet"
EXITED = "__VACANT_TUI_EXITED__"
DEFAULT_SCENARIOS = "B_agent_fault,A_input_fault,C_script_fault,M_multi_turn"

#: 只在互動介面有意義的情境。M：人先問一句（還不要它交件）——回合結束時契約還沒過，回饋把輪數用完；
#: 之後人才要它寫報告、它寫錯。**新的要求要有新的輪數**，否則寫錯的那一次 agent 收不到位置
#: （2026-09-25 做這支時發現、修了：`hookpolicy.new_request`）。
TUI_SCENARIOS: dict[str, dict] = {
    "M_multi_turn": {
        # 上限 1 輪：第一回合一定用完（OpenCode 的外掛等自己送回的回饋時不驗那段 idle，上限 2 時它第一回合只用 1 輪，
        # 走不到重置——2026-09-25 第一次跑就是這樣），第二回合的回饋只可能來自「人的新要求重新算輪數」
        "max_feedback_rounds": 1,
        "turns": [
            {"when": "How many data rows", "say": "How many data rows does inputs/ledger.csv have? "
                                                  "Just answer; don't write any file yet.",
             "steps": [{"run": "cat inputs/ledger.csv"}], "final": "It has 3 data rows.",
             "fix": {"steps": [], "final": "Noted. I'll write the report when you ask."}},
            {"when": "Now write report.md", "say": "Now write report.md with the quarter total "
                                                   "described in the task contract.",
             "steps": [{"write": ["report.md", "# Quarter\n\nTotal: 999\n"]}], "final": "Done.",
             "fix": {"steps": [{"run": "cat inputs/ledger.csv"},
                               {"write": ["report.md", "# Quarter\n\nTotal: 69\n"]}],
                     "final": "Fixed."}}]},
}
TUI_EXPECT: dict[str, dict] = {"M_multi_turn": {   # 同 B：寫錯的是第二回合寫報告的那一步
    "state": "located", "fault_class": "agent", "confidence": "provable",
    "step_writes": "report.md", "value": "999"}}
T.SCENARIOS.update(TUI_SCENARIOS)
T.EXPECT.update(TUI_EXPECT)


def tui_argv(lab: T.Lab) -> list[str]:
    b = lab.bindir
    if lab.agent == "claude":
        return [shutil.which("claude") or "claude", "--permission-mode", "acceptEdits",
                "--allowedTools", "Bash"]
    if lab.agent == "codex":
        argv = [str(b / "codex"), "-s", "workspace-write", "-a", "never"]
        if lab.web:
            argv += ["-c", "sandbox_workspace_write.network_access=true"]
        return argv
    if lab.agent == "pi":
        return [str(b / "pi"), "--provider", "mock", "--model", "mock-model"]
    return [str(b / "opencode"), str(lab.proj)]


def first_run_done(lab: T.Lab) -> None:
    """這個人已經走過第一次開啟的對話框（不是 Vacant 的設定；少了它 TUI 停在對話框上）。"""
    if lab.agent == "claude":
        cj = lab.home / ".claude.json"
        d = json.loads(cj.read_text()) if cj.is_file() else {}
        d.update(hasCompletedOnboarding=True, theme="dark", numStartups=3,
                 customApiKeyResponses={"approved": ["sk-fake-offline-000"[-20:]], "rejected": []})
        d.setdefault("projects", {})[str(lab.proj)] = {"hasTrustDialogAccepted": True,
                                                       "allowedTools": []}
        cj.write_text(json.dumps(d, indent=2))
    elif lab.agent == "codex":
        with open(lab.home / ".codex" / "config.toml", "a", encoding="utf-8") as f:
            f.write(f'\n[projects."{lab.proj}"]\ntrust_level = "trusted"\n')


class Pane:
    def __init__(self, name: str):
        self.name = name

    def start(self, cwd: pathlib.Path, env: dict[str, str], argv: list[str]) -> None:
        envs = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
        cmd = (f"cd {shlex.quote(str(cwd))} && env -i {envs} {shlex.join(argv)}; "
               f"echo {EXITED} $?; sleep 600")
        subprocess.run(["tmux", "kill-session", "-t", self.name], capture_output=True)
        subprocess.run(["tmux", "new-session", "-d", "-s", self.name, "-x", "160", "-y", "50",
                        cmd], check=True)

    def text(self, history: int = 0) -> str:
        argv = ["tmux", "capture-pane", "-p", "-J", "-t", self.name]
        if history:
            argv[3:3] = ["-S", f"-{history}"]
        return subprocess.run(argv, capture_output=True, text=True).stdout

    def keys(self, seq: list[tuple[str, str]]) -> None:
        for kind, k in seq:
            subprocess.run(["tmux", "send-keys", "-t", self.name, *(["-l"] if kind == "l" else []),
                            k], check=False)
            time.sleep(0.7)

    def wait(self, needle: str, timeout: float) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if needle in self.text():
                return True
            time.sleep(0.5)
        return False

    def kill(self) -> None:
        subprocess.run(["tmux", "kill-session", "-t", self.name], capture_output=True)


def mock_rows(lab: T.Lab) -> list[dict]:
    if not lab.mock_log.is_file():
        return []
    return [json.loads(x) for x in lab.mock_log.read_text().splitlines() if x.strip()]


def fixed(rows: list[dict]) -> bool:
    """看過回饋之後，模型已經回了收尾的文字（劇本的 `fix` 段演完了）。"""
    return any(r.get("fed_back") and r.get("reply") == "text" for r in rows)


def stop_rounds(lab: T.Lab) -> list[int]:
    """這個專案的回合結束驗收記到第幾輪（掛鉤的事件紀錄）。"""
    p = lab.vhome / "intake" / "hooks" / "events.jsonl"
    cp = str(lab.proj / ".vacant" / "contract.json")
    out = []
    for line in (p.read_text().splitlines() if p.is_file() else []):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("kind") == "stop" and d.get("contract") == cp and d.get("round"):
            out.append(int(d["round"]))
    return out


def settled(lab: T.Lab, since: int, quiet: float, timeout: float) -> list[dict]:
    """等這一回合安靜下來：`since` 之後有請求，而且 `quiet` 秒沒有新的（回合結束的驗收與回饋都跑完了）。"""
    t0 = time.time()
    last_n, last_t = -1, time.time()
    while time.time() - t0 < timeout:
        rows = mock_rows(lab)
        if len(rows) != last_n:
            last_n, last_t = len(rows), time.time()
        elif len(rows) > since and time.time() - last_t >= quiet:
            break
        time.sleep(0.5)
    return mock_rows(lab)[since:]


def run_tui(lab: T.Lab, scn: str, timeout: float) -> dict:
    tag = scn.split("_")[0].lower()
    lab.proj = lab.root / f"proj-{tag}"
    lab.reset_project(f"q-total-{tag}")
    rounds = T.SCENARIOS[scn].get("max_feedback_rounds")
    if rounds is not None:                             # 這個情境自己的輪數上限：改了契約就重新鎖
        cp = lab.proj / ".vacant" / "contract.json"
        raw = json.loads(cp.read_text())
        raw.pop("lock", None)
        raw["hooks"]["max_feedback_rounds"] = rounds
        cp.write_text(json.dumps(raw, indent=2))
        r = lab.vacant("contract", "lock")
        assert r.returncode == 0, r.stderr
    lab.mock_log.unlink(missing_ok=True)
    lab.subagents = False
    lab.web = scn.startswith("F_")
    first_run_done(lab)
    lab.start_mock(T.SCENARIOS[scn])
    env = lab.env()
    env["TERM"] = "xterm-256color"
    if lab.web:
        env.update(http_proxy=f"http://127.0.0.1:{lab.port}",
                   no_proxy="127.0.0.1,localhost", NO_PROXY="127.0.0.1,localhost")
    pane = Pane(f"vacant-tui-{lab.agent}-{tag}")
    t0 = time.time()
    ready = resent = exited = False
    screen = ""
    turns = T.SCENARIOS[scn].get("turns") or []
    says = [t["say"] for t in turns] or [T.PROMPT]
    extra: dict = {}
    try:
        pane.start(lab.proj, env, tui_argv(lab))
        ready = pane.wait(READY[lab.agent], 60)
        time.sleep(2)                                  # 就緒的字樣出現之後，輸入框還要一下子
        for say in says[:-1]:                          # 前面的回合：人問問題，還不要它交件
            n0 = len(mock_rows(lab))
            pane.keys([("l", say), ("k", "Enter")])
            first = settled(lab, n0, 10, timeout)
            extra.setdefault("earlier_turns", []).append({
                "requests": len(first), "fed_back": sum(1 for r in first if r.get("fed_back"))})
        if len(says) > 1:
            # 前面的回合真的把輪數用完了嗎？沒用完，最後一回合的回饋就證明不了「新要求重新算輪數」
            # （2026-09-25 審查 harness#1：OpenCode 第一次跑就是沒用完、照樣算過）
            cap = int(json.loads((lab.proj / ".vacant" / "contract.json").read_text())
                      ["hooks"]["max_feedback_rounds"])
            extra["earlier_turns_used_the_budget"] = max(stop_rounds(lab) or [0]) >= cap
        n_before = len(mock_rows(lab))
        pane.keys([("l", says[-1]), ("k", "Enter")])
        t1 = time.time()
        while time.time() - t1 < 30 and len(mock_rows(lab)) <= n_before:
            time.sleep(0.5)
        if len(mock_rows(lab)) <= n_before:            # 按鍵掉了（介面還沒畫好）：重送一次
            resent = True
            pane.keys([("l", says[-1]), ("k", "Enter")])
        while time.time() - t0 < timeout and not fixed(mock_rows(lab)[n_before:]):
            time.sleep(1)
        last = mock_rows(lab)[n_before:]
        extra["_last_feedback"] = [r.get("feedback") for r in last if r.get("feedback")]
        time.sleep(4)                                  # 改好之後的那次回合結束驗收
        screen = pane.text(history=400)
        pane.keys(EXIT[lab.agent])
        exited = pane.wait(EXITED, 45)
    finally:
        pane.kill()
        lab.stop_mock()
    wall = round(time.time() - t0, 1)
    time.sleep(3)                                      # 背景的 submit／finalize
    for _ in range(30):
        if any(e["type"] == "finding" for e in lab.trace_events()):
            break
        time.sleep(1)
    res = T.collect(lab, scn, rc=None, wall=wall, err_tail="")
    typed = {hashlib.sha256(x.encode()).hexdigest() for x in says}
    evs = lab.trace_events()
    # 「有位置的回饋」＝指到這一格結論的那個值（`… says "999"`）；前面回合的泛用回饋、輪數用完時給人的摘要
    # （`report.md:3 = 999`）都不算（2026-09-25 審查 harness#2、#5）
    value = str((res.get("finding") or {}).get("value") or "")
    located = f'says "{value}"' if value else SHOWN
    extra["feedback_in_last_turn"] = any(located in str(x) for x in extra.pop("_last_feedback", []))
    shown = located in screen
    (lab.root / f"{scn}.screen.txt").write_text(screen.replace(str(lab.root.parent), "<out>"))
    res.update(extra)
    if res.get("earlier_turns_used_the_budget") is False:
        # 前面的回合沒把輪數用完 ⇒ 最後一回合的回饋證明不了「新要求重新算輪數」：這一格不算過
        res["judgement"] = {"correct": False, "mismatch": [
            "earlier turns did not use the whole feedback budget, so this row does not test the "
            "per-request reset"]}
    res.update({
        "tui_ready": ready, "prompt_resent": resent, "exited_cleanly": exited,
        "feedback_shown_to_person": shown,
        "person_prompts_in_trace": sum(1 for e in evs if e["type"] == "prompt"
                                       and e.get("source") == "user"),
        # 病歷記成「人說的」、但不是人打的（例如 Vacant 自己的回饋）：應該是 0
        "untyped_person_prompts": sum(1 for e in evs if e["type"] == "prompt"
                                      and e.get("source") == "user"
                                      and e.get("text_blob") not in typed),
        "screen_file": f"{lab.agent}/{scn}.screen.txt",
    })
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True, help="directory with the codex/opencode/pi binaries")
    ap.add_argument("--out", required=True)
    ap.add_argument("--agents", default="claude,codex,pi,opencode")
    ap.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    ap.add_argument("--timeout", type=float, default=150)
    args = ap.parse_args()
    if not shutil.which("tmux"):
        print("e2e_tui: needs tmux", file=sys.stderr)
        return 2
    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    results: dict = {"schema": "vacant-e2e-tui/1", "evidence_level": "L-fake (scripted model)",
               "surface": "interactive TUI in a tmux pseudo-terminal",
               "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "agents": {}}
    for agent in args.agents.split(","):
        root = out / agent
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        lab = T.Lab(agent, root, pathlib.Path(args.bin).resolve())
        lab.via_do = False
        lab.user_config()
        vers = subprocess.run(lab.native_argv("x")[:1] + ["--version"], env=lab.env(),
                              capture_output=True, text=True, timeout=60)
        inst = subprocess.run([T.PY, "-m", "vacant_network", "install", "--agents", agent],
                              env=lab.env(), capture_output=True, text=True, timeout=120)
        res: dict = {"version": (vers.stdout or vers.stderr).strip().splitlines()[:1],
               "install_exit": inst.returncode, "runs": {}}
        for scn in args.scenarios.split(","):
            try:
                res["runs"][scn] = run_tui(lab, scn, args.timeout)
            except Exception as e:  # noqa: BLE001 — 一格壞了照記，不拖垮整張表
                lab.stop_mock()
                res["runs"][scn] = {"scenario": scn, "harness_error": repr(e)[:400],
                                    "judgement": {"correct": False, "why": "harness error"},
                                    "finding": None}
            x = res["runs"][scn]
            print(f"[e2e-tui] {agent} {scn}: {'OK' if x['judgement']['correct'] else 'MISS'} "
                  f"fb_model={x.get('feedback_reached_model')} "
                  f"shown={x.get('feedback_shown_to_person')} final={x.get('final_decision')}",
                  flush=True)
        results["agents"][agent] = res
    results["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    (out / "SUMMARY.md").write_text(summary(results))
    print(summary(results))
    return 0


def summary(r: dict) -> str:
    lines = ["# e2e_tui — four real agents' interactive TUIs × planted faults (L-fake)", "",
             f"started {r.get('started')} · finished {r.get('finished')}", "",
             "| agent | scenario | attribution | got (state / class / grade) | "
             "feedback reached model (in the last turn) | shown to the person | "
             "actor id in feedback | resolved | "
             "final | person's prompts in trace (not typed by the person) | prompt resent | chain | "
             "earlier turns used the whole budget |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    n = ok = fb = shown = acc = 0
    for a, res in r["agents"].items():
        for scn, x in res["runs"].items():
            n += 1
            if x.get("harness_error"):
                lines.append(f"| {a} | {scn} | ❌ harness error: {x['harness_error'][:80]} |"
                             + " |" * 11)
                continue
            f = x.get("finding") or {}
            ok += int(x["judgement"]["correct"])
            fb += int(bool(x.get("feedback_in_last_turn")))
            shown += int(bool(x["feedback_shown_to_person"]))
            acc += int(x["final_decision"] == "accept")
            lines.append(
                f"| {a} | {scn} | {'✅' if x['judgement']['correct'] else '❌ ' + '; '.join(x['judgement'].get('mismatch') or [x['judgement'].get('why', '')])} "
                f"| {f.get('state')} / {f.get('fault_class')} / {f.get('confidence')} "
                f"| {x['feedback_reached_model']} ({x.get('feedback_in_last_turn')}) "
                f"| {x['feedback_shown_to_person']} "
                f"| {x['feedback_has_actor_id']} | {x['resolved_after_feedback']} "
                f"| {x['final_decision']} | {x['person_prompts_in_trace']} "
                f"({x['untyped_person_prompts']}) "
                f"| {x['prompt_resent']} | {x['chain_verifies']} "
                f"| {x.get('earlier_turns_used_the_budget', '—')} |")
    rej = sum(int(x.get("auth_rejected") or 0) for res in r["agents"].values()
              for x in res["runs"].values())
    multi = [x for res in r["agents"].values() for x in res["runs"].values()
             if "earlier_turns_used_the_budget" in x]
    used = sum(1 for x in multi if x["earlier_turns_used_the_budget"])
    lines += ["", f"**attribution correct: {ok}/{n}** · feedback reached the model in the turn "
              f"that wrote the error: {fb}/{n} · "
              f"shown to the person: {shown}/{n} · accepted after the fix: {acc}/{n} · "
              f"model requests with a credential other than the fake key: {rej}"
              + (f" · multi-turn rows whose earlier turns used the whole budget (so the last turn's "
                 f"feedback can only come from the per-request reset): {used}/{len(multi)}"
                 if multi else ""), ""]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
