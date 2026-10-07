import sys, json, certifi, os, asyncio
certifi.where = lambda: "/root/.ccr/ca-bundle.crt"
import edge_tts
async def one(text, out):
    c = edge_tts.Communicate(text, "zh-TW-HsiaoChenNeural", rate="+4%", boundary="WordBoundary", proxy=os.environ.get("HTTPS_PROXY"))
    words = []
    with open(out, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio": f.write(ch["data"])
            elif ch["type"] == "WordBoundary": words.append([ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]])
    return words
async def main():
    L = json.load(open("lines.json")); allw = []
    for i, (zh, en) in enumerate(L):
        allw.append(await one(zh, f"vo/{i:02d}.mp3"))
    json.dump(allw, open("words_raw.json", "w"), ensure_ascii=False)
asyncio.run(main())
