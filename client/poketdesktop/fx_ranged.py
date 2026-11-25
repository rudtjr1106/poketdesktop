# -*- coding: utf-8 -*-
"""날아가는 것 · 쏟아지는 것 · 솟는 것 — 닿지 않는 기술의 연출.

연출 하나는 fx(battle_fx.Effect) 의 시간표(fx.show)에 장면(act)과 신호(cue)를 넣는 함수다. 시각은 전부 ms 고,
넣은 것이 다 지나가면 연출이 끝난다. 그리는 법은 fx_kit 머리말에.

    모으기 -> 쏘기 -> 맞는 순간(K.impact) 의 세 박자가 기본이다. 큰 기술일수록 모으는 박자가 길다.
"""
import math
import random

from . import fx_kit as K

WHITE = K.WHITE
TAU = K.TAU
cos, sin = math.cos, math.sin


def power_of(fx):
    return fx.move.get("power") or 0


def is_status(fx):
    return (fx.move.get("cat") or "status") == "status"


# ---------------------------------------------------------------- 함께 쓰는 장면
def charge(fx, at, dur, x, y, size=1.0, typ=None, n=9):
    """기운을 모은다: 둘레에서 쐐기가 빨려 들고, 고리가 조여들고, 구슬이 자란다. 다 모이면 한 번 번쩍."""
    c = K.tone(typ or fx.type)
    cols = c.tri
    k = size
    seeds = [random.uniform(0, TAU) for _ in range(n)]

    def draw(p, u, ms):
        for j in range(n):                                  # 빨려 드는 쐐기
            ph = (u * 2.4 + j / float(n)) % 1.0
            a = seeds[j] + u * 1.6
            r0 = (60 - 48 * ph) * k
            r1 = max(3.0, r0 - (12 + 12 * (1 - ph)) * k)
            K.streak(p, x + cos(a) * r0, y + sin(a) * r0 * 0.85, x + cos(a) * r1, y + sin(a) * r1 * 0.85,
                     2.4 * k * (1 - ph * 0.5), c.light if j % 2 else c.hot)
        K.arcs(p, x, y, (42 - 30 * K.in2(u)) * k, c.base, 2, ms * 0.9, 3, 70, 0.9)
        r = (3 + 11 * K.out2(u)) * k * (1 + 0.08 * sin(ms * 0.05))
        if getattr(p, "raster", False):
            p.glow(x, y, r * 3.0, cols[0], 0.5 + 0.5 * u)
        else:
            K.flare(p, x, y, r * 1.9, 8, cols[0], inner=0.6, rot=ms * 0.012)
        K.orb(p, x, y, r, cols)
        if u > 0.8:
            K.glint(p, x, y, (22 + 34 * (u - 0.8) / 0.2) * k, WHITE)
    return fx.show.act(at, dur, draw)


def muzzle(fx, at, x, y, size=1.0, typ=None):
    """쏘는 순간 몸 앞에서 터지는 섬광과 고리."""
    c = K.tone(typ or fx.type)

    def draw(p, u, ms):
        r = (14 + 30 * K.out3(u)) * size
        if u < 0.7:
            K.ring(p, x, y, r, c.light, max(2, int(6 * (1 - u))), 0.9)
        if u < 0.5:
            K.flare(p, x, y, (30 - 20 * u) * size, 8, c.hot, inner=0.3, rot=u * 2)
            if getattr(p, "raster", False):
                p.glow(x, y, (34 - 20 * u) * size, c.base, 1.0 - u)
    return fx.show.act(at, 180, draw)


def trail(m, g, born0, born1, n, path, spread=6.0, life=(200, 340), size=(2.5, 5.0), drift=10.0, lift=0.0, g_=0.0):
    """길(path(u) -> (x, y))을 따라 시간차로 흘리는 조각들을 Motes 에 넣는다."""
    r = m.rnd
    for j in range(n):
        u = (j + r.uniform(0.0, 1.0)) / float(n)
        x, y = path(u)
        a = r.uniform(0, TAU)
        m.add(born0 + (born1 - born0) * u, r.uniform(*life), x + r.uniform(-spread, spread),
              y + r.uniform(-spread, spread), cos(a) * drift, sin(a) * drift, g_, r.uniform(*size),
              r.uniform(0, TAU), r.uniform(-5, 5), lift)


# ---------------------------------------------------------------- 광선
def laser(fx):
    """광선: 기운을 모아 굵은 빛기둥을 쏜다. 빛기둥은 가장자리가 일렁이고, 테가 줄기를 타고 달리고, 나선이 감긴다.

    맞는 쪽은 줄기가 닿아 있는 동안 떤다. 얼음이면 맞은 자리에 결정이 돋고, 오로라 · 시그널은 무지갯빛이다.
    위력 120 이상(파괴광선 · 솔라빔 ...)은 오래 모으고 굵다.
    """
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    key = K.key_of(fx.move)
    pw = power_of(fx)
    strong = pw >= 120 or any(w in key for w in ("solar", "hyper", "meteor", "eterna", "giga"))
    rainbow = any(w in key for w in ("aurora", "prismatic", "signal"))
    C = 360 if strong else 230
    F = 520 if strong else 380
    W = 4.5 if pw < 80 else 6.5 if pw < 120 else 9.0
    mx, my = g.mouth(18)
    cols = c.tri
    ln = math.hypot(g.tx - mx, g.ty - my) or 1.0
    seed = random.randrange(1000)
    N = 9

    charge(fx, 0, C, mx, my, size=1.15 if strong else 0.9)
    muzzle(fx, C, mx, my, 1.3 if strong else 1.0)
    K.recoil(fx, C, 1.3 if strong else 0.7)
    K.shake(fx, C + 80, F - 80, amp=2.4 if strong else 1.4)

    def beam(p, u, ms):
        reach = K.out3(ms / 85.0)
        thin = 1.0 if ms < F - 120 else max(0.0, (F - ms) / 120.0)
        w = W * thin * (1.0 + 0.14 * sin(ms * 0.05))
        if w < 0.4:
            return
        pts = g.path(0.0, reach, N, m=(mx, my))
        if rainbow:
            for col, off in (("#ff7ad0", -1.0), ("#ffe36e", -0.33), ("#7affb8", 0.33), ("#7ac8ff", 1.0)):
                q = g.path(0.0, reach, N, off=lambda u_, o=off: o * w * 1.25 + sin(u_ * 9 - ms * 0.02) * 1.5,
                           m=(mx, my))
                K.ribbon(p, q, w * 0.55, col)
            K.ribbon(p, pts, w * 0.42, WHITE)
        else:
            rim = [w * 1.95 * (0.55 if i == 0 else 1.0) * (1.0 + 0.16 * sin(i * 2.3 - ms * 0.035)) for i in range(N + 1)]
            K.ribbon(p, pts, rim, cols[0])
            K.ribbon(p, pts, [v * 0.66 for v in rim], cols[1])
            K.ribbon(p, pts, w * 0.5, cols[2] if fx.type not in ("GHOST", "DARK") else c.alt)
            for j, col in enumerate((c.hot, c.alt)):        # 감기는 나선
                q = g.path(0.0, reach, 14, off=lambda u_, o=j: sin(u_ * ln * 0.085 - ms * 0.03 + o * math.pi)
                           * (w * 1.7 + 2), m=(mx, my))
                p.line(q, col, 2, smooth=True)
        for j in range(3):                                  # 줄기를 타고 달리는 테
            uu = (ms * 0.0019 + j / 3.0) % 1.0
            if uu < reach - 0.04:
                x, y = mx + (g.tx - mx) * uu, my + (g.ty - my) * uu
                K.hoop(p, x, y, w * 0.7, w * (2.5 + uu), g.ang, c.hot, 2)
        # 쏘는 곳
        K.flare(p, mx, my, (W + 13) * thin * (1.1 if int(ms / 40) % 2 else 0.95) + 2, 8, cols[1], inner=0.45,
                rot=ms * 0.012)
        K.orb(p, mx, my, (W + 4) * thin + 1.5, cols, shine=False)
        # 닿은 곳
        if reach > 0.97:
            r = (W * 1.5 + 5 + 3 * (int(ms / 40) % 2)) * thin
            rnd = random.Random(seed + int(ms / 45))
            for _q in range(5):
                a = rnd.uniform(0, TAU)
                l0, l1 = r * 0.8, r + rnd.uniform(10, 24) * k
                K.streak(p, g.tx + cos(a) * l0, g.ty + sin(a) * l0, g.tx + cos(a) * l1, g.ty + sin(a) * l1,
                         2.0 * thin + 0.4, c.light if _q % 2 else WHITE)
            K.disc(p, g.tx, g.ty, r * 1.25, cols[1])
            K.disc(p, g.tx, g.ty, r * 0.8, WHITE)
            if fx.type == "ICE":                            # 얼어붙는다
                f = min(1.0, (ms - 85) / 240.0)
                for j in range(6):
                    a = j * math.pi / 3 + 0.3
                    K.spike(p, g.tx + cos(a) * 6, g.ty + sin(a) * 6, 4.5 * k, (10 + 22 * f) * k, a, c.light, c.dark)
    sh.act(C, F, beam)
    if strong:                                              # 발밑이 울린다
        def ground(p, u, ms):
            r = (20 + 60 * K.out2(u)) * k
            K.ring(p, g.sx, g.gs, r, c.light, max(1, int(4 * (1 - u))), 0.24)
        sh.act(C, 320, ground, z=-3)
    K.impact(fx, C + F - 70, size=1.45 if strong else 1.2)


# ---------------------------------------------------------------- 번개
def thunder(fx):
    """번개: 몸에 전기가 감기고, 하늘에서 굵은 벼락이 내리꽂힌다. 깜빡이며 두세 번 치고, 땅을 타고 전기가 번진다.

    벼락 뒤로 빛기둥이 서고(번쩍임), 꽂힌 자리에서 섬광이 퍼진다. 맞는 쪽은 감전된 동안 떤다.
    """
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    cols = (c.dark, c.base, c.hot)
    big = power_of(fx) >= 100
    A = 250
    seed = random.randrange(1000)
    top = g.top
    gy = g.ty + 10
    # (치는 때, 머무는 시간, 굵기, 옆으로 비킨 만큼)
    strikes = [(0, 110, 5.5, -18), (160, 90, 3.6, 14)] + ([(290, 80, 4.6, -4)] if big else [])

    def crackle(p, u, ms):                                  # 쓰는 쪽 몸에 감기는 전기
        rnd = random.Random(seed + int(ms / 45))
        for _q in range(4):
            a = rnd.uniform(0, TAU)
            r = rnd.uniform(18, 34) * (0.6 + 0.6 * u)
            K.bolt(p, K.zigzag(g.sx, g.sy, g.sx + cos(a) * r, g.sy + sin(a) * r * 0.9, 6, 4, rnd), 1, cols)
        K.arcs(p, g.sx, g.sy, (34 - 16 * u), c.light, 2, ms * 1.3, 3, 60, 0.85)
        if u > 0.75:
            K.glint(p, g.sx, g.sy - 14, 20 * (u - 0.75) / 0.25 + 6, WHITE)
    sh.act(0, A, crackle)

    def strike(p, u, ms):
        for n_, (t0, hold, w, off) in enumerate(strikes):
            a = ms - t0
            if a < 0 or a > hold + 70:
                continue
            rnd = random.Random(seed + n_ * 31 + int(a / 45))
            x0 = g.tx - g.face * 10 + off + rnd.uniform(-6, 6)
            pts = K.zigzag(x0, top, g.tx, gy, 15, 8, rnd)
            if a <= hold:
                # 벼락 뒤의 빛기둥
                if getattr(p, "raster", False):
                    p.glow_line([x0, top, (x0 + g.tx) / 2, (top + gy) / 2, g.tx, gy], c.base, w * 7.0, 0.9)
                    p.glow(g.tx, gy, 40 * k, c.light, 1.0, 0.5)
                else:
                    K.ribbon(p, [x0, top, (x0 + g.tx) / 2, (top + gy) / 2, g.tx, gy], [w * 3.2, w * 2.4, w * 1.2],
                             c.dark, smooth=True)
                K.bolt(p, pts, int(round(w * k)), cols)
                for _q in range(2):                         # 가지
                    q = rnd.randrange(2, 7) * 2
                    sgn = rnd.choice((-1, 1))
                    K.bolt(p, K.zigzag(pts[q], pts[q + 1], pts[q] + sgn * rnd.uniform(24, 46),
                                       pts[q + 1] + rnd.uniform(10, 30), 6, 3, rnd), 1, cols)
                r = (34 - 18 * a / hold) * k                # 꽂힌 자리의 섬광
                p.oval(g.tx, gy, r * 1.3, r * 0.5, c.hot, c.base, 3)
                K.flare(p, g.tx, gy - 4, r * 1.1, 6, WHITE, inner=0.35, rot=n_ + a * 0.01, sy=0.8)
            else:                                           # 잔상 한 줄
                p.line(pts, c.light, 1, cap="butt")
        if ms > 60:                                         # 땅을 타고 번지는 전기
            rnd = random.Random(seed + 7 + int(ms / 50))
            f = min(1.0, ms / 300.0)
            for sgn in (-1, 1):
                p.line(K.zigzag(g.tx, g.gt - 6, g.tx + sgn * (20 + 44 * f), g.gt - 6 + rnd.uniform(-3, 3), 4, 5, rnd),
                       c.light if int(ms / 50) % 2 else WHITE, 2, cap="butt")
    total = strikes[-1][0] + strikes[-1][1] + 70
    sh.act(A, total, strike)
    K.shake(fx, A, total, amp=2.6)
    K.impact(fx, A + total - 130, size=1.3)


# ---------------------------------------------------------------- 지진
def quake(fx):
    """지진: 쓰는 쪽이 땅을 내리찍으면 금이 달려가고, 맞는 쪽 발밑에서 바위가 줄줄이 솟구친다.

    그동안 두 도트가 다 흔들린다 (땅이 흔들리는 것이다). 솟은 바위는 밝은 면과 어두운 면이 있고, 흙덩이가 튄다.
    """
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    seed = random.randrange(1000)
    rnd = random.Random(seed)
    gx, gy = g.tx, g.gt
    crack = K.zigzag(g.sx, g.gs, gx, gy, 7, 9, rnd)
    npts = len(crack) // 2
    A, B = 300, 620
    slabs = [(0, 46, 11), (-19, 33, 9), (18, 36, 9), (-37, 21, 7), (36, 23, 7)]     # (옆으로, 높이, 폭) 가운데부터
    m = K.Motes(seed)
    for q, (ox, h, w) in enumerate(slabs):
        m.burst(A + q * 55, 3, gx + ox * k, gy, dist=(14, 34), life=(360, 520), ang=(-2.6, -0.5), g=640,
                size=(2.5, 5.0))
    paint = K.mote("GROUND")
    # 쓰는 쪽이 뛰어올라 내리찍는다
    src = K.Mover(fx, None if fx.hidden(fx.keys[0]) else fx.keys[0])

    def stomp(p, u, ms):
        src.to(0.0, -9.0 * K.hump(u) if u < 1 else 0.0)
    sh.act(0, 170, stomp, settle=src.home, z=-9)

    def shock(p, u, ms):                                    # 내리찍은 자리에서 번지는 충격
        for j in range(2):
            v = K.clamp(u * 1.3 - j * 0.25)
            if 0 < v < 1:
                r = (12 + 62 * K.out2(v)) * k
                K.ring(p, g.sx, g.gs, r, c.light if j == 0 else c.dark, max(1, int(5 * (1 - v))), 0.22)
        for sgn in (-1, 1):
            K.blob(p, g.sx + sgn * (10 + 26 * K.out2(u)), g.gs - 3, (8 - 5 * u) * k, c.light, sgn + 3, n=7, jag=0.2,
                   outline=c.dark)
    sh.act(150, 300, shock, z=-3)

    def cracks(p, u, ms):                                   # 금이 달려간다 - 속에서 빛이 샌다
        run = K.out2(min(1.0, ms / float(A - 60)))
        n = max(2, min(npts, int(round(npts * run))))
        pts = list(crack[:n * 2])
        if ms > A - 60:
            pts = [v + K.snoise(seed + i + int(ms / 40)) * 1.2 for i, v in enumerate(pts)]
        thin = 1.0 if ms < B + 100 else max(0.2, 1.0 - (ms - B - 100) / 200.0)
        p.line(pts, c.deep, 8 * thin, cap="butt")
        p.line(pts, c.alt, 4 * thin, cap="butt")
        p.line(pts, c.hot, max(1, 1.5 * thin), cap="butt")
    sh.act(150, B + 150, cracks, z=-2)

    def upheave(p, u, ms):
        for q, (ox, h, w) in enumerate(slabs):
            a = ms - q * 55
            if a < 0:
                continue
            up = K.back(min(1.0, a / 150.0)) if ms < B - 170 else max(0.0, (B - ms) / 170.0)
            hh = h * k * up
            x = gx + ox * k
            if hh > 1:
                tip = x + ox * 0.12 + g.face * 3
                p.poly([x - w * k, gy + 3, tip, gy - hh, x + w * k, gy + 3], c.dark, c.deep, 1)
                p.poly([tip, gy - hh, x + w * k, gy + 3, x + w * 0.15 * k, gy + 3], c.light)
                p.line([x - w * 0.4 * k, gy + 1, tip, gy - hh], c.base, 1)
            if a < 220:                                     # 솟는 자리의 흙먼지
                f = a / 220.0
                for sgn in (-1, 1):
                    K.blob(p, x + sgn * (w + 8 * f) * k, gy + 2 - 4 * f, (6 - 4 * f) * k, c.light, q * 2 + sgn, n=7,
                           jag=0.2, outline=c.base)
        m.draw(p, ms + A, paint)
    sh.act(A, B, upheave)
    K.shake(fx, 150, B + 150, amp=2.2)
    K.shake(fx, 170, B - 100, amp=1.4, key=fx.keys[0])
    K.impact(fx, A + 260, size=1.25)


# ---------------------------------------------------------------- 기운의 충격 (무색의 특수기 · 모르는 갈래)
def nova(fx):
    """기운을 모았다가 충격파로 쏘아 보낸다: 고리가 겹겹이 길을 따라 달려가고, 별빛이 따라간다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    mx, my = g.mouth(16)
    cols = c.tri
    C, T = 200, 300
    charge(fx, 0, C, mx, my, size=0.85)
    muzzle(fx, C, mx, my)
    K.recoil(fx, C, 0.6)
    m = K.Motes(random.randrange(1000))
    trail(m, g, C, C + T, 9, lambda u: (mx + (g.tx - mx) * u, my + (g.ty - my) * u), spread=8, drift=14)
    paint = K.mote(fx.type)

    def wave(p, u, ms):
        for j in range(3):
            v = u * 1.25 - j * 0.14
            if not 0.0 < v < 1.0:
                continue
            x, y = mx + (g.tx - mx) * K.in2(v) * 1.02, my + (g.ty - my) * K.in2(v) * 1.02
            r = (9 + 12 * v - j * 2) * k
            K.hoop(p, x, y, r * 0.42, r * 1.25, g.ang, cols[0], 5)
            K.hoop(p, x, y, r * 0.42, r * 1.25, g.ang, cols[1] if j else cols[2], 2)
        v = K.in2(min(1.0, u * 1.25))
        x, y = mx + (g.tx - mx) * v, my + (g.ty - my) * v
        K.comet(p, x - g.ux * 30 * k, y - g.uy * 30 * k, x, y, 7 * k, cols[0])
        K.comet(p, x - g.ux * 20 * k, y - g.uy * 20 * k, x, y, 4.5 * k, cols[1])
        K.glint(p, x, y, 13 * k, WHITE, rot=ms * 0.01)
        m.draw(p, ms + C, paint)
    sh.act(C, T, wave)
    K.impact(fx, C + T - 60, size=1.1)


# ---------------------------------------------------------------- 흘러가는 것 · 날아가는 것 (함께 쓰는 틀)
def stream(fx, at, dur, life, n, one, cone=14.0, m=None, wob=5.0, over=1.06, z=0):
    """입에서 과녁까지 줄지어 흘러가는 것들. one(p, x, y, v, j, ms) - v 는 그 조각이 간 만큼 0..1."""
    g = fx.geo
    mx, my = m or g.mouth(14)
    seeds = [(random.uniform(-1, 1), random.uniform(0, TAU), random.uniform(0.86, 1.08)) for _ in range(n)]
    gap = max(0.0, dur - life) / float(max(1, n - 1))

    def draw(p, u, ms):
        for j in range(n):
            a = ms - j * gap
            if a < 0 or a >= life:
                continue
            v = a / float(life)
            s, ph, sp = seeds[j]
            d = min(over, v * sp * over)
            off = s * cone * v + sin(v * 7 + ph) * wob * v
            one(p, mx + (g.tx - mx) * d + g.px * off, my + (g.ty - my) * d + g.py * off, v, j, ms)
    return fx.show.act(at, dur, draw, z=z)


def volley(fx, at, n, one, gap=90, life=190, spread=8.0, arc=0.0, m=None, hit=0.7, ease=K.in2, every=1, land=None):
    """n 발을 연달아 날린다. one(p, x, y, 각, j, v, ms). 꽂힐 때마다 작은 타격. 마지막이 닿는 시각을 돌려준다."""
    sh, g = fx.show, fx.geo
    mx, my = (g.sx, g.sy) if (m is None or isinstance(m, list)) else m
    ends = []
    for j in range(n):
        off = ((j % 2) * 2 - 1) * spread * (0.4 + 0.6 * ((j * 7) % 5) / 4.0) if n > 1 else 0.0
        lx = g.tx + ((j * 5) % 7 - 3) * 2.2 if n > 1 else g.tx
        ly = g.ty + ((j * 3) % 5 - 2) * 2.6 if n > 1 else g.ty
        x0, y0 = m[j] if isinstance(m, list) else (mx, my)

        def draw(p, u, ms, j=j, off=off, lx=lx, ly=ly, x0=x0, y0=y0):
            v = ease(u)
            x = x0 + (lx - x0) * v + g.px * off * K.hump(u)
            y = y0 + (ly - y0) * v + g.py * off * K.hump(u) - arc * K.hump(u)
            v2 = ease(min(1.0, u + 0.04))
            ang = math.atan2((y0 + (ly - y0) * v2 - arc * K.hump(min(1.0, u + 0.04))) - y + g.py * off * 0.0,
                             (x0 + (lx - x0) * v2) - x) if u < 0.96 else g.ang
            one(p, x, y, ang, j, u, ms)
        t0 = at + j * gap
        sh.act(t0, life, draw)
        if hit and j % every == 0:
            (land or K.mini)(fx, t0 + life - 20, lx, ly, hit)
        ends.append(t0 + life)
    return max(ends)


def rain(fx, at, n, one, gap=70, life=190, spread=30.0, lean=44.0, hit=0.7, every=1, typ=None):
    """하늘에서 과녁으로 쏟아진다. one(p, x, y, 각, j, v, ms)."""
    sh, g = fx.show, fx.geo
    top = g.top
    # 맞는 쪽이 화면 위쪽에 서 있으면 떨어질 높이가 없다 - 그만큼 멀리서 비스듬히 날아오게 한다
    lean = lean + max(0.0, 130.0 - (g.ty - top)) * 1.1
    ends = []
    for j in range(n):
        ox = random.uniform(-spread, spread)
        oy = random.uniform(-4, 16)
        x1, y1 = g.tx + ox - g.face * lean, top
        x2, y2 = g.tx + ox * 0.6, g.ty + oy
        ang = math.atan2(y2 - y1, x2 - x1)

        def draw(p, u, ms, j=j, x1=x1, y1=y1, x2=x2, y2=y2, ang=ang):
            v = K.in2(u) * 0.6 + u * 0.4
            one(p, x1 + (x2 - x1) * v, y1 + (y2 - y1) * v, ang, j, u, ms)
        t0 = at + j * gap
        sh.act(t0, life, draw)
        if hit and j % every == 0:
            K.mini(fx, t0 + life - 20, x2, y2, hit, typ=typ)
        ends.append(t0 + life)
    return max(ends)


def tail(p, x, y, ang, ln, w, cols):
    """날아가는 것 뒤에 끌리는 세 겹 꼬리."""
    bx, by = x - cos(ang) * ln, y - sin(ang) * ln
    if getattr(p, "raster", False):                         # 그림 바탕: 겉 꼬리는 빛으로 번진다
        p.glow_line([bx, by, x, y], cols[0], w * 2.4, 1.0)
    else:
        K.comet(p, bx, by, x, y, w, cols[0])
    K.comet(p, x - cos(ang) * ln * 0.66, y - sin(ang) * ln * 0.66, x, y, w * 0.62, cols[1])
    if cols[2]:
        K.comet(p, x - cos(ang) * ln * 0.36, y - sin(ang) * ln * 0.36, x, y, w * 0.3, cols[2])


# ---------------------------------------------------------------- 불
def _fire_cols(fx):
    c = fx.c
    if fx.type == "GHOST":
        return (c.deep, c.dark, c.base, c.alt)
    if fx.type == "DARK":
        return (c.deep, c.dark, c.base, c.alt)
    if fx.type == "DRAGON":
        return (c.deep, c.dark, c.base, c.hot)
    return (c.dark, c.base, c.light, c.hot)


def flame(fx):
    """불길을 뿜는다: 굵어지며 뻗는 불기둥 둘레로 불덩이가 이글거리며 흘러가고, 닿은 쪽은 불길에 휩싸인다.

    용 · 고스트 · 악의 '뿜는' 기술도 이 모양이다 (색은 그 타입 것 - 용의숨결은 남빛 불, 고스트는 보랏빛 불).
    """
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    rim, body, lite, hot = _fire_cols(fx)
    pw = power_of(fx)
    F = 420 if pw < 70 else 520 if pw < 100 else 620
    life = 240
    mx, my = g.mouth(14)
    seed = random.randrange(1000)
    N = 8
    K.recoil(fx, 60, 0.6)
    K.shake(fx, life, F - life + 60, amp=1.8)

    def gather(p, u, ms):
        r = 10 * K.out2(u) * k
        K.flare(p, mx, my, r * 2.0, 7, rim, inner=0.55, rot=ms * 0.02)
        K.orb(p, mx, my, r, (rim, lite, hot), shine=False)
    sh.act(0, 110, gather)

    def core(p, u, ms):                                     # 불기둥 (속이 꽉 찬 줄기)
        reach = K.out2(ms / float(life)) * 1.02
        thin = 1.0 if ms < F - 130 else max(0.0, (F - ms) / 130.0)
        if thin <= 0.05:
            return
        pts = g.path(0.0, reach, N, off=lambda u_: sin(u_ * 8 - ms * 0.02) * 2.5 * u_, m=(mx, my))
        ws = [(2.5 + 9.5 * (i / float(N)) ** 0.8) * k * thin * (1 + 0.18 * sin(i * 1.7 - ms * 0.03)) for i in range(N + 1)]
        K.ribbon(p, pts, [w * 1.5 for w in ws], rim)
        K.ribbon(p, pts, ws, body)
        K.ribbon(p, pts, [w * 0.55 for w in ws], lite)
        K.ribbon(p, pts, [w * 0.22 for w in ws], hot)
        K.orb(p, mx, my, (6 + 1.5 * sin(ms * 0.05)) * k * thin + 1, (rim, lite, hot), shine=False)
    sh.act(60, F, core)

    def puff(p, x, y, v, j, ms):                            # 줄기를 감싸고 흘러가는 불덩이
        r = (4.5 + 8.0 * v) * k
        wob = ms * 0.02 + j
        K.blob(p, x, y, r, rim if v > 0.75 else body, seed + j, wob, n=8, jag=0.3)
        if v < 0.8:
            K.blob(p, x, y + r * 0.1, r * 0.58, lite if v < 0.5 else body, seed + j + 9, wob, n=7, jag=0.3)
        if j % 3 == 0 and v > 0.25:
            K.tongue(p, x, y - r * 0.7, r * 0.75, K.snoise(seed + j + int(ms / 50)) * 4, lite, rim)
    stream(fx, 60, F, life, 10 if pw < 70 else 14, puff, cone=11.0, m=(mx, my), wob=4.0)

    m = K.Motes(seed)
    for j in range(8):
        m.add(life + j * (F - life) / 8.0, 300, g.tx + random.uniform(-22, 22) * k, g.ty + random.uniform(-6, 10),
              random.uniform(-6, 6), -random.uniform(26, 44), 0, random.uniform(3, 5.5), random.uniform(0, TAU))

    def engulf(p, u, ms):                                   # 불길에 휩싸인다
        f = K.fade(u, 0.15, 0.75)
        for j in range(5):
            r = (12 + 6 * sin(ms * 0.03 + j * 2.1)) * k * f * (1.25 - abs(j - 2) * 0.16)
            if r > 2:
                K.flame(p, g.tx + (j - 2) * 11 * k, g.ty + 18 * k - r * 0.4, r, K.snoise(seed + j + int(ms / 50)) * 5,
                        (rim, body if j % 2 else lite, hot))
        m.draw(p, ms + life + 60, lambda p_, x, y, s, rot, kk, n_: K.glint(p_, x, y, s * (0.6 + kk), hot if kk > 0.5 else lite))
    sh.act(life + 40, F - life + 80, engulf, z=2)
    K.impact(fx, F - 20, size=1.2)


def ember(fx):
    """불꽃세례: 작은 불덩이 셋이 포물선으로 날아가 톡톡 터진다."""
    c = fx.c
    cols = (c.dark, c.light, c.hot)

    def one(p, x, y, ang, j, v, ms):
        tail(p, x, y, ang, 22, 5.5, cols)
        K.flame(p, x, y + 2, 8, K.snoise(j + int(ms / 40)) * 3, cols)
    end = volley(fx, 0, 3, one, gap=110, life=220, arc=22, spread=6, hit=0.75, m=fx.geo.mouth(12))
    K.impact(fx, end - 40, size=1.0)


def daimonji(fx):
    """불대문자: 불덩이가 날아가 터지며 큰 대(大) 자로 타오른다. 획마다 불꽃이 핥아 오르고 불티가 날린다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    cols = (c.dark, c.base, c.light, c.hot)
    s = 31 * k
    cx, cy = g.tx, g.ty - 2
    hub = (0.0, -0.3)
    # 大: 긴 가로획 · 짧은 윗획 · 벌어지는 두 다리 (다리는 바깥으로 휜다 - 다섯 획이 같으면 별로 보인다)
    arms = [(-1.3, -0.3), (1.3, -0.3), (0.0, -1.0), (-1.0, 1.08), (1.0, 1.08)]
    A, B = 230, 560
    seed = random.randrange(1000)
    mx, my = g.mouth(14)
    charge(fx, 0, 120, mx, my, 0.7)

    def ball(p, u, ms):
        v = K.in2(u)
        x, y = mx + (g.tx - mx) * v, my + (g.ty - my) * v
        tail(p, x, y, g.ang, 34 * k, 8 * k, (cols[0], cols[2], cols[3]))
        K.flame(p, x, y + 3, 11 * k, K.snoise(int(ms / 40)) * 4, (cols[0], cols[2], cols[3]))
    sh.act(100, A - 100, ball)
    K.mini(fx, A - 10, cx, cy, 1.2)
    m = K.Motes(seed)
    for j in range(12):
        ax, ay = arms[j % 5]
        u_ = random.uniform(0.3, 1.0)
        m.add(60 + j * 34, 280, cx + (hub[0] + (ax - hub[0]) * u_) * s, cy + (hub[1] + (ay - hub[1]) * u_) * s,
              random.uniform(-5, 5), -random.uniform(18, 34), 0, random.uniform(4, 7), random.uniform(0, TAU))

    def kanji(p, u, ms):
        f = K.back(min(1.0, ms / 130.0), 1.2)
        thin = 1.0 if ms < B - 150 else max(0.0, (B - ms) / 150.0)
        if thin <= 0.03:
            return
        flick = 1.0 + 0.12 * sin(ms * 0.06)
        for wd, col in ((8.5, cols[0]), (6.0, cols[1]), (3.6, cols[2]), (1.4, cols[3])):     # 겉 - 속 - 심
            for n_, (ax, ay) in enumerate(arms):
                x1, y1 = cx + hub[0] * s, cy + hub[1] * s
                x2, y2 = cx + (hub[0] + (ax - hub[0]) * f) * s, cy + (hub[1] + (ay - hub[1]) * f) * s
                wx = K.snoise(seed + n_ + int(ms / 50)) * 2.0
                bow = (ax * 0.22 * s) if n_ >= 3 else 0.0   # 다리는 바깥으로 휜다
                wk = wd * k * thin * flick * (0.82 if n_ < 3 else 1.0)
                line = [x1, y1, (x1 + x2) / 2 + wx - bow * 0.2, (y1 + y2) / 2 - wx - abs(bow) * 0.5, x2, y2]
                if col == cols[0] and getattr(p, "raster", False):
                    p.glow_line(line, cols[1], wk * 2.6, 1.0)           # (그림 바탕) 겉불은 열기로 번진다
                    continue
                K.ribbon(p, line, [wk, wk * 0.95, wk * 0.5], col)
        m.draw(p, ms, lambda p_, x, y, sz, rot, kk, n_: K.flame(p_, x, y, sz * (0.5 + kk), sin(rot) * 3,
                                                                 (cols[0], cols[2], cols[3])))
    sh.act(A, B, kanji)
    K.shake(fx, A, B - 100, amp=2.0)
    K.impact(fx, A + B - 190, size=1.35)


# ---------------------------------------------------------------- 물
def jet(fx):
    """물줄기: 굵은 물기둥이 꿈틀대며 뻗어 가 꽂히고, 맞은 자리에서 물왕관이 솟는다. 센 기술일수록 굵고 나선이 감긴다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    pw = power_of(fx)
    W = 3.2 if pw < 60 else 5.0 if pw < 100 else 7.5
    F = 360 if pw < 60 else 480 if pw < 100 else 580
    mx, my = g.mouth(14)
    ln = math.hypot(g.tx - mx, g.ty - my) or 1.0
    seed = random.randrange(1000)
    N = 10
    charge(fx, 0, 130, mx, my, 0.6)
    K.recoil(fx, 110, 0.5 if pw < 100 else 1.0)
    K.shake(fx, 200, F - 110, amp=1.6 if pw < 100 else 2.4)
    m = K.Motes(seed)
    for j in range(12):
        t0 = 190 + j * (F - 200) / 12.0
        a = random.uniform(-2.8, -0.35)
        d = random.uniform(16, 34) * k
        m.add(t0, 330, g.tx, g.ty, cos(a) * d, sin(a) * d, 560, random.uniform(3, 5), a)
    trail(m, g, 110, F, 6, lambda u: (mx + (g.tx - mx) * u, my + (g.ty - my) * u), spread=3, drift=12, g_=420)
    paint = K.mote("WATER")

    def water(p, u, ms):
        reach = K.out2(ms / 110.0)
        thin = 1.0 if ms < F - 120 else max(0.0, (F - ms) / 120.0)
        t0 = 0.0 if ms < F - 120 else 1.0 - thin                # 끝날 때는 꼬리부터 걷힌다
        if thin <= 0.03:
            return
        w = W * k * (0.5 + 0.5 * thin) * (1 + 0.1 * sin(ms * 0.06))
        pts = g.path(t0, reach, N, off=lambda u_: sin(u_ * ln * 0.06 - ms * 0.035) * 3.2 * min(1.0, u_ * 4),
                     m=(mx, my))
        ws = [w * (0.6 if i == 0 else 1.0) * (1 + 0.15 * sin(i * 1.9 - ms * 0.04)) for i in range(N + 1)]
        if getattr(p, "raster", False):
            p.glow_line(pts, c.base, w * 4.6, 1.0)
        else:
            K.ribbon(p, pts, [v * 1.75 for v in ws], c.dark)
        K.ribbon(p, pts, [v * 1.2 for v in ws], c.base)
        K.ribbon(p, pts, [v * 0.62 for v in ws], c.light)
        K.ribbon(p, pts, [v * 0.22 for v in ws], WHITE)
        if pw >= 100:                                       # 센 물기둥에는 나선이 감긴다
            for j, col in enumerate((c.alt, WHITE)):
                q = g.path(t0, reach, 14, off=lambda u_, o=j: sin(u_ * ln * 0.1 - ms * 0.04 + o * math.pi) * (w * 2.0 + 2),
                           m=(mx, my))
                p.line(q, col, 2, smooth=True)
        if reach > 0.95:                                    # 맞은 자리 - 물왕관
            cr = (15 + W * 2 + 4 * (int(ms / 45) % 2)) * k * (0.5 + 0.5 * thin)
            pts = []
            for q in range(13):
                a = math.pi + math.pi * q / 12.0
                rq = cr * (1.0 if q % 2 else 0.55)
                pts += [g.tx + cos(a) * rq * 1.15, g.ty + 6 + sin(a) * rq * 1.25]
            p.poly(pts, c.base, c.dark, 1)
            p.oval(g.tx, g.ty + 6, cr * 1.2, cr * 0.3, c.light, c.dark, 1)
            K.disc(p, g.tx, g.ty, cr * 0.5, WHITE)
        m.draw(p, ms + 110, paint)
    sh.act(110, F, water)
    K.impact(fx, 110 + F - 100, size=1.15 if pw < 100 else 1.3)


def bubble(fx):
    """거품이 흔들리며 떠 가서 톡톡 터진다."""
    c = fx.c
    life = 330

    def one(p, x, y, v, j, ms):
        r = (4 + (j * 7) % 5) * (0.6 + 0.4 * K.out2(v * 3))
        if v > 0.9:                                         # 터진다
            K.flare(p, x, y, r + 7, 6, WHITE, inner=0.5, outline=c.light)
            return
        p.oval(x, y, r, r, c.base, c.dark, 1)
        p.oval(x, y, r * 0.72, r * 0.72, c.light)
        p.oval(x - r * 0.3, y - r * 0.32, r * 0.26, r * 0.2, WHITE)
    end = stream(fx, 0, 620, life, 12, one, cone=16, wob=8, over=1.0)
    K.shake(fx, life, 620 - life, amp=1.2)
    K.impact(fx, end - 60, size=0.95)


def surf(fx):
    """파도타기: 뒤에서 큰 파도가 일어나 말려 올라가며 덮친다. 물마루에 거품이 일고 물보라가 날린다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    if "muddy" in K.key_of(fx.move):
        c = K.tone("GROUND")
    f = g.face
    T = 560
    seed = random.randrange(1000)
    m = K.Motes(seed)

    def wave(p, u, ms):
        v = K.inout(u)
        x, y = g.at(-0.12 + 1.14 * v)
        y += 26
        grow = K.out2(min(1.0, ms / 180.0)) * (1.0 if u < 0.86 else max(0.2, (1 - u) / 0.14))
        hh, ww = 60 * k * grow, 66 * k

        def shape(sc, back, lift=0.0):
            h, w = hh * sc, ww * sc
            bx = x - f * back
            return [bx - f * w * 1.1, y, bx - f * w * 0.5, y - h * 0.52 - lift, bx + f * w * 0.05, y - h * 1.06 - lift,
                    bx + f * w * 0.66, y - h * 0.84 - lift, bx + f * w * 0.36, y - h * 0.38, bx + f * w * 0.56, y]
        p.poly(shape(1.12, 14), c.deep, "", 1, True)
        p.poly(shape(1.0, 0), c.dark, "", 1, True)
        p.poly(shape(0.8, 8), c.base, "", 1, True)
        p.poly(shape(0.52, 16), c.light, "", 1, True)
        for j in range(5):                                  # 물마루의 거품
            px = x + f * ww * (0.0 + j * 0.13)
            py = y - hh * (0.98 - j * 0.07) + 2 * sin(ms * 0.02 + j)
            K.blob(p, px, py, (7.5 - j) * grow + 1, WHITE, seed + j, ms * 0.01, n=7, jag=0.2)
        if grow > 0.5:
            for j in range(4):                              # 앞으로 날리는 물보라
                ph = (ms * 0.004 + j * 0.25) % 1.0
                K.drop(p, x + f * (ww * 0.5 + 26 * ph), y - hh * (0.8 - 0.5 * ph) - 8 * K.hump(ph), 3.5 * (1 - ph) + 1,
                       math.pi if f > 0 else 0.0, c.light, c.dark)
    sh.act(0, T, wave)
    K.shake(fx, T - 200, 300, amp=2.4)
    K.impact(fx, T - 150, size=1.4, typ="WATER")


# ---------------------------------------------------------------- 전기
def zap(fx):
    """전격: 지그재그 전기가 깜빡이며 이어진다. 방전 · 라이징볼트는 먼저 사방으로 튄다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    cols = (c.dark, c.base, c.hot)
    radial = any(w in K.key_of(fx.move) for w in ("discharge", "voltage", "electroweb"))
    mx, my = g.mouth(10)
    A = 200 if radial else 110
    F = 380
    seed = random.randrange(1000)

    def gather(p, u, ms):
        rnd = random.Random(seed + int(ms / 45))
        n = 7 if radial else 4
        for q in range(n):
            a = TAU * q / n + rnd.uniform(-0.3, 0.3)
            r = (20 + (50 if radial else 16) * u) * k
            K.bolt(p, K.zigzag(g.sx, g.sy, g.sx + cos(a) * r, g.sy + sin(a) * r * 0.85, 6, 4, rnd), 1, cols)
        K.orb(p, mx, my, (4 + 5 * u) * k, cols, shine=False)
    sh.act(0, A, gather)
    K.recoil(fx, A, 0.5)
    K.shake(fx, A + 30, F - 30, amp=2.2)

    def arc(p, u, ms):
        if int(ms / 45) % 4 == 3 and ms < F - 60:           # 한 박자씩 끊긴다
            return
        rnd = random.Random(seed + 3 + int(ms / 45))
        thin = 1.0 if ms < F - 90 else max(0.3, (F - ms) / 90.0)
        main = K.zigzag(mx, my, g.tx, g.ty, 12, 8, rnd)
        K.bolt(p, main, max(1, int(round(4 * k * thin))), cols)
        p.line(K.zigzag(mx, my, g.tx, g.ty, 18, 7, rnd), c.alt, 1, cap="butt")
        for q in (2, 5):                                    # 가지
            bx, by = main[q * 2], main[q * 2 + 1]
            a = g.ang + rnd.choice((-1, 1)) * rnd.uniform(0.6, 1.2)
            ln_ = rnd.uniform(18, 32) * k
            K.bolt(p, K.zigzag(bx, by, bx + cos(a) * ln_, by + sin(a) * ln_, 5, 3, rnd), 1, cols)
        K.flare(p, mx, my, (13 + 3 * (int(ms / 45) % 2)) * k, 6, c.base, inner=0.4, rot=ms * 0.02)
        K.orb(p, mx, my, 7 * k, cols, shine=False)
        for _q in range(4):                                 # 맞는 곳에서 튄다
            a = rnd.uniform(0, TAU)
            r = rnd.uniform(18, 36) * k
            p.line(K.zigzag(g.tx, g.ty, g.tx + cos(a) * r, g.ty + sin(a) * r, 5, 3, rnd), c.base, 2, cap="butt")
        r = (7 + 3 * (int(ms / 45) % 3)) * k
        p.oval(g.tx, g.ty, r, r, WHITE, c.base, 2)
    sh.act(A, F, arc)
    K.impact(fx, A + F - 110, size=1.1)


# ---------------------------------------------------------------- 풀
def leafstorm(fx):
    """잎보라: 잎이 나선으로 휘몰아쳐 날아가 꽂힌다. 꽃 기술은 분홍 꽃잎, 매지컬리프는 반짝임이 따른다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    key = K.key_of(fx.move)
    petal = any(w in key for w in ("petal", "flower", "bloom"))
    magical = "magical" in key or fx.type == "FAIRY"
    light, dark, vein = (("#ffd6ea", "#f07aa8", "#b84a7a") if petal else (c.light, c.base, c.deep))
    pw = power_of(fx)
    n = 7 if pw < 70 else 10 if pw < 120 else 13
    gap, life = 46, 300
    seeds = [(random.uniform(10, 24) * (1 if j % 2 else -1), random.uniform(0, TAU)) for j in range(n)]
    total = (n - 1) * gap + life

    def wind(p, u, ms):                                     # 감아 도는 바람 두 가닥
        t1 = K.out2(min(1.0, ms / 200.0))
        t0 = K.clamp((ms - total + 220) / 220.0)
        if t1 - t0 < 0.05:
            return
        for j in range(2):
            q = g.path(t0, t1, 12, off=lambda u_, o=j: sin(u_ * 9 - ms * 0.02 + o * math.pi) * 14 * k * K.hump(u_))
            p.line(q, c.dark if j else c.light, 2, smooth=True)
    sh.act(0, total, wind, z=-1)

    def leaves(p, u, ms):
        for j in range(n):
            a = ms - j * gap
            if a < 0 or a >= life:
                continue
            v = a / float(life)
            amp, ph = seeds[j]
            d = K.in2(v) * 0.5 + v * 0.5
            off = amp * sin(v * TAU * 1.25 + ph) * K.hump(v) * k
            x, y = g.at(d, off)
            rot = v * 14 + ph
            if petal:
                K.petal(p, x, y, 8 * k, rot, light, dark)
            else:
                K.leaf(p, x, y, 9 * k, rot, light if j % 2 else dark, vein)
            if magical and (j + int(ms / 60)) % 2:
                K.glint(p, x - g.ux * 12, y - g.uy * 12, 6, WHITE)
    sh.act(0, total, leaves)
    for j in range(0, n, 3):
        K.mini(fx, j * gap + life - 20, g.tx + random.uniform(-8, 8), g.ty + random.uniform(-8, 8), 0.6)
    K.shake(fx, life, total - life + 40, amp=1.5)
    K.impact(fx, total - 60, size=1.1 if pw < 120 else 1.3)


# ---------------------------------------------------------------- 얼음
def blizzard(fx):
    """눈보라: 흰 바람이 굽이쳐 몰아치고 눈과 얼음 조각이 쓸려 간다. 맞는 쪽에는 눈 결정이 피고 얼음이 돋는다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    pw = power_of(fx)
    F = 520 if pw < 100 else 660
    life = 260
    seed = random.randrange(1000)

    def wind(p, u, ms):
        thin = K.fade(u, 0.12, 0.8)
        for j, off in enumerate((-24, -8, 8, 24)):
            u0 = (ms * 0.0026 + j * 0.27) % 1.25 - 0.15
            q = g.path(max(0.0, u0), min(1.05, u0 + 0.42), 6, off=lambda u_, o=off, jj=j: o * (0.4 + 0.6 * u_) * k
                       + 6 * sin(u_ * 7 + jj + ms * 0.01))
            K.ribbon(p, q, K.widths(6, (3.4 if j in (1, 2) else 2.4) * thin + 0.3, "spindle"),
                     WHITE if j in (1, 2) else c.light)
    sh.act(0, F, wind, z=-1)

    def flake(p, x, y, v, j, ms):
        if j % 3 == 0:
            K.shard(p, x, y, (5 + 2 * (j % 2)) * k, v * 9 + j, WHITE, c.dark)
        else:
            r = 1.6 + (j % 3)
            p.oval(x, y, r, r, WHITE if j % 2 else c.light)
    stream(fx, 0, F, life, 22 if pw < 100 else 30, flake, cone=30, wob=7, over=1.12)

    def freeze(p, u, ms):                                   # 맞는 쪽이 얼어붙는다
        gr = K.out2(min(1.0, ms / 260.0)) * (1.0 if u < 0.85 else (1 - u) / 0.15)
        for j in range(8):                                  # 돋아나는 얼음
            a = j * math.pi / 4 + 0.2
            K.spike(p, g.tx + cos(a) * 22 * k, g.ty + sin(a) * 17 * k, 4.2 * k, (8 + 12 * K.noise(seed + j)) * k * gr, a,
                    c.light if j % 2 else WHITE, c.dark)
        ln = 24 * k * gr                                    # 눈 결정
        for j in range(6):
            a = j * math.pi / 3 + 0.26 + ms * 0.001
            ca, sa = cos(a), sin(a)
            p.line([g.tx, g.ty, g.tx + ca * ln, g.ty + sa * ln], WHITE, 2, cap="butt")
            bx, by = g.tx + ca * ln * 0.62, g.ty + sa * ln * 0.62
            for sg in (-1, 1):
                p.line([bx, by, bx + cos(a + sg * 0.9) * ln * 0.34, by + sin(a + sg * 0.9) * ln * 0.34], c.light, 2,
                       cap="butt")
    sh.act(life - 30, F - life + 120, freeze, z=2)
    K.shake(fx, life, F - life, amp=1.8)
    K.impact(fx, F - 40, size=1.2 if pw < 100 else 1.35)


def icicles(fx):
    """고드름떨구기: 굵은 고드름이 줄줄이 내리꽂힌다."""
    c = fx.c

    def one(p, x, y, ang, j, v, ms):
        K.streak(p, x - cos(ang) * 34, y - sin(ang) * 34, x, y, 2.0, c.light)
        K.shard(p, x, y, 13 * fx.big, ang, c.light, c.dark, slim=0.36)
        K.shard(p, x, y, 6 * fx.big, ang, WHITE, slim=0.3)
    end = rain(fx, 0, 6, one, gap=75, lean=10)
    K.shake(fx, 180, end - 180, amp=2.0, vertical=True)
    K.impact(fx, end - 40, size=1.2)


def ice(fx):
    """얼음 조각이 날아가 박힌다 (눈사태 · 아이스볼 · 얼음숨결 ... 이름에 얼음이 든 나머지)."""
    c = fx.c
    k = max(1.0, fx.big)

    def one(p, x, y, ang, j, v, ms):
        K.streak(p, x - cos(ang) * 26, y - sin(ang) * 26, x, y, 2.4, c.light)
        K.shard(p, x, y, 10 * k, ang, c.light, c.dark)
        K.shard(p, x, y, 4.5 * k, ang, WHITE)
    end = volley(fx, 0, 5, one, gap=80, life=180, spread=12, m=fx.geo.mouth(12))

    def frost(p, u, ms):
        f = K.fade(u, 0.2, 0.7)
        for j in range(6):
            a = j * math.pi / 3 + 0.5
            K.spike(p, fx.geo.tx + cos(a) * 14, fx.geo.ty + sin(a) * 12, 4 * k, 18 * k * f, a, c.light, c.dark)
    fx.show.act(180, end - 100, frost, z=2)
    K.impact(fx, end - 40, size=1.15)


# ---------------------------------------------------------------- 독
def sludge(fx):
    """오물: 출렁이는 덩어리가 포물선으로 날아가 철퍽 퍼진다. 방울이 뚝뚝 떨어지고 독안개가 피어오른다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    A = 330
    seed = random.randrange(1000)
    mx, my = g.mouth(12)
    m = K.Motes(seed)

    def pos(u):
        return mx + (g.tx - mx) * u, my + (g.ty - my) * u - 36 * K.hump(u)
    trail(m, g, 0, A, 6, pos, spread=2, drift=3, g_=520, life=(260, 340), size=(3, 4.5))
    paint = K.mote("POISON")

    def gob(p, u, ms):
        x, y = pos(u)
        r = 15 * k * (1 + 0.08 * sin(ms * 0.05))
        K.blob(p, x, y, r * 1.18, c.deep, seed, ms * 0.03, n=9, jag=0.3)
        K.blob(p, x, y, r, c.dark, seed, ms * 0.03, n=9, jag=0.3, outline=c.alt, width=2)
        K.blob(p, x - r * 0.2, y - r * 0.22, r * 0.52, c.base, seed + 4, ms * 0.03, n=7, jag=0.25)
        p.oval(x + r * 0.3 * cos(ms * 0.02), y + r * 0.3 * sin(ms * 0.02), r * 0.2, r * 0.2, "", c.alt, 2)
        m.draw(p, ms, paint)
    sh.act(0, A, gob)

    def fumes(p, u, ms):
        for j in range(4):
            v = K.clamp(u * 1.4 - j * 0.12)
            if 0 < v < 1:
                K.blob(p, g.tx + (j - 1.5) * 13 * k, g.ty - (4 + 34 * v) * k, (10 - 6 * v) * k,
                       c.dark if j % 2 else c.base, seed + j, ms * 0.01, n=8, jag=0.22, outline=c.deep)
    sh.act(A + 60, 420, fumes, z=6)
    K.impact(fx, A - 20, size=1.15)


def needles(fx):
    """바늘: 가는 침이 빠르게 연달아 꽂힌다."""
    c = fx.c

    def one(p, x, y, ang, j, v, ms):
        K.streak(p, x - cos(ang) * 30, y - sin(ang) * 30, x, y, 1.8, c.light)
        K.shard(p, x, y, 7.5, ang, WHITE, c.dark, slim=0.26)
    end = volley(fx, 0, 5, one, gap=70, life=140, spread=9, hit=0.6, ease=lambda u: u, m=fx.geo.mouth(12))
    K.impact(fx, end - 40, size=0.95)


# ---------------------------------------------------------------- 에스퍼
def psy(fx):
    """염력: 이마가 번쩍이고 염파가 겹겹이 건너간다. 맞는 쪽은 **들려 올라가** 문양 속에서 조여지다가 내리꽂힌다.

    둘레에 육각 문양이 돌며 좁혀 들고, 공간이 일렁이고, 빛이 궤도를 돈다.
    """
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    violet = c.alt
    pw = power_of(fx)
    A = 200
    B = 560 if pw >= 90 else 420
    hx, hy = g.sx, g.sy - 18

    def cast(p, u, ms):
        K.flare(p, hx, hy, (9 + 9 * K.hump(u)) * k, 4, WHITE, inner=0.22, rot=ms * 0.01, outline=violet)
        for j in range(3):                                  # 건너가는 염파
            v = u * 1.5 - j * 0.2
            if 0.0 < v < 1.0:
                x, y = g.at(0.1 + 0.8 * v)
                r = (8 + 14 * v) * k
                K.hoop(p, x, y, r * 0.38, r * 1.3, g.ang, c.dark, 5)
                K.hoop(p, x, y, r * 0.38, r * 1.3, g.ang, violet if j % 2 else c.light, 2)
    sh.act(0, A + 120, cast)

    # 맞는 쪽이 들려 올라가 떨다가 떨어진다
    tgt = K.Mover(fx, None if (fx.miss or fx.immune) else fx.keys[1])

    def lift(p, u, ms):
        up = K.out2(min(1.0, ms / 160.0)) if ms < B - 70 else max(0.0, (B - ms) / 70.0)
        tgt.to((1.5 if int(ms / 40) % 2 else -1.5) * up, -9.0 * up)
    sh.act(A, B, lift, settle=tgt.home, z=-9)

    def warp(p, u, ms):
        f = ms / float(B)
        rr = (56 - 30 * K.in2(f)) * k
        yy = g.ty - 9 * min(1.0, ms / 160.0)
        K.sigil(p, g.tx, yy, rr, ms * 0.011, c.dark, 4)
        K.sigil(p, g.tx, yy, rr, ms * 0.011, violet, 2)
        for j in range(3):                                  # 일그러지는 공간
            y0 = yy - 16 * k + j * 16 * k
            pts = []
            for q in range(9):
                pts += [g.tx - 46 * k + q * 11.5 * k, y0 + 5 * sin(q * 1.3 + ms * 0.04 + j * 2)]
            p.line(pts, c.base, 2, smooth=True)
        for j in range(2):                                  # 조여드는 고리
            r2 = (52 - (ms * 0.16 + j * 24) % 48) * k
            K.ring(p, g.tx, yy, r2, c.light if j else violet, 3 if r2 < 30 * k else 2, 0.72)
        for j in range(3):                                  # 궤도를 도는 빛
            a = ms * 0.02 + j * 2.09
            K.glint(p, g.tx + cos(a) * rr * 0.92, yy + sin(a) * rr * 0.62, 7.5 * k, WHITE if j else c.light)
        if ms > B - 110:                                    # 한 점으로 찌그러진다
            K.orb(p, g.tx, yy, (B - ms) / 110.0 * 15 * k + 3, (c.dark, c.light, WHITE), shine=False)
    sh.act(A, B, warp)
    K.impact(fx, A + B - 30, size=1.25)


# ---------------------------------------------------------------- 파동 · 구슬
def pulse(fx):
    """파동: 심이 날아가며 뒤로 고리를 터뜨린다. 고리는 길을 감싸고 커지며 가늘어진다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    cols = c.tri
    mx, my = g.mouth(16)
    C, T = 180, 330
    charge(fx, 0, C, mx, my, 0.8)
    muzzle(fx, C, mx, my, 1.1)
    K.recoil(fx, C, 0.6)

    def fly(p, u, ms):
        v = K.in2(u) * 0.55 + u * 0.45
        x, y = mx + (g.tx - mx) * v, my + (g.ty - my) * v
        for j in range(5):                                  # 지나온 자리의 고리
            b = v - 0.13 * (j + 1) + ((ms * 0.0012) % 0.13)
            if b <= 0.02:
                continue
            rx, ry = mx + (g.tx - mx) * b, my + (g.ty - my) * b
            age = (v - b) / 0.75
            r = (7 + 26 * age) * k
            w = max(1, int(6 * (1 - age)))
            K.hoop(p, rx, ry, r * 0.4, r, g.ang, cols[0], w + 3)
            K.hoop(p, rx, ry, r * 0.4, r, g.ang, cols[1] if fx.type not in ("GHOST", "DARK") else c.alt, w)
        K.flare(p, x, y, 18 * k, 9, cols[0], inner=0.55, rot=ms * 0.02)
        K.orb(p, x, y, 10.5 * k, cols)
    sh.act(C, T, fly)
    K.impact(fx, C + T - 50, size=1.15)


def ball(fx):
    """구슬: 기운이 휘감겨 뭉치고, 가시 돋친 기운을 두른 채 혜성처럼 꼬리를 끌며 날아가 크게 터진다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    dark_ = fx.type in ("GHOST", "DARK")
    cols = c.tri
    mx, my = g.mouth(20)
    R = 13.5 * k
    C, T = 300, 290
    seed = random.randrange(1000)
    charge(fx, 0, C, mx, my, 1.0)
    muzzle(fx, C, mx, my, 1.2)
    K.recoil(fx, C, 0.9)
    m = K.Motes(seed)
    trail(m, g, C, C + T, 10, lambda u: (mx + (g.tx - mx) * K.in2(u), my + (g.ty - my) * K.in2(u)), spread=5,
          drift=12, life=(200, 320), size=(3, 5.5))
    paint = K.mote(fx.type)

    def fly(p, u, ms):
        v = K.in2(u)
        x, y = mx + (g.tx - mx) * v, my + (g.ty - my) * v
        gone = math.hypot(x - mx, y - my)
        tl = min(R * 4.6, gone + R * 0.5)
        if tl > R:
            tail(p, x, y, g.ang, tl, R * 0.98, cols)
        K.burst_star(p, x, y, R * 1.9, 9, cols[0], seed + int(ms / 50), inner=0.62, rot=ms * 0.02)
        if c.edge:
            K.disc(p, x, y, R * 1.16, c.edge)               # 어두운 구슬은 밝은 테가 있어야 보인다
        K.orb(p, x, y, R * (1 + 0.08 * sin(ms * 0.07)), (c.deep, c.dark, c.alt) if dark_ else cols)
        K.arcs(p, x, y, R * 1.6, cols[2] if dark_ else c.hot, 2, ms * 1.4, 2, 110)
        m.draw(p, ms + C, paint)
    sh.act(C, T, fly)
    K.impact(fx, C + T - 40, size=1.3)


# ---------------------------------------------------------------- 빛
def moon(fx):
    """문포스: 초승달이 떠오르고, 달빛이 모여 구슬이 되어 날아가 터진다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    pale, gold = "#fff6c8", "#ffe07a"
    mx, my = g.sx - g.face * 26, max(16.0, g.sy - 52)       # 쓰는 쪽 뒤 위
    R = 19 * k
    tilt = (math.pi if g.face > 0 else 0.0) - 0.45 * g.face
    A, B, T = 220, 300, 250
    seed = random.randrange(1000)

    def luna(p, u, ms):
        rise = K.back(min(1.0, ms / float(A)), 1.2)
        fade_ = 1.0 if ms < A + B else max(0.0, 1.0 - (ms - A - B) / 120.0)
        r = R * (0.4 + 0.6 * rise) * fade_
        y = my + 16 * (1 - rise)
        if r < 2:
            return
        K.arcs(p, mx, y, r + 12, gold, 2, ms * 0.25, 4, 50)        # 달무리
        K.crescent(p, mx, y, r + 2.5, tilt, 4.3, r * 0.84, c.base)
        K.crescent(p, mx, y, r, tilt, 4.3, r * 0.76, pale)
        for j in range(3):
            a = ms * 0.015 + j * 2.1
            K.glint(p, mx + cos(a) * (r + 10), y + sin(a) * (r + 8), 5 + 3 * ((int(ms / 60) + j) % 2),
                    WHITE if j % 2 else gold)
    sh.act(0, A + B + 120, luna)

    def gather(p, u, ms):
        for j in range(6):
            a = j * math.pi / 3 + ms * 0.012
            rr = 44 * (1 - K.in2(u))
            K.glint(p, mx + cos(a) * rr, my + sin(a) * rr, 6, pale)
        K.orb(p, mx, my, (3 + 9.5 * K.out2(u)) * k, (c.dark, c.light, WHITE))
    sh.act(A, B, gather)
    m = K.Motes(seed)
    trail(m, g, A + B, A + B + T, 8, lambda u: (mx + (g.tx - mx) * K.in2(u), my + (g.ty - my) * K.in2(u)), spread=5,
          drift=10)
    paint = K.mote("FAIRY")

    def fly(p, u, ms):
        v = K.in2(u)
        x, y = mx + (g.tx - mx) * v, my + (g.ty - my) * v
        ang = math.atan2(g.ty - my, g.tx - mx)
        tail(p, x, y, ang, min(52 * k, 6 + math.hypot(x - mx, y - my)), 10 * k, (c.dark, c.light, pale))
        K.orb(p, x, y, 12 * k, (c.dark, c.light, WHITE))
        K.glint(p, x, y, 20 * k, WHITE, rot=ms * 0.01)
        m.draw(p, ms + A + B, paint)
    sh.act(A + B, T, fly)
    K.impact(fx, A + B + T - 40, size=1.4)


def sparkle(fx):
    """반짝이는 바람 (요정의바람 · 은빛바람 · 얼어붙은바람 · 매지컬샤인): 빛가루가 굽이치는 바람을 타고 쏟아진다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    F, life = 520, 260

    def wind(p, u, ms):
        thin = K.fade(u, 0.15, 0.8)
        for j, off in enumerate((-16, 0, 16)):
            u0 = (ms * 0.0024 + j * 0.33) % 1.2 - 0.15
            q = g.path(max(0.0, u0), min(1.05, u0 + 0.45), 6, off=lambda u_, o=off, jj=j: o * k + 7 * sin(u_ * 9 + jj * 2
                                                                                                            - ms * 0.012))
            K.ribbon(p, q, K.widths(6, 2.6 * thin + 0.3), c.light if j != 1 else WHITE)
    sh.act(0, F, wind, z=-1)

    def spark(p, x, y, v, j, ms):
        r = (4 + 5 * abs(sin(ms * 0.02 + j))) * k
        if j % 4 == 0 and fx.type == "FAIRY":
            K.heart(p, x, y, r * 0.8, c.base, c.deep)
        elif j % 3 == 0:
            K.star(p, x, y, r, c.alt, "", v * 6 + j)
        else:
            K.glint(p, x, y, r * 1.2, WHITE if j % 2 else c.light)
    stream(fx, 0, F, life, 20, spark, cone=20, wob=7, over=1.08)
    K.shake(fx, life, F - life, amp=1.3)
    K.impact(fx, F - 50, size=1.1)


def flash(fx):
    """섬광: 몸에서 빛살이 돌며 뻗고, 별이 줄지어 날아가 맞는 쪽이 눈부시게 반짝인다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    sx, sy = fx.src

    def rays(p, u, ms):
        ln = (18 + 66 * K.out2(min(1.0, ms / 160.0))) * k
        thin = K.fade(u, 0.1, 0.65)
        w = 0.17 * thin
        for j in range(12):
            a = j * math.pi / 6 + ms * 0.0016
            far = ln * (1.0 if j % 2 else 0.62)
            p.poly([sx + cos(a - w) * 9, sy + sin(a - w) * 9, sx + cos(a) * far, sy + sin(a) * far,
                    sx + cos(a + w) * 9, sy + sin(a + w) * 9], WHITE if j % 2 else c.light)
        K.glint(p, sx, sy, (24 + 6 * (int(ms / 40) % 2)) * k * thin + 1, WHITE)
        K.ring(p, sx, sy, (10 + 60 * u) * k, c.alt, max(1, int(4 * (1 - u))), 0.9)
    sh.act(0, 420, rays)

    def one(p, x, y, ang, j, v, ms):
        K.streak(p, x - cos(ang) * 22, y - sin(ang) * 22, x, y, 2.4, c.light)
        K.star(p, x, y, 8.5 * k, c.alt if j % 2 else WHITE, c.dark, ms * 0.02 + j)
    end = volley(fx, 120, 5, one, gap=60, life=200, spread=14, hit=0.55)
    K.impact(fx, end - 50, size=1.2)


# ---------------------------------------------------------------- 돌 · 땅
def gem(fx):
    """파워젬 · 원시의힘: 돌이 발밑에서 떠올라 빛나다가 하나씩 쏘아져 나간다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    rocky = "ancient" in K.key_of(fx.move) or fx.type == "GROUND"
    n = 5
    A, H = 200, 110
    hover = [(g.sx + ox, g.sy - 34 + oy) for ox, oy in ((-30, 4), (-15, -7), (0, 5), (15, -5), (30, 2))]

    def stone(p, x, y, j, ang, sc=1.0):
        if rocky:
            K.chunk(p, x, y, 8.5 * k * sc, j, c.light, c.dark)
        else:
            K.shard(p, x, y, 8.5 * k * sc, ang, c.alt if j % 2 else c.light, c.dark, slim=0.5)
            K.shard(p, x, y, 3.6 * k * sc, ang, WHITE, slim=0.5)

    def rise(p, u, ms):
        for j, (hx_, hy_) in enumerate(hover):
            if ms < A:
                y0 = g.gs
                stone(p, hx_, y0 + (hy_ - y0) * K.back(min(1.0, ms / float(A)), 1.4), j, -math.pi / 2,
                      0.5 + 0.5 * ms / float(A))
            elif ms < A + H + j * 80:
                y = hy_ + 2 * sin(ms * 0.02 + j)
                stone(p, hx_, y, j, -math.pi / 2)
                if (int(ms / 70) + j) % 3 == 0:
                    K.glint(p, hx_ + 5, y - 6, 8, WHITE)
        K.ring(p, g.sx, g.gs, (14 + 30 * min(1.0, ms / float(A))) * k, c.light, max(1, int(3 * (1 - u))), 0.25)
    sh.act(0, A + H + n * 80, rise)

    def one(p, x, y, ang, j, v, ms):
        K.streak(p, x - cos(ang) * 28, y - sin(ang) * 28, x, y, 2.6, c.light)
        stone(p, x, y, j, ang)
    end = volley(fx, A + H, n, one, gap=80, life=170, spread=0, m=hover, hit=0.75)
    K.impact(fx, end - 40, size=1.2)


def _sky(fx, n, one, gap=70, life=190, spread=30.0, lean=44.0, hit=0.7, final=1.2, every=1, vertical=True,
         typ=None):
    end = rain(fx, 0, n, one, gap=gap, life=life, spread=spread, lean=lean, hit=hit, every=every, typ=typ)
    K.shake(fx, life - 20, end - life + 40, amp=2.0, vertical=vertical)
    K.impact(fx, end - 40, size=final)


def rockfall(fx):
    """스톤샤워: 바위가 쏟아져 내린다."""
    c = fx.c

    def one(p, x, y, ang, j, v, ms):
        K.streak(p, x - cos(ang) * 30, y - sin(ang) * 30, x, y, 2.4, c.light)
        K.chunk(p, x, y, (9 + j % 3 * 3) * fx.big, j, c.light, c.dark)
    _sky(fx, 6, one)


def arrows(fx):
    """사우전드애로: 화살이 비처럼 꽂힌다."""
    c = fx.c

    def one(p, x, y, ang, j, v, ms):
        ca, sa = cos(ang), sin(ang)
        p.line([x - ca * 24, y - sa * 24, x, y], c.light, 3, cap="butt")
        K.shard(p, x, y, 5.5, ang, WHITE, c.dark)
        K.streak(p, x - ca * 30 - sa * 3, y - sa * 30 + ca * 3, x - ca * 22, y - sa * 22, 2.4, c.alt)
    _sky(fx, 10, one, gap=45, life=150, spread=34, hit=0.55, every=2)


def meteor(fx):
    """용성군: 불타는 유성이 긴 꼬리를 끌며 떨어져 터진다."""
    c = fx.c
    k = fx.big

    def one(p, x, y, ang, j, v, ms):
        ca, sa = cos(ang), sin(ang)
        tail(p, x, y, ang, 58, 10 * k, (c.dark, "#ff8a3c", "#ffe27a"))
        K.streak(p, x - ca * 70 + sa * 6, y - sa * 70 - ca * 6, x - ca * 30, y - sa * 30, 1.6, c.light)
        K.burst_star(p, x, y, 13 * k, 7, c.dark, j + int(ms / 50), inner=0.6, rot=ms * 0.02)
        K.orb(p, x, y, 8.5 * k, ("#c8421a", "#ffd27a", WHITE), shine=False)
    _sky(fx, 5, one, gap=100, life=230, spread=28, hit=0.95, final=1.4, typ="FIRE")


def coins(fx):
    """골드러시: 금화가 뒤집히며 쏟아진다."""
    def one(p, x, y, ang, j, v, ms):
        rx = 1.5 + 5.0 * abs(cos(ms * 0.02 + j))
        p.oval(x, y, rx, 6.5, "#ffd447", "#a87400", 2)
        if rx > 4:
            p.oval(x, y, rx * 0.5, 3.5, "#fff3a8")
        if (int(ms / 60) + j) % 3 == 0:
            K.glint(p, x + 3, y - 4, 7, WHITE)
    _sky(fx, 12, one, gap=40, life=180, spread=36, hit=0.5, every=2, final=1.1)


def pillars(fx):
    """스톤에지: 날카로운 돌기둥이 줄지어 솟으며 달려가 꿰뚫는다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    row = [(0.3, 20, 7), (0.52, 28, 9), (0.76, 40, 11), (1.0, 66, 14)]
    seed = random.randrange(1000)
    m = K.Motes(seed)
    for q, (u, h, w) in enumerate(row):
        x, y = g.at(u)
        m.burst(q * 70, 3, x, y + 24, dist=(12, 28), life=(300, 420), ang=(-2.5, -0.6), g=620, size=(2.5, 4.5))
    paint = K.mote("ROCK")
    T = 620

    def rise(p, u, ms):
        for q, (u_, h, w) in enumerate(row):
            a = ms - q * 70
            if a < 0:
                continue
            x, y = g.at(u_)
            y += 24
            up = K.back(min(1.0, a / 110.0), 1.5) * (1.0 if ms < T - 140 else max(0.0, (T - ms) / 140.0))
            hh = h * k * up
            if hh < 1:
                continue
            tip = x + g.face * 6
            p.poly([x - w * k, y + 3, tip, y - hh, x + w * k, y + 3], c.dark, c.deep, 1)
            p.poly([tip, y - hh, x + w * k, y + 3, x + w * 0.2 * k, y + 3], c.light)
            p.line([x - w * 0.5 * k, y + 2, tip - 1, y - hh * 0.96], c.base, 1)
        m.draw(p, ms, paint)
    sh.act(0, T, rise)
    K.shake(fx, 180, 260, amp=2.2, vertical=True)
    K.impact(fx, 3 * 70 + 60, size=1.3)


def erupt(fx):
    """대지의힘: 발밑이 갈라져 빛이 새더니 불기둥이 솟는다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    lava = ("#7a1f0a", "#ff7a2c", "#ffe27a")
    gy = g.gt
    cols = [(0, 70), (-18, 48), (18, 54)]
    A, B = 200, 460
    seed = random.randrange(1000)
    rnd = random.Random(seed)
    cracks = [K.zigzag(g.tx, gy, g.tx + cos(a) * 42 * k, gy + sin(a) * 11 * k, 3, 4, rnd)
              for a in (-2.7, -0.45, 0.4, 2.75, 1.5)]
    m = K.Motes(seed)
    for q, (ox, h) in enumerate(cols):
        m.burst(A + q * 60, 3, g.tx + ox * k, gy, dist=(16, 34), life=(320, 460), ang=(-2.5, -0.6), g=620,
                size=(2.5, 4.5))
    paint = K.mote("GROUND")

    def glow(p, u, ms):
        f = K.out2(min(1.0, ms / float(A)))
        for q in cracks:
            n = max(2, int(round(len(q) / 2 * f)))
            p.line(q[:n * 2], c.deep, 6, cap="butt")
            p.line(q[:n * 2], lava[2] if int(ms / 50) % 2 else lava[1], 2, cap="butt")
        p.oval(g.tx, gy, 30 * k * f, 6 * k * f, "", lava[1], 2)
    sh.act(0, A + B, glow, z=-2)

    def pillar(p, u, ms):
        for q, (ox, h) in enumerate(cols):
            a = ms - q * 60
            if a < 0:
                continue
            up = K.back(min(1.0, a / 130.0), 1.3) * (1.0 if ms < B - 120 else max(0.0, (B - ms) / 120.0))
            r = h * k * up * (1 + 0.08 * sin(ms * 0.06 + q)) / 2.5
            if r > 2:
                K.flame(p, g.tx + ox * k, gy - r * 0.9 + 2, r, K.snoise(seed + q + int(ms / 50)) * 4, lava)
        m.draw(p, ms + A, paint)
    sh.act(A, B, pillar)
    K.shake(fx, A, B - 60, amp=2.2, vertical=True)
    K.impact(fx, A + 200, size=1.3, typ="FIRE" if fx.type in ("FIRE", "GROUND") else None)


def rocks(fx):
    """돌덩이 여러 개를 던진다 (암석포 · 바위깨기 · 스텔스록 ... 이름에 바위가 든 나머지)."""
    c = fx.c
    k = max(1.0, fx.big)

    def one(p, x, y, ang, j, v, ms):
        K.chunk(p, x, y, 9 * k, j + int(ms / 80), c.light, c.dark)
    end = volley(fx, 0, 4, one, gap=95, life=230, arc=20, spread=8, hit=0.8, ease=lambda u: u)
    K.impact(fx, end - 40, size=1.1)


def throw(fx):
    """무언가를 던진다: 타입 색 덩이가 빙글 돌며 포물선으로 날아간다."""
    c = fx.c
    cols = c.tri

    def one(p, x, y, ang, j, v, ms):
        K.arcs(p, x, y, 13, cols[1], 2, ms * 2.0, 2, 120)
        K.orb(p, x, y, 8.5 * max(1.0, fx.big), cols)
    end = volley(fx, 0, 1, one, life=330, arc=30, ease=lambda u: u, hit=0)
    K.impact(fx, end - 40, size=1.1)


def bone(fx):
    """뼈가 빙글빙글 돌면서 날아간다."""
    def one(p, x, y, ang, j, v, ms):
        a = ms * 0.03
        dx, dy = 13 * cos(a), 13 * sin(a) * 0.7
        p.line([x - dx, y - dy, x + dx, y + dy], "#6b6046", 8, cap="round")
        p.line([x - dx, y - dy, x + dx, y + dy], "#f4efe0", 5, cap="round")
        for sg in (-1, 1):
            p.oval(x + sg * dx, y + sg * dy, 4.2, 4.2, "#f4efe0", "#6b6046", 1)
        K.arcs(p, x, y, 16, WHITE, 1, ms * 1.5, 2, 90)
    end = volley(fx, 0, 1, one, life=340, arc=20, ease=lambda u: u, hit=0)
    K.impact(fx, end - 40, size=1.1)


def shot(fx):
    """닿지 않는 물리기: 타입의 것을 세 발 날린다 (불씨 · 물방울 · 잎 · 돌 ...)."""
    c = fx.c
    k = max(1.0, fx.big)
    paint = K.mote(fx.type)
    cols = c.tri

    def one(p, x, y, ang, j, v, ms):
        tail(p, x, y, ang, 26, 5 * k, cols)
        paint(p, x, y, 8 * k, ang, 1.0, j)
    end = volley(fx, 0, 3, one, gap=90, life=190, spread=10, m=fx.geo.mouth(12))
    K.impact(fx, end - 40, size=1.1)


def volley_multi(fx):
    """닿지 않는 연속기: 네 발을 연달아 (물수리검은 표창)."""
    c = fx.c
    k = max(1.0, fx.big)
    paint = K.mote(fx.type)
    star_ = fx.type in ("WATER", "DARK", "STEEL")

    def one(p, x, y, ang, j, v, ms):
        K.streak(p, x - cos(ang) * 24, y - sin(ang) * 24, x, y, 2.4, c.light)
        if star_:
            K.flare(p, x, y, 11 * k, 4, c.light, inner=0.34, rot=ms * 0.03 + j, outline=c.dark)
            p.oval(x, y, 2.2, 2.2, WHITE)
        else:
            paint(p, x, y, 8 * k, ang, 1.0, j)
    end = volley(fx, 0, 4, one, gap=85, life=170, spread=9)
    K.impact(fx, end - 40, size=1.0)


# ---------------------------------------------------------------- 바람
def _feathers(m, born, x, y, n):
    m.burst(born, n, x, y, dist=(14, 34), life=(360, 520), g=70, size=(4, 6.5), spin=4)


def wind(fx):
    """바람: 소용돌이치는 바람 줄기를 타고 바람 칼날 셋이 날아가 꽂히고 깃털이 흩날린다.

    변화기(깃털댄스 · 순풍 ...)는 바람과 깃털만 지나간다. 날개로 치는 기술(닿는 기술)은 fx_melee 가 달려들어 긋는다.
    """
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    status = is_status(fx)
    if not status and "contact" in (fx.move.get("flags") or []):
        from . import fx_melee
        return fx_melee.hit(fx)
    n, gap, life = 3, 100, 270
    total = (n - 1) * gap + life
    seed = random.randrange(1000)
    m = K.Motes(seed)
    for j in range(n):
        _feathers(m, j * gap + life - 20, g.tx + random.uniform(-10, 10), g.ty + random.uniform(-8, 8), 2)
    paint = K.mote("FLYING")

    def gusts(p, u, ms):
        thin = K.fade(u, 0.12, 0.8)
        for j in range(3):
            q = g.path(0.0, 1.0, 12, off=lambda u_, o=j: sin(u_ * 7 - ms * 0.03 + o * 2.1) * (10 + 6 * o) * k
                       * min(1.0, u_ * 3))
            K.ribbon(p, q, K.widths(12, (2.6 - 0.5 * j) * thin + 0.2), WHITE if j == 0 else c.light)
        m.draw(p, ms, paint)
    sh.act(0, total + 200, gusts, z=-1)
    if not status:
        def one(p, x, y, ang, j, v, ms):
            r = 25 * k
            wob = ang + 0.3 * sin(ms * 0.03 + j)
            cx, cy = x - cos(wob) * r, y - sin(wob) * r
            K.crescent(p, cx - cos(wob) * 9, cy - sin(wob) * 9, r, wob, 1.9, 5 * k, c.dark)
            K.crescent(p, cx, cy, r, wob, 2.2, 10 * k, c.light, c.dark)
            K.crescent(p, cx, cy, r - 1, wob, 2.2, 4 * k, WHITE)
        end = volley(fx, 0, n, one, gap=gap, life=life, spread=12, hit=0.7)
        K.impact(fx, end - 50, size=1.15)
    else:
        K.impact(fx, total - 60)


def tornado(fx):
    """회오리: 바람이 불어 가서 맞는 쪽을 깔때기로 휘감아 올린다. 밑동에 먼지가 일고 잔해가 말려 오른다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    A = 150
    B = 620 if power_of(fx) >= 100 else 460
    levels = 7
    base = g.gt + 2
    status = is_status(fx)

    def blow(p, u, ms):
        t1 = K.out2(u)
        t0 = max(0.0, t1 - 0.5)
        for j, off in enumerate((-12, 0, 12)):
            q = g.path(t0, t1, 6, off=lambda u_, o=off, jj=j: o + 6 * sin(u_ * 8 + jj))
            K.ribbon(p, q, K.widths(6, 2.4), WHITE if j == 1 else c.light)
    sh.act(0, A + 80, blow)
    # 맞는 쪽이 살짝 들려 흔들린다
    tgt = K.Mover(fx, None if (fx.miss or fx.immune or status) else fx.keys[1])

    def lift(p, u, ms):
        up = K.fade(u, 0.2, 0.8)
        tgt.to(3.0 * sin(ms * 0.03) * up, -6.0 * up)
    sh.act(A, B, lift, settle=tgt.home, z=-9)

    def funnel(p, u, ms):
        grow = K.out2(min(1.0, ms / 150.0)) * (1.0 if u < 0.85 else max(0.0, (1 - u) / 0.15))
        if grow < 0.05:
            return
        dr = (40 + 6 * sin(ms * 0.02)) * k * grow          # 밑동의 먼지 고리
        p.oval(g.tx, base, dr, dr * 0.22, "", c.dark, 3)
        p.oval(g.tx, base, dr * 0.7, dr * 0.15, "", c.light, 2)
        for j in range(levels):
            f = j / float(levels - 1)
            rx = (7 + 31 * f) * k * grow
            ry = max(2.0, rx * 0.3)
            cx = g.tx + sin(ms * 0.022 + j * 0.9) * (3 + 7 * f)
            cy = base - f * 68 * k * grow
            st = (ms * 1.5 + j * 61) % 360
            p.arc(cx, cy, rx, ry, st, 215, c.dark, 6)
            p.arc(cx, cy, rx, ry, st + 8, 200, WHITE if j % 2 else c.light, 3)
        for j in range(5):                                  # 말려 오르는 것들
            f = (ms * 0.0022 + j * 0.2) % 1.0
            a = ms * 0.03 + j * 1.7
            rx = (9 + 30 * f) * k
            x, y = g.tx + cos(a) * rx, base - f * 68 * k + sin(a) * rx * 0.3
            if j % 2:
                K.chunk(p, x, y, 4 * k, j, c.light, c.dark)
            else:
                K.feather(p, x, y, 5 * k, a, WHITE, c.base)
    sh.act(A, B, funnel)
    if status:
        K.impact(fx, A + B - 80)
    else:
        K.impact(fx, A + B - 90, size=1.25)


# ---------------------------------------------------------------- 폭발
def boom(fx):
    """폭발: 포탄이 꼬리를 끌고 날아가 번쩍 터진다. 불덩이가 부풀고 양옆에서 또 터지고, 바닥을 충격파가 쓸고 지나간
    뒤 연기가 버섯구름처럼 오른다. 대폭발 · 자폭은 쓰는 쪽에서 터진다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    if fx.type == "NORMAL":
        c = K.tone("FIRE")                              # 잿빛 폭발은 폭발 같지 않다
    cols = (c.dark, c.light, c.hot)
    at_self = any(w in K.key_of(fx.move) for w in ("explosion", "selfdestruct", "mindblown", "mistyexplosion"))
    k *= 1.2 if at_self else 1.0
    x0, y0 = fx.src if at_self else fx.dst
    A = 0 if at_self else 230
    seed = random.randrange(1000)
    if not at_self:
        mx, my = g.mouth(14)
        charge(fx, 0, 110, mx, my, 0.6)

        def shell(p, u, ms):
            v = K.in2(u)
            x, y = mx + (g.tx - mx) * v, my + (g.ty - my) * v
            tail(p, x, y, g.ang, 40 * k, 7.5 * k, cols)
            K.orb(p, x, y, 8.5 * k, (c.deep, c.base, c.hot))
        sh.act(90, A - 90, shell)
    side = [(-28, -8, 70), (26, -15, 130), (4, -30, 190)]   # 2차 폭발 (옆으로, 위로, 터지는 때)

    def blast(p, u, ms):
        if ms < 90:                                         # 섬광 기둥
            hw, hh = (17 - ms * 0.12) * k, (72 + ms * 0.35) * k
            p.oval(x0, y0 - hh * 0.35, hw, hh * 0.65, c.light)
            p.oval(x0, y0 - hh * 0.36, hw * 0.45, hh * 0.6, WHITE)
        if 50 < ms < 330:                                   # 바닥을 쓸고 가는 충격파
            v = (ms - 50) / 280.0
            rr = (24 + 96 * K.out2(v)) * k
            p.oval(x0, y0 + 16 * k, rr, rr * 0.26, "", c.deep, max(1, int(8 * (1 - v))) + 2)
            p.oval(x0, y0 + 16 * k, rr, rr * 0.26, "", c.light, max(1, int(8 * (1 - v))))
        if ms < 340:                                        # 불덩이 (겉은 남고 속이 먼저 꺼진다)
            r = (16 + 40 * K.out3(min(1.0, ms / 240.0))) * k
            shrink = 1.0 if ms < 150 else max(0.0, 1.0 - (ms - 150) / 190.0)
            K.blob(p, x0, y0, r * 1.1, c.deep, seed, ms * 0.012, n=12, jag=0.24)
            K.blob(p, x0, y0, r, c.dark if ms > 220 else c.base, seed, ms * 0.012, n=12, jag=0.24)
            if shrink > 0.1:
                K.blob(p, x0, y0, r * 0.72 * shrink, c.light, seed + 3, ms * 0.012, n=10, jag=0.24)
            if ms < 180:
                K.blob(p, x0, y0, r * 0.42 * shrink, WHITE, seed + 6, ms * 0.012, n=9, jag=0.22)
        for q, (ox, oy, t0) in enumerate(side):             # 2차 폭발
            a = ms - t0
            if 0 <= a < 190:
                r = (9 + 17 * K.out2(a / 110.0)) * k * (1.0 - a / 220.0)
                K.blob(p, x0 + ox * k, y0 + oy * k, r, c.dark, seed + q * 5, a * 0.02, n=9)
                K.blob(p, x0 + ox * k, y0 + oy * k, r * 0.66, c.light, seed + q * 5 + 2, a * 0.02, n=8)
                if a < 90:
                    K.blob(p, x0 + ox * k, y0 + oy * k, r * 0.34, WHITE, seed + q * 5 + 4, a * 0.02, n=7)
        if 110 < ms:                                        # 버섯구름처럼 오르는 연기
            for q in range(4):
                v = K.clamp((ms - 110 - q * 55) / 380.0)
                if 0 < v < 1:
                    K.smoke(p, x0 + (q - 1.5) * 9 * k + K.snoise(seed + q) * 6, y0 - (6 + 52 * K.out2(v)) * k,
                            (8 + 9 * K.hump(v)) * k, 1 - v, seed + q)
    sh.act(A, 620, blast)
    K.shake(fx, A + 40, 380, amp=2.6)
    if at_self:
        K.shake(fx, A, 380, amp=2.6, key=fx.keys[0])
    K.impact(fx, A, where=(x0, y0), size=1.5, move=not at_self)
    if at_self and not is_status(fx):
        K.impact(fx, 150, size=1.2)


# ---------------------------------------------------------------- 소리
def sound(fx):
    """소리: 입에서 굵은 음파가 겹겹이 퍼져 나간다. 공격기는 맞은 쪽이 덜덜 떨고 끝에 크게 맞는다.

    노래 · 울음소리 같은 변화기는 음표가 춤추며 날아가 상대 둘레에서 조용히 내려앉는다.
    """
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    status = is_status(fx)
    mx, my = g.mouth(16)
    reach = math.hypot(g.tx - mx, g.ty - my)
    N, GAP, LIFE = 5, 70, 280
    total = (N - 1) * GAP + LIFE

    def waves(p, u, ms):
        for j in range(N):
            a = ms - j * GAP
            if a < 0 or a >= LIFE:
                continue
            v = a / float(LIFE)
            rr = 12 + v * reach * 0.98
            w = max(1, int(8 * (1 - v * 0.75)))
            p.arc(mx, my, rr, rr, g.deg - 38, 76, c.deep, w + 4)
            p.arc(mx, my, rr, rr, g.deg - 36, 72, c.light if j % 2 else c.base, w)
            if v < 0.4:
                p.arc(mx, my, rr, rr, g.deg - 20, 40, WHITE, 2)
        K.flare(p, mx, my, (9 + 4 * (int(ms / 50) % 2)) * k, 6, c.hot, inner=0.4, rot=ms * 0.01)
    sh.act(0, total, waves)
    if status:
        def notes(p, u, ms):
            for j in range(3):
                v = K.clamp((ms - j * 80) / 380.0)
                if not 0 < v < 1:
                    continue
                x, y = g.at(v, sin(v * 9 + j) * 14)
                y -= 10 + 6 * sin(ms * 0.025 + j)
                K.note(p, x, y, 4.2, WHITE if j % 2 else c.light, c.deep)
        sh.act(60, total - 60, notes, z=2)
        K.impact(fx, total - 80)
    else:
        def quiver(p, u, ms):
            sh_ = 3 if int(ms / 40) % 2 else -3
            for j, rr in enumerate((24 * k, 36 * k)):
                p.oval(g.tx + sh_, g.ty, rr, rr * 0.75, "", c.light if j else WHITE, 2)
        sh.act(GAP * 2 + 60, total - GAP * 2 - 60, quiver)
        K.shake(fx, GAP * 2 + 60, total - GAP * 2 - 60, amp=2.6)
        K.impact(fx, total - 70, size=1.1 + 0.2 * (fx.big > 1.1))


def swarm(fx):
    """벌레 떼: 반짝이는 인분과 작은 날개들이 윙윙거리며 몰려가 뒤덮는다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    F, life = 520, 250

    def bug(p, x, y, v, j, ms):
        if j % 3 == 0:                                      # 날개 한 쌍
            a = g.ang + 0.6 * sin(ms * 0.09 + j)
            for sg in (-1, 1):
                K.leaf(p, x + g.px * 4 * sg, y + g.py * 4 * sg, 5 * k, a + sg * 1.1, c.hot, c.dark)
            p.oval(x, y, 2.4, 2.4, c.deep)
        else:
            r = (2 + (j % 3)) * k
            p.oval(x, y, r, r, c.alt if j % 2 else c.light, c.dark, 1)
    stream(fx, 0, F, life, 24, bug, cone=22, wob=10, over=1.05)

    def buzz(p, u, ms):
        rnd = random.Random(int(ms / 50))
        for _q in range(3):
            u0 = rnd.uniform(0.1, 0.8) * min(1.0, ms / 200.0)
            x, y = g.at(u0, rnd.uniform(-18, 18))
            p.line(K.zigzag(x, y, x + g.ux * 20, y + g.uy * 20, 5, 4, rnd), c.light, 1, cap="butt")
    sh.act(0, F, buzz, z=-1)
    K.shake(fx, life, F - life, amp=1.5)
    K.impact(fx, F - 50, size=1.1)


# ---------------------------------------------------------------- 흡수
def drain(fx):
    """흡수: 맞는 쪽에서 기운이 빨려 나와 굽이치는 두 줄기를 타고 내게 흘러든다. 드레인키스는 하트."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    kiss = "kiss" in K.key_of(fx.move)
    heal = ("#1f7a44", "#7bffa0", "#eafff0")
    n, gap, life = 8, 60, 300
    total = 120 + (n - 1) * gap + life
    amps = [(-1 if j % 2 else 1) * random.uniform(8, 22) for j in range(n)]
    if "contact" in (fx.move.get("flags") or []):
        fx.st.lunge(fx.who, lambda: None)
    K.mini(fx, 0, g.tx, g.ty, 1.0)
    K.jolt(fx, 0, 0.8)

    def sap(p, u, ms):
        if ms < 280:                                        # 빨려 나오는 자리 - 기운이 쪼그라든다
            r = 32 - ms * 0.09
            K.burst_star(p, g.tx, g.ty, r * 1.2, 9, "", 3, inner=0.62, rot=ms * 0.012, outline=c.dark, width=2)
            K.ring(p, g.tx, g.ty, r, c.light, 2, 0.8)
        if 80 < ms < total - 120:                           # 흘러드는 두 줄기
            for j in range(2):
                q = g.path(1.0, 0.0, 10, off=lambda u_, o=j: (16 if o else -16) * K.hump(u_) * cos(ms * 0.012 + o))
                K.ribbon(p, q, K.widths(10, 2.2), c.light if j else c.dark)
        for j in range(n):
            a = ms - 120 - j * gap
            if a < 0 or a >= life:
                continue
            v = a / float(life)
            x, y = g.at(1 - K.inout(v), amps[j] * K.hump(v))
            if kiss:
                K.heart(p, x, y, 7.5, c.base, c.deep)
            else:
                K.orb(p, x, y, 6.5, (c.dark, c.light, c.hot), shine=False)
                K.ring(p, x, y, 9.5, c.light, 1)
        a0 = ms - 120 - life                                # 스며든다 - 회복의 고리와 '+'
        if a0 > 0:
            f = (a0 % 260) / 260.0
            K.ring(p, g.sx, g.sy, (12 + 34 * f), heal[1], max(1, int(4 * (1 - f))), 0.8)
            for j in range(3):
                ph = (a0 * 0.003 + j * 0.33) % 1.0
                K.plus(p, g.sx + (j - 1) * 14, g.sy + 14 - 34 * ph, 5.5 * (1 - ph * 0.6), heal[1], heal[0])
    sh.act(0, total, sap)
    sh.wait(total + 60)


STYLES = {
    "laser": laser, "thunder": thunder, "quake": quake, "nova": nova,
    "flame": flame, "ember": ember, "daimonji": daimonji, "jet": jet, "bubble": bubble, "surf": surf,
    "zap": zap, "leafstorm": leafstorm, "leaf": leafstorm, "blizzard": blizzard, "icicles": icicles, "ice": ice,
    "sludge": sludge, "needles": needles, "psy": psy, "pulse": pulse, "ball": ball, "aura": ball,
    "moon": moon, "sparkle": sparkle, "flash": flash, "gem": gem, "rockfall": rockfall, "arrows": arrows,
    "meteor": meteor, "coins": coins, "pillars": pillars, "erupt": erupt, "rock": rocks, "throw": throw,
    "bone": bone, "shot": shot, "wind": wind, "tornado": tornado, "boom": boom, "sound": sound, "swarm": swarm,
    "drain": drain,
}
