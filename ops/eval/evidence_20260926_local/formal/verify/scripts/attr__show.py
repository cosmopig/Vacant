import json, sys
rows = json.load(open("/tmp/claude-0/verify_formal/attr/runs.json"))
R = {(r["task"], r["arm"], r["sample"]): r for r in rows}
t, a, s = sys.argv[1], sys.argv[2], int(sys.argv[3])
lo = int(sys.argv[4]) if len(sys.argv) > 4 else 1
turn = 0
for line in open(R[(t, a, s)]["trial"] + "/agent/pi.txt"):
    try: e = json.loads(line)
    except: continue
    ty = e.get("type")
    if ty == "turn_start": turn += 1
    if turn < lo: continue
    if ty == "tool_execution_start": print(f"[{turn}] CALL {e.get('toolName')}: {json.dumps(e.get('args'))[:300]}")
    elif ty == "message_end":
        m = e.get("message") or {}
        if m.get("role") == "toolResult":
            print(f"[{turn}] RESULT: " + " ".join(c.get("text", "") for c in m.get("content") or [] if c.get("type") == "text")[:300].replace("\n", " | "))
        elif m.get("role") == "assistant":
            tx = " ".join(c.get("text", "") for c in m.get("content") or [] if c.get("type") == "text")
            if tx.strip(): print(f"[{turn}] SAY: {tx[:400]}".replace("\n", " "))
    elif ty == "entry_appended":
        print(f"[{turn}] VACANT {e['entry'].get('customType')}: {str(e['entry'].get('content'))[:250]}".replace("\n", " "))
