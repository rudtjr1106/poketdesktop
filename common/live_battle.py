# -*- coding: utf-8 -*-
"""실시간 1:1 배틀 — **양쪽 다 사람이 고른다.**

지금까지 유저 배틀(party_battle)은 매칭 순간 서버가 판 전체를 돌려 로그로
남기고 양쪽은 그걸 재생만 했다. 사람이 개입할 자리가 없었다. 여기서는
**둘이 동시에 고르고, 둘 다 들어오면 그 턴이 진행된다.**

레이드(raid_battle)와 같은 틀이다 - 서버에 따로 도는 시계가 없으므로
'고른 것을 적어 두고, 다 모이면 그 자리에서 한 턴을 돈다'. 다른 점은
사람이 둘뿐이고 양쪽 다 사람이라는 것이다.

## 한 턴

    1. 둘 다 고른다 (기술 / 교체 / 기권). 제한 시간을 넘긴 쪽은 서버가
       대신 고른다 (auto_choice - 지금 가장 센 기술).
    2. 교체가 먼저(a -> b), 그다음 기술을 우선도·스피드 순으로.
    3. 턴 끝 (화상·날씨·먹다남은음식 ...)
    4. 쓰러졌거나 유턴으로 물러난 쪽은 **그 자리에서 다음을 고른다**
       (phase="switch"). 상대는 기다린다. 본가와 같다.

## 시점

엔진은 **늘 a 쪽 기준**으로 돈다 (bt.me = a, bt.foe = b). b 에게 줄 때는
party_battle.flip 으로 한 번 뒤집는다 - 이미 유저 배틀 재생에서 쓰고 있는
것이라 이벤트 종류가 늘어도 같이 따라온다.

## 저장

관장·레이드와 같다. 턴마다 DB 에 통째로 자고 다음 요청에서 깬다. 난수
상태까지 남기므로 같은 턴을 다시 보내 결과를 골라 먹을 수 없다.

## 챔피언로드

여기서 다루는 것은 '두 사람이 한 판을 실시간으로 둔다' 뿐이다. 누가
누구와 붙는지, 무엇을 걸고 붙는지는 서버(app/live.py)가 정한다. 나중에
챔피언로드가 같은 엔진 위에 다른 규칙을 얹을 수 있게 하려는 것이다.
"""
import random

from . import abilities as A
from . import battle as B
from . import field as FD
from . import held as H
from . import movecalc as MC
from . import pokelogic as P
from . import statusmoves as SM
from .party_battle import flip_log

TEAM_MAX = 6
STATS = ("hp", "atk", "def", "spa", "spd", "spe")
# 이 턴을 넘기면 남은 머릿수로 판정한다. 사람이 두는 판이라 관장(400)보다
# 짧게 둔다 - 서로 회복기만 쓰면 끝이 안 난다.
MAX_TURNS = 150

# 이 판에서 쓸 레벨. 양쪽 다 여기에 맞춘다 (높으면 내리고 낮으면 올린다).
LEVEL = 50


def leveled(mon, level=LEVEL):
    """레벨만 맞춘 사본. 개체값·노력치·성격·도구·기술은 그대로."""
    return P.at_level(mon, level)


class LiveDuel(B.Battle):
    """쓰러져도 판을 안 끝내는 Battle. 끝내는 건 LiveBattle 이 한다."""

    def _check_faint(self, ev):
        for who, f in (("foe", self.foe), ("me", self.me)):
            if not f.alive() and not f.ab.get("fainted"):
                f.ab["fainted"] = True
                prefix = self.foe_prefix if who == "foe" else ""
                ev.append({"t": "faint", "who": who,
                           "text": "%s%s 은(는) 쓰러졌다!" % (prefix, f.name)})


class Player(object):
    """판에 앉은 사람 하나."""

    def __init__(self, uid, name, team):
        self.uid = int(uid)
        self.name = name or "?"
        self.team = team
        self.slot = next((i for i, f in enumerate(team) if f.alive()), 0)
        self.choice = None              # 이번 턴에 할 것
        self.need_switch = False        # 다음 포켓몬을 골라야 한다
        self.pending_out = None         # 유턴·배턴터치로 물러나는 중
        self.forfeited = False
        self.auto = 0                   # 서버가 대신 고른 횟수

    @property
    def mon(self):
        return self.team[self.slot]

    def alive_slots(self):
        return [i for i, f in enumerate(self.team) if f.alive()]

    def wiped(self):
        return not self.alive_slots()

    def playing(self):
        return not self.forfeited and not self.wiped()


class LiveBattle(object):

    def __init__(self, dex, a, b, rng=None, max_turns=MAX_TURNS):
        """a, b: (uid, 이름, [mon ...]). mon 은 이미 레벨을 맞춘 것."""
        self.dex = dex
        self.rng = rng or random.Random()
        self.max_turns = int(max_turns)
        self.a = Player(a[0], a[1], [self._fighter(m) for m in a[2][:TEAM_MAX]])
        self.b = Player(b[0], b[1], [self._fighter(m) for m in b[2][:TEAM_MAX]])
        if not self.a.team or not self.b.team:
            raise ValueError("양쪽 다 포켓몬이 있어야 합니다.")
        self.field = FD.Field()
        self._wire()
        self.turn = 0
        self.over = False
        self.result = None              # "a" / "b" / "draw"
        self.reason = None              # ko / forfeit / turns
        self.started = False

    # ---------------- 만들기 ----------------
    def _fighter(self, mon):
        f = B.Fighter(self.dex, mon)
        f.ability_on = True
        return f

    def _wire(self):
        self.bt = LiveDuel(self.dex, self.a.mon, self.b.mon, self.rng,
                           ai="trainer", field=self.field)
        self.bt.teams = {"me": self.a.team, "foe": self.b.team}
        self.bt.foe_prefix = "상대 "
        self.bt.max_turns = 10 ** 9      # 끝내는 건 여기서 한다
        self.bt.kind = "pvp"
        self.bt.switcher = self._move_switch

    def side(self, who):
        return self.a if who == "a" else self.b

    def other(self, who):
        return "b" if who == "a" else "a"

    @staticmethod
    def _seat(who):
        """엔진 안에서의 자리. a 가 me, b 가 foe 다."""
        return "me" if who == "a" else "foe"

    # ---------------- 시작 ----------------
    def start(self):
        if self.started:
            return []
        self.started = True
        ev = [{"t": "intro", "me": self.a.name, "foe": self.b.name,
               "text": "%s 님과의 승부가 시작됐다!" % self.b.name}]
        ev.append(self._out_event("a"))
        ev.append(self._out_event("b"))
        self._entry_abilities(ev, fresh=False)
        return ev

    def _out_event(self, who, text=None):
        p = self.side(who)
        seat = self._seat(who)
        return {"t": "switch", "who": seat, "slot": p.slot,
                "mon": self.view_mon(p.mon, True),
                "text": text or ("가랏! %s!" % p.mon.name if who == "a"
                                 else "상대는 %s 을(를) 내보냈다!" % p.mon.name)}

    def _entry_abilities(self, ev, only=None, fresh=True):
        """나온 순간의 특성 (위협·다운로드 ...). 빠른 쪽부터."""
        pair = [("me", self.a.mon), ("foe", self.b.mon)]
        if only:
            pair = [x for x in pair if x[0] in only]
        pair.sort(key=lambda x: -x[1].stat("spe"))
        for seat, f in pair:
            if not f.alive():
                continue
            team = self.a.team if seat == "me" else self.b.team
            f.ab["down"] = sum(1 for x in team if not x.alive())
            A.on_switch_in(self.bt, f, seat, ev)
            SM.on_enter_abilities(self.bt, f, seat, ev)
            if not fresh:
                f.ab["fresh"] = False

    # ---------------- 고르기 ----------------
    def phase(self):
        """지금 무엇을 고를 차례인가. choose(기술·교체) / switch(다음 포켓몬)."""
        if self.a.need_switch or self.b.need_switch:
            return "switch"
        return "choose"

    def can_act(self, who):
        p = self.side(who)
        if self.over or not p.playing():
            return False
        if self.phase() == "switch":
            return p.need_switch
        return True

    def valid_switches(self, who):
        p = self.side(who)
        return [i for i in p.alive_slots() if i != p.slot]

    def choose(self, who, kind, value=None):
        """이 사람이 이번에 할 것을 적어 둔다. 턴은 아직 안 돈다."""
        p = self.side(who)
        if self.over:
            raise ValueError("이미 끝난 승부입니다.")
        if not self.can_act(who):
            raise ValueError("지금은 고를 차례가 아닙니다.")
        if kind == "forfeit":
            p.choice = ("forfeit", None)
            return p.choice
        if self.phase() == "switch" and kind != "switch":
            raise ValueError("다음 포켓몬을 골라야 합니다.")
        if kind == "switch":
            slot = int(value)
            if slot not in self.valid_switches(who):
                raise ValueError("그 포켓몬으로는 바꿀 수 없습니다.")
            if self.phase() != "switch" and SM.trapped(self.bt, p.mon):
                raise ValueError("%s 은(는) 붙잡혀 있어서 교체할 수 없습니다." % p.mon.name)
            p.choice = ("switch", slot)
        elif kind == "move":
            # 역린류·2턴 기술로 잠겨 있으면 그것으로 바꿔 받는다
            key = SM.locked_move(p.mon) or value or ""
            if key != B.STRUGGLE:
                if key not in p.mon.pp:
                    raise ValueError("그 기술은 배우지 않았습니다.")
                if p.mon.pp.get(key, 0) <= 0:
                    raise ValueError("그 기술은 PP 가 없습니다.")
                why = SM.restricted(self.bt, p.mon, key)
                enc = p.mon.cond.get("encore")
                if why and not (enc and enc.get("move") == key):
                    raise ValueError(why)
            p.choice = ("move", key)
        else:
            raise ValueError("무엇을 할지 알 수 없습니다.")
        return p.choice

    def auto_choice(self, who):
        """시간 안에 못 고른 사람 대신. 교체 차례면 다음 포켓몬, 아니면 가장 센 기술."""
        p = self.side(who)
        if self.phase() == "switch":
            left = self.valid_switches(who) or p.alive_slots()
            return ("switch", left[0]) if left else ("move", B.STRUGGLE)
        foe = self.side(self.other(who)).mon
        best, score = None, -1.0
        for key in self.bt.usable(p.mon):
            md = self.bt.move_of(key)
            if not MC.attacks(md):
                continue
            d = self.bt.estimate(p.mon, foe, key)
            if d > score:
                best, score = key, d
        return ("move", best or self.bt.usable(p.mon)[0])

    def ready(self):
        """고를 사람이 모두 골랐는가.

        **기권은 상대를 안 기다린다.** 한쪽이 그만두겠다고 했는데 상대가
        고를 때까지 판이 멈춰 있으면, 그만둔 사람은 창을 닫고 가 버리고
        남은 사람은 제한 시간을 다 기다려야 한다.
        """
        for w in ("a", "b"):
            c = self.side(w).choice
            if c and c[0] == "forfeit":
                return True
        return all(self.side(w).choice is not None
                   for w in ("a", "b") if self.can_act(w))

    def waiting(self):
        return [w for w in ("a", "b") if self.can_act(w) and self.side(w).choice is None]

    # ---------------- 한 턴 ----------------
    def resolve(self):
        """한 턴(또는 교체 한 번)을 돈다. 일어난 일 목록 (a 쪽 기준)."""
        if self.over:
            return [{"t": "over", "result": self.result}]
        if not self.started:
            return self.start()
        for w in ("a", "b"):
            if self.can_act(w) and self.side(w).choice is None:
                self.side(w).choice = self.auto_choice(w)
                self.side(w).auto += 1
        # 기권은 어느 단계에서든 그 자리에서 끝난다.
        for w in ("a", "b"):
            c = self.side(w).choice
            if c and c[0] == "forfeit":
                ev = []
                self._give_up(w, ev)
                for x in ("a", "b"):
                    self.side(x).choice = None
                return ev
        if self.phase() == "switch":
            return self._do_switches()
        return self._do_turn()

    def _do_switches(self):
        """쓰러졌거나 물러난 쪽이 다음 포켓몬을 낸다. 턴은 안 는다."""
        ev = []
        fresh = []
        for w in ("a", "b"):
            p = self.side(w)
            if not p.need_switch:
                continue
            kind, value = p.choice or self.auto_choice(w)
            p.choice = None
            if kind == "forfeit":
                self._give_up(w, ev)
                continue
            p.need_switch = False
            out, p.pending_out = p.pending_out, None
            carry = ({"mode": out["mode"], "state": out.get("state")}
                     if out and out["mode"] in ("pass", "shed") else None)
            self._switch(w, int(value), ev, carry=carry, trigger=False)
            fresh.append(self._seat(w))
        if fresh and not self.over:
            self._entry_abilities(ev, only=fresh, fresh=False)
            self.bt._check_faint(ev)      # 압정에 쓰러질 수 있다
            self._settle(ev)
        return ev

    def _do_turn(self):
        ev = []
        self.turn += 1
        self.bt.turn_no = self.turn
        self.bt.begin_turn()

        # 기권이 있으면 거기서 끝
        for w in ("a", "b"):
            if (self.side(w).choice or ("", None))[0] == "forfeit":
                self._give_up(w, ev)
        if self.over:
            return ev

        moves = {}
        for w in ("a", "b"):
            p = self.side(w)
            kind, value = p.choice or ("move", None)
            if kind == "switch":
                self._switch(w, int(value), ev)
            else:
                key = value
                if key != B.STRUGGLE and (key not in p.mon.pp
                                          or p.mon.pp.get(key, 0) <= 0):
                    key = self.bt.usable(p.mon)[0]
                if p.mon.held:
                    key = H.force_move(p.mon, key, ev, self._seat(w))
                moves[self._seat(w)] = key

        me, foe = self.a.mon, self.b.mon
        me.flinched = False
        foe.flinched = False
        mm, fm = moves.get("me"), moves.get("foe")
        if mm and fm:
            order = self.bt._order(mm, fm, ev)
        elif mm:
            order = ["me"]
        elif fm:
            order = ["foe"]
        else:
            order = []
        me.moved_second = bool(order) and order[0] != "me"
        foe.moved_second = bool(order) and order[0] != "foe"

        acting = {"me": self.a.mon, "foe": self.b.mon}
        for seat in order:
            user = self.a.mon if seat == "me" else self.b.mon
            target = self.b.mon if seat == "me" else self.a.mon
            if user is not acting[seat]:
                continue                  # 이번 턴에 끌려 나온 쪽은 안 움직인다
            if not user.alive() or not target.alive():
                continue
            self.bt._use(seat, user, target, moves[seat], ev)

        if self.a.mon.alive() or self.b.mon.alive():
            self.bt._end_of_turn(ev)
        self.bt._check_faint(ev)
        self._settle(ev)
        for w in ("a", "b"):
            self.side(w).choice = None
        if not self.over and self.turn >= self.max_turns:
            self._by_headcount(ev)
        return ev

    # ---------------- 교체 ----------------
    def _switch(self, who, slot, ev, trigger=True, carry=None, dragged=False):
        p = self.side(who)
        seat = self._seat(who)
        old = p.mon
        if old.alive():
            A.on_switch_out(old)
            ev.append({"t": "recall", "who": seat,
                       "text": ("%s 은(는) 끌려 나갔다!" % old.name) if dragged
                       else ("%s, 돌아와!" % old.name if who == "a"
                             else "상대는 %s 을(를) 불러들였다!" % old.name)})
        SM.on_leave(self.bt, seat)
        old.stages = dict((k, 0) for k in B.STAGE_KEYS)
        old.flinched = False
        old.locked = None
        old.clear_volatile()
        old.types_override = None
        p.slot = slot
        if seat == "me":
            self.bt.me = p.mon
        else:
            self.bt.foe = p.mon
        if carry:
            SM.apply_pass(p.mon, carry.get("state"),
                          shed=carry.get("mode") == "shed")
        ev.append(self._out_event(who))
        self.bt.enter(seat, ev)
        if trigger and p.mon.alive():
            self._entry_abilities(ev, only=[seat], fresh=False)

    def _move_switch(self, seat, mode, ev, key, state=None):
        """기술이 부른 교체 (유턴·울부짖기 ...). 해냈으면 True."""
        who = "a" if seat == "me" else "b"
        p = self.side(who)
        others = self.valid_switches(who)
        if not others:
            return False
        if mode == "drag":
            self._switch(who, self.rng.choice(others), ev, dragged=True)
            return True
        # 누구를 낼지는 **사람이 고른다.** 이 턴이 끝난 뒤에 묻는다.
        p.pending_out = {"mode": mode, "state": state, "key": key}
        ev.append({"t": "msg", "who": seat,
                   "text": "%s 은(는) 돌아갈 준비를 한다!" % p.mon.name})
        return True

    # ---------------- 정리 ----------------
    def _give_up(self, who, ev):
        p = self.side(who)
        if p.forfeited or self.over:
            return
        p.forfeited = True
        p.choice = None
        p.need_switch = False
        ev.append({"t": "msg", "who": self._seat(who),
                   "text": "%s 님이 승부를 포기했다..." % p.name})
        self._finish(self.other(who), "forfeit", ev)

    def _settle(self, ev):
        if self.over:
            return
        a_out, b_out = self.a.wiped(), self.b.wiped()
        if a_out and b_out:
            return self._finish("draw", "ko", ev)
        if a_out:
            return self._finish("b", "ko", ev)
        if b_out:
            return self._finish("a", "ko", ev)
        for w in ("a", "b"):
            p = self.side(w)
            if not p.mon.alive():
                p.need_switch = True
                p.pending_out = None
                p.choice = None
                ev.append({"t": "choose", "who": self._seat(w),
                           "text": "%s 님이 다음 포켓몬을 고르고 있다..." % p.name})
            elif p.pending_out and self.valid_switches(w):
                p.need_switch = True
                p.choice = None
                ev.append({"t": "choose", "who": self._seat(w),
                           "text": "%s 님이 교체할 포켓몬을 고르고 있다..." % p.name})
            else:
                p.pending_out = None

    def _by_headcount(self, ev):
        na = sum(1 for f in self.a.team if f.alive())
        nb = sum(1 for f in self.b.team if f.alive())
        if na == nb:
            ra = sum(f.hp / float(f.maxhp or 1) for f in self.a.team)
            rb = sum(f.hp / float(f.maxhp or 1) for f in self.b.team)
            na, nb = ra, rb
        self._finish("a" if na > nb else ("b" if na < nb else "draw"),
                     "turns", ev)

    def _finish(self, result, reason, ev):
        self.over = True
        self.result = result
        self.reason = reason
        self.a.need_switch = self.b.need_switch = False
        if result == "draw":
            text = "양쪽 모두 쓰러졌다..."
        else:
            text = "%s 님이 이겼다!" % self.side(result).name
        ev.append({"t": "over", "result": result, "reason": reason, "text": text})

    def outcome(self, who):
        """그 사람 기준의 승패. win / lose / draw."""
        if not self.over:
            return None
        if self.result == "draw":
            return "draw"
        return "win" if self.result == who else "lose"

    def left(self, who):
        return len(self.side(who).alive_slots())

    # ---------------- 보여주기 ----------------
    def view_mon(self, f, mine):
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
        return out

    def moves_of(self, who):
        p = self.side(who)
        f, dex = p.mon, self.dex
        out = []
        for m in f.moves:
            md = dex.move(m) or {}
            out.append({"key": m, "kr": dex.move_name(m), "type": md.get("type"),
                        "typeKr": dex.type_name(md.get("type")), "cat": md.get("cat"),
                        "power": md.get("power"), "acc": md.get("acc"),
                        "pp": f.pp.get(m, 0), "maxpp": md.get("pp", 0),
                        "desc": md.get("desc", ""),
                        "blocked": SM.restricted(self.bt, f, m)})
        if not any(x["pp"] > 0 for x in out):
            out.append({"key": B.STRUGGLE, "kr": "몸부림", "type": "NORMAL",
                        "typeKr": "노말", "cat": "physical", "power": 50, "acc": 0,
                        "pp": 1, "maxpp": 1, "desc": "", "blocked": None})
        return out

    def view(self, who):
        """그 사람 시점의 판 상태. me 가 늘 자기 쪽이다."""
        me, foe = self.side(who), self.side(self.other(who))
        return {
            "turn": self.turn, "maxTurns": self.max_turns,
            "over": self.over, "result": self.outcome(who), "reason": self.reason,
            "phase": self.phase(), "canAct": self.can_act(who),
            "weather": self.field.weather, "terrain": self.field.terrain,
            "me": {"name": me.name, "slot": me.slot,
                   "team": [self.view_mon(f, True) for f in me.team],
                   "moves": self.moves_of(who),
                   "switches": self.valid_switches(who),
                   "chosen": me.choice is not None,
                   "needSwitch": me.need_switch,
                   "left": len(me.alive_slots())},
            "foe": {"name": foe.name, "slot": foe.slot,
                    "team": [self.view_mon(f, False) for f in foe.team],
                    "chosen": foe.choice is not None,
                    "needSwitch": foe.need_switch,
                    "left": len(foe.alive_slots())},
        }

    def events_for(self, who, events):
        """a 쪽 기준으로 만든 일을 그 사람 시점으로."""
        return list(events) if who == "a" else flip_log(events)

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

    def _dump_side(self, p):
        return {"uid": p.uid, "name": p.name, "slot": p.slot,
                "team": [self._dump_fighter(f) for f in p.team],
                "choice": list(p.choice) if p.choice else None,
                "needSwitch": p.need_switch, "pendingOut": p.pending_out,
                "forfeited": p.forfeited, "auto": p.auto}

    def _load_side(self, d):
        p = Player(d["uid"], d["name"], [self._load_fighter(x) for x in d["team"]])
        p.slot = int(d["slot"])
        p.choice = tuple(d["choice"]) if d.get("choice") else None
        p.need_switch = bool(d.get("needSwitch"))
        p.pending_out = d.get("pendingOut")
        p.forfeited = bool(d.get("forfeited"))
        p.auto = int(d.get("auto") or 0)
        return p

    def dump(self):
        st = self.rng.getstate()
        return {"v": 1, "turn": self.turn, "over": self.over,
                "result": self.result, "reason": self.reason,
                "started": self.started, "maxTurns": self.max_turns,
                "a": self._dump_side(self.a), "b": self._dump_side(self.b),
                "field": self.field.dump(),
                "rng": [st[0], list(st[1]), st[2]]}

    @classmethod
    def load(cls, dex, d):
        self = cls.__new__(cls)
        self.dex = dex
        self.rng = random.Random()
        r = d["rng"]
        self.rng.setstate((r[0], tuple(r[1]), r[2]))
        self.max_turns = int(d.get("maxTurns") or MAX_TURNS)
        self.a = self._load_side(d["a"])
        self.b = self._load_side(d["b"])
        self.field = FD.Field.load(d.get("field"))
        self._wire()
        self.turn = int(d["turn"])
        self.bt.turn_no = self.turn
        self.over = bool(d["over"])
        self.result = d.get("result")
        self.reason = d.get("reason")
        self.started = bool(d.get("started"))
        return self
