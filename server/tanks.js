// Tanks while they are switched on: one per side per match, parked near each side's spawns. A soldier climbs into
// their own side's tank and drives it on their client (the shared TankBody); the server checks the moves, fires the
// cannon, runs the armour and the tracks, and keeps a destroyed tank as a wreck until the next match.
import { PLAYER, TEAMS } from '../shared/constants.js'
import { damageFor } from '../shared/weapons.js'
import { TANK, TankBody, tankSide, rayVsTank, tankDistance, underHull, gunRay, tankPoint, shellDamage, armourFor, wrapAngle } from '../shared/tanks.js'
import { rayMap, CHAR_GROUPS, TANK_QUERY } from '../shared/physics.js'
import { rayVsPlayer } from '../shared/hitbox.js'
import { CAT } from './cats.js'

const TEAM_IDS = ['allies', 'axis']
const r2 = (v) => Math.round(v * 100) / 100
const r3 = (v) => Math.round(v * 1000) / 1000
const clampPitch = (v) => Math.max(TANK.pitchMin, Math.min(TANK.pitchMax, v))

export class Tanks {
  constructor (game) {
    this.g = game
    this.list = []
    this.lost = { allies: false, axis: false } // destroyed this match: no second tank until the next one
    this.parking = { allies: this.findParking('allies'), axis: this.findParking('axis') }
  }

  get (id) { return this.list.find((t) => t.id === id) ?? null }

  // open, level ground near the side's spawns (but clear of them) with room to turn on the spot, facing open road
  // as near the middle of the map as it can
  findParking (team) {
    const g = this.g
    const R = g.RAPIER
    const spawns = g.map.spawns[team]
    const cx = spawns.reduce((s, p) => s + p[0], 0) / spawns.length
    const cz = spawns.reduce((s, p) => s + p[2], 0) / spawns.length
    const b = g.map.bounds
    const middle = Math.atan2(-((b.min[0] + b.max[0]) / 2 - cx), -((b.min[2] + b.max[2]) / 2 - cz))
    const probe = new R.Cylinder(0.6, Math.hypot(TANK.half[0], TANK.half[1]) + 0.6)
    const hull = new R.Cuboid(TANK.half[0] + 0.2, 0.6, TANK.half[1])
    const rot = { x: 0, y: 0, z: 0, w: 1 }
    const yawRot = (y) => ({ x: 0, y: Math.sin(y / 2), z: 0, w: Math.cos(y / 2) })
    const runway = (c, y) => [3, 6, 9, 12].every((m) => !g.world.intersectionWithShape(
      { x: c[0] - Math.sin(y) * m, y: c[1] + 0.25 + 0.6, z: c[2] - Math.cos(y) * m }, yawRot(y), hull, undefined, TANK_QUERY))
    const headings = [0, 1, -1, 2, -2, 3, -3, 4, -4].map((k) => wrapAngle(middle + k * Math.PI / 8))
    const nav = g.nav
    const cells = nav.walkList
      .filter((i) => nav.clear[i] >= 6)
      .map((i) => ({ i, c: nav.center(i) }))
      .filter(({ c }) => Math.hypot(c[0] - cx, c[2] - cz) < 50 && spawns.every((s) => Math.hypot(c[0] - s[0], c[2] - s[2]) > 6))
      .sort((a, b2) => Math.hypot(a.c[0] - cx, a.c[2] - cz) - Math.hypot(b2.c[0] - cx, b2.c[2] - cz))
    for (const { c } of cells) {
      if (g.world.intersectionWithShape({ x: c[0], y: c[1] + 0.25 + 0.6, z: c[2] }, rot, probe, undefined, TANK_QUERY)) continue
      const yaw = headings.find((y) => runway(c, y))
      if (yaw == null) continue
      const t = { team, pos: c, yaw, turret: yaw, gun: 0 }
      const level = [[-1, -1], [1, -1], [-1, 1], [1, 1]].every(([sx, sz]) => {
        const at = tankPoint(t, sx * TANK.half[0], 0, sz * TANK.half[1])
        const hit = rayMap(R, g.world, [at[0], c[1] + 1, at[2]], [0, -1, 0], 2)
        return hit && Math.abs(1 - hit.dist) < 0.25
      })
      if (level) return { pos: [c[0], c[1] + 0.02, c[2]], yaw }
    }
    return { pos: spawns[0].slice(), yaw: middle }
  }

  newMatch () {
    this.lost = { allies: false, axis: false }
    this.spawnAll()
  }

  // switched on, a new match, or a toggle back on: every side that has not lost its tank this match gets one
  spawnAll () {
    this.clear()
    if (!this.g.tanksEnabled) return
    for (const team of TEAM_IDS) {
      if (this.lost[team]) continue
      const t = {
        id: tankSide(team).id,
        team,
        pos: [0, 0, 0],
        yaw: 0,
        turret: 0,
        gun: 0,
        hp: TANK.maxHealth,
        driver: 0,
        destroyed: false,
        firedAt: -1e9,
        posAt: 0,
        lastStateAt: 0,
        body: new TankBody(this.g.RAPIER, this.g.world, team)
      }
      this.park(t)
      this.list.push(t)
    }
  }

  park (t) {
    const home = this.parking[t.team]
    t.pos = home.pos.slice()
    t.yaw = t.turret = home.yaw
    t.gun = 0
    t.posAt = this.g.now()
    t.body.setPose(t.pos[0], t.pos[1], t.pos[2], t.yaw)
  }

  clear () {
    for (const t of this.list) { this.eject(t); t.body.dispose() }
    this.list = []
  }

  // Search and Destroy: every round starts with both tanks back home and empty (a wreck stays where it burnt out)
  roundReset () {
    for (const t of this.list) {
      this.eject(t)
      if (!t.destroyed) this.park(t)
    }
  }

  // ------------------------------------------------------------------ getting in and out

  nearest (p) {
    const at = [p.pos[0], p.pos[1] + 1, p.pos[2]]
    let best = null; let bd = TANK.reach + PLAYER.radius
    for (const t of this.list) {
      if (t.team !== p.team || t.destroyed || t.driver) continue
      const d = tankDistance(at, t)
      if (d <= bd) { bd = d; best = t }
    }
    return best
  }

  enter (p) {
    const g = this.g
    if (!p.alive || p.tank || g.match.state !== 'playing') return
    const t = this.nearest(p)
    if (!t) return
    const now = g.now()
    t.driver = p.id
    p.tank = t
    p.cookAt = 0
    p.useOn = false
    p.crouch = p.ads = p.reloading = false
    p.pos = t.pos.slice()
    p.posAt = now
    p.lastStateAt = t.lastStateAt = now
    if (!p.isBot) {
      p.channel.emit('drive', {
        id: t.id, life: p.life, pos: t.pos, yaw: t.yaw, turret: t.turret, gun: t.gun,
        ready: Math.max(0, Math.round(t.firedAt + TANK.reload * 1000 - now))
      }, { reliable: true })
    }
  }

  exit (p) {
    const t = p.tank
    if (t) this.eject(t, this.exitSpot(t))
  }

  // pos: where the driver steps out (null: where they are). A dead driver is not told: the kill says it all
  eject (t, pos = null) {
    const p = this.g.players.get(t.driver)
    t.driver = 0
    if (!p || p.tank !== t) return
    p.tank = null
    if (pos) {
      p.pos = pos
      p.posAt = p.lastStateAt = this.g.now()
    }
    if (!p.isBot && p.alive) p.channel.emit('drive', { id: 0, life: p.life, pos: p.pos }, { reliable: true })
  }

  // beside the hull, behind it, in front of it, or on top as a last resort
  exitSpot (t) {
    const g = this.g
    const R = g.RAPIER
    const hx = TANK.half[0] + PLAYER.radius + 0.25; const hz = TANK.half[1] + PLAYER.radius + 0.25
    const shape = new R.Capsule(PLAYER.height / 2 - PLAYER.radius, PLAYER.radius)
    for (const [lx, lz] of [[-hx, 0], [hx, 0], [0, hz], [-hx, hz * 0.6], [hx, hz * 0.6], [0, -hz]]) {
      const at = tankPoint(t, lx, 0, lz)
      const ground = rayMap(R, g.world, [at[0], t.pos[1] + 2.5, at[2]], [0, -1, 0], 5)
      if (!ground) continue
      const y = t.pos[1] + 2.5 - ground.dist
      if (Math.abs(y - t.pos[1]) > 1.5) continue
      const free = !g.world.intersectionWithShape({ x: at[0], y: y + PLAYER.height / 2 + 0.06, z: at[2] }, { x: 0, y: 0, z: 0, w: 1 }, shape, undefined, CHAR_GROUPS)
      if (free) return [r2(at[0]), r2(y + 0.02), r2(at[2])]
    }
    return [t.pos[0], r2(t.pos[1] + tankSide(t.team).hullH + 0.05), t.pos[2]]
  }

  // ------------------------------------------------------------------ driving

  // [life, x, y, z, hull yaw, turret yaw, gun pitch, client time]
  state (p, s) {
    const t = p.tank
    if (!t || !p.alive || !Array.isArray(s) || s.length < 7 || s[0] !== p.life) return
    const [, x, y, z, yaw, turret, gun] = s
    if (![x, y, z, yaw, turret, gun].every(Number.isFinite)) return
    const g = this.g
    const now = g.now()
    const dt = Math.max(0.05, (now - t.lastStateAt) / 1000)
    const moved = Math.hypot(x - t.pos[0], z - t.pos[2])
    const b = g.map.bounds
    const out = x < b.min[0] - 3 || x > b.max[0] + 3 || z < b.min[2] - 3 || z > b.max[2] + 3 || y < -5 || y > 25
    t.lastStateAt = p.lastStateAt = now
    if (t.destroyed || moved > TANK.speed * 1.5 * dt + 1.5 || out) {
      p.channel.emit('tp', { life: p.life, pos: t.pos, yaw: t.yaw }, { reliable: true })
      return
    }
    t.pos = [x, y, z]
    t.posAt = g.sampleTime(p, s[7], now)
    t.yaw = wrapAngle(yaw)
    t.turret = wrapAngle(turret)
    t.gun = clampPitch(gun)
    t.body.setPose(x, y, z, t.yaw)
    p.pos = t.pos.slice()
    p.posAt = t.posAt
    p.yaw = t.turret
    p.pitch = t.gun
    if (moved / dt > TANK.crushSpeed) this.crush(t, p)
  }

  crush (t, driver) {
    for (const q of this.g.players.values()) {
      if (!q.alive || q.tank || q.team === t.team) continue
      if (underHull(t, q.pos[0], q.pos[1], q.pos[2], 0.15)) this.g.applyDamage(q, driver, 1000, TANK.crushId, 'body', t.pos)
    }
  }

  // { t: turret yaw, g: gun pitch } as the driver saw them when firing
  fire (p, msg) {
    const g = this.g
    const t = p.tank
    if (!t || t.destroyed || !p.alive) return
    const now = g.now()
    if (now - t.firedAt < TANK.reload * 1000 * 0.9) return
    if (Number.isFinite(msg?.t)) t.turret = wrapAngle(msg.t)
    if (Number.isFinite(msg?.g)) t.gun = clampPitch(msg.g)
    t.firedAt = p.firedAt = now
    // from the gun's pivot, so a barrel poking through a wall bursts on it
    const { o, d } = gunRay(t)
    let maxT = TANK.range
    const mh = rayMap(g.RAPIER, g.world, o, d, maxT)
    if (mh) maxT = mh.dist
    let direct = null
    for (const u of this.list) {
      if (u === t) continue
      const h = rayVsTank(o, d, maxT, u)
      if (h != null) { maxT = h; direct = u }
    }
    for (const q of g.players.values()) {
      if (!q.alive || q.tank) continue
      const h = rayVsPlayer(o, d, maxT, q.pos[0], q.pos[1], q.pos[2], q.crouch)
      if (h) { maxT = h.t; direct = null }
    }
    const e = [o[0] + d[0] * maxT, o[1] + d[1] * maxT, o[2] + d[2] * maxT]
    g.emitAll('shell', { id: t.id, o: o.map(r2), e: e.map(r2) }, true)
    g.cats.scare(e, CAT.blastRadius)
    for (const q of g.players.values()) if (q.isBot && q.team !== p.team) q.bot.hear(p)
    // the blast's centre is pulled back off the surface, so its line-of-sight checks start in the open
    const back = Math.min(0.3, maxT)
    g.blast([e[0] - d[0] * back, e[1] - d[1] * back, e[2] - d[2] * back], p, p.team, shellDamage, TANK.gunId, e, direct)
  }

  // ------------------------------------------------------------------ armour

  // a bullet claimed by a client: { id: tank } from o to the impact point e
  bullet (p, weapon, id, o, e, dist) {
    const t = this.get(id)
    if (!t || t.destroyed || t.team === p.team) return
    if (tankDistance(e, t) > 2) return // the shooter saw it up to an interpolation delay ago, and it may be moving
    this.damage(t, p, damageFor(weapon, dist, 'body') * armourFor(weapon), weapon, o)
  }

  // nearest tank along a ray: { t, tank } or null
  ray (o, d, maxT) {
    let best = null
    for (const t of this.list) {
      const h = rayVsTank(o, d, best?.t ?? maxT, t)
      if (h != null) best = { t: h, tank: t }
    }
    return best
  }

  // a blast at c from team's side: every other side's tank in reach, the one hit directly at full strength
  blast (c, attacker, team, damageAt, weapon, direct = null) {
    for (const t of this.list) {
      if (t.destroyed || t.team === team) continue
      const dmg = damageAt(t === direct ? 0 : tankDistance(c, t)) * armourFor(weapon)
      if (dmg > 0) this.damage(t, attacker, dmg, weapon, c)
    }
  }

  damage (t, attacker, amount, weapon, from) {
    const g = this.g
    if (t.destroyed || !(amount > 0) || g.match.state !== 'playing') return
    if (g.sd && g.sd.state !== 'live') return
    t.hp -= amount
    const driver = g.players.get(t.driver)
    const killed = t.hp <= 0
    if (driver && !driver.isBot) {
      driver.channel.emit('tdmg', { a: attacker.id, n: Math.round(amount), hp: Math.max(0, Math.round(t.hp)), from: from.map(r2) }, { reliable: true })
    }
    if (!attacker.isBot && attacker.channel) attacker.channel.emit('hit', { v: driver?.id ?? 0, k: killed, tank: t.id }, { reliable: true })
    if (killed) this.destroy(t, attacker, weapon)
  }

  destroy (t, attacker, weapon) {
    const g = this.g
    t.hp = 0
    t.destroyed = true
    this.lost[t.team] = true
    console.log(`[game] the ${t.team} tank was destroyed by ${attacker?.name}`)
    g.emitAll('tankboom', { id: t.id, p: t.pos.map(r2), by: attacker?.id ?? 0 }, true)
    g.emitAll('notice', { m: `The ${TEAMS[t.team].name} ${tankSide(t.team).name} was destroyed` }, true)
    g.cats.scare(t.pos, CAT.blastRadius * 2)
    const driver = g.players.get(t.driver)
    if (driver?.alive) g.kill(driver, attacker, weapon, false)
    else this.eject(t)
  }

  // [id, x, y, z, yaw, turret, gun, hp, driver, flags (1 wreck, 2 just fired), age]
  snapshot (now) {
    return this.list.map((t) => [
      t.id, r2(t.pos[0]), r2(t.pos[1]), r2(t.pos[2]), r3(t.yaw), r3(t.turret), r3(t.gun), Math.max(0, Math.round(t.hp)), t.driver,
      (t.destroyed ? 1 : 0) | (now - t.firedAt < 400 ? 2 : 0), Math.max(0, Math.min(1000, Math.round(now - t.posAt)))
    ])
  }
}
