#!/system/bin/sh
#
# Copy the UniXNU boot log window (last 4 MiB of userdata) to /tmp so the host
# can pull it. Reads raw blocks on purpose: no mount, no filesystem access.
#
set -e

# The skip is computed on the host: Android sh uses 32-bit arithmetic and a
# 491 GB partition overflows it, which silently reads the wrong offset.
SKIP="$1"
[ -n "$SKIP" ] || { echo "usage: read-log-device.sh <skip-in-4096-byte-blocks>"; exit 1; }

P=/dev/block/by-name/userdata
[ -e "$P" ] || P=$(ls /dev/block/platform/*/by-name/userdata 2>/dev/null | head -n 1)
[ -n "$P" ] || P=$(ls /dev/block/bootdevice/by-name/userdata 2>/dev/null | head -n 1)
[ -b "$P" ] || { echo "no userdata block device"; exit 1; }

echo "userdata: $P"
echo "window:   $SKIP blocks of 4096 bytes"

dd if="$P" of=/tmp/unixnu-log.bin bs=4096 skip="$SKIP" count=1024
sync
wc -c /tmp/unixnu-log.bin
