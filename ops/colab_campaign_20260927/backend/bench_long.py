import json, random, statistics, time, urllib.request, concurrent.futures as cf
B = "http://localhost:18000/v1/chat/completions"
VOC = ("merchant payment fee card scheme acquirer country volume fraud rate transaction amount monthly average "
       "account type category code capture delay intracountry credit debit ratio dataset column row value total "
       "percentage filter group sort compute result answer question manual section policy rule threshold").split()
def text(ntok, rnd):   # 約 1 字 ≈ 1.3 token
    return " ".join(rnd.choice(VOC) + (str(rnd.randint(0, 999)) if rnd.random() < 0.2 else "") for _ in range(int(ntok / 1.3)))
def post(msgs, mx):
    body = {"model": "gemma-4-12b-it-qat", "messages": msgs, "max_completion_tokens": mx, "reasoning_effort": "none", "temperature": 0.7}
    req = urllib.request.Request(B, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time(); d = json.load(urllib.request.urlopen(req, timeout=1200)); return time.time() - t0, d
def session(sid):
    rnd = random.Random(1000 + sid)
    msgs = [{"role": "system", "content": "You are a data analyst agent. Reference material follows.\n" + text(35000, rnd)}]
    lat, cached, prompt = [], [], []
    for turn in range(10):
        msgs.append({"role": "user", "content": f"Tool output {turn}:\n" + text(1500, rnd) + "\nState the next step in about 150 words."})
        dt, d = post(msgs, 200)
        msgs.append({"role": "assistant", "content": d["choices"][0]["message"].get("content") or ""})
        u = d["usage"]; lat.append(dt); prompt.append(u["prompt_tokens"]); cached.append((u.get("prompt_tokens_details") or {}).get("cached_tokens", 0))
    return lat, prompt, cached
for S in (4, 16, 32):
    t0 = time.time()
    with cf.ThreadPoolExecutor(S) as ex: rs = list(ex.map(session, range(S * 100, S * 100 + S)))
    wall = time.time() - t0
    first = [r[0][0] for r in rs]; later = sorted(x for r in rs for x in r[0][1:])
    hit = sum(sum(r[2][1:]) for r in rs) / max(1, sum(sum(r[1][1:]) for r in rs))
    rec = {"sessions": S, "wall_s": round(wall), "prompt_tokens_first": rs[0][1][0], "prompt_tokens_last": rs[0][1][-1],
           "first_call_p50_s": round(statistics.median(first), 1), "first_call_max_s": round(max(first), 1),
           "later_calls_p50_s": round(statistics.median(later), 1), "later_calls_p90_s": round(later[int(len(later) * .9) - 1], 1),
           "later_calls_max_s": round(max(later), 1), "cache_hit_ratio_later": round(hit, 3),
           "calls_per_min": round(S * 10 / wall * 60, 1)}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    open("/content/bench_results.jsonl", "a").write(json.dumps({"engine": "vLLM 0.30.0 w4a16-ct G4", **rec}) + "\n")
