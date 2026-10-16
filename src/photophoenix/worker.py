"""Worker-process side of the app. Never modifies the encrypted files."""
import json, os, shutil

from . import config, copies, engine, safety

_lib, _copies, _settings = None, {}, None


def init(settings_dict):
    """Runs once in each worker process."""
    global _lib, _copies, _settings
    _settings = config.Settings(**settings_dict)
    if _settings.low_priority:
        safety.low_priority(background=True)
    safety.use_temp_dir(_settings.temp_dir)
    with open(_settings.library_path, encoding="utf-8") as fh:
        _lib = engine.Library(json.load(fh))
    _copies = copies.load(_settings.copies_path, _settings.copy_roots())


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


def _write(path, data):
    with open(path, "wb") as fh:
        fh.write(data)
