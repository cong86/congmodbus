"""Build the complete v1.5 runtime bundle from committed Git contents."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZIP_STORED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = (2026, 9, 28, 0, 0, 0)


def git_bytes(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=ROOT)


def main(output: Path) -> None:
    manifest = json.loads(git_bytes("custom_components/congmodbus/manifest.json"))
    if manifest["version"] != "1.5":
        raise SystemExit("Release bundle requires congmodbus manifest version 1.5")

    tracked = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=ROOT, text=True
    ).splitlines()
    pairs = [
        (path, path)
        for path in tracked
        if path.startswith("custom_components/congmodbus/")
        or path.startswith("examples/packages/")
        or path in ("README.md", "CHANGELOG.md")
    ]
    pairs += [
        (path, "custom_components/" + path.removeprefix("extras/"))
        for path in tracked
        if path.startswith("extras/homekit_climate_proxy/")
    ]
    pairs.sort(key=lambda item: item[1])
    required = {
        "custom_components/congmodbus/manifest.json",
        "custom_components/homekit_climate_proxy/manifest.json",
        "examples/packages/congmodbus.yaml",
        "examples/packages/homekit_climate_proxy.yaml",
    }
    if not required.issubset({destination for _, destination in pairs}):
        raise SystemExit("Release bundle is missing a required component or example")

    output.parent.mkdir(parents=True, exist_ok=True)
    checksums = []
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for source, destination in pairs:
            data = git_bytes(source)
            info = ZipInfo(destination, FIXED_TIME)
            info.compress_type = ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
            checksums.append(f"{hashlib.sha256(data).hexdigest()}  {destination}")

        info = ZipInfo("SHA256SUMS.txt", FIXED_TIME)
        info.compress_type = ZIP_STORED
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        archive.writestr(info, "\n".join(checksums) + "\n")

    print(f"{output}: {hashlib.sha256(output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_release.py OUTPUT_ZIP")
    main(Path(sys.argv[1]))
