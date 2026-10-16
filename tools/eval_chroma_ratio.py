"""Usage: python tools/eval_chroma_ratio.py HEALTHY_PHOTO_DIR [...]

Per-camera chroma-ratio decision: pool evidence from k photos of the same camera (simulated by
drawing k photos at random), compared with per-photo decisions."""
import os, random, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from photophoenix import safety, fastjpeg as fj, engine

safety.low_priority(background=True)

def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


random.seed(21)
pool = []
ROOTS = sys.argv[1:]  # folders of healthy JPEGs
if not ROOTS: sys.exit("usage: python tools/eval_chroma_ratio.py HEALTHY_PHOTO_DIR [...]")
for root in ROOTS:
    if os.path.isdir(root):
        for dp, _, fs in os.walk(root):
            pool += [os.path.join(dp, f) for f in fs if f.lower().endswith((".jpg", ".jpeg"))]
random.shuffle(pool)
ev = {1: [], 2: []}
for p in pool:
    if len(ev[1]) >= 160: break
    try:
        d = _read(p)
        if len(d) < 300_000: continue
        D = fj.Donor(d, p)
        if D.dri or len(D.scan) != 3 or D.dc_quant(0) != D.dc_quant(1): continue
        buf = fj.destuff(d[D.scan_start:d.rfind(b"\xff\xd9")])
        m, st, _, (dcs, fl) = fj.decode(buf, D.layout(), 3)
        if st != "eof" or m != D.total: continue
    except Exception:
        continue
    lost = int(m * min(0.8, 153_600 / len(d)))
    per = [len(dcs[c]) // m for c in range(3)]
    sub = [list(dcs[c][lost * per[c]:]) for c in range(3)]; subf = [list(fl[c][lost * per[c]:]) for c in range(3)]
    for ratio in (1, 2):
        s2 = [sub[0]] + [[int(round(v / ratio)) for v in sub[c]] for c in (1, 2)]
        ev[ratio].append(engine.chroma_ratio_evidence(D, s2, subf))
rng = np.random.default_rng(0)
for k in (1, 3, 5, 8, 12):
    line = []
    for ratio in (1, 2):
        e = np.array(ev[ratio]); picks = []
        for _ in range(2000):
            idx = rng.choice(len(e), k, replace=False)
            picks.append(engine.camera_chroma_ratio(e[idx]))
        picks = np.array(picks)
        line.append(f"true {ratio}: right {np.mean(picks == ratio):5.1%}")
    print(f"{k:2d} photos per camera -> " + " | ".join(line))
