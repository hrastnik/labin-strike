// DOM HUD: health, ammo, crosshair, hitmarkers, killfeed, scores/timer, scoreboard, compass minimap.
import { WEAPONS, TEAMS, PLAYER } from '@shared/constants.js'

// compass north in map (x, z) coordinates
const NORTH_X = -0.8502
const NORTH_Z = -0.5264

const $ = (id) => document.getElementById(id)
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

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
      centerMsg: $('center-msg'),
      notices: $('notices'),
      killfeed: $('killfeed'),
      compass: $('compass'),
      healthFill: $('health-fill'),
      healthNum: $('health-num'),
      weaponName: $('weapon-name'),
      ammoMag: $('ammo-mag'),
      ammoReserve: $('ammo-reserve'),
      ammoBullets: $('ammo-bullets'),
      weaponHint: $('weapon-hint'),
      death: $('death'),
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

  health (hp, alive) {
    const v = Math.max(0, Math.round(hp))
    this.set('hp', v, () => {
      this.el.healthNum.textContent = v
      this.el.healthFill.style.width = `${v}%`
      this.el.healthFill.classList.toggle('low', v <= 35)
    })
    const pain = alive ? Math.max(0, 1 - hp / 70) : 0
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

  timer (secondsLeft, state) {
    const s = Math.max(0, Math.ceil(secondsLeft))
    const txt = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
    this.set('timer', txt, (v) => { this.el.timer.textContent = v })
    this.set('timerlow', state === 'playing' && s <= 60, (v) => this.el.timer.classList.toggle('low', v))
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
    const w = WEAPONS[weapon]?.name || weapon
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

  death (show, killerName, secondsLeft, nextText = '') {
    this.el.death.classList.toggle('hidden', !show)
    if (!show) return
    this.set('deathby', killerName, (v) => { this.el.deathBy.textContent = v ? `by ${v}` : '' })
    this.set('deathnext', nextText, (v) => { this.el.deathNext.textContent = v })
    const s = Math.max(0, Math.ceil(secondsLeft))
    this.set('respawn', s, (v) => { this.el.deathRespawn.textContent = v > 0 ? `Respawning in ${v}…` : 'Respawning…' })
  }

  scoreboard (show, roster, match, myId, aliveSet) {
    this.el.scoreboard.classList.toggle('hidden', !show)
    if (!show) return
    const rows = (team) => [...roster.values()].filter((p) => p.team === team).sort((a, b) => b.k - a.k || a.d - b.d)
      .map((p) => `<tr class="${p.id === myId ? 'me' : ''} ${aliveSet.has(p.id) ? '' : 'dead'}"><td class="name">${esc(p.name)}${p.bot ? '<span class="bot">BOT</span>' : ''}</td><td class="n">${p.k}</td><td class="n">${p.d}</td><td class="n">${p.bot ? '–' : p.ping}</td></tr>`).join('')
    const table = (team) => `<table class="${team}"><caption>${TEAMS[team].name} &nbsp;${match.scores[team]}</caption><thead><tr><th>Name</th><th class="n">K</th><th class="n">D</th><th class="n">Ping</th></tr></thead><tbody>${rows(team)}</tbody></table>`
    const html = `<div class="sb-head"><div class="t">Team Deathmatch</div><div class="s">Rudarska ulica &middot; first to ${match.scoreLimit}</div></div><div class="sb-cols">${table('allies')}${table('axis')}</div>`
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
    const sorted = mapData.colliders.filter((col) => !col.clip).sort((a, b2) => (a.position[1] + a.halfExtents[1]) - (b2.position[1] + b2.halfExtents[1]))
    for (const col of sorted) {
      const [qx, qy, qz, qw] = col.rotation
      const yaw = Math.atan2(2 * (qw * qy + qx * qz), 1 - 2 * (qy * qy + qz * qz))
      const top = col.position[1] + col.halfExtents[1]
      if (top < 0.35) continue
      // three bands: low cover, raised ground / walls (park, retaining wall), buildings
      const shade = top > 6 ? 'rgba(28, 27, 22, 0.92)' : top > 1.6 ? 'rgba(96, 104, 78, 0.9)' : 'rgba(150, 144, 120, 0.85)'
      g.save()
      g.translate((col.position[0] - b.min[0]) * scale, (col.position[2] - b.min[2]) * scale)
      g.rotate(-yaw)
      g.fillStyle = shade
      g.fillRect(-col.halfExtents[0] * scale, -col.halfExtents[2] * scale, col.halfExtents[0] * 2 * scale, col.halfExtents[2] * 2 * scale)
      g.restore()
    }
    this.mapImage = { canvas: c, scale, x0: b.min[0], z0: b.min[2] }
  }

  // rotating minimap: player at centre, view direction up
  compass (me, yaw, players) {
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
      g.arc(S / 2 + sx, S / 2 + sy, p.friendly ? 4 : 5, 0, Math.PI * 2)
      g.fill()
      g.strokeStyle = 'rgba(0,0,0,.7)'
      g.lineWidth = 1.5
      g.stroke()
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
