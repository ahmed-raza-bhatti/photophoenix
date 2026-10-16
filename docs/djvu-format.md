# What STOP/Djvu does to a file

Measured on verified pairs of original and encrypted files (variant `.coot`, late 2019;
other "new" STOP/Djvu variants behave the same way).

| Bytes | Content |
|---|---|
| `0 .. 5` | original (unencrypted) — for a JPEG: `FF D8 FF E1 xx` |
| `5 .. 153605` | **encrypted** (exactly 150 KB = 0x25800 bytes), Salsa20 |
| `153605 .. original size` | **original bytes, untouched** |
| last 334 bytes (appended) | 256-byte key blob · 40-char personal ID · marker `{36A698B9-D67C-4E07-BE82-0EC5B14B4DF5}` |

So `encrypted size = original size + 334`, and files under ~150 KB are encrypted completely.

## Can it be decrypted?

Not for *online-key* victims (personal ID not ending in `t1`):

- Every file has its **own key**: the 256-byte key blob differs per file and is the size of
  an RSA-2048 ciphertext. Only the attackers' private key opens it.
- There is **no keystream reuse** between files: XOR of two same-camera headers shows ~0.4%
  zero bytes, exactly what random data gives (reuse would show >30%).

Offline-key victims (ID ending in `t1`) may be helped by Emsisoft's free decryptor.

## Why recovery is possible anyway

A JPEG stores its header (tables, size) first and the image data after it, top row first.
STOP/Djvu destroys the header and the top slice of the image, but the rest of the image data
— usually most of it — is intact. The challenge is decoding image data whose header,
starting point and colour baseline are all unknown. See [methods.md](methods.md).
