// Drives the real authoritative Game through fake channels: loadout validation, faction restrictions,
// ammunition, team switching and bot loadouts.
import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Game } from '../server/game.js'
import { MATCH } from '../shared/constants.js'
import { WEAPONS, WEAPON_LIST, isValidLoadout, startingAmmo } from '../shared/weapons.js'

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
