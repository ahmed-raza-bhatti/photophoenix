# Contributing to PhotoPhoenix

Thank you for helping ransomware victims get their photos back.

## How changes get in

- `main` is protected: **every change goes through a pull request**, needs a review and
  passing tests, and is **merged by a maintainer by hand** — no direct pushes, no auto-merge.
- Branch from `main`: `fix/...`, `feat/...`, `docs/...`.
- Keep pull requests small and focused; one topic per PR.
- Commit messages: imperative summary line ("Detect chroma step per camera"), body says *why*.
- Update `CHANGELOG.md`. If a change alters recovery results, bump `ENGINE_VERSION` in
  `src/photophoenix/engine.py` (the app then redoes older results).

## Before opening a PR

```
python -m unittest discover -s tests -v
```

- New estimators or heuristics need evidence: a `tools/eval_*.py` script that measures them on
  healthy photos with the top 150 KB hidden, and the numbers in `docs/validation.md`.
- Keep it gentle: no unbounded caches, respect `workers` and `min_free_ram_gb`.

## Privacy rules (strict)

- **Never commit real photos**, encrypted files, `local/`, `config.toml`, `.env`, `library.json`,
  `copies.csv`, `progress.json`, or anything with personal paths or names. Tests use
  synthetic images generated in code.
- Don't paste real ransom-note IDs or e-mail addresses into issues.

## Licence of contributions

PhotoPhoenix is free for non-commercial use (PolyForm Noncommercial 1.0.0) and separately licensed
to companies for commercial use (see COMMERCIAL.md). So that both stay possible:

> By submitting a contribution you confirm that you wrote it (or have the right to submit it),
> and you grant the project maintainer a perpetual, worldwide, non-exclusive, royalty-free,
> irrevocable licence to use, modify, sublicense and distribute your contribution under the
> project's non-commercial licence **and under commercial licences**. You keep your copyright.

Outside contributors: add this line to your PR description to confirm (the maintainer owns
their own code and doesn't add it):
`I agree to the Licence of contributions in CONTRIBUTING.md.`

## Good first contributions

- Faster decoder (Numba/Cython port of `fastjpeg.decode`).
- Other file types: MP4/3GP video, MP3, PNG, ZIP-based Office files — most of each survives too.
- Progressive JPEG and optimised-Huffman-table photos.
- Translations of the app and README.
