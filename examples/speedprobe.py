import json, os, urllib.request, time
M = "gemma-4-12b-coder-fable5-composer2.5-v1"
# 端點不寫死（G10）：VACANT_ENDPOINT 指定，預設本機 LM Studio
URL = os.environ.get("VACANT_ENDPOINT", "http://localhost:1234").rstrip("/") + "/api/v1/chat"
outs = []
for i in range(2):
    body = json.dumps({"model": M, "system_prompt": "Output ONLY the answer.",
                       "input": f"Reverse, output only the result: world{i}"}).encode()
    t0 = time.time()
    try:
        req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=90))
        s = d.get("stats", {})
        msg = [o.get("content") for o in d.get("output", []) if o.get("type") == "message"]
        outs.append("call%d time=%.1fs tok/s=%.1f out_tok=%s msg=%s" % (
            i, time.time() - t0, s.get("tokens_per_second", 0), s.get("total_output_tokens"), msg))
    except Exception as e:
        outs.append("call%d ERROR %s: %s" % (i, type(e).__name__, str(e)[:80]))
print("RESULT")
for o in outs:
    print(" ", o)
