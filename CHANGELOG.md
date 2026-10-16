# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/). Package version `0.x.y` follows the
engine version `x.y`; when results change, `ENGINE_VERSION` in `engine.py` is bumped so the
app redoes photos recovered by an older engine.

## [0.3.3] — engine 3.3
### Added
- Per-camera chroma step detection (fixes faded colours on cameras that store colour 2× coarser).
- Configurable settings (`config.toml`, `.env`, `STOPGAP_*`), command line, synthetic tests.
### Changed
- Repository restructured as the `stopgap` package; renamed to STOPgap.

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
