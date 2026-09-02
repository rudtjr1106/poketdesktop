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

from . import pokelogic as P

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

    # ---- 상태 ----
    def alive(self):
        return self.hp > 0

    def stat(self, key, crit=False):
        v = self.base.get(key, 1)
        s = self.stages.get(key, 0)
        if crit and s < 0:                  # 급소는 상대의 방어 상승/내 공격 하락을 무시
            s = 0
        v = int(v * stage_mult(s))
        if key == "spe" and self.status == "paralysis":
            v = int(v * 0.5)
        return max(1, v)

    def snapshot(self):
        return {"hp": self.hp, "maxhp": self.maxhp, "status": self.status,
                "pp": dict(self.pp), "stages": dict(self.stages)}


# ---------------------------------------------------------------- 계산
def effectiveness(dex, move_type, defender_types):
    t = dex.types.get(move_type) or {}
    eff = t.get("eff") or {}
    mult = 1.0
    for d in defender_types:
        mult *= eff.get(d, 1.0)
    return mult


def accuracy_check(dex, move, user, target, rng):
    acc = move.get("acc") or 0
    if acc <= 0:                            # 0 = 반드시 맞는 기술
        return True
    rate = acc * stage_mult(user.stages["acc"], "acc") \
        / stage_mult(target.stages["eva"], "acc")
    return rng.uniform(0, 100) < rate


def damage(dex, move, user, target, rng, crit=None):
    """(데미지, 급소여부, 상성배율) 을 돌려준다."""
    power = move.get("power") or 0
    if power <= 0:
        return 0, False, 1.0
    phys = move.get("cat") == "physical"
    if crit is None:
        chance = CRIT_CHANCE
        if move.get("crit"):                # 급소율이 높은 기술
            chance = max(2, CRIT_CHANCE // (2 ** move["crit"]))
        crit = rng.randrange(chance) == 0

    a = user.stat("atk" if phys else "spa", crit)
    d = target.stat("def" if phys else "spd", crit)
    base = math.floor(math.floor(math.floor(2 * user.level / 5 + 2) * power * a / d)
                      / 50) + 2

    mult = 1.0
    if user.species and move.get("type") in (user.species.get("types") or []):
        mult *= STAB
    eff = effectiveness(dex, move.get("type"), (target.species or {}).get("types", []))
    mult *= eff
    if crit:
        mult *= CRIT_MULT
    mult *= rng.uniform(0.85, 1.0)
    if user.status == "burn" and phys:
        mult *= 0.5

    dmg = int(base * mult)
    if eff > 0:
        dmg = max(1, dmg)
    return dmg, crit, eff


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

    def __init__(self, dex, mine, foe, rng=None, ai="wild"):
        self.dex = dex
        self.rng = rng or random.Random()
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
        """쓸 수 있는 기술. 하나도 없으면 몸부림."""
        out = [m for m in f.moves if f.pp.get(m, 0) > 0]
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

        if ai == "wild":
            # 위력이 있는 기술 쪽으로 살짝만 기울인 무작위
            weights = []
            for m in pool:
                md = self.move_of(m)
                if md.get("power"):
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
            acc = (md.get("acc") or 100) / 100.0
            if md.get("power"):
                d, _c, _e = damage(self.dex, md, user, target,
                                   EST_RNG, crit=False)
                # 연속기는 한 번 때리는 게 아니다. 씨앗기관총(위력 25)이
                # 위력 25 짜리로 평가되어 늘 뒷전으로 밀렸다.
                hits = md.get("hits") or [1, 1]
                lo, hi = (hits + [1, 1])[:2]
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
                if d >= target.hp:          # 이걸로 끝낼 수 있으면 최우선
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

    def _status_score(self, md, best_dmg, user=None, target=None):
        """변화기가 지금 쓸 만한지. 효과가 이미 걸려 있으면 0."""
        user = user or self.foe
        target = target or self.me
        useful = False
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
        foe_move = self.choose_ai()

        if my_move != STRUGGLE and (my_move not in self.me.pp
                                    or self.me.pp.get(my_move, 0) <= 0):
            my_move = self.usable(self.me)[0]

        order = self._order(my_move, foe_move)
        self.me.flinched = False
        self.foe.flinched = False

        for who in order:
            if self.over:
                break
            user, target = (self.me, self.foe) if who == "me" else (self.foe, self.me)
            key = my_move if who == "me" else foe_move
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

    def _order(self, my_move, foe_move):
        mp = self.move_of(my_move).get("pri", 0) if my_move else 0
        fp = self.move_of(foe_move).get("pri", 0) if foe_move else 0
        if mp != fp:
            return ["me", "foe"] if mp > fp else ["foe", "me"]
        ms, fs = self.me.stat("spe"), self.foe.stat("spe")
        if ms != fs:
            return ["me", "foe"] if ms > fs else ["foe", "me"]
        return ["me", "foe"] if self.rng.random() < 0.5 else ["foe", "me"]

    # ---------------- 기술 사용 ----------------
    def _use(self, who, user, target, key, ev):
        if key is None:
            key = STRUGGLE
        move = self.move_of(key)

        if not self._can_move(who, user, ev):
            return

        if key != STRUGGLE:
            user.pp[key] = max(0, user.pp.get(key, 0) - 1)
        ev.append({"t": "move", "who": who, "name": user.name,
                   "move": self.move_name(key), "moveType": move.get("type"),
                   "cat": move.get("cat"),
                   "text": "%s 의 %s!" % (user.name, self.move_name(key))})

        if not accuracy_check(self.dex, move, user, target, self.rng):
            ev.append({"t": "miss", "who": who, "text": "하지만 빗나갔다!"})
            return

        total = 0
        if move.get("power"):
            lo, hi = (move.get("hits") or [1, 1])[:2]
            times = 1
            if hi > 1:
                times = self.rng.choice(MULTI_HIT) if (lo, hi) == (2, 5) \
                    else self.rng.randint(lo, hi)
            eff = 1.0
            for i in range(times):
                if not target.alive():
                    break
                dmg, crit, eff = damage(self.dex, move, user, target, self.rng)
                if key == STRUGGLE and eff == 0:      # 몸부림은 무효가 없다
                    eff = 1.0
                    dmg = max(1, dmg or 1)
                if eff == 0:
                    ev.append({"t": "immune", "who": who,
                               "text": "%s 에게는 효과가 없는 것 같다..." % target.name})
                    return
                target.hp = max(0, target.hp - dmg)
                total += dmg
                ev.append({"t": "hit", "who": who, "target": "foe" if who == "me" else "me",
                           "damage": dmg, "crit": crit, "eff": eff,
                           "hp": target.hp, "maxhp": target.maxhp})
                if crit:
                    ev.append({"t": "msg", "text": "급소에 맞았다!"})
            if times > 1:
                ev.append({"t": "msg", "text": "%d번 맞았다!" % min(times, i + 1)})
            if eff > 1:
                ev.append({"t": "msg", "text": "효과가 굉장했다!"})
            elif 0 < eff < 1:
                ev.append({"t": "msg", "text": "효과가 별로인 듯하다..."})

        # 흡수 / 반동
        drain = move.get("drain") or 0
        if drain and total:
            amount = max(1, int(total * abs(drain) / 100.0))
            if drain > 0:
                user.hp = min(user.maxhp, user.hp + amount)
                ev.append({"t": "heal", "who": who, "amount": amount, "hp": user.hp,
                           "maxhp": user.maxhp,
                           "text": "%s 은(는) 체력을 흡수했다!" % target.name})
            else:
                user.hp = max(0, user.hp - amount)
                ev.append({"t": "recoil", "who": who, "amount": amount, "hp": user.hp,
                           "maxhp": user.maxhp,
                           "text": "%s 은(는) 반동을 받았다!" % user.name})

        # 회복기
        heal = move.get("heal") or 0
        if heal > 0 and user.hp < user.maxhp:
            amount = max(1, int(user.maxhp * heal / 100.0))
            user.hp = min(user.maxhp, user.hp + amount)
            ev.append({"t": "heal", "who": who, "amount": amount, "hp": user.hp,
                       "maxhp": user.maxhp,
                       "text": "%s 은(는) 체력을 회복했다!" % user.name})

        # 능력 변화
        stats = move.get("stat") or []
        if stats:
            chance = move.get("statChance") or 0
            if chance == 0 or self.rng.uniform(0, 100) < chance:
                # 누구에게 거는지는 도감을 만들 때 이미 판정해 두었다
                # (build_pokedex._stat_self). 여기서 짐작하면 안 된다 -
                # 예전에는 '올려주는 기술이면 자기 자신' 으로 짐작했는데,
                # 그러면 메탈클로처럼 때리면서 자기 공격이 오르는 기술이
                # 전부 상대를 강화해 버렸다.
                dst = user if move.get("statSelf") else target
                for stat, change in stats:
                    self._change_stat(dst, stat, change, ev,
                                      "me" if dst is self.me else "foe")

        # 상태이상
        ail = move.get("ail")
        if ail in HANDLED_STATUS and target.alive():
            chance = move.get("ailChance") or 0
            if chance == 0 or self.rng.uniform(0, 100) < chance:
                self._apply_status(target, ail, ev)

        # 풀죽음
        fl = move.get("flinch") or 0
        if fl and target.alive() and self.rng.uniform(0, 100) < fl:
            target.flinched = True

        self._check_faint(ev)

    def _can_move(self, who, user, ev):
        """상태이상 때문에 못 움직이는지."""
        if user.flinched:
            ev.append({"t": "msg", "text": "%s 은(는) 풀이 죽어 움직이지 못했다!" % user.name})
            return False
        if user.status == "sleep":
            if user.sleep_turns > 0:
                user.sleep_turns -= 1
                ev.append({"t": "status", "who": who, "status": "sleep",
                           "text": "%s 은(는) 쿨쿨 잠들어 있다." % user.name})
                return False
            user.status = None
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
        if user.status == "paralysis" and self.rng.random() < 0.25:
            ev.append({"t": "status", "who": who, "status": "paralysis",
                       "text": "%s 은(는) 몸이 저려서 움직일 수 없다!" % user.name})
            return False
        return True

    def _change_stat(self, f, stat, change, ev, who):
        if stat not in f.stages:
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
        ev.append({"t": "stat", "who": who, "stat": stat, "change": change,
                   "text": "%s 의 %s 이(가) %s!"
                           % (f.name, STAT_KR.get(stat, stat),
                              word.get(change, "변했다"))})

    def _apply_status(self, f, ail, ev):
        if f.status:
            return
        sp = f.species or {}
        types = sp.get("types") or []
        # 타입에 따라 안 걸리는 상태이상
        immune = {"burn": "FIRE", "poison": "POISON", "paralysis": "ELECTRIC",
                  "freeze": "ICE"}
        if immune.get(ail) in types:
            return
        if ail == "poison" and "STEEL" in types:
            return
        f.status = ail
        if ail == "sleep":
            f.sleep_turns = self.rng.randint(1, 3)
        ev.append({"t": "ailment", "status": ail,
                   "who": "me" if f is self.me else "foe",
                   "text": "%s 은(는) %s 상태가 되었다!" % (f.name, STATUS_KR.get(ail, ail))})

    # ---------------- 턴 종료 ----------------
    def _end_of_turn(self, ev):
        for who, f in (("me", self.me), ("foe", self.foe)):
            if not f.alive():
                continue
            if f.status == "burn":
                d = max(1, f.maxhp // 16)
                f.hp = max(0, f.hp - d)
                ev.append({"t": "chip", "who": who, "damage": d, "hp": f.hp,
                           "maxhp": f.maxhp,
                           "text": "%s 은(는) 화상 때문에 데미지를 입었다!" % f.name})
            elif f.status == "poison":
                d = max(1, f.maxhp // 8)
                f.hp = max(0, f.hp - d)
                ev.append({"t": "chip", "who": who, "damage": d, "hp": f.hp,
                           "maxhp": f.maxhp,
                           "text": "%s 은(는) 독 때문에 데미지를 입었다!" % f.name})
        self._check_faint(ev)

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
