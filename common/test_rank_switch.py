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
    9. 효과 있는 공격 기술이 하나라도 있으면 효과 없는 공격 기술은 아예 안 고른다 (2026-11-21 게시판 #764 - 두 턴째 나와 있는
       하마돈에게 볼트체인지). 셈이 무효 기술을 크게 쳐 줘도 빼고, 공격이 다 무효면 그대로 둔다 (WAR_NOEFFECT_DROP).
   10. 불가사의부적(효과가 굉장하지 않으면 막는다)도 무효로 본다 - 테라스탈로 바뀐 타입으로.
   11. 공격 기술이 **다** 막히면 (2026-11-23 게시판 #819 - 워시로토무 대 마중물 트리토돈) 교체나 쓸모 있는 변화기가 남을 때
       막힌 공격을 다 뺀다 (WAR_ALLBLOCK_DROP). 흡수(마중물 ...)는 '상대를 키운다' 로 따로 안다.
   12. 그 판의 세 장면(동료 둘 · 혼자 남음)에서 막힌 공격을 안 고른다 - 아픔나누기는 조금이라도 오르면 쳐 준다.
   13. 쓸 만한 것이 없어도(아픔나누기가 손해) 상대를 키우는 흡수 공격은 안 쓴다 - 그냥 무효인 공격으로.
   14. 불가사의부적에 막히는 공격은 '확실히 쓰러뜨린다'(_secure_ko)에 넣지 않는다 (2026-11-26 게시판 #606 - 체력 1 인 껍질몬은
       어림 데미지가 조금만 나와도 KO 라, 막히는 공격이 다 뽑혀 교체 · 변화기가 선택지에서 사라졌다. WAR_KO_GUARD).
   15. 공격이 다 막혔고 교체가 있으면 공격 쪽만 올리는 변화기(나쁜음모 ...)도 뺀다 (WAR_ALLBLOCK_IDLE_BOOST).
   16. 판 전체: 전기 테라 껍질몬 앞의 헬가가 막히는 화염방사를 되풀이하지 않고 지진 대짱이로 바꾼다.
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
                    m.WAR_NOEFFECT_DROP = False        # 9 의 빼기도 끈다 (감점만의 몫을 보려고)
                m.rng.seed(seed)
                opt = m._war_search(("move", "-"))
                k = opt[1] if opt[0] == "move" else "교체"
                got[on][k] = got[on].get(k, 0) + 1
    finally:
        TB.TrainerBattle._eval_v2 = real
    chk("7. 셈이 비기면 효과 없는 기술은 안 고른다 (40번)", "CLOSECOMBAT" not in got[True], got[True])
    chk("7. (견줌) 감점을 끄면 비긴 셈에서 인파이트가 뽑힌 적이 있다", got[False].get("CLOSECOMBAT", 0) > 0, got[False])


def t_무효_빼기(dex):
    """9 · 10: 효과 있는 공격이 있으면 효과 없는 공격은 아예 안 고른다 · 불가사의부적도 무효로 본다 (게시판 #764)."""
    print("\n=== 랭크 AI: 효과 없는 공격 빼기 (게시판 #764) · 불가사의부적 ===")
    # 9. 셈이 무효 기술 쪽을 크게 쳐 줘도 (운영의 판: 다음 턴에 어차피 쓰러져 모든 공격의 값이 같고, '상대가 교체해 오면'
    #    갈래와 최악 섞기가 볼트체인지에 0.5 남짓을 더했다 - 감점 0.3 보다 컸다) 빼고 고른다. 끄면 뽑힌다.
    real, real_act = TB.TrainerBattle._eval_v2, TB.TrainerBattle.act

    def act(self, *a, **kw):                           # 사본이 셈하는 수를 적어 둔다 (act 가 _forced 를 비운다)
        if getattr(self, "_forced", None) is not None:
            self._probe = self._forced
        return real_act(self, *a, **kw)
    TB.TrainerBattle.act = act
    TB.TrainerBattle._eval_v2 = lambda self: 1.0 if getattr(self, "_probe", None) == ("move", "VOLTSWITCH") else 0.0
    got = {True: {}, False: {}}
    try:
        for on in (True, False):
            for seed in range(12):
                a = [mon("HIPPOWDON", ["EARTHQUAKE", "SLACKOFF"]), mon("CORVIKNIGHT", ["BRAVEBIRD"])]
                b = [mon("MIRAIDON", ["VOLTSWITCH", "DRACOMETEOR", "OVERHEAT", "DRAGONPULSE"]),
                     mon("GARCHOMP", ["EARTHQUAKE"])]
                pb, bt = fresh(dex, a, b, seed)
                pb.turns = 3
                pb.in_at = {"me": 1, "foe": 1}
                m = pb._mirror("foe")
                m.turn += 1
                m.bt.turn_no = m.turn
                m.WAR_NOEFFECT_DROP = on
                m.rng.seed(seed)
                opt = m._war_search(("move", "DRAGONPULSE"))
                k = opt[1] if opt[0] == "move" else "교체"
                got[on][k] = got[on].get(k, 0) + 1
    finally:
        TB.TrainerBattle._eval_v2, TB.TrainerBattle.act = real, real_act
    chk("9. 볼트체인지는 하마돈(땅)에게 효과 없음", m._no_effect("VOLTSWITCH"))
    chk("9. 셈이 볼트체인지를 쳐 줘도 빼고 고른다 (12번)", "VOLTSWITCH" not in got[True], got[True])
    chk("9. (견줌) 빼기를 끄면 셈대로 볼트체인지를 고른다", got[False].get("VOLTSWITCH", 0) > 0, got[False])

    # 9. 공격이 다 무효면 빼지 않는다 (변화기 · 교체와 겨룬다 - 감점은 그대로)
    a = [mon("HIPPOWDON", ["EARTHQUAKE"])]
    b = [mon("PIKACHU", ["THUNDERBOLT", "VOLTSWITCH", "THUNDERWAVE"])]
    pb, bt = fresh(dex, a, b)
    m = pb._mirror("foe")
    opts = [("move", "THUNDERBOLT"), ("move", "VOLTSWITCH"), ("move", "THUNDERWAVE")]
    chk("9. 공격이 다 무효면 선택지를 그대로 둔다", m._drop_no_effect(opts) == opts, m._drop_no_effect(opts))

    # 10. 불가사의부적: 효과가 굉장하지 않으면 막는다 - 테라스탈로 타입이 바뀌어도 그 타입으로 본다
    a = [mon("SHEDINJA", ["SHADOWCLAW"], ability="WONDERGUARD")]
    b = [mon("KINGAMBIT", ["SUCKERPUNCH", "IRONHEAD", "KOWTOWCLEAVE", "SWORDSDANCE"])]
    pb, bt = fresh(dex, a, b)
    m = pb._mirror("foe")
    chk("10. 껍질몬(벌레/고스트)에게 기습 · 도각참(악)은 효과가 굉장하다", not m._no_effect("SUCKERPUNCH")
        and not m._no_effect("KOWTOWCLEAVE"))
    chk("10. 아이언헤드(강철)는 불가사의부적에 막힌다", m._no_effect("IRONHEAD"))
    m.WAR_NOEFFECT_DROP = False
    chk("10. (견줌) 끄면 예전처럼 불가사의부적을 모른다", not m._no_effect("IRONHEAD"))
    m.WAR_NOEFFECT_DROP = True
    m.me.tera = "ELECTRIC"                             # 운영의 그 껍질몬 (전기 테라스탈 - 약점이 땅 하나)
    chk("10. 전기로 테라스탈한 껍질몬에게는 기습 · 도각참도 막힌다",
        m._no_effect("SUCKERPUNCH") and m._no_effect("KOWTOWCLEAVE"), m.me.types())


def t_다_막힘(dex):
    """11 · 12 · 13: 공격 기술이 다 막힐 때 (게시판 #819 - 워시로토무 대 마중물 트리토돈, 랭크 #65364)."""
    print("\n=== 랭크 AI: 공격이 다 막힐 때 (게시판 #819) ===")

    def rotom():
        m = mon("ROTOM", ["THUNDERBOLT", "VOLTSWITCH", "HYDROPUMP", "PAINSPLIT"], held="SITRUSBERRY",
                ability="LEVITATE", nature="MODEST")
        m["form"] = "WASH"                             # 전기/물
        return m

    def gastro():
        return mon("GASTRODON", ["MUDDYWATER", "EARTHQUAKE", "RECOVER", "ICEBEAM"], held="LEFTOVERS",
                   ability="STORMDRAIN", nature="CALM")

    ATTACKS = ("THUNDERBOLT", "VOLTSWITCH", "HYDROPUMP")

    def plan(mates, rotom_hp, gas_hp, seed, on=True):
        b = [rotom()] + [mon("AEGISLASH", ["SACREDSWORD", "IRONHEAD"]), mon("MIMIKYU", ["PLAYROUGH"])][:max(1, mates)]
        pb, bt = fresh(dex, [gastro(), mon("CORVIKNIGHT", ["BODYPRESS", "BRAVEBIRD"])], b, seed)
        pb.turns = 6
        pb.in_at = {"me": 1, "foe": 1}
        pb.b[0].hp, pb.a[0].hp = rotom_hp, gas_hp
        if not mates:
            for f in pb.b[1:]:
                f.hp = 0                               # 로토무 혼자 남았다
        keep = TB.TrainerBattle.WAR_ALLBLOCK_DROP
        TB.TrainerBattle.WAR_ALLBLOCK_DROP = on
        try:
            slot, key = pb._war_plan("foe")
            m = pb._mirror("foe")
        finally:
            TB.TrainerBattle.WAR_ALLBLOCK_DROP = keep
        return ("교체" if slot is not None else key), m

    _k, m = plan(2, 82, 81, 0)
    chk("11. (전제) 셋 다 막힌다: 10만볼트 · 볼트체인지(땅) · 하이드로펌프(마중물)",
        all(m._no_effect(k) for k in ATTACKS), [m._no_effect(k) for k in ATTACKS])
    chk("11. 마중물에 먹히는 하이드로펌프만 '상대를 키운다'",
        m._feeds_foe("HYDROPUMP") and not m._feeds_foe("THUNDERBOLT") and not m._feeds_foe("VOLTSWITCH"))
    opts = [("move", k) for k in ATTACKS + ("PAINSPLIT",)] + [("switch", 1)]
    chk("11. 교체나 쓸모 있는 변화기가 남으면 막힌 공격을 다 뺀다",
        m._drop_no_effect(opts) == [("move", "PAINSPLIT"), ("switch", 1)], m._drop_no_effect(opts))

    for label, mates, rh, gh in (("동료 둘 · 82 대 81 (6라운드)", 2, 82, 81), ("동료 둘 · 46 대 191 (4라운드)", 2, 46, 191),
                                 ("혼자 · 86 대 110 (8라운드)", 0, 86, 110)):
        got = {}
        for seed in range(12):
            k, _m = plan(mates, rh, gh, seed)
            got[k] = got.get(k, 0) + 1
        chk("12. %s: 막힌 공격을 안 고른다 (아픔나누기 · 교체)" % label, not any(k in got for k in ATTACKS), got)

    # 13. 아픔나누기가 손해(내 체력이 더 많다)면 쓸 만한 것이 없다 - 그래도 상대를 키우는 하이드로펌프만은 안 쓴다
    got, off = {}, {}
    for seed in range(12):
        k, m = plan(0, 150, 60, seed)
        got[k] = got.get(k, 0) + 1
        k2, _m = plan(0, 150, 60, seed, on=False)
        off[k2] = off.get(k2, 0) + 1
    chk("13. (전제) 150 대 60 이면 아픔나누기는 손해다", not m._some_gain("PAINSPLIT"))
    chk("13. 쓸 만한 것이 없어도 마중물에 하이드로펌프는 안 쏜다 (그냥 무효인 공격으로)",
        "HYDROPUMP" not in got and "PAINSPLIT" not in got, got)
    chk("13. (견줌) 끄면 하이드로펌프를 고른 적이 있다", off.get("HYDROPUMP", 0) > 0, off)


def t_껍질몬(dex):
    """14 · 15 · 16: 불가사의부적 껍질몬 앞에서 막히는 공격만 되풀이하지 않는다 (게시판 #606, 2026-11-26)."""
    print("\n=== 랭크 AI: 껍질몬 (게시판 #606) ===")
    shed = mon("SHEDINJA", ["SHADOWSNEAK", "METALCLAW", "CONFUSERAY", "SHADOWCLAW"], held="ELECTRICTERASHARD",
               ability="WONDERGUARD")
    hound = mon("HOUNDOOM", ["FLAMETHROWER", "DARKPULSE", "SLUDGEBOMB", "NASTYPLOT"], ability="FLASHFIRE")
    swamp = mon("SWAMPERT", ["ICEPUNCH", "LIQUIDATION", "EARTHQUAKE", "STEALTHROCK"], held="LEFTOVERS",
                ability="TORRENT")
    BLOCKED = ("FLAMETHROWER", "DARKPULSE", "SLUDGEBOMB")

    # 14. 체력 1 인 껍질몬 - 막히는 공격도 데미지 어림으로는 다 KO 다. '확실히 쓰러뜨린다' 에 넣지 않는다.
    pb, bt = fresh(dex, [shed], [hound, swamp])
    m = pb._mirror("foe")
    m.me.tera = "ELECTRIC"                             # 운영의 그 껍질몬 (전기 테라스탈 - 약점이 땅 하나)
    m.foe.hp = 40                                      # 껍질몬의 섀도클로가 위협이 되는 체력 (KO_FORCE_THREAT)
    chk("14. (전제) 헬가의 공격 셋이 다 불가사의부적에 막힌다", all(m._no_effect(k) for k in BLOCKED))
    chk("14. 막히는 공격은 '확실한 KO' 가 아니다", m._secure_ko() == [], m._secure_ko())
    m.WAR_KO_GUARD = False
    chk("14. (견줌) 끄면 막히는 공격이 다 '확실한 KO' 로 뽑혔다 - 선택지가 그것들로 좁혀졌다",
        sorted(m._secure_ko()) == sorted(BLOCKED), m._secure_ko())
    m.WAR_KO_GUARD = True

    # 15. 공격이 다 막혔고 교체가 있으면 공격 쪽만 올리는 변화기(나쁜음모)도 뺀다. 버티는 능력도 올리면(명상) 둔다.
    opts = [("move", k) for k in BLOCKED + ("NASTYPLOT",)] + [("switch", 1)]
    chk("15. 막힌 공격 · 나쁜음모를 빼고 교체만 남긴다", m._drop_no_effect(opts) == [("switch", 1)], m._drop_no_effect(opts))
    chk("15. 나쁜음모는 '쓸 데 없는 능력 올리기' · 명상(특수방어도 올림)은 아니다",
        m._idle_boost("NASTYPLOT") and m._idle_boost("DRAGONDANCE") and not m._idle_boost("CALMMIND")
        and not m._idle_boost("FLAMETHROWER"))
    alone = [("move", k) for k in BLOCKED + ("NASTYPLOT",)]
    chk("15. 바꿀 자리가 없으면 나쁜음모는 그대로 남는다 (빼면 막힌 공격만 남는다)",
        ("move", "NASTYPLOT") in m._drop_no_effect(alone), m._drop_no_effect(alone))
    m.WAR_ALLBLOCK_IDLE_BOOST = False
    chk("15. (견줌) 끄면 나쁜음모가 남는다", ("move", "NASTYPLOT") in m._drop_no_effect(opts), m._drop_no_effect(opts))
    m.WAR_ALLBLOCK_IDLE_BOOST = True

    # 16. 판 전체: 헬가가 껍질몬을 위협하면 껍질몬이 전기 테라스탈 -> 헬가는 막히는 공격을 되풀이하지 않고 대짱이(지진)로 바꾼다
    def play(seed, on=True):
        keep = (TB.TrainerBattle.WAR_KO_GUARD, TB.TrainerBattle.WAR_ALLBLOCK_IDLE_BOOST)
        TB.TrainerBattle.WAR_KO_GUARD = TB.TrainerBattle.WAR_ALLBLOCK_IDLE_BOOST = on
        try:
            out = PB.simulate(dex, [hound, swamp], [shed], seed=seed, keystone={"me": False, "foe": False},
                              zring={"me": False, "foe": False}, war_ai=True, tera_orb={"me": True, "foe": True})
        finally:
            TB.TrainerBattle.WAR_KO_GUARD, TB.TrainerBattle.WAR_ALLBLOCK_IDLE_BOOST = keep
        tera, cur, wasted = False, None, 0
        for e in out["events"]:
            if e.get("t") == "round":
                cur = (e.get("me") or {}).get("species")
            elif e.get("t") == "tera" and e.get("who") == "foe":
                tera = True
            elif e.get("t") == "move" and e.get("who") == "me" and cur == "HOUNDOOM" and tera:
                wasted += 1                            # 테라스탈한 다음 턴부터 헬가가 쓴 기술
        return out["winner"], tera, wasted
    on = [play(s) for s in range(4)]
    off = [play(s, False) for s in range(4)]
    chk("16. (전제) 네 판 다 껍질몬이 전기 테라스탈한다", all(t for _w, t, _n in on + off), on + off)
    chk("16. 테라스탈한 뒤 헬가는 막히는 공격을 한 번 넘게 안 쓰고 바꾼다 · 대짱이가 이긴다",
        all(w == "me" and n <= 1 for w, _t, n in on), on)
    chk("16. (견줌) 끄면 헬가가 막히는 공격을 판마다 다섯 번 넘게 썼다", all(n >= 5 for _w, _t, n in off), off)


def t_묶은_쪽이_쓰러지면(dex):
    """조이기류: 묶은 쪽이 쓰러지면 묶기가 풀린다 (본가 · 관장 판과 같다). 랭크는 라운드마다 판을 새로 세워서
    묶인 쪽 cond 의 bound 가 다음 라운드까지 따라가, 새로 나온 상대에게도 데미지와 교체 봉인이 이어졌다 (11/19 #664 검토)."""
    print("\n-- 묶은 쪽이 쓰러지면 묶기가 풀린다")
    for war in (True, False):
        a = [mon("CHARIZARD", ["FIRESPIN"]), mon("SNORLAX", ["BODYSLAM"])]
        b = [mon("BLISSEY", ["SEISMICTOSS"]), mon("SKARMORY", ["BRAVEBIRD"])]
        pb = PB.PartyBattle(dex, a, b, 7, keystone={"me": False, "foe": False},
                            zring={"me": False, "foe": False}, war_ai=war)
        pb.events.append({"t": "teams"})
        pb.round_no = 1
        bt = pb._round_battle()
        foe = bt.foe
        foe.cond["bound"] = {"turns": 4, "by": "me", "move": "FIRESPIN"}
        bt.me.hp = 0                                    # 묶은 리자몽이 쓰러졌다
        pb._advance("me")
        chk("%s: 묶은 쪽이 쓰러지면 상대의 묶기가 풀린다" % ("시즌5 랭크(_war_advance)" if war else "랭크(_advance)"),
            not foe.cond.get("bound"), foe.cond.get("bound"))


def main():
    dex = P.Pokedex.load(os.path.join(ROOT, "server", "data", "pokedex.json"))
    t_판정(dex)
    t_날뛰기(dex)
    t_랭크(dex)
    t_무효(dex)
    t_무효_빼기(dex)
    t_다_막힘(dex)
    t_껍질몬(dex)
    t_묶은_쪽이_쓰러지면(dex)
    print("\n합계 OK %d · FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
