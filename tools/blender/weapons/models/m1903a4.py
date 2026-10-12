"""M1903A4 sniper: the m1903 base (m1903.py) without iron sights, with the bolt handle forged down and back,
a Redfield one-piece base with split rings and an M73B1 (Weaver 330C) 2.2x scope. Loaded one round at a time
(client mag: 1), so the 'mag' part is a single cartridge.

M73B1: ~275 mm long, 3/4 in (19 mm) tube, slightly enlarged eyepiece and objective, windage/elevation turret."""
from .m1903 import build as base

REF = 'm1903'
META = {'kind': 'rifle', 'magHidden': True, 'compare': False}

AXIS_V = 41.0          # optical axis height above the bore
OCU_U = -23.0          # rear face of the eyepiece
OBJ_U = 252.0          # front face of the objective
R_TUBE = 9.5


def scope(g):
    v = AXIS_V
    prof = [(OCU_U + 6, 0), (OCU_U + 6, 13.0), (OCU_U, 13.4), (OCU_U, 15.6), (OCU_U + 2, 16.3), (OCU_U + 27, 16.3),
            (OCU_U + 30, 15.4), (OCU_U + 42, 11.0), (OCU_U + 50, R_TUBE), (224, R_TUBE), (231, 10.9),
            (OBJ_U - 3, 11.3), (OBJ_U, 10.8), (OBJ_U, 9.6), (OBJ_U - 5, 9.3), (OBJ_U - 5, 0)]
    g.lathe(prof, 'blued', at=(v, 0), seg=36, name='scopebody')
    g.tube(OCU_U + 9, OCU_U + 12, 16.7, 15.0, 'blued', at=(v, 0), seg=36)      # eyepiece lock ring
    g.cyl(OCU_U + 4.5, OCU_U + 6.5, 13.2, 'glass', at=(v, 0), seg=32, name='ocular_lens')
    g.cyl(OBJ_U - 6.5, OBJ_U - 4.5, 9.5, 'glass', at=(v, 0), seg=28, name='objective_lens')
    # turret: saddle, elevation knob on top, windage knob on the right
    g.lathe([(96, 9.0), (98, 11.8), (120, 11.8), (122, 9.0)], 'blued', at=(v, 0), seg=36)
    g.box(99, 119, v, v + 13.5, width=19, mat='blued', bevel=2.0, name='saddle')
    for axis, at in (('v', (109, 0)), ('w', (109, v))):
        x0 = v + 13 if axis == 'v' else 9
        g.lathe([(x0, 7.6), (x0 + 6, 7.6), (x0 + 6, 8.4), (x0 + 11, 8.4), (x0 + 12, 7.4), (x0 + 12, 0)], 'blued',
                axis=axis, at=at, seg=24, name='knob_' + axis)

    # Redfield one-piece base over the bridge and the receiver ring (open over the ejection port)
    g.extrude([(14, 17.0), (64, 17.0), (64, 22.5), (18, 22.5, 3)], width=20, mat='blued', plane='side', bevel=1.0,
              name='base_rear')
    g.extrude([(140, 17.0), (190, 17.0), (186, 22.5, 3), (140, 22.5)], width=20, mat='blued', plane='side',
              bevel=1.0, name='base_front')
    for s in (1, -1):       # side rails joining the two pads
        g.box(60, 144, 17.5, 22.5, w0=min(s * 6.5, s * 10), w1=max(s * 6.5, s * 10), mat='blued', bevel=0.6)
    for u0, u1 in ((34, 47), (156, 169)):    # split rings with standoffs
        g.extrude([(-9, 21), (9, 21), (7.5, v - 8), (-7.5, v - 8)], u0 + 1, u1 - 1, 'blued', plane='front',
                  bevel=0.8)
        g.tube(u0, u1, R_TUBE + 3.0, R_TUBE - 0.2, 'blued', at=(v, 0), seg=36)
        for s in (1, -1):   # ring clamp screws
            g.cyl(s * 11.5, s * 14.5, 2.6, 'blued', axis='w', at=((u0 + u1) / 2, v - 1), seg=10)
    for s in (1, -1):       # rear windage screws of the Redfield ring mount
        g.cyl(s * 10, s * 15, 3.0, 'blued', axis='w', at=(40.5, 20), seg=12)


def build(g):
    base(g, scoped=True)
    scope(g)
    g.anchor('sight', OCU_U, AXIS_V)
    g.anchor('eye', OCU_U - 80, AXIS_V)
