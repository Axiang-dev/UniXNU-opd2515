# OPD2515 repository guide

This is a standalone UniXNU device repository for the OPPO Pad mini 5G
(`opd2515`, SM8845P / Alor, OPD2515).

## Safety boundary

- Device tests use `fastboot boot` only.
- Never run `fastboot flash`, `erase`, `format`, or write any partition.
- Keep OrangeFox/REC and the stock GBL/BDS path intact.
- The only authorized persistent write is the existing 4 MiB diagnostic window
  at the tail of userdata. Never format userdata during bring-up.
- Enter BDS manually. Do not use `adb reboot bootloader`.

## Working rules

- Start from `STATE.md`, then `PROGRESS.md` and `porting.toml`.
- Do not claim MMU completion, kernel C startup, root mount, or iOS userland
  without direct evidence.
- Add each hardware observation to the matching `porting.toml` area.
- Keep `board.toml` and `porting.toml` identities synchronized.
- Preserve upstream pin `8ec13bb1077502e53e8ba3b82c56842589b5c837` unless the
  change is deliberately rebased and revalidated.
- Never commit `local.toml`, `UNIXNU_UNIQUE_CHIP_ID`, Apple IPSW contents, vendor
  firmware, keys, logs containing secrets, or generated build outputs.

## Validation

From the device repository, with a compatible UniXNU checkout at `../UniXNU`:

```sh
python3 ../UniXNU/scripts/porting-record.py check --device .
python3 scripts/verify.py
```