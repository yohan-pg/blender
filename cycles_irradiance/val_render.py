"""Blender: one validation render of the authored camera with nvs_passes.setup_cycles settings.
Usage: blender -b X.blend --python val_render.py -- MODE SPP SEED OUT_PREFIX
 MODE  beauty  stock settings (plus data passes for pixel classes)
       irr     nvs_passes.to_irradiance(): camera rays see white Lambertian -> Combined = E/pi (two-pass method)
       onepass beauty + the patched build's Irradiance pass (view_layer.cycles.use_pass_irradiance)
Writes OUT_PREFIX.exr (multilayer, all passes, 32-bit), OUT_PREFIX.png (AgX display beauty) and prints
'VALTIME <render seconds>'."""
import bpy, sys, os, time
sys.path.insert(0, '/tmp/ever2')
import nvs_passes as NP
mode, spp, seed, out = sys.argv[sys.argv.index('--') + 1:][:4]
spp, seed = int(spp), int(seed)
sc = bpy.context.scene; r = sc.render; vl = sc.view_layers[0] if bpy.context.view_layer is None else bpy.context.view_layer
NP.setup_cycles(sc, spp, 'OPTIX')
sc.cycles.seed = seed
r.resolution_percentage = int(100 * 960 / r.resolution_x) if r.resolution_x > 960 else 100
if os.environ.get('VAL_DEVICE') == 'CPU':  # determinism check: CPU, no denoiser, small image
    sc.cycles.device = 'CPU'; sc.cycles.use_denoising = False
    r.resolution_percentage = max(1, r.resolution_percentage * int(os.environ.get('VAL_SCALE', '25')) // 100)
vl.use_pass_z = True; vl.use_pass_normal = True
if mode != 'irr':  # the pipeline's main render keeps the light passes; the irradiance render only needs Combined
    vl.use_pass_diffuse_color = vl.use_pass_glossy_color = vl.use_pass_transmission_color = True
    vl.use_pass_diffuse_direct = vl.use_pass_diffuse_indirect = True
    vl.use_pass_glossy_direct = vl.use_pass_glossy_indirect = True
    vl.use_pass_transmission_direct = vl.use_pass_transmission_indirect = True
    vl.use_pass_emit = True
if mode == 'irr':
    NP.to_irradiance()
if mode == 'onepass':
    vl.cycles.use_pass_irradiance = True
sc.use_nodes = False; r.use_compositing = False
t0 = time.time(); bpy.ops.render.render(); dt = time.time() - t0
im = r.image_settings; im.file_format = 'OPEN_EXR_MULTILAYER'; im.color_depth = '32'; im.exr_codec = 'ZIP'
bpy.data.images['Render Result'].save_render(out + '.exr', scene=sc)
im.file_format = 'PNG'; im.color_depth = '16'; im.color_mode = 'RGB'
bpy.data.images['Render Result'].save_render(out + '.png', scene=sc)
print('VALRES', r.resolution_x * r.resolution_percentage // 100, r.resolution_y * r.resolution_percentage // 100)
print('VALTIME', mode, spp, seed, '%.2f' % dt, flush=True)
