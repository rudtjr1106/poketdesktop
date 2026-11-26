# -*- coding: utf-8 -*-
"""기술 연출 고르기 · 컷인 — 연출 자체는 갈래별 파일에 있다.

    pick(move, base)   이 기술이 쓸 연출 이름 (battle_fx 가 고른 갈래 base 를 받아 더 좁힌다)
    STYLES[이름](fx)   연출 하나. fx 는 battle_fx.Effect - 시간표(fx.show)에 장면을 넣기만 하면 된다
    cutin(fx, then)    Z기술 · 아주 센 기술 앞에 지나가는 띠

    fx_kit.py      연장: 시간표 · 붓 · 색 · 도형 · 조각 · 맞는 순간
    fx_melee.py    몸으로 치는 것 (달려들어 치기 · 베기 · 물기 · 주먹 ...)
    fx_ranged.py   날아가는 것 · 쏟아지는 것 · 솟는 것 (광선 · 구슬 · 번개 · 지진 ...)
    fx_status.py   변화기 (랭크 · 회복 · 상태이상 · 방어 · 날씨 ...)

**연출은 조합으로 고른다.** 기술 900여 개를 하나하나 그릴 수는 없으니

    전하는 법  (달려든다 · 던진다 · 뿜는다 · 쏜다 · 떨어진다 · 솟는다 · 건다)   <- 이름의 낱말 · 플래그 · 분류
    타입      (색 다섯 단 · 조각 · 맞은 자리의 모습)                           <- fx_kit.PAL / MOTE / IMPACT_KIND
    세기      (위력대 · 급소 · 효과)                                          <- fx.big / fx.crit / fx.eff

를 곱한다. 거기에 많이 쓰이는 기술은 이름으로 못 박아 그 기술답게 그린다 (EXACT).

눈으로 보려면: python tools/fx_gallery.py (창) · python tools/fx_preview.py 파괴광선 --out 폴더 (그림)
"""
import math
import random

from . import fx_kit as K
from . import ui_common as U

WHITE = K.WHITE
GOLD = K.GOLD
CUT_BG = "#0e1018"              # 컷인 띠 (바탕화면 레이어의 투명색 #fe01fe 와 멀다)
MS = K.MS


# ---------------------------------------------------------------- 연출 고르기
# 영문 이름(글자·숫자만, 소문자)으로 못 박는 기술들. 낱말 규칙보다 먼저 본다.
_EXACT_GROUPS = {
    "moon": "moonblast",
    "daimonji": "fireblast",
    "ember": "ember",
    "flame": "flamethrower heatwave inferno overheat fierydance mysticalfire incinerate burnup blueflare "
             "sacredfire searingshot dragonbreath",
    "surf": "surf muddywater",
    "bubble": "bubble bubblebeam",
    "jet": "watergun hydropump hydrocannon scald brine waterspout steameruption snipeshot originpulse",
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
             "photongeyser nihillight gigaimpact",
    "sparkle": "fairywind silverwind icywind ominouswind dazzlinggleam",
    "blizzard": "blizzard powdersnow glaciate sheercold",
    "sludge": "sludgebomb sludge sludgewave acidspray venoshock acid gunkshot belch",
    "needles": "poisonsting pinmissile barbbarrage",
    "shield": "protect detect kingsshield spikyshield banefulbunker obstruct silktrap "
              "burningbulwark wideguard quickguard craftyshield endure matblock",
    "wall": "reflect lightscreen auroraveil safeguard mist luckychant",
    "gem": "powergem ancientpower diamondstorm",
    "whip": "vinewhip powerwhip firelash",
    "psy": "psychic psyshock psystrike confusion extrasensory futuresight expandingforce",
    "leafstorm": "leafstorm razorleaf magicalleaf petalblizzard",
    "weather": "sunnyday raindance sandstorm hail snowscape",
    "hazard": "stealthrock spikes toxicspikes stickyweb",
    "wisp": "willowisp",
    "roost": "roost",
}
EXACT = {}
for _style, _names in _EXACT_GROUPS.items():
    for _n in _names.split():
        EXACT[_n] = _style

# 이름으로 못 잡은 특수기 ('뿜는 것') 는 타입이 모양을 고른다
STREAM = {
    "NORMAL": "nova", "FIRE": "flame", "WATER": "jet", "ELECTRIC": "zap", "GRASS": "leafstorm",
    "ICE": "blizzard", "FIGHTING": "aura", "POISON": "sludge", "GROUND": "erupt", "FLYING": "wind",
    "PSYCHIC": "psy", "BUG": "swarm", "ROCK": "gem", "GHOST": "flame", "DRAGON": "flame",
    "DARK": "pulse", "STEEL": "laser", "FAIRY": "sparkle",
}
FALLBACK = "nova"               # 모르는 갈래가 오면


key_of = K.key_of


def pick(move, base):
    """기술의 연출을 고른다. base 는 battle_fx 가 고른 갈래."""
    style = EXACT.get(key_of(move))
    if style:
        return style
    if (move.get("cat") or "status") == "status":
        return base
    flags = move.get("flags") or []
    if (move.get("pri") or 0) > 0 and (move.get("power") or 0) > 0 and base in ("hit", "punch", "stream", "shot",
                                                                                "ice"):
        return "dash"                       # 선공기는 스치고 지나간다
    if base == "slash" and "contact" not in flags:
        return "blades"                     # 닿지 않는 베기는 칼날이 날아간다
    if base == "stream":
        return STREAM.get(move.get("type"), FALLBACK)
    return base


# ---------------------------------------------------------------- 컷인 (1.13.2)
# 이 위력부터 쓰기 직전에 컷인을 띄운다 (Z기술은 늘). 위력 130 = 오버히트 · 용성군 · 리프스톰 ... - 판마다 몇 번
# 안 나오는 한 방이라 눈에 띄어도 거슬리지 않는다. 100 이나 120 으로 낮추면 인파이트 · 플레어드라이브처럼
# 랜덤 배틀에서 늘 쓰는 기술마다 떠서 판이 늘어진다.
CUTIN_POWER = 130
CUTIN_MS = 430


def wants_cutin(fx):
    """이 기술에 컷인을 띄우나 - Z기술, 또는 위력 CUTIN_POWER 이상인 공격기."""
    if getattr(fx, "zmove", False):
        return True
    m = fx.move or {}
    return (m.get("cat") or "status") != "status" and (m.get("power") or 0) >= CUTIN_POWER


def cutin(fx, then):
    """쓰기 직전에 두 포켓몬 사이로 비스듬한 띠가 열리고 기술 이름이 뜬다. CUTIN_MS 뒤 then().

    띠는 쓰는 쪽에서부터 칼로 긋듯 열려서(누가 쓰는지 보인다) 잠깐 머물고, 위아래로 접히며 사라진다. 띠 위아래로
    타입 색 날이 서고, 안에는 반대쪽으로 흐르는 빛줄이 지나간다. Z기술은 이름이 금빛이다.
    """
    sh = fx.show
    g, c = fx.geo, fx.c
    name = fx.label or (fx.move or {}).get("kr") or ""
    zm = bool(getattr(fx, "zmove", False))
    x1, x2 = min(g.sx, g.tx) - 80, max(g.sx, g.tx) + 80
    cy = (g.sy + g.ty) / 2.0
    hh = 18 * min(fx.big, 1.2)
    slant = 16
    left = g.sx <= g.tx                                 # 쓰는 쪽이 왼쪽이면 왼쪽부터 열린다
    font = (U.FAMILY, U.pt(15 if zm else 13), "bold")
    # 흐르는 줄은 띠의 위 · 아래 가장자리 쪽으로만 지나간다 - 가운데의 기술 이름을 가로지르지 않게
    streaks = [(random.uniform(0, 1), random.choice((-1, 1)) * random.uniform(0.5, 0.8), random.uniform(20, 46))
               for _ in range(7)]
    edge = GOLD if zm else c.light

    def draw(p, u, ms):
        open_ = K.out3(ms / 110.0)
        h = hh * (1.0 if ms < 330 else max(0.0, 1.0 - (ms - 330) / 90.0))
        if h <= 1:
            return
        w = (x2 - x1) * open_
        a, b = (x1, x1 + w) if left else (x2 - w, x2)
        # 타입 색 날 (띠보다 조금 넓게 깔린다) - 그 위에 어두운 띠
        p.poly([a + slant - 8, cy - h - 4, b + slant + 8, cy - h - 4, b - slant + 8, cy + h + 4,
                a - slant - 8, cy + h + 4], c.base if not zm else "#b8860b")
        p.poly([a + slant, cy - h, b + slant, cy - h, b - slant, cy + h, a - slant, cy + h], CUT_BG, edge, 2)
        for q, (s0, v, ln) in enumerate(streaks):       # 띠 안을 반대쪽으로 흐르는 빛줄
            px = a + ((s0 - ms / 260.0 * (1 if left else -1)) % 1.0) * (b - a)
            py = cy + v * h
            x_ = px + (ln if left else -ln)
            if min(px, x_) > a and max(px, x_) < b:
                K.streak(p, px, py, x_, py, 1.6, edge if q % 2 else c.base)
        if ms < 150:                                    # 여는 끝의 번쩍임
            hx = b if left else a
            K.glint(p, hx, cy, 16 * (1.2 - ms / 150.0), WHITE)
        if 70 <= ms <= 360 and name and open_ > 0.5:
            tx = (a + b) / 2.0
            p.text(tx + 2, cy + 2, name, "#000000", font)
            p.text(tx, cy, name, GOLD if zm else WHITE, font)

    def go():
        sh.rebase()
        then()
    sh.act(0, CUTIN_MS, draw, z=9)
    sh.cue(CUTIN_MS, go)


# ---------------------------------------------------------------- 연출 모음
from . import fx_melee, fx_ranged, fx_status                 # noqa: E402

STYLES = {}
STYLES.update(fx_melee.STYLES)
STYLES.update(fx_ranged.STYLES)
STYLES.update(fx_status.STYLES)


def impact(fx, at=None, done=None, size=1.0, typ=None):
    """맞는 순간 (옛 이름 - 숨는 기술 연출이 부른다). 시간표에 충격을 얹고, 끝나면 연출이 끝난다."""
    fx.show.rebase()
    K.impact(fx, 0, where=at, size=size, typ=typ)
    if done:
        fx.show.done = done


# ---------------------------------------------------------------- 옛 연장 (숨는 기술 연출 vanish_fx 가 쓴다)
# vanish_fx 는 도트를 숨기고 옮기는 박자가 엔진의 숨김 기록과 맞물려 있어서 그대로 두었다. 그쪽이 쓰는
# 캔버스 직접 그리기 도구만 여기 남긴다 (새 연출은 fx_kit 의 붓으로 그린다).
mix = K.mix


def ease_out(t):
    return 1.0 - (1.0 - t) ** 2


def ease_in(t):
    return t * t


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
    """흩어지는 조각들 (프레임 수로 굴리는 옛 방식)."""

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


def orb(cv, x, y, r, light, dark, core=WHITE, rim=""):
    out = [cv.create_oval(x - r, y - r, x + r, y + r, fill=dark, outline=rim, width=2)]
    r2 = r * 0.68
    out.append(cv.create_oval(x - r2, y - r2, x + r2, y + r2, fill=light, outline=""))
    if core:
        r3 = r * 0.34
        out.append(cv.create_oval(x - r3, y - r3, x + r3, y + r3, fill=core, outline=""))
    return out


def glint(cv, x, y, r, fill=WHITE):
    pts = []
    for i in range(8):
        a = -math.pi / 2 + math.pi * i / 4
        rr = r if i % 2 == 0 else r * 0.16
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    return cv.create_polygon(*pts, fill=fill, outline="", width=1)


def tongue(cv, x, y, r, lean, fill, outline=""):
    return cv.create_polygon(
        x - r * 0.75, y + r * 0.4, x - r * 0.55, y - r * 0.4, x + lean, y - r * 1.7,
        x + r * 0.55, y - r * 0.4, x + r * 0.75, y + r * 0.4, x, y + r * 0.9,
        fill=fill, outline=outline, smooth=True)


def rock(cv, x, y, r, light, dark, seed=0):
    rnd = random.Random(seed)
    pts = []
    for i in range(6):
        a = 2 * math.pi * i / 6 + rnd.uniform(-0.25, 0.25)
        rr = r * rnd.uniform(0.72, 1.1)
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    return [cv.create_polygon(*pts, fill=dark, outline=light, width=2),
            cv.create_line(pts[0], pts[1], x, y, pts[6], pts[7], fill=light, width=1)]


def puff(cv, x, y, r, fill, outline=""):
    out = []
    for dx, dy, k in ((-0.55, 0.15, 0.62), (0.5, 0.2, 0.58), (0.0, -0.2, 0.8)):
        rr = r * k
        out.append(cv.create_oval(x + dx * r - rr, y + dy * r - rr, x + dx * r + rr, y + dy * r + rr,
                                  fill=fill, outline=outline))
    return out
