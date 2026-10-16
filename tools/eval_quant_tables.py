"""Usage: python tools/eval_quant_tables.py HEALTHY_PHOTO_DIR [...]

How tightly does the 'blocks must stay within 0..255' rule pin a photo's DC quant step?

Uses healthy photos (true tables known), hides the top ~150 KB like the ransomware does,
and compares the largest step that keeps the visible blocks in range with the true step.
"""
import os, random, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from photophoenix import safety, fastjpeg as fj

safety.low_priority(background=True)

def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


random.seed(11)
pool = []
ROOTS = sys.argv[1:]  # folders of healthy JPEGs (true tables known)
if not ROOTS: sys.exit("usage: python tools/eval_quant_tables.py HEALTHY_PHOTO_DIR [...]")
for root in ROOTS:
    if not os.path.isdir(root): continue
    for dp, _, fs in os.walk(root):
        pool += [os.path.join(dp, f) for f in fs if f.lower().endswith((".jpg", ".jpeg"))]
random.shuffle(pool)
rows = []
for p in pool:
    if len(rows) >= 150: break
    try:
        d = _read(p)
        if len(d) < 400_000: continue
        D = fj.Donor(d, p)
        if D.dri or len(D.scan) != 3: continue
        buf = fj.destuff(d[D.scan_start:d.rfind(b"\xff\xd9")])
        m, st, _, (dcs, fl) = fj.decode(buf, D.layout(), 3)
        if st != "eof" or m != D.total: continue
    except Exception:
        continue
    lost = int(m * min(0.8, 153_600 / len(d)))
    per = [len(dcs[c]) // m for c in range(3)]
    ys = np.asarray(dcs[0][lost * per[0]:], float)
    cb = np.asarray(dcs[1][lost * per[1]:], float); cr = np.asarray(dcs[2][lost * per[2]:], float)
    qy, qc = D.dc_quant(0), D.dc_quant(1)
    sy = np.percentile(ys, 99.9) - np.percentile(ys, 0.1)
    ay = max(abs(np.percentile(ys, 99.9)), abs(np.percentile(ys, 0.1)))  # absolute (restart files)
    bound_rel = 255 * 8 / max(sy, 1)          # align/infer: only the spread is known
    bound_abs = 128 * 8 / max(ay, 1)          # restart: absolute values known
    rows.append((qy, bound_rel / qy, bound_abs / qy, sy * qy / 8))
r = np.array(rows)
print(f"{len(r)} healthy photos")
for name, col in (("spread rule (align/infer)", 1), ("absolute rule (restart)", 2)):
    x = r[:, col]
    print(f"{name}: bound/true  median {np.median(x):.2f} | within 1.25x: {np.mean(x <= 1.25):.0%} | within 1.5x: {np.mean(x <= 1.5):.0%} "
          f"| over 2x: {np.mean(x > 2):.0%} | violations (<0.97): {np.mean(x < 0.97):.0%}")
print(f"true brightness spread of visible part (levels): median {np.median(r[:,3]):.0f}, 10th pct {np.percentile(r[:,3],10):.0f}")
