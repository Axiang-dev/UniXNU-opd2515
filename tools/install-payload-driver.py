#!/usr/bin/env python3
"""Install the built DarwinBoot driver into an existing OPD2515 payload."""

import argparse
import shutil
import tempfile
from pathlib import Path

from pyfatfs.PyFatFS import PyFatFS


CONFIG_PATH = "/EFI/UniXNU/unixnu.toml"
DRIVER_PATH = "/EFI/UniXNU/Drivers/DarwinBoot.efi"
DRIVER_SECTION = '[[driver]]\npath = "Drivers/DarwinBoot.efi"\nconnect = false\n\n'


def install_driver(source: Path, driver: Path, output: Path) -> None:
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        image = Path(temporary) / "payload.img"
        shutil.copyfile(source, image)

        with PyFatFS(str(image), read_only=False) as volume:
            config = volume.readtext(CONFIG_PATH).replace("\r\n", "\n")
            if DRIVER_SECTION not in config:
                marker = "[[entry]]"
                if marker not in config:
                    raise RuntimeError("payload config has no entry section")
                config = config.replace(marker, DRIVER_SECTION + marker, 1)
                volume.writetext(CONFIG_PATH, config)

            volume.makedirs("/EFI/UniXNU/Drivers", recreate=True)
            if volume.exists(DRIVER_PATH):
                volume.remove(DRIVER_PATH)
            volume.writebytes(DRIVER_PATH, driver.read_bytes())

            installed = volume.readbytes(DRIVER_PATH)
            if installed != driver.read_bytes():
                raise RuntimeError("driver readback mismatch")
            if DRIVER_SECTION not in volume.readtext(CONFIG_PATH):
                raise RuntimeError("driver config readback mismatch")

        if output.exists():
            output.unlink()
        shutil.move(image, output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("driver", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    install_driver(args.source, args.driver, args.output)


if __name__ == "__main__":
    main()
