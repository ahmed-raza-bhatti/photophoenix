"""Recover a random sample of encrypted photos from some folders and print per-photo results.

Usage: python tools/sample_test.py OUTPUT_DIR ENCRYPTED_DIR [ENCRYPTED_DIR ...] [--per-folder N]
Uses the camera library from config (data_dir/library.json) and gentle worker settings.
"""
import argparse, json, os, random, sys, time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from stopgap import config, engine, safety



def _write(path, data):
    with open(path, "wb") as fh:
        fh.write(data)

_lib = None


def init(lib_path, temp_dir):
    global _lib
    safety.low_priority(background=True); safety.use_temp_dir(temp_dir)
    _lib = engine.Library(json.load(open(lib_path, encoding="utf-8")))


def work(args):
    path, out = args
    t = time.time()
    try:
        r = engine.recover(path, _lib)
    except Exception as ex:
        return path, "failed", str(ex)[:60], 0, 0, time.time() - t
    dest = os.path.join(out, os.path.basename(os.path.dirname(path)), os.path.basename(path)[:-5])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    _write(dest, r["jpg"])
    return path, r["status"], f"{r['method']} {r['dims']}", r["frac"], r["q"], time.time() - t


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("output"); ap.add_argument("folders", nargs="+")
    ap.add_argument("--per-folder", type=int, default=6); a = ap.parse_args()
    s = config.load(); random.seed(3)
    files = []
    for f in a.folders:
        cs = [os.path.join(f, n) for n in os.listdir(f) if n.lower().endswith((".jpg.coot", ".jpeg.coot"))]
        files += random.sample(cs, min(a.per_folder, len(cs)))
    t0 = time.time()
    with ProcessPoolExecutor(s.workers, initializer=init, initargs=(s.library_path, s.temp_dir)) as ex:
        res = list(ex.map(work, [(f, a.output) for f in files]))
    for p, st, how, frac, q, dt in res:
        print(f"{st:7s} {os.path.basename(p)[:50]:50s} {how:26s} {frac:5.0%} q={q:4.2f} {dt:5.1f}s")
    ok = sum(r[1] == "ok" for r in res); rv = sum(r[1] == "review" for r in res)
    print(f"\n{len(res)} photos in {time.time() - t0:.0f}s: {ok} ok, {rv} review, {len(res) - ok - rv} failed")
