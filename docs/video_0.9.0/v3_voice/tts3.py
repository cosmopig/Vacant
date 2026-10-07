import json, certifi, os, asyncio, subprocess, numpy as np
certifi.where = lambda: "/root/.ccr/ca-bundle.crt"
import edge_tts
VO = {"narr": "zh-TW-HsiaoChenNeural", "agent": "zh-TW-YunJheNeural"}
async def one(c):
    com = edge_tts.Communicate(c["zh"], VO[c["v"]], rate=c["rate"], pitch=c["pitch"], volume=c["vol"], boundary="WordBoundary", proxy=os.environ.get("HTTPS_PROXY"))
    words = []
    with open(f"vo/{c['id']}.mp3", "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio": f.write(ch["data"])
            elif ch["type"] == "WordBoundary": words.append([ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]])
    return words
async def main():
    C = json.load(open("clips.json")); out = {}
    for c in C:
        w = await one(c)
        raw = subprocess.check_output(['ffmpeg','-v','error','-i',f"vo/{c['id']}.mp3",'-f','s16le','-ac','1','-ar','48000','-'])
        x = np.frombuffer(raw, np.int16).astype(float) / 32768
        lead = np.argmax(np.abs(x) > 10 ** (-50 / 20)) / 48000
        subprocess.run(['ffmpeg','-y','-v','error','-i',f"vo/{c['id']}.mp3",'-af','silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse','-ar','48000','-ac','1',f"vo/{c['id']}.wav"], check=True)
        d = float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f"vo/{c['id']}.wav"]))
        out[c["id"]] = {"dur": round(d, 3), "words": [[round(max(0, o - lead), 3), round(du, 3), t] for o, du, t in w]}
        print(c["id"], round(d, 2), round(c["at"], 2), "->", round(c["at"] + d, 2), [t for _, _, t in w])
    json.dump(out, open("clipwords.json", "w"), ensure_ascii=False)
asyncio.run(main())
