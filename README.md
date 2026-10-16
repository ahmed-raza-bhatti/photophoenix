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
| **100%** of the photo | an exact, untouched copy of the file is on a drive you point PhotoPhoenix to — [rare; see below](#finding-untouched-copies-what-to-expect) |
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

## The grey area: why some photos have one and others don't

The grey band at the top is the part of the picture that was inside the encrypted 150 KB. It
can't be recovered: it is scrambled with a key only the attackers have. Only an untouched copy
(or the key leaking one day) can bring it back.

**How big it is depends on the file size**, because the encrypted part is always 150 KB:

| Photo file size | Share of the picture lost | What you see |
|---|---|---|
| ~3–4 MB (recent phones) | ~3–6% | a thin strip, easy to miss |
| ~1–1.5 MB (phones around 2014–2016) | ~10–20% | a clear band |
| ~300–500 KB (old phones) | ~30–75% | most of the top half |
| under ~150 KB | 100% | nothing to recover (reported as failed) |

Part of the 150 KB is camera metadata, so photos with a lot of it lose even less.

**No grey area at all** when the photo was restored from an untouched copy, or rebuilt from
its own header (both complete). Also, when PhotoPhoenix can't tell a camera's full image
height, it saves only the rows that survived: such a photo has no grey band but is **shorter
than the original** — its top is missing.

**Your choice in the app** (*Grey area*): **Keep it** (default — original size, the band shows
honestly what is missing), **Crop it off** (grey rows removed; the photo is shorter), or **Save
both** (the full photo plus `… (cropped).jpg`). Cropping is lossless: the picture data is copied,
not re-compressed. `report.csv` marks cropped photos. Changing the choice later redoes the
affected photos. Setting: `grey_area` in `config.toml`; command line: `recover --grey crop`.

## Videos (MP4, 3GP, MOV)

Videos are large, so the encrypted 150 KB is usually less than 1% of the file. What comes
back depends on where the video's **index** (the table of where every frame is) was stored:

| Index stored | Typical source | Result |
|---|---|---|
| **At the end** — survived | most Android phone camera apps | **The whole video plays**, full length, with sound. Only the first moments (whose data was encrypted) are glitchy — `report.csv` gives an estimate, usually 1–3 seconds. |
| **At the start** — encrypted | iPhones, WhatsApp and other chat apps, video editors | **Not supported yet.** The video data is still there, but rebuilding its index is future work. These are listed as "failed" with that reason; keep the encrypted files. |
| — | videos under ~150 KB | nothing to recover |

On one real 250 GB drive, 196 of 440 encrypted videos had their index at the end. Untouched
copies (see below) are restored complete for any video. Turn videos off with the
**Include videos** box or `include_videos = false`.

## Teaching PhotoPhoenix your cameras

A JPEG starts with a header: the "instructions" for reading the picture (size, compression
tables, how colour is stored). STOP/Djvu destroyed that header in every photo, but each phone or
camera model writes the same kind of header on all its photos. So PhotoPhoenix borrows the header
of a **healthy photo from the same camera model** to read what survived. No part of the healthy
photo's picture is used.

- **First Start:** it learns automatically from healthy JPEGs in `donor_dirs` (default: the
  encrypted-photos folder).
- **Later, more sources:** press **Learn cameras from…**, add folders, or **Add whole PC** for
  every drive, and press **Start learning**. New cameras are added to the existing library.
  Command line: `python -m photophoenix build-library D:\ E:\Backup`.
- **What is read:** only the first ~128 KB of each JPEG (the header). System, program and
  app-cache folders, tiny images and encrypted files are skipped. It runs at low priority and
  can be stopped at any time; whatever was learned is kept.
- **What it helps with:** a camera PhotoPhoenix has a healthy photo from gets the most reliable
  repair. Without one it estimates the settings from the data, which works for most photos but
  occasionally gets colours wrong. It does **not** bring back the encrypted top part of a photo.

## Finding untouched copies: what to expect

The **Find untouched copies** button checks whether an exact, unencrypted copy of any of your
encrypted photos sits in folders you choose. A copy gives the whole photo back. It is worth
one try, but **for most people it finds few or no copies.** Please read this before relying on it.

**How it decides a file is a copy.** STOP/Djvu keeps a file's size (plus 334 bytes it adds at
the end) and leaves everything after the first 150 KB untouched. So a file that is exactly
334 bytes smaller *and* whose bytes after 150 KB are identical is the same file, even if it
was renamed. Files smaller than about 160 KB can't be compared this way and are matched by
name and size only (less certain).

**What it will find**
- The exact same file saved twice: a folder you copied to another drive, a backup, a USB stick
  or SD card, an old phone's folder you copied to the PC, a file transfer app's folder
  (SHAREit, Xender, Nearby Share), photos you *received* in WhatsApp and saved elsewhere.

**What it will NOT find**
- **Copies that were re-saved or compressed.** Photos you *sent* through WhatsApp, Messenger,
  Facebook, Instagram or e-mail apps that shrink images are different files. Their pixels may
  look the same, but their bytes are not, so they don't count as copies. (They *can* still help
  as "healthy photos" for learning your camera's settings.)
- **Anything in folders you didn't choose.** It doesn't search your whole computer, your phone,
  or the cloud. To use Google Photos, OneDrive, iCloud or a phone, first download/copy those
  photos into a folder, then add that folder to `copy_search_dirs`.
- **Copies on drives the ransomware also encrypted.** STOP/Djvu encrypts every drive connected
  at the time, including USB drives that were plugged in.

**What happens**
1. It shows you the exact folders it will read and asks before starting.
2. It only reads files; it never changes, moves, deletes or uploads anything.
3. It tells you how many encrypted photos have a copy (and how many of those were verified
   byte-for-byte), and saves the list in `local/copies.csv`.
4. On **Start**, photos with a copy are restored by copying that file; all others are
   repaired as usual. Finding no copies changes nothing else.

**Real-world example:** on one victim's 250 GB drive with 21,000 encrypted files, about 1 in
20 had an untouched copy, almost all of them WhatsApp images that had also been moved to
another folder by a file transfer app. Camera photos almost never had copies.

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

- The encrypted top part of each photo is gone; it is shown as a grey band or cropped off
  (see [The grey area](#the-grey-area-why-some-photos-have-one-and-others-dont)).
- Colours are estimated when the camera didn't use restart markers; usually close, sometimes off.
- Photos: only baseline JPEG (no PNG or progressive JPEG yet). Videos: only those whose index
  survived. No documents yet.
- Photos re-saved by editing apps with custom ("optimised") Huffman tables can't be matched.

## License

Free for **non-commercial** use under the [PolyForm Noncommercial License 1.0.0](LICENSE):
personal use, research, education, charities and public institutions. **Commercial use
requires a separate agreement** — see [COMMERCIAL.md](COMMERCIAL.md). Contributions are
welcome under the terms in [CONTRIBUTING.md](CONTRIBUTING.md).
