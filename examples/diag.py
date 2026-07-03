import sys, tempfile, urllib.request
print("A start", flush=True)
url = None
for ip in ["192.168.76.1", "172.25.16.1", "172.17.119.12"]:
    try:
        urllib.request.urlopen(f"http://{ip}:1234/v1/models", timeout=4).read()
        url = f"http://{ip}:1234/v1"; print(f"B url={url}", flush=True); break
    except Exception as e:
        print(f"B {ip} fail {type(e).__name__}", flush=True)
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
