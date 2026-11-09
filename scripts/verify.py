#!/usr/bin/env python3
"""Offline consistency checks for the OPD2515 device repository."""
from __future__ import annotations

import hashlib
import py_compile
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ID = {
    "name": "opd2515",
    "soc": "SM8845",
    "os_profile": "ios-16.5-20F66",
}
EXPECTED_AREAS = {
    "configuration", "firmware", "cpu", "memory", "storage", "display",
    "input", "gpu", "network", "audio", "power", "packaging", "diagnostics",
}
EXPECTED_PHOTOS = {
    "docs/evidence/s8-darwinboot-xnu-handoff.jpg":
        "46e73d13ecf40f43bc1f5c66bc07ba782a033cbde95d881ada08176b033384d4",
    "docs/evidence/s8-post-handoff-unixnu-menu.jpg":
        "5ecb83bc4c14871a30a10193c927f10a2e5d41498a98e448531d1113ed2146b4",
    "docs/evidence/s9-entry-bands-reboot.jpg":
        "057124bdaa26f855673a486e2e763221c093a8a4d69f956b2ca687ed7ace1701",
}


def load_toml(name: str) -> dict:
    with (ROOT / name).open("rb") as source:
        return tomllib.load(source)


def main() -> int:
    board = load_toml("board.toml")
    record = load_toml("porting.toml")
    load_toml("feeds.toml")
    package = load_toml("package/unixnu.toml")

    identity = board["board"]
    for key, value in EXPECTED_ID.items():
        if identity.get(key) != value:
            raise SystemExit(f"board.toml {key} is {identity.get(key)!r}, expected {value!r}")
    for key, value in EXPECTED_ID.items():
        if record["device"].get(key) != value:
            raise SystemExit(f"porting.toml device.{key} does not match board.toml")
    if board["payload"]["adt"].get("unique_chip_id") != "required":
        raise SystemExit("unique_chip_id must remain the literal 'required'")

    areas = {area["id"]: area for area in record["area"]}
    if set(areas) != EXPECTED_AREAS:
        raise SystemExit(f"porting area mismatch: {sorted(set(areas) ^ EXPECTED_AREAS)}")

    drivers = package.get("driver", [])
    if len(drivers) != 1 or drivers[0].get("path") != "Drivers/DarwinBoot.efi":
        raise SystemExit("payload must declare exactly the DarwinBoot driver")
    entries = {entry.get("id") for entry in package.get("entry", [])}
    if not {"xnu", "exit"}.issubset(entries):
        raise SystemExit("payload is missing the xnu or exit entry")

    patch = ROOT / "patches/unixnu/0001-feat-opd2515-advance-firmware-boot-to-XNU-handoff.patch"
    if not patch.is_file() or patch.stat().st_size < 1024:
        raise SystemExit("UniXNU source patch is missing or truncated")

    for relative, expected in EXPECTED_PHOTOS.items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"{relative}: SHA-256 {actual} != {expected}")

    for directory in ("scripts", "tools"):
        for source in (ROOT / directory).glob("*.py"):
            with tempfile.TemporaryDirectory() as temporary:
                py_compile.compile(
                    str(source),
                    cfile=str(Path(temporary) / f"{source.stem}.pyc"),
                    doraise=True,
                )

    sibling = ROOT.parent / "UniXNU" / "scripts" / "porting-record.py"
    if sibling.is_file():
        subprocess.run(
            [sys.executable, str(sibling), "check", "--device", "."],
            cwd=ROOT,
            check=True,
        )
    else:
        print(f"note: sibling UniXNU checker not found at {sibling}; skipped")

    print("opd2515 repository: offline consistency checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
