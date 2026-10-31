#!/usr/bin/env bash
# Build FastHenry2 and FastCap2 (MIT / FastFieldSolvers, github.com/ediloren) into /opt/solvers. Idempotent; non-fatal for the caller.
# The 1990s C needs legacy flags; FastCap needs 'static' removed from functions declared implicitly before their definition.
set -uo pipefail
D=/opt/solvers; mkdir -p "$D"; F='-O2 -std=gnu89 -w -fcommon -fpermissive -Wno-implicit-function-declaration -Wno-incompatible-pointer-types -Wno-int-conversion -Wno-implicit-int -Wno-return-mismatch'
build() {   # $1 repo, $2 binary
  [ -x "$D/$1/bin/$2" ] && return 0
  [ -d "$D/$1" ] || git clone --depth 1 "https://github.com/ediloren/$1.git" "$D/$1" >/dev/null 2>&1 || return 1
  for i in 1 2 3 4 5 6 7 8; do
    out=$(make -C "$D/$1" all CFLAGS="$F" 2>&1 | grep -E "error: static declaration of" || true)
    [ -z "$out" ] && break
    echo "$out" | sed -E "s/^([^:]+):([0-9]+):.*/\1 \2/" | while read -r f l; do sed -i "${l}s/^static //" "$D/$1/src/$(basename "$f")" 2>/dev/null || sed -i "${l}s/^static //" "$f"; done
  done
  make -C "$D/$1" all CFLAGS="$F" >/dev/null 2>&1; [ -x "$D/$1/bin/$2" ]
}
build FastHenry2 fasthenry && echo "fasthenry ok" || echo "fasthenry FAILED"
build FastCap2 fastcap && echo "fastcap ok" || echo "fastcap FAILED"
