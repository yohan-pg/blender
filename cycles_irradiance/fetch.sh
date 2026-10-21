#!/bin/bash
# Fetch Blender 4.2.9 source + precompiled libs, CUDA 12.9 (12.8 headers clash with glibc 2.41 cospi/sinpi) toolkit (user space), OptiX headers into /tmp/cyc
set -ex
mkdir -p /tmp/cyc && cd /tmp/cyc
( [ -d cuda129 ] || { wget -q https://developer.download.nvidia.com/compute/cuda/12.9.1/local_installers/cuda_12.9.1_575.57.08_linux.run -O cuda.run && \
  sh cuda.run --silent --toolkit --toolkitpath=/tmp/cyc/cuda129 --no-man-page --override && rm cuda.run; } ) > cuda_install.log 2>&1 &
[ -d optix-dev ] || git clone --depth 1 --branch v8.0.0 https://github.com/NVIDIA/optix-dev.git
[ -d blender ] || git clone --depth 1 --branch v4.2.9 https://projects.blender.org/blender/blender.git
cd blender
git submodule status || true
git submodule update --init --depth 1 lib/linux_x64 || {
  git clone --depth 1 --branch blender-v4.2-release https://projects.blender.org/blender/lib-linux_x64.git lib/linux_x64; }
cd lib/linux_x64 && git lfs pull && cd ../..
du -sh lib/linux_x64
wait
cat /tmp/cyc/cuda_install.log | tail -5
/tmp/cyc/cuda129/bin/nvcc --version
echo FETCH_DONE
