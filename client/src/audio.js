// Procedural WebAudio: gunshots (local + spatialised remote), reload/dry clicks, footsteps, hit/kill cues.
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

  // weapon: 'rifle' | 'pistol'; pos null = local (non-spatial); dist used for muffling distant shots
  shot (weapon, pos = null, dist = 0) {
    if (!this.ctx || !this.enabled) return
    const ctx = this.ctx
    const t = ctx.currentTime
    const dest = this.out(pos)
    const far = Math.min(1, dist / 90)
    const rifle = weapon === 'rifle'

    // crack: filtered noise burst
    const n = ctx.createBufferSource()
    n.buffer = this.noise
    n.playbackRate.value = 0.9 + Math.random() * 0.2
    const bp = ctx.createBiquadFilter()
    bp.type = 'lowpass'
    bp.frequency.setValueAtTime((rifle ? 6500 : 5200) * (1 - far * 0.8), t)
    bp.frequency.exponentialRampToValueAtTime(rifle ? 900 : 700, t + 0.18)
    const g = ctx.createGain()
    const vol = pos ? 1.0 : 0.85
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(vol, t + 0.003)
    g.gain.exponentialRampToValueAtTime(0.0001, t + (rifle ? 0.32 : 0.24) + far * 0.3)
    n.connect(bp); bp.connect(g); g.connect(dest)
    n.start(t, Math.random() * 0.5, 0.8)

    // thump: pitched-down sine body
    const o = ctx.createOscillator()
    o.type = 'sine'
    o.frequency.setValueAtTime(rifle ? 140 : 180, t)
    o.frequency.exponentialRampToValueAtTime(40, t + 0.14)
    const og = ctx.createGain()
    og.gain.setValueAtTime(pos ? 0.6 : 0.9, t)
    og.gain.exponentialRampToValueAtTime(0.0001, t + 0.16)
    o.connect(og); og.connect(dest)
    o.start(t); o.stop(t + 0.2)

    // tail: low rumble reflecting off the buildings
    const r = ctx.createBufferSource()
    r.buffer = this.brown
    const rg = ctx.createGain()
    rg.gain.setValueAtTime(0.0001, t)
    rg.gain.exponentialRampToValueAtTime(0.35 + far * 0.4, t + 0.02)
    rg.gain.exponentialRampToValueAtTime(0.0001, t + 0.7 + far * 0.5)
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

  reload (weapon, duration) {
    // mag out, mag in, bolt/slide
    this.click(1400, 0.3, 0.05, duration * 0.2)
    this.click(1800, 0.35, 0.05, duration * 0.62)
    this.click(2600, 0.4, 0.04, duration * 0.85)
    if (weapon === 'rifle') this.click(1100, 0.35, 0.06, duration * 0.9)
  }

  weaponSwitch () { this.click(1600, 0.2, 0.05); this.click(2400, 0.2, 0.03, 0.12) }

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
