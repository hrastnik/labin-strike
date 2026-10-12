// Drives the real authoritative Game through fake channels: loadout validation, faction restrictions,
// ammunition, team switching, bot loadouts, grenades, sprint movement, ammo drops, the knife, the cats and the tanks.
import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Game } from '../server/game.js'
import { MATCH, PLAYER } from '../shared/constants.js'
import { WEAPONS, WEAPON_LIST, GRENADE, KNIFE, AMMO_DROP, CLASS_IDS, isValidLoadout, startingAmmo, sanitizeLoadout, damageFor } from '../shared/weapons.js'
import { NADE_DT, createGrenade, stepGrenade } from '../shared/grenade.js'
import { lineOfSight, rayMap } from '../shared/physics.js'
import { TANK, tankPoint, gunRay, armourFor, underHull } from '../shared/tanks.js'
import { CAT, CAT_STATE, CAT_COATS } from '../server/cats.js'
import { SD, SD_SITES, otherTeam } from '../shared/modes.js'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function fakeChannel () {
  const handlers = {}
  const ch = {
    sent: [],
    player: null,
    on (ev, fn) { handlers[ev] = fn },
    onDisconnect (fn) { handlers.__disconnect = fn },
    emit (ev, data) { ch.sent.push([ev, data]) },
    send (ev, data) { handlers[ev]?.(data) },
    disconnect () { handlers.__disconnect?.() },
    last (ev) { for (let i = ch.sent.length - 1; i >= 0; i--) if (ch.sent[i][0] === ev) return ch.sent[i][1]; return undefined },
    count (ev) { return ch.sent.filter((s) => s[0] === ev).length }
  }
  return ch
}

let game
let clock = 0
const io = { onConnection (fn) { io.connect = fn } }

test.before(async () => {
  game = new Game(io, ROOT)
  await game.init()
  game.stop() // drive time by hand
  game.now = () => clock
  clock = 100000
  game.restartMatch()
})

function advance (ms) {
  const steps = Math.ceil(ms / 33)
  for (let i = 0; i < steps; i++) { clock += ms / steps; game.tick(ms / steps / 1000) }
}

function connect (name, join = {}) {
  const ch = fakeChannel()
  io.connect(ch)
  ch.send('join', { name, ...join })
  return ch
}

function deploy (ch, loadout) {
  clock += 250 // past the loadout request rate limit
  ch.send('loadout', { ...loadout, deploy: true })
  advance(50)
  return ch.player
}

function fire (ch, w, extra = {}) {
  const p = ch.player
  const before = p.ammo[w]
  clock += 2000 // past any fire-rate limit
  ch.send('fire', { w, o: [p.pos[0], p.pos[1] + 1.6, p.pos[2]], e: [p.pos[0], p.pos[1] + 1.6, p.pos[2] - 5], ...extra })
  return p.ammo[w] !== before
}

test('join sanitises a requested loadout to the assigned faction and waits for deploy', () => {
  const ch = connect('Alpha', { team: 'axis', loadout: { cls: 'assault', primary: 'thompson', secondary: 'm1911' } })
  const w = ch.last('welcome')
  assert.equal(w.team, 'axis')
  assert.deepEqual(w.loadout, { cls: 'assault', primary: 'mp40', secondary: 'p38' })
  assert.equal(w.spawn, undefined)
  advance(500)
  assert.equal(ch.player.alive, false, 'not spawned before deploying')
  ch.disconnect()
})

test('server rejects opposing-faction, cross-class and malformed loadout requests', () => {
  const ch = connect('Bravo', { team: 'allies' })
  const p = ch.player
  const before = { ...p.loadout }
  for (const bad of [
    { cls: 'assault', primary: 'mp40', secondary: 'm1911' },
    { cls: 'assault', primary: 'thompson', secondary: 'luger' },
    { cls: 'rifleman', primary: 'thompson', secondary: 'm1911' },
    { cls: '__proto__', primary: 'thompson', secondary: 'm1911' },
    { cls: 'assault', primary: 'constructor', secondary: 'm1911' },
    { cls: 'assault', primary: ['thompson'], secondary: 'm1911' },
    null
  ]) {
    clock += 250
    ch.send('loadout', bad && { ...bad, deploy: true })
    if (bad) assert.equal(ch.last('loadout').applied, 'rejected', JSON.stringify(bad))
    assert.deepEqual(p.loadout, before)
    assert.equal(p.deployed, false)
  }
  ch.disconnect()
})

test('deploying spawns with the chosen loadout and class ammunition', () => {
  const ch = connect('Charlie', { team: 'allies' })
  const p = deploy(ch, { cls: 'support', primary: 'bren', secondary: 'webley' })
  assert.equal(p.alive, true)
  const s = ch.last('spawn')
  assert.deepEqual(s.loadout, { cls: 'support', primary: 'bren', secondary: 'webley' })
  const a = startingAmmo('support', 'bren', 'primary')
  assert.equal(p.ammo.bren, a.mag + a.reserve)
  ch.disconnect()
})

test('fire is only accepted for issued, same-faction weapons with ammunition left', () => {
  const ch = connect('Delta', { team: 'axis' })
  const p = deploy(ch, { cls: 'rifleman', primary: 'kar98k', secondary: 'luger' })
  assert.equal(fire(ch, 'kar98k'), true, 'own primary')
  assert.equal(fire(ch, 'luger'), true, 'own secondary')
  assert.equal(fire(ch, 'm1garand'), false, 'enemy faction weapon')
  assert.equal(fire(ch, 'mp40'), false, 'own faction but not issued')
  assert.equal(fire(ch, 'rifle'), false, 'legacy id')
  assert.equal(fire(ch, 'constructor'), false, 'prototype key')
  // exhaust the pistol
  p.ammo.luger = 1
  assert.equal(fire(ch, 'luger'), true)
  assert.equal(p.ammo.luger, 0)
  const shots = p.firedAt
  assert.equal(fire(ch, 'luger'), false, 'no ammo left')
  assert.equal(p.firedAt, shots)
  ch.disconnect()
})

test('fire rate is limited per weapon', () => {
  const ch = connect('Echo', { team: 'allies' })
  const p = deploy(ch, { cls: 'marksman', primary: 'm1903', secondary: 'm1911' })
  const start = p.ammo.m1903
  clock += 5000
  for (let i = 0; i < 5; i++) {
    clock += 100
    ch.send('fire', { w: 'm1903', o: [p.pos[0], p.pos[1] + 1.6, p.pos[2]], e: [p.pos[0], p.pos[1] + 1.6, p.pos[2] - 5] })
  }
  assert.equal(start - p.ammo.m1903, 1, 'bolt-action cannot fire 5 rounds in 0.5 s')
  ch.disconnect()
})

test('class change applies at once right after spawning, otherwise at the next spawn', () => {
  const ch = connect('Foxtrot', { team: 'axis' })
  const p = deploy(ch, { cls: 'assault', primary: 'stg44', secondary: 'p38' })
  clock += 300
  ch.send('loadout', { cls: 'support', primary: 'mg42', secondary: 'luger' })
  assert.equal(ch.last('loadout').applied, 'now')
  assert.equal(p.loadout.primary, 'mg42')
  assert.equal(p.ammo.mg42, startingAmmo('support', 'mg42', 'primary').mag + startingAmmo('support', 'mg42', 'primary').reserve)
  assert.equal(p.ammo.stg44, undefined, 'old weapon no longer usable')
  assert.equal(fire(ch, 'stg44'), false)

  // once in combat, the change waits for the next life
  fire(ch, 'mg42')
  clock += 300
  ch.send('loadout', { cls: 'marksman', primary: 'kar98k_scoped', secondary: 'p38' })
  assert.equal(ch.last('loadout').applied, 'next')
  assert.equal(p.loadout.primary, 'mg42')
  game.kill(p, null, 'mg42', false)
  advance(MATCH.respawnDelay * 1000 + 100)
  assert.equal(p.alive, true)
  assert.equal(p.loadout.primary, 'kar98k_scoped')
  assert.equal(ch.last('spawn').loadout.primary, 'kar98k_scoped')
  ch.disconnect()
})

test('switching teams converts the loadout, returns to the loadout screen and is rate limited', () => {
  const ch = connect('Golf', { team: 'axis' })
  const p = deploy(ch, { cls: 'assault', primary: 'mp40', secondary: 'luger' })
  const kills = p.kills; const deaths = p.deaths
  clock += 10000
  ch.send('team', { team: 'allies' })
  const t = ch.last('team')
  assert.equal(t.denied, undefined)
  assert.equal(p.team, 'allies')
  assert.equal(p.alive, false)
  assert.equal(p.deployed, false)
  assert.deepEqual(t.loadout, { cls: 'assault', primary: 'thompson', secondary: 'webley' })
  assert.ok(isValidLoadout('allies', p.loadout))
  assert.equal(p.kills, kills); assert.equal(p.deaths, deaths)
  assert.equal(fire(ch, 'mp40'), false, 'dead and wrong faction')

  // cannot spawn with the old faction's weapons after switching
  clock += 250
  ch.send('loadout', { cls: 'assault', primary: 'mp40', secondary: 'luger', deploy: true })
  assert.equal(ch.last('loadout').applied, 'rejected')
  ch.send('team', { team: 'axis' })
  assert.match(ch.last('team').denied, /Wait/)

  deploy(ch, { cls: 'assault', primary: 'sten', secondary: 'm1911' })
  advance(MATCH.respawnDelay * 1000 + 100)
  assert.equal(p.alive, true)
  assert.deepEqual(ch.last('spawn').loadout, { cls: 'assault', primary: 'sten', secondary: 'm1911' })
  ch.disconnect()
})

test('team switch is refused when it would stack the humans', () => {
  const a = connect('Hotel', { team: 'axis' })
  const b = connect('India', { team: 'axis' })
  assert.notEqual(a.player.team, b.player.team, 'second human auto-balanced')
  const allied = a.player.team === 'allies' ? a : b
  clock += 10000
  allied.send('team', { team: 'axis' })
  assert.match(allied.last('team').denied, /unbalanced/)
  assert.equal(allied.player.team, 'allies')
  a.disconnect(); b.disconnect()
})

test('any player can turn the bots off and on for the whole server', () => {
  const a = connect('Kilo')
  const b = connect('Lima')
  const bots = () => [...game.players.values()].filter((p) => p.isBot).length
  assert.ok(bots() > 0)
  clock += 10000
  a.send('bots', { on: false })
  assert.equal(bots(), 0)
  assert.equal(b.last('roster').match.bots, false)
  assert.match(b.last('notice').m, /Kilo turned bots off/)
  b.send('bots', { on: false })
  assert.equal(b.last('notice').m.includes('Lima'), false, 'switching to the current state does nothing')
  a.send('bots', { on: true })
  assert.equal(bots(), 0, 'one player cannot flip it back and forth at once')
  clock += MATCH.botToggleCooldown * 1000
  a.send('bots', { on: true })
  assert.equal(bots(), MATCH.targetPlayers - 2)
  assert.equal(game.matchInfo().bots, true)
  a.disconnect(); b.disconnect()
})

test('bots always carry valid weapons of their own faction', () => {
  const ch = connect('Juliet', { team: 'allies' })
  deploy(ch, { cls: 'assault', primary: 'thompson', secondary: 'm1911' })
  const seen = new Set()
  for (let round = 0; round < 40; round++) {
    for (const p of game.players.values()) {
      if (!p.isBot) continue
      game.spawn(p)
      assert.ok(isValidLoadout(p.team, p.loadout), `${p.name} ${JSON.stringify(p.loadout)}`)
      seen.add(p.loadout.primary)
    }
  }
  assert.ok(seen.size >= 10, `bots use a variety of weapons (${seen.size})`)
  // and bots can fire their weapons through the normal server path
  const bot = [...game.players.values()].find((p) => p.isBot)
  game.fireBot(bot, bot.loadout.primary, [bot.pos[0], bot.pos[1] + 1.6, bot.pos[2]], [0, 0, -1])
  ch.disconnect()
})

test('snapshots carry the weapon actually in hand', () => {
  const ch = connect('Kilo', { team: 'axis' })
  const p = deploy(ch, { cls: 'officer', primary: 'g43', secondary: 'luger' })
  game.broadcastSnapshot()
  const row = (snap) => snap.p.find((e) => e[0] === p.id)
  assert.equal(WEAPON_LIST[row(ch.last('snap'))[7]], 'g43')
  ch.send('st', [p.life, p.pos[0], p.pos[1], p.pos[2], 0, 0, 0, 1, clock])
  game.broadcastSnapshot()
  assert.equal(WEAPON_LIST[row(ch.last('snap'))[7]], 'luger')
  ch.send('st', [p.life, p.pos[0], p.pos[1], p.pos[2], 0, 0, 0, 7, clock])
  game.broadcastSnapshot()
  assert.equal(WEAPON_LIST[row(ch.last('snap'))[7]], 'g43', 'unknown slot index falls back to primary')
  assert.ok(WEAPONS[WEAPON_LIST[row(ch.last('snap'))[7]]])
  ch.disconnect()
})

test('every class on both sides spawns with the grenade, refilled each life', () => {
  for (const team of ['allies', 'axis']) {
    const ch = connect(`Nade ${team}`, { team })
    for (const cls of CLASS_IDS) {
      const p = deploy(ch, sanitizeLoadout(team, { cls }))
      if (!p.alive) game.spawn(p)
      assert.equal(p.grenades, GRENADE.count, `${team} ${cls}`)
    }
    ch.disconnect()
  }
  for (const p of game.players.values()) if (p.isBot && p.alive) assert.equal(p.grenades, GRENADE.count, p.name)
})

test('the server refuses extra, dead and implausible grenade throws', () => {
  const ch = connect('Lima', { team: 'allies' })
  const p = deploy(ch, { cls: 'rifleman', primary: 'm1garand', secondary: 'm1911' })
  const mine = () => game.grenades.filter((g) => g.owner === p.id).length
  const throwIt = (o, d = [0, 0, -1]) => {
    const before = mine()
    ch.send('nade', { o: o || [p.pos[0], p.pos[1] + PLAYER.eye, p.pos[2]], d, k: 7 })
    return mine() > before
  }
  assert.equal(throwIt([p.pos[0] + 10, p.pos[1] + PLAYER.eye, p.pos[2]]), false, 'origin far from the player')
  assert.equal(throwIt(undefined, [0, 0, 0]), false, 'no direction')
  assert.equal(throwIt(undefined, [0, 'x', 1]), false, 'malformed direction')
  assert.equal(throwIt(), true)
  assert.equal(p.grenades, GRENADE.count - 1)
  assert.equal(throwIt(), false, 'one per life')

  const myBooms = () => ch.sent.filter(([ev, d]) => ev === 'boom' && d.id === p.id && d.k === 7).length
  advance(GRENADE.fuse * 1000 - 200)
  assert.equal(myBooms(), 0, 'not before the fuse runs out')
  advance(400)
  assert.equal(myBooms(), 1)
  assert.equal(mine(), 0)

  if (p.alive) game.kill(p, null, 'm1garand', false)
  assert.equal(throwIt(), false, 'dead')
  advance(MATCH.respawnDelay * 1000 + 100)
  assert.equal(p.alive, true)
  assert.equal(p.grenades, GRENADE.count)
  ch.disconnect()
})

// a direction from `at` with nothing solid in the way for `len` metres at foot and chest height
function openDirection (at, len) {
  for (let i = 0; i < 16; i++) {
    const a = (i / 16) * Math.PI * 2
    const d = [Math.cos(a), 0, Math.sin(a)]
    const clear = [0.3, 1.1].every((h) => lineOfSight(game.RAPIER, game.world, [at[0], at[1] + h, at[2]],
      [at[0] + d[0] * len, at[1] + h, at[2] + d[2] * len]))
    if (clear) return d
  }
  throw new Error('no open ground around the spawn')
}

test('a blast hurts enemies in range and the thrower, never teammates, and credits the kill', () => {
  const ch = connect('Mike', { team: 'axis' })
  const p = deploy(ch, { cls: 'assault', primary: 'mp40', secondary: 'p38' })
  const bots = [...game.players.values()].filter((q) => q.isBot && q.alive)
  const [enemy, farEnemy] = bots.filter((q) => q.team === 'allies')
  const mate = bots.find((q) => q.team === 'axis')
  const at = p.pos.slice()
  const d = openDirection(at, 6)
  const along = (m) => [at[0] + d[0] * m, at[1], at[2] + d[2] * m]
  p.pos = along(0); mate.pos = along(3); enemy.pos = along(5); farEnemy.pos = along(4)
  farEnemy.pos[1] += 40 // well out of reach
  for (const q of [p, enemy, farEnemy, mate]) { q.protectUntil = 0; q.hp = PLAYER.maxHealth; q.crouch = false }
  const kills = p.kills
  game.explode({ pos: along(4.5).map((v, i) => i === 1 ? v + 0.05 : v), owner: p.id, team: p.team, k: 0 })
  assert.equal(enemy.alive, false, 'enemy beside the blast is killed')
  assert.equal(p.kills, kills + 1)
  assert.equal(ch.last('kill').w, GRENADE.id)
  assert.equal(ch.last('kill').k, p.id)
  assert.equal(mate.hp, PLAYER.maxHealth, 'no friendly fire')
  assert.equal(farEnemy.hp, PLAYER.maxHealth, 'out of range')
  assert.ok(p.hp < PLAYER.maxHealth && p.alive, `thrower hurt by their own grenade at 4.5 m (${p.hp})`)
  assert.deepEqual(ch.last('dmg').from, along(4.5).map((v, i) => Math.round((i === 1 ? v + 0.05 : v) * 100) / 100), 'damage comes from the blast')
  ch.disconnect()
})

test('bots throw through the same server path, and humans see it', () => {
  const ch = connect('November', { team: 'allies' })
  deploy(ch, { cls: 'assault', primary: 'thompson', secondary: 'm1911' })
  const bot = [...game.players.values()].find((q) => q.isBot && q.alive && q.grenades > 0)
  game.throwGrenade(bot, [bot.pos[0], bot.pos[1] + PLAYER.eye, bot.pos[2]], [0, 0, -1])
  assert.equal(bot.grenades, GRENADE.count - 1)
  assert.equal(ch.last('nade').id, bot.id)
  ch.disconnect()
})

// moves the clock on grenades alone, so no bot gets a turn to interfere
function grenadesFor (ms) {
  clock += ms
  game.updateGrenades(ms / 1000, clock)
}

test('cooking burns the fuse from the cook message, timed by the server', () => {
  const ch = connect('Whiskey', { team: 'allies' })
  const p = deploy(ch, { cls: 'rifleman', primary: 'm1garand', secondary: 'm1911' })
  const other = connect('Xray', { team: 'axis' })
  const booms = () => ch.sent.filter(([ev, d]) => ev === 'boom' && d.id === p.id && d.k === 3).length
  ch.send('cook', { k: 3 })
  grenadesFor(2000)
  ch.send('cook', { k: 9 })
  assert.equal(p.cookK, 3, 'a second cook does not restart the fuse')
  ch.send('nade', { o: [p.pos[0], p.pos[1] + PLAYER.eye, p.pos[2]], d: [0, 0, -1], k: 3 })
  assert.equal(p.grenades, GRENADE.count - 1)
  assert.equal(p.cookAt, 0)
  assert.equal(other.last('nade').f, GRENADE.fuse * 1000 - 2000, 'others are told how much fuse is left')
  grenadesFor(GRENADE.fuse * 1000 - 2000 - 100)
  assert.equal(booms(), 0)
  grenadesFor(150)
  assert.equal(booms(), 1)

  ch.send('cook', { k: 4 })
  assert.equal(p.cookAt, 0, 'no grenade left to cook')
  ch.disconnect(); other.disconnect()
})

test('a grenade held past its fuse goes off in the hand and kills the thrower', () => {
  const ch = connect('Yankee', { team: 'axis' })
  const p = deploy(ch, { cls: 'assault', primary: 'mp40', secondary: 'p38' })
  p.protectUntil = 0
  const kills = p.kills
  ch.send('cook', { k: 0 })
  grenadesFor(GRENADE.fuse * 1000 - 100)
  assert.equal(p.alive, true)
  grenadesFor(150)
  assert.equal(ch.last('nade').d, null, 'the holder is told it fell from their hand')
  assert.equal(p.alive, false)
  assert.equal(p.grenades, 0)
  assert.deepEqual(ch.last('kill'), { k: p.id, v: p.id, w: GRENADE.id, hs: false })
  assert.equal(p.kills, kills, 'no score for blowing yourself up')
  ch.disconnect()
})

test('a soldier killed while cooking drops the live grenade with the fuse it had left', () => {
  const ch = connect('Zulu', { team: 'allies' })
  const p = deploy(ch, { cls: 'assault', primary: 'thompson', secondary: 'm1911' })
  ch.send('cook', { k: 5 })
  grenadesFor(1000)
  game.kill(p, null, 'mp40', false)
  const dropped = ch.last('nade')
  assert.equal(dropped.k, 5)
  assert.equal(dropped.d, null)
  assert.equal(dropped.f, GRENADE.fuse * 1000 - 1000)
  const g = game.grenades.find((q) => q.owner === p.id && q.k === 5)
  assert.ok(g && Math.hypot(...g.vel) === 0, 'falls rather than flies')
  grenadesFor(GRENADE.fuse * 1000 - 1000 + 50)
  assert.ok(ch.sent.some(([ev, d]) => ev === 'boom' && d.id === p.id && d.k === 5))
  advance(MATCH.respawnDelay * 1000 + 100)
  assert.equal(p.cookAt, 0, 'a new life starts with nothing cooking')
  ch.disconnect()
})

test('a thrown grenade arcs, lands and settles before the fuse runs out', () => {
  const sp = game.map.spawns.allies[0]
  const eye = [sp[0], sp[1] + PLAYER.eye, sp[2]]
  const g = createGrenade(eye, openDirection(sp, 20))
  let peak = eye[1]
  for (let i = 0; i < GRENADE.fuse / NADE_DT; i++) { stepGrenade(game.RAPIER, game.world, g); peak = Math.max(peak, g.pos[1]) }
  assert.ok(peak > eye[1] + 0.3, 'lofted above the view line')
  assert.ok(g.rest, 'at rest')
  assert.ok(g.pos[1] < eye[1] - 1, 'on the ground')
  assert.ok(Math.hypot(g.pos[0] - eye[0], g.pos[2] - eye[2]) > 10, 'thrown a fair distance')
})

test('sprinting passes the movement check, a teleport does not', () => {
  const ch = connect('Oscar', { team: 'axis' })
  const p = deploy(ch, { cls: 'assault', primary: 'mp40', secondary: 'p38' })
  const speed = PLAYER.walkSpeed * PLAYER.sprintMul * WEAPONS.mp40.moveMul
  const tps = ch.count('tp')
  const x0 = p.pos[0]
  for (let i = 1; i <= 15; i++) {
    clock += 1000 / 30
    ch.send('st', [p.life, x0 + speed * i / 30, p.pos[1], p.pos[2], 0, 0, 0, 0, clock])
  }
  assert.equal(ch.count('tp'), tps, 'sprint accepted')
  assert.ok(p.pos[0] > x0 + 3)
  clock += 1000 / 30
  ch.send('st', [p.life, p.pos[0] + 6, p.pos[1], p.pos[2], 0, 0, 0, 0, clock])
  assert.equal(ch.count('tp'), tps + 1, 'teleport pulled back')
  ch.disconnect()
})

test('every death leaves an ammo can on the ground under the body, gone after its lifetime', () => {
  const ch = connect('Papa', { team: 'allies' })
  const p = deploy(ch, { cls: 'assault', primary: 'thompson', secondary: 'm1911' })
  const ground = p.pos[1]
  p.pos = [p.pos[0], ground + 1.5, p.pos[2]] // killed in mid-jump
  game.kill(p, null, 'thompson', false)
  const can = ch.last('drop')
  assert.equal(can.t, 'allies')
  assert.ok(Math.abs(can.p[1] - ground) < 0.3, `on the ground (${can.p[1]} vs ${ground})`)
  assert.equal(can.ttl, AMMO_DROP.lifetime * 1000)
  const alive = () => game.drops.some((d) => d.id === can.i)
  game.updateDrops(clock + AMMO_DROP.lifetime * 1000 - 100)
  assert.ok(alive(), 'still there just before its time')
  game.updateDrops(clock + AMMO_DROP.lifetime * 1000)
  assert.ok(!alive(), 'despawned')
  assert.equal(ch.sent.filter(([ev, d]) => ev === 'undrop' && d.i === can.i).length, 1)
  ch.disconnect()
})

test('anyone short of ammunition takes a can from either side, topped up to no more than a full load', () => {
  const ch = connect('Quebec', { team: 'axis' })
  const p = deploy(ch, { cls: 'rifleman', primary: 'kar98k', secondary: 'luger' })
  const full = { kar98k: p.ammo.kar98k, luger: p.ammo.luger }
  game.dropAmmo({ pos: p.pos.slice(), team: 'allies' })
  const can = ch.last('drop')
  const lying = () => game.drops.some((d) => d.id === can.i)
  game.updateDrops(clock)
  assert.ok(lying(), 'a fully stocked soldier leaves it')
  p.ammo.kar98k = 3
  p.ammo.luger = full.luger - 2
  game.updateDrops(clock)
  const got = ch.last('ammo')
  assert.equal(got.life, p.life)
  assert.equal(got.a.kar98k, Math.ceil(startingAmmo('rifleman', 'kar98k', 'primary').reserve * AMMO_DROP.share))
  assert.equal(got.a.luger, 2, 'only what fits')
  assert.equal(p.ammo.kar98k, 3 + got.a.kar98k)
  assert.equal(p.ammo.luger, full.luger)
  assert.ok(!lying())
  assert.equal(ch.last('undrop').by, p.id)
  ch.disconnect()
})

test('a new round clears the cans, and joiners are sent the ones lying around', () => {
  const a = connect('Uniform', { team: 'allies' })
  deploy(a, { cls: 'assault', primary: 'thompson', secondary: 'm1911' })
  game.dropAmmo({ pos: a.player.pos.slice(), team: 'axis' })
  const b = connect('Victor', { team: 'axis' })
  assert.ok(b.last('welcome').drops.some((d) => d.i === a.last('drop').i))
  game.restartMatch()
  assert.equal(game.drops.length, 0)
  a.disconnect(); b.disconnect()
})

test('one knife stab kills an enemy in reach and in front, and nobody else', () => {
  const ch = connect('Romeo', { team: 'axis' })
  const p = deploy(ch, { cls: 'assault', primary: 'mp40', secondary: 'p38' })
  const bots = [...game.players.values()].filter((q) => q.isBot && q.alive)
  const enemy = bots.find((q) => q.team === 'allies')
  const mate = bots.find((q) => q.team === 'axis')
  const at = p.pos.slice()
  const d = openDirection(at, 5)
  const eye = [at[0], at[1] + PLAYER.eye, at[2]]
  const place = (q, m) => { q.pos = [at[0] + d[0] * m, at[1], at[2] + d[2] * m]; q.protectUntil = 0; q.hp = PLAYER.maxHealth; q.crouch = false }
  const stab = (q, dir = d, wait = 1000) => { clock += wait; ch.send('knife', { o: eye, d: dir, hit: q.id }) }

  place(mate, 1)
  stab(mate)
  assert.equal(mate.hp, PLAYER.maxHealth, 'no friendly fire')
  mate.pos[1] += 40
  place(enemy, 4.5)
  stab(enemy)
  assert.equal(enemy.hp, PLAYER.maxHealth, 'out of reach')
  place(enemy, 1)
  stab(enemy, d.map((v) => -v))
  assert.equal(enemy.hp, PLAYER.maxHealth, 'behind the attacker')
  stab(enemy, d, 50)
  assert.equal(enemy.hp, PLAYER.maxHealth, 'too soon after the last stab')

  const kills = p.kills
  stab(enemy)
  assert.equal(enemy.alive, false)
  assert.equal(p.kills, kills + 1)
  assert.equal(ch.last('kill').w, KNIFE.id)
  assert.equal(ch.last('hit').k, true)
  ch.disconnect()
})

test('bots knife an enemy standing in front of them, and humans see the stab', () => {
  const ch = connect('Sierra', { team: 'allies' })
  const p = deploy(ch, { cls: 'assault', primary: 'thompson', secondary: 'm1911' })
  const bot = [...game.players.values()].find((q) => q.isBot && q.alive && q.team === 'axis')
  const at = p.pos.slice()
  const d = openDirection(at, 3)
  bot.pos = [at[0] + d[0], at[1], at[2] + d[2]]
  bot.yaw = Math.atan2(d[0], d[2]) // facing back towards the player
  bot.protectUntil = 0
  p.protectUntil = 0
  const b = bot.bot
  b.motor.setPosition(...bot.pos)
  Object.assign(b, { target: p.id, visible: true, reactUntil: 0, knifeReadyAt: 0, nextPerceive: Infinity })
  b.update(1 / 30, clock, true)
  assert.equal(p.alive, false)
  assert.equal(ch.last('kill').w, KNIFE.id)
  assert.equal(ch.last('kill').k, bot.id)
  assert.equal(ch.last('stab').id, bot.id)
  ch.disconnect()
})

test('cats wander the map on their own and show up in snapshots', () => {
  const ch = connect('Tango', { team: 'allies' })
  const start = game.cats.list.map((c) => c.pos.slice())
  // a cat with nothing to do mostly goes for a stroll somewhere nearby
  for (const c of game.cats.list) for (let i = 0; i < 50 && c.state !== CAT_STATE.walk; i++) game.cats.decide(c, clock)
  assert.ok(game.cats.list.every((c) => c.state === CAT_STATE.walk))
  for (const c of game.cats.list) c.calmAt = 0
  for (let i = 0; i < 200; i++) { clock += 33; game.cats.move.call(game.cats, game.cats.list[0], 0.033, clock) }
  assert.ok(Math.hypot(game.cats.list[0].pos[0] - start[0][0], game.cats.list[0].pos[2] - start[0][2]) > 0.5, 'went for a stroll')
  for (const c of game.cats.list) assert.ok(game.nav.isWalkable(c.pos[0], c.pos[2]) || game.nav.nearestWalkable(c.pos[0], c.pos[2], 1) >= 0, 'on walkable ground')
  game.broadcastSnapshot()
  const snap = ch.last('snap')
  assert.equal(snap.c.length, CAT_COATS.length)
  assert.deepEqual(snap.c.map((r) => r[1]).sort(), CAT_COATS.map((_, i) => i))
  ch.disconnect()
})

test('cats bolt from a soldier walking up, a passing bullet and a grenade, but let a crouching one creep close', () => {
  const ch = connect('Uniform', { team: 'axis' })
  const p = deploy(ch, { cls: 'assault', primary: 'mp40', secondary: 'p38' })
  const cat = game.cats.list[0]
  // the bots are lifted out of the way so only this soldier is near the cat
  const others = [...game.players.values()].filter((q) => q !== p && q.alive)
  for (const q of others) q.pos[1] += 40
  const calm = () => Object.assign(cat, { state: CAT_STATE.lie, until: Infinity, path: null, calmAt: 0 })
  cat.pos = p.pos.slice()
  const d = openDirection(cat.pos, 4)

  calm()
  p.crouch = true
  p.pos = [cat.pos[0] + d[0] * 1.5, cat.pos[1], cat.pos[2] + d[2] * 1.5]
  game.cats.update(1 / 30, clock)
  assert.equal(cat.state, CAT_STATE.lie, 'a crouching soldier can sneak up')
  p.crouch = false
  game.cats.update(1 / 30, clock)
  assert.equal(cat.state, CAT_STATE.run, 'standing up at arm\'s length scares it')
  const from = Math.hypot(cat.path.at(-1)[0] - p.pos[0], cat.path.at(-1)[2] - p.pos[2])
  assert.ok(from > CAT.personal * 2, `runs well away (${from.toFixed(1)} m)`)

  p.pos[1] += 40 // out of the way
  calm()
  game.cats.hearShot([cat.pos[0] - 20, cat.pos[1] + 1, cat.pos[2] + 1], [cat.pos[0] + 20, cat.pos[1] + 1, cat.pos[2] + 1])
  assert.equal(cat.state, CAT_STATE.run, 'a bullet whizzing past')
  calm()
  game.cats.hearShot([cat.pos[0] - 20, cat.pos[1] + 1, cat.pos[2] + 10], [cat.pos[0] + 20, cat.pos[1] + 1, cat.pos[2] + 10])
  assert.equal(cat.state, CAT_STATE.lie, 'shots far off are ignored')
  game.explode({ owner: p.id, team: p.team, k: 0, pos: [cat.pos[0] + 5, cat.pos[1], cat.pos[2]] })
  assert.equal(cat.state, CAT_STATE.run, 'a grenade going off')
  for (const q of others) q.pos[1] -= 40
  ch.disconnect()
})

// ------------------------------------------------------------------ Search and Destroy

const AXIS_KIT = { cls: 'assault', primary: 'mp40', secondary: 'p38' }
const ALLIES_KIT = { cls: 'assault', primary: 'thompson', secondary: 'm1911' }

// two humans and no bots, so nothing but the test decides a round
function sdMatch () {
  game.botsEnabled = false
  game.balanceBots()
  const ax = connect('Victor', { team: 'axis' })
  const al = connect('Whiskey', { team: 'allies' })
  const a = deploy(ax, AXIS_KIT)
  const b = deploy(al, ALLIES_KIT)
  game.mode = 'sd'
  game.restartMatch()
  for (const p of [a, b]) p.protectUntil = 0
  return { ax, al, a, b }
}

function endSd (...chs) {
  for (const ch of chs) ch.disconnect()
  game.mode = 'tdm'
  game.botsEnabled = true
  game.restartMatch()
  game.balanceBots()
}

function plantAt (ch, site) {
  ch.player.pos = site.pos.slice()
  ch.send('use', { on: true })
  advance(SD.plantTime * 1000 + 200)
}

test('S&D: any player switches the mode, and the fallen stay down until the next round', () => {
  game.botsEnabled = false
  game.balanceBots()
  const ax = connect('Victor', { team: 'axis' })
  const al = connect('Whiskey', { team: 'allies' })
  const a = deploy(ax, AXIS_KIT)
  const b = deploy(al, ALLIES_KIT)
  clock += MATCH.modeSwitchCooldown * 1000
  ax.send('mode', { mode: 'sd' })
  assert.ok(al.sent.some(([ev, d]) => ev === 'notice' && /Victor switched the mode to Search & Destroy/.test(d.m)))
  const m = al.last('roster').match
  assert.deepEqual([m.mode, m.round, m.attackers, m.roundState, m.scoreLimit], ['sd', 1, SD.firstAttackers, 'live', SD.roundsToWin])
  assert.ok(a.alive && b.alive, 'everyone deployed starts the round')
  ax.send('mode', { mode: 'tdm' })
  assert.equal(game.mode, 'sd', 'one player cannot flip the mode straight back')

  b.protectUntil = 0
  game.applyDamage(b, a, 500, 'mp40', 'body')
  advance(100)
  assert.deepEqual([game.sd.state, game.sd.winner, game.sd.reason], ['over', 'axis', 'eliminated'])
  assert.deepEqual(game.match.scores, { allies: 0, axis: 1 }, 'rounds, not kills, are the score')
  advance((MATCH.respawnDelay + 1) * 1000)
  assert.equal(b.alive, false, 'no respawning')
  advance(SD.roundOver * 1000)
  assert.equal(game.sd.round, 2)
  assert.ok(b.alive, 'back for the next round')
  endSd(ax, al)
})

test('S&D: an attacker plants by holding use at a site, and a defender who stays put defuses it', () => {
  const { ax, al, a, b } = sdMatch()
  const site = SD_SITES[game.sd.defenders][0]
  b.pos = [site.pos[0] + 20, site.pos[1], site.pos[2]]
  a.pos = [site.pos[0] + SD.siteRadius + 2, site.pos[1], site.pos[2]]
  ax.send('use', { on: true })
  advance(SD.plantTime * 1000 + 200)
  assert.equal(game.sd.bomb, null, 'nothing to plant outside a site')
  plantAt(ax, site)
  assert.equal(game.sd.bomb?.site, site.id)
  assert.equal(al.last('bomb').e, 'plant')
  assert.equal(ax.last('act').k, null)
  assert.equal(al.last('roster').match.bomb.s, site.id)

  const bp = game.sd.bomb.pos
  b.pos = [bp[0] + 1, bp[1], bp[2]]
  al.send('use', { on: true })
  advance(100)
  assert.equal(al.last('act').k, 'defuse')
  advance(SD.defuseTime * 1000 - 1000)
  b.pos = [bp[0] - 1, bp[1], bp[2]]
  advance(1500)
  assert.equal(game.sd.state, 'live', 'shifting position starts the defuse over')
  advance(SD.defuseTime * 1000)
  assert.deepEqual([game.sd.state, game.sd.winner, game.sd.reason], ['over', 'allies', 'defused'])
  assert.equal(al.last('bomb').e, 'defuse')
  endSd(ax, al)
})

test('S&D: the bomb kills everyone close when it goes off, and a round with no plant goes to the defenders', () => {
  const { ax, al, a, b } = sdMatch()
  const site = SD_SITES[game.sd.defenders][1]
  b.pos = [site.pos[0] + 30, site.pos[1], site.pos[2]]
  plantAt(ax, site)
  const bp = game.sd.bomb.pos
  b.pos = [bp[0] + SD.killRadius - 2, bp[1], bp[2]]
  a.pos = [bp[0] - SD.blastRadius - 5, bp[1], bp[2]]
  advance(SD.bombTime * 1000)
  assert.deepEqual([game.sd.winner, game.sd.reason], ['axis', 'bomb'])
  assert.equal(b.alive, false, 'caught in the blast')
  assert.ok(a.alive, 'out of reach')
  assert.equal(al.last('bomb').e, 'boom')
  assert.equal(al.last('kill').w, SD.bomb.id)

  advance(SD.roundOver * 1000 + 100)
  assert.equal(game.sd.state, 'live')
  advance(SD.roundTime * 1000)
  assert.deepEqual([game.sd.winner, game.sd.reason], ['allies', 'time'])
  endSd(ax, al)
})

test('S&D: the roles swap at halftime and the first side to the round limit wins the match', () => {
  const { ax, al } = sdMatch()
  game.sd.round = SD.halftime
  game.sd.endRound(game.sd.defenders, 'time')
  advance(SD.roundOver * 1000 + 100)
  assert.equal(game.sd.round, SD.halftime + 1)
  assert.equal(game.sd.attackers, otherTeam(SD.firstAttackers))
  assert.ok(al.sent.some(([ev, d]) => ev === 'notice' && /Halftime/.test(d.m)))
  game.match.scores.allies = SD.roundsToWin - 1
  game.sd.endRound('allies', 'eliminated')
  assert.deepEqual([game.match.state, game.match.winner], ['ended', 'allies'])
  endSd(ax, al)
})

test('S&D: bots plant at their site when nobody is around, and defending bots run to the bomb and defuse it', () => {
  const ch = connect('Xray', { team: 'axis' })
  game.mode = 'sd'
  game.restartMatch()
  const sd = game.sd
  const quiet = (q) => Object.assign(q.bot, { target: null, visible: false, alertPos: null, nextPerceive: Infinity, pauseUntil: 0 })
  const run = (q, ms) => { for (let t = 0; t < ms && sd.state === 'live'; t += 33) { clock += 33; q.bot.update(0.033, clock, true); sd.updateActions(clock) } }

  const planter = [...game.players.values()].find((q) => q.isBot && q.team === sd.attackers)
  const site = SD_SITES[sd.defenders].find((s) => s.id === planter.bot.sdSite)
  planter.bot.motor.setPosition(...site.pos)
  planter.pos = site.pos.slice()
  quiet(planter)
  run(planter, SD.plantTime * 1000 + 1500)
  assert.equal(sd.bomb?.site, site.id, 'planted')
  assert.equal(sd.bomb.by, planter.id)

  const defender = [...game.players.values()].find((q) => q.isBot && q.team === sd.defenders)
  // 4 m off in the open, on the bomb's own level (site B is up on the terrace)
  const bp = sd.bomb.pos
  const start = Array.from({ length: 16 }, (_, k) => [bp[0] + Math.cos(k * Math.PI / 8) * 4, bp[1], bp[2] + Math.sin(k * Math.PI / 8) * 4])
    .find((pt) => {
      const i = game.nav.nearestWalkable(pt[0], pt[2], 0)
      return i >= 0 && Math.abs(game.nav.height[i] - bp[1]) < 0.3 && [0.3, 1.1].every((h) => lineOfSight(game.RAPIER, game.world, [bp[0], bp[1] + h, bp[2]], [pt[0], pt[1] + h, pt[2]]))
    })
  defender.bot.motor.setPosition(...start)
  defender.pos = start
  quiet(defender)
  run(defender, SD.defuseTime * 1000 + 4000)
  assert.deepEqual([sd.state, sd.winner, sd.reason], ['over', sd.defenders, 'defused'])
  ch.disconnect()
  endSd()
})

// ------------------------------------------------------------------ Tanks

// two humans and no bots, with the tanks switched on by the axis soldier
function tankMatch () {
  game.botsEnabled = false
  game.balanceBots()
  const ax = connect('Yankee', { team: 'axis' })
  const al = connect('Zulu', { team: 'allies' })
  const a = deploy(ax, AXIS_KIT)
  const b = deploy(al, ALLIES_KIT)
  clock += MATCH.tankToggleCooldown * 1000
  ax.send('tanks', { on: true })
  for (const p of [a, b]) p.protectUntil = 0
  return { ax, al, a, b, tank: (team) => game.tanks.list.find((t) => t.team === team) }
}

function endTanks (...chs) {
  for (const ch of chs) ch.disconnect()
  game.tanksEnabled = false
  game.mode = 'tdm'
  game.botsEnabled = true
  game.restartMatch()
  game.balanceBots()
}

// standing on the ground just off the tank's left side
const beside = (t) => tankPoint(t, -(TANK.half[0] + 0.6), 0, 0)

function climbIn (ch, t) {
  ch.player.pos = beside(t)
  ch.send('tank', { on: true })
  assert.equal(ch.player.tank, t)
}

// a point straight down the gun's line, short of whatever solid it would hit first
function downTheBarrel (t, want) {
  const { o, d } = gunRay(t)
  const mh = rayMap(game.RAPIER, game.world, o, d, 250)
  const m = Math.min(want, (mh ? mh.dist : 250) - 1)
  assert.ok(m > 4, `room in front of the ${t.team} tank (${m})`)
  return [o[0] + d[0] * m, o[1], o[2] + d[2] * m]
}

test('tanks: any player switches them on for the whole server, one per side, parked clear of the spawns', () => {
  assert.equal(game.tanks.list.length, 0, 'off by default')
  const { ax, al } = tankMatch()
  assert.equal(al.last('roster').match.tanks, true)
  assert.match(al.last('notice').m, /Yankee turned tanks on/)
  assert.deepEqual(game.tanks.list.map((t) => t.team).sort(), ['allies', 'axis'])
  for (const t of game.tanks.list) {
    assert.equal(t.hp, TANK.maxHealth)
    for (const s of game.map.spawns[t.team]) assert.equal(underHull(t, s[0], s[1], s[2], 1), false, 'no spawn point under the hull')
  }
  game.broadcastSnapshot()
  assert.equal(al.last('snap').k.length, 2)
  al.send('tanks', { on: false })
  assert.equal(game.tanks.list.length, 0)
  endTanks(ax, al)
})

test("tanks: a soldier climbs into their own side's tank only, one at a time, and steps out beside it", () => {
  const { ax, al, a, b, tank } = tankMatch()
  const mine = tank('axis')
  a.pos = beside(tank('allies'))
  ax.send('tank', { on: true })
  assert.equal(a.tank, null, "not the enemy's")
  a.pos = tankPoint(mine, -(TANK.half[0] + 3), 0, 0)
  ax.send('tank', { on: true })
  assert.equal(a.tank, null, 'out of reach')
  climbIn(ax, mine)
  assert.equal(mine.driver, a.id)
  assert.equal(ax.last('drive').id, mine.id)
  const mate = connect('Alfa', { team: 'axis' })
  const c = deploy(mate, AXIS_KIT)
  c.pos = beside(mine)
  mate.send('tank', { on: true })
  assert.equal(c.tank, null, 'taken')
  game.broadcastSnapshot()
  assert.ok(al.last('snap').p.find((e) => e[0] === a.id)[6] & 64, 'snapshots say who is inside')
  assert.equal(fire(ax, 'mp40'), false, 'no rifle out of the hatch')

  ax.send('tank', { on: false })
  assert.equal(a.tank, null)
  assert.equal(mine.driver, 0)
  const out = ax.last('drive')
  assert.equal(out.id, 0)
  assert.deepEqual(a.pos, out.pos)
  assert.equal(underHull(mine, ...out.pos, 0.2), false, 'out beside the hull, not in it')
  assert.ok(Math.hypot(out.pos[0] - mine.pos[0], out.pos[2] - mine.pos[2]) < TANK.half[1] + 2)
  mate.send('tank', { on: true })
  assert.equal(c.tank, mine, 'free again')
  mate.disconnect()
  assert.equal(mine.driver, 0, 'a driver who leaves frees it')
  endTanks(ax, al)
})

test('tanks: the driver moves the tank at its own pace, and a jump is pulled back', () => {
  const { ax, al, a, tank } = tankMatch()
  const t = tank('axis')
  climbIn(ax, t)
  const start = t.pos.slice()
  clock += 1000
  ax.send('tk', [a.life, start[0] + 4, start[1], start[2], t.yaw + 0.3, t.yaw + 1, 2, clock])
  assert.deepEqual(t.pos, [start[0] + 4, start[1], start[2]])
  assert.deepEqual(a.pos, t.pos, 'the driver rides along')
  assert.equal(t.gun, TANK.pitchMax, 'the gun only elevates so far')
  assert.deepEqual([t.body.pos.x, t.body.pos.z], [t.pos[0], t.pos[2]], 'the collider follows')
  clock += 100
  ax.send('tk', [a.life, t.pos[0] + 20, start[1], start[2], t.yaw, t.turret, 0, clock])
  assert.equal(t.pos[0], start[0] + 4)
  assert.deepEqual(ax.last('tp').pos, t.pos)
  endTanks(ax, al)
})

test('tanks: small arms barely scratch one, a grenade hurts it, and the driver inside is out of reach', () => {
  const { ax, al, a, b, tank } = tankMatch()
  const t = tank('allies')
  climbIn(al, t)
  a.pos = beside(t)
  const side = tankPoint(t, -TANK.half[0], 1, 0)
  const o = [a.pos[0], a.pos[1] + PLAYER.eye, a.pos[2]]
  const dist = Math.hypot(side[0] - o[0], side[1] - o[1], side[2] - o[2])
  assert.equal(fire(ax, 'mp40', { e: side, hit: { tank: t.id } }), true)
  assert.equal(t.hp, TANK.maxHealth - damageFor('mp40', dist, 'body') * armourFor('mp40'))
  assert.ok(t.hp > TANK.maxHealth - 5)
  assert.equal(ax.last('hit').tank, t.id)
  assert.equal(al.last('tdmg').a, a.id)
  fire(ax, 'mp40', { e: [b.pos[0], b.pos[1] + 1.6, b.pos[2]], hit: { id: b.id, zone: 'head' } })
  assert.equal(b.hp, PLAYER.maxHealth, 'the driver is behind armour')

  const hp = t.hp
  a.pos = [a.pos[0], a.pos[1] + 40, a.pos[2]]
  game.explode({ pos: tankPoint(t, -(TANK.half[0] + 0.5), 0.05, 0), owner: a.id, team: a.team, k: 0 })
  assert.ok(hp - t.hp > 200, `a grenade at the tracks (${hp - t.hp})`)
  assert.equal(b.hp, PLAYER.maxHealth)
  endTanks(ax, al)
})

test('tanks: the cannon reloads between shells, kills soldiers in the blast, and burns out the enemy tank for the rest of the match', () => {
  const { ax, al, a, b, tank } = tankMatch()
  const mine = tank('axis'); const theirs = tank('allies')
  climbIn(ax, mine)
  const shells = () => al.count('shell')
  const at = downTheBarrel(mine, 9)
  b.pos = [at[0], at[1] - 1.2, at[2]]
  clock += TANK.reload * 1000
  ax.send('shell', { t: mine.turret, g: 0 })
  assert.equal(shells(), 1)
  assert.equal(b.alive, false)
  assert.deepEqual([al.last('kill').k, al.last('kill').w], [a.id, TANK.gunId])
  ax.send('shell', { t: mine.turret, g: 0 })
  assert.equal(shells(), 1, 'still reloading')

  advance((MATCH.respawnDelay + 0.5) * 1000)
  assert.ok(b.alive)
  b.protectUntil = 0
  climbIn(al, theirs)
  const p = downTheBarrel(mine, 12)
  theirs.pos = [p[0], mine.pos[1], p[2]]
  let n = 0
  while (!theirs.destroyed && n < 10) {
    clock += TANK.reload * 1000
    ax.send('shell', { t: mine.turret, g: 0 })
    n++
  }
  assert.equal(n, Math.ceil(TANK.maxHealth / (TANK.damage * armourFor(TANK.gunId))), 'shells it takes')
  assert.equal(al.last('tankboom').id, theirs.id)
  assert.equal(b.alive, false, 'the crew goes with it')
  assert.equal(b.tank, null)
  assert.equal(al.last('drive').id, theirs.id, 'the kill tells the crew, not a drive message that would set them down in the hull')
  assert.equal(al.last('kill').w, TANK.gunId)

  advance((MATCH.respawnDelay + 0.5) * 1000)
  b.pos = beside(theirs)
  al.send('tank', { on: true })
  assert.equal(b.tank, null, 'nobody drives a wreck')
  clock += MATCH.tankToggleCooldown * 1000
  al.send('tanks', { on: false })
  clock += MATCH.tankToggleCooldown * 1000
  al.send('tanks', { on: true })
  assert.deepEqual(game.tanks.list.map((t) => t.team), ['axis'], 'switching them off and on does not bring it back')
  game.restartMatch()
  assert.deepEqual(game.tanks.list.map((t) => t.team).sort(), ['allies', 'axis'], 'a new match does')
  endTanks(ax, al)
})

test('tanks: the tracks crush an enemy the tank rolls over, not one it creeps up to', () => {
  const { ax, al, a, b, tank } = tankMatch()
  const t = tank('axis')
  climbIn(ax, t)
  const move = (m, ms) => {
    clock += ms
    const p = tankPoint(t, 0, 0, -m)
    ax.send('tk', [a.life, p[0], p[1], p[2], t.yaw, t.turret, 0, clock])
  }
  b.pos = tankPoint(t, 0, 0, -(TANK.half[1] + 0.3))
  move(0.5, 1000)
  assert.ok(b.alive, 'creeping')
  b.pos = tankPoint(t, 0, 0, -(TANK.half[1] + 1))
  move(2, 300)
  assert.equal(b.alive, false)
  assert.equal(al.last('kill').w, TANK.crushId)
  endTanks(ax, al)
})

test('tanks: in S&D every round starts with both tanks back home and empty', () => {
  const { ax, al, a, b, tank } = tankMatch()
  game.mode = 'sd'
  game.restartMatch()
  const t = tank('axis')
  const home = t.pos.slice()
  climbIn(ax, t)
  clock += 1000
  ax.send('tk', [a.life, home[0] + 3, home[1], home[2], t.yaw, t.turret, 0, clock])
  ax.send('use', { on: true })
  assert.equal(game.sd.actionFor(a), null, 'no planting from inside')
  game.sd.endRound('axis', 'time')
  advance(SD.roundOver * 1000 + 100)
  assert.equal(game.sd.round, 2)
  assert.deepEqual(t.pos, home)
  assert.equal(t.driver, 0)
  assert.equal(a.tank, null)
  assert.ok(a.alive)
  endTanks(ax, al)
})
