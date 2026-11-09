"""Pack an Android boot image v0 for `fastboot boot` (memory only).

Header layout follows AOSP mkbootimg for header_version 0. The loader on this
device only looks at the kernel field, but the image stays valid Android.
"""
import argparse
import hashlib
import struct
from pathlib import Path

PAGE = 4096


def pad(data, page=PAGE):
    return data + b"\0" * ((-len(data)) % page)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kernel")
    ap.add_argument("ramdisk")
    ap.add_argument("output")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0x10000000)
    ap.add_argument("--kernel-offset", type=lambda s: int(s, 0), default=0x8000)
    ap.add_argument("--ramdisk-offset", type=lambda s: int(s, 0), default=0x01000000)
    ap.add_argument("--tags-offset", type=lambda s: int(s, 0), default=0x100)
    ap.add_argument("--cmdline", default="")
    args = ap.parse_args()

    kernel = Path(args.kernel).read_bytes()
    ramdisk = Path(args.ramdisk).read_bytes()

    digest = hashlib.sha1()
    for blob in (kernel, ramdisk):
        digest.update(struct.pack("<I", len(blob)))
        digest.update(blob)
    image_id = digest.digest() + b"\0" * 12

    cmdline = args.cmdline.encode("ascii")[:511]
    header = struct.pack(
        "<8s10I16s512s32s1024s",
        b"ANDROID!",
        len(kernel),
        args.base + args.kernel_offset,
        len(ramdisk),
        args.base + args.ramdisk_offset,
        0,
        0,
        args.base + args.tags_offset,
        PAGE,
        0,
        0,
        b"",
        cmdline,
        image_id,
        b"",
    )

    image = pad(header) + pad(kernel) + pad(ramdisk)
    Path(args.output).write_bytes(image)
    print(f"{args.output}: {len(image)} bytes, kernel {len(kernel)}, ramdisk {len(ramdisk)}")
    print(f"id {image_id.hex()}")


if __name__ == "__main__":
    main()
