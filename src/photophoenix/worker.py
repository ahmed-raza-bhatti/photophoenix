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


def work(path, src, out, prev_output=None):
    """Recover one photo. prev_output: an older engine's result for it, replaced by the new one."""
    rel = os.path.relpath(path, src)
    twin = _copies.get(os.path.normcase(os.path.abspath(path)))
    if twin and not os.path.exists(twin):
        twin = None
    try:
        r = engine.recover(path, _lib, twin)
    except Exception as ex:
        return dict(file=rel, status="failed", detail=str(ex)[:100], ver=engine.ENGINE_VERSION)
    sub = "" if r["status"] == "ok" else "_needs_review"
    dest = os.path.join(out, sub, rel[:-len(".coot")])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if r["method"] == "copy":
        shutil.copyfile(twin, dest)
    else:
        with open(dest, "wb") as fh:
            fh.write(r["jpg"])
    # only remove a file this app wrote earlier, inside the output folder, now superseded
    if prev_output and os.path.normcase(prev_output) != os.path.normcase(dest) \
            and os.path.normcase(os.path.abspath(prev_output)).startswith(os.path.normcase(os.path.abspath(out)) + os.sep) \
            and os.path.isfile(prev_output):
        os.remove(prev_output)
    return dict(file=rel, status=r["status"], method=r["method"], percent=round(r["frac"] * 100),
                quality=round(r["q"], 2), dims=r["dims"], output=dest, ver=engine.ENGINE_VERSION)
