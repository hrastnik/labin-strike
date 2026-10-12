// Loadout screen: faction, class, primary and sidearm selection with weapon icons and stats.
// It only ever lists the player's own faction; the server re-validates every request anyway.
import * as THREE from 'three'
import { TEAMS } from '@shared/constants.js'
import { WEAPONS, CLASSES, CLASS_IDS, CATEGORY_NAMES, classOptions, sanitizeLoadout, startingAmmo } from '@shared/weapons.js'
import { buildGun } from './gunmodels.js'

const $ = (id) => document.getElementById(id)
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

const FORCES = { allies: 'U.S. Army · British Army', axis: 'Wehrmacht' }

// ------------------------------------------------------------------ icons: side-on renders of the weapon models

let iconRenderer = null
const icons = new Map()

export function iconFor (id) {
  if (icons.has(id)) return icons.get(id)
  let url = ''
  try {
    if (!iconRenderer) {
      const canvas = document.createElement('canvas')
      iconRenderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true })
      iconRenderer.setSize(360, 120, false)
      iconRenderer.outputColorSpace = THREE.SRGBColorSpace
    }
    const scene = new THREE.Scene()
    scene.add(new THREE.HemisphereLight('#f4efe0', '#4a4438', 2.2))
    const key = new THREE.DirectionalLight('#fff4e0', 2.4)
    key.position.set(1, 1.2, 0.3)
    scene.add(key)
    const spec = buildGun(id)
    spec.mag.visible = !spec.magHidden
    scene.add(spec.gun)
    const bb = new THREE.Box3().setFromObject(spec.gun)
    const size = bb.getSize(new THREE.Vector3())
    const c = bb.getCenter(new THREE.Vector3())
    const halfW = Math.max(size.z / 2, (size.y / 2) * 3) * 1.08
    const cam = new THREE.OrthographicCamera(-halfW, halfW, halfW / 3, -halfW / 3, 0.01, 10)
    cam.position.set(c.x + 2, c.y, c.z) // right-hand side, muzzle pointing right
    cam.lookAt(c)
    iconRenderer.setClearColor(0x000000, 0)
    iconRenderer.render(scene, cam)
    url = iconRenderer.domElement.toDataURL('image/png')
    spec.gun.traverse((o) => { if (o.isMesh) o.geometry.dispose() })
  } catch (err) {
    console.warn('weapon icon failed', id, err)
  }
  icons.set(id, url)
  return url
}

// ------------------------------------------------------------------ stats, normalised for the bars

const clamp01 = (v) => Math.max(0, Math.min(1, v))

export function weaponStats (w) {
  return [
    ['Damage', clamp01(w.damage / 110)],
    ['Fire rate', clamp01((Math.log(w.rpm) - Math.log(40)) / (Math.log(1200) - Math.log(40)))],
    ['Accuracy', clamp01(1 - (w.spread.ads / 0.012) * 0.45 - (w.spread.hip / 0.08) * 0.55)],
    ['Range', clamp01((w.falloffEnd * (0.5 + w.falloffMin * 0.5)) / 190)],
    ['Mobility', clamp01((w.moveMul - 0.74) / 0.33)],
    ['Handling', clamp01(1 - (w.reloadTime / 6) * 0.45 - (w.adsTime / 0.36) * 0.3 - (w.drawTime / 1) * 0.25)]
  ]
}

function statBars (w) {
  return weaponStats(w).map(([label, v]) =>
    `<div class="lo-stat"><span>${label}</span><div class="bar"><i style="width:${Math.round(v * 100)}%"></i></div></div>`).join('')
}

const ACTION = { auto: 'Automatic', semi: 'Semi-automatic', bolt: 'Bolt-action' }

// ------------------------------------------------------------------ menu

export class LoadoutMenu {
  constructor ({ onDeploy, onTeam, onClose }) {
    this.el = $('loadout')
    this.onDeploy = onDeploy
    this.onTeam = onTeam
    this.onClose = onClose
    this.team = 'allies'
    this.sel = null
    this.mode = 'deploy' // 'deploy': before spawning | 'change': in the field
    this.isOpen = false
    $('lo-deploy').addEventListener('click', () => this.onDeploy({ ...this.sel }))
    $('lo-switch').addEventListener('click', () => this.onTeam(this.team === 'allies' ? 'axis' : 'allies'))
    $('lo-close').addEventListener('click', () => this.onClose())
    this.el.addEventListener('click', (e) => {
      const b = e.target.closest('[data-pick]')
      if (!b) return
      const [kind, value] = b.dataset.pick.split(':')
      if (kind === 'cls') this.sel = sanitizeLoadout(this.team, { ...this.sel, cls: value, primary: null, secondary: this.sel.secondary })
      else this.sel = sanitizeLoadout(this.team, { ...this.sel, [kind]: value })
      this.render()
    })
  }

  // team and the loadout to preselect; `current` is what the soldier carries now (or will at next spawn)
  open (team, loadout, mode, current = null) {
    this.team = team
    this.sel = sanitizeLoadout(team, loadout)
    this.current = current
    this.mode = mode
    this.isOpen = true
    this.status('')
    this.el.classList.remove('hidden')
    this.render()
  }

  close () {
    this.isOpen = false
    this.el.classList.add('hidden')
  }

  status (text, error = false) {
    const s = $('lo-status')
    s.textContent = text
    s.classList.toggle('error', error)
  }

  render () {
    const team = this.team
    const t = TEAMS[team]
    const other = team === 'allies' ? 'axis' : 'allies'
    this.el.dataset.team = team
    $('lo-team').textContent = t.name
    $('lo-force').textContent = FORCES[team]
    $('lo-switch').textContent = `Switch to ${TEAMS[other].name}`
    $('lo-deploy').textContent = this.mode === 'deploy' ? 'Deploy' : 'Confirm loadout'
    $('lo-close').classList.toggle('hidden', this.mode === 'deploy')

    const sel = this.sel
    $('lo-classes').innerHTML = CLASS_IDS.map((id) => {
      const c = CLASSES[id]
      const o = classOptions(team, id)
      const names = o.primary.map((w) => WEAPONS[w].name).join(' / ')
      const cur = this.current?.cls === id ? '<span class="lo-cur">current</span>' : ''
      return `<button class="lo-class${sel.cls === id ? ' sel' : ''}" data-pick="cls:${id}">
        <b>${esc(c.name)}${cur}</b><small>${esc(names)}</small></button>`
    }).join('')

    const o = classOptions(team, sel.cls)
    const card = (slot, id) => {
      const w = WEAPONS[id]
      const a = startingAmmo(sel.cls, id, slot)
      const img = iconFor(id)
      return `<button class="lo-weapon${sel[slot] === id ? ' sel' : ''}" data-pick="${slot}:${id}">
        ${img ? `<img src="${img}" alt="" draggable="false">` : '<div class="noimg"></div>'}
        <b>${esc(w.name)}</b><small>${esc(CATEGORY_NAMES[w.category])} · ${a.mag} + ${a.reserve}</small></button>`
    }
    $('lo-primary').innerHTML = o.primary.map((id) => card('primary', id)).join('')
    $('lo-secondary').innerHTML = o.secondary.map((id) => card('secondary', id)).join('')

    const p = WEAPONS[sel.primary]
    const s = WEAPONS[sel.secondary]
    const pa = startingAmmo(sel.cls, sel.primary, 'primary')
    const sa = startingAmmo(sel.cls, sel.secondary, 'secondary')
    const c = CLASSES[sel.cls]
    const facts = (w, a) => `<div class="lo-facts">
        <span><b>${a.mag}</b> magazine</span><span><b>${a.reserve}</b> reserve</span>
        <span><b>${w.rpm}</b> rpm</span><span><b>${w.reloadTime.toFixed(1)} s</b> reload</span>
        <span><b>${w.velocity}</b> m/s</span><span><b>${Math.round(w.falloffStart)}–${Math.round(w.falloffEnd)} m</b> falloff</span>
      </div>`
    $('lo-detail').innerHTML = `
      <div class="lo-class-desc"><b>${esc(c.name)}</b> · ${esc(c.desc)}</div>
      <div class="lo-big"><img src="${iconFor(sel.primary)}" alt="" draggable="false"></div>
      <div class="lo-wname">${esc(p.name)} <small>${esc(ACTION[p.action])} ${esc(CATEGORY_NAMES[p.category].toLowerCase())}</small></div>
      <div class="lo-desc">${esc(p.desc)}</div>
      ${statBars(p)}
      ${facts(p, pa)}
      <div class="lo-sub">Sidearm · <b>${esc(s.name)}</b> <small>${sa.mag} + ${sa.reserve} · ${s.damage} dmg</small></div>
      <div class="lo-sub">Equipment · ${c.kit.map(esc).join(', ')}</div>`

    if (this.mode === 'change' && this.current && sel.cls === this.current.cls && sel.primary === this.current.primary && sel.secondary === this.current.secondary) {
      $('lo-deploy').textContent = 'Keep loadout'
    }
  }
}
