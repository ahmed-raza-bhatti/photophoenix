"""Index-rebuild tests for videos whose index was encrypted (synthetic data only).

Run:  python -m unittest discover -s tests -v
"""
import os, random, shutil, struct, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.join(ROOT, "tests"))
from photophoenix import video_index  # noqa: E402
from test_video import djvu_encrypt  # noqa: E402

TMP_BASE = os.path.join(ROOT, "local", "tmp")


def nal(header, payload_first, n):
    body = bytes([header, payload_first]) + bytes(random.Random(n).getrandbits(8) for _ in range(n))
    return struct.pack(">I", len(body)) + body


class WalkFramesTests(unittest.TestCase):
    def test_frames_found_and_audio_skipped(self):
        rnd = random.Random(5)
        data, expected = bytearray(), []
        for i in range(30):
            start = len(data)
            if i % 10 == 0:                                   # keyframe: SPS + PPS + IDR slice
                data += nal(0x67, 0x42, 10) + nal(0x68, 0xCE, 4) + nal(0x65, 0x88, 900 + i)
            else:                                             # P frame: two slices (2nd not first_mb 0)
                data += nal(0x41, 0x9A, 400 + i) + nal(0x41, 0x1A, 300)
            expected.append((start, len(data) - start, i % 10 == 0))
            if i % 3 == 2:                                    # an "audio" chunk: junk that isn't NALs
                junk = bytearray(rnd.getrandbits(8) for _ in range(700))
                junk[0] = 0xFF                                # make sure it can't parse as a length
                data += junk
        data += b"\0" * 32
        frames = video_index.walk_frames(bytes(data), 0, len(data) - 32)
        self.assertEqual(frames, expected)


class TimingAndFakeFrameTests(unittest.TestCase):
    def test_aac_frame_duration_comes_from_the_format(self):
        self.assertEqual(video_index.aac_frame_delta("1190", 48000), 1024)   # 48 kHz stereo
        self.assertEqual(video_index.aac_frame_delta("1210", 44100), 1024)   # 44.1 kHz stereo
        self.assertEqual(video_index.aac_frame_delta("1190", 90000), 1920)   # other timescale

    def test_typical_duration_ignores_an_odd_first_entry(self):
        stts = struct.pack(">I4sII", 32, b"stts", 0, 3) + struct.pack(">IIIIII", 1, 1105, 500, 1024, 1, 900)
        self.assertEqual(video_index._typical_delta(stts, (8, len(stts))), 1024)

    def test_fake_oversized_frame_in_audio_is_rejected(self):
        rnd = random.Random(7)
        data = bytearray()
        for i in range(40):                                   # normal chained P frames (~1 KB)
            data += nal(0x41, 0x9A, 900 + i) + nal(0x41, 0x1A, 100)
            if i == 20:                                       # audio chunk with a fake frame start inside
                junk = bytearray(rnd.getrandbits(8) for _ in range(3000)); junk[0] = 0xFF
                fake = struct.pack(">I", 200_000) + bytes([0x41, 0x9A]) + bytes(20)   # claims 200 KB
                data += junk + fake + junk
        data += b"\0" * 32
        frames = video_index.walk_frames(bytes(data), 0, len(data) - 32)
        self.assertLess(max(s for _, s, _ in frames), 5000)   # no frame swallowed audio + video
        self.assertGreaterEqual(len(frames), 39)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class RebuildTests(unittest.TestCase):
    def setUp(self):
        os.makedirs(TMP_BASE, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=TMP_BASE); self.dir = self.tmp.name
        enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        if "libx264" not in enc:
            self.skipTest("ffmpeg has no libx264")

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, name, seconds, size="640x360", seed=1):
        p = os.path.join(self.dir, name)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=25:duration={seconds}",
                        "-f", "lavfi", "-i", f"sine=frequency={300 + seed}:duration={seconds}",
                        "-c:v", "libx264", "-profile:v", "main", "-bf", "0", "-g", "25", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", "-movflags", "+faststart", p], check=True)
        return p

    def frame_hashes(self, path, stream="0:v"):
        out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", stream, "-f", "framemd5", "-"],
                             capture_output=True, text=True, check=True).stdout
        return [l.split(",")[-1].strip() for l in out.splitlines() if l and not l.startswith("#")]

    def test_rebuilt_frames_are_identical(self):
        ref_dir = os.path.join(self.dir, "refs"); os.makedirs(ref_dir)
        shutil.move(self.make("ref.mp4", 3, seed=2), os.path.join(ref_dir, "ref.mp4"))
        refs = video_index.scan_refs([ref_dir])
        self.assertEqual(len(refs), 1)
        src = self.make("patient.mp4", 20)
        with open(src, "rb") as fh: original = fh.read()
        enc = src + ".coot"
        with open(enc, "wb") as fh: fh.write(djvu_encrypt(original))
        out = os.path.join(self.dir, "rebuilt.mp4")
        info = video_index.rebuild(enc, out, refs, temp_dir=self.dir)
        self.assertEqual(info["status"], "ok")
        got, want = self.frame_hashes(out), self.frame_hashes(src)
        self.assertGreater(len(got), 0.7 * len(want))           # most frames survived
        self.assertEqual(got[-200:], want[-200:])                 # and they are pixel-identical
        try:
            import av  # noqa: F401  (sound needs PyAV)
        except ImportError:
            return
        self.assertIn("sound", info["note"])
        got_a, want_a = self.frame_hashes(out, "0:a"), self.frame_hashes(src, "0:a")
        self.assertGreater(len(got_a), 0.7 * len(want_a))         # most of the sound survived
        # bit-identical once decoded (the original trims the encoder's padding on its very last
        # frame in its index; the rebuilt index can't know that, so the last frame is excluded)
        self.assertEqual(got_a[-300:-1], want_a[-300:-1])

    def test_wrong_reference_is_rejected(self):
        ref_dir = os.path.join(self.dir, "refs"); os.makedirs(ref_dir)
        shutil.move(self.make("ref.mp4", 3, size="320x240", seed=2), os.path.join(ref_dir, "ref.mp4"))
        refs = video_index.scan_refs([ref_dir])
        src = self.make("patient.mp4", 12)
        with open(src, "rb") as fh: original = fh.read()
        enc = src + ".coot"
        with open(enc, "wb") as fh: fh.write(djvu_encrypt(original))
        with self.assertRaises(ValueError):
            video_index.rebuild(enc, os.path.join(self.dir, "x.mp4"), refs, temp_dir=self.dir)


if __name__ == "__main__":
    unittest.main()
