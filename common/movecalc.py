# -*- coding: utf-8 -*-
"""위력이나 데미지가 **원작 공식으로 정해지는** 기술.

도감(PokeAPI)은 이런 기술의 위력을 비워 둔다. 우리 도감에는 0 으로 들어오고,
battle.py 는 위력이 0 이면 데미지 계산을 건너뛰었다. 그래서 안다리걸기·
나이트헤드·바둥바둥·카운터 같은 기술이 PP 만 쓰고 아무 일도 안 했다 - 명중
판정은 통과하니 화면에는 "근육몬의 안다리걸기!" 까지만 나오고 끝났다.

여기는 **계산만** 한다. 배틀·특성·도구 모듈을 import 하지 않는다 (abilities 와
battle 이 둘 다 이걸 쓴다). 실패 판정, 이벤트, 상태 바꾸기는 battle.Battle._use 가 한다.

    power(move, user, target)          위력 (0 이면 때리는 기술이 아니다)
    fixed(move, user, target, rng)     고정 데미지 (None 이면 보통 계산)
    move_type(move, user)              타입이 바뀌는 기술 (잠재파워·자연의은혜·심판의뭉치)
    attacks(move)                      때리는 기술인가 (위력이 0 이어도 공식이 있으면 True)

기술 dict 에는 이름 키가 없어서 영어 이름으로 되짚는다 (abilities.key_of 와 같다).
한 번 쓸 때 정해지는 값(매그니튜드의 크기, 프레젠트, 집단폭행의 한 대, 참기의 되돌림)은
_use 가 기술 dict 를 복사해 "_power" / "_fixed" 로 얹어 넘긴다.
"""

# ---------------------------------------------------------------- 분류
WEIGHT_TARGET = {"LOWKICK", "GRASSKNOT"}           # 상대 몸무게
WEIGHT_RATIO = {"HEAVYSLAM", "HEATCRASH"}          # 내 몸무게 / 상대 몸무게
LOW_HP = {"FLAIL", "REVERSAL"}                     # 내 체력이 적을수록
USER_HP = {"ERUPTION": 150, "WATERSPOUT": 150, "DRAGONENERGY": 150}   # 내 체력 비율
TARGET_HP = {"CRUSHGRIP": 120, "WRINGOUT": 120, "HARDPRESS": 100}     # 상대 체력 비율
SPEED = {"ELECTROBALL", "GYROBALL"}
HAPPY = {"RETURN", "PIKAPAPOW", "VEEVEEVOLLEY"}    # 친밀도가 높을수록
UNHAPPY = {"FRUSTRATION"}                          # 친밀도가 낮을수록
MY_BOOSTS = {"STOREDPOWER", "POWERTRIP"}           # 20 + 내 랭크 상승 1당 20
PUNISHMENT = "PUNISHMENT"                          # 60 + 상대 랭크 상승 1당 20
TRUMPCARD = "TRUMPCARD"                            # 남은 PP 가 적을수록
LASTRESPECTS = "LASTRESPECTS"                      # 50 + 쓰러진 동료 1당 50

# 조건이 맞으면 위력이 달라진다 (도감에 기본 위력은 있다)
DOUBLE_IF = {"FACADE", "HEX", "VENOSHOCK", "BRINE", "ACROBATICS", "WAKEUPSLAP",
             "SMELLINGSALTS", "PAYBACK", "AVALANCHE", "REVENGE", "ASSURANCE",
             "BOLTBEAK", "FISHIOUSREND"}
KNOCKOFF = "KNOCKOFF"                              # 상대가 도구를 들고 있으면 1.5배

# 한 번 쓸 때 정해진다 (_use 가 _power 로 넘긴다)
PER_USE = {"MAGNITUDE", "PRESENT", "BEATUP", "FLING", "NATURALGIFT", "SPITUP"}

# 고정 데미지
LEVEL_DAMAGE = {"SEISMICTOSS", "NIGHTSHADE"}
FLAT_DAMAGE = {"DRAGONRAGE": 40, "SONICBOOM": 20}
HALF_HP = {"SUPERFANG", "NATURESMADNESS", "RUINATION"}
OHKO = {"FISSURE", "GUILLOTINE", "HORNDRILL", "SHEERCOLD"}
# 이 턴에 맞은 데미지를 돌려준다: (어느 쪽으로 맞았나, 배율)
COUNTERS = {"COUNTER": ("physical", 2.0), "MIRRORCOAT": ("special", 2.0),
            "METALBURST": (None, 1.5), "COMEUPPANCE": (None, 1.5)}
OTHER_FIXED = {"PSYWAVE", "ENDEAVOR", "FINALGAMBIT", "BIDE"}

VARIABLE = (WEIGHT_TARGET | WEIGHT_RATIO | LOW_HP | set(USER_HP) | set(TARGET_HP) | SPEED
            | HAPPY | UNHAPPY | MY_BOOSTS | {PUNISHMENT, TRUMPCARD, LASTRESPECTS} | PER_USE)
FIXED = LEVEL_DAMAGE | set(FLAT_DAMAGE) | HALF_HP | OHKO | set(COUNTERS) | OTHER_FIXED

# 내던지기 위력 (PokeAPI items.fling_power, 이 게임의 지니는 도구 121개 전부)
FLING_POWER = {
    "AGUAVBERRY": 10, "APICOTBERRY": 10, "ASPEARBERRY": 10, "BABIRIBERRY": 10, "BIGROOT": 10,
    "BLACKBELT": 30, "BLACKGLASSES": 30, "BLACKSLUDGE": 30, "BRIGHTPOWDER": 10, "CHARCOAL": 30,
    "CHARTIBERRY": 10, "CHERIBERRY": 10, "CHESTOBERRY": 10, "CHILANBERRY": 10, "CHOICEBAND": 10,
    "CHOICESCARF": 10, "CHOICESPECS": 10, "CHOPLEBERRY": 10, "COBABERRY": 10, "COLBURBERRY": 10,
    "CUSTAPBERRY": 10, "DRACOPLATE": 90, "DRAGONFANG": 70, "DREADPLATE": 90, "EARTHPLATE": 90,
    "ENIGMABERRY": 10, "EXPERTBELT": 10, "FIGYBERRY": 10, "FISTPLATE": 90, "FLAMEORB": 30,
    "FLAMEPLATE": 90, "FOCUSBAND": 10, "FOCUSSASH": 10, "FULLINCENSE": 10, "GANLONBERRY": 10,
    "HABANBERRY": 10, "HARDSTONE": 100, "IAPAPABERRY": 10, "ICICLEPLATE": 90, "INSECTPLATE": 90,
    "IRONBALL": 130, "IRONPLATE": 90, "JABOCABERRY": 10, "KASIBBERRY": 10, "KEBIABERRY": 10,
    "KINGSROCK": 30, "LAGGINGTAIL": 10, "LANSATBERRY": 10, "LAXINCENSE": 10, "LEFTOVERS": 10,
    "LEPPABERRY": 10, "LIECHIBERRY": 10, "LIFEORB": 30, "LUCKYEGG": 30, "LUMBERRY": 10,
    "MACHOBRACE": 60, "MAGNET": 30, "MAGOBERRY": 10, "MEADOWPLATE": 90, "METALCOAT": 30,
    "METRONOME": 30, "MICLEBERRY": 10, "MINDPLATE": 90, "MIRACLESEED": 30, "MUSCLEBAND": 10,
    "MYSTICWATER": 30, "NEVERMELTICE": 30, "OCCABERRY": 10, "ODDINCENSE": 10, "ORANBERRY": 10,
    "PASSHOBERRY": 10, "PAYAPABERRY": 10, "PECHABERRY": 10, "PETAYABERRY": 10, "POISONBARB": 70,
    "POWERANKLET": 70, "POWERBAND": 70, "POWERBELT": 70, "POWERBRACER": 70, "POWERLENS": 70,
    "POWERWEIGHT": 70, "QUICKCLAW": 80, "RAWSTBERRY": 10, "RAZORCLAW": 80, "RAZORFANG": 30,
    "RINDOBERRY": 10, "ROCKINCENSE": 10, "ROSEINCENSE": 10, "ROWAPBERRY": 10, "SALACBERRY": 10,
    "SCOPELENS": 30, "SEAINCENSE": 10, "SHARPBEAK": 50, "SHELLBELL": 30, "SHUCABERRY": 10,
    "SILKSCARF": 10, "SILVERPOWDER": 10, "SITRUSBERRY": 10, "SKYPLATE": 90, "SMOKEBALL": 30,
    "SOFTSAND": 10, "SOOTHEBELL": 10, "SPELLTAG": 30, "SPLASHPLATE": 90, "SPOOKYPLATE": 90,
    "STARFBERRY": 10, "STICKYBARB": 80, "STONEPLATE": 90, "TANGABERRY": 10, "TOXICORB": 30,
    "TOXICPLATE": 90, "TWISTEDSPOON": 30, "WACANBERRY": 10, "WAVEINCENSE": 10, "WHITEHERB": 10,
    "WIDELENS": 10, "WIKIBERRY": 10, "WISEGLASSES": 10, "YACHEBERRY": 10, "ZAPPLATE": 90,
    "ZOOMLENS": 10,
}
# 내던지면 상대에게 붙는 효과 (PokeAPI item_fling_effects). 열매·허브 효과는 뺐다.
FLING_EFFECT = {"KINGSROCK": "flinch", "RAZORFANG": "flinch", "POISONBARB": "poison",
                "TOXICORB": "poison", "FLAMEORB": "burn"}

# 자연의은혜 (PokeAPI berries.natural_gift_*). 표는 5세대 값이라 6세대부터처럼 +20 해서 쓴다.
NATURAL_GIFT = {
    "AGUAVBERRY": ("DRAGON", 60), "APICOTBERRY": ("GROUND", 80), "ASPEARBERRY": ("ICE", 60),
    "BABIRIBERRY": ("STEEL", 60), "CHARTIBERRY": ("ROCK", 60), "CHERIBERRY": ("FIRE", 60),
    "CHESTOBERRY": ("WATER", 60), "CHILANBERRY": ("NORMAL", 60), "CHOPLEBERRY": ("FIGHTING", 60),
    "COBABERRY": ("FLYING", 60), "COLBURBERRY": ("DARK", 60), "CUSTAPBERRY": ("GHOST", 80),
    "ENIGMABERRY": ("BUG", 80), "FIGYBERRY": ("BUG", 60), "GANLONBERRY": ("ICE", 80),
    "HABANBERRY": ("DRAGON", 60), "IAPAPABERRY": ("DARK", 60), "JABOCABERRY": ("DRAGON", 80),
    "KASIBBERRY": ("GHOST", 60), "KEBIABERRY": ("POISON", 60), "LANSATBERRY": ("FLYING", 80),
    "LEPPABERRY": ("FIGHTING", 60), "LIECHIBERRY": ("GRASS", 80), "LUMBERRY": ("FLYING", 60),
    "MAGOBERRY": ("GHOST", 60), "MICLEBERRY": ("ROCK", 80), "OCCABERRY": ("FIRE", 60),
    "ORANBERRY": ("POISON", 60), "PASSHOBERRY": ("WATER", 60), "PAYAPABERRY": ("PSYCHIC", 60),
    "PECHABERRY": ("ELECTRIC", 60), "PETAYABERRY": ("POISON", 80), "RAWSTBERRY": ("GRASS", 60),
    "RINDOBERRY": ("GRASS", 60), "ROWAPBERRY": ("DARK", 80), "SALACBERRY": ("FIGHTING", 80),
    "SHUCABERRY": ("GROUND", 60), "SITRUSBERRY": ("PSYCHIC", 60), "STARFBERRY": ("PSYCHIC", 80),
    "TANGABERRY": ("BUG", 60), "WACANBERRY": ("ELECTRIC", 60), "WIKIBERRY": ("ROCK", 60),
    "YACHEBERRY": ("ICE", 60),
}
NATURAL_GIFT_BONUS = 20

# 심판의뭉치: 플레이트 타입
PLATE_TYPE = {
    "FLAMEPLATE": "FIRE", "SPLASHPLATE": "WATER", "ZAPPLATE": "ELECTRIC", "MEADOWPLATE": "GRASS",
    "ICICLEPLATE": "ICE", "FISTPLATE": "FIGHTING", "TOXICPLATE": "POISON", "EARTHPLATE": "GROUND",
    "SKYPLATE": "FLYING", "MINDPLATE": "PSYCHIC", "INSECTPLATE": "BUG", "STONEPLATE": "ROCK",
    "SPOOKYPLATE": "GHOST", "DRACOPLATE": "DRAGON", "DREADPLATE": "DARK", "IRONPLATE": "STEEL",
}
# 잠재파워: 개체값 홀짝으로 정하는 16타입 (노말·페어리는 안 나온다)
HIDDEN_POWER_TYPES = ["FIGHTING", "FLYING", "POISON", "GROUND", "ROCK", "BUG", "GHOST", "STEEL",
                      "FIRE", "WATER", "GRASS", "ELECTRIC", "PSYCHIC", "ICE", "DRAGON", "DARK"]

# 매그니튜드: (누적 확률 %, 크기, 위력)
MAGNITUDES = [(5, 4, 10), (15, 5, 30), (35, 6, 50), (65, 7, 70), (85, 8, 90), (95, 9, 110),
              (100, 10, 150)]


def key(move):
    return "".join(c for c in ((move or {}).get("en") or "").upper() if c.isalnum())


def attacks(move):
    """때리는 기술인가. 위력이 0 이어도 공식이 있으면 때리는 기술이다."""
    if not move:
        return False
    if move.get("power") and move.get("cat") != "status":
        return True
    k = key(move)
    return k in VARIABLE or k in FIXED


def item_on(f):
    """지금 도구를 들고 있나. 먹은 열매·내던진 도구는 없는 것으로 친다."""
    return bool(f.held) and not getattr(f, "used", False) and not getattr(f, "item_gone", False)


# 틀깨기류. abilities.MOLD_BREAKERS 와 같다 (여기서는 abilities 를 import 하지 않는다).
_MOLD_BREAKERS = ("MOLDBREAKER", "TERAVOLT", "TURBOBLAZE")


def _ability(f):
    """켜져 있는 특성. abilities.on 과 같은 판정 (위액을 맞으면 없는 것)."""
    if f is None or not getattr(f, "ability_on", False) or not getattr(f, "ability", None):
        return None
    if (getattr(f, "cond", None) or {}).get("gastro"):
        return None
    return f.ability


def kg(f, by=None):
    """이 판에서의 몸무게(kg). 원작 순서 그대로:

      1. 도감 몸무게에서 바디퍼지 한 번마다 100kg 을 뺀다 (0.1kg 아래로는 안 간다)
      2. 헤비메탈이면 2배, 라이트메탈이면 절반
      3. 0.1kg 아래로는 안 간다

    by 는 몸무게를 재는 쪽(안다리걸기를 쓴 포켓몬). 틀깨기면 맞는 쪽의 헤비메탈·
    라이트메탈을 무시한다.
    """
    base = float(((getattr(f, "species", None) or {}).get("kg")) or 0.0)
    if not base:
        return 0.0
    w = max(0.1, base - 100.0 * int((getattr(f, "cond", None) or {}).get("autotomize") or 0))
    ab = _ability(f)
    if ab and by is not None and by is not f and _ability(by) in _MOLD_BREAKERS:
        ab = None
    if ab == "HEAVYMETAL":
        w *= 2
    elif ab == "LIGHTMETAL":
        w /= 2.0
    return max(0.1, round(w, 1))


def _stat(f, name):
    try:
        return f.stat(name)
    except Exception:                                           # noqa: BLE001
        return (f.base or {}).get(name, 1)


def _boosts(f):
    return sum(v for k, v in (f.stages or {}).items() if v > 0 and k in ("atk", "def", "spa", "spd", "spe", "acc", "eva"))


def hurt_this_turn(f, kind=None, by=None):
    """이 턴에 상대에게 맞은 데미지. kind 가 physical/special 이면 그쪽만."""
    h = getattr(f, "hurt", None) or {}
    if by is not None and h.get("by") not in (None, by):
        return 0
    if kind:
        return int(h.get(kind) or 0)
    return int((h.get("physical") or 0) + (h.get("special") or 0))


def power(move, user, target):
    """이번에 쓸 위력. 보통 기술은 도감 값 그대로다."""
    if move.get("_power") is not None:
        return int(move["_power"])
    base = int(move.get("power") or 0)
    k = key(move)
    if k in WEIGHT_TARGET:
        w = kg(target, by=user)
        for limit, p in ((10, 20), (25, 40), (50, 60), (100, 80), (200, 100)):
            if w < limit:
                return p
        return 120
    if k in WEIGHT_RATIO:
        r = kg(user) / max(0.1, kg(target, by=user))
        for limit, p in ((5, 120), (4, 100), (3, 80), (2, 60)):
            if r >= limit:
                return p
        return 40
    if k in LOW_HP:
        p = 48 * user.hp // max(1, user.maxhp)
        for limit, pw in ((1, 200), (4, 150), (9, 100), (16, 80), (32, 40)):
            if p <= limit:
                return pw
        return 20
    if k in USER_HP:
        return max(1, USER_HP[k] * user.hp // max(1, user.maxhp))
    if k in TARGET_HP:
        return max(1, TARGET_HP[k] * target.hp // max(1, target.maxhp))
    if k == "ELECTROBALL":
        r = _stat(user, "spe") / float(max(1, _stat(target, "spe")))
        for limit, p in ((4, 150), (3, 120), (2, 80), (1, 60)):
            if r >= limit:
                return p
        return 40
    if k == "GYROBALL":
        return max(1, min(150, 25 * _stat(target, "spe") // max(1, _stat(user, "spe")) + 1))
    if k in HAPPY:
        return max(1, int(user.mon.get("happiness", 70)) * 10 // 25)
    if k in UNHAPPY:
        return max(1, (255 - int(user.mon.get("happiness", 70))) * 10 // 25)
    if k in MY_BOOSTS:
        return 20 + 20 * _boosts(user)
    if k == PUNISHMENT:
        return min(200, 60 + 20 * _boosts(target))
    if k == TRUMPCARD:
        left = user.pp.get(k, 0) if hasattr(user, "pp") else 0
        return {0: 200, 1: 80, 2: 60, 3: 50}.get(left, 40)
    if k == LASTRESPECTS:
        return 50 + 50 * int((getattr(user, "ab", None) or {}).get("down") or 0)
    if k == KNOCKOFF and item_on(target):
        return base * 3 // 2
    if k in DOUBLE_IF and _doubled(k, user, target):
        return base * 2
    if k in PER_USE:
        return 0                     # _use 가 정해 준다. 점수를 매길 때는 expected_power 를 쓴다
    return base


def _doubled(k, user, target):
    if k == "FACADE":
        return user.status in ("burn", "poison", "paralysis", "bad-poison")
    if k == "HEX":
        return bool(target.status)
    if k == "VENOSHOCK":
        return target.status in ("poison", "bad-poison")
    if k == "BRINE":
        return target.hp * 2 <= target.maxhp
    if k == "ACROBATICS":
        return not item_on(user)
    if k == "WAKEUPSLAP":
        return target.status == "sleep"
    if k == "SMELLINGSALTS":
        return target.status == "paralysis"
    if k == "PAYBACK":
        return bool(getattr(user, "moved_second", False))
    if k in ("AVALANCHE", "REVENGE"):
        return hurt_this_turn(user) > 0
    if k == "ASSURANCE":
        return hurt_this_turn(target) > 0
    if k in ("BOLTBEAK", "FISHIOUSREND"):
        return not getattr(user, "moved_second", False)
    return False


def expected_power(move, user, target, team=None):
    """AI 가 점수를 매길 때 쓰는 위력. 한 번 쓸 때 정해지는 것은 기댓값으로."""
    k = key(move)
    if k == "MAGNITUDE":
        return 71
    if k == "PRESENT":
        return 52                    # 40x0.4 + 80x0.3 + 120x0.1 (20% 는 회복시킨다)
    if k == "FLING":
        return FLING_POWER.get(user.held, 0) if item_on(user) else 0
    if k == "NATURALGIFT":
        g = NATURAL_GIFT.get(user.held) if item_on(user) else None
        return (g[1] + NATURAL_GIFT_BONUS) if g else 0
    if k == "SPITUP":
        return 100 * min(3, getattr(user, "stockpile", 0) or 0)
    if k == "BEATUP":
        members = team or [user]
        return sum(beat_up_power(m) for m in members if m.alive() and not m.status)
    return power(move, user, target)


def beat_up_power(member):
    return 5 + int(((member.species or {}).get("base") or {}).get("atk", 50)) // 10


def fixed(move, user, target, rng):
    """고정 데미지. 보통 기술이면 None. 조건이 안 맞아 실패할 기술이면 0."""
    if move.get("_fixed") is not None:
        return int(move["_fixed"])
    k = key(move)
    if k not in FIXED:
        return None
    if k in LEVEL_DAMAGE:
        return user.level
    if k in FLAT_DAMAGE:
        return FLAT_DAMAGE[k]
    if k in HALF_HP:
        return max(1, target.hp // 2)
    if k in OHKO:
        return target.hp
    if k in COUNTERS:
        kind, mult = COUNTERS[k]
        got = hurt_this_turn(user, kind)
        return int(got * mult) if got else 0
    if k == "PSYWAVE":
        return max(1, int(user.level * rng.uniform(0.5, 1.5)))
    if k == "ENDEAVOR":
        return max(0, target.hp - user.hp)
    if k == "FINALGAMBIT":
        return user.hp
    return 0                          # BIDE: 참고 있는 동안은 _use 가 _fixed 로 넘긴다


def ohko_accuracy(move, user, target):
    """일격기 명중률(%). 못 맞히는 상대면 0."""
    k = key(move)
    if target.level > user.level:
        return 0
    if k == "SHEERCOLD" and "ICE" in (target.types() or []):
        return 0
    base = 30 if (k != "SHEERCOLD" or "ICE" in (user.types() or [])) else 20
    return min(100, base + user.level - target.level)


def move_type(move, user):
    """타입이 바뀌는 기술. 아니면 도감 타입."""
    k = key(move)
    if k == "HIDDENPOWER":
        ivs = (user.mon or {}).get("ivs") or {}
        bits = [ivs.get(s, 31) & 1 for s in ("hp", "atk", "def", "spe", "spa", "spd")]
        n = sum(b << i for i, b in enumerate(bits))
        return HIDDEN_POWER_TYPES[n * 15 // 63]
    if k == "NATURALGIFT" and item_on(user) and user.held in NATURAL_GIFT:
        return NATURAL_GIFT[user.held][0]
    if k == "JUDGMENT" and item_on(user) and user.held in PLATE_TYPE:
        return PLATE_TYPE[user.held]
    return move.get("type")


def resolve(move, user, target):
    """damage() 가 쓰는 기술. 위력·타입이 바뀌면 복사본, 아니면 그대로."""
    if not move:
        return move
    k = key(move)
    t = move_type(move, user)
    if k not in VARIABLE and t == move.get("type") and k not in DOUBLE_IF and k != KNOCKOFF:
        return move
    out = dict(move)
    out["type"] = t
    if k not in FIXED:
        if k in PER_USE and move.get("_power") is None:
            out["power"] = expected_power(move, user, target)     # 점수 매길 때
        else:
            out["power"] = power(move, user, target)
    return out
