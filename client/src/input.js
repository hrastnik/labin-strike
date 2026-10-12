// Keyboard / mouse / pointer-lock input. Edge-triggered actions are queued and consumed once per frame.

export class Input {
  constructor (canvas) {
    this.canvas = canvas
    this.keys = new Set()
    this.pressed = new Set()
    this.mouse = { dx: 0, dy: 0, left: false, right: false, leftPressed: false, wheel: 0 }
    this.locked = false
    this.sensitivity = 1
    this.onLockChange = null
    this.enabled = false

    window.addEventListener('keydown', (e) => {
      if (!this.enabled) return
      if (e.target instanceof HTMLInputElement) return
      if (['Tab', 'Space', 'ArrowUp', 'ArrowDown', 'ControlLeft', 'KeyC'].includes(e.code) || (e.ctrlKey && e.code === 'KeyW')) e.preventDefault()
      if (!this.keys.has(e.code)) this.pressed.add(e.code)
      this.keys.add(e.code)
    })
    window.addEventListener('keyup', (e) => { this.keys.delete(e.code) })
    window.addEventListener('blur', () => { this.keys.clear(); this.mouse.left = this.mouse.right = false })

    document.addEventListener('mousemove', (e) => {
      if (!this.locked) return
      // ignore the occasional huge spike some browsers emit when re-locking
      if (Math.abs(e.movementX) > 600 || Math.abs(e.movementY) > 600) return
      this.mouse.dx += e.movementX
      this.mouse.dy += e.movementY
    })
    document.addEventListener('mousedown', (e) => {
      if (!this.locked) return
      if (e.button === 0) { this.mouse.left = true; this.mouse.leftPressed = true }
      if (e.button === 2) this.mouse.right = true
    })
    document.addEventListener('mouseup', (e) => {
      if (e.button === 0) this.mouse.left = false
      if (e.button === 2) this.mouse.right = false
    })
    document.addEventListener('wheel', (e) => { if (this.locked) this.mouse.wheel += Math.sign(e.deltaY) }, { passive: true })
    document.addEventListener('contextmenu', (e) => e.preventDefault())
    document.addEventListener('pointerlockchange', () => {
      this.locked = document.pointerLockElement === this.canvas
      if (!this.locked) { this.mouse.left = this.mouse.right = false; this.keys.clear() }
      this.onLockChange?.(this.locked)
    })
    document.addEventListener('pointerlockerror', () => this.onLockChange?.(false, true))
  }

  lock () {
    if (this.locked) return
    // without a user gesture the request is rejected; the pause overlay then asks for a click
    const plain = () => {
      try { this.canvas.requestPointerLock()?.catch?.(() => {}) } catch {}
    }
    try {
      const p = this.canvas.requestPointerLock({ unadjustedMovement: true })
      // unadjustedMovement is unsupported on some platforms: retry without it
      p?.catch?.((err) => { if (err?.name !== 'NotAllowedError') plain() })
    } catch {
      plain()
    }
  }

  unlock () { if (document.pointerLockElement) document.exitPointerLock() }

  down (code) { return this.keys.has(code) }
  wasPressed (code) { return this.pressed.has(code) }

  consumeLook () {
    const k = 0.0022 * this.sensitivity
    const r = [this.mouse.dx * k, this.mouse.dy * k]
    this.mouse.dx = this.mouse.dy = 0
    return r
  }

  endFrame () {
    this.pressed.clear()
    this.mouse.leftPressed = false
    this.mouse.wheel = 0
  }
}
