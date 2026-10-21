#!/bin/bash
# Tar the built patched Blender (portable install dir /tmp/cyc/build/bin) + patch/scripts into DEST.
# Usage: [TARNAME=...] [DEST=dir] bash tar_store.sh
#  DEST defaults to sophia storage blender_irr/ when mounted, else /tmp/cyc/out (e.g. on nancy: pull it from there).
set -ex
ST=/srv/storage/graphdeco@storage1.sophia.grid5000.fr/user/ypoirier
if [ -z "$DEST" ]; then if [ -d $ST ]; then DEST=$ST/blender_irr; else DEST=/tmp/cyc/out; fi; fi
D=$DEST; mkdir -p $D
T=${TARNAME:-blender-4.2.9-cycles-irradiance-linux-x64-sm90-sm120}
tar -C /tmp/cyc/build --transform "s,^bin,$T," -czf $D/$T.tar.gz.tmp bin
mv $D/$T.tar.gz.tmp $D/$T.tar.gz
sha256sum $D/$T.tar.gz > $D/$T.tar.gz.sha256
for f in cycles_irradiance.patch build.sh fetch.sh libs.sh cuda129.sh fix_cuda_hdr.sh val_render.py run_val.sh analyze.py NOTES.md tar_store.sh; do
  [ -f /tmp/cyc/$f ] && cp /tmp/cyc/$f $D/
done
ls -la $D
echo TAR_DONE
