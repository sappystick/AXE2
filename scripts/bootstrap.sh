#!/usr/bin/env bash
# AXE2: install every tool in a fresh container (or a Linux / WSL machine) and self-test. Idempotent; only adds packages; never removes any.
# usage: scripts/bootstrap.sh        (also the SessionStart hook in cloud sessions; make tools)
set -euo pipefail
cd "$(dirname "$0")/.."
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
export DEBIAN_FRONTEND=noninteractive
say() { echo "[bootstrap] $*"; }

# 1. KiCad 9 from the official PPA (added by hand: add-apt-repository is unreliable in cloud images)
if command -v kicad-cli >/dev/null 2>&1 && kicad-cli version 2>/dev/null | grep -q '^9\.'; then
  say "KiCad $(kicad-cli version) already installed"
else
  say "installing KiCad 9"
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq --no-install-recommends gnupg curl ca-certificates
  if [ ! -f /usr/share/keyrings/kicad9.gpg ]; then
    FP=$(curl -fsS "https://api.launchpad.net/devel/~kicad/+archive/ubuntu/kicad-9.0-releases" | python3 -c "import sys,json;print(json.load(sys.stdin)['signing_key_fingerprint'])")
    curl -fsS "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x${FP}" | gpg --dearmor | $SUDO tee /usr/share/keyrings/kicad9.gpg >/dev/null
  fi
  CODENAME=$(. /etc/os-release; echo "${VERSION_CODENAME}")
  echo "deb [signed-by=/usr/share/keyrings/kicad9.gpg] https://ppa.launchpadcontent.net/kicad/kicad-9.0-releases/ubuntu ${CODENAME} main" | $SUDO tee /etc/apt/sources.list.d/kicad9.list >/dev/null
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq --no-install-recommends kicad
fi

# 2. system tools: KiCad libraries + 3D models (3.3 GB), ngspice, ARM gcc (firmware), gmsh (meshing), off-screen OpenGL (renders), Java 25 (Freerouting)
NEED=""
for p in kicad-footprints kicad-symbols kicad-packages3d ngspice gcc-arm-none-eabi libnewlib-arm-none-eabi gmsh libosmesa6 libegl1 libgl1; do
  dpkg -s "$p" >/dev/null 2>&1 || NEED="$NEED $p"
done
if [ -n "$NEED" ]; then say "installing:$NEED"; $SUDO apt-get update -qq; $SUDO apt-get install -y -qq --no-install-recommends $NEED >/dev/null || say "WARNING: some system tools not installed"; fi
if ! ls /usr/lib/jvm/java-2[5-9]-openjdk*/bin/java >/dev/null 2>&1; then
  $SUDO apt-get install -y -qq --no-install-recommends openjdk-25-jre-headless >/dev/null 2>&1 || say "WARNING: openjdk-25 not installed: Freerouting unavailable (the A* router still works)"
fi

# 3. Python packages (pinned). Debian owns blinker; gerbonara -> quart -> flask wants blinker >= 1.9: a second copy is installed, nothing removed.
pipi() { pip install -q "$@" 2>/dev/null || pip install -q --break-system-packages "$@"; }
pipi --ignore-installed blinker
pipi -r requirements.txt

# 4. Freerouting (pinned jar from Maven Central, SHA-256 checked)
scripts/fetch_freerouting.sh >/dev/null 2>&1 || say "WARNING: Freerouting jar not fetched (the A* router still works)"

# 5. self-test: every tool the runner needs must answer
fail=0
chk() { if "$@" >/dev/null 2>&1; then :; else echo "[bootstrap] SELF-TEST FAILED: $*"; fail=1; fi; }
chk python3 -c "import numpy, scipy, matplotlib, PIL, gerbonara, shapely, manifold3d"
chk python3 -c "import kiutils, magpylib, trimesh, pyvista, cadquery, spicelib, meshio, skfem, optuna, pymupdf, rtree"
chk kicad-cli version
chk /usr/bin/python3 -c "import pcbnew"
chk ngspice --version
chk arm-none-eabi-gcc --version
chk gmsh --version
chk test -d /usr/share/kicad/3dmodels
say "python      $(python3 --version 2>&1) | numpy $(python3 -c 'import numpy;print(numpy.__version__)') scipy $(python3 -c 'import scipy;print(scipy.__version__)') shapely $(python3 -c 'import shapely;print(shapely.__version__)')"
say "kicad       $(kicad-cli version 2>&1 | head -1) | pcbnew $(/usr/bin/python3 -c 'import pcbnew;print(pcbnew.Version())' 2>&1 | tail -1)"
say "freerouting $(python3 -c 'import sys; sys.path.insert(0,"src/pcb"); import freeroute as F, os; print(F.VERSION, "jar ok" if os.path.exists(F.JAR) else "jar MISSING")' 2>/dev/null)"
say "tools       ngspice $(ngspice --version 2>/dev/null | grep -o 'ngspice-[0-9]*' | head -1) | gmsh $(gmsh --version 2>&1 | tail -1) | magpylib $(python3 -c 'import magpylib;print(magpylib.__version__)' 2>/dev/null) pyvista $(python3 -c 'import pyvista;print(pyvista.__version__)' 2>/dev/null) cadquery $(python3 -c 'import cadquery;print(cadquery.__version__)' 2>/dev/null)"
[ "$fail" -eq 0 ] && say "environment OK" || { say "environment INCOMPLETE"; exit 1; }
