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
  spawnProtection: 1.5 // seconds
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
  adsSpeedMul: 0.6,
  jumpSpeed: 5.4,
  gravity: 19,
  maxHealth: 100,
  regenDelay: 5, // seconds without damage before health regenerates (COD2 style)
  regenRate: 22 // hp per second
}

// spread values are in radians (half-angle of the cone)
export const WEAPONS = {
  rifle: {
    id: 'rifle',
    name: 'StG 44',
    slot: 1,
    auto: true,
    rpm: 600,
    mag: 30,
    reserve: 150,
    reloadTime: 2.4,
    drawTime: 0.45,
    damage: 27,
    headMul: 2.0,
    legMul: 0.75,
    falloffStart: 30,
    falloffEnd: 80,
    falloffMin: 0.65,
    range: 250,
    spread: { hip: 0.03, ads: 0.004, move: 0.035, air: 0.12, crouchMul: 0.7, bloom: 0.007, bloomMax: 0.05, recover: 0.12 },
    recoil: { pitch: 0.011, yaw: 0.005, recover: 6 },
    adsFov: 50
  },
  pistol: {
    id: 'pistol',
    name: 'M1911',
    slot: 2,
    auto: false,
    rpm: 360,
    mag: 7,
    reserve: 42,
    reloadTime: 1.7,
    drawTime: 0.3,
    damage: 34,
    headMul: 2.0,
    legMul: 0.8,
    falloffStart: 15,
    falloffEnd: 45,
    falloffMin: 0.55,
    range: 150,
    spread: { hip: 0.022, ads: 0.006, move: 0.03, air: 0.1, crouchMul: 0.75, bloom: 0.018, bloomMax: 0.06, recover: 0.16 },
    recoil: { pitch: 0.022, yaw: 0.006, recover: 7 },
    adsFov: 60
  }
}

export const WEAPON_IDS = ['rifle', 'pistol']

export function damageFor (weapon, distance, zone) {
  const w = WEAPONS[weapon]
  let dmg = w.damage
  if (distance > w.falloffStart) {
    const t = Math.min(1, (distance - w.falloffStart) / (w.falloffEnd - w.falloffStart))
    dmg *= 1 - t * (1 - w.falloffMin)
  }
  if (zone === 'head') dmg *= w.headMul
  else if (zone === 'legs') dmg *= w.legMul
  return Math.round(dmg)
}

export const BOT_NAMES = [
  'Pvt. Rossi', 'Cpl. Novak', 'Sgt. Kovač', 'Pvt. Miller', 'Lt. Brandt', 'Pvt. Weber',
  'Cpl. Price', 'Sgt. Hartmann', 'Pvt. Dukić', 'Cpl. Fischer', 'Pvt. Moore', 'Sgt. Vogel',
  'Pvt. Ivančić', 'Cpl. Baker', 'Pvt. Krüger', 'Sgt. Foley'
]
