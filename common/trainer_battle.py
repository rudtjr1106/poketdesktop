# -*- coding: utf-8 -*-
"""관장 도전 — 트레이너와 6:6. **사람이 매 턴 고른다.**

야생 배틀(battle.Battle)은 1:1 이고, PvP(party_battle)는 양쪽을 AI 가 끝까지
돌린다. 관장 도전은 둘 다 아니다. 내 쪽은 사람이 기술을 고르거나 포켓몬을
바꾸고, 상대 트레이너는 AI 가 고른다. 한쪽이 전멸할 때까지 이어진다.

Battle 을 **감싸서** 쓴다. 고치지 않는다 - 야생과 PvP 가 그 위에서 돌고
있어서, 거기가 흔들리는 게 제일 나쁘다. 한 판 안에서 지금 나와 있는 둘을
Battle.me / Battle.foe 에 끼워 넣고, 바꿀 때 갈아 끼운다.

## 특성은 켠다

이 판의 Fighter 는 전부 ability_on = True 다. 위협·저수·옹골참 같은 것이
동작한다(common/abilities.py). 날씨·필드는 없다.

## 한 턴

    내가 고른 것      기술(move) 또는 교체(switch)
    상대가 고른 것    기술, 가끔 교체 (아래 '상대 AI')

    1. 교체가 먼저 일어난다 (내 쪽 -> 상대 쪽)
    2. 남은 기술들을 우선도·스피드 순으로 쓴다
    3. 턴 끝 처리 (화상·독·먹다남은음식·가속 ...)
    4. 쓰러진 쪽 정리
         상대가 쓰러지면 상대는 **바로** 다음을 내보낸다
         내가 쓰러지면 **다음 입력은 교체만** 받는다 (need_switch)

## 상대 AI

PvP 와 야생은 battle.Battle.choose_for 를 쓴다. 관장은 **여기서 따로 고른다** -
그쪽을 고치면 유저 배틀의 결과와 test_held 의 요약값이 바뀐다.

    기술    데미지를 셈하되 **누가 먼저 움직이는지**를 본다. 먼저 쓰러뜨릴 수
            있으면 끝내고, 내가 먼저 맞고 쓰러질 판이면 선공기를 쓴다.
    변화기  걸리지 않을 상태이상(불꽃에게 도깨비불, 이미 잠든 상대)은 안 쓴다.
            화상은 물리형에게, 마비는 나보다 빠른 상대에게 값을 더 친다.
            랭크업은 두 대 넘게 버틸 때만, +2 까지만 쌓는다.
            회복기는 반 넘게 깎였고 회복량이 맞는 양보다 많을 때만.
    교체    지금 포켓몬이 이번 턴에 쓰러질 판이거나 아무것도 못 하는 판이면,
            들어오면서 덜 맞고 상대를 더 때리는 포켓몬으로 바꾼다.
    다음    쓰러지면 지금 상대에게 가장 강한 포켓몬을 내보낸다.

트레이너 레벨이 높을수록 실수가 적고(Lv.20 10% -> Lv.100 0%) 교체를 잘 한다
(Lv.20 35% -> Lv.100 90%). 셈은 급소·난수 없이 한다.

## 저장

서버는 턴마다 DB 에 잤다가 깬다. dump() 가 판 전체(체력·PP·랭크·도구·특성
상태·난수 상태)를 JSON 으로 내고 load() 가 그대로 되살린다. 난수 상태까지
남기는 이유 - 시드만 남기고 매번 새로 굴리면 같은 턴을 다시 보내 결과를
골라 먹을 수 있다.
"""
import random

from . import abilities as A
from . import battle as B
from . import held as H
from . import movecalc as MC

TEAM_MAX = 6
MAX_TURNS = 400
STATS = ("hp", "atk", "def", "spa", "spd", "spe")
IV_GYM = 31                 # 관장 포켓몬의 개체값 (tools/build_gyms.py)

# 추정 데미지(EST_RNG 는 난수 0.977 쯤)를 평균 난수(0.925)로 낮춰 "쓰러뜨릴 수 있나" 를 본다
KO_ROLL = 0.95


def works(md):
    """이 엔진에서 뭔가 일어나는 기술인가.

    방어·대타출동·잠자기·날씨·도발 같은 것은 battle.py 가 처리하지 않아서 턴만 버린다.
    위력이 공식으로 정해지는 기술(안다리걸기·나이트헤드 ...)과 씨뿌리기는 이제 된다.
    """
    if not md:
        return False
    if MC.attacks(md) or md.get("heal"):
        return True
    if md.get("ail") in B.HANDLED_STATUS or md.get("ail") == "leech-seed":
        return True
    self_target = bool(md.get("statSelf"))
    # 나를 올리거나 상대를 내리는 것. 재주넘기처럼 상대를 올리는 것은 손해다.
    return any((change > 0) == self_target for _stat, change in (md.get("stat") or []))


def trainer_mon(entry):
    """gyms.json 의 한 줄 -> Fighter 가 먹는 mon.

    노력치는 능력마다 따로(evs) 적는다. 예전 자료의 한 숫자(ev)도 읽는다.
    """
    iv = int(entry.get("iv", IV_GYM))
    ev = int(entry.get("ev", 0))
    evs = entry.get("evs") or {}
    return {
        "species": entry["species"], "level": int(entry["level"]),
        "ivs": dict((s, iv) for s in STATS),
        "evs": dict((s, int(evs.get(s, ev))) for s in STATS),
        "nature": entry.get("nature") or "HARDY", "ability": entry.get("ability"),
        "moves": list(entry.get("moves") or []), "held": entry.get("held"),
        "gender": entry.get("gender") or "N", "shiny": False, "nickname": None,
        "statBoost": entry.get("boost"),
        "happiness": 255,           # 잘 키운 포켓몬 - 은혜갚기가 제 위력(102)으로 들어간다
    }


def best_score_better(sc, best):
    return best is None or sc > best


class Duel(B.Battle):
    """쓰러져도 판을 끝내지 않는 Battle. 끝내는 건 TrainerBattle 이 한다."""

    def _check_faint(self, ev):
        for who, f in (("foe", self.foe), ("me", self.me)):
            if not f.alive() and not f.ab.get("fainted"):
                f.ab["fainted"] = True
                prefix = "상대 " if who == "foe" else ""
                ev.append({"t": "faint", "who": who,
                           "text": "%s%s 은(는) 쓰러졌다!" % (prefix, f.name)})


class TrainerBattle(object):

    def __init__(self, dex, my_mons, trainer, rng=None):
        if not my_mons:
            raise ValueError("데리고 다니는 포켓몬이 없습니다.")
        self.dex = dex
        self.rng = rng or random.Random()
        self.trainer = {k: trainer.get(k) for k in ("id", "name", "role", "sprite", "level")}
        # 관장 탭 카드와 배틀 화면의 그림이 다른 트레이너가 있다 (이스터에그: 렌트라와 함께 / 혼자)
        self.trainer["battleSprite"] = trainer.get("battleSprite") or trainer.get("sprite")
        self.me_team = [self._fighter(m) for m in my_mons[:TEAM_MAX]]
        self.foe_team = [self._fighter(trainer_mon(e)) for e in trainer["team"][:TEAM_MAX]]
        self.mi = next(i for i, f in enumerate(self.me_team) if f.alive())
        self.fi = 0
        self.bt = Duel(dex, self.me_team[self.mi], self.foe_team[self.fi], self.rng, ai="trainer")
        self.bt.teams = {"me": self.me_team, "foe": self.foe_team}    # 집단폭행
        self.bt.foe_prefix = "상대 "
        self.bt.max_turns = 10 ** 9            # 끝내는 건 여기서 한다
        self.turn = 0
        self.over = False
        self.result = None                     # won / lost / draw / forfeit
        self.need_switch = False
        self.pending_entry = False             # 상대가 내보낸 뒤 특성 발동을 미뤄 둔 상태
        self.foe_switched_last = False
        self.seen = {0}                        # 한 번이라도 나온 상대 자리
        self.started = False
        # 누가 누구를 쓰러뜨렸나. 서버가 경험치를 줄 때 본다 (내 자리가 받는다).
        self.kos = []

    # ---------------- 만들기 ----------------
    def _fighter(self, mon):
        f = B.Fighter(self.dex, mon)
        f.ability_on = True
        return f

    @property
    def me(self):
        return self.me_team[self.mi]

    @property
    def foe(self):
        return self.foe_team[self.fi]

    def skill(self):
        """0(Lv.20) ~ 1(Lv.100)."""
        lv = int(self.trainer.get("level") or 50)
        return max(0.0, min(1.0, (lv - 20) / 80.0))

    def smartness(self):
        """상대가 불리할 때 실제로 바꿀 확률. 레벨이 높은 트레이너일수록 크다."""
        return 0.35 + 0.55 * self.skill()

    def mistake(self):
        """가장 좋은 수 대신 두 번째 수를 둘 확률."""
        return 0.10 * (1.0 - self.skill())

    # ---------------- 시작 ----------------
    def start(self):
        if self.started:
            return []
        self.started = True
        ev = [{"t": "intro", "trainer": self.trainer,
               "text": "%s %s 이(가) 승부를 걸어왔다!" % (self.trainer.get("role") or "",
                                                  self.trainer.get("name") or "")}]
        ev.append(self._out_event("foe", self.fi))
        ev.append(self._out_event("me", self.mi))
        self._entry_abilities(ev, fresh=False)
        return ev

    def _out_event(self, who, slot):
        f = (self.foe_team if who == "foe" else self.me_team)[slot]
        text = ("상대는 %s 을(를) 내보냈다!" % f.name) if who == "foe" else ("가랏! %s!" % f.name)
        return {"t": "switch", "who": who, "slot": slot, "mon": self.side(f, who == "me"),
                "text": text}

    def _entry_abilities(self, ev, fresh=True, only=None):
        """나온 순간의 특성(위협·다운로드 ...). 빠른 쪽부터."""
        pair = [("me", self.me), ("foe", self.foe)]
        if only:
            pair = [p for p in pair if p[0] in only]
        pair.sort(key=lambda p: -p[1].stat("spe"))
        for who, f in pair:
            if f.alive():
                self._count_down(f, who)
                A.on_switch_in(self.bt, f, who, ev)
                if not fresh:
                    f.ab["fresh"] = False

    def _count_down(self, f, who):
        team = self.me_team if who == "me" else self.foe_team
        f.ab["down"] = sum(1 for x in team if not x.alive())

    # ---------------- 교체 ----------------
    def _switch(self, who, slot, ev, trigger=True, fresh=True):
        team = self.me_team if who == "me" else self.foe_team
        old = self.me if who == "me" else self.foe
        if old.alive():
            A.on_switch_out(old)
            ev.append({"t": "recall", "who": who,
                       "text": ("%s, 돌아와!" % old.name) if who == "me"
                       else ("상대는 %s 을(를) 불러들였다!" % old.name)})
        old.stages = dict((k, 0) for k in B.STAGE_KEYS)
        old.flinched = False
        old.locked = None
        old.types_override = None
        old.clear_volatile()                    # 씨뿌리기·참기·비축은 물러나면 풀린다
        if who == "me":
            self.mi = slot
            self.bt.me = team[slot]
        else:
            self.fi = slot
            self.bt.foe = team[slot]
            self.seen.add(slot)
        ev.append(self._out_event(who, slot))
        if trigger:
            # 턴 사이에 들어온 것(쓰러진 뒤 교체)은 다음 턴 끝에 가속이 붙는다.
            self._entry_abilities(ev, fresh=fresh, only=(who,))

    # ---------------- 상대 AI ----------------
    def _est(self, user, target, key):
        """급소·난수 없이 이 기술이 줄 데미지. 명중률은 곱하지 않는다."""
        md = self.bt.move_of(key)
        if not MC.attacks(md) or A.would_block(user, target, md):
            return 0.0
        d, _crit, _eff = B.damage(self.dex, md, user, target, B.EST_RNG, crit=False)
        lo, hi = ((md.get("hits") or [1, 1]) + [1, 1])[:2]
        if MC.key(md) == "BEATUP" or MC.key(md) in MC.FIXED:
            hi = 1
        if hi > 1:
            d *= B.HITS_AVG if (lo, hi) == (2, 5) else (lo + hi) / 2.0
        return float(d)

    @staticmethod
    def _acc(md):
        return ((md or {}).get("acc") or 100) / 100.0

    def _hit_rate(self, md, user, target):
        """맞힐 확률. 일격기는 레벨 차이로 정해진다."""
        if MC.key(md) in MC.OHKO:
            return MC.ohko_accuracy(md, user, target) / 100.0
        return self._acc(md)

    def _pool(self, f):
        pool = self.bt.usable(f)
        return H.lock_pool(f, pool) if f.held else pool

    def _best(self, user, target):
        """(명중률을 곱한 데미지, 기술) — user 가 target 에게 쓸 가장 아픈 기술."""
        best, best_k = 0.0, None
        if not user.alive() or not target.alive():
            return best, best_k
        for k in self._pool(user):
            d = self._est(user, target, k) * self._hit_rate(self.bt.move_of(k), user, target)
            if d > best:
                best, best_k = d, k
        return best, best_k

    def _first(self, user, target, md, their_md=None):
        """user 가 이 기술로 target 보다 먼저 움직이나. 같으면 늦는 것으로 친다."""
        up = (md.get("pri") or 0) + A.priority_bonus(user, md)
        tp = ((their_md.get("pri") or 0) + A.priority_bonus(target, their_md)) if their_md else 0
        if up != tp:
            return up > tp
        return user.stat("spe") > target.stat("spe")

    def _foe_move(self):
        """상대 트레이너가 이번 턴에 쓸 기술."""
        bt = self.bt
        user, target = self.foe, self.me
        pool = self._pool(user)
        if pool == [B.STRUGGLE]:
            return B.STRUGGLE
        their_d, their_k = self._best(target, user)
        their_md = bt.move_of(their_k) if their_k else None
        their_ko = their_k is not None and their_d * KO_ROLL >= user.hp

        rows, dmg_best, main = [], 0.0, None
        for k in pool:
            md = bt.move_of(k)
            if not MC.attacks(md):
                rows.append([k, None, md])
                continue
            d = self._est(user, target, k)
            if d <= 0:
                rows.append([k, 0.0, md])
                continue
            acc = self._hit_rate(md, user, target)
            ohko = MC.key(md) in MC.OHKO
            first = self._first(user, target, md, their_md)
            dealt = min(d, target.hp)
            score = dealt * acc
            back = md.get("drain") or 0
            if back < 0:                                   # 반동기
                hurt = dealt * (-back) / 100.0
                score = score * 0.25 if hurt >= user.hp else score - hurt * 0.5
            elif back > 0:                                 # 흡수기
                score += dealt * back / 100.0 * 0.3
            if md.get("statSelf") and any(c < 0 for _st, c in (md.get("stat") or [])):
                score *= 0.9                               # 인파이트·용성군 (내 능력이 떨어진다)
            if ohko:
                score = target.hp * acc                    # 맞으면 끝, 명중률이 곧 값이다
            elif d * KO_ROLL >= target.hp:
                score = target.hp * acc * (3.0 if first else 1.6)
            if their_ko and not first:
                score *= 0.35                              # 쓰기 전에 쓰러질 공산이 크다
            if dealt * acc > dmg_best:
                dmg_best, main = dealt * acc, ("atk" if md.get("cat") == "physical" else "spa")
            rows.append([k, score, md])

        base = max(dmg_best, target.maxhp * 0.12)
        for row in rows:
            if row[1] is None:
                row[1] = self._status_value(user, target, row[2], base, dmg_best, main,
                                            their_d, their_md)

        scored = sorted([(s, i, k) for i, (k, s, _md) in enumerate(rows) if s and s > 0],
                        key=lambda x: (-x[0], x[1]))
        if not scored:
            return bt.choose_for(user, target, "trainer")
        if len(scored) > 1 and self.rng.random() < self.mistake():
            return scored[1][2]
        return scored[0][2]

    def _status_value(self, user, target, md, base, dmg_best, main, their_d, their_md):
        """변화기의 값을 '한 대 때린 것' 과 같은 단위로. 쓸모없으면 0."""
        if not works(md):
            return 0.0
        if their_d * KO_ROLL >= user.hp and not self._first(user, target, md, their_md):
            return 0.0                                      # 쓰기 전에 쓰러진다
        if A.aims_at_foe(md) and A.would_block(user, target, md):
            return 0.0
        can_ko = dmg_best * KO_ROLL >= target.hp
        value = 0.0
        ail = md.get("ail")
        if ail in B.HANDLED_STATUS and not can_ko:
            value += self._ail_value(user, target, ail, base)
        if md.get("stat") and not can_ko:
            value += self._stat_value(user, target, md, base, main, their_d, their_md)
        if md.get("ail") == "leech-seed" and not can_ko:
            types = target.types()
            if not target.seeded and "GRASS" not in types:
                # 턴마다 1/8 을 빼앗는다. 판이 길수록 값을 한다.
                lasts = user.hp / their_d if their_d > 0 else 9.0
                value += base * 0.7 * max(0.0, min(1.0, (lasts - 1.0) / 2.0))
        mk = MC.key(md)
        if mk == "SWALLOW" and not user.stockpile:
            return 0.0
        if mk == "STOCKPILE" and user.stockpile >= 3:
            return 0.0
        heal = md.get("heal") or 0
        if heal and user.hp < user.maxhp:
            amount = min(user.maxhp - user.hp, user.maxhp * heal / 100.0)
            left = user.hp / float(user.maxhp)
            if left <= 0.55 and amount > their_d:           # 회복해도 그만큼 다시 맞으면 제자리
                value += base * (amount / float(user.maxhp)) * 4.0 * (1.0 - left)
        return value * self._acc(md)

    def _ail_value(self, user, target, ail, base):
        if target.status:
            return 0.0
        types = target.types()
        corrode = ail == "poison" and A.can_poison_types(user)
        immune = {"burn": "FIRE", "poison": "POISON", "paralysis": "ELECTRIC", "freeze": "ICE"}
        if not corrode and (immune.get(ail) in types or (ail == "poison" and "STEEL" in types)):
            return 0.0
        if A.status_blocked(target, ail, user):
            return 0.0
        if ail in ("sleep", "freeze"):
            v = 1.5
        elif ail == "paralysis":
            ts, us = target.stat("spe"), user.stat("spe")
            v = 1.2 if ts > us and ts * 0.5 < us else 0.6    # 마비로 내가 먼저 움직이게 된다
        elif ail == "burn":
            v = 1.2 if target.base["atk"] > target.base["spa"] else 0.35
        else:                                               # 독 - 오래 가는 판에서 값을 한다
            v = 1.0 if base < target.maxhp * 0.25 else 0.4
        if ail in ("burn", "paralysis", "poison") and A.has(target, "SYNCHRONIZE") and not user.status:
            v *= 0.4
        left = target.hp / float(target.maxhp or 1)
        return base * v * (0.4 + 0.6 * min(1.0, left * 1.3))

    def _stat_value(self, user, target, md, base, main, their_d, their_md):
        v = 0.0
        self_target = bool(md.get("statSelf"))
        their_def = "def" if (their_md or {}).get("cat") == "physical" else "spd"
        for stat, change in md.get("stat") or []:
            if self_target and change > 0:
                cur = user.stages.get(stat, 0)
                if cur >= 2:
                    continue                                # +2 넘게는 쌓지 않는다
                new = min(2, cur + change)
                if stat == main:
                    v += B.stage_mult(new) / B.stage_mult(cur) - 1.0
                elif stat == "spe":
                    us, ts = user.stat("spe"), target.stat("spe")
                    after = us * B.stage_mult(new) / B.stage_mult(cur)
                    v += 0.8 if us <= ts < after else 0.1
                elif stat == their_def:
                    v += 0.3 * (new - cur)
                elif stat == "eva":
                    v += 0.15 * (new - cur)
            elif not self_target and change < 0:
                cur = target.stages.get(stat, 0)
                if cur <= -2:
                    continue
                if stat in ("atk", "spa") and their_md and stat == ("atk" if their_md.get("cat") == "physical" else "spa"):
                    v += 0.25 * min(2, -change)
                elif stat == "spe":
                    us, ts = user.stat("spe"), target.stat("spe")
                    v += 0.5 if ts >= us > ts * B.stage_mult(change) else 0.05
                elif main and stat == ("def" if main == "atk" else "spd"):
                    v += 0.25 * min(2, -change)
                elif stat == "acc":
                    v += 0.1
            elif self_target and change < 0:
                v -= 0.1 * (-change)                        # 껍질깨기의 방어 하락
        if v <= 0:
            return 0.0
        # 올려 놓고 때릴 시간이 있어야 한다. 이번 턴에 한 대 맞고도 두 대 넘게 버틸 때만.
        lasts = user.hp / their_d if their_d > 0 else 9.0
        room = max(0.0, min(1.0, (lasts - 1.5) / 2.0))
        return base * v * 2.0 * room

    def _standing(self, f, foe_mon):
        """f 가 foe_mon 과 붙었을 때의 점수. 클수록 f 에게 유리하다."""
        deal, dk = self._best(f, foe_mon)
        take, tk = self._best(foe_mon, f)
        sc = min(1.0, deal / float(foe_mon.hp or 1)) - 0.7 * min(1.0, take / float(f.hp or 1))
        if dk and deal * KO_ROLL >= foe_mon.hp and self._first(f, foe_mon, self.bt.move_of(dk),
                                                              self.bt.move_of(tk) if tk else None):
            sc += 0.6
        elif tk and take * KO_ROLL >= f.hp and not (dk and self._first(
                f, foe_mon, self.bt.move_of(dk), self.bt.move_of(tk))):
            sc -= 0.4
        return sc

    def _pick(self, team, against, cur=None):
        """쓰러진 뒤 내보낼 자리. 상대도 쓰러져 곧 바꿀 거면 남은 상대 전부를 두고 본다."""
        rivals = [against] if against.alive() else [f for f in self.me_team if f.alive()]
        best, best_sc = None, None
        for i, f in enumerate(team):
            if not f.alive():
                continue
            sc = sum(self._standing(f, r) for r in rivals) / float(len(rivals) or 1)
            if best_score_better(sc, best_sc):
                best, best_sc = i, sc
        return best

    def _foe_wants_switch(self):
        """상대가 이번 턴에 바꾸고 싶은 자리. 안 바꾸면 None."""
        if self.foe_switched_last:
            return None
        others = [i for i, f in enumerate(self.foe_team) if f.alive() and i != self.fi]
        if not others:
            return None
        foe, me = self.foe, self.me
        their_d, their_k = self._best(me, foe)
        if their_k is None:
            return None
        their_md = self.bt.move_of(their_k)
        our_d, our_k = self._best(foe, me)
        if our_k and our_d * KO_ROLL >= me.hp and self._first(foe, me, self.bt.move_of(our_k), their_md):
            return None                                     # 먼저 쓰러뜨리면 된다
        danger = their_d * KO_ROLL >= foe.hp
        walled = our_d < me.maxhp * 0.12 and their_d >= foe.hp * 0.35
        if not (danger or walled):
            return None
        stay = min(1.0, our_d / float(me.hp)) - 0.7 * min(1.0, their_d / float(foe.hp))
        best, best_sc = None, None
        for i in others:
            f = self.foe_team[i]
            # 들어오면서 사람이 고를 기술(지금 포켓몬에게 가장 아픈 것)을 맞는다
            taken = self._est(me, f, their_k) * self._acc(their_md)
            if taken >= f.hp * 0.6:
                continue
            left = f.hp - taken
            deal, _dk = self._best(f, me)
            nxt, _nk = self._best(me, f)
            sc = (min(1.0, deal / float(me.hp)) - 0.7 * min(1.0, nxt / float(left))
                  - 0.3 * taken / float(f.maxhp))
            if best_score_better(sc, best_sc):
                best, best_sc = i, sc
        if best is None or best_sc < stay + 0.25:
            return None
        if self.rng.random() >= self.smartness():
            return None
        return best

    # ---------------- 한 턴 ----------------
    def valid_switches(self):
        return [i for i, f in enumerate(self.me_team) if f.alive() and i != self.mi]

    def act(self, kind, value=None):
        """kind: 'move' (value=기술) / 'switch' (value=자리) / 'forfeit'"""
        if self.over:
            return [{"t": "over", "result": self.result}]
        if not self.started:
            return self.start()
        if kind == "forfeit":
            self.over = True
            self.result = "forfeit"
            return [{"t": "over", "result": "forfeit", "text": "승부를 포기했다..."}]

        ev = []
        if self.need_switch:
            if kind != "switch" or value not in self.valid_switches():
                raise ValueError("다음 포켓몬을 골라야 합니다.")
            self.need_switch = False
            self._switch("me", value, ev, trigger=not self.pending_entry, fresh=False)
            if self.pending_entry:
                self.pending_entry = False
                self._entry_abilities(ev, fresh=False)
            return ev

        if kind == "switch" and value not in self.valid_switches():
            raise ValueError("그 포켓몬으로는 바꿀 수 없습니다.")

        self.turn += 1
        self.bt.turn_no = self.turn
        bt = self.bt
        bt.begin_turn()
        me_move = None
        foe_move = None

        # 상대가 무엇을 할지 먼저 정한다 (내 선택을 보지 않는다)
        foe_slot = self._foe_wants_switch()
        if foe_slot is None:
            foe_move = self._foe_move()

        if kind == "switch":
            self._switch("me", value, ev)
        else:
            me = self.me
            me_move = value
            if me_move != B.STRUGGLE and (me_move not in me.pp or me.pp.get(me_move, 0) <= 0):
                me_move = bt.usable(me)[0]
            if me.held:
                me_move = H.force_move(me, me_move, ev, "me")

        if foe_slot is not None:
            self._switch("foe", foe_slot, ev)
            self.foe_switched_last = True
        else:
            self.foe_switched_last = False

        me, foe = self.me, self.foe
        me.flinched = False
        foe.flinched = False
        if me_move and foe_move:
            order = bt._order(me_move, foe_move, ev)
        elif me_move:
            order = ["me"]
        elif foe_move:
            order = ["foe"]
        else:
            order = []
        me.moved_second = bool(order) and order[0] != "me"
        foe.moved_second = bool(order) and order[0] != "foe"

        for who in order:
            user, target = (self.me, self.foe) if who == "me" else (self.foe, self.me)
            if not user.alive() or not target.alive():
                continue
            bt._use(who, user, target, me_move if who == "me" else foe_move, ev)

        if self.me.alive() or self.foe.alive():
            bt._end_of_turn(ev)
        bt._check_faint(ev)
        if not self.foe.alive() and not any(k["foe"] == self.fi for k in self.kos):
            self.kos.append({"foe": self.fi, "by": self.mi, "turn": self.turn})
        self._settle(ev)
        if not self.over and self.turn >= MAX_TURNS:
            self._by_headcount(ev)
        return ev

    def _settle(self, ev):
        """쓰러진 쪽을 정리한다."""
        me_down = not self.me.alive()
        foe_down = not self.foe.alive()
        if not me_down and not foe_down:
            return
        me_left = [i for i, f in enumerate(self.me_team) if f.alive()]
        foe_left = [i for i, f in enumerate(self.foe_team) if f.alive()]
        if not me_left and not foe_left:
            return self._finish("draw", ev)
        if not foe_left:
            return self._finish("won", ev)
        if not me_left:
            return self._finish("lost", ev)
        if foe_down:
            nxt = self._pick(self.foe_team, self.me)
            # 나도 쓰러져서 곧 바꿀 거면, 상대의 등장 특성은 내가 고른 뒤에
            self._switch("foe", nxt, ev, trigger=not me_down, fresh=False)
            if me_down:
                self.pending_entry = True
            self.foe_switched_last = False
        if me_down:
            self.need_switch = True
            ev.append({"t": "choose", "who": "me", "text": "다음 포켓몬을 고르세요."})

    def _finish(self, result, ev):
        self.over = True
        self.result = result
        text = {"won": "%s 과(와)의 승부에서 이겼다!" % self.trainer.get("name"),
                "lost": "눈앞이 캄캄해졌다...",
                "draw": "양쪽 모두 쓰러졌다..."}[result]
        ev.append({"t": "over", "result": result, "text": text})

    def _by_headcount(self, ev):
        na = sum(1 for f in self.me_team if f.alive())
        nb = sum(1 for f in self.foe_team if f.alive())
        if na == nb:
            ra = sum(f.hp / float(f.maxhp or 1) for f in self.me_team)
            rb = sum(f.hp / float(f.maxhp or 1) for f in self.foe_team)
            na, nb = ra, rb
        self._finish("won" if na > nb else ("lost" if na < nb else "draw"), ev)

    # ---------------- 보여주기 ----------------
    def side(self, f, mine):
        sp = f.species or {}
        dex = self.dex
        out = {
            "species": f.mon["species"], "num": sp.get("num"), "name": f.name,
            "level": f.level, "hp": f.hp, "maxhp": f.maxhp,
            "status": f.status, "statusKr": B.STATUS_KR.get(f.status),
            "gender": f.mon.get("gender"), "shiny": bool(f.mon.get("shiny")),
            "types": [dex.type_name(t) for t in f.types()], "typeIds": f.types(),
            "stages": dict((k, v) for k, v in f.stages.items() if v),
            "fainted": not f.alive(),
        }
        if mine or f.ab.get("shown"):
            out["ability"] = f.ability
            out["abilityKr"] = dex.ability_name(f.ability) if f.ability else None
        if mine:
            out["id"] = f.mon.get("id")
            out["held"] = f.held
            out["heldKr"] = H.name(f.held) if f.held else None
            out["locked"] = f.locked
            out["stats"] = dict((k, f.base.get(k)) for k in STATS)
            moves = []
            for m in f.moves:
                md = dex.move(m) or {}
                moves.append({"key": m, "kr": dex.move_name(m), "type": md.get("type"),
                              "typeKr": dex.type_name(md.get("type")), "cat": md.get("cat"),
                              "power": md.get("power"), "acc": md.get("acc"),
                              "pp": f.pp.get(m, 0), "maxpp": md.get("pp", 0),
                              "desc": md.get("desc", "")})
            if not any(x["pp"] > 0 for x in moves):
                moves.append({"key": B.STRUGGLE, "kr": "몸부림", "type": "NORMAL",
                              "typeKr": "노말", "cat": "physical", "power": 50, "acc": 0,
                              "pp": 1, "maxpp": 1, "desc": ""})
            out["moves"] = moves
        return out

    def view(self):
        foe_team = []
        for i, f in enumerate(self.foe_team):
            if i in self.seen:
                foe_team.append(self.side(f, False))
            else:
                foe_team.append({"hidden": True, "fainted": not f.alive()})
        return {
            "turn": self.turn, "over": self.over, "result": self.result,
            "needSwitch": self.need_switch, "trainer": self.trainer,
            "me": {"slot": self.mi, "team": [self.side(f, True) for f in self.me_team]},
            "foe": {"slot": self.fi, "team": foe_team},
        }

    # ---------------- 저장 ----------------
    @staticmethod
    def _dump_fighter(f):
        return {"mon": f.mon, "hp": f.hp, "pp": f.pp, "status": f.status,
                "stages": f.stages, "sleep": f.sleep_turns, "held": f.held_state(),
                "abil": A.state(f), "vol": f.volatile()}

    def _load_fighter(self, d):
        f = B.Fighter(self.dex, d["mon"], d["hp"], d["pp"], d["status"])
        f.stages = d.get("stages") or f.stages
        f.sleep_turns = d.get("sleep", 0)
        f.load_held(d.get("held"))
        f.ability_on = True
        A.load(f, d.get("abil"))
        f.load_volatile(d.get("vol"))
        return f

    def dump(self):
        st = self.rng.getstate()
        return {
            "v": 1, "trainer": self.trainer,
            "me": [self._dump_fighter(f) for f in self.me_team],
            "foe": [self._dump_fighter(f) for f in self.foe_team],
            "mi": self.mi, "fi": self.fi, "turn": self.turn, "over": self.over,
            "result": self.result, "needSwitch": self.need_switch,
            "pendingEntry": self.pending_entry, "foeSwitchedLast": self.foe_switched_last,
            "seen": sorted(self.seen), "started": self.started, "kos": self.kos,
            "rng": [st[0], list(st[1]), st[2]],
        }

    @classmethod
    def load(cls, dex, d):
        self = cls.__new__(cls)
        self.dex = dex
        self.rng = random.Random()
        r = d["rng"]
        self.rng.setstate((r[0], tuple(r[1]), r[2]))
        self.trainer = d["trainer"]
        self.me_team = [self._load_fighter(x) for x in d["me"]]
        self.foe_team = [self._load_fighter(x) for x in d["foe"]]
        self.mi, self.fi = d["mi"], d["fi"]
        self.bt = Duel(dex, self.me_team[self.mi], self.foe_team[self.fi], self.rng, ai="trainer")
        self.bt.teams = {"me": self.me_team, "foe": self.foe_team}    # 집단폭행
        self.bt.foe_prefix = "상대 "
        self.bt.max_turns = 10 ** 9
        self.turn = d["turn"]
        self.bt.turn_no = self.turn
        self.over = d["over"]
        self.result = d["result"]
        self.need_switch = d["needSwitch"]
        self.pending_entry = d.get("pendingEntry", False)
        self.foe_switched_last = d.get("foeSwitchedLast", False)
        self.seen = set(d.get("seen") or [0])
        self.started = d.get("started", True)
        self.kos = list(d.get("kos") or [])
        return self
