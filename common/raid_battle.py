# -*- coding: utf-8 -*-
"""레이드 — 여럿(3~6인)이 보스 하나를 상대하는 판.

야생(battle.Battle)은 1:1, 관장(trainer_battle)은 사람 하나와 트레이너
하나다. 레이드는 **사람이 여럿이고 상대가 하나**다.

## 어떻게 여럿을 한 판에 세우나

Battle 을 고치지 않는다. 대신 **사람 수만큼 Battle 을 만들고 보스를
공유한다.**

    bt[0].me = 1번 사람의 포켓몬   bt[0].foe = 보스
    bt[1].me = 2번 사람의 포켓몬   bt[1].foe = 보스   (같은 Fighter 객체)
    ...

보스가 같은 객체라 누가 때리든 체력이 한 군데서 줄고, 판(Field)도 하나를
같이 쓰므로 날씨·필드·리플렉터가 전원에게 통한다. 데미지·특성·도구·
상태이상 계산은 전부 원래 엔진 그대로다.

턴 끝 처리만 손을 봤다(battle._end_of_turn 의 sides/field). 그대로 사람
수만큼 부르면 보스의 화상 데미지가 사람 수만큼 들어가고 날씨의 남은 턴도
그만큼 줄어든다. 첫 사람이 보스와 판을 맡고 나머지는 자기 쪽만 한다.

## 한 라운드

    1. 모두가 이번에 할 것을 고른다 (기술 / 교체). 제한 시간을 넘긴
       사람은 서버가 대신 고른다 (raid.AUTO — 가장 센 기술).
    2. 교체가 먼저, 그다음 기술을 **우선도 -> 스피드** 순으로 쓴다.
       보스는 4인 이상이면 한 라운드에 두 번 움직인다.
    3. 턴 끝 (화상·독·날씨·먹다남은음식 ...)
    4. 쓰러진 사람은 그 라운드를 쉬고, 다음 라운드에 다음 포켓몬이 나온다.

## 기믹

    보호막  체력이 절반 아래로 처음 내려가면 막이 선다. 정해진 라운드
            안에 다 깎지 못하면 보스가 전원에게 큰 한 방을 쓴다.
    분노    체력이 1/4 아래로 내려가면 공격·특수공격이 오른다 (한 번).
    날씨    보스 타입에 맞는 날씨가 판 내내 깔린다.

## 저장

관장과 같다. 라운드마다 DB 에 통째로 자고 다음 요청에서 깬다. 난수
상태까지 남기므로 같은 라운드를 다시 보내 결과를 골라 먹을 수 없다.
"""
import random

from . import abilities as A
from . import battle as B
from . import field as FD
from . import held as H
from . import movecalc as MC
from . import statusmoves as SM

TEAM_MAX = 6
STATS = ("hp", "atk", "def", "spa", "spd", "spe")

# 보스가 전원에게 쓰는 한 방. 최대 체력의 이만큼을 깎는다.
ROAR_RATIO = 0.45
# 보호막이 버텨야 하는 라운드 수와, 그 몇 배로 크기를 잡을지.
#
# **최대 체력의 몇 %로 두면 안 된다.** 보스마다 맷집이 딴판이라(테오키스는
# 방어 50, 루기아는 130/154) 같은 30% 여도 한쪽은 한 라운드에 녹고 한쪽은
# 세 라운드로 못 깬다. 인원수로 곱하는 것도 안 된다 - 최대 체력이 이미
# 인원수만큼 늘어 있어서 두 번 곱한 꼴이 되고, 6인이면 아무도 못 깬다.
#
# 그래서 **여기까지 오면서 팀이 라운드당 얼마나 깎았는지**로 잰다. 물몸
# 보스든 단단한 보스든, 3인이든 6인이든 늘 비슷한 만큼 버틴다 - 봇으로
# 여섯 보스 x 3/4/6인을 재보면 열에 여덟쯤 깬다(tools/sim_raid.py 와 같은 봇).
SHIELD_ROUNDS = 3
SHIELD_PACE = 0.85          # 라운드당 깎는 양 x 라운드 수 x 이 값
SHIELD_MIN = 0.08           # 최대 체력 대비 하한
SHIELD_MAX = 0.45           # 상한

# 보스 타입 -> 깔리는 날씨
WEATHER_BY_TYPE = {
    "FIRE": "sun", "WATER": "rain", "ROCK": "sand", "GROUND": "sand",
    "ICE": "hail", "STEEL": "sand",
}


def leveled(mon, level):
    """레벨만 맞춘 사본. **개체값·노력치·성격·도구·기술은 그대로다.**

    레이드는 전원이 같은 레벨로 싸운다 (raid.TEAM_LEVEL). 높은 쪽은
    내리고 낮은 쪽은 올린다 - 랭크 배틀(pvp.capped)은 내리기만 하지만,
    여기서는 Lv.30 과 Lv.100 이 한 방에 서므로 올리지 않으면 낮은 쪽이
    한 대에 쓰러져 구경만 하게 된다.

    원본을 고치지 않는다. 경험치는 그대로라 판이 끝나도 레벨은 안 바뀐다.
    """
    m = dict(mon)
    m["level"] = int(level)
    return m


class RaidDuel(B.Battle):
    """쓰러져도 판을 안 끝내는 Battle. 끝내는 건 RaidBattle 이 한다."""

    raid = None

    def _check_faint(self, ev):
        for who, f in (("foe", self.foe), ("me", self.me)):
            if f is not None and not f.alive() and not f.ab.get("fainted"):
                f.ab["fainted"] = True
                ev.append({"t": "faint", "who": who,
                           "text": "%s 은(는) 쓰러졌다!" % f.name})

    def _suppress_weather(self):
        """날씨부정·에어록은 **판에 서 있는 누구라도** 갖고 있으면 통한다.

        Battle 의 것을 그대로 쓰면 이 사람 저 사람의 Battle 이 서로 덮어써서
        마지막에 계산한 사람 기준이 된다.
        """
        r = getattr(self, "raid", None)
        if r is None:
            return B.Battle._suppress_weather(self)
        self.field.suppressed = r.weather_off()


class Player(object):
    """레이드에 들어온 사람 하나."""

    def __init__(self, uid, name, team):
        self.uid = int(uid)
        self.name = name or "?"
        self.team = team                 # Fighter 목록
        self.slot = next((i for i, f in enumerate(team) if f.alive()), 0)
        self.bt = None
        self.choice = None               # 이번 라운드에 할 것
        self.damage = 0                  # 보스에게 넣은 누적 데미지
        self.left = False                # 스스로 나갔다
        self.auto = 0                    # 시간 안에 못 고른 횟수

    @property
    def mon(self):
        return self.team[self.slot]

    def alive_slots(self):
        return [i for i, f in enumerate(self.team) if f.alive()]

    def wiped(self):
        return not self.alive_slots()

    def playing(self):
        """이번 라운드에 움직일 수 있는가.

        쓰러져도 **그 라운드가 끝나면서** 다음 포켓몬이 나오므로(_settle),
        '쉬는 중' 이라는 상태는 따로 두지 않는다. 한 라운드를 쉬는 것은
        쓰러진 그 라운드의 남은 차례뿐이다.
        """
        return not self.left and not self.wiped()

    def counts(self):
        """아직 판에 남아 있는가 (보상·승패를 셀 때)."""
        return not self.left and not self.wiped()


class RaidBattle(object):

    def __init__(self, dex, boss_mon, players, hp_mult=1.0, max_rounds=15,
                 double_from=4, rng=None):
        """players: [(uid, 이름, [mon ...])] — mon 은 이미 레벨을 맞춘 것."""
        if not players:
            raise ValueError("참가자가 없습니다.")
        self.dex = dex
        self.rng = rng or random.Random()
        self.max_rounds = int(max_rounds)
        self.double_from = int(double_from)
        self.field = FD.Field()
        self.boss = self._fighter(boss_mon)
        # 체력만 인원수에 맞춰 늘린다. 공격력은 그대로다 - 그쪽까지 올리면
        # 사람이 많을수록 더 아프게 맞아서 늘린 보람이 없다.
        self.boss.maxhp = max(1, int(round(self.boss.maxhp * float(hp_mult))))
        self.boss.hp = self.boss.maxhp
        self.hp_mult = float(hp_mult)
        self.players = []
        for uid, name, mons in players:
            team = [self._fighter(m) for m in mons[:TEAM_MAX]]
            if not team:
                raise ValueError("%s 님의 포켓몬이 없습니다." % (name or uid))
            self.players.append(Player(uid, name, team))
        self.round = 0
        self.over = False
        self.result = None               # won / lost / timeout
        self.started = False
        self.shield = None               # {"hp":, "max":, "rounds":}
        self.shielded_once = False
        self.raged = False
        self.roar_next = False           # 보호막을 못 깨서 다음 라운드에 한 방
        self._wire()

    # ---------------- 만들기 ----------------
    def _fighter(self, mon):
        f = B.Fighter(self.dex, mon)
        f.ability_on = True
        return f

    def _wire(self):
        """사람마다 Battle 을 하나씩. 보스와 판은 같은 것을 나눠 쓴다."""
        for i, p in enumerate(self.players):
            bt = RaidDuel(self.dex, p.mon, self.boss, self.rng, ai="trainer",
                          field=self.field)
            bt.raid = self
            bt.teams = {"me": p.team, "foe": [self.boss]}
            bt.foe_prefix = ""
            bt.max_turns = 10 ** 9
            bt.kind = "gym"              # 교체가 되는 판
            bt.switcher = self._make_switcher(i)
            bt.turn_no = self.round
            p.bt = bt
        self._sync_weather()

    def _make_switcher(self, i):
        def go(who, mode, ev, key, state=None):
            return self._move_switch(i, who, mode, ev, key, state)
        return go

    def weather_off(self):
        """날씨부정·에어록이 판에 서 있는가."""
        on = [self.boss] + [p.mon for p in self.players if p.counts()]
        return any(f is not None and f.alive() and A.has(f, "CLOUDNINE", "AIRLOCK")
                   for f in on)

    def _sync_weather(self):
        self.field.suppressed = self.weather_off()

    # ---------------- 시작 ----------------
    def start(self):
        if self.started:
            return []
        self.started = True
        ev = [{"t": "intro", "text": "%s 이(가) 나타났다!" % self.boss.name,
               "boss": self.boss.mon["species"]}]
        w = WEATHER_BY_TYPE.get((self.boss.types() or [None])[0])
        if w:
            self.field.weather = w
            self.field.weather_turns = self.max_rounds + 2
            ev.append({"t": "weather", "weather": w,
                       "text": FD.WEATHER_START.get(w, "날씨가 바뀌었다!")})
        for i, p in enumerate(self.players):
            ev.append(self._out_event(i, "가랏! %s!" % p.mon.name))
        self._entry_abilities(ev)
        return ev

    def _out_event(self, i, text=None):
        p = self.players[i]
        return {"t": "switch", "who": "me", "p": i, "slot": p.slot,
                "mon": self.side(p.mon, True),
                "text": text or ("%s 이(가) %s 을(를) 내보냈다!" % (p.name, p.mon.name))}

    def _entry_abilities(self, ev, only=None, fresh=True):
        """나온 순간의 특성 (위협·다운로드 ...). 빠른 쪽부터."""
        pair = [(i, p) for i, p in enumerate(self.players)
                if p.counts() and (only is None or i in only)]
        pair.sort(key=lambda x: -x[1].mon.stat("spe"))
        for i, p in pair:
            bt = p.bt
            p.mon.ab["down"] = sum(1 for f in p.team if not f.alive())
            got = []
            A.on_switch_in(bt, p.mon, "me", got)
            SM.on_enter_abilities(bt, p.mon, "me", got)
            if not fresh:
                p.mon.ab["fresh"] = False
            ev.extend(self._tag(got, i))
        if only is None:
            got = []
            A.on_switch_in(self.players[0].bt, self.boss, "foe", got)
            SM.on_enter_abilities(self.players[0].bt, self.boss, "foe", got)
            ev.extend(self._tag(got, 0))
        self._sync_weather()

    @staticmethod
    def _tag(events, i):
        """이 사람의 Battle 이 낸 일이라고 표시한다. 화면이 누구 칸을 움직일지 안다."""
        for e in events:
            e.setdefault("p", i)
        return events

    # ---------------- 고르기 ----------------
    def choose(self, i, kind, value=None):
        """이번 라운드에 할 것을 적어 둔다. 라운드는 아직 안 돈다."""
        p = self.players[i]
        if self.over:
            raise ValueError("이미 끝난 레이드입니다.")
        if not p.playing():
            raise ValueError("이번 라운드에는 움직일 수 없습니다.")
        if kind == "move":
            key = value or ""
            if key != B.STRUGGLE:
                if key not in p.mon.pp:
                    raise ValueError("그 기술은 배우지 않았습니다.")
                if p.mon.pp.get(key, 0) <= 0:
                    raise ValueError("그 기술은 PP 가 없습니다.")
                why = SM.restricted(p.bt, p.mon, key)
                enc = p.mon.cond.get("encore")
                if why and not (enc and enc.get("move") == key):
                    raise ValueError(why)
            p.choice = ("move", key)
        elif kind == "switch":
            slot = int(value)
            if slot == p.slot or slot not in p.alive_slots():
                raise ValueError("그 포켓몬으로는 바꿀 수 없습니다.")
            if SM.trapped(p.bt, p.mon):
                raise ValueError("%s 은(는) 붙잡혀 있어서 교체할 수 없습니다." % p.mon.name)
            p.choice = ("switch", slot)
        else:
            raise ValueError("무엇을 할지 알 수 없습니다.")
        return p.choice

    def auto_choice(self, i):
        """시간 안에 못 고른 사람 대신. 지금 가장 센 기술."""
        p = self.players[i]
        bt = p.bt
        best, score = None, -1.0
        for key in bt.usable(p.mon):
            md = bt.move_of(key)
            if not MC.attacks(md):
                continue
            d = bt.estimate(p.mon, self.boss, key)
            if d > score:
                best, score = key, d
        return ("move", best or bt.usable(p.mon)[0])

    def ready(self):
        """움직일 수 있는 사람이 모두 골랐는가."""
        return all(p.choice is not None for p in self.players if p.playing())

    def waiting(self):
        return [i for i, p in enumerate(self.players)
                if p.playing() and p.choice is None]

    def leave(self, i):
        """스스로 나간다. 남은 사람끼리 계속한다."""
        p = self.players[i]
        if p.left:
            return []
        p.left = True
        p.choice = None
        ev = [{"t": "leave", "p": i, "who": "me",
               "text": "%s 님이 레이드에서 물러났다." % p.name}]
        if not any(x.counts() for x in self.players):
            self._finish("lost", ev)
        return ev

    # ---------------- 한 라운드 ----------------
    def resolve(self):
        """한 라운드를 돈다. 일어난 일 목록."""
        if self.over:
            return [{"t": "over", "result": self.result}]
        if not self.started:
            return self.start()
        ev = []
        self.round += 1
        for p in self.players:
            p.bt.turn_no = self.round
            p.bt.begin_turn()
        self._sync_weather()

        # 못 고른 사람은 서버가 대신 고른다
        for i, p in enumerate(self.players):
            if p.playing() and p.choice is None:
                p.choice = self.auto_choice(i)
                p.auto += 1

        # 1) 보호막을 못 깼으면 먼저 한 방
        if self.roar_next:
            self.roar_next = False
            self._roar(ev)

        # 2) 교체
        for i, p in enumerate(self.players):
            if p.playing() and p.choice and p.choice[0] == "switch":
                self._switch(i, p.choice[1], ev)

        # 3) 기술
        for actor in self._order():
            if self.over:
                break
            if actor[0] == "boss":
                self._boss_turn(ev)
            else:
                self._player_turn(actor[1], ev)
            self._check_gimmicks(ev)

        # 4) 턴 끝. 첫 사람이 보스와 판을 맡는다 (나머지가 또 하면 두 번 센다)
        #    **보스가 여기서 잃는 체력(화상·모래바람·씨뿌리기)도 막이 받는다.**
        #    안 그러면 막이 서 있는데 체력이 줄어든다.
        boss_hp = self.boss.hp
        eot = []
        first = True
        for i, p in enumerate(self.players):
            if not p.counts():
                continue
            got = []
            p.bt._end_of_turn(got, sides=("me", "foe") if first else ("me",),
                              field=first)
            eot.extend(self._tag(got, i))
            first = False
        if first:                    # 아무도 안 남았다 - 보스 쪽만 따로 돌린다
            got = []
            self.players[0].bt._end_of_turn(got, sides=("foe",), field=True)
            eot.extend(self._tag(got, 0))
        self._guard(boss_hp, eot)
        ev.extend(eot)

        self._check_gimmicks(ev)
        self._settle(ev)
        for p in self.players:
            p.choice = None
        if not self.over and self.round >= self.max_rounds:
            self._finish("timeout", ev)
        return ev

    def _order(self):
        """이번 라운드에 움직이는 차례. [("me", i) / ("boss", n)]"""
        rows = []
        for i, p in enumerate(self.players):
            if not p.playing() or not p.choice or p.choice[0] != "move":
                continue
            md = p.bt.move_of(p.choice[1])
            pr = SM.priority(p.bt, p.mon, md) + A.priority_bonus(p.mon, md)
            rows.append((pr, p.bt.speed("me"), ("me", i)))
        n = sum(1 for p in self.players if p.counts())
        hits = 2 if n >= self.double_from else 1
        bt0 = self.players[0].bt
        for k in range(hits):
            # 보스의 기술은 제 차례에 고른다. 순서를 정할 때는 우선도 0 으로 본다.
            rows.append((0, bt0.speed("foe") - k, ("boss", k)))
        trick = self.field.room("trickroom")
        rows.sort(key=lambda r: (-r[0], r[1] if trick else -r[1],
                                 self.rng.random()))
        return [r[2] for r in rows]

    def _player_turn(self, i, ev):
        p = self.players[i]
        if not p.playing() or not p.mon.alive() or not self.boss.alive():
            return
        if not p.choice or p.choice[0] != "move":
            return
        key = p.choice[1]
        if key != B.STRUGGLE and p.mon.pp.get(key, 0) <= 0:
            key = p.bt.usable(p.mon)[0]
        got = []
        if p.mon.held:
            key = H.force_move(p.mon, key, got, "me")
        before = self.boss.hp
        p.bt._use("me", p.mon, self.boss, key, got)
        p.damage += self._guard(before, got, i)
        ev.extend(self._tag(got, i))

    def _guard(self, before, ev, i=None):
        """보호막이 서 있으면 방금 깎인 체력을 막으로 돌린다. 깎인 양.

        **체력을 되돌리는 것으로 끝나지 않는다.** 이미 만들어진 일(events)에
        보스의 체력이 적혀 있어서, 그대로 두면 화면이 체력바를 내렸다가
        판이 끝날 때 도로 올린다 - 막이 있는데 체력이 줄어드는 것처럼 보인다.
        여기서 같이 고친다.

        막보다 큰 한 방은 **넘친 만큼 체력으로 들어간다.** 안 그러면 큰
        기술이 막에 먹혀 사라진 것처럼 보인다.
        """
        dealt = max(0, before - self.boss.hp)
        if not self.shield or not dealt:
            return dealt
        took = min(dealt, self.shield["hp"])
        over = dealt - took
        self.shield["hp"] -= took
        self.boss.hp = max(0, before - over)
        broke = self.shield["hp"] <= 0
        line = {"t": "shield", "damage": took, "hp": self.shield["hp"],
                "maxhp": self.shield["max"],
                "text": "보호막이 %s 깎였다!" % format(took, ",")}
        if i is not None:
            line["p"] = i
        ev.append(line)
        if broke:
            self.shield = None
            ev.append({"t": "shieldBreak",
                       "text": "%s 의 보호막이 깨졌다!" % self.boss.name})
        self._fix_boss_hp(ev)
        return dealt

    def _fix_boss_hp(self, ev):
        """일어난 일에 적힌 보스 체력을 지금 값으로 맞춘다 (막이 먹은 뒤).

        쓰러졌다고 적어 둔 것도 걷어낸다 - 막에 막혀 안 쓰러졌는데 화면에서
        쓰러지는 연출이 나가면 안 된다.
        """
        alive = self.boss.alive()
        out = []
        for e in ev:
            t = e.get("t")
            mine = (e.get("target") == "foe") if t == "hit" else (e.get("who") == "foe")
            if t == "faint" and mine and alive:
                continue                     # 안 쓰러졌다
            if mine and "hp" in e:
                e["hp"] = self.boss.hp
            out.append(e)
        if alive:
            self.boss.ab.pop("fainted", None)
        if len(out) != len(ev):
            ev[:] = out

    def _boss_turn(self, ev):
        if not self.boss.alive() or self.over:
            return
        targets = [i for i, p in enumerate(self.players)
                   if p.playing() and p.mon.alive()]
        if not targets:
            return
        i = self._pick_target(targets)
        p = self.players[i]
        bt = p.bt
        key = bt.choose_for(self.boss, p.mon, "trainer")
        got = []
        if self.boss.held:
            key = H.force_move(self.boss, key, got, "foe")
        bt._use("foe", self.boss, p.mon, key, got)
        ev.extend(self._tag(got, i))

    def _pick_target(self, targets):
        """많이 때린 사람을 노린다. 늘 그러면 한 사람만 죽으므로 절반만."""
        if len(targets) == 1 or self.rng.random() < 0.4:
            return self.rng.choice(targets)
        return max(targets, key=lambda i: self.players[i].damage)

    def _roar(self, ev):
        """보호막을 못 깼을 때의 한 방. 살아 있는 전원이 맞는다."""
        ev.append({"t": "roar", "who": "foe",
                   "text": "%s 이(가) 크게 포효했다!" % self.boss.name})
        for i, p in enumerate(self.players):
            if not p.playing() or not p.mon.alive():
                continue
            f = p.mon
            d = max(1, int(f.maxhp * ROAR_RATIO))
            if A.has(f, "MAGICGUARD"):
                continue
            f.hp = max(0, f.hp - d)
            ev.append({"t": "chip", "who": "me", "p": i, "damage": d,
                       "hp": f.hp, "maxhp": f.maxhp,
                       "text": "%s 은(는) 포효에 휩쓸렸다!" % f.name})
            if not f.alive():
                f.ab["fainted"] = True
                ev.append({"t": "faint", "who": "me", "p": i,
                           "text": "%s 은(는) 쓰러졌다!" % f.name})

    # ---------------- 기믹 ----------------
    def _check_gimmicks(self, ev):
        if self.over or not self.boss.alive():
            return
        frac = self.boss.hp / float(self.boss.maxhp or 1)
        if not self.shielded_once and not self.shield and frac <= 0.5:
            self.shielded_once = True
            size = self.shield_size()
            self.shield = {"hp": size, "max": size, "rounds": SHIELD_ROUNDS,
                           "from": self.round}
            ev.append({"t": "shieldUp", "hp": size, "maxhp": size,
                       "rounds": SHIELD_ROUNDS, "left": SHIELD_ROUNDS,
                       "text": "%s 이(가) 보호막을 펼쳤다! %d라운드 안에 깨야 한다!"
                               % (self.boss.name, SHIELD_ROUNDS)})
        if not self.raged and frac <= 0.25:
            self.raged = True
            got = []
            bt = self.players[0].bt
            bt._change_stat(self.boss, "atk", 2, got, "foe")
            bt._change_stat(self.boss, "spa", 2, got, "foe")
            ev.append({"t": "rage", "who": "foe",
                       "text": "%s 이(가) 분노하기 시작했다!" % self.boss.name})
            ev.extend(self._tag(got, 0))

    def shield_size(self):
        """이번 보호막의 크기. 팀이 라운드당 깎아 온 양으로 잰다."""
        done = max(1, self.boss.maxhp - self.boss.hp)
        per_round = done / float(max(1, self.round))
        size = int(per_round * SHIELD_ROUNDS * SHIELD_PACE)
        lo = int(self.boss.maxhp * SHIELD_MIN)
        hi = int(self.boss.maxhp * SHIELD_MAX)
        return max(1, min(max(size, lo), hi))

    # ---------------- 교체 ----------------
    def _switch(self, i, slot, ev, dragged=False):
        p = self.players[i]
        old = p.mon
        got = []
        if old.alive():
            A.on_switch_out(old)
            got.append({"t": "recall", "who": "me",
                        "text": ("%s 은(는) 끌려 나갔다!" % old.name) if dragged
                        else ("%s, 돌아와!" % old.name)})
        SM.on_leave(p.bt, "me")
        old.stages = dict((k, 0) for k in B.STAGE_KEYS)
        old.flinched = False
        old.locked = None
        old.clear_volatile()
        old.types_override = None
        p.slot = slot
        p.bt.me = p.mon
        got.append(self._out_event(i))
        p.bt.enter("me", got)
        ev.extend(self._tag(got, i))
        if p.mon.alive():
            self._entry_abilities(ev, only=[i], fresh=False)

    def _move_switch(self, i, who, mode, ev, key, state=None):
        """기술이 부른 교체 (유턴·울부짖기 ...). 해냈으면 True."""
        if who == "foe":
            return False                 # 보스는 하나뿐이라 바꿀 수 없다
        p = self.players[i]
        others = [s for s in p.alive_slots() if s != p.slot]
        if not others:
            return False
        slot = self.rng.choice(others) if mode == "drag" else others[0]
        carry = {"mode": mode, "state": state} if mode in ("pass", "shed") else None
        self._switch(i, slot, ev, dragged=(mode == "drag"))
        if carry:
            SM.apply_pass(p.mon, carry.get("state"), shed=carry.get("mode") == "shed")
        return True

    # ---------------- 정리 ----------------
    def _settle(self, ev):
        if not self.boss.alive():
            return self._finish("won", ev)
        # 쓰러진 사람의 다음 포켓몬은 **이 라운드가 끝나는 지금** 나온다.
        # 다음 라운드가 시작할 때 내보내면, 그 사람은 화면에서 '쉬는 중' 인
        # 채로 고를 기회를 못 받고 서버가 대신 기술을 골라 버린다.
        for i, p in enumerate(self.players):
            if p.counts() and not p.mon.alive():
                p.choice = None
                self._switch(i, p.alive_slots()[0], ev)
        if not any(p.counts() for p in self.players):
            return self._finish("lost", ev)
        if self.shield and self.round - self.shield["from"] >= self.shield["rounds"]:
            self.shield = None
            self.roar_next = True
            ev.append({"t": "shieldHeld",
                       "text": "보호막을 깨지 못했다! %s 이(가) 힘을 모은다..." % self.boss.name})

    def _finish(self, result, ev):
        self.over = True
        self.result = result
        text = {"won": "%s 을(를) 쓰러뜨렸다!" % self.boss.name,
                "lost": "모두 쓰러졌다...",
                "timeout": "%s 은(는) 사라져 버렸다..." % self.boss.name}[result]
        ev.append({"t": "over", "result": result, "text": text})

    def ranking(self):
        """기여도 순. [(자리, uid, 이름, 데미지)]"""
        rows = [(i, p.uid, p.name, p.damage) for i, p in enumerate(self.players)]
        rows.sort(key=lambda r: -r[3])
        return rows

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
            "ability": f.ability,
            "abilityKr": dex.ability_name(f.ability) if f.ability else None,
        }
        if mine:
            out["id"] = f.mon.get("id")
            out["held"] = f.held
            out["heldKr"] = H.name(f.held) if f.held else None
            out["locked"] = f.locked
        return out

    def moves_of(self, i):
        p = self.players[i]
        f, bt = p.mon, p.bt
        dex = self.dex
        out = []
        for m in f.moves:
            md = dex.move(m) or {}
            out.append({"key": m, "kr": dex.move_name(m), "type": md.get("type"),
                        "typeKr": dex.type_name(md.get("type")), "cat": md.get("cat"),
                        "power": md.get("power"), "acc": md.get("acc"),
                        "pp": f.pp.get(m, 0), "maxpp": md.get("pp", 0),
                        "desc": md.get("desc", ""),
                        "blocked": SM.restricted(bt, f, m)})
        if not any(x["pp"] > 0 for x in out):
            out.append({"key": B.STRUGGLE, "kr": "몸부림", "type": "NORMAL",
                        "typeKr": "노말", "cat": "physical", "power": 50, "acc": 0,
                        "pp": 1, "maxpp": 1, "desc": "", "blocked": None})
        return out

    def view(self, me=None):
        """화면에 줄 판 상태. me 가 있으면 그 사람의 기술·파티까지 싣는다."""
        boss = self.side(self.boss, False)
        boss["shield"] = None
        if self.shield:
            boss["shield"] = dict(self.shield)
            # 몇 라운드 남았나. 화면이 세는 것보다 여기서 주는 쪽이 안 어긋난다.
            boss["shield"]["left"] = max(0, self.shield["rounds"]
                                         - (self.round - self.shield["from"]))
        boss["raged"] = self.raged
        players = []
        for i, p in enumerate(self.players):
            players.append({
                "index": i, "uid": p.uid, "name": p.name, "slot": p.slot,
                "mon": self.side(p.mon, False),
                "left": p.left, "out": p.wiped(),
                "chosen": p.choice is not None, "damage": p.damage,
                "alive": len(p.alive_slots()), "team": len(p.team),
            })
        out = {"round": self.round, "maxRounds": self.max_rounds,
               "over": self.over, "result": self.result, "started": self.started,
               "boss": boss, "players": players,
               "weather": self.field.weather, "terrain": self.field.terrain,
               "bossHits": 2 if sum(1 for p in self.players if p.counts()) >= self.double_from else 1}
        if me is not None:
            p = self.players[me]
            out["me"] = {"index": me, "slot": p.slot,
                         "moves": self.moves_of(me),
                         "team": [self.side(f, True) for f in p.team],
                         "choice": list(p.choice) if p.choice else None,
                         "canAct": p.playing()}
        return out

    # ---------------- 저장 ----------------
    @staticmethod
    def _dump_fighter(f):
        return {"mon": f.mon, "hp": f.hp, "maxhp": f.maxhp, "pp": f.pp,
                "status": f.status, "stages": f.stages, "sleep": f.sleep_turns,
                "held": f.held_state(), "abil": A.state(f), "vol": f.volatile()}

    def _load_fighter(self, d):
        # 보스는 최대 체력을 늘려 둔 상태다. Fighter 는 종족값으로 다시
        # 계산하므로 체력을 먼저 비워 두고 저장해 둔 값으로 덮는다.
        f = B.Fighter(self.dex, d["mon"], None, d["pp"], d["status"])
        f.maxhp = int(d.get("maxhp") or f.maxhp)
        f.hp = max(0, min(f.maxhp, int(d["hp"])))
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
            "v": 1, "round": self.round, "over": self.over, "result": self.result,
            "started": self.started, "maxRounds": self.max_rounds,
            "doubleFrom": self.double_from, "hpMult": self.hp_mult,
            "boss": self._dump_fighter(self.boss),
            "shield": dict(self.shield) if self.shield else None,
            "shieldedOnce": self.shielded_once, "raged": self.raged,
            "roarNext": self.roar_next,
            "players": [{
                "uid": p.uid, "name": p.name, "slot": p.slot,
                "team": [self._dump_fighter(f) for f in p.team],
                "damage": p.damage, "left": p.left,
                "auto": p.auto, "choice": list(p.choice) if p.choice else None,
            } for p in self.players],
            "field": self.field.dump(),
            "rng": [st[0], list(st[1]), st[2]],
        }

    @classmethod
    def load(cls, dex, d):
        self = cls.__new__(cls)
        self.dex = dex
        self.rng = random.Random()
        r = d["rng"]
        self.rng.setstate((r[0], tuple(r[1]), r[2]))
        self.field = FD.Field.load(d.get("field"))
        self.max_rounds = int(d.get("maxRounds") or 15)
        self.double_from = int(d.get("doubleFrom") or 4)
        self.hp_mult = float(d.get("hpMult") or 1.0)
        self.boss = self._load_fighter(d["boss"])
        self.players = []
        for x in d["players"]:
            p = Player(x["uid"], x["name"], [self._load_fighter(t) for t in x["team"]])
            p.slot = int(x["slot"])
            p.damage = int(x.get("damage") or 0)
            p.left = bool(x.get("left"))
            p.auto = int(x.get("auto") or 0)
            p.choice = tuple(x["choice"]) if x.get("choice") else None
            self.players.append(p)
        self.round = int(d["round"])
        self.over = bool(d["over"])
        self.result = d.get("result")
        self.started = bool(d.get("started"))
        self.shield = dict(d["shield"]) if d.get("shield") else None
        self.shielded_once = bool(d.get("shieldedOnce"))
        self.raged = bool(d.get("raged"))
        self.roar_next = bool(d.get("roarNext"))
        self._wire()
        for p in self.players:
            p.bt.turn_no = self.round
        return self
