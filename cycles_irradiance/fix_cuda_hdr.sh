#!/bin/bash
# CUDA 12.x crt/math_functions.h vs glibc >= 2.41 (sinpi/cospi now declared noexcept in mathcalls.h).
# Add noexcept(true) to the four CUDA declarations in OUR private toolkit copy (/tmp/cyc/cuda129).
set -e
f=/tmp/cyc/cuda129/targets/x86_64-linux/include/crt/math_functions.h
[ -f $f.orig ] || cp $f $f.orig
sed -i -E 's/^(extern __DEVICE_FUNCTIONS_DECL__ __device_builtin__ (double|float) +(sinpi|cospi|sinpif|cospif)\((double|float) x\));/\1 noexcept(true);/' $f
grep -n "sinpi(double x)\|cospi(double x)\|sinpif(float x)\|cospif(float x)" $f
