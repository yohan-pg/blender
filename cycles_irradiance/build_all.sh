#!/bin/bash
# Full node build of the patched Blender: fetch -> libs -> CUDA 12.9 -> build (sm_90 + sm_120 cubins, OptiX) -> tar -> GPU check.
# Scripts + cycles_irradiance.patch must be in /tmp/cyc. Usage: bash /tmp/cyc/build_all.sh [jobs]
set -o pipefail
J=${1:-$(nproc)}; cd /tmp/cyc
for s in fetch libs cuda129; do echo "== $s $(date +%T)"; bash /tmp/cyc/$s.sh > /tmp/cyc/$s.log 2>&1 || { echo "FAIL $s"; tail -30 /tmp/cyc/$s.log; exit 1; }; tail -2 /tmp/cyc/$s.log; done
echo "== build $(date +%T) jobs=$J"; CUDA_ARCHS="sm_90;sm_120" bash /tmp/cyc/build.sh $J > /tmp/cyc/build.log 2>&1 || { echo "FAIL build"; tail -60 /tmp/cyc/build.log; exit 1; }; tail -12 /tmp/cyc/build.log
echo "== tar $(date +%T)"; DEST=/tmp/cyc/out bash /tmp/cyc/tar_store.sh > /tmp/cyc/tar.log 2>&1 || { echo "FAIL tar"; tail /tmp/cyc/tar.log; exit 1; }; tail -4 /tmp/cyc/tar.log
echo "== val $(date +%T)"; bash /tmp/cyc/bw_val.sh /tmp/cyc/build/bin/blender /tmp/cyc/bwval 256
echo "BUILD_ALL_DONE $(date +%T)"
