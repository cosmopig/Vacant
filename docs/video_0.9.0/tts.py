import sys, certifi
certifi.where = lambda: "/root/.ccr/ca-bundle.crt"
import os, asyncio, edge_tts
async def main(voice, text, out, rate="+0%", pitch="+0Hz"):
    c = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, proxy=os.environ.get("HTTPS_PROXY"))
    sub = edge_tts.SubMaker()
    with open(out, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio": f.write(ch["data"])
            elif ch["type"] in ("WordBoundary","SentenceBoundary"): sub.feed(ch)
    open(out+".srt","w").write(sub.get_srt())
args = sys.argv[1:]
asyncio.run(main(*args))
