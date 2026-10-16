# Recovery methods

The techniques that make STOPgap work, in the order the engine tries them. Each one was
added to fix a concrete failure seen on real photos; the evidence is in
[validation.md](validation.md). Keep these when changing the code.

## 0. Exact boundary, not guesswork

The encrypted region is exactly bytes `[5, 153605)` and the trailer exactly 334 bytes
([djvu-format.md](djvu-format.md)). Early versions guessed the boundary from byte patterns
and lost data; using the measured constants is exact.

## 1. Untouched copies (100%)

Many photos also exist unencrypted elsewhere: backups, chat downloads, phone-transfer apps,
other folders. A candidate is a verified original when its size is `encrypted − 334` and two
64 KB windows after byte 153605 match byte-for-byte. Files too small to verify are matched by
name + size. Only folders the user configures are searched (`copies.py`).

## 2. Header path (≈100%)

Some cameras write large metadata first, pushing the real DQT/DHT/SOF/SOS header past the
encrypted area. If a complete header is found in the surviving part, the whole image is
rebuilt from it (`try_header_path`).

## 3. Restart-marker path (exact)

Some cameras insert restart markers (`FFD0..FFD7`) every N blocks. Each marker resets the DC
predictors, so every surviving interval has **absolute** colours, and the marker numbering
plus the interval count pin each interval's exact position. A donor of the same camera and
size gives the header; lost intervals are filled with flat grey blocks and correctly
numbered markers. Some cameras also put a marker after the last interval — handled.

## 4. Align path (same-camera header)

Without restart markers:

1. **Fast resync.** Decode from the first surviving byte; on a Huffman error jump past it.
   The correct tables lock on within ~100 bytes; wrong tables fail fast, which is also how
   the camera's tables are identified among thousands in the library.
2. **Count blocks to the end.** Once synchronised, every MCU to the end of the file is
   counted, so `lost = total − counted` and the surviving data is placed exactly — the last
   block is always the bottom-right corner.
3. **Header from a healthy photo** of the same tables and inferred width.

## 5. Infer path (no same-camera photo)

1. **Width from the data.** The decoded DC values form a 1/8-scale thumbnail. Only the true
   row width makes consecutive rows line up; each candidate width is scored by
   vertical-vs-horizontal neighbour differences.
2. **Size** from common aspect ratios and known sizes; if nothing fits, only the recovered rows.
3. **Quant tables** — see 6.

## 6. Quantisation tables: blocks must stay within 0..255

A wrong quant table rescales everything: too coarse gives crushed blacks and garish colours,
too fine gives a faded image. Real pixels are 0..255, so a table is only possible if every
visible block stays in range:

- restart path (absolute DC): `step ≤ 1024 / max|DC|`
- other paths (relative DC): `step ≤ 2040 / spread(DC)`

The tightest allowed step is chosen, tightened further by the other photos of the same
camera (all photos of a camera share a table). Among tables with that step, the one with the
cleanest block seams wins.

## 7. Chroma step per camera

Most cameras use the same DC step for brightness and colour; some (e.g. certain compacts)
store colour 2× coarser. Assuming 1:1 for those gives ashy, faded colours. Two signals per
photo — colour spread compared with the typical ~70 levels of real photos, and the RGB gamut
ceiling — are pooled over up to 8 photos of the same camera in the folder (a deterministic
sample, so all workers agree). The rule is conservative: it never switched a normal camera in
testing, and leaves borderline cameras at 1:1.

## 8. Colour (DC) offset

Decoding mid-stream gives each component's DC values minus one unknown constant. The
estimator uses: the 0..255 range constraint; clipped highlights (many perfectly flat blocks at
the maximum are pure white, so neutral); bright blocks mostly being near-neutral, blended with
the global median. About 10× more accurate on brightness than a simple median rule.

## 9. Rebuilding the file

New header (donor segments, size/sampling/quant tables patched, APP segments dropped) +
flat-grey blank MCUs for the lost area (the last one carries the DC correction, split over
several MCUs if a table lacks large categories) + the surviving entropy bits shifted into
place + byte stuffing + EOI. Candidates are scored by a block-seam ratio (≈1 for a real
picture) and the best is kept; scores ≥ 2 go to `_needs_review`.
