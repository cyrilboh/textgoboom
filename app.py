from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>textgoboom - Fireworks</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #000; overflow: hidden; }
  canvas { display: block; }
</style>
</head>
<body>
<canvas id="c"></canvas>
<script>
"use strict";

const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");

let W, H;
function resize() {
  W = canvas.width = window.innerWidth;
  H = canvas.height = window.innerHeight;
}
resize();
window.addEventListener("resize", resize);

/* ---------- CONFIG ---------- */
const TEXT = __TEXT_JSON__;
const GRAVITY = 0.04;
const FRICTION = 0.985;
const FADE_RATE = 0.012;
const HUE_CYCLE_SPEED = 0.5;

/* ---------- HELPERS ---------- */
function rand(min, max) { return Math.random() * (max - min) + min; }

/* ---------- TEXT TARGET POINTS ---------- */
function getTextPoints(text) {
  const offscreen = document.createElement("canvas");
  const octx = offscreen.getContext("2d");

  // Size the font to fit well on screen
  const fontSize = Math.min(Math.floor(W / (text.length * 0.65)), Math.floor(H * 0.35));
  offscreen.width = W;
  offscreen.height = H;

  octx.fillStyle = "#fff";
  octx.font = `bold ${fontSize}px Arial, Helvetica, sans-serif`;
  octx.textAlign = "center";
  octx.textBaseline = "middle";
  octx.fillText(text, W / 2, H / 2);

  const imageData = octx.getImageData(0, 0, W, H).data;
  const points = [];
  const gap = 4; // sample every 4 pixels for density

  for (let y = 0; y < H; y += gap) {
    for (let x = 0; x < W; x += gap) {
      const i = (y * W + x) * 4;
      if (imageData[i + 3] > 128) {
        points.push({ x, y });
      }
    }
  }
  return points;
}

/* ---------- PARTICLE ---------- */
class Particle {
  constructor(x, y, vx, vy, hue, targetX, targetY) {
    this.x = x;
    this.y = y;
    this.vx = vx;
    this.vy = vy;
    this.hue = hue;
    this.alpha = 1;
    this.targetX = targetX !== undefined ? targetX : null;
    this.targetY = targetY !== undefined ? targetY : null;
    this.settled = false;
    this.settledTime = 0;
    this.trail = [];
  }

  update() {
    this.trail.push({ x: this.x, y: this.y, alpha: this.alpha });
    if (this.trail.length > 6) this.trail.shift();

    if (this.targetX !== null && !this.settled) {
      // Guided particle: steer toward target
      const dx = this.targetX - this.x;
      const dy = this.targetY - this.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < 2) {
        this.settled = true;
        this.vx = 0;
        this.vy = 0;
        this.x = this.targetX;
        this.y = this.targetY;
      } else {
        // Ease toward target
        this.vx += dx * 0.035;
        this.vy += dy * 0.035;
        this.vx *= 0.92;
        this.vy *= 0.92;
        this.x += this.vx;
        this.y += this.vy;
      }
    } else if (this.settled) {
      // Hold position, then fade
      this.settledTime++;
      if (this.settledTime > 120) {
        this.alpha -= FADE_RATE * 1.5;
      }
    } else {
      // Free particle: normal physics
      this.vy += GRAVITY;
      this.vx *= FRICTION;
      this.vy *= FRICTION;
      this.x += this.vx;
      this.y += this.vy;
      this.alpha -= FADE_RATE;
    }
  }

  draw() {
    // Draw trail
    for (let i = 0; i < this.trail.length; i++) {
      const t = this.trail[i];
      const a = (i / this.trail.length) * this.alpha * 0.4;
      ctx.beginPath();
      ctx.arc(t.x, t.y, 1.5, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${this.hue}, 100%, 60%, ${a})`;
      ctx.fill();
    }

    // Draw particle
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.settled ? 2 : 2.5, 0, Math.PI * 2);
    ctx.fillStyle = `hsla(${this.hue}, 100%, 70%, ${this.alpha})`;
    ctx.fill();
  }

  get alive() {
    return this.alpha > 0.01;
  }
}

/* ---------- ROCKET ---------- */
class Rocket {
  constructor(targetX, targetY) {
    this.x = rand(W * 0.2, W * 0.8);
    this.y = H;
    this.targetX = targetX !== undefined ? targetX : this.x + rand(-50, 50);
    this.targetY = targetY !== undefined ? targetY : rand(H * 0.1, H * 0.35);
    this.vx = (this.targetX - this.x) * 0.018;
    this.vy = -rand(8, 12);
    this.hue = rand(0, 360);
    this.trail = [];
    this.exploded = false;
  }

  update() {
    this.trail.push({ x: this.x, y: this.y, alpha: 1 });
    if (this.trail.length > 12) this.trail.shift();
    for (const t of this.trail) t.alpha -= 0.05;

    this.x += this.vx;
    this.vy += GRAVITY * 1.5;
    this.y += this.vy;

    if (this.vy >= 0 || this.y <= this.targetY) {
      this.exploded = true;
    }
  }

  draw() {
    for (let i = 0; i < this.trail.length; i++) {
      const t = this.trail[i];
      if (t.alpha <= 0) continue;
      ctx.beginPath();
      ctx.arc(t.x, t.y, 2, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${this.hue}, 80%, 70%, ${Math.max(0, t.alpha)})`;
      ctx.fill();
    }
    ctx.beginPath();
    ctx.arc(this.x, this.y, 3, 0, Math.PI * 2);
    ctx.fillStyle = `hsla(${this.hue}, 100%, 85%, 1)`;
    ctx.fill();
  }
}

/* ---------- STATE ---------- */
let particles = [];
let rockets = [];
let textPoints = null;
let textPointIndex = 0;
let globalHue = 0;
let textWaves = 0;
const MAX_TEXT_WAVES = TEXT ? 99999 : 0; // effectively infinite for text mode

if (TEXT) {
  textPoints = getTextPoints(TEXT);
  // Shuffle so fireworks fill in randomly
  for (let i = textPoints.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [textPoints[i], textPoints[j]] = [textPoints[j], textPoints[i]];
  }
}

/* ---------- EXPLODE ---------- */
function explodeRandom(x, y, hue) {
  const count = Math.floor(rand(60, 120));
  for (let i = 0; i < count; i++) {
    const angle = rand(0, Math.PI * 2);
    const speed = rand(1, 5);
    const vx = Math.cos(angle) * speed;
    const vy = Math.sin(angle) * speed;
    const h = hue + rand(-20, 20);
    particles.push(new Particle(x, y, vx, vy, h));
  }
}

function explodeText(x, y, hue) {
  if (!textPoints || textPoints.length === 0) return;

  // Assign a batch of text points to this explosion
  const batchSize = Math.min(Math.floor(rand(30, 70)), textPoints.length - textPointIndex);
  if (textPointIndex >= textPoints.length) {
    // All text points assigned: do a normal explosion instead, or restart
    textPointIndex = 0;
    textWaves++;
    // Clear old text particles when restarting
    particles = particles.filter(p => p.targetX === null);
    // Reshuffle and get new points (recompute to handle resize)
    textPoints = getTextPoints(TEXT);
    for (let i = textPoints.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [textPoints[i], textPoints[j]] = [textPoints[j], textPoints[i]];
    }
  }

  for (let i = 0; i < batchSize && textPointIndex < textPoints.length; i++, textPointIndex++) {
    const tp = textPoints[textPointIndex];
    const angle = rand(0, Math.PI * 2);
    const speed = rand(1, 4);
    const vx = Math.cos(angle) * speed;
    const vy = Math.sin(angle) * speed;
    const h = hue + rand(-15, 15);
    particles.push(new Particle(x, y, vx, vy, h, tp.x, tp.y));
  }
}

/* ---------- MAIN LOOP ---------- */
let lastRocket = 0;
const rocketInterval = TEXT ? 300 : 700; // faster rockets for text mode

function loop(ts) {
  // Semi-transparent overlay for trail effect
  ctx.fillStyle = "rgba(0, 0, 0, 0.15)";
  ctx.fillRect(0, 0, W, H);

  globalHue = (globalHue + HUE_CYCLE_SPEED) % 360;

  // Launch rockets
  if (ts - lastRocket > rocketInterval) {
    lastRocket = ts;
    if (TEXT) {
      // For text mode, launch toward spread-out positions
      const rx = rand(W * 0.2, W * 0.8);
      const ry = rand(H * 0.2, H * 0.5);
      rockets.push(new Rocket(rx, ry));
    } else {
      rockets.push(new Rocket());
    }
  }

  // Update & draw rockets
  for (let i = rockets.length - 1; i >= 0; i--) {
    const r = rockets[i];
    r.update();
    if (r.exploded) {
      if (TEXT) {
        explodeText(r.x, r.y, r.hue);
      } else {
        explodeRandom(r.x, r.y, r.hue);
      }
      rockets.splice(i, 1);
    } else {
      r.draw();
    }
  }

  // Update & draw particles
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i];
    p.update();
    if (!p.alive) {
      particles.splice(i, 1);
    } else {
      p.draw();
    }
  }

  requestAnimationFrame(loop);
}

requestAnimationFrame(loop);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        text = qs.get("text", [None])[0]

        # Build page with the text parameter injected safely
        # Escape </ sequences to prevent script tag injection
        text_json = json.dumps(text).replace("<", r"\u003c").replace(">", r"\u003e")
        page = HTML_PAGE.replace("__TEXT_JSON__", text_json)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page.encode())))
        self.end_headers()
        self.wfile.write(page.encode())

    def log_message(self, format, *args):
        # Quieter logging
        print(f"[textgoboom] {args[0]}")


if __name__ == "__main__":
    port = 8124
    print(f"Starting textgoboom on http://127.0.0.1:{port}")
    print(f"  Open http://127.0.0.1:{port}          for random fireworks")
    print(f"  Open http://127.0.0.1:{port}?text=BOOM for text fireworks")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
