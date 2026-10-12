import json, urllib.request
B = "http://localhost:18000/v1/chat/completions"
def post(body):
    req = urllib.request.Request(B, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r: return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:400]
out = []
st, t = post({"model": "gemma-4-12b-it-qat", "messages": [{"role": "user", "content": "say ok"}], "max_completion_tokens": 16})
out.append(("(b) say ok", st, t[:260]))
st, t = post({"model": "gemma-4-12b-it-qat", "messages": [{"role": "user", "content": "say ok"}], "max_completion_tokens": 16, "reasoning_effort": "none"})
out.append(("(b) reasoning_effort none", st, t[:260]))
tools = [{"type": "function", "function": {"name": "bash", "description": "Run a shell command", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}]
st, t = post({"model": "gemma-4-12b-it-qat", "stream": True, "stream_options": {"include_usage": True}, "max_completion_tokens": 256,
              "reasoning_effort": "none", "messages": [{"role": "user", "content": "Use the bash tool to run: ls /app"}], "tools": tools})
out.append(("(b2) stream tool_calls", st, f"tool_calls 出現 {t.count('tool_calls')} 次；usage 列：" + str([l[:200] for l in t.splitlines() if '"usage"' in l and 'prompt_tokens' in l][-1:])))
for label, extra in (("預設", {}), ("reasoning_effort none", {"reasoning_effort": "none"}), ("enable_thinking true", {"chat_template_kwargs": {"enable_thinking": True}})):
    st, t = post({"model": "gemma-4-12b-it-qat", "max_completion_tokens": 800, "messages": [{"role": "user", "content": "A farmer has 17 sheep. All but 9 run away. How many are left?"}], **extra})
    try:
        d = json.loads(t); m = d["choices"][0]["message"]
        out.append(("思考探針 " + label, st, f"reasoning: {bool(m.get('reasoning_content') or m.get('reasoning'))} | usage {d.get('usage')} | {(m.get('content') or '')[:50]!r}"))
    except Exception as e:
        out.append(("思考探針 " + label, st, t[:200]))
open("/content/compat_probe.json", "w").write(json.dumps(out, ensure_ascii=False, indent=1))
for o in out: print(*o)
