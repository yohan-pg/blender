#!/bin/bash
# Validation renders of AI43_001 (authored camera, 960 px wide, nvs_passes.setup_cycles), stock vs patched build.
# Usage: bash run_val.sh [JOBS...]   JOB = bin:mode:spp:seed  (bin = stock|patched)
ST=$(ls -d /srv/storage/graphdeco@storage1.sophia.*/user/ypoirier)
SCENE=${SCENE:-$ST/scenes_fixed/AI43_001.blend}
V=/tmp/cyc/val; mkdir -p $V
# stocksrc = unpatched v4.2.9 built with the same toolchain as patched (isolates patch effects from codegen)
declare -A BIN=([stock]=/tmp/ypsel/blender/blender [patched]=/tmp/cyc/build/bin/blender [stocksrc]=/tmp/cyc/bin_stocksrc/blender)
TAG=${TAG:-}
JOBS=${@:-"stock:beauty:256:0 patched:onepass:256:0 stock:irr:256:0 stock:beauty:64:0 patched:onepass:64:0 stock:irr:64:0 patched:beauty:256:0 stock:beauty:256:1 stock:irr:2048:7 stock:beauty:2048:7"}
for j in $JOBS; do
  IFS=: read b m s seed <<< "$j"
  o=$V/${TAG}${b}_${m}_${s}_${seed}
  t0=$(date +%s.%N)
  ${BIN[$b]} -b "$SCENE" --python /tmp/cyc/val_render.py -- $m $s $seed $o > $o.log 2>&1; rc=$?
  t1=$(date +%s.%N)
  echo "JOB $j exit=$rc wall=$(echo "$t1 - $t0" | bc) $(grep -h '^VALTIME\|^VALRES' $o.log | tr '\n' ' ') $(grep -h -m3 'Error\|Traceback' $o.log | tr '\n' ' ')"
done
echo VAL_DONE
