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
    상대가 고른 것    기술, 가끔 교체 (높은 레벨일수록 머리를 쓴다)

    1. 교체가 먼저 일어난다 (내 쪽 -> 상대 쪽)
    2. 남은 기술들을 우선도·스피드 순으로 쓴다
    3. 턴 끝 처리 (화상·독·먹다남은음식·가속 ...)
    4. 쓰러진 쪽 정리
         상대가 쓰러지면 상대는 **바로** 다음을 내보낸다
         내가 쓰러지면 **다음 입력은 교체만** 받는다 (need_switch)

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

TEAM_MAX = 6
MAX_TURNS = 400
SWITCH_MARGIN = 1.5
STATS = ("hp", "atk", "def", "spa", "spd", "spe")


def trainer_mon(entry):
    """gyms.json 의 한 줄 -> Fighter 가 먹는 mon."""
    iv = int(entry.get("iv", 31))
    ev = int(entry.get("ev", 0))
    return {
        "species": entry["species"], "level": int(entry["level"]),
        "ivs": dict((s, iv) for s in STATS), "evs": dict((s, ev) for s in STATS),
        "nature": entry.get("nature") or "HARDY", "ability": entry.get("ability"),
        "moves": list(entry.get("moves") or []), "held": entry.get("held"),
        "gender": entry.get("gender") or "N", "shiny": False, "nickname": None,
        "statBoost": entry.get("boost"),
    }


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

    def smartness(self):
        """상대 AI 가 불리할 때 바꿀 확률. 레벨이 높은 트레이너일수록 크다."""
        lv = int(self.trainer.get("level") or 50)
        return 0.15 + max(0, min(80, lv - 20)) / 80.0 * 0.35

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

    def _matchup(self, mine, foe):
        """party_battle._matchup 과 같은 셈. 특성으로 무효가 되는 것까지 본다."""
        foe_types = foe.types()
        my_types = mine.types()
        atk = 0.0
        for key in mine.moves:
            md = self.dex.move(key) or {}
            if not md.get("power") or A.would_block(mine, foe, md):
                continue
            atk = max(atk, B.effectiveness(self.dex, A.move_type(mine, md), foe_types))
        dfn = 0.0
        for key in foe.moves:
            md = self.dex.move(key) or {}
            if not md.get("power") or A.would_block(foe, mine, md):
                continue
            dfn = max(dfn, B.effectiveness(self.dex, A.move_type(foe, md), my_types))
        atk = atk or 0.25
        dfn = dfn or 0.25
        health = 0.6 + 0.4 * (mine.hp / float(mine.maxhp or 1))
        return (atk / dfn) * health

    def _pick(self, team, against, cur=None):
        best, best_score = None, None
        for i, f in enumerate(team):
            if not f.alive():
                continue
            sc = self._matchup(f, against)
            if cur is not None and i == cur:
                sc *= SWITCH_MARGIN
            if best_score is None or sc > best_score:
                best, best_score = i, sc
        return best

    def _foe_wants_switch(self):
        """상대가 이번 턴에 바꾸고 싶은 자리. 안 바꾸면 None."""
        if self.foe_switched_last:
            return None
        others = [i for i, f in enumerate(self.foe_team) if f.alive() and i != self.fi]
        if not others:
            return None
        cur = self._matchup(self.foe, self.me)
        best = self._pick(self.foe_team, self.me, cur=self.fi)
        if best is None or best == self.fi:
            return None
        if self._matchup(self.foe_team[best], self.me) < cur * 2.0:
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
        me_move = None
        foe_move = None

        # 상대가 무엇을 할지 먼저 정한다 (내 선택을 보지 않는다)
        foe_slot = self._foe_wants_switch()
        if foe_slot is None:
            foe_move = bt.choose_for(self.foe, self.me, "trainer")

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
                "abil": A.state(f)}

    def _load_fighter(self, d):
        f = B.Fighter(self.dex, d["mon"], d["hp"], d["pp"], d["status"])
        f.stages = d.get("stages") or f.stages
        f.sleep_turns = d.get("sleep", 0)
        f.load_held(d.get("held"))
        f.ability_on = True
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
