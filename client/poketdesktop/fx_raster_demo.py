# -*- coding: utf-8 -*-
"""[시범] 그림 바탕에 맞춰 다시 그린 연출 셋 — 파괴광선(laser) · 화염방사(flame) · 섀도볼(ball).

도형 바탕의 연출은 '어두운 테 - 제 색 - 흰 심' 세 겹으로 빛을 흉내 냈다. 그림 바탕에서는 빛이 진짜로 번지므로
테를 두르지 않는다: 밝은 몸과 흰 심만 또렷하게 그리고, 둘레의 빛은 빛 층(p.glow*)에 넓게 깔아 번지게 둔다.
박자와 도트를 미는 것(시간표 · K.recoil · K.shake · K.impact)은 도형 바탕과 같다.
"""
import math
import random

from . import fx_kit as K

WHITE = K.WHITE
TAU = K.TAU
cos, sin = math.cos, math.sin


def laser(fx):
    """광선: 빛이 빨려 들어 눈부신 한 점이 되고, 넓은 후광을 두른 빛기둥이 뻗는다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    key = K.key_of(fx.move)
    pw = fx.move.get("power") or 0
    strong = pw >= 120 or any(w in key for w in ("solar", "hyper", "meteor", "eterna", "giga"))
    C, F = (380, 540) if strong else (240, 400)
    W = 5.0 if pw < 80 else 7.0 if pw < 120 else 10.0
    mx, my = g.mouth(18)
    deep = c.dark if fx.type not in ("GHOST", "DARK") else c.alt     # 후광은 심보다 짙어야 빛처럼 보인다
    seed = random.randrange(1000)
    seeds = [random.uniform(0, TAU) for _ in range(12)]
    N = 9

    def gather(p, u, ms):
        e = K.out2(u)
        p.glow(g.sx, g.gs, 34 * e * k, deep, 0.5 * e, 0.3)                 # 발밑에 고이는 빛
        p.glow(mx, my, (10 + 26 * e) * k, deep, 0.5 + 0.4 * u)
        p.glow(mx, my, (4 + 10 * e) * k, c.light, 1.0)
        for j, a0 in enumerate(seeds):                                     # 빨려 드는 빛줄
            ph = (u * 2.6 + j / 12.0) % 1.0
            a = a0 + u * 1.2
            r0 = (74 - 62 * ph) * k
            r1 = max(4.0, r0 - (10 + 16 * (1 - ph)) * k)
            K.streak(p, mx + cos(a) * r0, my + sin(a) * r0 * 0.85, mx + cos(a) * r1, my + sin(a) * r1 * 0.85,
                     1.8 * k * (1 - ph * 0.5), WHITE if j % 3 else c.light)
        r = (2.5 + 9 * e) * k * (1 + 0.1 * sin(ms * 0.06))
        K.disc(p, mx, my, r * 1.5, c.light)
        K.disc(p, mx, my, r, WHITE)
        ln = (20 + 70 * u * u) * k                                         # 가로로 길게 번쩍이는 빛살
        K.streak(p, mx - ln, my, mx + ln, my, 1.3 + 1.2 * u, WHITE)
        if u > 0.82:
            K.glint(p, mx, my, (26 + 40 * (u - 0.82) / 0.18) * k, WHITE)
    sh.act(0, C, gather)
    K.recoil(fx, C, 1.3 if strong else 0.7)
    K.shake(fx, C + 80, F - 80, amp=2.4 if strong else 1.4)
    m = K.Motes(seed)
    for j in range(14):                                                    # 닿은 자리에서 튀는 불티
        a = g.ang + math.pi + random.uniform(-1.3, 1.3)
        d = random.uniform(22, 60) * k
        m.add(90 + j * (F - 200) / 14.0, 220, g.tx, g.ty, cos(a) * d, sin(a) * d, 0, random.uniform(2.5, 4.5), a)

    def beam(p, u, ms):
        reach = K.out3(ms / 80.0)
        thin = 1.0 if ms < F - 130 else max(0.0, (F - ms) / 130.0)
        w = W * thin * (1.0 + 0.12 * sin(ms * 0.05))
        if w < 0.3:
            return
        pts = g.path(0.0, reach, N, m=(mx, my))
        p.glow_line(pts, deep, w * 3.6, 0.8)                               # 후광 - 빛 층에서 번진다
        p.glow_line(pts, c.base, w * 1.9, 1.0)
        edge = [w * 1.5 * (0.5 if i == 0 else 1.0) * (1.0 + 0.14 * sin(i * 2.3 - ms * 0.04)) for i in range(N + 1)]
        K.ribbon(p, pts, edge, c.light)
        K.ribbon(p, pts, [v * 0.6 for v in edge], WHITE)
        rnd = random.Random(seed + int(ms / 34))
        for _q in range(7):                                                # 줄기를 타고 흐르는 빛 조각
            uu = rnd.uniform(0.05, max(0.06, reach - 0.08))
            off = rnd.uniform(-1.9, 1.9) * w
            x, y = mx + (g.tx - mx) * uu + g.px * off, my + (g.ty - my) * uu + g.py * off
            ln_ = rnd.uniform(10, 26)
            K.streak(p, x, y, x + g.ux * ln_, y + g.uy * ln_, 1.2, WHITE if _q % 2 else c.hot)
        fl = 1.12 if int(ms / 40) % 2 else 0.94
        p.glow(mx, my, (W * 2.0 + 9) * thin * fl, c.base, 0.9)             # 쏘는 곳
        K.disc(p, mx, my, (W + 5) * thin * fl + 1, WHITE)
        K.streak(p, mx - 70 * k * thin, my, mx + 70 * k * thin, my, 1.8 * thin + 0.3, WHITE)
        K.streak(p, mx, my - 30 * k * thin, mx, my + 30 * k * thin, 1.4 * thin + 0.2, WHITE)
        if reach > 0.97:                                                   # 닿은 곳
            p.glow(g.tx, g.ty, (W * 2.6 + 12) * thin * fl, deep, 0.9)
            p.glow(g.tx, g.ty, (W * 1.5 + 6) * thin * fl, c.light, 1.0)
            K.disc(p, g.tx, g.ty, (W * 1.6 + 4) * thin * fl, WHITE)
            m.draw(p, ms, lambda p_, x, y, s_, rot, kk, n_: K.streak(
                p_, x - cos(rot) * s_ * 2.4 * kk, y - sin(rot) * s_ * 2.4 * kk, x, y, s_ * 0.45 * kk + 0.3,
                WHITE if n_ % 2 else c.hot))
    sh.act(C, F, beam)
    K.impact(fx, C + F - 70, size=1.45 if strong else 1.2)


def flame(fx):
    """불길: 테 없는 불덩이가 겹쳐 흐르고, 빛이 번져 한 줄기 불이 된다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    if fx.type in ("GHOST", "DARK", "DRAGON"):
        red, body, lite, hot = c.dark, c.base, c.light, c.hot if fx.type == "DRAGON" else c.alt
    else:
        red, body, lite, hot = "#e02a0a", "#ff7a1a", "#ffc23a", "#fff6c8"
    pw = fx.move.get("power") or 0
    F = 440 if pw < 70 else 540 if pw < 100 else 640
    life = 250
    mx, my = g.mouth(14)
    seed = random.randrange(1000)
    n = 16 if pw < 70 else 22
    seeds = [(random.uniform(-1, 1), random.uniform(0, TAU), random.uniform(0.86, 1.08)) for _ in range(n)]
    gap = (F - life) / float(n - 1)
    K.recoil(fx, 40, 0.6)
    K.shake(fx, life, F - life + 60, amp=1.8)
    m = K.Motes(seed)
    for j in range(12):
        m.add(life + j * (F - life) / 12.0, 340, g.tx + random.uniform(-24, 24) * k, g.ty + random.uniform(-6, 12),
              random.uniform(-8, 8), -random.uniform(28, 52), 0, random.uniform(1.6, 3.0), 0)

    def fire(p, u, ms):
        reach = K.out2(ms / float(life)) * 1.02
        thin = 1.0 if ms < F - 130 else max(0.0, (F - ms) / 130.0)
        pts = g.path(0.0, reach, 8, off=lambda u_: sin(u_ * 8 - ms * 0.02) * 2.5 * u_, m=(mx, my))
        if thin > 0.05:                                                    # 속이 꽉 찬 불줄기 + 번지는 열기
            ws = [(2.0 + 8.0 * (i / 8.0) ** 0.8) * k * thin for i in range(9)]
            p.glow_line(pts, red, 22 * k * thin, 0.8)
            p.glow_line(pts, body, 10 * k * thin, 0.9)
            K.ribbon(p, pts, ws, body)
            K.ribbon(p, pts, [w * 0.6 for w in ws], lite)
            K.ribbon(p, pts, [w * 0.26 for w in ws], hot)
        for j in range(n):                                                 # 흘러가는 불덩이 (테가 없다)
            a = ms - j * gap
            if a < 0 or a >= life:
                continue
            v = a / float(life)
            s_, ph, sp = seeds[j]
            d = min(1.06, v * sp * 1.06)
            off = s_ * 12 * v + sin(v * 7 + ph) * 4 * v
            x, y = mx + (g.tx - mx) * d + g.px * off, my + (g.ty - my) * d + g.py * off
            r = (3.5 + 8.5 * v) * k
            p.glow(x, y, r * 1.5, red, 0.7)
            K.blob(p, x, y, r, body if v < 0.7 else red, seed + j, ms * 0.02 + j, n=8, jag=0.3)
            if v < 0.75:
                K.blob(p, x, y + r * 0.1, r * 0.6, lite, seed + j + 9, ms * 0.02 + j, n=7, jag=0.3)
            if v < 0.4:
                K.disc(p, x, y, r * 0.3, hot)
        K.disc(p, mx, my, (5 + 1.5 * sin(ms * 0.05)) * k * thin + 1, hot)
        p.glow(mx, my, 11 * k * thin, body, 1.0)
        if ms > life - 20:                                                 # 불길에 휩싸인다
            f = K.fade((ms - life + 20) / float(F - life + 100), 0.15, 0.75)
            p.glow(g.tx, g.ty + 6, 34 * k * f, red, 0.85)
            p.glow(g.tx, g.ty + 8, 17 * k * f, body, 1.0)
            for j in range(5):
                r = (12 + 6 * sin(ms * 0.03 + j * 2.1)) * k * f * (1.25 - abs(j - 2) * 0.16)
                if r > 2:
                    K.flame(p, g.tx + (j - 2) * 11 * k, g.ty + 18 * k - r * 0.4, r, K.snoise(seed + j + int(ms / 50)) * 5,
                            (body, lite, hot))
            m.draw(p, ms, lambda p_, x, y, s2, rot, kk, n_: (p_.glow(x, y, s2 * 3, body, kk),
                                                              K.disc(p_, x, y, s2 * (0.4 + 0.6 * kk), hot)))
    sh.act(0, F + 100, fire)
    K.impact(fx, F - 20, size=1.2)


def ball(fx):
    """구슬: 어둠이 소용돌이쳐 뭉치고, 빛을 두른 구슬이 긴 빛 꼬리를 끌며 날아가 터진다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    dark_ = fx.type in ("GHOST", "DARK")
    halo = c.base if not dark_ else "#8a4cff"
    rim = c.light if not dark_ else c.alt
    core = c.hot if not dark_ else "#150a2e"
    mx, my = g.mouth(20)
    R = 13.0 * k
    C, T = 320, 300
    seed = random.randrange(1000)
    seeds = [random.uniform(0, TAU) for _ in range(10)]
    K.recoil(fx, C, 0.9)

    def orb(p, x, y, r, ms, lit=1.0):
        p.glow(x, y, r * 2.5, halo, 0.85 * lit)
        p.glow(x, y, r * 1.5, rim, 0.8 * lit)
        K.disc(p, x, y, r * 1.12, rim)
        K.disc(p, x, y, r, core)
        if dark_:                                                          # 어두운 구슬 속에서 도는 빛
            K.arcs(p, x, y, r * 0.62, c.alt, 2, ms * 1.6, 2, 130)
            K.disc(p, x - r * 0.3, y - r * 0.32, r * 0.2, "#c8a8ff")
        else:
            K.disc(p, x, y, r * 0.55, WHITE)
        K.arcs(p, x, y, r * 1.55, rim, 2, -ms * 1.2, 2, 100)

    def gather(p, u, ms):
        e = K.out2(u)
        for j, a0 in enumerate(seeds):                                     # 휘감겨 드는 기운
            ph = (u * 2.2 + j / 10.0) % 1.0
            a = a0 + ph * 3.2
            rr = (56 - 50 * ph) * k
            x, y = mx + cos(a) * rr, my + sin(a) * rr * 0.85
            bx, by = mx + cos(a - 0.5) * (rr + 9), my + sin(a - 0.5) * (rr + 9) * 0.85
            K.streak(p, bx, by, x, y, 2.4 * k * (1 - ph * 0.5), rim if j % 2 else halo)
        orb(p, mx, my, max(2.0, R * e), ms, 0.4 + 0.6 * u)
    sh.act(0, C, gather)
    m = K.Motes(seed)
    for j in range(12):
        u = (j + random.random()) / 12.0
        v = K.in2(u)
        a = random.uniform(0, TAU)
        m.add(C + T * u, 300, mx + (g.tx - mx) * v, my + (g.ty - my) * v, cos(a) * 12, sin(a) * 12 - 6, 0,
              random.uniform(3.5, 6), a, 4)
    paint = K.mote(fx.type)

    def fly(p, u, ms):
        v = K.in2(u)
        x, y = mx + (g.tx - mx) * v, my + (g.ty - my) * v
        tl = min(R * 6.5, math.hypot(x - mx, y - my))
        if tl > 4:                                                         # 빛 꼬리 (뒤로 갈수록 가늘고 옅다)
            for q, (ln_, w, a_) in enumerate(((1.0, 0.9, 0.5), (0.62, 1.5, 0.75), (0.3, 2.0, 1.0))):
                p.glow_line([x - g.ux * tl * ln_, y - g.uy * tl * ln_, x, y], halo if q < 2 else rim, R * w, a_)
            K.comet(p, x - g.ux * tl * 0.8, y - g.uy * tl * 0.8, x, y, R * 0.7, rim)
            K.comet(p, x - g.ux * tl * 0.5, y - g.uy * tl * 0.5, x, y, R * 0.42, core if dark_ else WHITE)
        m.draw(p, ms + C, paint)
        orb(p, x, y, R * (1 + 0.07 * sin(ms * 0.07)), ms)
    sh.act(C, T, fly)
    K.impact(fx, C + T - 40, size=1.3)


STYLES = {"laser": laser, "flame": flame, "ball": ball}
