# Labin Strike

A browser-based, low-poly multiplayer shooter (Team Deathmatch and Search and Destroy) set on **Rudarska ulica in Labin, Croatia**. The map is rebuilt from street-level references, and the gunplay is old-school: hitscan rifles, health that regenerates, and bots that fill empty slots.

![Aerial view of the Rudarska ulica map](docs/screenshots/overview.jpg)

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/gameplay.jpg" alt="In-game view with HUD and bots" /></td>
    <td width="50%"><img src="docs/screenshots/scoreboard.jpg" alt="Team Deathmatch scoreboard" /></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/menu.jpg" alt="Main menu" /></td>
    <td width="50%" valign="top">

**Allies vs Axis**, in two modes that any player can switch from the pause screen:

- **Team Deathmatch.** First team to 50 kills, or the leading team when the 10-minute timer runs out.
- **Search and Destroy.** Rounds without respawns. The attackers plant a demolition charge at one of the defenders' two sites (hold <kbd>F</kbd> for 4 s); the defenders stop them, or defuse it (7 s) before its 40 s fuse runs out. First to 6 rounds. Teams keep their weapons and spawns, so the attacking role swaps at halftime, and each side defends the sites on its own half. Bots plant, guard and defuse too

Features:


- 22 WWII weapons across six classes (Rifleman, Assault, Support, Marksman, Officer, Engineer), each with its own damage falloff, fire rate, recoil, spread, reload style, handling and movement weight
- Strict faction rules: Axis soldiers only ever carry Axis weapons and Allied soldiers Allied ones, enforced by the server
- Aim down sights, sprint, crouch, lean (<kbd>Q</kbd>/<kbd>E</kbd>, to peek round a corner without stepping out), jump, and spawn protection
- Every soldier, on either side, carries one Stielhandgranate 24 stick grenade per life. It bounces off the map and has a 3.5 s fuse that starts when the cord is pulled: hold G to cook it, but hold it too long and it goes off in your hand, and if you are killed with it cooking it drops at your feet. Bots throw theirs at enemies who duck behind cover
- A knife on <kbd>V</kbd> (M3 trench knife or S84/98 bayonet): one stab kills at arm's length. Bots use it up close, and they move in for it while reloading
- Every death, friendly or enemy, leaves an ammo can under the body for 30 s. Walk over it to refill your own weapons' reserve, up to what you spawned with
- Health regenerates COD2-style after 5 s without taking damage
- Tanks, switched on from the pause screen: one per side per match, an M4 Sherman for the Allies and a Panzer IV for the Axis, parked near each side's spawn. Walk up to your own side's tank and press <kbd>F</kbd> to drive it from a chase camera: <kbd>W</kbd><kbd>S</kbd> throttle, <kbd>A</kbd><kbd>D</kbd> turn the hull, the turret follows the mouse, and <kbd>LMB</kbd> fires a high-explosive shell (4 s reload). A tank has 600 armour: rifles and machine guns barely scratch it, grenades, shells and the S&D bomb are what kill it. It runs over enemies, and the crew goes down with it. A destroyed tank stays a smoking wreck until the next match. Bots shoot at enemy tanks and lob their grenades at them
- A motorcycle at each base, all match long: a Harley-Davidson WLA for the Allies and a BMW R35 for the Axis. Walk up to your own side's bike and press <kbd>F</kbd> to ride it from a chase camera: <kbd>W</kbd> throttle (up to 15 m/s), <kbd>S</kbd> brake and reverse, <kbd>A</kbd><kbd>D</kbd> steer, and the mouse looks around. It only turns while it rolls, and leans into the corners. The rider sits in the open with no weapon in hand, so they can be shot off it. A bike has 180 condition: bullets wear it down, a grenade at the wheels, a tank shell or a tank rolling over it wrecks it, and the rider goes down with it. A new one stands at the base a minute after it is destroyed
- Three cats roam the map in place of Counter-Strike's chickens: the main developer's blue-cream tabby plus a ginger and a tuxedo. They meow, flop over on the pavement, and hiss and bolt when you get too close, shoot near them or throw a grenade. Crouch to sneak up on one
- Server-side bots fill the match up to 8 players. They use A* pathfinding, line-of-sight targeting and human-like aim error
- Killfeed, compass/minimap, hitmarkers, damage direction indicators

</td>
  </tr>
</table>

## Quick start

Requires **Node.js 20+**.

```bash
npm install
npm run dev          # http://localhost:7344
```

In dev, the Node server runs the game simulation and serves the client through Vite middleware, all on one port. Open the URL, pick a callsign (and optionally a side) and hit **Deploy**, then choose a class and weapons on the loadout screen. Open a second tab to play against yourself, or let the bots handle it.

Handy URL params: `?name=Mateo` pre-fills the callsign, `?team=axis` picks a side, `?cls=support&primary=mg42&secondary=luger` preselects a loadout, and `?autojoin` deploys as soon as the map loads.

### Controls

| Key | Action | Key | Action |
| --- | --- | --- | --- |
| <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> | Move | Mouse | Aim |
| <kbd>LMB</kbd> | Fire | <kbd>RMB</kbd> | Aim down sights |
| <kbd>Shift</kbd> | Sprint (forward) | <kbd>G</kbd> | Throw grenade (hold to cook) |
| <kbd>Space</kbd> | Jump | <kbd>C</kbd> / <kbd>Ctrl</kbd> | Crouch |
| <kbd>R</kbd> | Reload | <kbd>1</kbd> / <kbd>2</kbd> | Rifle / pistol |
| <kbd>Tab</kbd> | Scoreboard | <kbd>Esc</kbd> | Pause |
| <kbd>V</kbd> | Knife | <kbd>B</kbd> | Loadout / switch side |
| <kbd>Q</kbd> / <kbd>E</kbd> | Lean left / right | <kbd>F</kbd> | Get in / out of your side's tank or onto / off its motorcycle; hold to plant / defuse (Search and Destroy) |

## How it works

```
client/   three.js renderer, input, HUD, viewmodel, audio, prediction   (Vite)
server/   authoritative match simulation (TDM, S&D rounds), bots, nav grid, HTTP + signaling
shared/   constants, Rapier physics + character motor, hitboxes, map parsing
tools/    Blender build scripts for the map and cars, texture/sky generators
```

- **Networking.** [geckos.io](https://github.com/geckos-io/geckos.io) sends data over WebRTC data channels, so it behaves like UDP inside the browser. The server ticks at 30 Hz and sends snapshots at 20 Hz. Clients upload input at 30 Hz and interpolate remote players with a 110 ms buffer. HTTP and the WebRTC UDP mux share port **7344**, so one TCP+UDP firewall rule is enough.
- **Physics.** [Rapier](https://rapier.rs/) runs the same kinematic character motor on both sides: the client for the local player, the server for bots. Movement collides identically everywhere.
- **Grenades.** `shared/grenade.js` steps the flight (gravity, bounces off solid geometry) at a fixed 60 Hz. The server runs it to place the blast and deal damage: full damage within 2 m, nothing past 7.5 m, only to body parts it can see, never to teammates, but to the thrower. Clients replay the same throw so their visual follows the server's path until the `boom` message arrives. The fuse is timed on the server from the client's `cook` message (sent on pressing G) to its `nade` message, so a client cannot shorten or stretch it.
- **Knife and ammo cans.** The client picks who its stab reaches, and the server re-checks reach, angle and line of sight with some slack for latency (`knifeReach` in `shared/hitbox.js`). The server also places the ammo cans, gives each one to the first soldier over it who is short of ammunition, and removes them when they expire. Clients only draw them.
- **Cats.** Where Counter-Strike has chickens, Rudarska ulica has the main developer's cats. `server/cats.js` walks them around the nav grid, lets them stop to look around or lie down, and sends them running from soldiers who come close (crouch to sneak up), from bullets passing near them and from grenades. Nobody can hurt them. They ride along in the snapshots, and `client/src/cats.js` animates the Blender model with code: legs, head and tail each have their own pivot.
- **Hits.** Players have a head sphere plus body and leg capsules, defined in `shared/hitbox.js`. The client claims a hit, and the server checks the shooter's position, the target's position and line of sight before applying damage.
- **Search and Destroy.** `server/sd.js` runs the rounds: one spawn each (joiners still get in during the first 15 s), the round and bomb timers, elimination and halftime. Planting and defusing are timed on the server while the client holds the use key and stays put, so a client cannot shorten them. The four bomb sites in `shared/modes.js` were placed with the nav grid so the defenders reach a site in about half the attackers' time.
- **Tanks.** The driver's client moves the tank with the same Rapier character controller the soldiers use, fitted with a box (`TankBody` in `shared/tanks.js`), and reports its pose like a player does. The server checks the speed and keeps the tank's collider in its own world, so soldiers and bots walk into it. The server fires the shells from its own copy of the turret, settles the armour (hull and turret boxes, tested analytically like the hitboxes), crushes enemies under a moving hull, and parks each side's tank on open ground near its spawns (`server/tanks.js`).
- **Motorcycles.** `BikeBody` in `shared/bikes.js` is the same idea with a narrow box that turns in proportion to its speed. The rider keeps their own hitbox, posed where the bike is and leaned by the bike's lean, so shots and blasts reach them as they would anyone on foot, while the bike is one box with its own condition. `server/bikes.js` parks each side's bike near its spawns, clear of the tank's spot, and puts a new one there a minute after the old one is destroyed. `client/src/bikes.js` builds both bikes from primitives and seats a soldier of the right side on them while they are ridden.
- **Map.** Colliders, spawns and car markers are stored as named nodes inside `parking_lot.glb`. Server and client both read them with `shared/mapdata.js`. The server bakes a 0.5 m walkability grid from the map at startup to give bots their pathfinding.
- **Cars.** Parked cars are instanced from `cars.glb`. Each model costs three draw calls per LOD (paint, opaque, glass), however many copies are on the map.

Match rules and movement live in [`shared/constants.js`](shared/constants.js); modes, Search and Destroy timings and bomb sites in [`shared/modes.js`](shared/modes.js); weapons, classes and faction rules in [`shared/weapons.js`](shared/weapons.js).

## Weapons and loadouts

| Class | Axis primary | Allied primary | Kit |
| --- | --- | --- | --- |
| Rifleman | Kar98k, Gewehr 43 | M1 Garand, Lee-Enfield No. 4 | +25% reserve |
| Assault | MP 40, StG 44 | M1 Thompson, Sten Mk II | |
| Support | MG 42, FG 42 | BAR M1918A2, Bren Mk I, Browning M1919A6 | +50% reserve |
| Marksman | Kar98k Zf. 39, Kar98k | M1903A4, M1903 Springfield | 4x / 2.5x scopes |
| Officer | MP 40, Gewehr 43 | M1 Thompson, M1 Carbine | double pistol reserve |
| Engineer | Kar98k, MP 40 | M1 Carbine, M3 Grease Gun | +25% reserve |

Sidearms: Walther P38 and Luger P08 (Axis), M1911 and Webley Mk VI (Allies).

- **Data-driven.** Every stat (damage and falloff, rpm, magazine and reserve, reload style and timing, hip/ADS/movement spread, bloom, recoil, ADS time and zoom, draw time, movement weight, muzzle velocity, sound and muzzle flash) is a field in `shared/weapons.js`. To add a weapon, add an entry, list it under a class, and optionally give it a model in `client/src/gunmodels.js`.
- **Reload styles.** Detachable magazines, the M1 Garand's en-bloc clip (with the ping when it empties), stripper-clip chargers for bolt-actions (time depends on rounds missing), single-round loading for the scoped rifles, belt reloads for the MG 42 and M1919, and a break-top speed-loader for the Webley. Bolt-actions also work the bolt between shots.
- **Server-authoritative.** The server stores each player's loadout and per-life ammunition. Loadout requests are validated against the player's server-side team and class lists, `fire` is only accepted for the two weapons issued for the current life while rounds remain, and spawning re-checks the loadout. Switching sides (B → Switch) converts the loadout to the other faction's equivalent, is refused when it would stack the humans, and is rate-limited. A class change applies at once within 5 s of spawning if you have not fired or been hit yet, otherwise at the next spawn. Bots roll a random class from their own faction every life.
- The grenade is equipment rather than a loadout weapon: every class on both sides gets `GRENADE.count` per life, so the faction rules do not apply to it. The server only accepts a throw from a living player with a grenade left, from near their own eye position. There are no weapon pickups; any future equip path should go through `canUse()` / `isValidLoadout()` in `shared/weapons.js`.

## Tests

```bash
npm test             # weapon catalogue, faction rules, grenades, the server's loadout / fire / team / movement validation, Search and Destroy rounds, tanks and motorcycles
```

## Production

```bash
npm run build        # builds the client into dist/
npm start            # NODE_ENV=production, serves dist/ + game on :7344
```

`server.sh {start|stop|restart|status}` runs the server as a detached background process with a pid file and `server.log`. `GET /healthz` returns server stats as JSON.

`deploy.sh` builds locally, rsyncs to a VPS, runs `npm ci --omit=dev` only when the lockfile changed, and restarts the server. Set the target in a gitignored `.deploy.env`:

```bash
DEPLOY_HOST=user@example.com
DEPLOY_DIR=/srv/labin-strike
```

Every push to `main` also deploys automatically: [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) runs the tests, builds the client and calls `deploy.sh`. It reads its settings from the `production` environment (Settings → Environments): the `DEPLOY_SSH_KEY` secret and the `DEPLOY_HOST`, `DEPLOY_DIR` and `DEPLOY_KNOWN_HOSTS` variables. You can also run it by hand from the Actions tab.

Environment variables: `PORT` (default `7344`), `UDP_PORT_MIN` / `UDP_PORT_MAX` (default: same as `PORT`).

## Rebuilding assets

The map and cars are generated procedurally in Blender. Their output is committed, so you only need these steps to change the art.

```bash
# Map → client/public/assets/maps/parking_lot.glb
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/rudarska/build.py

# Procedural decals / foliage cards / resized PBR textures (needs Pillow + numpy)
python3 tools/blender/gen_textures.py

# Sky backdrop grading → client/public/assets/sky/sky.jpg
python3 tools/sky_src/grade_sky.py
```

The car models are built with `tools/blender/cars/` and exported to `client/public/assets/cars/cars.glb` by `export.py`.

```bash
# Cats → client/public/assets/cats/cats.glb (add `-- --preview /tmp/cats.png` for a still of every coat)
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/cats/build.py
```

The tanks are Quaternius's low-poly tanks from [Poly Pizza](https://poly.pizza/u/Quaternius), released under CC0 and used unchanged as `client/public/assets/tanks/sherman.glb` and `panzer.glb`. `shared/tanks.js` holds their measured hull and turret sizes at the 0.36 scale the client draws them at.

The headshot sound, `client/public/assets/sounds/headshot.wav`, layers BMacZero's `bing1.wav` from [Metal Impact Sounds](https://opengameart.org/content/metal-impact-sounds) over qubodup's `qubodupImpactMeat02` from [Impact](https://opengameart.org/content/impact), both CC0 on OpenGameArt.

`node tools/test/run_straight.mjs` is a movement check. It runs the character motor across the map in straight lines and reports places where you would snag on open ground.

## License

[MIT](LICENSE) © Mateo Hrastnik
