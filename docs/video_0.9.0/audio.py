"""Score + sound design + VO mix, all synced to film.html's timeline. Output: mix.wav (48k stereo)."""
import json, numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000; DUR = 60.0; N = int(SR * DUR)
rs = np.random.default_rng(7)
music = np.zeros((N, 2)); sfx = np.zeros((N, 2))

def tt(d): return np.arange(int(SR * d)) / SR
def midi(m): return 440 * 2 ** ((m - 69) / 12)
def env(n, a=.01, r=.3, curve=4.0):
    t = np.arange(n) / SR; e = np.minimum(1, t / max(a, 1e-4))
    return e * np.exp(-curve * np.maximum(0, t - a) / max(r, 1e-4))
def lp(x, fc, order=2):
    b, a = signal.butter(order, min(fc, SR / 2 - 100) / (SR / 2)); return signal.lfilter(b, a, x, axis=0)
def hp(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), 'high'); return signal.lfilter(b, a, x, axis=0)
def bp(x, lo, hi):
    b, a = signal.butter(2, [lo / (SR / 2), hi / (SR / 2)], 'band'); return signal.lfilter(b, a, x, axis=0)
def put(buf, at, x, gain=1.0, pan=0.0):
    i = int(at * SR)
    if x.ndim == 1: x = np.stack([x * np.sqrt(.5 * (1 - pan)), x * np.sqrt(.5 * (1 + pan))], 1) * np.sqrt(2)
    j = min(N, i + len(x));
    if j > i: buf[i:j] += x[: j - i] * gain
def saw(f, d, det=0.0):
    t = tt(d); ph = (f * (1 + det)) * t; return 2 * (ph - np.floor(ph + .5))
def sine(f, d): return np.sin(2 * np.pi * f * tt(d))
def noise(d): return rs.standard_normal(int(SR * d))

# ── reverb (synthetic stereo IR) ──
def reverb(x, secs=2.8, wet=.35, damp=4500):
    n = int(SR * secs); t = np.arange(n) / SR
    ir = np.stack([lp(rs.standard_normal(n), damp) * np.exp(-3.2 * t / secs * 2) for _ in range(2)], 1)
    ir /= np.sqrt((ir ** 2).sum(0))
    y = np.stack([signal.fftconvolve(x[:, k], ir[:, k])[: len(x)] for k in range(2)], 1)
    return x * (1 - wet) + y * wet * 1.2

# ───────────── MUSIC ─────────────
# drone: D1/D2 with slow filter breathing, throughout (ducked at freeze handled by automation)
def pad(notes, d, cutoff=1400, det=.004, vol=.08):
    x = np.zeros(int(SR * d))
    for m in notes:
        f = midi(m)
        for k in (-1, 0, 1): x += saw(f, d, det * k) / 3
    x = lp(x, cutoff, 2); a = env(len(x), a=min(1.2, d / 3), r=d, curve=.8)
    rel = np.minimum(1, (len(x) - np.arange(len(x))) / (SR * .8))
    return x * a * rel * vol

drone_t = tt(60)
drone = (np.sin(2 * np.pi * midi(26) * drone_t) * .55 + np.sin(2 * np.pi * midi(38) * drone_t) * .25)
drone *= .09 * (0.75 + .25 * np.sin(2 * np.pi * .11 * drone_t))
dn = lp(rs.standard_normal(N), 300) * .05 * (0.5 + .5 * np.sin(2 * np.pi * .07 * drone_t))
put(music, 0, drone + dn, 1.0)

# cold-open pulse (heartbeat sub) 0.0–7.0
for k, at in enumerate(np.arange(0.2, 6.8, 1.2)):
    for off, g in ((0, 1), (.22, .6)):
        b = sine(48, .45) * env(int(SR * .45), .005, .18)
        put(music, at + off, b, .35 * g)
# ticking 8ths 4.3–7.0 (the audit grind) + riser into implosion
for at in np.arange(4.3, 6.95, .3125):
    put(sfx, at, hp(noise(.03), 6000) * env(int(SR * .03), .001, .012), .10, pan=.3 * np.sin(at * 5))
def riser(d, f0=200, f1=4000, vol=.15):
    t = tt(d); f = f0 * (f1 / f0) ** (t / d); ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * .3 + bp(noise(d), 800, 9000) * (t / d) ** 2 * .7
    return x * (t / d) ** 2.2 * vol
put(sfx, 5.4, riser(1.65, 120, 2400, .22))

# progression from logo: Dm9 → Bbmaj7 → Fmaj7 → C(add9); bar = 0.625*4 = 2.5 s, 2 bars per chord
CH = {'Dm9': [50, 53, 57, 60, 64], 'Bb': [46, 50, 53, 57, 62], 'F': [53, 57, 60, 64, 67], 'C': [48, 55, 60, 62, 64],
      'Dmaj': [50, 54, 57, 62, 66, 69]}
prog = ['Dm9', 'Bb', 'F', 'C']
seq = []
t0 = 8.45
while t0 < 24.6:
    for c in prog:
        if t0 >= 24.6: break
        d = min(3.3, 24.75 - t0); seq.append((t0, c, d)); t0 += 3.3
for at, c, d in seq: put(music, at, pad(CH[c], d + .6, 1600, vol=.06), 1.0, pan=0)
# arpeggio 16ths 11.0–24.7 (BPM 96 → 16th = .15625)
beat = .625
def pluck(f, d=.35, vol=.12, bright=3500):
    x = saw(f, d) * .6 + np.sign(np.sin(2 * np.pi * f * tt(d))) * .2
    return lp(x, bright) * env(len(x), .003, .12) * vol
def chord_at(t):
    for at, c, d in seq:
        if at <= t < at + d: return CH[c]
    return CH['Dm9']
k = 0
for at in np.arange(11.0, 24.7, beat / 4):
    ns = chord_at(at); m = ns[[0, 2, 4, 2, 1, 3, 4, 3][k % 8] % len(ns)] + 12
    vol = .045 + .025 * ((k % 4) == 0)
    put(music, at, pluck(midi(m), vol=vol, bright=2500 + 1500 * min(1, (at - 11) / 8)), 1, pan=.35 * np.sin(k * 1.3))
    k += 1
# soft kick on beats 12.25–24.7, hats on offbeats
def kick(vol=.5):
    d = .35; t = tt(d); f = 45 + 90 * np.exp(-t * 35); ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * env(len(t), .002, .16) * vol
for at in np.arange(12.25, 24.6, beat): put(music, at, kick(.32), 1)
for at in np.arange(12.25 + beat / 2, 24.6, beat): put(music, at, hp(noise(.05), 7000) * env(int(SR * .05), .001, .02), .05, pan=.2)

# FREEZE 24.75: reverse swell before, tape-stop, then suspended tension (high tone + low drone + heartbeat)
rev = (bp(noise(.9), 2000, 12000) * np.linspace(0, 1, int(SR * .9)) ** 3)
put(sfx, 23.85, rev, .28)
# tension bed 24.75–35.4
bed_d = 35.4 - 24.75; bt = tt(bed_d)
bed = (np.sin(2 * np.pi * midi(81) * bt) * .5 + np.sin(2 * np.pi * midi(81) * 1.003 * bt) * .5) * .018 * np.minimum(1, bt / 2)
bed += lp(saw(midi(38), bed_d), 400) * .05 * np.minimum(1, bt / 3)
bed *= np.minimum(1, (bed_d - bt) / .3)
put(music, 24.75, bed, 1)
for at in np.arange(25.3, 35.3, 1.0):  # heartbeat
    for off, g in ((0, 1), (.2, .55)): put(music, at + off, sine(52, .4) * env(int(SR * .4), .004, .15), .4 * g)
# data blips during scan 27.3–35.3
for i, at in enumerate(np.arange(27.3, 35.2, .125)):
    f = 1800 + 600 * ((i * 7) % 5)
    put(sfx, at, sine(f, .03) * env(int(SR * .03), .001, .01), .025, pan=np.sin(i) * .6)
# resolution after fix 37.35 → Fmaj / C / Dm across delivery + evidence (build)
seq2 = [(37.35, 'F', 3.3), (40.65, 'C', 3.0), (43.65, 'Bb', 3.3), (46.95, 'F', 2.2), (49.15, 'C', 2.2)]
for at, c, d in seq2: put(music, at, pad(CH[c], d + .6, 1900, vol=.06), 1)
k = 0
for at in np.arange(43.65, 51.2, beat / 4):
    ns = dict((a, CH[c]) for a, c, d in seq2)
    cur = CH['Bb'] if at < 46.95 else (CH['F'] if at < 49.15 else CH['C'])
    m = cur[[0, 2, 4, 2, 1, 3, 4, 3][k % 8] % len(cur)] + 12
    put(music, at, pluck(midi(m), vol=.05 + .02 * (k % 4 == 0), bright=4200), 1, pan=.35 * np.sin(k * 1.3)); k += 1
for at in np.arange(43.65, 51.2, beat): put(music, at, kick(.36), 1)
for at in np.arange(43.65 + beat / 2, 51.2, beat): put(music, at, hp(noise(.05), 7000) * env(int(SR * .05), .001, .02), .06, pan=-.2)
# breakdown 51.3–54.6: sparse bell notes, one per lit step (9 ascending)
bells = [62, 64, 65, 67, 69, 72, 74, 76, 77]
for i, m in enumerate(bells):
    at = 52.9 + (54.2 - 52.9) * i / 8
    x = (sine(midi(m), 1.6) + .3 * sine(midi(m) * 2.01, 1.6)) * env(int(SR * 1.6), .002, .5, 3)
    put(music, at, x, .06, pan=-.6 + 1.2 * i / 8)
put(music, 51.3, pad(CH['Bb'], 3.6, 1100, vol=.05), 1)
# finale: riser → hit → D major bloom, tail to 60
put(sfx, 54.6, riser(1.2, 150, 5000, .22))
put(music, 55.8, pad(CH['Dmaj'], 4.2, 2600, vol=.09), 1)
put(music, 55.8, pad([38, 45], 4.2, 600, vol=.10), 1)

# ───────────── SFX ─────────────
def click(vol=.15):
    d = .025; return hp(noise(d), 2500) * env(int(SR * d), .0005, .006) * vol
def boom(vol=.8, d=2.4):
    t = tt(d); f = 32 + 70 * np.exp(-t * 10); ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * env(len(t), .003, .9, 3) + lp(noise(d), 500) * env(len(t), .001, .25) * .4) * vol
def whoosh(d=.6, vol=.2, lo=400, hi=6000):
    t = tt(d); x = bp(noise(d), lo, hi); e = np.sin(np.pi * t / d) ** 2; return x * e * vol
def ping(f, d=.6, vol=.12):
    return (sine(f, d) + .35 * sine(f * 2.76, d)) * env(int(SR * d), .002, .2, 4) * vol
def glitch(d=.35, vol=.18):
    x = noise(d); step = 1 + (np.arange(len(x)) // 900) % 7; x = np.repeat(x[::8], 8)[: len(x)]
    x = np.round(x * 3) / 3; return hp(x, 300) * vol * (np.arange(len(x)) // 1200 % 2)
def buzz(d=.45, vol=.12):
    t = tt(d); x = np.sign(np.sin(2 * np.pi * 110 * t)) + np.sign(np.sin(2 * np.pi * 116.5 * t)); return lp(x, 1800) * env(len(t), .005, .3, 2) * vol

# A: typing 做完了。 (0.7–1.25), done chip, glitches
for i in range(4): put(sfx, .7 + i * .1375, click(.22), pan=-.1 + .07 * i)
put(sfx, 1.45, ping(midi(84), .5, .07))
put(sfx, 2.95, glitch(.3, .16)); put(sfx, 3.55, glitch(.45, .22)); put(sfx, 3.55, boom(.25, 1.0))
# implosion 7.05 → logo assembly whoosh, hit at 8.45
put(sfx, 7.0, sine(60, .5) * np.linspace(1, 0, int(SR * .5)) * .3)
put(sfx, 7.05, whoosh(1.3, .22, 300, 9000))
for i in range(40):  # particles landing shimmer
    put(sfx, 7.4 + i * .022 + rs.random() * .05, ping(midi(96 + (i % 5) * 2), .15, .012), pan=rs.uniform(-.8, .8))
put(sfx, 8.45, boom(.9, 3.0)); put(sfx, 8.45, whoosh(1.2, .1, 2000, 12000))
put(sfx, 8.9, ping(midi(86), 1.2, .05)); put(sfx, 9.15, ping(midi(74), .6, .04)); put(sfx, 9.75, ping(midi(81), .8, .05))
# C: terminal typing, install checks, strikes, zero-config thump
L1 = len('$ pipx install vacant-network'); L2 = len('$ vacant install')
for i in range(L1): put(sfx, 11.15 + .8 * i / L1, click(.10 + .04 * rs.random()), pan=rs.uniform(-.2, .2))
for i in range(L2): put(sfx, 12.15 + .45 * i / L2, click(.10 + .04 * rs.random()), pan=rs.uniform(-.2, .2))
put(sfx, 12.6, click(.25))  # enter
for i in range(4): put(sfx, 12.85 + i * .38, ping(midi([79, 83, 86, 91][i]), .5, .06), pan=-.5 + i * .33)
for i in range(3): put(sfx, 15.05 + i * .3, sine(90, .2) * env(int(SR * .2), .002, .08) * .2)
for i in range(3): put(sfx, 15.45 + i * .35, whoosh(.25, .22, 1500, 9000), pan=-.4 + .4 * i)
put(sfx, 16.55, boom(.45, 1.4)); put(sfx, 16.55, ping(midi(86), .9, .05))
# D: chain blocks land + seal pings; scan; equality chime; Δ=0
for i in range(9):
    land = 17.65 + i * .26
    put(sfx, land + .05, kick(.18)); put(sfx, land + .3, ping(midi(88 + (i % 3) * 3), .3, .03), pan=-.6 + i * .15)
put(sfx, 20.3, whoosh(.7, .16, 600, 8000))
put(sfx, 21.6, ping(midi(76), 1.2, .06)); put(sfx, 21.62, ping(midi(83), 1.2, .05))
put(sfx, 22.3, ping(midi(88), .8, .04))
# E: slam + freeze
put(sfx, 24.75, boom(1.0, 3.5)); put(sfx, 24.75, whoosh(.5, .2, 100, 3000))
tape = saw(110, .6) * np.linspace(1, 0, int(SR * .6)) ** 2; put(sfx, 24.7, lp(tape, 900), .05)
put(sfx, 26.6, whoosh(.6, .1, 500, 6000))
for i, at in enumerate([29.3, 30.27, 31.43, 32.6, 33.76]):
    put(sfx, at, whoosh(.3, .08, 2000, 9000)); put(sfx, at + .05, click(.15))
for i in range(5): put(sfx, 35.15 + i * .05, ping(midi(90), .2, .025))
put(sfx, 35.35, buzz(.5, .14)); put(sfx, 35.35, boom(.3, 1.0))
put(sfx, 36.0, whoosh(.8, .16, 300, 5000))
put(sfx, 36.9, whoosh(.4, .08, 3000, 12000))
for i, m in enumerate([74, 78, 81, 86]): put(sfx, 37.35 + i * .06, ping(midi(m), 1.0, .05))
# F: card + sections
put(sfx, 38.6, whoosh(.7, .14, 300, 7000))
for i, at in enumerate([39.95, 40.9, 41.85]): put(sfx, at, ping(midi([81, 84, 88][i]), .5, .04)); put(sfx, at, click(.1))
# G: counters
for i in range(26): put(sfx, 44.3 + i * .05, click(.05), pan=-.3)
for i in range(26): put(sfx, 44.32 + i * .05, click(.06), pan=.3)
put(sfx, 46.4, ping(midi(86), .6, .04))
put(sfx, 48.1, whoosh(.6, .12, 400, 7000))
for i in range(14): put(sfx, 48.6 + i * .057, click(.06))
put(sfx, 49.45, boom(.55, 1.5)); put(sfx, 49.45, ping(midi(81), 1.0, .05))
put(sfx, 49.9, ping(midi(88), .8, .04))
# H
put(sfx, 51.3, whoosh(.8, .1, 200, 4000))
put(sfx, 55.8, boom(.9, 4.0)); put(sfx, 55.8, whoosh(1.5, .12, 3000, 14000))
for i in range(30): put(sfx, 54.7 + i * .03 + rs.random() * .04, ping(midi(96 + (i % 5) * 2), .15, .01), pan=rs.uniform(-.8, .8))
put(sfx, 57.4, ping(midi(93), 1.5, .03))

# ───────────── VO ─────────────
cues = json.load(open('cues.json'))
vo = np.zeros(N)
for c in cues:
    if c.get('visual'): continue
    sr, x = wavfile.read(f"vo3/{c['i']:02d}.wav"); x = x.astype(np.float64) / 32768
    assert sr == SR
    i = int(c['start'] * SR); vo[i:i + len(x)] += x[: N - i]
vo = hp(vo, 80)
# gentle presence + compression-ish
vo = vo * 1.0
voS = np.stack([vo, vo], 1)
voS = reverb(voS, 1.2, .08, 6000)

# ───────────── mix ─────────────
music = reverb(music, 3.2, .35)
sfx = reverb(sfx, 2.2, .22)
# global automation: fade-in 0–0.5, freeze dip for music 24.75–29 already sparse; end fade 59.0–60
t = np.arange(N) / SR
fade = np.minimum(1, t / .5) * np.clip((60 - t) / 1.0, 0, 1)
# duck music under VO
envv = np.abs(vo); envv = lp(envv, 6, 1); envv = envv / (envv.max() + 1e-9)
duck = 1 - .55 * np.clip(envv * 3, 0, 1)
duck = lp(duck, 3, 1)
mix = music * (duck * fade)[:, None] * 1.0 + sfx * fade[:, None] * .9 + voS * 1.6
peak = np.abs(mix).max(); mix = mix / peak * .89
wavfile.write('mix_raw.wav', SR, (mix * 32767).astype(np.int16))
np.save('stems_info.npy', np.array([peak]))
print('peak before norm', peak)
act = envv > .15
bg = (music * (duck * fade)[:, None] + sfx * fade[:, None] * .9)
r = lambda x: 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)
print('VO-active: vo %.1f dB, bed %.1f dB, SNR %.1f dB' % (r(voS[act] * 1.6), r(bg[act]), r(voS[act] * 1.6) - r(bg[act])))
for a, b in [(0, 7), (7, 11), (11, 17.5), (17.5, 24.6), (24.6, 35.4), (35.4, 43.6), (43.6, 51.3), (51.3, 60)]:
    s = slice(int(a * SR), int(b * SR)); print(f'{a:5.1f}-{b:4.1f}  bed {r(bg[s]):6.1f} dB')
