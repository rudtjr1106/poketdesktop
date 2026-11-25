# -*- coding: utf-8 -*-
"""몸으로 치는 것 — 달려들어 치는 기술의 연출.

    달려든다(K.rush - 몸은 무대가 옮기고, 길에 잔상이 남는다) -> 타입 · 무기에 맞는 한 수 -> 맞는 순간(K.impact)

닿는 순간부터의 시각이 0 이다 (rush 가 기준을 옮긴다). 타입의 한 수(FLOURISH)는 (fx, at) 을 받아 장면을 넣고
끝나는 시각을 돌려준다 - 그 조금 앞에 맞는 순간이 얹힌다.
"""
import math
import random

from . import battle_fx as FX
from . import fx_kit as K

WHITE = K.WHITE
TAU = K.TAU
cos, sin = math.cos, math.sin


def contact(fx):
    return "contact" in (fx.move.get("flags") or [])


# ---------------------------------------------------------------- 함께 쓰는 한 수
def sweep(fx, at, mirror=False, cols=None, thick=15.0, span=2.5, r=54.0, dur=190):
    """크게 휘두른 자국: 초승달이 한쪽 끝에서 다른 쪽 끝으로 그어지고, 가늘어지며 날 끝의 빛이 미끄러진다."""
    sh, g, k = fx.show, fx.geo, fx.big
    c = fx.c
    rim, body, core = cols or (c.deep, c.light if fx.type not in ("GHOST", "DARK") else c.dark, WHITE)
    r = r * k
    thick = thick * k
    tilt = (0.75 if mirror else -0.75) * g.face
    ang = g.ang + tilt
    cx, cy = g.tx - cos(ang) * r * 0.62, g.ty - sin(ang) * r * 0.62
    lo, hi = ang - span / 2.0, ang + span / 2.0
    if mirror:
        lo, hi = hi, lo

    def draw(p, u, ms):
        if u < 0.5:                                         # 그어지는 중
            a1 = lo + (hi - lo) * K.out2(u / 0.5)
            K.crescent(p, cx, cy, r + 15 * k, ang, span, thick * 0.3, rim, a0=lo, a1=a1)
            K.crescent(p, cx, cy, r + 4 * k, ang, span, thick * 1.25, rim, a0=lo, a1=a1)
            K.crescent(p, cx, cy, r, ang, span, thick, body, a0=lo, a1=a1)
            K.crescent(p, cx, cy, r - 1, ang, span, thick * 0.45, core, a0=lo, a1=a1)
            K.glint(p, cx + cos(a1) * r, cy + sin(a1) * r, 13 * k, WHITE)
        else:                                               # 남은 자국이 가늘어진다
            v = (u - 0.5) / 0.5
            th = thick * (1 - v) ** 1.4
            if th > 0.6:
                K.crescent(p, cx, cy, r + 3 * k, ang, span, th * 1.3, rim)
                K.crescent(p, cx, cy, r, ang, span, th, body)
                K.crescent(p, cx, cy, r - 1, ang, span, th * 0.45, core)
            a2 = lo + (hi - lo) * v
            K.glint(p, cx + cos(a2) * r, cy + sin(a2) * r, 15 * k * (1 - v * 0.5), WHITE)
    return sh.act(at, dur, draw)


def rips(fx, at, mirror=False, cols=None, dur=170, n=3):
    """발톱 자국 세 줄이 위에서 아래로 죽 그어진다."""
    sh, g, k, c = fx.show, fx.geo, fx.big, fx.c
    rim, body, core = cols or (c.deep, c.light if fx.type not in ("GHOST", "DARK") else c.alt, WHITE)
    s = g.face * (-1 if mirror else 1)

    def draw(p, u, ms):
        f = K.out2(min(1.0, u / 0.45))
        thin = 1.0 if u < 0.55 else max(0.0, 1.0 - (u - 0.55) / 0.45)
        for j in range(n):
            o = (j - (n - 1) / 2.0) * 18
            x1, y1 = g.tx + s * (-30 + o) * k, g.ty - 38 * k
            x2, y2 = x1 + s * 52 * k * f, y1 + 76 * k * f
            w = (8.0 if j == n // 2 else 6.4) * k * thin
            if w < 0.5:
                continue
            K.streak(p, x1, y1, x2, y2, w * 1.5, rim)
            K.streak(p, x1, y1, x2, y2, w, body)
            K.streak(p, x1, y1, x2, y2, w * 0.4, core)
    return sh.act(at, dur, draw)


def speedlines(fx, at, dur, n=5, ln=46.0, back=10.0, col=None):
    """맞는 쪽으로 꽂히는 속도선."""
    g, c = fx.geo, fx.c

    def draw(p, u, ms):
        f = 1 - K.out2(u)
        for j in range(n):
            off = (j - (n - 1) / 2.0) * 9
            x2 = g.tx - g.ux * (back + 30 * f) + g.px * off
            y2 = g.ty - g.uy * (back + 30 * f) + g.py * off
            K.streak(p, x2 - g.ux * ln * (0.6 + 0.4 * f), y2 - g.uy * ln * (0.6 + 0.4 * f), x2, y2,
                     1.8 if j != n // 2 else 2.4, WHITE if j % 2 == 0 else (col or c.light))
    return fx.show.act(at, dur, draw, z=-1)


# ---------------------------------------------------------------- 타입의 한 수 (접촉기)
def _smash(fx, at):
    """정통으로 친다: 달려든 쪽에서 날아와 꽂히는 쐐기 다섯 줄."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big

    def draw(p, u, ms):
        far = 60 * (1 - K.out3(u))
        for j, off in enumerate((-22, -11, 0, 11, 22)):
            sc = 1.0 - abs(off) / 44.0
            x1 = g.tx - g.ux * (far + 44) * sc + g.px * off * 1.5 * k
            y1 = g.ty - g.uy * (far + 44) * sc + g.py * off * 1.5 * k
            x2 = g.tx - g.ux * far * 0.2 + g.px * off * 0.35 * k
            y2 = g.ty - g.uy * far * 0.2 + g.py * off * 0.35 * k
            K.streak(p, x1, y1, x2, y2, (5.5 if j == 2 else 4.2) * k, c.dark)
            K.streak(p, x1, y1, x2, y2, (2.6 if j == 2 else 1.9) * k, WHITE if j in (1, 2, 3) else c.light)
    return sh.act(at, 110, draw)


def _burn(fx, at):
    """불꽃을 두른 한 방: 불길이 호를 그리며 휘감기고 불티가 튄다."""
    c = fx.c
    end = sweep(fx, at, cols=(c.dark, c.base, c.hot), thick=17)
    g, k = fx.geo, fx.big
    seed = random.randrange(1000)

    def lick(p, u, ms):
        f = K.fade(u, 0.2, 0.6)
        for j in range(4):
            a = g.ang - 1.1 * g.face + j * 0.7 * g.face
            x, y = g.tx + cos(a) * 26 * k, g.ty + sin(a) * 22 * k
            K.flame(p, x, y, (8 + 3 * sin(ms * 0.04 + j)) * k * f + 1, K.snoise(seed + j + int(ms / 45)) * 4,
                    (c.dark, c.light, c.hot))
    fx.show.act(at + 40, 230, lick, z=1)
    return end


def _crash(fx, at):
    """물을 두른 한 방: 물결이 말려 올라 내리덮친다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    f_ = g.face

    def draw(p, u, ms):
        grow = K.back(min(1.0, u / 0.5), 1.4) * (1.0 if u < 0.7 else (1 - u) / 0.3)
        x, y = g.tx - f_ * 20 * (1 - u), g.ty + 22 * k
        h, w = 52 * k * grow, 40 * k
        for sc, col in ((1.1, c.deep), (1.0, c.dark), (0.78, c.base), (0.5, c.light)):
            p.poly([x - f_ * w * sc, y, x - f_ * w * 0.4 * sc, y - h * 0.55 * sc, x + f_ * w * 0.1 * sc, y - h * sc,
                    x + f_ * w * 0.7 * sc, y - h * 0.78 * sc, x + f_ * w * 0.36 * sc, y - h * 0.34 * sc,
                    x + f_ * w * 0.5 * sc, y], col, "", 1, True)
        for j in range(3):
            K.disc(p, x + f_ * w * (0.1 + j * 0.2), y - h * (0.94 - j * 0.1), (6 - j) * grow + 1, WHITE)
    return sh.act(at, 220, draw)


def _crackle(fx, at):
    """몸에 감긴 전기가 터진다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    seed = random.randrange(1000)
    cols = (c.dark, c.base, c.hot)

    def draw(p, u, ms):
        rnd = random.Random(seed + int(ms / 40))
        for _j in range(6):
            a = rnd.uniform(0, TAU)
            r = rnd.uniform(26, 46) * k
            K.bolt(p, K.zigzag(g.tx, g.ty, g.tx + cos(a) * r, g.ty + sin(a) * r * 0.85, 7, 4, rnd), 2, cols)
        K.arcs(p, g.tx, g.ty, (20 + 20 * u) * k, c.alt, 2, ms * 2.0, 3, 60)
    speedlines(fx, at, 120)
    return sh.act(at, 180, draw)


def _leafblade(fx, at):
    """잎날 두 번: 초록 칼날이 X 자로 엇갈리고 잎이 흩어진다."""
    c = fx.c
    cols = (c.deep, c.base, c.hot)
    sweep(fx, at, cols=cols, thick=13)
    return sweep(fx, at + 80, mirror=True, cols=(c.deep, c.light, WHITE), thick=13)


def _frostbite(fx, at):
    """얼음 송곳이 사방에서 박힌다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big

    def draw(p, u, ms):
        f = K.back(min(1.0, u / 0.4), 1.6)
        thin = 1.0 if u < 0.7 else (1 - u) / 0.3
        for j in range(5):
            a = g.ang + math.pi + (j - 2) * 0.55
            r0 = (52 - 34 * f) * k
            x, y = g.tx + cos(a) * r0, g.ty + sin(a) * r0
            K.spike(p, x, y, 5.5 * k * thin, 30 * k * thin, a + math.pi, c.light, c.dark)
            K.spike(p, x, y, 2.2 * k * thin, 24 * k * thin, a + math.pi, WHITE)
    speedlines(fx, at, 120)
    return sh.act(at, 200, draw)


def _fist(fx, at):
    """격투: 압축된 충격이 반달로 밀려들고 별이 튄다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big

    def draw(p, u, ms):
        f = K.out3(u)
        for j, (rr, th, col) in enumerate(((46, 13, c.deep), (44, 10, c.base), (42, 4.5, c.hot))):
            r = (rr - 16 * (1 - f)) * k
            cx, cy = g.tx - g.ux * (r + 12 * (1 - f)), g.ty - g.uy * (r + 12 * (1 - f))
            K.crescent(p, cx, cy, r, g.ang, 1.9, th * k * (1 - u * 0.6), col)
        K.flare(p, g.tx - g.ux * 6, g.ty - g.uy * 6, (14 + 16 * f) * k, 5, c.alt, inner=0.42, rot=ms * 0.01,
                outline=c.deep)
    speedlines(fx, at, 130, n=7, ln=58, col=c.alt)
    return sh.act(at, 150, draw)


def _toxic(fx, at):
    """독을 묻힌 한 방: 보랏빛 자국에서 독이 튀고 거품이 인다."""
    c = fx.c
    end = rips(fx, at, cols=(c.deep, c.base, c.alt))
    g, k = fx.geo, fx.big
    m = K.Motes(random.randrange(1000))
    m.burst(0, 7, g.tx, g.ty, dist=(14, 34), life=(260, 380), g=120, size=(3, 6), lift=10)
    paint = K.mote("POISON")
    fx.show.act(at + 40, 360, lambda p, u, ms: m.draw(p, ms, paint), z=1)
    return end


def _upheave(fx, at):
    """발밑의 땅이 치받는다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    gy = g.gt
    slabs = [(0, 34, 10), (-17, 22, 8), (17, 25, 8)]

    def draw(p, u, ms):
        up = K.back(min(1.0, u / 0.4), 1.5) * (1.0 if u < 0.7 else (1 - u) / 0.3)
        for q, (ox, h, w) in enumerate(slabs):
            x = g.tx + ox * k
            tip = x + ox * 0.15
            hh = h * k * up
            if hh > 1:
                p.poly([x - w * k, gy + 3, tip, gy - hh, x + w * k, gy + 3], c.dark, c.deep, 1)
                p.poly([tip, gy - hh, x + w * k, gy + 3, x + w * 0.15 * k, gy + 3], c.light)
        for sgn in (-1, 1):
            K.blob(p, g.tx + sgn * (18 + 16 * u) * k, gy, (8 - 5 * u) * k, c.light, sgn + 2, n=7, jag=0.2,
                   outline=c.base)
    speedlines(fx, at, 110)
    return sh.act(at, 240, draw)


def _wing(fx, at):
    """날개로 친다: 흰 날개 자국 두 줄이 X 로 엇갈리고 깃털이 흩날린다."""
    c = fx.c
    g = fx.geo
    m = K.Motes(random.randrange(1000))
    m.burst(40, 6, g.tx, g.ty, dist=(16, 38), life=(380, 520), g=70, size=(4.5, 7), spin=4)
    paint = K.mote("FLYING")
    fx.show.act(at, 540, lambda p, u, ms: m.draw(p, ms, paint), z=1)
    sweep(fx, at, cols=(c.dark, c.light, WHITE), span=2.0)
    return sweep(fx, at + 70, mirror=True, cols=(c.dark, c.hot, WHITE), span=2.0)


def _mindspike(fx, at):
    """염력을 실은 한 방: 고리가 조여들며 번쩍인다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big

    def draw(p, u, ms):
        for j in range(3):
            r = (50 - 38 * K.out2(K.clamp(u * 1.3 - j * 0.12))) * k
            K.ring(p, g.tx, g.ty, r, c.alt if j % 2 else c.light, 3, 0.8)
        K.sigil(p, g.tx, g.ty, (30 - 14 * u) * k, ms * 0.02, c.base, 2, 0.8)
        K.glint(p, g.tx, g.ty, (10 + 22 * u) * k, WHITE, rot=ms * 0.01)
    return sh.act(at, 190, draw)


def _xscissor(fx, at):
    """벌레의 낫: 가늘고 날카로운 자국이 X 로 엇갈린다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big

    def draw(p, u, ms):
        f = K.out3(min(1.0, u / 0.45))
        thin = 1.0 if u < 0.5 else (1 - u) / 0.5
        for sg in (1, -1):
            ln = 46 * k
            x1, y1 = g.tx - ln * 0.8, g.ty - ln * sg * 0.72
            x2, y2 = x1 + ln * 1.6 * f, y1 + ln * sg * 1.44 * f
            K.streak(p, x1, y1, x2, y2, 7.5 * k * thin, c.deep)
            K.streak(p, x1, y1, x2, y2, 5 * k * thin, c.base)
            K.streak(p, x1, y1, x2, y2, 1.8 * k * thin, c.hot)
        if u > 0.4:
            K.glint(p, g.tx, g.ty, 22 * k * (1 - u) + 4, WHITE)
    return sh.act(at, 200, draw)


def _rocksmash(fx, at):
    """바위로 내리친다: 큰 돌이 깨지며 조각이 튄다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    m = K.Motes(random.randrange(1000))
    m.burst(90, 7, g.tx, g.ty, dist=(18, 42), life=(320, 460), g=620, size=(3, 6))
    paint = K.mote("ROCK")

    def draw(p, u, ms):
        if ms < 100:
            v = K.in2(ms / 100.0)
            y = g.ty - 46 * k * (1 - v)
            K.chunk(p, g.tx - g.face * 6, y, 17 * k, 3, c.light, c.dark)
            K.streak(p, g.tx - g.face * 6, y - 40, g.tx - g.face * 6, y - 12, 2.5, c.light)
        m.draw(p, ms, paint)
    return sh.act(at, 480, draw) - 340


def _haunt(fx, at):
    """그림자가 발밑에서 솟아 덮친다. 어둠 속에서 눈이 번뜩인다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    seed = random.randrange(1000)

    def draw(p, u, ms):
        h = (30 + 40 * K.out2(min(1.0, u / 0.5))) * k * (1.0 if u < 0.8 else (1 - u) / 0.2)
        p.oval(g.tx, g.gt, 30 * k, 6 * k, c.deep, c.edge or c.light, 1)
        for j, (ox, kk) in enumerate(((-18, 0.7), (17, 0.76), (0, 1.0))):
            lean = 6 * sin(ms * 0.03 + j * 2)
            r = h * kk * 0.42
            if r > 2:
                K.tongue(p, g.tx + ox * k, g.gt + 6 - r, r, lean, c.deep, c.edge or c.light)
                K.tongue(p, g.tx + ox * k, g.gt + 6 - r * 0.8, r * 0.6, lean * 0.7, c.dark)
        if 0.2 < u < 0.85:                                  # 눈
            for ex in (-7, 7):
                K.streak(p, g.tx + ex * k - 5, g.ty - 6, g.tx + ex * k + 5, g.ty - 8 + (2 if ex > 0 else -2), 2.6, c.alt)
    return sh.act(at, 260, draw)


def _rend(fx, at):
    """용의 발톱: 엇갈린 발톱 두 번, 금빛이 튄다."""
    c = fx.c
    rips(fx, at, cols=(c.deep, c.base, c.hot), dur=150)
    return rips(fx, at + 90, mirror=True, cols=(c.deep, c.light, c.alt), dur=160)


def _nightslash(fx, at):
    """어둠의 칼: 검은 초승달 둘이 엇갈리고 붉은 날이 선다."""
    c = fx.c
    sweep(fx, at, cols=(c.light, c.deep, c.alt), thick=14)
    return sweep(fx, at + 70, mirror=True, cols=(c.light, c.dark, c.alt), thick=12)


def _clang(fx, at):
    """쇠가 부딪힌다: 길게 번쩍이는 십자와 불똥."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    m = K.Motes(random.randrange(1000))
    m.burst(0, 8, g.tx, g.ty, dist=(20, 52), life=(220, 340), g=300, size=(3, 5.5))
    paint = K.mote("STEEL")

    def draw(p, u, ms):
        r = (18 + 44 * K.out3(u)) * k
        th = max(0.6, 4 * (1 - u)) * k
        K.streak(p, g.tx - r * 1.5, g.ty, g.tx + r * 1.5, g.ty, th * 1.8, c.dark)
        K.streak(p, g.tx, g.ty - r * 1.5, g.tx, g.ty + r * 1.5, th * 1.8, c.dark)
        K.streak(p, g.tx - r * 1.5, g.ty, g.tx + r * 1.5, g.ty, th, WHITE)
        K.streak(p, g.tx, g.ty - r * 1.5, g.tx, g.ty + r * 1.5, th, WHITE)
        K.flare(p, g.tx, g.ty, r * 0.55, 4, c.light, inner=0.3, rot=math.pi / 4)
        m.draw(p, ms, paint)
    speedlines(fx, at, 110)
    return sh.act(at, 340, draw) - 200


def _brawl(fx, at):
    """치근거리기: 먼지 구름 속에서 별과 하트가 튄다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    seed = random.randrange(1000)
    m = K.Motes(seed)
    m.burst(0, 9, g.tx, g.ty, dist=(18, 46), life=(300, 460), g=160, size=(4.5, 7.5), ang=(-math.pi, 0))
    paint = K.mote("FAIRY")
    spots = [(random.uniform(-20, 20), random.uniform(-14, 14), random.uniform(11, 17), j * 34) for j in range(8)]

    def draw(p, u, ms):
        for j, (ox, oy, r, t0) in enumerate(spots):
            a = ms - t0
            if 0 <= a < 170:
                v = a / 170.0
                K.blob(p, g.tx + ox * k, g.ty + oy * k, r * (0.6 + 0.6 * v) * k, WHITE if v < 0.5 else c.light,
                       seed + j, n=8, jag=0.2, outline=c.dark)
        m.draw(p, ms, paint)
    return sh.act(at, 440, draw) - 200


FLOURISH = {
    "NORMAL": _smash, "FIRE": _burn, "WATER": _crash, "ELECTRIC": _crackle, "GRASS": _leafblade,
    "ICE": _frostbite, "FIGHTING": _fist, "POISON": _toxic, "GROUND": _upheave, "FLYING": _wing,
    "PSYCHIC": _mindspike, "BUG": _xscissor, "ROCK": _rocksmash, "GHOST": _haunt, "DRAGON": _rend,
    "DARK": _nightslash, "STEEL": _clang, "FAIRY": _brawl,
}


def hit(fx):
    """접촉기: 달려들어 때린다. 타입마다 한 수가 다르다."""
    def strike():
        end = (FLOURISH.get(fx.type) or _smash)(fx, 0)
        K.impact(fx, max(0, end - 70), size=1.15)
    K.rush(fx, strike)


def flurry(fx):
    """난타 (인파이트 · 역린): 사방에서 연달아 꽂히는 타격과 속도선, 마지막에 크게."""
    g, c, k = fx.geo, fx.c, fx.big

    def strike():
        n = 7
        for i in range(n):
            a = i * 2.4 + random.uniform(-0.4, 0.4)
            K.mini(fx, i * 62, g.tx + cos(a) * 21, g.ty + sin(a) * 17, 0.9, n=2)
        speedlines(fx, 0, n * 62, n=7, ln=64)

        def lines(p, u, ms):                                # 주먹이 스친 자국
            j = int(ms / 62)
            a = g.ang + ((j * 7) % 5 - 2) * 0.32
            f = (ms % 62) / 62.0
            x2, y2 = g.tx + cos(a) * 14, g.ty + sin(a) * 14
            K.streak(p, x2 - cos(a) * 62 * (1 - f * 0.4), y2 - sin(a) * 62 * (1 - f * 0.4), x2, y2, 4.5 * k * (1 - f),
                     c.deep)
            K.streak(p, x2 - cos(a) * 56 * (1 - f * 0.4), y2 - sin(a) * 56 * (1 - f * 0.4), x2, y2, 2.4 * k * (1 - f),
                     c.hot)
        fx.show.act(0, n * 62, lines)
        K.shake(fx, 0, n * 62, amp=2.2)
        K.impact(fx, n * 62 + 20, size=1.35)
    K.rush(fx, strike)


def dash(fx):
    """선공기: 눈에 안 보이게 스치고 지나간다 - 빛줄기가 과녁을 꿰뚫고, 한 박자 뒤에 터진다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    cols = c.tri
    fx.st.lunge(fx.who, lambda: None)                   # 몸도 같이 움찔한다 (궤적은 여기서 그린다)

    def draw(p, u, ms):
        if ms < 150:                                        # 꿰뚫고 지나가는 빛줄기
            head = 1.35 * K.out2(ms / 110.0)
            tailp = 1.35 * K.in2(ms / 150.0)
            if head - tailp > 0.03:
                pts = g.path(tailp, head, 6)
                K.glow_ribbon(p, pts, K.widths(6, 8.5 * k, "comet"), cols)
                for j, off in enumerate((-10, 10)):
                    x1, y1 = g.at(tailp + 0.05, off)
                    x2, y2 = g.at(head - 0.05, off * 0.5)
                    K.streak(p, x1, y1, x2, y2, 1.5, WHITE)
            for j in range(3):                              # 잔상
                x, y = g.at(max(0.0, head - 0.24 * (j + 1)))
                K.ring(p, x, y, (13 - j * 3) * k, cols[0] if fx.type not in ("GHOST", "DARK") else c.light, 2)
        elif ms < 300:                                      # 지나간 자리에 남는 한 줄
            v = (ms - 150) / 150.0
            ln = 62 * k
            K.streak(p, g.tx - g.ux * ln, g.ty - g.uy * ln, g.tx + g.ux * ln, g.ty + g.uy * ln, 6 * k * (1 - v), cols[0])
            K.streak(p, g.tx - g.ux * ln, g.ty - g.uy * ln, g.tx + g.ux * ln, g.ty + g.uy * ln, 3 * k * (1 - v), WHITE)
    sh.act(0, 300, draw)
    K.impact(fx, 150, size=1.05)


def phantom(fx):
    """고스트다이브: 그림자가 땅을 타고 가서 발밑에서 솟아 덮친다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    A = 260

    def slide(p, u, ms):
        v = K.in2(u)
        x, y = g.at(v)
        y += 26
        w = (22 + 8 * sin(ms * 0.04)) * k
        p.oval(x, y, w, 6.5 * k, c.deep, c.edge or c.light, 2)
        for j in range(3):                                  # 지나온 자리
            bx, by = g.at(max(0.0, v - 0.12 * (j + 1)))
            bw = (14 - j * 4) * k
            p.oval(bx, by + 26, bw, 3.5 * k, c.deep)
        K.streak(p, x - 6, y - 2, x + 6, y - 3, 2.2, c.alt)
    sh.act(0, A, slide)

    def strike():
        sh.rebase()
        end = _haunt(fx, 0)
        K.impact(fx, end - 110, size=1.25)
    sh.cue(A, strike)


def slash(fx):
    """베기. 닿는 기술이면 달려들어 벤다. 이름에 cross 가 있으면 X 자로 두 번."""
    cross = any(w in K.key_of(fx.move) for w in ("cross", "xscissor", "scissor", "dual", "double"))

    def cut():
        if cross:
            sweep(fx, 0)
            end = sweep(fx, 80, mirror=True)
        else:
            end = sweep(fx, 0, thick=17)
        K.impact(fx, end - 110, size=1.15)
    if contact(fx):
        K.rush(fx, cut)
    else:
        cut()


def blades(fx):
    """칼날이 날아간다 (에어슬래시 · 사이코커터): 초승달 셋이 잔상을 끌며 날아가 꽂히고, 끝에 크게 벤다."""
    from .fx_ranged import volley
    c, k = fx.c, fx.big
    cols = (c.deep, c.light if fx.type not in ("GHOST", "DARK") else c.dark, WHITE)

    def one(p, x, y, ang, j, v, ms):
        r = 22 * k
        wob = ang + 0.35 * sin(ms * 0.03 + j)
        cx, cy = x - cos(wob) * r, y - sin(wob) * r
        for q in (2, 1):                                    # 잔상
            K.crescent(p, cx - cos(wob) * 9 * q, cy - sin(wob) * 9 * q, r, wob, 1.9, (4.5 - q) * k, cols[0])
        K.crescent(p, cx, cy, r + 2, wob, 2.2, 10 * k, cols[0])
        K.crescent(p, cx, cy, r, wob, 2.2, 8 * k, cols[1])
        K.crescent(p, cx, cy, r - 1, wob, 2.2, 3.5 * k, cols[2])
    end = volley(fx, 0, 3, one, gap=110, life=240, spread=11, hit=0.7)
    fx.show.rebase()
    e2 = sweep(fx, end - 60)
    K.impact(fx, e2 - 110, size=1.15)


def claw(fx):
    """발톱. 닿는 기술이면 달려들어 할퀸다."""
    def go():
        end = rips(fx, 0)
        K.impact(fx, end - 90, size=1.1)
    if contact(fx):
        K.rush(fx, go)
    else:
        go()


def bite(fx):
    """물기: 위아래 이빨이 가운데로 닫히며 맞물린다 - 다 닫힌 채 한 박자 머물고 터진다.

    이빨의 자리와 수는 battle_fx.fang_rows 가 정한다 (윗니 넷 · 아랫니 셋이 과녁 가운데에서 맞물린다 - 예전에
    대각선으로 보인다는 제보를 받고 고친 모양이라 client/test_gym_ui.py 가 다 닫힌 순간을 찍어 본다). 그래서 다 닫힌
    이빨은 장마다 지우는 붓이 아니라 연출이 쥐고 있는 도형(fx.add)으로 그리고, 그 박자에는 다른 다각형을 안 그린다.
    """
    sh, c, k = fx.show, fx.c, fx.big
    tx, ty = fx.dst
    steps = FX.FANG_OPEN
    T = FX.FANG_STEP_MS * (len(steps) - 1) + 40
    rim = c.deep
    tooth = c.hot if fx.type not in ("GHOST", "DARK") else c.light

    def strike():
        def jaws(p, u, ms):
            i = min(len(steps) - 2, int(ms / FX.FANG_STEP_MS))
            gap = steps[i] - (steps[i] - steps[i + 1]) * ((ms % FX.FANG_STEP_MS) / float(FX.FANG_STEP_MS))
            if ms >= FX.FANG_STEP_MS * (len(steps) - 1):
                gap = 0
            up, lo = FX.fang_rows(tx, ty, gap)
            w = (FX.FANG_TEETH - 1) * FX.FANG_GAP / 2.0 + 12
            for sg, rows in ((-1, up), (1, lo)):            # 잇몸 (타입 색 반달) - 이빨 뒤에 깔린다
                base = rows[0][1]
                p.poly([tx - w, base, tx - w * 0.6, base + sg * 12, tx, base + sg * 16, tx + w * 0.6, base + sg * 12,
                        tx + w, base, tx, base - sg * 5], c.dark, rim, 1, True)
            for pts in up + lo:
                p.poly(list(pts), tooth, rim, 2)
        sh.act(0, T, jaws)

        def shut():                                         # 다 닫혔다 - 이 모습을 쥐고 한 박자 머문다
            up, lo = FX.fang_rows(tx, ty, 0)
            for pts in up + lo:
                fx.add(fx.cv.create_polygon(*pts, fill=tooth, outline=rim, width=2))
        sh.cue(T, shut)

        def snap(p, u, ms):                                 # 맞물린 순간의 떨림 (선만 쓴다)
            for sg in (-1, 1):
                x = tx + sg * (44 + 10 * u)
                p.line([x, ty - 9, x + sg * 7, ty, x, ty + 9], WHITE, 2)
            p.line([tx - 30, ty, tx + 30, ty], WHITE, max(1, int(3 * (1 - u))))
        sh.act(T, FX.FANG_HOLD_MS, snap)
        # (물린 채 머무는 동안에는 도트를 밀지 않는다 - 이빨은 과녁 가운데에 물려 있어야 한다. 밀리는 것은 터질 때다)
        sh.cue(T + FX.FANG_HOLD_MS, fx.burst)
    K.rush(fx, strike)


def punch(fx):
    """주먹: 달려들어 주먹을 꽂는다. 주먹은 타입의 기운을 두르고, 뒤로 잔상과 속도선이 길게 남는다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    ca, sa = cos(g.ang), sin(g.ang)
    paint = K.mote(fx.type)

    def rot(x, y, dx, dy):
        return [x + dx * ca - dy * sa, y + dx * sa + dy * ca]

    def fist(p, x, y, r, fill, edge):
        pts = []
        for dx, dy in ((-1, -1), (0, -1.08), (1, -1), (1.12, 0), (1, 1), (0, 1.08), (-1, 1), (-1.05, 0)):
            pts += rot(x, y, dx * r, dy * r)
        p.poly(pts, fill, edge, 2, True)

    def strike():
        def draw(p, u, ms):
            back = 34 * (1 - K.out3(min(1.0, u / 0.6)))
            x, y = g.tx - g.ux * back, g.ty - g.uy * back
            r = (13 + 5 * K.out2(u)) * k
            for off in (-15, -7.5, 0, 7.5, 15):             # 뒤로 길게 뻗는 속도선
                a_, b_ = rot(x, y, -r - 46 + abs(off), off), rot(x, y, -r - 2, off)
                K.streak(p, a_[0], a_[1], b_[0], b_[1], 2.4 if off == 0 else 1.7, WHITE if off == 0 else c.light)
            for q, sc in ((2, 0.6), (1, 0.8)):              # 잔상
                fist(p, x - g.ux * r * 1.15 * q, y - g.uy * r * 1.15 * q, r * sc, c.dark, "")
            K.burst_star(p, x, y, r * 1.75, 8, c.deep, 4, inner=0.66, rot=ms * 0.02)      # 두른 기운
            fist(p, x, y, r, c.light if fx.type not in ("GHOST", "DARK") else c.base, c.deep)
            for off in (-0.45, 0.0, 0.45):                  # 손가락 마디
                a_, b_ = rot(x, y, r * 0.35, off * r), rot(x, y, r * 0.98, off * r)
                p.line(a_ + b_, c.deep, 2)
            for j in range(3):
                paint(p, x - g.ux * (r + 6 + j * 9) + g.px * (j - 1) * 9, y - g.uy * (r + 6 + j * 9) + g.py * (j - 1) * 9,
                      5 * k, ms * 0.02 + j, 1 - u * 0.5, j)
        end = sh.act(0, 130, draw)
        K.impact(fx, end - 50, size=1.2)
    K.rush(fx, strike)


def kick(fx):
    """발차기: 달려들어 크게 돌려 찬다."""
    def strike():
        end = sweep(fx, 0, mirror=True, thick=24, span=2.1, r=50)
        speedlines(fx, 0, 120)
        K.impact(fx, end - 110, size=1.15)
    K.rush(fx, strike)


def stab(fx):
    """찌르기: 뾰족한 것이 나선을 감으며 과녁을 꿰뚫고 들어가, 끝이 뒤로 삐져나온다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big

    def thrust():
        def draw(p, u, ms):
            tip = -30 + 46 * K.out3(min(1.0, u / 0.5))
            x, y = g.tx + g.ux * (tip - 30 * k), g.ty + g.uy * (tip - 30 * k)
            for off in (-12, 0, 12):                        # 뒤로 뻗는 속도선
                K.streak(p, x - g.ux * 58 + g.px * off, y - g.uy * 58 + g.py * off, x - g.ux * 8 + g.px * off,
                         y - g.uy * 8 + g.py * off, 1.8, WHITE if off == 0 else c.light)
            hp = []                                         # 자루를 감는 드릴 나선
            for q in range(9):
                v = q / 8.0
                off = sin(v * 12 + ms * 0.07) * 7.5 * k
                hp += [x - g.ux * (8 + 42 * v) + g.px * off, y - g.uy * (8 + 42 * v) + g.py * off]
            p.line(hp, c.base, 2, smooth=True)
            K.shard(p, x, y, 26 * k, g.ang, c.deep, slim=0.5)
            K.shard(p, x, y, 23 * k, g.ang, c.light, c.dark)
            K.shard(p, x, y, 10 * k, g.ang, WHITE)
            if u > 0.45:                                    # 꿰뚫은 끝
                ex, ey = g.tx + g.ux * 26 * k, g.ty + g.uy * 26 * k
                K.shard(p, ex, ey, 12 * k * (1 - (u - 0.45)), g.ang, WHITE, c.light)
        end = sh.act(0, 170, draw)
        K.impact(fx, end - 90, size=1.15)
    if contact(fx):
        K.rush(fx, thrust)
    else:
        thrust()


def hammer(fx):
    """해머: 큰 망치를 뒤로 젖혔다가 내리찍는다. 찍힌 자리에서 땅이 울린다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    f = g.face
    px, py = g.tx - f * 44, g.ty + 22
    L = 54 * k
    T = 320

    def swing(ms):                                          # 도: 0 = 맞는 쪽 수평, 음수 = 위
        if ms < 150:
            return -75 - 50 * K.out2(ms / 150.0)
        return -125 + 105 * K.in3(min(1.0, (ms - 150) / 90.0))

    def draw(p, u, ms):
        a = math.radians(swing(ms))
        dx, dy = f * cos(a), sin(a)
        nx, ny = -dy, dx
        hx, hy = px + dx * L, py + dy * L
        if 150 <= ms <= 260:                                # 휘두른 자리
            a0 = math.radians(swing(150))
            K.crescent(p, px, py, L, 0, 0, 12 * k, c.light, a0=math.atan2(sin(a0), f * cos(a0)),
                       a1=math.atan2(dy, dx))
        p.line([px, py, hx, hy], "#3a2812", 7)
        p.line([px, py, hx, hy], "#8a6238", 4)
        hw, hl = 10 * k, 19 * k
        pts = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            pts += [hx + dx * hw * su + nx * hl * sv, hy + dy * hw * su + ny * hl * sv]
        p.poly(pts, c.dark, c.deep, 2)
        p.poly([pts[0], pts[1], pts[2], pts[3], hx + dx * hw * 0.2 - nx * hl * 0.2, hy + dy * hw * 0.2 - ny * hl * 0.2,
                hx - dx * hw * 0.6 - nx * hl * 0.2, hy - dy * hw * 0.6 - ny * hl * 0.2], c.light)
        if ms > 240:
            v = (ms - 240) / 80.0
            p.oval(g.tx, g.gt, (16 + 50 * v) * k, (4 + 9 * v) * k, "", c.light, max(1, int(5 * (1 - v))))
    sh.act(0, T, draw)
    K.shake(fx, 240, 160, amp=2.6, vertical=True)
    K.impact(fx, 235, size=1.45)


def whip(fx):
    """채찍: 덩굴이 휘며 뻗어 나가 끝으로 찰싹 내리치고 돌아온다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    T = 420

    def draw(p, u, ms):
        ext = K.out2(min(1.0, ms / 170.0)) if ms < 250 else max(0.0, 1.0 - (ms - 250) / 170.0)
        if ext < 0.04:
            return
        bend = -48 * cos(ms * 0.021) * g.face
        pts = []
        for s in range(10):
            v = s / 9.0 * ext
            pts += list(g.at(v, bend * sin(math.pi * s / 9.0) * (0.3 + 0.7 * (1 - ext))))
        ws = [4.5 * k * (1 - 0.7 * s / 9.0) for s in range(10)]
        K.ribbon(p, pts, [w * 1.5 for w in ws], c.deep)
        K.ribbon(p, pts, ws, c.base)
        K.ribbon(p, pts, [w * 0.4 for w in ws], c.light)
        for s in (3, 6):                                    # 잎
            K.leaf(p, pts[s * 2], pts[s * 2 + 1] - 5, 5.5 * k, g.ang - 0.9, c.light, c.deep)
        if 150 < ms < 230:                                  # 끝이 찰싹
            K.glint(p, g.tx, g.ty, 24 * k * (1 - (ms - 150) / 80.0) + 4, WHITE)
    sh.act(0, T, draw)
    K.impact(fx, 165, size=1.15)


def multi(fx):
    """연속기: 닿는 기술은 달려들어 여러 번 때리고, 아니면 여러 발을 날린다 (물수리검은 표창)."""
    g = fx.geo
    if not contact(fx):
        from .fx_ranged import volley_multi
        return volley_multi(fx)

    def strike():
        n = 4
        for i in range(n):
            a = i * 2.2 + 0.6
            K.mini(fx, i * 78, g.tx + cos(a) * 17, g.ty + sin(a) * 14, 0.95)
        speedlines(fx, 0, n * 78)
        K.shake(fx, 0, n * 78, amp=1.8)
        K.impact(fx, n * 78 - 10, size=1.0)
    K.rush(fx, strike)


def recoil(fx):
    """몸을 던지는 기술: 타오르는 기운을 두르고 돌진해 크게 터지고, 나도 아프다."""
    sh, g, c, k = fx.show, fx.geo, fx.c, fx.big
    sx, sy = fx.src
    cols = (c.dark, c.light, c.hot)
    A = 250
    seed = random.randrange(1000)

    def aura(p, u, ms):
        grow = K.out2(min(1.0, ms / 160.0))
        K.burst_star(p, sx, sy, (36 + 4 * sin(ms * 0.05)) * k * grow, 12, c.deep, seed + int(ms / 60), inner=0.62,
                     rot=ms * 0.01)
        for j in range(7):
            ph = ms * 0.03 + j * 0.9
            r = (10 + 4 * sin(ms * 0.04 + j)) * k * grow
            K.flame(p, sx + cos(ph) * 21, sy + 14 + sin(ph) * 8 - r * 0.3, r, 4 * sin(ph), cols)
        K.ring(p, sx, sy, (34 - 20 * u) * k, c.light, 2, 0.8)
    sh.act(0, A, aura)

    def go():
        sh.rebase()

        def strike():
            m = K.Motes(seed)
            K.scatter(m, fx.type, 0, sx, sy, 5, 0.7)
            paint = K.mote(fx.type)
            sh.act(0, 420, lambda p, u, ms: m.draw(p, ms, paint))      # 반동
            end = (FLOURISH.get(fx.type) or _smash)(fx, 0)
            K.impact(fx, max(0, end - 80), size=1.45)
        K.rush(fx, strike)
    sh.cue(A, go)


STYLES = {
    "hit": hit, "flurry": flurry, "dash": dash, "phantom": phantom, "slash": slash, "blades": blades,
    "claw": claw, "bite": bite, "punch": punch, "kick": kick, "stab": stab, "hammer": hammer, "whip": whip,
    "multi": multi, "recoil": recoil,
}
