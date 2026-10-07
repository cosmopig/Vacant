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
def riser(d, f0=200, f1=4000, vol=.15):
    t = tt(d); f = f0 * (f1 / f0) ** (t / d); ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * .3 + bp(noise(d), 800, 9000) * (t / d) ** 2 * .7) * (t / d) ** 2.2 * vol
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

A = json.load(open('anchors.json'))
def snare(vol=.2): d = .18; return (bp(noise(d), 1200, 7000) * env(int(SR * d), .001, .07) + sine(190, d) * env(int(SR * d), .001, .04) * .5) * vol
def stab(notes, vol=.08, d=.5, bright=3000):
    x = np.zeros(int(SR * d))
    for m in notes: x += saw(midi(m), d, .003) + saw(midi(m), d, -.003)
    return lp(x, bright) * env(len(x), .003, .18, 3) * vol / len(notes)

MIN = [[50, 53, 57, 60, 64], [46, 50, 53, 57, 62], [53, 57, 60, 64, 67], [48, 52, 55, 60, 62]]; MINB = [38, 34, 41, 36]
MAJ = [[53, 57, 60, 64, 67], [48, 52, 55, 60, 64], [46, 50, 53, 57, 62], [53, 57, 60, 65, 69]]; MAJB = [41, 36, 34, 41]
B = .5
def groove(t0, t1, anchor, prog, bassn, kick_on=True, clap_on=True, energy=1.0, e1=None, chords=True, hats=True, plucks=True, bright=None):
    at = t0
    while at < t1 - 1e-6:
        n = int(round((at - anchor) / B)); bar, beat = n // 4, n % 4
        e = energy if e1 is None else lerp_(energy, e1, (at - t0) / max(1e-6, t1 - t0))
        ch = prog[bar % 4]
        if kick_on: put(music, at, kick(.42 * e))
        if clap_on and beat in (1, 3): put(music, at, clap(.16 * e), pan=.05)
        for s in range(4):
            st = at + s * B / 4
            if st >= t1: break
            if hats: put(music, st, hat(.05 * e * (1.4 if s == 2 else .8)), pan=.25 * np.sin(st * 7))
            if plucks:
                m = ch[[0, 2, 4, 2][s] % len(ch)] + 12 + (12 if (beat == 3 and s == 3) else 0)
                put(music, st, pluck(midi(m), .22, .034 * e, (bright or 2600) + 1800 * e), pan=.4 * np.sin(st * 3.3))
        if beat == 0: put(music, at, bass(midi(bassn[bar % 4]), .4, .2 * e))
        if beat == 1: put(music, at + B / 2, bass(midi(bassn[bar % 4]), .22, .16 * e))
        if beat == 3: put(music, at + B / 2, bass(midi(bassn[bar % 4] + 12), .18, .13 * e))
        if chords and beat == 0: put(music, at, pad(ch, B * 4 + .3, 1800, vol=.04 * e))
        at += B
def lerp_(a, b, x): return a + (b - a) * min(1, max(0, x))
def roll(t0, t1, vol=.16, start_iv=.25, end_iv=.0625):
    at = t0
    while at < t1:
        x = (at - t0) / (t1 - t0); put(music, at, snare(vol * (.35 + .65 * x)), pan=.1); at += start_iv + (end_iv - start_iv) * x

# ══════════ MUSIC: the emotional arc ══════════
T = tt(60)
# 1) cold open — unease (0–7)
drone = (np.sin(2 * np.pi * midi(26) * T) * .55 + np.sin(2 * np.pi * midi(38) * T) * .25) * .07
dmask = lp(((T < 8.5) | ((T > 24.7) & (T < 29.3)) | ((T > 35.3) & (T < 37.4))).astype(float), 4, 1)
silence = np.ones(N)
for a, b in ((3.38, 3.5), (7.05, 7.5), (24.22, 24.75), (35.33, 35.36)):  # music holds its breath
    i, j = int(a * SR), int(b * SR); silence[i:j] = 0
silence = lp(silence, 25, 1)
put(music, 0, drone * (0.35 + .65 * dmask) + lp(rs.standard_normal(N), 300) * .035 * dmask)
for at in (0.35, 1.55):
    for off, g in ((0, 1), (.22, .6)): put(music, at + off, sine(48, .45) * env(int(SR * .45), .005, .18), .4 * g)
sw = tt(.9); put(music, 2.55, np.sin(2 * np.pi * (880 + 220 * sw / .9) * sw) * (sw / .9) ** 2 * .02)      # a question forming
put(sfx, 3.05, bp(noise(.5), 2000, 12000) * np.linspace(0, 1, int(SR * .5)) ** 3, .22)                    # reverse swell into the glitch
# audit grind: ticks accelerate, riser into the implosion
at, k = 4.3, 0
while at < 6.95:
    put(sfx, at, hat(.7, .03), .2, pan=.3 * np.sin(k)); x = (at - 4.3) / 2.65; at += .32 - .24 * x; k += 1
for at in np.arange(4.4, 6.9, .6): put(music, at, sine(46, .4) * env(int(SR * .4), .004, .16), .3)
put(sfx, 5.5, riser(1.5, 120, 2600, .22))
# 2) the light comes on (7.5–11)
put(sfx, 7.5, riser(.95, 200, 7000, .24))
groove(8.45, 10.5, 8.45, MIN, MINB, kick_on=False, clap_on=False, energy=.6, hats=False)
roll(10.5, 11.0, .2)                                                                                     # fill into the groove
# 3) confidence (11–14.95), then stop-time questions on the keycaps
groove(11.0, 14.95, 8.45, MIN, MINB, energy=1.0)
for i, k in enumerate(('k1', 'k2', 'k3')):
    put(music, A[k], kick(.45)); put(music, A[k], clap(.18)); put(music, A[k], stab([62 + 2 * i, 65 + 2 * i, 69 + 2 * i], .14, .45))
put(music, A['none'], stab([50, 57, 62, 65, 69], .2, 1.2, 4000)); put(music, A['none'], bass(midi(38), .6, .3))
groove(A['none'], 23.45, 8.45, MIN, MINB, energy=1.05, e1=1.15, bright=3200)
# 4) build → silence → slam
roll(23.45, 24.2, .22, .125, .03); put(sfx, 23.5, riser(.72, 300, 8000, .2))
hold = tt(.5); put(music, 24.25, np.sin(2 * np.pi * midi(93) * hold) * .012 * np.sin(np.pi * hold / .5))
# 5) freeze — suspense (24.75–29.2)
bt = tt(4.45); bed = (np.sin(2 * np.pi * midi(81) * bt) + np.sin(2 * np.pi * midi(81) * 1.004 * bt)) * .011 * np.minimum(1, bt / 1.2)
bed += lp(saw(midi(38), 4.45), 360) * .05 * np.minimum(1, bt / 2); bed *= np.minimum(1, (4.45 - bt) / .25); put(music, 24.78, bed)
for at in np.arange(25.4, 29.1, 1.0):
    for off, g in ((0, 1), (.2, .55)): put(music, at + off, sine(52, .4) * env(int(SR * .4), .004, .15), .45 * g)
# 6) five questions — rising stakes (29.3–35.3)
qs = [A['q1'], A['q2'], A['q3'], A['q4'], A['q5']]
groove(29.25, 35.3, 29.25, MIN, MINB, kick_on=False, clap_on=False, energy=.55, e1=.95, chords=False)
for i, q in enumerate(qs):
    put(music, q, stab([57 + 2 * i, 62 + 2 * i, 65 + 2 * i], .12, .4, 3500)); put(music, q, kick(.25 + .05 * i))
at, k = 29.3, 0
while at < 35.25: put(sfx, at, hat(.6, .025), .12, pan=.2 * np.sin(k)); at += .25 - .17 * (at - 29.3) / 6; k += 1
put(sfx, 33.9, riser(1.4, 300, 6000, .2))
# 7) failure: hard stop, then tension until it is fixed
for at in np.arange(35.9, 37.3, .5): put(music, at, sine(44, .35) * env(int(SR * .35), .004, .15), .4)
for at in np.arange(35.6, 37.3, .25): put(sfx, at, click(.08), pan=.3)
put(sfx, 36.8, riser(.55, 400, 5000, .14))
# 8) resolution → warmth → pride (37.35–51.25), major key
put(music, 37.35, stab([53, 60, 65, 69, 72, 76], .26, 1.6, 4500)); put(music, 37.35, bass(midi(41), .9, .3))
groove(37.35, 38.6, 37.35, MAJ, MAJB, energy=1.0)
groove(38.6, 43.6, 37.35, MAJ, MAJB, clap_on=False, energy=.75)
groove(43.6, 47.5, 37.35, MAJ, MAJB, energy=.85, e1=1.2, bright=3400)
put(sfx, 46.85, riser(.71, 400, 7000, .18))
put(music, A['b2'], stab([53, 60, 65, 69, 72], .2, .9, 5000)); put(music, A['b2'], kick(.5))
groove(47.56, 51.25, 37.35, MAJ, MAJB, energy=1.05)
# 9) intimacy (51.6–55) — almost nothing, a bead lights per note
put(music, 51.55, pad([46, 53, 57, 62], 3.6, 1000, vol=.05))
bells = [62, 64, 65, 67, 69, 72, 74, 76, 77]
for i, m in enumerate(bells): put(music, A['g2'] + (A['g4'] - .1 - A['g2']) * i / 8, marimba(midi(m), .9, .085), pan=-.6 + 1.2 * i / 8)
# 10) triumph (55.85–60)
put(sfx, 54.95, riser(.9, 150, 6000, .24))
put(music, 55.85, pad([50, 54, 57, 62, 66, 69], 4.1, 2200, vol=.065)); put(music, 55.85, pad([38, 45], 4.1, 600, vol=.09))
for i, m in enumerate([74, 78, 81, 86, 90]): put(music, 55.85 + i * .09, marimba(midi(m), 1.2, .06), pan=-.4 + .2 * i)
put(music, A['g4'] + 3.4, marimba(midi(93), 1.5, .04))
put(music, 8.45, pad([38, 50, 57, 62, 65, 69], 1.6, 2000, vol=.08, att=.05))

# ══════════ SFX (synced to picture) ══════════
for i in range(3): put(sfx, A['done1'] + i * .07, pop(700 + i * 140, .1))
put(sfx, 3.55, glitch(.3, .2)); put(sfx, 3.55, boom(.3, 1.0)); put(sfx, 3.62, scribble(.4, .12))
put(sfx, 7.0, sine(60, .5) * np.linspace(1, 0, int(SR * .5)) * .3)
for i in range(36): put(sfx, 7.55 + i * .022 + rs.random() * .04, clack(.05 + .03 * rs.random()), pan=-.8 + 1.6 * i / 35)
put(sfx, 8.45, boom(1.0, 3.0)); put(sfx, 8.45, whoosh(1.2, .12, 2000, 12000))
for at, f in ((A['inst1'], 700), (A['inst2'], 900)):
    for k in range(3): put(sfx, at - .2 + k * .05, pop(f + k * 90, .08))
put(sfx, A['inst2'] + .75, scribble(.4, .08))
put(sfx, 11.05, whoosh(.5, .12, 600, 8000))
for i in range(12): put(sfx, 11.05 + i * .025, click(.08), pan=-.4)
for i, a in enumerate(A['ag']): put(sfx, a, pop(520 + i * 140, .22), pan=.2 + .15 * i); put(sfx, a + .03, ping(midi([79, 83, 86, 91][i]), .4, .04), pan=.3)
for i, k in enumerate(('k1', 'k2', 'k3')): put(sfx, A[k] - .05, whoosh(.25, .08, 1000, 6000)); put(sfx, A[k] + .1, clack(.3), pan=-.4 + .4 * i); put(sfx, A[k] + .32, scribble(.3, .13), pan=-.4 + .4 * i)
put(sfx, A['none'], boom(.6, 1.4)); put(sfx, A['none'], pop(400, .25)); put(sfx, A['none'] + .05, whoosh(.9, .16, 200, 4000))
for i in range(9): land = 17.65 + i * .26; put(sfx, land + .05, clack(.12)); put(sfx, land + .25, ping(midi(88 + (i % 3) * 3), .3, .03), pan=-.6 + i * .15)
put(sfx, 20.45, whoosh(.6, .18, 300, 6000), pan=-.5); put(sfx, 20.57, whoosh(.6, .18, 300, 6000), pan=.5)
put(sfx, 21.95, clack(.35)); put(sfx, 22.05, ping(midi(76), 1.2, .06)); put(sfx, 22.07, ping(midi(83), 1.2, .05)); put(sfx, 22.1, ping(midi(88), 1.0, .04))
put(sfx, 23.9, shatter(.3))
put(sfx, 24.75, boom(1.1, 3.8))
tape = saw(110, .6) * np.linspace(1, 0, int(SR * .6)) ** 2; put(sfx, 24.7, lp(tape, 900), .06)
lz = tt(2.0); put(sfx, 27.0, np.sin(2 * np.pi * (600 + 300 * lz / 2) * lz) * np.sin(np.pi * lz / 2) * .03)
put(sfx, 29.2, whoosh(.5, .2, 1000, 12000))
for i, q in enumerate(qs): put(sfx, q - .03, pop(450 + i * 110, .24), pan=-.2 + .1 * i)
put(sfx, 35.35, buzz(.55, .16)); put(sfx, 35.35, boom(.45, 1.2))
put(sfx, 36.0, whoosh(.7, .18, 300, 5000), pan=-.5); put(sfx, 35.95, scribble(.5, .1), pan=-.4)
put(sfx, 36.55, whoosh(.45, .12, 1500, 9000), pan=-.6); put(sfx, 36.85, pop(700, .22), pan=-.5); put(sfx, 37.0, whoosh(.4, .14, 400, 6000))
for i, m in enumerate([74, 78, 81, 86]): put(sfx, 37.35 + i * .06, ping(midi(m), 1.0, .05))
put(sfx, 38.65, whoosh(.8, .16, 200, 6000))
for i, k in enumerate(('n1', 'n2', 'n3')): put(sfx, A[k], pop(600 + i * 150, .2)); put(sfx, A[k] + .02, ping(midi([81, 84, 88][i]), .4, .03))
for i in range(40): put(sfx, A['b0'] + i * .055, click(.045))
put(sfx, A['b2'] + .1, scribble(.5, .12))
put(sfx, 48.1, whoosh(.6, .14, 400, 7000))
for i in range(14): put(sfx, 48.6 + i * .057, click(.06))
put(sfx, 49.15, scribble(.35, .1)); put(sfx, 49.45, boom(.5, 1.4)); put(sfx, 49.45, pop(350, .28)); put(sfx, 49.6, scribble(.45, .12)); put(sfx, 49.9, ping(midi(88), .8, .04))
put(sfx, 51.6, whoosh(.8, .08, 200, 4000))
for i in range(9): put(sfx, 51.7 + i * .06, pop(800 + i * 60, .08), pan=-.6 + 1.2 * i / 8)
put(sfx, A['g4'], scribble(.5, .1))
for i in range(40): put(sfx, 55.25 + i * .018 + rs.random() * .04, clack(.04 + .03 * rs.random()), pan=rs.uniform(-.8, .8))
put(sfx, 55.85, boom(1.0, 4.0)); put(sfx, 55.85, whoosh(.6, .12, 3000, 14000))
put(sfx, 58.0, pop(500, .14)); put(sfx, 58.0, ping(midi(93), 1.5, .03))

# ══════════ VOICE ══════════
def compress(x, thr=.12, ratio=3.0):
    e = np.sqrt(lp(x ** 2, 30, 1).clip(1e-12)); g = np.where(e > thr, (thr + (e - thr) / ratio) / e, 1.0); return x * lp(g, 40, 1)
def narr_fx(x):
    x = hp(x, 90); x = x / (np.sqrt((x[np.abs(x) > .02] ** 2).mean()) + 1e-9) * .12; x = x + .35 * bp(x, 2500, 6000); return compress(x)
def agent_fx(x):
    y = bp(x, 280, 3600); y = np.tanh(y * 3.2) / 2.2
    d = int(.007 * SR); y2 = np.r_[np.zeros(d), y[:-d]]; y = y + .35 * y2
    am = 1 + .12 * np.sign(np.sin(2 * np.pi * 70 * np.arange(len(y)) / SR)); return compress(y * am)
PL = json.load(open('place.json'))
voD = np.zeros((N, 2)); voW = np.zeros((N, 2)); env_sig = np.zeros(N)
for p in PL:
    isag = p['id'].startswith('agent')
    sr, x = wavfile.read('agent_done.wav' if isag else f"sent/{p['id']}.wav"); x = x.astype(np.float64) / 32768
    x = agent_fx(x) if isag else narr_fx(x)
    i = int(p['at'] * SR); j = min(N, i + len(x)); seg = x[: j - i]
    env_sig[i:j] += np.abs(seg)
    wet = .1                                   # one room for every narrator line
    pan = -.12 if isag else 0
    st = np.stack([seg * np.sqrt(.5 * (1 - pan)), seg * np.sqrt(.5 * (1 + pan))], 1) * np.sqrt(2)
    voD[i:j] += st * (1 - wet); voW[i:j] += st * wet
voS = voD + reverb(voW, 2.4, 1.0, 6500)

music = reverb(music, 3.2, .33) * silence[:, None]; sfx = reverb(sfx, 2.2, .22) * (0.3 + .7 * silence)[:, None]
fade = np.minimum(1, T / .4) * np.clip((60 - T) / 1.0, 0, 1)
envv = lp(env_sig, 6, 1); envv /= envv.max() + 1e-9
duck = lp(1 - .68 * np.clip(envv * 3, 0, 1), 3, 1)
mix = music * (duck * fade)[:, None] + sfx * fade[:, None] * .9 + voS * 2.1
AUTO = [(0, -9), (4.2, -8), (6.9, -4), (7.04, -10), (8.4, -7), (8.47, 2), (9.2, -1), (10.9, -1), (14.9, -1), (16.95, 2), (17.6, 0), (23.4, 0), (24.2, 1.5),
        (24.74, 0), (24.78, 3), (25.6, -7), (29.2, -6), (29.32, -7), (35.25, 0), (35.4, -1), (37.3, -4), (37.36, 1.5), (38.8, -1), (43.6, -2),
        (47.56, 2), (51.2, 0), (51.65, -8), (54.95, -7), (55.86, 3), (56.5, 0), (59.0, 0), (60, 0)]
kt = np.array([k for k, _ in AUTO]); kd = np.array([d for _, d in AUTO])
gain_db = np.interp(T, kt, kd); master = 10 ** (lp(gain_db, 12, 1) / 20)
sduck = lp(1 - .45 * np.clip(envv * 3, 0, 1), 8, 1)
mix = (music * (duck * fade)[:, None] + sfx * (sduck * fade)[:, None] * .9) * master[:, None] + voS * 2.1 * fade[:, None]
wavfile.write('vo_stem.wav', SR, (voS / np.abs(voS).max() * .8 * 32767).astype(np.int16))
mix /= np.abs(mix).max() / .89
wavfile.write('mix_raw.wav', SR, (mix * 32767).astype(np.int16))
act = envv > .12; bg = music * (duck * fade)[:, None] + sfx * fade[:, None] * .9
r = lambda x: 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)
print('SNR under VO %.1f dB' % (r(voS[act] * 2.1) - r(bg[act])))
for a_, b_ in ((9.2, 10.9), (56.6, 58.7)):
    s_ = slice(int(a_ * SR), int(b_ * SR)); print('  SNR %.2f-%.2f: %.1f dB' % (a_, b_, r(voS[s_] * 2.1) - r(bg[s_])))
sec = []
for a, b, name in [(0, 7.05, 'unease'), (7.05, 7.5, 'breath'), (8.45, 11, 'light'), (11, 14.95, 'groove'), (14.95, 16.95, 'stop-time'), (17, 23.4, 'groove+'), (24.22, 24.75, 'silence'),
                   (24.75, 29.2, 'freeze'), (29.3, 35.3, 'questions'), (35.4, 37.3, 'tension'), (37.35, 43.6, 'resolve'), (43.6, 51.2, 'pride'), (51.6, 55, 'intimate'), (55.85, 59, 'triumph')]:
    s = slice(int(a * SR), int(b * SR)); print(f'{name:10s} {a:5.2f}-{b:5.2f} full mix {r(mix[s]):6.1f} dB')
