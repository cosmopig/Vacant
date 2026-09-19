"""驗收下載回來的媒體：吐出 "video" 或 "image"，不合格就非零退出。

判模態不看旗標、看檔案本身——Google Flow 由同一個提示詞框決定要生圖還是生片，
模態不是呼叫端選的。**這支是 gen_asset.sh 唯一承認的「完成」依據的一半**
（另一半是 ffmpeg 真的解出一格像素）。
"""
import json
import sys

d = json.load(open(sys.argv[1]))
vs = [s for s in d["streams"] if s.get("codec_type") == "video"]
if not vs or not vs[0].get("width") or not vs[0].get("height"):
    sys.exit("沒有可用的影像串流")
fmt = d["format"].get("format_name", "")
dur = float(d["format"].get("duration") or 0)
nb = int(vs[0].get("nb_frames") or 0)
still = ("image2" in fmt or "_pipe" in fmt
         or (vs[0].get("codec_name") in ("png", "mjpeg", "webp", "bmp") and nb <= 1))
if still:
    print("image")
else:
    if dur <= 0.5:
        sys.exit(f"影片時長不合格：{dur}")
    print("video")
