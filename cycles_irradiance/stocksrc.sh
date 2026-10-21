#!/bin/bash
# Build the UNPATCHED v4.2.9 Cycles with the identical toolchain/config (same build dir), save it as
# /tmp/cyc/bin_stocksrc, then re-apply the patch and rebuild so /tmp/cyc/build/bin is the patched build again.
set -ex
J=${1:-14}
cd /tmp/cyc/blender
git checkout -- intern/cycles
git status --short intern/cycles | head
nice -n 5 make -C /tmp/cyc/build -j$J install > /tmp/cyc/make_stocksrc.log 2>&1 || { grep -m5 "error" /tmp/cyc/make_stocksrc.log; exit 1; }
rm -rf /tmp/cyc/bin_stocksrc; cp -a /tmp/cyc/build/bin /tmp/cyc/bin_stocksrc
/tmp/cyc/bin_stocksrc/blender --version | head -1
git apply /tmp/cyc/cycles_irradiance.patch
nice -n 5 make -C /tmp/cyc/build -j$J install > /tmp/cyc/make_repatch.log 2>&1 || { grep -m5 "error" /tmp/cyc/make_repatch.log; exit 1; }
/tmp/cyc/build/bin/blender -b --python-expr "import bpy;print('HASPROP', hasattr(bpy.context.view_layer.cycles,'use_pass_irradiance'))" 2>&1 | grep HASPROP
/tmp/cyc/bin_stocksrc/blender -b --python-expr "import bpy;print('HASPROP', hasattr(bpy.context.view_layer.cycles,'use_pass_irradiance'))" 2>&1 | grep HASPROP
echo STOCKSRC_DONE
