#!/bin/bash
# User-space CUDA 12.9.1 toolkit (12.8's crt/math_functions.h conflicts with Debian trixie glibc 2.41 cospi/sinpi)
set -ex
cd /tmp/cyc
[ -x cuda129/bin/nvcc ] || { wget -q https://developer.download.nvidia.com/compute/cuda/12.9.1/local_installers/cuda_12.9.1_575.57.08_linux.run -O cuda129.run && \
  sh cuda129.run --silent --toolkit --toolkitpath=/tmp/cyc/cuda129 --no-man-page --override && rm cuda129.run; }
cuda129/bin/nvcc --version | tail -2
echo CUDA_DONE
