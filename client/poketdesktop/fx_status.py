# -*- coding: utf-8 -*-
"""변화기의 연출 — 때리지 않는다. 걸고, 두르고, 고친다.

공격기처럼 터지지 않게 한다: 맞는 순간(K.impact) 대신 조용히 내려앉고(K.settle), 맞은 쪽 도트도 밀지 않는다.
랭크가 오르면 따뜻한 빛의 화살표가 솟고 내리면 푸른 화살표가 가라앉는다 - 타입이 아니라 '무슨 일이 일어났나'
를 읽을 수 있어야 하는 기술들이라, 회복 · 랭크 · 상태이상의 색은 타입 색보다 그 뜻의 색을 먼저 쓴다.
"""
import math
import random

from . import fx_kit as K

WHITE = K.WHITE
TAU = K.TAU
cos, sin = math.cos, math.sin

UP = ("#7a2a06", "#ff8a3c", "#fff0b8")          # 랭크가 오른다 (테, 몸, 심)
DOWN = ("#10245e", "#4a82f0", "#d8ecff")        # 랭크가 내린다
HEAL = ("#135c33", "#58e08a", "#eafff0")        # 회복


# ---------------------------------------------------------------- 함께 쓰는 장면
def arrows(fx, at, x, y, up, cols, dur=560, n=3):
    """랭크 화살표: 갈매기 셋이 줄지어 솟거나 가라앉고, 몸 둘레로 빛줄기가 같은 쪽으로 흐른다."""
    k = 1.0
    seed = random.randrange(1000)
    d = -1 if up else 1

    def draw(p, u, ms):
        f = K.fade(u, 0.14, 0.72)
        if K.ras(p):
            p.glow(x, y, 30 * f, cols[1], 0.45 * f, 1.25)        # 몸을 감싸는 기운
        for j in range(8):                                  # 흐르는 빛줄기
            ph = (ms * 0.0022 + K.noise(seed + j)) % 1.0
            xx = x + (j - 3.5) * 8.5
            y0 = y + 26 * k - 62 * ph if up else y - 34 * k + 62 * ph
            K.streak(p, xx, y0, xx, y0 + d * 22 * (1 - ph * 0.5), 2.0 * f + 0.2, cols[1] if j % 2 else cols[2])
        K.ring(p, x, y + 24, (16 + 22 * ((ms * 0.003) % 1.0)) * f + 2, cols[1], max(1, int(3 * f)), 0.26)
        for j in range(n):                                  # 갈매기
            a = ms - j * 90
            if a < 0:
                continue
            slide = 34 * K.out2(min(1.0, a / 300.0))
            yy = y + (16 - slide - j * 2 if up else -22 + slide + j * 2)
            s = K.back(min(1.0, a / 140.0), 2.0) * (1.0 if u < 0.8 else max(0.0, (1 - u) / 0.2))
            if s <= 0.05:
                continue
            if K.ras(p):
                p.glow(x, yy - d * 2, 15 * s, cols[1], 0.85)
            else:
                K.chevron(p, x, yy, 15 * s, 12 * s, up, cols[0])
            K.chevron(p, x, yy, 12.5 * s, 10 * s, up, cols[1])
            K.chevron(p, x, yy + d * 1.5, 7 * s, 5.5 * s, up, cols[2])
        if up and 0.25 < u < 0.7:
            K.glint(p, x + 16, y - 20, 9 * K.hump((u - 0.25) / 0.45) + 2, WHITE)
    return fx.show.act(at, dur, draw)


def cast(fx, at, dur=200, typ=None):
    """쓰는 쪽에서 맞는 쪽으로 건너가는 기운 (누가 누구에게 거는지 보인다)."""
    g = fx.geo
    c = K.tone(typ or fx.type)
    cols = c.tri

    def draw(p, u, ms):
        for j in range(3):
            v = u * 1.4 - j * 0.16
            if 0.0 < v < 1.0:
                x, y = g.at(0.12 + 0.82 * v)
                r = 7 + 9 * v
                if K.ras(p):
                    K.glow_hoop(p, x, y, r * 0.4, r * 1.2, g.ang, cols[0], 7)
                else:
                    K.hoop(p, x, y, r * 0.4, r * 1.2, g.ang, cols[0], 4)
                K.hoop(p, x, y, r * 0.4, r * 1.2, g.ang, cols[1] if not c.edge else c.alt, 2)
        K.glint(p, g.sx + g.ux * 14, g.sy + g.uy * 14 - 8, 12 * K.hump(u) + 2, WHITE)
    return fx.show.act(at, dur, draw)


def swirl(fx, at, x, y, typ=None, dur=560, n=9):
    """몸을 감싸고 도는 타입의 기운: 고리가 돌며 오르고 조각이 나선으로 피어오른다."""
    c = K.tone(typ or fx.type)
    paint = K.mote(typ or fx.type)
    seeds = [random.uniform(0, TAU) for _ in range(n)]

    def draw(p, u, ms):
        f = K.fade(u, 0.15, 0.75)
        for j in range(3):                                  # 오르며 도는 고리
            ph = (ms * 0.0018 + j / 3.0) % 1.0
            rr = (26 - 8 * ph) * f + 2
            yy = y + 22 - 50 * ph
            if K.ras(p):
                K.glow_arc(p, x, yy, rr, rr * 0.32, (ms * 0.9 + j * 120) % 360, 200, c.base if not c.edge else c.alt, 7, 0.8)
            else:
                p.arc(x, yy, rr, rr * 0.32, (ms * 0.9 + j * 120) % 360, 200, c.deep if not c.edge else c.edge, 4)
            p.arc(x, yy, rr, rr * 0.32, (ms * 0.9 + j * 120 + 6) % 360, 185, c.light if not c.edge else c.alt, 2)
        for j in range(n):                                  # 나선으로 오르는 조각
            ph = (ms * 0.002 + j / float(n)) % 1.0
            a = seeds[j] + ph * 5.0
            paint(p, x + cos(a) * (22 - 8 * ph), y + 24 - 58 * ph + sin(a) * 5, 5.5 * f + 0.5, a, 1 - ph * 0.6, j)
        if u > 0.55:
            K.glint(p, x, y - 26, 16 * K.hump((u - 0.55) / 0.45) + 2, WHITE)
    return fx.show.act(at, dur, draw)


# ---------------------------------------------------------------- 랭크 · 회복
def buff(fx):
    """능력이 오른다: 따뜻한 빛줄기와 화살표가 솟는다."""
    arrows(fx, 0, fx.src[0], fx.src[1], True, UP)


def selfdown(fx):
    """내 능력이 내린다 (껍질깨기의 방어 ...): 푸른 화살표가 가라앉는다."""
    arrows(fx, 0, fx.src[0], fx.src[1], False, DOWN)


def debuff(fx):
    """상대의 능력을 내린다: 기운이 건너가고, 푸른 화살표가 가라앉는다."""
    end = cast(fx, 0)
    arrows(fx, end - 60, fx.dst[0], fx.dst[1], False, DOWN)


def heal(fx, at=0, where=None):
    """회복: 초록빛 고리가 발밑에서 머리 위로 훑어 오르고 '+' 가 피어오른다. 빛가루가 몸을 감싸고 돈다."""
    sh = fx.show
    x, y = where or fx.src
    seed = random.randrange(1000)
    T = 660

    def draw(p, u, ms):
        f = K.fade(u, 0.12, 0.75)
        if K.ras(p):
            p.glow(x, y, 32 * f, HEAL[1], 0.5 * f, 1.2)          # 몸을 감싸는 초록빛
        for j in range(3):                                  # 훑어 오르는 고리
            ph = (ms * 0.0019 + j / 3.0) % 1.0
            rr = (27 - 6 * ph) * f + 1
            yy = y + 24 - 56 * ph
            if K.ras(p):
                K.glow_hoop(p, x, yy, rr, rr * 0.3, 0.0, HEAL[1], (int(4 * (1 - ph) * f) + 2) * 2.0, 0.8)
            else:
                p.oval(x, yy, rr, rr * 0.3, "", HEAL[0], int(4 * (1 - ph) * f) + 2)
            p.oval(x, yy, rr, rr * 0.3, "", HEAL[1] if j % 2 else HEAL[2], max(1, int(3 * (1 - ph) * f)))
        for j in range(6):                                  # 피어오르는 '+'
            ph = (ms * 0.0016 + K.noise(seed + j)) % 1.0
            xx = x + (K.noise(seed + j * 3) - 0.5) * 56
            yy = y + 22 - 60 * ph
            s_ = (6 + 4 * K.noise(seed + j * 7)) * K.hump(ph) * f
            if s_ > 1.5 and K.ras(p):
                p.glow(xx, yy, s_ * 1.9, HEAL[1], 0.8)
            elif s_ > 1.5:
                K.plus(p, xx, yy, s_ + 1.8, HEAL[0])
            if s_ > 1.5:
                K.plus(p, xx, yy, s_, HEAL[1] if j % 2 else HEAL[2])
        for j in range(4):
            a = ms * 0.008 + j * TAU / 4
            K.glint(p, x + cos(a) * 26, y + sin(a) * 17 - 6, (6 + 3 * sin(ms * 0.02 + j)) * f + 1, WHITE)
    return sh.act(at, T, draw)


def heal_style(fx):
    """회복기: 내 몸을 고치면 내 몸에서, 상대를 고치면(치유파동) 기운이 건너가 그쪽에서 피어오른다."""
    if (fx.move.get("target") or 10) in (7, 5, 3, 13, 15, 4) or fx.move.get("statSelf"):
        return heal(fx)
    end = cast(fx, 0, typ="GRASS")
    heal(fx, end - 60, fx.dst)


def roost(fx):
    """날개쉬기: 깃털이 살랑살랑 내려앉고 기운이 돌아온다."""
    x, y = fx.src
    m = K.Motes(random.randrange(1000))
    for j in range(9):
        m.add(j * 40, 520, x + random.uniform(-30, 30), y - 46, random.uniform(-10, 10), 58, 0,
              random.uniform(5, 7.5), random.uniform(0, TAU), random.uniform(-3, 3))
    paint = K.mote("FLYING")
    fx.show.act(0, 700, lambda p, u, ms: m.draw(p, ms, paint), z=2)
    heal(fx)


# ---------------------------------------------------------------- 상태이상
def _ail_poison(fx, at, x, y):
    c = K.tone("POISON")
    seed = random.randrange(1000)

    def draw(p, u, ms):
        f = K.fade(u, 0.12, 0.8)
        for j in range(7):
            ph = (ms * 0.002 + K.noise(seed + j)) % 1.0
            xx = x + (K.noise(seed + j * 5) - 0.5) * 46 + 3 * sin(ms * 0.02 + j)
            r = (4.5 + 4.5 * K.noise(seed + j * 9)) * f * (1 - ph * 0.4)
            if r > 1:
                p.oval(xx, y + 20 - 50 * ph, r, r, c.light if j % 3 else c.alt, c.deep, 2)
                p.oval(xx - r * 0.3, y + 20 - 50 * ph - r * 0.3, r * 0.3, r * 0.3, c.hot)
        K.blob(p, x, y + 22, 24 * f + 1, c.dark, seed, ms * 0.01, n=9, jag=0.2, sy=0.3, outline=c.alt, width=2)
    return fx.show.act(at, 560, draw)


def _ail_burn(fx, at, x, y):
    c = K.tone("FIRE")
    seed = random.randrange(1000)
    cols = (c.dark, c.light, c.hot)

    def draw(p, u, ms):
        f = K.fade(u, 0.15, 0.75)
        for j in range(5):
            r = (10 + 4 * sin(ms * 0.035 + j * 2.1)) * f * (1.15 - abs(j - 2) * 0.14)
            if r > 2:
                K.flame(p, x + (j - 2) * 11, y + 20 - r * 0.4, r, K.snoise(seed + j + int(ms / 50)) * 4, cols)
        for j in range(4):
            ph = (ms * 0.0024 + j * 0.25) % 1.0
            K.glint(p, x + (K.noise(seed + j) - 0.5) * 40, y + 6 - 44 * ph, 5 * (1 - ph) * f + 1, c.hot)
    return fx.show.act(at, 540, draw)


def _ail_para(fx, at, x, y):
    c = K.tone("ELECTRIC")
    seed = random.randrange(1000)
    cols = (c.dark, c.base, c.hot)

    def draw(p, u, ms):
        if int(ms / 45) % 3 == 2:
            return
        rnd = random.Random(seed + int(ms / 45))
        for _j in range(4):
            a = rnd.uniform(0, TAU)
            r0, r1 = rnd.uniform(8, 16), rnd.uniform(24, 36)
            K.bolt(p, K.zigzag(x + cos(a) * r0, y + sin(a) * r0, x + cos(a + 0.6) * r1, y + sin(a + 0.6) * r1 * 0.9, 5,
                               4, rnd), 1, cols)
        K.arcs(p, x, y, 26, c.light, 2, ms * 1.6, 3, 50, 0.85)
    K.shake(fx, at + 60, 420, amp=1.6)
    return fx.show.act(at, 520, draw)


def _ail_sleep(fx, at, x, y):
    c = K.tone("PSYCHIC")

    def draw(p, u, ms):
        for j in range(3):
            a = ms - j * 150
            if a < 0:
                continue
            ph = min(1.0, a / 460.0)
            s = (5 + j * 2.6) * K.fade(ph, 0.2, 0.75)
            if s > 1:                                       # (머리 위 옆으로 비스듬히 - 화면 위쪽에 선 상대도 잘리지 않게)
                K.zee(p, x + 16 + j * 13 + 3 * sin(ms * 0.01 + j), max(8.0, y - 12 - j * 9 - 12 * ph), s,
                      WHITE if j % 2 else "#c8d8ff", c.deep)
        K.ring(p, x, y, 22 + 6 * sin(ms * 0.01), "#9fb0e8", 1, 0.8)
    return fx.show.act(at, 760, draw)


def _ail_confuse(fx, at, x, y):
    c = K.tone("FAIRY")

    def draw(p, u, ms):
        f = K.fade(u, 0.12, 0.8)
        cy = y - 30
        p.arc(x, cy, 24, 7.5, (ms * 0.5) % 360, 300, c.dark, 2)
        for j in range(3):
            a = ms * 0.012 + j * TAU / 3
            back_ = sin(a) < 0
            if K.ras(p):
                p.glow(x + cos(a) * 24, cy + sin(a) * 7.5, 8 * f + 1, c.alt, 0.7)
            K.star(p, x + cos(a) * 24, cy + sin(a) * 7.5, (6.5 if not back_ else 5) * f + 1, c.alt, c.deep, ms * 0.01)
        for j in range(2):                                  # 어질어질한 소용돌이
            rr = (10 + j * 7) * f
            p.arc(x, y - 4, rr, rr * 0.8, (-ms * 0.9 + j * 180) % 360, 220, "#d8c8ff" if j else WHITE, 2)
    return fx.show.act(at, 640, draw)


def _ail_freeze(fx, at, x, y):
    c = K.tone("ICE")
    seed = random.randrange(1000)

    def draw(p, u, ms):
        f = K.back(min(1.0, u / 0.35), 1.5) * (1.0 if u < 0.8 else (1 - u) / 0.2)
        for j in range(8):
            a = j * math.pi / 4 + 0.2
            K.spike(p, x + cos(a) * 19, y + sin(a) * 15, 4.2, (9 + 13 * K.noise(seed + j)) * f, a,
                    c.light if j % 2 else WHITE, c.dark)
        if u < 0.5:
            K.glint(p, x, y - 4, 20 * (1 - u * 2) + 2, WHITE)
    return fx.show.act(at, 520, draw)


def _ail_bind(fx, at, x, y):
    c = fx.c

    def draw(p, u, ms):
        sq = K.out2(min(1.0, u / 0.5))
        thin = 1.0 if u < 0.8 else (1 - u) / 0.2
        for j in range(3):
            rr = (40 - 18 * sq) - j * 2
            yy = y - 12 + j * 12
            if K.ras(p):
                K.glow_arc(p, x, yy, rr, rr * 0.3, (ms * 0.8 + j * 90) % 360, 300, c.base if not c.edge else c.alt,
                           (int(5 * thin) + 1) * 1.8, 0.8)
            else:
                p.arc(x, yy, rr, rr * 0.3, (ms * 0.8 + j * 90) % 360, 300, c.deep, int(5 * thin) + 1)
            p.arc(x, yy, rr, rr * 0.3, (ms * 0.8 + j * 90 + 6) % 360, 285, c.light if not c.edge else c.alt,
                  max(1, int(3 * thin)))
    return fx.show.act(at, 520, draw)


def _ail_seed(fx, at, x, y):
    c = K.tone("GRASS")

    def draw(p, u, ms):
        f = K.out2(min(1.0, u / 0.5)) * (1.0 if u < 0.85 else (1 - u) / 0.15)
        for sg in (-1, 1):                                  # 감아 오르는 덩굴
            pts = []
            for q in range(8):
                v = q / 7.0 * f
                pts += [x + sg * (20 - 16 * v) * cos(v * 5), y + 22 - 46 * v]
            p.line(pts, c.deep, 4, smooth=True)
            p.line(pts, c.base, 2, smooth=True)
            if len(pts) >= 4:
                K.leaf(p, pts[-2], pts[-1], 6 * f + 1, -math.pi / 2 + sg * 0.6, c.light, c.deep)
        for j in range(3):
            p.oval(x + (j - 1) * 12, y + 22, 3.2, 2.4, c.alt, c.deep, 1)
    return fx.show.act(at, 560, draw)


def _ail_love(fx, at, x, y):
    c = K.tone("FAIRY")
    seed = random.randrange(1000)

    def draw(p, u, ms):
        f = K.fade(u, 0.15, 0.8)
        for j in range(5):
            ph = (ms * 0.0018 + K.noise(seed + j)) % 1.0
            s = (5 + 4 * K.noise(seed + j * 3)) * K.hump(ph) * f
            if s > 1:
                K.heart(p, x + (K.noise(seed + j * 7) - 0.5) * 48 + 4 * sin(ms * 0.01 + j), y + 14 - 50 * ph, s,
                        c.base if j % 2 else "#ff5a8a", c.deep)
    return fx.show.act(at, 600, draw)


def _ail_curse(fx, at, x, y):
    """그 밖의 것: 발밑에 문양이 돌고 타입의 기운이 몸으로 스며든다."""
    c = fx.c
    paint = K.mote(fx.type)
    seeds = [random.uniform(0, TAU) for _ in range(8)]
    line = c.light if not c.edge else c.alt

    def draw(p, u, ms):
        f = K.fade(u, 0.15, 0.75)
        if K.ras(p):
            p.glow(x, y + 22, 34 * f + 1, c.dark if not c.edge else c.alt, 0.8, 0.3)
        else:
            K.sigil(p, x, y + 22, 30 * f + 1, ms * 0.006, c.deep, 4, 0.3)
        K.sigil(p, x, y + 22, 30 * f + 1, ms * 0.006, line, 2, 0.3)
        for j in range(8):
            ph = (ms * 0.0022 + j / 8.0) % 1.0
            rr = 40 * (1 - K.in2(ph))
            paint(p, x + cos(seeds[j]) * rr, y + sin(seeds[j]) * rr * 0.8, 5 * f + 0.5, seeds[j], 1 - ph * 0.5, j)
        K.ring(p, x, y, (36 - 22 * ((ms * 0.003) % 1.0)) * f + 2, line, 2, 0.8)
    return fx.show.act(at, 540, draw)


AILMENT = {
    "poison": _ail_poison, "burn": _ail_burn, "paralysis": _ail_para, "sleep": _ail_sleep, "yawn": _ail_sleep,
    "confusion": _ail_confuse, "freeze": _ail_freeze, "trap": _ail_bind, "leech-seed": _ail_seed,
    "infatuation": _ail_love, "nightmare": _ail_sleep, "disable": _ail_bind,
}


def outcome(fx, at):
    """변화기가 닿은 뒤의 모습 - 무슨 일이 일어났나를 보여 준다. 끝나는 시각을 돌려준다.

    걸리는 상태이상이 있으면 그것(독 · 화상 · 마비 · 잠 ...), 랭크가 바뀌면 화살표(오르면 따뜻한 빛, 내리면 푸른 빛 -
    내 것이면 내 몸에, 상대 것이면 상대 몸에), 회복이면 초록빛. 아무것도 아니면 조용히 내려앉는다.
    소리 · 가루 · 바람처럼 '전하는 법' 만 그리는 연출들이 끝에 이것을 부른다 (K.impact 가 변화기면 이리로 돌린다).
    """
    mv = fx.move
    tx, ty = fx.dst
    ail = mv.get("ail")
    if ail in AILMENT:
        return AILMENT[ail](fx, at, tx, ty)
    stats = mv.get("stat") or []
    if stats:
        up = any(v > 0 for _s, v in stats)
        x, y = fx.src if mv.get("statSelf") else fx.dst
        return arrows(fx, at, x, y, up, UP if up else DOWN)
    if (mv.get("heal") or 0) > 0:
        return heal(fx, at, fx.src if mv.get("statSelf", True) and (mv.get("target") or 10) in (7, 5, 3, 13, 15, 4)
                    else fx.dst)
    if fx.miss or fx.immune:
        return K.settle(fx, at, tx, ty, 0.7)
    if ail:
        return _ail_curse(fx, at, tx, ty)
    return K.settle(fx, at, tx, ty)


K.STATUS_HOOK = outcome


def hex_(fx):
    """상대에게 거는 변화기: 기운이 건너가고, 걸리는 것에 맞는 모습이 맞는 쪽을 덮는다 (독 · 화상 · 마비 · 잠 ...)."""
    end = cast(fx, 0)
    mv = fx.move
    if mv.get("ail") in AILMENT or mv.get("stat") or (mv.get("heal") or 0) > 0:
        outcome(fx, end - 60)
    else:
        _ail_curse(fx, end - 60, fx.dst[0], fx.dst[1])


def wisp(fx):
    """도깨비불: 푸른 불 셋이 몸 둘레를 돌다가 일렁이며 건너가 달라붙는다."""
    sh, g = fx.show, fx.geo
    cols = ("#1c2a7a", "#5a8cff", "#e6f4ff")
    A, T = 240, 300

    def draw(p, u, ms):
        for j in range(3):
            if ms < A:
                a = ms * 0.014 + j * TAU / 3
                x, y = g.sx + cos(a) * 24, g.sy + sin(a) * 12 - 6
            else:
                v = K.inout(K.clamp((ms - A - j * 40) / float(T)))
                x, y = g.at(v, sin(v * 9 + j * 2) * 14 * K.hump(v))
                y -= 14 * K.hump(v)
            if K.ras(p):
                p.glow(x, y - 3, 15, "#3d6cff", 0.9)
            K.flame(p, x, y, 8.5 + 1.5 * sin(ms * 0.04 + j), K.snoise(j + int(ms / 45)) * 4, cols)
    sh.act(0, A + T + 80, draw)
    _ail_burn(fx, A + T, fx.dst[0], fx.dst[1])


def self_(fx):
    """자기에게 쓰는 변화기: 타입의 기운이 몸을 감싸고 돈다. 랭크가 바뀌거나 회복하면 그 모습이 뒤따른다."""
    end = swirl(fx, 0, fx.src[0], fx.src[1])
    mv = fx.move
    if (mv.get("cat") or "status") == "status" and (mv.get("stat") or (mv.get("heal") or 0) > 0):
        outcome(fx, end - 200)


# ---------------------------------------------------------------- 지키는 기술
def shield(fx):
    """방어: 몸 앞에 벌집 무늬 방패가 툭 튀어나와 펼쳐지고, 빛이 한 번 훑고 지나간다."""
    sh, g = fx.show, fx.geo
    rim, light, hot = "#0d5c50", "#48dcc0", "#d8fff6"
    cx, cy = g.mouth(22)
    T = 560

    def hexa(r, ox=0.0, oy=0.0):
        pts = []
        for q in range(6):
            a = math.pi / 6 + q * math.pi / 3
            pts += [cx + ox + cos(a) * r, cy + oy + sin(a) * r]
        return pts

    def draw(p, u, ms):
        s = K.back(min(1.0, ms / 150.0), 2.4) * (1.0 if ms < T - 120 else max(0.0, (T - ms) / 120.0))
        if s <= 0.03:
            return
        r = 31 * s * (1 + 0.03 * sin(ms * 0.03))
        if K.ras(p):
            p.glow_line(hexa(r + 2) + hexa(r + 2)[:2], light, 9, 0.75)
            if ms < 200:
                p.glow(cx, cy, r * 1.3, light, 0.8 * (1 - ms / 200.0))      # 튀어나오는 순간
        else:
            p.poly(hexa(r + 3), "", rim, 6)
        p.poly(hexa(r), "", light, 3)
        cell = r * 0.36                                     # 벌집
        for ox, oy in ((0, 0), (0, -2), (0, 2), (1.73, -1), (1.73, 1), (-1.73, -1), (-1.73, 1)):
            p.poly(hexa(cell * 0.92, ox * cell * 0.9, oy * cell * 0.9), "", light if (ox or oy) else hot, 1)
        if 140 < ms < 360:                                  # 훑고 지나가는 빛
            x = cx - r + 2 * r * (ms - 140) / 220.0
            K.streak(p, x - 8, cy + r * 0.7, x + 8, cy - r * 0.7, 3.5, WHITE)
        if ms < 260:
            K.ring(p, cx, cy, r + 30 * (ms / 260.0), light, max(1, int(4 * (1 - ms / 260.0))))
            K.glint(p, cx + r * 0.5, cy - r * 0.55, 15 * (1 - ms / 260.0) + 2, WHITE)
    sh.act(0, T, draw)


def wall(fx):
    """리플렉터 · 빛의장막: 몸 앞에 빛나는 판이 서고, 빛줄이 판을 타고 오른다."""
    sh, g = fx.show, fx.geo
    key = K.key_of(fx.move)
    rim, light, hot = (("#1a3f8a", "#7ab0ff", "#e6f1ff") if "reflect" in key else
                       ("#8a6200", "#ffd24a", "#fff8d8") if "lightscreen" in key else
                       ("#3d2a8a", "#a898ff", "#f1ecff") if "aurora" in key else ("#17633a", "#70dc98", "#eafff0"))
    cx, cy = g.mouth(24)
    T = 580

    def draw(p, u, ms):
        grow = K.back(min(1.0, ms / 170.0), 1.8) * (1.0 if ms < T - 120 else max(0.0, (T - ms) / 120.0))
        if grow <= 0.03:
            return
        hh, ww = 36 * grow, 10
        sk = 7 * g.face                                     # 비스듬히 선 판
        pts = [cx - ww + sk, cy - hh, cx + ww + sk, cy - hh + 5, cx + ww - sk, cy + hh, cx - ww - sk, cy + hh - 5]
        if K.ras(p):
            p.glow_line(pts + pts[:2], light, 9, 0.75)
        else:
            p.poly(pts, "", rim, 6)
        p.poly(pts, "", light, 3)
        for j in range(4):                                  # 판을 타고 오르는 빛
            v = ((ms * 0.0016 + j * 0.25) % 1.0) * 2 - 1
            y = cy - hh * v * 0.86
            p.line([cx - ww * 0.75 - sk * v * 0.8, y + 4, cx + ww * 0.75 - sk * v * 0.8, y - 4],
                   hot if j == 0 else light, 2)
        if ms < 280:
            K.glint(p, cx + sk, cy - hh, 16 * (1 - ms / 280.0) + 2, WHITE)
            K.ring(p, cx, cy, (20 + 30 * ms / 280.0), light, max(1, int(3 * (1 - ms / 280.0))), 1.3)
    sh.act(0, T, draw)


# ---------------------------------------------------------------- 가루 · 춤 · 잠
POWDER = {"sleep": ("#2e7a4a", "#8fe8b0", "#eafff0"), "stun": ("#8a6a00", "#ffe04a", "#fffbd0"),
          "poison": ("#4a1a78", "#c070f0", "#f6e2ff"), "spore": ("#7a5a1a", "#f0c070", "#fff4d8"),
          "rage": ("#7a1a1a", "#ff6a5a", "#ffe6e0"), "cotton": ("#6a7a8a", "#f2f6fa", "#ffffff")}


def powder(fx):
    """가루: 가루 구름이 살랑살랑 건너가 머리 위에서 흩뿌려져 내려앉는다."""
    sh, g = fx.show, fx.geo
    key = K.key_of(fx.move)
    cols = next((v for w, v in POWDER.items() if w in key), None) or fx.c.tri
    n, life, T = 26, 420, 700
    seeds = [(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(0, TAU), random.uniform(2.6, 5.0))
             for _ in range(n)]
    gap = (T - life) / float(n - 1)

    def draw(p, u, ms):
        for j in range(n):
            a = ms - j * gap
            if a < 0 or a >= life:
                continue
            v = a / float(life)
            sx_, sy_, ph, r = seeds[j]
            d = K.out2(min(1.0, v / 0.55))
            x = g.sx + (g.tx - g.sx) * d + sx_ * 20 * d + 4 * sin(a * 0.012 + ph)
            y = g.sy + (g.ty - 30 - g.sy) * d + sy_ * 9 * d - 14 * K.hump(min(1.0, v / 0.55))
            if v > 0.55:                                    # 내려앉는다
                y += 44 * K.in2((v - 0.55) / 0.45)
            rr = r * (1.0 if v < 0.8 else (1 - v) / 0.2 + 0.2)
            p.oval(x, y, rr, rr, cols[1] if j % 3 else cols[2], cols[0], 1)
            if j % 5 == 0:
                K.glint(p, x, y, rr * 2.4, cols[2])
    sh.act(0, T, draw)
    if (fx.move.get("cat") or "status") == "status":
        outcome(fx, T - 160)
    else:
        K.impact(fx, T - 140, size=1.0)


def dance(fx):
    """춤: 자기 둘레를 돈다. 칼춤은 칼 넷이 돌다가 머리 위에서 엇갈리며 번쩍이고, 나머지는 별과 발자국 고리."""
    sh, c = fx.show, fx.c
    sx, sy = fx.src
    key = K.key_of(fx.move)
    sword = "sword" in key or "blade" in key
    T = 600
    paint = K.mote(fx.type)

    def blade(p, x, y, a, s):
        ca, sa = cos(a), sin(a)
        K.streak(p, x - ca * 5 * s, y - sa * 5 * s, x + ca * 19 * s, y + sa * 19 * s, 3.6 * s, "#39485a")
        K.streak(p, x - ca * 4 * s, y - sa * 4 * s, x + ca * 18 * s, y + sa * 18 * s, 2.4 * s, "#e8f0ff")
        p.line([x - sa * 6 * s - ca * 3 * s, y + ca * 6 * s - sa * 3 * s, x + sa * 6 * s - ca * 3 * s,
                y - ca * 6 * s - sa * 3 * s], "#ffd447", max(2, 3 * s))
        p.line([x - ca * 3 * s, y - sa * 3 * s, x - ca * 9 * s, y - sa * 9 * s], "#8a6238", max(2, 3 * s))

    def draw(p, u, ms):
        f = K.fade(u, 0.12, 0.85)
        for j in range(2):                                  # 발밑의 고리
            ph = (ms * 0.003 + j * 0.5) % 1.0
            K.ring(p, sx, sy + 24, 10 + 30 * ph, c.light if not c.edge else c.alt, max(1, int(3 * (1 - ph))), 0.26)
        n = 4 if sword else 5
        close = K.in2(K.clamp((u - 0.6) / 0.25)) if sword else 0.0
        for j in range(n):
            a = ms * 0.012 + j * TAU / n
            rx, ry = 32 * (1 - close), 12 * (1 - close)
            x, y = sx + cos(a) * rx, sy - 26 * (0.4 + 0.6 * close) + sin(a) * ry
            if sword:
                blade(p, x, y, -math.pi / 2 + (0.5 * cos(a)) * (1 - close) + (j - 1.5) * 0.5 * close, f * 1.1)
            else:
                paint(p, x, y, 8 * f + 0.5, a, 1.0, j)
                K.streak(p, x - cos(a + 1.57) * 10, y - sin(a + 1.57) * 4, x, y, 1.6, c.light)
        if sword and u > 0.82:
            K.glint(p, sx, sy - 30, 26 * K.hump((u - 0.82) / 0.18) + 3, WHITE)
    sh.act(0, T, draw)
    stats = fx.move.get("stat") or []
    if stats and fx.move.get("statSelf") and (fx.move.get("cat") or "status") == "status":
        up = any(v > 0 for _s, v in stats)
        arrows(fx, T - 180, sx, sy, up, UP if up else DOWN, dur=460)
    elif (fx.move.get("cat") or "status") != "status":
        K.impact(fx, T - 120, size=1.15)


def sleepz(fx):
    """잠: 잠자기는 내 머리 위로 Z 가 떠오르고, 최면술 · 하품은 물결이 건너가 상대 머리 위에 Z 가 뜬다."""
    key = K.key_of(fx.move)
    if "rest" in key:
        _ail_sleep(fx, 0, fx.src[0], fx.src[1])
        if fx.move.get("heal"):
            heal(fx)
        return
    sh, g = fx.show, fx.geo
    c = K.tone("PSYCHIC")

    def rings(p, u, ms):
        for j in range(4):
            v = u * 1.3 - j * 0.14
            if 0 < v < 1:
                x, y = g.at(v)
                r = 8 + 12 * v
                K.hoop(p, x, y, r * 0.4, r * 1.2, g.ang, c.light if j % 2 else c.alt, 2)
    end = sh.act(0, 340, rings)
    _ail_sleep(fx, end - 100, fx.dst[0], fx.dst[1])


# ---------------------------------------------------------------- 날씨 · 깔아 두는 것
def weather(fx):
    """날씨: 하늘이 바뀐다 - 쾌청은 해가 뜨고, 비바라기는 빗줄기가, 모래바람은 모래가, 싸라기눈은 눈이 쏟아진다."""
    sh, g = fx.show, fx.geo
    key = K.key_of(fx.move)
    x0, x1 = min(g.sx, g.tx) - 60, max(g.sx, g.tx) + 60
    y0, y1 = g.top + 16, max(g.gs, g.gt) + 6
    cx = (x0 + x1) / 2.0
    T = 760
    seed = random.randrange(1000)
    n = 22
    drops = [(K.noise(seed + j * 3), K.noise(seed + j * 7), 0.7 + 0.6 * K.noise(seed + j * 11)) for j in range(n)]

    def sun(p, u, ms):
        f = K.back(min(1.0, ms / 220.0), 1.6) * (1.0 if u < 0.82 else (1 - u) / 0.18)
        sy_ = max(y0 + 10, min(g.sy, g.ty) - 50)
        r = 17 * f
        if r < 1:
            return
        for j in range(12):
            a = j * math.pi / 6 + ms * 0.0022
            far = r * (2.5 if j % 2 else 1.9)
            w = 0.13
            p.poly([cx + cos(a - w) * r * 1.2, sy_ + sin(a - w) * r * 1.2, cx + cos(a) * far, sy_ + sin(a) * far,
                    cx + cos(a + w) * r * 1.2, sy_ + sin(a + w) * r * 1.2], "#ffd24a" if j % 2 else "#fff0a0")
        if K.ras(p):
            p.glow(cx, sy_, r * 3.0, "#ff9a2c", 0.8)                # 햇무리
            p.glow(cx, sy_, r * 1.8, "#ffd24a", 1.0)
        K.orb(p, cx, sy_, r, ("#e0701a", "#ffc83c", "#fffbe0"), shine=False)
        for j in range(3):                                  # 내리쬐는 볕
            xx = cx + (j - 1) * 46
            K.streak(p, xx, sy_ + r * 2.6, xx - 14, sy_ + r * 2.6 + 54 * f, 2.6 * f, "#fff0a0")

    def fall(p, u, ms):
        f = K.fade(u, 0.1, 0.85)
        rain_, sand, snow = "rain" in key, "sandstorm" in key, ("hail" in key or "snow" in key)
        for j, (a, b, sp) in enumerate(drops):
            ph = (ms * 0.0026 * sp + b) % 1.0
            if sand:                                        # 옆으로 휩쓴다
                x = x0 + (x1 - x0) * ((a + ms * 0.0022 * sp) % 1.0)
                y = y0 + (y1 - y0) * b + 5 * sin(ms * 0.01 + j)
                K.streak(p, x, y, x + 26 * f, y + 3, 1.8 * f + 0.2, "#e8cf9a" if j % 2 else "#b88a4a")
            elif snow:
                x = x0 + (x1 - x0) * a + 8 * sin(ms * 0.006 + j)
                y = y0 + (y1 - y0) * ph
                if j % 4 == 0:
                    K.shard(p, x, y, 5 * f + 0.5, ms * 0.01 + j, "#ffffff", "#63c8d8")
                else:
                    p.oval(x, y, (1.6 + j % 3) * f + 0.3, (1.6 + j % 3) * f + 0.3, "#ffffff", "#9fd8e8", 1)
            else:
                x = x0 + (x1 - x0) * a - 26 * ph
                y = y0 + (y1 - y0) * ph
                K.streak(p, x + 8, y - 22, x, y, 1.6 * f + 0.2, "#8ec9ff" if j % 2 else "#e9f8ff")
                if ph > 0.92 and rain_:
                    p.oval(x, y1, 6, 1.6, "", "#8ec9ff", 1)
    sh.act(0, T, sun if "sunny" in key else fall)


def hazard(fx):
    """깔아 두는 것: 스텔스록은 뾰족한 돌이, 압정뿌리기는 압정이 상대 발밑에 박히고, 끈적끈적네트는 거미줄이 펼쳐진다."""
    from .fx_ranged import volley
    sh, g, c = fx.show, fx.geo, fx.c
    key = K.key_of(fx.move)
    gy = g.gt
    if "web" in key:
        T = 620

        def web(p, u, ms):
            f = K.out2(min(1.0, ms / 260.0)) * (1.0 if u < 0.85 else (1 - u) / 0.15)
            r = 38 * f
            if r < 2:
                return
            for j in range(8):
                a = j * math.pi / 4
                p.line([g.tx, gy, g.tx + cos(a) * r, gy + sin(a) * r * 0.34], "#f4f8ff", 1)
            for q in (0.35, 0.68, 1.0):
                pts = []
                for j in range(8):
                    a = j * math.pi / 4
                    pts += [g.tx + cos(a) * r * q, gy + sin(a) * r * q * 0.34]
                p.poly(pts, "", "#f4f8ff" if q < 1 else "#c8d4e8", 1)
        cast(fx, 0, typ="BUG")
        sh.act(160, T, web)
        return
    toxic = "toxic" in key
    spikes_ = "spikes" in key
    cc = K.tone("POISON") if toxic else c
    slots = [(-30, 3), (-14, -3), (2, 4), (17, -2), (32, 3)]

    def one(p, x, y, ang, j, v, ms):
        if spikes_:
            K.flare(p, x, y, 7.5, 4, cc.light if toxic else "#dfe6ee", inner=0.3, rot=ms * 0.02 + j, outline=cc.deep)
        else:
            K.spike(p, x, y + 6, 5, 15, -math.pi / 2 + sin(ms * 0.02 + j) * 0.6, cc.light, cc.deep)
    end = volley(fx, 0, 5, one, gap=70, life=300, arc=30, spread=0, hit=0, ease=lambda u: u)

    def stuck(p, u, ms):
        f = K.back(min(1.0, ms / 120.0), 2.0) * (1.0 if u < 0.8 else (1 - u) / 0.2)
        for j, (ox, oy) in enumerate(slots):
            if ms < j * 70 - 60:
                continue
            x, y = g.tx + ox, gy + oy
            if spikes_:
                K.flare(p, x, y - 3, 7.5 * f, 4, cc.light if toxic else "#dfe6ee", inner=0.3, rot=0.4 + j,
                        outline=cc.deep)
            else:
                K.spike(p, x, y + 3, 5.5 * f, (14 + 5 * (j % 2)) * f, -math.pi / 2 + (j - 2) * 0.12, cc.dark, cc.deep)
                K.spike(p, x + 1.5, y + 3, 2.4 * f, (11 + 4 * (j % 2)) * f, -math.pi / 2 + (j - 2) * 0.12, cc.light)
            if (int(ms / 80) + j) % 4 == 0:
                K.glint(p, x + 3, y - 12, 6, WHITE)
    sh.act(300, end - 300 + 380, stuck)


STYLES = {
    "buff": buff, "selfdown": selfdown, "debuff": debuff, "heal": heal_style, "roost": roost, "hex": hex_, "wisp": wisp,
    "self": self_, "shield": shield, "wall": wall, "powder": powder, "dance": dance, "sleepz": sleepz,
    "weather": weather, "hazard": hazard,
}
