// Grenade flight: gravity plus bounces off solid map geometry, stepped at a fixed rate. The server runs it to
// decide where the blast happens; clients run the same code from the same throw so the visual follows that path.
import { GRENADE } from './weapons.js'
import { rayMap } from './physics.js'

export const NADE_DT = 1 / 60

// dir: normalized view direction; the throw leaves a little above it
export function launchVelocity (dir) {
  const h = Math.hypot(dir[0], dir[2])
  if (h < 1e-4) return [0, Math.sign(dir[1]) * GRENADE.speed, 0]
  const pitch = Math.min(1.5, Math.atan2(dir[1], h) + GRENADE.loft)
  const c = Math.cos(pitch) * GRENADE.speed
  return [(dir[0] / h) * c, Math.sin(pitch) * GRENADE.speed, (dir[2] / h) * c]
}

export function createGrenade (origin, dir) {
  return { pos: origin.slice(), vel: launchVelocity(dir), rest: false }
}

// advances g = { pos, vel, rest } by one NADE_DT; returns the impact speed when it hits something this step
export function stepGrenade (RAPIER, world, g) {
  if (g.rest) return 0
  const v = g.vel
  v[1] -= GRENADE.gravity * NADE_DT
  const speed = Math.hypot(v[0], v[1], v[2])
  if (speed < 1e-6) return 0
  const d = [v[0] / speed, v[1] / speed, v[2] / speed]
  const hit = rayMap(RAPIER, world, g.pos, d, speed * NADE_DT + GRENADE.radius)
  const n = hit?.normal
  const vn = n ? v[0] * n[0] + v[1] * n[1] + v[2] * n[2] : 0
  if (!hit || vn >= 0) {
    g.pos[0] += v[0] * NADE_DT; g.pos[1] += v[1] * NADE_DT; g.pos[2] += v[2] * NADE_DT
    if (g.pos[1] < -20) g.rest = true
    return 0
  }
  const t = Math.max(0, hit.dist - GRENADE.radius)
  g.pos[0] += d[0] * t; g.pos[1] += d[1] * t; g.pos[2] += d[2] * t
  // keep the sliding part (with friction), reflect what went into the surface
  const out = -vn * GRENADE.bounce
  for (let i = 0; i < 3; i++) v[i] = (v[i] - n[i] * vn) * GRENADE.friction + n[i] * out
  if (n[1] > 0.7 && Math.hypot(v[0], v[1], v[2]) < 1.2) {
    v[0] = v[1] = v[2] = 0
    g.rest = true
  }
  return -vn
}
