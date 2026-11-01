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
import json
import random
import sys
import time

from . import abilities as A
from . import attackfx as AF
from . import battle as B
from . import field as FD
from . import held as H
from . import movecalc as MC
from . import statusmoves as SM

TEAM_MAX = 6
# 이 레벨 이상의 관장은 메가진화를 쓴다 (시즌 3). 한 판에 한 번이라 팀에서
# 메가가 되는 첫 포켓몬에게만 스톤을 쥐여 준다.
MEGA_TRAINER_LEVEL = 80


def give_mega_stone(dex, team, level):
    """높은 관장의 팀에서 메가가 되는 첫 포켓몬에게 스톤을 쥐여 준다.

    레쿠쟈처럼 스톤 대신 기술로 되는 폼은 건너뛴다. 준 자리를 돌려준다(없으면 None).
    """
    if int(level or 0) < MEGA_TRAINER_LEVEL:
        return None
    for i, f in enumerate(team):
        forms = (getattr(dex, "mega_of", None) or {}).get(f.mon.get("species")) or []
        stone = next((m.get("megaStone") for m in forms if m.get("megaStone")), None)
        if stone:
            f.held = stone
            f.mon = dict(f.mon, held=stone)
            return i
    return None
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
    k = MC.key(md)
    if k in SM.AI_DEAD:
        return False                      # 1:1 에서 실패하거나 AI 가 쓸 일이 없는 것
    if k in SM.HANDLERS or k in AF.HANDLERS or MC.attacks(md) or md.get("heal"):
        return True
    if md.get("ail") in B.HANDLED_STATUS or md.get("ail") == "leech-seed":
        return True
    self_target = bool(md.get("statSelf"))
    # 나를 올리거나 상대를 내리는 것. 재주넘기처럼 상대를 올리는 것은 손해다.
    return any((change > 0) == self_target for _stat, change in (md.get("stat") or []))


def trainer_mon(entry):
    """gyms.json 의 한 줄 -> Fighter 가 먹는 mon.

    노력치는 능력마다 따로(evs) 적는다. 예전 자료의 한 숫자(ev)도 읽는다.
    **이미 mon 인 것**(개체값을 능력마다 가진 것 - 길드전에서 사람이 짠 방어팀)은 그대로 쓴다.
    """
    if isinstance(entry.get("ivs"), dict):
        mon = dict(entry)
        mon.setdefault("happiness", 255)
        mon.setdefault("statBoost", None)
        return mon
    iv = int(entry.get("iv", IV_GYM))
    ev = int(entry.get("ev", 0))
    evs = entry.get("evs") or {}
    return {
        "species": entry["species"], "level": int(entry["level"]),
        "ivs": dict((s, iv) for s in STATS),
        "evs": dict((s, int(evs.get(s, ev))) for s in STATS),
        "nature": entry.get("nature") or "HARDY", "ability": entry.get("ability"),
        "moves": list(entry.get("moves") or []), "held": entry.get("held"),
        "gender": entry.get("gender") or "N", "nickname": None,
        # 관장 포켓몬은 보통 이로치가 아니다. 자료에 적힌 관장만 (시즌 챔피언 관장: 그 사람이 쓰는 이로치 색 그대로)
        "shiny": bool(entry.get("shiny")), "tint": entry.get("tint") if entry.get("shiny") else None,
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
                self._note_fall(who)            # 다음 턴의 원수갚기가 본다
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
        # 트레이너가 아니라 **마주친 포켓몬**이다 (시즌 4, 악당을 다 물리치고 만나는 전설).
        # 문구만 달라진다: 승부를 걸어오지 않고 나타나고, 이기는 것이 아니라 쓰러뜨린다.
        if trainer.get("wild"):
            self.trainer["wild"] = True
        # 길드전 (시즌 4): 사람이 짠 방어팀을 **센 AI** 가 굴린다 (_war_choice). 자기 키스톤·Z링을 쓴다.
        if trainer.get("ai") == "war":
            self.trainer["ai"] = "war"
        # 관장 탭 카드와 배틀 화면의 그림이 다른 트레이너가 있다 (이스터에그: 렌트라와 함께 / 혼자)
        self.trainer["battleSprite"] = trainer.get("battleSprite") or trainer.get("sprite")
        # 판을 시작할 때 한 번 재생하는 등장 연출 (움직이는 PNG) 과 그 그림에서 발이 닿는 자리 (2.0.3)
        if trainer.get("entrySprite"):
            self.trainer["entrySprite"] = trainer["entrySprite"]
            self.trainer["entryFoot"] = trainer.get("entryFoot")
        self.me_team = [self._fighter(m) for m in my_mons[:TEAM_MAX]]
        self.foe_team = [self._fighter(trainer_mon(e)) for e in trainer["team"][:TEAM_MAX]]
        self.mi = next(i for i, f in enumerate(self.me_team) if f.alive())
        self.fi = 0
        # 메가진화 (시즌 3). 내 키스톤은 서버가 채운다(관장 8곳). 높은 관장은
        # 스톤을 쥐고 알아서 메가진화한다.
        # 악당 출현(시즌 4)의 간부와 전설은 안 받는다 - 간부의 도구는 자료 그대로여야 하고,
        # 마주친 전설이 "키스톤이 반응했다" 며 메가진화하면 안 된다.
        mega_slot = (None if trainer.get("noMega") or trainer.get("wild")
                     else give_mega_stone(dex, self.foe_team, trainer.get("level")))
        self.keystone = {"me": False, "foe": mega_slot is not None}
        self.mega_done = set()
        # Z기술 (시즌 4). 내 Z링은 서버가 채운다. 관장은 쓰지 않는다.
        B.gimmick_init(self)
        if self.war:
            self.keystone["foe"] = bool(trainer.get("keystone"))
            self.zring["foe"] = bool(trainer.get("zring"))
        elif trainer.get("zring"):
            self.zring["foe"] = True           # Z링을 가진 관장 (시즌 챔피언 관장) - 알아서 Z기술을 쓴다
        self._make_duel(FD.Field())
        self.turn = 0
        self.over = False
        self.result = None                     # won / lost / draw / forfeit
        self.need_switch = False
        self.mid = None                 # 턴 도중에 멈춘 자리 (유턴으로 물러나는 중 - _pause 를 보라)
        self.pending_entry = False             # 상대가 내보낸 뒤 특성 발동을 미뤄 둔 상태
        self.foe_switched_last = False
        self.seen = {0}                        # 한 번이라도 나온 상대 자리
        self.started = False
        # 누가 누구를 쓰러뜨렸나. 서버가 경험치를 줄 때 본다 (내 자리가 받는다).
        self.kos = []
        self.war_stall = {}                     # 길드전 새 셈: AI 자리마다 시간 끌기 수(회복 · 방어 …)를 고른 횟수
        self.war_sent = -1                      # 길드전 새 셈: AI 가 쓰러진 포켓몬 대신 다음 포켓몬을 낸 턴
        # 내 포켓몬이 유턴·배턴터치·순간이동으로 물러난다 - 그 기술이 끝나자마자 사람이 고른다 (_pause)
        self.pending_out = None

    # ---------------- 만들기 ----------------
    def _make_duel(self, field):
        self.bt = Duel(self.dex, self.me_team[self.mi], self.foe_team[self.fi], self.rng, ai="trainer",
                       field=field)
        self.bt.teams = {"me": self.me_team, "foe": self.foe_team}    # 집단폭행·치료방울·회생의기도
        self.bt.foe_prefix = "상대 "
        self.bt.max_turns = 10 ** 9            # 끝내는 건 여기서 한다
        self.bt.kind = "gym"
        self.bt.switcher = self._move_switch
        # 같은 객체를 나눠 쓴다 - 불러올 때 판을 새로 만들어도 한 판 한 번이 지켜진다
        self.bt.keystone = self.keystone
        self.bt.mega_done = self.mega_done
        self.bt.auto_mega = {"me": False, "foe": bool(self.keystone.get("foe"))}
        B.gimmick_share(self, self.bt)
        if self.war or self.zring.get("foe"):  # 길드전의 방어 AI · Z링을 가진 관장은 Z기술을 알아서 쓴다
            self.bt.auto_z["foe"] = True

    @property
    def war(self):
        """길드전 방어 AI 인가 (판의 사본으로 수를 셈하는 중에는 그 사본도 같은 AI 다)."""
        return self.trainer.get("ai") == "war"

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
        """상대가 불리할 때 실제로 바꿀 확률. 레벨이 높은 트레이너일수록 크다 (길드전은 늘 바꾼다)."""
        return 1.0 if self.war else 0.35 + 0.55 * self.skill()

    def mistake(self):
        """가장 좋은 수 대신 두 번째 수를 둘 확률 (길드전은 실수하지 않는다)."""
        return 0.0 if self.war else 0.10 * (1.0 - self.skill())

    # ---------------- 시작 ----------------
    def start(self):
        if self.started:
            return []
        self.started = True
        if self.trainer.get("wild"):
            intro = "%s %s 이(가) 모습을 드러냈다!" % (self.trainer.get("role") or "",
                                               self.trainer.get("name") or "")
        else:
            intro = "%s %s 이(가) 승부를 걸어왔다!" % (self.trainer.get("role") or "",
                                               self.trainer.get("name") or "")
        ev = [{"t": "intro", "trainer": self.trainer, "text": intro.strip()}]
        ev.append(self._out_event("foe", self.fi))
        ev.append(self._out_event("me", self.mi))
        self._entry_abilities(ev, fresh=False)
        return ev

    def _out_event(self, who, slot):
        f = (self.foe_team if who == "foe" else self.me_team)[slot]
        if who == "foe":
            text = ("%s 이(가) 앞을 막아섰다!" if self.trainer.get("wild")
                    else "상대는 %s 을(를) 내보냈다!") % f.name
        else:
            text = "가랏! %s!" % f.name
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
                SM.on_enter_abilities(self.bt, f, who, ev)     # 가뭄·잔비·일렉트릭메이커 ...
                if not fresh:
                    f.ab["fresh"] = False

    def _count_down(self, f, who):
        team = self.me_team if who == "me" else self.foe_team
        f.ab["down"] = sum(1 for x in team if not x.alive())

    # ---------------- 교체 ----------------
    def _switch(self, who, slot, ev, trigger=True, fresh=True, carry=None, dragged=False):
        """carry: 배턴터치·꼬리자르기로 넘길 것 (statusmoves.pass_state)."""
        team = self.me_team if who == "me" else self.foe_team
        old = self.me if who == "me" else self.foe
        if old.alive():
            A.on_switch_out(old)
            if dragged:
                ev.append({"t": "recall", "who": who, "text": "%s 은(는) 끌려 나갔다!" % old.name})
            else:
                ev.append({"t": "recall", "who": who,
                           "text": ("%s, 돌아와!" % old.name) if who == "me"
                           else ("상대는 %s 을(를) 불러들였다!" % old.name)})
        SM.on_leave(self.bt, who)               # 상대에게 걸어 둔 헤롱헤롱·검은눈빛이 풀린다
        old.stages = dict((k, 0) for k in B.STAGE_KEYS)
        old.flinched = False
        old.locked = None
        old.clear_volatile()                    # 씨뿌리기·참기·비축·혼란·대타출동 ... 은 물러나면 풀린다
        old.types_override = None
        if who == "me":
            self.mi = slot
            self.bt.me = team[slot]
        else:
            self.fi = slot
            self.bt.foe = team[slot]
            self.seen.add(slot)
        if carry:
            SM.apply_pass(team[slot], carry.get("state"), shed=carry.get("mode") == "shed")
        ev.append(self._out_event(who, slot))
        self.bt.enter(who, ev)                  # 압정·스텔스록·치유소원
        if trigger and team[slot].alive():
            # 턴 사이에 들어온 것(쓰러진 뒤 교체)은 다음 턴 끝에 가속이 붙는다.
            self._entry_abilities(ev, fresh=fresh, only=(who,))

    def _move_switch(self, who, mode, ev, key, state=None):
        """기술이 부른 교체 (Battle.request_switch 가 부른다). 해냈으면 True."""
        team = self.me_team if who == "me" else self.foe_team
        cur = self.mi if who == "me" else self.fi
        others = [i for i, f in enumerate(team) if f.alive() and i != cur]
        if not others:
            return False
        carry = {"mode": mode, "state": state} if mode in ("pass", "shed") else None
        if mode == "drag":
            slot = self.rng.choice(others)
            self._switch(who, slot, ev, carry=None, dragged=True)
            return True
        if who == "foe":
            opp = self.me
            best, best_sc = None, None
            for i in others:
                sc = self._standing(team[i], opp) if opp.alive() else 0
                if best_score_better(sc, best_sc):
                    best, best_sc = i, sc
            self._switch("foe", best, ev, carry=carry)
            self.foe_switched_last = True
            return True
        # 내 포켓몬: 누구를 낼지 사람이 고른다. **그 기술이 끝나자마자 묻는다** (_pause) -
        # 턴은 거기서 멈췄다가, 고른 포켓몬이 나온 뒤에 이어진다.
        self.pending_out = {"mode": mode, "state": state, "key": key}
        ev.append({"t": "msg", "who": "me", "text": "%s 은(는) 돌아갈 준비를 한다!" % self.me.name})
        return True

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
        if not f.held:
            return pool
        # 구애 도구: 처음 쓴 기술만, 아직 안 묶였으면 변화기는 안 고른다 (게시판 #284)
        return H.choice_pool(f, H.lock_pool(f, pool), lambda k: MC.attacks(self.bt.move_of(k)))

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
            # 지금 쓰면 실패하는 기술(잠 안 든 상대에게 꿈먹기), 쓰면 내가 쓰러지는 기술,
            # 다음 턴을 쉬는 기술은 그만큼 낮게 친다 (attackfx.ai_mult).
            am = AF.ai_mult(bt, MC.key(md), md, user, target)
            if d <= 0 or am <= 0:
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
            score *= am
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
        v = AF.status_value(self.bt, MC.key(md), md, user, target, base)
        if v is None:
            v = SM.value(self.bt, MC.key(md), md, user, target, "foe", base)
        if v is not None:
            return v * self._acc(md)
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
        if self.foe_switched_last or SM.trapped(self.bt, self.foe) or SM.must_stay(self.foe):
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

    # ---------------- 길드전 방어 AI (ai="war") ----------------
    # 새 셈 (2026-10-22, design-notes/2026-10-22-guild-war-defense-ai.md): 깔기 · 랭크업 · 교체의 앞으로의 값을
    # 보고 몇 턴 더 내다본다. 끄면(False) 아래의 옛 셈 그대로 - 전쟁 중 문제가 보이면 이것만 끈다.
    WAR_V2 = True
    WAR_REPLY = (0.55, 0.25, 0.20)   # 사람이 할 법한 것의 무게: 가장 아픈 기술 · 둘째 기술 · 가장 나은 교체
    # 지금 나와 있는 상대에게 아무 효과가 없는 공격 기술(타입 무효 · 부유 · 저수 ...)에 매기는 감점 (시즌 5 랭크의 거울 판
    # _RankedWar 만 켠다). 2.0.2 추가, 게시판 #404 나라 - 메가엘레이드(23 HP)가 이미 나와 있는 따라큐에게 인파이트(무효)를
    # 썼다. 다음에 나올 두드리짱의 틀깨기가 탈을 무시해서 한 턴 뒤에는 어느 기술을 썼든 형세가 같았고, 네 기술 점수가 비겨
    # '따라큐가 빠지고 마기라스가 들어오면' 갈래와 사본의 운으로 인파이트가 뽑혔다. 비슷할 때 뒤로 미는 만큼만 (WAR2_PRIOR 와
    # 같은 크기) - 상대 교체를 노려 일부러 쓰는 값이 그보다 크면 그대로 쓴다. 240판: 무효 기술 0.30 -> 0.05/판, 교체 · 턴 ·
    # 지금 AI 와 맞붙여 50.0% 그대로. ('쓰러뜨릴 수 있는 상대는 안 바꾼다' 로 교체 갈래를 빼 보았으나 무효는 거의 그대로에
    # 교체만 판마다 0.5 늘어 뺐다.)
    WAR_NOEFFECT_PEN = 0.0
    WAR_DEPTH = 1                    # 몇 턴 앞까지 굴려 보나 (첫 턴 + 그 뒤를 양쪽 다 무난하게 둔 것)
    WAR_SIM = True                   # 사본으로 셈하나 (끄면 실수 없는 관장 AI 다)
    WAR_BUDGET = 0.5                 # 한 턴에 셈에 쓰는 시간 상한 (초)
    WAR_SEEDS = 2                    # 사람의 수 하나마다 굴려 보는 난수 수
    WAR_PRIOR = 0.3                  # 관장 AI 의 수에 얹어 주는 값 (셈이 이만큼 넘게 나아야 뒤집는다)

    def _rollout(self, turns):
        """사본에서 몇 턴을 더 둔다. 사람 쪽은 가장 아픈 기술(쓰러지면 형세가 가장 나은 포켓몬),
        AI 쪽은 보통 관장 AI 로. 한 수의 값을 그 한 턴이 아니라 그 뒤까지 보고 매기려는 것이다."""
        for _ in range(turns):
            if self.over:
                return
            if self.need_switch:
                opts = self.valid_switches()
                if not opts:
                    return
                self.act("switch", max(opts, key=lambda i: (self._standing(self.me_team[i], self.foe), -i)))
                continue
            lock = SM.locked_move(self.me, self.bt)
            _d, k = self._best(self.me, self.foe)
            k = lock or k or self.bt.usable(self.me)[0]
            try:
                self.act("move", k)
            except ValueError:
                self.act("move", self.bt.usable(self.me)[0])

    # ---- 새 셈 (WAR_V2) ----
    WAR2_DEPTH = 2          # 첫 턴 뒤 양쪽 기본 정책(사람 = 가장 아픈 기술, AI = 관장 AI)으로 더 굴릴 턴 수
    WAR2_SEEDS = 2          # 사람의 수 하나마다 굴려 보는 난수 수
    WAR2_EMERGENCY = 2.0    # 비상 상한 (초). 셈의 양은 고정이고, 이 시간을 넘을 때만 그때까지 본 것 중에서 고른다
    # 값은 tools/war_ai_bench.py 로 맞췄다 (design-notes/bench-log.md, 2026-10-22): 0.15 보다 0.3 이 낫고, 교체를
    # '위험할 때만' 셈하게 막으면 오히려 졌다 (승률 0.465). 깊이 2 는 0 · 1 과 승률이 같으면서 랭크업 7배 · 시간 끌기 절반.
    WAR2_PRIOR = 0.3        # 관장 AI 의 수에 얹는 값
    WAR2_RISK = 0.35        # 최악의 경우를 섞는 비율 (나머지는 평균)
    STALL_FREE = 2          # 한 포켓몬이 감점 없이 쓰는 시간 끌기 수(회복 · 방어 · 대타출동 · 소원 · 잠자기)
    STALL_PEN = 0.3         # 그 뒤로 한 번마다 깎는 값
    STALL_TURN = 40         # 이 턴이 지나면 시간 끌기 수를 더 깎는다
    STALL_LATE = 0.2        # STALL_TURN 뒤 10턴마다
    STALL_EXTRA = ("SUBSTITUTE", "WISH", "REST")
    WAR2_SLOW = 1.0         # 셈이 이보다 오래 걸리면 서버 로그에 남긴다 (초)
    KO_FORCE_THREAT = 0.25  # 상대의 이번 턴 공격이 내 남은 체력의 이만큼 넘을 때만 '확실한 KO' 를 강제한다
    # 바꿔 들어올 포켓몬이 사람의 기술을 남은 체력의 이만큼 넘게 맞으면 교체 후보에서 뺀다 = **들어오면 바로 쓰러질 때만**.
    # 관장 AI 처럼 0.6 으로 했더니 '크게 맞고도 받아내는' 교체까지 막혀 벤치마크가 0.510 -> 0.476 (마진 -0.39) 이었다.
    SAFE_SWITCH_TAKEN = 1.0
    # 쓰러진 포켓몬 대신 막 낸 포켓몬을 바로 다음 턴에 바꾸면 깎는 값 - 그 턴을 상대에게 공짜로 준다
    # (2026-10-22 테스트 플레이 T14: 따라큐를 내보냈다가 바로 토게키스로 바꿨다)
    WAR2_REENTRY_PEN = 0.3

    def _is_stall(self, key):
        """시간을 끄는 수인가 - 상대를 깎지 못하고 버티기만 하는 것."""
        if not key or key == B.STRUGGLE:
            return False
        md = self.bt.move_of(key) or {}
        if MC.attacks(md):
            return False
        return (md.get("heal") or 0) > 0 or key in SM.PROTECTS or key in self.STALL_EXTRA

    def _stall_pen(self):
        n = self.war_stall.get(str(self.fi), 0)
        pen = self.STALL_PEN * max(0, n - self.STALL_FREE + 1)
        if self.turn > self.STALL_TURN:
            pen += self.STALL_LATE * (self.turn - self.STALL_TURN) / 10.0
        return pen

    def _war_choice_v2(self):
        """(바꿀 자리, 쓸 기술) - 새 셈. 관장 AI 의 수(plain)를 먼저 정하고, 사본에서 몇 턴을 굴려 뒤집을지 본다.

        셈 안에서 무엇이 터져도 그 턴은 plain 이다 - act 가 예외로 떨어지면 판이 멈추고 시간이 지나 공격권이 날아간다.
        """
        slot = self._foe_wants_switch()
        plain = ("switch", slot) if slot is not None else ("move", self._foe_move())
        try:
            best = self._war_search(plain)
        except Exception as e:                              # noqa: BLE001
            self._war_log("셈 오류 -> 관장 AI 의 수: %r" % (e,))
            best = plain
        if best[0] == "move" and self._is_stall(best[1]):
            k = str(self.fi)
            self.war_stall[k] = self.war_stall.get(k, 0) + 1
        return (best[1], None) if best[0] == "switch" else (None, best[1])

    def _war_pick(self):
        """쓰러진 포켓몬 대신 낼 자리 - 후보마다 사본에서 내보내고 몇 턴 굴려 _eval_v2 로 고른다 (WAR_V2).

        예전에는 옛 점수(_pick)로 내고 다음 수는 새 셈으로 골라서, 내보낸 포켓몬을 바로 다음 턴에 바꾸는 일이
        있었다 (테스트 플레이 T14). 상대도 같이 쓰러졌을 때는 상대가 무엇을 낼지 몰라 옛 점수를 쓴다(부르는 쪽).
        """
        plain = self._pick(self.foe_team, self.me)
        cands = [i for i, f in enumerate(self.foe_team) if f.alive() and i != self.fi]
        if len(cands) <= 1:
            return plain
        try:
            blob = json.dumps(self.dump())
            seeds = [self.rng.randrange(1 << 30) for _s in range(self.WAR2_SEEDS + 1)]
            best, best_sc = None, None
            for i in cands:
                vals = []
                for seed in seeds:
                    sim = TrainerBattle.load(self.dex, json.loads(blob))
                    sim._sim = True
                    sim.rng.seed(seed)
                    ev = []
                    sim._switch("foe", i, ev, trigger=True, fresh=False)
                    sim.foe_switched_last = False
                    if not sim.foe.alive():                  # 압정에 쓰러졌다
                        sim.bt._check_faint(ev)
                        sim._settle(ev)
                    sim._rollout(1 + self.WAR2_DEPTH)
                    vals.append(sim._eval_v2())
                mean = sum(vals) / float(len(vals))
                sc = (1 - self.WAR2_RISK) * mean + self.WAR2_RISK * min(vals) + (self.WAR2_PRIOR if i == plain else 0.0)
                if best_sc is None or sc > best_sc:
                    best, best_sc = i, sc
            return plain if best is None else best
        except Exception as e:                              # noqa: BLE001
            self._war_log("다음 포켓몬 셈 오류 -> 옛 점수: %r" % (e,))
            return plain

    def _safe_switches(self):
        """바꿔 들어와도 되는 자리 - **사람이 지금 포켓몬에게 쓸 기술을 맞고 들어오자마자 쓰러질 포켓몬은 뺀다**
        (SAFE_SWITCH_TAKEN 배 이상 맞는 것).

        2026-10-22 테스트 플레이 T20: 막 나온 따라큐 62% 를 체력 30% 의 토게키스로 바꿨고, 토게키스는 들어오며
        쓰러졌다. 셈은 '약한 쪽을 버려 센 쪽을 아낀다' 로 보았지만 용의춤 레쿠쟈가 더 빨라 따라큐도 결국 졌다.
        """
        foe, me = self.foe, self.me
        _d, their_k = self._best(me, foe)
        their_md = self.bt.move_of(their_k) if their_k else None
        out = []
        for i, f in enumerate(self.foe_team):
            if not f.alive() or i == self.fi:
                continue
            if their_k and self._est(me, f, their_k) * self._acc(their_md) >= f.hp * self.SAFE_SWITCH_TAKEN:
                continue
            out.append(i)
        return out

    def _secure_ko(self):
        """이번 턴에 확실히 쓰러뜨리는 기술들 - 데미지가 넉넉하고(KO_ROLL), 명중 90% 이상, 먼저 쓰러지지 않는다.

        체력이 가득한 상대의 기합의띠 · 옹골참은 확실하지 않으니 뺀다. **상대가 이번 턴에 내 남은 체력의
        KO_FORCE_THREAT 도 못 깎으면 강제하지 않는다** - 그 앞에서 랭크를 쌓는 것은 공짜다 (셈이 정한다).
        벤치마크에서 늘 강제했더니 승률이 0.528 -> 0.490 으로 내려갔다.
        """
        foe, me = self.foe, self.me
        if not foe.alive() or not me.alive():
            return []
        if me.hp >= me.maxhp and (me.held == "FOCUSSASH" or A.has(me, "STURDY")):
            return []
        their_d, their_k = self._best(me, foe)
        if their_d < foe.hp * self.KO_FORCE_THREAT:
            return []
        their_md = self.bt.move_of(their_k) if their_k else None
        out = []
        for k in self._pool(foe):
            md = self.bt.move_of(k)
            if not md or not MC.attacks(md) or AF.ai_mult(self.bt, MC.key(md), md, foe, me) <= 0:
                continue
            if self._est(foe, me, k) * KO_ROLL < me.hp or self._hit_rate(md, foe, me) < 0.9:
                continue
            if their_k and their_d * KO_ROLL >= foe.hp and not self._first(foe, me, md, their_md):
                continue                                    # 쓰기 전에 내가 쓰러진다
            out.append(k)
        return out

    def _war_search(self, plain):
        """내 수 전부 x 사람의 수(_human_replies) x 시드를 사본에서 (첫 턴 + WAR2_DEPTH 턴) 굴려 _eval_v2 로 잰다."""
        foe = self.foe
        opts = [("move", k) for k in self._pool(foe)]
        if not (self.foe_switched_last or SM.trapped(self.bt, foe) or SM.must_stay(foe)):
            opts += [("switch", i) for i in self._safe_switches()]
        kos = self._secure_ko()
        if kos:
            # **지금 확실히 쓰러뜨릴 수 있으면 쓰러뜨린다** (2026-10-22 테스트 플레이 T19: 체력 1 의 메가레쿠쟈 앞에서
            # 대도각참이 칼춤을 쓰고 한 대를 더 맞았다 - 셈은 다음 턴에 쓰러뜨려도 +2 가 남으니 낫다고 보았다)
            opts = [("move", k) for k in kos]
            if len(opts) == 1:
                return opts[0]
        replies = self._human_replies()
        if len(opts) <= 1 or not replies:
            return opts[0] if kos else plain
        blob, self._war_pre = getattr(self, "_war_pre", None) or json.dumps(self.dump()), None
        seeds = [[self.rng.randrange(1 << 30) for _s in range(self.WAR2_SEEDS)] for _ in replies]
        t0 = time.time()
        deadline = t0 + self.WAR2_EMERGENCY
        stall_pen = self._stall_pen()
        best, best_sc = None, None
        errs, first_err, seen, cut = 0, None, 0, False
        for opt in sorted(opts, key=lambda o: o != plain):        # 관장 AI 의 수부터 (비상 상한이 와도 그것은 본다)
            if time.time() > deadline and best is not None:
                cut = True
                break
            seen += 1
            vals = []
            for (w, kind, value), ss in zip(replies, seeds):
                for seed in ss:
                    sim = TrainerBattle.load(self.dex, json.loads(blob))
                    sim._sim = True
                    sim._forced = opt
                    sim.rng.seed(seed)
                    try:
                        sim.act(kind, value)
                        sim._rollout(self.WAR2_DEPTH)
                        vals.append((w, sim._eval_v2()))
                    except Exception as e:                     # noqa: BLE001  (그 사본은 셈에서 뺀다)
                        errs += 1
                        first_err = first_err or e
            if not vals:
                continue
            mean = sum(w * v for w, v in vals) / sum(w for w, _v in vals)
            sc = (1 - self.WAR2_RISK) * mean + self.WAR2_RISK * min(v for _w, v in vals) + self.rng.random() * 0.01
            if opt == plain:
                sc += self.WAR2_PRIOR
            if opt[0] == "move" and self._is_stall(opt[1]):
                sc -= stall_pen
            if opt[0] == "switch" and self.war_sent == self.turn - 1:
                sc -= self.WAR2_REENTRY_PEN                # 막 낸 포켓몬을 바로 바꾸면 그 턴을 공짜로 준다
            if opt[0] == "switch":
                sc -= self._switch_cost(opt[1])
            if opt[0] == "move" and self.WAR_NOEFFECT_PEN and self._no_effect(opt[1]):
                sc -= self.WAR_NOEFFECT_PEN
            if best_sc is None or sc > best_sc:
                best, best_sc = opt, sc
        took = time.time() - t0
        if errs:
            self._war_log("사본 오류 %d개 (첫 오류 %r)" % (errs, first_err))
        if cut or took > self.WAR2_SLOW:
            self._war_log("셈 %dms (선택지 %d/%d%s)" % (took * 1000, seen, len(opts), ", 비상 상한" if cut else ""))
        return best or plain

    def _switch_cost(self, slot):
        """교체 수에 붙이는 값 - 길드전은 0 (시즌 5 랭크의 거울 판 _RankedWar 만 덮어쓴다)."""
        return 0.0

    def _no_effect(self, key):
        """이 공격 기술이 지금 나와 있는 상대에게 아무 효과가 없나 (타입 무효 · 막는 특성). 변화기는 아니다."""
        md = self.bt.move_of(key)
        if not md or not MC.attacks(md):
            return False
        if A.would_block(self.foe, self.me, md):
            return True
        _d, _crit, eff = B.damage(self.dex, md, self.foe, self.me, B.EST_RNG, crit=False)
        return eff == 0

    def _war_log(self, text):
        """서버 로그(docker logs)에 한 줄 - 전쟁 중 새 셈을 되돌릴지 정할 근거 (2026-10-22 사용자 결정)."""
        try:
            sys.stderr.write("[길드전 AI] %s T%d 자리 %s: %s\n" % (self.trainer.get("id"), self.turn, self.fi, text))
            sys.stderr.flush()
        except Exception:                                   # noqa: BLE001
            pass

    def _war_choice(self):
        """(바꿀 자리, 쓸 기술) - 한 턴을 **판의 사본으로 미리 돌려 보고** 고른다.

        내가 할 수 있는 것(쓸 수 있는 기술 전부, 바꿀 수 있는 자리 전부) x 사람이 할 법한 것(가장 아픈
        기술 둘, 가장 나은 교체)을 사본에서 한 턴씩 돌려, 끝난 뒤의 형세(_eval)를 잰다. 사람의 수마다
        같은 난수를 써서 내 수끼리 공평하게 견준다. 평균과 최악을 섞어 고른다 - 한 수만 노리다 크게
        지는 수를 피한다. 작은 흔들림을 섞어 같은 판에서 늘 같은 수를 두지 않는다 (외워서 이기지 못하게).
        """
        if self.WAR_V2:
            return self._war_choice_v2()
        foe = self.foe
        # 먼저 실수 없는 관장 AI 의 수를 정해 둔다. 셈은 이것을 **뒤집을 만큼 뚜렷할 때만** 뒤집는다
        # (WAR_PRIOR) - 사본 몇 판의 난수에 휘둘려 좋은 수를 버리지 않게.
        slot = self._foe_wants_switch()
        plain = ("switch", slot) if slot is not None else ("move", self._foe_move())
        opts = [("move", k) for k in self._pool(foe)]
        if not (self.foe_switched_last or SM.trapped(self.bt, foe) or SM.must_stay(foe)):
            opts += [("switch", i) for i, f in enumerate(self.foe_team) if f.alive() and i != self.fi]
        replies = self._human_replies() if self.WAR_SIM else []
        best, best_sc = None, None
        if len(opts) > 1 and replies:
            blob = json.dumps(self.dump())
            seeds = [[self.rng.randrange(1 << 30) for _s in range(self.WAR_SEEDS)] for _ in replies]
            deadline = time.time() + self.WAR_BUDGET
            for opt in sorted(opts, key=lambda o: o != plain):    # 관장 AI 의 수부터 (시간이 모자라도 그것은 본다)
                if time.time() > deadline and best is not None:
                    break                                      # 셈이 길어졌다 - 지금까지 본 것 가운데 고른다
                vals = []
                for (w, kind, value), ss in zip(replies, seeds):
                    for seed in ss:
                        sim = TrainerBattle.load(self.dex, json.loads(blob))
                        sim._sim = True
                        sim._forced = opt
                        sim.rng.seed(seed)
                        try:
                            sim.act(kind, value)
                            sim._rollout(self.WAR_DEPTH - 1)
                        except Exception:                      # noqa: BLE001  (그 수는 셈에서 뺀다)
                            continue
                        vals.append((w, sim._eval()))
                if not vals:
                    continue
                mean = sum(w * v for w, v in vals) / sum(w for w, _v in vals)
                sc = 0.65 * mean + 0.35 * min(v for _w, v in vals) + self.rng.random() * 0.01
                if opt == plain:
                    sc += self.WAR_PRIOR
                if best_sc is None or sc > best_sc:
                    best, best_sc = opt, sc
        best = best or plain
        return (best[1], None) if best[0] == "switch" else (None, best[1])

    def _human_replies(self):
        """사람이 이번 턴에 할 법한 것: [(무게, 'move'/'switch', 값)]."""
        me, foe = self.me, self.foe
        if not me.alive() or not foe.alive():
            return []
        lock = SM.locked_move(me, self.bt)
        if lock:
            return [(1.0, "move", lock)]
        moves = []
        for k in self.bt.usable(me):
            if k != B.STRUGGLE and SM.restricted(self.bt, me, k):
                continue
            moves.append((self._est(me, foe, k) * self._hit_rate(self.bt.move_of(k), me, foe), k))
        moves.sort(key=lambda x: (-x[0], x[1]))
        out = [(w, "move", k) for w, (_d, k) in zip(self.WAR_REPLY[:2], moves)]
        if not (SM.trapped(self.bt, me) or SM.must_stay(me)):
            sw = [(self._standing(f, foe), i) for i, f in enumerate(self.me_team) if f.alive() and i != self.mi]
            if sw:
                out.append((self.WAR_REPLY[2], "switch", max(sw)[1]))
        return out

    def _eval(self):
        """이 판을 상대(AI) 쪽에서 본 값. 클수록 AI 에게 좋다.

        살아 있는 포켓몬 한 마리에 0.5 + 남은 체력 비율. 나와 있는 둘의 랭크(±2 까지)와 상태이상을 조금.
        """
        if self.over:
            return 100.0 if self.result in ("lost", "forfeit") else (-100.0 if self.result == "won" else 0.0)

        def side(team):
            return sum(0.5 + f.hp / float(f.maxhp or 1) for f in team if f.alive())
        v = side(self.foe_team) - side(self.me_team)
        for f, sign in ((self.foe, 1.0), (self.me, -1.0)):
            if not f.alive():
                continue
            v += sign * 0.05 * sum(max(-2, min(2, f.stages.get(k, 0))) for k in ("atk", "def", "spa", "spd", "spe"))
            if f.status:
                v -= sign * 0.12
        return v

    # ---- 새 형세 평가 (WAR_V2) - 단위는 옛 _eval 과 같다: 한 마리 = 0.5 + 체력 비율 ----
    HAZARD_W = 1.5       # 깔기가 앞으로 깎을 체력 비율 합에 곱한다 (벤치마크로 1.0 · 1.5 중 1.5)
    STAGE_W = 0.35       # 실제로 쓰는 공격 능력 · 맞을 쪽 방어의 랭크 (1 - 0.75^단계 만큼)
    SPEED_FLIP_W = 0.25  # 랭크 · 마비로 스피드가 뒤집힌 값
    SIDE_W = 0.03        # 벽 · 순풍의 남은 한 턴

    def _hazard_toll(self, who):
        """who 진영에 깔린 것이 그 진영의 **아직 안 나온** 포켓몬에게 앞으로 줄 손해 (체력 비율의 합)."""
        side = self.bt.field.side(who)
        if not any(side.get(h) for h in FD.HAZARDS):
            return 0.0
        team, cur = (self.me_team, self.me) if who == "me" else (self.foe_team, self.foe)
        total = 0.0
        for f in team:
            if f is cur or not f.alive() or H.no_hazards(f):
                continue
            magic = A.has(f, "MAGICGUARD")
            ground = SM.grounded(f)
            types = f.types()
            loss = 0.0
            if side.get("stealthrock") and not magic:
                loss += self.dex.effectiveness("ROCK", types) / 8.0
            if side.get("spikes") and ground and not magic:
                loss += 1.0 / {1: 8, 2: 6, 3: 4}[min(3, int(side["spikes"]))]
            if side.get("toxicspikes") and ground and not f.status and "POISON" not in types and "STEEL" not in types:
                loss += 0.25 if int(side["toxicspikes"]) >= 2 else 0.15
            if side.get("stickyweb") and ground:
                loss += 0.05
            total += min(loss, f.hp / float(f.maxhp or 1))
        return total

    def _attack_kinds(self, f):
        """(물리 공격기가 있나, 특수 공격기가 있나)"""
        phys = spec = False
        for k in f.moves:
            md = self.bt.move_of(k) or {}
            if MC.attacks(md):
                phys = phys or md.get("cat") == "physical"
                spec = spec or md.get("cat") == "special"
        return phys, spec

    def _stage_value(self, f, opp):
        """f 의 랭크가 f 쪽에 주는 값."""
        if not f.alive() or not opp.alive():
            return 0.0
        phys, spec = self._attack_kinds(f)
        o_phys, o_spec = self._attack_kinds(opp)

        def curve(s):
            return (1.0 - 0.75 ** abs(s)) * (1 if s > 0 else -1) if s else 0.0
        st = f.stages
        v = curve(st.get("atk", 0)) * (1.0 if phys else 0.1) + curve(st.get("spa", 0)) * (1.0 if spec else 0.1)
        v += 0.6 * (curve(st.get("def", 0)) * (1.0 if o_phys else 0.2) + curve(st.get("spd", 0)) * (1.0 if o_spec else 0.2))
        v *= self.STAGE_W
        mine, theirs = f.stat("spe"), opp.stat("spe")
        plain = f.stat("spe", stages=False)
        if (mine > theirs) != (plain > theirs):         # 랭크로 스피드가 뒤집혔다
            v += self.SPEED_FLIP_W if mine > theirs else -self.SPEED_FLIP_W
        return v

    def _status_value_of(self, f, opp):
        """f 에게 걸린 상태이상이 f 쪽에 주는 손해 (0 이상)."""
        if not f.alive() or not f.status:
            return 0.0
        if A.has(f, "GUTS", "MARVELSCALE", "QUICKFEET", "MAGICGUARD", "POISONHEAL"):
            return 0.0
        phys, spec = self._attack_kinds(f)
        s = f.status
        if s == "burn":
            return 0.35 if phys and not spec else (0.2 if phys else 0.08)
        if s == "paralysis":
            fast = f.stat("spe", stages=True) * 2 > opp.stat("spe")       # 마비 전에는 더 빨랐나
            return 0.12 + (self.SPEED_FLIP_W if fast and f.stat("spe") <= opp.stat("spe") else 0.0)
        if s == "poison":
            return 0.2 if f.cond.get("toxic") else 0.12
        if s in ("sleep", "freeze"):
            return 0.35
        return 0.12

    def _eval_v2(self):
        """이 판을 AI(방어) 쪽에서 본 값. 클수록 AI 에게 좋다 (WAR_V2).

        옛 _eval + 깔기가 앞으로 깎을 체력 · 실제로 쓰는 능력의 랭크(±6, 올라갈수록 덜) · 스피드 역전 ·
        상태이상의 종류와 상대 · 벽 · 순풍. **무승부는 진 것과 같다** - 400턴을 끌어 무승부로 칸을 지키지 않게.
        """
        if self.over:
            if self.result in ("lost", "forfeit"):
                return 100.0
            if self.result == "draw" and self.turn < MAX_TURNS:
                return 90.0                 # 마지막끼리 같이 쓰러졌다 - 길드전에서 무승부는 칸을 지킨다 (defends)
            return -100.0                   # 진 판 · 400턴 무승부 (시간 끌기로 노리지 않게)

        def side(team):
            return sum(0.5 + f.hp / float(f.maxhp or 1) for f in team if f.alive())
        v = side(self.foe_team) - side(self.me_team)
        v += self.HAZARD_W * (self._hazard_toll("me") - self._hazard_toll("foe"))
        v += self._stage_value(self.foe, self.me) - self._stage_value(self.me, self.foe)
        # 상태이상은 **벤치에 있는 것까지** - 나와 있는 둘만 보면 걸린 포켓몬을 교체해 넣기만 해도 값이 올라
        # 쓸데없는 교체를 부추긴다 (검토 지적)
        v += sum(self._status_value_of(f, self.foe) for f in self.me_team) \
            - sum(self._status_value_of(f, self.me) for f in self.foe_team)
        for who, sign in (("foe", 1.0), ("me", -1.0)):
            sd = self.bt.field.side(who)
            for k in ("reflect", "lightscreen", "auroraveil", "tailwind"):
                v += sign * self.SIDE_W * int(sd.get(k) or 0)
        return v

    # ---------------- 한 턴 ----------------
    def valid_switches(self):
        return [i for i, f in enumerate(self.me_team) if f.alive() and i != self.mi]

    def act(self, kind, value=None, mega=False, z=False):
        """kind: 'move' (value=기술) / 'switch' (value=자리) / 'forfeit'

        mega: 이 턴에 메가진화한다 (기술을 고를 때만. 교체하면서는 못 한다).
        z: 고른 기술을 Z기술로 쓴다 (시즌 4, 기술을 고를 때만).
        """
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
            out, self.pending_out = self.pending_out, None
            carry = {"mode": out["mode"], "state": out.get("state")} if out and out["mode"] in ("pass", "shed") else None
            mid, self.mid = self.mid, None
            self._switch("me", value, ev, trigger=not self.pending_entry, fresh=False, carry=carry)
            if self.pending_entry:
                self.pending_entry = False
                self._entry_abilities(ev, fresh=False)
            if mid:
                # 유턴·볼트체인지로 턴 도중에 물러났다. 남은 차례(상대의 기술)와 턴 끝을 마저 돈다.
                self._wake(mid)
                if not self.me.alive():             # 나오자마자 압정에 쓰러졌다
                    self.bt._check_faint(ev)
                if self._run(mid["order"], mid["moves"], mid["actors"], ev):
                    return ev                       # 또 멈췄다 (나온 포켓몬이 위기회피로 물러난다)
                return self._end_turn(ev)
            if not self.me.alive():                 # 압정에 쓰러졌다
                self.bt._check_faint(ev)
                self._settle(ev)
            return ev

        if kind == "switch" and value not in self.valid_switches():
            raise ValueError("그 포켓몬으로는 바꿀 수 없습니다.")
        if kind == "switch" and SM.trapped(self.bt, self.me):
            raise ValueError("%s 은(는) 붙잡혀 있어서 교체할 수 없습니다." % self.me.name)
        if kind == "switch" and SM.must_stay(self.me):
            raise ValueError(SM.must_stay(self.me))     # 반동 턴·날뛰는 중·모으는 중
        if kind == "move":
            # 역린류·2턴 기술로 잠겨 있으면 그것으로 바꿔 받는다 (거절하지 않는다)
            value = SM.locked_move(self.me, self.bt) or value
        if kind == "move" and value and value != B.STRUGGLE:
            why = SM.restricted(self.bt, self.me, value)
            enc = self.me.cond.get("encore")
            if why and not (enc and enc.get("move") == value):
                raise ValueError(why)

        if self.war and self.WAR_V2 and not getattr(self, "_sim", False):
            # 길드전 새 셈은 **이번 턴을 열기 전의 판**에서 사본을 뜬다. 연 뒤에 뜨면 사본의 act 가 턴을 또 열어서
            # (나온 뒤 턴 수 · 시계가 둘씩 감) 나오자마자 쓰는 속이기 · 만나자마자가 사본에서는 늘 실패했다.
            self._war_pre = json.dumps(self.dump())
        self.turn += 1
        self.bt.turn_no = self.turn
        bt = self.bt
        bt.begin_turn()
        me_move = None
        foe_move = None

        # 상대가 무엇을 할지 먼저 정한다 (내 선택을 보지 않는다)
        forced, self._forced = getattr(self, "_forced", None), None
        if forced is not None:                 # 수를 셈하는 사본: 셈하려는 수를 그대로 둔다
            foe_slot = forced[1] if forced[0] == "switch" else None
            foe_move = forced[1] if forced[0] == "move" else None
        elif self.war and not getattr(self, "_sim", False):
            foe_slot, foe_move = self._war_choice()
        else:
            foe_slot = self._foe_wants_switch()
            if foe_slot is None:
                foe_move = self._foe_move()

        if kind == "switch":
            self._switch("me", value, ev)
            if not self.me.alive():
                self.bt._check_faint(ev)
        else:
            me = self.me
            me_move = value
            if me_move != B.STRUGGLE and (me_move not in me.pp or me.pp.get(me_move, 0) <= 0):
                me_move = bt.usable(me)[0]
            if me.held:
                me_move = H.force_move(me, me_move, ev, "me", bt)

        if foe_slot is not None:
            self._switch("foe", foe_slot, ev)
            self.foe_switched_last = True
        else:
            self.foe_switched_last = False

        # 메가진화 (시즌 3): 둘 다 고른 뒤, 순서를 정하기 전에. 교체한 쪽은 못 한다.
        bt.auto_mega["foe"] = bool(self.keystone.get("foe")) and foe_slot is None
        bt.mega_step({"me": bool(mega) and kind == "move"}, ev)
        bt.z_request("me", me_move, bool(z) and kind == "move")
        bt._auto_z("foe", foe_move)            # 길드전 방어 AI 만 켜져 있다 (관장은 auto_z 가 꺼져 있다)

        me, foe = self.me, self.foe
        me.flinched = False
        foe.flinched = False
        # 이 턴에 누가 무엇을 하려는지 (교체한 쪽은 None) - 기습·질풍신뢰가 본다
        bt.pending = {"me": me_move, "foe": foe_move}
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

        # 이 턴에 움직일 자리. 턴 도중에 바뀐 포켓몬(끌려 나왔거나 물러난 뒤 나온)은 안 움직인다.
        actors = {"me": self.mi, "foe": self.fi}
        if self._run(order, {"me": me_move, "foe": foe_move}, actors, ev):
            return ev                           # 교체할 포켓몬을 고르는 동안 턴이 멈췄다
        return self._end_turn(ev)

    def _run(self, order, moves, actors, ev):
        """남은 차례를 돈다. **사람이 고를 교체가 걸리면 거기서 멈춘다** (True).

        유턴·볼트체인지·퀵턴·배턴터치·막말내뱉기·순간이동은 쓰자마자 물러나는 기술이다 (1.10.4).
        예전에는 턴이 다 끝난 뒤에 물었다 - 그래서 물러나려던 포켓몬이 상대의 기술을 그대로 맞고,
        턴 끝의 독·날씨 피해까지 받고 나서야 바뀌었다. 원작에서는 나온 포켓몬이 대신 맞는다.
        """
        bt = self.bt
        order = list(order)
        while order:
            who = order.pop(0)
            user, target = (self.me, self.foe) if who == "me" else (self.foe, self.me)
            if (self.mi if who == "me" else self.fi) != actors[who]:
                continue                        # 이번 턴에 끌려 나온 포켓몬은 움직이지 않는다
            if not user.alive() or not target.alive():
                continue
            bt._use(who, user, target, moves[who], ev)
            if not self.foe.alive() and not any(k["foe"] == self.fi for k in self.kos):
                self.kos.append({"foe": self.fi, "by": self.mi, "turn": self.turn})
            if self._pause(order, moves, actors, ev):
                return True
        return False

    def _pause(self, order, moves, actors, ev):
        """내 포켓몬이 물러나기로 했으면 턴을 여기서 멈추고 누구를 낼지 묻는다. 멈췄으면 True.

        상대가 다 쓰러졌으면 안 멈춘다 - 판이 끝난다 (턴 끝 정리가 한다).
        """
        if not self.pending_out or self.over:
            return False
        if not (self.me.alive() and self.valid_switches()):
            self.pending_out = None
            return False
        if not any(f.alive() for f in self.foe_team):
            self.pending_out = None
            return False
        bt = self.bt
        self.need_switch = True
        # 저장했다 깨어나도 턴이 이어지게, 이 턴에만 있는 것들을 같이 적어 둔다.
        self.mid = {"order": list(order), "moves": dict(moves), "actors": dict(actors),
                    "pending": dict(bt.pending or {}), "acted": sorted(bt.acted or ()),
                    "flinched": {"me": bool(self.me.flinched), "foe": bool(self.foe.flinched)},
                    "second": {"me": bool(self.me.moved_second), "foe": bool(self.foe.moved_second)},
                    "hurt": {"me": self.me.hurt, "foe": self.foe.hurt}}
        ev.append({"t": "choose", "who": "me", "text": "교체할 포켓몬을 고르세요."})
        return True

    def _wake(self, mid):
        """멈췄던 턴의 사정을 되살린다. 새로 나온 내 포켓몬은 이 턴에 아무것도 안 했다."""
        bt = self.bt
        bt.pending = dict(mid.get("pending") or {})
        bt.pending["me"] = None                  # 나온 포켓몬은 이 턴에 기술을 안 쓴다 (기습이 본다)
        bt.acted = set(mid.get("acted") or ())
        if self.fi == (mid.get("actors") or {}).get("foe"):
            self.foe.flinched = bool((mid.get("flinched") or {}).get("foe"))
            self.foe.moved_second = bool((mid.get("second") or {}).get("foe"))
            self.foe.hurt = (mid.get("hurt") or {}).get("foe")

    def _end_turn(self, ev):
        """턴 끝: 독·날씨 같은 것, 쓰러진 쪽 정리, 턴 수 제한."""
        bt = self.bt
        # 마지막끼리 쓰러뜨린 턴에도 턴 끝이 돈다 - 이긴 쪽이 화상 · 독 데미지로 같이 쓰러지면 무승부. 본가와 다르지만
        # **시즌 중에 판정을 바꾸지 않는다** (랭크 · 길드전 형평성, 2026-10-20 사용자 결정 - 1.13.3 에서 고쳤다가 되돌림).
        if self.me.alive() or self.foe.alive():
            bt._end_of_turn(ev)
        bt._check_faint(ev)
        if not self.foe.alive() and not any(k["foe"] == self.fi for k in self.kos):
            self.kos.append({"foe": self.fi, "by": self.mi, "turn": self.turn})
        self._settle(ev)
        if self.pending_out and not self.over and not self.need_switch:
            # 턴 끝의 피해로 물러나게 됐다 (위기회피). 턴은 이미 끝났으니 고르기만 하면 된다.
            if self.me.alive() and self.valid_switches():
                self.need_switch = True
                ev.append({"t": "choose", "who": "me", "text": "교체할 포켓몬을 고르세요."})
            else:
                self.pending_out = None
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
            if self.war and self.WAR_V2 and not me_down and not getattr(self, "_sim", False):
                nxt = self._war_pick()
                self.war_sent = self.turn
            else:
                nxt = self._pick(self.foe_team, self.me)
            # 나도 쓰러져서 곧 바꿀 거면, 상대의 등장 특성은 내가 고른 뒤에
            self._switch("foe", nxt, ev, trigger=not me_down, fresh=False)
            if me_down:
                self.pending_entry = True
            self.foe_switched_last = False
            if not self.foe.alive():                # 압정에 쓰러졌다 - 다음을 또 낸다
                self.bt._check_faint(ev)
                return self._settle(ev)
        if me_down:
            self.need_switch = True
            self.pending_out = None
            ev.append({"t": "choose", "who": "me", "text": "다음 포켓몬을 고르세요."})

    def _finish(self, result, ev):
        self.over = True
        self.result = result
        text = {"won": ("%s 을(를) 쓰러뜨렸다!" if self.trainer.get("wild")
                        else "%s 과(와)의 승부에서 이겼다!") % self.trainer.get("name"),
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
            # 변신(메타몽)한 동안은 상대의 모습 번호 (statusmoves.h_transform 의 cond["look"])
            "species": f.mon["species"], "num": f.cond.get("look") or sp.get("num"), "name": f.name,
            "level": f.level, "hp": f.hp, "maxhp": f.maxhp,
            "status": f.status, "statusKr": B.STATUS_KR.get(f.status),
            "gender": f.mon.get("gender"), "shiny": bool(f.mon.get("shiny")),
            # 이로치가 고른 색 (1.8.0, common/tint). 없으면 None.
            "tint": f.mon.get("tint") if f.mon.get("shiny") else None,
            "types": [dex.type_name(t) for t in f.types()], "typeIds": f.types(),
            "stages": dict((k, v) for k, v in f.stages.items() if v),
            "fainted": not f.alive(),
            "mega": bool(f.mega),
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
                t = B.shown_type(md, f)            # 가면·플레이트로 바뀐 타입 (게시판 #259)
                moves.append({"key": m, "kr": dex.move_name(m), "type": t,
                              "typeKr": dex.type_name(t), "cat": md.get("cat"),
                              "power": md.get("power"), "acc": md.get("acc"),
                              "pp": f.pp.get(m, 0), "maxpp": md.get("pp", 0),
                              "desc": md.get("desc", ""),
                              "blocked": SM.restricted(self.bt, f, m) if f is self.me else None})
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
            # 메가진화 단추를 띄울지 (키스톤·스톤·한 판 한 번을 다 본 값)
            "canMega": bool(not self.over and not self.need_switch
                            and self.bt.can_mega("me")),
            "megaUsed": "me" in self.mega_done,
            "me": {"slot": self.mi, "team": [self.side(f, True) for f in self.me_team]},
            "foe": {"slot": self.fi, "team": foe_team},
            # Z기술 단추 (시즌 4): zMoves(무엇이 되는지)·zUsed
            "gimmick": B.gimmick_view(self.bt, "me", not self.over and not self.need_switch),
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
        # 메가를 다시 입히는 일(load_volatile)이 먼저다. 메가진화는 특성·타입을 그 폼의
        # 것으로 되돌리므로, 뒤에 하면 그 뒤에 바뀐 것(변환자재의 타입, 미라)이 지워진다.
        f.load_volatile(d.get("vol"))
        A.load(f, d.get("abil"))
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
            "field": self.bt.field.dump(), "pendingOut": self.pending_out, "mid": self.mid,
            "keystone": dict(self.keystone), "megaDone": sorted(self.mega_done),
            "gimmick": B.gimmick_dump(self),
            "warStall": dict(self.war_stall), "warSent": self.war_sent,
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
        self.keystone = dict(d.get("keystone") or {"me": False, "foe": False})
        self.mega_done = set(d.get("megaDone") or [])
        B.gimmick_load(self, d.get("gimmick"))
        self._make_duel(FD.Field.load(d.get("field")))
        self.pending_out = d.get("pendingOut")
        self.mid = d.get("mid")
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
        self.war_stall = dict(d.get("warStall") or {})
        self.war_sent = int(d.get("warSent", -1))
        return self
