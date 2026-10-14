// Labin Strike client: boot, menu, game loop, combat and networking glue.
import './style.css'
import * as THREE from 'three'
import RAPIER from '@dimforge/rapier3d-compat'
import { PLAYER, INPUT_RATE, INTERP_DELAY, MATCH, TEAMS, KILLCAM, killcamLength } from '@shared/constants.js'
import { WEAPONS, WEAPON_LIST, CLASSES, GRENADE, KNIFE, sanitizeLoadout } from '@shared/weapons.js'
import { MODES, SD, SD_SITES, otherTeam, sdSiteAt } from '@shared/modes.js'
import { parseGlbJson, extractMapData } from '@shared/mapdata.js'
import { buildMapWorld, rayMap, lineOfSight } from '@shared/physics.js'
import { rayVsPlayer, knifeReach, leanShift } from '@shared/hitbox.js'
import { TANK, tankSide, gunRay, wrapAngle } from '@shared/tanks.js'
import { BIKE, bikeSide } from '@shared/bikes.js'
import { createRenderer, createScene, fitSunToBounds, fetchMap, parseMap } from './renderer.js'
import { ShadowCache } from './shadowcache.js'
import { loadCars } from './cars.js'
import { loadCats } from './cats.js'
import { loadTanks } from './tanks.js'
import { loadBikes } from './bikes.js'
import { loadWeaponModels } from './weaponmodels.js'
import { loadSoldierModels } from './soldiermodels.js'
import { Input } from './input.js'
import { LocalPlayer } from './player.js'
import { WeaponSystem } from './weapons.js'
import { Viewmodel } from './viewmodel.js'
import { Avatars } from './avatars.js'
import { Effects } from './effects.js'
import { Grenades } from './grenades.js'
import { Drops } from './drops.js'
import { Bomb } from './bomb.js'
import { Audio } from './audio.js'
import { Hud, weaponLabel } from './hud.js'
import { Net } from './net.js'
import { LoadoutMenu } from './loadout.js'
import { Spectator } from './spectate.js'
import { Killcam } from './killcam.js'

const BASE_FOV = 68
const LEAN_ROLL = 0.18 // camera roll at a full lean, radians
const LEAN_GAP = 0.2 // closest the leaning eye gets to a wall
const $ = (id) => document.getElementById(id)
const params = new URLSearchParams(location.search)

const store = {
  get (k, d) { try { const v = localStorage.getItem(`ls.${k}`); return v == null ? d : v } catch { return d } },
  set (k, v) { try { localStorage.setItem(`ls.${k}`, v) } catch {} }
}

const G = {
  state: 'loading', // loading | menu | connecting | playing
  spectating: false, // joined to watch, on neither side
  myId: 0,
  team: null,
  deployed: false, // confirmed a loadout since joining / switching sides
  loadout: null, // what the server armed us with
  pending: null, // loadout queued for the next spawn
  firstSpawn: true,
  roster: new Map(),
  match: { state: 'playing', scores: { allies: 0, axis: 0 }, winner: null, scoreLimit: MATCH.scoreLimit, timeLeft: MATCH.timeLimit },
  matchEndsLocal: 0,
  killerName: '',
  respawnAt: 0,
  lastSend: 0,
  myPing: 0,
  aliveIds: new Set(),
  fps: 0,
  hits: 0,
  shots: 0,
  nadeSeq: 0,
  cookK: 0, // throw number of the grenade in hand
  cookAt: 0, // when its cord was pulled (performance.now)
  shake: 0, // camera shake from nearby blasts, 0..1
  act: null, // Search and Destroy: { k: 'plant' | 'defuse', at, ms } while the server runs our plant or defuse
  useHeld: false, // last use-key state sent to the server
  driving: null, // the tank we are in (tanks.js state), confirmed by the server
  tankReadyAt: 0, // performance.now() when its gun is loaded
  riding: null, // the motorcycle we are on (bikes.js state), confirmed by the server
  killcam: null, // our death to replay: { killer, at (server ms), roster, w, hs }, until it has played or been skipped
  tps: 0, // server position corrections received
  trace: null // test helper: per-frame [t, camX, camY, camZ]
}

// ------------------------------------------------------------------ setup

const canvas = $('game')
let highQuality = store.get('quality', '1') === '1'
const renderer = createRenderer(canvas, highQuality)
const { scene, sun } = createScene(renderer, highQuality)
const shadowCache = new ShadowCache(renderer, sun)
// near plane 0.1 (player capsule keeps the eye >= 0.35 m from walls): 2x the depth precision of 0.05
const camera = new THREE.PerspectiveCamera(BASE_FOV, window.innerWidth / window.innerHeight, 0.1, 1600)
camera.rotation.order = 'YXZ'
scene.add(camera)

const input = new Input(canvas)
const weapons = new WeaponSystem()
const viewmodel = new Viewmodel()
const avatars = new Avatars(scene)
const effects = new Effects(scene)
const drops = new Drops(scene)
const audio = new Audio()
const bomb = new Bomb(scene, audio)
const hud = new Hud()
const net = new Net()

let world = null
let mapData = null
let player = null
let grenades = null
let cars = null
let cats = null
let tanks = null
let bikes = null
const spec = new Spectator(camera, viewmodel, (o, d, len) => rayMap(RAPIER, world, o, d, len), BASE_FOV)
const killcam = new Killcam({
  scene,
  camera,
  viewmodel,
  ray: (o, d, len) => rayMap(RAPIER, world, o, d, len),
  baseFov: BASE_FOV,
  play: (type, d) => SHOW[type]?.(d, true),
  makeGrenades: () => new Grenades(scene, RAPIER, world)
})
// server ms now (the clock the snapshots are on)
const serverNow = () => avatars.renderTime(0)

function resize () {
  const w = window.innerWidth; const h = window.innerHeight
  renderer.setSize(w, h, false)
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  viewmodel.resize(w / h)
}
window.addEventListener('resize', resize)
resize()

// ------------------------------------------------------------------ menu

const nameInput = $('name-input')
const sensInput = $('sens-input')
const qualityInput = $('quality-input')
const deployBtn = $('btn-deploy')
const watchBtn = $('btn-watch')
const menuStatus = $('menu-status')

nameInput.value = params.get('name') || store.get('name', '')
sensInput.value = store.get('sens', '1')
qualityInput.checked = highQuality
const applySens = () => {
  input.sensitivity = Number(sensInput.value)
  $('sens-val').textContent = Number(sensInput.value).toFixed(2)
}
applySens()
sensInput.addEventListener('input', () => { applySens(); store.set('sens', sensInput.value) })
qualityInput.addEventListener('change', () => {
  highQuality = qualityInput.checked
  store.set('quality', highQuality ? '1' : '0')
  const size = highQuality ? 4096 : 2048
  sun.shadow.mapSize.set(size, size)
  sun.shadow.map?.dispose()
  sun.shadow.map = null
  renderer.shadowMap.type = THREE.PCFShadowMap
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, highQuality ? 2 : 1.25))
  resize()
})
const fullscreenInput = $('fullscreen-input')
fullscreenInput.checked = input.fullscreen = store.get('fullscreen', '0') === '1'
if (navigator.keyboard?.lock) $('fullscreen-hint').textContent = '(Ctrl+W won’t close the tab)'
fullscreenInput.addEventListener('change', () => {
  input.fullscreen = fullscreenInput.checked
  store.set('fullscreen', input.fullscreen ? '1' : '0')
  if (!input.fullscreen) input.exitFullscreen()
})
// side preference on the main menu (the server still balances humans)
let teamPref = ['allies', 'axis'].includes(params.get('team')) ? params.get('team') : store.get('team', 'auto')
const prefButtons = document.querySelectorAll('#team-pref button')
const showPref = () => prefButtons.forEach((b) => b.classList.toggle('sel', b.dataset.team === teamPref))
prefButtons.forEach((b) => b.addEventListener('click', () => { teamPref = b.dataset.team; store.set('team', teamPref); showPref() }))
showPref()

// last loadout chosen for each side (URL params ?cls=&primary=&secondary= override, handy with ?autojoin)
function savedLoadout (team) {
  let l = null
  try { l = JSON.parse(store.get(`loadout.${team}`, 'null')) } catch {}
  if (params.has('cls') || params.has('primary')) {
    l = { cls: params.get('cls') || l?.cls, primary: params.get('primary') || l?.primary, secondary: params.get('secondary') || l?.secondary }
  }
  return l && sanitizeLoadout(team, l)
}

nameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') deploy() })
deployBtn.addEventListener('click', () => deploy())
watchBtn.addEventListener('click', () => deploy(true))
$('pause').addEventListener('click', () => { if (G.state === 'playing') input.lock() })
$('btn-loadout').addEventListener('click', (e) => { e.stopPropagation(); openLoadout() })
$('btn-leave').addEventListener('click', (e) => { e.stopPropagation(); leave('Left the match') })
$('btn-bots').addEventListener('click', (e) => { e.stopPropagation(); net.emit('bots', { on: !G.match.bots }, true) })
$('btn-tanks').addEventListener('click', (e) => { e.stopPropagation(); net.emit('tanks', { on: !G.match.tanks }, true) })
$('btn-mode').addEventListener('click', (e) => { e.stopPropagation(); net.emit('mode', { mode: G.match.mode === 'sd' ? 'tdm' : 'sd' }, true) })
// from the field to the stands and back; the click also takes the pointer for the spectator camera
$('btn-spectate').addEventListener('click', () => net.emit('spectate', {}, true))
for (const team of ['allies', 'axis']) {
  $(`btn-join-${team}`).addEventListener('click', (e) => { e.stopPropagation(); net.emit('team', { team }, true) })
}
canvas.addEventListener('click', () => { if (G.state === 'playing' && !input.locked) input.lock() })

function setStatus (text, error = false) {
  menuStatus.textContent = text
  menuStatus.classList.toggle('error', error)
}

function showMenu (v) {
  $('menu').classList.toggle('hidden', !v)
  hud.show(!v)
}

// spectate: join to watch, on neither side
async function deploy (spectate = false) {
  if (G.state !== 'menu') return
  const name = nameInput.value.trim() || `Soldier${Math.floor(Math.random() * 900 + 100)}`
  store.set('name', name)
  audio.unlock()
  input.enterFullscreen()
  G.state = 'connecting'
  deployBtn.disabled = watchBtn.disabled = true
  ;(spectate ? watchBtn : deployBtn).textContent = 'Connecting…'
  setStatus('Establishing UDP channel…')
  try {
    await net.connect()
  } catch (err) {
    console.warn('connect failed', err)
    G.state = 'menu'
    menuReady()
    setStatus(err?.message || 'Could not connect to the server', true)
    return
  }
  setStatus('Joining match…')
  if (spectate) { net.emit('join', { name, spectate: true }, true); return }
  const team = teamPref === 'auto' ? undefined : teamPref
  net.emit('join', { name, team, loadout: savedLoadout(team || store.get('lastTeam', 'allies')) }, true)
}

function menuReady () {
  deployBtn.disabled = watchBtn.disabled = false
  deployBtn.textContent = 'Deploy'
  watchBtn.textContent = 'Spectate'
}

function setPauseMode () {
  $('pause').classList.toggle('spectator', G.spectating)
  $('pause-title').textContent = G.spectating ? 'Spectating' : 'Paused'
  $('pause-text').textContent = G.spectating ? 'Click to keep watching' : 'Click to return to the fight'
}

// ------------------------------------------------------------------ loadout

const loadoutMenu = new LoadoutMenu({
  onDeploy: (l) => requestLoadout(l),
  onTeam: (team) => { loadoutMenu.status('Switching sides…'); net.emit('team', { team }, true) },
  onClose: () => closeLoadout()
})

const loadoutLabel = (l) => `${CLASSES[l.cls].name} · ${WEAPONS[l.primary].name} · ${WEAPONS[l.secondary].name}`
const sameLoadout = (a, b) => a && b && a.cls === b.cls && a.primary === b.primary && a.secondary === b.secondary

function openLoadout () {
  if (G.state !== 'playing' || loadoutMenu.isOpen || G.spectating) return
  const cur = G.pending || G.loadout
  if (G.deployed) loadoutMenu.open(G.team, cur, 'change', cur)
  else loadoutMenu.open(G.team, savedLoadout(G.team) || G.loadout, 'deploy')
  input.mouse.left = input.mouse.right = false
  hud.pause(false)
  input.unlock()
}

function closeLoadout () {
  if (!loadoutMenu.isOpen || !G.deployed) return // the first spawn needs a loadout
  loadoutMenu.close()
  input.lock()
}

function requestLoadout (l) {
  store.set(`loadout.${G.team}`, JSON.stringify(l))
  const deploying = !G.deployed
  if (!deploying && sameLoadout(l, G.pending || G.loadout)) { closeLoadout(); return }
  net.emit('loadout', { ...l, deploy: deploying }, true)
  if (deploying) {
    G.deployed = true
    hud.show(true)
    hud.center(`DEPLOYING<small>${loadoutLabel(l)}</small>`, MATCH.respawnDelay + 0.5)
  }
  loadoutMenu.close()
  input.lock()
}

function applyLoadout (l) {
  G.loadout = l
  G.pending = null
  weapons.reset(l)
  viewmodel.prepare([l.primary, l.secondary])
}

function leave (msg) {
  loadoutMenu.close()
  hud.scope(false)
  G.deployed = false
  G.spectating = false
  spec.reset()
  endKillcam()
  killcam.clear()
  hud.spectate(null)
  setPauseMode()
  net.close()
  input.unlock()
  input.exitFullscreen()
  input.enabled = false
  G.state = 'menu'
  G.myId = 0
  if (player) player.alive = false
  avatars.clear()
  cats?.clear()
  stopDriving()
  tanks?.clear()
  bikes?.clear()
  grenades?.clear()
  drops.clear()
  bomb.remove()
  G.act = null
  G.useHeld = false
  G.roster.clear()
  showMenu(true)
  hud.pause(false)
  menuReady()
  setStatus(msg || '')
}

// browsers never let a page cancel Ctrl+W, but they do ask before closing a tab mid-match
// (Ctrl is crouch, so the combo is one stray finger away)
window.addEventListener('beforeunload', (e) => {
  if (G.state !== 'playing') return
  e.preventDefault()
  e.returnValue = ''
})

input.onLockChange = (locked, error) => {
  if (G.state !== 'playing' || loadoutMenu.isOpen) return
  hud.pause(!locked && !error)
  if (error) hud.notice('Pointer lock unavailable – click the game to retry')
}

// ------------------------------------------------------------------ networking

net.onDisconnect = () => { if (G.state === 'playing' || G.state === 'connecting') leave('Disconnected from server') }

// on joining, and on going from playing to spectating or back (same id, new side)
net.on('welcome', (d) => {
  G.myId = d.id
  G.spectating = !!d.spectator
  G.team = d.team ?? null
  G.loadout = d.loadout ?? null
  G.pending = null
  G.deployed = false
  G.firstSpawn = true
  if (d.team) store.set('lastTeam', d.team)
  if (player) { player.life = 0; player.alive = false; player.deathPos = null }
  stopDriving()
  endKillcam()
  avatars.clear() // name tags and friend / foe depend on our side, or having none
  spec.reset()
  setRoster(d.roster, d.match)
  drops.clear()
  for (const dr of d.drops || []) drops.add(dr)
  hud.setTeam(d.team)
  hud.scope(false)
  hud.death(false)
  setPauseMode()
  G.state = 'playing'
  input.enabled = true
  showMenu(false)
  setStatus('')
  if (G.spectating) {
    loadoutMenu.close()
    hud.show(true)
    input.lock()
    if (!input.locked) hud.pause(true)
    return
  }
  hud.spectate(null)
  viewmodel.setTeam(d.team)
  hud.show(false) // until deployed
  if (params.has('autojoin')) requestLoadout(savedLoadout(d.team) || d.loadout)
  else openLoadout()
})

net.on('spawn', (d) => onSpawn(d))

function onSpawn (d) {
  if (!player || d.life <= player.life) return
  endKillcam()
  player.spawn(d.pos, d.yaw, d.life)
  player.deathPos = null
  stopDriving()
  G.act = null
  applyLoadout(d.loadout)
  G.deployed = true
  G.killerName = ''
  hud.death(false)
  hud.show(true)
  // pointer lock can be refused (no recent click): ask for one, as on joining before
  if (!input.locked && !loadoutMenu.isOpen) hud.pause(true)
  if (G.firstSpawn) {
    G.firstSpawn = false
    hud.center(`${TEAMS[G.team].name.toUpperCase()}<small>Team Deathmatch · first to ${G.match.scoreLimit}</small>`, 3)
  }
}

net.on('loadout', (d) => {
  if (d.applied === 'rejected') {
    G.deployed = G.deployed && !!player?.alive
    openLoadout()
    loadoutMenu.status('That loadout is not available to your side', true)
  } else if (d.applied === 'now') {
    if (player?.alive && d.life === player.life) applyLoadout(d.loadout)
    hud.notice(`Loadout changed: ${loadoutLabel(d.loadout)}`)
  } else if (d.applied === 'next') {
    G.pending = d.loadout
    hud.notice(`Next spawn: ${loadoutLabel(d.loadout)}`)
  } else {
    G.loadout = d.loadout
  }
})

net.on('team', (d) => {
  if (d.denied) {
    if (loadoutMenu.isOpen) loadoutMenu.status(d.denied, true)
    else hud.notice(d.denied)
    return
  }
  G.team = d.team
  G.loadout = d.loadout
  G.pending = null
  G.deployed = false
  G.firstSpawn = true
  store.set('lastTeam', d.team)
  if (player) { player.alive = false; player.deathPos = null }
  stopDriving()
  endKillcam()
  input.mouse.left = false
  avatars.clear() // everyone's friend / foe status flipped
  viewmodel.setTeam(d.team)
  hud.setTeam(d.team)
  hud.show(false)
  hud.scope(false)
  loadoutMenu.close()
  openLoadout()
  loadoutMenu.status(`You are now with the ${TEAMS[d.team].name}`)
})

net.on('tp', (d) => {
  G.tps++
  if (!player || d.life !== player.life) return
  const v = G.driving || G.riding
  if (v) {
    v.body.setPose(d.pos[0], d.pos[1], d.pos[2], d.yaw ?? v.body.yaw)
    v.body.stop()
  } else player.teleport(d.pos)
})

// the server puts us in a tank ({ id, pos, yaw, turret, gun, ready: ms until loaded }) or back on foot ({ id: 0, pos })
net.on('drive', (d) => {
  if (!player || d.life !== player.life || !tanks) return
  if (!d.id) {
    stopDriving()
    if (player.alive) player.teleport(d.pos)
    return
  }
  const s = tanks.get(d.id)
  if (!s) return
  s.body.setPose(d.pos[0], d.pos[1], d.pos[2], d.yaw)
  s.body.stop()
  s.turret = d.turret
  s.gun = d.gun
  tanks.mine = G.driving = s
  G.tankReadyAt = performance.now() + d.ready
  input.mouse.left = false
  hud.scope(false)
})

// the server puts us on a motorcycle ({ id, pos, yaw }) or back on foot ({ id: 0, pos })
net.on('ride', (d) => {
  if (!player || d.life !== player.life || !bikes) return
  if (!d.id) {
    stopDriving()
    if (player.alive) player.teleport(d.pos)
    return
  }
  const s = bikes.get(d.id)
  if (!s) return
  s.body.setPose(d.pos[0], d.pos[1], d.pos[2], d.yaw)
  s.body.stop()
  bikes.mine = G.riding = s
  player.yaw = d.yaw
  player.pitch = -0.15
  input.mouse.left = false
  hud.scope(false)
})

function stopDriving () {
  if (tanks) tanks.mine = null
  if (bikes) bikes.mine = null
  G.driving = G.riding = null
  audio.engine(0)
  audio.bikeEngine(0)
}

net.on('snap', (s) => {
  if (G.state !== 'playing') return
  avatars.onSnapshot(s, G.myId, G.roster, G.team)
  killcam.snapshot(s)
  cats?.onSnapshot(s.t, s.c)
  tanks?.onSnapshot(s.t, s.k)
  bikes?.onSnapshot(s.t, s.b)
  G.aliveIds.clear()
  for (const e of s.p) {
    if (e[6] & 1) G.aliveIds.add(e[0])
    if (e[0] === G.myId && player) {
      if (player.alive && e[9] === player.life) player.hp = e[8]
    }
  }
})

net.on('roster', (d) => setRoster(d.players, d.match))

function setRoster (players, match) {
  G.roster.clear()
  for (const p of players) G.roster.set(p.id, p)
  const me = G.roster.get(G.myId)
  if (me) G.myPing = me.ping
  const prev = G.match
  G.match = match
  $('btn-bots').textContent = `Bots: ${match.bots ? 'on' : 'off'}`
  $('btn-tanks').textContent = `Tanks: ${match.tanks ? 'on' : 'off'}`
  $('btn-mode').textContent = `Mode: ${MODES[match.mode].short}`
  G.matchEndsLocal = performance.now() + (match.msLeft ?? match.timeLeft * 1000)
  if (match.bomb) bomb.place(match.bomb.p, match.roundState === 'live' ? match.msLeft : null)
  else bomb.remove()
  if (prev.state === 'playing' && match.state === 'ended') {
    const txt = match.winner === 'draw' ? 'DRAW' : !G.team ? `${TEAMS[match.winner].name.toUpperCase()} WIN` : match.winner === G.team ? 'VICTORY' : 'DEFEAT'
    const sub = match.winner === 'draw' ? 'The match ended in a draw' : `${TEAMS[match.winner]?.name} win ${match.scores.allies} – ${match.scores.axis}`
    hud.center(`${txt}<small>${sub} · next ${match.mode === 'sd' ? 'match' : 'round'} in ${match.timeLeft}s</small>`, MATCH.intermission)
  } else if (match.mode === 'sd' && match.state === 'playing') {
    if (match.roundState === 'live' && (match.round !== prev.round || prev.mode !== 'sd')) {
      const task = !G.team ? `The ${TEAMS[match.attackers].name} attack` : match.attackers === G.team ? 'Attack: plant the bomb at site A or B' : 'Defend sites A and B'
      hud.center(`ROUND ${match.round}<small>${task}</small>`, 3.5)
    } else if (match.roundState === 'over' && prev.roundState === 'live') {
      const loser = otherTeam(match.roundWinner)
      const why = { eliminated: `The ${TEAMS[loser].name} were wiped out`, time: 'Time ran out', bomb: 'The bomb went off', defused: 'The bomb was defused' }[match.reason]
      const result = !G.team ? `${TEAMS[match.roundWinner].name.toUpperCase()} WIN THE ROUND` : match.roundWinner === G.team ? 'ROUND WON' : 'ROUND LOST'
      hud.center(`${result}<small>${why} · ${match.scores.allies} – ${match.scores.axis}</small>`, SD.roundOver)
    }
  }
}

net.on('act', (d) => { G.act = d.k ? { k: d.k, at: performance.now(), ms: d.ms } : null })

net.on('bomb', (d) => {
  if (G.state !== 'playing') return
  if (d.e === 'plant') {
    bomb.place(d.p, d.ms)
    audio.click(900, 0.4, 0.08)
  } else if (d.e === 'defuse') {
    bomb.remove()
    audio.click(2400, 0.35, 0.05)
    audio.click(1600, 0.35, 0.06, 0.1)
  } else if (d.e === 'boom') {
    bomb.remove()
    const pos = new THREE.Vector3(...d.p)
    const scorch = scorchBelow(pos)
    for (let i = 0; i < 3; i++) {
      const at = pos.clone().add(new THREE.Vector3((Math.random() - 0.5) * 3, 0.2 + i * 0.6, (Math.random() - 0.5) * 3))
      effects.explosion(at, i === 0 ? scorch : null)
    }
    const dist = pos.distanceTo(earPos())
    audio.explosion(pos, dist)
    if (player.alive) G.shake = Math.max(G.shake, Math.max(0, 1 - dist / 50) ** 2)
  }
})

// scorch mark for a blast at pos, if there is ground close below it
function scorchBelow (pos) {
  const below = rayMap(RAPIER, world, [pos.x, pos.y + 0.2, pos.z], [0, -1, 0], 0.8)
  return below && below.normal[1] > 0.5 ? { point: new THREE.Vector3(pos.x, pos.y + 0.2 - below.dist, pos.z), normal: below.normal } : null
}

// what the server tells everyone happened, shown live or (past) again by the kill-cam, on its own soldiers and
// grenades: no shaking our camera, and no second bullet hole or scorch mark where the first one already is
const SHOW = {
  // a tank gun: the shooter's client already showed its own muzzle blast
  shell (d, past) {
    const s = tanks?.get(d.id)
    const o = new THREE.Vector3(...d.o)
    const e = new THREE.Vector3(...d.e)
    const dir = e.clone().sub(o).normalize()
    const muzzle = o.clone().addScaledVector(dir, s ? tankSide(s.team).barrel : 2)
    const ear = camera.position
    if (s && (past || s !== G.driving)) {
      s.firedAt = performance.now()
      effects.gunBlast(muzzle, dir)
      audio.cannon(muzzle, muzzle.distanceTo(ear))
    }
    effects.tracer(muzzle, e, 900)
    effects.explosion(e.clone().addScaledVector(dir, -0.3), past ? null : scorchBelow(e))
    const dist = e.distanceTo(ear)
    audio.explosion(e, dist)
    if (!past && player.alive) G.shake = Math.max(G.shake, Math.max(0, 1 - dist / 35) ** 2)
  },

  bikeboom (d, past) {
    const pos = new THREE.Vector3(...d.p)
    for (let i = 0; i < 2; i++) effects.explosion(pos.clone().add(new THREE.Vector3((Math.random() - 0.5) * 1.2, 0.4 + i * 0.5, (Math.random() - 0.5) * 1.6)), null)
    const dist = pos.distanceTo(camera.position)
    audio.explosion(pos, dist)
    if (!past && player.alive) G.shake = Math.max(G.shake, Math.max(0, 1 - dist / 30) ** 2)
  },

  tankboom (d, past) {
    const pos = new THREE.Vector3(...d.p)
    for (let i = 0; i < 4; i++) {
      effects.explosion(pos.clone().add(new THREE.Vector3((Math.random() - 0.5) * 3, 0.6 + i * 0.5, (Math.random() - 0.5) * 4)), null)
    }
    const dist = pos.distanceTo(camera.position)
    audio.explosion(pos, dist)
    if (!past && player.alive) G.shake = Math.max(G.shake, Math.max(0, 1 - dist / 50) ** 2)
  },

  shot (d, past) {
    const a = (past ? killcam.ghosts : avatars).map.get(d.id)
    a?.showFlash()
    const o = new THREE.Vector3(...d.o)
    const e = new THREE.Vector3(...d.e)
    const len = o.distanceTo(e)
    const dir = e.clone().sub(o).divideScalar(len || 1)
    let from = o.clone().addScaledVector(dir, 0.8)
    if (!past) spec.onShot(d.id)
    else if (killcam.onShot(d.id)) {
      // through the killer's eyes: out of the muzzle of the rifle in their hands
      viewmodel.muzzleWorld(camera, muzzle)
      from = muzzle.clone()
      effects.muzzle(muzzle)
    }
    audio.shot(d.w, o, o.distanceTo(earPos()))
    effects.tracer(from, e, tracerSpeed(d.w) * 0.72)
    // the replay knows where everyone stood: blood where the bullet stopped in someone
    if (past && len > 0.5) {
      for (const g of killcam.ghosts.map.values()) {
        if (g.id === d.id || !g.exposed) continue
        const h = rayVsPlayer(d.o, [dir.x, dir.y, dir.z], len + 0.3, g.pos.x, g.pos.y, g.pos.z, g.crouched, leanShift(g.yaw, g.lean))
        if (h && Math.abs(h.t - len) < 0.6) { effects.blood(e, dir.clone().negate()); return }
      }
    }
    // impact where the bullet stopped (if it stopped on map geometry)
    if (len > 0.5 && d.n !== 0) {
      const h = rayMap(RAPIER, world, d.o, [dir.x, dir.y, dir.z], len + 0.3)
      if (h && Math.abs(h.dist - len) < 0.6) effects.impact(o.clone().addScaledVector(dir, h.dist), h.normal, 'world', !past)
    }
    // bullet passing close by
    if (!past && player.alive && a && a.team !== G.team) {
      const myEye = player.eyePos(new THREE.Vector3())
      const seg = e.clone().sub(o)
      const t = THREE.MathUtils.clamp(myEye.clone().sub(o).dot(seg) / seg.lengthSq(), 0, 1)
      const closest = o.clone().addScaledVector(seg, t)
      if (closest.distanceTo(myEye) < 1.6 && t > 0.05 && t < 0.98) audio.whiz(closest)
    }
  },

  // our own throws are never echoed back, but a cooked grenade we dropped or held too long is
  nade (d, past) {
    (past ? killcam.grenades : grenades).spawn(`${d.id}:${d.k}`, d.o, d.d, d.f)
    if (!d.d) return
    if (past) killcam.onNade(d.id)
    else spec.onNade(d.id)
  },

  boom (d, past) {
    (past ? killcam.grenades : grenades).remove(`${d.id}:${d.k}`)
    const pos = new THREE.Vector3(...d.p)
    effects.explosion(pos.clone().setY(pos.y + 0.15), past ? null : scorchBelow(pos))
    const dist = pos.distanceTo(earPos())
    audio.explosion(pos, dist)
    if (!past && player.alive) G.shake = Math.max(G.shake, Math.max(0, 1 - dist / 30) ** 2)
  },

  stab (d, past) {
    const a = (past ? killcam.ghosts : avatars).map.get(d.id)
    if (!a?.alive) return
    a.stab()
    if (past) killcam.onStab(d.id)
    else spec.onStab(d.id)
    audio.knifeSwing(a.pos.clone().setY(a.pos.y + 1.2))
  }
}

// while the kill-cam plays, the present goes on unseen and unheard: only what must still be right afterwards
const KEEP = {
  nade: (d) => grenades.spawn(`${d.id}:${d.k}`, d.o, d.d, d.f),
  boom: (d) => grenades.remove(`${d.id}:${d.k}`)
}

for (const type of Object.keys(SHOW)) {
  net.on(type, (d) => {
    if (G.state !== 'playing' || (type === 'shot' && d.id === G.myId)) return
    killcam.record(type, d, serverNow())
    if (!killcam.active) SHOW[type](d, false)
    else KEEP[type]?.(d)
  })
}

net.on('drop', (d) => { if (G.state === 'playing') drops.add(d, serverNow()) })
net.on('undrop', (d) => drops.remove(d.i))

net.on('ammo', (d) => {
  if (!player?.alive || d.life !== player.life) return
  weapons.addAmmo(d.a)
  hud.pickup(d.a)
  audio.pickup()
})

net.on('dmg', (d) => {
  if (!player) return
  player.hp = d.hp
  const from = d.from
  const dx = from[0] - player.pos.x; const dz = from[2] - player.pos.z
  // angle of attacker relative to view direction, clockwise from screen-up
  const ang = Math.atan2(-dx, -dz) - player.yaw
  hud.damageFlash(-ang)
  audio.hurt()
  const t = G.roster.get(d.a)
  if (t) G.killerName = t.name
})

net.on('hit', (d) => {
  G.hits++
  hud.hit(d.k)
  audio.hitmarker(d.k)
})

net.on('kill', (d) => {
  killcam.record('kill', d, serverNow())
  const killer = G.roster.get(d.k)
  const victim = G.roster.get(d.v)
  hud.killfeed(killer, victim, d.w, d.hs, G.myId)
  if (d.v === G.myId && player) {
    // killed in a tank or on a bike: the death camera starts from the chase camera
    player.deathPos = G.driving || G.riding ? camera.position.clone() : player.eyePos(new THREE.Vector3())
    stopDriving()
    player.alive = false
    player.hp = 0
    player.deathAt = performance.now()
    G.killerName = killer && killer.id !== G.myId ? killer.name : ''
    // at an enemy's hands: the kill-cam, after which the server respawns us (or as soon as we skip it)
    endKillcam()
    G.killcam = killer && killer.id !== G.myId && killer.team !== G.team && G.match.state === 'playing'
      ? { killer: killer.id, at: serverNow(), roster: new Map(G.roster), w: d.w, hs: d.hs }
      : null
    if (!G.killcam) net.emit('skip', {}, true)
    G.respawnAt = player.deathAt + (G.killcam ? killcamLength() : MATCH.respawnDelay) * 1000
    input.mouse.left = false
    G.act = null
  } else if (d.k === G.myId && victim) {
    hud.center(`<small>You killed ${escapeHtml(victim.name)}${d.hs ? ' · headshot' : ''}</small>`, 1.6)
    if (d.hs) audio.headshot()
  }
  const a = avatars.map.get(d.v)
  if (a) a.killedLife = a.life // drop immediately instead of waiting for the interpolation delay
})

net.on('ping', (d) => net.emit('pong', { t: d.t }))
net.on('notice', (d) => hud.notice(d.m))
net.on('chat', (d) => {
  const p = G.roster.get(d.id)
  hud.notice(`${p ? p.name : '?'}: ${d.m}`)
})

function escapeHtml (s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}

// ------------------------------------------------------------------ combat

// hits are hitscan; muzzle velocity only shapes how fast the tracer streaks
const tracerSpeed = (id) => 150 + (WEAPONS[id]?.velocity ?? 685) * 0.4

const tmpV = new THREE.Vector3()
const tmpO = new THREE.Vector3()
const tmpEar = new THREE.Vector3()

// where we hear the world from: our own head, or the camera when watching
const earPos = () => player?.alive ? player.eyePos(tmpEar) : camera.position
const muzzle = new THREE.Vector3()

// random direction inside a cone of half-angle `spread` around forward
function coneDir (fwd, spread) {
  const up = Math.abs(fwd.y) < 0.99 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0)
  const right = new THREE.Vector3().crossVectors(fwd, up).normalize()
  const up2 = new THREE.Vector3().crossVectors(right, fwd)
  const r = spread * Math.sqrt(Math.random())
  const a = Math.random() * Math.PI * 2
  return fwd.clone().addScaledVector(right, Math.cos(a) * Math.tan(r)).addScaledVector(up2, Math.sin(a) * Math.tan(r)).normalize()
}

// nearest player hit along the ray (alive enemies + friendlies, which block but deal no damage)
function rayPlayers (o, d, maxT) {
  let best = null
  for (const a of avatars.map.values()) {
    if (!a.exposed) continue
    const h = rayVsPlayer(o, d, maxT, a.pos.x, a.pos.y, a.pos.z, a.crouched, leanShift(a.yaw, a.lean))
    if (h && (!best || h.t < best.t)) best = { ...h, avatar: a }
  }
  return best
}

function fireShot (spread) {
  G.shots++
  const w = weapons.def
  const fwd = new THREE.Vector3()
  camera.getWorldDirection(fwd)
  const dir = coneDir(fwd, spread)
  camera.getWorldPosition(tmpO)
  const o = [tmpO.x, tmpO.y, tmpO.z]
  const d = [dir.x, dir.y, dir.z]
  const mh = rayMap(RAPIER, world, o, d, w.range)
  let maxT = mh ? mh.dist : w.range
  const th = tanks?.ray(o, d, maxT)
  if (th) maxT = th.t
  const bh = bikes?.ray(o, d, maxT)
  if (bh) maxT = bh.t
  const ph = rayPlayers(o, d, maxT)
  const t = ph ? ph.t : maxT
  const end = tmpO.clone().addScaledVector(dir, t)
  viewmodel.muzzleWorld(camera, muzzle)
  if (Math.random() < 0.6) effects.tracer(muzzle, end, tracerSpeed(w.id))
  effects.muzzle(muzzle)
  if (ph) {
    effects.blood(end, dir.clone().negate())
  } else if (bh || th) {
    effects.sparks(end, [-dir.x, -dir.y, -dir.z])
  } else if (mh) {
    effects.impact(end, mh.normal)
  }
  const msg = { w: weapons.id, o: o.map(r2), e: [r2(end.x), r2(end.y), r2(end.z)] }
  if (ph && ph.avatar.team !== G.team) msg.hit = { id: ph.avatar.id, zone: ph.zone }
  else if (!ph && bh) { if (bh.bike.team !== G.team) msg.hit = { bike: bh.bike.id } }
  else if (!ph && th && th.tank.team !== G.team) msg.hit = { tank: th.tank.id }
  net.emit('fire', msg)
  recordOwn('shot', { id: G.myId, w: msg.w, o: msg.o, e: msg.e })
}

// our own shots, throws and stabs are not echoed back: the kill-cam keeps them itself, on the timeline our position
// reaches the snapshots on (stamped when the server got it, about a round trip later than our clock says now)
function recordOwn (type, d) { killcam.record(type, d, serverNow() + G.myPing) }
const r2 = (v) => Math.round(v * 100) / 100
const r3 = (v) => Math.round(v * 1000) / 1000

// rounded and normalised exactly as the server does, so this visual follows the server's flight
function throwGrenade () {
  if (!player.alive) return
  camera.getWorldPosition(tmpO)
  camera.getWorldDirection(tmpV)
  const o = [tmpO.x, tmpO.y, tmpO.z].map(r3)
  const d0 = [tmpV.x, tmpV.y, tmpV.z].map(r3)
  const len = Math.hypot(...d0)
  const d = d0.map((v) => r3(v / len))
  const k = G.cookK
  grenades.spawn(`${G.myId}:${k}`, o, d, GRENADE.fuse * 1000 - (performance.now() - G.cookAt))
  net.emit('nade', { o, d, k }, true)
  recordOwn('nade', { id: G.myId, k, o, d, f: GRENADE.fuse * 1000 - (performance.now() - G.cookAt) })
  audio.nadeThrow()
}

// the client picks who the blade reaches; the server re-checks reach, angle and line of sight
function knifeStrike () {
  if (!player.alive) return
  camera.getWorldPosition(tmpO)
  camera.getWorldDirection(tmpV)
  const o = [tmpO.x, tmpO.y, tmpO.z]
  const d = [tmpV.x, tmpV.y, tmpV.z]
  let best = null
  for (const a of avatars.map.values()) {
    if (!a.exposed || a.team === G.team) continue
    const r = knifeReach(o, d, a.pos.x, a.pos.y, a.pos.z, a.crouched)
    if (r.dist > KNIFE.range || r.angle > KNIFE.cone || (best && r.dist >= best.r.dist)) continue
    if (lineOfSight(RAPIER, world, o, r.at)) best = { a, r }
  }
  const msg = { o: o.map(r2), d: d.map(r3) }
  if (best) {
    msg.hit = best.a.id
    const at = new THREE.Vector3(...best.r.at)
    const back = tmpO.clone().sub(at).setY(0).normalize()
    effects.blood(at.addScaledVector(back, PLAYER.radius), back)
    audio.knifeHit()
  }
  net.emit('knife', msg, true)
  recordOwn('stab', { id: G.myId })
}

// what's under the crosshair (for name display / crosshair colour)
function crosshairTarget () {
  camera.getWorldPosition(tmpO)
  camera.getWorldDirection(tmpV)
  const o = [tmpO.x, tmpO.y, tmpO.z]
  const d = [tmpV.x, tmpV.y, tmpV.z]
  const mh = rayMap(RAPIER, world, o, d, 150)
  let maxT = mh ? mh.dist : 150
  const th = tanks?.ray(o, d, maxT, G.driving)
  if (th) maxT = th.t
  const bh = bikes?.ray(o, d, maxT, G.riding)
  if (bh) maxT = bh.t
  const ph = rayPlayers(o, d, maxT)
  if (ph) return { name: ph.avatar.name, friendly: ph.avatar.team === G.team }
  if (bh) return { name: bikeSide(bh.bike.team).name, friendly: bh.bike.team === G.team }
  if (th) return { name: tankSide(th.tank.team).name, friendly: th.tank.team === G.team }
  return null
}

// ------------------------------------------------------------------ boot

async function boot () {
  const fill = $('loading-fill'); const text = $('loading-text')
  const progress = (p, label) => { fill.style.width = `${Math.round(p * 100)}%`; if (label) text.textContent = label }
  try {
    progress(0.05, 'Initialising physics…')
    const weaponModels = loadWeaponModels('/assets/weapons/weapons.glb')
      .catch((err) => console.warn('weapon models unavailable, using procedural ones', err))
    const soldierModels = loadSoldierModels('/assets/soldiers/soldiers.glb')
      .catch((err) => console.warn('soldier models unavailable, using procedural ones', err))
    await RAPIER.init()
    progress(0.1, 'Loading map…')
    const buffer = await fetchMap('/assets/maps/parking_lot.glb', (p) => progress(0.1 + p * 0.75))
    mapData = extractMapData(parseGlbJson(buffer))
    world = buildMapWorld(RAPIER, mapData)
    progress(0.88, 'Building scene…')
    const mapRoot = await parseMap(buffer, renderer)
    scene.add(mapRoot)
    if (mapRoot.userData.cars.length) {
      progress(0.92, 'Parking cars…')
      cars = await loadCars('/assets/cars/cars.glb', mapRoot.userData.cars, renderer)
      scene.add(cars)
    }
    progress(0.95, 'Letting the cats out…')
    cats = await loadCats('/assets/cats/cats.glb', scene, audio)
    progress(0.97, 'Fuelling the tanks…')
    tanks = await loadTanks(scene, RAPIER, world)
    progress(0.99, 'Arming…')
    await weaponModels // before anything builds a weapon, grenade or knife
    await soldierModels // before any soldier, rider or first-person arm
    bikes = await loadBikes('/assets/bikes/bikes.glb', scene, RAPIER, world) // its riders are soldiers, who carry a weapon
    fitSunToBounds(sun, mapData.bounds)
    // the map and the parked cars never move: their shadows are rendered once
    shadowCache.addStatic(mapRoot, ...(cars ? [cars] : []))
    shadowCache.onBake = () => cars?.cull(null)
    player = new LocalPlayer(RAPIER, world)
    grenades = new Grenades(scene, RAPIER, world)
    hud.buildMinimap(mapData)
    viewmodel.setTeam('allies')
    // warm up shaders so the first frame in-game does not hitch
    renderer.compile(scene, camera)
    progress(1, 'Ready')
    $('loading').classList.add('hidden')
    G.state = 'menu'
    menuReady()
    if (params.has('autojoin')) deploy(params.has('spectate'))
  } catch (err) {
    console.error(err)
    text.textContent = `Failed to load: ${err.message || err}`
  }
}

// ------------------------------------------------------------------ loop

let lastT = performance.now()
let frames = 0; let fpsT = 0
let menuOrbit = 0
let lookDX = 0; let lookDY = 0
let fovCurrent = BASE_FOV
let deathRoll = 0

function frame () {
  requestAnimationFrame(frame)
  const now = performance.now()
  const dt = Math.min(0.05, (now - lastT) / 1000)
  lastT = now
  frames++; fpsT += dt
  if (fpsT >= 0.5) { G.fps = Math.round(frames / fpsT); frames = 0; fpsT = 0 }

  if (G.state === 'playing') {
    if (input.wasPressed('KeyB')) { if (loadoutMenu.isOpen) closeLoadout(); else openLoadout() }
    if (input.wasPressed('Escape')) closeLoadout()
  }
  spec.firstPerson = false
  if (G.state === 'playing' && G.spectating) updateSpectating(dt, now)
  else if (G.state === 'playing' && player && G.deployed) updateGame(dt, now)
  else {
    updateMenuCamera(dt)
    if (G.state === 'playing') avatars.update(dt, INTERP_DELAY)
  }

  // the kill-cam poses the tanks, bikes and cats as they were, and slows the world down around the kill
  const past = killcam.active
  const wdt = dt * killcam.scale
  effects.update(wdt)
  drops.update(past ? killcam.time : null)
  bomb.update()
  if (G.state === 'playing') {
    const t = past ? killcam.time : avatars.renderTime(INTERP_DELAY)
    cats?.update(wdt, t, camera.position)
    tanks?.update(wdt, t, (pos) => effects.smoke(pos), past)
    bikes?.update(wdt, t, (pos) => effects.smoke(pos), past)
  }
  grenades?.update(dt, (pos, impact) => audio.nadeBounce(pos, Math.min(1, impact / 10)))
  camera.updateMatrixWorld()
  if (camOverride && G.state === 'playing') { camera.position.set(...camOverride.pos); camera.lookAt(...camOverride.look) }
  cars?.cull(camera)
  renderer.clear()
  renderer.render(scene, camera)
  if (G.state === 'playing' && ((player?.alive && !G.driving && !G.riding) || spec.firstPerson || killcam.firstPerson)) viewmodel.render(renderer, 58 - (BASE_FOV - fovCurrent) * 0.25, scene, camera)
  if (G.trace) G.trace.push([now, camera.position.x, camera.position.y, camera.position.z])
  input.endFrame()
}

let camOverride = null   // test helper (window.__labin.cam): fixed camera, in the menu or in game

function updateMenuCamera (dt) {
  if (!mapData) return
  if (camOverride) {
    camera.position.set(...camOverride.pos)
    camera.lookAt(...camOverride.look)
    return
  }
  menuOrbit += dt * 0.04
  const b = mapData.bounds
  const cx = (b.min[0] + b.max[0]) / 2; const cz = (b.min[2] + b.max[2]) / 2
  camera.position.set(cx + Math.cos(menuOrbit) * 40, 16, cz + Math.sin(menuOrbit) * 26)
  camera.lookAt(cx, 1, cz)
  if (camera.fov !== BASE_FOV) { camera.fov = BASE_FOV; camera.updateProjectionMatrix() }
}

function updateGame (dt, now) {
  const locked = input.locked
  // look
  const [ldx, ldy] = input.consumeLook()
  const fovScale = fovCurrent / BASE_FOV
  lookDX = ldx * fovScale; lookDY = ldy * fovScale
  if (player.alive) player.look(lookDX, lookDY)

  const canAct = player.alive && locked && G.match.state === 'playing' && !loadoutMenu.isOpen
  const sd = G.match.mode === 'sd'
  // remote players (before the camera, which may be following one of them)
  avatars.update(dt, INTERP_DELAY)
  const replaying = updateKillcam(dt, now)
  // Search and Destroy keeps the fallen out until the next round: after a moment (and the kill-cam) they watch their own side
  const watching = sd && !player.alive && !G.driving && !G.riding && !G.killcam && (!player.deathPos || now - player.deathAt > 3000)
  // Search and Destroy: hold F to plant or defuse; the server decides whether it counts, and we hold still meanwhile
  const sdLive = sd && G.match.roundState === 'live'
  const acting = !!G.act
  // F also climbs into our side's tank or onto its motorcycle when standing beside it, and out again
  const mounted = G.driving || G.riding
  const free = canAct && !mounted && !acting && !weapons.busy
  const board = free ? tanks?.boardable(G.team, player.pos) : null
  const mount = free && !board ? bikes?.boardable(G.team, player.pos) : null
  if (canAct && input.wasPressed('KeyF')) {
    if (G.driving || board) net.emit('tank', { on: !G.driving }, true)
    else if (G.riding || mount) net.emit('bike', { on: !G.riding }, true)
  }
  const wantUse = canAct && !mounted && !board && !mount && sdLive && input.down('KeyF')
  if (wantUse !== G.useHeld) { G.useHeld = wantUse; net.emit('use', { on: wantUse }, true) }

  if (G.driving) driveTank(dt, now, G.driving, canAct)
  else if (G.riding) rideBike(dt, now, G.riding)
  else moveOnFoot(dt, now, canAct, acting, watching, replaying)
  if (!watching && !replaying) hud.spectate(null)

  // audio listener
  const fwd = camera.getWorldDirection(tmpV)
  audio.setListener(camera.position, fwd)

  matchClock(dt, now)
  const next = G.pending ? `Next spawn: ${loadoutLabel(G.pending)}` : 'Press B to change loadout'
  if (sd) {
    // between rounds the result banner takes the centre of the screen; once watching, the spectator bar says it
    const title = player.deathPos ? 'You were killed' : 'Round in progress'
    hud.death(!watching && !replaying && !player.alive && G.match.state === 'playing' && G.match.roundState === 'live', player.deathPos ? G.killerName : '', 0, next, title, 'You join in at the start of the next round')
  } else {
    hud.death(!replaying && !player.alive && player.deathPos && G.match.state === 'playing', G.killerName, (G.respawnAt - now) / 1000, next)
  }
  const prompt = board ? `Press <kbd>F</kbd> to drive the ${tankSide(board.team).name}` : mount ? `Press <kbd>F</kbd> to ride the ${bikeSide(mount.team).name}` : ''
  const sites = updateObjectives(now, sdLive, acting, prompt)
  hud.scoreboard(input.down('Tab') || G.match.state === 'ended', G.roster, G.match, G.myId, G.aliveIds)
  hud.netstat(G.myPing, G.fps)
  const centre = watching || replaying ? camera.position : player.pos
  hud.compass(centre, player.alive ? player.yaw : camera.rotation.y, compassMarks(now, G.team, false), sites)
}

// scores, timer and the centre banner's countdown
function matchClock (dt, now) {
  hud.update(dt)
  hud.scores(G.match, G.team)
  const secs = (G.matchEndsLocal - now) / 1000
  const live = G.match.mode === 'sd' && G.match.roundState === 'live'
  hud.timer(secs, G.match.state === 'playing' && (G.match.mode === 'sd' ? live && (!!G.match.bomb || secs <= 15) : secs <= 60))
}

// soldiers and tanks for the minimap, friendly to `team`; all: the other side too, not only while firing (spectators)
function compassMarks (now, team, all) {
  const others = []
  for (const a of avatars.map.values()) {
    if (!a.alive || a.inTank) continue
    const friendly = a.team === team
    // COD2 compass: enemies only show up while firing
    if (!friendly && !all && !(a.flags & 16)) continue
    others.push({ x: a.pos.x, z: a.pos.z, friendly })
  }
  for (const t of tanks?.map.values() ?? []) {
    if (t.destroyed || t === G.driving) continue
    const friendly = t.team === team
    if (!friendly && !all && now - t.firedAt > 2000) continue
    others.push({ x: t.pos[0], z: t.pos[2], friendly, tank: true })
  }
  // free motorcycles: ours, or everyone's for a spectator
  for (const b of bikes?.map.values() ?? []) {
    if (b.destroyed || b.driver || (b.team !== team && !all)) continue
    others.push({ x: b.pos[0], z: b.pos[2], friendly: b.team === team, bike: true })
  }
  return others
}

// ------------------------------------------------------------------ spectating

const SPEC_FREE_KEYS = '<kbd>WASD</kbd> fly &middot; <kbd>Space</kbd> / <kbd>C</kbd> up / down &middot; <kbd>Shift</kbd> faster &middot; <kbd>LMB</kbd> follow a soldier'
const followKeys = (view) => `<kbd>LMB</kbd> / <kbd>RMB</kbd> next / previous &middot; <kbd>Space</kbd> ${view.mode === 'third' ? 'first' : 'third'} person`

// who the spectator bar names: the soldier followed, their weapon (or tank) and health
function watchInfo (view) {
  const a = view?.target
  if (!a) return { name: '' }
  const weapon = a.inTank ? tankSide(a.team).name : a.onBike ? bikeSide(a.team).name : WEAPONS[WEAPON_LIST[a.weapon]]?.name ?? ''
  return { name: a.name, team: a.team, weapon, hp: a.alive ? a.hp : 0 }
}

// the spectator camera's field of view, scope and listener (view: null for the overview orbit)
function watchCamera (view) {
  const fov = view?.fov || BASE_FOV
  if (fov !== fovCurrent) { fovCurrent = fov; camera.fov = fov; camera.updateProjectionMatrix() }
  hud.scope(!!view?.scoped)
  camera.updateMatrixWorld()
  audio.setListener(camera.position, camera.getWorldDirection(tmpV))
}

// fallen in Search and Destroy: follow the teammates still standing, or watch from above when there are none
function watchTeammates (dt, now) {
  const view = spec.update({ avatars, tanks, input: input.locked ? input : null, look: [lookDX, lookDY], pool: (a) => a.team === G.team, canFree: false, bounds: mapData.bounds, dt, now })
  if (!view) updateMenuCamera(dt)
  watchCamera(view)
  const sub = player.deathPos
    ? `Killed${G.killerName ? ` by ${G.killerName}` : ''} · back in next round`
    : 'Round in progress · you join in at the start of the next round'
  const keys = `${view ? `${followKeys(view)} &middot; ` : ''}<kbd>B</kbd> loadout`
  hud.spectate({ ...watchInfo(view), sub, keys })
}

// spectators: follow anyone on either side, or fly the free camera
function updateSpectating (dt, now) {
  const [dx, dy] = input.consumeLook()
  avatars.update(dt, INTERP_DELAY)
  const view = spec.update({ avatars, tanks, input: input.locked ? input : null, look: [dx, dy], pool: () => true, canFree: true, bounds: mapData.bounds, dt, now })
  watchCamera(view)
  const keys = view.mode === 'free' ? SPEC_FREE_KEYS : `${followKeys(view)} &middot; <kbd>F</kbd> free camera`
  hud.spectate({ ...watchInfo(view), keys: `${keys} &middot; <kbd>Esc</kbd> join a side` })
  hud.health(0, false) // no pain vignette
  matchClock(dt, now)
  const team = view.target?.team ?? null
  const sites = updateObjectives(now, G.match.mode === 'sd' && G.match.roundState === 'live', false, '', team)
  hud.scoreboard(input.down('Tab') || G.match.state === 'ended', G.roster, G.match, G.myId, G.aliveIds)
  hud.netstat(G.myPing, G.fps)
  hud.compass(camera.position, camera.rotation.y, compassMarks(now, team ?? 'allies', true), sites)
}

// ------------------------------------------------------------------ kill-cam

// our death through the killer's eyes, after a moment on the ground; true while it holds the camera.
// Space or a click skips it, and with it the wait for the respawn beyond the usual delay
function updateKillcam (dt, now) {
  const k = G.killcam
  if (!k) return false
  if ((player.alive && !k.test) || G.match.state !== 'playing') { endKillcam(); return false }
  if (input.locked && !loadoutMenu.isOpen && (input.wasPressed('Space') || input.mouse.leftPressed)) { skipKillcam(now); return false }
  if (!killcam.active) {
    if (now - (k.test ? k.since : player.deathAt) < KILLCAM.delay * 1000) return false
    if (!killcam.start({ killer: k.killer, victim: G.myId, at: k.at, roster: k.roster })) { skipKillcam(now); return false }
    avatars.hidden = grenades.hidden = true
  }
  const view = killcam.update({ tanks, dt, bounce: (pos, impact) => audio.nadeBounce(pos, Math.min(1, impact / 10)) })
  if (!view) { endKillcam(); return false }
  watchCamera(view)
  hud.killcam({ progress: killcam.progress })
  const how = `Killed you with ${weaponLabel(k.w, view.target.team)}${k.hs ? ' · headshot' : ''}`
  hud.spectate({ ...watchInfo(view), sub: how, keys: '<kbd>Space</kbd> skip' })
  return true
}

function skipKillcam (now) {
  if (G.match.mode !== 'sd') {
    net.emit('skip', {}, true)
    G.respawnAt = Math.max(now, player.deathAt + MATCH.respawnDelay * 1000)
  }
  endKillcam()
}

function endKillcam () {
  if (!G.killcam && !killcam.active) return
  G.killcam = null
  killcam.stop()
  avatars.hidden = false
  if (grenades) grenades.hidden = false
  if (G.team) viewmodel.setTeam(G.team)
  hud.killcam(null)
  hud.spectate(null)
  hud.scope(false)
}

function moveOnFoot (dt, now, canAct, acting, watching, replaying) {
  hud.tankGun(null)
  hud.gunSight(null)
  audio.engine(0)
  audio.bikeEngine(0)
  // weapon controls
  let switchTo = null
  if (input.wasPressed('Digit1')) switchTo = 0
  if (input.wasPressed('Digit2')) switchTo = 1
  if (input.mouse.wheel) switchTo = (weapons.index + 1) % weapons.slots.length
  const armed = canAct && !acting
  const shots = weapons.update(dt, {
    trigger: armed && input.mouse.left,
    triggerPressed: armed && input.mouse.leftPressed,
    ads: armed && input.mouse.right,
    reload: armed && input.wasPressed('KeyR'),
    switchTo: player.alive && !loadoutMenu.isOpen && !acting ? switchTo : null,
    throwNade: armed && input.wasPressed('KeyG'),
    holdNade: armed && input.down('KeyG'),
    knife: armed && input.wasPressed('KeyV'),
    sprint: player.sprinting,
    alive: canAct
  }, { speed: player.speed, grounded: player.grounded, crouched: player.crouched })

  // tanks and bikes drive through soldiers: step out of one rather than stay stuck in it
  const out = player.alive && (tanks?.pushOut(player.pos) || bikes?.pushOut(player.pos))
  if (out) player.teleport(out)

  // movement (frozen while the loadout screen is up, or while planting / defusing)
  const steer = !loadoutMenu.isOpen && !acting
  const forward = steer && (input.down('KeyW') || input.down('ArrowUp'))
  const crouch = !loadoutMenu.isOpen && (input.down('KeyC') || input.down('ControlLeft'))
  // aiming or pulling the trigger drops out of the sprint
  const sprint = forward && !crouch && (input.down('ShiftLeft') || input.down('ShiftRight')) &&
    !(canAct && (input.mouse.left || input.mouse.right)) && !weapons.busy
  const lean = canAct && !acting && !sprint ? (input.down('KeyE') ? 1 : 0) - (input.down('KeyQ') ? 1 : 0) : 0
  const move = player.update(dt, {
    f: forward,
    b: steer && (input.down('KeyS') || input.down('ArrowDown')),
    l: steer && (input.down('KeyA') || input.down('ArrowLeft')),
    r: steer && (input.down('KeyD') || input.down('ArrowRight')),
    jump: steer && input.wasPressed('Space'),
    crouch,
    sprint,
    ads: weapons.adsT,
    speedMul: weapons.def.moveMul,
    lean,
    leanRoom
  })
  if (move.steps) audio.footstep(null, player.crouched ? 0.05 : 0.11)
  if (move.landed) { viewmodel.land(Math.min(1, move.landed / 9)); audio.footstep(null, 0.2) }

  // camera
  const ws = weapons
  if (replaying) {
    // the kill-cam has placed the camera
  } else if (player.alive) {
    player.eyePos(camera.position)
    camera.rotation.set(player.pitch + ws.punch.pitch, player.yaw + ws.punch.yaw, -player.lean * LEAN_ROLL)
    if (G.shake > 0.001) {
      camera.rotation.x += (Math.random() - 0.5) * 0.06 * G.shake
      camera.rotation.y += (Math.random() - 0.5) * 0.06 * G.shake
    }
    deathRoll = 0
  } else if (watching) {
    watchTeammates(dt, now)
  } else if (player.deathPos) {
    // slump to the ground
    const k = Math.min(1, (now - player.deathAt) / 600)
    camera.position.copy(player.deathPos)
    camera.position.y -= (PLAYER.eye - 0.35) * k * k
    deathRoll += (0.45 - deathRoll) * Math.min(1, dt * 5)
    camera.rotation.set(player.pitch * (1 - k) - 0.15 * k, player.yaw, deathRoll)
  } else {
    updateMenuCamera(dt)
  }
  G.shake *= Math.exp(-dt * 4)
  const targetFov = BASE_FOV + (ws.def.adsFov - BASE_FOV) * ws.adsT
  if (!watching && !replaying && Math.abs(targetFov - fovCurrent) > 0.01) {
    fovCurrent = targetFov
    camera.fov = fovCurrent
    camera.updateProjectionMatrix()
  }
  camera.updateMatrixWorld()

  // shooting (after the camera is placed so shots leave from the current view)
  for (let i = 0; i < shots; i++) {
    const spread = ws.spread({ speed: player.speed, grounded: player.grounded, crouched: player.crouched })
    fireShot(spread)
  }
  for (const ev of ws.drainEvents()) {
    if (ev === 'fire') {
      audio.shot(ws.id)
      viewmodel.fire()
      if (ws.def.action === 'bolt') audio.bolt(60 / ws.def.rpm)
    } else if (ev === 'dry') audio.dry()
    else if (ev === 'reload') audio.reload(ws.id, ws.reloadDur, ws.reloadSteps)
    else if (ev === 'switch') audio.weaponSwitch()
    else if (ev === 'ping') { audio.ping(); viewmodel.ping() }
    else if (ev === 'windup') {
      G.cookK = G.nadeSeq++
      G.cookAt = performance.now()
      net.emit('cook', { k: G.cookK }, true)
      audio.nadeWindup()
    }
    else if (ev === 'throw') throwGrenade()
    else if (ev === 'swing') audio.knifeSwing()
    else if (ev === 'stab') knifeStrike()
  }

  // send state
  // (keeps a steady cadence instead of drifting to every 3rd frame when a frame lands a hair early)
  if (player.alive && now - G.lastSend >= 1000 / INPUT_RATE - 4) {
    G.lastSend = Math.max(G.lastSend + 1000 / INPUT_RATE, now - 50)
    const p = player.pos
    const flags = (player.crouched ? 2 : 0) | (ws.adsT > 0.5 ? 4 : 0) | (ws.reloading ? 8 : 0)
    net.emit('st', [player.life, r2(p.x), r2(p.y), r2(p.z), Math.round(player.yaw * 1000) / 1000, Math.round(player.pitch * 1000) / 1000, flags, ws.index, Math.round(now), r2(player.lean)])
  }

  // viewmodel (hidden behind the scope overlay when a scoped rifle is fully raised); the spectator camera poses its own
  if (!watching && !replaying) updateViewmodel(dt, ws)

  hud.health(player.hp, player.alive)
  hud.weapon(ws)
  const spread = ws.spread({ speed: player.speed, grounded: player.grounded, crouched: player.crouched })
  hud.crosshair(spread, fovCurrent, player.alive && ws.adsT < 0.5 && !ws.reloading && ws.sprintT < 0.5 && !ws.busy, player.alive ? crosshairTarget() : null)
}

function updateViewmodel (dt, ws) {
  const scoped = player.alive && ws.def.scope && ws.adsT > 0.85
  viewmodel.scoped = scoped
  hud.scope(scoped)
  viewmodel.update({
    dt,
    weapon: ws.id,
    ads: ws.adsT,
    sprint: ws.sprintT,
    speed: player.speed,
    grounded: player.grounded,
    crouched: player.crouched,
    reloadFrac: ws.reloading ? 1 - ws.reloadT / ws.reloadDur : -1,
    drawFrac: ws.drawing ? ws.drawT / ws.def.drawTime : 0,
    throwFrac: ws.throwFrac,
    knifeFrac: ws.knifeFrac,
    cycleFrac: ws.cycleFrac,
    reloadSteps: ws.reloadSteps,
    mag: ws.clip.mag,
    lookDX,
    lookDY,
    alive: player.alive,
    ...G.vmPose
  })
}

function leanRoom (side) {
  const p = player.pos
  const s = leanShift(player.yaw, side)
  const d = [s[0] / PLAYER.leanDist, 0, s[1] / PLAYER.leanDist]
  const hit = rayMap(RAPIER, world, [p.x, p.y + player.eye, p.z], d, PLAYER.leanDist + LEAN_GAP)
  return hit ? Math.max(0, (hit.dist - LEAN_GAP) / PLAYER.leanDist) : 1
}

const CAM_BACK = 8 // metres behind the turret
const camFwd = new THREE.Vector3()
const camBack = new THREE.Vector3()
const camPivot = new THREE.Vector3()
const gunPt = new THREE.Vector3()

// W/S throttle, A/D turn the hull, the mouse swings the camera and the turret follows it, LMB fires
function driveTank (dt, now, s, canAct) {
  const steer = !loadoutMenu.isOpen
  const key = (a, b) => steer && (input.down(a) || input.down(b))
  const throttle = (key('KeyW', 'ArrowUp') ? 1 : 0) - (key('KeyS', 'ArrowDown') ? 1 : 0)
  const turn = (key('KeyA', 'ArrowLeft') ? 1 : 0) - (key('KeyD', 'ArrowRight') ? 1 : 0)
  if (!s.destroyed) s.body.drive(dt, throttle, turn)
  const b = s.body.pos
  s.pos = [b.x, b.y, b.z]
  s.yaw = s.body.yaw
  const sd = tankSide(s.team)
  // we ride in the turret: the death camera and the minimap start from here
  player.teleport([b.x, b.y + sd.hullH + 0.9 - PLAYER.eye, b.z])

  // third-person camera behind the turret, pulled in where a wall would come between them
  player.pitch = Math.max(-0.5, Math.min(0.45, player.pitch))
  const yaw = player.yaw; const pitch = player.pitch
  camFwd.set(-Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch))
  camPivot.set(b.x, b.y + sd.hullH + 1.5, b.z)
  camBack.copy(camFwd).negate()
  camBack.y += 0.4
  camBack.normalize()
  const wall = rayMap(RAPIER, world, camPivot.toArray(), camBack.toArray(), CAM_BACK)
  const back = wall ? Math.max(0.8, wall.dist - 0.3) : CAM_BACK
  camera.position.copy(camPivot).addScaledVector(camBack, back)
  const kick = Math.max(0, 1 - (now - s.firedAt) / 300) ** 2 * 0.05
  camera.rotation.set(pitch + kick, yaw, 0)
  if (G.shake > 0.001) {
    camera.rotation.x += (Math.random() - 0.5) * 0.06 * G.shake
    camera.rotation.y += (Math.random() - 0.5) * 0.06 * G.shake
  }
  G.shake *= Math.exp(-dt * 4)
  if (fovCurrent !== BASE_FOV) { fovCurrent = BASE_FOV; camera.fov = BASE_FOV; camera.updateProjectionMatrix() }
  camera.updateMatrixWorld()
  hud.scope(false)

  // what the crosshair is on, looking past the tank itself
  const o = camera.position.clone().addScaledVector(camFwd, back).toArray()
  const d = camFwd.toArray()
  let reach = TANK.range
  const mh = rayMap(RAPIER, world, o, d, reach)
  if (mh) reach = mh.dist
  const th = tanks.ray(o, d, reach, s)
  if (th) reach = th.t
  const ph = rayPlayers(o, d, reach)
  if (ph) reach = ph.t
  const aim = gunPt.fromArray(o).addScaledVector(camFwd, Math.max(reach, 8))
  // the turret traverses and the gun elevates towards it, at their own pace
  const g = gunRay(s).o
  const wx = aim.x - g[0]; const wy = aim.y - g[1]; const wz = aim.z - g[2]
  const wantYaw = Math.atan2(-wx, -wz)
  const wantPitch = Math.max(TANK.pitchMin, Math.min(TANK.pitchMax, Math.atan2(wy, Math.hypot(wx, wz))))
  const dy = wrapAngle(wantYaw - s.turret)
  s.turret = wrapAngle(s.turret + Math.sign(dy) * Math.min(Math.abs(dy), TANK.traverse * dt))
  s.gun += Math.sign(wantPitch - s.gun) * Math.min(Math.abs(wantPitch - s.gun), TANK.elevate * dt)

  const ready = now >= G.tankReadyAt
  const gr = gunRay(s)
  if (canAct && ready && !s.destroyed && input.mouse.left) {
    G.tankReadyAt = now + TANK.reload * 1000
    net.emit('shell', { t: r3(s.turret), g: r3(s.gun) }, true)
    s.firedAt = now
    effects.gunBlast(new THREE.Vector3(...gr.muzzle), new THREE.Vector3(...gr.d))
    audio.cannon()
    G.shake = Math.max(G.shake, 0.35)
  }
  audio.engine(s.destroyed ? 0 : 0.15 + Math.min(1, Math.abs(s.body.speed) / TANK.speed + Math.abs(turn) * 0.3) * 0.85)

  if (now - G.lastSend >= 1000 / INPUT_RATE - 4) {
    G.lastSend = Math.max(G.lastSend + 1000 / INPUT_RATE, now - 50)
    net.emit('tk', [player.life, r2(b.x), r2(b.y), r2(b.z), r3(s.yaw), r3(s.turret), r3(s.gun), Math.round(now)])
  }

  // the gun's own sight: where a shell would land now, which trails the crosshair while the turret swings round
  const gh = rayMap(RAPIER, world, gr.o, gr.d, TANK.range)
  gunPt.fromArray(gr.o).addScaledVector(tmpV.fromArray(gr.d), gh ? gh.dist : TANK.range).project(camera)
  const onScreen = gunPt.z < 1 && Math.abs(gunPt.x) < 1 && Math.abs(gunPt.y) < 1
  hud.gunSight(onScreen ? (gunPt.x + 1) / 2 * window.innerWidth : null, (1 - gunPt.y) / 2 * window.innerHeight, ready)
  hud.health(s.hp, true, TANK.maxHealth, 'ARMOUR')
  hud.tankGun(sd.gunName, ready ? 1 : 1 - (G.tankReadyAt - now) / (TANK.reload * 1000))
  hud.crosshair(0.003, BASE_FOV, true, crosshairTarget())
}

const BIKE_CAM_BACK = 4.5

// W throttle, S brake and reverse, A/D steer; the mouse looks around, and the view turns with the bike
function rideBike (dt, now, s) {
  const steer = !loadoutMenu.isOpen
  const key = (a, b) => steer && (input.down(a) || input.down(b))
  const throttle = (key('KeyW', 'ArrowUp') ? 1 : 0) - (key('KeyS', 'ArrowDown') ? 1 : 0)
  const turn = (key('KeyA', 'ArrowLeft') ? 1 : 0) - (key('KeyD', 'ArrowRight') ? 1 : 0)
  const yaw0 = s.body.yaw
  if (!s.destroyed) s.body.drive(dt, throttle, turn)
  const b = s.body.pos
  s.pos = [b.x, b.y, b.z]
  s.yaw = s.body.yaw
  s.lean = s.body.lean
  player.yaw = wrapAngle(player.yaw + wrapAngle(s.yaw - yaw0))
  player.teleport([b.x, b.y, b.z])

  player.pitch = Math.max(-0.6, Math.min(0.5, player.pitch))
  const yaw = player.yaw; const pitch = player.pitch
  camFwd.set(-Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch))
  camPivot.set(b.x, b.y + 1.7, b.z)
  camBack.copy(camFwd).negate()
  camBack.y += 0.3
  camBack.normalize()
  const wall = rayMap(RAPIER, world, camPivot.toArray(), camBack.toArray(), BIKE_CAM_BACK)
  camera.position.copy(camPivot).addScaledVector(camBack, wall ? Math.max(0.6, wall.dist - 0.3) : BIKE_CAM_BACK)
  camera.rotation.set(pitch, yaw, 0)
  if (G.shake > 0.001) {
    camera.rotation.x += (Math.random() - 0.5) * 0.06 * G.shake
    camera.rotation.y += (Math.random() - 0.5) * 0.06 * G.shake
  }
  G.shake *= Math.exp(-dt * 4)
  if (fovCurrent !== BASE_FOV) { fovCurrent = BASE_FOV; camera.fov = BASE_FOV; camera.updateProjectionMatrix() }
  camera.updateMatrixWorld()

  audio.bikeEngine(s.destroyed ? 0 : 0.12 + Math.min(1, Math.abs(s.body.speed) / BIKE.speed) * 0.88)
  if (now - G.lastSend >= 1000 / INPUT_RATE - 4) {
    G.lastSend = Math.max(G.lastSend + 1000 / INPUT_RATE, now - 50)
    net.emit('bk', [player.life, r2(b.x), r2(b.y), r2(b.z), r3(s.yaw), r2(s.lean), Math.round(now)])
  }

  hud.scope(false)
  hud.gunSight(null)
  hud.health(player.hp, player.alive)
  hud.bike(bikeSide(s.team).name, s.hp / BIKE.maxHealth)
  hud.crosshair(0, BASE_FOV, false, null)
}

const markV = new THREE.Vector3()

// Search and Destroy HUD: round line, use prompt, plant / defuse bar and the site markers; returns the minimap marks
// extra: a prompt to show when Search and Destroy has none (the tank)
// team: whose side the markers are told from (null: a spectator in the free camera, neither)
function updateObjectives (now, live, acting, extra = '', team = G.team) {
  const m = G.match
  if (m.mode !== 'sd' || !m.attackers || m.state !== 'playing') {
    hud.roundInfo('', false)
    hud.usePrompt(extra)
    hud.act(-1)
    hud.markers([])
    return []
  }
  const defenders = otherTeam(m.attackers)
  const attacking = team === m.attackers
  const b = m.bomb
  const role = b ? `Bomb planted at ${b.s}` : !G.team ? '' : attacking ? 'You are attacking' : 'You are defending'
  hud.roundInfo(`Round ${m.round} of ${SD.halftime * 2} &middot; ${TEAMS[m.attackers].name} attack${role ? ` &middot; <b>${role}</b>` : ''}`, !!b)

  let prompt = ''
  if (live && player.alive && !acting) {
    const at = [player.pos.x, player.pos.y, player.pos.z]
    if (attacking && !b) {
      const site = sdSiteAt(defenders, at)
      if (site) prompt = `Hold <kbd>F</kbd> to plant the bomb at ${site.id}`
    } else if (!attacking && b && Math.hypot(at[0] - b.p[0], at[2] - b.p[2]) <= SD.defuseReach && Math.abs(at[1] - b.p[1]) < 1.5) {
      prompt = 'Hold <kbd>F</kbd> to defuse the bomb'
    }
  }
  hud.usePrompt(prompt || extra)
  hud.act(G.act ? (now - G.act.at) / G.act.ms : -1, G.act?.k === 'plant' ? 'Planting the bomb' : 'Defusing the bomb')

  const targets = b
    ? [{ key: 'bomb', pos: b.p, text: b.s, sub: !team ? 'Bomb' : attacking ? 'Guard' : 'Defuse', cls: 'bomb', color: '#ff5b4a' }]
    : SD_SITES[defenders].map((s) => ({ key: s.id, pos: s.pos, text: s.id, sub: !team ? 'Site' : attacking ? 'Attack' : 'Defend', cls: attacking ? 'attack' : 'defend', color: attacking ? '#ffb35a' : '#8fd8ff' }))
  const marks = []
  const w = window.innerWidth; const h = window.innerHeight
  for (const t of live ? targets : []) {
    markV.set(t.pos[0], t.pos[1] + 1.4, t.pos[2])
    const dist = Math.round(markV.distanceTo(camera.position))
    markV.project(camera)
    if (markV.z > 1) continue // behind the camera
    const x = (markV.x + 1) / 2 * w; const y = (1 - markV.y) / 2 * h
    if (x < 0 || x > w || y < 0 || y > h) continue
    marks.push({ key: t.key, x, y, text: t.text, sub: `${t.sub} · ${dist} m`, cls: t.cls })
  }
  hud.markers(marks)
  return targets.map((t) => ({ x: t.pos[0], z: t.pos[2], text: t.text, color: t.color }))
}

// debug/verification hook (read-only snapshot of game state)
window.__labin = {
  viewmodel: (v) => { viewmodel.visible = !!v },
  // test helper: view the first-person arms and gun from pos looking at look (viewmodel camera space; null resets)
  vmcam: (pos, look) => { viewmodel.debugView = pos ? { pos, look } : null },
  // test helper: hold the first-person animation at a point, e.g. { throwFrac: 0.3 } or { knifeFrac: 0.5 } (null releases)
  vmpose: (pose) => { G.vmPose = pose || undefined },
  // test helper: which first-person models are built, and whether they come from weapons.glb
  viewmodels: () => Object.fromEntries(Object.entries(viewmodel.models).map(([id, m]) => [id, !!m.modelled])),
  // test helper: pin the camera at pos looking at look, in the menu or in game (null restores it)
  cam: (pos, look) => { camOverride = pos ? { pos, look } : null },
  // test helper: start (true) / stop and return (false) the per-frame camera trace
  trace: (on) => { const t = G.trace; G.trace = on ? [] : null; return t },
  // test helpers: drive the loadout flow without clicking, and send raw (possibly forged) requests
  deploy: (l) => requestLoadout(l),
  openLoadout: () => openLoadout(),
  send: (ev, data) => net.emit(ev, data, true),
  // test helper: pretend the pointer is locked (automated browsers are often refused pointer lock)
  fakeLock: (v) => { input.locked = !!v; if (v) hud.pause(false) },
  // test helper: point the view at a world position
  lookAt: (x, y, z) => {
    if (!player) return
    const e = player.eyePos(new THREE.Vector3())
    player.yaw = Math.atan2(-(x - e.x), -(z - e.z))
    player.pitch = Math.atan2(y - e.y, Math.hypot(x - e.x, z - e.z))
  },
  // test helper: the kill-cam's state, and (with trace on) one row per replayed frame
  // test helper: replay the latest recorded kill (n: how many kills back) as if it were our own death
  replayKill: (n = 0) => {
    const kills = killcam.events.filter((e) => e.type === 'kill' && e.d.k && e.d.k !== e.d.v)
    const e = kills[kills.length - 1 - n]
    if (!e) return null
    G.killcam = { killer: e.d.k, at: e.t, roster: new Map(G.roster), w: e.d.w, hs: e.d.hs, test: true, since: performance.now() - KILLCAM.delay * 1000 }
    return { killer: e.d.k, victim: e.d.v, at: e.t, w: e.d.w }
  },
  killcam: () => ({
    rt: avatars.renderTime(INTERP_DELAY),
    pending: G.killcam && { killer: G.killcam.killer, at: G.killcam.at },
    active: killcam.active,
    time: killcam.time,
    at: killcam.at,
    scale: killcam.scale,
    firstPerson: killcam.firstPerson,
    snaps: killcam.snaps.length,
    span: killcam.snaps.length ? [killcam.snaps[0].t, killcam.snaps[killcam.snaps.length - 1].t] : null,
    events: killcam.events.map((e) => ({ t: e.t, type: e.type, id: e.d.id ?? e.d.k })),
    ghosts: [...killcam.ghosts.map.values()].map((a) => ({ id: a.id, alive: a.alive, visible: a.root.visible, pos: [a.pos.x, a.pos.y, a.pos.z].map(r2), yaw: r3(a.yaw), pitch: r3(a.pitch) })),
    live: [...avatars.map.values()].map((a) => ({ id: a.id, alive: a.alive, visible: a.root.visible, pos: [a.pos.x, a.pos.y, a.pos.z].map(r2), yaw: r3(a.yaw), pitch: r3(a.pitch) })),
    cam: [camera.position.x, camera.position.y, camera.position.z].map(r2)
  }),
  state: () => ({
    state: G.state,
    spectating: G.spectating,
    spec: { target: spec.targetId, third: spec.third, free: spec.free, firstPerson: spec.firstPerson },
    locked: input.locked,
    hits: G.hits,
    shots: G.shots,
    myId: G.myId,
    team: G.team,
    alive: player?.alive,
    hp: player?.hp,
    pos: player ? [player.pos.x, player.pos.y, player.pos.z].map(r2) : null,
    weapon: weapons.id,
    ammo: weapons.clip,
    grenades: weapons.grenades,
    cooking: weapons.cooking ? weapons.cookT : null,
    grenadesInFlight: grenades?.live.size,
    drops: [...drops.live].map(([id, d]) => ({ id, pos: d.mesh.position.toArray().map(r2) })),
    knifing: weapons.knifing,
    cats: cats ? [...cats.map].map(([id, c]) => ({ id, state: c.state, pos: c.pos.toArray().map(r2) })) : [],
    tanks: tanks ? [...tanks.map.values()].map((t) => ({ id: t.id, team: t.team, hp: t.hp, driver: t.driver, destroyed: t.destroyed, pos: t.pos.map(r2) })) : [],
    driving: G.driving?.id ?? 0,
    bikes: bikes ? [...bikes.map.values()].map((b) => ({ id: b.id, team: b.team, hp: b.hp, driver: b.driver, destroyed: b.destroyed, pos: b.pos.map(r2), yaw: r3(b.yaw), lean: r2(b.lean) })) : [],
    riding: G.riding?.id ?? 0,
    sprinting: player?.sprinting,
    speed: player?.speed,
    loadout: G.loadout,
    pending: G.pending,
    deployed: G.deployed,
    loadoutOpen: loadoutMenu.isOpen,
    viewmodelHidden: !viewmodel.holder.visible,
    fps: G.fps,
    tps: G.tps,
    match: G.match,
    roster: [...G.roster.values()],
    avatars: [...avatars.map.values()].map((a) => ({ id: a.id, name: a.name, team: a.team, alive: a.alive, pos: [a.pos.x, a.pos.y, a.pos.z].map(r2) })),
    drawCalls: renderer.info.render.calls,
    triangles: renderer.info.render.triangles
  })
}

requestAnimationFrame(frame)
boot()
