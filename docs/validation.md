# Validation

Every estimator was tested on **healthy** photos whose true values are known, with the top
150 KB hidden exactly as STOP/Djvu would. Scripts are in `tools/`; numbers below are from a
personal collection of a few thousand phone and camera photos (2008–2019).

## Decryption feasibility
- Key blobs differ for every file (6/6 distinct); XOR of same-camera headers: 0.27–0.51%
  zero bytes (random: 0.39%). Conclusion: no keystream reuse, no decryption.

## Colour offset estimator (`colour.estimate_v2`), 120 photos
| | brightness error median / 90th pct | colour error median / 90th pct |
|---|---|---|
| simple median rule | 35.5 / 76.8 levels | 2.5 / 11.3 |
| v2 (range + clipping + bright-neutral) | **3.6 / 22.1** | **1.5 / 7.3** |

## Quant-table rule (`tools/eval_quant_tables.py`), 150 photos
Tightest allowed DC step ÷ true step:
| | median | within 1.25× | within 1.5× | below true |
|---|---|---|---|---|
| spread rule (align/infer) | 1.07 | 82% | 93% | 0% |
| absolute rule (restart) | 1.02 | 97% | 99% | 0% |

## Chroma step per camera (`tools/eval_chroma_ratio.py`), 160 photos
Simulated 2:1 cameras made by halving real photos' colour DCs. Final conservative rule,
pooled over 8 photos: 1:1 cameras classified correctly **100%**, 2:1 cameras **79%**
(the rest stay 1:1 — slightly pale rather than garish). Per-photo decisions were much worse
(89% / 39%).

## End-to-end samples (66 photos from 11 folders)
| engine | recovered | needs review | failed |
|---|---|---|---|
| 3.0 | 31 | 21 | 14 |
| 3.1 (width + quant inference) | **52** | 0 | 14 |
11 of the 14 failures are files entirely inside the encrypted 150 KB (only a copy helps).

## Unit tests
`python -m unittest discover -s tests` — synthetic photos only: align path, exact restart
path, too-small file, copy finding and verification, config precedence.
