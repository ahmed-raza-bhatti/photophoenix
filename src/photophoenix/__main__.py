"""Command line.

  python -m photophoenix                         open the desktop app
  python -m photophoenix recover FILE.coot [-o OUT.jpg]
  python -m photophoenix build-library [DIR ...] learn camera settings from healthy JPEGs (adds to library)
  python -m photophoenix find-copies             look for untouched copies of encrypted files
"""
import argparse, json, multiprocessing, os, sys

from . import __version__, config, copies, engine, safety


def main(argv=None):
    ap = argparse.ArgumentParser(prog="photophoenix", description="Recover photos from STOP/Djvu ransomware.")
    ap.add_argument("--version", action="version", version=f"PhotoPhoenix {__version__} (engine {engine.ENGINE_VERSION})")
    ap.add_argument("--config", help="path to config.toml")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("recover", help="recover one encrypted photo")
    r.add_argument("file"); r.add_argument("-o", "--output")
    b = sub.add_parser("build-library", help="learn camera settings from healthy JPEGs")
    b.add_argument("dirs", nargs="*", help="folders or drives of healthy photos (default: donor_dirs / source_dir)")
    b.add_argument("--replace", action="store_true", help="start a new library instead of adding to the existing one")
    sub.add_parser("find-copies", help="find untouched copies of encrypted files (read-only)")
    a = ap.parse_args(argv)

    s = config.load(a.config)
    if s.low_priority:
        safety.low_priority(background=a.cmd is not None)
    safety.use_temp_dir(s.temp_dir)

    if a.cmd is None:
        from .app import main as app_main
        return app_main()
    if a.cmd == "build-library":
        roots = a.dirs or s.donor_roots()
        if not roots:
            sys.exit("Give folders of healthy JPEGs, or set donor_dirs / source_dir in config.toml.")
        new = engine.scan_library(roots, [s.data_dir.lower()] + [d.lower() for d in s.skip_dirs],
                                  progress=lambda n: print(f"  {n} JPEG headers read", flush=True))
        old = []
        if not a.replace and os.path.exists(s.library_path):
            with open(s.library_path, encoding="utf-8") as fh: old = json.load(fh)
        merged, added = engine.merge_library(old, new)
        os.makedirs(s.data_dir, exist_ok=True)
        with open(s.library_path, "w", encoding="utf-8") as fh: json.dump(merged, fh)
        print(f"{added} new camera/size types learned; library now has {len(merged)} -> {s.library_path}")
    elif a.cmd == "find-copies":
        if not s.source_dir:
            sys.exit("Set source_dir (the folder with *.coot files) in config.toml or PHOTOPHOENIX_SOURCE_DIR.")
        st = {}
        copies.find(s.source_dir, s.copy_roots(), s.copies_path, skip=[d.lower() for d in s.skip_dirs], stats=st)
        if st.get("found"):
            print(f"{st['found']} of {st['total']} encrypted files will be restored complete from copies "
                  f"({st['verified']} verified byte-for-byte, {st['found'] - st['verified']} by name and size only).")
        else:
            print("No untouched copies found (the most common result). Recovery will repair photos from "
                  "the surviving data. Add backup folders to copy_search_dirs to search more places.")
    elif a.cmd == "recover":
        if not os.path.exists(s.library_path):
            sys.exit(f"No camera library yet: run 'python -m photophoenix build-library DIR' first ({s.library_path}).")
        with open(s.library_path, encoding="utf-8") as fh:
            lib = engine.Library(json.load(fh))
        twin = copies.load(s.copies_path, s.copy_roots()).get(os.path.normcase(os.path.abspath(a.file)))
        res = engine.recover(a.file, lib, twin)
        out = a.output or a.file[:-len(".coot")] if a.file.lower().endswith(".coot") else a.output
        out = out or a.file + ".recovered.jpg"
        if os.path.exists(out) and not a.output:
            out = os.path.splitext(out)[0] + ".recovered.jpg"
        if res["method"] == "copy":
            import shutil; shutil.copyfile(twin, out)
        else:
            with open(out, "wb") as fh: fh.write(res["jpg"])
        print(f"{res['status']}: {res['method']} {res.get('dims', '')} ~{res['frac']:.0%} of the image -> {out}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
