// Search and Destroy rounds: spawning once per round, planting and defusing, the bomb, elimination and halftime.
// The Game owns the players and the match; it hands rounds to this while the mode is 'sd'.
import { TEAMS } from '../shared/constants.js'
import { SD, SD_SITES, otherTeam, sdAttackers, sdSiteAt, bombDamage } from '../shared/modes.js'
import { CAT } from './cats.js'

const r2 = (v) => Math.round(v * 100) / 100

export class SearchAndDestroy {
  constructor (game) {
    this.g = game
    this.round = 0
    this.state = 'over' // 'live' | 'over'
    this.attackers = sdAttackers(1)
    this.startedAt = 0
    this.endsAt = 0
    this.nextAt = 0
    this.bomb = null // { site, pos, explodeAt, by }
    this.winner = null
    this.reason = null // 'eliminated' | 'time' | 'bomb' | 'defused'
    this.fielded = { allies: false, axis: false }
    this.target = 'A' // the site most attacking bots go for this round
  }

  get defenders () { return otherTeam(this.attackers) }

  nextRound () {
    const g = this.g
    const now = g.now()
    this.round++
    this.attackers = sdAttackers(this.round)
    this.state = 'live'
    this.startedAt = now
    this.endsAt = now + SD.roundTime * 1000
    this.bomb = null
    this.winner = null
    this.reason = null
    this.fielded = { allies: false, axis: false }
    const sites = SD_SITES[this.defenders]
    this.target = sites[Math.floor(Math.random() * sites.length)].id
    g.clearField()
    g.tanks.roundReset()
    g.bikes.reset()
    for (const p of g.players.values()) { p.alive = false; p.useOn = false; p.act = null }
    for (const p of g.players.values()) if (p.deployed) g.spawn(p)
    if (this.round === SD.halftime + 1) g.emitAll('notice', { m: 'Halftime: the sides swap roles' }, true)
    g.emitAll('notice', { m: `Round ${this.round}: the ${TEAMS[this.attackers].name} attack` }, true)
    g.broadcastRoster()
  }

  // joiners, side-switchers and new bots may still come in early in a round, once
  canSpawn (p, now) {
    return this.state === 'live' && p.sdRound !== this.round && now - this.startedAt < SD.joinGrace * 1000
  }

  onSpawn (p) {
    p.sdRound = this.round
    p.useOn = false
    p.act = null
    this.fielded[p.team] = true
  }

  use (p, on) {
    if (typeof on === 'boolean') p.useOn = on
  }

  tick (now) {
    if (this.state === 'over') {
      if (now >= this.nextAt && this.g.match.state === 'playing') this.nextRound()
      return
    }
    this.updateActions(now)
    if (this.state !== 'live') return
    if (this.bomb) {
      if (now >= this.bomb.explodeAt) this.explode()
    } else if (now >= this.endsAt) {
      this.endRound(this.defenders, 'time')
    }
    if (this.state === 'live') this.checkElimination()
  }

  actionFor (p) {
    if (p.tank || p.bike) return null
    if (p.team === this.attackers && !this.bomb) {
      const site = sdSiteAt(this.defenders, p.pos)
      return site && { kind: 'plant', site: site.id }
    }
    if (p.team === this.defenders && this.bomb) {
      const b = this.bomb.pos
      if (Math.hypot(p.pos[0] - b[0], p.pos[2] - b[2]) <= SD.defuseReach && Math.abs(p.pos[1] - b[1]) < 1.5) return { kind: 'defuse' }
    }
    return null
  }

  // a plant or defuse runs while the player holds the use key, stands still and stays in place
  updateActions (now) {
    for (const p of this.g.players.values()) {
      const want = p.alive && p.useOn ? this.actionFor(p) : null
      if (!want) { this.setAct(p, null); continue }
      const a = p.act
      if (!a || a.kind !== want.kind || Math.hypot(p.pos[0] - a.at[0], p.pos[2] - a.at[2]) > SD.moveTolerance) {
        this.setAct(p, { ...want, start: now, at: p.pos.slice() })
        continue
      }
      if (now - a.start < actionTime(a.kind)) continue
      this.setAct(p, null)
      p.useOn = false
      if (a.kind === 'plant') this.plant(p, a.site)
      else this.defuse(p)
      if (this.state !== 'live') return
    }
  }

  setAct (p, act) {
    if (!act && !p.act) return
    p.act = act
    if (!p.isBot) p.channel.emit('act', act ? { k: act.kind, ms: actionTime(act.kind) } : { k: null }, { reliable: true })
  }

  plant (p, site) {
    const g = this.g
    const now = g.now()
    this.bomb = { site, pos: p.pos.map(r2), explodeAt: now + SD.bombTime * 1000, by: p.id }
    console.log(`[game] ${p.name} planted the bomb at ${site}`)
    g.emitAll('bomb', { e: 'plant', s: site, p: this.bomb.pos, ms: SD.bombTime * 1000, by: p.id }, true)
    g.emitAll('notice', { m: `${p.name} planted the bomb at ${site}` }, true)
    g.broadcastRoster()
  }

  defuse (p) {
    console.log(`[game] ${p.name} defused the bomb`)
    this.bomb = null
    this.g.emitAll('bomb', { e: 'defuse', by: p.id }, true)
    this.g.emitAll('notice', { m: `${p.name} defused the bomb` }, true)
    this.endRound(this.defenders, 'defused')
  }

  explode () {
    const g = this.g
    const b = this.bomb
    this.bomb = null
    g.emitAll('bomb', { e: 'boom', p: b.pos }, true)
    g.cats.scare(b.pos, CAT.blastRadius * 2)
    // a planter who has since left still owns the blast, so the killfeed shows it as a death
    const by = g.players.get(b.by) ?? { id: 0, team: this.attackers, pos: b.pos, isBot: true, kills: 0 }
    const c = [b.pos[0], b.pos[1] + 0.5, b.pos[2]]
    for (const q of [...g.players.values()]) {
      if (!q.alive || q.tank) continue
      const dmg = bombDamage(Math.hypot(q.pos[0] - c[0], q.pos[1] + 1 - c[1], q.pos[2] - c[2]))
      if (dmg > 0) g.applyDamage(q, by, dmg, SD.bomb.id, 'body', c)
    }
    g.tanks.blast(c, by, this.attackers, bombDamage, SD.bomb.id)
    g.bikes.blast(c, by, this.attackers, bombDamage, SD.bomb.id)
    this.endRound(this.attackers, 'bomb')
  }

  // a side that never had anyone on the field this round (bots off, nobody on it) cannot be wiped out
  checkElimination () {
    const alive = { allies: 0, axis: 0 }
    for (const p of this.g.players.values()) if (p.alive) alive[p.team]++
    if (this.fielded[this.defenders] && !alive[this.defenders]) this.endRound(this.attackers, 'eliminated')
    else if (this.fielded[this.attackers] && !alive[this.attackers] && !this.bomb) this.endRound(this.defenders, 'eliminated')
  }

  endRound (winner, reason) {
    if (this.state !== 'live') return
    const g = this.g
    this.state = 'over'
    this.winner = winner
    this.reason = reason
    this.bomb = null
    this.nextAt = g.now() + SD.roundOver * 1000
    for (const p of g.players.values()) { this.setAct(p, null); p.useOn = false }
    const s = g.match.scores
    s[winner]++
    console.log(`[game] round ${this.round} to ${winner} (${reason}) ${JSON.stringify(s)}`)
    if (s[winner] >= SD.roundsToWin) g.endMatch(winner)
    else if (this.round >= SD.halftime * 2) g.endMatch(s.allies === s.axis ? 'draw' : s.allies > s.axis ? 'allies' : 'axis')
    g.broadcastRoster()
  }

  timeLeft (now) {
    if (this.state === 'over') return this.nextAt - now
    return (this.bomb ? this.bomb.explodeAt : this.endsAt) - now
  }

  info () {
    return {
      round: this.round,
      attackers: this.attackers,
      roundState: this.state,
      roundWinner: this.winner,
      reason: this.reason,
      bomb: this.bomb && { s: this.bomb.site, p: this.bomb.pos }
    }
  }
}

const actionTime = (kind) => (kind === 'plant' ? SD.plantTime : SD.defuseTime) * 1000
