"""Kar98k sniper: the kar98k base (kar98k.py) with a Zeiss ZF39 4x scope on the high turret mount
(front turret base on the receiver ring, rear base with locking lever on the bridge). Iron sights stay on the rifle,
as on the real thing. Loaded one round at a time (client mag: 1), so the 'mag' part is a single cartridge.

ZF39: ~270 mm long, 26 mm tube, ~39 mm ocular and objective bells, elevation drum on top."""
from .kar98k import build as base

REF = 'kar98k'
META = {'kind': 'rifle', 'magHidden': True, 'compare': False}

AXIS_V = 50.0          # optical axis height above the bore
OCU_U = -15.0          # rear face of the eyepiece
OBJ_U = 255.0          # front face of the objective bell
R_TUBE = 13.0


def scope(g):
    v = AXIS_V
    # main body: eyepiece bell, 26 mm tube, objective bell; both ends recessed for the lenses
    prof = [(OCU_U + 7, 0), (OCU_U + 7, 15.2), (OCU_U, 15.6), (OCU_U, 18.2), (OCU_U + 2, 19.3), (OCU_U + 24, 19.3),
            (OCU_U + 27, 18.4), (OCU_U + 32, 16.6), (OCU_U + 44, R_TUBE), (190, R_TUBE), (205, 15.2), (224, 18.8),
            (OBJ_U - 3, 19.4), (OBJ_U, 18.6), (OBJ_U, 17.0), (OBJ_U - 7, 16.6), (OBJ_U - 7, 0)]
    g.lathe(prof, 'blued', at=(v, 0), seg=40, name='scopebody')
    # eyepiece focusing ring grooves
    for u in (OCU_U + 8, OCU_U + 15):
        g.tube(u, u + 3, 19.8, 18.0, 'blued', at=(v, 0), seg=40)
    # lenses
    g.cyl(OCU_U + 5.5, OCU_U + 7.5, 15.4, 'glass', at=(v, 0), seg=32, name='ocular_lens')
    g.cyl(OBJ_U - 7.5, OBJ_U - 5.5, 16.8, 'glass', at=(v, 0), seg=32, name='objective_lens')
    # mid saddle with the elevation drum on top
    g.lathe([(88, 13.5), (90, 15.8), (114, 15.8), (116, 13.5)], 'blued', at=(v, 0), seg=40, closed=False)
    g.lathe([(v + 12, 12.0), (v + 17, 12.0), (v + 17, 14.6), (v + 29, 14.6), (v + 30.5, 13.4), (v + 30.5, 0)],
            'blued', axis='v', at=(102, 0), seg=32, name='drum')
    g.lathe([(v + 21, 15.0), (v + 24, 15.0)], 'bright', axis='v', at=(102, 0), seg=32)   # range scale band
    # small windage cap on the left
    g.lathe([(-12, 10.5), (-19, 10.5), (-19, 0)], 'blued', axis='w', at=(102, v), seg=24)

    # front turret mount on the receiver ring: round turret base, standoff, split ring
    g.lathe([(14, 13.5), (26, 13.5), (27, 12.5), (27, 0)], 'blued', axis='v', at=(172, 0), seg=28, name='turret')
    g.extrude([(-9, 24), (9, 24), (8, v - 10), (-8, v - 10)], 164, 180, 'blued', plane='front', bevel=0.8)
    g.tube(163, 181, R_TUBE + 3.6, R_TUBE - 0.2, 'blued', at=(v, 0), seg=40, name='front_ring')
    g.box(166, 178, v + 15, v + 18.5, width=10, mat='blued', bevel=0.6)              # ring cap screw boss
    # rear base on the bridge, standoff, ring and the locking lever on the left
    g.box(34, 60, 12.5, 23, width=22, mat='blued', bevel=1.2, name='rearbase')
    g.extrude([(-8.5, 22), (8.5, 22), (7.5, v - 10), (-7.5, v - 10)], 40, 55, 'blued', plane='front', bevel=0.8)
    g.tube(39, 56, R_TUBE + 3.6, R_TUBE - 0.2, 'blued', at=(v, 0), seg=40, name='rear_ring')
    g.box(42, 53, v + 15, v + 18.5, width=10, mat='blued', bevel=0.6)
    g.pipe([(47, 18, -11.5), (40, 18, -13.5), (16, 15, -14.5)], 2.2, 'blued', seg=10, corner=3, name='lever')
    g.box(13, 19, 12.5, 17.5, w0=-17, w1=-12, mat='blued', bevel=0.8)


def build(g):
    base(g, scoped=True)
    scope(g)
    g.anchor('sight', OCU_U, AXIS_V)
    g.anchor('eye', OCU_U - 80, AXIS_V)
