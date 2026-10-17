# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/). Package version `0.x.y` follows the
engine version `x.y`; when results change, `ENGINE_VERSION` in `engine.py` is bumped so the
app redoes photos recovered by an older engine.

## [Unreleased]
### Added
- Video recovery (MP4 / 3GP / MOV) for videos whose index survived at the end of the file: the
  file header is rebuilt in front of the untouched media; full length with sound, only the first
  moments are damaged (estimated in `report.csv`). Videos whose index was encrypted are reported
  as not supported yet. "Include videos" option; `recover` works on videos too.
- Grey-area choice: keep it, crop it off, or save both. Cropping is lossless (the new file starts
  at the first complete block row; picture data is copied, not re-compressed). `report.csv`
  marks cropped photos; changing the choice redoes affected photos. `recover --grey`.
- README section explaining the grey area: why its size varies and why some photos have none.
- "Learn cameras from…" window: add healthy-photo folders or the whole PC to the camera library
  at any time; learning adds to the existing library, can be stopped, keeps what it learned.
- Honest explanation and result summary for "Find untouched copies".
### Fixed
- "Find untouched copies" replaced the whole copy list, so searching a second folder wiped the
  copies found earlier. Searches now add to the list (entries whose files are gone are dropped).
### Changed
- Camera learning reads only the first 128 KB of each JPEG and skips system, program and
  app-cache folders and images under 640×480. `build-library` now adds to the library
  (`--replace` to start fresh).

## [0.3.3] — engine 3.3
### Added
- Per-camera chroma step detection (fixes faded colours on cameras that store colour 2× coarser).
- Configurable settings (`config.toml`, `.env`, `PHOTOPHOENIX_*`), command line, synthetic tests.
### Changed
- Repository restructured as the `photophoenix` package; renamed to PhotoPhoenix.

## engine 3.2
- Quant tables chosen by the 0..255 range rule in every path (fixes garish, over-amplified colours).
- App redoes photos recovered by an older engine.

## engine 3.1
- Infer width and quant tables without a same-camera photo; deep camera search; memory-safe
  lookup tables; low process priority, RAM guard, worker cap.

## engine 3.0
- Exact encrypted boundary from verified pairs; untouched-copy finder; fast table-driven
  decoder; donor library; header path; restart-marker path with trailing-marker support;
  colour estimator v2.

## engine 1–2
- Header graft with alignment search; restart-marker repair; first desktop app.
