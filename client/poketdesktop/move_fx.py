# -*- coding: utf-8 -*-
"""기술 전용 연출 (1.10.0).

battle_fx 의 갈래는 '어떤 종류의 기술인가' 까지만 갈랐다. 그래서 화염방사도
사이코키네시스도 문포스도 전부 같은 '타입 색 줄기' 였고, 치근거리기도 아이언헤드도
'달려들어 세 줄 긋기' 였다. 랜덤 배틀 800판(기술 2만 번)을 세어 보니 그 둘이
기술 사용의 47% 였다. 여기서는 **많이 쓰이는 기술부터 그 기술답게** 그린다.

    pick(move, base)   이 기술이 쓸 연출 이름 (없으면 battle_fx 가 고른 base 그대로)
    STYLES[이름](fx)   연출 하나. fx 는 battle_fx.Effect
    impact(fx)         맞는 순간 - 모든 연출이 이걸로 끝난다

그리는 법.

  * **반투명이 없다.** 바탕화면 배틀의 레이어는 색 하나를 뚫어 투명하게 만드는
    창이라 알파가 안 먹는다. 빛은 '어두운 색 - 밝은 색 - 흰 심' 을 겹쳐서 내고,
    사라지는 것은 흐려지는 대신 **작아지고 가늘어진다.**
  * **센 기술은 크게.** fx.big 이 위력에 따라 0.85 ~ 1.35 다.
  * **모으고 - 쏘고 - 맞는다.** 큰 기술은 쏘기 전에 기운을 모으는 박자가 있다.
  * 캔버스에는 create_* / coords / move / delete 만 쓴다. 관장 배틀 창은 이 넷을
    감싸서 2배로 키워 그리므로(ui_gym_battle._ScaledCanvas), itemconfigure 로
    굵기를 바꾸면 그 창에서만 크기가 어긋난다.
  * 한 편은 2초 안에 끝낸다 (관장 배틀 창은 2.6초에 다음으로 넘어간다).

눈으로 보려면: python tools/fx_preview.py 문포스 화염방사 --out 폴더
"""
import math
import random
import re

from . import battle_fx as FX

WHITE = "#ffffff"
MS = 30                         # 한 프레임


# ---------------------------------------------------------------- 연출 고르기
# 영문 이름(글자·숫자만, 소문자)으로 못 박는 기술들. 낱말 규칙보다 먼저 본다.
_EXACT_GROUPS = {
    "moon": "moonblast",
    "daimonji": "fireblast",
    "ember": "ember",
    "surf": "surf muddywater",
    "bubble": "bubble bubblebeam",
    "jet": "watergun hydropump hydrocannon scald brine waterspout steameruption snipeshot",
    "pillars": "stoneedge precipiceblades",
    "rockfall": "rockslide rocktomb rockthrow smackdown",
    "arrows": "thousandarrows",
    "meteor": "dracometeor",
    "coins": "makeitrain payday",
    "icicles": "iciclecrash",
    "thunder": "thunder thunderbolt thundercage thunderclap fusionbolt wildboltstorm",
    "zap": "thundershock discharge electroweb risingvoltage voltswitch",
    "tornado": "hurricane gust twister whirlwind bleakwindstorm springtidestorm sandsearstorm "
               "razorwind leaftornado",
    "erupt": "earthpower lavaplume eruption scorchingsands landswrath",
    "hammer": "gigatonhammer icehammer woodhammer hammerarm dragonhammer crabhammer",
    "phantom": "phantomforce shadowforce shadowsneak",
    "flurry": "closecombat outrage thrash ragingfury furyswipes cometpunch barrage",
    "blades": "airslash aircutter psychocut aquacutter",
    "laser": "hyperbeam solarbeam icebeam aurorabeam signalbeam psybeam chargebeam flashcannon "
             "steelbeam meteorbeam moongeistbeam prismaticlaser eternabeam ficklebeam twinbeam "
             "photongeyser nihillight",
    "sparkle": "fairywind silverwind icywind ominouswind",
    "blizzard": "blizzard powdersnow glaciate sheercold",
    "sludge": "sludgebomb sludge sludgewave acidspray venoshock acid gunkshot belch",
    "needles": "poisonsting pinmissile barbbarrage",
    "shield": "protect detect kingsshield spikyshield banefulbunker obstruct silktrap "
              "burningbulwark wideguard quickguard craftyshield endure matblock",
    "wall": "reflect lightscreen auroraveil safeguard mist luckychant",
    "gem": "powergem ancientpower diamondstorm",
    "whip": "vinewhip powerwhip firelash",
}
EXACT = {}
for _style, _names in _EXACT_GROUPS.items():
    for _n in _names.split():
        EXACT[_n] = _style

# 이름으로 못 잡은 '타입 색 줄기'(특수기) 는 타입이 연출을 고른다
STREAM = {
    "FIRE": "flame", "DRAGON": "flame", "GHOST": "flame", "DARK": "flame",
    "WATER": "jet", "ELECTRIC": "zap", "PSYCHIC": "psy", "FAIRY": "sparkle",
    "ICE": "blizzard", "POISON": "sludge", "GROUND": "erupt", "ROCK": "gem",
    "STEEL": "laser",
}


def key_of(move):
    return re.sub(r"[^a-z0-9]", "", (move.get("en") or "").lower())


def pick(move, base):
    """기술의 전용 연출을 고른다. 없으면 base(battle_fx 가 고른 갈래) 그대로."""
    style = EXACT.get(key_of(move))
    if style:
        return style
    if (move.get("cat") or "status") == "status":
        return base
    flags = move.get("flags") or []
    if (move.get("pri") or 0) > 0 and (move.get("power") or 0) > 0 and base in ("contact", "punch", "beam", "ice"):
        return "dash"                       # 선공기는 스치고 지나간다
    if base == "slash" and "contact" not in flags:
        return "blades"                     # 닿지 않는 베기는 칼날이 날아간다
    if base == "beam":
        return STREAM.get(move.get("type"), "beam")
    if base == "contact":
        return "hit"
    return base


# ---------------------------------------------------------------- 도구
def mix(a, b, t):
    """두 색 사이 (t=0 이면 a, 1 이면 b)."""
    t = max(0.0, min(1.0, t))
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#%02x%02x%02x" % tuple(
        int(round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t)) for i in (0, 2, 4))


def ease_out(t):
    return 1.0 - (1.0 - t) ** 2


def ease_in(t):
    return t * t


class Geo(object):
    """쓰는 쪽에서 맞는 쪽으로 가는 길."""

    def __init__(self, fx):
        self.sx, self.sy = fx.src
        self.tx, self.ty = fx.dst
        dx, dy = self.tx - self.sx, self.ty - self.sy
        self.d = math.hypot(dx, dy) or 1.0
        self.ux, self.uy = dx / self.d, dy / self.d
        self.px, self.py = -self.uy, self.ux            # 길에 수직
        self.face = 1 if dx >= 0 else -1                # 맞는 쪽이 오른쪽이면 1
        self.ang = math.atan2(dy, dx)

    def at(self, t, off=0.0):
        """길 위의 점. off 는 길 옆으로 비킨 만큼."""
        return (self.sx + (self.tx - self.sx) * t + self.px * off,
                self.sy + (self.ty - self.sy) * t + self.py * off)

    def mouth(self, r=16):
        """쓰는 쪽 몸 앞 (뭔가 뿜어 나오는 자리)."""
        return (self.sx + self.ux * r, self.sy + self.uy * r)


class Cel(object):
    """한 프레임 치 도형. 다음 프레임에 통째로 지우고 다시 그린다."""

    def __init__(self, fx):
        self.fx = fx
        self.ids = []

    def clear(self):
        cv = self.fx.cv
        for i in self.ids:
            cv.delete(i)
        self.ids = []

    def put(self, *items):
        for it in items:
            if isinstance(it, (list, tuple)):
                self.put(*it)
            elif it is not None:
                self.ids.append(it)
                self.fx.items.append(it)


def run(fx, n, draw, done=None, ms=MS):
    """프레임마다 draw(i, t) 를 부른다 (i = 0..n, t = 0..1). 끝나면 done()."""
    def step(i):
        if fx.dead:
            return
        if i > n:
            if done:
                done()
            return
        draw(i, i / float(n))
        fx.after(ms, lambda: step(i + 1))
    step(0)


class Sparks(object):
    """흩어지는 조각들. 저마다 속도·중력·수명이 있고, 수명이 다하면 사라진다.

    조각은 프레임마다 make(x, y, k) 로 다시 그린다 (k 는 남은 수명 1 -> 0).
    캔버스 도형은 돌리거나 줄일 수 없어서 다시 그리는 수밖에 없다.
    """

    def __init__(self, fx, ms=MS):
        self.fx = fx
        self.ms = ms
        self.ps = []
        self.on = False

    def add(self, make, x, y, vx=0.0, vy=0.0, life=8, g=0.0, drag=1.0):
        self.ps.append([[], make, x, y, vx, vy, life, float(life), g, drag])
        if not self.on:
            self.on = True
            self.fx.after(self.ms, self._tick)

    def _tick(self):
        fx = self.fx
        if fx.dead:
            return
        cv = fx.cv
        keep = []
        for p in self.ps:
            for i in p[0]:
                cv.delete(i)
            p[6] -= 1
            if p[6] < 0:
                continue
            p[2] += p[4]
            p[3] += p[5]
            p[5] += p[8]
            p[4] *= p[9]
            p[5] *= p[9]
            got = p[1](p[2], p[3], p[6] / p[7])
            p[0] = list(got) if isinstance(got, (list, tuple)) else ([got] if got is not None else [])
            fx.items.extend(p[0])
            keep.append(p)
        self.ps = keep
        if keep:
            fx.after(self.ms, self._tick)
        else:
            self.on = False


# ---------------------------------------------------------------- 도형
def orb(cv, x, y, r, light, dark, core=WHITE, rim=""):
    """빛나는 구슬: 어두운 겉 - 밝은 속 - 심. rim 을 주면 그 색 테를 두른다."""
    out = [cv.create_oval(x - r, y - r, x + r, y + r, fill=dark, outline=rim, width=2)]
    r2 = r * 0.68
    out.append(cv.create_oval(x - r2, y - r2, x + r2, y + r2, fill=light, outline=""))
    if core:
        r3 = r * 0.34
        out.append(cv.create_oval(x - r3, y - r3, x + r3, y + r3, fill=core, outline=""))
    return out


def spike(cv, x, y, r, n, fill, outline="", inner=0.42, rot=0.0, width=1):
    """뾰족한 별. n 이 4 고 inner 가 작으면 반짝임, 8 이면 맞는 순간의 번쩍."""
    pts = []
    for i in range(n * 2):
        a = rot + math.pi * i / n
        rr = r if i % 2 == 0 else r * inner
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    return cv.create_polygon(*pts, fill=fill, outline=outline, width=width)


def glint(cv, x, y, r, fill=WHITE):
    return spike(cv, x, y, r, 4, fill, inner=0.16, rot=-math.pi / 2)


def blade(cv, x, y, r, ang, sweep, thick, fill, outline="", a0=None, a1=None):
    """초승달 칼날. (x, y) 가 원의 중심, ang 이 휜 쪽. 가운데가 thick 만큼 두껍다.

    a0, a1 을 주면 그 사이만 그린다 (휘두르는 중간).
    """
    lo = ang - sweep / 2.0 if a0 is None else a0
    hi = ang + sweep / 2.0 if a1 is None else a1
    n = 10
    pts = []
    for i in range(n + 1):
        a = lo + (hi - lo) * i / n
        pts += [x + math.cos(a) * r, y + math.sin(a) * r]
    for i in range(n, -1, -1):
        a = lo + (hi - lo) * i / n
        rr = r - thick * math.sin(math.pi * i / n)
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    return cv.create_polygon(*pts, fill=fill, outline=outline, width=1)


def tongue(cv, x, y, r, lean, fill, outline=""):
    """불꽃 혀 하나. 아래가 둥글고 위로 뾰족하다. lean 만큼 끝이 옆으로 기운다."""
    return cv.create_polygon(
        x - r * 0.75, y + r * 0.4, x - r * 0.55, y - r * 0.4, x + lean, y - r * 1.7,
        x + r * 0.55, y - r * 0.4, x + r * 0.75, y + r * 0.4, x, y + r * 0.9,
        fill=fill, outline=outline, smooth=True)


def zig(x1, y1, x2, y2, jag, n):
    """지그재그 길의 좌표 (번개·갈라진 땅)."""
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy) or 1.0
    px, py = -dy / d, dx / d
    pts = [x1, y1]
    for i in range(1, n):
        t = (i + random.uniform(-0.3, 0.3)) / float(n)
        o = random.uniform(-jag, jag)
        pts += [x1 + dx * t + px * o, y1 + dy * t + py * o]
    return pts + [x2, y2]


def bolt(cv, pts, light, dark, w):
    """번개 한 줄: 어두운 겉 - 밝은 속 - 흰 심."""
    return [cv.create_line(*pts, fill=dark, width=w + 4),
            cv.create_line(*pts, fill=light, width=w + 1),
            cv.create_line(*pts, fill=WHITE, width=max(1, w - 2))]


def heart(cv, x, y, r, fill, outline=""):
    pts = []
    for i in range(16):
        a = 2 * math.pi * i / 16
        hx = 16 * math.sin(a) ** 3
        hy = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts += [x + hx * r / 16.0, y + hy * r / 16.0]
    return cv.create_polygon(*pts, fill=fill, outline=outline, width=1)


def rock(cv, x, y, r, light, dark, seed=0):
    rnd = random.Random(seed)
    pts = []
    for i in range(6):
        a = 2 * math.pi * i / 6 + rnd.uniform(-0.25, 0.25)
        rr = r * rnd.uniform(0.72, 1.1)
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    return [cv.create_polygon(*pts, fill=dark, outline=light, width=2),
            cv.create_line(pts[0], pts[1], x, y, pts[6], pts[7], fill=light, width=1)]


def shard(cv, x, y, r, ang, fill, outline=""):
    """ang 쪽을 보는 길쭉한 조각 (얼음·화살촉·바늘)."""
    c, s = math.cos(ang), math.sin(ang)
    pts = []
    for dx, dy in ((r * 1.5, 0), (0, r * 0.42), (-r * 0.9, 0), (0, -r * 0.42)):
        pts += [x + dx * c - dy * s, y + dx * s + dy * c]
    return cv.create_polygon(*pts, fill=fill, outline=outline, width=1)


def rip(cv, x1, y1, x2, y2, w, fill, outline=""):
    """양 끝이 뾰족하고 가운데가 두꺼운 자국 (발톱·칼자국)."""
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy) or 1.0
    px, py = -dy / d * w, dx / d * w
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    return cv.create_polygon(x1, y1, mx + px, my + py, x2, y2, mx - px, my - py,
                             fill=fill, outline=outline, width=1)


def puff(cv, x, y, r, fill, outline=""):
    """뭉게구름 한 덩이."""
    out = []
    for dx, dy, k in ((-0.55, 0.15, 0.62), (0.5, 0.2, 0.58), (0.0, -0.2, 0.8)):
        rr = r * k
        out.append(cv.create_oval(x + dx * r - rr, y + dy * r - rr, x + dx * r + rr, y + dy * r + rr,
                                  fill=fill, outline=outline))
    return out


# ---------------------------------------------------------------- 맞는 순간
# 타입마다 튀는 조각이 다르다
SCATTER = {
    "FIRE": "flame", "WATER": "drop", "ELECTRIC": "zap", "GRASS": "leaf", "BUG": "leaf",
    "ICE": "shard", "DRAGON": "shard", "ROCK": "pebble", "GROUND": "pebble",
    "FAIRY": "star", "PSYCHIC": "star", "GHOST": "wisp", "DARK": "wisp", "POISON": "bubble",
    "STEEL": "glint",
}


def scatter(fx, sp, x, y, k=1.0, typ=None, n=None):
    """타입에 맞는 조각을 (x, y) 에서 흩뿌린다."""
    cv = fx.cv
    typ = typ or fx.type
    light, dark = FX.colors(typ)
    kind = SCATTER.get(typ, "line")
    n = n if n is not None else max(4, int(round(7 * k)))
    for j in range(n):
        a = random.uniform(0, 2 * math.pi)
        v = random.uniform(3.2, 6.4) * k
        vx, vy = math.cos(a) * v, math.sin(a) * v
        if kind == "flame":
            lean = random.uniform(-4, 4)
            sp.add(lambda px, py, lk, le=lean: tongue(cv, px, py, (3 + 6 * lk) * k, le,
                                                      light if lk > 0.5 else dark),
                   x + vx * 2, y + vy, vx * 0.5, -abs(vy) * 0.6 - 1.2, life=9, g=-0.12)
        elif kind == "drop":
            sp.add(lambda px, py, lk: FX._drop(cv, px, py, (2 + 2.5 * lk) * k, light, dark),
                   x, y, vx * 0.9, -abs(vy) - 1.5, life=10, g=1.05)
        elif kind == "zap":
            sp.add(lambda px, py, lk, ang=a: cv.create_line(
                *zig(px, py, px + math.cos(ang) * 12 * k, py + math.sin(ang) * 12 * k, 4, 3),
                fill=WHITE if lk > 0.5 else light, width=2),
                   x + vx, y + vy, vx, vy, life=7, drag=0.82)
        elif kind == "leaf":
            sp.add(lambda px, py, lk, ph=a: FX._leaf_shape(cv, px, py, (3 + 3 * lk) * k, light, dark,
                                                         math.degrees(ph) + lk * 500),
                   x, y, vx, vy, life=10, g=0.18, drag=0.9)
        elif kind == "shard":
            sp.add(lambda px, py, lk, ang=a, col=WHITE if j % 2 else light: shard(
                cv, px, py, (2 + 5 * lk) * k, ang, col, dark),
                   x + vx, y + vy, vx * 1.2, vy * 1.2, life=8, drag=0.8)
        elif kind == "pebble":
            sp.add(lambda px, py, lk, sd=j: rock(cv, px, py, (2 + 3 * lk) * k, light, dark, sd),
                   x, y + 8, vx * 0.8, -abs(vy) - 2.0, life=10, g=1.0)
        elif kind == "star":
            if typ == "FAIRY" and j % 3 == 0:
                sp.add(lambda px, py, lk: heart(cv, px, py, (3 + 4 * lk) * k, light, dark),
                       x, y, vx * 0.8, vy * 0.8 - 0.8, life=10, drag=0.88)
            else:
                sp.add(lambda px, py, lk: FX._star(cv, px, py, (2 + 5 * lk) * k, light, dark),
                       x, y, vx, vy - 0.5, life=10, drag=0.86)
        elif kind == "wisp":
            sp.add(lambda px, py, lk, le=random.uniform(-5, 5): tongue(cv, px, py, (2 + 6 * lk) * k, le, dark,
                                                                        light),
                   x + vx * 2, y + vy * 2, vx * 0.35, -abs(vy) * 0.45 - 0.8, life=10)
        elif kind == "bubble":
            sp.add(lambda px, py, lk: cv.create_oval(px - (2 + 4 * lk) * k, py - (2 + 4 * lk) * k,
                                                     px + (2 + 4 * lk) * k, py + (2 + 4 * lk) * k,
                                                     fill=dark, outline=light, width=2),
                   x + vx * 2, y + vy * 2, vx * 0.4, -abs(vy) * 0.5 - 0.6, life=10)
        elif kind == "glint":
            sp.add(lambda px, py, lk: glint(cv, px, py, (2 + 7 * lk) * k, WHITE if lk > 0.4 else light),
                   x + vx * 2, y + vy * 2, vx, vy, life=8, drag=0.8)
        else:
            sp.add(lambda px, py, lk, ax=math.cos(a), ay=math.sin(a): cv.create_line(
                px, py, px + ax * (4 + 9 * lk) * k, py + ay * (4 + 9 * lk) * k,
                fill=WHITE if lk > 0.5 else light, width=3 if lk > 0.5 else 2, capstyle="round"),
                   x + vx * 2, y + vy * 2, vx * 1.3, vy * 1.3, life=7, drag=0.84)


def impact(fx, at=None, done=None, size=1.0, typ=None):
    """맞는 순간. 흰 별이 번쩍하고, 고리가 퍼지고, 타입에 맞는 조각이 튄다."""
    cv = fx.cv
    x, y = at or fx.dst
    light, dark = FX.colors(typ or fx.type)
    k = size * fx.big
    cel = Cel(fx)
    scatter(fx, Sparks(fx), x, y, k, typ=typ)
    rot = random.uniform(0, math.pi)

    def draw(i, t):
        cel.clear()
        if i < 3:                                       # 번쩍 - 맞는 프레임
            cel.put(spike(cv, x, y, (30 - i * 6) * k, 8, WHITE, light, inner=0.4,
                          rot=rot + i * 0.25, width=2))
        r = (12 + 34 * ease_out(t)) * k
        w = max(1, int(round(5 * (1 - t))))
        cel.put(cv.create_oval(x - r, y - r * 0.82, x + r, y + r * 0.82, outline=light, width=w))
        if i > 1:
            r2 = r * 0.6
            cel.put(cv.create_oval(x - r2, y - r2 * 0.82, x + r2, y + r2 * 0.82,
                                   outline=dark, width=max(1, w - 1)))

    def end():
        cel.clear()
        (done or fx.finish)()
    run(fx, 10, draw, end)


def mini(fx, x, y, k=0.7, typ=None):
    """작은 타격 하나 (연속기의 한 대). 끝을 기다리지 않는다."""
    cv = fx.cv
    light, _dark = FX.colors(typ or fx.type)
    cel = Cel(fx)
    scatter(fx, Sparks(fx), x, y, k * 0.8, typ=typ, n=3)
    rot = random.uniform(0, math.pi)

    def draw(i, t):
        cel.clear()
        if i < 3:
            cel.put(spike(cv, x, y, (20 - i * 5) * k * fx.big, 6, WHITE, light, inner=0.4, rot=rot, width=2))
    run(fx, 3, draw, cel.clear)


# ---------------------------------------------------------------- 접촉기
def _smash(fx, done):
    """달려든 쪽에서 날아와 꽂히는 굵은 줄 세 개."""
    cv = fx.cv
    g = Geo(fx)
    light, _dark = FX.colors(fx.type)
    cel = Cel(fx)

    def draw(i, t):
        cel.clear()
        for j, off in enumerate((-13, 0, 13)):
            far = 44 - i * 13
            x1, y1 = g.tx - g.ux * (far + 26) + g.px * off * 1.5, g.ty - g.uy * (far + 26) + g.py * off * 1.5
            x2, y2 = g.tx - g.ux * far * 0.3 + g.px * off * 0.5, g.ty - g.uy * far * 0.3 + g.py * off * 0.5
            cel.put(rip(cv, x1, y1, x2, y2, 4 if j == 1 else 3, WHITE, light))

    def end():
        cel.clear()
        done()
    run(fx, 2, draw, end, ms=26)


def _brawl(fx, done):
    """치근거리기: 먼지 구름 속에서 별과 하트가 튄다."""
    cv = fx.cv
    tx, ty = fx.dst
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    sp = Sparks(fx)
    clouds = []

    def draw(i, t):
        cel.clear()
        if i < 9:
            a = random.uniform(0, 2 * math.pi)
            clouds.append([tx + math.cos(a) * random.uniform(4, 22), ty + math.sin(a) * random.uniform(4, 16),
                           random.uniform(11, 17), 0])
            if i % 2 == 0:
                vx, vy = random.uniform(-4, 4), random.uniform(-5.5, -2)
                if i % 4 == 0:
                    sp.add(lambda px, py, lk: heart(cv, px, py, 4 + 5 * lk, light, dark),
                           tx, ty, vx, vy, life=9, g=0.25)
                else:
                    sp.add(lambda px, py, lk: FX._star(cv, px, py, 3 + 6 * lk, "#fff6a8", dark),
                           tx, ty, vx, vy, life=9, g=0.25)
        for c in clouds:
            c[3] += 1
            if c[3] <= 4:
                cel.put(puff(cv, c[0], c[1], c[2] * (0.6 + 0.14 * c[3]), WHITE if c[3] < 3 else light, dark))

    def end():
        cel.clear()
        done()
    run(fx, 11, draw, end)


def _haunt(fx, done):
    """그림자가 발밑에서 솟아 덮친다 (고스트·악 접촉기)."""
    cv = fx.cv
    tx, ty = fx.dst
    light, dark = FX.colors(fx.type)
    ink = mix(dark, "#000000", 0.45)
    cel = Cel(fx)

    def draw(i, t):
        cel.clear()
        h = 30 + 34 * ease_out(min(1.0, i / 5.0))
        for j, (ox, kk) in enumerate(((-17, 0.7), (16, 0.75), (0, 1.0))):
            lean = 5 * math.sin(i * 0.9 + j * 2)
            cel.put(tongue(cv, tx + ox, ty + 30 - h * kk * 0.42, h * kk * 0.42, lean, ink, light))
        if 2 <= i <= 7:                                 # 눈
            for ex in (-7, 7):
                cel.put(cv.create_oval(tx + ex - 3, ty - 8, tx + ex + 3, ty - 3 + (1 if i % 2 else 0),
                                       fill="#ff5a7a", outline=""))

    def end():
        cel.clear()
        done()
    run(fx, 8, draw, end)


def _clang(fx, done):
    """쇠가 부딪히는 번쩍임."""
    cv = fx.cv
    tx, ty = fx.dst
    light, _dark = FX.colors(fx.type)
    cel = Cel(fx)

    def draw(i, t):
        cel.clear()
        r = (16, 40, 54, 40, 22)[min(i, 4)] * fx.big
        cel.put(cv.create_line(tx - r * 1.5, ty, tx + r * 1.5, ty, fill=light, width=2),
                cv.create_line(tx, ty - r * 1.5, tx, ty + r * 1.5, fill=light, width=2),
                spike(cv, tx, ty, r, 4, WHITE, light, inner=0.14, rot=-math.pi / 2, width=1),
                spike(cv, tx, ty, r * 0.5, 4, WHITE, inner=0.3, rot=-math.pi / 4))

    def end():
        cel.clear()
        done()
    run(fx, 4, draw, end)


def _crackle(fx, done):
    """몸에 감긴 전기가 터진다."""
    cv = fx.cv
    tx, ty = fx.dst
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)

    def draw(i, t):
        cel.clear()
        for _j in range(5):
            a = random.uniform(0, 2 * math.pi)
            r = random.uniform(26, 42) * fx.big
            cel.put(bolt(cv, zig(tx, ty, tx + math.cos(a) * r, ty + math.sin(a) * r * 0.85, 7, 4),
                         light, dark, 2))

    def end():
        cel.clear()
        done()
    run(fx, 5, draw, end)


def _rips(fx, done, mirror=False, at=None, hold=3, color=None):
    """발톱 자국 세 줄이 위에서 아래로 그어진다."""
    cv = fx.cv
    tx, ty = at or fx.dst
    light, dark = FX.colors(fx.type)
    g = Geo(fx)
    s = g.face * (-1 if mirror else 1)
    cel = Cel(fx)
    k = fx.big

    def draw(i, t):
        cel.clear()
        f = min(1.0, (i + 1) / 4.0)
        thin = 1.0 if i < 4 + hold - 2 else 0.5
        for j, o in enumerate((-15, 0, 15)):
            x1, y1 = tx + s * (-22 + o) * k, ty - 27 * k
            x2, y2 = x1 + s * 38 * k * f, y1 + 54 * k * f
            w = (6 if j == 1 else 5) * k * thin
            cel.put(rip(cv, x1, y1, x2, y2, w, color or light, dark),
                    rip(cv, x1, y1, x2, y2, w * 0.4, WHITE))

    def end():
        cel.clear()
        done()
    run(fx, 3 + hold, draw, end)


def _rend(fx, done):
    """엇갈린 발톱 두 번 (드래곤)."""
    _rips(fx, lambda: _rips(fx, done, mirror=True, hold=2), hold=1)


FLOURISH = {"FAIRY": _brawl, "GHOST": _haunt, "DARK": _haunt, "STEEL": _clang,
            "ELECTRIC": _crackle, "DRAGON": _rend}


def hit(fx):
    """접촉기: 달려들어 때린다. 타입마다 맞는 모습이 다르다."""
    def strike():
        if fx.dead:
            return
        (FLOURISH.get(fx.type) or _smash)(fx, lambda: impact(fx, size=1.15))
    fx.st.lunge(fx.who, strike)


def flurry(fx):
    """난타 (인파이트·역린): 사방에서 연달아 터지고 마지막에 크게."""
    tx, ty = fx.dst

    def strike():
        def one(i):
            if fx.dead:
                return
            if i >= 6:
                return fx.after(70, lambda: impact(fx, size=1.3))
            a = i * 2.4 + random.uniform(-0.4, 0.4)
            mini(fx, tx + math.cos(a) * 20, ty + math.sin(a) * 17, k=0.85)
            fx.after(66, lambda: one(i + 1))
        one(0)
    fx.st.lunge(fx.who, strike)


def dash(fx):
    """선공기: 눈에 안 보이게 스치고 지나간다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    fx.st.lunge(fx.who, lambda: None)                   # 몸도 같이 움찔한다

    def draw(i, t):
        cel.clear()
        if i <= 4:                                      # 날아가는 줄기
            head = 1.25 * (i + 1) / 5.0
            tail = max(0.0, head - 0.5)
            for j, off in enumerate((-9, -3, 3, 9)):
                x1, y1 = g.at(tail + 0.04 * j, off)
                x2, y2 = g.at(head - 0.03 * (3 - j), off)
                cel.put(cv.create_line(x1, y1, x2, y2, fill=WHITE if j in (1, 2) else light,
                                       width=3 if j in (1, 2) else 2, capstyle="round"))
            for j in range(3):                          # 잔상
                x, y = g.at(max(0.0, head - 0.22 * (j + 1)))
                r = 12 - j * 3
                cel.put(cv.create_oval(x - r, y - r, x + r, y + r, outline=dark, width=2))
        else:                                           # 지나간 자리에 남는 한 줄
            ln = 58 * fx.big
            w = (6, 4, 2)[min(2, i - 5)]
            cel.put(cv.create_line(g.tx - g.ux * ln, g.ty - g.uy * ln, g.tx + g.ux * ln, g.ty + g.uy * ln,
                                   fill=light, width=w + 3, capstyle="round"),
                    cv.create_line(g.tx - g.ux * ln, g.ty - g.uy * ln, g.tx + g.ux * ln, g.ty + g.uy * ln,
                                   fill=WHITE, width=w, capstyle="round"))

    def end():
        cel.clear()
        impact(fx, size=1.05)
    run(fx, 7, draw, end, ms=28)


def phantom(fx):
    """고스트다이브: 그림자가 땅을 타고 가서 발밑에서 솟는다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    ink = mix(dark, "#000000", 0.5)
    cel = Cel(fx)

    def draw(i, t):
        cel.clear()
        tt = ease_in(min(1.0, i / 7.0))
        x, y = g.at(tt)
        y += 26
        w = 20 + 8 * math.sin(i * 1.3)
        cel.put(cv.create_oval(x - w, y - 6, x + w, y + 6, fill=ink, outline=light, width=2))
        for j in range(2):                              # 지나온 자리
            bx, by = g.at(max(0.0, tt - 0.14 * (j + 1)))
            bw = 12 - j * 5
            cel.put(cv.create_oval(bx - bw, by + 23, bx + bw, by + 29, fill=ink, outline=""))

    def end():
        cel.clear()
        _haunt(fx, lambda: impact(fx, size=1.2))
    run(fx, 7, draw, end)


# ---------------------------------------------------------------- 베기 · 발톱
def _sweep(fx, done, mirror=False, color=None, thick=15, span=2.5):
    """크게 휘두른 칼자국. 초승달이 한쪽 끝에서 다른 쪽 끝으로 그어진다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    col = color or light
    k = fx.big
    r = 46 * k
    tilt = (0.75 if mirror else -0.75) * g.face
    ang = g.ang + tilt
    cx, cy = g.tx - math.cos(ang) * r * 0.62, g.ty - math.sin(ang) * r * 0.62
    cel = Cel(fx)

    def draw(i, t):
        cel.clear()
        lo, hi = ang - span / 2.0, ang + span / 2.0
        if mirror:
            lo, hi = hi, lo
        if i < 4:                                       # 그어지는 중
            a1 = lo + (hi - lo) * (i + 1) / 4.0
            cel.put(blade(cv, cx, cy, r, ang, span, thick * k, col, dark, a0=lo, a1=a1),
                    blade(cv, cx, cy, r - 1, ang, span, thick * 0.47 * k, WHITE, a0=lo, a1=a1))
        else:                                           # 남은 자국이 가늘어진다
            th = (0.73, 0.4, 0.13)[min(2, i - 4)] * thick * k
            cel.put(blade(cv, cx, cy, r, ang, span, th, col, dark),
                    blade(cv, cx, cy, r - 1, ang, span, th * 0.45, WHITE))

    def end():
        cel.clear()
        done()
    run(fx, 6, draw, end, ms=28)


def slash(fx):
    """베기. 닿는 기술이면 달려들어 벤다. 이름에 cross 가 있으면 X 자로 두 번."""
    cross = any(w in key_of(fx.move) for w in ("cross", "xscissor", "scissor", "dual", "double"))

    def cut():
        if fx.dead:
            return
        if cross:
            _sweep(fx, lambda: None)
            fx.after(80, lambda: _sweep(fx, lambda: impact(fx, size=1.15), mirror=True))
        else:
            _sweep(fx, lambda: impact(fx, size=1.1))
    if "contact" in (fx.move.get("flags") or []):
        fx.st.lunge(fx.who, cut)
    else:
        cut()


def blades(fx):
    """칼날이 날아간다 (에어슬래시·사이코커터)."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    k = fx.big
    n, gap, life = 3, 4, 8
    total = (n - 1) * gap + life

    def draw(i, t):
        cel.clear()
        for j in range(n):
            a = i - j * gap
            if a < 0 or a > life:
                continue
            tt = a / float(life)
            off = (-11, 9, 0)[j]
            x, y = g.at(tt, off * math.sin(math.pi * tt))
            r = 17 * k
            wob = g.ang + 0.35 * math.sin(a * 1.1 + j)
            cx, cy = x - math.cos(wob) * r, y - math.sin(wob) * r
            if a >= 1:                                  # 꼬리
                bx, by = g.at(max(0.0, tt - 0.09), off * math.sin(math.pi * tt))
                cel.put(blade(cv, bx - math.cos(wob) * r, by - math.sin(wob) * r, r, wob, 1.9, 3 * k, dark))
            cel.put(blade(cv, cx, cy, r, wob, 2.2, 8 * k, light, dark),
                    blade(cv, cx, cy, r - 1, wob, 2.2, 3.5 * k, WHITE))
            if a == life:
                mini(fx, g.tx + off * 0.6, g.ty + off * 0.4, k=0.7)

    def end():
        cel.clear()
        _sweep(fx, lambda: impact(fx, size=1.1))
    run(fx, total, draw, end, ms=28)


def claw(fx):
    """발톱. 닿는 기술이면 달려들어 할퀸다."""
    def go():
        if fx.dead:
            return
        _rips(fx, lambda: impact(fx, size=1.1))
    if "contact" in (fx.move.get("flags") or []):
        fx.st.lunge(fx.who, go)
    else:
        go()



# ---------------------------------------------------------------- 날아가는 것
def pulse(fx):
    """파동: 심이 날아가며 고리를 남긴다. 고리는 커지면서 가늘어진다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    sp = Sparks(fx)
    k = fx.big
    rings = []
    kx, ky = 0.42 + 0.58 * abs(g.uy), 0.42 + 0.58 * abs(g.ux)      # 고리가 가는 쪽을 본다

    def draw(i, t):
        cel.clear()
        x, y = g.at(t)
        if i % 2 == 0:
            rings.append([x, y, 0])
        for r in rings:
            r[2] += 1
            if r[2] > 7:
                continue
            rr = (5 + r[2] * 3.8) * k
            cel.put(cv.create_oval(r[0] - rr * kx, r[1] - rr * ky, r[0] + rr * kx, r[1] + rr * ky,
                                   outline=dark if r[2] > 4 else light, width=max(1, 5 - r[2] // 2 * 1)))
        cel.put(orb(cv, x, y, 8 * k, light, dark))
        if fx.type == "WATER" and i % 2:
            sp.add(lambda px, py, lk: FX._drop(cv, px, py, 2 + 2 * lk, light, dark),
                   x, y, random.uniform(-1.5, 1.5), -1.0, life=6, g=0.8)

    def end():
        cel.clear()
        impact(fx, size=1.1)
    run(fx, 12, draw, end, ms=28)


def ball(fx):
    """구슬: 몸 앞에서 기운이 모여 뭉치고, 꼬리를 끌며 날아가 터진다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    core = light if fx.type in ("GHOST", "DARK") else WHITE
    if fx.type in ("GHOST", "DARK"):
        light, dark = mix(dark, light, 0.35), mix(dark, "#000000", 0.4)
    rim = core if core != WHITE else ""               # 어두운 구슬은 밝은 테가 있어야 보인다
    cel = Cel(fx)
    k = fx.big
    mx, my = g.mouth(20)
    R = 12 * k
    trail = []
    C, T = 7, 9

    def draw(i, t):
        cel.clear()
        if i <= C:                                      # 모은다
            f = i / float(C)
            for j in range(6):
                a = j * math.pi / 3 + i * 0.5
                rr = 38 * (1 - f)
                px, py = mx + math.cos(a) * rr, my + math.sin(a) * rr
                cel.put(cv.create_oval(px - 2.5, py - 2.5, px + 2.5, py + 2.5, fill=core, outline=""))
            cel.put(orb(cv, mx, my, 3 + (R - 3) * ease_out(f), light, dark, core, rim))
            return
        tt = ease_in((i - C) / float(T))                # 쏜다
        x, y = mx + (g.tx - mx) * tt, my + (g.ty - my) * tt
        trail.append((x, y))
        for j, (bx, by) in enumerate(trail[-4:-1]):
            rr = R * (0.32 + 0.18 * j)
            cel.put(cv.create_oval(bx - rr, by - rr, bx + rr, by + rr, fill=dark, outline=rim))
        cel.put(orb(cv, x, y, R * (1 + 0.08 * math.sin(i * 2.0)), light, dark, core, rim))
        for j in range(2):                              # 구슬을 도는 빛
            a = i * 0.9 + j * math.pi
            px, py = x + math.cos(a) * (R + 5), y + math.sin(a) * (R + 5) * 0.6
            cel.put(cv.create_oval(px - 2, py - 2, px + 2, py + 2, fill=core, outline=""))

    def end():
        cel.clear()
        impact(fx, size=1.25)
    run(fx, C + T, draw, end)


def leaf(fx):
    """잎 여러 장이 돌면서 휘어 날아간다. 꽃 기술은 분홍 꽃잎."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    key = key_of(fx.move)
    if any(w in key for w in ("petal", "flower", "bloom")):
        light, dark = "#ffd6ea", "#f07aa8"
    magical = "magical" in key or fx.type == "FAIRY"
    cel = Cel(fx)
    k = fx.big
    n, gap, life = 8, 2, 9
    amps = [(-1 if j % 2 else 1) * random.uniform(8, 26) for j in range(n)]

    def draw(i, t):
        cel.clear()
        for j in range(n):
            a = i - j * gap
            if a < 0 or a > life:
                continue
            tt = a / float(life)
            x, y = g.at(tt, amps[j] * math.sin(math.pi * tt))
            if magical and a % 2 == 0:
                cel.put(glint(cv, x - g.ux * 11, y - g.uy * 11, 5))
            cel.put(FX._leaf_shape(cv, x, y, 8 * k, light, dark, tt * 620 + j * 47))
            if a == life:
                mini(fx, x, y, 0.6)

    def end():
        cel.clear()
        impact(fx, size=1.1)
    run(fx, (n - 1) * gap + life, draw, end, ms=28)


def whip(fx):
    """채찍: 덩굴이 휘며 뻗어 나가 내리치고 돌아온다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)

    def draw(i, t):
        cel.clear()
        ext = min(1.0, (i + 1) / 5.0) if i < 8 else max(0.0, 1.0 - (i - 7) / 4.0)
        bend = -46 * math.cos(i * 0.62) * g.face
        pts = []
        for s in range(9):
            u = s / 8.0 * ext
            x, y = g.at(u, bend * math.sin(math.pi * s / 8.0) * (0.35 + 0.65 * (1 - ext)))
            pts += [x, y]
        cel.put(cv.create_line(*pts, fill=dark, width=6, smooth=True, capstyle="round"),
                cv.create_line(*pts, fill=light, width=3, smooth=True, capstyle="round"))
        if i == 5:
            impact(fx, size=1.15)                       # 끝이 닿는 순간 (돌아오는 동안 터진다)
    run(fx, 10, draw, cel.clear)


def psy(fx):
    """염력: 머리에서 염파가 나가고, 맞는 쪽 둘레의 공간이 조여들며 일그러진다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    violet = "#c58bff"
    cel = Cel(fx)
    k = fx.big
    A = 5
    B = 16 if (fx.move.get("power") or 0) >= 90 else 11
    deg = -math.degrees(g.ang)

    def draw(i, t):
        cel.clear()
        if i <= A + 2:                                  # 염파
            for j in range(3):
                rr = 12 + (i - j) * 13
                if 12 <= rr <= 90:
                    cel.put(cv.create_arc(g.sx - rr, g.sy - rr, g.sx + rr, g.sy + rr, start=deg - 32,
                                          extent=64, style="arc", outline=violet if j % 2 else light, width=3))
        if i >= A:
            b = i - A
            for j in range(3):                          # 일그러지는 공간
                yy = g.ty - 16 * k + j * 16 * k
                pts = []
                for s in range(9):
                    pts += [g.tx - 46 * k + s * 11.5 * k, yy + 5 * math.sin(s * 1.3 + b * 1.2 + j * 2)]
                cel.put(cv.create_line(*pts, fill=dark, width=2, smooth=True))
            for j in range(3):                          # 조여드는 고리
                rr = (58 - (b * 5 + j * 19) % 54) * k
                cel.put(cv.create_oval(g.tx - rr, g.ty - rr * 0.72, g.tx + rr, g.ty + rr * 0.72,
                                       outline=violet if j % 2 else light, width=3 if rr < 32 * k else 2))
            if b % 2 == 0:
                cel.put(glint(cv, g.tx + random.uniform(-32, 32) * k, g.ty + random.uniform(-24, 24) * k, 7))

    def end():
        cel.clear()
        impact(fx, size=1.2)
    run(fx, A + B, draw, end)


def flame(fx):
    """불길을 뿜는다. 멀어질수록 퍼지고, 닿은 쪽은 불길에 휩싸인다.

    용·고스트·악의 줄기도 이 모양을 쓴다 (색만 그 타입 것).
    """
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    hot = WHITE if fx.type in ("FIRE", "DRAGON") else light
    if fx.type in ("GHOST", "DARK"):
        light, dark = mix(dark, light, 0.4), mix(dark, "#000000", 0.35)
    cel = Cel(fx)
    k = fx.big
    p = fx.move.get("power") or 0
    emit = 8 if p < 70 else 12 if p < 100 else 16
    life = 9
    mx, my = g.mouth(14)
    spd = math.hypot(g.tx - mx, g.ty - my) / float(life)
    parts = []

    def draw(i, t):
        cel.clear()
        if i < emit:
            for _ in range(3):
                v = spd * random.uniform(0.88, 1.08)
                side = random.uniform(-1.3, 1.3)
                parts.append([mx, my, g.ux * v + g.px * side, g.uy * v + g.py * side, 0])
        for q in parts:
            q[0] += q[2]
            q[1] += q[3]
            q[4] += 1
        parts[:] = [q for q in parts if q[4] <= life]
        for q in parts:                                 # 어두운 겉부터 깔고 밝은 속을 얹는다
            r = (5 + 11.0 * q[4] / life) * k
            cel.put(cv.create_oval(q[0] - r, q[1] - r, q[0] + r, q[1] + r, fill=dark, outline=""))
        for q in parts:
            r = (5 + 11.0 * q[4] / life) * k * 0.62
            cel.put(cv.create_oval(q[0] - r, q[1] - r, q[0] + r, q[1] + r, fill=light, outline=""))
        for q in parts:
            if q[4] < life * 0.6:
                r = (5 + 11.0 * q[4] / life) * k * 0.3
                cel.put(cv.create_oval(q[0] - r, q[1] - r, q[0] + r, q[1] + r, fill=hot, outline=""))
        if life - 1 <= i <= emit + life - 2:            # 불길에 휩싸인다
            for j in range(3):
                r = (9 + 5 * math.sin(i * 1.7 + j * 2.1)) * k
                cel.put(tongue(cv, g.tx + (j - 1) * 13 * k, g.ty + 16 * k - r * 0.4, r,
                               random.uniform(-5, 5), light, dark))

    def end():
        cel.clear()
        impact(fx, size=1.2)
    run(fx, emit + life, draw, end, ms=28)


def ember(fx):
    """불꽃세례: 작은 불덩이 셋을 연달아 던진다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    n, gap, life = 3, 4, 8

    def pos(tt):
        x, y = g.at(tt)
        return x, y - 22 * math.sin(math.pi * tt)

    def draw(i, t):
        cel.clear()
        for j in range(n):
            a = i - j * gap
            if a < 0 or a > life:
                continue
            tt = a / float(life)
            x, y = pos(tt)
            for q in (2, 1):
                bx, by = pos(max(0.0, tt - q * 0.07))
                rr = 5 - q * 1.4
                cel.put(cv.create_oval(bx - rr, by - rr, bx + rr, by + rr, fill=dark, outline=""))
            cel.put(tongue(cv, x, y + 1, 9, random.uniform(-3, 3), dark, light), orb(cv, x, y + 2, 6.5, light, dark))
            if a == life:
                mini(fx, x, y, 0.8)

    def end():
        cel.clear()
        impact(fx, size=1.0)
    run(fx, (n - 1) * gap + life, draw, end, ms=28)


# ---------------------------------------------------------------- 물
def jet(fx):
    """물줄기: 굵은 물기둥이 뻗어 가 꽂히고, 맞은 자리에서 물이 튄다. 센 기술일수록 굵다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    sp = Sparks(fx)
    p = fx.move.get("power") or 0
    w = 5 if p < 60 else 7 if p < 100 else 10
    n1, n2, n3 = 4, (6 if p < 60 else 9), 3
    mx, my = g.mouth(14)

    def path(t0, t1, ph):
        pts = []
        for s in range(11):
            u = t0 + (t1 - t0) * s / 10.0
            amp = min(1.0, u * 5) * 3.5 * math.sin(u * 11 - ph)
            pts += [mx + (g.tx - mx) * u + g.px * amp, my + (g.ty - my) * u + g.py * amp]
        return pts

    def spray(x, y, up=True):
        a = random.uniform(-math.pi, 0) if up else random.uniform(0, 2 * math.pi)
        v = random.uniform(2.5, 5.5)
        sp.add(lambda px, py, lk: FX._drop(cv, px, py, 2 + 2.5 * lk, light, dark),
               x, y, math.cos(a) * v, math.sin(a) * v - 1.0, life=7, g=0.9)

    def draw(i, t):
        cel.clear()
        if i < n1:
            t0, t1 = 0.0, (i + 1) / float(n1)
        elif i < n1 + n2:
            t0, t1 = 0.0, 1.0
        else:
            t0, t1 = (i - n1 - n2 + 1) / (n3 + 1.0), 1.0
        pts = path(t0, t1, i * 1.4)
        beat = i % 2
        cel.put(cv.create_line(*pts, fill=dark, width=w + 5 + beat, smooth=True, capstyle="round"),
                cv.create_line(*pts, fill=light, width=w + 1, smooth=True, capstyle="round"),
                cv.create_line(*pts, fill=WHITE, width=max(2, w - 4), smooth=True, capstyle="round"))
        if i >= n1 - 1:                                 # 맞은 자리
            rr = 7 + w * 0.5 + 3 * (i % 3)
            cel.put(cv.create_oval(g.tx - rr, g.ty - rr, g.tx + rr, g.ty + rr, fill=WHITE, outline=light, width=2))
            spray(g.tx, g.ty)
            spray(g.tx, g.ty)
        if i % 3 == 0 and i < n1 + n2:
            u = random.uniform(0.2, 0.8)
            spray(mx + (g.tx - mx) * u, my + (g.ty - my) * u, up=False)

    def end():
        cel.clear()
        impact(fx, size=1.15)
    run(fx, n1 + n2 + n3, draw, end)


def bubble(fx):
    """거품이 흔들리며 떠 가서 터진다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    n, gap, life = 9, 2, 11
    seeds = [(random.uniform(-14, 14), random.uniform(0, 6.28), random.uniform(4, 8)) for _ in range(n)]

    def draw(i, t):
        cel.clear()
        for j in range(n):
            a = i - j * gap
            if a < 0 or a > life:
                continue
            tt = a / float(life)
            amp, ph, r = seeds[j]
            x, y = g.at(tt, amp + 6 * math.sin(tt * 9 + ph))
            if a == life:                               # 터진다
                cel.put(spike(cv, x, y, r + 7, 6, WHITE, light, inner=0.5))
                continue
            cel.put(cv.create_oval(x - r, y - r, x + r, y + r, fill=dark, outline=light, width=2),
                    cv.create_oval(x - r * 0.6, y - r * 0.65, x - r * 0.1, y - r * 0.15, fill=WHITE, outline=""))

    def end():
        cel.clear()
        impact(fx, size=0.95)
    run(fx, (n - 1) * gap + life, draw, end)


def surf(fx):
    """파도가 일어나 맞는 쪽을 덮친다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    if "muddy" in key_of(fx.move):
        light, dark = "#d9c28a", "#8a6a3a"
    cel = Cel(fx)
    sp = Sparks(fx)
    k = fx.big
    f = g.face
    n = 15

    def draw(i, t):
        cel.clear()
        x, y = g.at(-0.08 + 1.16 * t)
        y += 26
        grow = min(1.0, (i + 1) / 5.0) * (1.0 if i < n - 2 else 0.6)
        hh, ww = 54 * k * grow, 62 * k

        def wave(sc, back):
            h, w = hh * sc, ww * sc
            bx = x - f * back
            return [bx - f * w, y, bx - f * w * 0.45, y - h * 0.5, bx + f * w * 0.05, y - h * 1.05,
                    bx + f * w * 0.6, y - h * 0.82, bx + f * w * 0.3, y - h * 0.36, bx + f * w * 0.5, y]
        cel.put(cv.create_polygon(*wave(1.0, 0), fill=dark, outline=light, width=2, smooth=True),
                cv.create_polygon(*wave(0.7, 12), fill=light, outline="", smooth=True))
        for j in range(4):                              # 물마루의 거품
            px = x + f * ww * (0.02 + j * 0.13)
            py = y - hh * (0.86 - j * 0.07) + 2 * math.sin(i + j)
            rr = 6 - j
            cel.put(cv.create_oval(px - rr, py - rr, px + rr, py + rr, fill=WHITE, outline=""))
        if i % 2 == 0:
            sp.add(lambda px, py, lk: FX._drop(cv, px, py, 2 + 2 * lk, light, dark),
                   x + f * ww * 0.45, y - hh * 0.75, f * random.uniform(1, 4), -random.uniform(1, 3), life=6, g=0.8)

    def end():
        cel.clear()
        impact(fx, size=1.35)
    run(fx, n, draw, end)



# ---------------------------------------------------------------- 땅 · 바위
def _pebbles(fx, sp, x, y, n=2, typ=None):
    cv = fx.cv
    light, dark = FX.colors(typ or fx.type)
    for q in range(n):
        sp.add(lambda px, py, lk, sd=q: rock(cv, px, py, 2 + 3 * lk, light, dark, sd),
               x, y, random.uniform(-3, 3), -random.uniform(4, 8), life=9, g=1.0)


def quake(fx):
    """지진: 발밑에서 금이 달려가고, 맞는 쪽 땅이 솟구치며 흔들린다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    ink = "#2a1c10"
    cel = Cel(fx)
    sp = Sparks(fx)
    k = fx.big
    gx, gy = g.tx, g.ty + 24
    crack = zig(g.sx, g.sy + 24, gx, gy, 7, 9)
    npts = len(crack) // 2
    spikes = [(0, 44), (-17, 31), (17, 31), (-34, 20), (34, 20)]     # 가운데부터 솟는다
    A, B = 6, 13

    def draw(i, t):
        cel.clear()
        m = max(2, min(npts, int(round(npts * (i + 1) / float(A)))))
        pts = crack[:m * 2]
        if i >= A:                                      # 다 갈라진 뒤에는 떨린다
            pts = [v + random.uniform(-1.2, 1.2) for v in pts]
        cel.put(cv.create_line(*pts, fill=dark, width=7), cv.create_line(*pts, fill=ink, width=3))
        if i < A:
            return
        b = i - A
        for sgn in (-1, 1):                             # 양옆으로 번지는 떨림
            x0 = gx + sgn * 46 * k
            cel.put(cv.create_line(*zig(x0, gy + 3, x0 + sgn * 36 * k, gy + 3, 4, 4), fill=light, width=2))
        for q, (ox, h) in enumerate(spikes):
            age = b - q
            if age < 0:
                continue
            up = ease_out(min(1.0, age / 3.0)) if b < B - 3 else max(0.0, (B - b) / 4.0)
            hh = h * k * up
            x = gx + ox * k
            if hh > 1:
                tip = x + ox * 0.1
                cel.put(cv.create_polygon(x - 9 * k, gy + 4, tip, gy - hh, x + 9 * k, gy + 4,
                                          fill=dark, outline=light, width=2),
                        cv.create_line(x - 2 * k, gy + 2, tip, gy - hh, fill=light, width=1))
            if age == 1:
                _pebbles(fx, sp, x, gy)

    def end():
        cel.clear()
        impact(fx, size=1.2)
    run(fx, A + B, draw, end)


def pillars(fx):
    """스톤에지: 날카로운 돌기둥이 줄지어 솟으며 달려가 꿰뚫는다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    sp = Sparks(fx)
    k = fx.big
    row = [(0.32, 20), (0.56, 28), (0.8, 38), (1.0, 60)]

    def draw(i, t):
        cel.clear()
        for q, (u, h) in enumerate(row):
            age = i - q * 2
            if age < 0:
                continue
            x, y = g.at(u)
            y += 24
            hh = h * k * ease_out(min(1.0, (age + 1) / 2.0))
            w = (7 + q * 2.5) * k
            tip = x + g.face * 5
            cel.put(cv.create_polygon(x - w, y + 3, tip, y - hh, x + w, y + 3, fill=dark, outline=light, width=2),
                    cv.create_polygon(tip, y - hh, x + w, y + 3, x + w * 0.2, y + 3, fill=mix(dark, light, 0.45),
                                      outline=""))
            if age == 0:
                _pebbles(fx, sp, x, y)
        if i == 7:
            impact(fx, size=1.25)                       # 마지막 기둥이 꿰뚫는 순간 (기둥은 선 채로)
    run(fx, 9, draw)


def _rain(fx, make, n=6, gap=2, life=6, spread=30, lean=46, height=150, hit=0.7, final=1.2, streak=None):
    """위에서 쏟아진다 (돌·화살·유성·동전·고드름). make(x, y, 각도, 번호, 나이)."""
    cv = fx.cv
    g = Geo(fx)
    light, _dark = FX.colors(fx.type)
    cel = Cel(fx)
    top = max(-12.0, g.ty - height)                     # 화면 위 끝에서 시작한다
    lean = lean * (g.ty - top) / float(height)
    lands = [(random.uniform(-spread, spread), random.uniform(-6, 14)) for _ in range(n)]

    def draw(i, t):
        cel.clear()
        for j in range(n):
            a = i - j * gap
            if a < 0 or a > life:
                continue
            tt = a / float(life)
            ox, oy = lands[j]
            x1, y1 = g.tx + ox - g.face * lean, top
            x2, y2 = g.tx + ox * 0.6, g.ty + oy
            x, y = x1 + (x2 - x1) * tt, y1 + (y2 - y1) * tt
            ang = math.atan2(y2 - y1, x2 - x1)
            cel.put(cv.create_line(x - math.cos(ang) * 26, y - math.sin(ang) * 26, x, y,
                                   fill=streak or light, width=2))
            cel.put(make(x, y, ang, j, a))
            if a == life:
                mini(fx, x2, y2, hit)

    def end():
        cel.clear()
        impact(fx, size=final)
    run(fx, (n - 1) * gap + life, draw, end)


def rockfall(fx):
    """스톤샤워: 바위가 쏟아진다."""
    light, dark = FX.colors(fx.type)
    _rain(fx, lambda x, y, ang, j, a: rock(fx.cv, x, y, (8 + j % 3 * 2.5) * fx.big, light, dark, j), n=6)


def arrows(fx):
    """사우전드애로: 화살이 비처럼 꽂힌다."""
    cv = fx.cv
    light, dark = FX.colors(fx.type)

    def make(x, y, ang, j, a):
        c, s = math.cos(ang), math.sin(ang)
        return [cv.create_line(x - c * 20, y - s * 20, x, y, fill=light, width=3),
                shard(cv, x, y, 5, ang, WHITE, dark)]
    _rain(fx, make, n=10, gap=1, life=5, spread=34, hit=0.55)


def meteor(fx):
    """용성군: 유성이 꼬리를 끌며 떨어진다."""
    cv = fx.cv
    light, dark = FX.colors(fx.type)

    def make(x, y, ang, j, a):
        c, s = math.cos(ang), math.sin(ang)
        return [rip(cv, x - c * 40, y - s * 40, x + c * 4, y + s * 4, 8, "#ff8a3c", dark),
                rip(cv, x - c * 26, y - s * 26, x + c * 4, y + s * 4, 4, "#ffe27a"),
                orb(cv, x, y, 9 * fx.big, "#ffd27a", dark)]
    _rain(fx, make, n=5, gap=3, life=6, spread=28, hit=0.9, final=1.35, streak=dark)


def coins(fx):
    """골드러시: 금화가 쏟아진다."""
    cv = fx.cv

    def make(x, y, ang, j, a):
        rx = 1.5 + 4.5 * abs(math.cos(a * 1.4 + j))    # 뒤집히며 떨어진다
        out = [cv.create_oval(x - rx, y - 6, x + rx, y + 6, fill="#ffd447", outline="#a87400", width=2)]
        if (a + j) % 3 == 0:
            out.append(glint(cv, x + 3, y - 4, 6))
        return out
    _rain(fx, make, n=12, gap=1, life=6, spread=36, hit=0.5, streak="#ffe9a0")


def icicles(fx):
    """고드름떨구기."""
    cv = fx.cv
    light, dark = FX.colors(fx.type)
    _rain(fx, lambda x, y, ang, j, a: [shard(cv, x, y, 10, ang, light, dark), shard(cv, x, y, 4, ang, WHITE)],
          n=6, lean=10)


def gem(fx):
    """파워젬·원시의힘: 돌이 떠올라 빛나다가 하나씩 쏘아져 나간다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    rocky = "ancient" in key_of(fx.move)
    cel = Cel(fx)
    k = fx.big
    n, gap, life = 5, 2, 5
    A, H = 5, 3
    hover = [(g.sx + ox, g.sy - 34 + oy) for ox, oy in ((-30, 4), (-15, -6), (0, 6), (15, -4), (30, 2))]

    def stone(x, y, j, ang):
        if rocky:
            return rock(cv, x, y, 8 * k, light, dark, j)
        return [shard(cv, x, y, 8 * k, ang, light, dark), shard(cv, x, y, 3.5 * k, ang, WHITE)]

    def draw(i, t):
        cel.clear()
        for j in range(n):
            hx, hy = hover[j]
            start = A + H + j * gap
            if i < A:                                   # 떠오른다
                y0 = g.sy + 24
                cel.put(stone(hx, y0 + (hy - y0) * ease_out((i + 1) / float(A)), j, -math.pi / 2))
            elif i < start:                             # 떠서 빛난다
                y = hy + 2 * math.sin(i * 1.2 + j)
                cel.put(stone(hx, y, j, -math.pi / 2))
                if (i + j) % 3 == 0:
                    cel.put(glint(cv, hx + 5, y - 6, 7))
            elif i - start <= life:                     # 쏘아진다
                a = i - start
                tt = ease_in(a / float(life))
                x, y = hx + (g.tx - hx) * tt, hy + (g.ty - hy) * tt
                cel.put(cv.create_line(hx + (x - hx) * 0.55, hy + (y - hy) * 0.55, x, y, fill=light, width=2),
                        stone(x, y, j, math.atan2(g.ty - hy, g.tx - hx)))
                if a == life:
                    mini(fx, g.tx + (j - 2) * 5, g.ty + (j % 2) * 8 - 4, 0.75)

    def end():
        cel.clear()
        impact(fx, size=1.2)
    run(fx, A + H + (n - 1) * gap + life, draw, end)


def erupt(fx):
    """대지의힘: 발밑이 갈라져 빛나더니 불기둥이 솟는다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    lava, core = "#ff9a3c", "#ffe27a"
    cel = Cel(fx)
    sp = Sparks(fx)
    k = fx.big
    gy = g.ty + 24
    cols = [(0, 66), (-17, 46), (17, 50)]
    A, B = 5, 11

    def draw(i, t):
        cel.clear()
        ln = (16 + 24 * min(1.0, (i + 1) / float(A))) * k
        for a in (-2.7, -0.45, 0.4, 2.75):              # 빛나는 틈
            pts = zig(g.tx, gy, g.tx + math.cos(a) * ln, gy + math.sin(a) * ln * 0.25, 3, 4)
            cel.put(cv.create_line(*pts, fill=dark, width=5),
                    cv.create_line(*pts, fill=core if i % 2 else lava, width=2))
        if i < A:
            return
        b = i - A
        for q, (ox, h) in enumerate(cols):
            age = b - q
            if age < 0:
                continue
            up = ease_out(min(1.0, age / 3.0)) * (1.0 if b < B - 2 else 0.5)
            r = h * k * up * (1 + 0.08 * math.sin(i * 2.0 + q)) / 2.6
            x = g.tx + ox * k
            if r > 2:
                cy = gy - r * 0.9 + 2
                lean = random.uniform(-4, 4)
                cel.put(tongue(cv, x, cy, r, lean, dark),
                        tongue(cv, x, cy + r * 0.25, r * 0.72, lean * 0.7, lava),
                        tongue(cv, x, cy + r * 0.45, r * 0.42, lean * 0.4, core))
            if age == 0:
                _pebbles(fx, sp, x, gy, n=3, typ="GROUND")

    def end():
        cel.clear()
        impact(fx, size=1.25)
    run(fx, A + B, draw, end)


# ---------------------------------------------------------------- 전기
def thunder(fx):
    """번개: 몸에 전기가 감기더니 하늘에서 내리꽂힌다. 깜빡이며 두 번 친다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    k = fx.big
    top = max(-12.0, g.ty - 190)
    A = 4

    def draw(i, t):
        cel.clear()
        if i < A:
            for _q in range(3):
                a = random.uniform(0, 2 * math.pi)
                r = random.uniform(16, 30)
                cel.put(bolt(cv, zig(g.sx, g.sy, g.sx + math.cos(a) * r, g.sy + math.sin(a) * r, 5, 3),
                             light, dark, 1))
            return
        b = i - A
        if b in (0, 1, 2, 3, 5, 6, 8):                  # 깜빡인다
            x0 = g.tx - g.face * 20 + random.uniform(-8, 8)
            pts = zig(x0, top, g.tx, g.ty + 10, 13, 7)
            cel.put(bolt(cv, pts, light, dark, int(round((5 if b < 4 else 3) * k))))
            for _q in range(2):                         # 가지
                q = random.randrange(2, 6) * 2
                sgn = random.choice((-1, 1))
                cel.put(bolt(cv, zig(pts[q], pts[q + 1], pts[q] + sgn * random.uniform(22, 42),
                                     pts[q + 1] + random.uniform(8, 26), 6, 3), light, dark, 1))
        if b < 3:                                       # 꽂힌 자리의 섬광
            r = (32 - b * 8) * k
            cel.put(cv.create_oval(g.tx - r, g.ty + 10 - r * 0.5, g.tx + r, g.ty + 10 + r * 0.5,
                                   fill=WHITE, outline=light, width=3))
        if b >= 2:                                      # 땅을 타고 흩어진다
            for sgn in (-1, 1):
                cel.put(cv.create_line(*zig(g.tx, g.ty + 16, g.tx + sgn * (22 + b * 5),
                                            g.ty + 16 + random.uniform(-4, 4), 4, 4), fill=light, width=2))

    def end():
        cel.clear()
        impact(fx, size=1.3)
    run(fx, A + 9, draw, end, ms=32)


def zap(fx):
    """전격: 지그재그 전기가 깜빡이며 이어진다. 방전은 먼저 사방으로 튄다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    k = fx.big
    radial = any(w in key_of(fx.move) for w in ("discharge", "voltage", "electroweb"))
    mx, my = g.mouth(10)
    wait = 4 if radial else 0

    def draw(i, t):
        cel.clear()
        if radial and i < 6:
            for q in range(7):
                a = q * 0.9 + random.uniform(-0.2, 0.2)
                r = (22 + i * 6) * k
                cel.put(bolt(cv, zig(g.sx, g.sy, g.sx + math.cos(a) * r, g.sy + math.sin(a) * r * 0.8, 6, 4),
                             light, dark, 1))
        if i < wait:
            return
        cel.put(bolt(cv, zig(mx, my, g.tx, g.ty, 11, 8), light, dark, int(round(3 * k))),
                cv.create_line(*zig(mx, my, g.tx, g.ty, 17, 7), fill=WHITE, width=1))
        for _q in range(2):
            a = random.uniform(0, 2 * math.pi)
            r = random.uniform(16, 30)
            cel.put(cv.create_line(*zig(g.tx, g.ty, g.tx + math.cos(a) * r, g.ty + math.sin(a) * r, 5, 3),
                                   fill=light, width=2))
        r = 6 + (i % 3) * 3
        cel.put(cv.create_oval(g.tx - r, g.ty - r, g.tx + r, g.ty + r, fill=WHITE, outline=light, width=2))

    def end():
        cel.clear()
        impact(fx, size=1.1)
    run(fx, wait + 9, draw, end, ms=32)


# ---------------------------------------------------------------- 바람
def tornado(fx):
    """회오리: 바람이 불어 가서 맞는 쪽을 깔때기 모양으로 휘감는다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    k = fx.big
    A = 4
    B = 18 if (fx.move.get("power") or 0) >= 100 else 12
    levels = 7
    base = g.ty + 26

    def draw(i, t):
        cel.clear()
        if i < A + 2:                                   # 불어 가는 바람
            t1 = min(1.0, (i + 1) / float(A))
            t0 = max(0.0, t1 - 0.45)
            for j, off in enumerate((-12, 0, 12)):
                pts = []
                for s in range(5):
                    u = t0 + (t1 - t0) * s / 4.0
                    pts += list(g.at(u, off + 6 * math.sin(u * 8 + j)))
                cel.put(cv.create_line(*pts, fill=light, width=2, smooth=True))
        if i < A:
            return
        b = i - A
        grow = min(1.0, (b + 1) / 4.0) * (1.0 if b < B - 2 else 0.6)
        for j in range(levels):
            f = j / float(levels - 1)
            rx = (7 + 30 * f) * k * grow
            ry = max(2.0, rx * 0.3)
            cx = g.tx + math.sin(b * 0.7 + j * 0.9) * (3 + 7 * f)
            cy = base - f * 66 * k * grow
            st = (b * 47 + j * 61) % 360
            cel.put(cv.create_arc(cx - rx, cy - ry, cx + rx, cy + ry, start=st, extent=210,
                                  style="arc", outline=light, width=3),
                    cv.create_arc(cx - rx, cy - ry, cx + rx, cy + ry, start=st + 220, extent=110,
                                  style="arc", outline=dark, width=2))
        for j in range(4):                              # 말려 올라가는 것들
            f = (b * 0.09 + j * 0.25) % 1.0
            a = b * 0.9 + j * 1.7
            rx = (7 + 30 * f) * k
            x, y = g.tx + math.cos(a) * rx, base - f * 66 * k + math.sin(a) * rx * 0.3
            cel.put(cv.create_line(x - 4, y, x + 4, y - 2, fill=WHITE, width=2))

    def end():
        cel.clear()
        impact(fx, size=1.2)
    run(fx, A + B, draw, end)


# ---------------------------------------------------------------- 폭발
def daimonji(fx):
    """불대문자: 불덩이가 날아가 큰 대(大) 자로 타오른다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    sp = Sparks(fx)
    k = fx.big
    s = 30 * k
    cx, cy = g.tx, g.ty - 2
    hub = (0.0, -0.28)
    arms = [(-1.0, -0.28), (1.0, -0.28), (0.0, -1.0), (-0.82, 0.95), (0.82, 0.95)]
    A, B = 6, 14

    def draw(i, t):
        cel.clear()
        if i < A:                                       # 날아가는 불덩이
            tt = ease_in((i + 1) / float(A))
            x, y = g.at(tt)
            bx, by = g.at(max(0.0, tt - 0.2))
            cel.put(rip(cv, bx, by, x, y, 6, dark, light), orb(cv, x, y, 9 * k, light, dark))
            return
        b = i - A
        f = min(1.0, (b + 1) / 3.0)
        thin = 1.0 if b < B - 3 else (B - b) / 4.0
        wob = [(random.uniform(-2, 2), random.uniform(-2, 2)) for _a in arms]
        for wd, col in ((11, dark), (7, light), (3, "#fff3c0")):    # 겉 - 속 - 심 순서로 겹친다
            for (ax, ay), (wx, wy) in zip(arms, wob):
                x1, y1 = cx + hub[0] * s, cy + hub[1] * s
                x2, y2 = cx + (hub[0] + (ax - hub[0]) * f) * s, cy + (hub[1] + (ay - hub[1]) * f) * s
                cel.put(cv.create_line(x1, y1, (x1 + x2) / 2 + wx, (y1 + y2) / 2 + wy, x2, y2, fill=col,
                                       width=max(1, int(round(wd * k * thin + b % 2))),
                                       capstyle="round", smooth=True))
        if b % 2 == 0 and b < B - 3:                    # 획에서 피어오르는 불꽃
            ax, ay = random.choice(arms)
            u = random.uniform(0.3, 1.0)
            sp.add(lambda px, py, lk, le=random.uniform(-4, 4): tongue(cv, px, py, 3 + 6 * lk, le, light, dark),
                   cx + (hub[0] + (ax - hub[0]) * u) * s, cy + (hub[1] + (ay - hub[1]) * u) * s,
                   0.0, -2.2, life=6)
        if b == 0:
            mini(fx, cx, cy, 1.3)

    def end():
        cel.clear()
        impact(fx, size=1.3)
    run(fx, A + B, draw, end)


def boom(fx):
    """폭발: 번쩍하고 불덩이가 부풀었다 꺼지며 연기가 오른다. 대폭발은 쓰는 쪽에서 터진다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    sp = Sparks(fx)
    if fx.type == "NORMAL":
        light, dark = FX.colors("FIRE")                 # 잿빛 폭발은 폭발 같지 않다
    at_self = any(w in key_of(fx.move) for w in ("explosion", "selfdestruct", "mindblown"))
    k = fx.big * (1.2 if at_self else 1.0)
    x0, y0 = fx.src if at_self else fx.dst
    A = 0 if at_self else 5
    seeds = [random.uniform(0.75, 1.15) for _q in range(14)]

    def blob(r, rot):
        pts = []
        for q in range(14):
            a = rot + 2 * math.pi * q / 14
            rr = r * seeds[q] * (1.0 if q % 2 else 0.78)
            pts += [x0 + math.cos(a) * rr, y0 + math.sin(a) * rr * 0.92]
        return pts

    def draw(i, t):
        cel.clear()
        if i < A:                                       # 날아가는 포탄
            tt = (i + 1) / float(A)
            x, y = g.at(tt)
            bx, by = g.at(max(0.0, tt - 0.2))
            cel.put(rip(cv, bx, by, x, y, 5, dark, light), orb(cv, x, y, 8 * k, light, dark))
            return
        b = i - A
        if b == 0:
            scatter(fx, sp, x0, y0, k * 1.3)
        if b < 11:
            r = (14 + 34 * ease_out(min(1.0, b / 8.0))) * k
            shrink = 1.0 if b < 5 else max(0.0, 1.0 - (b - 4) / 7.0)
            cel.put(cv.create_polygon(*blob(r, b * 0.2), fill=dark, outline="", smooth=True),
                    cv.create_polygon(*blob(r * 0.7 * shrink, b * 0.2 + 0.4), fill=light, outline="", smooth=True))
            if b < 6:
                cel.put(cv.create_polygon(*blob(r * 0.4 * shrink, b * 0.2 + 0.9), fill=WHITE, outline="",
                                          smooth=True))
        if b < 2:
            cel.put(spike(cv, x0, y0, (26 + b * 22) * k, 10, WHITE, light, inner=0.5, rot=b * 0.3, width=2))
        if b >= 3:                                      # 충격 고리
            rr = (20 + (b - 3) * 9) * k
            cel.put(cv.create_oval(x0 - rr, y0 - rr * 0.7, x0 + rr, y0 + rr * 0.7, outline=light,
                                   width=max(1, 5 - (b - 3) // 2)))
        if 4 <= b <= 11 and b % 2 == 0:                 # 연기
            sp.add(lambda px, py, lk: puff(cv, px, py, 5 + 8 * lk, "#8b90a6", "#5c6074"),
                   x0 + random.uniform(-18, 18) * k, y0 - 6, random.uniform(-1, 1), -2.4, life=7)

    def end():
        cel.clear()
        fx.finish()
    run(fx, A + 15, draw, end)



# ---------------------------------------------------------------- 빛
def moon(fx):
    """문포스: 초승달이 떠오르고, 달빛이 모여 구슬이 되어 날아가 터진다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    pale = "#fff6c8"
    cel = Cel(fx)
    k = fx.big
    mx, my = g.sx - g.face * 26, max(15.0, g.sy - 50)       # 쓰는 쪽 뒤 위
    R = 18 * k
    tilt = (math.pi if g.face > 0 else 0.0) - 0.45 * g.face
    A, B, T = 7, 9, 8
    trail = []

    def crescent(y, r):
        return [blade(cv, mx, y, r + 2, tilt, 4.3, r * 0.8, light),
                blade(cv, mx, y, r, tilt, 4.3, r * 0.74, pale)]

    def draw(i, t):
        cel.clear()
        if i < A:                                       # 달이 뜬다
            f = ease_out((i + 1) / float(A))
            cel.put(crescent(my + 16 * (1 - f), R * (0.4 + 0.6 * f)))
        elif i < A + B + 3:
            fade = 1.0 if i < A + B else (A + B + 3 - i) / 4.0
            cel.put(crescent(my, R * fade))
        if i < A + B:
            for j in range(3):                          # 달 둘레의 반짝임
                a = i * 0.5 + j * 2.1
                cel.put(glint(cv, mx + math.cos(a) * (R + 9), my + math.sin(a) * (R + 7),
                              4 + 3 * ((i + j) % 2), WHITE if (i + j) % 2 else pale))
        if A <= i < A + B:                              # 달빛이 모인다
            f = (i - A + 1) / float(B)
            for j in range(6):
                a = j * math.pi / 3 + i * 0.4
                rr = 40 * (1 - f)
                cel.put(glint(cv, mx + math.cos(a) * rr, my + math.sin(a) * rr, 5, pale))
            cel.put(orb(cv, mx, my, (3 + 9 * ease_out(f)) * k, light, dark))
        elif i >= A + B:                                # 쏜다
            tt = ease_in((i - A - B + 1) / float(T))
            x, y = mx + (g.tx - mx) * tt, my + (g.ty - my) * tt
            trail.append((x, y))
            for j, (bx, by) in enumerate(trail[-4:-1]):
                rr = (4 + 2.5 * j) * k
                cel.put(cv.create_oval(bx - rr, by - rr, bx + rr, by + rr, fill=dark, outline=""))
                cel.put(glint(cv, bx + (j - 1) * 5, by - 7 + j * 4, 5, pale))
            cel.put(orb(cv, x, y, 12 * k, light, dark), glint(cv, x, y, 17 * k, WHITE))

    def end():
        cel.clear()
        impact(fx, size=1.35)
    run(fx, A + B + T - 1, draw, end)


def laser(fx):
    """광선: 기운을 모아 굵은 빛줄기를 쏜다. 얼음이면 맞은 자리가 얼고, 오로라면 무지갯빛이다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    key = key_of(fx.move)
    cel = Cel(fx)
    k = fx.big
    p = fx.move.get("power") or 0
    strong = p >= 120 or any(w in key for w in ("solar", "hyper", "meteor", "eterna"))
    rainbow = any(w in key for w in ("aurora", "prismatic", "signal"))
    C, F, R = (10 if strong else 6), (11 if strong else 8), 3
    W = 6 if p < 80 else 8 if p < 120 else 11
    mx, my = g.mouth(18)
    kx, ky = 0.4 + 0.6 * abs(g.uy), 0.4 + 0.6 * abs(g.ux)

    def beam(t1, wk):
        x2, y2 = mx + (g.tx - mx) * t1, my + (g.ty - my) * t1
        out = []
        if rainbow:
            for col, off in (("#ff8ad8", -W * 0.75), ("#8affc1", 0.0), ("#8ad4ff", W * 0.75)):
                out.append(cv.create_line(mx + g.px * off, my + g.py * off, x2 + g.px * off, y2 + g.py * off,
                                          fill=col, width=max(1, int(round(W * 0.8 * wk))), capstyle="round"))
            out.append(cv.create_line(mx, my, x2, y2, fill=WHITE, width=max(1, int(round(W * 0.4 * wk))),
                                      capstyle="round"))
            return out
        for col, ww in ((dark, W + 7), (light, W + 2), (WHITE, max(2, W - 4))):
            out.append(cv.create_line(mx, my, x2, y2, fill=col, width=max(1, int(round(ww * wk))),
                                      capstyle="round"))
        return out

    def draw(i, t):
        cel.clear()
        if i < C:                                       # 모은다
            f = (i + 1) / float(C)
            for j in range(8):
                a = j * math.pi / 4 + i * 0.45
                rr = 46 * (1 - f) + 5
                px, py = mx + math.cos(a) * rr, my + math.sin(a) * rr
                cel.put(cv.create_line(px, py, px + (mx - px) * 0.35, py + (my - py) * 0.35, fill=light, width=2))
            cel.put(orb(cv, mx, my, 2 + (W + 4) * f, light, dark))
            return
        b = i - C
        if b >= F:                                      # 가늘어지며 꺼진다
            cel.put(beam(1.0, 1.0 - (b - F + 1) / float(R + 1)))
            return
        t1 = min(1.0, (b + 1) / 2.0)
        cel.put(beam(t1, 1.18 if b % 2 else 1.0))
        for j in range(2):                              # 줄기를 타고 가는 고리
            u = (b * 0.19 + j * 0.5) % 1.0
            if u < t1:
                x, y = mx + (g.tx - mx) * u, my + (g.ty - my) * u
                rr = W + 4
                cel.put(cv.create_oval(x - rr * kx, y - rr * ky, x + rr * kx, y + rr * ky, outline=WHITE, width=2))
        cel.put(orb(cv, mx, my, (W + 3) * (1.1 if b % 2 else 1.0), light, dark))
        if t1 >= 1.0:
            r = W + 6 + 3 * (b % 2)
            cel.put(orb(cv, g.tx, g.ty, r, WHITE, light))
            for _q in range(3):
                a = random.uniform(0, 2 * math.pi)
                cel.put(cv.create_line(g.tx + math.cos(a) * r, g.ty + math.sin(a) * r,
                                       g.tx + math.cos(a) * (r + 15), g.ty + math.sin(a) * (r + 15),
                                       fill=light, width=2))
            if fx.type == "ICE":                        # 얼어붙는다
                ln = min(26.0, 6 + (b - 1) * 3.5) * k
                for j in range(6):
                    a = j * math.pi / 3 + 0.3
                    cel.put(shard(cv, g.tx + math.cos(a) * ln * 0.6, g.ty + math.sin(a) * ln * 0.6,
                                  ln * 0.45, a, WHITE, dark))

    def end():
        cel.clear()
        impact(fx, size=1.4 if strong else 1.2)
    run(fx, C + F + R, draw, end)


def sparkle(fx):
    """반짝이는 바람 (요정의바람·은빛바람·얼어붙은바람)."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    k = fx.big
    n, life = 16, 9
    parts = []

    def lane(u, off, i, ph):
        return g.at(u, off + 7 * math.sin(u * 9 - i * 0.8 + ph))

    def draw(i, t):
        cel.clear()
        t1 = min(1.0, (i + 1) / 6.0)
        t0 = max(0.0, (i - n + 6) / 6.0)
        if t0 < t1:
            for j, off in enumerate((-15, 0, 15)):
                pts = []
                for s in range(7):
                    pts += list(lane(t0 + (t1 - t0) * s / 6.0, off, i, j * 2))
                cel.put(cv.create_line(*pts, fill=dark if j == 1 else light, width=2, smooth=True))
        if i < n - life + 2:
            for _q in range(2):
                parts.append([0, random.choice((-15, 0, 15)), random.uniform(0, 6.28)])
        for q in parts:
            q[0] += 1
        parts[:] = [q for q in parts if q[0] <= life]
        for q in parts:
            x, y = lane(q[0] / float(life), q[1], i, q[2])
            r = (4 + 4 * abs(math.sin(q[0] * 1.3 + q[2]))) * k
            cel.put(glint(cv, x, y, r, WHITE if q[0] % 2 else light))

    def end():
        cel.clear()
        impact(fx, size=1.1)
    run(fx, n, draw, end)


def flash(fx):
    """섬광: 몸에서 빛살이 뻗어 나가고 맞는 쪽이 눈부시게 반짝인다."""
    cv = fx.cv
    sx, sy = fx.src
    tx, ty = fx.dst
    light, _dark = FX.colors(fx.type)
    cel = Cel(fx)
    k = fx.big

    def draw(i, t):
        cel.clear()
        if i < 9:
            ln = (18 + 62 * ease_out(min(1.0, (i + 1) / 5.0))) * k
            thin = 1.0 if i < 6 else (9 - i) / 4.0
            w = 0.2 * thin
            for j in range(12):
                a = j * math.pi / 6 + i * 0.06
                far = ln * (1.0 if j % 2 else 0.66)
                cel.put(cv.create_polygon(sx + math.cos(a - w) * 10, sy + math.sin(a - w) * 10,
                                          sx + math.cos(a) * far, sy + math.sin(a) * far,
                                          sx + math.cos(a + w) * 10, sy + math.sin(a + w) * 10,
                                          fill=WHITE if j % 2 else light, outline=""))
            cel.put(glint(cv, sx, sy, (22 + 6 * (i % 2)) * k * thin, WHITE))
        if i >= 4:
            for j in range(3):
                a = i * 0.9 + j * 2.1
                cel.put(glint(cv, tx + math.cos(a) * 18, ty + math.sin(a) * 14,
                              (7 + 5 * ((i + j) % 2)) * k, WHITE if (i + j) % 2 else light))

    def end():
        cel.clear()
        impact(fx, size=1.2)
    run(fx, 11, draw, end)


# ---------------------------------------------------------------- 지키는 기술
def shield(fx):
    """방어: 몸 앞에 육각 방패가 펼쳐진다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = "#b8fff0", "#35b89c"
    cel = Cel(fx)
    cx, cy = g.mouth(22)
    n = 15

    def hexa(r):
        pts = []
        for q in range(6):
            a = math.pi / 6 + q * math.pi / 3
            pts += [cx + math.cos(a) * r, cy + math.sin(a) * r]
        return pts

    def draw(i, t):
        cel.clear()
        s = (0.35, 0.8, 1.14, 1.0)[i] if i < 4 else 1.0 + 0.04 * math.sin(i * 1.6)
        if i > n - 3:
            s *= (n - i + 1) / 4.0
        r = 30 * s
        out, inn = hexa(r), hexa(r * 0.6)
        cel.put(cv.create_polygon(*out, fill="", outline=dark, width=5),
                cv.create_polygon(*out, fill="", outline=light, width=2),
                cv.create_polygon(*inn, fill="", outline=light, width=1))
        for q in range(6):
            cel.put(cv.create_line(inn[q * 2], inn[q * 2 + 1], out[q * 2], out[q * 2 + 1], fill=light, width=1))
        if 4 <= i <= 9:                                 # 훑고 지나가는 빛
            x = cx - r + 2 * r * (i - 4) / 5.0
            cel.put(cv.create_line(x - 6, cy + r * 0.6, x + 6, cy - r * 0.6, fill=WHITE, width=3))
        if i in (3, 4, 5):
            cel.put(glint(cv, cx + r * 0.5, cy - r * 0.55, 12 - (i - 3) * 3))

    def end():
        cel.clear()
        fx.finish()
    run(fx, n, draw, end)


def wall(fx):
    """리플렉터·빛의장막: 몸 앞에 빛나는 벽이 선다."""
    cv = fx.cv
    g = Geo(fx)
    key = key_of(fx.move)
    light, dark = (("#cfe6ff", "#5a8fe0") if "reflect" in key else
                   ("#fff3b0", "#e0b040") if "lightscreen" in key else
                   ("#e8d8ff", "#8a7bff") if "aurora" in key else ("#e6ffe9", "#58c07a"))
    cel = Cel(fx)
    cx, cy = g.mouth(24)
    n = 15

    def draw(i, t):
        cel.clear()
        grow = min(1.0, (i + 1) / 4.0) * (1.0 if i < n - 2 else 0.5)
        hh, ww = 34 * grow, 9
        sk = 6 * g.face                                 # 비스듬히 선 판
        pts = [cx - ww + sk, cy - hh, cx + ww + sk, cy - hh + 5, cx + ww - sk, cy + hh, cx - ww - sk, cy + hh - 5]
        cel.put(cv.create_polygon(*pts, fill="", outline=dark, width=5),
                cv.create_polygon(*pts, fill="", outline=light, width=2))
        for j in range(3):                              # 판을 타고 오르는 빛
            u = ((i * 0.12 + j * 0.34) % 1.0) * 2 - 1
            y = cy + hh * u * 0.85
            cel.put(cv.create_line(cx - ww * 0.7, y + 4, cx + ww * 0.7, y - 4, fill=WHITE if j == 0 else light,
                                   width=2))
        if i in (3, 4, 5):
            cel.put(glint(cv, cx + sk, cy - hh, 13 - (i - 3) * 3))

    def end():
        cel.clear()
        fx.finish()
    run(fx, n, draw, end)


# ---------------------------------------------------------------- 얼음 · 독
def blizzard(fx):
    """눈보라: 눈과 얼음 조각이 바람을 타고 휩쓸고, 맞는 쪽에 눈 결정이 얼어붙는다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    k = fx.big
    n, life = 18, 8
    parts = []

    def draw(i, t):
        cel.clear()
        for j, off in enumerate((-26, -9, 9, 26)):      # 바람
            u0 = (i * 0.13 + j * 0.27) % 1.2 - 0.1
            pts = []
            for s in range(5):
                u = u0 + 0.3 * s / 4.0
                pts += list(g.at(u, off + 5 * math.sin(u * 7 + j)))
            cel.put(cv.create_line(*pts, fill=light, width=2, smooth=True))
        if i < n - life:
            for _q in range(4):
                parts.append([0, random.uniform(-34, 34), random.random() < 0.3, random.uniform(0, 6.28)])
        for q in parts:
            q[0] += 1
        parts[:] = [q for q in parts if q[0] <= life]
        for q in parts:
            u = q[0] / float(life) * 1.15
            x, y = g.at(u, q[1] + 6 * math.sin(u * 8 + q[3]))
            if q[2]:
                cel.put(shard(cv, x, y, 5 * k, q[3] + q[0] * 0.8, WHITE, dark))
            else:
                r = 1.5 + q[3] % 2.0
                cel.put(cv.create_oval(x - r, y - r, x + r, y + r, fill=WHITE, outline=""))
        if i >= 7:                                      # 눈 결정
            ln = min(24.0, (i - 6) * 3.0) * k
            for j in range(6):
                a = j * math.pi / 3 + 0.26
                c, s_ = math.cos(a), math.sin(a)
                cel.put(cv.create_line(g.tx, g.ty, g.tx + c * ln, g.ty + s_ * ln, fill=WHITE, width=2))
                bx, by = g.tx + c * ln * 0.6, g.ty + s_ * ln * 0.6
                for sg in (-1, 1):
                    cel.put(cv.create_line(bx, by, bx + math.cos(a + sg * 0.9) * ln * 0.32,
                                           by + math.sin(a + sg * 0.9) * ln * 0.32, fill=light, width=2))

    def end():
        cel.clear()
        impact(fx, size=1.2)
    run(fx, n, draw, end)


def sludge(fx):
    """오물: 출렁이는 덩어리가 날아가 철퍽 퍼지고, 방울이 흘러내리며 거품이 인다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    sp = Sparks(fx)
    k = fx.big
    A = 9
    seeds = [random.uniform(0, 6.28) for _q in range(8)]

    def gob(x, y, r, i):
        pts = []
        for q in range(8):
            a = 2 * math.pi * q / 8
            rr = r * (0.85 + 0.25 * math.sin(seeds[q] + i * 1.1))
            pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
        return [cv.create_polygon(*pts, fill=dark, outline=light, width=2, smooth=True),
                cv.create_oval(x - r * 0.45, y - r * 0.5, x - r * 0.05, y - r * 0.1, fill=light, outline="")]

    def drip(x, y, vy):
        sp.add(lambda px, py, lk: FX._drop(cv, px, py, 2 + 2.5 * lk, light, dark), x, y, 0.0, vy, life=7, g=0.5)

    def draw(i, t):
        cel.clear()
        if i <= A:
            tt = i / float(A)
            x, y = g.at(tt)
            y -= 34 * math.sin(math.pi * tt)
            cel.put(gob(x, y, 13 * k, i))
            if i % 2:
                drip(x, y + 6, 1.5)
            return
        b = i - A
        r = (16 + 14 * ease_out(min(1.0, b / 3.0))) * k
        pts = []
        for q in range(16):                             # 철퍽
            a = 2 * math.pi * q / 16
            rr = r * (1.0 if q % 2 else 0.5) * (0.85 + 0.2 * math.sin(seeds[q % 8] * 3))
            pts += [g.tx + math.cos(a) * rr, g.ty + math.sin(a) * rr * 0.8]
        cel.put(cv.create_polygon(*pts, fill=dark, outline=light, width=2, smooth=True))
        if b == 1:
            for _q in range(4):
                drip(g.tx + random.uniform(-18, 18), g.ty + 6, 1.0)
                sp.add(lambda px, py, lk: cv.create_oval(px - 2 - 4 * lk, py - 2 - 4 * lk, px + 2 + 4 * lk,
                                                         py + 2 + 4 * lk, fill=dark, outline=light, width=2),
                       g.tx + random.uniform(-16, 16), g.ty, random.uniform(-0.5, 0.5), -1.8, life=8)

    def end():
        cel.clear()
        impact(fx, size=1.05)
    run(fx, A + 6, draw, end)


# ---------------------------------------------------------------- 휘두르는 것 · 연속기
def hammer(fx):
    """해머: 큰 망치를 뒤로 젖혔다가 내리찍는다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    k = fx.big
    f = g.face
    px, py = g.tx - f * 44, g.ty + 22
    L = 52 * k

    def swing(i):                                       # 도: 0 = 맞는 쪽 수평, 음수 = 위
        if i < 4:
            return -75 - 45 * ease_out((i + 1) / 4.0)
        return -120 + 97 * ease_in(min(1.0, (i - 3) / 3.0))

    def draw(i, t):
        cel.clear()
        a = math.radians(swing(i))
        dx, dy = f * math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        hx, hy = px + dx * L, py + dy * L
        if 4 <= i <= 6:                                 # 휘두른 자리
            cel.put(cv.create_arc(px - L, py - L, px + L, py + L, start=-math.degrees(math.atan2(dy, dx)),
                                  extent=44 * f, style="arc", outline=light, width=4))
        cel.put(cv.create_line(px, py, hx, hy, fill="#6b4a2a", width=5, capstyle="round"))
        hw, hl = 9 * k, 17 * k
        pts = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            pts += [hx + dx * hw * su + nx * hl * sv, hy + dy * hw * su + ny * hl * sv]
        cel.put(cv.create_polygon(*pts, fill=dark, outline=light, width=2),
                cv.create_line(hx - dx * hw * 0.3 - nx * hl * 0.7, hy - dy * hw * 0.3 - ny * hl * 0.7,
                               hx - dx * hw * 0.3 + nx * hl * 0.7, hy - dy * hw * 0.3 + ny * hl * 0.7,
                               fill=WHITE, width=2))
        if i == 7:
            impact(fx, size=1.4)                        # 망치는 찍힌 채로 남는다
    run(fx, 9, draw)


def needles(fx):
    """바늘: 가는 침이 연달아 꽂힌다."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    n, gap, life = 4, 2, 5

    def draw(i, t):
        cel.clear()
        for j in range(n):
            a = i - j * gap
            if a < 0 or a > life:
                continue
            off = (j - (n - 1) / 2.0) * 7
            x, y = g.at(a / float(life), off)
            cel.put(cv.create_line(x - g.ux * 18, y - g.uy * 18, x, y, fill=light, width=2),
                    shard(cv, x, y, 6, g.ang, WHITE, dark))
            if a == life:
                mini(fx, g.tx + off * 0.8, g.ty + off * 0.5, 0.6)

    def end():
        cel.clear()
        impact(fx, size=0.95)
    run(fx, (n - 1) * gap + life, draw, end)


# 닿지 않는 연속기가 날리는 것
_SHOTS = {"WATER": "star", "ICE": "shard", "DRAGON": "shard", "BUG": "shard", "POISON": "shard",
          "STEEL": "shard", "ROCK": "rock", "GROUND": "rock", "GRASS": "seed"}


def _volley(fx, kind, n=4, final=1.0):
    """여러 발을 연달아 날린다. kind: star(표창) / shard / rock / seed / orb."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    k = max(1.0, fx.big)                                # 한 발의 위력은 낮아도 작게 그리지 않는다
    cel = Cel(fx)
    gap, life = 3, 6

    def draw(i, t):
        cel.clear()
        for j in range(n):
            a = i - j * gap
            if a < 0 or a > life:
                continue
            tt = a / float(life)
            x, y = g.at(tt, ((j % 2) * 2 - 1) * 8 * math.sin(math.pi * tt))
            if kind == "star":
                cel.put(spike(cv, x, y, 11 * k, 4, light, dark, inner=0.35, rot=a * 1.1 + j),
                        cv.create_oval(x - 2, y - 2, x + 2, y + 2, fill=WHITE, outline=""))
            elif kind == "shard":
                cel.put(cv.create_line(x - g.ux * 16, y - g.uy * 16, x, y, fill=light, width=2),
                        shard(cv, x, y, 7 * k, g.ang, light, dark), shard(cv, x, y, 3 * k, g.ang, WHITE))
            elif kind == "rock":
                y -= 16 * math.sin(math.pi * tt)        # 돌은 포물선으로
                cel.put(rock(cv, x, y, 8 * k, light, dark, j))
            elif kind == "seed":
                cel.put(cv.create_oval(x - 4, y - 3, x + 4, y + 3, fill=light, outline=dark, width=2))
            else:
                cel.put(orb(cv, x, y, 6 * k, light, dark))
            if a == life:
                mini(fx, g.tx + (j - 1.5) * 6, g.ty + (j * 7) % 11 - 5, 0.75)

    def end():
        cel.clear()
        impact(fx, size=final)
    run(fx, (n - 1) * gap + life, draw, end)


def multi(fx):
    """연속기: 닿는 기술은 달려들어 여러 번 때리고, 아니면 여러 발을 날린다 (물수리검은 표창)."""
    g = Geo(fx)
    n = 4
    if "contact" not in (fx.move.get("flags") or []):
        return _volley(fx, _SHOTS.get(fx.type, "orb"), n)

    def strike():
        def one(i):
            if fx.dead:
                return
            if i >= n:
                return fx.after(60, lambda: impact(fx, size=1.0))
            a = i * 2.2 + 0.6
            mini(fx, g.tx + math.cos(a) * 16, g.ty + math.sin(a) * 13, 0.9)
            fx.after(75, lambda: one(i + 1))
        one(0)
    fx.st.lunge(fx.who, strike)


def rocks(fx):
    """돌덩이 여러 개를 던진다 (암석포·바위깨기처럼 이름에 바위가 든 나머지 기술)."""
    _volley(fx, "rock", 4, final=1.1)


def recoil(fx):
    """몸을 던지는 기술: 기운을 두르고 돌진해 크게 터지고, 나도 아프다."""
    cv = fx.cv
    sx, sy = fx.src
    light, dark = FX.colors(fx.type)
    cel = Cel(fx)
    k = fx.big

    def draw(i, t):
        cel.clear()
        for j in range(5):
            ph = i * 0.9 + j * 1.26
            r = (8 + 4 * math.sin(i * 1.3 + j)) * k * min(1.0, (i + 2) / 5.0)
            cel.put(tongue(cv, sx + math.cos(ph) * 18, sy + 20 - r * 0.3, r, 4 * math.sin(ph), dark, light))
        rr = 32 - i * 2.4
        cel.put(cv.create_oval(sx - rr, sy - rr * 0.8, sx + rr, sy + rr * 0.8, outline=light, width=2))

    def go():
        cel.clear()

        def strike():
            if fx.dead:
                return
            scatter(fx, Sparks(fx), sx, sy, 0.6, n=4)   # 반동
            impact(fx, size=1.45)
        fx.st.lunge(fx.who, strike)
    run(fx, 8, draw, go)



# ---------------------------------------------------------------- 주먹 · 발 · 찌르기 · 흡수
def punch(fx):
    """주먹: 달려들어 주먹을 꽂는다."""
    def strike():
        if fx.dead:
            return
        cv = fx.cv
        g = Geo(fx)
        light, dark = FX.colors(fx.type)
        cel = Cel(fx)
        k = fx.big
        c, s = math.cos(g.ang), math.sin(g.ang)

        def rot(x, y, dx, dy):
            return [x + dx * c - dy * s, y + dx * s + dy * c]

        def draw(i, t):
            cel.clear()
            back = (26, 10, 0)[min(i, 2)]
            x, y = g.tx - g.ux * back, g.ty - g.uy * back
            r = (11 + 3 * min(i, 2)) * k
            for off in (-8, 0, 8):                      # 뒤로 뻗는 줄
                cel.put(cv.create_line(*(rot(x, y, -r - 28, off) + rot(x, y, -r - 2, off)),
                                       fill=light, width=3, capstyle="round"))
            pts = []
            for dx, dy in ((-1, -1), (0, -1.08), (1, -1), (1.1, 0), (1, 1), (0, 1.08), (-1, 1), (-1.05, 0)):
                pts += rot(x, y, dx * r, dy * r)
            cel.put(cv.create_polygon(*pts, fill=light, outline=dark, width=2, smooth=True))
            for off in (-0.45, 0.0, 0.45):              # 손가락 마디
                cel.put(cv.create_line(*(rot(x, y, r * 0.35, off * r) + rot(x, y, r * 0.95, off * r)),
                                       fill=dark, width=2))

        def end():
            cel.clear()
            impact(fx, size=1.15)
        run(fx, 3, draw, end, ms=28)
    fx.st.lunge(fx.who, strike)


def kick(fx):
    """발차기: 달려들어 크게 돌려 찬다."""
    def strike():
        if fx.dead:
            return
        _sweep(fx, lambda: impact(fx, size=1.15), mirror=True, thick=22, span=2.1)
    fx.st.lunge(fx.who, strike)


def stab(fx):
    """찌르기: 뾰족한 것이 과녁을 꿰뚫고 들어간다."""
    def thrust():
        if fx.dead:
            return
        cv = fx.cv
        g = Geo(fx)
        light, dark = FX.colors(fx.type)
        cel = Cel(fx)
        k = fx.big

        def draw(i, t):
            cel.clear()
            tip = (-22, 2, 14)[min(i, 2)]
            x, y = g.tx + g.ux * (tip - 30 * k), g.ty + g.uy * (tip - 30 * k)
            for off in (-9, 9):
                cel.put(cv.create_line(x - g.ux * 40 + g.px * off, y - g.uy * 40 + g.py * off,
                                       x - g.ux * 8 + g.px * off, y - g.uy * 8 + g.py * off, fill=light, width=2))
            cel.put(shard(cv, x, y, 20 * k, g.ang, light, dark), shard(cv, x, y, 9 * k, g.ang, WHITE))

        def end():
            cel.clear()
            impact(fx, size=1.1)
        run(fx, 3, draw, end, ms=28)
    if "contact" in (fx.move.get("flags") or []):
        fx.st.lunge(fx.who, thrust)
    else:
        thrust()


def drain(fx):
    """흡수: 맞는 쪽에서 기운이 빨려 나와 내게 흘러든다. 드레인키스는 하트."""
    cv = fx.cv
    g = Geo(fx)
    light, dark = FX.colors(fx.type)
    kiss = "kiss" in key_of(fx.move)
    cel = Cel(fx)
    sp = Sparks(fx)
    n, gap, life = 7, 2, 9
    amps = [(-1 if j % 2 else 1) * random.uniform(8, 22) for j in range(n)]
    mini(fx, g.tx, g.ty, 1.0)

    def draw(i, t):
        cel.clear()
        if i < 5:                                       # 빨려 나오는 자리
            r = 26 - i * 4
            cel.put(cv.create_oval(g.tx - r, g.ty - r * 0.8, g.tx + r, g.ty + r * 0.8, outline=light, width=2))
        for j in range(n):
            a = i - 2 - j * gap
            if a < 0 or a > life:
                continue
            tt = a / float(life)
            x, y = g.at(1 - tt, amps[j] * math.sin(math.pi * tt))
            cel.put(heart(cv, x, y, 6, light, dark) if kiss else orb(cv, x, y, 5, light, dark))
            if a == life:                               # 내 몸에 스며든다
                sp.add(lambda px, py, lk: glint(cv, px, py, 3 + 6 * lk, "#9dffc0"),
                       g.sx + random.uniform(-14, 14), g.sy + random.uniform(-4, 16), 0.0, -1.6, life=7)

    def end():
        cel.clear()
        fx.after(120, fx.finish)
    run(fx, 2 + (n - 1) * gap + life, draw, end)


STYLES = {
    "hit": hit, "flurry": flurry, "dash": dash, "phantom": phantom,
    "slash": slash, "blades": blades, "claw": claw,
    "pulse": pulse, "ball": ball, "leaf": leaf, "whip": whip, "psy": psy,
    "flame": flame, "ember": ember, "jet": jet, "bubble": bubble, "surf": surf,
    "quake": quake, "pillars": pillars, "rockfall": rockfall, "arrows": arrows, "meteor": meteor,
    "coins": coins, "icicles": icicles, "gem": gem, "erupt": erupt,
    "thunder": thunder, "zap": zap, "tornado": tornado, "daimonji": daimonji, "boom": boom,
    "moon": moon, "laser": laser, "sparkle": sparkle, "flash": flash, "shield": shield, "wall": wall,
    "blizzard": blizzard, "sludge": sludge, "hammer": hammer, "needles": needles, "multi": multi,
    "recoil": recoil, "punch": punch, "kick": kick, "stab": stab, "drain": drain,
    "rock": rocks,
}
