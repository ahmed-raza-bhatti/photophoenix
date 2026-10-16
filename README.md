# PhotoPhoenix

**Recover your photos from STOP/Djvu ransomware — no ransom, no key.**

STOP/Djvu is one of the most widespread ransomware families aimed at home users. It
renames files with extensions like `.coot`, `.djvu`, `.boop`, `.mzlq` and leaves a
`_readme.txt` asking for about $490–$980. Files hit by its newer variants with an *online*
key cannot be decrypted by anyone except the attackers.

But STOP/Djvu only encrypts the **first 150 KB** of each file. In a typical 1–4 MB phone
photo, 85–97% of the image data is still there, untouched. PhotoPhoenix rebuilds a viewable
JPEG from that surviving data. It works entirely offline, on your own computer.

| What you get | When |
|---|---|
| **100%** of the photo | an untouched copy exists somewhere (backup, phone transfer, chat download) — PhotoPhoenix finds and verifies it |
| **Nearly 100%** | the photo's own JPEG header happens to lie beyond the encrypted part |
| **Most of the photo, exact colours** | the camera used JPEG restart markers (common on older phones) |
| **Most of the photo, estimated colours** | everything else with enough data — the top strip that was encrypted stays grey |
| **Nothing** | files smaller than ~150 KB were encrypted completely |

> PhotoPhoenix does **not** decrypt anything and never contacts the attackers or any server.
> If you are a victim: don't pay, keep the encrypted files (keys sometimes leak and the free
> [Emsisoft STOP/Djvu decryptor](https://www.emsisoft.com/ransomware-decryption/stop-djvu/)
> may help with *offline* keys), and scan your PC — cracked software "activators" are a
> common infection route.

## Quick start (Windows)

1. Install [Python 3.11+](https://www.python.org/downloads/) (tick "Add python.exe to PATH").
2. Download or clone this repository, then in its folder run:
   ```
   pip install -r requirements.txt
   ```
3. Double-click **`Run PhotoPhoenix.bat`**.
4. Choose the folder with the encrypted files and an empty folder for the results, press **Start**.

The first run learns your cameras' JPEG settings from healthy photos (see below), then
recovers every `*.jpg.coot` / `*.jpeg.coot` file. Pause, Resume and Stop at any time;
starting again with the same folders picks up where it left off.

Linux / macOS: `pip install -r requirements.txt`, then `PYTHONPATH=src python -m photophoenix`.

## What you need to provide

- **The encrypted files.** Work on a copy if you can; PhotoPhoenix never modifies them anyway.
- **Some healthy, unencrypted JPEGs**, ideally from the same phones or cameras (photos you
  sent to others, cloud backups, an old SD card, a folder the ransomware missed). PhotoPhoenix
  learns each camera's JPEG settings from them. Without any, it can still infer most
  settings from the data itself, just less reliably.
- **A computer with Python 3.11+.** No GPU, no accounts, no API keys, no paid services.
  About 200 MB of RAM per worker; 4 workers by default.

## Settings

Defaults work for most people. To change them, copy `config.example.toml` to `config.toml`
(or `.env.example` to `.env`) and edit. Every setting can also be an environment variable
`PHOTOPHOENIX_<NAME>`. The important ones:

| Setting | Meaning |
|---|---|
| `source_dir` / `output_dir` | default folders shown in the app |
| `donor_dirs` | folders of healthy JPEGs to learn cameras from |
| `copy_search_dirs` | folders searched for untouched copies — nothing else is ever searched |
| `workers`, `min_free_ram_gb`, `low_priority` | how hard PhotoPhoenix works your computer |

## Command line

```
python -m photophoenix                          # the desktop app
python -m photophoenix build-library DIR [DIR]  # learn cameras from healthy JPEGs
python -m photophoenix find-copies              # find untouched copies (source_dir, copy_search_dirs)
python -m photophoenix recover FILE.jpg.coot -o OUT.jpg
```
(Set `PYTHONPATH=src`, or `pip install -e .` once and use the `photophoenix` command.)

## Privacy

PhotoPhoenix runs offline and reads only the folders you choose. The camera library
(`local/library.json`) and copy list (`local/copies.csv`) contain paths to your photos; they
stay on your computer and are excluded from git.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — components, data flow, stack, how to extend
- [docs/methods.md](docs/methods.md) — the recovery techniques and why they work
- [docs/djvu-format.md](docs/djvu-format.md) — what STOP/Djvu does to a file, measured
- [docs/validation.md](docs/validation.md) — how each technique was tested, with results
- [docs/safety.md](docs/safety.md) — running gently on old or failing hardware
- [CHANGELOG.md](CHANGELOG.md) · [CONTRIBUTING.md](CONTRIBUTING.md) · [COMMERCIAL.md](COMMERCIAL.md)

## Known limitations

- The encrypted top part of each photo is gone; it is shown as a grey band.
- Colours are estimated when the camera didn't use restart markers; usually close, sometimes off.
- Only baseline JPEG photos are handled (no PNG, video, documents, progressive JPEG yet).
- Photos re-saved by editing apps with custom ("optimised") Huffman tables can't be matched.

## License

Free for **non-commercial** use under the [PolyForm Noncommercial License 1.0.0](LICENSE):
personal use, research, education, charities and public institutions. **Commercial use
requires a separate agreement** — see [COMMERCIAL.md](COMMERCIAL.md). Contributions are
welcome under the terms in [CONTRIBUTING.md](CONTRIBUTING.md).
