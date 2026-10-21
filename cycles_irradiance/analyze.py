"""Compare stock two-pass irradiance vs the patched one-pass Irradiance pass, and stock vs patched beauty.
Usage: python analyze.py VALDIR OUT.json OUT.jpg   (needs numpy, OpenEXR, PIL)"""
import sys, json, numpy as np, OpenEXR
from PIL import Image, ImageDraw
V, OUTJ, OUTS = sys.argv[1:4]
L = 'RenderLayer.'
def load(name):
    f = OpenEXR.File(f'{V}/{name}.exr'); ch = f.parts[0].channels
    d = {}
    for k, v in ch.items():
        k = k[len(L):] if k.startswith(L) else k
        d[k] = np.asarray(v.pixels, np.float64)
    return d
def rgb(d, p):
    if p in d and d[p].ndim == 3: return d[p][..., :3]
    return np.stack([d[f'{p}.{c}'] for c in 'RGB'], -1)
def lum(x): return x @ np.array([.2126, .7152, .0722])
def png(name): return np.asarray(Image.open(f'{V}/{name}.png').convert('RGB'), np.float64) / 255.
def psnr(a, b): return float(10 * np.log10(1. / np.mean((a - b) ** 2)))

ref_b = load('stock_beauty_2048_7')
dc, gc, tc = lum(rgb(ref_b, 'DiffCol')), lum(rgb(ref_b, 'GlossCol')), lum(rgb(ref_b, 'TransCol'))
z = ref_b['Depth.Z'] if 'Depth.Z' in ref_b else ref_b['Depth']
emit = lum(rgb(ref_b, 'Emit'))
bg = z > 1e9
glass = (tc > .05) & ~bg
metal = (dc < .01) & (tc < .01) & (gc > .02) & ~bg
emitter = (emit > .01) & ~bg & ~glass & ~metal
diel = (dc >= .01) & (tc <= .05) & ~bg & ~emitter
classes = {'dielectric': diel, 'metal': metal, 'glass': glass, 'emitter': emitter, 'all_fg': ~bg}
res = {'pixels': {k: int(v.sum()) for k, v in classes.items()}, 'background_pixels': int(bg.sum())}
print('pixels', res['pixels'], 'bg', int(bg.sum()))

ref_irr = lum(rgb(load('stock_irr_2048_7'), 'Noisy Image'))
def stats(a, b):
    out = {}
    for k, m in classes.items():
        if m.sum() == 0: continue
        aa, bb = a[m], b[m]
        out[k] = {'rel_mae': float(np.abs(aa - bb).mean() / bb.mean()), 'rel_rmse': float(np.sqrt(((aa - bb) ** 2).mean()) / bb.mean()),
                  'bias': float(aa.mean() / bb.mean() - 1)}
    return out
irr = {}
for spp in (256, 64):
    two, one = load(f'stock_irr_{spp}_0'), load(f'patched_onepass_{spp}_0')
    for den, p2, p1 in (('denoised', 'Combined', 'Irradiance'), ('noisy', 'Noisy Image', 'Noisy Irradiance')):
        a1, a2 = lum(rgb(one, p1)), lum(rgb(two, p2))
        irr[f'{spp}spp_{den}'] = {'onepass_vs_twopass': stats(a1, a2), 'onepass_vs_ref2048': stats(a1, ref_irr),
                                  'twopass_vs_ref2048': stats(a2, ref_irr)}
res['irradiance'] = irr

# beauty
sb0, sb1, pb = load('stock_beauty_256_0'), load('stock_beauty_256_1'), load('patched_onepass_256_0')
d0, d1, dp = png('stock_beauty_256_0'), png('stock_beauty_256_1'), png('patched_onepass_256_0')
lin = lambda d, p='Combined': lum(rgb(d, p))
beauty = {'psnr_display_patched_vs_stock': psnr(dp, d0), 'psnr_display_stock_seed1_vs_stock': psnr(d1, d0),
          'mean_rel_diff_linear_patched_vs_stock': float(lin(pb).mean() / lin(sb0).mean() - 1),
          'mean_rel_diff_linear_stock_seed1_vs_stock': float(lin(sb1).mean() / lin(sb0).mean() - 1),
          'mean_abs_diff_display_patched_vs_stock': float(np.abs(dp - d0).mean()),
          'mean_abs_diff_display_seed1_vs_stock': float(np.abs(d1 - d0).mean())}
try:
    po = load('patched_beauty_256_0')
    beauty['patched_pass_off_vs_stock_max_abs_linear'] = float(np.abs(rgb(po, 'Combined') - rgb(sb0, 'Combined')).max())
    beauty['patched_pass_off_vs_stock_psnr_display'] = psnr(png('patched_beauty_256_0'), d0)
except Exception as e:
    print('no pass-off render', e)
refb = lin(ref_b, 'Noisy Image')
noise = {}
for spp in (256, 64):
    s, p = load(f'stock_beauty_{spp}_0'), load(f'patched_onepass_{spp}_0')
    for k, m in classes.items():
        if m.sum() == 0: continue
        rs = np.sqrt(((lin(s, 'Noisy Image') - refb)[m] ** 2).mean()); rp = np.sqrt(((lin(p, 'Noisy Image') - refb)[m] ** 2).mean())
        bs = lin(s, 'Noisy Image')[m].mean() / refb[m].mean() - 1; bp = lin(p, 'Noisy Image')[m].mean() / refb[m].mean() - 1
        noise[f'{spp}spp_{k}'] = {'rmse_stock': float(rs), 'rmse_patched': float(rp), 'rmse_ratio': float(rp / rs),
                                  'bias_stock_vs_ref': float(bs), 'bias_patched_vs_ref': float(bp)}
beauty['noisy_beauty_vs_ref2048'] = noise
res['beauty'] = beauty
json.dump(res, open(OUTJ, 'w'), indent=1)
print(json.dumps(res, indent=1))

# side-by-side figure
two, one = rgb(load('stock_irr_256_0'), 'Combined'), rgb(load('patched_onepass_256_0'), 'Irradiance')
s = 1. / max(np.percentile(lum(two)[~bg], 99), 1e-6)
tm = lambda x: np.clip((x * s / (1 + x * s)) ** (1 / 2.2), 0, 1)
rel = np.abs(lum(one) - lum(two)) / np.maximum(lum(two), 1e-4); rel[bg] = 0
def heat(r, vmax):
    t = np.clip(r / vmax, 0, 1)
    return np.stack([t, .6 * (1 - np.abs(2 * t - 1)), 1 - t], -1)
bdiff = np.clip(np.abs(dp - d0) * 10, 0, 1)
cls = np.zeros(bg.shape + (3,)); cls[diel] = (.6, .6, .6); cls[metal] = (1, .7, .1); cls[glass] = (.2, .6, 1); cls[emitter] = (1, 1, 1)
panels = [(d0, 'stock beauty 256spp'), (dp, 'patched beauty 256spp (Irradiance pass on)'), (bdiff, '|patched - stock| beauty x10'),
          (tm(two), 'two-pass irradiance E/pi (stock, 256spp, OptiX)'), (tm(one), 'one-pass Irradiance pass (patched, 256spp, OptiX)'),
          (heat(rel, .2), '|one - two| / two  (blue 0 .. red >= 20%)')]
H, W = bg.shape
S = Image.new('RGB', (3 * W, 2 * H + 40))
for i, (im, t) in enumerate(panels):
    x, y = (i % 3) * W, (i // 3) * H
    S.paste(Image.fromarray((np.clip(im, 0, 1) * 255).astype(np.uint8)), (x, y))
    d = ImageDraw.Draw(S); d.rectangle((x, y, x + 7 * len(t) + 8, y + 15), fill='black'); d.text((x + 4, y + 2), t, fill='white')
d = ImageDraw.Draw(S)
m = irr['256spp_denoised']['onepass_vs_twopass']; m64 = irr['64spp_denoised']['onepass_vs_twopass']
txt = ('AI43_001  rel. MAE one-pass vs two-pass (denoised): 256spp ' + ', '.join(f'{k} {v["rel_mae"]*100:.1f}%' for k, v in m.items() if k != 'emitter') +
       ' | 64spp ' + ', '.join(f'{k} {v["rel_mae"]*100:.1f}%' for k, v in m64.items() if k != 'emitter') +
       f'   beauty PSNR patched/stock {beauty["psnr_display_patched_vs_stock"]:.1f} dB (stock seed/seed {beauty["psnr_display_stock_seed1_vs_stock"]:.1f} dB)')
d.text((6, 2 * H + 4), txt, fill='white')
d.text((6, 2 * H + 22), 'background (sky) pixels: two-pass shows the world, one-pass Irradiance is 0 (excluded from stats)', fill='white')
S.save(OUTS, quality=90)
Image.fromarray((cls * 255).astype(np.uint8)).save(OUTS.replace('.jpg', '_classes.png'))
print('SAVED', OUTS)
