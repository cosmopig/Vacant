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

# word times (absolute) from the same TTS run
CUES = json.load(open('cues.json')); WORDS = json.load(open('words.json'))
def WT(line, k): return [c for c in CUES if c['i'] == line][0]['start'] + max(0, WORDS[line]['words'][k][0])

def pad(notes, d, cutoff=1400, det=.004, vol=.08, att=None):
    x = np.zeros(int(SR * d))
    for m in notes:
        for k in (-1, 0, 1): x += saw(midi(m), d, det * k) / 3
    x = lp(x, cutoff, 2); a = env(len(x), a=att or min(1.0, d / 3), r=d, curve=.8)
    rel = np.minimum(1, (len(x) - np.arange(len(x))) / (SR * .6)); return x * a * rel * vol
def pluck(f, d=.3, vol=.1, bright=3500):
    x = saw(f, d) * .6 + np.sign(np.sin(2 * np.pi * f * tt(d))) * .2; return lp(x, bright) * env(len(x), .002, .1) * vol
def marimba(f, d=.5, vol=.1):
    return (sine(f, d) + .25 * sine(f * 4.0, d) * env(int(SR * d), .001, .03)) * env(int(SR * d), .001, .18, 3) * vol
def kick(vol=.5):
    d = .4; t = tt(d); f = 42 + 110 * np.exp(-t * 32); ph = 2 * np.pi * np.cumsum(f) / SR
    cl = np.zeros(len(t)); cl[:480] = hp(noise(.01), 2000) * .15
    return (np.sin(ph) * env(len(t), .001, .2, 3.5) + cl) * vol
def clap(vol=.2):
    d = .25; x = bp(noise(d), 900, 5000); e = np.zeros(len(x))
    for o in (0, .011, .022): i = int(o * SR); e[i:] += env(len(x) - i, .001, .06 if o < .02 else .12)
    return x * e * vol
def hat(vol=.05, d=.05): return hp(noise(d), 8000) * env(int(SR * d), .0005, .02) * vol
def bass(f, d=.24, vol=.2): x = saw(f, d) + .5 * sine(f, d); return lp(x, 420) * env(len(x), .003, .14, 2.5) * vol

# ───────────── MUSIC ─────────────
drone_t = tt(60)
drone = (np.sin(2 * np.pi * midi(26) * drone_t) * .55 + np.sin(2 * np.pi * midi(38) * drone_t) * .25) * .07
dark_mask = ((drone_t < 8.6) | ((drone_t > 24.7) & (drone_t < 29.3))).astype(float)
dark_mask = lp(dark_mask, 4, 1)
put(music, 0, drone * (0.4 + .6 * dark_mask) + lp(rs.standard_normal(N), 300) * .04 * dark_mask)
# cold-open heartbeat + audit ticks + riser
for at in np.arange(0.2, 6.8, 1.2):
    for off, g in ((0, 1), (.22, .6)): put(music, at + off, sine(48, .45) * env(int(SR * .45), .005, .18), .35 * g)
for at in np.arange(4.3, 6.95, .25): put(sfx, at, hat(.6, .03), .18, pan=.3 * np.sin(at * 5))
def riser(d, f0=200, f1=4000, vol=.15):
    t = tt(d); f = f0 * (f1 / f0) ** (t / d); ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * .3 + bp(noise(d), 800, 9000) * (t / d) ** 2 * .7) * (t / d) ** 2.2 * vol
put(sfx, 5.6, riser(1.45, 120, 2400, .2)); put(sfx, 7.05, riser(1.4, 200, 6000, .22))

# groove: 120 BPM anchored on the logo hit (8.45)
B = .5; A0 = 8.45
PROG = [[50, 53, 57, 60, 64], [46, 50, 53, 57, 62], [53, 57, 60, 64, 67], [48, 52, 55, 60, 62]]  # Dm9 Bbmaj9 Fmaj7 C
BASSN = [38, 34, 41, 36]
def groove(t0, t1, kick_on=True, clap_on=True, energy=1.0, chords=True):
    k = 0; at = t0
    while at < t1 - 1e-6:
        bar = int(round((at - A0) / B)) // 4; beat = int(round((at - A0) / B)) % 4
        ch = PROG[bar % 4]
        if kick_on: put(music, at, kick(.42 * energy))
        if clap_on and beat in (1, 3): put(music, at, clap(.16 * energy), pan=.05)
        for s in range(4):                             # 16ths
            st = at + s * B / 4
            if st >= t1: break
            put(music, st, hat(.05 * energy * (1.4 if s == 2 else .8)), pan=.25 * np.sin(st * 7))
            m = ch[[0, 2, 4, 2][s] % len(ch)] + 12 + (12 if (beat == 3 and s == 3) else 0)
            put(music, st, pluck(midi(m), .22, .035 * energy, 2600 + 1800 * energy), pan=.4 * np.sin(st * 3.3))
        # bass: root on 1 and the "and" of 2, octave pop on 4
        if beat == 0: put(music, at, bass(midi(BASSN[bar % 4]), .4, .2 * energy))
        if beat == 1: put(music, at + B / 2, bass(midi(BASSN[bar % 4]), .22, .16 * energy))
        if beat == 3: put(music, at + B / 2, bass(midi(BASSN[bar % 4] + 12), .18, .13 * energy))
        if chords and beat == 0: put(music, at, pad(ch, B * 4 + .3, 1800, vol=.04 * energy))
        at += B; k += 1
groove(8.45, 11.0, kick_on=False, clap_on=False, energy=.7)        # logo bloom: no drums yet
groove(11.0, 24.45, energy=1.0)                                    # install → chain → panes
groove(29.25, 35.25, kick_on=False, clap_on=False, energy=.65)     # checks scanning: pulse only
groove(37.35, 51.2, energy=1.0)                                    # resolved → delivery → numbers
# freeze bed: suspended tension 24.75–29.25
bed_d = 4.5; bt = tt(bed_d)
bed = (np.sin(2 * np.pi * midi(81) * bt) + np.sin(2 * np.pi * midi(81) * 1.003 * bt)) * .012 * np.minimum(1, bt / 1.5)
bed += lp(saw(midi(38), bed_d), 380) * .05 * np.minimum(1, bt / 2); bed *= np.minimum(1, (bed_d - bt) / .2)
put(music, 24.75, bed)
for at in np.arange(25.3, 29.2, 1.0):
    for off, g in ((0, 1), (.2, .55)): put(music, at + off, sine(52, .4) * env(int(SR * .4), .004, .15), .4 * g)
# scanning beat 35.25–37.35: tension hold (only hats + sub pulses)
for at in np.arange(35.25, 37.3, B / 2): put(music, at, hat(.06), pan=.2)
# breakdown 51.3–54.6: marimba steps, one per lit bead
put(music, 51.3, pad(PROG[1], 3.5, 1100, vol=.05))
bells = [62, 64, 65, 67, 69, 72, 74, 76, 77]
for i, m in enumerate(bells): put(music, 52.9 + 1.3 * i / 8, marimba(midi(m), .8, .09), pan=-.6 + 1.2 * i / 8)
# finale
put(sfx, 54.6, riser(1.2, 150, 5000, .22))
put(music, 55.8, pad([50, 54, 57, 62, 66, 69], 4.2, 2600, vol=.09))
put(music, 55.8, pad([38, 45], 4.2, 600, vol=.1))
for i, m in enumerate([74, 78, 81, 86, 90]): put(music, 55.8 + i * .09, marimba(midi(m), 1.2, .06), pan=-.4 + .2 * i)

# ───────────── SFX ─────────────
def click(vol=.15): d = .025; return hp(noise(d), 2500) * env(int(SR * d), .0005, .006) * vol
def boom(vol=.8, d=2.4):
    t = tt(d); f = 32 + 70 * np.exp(-t * 10); ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * env(len(t), .003, .9, 3) + lp(noise(d), 500) * env(len(t), .001, .25) * .4) * vol
def whoosh(d=.6, vol=.2, lo=400, hi=6000): t = tt(d); return bp(noise(d), lo, hi) * np.sin(np.pi * t / d) ** 2 * vol
def ping(f, d=.6, vol=.12): return (sine(f, d) + .35 * sine(f * 2.76, d)) * env(int(SR * d), .002, .2, 4) * vol
def pop(f=600, vol=.2):
    d = .12; t = tt(d); fr = f * (1 + 1.8 * np.exp(-t * 60)); ph = 2 * np.pi * np.cumsum(fr) / SR
    return np.sin(ph) * env(len(t), .001, .04, 3) * vol
def clack(vol=.25): d = .08; return (bp(noise(d), 1500, 6000) * env(int(SR * d), .0005, .015) + sine(220, d) * env(int(SR * d), .001, .03)) * vol
def scribble(d=.35, vol=.1):
    x = bp(noise(d), 2500, 7000); am = .5 + .5 * np.sin(2 * np.pi * 23 * tt(d) + 3 * np.sin(2 * np.pi * 7 * tt(d)))
    return x * am * np.sin(np.pi * tt(d) / d) * vol
def glitch(d=.35, vol=.18):
    x = np.repeat(noise(d)[::8], 8)[:int(SR * d)]; x = np.round(x * 3) / 3; return hp(x, 300) * vol * (np.arange(len(x)) // 1200 % 2)
def buzz(d=.45, vol=.12):
    t = tt(d); x = np.sign(np.sin(2 * np.pi * 110 * t)) + np.sign(np.sin(2 * np.pi * 116.5 * t)); return lp(x, 1800) * env(len(t), .005, .3, 2) * vol
def shatter(vol=.2):
    x = np.zeros(int(SR * 1.2))
    for k in range(26):
        i = int(rs.uniform(0, .5) * SR); y = ping(rs.uniform(2500, 7000), .25, 1) ; x[i:i + len(y)] += y[: len(x) - i] * rs.uniform(.2, 1)
    return (x * .08 + bp(noise(1.2), 3000, 12000) * env(int(SR * 1.2), .001, .25) * .5) * vol

# A
for i in range(4): put(sfx, WT(0, 3) - .05 + i * .07, pop(900 + i * 120, .14), pan=-.15 + .1 * i)
put(sfx, WT(0, 3) + .4, ping(midi(84), .5, .06))
put(sfx, 3.55, glitch(.3, .18)); put(sfx, 3.55, boom(.25, 1.0)); put(sfx, 3.62, scribble(.4, .12))
put(sfx, 4.4, whoosh(1.2, .1, 200, 3000))
put(sfx, 7.0, sine(60, .5) * np.linspace(1, 0, int(SR * .5)) * .3)
# B: voxels land in a cascade (left → right), then the hit
for i in range(36):
    put(sfx, 7.55 + i * .022 + rs.random() * .04, clack(.05 + .03 * rs.random()), pan=-.8 + 1.6 * i / 35)
put(sfx, 8.45, boom(.95, 3.0)); put(sfx, 8.45, whoosh(1.2, .12, 2000, 12000))
put(sfx, 8.85, ping(midi(86), 1.0, .05))
for at, f in ((WT(2, 1), 700), (WT(2, 3), 900)):
    for k in range(3): put(sfx, at + k * .06, pop(f + k * 90, .12))
put(sfx, WT(2, 3) + .3, scribble(.4, .1))
# C
put(sfx, 11.05, whoosh(.5, .12, 600, 8000))
L1 = len('$ pipx install vacant-network'); L2 = len('$ vacant install')
for i in range(L1): put(sfx, 11.15 + .8 * i / L1, click(.09 + .04 * rs.random()), pan=-.4)
for i in range(L2): put(sfx, 12.15 + .45 * i / L2, click(.09 + .04 * rs.random()), pan=-.4)
put(sfx, 12.62, click(.22), pan=-.4)
for i in range(4): put(sfx, 12.85 + i * .38, pop(520 + i * 140, .22), pan=.2 + .15 * i); put(sfx, 12.88 + i * .38, ping(midi([79, 83, 86, 91][i]), .4, .04), pan=.3)
for i, k in enumerate((1, 2, 3)):
    at = WT(4, k); put(sfx, at - .05, whoosh(.25, .08, 1000, 6000)); put(sfx, at + .12, clack(.3), pan=-.4 + .4 * i); put(sfx, at + .12, kick(.2))
    put(sfx, at + .32, scribble(.3, .13), pan=-.4 + .4 * i)
put(sfx, 16.2, whoosh(.9, .18, 200, 4000))
put(sfx, 16.55, boom(.45, 1.2)); put(sfx, 16.55, pop(400, .25)); put(sfx, 16.6, scribble(.4, .08))
# D
for i in range(9):
    land = 17.65 + i * .26; put(sfx, land + .05, clack(.12)); put(sfx, land + .25, ping(midi(88 + (i % 3) * 3), .3, .03), pan=-.6 + i * .15)
put(sfx, 17.6, whoosh(2.8, .06, 300, 3000))
put(sfx, 20.45, whoosh(.6, .18, 300, 6000), pan=-.5); put(sfx, 20.57, whoosh(.6, .18, 300, 6000), pan=.5)
put(sfx, 21.95, clack(.35)); put(sfx, 22.05, ping(midi(76), 1.2, .06)); put(sfx, 22.07, ping(midi(83), 1.2, .05)); put(sfx, 22.1, ping(midi(88), 1.0, .04))
put(sfx, 23.85, riser(.9, 400, 6000, .14)); put(sfx, 23.9, shatter(.35))
# E1 freeze
put(sfx, 24.75, boom(1.0, 3.5)); put(sfx, 24.75, whoosh(.5, .2, 100, 3000))
tape = saw(110, .6) * np.linspace(1, 0, int(SR * .6)) ** 2; put(sfx, 24.7, lp(tape, 900), .06)
put(sfx, 26.55, whoosh(.6, .1, 500, 6000))
lz = tt(2.0); put(sfx, 27.0, np.sin(2 * np.pi * (600 + 300 * lz / 2) * lz) * np.sin(np.pi * lz / 2) * .03)
# E2 checks
put(sfx, 29.2, whoosh(.5, .2, 1000, 12000)); put(sfx, 29.22, ping(midi(91), .6, .04))
for i, k in enumerate((0, 3, 6, 9, 12)): put(sfx, WT(9, k) - .05, pop(450 + i * 110, .24), pan=-.2 + .1 * i)
for i in range(4): put(sfx, 35.15 + i * .05, ping(midi(90), .2, .03))
put(sfx, 35.35, buzz(.5, .14)); put(sfx, 35.35, boom(.3, 1.0))
put(sfx, 36.0, whoosh(.7, .18, 300, 5000), pan=-.5); put(sfx, 35.95, scribble(.5, .1), pan=-.4)
put(sfx, 36.55, whoosh(.45, .12, 1500, 9000), pan=-.6)
put(sfx, 36.85, pop(700, .22), pan=-.5)
put(sfx, 37.0, whoosh(.4, .14, 400, 6000))
for i, m in enumerate([74, 78, 81, 86]): put(sfx, 37.35 + i * .06, ping(midi(m), 1.0, .05))
# F
put(sfx, 38.65, whoosh(.8, .16, 200, 6000))
for i, k in enumerate((3, 6, 9)): put(sfx, WT(11, k), pop(600 + i * 150, .2)); put(sfx, WT(11, k) + .02, ping(midi([81, 84, 88][i]), .4, .03))
# G
t_ = tt(1.6); put(sfx, 44.3, np.sin(2 * np.pi * np.cumsum(300 + 500 * t_ / 1.6) / SR) * np.sin(np.pi * t_ / 1.6) * .05)
for i in range(30): put(sfx, 44.3 + i * .053, click(.05))
put(sfx, 46.1, scribble(.6, .12)); put(sfx, 46.4, ping(midi(86), .6, .04))
put(sfx, 48.1, whoosh(.6, .14, 400, 7000))
for i in range(14): put(sfx, 48.6 + i * .057, click(.06))
put(sfx, 49.15, scribble(.35, .1)); put(sfx, 49.45, boom(.5, 1.4)); put(sfx, 49.45, pop(350, .28)); put(sfx, 49.6, scribble(.45, .12))
put(sfx, 49.9, ping(midi(88), .8, .04))
# H
put(sfx, 51.3, whoosh(.8, .1, 200, 4000))
for i in range(9): put(sfx, 51.45 + i * .06, pop(800 + i * 60, .1), pan=-.6 + 1.2 * i / 8)
put(sfx, WT(14, 8), scribble(.5, .1))
for i in range(40): put(sfx, 54.75 + i * .018 + rs.random() * .04, clack(.04 + .03 * rs.random()), pan=rs.uniform(-.8, .8))
put(sfx, 55.8, boom(.9, 4.0)); put(sfx, 55.8, whoosh(1.5, .12, 3000, 14000))
put(sfx, 57.5, pop(500, .15)); put(sfx, 57.5, ping(midi(93), 1.5, .03))
# ───────────── VO ─────────────
cues = json.load(open('cues.json'))
vo = np.zeros(N)
for c in cues:
    if c.get('visual'): continue
    sr, x = wavfile.read(f"../video/vo3/{c['i']:02d}.wav"); x = x.astype(np.float64) / 32768
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
