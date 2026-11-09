#!/usr/bin/env python3
"""Install a DarwinBoot trust-cache bundle into the OPD2515 payload."""

import argparse
import shutil
import struct
import tempfile
from pathlib import Path

from pyfatfs.PyFatFS import PyFatFS


TRUST_PATH = "/EFI/UniXNU/Payloads/kernel.macho.trustcache"


def validate_bundle(data: bytes) -> None:
    if len(data) < 8:
        raise RuntimeError("trust-cache bundle is too short")
    count = struct.unpack_from("<I", data, 0)[0]
    if count == 0 or count > 128 or count > (len(data) - 4) // 4:
        raise RuntimeError("trust-cache bundle has an invalid module count")

    for index in range(count):
        start = struct.unpack_from("<I", data, 4 + index * 4)[0]
        end = (
            struct.unpack_from("<I", data, 8 + index * 4)[0]
            if index + 1 < count
            else len(data)
        )
        if (
            start < 4 + count * 4
            or start & 3
            or end > len(data)
            or end < start
            or end - start < 24
            or struct.unpack_from("<I", data, start)[0] != 2
        ):
            raise RuntimeError(f"trust-cache module {index} has an invalid range")
        entries = struct.unpack_from("<I", data, start + 20)[0]
        if entries > (end - start - 24) // 24 or end - start != 24 + entries * 24:
            raise RuntimeError(f"trust-cache module {index} has an invalid entry table")


def install_bundle(source: Path, bundle: Path, output: Path) -> None:
    payload = bundle.read_bytes()
    validate_bundle(payload)

    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        image = Path(temporary) / "payload.img"
        shutil.copyfile(source, image)

        with PyFatFS(str(image), read_only=False) as volume:
            if volume.exists(TRUST_PATH):
                volume.remove(TRUST_PATH)
            volume.writebytes(TRUST_PATH, payload)
            installed = volume.readbytes(TRUST_PATH)
            if installed != payload:
                raise RuntimeError("trust-cache readback mismatch")
            validate_bundle(installed)

        if output.exists():
            output.unlink()
        shutil.move(image, output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    install_bundle(args.source, args.bundle, args.output)


if __name__ == "__main__":
    main()
