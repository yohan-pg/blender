"""Self-contained GPU check of the patched build (no scene files needed, e.g. on a Blackwell node).
Builds a small test scene (diffuse floor/walls, textured cube, metal + glass spheres, area light, dim world) and renders:
  off   pass off, beauty                         -> OUT/off_Image.exr
  on    pass on: beauty + Irradiance + Noisy     -> OUT/on_{Image,Irradiance,NoisyIrradiance}.exr
  two   reference two-pass method (camera rays see white Lambert, nvs_passes.to_irradiance) -> OUT/two_Image.exr
  cmp   loads the EXRs and prints CMP lines (rel MAE / bias of Irradiance vs two-pass, beauty on vs off)
Usage: blender -b --factory-startup --python bw_val.py -- MODE DEVICE(OPTIX|CUDA) OUT [SPP]"""
import bpy,sys,os,time,glob
import numpy as np
mode,dev,out=sys.argv[sys.argv.index('--')+1:][:3];spp=int(sys.argv[sys.argv.index('--')+4])if len(sys.argv)>sys.argv.index('--')+4 else 256
os.makedirs(out,exist_ok=True);W,H=480,270
def load(p):
 im=bpy.data.images.load(p);a=np.array(im.pixels[:],np.float64).reshape(im.size[1],im.size[0],im.channels)[...,:3];bpy.data.images.remove(im);return a
if mode=='cmp':
 sfx=os.environ.get('SFX','')
 two=load(f'{out}/two{sfx}_Image.exr');irr=load(f'{out}/on{sfx}_Irradiance.exr');irn=load(f'{out}/on{sfx}_NoisyIrradiance.exr');bon=load(f'{out}/on{sfx}_Image.exr');boff=load(f'{out}/off{sfx}_Image.exr')
 m=irr.sum(-1)>0;m3=np.repeat(m[...,None],3,-1)
 r=lambda a,b:(np.abs(a-b)[m3].sum()/np.abs(b)[m3].sum(),a[m3].sum()/b[m3].sum()-1)
 print('CMP fg_frac %.3f'%m.mean(),'irr_denoised_vs_twopass rmae %.4f bias %+.4f'%r(irr,two),'irr_noisy_vs_twopass rmae %.4f bias %+.4f'%r(irn,two),
  'beauty_on_vs_off rmae %.4f bias %+.4f'%r(bon,boff),'irr_mean %.4f'%irr[m3].mean(),'nan',int(np.isnan(irr).sum()+np.isnan(bon).sum()),flush=True);raise SystemExit
sc=bpy.context.scene
for o in list(bpy.data.objects):
 if o.type!='CAMERA':bpy.data.objects.remove(o,do_unlink=True)
def mat(name,**kw):
 m=bpy.data.materials.new(name);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF']
 for k,v in kw.items():b.inputs[k].default_value=v
 return m,b
def add(op,mt,**kw):getattr(bpy.ops.mesh,op)(**kw);o=bpy.context.object;o.data.materials.append(mt);return o
floor,_=mat('floor',**{'Base Color':(.6,.55,.5,1),'Roughness':.6})
add('primitive_plane_add',floor,size=12)
wall,_=mat('wall',**{'Base Color':(.7,.7,.75,1),'Roughness':.9})
for loc,rot in(((0,4,3),(1.5708,0,0)),((-4,0,3),(0,1.5708,0))):add('primitive_plane_add',wall,size=8,location=loc,rotation=rot)
cube,b=mat('cube',**{'Roughness':.4});ck=cube.node_tree.nodes.new('ShaderNodeTexChecker');ck.inputs['Scale'].default_value=6;cube.node_tree.links.new(ck.outputs[0],b.inputs['Base Color'])
add('primitive_cube_add',cube,size=1.2,location=(-1.2,.8,.6))
metal,_=mat('metal',**{'Base Color':(.95,.75,.5,1),'Metallic':1.,'Roughness':.15});add('primitive_uv_sphere_add',metal,radius=.7,location=(.6,1.2,.7));bpy.ops.object.shade_smooth()
glass,_=mat('glass',**{'Transmission Weight':1.,'Roughness':0.,'IOR':1.45});add('primitive_uv_sphere_add',glass,radius=.6,location=(1.6,-.2,.6));bpy.ops.object.shade_smooth()
bpy.ops.object.light_add(type='AREA',location=(1,-1,4));L=bpy.context.object;L.data.energy=600;L.data.size=1.5
w=bpy.data.worlds.new('w');w.use_nodes=True;w.node_tree.nodes['Background'].inputs['Strength'].default_value=.3;sc.world=w
cam=sc.camera;cam.location=(5.5,-6,3.2);cam.rotation_euler=(1.2,0,.72)
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type=dev;prefs.get_devices()
for d in prefs.devices:d.use=d.type==dev
print('DEVICES',[(d.name,d.type,d.use)for d in prefs.devices],flush=True);assert any(d.use for d in prefs.devices),'no '+dev+' device'
cy=sc.cycles;r=sc.render;r.engine='CYCLES';cy.device='GPU';cy.samples=spp;cy.use_adaptive_sampling=False;cy.use_denoising=True;cy.denoiser='OPTIX' if dev=='OPTIX' else 'OPENIMAGEDENOISE'
cy.max_bounces=cy.diffuse_bounces=cy.glossy_bounces=cy.transmission_bounces=32;cy.sample_clamp_direct=cy.sample_clamp_indirect=0;cy.seed=0
r.resolution_x,r.resolution_y,r.resolution_percentage=W,H,100;r.film_transparent=False
vl=bpy.context.view_layer
if mode=='on':vl.cycles.use_pass_irradiance=True
if mode=='two':
 for m in bpy.data.materials:
  if not m.use_nodes:continue
  nt=m.node_tree;o=nt.nodes['Material Output'];src=o.inputs['Surface'].links[0].from_socket
  lp=nt.nodes.new('ShaderNodeLightPath');wd=nt.nodes.new('ShaderNodeBsdfDiffuse');wd.inputs['Color'].default_value=(1,1,1,1);mx=nt.nodes.new('ShaderNodeMixShader')
  nt.links.new(lp.outputs['Is Camera Ray'],mx.inputs[0]);nt.links.new(src,mx.inputs[1]);nt.links.new(wd.outputs[0],mx.inputs[2]);nt.links.new(mx.outputs[0],o.inputs['Surface'])
sc.use_nodes=True;r.use_compositing=True;t=sc.node_tree
for x in list(t.nodes):t.nodes.remove(x)
rl=t.nodes.new('CompositorNodeRLayers');cp=t.nodes.new('CompositorNodeComposite');t.links.new(rl.outputs['Image'],cp.inputs['Image'])
fo=t.nodes.new('CompositorNodeOutputFile');fo.base_path=out;fo.format.file_format='OPEN_EXR';fo.format.color_depth='32';fo.file_slots.clear()
sfx=os.environ.get('SFX','')
socks=['Image']+(['Irradiance','Noisy Irradiance']if mode=='on'else[])
print('SOCKETS',[s.name for s in rl.outputs if s.enabled],flush=True)
for s in socks:
 lab=f'{mode}{sfx}_{s.replace(" ","")}_';fo.file_slots.new(lab);t.links.new(rl.outputs[s],fo.inputs[lab])
t0=time.time();res=bpy.ops.render.render();dt=time.time()-t0
for p in glob.glob(f'{out}/{mode}{sfx}_*_0001.exr'):os.replace(p,p.replace('_0001.exr','.exr').replace('_.exr','.exr'))
print('BWVAL',mode,dev,spp,res,'render_s %.2f'%dt,sorted(os.path.basename(p)for p in glob.glob(f'{out}/{mode}{sfx}_*.exr')),flush=True)
