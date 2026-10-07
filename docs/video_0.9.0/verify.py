import sys, subprocess, numpy as np, json
fn, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
w, h = W // 8, H // 8
p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', fn, '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
lum, diff, prev, n = [], [], None, 0
while True:
    b = p.stdout.read(w * h)
    if len(b) < w * h: break
    a = np.frombuffer(b, np.uint8).astype(np.float32)
    lum.append(a.mean()); diff.append(0 if prev is None else np.abs(a - prev).mean()); prev = a; n += 1
lum, diff = np.array(lum), np.array(diff)
print('frames', n, 'duration', n / 30)
black = [i for i in range(n) if lum[i] < 2.0 and not (i < 15 or i > 1777)]
print('unexpected near-black frames:', black[:20], len(black))
d = np.median(diff) ; spikes = [(i, round(i / 30, 2), round(float(diff[i]), 1)) for i in range(1, n) if diff[i] > max(12, 8 * d)]
print('median frame diff', round(float(d), 2), 'spikes(>max(12,8x median))', spikes)
frozen = [i for i in range(1, n) if diff[i] == 0]
print('identical consecutive frames:', len(frozen), frozen[:10])
print('luma min/mean/max', lum.min().round(1), lum.mean().round(1), lum.max().round(1))
