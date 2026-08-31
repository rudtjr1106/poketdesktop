# -*- coding: utf-8 -*-
"""
포켓몬 규칙 엔진 — 서버와 클라이언트가 같은 파일을 쓴다.

능력치, 경험치 곡선, 성격, 성별, 이로치 판정은 전부 본가 시리즈(3세대 이후)
공식을 그대로 따른다. 여기서 계산이 갈리면 나중에 배틀에서 결과가 어긋나므로
반드시 이 모듈 하나만 쓴다.
"""
import hashlib
import json
import math
import os
import random

# ---------------------------------------------------------------- 상수
STATS = ("hp", "atk", "def", "spa", "spd", "spe")
STAT_KR = {"hp": "HP", "atk": "공격", "def": "방어",
           "spa": "특수공격", "spd": "특수방어", "spe": "스피드"}

IV_MAX = 31
EV_MAX = 255
EV_TOTAL_MAX = 510
LEVEL_MAX = 100

SHINY_RATE = 4096          # 1/4096 (6세대 이후 기본값)
HIDDEN_ABILITY_RATE = 128  # 야생에서 숨은 특성이 나올 확률 1/128

# 성격 25종. (오르는 능력, 내리는 능력, 한글 이름)
NATURES = [
    ("HARDY",   None,  None,  "노력"),
    ("LONELY",  "atk", "def", "외로움"),
    ("BRAVE",   "atk", "spe", "용감"),
    ("ADAMANT", "atk", "spa", "고집"),
    ("NAUGHTY", "atk", "spd", "개구쟁이"),
    ("BOLD",    "def", "atk", "대담"),
    ("DOCILE",  None,  None,  "온순"),
    ("RELAXED", "def", "spe", "무사태평"),
    ("IMPISH",  "def", "spa", "장난꾸러기"),
    ("LAX",     "def", "spd", "촐랑"),
    ("TIMID",   "spe", "atk", "겁쟁이"),
    ("HASTY",   "spe", "def", "성급"),
    ("SERIOUS", None,  None,  "성실"),
    ("JOLLY",   "spe", "spa", "명랑"),
    ("NAIVE",   "spe", "spd", "천진난만"),
    ("MODEST",  "spa", "atk", "조심"),
    ("MILD",    "spa", "def", "의젓"),
    ("QUIET",   "spa", "spe", "냉정"),
    ("BASHFUL", None,  None,  "수줍음"),
    ("RASH",    "spa", "spd", "덜렁"),
    ("CALM",    "spd", "atk", "차분"),
    ("GENTLE",  "spd", "def", "얌전"),
    ("SASSY",   "spd", "spe", "건방"),
    ("CAREFUL", "spd", "spa", "신중"),
    ("QUIRKY",  None,  None,  "변덕"),
]
NATURE_BY_NAME = dict((n[0], n) for n in NATURES)

# Essentials 의 GenderRate 문자열 -> 암컷이 나올 확률
GENDER_RATE = {
    "AlwaysMale": 0.0,
    "FemaleOneEighth": 0.125,
    "Female25Percent": 0.25,
    "Female50Percent": 0.5,
    "Female75Percent": 0.75,
    "FemaleSevenEighths": 0.875,
    "AlwaysFemale": 1.0,
    "Genderless": None,
}


# ---------------------------------------------------------------- 경험치 곡선
def exp_for_level(curve, n):
    """레벨 n 에 도달하는 데 필요한 누적 경험치. 본가 공식 그대로."""
    if n <= 1:
        return 0
    n = min(int(n), LEVEL_MAX)
    if curve == "fast":
        return (4 * n ** 3) // 5
    if curve == "medium":
        return n ** 3
    if curve == "slow":
        return (5 * n ** 3) // 4
    if curve == "medium_slow":
        return max(0, (6 * n ** 3) // 5 - 15 * n ** 2 + 100 * n - 140)
    if curve == "erratic":
        if n < 50:
            return (n ** 3 * (100 - n)) // 50
        if n < 68:
            return (n ** 3 * (150 - n)) // 100
        if n < 98:
            return (n ** 3 * ((1911 - 10 * n) // 3)) // 500
        return (n ** 3 * (160 - n)) // 100
    if curve == "fluctuating":
        if n < 15:
            return (n ** 3 * (((n + 1) // 3) + 24)) // 50
        if n < 36:
            return (n ** 3 * (n + 14)) // 50
        return (n ** 3 * ((n // 2) + 32)) // 50
    return n ** 3


def level_from_exp(curve, exp):
    lv = 1
    while lv < LEVEL_MAX and exp >= exp_for_level(curve, lv + 1):
        lv += 1
    return lv


def exp_progress(curve, exp):
    """(현재 레벨, 이번 레벨에서 번 경험치, 다음 레벨까지 필요한 총량)"""
    lv = level_from_exp(curve, exp)
    if lv >= LEVEL_MAX:
        return lv, 0, 0
    cur = exp_for_level(curve, lv)
    nxt = exp_for_level(curve, lv + 1)
    return lv, exp - cur, nxt - cur


# ---------------------------------------------------------------- 능력치
def nature_mult(nature, stat):
    n = NATURE_BY_NAME.get(nature)
    if not n or n[1] == n[2]:
        return 1.0
    if n[1] == stat:
        return 1.1
    if n[2] == stat:
        return 0.9
    return 1.0


def calc_stat(stat, base, iv, ev, level, nature):
    """3세대 이후 능력치 공식."""
    if stat == "hp":
        if base == 1:                      # 껍질몬은 HP 가 항상 1
            return 1
        return (2 * base + iv + ev // 4) * level // 100 + level + 10
    raw = (2 * base + iv + ev // 4) * level // 100 + 5
    return int(math.floor(raw * nature_mult(nature, stat)))


def calc_all_stats(species, ivs, evs, level, nature):
    base = species["base"]
    return dict((s, calc_stat(s, base[s], ivs.get(s, 0), evs.get(s, 0), level, nature))
                for s in STATS)


# ---------------------------------------------------------------- 생성
def roll_gender(species, rng):
    """암컷 비율(femaleRatio)이 있으면 그걸 쓰고, 없으면 옛 문자열 방식을 쓴다."""
    if "femaleRatio" in species:
        p = species["femaleRatio"]
    else:
        p = GENDER_RATE.get(species.get("gender"), 0.5)
    if p is None:
        return "N"
    return "F" if rng.random() < p else "M"


# ---------------------------------------------------------------- 포획
BALL_BONUS = {
    "POKEBALL": 1.0, "GREATBALL": 1.5, "ULTRABALL": 2.0, "MASTERBALL": 255.0,
}


def catch_attempt(species, mon, rng, ball="POKEBALL",
                  hp_ratio=1.0, status_bonus=1.0):
    """5세대 이후 포획 판정. (잡혔는지, 흔들린 횟수) 를 돌려준다.

        a = (3*최대HP - 2*현재HP) * 포획률 * 볼보정 / (3*최대HP) * 상태보정
        a >= 255 이면 그냥 잡힘
        b = 65536 / (255/a)^(3/16) 로 네 번 판정

    아직 배틀이 없어서 체력은 항상 가득 찬 상태(1/3 보정)로 들어간다.
    """
    bonus = BALL_BONUS.get(ball, 1.0)
    rate = max(1, species.get("catch", 45))
    if bonus >= 255:
        return True, 4
    hp_ratio = max(0.0, min(1.0, hp_ratio))
    a = (3.0 - 2.0 * hp_ratio) / 3.0 * rate * bonus * status_bonus
    if a >= 255:
        return True, 4
    a = max(1.0, a)
    b = 65536.0 / ((255.0 / a) ** 0.1875)
    shakes = 0
    for _ in range(4):
        if rng.randrange(65536) < b:
            shakes += 1
        else:
            return False, shakes
    return True, 4


def catch_chance(species, ball="POKEBALL", hp_ratio=1.0, status_bonus=1.0):
    """설명용 확률(0~1). 실제 판정은 catch_attempt 가 한다."""
    bonus = BALL_BONUS.get(ball, 1.0)
    rate = max(1, species.get("catch", 45))
    if bonus >= 255:
        return 1.0
    a = (3.0 - 2.0 * max(0.0, min(1.0, hp_ratio))) / 3.0 * rate * bonus * status_bonus
    if a >= 255:
        return 1.0
    a = max(1.0, a)
    b = 65536.0 / ((255.0 / a) ** 0.1875)
    return min(1.0, (b / 65536.0) ** 4)


def roll_ability(species, rng, hidden_rate=HIDDEN_ABILITY_RATE):
    hidden = species.get("hidden")
    if hidden and hidden_rate and rng.randrange(hidden_rate) == 0:
        return hidden, True
    pool = species.get("abil") or []
    if not pool:
        return (hidden or None), bool(hidden)
    return rng.choice(pool), False


def learnable_moves(species, level):
    """해당 레벨까지 배우는 기술을 순서대로."""
    out = []
    for lv, mv in species.get("moves", []):
        if lv <= level and mv not in out:
            out.append(mv)
    return out


def default_moveset(species, level):
    """야생 개체가 들고 나오는 기술 4개 (가장 최근에 배운 것들)."""
    known = learnable_moves(species, level)
    return known[-4:] if known else []


def make_pokemon(species, level, rng=None, shiny_rate=SHINY_RATE,
                 force_shiny=None, ivs=None):
    """야생 개체 하나를 규칙대로 굴려 만든다."""
    rng = rng or random.Random()
    level = max(1, min(LEVEL_MAX, int(level)))
    if ivs is None:
        ivs = dict((s, rng.randint(0, IV_MAX)) for s in STATS)
    evs = dict((s, 0) for s in STATS)
    nature = rng.choice(NATURES)[0]
    ability, is_hidden = roll_ability(species, rng)
    shiny = force_shiny if force_shiny is not None else (rng.randrange(shiny_rate) == 0)
    return {
        "species": species["internal"],
        "level": level,
        "exp": exp_for_level(species.get("growth", "medium"), level),
        "ivs": ivs,
        "evs": evs,
        "nature": nature,
        "ability": ability,
        "hiddenAbility": is_hidden,
        "gender": roll_gender(species, rng),
        "shiny": bool(shiny),
        "moves": default_moveset(species, level),
        "nickname": None,
        "happiness": species.get("happiness", 70),
    }


# ---------------------------------------------------------------- 도감
class Pokedex(object):
    """pokedex.json 을 감싸고, 야생 등장 추첨까지 담당한다."""

    def __init__(self, data):
        self.raw = data
        self.species = data["species"]
        self.by_internal = dict((s["internal"], s) for s in self.species)
        self.by_num = dict((s["num"], s) for s in self.species)
        self.moves = data.get("moves", {})
        self.abilities = data.get("abilities", {})
        self.types = data.get("types", {})
        self._pool_cache = {}

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def digest(self):
        blob = json.dumps(self.raw, ensure_ascii=False,
                          sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]

    def get(self, key):
        if isinstance(key, int):
            return self.by_num.get(key)
        return self.by_internal.get(key)

    def name(self, key):
        s = self.get(key)
        return s["kr"] if s else str(key)

    def move(self, key):
        return self.moves.get(key)

    def move_name(self, key):
        m = self.moves.get(key)
        return m["kr"] if m else str(key)

    def ability_name(self, key):
        a = self.abilities.get(key)
        return a["kr"] if a else str(key)

    def type_name(self, key):
        t = self.types.get(key)
        return t["kr"] if t else str(key)

    def effectiveness(self, atk_type, def_types):
        """공격 타입이 방어 타입들에게 주는 배율."""
        t = self.types.get(atk_type)
        if not t:
            return 1.0
        eff = t.get("eff") or {}
        mult = 1.0
        for d in def_types:
            mult *= eff.get(d, 1.0)
        return mult

    # ---- 야생 추첨 ----
    @staticmethod
    def bst(species):
        return sum((species.get("base") or {}).values())

    def spawn_pool(self, max_level, max_bst=None):
        """해당 레벨까지 나올 수 있는 종과 누적 가중치.

        max_bst 는 '종족값 합' 상한이다. 이게 없으면 레벨 5 짜리 야생인데
        종족값 600 짜리가 나와서 스타팅 포켓몬이 손도 못 쓰고 진다.
        본가가 초반 루트에 약한 포켓몬만 배치하는 것과 같은 이유다.
        """
        key = (int(max_level), int(max_bst) if max_bst else 0)
        if key in self._pool_cache:
            return self._pool_cache[key]
        pool, cum, total = [], [], 0
        for s in self.species:
            if not s.get("spawnable") or s.get("minLevel", 1) > max_level:
                continue
            if max_bst and self.bst(s) > max_bst:
                continue
            total += s.get("weight", 0)
            pool.append(s)
            cum.append(total)
        if not pool and max_bst:            # 너무 좁으면 상한을 풀어준다
            return self.spawn_pool(max_level, None)
        self._pool_cache[key] = (pool, cum, total)
        return pool, cum, total

    def roll_species(self, max_level, rng=None, max_bst=None):
        rng = rng or random.Random()
        pool, cum, total = self.spawn_pool(max_level, max_bst)
        if not pool or total <= 0:
            return None
        import bisect
        return pool[bisect.bisect_right(cum, rng.randrange(total))]

    def roll_wild(self, min_level=2, max_level=12, rng=None, max_bst=None, **kw):
        """야생 개체 하나. 종을 먼저 뽑고, 그 종이 나올 수 있는 레벨대로 맞춘다."""
        rng = rng or random.Random()
        max_level = max(1, min(LEVEL_MAX, int(max_level)))
        min_level = max(1, min(max_level, int(min_level)))
        s = self.roll_species(max_level, rng, max_bst)
        if s is None:
            return None
        lo = max(min_level, s.get("minLevel", 1))
        lo = min(lo, max_level)
        return make_pokemon(s, rng.randint(lo, max_level), rng, **kw)

    # ---- 개체 요약 ----
    def stats_of(self, mon):
        s = self.get(mon["species"])
        if not s:
            return dict((k, 0) for k in STATS)
        return calc_all_stats(s, mon.get("ivs", {}), mon.get("evs", {}),
                              mon.get("level", 1), mon.get("nature", "HARDY"))

    def describe(self, mon):
        s = self.get(mon["species"])
        if not s:
            return {}
        curve = s.get("growth", "medium")
        lv, got, need = exp_progress(curve, mon.get("exp", 0))
        ivs = mon.get("ivs", {})
        return {
            "num": s["num"],
            "name": mon.get("nickname") or s["kr"],
            "species": s["kr"],
            "types": [self.type_name(t) for t in s["types"]],
            "level": mon.get("level", lv),
            "stats": self.stats_of(mon),
            "ivs": ivs,
            "ivTotal": sum(ivs.get(k, 0) for k in STATS),
            "ivPercent": round(100.0 * sum(ivs.get(k, 0) for k in STATS) / (IV_MAX * 6), 1),
            "nature": NATURE_BY_NAME.get(mon.get("nature", "HARDY"), ("", None, None, "?"))[3],
            "ability": self.ability_name(mon.get("ability")),
            "hiddenAbility": mon.get("hiddenAbility", False),
            "gender": mon.get("gender", "N"),
            "shiny": mon.get("shiny", False),
            "moves": [self.move_name(m) for m in mon.get("moves", [])],
            "expInLevel": got,
            "expToNext": need,
        }


def default_pokedex_path():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, "..", "server", "data", "pokedex.json"),
              os.path.join(here, "data", "pokedex.json"),
              os.path.join(here, "pokedex.json")):
        p = os.path.abspath(p)
        if os.path.exists(p):
            return p
    return None
