#!/bin/bash
# Re-apply the (updated) patch onto a clean Cycles tree on the node.
set -e
cd /tmp/cyc/blender && git checkout -- intern/cycles && git apply /tmp/cyc/cycles_irradiance.patch && git diff --stat | tail -1
