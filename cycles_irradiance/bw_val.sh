#!/bin/bash
# GPU check of a patched build with bw_val.py: pass off / on / two-pass reference, OptiX and CUDA devices.
# Usage: bash bw_val.sh [BLENDER] [OUT] [SPP]
B=${1:-/tmp/cyc/build/bin/blender}; O=${2:-/tmp/cyc/bwval}; S=${3:-256}; P=$(dirname $0)/bw_val.py
mkdir -p $O; nvidia-smi --query-gpu=name,compute_cap,driver_version --format=csv,noheader
for D in OPTIX CUDA; do
 for M in off on two; do
  SFX=_$D $B -b --factory-startup --python $P -- $M $D $O $S > $O/${M}_$D.log 2>&1; echo "exit=$? $(grep -h -E '^BWVAL|Error|rror:|Traceback|CUDA error|OPTIX_ERROR' $O/${M}_$D.log | grep -v 'Not freed' | head -4 | tr '\n' ' ')"
 done
 grep -h '^SOCKETS' $O/on_$D.log | head -1
 SFX=_$D $B -b --factory-startup --python $P -- cmp $D $O 2>&1 | grep -E '^CMP|Error|Traceback'
done
echo BWVAL_DONE
