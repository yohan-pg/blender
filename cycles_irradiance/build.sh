#!/bin/bash
# Configure + build a headless Blender 4.2.9 with the Cycles irradiance patch (CUDA cubins + OptiX PTX).
# Usage: [CUDA_ARCHS="sm_90;sm_120"] bash build.sh [jobs]   (sm_90 = H100, sm_120 = Blackwell RTX PRO 6000; CUDA >= 12.8)
set -ex
J=${1:-12}
ARCHS=${CUDA_ARCHS:-"sm_90;sm_120"}
SRC=/tmp/cyc/blender BUILD=/tmp/cyc/build
cd $SRC
if ! grep -q CLOSURE_BSDF_IRRADIANCE_ID intern/cycles/kernel/svm/types.h; then
  git apply --check /tmp/cyc/cycles_irradiance.patch
  git apply /tmp/cyc/cycles_irradiance.patch
fi
git diff --stat | tail -1
export PATH=/tmp/cyc/cuda129/bin:$PATH
# CUDA 12.x headers clash with glibc 2.41 (sinpi/cospi noexcept): patch our private toolkit copy
bash /tmp/cyc/fix_cuda_hdr.sh
# OpenSubdiv's headers include <GL/gl.h>: no system GL headers on the node, use Debian's (headers only, no root)
if [ ! -f /tmp/cyc/glinc/GL/gl.h ]; then
  mkdir -p /tmp/cyc/debs /tmp/cyc/glinc && cd /tmp/cyc/debs
  apt-get download libgl-dev libglx-dev libegl-dev libgles-dev libglvnd-core-dev
  for f in *.deb; do dpkg-deb -x $f /tmp/cyc/sysroot; done
  cp -r /tmp/cyc/sysroot/usr/include/{GL,KHR,EGL,GLES,GLES2,GLES3} /tmp/cyc/glinc/ 2>/dev/null || true
  cd $SRC
fi
cmake -S $SRC -B $BUILD -G "Unix Makefiles" \
  -C $SRC/build_files/cmake/config/blender_headless.cmake \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_FLAGS="-isystem /tmp/cyc/glinc" -DCMAKE_CXX_FLAGS="-isystem /tmp/cyc/glinc" \
  -DWITH_LIBS_PRECOMPILED=ON \
  -DWITH_GHOST_X11=OFF -DWITH_GHOST_WAYLAND=OFF \
  -DWITH_INSTALL_PORTABLE=ON -DWITH_PYTHON_INSTALL=ON \
  -DWITH_CYCLES_DEVICE_CUDA=ON -DWITH_CYCLES_CUDA_BINARIES=ON -DCYCLES_CUDA_BINARIES_ARCH="$ARCHS" \
  -DWITH_CYCLES_DEVICE_OPTIX=ON -DOPTIX_ROOT_DIR=/tmp/cyc/optix-dev \
  -DCUDA_TOOLKIT_ROOT_DIR=/tmp/cyc/cuda129 -DCUDA_NVCC_EXECUTABLE=/tmp/cyc/cuda129/bin/nvcc \
  -DWITH_CYCLES_DEVICE_HIP=OFF -DWITH_CYCLES_HIP_BINARIES=OFF -DWITH_CYCLES_DEVICE_HIPRT=OFF \
  -DWITH_CYCLES_DEVICE_ONEAPI=OFF -DWITH_CYCLES_ONEAPI_BINARIES=OFF \
  -DWITH_USD=OFF -DWITH_HYDRA=OFF -DWITH_MATERIALX=OFF -DWITH_CYCLES_HYDRA_RENDER_DELEGATE=OFF \
  -DWITH_GTESTS=OFF -DWITH_OPENCOLLADA=OFF 2>&1 | tail -40
nice -n 5 make -C $BUILD -j$J install > /tmp/cyc/make.log 2>&1 || { grep -n -B2 -A8 "error" /tmp/cyc/make.log | head -120; exit 1; }
tail -3 /tmp/cyc/make.log
test -x $BUILD/bin/blender
ls $BUILD/bin/4.2/scripts/addons_core/cycles/lib/ 2>/dev/null || find $BUILD/bin -name "kernel_*.cubin*" -o -name "kernel_optix*" | head
$BUILD/bin/blender --version | head -2
echo BUILD_DONE
