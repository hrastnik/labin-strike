// The cats of Rudarska ulica (where Counter-Strike has chickens). They wander the nav grid, stop to look around
// or stretch out on the warm ground, and bolt from soldiers who come close, from gunfire and from grenades.
// Nobody can hurt them. Soldiers who crouch can creep right up to one.
const TAU = Math.PI * 2
const r2 = (v) => Math.round(v * 100) / 100
const r3 = (v) => Math.round(v * 1000) / 1000
const wrap = (a) => { a = (a + Math.PI) % TAU; return (a < 0 ? a + TAU : a) - Math.PI }

export const CAT_STATE = { idle: 0, walk: 1, run: 2, lie: 3 }
// coat names match the cat_<coat> models in cats.glb (tools/blender/cats)
export const CAT_COATS = ['main', 'ginger', 'tuxedo']

export const CAT = {
  walkSpeed: 0.7,
  runSpeed: 5.2,
  turnRate: 5, // rad/s walking (running turns twice as fast)
  wanderRange: 14, // how far a stroll goes
  fleeDist: 14, // how far from the scare a cat runs
  personal: 2.4, // a standing soldier this close spooks a cat
  sneak: 0.9, // ... a crouching one only this close
  shotRadius: 3, // a bullet passing this close
  blastRadius: 14
}

export class Cats {
  constructor (game) {
    this.g = game
    this.list = CAT_COATS.map((coat, i) => this.create(i + 1, i))
  }

  create (id, coat) {
    const c = { id, coat, pos: [0, 0, 0], yaw: Math.random() * TAU, state: CAT_STATE.idle, path: null, pathIdx: 0, until: 0, calmAt: 0 }
    this.place(c)
    return c
  }

  place (c) {
    const nav = this.g.nav
    c.pos = nav.center(nav.randomCell())
    c.state = CAT_STATE.idle
    c.path = null
    c.until = this.g.now() + 500 + Math.random() * 3000
  }

  // something frightening happened at pos: cats within radius run from it
  scare (pos, radius) {
    for (const c of this.list) {
      if (Math.hypot(c.pos[0] - pos[0], c.pos[2] - pos[2]) < radius) this.flee(c, pos)
    }
  }

  // a bullet flew from o to e
  hearShot (o, e) {
    const dx = e[0] - o[0]; const dz = e[2] - o[2]
    const len2 = dx * dx + dz * dz || 1
    for (const c of this.list) {
      const t = Math.max(0, Math.min(1, ((c.pos[0] - o[0]) * dx + (c.pos[2] - o[2]) * dz) / len2))
      const at = [o[0] + dx * t, 0, o[2] + dz * t]
      if (Math.hypot(c.pos[0] - at[0], c.pos[2] - at[2]) < CAT.shotRadius) this.flee(c, at)
    }
  }

  flee (c, from) {
    const now = this.g.now()
    c.calmAt = now + 2500 + Math.random() * 1500
    // already running from something and still on its way: keep going
    if (c.state === CAT_STATE.run && c.path && c.pathIdx < c.path.length) return
    const nav = this.g.nav
    const away = Math.atan2(c.pos[0] - from[0], c.pos[2] - from[2])
    let best = null; let bestScore = -Infinity
    for (let k = 0; k < 8; k++) {
      const a = away + (Math.random() - 0.5) * 1.6
      const d = CAT.fleeDist * (0.6 + Math.random() * 0.5)
      const i = nav.nearestWalkable(c.pos[0] + Math.sin(a) * d, c.pos[2] + Math.cos(a) * d, 3)
      if (i < 0) continue
      const pt = nav.center(i)
      const score = Math.hypot(pt[0] - from[0], pt[2] - from[2]) + nav.clear[i]
      if (score > bestScore) { bestScore = score; best = pt }
    }
    if (!best || !this.go(c, best)) return
    c.state = CAT_STATE.run
  }

  go (c, dest) {
    const path = this.g.nav.findPath(c.pos, dest, 6000)
    if (!path) return false
    c.path = path
    c.pathIdx = 0
    return true
  }

  update (dt, now) {
    for (const c of this.list) {
      this.spook(c)
      if (c.state === CAT_STATE.walk || c.state === CAT_STATE.run) this.move(c, dt, now)
      else if (now >= c.until) this.decide(c, now)
    }
  }

  // soldiers walking up to a cat
  spook (c) {
    for (const p of this.g.players.values()) {
      if (!p.alive) continue
      const d = Math.hypot(p.pos[0] - c.pos[0], p.pos[2] - c.pos[2])
      if (d < (p.crouch ? CAT.sneak : CAT.personal) && Math.abs(p.pos[1] - c.pos[1]) < 2) { this.flee(c, p.pos); return }
    }
  }

  decide (c, now) {
    const roll = Math.random()
    const nav = this.g.nav
    if (roll < 0.55) {
      const i = nav.randomCell(Math.random, (pt) => Math.hypot(pt[0] - c.pos[0], pt[2] - c.pos[2]) < CAT.wanderRange)
      if (this.go(c, nav.center(i))) { c.state = CAT_STATE.walk; return }
    }
    if (roll > 0.8) {
      c.state = CAT_STATE.lie
      c.until = now + 6000 + Math.random() * 12000
    } else {
      c.state = CAT_STATE.idle
      c.until = now + 1500 + Math.random() * 4000
      c.yaw = wrap(c.yaw + (Math.random() - 0.5) * 2)
    }
  }

  move (c, dt, now) {
    const run = c.state === CAT_STATE.run
    const wp = c.path?.[c.pathIdx]
    if (!wp) { this.arrive(c, now); return }
    const dx = wp[0] - c.pos[0]; const dz = wp[2] - c.pos[2]
    const dist = Math.hypot(dx, dz)
    const step = (run ? CAT.runSpeed : CAT.walkSpeed) * dt
    if (dist <= step) {
      c.pos[0] = wp[0]; c.pos[2] = wp[2]
      c.pathIdx++
    } else {
      const want = Math.atan2(-dx, -dz) // yaw 0 faces -z, like the soldiers
      const turn = CAT.turnRate * (run ? 2 : 1) * dt
      const d = wrap(want - c.yaw)
      c.yaw = wrap(c.yaw + Math.max(-turn, Math.min(turn, d)))
      // slow down while turning hard so walking cats don't slide sideways
      const k = Math.max(0.2, Math.cos(Math.min(Math.PI / 2, Math.abs(d))))
      c.pos[0] += (dx / dist) * step * k
      c.pos[2] += (dz / dist) * step * k
    }
    const nav = this.g.nav
    const [cx, cz] = nav.cellOf(c.pos[0], c.pos[2])
    if (cx >= 0 && cz >= 0 && cx < nav.w && cz < nav.h) {
      const i = nav.idx(cx, cz)
      if (nav.walk[i]) c.pos[1] += (nav.height[i] - c.pos[1]) * Math.min(1, dt * 12)
    }
    if (c.pathIdx >= c.path.length) this.arrive(c, now)
  }

  arrive (c, now) {
    c.path = null
    // a fleeing cat that is still spooked sits tight and watches; a calm one carries on
    c.state = CAT_STATE.idle
    c.until = Math.max(now + 800 + Math.random() * 2500, c.calmAt)
  }

  // [id, coat, x, y, z, yaw, state]
  snapshot () {
    return this.list.map((c) => [c.id, c.coat, r2(c.pos[0]), r2(c.pos[1]), r2(c.pos[2]), r3(c.yaw), c.state])
  }
}
