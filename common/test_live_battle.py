# -*- coding: utf-8 -*-
"""실시간 1:1 배틀 엔진 검사.

    python common/test_live_battle.py

서버도 DB 도 없이 common/live_battle.py 만 본다.

제일 중요한 것 셋.
  · **한쪽만 골라서는 턴이 안 돈다.** 둘 다 들어와야 진행된다.
  · **쓰러진 쪽만 다음을 고른다.** 상대는 그동안 아무것도 안 고른다(본가와 같다).
  · **시점.** 엔진은 a 기준으로 돌고, b 에게 줄 때 한 번 뒤집는다.
"""
import copy
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import battle as B                        # noqa: E402
from common import live_battle as L                   # noqa: E402
from common import pokelogic as P                     # noqa: E402

DEX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "server", "data", "pokedex.json")
OK = FAIL = 0
DEX = None


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mon(species, level=50, moves=None, ivs=31):
    sp = DEX.get(species)
    m = P.make_pokemon(sp, level, random.Random(1), shiny_rate=10 ** 9)
    m["ivs"] = dict((s, ivs) for s in P.STATS)
    m["evs"] = dict((s, 0) for s in P.STATS)
    m["nature"] = "HARDY"
    m["held"] = None
    if moves:
        m["moves"] = list(moves)
    return m


def build(a_team=("SNORLAX", "PIDGEY"), b_team=("SNORLAX", "PIDGEY"),
          moves=("TACKLE",), seed=5, level=50, turns=150):
    a = [L.leveled(mon(x, 100, moves), level) for x in a_team]
    b = [L.leveled(mon(x, 5, moves), level) for x in b_team]
    return L.LiveBattle(DEX, (1, "가", a), (2, "나", b),
                        rng=random.Random(seed), max_turns=turns)


def both(lb, key="TACKLE"):
    for w in ("a", "b"):
        if lb.can_act(w):
            try:
                lb.choose(w, "move", key)
            except ValueError:
                lb.choose(w, *lb.auto_choice(w))


def main():
    global DEX
    DEX = P.Pokedex.load(DEX_PATH)

    print("=== 레벨 맞추기 ===")
    lb = build()
    chk("높은 쪽도 Lv.50", lb.a.mon.level == 50, lb.a.mon.level)
    chk("낮은 쪽도 Lv.50", lb.b.mon.level == 50, lb.b.mon.level)
    chk("같은 종·같은 레벨이면 능력치도 같다",
        lb.a.team[0].base == lb.b.team[0].base,
        (lb.a.team[0].base, lb.b.team[0].base))

    print("=== 시작 ===")
    ev = lb.start()
    chk("시작 연출", ev and ev[0]["t"] == "intro", ev[:1])
    chk("둘 다 나온다", sum(1 for e in ev if e["t"] == "switch") == 2)
    chk("두 번 시작해도 한 번만", lb.start() == [])

    print("=== 한쪽만 골라서는 안 돈다 ===")
    turn = lb.turn
    lb.choose("a", "move", "TACKLE")
    chk("고른 것이 남는다", lb.a.choice == ("move", "TACKLE"), lb.a.choice)
    chk("아직 준비 안 됨", not lb.ready())
    chk("누가 안 골랐는지", lb.waiting() == ["b"], lb.waiting())
    chk("상대 화면에는 '골랐다' 만 보인다",
        lb.view("b")["foe"]["chosen"] is True
        and lb.view("b")["me"]["chosen"] is False)
    lb.choose("b", "move", "TACKLE")
    chk("둘 다 고르면 준비됨", lb.ready())
    ev = lb.resolve()
    chk("턴이 돈다", lb.turn == turn + 1, lb.turn)
    chk("고른 것은 비워진다", lb.a.choice is None and lb.b.choice is None)

    print("=== 시간을 넘기면 서버가 대신 ===")
    lb = build()
    lb.start()
    lb.choose("a", "move", "TACKLE")
    before = lb.b.auto
    lb.resolve()                      # b 는 안 골랐다
    chk("대신 골라 진행한다", lb.turn == 1, lb.turn)
    chk("대신 고른 횟수를 센다", lb.b.auto == before + 1, lb.b.auto)
    chk("a 는 제 손으로 골랐다", lb.a.auto == 0, lb.a.auto)

    print("=== 쓰러지면 그 쪽만 고른다 ===")
    lb = build()
    lb.start()
    lb.b.mon.hp = 0
    lb.b.mon.ab["fainted"] = True
    ev = []
    lb._settle(ev)
    chk("쓰러진 쪽이 교체 차례", lb.b.need_switch and not lb.a.need_switch)
    chk("판 전체가 교체 단계", lb.phase() == "switch", lb.phase())
    chk("쓰러진 쪽만 고를 수 있다",
        lb.can_act("b") and not lb.can_act("a"),
        (lb.can_act("a"), lb.can_act("b")))
    chk("상대 화면에도 '기다리는 중'", lb.view("a")["canAct"] is False)
    try:
        lb.choose("a", "move", "TACKLE")
        chk("상대는 아무것도 못 고른다", False)
    except ValueError as e:
        chk("상대는 아무것도 못 고른다", "차례가 아닙니다" in str(e), str(e))
    try:
        lb.choose("b", "move", "TACKLE")
        chk("교체 차례에 기술은 못 고른다", False)
    except ValueError as e:
        chk("교체 차례에 기술은 못 고른다", "다음 포켓몬" in str(e), str(e))
    lb.choose("b", "switch", 1)
    ev = lb.resolve()
    chk("다음 포켓몬이 나온다", lb.b.slot == 1, lb.b.slot)
    chk("나왔다고 알린다", any(e["t"] == "switch" and e["who"] == "foe" for e in ev))
    chk("교체는 턴을 안 먹는다", lb.turn == 0, lb.turn)
    chk("다시 둘 다 고르는 단계", lb.phase() == "choose" and lb.can_act("a"))

    print("=== 교체 차례에도 안 고르면 ===")
    lb = build()
    lb.start()
    lb.a.mon.hp = 0
    lb.a.mon.ab["fainted"] = True
    lb._settle([])
    lb.resolve()                      # a 가 안 골랐다
    chk("서버가 다음 포켓몬을 낸다", lb.a.slot == 1 and not lb.a.need_switch,
        (lb.a.slot, lb.a.need_switch))

    print("=== 교체 ===")
    lb = build()
    lb.start()
    lb.choose("a", "switch", 1)
    lb.choose("b", "move", "TACKLE")
    ev = lb.resolve()
    chk("바꾼다", lb.a.slot == 1, lb.a.slot)
    chk("불러들였다고 알린다", any(e["t"] == "recall" and e["who"] == "me" for e in ev))
    try:
        lb.choose("a", "switch", 1)
        chk("지금 나와 있는 자리로는 못 바꾼다", False)
    except ValueError:
        chk("지금 나와 있는 자리로는 못 바꾼다", True)
    lb.a.team[0].hp = 0
    try:
        lb.choose("a", "switch", 0)
        chk("쓰러진 자리로는 못 바꾼다", False)
    except ValueError:
        chk("쓰러진 자리로는 못 바꾼다", True)

    print("=== 못 고르는 기술 ===")
    lb = build(moves=("TACKLE",))
    lb.start()
    try:
        lb.choose("a", "move", "HYPERBEAM")
        chk("안 배운 기술은 거절", False)
    except ValueError as e:
        chk("안 배운 기술은 거절", "배우지" in str(e), str(e))
    lb.a.mon.pp["TACKLE"] = 0
    try:
        lb.choose("a", "move", "TACKLE")
        chk("PP 가 없으면 거절", False)
    except ValueError as e:
        chk("PP 가 없으면 거절", "PP" in str(e), str(e))

    print("=== 기권 ===")
    lb = build()
    lb.start()
    lb.choose("a", "forfeit")
    lb.choose("b", "move", "TACKLE")
    ev = lb.resolve()
    chk("건 사람이 진다", lb.over and lb.result == "b", (lb.over, lb.result))
    chk("까닭이 남는다", lb.reason == "forfeit", lb.reason)
    chk("a 기준 패배", lb.outcome("a") == "lose")
    chk("b 기준 승리", lb.outcome("b") == "win")
    chk("끝났다고 알린다", any(e["t"] == "over" for e in ev))

    print("=== 전멸 ===")
    lb = build()
    lb.start()
    for f in lb.b.team:
        f.hp = 0
    lb._settle([])
    chk("모두 쓰러지면 상대가 이긴다", lb.over and lb.result == "a", lb.result)
    chk("까닭은 ko", lb.reason == "ko", lb.reason)
    lb2 = build()
    lb2.start()
    for f in lb2.a.team + lb2.b.team:
        f.hp = 0
    lb2._settle([])
    chk("양쪽 다 쓰러지면 무승부", lb2.result == "draw", lb2.result)
    chk("무승부는 둘 다 draw",
        lb2.outcome("a") == "draw" and lb2.outcome("b") == "draw")

    print("=== 턴 상한 ===")
    lb = build(turns=3)
    lb.start()
    while not lb.over:
        both(lb)
        lb.resolve()
    chk("상한에서 멈춘다", lb.turn == 3, lb.turn)
    chk("머릿수로 판정", lb.reason == "turns", lb.reason)
    chk("결과가 셋 중 하나", lb.result in ("a", "b", "draw"), lb.result)

    print("=== 시점 ===")
    lb = build()
    lb.start()
    va, vb = lb.view("a"), lb.view("b")
    chk("a 의 me 는 가", va["me"]["name"] == "가" and va["foe"]["name"] == "나")
    chk("b 의 me 는 나", vb["me"]["name"] == "나" and vb["foe"]["name"] == "가")
    chk("내 기술만 나에게", len(va["me"]["moves"]) >= 1 and "moves" not in va["foe"])
    chk("상대 파티는 보이되 도구는 안 보인다",
        "held" not in va["foe"]["team"][0], va["foe"]["team"][0].keys())
    raw = [{"t": "hit", "who": "me", "target": "foe", "hp": 7}]
    chk("a 에게는 그대로", lb.events_for("a", raw)[0]["who"] == "me")
    got = lb.events_for("b", raw)[0]
    chk("b 에게는 뒤집혀서", got["who"] == "foe" and got["target"] == "me", got)
    chk("원본은 안 바뀐다", raw[0]["who"] == "me")

    print("=== 저장하고 되살리기 ===")
    lb = build(seed=11)
    lb.start()
    for _ in range(3):
        both(lb)
        lb.resolve()
    lb.choose("a", "move", "TACKLE")
    d = json.loads(json.dumps(lb.dump()))
    back = L.LiveBattle.load(DEX, copy.deepcopy(d))
    chk("턴", back.turn == lb.turn)
    chk("체력", [f.hp for f in back.a.team] == [f.hp for f in lb.a.team])
    chk("PP", [dict(f.pp) for f in back.b.team] == [dict(f.pp) for f in lb.b.team])
    chk("고른 것", back.a.choice == ("move", "TACKLE"), back.a.choice)
    chk("자리", (back.a.slot, back.b.slot) == (lb.a.slot, lb.b.slot))
    chk("이름", (back.a.name, back.b.name) == ("가", "나"))
    chk("다시 저장해도 같다", back.dump() == d)
    for x in (lb, back):
        x.a.choice = x.b.choice = None
        both(x)
        x.resolve()
    chk("이어서 돌려도 같은 결과",
        [f.hp for f in back.b.team] == [f.hp for f in lb.b.team],
        ([f.hp for f in back.b.team], [f.hp for f in lb.b.team]))

    print("=== 끝까지 ===")
    wins = {"a": 0, "b": 0, "draw": 0}
    for g in range(6):
        lb = build(seed=20 + g)
        lb.start()
        n = 0
        while not lb.over and n < 400:
            n += 1
            both(lb)
            lb.resolve()
        wins[lb.result] = wins.get(lb.result, 0) + 1
    chk("여섯 판이 다 끝난다", sum(wins.values()) == 6, wins)
    chk("같은 팀이면 어느 쪽도 늘 이기지는 않는다",
        wins["a"] < 6 and wins["b"] < 6, wins)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
