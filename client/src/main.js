// Labin Strike client: boot, menu, game loop, combat and networking glue.
import './style.css'
import * as THREE from 'three'
import RAPIER from '@dimforge/rapier3d-compat'
import { WEAPONS, WEAPON_IDS, PLAYER, INPUT_RATE, INTERP_DELAY, MATCH, TEAMS } from '@shared/constants.js'
import { parseGlbJson, extractMapData } from '@shared/mapdata.js'
import { buildMapWorld, rayMap } from '@shared/physics.js'
import { rayVsPlayer } from '@shared/hitbox.js'
import { createRenderer, createScene, fitSunToBounds, fetchMap, parseMap } from './renderer.js'
import { loadCars } from './cars.js'
import { Input } from './input.js'
import { LocalPlayer } from './player.js'
import { WeaponSystem } from './weapons.js'
import { Viewmodel } from './viewmodel.js'
import { Avatars } from './avatars.js'
import { Effects } from './effects.js'
import { Audio } from './audio.js'
import { Hud } from './hud.js'
import { Net } from './net.js'

const BASE_FOV = 68
const $ = (id) => document.getElementById(id)
const params = new URLSearchParams(location.search)

const store = {
  get (k, d) { try { const v = localStorage.getItem(`ls.${k}`); return v == null ? d : v } catch { return d } },
  set (k, v) { try { localStorage.setItem(`ls.${k}`, v) } catch {} }
}

const G = {
  state: 'loading', // loading | menu | connecting | playing
  myId: 0,
  team: null,
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
  tps: 0, // server position corrections received
  trace: null // test helper: per-frame [t, camX, camY, camZ]
}

// ------------------------------------------------------------------ setup

const canvas = $('game')
let highQuality = store.get('quality', '1') === '1'
const renderer = createRenderer(canvas, highQuality)
const { scene, sun } = createScene(renderer, highQuality)
// near plane 0.1 (player capsule keeps the eye >= 0.35 m from walls): 2x the depth precision of 0.05
const camera = new THREE.PerspectiveCamera(BASE_FOV, window.innerWidth / window.innerHeight, 0.1, 1600)
camera.rotation.order = 'YXZ'
scene.add(camera)

const input = new Input(canvas)
const weapons = new WeaponSystem()
const viewmodel = new Viewmodel()
const avatars = new Avatars(scene)
const effects = new Effects(scene)
const audio = new Audio()
const hud = new Hud()
const net = new Net()

let world = null
let mapData = null
let player = null
let cars = null

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
nameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') deploy() })
deployBtn.addEventListener('click', () => deploy())
$('pause').addEventListener('click', () => { if (G.state === 'playing') input.lock() })
$('btn-leave').addEventListener('click', (e) => { e.stopPropagation(); leave('Left the match') })
canvas.addEventListener('click', () => { if (G.state === 'playing' && !input.locked) input.lock() })

function setStatus (text, error = false) {
  menuStatus.textContent = text
  menuStatus.classList.toggle('error', error)
}

function showMenu (v) {
  $('menu').classList.toggle('hidden', !v)
  hud.show(!v)
}

async function deploy () {
  if (G.state !== 'menu') return
  const name = nameInput.value.trim() || `Soldier${Math.floor(Math.random() * 900 + 100)}`
  store.set('name', name)
  audio.unlock()
  G.state = 'connecting'
  deployBtn.disabled = true
  deployBtn.textContent = 'Connecting…'
  setStatus('Establishing UDP channel…')
  try {
    await net.connect()
  } catch (err) {
    console.warn('connect failed', err)
    G.state = 'menu'
    deployBtn.disabled = false
    deployBtn.textContent = 'Deploy'
    setStatus(err?.message || 'Could not connect to the server', true)
    return
  }
  setStatus('Joining match…')
  net.emit('join', { name }, true)
  input.lock()
}

function leave (msg) {
  net.close()
  input.unlock()
  input.enabled = false
  G.state = 'menu'
  G.myId = 0
  if (player) player.alive = false
  avatars.clear()
  G.roster.clear()
  showMenu(true)
  hud.pause(false)
  deployBtn.disabled = false
  deployBtn.textContent = 'Deploy'
  setStatus(msg || '')
}

input.onLockChange = (locked, error) => {
  if (G.state !== 'playing') return
  hud.pause(!locked && !error)
  if (error) hud.notice('Pointer lock unavailable – click the game to retry')
}

// ------------------------------------------------------------------ networking

net.onDisconnect = () => { if (G.state === 'playing' || G.state === 'connecting') leave('Disconnected from server') }

net.on('welcome', (d) => {
  G.myId = d.id
  G.team = d.team
  setRoster(d.roster, d.match)
  viewmodel.setTeam(d.team)
  hud.setTeam(d.team)
  G.state = 'playing'
  input.enabled = true
  showMenu(false)
  setStatus('')
  hud.pause(!input.locked)
  if (d.spawn) onSpawn(d.spawn)
  hud.center(`${TEAMS[d.team].name.toUpperCase()}<small>Team Deathmatch · first to ${d.match.scoreLimit}</small>`, 3)
})

net.on('spawn', (d) => onSpawn(d))

function onSpawn (d) {
  if (!player || d.life <= player.life) return
  player.spawn(d.pos, d.yaw, d.life)
  weapons.reset()
  G.killerName = ''
  hud.death(false)
}

net.on('tp', (d) => {
  G.tps++
  if (player && d.life === player.life) player.teleport(d.pos)
})

net.on('snap', (s) => {
  if (G.state !== 'playing') return
  avatars.onSnapshot(s, G.myId, G.roster, G.team)
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
  const prev = G.match.state
  G.match = match
  G.matchEndsLocal = performance.now() + match.timeLeft * 1000
  if (prev === 'playing' && match.state === 'ended') {
    const txt = match.winner === 'draw' ? 'DRAW' : match.winner === G.team ? 'VICTORY' : 'DEFEAT'
    const sub = match.winner === 'draw' ? 'The match ended in a draw' : `${TEAMS[match.winner]?.name} win ${match.scores.allies} – ${match.scores.axis}`
    hud.center(`${txt}<small>${sub} · next round in ${match.timeLeft}s</small>`, MATCH.intermission)
  }
}

net.on('shot', (d) => {
  if (G.state !== 'playing' || d.id === G.myId) return
  const a = avatars.map.get(d.id)
  a?.showFlash()
  const o = new THREE.Vector3(...d.o)
  const e = new THREE.Vector3(...d.e)
  const myEye = player.eyePos(new THREE.Vector3())
  audio.shot(d.w, o, o.distanceTo(myEye))
  effects.tracer(o.clone().addScaledVector(e.clone().sub(o).normalize(), 0.8), e, 300)
  // impact decal where the bullet stopped (if it stopped on map geometry)
  const len = o.distanceTo(e)
  if (len > 0.5 && d.n !== 0) {
    const dir = e.clone().sub(o).divideScalar(len)
    const h = rayMap(RAPIER, world, d.o, [dir.x, dir.y, dir.z], len + 0.3)
    if (h && Math.abs(h.dist - len) < 0.6) effects.impact(o.clone().addScaledVector(dir, h.dist), h.normal)
  }
  // bullet passing close by
  if (player.alive && a && a.team !== G.team) {
    const seg = e.clone().sub(o)
    const t = THREE.MathUtils.clamp(myEye.clone().sub(o).dot(seg) / seg.lengthSq(), 0, 1)
    const closest = o.clone().addScaledVector(seg, t)
    if (closest.distanceTo(myEye) < 1.6 && t > 0.05 && t < 0.98) audio.whiz(closest)
  }
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
  const killer = G.roster.get(d.k)
  const victim = G.roster.get(d.v)
  hud.killfeed(killer, victim, d.w, d.hs, G.myId)
  if (d.v === G.myId && player) {
    player.alive = false
    player.hp = 0
    player.deathAt = performance.now()
    player.deathPos = player.eyePos(new THREE.Vector3())
    G.respawnAt = performance.now() + MATCH.respawnDelay * 1000
    G.killerName = killer && killer.id !== G.myId ? killer.name : ''
    input.mouse.left = false
  } else if (d.k === G.myId && victim) {
    hud.center(`<small>You killed ${escapeHtml(victim.name)}${d.hs ? ' · headshot' : ''}</small>`, 1.6)
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

const tmpV = new THREE.Vector3()
const tmpO = new THREE.Vector3()
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
    if (!a.alive) continue
    const h = rayVsPlayer(o, d, maxT, a.pos.x, a.pos.y, a.pos.z, a.crouched)
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
  const maxT = mh ? mh.dist : w.range
  const ph = rayPlayers(o, d, maxT)
  const t = ph ? ph.t : maxT
  const end = tmpO.clone().addScaledVector(dir, t)
  viewmodel.muzzleWorld(camera, muzzle)
  if (Math.random() < 0.6) effects.tracer(muzzle, end, 420)
  effects.muzzle(muzzle)
  if (ph) {
    effects.blood(end, dir.clone().negate())
  } else if (mh) {
    effects.impact(end, mh.normal)
  }
  const msg = { w: weapons.id, o: o.map(r2), e: [r2(end.x), r2(end.y), r2(end.z)] }
  if (ph && ph.avatar.team !== G.team) msg.hit = { id: ph.avatar.id, zone: ph.zone }
  net.emit('fire', msg)
}
const r2 = (v) => Math.round(v * 100) / 100

// what's under the crosshair (for name display / crosshair colour)
function crosshairTarget () {
  camera.getWorldPosition(tmpO)
  camera.getWorldDirection(tmpV)
  const o = [tmpO.x, tmpO.y, tmpO.z]
  const d = [tmpV.x, tmpV.y, tmpV.z]
  const mh = rayMap(RAPIER, world, o, d, 150)
  const ph = rayPlayers(o, d, mh ? mh.dist : 150)
  if (!ph) return null
  return { name: ph.avatar.name, friendly: ph.avatar.team === G.team }
}

// ------------------------------------------------------------------ boot

async function boot () {
  const fill = $('loading-fill'); const text = $('loading-text')
  const progress = (p, label) => { fill.style.width = `${Math.round(p * 100)}%`; if (label) text.textContent = label }
  try {
    progress(0.05, 'Initialising physics…')
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
    fitSunToBounds(sun, mapData.bounds)
    player = new LocalPlayer(RAPIER, world)
    hud.buildMinimap(mapData)
    viewmodel.setTeam('allies')
    // warm up shaders so the first frame in-game does not hitch
    renderer.compile(scene, camera)
    progress(1, 'Ready')
    $('loading').classList.add('hidden')
    G.state = 'menu'
    deployBtn.disabled = false
    deployBtn.textContent = 'Deploy'
    if (params.has('autojoin')) deploy()
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

  if (G.state === 'playing' && player) updateGame(dt, now)
  else updateMenuCamera(dt)

  effects.update(dt)
  cars?.update(camera.position, dt)
  renderer.clear()
  renderer.render(scene, camera)
  if (G.state === 'playing' && player?.alive) viewmodel.render(renderer, 58 - (BASE_FOV - fovCurrent) * 0.35)
  if (G.trace) G.trace.push([now, camera.position.x, camera.position.y, camera.position.z])
  input.endFrame()
}

let camOverride = null   // test helper (window.__labin.cam): fixed menu camera

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

  // weapon controls
  let switchTo = null
  if (input.wasPressed('Digit1')) switchTo = 0
  if (input.wasPressed('Digit2')) switchTo = 1
  if (input.wasPressed('KeyQ')) switchTo = weapons.prevIndex
  if (input.mouse.wheel) switchTo = (weapons.index + 1) % WEAPON_IDS.length
  const canAct = player.alive && locked && G.match.state === 'playing'
  const shots = weapons.update(dt, {
    trigger: canAct && input.mouse.left,
    triggerPressed: canAct && input.mouse.leftPressed,
    ads: canAct && input.mouse.right,
    reload: canAct && input.wasPressed('KeyR'),
    switchTo: player.alive ? switchTo : null,
    alive: canAct
  }, { speed: player.speed, grounded: player.grounded, crouched: player.crouched })

  // movement
  const move = player.update(dt, {
    f: input.down('KeyW') || input.down('ArrowUp'),
    b: input.down('KeyS') || input.down('ArrowDown'),
    l: input.down('KeyA') || input.down('ArrowLeft'),
    r: input.down('KeyD') || input.down('ArrowRight'),
    jump: input.wasPressed('Space'),
    crouch: input.down('KeyC') || input.down('ControlLeft'),
    ads: weapons.adsT
  })
  if (move.steps) audio.footstep(null, player.crouched ? 0.05 : 0.11)
  if (move.landed) { viewmodel.land(Math.min(1, move.landed / 9)); audio.footstep(null, 0.2) }

  // camera
  const ws = weapons
  if (player.alive) {
    player.eyePos(camera.position)
    camera.rotation.set(player.pitch + ws.punch.pitch, player.yaw + ws.punch.yaw, 0)
    deathRoll = 0
  } else if (player.deathPos) {
    // slump to the ground
    const k = Math.min(1, (now - player.deathAt) / 600)
    camera.position.copy(player.deathPos)
    camera.position.y -= (PLAYER.eye - 0.35) * k * k
    deathRoll += (0.45 - deathRoll) * Math.min(1, dt * 5)
    camera.rotation.set(player.pitch * (1 - k) - 0.15 * k, player.yaw, deathRoll)
  }
  const targetFov = BASE_FOV + (ws.def.adsFov - BASE_FOV) * ws.adsT
  if (Math.abs(targetFov - fovCurrent) > 0.01) {
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
    if (ev === 'fire') { audio.shot(ws.id); viewmodel.fire() } else if (ev === 'dry') audio.dry()
    else if (ev === 'reload') audio.reload(ws.id, ws.def.reloadTime)
    else if (ev === 'switch') audio.weaponSwitch()
  }

  // send state
  // (keeps a steady cadence instead of drifting to every 3rd frame when a frame lands a hair early)
  if (player.alive && now - G.lastSend >= 1000 / INPUT_RATE - 4) {
    G.lastSend = Math.max(G.lastSend + 1000 / INPUT_RATE, now - 50)
    const p = player.pos
    const flags = (player.crouched ? 2 : 0) | (ws.adsT > 0.5 ? 4 : 0) | (ws.reloading ? 8 : 0)
    net.emit('st', [player.life, r2(p.x), r2(p.y), r2(p.z), Math.round(player.yaw * 1000) / 1000, Math.round(player.pitch * 1000) / 1000, flags, ws.index, Math.round(now)])
  }

  // remote players
  avatars.update(dt, INTERP_DELAY)

  // audio listener
  const fwd = camera.getWorldDirection(tmpV)
  audio.setListener(camera.position, fwd)

  // viewmodel
  viewmodel.update({
    dt,
    weapon: ws.id,
    ads: ws.adsT,
    speed: player.speed,
    grounded: player.grounded,
    crouched: player.crouched,
    reloadFrac: ws.reloading ? 1 - ws.reloadT / ws.def.reloadTime : -1,
    drawFrac: ws.drawing ? ws.drawT / ws.def.drawTime : 0,
    lookDX,
    lookDY,
    alive: player.alive
  })

  // HUD
  hud.update(dt)
  hud.health(player.hp, player.alive)
  hud.weapon(ws)
  const spread = ws.spread({ speed: player.speed, grounded: player.grounded, crouched: player.crouched })
  hud.crosshair(spread, fovCurrent, player.alive && ws.adsT < 0.5 && !ws.reloading, player.alive ? crosshairTarget() : null)
  hud.scores(G.match, G.team)
  hud.timer((G.matchEndsLocal - now) / 1000, G.match.state)
  hud.death(!player.alive && G.match.state === 'playing', G.killerName, (G.respawnAt - now) / 1000)
  hud.scoreboard(input.down('Tab') || G.match.state === 'ended', G.roster, G.match, G.myId, G.aliveIds)
  hud.netstat(G.myPing, G.fps)
  const others = []
  for (const a of avatars.map.values()) {
    if (!a.alive) continue
    const friendly = a.team === G.team
    // COD2 compass: enemies only show up while firing
    if (!friendly && !(a.flags & 16)) continue
    others.push({ x: a.pos.x, z: a.pos.z, friendly })
  }
  hud.compass(player.pos, player.alive ? player.yaw : camera.rotation.y, others)
}

// debug/verification hook (read-only snapshot of game state)
window.__labin = {
  viewmodel: (v) => { viewmodel.visible = !!v },
  // test helper: pin the menu camera at pos looking at look (null restores the orbit)
  cam: (pos, look) => { camOverride = pos ? { pos, look } : null },
  // test helper: start (true) / stop and return (false) the per-frame camera trace
  trace: (on) => { const t = G.trace; G.trace = on ? [] : null; return t },
  // test helper: point the view at a world position
  lookAt: (x, y, z) => {
    if (!player) return
    const e = player.eyePos(new THREE.Vector3())
    player.yaw = Math.atan2(-(x - e.x), -(z - e.z))
    player.pitch = Math.atan2(y - e.y, Math.hypot(x - e.x, z - e.z))
  },
  state: () => ({
    state: G.state,
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
