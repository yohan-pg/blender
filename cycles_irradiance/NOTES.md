# Cycles "Irradiance" pass: exact E/pi in one render (Blender 4.2.9 LTS)

## What it does
A new render pass, **Irradiance**, is enabled per view layer with `view_layer.cycles.use_pass_irradiance = True`.
When the pass is enabled, the denoiser also outputs **Noisy Irradiance**.

The pass holds E/pi at the first camera hit. E is the full cosine-weighted incident radiance (direct + indirect,
around the shading normal `sd->N`). This is the same quantity `nvs_passes.to_irradiance()` computes with its second
render (a white Lambertian seen by camera rays). It is defined on every surface type: dielectrics, metals, glass,
emitters and alpha/transparent surfaces. On alpha/transparent surfaces it is taken at the first surface hit, like the
two-pass method.

**Background pixels are 0** (undefined). The two-pass method shows the world colour there.
Emitters get the light incident on them (E/pi), not their emission. This also matches the two-pass method.

The feature is **opt-in**. With the pass off, the patched build is bit-identical to unpatched 4.2.9 built with the
same toolchain: on CPU, all passes, NaNs included. On GPU, run-to-run nondeterminism is identical for both builds.

## Design (why a virtual closure, not a "diffuse lobe in the material")
At the first camera hit (`bounce == 0`, `transparent_bounce == 0`, `PATH_RAY_CAMERA`), the kernel appends one
virtual closure, `CLOSURE_BSDF_IRRADIANCE_ID`, to the shader's closure list. It is a white Lambert at `sd->N` and
reuses the diffuse sample/eval code.
- **Contribution weight w = 1e-3**, so it is imperceptible in beauty. Beauty stays unbiased because Cycles'
  one-sample MIS picks closures by `sample_weight` but weights the estimate by `weight`.
- **Sample weight is adaptive.** The lobe gets fraction f = 0.35 of the BSDF picks, counting existing
  Diffuse/Oren-Nayar closures towards it. It always gets at least fmin = 0.05. On pure metal or glass about 35% of
  camera samples are cosine-sampled for the pass, so the pass is "well sampled" without changing the look.
- **Its own closure ID**, so it never leaks into DiffDir/GlossDir/etc. Light-pass bookkeeping (`BsdfEval`) gets an
  `irradiance` component. The path carries `pass_irradiance_weight = eval.irradiance / eval.sum / w`, and the
  shadow state carries it for NEE. Every emission/direct-light write adds `w * pass_irradiance_weight *
  contribution` to the pass (self-normalised: the result is E/pi directly) and subtracts that share from the
  transmission split.
- **Russian roulette** at bounce >= 1 on irradiance paths uses max(|T|, |T x irr_w|). Without this, paths that went
  through the 1e-3 lobe would almost always be killed (the throughput is about 1e-3). Beauty stays unbiased; paths
  are a bit longer.
- **Denoising features** (albedo/normal) are written *before* injection, so data passes and DiffCol are unchanged.
  Specular primary hits defer their features. If the virtual lobe is picked, the deferral is cleared; otherwise
  the feature throughput is rescaled by S/(S - s_v) to stay unbiased.
- The pass is OptiX/OIDN-denoisable with a fake albedo (like the shadow catcher), so both "Irradiance" (denoised)
  and "Noisy Irradiance" exist.

Why not divide DiffDir+DiffInd by DiffCol? That gives 0/0 on metal and glass. It also suffers bump-normal mismatch,
ratio-of-sums at anti-aliased edges, and SSS/translucent contamination.

## Files / functions patched (cycles_irradiance.patch, 22 files)
- `kernel/svm/types.h`: `CLOSURE_BSDF_IRRADIANCE_ID`.
- `kernel/closure/bsdf.h`: sample/eval/label/roughness reuse the diffuse cases.
- `kernel/types.h`: `PASS_IRRADIANCE`; `BsdfEval::irradiance`.
- `kernel/data_template.h`: KernelFilm `pass_irradiance`, `irradiance_weight`, `irradiance_sample_fraction`,
  `irradiance_min_fraction`, `irradiance_rr`.
- `kernel/integrator/state_template.h`, `shadow_state_template.h`: `pass_irradiance_weight`.
- `kernel/film/light_passes.h`:
  - `bsdf_eval_init/accum/mul` gain the irradiance component;
  - new `bsdf_eval_pass_irradiance_weight()` and `film_irradiance_share()`;
  - irradiance writes in `film_write_emission_or_background_pass` and `film_write_direct_light`.
- `kernel/integrator/surface_shader.h`:
  - new `surface_shader_add_irradiance_closure()`;
  - `_surface_shader_exclude` treats the closure like diffuse.
- `kernel/integrator/shade_surface.h`:
  - injection after `film_write_denoising_features_surface`;
  - NEE shadow state;
  - bounce-0 weight;
  - denoising-feature compensation.
- `kernel/integrator/path_state.h`: init; RR.
- `subsurface.h`, `shade_volume.h`, `shade_dedicated_light.h`: zero/copy the weight.
- `scene/film.cpp`:
  - pass offset;
  - kernel-feature range;
  - env-var tuning;
  - auto NOISY pass.
- `scene/pass.cpp`: pass info. `scene/scene.cpp`: max_closures + 1 when the pass is on.
- `integrator/denoiser_gpu.cpp`, `denoiser_oidn.cpp`: denoise PASS_IRRADIANCE.
- `blender/sync.cpp`: MAP_PASS "Irradiance" / "Noisy Irradiance".
- `blender/addon/properties.py`, `engine.py`, `ui.py`: `use_pass_irradiance`.

Tuning env vars (read at render time): `CYCLES_IRRADIANCE_WEIGHT` (1e-3), `CYCLES_IRRADIANCE_FRACTION` (0.35),
`CYCLES_IRRADIANCE_MIN_FRACTION` (0.05), `CYCLES_IRRADIANCE_RR` (1).

## Build (node, everything under /tmp/cyc)
1. `fetch.sh`: Blender v4.2.9 source and optix-dev v8.0.0.
2. `libs.sh`: lib/linux_x64 at the pinned submodule SHA, plus LFS.
3. `cuda129.sh`: CUDA 12.9.1 toolkit into /tmp/cyc/cuda129.
4. `bash build.sh 14`. It applies the patch and runs `fix_cuda_hdr.sh`. That script adds noexcept to
   sinpi/cospi in the CUDA headers, needed for glibc 2.41. build.sh also pulls Debian GL headers for OpenSubdiv,
   then runs a headless cmake (CUDA sm_90 cubin + OptiX PTX) and `make install`. The result is `/tmp/cyc/build/bin/blender`.
5. `tar_store.sh` stores `blender_irr/blender-4.2.9-cycles-irradiance-linux-x64-sm90.tar.gz` (396 MB) plus the patch and
   scripts. To use it: untar, then run `<dir>/blender -b ...`. sm_90 only; other GPUs JIT from OptiX PTX / need CUDA.

Toolchain: Debian trixie, gcc 14.2, glibc 2.41, cmake 3.31, CUDA 12.9.1, OptiX 8.0 headers, driver 580.

## Validation (AI43_001, authored camera, 952x649, nvs_passes.setup_cycles, OptiX, H100 shared with other jobs)
Scripts: `run_val.sh` / `val_render.py` render; `analyze.py VALDIR OUT.json OUT.jpg` analyses. Raw numbers are in
`cycles_irr_patch.json`.

Pixel classes come from the stock 2048-spp passes: dielectric 584,583; metal 24,446; glass 8,793; background 0.
References: stock two-pass irradiance and beauty at 2048 spp.

### Irradiance, relative MAE (bias in parentheses)
| | one-pass vs two-pass | one-pass vs ref2048 | two-pass vs ref2048 |
|---|---|---|---|
| 256 denoised, dielectric | 1.4% | 3.3% (+0.5%) | 3.0% (+0.0%) |
| 256 denoised, metal | 4.0% | 5.6% (+0.4%) | 4.5% (-0.1%) |
| 256 denoised, glass | 3.3% | 5.4% (+0.2%) | 4.4% (+0.0%) |
| 256 noisy, dielectric | 6.5% | 8.6% (0.0%) | 7.8% (0.0%) |
| 256 noisy, metal | 11.5% | 12.7% (+0.1%) | 9.3% (0.0%) |
| 256 noisy, glass | 12.7% | 14.7% (-0.3%) | 10.0% (0.0%) |
| 64 denoised, dielectric | 1.9% | 3.9% (+0.6%) | 3.5% (+0.1%) |
| 64 denoised, metal | 5.7% | 7.7% (+0.3%) | 5.8% (-0.4%) |
| 64 denoised, glass | 5.0% | 6.9% (-0.1%) | 5.3% (0.0%) |
| 64 noisy, dielectric | 12.6% | 16.8% (0.0%) | 15.3% (0.1%) |
| 64 noisy, metal | 22.7% | 24.7% (+0.3%) | 18.0% (0.0%) |
| 64 noisy, glass | 24.8% | 28.7% (-0.5%) | 19.8% (+0.1%) |

The noisy one-pass estimate is unbiased (|bias| <= 0.5%, within noise). Variance at equal spp is about 1.1x
(dielectric) to 1.4x (metal, glass) that of the dedicated pass, because only about 35% of samples go to the lobe on
specular surfaces. Denoised one-pass shows a consistent +0.4..0.6% bias versus the reference: the OptiX denoiser with
a fake albedo is slightly biased, while the noisy pass is not.

### Beauty, patched (pass on) vs stock, same seed
- Display PSNR is 46.6 dB. Stock seed 0 vs stock seed 1 gives 41.3 dB, so the patched/stock difference is below
  seed-to-seed noise.
- The linear mean differs by +0.11% (seed-to-seed: -0.02%).
- Noisy-beauty RMSE vs ref2048, patched/stock: dielectric 0.92x, all foreground 0.93x, metal 1.085x, glass 1.10x.
  The dielectric gain comes from the RR change (longer paths); metal/glass lose some samples to the lobe.
- Pass off: bit-identical to unpatched source with the same toolchain on CPU (all passes). On GPU, unpatched vs
  unpatched rerun gives a max |diff| of 6.5e-3, the same spread as patched vs patched (GPU float nondeterminism).
  The official stock binary differs by about 1e-3 because of codegen (different compiler/CUDA).

### Time (render seconds, excluding scene load; node shared, so noisy)
| spp | stock beauty | stock irr render | two-pass total | patched one-pass | patched beauty (pass off) |
|---|---|---|---|---|---|
| 256 | 10.5 (12.9/9.0/9.6) | 9.5 (9.7/9.4) | **20.0** | **10.7** (11.2/10.3) | 10.6 (10.7/11.7/10.1/10.0) |
| 64 | 6.2 | 4.9 | **11.1** | **5.5** | - |

Including Blender start-up and scene load (about 3 s each), wall time at 256 spp is about 28 s for the two-pass
method vs about 14 s for one pass. One-pass is about 1.9-2x faster.

## Caveats
- With the pass on, beauty is not bit-identical to stock. It is unbiased, and per-pixel noise changes as above
  (metal/glass +9-10% RMSE).
- The pass needs KERNEL_FEATURE_LIGHT_PASSES, which is enabled automatically. The closure array grows by 1.
- Background = 0. Volume primary scatter, BSSRDF bounce-0 and MNEE paths contribute 0 to the pass (weight zeroed).
  Path guiding was not handled or tested (off in setup_cycles).
- `filter_glossy` / clamping affect the pass exactly as in the two-pass method (both are off in setup_cycles).
- The lobe uses `sd->N`: the interpolated shading normal, including material-output displacement bump, but not
  per-BSDF Normal inputs such as normal maps. This matches the white Diffuse BSDF of to_irradiance(), which has no
  normal input. The 5% minimum lobe share limits fireflies on surfaces whose own BSDF is not
  diffuse.
- Built for sm_90 (H100) only; other GPUs would need an OptiX PTX JIT or a rebuild with CYCLES_CUDA_BINARIES_ARCH.
- Stock Cycles itself writes a few NaNs into the Dir light passes (150-250 px at 238x162 on this scene); this is
  unchanged by the patch.
- The harmless addon traceback (`update_pause ... tag_redraw`) occurs in the stock binary as well.
