# -*- coding: utf-8 -*-
"""시즌 5 랭크의 지나친 교체 + 교체에 얽힌 판정 버그 두 개 (2.0.2 추가, 서버만). 서버 없이 엔진만.

    python common/test_rank_switch.py

게시판 의견: 랭크 자동 배틀이 상성을 노린 맞교체를 끝없이 되풀이해 판이 늘어진다 · 나오자마자 또 바꾼다 ·
구애 도구 잠금이 교체 뒤에도 남는다 · 페어리에게 역린을 계속 쓴다.

  판정 (엔진 공용 - 모든 배틀)
    1. 유턴으로 물러나면 구애 잠금이 풀린다 (예전: 물러난 뒤 note_move 가 다시 잠갔다).
    2. 날려 보내기로 끌려 나가도 풀린다 (파티전 _retire).
    3. 역린이 맞히는 데까지 못 가면(무효) 날뛰기가 그 자리에서 끝난다 - 교체도 다시 된다.
       본가(Showdown lockedmove)대로 마지막 턴에 끊기면 지쳐서 혼란, 중간 턴 · 잠듦이면 혼란 없음.
       소란피기는 끊겨도 정해진 턴 동안 이어진다.
  랭크 AI (war_ai=True 만)
    4. 한쪽만 쓰러져 새로 낸 선수는 그 첫 턴에 스스로 안 바꾼다. 둘 다 쓰러졌으면 바꿀 수 있다.
    5. 물러난 지 5턴 안 된 선수를 다시 부르기 · 나온 지 2턴 안 된 선수를 바꾸기에 감점.
       끌려 들어온 선수(울부짖기 ...)는 AI 가 고른 게 아니라 앞 선수의 감점을 물려받지 않는다.
    6. 길드전(사람 상대) TrainerBattle 의 교체 감점은 0 이다.
    7. 지금 나와 있는 상대에게 효과 없는 공격 기술은 점수가 비슷할 때 뒤로 민다 (게시판 #404 - 이미 나와 있는 따라큐에게
       인파이트). 셈이 비기면 한 번도 안 고른다. 길드전 AI 는 그대로다.
    8. #404 장면(실제 두 팀 · 남은 HP, 메가엘레이드 23 HP 대 탈이 그대로인 따라큐)에서 인파이트를 안 고른다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import random                                # noqa: E402

from common import battle as B               # noqa: E402
from common import party_battle as PB        # noqa: E402
from common import pokelogic as P            # noqa: E402
from common import statusmoves as SM         # noqa: E402
from common import trainer_battle as TB      # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mon(species, moves, held=None, ability=None, nature="JOLLY"):
    return TB.trainer_mon({"species": species, "level": 50, "iv": 31, "moves": moves, "held": held,
                           "ability": ability, "nature": nature, "evs": {}})


def fresh(dex, a, b, seed=7):
    """랭크 판을 첫 라운드 앞까지 세운다 (run 의 앞부분과 같다)."""
    pb = PB.PartyBattle(dex, a, b, seed, keystone={"me": False, "foe": False},
                        zring={"me": False, "foe": False}, war_ai=True)
    pb.events.append({"t": "teams"})
    pb.round_no = 1
    bt = pb._round_battle()
    pb._entry_abilities(bt)
    return pb, bt


def turn(pb, bt, me_plan, foe_plan):
    """양쪽 수를 정해 한 턴 (_war_turn 과 같은 갈림길). plan = (바꿀 자리, 기술)."""
    plan = {"me": me_plan, "foe": foe_plan}
    pb.moved_out = {"me": False, "foe": False}
    if plan["me"][0] is None and plan["foe"][0] is None:
        bt.planned = plan["foe"][1]
        try:
            ev = bt.take_turn(plan["me"][1])
        finally:
            bt.planned = None
    else:
        ev = pb._switch_turn(bt, plan)
    pb.turns += 1
    for who in ("me", "foe"):
        pb.switched_last[who] = plan[who][0] is not None or pb.moved_out[who]
    return ev


def t_판정(dex):
    print("\n=== 판정: 구애 잠금 · 역린 ===")
    scarf = mon("DRAGAPULT", ["UTURN", "DRAGONDARTS", "PHANTOMFORCE", "FIREBLAST"], held="CHOICESCARF")
    mate = mon("GARCHOMP", ["EARTHQUAKE", "DRAGONCLAW", "STONEEDGE", "SWORDSDANCE"])
    wall = mon("BLISSEY", ["SOFTBOILED", "SEISMICTOSS", "TOXIC", "CALMMIND"], nature="BOLD")
    wall2 = mon("SKARMORY", ["ROOST", "BRAVEBIRD", "SPIKES", "WHIRLWIND"], nature="IMPISH")

    pb, bt = fresh(dex, [scarf, mate], [wall, wall2])
    turn(pb, bt, (None, "UTURN"), (None, "SEISMICTOSS"))
    chk("1. 유턴으로 물러났다", bt.me is pb.a[1], bt.me.name)
    chk("1. 물러난 구애스카프의 잠금이 풀린다", pb.a[0].locked is None, pb.a[0].locked)
    turn(pb, bt, (0, None), (None, "SEISMICTOSS"))
    ev = turn(pb, bt, (None, "FIREBLAST"), (None, "SEISMICTOSS"))
    used = [e.get("text") for e in ev if e.get("t") == "move" and e.get("who") == "me"]
    chk("1. 돌아와서 유턴이 아닌 기술을 쓴다", any("불대문자" in (t or "") for t in used), used)

    pb, bt = fresh(dex, [scarf, mate], [wall2, wall])
    turn(pb, bt, (None, "DRAGONDARTS"), (None, "SPIKES"))
    chk("2. 기술을 쓰면 잠긴다 (전제)", pb.a[0].locked == "DRAGONDARTS", pb.a[0].locked)
    turn(pb, bt, (None, "DRAGONDARTS"), (None, "WHIRLWIND"))
    chk("2. 날려 보내기로 끌려 나갔다", bt.me is pb.a[1], bt.me.name)
    chk("2. 끌려 나가면 잠금이 풀린다", pb.a[0].locked is None, pb.a[0].locked)

    hax = mon("HAXORUS", ["OUTRAGE", "EARTHQUAKE", "POISONJAB", "DRAGONDANCE"], ability="MOLDBREAKER")
    lax = mon("SNORLAX", ["BODYSLAM", "REST", "CURSE", "EARTHQUAKE"], nature="CAREFUL")
    fairy = mon("SYLVEON", ["HYPERVOICE", "CALMMIND", "WISH", "PROTECT"], nature="CALM")
    pb, bt = fresh(dex, [hax], [lax, fairy], seed=3)
    turn(pb, bt, (None, "OUTRAGE"), (None, "CURSE"))
    chk("3. 역린을 쓰면 날뛴다 (전제)", bool(bt.me.cond.get("rage")) and bool(SM.must_stay(bt.me)),
        bt.me.cond.get("rage"))
    ev = turn(pb, bt, (None, "OUTRAGE"), (1, None))
    chk("3. 페어리가 나와 역린이 안 통했다", bt.foe is pb.b[1] and
        any("효과가 없" in (e.get("text") or "") for e in ev), [e.get("text") for e in ev][-4:])
    chk("3. 안 통하면 날뛰기가 끝난다", not bt.me.cond.get("rage"), bt.me.cond.get("rage"))
    chk("3. 날뛰기가 끝나 다시 바꿀 수 있다", not SM.must_stay(bt.me))


def t_날뛰기(dex):
    print("\n=== 판정: 날뛰기가 끊길 때 (본가 Showdown lockedmove · uproar) ===")

    def duel(move, turns, foe, foe_moves, prep=None):
        a = B.Fighter(dex, mon("HAXORUS", [move, "EARTHQUAKE", "POISONJAB", "DRAGONDANCE"]))
        b = B.Fighter(dex, mon(foe, foe_moves))
        a.ability_on = b.ability_on = True
        bt = B.Battle(dex, a, b, random.Random(1), ai="trainer")
        bt.kind = "pvp"
        bt.me.cond["rage"] = {"move": move, "turns": turns}
        if prep:
            prep(bt)
        ev = []
        bt._use("me", bt.me, bt.foe, move, ev)
        return bt, [e.get("text") or "" for e in ev]

    bt, tx = duel("OUTRAGE", 1, "SNORLAX", ["CURSE"])
    chk("기준: 마지막 턴에 맞히면 끝나고 혼란", not bt.me.cond.get("rage") and bt.me.cond.get("confused"), tx)
    bt, tx = duel("OUTRAGE", 1, "SYLVEON", ["CALMMIND"])
    chk("마지막 턴에 페어리에게 무효 - 끝나고 혼란 (본가)", not bt.me.cond.get("rage") and bt.me.cond.get("confused")
        and any("효과가 없" in t for t in tx), tx)
    bt, tx = duel("OUTRAGE", 2, "SYLVEON", ["CALMMIND"])
    chk("중간 턴에 무효 - 끝나고 혼란 없음", not bt.me.cond.get("rage") and not bt.me.cond.get("confused"), tx)

    def sleep(bt):
        bt.me.status = "sleep"
        bt.me.sleep_turns = 3
    bt, tx = duel("OUTRAGE", 1, "SNORLAX", ["CURSE"], prep=sleep)
    chk("마지막 턴이라도 잠들어 못 쓰면 혼란 없이 끝", not bt.me.cond.get("rage") and not bt.me.cond.get("confused")
        and bt.me.status == "sleep", (bt.me.status, tx))
    bt, tx = duel("UPROAR", 2, "GENGAR", ["NASTYPLOT"])
    chk("소란피기는 고스트에게 무효여도 이어진다 (끊긴 턴도 한 턴으로)", (bt.me.cond.get("rage") or {}).get("turns") == 1,
        bt.me.cond.get("rage"))
    bt, tx = duel("UPROAR", 1, "GENGAR", ["NASTYPLOT"])
    chk("  마지막 턴이면 거기서 끝 (혼란 없음)", not bt.me.cond.get("rage") and not bt.me.cond.get("confused"),
        bt.me.cond.get("rage"))


def t_랭크(dex):
    print("\n=== 랭크 AI: 교체 감점 ===")
    a = [mon("GARCHOMP", ["EARTHQUAKE", "DRAGONCLAW", "STONEEDGE", "SWORDSDANCE"]),
         mon("ROTOMWASH", ["HYDROPUMP", "VOLTSWITCH", "WILLOWISP", "PROTECT"], nature="BOLD"),
         mon("CORVIKNIGHT", ["BRAVEBIRD", "BODYPRESS", "ROOST", "BULKUP"], nature="IMPISH")]
    b = [mon("TOGEKISS", ["AIRSLASH", "DAZZLINGGLEAM", "ROOST", "NASTYPLOT"], nature="TIMID"),
         mon("TYRANITAR", ["STONEEDGE", "CRUNCH", "EARTHQUAKE", "DRAGONDANCE"]),
         mon("GENGAR", ["SHADOWBALL", "SLUDGEBOMB", "FOCUSBLAST", "NASTYPLOT"], nature="TIMID")]

    pb, bt = fresh(dex, a, b)
    chk("5. 판 첫 턴은 '나온 지 2턴 안' 이라 모든 자리에 감점", pb._rank_cost("me", pb.a) ==
        {0: PB.PartyBattle.RANK_SETTLE_PEN, 1: PB.PartyBattle.RANK_SETTLE_PEN, 2: PB.PartyBattle.RANK_SETTLE_PEN},
        pb._rank_cost("me", pb.a))
    turn(pb, bt, (None, "SWORDSDANCE"), (None, "NASTYPLOT"))
    turn(pb, bt, (None, "SWORDSDANCE"), (None, "ROOST"))
    chk("5. 두 턴을 버틴 뒤에는 감점 없음", pb._rank_cost("me", pb.a) == {}, pb._rank_cost("me", pb.a))
    turn(pb, bt, (2, None), (None, "AIRSLASH"))                   # 한카리아스 -> 아머까오 (스스로)
    t = pb.turns + 1
    cost = pb._rank_cost("me", pb.a)
    chk("5. 막 물러난 한카리아스를 다시 부르면 되부르기 + 자리 잡기 감점",
        abs(cost.get(0, 0) - (PB.PartyBattle.RANK_RECALL_PEN + PB.PartyBattle.RANK_SETTLE_PEN)) < 1e-9, cost)
    chk("5. 물러난 적 없는 로토무는 자리 잡기 감점만", abs(cost.get(1, 0) - PB.PartyBattle.RANK_SETTLE_PEN) < 1e-9, cost)
    pb.turns = t - 1 + PB.PartyBattle.RANK_RECALL_TURNS + 1         # 되부르기 창이 지난 뒤
    chk("5. 5턴이 지나면 되부르기 감점이 사라진다", pb._rank_cost("me", pb.a) == {}, pb._rank_cost("me", pb.a))
    m = pb._mirror("me")
    chk("5. 거울 판이 같은 감점을 본다", m._switch_cost(0) == pb._rank_cost("me", pb.a).get(0, 0.0))

    pb, bt = fresh(dex, a, b)
    chk("5. (전제) 판 첫 턴의 foe 는 자리 잡기 감점", pb._rank_cost("foe", pb.b) != {}, pb._rank_cost("foe", pb.b))
    pb._move_switch("foe", "drag", [], "WHIRLWIND")
    chk("5. 끌려 들어온 선수는 앞 선수의 자리 잡기 감점을 물려받지 않는다", pb._rank_cost("foe", pb.b) == {},
        pb._rank_cost("foe", pb.b))

    # 4. 한쪽만 쓰러졌을 때 / 둘 다 쓰러졌을 때
    pb, bt = fresh(dex, a, b)
    pb.b[0].hp = 0
    pb._war_advance("foe")
    chk("4. 한쪽만 쓰러져 낸 선수는 첫 턴에 안 바꾼다", pb.switched_last["foe"] is True, pb.switched_last)
    chk("4. 쓰러지지 않은 쪽은 그대로", pb.switched_last["me"] is False, pb.switched_last)
    pb, bt = fresh(dex, a, b)
    pb.a[0].hp = pb.b[0].hp = 0
    pb._war_advance("both")
    chk("4. 둘 다 쓰러졌으면 바로 바꿀 수 있다", pb.switched_last == {"me": False, "foe": False}, pb.switched_last)

    # 6. 길드전은 감점 없음
    g = TB.TrainerBattle.__new__(TB.TrainerBattle)
    chk("6. 길드전 TrainerBattle 의 교체 감점은 0", g._switch_cost(0) == 0.0)


# 게시판 #404 (11/01 39936) 의 두 팀 - 운영 랭크 팀 그대로 (종 · 성격 · 특성 · 도구 · 개체값 · 노력치 · 기술, 레벨은 50 상한)
_ST = ("hp", "atk", "def", "spa", "spd", "spe")
_404_A = [  # 나라
    ("GHOLDENGO", "QUIRKY", "GOODASGOLD", "AIRBALLOON", (3, 22, 3, 5, 9, 23), (6, 0, 0, 252, 0, 252),
     ["MAKEITRAIN", "DAZZLINGGLEAM", "SHADOWBALL", "POWERGEM"]),
    ("GARCHOMP", "HASTY", "SANDVEIL", "CHOICESCARF", (22, 19, 19, 12, 1, 1), (6, 252, 0, 0, 0, 252),
     ["OUTRAGE", "EARTHQUAKE", "ROCKSLIDE", "FIREFANG"]),
    ("TINKATON", "ADAMANT", "MOLDBREAKER", None, (28, 19, 24, 12, 3, 16), (0, 252, 8, 0, 0, 250),
     ["HARDPRESS", "PLAYROUGH", "ROCKSLIDE", "KNOCKOFF"]),
    ("MIRAIDON", "CALM", "HADRONENGINE", "ASSAULTVEST", (13, 31, 31, 19, 18, 31), (6, 0, 0, 252, 0, 252),
     ["DRAGONPULSE", "DAZZLINGGLEAM", "VOLTSWITCH", "ELECTRODRIFT"]),
    ("MEOWSCARADA", "JOLLY", "OVERGROW", "MUSCLEBAND", (10, 11, 17, 11, 0, 3), (6, 252, 0, 0, 0, 252),
     ["FLOWERTRICK", "KNOCKOFF", "UTURN", "THUNDERPUNCH"]),
    ("GALLADE", "JOLLY", "STEADFAST", "GALLADITE", (7, 8, 15, 5, 1, 25), (6, 252, 0, 0, 0, 252),
     ["CLOSECOMBAT", "NIGHTSLASH", "ZENHEADBUTT", "ICEPUNCH"])]
_404_B = [  # 상대
    ("ARCHALUDON", "JOLLY", "STAMINA", "ASSAULTVEST", (13, 24, 2, 5, 3, 17), (36, 179, 77, 97, 55, 66),
     ["ROCKSMASH", "HYPERBEAM", "DRAGONCLAW", "FLASHCANNON"]),
    ("TYRANITAR", "GENTLE", "SANDSTREAM", "WEAKNESSPOLICY", (11, 16, 9, 23, 21, 12), (55, 252, 30, 110, 19, 44),
     ["ICEPUNCH", "FIREBLAST", "STONEEDGE", "EARTHQUAKE"]),
    ("MIMIKYU", "MILD", "DISGUISE", "MIMIKIUMZ", (6, 10, 16, 2, 6, 28), (65, 208, 57, 74, 48, 58),
     ["SHADOWCLAW", "DESTINYBOND", "PLAYROUGH", "GIGADRAIN"]),
    ("EXCADRILL", "TIMID", "SANDRUSH", "SITRUSBERRY", (30, 30, 15, 10, 29, 29), (42, 172, 63, 100, 68, 65),
     ["RAPIDSPIN", "SLUDGEBOMB", "MEGAHORN", "EARTHQUAKE"]),
    ("GENGAR", "MILD", "CURSEDBODY", "GENGARITE", (29, 19, 18, 11, 24, 18), (40, 198, 67, 72, 55, 78),
     ["THIEF", "SLUDGEWAVE", "SHADOWBALL", "DESTINYBOND"]),
    ("MIRAIDON", "JOLLY", "HADRONENGINE", None, (0, 31, 31, 31, 8, 10), (4, 0, 2, 252, 0, 252),
     ["DRAGONPULSE", "OVERHEAT", "DAZZLINGGLEAM", "ELECTRODRIFT"])]


def _404_scene(dex, seed):
    def team(rows):
        out = []
        for n, (sp, nat, ab, held, iv, ev, mv) in enumerate(rows):
            m = {"id": n + 1, "species": sp, "nickname": None, "level": 50, "exp": 0, "nature": nat, "ability": ab,
                 "hiddenAbility": False, "gender": None, "shiny": False, "happiness": 255,
                 "ivs": dict(zip(_ST, iv)), "evs": dict(zip(_ST, ev)), "moves": list(mv), "held": held}
            if held and held.endswith("ITE"):
                m["bonded"] = True                 # 유대를 마쳤다 (메가진화할 수 있다)
            out.append(m)
        return out
    pb = PB.PartyBattle(dex, team(_404_A), team(_404_B), seed, keystone={"me": True, "foe": True},
                        zring={"me": True, "foe": True}, war_ai=True)
    pb.events.append({"t": "teams"})
    pb.round_no = 4
    pb.ia, pb.ib = 5, 2                        # 메가엘레이드 대 따라큐
    pb.a[1].hp = 0                             # 한카리아스 · 상대 미라이돈은 쓰러졌다
    pb.b[5].hp = 0
    bt = pb._round_battle()
    pb._entry_abilities(bt)
    g = pb.a[5]
    g.mega_evolve(g.mega_target())
    bt.mega_done.add("me")
    g.hp = 23
    pb.turns = 7
    pb.in_at = {"me": 6, "foe": 7}
    pb.switched_last = {"me": False, "foe": True}
    return pb, bt


def t_무효(dex):
    print("\n=== 랭크 AI: 이미 나와 있는 상대에게 효과 없는 기술 (게시판 #404) ===")
    pb, bt = _404_scene(dex, 0)
    m = pb._mirror("me")
    chk("7. 인파이트는 따라큐(고스트)에게 효과 없음", m._no_effect("CLOSECOMBAT"))
    chk("7. 사념의박치기 · 깜짝베기는 효과 있음 (탈이 막아도 깨진다)",
        not m._no_effect("ZENHEADBUTT") and not m._no_effect("NIGHTSLASH"))
    g = TB.TrainerBattle.__new__(TB.TrainerBattle)
    # 2026-11-01 길드전도 켰다 (사람 대역 상대 400판에 판 100개당 8.5번 - 사용자 '멍청해 보이는 수를 줄이자')
    chk("7. 길드전 TrainerBattle 도 같은 감점이 켜져 있다", g.WAR_NOEFFECT_PEN == m.WAR_NOEFFECT_PEN > 0)
    picks = {}
    for seed in range(32):
        pb, bt = _404_scene(dex, seed)
        plan = pb._war_plan("me")
        k = plan[1] if plan[0] is None else "교체"
        picks[k] = picks.get(k, 0) + 1
    chk("8. #404 장면 32번: 인파이트(무효)를 안 고른다", "CLOSECOMBAT" not in picks, picks)

    # 셈이 비길 때 (운영의 그 판은 다음에 나올 두드리짱의 틀깨기 때문에 어느 기술이든 한 턴 뒤 형세가 같았다) - 형세 값을
    # 모두 같게 두면 사본의 운만 남는다. 감점이 있으면 무효 기술은 한 번도 안 뽑히고, 끄면 뽑힌 적이 있다
    real = TB.TrainerBattle._eval_v2
    TB.TrainerBattle._eval_v2 = lambda self: 0.0
    got = {True: {}, False: {}}
    try:
        for on in (True, False):
            for seed in range(40):
                pb, bt = _404_scene(dex, seed)
                m = pb._mirror("me")
                m.turn += 1
                m.bt.turn_no = m.turn
                if not on:
                    m.WAR_NOEFFECT_PEN = 0.0
                m.rng.seed(seed)
                opt = m._war_search(("move", "-"))
                k = opt[1] if opt[0] == "move" else "교체"
                got[on][k] = got[on].get(k, 0) + 1
    finally:
        TB.TrainerBattle._eval_v2 = real
    chk("7. 셈이 비기면 효과 없는 기술은 안 고른다 (40번)", "CLOSECOMBAT" not in got[True], got[True])
    chk("7. (견줌) 감점을 끄면 비긴 셈에서 인파이트가 뽑힌 적이 있다", got[False].get("CLOSECOMBAT", 0) > 0, got[False])


def main():
    dex = P.Pokedex.load(os.path.join(ROOT, "server", "data", "pokedex.json"))
    t_판정(dex)
    t_날뛰기(dex)
    t_랭크(dex)
    t_무효(dex)
    print("\n합계 OK %d · FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
