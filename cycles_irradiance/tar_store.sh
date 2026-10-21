#!/bin/bash
# Tar the built patched Blender (portable install dir /tmp/cyc/build/bin) + patch/scripts into storage blender_irr/.
set -ex
ST=$(ls -d /srv/storage/graphdeco@storage1.sophia.*/user/ypoirier)
D=$ST/blender_irr; mkdir -p $D
T=blender-4.2.9-cycles-irradiance-linux-x64-sm90
tar -C /tmp/cyc/build --transform "s,^bin,$T," -czf $D/$T.tar.gz.tmp bin
mv $D/$T.tar.gz.tmp $D/$T.tar.gz
for f in cycles_irradiance.patch build.sh fetch.sh libs.sh cuda129.sh fix_cuda_hdr.sh val_render.py run_val.sh analyze.py NOTES.md; do
  [ -f /tmp/cyc/$f ] && cp /tmp/cyc/$f $D/
done
ls -la $D
echo TAR_DONE
