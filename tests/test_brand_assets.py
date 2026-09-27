"""Tests for Home Assistant local brand assets and release integrity."""

import hashlib
import pathlib
import struct
import subprocess
import unittest


REPOSITORY_PATH = pathlib.Path(__file__).parents[1]
BRAND_PATH = REPOSITORY_PATH / "custom_components" / "congmodbus" / "brand"
CHECKSUM_PATH = REPOSITORY_PATH / "FILES-SHA256.txt"


def png_dimensions(path):
    """Return dimensions from the PNG IHDR chunk without optional libraries."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"{path.name} is not a valid PNG")
    return struct.unpack(">II", data[16:24])


class BrandAssetsTest(unittest.TestCase):
    def test_standard_and_retina_icons_have_expected_dimensions(self):
        self.assertEqual((512, 512), png_dimensions(BRAND_PATH / "icon.png"))
        self.assertEqual((1024, 1024), png_dimensions(BRAND_PATH / "icon@2x.png"))

    def test_checksum_manifest_covers_all_tracked_release_files(self):
        expected = {}
        for line in CHECKSUM_PATH.read_text(encoding="utf-8").splitlines():
            digest, relative_path = line.split("  ", 1)
            expected[relative_path] = digest

        tracked = set(
            subprocess.check_output(
                ["git", "ls-files"], cwd=REPOSITORY_PATH, text=True
            ).splitlines()
        )
        tracked.remove(CHECKSUM_PATH.name)
        self.assertEqual(tracked, set(expected))

        for relative_path, digest in expected.items():
            data = (REPOSITORY_PATH / relative_path).read_bytes()
            # Git for Windows may check text files out with CRLF while release
            # archives and Linux CI contain the canonical LF bytes.
            if pathlib.Path(relative_path).suffix != ".png":
                data = data.replace(b"\r\n", b"\n")
            actual = hashlib.sha256(data).hexdigest()
            self.assertEqual(digest, actual, relative_path)


if __name__ == "__main__":
    unittest.main()
