// Procedural WebAudio (the headshot cue is the one recorded clip): gunshots (local + spatialised remote), reload/dry clicks, knife, pickups, footsteps, hit/kill/headshot cues, cats,
// tank guns and the engines of the tank or motorcycle we drive.
// Each weapon's report is shaped by its fx.sound profile in shared/weapons.js.
import { WEAPONS } from '@shared/weapons.js'

const DEFAULT_SOUND = WEAPONS.stg44.fx.sound

export class Audio {
  constructor () {
    this.ctx = null
    this.enabled = true
    this.volume = 0.6
  }

  // must be called from a user gesture
  unlock () {
    if (this.ctx) { if (this.ctx.state === 'suspended') this.ctx.resume(); return }
    const AC = window.AudioContext || window.webkitAudioContext
    if (!AC) { this.enabled = false; return }
    this.ctx = new AC()
    this.master = this.ctx.createGain()
    this.master.gain.value = this.volume
    const comp = this.ctx.createDynamicsCompressor()
    comp.threshold.value = -14
    comp.ratio.value = 6
    this.master.connect(comp)
    comp.connect(this.ctx.destination)
    this.noise = this.makeNoise(1.5)
    this.brown = this.makeBrown(1.5)
    fetch('/assets/sounds/headshot.wav')
      .then((r) => r.arrayBuffer())
      .then((b) => this.ctx.decodeAudioData(b))
      .then((clip) => { this.headshotClip = clip })
      .catch(() => {})
  }

  makeNoise (sec) {
    const ctx = this.ctx
    const b = ctx.createBuffer(1, ctx.sampleRate * sec, ctx.sampleRate)
    const d = b.getChannelData(0)
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1
    return b
  }

  makeBrown (sec) {
    const ctx = this.ctx
    const b = ctx.createBuffer(1, ctx.sampleRate * sec, ctx.sampleRate)
    const d = b.getChannelData(0)
    let last = 0
    for (let i = 0; i < d.length; i++) {
      last = (last + 0.02 * (Math.random() * 2 - 1)) / 1.02
      d[i] = last * 3.5
    }
    return b
  }

  setListener (pos, fwd) {
    if (!this.ctx) return
    const l = this.ctx.listener
    const t = this.ctx.currentTime
    if (l.positionX) {
      l.positionX.setValueAtTime(pos.x, t); l.positionY.setValueAtTime(pos.y, t); l.positionZ.setValueAtTime(pos.z, t)
      l.forwardX.setValueAtTime(fwd.x, t); l.forwardY.setValueAtTime(fwd.y, t); l.forwardZ.setValueAtTime(fwd.z, t)
      l.upX.setValueAtTime(0, t); l.upY.setValueAtTime(1, t); l.upZ.setValueAtTime(0, t)
    } else {
      l.setPosition(pos.x, pos.y, pos.z)
      l.setOrientation(fwd.x, fwd.y, fwd.z, 0, 1, 0)
    }
  }

  out (pos) {
    if (!pos) return this.master
    const p = this.ctx.createPanner()
    p.panningModel = 'HRTF'
    p.distanceModel = 'inverse'
    p.refDistance = 4
    p.rolloffFactor = 1.1
    p.maxDistance = 400
    if (p.positionX) { p.positionX.value = pos.x; p.positionY.value = pos.y; p.positionZ.value = pos.z } else p.setPosition(pos.x, pos.y, pos.z)
    p.connect(this.master)
    return p
  }

  // weapon: weapon id; pos null = local (non-spatial); dist used for muffling distant shots
  shot (weapon, pos = null, dist = 0) {
    if (!this.ctx || !this.enabled) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const dest = this.out(pos)
    const far = Math.min(1, dist / 90)
    const snd = (Object.hasOwn(WEAPONS, weapon) && WEAPONS[weapon].fx.sound) || DEFAULT_SOUND

    // crack: filtered noise burst
    const n = ctx.createBufferSource()
    n.buffer = this.noise
    n.playbackRate.value = 0.9 + Math.random() * 0.2
    const bp = ctx.createBiquadFilter()
    bp.type = 'lowpass'
    bp.frequency.setValueAtTime(snd.crack * (1 - far * 0.8), t)
    bp.frequency.exponentialRampToValueAtTime(snd.crackEnd, t + 0.18)
    const g = ctx.createGain()
    const vol = (pos ? 1.0 : 0.85) * snd.vol
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(vol, t + 0.003)
    g.gain.exponentialRampToValueAtTime(0.0001, t + snd.decay + far * 0.3)
    n.connect(bp); bp.connect(g); g.connect(dest)
    n.start(t, Math.random() * 0.5, 0.8)

    // thump: pitched-down sine body
    const o = ctx.createOscillator()
    o.type = 'sine'
    o.frequency.setValueAtTime(snd.body, t)
    o.frequency.exponentialRampToValueAtTime(40, t + 0.14)
    const og = ctx.createGain()
    og.gain.setValueAtTime((pos ? 0.6 : 0.9) * snd.vol, t)
    og.gain.exponentialRampToValueAtTime(0.0001, t + 0.16)
    o.connect(og); og.connect(dest)
    o.start(t); o.stop(t + 0.2)

    // tail: low rumble reflecting off the buildings
    const r = ctx.createBufferSource()
    r.buffer = this.brown
    const rg = ctx.createGain()
    rg.gain.setValueAtTime(0.0001, t)
    rg.gain.exponentialRampToValueAtTime(snd.tail + far * 0.4, t + 0.02)
    rg.gain.exponentialRampToValueAtTime(0.0001, t + 0.7 + Math.max(0, snd.tail - 0.35) * 0.6 + far * 0.5)
    r.connect(rg); rg.connect(dest)
    r.start(t, Math.random(), 1.3)
  }

  click (freq = 2200, vol = 0.25, dur = 0.03, when = 0) {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime + when
    const n = ctx.createBufferSource()
    n.buffer = this.noise
    const f = ctx.createBiquadFilter()
    f.type = 'bandpass'
    f.frequency.value = freq
    f.Q.value = 4
    const g = ctx.createGain()
    g.gain.setValueAtTime(vol, t)
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur)
    n.connect(f); f.connect(g); g.connect(this.master)
    n.start(t, Math.random(), dur + 0.02)
  }

  dry () { this.click(3200, 0.35, 0.025) }

  // timings follow the viewmodel's reload animation for each style
  reload (weapon, duration, steps = 1) {
    const w = WEAPONS[weapon]
    const style = w?.reload.style || 'mag'
    if (style === 'charger' || style === 'single') {
      this.click(1700, 0.3, 0.05, duration * 0.04) // bolt up
      this.click(1200, 0.35, 0.06, duration * 0.12) // bolt back
      const n = Math.max(1, steps)
      for (let i = 0; i < n; i++) this.click(style === 'single' ? 2300 : 1500, 0.32, 0.07, duration * (0.15 + 0.68 * (i + 0.6) / n))
      this.click(1300, 0.38, 0.06, duration * 0.88) // bolt forward
      this.click(2100, 0.32, 0.04, duration * 0.95) // and down
    } else if (style === 'enbloc') {
      this.click(1600, 0.3, 0.05, duration * 0.3)
      this.click(1300, 0.4, 0.05, duration * 0.58) // clip seated
      this.click(950, 0.5, 0.07, duration * 0.73) // bolt slams home
    } else if (style === 'belt') {
      this.click(1500, 0.35, 0.06, duration * 0.15) // cover open
      this.click(900, 0.4, 0.09, duration * 0.36) // box off
      this.click(1000, 0.4, 0.09, duration * 0.6) // box on
      this.click(1800, 0.3, 0.05, duration * 0.66) // belt laid
      this.click(1200, 0.45, 0.06, duration * 0.78) // cover shut
      this.click(1100, 0.4, 0.07, duration * 0.9) // charge
    } else {
      // mag out, mag in, bolt/slide
      this.click(1400, 0.3, 0.05, duration * 0.2)
      this.click(1800, 0.35, 0.05, duration * 0.62)
      this.click(2600, 0.4, 0.04, duration * 0.85)
      if (w?.category !== 'pistol') this.click(1100, 0.35, 0.06, duration * 0.9)
    }
  }

  // working a bolt-action between shots
  bolt (cycle) {
    this.click(1700, 0.22, 0.04, cycle * 0.12)
    this.click(1150, 0.3, 0.06, cycle * 0.35)
    this.click(1350, 0.32, 0.05, cycle * 0.6)
    this.click(2100, 0.24, 0.04, cycle * 0.8)
  }

  // the M1 Garand's empty en-bloc clip
  ping () {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime + 0.03
    for (const [f, v] of [[3150, 0.11], [4720, 0.05], [6900, 0.025]]) {
      const o = ctx.createOscillator()
      o.type = 'sine'
      o.frequency.setValueAtTime(f, t)
      const g = ctx.createGain()
      g.gain.setValueAtTime(0.0001, t)
      g.gain.exponentialRampToValueAtTime(v, t + 0.004)
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.55)
      o.connect(g); g.connect(this.master)
      o.start(t); o.stop(t + 0.6)
    }
  }

  weaponSwitch () { this.click(1600, 0.2, 0.05); this.click(2400, 0.2, 0.03, 0.12) }

  // unscrewing the cap and pulling the cord
  nadeWindup () { this.click(1300, 0.25, 0.05); this.click(700, 0.3, 0.09, 0.14) }

  nadeThrow () {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const n = ctx.createBufferSource()
    n.buffer = this.noise
    const f = ctx.createBiquadFilter()
    f.type = 'bandpass'
    f.Q.value = 1.5
    f.frequency.setValueAtTime(500, t)
    f.frequency.exponentialRampToValueAtTime(1400, t + 0.18)
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(0.22, t + 0.06)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.22)
    n.connect(f); f.connect(g); g.connect(this.master)
    n.start(t, Math.random(), 0.3)
  }

  // blade cutting the air; pos null = local
  knifeSwing (pos = null) {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const n = ctx.createBufferSource()
    n.buffer = this.noise
    const f = ctx.createBiquadFilter()
    f.type = 'bandpass'
    f.Q.value = 3
    f.frequency.setValueAtTime(900, t + 0.08)
    f.frequency.exponentialRampToValueAtTime(3800, t + 0.2)
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.0001, t + 0.08)
    g.gain.exponentialRampToValueAtTime(0.3, t + 0.15)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.26)
    n.connect(f); f.connect(g); g.connect(this.out(pos))
    n.start(t, Math.random(), 0.3)
  }

  knifeHit () {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const o = ctx.createOscillator()
    o.type = 'triangle'
    o.frequency.setValueAtTime(160, t)
    o.frequency.exponentialRampToValueAtTime(60, t + 0.12)
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.6, t)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.15)
    o.connect(g); g.connect(this.master)
    o.start(t); o.stop(t + 0.18)
    this.click(700, 0.35, 0.06)
  }

  // a cat somewhere nearby: a voiced sweep through two formants, "mi-aow"
  meow (pos) {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const dur = 0.45 + Math.random() * 0.35
    const f0 = 480 + Math.random() * 220
    const o = ctx.createOscillator()
    o.type = 'sawtooth'
    o.frequency.setValueAtTime(f0, t)
    o.frequency.linearRampToValueAtTime(f0 * 1.35, t + dur * 0.35)
    o.frequency.linearRampToValueAtTime(f0 * 0.8, t + dur)
    const out = ctx.createGain()
    out.gain.setValueAtTime(0.0001, t)
    out.gain.exponentialRampToValueAtTime(0.35, t + 0.06)
    out.gain.setValueAtTime(0.35, t + dur * 0.6)
    out.gain.exponentialRampToValueAtTime(0.0001, t + dur)
    // "ee" opening to "ow"
    for (const [from, to, q, g] of [[2600, 1100, 6, 0.6], [900, 700, 4, 1]]) {
      const f = ctx.createBiquadFilter()
      f.type = 'bandpass'
      f.Q.value = q
      f.frequency.setValueAtTime(from, t)
      f.frequency.exponentialRampToValueAtTime(to, t + dur * 0.7)
      const fg = ctx.createGain()
      fg.gain.value = g
      o.connect(f); f.connect(fg); fg.connect(out)
    }
    out.connect(this.out(pos))
    o.start(t); o.stop(t + dur + 0.05)
  }

  // a startled cat
  hiss (pos) {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const n = ctx.createBufferSource()
    n.buffer = this.noise
    const f = ctx.createBiquadFilter()
    f.type = 'highpass'
    f.frequency.value = 2800
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(0.4, t + 0.04)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.5)
    n.connect(f); f.connect(g); g.connect(this.out(pos))
    n.start(t, Math.random(), 0.55)
  }

  // snapping the lid of an ammo can and stuffing the rounds away
  pickup () { this.click(2400, 0.3, 0.03); this.click(1100, 0.3, 0.06, 0.08); this.click(900, 0.25, 0.08, 0.2) }

  // wooden handle and steel head knocking on the ground; strength 0..1
  nadeBounce (pos, strength) {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const o = ctx.createOscillator()
    o.type = 'triangle'
    o.frequency.setValueAtTime(420 + Math.random() * 160, t)
    o.frequency.exponentialRampToValueAtTime(180, t + 0.06)
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.35 * strength, t)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.08)
    o.connect(g); g.connect(this.out(pos))
    o.start(t); o.stop(t + 0.1)
  }

  // the planted bomb's timer
  bombBeep (pos) {
    if (!this.ctx || !this.enabled) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const dest = this.out(pos)
    dest.refDistance = 6
    const o = ctx.createOscillator()
    o.type = 'square'
    o.frequency.value = 1750
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(0.16, t + 0.005)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.09)
    o.connect(g); g.connect(dest)
    o.start(t); o.stop(t + 0.1)
  }

  explosion (pos, dist) {
    if (!this.ctx || !this.enabled) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const dest = this.out(pos)
    dest.refDistance = 14 // carries much further than a gunshot
    const far = Math.min(1, dist / 120)

    // blast front: bright noise that closes down fast
    const n = ctx.createBufferSource()
    n.buffer = this.noise
    const lp = ctx.createBiquadFilter()
    lp.type = 'lowpass'
    lp.frequency.setValueAtTime(4500 * (1 - far * 0.85), t)
    lp.frequency.exponentialRampToValueAtTime(260, t + 0.35)
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(1.6, t + 0.005)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.5 + far * 0.4)
    n.connect(lp); lp.connect(g); g.connect(dest)
    n.start(t, Math.random() * 0.5, 1)

    // body: a deep falling thump
    const o = ctx.createOscillator()
    o.type = 'sine'
    o.frequency.setValueAtTime(90, t)
    o.frequency.exponentialRampToValueAtTime(28, t + 0.5)
    const og = ctx.createGain()
    og.gain.setValueAtTime(1.4, t)
    og.gain.exponentialRampToValueAtTime(0.0001, t + 0.6)
    o.connect(og); og.connect(dest)
    o.start(t); o.stop(t + 0.65)

    // rumble rolling down the street
    const r = ctx.createBufferSource()
    r.buffer = this.brown
    const rg = ctx.createGain()
    rg.gain.setValueAtTime(0.0001, t)
    rg.gain.exponentialRampToValueAtTime(1.2 + far * 0.4, t + 0.04)
    rg.gain.exponentialRampToValueAtTime(0.0001, t + 1.8 + far)
    r.connect(rg); rg.connect(dest)
    r.start(t, Math.random() * 0.3, 1.45)
  }

  // a tank gun: a hard crack on top of the explosion's thump, heard across the whole map
  cannon (pos = null, dist = 0) {
    if (!this.ctx || !this.enabled) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const dest = this.out(pos)
    if (pos) dest.refDistance = 18
    const n = ctx.createBufferSource()
    n.buffer = this.noise
    const bp = ctx.createBiquadFilter()
    bp.type = 'lowpass'
    bp.frequency.setValueAtTime(6000 * (1 - Math.min(0.8, dist / 150)), t)
    bp.frequency.exponentialRampToValueAtTime(180, t + 0.25)
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(2, t + 0.003)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.35)
    n.connect(bp); bp.connect(g); g.connect(dest)
    n.start(t, Math.random() * 0.5, 0.4)
    const o = ctx.createOscillator()
    o.type = 'sine'
    o.frequency.setValueAtTime(70, t)
    o.frequency.exponentialRampToValueAtTime(24, t + 0.6)
    const og = ctx.createGain()
    og.gain.setValueAtTime(1.6, t)
    og.gain.exponentialRampToValueAtTime(0.0001, t + 0.7)
    o.connect(og); og.connect(dest)
    o.start(t); o.stop(t + 0.75)
  }

  // the engine of the tank we drive: level 0 is off, 1 flat out
  engine (level) {
    if (!this.ctx || !this.enabled) return
    const ctx = this.ctx
    if (!this.motor) {
      if (level <= 0) return
      const src = ctx.createBufferSource()
      src.buffer = this.brown
      src.loop = true
      const lp = ctx.createBiquadFilter()
      lp.type = 'lowpass'
      const g = ctx.createGain()
      g.gain.value = 0
      src.connect(lp); lp.connect(g); g.connect(this.master)
      src.start()
      this.motor = { src, lp, g }
    }
    const t = ctx.currentTime
    this.motor.g.gain.setTargetAtTime(level > 0 ? 0.25 + level * 0.35 : 0, t, 0.15)
    this.motor.lp.frequency.setTargetAtTime(110 + level * 260, t, 0.2)
    this.motor.src.playbackRate.setTargetAtTime(0.7 + level * 0.6, t, 0.2)
  }

  // the engine of the motorcycle we ride: a twin's putter that climbs with the revs; level 0 is off, 1 flat out
  bikeEngine (level) {
    if (!this.ctx || !this.enabled) return
    const ctx = this.ctx
    if (!this.bikeMotor) {
      if (level <= 0) return
      const o = ctx.createOscillator()
      o.type = 'sawtooth'
      const lp = ctx.createBiquadFilter()
      lp.type = 'lowpass'
      lp.Q.value = 3
      const g = ctx.createGain()
      g.gain.value = 0
      o.connect(lp); lp.connect(g); g.connect(this.master)
      o.start()
      this.bikeMotor = { o, lp, g }
    }
    const t = ctx.currentTime
    const m = this.bikeMotor
    m.g.gain.setTargetAtTime(level > 0 ? 0.1 + level * 0.14 : 0, t, 0.1)
    m.o.frequency.setTargetAtTime(26 + level * 64, t, 0.15)
    m.lp.frequency.setTargetAtTime(240 + level * 900, t, 0.15)
  }

  footstep (pos = null, vol = 0.12) {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const n = ctx.createBufferSource()
    n.buffer = this.brown
    n.playbackRate.value = 1.6 + Math.random() * 0.6
    const f = ctx.createBiquadFilter()
    f.type = 'lowpass'
    f.frequency.value = 700 + Math.random() * 300
    const g = ctx.createGain()
    g.gain.setValueAtTime(vol, t)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.09)
    n.connect(f); f.connect(g); g.connect(this.out(pos))
    n.start(t, Math.random(), 0.12)
  }

  hitmarker (kill = false) {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const o = ctx.createOscillator()
    o.type = 'square'
    o.frequency.setValueAtTime(kill ? 1300 : 1900, t)
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.08, t)
    g.gain.exponentialRampToValueAtTime(0.0001, t + (kill ? 0.16 : 0.05))
    o.connect(g); g.connect(this.master)
    o.start(t); o.stop(t + 0.2)
  }

  // a round ringing off the helmet and into the head: a recorded clip, not synthesised
  headshot () {
    if (!this.ctx || !this.headshotClip) return
    const src = this.ctx.createBufferSource()
    src.buffer = this.headshotClip
    src.playbackRate.value = 0.96 + Math.random() * 0.08
    const g = this.ctx.createGain()
    g.gain.value = 0.3
    src.connect(g); g.connect(this.master)
    src.start()
  }

  hurt () {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const o = ctx.createOscillator()
    o.type = 'triangle'
    o.frequency.setValueAtTime(110, t)
    o.frequency.exponentialRampToValueAtTime(55, t + 0.18)
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.5, t)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.22)
    o.connect(g); g.connect(this.master)
    o.start(t); o.stop(t + 0.25)
    this.click(500, 0.3, 0.08)
  }

  whiz (pos) {
    if (!this.ctx) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const n = ctx.createBufferSource()
    n.buffer = this.noise
    const f = ctx.createBiquadFilter()
    f.type = 'bandpass'
    f.Q.value = 6
    f.frequency.setValueAtTime(3000, t)
    f.frequency.exponentialRampToValueAtTime(1200, t + 0.12)
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(0.25, t + 0.04)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.14)
    n.connect(f); f.connect(g); g.connect(this.out(pos))
    n.start(t, Math.random(), 0.2)
  }
}
