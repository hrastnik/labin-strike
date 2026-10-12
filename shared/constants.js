// Shared tuning values used by both the client and the authoritative server.

export const PORT = 7344
export const TICK_RATE = 30 // server simulation Hz
export const SNAPSHOT_RATE = 20 // server -> client state broadcasts Hz
export const INPUT_RATE = 30 // client -> server state uploads Hz
export const INTERP_DELAY = 110 // ms of buffering for remote entity interpolation

export const MATCH = {
  targetPlayers: 8, // bots fill empty slots up to this many players
  scoreLimit: 50,
  timeLimit: 10 * 60, // seconds
  intermission: 12, // seconds between rounds
  respawnDelay: 3, // seconds
  spawnProtection: 1.5, // seconds
  loadoutGrace: 5, // seconds after spawning in which a class change applies at once (if not yet in combat)
  teamSwitchCooldown: 5, // seconds
  botToggleCooldown: 2, // seconds between one player's bot on/off switches
  modeSwitchCooldown: 10 // seconds between one player's mode switches (each one restarts the match)
}

export const TEAMS = {
  allies: { id: 'allies', name: 'Allies', color: '#7f9a4c', hud: '#9fc16a' },
  axis: { id: 'axis', name: 'Axis', color: '#8a8f99', hud: '#d0574a' }
}

export const PLAYER = {
  radius: 0.35,
  height: 1.8,
  crouchHeight: 1.25,
  eye: 1.62,
  crouchEye: 1.08,
  walkSpeed: 5.0,
  crouchSpeed: 2.4,
  sprintMul: 1.45, // forward only, standing, not aiming or firing
  adsSpeedMul: 0.6,
  jumpSpeed: 5.4,
  gravity: 19,
  maxHealth: 100,
  regenDelay: 5, // seconds without damage before health regenerates (COD2 style)
  regenRate: 22 // hp per second
}

// weapon stats, classes and faction rules live in weapons.js
export { WEAPONS, damageFor } from './weapons.js'

export const BOT_NAMES = [
  'Pvt. Rossi', 'Cpl. Novak', 'Sgt. Kovač', 'Pvt. Miller', 'Lt. Brandt', 'Pvt. Weber',
  'Cpl. Price', 'Sgt. Hartmann', 'Pvt. Dukić', 'Cpl. Fischer', 'Pvt. Moore', 'Sgt. Vogel',
  'Pvt. Ivančić', 'Cpl. Baker', 'Pvt. Krüger', 'Sgt. Foley'
]
