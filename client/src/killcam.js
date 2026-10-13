// Kill-cam: the last few seconds before our death, replayed through the killer's eyes.
// Everything comes from what we already receive: the snapshots (kept for a while here) are fed to a second set of
// soldiers on their own timeline, and the shots, stabs and grenades are fired again when the replay reaches them.
// The tanks, bikes and cats have no copies: they keep enough history to be posed at the replay's time instead.
import { KILLCAM, INTERP_DELAY, killcamSpeed } from '@shared/constants.js'
import { Avatars } from './avatars.js'
import { Spectator } from './spectate.js'

export const HISTORY = 12000 // ms of snapshots kept by the kill-cam and by the tanks, bikes and cats it poses
const LEAD = 600 // ms of snapshots handed to the replayed soldiers ahead of the replay's time (interpolation needs them)
const MAX_LAG = 1000 // ms, the most the killer's view of the others is held back

export class Killcam {
  // play(type, data, replay): shows one recorded event (shot, stab, nade, boom, shell, bikeboom, tankboom) in the replay
  // makeGrenades(): the replay's own grenades
  constructor ({ scene, camera, viewmodel, ray, baseFov, play, makeGrenades }) {
    this.scene = scene
    this.play = play
    this.makeGrenades = makeGrenades
    this.ghosts = new Avatars(scene) // the soldiers as they were
    this.spec = new Spectator(camera, viewmodel, ray, baseFov)
    this.grenades = null
    this.snaps = [] // { t (server ms), p, ... } as received, oldest first
    this.events = [] // { t (server ms), type, d }, oldest first
    this.queue = [] // the replay's events still to play: { at (replay ms), type, d }
    this.active = false
    this.time = 0 // the replay's server ms
    this.scale = 1 // playback speed this frame
  }

  // ------------------------------------------------------------------ recording

  snapshot (s) {
    const last = this.snaps[this.snaps.length - 1]
    if (last && s.t <= last.t) return // late or repeated: the soldiers already moved past it
    this.snaps.push(s)
    this.trim(this.snaps, s.t)
  }

  // t: server ms the event happened at (our own are stamped ahead of the others: kept in order of t)
  record (type, d, t) {
    const e = { t, type, d }
    const list = this.events
    let i = list.length
    while (i > 0 && list[i - 1].t > t) i--
    list.splice(i, 0, e)
    this.trim(list, list[list.length - 1].t)
    if (this.active) this.enqueue(e)
  }

  trim (list, now) {
    let n = 0
    while (n < list.length && list[n].t < now - HISTORY) n++
    if (n) list.splice(0, n)
  }

  clear () {
    this.stop()
    this.snaps.length = 0
    this.events.length = 0
  }

  // ------------------------------------------------------------------ playback

  /**
   * killer, victim: ids; at: server ms of the kill; roster: id -> { name, team, bot, ping } (as it was at the kill)
   * Returns false when there is nothing to show (the killer is not in the recording).
   */
  start ({ killer, victim, at, roster }) {
    this.stop()
    const k = roster.get(killer)
    const from = at - KILLCAM.before * 1000
    if (!k || !this.snaps.some((s) => s.t >= from && s.t <= at && s.p.some((e) => e[0] === killer))) return false
    this.killer = killer
    this.victim = victim
    this.at = at
    this.roster = new Map(roster)
    this.time = from
    this.end = at + KILLCAM.after * 1000
    // the killer saw everyone else (and what they did) late: by the interpolation delay plus the round trip for a
    // player, not at all for a bot, which plays on the server's own state
    const ping = k.bot ? 0 : Math.max(0, k.ping || 0)
    this.lag = k.bot ? 0 : Math.min(MAX_LAG, INTERP_DELAY + ping)
    this.news = k.bot ? 0 : Math.min(MAX_LAG, ping / 2) // a message from the server reaches them half a round trip later
    this.fedT = -Infinity
    this.queue = []
    for (const e of this.events) this.enqueue(e)
    this.grenades ??= this.makeGrenades()
    this.spec.reset()
    this.spec.follow(killer)
    this.active = true
    this.feed()
    // the soldiers start where they were, without walking in from wherever the first sample put them
    for (const a of this.ghosts.map.values()) if (a.sample(this.sampleTime(a))) { a.lastPos.copy(a.pos); a.animate(0) }
    return true
  }

  // the recording's server ms to show soldier a at: the killer at the replay's time, the others as late as they saw them
  sampleTime (a) { return a.id === this.killer ? this.time : this.time - this.lag }

  // queue event e to play when the killer saw it (their own actions at once, the rest when the news reached them)
  enqueue (e) {
    const own = e.d.id === this.killer && (e.type === 'shot' || e.type === 'stab' || e.type === 'nade')
    const at = e.t + (own ? 0 : this.news)
    if (at < this.time || at > this.end) return
    const q = this.queue
    let i = q.length
    while (i > 0 && q[i - 1].at > at) i--
    q.splice(i, 0, { at, type: e.type, d: e.d })
  }

  stop () {
    if (!this.active) return
    this.active = false
    this.scale = 1
    this.queue = []
    this.ghosts.clear()
    this.grenades?.clear()
  }

  // hand the soldiers the snapshots up to a little past the replay's time, seen from the killer's side
  feed () {
    const team = this.roster.get(this.killer)?.team ?? null
    // by time, not by position in the list: the oldest snapshots are dropped as new ones come in
    for (const s of this.snaps) {
      if (s.t <= this.fedT) continue
      if (s.t > this.time + LEAD) break
      this.ghosts.onSnapshot(s, -1, this.roster, team)
      this.fedT = s.t
    }
  }

  /**
   * Advances the replay by dt (real seconds) and places the camera. ctx: { tanks, dt, bounce(pos, impact) }
   * Returns the spectator view of the killer ({ target, mode, fov, scoped }), or null once the replay is over.
   */
  update (ctx) {
    if (!this.active) return null
    this.scale = killcamSpeed((this.time - this.at) / 1000)
    const dt = ctx.dt * this.scale
    this.time += dt * 1000
    if (this.time >= this.end) { this.stop(); return null }
    this.feed()
    while (this.queue.length && this.queue[0].at <= this.time) {
      const e = this.queue.shift()
      if (e.type === 'kill') {
        const a = this.ghosts.map.get(e.d.v)
        if (a) a.killedLife = a.life
      } else this.play(e.type, e.d, this)
    }
    for (const a of this.ghosts.map.values()) if (a.sample(this.sampleTime(a))) a.animate(dt)
    this.grenades.update(dt, ctx.bounce)

    const a = this.ghosts.map.get(this.killer)
    if (!a) { this.stop(); return null }
    if (a.tag) a.tag.visible = false
    return this.spec.watch(a, { tanks: ctx.tanks, dt, now: this.time })
  }

  // in the killer's eyes this frame (draw the first-person weapon)
  get firstPerson () { return this.active && this.spec.firstPerson }

  // what the killer did, for the first-person weapon; onShot: true when the shot leaves that weapon
  onShot (id) {
    if (!this.firstPerson || id !== this.killer) return false
    this.spec.onShot(id, this.time)
    return true
  }

  onStab (id) { this.spec.onStab(id, this.time) }
  onNade (id) { this.spec.onNade(id, this.time) }

  // seconds of play shown so far, and in all (for a progress bar)
  get progress () { return Math.max(0, Math.min(1, (this.time - (this.at - KILLCAM.before * 1000)) / ((KILLCAM.before + KILLCAM.after) * 1000))) }

}
