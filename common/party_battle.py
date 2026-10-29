# -*- coding: utf-8 -*-
"""파티 대 파티 전투 — 유저끼리 붙일 때 쓴다.

battle.Battle 은 1:1 전용이다. 여기서는 그걸 **감싸기만** 한다. 고치지
않는다 — 야생 배틀이 그 위에서 돌고 있고, 그게 깨지는 게 제일 나쁘다.

진행은 본가의 배틀타워와 같다. 앞선 두 마리가 붙고, 쓰러진 쪽이 다음
포켓몬을 내보낸다. 한쪽이 전멸하면 끝난다. 사람이 개입하지 않는다 —
양쪽 다 기술을 알아서 고른다.

**결과는 시드 하나로 정해진다.** 같은 팀, 같은 시드면 언제 몇 번을
돌려도 같은 로그가 나온다. 그래서 서버가 매칭 순간 한 번만 계산해서
로그로 저장하고, 양쪽 클라이언트는 그 로그를 재생하기만 하면 된다.
턴마다 서버를 왕복할 필요가 없고, 재생 도중 앱이 꺼져도 승패는 이미
확정되어 있다.

로그에 담기는 이벤트는 Battle 이 내는 것 그대로에 세 가지를 더한다.

    {"t": "round", "n": 1, "me": {...}, "foe": {...}}   라운드 시작(선수 소개)
    {"t": "ko",    "side": "me"|"foe"|"both"}           라운드 끝
    {"t": "match", "winner": "me"|"foe"|"draw", ...}    판 끝

Battle 이 내는 "over" 는 1:1 기준이라(한 라운드가 끝날 때마다 나온다)
여기서 걸러낸다. 재생기는 "over" 를 몰라야 한다.

시점은 **항상 a 쪽 기준**이다. me = a, foe = b. b 쪽 화면에서는
클라이언트가 재생 직전에 한 번 뒤집는다.

## 시즌 5 랭크: 양쪽 다 길드전 방어 AI (war_ai=True)

서버가 시즌 5 의 랜덤(랭크) 배틀 · 연습판에서만 켠다 (pvp.run_match, season.rules_v5). 끄면 아래는 하나도
안 지나고, 같은 시드면 예전과 한 글자도 다르지 않은 로그가 나온다.

**판정은 이 엔진 그대로다** - 바뀌는 것은 '무엇을 고르느냐' 뿐이다. 턴마다 양쪽이 각자 자기를 길드전 방어 AI
(trainer_battle 의 _war_choice) 자리에 앉힌 **거울 판**(_RankedWar)을 만들어 고른다. 거울 판은 그 순간의 체력 ·
PP · 랭크 · 상태 · 도구 · 날씨 · 깔기를 그대로 옮긴 TrainerBattle 이고, 셈(사본을 굴려 보기)은 그 안에서만 한다.
고른 것(기술 또는 교체)은 여기 Battle 이 판정한다. 그래서:

  - 15% 무작위가 없다 (길드전 AI 는 실수하지 않는다).
  - 라운드 도중에 스스로 바꾼다. 화면에는 기술로 바뀔 때(유턴)와 같은 "round" 이벤트로 나간다 - 앱이
    이미 '살아 있는 채로 바뀌는 선수' 를 그릴 줄 안다. 그 앞에 "msg" 한 줄(물러났다)을 붙인다.
  - 쓰러진 뒤 다음 선수도 길드전 AI 의 고르기(_war_pick)다.

TrainerBattle 엔진으로 판 전체를 돌리지 않는 까닭: 라운드 30턴 상한 · 쓰러뜨린 턴의 턴 끝 · 머릿수 판정 같은
판정이 이 엔진과 달라서, 그걸로 돌리면 고르기만이 아니라 판정이 바뀐다. 로그 꼴도 다시 만들어야 한다.
"""
import json
import random
import time

from . import abilities as A
from . import battle as B
from . import field as FD
from . import held as H
from . import movecalc as MC
from . import statusmoves as SM
from . import trainer_battle as TB

# 특성을 켠다 (관장 배틀과 같은 common/abilities.py). 끄면 예전 판과 한 글자도
# 안 다른 로그가 나온다 - 저장된 판은 로그를 그대로 재생하므로 켜도 옛 판은 그대로다.
ABILITIES = True

# 한 라운드(1:1)에 쓸 수 있는 턴 수. 야생의 80 보다 훨씬 짧다.
# 6:6 이면 최대 여섯 라운드라, 라운드마다 80턴을 주면 한 판이 480턴까지
# 늘어난다. 그걸 도트로 재생하면 몇 분이 걸린다. 30턴이면 웬만한 라운드는
# 안에서 끝나고, 안 끝나면 양쪽 다 물러나는 것으로 친다.
ROUND_TURNS = 30
# 이미 나와 있는 선수에게 주는 웃돈. 이만큼 차이가 안 나면 안 바꾼다.
# 교체에도 한 턴이 드는 셈이라 조금 유리한 정도로는 바꾸지 않는다.
SWITCH_MARGIN = 1.5

# 판 전체의 안전장치. 라운드 수 × ROUND_TURNS 를 넘길 일은 없지만,
# 어딘가 잘못되어 라운드가 안 끝나면 여기서 멈춘다.
MAX_ROUNDS = 16

# ---- 시즌 5 랭크 (war_ai=True) 의 셈 양 ----
# 랭크는 요청 한 번에 판 전체를 계산한다. 길드전은 사람이 한 턴씩 두니 턴당 0.5초를 써도 되지만, 여기서는
# 양쪽 x 판 전체 턴이 한 요청 안에 든다. 그래서 길드전보다 얕게 보고(_RankedWar) 판 전체에 시간 상한을 둔다.
# 상한을 다 쓰면 남은 턴은 셈 없이 관장 AI 의 수(길드전 AI 가 셈하기 전에 정하는 그 수)로 둔다 - 그것도 무작위는
# 없다. 시간에 걸리면 기계마다 결과가 달라질 수 있지만 로그를 저장해 재생하므로 괜찮다.
# 값은 tools/ranked_war_bench.py 로 쟀다 (2026-10-29, M1 맥 · 챔피언급 6:6 48판). 이 맥에서는 상한에 안 걸리고 한 판이
# 중앙값 0.80초 · p95 1.26초 · 최대 1.40초 (예전 판은 0.01초). 운영 서버(t3.small)를 3배 느리다고 보면(--slow 3) 중앙값
# 2.35초 · 최대 3.56초이고 셈 없이 둔 수는 1.7% - 대략 5초 안이다 (앱은 15초를 기다린다). 셈 깊이 2 · 시드 2 (길드전 그대로)는
# 이 상한 안에서 절반 가까이 셈 없이 두게 되어 오히려 약했다 (옛 AI 상대 0.57 · 깊이 1 은 0.74).
WAR_MATCH_BUDGET = 3.5      # 한 판에 셈에 쓰는 시간 (초, 양쪽 합)
WAR_TURN_CAP = 0.25         # 한 수에 셈에 쓰는 시간 상한 (초) - 길드전의 비상 상한(2초)에 해당


def _side_view(f):
    """선수 소개에 쓸 정보. 화면이 도트를 띄우는 데 필요한 것까지 담는다."""
    # 도감 번호는 mon 에 없을 수 있다(야생으로 뽑은 개체에는 없다).
    # Fighter 가 이미 도감 항목을 들고 있으니 거기서 가져온다 - 화면이
    # 도트를 찾을 때 쓰는 값이라 비면 아무것도 안 뜬다.
    sp = f.species or {}
    out = {"name": f.name, "species": f.mon.get("species"),
           # 메가진화한 선수가 다시 나오면 메가 모습으로 (시즌 3)
           "num": sp.get("num") if f.mega else (f.mon.get("num") or sp.get("num")),
           "level": f.mon.get("level"),
           "shiny": bool(f.mon.get("shiny")), "hp": f.hp, "maxhp": f.maxhp,
           "gender": f.mon.get("gender")}
    # 이로치가 고른 색 (1.8.0). **있을 때만 싣는다** - 아래 메가와 같은 까닭이다.
    if f.mon.get("tint") and f.mon.get("shiny"):
        out["tint"] = f.mon["tint"]
    # **메가일 때만 싣는다.** 늘 "mega": False 를 붙이면 메가와 상관없는 옛 판의
    # 로그까지 글자가 바뀐다 (test_held 의 요약값이 그걸 지킨다).
    if f.mega:
        out["mega"] = True
    return out


# ---------------- 시즌 5 랭크: 길드전 방어 AI 의 거울 판 ----------------
class _NoSlip(object):
    """random() 이 늘 1 인 난수 - Battle.choose_for 의 '15% 무작위' 를 안 타게 한다 (그 줄만 rng.random 을 부른다)."""

    @staticmethod
    def random():
        return 1.0


class _SteadyDuel(TB.Duel):
    """거울 판의 Battle. 관장 AI 가 쓸 만한 수를 못 찾아 choose_for 로 넘길 때도 무작위 없이 고른다."""

    def choose_for(self, user, target, ai):
        if ai != "trainer":
            return TB.Duel.choose_for(self, user, target, ai)
        rng, self.rng = self.rng, _NoSlip
        try:
            return TB.Duel.choose_for(self, user, target, ai)
        finally:
            self.rng = rng


class _Planned(B.Battle):
    """시즌 5 랭크의 라운드. b 쪽 기술을 Battle 이 고르지 않고 길드전 AI 가 고른 것(planned)을 쓴다.

    take_turn 은 그대로 지난다 - 메가진화 · 순서 · 턴 끝이 예전 판과 같은 길이다. 고르는 자리(choose_ai)만 바꾼다.
    """
    planned = None

    def choose_ai(self):
        return self.planned if self.planned is not None else B.Battle.choose_ai(self)


class _RankedWar(TB.TrainerBattle):
    """한쪽을 길드전 방어 AI(foe) 자리에, 상대를 사람(me) 자리에 앉힌 판. 고르기만 하고 이 판으로 싸우지는 않는다.

    셈의 틀(평가 · 사람의 수 · 교체 거름 · 확실한 KO · 시간 끌기 감점)은 길드전 그대로다. 양만 줄인다:
    셈 깊이 2 -> 1, 시드 2 -> 1. 판 전체를 한 요청에서 돌려야 해서다 (WAR_MATCH_BUDGET).
    """
    WAR2_DEPTH = 1
    WAR2_SEEDS = 1
    WAR2_EMERGENCY = WAR_TURN_CAP
    WAR_BUDGET = WAR_TURN_CAP            # WAR_V2 를 끄면 옛 셈 - 그쪽 상한도 같게
    WAR2_SLOW = 10 ** 9

    def _make_duel(self, field):
        TB.TrainerBattle._make_duel(self, field)
        self.bt.__class__ = _SteadyDuel

    def _war_log(self, text):
        """랭크는 판마다 수십 번 고른다 - 서버 로그에 한 줄씩 남기지 않고 센다 (PartyBattle.war_stats, 벤치가 본다)."""
        key = "cut" if "비상 상한" in text else "error"
        self.war_notes[key] = self.war_notes.get(key, 0) + 1


_SIDE_REFS = ("by", "attract", "trapped", "octolock")
_RNG0 = random.Random(0).getstate()
_RNG0 = [_RNG0[0], list(_RNG0[1]), _RNG0[2]]


def _swap_refs(obj):
    """거울 판(a 를 AI 자리에)으로 옮길 때, 상태 안에 적힌 진영 이름(헤롱헤롱을 건 쪽 ...)을 뒤집는다."""
    if isinstance(obj, dict):
        return dict((k, _FLIP[v] if k in _SIDE_REFS and v in _FLIP else _swap_refs(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return [_swap_refs(v) for v in obj]
    return obj


class PartyBattle(object):
    """파티끼리 한 판.

        pb = PartyBattle(dex, a_mons, b_mons, seed=12345)
        out = pb.run()
        out["winner"]   "me"(a 승) / "foe"(b 승) / "draw"
        out["events"]   재생할 이벤트 목록
        out["turns"]    총 턴 수
    """

    def __init__(self, dex, a_mons, b_mons, seed=None, keystone=None, zring=None, war_ai=False):
        if not a_mons or not b_mons:
            # 엔진이 정책을 갖지는 않지만, 여기서 안 막으면 아래에서
            # team[0] 이 IndexError 를 내고 서버가 500 을 뱉는다.
            raise ValueError("양쪽 다 최소 한 마리는 있어야 합니다.")
        self.dex = dex
        self.seed = random.randrange(1 << 30) if seed is None else int(seed)
        self.rng = random.Random(self.seed)
        self.a = [self._fighter(dex, m) for m in a_mons]
        self.b = [self._fighter(dex, m) for m in b_mons]
        # 이번 라운드에 새로 링에 오른 쪽. 나올 때 발동하는 특성(위협 ...)을 여기서 본다.
        self.entered = {"me": True, "foe": True}
        self.ia = self.ib = 0          # 지금 나와 있는 선수의 자리
        self.events = []
        self.turns = 0
        self.winner = None
        # 날씨·필드·진영은 한 판 내내 간다 (라운드마다 Battle 은 새로 만든다)
        self.field = FD.Field()
        self.round_no = 0
        self.bt = None
        # 메가진화 (시즌 3). 양쪽 다 AI 가 싸우니 알아서 메가진화한다. 라운드마다
        # Battle 을 새로 만들어도 한 판 한 번이 지켜지게 여기 둔다.
        self.keystone = dict(keystone or {"me": False, "foe": False})
        self.mega_done = set()
        # Z기술 (시즌 4). 메가와 같은 틀 - 한 판에 한 번, AI 가 알아서 쓴다.
        self.zring = dict(zring or {"me": False, "foe": False})
        self.z_done = set()
        # 시즌 5 랭크: 양쪽 다 길드전 방어 AI 로 고른다 (맨 위 설명). 끄면 아래 칸은 하나도 안 쓴다.
        self.war_ai = bool(war_ai)
        if self.war_ai:
            # 셈의 난수는 판정의 난수(self.rng)와 따로 굴린다 - 셈이 시간 상한에 걸려 덜 굴려도 판정 쪽 순서는
            # 그대로다. 그래도 시드에서 나오므로 상한에 안 걸리면 같은 시드 = 같은 판이다.
            self.ai_rng = random.Random(self.seed * 2 + 1)
            self.war_spent = 0.0                     # 이 판에서 셈에 쓴 시간 (양쪽 합)
            self.war_stats = {"choices": 0, "searched": 0, "plain": 0, "cut": 0, "error": 0}
            # 거울 판이 길드전에서 TrainerBattle 에 들고 있던 것 - 판이 하나뿐이라 진영마다 여기 둔다
            self.war_stall = {"me": {}, "foe": {}}   # 자리마다 시간 끌기 수를 고른 횟수
            self.war_sent = {"me": -1, "foe": -1}    # 쓰러진 선수 대신 다음 선수를 낸 턴
            self.switched_last = {"me": False, "foe": False}   # 지난 턴에 바꿨다 (두 턴 내리 안 바꾼다)
            self.moved_out = {"me": False, "foe": False}       # 이번 턴에 기술로 물러났다 (유턴 ...)

    # ---------------- 도구 ----------------
    @staticmethod
    def _fighter(dex, mon):
        f = B.Fighter(dex, mon)
        f.ability_on = ABILITIES
        return f

    def _alive(self, team, start):
        """start 부터 살아 있는 첫 자리. 없으면 None."""
        for i in range(start, len(team)):
            if team[i].alive():
                return i
        return None

    def _matchup(self, mine, foe):
        """이 조합이 나에게 얼마나 유리한가. 클수록 좋다.

        공격 쪽 - 내 기술이 상대 타입에 얼마나 잘 박히나 (제일 잘 박히는 것)
        수비 쪽 - 상대 타입이 나를 얼마나 잘 때리나 (제일 아픈 것)
        둘을 나눈다. 2배로 때리고 0.5배로 맞으면 4, 반대면 0.25.

        기술을 실제로 보고 판단한다. 타입만 보면 '불꽃이 풀에게 유리' 인데
        정작 불꽃 기술이 하나도 없는 경우를 놓친다.
        """
        foe_types = foe.types()
        my_types = mine.types()

        # 특성으로 막히는 기술(부유에 땅, 저수에 물 ...)은 없는 셈 치고,
        # 스킨 특성으로 바뀌는 타입까지 본다 (특성이 꺼져 있으면 그대로다).
        atk = 0.0
        for key in mine.moves:
            md = self.dex.move(key) or {}
            if not MC.attacks(md) or A.would_block(mine, foe, md):
                continue                       # 변화기는 상성과 무관하다
            e = B.effectiveness(self.dex, A.move_type(mine, md), foe_types)
            if e > atk:
                atk = e
        if atk <= 0:
            atk = 0.25                         # 때릴 수단이 없다시피 하다

        dfn = 0.0
        for key in foe.moves:
            md = self.dex.move(key) or {}
            if not MC.attacks(md) or A.would_block(foe, mine, md):
                continue
            e = B.effectiveness(self.dex, A.move_type(foe, md), my_types)
            if e > dfn:
                dfn = e
        if dfn <= 0:
            dfn = 0.25

        # 체력이 많이 남은 쪽을 조금 더 쳐준다. 상성이 같으면 성한 애가 낫다.
        health = 0.6 + 0.4 * (mine.hp / float(mine.maxhp or 1))

        # 힘 차이(능력치 합)도 보게 해 봤지만 600판을 붙여 50.8% 였다.
        # 재보고 이득이 없어서 넣지 않는다 - 안 쓰는 복잡함은 빚이다.
        return (atk / dfn) * health

    def _pick_against(self, team, foe, cur=None):
        """상대에게 제일 잘 맞는 선수의 자리.

        같은 점수면 **앞자리를 고른다.** 무작위를 쓰지 않는다 - PVP 는
        서버가 계산한 로그를 그대로 재생하는 구조라, 여기에 rng 를 넣으면
        나중에 조건 하나만 고쳐도 이전 판들과 어긋난다.
        """
        best, best_score = None, None
        for i, f in enumerate(team):
            if not f.alive():
                continue
            sc = self._matchup(f, foe)
            # 이미 나와 있는 애는 조금 더 쳐준다. 점수가 비슷한데 굳이
            # 바꾸면 한 턴을 버리는 셈이다(교체에도 턴이 든다).
            if cur is not None and i == cur:
                sc *= SWITCH_MARGIN
            if best_score is None or sc > best_score:
                best, best_score = i, sc
        return best

    def _round_battle(self):
        """지금 선수 둘로 1:1 한 라운드를 만든다."""
        # ai="trainer" 를 반드시 준다. 기본값은 "wild" 라 상대가 기술을
        # 무작위로 고른다 - 내 쪽은 choose_mine 이 알아서 'trainer' 로
        # 고르기 때문에, 빠뜨리면 a 가 머리를 쓰고 b 는 아무 기술이나
        # 쓰는 판이 된다. 실제로 600판을 돌려 보니 a 가 69% 를 이겼다.
        bt = (_Planned if self.war_ai else B.Battle)(self.dex, self.a[self.ia], self.b[self.ib], self.rng,
                                                    ai="trainer", field=self.field)
        # 상대가 야생이 아니다. 문구에서 '야생' 을 뗀다.
        bt.foe_prefix = ""
        bt.max_turns = ROUND_TURNS
        bt.teams = {"me": self.a, "foe": self.b}     # 집단폭행이 세는 같은 편
        bt.kind = "pvp"
        bt.switcher = self._move_switch
        bt.keystone = self.keystone
        bt.mega_done = self.mega_done
        bt.auto_mega = {"me": True, "foe": True}
        bt.zring, bt.z_done = self.zring, self.z_done
        bt.auto_z = {"me": True, "foe": True}
        self.bt = bt
        return bt

    def _move_switch(self, who, mode, ev, key, state=None):
        """라운드 도중에 기술로 바뀐다 (울부짖기·유턴·배턴터치 ...). 해냈으면 True.

        화면은 "round" 이벤트를 받으면 살아 있는 채로 바뀌는 선수를 물러나게 하고
        새 선수를 링에 세운다 (상성 교체와 같은 길). 쓰러진 게 아니므로 "ko" 는 안 낸다.
        """
        bt = self.bt
        team = self.a if who == "me" else self.b
        cur = self.ia if who == "me" else self.ib
        others = [i for i, f in enumerate(team) if f.alive() and i != cur]
        if not others or bt is None:
            return False
        opp = bt.fighter("foe" if who == "me" else "me")
        if mode == "drag":
            nxt = self.rng.choice(others)
        elif self.war_ai:
            # 시즌 5 랭크: 길드전 AI 가 유턴 뒤에 고르는 것과 같게 - 지금 상대와 붙었을 때의 형세(_standing).
            # 거울 판을 못 만들면 예전 상성 고르기로 (판이 멈추면 안 된다).
            try:
                m = self._mirror(who)
                nxt = max(others, key=lambda i: (m._standing(m.foe_team[i], m.me) if opp.alive() else 0, -i))
            except Exception:                           # noqa: BLE001
                self.war_stats["error"] += 1
                nxt = max(others, key=lambda i: (self._matchup(team[i], opp), -i))
            self.moved_out[who] = True               # 길드전 AI 처럼 다음 턴에는 스스로 안 바꾼다
        else:
            nxt = max(others, key=lambda i: (self._matchup(team[i], opp), -i))
        self._bring_in(who, nxt, ev, mode, state)
        return True

    def _bring_in(self, who, nxt, ev, mode=None, state=None):
        """살아 있는 선수를 물리고 nxt 를 링에 세운다 (기술로 바뀔 때 · 시즌 5 랭크에서 스스로 바꿀 때)."""
        bt = self.bt
        team = self.a if who == "me" else self.b
        old = team[self.ia if who == "me" else self.ib]
        self._retire(old)
        SM.on_leave(bt, who)
        if who == "me":
            self.ia = nxt
            bt.me = team[nxt]
        else:
            self.ib = nxt
            bt.foe = team[nxt]
        if mode in ("pass", "shed"):
            SM.apply_pass(team[nxt], state, shed=mode == "shed")
        ev.append({"t": "round", "n": self.round_no, "mi": self.ia, "fi": self.ib,
                   "me": _side_view(self.a[self.ia]), "foe": _side_view(self.b[self.ib])})
        bt.enter(who, ev)
        if team[nxt].alive():
            team[nxt].ab["down"] = sum(1 for x in team if not x.alive())
            A.on_switch_in(bt, team[nxt], who, ev)
            SM.on_enter_abilities(bt, team[nxt], who, ev)

    # ---------------- 진행 ----------------
    def run(self):
        # 명단을 맨 앞에 넣는다. 화면은 시작하자마자 양쪽 여섯 마리를
        # 다 세워야 하는데, 라운드 이벤트에는 실제로 링에 나온 애들만
        # 담긴다 - 일찍 끝나면 뒤쪽 선수는 로그에 아예 안 나온다.
        # me/foe 키라서 시점 뒤집기(flip)가 그대로 처리해 준다.
        self.events.append({"t": "teams",
                            "me": [_side_view(f) for f in self.a],
                            "foe": [_side_view(f) for f in self.b]})
        for n in range(1, MAX_ROUNDS + 1):
            self.round_no = n
            # **자리 번호를 같이 보낸다.** 예전에는 화면이 "쓰러지지 않은
            # 첫 자리" 로 스스로 계산했는데, 그러면 서버가 순서를 바꿔
            # 내보내는 순간 다른 포켓몬이 나온다. 오류도 안 난다.
            self.events.append({"t": "round", "n": n,
                                "mi": self.ia, "fi": self.ib,
                                "me": _side_view(self.a[self.ia]),
                                "foe": _side_view(self.b[self.ib])})
            side = self._one_round()
            self.events.append({"t": "ko", "side": side})
            if self._advance(side):
                break
        if self.winner is None:
            # 라운드 상한까지 왔는데 양쪽 다 남아 있다. 머릿수로 가른다.
            self.winner = self._by_headcount()
        self.events.append({"t": "match", "winner": self.winner,
                            "turns": self.turns, "rounds": n})
        return {"winner": self.winner, "turns": self.turns,
                "events": self.events, "seed": self.seed}

    def _one_round(self):
        """한 라운드를 끝까지. 누가 쓰러졌는지("me"/"foe"/"both") 돌려준다."""
        bt = self._round_battle()
        for who in ("me", "foe"):
            if self.entered.get(who):
                bt.enter(who, self.events)          # 압정·스텔스록 (첫 라운드는 아무것도 없다)
        self._entry_abilities(bt)
        while not bt.over and bt.me.alive() and bt.foe.alive():
            if self.war_ai:
                ev = self._war_turn(bt)
            else:
                ev = bt.take_turn(bt.choose_mine())
            self.turns += 1
            if bt.over and self._still_on(bt):
                # **쓰러뜨린 턴에도 턴 끝은 온다** (1.13.3, 게시판 #295 slovena '다투곰 화상이 2~3턴 뒤에'). 1:1
                # 배틀은 누가 쓰러지면 판이 끝난 것으로 보고 턴 끝을 건너뛴다. 그래서 상대를 한 방에 쓰러뜨리는
                # 동안 화염구슬 · 먹다남은음식 · 독 데미지 · 가속이 빠졌다. 본가처럼 턴 끝을 마친 뒤 다음 선수가
                # 나온다 (관장 · 실시간 배틀은 원래 그렇다). 턴 끝 가운데 '판이 끝났으면 안 하는 것'(열매 ·
                # 탈출 도구)도 돌게 잠깐 연다. 쓰러짐은 _check_faint 가 한 번만 알린다.
                bt.over = False
                bt._end_of_turn(ev)
                bt.over = True
            # Battle 의 "over" 는 1:1 기준이라 라운드마다 나온다.
            # 그대로 흘리면 재생기가 판이 끝난 줄 안다.
            self.events.extend(e for e in ev if e.get("t") != "over")

        a_down = not self.a[self.ia].alive()
        b_down = not self.b[self.ib].alive()
        if a_down and b_down:
            return "both"
        if a_down:
            return "me"
        if b_down:
            return "foe"
        # 아무도 안 쓰러졌는데 라운드가 끝났다 = 턴 상한(무승부).
        # 양쪽 다 물러나는 것으로 친다. 한쪽만 물리면 화면에서 한 마리가
        # 링에 남은 채로 다음 선수와 겹친다.
        return "both"

    def _still_on(self, bt):
        """이번 턴에 한쪽만 쓰러졌고 그쪽에 다음 선수가 남아 있다 = 판이 이어진다 (턴 끝이 와야 한다).

        마지막 선수가 쓰러졌으면 판이 끝나므로 턴 끝은 없다 (본가와 같다). 둘 다 살아 있는데 끝났으면 턴 상한이나
        날려 보내기라 턴 끝은 이미 돌았다.
        """
        if bt.me.alive() == bt.foe.alive():
            return False
        team = self.a if not bt.me.alive() else self.b
        down = bt.me if not bt.me.alive() else bt.foe
        return any(f.alive() for f in team if f is not down)

    def _entry_abilities(self, bt):
        """새로 링에 오른 쪽의 '나올 때' 특성. 빠른 쪽부터 (관장 배틀과 같다)."""
        pair = [(who, f) for who, f in (("me", bt.me), ("foe", bt.foe)) if self.entered.get(who)]
        pair.sort(key=lambda p: -p[1].stat("spe"))
        for who, f in pair:
            if f.alive():
                team = self.a if who == "me" else self.b
                f.ab["down"] = sum(1 for x in team if not x.alive())
                A.on_switch_in(bt, f, who, self.events)
                SM.on_enter_abilities(bt, f, who, self.events)
                # 라운드 시작에 나온 것(판의 첫 선수 · 쓰러진 선수 대신 나온 것)은 '이번 턴에 나온 것' 이 아니다 -
                # 가속이 그 턴 끝에 오른다 (본가 · 관장 배틀과 같다, 1.13.3). 예전에는 라운드마다 한 턴씩 늦었다.
                f.ab["fresh"] = False
        self.entered = {"me": False, "foe": False}

    def _retire(self, f):
        """쓰러지지 않고 물러난다 (턴 상한 무승부). 재생력·자연회복이 여기서 돈다."""
        if f.alive():
            A.on_switch_out(f)
            f.stages = dict((k, 0) for k in B.STAGE_KEYS)
            f.clear_volatile()
            f.types_override = None

    def _advance(self, side):
        """쓰러진 쪽의 다음 선수를 내보낸다. 판이 끝났으면 True.

        양쪽을 다 본 뒤에 판정한다. 한쪽을 보고 바로 돌아가면 둘이 동시에
        전멸했을 때 무승부가 아니라 한쪽 승리가 된다.
        """
        if self.war_ai:
            return self._war_advance(side)
        a_out = b_out = False
        # **상성이 유리한 쪽을 내보낸다.** 예전에는 무조건 살아 있는
        # 첫 자리였다. 순서대로 나가서 물 타입 앞에 불 타입이 계속
        # 나가는 일이 벌어졌다.
        #
        # 상대를 보고 고르므로 순서가 중요하다. 양쪽이 같이 쓰러졌을 때는
        # a 가 먼저 (지금 b 를 보고) 고르고, 그다음 b 가 (새 a 를 보고)
        # 고른다. 완전히 공평하진 않지만 **결정적**이고, 서로를 보고
        # 무한히 다시 고르는 것을 피한다.
        if side in ("me", "both"):
            self._retire(self.a[self.ia])
            nxt = self._pick_against(self.a, self.b[self.ib])
            if nxt is None:
                a_out = True
            else:
                self.ia = nxt
                self.entered["me"] = True
        if side in ("foe", "both"):
            self._retire(self.b[self.ib])
            nxt = self._pick_against(self.b, self.a[self.ia])
            if nxt is None:
                b_out = True
            else:
                self.ib = nxt
                self.entered["foe"] = True

        if a_out and b_out:
            self.winner = "draw"
        elif a_out:
            self.winner = "foe"
        elif b_out:
            self.winner = "me"
        else:
            return False
        return True

    # ---------------- 시즌 5 랭크: 길드전 방어 AI 로 고르기 ----------------
    def _mirror(self, who):
        """who 쪽을 길드전 방어 AI(foe) 자리에 앉힌 거울 판 (_RankedWar). 지금 판에서 옮긴 사본이라 셈이 판을 못 건드린다.

        b(foe) 쪽은 진영 이름이 그대로고, a(me) 쪽은 me/foe 를 통째로 뒤집는다 (팀 · 자리 · 진영 · 메가 · Z ·
        상태 안에 적힌 '건 쪽').
        """
        flip = who == "me"
        mine, theirs = (self.a, self.b) if flip else (self.b, self.a)
        fi, mi = (self.ia, self.ib) if flip else (self.ib, self.ia)

        def side(x):                                   # 진짜 진영 -> 거울 판의 진영
            return _FLIP[x] if flip else x

        def fighters(team):
            out = [TB.TrainerBattle._dump_fighter(f) for f in team]
            return _swap_refs(out) if flip else out
        fd = self.field.dump()
        if fd and flip:
            fd = _swap_refs(dict(fd, sides={"me": fd["sides"]["foe"], "foe": fd["sides"]["me"]}))
        other = _FLIP[who]
        d = {"v": 1, "trainer": {"id": "rank", "name": "", "role": "", "level": 50, "ai": "war"},
             "me": fighters(theirs), "foe": fighters(mine), "mi": mi, "fi": fi,
             "turn": self.turns, "over": False, "result": None, "needSwitch": False,
             "foeSwitchedLast": self.switched_last[who] or self.moved_out[who],
             "seen": list(range(len(mine))), "started": True, "rng": _RNG0, "field": fd,
             "keystone": {"me": bool(self.keystone.get(other)), "foe": bool(self.keystone.get(who))},
             "megaDone": sorted(side(x) for x in self.mega_done),
             "gimmick": {"zring": {"me": bool(self.zring.get(other)), "foe": bool(self.zring.get(who))},
                         "zDone": sorted(side(x) for x in self.z_done)},
             "warStall": dict(self.war_stall[who]), "warSent": self.war_sent[who]}
        # json 을 한 번 지난다 - 사본이 진짜 판의 mon dict 를 같이 쥐면 셈이 도구 · PP 를 고쳐 쓸 수 있다
        blob = json.dumps(d)
        m = _RankedWar.load(self.dex, json.loads(blob))
        m.rng.seed(self.ai_rng.randrange(1 << 30))
        m.war_notes = {}
        m._war_pre = blob             # 셈이 사본을 뜨는 판 = 이번 턴을 열기 전의 판 (길드전의 act 와 같다)
        return m

    def _war_left(self):
        return WAR_MATCH_BUDGET - self.war_spent

    def _war_plan(self, who):
        """(바꿀 자리, 쓸 기술) - 이번 턴 who 쪽의 수. 둘 중 하나는 None.

        길드전 AI 의 고르기(_war_choice)를 그대로 부른다. 판의 시간(WAR_MATCH_BUDGET)을 다 썼으면 셈 없이
        관장 AI 의 수 - 길드전 AI 가 셈하기 전에 먼저 정하는 그 수다. 무엇이 터져도 그 턴은 그 수다.
        """
        t0 = time.time()
        st = self.war_stats
        st["choices"] += 1
        m = None
        try:
            # 거울 판 만들기도 감싼다 - 사본이 못 옮기는 상태가 생기면 랜덤 배틀만 매 판 500 이 난다 (10/29 검토)
            m = self._mirror(who)
            m.turn += 1               # 길드전의 act 는 턴 수를 올린 뒤에 고른다 (시간 끌기 감점 · 막 낸 포켓몬 감점이 본다)
            m.bt.turn_no = m.turn
            left = self._war_left()
            if left > 0:
                # 한 수의 상한은 남은 시간보다 길지 않게 (셈은 관장 AI 의 수를 먼저 보므로 그만큼은 넘을 수 있다)
                m.WAR2_EMERGENCY = m.WAR_BUDGET = min(WAR_TURN_CAP, left)
                slot, key = m._war_choice()
                st["searched"] += 1
            else:
                slot = m._foe_wants_switch()
                key = None if slot is not None else m._foe_move()
                st["plain"] += 1
        except Exception:                               # noqa: BLE001  (판이 멈추면 안 된다 - 예전의 고르기)
            st["error"] += 1
            slot, key = None, None
        if m is not None:
            for k, n in m.war_notes.items():
                st[k] = st.get(k, 0) + n
            self.war_stall[who] = dict(m.war_stall)
        self.war_spent += time.time() - t0
        team = self.a if who == "me" else self.b
        cur = self.ia if who == "me" else self.ib
        if slot is not None and not (0 <= slot < len(team) and slot != cur and team[slot].alive()):
            slot = None
        if slot is None and key is None:
            bt = self.bt
            f = bt.fighter(who)
            key = _steady_choose(bt, f, bt.fighter(_FLIP[who]))
        return slot, key

    def _war_turn(self, bt):
        """시즌 5 랭크의 한 턴. 양쪽이 **턴을 열기 전의 판**을 보고 각자 고른다 (서로의 수를 모른다).

        둘 다 기술이면 예전 판과 같은 take_turn 이다 (b 의 기술만 _Planned 로 넣는다). 한쪽이라도 바꾸면 _switch_turn.
        """
        plan = {"me": self._war_plan("me"), "foe": self._war_plan("foe")}
        self.moved_out = {"me": False, "foe": False}
        if plan["me"][0] is None and plan["foe"][0] is None:
            bt.planned = plan["foe"][1]
            try:
                ev = bt.take_turn(plan["me"][1])
            finally:
                bt.planned = None
        else:
            ev = self._switch_turn(bt, plan)
        for who in ("me", "foe"):
            self.switched_last[who] = plan[who][0] is not None or self.moved_out[who]
        return ev

    def _switch_turn(self, bt, plan):
        """누군가 스스로 바꾸는 턴. Battle.take_turn 과 같은 순서에 '바꾼 쪽은 기술을 안 쓴다' 만 더한다.

        교체가 먼저다 (a -> b. 관장 배틀은 사람 -> AI). 메가진화는 바꾸지 않은 쪽만. 그 뒤는 take_turn 그대로 -
        구애 잠금 · Z기술 · 순서 · 기술 · 턴 끝 · 라운드 턴 상한.
        """
        if bt.over:
            return [{"t": "over", "result": bt.result}]
        bt.turn_no += 1
        ev = []
        bt.begin_turn()
        moves = {}
        for who in ("me", "foe"):
            slot, key = plan[who]
            moves[who] = key if slot is None else None
            if slot is not None:
                self._war_switch(who, slot, ev)
        keep = dict(bt.auto_mega)
        bt.auto_mega = dict((w, keep.get(w) and moves[w] is not None) for w in ("me", "foe"))
        try:
            bt.mega_step({"me": False}, ev)
        finally:
            bt.auto_mega = keep
        for who in ("me", "foe"):
            f, k = bt.fighter(who), moves[who]
            if k is None:
                continue
            if k != B.STRUGGLE and (k not in f.pp or f.pp.get(k, 0) <= 0):
                k = bt.usable(f)[0]
            if f.held:
                k = H.force_move(f, k, ev, who, bt)
            moves[who] = k
        bt.z_request("me", moves["me"], False)
        bt._auto_z("me", moves["me"])
        bt._auto_z("foe", moves["foe"])
        if moves["me"] and moves["foe"]:
            order = bt._order(moves["me"], moves["foe"], ev)
        else:
            bt.pending = dict(moves)
            order = [w for w in ("me", "foe") if moves[w]]
        bt.me.flinched = False
        bt.foe.flinched = False
        bt.me.moved_second = bool(order) and order[0] != "me"
        bt.foe.moved_second = bool(order) and order[0] != "foe"
        acting = {"me": bt.me, "foe": bt.foe}
        for who in order:
            if bt.over:
                break
            user, target = (bt.me, bt.foe) if who == "me" else (bt.foe, bt.me)
            if user is not acting[who]:
                continue                 # 이번 턴에 끌려 나온 포켓몬은 움직이지 않는다
            if not user.alive() or not target.alive():
                continue
            bt._use(who, user, target, moves[who], ev)
        if not bt.over:
            # 들어오다 스텔스록에 쓰러졌으면 **턴 끝 전에** 판(라운드)을 닫는다. 기술을 쓴 쪽이 없어 _use 가 못 봤다 -
            # 그대로 두면 턴 끝이 여기서 한 번, 쓰러뜨린 턴의 턴 끝(_one_round 의 _still_on)에서 또 한 번 돈다.
            bt._check_faint(ev)
        if not bt.over:
            bt._end_of_turn(ev)
        if not bt.over and bt.turn_no >= bt.max_turns:
            bt.over = True
            bt.result = "fled"
            ev.append({"t": "flee", "who": "foe",
                       "text": "%s%s 은(는) 흥미를 잃고 떠나버렸다." % (bt.foe_prefix, bt.foe.name)})
        return ev

    def _war_switch(self, who, slot, ev):
        """스스로 바꾼다. 기술로 바뀔 때(_move_switch)와 같은 길에, 다른 엔진(관장 · 실시간 · 레이드)처럼
        움찔 · 구애 잠금을 푼다. 화면은 "round" 이벤트로 선수를 바꿔 세운다 - 그 앞에 물러나는 글 한 줄."""
        team = self.a if who == "me" else self.b
        old = team[self.ia if who == "me" else self.ib]
        ev.append({"t": "msg", "who": who, "text": "%s 은(는) 물러났다!" % old.name})
        old.flinched = False
        old.locked = None
        self._bring_in(who, slot, ev)

    def _war_advance(self, side):
        """시즌 5 랭크: 쓰러진(또는 턴 상한으로 물러난) 쪽의 다음 선수를 길드전 AI 처럼 고른다. 판이 끝났으면 True.

        한쪽만 쓰러졌으면 길드전 AI 의 _war_pick (후보마다 내보내 보고 몇 턴 굴린다). 둘 다면 서로 무엇을 낼지 모르니
        관장 배틀이 둘 다 쓰러졌을 때처럼 남은 상대 전부를 두고 본 점수(_pick) - **양쪽이 같은 판을 보고 동시에**
        고른다 (예전처럼 a 가 먼저 고르고 b 가 그걸 보지 않는다).
        """
        down = ("me", "foe") if side == "both" else (side,)
        for who in down:                                 # 물러나는 쪽부터 정리한다 (예전 판과 같은 차례)
            team = self.a if who == "me" else self.b
            self._retire(team[self.ia if who == "me" else self.ib])
        picks = {}
        for who in down:
            team = self.a if who == "me" else self.b
            picks[who] = self._war_next(who, single=side != "both") if any(f.alive() for f in team) else None
        for who in down:
            if picks[who] is None:
                continue
            if who == "me":
                self.ia = picks[who]
            else:
                self.ib = picks[who]
            self.entered[who] = True
            self.switched_last[who] = False
            # 같은 턴에 기술로 물러났다가(유턴 · 탈출버튼 ...) 쓰러졌으면 moved_out 이 남아 있다. 그대로 두면 새로 낸
            # 선수가 첫 턴에 스스로 못 바꾼다 - 길드전 TrainerBattle._settle 도 다음 선수를 낸 뒤 둘 다 푼다 (10/29 검토).
            self.moved_out[who] = False
        a_out = "me" in down and picks["me"] is None
        b_out = "foe" in down and picks["foe"] is None
        if a_out and b_out:
            self.winner = "draw"
        elif a_out:
            self.winner = "foe"
        elif b_out:
            self.winner = "me"
        else:
            return False
        return True

    def _war_next(self, who, single):
        """who 쪽이 다음에 낼 자리 (살아 있는 선수가 있을 때만 부른다)."""
        t0 = time.time()
        team = self.a if who == "me" else self.b
        try:
            m = self._mirror(who)
            if single and m.WAR_V2 and self._war_left() > 0:
                nxt = m._war_pick()
                self.war_sent[who] = self.turns
            else:
                nxt = m._pick(m.foe_team, m.me)
        except Exception:                               # noqa: BLE001
            self.war_stats["error"] += 1
            nxt = None
        self.war_spent += time.time() - t0
        if nxt is None or not (0 <= nxt < len(team)) or not team[nxt].alive():
            nxt = self._pick_against(team, (self.b if who == "me" else self.a)[self.ib if who == "me" else self.ia])
        return nxt

    def _by_headcount(self):
        """상한까지 안 끝났을 때. 남은 마릿수 -> 남은 체력 비율 순으로."""
        na = sum(1 for f in self.a if f.alive())
        nb = sum(1 for f in self.b if f.alive())
        if na != nb:
            return "me" if na > nb else "foe"
        ra = sum(f.hp / float(f.maxhp or 1) for f in self.a)
        rb = sum(f.hp / float(f.maxhp or 1) for f in self.b)
        if abs(ra - rb) < 1e-9:
            return "draw"
        return "me" if ra > rb else "foe"


def simulate(dex, a_mons, b_mons, seed=None, keystone=None, zring=None, war_ai=False):
    """한 줄로 쓰는 입구. keystone = {"me": a 가 가졌나, "foe": b 가 가졌나}.

    zring 도 같은 꼴이다 (시즌 4). 안 주면 Z기술 없이 싸운다 -
    그때의 로그는 예전과 한 글자도 다르지 않다.
    war_ai: 양쪽 다 길드전 방어 AI 로 고른다 (시즌 5 랭크 · 연습판, 맨 위 설명). 안 주면 예전 판 그대로.
    """
    return PartyBattle(dex, a_mons, b_mons, seed, keystone=keystone, zring=zring, war_ai=war_ai).run()


def _steady_choose(bt, user, target):
    """Battle.choose_for 의 'trainer' 고르기에서 15% 무작위만 뺀 것 (시즌 5 랭크가 셈에 실패했을 때)."""
    rng, bt.rng = bt.rng, _NoSlip
    try:
        return bt.choose_for(user, target, "trainer")
    finally:
        bt.rng = rng


# 시점 뒤집기 --------------------------------------------------------
# 저장된 로그는 항상 a 시점이다. b 쪽 화면에서는 이걸 통과시켜 뒤집는다.
# 뒤집을 것을 한 군데 모아 둔다 - 흩어 놓으면 하나를 빠뜨리고, 그러면
# 진 쪽 화면에서만 체력바가 반대로 나오는 식으로 조용히 어긋난다.
_FLIP = {"me": "foe", "foe": "me"}


def flip(ev):
    """이벤트 하나를 상대 시점으로."""
    out = dict(ev)
    for k in ("who", "side", "target", "winner"):
        if out.get(k) in _FLIP:
            out[k] = _FLIP[out[k]]
    if "me" in out or "foe" in out:
        me, foe = out.get("me"), out.get("foe")
        if me is not None:
            out["foe"] = me
        if foe is not None:
            out["me"] = foe
    # 자리 번호도 같이 뒤집는다. 안 그러면 상대 화면에서 엉뚱한 자리의
    # 포켓몬이 링으로 나온다.
    if "mi" in out or "fi" in out:
        mi, fi = out.get("mi"), out.get("fi")
        if mi is not None:
            out["fi"] = mi
        if fi is not None:
            out["mi"] = fi
    return out


def flip_log(events):
    return [flip(e) for e in events]
