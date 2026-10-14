// Blender-modelled soldiers and first-person arms from soldiers.glb (tools/blender/soldiers):
//   soldier_allies / soldier_axis   skinned bodies; their skeleton's bone heads are the pivots avatars.js animates
//   fp_upper_<team> / fp_fore_<team> first-person sleeves along +y from the shoulder / elbow (cuff at FORE)
//   fp_hand_r / fp_hand_l            the soldier's fists in their grip frame: origin mid-fist, +y along the grip
//                                    (little finger to index), +z towards the wrist; extras wrist, fore
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js'

const _a = new THREE.Vector3()
const _b = new THREE.Vector3()
const _c = new THREE.Vector3()
const _m = new THREE.Matrix4()
const _m2 = new THREE.Matrix4()
const _q = new THREE.Quaternion()
const Y = new THREE.Vector3(0, 1, 0)
const FORE = 0.26 // elbow to wrist (first person)
const UPPER = 0.29 // shoulder to elbow (first person)
const CUFF_GAP = 0.022 // cuff to wrist joint
const WRIST_BEND = 0.42 // radians the forearm may leave the line of the hand (the cuff hides the wrist up to here)

const T = { soldiers: {}, rest: {}, parents: {}, fp: {} }

export async function loadSoldierModels (url) {
  const loader = new GLTFLoader()
  loader.setMeshoptDecoder(MeshoptDecoder)
  const gltf = await loader.loadAsync(url)
  gltf.scene.updateMatrixWorld(true)
  gltf.scene.traverse((o) => {
    if (o.isSkinnedMesh) {
      const team = o.name.replace('soldier_', '')
      o.geometry.computeBoundingSphere()
      o.material.roughness = 0.9
      T.soldiers[team] = { geometry: o.geometry, material: o.material, bones: o.skeleton.bones.map((b) => b.name) }
      for (const b of o.skeleton.bones) {
        T.rest[b.name] ??= b.getWorldPosition(new THREE.Vector3())
        T.parents[b.name] ??= b.parent?.isBone ? b.parent.name : null
      }
    } else if (o.isMesh && o.name.startsWith('fp_')) {
      o.updateMatrixWorld()
      const geo = o.geometry.clone().applyMatrix4(o.matrixWorld)
      geo.computeBoundingSphere()
      const e = o.userData
      T.fp[o.name.replace('fp_', '')] = {
        geometry: geo,
        material: o.material,
        wrist: e.wrist && new THREE.Vector3(...e.wrist),
        fore: e.fore && new THREE.Vector3(...e.fore)
      }
    }
  })
  return T
}

export const hasSoldierModels = () => !!(T.soldiers.allies && T.soldiers.axis)

// ------------------------------------------------------------------ third person

/**
 * A soldier's skinned body with its bones as plain pivots (identity rest rotations, so the animation code can set
 * rotations directly). Returns { mesh, bones: name -> THREE.Bone, arms: [right, left] } or null without the model.
 * Call with the bones' owner (`root`) still at the origin: the bind pose is taken from it.
 */
export function buildSoldier (team, root) {
  const t = T.soldiers[team] || T.soldiers.allies
  if (!t) return null
  const bones = {}
  for (const name of t.bones) {
    const b = new THREE.Bone()
    b.name = name
    bones[name] = b
  }
  for (const name of t.bones) {
    const p = T.parents[name]
    const b = bones[name]
    b.position.copy(T.rest[name])
    if (p) {
      b.position.sub(T.rest[p])
      bones[p].add(b)
    } else root.add(b)
  }
  root.updateMatrixWorld(true)
  const mesh = new THREE.SkinnedMesh(t.geometry, t.material)
  mesh.castShadow = true
  mesh.userData.shared = true
  root.add(mesh)
  mesh.updateMatrixWorld(true)
  mesh.bind(new THREE.Skeleton(t.bones.map((n) => bones[n])))
  // a generous fixed bound: limbs swing and the body falls, but never this far
  mesh.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0.9, 0), 1.6)
  const arms = ['r', 'l'].map((s) => arm(bones[`upperarm_${s}`], bones[`forearm_${s}`], bones[`hand_${s}`]))
  return { mesh, bones, arms }
}

function arm (upper, fore, hand) {
  return {
    upper,
    fore,
    hand,
    shoulder: upper.position.clone(),
    restU: fore.position.clone(), // shoulder -> elbow, in the upper arm's (= the aim pivot's) frame
    restF: hand.position.clone(), // elbow -> wrist
    lenU: fore.position.length(),
    lenF: hand.position.length()
  }
}

/**
 * Two-bone IK: bend arm `a` so its wrist reaches `target` (in the frame of the upper arm's parent), the elbow pushed
 * towards `pole`. A target out of reach brings the shoulder forward a little (up to `reach` metres) first.
 */
export function aimArm (a, target, pole, reach = 0.08) {
  const s = _a.copy(a.shoulder)
  const d = _b.copy(target).sub(s)
  const full = a.lenU + a.lenF - 1e-3
  let dist = d.length()
  if (dist > full) {
    s.addScaledVector(d, Math.min(reach, dist - full) / dist)
    d.copy(target).sub(s)
    dist = d.length()
  }
  a.upper.position.copy(s)
  dist = THREE.MathUtils.clamp(dist, Math.abs(a.lenU - a.lenF) + 1e-3, full)
  d.normalize()
  const cosA = THREE.MathUtils.clamp((a.lenU * a.lenU + dist * dist - a.lenF * a.lenF) / (2 * a.lenU * dist), -1, 1)
  const perp = _c.copy(pole).addScaledVector(d, -pole.dot(d))
  if (perp.lengthSq() < 1e-8) perp.set(0, -1, 0)
  perp.normalize()
  const elbow = new THREE.Vector3().copy(d).multiplyScalar(a.lenU * cosA).addScaledVector(perp, a.lenU * Math.sqrt(1 - cosA * cosA))
  const wrist = new THREE.Vector3().copy(d).multiplyScalar(dist)
  const u1 = elbow.clone().normalize()
  const f1 = wrist.clone().sub(elbow).normalize()
  // rest and target frames: the bone's direction and the arm's bending-plane normal
  const u0 = a.restU.clone().normalize()
  const f0 = a.restF.clone().normalize()
  const n0 = u0.clone().cross(f0).normalize()
  const n1 = u1.clone().cross(f1)
  if (n1.lengthSq() < 1e-8) n1.copy(perp).cross(u1)
  n1.normalize()
  const Ru = frameRotation(u0, n0, u1, n1)
  a.upper.quaternion.setFromRotationMatrix(Ru)
  const Rf = frameRotation(f0, n0, f1, n1)
  a.fore.quaternion.setFromRotationMatrix(_m2.copy(Ru).invert().multiply(Rf))
}

// the rotation taking the orthonormal frame (x0, n0) to (x1, n1)
function frameRotation (x0, n0, x1, n1) {
  const b0 = new THREE.Vector3().crossVectors(x0, n0)
  const b1 = new THREE.Vector3().crossVectors(x1, n1)
  _m.makeBasis(x0, n0, b0)
  return new THREE.Matrix4().makeBasis(x1, n1, b1).multiply(_m.transpose())
}

// ------------------------------------------------------------------ first person

// shoulders in the viewmodel's gun-rooted space (the gun's origin is its trigger): the arms come from here. A pistol is
// held out in the right hand
const SHOULDER = [new THREE.Vector3(0.17, -0.26, 0.46), new THREE.Vector3(-0.2, -0.28, 0.34)]
const PISTOL_SHOULDER = [new THREE.Vector3(0.16, -0.26, 0.6)]

// grip axes (little finger -> index) in gun space
const AXIS = {
  pistolGrip: new THREE.Vector3(0, 0.95, -0.31),
  steep: new THREE.Vector3(0, 0.86, -0.51),
  wrist: new THREE.Vector3(0, 0.62, -0.78),
  forend: new THREE.Vector3(0, 0.08, -1),
  pistol: new THREE.Vector3(0, 0.92, -0.39),
  luger: new THREE.Vector3(0, 0.8, -0.6)
}
const RIGHT_GRIP = {
  stg44: 'pistolGrip', mp40: 'pistolGrip', mg42: 'pistolGrip', thompson: 'pistolGrip', m3: 'pistolGrip',
  m1919a6: 'pistolGrip', bren: 'pistolGrip', fg42: 'steep', luger: 'luger'
}

/** right and left fist placements { side, at, axis, fore?, tip?, bend? } for a gun spec (gun space). */
function grips (spec) {
  if (spec.kind === 'pistol') {
    // held out in the right hand alone, wrist nearly straight: the forearm runs back in line with the gun, a little
    // low and to the right, the grip lying diagonally across the palm
    const at = new THREE.Vector3(0.004, -0.07, 0.048) // the middle of the right fist, under the trigger guard
    return [{ side: 'r', at, axis: AXIS[RIGHT_GRIP[spec.id] || 'pistol'], fore: new THREE.Vector3(0.22, -0.3, 1), tip: 0.4 }]
  }
  const rh = spec.rh || [0.005, -0.075, 0.075]
  const lh = spec.lh || [-0.01, -0.02, -0.28]
  return [
    { side: 'r', at: new THREE.Vector3(0, rh[1], rh[2]), axis: AXIS[RIGHT_GRIP[spec.id] || 'wrist'] },
    // the support fist cradles the forend from below and to the left, its forearm slanting back down towards the
    // left shoulder
    { side: 'l', at: new THREE.Vector3(-0.006, lh[1] - 0.026, lh[2]), axis: AXIS.forend, fore: new THREE.Vector3(-0.65, -0.7, 0.4), tip: 0.4 }
  ]
}

/** first-person arms holding a gun: added to `root` (the gun's own group). Null without the models. */
export function buildFPArms (root, team, spec) {
  if (!hasSoldierModels() || !T.fp.hand_r) return null
  const arms = new THREE.Group()
  root.add(arms)
  const sh = spec.kind === 'pistol' ? PISTOL_SHOULDER : SHOULDER
  // hip view: off to the right and close to the eye; a one-handed pistol sits low, just right of the middle
  if (spec.kind === 'pistol') spec.hip.set(0.07, -0.1, -0.44)
  else spec.hip.add(new THREE.Vector3(0.035, 0, 0.09))
  grips(spec).forEach((g, i) => fpArm(arms, team, g.side, g.at, g.axis, sh[i], i ? -1 : 1, g.fore, g.tip))
  return arms
}

/** a single right arm closing its fist about `axis` at `at` (grenade handle, knife grip). */
export function buildFPFist (root, team, at, axis, shoulder) {
  if (!hasSoldierModels() || !T.fp.hand_r) return null
  return fpArm(root, team, 'r', at, axis, shoulder || SHOULDER[0], 1)
}

// fore: the way the forearm should leave the fist (default: towards the shoulder). The fist's own forearm leaves at
// right angles to its grip; a real hand holds the grip diagonally across the palm and bends at the wrist, so the
// fist tips off the grip axis by up to `tip` radians and the wrist bends the rest of the way (up to WRIST_BEND)
function fpArm (parent, team, side, at, axis, shoulder, sgn, fore = null, tip = 0) {
  const h = T.fp['hand_' + side]
  const want = (fore ? fore.clone() : shoulder.clone().sub(at)).normalize()
  const ax = axis.clone().normalize()
  if (tip > 0) {
    // the grip axis at right angles to the forearm, and as far towards it as the fist may tip
    const perp = ax.clone().addScaledVector(want, -ax.dot(want))
    if (perp.lengthSq() > 1e-8) {
      const ang = Math.min(tip, ax.angleTo(perp.normalize()))
      ax.applyAxisAngle(_a.crossVectors(ax, perp).normalize(), ang)
    }
  }
  // grip axis first, then roll about it until the forearm heads the wanted way
  const q = new THREE.Quaternion().setFromUnitVectors(Y, ax)
  const hf = h.fore.clone().applyQuaternion(q)
  const w = want.clone()
  hf.addScaledVector(ax, -hf.dot(ax))
  w.addScaledVector(ax, -w.dot(ax))
  if (hf.lengthSq() > 1e-8 && w.lengthSq() > 1e-8) {
    hf.normalize(); w.normalize()
    const ang = Math.atan2(_a.crossVectors(hf, w).dot(ax), hf.dot(w))
    q.premultiply(_q.setFromAxisAngle(ax, ang))
  }
  const wrist = h.wrist.clone().applyQuaternion(q).add(at)
  // the wrist bends the rest of the way, and the fist's wrist with it (into the sleeve, not out through it)
  const toElbow = h.fore.clone().applyQuaternion(q).normalize()
  const bend = Math.min(WRIST_BEND, toElbow.angleTo(want))
  let geometry = h.geometry
  if (bend > 1e-3) {
    const bendAxis = _b.crossVectors(toElbow, want).normalize()
    toElbow.applyAxisAngle(bendAxis, bend)
    geometry = bendWrist(h, bendAxis.clone().applyQuaternion(_q.copy(q).invert()), bend)
  }
  const hand = new THREE.Mesh(geometry, h.material)
  hand.userData.shared = geometry === h.geometry
  hand.position.copy(at)
  hand.quaternion.copy(q)
  parent.add(hand)
  const elbow = wrist.clone().addScaledVector(toElbow, FORE)
  const sh = elbow.clone().add(shoulder.clone().sub(elbow).normalize().multiplyScalar(UPPER))
  // the cuff stops short of the wrist so the fist and a bit of wrist show (the fist's wrist runs on into the sleeve)
  sleeve(parent, `fore_${team}`, elbow.clone().addScaledVector(toElbow, CUFF_GAP), wrist.clone().addScaledVector(toElbow, CUFF_GAP), sgn)
  sleeve(parent, `upper_${team}`, sh, elbow, sgn)
  return { hand, wrist, elbow }
}

// a copy of fist `h` with its wrist bent by `angle` about `axis` (fist frame): the hand stays, the wrist and the forearm
// stub beyond it turn about the wrist joint, eased in across the heel of the hand
function bendWrist (h, axis, angle) {
  const geo = h.geometry.clone()
  const pos = geo.attributes.position
  const nrm = geo.attributes.normal
  const z0 = h.wrist.z - 0.02
  const z1 = h.wrist.z + 0.01
  const v = new THREE.Vector3()
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i)
    const t = THREE.MathUtils.smoothstep(v.z, z0, z1)
    if (t <= 0) continue
    _q.setFromAxisAngle(axis, angle * t)
    v.sub(h.wrist).applyQuaternion(_q).add(h.wrist)
    pos.setXYZ(i, v.x, v.y, v.z)
    if (nrm) { v.fromBufferAttribute(nrm, i).applyQuaternion(_q); nrm.setXYZ(i, v.x, v.y, v.z) }
  }
  geo.computeBoundingSphere()
  return geo
}

// a sleeve mesh along +y from `from` towards `to`, its outside (+x) turned outwards and up; mirrored on the left
function sleeve (parent, key, from, to, sgn) {
  const s = T.fp[key] || T.fp[key.replace(/_\w+$/, '_allies')]
  const m = new THREE.Mesh(s.geometry, s.material)
  m.userData.shared = true
  const y = to.clone().sub(from).normalize()
  const ref = new THREE.Vector3(1, sgn > 0 ? 0.6 : -0.6, 0)
  const x = ref.addScaledVector(y, -ref.dot(y)).normalize()
  const z = new THREE.Vector3().crossVectors(x, y)
  m.quaternion.setFromRotationMatrix(_m.makeBasis(x, y, z))
  m.position.copy(from)
  if (sgn < 0) m.scale.x = -1
  parent.add(m)
  return m
}
