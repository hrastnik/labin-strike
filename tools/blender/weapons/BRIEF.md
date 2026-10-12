# Weapon modelling brief (for modelling agents)

Goal: replace the game's crude procedural guns with realistic Blender models, each matched closely to a real
side-view photo. Quality bar: a player looking at the first-person view should recognise every characteristic
feature (receiver shape, sights, bolt/charging handle, magazine, stock lines, screws/rivets/pins, vents, bands,
sling swivels...). The silhouette must match the reference photo (IoU ≥ 0.93, ideally ≥ 0.95) and the 3D form must be
right in the other axes too (widths from real dimensions/your knowledge: e.g. a receiver ~25-35 mm wide, a stock
~40 mm at the butt).

## Tools (all paths relative to the repo root /Users/lloyds/Projects/labin-strike)
- `tools/blender/weapons/lib.py` – modelling kit. READ ITS MODULE DOCSTRING AND THE GUN CLASS fully before starting.
- `tools/blender/weapons/models/stg44.py` – finished exemplar. Copy its structure and level of detail.
- `tools/blender/weapons/reftool.py` – reference photos (system `python3`): fetch, pixgrid, rect, crop, profile,
  compare, trace. Read its docstring.
- Build + compare + renders (≈15 s):
  `/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/weapons/build.py -- <id> [--nobeauty] [--fp]`
  prints `[id] N tris`, `id: IoU x.xxx` and writes into `tools/blender/weapons/ref/`:
  `<ref>_cmp_outline.jpg` / `_cmp_blend.jpg` / `_cmp_stack.jpg` (model silhouette vs photo),
  `<id>_beauty_side.png`, `_beauty_q34.png`, `_beauty_fp.png` (shaded renders; fp = in-game first-person framing).
  LOOK at these images (Read tool) after every build. Pipe build output through `grep -E "tris|IoU|Error|Traceback|File"`.
- Materials (keys for `mat=`): blued, blued_old, phosphate, park (US parkerised), paint, bright (polished steel),
  walnut, beech, laminate, bakelite, black, checker_w / checker_b (chequered wood / chequered grips), brass,
  leather, feldgrau, glass. Pick by the real weapon's finish.
- Reference sources live in `tools/blender/weapons/ref/src/<id>.jpg` (from `refs.json`). Some are poor (cutaway
  drawings, perspective, two guns in one picture, low resolution). If a reference is not a clean, orthogonal,
  full side view of the right model, find a better one on Wikimedia Commons (agent-browser, ALWAYS with
  `--session <your-agent-name>` since other agents use the browser too; or the Commons API via curl/WebFetch) and
  register it in `tools/blender/weapons/cal/<id>.json` (`title`, `page`, `license`, `length_mm`, then `cal`),
  then `python3 tools/blender/weapons/reftool.py fetch <id>`. Right-side views (muzzle pointing right) are what the
  tools expect; a left-side photo can be mirrored via a new id only if you also mirror it (prefer a right-side photo).
  Extra crops/detail photos may be used to understand 3D shape (top views, close-ups).

## Workflow per weapon
1. View the source photo. `reftool.py pixgrid <id>` → read `ref/<id>_pixgrid.jpg`, pick calibration points
   (muzzle centre, a point on the bore axis further back, trigger front face, rearmost point), write them to
   `tools/blender/weapons/cal/<id>.json` as `{"cal": {...}}` (plus `crop` for multi-gun images). NEVER edit refs.json.
   `reftool.py rect <id>` → check `ref/<id>_grid.jpg` (mm grid in model space) and `ref/<id>_mask.png`
   (segmentation; it must be clean – see the bg / crop options; a bad mask ruins traces and IoU).
2. Measure with `reftool.py crop <id> u0 u1 v0 v1` and `profile`. Use `g.outline(region)` (traced from the mask) for
   organic outlines (stocks, grips, magazines), explicit profiles / lathes for machined parts.
3. Write `tools/blender/weapons/models/<id>.py` (REF, META, build(g)). Build, compare, fix, repeat. Typically 8-20
   iterations. Check the q34 and fp renders for 3D correctness (nothing floating, no gaps, no z-fighting,
   symmetric parts mirrored, plausible widths). Add the small details last (screws, pins, rivets, sling swivels,
   knurling, serrations, sight details) – they matter in first person.
4. Budget: rifles/MGs ≤ 35k tris, SMGs ≤ 25k, pistols ≤ 15k, knives/grenade ≤ 8k. Model what's visible; the
   inside of receivers is not.

## Game contract (must match the client)
Model frame: u forward along the bore, v up, w right, mm; origin u=0 at the trigger's front face, v=0 on the
bore axis. Anchors (`g.anchor`), all required for guns:
- `muzzle` (muzzle face centre), `sight` (u of the rear sight, v = height of the sight line = top of front post /
  bottom of rear notch; w ≠ 0 only for offset sights), `eject` (ejection port centre, w on the ejecting side),
  `rh` (centre of the right hand on the pistol grip/wrist, ~ middle of the grip), `lh` (support hand on the
  forend/handguard/magazine housing – where a soldier actually holds it), `eye` (where the aiming eye sits:
  for stocked weapons over the comb, ~250-320 mm behind the rear sight, v = sight line; pistols: ~ u = -450).
Parts (`with g.part('<name>'):` + `g.pivot`): read the weapon's procedural builder in `client/src/gunmodels.js`
and the reload animation in `client/src/viewmodel.js` to see what is animated, then match it:
- `mag` – detachable magazine (or the clip/charger shown during reload); pivot at the magazine's top centre. Its
  removal direction is META `client.magDir` in three.js axes [x=w, y=v, z=-u] (default [0,-1,0]); set it if the
  magazine leaves along a different direction (curved/raked mags, side/top mags).
- `bolt` – bolt-action rifles: bolt with handle; pivot on the bore axis (u at the bolt body's centre, v = bore,
  w = 0) – the client rotates it about the bore axis (handle on the right goes up by 1.2 rad) then pulls it back
  70 mm. Luger: the toggle is the 'bolt'.
- `cover` – belt MG feed cover, pivot at its front hinge; client rotates it by -1.1 rad about w (rear goes up).
- `breakTop` – Webley: the barrel half (barrel, top strap, cylinder, extractor) at the hinge pin; the client rotates it −0.7 rad about +w (muzzle down). Frame, grip and hammer stay in body with the hands.
Gameplay metadata (hip position, kick, magHidden, ejectDown, ...) stays in gunmodels.js; you only need META
`client` overrides when the model needs different values (magDir most commonly). META `kind` = 'rifle' | 'pistol'.
Non-guns: knives – u along the blade toward the tip, origin at the middle of the grip, v = spine up/edge down;
grenade – u along the stick toward the head (head at +u), origin at the balance point (~ where the head meets the
stick). Knives/grenade need no anchors; set META `{'kind': 'melee'}` / `{'kind': 'grenade'}`.

## Rules
- Only create/modify: `tools/blender/weapons/models/<your ids>.py`, `tools/blender/weapons/cal/<your ids>.json`,
  and generated files under `tools/blender/weapons/ref/` for your ids. Do NOT edit lib.py, materials.py, bake.py,
  render.py, reftool.py, build.py, export.py, refs.json or anything in client/. If you need a helper, write it inside
  your model file; mention useful generic helpers in your final report.
- Do NOT run build.py with --export, do not touch client/public, do not commit or push.
- Final report (short): per id – reference used (title + licence), IoU, tris, parts, anchors, any open issues,
  and the paths of the final cmp_outline and beauty_fp images.
