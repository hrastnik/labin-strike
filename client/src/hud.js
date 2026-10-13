// DOM HUD: health, ammo, pickups, crosshair, hitmarkers, killfeed, scores/timer, scoreboard, compass minimap,
// the Search and Destroy round line, site markers and plant / defuse bar, and the tank's armour, gun and gun sight.
import { WEAPONS, TEAMS, PLAYER } from '@shared/constants.js'
import { GRENADE, KNIFE } from '@shared/weapons.js'
import { MODES, SD } from '@shared/modes.js'
import { TANK } from '@shared/tanks.js'

// compass north in map (x, z) coordinates
const NORTH_X = -0.8502
const NORTH_Z = -0.5264

const $ = (id) => document.getElementById(id)
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

// top-down outline (world x, z) and top height of a map collider: an oriented box, or a convex hull's points
function outline (col) {
  const [qx, qy, qz, qw] = col.rotation
  const [px, py, pz] = col.position
  const rot = (x, y, z) => { // quaternion rotation
    const tx = 2 * (qy * z - qz * y); const ty = 2 * (qz * x - qx * z); const tz = 2 * (qx * y - qy * x)
    return [x + qw * tx + (qy * tz - qz * ty), y + qw * ty + (qz * tx - qx * tz), z + qw * tz + (qx * ty - qy * tx)]
  }
  const local = []
  if (col.hull) {
    for (let i = 0; i < col.hull.length; i += 3) local.push([col.hull[i], col.hull[i + 1], col.hull[i + 2]])
  } else {
    const [hx, hy, hz] = col.halfExtents
    for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) local.push([sx * hx, sy * hy, sz * hz])
  }
  let top = -Infinity
  const flat = local.map(([x, y, z]) => {
    const w = rot(x, y, z)
    top = Math.max(top, py + w[1])
    return [px + w[0], pz + w[2]]
  })
  // 2D convex hull (monotone chain)
  flat.sort((a, b) => a[0] - b[0] || a[1] - b[1])
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
  const half = (list) => {
    const h = []
    for (const p of list) {
      while (h.length >= 2 && cross(h[h.length - 2], h[h.length - 1], p) <= 0) h.pop()
      h.push(p)
    }
    h.pop()
    return h
  }
  return { pts: [...half(flat), ...half([...flat].reverse())], top }
}

export class Hud {
  constructor () {
    this.el = {
      hud: $('hud'),
      vignette: $('vignette'),
      crosshair: $('crosshair'),
      hitmarker: $('hitmarker'),
      targetName: $('target-name'),
      scoreAllies: $('score-allies'),
      scoreAxis: $('score-axis'),
      timer: $('timer'),
      roundInfo: $('round-info'),
      markers: $('sd-markers'),
      usePrompt: $('use-prompt'),
      act: $('act'),
      actLabel: $('act-label'),
      actFill: $('act-fill'),
      centerMsg: $('center-msg'),
      notices: $('notices'),
      killfeed: $('killfeed'),
      compass: $('compass'),
      healthFill: $('health-fill'),
      healthNum: $('health-num'),
      healthLabel: $('health-label'),
      gunMark: $('gun-mark'),
      weaponName: $('weapon-name'),
      ammoMag: $('ammo-mag'),
      ammoReserve: $('ammo-reserve'),
      ammoBullets: $('ammo-bullets'),
      nades: $('nades'),
      fuse: $('fuse'),
      fuseFill: $('fuse-fill'),
      weaponHint: $('weapon-hint'),
      pickup: $('pickup'),
      death: $('death'),
      deathTitle: $('death-title'),
      deathBy: $('death-by'),
      deathRespawn: $('death-respawn'),
      deathNext: $('death-next'),
      scope: $('scope'),
      scoreboard: $('scoreboard'),
      netstat: $('netstat'),
      pause: $('pause'),
      dmgDirs: $('damage-dirs')
    }
    this.compassCtx = this.el.compass.getContext('2d')
    this.hitT = 0
    this.flashT = 0
    this.last = {}
    this.centerTimer = 0
    this.mapImage = null
    this.marks = new Map() // marker key -> element
  }

  show (v) { this.el.hud.classList.toggle('hidden', !v) }

  set (key, value, fn) {
    if (this.last[key] === value) return
    this.last[key] = value
    fn(value)
  }

  setTeam (team) {
    document.querySelectorAll('#topbar .team').forEach((e) => e.classList.toggle('mine', e.classList.contains(team)))
  }

  // max, label: the tank's armour while driving
  health (hp, alive, max = PLAYER.maxHealth, label = 'HEALTH') {
    const v = Math.max(0, Math.round(hp))
    this.set('hplabel', label, (l) => { this.el.healthLabel.textContent = l })
    this.set('hp', `${v}/${max}`, () => {
      this.el.healthNum.textContent = v
      this.el.healthFill.style.width = `${(v / max) * 100}%`
      this.el.healthFill.classList.toggle('low', v <= max * 0.35)
    })
    const pain = alive && max === PLAYER.maxHealth ? Math.max(0, 1 - hp / 70) : 0
    const op = Math.min(1, pain * 0.9 + this.flashT * 2.2)
    this.set('vig', op.toFixed(2), (s) => { this.el.vignette.style.opacity = s })
  }

  weapon (ws) {
    const w = WEAPONS[ws.id]
    const a = ws.clip
    this.set('wname', w.name, (v) => { this.el.weaponName.textContent = v })
    this.set('mag', a.mag, (v) => {
      this.el.ammoMag.textContent = v
      this.el.ammoMag.classList.toggle('low', v <= Math.ceil(w.mag * 0.25))
    })
    this.set('res', a.reserve, (v) => { this.el.ammoReserve.textContent = v })
    this.set('nades', ws.grenades, (n) => {
      const html = []
      for (let i = 0; i < GRENADE.count; i++) html.push(`<i${i >= n ? ' class="spent"' : ''}></i>`)
      this.el.nades.innerHTML = html.join('')
    })
    const fuse = ws.cooking ? Math.round(Math.max(0, 1 - ws.cookT / GRENADE.fuse) * 100) : -1
    this.set('fuse', fuse, (v) => {
      this.el.fuse.classList.toggle('show', v >= 0)
      this.el.fuse.classList.toggle('low', v >= 0 && v < 30)
      this.el.fuseFill.style.width = `${Math.max(0, v)}%`
    })
    const bkey = `${ws.id}:${a.mag}`
    this.set('bullets', bkey, () => {
      const html = []
      for (let i = 0; i < w.mag; i++) html.push(`<i${i >= a.mag ? ' class="spent"' : ''}></i>`)
      this.el.ammoBullets.innerHTML = html.join('')
      this.el.ammoBullets.classList.toggle('dense', w.mag > 35) // belts
    })
    let hint = ''
    if (ws.reloading) hint = 'Reloading…'
    else if (a.mag === 0 && a.reserve === 0) hint = 'Out of ammo'
    else if (a.mag <= Math.ceil(w.mag * 0.25)) hint = 'Press R to reload'
    this.set('hint', hint, (v) => { this.el.weaponHint.textContent = v })
  }

  // the tank's gun in place of the weapon panel; gun: its name, or null on foot. ready: 0..1 through the reload
  tankGun (gun, ready = 1) {
    this.vehicle(!!gun)
    if (!gun) return
    this.set('wname', gun, (v) => { this.el.weaponName.textContent = v })
    const left = ready < 1 ? `Loading ${Math.round(ready * 100)}%` : 'Ready'
    this.set('mag', left, (v) => { this.el.ammoMag.textContent = v; this.el.ammoMag.classList.toggle('low', ready < 1) })
    this.set('hint', 'F to get out', (v) => { this.el.weaponHint.textContent = v })
  }

  // the motorcycle's name and condition (0..1) in place of the weapon panel
  bike (name, condition) {
    this.vehicle(true)
    this.set('wname', name, (v) => { this.el.weaponName.textContent = v })
    const pct = Math.max(0, Math.round(condition * 100))
    this.set('mag', `${pct}%`, (v) => { this.el.ammoMag.textContent = v; this.el.ammoMag.classList.toggle('low', pct <= 35) })
    this.set('hint', 'F to get off', (v) => { this.el.weaponHint.textContent = v })
  }

  vehicle (on) {
    this.set('driving', on, (v) => {
      this.el.hud.classList.toggle('driving', v)
      if (!v) { this.last.wname = this.last.hint = this.last.mag = this.last.res = undefined }
    })
  }

  // where the gun actually points, in screen px (null when off screen); ready: loaded
  gunSight (x, y, ready) {
    const el = this.el.gunMark
    this.set('gunmark', x != null, (v) => el.classList.toggle('show', v))
    if (x == null) return
    this.set('gunready', ready, (v) => el.classList.toggle('ready', v))
    el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`
  }

  // gain: weapon id -> rounds picked up
  pickup (gain) {
    const el = this.el.pickup
    el.textContent = Object.entries(gain).map(([id, n]) => `+${n} ${WEAPONS[id]?.name ?? id}`).join('  ·  ')
    el.classList.remove('show')
    void el.offsetWidth // restart the fade
    el.classList.add('show')
  }

  // gap in px from spread (radians) and current vertical FOV (degrees)
  crosshair (spread, fovDeg, visible, target) {
    const h = window.innerHeight
    const px = Math.tan(spread) / Math.tan((fovDeg * Math.PI) / 360) * (h / 2)
    const gap = Math.round(Math.max(4, Math.min(120, px + 3)))
    this.set('xgap', gap, (g) => this.el.crosshair.style.setProperty('--crosshair-gap', `${g}px`))
    this.set('xvis', visible, (v) => { this.el.crosshair.style.opacity = v ? '1' : '0' })
    const cls = target ? (target.friendly ? 'friend' : 'enemy') : ''
    this.set('xcls', cls, (c) => { this.el.crosshair.className = c })
    const tn = target ? `${target.friendly ? 'f' : 'e'}:${target.name}` : ''
    this.set('tname', tn, () => {
      this.el.targetName.textContent = target ? target.name : ''
      this.el.targetName.className = cls
    })
  }

  hit (kill) {
    this.hitT = kill ? 0.45 : 0.22
    this.el.hitmarker.classList.toggle('kill', !!kill)
  }

  damageFlash (fromAngle) {
    this.flashT = 0.35
    if (fromAngle != null) {
      const d = document.createElement('div')
      d.className = 'dd'
      d.style.transform = `rotate(${fromAngle}rad)`
      this.el.dmgDirs.appendChild(d)
      setTimeout(() => d.remove(), 1500)
    }
  }

  scores (match, myTeam) {
    this.set('sa', match.scores.allies, (v) => { this.el.scoreAllies.textContent = v })
    this.set('sx', match.scores.axis, (v) => { this.el.scoreAxis.textContent = v })
  }

  timer (secondsLeft, low) {
    const s = Math.max(0, Math.ceil(secondsLeft))
    const txt = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
    this.set('timer', txt, (v) => { this.el.timer.textContent = v })
    this.set('timerlow', low, (v) => this.el.timer.classList.toggle('low', v))
  }

  // html: the Search and Destroy round line under the scores ('' in Team Deathmatch)
  roundInfo (html, bomb) {
    this.set('round', html, (v) => { this.el.roundInfo.innerHTML = v })
    this.set('roundbomb', bomb, (v) => this.el.roundInfo.classList.toggle('bomb', v))
  }

  usePrompt (html) {
    this.set('use', html, (v) => { this.el.usePrompt.innerHTML = v })
  }

  // frac: 0..1 through planting or defusing, or -1 when doing neither
  act (frac, label) {
    this.set('act', frac >= 0, (v) => this.el.act.classList.toggle('show', v))
    if (frac < 0) return
    this.set('actlabel', label, (v) => { this.el.actLabel.textContent = v })
    this.el.actFill.style.width = `${Math.round(Math.min(1, frac) * 100)}%`
  }

  // list: [{ key, x, y (screen px), text, sub, cls }] for the sites and the bomb in view
  markers (list) {
    const seen = new Set()
    for (const m of list) {
      seen.add(m.key)
      let el = this.marks.get(m.key)
      if (!el) {
        el = document.createElement('div')
        this.el.markers.appendChild(el)
        this.marks.set(m.key, el)
      }
      const cls = `sd-mark ${m.cls}`
      if (el.className !== cls) el.className = cls
      const html = `${esc(m.text)}<small>${esc(m.sub)}</small>`
      if (el.dataset.html !== html) { el.dataset.html = html; el.innerHTML = html }
      el.style.left = `${m.x.toFixed(1)}px`
      el.style.top = `${m.y.toFixed(1)}px`
    }
    for (const [key, el] of this.marks) if (!seen.has(key)) { el.remove(); this.marks.delete(key) }
  }

  center (html, seconds = 2.5) {
    this.el.centerMsg.innerHTML = html
    this.el.centerMsg.classList.add('show')
    this.centerTimer = seconds
  }

  notice (text) {
    const d = document.createElement('div')
    d.textContent = text
    this.el.notices.appendChild(d)
    while (this.el.notices.children.length > 4) this.el.notices.firstChild.remove()
    setTimeout(() => d.remove(), 5000)
  }

  killfeed (killer, victim, weapon, headshot, myId) {
    const d = document.createElement('div')
    d.className = 'kf'
    const name = (p) => p ? `<span class="${p.team}${p.id === myId ? ' me' : ''}">${esc(p.name)}</span>` : '<span>World</span>'
    const w = weapon === GRENADE.id ? GRENADE.name : weapon === KNIFE.id ? KNIFE.name[killer?.team] ?? 'Knife'
      : weapon === SD.bomb.id ? SD.bomb.name : weapon === TANK.gunId ? TANK.sides[killer?.team]?.gunName ?? 'Tank gun'
        : weapon === TANK.crushId ? 'Tracks' : WEAPONS[weapon]?.name || weapon
    if (killer && killer.id !== victim?.id) {
      d.innerHTML = `${name(killer)}<span class="wpn">${esc(w)}</span>${headshot ? '<span class="hs">HEADSHOT</span>' : ''}${name(victim)}`
    } else {
      d.innerHTML = `${name(victim)}<span class="wpn">died</span>`
    }
    this.el.killfeed.appendChild(d)
    while (this.el.killfeed.children.length > 6) this.el.killfeed.firstChild.remove()
    setTimeout(() => d.remove(), 7000)
  }

  scope (on) {
    this.set('scope', on, (v) => this.el.scope.classList.toggle('hidden', !v))
  }

  // status: replaces the respawn countdown (Search and Destroy has none)
  death (show, killerName, secondsLeft, nextText = '', title = 'You were killed', status = null) {
    this.el.death.classList.toggle('hidden', !show)
    if (!show) return
    this.set('deathtitle', title, (v) => { this.el.deathTitle.textContent = v })
    this.set('deathby', killerName, (v) => { this.el.deathBy.textContent = v ? `by ${v}` : '' })
    this.set('deathnext', nextText, (v) => { this.el.deathNext.textContent = v })
    const s = Math.max(0, Math.ceil(secondsLeft))
    const txt = status ?? (s > 0 ? `Respawning in ${s}…` : 'Respawning…')
    this.set('respawn', txt, (v) => { this.el.deathRespawn.textContent = v })
  }

  scoreboard (show, roster, match, myId, aliveSet) {
    this.el.scoreboard.classList.toggle('hidden', !show)
    if (!show) return
    const rows = (team) => [...roster.values()].filter((p) => p.team === team).sort((a, b) => b.k - a.k || a.d - b.d)
      .map((p) => `<tr class="${p.id === myId ? 'me' : ''} ${aliveSet.has(p.id) ? '' : 'dead'}"><td class="name">${esc(p.name)}${p.bot ? '<span class="bot">BOT</span>' : ''}</td><td class="n">${p.k}</td><td class="n">${p.d}</td><td class="n">${p.bot ? '–' : p.ping}</td></tr>`).join('')
    const table = (team) => `<table class="${team}"><caption>${TEAMS[team].name} &nbsp;${match.scores[team]}</caption><thead><tr><th>Name</th><th class="n">K</th><th class="n">D</th><th class="n">Ping</th></tr></thead><tbody>${rows(team)}</tbody></table>`
    const sd = match.mode === 'sd'
    const goal = sd ? `round ${match.round} &middot; first to ${match.scoreLimit} rounds` : `first to ${match.scoreLimit}`
    const html = `<div class="sb-head"><div class="t">${MODES[match.mode ?? 'tdm'].name}</div><div class="s">Rudarska ulica &middot; ${goal}</div></div><div class="sb-cols">${table('allies')}${table('axis')}</div>`
    this.set('sbhtml', html, (v) => { this.el.scoreboard.innerHTML = v })
  }

  netstat (ping, fps) {
    const t = `${fps} fps · ${Math.round(ping)} ms`
    this.set('net', t, (v) => { this.el.netstat.textContent = v })
  }

  pause (v) { this.el.pause.classList.toggle('hidden', !v) }

  // pre-renders a top-down footprint of the map colliders for the minimap
  buildMinimap (mapData) {
    const b = mapData.bounds
    const scale = 6 // px per metre
    const w = Math.ceil((b.max[0] - b.min[0]) * scale)
    const h = Math.ceil((b.max[2] - b.min[2]) * scale)
    const c = document.createElement('canvas')
    c.width = w; c.height = h
    const g = c.getContext('2d')
    g.fillStyle = 'rgba(90, 92, 80, 0.55)'
    g.fillRect(0, 0, w, h)
    const sorted = mapData.colliders.filter((col) => !col.clip).map(outline).sort((a, b2) => a.top - b2.top)
    for (const { pts, top } of sorted) {
      if (top < 0.35) continue
      // three bands: low cover, raised ground / walls (park, retaining wall), buildings
      g.fillStyle = top > 6 ? 'rgba(28, 27, 22, 0.92)' : top > 1.6 ? 'rgba(96, 104, 78, 0.9)' : 'rgba(150, 144, 120, 0.85)'
      g.beginPath()
      pts.forEach(([x, z], i) => g[i ? 'lineTo' : 'moveTo']((x - b.min[0]) * scale, (z - b.min[2]) * scale))
      g.fill()
    }
    this.mapImage = { canvas: c, scale, x0: b.min[0], z0: b.min[2] }
  }

  // rotating minimap: player at centre, view direction up; sites: [{ x, z, text, color }] pinned to the rim when far
  compass (me, yaw, players, sites = []) {
    const g = this.compassCtx
    const S = this.el.compass.width
    g.clearRect(0, 0, S, S)
    if (!this.mapImage) return
    const m = this.mapImage
    const zoom = 1.6 // canvas px per minimap px
    g.save()
    g.translate(S / 2, S / 2)
    g.rotate(yaw)
    g.scale(zoom, zoom)
    g.translate(-(me.x - m.x0) * m.scale, -(me.z - m.z0) * m.scale)
    g.drawImage(m.canvas, 0, 0)
    g.restore()

    // other players
    for (const p of players) {
      const dx = p.x - me.x; const dz = p.z - me.z
      const c = Math.cos(yaw); const s = Math.sin(yaw)
      let sx = (dx * c - dz * s) * m.scale * zoom
      let sy = (dx * s + dz * c) * m.scale * zoom
      const r = Math.hypot(sx, sy)
      const maxR = S / 2 - 8
      if (r > maxR) { if (!p.friendly) continue; sx *= maxR / r; sy *= maxR / r }
      g.fillStyle = p.friendly ? '#9fd36a' : '#ff4b3a'
      g.beginPath()
      if (p.tank) g.rect(S / 2 + sx - 7, S / 2 + sy - 7, 14, 14)
      else if (p.bike) g.rect(S / 2 + sx - 4, S / 2 + sy - 4, 8, 8)
      else g.arc(S / 2 + sx, S / 2 + sy, p.friendly ? 4 : 5, 0, Math.PI * 2)
      g.fill()
      g.strokeStyle = 'rgba(0,0,0,.7)'
      g.lineWidth = 1.5
      g.stroke()
    }
    g.font = '600 16px "Stardos Stencil", Oswald, sans-serif'
    g.textAlign = 'center'; g.textBaseline = 'middle'
    for (const st of sites) {
      const dx = st.x - me.x; const dz = st.z - me.z
      const c = Math.cos(yaw); const s = Math.sin(yaw)
      let sx = (dx * c - dz * s) * m.scale * zoom
      let sy = (dx * s + dz * c) * m.scale * zoom
      const r = Math.hypot(sx, sy)
      const maxR = S / 2 - 12
      if (r > maxR) { sx *= maxR / r; sy *= maxR / r }
      g.lineWidth = 3
      g.strokeStyle = 'rgba(0,0,0,.8)'
      g.strokeText(st.text, S / 2 + sx, S / 2 + sy)
      g.fillStyle = st.color
      g.fillText(st.text, S / 2 + sx, S / 2 + sy)
    }
    // self arrow
    g.fillStyle = '#f2e7c4'
    g.strokeStyle = 'rgba(0,0,0,.8)'
    g.beginPath()
    g.moveTo(S / 2, S / 2 - 9); g.lineTo(S / 2 + 6, S / 2 + 6); g.lineTo(S / 2, S / 2 + 2); g.lineTo(S / 2 - 6, S / 2 + 6)
    g.closePath(); g.fill(); g.stroke()
    // north marker on the rim (real north: 58 deg counter-clockwise from the map's -Z axis)
    const R = S / 2 - 12
    const c = Math.cos(yaw); const sn = Math.sin(yaw)
    const nx = (NORTH_X * c - NORTH_Z * sn) * R
    const ny = (NORTH_X * sn + NORTH_Z * c) * R
    g.font = '600 15px Oswald, sans-serif'
    g.textAlign = 'center'; g.textBaseline = 'middle'
    g.fillStyle = '#d9b55a'
    g.fillText('N', S / 2 + nx, S / 2 + ny)
  }

  update (dt) {
    if (this.hitT > 0) {
      this.hitT -= dt
      this.el.hitmarker.style.opacity = Math.max(0, Math.min(1, this.hitT * 6)).toFixed(2)
    }
    if (this.flashT > 0) this.flashT = Math.max(0, this.flashT - dt)
    if (this.centerTimer > 0) {
      this.centerTimer -= dt
      if (this.centerTimer <= 0) this.el.centerMsg.classList.remove('show')
    }
  }
}

export { PLAYER }
