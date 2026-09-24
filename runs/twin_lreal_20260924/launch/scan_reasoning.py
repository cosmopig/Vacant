"""逐通掃 wire_*/*.resp.bin 的 SSE 塊：reasoning_content 有沒有非空、usage.reasoning_tokens 分佈、model 分佈。"""
import collections
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
files = sorted(root.glob("runs/*/wire_*/*.resp.bin"))
n_parsed = 0
rc_resp = 0
rc_chunks = 0
rt = collections.Counter()
models = collections.Counter()
thought_marker = 0
arm = collections.Counter()
for f in files:
    arm["ON" if "RUN-ON" in f.parent.name else "OFF"] += 1
    raw = f.read_bytes().decode("utf-8", "replace")
    chunks = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            p = line[5:].strip()
            if p and p != "[DONE]":
                try:
                    chunks.append(json.loads(p))
                except Exception:
                    pass
    if not chunks:
        try:
            chunks = [json.loads(raw)]
        except Exception:
            continue
    n_parsed += 1
    has = False
    content = ""
    for c in chunks:
        if c.get("model"):
            models[c["model"]] += 1
        for ch in c.get("choices") or []:
            d = ch.get("delta") or ch.get("message") or {}
            if d.get("reasoning_content"):
                has = True
                rc_chunks += 1
            content += d.get("content") or ""
        u = c.get("usage")
        if u is not None:
            det = u.get("completion_tokens_details") or {}
            rt[str(det.get("reasoning_tokens", u.get("reasoning_tokens")))] += 1
    rc_resp += has
    thought_marker += "<|channel>thought" in content
print(json.dumps({
    "resp_files": len(files), "parsed": n_parsed,
    "resp_with_nonempty_reasoning_content": rc_resp,
    "reasoning_content_chunks": rc_chunks,
    "usage_reasoning_tokens": dict(rt), "model_chunks": dict(models),
    "content_with_empty_thought_channel_marker": thought_marker,
    "resp_files_by_arm": dict(arm)}, ensure_ascii=False, indent=1))
