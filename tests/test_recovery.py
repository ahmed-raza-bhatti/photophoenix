"""End-to-end tests on synthetic photos (no real photos are used or needed).

Each test builds JPEGs with Pillow, "encrypts" one the way STOP/Djvu does (first 150 KB
scrambled after byte 5, 334-byte trailer appended) and checks recovery.

Run:  python -m unittest discover -s tests -v
"""
import io, json, os, random, sys, tempfile, unittest
import numpy as np
from PIL import Image



def _write(path, data):
    with open(path, "wb") as fh:
        fh.write(data)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from photophoenix import config, copies, engine  # noqa: E402

TMP_BASE = os.path.join(ROOT, "local", "tmp")  # keep test files off the system temp disk


def synthetic_photo(seed, w=1600, h=1200):
    """Smooth gradients + coloured shapes + grain: compresses like a real photo (~0.5-1 MB)."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.stack([120 + 80 * np.sin(x / 170 + seed), 110 + 70 * np.cos(y / 130), 100 + 60 * np.sin((x + y) / 210)], -1)
    for _ in range(25):
        cx, cy, r = rng.integers(0, w), rng.integers(0, h), rng.integers(30, 220)
        mask = (x - cx) ** 2 + (y - cy) ** 2 < r * r
        img[mask] = rng.integers(0, 256, 3)
    img[: h // 10, :] = 250            # a bright band (like sky) gives a white anchor
    img[-h // 12:, : w // 3] = 8       # and a dark one
    img += rng.normal(0, 9, img.shape)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def jpeg_bytes(im, **kw):
    b = io.BytesIO(); im.save(b, "JPEG", quality=90, **kw); return b.getvalue()


def djvu_encrypt(data, seed=0):
    rnd = random.Random(seed)
    scrambled = bytes(rnd.getrandbits(8) for _ in range(engine.ENC_END - 5))
    trailer = bytes(rnd.getrandbits(8) for _ in range(256)) + b"A" * 40 + engine.MARKER
    assert len(trailer) == engine.TRAILER
    return data[:5] + scrambled + data[engine.ENC_END:] + trailer


def mean_abs_diff_bottom(a_bytes, b_bytes, frac=0.4):
    a = np.asarray(Image.open(io.BytesIO(a_bytes)).convert("RGB"), np.float32)
    b = np.asarray(Image.open(io.BytesIO(b_bytes)).convert("RGB"), np.float32)
    h = a.shape[0]; s = int(h * (1 - frac))
    return float(np.abs(a[s:] - b[s:]).mean())


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        os.makedirs(TMP_BASE, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=TMP_BASE)
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _library(self, donor_bytes):
        ddir = os.path.join(self.dir, "healthy"); os.makedirs(ddir, exist_ok=True)
        _write(os.path.join(ddir, "donor.jpg"), donor_bytes)
        return engine.Library(engine.scan_library([ddir]))

    def _encrypt_to_file(self, data, name="IMG_0001.jpg"):
        edir = os.path.join(self.dir, "encrypted"); os.makedirs(edir, exist_ok=True)
        p = os.path.join(edir, name + ".coot"); _write(p, djvu_encrypt(data)); return p

    def test_align_path_with_same_camera_donor(self):
        original = jpeg_bytes(synthetic_photo(1))
        self.assertGreater(len(original), engine.ENC_END + 200_000)
        lib = self._library(jpeg_bytes(synthetic_photo(2)))
        r = engine.recover(self._encrypt_to_file(original), lib)
        self.assertEqual(r["method"], "align")
        self.assertEqual(r["dims"], "1600x1200")
        self.assertLess(r["q"], 2.0)
        self.assertLess(mean_abs_diff_bottom(original, r["jpg"]), 12.0)

    def test_restart_path_is_exact(self):
        original = jpeg_bytes(synthetic_photo(3), restart_marker_blocks=50)
        lib = self._library(jpeg_bytes(synthetic_photo(4), restart_marker_blocks=50))
        r = engine.recover(self._encrypt_to_file(original), lib)
        self.assertEqual(r["method"], "restart")
        self.assertLess(mean_abs_diff_bottom(original, r["jpg"]), 1.0)  # exact apart from rounding

    def _assert_lossless_crop(self, r):
        full = np.asarray(Image.open(io.BytesIO(r["jpg"])).convert("RGB"), np.int16)
        self.assertIsNotNone(r.get("jpg_cropped"))
        crop = np.asarray(Image.open(io.BytesIO(r["jpg_cropped"])).convert("RGB"), np.int16)
        self.assertLess(crop.shape[0], full.shape[0])            # grey rows removed
        self.assertEqual(crop.shape[1], full.shape[1])
        cut = full.shape[0] - crop.shape[0]
        # identical to the bottom of the full photo (row 0 may differ: colour smoothing at the edge)
        self.assertEqual(int(np.abs(full[cut + 1:] - crop[1:]).max()), 0)
        self.assertLess(float(crop[:8].std()), 5 + float(full[cut:cut + 8].std()) * 2)  # no grey band left

    def test_crop_align_is_lossless(self):
        lib = self._library(jpeg_bytes(synthetic_photo(2)))
        r = engine.recover(self._encrypt_to_file(jpeg_bytes(synthetic_photo(1))), lib, crop=True)
        self._assert_lossless_crop(r)

    def test_crop_restart_is_lossless(self):
        lib = self._library(jpeg_bytes(synthetic_photo(4), restart_marker_blocks=50))
        r = engine.recover(self._encrypt_to_file(jpeg_bytes(synthetic_photo(3), restart_marker_blocks=50)), lib, crop=True)
        self.assertEqual(r["method"], "restart")
        self._assert_lossless_crop(r)

    def test_whole_file_inside_encrypted_area_is_reported(self):
        small = jpeg_bytes(synthetic_photo(5, 320, 240))
        lib = self._library(jpeg_bytes(synthetic_photo(6)))
        with self.assertRaises(ValueError):
            engine.recover(self._encrypt_to_file(small), lib)

    def test_untouched_copy_is_found_and_verified(self):
        original = jpeg_bytes(synthetic_photo(7))
        enc = self._encrypt_to_file(original)
        backup = os.path.join(self.dir, "backup"); os.makedirs(backup)
        _write(os.path.join(backup, "renamed.jpg"), original)
        csv_path = os.path.join(self.dir, "copies.csv")
        stats = {}
        found = copies.find(os.path.dirname(enc), [backup], csv_path, progress=lambda m: None, stats=stats)
        self.assertEqual(len(found), 1)
        self.assertEqual(stats, {"total": 1, "found": 1, "verified": 1, "in_list": 1})
        self.assertEqual(found[enc][1], "verified-bytes")
        self.assertIn(os.path.normcase(os.path.abspath(enc)), copies.load(csv_path, [backup]))
        self.assertEqual(copies.load(csv_path, [os.path.join(self.dir, "elsewhere")]), {})  # outside allowed roots
        # a later search of another folder (finding nothing) must not wipe the earlier result
        other = os.path.join(self.dir, "other"); os.makedirs(other)
        st2 = {}
        copies.find(other, [other], csv_path, progress=lambda m: None, stats=st2)
        self.assertEqual((st2["found"], st2["in_list"]), (0, 1))
        self.assertIn(os.path.normcase(os.path.abspath(enc)), copies.load(csv_path, [backup]))


class LibraryTests(unittest.TestCase):
    def setUp(self):
        os.makedirs(TMP_BASE, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=TMP_BASE); self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _put(self, rel, data):
        p = os.path.join(self.dir, rel); os.makedirs(os.path.dirname(p), exist_ok=True); _write(p, data)

    def test_learning_skips_system_folders_and_tiny_images_and_merges(self):
        self._put("photos/a.jpg", jpeg_bytes(synthetic_photo(10)))                       # 1600x1200
        self._put("photos/thumb.jpg", jpeg_bytes(synthetic_photo(11, 320, 240)))        # too small
        self._put("AppData/cache/big.jpg", jpeg_bytes(synthetic_photo(12, 1200, 1600)))  # cache folder
        first = engine.scan_library([self.dir])
        self.assertEqual(len(first), 1)
        self._put("more/b.jpg", jpeg_bytes(synthetic_photo(13, 1200, 1600)))            # a new size
        merged, added = engine.merge_library(first, engine.scan_library([os.path.join(self.dir, "more")]))
        self.assertEqual((len(merged), added), (2, 1))
        merged2, added2 = engine.merge_library(merged, engine.scan_library([self.dir]))
        self.assertEqual((len(merged2), added2), (2, 0))  # nothing new the second time

    def test_learning_can_stop_early(self):
        for i in range(3):
            self._put(f"p/{i}.jpg", jpeg_bytes(synthetic_photo(20 + i)))
        self.assertEqual(engine.scan_library([self.dir], should_stop=lambda: True), [])


class ConfigTests(unittest.TestCase):
    def test_environment_overrides(self):
        os.environ["PHOTOPHOENIX_WORKERS"] = "2"; os.environ["PHOTOPHOENIX_DONOR_DIRS"] = "a;b"
        try:
            s = config.load(config_path=os.path.join(TMP_BASE, "does-not-exist.toml"))
            self.assertEqual(s.workers, 2)
            # relative paths resolve against the project folder
            self.assertEqual(s.donor_dirs, [os.path.join(config.PROJECT_ROOT, "a"), os.path.join(config.PROJECT_ROOT, "b")])
        finally:
            del os.environ["PHOTOPHOENIX_WORKERS"], os.environ["PHOTOPHOENIX_DONOR_DIRS"]

    def test_recover_choice_and_old_setting(self):
        os.environ["PHOTOPHOENIX_RECOVER"] = "videos"
        try:
            self.assertEqual(config.load(config_path=os.path.join(TMP_BASE, "none.toml")).recover, "videos")
        finally:
            del os.environ["PHOTOPHOENIX_RECOVER"]
        os.environ["PHOTOPHOENIX_INCLUDE_VIDEOS"] = "false"   # older setting still respected
        try:
            self.assertEqual(config.load(config_path=os.path.join(TMP_BASE, "none.toml")).recover, "photos")
        finally:
            del os.environ["PHOTOPHOENIX_INCLUDE_VIDEOS"]

    def test_workers_are_capped(self):
        os.environ["PHOTOPHOENIX_WORKERS"] = "99"
        try:
            self.assertLessEqual(config.load().workers, config.Settings().max_workers)
        finally:
            del os.environ["PHOTOPHOENIX_WORKERS"]


if __name__ == "__main__":
    unittest.main()
