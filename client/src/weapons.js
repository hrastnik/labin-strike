// Local weapon state: ammo, fire timing, reloads, switching, spread bloom and recoil punch.
// The loadout (which two weapons, which class) always comes from the server's spawn / equip messages.
import { WEAPONS, GRENADE, KNIFE, startingAmmo, reloadDuration } from '@shared/weapons.js'
import { PLAYER } from '@shared/constants.js'

const SLOT_NAMES = ['primary', 'secondary']
const THROW_TIME = GRENADE.windup + GRENADE.recover
const KNIFE_TIME = KNIFE.windup + KNIFE.recover
const SPRINT_TIME = 0.18 // seconds to lower the weapon into the sprint carry, and to raise it again

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
    this.drawT = this.def.drawTime
    this.reloadT = 0
    this.reloadDur = 0
    this.reloadSteps = 0 // rounds / clips pushed in by an incremental reload (for the animation)
    this.cooldown = 0
    this.bloom = 0
    this.punch = { pitch: 0, yaw: 0 }
    this.kick = { pitch: 0, yaw: 0, bloom: 0 }
    this.adsT = 0
    this.sprintT = 0
    this.grenades = GRENADE.count
    this.throwT = 0
    this.cookT = -1 // seconds since the cord was pulled, -1 once the grenade has left the hand
    this.knifeT = 0
    this.triggerHeld = false
    this.lastShotAt = -1e9
    this.events = [] // 'fire' | 'dry' | 'reload' | 'reloaded' | 'switch' | 'ping' | 'windup' | 'throw' | 'swing' | 'stab'
  }

  get id () { return this.slots[this.index] }
  get def () { return WEAPONS[this.id] }
  get reloading () { return this.reloadT > 0 }
  get drawing () { return this.drawT > 0 }
  get throwing () { return this.throwT > 0 }
  // 0..1 through windup, release and recovery; -1 when not throwing
  get throwFrac () { return this.throwing ? 1 - this.throwT / THROW_TIME : -1 }
  get cooking () { return this.cookT >= 0 }
  get knifing () { return this.knifeT > 0 }
  get knifeFrac () { return this.knifing ? 1 - this.knifeT / KNIFE_TIME : -1 }
  // hands full with the grenade or the knife
  get busy () { return this.throwing || this.knifing }
  get clip () { return this.ammo[this.id] }
  // 0..1 progress of working the bolt after a shot, -1 when not cycling
  get cycleFrac () {
    const w = this.def
    if (w.action !== 'bolt' || this.cooldown <= 0) return -1
    return 1 - this.cooldown / (60 / w.rpm)
  }

  switchTo (i) {
    if (i === this.index || i < 0 || i >= this.slots.length) return
    this.index = i
    this.reloadT = 0
    this.drawT = this.def.drawTime
    this.cooldown = Math.max(this.cooldown, 0)
    this.bloom = 0
    this.kick = { pitch: 0, yaw: 0, bloom: 0 }
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

  // rounds from an ammo can (weapon id -> count) go into reserve
  addAmmo (gain) {
    for (const id in gain) if (this.ammo[id]) this.ammo[id].reserve += gain[id]
  }

  // the cord is pulled on pressing G, so once wound up the throw always goes: holding G only delays the release
  updateThrow (dt, ctl) {
    if (!this.throwing) {
      if (!ctl.throwNade || !ctl.alive || this.grenades <= 0 || this.knifing) return
      this.throwT = THROW_TIME
      this.cookT = 0
      this.reloadT = 0
      this.events.push('windup')
      return
    }
    if (this.cooking) {
      this.cookT += dt
      if (this.cookT >= GRENADE.fuse) {
        this.cookT = -1
        this.throwT = 0
        this.grenades--
        this.drawT = this.def.drawTime
        return
      }
    }
    const before = this.throwT
    const hold = this.cooking && ctl.holdNade ? GRENADE.recover + 1e-3 : 0
    this.throwT = Math.max(Math.min(hold, before), this.throwT - dt)
    if (before > GRENADE.recover && this.throwT <= GRENADE.recover) {
      this.grenades--
      this.cookT = -1
      this.events.push('throw')
    }
    if (!this.throwing) this.drawT = this.def.drawTime
  }

  updateKnife (dt, ctl) {
    if (!this.knifing) {
      if (!ctl.knife || !ctl.alive || this.throwing) return
      this.knifeT = KNIFE_TIME
      this.reloadT = 0
      this.events.push('swing')
      return
    }
    if (!ctl.alive) { this.knifeT = 0; return }
    const before = this.knifeT
    this.knifeT = Math.max(0, this.knifeT - dt)
    if (before > KNIFE.recover && this.knifeT <= KNIFE.recover) this.events.push('stab')
  }

  /**
   * ctl: { trigger, triggerPressed, ads, reload, switchTo, throwNade, holdNade, knife, sprint, alive }
   * ctx: { speed, grounded, crouched }
   * returns number of shots fired this frame
   */
  update (dt, ctl, ctx) {
    if (ctl.switchTo != null && !this.busy) this.switchTo(ctl.switchTo)
    this.updateThrow(dt, ctl)
    this.updateKnife(dt, ctl)
    const w = this.def
    this.sprintT = Math.max(0, Math.min(1, this.sprintT + (ctl.sprint ? dt : -dt) / SPRINT_TIME))
    // weapon down: sprinting, or busy with the grenade or knife
    const lowered = this.sprintT > 0.25 || this.busy

    const wantAds = ctl.ads && !this.reloading && !this.drawing && !lowered
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
    if (ctl.reload && !this.busy) this.startReload()
    // auto-reload an empty magazine once the trigger is released
    if (ctl.alive && !ctl.trigger && !this.busy && this.clip.mag === 0 && this.cooldown <= 0) this.startReload()

    this.cooldown = Math.max(-0.05, this.cooldown - dt)
    this.bloom = Math.max(0, this.bloom - w.spread.recover * dt)
    const rk = Math.exp(-w.recoil.recover * dt)
    this.punch.pitch *= rk
    this.punch.yaw *= rk
    // a shot's own kick lands the frame after it, so the round leaves along the aim the player saw
    this.bloom = Math.min(w.spread.bloomMax, this.bloom + this.kick.bloom)
    this.punch.pitch += this.kick.pitch
    this.punch.yaw += this.kick.yaw
    this.kick = { pitch: 0, yaw: 0, bloom: 0 }

    let shots = 0
    const wants = w.auto ? ctl.trigger : ctl.triggerPressed
    if (!wants) this.triggerHeld = false
    if (!ctl.alive || !wants || this.drawing || lowered) return 0
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
      this.kick.bloom += w.spread.bloom * (1 - 0.5 * this.adsT)
      const kick = 1 - 0.35 * this.adsT
      this.kick.pitch += w.recoil.pitch * kick * (0.85 + Math.random() * 0.3)
      this.kick.yaw += w.recoil.yaw * kick * (Math.random() * 2 - 1)
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
