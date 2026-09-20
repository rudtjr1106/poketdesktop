# -*- coding: utf-8 -*-
"""변화기 — 혼란·도발·대타출동·방어·날씨·필드·압정·교체 기술 ...

배울 수 있는 기술 755개 중 144개가 이 엔진에서 **아무 일도 안 했다** (전부 변화기).
유저 포켓몬 1,857마리 중 629마리가 하나 이상 들고 있었다. 여기에 원작대로 만든다.

## 무엇이 어디에 사나

    Fighter.cond          포켓몬에 붙는 것 (혼란·도발·대타출동·방어·씨앗 말고 나머지 ...)
                          물러나면 풀린다 (배턴터치로 넘기는 것은 PASS_KEYS)
    Field (field.py)      판 전체 (날씨·필드·트릭룸 ...)와 진영 (리플렉터·압정·순풍 ...)
    Battle.request_switch 교체 기술 (울부짖기·배턴터치·순간이동·유턴 ...)
                          야생은 교체가 없어서 판이 끝나고(도망), 관장·유저 배틀은
                          trainer_battle / party_battle 이 실제로 바꾼다.

## 1:1 배틀에서 원작도 실패하는 것

도우미·날따름·분노가루·사이드체인지·당신먼저·순서미루기·아로마미스트·드래곤옐은
같은 편이 있어야 뜻이 있다. 원작 싱글배틀에서도 실패하므로 여기서도 실패한다.
튀어오르기는 원작에서도 아무 일도 안 일어난다.

## 규칙

- battle.py 를 import 하지 않는다 (battle 이 이걸 import 한다). 판을 바꾸는 일은
  넘겨받은 bt 의 메서드(_change_stat, _apply_status, request_switch ...)로 한다.
- 난수는 bt.rng 만 쓴다. 유저 배틀은 같은 시드면 같은 로그여야 한다.
- cond 에는 JSON 으로 저장되는 값만 넣는다 (턴마다 잤다 깨는 배틀이 그대로 적는다).
"""
from . import abilities as A
from . import field as FD
from . import held as H
from . import movecalc as MC

# ---------------------------------------------------------------- 분류
PROTECTS = {"PROTECT", "DETECT", "KINGSSHIELD", "SPIKYSHIELD", "BANEFULBUNKER", "OBSTRUCT",
            "SILKTRAP", "BURNINGBULWARK", "MAXGUARD"}
STREAK_MOVES = PROTECTS | {"ENDURE", "QUICKGUARD", "WIDEGUARD", "CRAFTYSHIELD"}
# 1:1 에서는 원작도 실패한다
SINGLES_FAIL = {"HELPINGHAND", "FOLLOWME", "RAGEPOWDER", "ALLYSWITCH", "AFTERYOU", "QUASH",
                "AROMATICMIST", "DRAGONCHEER", "SPOTLIGHT", "HOLDHANDS"}
WEATHER_MOVES = {"SUNNYDAY": "sun", "RAINDANCE": "rain", "SANDSTORM": "sand", "HAIL": "hail",
                 "SNOWSCAPE": "snow", "CHILLYRECEPTION": "snow"}
TERRAIN_MOVES = {"ELECTRICTERRAIN": "electric", "GRASSYTERRAIN": "grassy",
                 "MISTYTERRAIN": "misty", "PSYCHICTERRAIN": "psychic"}
ROOM_MOVES = {"TRICKROOM": "trickroom", "MAGICROOM": "magicroom", "WONDERROOM": "wonderroom",
              "GRAVITY": "gravity", "MUDSPORT": "mudsport", "WATERSPORT": "watersport"}
SCREENS = {"REFLECT": "reflect", "LIGHTSCREEN": "lightscreen", "AURORAVEIL": "auroraveil"}
SIDE_MOVES = {"SAFEGUARD": ("safeguard", 5), "MIST": ("mist", 5), "TAILWIND": ("tailwind", 4)}
HAZARD_MOVES = {"SPIKES": ("spikes", 3), "TOXICSPIKES": ("toxicspikes", 2),
                "STEALTHROCK": ("stealthrock", 1), "STICKYWEB": ("stickyweb", 1)}
DRAG_MOVES = {"ROAR", "WHIRLWIND"}
DRAG_ATTACKS = {"DRAGONTAIL", "CIRCLETHROW"}
OUT_ATTACKS = {"UTURN", "VOLTSWITCH", "FLIPTURN"}
SCREEN_BREAKERS = {"BRICKBREAK", "PSYCHICFANGS", "RAGINGBULL"}
SPINNERS = {"RAPIDSPIN", "MORTALSPIN"}
TERRAIN_BREAKERS = {"STEELROLLER", "ICESPINNER"}
HEAL_BY_WEATHER = {"MOONLIGHT", "MORNINGSUN", "SYNTHESIS"}
# 배턴터치로 넘기는 것 (랭크는 따로 넘긴다)
PASS_KEYS = ("sub", "confused", "focus", "cursed", "perish", "ingrain", "aquaring", "magnetrise",
             "lockon", "embargo", "healblock", "gastro", "telekinesis", "trapped", "powertrick")
# 흉내·스케치·손가락흔들기 등이 못 부르는 기술
CALL_BAN = {"ASSIST", "BANEFULBUNKER", "BEAKBLAST", "BELCH", "BESTOW", "CELEBRATE", "CHATTER",
            "COPYCAT", "COUNTER", "COVET", "CRAFTYSHIELD", "DESTINYBOND", "DETECT", "ENDURE",
            "FEINT", "FOCUSPUNCH", "FOLLOWME", "HELPINGHAND", "HOLDHANDS", "KINGSSHIELD",
            "MATBLOCK", "MEFIRST", "METRONOME", "MIMIC", "MIRRORCOAT", "MIRRORMOVE", "NATUREPOWER",
            "PROTECT", "QUASH", "QUICKGUARD", "RAGEPOWDER", "SKETCH", "SLEEPTALK", "SNATCH", "SNORE",
            "SPIKYSHIELD", "SPOTLIGHT", "STRUGGLE", "SWITCHEROO", "THIEF", "TRANSFORM", "TRICK",
            "WIDEGUARD", "BIDE", "DYNAMAXCANNON", "OBSTRUCT", "SILKTRAP", "BURNINGBULWARK",
            "SHEDTAIL", "REVIVALBLESSING", "TERASTARSTORM", "BLAZINGTORQUE", "COMBATTORQUE",
            "MAGICALTORQUE", "NOXIOUSTORQUE", "WICKEDTORQUE", "DOODLE", "INSTRUCT", "ALLYSWITCH",
            "AFTERYOU", "SHELLTRAP", "SKETCH", "SPECTRALTHIEF", "SNIPESHOT"}
# 역린류: 쓰면 2~3턴 이어지고, 끝나면 혼란에 빠진다. 소란피기는 혼란이 없다.
RAGE_MOVES = {"OUTRAGE", "THRASH", "PETALDANCE", "RAGINGFURY"}
LOCK_MOVES = RAGE_MOVES | {"UPROAR"}

# 두 턴에 걸쳐 쓰는 기술. (첫 턴 문구, 숨는 자리, 첫 턴에 오르는 능력)
# 숨는 자리가 있으면 그동안 웬만한 기술이 빗나간다.
CHARGE2 = {
    "SOLARBEAM": ("%s 은(는) 햇빛을 모으고 있다!", None, None),
    "SOLARBLADE": ("%s 은(는) 햇빛을 모으고 있다!", None, None),
    "SKYATTACK": ("%s 은(는) 힘을 모으고 있다!", None, None),
    "RAZORWIND": ("%s 은(는) 바람을 모으고 있다!", None, None),
    "SKULLBASH": ("%s 은(는) 머리를 단단히 했다!", None, "def"),
    "METEORBEAM": ("%s 은(는) 우주의 힘을 모으고 있다!", None, "spa"),
    "ELECTROSHOT": ("%s 은(는) 전기를 모으고 있다!", None, "spa"),
    "FREEZESHOCK": ("%s 은(는) 전기를 모으고 있다!", None, None),
    "ICEBURN": ("%s 은(는) 냉기를 모으고 있다!", None, None),
    "GEOMANCY": ("%s 은(는) 에너지를 모으고 있다!", None, None),
    "FLY": ("%s 은(는) 하늘 높이 날아올랐다!", "fly", None),
    "BOUNCE": ("%s 은(는) 높이 뛰어올랐다!", "fly", None),
    "DIG": ("%s 은(는) 땅속으로 파고들었다!", "dig", None),
    "DIVE": ("%s 은(는) 물속으로 숨었다!", "dive", None),
    "PHANTOMFORCE": ("%s 은(는) 모습을 감췄다!", "vanish", None),
    "SHADOWFORCE": ("%s 은(는) 모습을 감췄다!", "vanish", None),
}
# 숨어 있어도 맞는 기술 (본가 그대로)
HITS_HIDDEN = {
    "fly": {"GUST", "TWISTER", "THUNDER", "SKYUPPERCUT", "HURRICANE", "SMACKDOWN",
            "THOUSANDARROWS"},
    "dig": {"EARTHQUAKE", "MAGNITUDE", "FISSURE"},
    "dive": {"SURF", "WHIRLPOOL"},
    "vanish": set(),
}

CHARGE_BAN = {"BOUNCE", "DIG", "DIVE", "FLY", "GEOMANCY", "METEORBEAM", "PHANTOMFORCE", "RAZORWIND",
              "SHADOWFORCE", "SKULLBASH", "SKYATTACK", "SKYDROP", "SOLARBEAM", "SOLARBLADE",
              "FREEZESHOCK", "ICEBURN", "ELECTROSHOT", "UPROAR"}
NATURE_POWER = {"electric": "THUNDERBOLT", "grassy": "ENERGYBALL", "misty": "MOONBLAST",
                "psychic": "PSYCHIC", None: "TRIATTACK"}
ABILITY_FIXED = {"MULTITYPE", "STANCECHANGE", "SCHOOLING", "COMATOSE", "SHIELDSDOWN", "DISGUISE",
                 "RKSSYSTEM", "BATTLEBOND", "POWERCONSTRUCT", "ICEFACE", "GULPMISSILE",
                 "ASONEGLASTRIER", "ASONESPECTRIER", "ZEROTOHERO", "COMMANDER", "TERASHIFT",
                 "PROTOSYNTHESIS", "QUARKDRIVE"}

STAT_KR = {"atk": "공격", "def": "방어", "spa": "특수공격", "spd": "특수방어", "spe": "스피드",
           "acc": "명중률", "eva": "회피율"}


def key(move):
    return MC.key(move)


def flags(move):
    return set((move or {}).get("flags") or [])


def say(ev, who, text):
    ev.append({"t": "msg", "who": who, "text": text})


def fail(ev, who, text="하지만 실패했다!"):
    ev.append({"t": "msg", "who": who, "text": text})
    return True


def other(who):
    return "foe" if who == "me" else "me"


def rng_of(f):
    return None


# ---------------------------------------------------------------- 땅에 붙어 있나
def forced_grounded(f):
    """비행·부유여도 땅에 붙는다 (중력·뿌리박기·검은철구·떨어뜨리기)."""
    fl = f.field
    return bool((fl is not None and fl.room("gravity")) or f.cond.get("ingrain")
                or f.cond.get("smackdown") or f._held == "IRONBALL" and f.held == "IRONBALL")


def grounded(f):
    if forced_grounded(f):
        return True
    if "FLYING" in f.types():
        return False
    if A.has(f, "LEVITATE"):
        return False
    if f.cond.get("magnetrise") or f.cond.get("telekinesis"):
        return False
    return True


def weather(f):
    fl = f.field
    if fl is None or fl.suppressed:
        return None
    return fl.weather


def terrain(f):
    fl = f.field
    return fl.terrain if fl is not None else None


# ---------------------------------------------------------------- 쓸 수 있나
def restricted(bt, f, k):
    """이 기술을 지금 못 쓰는 까닭 (문구). 쓸 수 있으면 None."""
    if k == "STRUGGLE":
        return None
    md = bt.move_of(k)
    c = f.cond
    enc = c.get("encore")
    if enc and enc.get("move") != k and f.pp.get(enc.get("move"), 0) > 0:
        return "%s 은(는) 앙코르를 받아 다른 기술을 쓸 수 없다!" % f.name
    rg = c.get("rage")
    if rg and rg.get("move") != k and f.pp.get(rg.get("move"), 0) > 0:
        return "%s 은(는) %s 을(를) 쓰는 중이라 멈출 수 없다!" % (
            f.name, bt.move_name(rg.get("move")))
    ch = c.get("charge2")
    if ch and ch.get("move") != k and f.pp.get(ch.get("move"), 0) > 0:
        return "%s 은(는) %s 을(를) 준비하는 중이다!" % (
            f.name, bt.move_name(ch.get("move")))
    if c.get("taunt") and md.get("cat") == "status" and not MC.attacks(md):
        return "%s 은(는) 도발당해서 %s 을(를) 쓸 수 없다!" % (f.name, bt.move_name(k))
    dis = c.get("disable")
    if dis and dis.get("move") == k:
        return "%s 의 %s 은(는) 사슬묶기로 쓸 수 없다!" % (f.name, bt.move_name(k))
    if c.get("torment") and c.get("lastMove") == k:
        return "%s 은(는) 트집 때문에 같은 기술을 연달아 쓸 수 없다!" % f.name
    opp = bt.foe if f is bt.me else bt.me
    if opp is not None and k in (opp.cond.get("imprison") or []):
        return "%s 은(는) 봉인당해서 %s 을(를) 쓸 수 없다!" % (f.name, bt.move_name(k))
    if c.get("healblock") and ((md.get("heal") or 0) > 0 or "heal" in flags(md)):
        return "%s 은(는) 회복봉인으로 %s 을(를) 쓸 수 없다!" % (f.name, bt.move_name(k))
    if f.field is not None and f.field.room("gravity") and "gravity" in flags(md):
        return "%s 은(는) 중력 때문에 %s 을(를) 쓸 수 없다!" % (f.name, bt.move_name(k))
    if c.get("silenced") and "sound" in flags(md):
        return "%s 은(는) 목이 막혀 %s 을(를) 쓸 수 없다!" % (f.name, bt.move_name(k))
    return None


# 나온 첫 턴에만 쓸 수 있는 기술.
FIRST_TURN_ONLY = {"FAKEOUT", "FIRSTIMPRESSION"}


def locked_move(f):
    """지금 반드시 써야 하는 기술 (역린류·2턴 기술). 없으면 None.

    화면은 restricted 로 다른 칸을 흐리게 하지만, **고르는 쪽이 딴 것을
    보내와도 거절하지 않는다** - 엔진이 어차피 이것으로 바꿔 쓴다.
    사람이 창을 띄워 둔 사이에 잠긴 것이라면 거절이 더 이상하다.
    """
    c = f.cond or {}
    for name in ("rage", "charge2"):
        lock = c.get(name)
        if not lock or not lock.get("move"):
            continue
        # **PP 가 떨어지면 잠금이 풀린다.** 안 그러면 쓸 수 없는 기술에
        # 묶여서 아무것도 못 하게 된다 (몸부림으로 빠져나가야 한다).
        if f.pp.get(lock["move"], 0) <= 0:
            c.pop(name, None)
            continue
        return lock["move"]
    return None


def first_turn_only(f, k):
    """속이기·만나자마자: 나온 턴이 아니면 실패한다.

    **자료에는 이 규칙이 없다.** 우선도(+3)와 풀죽음(100%)은 도감에 맞게
    들어 있어서, 이것만 빠지면 매 턴 100% 풀죽이는 기술이 된다.
    """
    if k not in FIRST_TURN_ONLY:
        return False
    return int((f.cond or {}).get("outTurns") or 0) > 1


def hidden_spot(f):
    """지금 숨어 있는 자리 (공중·땅속·물속·그림자). 없으면 None."""
    return (f.cond or {}).get("invuln")


def hidden_from(f, k):
    """숨어 있어서 이 기술이 안 닿나."""
    spot = hidden_spot(f)
    if not spot:
        return False
    return k not in HITS_HIDDEN.get(spot, set())


def priority(bt, f, move):
    p = move.get("pri", 0) or 0
    if f.ability_on:
        p += A.priority_bonus(f, move)
    if key(move) == "GRASSYGLIDE" and terrain(f) == "grassy" and grounded(f):
        p += 1
    return p


# ---------------------------------------------------------------- 명중
def accuracy(move, user, target):
    acc = move.get("acc") or 0
    k = key(move)
    w = weather(user)
    if k in ("THUNDER", "HURRICANE", "BLEAKWINDSTORM", "WILDBOLTSTORM", "SANDSEARSTORM"):
        if w == "rain":
            return 0
        if w == "sun" and k in ("THUNDER", "HURRICANE"):
            return 50
    if k == "BLIZZARD" and w in ("hail", "snow"):
        return 0
    return acc


def sure_hit(user, target):
    if user.cond.get("lockon"):
        return True
    if target.cond.get("telekinesis"):
        return True
    return False


# ---------------------------------------------------------------- 위력·타입
def resolve(move, user, target):
    """날씨구슬·대지의파동처럼 날씨·필드로 타입·위력이 바뀌는 기술."""
    k = key(move)
    w = weather(user)
    t = terrain(user)
    if k == "WEATHERBALL" and w:
        return dict(move, type={"sun": "FIRE", "rain": "WATER", "sand": "ROCK", "hail": "ICE",
                                "snow": "ICE"}[w], power=(move.get("power") or 50) * 2)
    if k == "TERRAINPULSE" and t and grounded(user):
        return dict(move, type={"electric": "ELECTRIC", "grassy": "GRASS", "misty": "FAIRY",
                                "psychic": "PSYCHIC"}[t], power=(move.get("power") or 50) * 2)
    return move


def field_mult(move, mtype, user, target, crit):
    """날씨·필드·흙놀이·리플렉터 배율."""
    m = 1.0
    k = key(move)
    w = weather(user)
    if w == "sun":
        if mtype == "FIRE":
            m *= 1.5
        elif mtype == "WATER":
            m *= 1.5 if k == "HYDROSTEAM" else 0.5
    elif w == "rain":
        if mtype == "WATER":
            m *= 1.5
        elif mtype == "FIRE":
            m *= 0.5
    if k in ("SOLARBEAM", "SOLARBLADE") and w in ("rain", "sand", "hail", "snow"):
        m *= 0.5
    t = terrain(user)
    if t:
        ug, tg = grounded(user), grounded(target)
        if ug and ((t == "electric" and mtype == "ELECTRIC") or (t == "grassy" and mtype == "GRASS")
                   or (t == "psychic" and mtype == "PSYCHIC")):
            m *= 1.3
        if tg and t == "misty" and mtype == "DRAGON":
            m *= 0.5
        if tg and t == "grassy" and k in ("EARTHQUAKE", "BULLDOZE", "MAGNITUDE"):
            m *= 0.5
        if k == "RISINGVOLTAGE" and t == "electric" and tg:
            m *= 2.0
        if k == "EXPANDINGFORCE" and t == "psychic" and ug:
            m *= 1.5
        if k == "MISTYEXPLOSION" and t == "misty" and ug:
            m *= 1.5
        if k == "PSYBLADE" and t == "electric":
            m *= 1.5
    fl = user.field
    if fl is not None:
        if mtype == "ELECTRIC" and fl.room("mudsport"):
            m *= 1.0 / 3
        if mtype == "FIRE" and fl.room("watersport"):
            m *= 1.0 / 3
        side = fl.side(target.side_name) if target.side_name else {}
        if not crit and not A.has(user, "INFILTRATOR"):
            cat = move.get("cat")
            if side.get("auroraveil") or (cat == "physical" and side.get("reflect")) \
                    or (cat == "special" and side.get("lightscreen")):
                m *= 0.5
    if A.has(user, "SANDFORCE") and w == "sand" and mtype in ("ROCK", "GROUND", "STEEL"):
        m *= 1.3
    return m


# ---------------------------------------------------------------- 상태 (cond)
def confuse(bt, target, tw, ev, source=None, quiet=False):
    """혼란에 빠뜨린다. 걸렸으면 True."""
    if not target.alive():
        return False
    if target.cond.get("confused"):
        if not quiet:
            say(ev, tw, "%s 은(는) 이미 혼란에 빠져 있다!" % target.name)
        return False
    if A.has(target, "OWNTEMPO") and not (source is not None and A.breaks(source)):
        if not quiet:
            A.pop(bt, target, tw, ev)
            say(ev, tw, "%s 은(는) 혼란에 빠지지 않는다!" % target.name)
        return False
    if blocked_by_guard(bt, target, tw, source, ev, quiet):
        return False
    target.cond["confused"] = bt.rng.randint(2, 5)
    say(ev, tw, "%s 은(는) 혼란에 빠졌다!" % target.name)
    return True


def blocked_by_guard(bt, target, tw, source, ev, quiet=False):
    """신비의부적·미스트필드가 상대의 상태이상·혼란을 막는다."""
    if source is None or source is target:
        return False
    side = bt.field.side(tw)
    if side.get("safeguard") and not A.has(source, "INFILTRATOR"):
        if not quiet:
            say(ev, tw, "%s 은(는) 신비의부적에 보호받고 있다!" % target.name)
        return True
    if terrain(target) == "misty" and grounded(target):
        if not quiet:
            say(ev, tw, "%s 은(는) 미스트필드에 보호받고 있다!" % target.name)
        return True
    return False


def confusion_turn(bt, user, who, ev):
    """혼란: 풀리거나, 1/3 로 스스로를 때린다. 못 움직였으면 False."""
    left = user.cond.get("confused")
    if not left:
        return True
    left -= 1
    if left <= 0:
        user.cond.pop("confused", None)
        say(ev, who, "%s 의 혼란이 풀렸다!" % user.name)
        return True
    user.cond["confused"] = left
    say(ev, who, "%s 은(는) 혼란에 빠져 있다!" % user.name)
    if bt.rng.random() >= 1.0 / 3:
        return True
    atk, df = user.stat("atk"), user.stat("def")
    base = ((2 * user.level // 5 + 2) * 40 * atk // max(1, df)) // 50 + 2
    dmg = max(1, int(base * bt.rng.uniform(0.85, 1.0)))
    if user.cond.get("sub"):
        pass                               # 대타가 있어도 자기 몸을 때린다
    user.hp = max(0, user.hp - dmg)
    ev.append({"t": "hit", "who": who, "target": who, "damage": dmg, "crit": False, "eff": 1.0,
               "hp": user.hp, "maxhp": user.maxhp,
               "text": "영문도 모른 채 자신을 공격했다!"})
    return False


def attract_turn(bt, user, who, ev):
    if not user.cond.get("attract"):
        return True
    say(ev, who, "%s 은(는) 헤롱헤롱하다!" % user.name)
    if bt.rng.random() < 0.5:
        say(ev, who, "%s 은(는) 헤롱헤롱해서 기술을 쓸 수 없었다!" % user.name)
        return False
    return True


def sub_blocks(user, target, move):
    """대타출동이 이 기술을 대신 받나 (소리 기술·틈새포착·authentic 은 뚫는다)."""
    if not target.cond.get("sub") or user is target:
        return False
    if not A.aims_at_foe(move):
        return False
    fl = flags(move)
    if "sound" in fl or "authentic" in fl or A.has(user, "INFILTRATOR"):
        return False
    return True


def hit_sub(bt, user, who, target, tw, dmg, ev):
    """대타가 맞는다. 대타가 받은 만큼을 돌려준다."""
    hp = target.cond.get("sub") or 0
    took = min(hp, dmg)
    hp -= took
    say(ev, tw, "대타가 %s 대신 공격을 받았다!" % target.name)
    if hp <= 0:
        target.cond.pop("sub", None)
        say(ev, tw, "%s 의 대타가 사라졌다!" % target.name)
    else:
        target.cond["sub"] = hp
    return took


# ---------------------------------------------------------------- 날씨·필드·방
WEATHER_ABILITY = {"DROUGHT": "sun", "DRIZZLE": "rain", "SANDSTREAM": "sand", "SNOWWARNING": "snow",
                   "ORICHALCUMPULSE": "sun"}
TERRAIN_ABILITY = {"ELECTRICSURGE": "electric", "GRASSYSURGE": "grassy", "MISTYSURGE": "misty",
                   "PSYCHICSURGE": "psychic", "HADRONENGINE": "electric"}


def set_weather(bt, w, ev, who=None):
    fl = bt.field
    if fl.weather == w:
        return False
    fl.weather, fl.weather_turns = w, 5
    ev.append({"t": "msg", "who": who, "text": FD.WEATHER_START[w]})
    return True


def set_terrain(bt, t, ev, who=None):
    fl = bt.field
    if fl.terrain == t:
        return False
    fl.terrain, fl.terrain_turns = t, 5
    ev.append({"t": "msg", "who": who, "text": FD.TERRAIN_START[t]})
    # 일렉트릭필드: 잠든 포켓몬은 그대로 두지만 새로 잠들지 않는다 / 미스트필드: 혼란 방지
    return True


def toggle_room(bt, room, ev, who=None):
    """트릭룸·매직룸·원더룸·중력은 다시 쓰면 풀린다 (중력은 실패). 흙놀이·물놀이는 실패."""
    fl = bt.field
    if fl.rooms.get(room):
        if room in ("trickroom", "magicroom", "wonderroom"):
            fl.rooms.pop(room, None)
            ev.append({"t": "msg", "who": who, "text": FD.ROOM_END[room]})
            return True
        return fail(ev, who)
    fl.rooms[room] = 5
    ev.append({"t": "msg", "who": who, "text": FD.ROOM_START[room]})
    if room == "gravity":
        for f in (bt.me, bt.foe):
            if f.alive() and (f.cond.pop("magnetrise", None) or f.cond.pop("telekinesis", None)):
                say(ev, f.side_name, "%s 은(는) 중력 때문에 땅으로 떨어졌다!" % f.name)
    return True


# ---------------------------------------------------------------- 능력치·특성·타입을 바꿔 둔 것
def _snap(f):
    return {"base": dict(f.base), "moves": list(f.moves), "ability": f.ability,
            "types": list(f.types_override) if f.types_override else None}


def _changing(f):
    """바꾸기 전에 원래 모습을 한 번 적어 둔다."""
    if "orig" not in f.cond:
        f.cond["orig"] = _snap(f)
        f.cond["origPp"] = dict(f.pp)


def _changed(f):
    f.cond["now"] = _snap(f)


def reapply(f):
    """저장본에서 되살린 뒤, 바꿔 둔 능력치·기술·특성·타입을 다시 입힌다."""
    now = f.cond.get("now")
    if not now:
        return
    f.base = dict(now["base"])
    f.moves = list(now["moves"])
    f.ability = now["ability"]
    f.types_override = list(now["types"]) if now.get("types") else None
    for m in f.moves:
        f.pp.setdefault(m, 5)


def restore(f):
    """물러날 때 원래 모습으로."""
    orig = f.cond.get("orig")
    if not orig:
        return
    kept = set(f.moves)                    # 바뀌지 않고 남아 있던 기술은 지금 PP 를 그대로 둔다
    cur = dict(f.pp)
    f.base = dict(orig["base"])
    f.moves = list(orig["moves"])
    f.ability = orig["ability"]
    f.types_override = list(orig["types"]) if orig.get("types") else None
    pp = dict(f.cond.get("origPp") or cur)
    for m in f.moves:
        if m in kept and m in cur:
            pp[m] = cur[m]
    f.pp = pp
    f.maxhp = f.base.get("hp", f.maxhp)


def pass_state(f):
    """배턴터치로 넘길 것."""
    out = {"stages": dict(f.stages), "cond": {}, "seeded": f.seeded}
    for k in PASS_KEYS:
        if k in f.cond:
            out["cond"][k] = f.cond[k]
    return out


def apply_pass(f, st, shed=False):
    if not st:
        return
    if shed:
        if st.get("sub"):
            f.cond["sub"] = st["sub"]
        return
    f.stages = dict(st.get("stages") or f.stages)
    f.seeded = bool(st.get("seeded"))
    for k, v in (st.get("cond") or {}).items():
        f.cond[k] = v
    if "powertrick" in f.cond:
        _changing(f)
        f.base["atk"], f.base["def"] = f.base["def"], f.base["atk"]
        _changed(f)


def on_leave(bt, who):
    """who 쪽이 물러난다 - 그 포켓몬이 상대에게 걸어 둔 것(헤롱헤롱·검은눈빛·문어굳히기·조이기)을 푼다."""
    opp = bt.fighter(other(who))
    if opp is None:
        return
    for k in ("attract", "trapped", "octolock", "bound"):
        v = opp.cond.get(k)
        by = v.get("by") if isinstance(v, dict) else v
        if by == who:
            opp.cond.pop(k, None)


def trapped(bt, f):
    """교체·도망을 못 하나.

    검은눈빛·블록·문어굳히기·조이기·뿌리박기·페어리록과, 상대의 특성
    (그림자밟기·개미지옥·자력). 고스트 타입은 무엇에도 안 걸린다.
    """
    if "GHOST" in f.types():
        return False
    c = f.cond
    if bool(c.get("trapped") or c.get("octolock") or c.get("bound") or c.get("ingrain")
            or bt.field.room("fairylock")):
        return True
    return trapped_by_foe(bt, f)


def trapped_by_foe(bt, f):
    """상대 특성에 붙잡혀 있나. 붙잡는 쪽도 같은 특성이면 안 걸린다(본가)."""
    who = getattr(f, "side_name", None) or "me"
    foe = bt.fighter(other(who))
    if foe is None or not foe.alive() or not A.on(foe):
        return False
    kind = A.TRAP_ABILITY.get(foe.ability)
    if kind is None and foe.ability not in A.TRAP_ABILITY:
        return False
    if A.has(f, foe.ability):
        return False                    # 서로 같은 특성이면 안 걸린다
    if kind == "STEEL":
        return "STEEL" in f.types()
    if kind == "GROUNDED":
        return grounded(f)
    return True


# ---------------------------------------------------------------- 기술 효과
def run(bt, k, move, who, user, target, tw, ev):
    """변화기 효과. 여기서 다 처리했으면 True (battle 의 일반 처리를 건너뛴다)."""
    h = HANDLERS.get(k)
    if h is None:
        return False
    h(bt, move, who, user, target, tw, ev)
    return True


def _stat(bt, f, fw, stat, change, ev, source=None):
    bt._change_stat(f, stat, change, ev, fw, source=source if source is not None else f)


def _heal(bt, f, fw, amount, ev, text=None):
    if f.cond.get("healblock"):
        return 0
    amount = max(1, int(amount))
    if f.hp >= f.maxhp:
        return 0
    amount = min(amount, f.maxhp - f.hp)
    f.hp += amount
    ev.append({"t": "heal", "who": fw, "amount": amount, "hp": f.hp, "maxhp": f.maxhp,
               "text": text or "%s 은(는) 체력을 회복했다!" % f.name})
    return amount


def _chip(f, fw, amount, ev, text):
    amount = max(1, int(amount))
    f.hp = max(0, f.hp - amount)
    ev.append({"t": "chip", "who": fw, "damage": amount, "hp": f.hp, "maxhp": f.maxhp, "text": text})
    return amount


def _team_others(bt, who, f):
    return [m for m in bt.team_of(who) if m is not f and m.alive()]


def _last(f):
    return f.cond.get("lastMove")


# ---- 1:1 에서 실패 / 아무 일도 없음
def h_singles_fail(bt, move, who, user, target, tw, ev):
    fail(ev, who)


def h_splash(bt, move, who, user, target, tw, ev):
    say(ev, who, "하지만 아무 일도 일어나지 않았다!")


# ---- 방어 계열
def h_protect(bt, move, who, user, target, tw, ev):
    k = key(move)
    streak = user.cond.get("streak", 0)
    if streak and bt.rng.random() >= (1.0 / 3) ** streak:
        user.cond["streak"] = 0
        return fail(ev, who)
    user.cond["streak"] = streak + 1
    user.cond["protect"] = k
    say(ev, who, "%s 은(는) 방어 태세에 들어갔다!" % user.name)


def h_endure(bt, move, who, user, target, tw, ev):
    streak = user.cond.get("streak", 0)
    if streak and bt.rng.random() >= (1.0 / 3) ** streak:
        user.cond["streak"] = 0
        return fail(ev, who)
    user.cond["streak"] = streak + 1
    user.cond["endure"] = True
    say(ev, who, "%s 은(는) 버티기 태세에 들어갔다!" % user.name)


def h_guard(bt, move, who, user, target, tw, ev):
    k = key(move)
    streak = user.cond.get("streak", 0) if k != "CRAFTYSHIELD" else 0
    if streak and bt.rng.random() >= (1.0 / 3) ** streak:
        user.cond["streak"] = 0
        return fail(ev, who)
    if k != "CRAFTYSHIELD":
        user.cond["streak"] = streak + 1
    bt.field.side(who)[k.lower()] = True
    say(ev, who, {"QUICKGUARD": "패스트가드가 %s 진영을 지킨다!", "WIDEGUARD": "와이드가드가 %s 진영을 지킨다!",
                  "CRAFTYSHIELD": "트릭가드가 %s 진영을 지킨다!"}[k] % user.name)


# ---- 혼란·헤롱헤롱·도발 ...
def h_confuse(bt, move, who, user, target, tw, ev):
    k = key(move)
    if k == "SWAGGER":
        _stat(bt, target, tw, "atk", 2, ev, source=user)
    elif k == "FLATTER":
        _stat(bt, target, tw, "spa", 1, ev, source=user)
    confuse(bt, target, tw, ev, source=user)


def h_attract(bt, move, who, user, target, tw, ev):
    g1, g2 = user.mon.get("gender"), target.mon.get("gender")
    if target.cond.get("attract") or not g1 or not g2 or "N" in (g1, g2) or g1 == g2:
        return fail(ev, who)
    if A.has(target, "OBLIVIOUS") and not A.breaks(user):
        A.pop(bt, target, tw, ev)
        return fail(ev, who)
    target.cond["attract"] = who
    say(ev, tw, "%s 은(는) 헤롱헤롱해졌다!" % target.name)


def _mental_blocked(bt, user, target, tw, ev):
    if A.has(target, "OBLIVIOUS", "AROMAVEIL") and not A.breaks(user):
        A.pop(bt, target, tw, ev)
        say(ev, tw, "%s 에게는 효과가 없는 것 같다..." % target.name)
        return True
    return False


def h_taunt(bt, move, who, user, target, tw, ev):
    if target.cond.get("taunt") or _mental_blocked(bt, user, target, tw, ev):
        return fail(ev, who) if target.cond.get("taunt") else True
    target.cond["taunt"] = 3 if not target.moved_second else 4
    say(ev, tw, "%s 은(는) 도발에 넘어가 버렸다!" % target.name)


def h_torment(bt, move, who, user, target, tw, ev):
    if target.cond.get("torment") or _mental_blocked(bt, user, target, tw, ev):
        return fail(ev, who) if target.cond.get("torment") else True
    target.cond["torment"] = True
    say(ev, tw, "%s 은(는) 트집을 잡혔다!" % target.name)


def h_encore(bt, move, who, user, target, tw, ev):
    last = _last(target)
    if (not last or target.cond.get("encore") or last in ("ENCORE", "TRANSFORM", "MIMIC", "SKETCH",
                                                          "MIRRORMOVE", "STRUGGLE", "SLEEPTALK")
            or target.pp.get(last, 0) <= 0 or last not in target.moves):
        return fail(ev, who)
    if _mental_blocked(bt, user, target, tw, ev):
        return
    target.cond["encore"] = {"move": last, "turns": 3}
    say(ev, tw, "%s 은(는) 앙코르를 받았다!" % target.name)


def h_disable(bt, move, who, user, target, tw, ev):
    last = _last(target)
    if not last or target.cond.get("disable") or last == "STRUGGLE" or target.pp.get(last, 0) <= 0:
        return fail(ev, who)
    if _mental_blocked(bt, user, target, tw, ev):
        return
    target.cond["disable"] = {"move": last, "turns": 4}
    say(ev, tw, "%s 의 %s 을(를) 사슬묶었다!" % (target.name, bt.move_name(last)))


def h_yawn(bt, move, who, user, target, tw, ev):
    if target.status or target.cond.get("yawn") or A.status_blocked(target, "sleep", user) \
            or (terrain(target) in ("electric", "misty") and grounded(target)) \
            or blocked_by_guard(bt, target, tw, user, ev, quiet=True):
        return fail(ev, who)
    target.cond["yawn"] = 2
    say(ev, tw, "%s 은(는) 졸음이 쏟아진다!" % target.name)


def h_curse(bt, move, who, user, target, tw, ev):
    if "GHOST" in user.types():
        if target.cond.get("cursed"):
            return fail(ev, who)
        _chip(user, who, user.maxhp // 2, ev, "%s 은(는) 자신의 체력을 깎아 저주를 걸었다!" % user.name)
        target.cond["cursed"] = True
        return
    _stat(bt, user, who, "atk", 1, ev)
    _stat(bt, user, who, "def", 1, ev)
    _stat(bt, user, who, "spe", -1, ev)


def h_nightmare(bt, move, who, user, target, tw, ev):
    if target.status != "sleep" or target.cond.get("nightmare"):
        return fail(ev, who)
    target.cond["nightmare"] = True
    say(ev, tw, "%s 은(는) 악몽을 꾸기 시작했다!" % target.name)


def h_perish(bt, move, who, user, target, tw, ev):
    hit = False
    for f, fw in ((user, who), (target, tw)):
        if not f.alive() or f.cond.get("perish"):
            continue
        if f is not user and A.has(f, "SOUNDPROOF") and not A.breaks(user):
            A.pop(bt, f, fw, ev)
            continue
        f.cond["perish"] = 3
        hit = True
    if not hit:
        return fail(ev, who)
    say(ev, who, "멸망의노래를 들은 포켓몬은 3턴 뒤에 쓰러진다!")


def h_ingrain(bt, move, who, user, target, tw, ev):
    if user.cond.get("ingrain"):
        return fail(ev, who)
    user.cond["ingrain"] = True
    user.cond.pop("magnetrise", None)
    user.cond.pop("telekinesis", None)
    say(ev, who, "%s 은(는) 뿌리를 박았다!" % user.name)


def h_aquaring(bt, move, who, user, target, tw, ev):
    if user.cond.get("aquaring"):
        return fail(ev, who)
    user.cond["aquaring"] = True
    say(ev, who, "%s 은(는) 물의 베일을 둘렀다!" % user.name)


def h_healblock(bt, move, who, user, target, tw, ev):
    if target.cond.get("healblock") or (A.has(target, "AROMAVEIL") and not A.breaks(user)):
        return fail(ev, who)
    target.cond["healblock"] = 5
    say(ev, tw, "%s 은(는) 회복할 수 없게 되었다!" % target.name)


def h_embargo(bt, move, who, user, target, tw, ev):
    if target.cond.get("embargo"):
        return fail(ev, who)
    target.cond["embargo"] = 5
    say(ev, tw, "%s 은(는) 도구를 쓸 수 없게 되었다!" % target.name)


def h_lockon(bt, move, who, user, target, tw, ev):
    user.cond["lockon"] = 2
    say(ev, who, "%s 은(는) %s 을(를) 겨냥했다!" % (user.name, target.name))


def h_laserfocus(bt, move, who, user, target, tw, ev):
    user.cond["laserfocus"] = 2
    say(ev, who, "%s 은(는) 신경을 곤두세웠다!" % user.name)


def h_focusenergy(bt, move, who, user, target, tw, ev):
    if user.cond.get("focus"):
        return fail(ev, who)
    user.cond["focus"] = True
    say(ev, who, "%s 은(는) 힘을 모으고 있다!" % user.name)


def h_magnetrise(bt, move, who, user, target, tw, ev):
    if user.cond.get("magnetrise") or user.cond.get("ingrain") or bt.field.room("gravity") \
            or user.cond.get("smackdown"):
        return fail(ev, who)
    user.cond["magnetrise"] = 5
    say(ev, who, "%s 은(는) 전자기력으로 떠올랐다!" % user.name)


def h_telekinesis(bt, move, who, user, target, tw, ev):
    if target.cond.get("telekinesis") or target.cond.get("ingrain") or bt.field.room("gravity") \
            or target.cond.get("smackdown"):
        return fail(ev, who)
    target.cond["telekinesis"] = 3
    say(ev, tw, "%s 은(는) 공중으로 떠올랐다!" % target.name)


def h_trap(bt, move, who, user, target, tw, ev):
    if target.cond.get("trapped") or "GHOST" in target.types():
        return fail(ev, who)
    target.cond["trapped"] = who
    say(ev, tw, "%s 은(는) 이제 도망칠 수 없다!" % target.name)


def h_octolock(bt, move, who, user, target, tw, ev):
    if target.cond.get("octolock") or "GHOST" in target.types():
        return fail(ev, who)
    target.cond["octolock"] = who
    say(ev, tw, "%s 은(는) 문어굳히기에 걸렸다!" % target.name)


def h_fairylock(bt, move, who, user, target, tw, ev):
    if bt.field.rooms.get("fairylock"):
        return fail(ev, who)
    bt.field.rooms["fairylock"] = 2
    say(ev, who, FD.ROOM_START["fairylock"])


def h_gastro(bt, move, who, user, target, tw, ev):
    if target.cond.get("gastro") or target.ability in ABILITY_FIXED:
        return fail(ev, who)
    target.cond["gastro"] = True
    say(ev, tw, "%s 의 특성이 효과를 잃었다!" % target.name)


def _set_ability(bt, f, fw, ability, ev):
    _changing(f)
    f.ability = ability
    _changed(f)
    say(ev, fw, "%s 의 특성이 %s 이(가) 되었다!" % (f.name, bt.dex.ability_name(ability)))


def h_ability_change(bt, move, who, user, target, tw, ev):
    k = key(move)
    if k == "WORRYSEED":
        if target.ability in ABILITY_FIXED or target.ability in ("INSOMNIA", "TRUANT"):
            return fail(ev, who)
        _set_ability(bt, target, tw, "INSOMNIA", ev)
        if target.status == "sleep":
            target.status, target.sleep_turns = None, 0
            ev.append({"t": "cure", "who": tw, "text": "%s 은(는) 잠에서 깼다!" % target.name})
    elif k == "SIMPLEBEAM":
        if target.ability in ABILITY_FIXED or target.ability in ("SIMPLE", "TRUANT"):
            return fail(ev, who)
        _set_ability(bt, target, tw, "SIMPLE", ev)
    elif k == "ENTRAINMENT":
        if (not user.ability or user.ability == target.ability or target.ability in ABILITY_FIXED
                or user.ability in ABILITY_FIXED | {"TRACE", "FLOWERGIFT", "IMPOSTER"}):
            return fail(ev, who)
        _set_ability(bt, target, tw, user.ability, ev)
    elif k in ("ROLEPLAY", "DOODLE"):
        if (not target.ability or user.ability == target.ability or user.ability in ABILITY_FIXED
                or target.ability in ABILITY_FIXED | {"TRACE", "WONDERGUARD", "IMPOSTER"}):
            return fail(ev, who)
        _set_ability(bt, user, who, target.ability, ev)
    elif k == "SKILLSWAP":
        if (not user.ability or not target.ability or user.ability in ABILITY_FIXED | {"WONDERGUARD"}
                or target.ability in ABILITY_FIXED | {"WONDERGUARD"}):
            return fail(ev, who)
        a1, a2 = user.ability, target.ability
        _set_ability(bt, user, who, a2, ev)
        _set_ability(bt, target, tw, a1, ev)


def _set_types(bt, f, fw, types, ev):
    _changing(f)
    f.types_override = list(types)
    f.cond.pop("extraType", None)
    _changed(f)
    say(ev, fw, "%s 은(는) %s 타입이 되었다!" % (f.name, "·".join(bt.dex.type_name(t) for t in types)))


def h_type_change(bt, move, who, user, target, tw, ev):
    k = key(move)
    if k == "SOAK":
        if target.types() == ["WATER"] or target.ability in ("MULTITYPE", "RKSSYSTEM"):
            return fail(ev, who)
        _set_types(bt, target, tw, ["WATER"], ev)
    elif k == "MAGICPOWDER":
        if target.types() == ["PSYCHIC"]:
            return fail(ev, who)
        _set_types(bt, target, tw, ["PSYCHIC"], ev)
    elif k in ("TRICKORTREAT", "FORESTSCURSE"):
        t = "GHOST" if k == "TRICKORTREAT" else "GRASS"
        if t in target.types():
            return fail(ev, who)
        target.cond["extraType"] = t
        say(ev, tw, "%s 에게 %s 타입이 추가되었다!" % (target.name, bt.dex.type_name(t)))
    elif k == "REFLECTTYPE":
        if not target.types() or user.types() == target.types():
            return fail(ev, who)
        _set_types(bt, user, who, target.types(), ev)
    elif k == "CONVERSION":
        first = bt.move_of(user.moves[0]) if user.moves else {}
        t = first.get("type")
        if not t or t in user.types():
            return fail(ev, who)
        _set_types(bt, user, who, [t], ev)
    elif k == "CONVERSION2":
        last = _last(target)
        if not last:
            return fail(ev, who)
        lt = bt.move_of(last).get("type")
        from_types = [t for t in bt.dex.types if t not in user.types()
                      and bt.dex.effectiveness(lt, [t]) < 1] if lt else []
        if not from_types:
            return fail(ev, who)
        _set_types(bt, user, who, [bt.rng.choice(sorted(from_types))], ev)
    elif k == "ELECTRIFY":
        target.cond["electrify"] = True
        say(ev, tw, "%s 의 기술이 전기 타입이 되었다!" % target.name)


def h_odorsleuth(bt, move, who, user, target, tw, ev):
    target.cond["identified"] = True
    say(ev, tw, "%s 의 정체를 꿰뚫어 보았다!" % target.name)


def h_transform(bt, move, who, user, target, tw, ev):
    if user.cond.get("transformed") or target.cond.get("transformed") or target.cond.get("sub"):
        return fail(ev, who)
    _changing(user)
    for s in ("atk", "def", "spa", "spd", "spe"):
        user.base[s] = target.base.get(s, user.base.get(s))
    user.types_override = list(target.types())
    user.ability = target.ability
    user.moves = list(target.moves)
    for m in user.moves:
        user.pp[m] = min(5, bt.move_of(m).get("pp", 5) or 5)
    user.stages = dict(target.stages)
    user.cond["transformed"] = target.mon.get("species")
    _changed(user)
    say(ev, who, "%s 은(는) %s(으)로 변신했다!" % (user.name, target.name))


def h_mimic(bt, move, who, user, target, tw, ev):
    last = _last(target)
    if not last or last in CALL_BAN or last in user.moves or "MIMIC" not in user.moves:
        return fail(ev, who)
    _changing(user)
    i = user.moves.index("MIMIC")
    user.moves[i] = last
    user.pp[last] = bt.move_of(last).get("pp", 5) or 5
    _changed(user)
    say(ev, who, "%s 은(는) %s 을(를) 흉내 냈다!" % (user.name, bt.move_name(last)))


def h_sketch(bt, move, who, user, target, tw, ev):
    """스케치: **영원히** 배운다. 유저 포켓몬이면 서버가 DB 에 적는다 (mon['_sketched']).

    야생·관장 배틀의 **내 포켓몬**만 영원하다. 유저 배틀은 서버가 한 판을 통째로 계산하는
    시뮬레이션이라 그 판에서만 배운다 (넘겨받은 포켓몬 자료를 고치면 같은 시드로 다시 돌렸을 때
    다른 판이 나온다). 야생·관장의 상대 포켓몬도 그 판에서만이다.
    """
    last = _last(target)
    if not last or last in ("SKETCH", "STRUGGLE", "CHATTER") or last in user.moves or "SKETCH" not in user.moves:
        return fail(ev, who)
    i = user.moves.index("SKETCH")
    user.moves[i] = last
    user.pp.pop("SKETCH", None)
    user.pp[last] = bt.move_of(last).get("pp", 5) or 5
    mon_moves = list(user.mon.get("moves") or [])
    if "SKETCH" in mon_moves and who == "me" and bt.kind in ("wild", "gym"):
        mon_moves[mon_moves.index("SKETCH")] = last
        user.mon["moves"] = mon_moves
        user.mon["_sketched"] = True
    if user.cond.get("orig"):
        orig = user.cond["orig"]
        if "SKETCH" in orig["moves"]:
            orig["moves"][orig["moves"].index("SKETCH")] = last
        _changed(user)
    say(ev, who, "%s 은(는) %s 을(를) 스케치했다!" % (user.name, bt.move_name(last)))


def h_psychup(bt, move, who, user, target, tw, ev):
    user.stages = dict(target.stages)
    if target.cond.get("focus"):
        user.cond["focus"] = True
    say(ev, who, "%s 은(는) %s 의 능력 변화를 복사했다!" % (user.name, target.name))


def h_haze(bt, move, who, user, target, tw, ev):
    for f in (user, target):
        for s in f.stages:
            f.stages[s] = 0
    say(ev, who, "모든 능력 변화가 원래대로 돌아왔다!")


def h_topsyturvy(bt, move, who, user, target, tw, ev):
    if not any(target.stages.values()):
        return fail(ev, who)
    for s in target.stages:
        target.stages[s] = -target.stages[s]
    say(ev, tw, "%s 의 능력 변화가 뒤집어졌다!" % target.name)


def h_stat_swap(bt, move, who, user, target, tw, ev):
    k = key(move)
    stats = {"POWERSWAP": ("atk", "spa"), "GUARDSWAP": ("def", "spd"),
             "HEARTSWAP": ("atk", "def", "spa", "spd", "spe", "acc", "eva")}[k]
    for s in stats:
        user.stages[s], target.stages[s] = target.stages[s], user.stages[s]
    say(ev, who, "%s 은(는) 상대와 능력 변화를 바꿨다!" % user.name)


def h_split(bt, move, who, user, target, tw, ev):
    k = key(move)
    stats = ("atk", "spa") if k == "POWERSPLIT" else ("def", "spd")
    _changing(user)
    _changing(target)
    for s in stats:
        avg = (user.base[s] + target.base[s]) // 2
        user.base[s] = target.base[s] = avg
    _changed(user)
    _changed(target)
    say(ev, who, "%s 은(는) 상대와 %s 을(를) 나눠 가졌다!" % (user.name, "파워" if k == "POWERSPLIT" else "가드"))


def h_speedswap(bt, move, who, user, target, tw, ev):
    _changing(user)
    _changing(target)
    user.base["spe"], target.base["spe"] = target.base["spe"], user.base["spe"]
    _changed(user)
    _changed(target)
    say(ev, who, "%s 은(는) 상대와 스피드를 바꿨다!" % user.name)


def h_powertrick(bt, move, who, user, target, tw, ev):
    _changing(user)
    user.base["atk"], user.base["def"] = user.base["def"], user.base["atk"]
    if user.cond.get("powertrick"):
        user.cond.pop("powertrick", None)
    else:
        user.cond["powertrick"] = True
    _changed(user)
    say(ev, who, "%s 은(는) 공격과 방어를 바꿨다!" % user.name)


def h_spicy(bt, move, who, user, target, tw, ev):
    _stat(bt, target, tw, "atk", 2, ev, source=user)
    _stat(bt, target, tw, "def", -2, ev, source=user)


def h_acupressure(bt, move, who, user, target, tw, ev):
    room = [s for s in ("atk", "def", "spa", "spd", "spe", "acc", "eva") if user.stages.get(s, 0) < 6]
    if not room:
        return fail(ev, who)
    _stat(bt, user, who, bt.rng.choice(room), 2, ev)


def h_bellydrum(bt, move, who, user, target, tw, ev):
    if user.hp <= user.maxhp // 2 or user.stages.get("atk", 0) >= 6:
        return fail(ev, who)
    _chip(user, who, user.maxhp // 2, ev, "%s 은(는) 체력을 깎아 공격을 최대로 올렸다!" % user.name)
    user.stages["atk"] = 6
    ev.append({"t": "stat", "who": who, "stat": "atk", "change": 6,
               "text": "%s 의 공격이 최대로 올랐다!" % user.name})


def h_filletaway(bt, move, who, user, target, tw, ev):
    if user.hp <= user.maxhp // 2:
        return fail(ev, who)
    _chip(user, who, user.maxhp // 2, ev, "%s 은(는) 제 살을 깎았다!" % user.name)
    for s in ("atk", "spa", "spe"):
        _stat(bt, user, who, s, 2, ev)


def h_takeheart(bt, move, who, user, target, tw, ev):
    if user.status:
        user.status, user.sleep_turns = None, 0
        ev.append({"t": "cure", "who": who, "text": "%s 의 상태이상이 나았다!" % user.name})
    _stat(bt, user, who, "spa", 1, ev)
    _stat(bt, user, who, "spd", 1, ev)


def h_tidyup(bt, move, who, user, target, tw, ev):
    cleared = False
    for side in bt.field.sides.values():
        for hz in FD.HAZARDS:
            cleared |= bool(side.pop(hz, None))
    for f in (user, target):
        cleared |= bool(f.cond.pop("sub", None))
    if cleared:
        say(ev, who, "주변이 깨끗하게 정리되었다!")
    _stat(bt, user, who, "atk", 1, ev)
    _stat(bt, user, who, "spe", 1, ev)


def h_rototiller(bt, move, who, user, target, tw, ev):
    hit = False
    for f, fw in ((user, who), (target, tw)):
        if f.alive() and "GRASS" in f.types() and grounded(f):
            _stat(bt, f, fw, "atk", 1, ev, source=user)
            _stat(bt, f, fw, "spa", 1, ev, source=user)
            hit = True
    if not hit:
        fail(ev, who)


def h_decorate(bt, move, who, user, target, tw, ev):
    _stat(bt, target, tw, "atk", 2, ev, source=user)
    _stat(bt, target, tw, "spa", 2, ev, source=user)


# ---- 대타·체력
def h_substitute(bt, move, who, user, target, tw, ev):
    cost = user.maxhp // 4
    if user.cond.get("sub") or user.hp <= cost or cost <= 0:
        return fail(ev, who)
    _chip(user, who, cost, ev, "%s 의 대타가 나타났다!" % user.name)
    user.cond["sub"] = cost
    user.cond.pop("bound", None)


def h_shedtail(bt, move, who, user, target, tw, ev):
    cost = (user.maxhp + 1) // 2
    if user.hp <= cost or not _team_others(bt, who, user) or bt.kind == "wild":
        return fail(ev, who)
    _chip(user, who, cost, ev, "%s 은(는) 꼬리를 잘라 대타를 만들었다!" % user.name)
    bt.request_switch(who, "shed", ev, "SHEDTAIL", {"sub": user.maxhp // 4})


def h_painsplit(bt, move, who, user, target, tw, ev):
    avg = (user.hp + target.hp) // 2
    for f, fw in ((user, who), (target, tw)):
        if f.hp < avg:
            gain = min(avg, f.maxhp) - f.hp
            f.hp += gain
            ev.append({"t": "heal", "who": fw, "amount": gain, "hp": f.hp, "maxhp": f.maxhp,
                       "text": "%s 은(는) 체력을 나눠 받았다!" % f.name})
        elif f.hp > avg:
            _chip(f, fw, f.hp - avg, ev, "%s 은(는) 체력을 나눠 주었다!" % f.name)


def h_healbell(bt, move, who, user, target, tw, ev):
    cured = 0
    for m in bt.team_of(who):
        if m.status and m.alive():
            m.status, m.sleep_turns = None, 0
            cured += 1
    say(ev, who, "%s 의 동료들의 상태이상이 나았다!" % user.name if cured else "하지만 아무 일도 일어나지 않았다!")
    if cured and user.side_name:
        ev.append({"t": "cure", "who": who, "text": "상태이상이 나았다!"})


def h_psychoshift(bt, move, who, user, target, tw, ev):
    if not user.status or target.status:
        return fail(ev, who)
    st = user.status
    bt._apply_status(target, st, ev, source=user)
    if target.status == st:
        user.status, user.sleep_turns = None, 0
        ev.append({"t": "cure", "who": who, "text": "%s 의 상태이상이 옮겨 갔다!" % user.name})
    else:
        fail(ev, who)


def h_rest(bt, move, who, user, target, tw, ev):
    if user.hp >= user.maxhp or user.status == "sleep" or A.status_blocked(user, "sleep") \
            or (terrain(user) in ("electric", "misty") and grounded(user)):
        return fail(ev, who)
    if user.cond.get("healblock"):
        return fail(ev, who)
    user.status, user.sleep_turns = "sleep", 2
    user.cond.pop("nightmare", None)
    ev.append({"t": "ailment", "status": "sleep", "who": who, "text": "%s 은(는) 잠들어 기운을 차렸다!" % user.name})
    _heal(bt, user, who, user.maxhp, ev, "%s 은(는) 체력을 모두 회복했다!" % user.name)


def h_wish(bt, move, who, user, target, tw, ev):
    side = bt.field.side(who)
    if side.get("wish"):
        return fail(ev, who)
    side["wish"] = {"turns": 2, "amount": max(1, user.maxhp // 2), "by": user.name}
    say(ev, who, "%s 은(는) 소원을 빌었다!" % user.name)


def h_lunarblessing(bt, move, who, user, target, tw, ev):
    did = _heal(bt, user, who, user.maxhp // 4, ev)
    if user.status:
        user.status, user.sleep_turns = None, 0
        ev.append({"t": "cure", "who": who, "text": "%s 의 상태이상이 나았다!" % user.name})
        did = True
    if not did:
        fail(ev, who)


def h_healingwish(bt, move, who, user, target, tw, ev):
    if not _team_others(bt, who, user) or bt.kind == "wild":
        return fail(ev, who)
    bt.field.side(who)[key(move).lower()] = True
    user.hp = 0
    say(ev, who, "%s 은(는) 다음 동료를 위해 소원을 빌었다!" % user.name)


def h_revival(bt, move, who, user, target, tw, ev):
    down = [m for m in bt.team_of(who) if not m.alive() and m is not user]
    if not down or bt.kind == "wild":
        return fail(ev, who)
    pick = max(down, key=lambda m: (m.level, m.maxhp))
    pick.hp = max(1, pick.maxhp // 2)
    pick.status, pick.sleep_turns = None, 0
    pick.ab.pop("fainted", None)
    say(ev, who, "%s 이(가) 되살아났다!" % pick.name)
    hook = getattr(bt, "on_revive", None)
    if hook:
        hook(who, pick)


def h_destinybond(bt, move, who, user, target, tw, ev):
    if user.cond.get("dbondUsed"):
        user.cond.pop("dbondUsed", None)
        return fail(ev, who)
    user.cond["destinybond"] = True
    user.cond["dbondUsed"] = True
    say(ev, who, "%s 은(는) 상대를 길동무로 삼으려 한다!" % user.name)


def h_grudge(bt, move, who, user, target, tw, ev):
    user.cond["grudge"] = True
    say(ev, who, "%s 은(는) 원념을 품었다!" % user.name)


def h_spite(bt, move, who, user, target, tw, ev):
    last = _last(target)
    if not last or target.pp.get(last, 0) <= 0:
        return fail(ev, who)
    target.pp[last] = max(0, target.pp[last] - 4)
    say(ev, tw, "%s 의 %s PP 가 줄었다!" % (target.name, bt.move_name(last)))


def h_imprison(bt, move, who, user, target, tw, ev):
    shared = [m for m in user.moves if m in target.moves]
    if user.cond.get("imprison") or not shared:
        return fail(ev, who)
    user.cond["imprison"] = list(user.moves)
    say(ev, who, "%s 은(는) 기술을 봉인했다!" % user.name)


def h_snatch(bt, move, who, user, target, tw, ev):
    user.cond["snatch"] = True
    say(ev, who, "%s 은(는) 상대의 기술을 노리고 있다!" % user.name)


def h_magiccoat(bt, move, who, user, target, tw, ev):
    user.cond["magiccoat"] = True
    say(ev, who, "%s 은(는) 매직코트를 둘렀다!" % user.name)


def h_instruct(bt, move, who, user, target, tw, ev):
    last = _last(target)
    if not last or last in CALL_BAN or last in CHARGE_BAN or target.pp.get(last, 0) <= 0 \
            or last not in target.moves or not target.alive():
        return fail(ev, who)
    say(ev, tw, "%s 은(는) 지휘를 받아 다시 기술을 썼다!" % target.name)
    bt._use(tw, target, user, last, ev, instructed=True)


# ---- 다른 기술을 부른다
def _call(bt, who, user, target, k2, ev, text=None):
    if text:
        say(ev, who, text)
    bt._use(who, user, target, k2, ev, called=True)


def h_metronome(bt, move, who, user, target, tw, ev):
    pool = sorted(k for k, md in bt.dex.moves.items()
                  if k not in CALL_BAN and md.get("id", 0) < 10000 and "SPECIAL" not in k
                  and not k.endswith("PHYSICAL") and not k.startswith("MAX") and not k.startswith("GMAX")
                  and (MC.attacks(md) or md.get("cat") == "status"))
    _call(bt, who, user, target, bt.rng.choice(pool), ev)


def h_copycat(bt, move, who, user, target, tw, ev):
    last = getattr(bt, "last_before", None)
    if not last or last in CALL_BAN:
        return fail(ev, who)
    _call(bt, who, user, target, last, ev)


def h_mirrormove(bt, move, who, user, target, tw, ev):
    last = _last(target)
    if not last or last in CALL_BAN or "mirror" not in flags(bt.move_of(last)):
        return fail(ev, who)
    _call(bt, who, user, target, last, ev)


def h_naturepower(bt, move, who, user, target, tw, ev):
    k2 = NATURE_POWER.get(terrain(user), "TRIATTACK")
    _call(bt, who, user, target, k2, ev, "자연의힘은 %s 이(가) 되었다!" % bt.move_name(k2))


def h_sleeptalk(bt, move, who, user, target, tw, ev):
    if user.status != "sleep":
        return fail(ev, who)
    pool = [m for m in user.moves if m != "SLEEPTALK" and m not in CALL_BAN and m not in CHARGE_BAN]
    if not pool:
        return fail(ev, who)
    _call(bt, who, user, target, bt.rng.choice(pool), ev)


# ---- 도구
def h_trick(bt, move, who, user, target, tw, ev):
    a, b = user._held if MC.item_on(user) else None, target._held if MC.item_on(target) else None
    if (not a and not b) or (A.has(target, "STICKYHOLD") and not A.breaks(user)) or target.cond.get("sub"):
        return fail(ev, who)
    user.held, target.held = b, a
    user.used = target.used = False
    user.item_gone = target.item_gone = False
    user.locked = target.locked = None
    say(ev, who, "%s 은(는) 도구를 바꿔치기했다!" % user.name)
    if b:
        say(ev, who, "%s 은(는) %s 을(를) 받았다!" % (user.name, H.name(b)))
    if a:
        say(ev, tw, "%s 은(는) %s 을(를) 받았다!" % (target.name, H.name(a)))


def h_recycle(bt, move, who, user, target, tw, ev):
    orig = H.normalize(user.mon.get("held"))
    if not orig or not (user.used or user.item_gone) or user.cond.get("embargo"):
        return fail(ev, who)
    user.held = orig
    user.used = False
    user.item_gone = False
    say(ev, who, "%s 은(는) %s 을(를) 되살렸다!" % (user.name, H.name(orig)))


def h_teatime(bt, move, who, user, target, tw, ev):
    ate = False
    for f, fw in ((user, who), (target, tw)):
        if f.alive() and MC.item_on(f) and (f.held or "").endswith("BERRY"):
            ate |= eat_berry(bt, f, fw, ev)
    if not ate:
        fail(ev, who)


def eat_berry(bt, f, fw, ev):
    """다과회: 체력 조건 없이 열매를 먹는다."""
    h = f.held
    say(ev, fw, "%s 은(는) %s 을(를) 먹었다!" % (f.name, H.name(h)))
    spec = H.HEAL_BERRY.get(h)
    if spec:
        _thr, kind, amt = spec
        _heal(bt, f, fw, amt if kind == "flat" else f.maxhp * amt, ev)
    cure = H.CURE_BERRY.get(h)
    if cure and f.status and (cure == "*" or cure == f.status):
        f.status, f.sleep_turns = None, 0
        ev.append({"t": "cure", "who": fw, "text": "%s 의 상태이상이 나았다!" % f.name})
    pinch = H.PINCH_BERRY.get(h)
    if pinch and pinch[0] == "stat":
        _stat(bt, f, fw, pinch[1], 1, ev)
    if h == "LEPPABERRY":
        for m in f.moves:
            mx = bt.move_of(m).get("pp", 5) or 5
            if f.pp.get(m, 0) < mx:
                f.pp[m] = min(mx, f.pp.get(m, 0) + 10)
                break
    f.used = True
    return True


# ---- 날씨·필드·진영
def h_weather(bt, move, who, user, target, tw, ev):
    if not set_weather(bt, WEATHER_MOVES[key(move)], ev, who):
        fail(ev, who)


def h_terrain(bt, move, who, user, target, tw, ev):
    if not set_terrain(bt, TERRAIN_MOVES[key(move)], ev, who):
        fail(ev, who)


def h_room(bt, move, who, user, target, tw, ev):
    toggle_room(bt, ROOM_MOVES[key(move)], ev, who)


def h_screen(bt, move, who, user, target, tw, ev):
    k = key(move)
    name = SCREENS[k]
    side = bt.field.side(who)
    if side.get(name) or (k == "AURORAVEIL" and weather(user) not in ("hail", "snow")):
        return fail(ev, who)
    side[name] = 5
    say(ev, who, "%s 이(가) %s 진영을 지킨다!" % (FD.SIDE_KR[name], "우리" if who == "me" else "상대"))


def h_side(bt, move, who, user, target, tw, ev):
    name, turns = SIDE_MOVES[key(move)]
    side = bt.field.side(who)
    if side.get(name):
        return fail(ev, who)
    side[name] = turns
    say(ev, who, "%s 이(가) %s 진영을 감쌌다!" % (FD.SIDE_KR[name], "우리" if who == "me" else "상대"))


def h_hazard(bt, move, who, user, target, tw, ev):
    name, most = HAZARD_MOVES[key(move)]
    side = bt.field.side(tw)
    if side.get(name, 0) >= most:
        return fail(ev, who)
    side[name] = side.get(name, 0) + 1
    say(ev, tw, "%s 진영에 %s 이(가) 깔렸다!" % ("상대" if tw == "foe" else "우리", FD.HAZARD_KR[name]))


def h_courtchange(bt, move, who, user, target, tw, ev):
    keys = ("reflect", "lightscreen", "auroraveil", "safeguard", "mist", "tailwind") + FD.HAZARDS
    me, foe = bt.field.side("me"), bt.field.side("foe")
    a = dict((k, me.pop(k)) for k in keys if k in me)
    b = dict((k, foe.pop(k)) for k in keys if k in foe)
    me.update(b)
    foe.update(a)
    say(ev, who, "서로의 진영 효과를 바꿨다!")


# ---- 교체
def h_drag(bt, move, who, user, target, tw, ev):
    if target.cond.get("ingrain") or (A.has(target, "SUCTIONCUPS") and not A.breaks(user)):
        return fail(ev, who)
    if not bt.request_switch(tw, "drag", ev, key(move)):
        fail(ev, who)


def h_batonpass(bt, move, who, user, target, tw, ev):
    if bt.kind == "wild" or not _team_others(bt, who, user):
        return fail(ev, who)
    bt.request_switch(who, "pass", ev, "BATONPASS", pass_state(user))


def h_teleport(bt, move, who, user, target, tw, ev):
    if bt.kind != "wild" and not _team_others(bt, who, user):
        return fail(ev, who)
    if not bt.request_switch(who, "out", ev, "TELEPORT"):
        fail(ev, who)


HANDLERS = {}
for _k in SINGLES_FAIL:
    HANDLERS[_k] = h_singles_fail
HANDLERS["SPLASH"] = h_splash
for _k in PROTECTS:
    HANDLERS[_k] = h_protect
HANDLERS["ENDURE"] = h_endure
for _k in ("QUICKGUARD", "WIDEGUARD", "CRAFTYSHIELD"):
    HANDLERS[_k] = h_guard
for _k in ("CONFUSERAY", "SUPERSONIC", "SWEETKISS", "TEETERDANCE", "SWAGGER", "FLATTER"):
    HANDLERS[_k] = h_confuse
HANDLERS.update({
    "ATTRACT": h_attract, "TAUNT": h_taunt, "TORMENT": h_torment, "ENCORE": h_encore,
    "DISABLE": h_disable, "YAWN": h_yawn, "CURSE": h_curse, "NIGHTMARE": h_nightmare,
    "PERISHSONG": h_perish, "INGRAIN": h_ingrain, "AQUARING": h_aquaring, "HEALBLOCK": h_healblock,
    "EMBARGO": h_embargo, "LOCKON": h_lockon, "MINDREADER": h_lockon, "LASERFOCUS": h_laserfocus,
    "FOCUSENERGY": h_focusenergy, "MAGNETRISE": h_magnetrise, "TELEKINESIS": h_telekinesis,
    "MEANLOOK": h_trap, "BLOCK": h_trap, "SPIDERWEB": h_trap, "OCTOLOCK": h_octolock,
    "FAIRYLOCK": h_fairylock, "GASTROACID": h_gastro,
    "WORRYSEED": h_ability_change, "SIMPLEBEAM": h_ability_change, "ENTRAINMENT": h_ability_change,
    "ROLEPLAY": h_ability_change, "DOODLE": h_ability_change, "SKILLSWAP": h_ability_change,
    "SOAK": h_type_change, "MAGICPOWDER": h_type_change, "TRICKORTREAT": h_type_change,
    "FORESTSCURSE": h_type_change, "REFLECTTYPE": h_type_change, "CONVERSION": h_type_change,
    "CONVERSION2": h_type_change, "ELECTRIFY": h_type_change, "ODORSLEUTH": h_odorsleuth,
    "FORESIGHT": h_odorsleuth, "MIRACLEEYE": h_odorsleuth,
    "TRANSFORM": h_transform, "MIMIC": h_mimic, "SKETCH": h_sketch, "PSYCHUP": h_psychup,
    "HAZE": h_haze, "TOPSYTURVY": h_topsyturvy, "POWERSWAP": h_stat_swap, "GUARDSWAP": h_stat_swap,
    "HEARTSWAP": h_stat_swap, "POWERSPLIT": h_split, "GUARDSPLIT": h_split, "SPEEDSWAP": h_speedswap,
    "POWERTRICK": h_powertrick, "SPICYEXTRACT": h_spicy, "ACUPRESSURE": h_acupressure,
    "BELLYDRUM": h_bellydrum, "FILLETAWAY": h_filletaway, "TAKEHEART": h_takeheart,
    "TIDYUP": h_tidyup, "ROTOTILLER": h_rototiller, "DECORATE": h_decorate,
    "SUBSTITUTE": h_substitute, "SHEDTAIL": h_shedtail, "PAINSPLIT": h_painsplit,
    "HEALBELL": h_healbell, "AROMATHERAPY": h_healbell, "PSYCHOSHIFT": h_psychoshift, "REST": h_rest,
    "WISH": h_wish, "LUNARBLESSING": h_lunarblessing, "HEALINGWISH": h_healingwish,
    "LUNARDANCE": h_healingwish, "REVIVALBLESSING": h_revival, "DESTINYBOND": h_destinybond,
    "GRUDGE": h_grudge, "SPITE": h_spite, "IMPRISON": h_imprison, "SNATCH": h_snatch,
    "MAGICCOAT": h_magiccoat, "INSTRUCT": h_instruct, "METRONOME": h_metronome, "COPYCAT": h_copycat,
    "MIRRORMOVE": h_mirrormove, "NATUREPOWER": h_naturepower, "SLEEPTALK": h_sleeptalk,
    "TRICK": h_trick, "SWITCHEROO": h_trick, "RECYCLE": h_recycle, "TEATIME": h_teatime,
    "COURTCHANGE": h_courtchange, "ROAR": h_drag, "WHIRLWIND": h_drag, "BATONPASS": h_batonpass,
    "TELEPORT": h_teleport,
})
for _k in WEATHER_MOVES:
    if _k != "CHILLYRECEPTION":
        HANDLERS[_k] = h_weather
for _k in TERRAIN_MOVES:
    HANDLERS[_k] = h_terrain
for _k in ROOM_MOVES:
    HANDLERS[_k] = h_room
for _k in SCREENS:
    HANDLERS[_k] = h_screen
for _k in SIDE_MOVES:
    HANDLERS[_k] = h_side
for _k in HAZARD_MOVES:
    HANDLERS[_k] = h_hazard


# ---------------------------------------------------------------- 공격기에 붙은 것
def before_attack(bt, k, move, who, user, target, tw, ev):
    """맞히기 전. 실패하면 False."""
    if k == "STEELROLLER" and not bt.field.terrain:
        fail(ev, who)
        return False
    if k in SCREEN_BREAKERS and target.alive():
        side = bt.field.side(tw)
        gone = [n for n in ("reflect", "lightscreen", "auroraveil") if side.pop(n, None)]
        if gone:
            say(ev, tw, "%s 이(가) 깨졌다!" % "·".join(FD.SIDE_KR[n] for n in gone))
    return True


def after_attack(bt, k, move, who, user, target, tw, total, sub_hit, ev):
    """때리고 난 뒤 (고속스핀·끌어내기·유턴·필드 부수기·지옥찌르기·떨어뜨리기)."""
    if k in SPINNERS and user.alive() and total:
        side = bt.field.side(who)
        gone = [hz for hz in FD.HAZARDS if side.pop(hz, None)]
        if user.seeded:
            user.seeded = False
            gone.append("씨앗")
        if user.cond.pop("bound", None):
            gone.append("조이기")
        if gone:
            say(ev, who, "%s 은(는) 주변을 깨끗이 털어 냈다!" % user.name)
    if k in TERRAIN_BREAKERS and bt.field.terrain and total:
        t = bt.field.terrain
        bt.field.terrain, bt.field.terrain_turns = None, 0
        say(ev, who, FD.TERRAIN_END[t])
    if k == "SMACKDOWN" and total and target.alive() and not sub_hit:
        target.cond["smackdown"] = True
        target.cond.pop("magnetrise", None)
        target.cond.pop("telekinesis", None)
        if "FLYING" in target.types() or A.has(target, "LEVITATE"):
            say(ev, tw, "%s 은(는) 땅으로 떨어졌다!" % target.name)
    if k in DRAG_ATTACKS and total and target.alive() and user.alive() and not sub_hit:
        if not target.cond.get("ingrain") and not (A.has(target, "SUCTIONCUPS") and not A.breaks(user)):
            bt.request_switch(tw, "drag", ev, k)
    if k in OUT_ATTACKS and total and user.alive() and bt.kind != "wild" and _team_others(bt, who, user):
        bt.request_switch(who, "out", ev, k)


def after_status(bt, k, move, who, user, target, tw, ev):
    """일반 처리(능력 변화)를 한 뒤에 더 하는 것 (막말내뱉기·안개제거·차가운인사)."""
    if k == "DEFOG":
        side = bt.field.side(tw)
        gone = [n for n in ("reflect", "lightscreen", "auroraveil", "safeguard", "mist") if side.pop(n, None)]
        for s in bt.field.sides.values():
            for hz in FD.HAZARDS:
                if s.pop(hz, None):
                    gone.append(hz)
        if bt.field.terrain:
            say(ev, who, FD.TERRAIN_END[bt.field.terrain])
            bt.field.terrain, bt.field.terrain_turns = None, 0
        if gone:
            say(ev, who, "안개와 함께 주변이 깨끗해졌다!")
    if k == "PARTINGSHOT" and user.alive() and bt.kind != "wild" and _team_others(bt, who, user):
        bt.request_switch(who, "out", ev, k)
    if k == "AUTOTOMIZE" and any(e.get("t") == "stat" and e.get("who") == who
                                 and e.get("stat") == "spe" for e in ev):
        # 바디퍼지: 스피드가 바뀌었을 때만(이미 +6 이라 실패하면 그대로) 100kg 가벼워진다.
        # 교체하면 풀린다 (cond 는 물러날 때 비워진다). 안다리걸기·헤비봄버가 본다.
        user.cond["autotomize"] = int(user.cond.get("autotomize") or 0) + 1
        say(ev, who, "%s 은(는) 몸이 가벼워졌다!" % user.name)
    if k == "CHILLYRECEPTION":
        set_weather(bt, "snow", ev, who)
        if user.alive() and bt.kind != "wild" and _team_others(bt, who, user):
            bt.request_switch(who, "out", ev, k)


def heal_percent(k, move, user):
    """날씨로 회복량이 바뀌는 기술 (달빛·아침햇살·광합성·모래모으기)."""
    heal = move.get("heal") or 0
    w = weather(user)
    if k in HEAL_BY_WEATHER:
        if w == "sun":
            return 66
        if w in ("rain", "sand", "hail", "snow"):
            return 25
        return 50
    if k == "SHOREUP":
        return 66 if w == "sand" else 50
    return heal


def stat_boost(k, change, user):
    """쾌청에서 성장은 두 배."""
    if k == "GROWTH" and weather(user) == "sun":
        return change * 2
    return change


def apply_ail(bt, ail, move, user, target, who, tw, ev):
    """HANDLED_STATUS(화상·마비·독·잠듦·얼음) 밖의 부가 효과."""
    if not target.alive():
        return
    k = key(move)
    if ail == "confusion":
        confuse(bt, target, tw, ev, source=user, quiet=MC.attacks(move))
    elif ail == "trap":
        if not target.cond.get("bound"):
            target.cond["bound"] = {"turns": bt.rng.randint(4, 5), "by": who, "move": k}
            say(ev, tw, "%s 은(는) %s 에 붙잡혔다!" % (target.name, bt.move_name(k)))
    elif ail == "silence":
        target.cond["silenced"] = 2
    elif ail == "tar-shot":
        if not target.cond.get("tarshot"):
            target.cond["tarshot"] = True
            say(ev, tw, "%s 은(는) 불에 타기 쉬워졌다!" % target.name)
    elif ail == "no-type-immunity":
        target.cond["identified"] = True


# ---------------------------------------------------------------- 나올 때 (압정·치유소원)
def enter(bt, who, ev):
    f = bt.fighter(who)
    side = bt.field.side(who)
    if not f.alive():
        return
    for wish in ("healingwish", "lunardance"):
        if side.pop(wish, None):
            if f.hp < f.maxhp or f.status:
                f.hp = f.maxhp
                f.status, f.sleep_turns = None, 0
                if wish == "lunardance":
                    for m in f.moves:
                        f.pp[m] = bt.move_of(m).get("pp", f.pp.get(m, 5)) or 5
                ev.append({"t": "heal", "who": who, "amount": 0, "hp": f.hp, "maxhp": f.maxhp,
                           "text": "%s 은(는) 소원을 받아 기운을 되찾았다!" % f.name})
    magic = A.has(f, "MAGICGUARD")
    ground = grounded(f)
    if side.get("stealthrock") and not magic:
        eff = bt.dex.effectiveness("ROCK", f.types())
        _chip(f, who, f.maxhp * eff / 8.0, ev, "뾰족한 바위가 %s 에게 박혔다!" % f.name)
    if side.get("spikes") and ground and not magic and f.alive():
        frac = {1: 8, 2: 6, 3: 4}[min(3, side["spikes"])]
        _chip(f, who, f.maxhp / float(frac), ev, "%s 은(는) 압정을 밟았다!" % f.name)
    if side.get("toxicspikes") and ground and f.alive():
        if "POISON" in f.types():
            side.pop("toxicspikes", None)
            say(ev, who, "%s 은(는) 독압정을 흡수했다!" % f.name)
        elif not f.status and "STEEL" not in f.types() and not side.get("safeguard"):
            bt._apply_status(f, "poison", ev)
    if side.get("stickyweb") and ground and f.alive():
        say(ev, who, "%s 은(는) 끈적끈적네트에 걸렸다!" % f.name)
        bt._change_stat(f, "spe", -1, ev, who, source=bt.fighter(other(who)))


def on_enter_abilities(bt, f, who, ev):
    """날씨·필드를 부르는 특성 (가뭄·잔비·모래날림·눈퍼뜨리기·일렉트릭메이커 ...)."""
    if not A.on(f) or f.cond.get("gastro"):
        return
    w = WEATHER_ABILITY.get(f.ability)
    if w and bt.field.weather != w:
        A.pop(bt, f, who, ev)
        set_weather(bt, w, ev, who)
    t = TERRAIN_ABILITY.get(f.ability)
    if t and bt.field.terrain != t:
        A.pop(bt, f, who, ev)
        set_terrain(bt, t, ev, who)


# ---------------------------------------------------------------- 턴 끝
def end_turn_pre(bt, ev, sides=("me", "foe"), field=True):
    """상태이상 데미지보다 먼저: 날씨 데미지·회복, 희망사항, 그래스필드, 아쿠아링·뿌리박기.

    sides / field 는 레이드용이다 (battle.Battle._end_of_turn 의 설명을 보라).
    """
    fl = bt.field
    w = bt.weather()
    for who in sides:
        f = bt.fighter(who)
        if not f.alive():
            continue
        magic = A.has(f, "MAGICGUARD", "OVERCOAT")
        if w == "sand" and not magic and not any(t in f.types() for t in ("ROCK", "GROUND", "STEEL")) \
                and not A.has(f, "SANDVEIL", "SANDRUSH", "SANDFORCE"):
            _chip(f, who, f.maxhp / 16.0, ev, "모래바람이 %s 을(를) 덮쳤다!" % f.name)
        elif w == "hail" and not magic and "ICE" not in f.types() and not A.has(f, "ICEBODY", "SNOWCLOAK"):
            _chip(f, who, f.maxhp / 16.0, ev, "싸라기눈이 %s 을(를) 덮쳤다!" % f.name)
        if not f.alive():
            continue
        if w == "rain" and A.has(f, "RAINDISH"):
            A.pop(bt, f, who, ev)
            _heal(bt, f, who, f.maxhp / 16.0, ev)
        if w in ("hail", "snow") and A.has(f, "ICEBODY"):
            A.pop(bt, f, who, ev)
            _heal(bt, f, who, f.maxhp / 16.0, ev)
        if A.has(f, "DRYSKIN"):
            if w == "rain":
                A.pop(bt, f, who, ev)
                _heal(bt, f, who, f.maxhp / 8.0, ev)
            elif w == "sun":
                A.pop(bt, f, who, ev)
                _chip(f, who, f.maxhp / 8.0, ev, "%s 은(는) 햇살에 체력을 잃었다!" % f.name)
        if w == "sun" and A.has(f, "SOLARPOWER") and f.alive():
            _chip(f, who, f.maxhp / 8.0, ev, "%s 은(는) 햇살에 체력을 잃었다!" % f.name)
        if w == "rain" and A.has(f, "HYDRATION") and f.status:
            A.pop(bt, f, who, ev)
            f.status, f.sleep_turns = None, 0
            ev.append({"t": "cure", "who": who, "text": "%s 의 상태이상이 나았다!" % f.name})
    for who in (("me", "foe") if field else ()):
        side = fl.side(who)
        wish = side.get("wish")
        if wish:
            wish["turns"] -= 1
            if wish["turns"] <= 0:
                side.pop("wish", None)
                f = bt.fighter(who)
                if f.alive():
                    _heal(bt, f, who, wish["amount"], ev, "%s 의 소원이 이루어졌다!" % wish.get("by", f.name))
    for who in sides:
        f = bt.fighter(who)
        if not f.alive():
            continue
        if fl.terrain == "grassy" and grounded(f):
            _heal(bt, f, who, f.maxhp / 16.0, ev, "%s 은(는) 그래스필드로 체력을 회복했다!" % f.name)
        if f.cond.get("aquaring"):
            _heal(bt, f, who, f.maxhp / 16.0, ev, "%s 은(는) 아쿠아링으로 체력을 회복했다!" % f.name)
        if f.cond.get("ingrain"):
            _heal(bt, f, who, f.maxhp / 16.0, ev, "%s 은(는) 뿌리로 양분을 빨아올렸다!" % f.name)


def end_turn_post(bt, ev, sides=("me", "foe"), field=True):
    """상태이상 데미지·도구·특성 다음: 악몽·저주·조이기·문어굳히기, 남은 턴 세기, 하품·멸망의노래.

    sides / field 는 레이드용이다 (battle.Battle._end_of_turn 의 설명을 보라).
    남은 턴을 세는 것(리플렉터·방·필드·날씨)은 판에 하나뿐이라 field 쪽이다.
    """
    fl = bt.field
    for who in sides:
        f = bt.fighter(who)
        if not f.alive():
            continue
        c = f.cond
        magic = A.has(f, "MAGICGUARD")
        if c.get("nightmare"):
            if f.status != "sleep":
                c.pop("nightmare", None)
            elif not magic:
                _chip(f, who, f.maxhp / 4.0, ev, "%s 은(는) 악몽에 시달리고 있다!" % f.name)
        if c.get("cursed") and f.alive() and not magic:
            _chip(f, who, f.maxhp / 4.0, ev, "%s 은(는) 저주를 받고 있다!" % f.name)
        bound = c.get("bound")
        if bound and f.alive():
            bound["turns"] -= 1
            if bound["turns"] <= 0:
                c.pop("bound", None)
                say(ev, who, "%s 은(는) %s 에서 풀려났다!" % (f.name, bt.move_name(bound.get("move") or "BIND")))
            elif not magic:
                _chip(f, who, f.maxhp / 8.0, ev, "%s 은(는) %s 의 데미지를 입고 있다!"
                      % (f.name, bt.move_name(bound.get("move") or "BIND")))
        if c.get("octolock") and f.alive():
            src = bt.fighter(other(who))
            bt._change_stat(f, "def", -1, ev, who, source=src)
            bt._change_stat(f, "spd", -1, ev, who, source=src)
        for name, text in (("taunt", "%s 의 도발 효과가 풀렸다!"), ("embargo", "%s 은(는) 다시 도구를 쓸 수 있게 되었다!"),
                           ("healblock", "%s 은(는) 다시 회복할 수 있게 되었다!"),
                           ("magnetrise", "%s 의 전자부유가 끝났다!"), ("telekinesis", "%s 은(는) 땅으로 내려왔다!"),
                           ("silenced", None), ("laserfocus", None), ("lockon", None)):
            v = c.get(name)
            if isinstance(v, int) and not isinstance(v, bool) and v > 0:
                v -= 1
                if v <= 0:
                    c.pop(name, None)
                    if text:
                        say(ev, who, text % f.name)
                else:
                    c[name] = v
        for name, text in (("encore", "%s 의 앙코르가 끝났다!"), ("disable", "%s 의 사슬묶기가 풀렸다!")):
            v = c.get(name)
            if v:
                v["turns"] -= 1
                if v["turns"] <= 0 or f.pp.get(v.get("move"), 0) <= 0:
                    c.pop(name, None)
                    say(ev, who, text % f.name)
        if c.get("yawn"):
            c["yawn"] -= 1
            if c["yawn"] <= 0:
                c.pop("yawn", None)
                if not f.status:
                    bt._apply_status(f, "sleep", ev)
        if c.get("perish") and f.alive():
            c["perish"] -= 1
            say(ev, who, "%s 의 멸망 카운트가 %d 이(가) 되었다!" % (f.name, c["perish"]))
            if c["perish"] <= 0:
                c.pop("perish", None)
                f.hp = 0
    if not field:
        return
    for who in ("me", "foe"):
        side = fl.side(who)
        for name in ("reflect", "lightscreen", "auroraveil", "safeguard", "mist", "tailwind"):
            if side.get(name):
                side[name] -= 1
                if side[name] <= 0:
                    side.pop(name, None)
                    say(ev, who, "%s 진영의 %s 이(가) 사라졌다!" % ("우리" if who == "me" else "상대", FD.SIDE_KR[name]))
    for room in list(fl.rooms):
        fl.rooms[room] -= 1
        if fl.rooms[room] <= 0:
            fl.rooms.pop(room, None)
            if FD.ROOM_END.get(room):
                say(ev, None, FD.ROOM_END[room])
    if fl.terrain:
        fl.terrain_turns -= 1
        if fl.terrain_turns <= 0:
            say(ev, None, FD.TERRAIN_END[fl.terrain])
            fl.terrain = None
    if fl.weather:
        fl.weather_turns -= 1
        if fl.weather_turns <= 0:
            say(ev, None, FD.WEATHER_END[fl.weather])
            fl.weather = None


# ---------------------------------------------------------------- AI: 이 변화기가 지금 얼마나 값지나
def _moves_of(bt, f):
    return [bt.move_of(m) for m in f.moves]


def _has_type_move(bt, f, types):
    return any(MC.attacks(md) and md.get("type") in types for md in _moves_of(bt, f))


def _cat_of_best(bt, attacker, defender):
    best, cat = 0, None
    for m in bt.usable(attacker):
        md = bt.move_of(m)
        if not MC.attacks(md):
            continue
        d = bt.estimate(attacker, defender, m)
        if d > best:
            best, cat = d, md.get("cat")
    return cat


def value(bt, k, move, user, target, who, base):
    """'한 대 때린 것' 과 같은 단위. 지금 쓰면 실패하거나 쓸모없으면 0.

    이 목록에 없는 기술이면 None 을 돌려준다 (부르는 쪽이 원래 셈을 쓴다).
    """
    tw = other(who)
    c, tc = user.cond, target.cond
    fl = bt.field
    side, tside = fl.side(who), fl.side(tw)
    team = bt.kind != "wild"
    others = len(_team_others(bt, who, user))
    t_others = len(_team_others(bt, tw, target))
    threat = bt.best_damage(target, user)
    lasts = user.hp / threat if threat > 0 else 9.0
    long_game = max(0.0, min(1.0, (lasts - 1.0) / 2.0))
    hp = user.hp / float(user.maxhp or 1)
    thp = target.hp / float(target.maxhp or 1)
    fresh_target = not target.status and not tc.get("confused")
    blocked_status = (tside.get("safeguard") or (terrain(target) == "misty" and grounded(target)))

    if k in SINGLES_FAIL or k == "SPLASH":
        return 0.0
    if k in PROTECTS:
        if c.get("streak"):
            return 0.0
        chip = target.status in ("burn", "poison") or target.seeded or tc.get("cursed") \
            or tc.get("perish") or tc.get("bound") or tc.get("yawn") == 1
        return base * (0.9 if chip else (0.35 if threat >= user.hp else 0.1))
    if k == "ENDURE":
        if c.get("streak") or user.hp <= 1 or threat < user.hp:
            return 0.0
        pay = any(m in user.moves for m in ("FLAIL", "REVERSAL", "ENDEAVOR"))
        return base * (1.5 if pay else 0.2)
    if k in ("QUICKGUARD", "WIDEGUARD", "CRAFTYSHIELD"):
        return 0.0
    if k in ("CONFUSERAY", "SUPERSONIC", "SWEETKISS", "TEETERDANCE"):
        if tc.get("confused") or A.has(target, "OWNTEMPO") or blocked_status or tc.get("sub"):
            return 0.0
        return base * 0.8 * long_game
    if k in ("SWAGGER", "FLATTER"):
        if tc.get("confused") or A.has(target, "OWNTEMPO") or blocked_status:
            return 0.0
        physical = target.base.get("atk", 0) >= target.base.get("spa", 0)
        return base * (0.2 if (physical == (k == "SWAGGER")) else 0.7) * long_game
    if k == "ATTRACT":
        g1, g2 = user.mon.get("gender"), target.mon.get("gender")
        if tc.get("attract") or not g1 or not g2 or "N" in (g1, g2) or g1 == g2 or A.has(target, "OBLIVIOUS"):
            return 0.0
        return base * 0.9 * long_game
    if k == "TAUNT":
        if tc.get("taunt") or not any(md.get("cat") == "status" for md in _moves_of(bt, target)):
            return 0.0
        return base * 0.6 * long_game
    if k == "TORMENT":
        return 0.0 if tc.get("torment") else base * 0.25 * long_game
    if k == "ENCORE":
        last = _last(target)
        if not last or tc.get("encore") or last not in target.moves:
            return 0.0
        md = bt.move_of(last)
        weak = not MC.attacks(md) or bt.estimate(target, user, last) < threat * 0.5
        return base * (1.0 if weak else 0.1)
    if k == "DISABLE":
        last = _last(target)
        if not last or tc.get("disable") or last not in target.moves:
            return 0.0
        best = bt.estimate(target, user, last)
        return base * (0.8 if best >= threat * 0.9 and best > 0 else 0.15)
    if k == "YAWN":
        if target.status or tc.get("yawn") or blocked_status or A.status_blocked(target, "sleep", user) \
                or (terrain(target) == "electric" and grounded(target)):
            return 0.0
        return base * 1.1 * long_game
    if k == "CURSE":
        if "GHOST" in user.types():
            if tc.get("cursed") or hp <= 0.55:
                return 0.0
            return base * 1.0 * long_game
        if c.get("streak"):
            pass
        return base * (0.6 if user.stages.get("atk", 0) < 2 else 0.0) * long_game
    if k == "NIGHTMARE":
        if target.status != "sleep" or tc.get("nightmare") or target.sleep_turns < 2:
            return 0.0
        return base * 1.0
    if k == "PERISHSONG":
        if tc.get("perish") or not team or others == 0:
            return 0.0
        return base * (1.5 if trapped(bt, target) else 0.1)
    if k in ("INGRAIN", "AQUARING"):
        if c.get(k.lower()):
            return 0.0
        return base * 0.5 * long_game
    if k == "HEALBLOCK":
        heals = any((md.get("heal") or 0) > 0 or "heal" in flags(md) for md in _moves_of(bt, target))
        return 0.0 if tc.get("healblock") or not heals else base * 0.6
    if k == "EMBARGO":
        return 0.0 if tc.get("embargo") or not MC.item_on(target) else base * 0.25
    if k in ("LOCKON", "MINDREADER"):
        low = any(MC.attacks(md) and 0 < (md.get("acc") or 100) < 80 for md in _moves_of(bt, user)) \
            or any(m in MC.OHKO for m in user.moves)
        return 0.0 if c.get("lockon") or not low else base * 0.9
    if k == "LASERFOCUS":
        return 0.0 if c.get("laserfocus") else base * 0.35 * long_game
    if k == "FOCUSENERGY":
        return 0.0 if c.get("focus") else base * 0.45 * long_game
    if k == "MAGNETRISE":
        if c.get("magnetrise") or not grounded(user) or fl.room("gravity"):
            return 0.0
        return base * (0.8 if _has_type_move(bt, target, ("GROUND",)) else 0.05)
    if k == "TELEKINESIS":
        return 0.0
    if k in ("MEANLOOK", "BLOCK", "SPIDERWEB"):
        if tc.get("trapped") or "GHOST" in target.types() or not team:
            return 0.0
        combo = "PERISHSONG" in user.moves or target.status in ("poison", "burn")
        return base * (0.5 if combo else 0.05)
    if k == "OCTOLOCK":
        return 0.0 if tc.get("octolock") or "GHOST" in target.types() else base * 0.6 * long_game
    if k == "FAIRYLOCK":
        return 0.0
    if k == "GASTROACID":
        return 0.0 if tc.get("gastro") or not A.on(target) or target.ability in ABILITY_FIXED else base * 0.3
    if k in ("WORRYSEED", "SIMPLEBEAM", "ENTRAINMENT", "ROLEPLAY", "DOODLE", "SKILLSWAP"):
        if k == "WORRYSEED" and "REST" in target.moves and target.ability != "INSOMNIA":
            return base * 0.5
        return base * 0.05
    if k in ("SOAK", "MAGICPOWDER", "TRICKORTREAT", "FORESTSCURSE"):
        boost = {"SOAK": ("GRASS", "ELECTRIC"), "MAGICPOWDER": ("BUG", "GHOST", "DARK"),
                 "TRICKORTREAT": ("GHOST", "DARK"), "FORESTSCURSE": ("FIRE", "ICE", "FLYING", "BUG", "POISON")}[k]
        if _has_type_move(bt, user, boost):
            return base * 0.5
        return 0.0
    if k in ("REFLECTTYPE", "CONVERSION", "CONVERSION2", "ELECTRIFY"):
        if k == "CONVERSION2" and _last(target) and not c.get("orig"):
            return base * 0.4
        return 0.0
    if k in ("ODORSLEUTH", "FORESIGHT", "MIRACLEEYE"):
        if tc.get("identified"):
            return 0.0
        if "GHOST" in target.types() and _has_type_move(bt, user, ("NORMAL", "FIGHTING")):
            return base * 0.6
        return base * (0.5 if target.stages.get("eva", 0) >= 2 else 0.0)
    if k == "TRANSFORM":
        if c.get("transformed"):
            return 0.0
        mine = sum(user.base.get(s, 0) for s in ("atk", "def", "spa", "spd", "spe"))
        theirs = sum(target.base.get(s, 0) for s in ("atk", "def", "spa", "spd", "spe"))
        return base * (0.8 if theirs > mine * 1.15 else 0.0)
    if k in ("MIMIC", "SKETCH"):
        last = _last(target)
        if not last or last in CALL_BAN or last in user.moves:
            return 0.0
        return base * 0.3
    if k == "PSYCHUP":
        gain = sum(target.stages.values()) - sum(user.stages.values())
        return base * 0.3 * gain if gain > 1 else 0.0
    if k == "HAZE":
        gain = sum(max(0, v) for v in target.stages.values()) - sum(min(0, v) for v in user.stages.values()) \
            - sum(max(0, v) for v in user.stages.values())
        return base * 0.4 * gain if gain >= 2 else 0.0
    if k == "TOPSYTURVY":
        up = sum(max(0, v) for v in target.stages.values())
        return base * 0.5 * up if up >= 2 else 0.0
    if k in ("POWERSWAP", "GUARDSWAP", "HEARTSWAP"):
        stats = {"POWERSWAP": ("atk", "spa"), "GUARDSWAP": ("def", "spd"),
                 "HEARTSWAP": ("atk", "def", "spa", "spd", "spe")}[k]
        gain = sum(target.stages.get(s, 0) - user.stages.get(s, 0) for s in stats)
        return base * 0.3 * gain if gain >= 2 else 0.0
    if k in ("POWERSPLIT", "GUARDSPLIT", "SPEEDSWAP"):
        stats = {"POWERSPLIT": ("atk", "spa"), "GUARDSPLIT": ("def", "spd"), "SPEEDSWAP": ("spe",)}[k]
        if c.get("orig") and k != "SPEEDSWAP":
            return 0.0
        gain = sum(target.base.get(s, 0) - user.base.get(s, 0) for s in stats)
        if k == "SPEEDSWAP":
            return base * 0.6 if target.stat("spe") > user.stat("spe") * 1.2 else 0.0
        return base * 0.4 if gain > 40 else 0.0
    if k == "POWERTRICK":
        return base * 0.4 if not c.get("powertrick") and user.base.get("def", 0) > user.base.get("atk", 0) * 1.3 \
            and _cat_of_best(bt, user, target) == "physical" else 0.0
    if k == "SPICYEXTRACT":
        return 0.0
    if k == "ACUPRESSURE":
        return base * 0.4 * long_game
    if k == "BELLYDRUM":
        if hp <= 0.55 or user.stages.get("atk", 0) >= 2 or _cat_of_best(bt, user, target) != "physical":
            return 0.0
        return base * 2.5 * max(0.0, min(1.0, (user.hp / 2.0 / threat - 1.0) if threat else 1.0))
    if k == "FILLETAWAY":
        if hp <= 0.55 or user.stages.get("spe", 0) >= 2:
            return 0.0
        return base * 2.0 * max(0.0, min(1.0, (user.hp / 2.0 / threat - 1.0) if threat else 1.0))
    if k == "TAKEHEART":
        return base * (0.9 if user.status else (0.5 * long_game if user.stages.get("spa", 0) < 2 else 0.0))
    if k == "TIDYUP":
        hazards = any(side.get(hz) for hz in FD.HAZARDS)
        return base * (0.8 if hazards else 0.6 * long_game) if user.stages.get("atk", 0) < 2 else 0.0
    if k in ("ROTOTILLER", "DECORATE"):
        if k == "ROTOTILLER" and "GRASS" in user.types() and grounded(user) and "GRASS" not in target.types():
            return base * 0.5 * long_game
        return 0.0
    if k == "SUBSTITUTE":
        if c.get("sub") or hp <= 0.3 or threat >= user.maxhp // 4:
            return 0.0
        return base * 1.0 * long_game
    if k == "SHEDTAIL":
        return 0.0 if hp <= 0.55 or not team or others == 0 else base * 0.4
    if k == "PAINSPLIT":
        gain = (user.hp + target.hp) // 2 - user.hp
        return base * 3.0 * gain / float(user.maxhp) if gain > user.maxhp * 0.2 else 0.0
    if k in ("HEALBELL", "AROMATHERAPY"):
        n = sum(1 for m in bt.team_of(who) if m.status and m.alive())
        return base * 0.4 * n
    if k == "PSYCHOSHIFT":
        if not user.status or target.status:
            return 0.0
        return base * 0.9
    if k == "REST":
        if hp > 0.45 or user.status == "sleep" or A.status_blocked(user, "sleep") or c.get("healblock"):
            return 0.0
        return base * (1.6 if "SLEEPTALK" in user.moves else 1.1) * (1.0 - hp)
    if k == "WISH":
        return 0.0 if side.get("wish") or hp > 0.65 else base * 0.9 * (1.0 - hp)
    if k == "LUNARBLESSING":
        return base * (1.2 * (1.0 - hp) + (0.5 if user.status else 0.0)) if hp < 0.6 or user.status else 0.0
    if k in ("HEALINGWISH", "LUNARDANCE"):
        hurt = [m for m in _team_others(bt, who, user) if m.hp < m.maxhp * 0.5 or m.status]
        return base * 0.6 if team and hp < 0.25 and hurt else 0.0
    if k == "REVIVALBLESSING":
        down = [m for m in bt.team_of(who) if not m.alive() and m is not user]
        return base * 2.0 if team and down else 0.0
    if k == "DESTINYBOND":
        if c.get("dbondUsed") or threat < user.hp:
            return 0.0
        slower = bt.speed(who) < bt.speed(tw)
        return base * (2.0 if slower else 0.3)
    if k == "GRUDGE":
        return base * 0.2 if threat >= user.hp else 0.0
    if k == "SPITE":
        last = _last(target)
        return base * 0.1 if last and target.pp.get(last, 0) <= 4 else 0.0
    if k == "IMPRISON":
        shared = [m for m in user.moves if m in target.moves]
        return 0.0 if c.get("imprison") or not shared else base * 0.3
    if k == "SNATCH":
        return base * 0.2 if any("snatch" in flags(md) for md in _moves_of(bt, target)) else 0.0
    if k == "MAGICCOAT":
        return base * 0.3 if any("reflectable" in flags(md) for md in _moves_of(bt, target)) else 0.0
    if k == "INSTRUCT":
        return 0.0
    if k in ("METRONOME",):
        return base * 0.55
    if k in ("COPYCAT", "MIRRORMOVE"):
        last = fl.__dict__.get("last_move") if k == "COPYCAT" else _last(target)
        if not last or last in CALL_BAN:
            return 0.0
        md = bt.move_of(last)
        if k == "MIRRORMOVE" and "mirror" not in flags(md):
            return 0.0
        return bt.estimate(user, target, last) * 0.9 if MC.attacks(md) else base * 0.2
    if k == "NATUREPOWER":
        return bt.estimate(user, target, NATURE_POWER.get(terrain(user), "TRIATTACK"))
    if k == "SLEEPTALK":
        if user.status != "sleep" or user.sleep_turns < 1:
            return 0.0
        return base * 0.9
    if k in ("TRICK", "SWITCHEROO"):
        bad = user._held in ("CHOICEBAND", "CHOICESPECS", "CHOICESCARF", "TOXICORB", "FLAMEORB", "IRONBALL",
                             "LAGGINGTAIL", "STICKYBARB", "FULLINCENSE")
        return base * 0.7 if bad and MC.item_on(user) and not A.has(target, "STICKYHOLD") else 0.0
    if k == "RECYCLE":
        return base * 0.5 if H.normalize(user.mon.get("held")) and (user.used or user.item_gone) else 0.0
    if k == "TEATIME":
        return base * 0.2 if MC.item_on(user) and (user.held or "").endswith("BERRY") else 0.0
    if k in WEATHER_MOVES:
        w = WEATHER_MOVES[k]
        if fl.weather == w:
            return 0.0
        good = {"sun": ("FIRE",), "rain": ("WATER",), "sand": ("ROCK",), "hail": ("ICE",), "snow": ("ICE",)}[w]
        bad = {"sun": ("WATER",), "rain": ("FIRE",), "sand": (), "hail": (), "snow": ()}[w]
        score = 0.0
        if _has_type_move(bt, user, good) or any(t in user.types() for t in good):
            score += 0.5
        if _has_type_move(bt, target, good):
            score -= 0.4
        if _has_type_move(bt, target, bad):
            score += 0.3
        if A.has(user, "SWIFTSWIM", "CHLOROPHYLL", "SANDRUSH", "SLUSHRUSH", "SOLARPOWER", "RAINDISH",
                 "ICEBODY", "HYDRATION", "SANDFORCE", "DRYSKIN"):
            score += 0.6
        if k == "CHILLYRECEPTION":
            score += 0.2 if team and others else 0.0
        return base * max(0.0, score) * long_game
    if k in TERRAIN_MOVES:
        t = TERRAIN_MOVES[k]
        if fl.terrain == t:
            return 0.0
        good = {"electric": "ELECTRIC", "grassy": "GRASS", "misty": None, "psychic": "PSYCHIC"}[t]
        score = 0.5 if good and _has_type_move(bt, user, (good,)) and grounded(user) else 0.0
        if good and _has_type_move(bt, target, (good,)) and grounded(target):
            score -= 0.4
        if t == "misty" and _has_type_move(bt, target, ("DRAGON",)):
            score += 0.3
        if t == "grassy" and hp < 0.8:
            score += 0.2
        return base * max(0.0, score) * long_game
    if k in ROOM_MOVES:
        room = ROOM_MOVES[k]
        if room == "trickroom":
            slower = bt.speed(who) < bt.speed(tw)
            if fl.room("trickroom"):
                return base * 0.6 if not slower else 0.0
            return base * 1.2 * long_game if slower else 0.0
        if room == "gravity":
            if fl.room("gravity"):
                return 0.0
            use = (_has_type_move(bt, user, ("GROUND",)) and not grounded(target)) \
                or any(m in MC.OHKO for m in user.moves)
            return base * 0.5 if use else 0.0
        if room == "mudsport":
            return 0.0 if fl.room(room) or not _has_type_move(bt, target, ("ELECTRIC",)) else base * 0.4
        if room == "watersport":
            return 0.0 if fl.room(room) or not _has_type_move(bt, target, ("FIRE",)) else base * 0.4
        if room == "wonderroom":
            gap = (user.base.get("def", 0) - user.base.get("spd", 0))
            cat = _cat_of_best(bt, target, user)
            helps = (cat == "physical" and gap < -30) or (cat == "special" and gap > 30)
            return 0.0 if fl.room(room) or not helps else base * 0.4
        if room == "magicroom":
            return 0.0 if fl.room(room) or not MC.item_on(target) or MC.item_on(user) else base * 0.2
    if k in SCREENS:
        name = SCREENS[k]
        if side.get(name) or (k == "AURORAVEIL" and weather(user) not in ("hail", "snow")):
            return 0.0
        cat = _cat_of_best(bt, target, user)
        if k == "AURORAVEIL" or (cat == "physical") == (k == "REFLECT"):
            return base * (1.2 if team else 0.7) * long_game
        return base * 0.1
    if k in SIDE_MOVES:
        name = SIDE_MOVES[k][0]
        if side.get(name):
            return 0.0
        if name == "tailwind":
            slower = bt.speed(who) < bt.speed(tw) <= bt.speed(who) * 2
            return base * (1.1 if team else 0.6) * long_game if slower else 0.0
        if name == "safeguard":
            return base * 0.4 if any(md.get("ail") in ("burn", "poison", "paralysis", "sleep", "confusion")
                                     and not MC.attacks(md) for md in _moves_of(bt, target)) else 0.0
        if name == "mist":
            return base * 0.2 if any(md.get("stat") and not md.get("statSelf") and not MC.attacks(md)
                                     for md in _moves_of(bt, target)) else 0.0
    if k in HAZARD_MOVES:
        name, most = HAZARD_MOVES[k]
        if not team or t_others == 0 or tside.get(name, 0) >= most:
            return 0.0
        # 남은 상대 한 마리당 나올 때마다 1/8 쯤. 한 번 까는 게 한 대 때리는 것보다 낫다.
        return base * (0.6 + 0.3 * t_others) * (0.6 if tside.get(name) else 1.0)
    if k == "COURTCHANGE":
        mine = any(side.get(n) for n in FD.HAZARDS)
        theirs_good = any(tside.get(n) for n in ("reflect", "lightscreen", "auroraveil", "tailwind"))
        return base * 0.6 if mine or theirs_good else 0.0
    if k in DRAG_MOVES:
        if not team or t_others == 0 or tc.get("ingrain") or A.has(target, "SUCTIONCUPS"):
            return 0.0
        boosts = sum(max(0, v) for v in target.stages.values())
        hazard = any(tside.get(n) for n in FD.HAZARDS)
        return base * (0.4 * boosts + (0.4 if hazard else 0.0) + (0.5 if tc.get("sub") else 0.0))
    if k == "BATONPASS":
        if not team or others == 0:
            return 0.0
        boosts = sum(max(0, v) for v in user.stages.values())
        return base * 0.4 * boosts if boosts >= 2 else 0.0
    if k == "TELEPORT":
        return base * 0.3 if team and others and hp < 0.35 else 0.0
    if k == "PARTINGSHOT":
        return base * 0.5 if team and others else None
    if k == "DEFOG":
        mine = any(side.get(n) for n in FD.HAZARDS)
        return base * 0.6 if mine else None
    return None


# 관장 팀에 넣어 봐야 AI 가 쓸 일이 없는 기술 (1:1 에서 실패하거나, 상대만 좋아진다)
AI_DEAD = SINGLES_FAIL | {"SPLASH", "INSTRUCT", "TELEKINESIS", "FAIRYLOCK", "SPICYEXTRACT", "DECORATE",
                         "QUICKGUARD", "WIDEGUARD", "CRAFTYSHIELD", "ELECTRIFY", "REFLECTTYPE",
                         "CONVERSION", "TEATIME", "SIMPLEBEAM", "ENTRAINMENT", "ROLEPLAY", "DOODLE",
                         "SKILLSWAP", "SNATCH", "GRUDGE", "SPITE", "SKETCH", "MIMIC"}
