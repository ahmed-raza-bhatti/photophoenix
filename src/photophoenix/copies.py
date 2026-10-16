"""Find untouched originals of STOP/Djvu-encrypted files (read-only).

An encrypted file is the original plus a 334-byte trailer, and everything after the first
150 KB is still the original bytes. So a candidate whose size is (encrypted - 334) and whose
later bytes match is a verified original: recovery is then a plain copy (100%).

Only the folders you configure (copy_search_dirs, default: the source folder) are searched.
"""
import csv, os, time

from .engine import TRAILER, ENC_END

PLAIN_FROM = ENC_END + 4096
COLUMNS = ["encrypted", "original_copy", "match", "size"]


def walk(root, skip=()):
    stack = [root]
    while stack:
        d = stack.pop()
        if any(s in d.lower() for s in skip):
            continue
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            yield e.path, e.name, e.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError:
            pass


def same_tail(enc, cand, size):
    """Compare two plaintext windows (middle and end) of the original-sized region."""
    try:
        with open(enc, "rb") as a, open(cand, "rb") as b:
            for off in {max(PLAIN_FROM, size // 2), max(PLAIN_FROM, size - 65536)}:
                if off >= size: continue
                a.seek(off); b.seek(off); n = min(65536, size - off)
                if a.read(n) != b.read(n): return False
        return True
    except OSError:
        return False


def find(enc_root, search_roots, out_csv, skip=(), progress=print, stats=None):
    """Index encrypted files under enc_root, look for originals under search_roots, write out_csv.
    If `stats` is a dict, it receives total / found / verified counts."""
    t0 = time.time()
    enc = [(p, n[:-5], s - TRAILER) for p, n, s in walk(enc_root, skip) if n.lower().endswith(".coot") and s > TRAILER]
    by_size = {}
    for p, name, size in enc:
        by_size.setdefault(size, []).append((p, name))
    progress(f"{len(enc)} encrypted files indexed; searching {', '.join(search_roots)}")
    found, seen = {}, 0
    for root in search_roots:
        for path, name, size in walk(root, skip):
            seen += 1
            if seen % 100000 == 0:
                progress(f"  checked {seen:,} files, {len(found)} originals so far ({time.time() - t0:.0f}s)")
            if name.lower().endswith(".coot") or size not in by_size:
                continue
            for encp, encname in by_size[size]:
                if encp in found: continue
                if size > PLAIN_FROM + 4096:
                    if same_tail(encp, path, size):
                        found[encp] = (path, "verified-bytes", size)
                elif name.lower() == encname.lower():
                    found[encp] = (path, "name+size (too small to verify)", size)
    os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(COLUMNS)
        for k, (p, how, s) in sorted(found.items()): w.writerow([k, p, how, s])
    progress(f"{len(found)} of {len(enc)} encrypted files have an untouched copy -> {out_csv}")
    if stats is not None:
        stats.update(total=len(enc), found=len(found),
                     verified=sum(1 for v in found.values() if v[1] == "verified-bytes"))
    return found


def load(csv_path, allowed_roots):
    """{normalised encrypted path: original path}, keeping only originals inside allowed_roots."""
    if not os.path.exists(csv_path):
        return {}
    roots = [os.path.normcase(os.path.abspath(r)) for r in allowed_roots]
    out = {}
    with open(csv_path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            orig = os.path.normcase(os.path.abspath(r["original_copy"]))
            if any(orig == root or orig.startswith(root.rstrip(os.sep) + os.sep) for root in roots):
                out[os.path.normcase(os.path.abspath(r["encrypted"]))] = r["original_copy"]
    return out
