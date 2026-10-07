import sys, subprocess, numpy as np
fn, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
w, h = W // 8, H // 8
p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', fn, '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
vals = []
while True:
    b = p.stdout.read(w * h)
    if len(b) < w * h: break
    a = np.frombuffer(b, np.uint8).reshape(h, w); vals.append((a[2:6, 2:6].mean(), a[h//2-3:h//2+3, w//2-3:w//2+3].mean()))
v = np.array(vals); t = np.arange(len(v)) / 30
light = ~(((t < 8.5)) | ((t > 24.6) & (t < 29.3)))
bad = [(round(float(t[i]),2), round(float(v[i,0]),0)) for i in range(len(v)) if light[i] and v[i,0] < 200]
print(fn, 'light frames with dark corner (<200):', len(bad)); print(bad[:12], bad[-6:])
