"""vLLM 並行數量測：同一台 Colab VM、同一個模型，不同並行數下「每輪回應時間」是多少（2026-11-21）。

目的：E4B 與 atimeout 預註冊前要寫明打算用的 jobs 值，並讓每輪時間落在本機批次的範圍附近
（本機 3090、llama.cpp、jobs 1：每輪平均 5–12 秒；Colab jobs 6：平均 24–50 秒，見 analysis/turn_latency.py）。

做法：對 127.0.0.1:8000 送 agent 形狀的請求（長上下文＋中等輸出），每個並行數 c 同時送 c 個、重複 rounds 次，
記錄每個請求的牆鐘時間（＝一輪模型回應時間）與輸出 token 數。只用標準函式庫，可用 colab exec 餵進 VM：
在程式前面設 MODEL＝"gemma-4-12b-it-qat"、LEVELS＝[1,2,3,4,6]、CTX_TOKENS＝[6000, 24000]。
"""
import json
import statistics
import threading
import time
import urllib.request

MODEL = globals().get("MODEL", "gemma-4-12b-it-qat")
LEVELS = globals().get("LEVELS", [1, 2, 3, 4, 6])
CTX_TOKENS = globals().get("CTX_TOKENS", [6000, 24000])
ROUNDS = globals().get("ROUNDS", 2)
MAX_TOKENS = globals().get("MAX_TOKENS", 400)
URL = "http://127.0.0.1:8000/v1/chat/completions"

FILLER = ("def helper_{i}(x):\n    # utility used by the test suite\n    return [y * {i} for y in range(x)]\n\n")


def _prompt(n_tokens: int, salt: int) -> list:
    # 約 4 字元 ≈ 1 token；每個請求加 salt，避免 prefix cache 讓量測過度樂觀
    body = []
    i = 0
    while len("".join(body)) < n_tokens * 4:
        body.append(FILLER.format(i=i + salt * 1000))
        i += 1
    return [
        {"role": "system", "content": "You are a coding agent. Read the code and answer briefly."},
        {"role": "user", "content": f"[run {salt}]\n" + "".join(body) +
         "\nExplain in about 200 words what helper_3 returns and propose one test."},
    ]


def _one(n_tokens: int, salt: int, out: list) -> None:
    req = json.dumps({"model": MODEL, "messages": _prompt(n_tokens, salt), "max_tokens": MAX_TOKENS,
                      "temperature": 0.0}).encode()
    t0 = time.time()
    try:
        r = urllib.request.urlopen(urllib.request.Request(URL, data=req, headers={"Content-Type": "application/json"}),
                                   timeout=900)
        d = json.loads(r.read())
        toks = (d.get("usage") or {}).get("completion_tokens")
        out.append((time.time() - t0, toks, None))
    except Exception as e:  # noqa: BLE001
        out.append((time.time() - t0, None, repr(e)[:120]))


def main() -> None:
    salt = int(time.time()) % 100000
    rows = []
    for ctx in CTX_TOKENS:
        for c in LEVELS:
            lat = []
            errs = 0
            for _ in range(ROUNDS):
                res: list = []
                ths = []
                for _k in range(c):
                    salt += 1
                    th = threading.Thread(target=_one, args=(ctx, salt, res))
                    th.start()
                    ths.append(th)
                for th in ths:
                    th.join()
                lat += [x[0] for x in res if x[2] is None]
                errs += sum(1 for x in res if x[2] is not None)
            row = {"ctx_tokens": ctx, "concurrency": c, "n": len(lat), "errors": errs,
                   "mean_s": round(statistics.fmean(lat), 1) if lat else None,
                   "max_s": round(max(lat), 1) if lat else None}
            rows.append(row)
            print(json.dumps(row), flush=True)
    print("PROBE_DONE", json.dumps({"model": MODEL, "rows": rows}))


main()
