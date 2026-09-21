"""frames.json ＋ jpg → mp4，1280x720 / crf 28（repo 裡的證據不該是 15MB）。"""
import json, os, subprocess, sys

d, out = sys.argv[1], sys.argv[2]
fr = json.load(open(os.path.join(d, 'frames.json')))
lst = os.path.join(d, 'concat2.txt')
with open(lst, 'w') as f:
    for i, e in enumerate(fr):
        f.write("file '%s'\n" % e['name'])
        if i + 1 < len(fr):
            f.write('duration %.4f\n' % max(0.02, fr[i + 1]['t'] - e['t']))
    f.write("file '%s'\n" % fr[-1]['name'])
env = dict(os.environ, DYLD_FALLBACK_LIBRARY_PATH='/usr/local/Cellar/x265/4.1/lib')
cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'concat2.txt',
       '-vf', 'fps=20,scale=1280:-2,format=yuv420p', '-c:v', 'libx264',
       '-crf', '28', '-preset', 'veryfast', '-movflags', '+faststart',
       os.path.abspath(out)]
r = subprocess.run(cmd, cwd=d, env=env, capture_output=True, text=True)
if r.returncode != 0:
    sys.stderr.write(r.stderr[-2500:])
    sys.exit(r.returncode)
span = fr[-1]['t'] - fr[0]['t']
print('%s  frames=%d  span=%.1fs  capture_fps=%.2f  size=%dKB'
      % (os.path.basename(out), len(fr), span, (len(fr) - 1) / span,
         os.path.getsize(out) // 1024))
