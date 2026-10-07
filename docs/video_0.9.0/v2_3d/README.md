# v2：3D 動態版（Apple 式 3D motion graphics）

和 v1 同一份配音、字幕、時間軸（`../cues.json`），畫面改成：
- **真 3D**（three.js r170，headless Chromium 的 SwiftShader 軟體渲染）：VACANT 的 92 顆體素、agent 圖示、簽章鏈方塊、請求玻璃板、五個檢查膠囊、交件說明卡、長條、珠串
- **逐字動態字**：用 edge-tts 的 WordBoundary（`words.json`）讓字跟著配音一個字一個字彈出來
- **手繪塗鴉**（劃掉、圈起、箭頭、底線）與 **毛玻璃 UI**（字幕、終端機、安裝指令都會模糊背後的 3D 畫面）
- **開燈敘事**：暗（agent 說做完了、沒人查）→ Vacant 出現時亮起 → 「做完了」那一刻回到暗（時間停住）→ 檢查開始時再亮

## 重建
```bash
cd v2_3d && npm install three@0.170.0 && ln -s ../fonts fonts   # 字型同 v1
cp ../cues.json . && python3 -m http.server 8766 --bind 127.0.0.1 &
python3 render2.py 1920 1080 land.mp4 30 && python3 render2.py 1080 1920 port.mp4 30   # 每支約 1 小時
python3 audio2.py && ffmpeg -i mix_raw.wav -af loudnorm=I=-14:TP=-1.0:LRA=11 -ar 48000 mix2.wav
python3 ../verify.py land.mp4 1920 1080 && python3 corner.py land.mp4 1920 1080
```
`START=<frame> NFRAMES=<n>` 可只重渲一段再接回去。

⚠ 已知的坑（已修）：兩張疊在一起的 canvas（WebGL＋2D）每幀截圖時，Chromium 會把舊的圖層混進來
（11.27–11.57 s 出現殘影與暗角）。解法是每幀把 3D 畫面畫進同一張不透明的 2D canvas、只截那一張；
`corner.py` 逐幀檢查亮場的四角亮度，用來抓這種問題。
