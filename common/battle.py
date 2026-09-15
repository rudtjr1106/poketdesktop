# -*- coding: utf-8 -*-
"""배틀 엔진 — 1:1 야생 전투.

본가 시리즈(5세대 이후) 계산을 따른다.

    데미지 = ((2*레벨/5 + 2) * 위력 * 공격 / 방어 / 50 + 2) * 보정
    보정   = 자속(1.5) * 타입상성 * 급소(1.5) * 난수(0.85~1.00) * 화상(물리 0.5)

능력 랭크, 상태이상, 연속기, 흡수/반동, 풀죽음까지 다룬다.
판정은 전부 서버에서 돌리고 클라이언트는 결과만 그린다.

용어
    events   한 턴에 일어난 일을 순서대로 담은 목록. 클라이언트가 이걸로
             메시지를 띄우고 애니메이션을 재생한다.
"""
import math
import random

from . import abilities as A
from . import field as FD
from . import held as H
from . import movecalc as MC
from . import pokelogic as P
from . import statusmoves as SM

# ---------------------------------------------------------------- 상수
STAGE_KEYS = ("atk", "def", "spa", "spd", "spe", "acc", "eva")
STAGE_MIN, STAGE_MAX = -6, 6

CRIT_CHANCE = 24            # 1/24 (7세대 이후)
CRIT_MULT = 1.5
STAB = 1.5

STATUS_KR = {
    "burn": "화상", "paralysis": "마비", "poison": "독", "bad-poison": "맹독",
    "sleep": "잠듦", "freeze": "얼음", "confusion": "혼란",
}
STAT_KR = {"atk": "공격", "def": "방어", "spa": "특수공격", "spd": "특수방어",
           "spe": "스피드", "acc": "명중률", "eva": "회피율"}

# 우리가 실제로 처리하는 상태이상. 나머지는 무시한다(효과 없음).
HANDLED_STATUS = ("burn", "paralysis", "poison", "sleep", "freeze")

# 연속기 횟수 분포 (2~5회 기술의 본가 확률)
MULTI_HIT = [2, 2, 2, 3, 3, 3, 4, 5]
# MULTI_HIT 의 평균. 연속기의 기대 타수다.
HITS_AVG = sum(MULTI_HIT) / float(len(MULTI_HIT))


class _EstRng(object):
    """점수를 매길 때 damage() 에 넘기는 가짜 rng.

    지금까지는 기술마다 random.Random(0) 을 새로 만들어 넘겼다. 값은
    맞지만 객체를 만드는 값이 damage() 본체보다 비싸다. 상태를 갖지
    않는 것으로 바꾼다 - **진짜 Random 을 재사용하면 안 된다.** 상태가
    전진해서 부를 때마다 값이 달라지고, 그러면 점수가 흔들린다.

    Random(0).random() 이 0.8444218515250481 이고 uniform(a,b) 는
    a + (b-a)*random() 이라, 아래 식이 예전과 완전히 같은 값을 준다.
    """

    @staticmethod
    def uniform(a, b):
        return a + (b - a) * 0.8444218515250481


EST_RNG = _EstRng()


class _MaxRng(object):
    """난수 보정을 가장 크게(1.0) 주는 가짜 rng. '아무리 세게 들어가도' 를 셀 때."""

    @staticmethod
    def uniform(a, b):
        return b


MAX_RNG = _MaxRng()

# 잡기 모드: 상대 체력이 이만큼 이하가 되면 멈추고 볼을 던질 틈을 준다
SPARE_LOW = 0.25
# 안전한 기술이 이것보다 덜 깎으면 한참 걸리니 그냥 멈춘다 (최대 체력 대비)
SPARE_MIN_HIT = 0.04
# 체력이 이보다 많이 남았으면 '급소만 아니면 안 쓰러지는' 기술도 쓴다
SPARE_RISK_ABOVE = 0.4
# 잡기 모드에서 먼저 거는 상태이상. 포획률이 잠듦 2배, 마비 1.5배.
# 화상·독은 턴마다 체력을 깎아 쓰러뜨릴 수 있어서 안 건다.
SPARE_STATUS = ("sleep", "paralysis")

# 쓸 기술이 하나도 없을 때 쓰는 몸부림.
# 이게 없으면 양쪽 다 PP 가 떨어졌을 때 아무도 못 때려서 배틀이 안 끝난다.
STRUGGLE = "STRUGGLE"
STRUGGLE_MOVE = {
    "kr": "몸부림", "en": "Struggle", "type": "NORMAL", "cat": "physical",
    "power": 50, "acc": 0, "pp": 1, "pri": 0,
    "drain": -25,          # 준 데미지의 1/4 을 자기도 받는다
    "hits": [1, 1], "stat": [], "ail": None,
}

# 아무도 못 때리는 상황이 오래 가지 않게 하는 안전장치.
# 레벨 2~12 배틀은 보통 5턴이면 끝난다.
MAX_TURNS = 80


def stage_mult(stage, kind="normal"):
    """능력 랭크를 배율로."""
    s = max(STAGE_MIN, min(STAGE_MAX, stage))
    if kind == "acc":                       # 명중률/회피율은 분모가 3
        return (3.0 + s) / 3.0 if s >= 0 else 3.0 / (3.0 - s)
    return (2.0 + s) / 2.0 if s >= 0 else 2.0 / (2.0 - s)


class Fighter(object):
    """배틀에 나와 있는 포켓몬 한 마리."""

    def __init__(self, dex, mon, hp=None, pp=None, status=None):
        self.mon = mon
        self.species = dex.get(mon["species"])
        self.level = mon["level"]
        self.base = dex.stats_of(mon)
        # 관장 자료의 능력치 배율 (종족값이 낮은 포켓몬을 조금 올린 것). 야생·PvP 의
        # 포켓몬에는 이 값이 없어서 아무 일도 안 한다.
        boost = mon.get("statBoost")
        if boost:
            self.base = dict((k, int(round(v * float(boost)))) for k, v in self.base.items())
        self.maxhp = self.base["hp"]
        self.hp = self.maxhp if hp is None else max(0, min(self.maxhp, hp))
        self.stages = dict((k, 0) for k in STAGE_KEYS)
        self.status = status
        self.sleep_turns = 0
        self.moves = list(mon.get("moves") or [])
        self.pp = dict(pp) if pp else {}
        for m in self.moves:
            md = dex.move(m)
            self.pp.setdefault(m, (md or {}).get("pp", 5))
        self.flinched = False
        self.name = (mon.get("nickname")
                     or (self.species["kr"] if self.species else mon["species"]))
        self._dex = dex
        # 지닌 도구 (common/held.py). 없으면 None 이고, 그러면 훅은 전부
        # 아무것도 안 한다 - 도구 없는 판의 로그는 예전과 한 글자도 안 다르다.
        self.held = H.normalize(mon.get("held"))
        self.used = False            # 한 번 쓰는 도구를 이 판에서 썼는가
        self.locked = None           # 구애 도구가 잠근 기술
        self.last_move = None
        self.metro = 0               # 메트로놈 연속 횟수
        self.armed = False           # 랑사·미클열매를 먹어 둔 상태
        self.moved_second = False    # 이 턴에 나중에 움직였나 (포커스렌즈)
        # 특성 (common/abilities.py). **ability_on 이 True 인 판에서만** 돈다.
        # 야생·PvP 는 끈다 - 켜면 예전 판의 결과가 달라진다.
        self.ability = "".join(c for c in str(mon.get("ability") or "").upper() if c.isalnum()) or None
        self.ability_on = False
        self.ab = {}                 # 이 판에서 특성이 기억할 것 (타오르는불꽃, 탈 ...)
        self.types_override = None   # 변환자재가 바꾼 타입
        # 기술이 남기는 것 (volatile() 로 저장한다)
        self.seeded = False          # 씨뿌리기에 걸렸다. 물러나면 풀린다
        self.bide = None             # 참기: {"left": 남은 턴, "sum": 모은 데미지}
        self.stockpile = 0           # 비축하기 횟수 (0~3)
        self.item_gone = False       # 내던지기·자연의은혜로 도구를 썼다 (이 판에서만)
        # 이 턴에 상대에게 맞은 데미지 (카운터·미러코트·메탈버스트, 눈사태·리벤지).
        # 턴이 시작할 때 비운다 - 저장하지 않는다.
        self.hurt = None
        # 변화기가 건 것 (혼란·도발·대타출동·방어 ...). 이름 -> 값. statusmoves.py 가 다룬다.
        # JSON 으로 그대로 저장되는 값만 넣는다.
        self.cond = {}
        # 이 포켓몬이 서 있는 판과 진영. Battle 이 붙여 준다 (날씨·원더룸·순풍을 볼 때).
        self.field = None
        self.side_name = None

    # ---- 지닌 도구: 금제·매직룸이면 없는 것처럼 ----
    @property
    def held(self):
        h = self._held
        if h and (self.cond.get("embargo") or (self.field is not None and self.field.room("magicroom"))):
            return None
        return h

    @held.setter
    def held(self, value):
        self._held = value

    # ---- 상태 ----
    def alive(self):
        return self.hp > 0

    def volatile(self):
        """기술이 남긴 상태. 턴마다 잤다 깨는 배틀(야생·관장)이 같이 저장한다."""
        out = {}
        if self.cond:
            out["cond"] = dict(self.cond)
        if self._held != H.normalize(self.mon.get("held")):
            out["heldNow"] = self._held           # 트릭·바꿔치기로 바뀐 도구
        if self.seeded:
            out["seeded"] = True
        if self.bide:
            out["bide"] = dict(self.bide)
        if self.stockpile:
            out["stockpile"] = self.stockpile
        if self.item_gone:
            out["itemGone"] = True
        return out or None

    def load_volatile(self, d):
        d = d or {}
        self.seeded = bool(d.get("seeded"))
        self.bide = dict(d["bide"]) if d.get("bide") else None
        self.stockpile = int(d.get("stockpile") or 0)
        self.item_gone = bool(d.get("itemGone"))
        if self.item_gone:
            self.held = None                 # 이 판에서는 도구 효과도 없다 (DB 의 도구는 그대로)
        if "heldNow" in d:
            self.held = d["heldNow"]
        self.cond = dict(d.get("cond") or {})
        SM.reapply(self)                     # 변신·파워트릭처럼 능력치를 바꿔 둔 것

    def clear_volatile(self):
        """물러날 때 풀리는 것. 던진 도구는 돌아오지 않는다."""
        SM.restore(self)                     # 변신·특성 바꾸기·타입 바꾸기를 되돌린다
        self.seeded = False
        self.bide = None
        self.stockpile = 0
        self.hurt = None
        self.cond = {}

    def dex_move_name(self, key):
        return self._dex.move_name(key)

    def types(self):
        if self.types_override:
            out = list(self.types_override)
        else:
            out = list((self.species or {}).get("types") or [])
        extra = self.cond.get("extraType")               # 핼러윈·숲의저주
        if extra and extra not in out:
            out.append(extra)
        return out

    def stat(self, key, crit=False, stages=True):
        fld = self.field
        raw = key
        if fld is not None and fld.room("wonderroom") and key in ("def", "spd"):
            raw = "spd" if key == "def" else "def"      # 원더룸: 방어와 특수방어가 뒤바뀐다
        v = self.base.get(raw, 1)
        s = self.stages.get(key, 0) if stages else 0
        if crit and s < 0:                  # 급소는 상대의 방어 상승/내 공격 하락을 무시
            s = 0
        v = int(v * stage_mult(s))
        if key == "spe" and self.status == "paralysis":
            if not (self.ability_on and A.ignores_para_speed(self)):
                v = int(v * 0.5)
        if self.held:
            v = int(v * H.stat_mult(self, key))
        if self.ability_on:
            v = int(v * A.stat_mult(self, key))
        if fld is not None and fld.weather:
            w = SM.weather(self)
            if w == "sand" and key == "spd" and "ROCK" in self.types():
                v = int(v * 1.5)                 # 모래바람: 바위 타입 특수방어
            elif w == "snow" and key == "def" and "ICE" in self.types():
                v = int(v * 1.5)                 # 설경: 얼음 타입 방어
        return max(1, v)

    def held_state(self):
        return H.state(self)

    def load_held(self, d):
        H.load(self, d)

    def snapshot(self):
        return {"hp": self.hp, "maxhp": self.maxhp, "status": self.status,
                "pp": dict(self.pp), "stages": dict(self.stages),
                "held": self.held, "heldState": self.held_state()}


# ---------------------------------------------------------------- 계산
def effectiveness(dex, move_type, defender_types):
    t = dex.types.get(move_type) or {}
    eff = t.get("eff") or {}
    mult = 1.0
    for d in defender_types:
        mult *= eff.get(d, 1.0)
    return mult


def accuracy_check(dex, move, user, target, rng):
    acc = SM.accuracy(move, user, target)   # 날씨로 바뀌는 명중률 (번개·폭풍·눈보라)
    if acc <= 0:                            # 0 = 반드시 맞는 기술
        return True
    abil = user.ability_on or target.ability_on
    if abil and A.always_hit(user, target):
        return True
    if SM.sure_hit(user, target):           # 록온·마음의눈·텔레키네시스
        return True
    eva = target.stages["eva"]
    if abil and A.ignore_evasion(user):
        eva = min(0, eva) if A.has(user, "KEENEYE", "MINDSEYE", "ILLUMINATE") else 0
    if target.cond.get("identified"):
        eva = min(0, eva)                   # 냄새구별: 회피율 상승을 무시한다
    rate = acc * stage_mult(user.stages["acc"], "acc") \
        / stage_mult(eva, "acc")
    if user.field is not None and user.field.room("gravity"):
        rate *= 5.0 / 3.0                   # 중력
    if user.held or target.held:
        rate *= H.acc_mult(user, target)
    if abil:
        rate *= A.acc_mult(user, target, move)
    return rng.uniform(0, 100) < rate


def damage(dex, move, user, target, rng, crit=None):
    """(데미지, 급소여부, 상성배율) 을 돌려준다.

    위력이 원작 공식으로 정해지는 기술(안다리걸기·바둥바둥 ...)은 movecalc 가
    위력을 정하고, 고정 데미지 기술(나이트헤드·분노의앞니·일격기·카운터 ...)은
    타입 무효만 보고 그 값을 그대로 준다 - 급소·자속·상성 배율이 없다.
    """
    move = SM.resolve(MC.resolve(move, user, target), user, target)   # 날씨구슬·자연의힘 ...
    abil = user.ability_on or target.ability_on
    fixed = MC.fixed(move, user, target, rng)
    if fixed is not None:
        mtype = A.move_type(user, move) if abil else move.get("type")
        eff = type_eff(dex, move, mtype, user, target, abil)
        if eff == 0:
            return 0, False, 0.0
        return max(0, int(fixed)), False, eff
    power = move.get("power") or 0
    if power <= 0:
        return 0, False, 1.0
    phys = move.get("cat") == "physical"
    mtype = A.move_type(user, move) if abil else move.get("type")
    if crit is None:
        chance = CRIT_CHANCE
        # 급소율이 높은 기술 + 초점렌즈 같은 도구. 도구가 없으면 예전 식과
        # 같은 값이다.
        stages = (move.get("crit") or 0) + (H.crit_stages(user) if user.held else 0)
        if abil:
            stages += A.crit_bonus(user)
        if user.cond.get("focus"):
            stages += 2                         # 기충전
        if stages:
            chance = max(2, CRIT_CHANCE // (2 ** min(3, stages)))
        crit = rng.randrange(chance) == 0
        if user.cond.get("laserfocus"):
            crit = True                         # 예민해지기
        if abil:
            if A.crit_forced(user, target):
                crit = True
            if A.crit_blocked(user, target):
                crit = False

    if abil:
        a = user.stat("atk" if phys else "spa", crit,
                      stages=not A.unaware_attack(user, target))
        d = target.stat("def" if phys else "spd", crit,
                        stages=not A.unaware_defense(user))
        power = int(power * A.type_power_mult(user, move))
    else:
        a = user.stat("atk" if phys else "spa", crit)
        d = target.stat("def" if phys else "spd", crit)
    base = math.floor(math.floor(math.floor(2 * user.level / 5 + 2) * power * a / d)
                      / 50) + 2

    mult = 1.0
    if abil:
        if mtype in user.types():
            mult *= A.stab(user)
    else:
        if user.types() and mtype in user.types():
            mult *= STAB
    eff = type_eff(dex, move, mtype, user, target, abil)
    mult *= eff
    mult *= SM.field_mult(move, mtype, user, target, crit)     # 날씨·필드·리플렉터·흙놀이
    if crit:
        mult *= CRIT_MULT
        if abil:
            mult *= A.crit_mult(user)
    mult *= rng.uniform(0.85, 1.0)
    if user.status == "burn" and phys and not (abil and A.ignores_burn(user)) \
            and MC.key(move) != "FACADE":          # 객기는 화상이어도 반감되지 않는다
        mult *= 0.5
    if user.held:
        mult *= H.damage_mult(user, move, eff)
    if abil:
        mult *= A.attack_mult(user, target, move, mtype, eff)
        mult *= A.defense_mult(user, target, move, mtype, eff)

    dmg = int(base * mult)
    if eff > 0:
        dmg = max(1, dmg)
    return dmg, crit, eff


def type_eff(dex, move, mtype, user, target, abil):
    """상성 배율. 배짱·냄새구별(고스트), 중력·뿌리박기(비행에게 땅), 전자부유(땅 무효), 타르샷."""
    ttypes = target.types()
    if "GHOST" in ttypes and mtype in ("NORMAL", "FIGHTING") and \
            ((abil and A.ghost_bypass(user, mtype)) or target.cond.get("identified")):
        ttypes = [t for t in ttypes if t != "GHOST"]
    if mtype == "GROUND":
        if "FLYING" in ttypes and SM.forced_grounded(target):
            ttypes = [t for t in ttypes if t != "FLYING"]
        elif not SM.forced_grounded(target) and (target.cond.get("magnetrise") or target.cond.get("telekinesis")):
            return 0.0
    eff = effectiveness(dex, mtype, ttypes)
    if mtype == "FIRE" and target.cond.get("tarshot") and eff:
        eff *= 2.0
    if MC.key(move) == "FREEZEDRY" and "WATER" in ttypes:
        eff *= 4.0                               # 프리즈드라이: 물에게 굉장 (얼음->물 0.5 를 2 로)
    return eff


def exp_gain(dex, foe, winner_level, participants=1, shared=False):
    """본가 5세대 공식. shared 면 학습장치 몫(절반)."""
    sp = dex.get(foe.mon["species"])
    base = (sp or {}).get("baseExp", 60) or 60
    lf = foe.level
    n = max(1, participants)
    raw = (base * lf / 5.0) / n * \
        ((2.0 * lf + 10) / (lf + winner_level + 10)) ** 2.5 + 1
    if shared:
        raw *= 0.5
    return max(1, int(raw))


# ---------------------------------------------------------------- 배틀
class Battle(object):
    """야생 1:1 전투 한 판."""

    def __init__(self, dex, mine, foe, rng=None, ai="wild", field=None):
        self.dex = dex
        self.rng = rng or random.Random()
        # 날씨·필드·진영 (common/field.py). 관장·유저 배틀은 판 내내 같은 것을 준다.
        self.field = field if field is not None else FD.Field()
        # 어떤 배틀인가: wild (야생 1:1) / gym (관장) / pvp (유저 배틀). 교체가 되는지가 다르다.
        self.kind = "wild"
        self.me = mine
        self.foe = foe
        self.turn_no = 0
        self.over = False
        self.result = None                  # won / lost / fled / caught
        # 야생 포켓몬은 본가에서도 기술을 거의 무작위로 쓴다.
        # 머리를 쓰는 쪽은 트레이너/체육관 관장이다.
        self.ai = ai
        # 이 둘은 야생 배틀 기준값이다. 파티전(PartyBattle)은 한 판이
        # 여러 라운드로 나뉘므로 상한을 라운드마다 다시 주고, 상대가
        # 야생이 아니므로 이름 앞에 '야생' 을 붙이지 않는다.
        # 저장해 두는 로그라 여기서 틀리면 나중에 다시 봐도 계속 틀린다.
        self.max_turns = MAX_TURNS
        self.foe_prefix = "야생 "

    # ---------------- 서 있는 둘 ----------------
    @property
    def me(self):
        return self._me

    @me.setter
    def me(self, f):
        self._me = f
        self._attach(f, "me")

    @property
    def foe(self):
        return self._foe

    @foe.setter
    def foe(self, f):
        self._foe = f
        self._attach(f, "foe")

    def _attach(self, f, who):
        if f is not None:
            f.field = self.field
            f.side_name = who
        self._suppress_weather()

    def _suppress_weather(self):
        """날씨부정·에어록이 서 있으면 날씨 효과가 없다."""
        fl = self.field
        on = [getattr(self, "_me", None), getattr(self, "_foe", None)]
        fl.suppressed = any(f is not None and f.alive() and A.has(f, "CLOUDNINE", "AIRLOCK") for f in on)

    def fighter(self, who):
        return self.me if who == "me" else self.foe

    def weather(self):
        return None if getattr(self.field, "suppressed", False) else self.field.weather

    def grounded(self, f):
        return SM.grounded(f)

    def speed(self, who):
        """순서를 정할 때 쓰는 스피드. 순풍은 두 배."""
        f = self.fighter(who)
        v = f.stat("spe")
        if self.field.side(who).get("tailwind"):
            v *= 2
        return v

    # ---------------- 도구 ----------------
    def move_of(self, key):
        if key == STRUGGLE:
            return STRUGGLE_MOVE
        return self.dex.move(key) or {}

    def move_name(self, key):
        if key == STRUGGLE:
            return STRUGGLE_MOVE["kr"]
        return self.dex.move_name(key)

    def usable(self, f):
        """쓸 수 있는 기술. 하나도 없으면 몸부림.

        도발·사슬묶기·트집·앙코르·봉인·회복봉인·중력으로 못 쓰는 기술은 뺀다.
        """
        out = [m for m in f.moves if f.pp.get(m, 0) > 0 and not SM.restricted(self, f, m)]
        return out or [STRUGGLE]

    def choose_ai(self):
        """상대(야생)가 쓸 기술."""
        return self.choose_for(self.foe, self.me, self.ai)

    def choose_mine(self, ai="trainer"):
        """내 포켓몬이 알아서 고르는 기술.

        자동 전투에서 쓴다. 내 쪽은 머리를 쓰는 편이 보기 좋으니 기본이
        'trainer' 다. 야생은 무작위(wild)로 둔다.
        """
        return self.choose_for(self.me, self.foe, ai)

    def choose_for(self, user, target, ai):
        """기술 선택.

        trainer 는 '제일 아픈 기술'을 고른다. 변화기는 효과가 남아 있을 때만,
        그것도 공격보다 낮은 점수로 친다. 안 그러면 이미 잠든 상대에게
        최면술을 계속 걸면서 배틀이 끝나지 않는다.
        """
        pool = self.usable(user)
        if not pool:
            return STRUGGLE
        if user.held:
            pool = H.lock_pool(user, pool)      # 구애 도구는 처음 쓴 기술만

        if ai == "wild":
            # 위력이 있는 기술 쪽으로 살짝만 기울인 무작위
            weights = []
            for m in pool:
                md = self.move_of(m)
                if MC.attacks(md):
                    weights.append(2.0)
                elif self._status_score(md, 1, user, target) > 0:
                    weights.append(1.0)
                else:
                    weights.append(0.2)     # 효과 없는 변화기는 거의 안 쓴다
            total = sum(weights)
            pick = self.rng.uniform(0, total)
            acc = 0.0
            for m, w in zip(pool, weights):
                acc += w
                if pick <= acc:
                    return m
            return pool[-1]

        scored = []
        best_dmg = 0
        for m in pool:
            md = self.move_of(m)
            mk = MC.key(md)
            acc = (md.get("acc") or 100) / 100.0
            if mk in MC.OHKO:
                acc = MC.ohko_accuracy(md, user, target) / 100.0
            if user.ability_on and A.would_block(user, target, md):
                # 상대 특성에 빨려 들어가는 기술 (저수에 물 기술, 부유에 땅 기술)
                scored.append([m, 0.01, md])
                continue
            if MC.attacks(md):
                d, _c, _e = damage(self.dex, md, user, target,
                                   EST_RNG, crit=False)
                # 연속기는 한 번 때리는 게 아니다. 씨앗기관총(위력 25)이
                # 위력 25 짜리로 평가되어 늘 뒷전으로 밀렸다.
                hits = md.get("hits") or [1, 1]
                lo, hi = (hits + [1, 1])[:2]
                if mk == "BEATUP" or mk in MC.FIXED:
                    lo = hi = 1                 # 한 대 몫이 아니라 통째로 센다
                if hi > 1:
                    d *= HITS_AVG if (lo, hi) == (2, 5) else (lo + hi) / 2.0
                score = d * acc
                # 반동기(drain 이 음수)는 그만큼 내 체력을 깎는다.
                # 체력이 얼마 안 남았는데 이판사판으로 쓰면 자멸한다.
                back = md.get("drain") or 0
                if back < 0:
                    hurt = d * (abs(back) / 100.0)
                    if hurt >= user.hp:     # 이 기술로 내가 먼저 쓰러진다
                        score *= 0.25
                    else:
                        score -= hurt * 0.5
                # **끝낼 수 있는지는 배수를 곱하기 전 값으로 본다.**
                # best_dmg 에 3배가 섞이면 아래 변화기 기준선이 부풀어서
                # 변화기를 실제보다 덜 쓰게 된다.
                best_dmg = max(best_dmg, score)
                if d >= target.hp and mk not in MC.OHKO:   # 이걸로 끝낼 수 있으면 최우선 (일격기는 명중률이 곧 값이다)
                    score *= 3
            else:
                score = -1                  # 변화기는 아래에서 다시 매긴다
            scored.append([m, score, md])

        for row in scored:
            m, score, md = row
            if score >= 0:
                continue
            row[1] = self._status_score(md, best_dmg, user, target)

        pool2 = [(m, s) for m, s, _md in scored if s > 0]
        if not pool2:
            pool2 = [(m, max(0.1, s)) for m, s, _md in scored]
        if self.rng.random() < 0.15:        # 완벽하지 않게
            return self.rng.choice([m for m, _s in pool2])
        return max(pool2, key=lambda x: x[1])[0]

    def spare_plan(self, user, target):
        """잡기 모드. 상대를 쓰러뜨리지 않고 잡기 좋게 만든다.

        (쓸 기술, 멈출 이유) 를 돌려준다. 둘 중 하나만 채워진다.

            1. 상대가 상태이상이 아니면 잠재우기·마비 기술부터
            2. 체력이 SPARE_LOW 이하면 멈춘다            -> "low"
            3. **급소에 최대 난수로 맞아도** 안 쓰러지는 기술 중 가장 많이
               깎는 것. 없으면, 체력이 40% 넘게 남았을 때만 급소가 아니면
               안 쓰러지는 기술. 그것도 없거나 너무 약하면 멈춘다 -> "nosafe"

        몸부림만 남았으면 멈춘다. 몸부림은 상대를 쓰러뜨릴 수 있다.
        choose_for 와 따로 둔다 - 야생 무작위·PvP·관장 AI 는 그대로다.
        """
        pool = self.usable(user)
        if user.held:
            pool = H.lock_pool(user, pool)
        if pool == [STRUGGLE]:
            return None, "nosafe"
        if not target.status:
            types = target.types() if target.ability_on else ((target.species or {}).get("types") or [])
            for ail in SPARE_STATUS:
                cands = []
                for m in pool:
                    md = self.move_of(m)
                    if MC.attacks(md) or md.get("ail") != ail:
                        continue
                    if ail == "paralysis" and "ELECTRIC" in types:
                        continue
                    if target.ability_on and (A.would_block(user, target, md)
                                              or A.status_blocked(target, ail, user)):
                        continue
                    cands.append(((md.get("acc") or 100), m))
                if cands:
                    return max(cands)[1], None
        if target.hp <= target.maxhp * SPARE_LOW:
            return None, "low"
        best_m = self._spare_hit(pool, user, target, crit=True)
        if best_m is None and target.hp > target.maxhp * SPARE_RISK_ABOVE:
            # 급소까지 막으면 절반쯤에서 멈춰 버린다 (400판 중 185판). 체력이 넉넉하면
            # **급소가 아니면 안 쓰러지는** 기술까지 쓴다. 급소는 1/24 이다.
            best_m = self._spare_hit(pool, user, target, crit=False)
        if best_m is None:
            return None, "nosafe"
        return best_m, None

    def _spare_hit(self, pool, user, target, crit):
        """쓰러뜨리지 않는 공격 기술 중 가장 많이 깎는 것. 없거나 너무 약하면 None."""
        best, best_m = 0.0, None
        for m in pool:
            md = self.move_of(m)
            if not MC.attacks(md):
                continue
            mk = MC.key(md)
            if mk in MC.COUNTERS or mk in MC.PER_USE or mk in ("BIDE", "FINALGAMBIT"):
                # 고를 때는 얼마나 들어갈지 모른다 (맞은 만큼·무작위·파티 수). 잡을 때는 안 쓴다.
                continue
            if user.ability_on and A.would_block(user, target, md):
                continue
            if not crit and md.get("crit"):
                continue                        # 급소율이 높은 기술은 급소를 무시할 수 없다
            worst, _c, _e = damage(self.dex, md, user, target, MAX_RNG, crit=crit)
            lo, hi = ((md.get("hits") or [1, 1]) + [1, 1])[:2]
            worst *= max(1, hi)
            # 화상·독·씨뿌리기가 걸려 있거나 걸 수 있으면 턴 끝에 깎이는 몫까지 친다
            if target.status in ("burn", "poison") or md.get("ail") in ("burn", "poison"):
                worst += target.maxhp // 8
            if target.seeded:
                worst += target.maxhp // 8
            if worst >= target.hp:
                continue
            d, _c, _e = damage(self.dex, md, user, target, EST_RNG, crit=False)
            d *= (lo + hi) / 2.0 if hi > 1 else 1
            d *= (md.get("acc") or 100) / 100.0
            if d > best:
                best, best_m = d, m
        if best_m is None or best < target.maxhp * SPARE_MIN_HIT:
            return None
        return best_m

    def _status_score(self, md, best_dmg, user=None, target=None):
        """변화기가 지금 쓸 만한지. 효과가 이미 걸려 있으면 0."""
        user = user or self.foe
        target = target or self.me
        useful = False
        mk = MC.key(md)
        who = "me" if user is self.me else "foe"
        v = SM.value(self, mk, md, user, target, who, max(1.0, best_dmg))
        if v is not None:
            return v * ((md.get("acc") or 100) / 100.0)
        if mk == "SWALLOW" and (not user.stockpile or user.hp >= user.maxhp):
            return 0.0                      # 비축한 게 없거나 체력이 가득하면 실패한다
        if mk == "STOCKPILE" and user.stockpile >= 3:
            return 0.0
        if md.get("ail") == "leech-seed":
            types = target.types() if target.ability_on else ((target.species or {}).get("types") or [])
            if target.seeded or "GRASS" in types:
                return 0.0
            useful = True
        ail = md.get("ail")
        if ail in HANDLED_STATUS:
            if target.status:               # 이미 상태이상이면 소용없다
                return 0.0
            useful = True
        # **누구한테 걸리는지는 도감이 정한다.** 예전에는 "올려주는
        # 기술이면 자기 자신" 으로 짐작했는데, 그러면 재주넘기(SWAGGER)
        # 처럼 **상대의** 공격을 올려 주는 기술을 "내 공격이 오른다" 로
        # 잘못 세어 스스로 지는 수를 뒀다. 실행부(_use)는 이미 statSelf 를
        # 본다 - 점수부만 어긋나 있었다.
        self_target = bool(md.get("statSelf"))
        for stat, change in (md.get("stat") or []):
            who = user if self_target else target
            # 상대를 깎는 것도, 나를 올리는 것도 이득이다.
            # 나를 깎거나 상대를 올리는 것은 손해라 세지 않는다.
            good = (change > 0) if self_target else (change < 0)
            if not good:
                continue
            cur = who.stages.get(stat, 0)
            if (change > 0 and cur < STAGE_MAX) or (change < 0 and cur > STAGE_MIN):
                useful = True
        if md.get("heal") and user.hp < user.maxhp:
            useful = True
        if not useful:
            return 0.0
        # 때릴 수 있으면 때리는 쪽이 우선. 변화기는 그 절반 정도 값어치.
        score = max(1.0, best_dmg * 0.45) * ((md.get("acc") or 100) / 100.0)

        # **판이 얼마나 남았는지**를 본다. 변화기는 뒤가 길어야 값을 한다.
        # 예전에는 이걸 안 봐서, 상대 체력이 한 대 남았는데 랭크를 올리다가
        # 역전당하거나, 내가 죽기 직전에 최면술을 걸었다.
        if target.maxhp:
            left = target.hp / float(target.maxhp)
            # 상대가 얼마 안 남았으면 때려서 끝내는 게 낫다
            score *= 0.25 + 0.75 * min(1.0, left * 1.4)
        if user.maxhp:
            mine = user.hp / float(user.maxhp)
            # 내가 위태로우면 랭크를 올릴 때가 아니다. 회복기는 반대로 급하다.
            if not md.get("heal"):
                score *= 0.3 + 0.7 * min(1.0, mine * 1.6)
        return score

    # ---------------- 한 턴 ----------------
    def take_turn(self, my_move):
        """내 기술을 정해서 한 턴을 진행한다. 일어난 일 목록을 돌려준다."""
        if self.over:
            return [{"t": "over", "result": self.result}]
        self.turn_no += 1
        ev = []
        self.begin_turn()
        foe_move = self.choose_ai()

        if my_move != STRUGGLE and (my_move not in self.me.pp
                                    or self.me.pp.get(my_move, 0) <= 0):
            my_move = self.usable(self.me)[0]
        if self.me.held:
            # 사람이 고른 기술도 구애 잠금을 받는다 (야생 배틀은 사람이 고른다).
            my_move = H.force_move(self.me, my_move, ev, "me")

        order = self._order(my_move, foe_move, ev)
        self.me.flinched = False
        self.foe.flinched = False
        self.me.moved_second = order[0] != "me"
        self.foe.moved_second = order[0] != "foe"

        acting = {"me": self.me, "foe": self.foe}
        for who in order:
            if self.over:
                break
            user, target = (self.me, self.foe) if who == "me" else (self.foe, self.me)
            key = my_move if who == "me" else foe_move
            if user is not acting[who]:
                continue                 # 이번 턴에 끌려 나온 포켓몬은 움직이지 않는다
            if not user.alive() or not target.alive():
                continue
            self._use(who, user, target, key, ev)

        if not self.over:
            self._end_of_turn(ev)
        if not self.over and self.turn_no >= self.max_turns:
            # 서로 결정타가 없어 끝나지 않는 상황. 야생이 흥미를 잃고 떠난다.
            self.over = True
            self.result = "fled"
            ev.append({"t": "flee", "who": "foe",
                       "text": "%s%s 은(는) 흥미를 잃고 떠나버렸다."
                               % (self.foe_prefix, self.foe.name)})
        return ev

    def _order(self, my_move, foe_move, ev=None):
        mp = SM.priority(self, self.me, self.move_of(my_move)) if my_move else 0
        fp = SM.priority(self, self.foe, self.move_of(foe_move)) if foe_move else 0
        if self.me.ability_on and my_move:
            mp += A.priority_bonus(self.me, self.move_of(my_move))
        if self.foe.ability_on and foe_move:
            fp += A.priority_bonus(self.foe, self.move_of(foe_move))
        if mp != fp:
            return ["me", "foe"] if mp > fp else ["foe", "me"]
        # 같은 우선도 안에서 도구가 순서를 당기거나 미룬다 (선제공격손톱,
        # 느림보꼬리, 애슈열매). 도구가 없으면 난수를 안 건드린다.
        if self.me.held or self.foe.held:
            ev = ev if ev is not None else []
            bm = H.order_bias(self, self.me, "me", ev)
            bf = H.order_bias(self, self.foe, "foe", ev)
            if bm != bf:
                return ["me", "foe"] if bm > bf else ["foe", "me"]
        ms, fs = self.speed("me"), self.speed("foe")
        if ms != fs:
            faster_me = ms > fs
            if self.field.room("trickroom"):
                faster_me = not faster_me        # 트릭룸: 느린 쪽이 먼저
            return ["me", "foe"] if faster_me else ["foe", "me"]
        return ["me", "foe"] if self.rng.random() < 0.5 else ["foe", "me"]

    # ---------------- 기술 사용 ----------------
    def team_of(self, who):
        """집단폭행이 세는 같은 편. 관장·유저 배틀은 teams 를 채워 준다."""
        teams = getattr(self, "teams", None) or {}
        return teams.get(who) or [self.me if who == "me" else self.foe]

    def _fail(self, who, ev, text="하지만 실패했다!"):
        ev.append({"t": "msg", "who": who, "text": text})

    # ---------------- 변화기가 끼어드는 곳 ----------------
    def _intercepted(self, k, key, move, who, user, target, tw, ev):
        """가로채기·방어·패스트가드·트릭가드·매직코트·사이코필드·대타출동에 막혔으면 True."""
        fl = SM.flags(move)
        opp = target
        # 가로채기: 상대가 먼저 가로채기를 썼으면 자기에게 거는 기술을 빼앗긴다
        if "snatch" in fl and opp.cond.get("snatch") and opp.alive():
            opp.cond.pop("snatch", None)
            ev.append({"t": "msg", "who": tw, "text": "%s 이(가) %s 의 기술을 가로챘다!" % (opp.name, user.name)})
            self._use(tw, opp, user, key, ev, called=True, bounced=True)
            return True
        if not A.aims_at_foe(move) or target is user:
            return False
        side = self.field.side(tw)
        pri = SM.priority(self, user, move)
        # 방어 계열 (페인트는 뚫는다)
        guard = target.cond.get("protect")
        if guard and "protect" in fl and k not in ("FEINT", "HYPERSPACEFURY", "HYPERSPACEHOLE"):
            if guard in ("KINGSSHIELD", "OBSTRUCT", "SILKTRAP") and not MC.attacks(move):
                pass                                      # 킹실드·블로킹·스레드트랩은 변화기를 못 막는다
            else:
                ev.append({"t": "msg", "who": tw, "text": "%s 은(는) 공격으로부터 몸을 지켰다!" % target.name})
                if A.is_contact(move) and user.alive():
                    if guard == "SPIKYSHIELD" and not A.has(user, "MAGICGUARD"):
                        SM._chip(user, who, user.maxhp / 8.0, ev, "%s 은(는) 니들가드에 찔렸다!" % user.name)
                    elif guard == "KINGSSHIELD":
                        self._change_stat(user, "atk", -1, ev, who, source=target)
                    elif guard == "OBSTRUCT":
                        self._change_stat(user, "def", -2, ev, who, source=target)
                    elif guard == "SILKTRAP":
                        self._change_stat(user, "spe", -1, ev, who, source=target)
                    elif guard == "BANEFULBUNKER":
                        self._apply_status(user, "poison", ev, source=target)
                    elif guard == "BURNINGBULWARK":
                        self._apply_status(user, "burn", ev, source=target)
                self._check_faint(ev)
                return True
        if k == "FEINT" and guard:
            target.cond.pop("protect", None)
            ev.append({"t": "msg", "who": tw, "text": "%s 의 방어가 풀렸다!" % target.name})
        if side.get("quickguard") and pri > 0 and "protect" in fl:
            ev.append({"t": "msg", "who": tw, "text": "패스트가드가 %s 을(를) 지켰다!" % target.name})
            return True
        if side.get("wideguard") and move.get("target") in (9, 11) and MC.attacks(move):
            ev.append({"t": "msg", "who": tw, "text": "와이드가드가 %s 을(를) 지켰다!" % target.name})
            return True
        if side.get("craftyshield") and not MC.attacks(move):
            ev.append({"t": "msg", "who": tw, "text": "트릭가드가 %s 을(를) 지켰다!" % target.name})
            return True
        # 사이코필드: 땅에 붙은 상대에게 선공기가 안 통한다
        if pri > 0 and SM.terrain(target) == "psychic" and SM.grounded(target):
            ev.append({"t": "msg", "who": tw, "text": "%s 은(는) 사이코필드에 보호받고 있다!" % target.name})
            return True
        # 매직코트·매직미러: 되돌릴 수 있는 변화기를 튕긴다
        if "reflectable" in fl and (target.cond.get("magiccoat")
                                    or (A.has(target, "MAGICBOUNCE") and not A.breaks(user))):
            ev.append({"t": "msg", "who": tw, "text": "%s 은(는) %s 을(를) 튕겨 냈다!"
                       % (target.name, self.move_name(key))})
            self._use(tw, target, user, key, ev, called=True, bounced=True)
            return True
        # 대타출동: 변화기는 대타에게 막힌다 (소리·authentic 은 뚫는다)
        if not MC.attacks(move) and SM.sub_blocks(user, target, move):
            ev.append({"t": "msg", "who": who, "text": "하지만 실패했다!"})
            return True
        return False

    def estimate(self, attacker, defender, key):
        """급소·난수 없이, 명중률까지 곱한 기대 데미지 (AI 가 쓴다)."""
        md = self.move_of(key)
        if not MC.attacks(md) or (attacker.ability_on and A.would_block(attacker, defender, md)):
            return 0.0
        d, _c, _e = damage(self.dex, md, attacker, defender, EST_RNG, crit=False)
        lo, hi = ((md.get("hits") or [1, 1]) + [1, 1])[:2]
        if hi > 1 and MC.key(md) != "BEATUP" and MC.key(md) not in MC.FIXED:
            d *= HITS_AVG if (lo, hi) == (2, 5) else (lo + hi) / 2.0
        return d * ((md.get("acc") or 100) / 100.0)

    def best_damage(self, attacker, defender):
        if attacker is None or defender is None or not attacker.alive():
            return 0.0
        return max([self.estimate(attacker, defender, m) for m in self.usable(attacker)] or [0.0])

    def request_switch(self, who, mode, ev, key, state=None):
        """교체 기술. drag = 끌어낸다, out = 스스로 물러난다, pass = 배턴터치, shed = 꼬리자르기.

        관장·유저 배틀은 switcher 를 붙여 실제로 바꾼다. 야생은 파티가 없어서
        울부짖기·순간이동이 판을 끝낸다 (원작과 같다). 해냈으면 True.
        """
        hook = getattr(self, "switcher", None)
        if hook is not None:
            return hook(who, mode, ev, key, state)
        if mode in ("drag", "out"):
            f = self.fighter(who)
            self.over = True
            self.result = "fled"
            if mode == "drag":
                text = "%s%s 은(는) 날려가 버렸다!" % (self.foe_prefix if who == "foe" else "", f.name)
            elif who == "me":
                text = "%s 은(는) 순간이동으로 도망쳤다!" % f.name
            else:
                text = "%s%s 은(는) 순간이동으로 사라졌다!" % (self.foe_prefix, f.name)
            ev.append({"t": "flee", "who": who, "text": text})
            return True
        return False

    def enter(self, who, ev):
        """새로 나온 포켓몬: 압정·스텔스록·치유소원. (날씨를 부르는 특성은 등장 특성과 같이 돈다)"""
        SM.enter(self, who, ev)
        self._suppress_weather()

    def _use(self, who, user, target, key, ev, called=False, instructed=False, bounced=False):
        """기술 하나를 쓴다.

        called     다른 기술이 불렀다 (손가락흔들기·잠꼬대·따라하기 ...). 못 움직이는지·PP 를 안 본다.
        instructed 지휘로 한 번 더 쓴다 (PP 는 쓴다).
        bounced    매직코트로 튕겨 나왔다. 기술 이름을 다시 띄우지 않는다.
        """
        if key is None:
            key = STRUGGLE
        if user.bide and key != STRUGGLE and not called:
            key = "BIDE"                     # 참는 동안은 다른 기술을 못 쓴다
        enc = user.cond.get("encore")
        if enc and not called and key != STRUGGLE and user.pp.get(enc.get("move"), 0) > 0:
            key = enc["move"]                # 앙코르
        move = self.move_of(key)

        if not called and not instructed:
            if not self._can_move(who, user, ev, key):
                return
            why = SM.restricted(self, user, key)
            if why:
                ev.append({"t": "msg", "who": who, "text": why})
                return

        abil = user.ability_on or target.ability_on
        tw = "foe" if who == "me" else "me"
        k = MC.key(move) if key != STRUGGLE else STRUGGLE
        charging = k == "BIDE" and bool(user.bide)
        if not called:
            if k not in SM.STREAK_MOVES:
                user.cond.pop("streak", None)     # 방어는 연달아 쓸수록 실패하기 쉽다
            if k != "DESTINYBOND":
                user.cond.pop("destinybond", None)
                user.cond.pop("dbondUsed", None)
            if k != "GRUDGE":
                user.cond.pop("grudge", None)
        if key != STRUGGLE and not charging and (not called or instructed):
            cost = A.pp_cost(user, target) if abil else 1
            user.pp[key] = max(0, user.pp.get(key, 0) - cost)
            if user.held:
                H.restore_pp(user, key, move.get("pp"), who, ev)   # 과사열매
        if not charging and not bounced:
            ev.append({"t": "move", "who": who, "name": user.name,
                       "move": self.move_name(key), "moveType": MC.move_type(move, user),
                       "cat": move.get("cat"),
                       "text": "%s 의 %s!" % (user.name, self.move_name(key))})
        if key != STRUGGLE and not bounced:
            user.cond["lastMove"] = key
            self.last_before = self.field.last_move      # 흉내쟁이는 자기 직전의 기술을 본다
            self.field.last_move = key
        if abil and key != STRUGGLE and not charging and not bounced:
            A.before_move(self, user, who, move, ev)
            if A.blocks(self, user, who, target, tw, move, key, ev):
                return
        if user.cond.get("electrify") and MC.attacks(move):
            move = dict(move, type="ELECTRIC")    # 송전

        # ---- 가로채기·방어·매직코트·사이코필드·대타출동 ----
        if not bounced and self._intercepted(k, key, move, who, user, target, tw, ev):
            return

        # ---- 원작 공식 기술: 쓰기 전에 정해지거나 실패하는 것 ----
        move = self._before_special(k, move, who, user, target, tw, ev)
        if move is None:
            return
        if MC.attacks(move) and not SM.before_attack(self, k, move, who, user, target, tw, ev):
            return

        if k in MC.OHKO:
            if (abil and A.always_hit(user, target)) or user.cond.get("lockon"):
                hit = True
            else:
                hit = self.rng.uniform(0, 100) < MC.ohko_accuracy(move, user, target)
        elif bounced or not A.aims_at_foe(move) and not MC.attacks(move):
            hit = True
        else:
            hit = accuracy_check(self.dex, move, user, target, self.rng)
        if not hit:
            ev.append({"t": "miss", "who": who, "text": "하지만 빗나갔다!"})
            return
        if k not in ("LOCKON", "MINDREADER"):
            user.cond.pop("lockon", None)             # 록온은 다음 기술 한 번에 쓰인다

        # ---- 변화기 (statusmoves) ----
        if not MC.attacks(move) and SM.run(self, k, move, who, user, target, tw, ev):
            self._check_faint(ev)
            return

        if k == "PRESENT" and self.rng.random() < 0.2:
            # 프레젠트는 20% 로 상대를 회복시킨다
            if target.hp >= target.maxhp:
                return self._fail(who, ev, "%s 은(는) 체력이 가득해서 받을 수 없다!" % target.name)
            amount = max(1, target.maxhp // 4)
            target.hp = min(target.maxhp, target.hp + amount)
            ev.append({"t": "heal", "who": tw, "amount": amount, "hp": target.hp,
                       "maxhp": target.maxhp, "text": "%s 의 체력이 회복되었다!" % target.name})
            return
        if k == "PRESENT":
            roll = self.rng.random()
            move = dict(move, _power=40 if roll < 0.5 else (80 if roll < 0.875 else 120))

        total = 0
        sub_hit = False
        fixed_move = k in MC.FIXED or move.get("_fixed") is not None
        if MC.attacks(move):
            lo, hi = (move.get("hits") or [1, 1])[:2]
            times = 1
            members = []
            if k == "BEATUP":
                members = [m for m in self.team_of(who) if m.alive() and not m.status] or [user]
                times = len(members)
            elif hi > 1:
                forced = A.hit_count(user, lo, hi) if abil else None
                if forced:
                    times = forced
                else:
                    times = self.rng.choice(MULTI_HIT) if (lo, hi) == (2, 5) \
                        else self.rng.randint(lo, hi)
            eff = 1.0
            for i in range(times):
                if not target.alive():
                    break
                hit_move = dict(move, _power=MC.beat_up_power(members[i])) if members else move
                dmg, crit, eff = damage(self.dex, hit_move, user, target, self.rng)
                if fixed_move and eff != 0 and dmg <= 0:
                    return self._fail(who, ev)       # 카운터로 돌려줄 것이 없다 ...
                if key == STRUGGLE and eff == 0:      # 몸부림은 무효가 없다
                    eff = 1.0
                    dmg = max(1, dmg or 1)
                if eff == 0:
                    ev.append({"t": "immune", "who": who,
                               "text": "%s 에게는 효과가 없는 것 같다..." % target.name})
                    return
                if abil and key != STRUGGLE and A.wonder_guard_blocks(user, target, eff, move):
                    A.pop(self, target, tw, ev)
                    ev.append({"t": "immune", "who": who,
                               "text": "%s 에게는 효과가 없는 것 같다..." % target.name})
                    return
                if SM.sub_blocks(user, target, hit_move):
                    # 대타출동이 대신 맞는다. 맞는 쪽 특성·도구·부가효과는 없다.
                    total += SM.hit_sub(self, user, who, target, tw, dmg, ev)
                    sub_hit = True
                    continue
                if target.held:
                    # 반감 열매, 기합의띠. 맞는 쪽 도구가 데미지를 고친다.
                    # 고정 데미지에는 상성이 없어서 반감 열매가 안 먹힌다.
                    dmg = H.on_incoming(self, target, "foe" if who == "me" else "me",
                                        move, 1.0 if fixed_move else eff, dmg, ev)
                if abil:
                    dmg = A.survive(self, user, who, target, tw, move, dmg, ev)
                if target.cond.get("endure") and dmg >= target.hp and target.hp > 0:
                    dmg = target.hp - 1
                    ev.append({"t": "msg", "who": tw, "text": "%s 은(는) 공격을 버텼다!" % target.name})
                hp_before = target.hp
                target.hp = max(0, target.hp - dmg)
                total += dmg
                self._note_hurt(target, move, hp_before - target.hp, who)
                ev.append({"t": "hit", "who": who, "target": "foe" if who == "me" else "me",
                           "damage": dmg, "crit": crit, "eff": 1.0 if fixed_move else eff,
                           "hp": target.hp, "maxhp": target.maxhp})
                if crit:
                    ev.append({"t": "msg", "text": "급소에 맞았다!"})
                if abil:
                    A.after_hit(self, user, who, target, tw, move, dmg, eff, crit, hp_before, ev)
                if hp_before > 0 and not target.alive():
                    if target.cond.get("destinybond") and user.alive():
                        user.hp = 0
                        ev.append({"t": "msg", "who": who,
                                   "text": "%s 은(는) %s 의 길동무가 되었다!" % (user.name, target.name)})
                    if target.cond.get("grudge") and key != STRUGGLE and user.pp.get(key):
                        user.pp[key] = 0
                        ev.append({"t": "msg", "who": who,
                                   "text": "%s 의 %s 은(는) 원념으로 PP 가 0 이 되었다!"
                                           % (user.name, self.move_name(key))})
                if not user.alive():
                    break
            if times > 1:
                ev.append({"t": "msg", "text": "%d번 맞았다!" % min(times, i + 1)})
            if k in MC.OHKO and total and not target.alive():
                ev.append({"t": "msg", "text": "일격필살!"})
            elif fixed_move:
                pass                                 # 고정 데미지에는 상성 문구가 없다
            elif eff > 1:
                ev.append({"t": "msg", "text": "효과가 굉장했다!"})
            elif 0 < eff < 1:
                ev.append({"t": "msg", "text": "효과가 별로인 듯하다..."})
            self._after_special(k, move, who, user, target, tw, total, ev)
            SM.after_attack(self, k, move, who, user, target, tw, total, sub_hit, ev)
            if user.held or target.held:
                # 생명의구슬 반동, 조개껍질방울, 자보·애터·의문열매, 그리고
                # 체력이 줄어 발동하는 열매들.
                H.after_hit(self, user, who, target, tw, move, eff, total, ev)
                H.check_hp(self, target, tw, ev)
                H.check_hp(self, user, who, ev)
            if abil:
                A.use_after_electric(user, A.move_type(user, move))
                if total and not target.alive():
                    A.after_ko(self, user, who, ev)

        # 흡수 / 반동
        drain = move.get("drain") or 0
        if drain > 0 and user.cond.get("healblock"):
            drain = 0                                  # 회복봉인: 흡수기로도 회복하지 못한다
        if drain and total:
            amount = max(1, int(total * abs(drain) / 100.0))
            if drain > 0 and user.held:
                amount = max(1, int(amount * H.drain_mult(user)))    # 큰뿌리
            if drain > 0:
                user.hp = min(user.maxhp, user.hp + amount)
                ev.append({"t": "heal", "who": who, "amount": amount, "hp": user.hp,
                           "maxhp": user.maxhp,
                           "text": "%s 은(는) 체력을 흡수했다!" % target.name})
            elif not (abil and key != STRUGGLE and A.no_recoil(user)):
                user.hp = max(0, user.hp - amount)
                ev.append({"t": "recoil", "who": who, "amount": amount, "hp": user.hp,
                           "maxhp": user.maxhp,
                           "text": "%s 은(는) 반동을 받았다!" % user.name})

        # 회복기 (달빛·아침햇살·광합성은 날씨로 회복량이 바뀐다)
        heal = SM.heal_percent(k, move, user)
        if k == "SWALLOW":
            if not user.stockpile or user.hp >= user.maxhp:
                return self._fail(who, ev)
            heal = {1: 25, 2: 50, 3: 100}[min(3, user.stockpile)]
            self._spend_stockpile(user, who, ev)
        if k == "STOCKPILE":
            if user.stockpile >= 3:
                return self._fail(who, ev)
            user.stockpile += 1
            ev.append({"t": "msg", "who": who, "text": "%s 은(는) %d개 비축했다!" % (user.name, user.stockpile)})
        if heal > 0 and user.hp < user.maxhp:
            amount = max(1, int(user.maxhp * heal / 100.0))
            user.hp = min(user.maxhp, user.hp + amount)
            ev.append({"t": "heal", "who": who, "amount": amount, "hp": user.hp,
                       "maxhp": user.maxhp,
                       "text": "%s 은(는) 체력을 회복했다!" % user.name})

        # 부가 효과에 걸리는 특성 (하늘의은총·우격다짐·인분)
        sec_mult, sec_off, sec_shield = 1.0, False, False
        if abil:
            sec_mult = A.secondary_mult(user)
            sec_off, sec_shield = A.secondary_off(user, target)

        # 능력 변화
        stats = move.get("stat") or []
        if stats:
            chance = move.get("statChance") or 0
            if chance and (sec_off or (sec_shield and not move.get("statSelf"))):
                chance = -1                         # 부가효과가 사라졌다
            if chance == 0 or (chance > 0 and self.rng.uniform(0, 100) < chance * sec_mult):
                # 누구에게 거는지는 도감을 만들 때 이미 판정해 두었다
                # (build_pokedex._stat_self). 여기서 짐작하면 안 된다 -
                # 예전에는 '올려주는 기술이면 자기 자신' 으로 짐작했는데,
                # 그러면 메탈클로처럼 때리면서 자기 공격이 오르는 기술이
                # 전부 상대를 강화해 버렸다.
                dst = user if move.get("statSelf") else target
                if dst is target and (sub_hit or (target is not user and target.cond.get("sub")
                                                   and MC.attacks(move))):
                    stats = []                         # 대타가 맞았다
                for stat, change in stats:
                    self._change_stat(dst, stat, SM.stat_boost(k, change, user), ev,
                                      "me" if dst is self.me else "foe", source=user)

        # 씨뿌리기
        if move.get("ail") == "leech-seed" and target.alive():
            self._seed(target, who, tw, ev)
        if not MC.attacks(move):
            SM.after_status(self, k, move, who, user, target, tw, ev)

        # 상태이상
        ail = move.get("ail")
        if sub_hit:
            ail = None
        if ail and ail not in HANDLED_STATUS and ail not in ("leech-seed", "protect") and target.alive():
            chance = move.get("ailChance") or 0
            if chance and (sec_off or sec_shield):
                chance = -1
            if chance == 0 or (chance > 0 and self.rng.uniform(0, 100) < chance * sec_mult):
                SM.apply_ail(self, ail, move, user, target, who, tw, ev)
        if ail in HANDLED_STATUS and target.alive():
            chance = move.get("ailChance") or 0
            if chance and (sec_off or sec_shield):
                chance = -1
            if chance == 0 or (chance > 0 and self.rng.uniform(0, 100) < chance * sec_mult):
                # 누가 걸었는지 늘 넘긴다 - 신비의부적은 특성이 꺼진 판(야생·예전 PvP)에서도 막는다
                self._apply_status(target, ail, ev, source=user)

        # 풀죽음
        fl = move.get("flinch") or 0
        if abil and (sec_off or sec_shield or A.flinch_immune(user, target)):
            fl = 0
        elif abil:
            fl *= sec_mult
            if A.stench(user, move):
                fl = 10
        if fl and target.alive() and not sub_hit and self.rng.uniform(0, 100) < fl:
            target.flinched = True
        if user.held:
            H.flinch(self, user, target, move)          # 왕의징표석·예리한이빨
            H.note_move(user, key)                      # 구애 잠금·메트로놈

        self._check_faint(ev)

    # ---------------- 원작 공식 기술 ----------------
    def _before_special(self, k, move, who, user, target, tw, ev):
        """맞히기 전에 정해지는 것. 실패하면 None, 아니면 (고친) 기술."""
        if k == "BIDE":
            if not user.bide:
                user.bide = {"left": 2, "sum": 0}
                ev.append({"t": "msg", "who": who, "text": "%s 은(는) 참기 시작했다!" % user.name})
                return None
            user.bide["left"] -= 1
            if user.bide["left"] > 0:
                ev.append({"t": "msg", "who": who, "text": "%s 은(는) 참고 있다!" % user.name})
                return None
            got, user.bide = user.bide["sum"], None
            ev.append({"t": "move", "who": who, "name": user.name, "move": self.move_name("BIDE"),
                       "moveType": move.get("type"), "cat": move.get("cat"),
                       "text": "%s 의 참기가 풀렸다!" % user.name})
            if not got:
                self._fail(who, ev)
                return None
            return dict(move, _fixed=got * 2, acc=0)
        if k in MC.OHKO:
            types = target.types() if target.ability_on else ((target.species or {}).get("types") or [])
            if target.level > user.level or (k == "SHEERCOLD" and "ICE" in types):
                ev.append({"t": "immune", "who": who,
                           "text": "%s 에게는 효과가 없는 것 같다..." % target.name})
                return None
            if target.ability_on and A.has(target, "STURDY") and not A.breaks(user):
                A.pop(self, target, tw, ev)
                ev.append({"t": "immune", "who": who,
                           "text": "%s 은(는) 옹골참으로 버텼다!" % target.name})
                return None
        if k == "ENDEAVOR" and target.hp <= user.hp:
            self._fail(who, ev)
            return None
        if k == "SPITUP":
            if not user.stockpile:
                self._fail(who, ev)
                return None
            n = min(3, user.stockpile)
            self._spend_stockpile(user, who, ev)
            return dict(move, _power=100 * n)
        if k == "MAGNITUDE":
            roll = self.rng.uniform(0, 100)
            size, pw = next((m, p) for cut, m, p in MC.MAGNITUDES if roll < cut)
            ev.append({"t": "msg", "who": who, "text": "매그니튜드 %d!" % size})
            return dict(move, _power=pw)
        if k == "FLING":
            if not MC.item_on(user) or not MC.FLING_POWER.get(user.held):
                self._fail(who, ev)
                return None
            ev.append({"t": "msg", "who": who,
                       "text": "%s 은(는) %s 을(를) 내던졌다!" % (user.name, H.name(user.held))})
            return dict(move, _power=MC.FLING_POWER[user.held], _item=user.held)
        if k == "NATURALGIFT":
            gift = MC.NATURAL_GIFT.get(user.held) if MC.item_on(user) else None
            if not gift:
                self._fail(who, ev)
                return None
            return dict(move, _power=gift[1] + MC.NATURAL_GIFT_BONUS, type=gift[0], _item=user.held)
        return move

    def _after_special(self, k, move, who, user, target, tw, total, ev):
        """때리고 난 뒤 (도구가 없어진다, 스스로 쓰러진다, 잠·마비가 풀린다)."""
        if move.get("_item"):
            user.item_gone = True
            user.held = None                 # 던지거나 먹은 도구는 이 판에서 효과도 없다
            fx = MC.FLING_EFFECT.get(move["_item"]) if k == "FLING" else None
            if fx and target.alive() and total:
                if fx == "flinch":
                    target.flinched = True
                else:
                    self._apply_status(target, fx, ev, source=user if user.ability_on else None)
        if k == "FINALGAMBIT" and total:
            user.hp = 0
        if k == "WAKEUPSLAP" and target.status == "sleep" and total and target.alive():
            target.status, target.sleep_turns = None, 0
            ev.append({"t": "cure", "who": tw, "text": "%s 은(는) 잠에서 깼다!" % target.name})
        if k == "SMELLINGSALTS" and target.status == "paralysis" and total and target.alive():
            target.status = None
            ev.append({"t": "cure", "who": tw, "text": "%s 의 마비가 풀렸다!" % target.name})

    def _spend_stockpile(self, user, who, ev):
        """토해내기·꿀꺽 뒤에 비축으로 오른 방어·특수방어를 되돌린다."""
        n, user.stockpile = user.stockpile, 0
        for stat in ("def", "spd"):
            before = user.stages.get(stat, 0)
            user.stages[stat] = max(STAGE_MIN, before - n)
        ev.append({"t": "msg", "who": who, "text": "%s 의 비축이 사라졌다!" % user.name})

    def _note_hurt(self, target, move, dmg, who):
        """이 턴에 맞은 데미지를 적어 둔다 (카운터·미러코트·메탈버스트·참기·눈사태)."""
        if dmg <= 0:
            return
        h = target.hurt or {"physical": 0, "special": 0, "by": who}
        cat = move.get("cat") if move.get("cat") in ("physical", "special") else "physical"
        h[cat] = h.get(cat, 0) + dmg
        h["by"] = who
        target.hurt = h
        if target.bide:
            target.bide["sum"] = target.bide.get("sum", 0) + dmg

    def _seed(self, target, who, tw, ev):
        types = target.types() if target.ability_on else ((target.species or {}).get("types") or [])
        if "GRASS" in types:
            ev.append({"t": "immune", "who": who,
                       "text": "%s 에게는 효과가 없는 것 같다..." % target.name})
        elif target.seeded:
            self._fail(who, ev)
        else:
            target.seeded = True
            ev.append({"t": "msg", "who": tw, "text": "%s 에게 씨앗을 심었다!" % target.name})

    def begin_turn(self):
        """턴 시작. 지난 턴에 맞은 데미지는 이번 턴의 카운터에 안 쓴다.

        그 턴에만 가는 것(방어·버티기·매직코트·가로채기·송전·패스트가드)도 여기서 푼다.
        """
        for f in (self.me, self.foe):
            f.hurt = None
            for c in ("protect", "endure", "magiccoat", "snatch", "electrify"):
                f.cond.pop(c, None)
        self.field.clear_turn_guards()
        self._suppress_weather()

    def _can_move(self, who, user, ev, key=None):
        """상태이상 때문에 못 움직이는지. 잠꼬대·코골기는 잠든 채로 쓴다."""
        if user.flinched:
            # who 를 같이 실어야 화면이 **누구 머리 위에** 띄울지 안다.
            ev.append({"t": "msg", "who": who,
                       "text": "%s 은(는) 풀이 죽어 움직이지 못했다!" % user.name})
            if user.ability_on:
                A.on_flinch(self, user, who, ev)
            return False
        if user.status == "sleep":
            if user.sleep_turns > 0:
                user.sleep_turns -= A.sleep_ticks(user) if user.ability_on else 1
                if user.sleep_turns < 0:
                    user.sleep_turns = 0
                ev.append({"t": "status", "who": who, "status": "sleep",
                           "text": "%s 은(는) 쿨쿨 잠들어 있다." % user.name})
                if key in ("SLEEPTALK", "SNORE"):
                    return True
                return False
            user.status = None
            user.cond.pop("nightmare", None)
            ev.append({"t": "cure", "who": who, "text": "%s 은(는) 잠에서 깼다!" % user.name})
        if user.status == "freeze":
            if self.rng.random() < 0.2:
                user.status = None
                ev.append({"t": "cure", "who": who,
                           "text": "%s 의 얼음이 녹았다!" % user.name})
            else:
                ev.append({"t": "status", "who": who, "status": "freeze",
                           "text": "%s 은(는) 얼어붙어 움직이지 못한다!" % user.name})
                return False
        if user.cond.get("confused") and not SM.confusion_turn(self, user, who, ev):
            return False
        if user.status == "paralysis" and self.rng.random() < 0.25:
            ev.append({"t": "status", "who": who, "status": "paralysis",
                       "text": "%s 은(는) 몸이 저려서 움직일 수 없다!" % user.name})
            return False
        if user.cond.get("attract") and not SM.attract_turn(self, user, who, ev):
            return False
        return True

    def _change_stat(self, f, stat, change, ev, who, source=None):
        if stat not in f.stages:
            return
        if change < 0 and source is not None and source is not f \
                and self.field.side(who).get("mist") and not A.has(source, "INFILTRATOR"):
            ev.append({"t": "msg", "who": who, "text": "%s 은(는) 흰안개에 보호받고 있다!" % f.name})
            return
        if f.ability_on:
            change, blocked = A.adjust_stat_change(self, f, stat, change, source, who, ev)
            if blocked or not change:
                return
        before = f.stages[stat]
        f.stages[stat] = max(STAGE_MIN, min(STAGE_MAX, before + change))
        if f.stages[stat] == before:
            ev.append({"t": "msg",
                       "text": "%s 의 %s 은(는) 더 이상 %s 않는다!"
                               % (f.name, STAT_KR.get(stat, stat),
                                  "오르지" if change > 0 else "내려가지")})
            return
        word = {2: "크게 올랐다", 1: "올랐다", -1: "떨어졌다", -2: "크게 떨어졌다"}
        text = word.get(change) or ("매우 크게 올랐다" if change > 2 else
                                    "매우 크게 떨어졌다" if change < -2 else "변했다")
        ev.append({"t": "stat", "who": who, "stat": stat, "change": change,
                   "text": "%s 의 %s 이(가) %s!"
                           % (f.name, STAT_KR.get(stat, stat), text)})
        if change < 0 and f.held:
            H.on_stat_drop(self, f, who, ev)            # 하양허브
        if change < 0 and f.ability_on:
            A.after_drop(self, f, who, source, ev)      # 오기·승기

    def status_kr(self, ail):
        return STATUS_KR.get(ail, ail)

    def _apply_status(self, f, ail, ev, source=None):
        if f.status:
            return
        types = f.types() if f.ability_on else ((f.species or {}).get("types") or [])
        # 타입에 따라 안 걸리는 상태이상
        immune = {"burn": "FIRE", "poison": "POISON", "paralysis": "ELECTRIC",
                  "freeze": "ICE"}
        corrode = ail == "poison" and source is not None and A.can_poison_types(source)
        if immune.get(ail) in types and not corrode:
            return
        if ail == "poison" and "STEEL" in types and not corrode:
            return
        who = "me" if f is self.me else "foe"
        if source is not None and source is not f and SM.blocked_by_guard(self, f, who, source, ev, quiet=True):
            return
        if ail == "sleep" and SM.terrain(f) == "electric" and SM.grounded(f):
            return
        if SM.terrain(f) == "misty" and SM.grounded(f):
            return
        if f.ability_on and A.has(f, "LEAFGUARD") and SM.weather(f) == "sun":
            return
        if f.ability_on and A.status_blocked(f, ail, source):
            A.pop(self, f, who, ev)
            ev.append({"t": "msg", "who": who,
                       "text": "%s 은(는) %s 상태가 되지 않는다!" % (f.name, STATUS_KR.get(ail, ail))})
            return
        f.status = ail
        if ail == "sleep":
            f.sleep_turns = self.rng.randint(1, 3)
        ev.append({"t": "ailment", "status": ail, "who": who,
                   "text": "%s 은(는) %s 상태가 되었다!" % (f.name, STATUS_KR.get(ail, ail))})
        if f.held:
            H.on_status(self, f, who, ev)               # 버치열매 같은 것
        if f.ability_on:
            A.on_status(self, f, who, ail, source, ev)  # 싱크로

    # ---------------- 턴 종료 ----------------
    def _end_of_turn(self, ev):
        SM.end_turn_pre(self, ev)
        for who, f in (("me", self.me), ("foe", self.foe)):
            if not f.alive():
                continue
            how = A.status_chip(f, f.status) if f.ability_on else "normal"
            if f.status == "burn" and how != "none":
                d = max(1, f.maxhp // (32 if how == "less" else 16))
                f.hp = max(0, f.hp - d)
                ev.append({"t": "chip", "who": who, "damage": d, "hp": f.hp,
                           "maxhp": f.maxhp,
                           "text": "%s 은(는) 화상 때문에 데미지를 입었다!" % f.name})
            elif f.status == "poison" and how == "heal":
                if f.hp < f.maxhp:
                    A.pop(self, f, who, ev)
                    d = max(1, f.maxhp // 8)
                    f.hp = min(f.maxhp, f.hp + d)
                    ev.append({"t": "heal", "who": who, "amount": d, "hp": f.hp,
                               "maxhp": f.maxhp,
                               "text": "%s 은(는) 체력을 회복했다!" % f.name})
            elif f.status == "poison" and how != "none":
                d = max(1, f.maxhp // 8)
                f.hp = max(0, f.hp - d)
                ev.append({"t": "chip", "who": who, "damage": d, "hp": f.hp,
                           "maxhp": f.maxhp,
                           "text": "%s 은(는) 독 때문에 데미지를 입었다!" % f.name})
            if f.seeded and f.alive() and not A.has(f, "MAGICGUARD"):
                self._drain_seed(f, who, ev)
            if f.held:
                H.end_of_turn(self, f, who, ev)     # 먹다남은음식, 맹독구슬 ...
            if f.ability_on:
                A.end_of_turn(self, f, who, ev)     # 가속, 탈피, 변덕쟁이 ...
        SM.end_turn_post(self, ev)
        self._check_faint(ev)

    def _drain_seed(self, f, who, ev):
        """씨뿌리기: 최대 체력의 1/8 을 빼앗아 맞은편에 준다."""
        other_who = "foe" if who == "me" else "me"
        other = self.foe if who == "me" else self.me
        d = min(f.hp, max(1, f.maxhp // 8))
        f.hp -= d
        ev.append({"t": "chip", "who": who, "damage": d, "hp": f.hp, "maxhp": f.maxhp,
                   "text": "씨뿌리기가 %s 의 체력을 빼앗는다!" % f.name})
        if not other.alive():
            return
        amount = max(1, int(d * H.drain_mult(other))) if other.held else d
        if A.has(f, "LIQUIDOOZE"):
            other.hp = max(0, other.hp - amount)
            ev.append({"t": "chip", "who": other_who, "damage": amount, "hp": other.hp,
                       "maxhp": other.maxhp, "text": "%s 은(는) 해감액을 흡수했다!" % other.name})
        elif other.hp < other.maxhp:
            other.hp = min(other.maxhp, other.hp + amount)
            ev.append({"t": "heal", "who": other_who, "amount": amount, "hp": other.hp,
                       "maxhp": other.maxhp, "text": "%s 은(는) 체력을 흡수했다!" % other.name})

    def _check_faint(self, ev):
        if not self.foe.alive():
            self.over = True
            self.result = "won"
            ev.append({"t": "faint", "who": "foe",
                       "text": "%s%s 은(는) 쓰러졌다!"
                               % (self.foe_prefix, self.foe.name)})
        elif not self.me.alive():
            self.over = True
            self.result = "lost"
            ev.append({"t": "faint", "who": "me",
                       "text": "%s 은(는) 쓰러졌다!" % self.me.name})

    # ---------------- 도주 ----------------
    def try_run(self, attempts=1):
        """본가 도주 공식. 스피드가 빠를수록 잘 도망간다."""
        if self.me.held and H.flee_sure(self.me):      # 연막탄
            return True
        a, b = self.me.stat("spe"), self.foe.stat("spe")
        if a >= b:
            return True
        odds = (int(a * 128 / max(1, b)) + 30 * attempts) % 256
        return self.rng.randrange(256) < odds

    def state(self):
        return {
            "turn": self.turn_no,
            "over": self.over,
            "result": self.result,
            "me": self.me.snapshot(),
            "foe": self.foe.snapshot(),
        }
