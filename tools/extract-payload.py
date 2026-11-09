"""Extract the ramdisk section of an Android boot image into a file."""
import argparse
import struct
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("output")
    args = ap.parse_args()

    data = Path(args.image).read_bytes()
    magic, kernel_size, _ka, ramdisk_size, _ra = struct.unpack_from("<8s4I", data, 0)
    page_size = struct.unpack_from("<I", data, 36)[0]
    header_version = struct.unpack_from("<I", data, 40)[0]
    if magic != b"ANDROID!":
        raise SystemExit("not an Android boot image")
    if header_version >= 3:
        raise SystemExit("header v3/v4 is not supported by this helper")

    offset = page_size + (kernel_size + page_size - 1) // page_size * page_size
    Path(args.output).write_bytes(data[offset:offset + ramdisk_size])
    print(f"{args.output}: {ramdisk_size} bytes from {args.image} @ {offset}")


if __name__ == "__main__":
    main()
