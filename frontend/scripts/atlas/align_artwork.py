"""Alignment test: can the painted Ukraine map carry real coordinates?

usage: python3 -I align.py ARTWORK.png UKRAINE_BORDER.geojson OUT_DIR
Fits lon/lat -> pixel transforms from labelled city dots, validates them on
held-out cities and on the painted border, and reports error relative to the
Kyiv NO2 study box (0.5 x 0.5 degrees).
"""
import json, sys, itertools
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree
from scipy.ndimage import label, center_of_mass, binary_opening

art, border_path, out = sys.argv[1:4]
im = Image.open(art).convert('RGB'); A = np.asarray(im).astype(int); H, W = A.shape[:2]

CITIES = {  # name: (lon, lat, approx px x, approx px y)
    'Kyiv': (30.5234, 50.4501, 711, 331), 'Lviv': (24.0297, 49.8397, 258, 384),
    'Kharkiv': (36.2304, 49.9935, 1050, 373), 'Dnipro': (35.0462, 48.4647, 953, 502),
    'Donetsk': (37.8028, 48.0159, 1146, 541), 'Odesa': (30.7233, 46.4825, 621, 674)}
KYIV_BOX = (30.273, 50.2, 30.773, 50.7)  # west, south, east, north (from /api/air/kyiv map.bounds)

def dot_centre(x0, y0, r=9):
    sub = A[y0-r:y0+r+1, x0-r:x0+r+1]; dark = sub.sum(axis=2) < 200
    lab, n = label(dark); best = max(range(1, n+1), key=lambda i: (lab == i).sum())
    cy, cx = center_of_mass(lab == best); return x0 - r + cx, y0 - r + cy

names = list(CITIES); geo = np.array([CITIES[n][:2] for n in names])
px = np.array([dot_centre(*CITIES[n][2:]) for n in names])

R = 6371.0088
def equirect(ll): return np.asarray(ll, float)
def mercator(ll):
    ll = np.asarray(ll, float); return np.c_[ll[:, 0], np.degrees(np.log(np.tan(np.pi/4 + np.radians(ll[:, 1])/2)))]
def conic(ll, p1=46.0, p2=51.0, l0=31.0, f0=48.5):  # Lambert conformal conic
    ll = np.asarray(ll, float); f = np.radians(ll[:, 1]); l = np.radians(ll[:, 0] - l0)
    a, b, c = np.radians([p1, p2, f0]); t = lambda x: np.tan(np.pi/4 + x/2)
    n = np.log(np.cos(a)/np.cos(b)) / np.log(t(b)/t(a)); F = np.cos(a) * t(a)**n / n
    rho, rho0 = F / t(f)**n, F / t(c)**n
    return np.degrees(np.c_[rho*np.sin(n*l), rho0 - rho*np.cos(n*l)])
PROJ = {'equirectangular': equirect, 'Mercator': mercator, 'Lambert conic': conic}

def fit_affine(src, dst):
    M = np.c_[src, np.ones(len(src))]; coef, *_ = np.linalg.lstsq(M, dst, rcond=None)
    return lambda p: np.c_[p, np.ones(len(p))] @ coef
def fit_similarity(src, dst):  # scale + rotation + translation, y flipped
    s = src * [1, -1]; M = np.zeros((2*len(s), 4)); M[0::2] = np.c_[s[:, 0], -s[:, 1], np.ones(len(s)), np.zeros(len(s))]
    M[1::2] = np.c_[s[:, 1], s[:, 0], np.zeros(len(s)), np.ones(len(s))]
    a, b, tx, ty = np.linalg.lstsq(M, dst.reshape(-1), rcond=None)[0]
    return lambda p: np.c_[a*p[:, 0] + b*p[:, 1] + tx, b*p[:, 0] - a*p[:, 1] + ty]
FITS = {'affine': (fit_affine, 3), 'similarity': (fit_similarity, 2)}

def km_per_px(tf, proj):  # local scale at Kyiv
    c = np.array([[30.523, 50.45], [31.523, 50.45], [30.523, 51.45]]); p = tf(proj(c))
    return (111.19*np.cos(np.radians(50.45)) / np.linalg.norm(p[1]-p[0]) + 111.19 / np.linalg.norm(p[2]-p[0])) / 2

def box_px(tf, proj):
    w, s, e, n = KYIV_BOX; p = tf(proj(np.array([[w, s], [e, s], [e, n], [w, n]])))
    return np.linalg.norm(p[1]-p[0]), np.linalg.norm(p[3]-p[0]), p

# painted border: the dark red inked line
r, g, b = A[..., 0], A[..., 1], A[..., 2]
mask = (r > 90) & (r < 175) & (g < 95) & (b < 70) & (r - g > 45)
mask[:400, 1230:] = False  # painted element buttons, not geography
lab, n = label(mask, structure=np.ones((3, 3))); sizes = np.bincount(lab.ravel()); sizes[0] = 0
mask = np.isin(lab, np.where(sizes > 400)[0])
by, bx = np.nonzero(mask); painted = np.c_[bx, by].astype(float); ptree = cKDTree(painted)

gj = json.load(open(border_path))
ua = next(f for f in gj['features'] if f['properties']['ADMIN'] == 'Ukraine')
ring = np.array(max((p[0] for p in ua['geometry']['coordinates']), key=len))
def densify(ring, step=0.02):
    outp = []
    for p, q in zip(ring[:-1], ring[1:]):
        k = max(1, int(np.ceil(np.linalg.norm(q-p)/step))); outp.append(p + (q-p) * np.linspace(0, 1, k, endpoint=False)[:, None])
    return np.vstack(outp)
real = densify(ring)

report = {'image_size': [W, H], 'city_pixels': {n: [round(float(v), 1) for v in p] for n, p in zip(names, px)},
          'painted_border_pixels': int(len(painted)), 'models': []}
print(f'image {W}x{H}; painted border pixels {len(painted)}')
for n, p in zip(names, px): print(f'  {n:8s} px=({p[0]:.1f},{p[1]:.1f})')

best = None
for pn, proj in PROJ.items():
    for fn, (fitter, kmin) in FITS.items():
        src = proj(geo); tf = fitter(src, px); res = np.linalg.norm(tf(src) - px, axis=1)
        # hold-out: every way of fitting on 4 cities and testing on the other 2
        ho = []
        for test in itertools.combinations(range(6), 2):
            tr = [i for i in range(6) if i not in test]; t2 = fitter(src[tr], px[tr])
            ho += list(np.linalg.norm(t2(src[list(test)]) - px[list(test)], axis=1))
        ho = np.array(ho); kpp = km_per_px(tf, proj); bw, bh, _ = box_px(tf, proj)
        rp = tf(proj(real)); d_rp = ptree.query(rp)[0]; d_pr = cKDTree(rp).query(painted)[0]
        m = dict(projection=pn, transform=fn, km_per_px=round(float(kpp), 2), kyiv_box_px=[round(float(bw), 1), round(float(bh), 1)],
                 fit_residual_px=dict(zip(names, np.round(res, 1).tolist())), fit_rms_px=round(float(np.sqrt((res**2).mean())), 1),
                 holdout_median_px=round(float(np.median(ho)), 1), holdout_max_px=round(float(ho.max()), 1),
                 holdout_median_km=round(float(np.median(ho)*kpp), 0), holdout_max_km=round(float(ho.max()*kpp), 0),
                 holdout_median_in_box_widths=round(float(np.median(ho)/bw), 2),
                 border_real_to_painted_px=dict(median=round(float(np.median(d_rp)), 1), p90=round(float(np.percentile(d_rp, 90)), 1), max=round(float(d_rp.max()), 1)),
                 border_painted_to_real_px=dict(median=round(float(np.median(d_pr)), 1), p90=round(float(np.percentile(d_pr, 90)), 1), max=round(float(d_pr.max()), 1)))
        report['models'].append(m)
        print(f"{pn:16s} {fn:10s} rms={m['fit_rms_px']:5.1f}px holdout med/max={m['holdout_median_px']}/{m['holdout_max_px']}px "
              f"({m['holdout_median_km']:.0f}/{m['holdout_max_km']:.0f} km) box={bw:.0f}x{bh:.0f}px border p90={m['border_painted_to_real_px']['p90']}px max={m['border_painted_to_real_px']['max']}px")
        if best is None or m['holdout_median_px'] < best[0]['holdout_median_px']: best = (m, tf, proj)

# Best case for the artwork: an affine fitted to the painted border itself (ICP), then judged on the cities.
m0, tf0, proj0 = best; src_b = proj0(real); cur = tf0(src_b)
for _ in range(60):
    d, idx = ptree.query(cur); keep = d < np.percentile(d, 90)
    tfb = fit_affine(src_b[keep], painted[idx[keep]]); cur = tfb(src_b)
d_rp = ptree.query(cur)[0]; d_pr = cKDTree(cur).query(painted)[0]; cres = np.linalg.norm(tfb(proj0(geo)) - px, axis=1)
kpp = km_per_px(tfb, proj0); bw, bh, boxb = box_px(tfb, proj0)
report['border_fitted_affine'] = dict(projection=m0['projection'], km_per_px=round(float(kpp), 2), kyiv_box_px=[round(float(bw), 1), round(float(bh), 1)],
    border_painted_to_real_px=dict(median=round(float(np.median(d_pr)), 1), p90=round(float(np.percentile(d_pr, 90)), 1), max=round(float(d_pr.max()), 1)),
    city_error_px=dict(zip(names, np.round(cres, 1).tolist())), city_error_km=dict(zip(names, np.round(cres*kpp).tolist())))
print('border-fitted affine: border p90/max', report['border_fitted_affine']['border_painted_to_real_px'], 'city errors px', report['border_fitted_affine']['city_error_px'])
report['best_city_model'] = {'projection': m0['projection'], 'transform': m0['transform']}
json.dump(report, open(f'{out}/alignment-report.json', 'w'), indent=1)

# Diagnostic figure: artwork dimmed, real border (blue) from the best city fit, real city positions vs painted dots.
fig = Image.blend(im, Image.new('RGB', im.size, (255, 255, 255)), 0.45); d = ImageDraw.Draw(fig)
d.rectangle([0, 700, 470, H], fill=(236, 228, 208)); d.rectangle([1210, 30, W, 400], fill=(236, 228, 208)); d.rectangle([1200, 800, W, H], fill=(236, 228, 208))
rp = tf0(proj0(np.vstack([ring, ring[:1]]))); d.line([tuple(p) for p in rp], fill=(20, 80, 200), width=3)
for nme, p, q in zip(names, px, tf0(proj0(geo))):
    d.ellipse([p[0]-6, p[1]-6, p[0]+6, p[1]+6], outline=(0, 0, 0), width=2)
    d.line([tuple(p), tuple(q)], fill=(200, 0, 0), width=2); d.ellipse([q[0]-4, q[1]-4, q[0]+4, q[1]+4], fill=(200, 0, 0))
_, _, bp = box_px(tf0, proj0); d.polygon([tuple(p) for p in bp], outline=(200, 0, 0), width=2)
d.text((20, 720), 'Alignment test: painted atlas vs real coordinates', fill=(0, 0, 0))
d.text((20, 740), f"blue: real border, {m0['projection']} + {m0['transform']} fitted to 6 cities", fill=(20, 80, 200))
d.text((20, 760), 'black ring: painted city dot; red dot: where the fit puts the real city', fill=(160, 0, 0))
d.text((20, 780), 'red box: Kyiv NO2 study area under the same fit', fill=(160, 0, 0))
fig.save(f'{out}/alignment-test.png')
