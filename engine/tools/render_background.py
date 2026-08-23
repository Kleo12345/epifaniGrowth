"""
Render the branded "growing ball" background for journey videos.

Mechanic (kept): a single ball bounces inside a fixed ring and GROWS from small
to nearly ring-sized over the clip, so it "completes" (fills the ring) right as
the video ends — a built-in progress bar / climax, calibrated to the exact video
length so it always finishes on time regardless of duration.

Look (Epifani-branded): deep-navy backdrop with a soft central glow, faint
drifting data-motes and a vignette (no noisy matrix rain); a cyan glowing ring;
and a glossy ball whose colour shifts cyan → elite-green as it fills, with a
faint shockwave ping on each bounce.

All glows are premultiplied (falloff baked into RGB) and blitted additively so
they read as light, not as flat coloured discs.

Self-contained, headless (SDL dummy), streams frames straight to ffmpeg.

Usage:
  python tools/render_background.py            # 30s, 1080x1920, 30fps
  BG_SECONDS=45 python tools/render_background.py
"""
import math
import os
import random
import subprocess
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

W, H, FPS = 1080, 1920, 30

BASE = Path(__file__).resolve().parent.parent
OUT  = BASE / "assets" / "background" / "ball_matrix.mp4"

# Brand palette
NAVY  = (10, 14, 23)      # #0a0e17 backdrop
CYAN  = (0, 242, 255)     # #00f2ff accent (ring + ball start)
GREEN = (0, 255, 136)     # #00ff88 elite (ball end)

BALL_SPEED   = 9.0        # px/frame, constant (no gravity)
FILL_TARGET  = 0.86       # ball ends near-filling the ring (leaves a clear gap)
BOUNCE_POP   = 0.05       # transient radius overshoot on each bounce (visual)
CURVE_DEG    = 0.45       # gentle per-frame curve so paths arc, not straight lines
BOUNCE_JITTER = 24        # ± degrees of random kick on each bounce → varied angles
ADD = pygame.BLEND_RGBA_ADD


def _lerp(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def _glow(diam, color, peak, steps=36):
    """Premultiplied radial glow (transparent edge → bright centre) for additive blit.

    `peak` is the centre brightness in 0..1 of `color`. Because it's baked into the
    RGB channels, additive blitting yields a real light bloom, not a flat disc.
    """
    s = pygame.Surface((diam, diam), pygame.SRCALPHA)
    r = diam // 2
    for i in range(steps, 0, -1):
        f = i / steps
        inten = peak * (1 - f) ** 2
        col = (int(color[0] * inten), int(color[1] * inten), int(color[2] * inten), 255)
        pygame.draw.circle(s, col, (r, r), int(r * f))
    return s


def _vignette():
    """Darken the frame edges (normal alpha) to keep focus centre/lower."""
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    cx, cy = W / 2, H * 0.52
    maxd = math.hypot(cx, cy)
    steps = 60
    for i in range(steps):
        f = i / steps
        pygame.draw.circle(s, (0, 0, 0, int(150 * f ** 2)),
                           (int(cx), int(cy)), int(maxd * (1 - f)),
                           width=int(maxd / steps) + 2)
    return s


# ── parallax depth layer ──────────────────────────────────────────
# A far-back field of tiny dim specks drifting SLOWER than the node network,
# so the scene has real depth (parallax) without adding any bright/busy element.
BACK_SPECKS = 90
BACK_COLOR  = (14, 40, 52)   # very dim navy-cyan (further = darker)


def _make_back():
    return [[random.uniform(0, W), random.uniform(0, H),
             random.uniform(-0.08, 0.08), random.uniform(-0.12, -0.03),
             random.choice([1, 1, 2])] for _ in range(BACK_SPECKS)]


def _draw_back(screen, specks):
    """Far parallax specks: slow drift, dim, no connections. Additive so they
    read as faint distant light, never competing with the foreground."""
    layer = pygame.Surface((W, H), pygame.SRCALPHA)
    for s in specks:
        s[0] = (s[0] + s[2]) % W
        s[1] = (s[1] + s[3]) % H
        pygame.draw.circle(layer, BACK_COLOR, (int(s[0]), int(s[1])), s[4])
    screen.blit(layer, (0, 0), special_flags=ADD)


# ── AI "engine" network layer ─────────────────────────────────────
NET_NODES   = 34      # drifting nodes forming a living graph behind the ball
NET_LINK    = 250     # px: nodes closer than this get connected by a line
NET_NEAR    = 240     # px: nodes within this of the ball light up
NET_BASE    = (18, 66, 84)   # dim connection colour (navy-cyan)


def _make_nodes():
    return [[random.uniform(0, W), random.uniform(0, H),
             random.uniform(-0.25, 0.25), random.uniform(-0.35, -0.08),
             random.randint(1, 3)] for _ in range(NET_NODES)]


def _draw_network(screen, nodes, ball_pos):
    """Nodes + proximity lines on one premultiplied surface, blitted additively.

    Connections fade with distance; nodes/lines near the ball brighten (cyan→green
    energy following the ball) so the graph feels alive and 'computing'.
    """
    layer = pygame.Surface((W, H), pygame.SRCALPHA)
    bx, by = ball_pos
    for n in nodes:
        n[0] = (n[0] + n[2]) % W
        n[1] = (n[1] + n[3]) % H
    for i in range(len(nodes)):
        xi, yi = nodes[i][0], nodes[i][1]
        near_i = math.hypot(xi - bx, yi - by) < NET_NEAR
        for j in range(i + 1, len(nodes)):
            xj, yj = nodes[j][0], nodes[j][1]
            d = math.hypot(xi - xj, yi - yj)
            if d >= NET_LINK:
                continue
            f = 1.0 - d / NET_LINK            # 0..1, closer = brighter
            near = near_i or math.hypot(xj - bx, yj - by) < NET_NEAR
            col = _lerp(NET_BASE, CYAN, 0.6) if near else NET_BASE
            inten = f * (0.9 if near else 0.5)
            c = (int(col[0] * inten), int(col[1] * inten), int(col[2] * inten))
            pygame.draw.line(layer, c, (int(xi), int(yi)), (int(xj), int(yj)), 1)
    for n in nodes:
        near = math.hypot(n[0] - bx, n[1] - by) < NET_NEAR
        col = CYAN if near else _lerp(NET_BASE, CYAN, 0.4)
        inten = 0.8 if near else 0.45
        pygame.draw.circle(layer, (int(col[0] * inten), int(col[1] * inten), int(col[2] * inten)),
                           (int(n[0]), int(n[1])), n[4])
    screen.blit(layer, (0, 0), special_flags=ADD)


# ── progress arc (rides on the ring, fills cyan→green with the video) ──
def _draw_progress_arc(screen, circle, progress):
    """A glowing arc on the ring that sweeps clockwise from 12 o'clock, 0→100%,
    doubling the ball's fill as an explicit 'completion' signal, with a bright
    leading head. Drawn as segments (smooth + glowy, unlike pygame.draw.arc)."""
    if progress <= 0:
        return
    cx, cy = circle.pos
    r = circle.rad
    col = _lerp(CYAN, GREEN, progress)
    sweep = progress * 2 * math.pi
    # dense enough that the segment circles overlap into a smooth line (no beading)
    steps = max(2, int(sweep / (2 * math.pi) * 900))
    for s in range(steps + 1):
        a = math.pi / 2 - (sweep * s / steps)      # start at top, go clockwise
        x = cx + r * math.cos(a)
        y = cy - r * math.sin(a)
        pygame.draw.circle(screen, col, (int(x), int(y)), max(2, circle.width))
    # bright glowing head at the leading edge
    ha = math.pi / 2 - sweep
    hx, hy = cx + r * math.cos(ha), cy - r * math.sin(ha)
    screen.blit(_glow(int(circle.width * 10), (255, 255, 255), 0.7, steps=18),
                (int(hx) - circle.width * 5, int(hy) - circle.width * 5), special_flags=ADD)
    pygame.draw.circle(screen, (255, 255, 255), (int(hx), int(hy)), max(2, circle.width + 1))


class _Circle:
    def __init__(self, pos, rad, width):
        self.pos, self.rad, self.width = pos, rad, width
        self.glow = _glow(int(rad * 2.3), CYAN, 0.30)

    @property
    def inner(self):
        return self.rad - self.width

    def draw(self, screen, flash=0.0):
        screen.blit(self.glow, (self.pos[0] - self.glow.get_width() // 2,
                                self.pos[1] - self.glow.get_height() // 2), special_flags=ADD)
        col = _lerp(CYAN, (255, 255, 255), flash)
        pygame.draw.circle(screen, col, self.pos, int(self.rad), width=max(2, self.width))


class _Ball:
    """Single ball: constant-speed billiard bounce, radius + colour set per frame."""

    def __init__(self, pos, vx, vy, circle, rad, trail=8):
        self.pos = list(pos)
        self.vx, self.vy = vx, vy
        self.rad, self.circle = rad, circle
        self.color = CYAN
        self.trail = trail
        self.positions = []
        self.pop = 0.0
        self.bounced = False
        self.contact = None

    def step(self):
        self.bounced = False
        # gentle constant curve so the path arcs instead of repeating straight lines
        vel = pygame.math.Vector2(self.vx, self.vy).rotate(CURVE_DEG)
        self.vx, self.vy = vel.x, vel.y
        self.pos[0] += self.vx
        self.pos[1] += self.vy

        v = pygame.math.Vector2(self.pos)
        c = pygame.math.Vector2(self.circle.pos)
        dist = v.distance_to(c)
        boundary = self.circle.inner - self.rad

        if dist >= boundary and dist > 0:
            normal = (v - c).normalize()
            refl = pygame.math.Vector2(self.vx, self.vy).reflect(normal)
            # random kick on each bounce → the ball explores many directions
            refl = refl.rotate(random.uniform(-BOUNCE_JITTER, BOUNCE_JITTER))
            # keep it pointing inward so the kick can't send it through the wall
            inward = -normal
            if refl.length() == 0 or refl.normalize().dot(inward) < 0.15:
                refl = inward.rotate(random.uniform(-35, 35))
            spd = refl.normalize() * BALL_SPEED
            self.vx, self.vy = spd.x, spd.y
            overlap = dist - boundary
            self.pos[0] -= normal.x * overlap
            self.pos[1] -= normal.y * overlap
            self.pop = BOUNCE_POP
            self.bounced = True
            self.contact = (c.x + normal.x * self.circle.inner, c.y + normal.y * self.circle.inner)

        self.pop *= 0.8
        if self.trail:
            self.positions.append((int(self.pos[0]), int(self.pos[1]), int(self.rad)))
            if len(self.positions) > self.trail:
                self.positions.pop(0)

    def draw(self, screen):
        cr, cg, cb = self.color
        x, y = int(self.pos[0]), int(self.pos[1])
        r = int(self.rad * (1 + self.pop))

        # comet trail: same-hue, tapering in both brightness AND width toward the
        # tail (premultiplied additive so it reads as a light streak, not discs)
        n = len(self.positions)
        for idx, (tx, ty, tr) in enumerate(self.positions):
            f = (idx + 1) / n                      # 0 (oldest) → 1 (newest)
            inten = 0.40 * f * f
            br = max(2, int(tr * 0.62 * f))         # width tapers to the tail
            ts = pygame.Surface((br * 2, br * 2), pygame.SRCALPHA)
            pygame.draw.circle(ts, (int(cr * inten), int(cg * inten), int(cb * inten), 255),
                               (br, br), br)
            screen.blit(ts, (tx - br, ty - br), special_flags=ADD)

        # soft outer glow
        screen.blit(_glow(int(r * 2.8), self.color, 0.5, steps=24),
                    (x - int(r * 1.4), y - int(r * 1.4)), special_flags=ADD)

        # spherical body: darker rim → brighter core
        body = pygame.Surface((2 * r + 2, 2 * r + 2), pygame.SRCALPHA)
        steps = max(6, r // 12)
        for s in range(steps, 0, -1):
            f = s / steps
            shade = 0.5 + 0.5 * (1 - f)
            pygame.draw.circle(body, (int(cr * shade), int(cg * shade), int(cb * shade), 255),
                               (r + 1, r + 1), int(r * f))
        hl = pygame.Surface((2 * r + 2, 2 * r + 2), pygame.SRCALPHA)
        pygame.draw.circle(hl, (255, 255, 255, 110), (int(r * 0.68), int(r * 0.6)), max(2, int(r * 0.3)))
        body.blit(hl, (0, 0))
        screen.blit(body, (x - r - 1, y - r - 1))
        pygame.draw.circle(screen, (255, 255, 255), (x, y), r, width=max(2, int(r / 26)))


def render(out_path, duration: float, loudness=None, seed=None) -> Path:
    """Render the branded growing-ball background of exactly `duration` seconds."""
    if seed is not None:
        random.seed(seed)
    pygame.init()
    screen = pygame.Surface((W, H))

    center_glow = _glow(int(W * 1.7), CYAN, 0.11)
    vignette = _vignette()
    back = _make_back()
    nodes = _make_nodes()

    circle = _Circle(pos=(W // 2, H // 2), rad=W / 2.1, width=max(3, int(W / 220)))
    ang = random.uniform(0, 2 * math.pi)
    ball = _Ball([W / 2, H / 2], BALL_SPEED * math.cos(ang), BALL_SPEED * math.sin(ang),
                 circle, rad=W / 16, trail=16)
    r_start, r_end = W / 16, FILL_TARGET * circle.inner
    shockwaves = []

    total = int(round(duration * FPS))
    cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-g", str(FPS * 2), str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    for i in range(total):
        progress = i / max(1, total - 1)
        ball.rad = r_start + (r_end - r_start) * progress
        ball.color = _lerp(CYAN, GREEN, progress)

        screen.fill(NAVY)
        screen.blit(center_glow, (W // 2 - center_glow.get_width() // 2,
                                  int(H * 0.5) - center_glow.get_height() // 2), special_flags=ADD)
        _draw_back(screen, back)                 # far parallax layer (behind everything)
        _draw_network(screen, nodes, ball.pos)

        circle.draw(screen, 1.0 if ball.pop > 0.02 else 0.0)
        _draw_progress_arc(screen, circle, progress)
        ball.step()
        if ball.bounced and ball.contact:
            shockwaves.append([ball.contact[0], ball.contact[1], 0])
        for sw in shockwaves:
            age = sw[2]
            rad = int(20 + age * 9)
            inten = max(0.0, 0.55 - age * 0.06)
            if inten > 0:
                srf = pygame.Surface((rad * 2 + 4, rad * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(srf, (int(ball.color[0] * inten), int(ball.color[1] * inten),
                                         int(ball.color[2] * inten), 255),
                                   (rad + 2, rad + 2), rad, width=3)
                screen.blit(srf, (int(sw[0]) - rad - 2, int(sw[1]) - rad - 2), special_flags=ADD)
            sw[2] += 1
        shockwaves = [s for s in shockwaves if s[2] < 10]

        ball.draw(screen)
        screen.blit(vignette, (0, 0))
        proc.stdin.write(pygame.image.tostring(screen, "RGB"))

    proc.stdin.close()
    proc.wait()
    pygame.quit()
    return Path(out_path)


def main():
    duration = float(os.getenv("BG_SECONDS", "30"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"Rendering {duration:.0f}s → {OUT.name}")
    render(OUT, duration)
    print(f"✓ Background written: {OUT}")


if __name__ == "__main__":
    main()
