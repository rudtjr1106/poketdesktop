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


def turn_end_checks():
    """쓰러짐과 턴 끝. 마지막끼리는 턴 끝 화상 데미지로 이긴 쪽까지 쓰러지면 무승부 - **시즌 중에 판정을 바꾸지
    않는다** (형평성, 2026-10-20 사용자 결정, 바뀌면 알리려고 못 박는다). 상대에게 다음 포켓몬이 있으면 턴 끝은 온다."""
    print("\n== 쓰러짐과 턴 끝 (1.13.3)")
    a = [L.leveled(mon("MACHAMP", 100, ["CROSSCHOP"]), 70)]
    a[0]["ability"] = "NOGUARD"
    b = [L.leveled(mon("CATERPIE", 5, ["STRINGSHOT"]), 2)]
    lb = L.LiveBattle(DEX, (1, "가", a), (2, "나", b), rng=random.Random(5))
    lb.start()
    lb.a.mon.status, lb.a.mon.hp = "burn", 1
    lb.choose("a", "move", "CROSSCHOP")
    lb.choose("b", "move", "STRINGSHOT")
    lb.resolve()
    chk("마지막끼리는 예전 그대로: 화상 데미지로 같이 쓰러지면 무승부 (시즌 중 판정 유지)", lb.over and lb.result == "draw",
        (lb.over, lb.result))
    a = [L.leveled(mon("CONKELDURR", 100, ["MACHPUNCH"]), 70)]
    a[0]["ability"], a[0]["held"] = "GUTS", "FLAMEORB"
    b = [L.leveled(mon("CATERPIE", 5, ["STRINGSHOT"]), 2), L.leveled(mon("BLISSEY", 100, ["SOFTBOILED"]), 70)]
    lb = L.LiveBattle(DEX, (1, "가", a), (2, "나", b), rng=random.Random(5))
    lb.start()
    lb.choose("a", "move", "MACHPUNCH")
    lb.choose("b", "move", "STRINGSHOT")
    lb.resolve()
    chk("상대에게 다음 포켓몬이 있으면 쓰러뜨린 턴에도 턴 끝 (화염구슬)", lb.a.mon.status == "burn", lb.a.mon.status)


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

    print("=== 기권: 내 차례가 아니어도 된다 (제보, 1.9.2) ===")
    # 상대가 다음 포켓몬을 고르는 동안에는 '고를 차례가 아닙니다' 로 거절돼서,
    # 판이 안 끝나고 창이 껐다 켜도 다시 떴다.
    lb = build()
    lb.start()
    lb.b.mon.hp = 0
    lb.b.need_switch = True
    chk("상대가 다음 포켓몬을 고르는 중이다", lb.phase() == "switch" and not lb.can_act("a"),
        (lb.phase(), lb.can_act("a")))
    try:
        lb.choose("a", "forfeit")
        ok = True
    except ValueError as e:
        ok = str(e)
    chk("그때도 기권을 받는다", ok is True, ok)
    chk("상대를 안 기다리고 바로 끝난다", lb.ready())
    ev = lb.resolve()
    chk("건 사람이 진다 (교체 단계)", lb.over and lb.result == "b" and lb.reason == "forfeit",
        (lb.over, lb.result, lb.reason))
    try:
        lb.choose("a", "forfeit")
        chk("끝난 판에서는 거절", False)
    except ValueError as e:
        chk("끝난 판에서는 거절", "끝난" in str(e), str(e))
    lb = build()
    lb.start()
    lb.a.forfeited = True
    try:
        lb.choose("a", "forfeit")
        chk("이미 그만둔 사람은 다시 못 건다", False)
    except ValueError as e:
        chk("이미 그만둔 사람은 다시 못 건다", "끝난" in str(e), str(e))

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
    # 일 목록에도 안 실린다 (11/25): 내보낸 포켓몬(switch)에 지닌 도구 · 특성 · 번호가 통째로 실려 상대에게 갔다 -
    # 화면에는 안 그렸지만 응답을 들여다보면 보였다. 내 것은 그대로 온다.
    lb2 = build()
    lb2.a.team[0].held = "LEFTOVERS"
    lb2.b.team[0].held = "LIFEORB"
    ev2 = lb2.start()
    for viewer in ("a", "b"):
        got = [e for e in lb2.events_for(viewer, ev2) if e.get("t") == "switch"]
        foe_mon = next(e["mon"] for e in got if e["who"] == "foe")
        my_mon = next(e["mon"] for e in got if e["who"] == "me")
        chk("%s 가 받는 일 목록: 상대가 내보낸 포켓몬의 도구 · 특성 · 번호가 없다 (내 것은 있다)" % viewer,
            not any(k in foe_mon for k in ("held", "heldKr", "ability", "abilityKr", "id", "locked"))
            and my_mon.get("held") in ("LEFTOVERS", "LIFEORB") and "ability" in my_mon
            and foe_mon.get("name") and "hp" in foe_mon and "num" in foe_mon, sorted(foe_mon))
    chk("  저장해 둔 원본은 그대로다 (보여 줄 때만 뺀다)", "held" in ev2[1]["mon"] and "held" in ev2[2]["mon"])
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

    print("\n=== 테라스탈·Z기술을 내가 고른다 (2.5.0 · 시즌 4) ===")
    def gim(a_mon, b_mon, seed=9):
        lb = L.LiveBattle(DEX, (1, "가", [L.leveled(a_mon, 50)]), (2, "나", [L.leveled(b_mon, 50)]),
                          rng=random.Random(seed))
        return lb

    # 2.5.1: 테라피스도 지니는 도구라 Z크리스탈과 한 포켓몬이 같이 못 지닌다 - Z 는 za(불꽃Z), 테라는 ta(테라피스 풀)
    za = mon("CHARIZARD", 50, ("FLAMETHROWER", "AIRSLASH"))
    za["held"] = "FIRIUMZ"
    ta = mon("CHARIZARD", 50, ("FLAMETHROWER", "AIRSLASH"))
    ta["held"] = "GRASSTERASHARD"
    zb = mon("SNORLAX", 50, ("TACKLE",))
    lb = gim(za, zb)
    lb.start()
    g = lb.view("a")["gimmick"]
    chk("Z링·테라오브가 없으면 단추가 안 뜬다", g["canTera"] is None and g["zMoves"] == [] and not g["zUsed"], g)
    lb = gim(za, zb)
    lb.zring["me"] = lb.tera_orb["me"] = True          # a 쪽만 가졌다
    lb.start()
    g = lb.view("a")["gimmick"]
    chk("Z크리스탈을 지녔으면 Z기술 목록이 오고, 테라피스가 없으니 테라 단추는 없다",
        g["canTera"] is None
        and [(z["key"], z["name"], z["power"]) for z in g["zMoves"]] == [("FLAMETHROWER", "다이내믹풀플레임", 175)],
        g)
    gb = lb.view("b")["gimmick"]
    chk("안 가진 상대 쪽 화면에는 안 뜬다", gb["canTera"] is None and gb["zMoves"] == [], gb)
    lb.choose("a", "move", "FLAMETHROWER", z=True)
    lb.choose("b", "move", "TACKLE")
    ev = lb.resolve()
    chk("고른 대로 Z기술이 나간다", "zpower" in [e.get("t") for e in ev], [e.get("t") for e in ev])
    lb = gim(ta, zb)
    lb.zring["me"] = lb.tera_orb["me"] = True
    lb.start()
    g = lb.view("a")["gimmick"]
    chk("테라피스를 지녔으면 그 타입으로 테라 단추 (Z크리스탈이 없으니 Z기술은 없다)",
        g["canTera"] == "GRASS" and g["teraKr"] == "풀" and g["zMoves"] == [], g)
    lb.choose("a", "move", "FLAMETHROWER", tera=True)
    lb.choose("b", "move", "TACKLE")
    ev = lb.resolve()
    kinds_ = [e.get("t") for e in ev]
    chk("고른 대로 테라스탈하고 기술이 나간다", "tera" in kinds_ and kinds_.index("tera") < kinds_.index("move"), kinds_)
    va = lb.view("a")
    chk("내 포켓몬에 테라 타입이 실린다", va["me"]["team"][0]["tera"] == "GRASS"
        and va["me"]["team"][0]["typeIds"] == ["GRASS"], va["me"]["team"][0]["typeIds"])
    chk("상대 화면에도 드러난다", lb.view("b")["foe"]["team"][0]["tera"] == "GRASS")
    g = va["gimmick"]
    chk("쓴 뒤에는 다시 못 누른다", g["canTera"] is None and g["teraUsed"] and g["teraOn"], g)
    lb2 = L.LiveBattle.load(DEX, json.loads(json.dumps(lb.dump())))
    g2 = lb2.view("a")["gimmick"]
    chk("저장했다 불러와도 그대로다", g2 == g and lb2.a.team[0].tera == "GRASS", g2)
    # 요청을 받아 두는 것은 될 때만
    lb = gim(za, zb)
    lb.zring["me"] = lb.tera_orb["me"] = True
    lb.start()
    lb.choose("a", "move", "AIRSLASH", z=True)
    chk("타입이 안 맞는 기술에는 Z 요청을 안 받는다", lb.a.z_req is False)
    lb.choose("a", "move", "FLAMETHROWER", z=True, tera=True)
    chk("맞는 기술이면 Z 요청을 받고, 테라피스가 없으면 테라 요청은 안 받는다", lb.a.z_req is True and lb.a.tera_req is False)
    lb = gim(ta, zb)
    lb.zring["me"] = lb.tera_orb["me"] = True
    lb.start()
    lb.choose("a", "move", "FLAMETHROWER", tera=True)
    chk("테라피스를 지녔으면 테라 요청을 받는다", lb.a.tera_req is True)
    lb2 = L.LiveBattle.load(DEX, json.loads(json.dumps(lb.dump())))
    chk("골라 둔 요청도 저장된다", lb2.a.tera_req is True)
    lb = gim(ta, zb)
    lb.tera_orb["me"] = True
    lb.start()
    lb.choose("b", "move", "TACKLE")
    lb.choose("a", "move", "FLAMETHROWER", tera=True)
    lb.choose("a", "move", "AIRSLASH")
    chk("다시 고르면서 끄면 테라스탈 요청도 꺼진다", lb.a.tera_req is False)
    old = json.loads(json.dumps(lb.dump()))
    old.pop("gimmick", None)
    for s in ("a", "b"):
        old[s].pop("teraReq", None)
    lb3 = L.LiveBattle.load(DEX, old)
    chk("2.5.0 전에 저장한 판(칸 없음)은 테라스탈 없이 불러온다",
        lb3.view("a")["gimmick"]["canTera"] is None and lb3.a.tera_req is False)

    # 상대가 먼저 유턴으로 물러나 턴이 멈췄다 이어져도 (서버는 그사이 저장했다 불러온다) Z기술이 나간다
    ja = mon("JOLTEON", 50, ("UTURN",))
    ja2 = mon("SNORLAX", 50, ("TACKLE",))
    zc = mon("CHARIZARD", 50, ("FLAMETHROWER",))
    zc["held"] = "FIRIUMZ"
    lb = L.LiveBattle(DEX, (1, "가", [L.leveled(ja, 50), L.leveled(ja2, 50)]), (2, "나", [L.leveled(zc, 50)]),
                      rng=random.Random(3))
    lb.zring["foe"] = True                         # 자리 b 가 Z링을 가졌다
    lb.start()
    lb.choose("a", "move", "UTURN")
    lb.choose("b", "move", "FLAMETHROWER", z=True)
    ev = lb.resolve()
    chk("(쥬피썬더가 먼저 유턴을 쓰고 턴이 멈춘다)", lb.phase() == "switch" and lb.mid is not None
        and not any(e.get("t") == "zpower" for e in ev), (lb.phase(), [e.get("t") for e in ev]))
    lb = L.LiveBattle.load(DEX, json.loads(json.dumps(lb.dump())))
    lb.choose("a", "switch", 1)
    ev = lb.resolve()
    kinds_ = [e.get("t") for e in ev]
    chk("멈췄다 이어진 턴에도 고른 Z기술이 나간다", "zpower" in kinds_ and "foe" in lb.z_done, kinds_)

    turn_end_checks()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
