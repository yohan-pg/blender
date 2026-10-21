#!/bin/bash
# Precompiled Linux libs at the exact submodule commit pinned by Blender v4.2.9
set -ex
cd /tmp/cyc/blender
SHA=$(git ls-tree HEAD lib/linux_x64 | awk '{print $3}')
rm -rf lib/linux_x64 && mkdir -p lib/linux_x64 && cd lib/linux_x64
git init -q && git remote add origin https://projects.blender.org/blender/lib-linux_x64.git
git -c lfs.fetchexclude= fetch --depth 1 origin $SHA
git checkout -q FETCH_HEAD
git lfs pull
du -sh .
echo LIBS_DONE
