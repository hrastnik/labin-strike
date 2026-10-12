// Authoritative Team Deathmatch simulation: players, bots, damage, scoring, match flow.
import fs from 'node:fs'
import path from 'node:path'
import RAPIER from '@dimforge/rapier3d-compat'
import { TICK_RATE, SNAPSHOT_RATE, MATCH, PLAYER, BOT_NAMES } from '../shared/constants.js'
import {
  WEAPONS, WEAPON_CODE, CLASS_IDS, CLASSES, GRENADE, KNIFE, AMMO_DROP, damageFor, blastDamage, canUse, sanitizeLoadout,
  isValidLoadout, startingAmmo, ammoPickup
} from '../shared/weapons.js'
import { parseGlbJson, extractMapData } from '../shared/mapdata.js'
import { buildMapWorld, rayMap, lineOfSight } from '../shared/physics.js'
import { NADE_DT, createGrenade, stepGrenade } from '../shared/grenade.js'
import { rayVsPlayer, knifeReach } from '../shared/hitbox.js'
import { NavGrid } from './navgrid.js'
import { Bot } from './bot.js'
import { Cats, CAT } from './cats.js'

const TEAM_IDS = ['allies', 'axis']
const r2 = (v) => Math.round(v * 100) / 100
const r3 = (v) => Math.round(v * 1000) / 1000
// how far a human's stab may be from what the server sees, for the target having moved while the stab was in flight
const KNIFE_SLACK = 1.2

export class Game {
  constructor (io, root) {
    this.io = io
    this.root = root
    this.players = new Map()
    this.grenades = []
    this.drops = []
    this.nextDropId = 1
    this.nextId = 1
    this.startedAt = Date.now()
    this.botNames = [...BOT_NAMES].sort(() => Math.random() - 0.5)
    this.botsEnabled = true
  }

  now () { return Date.now() - this.startedAt }

  async init () {
    await RAPIER.init()
    this.RAPIER = RAPIER
    const glbPath = path.join(this.root, 'client/public/assets/maps/parking_lot.glb')
    const buf = fs.readFileSync(glbPath)
    const gltf = parseGlbJson(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength))
    this.map = extractMapData(gltf)
    this.world = buildMapWorld(RAPIER, this.map)
    const t0 = Date.now()
    const seeds = [...this.map.spawns.allies, ...this.map.spawns.axis]
    this.nav = new NavGrid(RAPIER, this.world, this.map.bounds, seeds)
    console.log(`[game] map loaded: ${this.map.colliders.length} colliders, nav ${this.nav.w}x${this.nav.h} ` +
      `(${this.nav.walkableCount} walkable) baked in ${Date.now() - t0}ms`)
    this.cats = new Cats(this)

    this.match = { state: 'playing', scores: { allies: 0, axis: 0 }, endsAt: this.now() + MATCH.timeLimit * 1000, restartAt: 0, winner: null }
    this.io.onConnection((ch) => this.onConnection(ch))
    this.balanceBots()

    this.timers = [
      setInterval(() => this.tick(1 / TICK_RATE), 1000 / TICK_RATE),
      setInterval(() => this.broadcastSnapshot(), 1000 / SNAPSHOT_RATE),
      setInterval(() => this.broadcastRoster(), 2000),
      setInterval(() => this.pingAll(), 2000)
    ]
  }

  stop () { this.timers?.forEach(clearInterval) }

  stats () {
    const all = [...this.players.values()]
    return { humans: all.filter((p) => !p.isBot).length, bots: all.filter((p) => p.isBot).length, match: this.match?.state }
  }

  humans () { return [...this.players.values()].filter((p) => !p.isBot) }

  // ------------------------------------------------------------------ connections

  onConnection (channel) {
    channel.on('join', (data) => this.join(channel, data))
    channel.on('st', (data) => { const p = channel.player; if (p) this.handleState(p, data) })
    channel.on('fire', (data) => { const p = channel.player; if (p) this.handleFire(p, data) })
    channel.on('cook', (data) => { const p = channel.player; if (p) this.handleCook(p, data) })
    channel.on('nade', (data) => { const p = channel.player; if (p) this.handleNade(p, data) })
    channel.on('knife', (data) => { const p = channel.player; if (p) this.handleKnife(p, data) })
    channel.on('loadout', (data) => { const p = channel.player; if (p) this.handleLoadout(p, data) })
    channel.on('team', (data) => { const p = channel.player; if (p) this.handleTeam(p, data) })
    channel.on('bots', (data) => { const p = channel.player; if (p) this.handleBots(p, data) })
    channel.on('pong', (data) => { const p = channel.player; if (p && data && typeof data.t === 'number') p.ping = Math.max(0, this.now() - data.t) })
    channel.on('chat', (data) => {
      const p = channel.player
      if (!p || typeof data?.m !== 'string') return
      this.emitAll('chat', { id: p.id, m: data.m.slice(0, 120) }, true)
    })
    channel.onDisconnect(() => this.leave(channel))
  }

  join (channel, data) {
    if (channel.player) return
    const name = String(data?.name || 'Soldier').replace(/[^\p{L}\p{N} ._\-]/gu, '').trim().slice(0, 16) || 'Soldier'
    // the first human into an empty server gets a fresh round rather than a half-played bot match
    if (!this.humans().length) this.restartMatch()
    // a requested team is honoured unless it would stack the humans; otherwise auto-balance
    const team = TEAM_IDS.includes(data?.team) && this.teamAllowed(data.team) ? data.team : this.chooseTeam()
    const p = this.createPlayer({ name, team, isBot: false, channel })
    p.loadout = sanitizeLoadout(team, data?.loadout)
    channel.player = p
    console.log(`[game] ${name} joined ${team} (${p.id})`)
    this.balanceBots()
    // humans pick (or confirm) a loadout before their first spawn: see handleLoadout
    channel.emit('welcome', {
      id: p.id,
      team,
      loadout: p.loadout,
      roster: this.roster(),
      match: this.matchInfo(),
      drops: this.drops.map((d) => this.dropInfo(d)),
      tick: TICK_RATE,
      snap: SNAPSHOT_RATE
    }, { reliable: true })
    this.broadcastRoster()
    this.emitAll('notice', { m: `${name} joined the ${team === 'allies' ? 'Allies' : 'Axis'}` }, true)
  }

  leave (channel) {
    const p = channel.player
    if (!p) return
    console.log(`[game] ${p.name} left`)
    this.players.delete(p.id)
    channel.player = null
    this.balanceBots()
    this.broadcastRoster()
    this.emitAll('notice', { m: `${p.name} left the game` }, true)
  }

  chooseTeam () {
    const h = { allies: 0, axis: 0 }
    for (const p of this.players.values()) if (!p.isBot) h[p.team]++
    if (h.allies !== h.axis) return h.allies < h.axis ? 'allies' : 'axis'
    const s = this.match.scores
    if (s.allies !== s.axis) return s.allies < s.axis ? 'allies' : 'axis'
    return Math.random() < 0.5 ? 'allies' : 'axis'
  }

  // true if moving one more human onto `team` keeps the human head-count within one of the other team
  teamAllowed (team, except = null) {
    const h = { allies: 0, axis: 0 }
    for (const p of this.players.values()) if (!p.isBot && p !== except) h[p.team]++
    const other = team === 'allies' ? 'axis' : 'allies'
    return h[team] <= h[other]
  }

  createPlayer ({ name, team, isBot, channel }) {
    const p = {
      id: this.nextId++,
      name,
      team,
      isBot,
      channel,
      pos: [0, 0, 0],
      posAt: 0, // server ms the position belongs to (snapshots carry its age so clients interpolate on the right timeline)
      clockOff: null, // smoothed server - client clock offset (humans)
      yaw: 0,
      pitch: 0,
      crouch: false,
      ads: false,
      reloading: false,
      slot: 0, // 0 = primary, 1 = secondary (which loadout weapon is in hand)
      loadout: randomLoadout(team), // authoritative: what this life is armed with
      pendingLoadout: null, // applied at the next spawn
      ammo: {}, // weapon id -> rounds left this life (magazine + reserve)
      grenades: 0,
      nadeSeq: 0, // bots number their own throws; humans send theirs
      cookAt: 0, // server ms the cord of the grenade in hand was pulled, 0 when not holding a live one
      cookK: 0,
      deployed: isBot, // humans deploy from the loadout screen
      spawnedAt: 0,
      lastLoadoutReq: 0,
      lastTeamSwitch: -1e9,
      hp: PLAYER.maxHealth,
      alive: false,
      life: 0,
      respawnAt: 0,
      lastDamageAt: -1e9,
      protectUntil: 0,
      kills: 0,
      deaths: 0,
      ping: 0,
      lastFire: {},
      lastKnife: -1e9,
      lastStateAt: 0,
      firedAt: -1e9
    }
    this.players.set(p.id, p)
    if (isBot) p.bot = new Bot(this, p)
    return p
  }

  balanceBots () {
    const perTeam = Math.ceil(MATCH.targetPlayers / 2)
    for (const team of TEAM_IDS) {
      const members = [...this.players.values()].filter((p) => p.team === team)
      const humans = members.filter((p) => !p.isBot).length
      const bots = members.filter((p) => p.isBot)
      const want = this.botsEnabled ? Math.max(0, perTeam - humans) : 0
      for (let i = bots.length; i < want; i++) {
        const name = this.botNames.shift() || `Bot ${this.nextId}`
        const b = this.createPlayer({ name, team, isBot: true })
        this.spawn(b)
      }
      // remove surplus bots, dead ones first
      bots.sort((a, b) => Number(a.alive) - Number(b.alive))
      for (let i = 0; i < bots.length - want; i++) {
        const b = bots[i]
        b.bot.dispose()
        this.players.delete(b.id)
        this.botNames.push(b.name)
      }
    }
  }

  // ------------------------------------------------------------------ spawning

  chooseSpawn (team) {
    const pts = this.map.spawns[team]
    const enemies = [...this.players.values()].filter((p) => p.alive && p.team !== team)
    const everyone = [...this.players.values()].filter((p) => p.alive)
    let best = pts[0]; let bestScore = -Infinity
    for (const pt of pts) {
      let minEnemy = 60
      for (const e of enemies) minEnemy = Math.min(minEnemy, Math.hypot(e.pos[0] - pt[0], e.pos[2] - pt[2]))
      let crowd = 0
      for (const o of everyone) if (Math.hypot(o.pos[0] - pt[0], o.pos[2] - pt[2]) < 1.6) crowd++
      const score = minEnemy + Math.random() * 8 - crowd * 100
      if (score > bestScore) { bestScore = score; best = pt }
    }
    return best
  }

  spawn (p) {
    const pt = this.chooseSpawn(p.team)
    p.pos = [pt[0], pt[1] + 0.05, pt[2]]
    p.posAt = this.now()
    // face towards the middle of the arena
    const cx = (this.map.bounds.min[0] + this.map.bounds.max[0]) / 2
    const cz = (this.map.bounds.min[2] + this.map.bounds.max[2]) / 2
    p.yaw = Math.atan2(-(cx - pt[0]), -(cz - pt[2]))
    p.pitch = 0
    p.hp = PLAYER.maxHealth
    p.alive = true
    p.crouch = false
    p.life++
    p.respawnAt = 0
    p.spawnedAt = this.now()
    p.protectUntil = this.now() + MATCH.spawnProtection * 1000
    p.lastStateAt = this.now()
    if (p.isBot) p.loadout = randomLoadout(p.team)
    else if (p.pendingLoadout) { p.loadout = p.pendingLoadout; p.pendingLoadout = null }
    // last line of defence: whatever path got us here, never spawn with another faction's weapons
    if (!isValidLoadout(p.team, p.loadout)) p.loadout = sanitizeLoadout(p.team, p.loadout)
    this.equip(p)
    if (p.isBot) p.bot.onSpawn()
    else p.channel.emit('spawn', { life: p.life, pos: p.pos, yaw: p.yaw, loadout: p.loadout }, { reliable: true })
  }

  equip (p) {
    const l = p.loadout
    p.slot = 0
    p.ammo = {}
    for (const slot of ['primary', 'secondary']) {
      const a = startingAmmo(l.cls, l[slot], slot)
      p.ammo[l[slot]] = a.mag + a.reserve
    }
    p.grenades = GRENADE.count
    p.cookAt = 0
  }

  // ------------------------------------------------------------------ loadouts and teams

  // { cls, primary, secondary, deploy? }: validated against the player's (server-side) team
  handleLoadout (p, data) {
    const now = this.now()
    if (now - p.lastLoadoutReq < 200) return
    p.lastLoadoutReq = now
    const req = { cls: data?.cls, primary: data?.primary, secondary: data?.secondary }
    if (!isValidLoadout(p.team, req)) {
      p.channel.emit('loadout', { loadout: p.pendingLoadout || p.loadout, applied: 'rejected' }, { reliable: true })
      return
    }
    const l = { cls: req.cls, primary: req.primary, secondary: req.secondary }
    let applied
    if (!p.deployed) {
      p.loadout = l
      applied = 'spawn'
      if (data.deploy) {
        p.deployed = true
        if (!p.respawnAt) p.respawnAt = now
      }
    } else if (p.alive && now - p.spawnedAt < MATCH.loadoutGrace * 1000 && p.firedAt < p.spawnedAt && p.lastDamageAt < p.spawnedAt) {
      // changed class right after spawning, before getting involved: swap kit on the spot
      p.loadout = l
      p.pendingLoadout = null
      this.equip(p)
      applied = 'now'
    } else {
      p.pendingLoadout = l
      applied = 'next'
    }
    p.channel.emit('loadout', { loadout: l, applied, life: p.life }, { reliable: true })
  }

  handleTeam (p, data) {
    const now = this.now()
    const team = data?.team
    const deny = (m) => p.channel.emit('team', { team: p.team, loadout: p.pendingLoadout || p.loadout, denied: m }, { reliable: true })
    if (!TEAM_IDS.includes(team) || team === p.team) return deny('Already on that team')
    if (now - p.lastTeamSwitch < MATCH.teamSwitchCooldown * 1000) return deny('Wait a moment before switching again')
    if (!this.teamAllowed(team, p)) return deny('Teams would be unbalanced')
    p.lastTeamSwitch = now
    // leaving the field is not a death: no score change, back to the loadout screen
    p.alive = false
    p.cookAt = 0
    p.team = team
    p.loadout = sanitizeLoadout(team, p.pendingLoadout || p.loadout)
    p.pendingLoadout = null
    p.ammo = {}
    p.deployed = false
    p.respawnAt = now + MATCH.respawnDelay * 1000
    console.log(`[game] ${p.name} switched to ${team}`)
    this.balanceBots()
    p.channel.emit('team', { team, loadout: p.loadout }, { reliable: true })
    this.broadcastRoster()
    this.emitAll('notice', { m: `${p.name} switched to the ${team === 'allies' ? 'Allies' : 'Axis'}` }, true)
  }

  // any player can switch the bots for the whole server
  handleBots (p, data) {
    const now = this.now()
    if (typeof data?.on !== 'boolean' || data.on === this.botsEnabled) return
    if (now - (p.lastBotToggle ?? -Infinity) < MATCH.botToggleCooldown * 1000) return
    p.lastBotToggle = now
    this.botsEnabled = data.on
    console.log(`[game] ${p.name} turned bots ${data.on ? 'on' : 'off'}`)
    this.balanceBots()
    this.broadcastRoster()
    this.emitAll('notice', { m: `${p.name} turned bots ${data.on ? 'on' : 'off'}` }, true)
  }

  // ------------------------------------------------------------------ client messages

  handleState (p, s) {
    if (!Array.isArray(s) || s.length < 8 || !p.alive || s[0] !== p.life) return
    const [, x, y, z, yaw, pitch, flags, weapon] = s
    if (![x, y, z, yaw, pitch].every(Number.isFinite)) return
    const now = this.now()
    const dt = Math.max(0.05, (now - p.lastStateAt) / 1000)
    const moved = Math.hypot(x - p.pos[0], z - p.pos[2])
    const b = this.map.bounds
    const outOfBounds = x < b.min[0] - 3 || x > b.max[0] + 3 || z < b.min[2] - 3 || z > b.max[2] + 3 || y < -5 || y > 25
    if (moved > PLAYER.walkSpeed * PLAYER.sprintMul * 1.5 * dt + 1.5 || outOfBounds) {
      // implausible movement: pull the client back to the last accepted position
      p.channel.emit('tp', { life: p.life, pos: p.pos }, { reliable: true })
      p.lastStateAt = now
      return
    }
    p.pos = [x, y, z]
    p.posAt = now
    // place the sample at the time the client took it (client clock + min-filtered offset), so packet jitter
    // doesn't turn into speed jitter for everyone watching this player
    const ct = s[8]
    if (Number.isFinite(ct)) {
      const off = now - ct
      if (p.clockOff == null || off < p.clockOff || off - p.clockOff > 1000) p.clockOff = off
      else p.clockOff += (off - p.clockOff) * 0.01
      p.posAt = Math.min(now, Math.max(now - 250, ct + p.clockOff))
    }
    p.yaw = yaw
    p.pitch = Math.max(-1.55, Math.min(1.55, pitch))
    p.crouch = !!(flags & 2)
    p.ads = !!(flags & 4)
    p.reloading = !!(flags & 8)
    p.slot = weapon === 1 ? 1 : 0
    p.lastStateAt = now
  }

  handleFire (p, msg) {
    if (!p.alive || !msg) return
    // only the weapons the server issued for this life, of the player's own faction, with rounds left
    const id = msg.w
    if (!canUse(p.team, id) || (id !== p.loadout.primary && id !== p.loadout.secondary)) return
    if (!(p.ammo[id] > 0)) return
    const w = WEAPONS[id]
    const now = this.now()
    const minInterval = (60000 / w.rpm) * 0.7
    if (now - (p.lastFire[id] ?? -1e9) < minInterval) return
    p.lastFire[id] = now
    p.ammo[id]--
    p.firedAt = now
    const o = msg.o; const e = msg.e
    if (!validVec(o) || !validVec(e)) return
    this.emitOthers(p, 'shot', { id: p.id, w: msg.w, o: o.map(r2), e: e.map(r2) })
    this.cats.hearShot(o, e)
    for (const q of this.players.values()) if (q.isBot && q.team !== p.team) q.bot.hear(p)

    const hit = msg.hit
    if (!hit || this.match.state !== 'playing') return
    const target = this.players.get(hit.id)
    if (!target || !target.alive || target.team === p.team) return
    // validation: shooter origin near server position, target near claimed hit point, map not in the way
    const eyeY = p.pos[1] + (p.crouch ? PLAYER.crouchEye : PLAYER.eye)
    if (Math.hypot(o[0] - p.pos[0], o[1] - eyeY, o[2] - p.pos[2]) > 3) return
    const dist = Math.hypot(e[0] - o[0], e[1] - o[1], e[2] - o[2])
    if (dist > w.range) return
    const tc = [target.pos[0], target.pos[1] + 1.0, target.pos[2]]
    if (Math.hypot(e[0] - tc[0], e[1] - tc[1], e[2] - tc[2]) > 3.2) return
    const d = [(e[0] - o[0]) / dist, (e[1] - o[1]) / dist, (e[2] - o[2]) / dist]
    const block = rayMap(this.RAPIER, this.world, o, d, dist)
    if (block && block.dist < dist - 0.4) return
    const zone = ['head', 'body', 'legs'].includes(hit.zone) ? hit.zone : 'body'
    this.applyDamage(target, p, damageFor(id, dist, zone), id, zone)
  }

  // { k: the client's throw number }: the fuse is timed here, so a client cannot claim a longer or shorter cook
  handleCook (p, msg) {
    if (!p.alive || !(p.grenades > 0) || p.cookAt) return
    p.cookAt = this.now()
    p.cookK = nadeKey(msg?.k)
  }

  // { o: eye position, d: view direction, k: the client's throw number (pairs its own visual with the blast) }
  handleNade (p, msg) {
    if (!p.alive || !(p.grenades > 0) || !msg) return
    const o = msg.o; const d = msg.d
    if (!validVec(o) || !validVec(d)) return
    const eyeY = p.pos[1] + (p.crouch ? PLAYER.crouchEye : PLAYER.eye)
    if (Math.hypot(o[0] - p.pos[0], o[1] - eyeY, o[2] - p.pos[2]) > 3) return
    const len = Math.hypot(d[0], d[1], d[2])
    if (len < 0.5 || len > 1.5) return
    this.throwGrenade(p, o, d.map((v) => v / len), nadeKey(msg.k))
  }

  // { o: eye position, d: view direction, hit: id of the enemy the client saw within reach, if any }
  handleKnife (p, msg) {
    if (!p.alive || !msg) return
    if (this.now() - p.lastKnife < (KNIFE.windup + KNIFE.recover) * 1000 * 0.7) return
    const o = msg.o; const d = msg.d
    if (!validVec(o) || !validVec(d)) return
    const eyeY = p.pos[1] + (p.crouch ? PLAYER.crouchEye : PLAYER.eye)
    if (Math.hypot(o[0] - p.pos[0], o[1] - eyeY, o[2] - p.pos[2]) > 3) return
    const len = Math.hypot(d[0], d[1], d[2])
    if (len < 0.5 || len > 1.5) return
    this.knife(p, o, d.map((v) => v / len), this.players.get(msg.hit), KNIFE_SLACK)
  }

  // ------------------------------------------------------------------ combat

  knife (p, o, d, target, slack = 0) {
    p.lastKnife = this.now()
    this.emitOthers(p, 'stab', { id: p.id })
    if (!target || !target.alive || target.team === p.team || this.match.state !== 'playing') return
    const r = knifeReach(o, d, target.pos[0], target.pos[1], target.pos[2], target.crouch)
    if (r.dist > KNIFE.range + slack || r.angle > KNIFE.cone + slack * 0.5) return
    if (!lineOfSight(this.RAPIER, this.world, o, r.at)) return
    this.applyDamage(target, p, KNIFE.damage, KNIFE.id, 'body')
  }

  // d: null lets a cooked grenade fall from the hand; the thrower has no local copy of that one, so all are told
  throwGrenade (p, o, d, k = p.nadeSeq++) {
    const now = this.now()
    const explodeAt = p.cookAt ? Math.max(now, p.cookAt + GRENADE.fuse * 1000) : now + GRENADE.fuse * 1000
    p.cookAt = 0
    p.grenades--
    p.firedAt = now
    o = o.map(r3); d = d?.map(r3) ?? null // the exact values the clients simulate from
    this.grenades.push({ ...createGrenade(o, d), owner: p.id, team: p.team, k, acc: 0, explodeAt })
    const msg = { id: p.id, k, o, d, f: Math.round(explodeAt - now) }
    if (d) this.emitOthers(p, 'nade', msg, true)
    else this.emitAll('nade', msg, true)
  }

  dropCooked (p) {
    const hand = [p.pos[0], p.pos[1] + (p.crouch ? PLAYER.crouchEye : PLAYER.eye) - 0.4, p.pos[2]]
    this.throwGrenade(p, hand, null, p.cookK)
  }

  updateGrenades (dt, now) {
    for (const p of this.players.values()) {
      if (p.alive && p.cookAt && now - p.cookAt >= GRENADE.fuse * 1000) this.dropCooked(p)
    }
    for (const g of this.grenades) {
      g.acc += dt
      while (g.acc >= NADE_DT) { g.acc -= NADE_DT; stepGrenade(this.RAPIER, this.world, g) }
    }
    const due = this.grenades.filter((g) => now >= g.explodeAt)
    if (!due.length) return
    this.grenades = this.grenades.filter((g) => now < g.explodeAt)
    for (const g of due) this.explode(g)
  }

  explode (g) {
    this.emitAll('boom', { id: g.owner, k: g.k, p: g.pos.map(r2) }, true)
    this.cats.scare(g.pos, CAT.blastRadius)
    const thrower = this.players.get(g.owner)
    if (!thrower || this.match.state !== 'playing') return
    const c = [g.pos[0], g.pos[1] + 0.2, g.pos[2]]
    for (const q of this.players.values()) {
      if (!q.alive || (q.team === g.team && q !== thrower)) continue
      // the blast reaches whichever of feet, chest and head is closest with nothing solid in between
      const h = q.crouch ? PLAYER.crouchHeight : PLAYER.height
      let dist = Infinity
      for (const y of [0.3, h * 0.6, h - 0.15]) {
        const pt = [q.pos[0], q.pos[1] + y, q.pos[2]]
        const dd = Math.hypot(pt[0] - c[0], pt[1] - c[1], pt[2] - c[2])
        if (dd < dist && dd < GRENADE.blastRadius && lineOfSight(this.RAPIER, this.world, c, pt)) dist = dd
      }
      const dmg = blastDamage(dist)
      if (dmg > 0) this.applyDamage(q, thrower, dmg, GRENADE.id, 'body', g.pos)
    }
  }

  // Fires a bot weapon along dir from origin; resolves hits server-side.
  fireBot (p, weapon, o, d) {
    const w = WEAPONS[weapon]
    const mapHit = rayMap(this.RAPIER, this.world, o, d, w.range)
    let maxT = mapHit ? mapHit.dist : w.range
    let victim = null; let zone = null
    for (const q of this.players.values()) {
      if (q === p || !q.alive || q.team === p.team) continue
      const h = rayVsPlayer(o, d, maxT, q.pos[0], q.pos[1], q.pos[2], q.crouch)
      if (h) { maxT = h.t; victim = q; zone = h.zone }
    }
    const e = [o[0] + d[0] * maxT, o[1] + d[1] * maxT, o[2] + d[2] * maxT]
    p.firedAt = this.now()
    this.emitAll('shot', { id: p.id, w: weapon, o: o.map(r2), e: e.map(r2), n: victim ? 0 : 1 })
    this.cats.hearShot(o, e)
    for (const q of this.players.values()) if (q.isBot && q.team !== p.team && q !== p) q.bot.hear(p)
    if (victim && this.match.state === 'playing') this.applyDamage(victim, p, damageFor(weapon, maxT, zone), weapon, zone)
  }

  // from: where the damage came from (the attacker, or the blast for grenades)
  applyDamage (victim, attacker, amount, weapon, zone, from = attacker.pos) {
    const now = this.now()
    if (!victim.alive || now < victim.protectUntil || amount <= 0) return
    victim.hp -= amount
    victim.lastDamageAt = now
    const killed = victim.hp <= 0
    if (!victim.isBot) {
      victim.channel.emit('dmg', { a: attacker.id, n: amount, hp: Math.max(0, Math.round(victim.hp)), from: from.map(r2) }, { reliable: true })
    } else {
      victim.bot.onDamaged(attacker)
    }
    if (!attacker.isBot && attacker !== victim) attacker.channel.emit('hit', { v: victim.id, hs: zone === 'head', k: killed }, { reliable: true })
    if (killed) this.kill(victim, attacker, weapon, zone === 'head')
  }

  kill (victim, attacker, weapon, headshot) {
    victim.alive = false
    victim.hp = 0
    victim.deaths++
    victim.respawnAt = this.now() + MATCH.respawnDelay * 1000
    if (attacker && attacker !== victim && attacker.team !== victim.team) {
      attacker.kills++
      this.match.scores[attacker.team]++
    }
    this.emitAll('kill', { k: attacker?.id, v: victim.id, w: weapon, hs: headshot }, true)
    this.dropAmmo(victim)
    if (victim.cookAt) this.dropCooked(victim)
    if (this.match.scores[attacker?.team] >= MATCH.scoreLimit) this.endMatch(attacker.team)
    else this.broadcastRoster()
  }

  // ------------------------------------------------------------------ ammo drops

  dropAmmo (victim) {
    const [x, y, z] = victim.pos
    const ground = rayMap(this.RAPIER, this.world, [x, y + 0.5, z], [0, -1, 0], 30)
    const drop = { id: this.nextDropId++, pos: [x, ground ? y + 0.5 - ground.dist : y, z].map(r2), team: victim.team, expireAt: this.now() + AMMO_DROP.lifetime * 1000 }
    this.drops.push(drop)
    this.emitAll('drop', this.dropInfo(drop), true)
    if (this.drops.length > AMMO_DROP.max) this.removeDrop(this.drops[0])
  }

  dropInfo (d) { return { i: d.id, p: d.pos, t: d.team, ttl: Math.max(0, d.expireAt - this.now()) } }

  removeDrop (drop, by = 0) {
    this.drops = this.drops.filter((d) => d !== drop)
    this.emitAll('undrop', { i: drop.id, by }, true)
  }

  // the first soldier over a can who is short of ammunition takes it; anyone fully stocked leaves it lying
  updateDrops (now) {
    for (const drop of this.drops.slice()) {
      if (now >= drop.expireAt) { this.removeDrop(drop); continue }
      for (const q of this.players.values()) {
        if (!q.alive || Math.abs(q.pos[1] - drop.pos[1]) > 1.2 || Math.hypot(q.pos[0] - drop.pos[0], q.pos[2] - drop.pos[2]) > AMMO_DROP.radius) continue
        const gain = ammoPickup(q.loadout, q.ammo)
        if (!Object.keys(gain).length) continue
        for (const id in gain) q.ammo[id] += gain[id]
        if (!q.isBot) q.channel.emit('ammo', { life: q.life, a: gain }, { reliable: true })
        this.removeDrop(drop, q.id)
        break
      }
    }
  }

  // ------------------------------------------------------------------ match flow

  endMatch (winner) {
    if (this.match.state !== 'playing') return
    this.match.state = 'ended'
    this.match.winner = winner
    this.match.restartAt = this.now() + MATCH.intermission * 1000
    console.log(`[game] match ended, winner: ${winner} ${JSON.stringify(this.match.scores)}`)
    this.broadcastRoster()
  }

  restartMatch () {
    this.match = { state: 'playing', scores: { allies: 0, axis: 0 }, endsAt: this.now() + MATCH.timeLimit * 1000, restartAt: 0, winner: null }
    this.grenades = []
    for (const d of this.drops.slice()) this.removeDrop(d)
    for (const p of this.players.values()) {
      p.kills = 0
      p.deaths = 0
      if (p.deployed) this.spawn(p)
    }
    this.broadcastRoster()
    this.emitAll('notice', { m: 'New round: Team Deathmatch' }, true)
  }

  tick (dt) {
    const now = this.now()
    const m = this.match
    if (m.state === 'playing' && now >= m.endsAt) {
      const s = m.scores
      this.endMatch(s.allies === s.axis ? 'draw' : s.allies > s.axis ? 'allies' : 'axis')
    } else if (m.state === 'ended' && now >= m.restartAt) {
      this.restartMatch()
    }
    this.updateGrenades(dt, now)
    this.updateDrops(now)
    // with nobody connected the bots (and cats) idle instead of burning CPU
    const anyHumans = this.humans().length > 0
    if (anyHumans) this.cats.update(dt, now)
    for (const p of this.players.values()) {
      if (!p.alive) {
        if (p.respawnAt && now >= p.respawnAt && m.state === 'playing' && p.deployed) this.spawn(p)
        continue
      }
      if (p.hp < PLAYER.maxHealth && now - p.lastDamageAt > PLAYER.regenDelay * 1000) {
        p.hp = Math.min(PLAYER.maxHealth, p.hp + PLAYER.regenRate * dt)
      }
      if (p.isBot && anyHumans) p.bot.update(dt, now, m.state === 'playing')
    }
  }

  // ------------------------------------------------------------------ networking

  emitAll (event, data, reliable = false) {
    for (const p of this.players.values()) if (!p.isBot) p.channel.emit(event, data, reliable ? { reliable: true } : undefined)
  }

  emitOthers (sender, event, data, reliable = false) {
    for (const p of this.players.values()) if (!p.isBot && p !== sender) p.channel.emit(event, data, reliable ? { reliable: true } : undefined)
  }

  broadcastSnapshot () {
    if (!this.humans().length) return
    const now = this.now()
    const list = []
    for (const p of this.players.values()) {
      const flags = (p.alive ? 1 : 0) | (p.crouch ? 2 : 0) | (p.ads ? 4 : 0) | (p.reloading ? 8 : 0) |
        (now - p.firedAt < 400 ? 16 : 0) | (now < p.protectUntil ? 32 : 0)
      const age = Math.max(0, Math.min(1000, Math.round(now - p.posAt)))
      const weapon = WEAPON_CODE[p.slot === 1 ? p.loadout.secondary : p.loadout.primary]
      list.push([p.id, r2(p.pos[0]), r2(p.pos[1]), r2(p.pos[2]), r3(p.yaw), r3(p.pitch), flags, weapon, Math.round(p.hp), p.life, age])
    }
    this.emitAll('snap', { t: now, p: list, c: this.cats.snapshot() })
  }

  roster () {
    return [...this.players.values()].map((p) => ({
      id: p.id, name: p.name, team: p.team, bot: p.isBot, k: p.kills, d: p.deaths, ping: p.isBot ? 0 : Math.round(p.ping)
    }))
  }

  matchInfo () {
    const m = this.match
    return {
      state: m.state,
      scores: m.scores,
      winner: m.winner,
      scoreLimit: MATCH.scoreLimit,
      bots: this.botsEnabled,
      timeLeft: Math.max(0, Math.round(((m.state === 'playing' ? m.endsAt : m.restartAt) - this.now()) / 1000))
    }
  }

  broadcastRoster () {
    this.emitAll('roster', { players: this.roster(), match: this.matchInfo() }, true)
  }

  pingAll () {
    this.emitAll('ping', { t: this.now() })
  }
}

function validVec (v) {
  return Array.isArray(v) && v.length === 3 && v.every(Number.isFinite)
}

function nadeKey (k) {
  return Number.isInteger(k) && k >= 0 ? k % 1e6 : 0
}

// bots roll a fresh class and weapons from their own faction every life
function randomLoadout (team) {
  const cls = CLASS_IDS[Math.floor(Math.random() * CLASS_IDS.length)]
  const c = CLASSES[cls]
  const any = (list) => list[Math.floor(Math.random() * list.length)]
  return { cls, primary: any(c.primary[team]), secondary: any(c.secondary[team]) }
}
