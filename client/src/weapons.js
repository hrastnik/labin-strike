// Local weapon state: ammo, fire timing, reloads, switching, spread bloom and recoil punch.
// The loadout (which two weapons, which class) always comes from the server's spawn / equip messages.
import { WEAPONS, startingAmmo, reloadDuration } from '@shared/weapons.js'
import { PLAYER } from '@shared/constants.js'

const SLOT_NAMES = ['primary', 'secondary']

export class WeaponSystem {
  constructor () {
    this.loadout = { cls: 'assault', primary: 'stg44', secondary: 'm1911' }
    this.reset()
  }

  reset (loadout) {
    if (loadout) this.loadout = { ...loadout }
    this.slots = [this.loadout.primary, this.loadout.secondary]
    this.ammo = {}
    this.slots.forEach((id, i) => { this.ammo[id] = startingAmmo(this.loadout.cls, id, SLOT_NAMES[i]) })
    this.index = 0
    this.prevIndex = 1
    this.drawT = this.def.drawTime
    this.reloadT = 0
    this.reloadDur = 0
    this.reloadSteps = 0 // rounds / clips pushed in by an incremental reload (for the animation)
    this.cooldown = 0
    this.bloom = 0
    this.punch = { pitch: 0, yaw: 0 }
    this.adsT = 0
    this.triggerHeld = false
    this.lastShotAt = -1e9
    this.events = [] // 'fire' | 'dry' | 'reload' | 'reloaded' | 'switch' | 'ping'
  }

  get id () { return this.slots[this.index] }
  get def () { return WEAPONS[this.id] }
  get reloading () { return this.reloadT > 0 }
  get drawing () { return this.drawT > 0 }
  get clip () { return this.ammo[this.id] }
  // 0..1 progress of working the bolt after a shot, -1 when not cycling
  get cycleFrac () {
    const w = this.def
    if (w.action !== 'bolt' || this.cooldown <= 0) return -1
    return 1 - this.cooldown / (60 / w.rpm)
  }

  switchTo (i) {
    if (i === this.index || i < 0 || i >= this.slots.length) return
    this.prevIndex = this.index
    this.index = i
    this.reloadT = 0
    this.drawT = this.def.drawTime
    this.cooldown = Math.max(this.cooldown, 0)
    this.bloom = 0
    this.events.push('switch')
  }

  startReload () {
    const a = this.clip
    const w = this.def
    if (this.reloading || this.drawing || a.mag >= w.mag || a.reserve <= 0) return false
    this.reloadDur = this.reloadT = reloadDuration(w, a.mag, a.reserve)
    const missing = Math.min(w.mag - a.mag, a.reserve)
    const r = w.reload
    this.reloadSteps = r.style === 'single' ? missing : r.style === 'charger' ? Math.floor(missing / r.clip) + missing % r.clip : 1
    this.events.push('reload')
    return true
  }

  // spread half-angle (rad) given the current movement context
  spread (ctx) {
    const s = this.def.spread
    const ads = this.adsT
    let v = s.hip + (s.ads - s.hip) * ads
    v += s.move * Math.min(1, ctx.speed / PLAYER.walkSpeed) * (1 - 0.6 * ads)
    if (!ctx.grounded) v += s.air
    if (ctx.crouched) v *= s.crouchMul
    return v + this.bloom
  }

  /**
   * ctl: { trigger, triggerPressed, ads, reload, switchTo, alive }
   * ctx: { speed, grounded, crouched }
   * returns number of shots fired this frame
   */
  update (dt, ctl, ctx) {
    if (ctl.switchTo != null) this.switchTo(ctl.switchTo)
    const w = this.def

    const wantAds = ctl.ads && !this.reloading && !this.drawing
    const adsSpeed = 1 / w.adsTime
    this.adsT = Math.max(0, Math.min(1, this.adsT + (wantAds ? 1 : -1) * adsSpeed * dt))

    if (this.drawT > 0) this.drawT = Math.max(0, this.drawT - dt)
    if (this.reloadT > 0) {
      this.reloadT -= dt
      if (this.reloadT <= 0) {
        this.reloadT = 0
        const a = this.clip
        const take = Math.min(w.mag - a.mag, a.reserve)
        a.mag += take
        a.reserve -= take
        this.events.push('reloaded')
      }
    }
    if (ctl.reload) this.startReload()
    // auto-reload an empty magazine once the trigger is released
    if (ctl.alive && !ctl.trigger && this.clip.mag === 0 && this.cooldown <= 0) this.startReload()

    this.cooldown = Math.max(-0.05, this.cooldown - dt)
    this.bloom = Math.max(0, this.bloom - w.spread.recover * dt)
    const rk = Math.exp(-w.recoil.recover * dt)
    this.punch.pitch *= rk
    this.punch.yaw *= rk

    let shots = 0
    const wants = w.auto ? ctl.trigger : ctl.triggerPressed
    if (!wants) this.triggerHeld = false
    if (!ctl.alive || !wants || this.drawing) return 0
    if (this.reloading) {
      // COD-style: firing during reload does nothing; firing an empty gun clicks once
      return 0
    }
    const interval = 60 / w.rpm
    while (this.cooldown <= 0) {
      const a = this.clip
      if (a.mag <= 0) {
        const other = this.ammo[this.slots[1 - this.index]]
        if (!this.triggerHeld) {
          this.events.push('dry')
          if (a.reserve <= 0 && other.mag + other.reserve > 0) { this.triggerHeld = true; this.switchTo(1 - this.index); break }
        }
        this.triggerHeld = true
        if (a.reserve > 0) this.startReload()
        break
      }
      a.mag--
      shots++
      this.cooldown += interval
      this.triggerHeld = true
      this.bloom = Math.min(w.spread.bloomMax, this.bloom + w.spread.bloom * (1 - 0.5 * this.adsT))
      const kick = 1 - 0.35 * this.adsT
      this.punch.pitch += w.recoil.pitch * kick * (0.85 + Math.random() * 0.3)
      this.punch.yaw += w.recoil.yaw * kick * (Math.random() * 2 - 1)
      this.events.push('fire')
      // the M1 Garand throws its empty en-bloc clip out with a ping
      if (a.mag === 0 && w.reload.style === 'enbloc') this.events.push('ping')
      if (!w.auto) break
    }
    if (shots) this.lastShotAt = performance.now()
    return shots
  }

  drainEvents () {
    const e = this.events
    this.events = []
    return e
  }
}
