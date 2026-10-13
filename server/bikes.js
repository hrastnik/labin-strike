// Motorcycles: one per side, parked at each base all match long. A soldier gets on their own side's bike and rides it
// on their client (the shared BikeBody); the server checks the moves, wears the bike down, and when it is destroyed
// leaves the wreck burning for a minute before a new one stands at the base.
import { PLAYER, TEAMS } from '../shared/constants.js'
import { damageFor } from '../shared/weapons.js'
import { BIKE, BikeBody, bikeSide, rayVsBike, bikeDistance, bikePoint, toughnessFor } from '../shared/bikes.js'
import { TANK, underHull, wrapAngle } from '../shared/tanks.js'
import { rayMap, CHAR_GROUPS, BIKE_QUERY } from '../shared/physics.js'
import { CAT } from './cats.js'

const TEAM_IDS = ['allies', 'axis']
const r2 = (v) => Math.round(v * 100) / 100
const r3 = (v) => Math.round(v * 1000) / 1000
const yawRot = (y) => ({ x: 0, y: Math.sin(y / 2), z: 0, w: Math.cos(y / 2) })

export class Bikes {
  // after the tanks: a bike keeps off the tank's parking spot
  constructor (game) {
    this.g = game
    this.parking = { allies: this.findParking('allies'), axis: this.findParking('axis') }
    this.list = TEAM_IDS.map((team) => ({
      id: bikeSide(team).id,
      team,
      pos: [0, 0, 0],
      yaw: 0,
      lean: 0,
      hp: BIKE.maxHealth,
      driver: 0,
      destroyed: false,
      respawnAt: 0,
      posAt: 0,
      lastStateAt: 0,
      body: new BikeBody(game.RAPIER, game.world)
    }))
    for (const b of this.list) this.park(b)
  }

  get (id) { return this.list.find((b) => b.id === id) ?? null }

  // level open ground near the side's spawns, clear of them and of the tank, with a run-up towards the middle
  findParking (team) {
    const g = this.g
    const R = g.RAPIER
    const spawns = g.map.spawns[team]
    const cx = spawns.reduce((s, p) => s + p[0], 0) / spawns.length
    const cz = spawns.reduce((s, p) => s + p[2], 0) / spawns.length
    const b = g.map.bounds
    const middle = Math.atan2(-((b.min[0] + b.max[0]) / 2 - cx), -((b.min[2] + b.max[2]) / 2 - cz))
    const tank = g.tanks.parking[team].pos
    const box = new R.Cuboid(BIKE.half[0] + 0.3, 0.4, BIKE.half[2] + 0.3)
    const open = (c, y, m) => !g.world.intersectionWithShape(
      { x: c[0] - Math.sin(y) * m, y: c[1] + 0.25 + 0.4, z: c[2] - Math.cos(y) * m }, yawRot(y), box, undefined, BIKE_QUERY)
    const headings = [0, 1, -1, 2, -2, 3, -3, 4, -4].map((k) => wrapAngle(middle + k * Math.PI / 8))
    const nav = g.nav
    const cells = nav.walkList
      .filter((i) => nav.clear[i] >= 3)
      .map((i) => nav.center(i))
      .filter((c) => Math.hypot(c[0] - cx, c[2] - cz) < 40 && spawns.every((s) => Math.hypot(c[0] - s[0], c[2] - s[2]) > 3.5) &&
        Math.hypot(c[0] - tank[0], c[2] - tank[2]) > TANK.half[1] + BIKE.half[2] + 2)
      .sort((a, b2) => Math.hypot(a[0] - cx, a[2] - cz) - Math.hypot(b2[0] - cx, b2[2] - cz))
    for (const c of cells) {
      const yaw = headings.find((y) => [0, 2, 4, 6].every((m) => open(c, y, m)))
      if (yaw == null) continue
      const level = [-1, 1].every((end) => {
        const at = bikePoint({ pos: c, yaw }, 0, 0, end * BIKE.half[2] * 0.7)
        const hit = rayMap(R, g.world, [at[0], c[1] + 1, at[2]], [0, -1, 0], 2)
        return hit && Math.abs(1 - hit.dist) < 0.15
      })
      if (level) return { pos: [c[0], c[1] + 0.02, c[2]], yaw }
    }
    return { pos: spawns[0].slice(), yaw: middle }
  }

  park (b) {
    const home = this.parking[b.team]
    b.pos = home.pos.slice()
    b.yaw = home.yaw
    b.lean = 0
    b.posAt = this.g.now()
    b.body.setPose(b.pos[0], b.pos[1], b.pos[2], b.yaw)
    b.body.stop()
  }

  // a new match or a new S&D round: both bikes back home, whole and empty
  reset () {
    for (const b of this.list) this.renew(b)
  }

  renew (b) {
    this.eject(b)
    b.hp = BIKE.maxHealth
    b.destroyed = false
    b.respawnAt = 0
    this.park(b)
  }

  tick (now) {
    for (const b of this.list) {
      if (!b.destroyed || now < b.respawnAt) continue
      this.renew(b)
      this.g.emitAll('notice', { m: `A new ${bikeSide(b.team).name} stands at the ${TEAMS[b.team].name} base` }, true)
    }
  }

  // ------------------------------------------------------------------ getting on and off

  nearest (p) {
    const at = [p.pos[0], p.pos[1] + 1, p.pos[2]]
    let best = null; let bd = BIKE.reach + PLAYER.radius
    for (const b of this.list) {
      if (b.team !== p.team || b.destroyed || b.driver) continue
      const d = bikeDistance(at, b)
      if (d <= bd) { bd = d; best = b }
    }
    return best
  }

  enter (p) {
    const g = this.g
    if (!p.alive || p.tank || p.bike || g.match.state !== 'playing') return
    const b = this.nearest(p)
    if (!b) return
    const now = g.now()
    b.driver = p.id
    p.bike = b
    p.cookAt = 0
    p.useOn = false
    p.crouch = p.ads = p.reloading = false
    p.lean = 0
    p.pos = b.pos.slice()
    p.yaw = b.yaw
    p.pitch = 0
    p.posAt = now
    p.lastStateAt = b.lastStateAt = now
    if (!p.isBot) p.channel.emit('ride', { id: b.id, life: p.life, pos: b.pos, yaw: b.yaw }, { reliable: true })
  }

  exit (p) {
    const b = p.bike
    if (b) this.eject(b, this.exitSpot(b))
  }

  // pos: where the rider steps off (null: where they are). A dead rider is not told: the kill says it all
  eject (b, pos = null) {
    const p = this.g.players.get(b.driver)
    b.driver = 0
    b.body.stop()
    if (!p || p.bike !== b) return
    p.bike = null
    p.lean = 0
    if (pos) {
      p.pos = pos
      p.posAt = p.lastStateAt = this.g.now()
    }
    if (!p.isBot && p.alive) p.channel.emit('ride', { id: 0, life: p.life, pos: p.pos }, { reliable: true })
  }

  // either side of the bike, behind it, in front of it, or where it stands as a last resort
  exitSpot (b) {
    const g = this.g
    const R = g.RAPIER
    const hx = BIKE.half[0] + PLAYER.radius + 0.2; const hz = BIKE.half[2] + PLAYER.radius + 0.2
    const shape = new R.Capsule(PLAYER.height / 2 - PLAYER.radius, PLAYER.radius)
    for (const [lx, lz] of [[-hx, 0], [hx, 0], [0, hz], [0, -hz]]) {
      const at = bikePoint(b, lx, 0, lz)
      const ground = rayMap(R, g.world, [at[0], b.pos[1] + 1.5, at[2]], [0, -1, 0], 3)
      if (!ground) continue
      const y = b.pos[1] + 1.5 - ground.dist
      if (Math.abs(y - b.pos[1]) > 1) continue
      const free = !g.world.intersectionWithShape({ x: at[0], y: y + PLAYER.height / 2 + 0.06, z: at[2] }, { x: 0, y: 0, z: 0, w: 1 }, shape, undefined, CHAR_GROUPS)
      if (free) return [r2(at[0]), r2(y + 0.02), r2(at[2])]
    }
    return b.pos.slice()
  }

  // ------------------------------------------------------------------ riding

  // [life, x, y, z, yaw, lean, client time]
  state (p, s) {
    const b = p.bike
    if (!b || !p.alive || !Array.isArray(s) || s.length < 6 || s[0] !== p.life) return
    const [, x, y, z, yaw, lean] = s
    if (![x, y, z, yaw, lean].every(Number.isFinite)) return
    const g = this.g
    const now = g.now()
    const dt = Math.max(0.05, (now - b.lastStateAt) / 1000)
    const moved = Math.hypot(x - b.pos[0], z - b.pos[2])
    const bounds = g.map.bounds
    const out = x < bounds.min[0] - 3 || x > bounds.max[0] + 3 || z < bounds.min[2] - 3 || z > bounds.max[2] + 3 || y < -5 || y > 25
    b.lastStateAt = p.lastStateAt = now
    if (b.destroyed || moved > BIKE.speed * 1.5 * dt + 1.5 || out) {
      p.channel.emit('tp', { life: p.life, pos: b.pos, yaw: b.yaw }, { reliable: true })
      return
    }
    b.pos = [x, y, z]
    b.posAt = g.sampleTime(p, s[6], now)
    b.yaw = wrapAngle(yaw)
    b.lean = Math.max(-1, Math.min(1, lean))
    b.body.setPose(x, y, z, b.yaw)
    // the rider's hitbox leans with the bike
    p.pos = b.pos.slice()
    p.posAt = b.posAt
    p.yaw = b.yaw
    p.pitch = 0
    p.lean = b.lean
  }

  // ------------------------------------------------------------------ damage

  // a bullet claimed by a client: { bike: id } from o to the impact point e
  bullet (p, weapon, id, o, e, dist) {
    const b = this.get(id)
    if (!b || b.destroyed || b.team === p.team) return
    if (bikeDistance(e, b) > 2) return // the shooter saw it up to an interpolation delay ago, and it may be moving
    this.damage(b, p, damageFor(weapon, dist, 'body') * toughnessFor(weapon), weapon, o)
  }

  // nearest bike along a ray: { t, bike } or null
  ray (o, d, maxT) {
    let best = null
    for (const b of this.list) {
      const h = rayVsBike(o, d, best?.t ?? maxT, b)
      if (h != null) best = { t: h, bike: b }
    }
    return best
  }

  // a blast at c from team's side: every other side's bike in reach
  blast (c, attacker, team, damageAt, weapon) {
    for (const b of this.list) {
      if (b.destroyed || b.team === team) continue
      const dmg = damageAt(bikeDistance(c, b)) * toughnessFor(weapon)
      if (dmg > 0) this.damage(b, attacker, dmg, weapon, c)
    }
  }

  // an enemy tank rolling over a bike flattens it
  crush (t, driver) {
    for (const b of this.list) {
      if (b.destroyed || b.team === t.team || !underHull(t, b.pos[0], b.pos[1], b.pos[2], BIKE.half[0])) continue
      this.destroy(b, driver, TANK.crushId)
    }
  }

  damage (b, attacker, amount, weapon, from) {
    const g = this.g
    if (b.destroyed || !(amount > 0) || g.match.state !== 'playing') return
    if (g.sd && g.sd.state !== 'live') return
    b.hp -= amount
    const killed = b.hp <= 0
    if (!attacker.isBot && attacker.channel) attacker.channel.emit('hit', { v: b.driver, k: killed, bike: b.id }, { reliable: true })
    if (killed) this.destroy(b, attacker, weapon)
  }

  destroy (b, attacker, weapon) {
    const g = this.g
    b.hp = 0
    b.destroyed = true
    b.respawnAt = g.now() + BIKE.respawn * 1000
    console.log(`[game] the ${b.team} motorcycle was destroyed by ${attacker?.name}`)
    g.emitAll('bikeboom', { id: b.id, p: b.pos.map(r2) }, true)
    g.emitAll('notice', { m: `The ${TEAMS[b.team].name} ${bikeSide(b.team).name} was destroyed` }, true)
    g.cats.scare(b.pos, CAT.blastRadius)
    const rider = g.players.get(b.driver)
    if (rider?.alive) g.kill(rider, attacker, weapon, false)
    else this.eject(b)
  }

  // [id, x, y, z, yaw, lean, hp, driver, flags (1 wreck), age]
  snapshot (now) {
    return this.list.map((b) => [
      b.id, r2(b.pos[0]), r2(b.pos[1]), r2(b.pos[2]), r3(b.yaw), r2(b.lean), Math.max(0, Math.round(b.hp)), b.driver,
      b.destroyed ? 1 : 0, Math.max(0, Math.min(1000, Math.round(now - b.posAt)))
    ])
  }
}
