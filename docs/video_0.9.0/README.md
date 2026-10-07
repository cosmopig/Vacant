# 0.9.0（v3.7）60 秒影片——原始碼

橫式 16:9 與直式 9:16 兩支、中文配音（zh-TW）、中英雙字幕（燒在畫面上＋另附 SRT／MP4 內嵌軟字幕）、配樂與音效全部由這個資料夾生成。
成片（MP4）不進 git（每支約 30 MB）。

**兩層內容**：配音＋大字給第一次看的人；四角的等寬小字（模組路徑、Ed25519、330 秒、五類 `kind`、條件與 p 值）給會暫停的人。
**口徑**：42.0% → 53.2% 一律和條件同框（DABstep 77×3、gemma-4-12b QAT、pi 0.87.1 `--print`、15 回合上限、預註冊）；
不設上限的 94 題「沒有量到差別」也在畫面上；用「有根據／可究責」，不用「信任」。來源：`CHANGELOG.md` 0.9.0、`README.md` 零設定一節。

## 重建

```bash
pip install edge-tts playwright scipy numpy
# 1. 字型（Noto Sans TC／Inter／JetBrains Mono，OFL）→ fonts/local.css＋woff2（見 fetch 段落：Google Fonts css2 → 下載每個 url → 改成本地檔名）
# 2. 配音：每行一支，去頭尾靜音
python3 - <<'PY'
import json,subprocess
for i,(zh,en) in enumerate(json.load(open('lines.json'))):
    subprocess.run(['python3','tts.py','zh-TW-HsiaoChenNeural',zh,f'vo3/{i:02d}.mp3','+4%'],check=True)
    subprocess.run(['ffmpeg','-y','-i',f'vo3/{i:02d}.mp3','-af','silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse','-ar','48000','-ac','1',f'vo3/{i:02d}.wav'],check=True)
PY
# 3. 配樂＋音效＋配音混音（時間軸與 film.html 同一份 cues.json）
python3 audio.py && ffmpeg -i mix_raw.wav -af loudnorm=I=-14:TP=-1.0:LRA=11 -ar 48000 mix.wav
# 4. 逐幀渲染（render.py 每一幀都回報文字是否超出安全邊界）
python3 -m http.server 8765 --bind 127.0.0.1 &
python3 render.py 1920 1080 land_v.mp4 30 && python3 render.py 1080 1920 port_v.mp4 30
# 5. 全幀檢查：黑幀、凍結幀、亮度突跳（應只有 8.45 s 與 24.8 s 兩個刻意的閃光）
python3 verify.py land_v.mp4 1920 1080 && python3 verify.py port_v.mp4 1080 1920
```
