// Procedural low-poly weapon models, shared by the first-person viewmodel, third-person soldiers and loadout icons.
// Units are metres; the bore points down -Z, +Y is up. Each builder returns the gun group plus the animated parts
// and anchor points the viewmodel needs (muzzle, sight height, hand positions, magazine, bolt, feed cover...).
import * as THREE from 'three'
import { applyWeaponModel, modelClone } from './weaponmodels.js'

function mat (color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.72, metalness: 0.0, flatShading: true, ...opts })
}

export const M = {
  steel: mat('#2d2f31', { metalness: 0.65, roughness: 0.42 }),
  steelLight: mat('#4a4d50', { metalness: 0.7, roughness: 0.38 }),
  parker: mat('#3b3e36', { metalness: 0.45, roughness: 0.6 }), // US parkerised steel
  black: mat('#1d1e20', { metalness: 0.4, roughness: 0.55 }),
  wood: mat('#6a4325', { roughness: 0.6 }),
  woodDark: mat('#4a2e1a', { roughness: 0.65 }),
  woodLight: mat('#86562f', { roughness: 0.6 }), // US walnut
  woodRed: mat('#6b3a22', { roughness: 0.62 }), // German laminate / British beech
  bakelite: mat('#3b2a1e', { roughness: 0.5 }),
  leather: mat('#6b4a2c', { roughness: 0.7 }),
  skin: mat('#c99a78', { roughness: 0.8 }),
  glove: mat('#3a2f25', { roughness: 0.9 }),
  brass: mat('#c9a043', { metalness: 0.8, roughness: 0.3 }),
  feldgrau: mat('#565c4b', { metalness: 0.35, roughness: 0.6 }),
  glass: mat('#203040', { metalness: 0.9, roughness: 0.15 })
}

export function makeSleeve (color) { return mat(color, { roughness: 0.95 }) }

// ------------------------------------------------------------------ primitives

const V = (x, y, z) => new THREE.Vector3(x, y, z)

function group (parent, x = 0, y = 0, z = 0) {
  const g = new THREE.Group()
  g.position.set(x, y, z)
  parent?.add(g)
  return g
}

function box (w, h, d, material, x = 0, y = 0, z = 0, parent) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material)
  m.position.set(x, y, z)
  parent?.add(m)
  return m
}

function cylZ (r, len, material, x, y, z, parent, seg = 10) {
  const g = new THREE.CylinderGeometry(r, r, len, seg)
  g.rotateX(Math.PI / 2)
  const m = new THREE.Mesh(g, material)
  m.position.set(x, y, z)
  parent?.add(m)
  return m
}

function coneZ (r0, r1, len, material, x, y, z, parent, seg = 10) {
  const g = new THREE.CylinderGeometry(r1, r0, len, seg)
  g.rotateX(Math.PI / 2)
  const m = new THREE.Mesh(g, material)
  m.position.set(x, y, z)
  parent?.add(m)
  return m
}

function cylY (r, len, material, x, y, z, parent, seg = 8) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, seg), material)
  m.position.set(x, y, z)
  parent?.add(m)
  return m
}

function sphere (r, material, x, y, z, parent) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(r, 8, 6), material)
  m.position.set(x, y, z)
  parent?.add(m)
  return m
}

// tapered 4-sided butt stock (same construction as the original StG 44 stock)
function buttStock (parent, material, { z, y, len, r0, r1, sx = 0.8, sy = 1.5, rotX = 0.14 }) {
  const g = new THREE.CylinderGeometry(r0, r1, len, 4, 1)
  g.rotateY(Math.PI / 4)
  g.rotateX(Math.PI / 2)
  g.scale(sx, sy, 1)
  const m = new THREE.Mesh(g, material)
  m.position.set(0, y, z)
  m.rotation.x = rotX
  parent.add(m)
  return m
}

function grip (parent, material, { z, y = -0.075, h = 0.1, rake = 0.28, w = 0.032, d = 0.045 }) {
  const m = box(w, h, d, material, 0, y, z, parent)
  m.rotation.x = rake
  return m
}

function triggerGuard (parent, z, y = -0.06, len = 0.06) {
  box(0.008, 0.008, len, M.steel, 0, y, z, parent)
  box(0.006, 0.02, 0.006, M.steel, 0, y + 0.015, z, parent)
}

// front post + rear notch on the sight line `y`
function ironSights (parent, { y, front, rear, x = 0, ears = false, material = M.steel }) {
  box(0.005, 0.02, 0.006, material, x, y - 0.007, front, parent)
  if (ears) {
    box(0.003, 0.024, 0.016, material, x - 0.011, y - 0.008, front, parent)
    box(0.003, 0.024, 0.016, material, x + 0.011, y - 0.008, front, parent)
  }
  box(0.03, 0.012, 0.03, material, x, y - 0.013, rear, parent)
  box(0.009, 0.012, 0.006, material, x - 0.01, y - 0.002, rear, parent)
  box(0.009, 0.012, 0.006, material, x + 0.01, y - 0.002, rear, parent)
}

// straight or curved box magazine hanging below (or, rotated, beside / above) the gun
function boxMag (parent, { x = 0, y, z, segs = 4, w = 0.026, d = 0.04, seg = 0.045, curve = 0, material = M.steel, rotZ = 0 }) {
  const g = group(parent, x, y, z)
  for (let i = 0; i < segs; i++) {
    const s = box(w, seg + 0.005, d, material, 0, -seg / 2 - i * seg, -i * i * curve - i * curve * 1.3, g)
    s.rotation.x = -i * curve * 20
  }
  g.rotation.z = rotZ
  return g
}

// stripper clip / single round shown above the action while reloading an internal magazine
function clipRounds (parent, { y, z, rounds }) {
  const g = group(parent, 0, y, z)
  if (rounds > 1) box(0.016, 0.004, rounds * 0.0105 + 0.006, M.steel, 0, -0.027, 0, g)
  for (let i = 0; i < rounds; i++) {
    cylY(0.0045, 0.046, M.brass, 0, 0, (i - (rounds - 1) / 2) * 0.0105, g, 6)
    cylY(0.0028, 0.012, M.brass, 0, 0.029, (i - (rounds - 1) / 2) * 0.0105, g, 6)
  }
  return g
}

// turn-bolt with a handle on the right; rotates about the bore (rotation.z) and slides back (+z)
function turnBolt (parent, { y, z, bent = true, len = 0.09 }) {
  const bolt = group(parent, 0, y, z)
  cylZ(0.0115, len, M.steelLight, 0, 0, 0, bolt)
  const h = box(0.046, 0.008, 0.008, M.steelLight, 0.024, 0, len * 0.3, bolt)
  h.rotation.z = bent ? -0.65 : -0.15
  sphere(0.011, M.steelLight, 0.044, bent ? -0.026 : -0.007, len * 0.3, bolt)
  return bolt
}

// ventilated machine-gun barrel jacket: alternating rings read as cooling holes at a distance
function jacket (parent, { r, y, z0, z1, material = M.steel, holes = 9 }) {
  const len = z0 - z1
  cylZ(r * 0.92, len, M.black, 0, y, (z0 + z1) / 2, parent, 10)
  const step = len / holes
  for (let i = 0; i < holes; i++) cylZ(r, step * 0.45, material, 0, y, z0 - step * (i + 0.5), parent, 10)
  cylZ(r * 1.04, 0.012, material, 0, y, z0 - 0.006, parent, 10)
  cylZ(r * 1.04, 0.012, material, 0, y, z1 + 0.006, parent, 10)
}

function bipod (parent, { y, z, spread = 0.03, len = 0.26, folded = true, material = M.steel }) {
  const g = group(parent, 0, y, z)
  for (const s of [-1, 1]) {
    const leg = cylZ(0.0045, len, material, s * spread, 0, folded ? len / 2 : 0, g, 6)
    if (!folded) { leg.rotation.x = Math.PI / 2; leg.position.set(s * spread, -len / 2, 0) }
  }
  box(spread * 2 + 0.012, 0.012, 0.014, material, 0, 0, 0, g)
  return g
}

function scope (parent, { y, z0, z1, r = 0.015 }) {
  const len = z0 - z1
  cylZ(r, len, M.black, 0, y, (z0 + z1) / 2, parent, 12)
  coneZ(r, r * 1.45, 0.05, M.black, 0, y, z1 - 0.02, parent, 12)
  cylZ(r * 1.3, 0.05, M.black, 0, y, z0 + 0.02, parent, 12)
  cylZ(r * 1.2, 0.002, M.glass, 0, y, z1 - 0.046, parent, 12)
  box(0.012, y - 0.03, 0.014, M.steel, 0, (y + 0.03) / 2, z0 - 0.03, parent)
  box(0.012, y - 0.03, 0.014, M.steel, 0, (y + 0.03) / 2, z1 + 0.04, parent)
}

// ------------------------------------------------------------------ rifle builders
// Shared layout for long arms: grip/wrist around z +0.07, receiver around z 0, muzzle at negative z.

function rifleSpec (gun, extra) {
  return {
    kind: 'rifle',
    hip: V(0.15, -0.2, -0.5),
    rh: [0.005, -0.075, 0.075],
    lh: [-0.01, -0.02, -0.28],
    lhRotZ: 0.5,
    kick: { z: 0.035, rot: 0.05 },
    reloadRoll: 0.55,
    magDir: [0, -1, 0],
    parts: {},
    gun,
    ...extra,
    ads: V(-(extra.sightX || 0), -extra.sightY, -0.5)
  }
}

// original StG 44 viewmodel geometry
function stg44 () {
  const gun = new THREE.Group()
  // receiver + top cover
  box(0.048, 0.06, 0.4, M.steel, 0, 0, -0.04, gun)
  cylZ(0.024, 0.36, M.steelLight, 0, 0.028, -0.05, gun, 8)
  box(0.05, 0.02, 0.1, M.steel, 0, -0.03, 0.02, gun) // trigger housing
  // barrel, gas tube, muzzle nut
  cylZ(0.011, 0.36, M.steel, 0, 0.004, -0.42, gun)
  cylZ(0.014, 0.25, M.steelLight, 0, 0.03, -0.33, gun, 8)
  cylZ(0.016, 0.03, M.steel, 0, 0.004, -0.6, gun)
  // front sight hood and post, rear tangent sight
  box(0.008, 0.032, 0.012, M.steel, 0, 0.055, -0.56, gun)
  box(0.03, 0.03, 0.006, M.steelLight, 0, 0.06, -0.565, gun)
  box(0.032, 0.022, 0.05, M.steel, 0, 0.055, -0.06, gun)
  box(0.012, 0.012, 0.006, M.steel, -0.011, 0.07, -0.04, gun)
  box(0.012, 0.012, 0.006, M.steel, 0.011, 0.07, -0.04, gun)
  // bakelite handguard
  box(0.056, 0.045, 0.16, M.bakelite, 0, 0.022, -0.27, gun)
  // curved magazine
  const mag = new THREE.Group()
  mag.position.set(0, -0.03, -0.16)
  gun.add(mag)
  for (let i = 0; i < 5; i++) {
    const seg = box(0.026, 0.05, 0.044, M.steel, 0, -0.025 - i * 0.045, -i * i * 0.0045 - i * 0.006, mag)
    seg.rotation.x = -i * 0.09
  }
  // pistol grip + trigger guard
  const g = box(0.032, 0.1, 0.045, M.wood, 0, -0.075, 0.07, gun)
  g.rotation.x = 0.28
  box(0.008, 0.008, 0.06, M.steel, 0, -0.06, 0.02, gun)
  box(0.006, 0.02, 0.006, M.steel, 0, -0.045, 0.02, gun)
  // stock (tapered)
  buttStock(gun, M.wood, { z: 0.28, y: -0.05, len: 0.24, r0: 0.03, r1: 0.042 })
  box(0.04, 0.11, 0.012, M.steel, 0, -0.075, 0.4, gun).rotation.x = 0.14
  return rifleSpec(gun, {
    mag,
    muzzle: V(0, 0.004, -0.63),
    sightY: 0.068,
    ejectPort: V(0.03, 0.02, -0.06)
  })
}

// full-length wooden rifle stock (Kar98k, Springfield, Garand, Lee-Enfield, Carbine)
function riflestock (gun, wood, { fore = -0.55, back = -0.06, wristZ = 0.1, buttZ = 0.3, buttLen = 0.26, guard = [-0.5, -0.22], drop = 1 }) {
  box(0.05, 0.048, back - fore, wood, 0, -0.02, (fore + back) / 2, gun) // forend
  if (guard) box(0.034, 0.02, guard[1] - guard[0], wood, 0, 0.014, (guard[0] + guard[1]) / 2, gun) // upper handguard
  box(0.05, 0.055, 0.16, wood, 0, -0.03, 0.0, gun) // around the action
  const wrist = box(0.038, 0.05, 0.13, wood, 0, -0.06 * drop, wristZ, gun)
  wrist.rotation.x = 0.3 * drop
  buttStock(gun, wood, { z: buttZ, y: -0.07 * drop, len: buttLen, r0: 0.03, r1: 0.05, sy: 1.7, rotX: 0.06 * drop })
  box(0.04, 0.13, 0.012, M.steel, 0, -0.085 * drop, buttZ + buttLen / 2 + 0.006, gun)
}

function boltRifle ({ wood = M.woodRed, barrelEnd = -0.74, sightY = 0.05, scoped = false, mag = 5, lee = false, bands = [-0.47, -0.55] }) {
  const gun = new THREE.Group()
  riflestock(gun, wood, { fore: lee ? -0.5 : -0.58, guard: lee ? [-0.5, -0.1] : [-0.52, -0.22] })
  cylZ(0.019, 0.2, M.steel, 0, 0.012, -0.02, gun) // receiver
  cylZ(0.011, 0.66, M.steel, 0, 0.014, barrelEnd + 0.33, gun) // barrel
  for (const z of bands) cylZ(0.031, 0.012, M.steel, 0, -0.004, z, gun, 8)
  if (lee) {
    cylZ(0.016, 0.06, M.steel, 0, 0.014, barrelEnd + 0.03, gun) // exposed muzzle with bayonet lugs
    box(0.04, 0.03, 0.03, M.steel, 0, 0.032, -0.03, gun) // receiver bridge with aperture rear sight
    box(0.03, 0.02, 0.06, M.steel, 0, -0.06, -0.12, gun) // protruding 10-round magazine
  }
  triggerGuard(gun, 0.03, -0.058)
  if (!scoped) ironSights(gun, { y: sightY, front: barrelEnd + 0.03, rear: lee ? -0.03 : -0.22, ears: true })
  const bolt = turnBolt(gun, { y: 0.012, z: 0.06, bent: scoped || !lee })
  if (scoped) scope(gun, { y: 0.074, z0: 0.07, z1: -0.2 })
  const clip = clipRounds(gun, { y: 0.06, z: -0.03, rounds: mag })
  return rifleSpec(gun, {
    mag: clip,
    magHidden: true,
    parts: { bolt },
    muzzle: V(0, 0.014, barrelEnd - 0.01),
    sightY: scoped ? 0.074 : sightY,
    ejectPort: V(0.02, 0.03, 0.0),
    rh: [0.005, -0.085, 0.1],
    lh: [-0.01, -0.04, -0.34],
    kick: { z: 0.06, rot: 0.12 }
  })
}

const kar98k = () => boltRifle({ wood: M.woodRed })
const kar98kScoped = () => boltRifle({ wood: M.woodRed, scoped: true, mag: 1 })
const m1903 = () => boltRifle({ wood: M.woodLight, barrelEnd: -0.72, bands: [-0.44, -0.58] })
const m1903a4 = () => boltRifle({ wood: M.woodLight, barrelEnd: -0.72, bands: [-0.44, -0.58], scoped: true, mag: 1 })
const leeEnfield = () => boltRifle({ wood: M.woodRed, barrelEnd: -0.7, lee: true, bands: [-0.32, -0.46] })

function garand () {
  const gun = new THREE.Group()
  riflestock(gun, M.woodLight, { fore: -0.5, guard: [-0.46, -0.08] })
  box(0.044, 0.04, 0.2, M.parker, 0, 0.012, -0.02, gun) // receiver
  cylZ(0.011, 0.62, M.parker, 0, 0.014, -0.42, gun) // barrel
  cylZ(0.009, 0.42, M.parker, 0, -0.008, -0.34, gun, 6) // operating rod
  box(0.028, 0.03, 0.05, M.parker, 0, 0.002, -0.68, gun) // gas cylinder
  const op = box(0.03, 0.01, 0.012, M.parker, 0.026, 0.012, 0.02, gun) // op-rod handle
  ironSights(gun, { y: 0.056, front: -0.68, rear: 0.06, ears: true, material: M.parker })
  box(0.008, 0.02, 0.012, M.parker, -0.02, 0.045, 0.06, gun) // aperture sight knobs
  box(0.008, 0.02, 0.012, M.parker, 0.02, 0.045, 0.06, gun)
  triggerGuard(gun, 0.04, -0.058)
  // en-bloc clip with eight rounds, seated in the receiver
  const clip = clipRounds(gun, { y: 0.02, z: -0.02, rounds: 8 })
  clip.scale.set(1, 0.9, 0.9)
  return rifleSpec(gun, {
    mag: clip,
    parts: { bolt: op },
    muzzle: V(0, 0.014, -0.73),
    sightY: 0.056,
    ejectPort: V(0.02, 0.03, -0.02),
    rh: [0.005, -0.085, 0.1],
    lh: [-0.01, -0.04, -0.3],
    kick: { z: 0.045, rot: 0.08 }
  })
}

function carbine () {
  const gun = new THREE.Group()
  riflestock(gun, M.woodLight, { fore: -0.36, guard: [-0.34, -0.08], buttZ: 0.27, buttLen: 0.22 })
  box(0.04, 0.036, 0.17, M.parker, 0, 0.012, -0.02, gun)
  cylZ(0.009, 0.46, M.parker, 0, 0.014, -0.33, gun)
  cylZ(0.03, 0.014, M.parker, 0, -0.004, -0.34, gun, 8) // barrel band
  box(0.022, 0.009, 0.012, M.parker, 0.024, 0.01, 0.0, gun) // op handle
  ironSights(gun, { y: 0.046, front: -0.54, rear: 0.03, ears: true, material: M.parker })
  triggerGuard(gun, 0.04, -0.058)
  const mag = boxMag(gun, { y: -0.045, z: -0.06, segs: 2, w: 0.022, d: 0.034, seg: 0.04, material: M.parker })
  return rifleSpec(gun, {
    mag,
    muzzle: V(0, 0.014, -0.57),
    sightY: 0.046,
    ejectPort: V(0.02, 0.03, -0.02),
    lh: [-0.01, -0.035, -0.24],
    hip: V(0.14, -0.19, -0.48)
  })
}

function g43 () {
  const gun = new THREE.Group()
  riflestock(gun, M.woodRed, { fore: -0.5, guard: [-0.42, -0.14] })
  cylZ(0.019, 0.2, M.steel, 0, 0.012, -0.03, gun)
  cylZ(0.011, 0.62, M.steel, 0, 0.014, -0.42, gun)
  cylZ(0.008, 0.3, M.steelLight, 0, 0.036, -0.28, gun, 6) // gas piston tube over the barrel
  box(0.012, 0.012, 0.02, M.steel, -0.024, 0.012, 0.02, gun) // charging handle (left)
  for (const z of [-0.36, -0.5]) cylZ(0.031, 0.012, M.steel, 0, -0.004, z, gun, 8)
  ironSights(gun, { y: 0.054, front: -0.7, rear: -0.18, ears: true })
  triggerGuard(gun, 0.03, -0.058)
  const mag = boxMag(gun, { y: -0.045, z: -0.06, segs: 2, w: 0.026, d: 0.05, seg: 0.04 })
  return rifleSpec(gun, {
    mag,
    muzzle: V(0, 0.014, -0.73),
    sightY: 0.054,
    ejectPort: V(0.02, 0.03, -0.03),
    rh: [0.005, -0.085, 0.1],
    lh: [-0.01, -0.04, -0.3],
    kick: { z: 0.045, rot: 0.08 }
  })
}

// ------------------------------------------------------------------ submachine guns

function mp40 () {
  const gun = new THREE.Group()
  cylZ(0.021, 0.34, M.black, 0, 0.012, -0.08, gun) // receiver tube
  box(0.04, 0.05, 0.16, M.bakelite, 0, -0.018, 0.0, gun) // lower frame
  cylZ(0.01, 0.2, M.black, 0, 0.012, -0.34, gun) // barrel
  box(0.014, 0.022, 0.03, M.black, 0, -0.008, -0.39, gun) // resting bar
  box(0.014, 0.014, 0.02, M.black, -0.026, 0.02, -0.02, gun) // cocking handle (left)
  ironSights(gun, { y: 0.052, front: -0.42, rear: -0.05, ears: true, material: M.black })
  const mw = box(0.03, 0.05, 0.05, M.black, 0, -0.035, -0.13, gun) // magazine well
  mw.rotation.x = 0.0
  const mag = boxMag(gun, { y: -0.06, z: -0.13, segs: 5, w: 0.022, d: 0.036, seg: 0.044, material: M.black })
  grip(gun, M.bakelite, { z: 0.06, y: -0.078 })
  triggerGuard(gun, 0.02)
  // folding wire stock, extended
  for (const s of [-1, 1]) cylZ(0.004, 0.27, M.black, s * 0.016, -0.03, 0.22, gun, 5)
  box(0.04, 0.09, 0.01, M.black, 0, -0.055, 0.36, gun)
  return rifleSpec(gun, {
    mag,
    muzzle: V(0, 0.012, -0.45),
    sightY: 0.052,
    ejectPort: V(0.022, 0.02, -0.06),
    lh: [-0.01, -0.05, -0.15],
    lhRotZ: 0.2,
    hip: V(0.14, -0.19, -0.46),
    kick: { z: 0.03, rot: 0.035 }
  })
}

function thompson () {
  const gun = new THREE.Group()
  box(0.05, 0.06, 0.3, M.parker, 0, 0.004, -0.08, gun) // receiver
  cylZ(0.013, 0.3, M.parker, 0, 0.012, -0.38, gun) // barrel
  box(0.012, 0.014, 0.022, M.parker, 0.03, 0.02, -0.05, gun) // cocking knob (right)
  box(0.046, 0.04, 0.16, M.woodLight, 0, -0.03, -0.3, gun) // horizontal forend
  ironSights(gun, { y: 0.054, front: -0.52, rear: 0.02, ears: true, material: M.parker })
  box(0.003, 0.024, 0.03, M.parker, -0.016, 0.054, 0.02, gun) // rear sight guards
  box(0.003, 0.024, 0.03, M.parker, 0.016, 0.054, 0.02, gun)
  const mag = boxMag(gun, { y: -0.03, z: -0.15, segs: 4, w: 0.024, d: 0.034, seg: 0.045, material: M.parker })
  grip(gun, M.woodLight, { z: 0.06, y: -0.07 })
  triggerGuard(gun, 0.02, -0.04)
  buttStock(gun, M.woodLight, { z: 0.22, y: -0.035, len: 0.28, r0: 0.03, r1: 0.05, sy: 1.6, rotX: 0.12 })
  box(0.04, 0.12, 0.012, M.parker, 0, -0.06, 0.36, gun).rotation.x = 0.12
  return rifleSpec(gun, {
    mag,
    muzzle: V(0, 0.012, -0.54),
    sightY: 0.054,
    ejectPort: V(0.03, 0.03, -0.08),
    lh: [-0.01, -0.06, -0.3],
    lhRotZ: 0.2,
    kick: { z: 0.035, rot: 0.045 }
  })
}

function m3 () {
  const gun = new THREE.Group()
  cylZ(0.032, 0.24, M.parker, 0, 0, -0.08, gun, 12) // fat stamped receiver
  coneZ(0.032, 0.014, 0.04, M.parker, 0, 0, -0.22, gun, 12)
  cylZ(0.011, 0.12, M.parker, 0, 0, -0.29, gun)
  box(0.02, 0.012, 0.06, M.steelLight, 0.03, 0.014, -0.06, gun) // ejection port cover
  box(0.014, 0.03, 0.008, M.parker, 0, 0.045, -0.2, gun) // front sight
  box(0.014, 0.02, 0.01, M.parker, 0, 0.042, 0.03, gun) // rear peep
  const mw = box(0.03, 0.05, 0.045, M.parker, 0, -0.045, -0.12, gun)
  mw.rotation.x = 0
  const mag = boxMag(gun, { y: -0.07, z: -0.12, segs: 4, w: 0.022, d: 0.034, seg: 0.045, material: M.parker })
  grip(gun, M.parker, { z: 0.06, y: -0.07, rake: 0.32 })
  triggerGuard(gun, 0.02, -0.04)
  // collapsible wire stock
  for (const s of [-1, 1]) cylZ(0.004, 0.28, M.steelLight, s * 0.018, -0.03, 0.2, gun, 5)
  box(0.04, 0.08, 0.01, M.steelLight, 0, -0.05, 0.34, gun)
  return rifleSpec(gun, {
    mag,
    muzzle: V(0, 0, -0.36),
    sightY: 0.058,
    ejectPort: V(0.032, 0.02, -0.06),
    lh: [-0.01, -0.07, -0.12],
    lhRotZ: 0.2,
    hip: V(0.14, -0.19, -0.46),
    kick: { z: 0.025, rot: 0.025 }
  })
}

function sten () {
  const gun = new THREE.Group()
  cylZ(0.02, 0.3, M.black, 0, 0, -0.04, gun) // receiver tube
  jacket(gun, { r: 0.022, y: 0, z0: -0.19, z1: -0.33, material: M.black, holes: 5 })
  cylZ(0.009, 0.06, M.black, 0, 0, -0.36, gun)
  box(0.012, 0.012, 0.02, M.black, 0.024, 0.0, 0.02, gun) // cocking handle
  box(0.006, 0.026, 0.006, M.black, 0, 0.03, -0.32, gun) // front sight
  box(0.016, 0.02, 0.01, M.black, 0, 0.026, 0.07, gun) // rear peep
  box(0.03, 0.04, 0.05, M.black, 0, -0.032, 0.05, gun) // trigger housing
  triggerGuard(gun, 0.05, -0.055)
  // magazine sticks out to the LEFT
  box(0.04, 0.03, 0.04, M.black, -0.035, 0, -0.14, gun)
  const mag = boxMag(gun, { x: -0.05, y: 0, z: -0.14, segs: 4, w: 0.022, d: 0.036, seg: 0.042, material: M.black, rotZ: -Math.PI / 2 })
  // skeleton stock
  cylZ(0.006, 0.28, M.black, 0, -0.02, 0.24, gun, 6)
  box(0.012, 0.05, 0.012, M.black, 0, -0.04, 0.12, gun).rotation.x = 0.6
  box(0.03, 0.09, 0.012, M.black, 0, -0.05, 0.38, gun)
  return rifleSpec(gun, {
    mag,
    magDir: [-1, 0, 0],
    muzzle: V(0, 0, -0.39),
    sightY: 0.04,
    ejectPort: V(0.022, 0.012, -0.08),
    rh: [0.005, -0.075, 0.09],
    lh: [-0.035, -0.03, -0.14],
    lhRotZ: 1.0,
    hip: V(0.14, -0.18, -0.46),
    kick: { z: 0.03, rot: 0.04 }
  })
}

// ------------------------------------------------------------------ automatic rifles and machine guns

function fg42 () {
  const gun = new THREE.Group()
  box(0.044, 0.05, 0.3, M.steel, 0, 0.006, -0.06, gun) // receiver
  cylZ(0.011, 0.34, M.steel, 0, 0.012, -0.38, gun)
  coneZ(0.017, 0.015, 0.06, M.steel, 0, 0.012, -0.56, gun) // muzzle brake
  box(0.05, 0.04, 0.14, M.woodRed, 0, -0.02, -0.25, gun) // handguard
  const bp = bipod(gun, { y: 0.0, z: -0.34, spread: 0.022, len: 0.2 })
  bp.rotation.x = -0.05
  box(0.008, 0.04, 0.008, M.steel, 0, 0.05, -0.5, gun) // tall folding front sight
  box(0.02, 0.03, 0.02, M.steel, 0, 0.044, 0.02, gun) // tall diopter rear
  // magazine on the LEFT side
  box(0.03, 0.03, 0.05, M.steel, -0.03, 0.006, -0.12, gun)
  const mag = boxMag(gun, { x: -0.042, y: 0.006, z: -0.12, segs: 3, w: 0.024, d: 0.05, seg: 0.04, rotZ: -Math.PI / 2 })
  grip(gun, M.woodRed, { z: 0.04, y: -0.075, rake: 0.5 })
  triggerGuard(gun, -0.01, -0.045)
  buttStock(gun, M.woodRed, { z: 0.22, y: -0.02, len: 0.22, r0: 0.026, r1: 0.045, sy: 1.6, rotX: 0.04 })
  box(0.036, 0.1, 0.012, M.steel, 0, -0.03, 0.335, gun)
  return rifleSpec(gun, {
    mag,
    magDir: [-1, 0, 0],
    parts: {},
    muzzle: V(0, 0.012, -0.6),
    sightY: 0.058,
    ejectPort: V(0.025, 0.02, -0.08),
    rh: [0.005, -0.075, 0.05],
    lh: [-0.01, -0.03, -0.27],
    kick: { z: 0.04, rot: 0.06 }
  })
}

function bar () {
  const gun = new THREE.Group()
  box(0.05, 0.07, 0.3, M.parker, 0, 0.0, -0.06, gun) // receiver
  cylZ(0.012, 0.56, M.parker, 0, 0.012, -0.48, gun)
  cylZ(0.009, 0.36, M.parker, 0, -0.016, -0.36, gun, 6) // gas cylinder
  coneZ(0.018, 0.016, 0.05, M.parker, 0, 0.012, -0.77, gun) // flash hider
  box(0.05, 0.04, 0.2, M.woodLight, 0, -0.02, -0.3, gun) // forend
  bipod(gun, { y: 0.012, z: -0.72, spread: 0.028, len: 0.32, folded: true })
  ironSights(gun, { y: 0.06, front: -0.74, rear: 0.03, ears: true, material: M.parker })
  const mag = boxMag(gun, { y: -0.035, z: -0.06, segs: 2, w: 0.032, d: 0.07, seg: 0.045, material: M.parker })
  grip(gun, M.woodLight, { z: 0.11, y: -0.07, rake: 0.35, h: 0.09 })
  triggerGuard(gun, 0.06, -0.04)
  buttStock(gun, M.woodLight, { z: 0.27, y: -0.04, len: 0.36, r0: 0.03, r1: 0.05, sy: 1.6, rotX: 0.12 })
  box(0.04, 0.13, 0.012, M.parker, 0, -0.07, 0.45, gun).rotation.x = 0.12
  return rifleSpec(gun, {
    mag,
    muzzle: V(0, 0.012, -0.8),
    sightY: 0.06,
    ejectPort: V(0.03, 0.03, -0.06),
    rh: [0.005, -0.07, 0.12],
    lh: [-0.01, -0.045, -0.32],
    hip: V(0.16, -0.21, -0.5),
    kick: { z: 0.045, rot: 0.06 }
  })
}

function bren () {
  const gun = new THREE.Group()
  box(0.05, 0.06, 0.32, M.parker, 0, 0.0, -0.04, gun) // receiver
  cylZ(0.014, 0.5, M.parker, 0, 0.012, -0.44, gun) // barrel
  coneZ(0.016, 0.026, 0.07, M.parker, 0, 0.012, -0.71, gun) // conical flash hider
  cylZ(0.01, 0.3, M.parker, 0, -0.018, -0.32, gun, 6) // gas cylinder
  box(0.012, 0.05, 0.012, M.parker, 0, 0.05, -0.32, gun) // carrying handle post
  box(0.01, 0.01, 0.12, M.woodDark, 0, 0.078, -0.32, gun)
  bipod(gun, { y: -0.018, z: -0.46, spread: 0.03, len: 0.28 })
  // sights offset to the left of the top-mounted magazine
  box(0.006, 0.026, 0.008, M.parker, -0.034, 0.07, -0.62, gun)
  box(0.012, 0.08, 0.012, M.parker, -0.034, 0.03, -0.62, gun)
  box(0.02, 0.03, 0.03, M.parker, -0.034, 0.06, 0.06, gun)
  // curved magazine on TOP, bending forward
  const mag = group(gun, 0, 0.03, -0.1)
  for (let i = 0; i < 4; i++) {
    const s = box(0.024, 0.045, 0.06, M.parker, 0, 0.022 + i * 0.04, -i * i * 0.006 - i * 0.008, mag)
    s.rotation.x = -i * 0.12
  }
  grip(gun, M.woodDark, { z: 0.08, y: -0.07, rake: 0.25 })
  triggerGuard(gun, 0.04, -0.04)
  buttStock(gun, M.parker, { z: 0.26, y: -0.01, len: 0.3, r0: 0.03, r1: 0.044, sy: 1.6, rotX: 0.04 })
  box(0.04, 0.11, 0.012, M.parker, 0, -0.02, 0.42, gun)
  return rifleSpec(gun, {
    mag,
    magDir: [0, 1, 0],
    muzzle: V(0, 0.012, -0.76),
    sightY: 0.078,
    sightX: -0.034,
    ejectPort: V(0, -0.035, -0.06),
    ejectDown: true,
    lh: [-0.01, -0.05, -0.2],
    hip: V(0.16, -0.22, -0.5),
    kick: { z: 0.035, rot: 0.04 },
    reloadRoll: -0.4
  })
}

function beltMG ({ us }) {
  const gun = new THREE.Group()
  const metal = us ? M.parker : M.steel
  box(0.056, 0.075, 0.3, metal, 0, 0.0, -0.02, gun) // receiver
  // hinged feed cover (pivots at its rear edge)
  const cover = group(gun, 0, 0.038, 0.1)
  box(0.05, 0.016, 0.18, M.steelLight, 0, 0.008, -0.09, cover)
  if (us) {
    jacket(gun, { r: 0.03, y: 0.01, z0: -0.17, z1: -0.6, material: metal, holes: 10 })
    coneZ(0.014, 0.03, 0.1, metal, 0, 0.01, -0.66, gun) // flash hider
    box(0.012, 0.03, 0.08, M.steelLight, 0, 0.05, -0.2, gun) // carry handle
    bipod(gun, { y: 0.0, z: -0.58, spread: 0.032, len: 0.3 })
    box(0.006, 0.026, 0.008, metal, 0, 0.06, -0.58, gun)
  } else {
    jacket(gun, { r: 0.028, y: 0.01, z0: -0.17, z1: -0.62, material: metal, holes: 12 })
    coneZ(0.026, 0.018, 0.06, metal, 0, 0.01, -0.66, gun) // muzzle booster
    box(0.012, 0.03, 0.06, M.steelLight, 0.034, 0.01, -0.3, gun) // barrel-change hatch handle
    bipod(gun, { y: 0.0, z: -0.62, spread: 0.03, len: 0.28 })
    box(0.006, 0.03, 0.008, metal, 0, 0.06, -0.62, gun)
  }
  box(0.02, 0.02, 0.03, metal, 0, 0.05, 0.08, gun) // rear sight
  // belt drum / ammunition box on the left, with a short belt into the feed
  const mag = group(gun, -0.06, -0.02, -0.04)
  if (us) {
    box(0.05, 0.11, 0.14, mat('#4b5032', { roughness: 0.7 }), 0, -0.04, 0, mag)
  } else {
    cylY(0.055, 0.05, M.black, -0.005, -0.03, 0, mag, 12).rotation.z = Math.PI / 2
  }
  for (let i = 0; i < 4; i++) cylY(0.005, 0.034, M.brass, 0.03 + i * 0.008, 0.02 + i * 0.004, 0, mag, 5).rotation.x = Math.PI / 2
  grip(gun, us ? M.woodDark : M.bakelite, { z: 0.08, y: -0.08, rake: 0.25 })
  triggerGuard(gun, 0.04, -0.045)
  buttStock(gun, us ? M.parker : M.bakelite, { z: 0.27, y: -0.025, len: 0.26, r0: 0.03, r1: 0.045, sy: 1.6, rotX: 0.06 })
  box(0.04, 0.11, 0.012, M.steel, 0, -0.04, 0.4, gun)
  return rifleSpec(gun, {
    mag,
    magDir: [-0.6, -1, 0],
    parts: { cover },
    muzzle: V(0, 0.01, -0.71),
    sightY: 0.072,
    ejectPort: V(0, -0.04, -0.02),
    ejectDown: true,
    lh: [-0.01, -0.06, -0.24],
    hip: V(0.16, -0.23, -0.5),
    kick: { z: 0.02, rot: 0.03 },
    reloadRoll: 0.3
  })
}

// ------------------------------------------------------------------ pistols

function pistolSpec (gun, extra) {
  return {
    kind: 'pistol',
    hip: V(0.12, -0.135, -0.42),
    kick: { z: 0.045, rot: 0.11 },
    reloadRoll: 0.35,
    magDir: [0, -1, 0],
    parts: {},
    gun,
    ...extra,
    ads: V(0, -extra.sightY, -0.5)
  }
}

// original M1911 viewmodel geometry
function m1911 () {
  const gun = new THREE.Group()
  box(0.027, 0.032, 0.2, M.steel, 0, 0, -0.06, gun) // slide
  box(0.025, 0.02, 0.17, M.steelLight, 0, -0.024, -0.05, gun) // frame
  cylZ(0.008, 0.02, M.steel, 0, 0.002, -0.165, gun)
  box(0.006, 0.01, 0.01, M.steel, 0, 0.021, -0.15, gun) // front sight
  box(0.018, 0.01, 0.01, M.steel, 0, 0.021, 0.03, gun) // rear sight
  const g = box(0.03, 0.11, 0.05, M.woodDark, 0, -0.08, 0.02, gun)
  g.rotation.x = 0.22
  box(0.006, 0.006, 0.05, M.steel, 0, -0.045, -0.04, gun)
  const mag = new THREE.Group()
  mag.position.set(0, -0.13, 0.03)
  box(0.022, 0.012, 0.035, M.steel, 0, 0, 0, mag)
  gun.add(mag)
  box(0.012, 0.012, 0.02, M.steel, 0, 0.012, 0.045, gun) // hammer
  return pistolSpec(gun, {
    mag,
    muzzle: V(0, 0.002, -0.18),
    sightY: 0.026,
    ejectPort: V(0.016, 0.018, -0.04)
  })
}

function p38 () {
  const gun = new THREE.Group()
  box(0.026, 0.026, 0.15, M.black, 0, 0, -0.04, gun) // slide (open top at the front)
  cylZ(0.008, 0.07, M.black, 0, 0.004, -0.15, gun) // exposed barrel
  box(0.024, 0.02, 0.17, M.black, 0, -0.022, -0.05, gun) // frame
  box(0.005, 0.01, 0.008, M.black, 0, 0.017, -0.17, gun)
  box(0.018, 0.01, 0.01, M.black, 0, 0.018, 0.025, gun)
  const g = box(0.03, 0.11, 0.05, M.bakelite, 0, -0.08, 0.02, gun)
  g.rotation.x = 0.2
  box(0.006, 0.006, 0.06, M.black, 0, -0.048, -0.045, gun)
  const mag = group(gun, 0, -0.13, 0.03)
  box(0.022, 0.012, 0.035, M.black, 0, 0, 0, mag)
  box(0.012, 0.014, 0.018, M.black, 0, 0.012, 0.045, gun) // hammer
  return pistolSpec(gun, { mag, muzzle: V(0, 0.004, -0.19), sightY: 0.023, ejectPort: V(0.016, 0.016, -0.03) })
}

function luger () {
  const gun = new THREE.Group()
  cylZ(0.0075, 0.12, M.black, 0, 0.004, -0.13, gun) // long thin barrel
  box(0.024, 0.026, 0.1, M.black, 0, 0, -0.03, gun) // receiver
  // toggle lock: two knuckles on top
  const toggle = group(gun, 0, 0.018, 0.0)
  box(0.018, 0.012, 0.035, M.steelLight, 0, 0, 0.0, toggle)
  cylZ(0.008, 0.024, M.steelLight, 0, 0.004, 0.022, toggle, 8).rotation.y = Math.PI / 2
  box(0.006, 0.01, 0.008, M.black, 0, 0.014, -0.18, gun) // front sight
  box(0.014, 0.008, 0.008, M.black, 0, 0.018, 0.035, gun)
  const g = box(0.03, 0.11, 0.048, M.woodDark, 0, -0.07, 0.04, gun)
  g.rotation.x = 0.45 // steeply raked grip
  box(0.006, 0.006, 0.05, M.black, 0, -0.035, -0.02, gun)
  const mag = group(g, 0, -0.058, 0) // wooden-based magazine in the heel of the grip
  box(0.024, 0.012, 0.044, M.woodDark, 0, 0, 0, mag)
  return pistolSpec(gun, { mag, parts: { bolt: toggle }, muzzle: V(0, 0.004, -0.2), sightY: 0.023, ejectPort: V(0.0, 0.03, -0.0) })
}

function webley () {
  const gun = new THREE.Group()
  // barrel + top strap tip down on a hinge at the front of the frame when reloading
  const top = group(gun, 0, -0.01, -0.03)
  box(0.02, 0.02, 0.18, M.black, 0, 0.018, -0.07, top) // barrel with rib
  box(0.006, 0.012, 0.008, M.black, 0, 0.032, -0.155, top)
  cylZ(0.022, 0.05, M.black, 0, -0.002, 0.02, top, 6) // cylinder
  box(0.026, 0.03, 0.08, M.black, 0, -0.02, 0.0, gun) // frame
  box(0.012, 0.012, 0.025, M.black, 0, 0.025, 0.045, gun) // hammer spur
  box(0.016, 0.008, 0.01, M.black, 0, 0.02, 0.035, gun)
  const g = box(0.03, 0.1, 0.045, M.woodDark, 0, -0.075, 0.05, gun)
  g.rotation.x = 0.35 // bird's-head grip
  box(0.006, 0.006, 0.04, M.black, 0, -0.04, -0.005, gun)
  // speed-loader with six rounds (only shown while reloading)
  const mag = group(gun, 0, -0.012, 0.09)
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2
    cylZ(0.0045, 0.03, M.brass, Math.cos(a) * 0.012, Math.sin(a) * 0.012, 0, mag, 6)
  }
  return pistolSpec(gun, {
    mag,
    magHidden: true,
    magDir: [0, -0.3, 1],
    parts: { breakTop: top },
    muzzle: V(0, 0.008, -0.2),
    sightY: 0.032,
    ejectPort: V(0, 0.01, 0.02),
    kick: { z: 0.05, rot: 0.14 }
  })
}

// ------------------------------------------------------------------ registry

const BUILDERS = {
  stg44,
  kar98k,
  kar98k_scoped: kar98kScoped,
  mp40,
  mg42: () => beltMG({ us: false }),
  fg42,
  g43,
  p38,
  luger,
  m1garand: garand,
  thompson,
  m3,
  bar,
  m1919a6: () => beltMG({ us: true }),
  m1903,
  m1903a4,
  m1carbine: carbine,
  sten,
  bren,
  lee_enfield: leeEnfield,
  m1911,
  webley
}

// Fresh procedural meshes every call (geometries are not shared, materials are); when weapons.glb has a model for
// this id its parts replace them (those share geometry, flagged userData.shared) and the procedural spec only
// supplies the gameplay metadata.
export function buildGun (id) {
  const b = BUILDERS[id] || BUILDERS.stg44
  const spec = b()
  spec.id = id
  applyWeaponModel(id, spec)
  spec.magRest = spec.mag.position.clone()
  return spec
}

// ------------------------------------------------------------------ first-person arms

function hand (x, y, z, rotX, material, parent) {
  const g = new THREE.Group()
  box(0.05, 0.035, 0.09, material, 0, 0, 0, g) // palm
  box(0.052, 0.025, 0.05, material, 0, -0.022, -0.035, g) // curled fingers
  box(0.02, 0.02, 0.05, material, 0.028, 0.008, -0.02, g) // thumb
  g.position.set(x, y, z)
  g.rotation.x = rotX
  parent.add(g)
  return g
}

// tapered cylinder between two points
function limb (a, b, r0, r1, material, parent) {
  const av = new THREE.Vector3(...a); const bv = new THREE.Vector3(...b)
  const len = av.distanceTo(bv)
  const g = new THREE.CylinderGeometry(r1, r0, len, 8)
  g.translate(0, len / 2, 0)
  const m = new THREE.Mesh(g, material)
  m.position.copy(av)
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), bv.clone().sub(av).normalize())
  parent?.add(m)
  return m
}

const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]]

// Long-arm grip; with the default hand positions this reproduces the original StG 44 arms exactly.
// Shoulders stay put, so moving a hand along the gun stretches the sleeve rather than the forearm.
function rifleArms (root, sleeveM, spec) {
  const arms = new THREE.Group()
  root.add(arms)
  const rh = spec.rh; const lh = spec.lh
  hand(rh[0], rh[1], rh[2], 0.3, M.skin, arms)
  limb(add(rh, [0.015, -0.015, 0.035]), add(rh, [0.135, -0.125, 0.345]), 0.028, 0.036, M.skin, arms)
  limb(add(rh, [0.065, -0.065, 0.175]), [0.2, -0.3, 0.6], 0.04, 0.05, sleeveM, arms)
  const l = hand(lh[0], lh[1], lh[2], 0.1, M.skin, arms)
  l.rotation.z = spec.lhRotZ
  limb(add(lh, [-0.015, -0.015, 0.02]), add(lh, [-0.15, -0.18, 0.3]), 0.027, 0.034, M.skin, arms)
  limb(add(lh, [-0.09, -0.11, 0.16]), [-0.24, -0.32, 0.3], 0.04, 0.05, sleeveM, arms)
  return arms
}

// original two-handed pistol grip
function pistolArms (root, sleeveM) {
  const arms = new THREE.Group()
  root.add(arms)
  const rh = hand(0.004, -0.075, 0.03, 0.22, M.skin, arms)
  rh.scale.setScalar(0.95)
  limb([0.01, -0.09, 0.06], [0.11, -0.2, 0.4], 0.027, 0.035, M.skin, arms)
  limb([0.06, -0.15, 0.24], [0.16, -0.3, 0.6], 0.04, 0.05, sleeveM, arms)
  const lh = hand(-0.025, -0.08, 0.02, 0.3, M.skin, arms)
  lh.rotation.z = -0.4
  limb([-0.03, -0.09, 0.05], [-0.15, -0.21, 0.38], 0.027, 0.035, M.skin, arms)
  limb([-0.1, -0.16, 0.22], [-0.2, -0.32, 0.58], 0.04, 0.05, sleeveM, arms)
  return arms
}

// gun + arms rooted for the first-person view
export function buildViewmodel (id, sleeveColor) {
  const spec = buildGun(id)
  const root = new THREE.Group()
  root.add(spec.gun)
  const sleeve = makeSleeve(sleeveColor)
  spec.arms = spec.kind === 'pistol' ? pistolArms(root, sleeve) : rifleArms(root, sleeve, spec)
  spec.root = root
  if (spec.magHidden) spec.mag.visible = false
  return spec
}

// ------------------------------------------------------------------ Stielhandgranate 24

// stick grenade standing on +Y: wooden handle below, charge head on top; origin near the balance point
export function buildGrenade () {
  const g = new THREE.Group()
  const m = modelClone('stielhandgranate')
  if (m) {
    m.rotation.x = Math.PI / 2 // modelled head-forward (-Z)
    g.add(m)
    return g
  }
  cylY(0.034, 0.1, M.feldgrau, 0, 0.12, 0, g, 10)
  cylY(0.036, 0.012, M.steelLight, 0, 0.068, 0, g, 10)
  cylY(0.014, 0.27, M.wood, 0, -0.07, 0, g, 8)
  cylY(0.016, 0.016, M.steelLight, 0, -0.21, 0, g, 8) // screw cap over the pull cord
  return g
}

// right hand holding a grenade by the handle, for the first-person throw
export function buildGrenadeViewmodel (sleeveColor) {
  const root = new THREE.Group()
  const nade = buildGrenade()
  nade.position.y = 0.06
  root.add(nade)
  const h = hand(0, -0.06, 0.022, -Math.PI / 2, M.skin, root)
  h.rotation.y = Math.PI
  limb([0.005, -0.1, 0.03], [0.06, -0.3, 0.12], 0.028, 0.036, M.skin, root)
  limb([0.04, -0.24, 0.09], [0.1, -0.52, 0.2], 0.04, 0.05, makeSleeve(sleeveColor), root)
  return { root, nade }
}

// ------------------------------------------------------------------ knives

// flat blade pointing down -Z, edge down, spine up
function blade (len, width, material, parent) {
  const s = new THREE.Shape()
  s.moveTo(0, width / 2)
  s.lineTo(len * 0.82, width / 2)
  s.lineTo(len, width * 0.15)
  s.quadraticCurveTo(len * 0.8, -width / 2, len * 0.55, -width / 2)
  s.lineTo(0, -width / 2)
  const g = new THREE.ExtrudeGeometry(s, { depth: 0.004, bevelEnabled: false })
  g.translate(0, 0, -0.002)
  g.rotateY(Math.PI / 2)
  const m = new THREE.Mesh(g, material)
  parent.add(m)
  return m
}

// M3 trench knife (allies) or S84/98 bayonet (axis), blade forward along -Z; origin at the middle of the grip
export function buildKnife (team) {
  const g = new THREE.Group()
  const m = modelClone(team === 'axis' ? 'knife_axis' : 'knife_allies')
  if (m) {
    g.add(m)
    return g
  }
  if (team === 'axis') {
    blade(0.25, 0.024, M.steelLight, g).position.z = -0.062
    box(0.016, 0.04, 0.012, M.steel, 0, 0.004, -0.058, g) // crossguard
    box(0.018, 0.03, 0.105, M.woodRed, 0, 0, 0, g)
    box(0.02, 0.034, 0.025, M.steel, 0, 0.002, 0.064, g) // pommel and bayonet lug
  } else {
    blade(0.17, 0.026, M.parker, g).position.z = -0.062
    box(0.012, 0.055, 0.01, M.parker, 0, -0.004, -0.058, g) // crossguard
    cylZ(0.013, 0.105, M.leather, 0, 0, 0, g, 8) // stacked leather washers
    cylZ(0.015, 0.02, M.parker, 0, 0, 0.064, g, 8)
  }
  return g
}

// right fist around the knife grip, for the first-person stab
export function buildKnifeViewmodel (team, sleeveColor) {
  const root = new THREE.Group()
  const knife = buildKnife(team)
  root.add(knife)
  const h = hand(0.004, -0.004, 0.004, 0, M.skin, root)
  h.rotation.z = Math.PI / 2
  limb([0.012, -0.012, 0.04], [0.09, -0.12, 0.34], 0.028, 0.036, M.skin, root)
  limb([0.055, -0.07, 0.2], [0.15, -0.3, 0.62], 0.04, 0.05, makeSleeve(sleeveColor), root)
  return { root, knife }
}

// ------------------------------------------------------------------ ammunition can

// what a fallen soldier leaves behind; standing on its base at the origin
export function buildAmmoCan (team) {
  const g = new THREE.Group()
  const paint = mat(team === 'axis' ? '#5b6164' : '#55592f', { metalness: 0.35, roughness: 0.6 })
  box(0.34, 0.17, 0.14, paint, 0, 0.085, 0, g)
  box(0.35, 0.03, 0.15, paint, 0, 0.18, 0, g) // lid
  box(0.022, 0.06, 0.155, M.steelLight, 0.13, 0.165, 0, g) // latch
  box(0.12, 0.012, 0.024, M.black, 0, 0.202, 0, g) // carry handle
  box(0.342, 0.022, 0.142, mat(team === 'axis' ? '#cfc9b4' : '#c9a834'), 0, 0.12, 0, g) // stencilled band
  return g
}

// Search and Destroy demolition charge: bundled TNT with a timer box and a lamp that blinks the fuse down
export function buildBomb () {
  const g = new THREE.Group()
  const tnt = mat('#9c4a2c', { roughness: 0.8 })
  for (let i = 0; i < 3; i++) cylZ(0.035, 0.3, tnt, (i - 1) * 0.072, 0.036, 0, g)
  for (let i = 0; i < 2; i++) cylZ(0.035, 0.3, tnt, (i - 0.5) * 0.072, 0.098, 0, g)
  for (const z of [-0.09, 0.09]) box(0.232, 0.142, 0.022, M.leather, 0, 0.066, z, g) // straps
  box(0.11, 0.06, 0.09, M.black, 0, 0.16, 0, g) // timer
  const lamp = sphere(0.016, new THREE.MeshStandardMaterial({ color: '#7a1a12', emissive: '#ff2a1a', emissiveIntensity: 0 }), 0.03, 0.198, 0, g)
  return { group: g, lamp }
}
