# -*- coding: utf-8 -*-
"""액션 배틀의 기술 꼴 (2.6.0).

턴제 기술 920개를 실시간 마당에서 어떻게 쓰는지 정한다. 도감의 분류 · 위력 · 플래그 · 대상 · 우선도 · 타격 수로
꼴을 **자동으로** 고르고, 이름난 기술은 OVERRIDES 로 손본다. 판(action_battle)과 웹 화면이 같이 본다.

    kit(dex, key)      꼴 하나 (아래 열쇠). 캐시한다 - 받은 dict 는 읽기만 한다
    move_of(dex, key)  판이 쓰는 기술 자료 = 도감 + FIX (도감에 없는 효과를 채운 사본, 고칠 것이 없으면 도감 것 그대로)
    style_of(move)     이펙트 모양 (STYLES 중 하나 - 웹 화면 fx.js 와 같은 목록)
    summary(dex)       꼴별 개수 · 못 쓰는 기술 목록 (검사 · 튜닝용)

kit 열쇠 (초 · u · u/s · 도)
    kind           KINDS 중 하나
    wind act rec   준비 · 발동 · 회복 시간          cd    다시 쓸 수 있을 때까지 (쓰기 시작한 때부터)
    pp             본가 PP 의 절반 (올림)
    range          탄이 날아가는 거리 · 근접 · 돌진이 달려드는 거리 ·
                   고리 · 부채꼴 반지름 · 광선 길이 · 내려찍기 · 함정 · 뛰어내리기를 놓을 수 있는 거리
    w              탄 지름 · 광선 굵기 · 표시(내려찍기 · 함정 · 뛰어내리기) 지름 · 근접이 치는 너비 · 돌진은 몸 지름
    speed          탄 · 돌진 · 근접 달려들기 속도
    n              탄 · 타격 수         spread  펼친 각 (탄 여러 발 · 부채꼴)
    home           탄이 상대 쪽으로 꺾는 빠르기 (도/초, 0 = 곧게)
    lock           준비 중 이동 배율 (0 = 못 움직인다)
    sty            이펙트 모양          ok · why   쓸 수 있나 · 못 쓰면 한국어 까닭 (쓸 수 있으면 "")

꼴마다 무엇을 하는지는 action_battle 이 정한다 (proj 날리기 · beam 광선 · melee 근접 · dash 돌진 · burst 주변 폭발 ·
cone 부채꼴 · strike 내려찍기 · leap 뛰어올랐다 내려찍기 · self 강화 · heal 회복 · guard 방어 · counter 되돌리기 ·
hazard 설치 · status 상태 걸기 · none 못 씀).

근접 (2026-11-18 사용자: "할퀴기, 드래곤클로 ... 몸통박치기, 전광석화처럼 내가 가는 방향으로 이동하면서 범위 공격으로")
    누르는 쪽으로 range = 160 + 0.6 × 위력 (240 까지) 만큼 RUSH_SEC(0.18초) 동안 달려들며, 지나는 길에서
    w/2 + 몸 반지름 안의 상대를 친다 (w = MELEE_W 120). act = RUSH_SEC + 0.1 × (타수 − 1).
    앞쪽 64 · 부채꼴 110° 일 때보다 훨씬 잘 맞으므로 대기 배율을 1.7 → 2.0 (날리기와 같다) 으로 늘렸다 (test_action_battle 판 길이).

빠르기 (2026-11-19 사용자: "전투가 좀 길어지는 것 같아서 약간 루즈해지는 감이 있는 것 같아")
    대기시간 전부 × CD_SCALE (0.85): 때리는 기술의 꼴 배율 CD_MULT 와 변화기 대기 (6~14초 → 5.1~11.9초). 바닥(한 번 쓰는
    시간 + 0.2초)은 그대로. 준비 × FAST_WIND (0.75): 날리기 · 근접 · 돌진 · 부채꼴 · 주변 폭발 · 상태 걸기만. 광선 · 내려찍기 ·
    뛰어내리기 (모으는 기술 · 일격기 포함) 는 예고를 보고 비켜야 하니 그대로.
"""
import math
import weakref

from . import abilities as A
from . import attackfx as AF
from . import movecalc as MC
from . import statusmoves as SM

KINDS = ("proj", "beam", "melee", "dash", "burst", "cone", "strike", "leap", "self", "heal", "guard", "counter",
         "hazard", "status", "none")
STYLES = ("orb", "flame", "jet", "zap", "leaf", "shard", "psy", "rock", "ghost", "dark", "fairy", "poison", "wind",
          "sound", "punch", "slash", "bite", "beam", "wave", "quake", "heal", "buff", "shield", "powder", "web")
ATTACK_KINDS = ("proj", "beam", "melee", "dash", "burst", "cone", "strike", "leap")

# 판이 다루는 상태 (도감 ail). 나머지(헤롱헤롱 · 사슬묶기 ...)는 턴에 묶여 있다.
AILS = ("burn", "paralysis", "poison", "sleep", "freeze", "confusion", "trap", "leech-seed")
# 나를 겨누는 대상 (도감 target): 3 같은 편 · 4 내 진영 · 5 나 또는 같은 편 · 7 나 · 13 나와 같은 편 · 14 모두 · 15 같은 편 모두
SELF_TARGETS = (3, 4, 5, 7, 13, 14, 15)

# 준비 중 이동 배율. 없는 꼴(광선 · 돌진 · 뛰어내리기 · 회복 · 방어 · 카운터)은 못 움직인다.
LOCK = {"proj": 0.35, "melee": 0.35, "burst": 0.35, "cone": 0.35, "strike": 0.35, "self": 0.35, "hazard": 0.35,
        "status": 0.35}
# 대기시간 = (0.6 + 위력/40) × 꼴 배율. 근접은 달려들며 넓게 치므로 (2026-11-18) 1.7 → 2.0.
# 2026-11-19 판이 늘어진다 → 대기 전부 × CD_SCALE (꼴 배율 · 변화기 대기 · 그 범위).
CD_SCALE = 0.85
CD_MULT = dict((k, round(v * CD_SCALE, 3)) for k, v in (
    ("proj", 2.0), ("melee", 2.0), ("dash", 1.8), ("beam", 2.6), ("burst", 2.4), ("cone", 2.2), ("strike", 2.4),
    ("leap", 2.5)))
STATUS_CD_RANGE = (6.0, 14.0)           # 변화기 대기 범위 (× CD_SCALE 전)
CD_STATUS = (round(STATUS_CD_RANGE[0] * CD_SCALE, 2), round(STATUS_CD_RANGE[1] * CD_SCALE, 2))     # 5.1 ~ 11.9
# 준비 × FAST_WIND (2026-11-19). 광선 · 내려찍기 · 뛰어내리기는 예고를 읽어야 하니 빼고, 일격기(내려찍기) ·
# 모으는 기술(광선 · 뛰어내리기)도 꼴로 같이 빠진다.
FAST_WIND = 0.75
FAST_WIND_KINDS = ("proj", "melee", "dash", "cone", "burst", "status")
HOME = 90.0                 # 반드시 맞는 기술(도감 명중 0)이 꺾는 빠르기
BODY_W = 52                 # 몸 지름 (action_battle.BODY_R × 2) - 돌진의 굵기
# 근접 달려들기: 거리 = MELEE_REACH[0] + 위력 × MELEE_REACH[1] (MELEE_REACH[2] 까지), RUSH_SEC 동안.
MELEE_REACH = (160.0, 0.6, 240.0)
MELEE_W = 120               # 근접이 치는 너비 (길 가운데에서 양쪽 60 + 상대 몸 반지름)
RUSH_SEC = 0.18
MULTI_GAP = 0.1             # 연속 근접: 첫 대 뒤 제자리에서 이만큼마다 한 대

# 이름으로 고르는 꼴 (규칙보다 먼저 본다)
CONE_MOVES = frozenset((
    "FLAMETHROWER", "DRAGONBREATH", "HEATWAVE", "BLIZZARD", "ICYWIND", "HYPERVOICE", "AIRCUTTER", "BLEAKWINDSTORM",
    "SANDSEARSTORM", "SPRINGTIDESTORM", "INCINERATE", "POWDERSNOW", "GLACIATE", "ELECTROWEB", "STRUGGLEBUG",
    "BREAKINGSWIPE", "RAZORLEAF", "TWISTER", "SWIFT", "ACID", "BUBBLE", "FIERYWRATH", "DRAGONENERGY",
    "BURNINGJEALOUSY"))
STRIKE_MOVES = frozenset((
    "THUNDER", "ROCKSLIDE", "STONEEDGE", "HURRICANE", "THOUSANDARROWS", "GLACIALLANCE", "MAKEITRAIN", "DRACOMETEOR",
    "FUTURESIGHT", "DOOMDESIRE", "ICICLECRASH", "WILDBOLTSTORM", "THUNDERCAGE", "MAGMASTORM", "EARTHPOWER",
    "JUDGMENT", "STEAMERUPTION", "FIREPLEDGE", "WATERPLEDGE", "GRASSPLEDGE", "SPACIALREND"))
BEAM_WORDS = ("BEAM", "CANNON", "LASER")
BEAM_MOVES = frozenset(("PHOTONGEYSER", "NIHILLIGHT", "LIGHTOFRUIN"))
GUARDS = frozenset(SM.STREAK_MOVES | {"MATBLOCK"})
# 카운터 류: 받은 쪽 (None = 물리 · 특수 다) · 되돌리는 배율
COUNTERS = dict(MC.COUNTERS, BIDE=(None, 2.0))
# 판 전체에 거는 것 (날씨 · 필드 · 방 · 진영). 트릭룸은 느린 쪽이 빨리 걷는다 (action_battle).
FIELD_MOVES = frozenset(set(SM.WEATHER_MOVES) | set(SM.TERRAIN_MOVES) | set(SM.ROOM_MOVES) | set(SM.SCREENS)
                        | set(SM.SIDE_MOVES))
SELF_FAINT = frozenset(("MEMENTO", "HEALINGWISH", "LUNARDANCE"))

WHY_TURN = "턴제에서만 뜻이 있는 기술이다"
WHY_FAINT = "쓰고 쓰러지는 변화기는 이 모드에 없다"
WHY_DOUBLE = "같이 싸우는 편이 있어야 하는 기술이다"
WHY_UNKNOWN = "도감에 없는 기술이다"

# 도감 자료에 없거나 이 모드에서 다르게 하는 효과 (move_of 가 도감 것 위에 얹는다).
#   stat · statSelf · heal · ail   도감과 같은 뜻
#   selfAil   쓴 쪽이 걸리는 상태 (잠자기)       cure   내 편의 상태이상을 고친다
#   cond      [이름, 초] 몸에 거는 것 (0 = 물러날 때까지) - battle.damage 가 cond 를 본다 (기충전 · 예민해지기 · 전자부유)
#   push      맞은 쪽을 밀어내는 거리 (u)        haze   둘 다 능력 랭크를 0 으로
#   stages    상대 랭크를 copy 베끼기 · swap 맞바꾸기 · invert 뒤집기
#   blink     움직이는 쪽으로 순간이동하는 거리 (u)   split  맞으면 둘의 체력을 똑같이 나눈다
FIX = {
    "BELLYDRUM": {"stat": [["atk", 6]], "statSelf": True, "heal": -50},
    "FILLETAWAY": {"stat": [["atk", 2], ["spa", 2], ["spe", 2]], "statSelf": True, "heal": -50},
    "VICTORYDANCE": {"stat": [["atk", 1], ["def", 1], ["spe", 1]], "statSelf": True},
    "TIDYUP": {"stat": [["atk", 1], ["spe", 1]], "statSelf": True},
    "SHELTER": {"stat": [["def", 2]], "statSelf": True},
    "TAKEHEART": {"stat": [["spa", 1], ["spd", 1]], "statSelf": True, "cure": True},
    "CURSE": {"stat": [["atk", 1], ["def", 1], ["spe", -1]], "statSelf": True},
    "SPICYEXTRACT": {"stat": [["atk", 2], ["def", -2]]},
    "LUNARBLESSING": {"heal": 25},
    "WISH": {"heal": 50},
    "AQUARING": {"heal": 25},
    "INGRAIN": {"heal": 25, "ail": None},
    "REST": {"heal": 100, "selfAil": "sleep"},
    "REFRESH": {"cure": True},
    "HEALBELL": {"cure": True},
    "AROMATHERAPY": {"cure": True},
    "FOCUSENERGY": {"cond": ["focus", 0]},
    "LASERFOCUS": {"cond": ["laserfocus", 5]},
    "MAGNETRISE": {"cond": ["magnetrise", 10]},
    "BLOCK": {"ail": "trap"},
    "MEANLOOK": {"ail": "trap"},
    "SPIDERWEB": {"ail": "trap"},
    "OCTOLOCK": {"ail": "trap", "stat": [["def", -1], ["spd", -1]]},
    "YAWN": {"ail": "sleep"},
    "ROAR": {"push": 320},
    "WHIRLWIND": {"push": 320},
    "DRAGONTAIL": {"push": 220},
    "CIRCLETHROW": {"push": 220},
    "HAZE": {"haze": True},
    "PSYCHUP": {"stages": "copy"},
    "HEARTSWAP": {"stages": "swap"},
    "TOPSYTURVY": {"stages": "invert"},
    "TELEPORT": {"blink": 260},
    "PAINSPLIT": {"split": True},
}
# 강화 꼴(self)로 가는 FIX 효과
SELF_EFFECTS = ("cure", "cond", "haze", "stages", "blink")

# 손으로 고친 꼴 · 수치 (자동으로 정한 것 위에 얹는다)
OVERRIDES = {
    "FLAMETHROWER": {"kind": "cone", "range": 360, "spread": 34},     # 곧게 뿜는 불길
    "DRAGONBREATH": {"range": 320, "spread": 40},
    "EARTHQUAKE": {"range": 250},
    "SURF": {"range": 240},
    "GEOMANCY": {"wind": 1.1},
    "THUNDER": {"w": 170},
}

# 이펙트 모양
TYPE_STYLE = {"NORMAL": "orb", "FIRE": "flame", "WATER": "jet", "ELECTRIC": "zap", "GRASS": "leaf", "ICE": "shard",
              "FIGHTING": "punch", "POISON": "poison", "GROUND": "rock", "FLYING": "wind", "PSYCHIC": "psy",
              "BUG": "shard", "ROCK": "rock", "GHOST": "ghost", "DRAGON": "orb", "DARK": "dark", "STEEL": "shard",
              "FAIRY": "fairy"}
WEB_MOVES = frozenset(("STICKYWEB", "STRINGSHOT", "SPIDERWEB", "ELECTROWEB"))
QUAKE_MOVES = frozenset(("EARTHQUAKE", "BULLDOZE", "MAGNITUDE", "FISSURE", "EARTHPOWER", "PRECIPICEBLADES",
                         "LANDSWRATH", "THOUSANDWAVES", "STOMPINGTANTRUM", "HIGHHORSEPOWER", "TECTONICRAGE"))
WAVE_MOVES = frozenset(("SURF", "MUDDYWATER", "SPLISHYSPLASH", "WHIRLPOOL", "SPARKLINGARIA", "HYDROSTEAM"))

_CACHE = weakref.WeakKeyDictionary()      # 도감 -> {열쇠: kit}


# ---------------------------------------------------------------- 기술 자료
def move_of(dex, key):
    """판이 쓰는 기술 자료. FIX 가 있으면 도감 것 위에 얹은 사본, 없으면 도감 것 그대로. 모르는 기술은 None."""
    mv = dex.move(key)
    fix = FIX.get(key)
    if not mv or not fix:
        return mv
    out = dict(mv)
    out.update(fix)
    return out


def nominal_power(mv):
    """한 번 맞을 때의 위력. 공식으로 정해지는 기술(안다리걸기 · 나이트헤드 ...)은 60 으로 친다."""
    return (mv.get("power") or 0) or (60 if MC.attacks(mv) else 0)


def _hits(mv):
    lo, hi = (mv.get("hits") or (1, 1))[:2]
    return int(lo), int(hi)


def _beamy(k, mv):
    if mv.get("cat") != "special":
        return False
    fl = mv.get("flags") or ()
    return (any(w in k for w in BEAM_WORDS) or k in BEAM_MOVES or "recharge" in fl or k in SM.CHARGE2)


# ---------------------------------------------------------------- 꼴 고르기
def classify(k, mv):
    """(꼴, 못 쓰는 까닭)."""
    if k in COUNTERS:
        return "counter", ""
    if mv.get("cat") == "status":
        return _status_kind(k, mv)
    return _attack_kind(k, mv), ""


def _attack_kind(k, mv):
    fl = set(mv.get("flags") or ())
    if k in MC.OHKO:
        return "strike"
    if k in AF.SELF_KO:
        return "burst"
    if (mv.get("pri") or 0) > 0:
        return "dash" if "contact" in fl else "proj"       # 얼음뭉치 · 진공파 · 물수리검은 빠른 탄
    if k in SM.CHARGE2:
        return "beam" if mv.get("cat") == "special" else "leap"
    if k in CONE_MOVES:
        return "cone"
    if k in STRIKE_MOVES:
        return "strike"
    if mv.get("target") in (9, 11):
        return "cone" if "sound" in fl else "burst"
    if _beamy(k, mv):
        return "beam"
    if fl & {"contact", "punch", "bite"}:
        return "melee"
    return "proj"


def _status_kind(k, mv):
    t = mv.get("target")
    stats = mv.get("stat") or []
    fl = mv.get("flags") or ()
    if k in GUARDS:
        return "guard", ""
    if k in SM.HAZARD_MOVES:
        return "hazard", ""
    if k in SELF_FAINT:
        return "none", WHY_FAINT
    if k in SM.SINGLES_FAIL:
        return "none", WHY_DOUBLE
    if (mv.get("heal") or 0) > 0 and t in SELF_TARGETS:
        return "heal", ""
    if k in FIELD_MOVES or any(mv.get(e) for e in SELF_EFFECTS):
        return "self", ""
    if stats and (mv.get("statSelf") or (t in SELF_TARGETS and all(c > 0 for _, c in stats))):
        return "self", ""
    if t in SELF_TARGETS:
        return "none", WHY_TURN
    if mv.get("ail") in AILS or mv.get("split"):
        return "status", ""
    if any(c < 0 for _, c in stats) or mv.get("push"):
        return ("burst" if "sound" in fl else "cone"), ""
    return "none", WHY_TURN


# ---------------------------------------------------------------- 수치
def _attack_numbers(kind, k, mv):
    p = nominal_power(mv)
    _, hi = _hits(mv)
    fl = mv.get("flags") or ()
    pri = mv.get("pri") or 0
    rec_more = 0.8 if "recharge" in fl else 0.0          # 파괴광선 류: 다음 턴에 못 움직이던 것
    if kind == "proj":
        ball, pulse = "ballistics" in fl, "pulse" in fl
        speed = min(900.0, max(480.0, 760 - 1.5 * p)) * (0.8 if ball else 1.3 if pulse else 1.0)
        wind = 0.16 + p / 700.0 + (0.05 if ball else 0.0)
        if pri > 0:
            speed, wind = speed * 1.35, wind * 0.5
        return dict(wind=wind, act=0.08, rec=0.2 + rec_more, range=700 if ball else 950 if pulse else 820,
                    w=18 if hi > 1 else min(56.0, 22 + p / 6.0 + (12 if ball else 0)), speed=min(1150.0, speed),
                    n=hi, spread=min(50, 10 * (hi - 1)))
    if kind == "melee":
        lo_r, per, hi_r = MELEE_REACH
        reach = min(hi_r, lo_r + per * p)
        return dict(wind=0.14 + p / 1000.0, act=RUSH_SEC + MULTI_GAP * (hi - 1), rec=0.18 + p / 1000.0 + rec_more,
                    range=reach, w=MELEE_W, speed=reach / RUSH_SEC, n=hi, spread=0)
    if kind == "dash":
        reach = min(520, 340 + 90 * (pri - 1))
        return dict(wind=0.08, act=reach / 1500.0, rec=0.25, range=reach, w=BODY_W, speed=1500, n=1, spread=0)
    if kind == "beam":
        return dict(wind=1.1 if k in SM.CHARGE2 else 0.55 + p / 600.0, act=0.25, rec=0.4 + rec_more, range=1000,
                    w=40 + p / 10.0, speed=3000, n=hi, spread=0)
    if kind == "burst":
        boom = k in AF.SELF_KO
        r = 280 if boom else min(250.0, 150 + 0.6 * p)
        return dict(wind=0.9 if boom else 0.4 + p / 1000.0, act=0.2, rec=0.3 + rec_more, range=r, w=2 * r, speed=1,
                    n=1, spread=360)
    if kind == "cone":
        reach = min(380, 280 + p)
        return dict(wind=0.3 + p / 1000.0, act=0.18, rec=0.3 + rec_more, range=reach, w=reach, speed=1, n=1,
                    spread=70)
    if kind == "strike":
        ohko = k in MC.OHKO
        return dict(wind=1.5 if ohko else 0.8 + p / 1000.0, act=0.15, rec=0.25 + rec_more, range=900,
                    w=130 if ohko else 150, speed=1, n=1, spread=0)
    # leap
    return dict(wind=0.95, act=0.15, rec=0.3, range=650, w=150, speed=1, n=1, spread=0)


STATUS_NUMBERS = {
    #          wind  act   rec   range  w     speed
    "self":    (0.35, 0.1, 0.25, 60, 120, 1),
    "heal":    (0.6, 0.1, 0.3, 60, 120, 1),
    "guard":   (0.05, 0.75, 0.25, 60, 120, 1),
    "counter": (0.05, 0.6, 0.4, 60, 120, 1),
    "hazard":  (0.4, 0.1, 0.25, 900, 120, 1),
    "status":  (0.3, 0.08, 0.25, 700, 30, 420),
    "none":    (0.1, 0.1, 0.1, 1, 1, 1),
}


def _status_numbers(kind, mv):
    if kind in ("cone", "burst"):           # 랭크 내리기 · 밀어내기: 꼴 모양만 빌린다
        return _attack_numbers(kind, "", dict(mv, power=0))
    wind, act, rec, reach, w, speed = STATUS_NUMBERS[kind]
    return dict(wind=wind, act=act, rec=rec, range=reach, w=w, speed=speed, n=1, spread=0)


def _cooldown(kind, k, mv, spend):
    """다시 쓸 때까지. 때리는 기술은 0.6 + 위력/40 (여러 번 치면 평균 타수만큼) × 꼴 배율 (CD_SCALE 이 들어 있다),
    변화기는 아래 값 × CD_SCALE 을 CD_STATUS (5.1~11.9초) 안으로. 한 번 쓰는 시간(spend) + 0.2초보다 짧지 않다."""
    if kind in ATTACK_KINDS and mv.get("cat") != "status":
        lo, hi = _hits(mv)
        cd = (0.6 + nominal_power(mv) * (lo + hi) / 2.0 / 40.0) * CD_MULT[kind]
        return max(cd, spend + 0.2)
    if kind == "guard":
        cd = 6.0
    elif kind == "counter":
        cd = 7.0
    elif kind == "hazard":
        cd = 10.0
    elif kind == "heal":
        cd = 6 + (mv.get("heal") or 0) / 10.0
    elif kind == "status":
        cd = 14.0 if mv.get("ail") == "sleep" else 10.0
    elif kind == "self" and k in FIELD_MOVES:
        cd = STATUS_CD_RANGE[1]
    elif kind in ("self", "cone", "burst"):
        cd = 6 + 1.5 * sum(abs(c) for _, c in (mv.get("stat") or [])) + (2 if mv.get("cond") else 0)
    else:
        cd = STATUS_CD_RANGE[0]
    cd *= CD_SCALE
    if mv.get("cat") == "status":
        cd = min(CD_STATUS[1], max(CD_STATUS[0], cd))
    return max(cd, spend + 0.2)


# ---------------------------------------------------------------- 꼴
def kit(dex, key):
    """기술 하나의 꼴. 도감마다 캐시한다 - 받은 dict 는 읽기만 한다."""
    cache = _CACHE.get(dex)
    if cache is None:
        cache = _CACHE[dex] = {}
    out = cache.get(key)
    if out is None:
        out = cache[key] = _build(dex, key)
    return out


def _build(dex, key):
    mv = move_of(dex, key)
    if not mv:
        return _finish("none", WHY_UNKNOWN, {"pp": 1, "type": "NORMAL"}, _status_numbers("none", {}), "")
    kind, why = classify(key, mv)
    over = OVERRIDES.get(key) or {}
    kind = over.get("kind", kind)
    if kind in ATTACK_KINDS and mv.get("cat") != "status":
        nums = _attack_numbers(kind, key, mv)
    else:
        nums = _status_numbers(kind, mv)
    if kind in FAST_WIND_KINDS and key not in SM.CHARGE2 and key not in MC.OHKO:
        nums["wind"] *= FAST_WIND               # 손으로 정한 준비(OVERRIDES)는 아래에서 그대로 덮는다
    nums.update((f, v) for f, v in over.items() if f != "kind")
    return _finish(kind, why, mv, nums, key)


def _finish(kind, why, mv, nums, key):
    spend = nums["wind"] + nums["act"] + nums["rec"]
    return {
        "kind": kind,
        "wind": round(nums["wind"], 3), "act": round(nums["act"], 3), "rec": round(nums["rec"], 3),
        "cd": round(_cooldown(kind, key, mv, spend), 2),
        "pp": max(1, int(math.ceil((mv.get("pp") or 1) / 2.0))),
        "range": round(float(nums["range"]), 1), "w": round(float(nums["w"]), 1),
        "speed": round(float(nums["speed"]), 1),
        "n": int(nums["n"]), "spread": float(nums["spread"]),
        "home": HOME if (kind in ("proj", "melee") and not mv.get("acc")) else 0.0,
        "lock": LOCK.get(kind, 0.0),
        "sty": style_of(mv),
        "ok": kind != "none",
        "why": why if kind == "none" else "",
    }


# ---------------------------------------------------------------- 이펙트 모양
def style_of(move):
    """이펙트 모양 열쇠 (STYLES 중 하나). 몸짓(펀치 · 물기 · 베기 · 소리 · 가루)이 먼저, 그다음 타입."""
    k = MC.key(move)
    fl = set(move.get("flags") or ())
    if k in GUARDS or k in SM.SCREENS or k in SM.SIDE_MOVES:
        return "shield"
    if move.get("cat") == "status":
        if (move.get("heal") or 0) > 0:
            return "heal"
        stats = move.get("stat") or []
        if stats and move.get("statSelf") and any(c > 0 for _, c in stats):
            return "buff"
    if k in WEB_MOVES:
        return "web"
    for flag, sty in (("powder", "powder"), ("sound", "sound"), ("punch", "punch"), ("bite", "bite")):
        if flag in fl:
            return sty
    if k in A.SLICING:
        return "slash"
    if k in A.WIND:
        return "wind"
    if _beamy(k, move):
        return "beam"
    if k in QUAKE_MOVES:
        return "quake"
    if "pulse" in fl or k in WAVE_MOVES:
        return "wave"
    return TYPE_STYLE.get(move.get("type"), "orb")


# ---------------------------------------------------------------- 검사 · 튜닝
def summary(dex):
    """{"kinds": {꼴: 개수}, "none": [못 쓰는 기술 열쇠]} - 도감 기술 전부."""
    kinds, none = {}, []
    for key in sorted(dex.moves):
        kd = kit(dex, key)["kind"]
        kinds[kd] = kinds.get(kd, 0) + 1
        if kd == "none":
            none.append(key)
    return {"kinds": kinds, "none": none}
