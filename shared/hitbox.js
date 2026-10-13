// Player hitboxes (head sphere + body/leg capsules) and analytic ray tests.
// Shared so client-side hit claims and server-side bot shots use identical geometry.
import { PLAYER } from './constants.js'

// sideways head shift [x, z] of a player at yaw leaning by lean (-1 left .. 1 right)
export function leanShift (yaw, lean) {
  const s = (lean || 0) * PLAYER.leanDist
  return [Math.cos(yaw) * s, -Math.sin(yaw) * s]
}

// share of the head's lean shift at height y above the feet: the torso tilts about the hips, the legs stay put
export function leanFactor (y, crouch) {
  const h = crouch ? PLAYER.crouchHeight : PLAYER.height
  const hip = 0.82 * h / PLAYER.height
  return Math.max(0, (y - hip) / (h - 0.17 - hip))
}

export function hitZones (x, y, z, crouch, shift = null) {
  const h = crouch ? PLAYER.crouchHeight : PLAYER.height
  const k = h / PLAYER.height
  const sx = shift ? shift[0] : 0; const sz = shift ? shift[1] : 0
  const f = leanFactor(h - 0.5, crouch)
  return [
    { zone: 'head', sphere: true, c: [x + sx, y + h - 0.17, z + sz], r: 0.2 },
    { zone: 'body', a: [x, y + 0.82 * k, z], b: [x + sx * f, y + h - 0.5, z + sz * f], r: 0.3 },
    { zone: 'legs', a: [x, y + 0.2, z], b: [x, y + 0.82 * k, z], r: 0.2 }
  ]
}

function dot (a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] }
function sub (a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]] }

export function raySphere (o, d, c, r) {
  const oc = sub(o, c)
  const b = dot(oc, d)
  const cc = dot(oc, oc) - r * r
  const h = b * b - cc
  if (h < 0) return -1
  return -b - Math.sqrt(h)
}

// capsule between pa and pb with radius r (Inigo Quilez); d must be normalized
export function rayCapsule (ro, rd, pa, pb, r) {
  const ba = sub(pb, pa)
  const oa = sub(ro, pa)
  const baba = dot(ba, ba)
  const bard = dot(ba, rd)
  const baoa = dot(ba, oa)
  const rdoa = dot(rd, oa)
  const oaoa = dot(oa, oa)
  const a = baba - bard * bard
  let b = baba * rdoa - baoa * bard
  let c = baba * oaoa - baoa * baoa - r * r * baba
  let h = b * b - a * c
  if (h >= 0) {
    const t = (-b - Math.sqrt(h)) / a
    const y = baoa + t * bard
    if (y > 0 && y < baba) return t
    const oc = y <= 0 ? oa : sub(ro, pb)
    b = dot(rd, oc)
    c = dot(oc, oc) - r * r
    h = b * b - c
    if (h > 0) return -b - Math.sqrt(h)
  }
  return -1
}

// knife from eye o along view d (normalized) to the player's body axis: { dist to the body surface, angle off d, at: axis point }
export function knifeReach (o, d, x, y, z, crouch) {
  const h = crouch ? PLAYER.crouchHeight : PLAYER.height
  const at = [x, Math.max(y + 0.3, Math.min(y + h - 0.15, o[1])), z]
  const v = sub(at, o)
  const len = Math.hypot(v[0], v[1], v[2])
  const angle = len > 1e-4 ? Math.acos(Math.max(-1, Math.min(1, dot(v, d) / len))) : 0
  return { dist: Math.max(0, len - PLAYER.radius), angle, at }
}

// returns { t, zone } of the closest hit within maxT, or null; shift: the player's leanShift
export function rayVsPlayer (o, d, maxT, x, y, z, crouch, shift = null) {
  // cheap reject against a bounding sphere around the player
  const center = [x, y + 0.9, z]
  const oc = sub(o, center)
  const b = dot(oc, d)
  if (b * b - (dot(oc, oc) - 1.5625) < 0) return null
  let best = null
  for (const hz of hitZones(x, y, z, crouch, shift)) {
    const t = hz.sphere ? raySphere(o, d, hz.c, hz.r) : rayCapsule(o, d, hz.a, hz.b, hz.r)
    if (t > 0 && t < maxT && (!best || t < best.t)) best = { t, zone: hz.zone }
  }
  return best
}
