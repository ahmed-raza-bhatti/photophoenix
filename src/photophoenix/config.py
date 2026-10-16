"""Settings for PhotoPhoenix.

Precedence (later wins): built-in defaults < config.toml < .env < environment variables.

- config.toml: path from PHOTOPHOENIX_CONFIG, else ./config.toml (see config.example.toml)
- .env:        ./.env (see .env.example); simple KEY=VALUE lines
- environment: PHOTOPHOENIX_<SETTING>, e.g. PHOTOPHOENIX_WORKERS=2

Nothing machine-specific lives in the source code; everything here can be overridden.
"""
import os
import tomllib
from dataclasses import dataclass, field, fields

GREY_MODES = ("keep", "crop", "both")
PROJECT_ROOT =os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class Settings:
    # Folder holding the encrypted *.coot files (searched recursively). Empty = choose in the app.
    source_dir: str = ""
    # Where recovered photos are written (mirrors the source folder structure).
    output_dir: str = ""
    # Folders of healthy (unencrypted) JPEGs used to learn camera settings. Empty = source_dir.
    donor_dirs: list = field(default_factory=list)
    # Folders searched for untouched copies of encrypted files. Empty = source_dir.
    copy_search_dirs: list = field(default_factory=list)
    # Machine-specific working data (camera library, copy list). Git-ignored.
    data_dir: str = os.path.join(PROJECT_ROOT, "local")
    # Temporary files. Keep this on a healthy disk.
    temp_dir: str = os.path.join(PROJECT_ROOT, "local", "tmp")
    # Parallel worker processes and an upper limit for the app's spinner.
    workers: int = 4
    max_workers: int = 6
    # Pause dispatching new photos when free RAM drops below this (avoids paging to disk).
    min_free_ram_gb: float = 3.0
    # Run workers at idle CPU / very-low disk / low memory priority.
    low_priority: bool = True
    # The encrypted top of a photo is shown grey. "keep" (shows what's missing), "crop" (remove
    # the grey rows; lossless) or "both" (save the full photo and a "(cropped)" copy).
    grey_area: str = "keep"
    # Folder names (case-insensitive substrings) never searched for encrypted files.
    skip_dirs: list = field(default_factory=lambda: ["$recycle.bin", "system volume information"])

    @property
    def library_path(self):
        return os.path.join(self.data_dir, "library.json")

    @property
    def copies_path(self):
        return os.path.join(self.data_dir, "copies.csv")

    def donor_roots(self):
        return self.donor_dirs or ([self.source_dir] if self.source_dir else [])

    def copy_roots(self):
        return self.copy_search_dirs or ([self.source_dir] if self.source_dir else [])


def _read_dotenv(path):
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _coerce(name, value, default):
    if isinstance(default, bool):
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        return int(value)
    if isinstance(default, float):
        return float(value)
    if isinstance(default, list):
        if isinstance(value, list):
            return value
        return [p.strip() for p in str(value).split(";") if p.strip()]  # ';' separated in env/.env
    return str(value)


def load(config_path=None):
    s = Settings()
    defaults = {f.name: getattr(s, f.name) for f in fields(Settings)}
    path = config_path or os.environ.get("PHOTOPHOENIX_CONFIG") or os.path.join(PROJECT_ROOT, "config.toml")
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            for k, v in tomllib.load(fh).items():
                if k in defaults:
                    setattr(s, k, _coerce(k, v, defaults[k]))
    env = _read_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    env.update({k: v for k, v in os.environ.items() if k.startswith("PHOTOPHOENIX_")})
    for k, v in env.items():
        name = k[len("PHOTOPHOENIX_"):].lower() if k.startswith("PHOTOPHOENIX_") else None
        if name in defaults:
            setattr(s, name, _coerce(name, v, defaults[name]))
    s.workers = max(1, min(s.workers, s.max_workers))
    if s.grey_area not in GREY_MODES:
        s.grey_area = "keep"
    # relative paths are relative to the project folder, not to wherever the app was started
    rel = lambda p: p if not p or os.path.isabs(p) else os.path.join(PROJECT_ROOT, p)
    s.source_dir, s.output_dir = rel(s.source_dir), rel(s.output_dir)
    s.data_dir, s.temp_dir = rel(s.data_dir), rel(s.temp_dir)
    s.donor_dirs = [rel(p) for p in s.donor_dirs]
    s.copy_search_dirs = [rel(p) for p in s.copy_search_dirs]
    return s
