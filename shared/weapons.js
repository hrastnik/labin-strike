// Data-driven weapon catalogue, playable classes and faction rules.
// Shared by the client (handling, HUD, loadout menu) and the authoritative server (validation, damage, bots).
// Adding a weapon: add an entry here, add it to a class list, and (optionally) a model in client/src/gunmodels.js.
//
// spread values are in radians (half-angle of the cone)
// reload.style: 'mag' (detachable box/stick/top mag), 'enbloc' (M1 Garand clip), 'charger' (stripper clips + single
//   rounds into an internal magazine), 'single' (rounds loaded one at a time), 'belt' (open feed cover, lay belt)
// velocity is muzzle velocity in m/s; hits are hitscan, so it drives tracer speed only
// fx.sound shapes the procedural gunshot (see client/src/audio.js); fx.eject: 'fire' | 'bolt' | 'none'

const BASE = {
  auto: false,
  action: 'semi', // 'auto' | 'semi' | 'bolt'
  headMul: 2.0,
  legMul: 0.75,
  range: 250,
  moveMul: 1, // movement speed multiplier while the weapon is held
  adsTime: 0.18, // seconds to raise the sights
  scope: false,
  velocity: 700,
  reload: { style: 'mag' }
}

function weapon (id, d) {
  const w = { ...BASE, ...d, id }
  w.spread = { air: 0.12, crouchMul: 0.7, ...d.spread }
  w.fx = { flash: 1, eject: 'fire', ...d.fx }
  if (w.action === 'auto') w.auto = true
  // nominal (empty-magazine) reload time, used by bots and the loadout screen
  if (w.reloadTime == null) w.reloadTime = reloadDuration(w, 0, Infinity)
  return w
}

// time to reload from `mag` rounds with `reserve` left; incremental styles depend on how many rounds go in
export function reloadDuration (w, mag, reserve) {
  const r = w.reload
  if (r.style !== 'charger' && r.style !== 'single') return w.reloadTime
  const missing = Math.max(0, Math.min(w.mag - mag, reserve))
  if (r.style === 'single') return r.open + missing * r.perRound + r.close
  const clips = Math.floor(missing / r.clip)
  return r.open + clips * r.perClip + (missing - clips * r.clip) * r.perRound + r.close
}

export const WEAPONS = {
  // ------------------------------------------------------------------ Axis
  stg44: weapon('stg44', {
    name: 'StG 44',
    faction: 'axis',
    category: 'assault',
    desc: 'Select-fire assault rifle. Flexible at every range.',
    action: 'auto',
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
    adsFov: 50,
    velocity: 685,
    fx: { sound: { crack: 6500, crackEnd: 900, body: 140, decay: 0.32, tail: 0.35, vol: 1 } }
  }),
  kar98k: weapon('kar98k', {
    name: 'Kar98k',
    faction: 'axis',
    category: 'bolt',
    desc: 'Mauser bolt-action rifle. One well-placed round is enough.',
    action: 'bolt',
    rpm: 48,
    mag: 5,
    reserve: 40,
    reload: { style: 'charger', clip: 5, open: 0.45, perClip: 1.15, perRound: 0.5, close: 0.45 },
    drawTime: 0.6,
    damage: 105,
    headMul: 1.6,
    falloffStart: 60,
    falloffEnd: 150,
    falloffMin: 0.9,
    range: 300,
    spread: { hip: 0.055, ads: 0.0012, move: 0.05, air: 0.14, bloom: 0.03, bloomMax: 0.05, recover: 0.25 },
    recoil: { pitch: 0.06, yaw: 0.012, recover: 5 },
    adsFov: 45,
    moveMul: 0.96,
    adsTime: 0.24,
    velocity: 760,
    fx: { sound: { crack: 7500, crackEnd: 700, body: 110, decay: 0.5, tail: 0.6, vol: 1.15 }, flash: 1.3, eject: 'bolt' }
  }),
  kar98k_scoped: weapon('kar98k_scoped', {
    name: 'Kar98k Zf. 39',
    faction: 'axis',
    category: 'scoped',
    desc: 'Sniper Kar98k with a 4x scope. The mount blocks chargers: load one round at a time.',
    action: 'bolt',
    rpm: 40,
    mag: 5,
    reserve: 30,
    reload: { style: 'single', open: 0.5, perRound: 0.55, close: 0.5 },
    drawTime: 0.7,
    damage: 110,
    headMul: 1.6,
    falloffStart: 80,
    falloffEnd: 200,
    falloffMin: 0.95,
    range: 350,
    spread: { hip: 0.08, ads: 0, move: 0.06, air: 0.16, bloom: 0.04, bloomMax: 0.08, recover: 0.25 },
    recoil: { pitch: 0.06, yaw: 0.012, recover: 5 },
    adsFov: 18,
    scope: true,
    moveMul: 0.94,
    adsTime: 0.32,
    velocity: 760,
    fx: { sound: { crack: 7500, crackEnd: 700, body: 110, decay: 0.5, tail: 0.6, vol: 1.15 }, flash: 1.3, eject: 'bolt' }
  }),
  mp40: weapon('mp40', {
    name: 'MP 40',
    faction: 'axis',
    category: 'smg',
    desc: 'Submachine gun with a slow, controllable cyclic rate.',
    action: 'auto',
    rpm: 530,
    mag: 32,
    reserve: 160,
    reloadTime: 2.3,
    drawTime: 0.35,
    damage: 25,
    headMul: 1.8,
    legMul: 0.8,
    falloffStart: 12,
    falloffEnd: 35,
    falloffMin: 0.5,
    range: 150,
    spread: { hip: 0.026, ads: 0.009, move: 0.022, air: 0.1, crouchMul: 0.75, bloom: 0.004, bloomMax: 0.03, recover: 0.15 },
    recoil: { pitch: 0.007, yaw: 0.004, recover: 7 },
    adsFov: 58,
    moveMul: 1.05,
    adsTime: 0.15,
    velocity: 400,
    fx: { sound: { crack: 4200, crackEnd: 600, body: 170, decay: 0.22, tail: 0.25, vol: 0.85 }, flash: 0.8 }
  }),
  mg42: weapon('mg42', {
    name: 'MG 42',
    faction: 'axis',
    category: 'lmg',
    desc: 'General-purpose machine gun. 1200 rounds a minute, hard to hold on target.',
    action: 'auto',
    rpm: 1200,
    mag: 50,
    reserve: 150,
    reload: { style: 'belt' },
    reloadTime: 5.2,
    drawTime: 0.95,
    damage: 22,
    headMul: 1.8,
    falloffStart: 35,
    falloffEnd: 90,
    falloffMin: 0.7,
    spread: { hip: 0.06, ads: 0.011, move: 0.06, air: 0.16, crouchMul: 0.55, bloom: 0.005, bloomMax: 0.065, recover: 0.1 },
    recoil: { pitch: 0.012, yaw: 0.009, recover: 5 },
    adsFov: 52,
    moveMul: 0.82,
    adsTime: 0.32,
    velocity: 755,
    fx: { sound: { crack: 7000, crackEnd: 1000, body: 120, decay: 0.2, tail: 0.3, vol: 1.05 }, flash: 1.2 }
  }),
  fg42: weapon('fg42', {
    name: 'FG 42',
    faction: 'axis',
    category: 'ar',
    desc: 'Paratrooper automatic rifle. Full-power rounds, heavy recoil, side-mounted magazine.',
    action: 'auto',
    rpm: 750,
    mag: 20,
    reserve: 120,
    reloadTime: 2.7,
    drawTime: 0.55,
    damage: 30,
    headMul: 1.8,
    falloffStart: 40,
    falloffEnd: 100,
    falloffMin: 0.7,
    range: 280,
    spread: { hip: 0.038, ads: 0.006, move: 0.04, air: 0.14, crouchMul: 0.65, bloom: 0.012, bloomMax: 0.07, recover: 0.12 },
    recoil: { pitch: 0.02, yaw: 0.01, recover: 5.5 },
    adsFov: 48,
    moveMul: 0.93,
    adsTime: 0.22,
    velocity: 760,
    fx: { sound: { crack: 7800, crackEnd: 900, body: 125, decay: 0.3, tail: 0.4, vol: 1.1 }, flash: 1.4 }
  }),
  g43: weapon('g43', {
    name: 'Gewehr 43',
    faction: 'axis',
    category: 'semi',
    desc: 'Gas-operated semi-automatic rifle with a 10-round magazine.',
    rpm: 280,
    mag: 10,
    reserve: 60,
    reloadTime: 3.0,
    drawTime: 0.5,
    damage: 50,
    headMul: 1.8,
    falloffStart: 50,
    falloffEnd: 130,
    falloffMin: 0.8,
    range: 300,
    spread: { hip: 0.04, ads: 0.0025, move: 0.045, air: 0.14, bloom: 0.018, bloomMax: 0.05, recover: 0.18 },
    recoil: { pitch: 0.032, yaw: 0.008, recover: 6 },
    adsFov: 44,
    moveMul: 0.96,
    adsTime: 0.22,
    velocity: 745,
    fx: { sound: { crack: 7200, crackEnd: 800, body: 120, decay: 0.42, tail: 0.5, vol: 1.1 }, flash: 1.2 }
  }),
  p38: weapon('p38', {
    name: 'Walther P38',
    faction: 'axis',
    category: 'pistol',
    desc: 'Double-action service pistol. Steady from the hip.',
    rpm: 400,
    mag: 8,
    reserve: 48,
    reloadTime: 1.6,
    drawTime: 0.28,
    damage: 29,
    legMul: 0.8,
    falloffStart: 15,
    falloffEnd: 45,
    falloffMin: 0.55,
    range: 150,
    spread: { hip: 0.019, ads: 0.006, move: 0.028, air: 0.1, crouchMul: 0.75, bloom: 0.016, bloomMax: 0.055, recover: 0.17 },
    recoil: { pitch: 0.019, yaw: 0.005, recover: 7.5 },
    adsFov: 60,
    adsTime: 0.14,
    velocity: 365,
    fx: { sound: { crack: 5600, crackEnd: 750, body: 200, decay: 0.22, tail: 0.25, vol: 0.9 }, flash: 0.7 }
  }),
  luger: weapon('luger', {
    name: 'Luger P08',
    faction: 'axis',
    category: 'pistol',
    desc: 'Toggle-locked pistol. Fast to draw and precise down the sights.',
    rpm: 420,
    mag: 8,
    reserve: 48,
    reloadTime: 1.75,
    drawTime: 0.25,
    damage: 27,
    headMul: 2.1,
    legMul: 0.8,
    falloffStart: 18,
    falloffEnd: 50,
    falloffMin: 0.55,
    range: 150,
    spread: { hip: 0.022, ads: 0.004, move: 0.03, air: 0.1, crouchMul: 0.75, bloom: 0.017, bloomMax: 0.06, recover: 0.18 },
    recoil: { pitch: 0.017, yaw: 0.004, recover: 7.5 },
    adsFov: 58,
    adsTime: 0.14,
    velocity: 350,
    fx: { sound: { crack: 6000, crackEnd: 800, body: 210, decay: 0.2, tail: 0.22, vol: 0.85 }, flash: 0.7 }
  }),

  // ------------------------------------------------------------------ Allies
  m1garand: weapon('m1garand', {
    name: 'M1 Garand',
    faction: 'allies',
    category: 'semi',
    desc: 'Semi-automatic rifle fed by 8-round en-bloc clips. Listen for the ping.',
    rpm: 280,
    mag: 8,
    reserve: 64,
    reload: { style: 'enbloc' },
    reloadTime: 2.5,
    drawTime: 0.5,
    damage: 52,
    headMul: 1.8,
    falloffStart: 55,
    falloffEnd: 140,
    falloffMin: 0.82,
    range: 300,
    spread: { hip: 0.042, ads: 0.002, move: 0.045, air: 0.14, bloom: 0.02, bloomMax: 0.055, recover: 0.18 },
    recoil: { pitch: 0.035, yaw: 0.009, recover: 6 },
    adsFov: 44,
    moveMul: 0.96,
    adsTime: 0.22,
    velocity: 850,
    fx: { sound: { crack: 7600, crackEnd: 850, body: 115, decay: 0.45, tail: 0.55, vol: 1.15 }, flash: 1.3 }
  }),
  thompson: weapon('thompson', {
    name: 'M1 Thompson',
    faction: 'allies',
    category: 'smg',
    desc: '.45 ACP submachine gun. Devastating up close, climbs under sustained fire.',
    action: 'auto',
    rpm: 700,
    mag: 30,
    reserve: 150,
    reloadTime: 2.6,
    drawTime: 0.4,
    damage: 26,
    headMul: 1.75,
    legMul: 0.8,
    falloffStart: 10,
    falloffEnd: 30,
    falloffMin: 0.5,
    range: 140,
    spread: { hip: 0.03, ads: 0.011, move: 0.024, air: 0.1, crouchMul: 0.75, bloom: 0.006, bloomMax: 0.04, recover: 0.13 },
    recoil: { pitch: 0.01, yaw: 0.006, recover: 6.5 },
    adsFov: 58,
    moveMul: 1.03,
    adsTime: 0.17,
    velocity: 285,
    fx: { sound: { crack: 3600, crackEnd: 500, body: 150, decay: 0.24, tail: 0.3, vol: 0.95 } }
  }),
  m3: weapon('m3', {
    name: 'M3 Grease Gun',
    faction: 'allies',
    category: 'smg',
    desc: 'Stamped-steel submachine gun. Slow cyclic rate, almost no recoil.',
    action: 'auto',
    rpm: 450,
    mag: 30,
    reserve: 150,
    reloadTime: 2.4,
    drawTime: 0.35,
    damage: 27,
    headMul: 1.75,
    legMul: 0.8,
    falloffStart: 14,
    falloffEnd: 38,
    falloffMin: 0.55,
    range: 150,
    spread: { hip: 0.024, ads: 0.007, move: 0.02, air: 0.1, crouchMul: 0.75, bloom: 0.003, bloomMax: 0.022, recover: 0.16 },
    recoil: { pitch: 0.005, yaw: 0.003, recover: 8 },
    adsFov: 58,
    moveMul: 1.05,
    adsTime: 0.15,
    velocity: 280,
    fx: { sound: { crack: 3200, crackEnd: 450, body: 135, decay: 0.24, tail: 0.28, vol: 0.85 }, flash: 0.8 }
  }),
  bar: weapon('bar', {
    name: 'BAR M1918A2',
    faction: 'allies',
    category: 'ar',
    desc: 'Browning Automatic Rifle. Hits hard, weighs 9 kg, kicks like a mule.',
    action: 'auto',
    rpm: 550,
    mag: 20,
    reserve: 140,
    reloadTime: 2.9,
    drawTime: 0.7,
    damage: 36,
    headMul: 1.75,
    falloffStart: 45,
    falloffEnd: 110,
    falloffMin: 0.72,
    range: 280,
    spread: { hip: 0.045, ads: 0.007, move: 0.05, air: 0.15, crouchMul: 0.6, bloom: 0.012, bloomMax: 0.065, recover: 0.11 },
    recoil: { pitch: 0.019, yaw: 0.009, recover: 5 },
    adsFov: 48,
    moveMul: 0.88,
    adsTime: 0.28,
    velocity: 805,
    fx: { sound: { crack: 7400, crackEnd: 850, body: 115, decay: 0.32, tail: 0.45, vol: 1.15 }, flash: 1.4 }
  }),
  m1919a6: weapon('m1919a6', {
    name: 'Browning M1919A6',
    faction: 'allies',
    category: 'lmg',
    desc: 'Belt-fed machine gun for sustained fire. Slowest weapon to move with.',
    action: 'auto',
    rpm: 500,
    mag: 100,
    reserve: 100,
    reload: { style: 'belt' },
    reloadTime: 6.0,
    drawTime: 1.0,
    damage: 34,
    headMul: 1.7,
    falloffStart: 40,
    falloffEnd: 100,
    falloffMin: 0.72,
    spread: { hip: 0.07, ads: 0.012, move: 0.07, air: 0.18, crouchMul: 0.5, bloom: 0.004, bloomMax: 0.05, recover: 0.12 },
    recoil: { pitch: 0.011, yaw: 0.007, recover: 5.5 },
    adsFov: 52,
    moveMul: 0.78,
    adsTime: 0.35,
    velocity: 853,
    fx: { sound: { crack: 7000, crackEnd: 950, body: 105, decay: 0.3, tail: 0.45, vol: 1.15 }, flash: 1.3 }
  }),
  m1903: weapon('m1903', {
    name: 'M1903 Springfield',
    faction: 'allies',
    category: 'bolt',
    desc: 'Bolt-action rifle with almost no damage falloff. Built for long shots.',
    action: 'bolt',
    rpm: 46,
    mag: 5,
    reserve: 40,
    reload: { style: 'charger', clip: 5, open: 0.45, perClip: 1.1, perRound: 0.5, close: 0.45 },
    drawTime: 0.6,
    damage: 105,
    headMul: 1.6,
    falloffStart: 80,
    falloffEnd: 180,
    falloffMin: 0.95,
    range: 300,
    spread: { hip: 0.055, ads: 0.001, move: 0.05, air: 0.14, bloom: 0.03, bloomMax: 0.05, recover: 0.25 },
    recoil: { pitch: 0.065, yaw: 0.013, recover: 5 },
    adsFov: 44,
    moveMul: 0.96,
    adsTime: 0.24,
    velocity: 820,
    fx: { sound: { crack: 7700, crackEnd: 720, body: 108, decay: 0.52, tail: 0.62, vol: 1.15 }, flash: 1.3, eject: 'bolt' }
  }),
  m1903a4: weapon('m1903a4', {
    name: 'M1903A4 Sniper',
    faction: 'allies',
    category: 'scoped',
    desc: 'Springfield with a 2.5x Weaver scope. Loaded one round at a time.',
    action: 'bolt',
    rpm: 40,
    mag: 5,
    reserve: 30,
    reload: { style: 'single', open: 0.5, perRound: 0.55, close: 0.5 },
    drawTime: 0.7,
    damage: 110,
    headMul: 1.6,
    falloffStart: 80,
    falloffEnd: 200,
    falloffMin: 0.95,
    range: 350,
    spread: { hip: 0.08, ads: 0, move: 0.06, air: 0.16, bloom: 0.04, bloomMax: 0.08, recover: 0.25 },
    recoil: { pitch: 0.065, yaw: 0.013, recover: 5 },
    adsFov: 22,
    scope: true,
    moveMul: 0.94,
    adsTime: 0.3,
    velocity: 820,
    fx: { sound: { crack: 7700, crackEnd: 720, body: 108, decay: 0.52, tail: 0.62, vol: 1.15 }, flash: 1.3, eject: 'bolt' }
  }),
  m1carbine: weapon('m1carbine', {
    name: 'M1 Carbine',
    faction: 'allies',
    category: 'semi',
    desc: 'Light semi-automatic carbine. Quick handling, modest punch.',
    rpm: 330,
    mag: 15,
    reserve: 90,
    reloadTime: 2.2,
    drawTime: 0.4,
    damage: 34,
    headMul: 1.8,
    legMul: 0.8,
    falloffStart: 25,
    falloffEnd: 70,
    falloffMin: 0.6,
    range: 200,
    spread: { hip: 0.028, ads: 0.004, move: 0.03, air: 0.12, bloom: 0.012, bloomMax: 0.045, recover: 0.2 },
    recoil: { pitch: 0.016, yaw: 0.006, recover: 7 },
    adsFov: 50,
    moveMul: 1.02,
    adsTime: 0.17,
    velocity: 600,
    fx: { sound: { crack: 5800, crackEnd: 750, body: 150, decay: 0.3, tail: 0.35, vol: 0.95 }, flash: 0.9 }
  }),
  sten: weapon('sten', {
    name: 'Sten Mk II',
    faction: 'allies',
    category: 'smg',
    desc: 'British submachine gun. Cheap, light and twitchy, with a side-mounted magazine.',
    action: 'auto',
    rpm: 540,
    mag: 32,
    reserve: 160,
    reloadTime: 2.4,
    drawTime: 0.32,
    damage: 25,
    headMul: 1.8,
    legMul: 0.8,
    falloffStart: 11,
    falloffEnd: 32,
    falloffMin: 0.5,
    range: 140,
    spread: { hip: 0.032, ads: 0.011, move: 0.024, air: 0.1, crouchMul: 0.75, bloom: 0.005, bloomMax: 0.036, recover: 0.14 },
    recoil: { pitch: 0.008, yaw: 0.007, recover: 6.5 },
    adsFov: 58,
    moveMul: 1.06,
    adsTime: 0.14,
    velocity: 365,
    fx: { sound: { crack: 4000, crackEnd: 550, body: 160, decay: 0.22, tail: 0.25, vol: 0.85 }, flash: 0.8 }
  }),
  bren: weapon('bren', {
    name: 'Bren Mk I',
    faction: 'allies',
    category: 'lmg',
    desc: 'British light machine gun. Famously accurate, sights offset beside the top magazine.',
    action: 'auto',
    rpm: 500,
    mag: 30,
    reserve: 120,
    reloadTime: 3.2,
    drawTime: 0.75,
    damage: 34,
    headMul: 1.75,
    falloffStart: 50,
    falloffEnd: 120,
    falloffMin: 0.75,
    range: 300,
    spread: { hip: 0.05, ads: 0.005, move: 0.055, air: 0.16, crouchMul: 0.55, bloom: 0.008, bloomMax: 0.05, recover: 0.13 },
    recoil: { pitch: 0.013, yaw: 0.005, recover: 6 },
    adsFov: 47,
    moveMul: 0.86,
    adsTime: 0.3,
    velocity: 745,
    fx: { sound: { crack: 7200, crackEnd: 900, body: 118, decay: 0.3, tail: 0.42, vol: 1.1 }, flash: 1.2 }
  }),
  lee_enfield: weapon('lee_enfield', {
    name: 'Lee-Enfield No. 4',
    faction: 'allies',
    category: 'bolt',
    desc: 'British bolt-action rifle. Ten rounds and the fastest bolt in the war.',
    action: 'bolt',
    rpm: 58,
    mag: 10,
    reserve: 50,
    reload: { style: 'charger', clip: 5, open: 0.4, perClip: 1.0, perRound: 0.45, close: 0.4 },
    drawTime: 0.55,
    damage: 100,
    headMul: 1.7,
    falloffStart: 50,
    falloffEnd: 130,
    falloffMin: 0.82,
    range: 300,
    spread: { hip: 0.052, ads: 0.0015, move: 0.05, air: 0.14, bloom: 0.028, bloomMax: 0.05, recover: 0.25 },
    recoil: { pitch: 0.058, yaw: 0.012, recover: 5.5 },
    adsFov: 45,
    moveMul: 0.96,
    adsTime: 0.23,
    velocity: 745,
    fx: { sound: { crack: 7300, crackEnd: 740, body: 112, decay: 0.48, tail: 0.58, vol: 1.12 }, flash: 1.3, eject: 'bolt' }
  }),
  m1911: weapon('m1911', {
    name: 'M1911',
    faction: 'allies',
    category: 'pistol',
    desc: '.45 ACP service pistol. Hard-hitting, seven rounds.',
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
    adsFov: 60,
    velocity: 253,
    fx: { sound: { crack: 5200, crackEnd: 700, body: 180, decay: 0.24, tail: 0.35, vol: 1 }, flash: 0.7 }
  }),
  webley: weapon('webley', {
    name: 'Webley Mk VI',
    faction: 'allies',
    category: 'pistol',
    desc: 'British .455 service revolver. Six heavy rounds, reloaded with a speed-loader.',
    rpm: 300,
    mag: 6,
    reserve: 36,
    reloadTime: 2.2,
    drawTime: 0.3,
    damage: 40,
    legMul: 0.8,
    falloffStart: 14,
    falloffEnd: 40,
    falloffMin: 0.55,
    range: 150,
    spread: { hip: 0.024, ads: 0.007, move: 0.03, air: 0.1, crouchMul: 0.75, bloom: 0.022, bloomMax: 0.065, recover: 0.15 },
    recoil: { pitch: 0.028, yaw: 0.007, recover: 6.5 },
    adsFov: 60,
    velocity: 190,
    fx: { sound: { crack: 4400, crackEnd: 600, body: 160, decay: 0.28, tail: 0.3, vol: 1 }, flash: 0.9, eject: 'none' }
  })
}

// stable numeric codes for compact snapshots
export const WEAPON_LIST = Object.keys(WEAPONS)
export const WEAPON_CODE = Object.fromEntries(WEAPON_LIST.map((id, i) => [id, i]))

export const CATEGORY_NAMES = {
  assault: 'Assault rifle',
  smg: 'Submachine gun',
  bolt: 'Bolt-action rifle',
  scoped: 'Scoped rifle',
  semi: 'Semi-automatic rifle',
  ar: 'Automatic rifle',
  lmg: 'Machine gun',
  pistol: 'Pistol'
}

const SIDEARMS = { axis: ['p38', 'luger'], allies: ['m1911', 'webley'] }

// reserveMul / secondaryReserveMul scale the reserve ammunition of the class's primary / secondary
export const CLASSES = {
  rifleman: {
    name: 'Rifleman',
    desc: 'Balanced general-purpose infantry.',
    primary: { axis: ['kar98k', 'g43'], allies: ['m1garand', 'lee_enfield'] },
    secondary: SIDEARMS,
    reserveMul: 1.25,
    secondaryReserveMul: 1,
    kit: ['Extra rifle ammunition (+25% reserve)']
  },
  assault: {
    name: 'Assault',
    desc: 'Aggressive close-quarters fighting.',
    primary: { axis: ['mp40', 'stg44'], allies: ['thompson', 'sten'] },
    secondary: SIDEARMS,
    reserveMul: 1,
    secondaryReserveMul: 1,
    kit: ['Standard field kit']
  },
  support: {
    name: 'Support',
    desc: 'Sustained fire to pin the enemy down.',
    primary: { axis: ['mg42', 'fg42'], allies: ['bar', 'bren', 'm1919a6'] },
    secondary: SIDEARMS,
    reserveMul: 1.5,
    secondaryReserveMul: 1,
    kit: ['Ammunition box (+50% reserve)']
  },
  marksman: {
    name: 'Marksman',
    desc: 'Accurate long-range fire.',
    primary: { axis: ['kar98k_scoped', 'kar98k'], allies: ['m1903a4', 'm1903'] },
    secondary: SIDEARMS,
    reserveMul: 1,
    secondaryReserveMul: 1,
    kit: ['Telescopic sight (scoped variants)']
  },
  officer: {
    name: 'Officer',
    desc: 'Leads from the front with a sidearm close at hand.',
    primary: { axis: ['mp40', 'g43'], allies: ['thompson', 'm1carbine'] },
    secondary: { axis: ['luger', 'p38'], allies: ['m1911', 'webley'] },
    reserveMul: 1,
    secondaryReserveMul: 2,
    kit: ['Extra pistol magazines (double reserve)']
  },
  engineer: {
    name: 'Engineer',
    desc: 'Light, mobile utility soldier.',
    primary: { axis: ['kar98k', 'mp40'], allies: ['m1carbine', 'm3'] },
    secondary: SIDEARMS,
    reserveMul: 1.25,
    secondaryReserveMul: 1,
    kit: ['Ammunition satchel (+25% reserve)']
  }
}

// Every soldier carries the German stick grenade, whichever side they fight for. It is equipment, not one of the
// two loadout weapons, so the faction rules above (canUse / isValidLoadout) do not apply to it.
export const GRENADE = {
  id: 'stielhandgranate',
  name: 'Stielhandgranate 24',
  count: 1, // per life
  fuse: 3.5, // seconds from pulling the cord; holding G cooks it, and it goes off in the hand when it runs out
  speed: 18, // m/s at release
  loft: 0.18, // rad added above the view direction
  gravity: 9.81,
  radius: 0.05,
  bounce: 0.35,
  friction: 0.65,
  windup: 0.3, // seconds from pressing G to release
  recover: 0.25, // seconds from release until the weapon is drawn again
  damage: 150,
  killRadius: 2, // full damage inside this distance
  blastRadius: 7.5 // no damage beyond this distance
}

export function blastDamage (distance) {
  const { damage, killRadius, blastRadius } = GRENADE
  if (!(distance < blastRadius)) return 0
  if (distance <= killRadius) return damage
  return Math.round(damage * (1 - (distance - killRadius) / (blastRadius - killRadius)))
}

// Quick melee on V. Like the grenade it is equipment every soldier carries, outside the faction-checked loadout.
export const KNIFE = {
  id: 'knife',
  name: { allies: 'M3 Trench Knife', axis: 'Seitengewehr 84/98' },
  damage: 135,
  range: 1.5, // metres from the eye to the surface of the target's body
  cone: 0.6, // rad either side of the view direction
  windup: 0.14, // seconds from pressing V to the strike
  recover: 0.38 // seconds from the strike until the weapon is up again
}

// Every death leaves an ammunition can that anyone, on either side, can walk over to refill their own weapons.
export const AMMO_DROP = {
  share: 0.4, // of the class's starting reserve, per weapon
  lifetime: 30, // seconds on the ground
  radius: 1.1, // pickup reach in metres
  max: 40
}

export const CLASS_IDS = Object.keys(CLASSES)
export const DEFAULT_CLASS = 'assault'
export const FACTIONS = ['allies', 'axis']

const own = (obj, k) => typeof k === 'string' && Object.hasOwn(obj, k)

export function isWeapon (id) { return own(WEAPONS, id) }

// the single faction rule every equip path must go through
export function canUse (team, id) {
  return isWeapon(id) && WEAPONS[id].faction === team
}

export function classOptions (team, cls) {
  const c = CLASSES[own(CLASSES, cls) ? cls : DEFAULT_CLASS]
  return { primary: c.primary[team] || [], secondary: c.secondary[team] || [] }
}

// Returns a valid loadout for `team`, keeping as much of `req` as is allowed. Weapons from another faction (or
// another class) are replaced: the same position in the new faction's list if `req` came from the other faction,
// otherwise the class default.
export function sanitizeLoadout (team, req) {
  const cls = own(CLASSES, req?.cls) ? req.cls : DEFAULT_CLASS
  const c = CLASSES[cls]
  const pick = (slot, want) => {
    const list = c[slot][team]
    if (list.includes(want) && canUse(team, want)) return want
    for (const other of FACTIONS) {
      const i = c[slot][other]?.indexOf(want) ?? -1
      if (other !== team && i >= 0) return list[Math.min(i, list.length - 1)]
    }
    return list[0]
  }
  return { cls, primary: pick('primary', req?.primary), secondary: pick('secondary', req?.secondary) }
}

export function isValidLoadout (team, l) {
  if (!l || !own(CLASSES, l.cls)) return false
  const o = classOptions(team, l.cls)
  return o.primary.includes(l.primary) && o.secondary.includes(l.secondary) && canUse(team, l.primary) && canUse(team, l.secondary)
}

// rounds a soldier of class `cls` spawns with for weapon `id` (in the magazine + in reserve)
export function startingAmmo (cls, id, slot) {
  const c = CLASSES[own(CLASSES, cls) ? cls : DEFAULT_CLASS]
  const w = WEAPONS[id]
  const mul = slot === 'secondary' ? c.secondaryReserveMul : c.reserveMul
  return { mag: w.mag, reserve: Math.round(w.reserve * mul) }
}

// rounds per weapon one ammo can gives a soldier holding `ammo` (weapon id -> magazine + reserve); never past a full spawn load
export function ammoPickup (loadout, ammo) {
  const gain = {}
  for (const slot of ['primary', 'secondary']) {
    const id = loadout[slot]
    const a = startingAmmo(loadout.cls, id, slot)
    const n = Math.min(Math.ceil(a.reserve * AMMO_DROP.share), a.mag + a.reserve - (ammo[id] ?? 0))
    if (n > 0) gain[id] = n
  }
  return gain
}

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
