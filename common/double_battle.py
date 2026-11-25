# -*- coding: utf-8 -*-
"""실시간 더블배틀 (독도, 2026-11-25) — **편마다 두 마리, 양쪽 다 사람이 고른다.**

live_battle.LiveBattle 과 같은 문(choose · ready · resolve · view · events_for · dump/load)을 가진다 -
서버(app/live.py)는 형식만 보고 갈아 끼운다.

## 어떻게 도나

엔진(battle.Battle)은 1:1 전용이다. 더블 엔진을 새로 쓰는 대신 **Battle 하나에 행동마다 둘을 앉힌다**:
쓰는 포켓몬과 맞는 포켓몬을 me/foe 자리에 앉히고 `_use` 를 부른다. 기술 900 · 특성 370 · 도구 245 의 판정이
그대로 온다. '상대는 하나' 를 가정한 곳은 여기서 메운다.

    자리      a0 a1 (먼저 기다린 사람) · b0 b1. 엔진의 편 글자는 a = "me", b = "foe" 로 늘 같다.
    앉히기    서로 다른 편이면 그대로. **같은 편(아군에게 쓰는 기술)** 이면 아군을 맞은편 자리에 앉히고
              Field 를 비춘 것(_FieldView - 양쪽 다 자기 편)으로 갈아 끼운다.
    이벤트    엔진은 who: me/foe 만 낸다. 앉힌 자리를 보고 at(누구) · to(누구에게)를 붙인다 (_flush).
    광역기    첫 대상은 보통대로 `_use`, 나머지는 엔진의 연결점(Battle.spread)이 `_do_use(called=True)` 로 -
              기술 이름 · PP · 못 움직임 판정은 한 번, 명중 · 방어 · 데미지는 대상마다.

## 본가 규칙 (v1)

    · '고른 하나' 기술은 상대 0 / 상대 1 / 아군 중 고른다. 쓰러진 상대를 겨눴으면 남은 상대로.
    · 상대 전부(11) · 나 빼고 전부(9)는 둘 이상을 때리면 0.75배.
    · 날따름 · 분노가루 · 스포트라이트, 피뢰침 · 마중물이 '고른 하나' 기술을 끌어온다.
    · 도우미 1.5배 · 프렌드가드 0.75배 · 배터리/파워스폿 1.3배 · 텔레파시 · 위협은 상대 둘 다.
    · 사이드체인지 · 당신먼저 · 순서미루기 · 아로마미스트 · 코칭 · 드래곤옐 · 지휘.
    · 쓰러지면 그 턴의 차례는 사라지고, 턴이 끝난 뒤 빈 자리를 가진 쪽이 다음을 고른다.

본가와 다른 것(벽 0.5배 · 붙잡기의 '건 쪽' 은 편 단위 · 미래예지는 편 단위 · 등장 특성은 위협 말고 상대 하나 …)은
design-notes/2026-11-25-double-battle.md 에 적어 두었다.
"""
import random

from . import abilities as A
from . import battle as B
from . import field as FD
from . import held as H
from . import movecalc as MC
from . import statusmoves as SM
from . import live_battle as L
from .party_battle import flip

TEAM_MAX = L.TEAM_MAX
MAX_TURNS = L.MAX_TURNS
SIDE = {"a": "me", "b": "foe"}           # 엔진의 편 글자
LETTER = {"me": "a", "foe": "b"}
POSITIONS = ("a0", "a1", "b0", "b1")

# 그 턴에만 가는 것 (battle.Battle.begin_turn 과 같은 목록 - 거기는 앉은 둘만 본다)
TURN_CONDS = ("protect", "endure", "magiccoat", "snatch", "electrify", "rose", "fell", "roost")

# 기술의 대상 번호(PokeAPI) -> 화면이 고르게 할 것
AIM = {10: "one", 2: "one", 8: "random", 11: "foes", 9: "all", 14: "all", 7: "self", 16: "self", 5: "self",
       3: "ally", 13: "team", 15: "team", 4: "field", 6: "field", 12: "field", 1: "back"}
# 나와 아군에게 거는 기술 가운데 엔진이 '나' 만 처리하는 것 - 아군 몫을 여기서 얹는다
TEAM_EXTRA = {"HOWL": [("atk", 1)], "GEARUP": [("atk", 1), ("spa", 1)], "MAGNETICFLUX": [("def", 1), ("spd", 1)],
              "LIFEDEW": "heal", "JUNGLEHEALING": "cure", "LUNARBLESSING": "cure"}
DRAWS = {"ELECTRIC": "LIGHTNINGROD", "WATER": "STORMDRAIN"}      # 피뢰침 · 마중물
CENTER = ("FOLLOWME", "RAGEPOWDER", "SPOTLIGHT")


class _FieldView(object):
    """같은 편 둘을 앉혔을 때의 Field. 날씨 · 필드 · 룸은 진짜 것이고, 편(sides)은 **양쪽 다 자기 편**이다.

    아군에게 지진을 쓸 때 엔진은 아군을 '맞은편' 으로 본다. 그대로 두면 상대 편의 리플렉터 · 와이드가드를
    아군이 쓰고, 아군의 것은 못 쓴다.
    """

    def __init__(self, real, side):
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_side", side)

    @property
    def sides(self):
        s = self._real.sides[self._side]
        return {"me": s, "foe": s}

    def side(self, who):
        return self._real.sides[self._side]

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_real"), name)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)


class DoubleDuel(B.Battle):
    """더블의 한 판을 도는 Battle. 앉히는 것 · 끝내는 것은 DoubleBattle 이 한다."""
    double = None           # 감싼 판 - 엔진의 연결점(statusmoves.h_singles_fail · attackfx.cant_use)이 본다
    _mods = None            # 지금 나가는 기술에 얹을 것 (광역 0.75 · 도우미 …) - move_of 가 본다

    # ---- 넷을 다 본다 ----
    def _check_faint(self, ev):
        d = self.double
        if d is None:
            return
        d._flush()
        for pk, f in d.actives():
            if not f.alive() and not f.ab.get("fainted"):
                f.ab["fainted"] = True
                d.field.side(SIDE[pk[0]])["fellAt"] = int(getattr(d.field, "clock", 0))   # 원수갚기
                ev.append({"t": "faint", "who": SIDE[pk[0]], "at": pk,
                           "text": "%s 은(는) 쓰러졌다!" % f.name})

    def _suppress_weather(self):
        d = self.double
        if d is None or not getattr(d, "wired", False):
            return B.Battle._suppress_weather(self)
        d.field.suppressed = any(f.alive() and A.has(f, "CLOUDNINE", "AIRLOCK") for _pk, f in d.actives())

    # ---- 지금 나가는 기술 ----
    def move_of(self, key):
        md = B.Battle.move_of(self, key)
        mods = self._mods
        if mods and key in mods["keys"]:
            return dict(md, **mods["over"])
        return md

    def spread(self, who, user, key, ev, n0):
        """엔진의 연결점 (Battle._use_one): 광역기의 나머지 대상."""
        self.double._spread_rest(who, user, ev, n0)

    def _use(self, who, user, target, key, ev, called=False, instructed=False, bounced=False):
        d = self.double
        if instructed and d is not None and not d._instructing:
            return d._instructed(user, key, ev)       # 지휘: 그 포켓몬이 고른 대상에게 다시 쓴다
        return B.Battle._use(self, who, user, target, key, ev, called, instructed, bounced)

    # ---- 씨뿌리기: 심은 자리로 ----
    def _seed(self, target, who, tw, ev):
        """심은 포켓몬의 자리("a1")를 seed_by 에 적는다. **who 가 앉은 자리**다 - 매직미러로 튕긴 씨앗은 튕겨 낸
        포켓몬이 심은 것이라, '이번에 움직인 포켓몬' 으로 적으면 자기 자리가 적혀 아무도 못 빨아들인다 (검토 11/25)."""
        had = target.seeded
        B.Battle._seed(self, target, who, tw, ev)
        if target.seeded and not had:
            target.seed_by = self.double._seats.get(who)

    def _drain_seed(self, f, who, ev):
        d = self.double
        pk = f.seed_by if isinstance(f.seed_by, str) else None
        taker = d.at(pk) if pk else None
        if taker is None or not taker.alive() or taker is f:
            return                                   # 받을 포켓몬이 없으면 빼앗지도 않는다 (엔진과 같다)
        d._flush()
        mine = d.pos_of(f)
        other = "foe" if who == "me" else "me"
        keep = (self._me, self._foe)
        if other == "me":
            self._me = taker
        else:
            self._foe = taker
        n0 = len(ev)
        try:
            B.Battle._drain_seed(self, f, who, ev)
        finally:
            self._me, self._foe = keep
        for e in ev[n0:]:                            # 자리를 여기서 붙인다 (앉은 자리와 다르다)
            at = mine if e.get("who") == who else pk
            e["at"] = at
            e["who"] = SIDE[at[0]]


class Player2(object):
    """판에 앉은 사람 하나. 자리 둘."""

    def __init__(self, uid, name, team):
        self.uid = int(uid)
        self.name = name or "?"
        self.team = team
        alive = [i for i, f in enumerate(team) if f.alive()]
        self.active = [alive[0] if alive else None, alive[1] if len(alive) > 1 else None]
        self.picks = None               # 이번에 할 것 ([pick ...] / "forfeit")
        self.need = []                  # 다음 포켓몬을 골라야 하는 자리
        self.pending_out = {}           # {자리: {mode, state, key}} 유턴 · 배턴터치로 물러나는 중
        self.forfeited = False
        self.auto = 0                   # 서버가 대신 고른 횟수

    def alive_slots(self):
        return [i for i, f in enumerate(self.team) if f.alive()]

    def reserves(self):
        return [i for i in self.alive_slots() if i not in self.active]

    def wiped(self):
        return not self.alive_slots()

    def playing(self):
        return not self.forfeited and not self.wiped()


def _blank_turn():
    return {"plan": {}, "queue": [], "done": [], "helped": {}, "center": {}, "struck": {}, "zplan": {}}


class DoubleBattle(object):
    fmt = "double"

    def __init__(self, dex, a, b, rng=None, max_turns=MAX_TURNS):
        """a, b: (uid, 이름, [mon ...]). mon 은 이미 레벨을 맞춘 것."""
        self.dex = dex
        self.rng = rng or random.Random()
        self.max_turns = int(max_turns)
        self.a = Player2(a[0], a[1], [self._fighter(m) for m in a[2][:TEAM_MAX]])
        self.b = Player2(b[0], b[1], [self._fighter(m) for m in b[2][:TEAM_MAX]])
        if not self.a.team or not self.b.team:
            raise ValueError("양쪽 다 포켓몬이 있어야 합니다.")
        self.field = FD.Field()
        self.keystone = {"me": False, "foe": False}
        self.mega_done = set()
        B.gimmick_init(self)
        self.turn = 0
        self.step = 0
        self.over = False
        self.result = None
        self.reason = None
        self.started = False
        self.mid = None                 # 턴 도중에 멈춘 자리 (유턴으로 물러나는 중)
        self._wire()

    # ---------------- 만들기 ----------------
    _fighter = L.LiveBattle._fighter
    _dump_fighter = staticmethod(L.LiveBattle._dump_fighter)
    _load_fighter = L.LiveBattle._load_fighter
    view_mon = L.LiveBattle.view_mon

    def _wire(self):
        self.wired = False
        self.t = _blank_turn()          # 이번 턴에만 있는 것 (차례 · 도우미 · 날따름 · 맞은 기록)
        self._ev = None                 # 지금 쌓고 있는 일 목록 (_flush 가 자리를 붙인다)
        self._mark = 0
        self._seats = {}
        self._cur = None                # 지금 움직이는 포켓몬 {side, pos, at, fk, target, key}
        self._rest = None               # 광역기의 나머지 대상
        self._telepathy = None          # 이번 기술을 텔레파시로 안 맞은 아군 자리
        self._instructing = False
        fa = next(f for f in self.a.team if f is not None)
        fb = next(f for f in self.b.team if f is not None)
        self.bt = DoubleDuel(self.dex, fa, fb, self.rng, ai="trainer", field=self.field)
        bt = self.bt
        bt.double = self
        bt.teams = {"me": self.a.team, "foe": self.b.team}
        bt.foe_prefix = ""               # 편은 자리(at)로 알린다 - 글에 '상대' 를 안 박는다
        bt.max_turns = 10 ** 9
        bt.kind = "pvp"
        bt.switcher = self._move_switch
        bt.keystone = self.keystone
        bt.mega_done = self.mega_done
        B.gimmick_share(self, bt)
        self.wired = True
        pa, pb = self._default_pair()
        self._seat(pa, pb)

    def side(self, who):
        return self.a if who == "a" else self.b

    @staticmethod
    def other(who):
        return "b" if who == "a" else "a"

    # ---------------- 자리 ----------------
    def mon(self, who, pos):
        """그 자리의 포켓몬 (쓰러진 채 남아 있을 수 있다). 비었으면 None."""
        p = self.side(who)
        i = p.active[pos]
        return p.team[i] if i is not None else None

    def at(self, pk):
        return self.mon(pk[0], int(pk[1])) if pk else None

    def actives(self):
        out = []
        for pk in POSITIONS:
            f = self.at(pk)
            if f is not None:
                out.append((pk, f))
        return out

    def pos_of(self, f):
        for pk, x in self.actives():
            if x is f:
                return pk
        return None

    def _fk(self, who, idx):
        """포켓몬의 이름표 (편:팀 자리). 사이드체인지로 자리가 바뀌어도 따라간다."""
        return "%s:%d" % (who, idx)

    def _fk_at(self, pk):
        i = self.side(pk[0]).active[int(pk[1])]
        return self._fk(pk[0], i) if i is not None else None

    def _where(self, fk):
        """이름표의 포켓몬이 지금 서 있는 자리. 물러났으면 None."""
        who, idx = fk.split(":")
        p = self.side(who)
        idx = int(idx)
        for pos in (0, 1):
            if p.active[pos] == idx:
                return "%s%d" % (who, pos)
        return None

    def _live(self, pk):
        f = self.at(pk)
        return f is not None and f.alive()

    def _foes(self, who):
        """맞은편의 살아 있는 자리들."""
        o = self.other(who)
        return [pk for pk in ("%s0" % o, "%s1" % o) if self._live(pk)]

    def _ally(self, pk):
        ap = "%s%d" % (pk[0], 1 - int(pk[1]))
        return ap if self._live(ap) else None

    def _facing(self, pk):
        """앉힐 맞은편 하나 (살아 있는 쪽 먼저). 다 쓰러졌으면 남아 있는 아무나."""
        o = self.other(pk[0])
        order = ["%s%d" % (o, int(pk[1])), "%s%d" % (o, 1 - int(pk[1]))]
        for x in order:
            if self._live(x):
                return x
        for x in order:
            if self.at(x) is not None:
                return x
        return None

    def _default_pair(self):
        def first(who):
            both = ["%s0" % who, "%s1" % who]
            for x in both:
                if self._live(x):
                    return x
            for x in both:
                if self.at(x) is not None:
                    return x
            # 판을 막 만들었거나 되살리는 중 - 팀의 첫 포켓몬이라도 앉힌다
            return None
        return first("a"), first("b")

    def _seat(self, u, t):
        """엔진에 둘을 앉힌다. u 가 쓰는 쪽, t 가 맞는 쪽 (같은 편일 수 있다)."""
        bt = self.bt
        self._flush()
        if u is None or t is None:
            return
        for pk, f in self.actives():
            f.field = self.field
            f.side_name = SIDE[pk[0]]
        fu, ft = self.at(u), self.at(t)
        if u[0] != t[0]:
            pa, pb = (u, t) if u[0] == "a" else (t, u)
            bt.field = self.field
            bt._me, bt._foe = self.at(pa), self.at(pb)
            self._seats = {"me": pa, "foe": pb}
        else:
            own = SIDE[u[0]]
            bt.field = _FieldView(self.field, own)
            if own == "me":
                bt._me, bt._foe = fu, ft
                self._seats = {"me": u, "foe": t}
            else:
                bt._foe, bt._me = fu, ft
                self._seats = {"foe": u, "me": t}
        bt._attach(bt._me, "me")
        bt._attach(bt._foe, "foe")
        # 이번 턴에 누가 무엇을 하려 하고, 누가 이미 움직였나 (기습 · 부리캐논 · 힘껏펀치가 본다)
        plan, done = self.t["plan"], self.t["done"]
        bt.pending, bt.acted = {}, set()
        for seat, pk in self._seats.items():
            fk = self._fk_at(pk)
            bt.pending[seat] = (plan.get(fk) or {}).get("key")
            if fk in done:
                bt.acted.add(seat)

    def _reseat(self, seats):
        """적어 둔 앉은 자리({"me": 자리, "foe": 자리})로 되돌린다. 같은 편 둘이면 쓰는 쪽이 자기 편 글자에 있었다."""
        me, foe = seats.get("me"), seats.get("foe")
        if not me or not foe or self.at(me) is None or self.at(foe) is None:
            return
        if me[0] != foe[0]:
            self._seat(me, foe)
        else:
            self._seat(me, foe) if SIDE[me[0]] == "me" else self._seat(foe, me)

    def _flush(self):
        """엔진이 낸 일에 자리를 붙인다 (who 는 진짜 편으로). 자리를 바꿔 앉히기 전에 늘 먼저 돈다."""
        ev = self._ev
        if ev is None:
            return
        seats = self._seats
        for e in ev[self._mark:]:
            if "at" in e:
                continue
            w, tg = e.get("who"), e.get("target")
            if w in seats:
                e["at"] = seats[w]
                e["who"] = SIDE[seats[w][0]]
            if e.get("t") == "hit" and tg in seats:
                e["to"] = seats[tg]
                e["target"] = SIDE[seats[tg][0]]
                if w in seats:
                    self._note_struck(seats[w], seats[tg], e)
        self._mark = len(ev)

    def _note_struck(self, upk, tpk, e):
        """누가 누구를 어떤 기술로 때렸나 - 카운터 · 미러코트가 돌려줄 상대."""
        if upk[0] == tpk[0] or not e.get("damage"):
            return
        fk, by = self._fk_at(tpk), self._fk_at(upk)
        if fk is None or by is None:
            return
        cat = self.bt.move_of(getattr(self.bt, "_now_key", None) or "").get("cat")
        cat = cat if cat in ("physical", "special") else "physical"
        st = self.t["struck"].setdefault(fk, {})
        st[cat] = [by, int(e.get("damage") or 0)]
        st["last"] = cat

    # ---------------- 시작 ----------------
    def start(self):
        if self.started:
            return []
        self.started = True
        ev = self._open()
        ev.append({"t": "intro", "me": self.a.name, "foe": self.b.name,
                   "text": "%s 님과 %s 님의 더블배틀이 시작됐다!" % (self.a.name, self.b.name)})
        fresh = []
        for pk, f in self.actives():
            ev.append(self._out_event(pk))
            fresh.append(pk)
        self._entry(fresh, ev)
        return self._close(ev)

    def _open(self):
        ev = []
        self._ev, self._mark = ev, 0
        return ev

    def _close(self, ev):
        self._flush()
        self._ev = None
        return ev

    def _out_event(self, pk, say="out"):
        f = self.at(pk)
        return {"t": "switch", "who": SIDE[pk[0]], "at": pk, "slot": self.side(pk[0]).active[int(pk[1])],
                "say": say, "name": f.name, "mon": self.view_mon(f, True),
                "text": "%s 님은 %s 을(를) 내보냈다!" % (self.side(pk[0]).name, f.name)}

    def _entry(self, pks, ev):
        """나온 순간의 특성 (위협 · 다운로드 · 날씨 ...). 빠른 쪽부터. 위협은 상대 둘 다 내린다."""
        bt = self.bt
        pks = [pk for pk in pks if self._live(pk)]
        pks.sort(key=lambda pk: -self.at(pk).stat("spe"))
        for pk in pks:
            f = self.at(pk)
            if f is None or not f.alive():
                continue
            seat = SIDE[pk[0]]
            f.ab["down"] = sum(1 for x in self.side(pk[0]).team if not x.alive())
            face = self._facing(pk)
            if face is None:
                continue
            self._seat(pk, face)
            A.on_switch_in(bt, f, seat, ev)
            if f.alive() and f.ability_on and f.ability == "INTIMIDATE":
                for other in self._foes(pk[0]):
                    if other == face:
                        continue
                    self._seat(pk, other)
                    n0 = len(ev)
                    A.on_switch_in(bt, f, seat, ev)
                    for i in range(n0, len(ev)):          # 특성 알림은 한 번만
                        if ev[i].get("t") == "ability" and ev[i].get("who") == seat:
                            del ev[i]
                            break
                self._seat(pk, face)
            SM.on_enter_abilities(bt, f, seat, ev)
            f.ab["fresh"] = False
        self._flush()

    # ---------------- 고르기 ----------------
    def phase(self):
        """지금 무엇을 고를 차례인가. choose(기술 · 교체) / switch(다음 포켓몬)."""
        return "switch" if (self.a.need or self.b.need) else "choose"

    def can_act(self, who):
        p = self.side(who)
        if self.over or not p.playing():
            return False
        if self.phase() == "switch":
            return bool(p.need)
        return True

    def valid_switches(self, who):
        return self.side(who).reserves()

    def _actors(self, who):
        """이번에 기술 · 교체를 고를 자리들."""
        return [pos for pos in (0, 1) if self._live("%s%d" % (who, pos))]

    def _stuck(self, pk):
        """그 자리의 포켓몬이 스스로 못 물러나는 까닭 (문구). 물러날 수 있으면 None."""
        f = self.at(pk)
        if f is None or not f.alive():
            return None
        foes = self._foes(pk[0]) or [self._facing(pk)]
        for x in foes:
            if x is None:
                continue
            self._seat(pk, x)
            why = SM.switch_block(self.bt, f)
            if why:
                return why
        return None

    def _aim(self, f, key, md):
        if key == B.STRUGGLE:
            return "random"
        if MC.key(md) == "CURSE":
            return "one" if "GHOST" in f.types() else "self"
        return AIM.get(md.get("target"), "one")

    def _choices(self, pk, aim):
        """화면이 대상으로 고를 수 있는 것 ("foe0" · "foe1" · "ally")."""
        if aim != "one":
            return []
        o = self.other(pk[0])
        out = ["foe%d" % i for i in (0, 1) if self._live("%s%d" % (o, i))]
        if self._ally(pk):
            out.append("ally")
        return out

    def choose(self, who, kind, value=None, **_kw):
        """이 사람이 이번에 할 것을 적어 둔다. 턴은 아직 안 돈다.

        kind = "picks": value = [{pos, kind: move|switch, move, target, slot, mega, z, tera} ...]
        kind = "forfeit": 그만둔다 (내 차례가 아니어도 된다).
        """
        p = self.side(who)
        if self.over:
            raise ValueError("이미 끝난 승부입니다.")
        if kind == "forfeit":
            if not p.playing():
                raise ValueError("이미 끝난 승부입니다.")
            p.picks = "forfeit"
            return p.picks
        if kind != "picks":
            raise ValueError("더블배틀은 두 마리의 행동을 함께 보내야 합니다.")
        if not self.can_act(who):
            raise ValueError("지금은 고를 차례가 아닙니다.")
        picks = [dict(x) for x in (value if isinstance(value, (list, tuple)) else []) if isinstance(x, dict)]
        try:
            out = self._check_switches(who, picks) if self.phase() == "switch" else self._check_picks(who, picks)
        except (TypeError, OverflowError, KeyError, AttributeError, IndexError):
            # 보내온 것을 믿지 않는다 - 꼴이 이상하면(기술 자리에 목록 · 무한대 ...) 거절한다. 서버 오류로 터지면 안 된다
            raise ValueError("잘못된 선택입니다.")
        finally:
            pa, pb = self._default_pair()
            self._seat(pa, pb)
        p.picks = out
        return out

    @staticmethod
    def _pos(x):
        try:
            return int(x.get("pos"))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("어느 자리의 행동인지 알 수 없습니다.")

    def _check_switches(self, who, picks):
        p = self.side(who)
        if any(x.get("kind") != "switch" for x in picks):
            raise ValueError("다음 포켓몬을 골라야 합니다.")
        got = dict((self._pos(x), x) for x in picks)
        if sorted(got) != sorted(p.need) or len(picks) != len(p.need):
            raise ValueError("다음 포켓몬을 골라야 합니다.")
        out, taken = [], set()
        for pos in p.need:
            try:
                slot = int(got[pos].get("slot"))
            except (TypeError, ValueError, OverflowError):
                raise ValueError("그 포켓몬으로는 바꿀 수 없습니다.")
            if slot not in p.reserves() or slot in taken:
                raise ValueError("그 포켓몬으로는 바꿀 수 없습니다.")
            taken.add(slot)
            out.append({"pos": pos, "kind": "switch", "slot": slot})
        return out

    def _check_picks(self, who, picks):
        p, bt = self.side(who), self.bt
        seat = SIDE[who]
        actors = self._actors(who)
        got = dict((self._pos(x), x) for x in picks)
        if sorted(got) != actors or len(picks) != len(actors):
            raise ValueError("나와 있는 포켓몬마다 할 것을 골라야 합니다.")
        out, taken = [], set()
        flags = {"mega": 0, "z": 0, "tera": 0}
        for pos in actors:
            x = got[pos]
            pk = "%s%d" % (who, pos)
            f = self.at(pk)
            if x.get("kind") == "switch":
                try:
                    slot = int(x.get("slot"))
                except (TypeError, ValueError, OverflowError):
                    raise ValueError("그 포켓몬으로는 바꿀 수 없습니다.")
                if slot not in p.reserves() or slot in taken:
                    raise ValueError("그 포켓몬으로는 바꿀 수 없습니다.")
                why = self._stuck(pk)
                if why:
                    raise ValueError(why)
                taken.add(slot)
                out.append({"pos": pos, "kind": "switch", "slot": slot})
                continue
            if x.get("kind") != "move":
                raise ValueError("무엇을 할지 알 수 없습니다.")
            self._seat(pk, self._facing(pk))
            key = SM.locked_move(f, bt) or x.get("move") or ""
            if not isinstance(key, str):
                raise ValueError("그 기술은 배우지 않았습니다.")
            if key == B.STRUGGLE and bt.usable(f) != [B.STRUGGLE]:
                raise ValueError("아직 쓸 수 있는 기술이 있습니다.")
            if key != B.STRUGGLE:
                if key not in f.pp:
                    raise ValueError("그 기술은 배우지 않았습니다.")
                if f.pp.get(key, 0) <= 0:
                    raise ValueError("그 기술은 PP 가 없습니다.")
                why = SM.restricted(bt, f, key)
                enc = f.cond.get("encore")
                if why and not (enc and enc.get("move") == key):
                    raise ValueError(why)
            md = bt.move_of(key)
            target = x.get("target") or None
            # Z기술(공격)은 원래 기술이 광역기여도 **고른 하나**만 때린다 (본가 · 검토 11/25)
            z_on = bool(x.get("z")) and key in bt.z_moves(seat)
            if not isinstance(target, str) and target is not None:
                raise ValueError("그 대상은 고를 수 없습니다.")
            if self._aim(f, key, md) != "one" and not (z_on and MC.attacks(md)):
                target = None
            elif target not in (None, "foe0", "foe1", "ally"):
                raise ValueError("그 대상은 고를 수 없습니다.")
            pick = {"pos": pos, "kind": "move", "move": key, "target": target}
            # 메가진화 · Z기술 · 테라스탈: 될 때만 받는다 (실시간 싱글과 같다). 한 턴에 한 마리.
            if x.get("mega") and bt.can_mega(seat) is not None:
                pick["mega"] = True
                flags["mega"] += 1
            if x.get("tera") and not pick.get("mega") and bt.can_tera(seat) is not None:
                pick["tera"] = True
                flags["tera"] += 1
            if z_on:
                pick["z"] = True
                flags["z"] += 1
            out.append(pick)
        for name, kr in (("mega", "메가진화"), ("tera", "테라스탈"), ("z", "Z기술")):
            if flags[name] > 1:
                raise ValueError("%s 은(는) 한 턴에 한 마리만 할 수 있습니다." % kr)
        return out

    def auto_choice(self, who):
        """시간 안에 못 고른 사람 대신. 교체 차례면 다음 포켓몬, 아니면 가장 센 기술을 가장 아픈 상대에게."""
        p, bt = self.side(who), self.bt
        if self.phase() == "switch":
            left = list(p.reserves())
            return ("picks", [{"pos": pos, "kind": "switch", "slot": left.pop(0)}
                              for pos in p.need if left])
        out = []
        for pos in self._actors(who):
            pk = "%s%d" % (who, pos)
            f = self.at(pk)
            best, score, aim = None, -1.0, None
            for fp in self._foes(who) or [self._facing(pk)]:
                if fp is None:
                    continue
                self._seat(pk, fp)
                for key in bt.usable(f):
                    md = bt.move_of(key)
                    if not MC.attacks(md):
                        continue
                    d = bt.estimate(f, self.at(fp), key)
                    if d > score:
                        best, score, aim = key, d, "foe%s" % fp[1]
            key = best or bt.usable(f)[0]
            locked = SM.locked_move(f, bt)
            if locked:
                key = locked
            if self._aim(f, key, bt.move_of(key)) != "one":
                aim = None
            out.append({"pos": pos, "kind": "move", "move": key, "target": aim})
        pa, pb = self._default_pair()
        self._seat(pa, pb)
        return ("picks", out)

    def ready(self):
        """고를 사람이 모두 골랐는가. **기권은 상대를 안 기다린다.**"""
        if any(self.side(w).picks == "forfeit" for w in ("a", "b")):
            return True
        return all(self.side(w).picks is not None for w in ("a", "b") if self.can_act(w))

    def waiting(self):
        return [w for w in ("a", "b") if self.can_act(w) and self.side(w).picks is None]

    # ---------------- 한 턴 ----------------
    def resolve(self):
        """한 턴(또는 교체 한 번)을 돈다. 일어난 일 목록 (who: me = a 쪽, at/to = 자리)."""
        if self.over:
            return [{"t": "over", "result": self.result}]
        if not self.started:
            return self.start()
        self.step += 1
        ev = self._open()
        for w in ("a", "b"):
            p = self.side(w)
            if p.picks == "forfeit":
                self._give_up(w, ev)
                for x in ("a", "b"):
                    self.side(x).picks = None
                return self._close(ev)
        for w in ("a", "b"):
            p = self.side(w)
            if self.can_act(w) and p.picks is None:
                p.picks = self.auto_choice(w)[1]
                p.auto += 1
        if self.phase() == "switch":
            self._do_switches(ev)
        else:
            self._do_turn(ev)
        return self._close(ev)

    def _do_switches(self, ev):
        """쓰러졌거나 물러난 자리에 다음 포켓몬이 선다. 턴은 안 는다."""
        fresh = []
        for w in ("a", "b"):
            p = self.side(w)
            if not p.need:
                continue
            picks = p.picks if isinstance(p.picks, list) else self.auto_choice(w)[1]
            p.picks = None
            need, p.need = list(p.need), []
            for x in picks:
                pos = int(x["pos"])
                if pos not in need or int(x["slot"]) not in p.reserves():
                    continue
                out = p.pending_out.pop(pos, None)
                carry = ({"mode": out["mode"], "state": out.get("state")}
                         if out and out["mode"] in ("pass", "shed") else None)
                self._switch(w, pos, int(x["slot"]), ev, carry=carry, trigger=False)
                fresh.append("%s%d" % (w, pos))
            p.pending_out = {}
        mid, self.mid = self.mid, None
        if fresh:
            self._entry(fresh, ev)
            self.bt._check_faint(ev)              # 압정에 쓰러질 수 있다
        if mid:
            # 유턴 · 볼트체인지로 **턴 도중에** 물러났다. 남은 차례와 턴 끝을 마저 돈다.
            self._wake(mid)
            if self._run(ev):
                return
            return self._end_turn(ev)
        self._settle(ev)

    def _begin(self):
        pa, pb = self._default_pair()
        self.t = _blank_turn()
        self._seat(pa, pb)
        bt = self.bt
        bt.turn_no = self.turn
        bt.begin_turn()
        seated = (bt._me, bt._foe)
        for _pk, f in self.actives():
            if not any(f is x for x in seated):
                f.hurt = None
                f.cond["outTurns"] = int(f.cond.get("outTurns") or 0) + 1
                for c in TURN_CONDS:
                    f.cond.pop(c, None)
            f.flinched = False
            f.moved_second = False

    def _speed(self, pk):
        f = self.at(pk)
        v = f.stat("spe")
        if self.field.side(SIDE[pk[0]]).get("tailwind"):
            v *= 2
        return v

    def _do_turn(self, ev):
        bt = self.bt
        self.turn += 1
        self._begin()
        picks = []                                   # (자리, 고른 것)
        for w in ("a", "b"):
            p = self.side(w)
            for x in (p.picks if isinstance(p.picks, list) else []):
                picks.append(("%s%d" % (w, int(x["pos"])), x))
            p.picks = None

        # 1) 교체 - 빠른 쪽부터
        swaps = [(pk, x) for pk, x in picks if x.get("kind") == "switch" and self._live(pk)]
        swaps.sort(key=lambda it: -self._speed(it[0]))
        for pk, x in swaps:
            if int(x["slot"]) in self.side(pk[0]).reserves():
                self._switch(pk[0], int(pk[1]), int(x["slot"]), ev)
        moves = [(pk, x) for pk, x in picks if x.get("kind") == "move" and self._live(pk)]

        # 2) 메가진화 -> 테라스탈 (편마다 한 마리, 빠른 쪽부터 - 엔진이 정한다)
        for flag, step in (("mega", bt.mega_step), ("tera", bt.tera_step)):
            want = dict((pk[0], pk) for pk, x in moves if x.get(flag))
            if "a" in want and "b" in want:
                self._seat(want["a"], want["b"])
                step({"me": True, "foe": True}, ev)
            else:
                for w, pk in want.items():
                    self._seat(pk, self._facing(pk))
                    step({SIDE[w]: True}, ev)
            self._flush()

        # 3) 이번 턴의 기술
        t = self.t
        for pk, x in moves:
            f = self.at(pk)
            if f is None or not f.alive():
                continue
            self._seat(pk, self._facing(pk))
            key = x.get("move")
            if key != B.STRUGGLE and (key not in f.pp or f.pp.get(key, 0) <= 0):
                key = bt.usable(f)[0]
            if f.held:
                key = H.force_move(f, key, ev, SIDE[pk[0]], bt)       # 구애 잠금
            fk = self._fk_at(pk)
            t["plan"][fk] = {"key": key, "target": x.get("target")}
            if x.get("z") and key in bt.z_moves(SIDE[pk[0]]):
                t["zplan"][fk] = key
        self._flush()

        # 4) 차례: 우선도 -> 느림보 -> 선제공격손톱류 -> 스피드(순풍 · 트릭룸) -> 동전
        order = []
        slow = self.field.room("trickroom")
        for fk in list(t["plan"]):
            pk = self._where(fk)
            f = self.at(pk)
            md = bt.move_of(t["plan"][fk]["key"])
            self._seat(pk, self._facing(pk))
            pri = SM.priority(bt, f, md)             # 한 번만 센다 (싱글의 _order 는 특성 몫을 두 번 센다)
            last = 1 if A.order_last(f, md) else 0
            bias = H.order_bias(bt, f, SIDE[pk[0]], ev) if f.held else 0
            spd = self._speed(pk)
            order.append((-pri, last, -bias, spd if slow else -spd, self.rng.random(), fk))
        self._flush()
        order.sort()
        t["queue"] = [x[-1] for x in order]

        if self._run(ev):
            return                                   # 교체할 포켓몬을 고르는 동안 턴이 멈췄다
        self._end_turn(ev)

    def _run(self, ev):
        """남은 차례를 돈다. **사람이 고를 교체가 걸리면 거기서 멈춘다** (True)."""
        t = self.t
        while t["queue"]:
            fk = t["queue"].pop(0)
            pk = self._where(fk)
            if pk is None or not self._live(pk):
                continue                             # 물러났거나 쓰러졌다 - 그 차례는 사라진다
            if self.a.wiped() or self.b.wiped():
                break
            self._act(pk, t["plan"][fk], ev)
            if fk not in t["done"]:
                t["done"].append(fk)
            self._flush()
            if self._pause(ev):
                return True
        return False

    # ---------------- 기술 하나 ----------------
    def _real_key(self, f, key):
        """실제로 나갈 기술 (참기 · 앙코르 · 역린류로 묶인 것) - battle._do_use 와 같은 차례."""
        if key is None:
            return B.STRUGGLE
        if key == B.STRUGGLE:
            return key
        if f.bide:
            return "BIDE"
        enc = f.cond.get("encore")
        if enc and f.pp.get(enc.get("move"), 0) > 0:
            key = enc["move"]
        return SM.locked_move(f, self.bt) or key

    def _targets(self, pk, f, key, md, want, single=False):
        """이 기술이 갈 자리들 (첫 자리가 주 대상). 갈 데가 없으면 ([], 까닭).
        single = Z기술로 나간다 - 원래 기술이 광역기여도 고른 하나만."""
        who = pk[0]
        k = MC.key(md) if key != B.STRUGGLE else B.STRUGGLE
        t = md.get("target")
        foes = self._foes(who)
        ally = self._ally(pk)
        if k == "CURSE":
            t = 10 if "GHOST" in f.types() else 7
        if single and key != B.STRUGGLE:
            t = 10
        if key == B.STRUGGLE or t == 8:
            if not foes:
                return [], None
            x = foes[0] if len(foes) == 1 else self.rng.choice(foes)
            return [self._drawn(pk, f, md, k, x)], None
        if t == 1:
            return self._counter(pk, f, k, foes), None
        if t in (10, 2):
            if want == "ally":
                return ([ally], None) if ally else ([], "ally")
            if not foes:
                return [], None
            x = "%s%s" % (self.other(who), want[3]) if want in ("foe0", "foe1") else foes[0]
            if x not in foes:
                x = foes[0]                           # 겨눈 상대가 이미 쓰러졌다 - 남은 상대로
            return [self._drawn(pk, f, md, k, x)], None
        if t == 11:
            return list(foes), None
        if t == 9:
            out = list(foes)
            if ally:
                af = self.at(ally)
                if MC.attacks(md) and af.ability_on and A.has(af, "TELEPATHY") and not A.breaks(f):
                    self._telepathy = ally            # 텔레파시: 아군의 공격을 안 맞는다
                else:
                    out.append(ally)
            return out, None
        face = self._facing(pk)
        if face is None or not self._live(face):
            # 맞은편이 다 쓰러졌다. 싱글에서도 그 턴의 남은 차례는 사라진다.
            return [], None
        return [face], None

    def _counter(self, pk, f, k, foes):
        """카운터 · 미러코트 · 메탈버스트: 이번 턴에 그 종류로 나를 마지막에 때린 상대."""
        kind = (MC.COUNTERS.get(k) or (None, 0))[0]
        st = self.t["struck"].get(self._fk_at(pk)) or {}
        hit = st.get(kind or st.get("last"))
        at = self._where(hit[0]) if hit else None
        if hit and at and self._live(at):
            cat = kind or st.get("last")
            f.hurt = {"physical": 0, "special": 0, "by": SIDE[at[0]]}
            f.hurt[cat] = int(hit[1])
            return [at]
        f.hurt = None                                 # 돌려줄 것이 없다 - 엔진이 실패시킨다
        return foes[:1]

    def _drawn(self, pk, f, md, k, x):
        """'고른 하나' 기술을 끌어오는 것: 날따름 · 분노가루 · 스포트라이트, 그다음 피뢰침 · 마중물."""
        if x[0] == pk[0]:
            return x
        if k == "SNIPESHOT" or A.has(f, "STALWART", "PROPELLERTAIL"):
            return x
        c = self.t["center"].get(x[0])
        if c:
            cp = self._where(c["fk"])
            if cp and self._live(cp):
                dodge = c["k"] == "RAGEPOWDER" and ("GRASS" in f.types() or A.has(f, "OVERCOAT")
                                                    or f.held == "SAFETYGOGGLES")
                if not dodge:
                    return cp
        mt = (A.move_type(f, md) if f.ability_on else None) or md.get("type")
        rod = DRAWS.get(mt)
        if rod and not A.breaks(f) and not A.has(self.at(x), rod):
            others = [p for p in self._foes(pk[0]) if p != x]
            ally = self._ally(pk)
            for p in others + ([ally] if ally else []):
                if A.has(self.at(p), rod):
                    return p
        return x

    def _mult(self, upk, tpk, f, md, count):
        """대상마다 얹는 배율: 광역 0.75 · 도우미 1.5 · 프렌드가드 0.75 · 배터리/파워스폿 1.3."""
        if not MC.attacks(md):
            return 1.0
        m = 1.0
        if count > 1:
            m *= 0.75
        m *= 1.5 ** int(self.t["helped"].get(self._fk_at(upk), 0))
        ua = self._ally(upk)
        if ua:
            af = self.at(ua)
            if A.has(af, "BATTERY") and md.get("cat") == "special":
                m *= 1.3
            if A.has(af, "POWERSPOT"):
                m *= 1.3
        ta = self._ally(tpk)
        if ta and ta != upk and A.has(self.at(ta), "FRIENDGUARD") and not A.breaks(f):
            m *= 0.75
        return m

    def _set_mods(self, upk, tpk, f, keys, md, count, extra=None):
        over = dict(extra or {})
        m = self._mult(upk, tpk, f, md, count)
        if m != 1.0:
            over["_mult"] = m
        self.bt._mods = {"keys": tuple(keys), "over": over} if over else None

    def _act(self, pk, act, ev, instructed=False):
        bt = self.bt
        f = self.at(pk)
        who = pk[0]
        seat = SIDE[who]
        fk = self._fk_at(pk)
        key = act.get("key")
        real = self._real_key(f, key)
        md = bt.move_of(real)
        k = MC.key(md) if real != B.STRUGGLE else B.STRUGGLE
        self._telepathy = None
        # 이 수가 Z기술로 나가나 (지금도 쓸 수 있을 때만 - 그사이 Z크리스탈을 잃었을 수 있다)
        zed = False
        if not instructed and self.t["zplan"].get(fk) == key and MC.attacks(md):
            self._seat(pk, self._facing(pk) or pk)
            zed = key in bt.z_moves(seat)
        tgts, why = self._targets(pk, f, real, md, act.get("target"), single=zed)
        if not tgts:
            if why == "ally":
                ev.append({"t": "msg", "who": seat, "at": pk,
                           "text": "%s 의 %s! 하지만 대상이 없다!" % (f.name, bt.move_name(real))})
            return
        first = tgts[0]
        keep = (self._cur, self._rest, bt._mods)
        self._cur = {"side": who, "at": pk, "fk": fk, "target": first, "key": real}
        self._rest = {"list": tgts[1:], "count": len(tgts), "key": key, "real": real, "md": md}
        self._seat(pk, first)
        # 광역기의 생명의구슬 반동은 다 때린 뒤에 한 번 (_spread_rest 가 준다) - 대상마다의 것은 끈다
        self._set_mods(pk, first, f, (key, real), md, len(tgts), {"_noorb": True} if len(tgts) > 1 else None)
        bt.z_want = {}
        if not instructed and self.t["zplan"].get(fk) == key:
            bt.z_request(seat, key, True)
        f.moved_second = self._fk_at(first) in self.t["done"]
        n0 = len(ev)
        try:
            if instructed:
                B.Battle._use(bt, seat, f, self.at(first), key, ev, instructed=True)
            else:
                bt._use(seat, f, self.at(first), key, ev)
        finally:
            self._flush()
            now = self._cur["at"]                     # 사이드체인지로 자리가 바뀌었을 수 있다
            self._cur, self._rest, bt._mods = keep
        mine = [e for e in ev[n0:] if e.get("t") == "move" and e.get("at") in (pk, now)
                and e.get("name") == f.name]
        moved = bool(mine) and not mine[0].get("charge")
        tn = md.get("target")
        aimed = (zed or real == B.STRUGGLE or tn in (2, 8, 9, 10, 11) or (tn == 1 and k != "CURSE")
                 or (k == "CURSE" and "GHOST" in f.types()))
        if mine and aimed:
            mine[0]["to"] = first
            if len(tgts) > 1:
                mine[0]["tos"] = list(tgts)
        if moved and self._telepathy and self._live(self._telepathy):
            af = self.at(self._telepathy)
            af.ab["shown"] = True
            ev.append({"t": "ability", "who": seat, "at": self._telepathy, "ability": af.ability,
                       "abilityKr": self.dex.ability_name(af.ability),
                       "text": "[%s의 %s]" % (af.name, self.dex.ability_name(af.ability))})
        if moved:
            self._after_act(now, f, k, md, ev)
        # 희망사항은 **빈 자리**로 간다 - 쓴 자리를 적어 둔다
        wish = self.field.side(seat).get("wish")
        if wish and "pos" not in wish:
            wish["pos"] = int(now[1])
        if not instructed:
            self.t.setdefault("aimed", {})[fk] = act.get("target")
        self._flush()

    def _after_act(self, pk, f, k, md, ev):
        """엔진이 둘만 본 기술의 나머지 몫 (나와 아군 · 판 전체)."""
        bt = self.bt
        seat = SIDE[pk[0]]
        ally = self._ally(pk)
        extra = TEAM_EXTRA.get(k)
        if extra and ally and f.alive():
            af = self.at(ally)
            self._seat(ally, self._facing(ally) or pk)
            if isinstance(extra, list):
                if k not in ("GEARUP", "MAGNETICFLUX") or A.has(af, "PLUS", "MINUS"):
                    for st, n in extra:
                        bt._change_stat(af, st, n, ev, seat, source=af)
            else:
                if extra == "cure" and af.status:
                    af.status, af.sleep_turns = None, 0
                    ev.append({"t": "cure", "who": seat, "text": "%s 의 상태이상이 나았다!" % af.name})
                SM._heal(bt, af, seat, af.maxhp / 4.0, ev)
            self._flush()
        if k == "HAZE":
            for _p, x in self.actives():
                for s in x.stages:
                    x.stages[s] = 0
        if k == "PERISHSONG":
            for _p, x in self.actives():
                if x.alive() and not x.cond.get("perish") and not (x is not f and A.has(x, "SOUNDPROOF")):
                    x.cond["perish"] = 3

    def _spread_rest(self, who, user, ev, n0):
        """광역기의 나머지 대상 (Battle._use_one 이 첫 대상을 끝낸 뒤, 뒤처리 앞에 부른다).

        기술 이름 · PP · 못 움직임은 첫 대상에서 한 번 끝났다. 여기서는 대상마다 명중 · 방어 · 무효 · 데미지만.
        생명의구슬 반동과 자기 능력 변화(골드러시)는 한 번만.
        """
        r, cur, bt = self._rest, self._cur, self.bt
        if not r or not r["list"] or cur is None:
            return
        mine = [e for e in ev[n0:] if e.get("t") == "move" and e.get("who") == who]
        if not mine or mine[0].get("charge"):
            return                                    # 못 움직였다 · 모으는 턴이다
        self._rest = None
        key2 = getattr(bt, "_now_key", None) or r["real"]
        keys = (r["key"], r["real"], key2)
        last_before = getattr(bt, "last_before", None)
        upk = cur["at"]
        first = cur["target"]
        for tp in r["list"]:
            if not user.alive():
                break
            if not self._live(tp):
                continue
            new = ev[n0:]
            extra = {"_noorb": True}
            if r["md"].get("statSelf") and any(e.get("t") == "hit" and e.get("who") == who for e in new):
                extra["stat"] = []
            self._seat(upk, tp)
            self._set_mods(upk, tp, user, keys, r["md"], r["count"], extra)
            n1 = len(ev)
            bt._do_use(who, user, self.at(tp), key2, ev, called=True)
            for i in range(n1, len(ev)):              # 기술 이름은 한 번만
                if ev[i].get("t") == "move" and ev[i].get("who") == who:
                    del ev[i]
                    break
            bt._check_faint(ev)
            if bt._me.held or bt._foe.held:
                H.settle(bt, ev)                      # 탈출버튼 · 레드카드 (맞은 그 자리에서)
            self._flush()
        bt.last_before = last_before
        self._seat(upk, first)
        self._set_mods(upk, first, user, keys, r["md"], r["count"])
        # 생명의구슬: 한 대라도 맞혔으면 **다 때린 뒤에** 한 번 깎인다 (held.after_hit 과 같은 조건). 대상마다 깎으면
        # 체력이 얼마 안 남은 포켓몬이 첫 대상만 때리고 쓰러진다 (검토 11/25)
        if user.alive() and user.held == "LIFEORB" and MC.attacks(r["md"]) and not H._sheer(user, r["md"]) \
                and any(e.get("t") == "hit" and e.get("who") == who for e in ev[n0:]):
            H._chip(user, who, user.maxhp // 10, ev, "%s 은(는) 생명의구슬로 체력이 조금 깎였다!" % user.name)
            bt._check_faint(ev)

    def _instructed(self, f, key, ev):
        """지휘: 그 포켓몬이 방금 쓴 기술을 고른 대상에게 한 번 더 (PP 는 든다)."""
        pk = self.pos_of(f)
        if pk is None or not f.alive():
            return None
        seats = dict(self._seats)
        fk = self._fk_at(pk)
        self._instructing = True
        try:
            self._act(pk, {"key": key, "target": (self.t.get("aimed") or {}).get(fk)}, ev, instructed=True)
        finally:
            self._instructing = False
            self._reseat(seats)
        return None

    # ---------------- 아군 기술 (엔진에서는 "실패" 였던 것) ----------------
    def ally_move(self, k, who, user, ev):
        """도우미 · 날따름 · 사이드체인지 ... statusmoves.h_singles_fail 과 attackfx.cant_use(코칭)가 넘긴다."""
        bt, cur, t = self.bt, self._cur, self.t
        pk = cur["at"] if cur else self.pos_of(user)
        ally = self._ally(pk)
        af = self.at(ally) if ally else None

        def fail():
            ev.append({"t": "msg", "who": who, "text": "하지만 실패했다!"})
            return True

        def say(text):
            ev.append({"t": "msg", "who": who, "text": text})
            return True

        if k == "HELPINGHAND":
            if af is None:
                return fail()
            fk = self._fk_at(ally)
            t["helped"][fk] = int(t["helped"].get(fk, 0)) + 1
            return say("%s 은(는) %s 을(를) 도울 태세에 들어갔다!" % (user.name, af.name))
        if k in ("FOLLOWME", "RAGEPOWDER"):
            held = t["center"].get(pk[0])
            at = self._where(held["fk"]) if held else None
            if not (at and self._live(at)):           # 둘 다 쓰면 먼저 쓴 쪽이 끌어온다
                t["center"][pk[0]] = {"fk": self._fk_at(pk), "k": k}
            return say("%s 은(는) 주목의 대상이 되었다!" % user.name)
        if k == "SPOTLIGHT":
            tp = cur["target"] if cur else None
            if not tp or not self._live(tp):
                return fail()
            t["center"][tp[0]] = {"fk": self._fk_at(tp), "k": k}
            self._flush()
            ev.append({"t": "msg", "who": SIDE[tp[0]], "at": tp,
                       "text": "%s 은(는) 주목의 대상이 되었다!" % self.at(tp).name})
            return True
        if k == "ALLYSWITCH":
            if af is None:
                return fail()
            self._flush()
            p = self.side(pk[0])
            p.active[0], p.active[1] = p.active[1], p.active[0]
            ev.append({"t": "swap", "who": SIDE[pk[0]], "at": pk, "to": ally,
                       "text": "%s 와(과) %s 이(가) 자리를 바꿨다!" % (user.name, af.name)})
            if cur:
                cur["at"] = ally
                self._seat(ally, cur["target"] if cur["target"][0] != pk[0] else pk)
            return True
        if k in ("AFTERYOU", "QUASH"):
            tp = cur["target"] if cur else None
            fk = self._fk_at(tp) if tp else None
            if fk is None or fk not in t["queue"]:
                return fail()
            t["queue"].remove(fk)
            self._flush()
            if k == "AFTERYOU":
                t["queue"].insert(0, fk)
                ev.append({"t": "msg", "who": SIDE[tp[0]], "at": tp,
                           "text": "%s 은(는) 호의를 받아들였다!" % self.at(tp).name})
            else:
                t["queue"].append(fk)
                ev.append({"t": "msg", "who": SIDE[tp[0]], "at": tp,
                           "text": "%s 의 순서가 미뤄졌다!" % self.at(tp).name})
            return True
        if k in ("AROMATICMIST", "COACHING"):
            if af is None:
                return fail()
            self._flush()
            n0 = len(ev)
            for st, n in ([("spd", 1)] if k == "AROMATICMIST" else [("atk", 1), ("def", 1)]):
                bt._change_stat(af, st, n, ev, who, source=af)
            for e in ev[n0:]:                         # 오른 것은 아군이다 (앉은 자리가 아니다)
                if e.get("who") == who:               # 맞은편의 흉내허브 같은 것은 그 자리 그대로
                    e["at"] = ally
            return True
        if k == "DRAGONCHEER":
            if af is None or af.cond.get("focus"):
                return fail()
            af.cond["focus"] = True
            self._flush()
            ev.append({"t": "msg", "who": who, "at": ally, "text": "%s 은(는) 기합이 들어갔다!" % af.name})
            return True
        if k == "HOLDHANDS":
            if af is None:
                return fail()
            return say("%s 와(과) %s 은(는) 손을 맞잡았다!" % (user.name, af.name))
        return fail()

    # ---------------- 멈춤 (유턴) ----------------
    def _pause(self, ev):
        """물러나기로 한 포켓몬이 있으면 턴을 여기서 멈추고 누구를 낼지 묻는다. 멈췄으면 True."""
        if self.over:
            return False
        out = []
        for w in ("a", "b"):
            p = self.side(w)
            room = len(p.reserves())
            for pos in sorted(p.pending_out):
                f = self.mon(w, pos)
                if f is None or not f.alive() or room <= 0 or self.side(self.other(w)).wiped():
                    del p.pending_out[pos]
                    continue
                room -= 1
                out.append((w, pos))
        if not out:
            return False
        for w in ("a", "b"):
            p = self.side(w)
            mine = [pos for x, pos in out if x == w]
            if mine:
                p.need = mine
                ev.append({"t": "choose", "who": SIDE[w],
                           "text": "%s 님이 교체할 포켓몬을 고르고 있다..." % p.name})
            p.picks = None
        # 저장했다 깨어나도 턴이 이어지게, 이 턴에만 있는 것들을 같이 적어 둔다.
        fx = {}
        for pk, f in self.actives():
            fx[self._fk_at(pk)] = {"fl": bool(f.flinched), "hurt": f.hurt}
        self.mid = dict(self.t, fx=fx)
        return True

    def _wake(self, mid):
        """멈췄던 턴의 사정을 되살린다. 그사이 새로 나온 포켓몬은 이 턴에 아무것도 안 했다."""
        t = _blank_turn()
        for k in list(t) + ["aimed"]:
            if k in mid:
                t[k] = mid[k]
        self.t = t
        fx = mid.get("fx") or {}
        for pk, f in self.actives():
            st = fx.get(self._fk_at(pk))
            if st:
                f.flinched = bool(st.get("fl"))
                f.hurt = st.get("hurt")
        pa, pb = self._default_pair()
        self._seat(pa, pb)

    # ---------------- 턴 끝 ----------------
    def _end_turn(self, ev):
        """턴 끝: 독 · 날씨 같은 것, 쓰러진 자리 정리, 턴 수 제한.

        엔진의 턴 끝은 둘만 본다 - 짝을 지어 두 번 돈다. 첫 짝이 판(날씨 · 벽 · 희망사항)까지 맡고
        둘째 짝은 자기들 것만.
        """
        bt = self.bt
        if any(f.alive() for _pk, f in self.actives()):
            first = {}
            for w in ("a", "b"):
                both = [pk for pk in ("%s0" % w, "%s1" % w) if self.at(pk) is not None]
                live = [pk for pk in both if self._live(pk)]
                wish = self.field.side(SIDE[w]).get("wish") or {}
                wp = "%s%s" % (w, wish.get("pos")) if wish.get("pos") is not None else None
                first[w] = wp if (wp in live and int(wish.get("turns") or 0) <= 1) else (live or both)[0]
            self._seat(first["a"], first["b"])
            bt._end_of_turn(ev)
            bt._check_faint(ev)
            self._flush()
            rest, sides = {}, []
            for w in ("a", "b"):
                more = [pk for pk in ("%s0" % w, "%s1" % w) if pk != first[w] and self._live(pk)]
                rest[w] = more[0] if more else first[w]
                if more:
                    sides.append(SIDE[w])
            if sides:
                self._seat(rest["a"], rest["b"])
                bt._end_of_turn(ev, sides=tuple(sides), field=False)
                bt._check_faint(ev)
                self._flush()
        self._settle(ev)
        for w in ("a", "b"):
            self.side(w).picks = None
        if not self.over and self.turn >= self.max_turns:
            self._by_headcount(ev)

    # ---------------- 교체 ----------------
    def _switch(self, who, pos, slot, ev, trigger=True, carry=None, dragged=False):
        p, bt = self.side(who), self.bt
        pk = "%s%d" % (who, pos)
        seat = SIDE[who]
        old = self.mon(who, pos)
        face = self._facing(pk)
        if old is not None:
            if old.alive():
                A.on_switch_out(old)
                self._flush()
                ev.append({"t": "recall", "who": seat, "at": pk, "say": "drag" if dragged else "back",
                           "name": old.name,
                           "text": ("%s 은(는) 끌려 나갔다!" % old.name) if dragged
                           else "%s 님은 %s 을(를) 불러들였다!" % (p.name, old.name)})
            # 떠나는 포켓몬이 걸어 둔 것(헤롱헤롱 · 검은눈빛 · 조이기)을 푼다 - 맞은편 둘 다
            o = self.other(who)
            for fp in ("%s0" % o, "%s1" % o):
                if self.at(fp) is not None:
                    self._seat(pk, fp)
                    SM.on_leave(bt, seat)
            seeder = old.seed_by
            old.stages = dict((k, 0) for k in B.STAGE_KEYS)
            old.flinched = False
            old.locked = None
            old.clear_volatile()
            old.types_override = None
        p.active[pos] = slot
        new = self.mon(who, pos)
        if face is None:
            face = self._facing(pk)
        self._seat(pk, face)
        if carry:
            SM.apply_pass(new, carry.get("state"), shed=carry.get("mode") == "shed")
            if new.seeded and old is not None:
                new.seed_by = seeder
        ev.append(self._out_event(pk))
        bt.enter(seat, ev)
        self._flush()
        if trigger and new.alive():
            self._entry([pk], ev)

    def _move_switch(self, seat, mode, ev, key, state=None):
        """기술이 부른 교체 (유턴 · 울부짖기 ...). 해냈으면 True. seat 는 엔진의 자리 글자."""
        pk = self._seats.get(seat)
        if pk is None:
            return False
        who, pos = pk[0], int(pk[1])
        p = self.side(who)
        others = p.reserves()
        if not others:
            return False
        if mode == "drag":
            seats = dict(self._seats)
            self._switch(who, pos, self.rng.choice(others), ev, dragged=True)
            self._reseat(seats)                       # 같은 자리에 새 포켓몬이 앉았다
            return True
        # 누구를 낼지는 **사람이 고른다.** 그 기술이 끝나자마자 묻는다 (_pause).
        p.pending_out[pos] = {"mode": mode, "state": state, "key": key}
        ev.append({"t": "msg", "who": seat, "text": "%s 은(는) 돌아갈 준비를 한다!" % self.at(pk).name})
        return True

    # ---------------- 정리 ----------------
    def _give_up(self, who, ev):
        p = self.side(who)
        if p.forfeited or self.over:
            return
        p.forfeited = True
        p.picks = None
        p.need = []
        ev.append({"t": "msg", "text": "%s 님이 승부를 포기했다..." % p.name})
        self._finish(self.other(who), "forfeit", ev)

    def _settle(self, ev):
        """쓰러진 자리를 비우고, 채울 포켓몬이 있으면 고르게 한다. 한 편이 다 쓰러졌으면 끝."""
        if self.over:
            return
        self._flush()
        a_out, b_out = self.a.wiped(), self.b.wiped()
        if a_out and b_out:
            return self._finish("draw", "ko", ev)
        if a_out:
            return self._finish("b", "ko", ev)
        if b_out:
            return self._finish("a", "ko", ev)
        for w in ("a", "b"):
            p = self.side(w)
            p.pending_out = {}
            empty = [pos for pos in (0, 1) if p.active[pos] is None or not p.team[p.active[pos]].alive()]
            # 이미 비워 둔 자리는 그대로 둔다 (채울 포켓몬이 없어서 한 마리로 싸우는 중)
            fallen = [pos for pos in empty if p.active[pos] is not None]
            room = len(p.reserves())
            p.need = fallen[:room]
            for pos in fallen[room:]:
                p.active[pos] = None
            if p.need:
                p.picks = None
                ev.append({"t": "choose", "who": SIDE[w],
                           "text": "%s 님이 다음 포켓몬을 고르고 있다..." % p.name})
        pa, pb = self._default_pair()
        self._seat(pa, pb)

    def _by_headcount(self, ev):
        na, nb = len(self.a.alive_slots()), len(self.b.alive_slots())
        if na == nb:
            na = sum(f.hp / float(f.maxhp or 1) for f in self.a.team)
            nb = sum(f.hp / float(f.maxhp or 1) for f in self.b.team)
        self._finish("a" if na > nb else ("b" if na < nb else "draw"), "turns", ev)

    def _finish(self, result, reason, ev):
        self.over = True
        self.result = result
        self.reason = reason
        self.a.need, self.b.need = [], []
        self.mid = None
        text = "양쪽 모두 쓰러졌다..." if result == "draw" else "%s 님이 이겼다!" % self.side(result).name
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
    def _act_view(self, who, pos):
        """내 자리 하나의 고를 것. 고를 차례가 아니면 None."""
        pk = "%s%d" % (who, pos)
        f = self.at(pk)
        if f is None or not f.alive():
            return None
        bt, dex = self.bt, self.dex
        seat = SIDE[who]
        stuck = self._stuck(pk)
        self._seat(pk, self._facing(pk))
        moves = []
        for m in f.moves:
            md = dex.move(m) or {}
            tp = B.shown_type(md, f)
            aim = self._aim(f, m, md)
            moves.append({"key": m, "kr": dex.move_name(m), "type": tp, "typeKr": dex.type_name(tp),
                          "cat": md.get("cat"), "power": md.get("power"), "acc": md.get("acc"),
                          "pp": f.pp.get(m, 0), "maxpp": md.get("pp", 0), "desc": md.get("desc", ""),
                          "blocked": SM.restricted(bt, f, m), "aim": aim, "targets": self._choices(pk, aim)})
        if bt.usable(f) == [B.STRUGGLE]:
            moves.append({"key": B.STRUGGLE, "kr": B.STRUGGLE_MOVE["kr"], "type": "NORMAL", "typeKr": "노말",
                          "cat": "physical", "power": 50, "acc": 0, "pp": 1, "maxpp": 1, "desc": "",
                          "blocked": None, "aim": "random", "targets": []})
        tera = bt.can_tera(seat)
        return {"pos": pos, "slot": self.side(who).active[pos], "moves": moves,
                "locked": SM.locked_move(f, bt),
                "canSwitch": bool(self.side(who).reserves()) and not stuck, "noSwitch": stuck,
                "canMega": bt.can_mega(seat) is not None,
                "canTera": tera, "teraKr": dex.type_name(tera) if tera else None,
                # Z기술(공격)은 고른 하나만 때린다 - 원래 기술이 광역기여도 대상을 고른다
                "zMoves": [dict(z, targets=None if z.get("status") else self._choices(pk, "one"))
                           for z in bt.z_preview(seat)]}

    def _foe_mon(self, f, who):
        """상대 포켓몬의 보이는 모습. 조이기의 남은 턴은 **내 편이 건 것만** - 상대끼리 건 것(상대가 제 아군을
        조였다)의 턴 수는 건 쪽의 끈기갈고리손톱을 드러낸다 (1:1 에서는 상대를 조이는 것이 늘 나였다)."""
        out = self.view_mon(f, False)
        b = f.cond.get("bound") if out.get("bound") else None
        if b and b.get("by") != SIDE[who]:
            out["bound"] = dict(out["bound"], turns=None)
        return out

    def view(self, who):
        """그 사람 시점의 판 상태. me 가 늘 자기 쪽이다."""
        me, foe = self.side(who), self.side(self.other(who))
        seat = SIDE[who]
        choosing = bool(self.can_act(who) and self.phase() == "choose")
        acts = [self._act_view(who, pos) if choosing else None for pos in (0, 1)]
        out = {
            "fmt": "double",
            "turn": self.turn, "step": self.step, "maxTurns": self.max_turns,
            "over": self.over, "result": self.outcome(who), "reason": self.reason,
            "phase": self.phase(), "canAct": self.can_act(who),
            "weather": self.field.weather, "terrain": self.field.terrain,
            "gimmick": {"megaUsed": seat in self.mega_done, "teraUsed": seat in self.tera_done,
                        "zUsed": seat in self.z_done},
            "me": {"name": me.name, "active": list(me.active),
                   "team": [self.view_mon(f, True) for f in me.team],
                   "acts": acts, "switches": list(me.reserves()),
                   "chosen": me.picks is not None, "need": list(me.need),
                   "left": len(me.alive_slots())},
            "foe": {"name": foe.name, "active": list(foe.active),
                    "team": [self._foe_mon(f, who) for f in foe.team],
                    "chosen": foe.picks is not None, "need": list(foe.need),
                    "left": len(foe.alive_slots())},
        }
        pa, pb = self._default_pair()
        self._seat(pa, pb)
        return out

    def events_for(self, who, events):
        """일 목록을 그 사람 시점으로. 자리는 me0 · me1 · foe0 · foe1, b 에게는 편을 뒤집는다.

        상대가 내보낸 포켓몬의 도구 · 특성 · 고정된 기술은 뺀다 (상대의 지닌 도구는 알리지 않는다).
        """
        def rel(pk):
            if pk in POSITIONS:
                return ("me" if pk[0] == who else "foe") + pk[1]
            return pk

        out = []
        for e in events:
            x = dict(e) if who == "a" else flip(e)
            if "at" in x:
                x["at"] = rel(x["at"])
            if "to" in x:
                x["to"] = rel(x["to"])
            if "tos" in x:
                x["tos"] = [rel(p) for p in x["tos"]]
            t = x.get("t")
            mine = x.get("who") == "me"
            if t == "switch":
                if not mine:
                    x["mon"] = L.public_mon(x.get("mon"))
                x["text"] = ("가랏! %s!" if mine else "상대는 %s 을(를) 내보냈다!") % x.get("name")
            elif t == "recall" and x.get("say") == "back":
                x["text"] = ("%s, 돌아와!" if mine else "상대는 %s 을(를) 불러들였다!") % x.get("name")
            elif t == "intro":
                x["text"] = "%s 님과의 더블배틀이 시작됐다!" % x.get("foe")
            out.append(x)
        return out

    # ---------------- 저장 ----------------
    def _dump_side(self, p):
        return {"uid": p.uid, "name": p.name, "active": list(p.active),
                "team": [self._dump_fighter(f) for f in p.team],
                "picks": p.picks, "need": list(p.need),
                "pendingOut": dict((str(k), v) for k, v in p.pending_out.items()),
                "forfeited": p.forfeited, "auto": p.auto}

    def _load_side(self, d):
        p = Player2(d["uid"], d["name"], [self._load_fighter(x) for x in d["team"]])
        p.active = [None if x is None else int(x) for x in d["active"]]
        p.picks = d.get("picks")
        p.need = [int(x) for x in d.get("need") or []]
        p.pending_out = dict((int(k), v) for k, v in (d.get("pendingOut") or {}).items())
        p.forfeited = bool(d.get("forfeited"))
        p.auto = int(d.get("auto") or 0)
        return p

    def dump(self):
        st = self.rng.getstate()
        return {"v": 1, "fmt": "double", "turn": self.turn, "step": self.step, "over": self.over,
                "result": self.result, "reason": self.reason,
                "started": self.started, "maxTurns": self.max_turns,
                "a": self._dump_side(self.a), "b": self._dump_side(self.b),
                "field": self.field.dump(),
                "keystone": dict(self.keystone), "megaDone": sorted(self.mega_done),
                "gimmick": B.gimmick_dump(self),
                "mid": self.mid,
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
        self.keystone = dict(d.get("keystone") or {"me": False, "foe": False})
        self.mega_done = set(d.get("megaDone") or [])
        B.gimmick_load(self, d.get("gimmick"))
        self.turn = int(d["turn"])
        self.step = int(d.get("step", d["turn"]) or 0)
        self.over = bool(d["over"])
        self.result = d.get("result")
        self.reason = d.get("reason")
        self.started = bool(d.get("started"))
        self.mid = d.get("mid")
        self._wire()
        self.bt.turn_no = self.turn
        return self
