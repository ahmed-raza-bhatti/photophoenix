"""Video recovery tests on synthetic files (no real videos needed).

Run:  python -m unittest discover -s tests -v
"""
import json, os, random, shutil, struct, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from photophoenix import engine, video  # noqa: E402

TMP_BASE = os.path.join(ROOT, "local", "tmp")


def box(typ, payload):
    return struct.pack(">I4s", 8 + len(payload), typ) + payload


def synthetic_mp4(media_bytes=600_000, chunk=10_000, seconds=12, index_at_end=True):
    """ftyp + mdat + moov (mvhd + one track with stco). Not playable, structurally valid."""
    rnd = random.Random(1)
    ftyp = box(b"ftyp", b"isom\0\0\0\0isomiso2mp41")
    media = bytes(rnd.getrandbits(8) for _ in range(media_bytes))

    def moov_for(media_start):
        mvhd = box(b"mvhd", b"\0\0\0\0" + struct.pack(">IIII", 0, 0, 1000, seconds * 1000) + b"\0" * 80)
        offs = list(range(media_start, media_start + media_bytes, chunk))
        stco = box(b"stco", b"\0\0\0\0" + struct.pack(">I", len(offs)) + struct.pack(">%dI" % len(offs), *offs))
        return box(b"moov", mvhd + box(b"trak", box(b"mdia", box(b"minf", box(b"stbl", stco)))))

    if index_at_end:
        start = len(ftyp) + 8
        return ftyp + box(b"mdat", media) + moov_for(start)
    moov_len = len(moov_for(0))
    start = len(ftyp) + moov_len + 8
    return ftyp + moov_for(start) + box(b"mdat", media)


def djvu_encrypt(data, seed=0):
    rnd = random.Random(seed)
    return (data[:5] + bytes(rnd.getrandbits(8) for _ in range(engine.ENC_END - 5)) + data[engine.ENC_END:]
            + bytes(rnd.getrandbits(8) for _ in range(256)) + b"A" * 40 + engine.MARKER)


class VideoTests(unittest.TestCase):
    def setUp(self):
        os.makedirs(TMP_BASE, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=TMP_BASE); self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _enc(self, data, name="VID_0001.mp4"):
        p = os.path.join(self.dir, name + ".coot")
        with open(p, "wb") as fh: fh.write(djvu_encrypt(data))
        return p

    def test_index_at_end_is_rebuilt(self):
        original = synthetic_mp4()
        out = os.path.join(self.dir, "out.mp4")
        info = video.recover_video(self._enc(original), out)
        with open(out, "rb") as fh: rebuilt = fh.read()
        self.assertEqual(len(rebuilt), len(original))
        self.assertEqual(rebuilt[engine.ENC_END:], original[engine.ENC_END:])  # media + index untouched
        top = list(video._boxes(rebuilt, 0, len(rebuilt)))
        self.assertEqual([t for t, *_ in top], [b"ftyp", b"mdat", b"moov"])
        self.assertEqual(top[1][1], 28)  # mdat header right where the original one was (after the 28-byte ftyp)
        self.assertEqual(info["dims"], "12 s")
        self.assertTrue(0 < info["damaged_seconds"] < 4)

    def test_3gp_gets_3gp_brand(self):
        out = os.path.join(self.dir, "out.3gp")
        video.recover_video(self._enc(synthetic_mp4(), "VID.3gp"), out)
        with open(out, "rb") as fh: self.assertEqual(fh.read(12)[8:12], b"3gp4")

    def test_index_at_start_is_reported_not_guessed(self):
        out = os.path.join(self.dir, "out.mp4")
        with self.assertRaises(ValueError) as cm:
            video.recover_video(self._enc(synthetic_mp4(index_at_end=False)), out)
        self.assertIn("index was at the start", str(cm.exception))

    def test_is_video(self):
        self.assertTrue(video.is_video("x.MP4.coot")); self.assertTrue(video.is_video("x.3gp"))
        self.assertFalse(video.is_video("x.jpg.coot"))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg not installed")
    def test_real_video_plays_full_length(self):
        src = os.path.join(self.dir, "real.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=8",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=8", "-c:v", "mpeg4", "-q:v", "3",
                        "-c:a", "aac", "-shortest", src], check=True)
        with open(src, "rb") as fh: original = fh.read()
        self.assertGreater(len(original), engine.ENC_END * 2)
        out = os.path.join(self.dir, "rebuilt.mp4")
        video.recover_video(self._enc(original), out)
        pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", out],
                            capture_output=True, text=True, check=True)
        self.assertAlmostEqual(float(json.loads(pr.stdout)["format"]["duration"]), 8.0, delta=0.5)
        # After the damaged start, the decoded pictures and sound are identical to the original's.
        # (ffmpeg may still print a few warnings while probing the encrypted first packets.)
        def md5(path, stream):
            return subprocess.run(["ffmpeg", "-v", "quiet", "-ss", "4", "-i", path, "-map", stream, "-f", "md5", "-"],
                                  capture_output=True, text=True, check=True).stdout.strip()
        for stream in ("0:v", "0:a"):
            self.assertEqual(md5(out, stream), md5(src, stream), stream)


if __name__ == "__main__":
    unittest.main()
