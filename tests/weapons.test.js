// Catalogue and faction-rule checks (pure data, no server).
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  WEAPONS, WEAPON_LIST, WEAPON_CODE, CLASSES, CLASS_IDS, FACTIONS, canUse, sanitizeLoadout, isValidLoadout,
  GRENADE, KNIFE, AMMO_DROP, startingAmmo, reloadDuration, damageFor, blastDamage, ammoPickup
} from '../shared/weapons.js'
import { PLAYER } from '../shared/constants.js'

const REQUIRED = ['name', 'faction', 'category', 'rpm', 'mag', 'reserve', 'reloadTime', 'drawTime', 'damage', 'headMul',
  'legMul', 'falloffStart', 'falloffEnd', 'falloffMin', 'range', 'adsFov', 'moveMul', 'adsTime', 'velocity']

test('every weapon has a complete, sane stat block', () => {
  for (const id of WEAPON_LIST) {
    const w = WEAPONS[id]
    for (const k of REQUIRED) assert.ok(w[k] != null, `${id}.${k}`)
    assert.ok(FACTIONS.includes(w.faction), `${id} faction`)
    assert.ok(w.falloffEnd > w.falloffStart, `${id} falloff`)
    assert.ok(w.spread.hip >= w.spread.ads, `${id} hip spread >= ads spread`)
    assert.ok(Number.isFinite(w.reloadTime) && w.reloadTime > 0, `${id} reload`)
    assert.equal(WEAPON_LIST[WEAPON_CODE[id]], id)
  }
})

test('original StG 44 and M1911 stats are unchanged', () => {
  const s = WEAPONS.stg44
  assert.deepEqual([s.rpm, s.mag, s.reserve, s.reloadTime, s.drawTime, s.damage, s.falloffStart, s.falloffEnd, s.falloffMin, s.adsFov],
    [600, 30, 150, 2.4, 0.45, 27, 30, 80, 0.65, 50])
  assert.deepEqual(s.spread, { hip: 0.03, ads: 0.004, move: 0.035, air: 0.12, crouchMul: 0.7, bloom: 0.007, bloomMax: 0.05, recover: 0.12 })
  assert.deepEqual(s.recoil, { pitch: 0.011, yaw: 0.005, recover: 6 })
  const p = WEAPONS.m1911
  assert.deepEqual([p.rpm, p.mag, p.reserve, p.reloadTime, p.drawTime, p.damage, p.falloffStart, p.falloffEnd, p.falloffMin, p.adsFov],
    [360, 7, 42, 1.7, 0.3, 34, 15, 45, 0.55, 60])
  assert.deepEqual(p.recoil, { pitch: 0.022, yaw: 0.006, recover: 7 })
})

test('every class offers only its own faction\'s weapons', () => {
  for (const cls of CLASS_IDS) {
    for (const team of FACTIONS) {
      for (const slot of ['primary', 'secondary']) {
        const list = CLASSES[cls][slot][team]
        assert.ok(list.length > 0, `${cls}.${slot}.${team} empty`)
        for (const id of list) assert.ok(canUse(team, id), `${cls}.${slot}.${team} contains ${id}`)
      }
    }
  }
})

test('canUse rejects other factions, unknown ids and prototype keys', () => {
  assert.ok(canUse('axis', 'mp40'))
  assert.ok(!canUse('allies', 'mp40'))
  assert.ok(!canUse('axis', 'thompson'))
  for (const bad of ['__proto__', 'constructor', 'toString', '', null, undefined, 42, 'rifle']) {
    assert.ok(!canUse('axis', bad), String(bad))
    assert.ok(!canUse('allies', bad), String(bad))
  }
})

test('sanitizeLoadout maps a loadout to the equivalent weapon of the new faction', () => {
  assert.deepEqual(sanitizeLoadout('allies', { cls: 'assault', primary: 'mp40', secondary: 'luger' }),
    { cls: 'assault', primary: 'thompson', secondary: 'webley' })
  assert.deepEqual(sanitizeLoadout('axis', { cls: 'support', primary: 'bren', secondary: 'm1911' }),
    { cls: 'support', primary: 'fg42', secondary: 'p38' })
  // third allied support weapon has no axis counterpart at that position: clamp to the last one
  assert.deepEqual(sanitizeLoadout('axis', { cls: 'support', primary: 'm1919a6', secondary: 'm1911' }).primary, 'fg42')
  assert.deepEqual(sanitizeLoadout('axis', { cls: '__proto__', primary: 'constructor' }), { cls: 'assault', primary: 'mp40', secondary: 'p38' })
  for (const team of FACTIONS) {
    for (const cls of CLASS_IDS) {
      for (const id of WEAPON_LIST) {
        const l = sanitizeLoadout(team, { cls, primary: id, secondary: id })
        assert.ok(isValidLoadout(team, l), `${team} ${cls} ${id}`)
      }
    }
  }
})

test('isValidLoadout requires class membership and faction', () => {
  assert.ok(isValidLoadout('axis', { cls: 'rifleman', primary: 'kar98k', secondary: 'luger' }))
  assert.ok(!isValidLoadout('axis', { cls: 'rifleman', primary: 'mp40', secondary: 'luger' }), 'class mismatch')
  assert.ok(!isValidLoadout('axis', { cls: 'rifleman', primary: 'm1garand', secondary: 'luger' }), 'enemy primary')
  assert.ok(!isValidLoadout('axis', { cls: 'rifleman', primary: 'kar98k', secondary: 'm1911' }), 'enemy sidearm')
  assert.ok(!isValidLoadout('axis', { cls: 'rifleman', primary: 'kar98k', secondary: 'kar98k' }), 'primary as secondary')
  assert.ok(!isValidLoadout('axis', null))
})

test('class ammunition and incremental reloads', () => {
  assert.deepEqual(startingAmmo('support', 'mg42', 'primary'), { mag: 50, reserve: 225 })
  assert.deepEqual(startingAmmo('officer', 'luger', 'secondary'), { mag: 8, reserve: 96 })
  assert.deepEqual(startingAmmo('assault', 'stg44', 'primary'), { mag: 30, reserve: 150 })
  const k = WEAPONS.kar98k
  assert.ok(reloadDuration(k, 4, 40) < reloadDuration(k, 0, 40), 'one round is quicker than a full charger')
  assert.ok(reloadDuration(WEAPONS.kar98k_scoped, 0, 40) > reloadDuration(k, 0, 40), 'scoped rifle loads singly')
  const l = WEAPONS.lee_enfield
  assert.equal(reloadDuration(l, 0, 50), l.reload.open + 2 * l.reload.perClip + l.reload.close)
  assert.equal(reloadDuration(WEAPONS.stg44, 3, 100), 2.4)
})

test('roles: bolt-actions one-shot to the body up close, SMGs fall off fastest', () => {
  for (const id of ['kar98k', 'm1903', 'lee_enfield', 'kar98k_scoped', 'm1903a4']) {
    assert.ok(damageFor(id, 10, 'body') >= 100, id)
  }
  for (const id of ['mp40', 'thompson', 'sten', 'm3']) {
    assert.ok(damageFor(id, 60, 'body') < damageFor('stg44', 60, 'body'), id)
  }
  for (const id of ['mg42', 'm1919a6', 'bren', 'bar']) assert.ok(WEAPONS[id].moveMul < 0.9, `${id} mobility`)
  for (const id of ['mp40', 'thompson', 'sten', 'm3']) assert.ok(WEAPONS[id].moveMul > 1, `${id} mobility`)
})

test('grenade blast: lethal up close, falling off to nothing at the edge', () => {
  assert.equal(blastDamage(0), GRENADE.damage)
  assert.ok(blastDamage(GRENADE.killRadius) >= PLAYER.maxHealth)
  let prev = Infinity
  for (let d = GRENADE.killRadius; d <= GRENADE.blastRadius; d += 0.5) {
    assert.ok(blastDamage(d) <= prev, `falls off at ${d} m`)
    prev = blastDamage(d)
  }
  assert.equal(blastDamage(GRENADE.blastRadius), 0)
  for (const bad of [Infinity, NaN, undefined]) assert.equal(blastDamage(bad), 0, String(bad))
})

test('one knife stab kills', () => {
  assert.ok(KNIFE.damage >= PLAYER.maxHealth)
  for (const team of FACTIONS) assert.ok(KNIFE.name[team], team)
})

test('an ammo can tops each weapon up by a share of its reserve, never past a full load', () => {
  const l = { cls: 'support', primary: 'mg42', secondary: 'luger' }
  const pa = startingAmmo(l.cls, l.primary, 'primary')
  const sa = startingAmmo(l.cls, l.secondary, 'secondary')
  assert.deepEqual(ammoPickup(l, { mg42: pa.mag + pa.reserve, luger: sa.mag + sa.reserve }), {})
  const g = ammoPickup(l, { mg42: 0, luger: sa.mag + sa.reserve - 3 })
  assert.equal(g.mg42, Math.ceil(pa.reserve * AMMO_DROP.share))
  assert.equal(g.luger, 3)
})
