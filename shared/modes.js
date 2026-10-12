// Game modes. Search and Destroy plays in rounds without respawns: the attacking side plants a bomb at one of the
// defenders' two sites, the defenders stop them or defuse it. Teams keep their spawns (weapons are faction-bound),
// so the attacking role swaps at halftime and each side defends the pair of sites on its own half.

export const MODES = {
  tdm: { name: 'Team Deathmatch', short: 'TDM' },
  sd: { name: 'Search & Destroy', short: 'S&D' }
}
export const MODE_IDS = Object.keys(MODES)

export const SD = {
  roundsToWin: 6,
  halftime: 5, // rounds before the roles swap; a match is at most twice this
  firstAttackers: 'axis',
  roundTime: 120, // seconds to plant
  roundOver: 6, // seconds from a round's result to the next round
  joinGrace: 15, // seconds into a round in which someone who has not yet played it may still spawn
  bombTime: 40, // fuse from planting
  plantTime: 4,
  defuseTime: 7,
  siteRadius: 3, // metres from a site's centre in which the bomb can be planted
  defuseReach: 1.8, // metres from the bomb
  moveTolerance: 0.6, // metres a planter or defuser may drift before the action is cancelled
  blastDamage: 400,
  killRadius: 6,
  blastRadius: 14,
  bomb: { id: 'bomb', name: 'Demolition charge' }
}

// placed with the nav grid so the defenders reach each site in about half the attackers' time (allies spawn at +X)
export const SD_SITES = {
  allies: [{ id: 'A', pos: [22.3, 0, 2.3] }, { id: 'B', pos: [50.3, 0.1, -17.8] }],
  axis: [{ id: 'A', pos: [-33.8, 0, 2.3] }, { id: 'B', pos: [-29.8, 2.8, -29.8] }]
}

export const otherTeam = (team) => team === 'allies' ? 'axis' : 'allies'

export const sdAttackers = (round) => round <= SD.halftime ? SD.firstAttackers : otherTeam(SD.firstAttackers)

export function sdSiteAt (defenders, pos) {
  return SD_SITES[defenders].find((s) => Math.hypot(pos[0] - s.pos[0], pos[2] - s.pos[2]) <= SD.siteRadius && Math.abs(pos[1] - s.pos[1]) < 1.5) ?? null
}

export function bombDamage (distance) {
  const { blastDamage, killRadius, blastRadius } = SD
  if (!(distance < blastRadius)) return 0
  if (distance <= killRadius) return blastDamage
  return Math.round(blastDamage * (1 - (distance - killRadius) / (blastRadius - killRadius)))
}
