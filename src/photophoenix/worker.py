"""Worker-process side of the app. Never modifies the encrypted files."""
import json, os, shutil, time

from . import config, copies, engine, safety, video, video_index

_lib, _copies, _settings, _video_refs = None, {}, None, []
_folder_ref, _folder_misses = {}, {}   # per folder: reference that worked / videos with no match
_progress_q, _last_emit = None, {}       # per-file progress for the app's "Working on" panel


def init(settings_dict, progress_q=None):
    """Runs once in each worker process."""
    global _lib, _copies, _settings, _video_refs, _progress_q
    _progress_q = progress_q
    _settings = config.Settings(**settings_dict)
    _video_refs = video_index.load_refs(_settings.video_refs_path)
    if _settings.low_priority:
        safety.low_priority(background=True)
    safety.use_temp_dir(_settings.temp_dir)
    try:
        with open(_settings.library_path, encoding="utf-8") as fh:
            _lib = engine.Library(json.load(fh))
    except FileNotFoundError:  # "videos only": no camera library needed
        _lib = engine.Library([])
    _copies = copies.load(_settings.copies_path, _settings.copy_roots())


def _emit(rel, step, frac=None, force=False):
    """Tell the app what this worker is doing (at most twice a second per file)."""
    if _progress_q is None:
        return
    now = time.monotonic()
    if not force and now - _last_emit.get(rel, 0) < 0.5:
        return
    _last_emit[rel] = now
    try:
        _progress_q.put_nowait((os.getpid(), rel, step, frac))
    except Exception:
        pass


def cropped_name(path):
    stem, ext = os.path.splitext(path)
    return f"{stem} (cropped){ext}"


def _inside(path, folder):
    return os.path.normcase(os.path.abspath(path)).startswith(os.path.normcase(os.path.abspath(folder)) + os.sep)


def work(path, src, out, prev=None, grey="keep"):
    """Recover one photo. prev: the earlier result for it (its files are replaced).
    grey: "keep" the grey (lost) area, "crop" it off, or save "both"."""
    rel = os.path.relpath(path, src)
    twin = _copies.get(os.path.normcase(os.path.abspath(path)))
    if twin and not os.path.exists(twin):
        twin = None
    if video.is_video(path):
        return _work_video(path, rel, out, prev, twin)
    _emit(rel, "restoring from untouched copy" if twin else "repairing photo", None, force=True)
    try:
        r = engine.recover(path, _lib, twin, crop=grey in ("crop", "both"))
    except Exception as ex:
        return dict(file=rel, status="failed", detail=str(ex)[:100], ver=engine.ENGINE_VERSION, grey=grey)
    sub = "" if r["status"] == "ok" else "_needs_review"
    dest = os.path.join(out, sub, rel[:-len(".coot")])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    written, cropped_out, note = [], None, ""
    if r["method"] == "copy":
        shutil.copyfile(twin, dest); written.append(dest)
    else:
        crop = r.get("jpg_cropped")
        if grey == "crop" and crop:
            _write(dest, crop); written.append(dest); cropped_out = dest; note = "cropped"
        else:
            _write(dest, r["jpg"]); written.append(dest)
            if grey == "both" and crop:
                cropped_out = cropped_name(dest); _write(cropped_out, crop); written.append(cropped_out)
                note = "full + cropped copy"
            elif grey != "keep" and r["method"] not in ("header",):
                note = "grey area kept (could not crop this one)"
    # remove files an earlier run wrote that are now superseded (only inside the output folder)
    for old in (prev or {}).get("output"), (prev or {}).get("cropped_output"):
        if old and _inside(old, out) and os.path.normcase(old) not in {os.path.normcase(w) for w in written} \
                and os.path.isfile(old):
            os.remove(old)
    return dict(file=rel, status=r["status"], method=r["method"], percent=round(r["frac"] * 100),
                quality=round(r["q"], 2), dims=r["dims"], output=dest, cropped_output=cropped_out,
                grey=grey, grey_note=note, ver=engine.ENGINE_VERSION)


def _work_video(path, rel, out, prev, twin):
    dest = os.path.join(out, rel[:-len(".coot")])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    say = lambda step, frac=None: _emit(rel, step, frac)
    say("starting video", None)
    try:
        if twin:
            _emit(rel, "restoring from untouched copy", None, force=True)
            shutil.copyfile(twin, dest)
            r = dict(status="ok", method="copy", frac=1.0, q=1.0, dims="", damaged_seconds=0)
        else:
            try:
                r = video.recover_video(path, dest, say)
            except ValueError as ex:
                if "index was at the start" not in str(ex):
                    raise
                # index encrypted: rebuild it from the frames, using a reference video's settings.
                # Remember per folder what worked (try it first) and stop trying everything in
                # folders where earlier videos matched no reference.
                folder = os.path.dirname(os.path.abspath(path)).lower()
                try:
                    r = video_index.rebuild(path, dest, _video_refs, temp_dir=_settings.temp_dir,
                                            prefer=_folder_ref.get(folder),
                                            max_tries=5 if _folder_misses.get(folder, 0) >= 2 else None,
                                            progress=say)
                    _folder_ref[folder] = r.pop("ref")
                except ValueError:
                    _folder_misses[folder] = _folder_misses.get(folder, 0) + 1
                    raise
    except Exception as ex:
        if os.path.exists(dest) and not twin:
            try: os.remove(dest)  # don't leave a half-written video behind
            except OSError: pass
        return dict(file=rel, status="failed", detail=str(ex)[:160], ver=engine.ENGINE_VERSION, kind="video",
                    refs=len(_video_refs))  # retried when reference videos are added
    old = (prev or {}).get("output")
    if old and _inside(old, out) and os.path.normcase(old) != os.path.normcase(dest) and os.path.isfile(old):
        os.remove(old)
    note = r.get("note") or (f"first ~{r['damaged_seconds']:g} s damaged" if r.get("damaged_seconds") else "")
    return dict(file=rel, status=r["status"], method=r["method"], percent=round(r["frac"] * 100),
                quality=r["q"], dims=r["dims"], output=dest, grey_note=note, kind="video",
                ver=engine.ENGINE_VERSION)


def _write(path, data):
    with open(path, "wb") as fh:
        fh.write(data)
