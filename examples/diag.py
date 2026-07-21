import os, sys, tempfile, urllib.request
print("A start", flush=True)
# 端點不寫死（G10）：VACANT_ENDPOINT 指定，預設本機 LM Studio
url = os.environ.get("VACANT_ENDPOINT", "http://localhost:1234").rstrip("/") + "/v1"
try:
    urllib.request.urlopen(f"{url}/models", timeout=4).read()
    print(f"B url={url}", flush=True)
except Exception as e:
    print(f"B {url} fail {type(e).__name__}", flush=True)
print("C import vacant", flush=True)
from vacant.host import Host
from vacant.openai_substrate import OpenAISubstrate
from vacant.tasks import NICHES, make_task
print("D build host", flush=True)
h = Host(tempfile.mkdtemp(), substrate=OpenAISubstrate(url, model="google/gemma-4-e4b", timeout=60, temperature=0.7, learn=False))
print("E mint", flush=True)
h.mint("req", niches=[]); h.mint("expert", niches=list(NICHES))
eid = h.vacant_id("expert")
print("F one wake (real gemma call)", flush=True)
t = make_task(0)
out = h.waker.wake(eid, t["prompt"], t)
print(f"G wake done: answer={out.result.output!r}", flush=True)
