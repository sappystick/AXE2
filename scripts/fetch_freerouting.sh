#!/bin/bash
# Fetch the pinned Freerouting jar used by src/pcb/freeroute.py (Maven Central: GitHub release downloads are blocked in the cloud containers).
# The SHA-256 is pinned; Maven's published SHA-1 (f00867db9c1772fa34fb38424c5d648cef8d7e62) matched on the first download, 2026-10-29.
# Needs Java 25+ to run (apt-get install openjdk-25-jre-headless).
set -e
V=2.4.1; SHA=fb2e91df901fa50cd23a09ab42793af0ece4f3b1f3857d6724dd6f9c0c00be98
D=$(cd "$(dirname "$0")/.." && pwd)/tools/freerouting; J=$D/freerouting-$V.jar
mkdir -p "$D"
if [ -f "$J" ] && echo "$SHA  $J" | sha256sum -c --quiet 2>/dev/null; then echo "[freerouting] $V present"; exit 0; fi
curl -sSfL -o "$J.part" "https://repo1.maven.org/maven2/app/freerouting/freerouting/$V/freerouting-$V-executable.jar"
echo "$SHA  $J.part" | sha256sum -c --quiet || { echo "[freerouting] checksum mismatch"; mv "$J.part" "$J.bad"; exit 1; }
mv "$J.part" "$J"; echo "[freerouting] $V fetched"
