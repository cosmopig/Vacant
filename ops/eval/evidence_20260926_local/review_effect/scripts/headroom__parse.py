"""Parse the local formal batch (711 runs) into a per-run record with per-turn text chunks.
Read-only on the data. Output: /tmp/claude-0/review_effect/headroom/runs.json"""
import json, re, pathlib, collections

ROOT = pathlib.Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3")
TASKS = pathlib.Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/dabstep_pinned/formal")
LEDGER = pathlib.Path("/home/user/Vacant/ops/eval/evidence_20260926_local/formal/ledger_formal.jsonl")
OUT = pathlib.Path("/tmp/claude-0/review_effect/headroom/runs.json")

WRITE_BASH = re.compile(r"(>>?\s*['\"]?(/app/)?answer\.txt)|(tee\s+(-a\s+)?['\"]?(/app/)?answer\.txt)|((cp|mv)\s+\S+\s+['\"]?(/app/)?answer\.txt)|(open\([^)]*answer\.txt[^)]*['\"][wa]['\"])|(write_text)")


def expected_of(task):
    t = (TASKS / f"dabstep-{task}" / "tests" / "test.sh").read_text()
    m = re.search(r"expected_answer=\$\(cat <<'ANSWER_EOF'\n(.*?)\nANSWER_EOF", t, re.S)
    return m.group(1)


def guideline_of(task):
    t = (TASKS / f"dabstep-{task}" / "instruction.md").read_text()
    m = re.search(r"guidelines you MUST follow when answering the question above: (.*?)\n\n", t, re.S)
    q = re.search(r"question you need to answer: (.*?)\n\n", t, re.S)
    return (m.group(1) if m else ""), (q.group(1) if q else "")


def parse_pi(p):
    turn = 0
    ev = dict(turns=0, chunks=[], calls=[], writes=[], nudges=[], checks=[], check_texts=[], stops=[], last_stop=None)
    pending = {}
    for line in open(p):
        try:
            e = json.loads(line)
        except Exception:
            continue
        t = e.get("type")
        if t == "turn_start":
            turn += 1
        elif t == "message_end":
            m = e.get("message") or {}
            role = m.get("role")
            for c in m.get("content") or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and role in ("assistant", "toolResult"):
                    ev["chunks"].append(dict(turn=turn, role=role, err=bool(m.get("isError")) if role == "toolResult" else False,
                                             tool=m.get("toolName"), call_id=m.get("toolCallId"), text=c.get("text", "")))
                elif c.get("type") == "toolCall":
                    name = c.get("name"); args = c.get("arguments") or {}
                    ev["calls"].append(dict(turn=turn, name=name, id=c.get("id"), args=args))
                    wrote = None
                    if name in ("write", "edit"):
                        path = str(args.get("path") or args.get("file_path") or "")
                        if path.endswith("answer.txt"):
                            wrote = str(args.get("content") if name == "write" else args.get("newText") or args.get("new_string"))
                    elif name == "bash":
                        cmd = str(args.get("command") or "")
                        if "answer.txt" in cmd and WRITE_BASH.search(cmd):
                            wrote = cmd
                    if wrote is not None:
                        ev["writes"].append(dict(turn=turn, content=wrote[:500], tool=name))
        elif t == "entry_appended":
            en = e.get("entry") or {}
            ct = en.get("customType")
            if ct == "vacant-budget":
                ev["nudges"].append(turn)
            elif ct == "vacant-check":
                ev["checks"].append(turn); ev["check_texts"].append(str(en.get("content"))[:800])
        elif t == "turn_end":
            m = e.get("message") or {}
            ev["last_stop"] = m.get("stopReason")
            ev["stops"].append((turn, m.get("stopReason")))
    ev["turns"] = turn
    return ev


def main():
    nreq = collections.Counter(); ptok = collections.Counter()
    for line in open(LEDGER):
        r = json.loads(line)
        nreq[r["tag"]] += 1
        ptok[r["tag"]] += (r.get("usage") or {}).get("prompt_tokens") or 0
    rows = []
    for res in sorted(ROOT.glob("g12-off-*-s*/*/dabstep-*__*/result.json")):
        trial = res.parent
        arm, s = trial.parents[1].name.removeprefix("g12-off-").rsplit("-s", 1)
        task = trial.name.split("__")[0].removeprefix("dabstep-")
        job = trial.parent.name
        r = json.loads(res.read_text())
        vr = r.get("verifier_result") or {}
        reward = (vr.get("rewards") or {}).get("reward")
        try:
            vout = (trial / "verifier" / "test-stdout.txt").read_text()
        except OSError:
            vout = ""
        got = re.search(r"Got: (.*)", vout)
        cfg = r["config"]["agent"]["env"]["OPENROUTER_BASE_URL"]
        up = re.search(r"/up/([^/]+)/", cfg)
        vc = None
        pvc = trial / "agent" / "vacant_check.json"
        if pvc.exists():
            try:
                vc = json.loads(pvc.read_text().strip().splitlines()[-1])
            except Exception:
                vc = None
        ae = r.get("agent_execution") or {}
        g, q = guideline_of(task)
        rows.append(dict(task=task, arm=arm, sample=int(s), job=job, trial=str(trial), reward=reward,
                         file=("answer.txt not found" not in vout) if vout else None,
                         got=got.group(1) if got else None, expected=expected_of(task), guideline=g, question=q,
                         upstream=up.group(1) if up else None, nreq=nreq[job], prompt_tokens=ptok[job],
                         agent_start=ae.get("started_at"), agent_end=ae.get("finished_at"),
                         exc=(r.get("exception_info") or {}).get("exception_type"), vc=vc,
                         pi=parse_pi(trial / "agent" / "pi.txt")))
    OUT.write_text(json.dumps(rows))
    print(len(rows), collections.Counter((x["arm"], x["sample"]) for x in rows))


if __name__ == "__main__":
    main()
