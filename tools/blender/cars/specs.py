"""Body specs. Each car: overall dimensions, axles/wheels, a station list (rear -> front) for the body cage and
rules for glass / trim faces. Numbers in metres; x = 0 is the middle of the car."""


def st(x, kind, top, belt, zs, ws, w, wb=None, zb=0.17, **kw):
    d = dict(x=x, kind=kind, top=top, belt=belt, zs=zs, ws=ws, w=w, wb=wb if wb is not None else w - 0.06, zb=zb)
    d.update(kw)
    return d


# --- compact hatchback (Golf-class): 4.26 x 1.80 x 1.45, wheelbase 2.62
HATCH = dict(
    name='hatch', L=4.26, W=1.80, H=1.45,
    axles=(1.27, -1.35), wheel_r=0.317, tyre_w=0.215, track=1.56, rim_in=17,
    stations=[
        # rear face (tailgate + bumper): rows k2..k9; the rear window lies on rows k7..k8
        st(-2.13, 'gh', 1.405, 1.00, 0.90, 0.775, 0.835, wb=0.74, zb=0.24, wr=0.50, crown=0.03,
           lean={2: 0.08, 3: 0.0, 4: -0.005, 5: 0.01, 6: 0.0, 7: 0.03, 8: 0.17, 9: 0.22, 10: 0.245, 11: 0.25},
           z3=0.34, z4=0.52, z5=0.72, rail_t=0.3, rail_h=0.06, wg=0.69, cap_bulge=0.01),
        st(-2.06, 'gh', 1.42, 1.00, 0.90, 0.85, 0.885, wb=0.80, zb=0.21, wr=0.565, crown=0.035,
           lean={2: 0.05, 8: 0.14, 9: 0.17, 10: 0.18, 11: 0.19}, z3=0.32, wg=0.78),
        st(-1.82, 'gh', 1.435, 1.01, 0.905, 0.865, 0.895, zb=0.19, wr=0.60, crown=0.04, lean={8: 0.10, 9: 0.05}),
        st(-1.35, 'gh', 1.445, 0.99, 0.90, 0.87, 0.90, zb=0.17, wr=0.62, rail_h=0.05, crown=0.035),
        st(-0.75, 'gh', 1.452, 0.975, 0.895, 0.87, 0.90, zb=0.16, wr=0.635, rail_h=0.045, crown=0.035),
        st(-0.15, 'gh', 1.45, 0.965, 0.89, 0.87, 0.90, zb=0.16, wr=0.63, rail_h=0.045, crown=0.035, id='roof_front'),
        st(0.30, 'gh', 1.25, 0.96, 0.885, 0.865, 0.90, zb=0.16, wr=0.665, crown=0.03, rail_h=0.05, rail_t=0.2),
        st(0.72, 'cowl', 1.00, 0.955, 0.88, 0.86, 0.895, zb=0.17, wr=0.70, id='cowl'),
        st(1.27, 'hood', 0.945, 0.905, 0.855, 0.86, 0.893, zb=0.18),
        st(1.80, 'hood', 0.895, 0.865, 0.80, 0.85, 0.885, zb=0.20, z4=0.50),
        st(2.04, 'hood', 0.865, 0.845, 0.77, 0.815, 0.86, wb=0.78, zb=0.23, z3=0.32, z4=0.47, z5=0.62,
           lean={2: -0.03, 3: 0.02, 4: 0.03, 5: 0.02, 6: -0.005, 7: -0.03, 8: -0.04, 9: -0.045, 10: -0.045, 11: -0.045}),
        # front face (bumper, grille, lights): rows k2..k9
        st(2.13, 'hood', 0.845, 0.83, 0.72, 0.73, 0.78, wb=0.68, zb=0.24, z3=0.33, z4=0.46, z5=0.58,
           lean={2: -0.05, 3: 0.0, 4: 0.01, 5: -0.005, 6: -0.035, 7: -0.075, 8: -0.088, 9: -0.092, 10: -0.092, 11: -0.092},
           cap_bulge=0.02, we=0.69),
    ],
    shoulder_crease=0.85,
    mirror=dict(x=0.52, z=1.045, len=0.22, h=0.125, d=0.105, arm_x=0.60, arm_z=0.99),
    handles=[(-0.42, 0.88), (-1.20, 0.89)],
    wipers=[((0.735, -0.06), (0.67, 0.60)), ((0.735, -0.64), (0.672, -0.12))],
    plate_z=(0.55, 0.767),
    antenna_x=-1.72,
    cabin=dict(front_x=-0.05, rear_x=-0.98, seat_y=0.37, hip_z=0.50, dash_x=0.55, wheel=(0.27, 0.37, 0.90),
               shelf=(-1.36, -2.0, 0.985)),
    ring_creases=[(-1, 7, 11, 0.8), (-1, 2, 7, 0.45), (0, 8, 11, 0.75), (0, 2, 8, 0.45)],
    features=[
        # --- front: headlights (wrap onto the wings), grille band, lower intake, corner intakes
        dict(type='lamp', name='headlight', view='front', depth=(1.7, 2.6), sink=0.06, lens='lens', floor='lamp_inner', wall='gloss',
             poly=[(0.375, 0.718), (0.62, 0.70), (0.80, 0.682), (0.862, 0.745), (0.845, 0.805), (0.39, 0.795)], radii=[0.012, 0.03, 0.04, 0.03, 0.03, 0.012],
             zones=[dict(poly=[(0.60, 0.708), (0.80, 0.690), (0.815, 0.704), (0.61, 0.721)], mat='drl', lift=0.01, radii=0.005),
                    dict(poly=[(0.39, 0.725), (0.53, 0.725), (0.53, 0.79), (0.40, 0.79)], mat='gloss', lift=0),
                    dict(poly=[(0.70, 0.722), (0.775, 0.722), (0.775, 0.797), (0.70, 0.797)], radii=0.036, mat='reflector', lift=0.02),
                    dict(poly=[(0.56, 0.735), (0.625, 0.735), (0.625, 0.79), (0.56, 0.79)], radii=0.03, mat='reflector', lift=0.012)]),
        dict(type='recess', name='grille', view='front', mirror=False, depth=(1.7, 2.6), sink=0.035, floor='gloss',
             poly=[(-0.365, 0.705), (0.365, 0.705), (0.38, 0.793), (-0.38, 0.793)], radii=0.012,
             zones=[dict(poly=[(-0.36, 0.722), (0.36, 0.722), (0.36, 0.733), (-0.36, 0.733)], mat='chrome', lift=0.03),
                    dict(poly=[(-0.36, 0.750), (0.36, 0.750), (0.36, 0.758), (-0.36, 0.758)], mat='gloss', lift=0.025),
                    dict(poly=[(-0.37, 0.772), (0.37, 0.772), (0.37, 0.780), (-0.37, 0.780)], mat='gloss', lift=0.025)]),
        dict(type='recess', name='intake', view='front', mirror=False, depth=(1.7, 2.6), sink=0.05, floor='trim',
             poly=[(-0.44, 0.465), (0.44, 0.465), (0.37, 0.285), (-0.37, 0.285)], radii=0.035,
             zones=[dict(poly=[(-0.42, 0.40), (0.42, 0.40), (0.41, 0.41), (-0.41, 0.41)], mat='trim', lift=0.035),
                    dict(poly=[(-0.40, 0.345), (0.40, 0.345), (0.39, 0.355), (-0.39, 0.355)], mat='trim', lift=0.035)]),
        dict(type='recess', name='corner', view='front', depth=(1.7, 2.6), sink=0.04, floor='trim',
             poly=[(0.55, 0.33), (0.735, 0.355), (0.76, 0.435), (0.575, 0.435)], radii=0.02,
             zones=[dict(poly=[(0.58, 0.416), (0.75, 0.416), (0.752, 0.426), (0.585, 0.426)], mat='chrome', lift=0.03)]),
        # --- rear: tail lights (wrap onto the quarters), plate recess, diffuser, reflectors
        dict(type='lamp', name='taillight', view='front', depth=(-2.6, -1.7), sink=0.04, lens='tail_lens', floor='tail_dark', wall='trim',
             poly=[(0.36, 0.915), (0.82, 0.885), (0.875, 0.925), (0.865, 0.99), (0.40, 0.98)], radii=[0.015, 0.03, 0.04, 0.03, 0.015],
             zones=[dict(poly=[(0.47, 0.935), (0.84, 0.912), (0.85, 0.925), (0.48, 0.95)], mat='tail', lift=0.012),
                    dict(poly=[(0.375, 0.93), (0.45, 0.928), (0.45, 0.972), (0.39, 0.974)], mat='reflector', lift=0)]),
        dict(type='recess', name='plate_rear', view='front', mirror=False, depth=(-2.6, -1.7), sink=0.012, floor='paint',
             poly=[(-0.29, 0.69), (0.29, 0.69), (0.29, 0.845), (-0.29, 0.845)], radii=0.03),
        dict(type='patch', view='front', mirror=False, depth=(-2.6, -1.85), mat='trim',
             poly=[(-0.73, 0.235), (0.73, 0.235), (0.75, 0.335), (-0.75, 0.335)], radii=0.03),
        dict(type='patch', view='front', depth=(-2.6, -1.85), mat='tail_dark',
             poly=[(0.60, 0.40), (0.745, 0.41), (0.745, 0.428), (0.60, 0.42)], radii=0.006),
        # --- panel gaps
        dict(type='gap', view='front', mirror=False, depth=(1.95, 2.6), line=[(-0.67, 0.815), (0.67, 0.815)]),
        dict(type='gap', view='top', mirror=False, depth=(0.81, 2.0),
             line=[(2.14, 0.66), (2.0, 0.725), (1.6, 0.765), (1.1, 0.775), (0.84, 0.76), (0.80, 0.60), (0.80, -0.60),
                   (0.84, -0.76), (1.1, -0.775), (1.6, -0.765), (2.0, -0.725), (2.14, -0.66)]),
        dict(type='gap', view='front', mirror=False, depth=(-2.6, -1.9),
             line=[(0.58, 1.36), (0.68, 1.02), (0.72, 0.90), (0.62, 0.66), (-0.62, 0.66), (-0.72, 0.90), (-0.68, 1.02), (-0.58, 1.36)]),
        dict(type='gap', view='side', depth=(0.74, 1.5),
             lines=[[(0.655, 0.985), (0.70, 0.82), (0.75, 0.55), (0.77, 0.10)],
                    [(-0.635, 0.99), (-0.615, 0.10)],
                    [(-1.49, 1.0), (-1.45, 0.88), (-1.38, 0.775), (-1.25, 0.735), (-1.135, 0.70), (-1.046, 0.63), (-0.975, 0.53),
                     (-0.94, 0.40), (-0.93, 0.10)]]),
        # --- glass
        dict(type='window', view='top', mirror=False, depth=(0.95, 1.9),           # windscreen
             outer=[(0.70, -0.70), (0.70, 0.70), (-0.13, 0.585), (-0.13, -0.585)], radii=[0.05, 0.05, 0.10, 0.10]),
        dict(type='window', view='front', mirror=False, depth=(-2.5, -1.75),       # rear window
             outer=[(-0.52, 1.03), (0.52, 1.03), (0.46, 1.355), (-0.46, 1.355)], radii=0.07),
        dict(type='window', view='side', depth=(0.55, 1.6), seal=0.02,             # side glass (DLO)
             outer=[(0.64, 0.975), (-0.10, 1.385), (-1.02, 1.38), (-1.50, 1.01)], radii=[0.02, 0.10, 0.16, 0.05],
             inner=[[(0.60, 0.98), (-0.09, 1.37), (-0.60, 1.37), (-0.60, 0.975)],
                    [(-0.68, 0.975), (-0.68, 1.37), (-1.00, 1.365), (-1.44, 1.015)]], inner_radii=0.025),
    ],
)



# ------------------------------------------------------------------------------------------------
# derived bodies: the tuned hatch remapped onto other proportions (piecewise-linear in x and z, scaled in y)

def _pw(pts):
    """piecewise-linear map through [(src, dst)...] (extrapolates with the end slopes)."""
    pts = sorted(pts)

    def f(v):
        for (a0, b0), (a1, b1) in zip(pts, pts[1:]):
            if v <= a1 or (a1, b1) == pts[-1]:
                if v < a0 and (a0, b0) != pts[0]:
                    continue
                return b0 + (v - a0) * (b1 - b0) / (a1 - a0)
        return v
    return f


def derive(base, name, L, W, H, axles, belt, zb, wheel_r, track, tyre_w=None, rim_in=None, xkeys=(), zkeys=(),
           drop=(), **over):
    """base spec -> new spec. Keys: front/rear ends + axles always map; xkeys / zkeys add (src, dst) points, e.g. to
    move the A-/C-pillars or lift the roof line differently from the belt."""
    import copy
    b = base
    bx0, bx1 = b['stations'][0]['x'], b['stations'][-1]['x']
    X = _pw([(bx0, -L / 2), (b['axles'][1], axles[1]), (b['axles'][0], axles[0]), (bx1, L / 2), *xkeys])
    bbelt = min(st['belt'] for st in b['stations'] if st['kind'] == 'gh')
    bzb = min(st['zb'] for st in b['stations'])
    Z = _pw([(0.0, 0.0), (bzb, zb), (bbelt, belt), (b['H'], H), *zkeys])
    sy = W / b['W']
    sx_r = (L / 2 + axles[1]) / (bx1 + b['axles'][1]) if False else 1.0

    def Y(v):
        return v * sy
    zk = ('top', 'belt', 'zs', 'zb', 'z3', 'z4', 'z5')
    yk = ('w', 'ws', 'wb', 'wr', 'wg', 'we', 'bulge5')
    sts = []
    for st in b['stations']:
        n = dict(st)
        n['x'] = X(st['x'])
        for k in zk:
            if k in st:
                n[k] = Z(st[k])
        for k in yk:
            if k in st and st[k] is not None:
                n[k] = Y(st[k])
        zsc = (Z(st['top']) - Z(st['belt'])) / max(1e-3, st['top'] - st['belt'])
        for k in ('crown', 'rail_h'):
            if k in st:
                n[k] = st[k] * zsc
        if 'lean' in st:
            n['lean'] = dict(st['lean'])
        sts.append(n)

    def conv(view, poly):
        if view == 'side':
            return [(X(u), Z(v)) for u, v in poly]
        if view == 'top':
            return [(X(u), Y(v)) for u, v in poly]
        return [(Y(u), Z(v)) for u, v in poly]

    def depth(view, d):
        f = {'side': Y, 'top': Z, 'front': X}[view]
        return (f(d[0]), f(d[1]))
    feats = []
    for f in b['features']:
        if f.get('name') in drop:
            continue
        g = copy.deepcopy(f)
        v = g['view']
        for k in ('poly', 'outer', 'line'):
            if k in g:
                g[k] = conv(v, g[k])
        for k in ('inner', 'lines'):
            if k in g:
                g[k] = [conv(v, p) for p in g[k]]
        for z in g.get('zones', []):
            z['poly'] = conv(v, z['poly'])
        g['depth'] = depth(v, g['depth'])
        feats.append(g)
    m = b['mirror']
    c = b['cabin']
    out = dict(b, name=name, L=L, W=W, H=H, axles=axles, wheel_r=wheel_r, track=track, tyre_w=tyre_w or b['tyre_w'],
               rim_in=rim_in or b['rim_in'], stations=sts, features=feats,
               mirror=dict(m, x=X(m['x']), z=Z(m['z']), arm_x=X(m['arm_x']), arm_z=Z(m['arm_z'])),
               handles=[(X(x), Z(z)) for x, z in b['handles']],
               wipers=[((X(a[0]), Y(a[1])), (X(e[0]), Y(e[1]))) for a, e in b['wipers']],
               plate_z=tuple(Z(z) for z in b['plate_z']), antenna_x=X(b['antenna_x']),
               cabin=dict(c, front_x=X(c['front_x']), rear_x=X(c['rear_x']), hip_z=Z(c['hip_z']), dash_x=X(c['dash_x']), dash_z=Z(c.get('dash_z', 0.84)),
                          wheel=(X(c['wheel'][0]), Y(c['wheel'][1]), Z(c['wheel'][2])),
                          shelf=(X(c['shelf'][0]), X(c['shelf'][1]), Z(c['shelf'][2])),
                          seat_y=Y(c['seat_y']), bench_w=Y(c.get('bench_w', 1.30)), dash_w=Y(c.get('dash_w', 1.42)),
                          shelf_w=Y(c.get('shelf_w', 1.30))))
    out['_X'], out['_Z'], out['_Y'] = X, Z, Y
    out.update(over)
    return out


def cladding(spec, top=0.40, arch=0.075):
    """unpainted plastic sills + wheel-arch flares as side-view patches (crossovers / SUVs)."""
    import math
    R = spec['wheel_r']
    ar = spec.get('arch_r', R + 0.06) + arch
    feats = []
    for ax in spec['axles']:
        poly = []
        for i in range(13):
            t = math.pi * i / 12
            poly.append((ax + math.cos(t) * ar, R + math.sin(t) * ar))
        poly += [(ax - ar, 0.05), (ax + ar, 0.05)]      # CCW in (x, z): over the arch front -> rear, back along the ground
        feats.append(dict(type='patch', view='side', depth=(0.55, 1.5), mat='trim', poly=poly))
    x0 = spec['axles'][1] + ar - 0.02
    x1 = spec['axles'][0] - ar + 0.02
    feats.append(dict(type='patch', view='side', depth=(0.55, 1.5), mat='trim',
                      poly=[(x1, 0.05), (x1, top), (x0, top), (x0, 0.05)]))
    return feats


def _feature(spec, **match):
    for f in spec['features']:
        if all(f.get(k) == v for k, v in match.items()):
            return f
    raise KeyError(match)


def _raise(spec, dz, keys=('top', 'belt')):
    """lift stations (by index) without remapping the features: {index: dz}"""
    for i, d in dz.items():
        for k in keys:
            spec['stations'][i][k] += d
    return spec


def _with_cladding(spec, top):
    spec['features'] = cladding(spec, top) + spec['features']
    return spec


# --- small hatch (Clio / Fabia class)
SMALL = derive(HATCH, 'small', L=4.02, W=1.74, H=1.45, axles=(1.24, -1.28), belt=0.955, zb=0.155, wheel_r=0.305,
               track=1.50, tyre_w=0.195, rim_in=16, rim_style='five')
_feature(SMALL, name='headlight')['radii'] = [0.02, 0.05, 0.05, 0.05, 0.04, 0.02]

# --- crossover (2008 / Q3 class): raised, plastic cladding
CROSS = _with_cladding(derive(HATCH, 'crossover', L=4.30, W=1.78, H=1.55, axles=(1.29, -1.30), belt=1.03, zb=0.20,
                              wheel_r=0.335, track=1.54, tyre_w=0.215, rim_in=17), top=0.40)

# --- compact SUV (Tiguan / X1 class)
SUV = _with_cladding(derive(HATCH, 'suv', L=4.50, W=1.84, H=1.65, axles=(1.33, -1.35), belt=1.10, zb=0.22, wheel_r=0.36,
                            track=1.58, tyre_w=0.235, rim_in=18, zkeys=[(1.385, 1.585)]), top=0.44)
_raise(SUV, {8: 0.02, 9: 0.04, 10: 0.05, 11: 0.05})        # blunter, higher nose

# --- estate (A4 Avant / Megane Grandtour class): longer roof, upright tailgate, quarter glass behind the C-pillar
WAGON = derive(HATCH, 'wagon', L=4.70, W=1.82, H=1.47, axles=(1.33, -1.45), belt=0.97, zb=0.16, wheel_r=0.32, track=1.57,
               tyre_w=0.225, rim_in=17)
for _st, _lean in zip(WAGON['stations'][:2], ({7: 0.02, 8: 0.09, 9: 0.12, 10: 0.135, 11: 0.14},
                                             {8: 0.07, 9: 0.09, 10: 0.10, 11: 0.105})):
    _st['lean'].update(_lean)
_w = _feature(WAGON, type='window', view='side')
_w['outer'] = [(0.66, 0.985), (-0.09, 1.405), (-1.86, 1.395), (-2.11, 1.075), (-2.02, 1.035)]
_w['radii'] = [0.02, 0.10, 0.10, 0.05, 0.03]
_w['inner'] = [[(0.62, 0.99), (-0.08, 1.39), (-0.62, 1.39), (-0.62, 0.99)],
               [(-0.71, 0.99), (-0.71, 1.39), (-1.42, 1.385), (-1.42, 1.005)],
               [(-1.52, 1.01), (-1.52, 1.38), (-1.85, 1.375), (-2.06, 1.075), (-1.99, 1.04)]]
_g = _feature(WAGON, type='gap', view='side')
_g['lines'][2][0] = (-1.47, 1.0)
_g['lines'][2][1] = (-1.47, 0.88)

# --- saloon (3-series / C-class / Octavia class): derived front + cabin, hand-built three-box rear
def _shift(f, dz):
    for k in ('poly',):
        f[k] = [(u, v + dz) for u, v in f[k]]
    for z in f.get('zones', []):
        z['poly'] = [(u, v + dz) for u, v in z['poly']]


SEDAN = derive(HATCH, 'sedan', L=4.70, W=1.82, H=1.44, axles=(1.40, -1.45), belt=0.97, zb=0.16, wheel_r=0.325, track=1.57,
               tyre_w=0.225, rim_in=18, rim_style='five', spokes=10, rim_seg_per_spoke=4)
SEDAN['stations'] = [
    # rear face + bumper (deck rear edge rounded forward)
    st(-2.35, 'hood', 0.985, 0.962, 0.90, 0.765, 0.81, wb=0.70, zb=0.25, z3=0.34, z4=0.50, z5=0.71, we=0.71,
       lean={2: 0.08, 3: 0.0, 4: -0.005, 5: 0.005, 6: 0.01, 7: 0.035, 8: 0.05, 9: 0.06, 10: 0.065, 11: 0.065},
       cap_bulge=0.02),
    st(-2.27, 'hood', 1.005, 0.982, 0.905, 0.845, 0.885, wb=0.80, zb=0.215, z3=0.322, we=0.80,
       lean={2: 0.05, 8: 0.02, 9: 0.025, 10: 0.025, 11: 0.025}),
    st(-1.98, 'hood', 1.022, 0.995, 0.912, 0.87, 0.905, wb=0.84, zb=0.19, crown_pow=2.6),
    st(-1.62, 'cowl', 1.045, 1.00, 0.91, 0.875, 0.91, wb=0.845, zb=0.175, wr=0.66),
    st(-1.12, 'gh', 1.28, 0.99, 0.906, 0.88, 0.91, wb=0.849, zb=0.165, wr=0.64, crown=0.03, rail_h=0.05, rail_t=0.2),
] + SEDAN['stations'][4:]
SEDAN['ring_creases'] = [(-1, 7, 11, 0.8), (-1, 2, 7, 0.45), (0, 7, 11, 0.8), (0, 2, 7, 0.45)]
SEDAN['antenna_x'] = -0.72
SEDAN['handles'] = [SEDAN['handles'][0], (-1.22, SEDAN['handles'][1][1])]
SEDAN['cabin'].update(rear_x=-0.85, shelf=(-1.27, -1.62, 1.0))
_f = SEDAN['features']
_f.remove(_feature(SEDAN, type='window', view='front'))
_f.remove(next(f for f in _f if f['type'] == 'gap' and f['view'] == 'front' and f['depth'][0] < 0))   # tailgate
_f.insert(len(_f) - 2, dict(type='window', view='top', mirror=False, depth=(0.95, 1.9),       # rear window
                            outer=[(-0.82, -0.575), (-0.82, 0.575), (-1.59, 0.635), (-1.59, -0.635)],
                            radii=[0.10, 0.10, 0.05, 0.05]))
_w = _feature(SEDAN, type='window', view='side')
_w['outer'] = [(0.715, 0.976), (-0.09, 1.377), (-0.78, 1.37), (-1.30, 1.075), (-1.44, 1.01)]
_w['radii'] = [0.02, 0.10, 0.16, 0.06, 0.03]
_w['inner'][1] = [(-0.72, 0.98), (-0.72, 1.36), (-0.80, 1.355), (-1.28, 1.075), (-1.38, 1.02)]
_g = _feature(SEDAN, type='gap', view='side')
_g['lines'][2] = [(-1.43, 1.0), (-1.42, 0.86), (-1.38, 0.80), (-1.30, 0.76), (-1.21, 0.725), (-1.12, 0.655),
                  (-1.06, 0.56), (-1.03, 0.42), (-1.02, 0.10)]
_f.append(dict(type='gap', view='top', mirror=False, depth=(0.975, 1.3),                       # boot lid
               line=[(-2.40, 0.655), (-2.25, 0.72), (-1.95, 0.745), (-1.69, 0.70), (-1.665, 0.40), (-1.665, -0.40),
                     (-1.69, -0.70), (-1.95, -0.745), (-2.25, -0.72), (-2.40, -0.655)]))
_f.append(dict(type='gap', view='front', mirror=False, depth=(-2.6, -2.15),
               line=[(0.72, 1.0), (0.745, 0.90), (0.66, 0.68), (-0.66, 0.68), (-0.745, 0.90), (-0.72, 1.0)]))
_t = _feature(SEDAN, name='taillight')
_shift(_t, -0.045)
_t['depth'] = (-2.6, -1.95)


SPECS = {'hatch': HATCH, 'small': SMALL, 'crossover': CROSS, 'suv': SUV, 'wagon': WAGON, 'sedan': SEDAN}



# map car kinds (tools/blender/rudarska/props.py) -> cars.glb models (picked by the car's serial number)
KIND_MODEL = {'hatch': ['hatch'], 'small': ['small'], 'sedan': ['sedan'], 'wagon': ['wagon'], 'suv': ['suv', 'crossover'],
              'van': ['suv']}


def dims(name):
    """collision-relevant dimensions: L, W, H, belt and the cabin's x range."""
    s = SPECS[name]
    sts = s['stations']
    belt = min(st['belt'] for st in sts if st['kind'] == 'gh')
    cab = [st['x'] for st in sts if st['kind'] == 'gh' and st['top'] > belt + 0.2]
    return dict(L=s['L'], W=s['W'], H=s['H'], belt=belt, cab_f=max(cab) + 0.1, cab_r=min(cab))
