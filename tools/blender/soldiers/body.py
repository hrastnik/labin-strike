"""Third-person soldiers: one skinned body per team, modelled after the reference illustration
(left: US paratrooper, M1 helmet, M42 jump jacket and trousers, tan webbing, brown jump boots;
 right: Wehrmacht rifleman, M40 Stahlhelm, M36 tunic, brown leather Y-straps and cartridge pouches, black boots).

Rest pose: standing, both hands forward at about the low-ready grip; the client re-aims the arms at every weapon's
grips with IK. The skeleton matches the game's pivots (client/src/avatars.js): its bone heads are where the
procedural soldier's pivots were, so the walk, crouch, lean and death animation keep working unchanged.
"""
import math

from mathutils import Matrix, Vector

from .lib import V, axis_rot, lerp

# bone: (parent, head) in three space; the order is the export order
SKELETON = {
    'body': (None, (0, 0, 0)),
    'hips': ('body', (0, 0.94, 0)),
    'thigh_l': ('hips', (-0.1, 0.94, 0)),
    'shin_l': ('thigh_l', (-0.1, 0.49, 0)),
    'foot_l': ('shin_l', (-0.1, 0.11, 0)),
    'thigh_r': ('hips', (0.1, 0.94, 0)),
    'shin_r': ('thigh_r', (0.1, 0.49, 0)),
    'foot_r': ('shin_r', (0.1, 0.11, 0)),
    'torso': ('body', (0, 0.94, 0)),
    'head': ('torso', (0, 1.54, 0)),
    'aim': ('torso', (0, 1.44, 0)),
}
SHOULDER = 0.19
HEAD_FWD = 0.05   # the head (and helmet) sits this far in front of the spine's line, over the collar
UPPER = 0.29   # shoulder to elbow
FORE = 0.26    # elbow to wrist
FIST = 0.075   # wrist to the middle of the grip


def arm_rest(side):
    """shoulder, elbow, wrist and fist centre of the rest pose (side +1 right, -1 left)."""
    s = V(side * SHOULDER, 1.44, 0)
    e = s + V(side * 0.3, -1, -0.35).normalized() * UPPER
    d = V(-side * 0.32, 0.23, -0.92).normalized()
    w = e + d * FORE
    return s, e, w, w + d * FIST, d


for _side, _n in ((1, 'r'), (-1, 'l')):
    _s, _e, _w, _, _ = arm_rest(_side)
    SKELETON[f'upperarm_{_n}'] = ('aim', tuple(_s))
    SKELETON[f'forearm_{_n}'] = (f'upperarm_{_n}', tuple(_e))
    SKELETON[f'hand_{_n}'] = (f'forearm_{_n}', tuple(_w))
BONES = list(SKELETON)

SKIN = '#d6a283'
SKIN_SHADE = '#c48c6e'
LIPS = '#bd8270'
BROW = '#5a4130'
EYE = '#3b2e24'
WHITE_EYE = '#d9d2c6'
LID = '#6e4b3c'
HAIR = '#5a4130'
BLUSH = '#d08c74'
IRIS = '#4f5d6a'
MK2 = '#4c5730'
MK2_GROOVE = '#33391f'
FUZE = '#77775f'
RING = '#a7a79c'
STICK_HEAD = '#59615a'
STICK_RING = '#7d8278'
STICK_WOOD = '#a07a4a'


def detail(p):
    """decimation priority: the head and helmet, then the hands."""
    for side in (1, -1):
        if (p - arm_rest(side)[3]).length < 0.07:
            return 0.8
    return 0.0


def uv_emphasis(p):
    """the face gets ~3x its share of the texture: scale the head up 1.75x while unwrapping (eased in over the neck)."""
    from .lib import smooth
    k = 1 + 0.75 * smooth(1.55, 1.6, p.y)
    return V(0, 1.68, -0.02), k


# ------------------------------------------------------------------------------------------------------ anatomy

def torso_stations(st):
    """(y, rx, ry, z centre) of the jacket from the hem to the neck."""
    return st['torso']


def build_torso(k, st):
    rows = st['torso']
    stations = [((0, y, zc), rx, ry) for y, rx, ry, zc in rows]
    bone = lambda p: 'hips' if p.y < 0.99 else 'torso'  # noqa: E731
    return k.loft(stations, st['jacket'], bone, n=32, p=2.4, name='torso')


def build_pelvis(k, st):
    rows = [(0.79, 0.135, 0.1, 0.0), (0.86, 0.155, 0.108, 0), (0.95, 0.158, 0.105, 0), (1.02, 0.15, 0.1, 0)]
    return k.loft([((0, y, zc), rx, ry) for y, rx, ry, zc in rows], st['trousers'], 'hips', n=24, p=2.3,
                  name='pelvis')


def build_legs(k, st):
    out = {}
    for side, n in ((1, 'r'), (-1, 'l')):
        x = side * 0.1
        thigh = [((x, 1.0, 0.0), 0.088, 0.098), ((x + side * 0.004, 0.86, -0.004), 0.088, 0.094),
                 ((x + side * 0.003, 0.72, -0.008), 0.08, 0.086), ((x, 0.58, -0.01), 0.068, 0.074),
                 ((x, 0.5, -0.012), 0.062, 0.068)]
        tb = lambda p, n=n: f'thigh_{n}'  # noqa: E731
        out['thigh_' + n] = k.loft(thigh, st['trousers'], tb, n=22, name='thigh_' + n)
        # knee cap
        k.ellipsoid((x, 0.49, -0.045), (0.05, 0.05, 0.035), st['trousers'], f'shin_{n}', name='knee_' + n)
        shin = st['shin'](x)
        out['shin_' + n] = k.loft(shin, st['trousers'], f'shin_{n}', n=22, name='shin_' + n)
        st['boot'](k, x, n)
    return out


def build_neck_head(k, st):
    """the realistic head, its neck running down inside the collar (realhead.py)."""
    from . import realhead
    f = st.get('face', {})
    return realhead.build(k, SKIN, LIPS, f.get('brow', BROW), f.get('hair', HAIR), BLUSH, f.get('iris', IRIS))


def build_arms(k, st, torso_surf=None):
    out = {}
    for side, n in ((1, 'r'), (-1, 'l')):
        s, e, w, fist, d = arm_rest(side)
        up = (e - s).normalized()
        k.ellipsoid(s + V(side * -0.005, -0.01, 0), (0.062, 0.068, 0.068), st['jacket'], f'upperarm_{n}',
                    name='deltoid_' + n)
        out['upper_' + n] = k.loft([(s - up * 0.02, 0.061, 0.063), (s.lerp(e, 0.5), 0.057, 0.059),
                                    (e - up * 0.01, 0.052, 0.053)], st['jacket'], f'upperarm_{n}', n=20,
                                   name='upper_' + n)
        k.ellipsoid(e, (0.052, 0.052, 0.052), st['jacket'], f'forearm_{n}', name='elbow_' + n)
        fd = (w - e).normalized()
        out['fore_' + n] = k.loft([(e + fd * 0.01, 0.051, 0.052), (e.lerp(w, 0.5), 0.048, 0.046),
                                   (w - fd * 0.03, 0.042, 0.04)], st['jacket'], f'forearm_{n}', n=20,
                                  name='fore_' + n)
        k.loft([(w - fd * 0.05, 0.044, 0.042), (w - fd * 0.012, 0.044, 0.042)], st['cuff'], f'forearm_{n}', n=20,
               name='cuff_' + n)
        k.loft([(w - fd * 0.02, 0.026, 0.021), (w + fd * 0.01, 0.026, 0.021)], SKIN, f'hand_{n}', n=14,
               name='wrist_' + n, side=V(0, 1, 0).cross(fd))
        fist_shape(k, fist, d, side, f'hand_{n}')
    return out


def fist_shape(k, c, d, side, bone):
    """a fist closed around an upright grip (third-person detail level): knuckle line vertical, palm facing the gun
    in the middle, thumb over the top."""
    left = V(0, 1, 0).cross(d).normalized()
    kl = d.cross(left).normalized()          # along the knuckles, roughly up
    pn = left * side                         # palm normal: towards the middle
    M = Matrix((pn, kl, d)).transposed()
    k.rbox(c - d * 0.022 - pn * 0.004, (0.036, 0.08, 0.072), SKIN, bone, rot=M, p=3.0, name='palm')
    k.capsule(c + d * 0.022 + pn * 0.012 - kl * 0.034, c + d * 0.022 + pn * 0.012 + kl * 0.03, 0.019,
              color=SKIN, bone=bone, name='fingers')
    k.capsule(c - d * 0.03 + kl * 0.03 + pn * 0.012, c + d * 0.02 + kl * 0.036 + pn * 0.022, 0.011, 0.0095,
              color=SKIN, bone=bone, name='thumb')


# ------------------------------------------------------------------------------------------------- helmets

def shell(k, f, color, bone, nt=48, ns=20, thick=0.01, name='shell'):
    """closed helmet shell from its outer surface f(theta, s) -> (point, outward normal); theta 0 = front,
    s 0 = apex .. 1 = rim. The inside is the surface pushed in by `thick`."""
    from .lib import T
    outer, inner = [], []
    for j in range(ns + 1):
        s = j / ns
        for i in range(nt):
            th = math.tau * i / nt
            p, n = f(th, max(s, 1e-3))
            outer.append(T(p))
            inner.append(T(p - n * thick))
    verts = outer + inner
    off = len(outer)
    faces = []
    for j in range(ns):
        for i in range(nt):
            i2 = (i + 1) % nt
            a, b, c, d = j * nt + i, j * nt + i2, (j + 1) * nt + i2, (j + 1) * nt + i
            faces.append((a, b, c, d))
            faces.append((off + d, off + c, off + b, off + a))
    j = ns
    for i in range(nt):
        i2 = (i + 1) % nt
        faces.append((j * nt + i2, j * nt + i, off + j * nt + i, off + j * nt + i2))
    # cap the apex holes (ring 0 is a tiny circle)
    verts.append(T(f(0, 0)[0]))
    verts.append(T(f(0, 0)[0] - f(0, 0)[1] * thick))
    ta, ti = len(verts) - 2, len(verts) - 1
    for i in range(nt):
        i2 = (i + 1) % nt
        faces.append((ta, i2, i))
        faces.append((ti, off + i, off + i2))
    from .lib import _fix_normals
    ob = k.mesh(verts, faces, color, bone, name)
    _fix_normals(ob)
    return ob


def m1_helmet(k, col, strap):
    cy, rx, rz, h = 1.73, 0.12, 0.138, 0.108

    def f(th, s):
        e = (1 - s) * math.pi / 2
        rim = cy + 0.008 * math.cos(th) - 0.016 * abs(math.sin(th)) - 0.006 * max(0.0, -math.cos(th))
        flare = 1 + 0.05 * (max(0.0, s - 0.84) / 0.16) ** 2
        x = rx * math.sin(th) * math.cos(e) * flare
        z = -rz * math.cos(th) * math.cos(e) * flare
        se = math.sin(e)
        y = cy + (rim - cy) * (1 - se) ** 2 + h * se - 0.008 * max(0.0, s - 0.88) / 0.12
        n = V(x / rx ** 2, (y - cy) / h ** 2, z / rz ** 2).normalized()
        return V(x, y, z - HEAD_FWD), n
    shell(k, f, col, 'head', thick=0.009, name='m1')
    return f


def stahlhelm(k, col):
    cy, rx, rz, h = 1.748, 0.11, 0.128, 0.1

    def f(th, s):
        c, sn = math.cos(th), math.sin(th)
        back = max(0.0, -c)          # 1 at the back
        front = max(0.0, c)
        sideish = abs(sn)
        drop = 0.02 * front + 0.068 * sideish * (1 - front) + 0.088 * back   # skirt depth
        drop = lerp(drop, 0.088, back ** 2)
        flare = 0.01 * front + 0.024 * sideish + 0.034 * back
        S0 = 0.66   # dome down to the crown line, then the skirt
        if s <= S0:
            e = (1 - s / S0) * math.pi / 2
            x, z = rx * sn * math.cos(e), -rz * c * math.cos(e)
            y = cy + h * math.sin(e)
            n = V(x / rx ** 2, (y - cy) / h ** 2, z / rz ** 2).normalized()
            return V(x, y, z - HEAD_FWD), n
        t = (s - S0) / (1 - S0)
        x0, z0 = rx * sn, -rz * c
        out = V(sn, 0, -c).normalized()
        # the skirt kinks out a little at the crown line, then flares
        kink = 0.006 * min(1.0, t * 4)
        fl = kink + flare * t ** 1.7
        p = V(x0, cy - drop * t, z0) + out * fl
        n = (out + V(0, -0.4 * (fl / max(drop, 0.01)) - 0.05, 0)).normalized()
        n = (out * (drop + 1e-3) + V(0, fl * 1.7 * t ** 0.7 + 0.002, 0)).normalized()
        return p - V(0, 0, HEAD_FWD), n
    shell(k, f, col, 'head', thick=0.008, ns=26, name='stahlhelm')
    return f


# ------------------------------------------------------------------------------------------------- detail helpers

def buttons_line(k, surf, pts, r, color, bone='torso'):
    for p in pts:
        k.stud(surf, p, r, 0.006, color, bone, name='button')


def belt_pouch(k, surf, ang, y, w, h, depth, color, lid, bone, ry=0.112, rx=0.168, zc=0.0):
    """a box pouch on the belt at angle ang (pi/2 = front centre) with its lid flap."""
    def at(a, yy):
        return (rx * math.cos(a), yy, zc - ry * math.sin(a))
    da = w / ((rx + ry) / 2) / 2
    k.patch(surf, [at(ang + da, y + h / 2), at(ang - da, y + h / 2), at(ang - da, y - h / 2), at(ang + da, y - h / 2)],
            depth, color, bone, nu=4, nv=4, name='pouch', bulge=0.004)
    k.patch(surf, [at(ang + da * 1.06, y + h / 2 + 0.006), at(ang - da * 1.06, y + h / 2 + 0.006),
                   at(ang - da * 1.06, y + h * 0.12), at(ang + da * 1.06, y + h * 0.12)], depth + 0.005, lid, bone,
            nu=4, nv=2, name='pouch_lid')


def mk2(k, c, bone):
    """US Mk 2 fragmentation grenade standing upright at c: olive drab 'pineapple', fuze, spoon and pull ring."""
    c = V(c)
    body_ = k.ellipsoid(c, (0.026, 0.031, 0.026), MK2, bone, name='mk2', n=16, rings=10)
    gs = k.surface([body_])
    for dy in (-0.016, 0.0, 0.016):
        r = 0.026 * math.sqrt(max(0.0, 1 - (dy / 0.031) ** 2))
        ring = [c + V(r * math.cos(a), dy, r * math.sin(a)) for a in [i * math.tau / 12 for i in range(12)]]
        k.strap(gs, ring, 0.003, 0.002, MK2_GROOVE, bone, closed=True, name='groove', role='decal', step=0.01)
    for i in range(6):
        a = i * math.pi / 3
        k.strap(gs, [c + V(0.026 * math.cos(a), -0.028, 0.026 * math.sin(a)) * 1.0 + V(0, 0, 0),
                     c + V(0.026 * math.cos(a), 0.028, 0.026 * math.sin(a))], 0.003, 0.002, MK2_GROOVE, bone,
                name='groove', role='decal', step=0.006)
    k.loft([(c + V(0, 0.028, 0), 0.009, 0.009), (c + V(0, 0.046, 0), 0.008, 0.008)], FUZE, bone, n=10, name='fuze')
    k.rbox(c + V(0.0, 0.03, -0.012), (0.009, 0.042, 0.006), FUZE, bone, name='spoon', p=4)
    k.loft([(c + V(0.012, 0.044, 0.0), 0.009, 0.009), (c + V(0.012, 0.047, 0.0), 0.009, 0.009)], RING, bone, n=10,
           name='ring')


def stick_grenade(k, top, down, bone):
    """Stielhandgranate 24 tucked behind the belt: grey head on top, wooden handle going down."""
    top, down = V(top), V(down).normalized()
    k.loft([(top, 0.034, 0.034), (top + down * 0.07, 0.034, 0.034)], STICK_HEAD, bone, n=16, name='stick_head')
    k.loft([(top + down * 0.068, 0.036, 0.036), (top + down * 0.076, 0.036, 0.036)], STICK_RING, bone, n=16,
           name='stick_collar')
    k.loft([(top + down * 0.075, 0.0145, 0.0145), (top + down * 0.3, 0.0145, 0.0145)], STICK_WOOD, bone, n=10,
           name='stick_handle')
    k.loft([(top + down * 0.3, 0.016, 0.016), (top + down * 0.315, 0.016, 0.016)], STICK_RING, bone, n=10,
           name='stick_cap')
