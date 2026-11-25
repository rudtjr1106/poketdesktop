# -*- coding: utf-8 -*-
"""실시간 더블배틀 엔진 검사 (독도, 2026-11-25).

    python common/test_double_battle.py

서버도 DB 도 없이 common/double_battle.py 만 본다. 못 박는 것 (본가 더블 규칙):

  · 편마다 두 마리. 나와 있는 포켓몬마다 기술(+ 대상)이나 교체를 고르고, **양쪽이 다 골라야** 턴이 돈다.
  · '고른 하나' 기술은 고른 자리만 맞는다. 상대 전부 · 나 빼고 전부 기술은 **기술 한 번**으로 여럿을 때리고
    둘 이상이면 0.75배다 - PP · 기술 이름 · 생명의구슬 반동은 한 번뿐.
  · 방어는 그 포켓몬만, 와이드가드는 편 전체의 광역기를 막는다.
  · 날따름 · 피뢰침이 '고른 하나' 기술을 끌어온다. 도우미는 1.5배. 위협은 상대 둘 다.
  · 쓰러진 대상을 겨눈 기술은 남은 상대로 간다. 턴이 끝나면 빈 자리를 가진 쪽만 다음을 고른다.
  · 유턴은 쓰자마자 멈춰서 고른다. 날려버리기는 그 자리를 바꾼다. 씨뿌리기는 심은 자리로 회복이 간다.
  · 메가진화는 편마다 한 번. 저장했다 되살려도 판이 이어진다. b 에게는 자리가 뒤집혀 보인다.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import battle as B                        # noqa: E402
from common import double_battle as D                 # noqa: E402
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


def mon(species, moves=("TACKLE",), ability=None, held=None, level=50, evs=None, nature="HARDY"):
    m = P.make_pokemon(DEX.get(species), 100, random.Random(1), shiny_rate=10 ** 9)
    m["ivs"] = dict((s, 31) for s in P.STATS)
    m["evs"] = dict((s, 0) for s in P.STATS)
    m["evs"].update(evs or {})
    m["nature"] = nature
    m["held"] = held
    m["moves"] = list(moves)
    if ability:
        m["ability"] = ability
    return L.leveled(m, level)


def build(a, b, seed=5, turns=150):
    return D.DoubleBattle(DEX, (1, "가", a), (2, "나", b), rng=random.Random(seed), max_turns=turns)


def mv(pos, move, target=None, **kw):
    return dict({"pos": pos, "kind": "move", "move": move, "target": target}, **kw)


def sw(pos, slot):
    return {"pos": pos, "kind": "switch", "slot": slot}


def go(db, a=None, b=None):
    """양쪽이 고르고 한 턴(또는 교체 한 번)을 돈다. 안 준 쪽은 서버가 대신 고르는 것(auto_choice)으로."""
    for who, picks in (("a", a), ("b", b)):
        if not db.can_act(who):
            continue
        db.choose(who, "picks", picks if picks is not None else db.auto_choice(who)[1])
    return db.resolve()


def f(db, at):
    """자리 이름("a0")의 포켓몬."""
    return db.mon(at[0], int(at[1]))


def hits(ev, at=None, to=None):
    return [e for e in ev if e.get("t") == "hit" and (at is None or e.get("at") == at)
            and (to is None or e.get("to") == to)]


def bulky(species="SNORLAX", **kw):
    return mon(species, evs={"hp": 252, "def": 252, "spd": 252}, **kw)


def basics():
    print("== 시작 · 고르기")
    db = build([bulky(), bulky("BLISSEY"), bulky("MILTANK")], [bulky(), bulky("BLISSEY"), bulky("MILTANK")])
    ev = db.start()
    chk("양쪽이 두 마리씩 낸다", sorted(e["at"] for e in ev if e["t"] == "switch") == ["a0", "a1", "b0", "b1"],
        [(e["t"], e.get("at")) for e in ev])
    va = db.view("a")
    chk("보기: 형식 · 나와 있는 둘 · 고를 차례", va["fmt"] == "double" and va["me"]["active"] == [0, 1]
        and va["foe"]["active"] == [0, 1] and va["phase"] == "choose" and va["canAct"]
        and [a["pos"] for a in va["me"]["acts"]] == [0, 1], va["me"].get("active"))
    m0 = va["me"]["acts"][0]["moves"][0]
    chk("기술마다 겨눌 수 있는 자리가 온다", m0["key"] == "TACKLE" and m0["aim"] == "one"
        and m0["targets"] == ["foe0", "foe1", "ally"], m0)
    chk("상대의 기술 · 도구는 안 보인다", "acts" not in va["foe"] and "held" not in va["foe"]["team"][0])
    db.choose("a", "picks", [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe1")])
    chk("한쪽만 골라서는 턴이 안 돈다", not db.ready() and db.waiting() == ["b"] and db.turn == 0)
    db.choose("b", "picks", [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")])
    chk("둘 다 고르면 돈다", db.ready())
    ev = db.resolve()
    chk("한 턴에 네 번 움직인다", db.turn == 1 and len([e for e in ev if e["t"] == "move"]) == 4,
        [(e["t"], e.get("at")) for e in ev])
    chk("고른 자리만 맞는다 (a0 -> b0, a1 -> b1, b0 · b1 -> a0)",
        len(hits(ev, "a0", "b0")) == 1 and len(hits(ev, "a1", "b1")) == 1 and len(hits(ev, "b0", "a0")) == 1
        and len(hits(ev, "b1", "a0")) == 1 and f(db, "a1").hp == f(db, "a1").maxhp,
        [(e.get("at"), e.get("to")) for e in ev if e["t"] == "hit"])
    evb = db.events_for("b", ev)
    chk("b 에게는 자리가 뒤집혀 보인다", any(e.get("t") == "hit" and e.get("at") == "foe0" and e.get("to") == "me0"
                                  and e.get("who") == "foe" for e in evb)
        and db.events_for("a", ev)[0].get("at", "me0").startswith(("me", "foe")),
        [(e.get("who"), e.get("at"), e.get("to")) for e in evb if e["t"] == "hit"])

    print("\n== 거절하는 것")
    def bad(who, picks):
        try:
            db.choose(who, "picks", picks)
        except ValueError as e:
            return str(e)
        return None
    chk("자리 하나만 고르면 안 된다", bad("a", [mv(0, "TACKLE", "foe0")]) is not None)
    chk("없는 대상", bad("a", [mv(0, "TACKLE", "foe7"), mv(1, "TACKLE", "foe0")]) is not None)
    chk("안 배운 기술", bad("a", [mv(0, "SURF", "foe0"), mv(1, "TACKLE", "foe0")]) is not None)
    chk("둘이 같은 포켓몬으로 바꿀 수 없다", bad("a", [sw(0, 2), sw(1, 2)]) is not None)
    chk("나와 있는 포켓몬으로는 못 바꾼다", bad("a", [sw(0, 1), mv(1, "TACKLE", "foe0")]) is not None)
    chk("거절해도 고른 것이 남지 않는다", db.side("a").picks is None)
    ev = go(db, [sw(0, 2), mv(1, "TACKLE", "foe0")], None)
    chk("교체: 그 자리에 새 포켓몬이 선다", db.side("a").active == [2, 1] and f(db, "a0").mon["species"] == "MILTANK"
        and any(e["t"] == "switch" and e.get("at") == "a0" for e in ev), db.side("a").active)
    chk("교체는 기술보다 먼저", [e["t"] for e in ev if e["t"] in ("switch", "move")][0] == "switch")


def spread():
    print("\n== 광역기 (상대 전부 · 나 빼고 전부)")
    def one(seed, n_foes):
        a = [bulky("GOLEM", moves=["SWIFT"], held="LIFEORB"), bulky()]
        b = [bulky(), bulky("BLISSEY")][:n_foes] if n_foes == 2 else [bulky()]
        db = build(a, b, seed=seed)
        db.start()
        ev = go(db, [mv(0, "SWIFT"), mv(1, "TACKLE", "foe0")], None)
        return db, ev
    db, ev = one(3, 2)
    g = f(db, "a0")
    chk("기술 이름은 한 번, 둘 다 맞는다", len([e for e in ev if e["t"] == "move" and e.get("at") == "a0"]) == 1
        and len(hits(ev, "a0", "b0")) == 1 and len(hits(ev, "a0", "b1")) == 1,
        [(e["t"], e.get("at"), e.get("to")) for e in ev if e.get("at") == "a0"])
    chk("PP 는 한 번만 든다", g.pp["SWIFT"] == (DEX.move("SWIFT")["pp"] - 1), g.pp)
    orb = [e for e in ev if e.get("at") == "a0" and "생명의구슬" in (e.get("text") or "")]
    chk("생명의구슬 반동도 한 번", len(orb) == 1, len(orb))
    def plain(n_foes):                    # 급소는 뺀다 (1.5배가 섞이면 평균이 흔들린다)
        got = [hits(one(s, n_foes)[1], "a0", "b0")[0] for s in range(60)]
        return [h["damage"] for h in got if not h["crit"]]
    two, solo = plain(2), plain(1)
    ratio = (sum(two) / float(len(two))) / (sum(solo) / float(len(solo)))
    chk("둘을 때리면 0.75배 (혼자 남은 상대에게는 그대로)", 0.70 <= ratio <= 0.80, round(ratio, 3))

    a = [bulky("GOLEM", moves=["EARTHQUAKE"]), bulky()]
    db = build(a, [bulky(), bulky("BLISSEY")])
    db.start()
    ev = go(db, [mv(0, "EARTHQUAKE"), mv(1, "TACKLE", "foe0")], None)
    chk("지진은 아군도 맞는다", sorted(e["to"] for e in hits(ev, "a0")) == ["a1", "b0", "b1"],
        [e["to"] for e in hits(ev, "a0")])
    a = [bulky("GOLEM", moves=["EARTHQUAKE"]), bulky("PIDGEOT")]
    db = build(a, [bulky(), bulky("BLISSEY")])
    db.start()
    ev = go(db, [mv(0, "EARTHQUAKE"), mv(1, "TACKLE", "foe0")], None)
    chk("비행 아군은 지진을 안 맞는다 (대상마다 따로 판정)", sorted(e["to"] for e in hits(ev, "a0")) == ["b0", "b1"],
        [e["to"] for e in hits(ev, "a0")])
    a = [bulky("GOLEM", moves=["EARTHQUAKE"]), bulky(ability="TELEPATHY")]
    db = build(a, [bulky(), bulky("BLISSEY")])
    db.start()
    ev = go(db, [mv(0, "EARTHQUAKE"), mv(1, "TACKLE", "foe0")], None)
    chk("텔레파시 아군도 안 맞는다", sorted(e["to"] for e in hits(ev, "a0")) == ["b0", "b1"],
        [e["to"] for e in hits(ev, "a0")])

    print("\n== 방어 · 와이드가드")
    a = [bulky("GOLEM", moves=["SWIFT"]), bulky()]
    db = build(a, [bulky(moves=["PROTECT"]), bulky("BLISSEY")])
    db.start()
    ev = go(db, [mv(0, "SWIFT"), mv(1, "TACKLE", "foe0")], [mv(0, "PROTECT"), mv(1, "TACKLE", "foe0")])
    chk("방어한 포켓몬만 안 맞는다", [e["to"] for e in hits(ev, "a0")] == ["b1"] and not hits(ev, "a1", "b0"),
        [(e.get("at"), e.get("to")) for e in ev if e["t"] == "hit"])
    db = build([bulky("GOLEM", moves=["SWIFT"]), bulky()], [bulky(moves=["WIDEGUARD"]), bulky("BLISSEY")])
    db.start()
    ev = go(db, [mv(0, "SWIFT"), mv(1, "TACKLE", "foe1")], [mv(0, "WIDEGUARD"), mv(1, "TACKLE", "foe0")])
    chk("와이드가드는 둘 다 지키고, '고른 하나' 기술은 못 막는다", not hits(ev, "a0") and len(hits(ev, "a1", "b1")) == 1,
        [(e.get("at"), e.get("to")) for e in ev if e["t"] == "hit"])


def redirect():
    print("\n== 끌어오기 · 도우미")
    db = build([bulky(), bulky()], [bulky(), bulky("CLEFABLE", moves=["FOLLOWME", "TACKLE"], ability="MAGICGUARD")])   # 헤롱헤롱바디면 검사가 흔들린다
    db.start()
    ev = go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "FOLLOWME")])
    chk("날따름: b0 을 겨눈 기술이 b1 로 간다", not hits(ev, "a0", "b0") and len(hits(ev, to="b1")) == 2
        and not any("실패" in (e.get("text") or "") for e in ev if e.get("at") == "b1"),
        [(e.get("at"), e.get("to")) for e in ev if e["t"] == "hit"])
    ev = go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")])
    chk("  그 턴뿐이다", len(hits(ev, to="b0")) == 2)

    db = build([bulky("JOLTEON", moves=["THUNDERBOLT"]), bulky()],
               [bulky("GYARADOS"), bulky("RHYDON", ability="LIGHTNINGROD")])
    db.start()
    ev = go(db, [mv(0, "THUNDERBOLT", "foe0"), mv(1, "TACKLE", "foe0")], None)
    chk("피뢰침: 전기 기술을 끌어와 받는다", not hits(ev, "a0", "b0") and f(db, "b0").hp == f(db, "b0").maxhp - sum(
        e["damage"] for e in hits(ev, to="b0")) and f(db, "b1").stages.get("spa", 0) >= 0
        and any(e.get("t") == "ability" and e.get("at") == "b1" for e in ev),
        [(e["t"], e.get("at"), e.get("to")) for e in ev if e.get("at") in ("a0", "b1")])

    def dmg(seed, helped):
        db = build([bulky("GOLEM", moves=["TACKLE"]), bulky("CLEFABLE", moves=["HELPINGHAND", "SPLASH"])],
                   [bulky(), bulky("BLISSEY")], seed=seed)
        db.start()
        ev = go(db, [mv(0, "TACKLE", "foe0"), mv(1, "HELPINGHAND" if helped else "SPLASH")], None)
        return ev, hits(ev, "a0", "b0")[0]["damage"]
    ev, _d = dmg(1, True)
    chk("도우미는 실패하지 않는다", not any("실패" in (e.get("text") or "") for e in ev if e.get("at") == "a1")
        and [e.get("at") for e in ev if e["t"] == "move"][0] == "a1", [(e["t"], e.get("at"), e.get("text")) for e in ev][:6])
    with_h = sum(dmg(s, True)[1] for s in range(40)) / 40.0
    without = sum(dmg(s, False)[1] for s in range(40)) / 40.0
    chk("도우미: 아군의 기술이 1.5배", 1.42 <= with_h / without <= 1.58, round(with_h / without, 3))

    print("\n== 등장 특성")
    db = build([bulky("GYARADOS", ability="INTIMIDATE"), bulky()], [bulky(), bulky("BLISSEY")])
    ev = db.start()
    chk("위협은 상대 둘 다 내린다", f(db, "b0").stages.get("atk") == -1 and f(db, "b1").stages.get("atk") == -1
        and f(db, "a1").stages.get("atk", 0) == 0,
        (f(db, "b0").stages, f(db, "b1").stages))
    chk("  특성 알림은 한 번", len([e for e in ev if e.get("t") == "ability" and e.get("at") == "a0"]) == 1,
        [(e.get("t"), e.get("at")) for e in ev if e.get("t") == "ability"])


def order_and_faint():
    print("\n== 속이기 · 쓰러짐 · 다음 포켓몬")
    db = build([mon("PERSIAN", ["FAKEOUT", "TACKLE"], evs={"spe": 252}), bulky()], [bulky(), bulky("BLISSEY")])
    db.start()
    ev = go(db, [mv(0, "FAKEOUT", "foe1"), mv(1, "TACKLE", "foe0")], None)
    chk("속이기: 맞은 포켓몬은 그 턴에 못 움직인다", len(hits(ev, "a0", "b1")) == 1
        and not any(e["t"] == "move" and e.get("at") == "b1" for e in ev)
        and any(e["t"] == "move" and e.get("at") == "b0" for e in ev), [(e["t"], e.get("at")) for e in ev])
    ev = go(db, [mv(0, "FAKEOUT", "foe1"), mv(1, "TACKLE", "foe0")], None)
    chk("  둘째 턴에는 실패한다", not hits(ev, "a0", "b1"))

    weak = mon("PIDGEY", ["TACKLE"], level=5)
    db = build([mon("GOLEM", ["ROCKSLIDE", "TACKLE"], evs={"atk": 252, "spe": 252}, level=100),
                mon("SNORLAX", ["TACKLE"], evs={"atk": 252}, level=100)],
               [dict(weak), bulky("BLISSEY"), bulky("MILTANK")])
    db.start()
    ev = go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")])
    chk("쓰러진 상대를 겨눈 기술은 남은 상대로 간다", not f(db, "b0") or not f(db, "b0").alive()
        if False else (len(hits(ev, "a0", "b0")) == 1 and len(hits(ev, "a1", "b1")) == 1),
        [(e.get("at"), e.get("to")) for e in ev if e["t"] == "hit"])
    chk("쓰러진 포켓몬의 차례는 사라진다", not any(e["t"] == "move" and e.get("at") == "b0" for e in ev))
    chk("빈 자리를 가진 쪽만 다음을 고른다", db.phase() == "switch" and db.can_act("b") and not db.can_act("a")
        and db.side("b").need == [0] and db.view("b")["me"]["need"] == [0] and db.view("a")["foe"]["need"] == [0],
        (db.phase(), db.side("b").need))
    try:
        db.choose("b", "picks", [mv(0, "TACKLE", "foe0")])
        wrong = False
    except ValueError:
        wrong = True
    chk("  그때는 교체만 받는다", wrong)
    turn = db.turn
    ev = go(db, None, [sw(0, 2)])
    chk("  고르면 그 자리에 선다 (턴은 안 는다)", db.side("b").active == [2, 1] and db.turn == turn and db.phase() == "choose"
        and any(e["t"] == "switch" and e.get("at") == "b0" for e in ev), db.side("b").active)

    print("\n== 남은 포켓몬이 모자랄 때 · 승패")
    db = build([mon("GOLEM", ["ROCKSLIDE", "TACKLE"], evs={"atk": 252, "spe": 252}, level=100),
                mon("SNORLAX", ["TACKLE"], evs={"atk": 252}, level=100)], [dict(weak), bulky("BLISSEY")])
    db.start()
    ev = go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe1")], None)
    chk("낼 포켓몬이 없으면 한 마리로 싸운다", db.phase() == "choose" and db.side("b").active[0] is None
        and db.side("b").active[1] == 1 and not db.over and len(db.view("b")["me"]["acts"]) == 2
        and db.view("b")["me"]["acts"][0] is None, (db.phase(), db.side("b").active))
    ev = go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe1")], [mv(1, "TACKLE", "foe0")])
    chk("  빈 자리를 겨눈 기술은 남은 상대로", len(hits(ev, "a0", "b1")) == 1, [(e.get("at"), e.get("to")) for e in ev if e["t"] == "hit"])
    for _ in range(60):
        if db.over:
            break
        go(db)
    chk("다 쓰러뜨리면 끝난다", db.over and db.result == "a" and db.reason == "ko" and db.outcome("b") == "lose",
        (db.over, db.result))

    db = build([bulky(), bulky()], [bulky(), bulky()])
    db.start()
    db.choose("b", "forfeit")
    ev = db.resolve()
    chk("기권은 상대를 안 기다리고 끝난다", db.over and db.result == "a" and db.reason == "forfeit")
    db = build([bulky(), bulky()], [bulky(), bulky()])
    db.start()
    ev = db.resolve()
    chk("안 고르면 서버가 대신 고른다", db.turn == 1 and db.side("a").auto == 1 and db.side("b").auto == 1
        and len([e for e in ev if e["t"] == "move"]) == 4)


def switching():
    print("\n== 유턴 · 날려버리기 · 사이드체인지")
    db = build([mon("SCIZOR", ["UTURN"], evs={"spe": 252}, nature="JOLLY"), bulky(), bulky("MILTANK")],
               [bulky(), bulky("BLISSEY")])
    db.start()
    ev = go(db, [mv(0, "UTURN", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")])
    chk("유턴: 쓰자마자 멈춰서 그 자리를 고른다", db.phase() == "switch" and db.side("a").need == [0] and db.can_act("a")
        and not db.can_act("b") and not any(e["t"] == "move" and e.get("at", "").startswith("b") for e in ev),
        (db.phase(), db.side("a").need, [(e["t"], e.get("at")) for e in ev]))
    ev = go(db, [sw(0, 2)], None)
    chk("  고르면 남은 차례가 이어지고, 나온 포켓몬이 대신 맞는다", db.side("a").active == [2, 1] and db.phase() == "choose"
        and len(hits(ev, to="a0")) == 2 and f(db, "a0").mon["species"] == "MILTANK" and db.turn == 1,
        [(e["t"], e.get("at"), e.get("to")) for e in ev])

    db = build([bulky(moves=["ROAR"]), bulky()], [bulky(), bulky("BLISSEY"), bulky("MILTANK")])
    db.start()
    ev = go(db, [mv(0, "ROAR", "foe1"), mv(1, "TACKLE", "foe0")], None)
    chk("울부짖기: 겨눈 자리의 포켓몬이 바뀐다", db.side("b").active == [0, 2], db.side("b").active)

    db = build([bulky("ALAKAZAM", moves=["ALLYSWITCH"]), bulky()], [bulky(), bulky("BLISSEY")])
    db.start()
    ev = go(db, [mv(0, "ALLYSWITCH"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")])
    chk("사이드체인지: 두 포켓몬의 자리가 바뀌고, 그 자리를 겨눈 기술이 바뀐 포켓몬에게 간다",
        db.side("a").active == [1, 0] and len(hits(ev, to="a0")) == 2 and f(db, "a0").mon["species"] == "SNORLAX"
        and f(db, "a0").hp < f(db, "a0").maxhp and any(e["t"] == "swap" for e in ev),
        (db.side("a").active, [(e["t"], e.get("at"), e.get("to")) for e in ev]))

    print("\n== 씨뿌리기 · 카운터")
    db = build([bulky(), bulky("VENUSAUR", moves=["LEECHSEED"])], [bulky(), bulky("BLISSEY")])
    db.start()
    f(db, "a0").hp = f(db, "a0").maxhp // 2
    f(db, "a1").hp = f(db, "a1").maxhp // 2
    h0, h1 = f(db, "a0").hp, f(db, "a1").hp
    ev = go(db, [mv(0, "SPLASH") if "SPLASH" in f(db, "a0").pp else mv(0, "TACKLE", "foe1"), mv(1, "LEECHSEED", "foe0")],
            [mv(0, "TACKLE", "foe1"), mv(1, "TACKLE", "foe1")])
    heal = [e for e in ev if e["t"] == "heal" and "흡수" in (e.get("text") or "")]
    chk("씨뿌리기: 심은 포켓몬(a1)이 회복한다", len(heal) == 1 and heal[0].get("at") == "a1" and f(db, "a0").hp <= h0,
        [(e["t"], e.get("at"), e.get("text")) for e in ev if e["t"] in ("heal", "chip")])

    db = build([bulky("WOBBUFFET", moves=["COUNTER"]), bulky()], [bulky(), mon("MACHAMP", ["TACKLE"], evs={"atk": 252})])
    db.start()
    ev = go(db, [mv(0, "COUNTER"), mv(1, "TACKLE", "foe0")], [mv(0, "SPLASH") if False else mv(0, "TACKLE", "foe1"),
                                                             mv(1, "TACKLE", "foe0")])
    chk("카운터는 나를 때린 포켓몬에게 돌아간다", len(hits(ev, "a0", "b1")) == 1 and not hits(ev, "a0", "b0"),
        [(e.get("at"), e.get("to")) for e in ev if e["t"] == "hit"])


def more():
    print("\n== 아군 기술 · 순서")
    db = build([bulky(), bulky()], [bulky(), bulky("AMOONGUSS", moves=["RAGEPOWDER", "TACKLE"])])
    db.start()
    grass = build([bulky("VENUSAUR"), bulky()], [bulky(), bulky("AMOONGUSS", moves=["RAGEPOWDER", "TACKLE"])])
    grass.start()
    ev = go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "RAGEPOWDER")])
    ev2 = go(grass, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "RAGEPOWDER")])
    chk("분노가루도 끌어온다 - 풀 타입은 안 끌린다", len(hits(ev, to="b1")) == 2 and len(hits(ev2, "a0", "b0")) == 1
        and len(hits(ev2, "a1", "b1")) == 1, [(e.get("at"), e.get("to")) for e in ev2 if e["t"] == "hit"])

    db = build([bulky(ability="STALWART"), bulky()], [bulky(), bulky("CLEFABLE", moves=["FOLLOWME"], ability="MAGICGUARD")])
    db.start()
    ev = go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "FOLLOWME")])
    chk("꿋꿋함은 날따름을 무시한다", len(hits(ev, "a0", "b0")) == 1 and len(hits(ev, "a1", "b1")) == 1,
        [(e.get("at"), e.get("to")) for e in ev if e["t"] == "hit"])

    db = build([bulky(moves=["SPOTLIGHT"]), bulky()], [bulky(), bulky()])
    db.start()
    ev = go(db, [mv(0, "SPOTLIGHT", "ally"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")])
    chk("스포트라이트: 비춘 포켓몬(a1)으로 상대의 기술이 간다", len(hits(ev, to="a1")) == 2 and not hits(ev, to="a0"),
        [(e.get("at"), e.get("to")) for e in ev if e["t"] == "hit"])

    slow = mon("SHUCKLE", ["TACKLE"], evs={"hp": 252})
    db = build([mon("ALAKAZAM", ["AFTERYOU"], evs={"spe": 252}), dict(slow)],
               [bulky("PERSIAN"), bulky("JOLTEON")])
    db.start()
    ev = go(db, [mv(0, "AFTERYOU", "ally"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")])
    order = [e.get("at") for e in ev if e["t"] == "move"]
    chk("당신먼저: 느린 아군이 바로 다음에 움직인다", order[:2] == ["a0", "a1"], order)
    db = build([mon("JOLTEON", ["QUASH"], evs={"spe": 252}), dict(slow)],
               [mon("ALAKAZAM", ["TACKLE"]), mon("PERSIAN", ["TACKLE"])])
    db.start()
    ev = go(db, [mv(0, "QUASH", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")])
    order = [e.get("at") for e in ev if e["t"] == "move"]
    chk("순서미루기: 그 상대가 맨 나중에 움직인다", order[-1] == "b0" and len(order) == 4, order)

    db = build([bulky(moves=["COACHING"]), bulky()], [bulky(), bulky()])
    db.start()
    ev = go(db, [mv(0, "COACHING"), mv(1, "TACKLE", "foe0")], None)
    chk("코칭: 아군의 공격 · 방어가 오른다 (나는 그대로)", f(db, "a1").stages.get("atk") == 1 and f(db, "a1").stages.get("def") == 1
        and not f(db, "a0").stages.get("atk") and any(e["t"] == "stat" and e.get("at") == "a1" for e in ev),
        (f(db, "a1").stages, [(e["t"], e.get("at")) for e in ev][:6]))
    db = build([bulky(moves=["HOWL"]), bulky()], [bulky(), bulky()])
    db.start()
    go(db, [mv(0, "HOWL"), mv(1, "TACKLE", "foe0")], None)
    chk("하울링: 나와 아군의 공격이 오른다", f(db, "a0").stages.get("atk") == 1 and f(db, "a1").stages.get("atk") == 1
        and not f(db, "b0").stages.get("atk"), (f(db, "a0").stages, f(db, "a1").stages))

    db = build([bulky(moves=["INSTRUCT"]), mon("PERSIAN", ["TACKLE"], evs={"spe": 252})], [bulky(), bulky("BLISSEY")])
    db.start()
    ev = go(db, [mv(0, "INSTRUCT", "ally"), mv(1, "TACKLE", "foe1")], None)
    chk("지휘: 아군이 고른 대상에게 한 번 더 쓴다 (PP 도 든다)", len(hits(ev, "a1", "b1")) == 2
        and f(db, "a1").pp["TACKLE"] == DEX.move("TACKLE")["pp"] - 2 and not hits(ev, "a1", "a0"),
        [(e["t"], e.get("at"), e.get("to")) for e in ev if e["t"] in ("hit", "move")])

    def taken(guard):
        vals = []
        for s in range(50):
            db = build([bulky("GOLEM", moves=["TACKLE"]), bulky()],
                       [bulky(), bulky("CLEFABLE", ability="FRIENDGUARD" if guard else "MAGICGUARD")], seed=s)
            db.start()
            h = hits(go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe1")], None), "a0", "b0")[0]
            if not h["crit"]:
                vals.append(h["damage"])
        return sum(vals) / float(len(vals))
    ratio = taken(True) / taken(False)
    chk("프렌드가드: 아군이 받는 데미지 0.75배", 0.70 <= ratio <= 0.80, round(ratio, 3))

    db = build([mon("SHUCKLE", ["TACKLE"]), mon("PERSIAN", ["TRICKROOM", "TACKLE"], evs={"spe": 252})],
               [mon("JOLTEON", ["TACKLE"], evs={"spe": 252}), mon("SNORLAX", ["TACKLE"])])
    db.start()
    go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TRICKROOM")], None)
    ev = go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")])
    order = [e.get("at") for e in ev if e["t"] == "move"]
    chk("트릭룸: 느린 순서로 움직인다", order == ["a0", "b1", "a1", "b0"], order)

    db = build([mon("PERSIAN", ["SUCKERPUNCH"], evs={"spe": 252}), bulky()],
               [bulky(moves=["TACKLE"]), bulky("BLISSEY", moves=["SPLASH"])])
    db.start()
    ev = go(db, [mv(0, "SUCKERPUNCH", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "SPLASH")])
    hit0 = len(hits(ev, "a0", "b0"))
    ev = go(db, [mv(0, "SUCKERPUNCH", "foe1"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "SPLASH")])
    chk("기습: 공격하려는 상대에게는 맞고, 변화기를 고른 상대에게는 실패한다 (자리마다 따로 본다)",
        hit0 == 1 and not hits(ev, "a0", "b1"), (hit0, len(hits(ev, "a0", "b1"))))

    print("\n== 판 전체 · 자리")
    db = build([bulky(moves=["HAZE"]), bulky(moves=["SWORDSDANCE"])], [bulky(moves=["SWORDSDANCE"]), bulky(moves=["SWORDSDANCE"])])
    db.start()
    for pk in ("a1", "b0", "b1"):
        f(db, pk).stages["atk"] = 2
    go(db, [mv(0, "HAZE"), mv(1, "SWORDSDANCE")], [mv(0, "SWORDSDANCE"), mv(1, "SWORDSDANCE")])
    # 흑안개가 없으면 2 + 칼춤 2 = 4. 지워졌으면 0 (먼저 칼춤) 이거나 2 (흑안개 뒤에 칼춤)
    chk("흑안개는 넷 모두의 능력 변화를 지운다 (그 뒤에 쓴 칼춤은 남는다)",
        all(f(db, pk).stages.get("atk", 0) in (0, 2) for pk in ("a1", "b0", "b1")),
        [f(db, pk).stages.get("atk") for pk in ("a1", "b0", "b1")])
    db = build([bulky(moves=["PERISHSONG"]), bulky()], [bulky(), bulky("BLISSEY")])
    db.start()
    go(db, [mv(0, "PERISHSONG"), mv(1, "TACKLE", "foe0")], None)
    chk("멸망의노래는 넷 모두에게 걸린다", all(f(db, pk).cond.get("perish") for pk in ("a0", "a1", "b0", "b1")),
        [f(db, pk).cond.get("perish") for pk in ("a0", "a1", "b0", "b1")])

    db = build([bulky(), bulky("BLISSEY", moves=["WISH", "TACKLE"])], [bulky(), bulky()])
    db.start()
    f(db, "a0").hp = f(db, "a0").maxhp // 2
    f(db, "a1").hp = f(db, "a1").maxhp // 2
    go(db, [mv(0, "TACKLE", "foe0"), mv(1, "WISH")], None)
    h1 = f(db, "a1").hp
    ev = go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")])
    wish = [e for e in ev if e["t"] == "heal" and "소원" in (e.get("text") or "")]
    chk("희망사항은 빈 자리(a1)로 간다", len(wish) == 1 and wish[0].get("at") == "a1" and f(db, "a1").hp > h1,
        [(e["t"], e.get("at"), e.get("text")) for e in ev if e["t"] == "heal"])

    db = build([bulky("GYARADOS", moves=["SURF"]), bulky()], [bulky(), bulky("GASTRODON", ability="STORMDRAIN")])
    db.start()
    ev = go(db, [mv(0, "SURF"), mv(1, "TACKLE", "foe0")], None)
    chk("마중물은 광역기를 끌어오지 않는다 (자기 몫만 받는다)", len(hits(ev, "a0", "b0")) == 1 and len(hits(ev, "a0", "a1")) == 1
        and not hits(ev, "a0", "b1"), [(e["t"], e.get("at"), e.get("to")) for e in ev if e.get("at") == "a0"])

    print("\n== 상대에게 안 보이는 것 · 턴 제한 · 턴 도중 저장")
    db = build([bulky(held="LEFTOVERS"), bulky(held="LIFEORB"), bulky("MILTANK", held="SITRUSBERRY")], [bulky(), bulky()])
    ev = db.start()
    ev += go(db, [sw(0, 2), mv(1, "TACKLE", "foe0")], None)
    seen = [e for e in db.events_for("b", ev) if e["t"] == "switch" and e["who"] == "foe"]
    mine = [e for e in db.events_for("a", ev) if e["t"] == "switch" and e["who"] == "me"]
    chk("상대가 내보낸 포켓몬의 도구 · 특성은 일 목록에 안 실린다 (내 것은 실린다)",
        len(seen) == 3 and not any(k in e["mon"] for e in seen for k in ("held", "heldKr", "ability", "id"))
        and all("held" in e["mon"] for e in mine) and "LEFTOVERS" not in json.dumps(db.events_for("b", ev))
        and "SITRUSBERRY" not in json.dumps(db.view("b")), [sorted(e["mon"]) for e in seen][:1])

    db = build([bulky(), bulky()], [bulky(), bulky(), bulky()], turns=2)
    db.start()
    go(db)
    go(db)
    chk("턴 제한: 남은 머릿수로 가린다", db.over and db.reason == "turns" and db.result == "b", (db.over, db.reason, db.result))

    db = build([mon("SCIZOR", ["UTURN"], evs={"spe": 252}, nature="JOLLY"), bulky(), bulky("MILTANK")],
               [bulky(), bulky("BLISSEY")], seed=9)
    db.start()
    go(db, [mv(0, "UTURN", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe1")])
    twin = D.DoubleBattle.load(DEX, json.loads(json.dumps(db.dump())))
    chk("턴 도중(유턴으로 멈춘 자리)에 저장해도 이어진다", twin.phase() == "switch" and twin.side("a").need == [0]
        and twin.mid is not None)
    e1, e2 = go(db, [sw(0, 2)], None), go(twin, [sw(0, 2)], None)
    chk("  되살린 판도 남은 차례를 똑같이 돈다", json.dumps(e1) == json.dumps(e2)
        and len([e for e in e2 if e["t"] == "move"]) == 3 and twin.mid is None,
        [(e["t"], e.get("at"), e.get("to")) for e in e2])

    weak = mon("PIDGEY", ["TACKLE"], level=5)
    db = build([mon("GOLEM", ["SWIFT"], evs={"spa": 252, "spe": 252}, level=100), bulky()],
               [dict(weak), dict(weak), bulky(), bulky("BLISSEY")])
    db.start()
    ev = go(db, [mv(0, "SWIFT"), mv(1, "TACKLE", "foe0")], None)
    chk("둘이 같이 쓰러지면 두 자리를 한 번에 고른다", db.phase() == "switch" and db.side("b").need == [0, 1]
        and len([e for e in ev if e["t"] == "faint"]) == 2, (db.phase(), db.side("b").need))
    try:
        db.choose("b", "picks", [sw(0, 2)])
        half = True
    except ValueError:
        half = False
    go(db, None, [sw(0, 3), sw(1, 2)])
    chk("  한 자리만 보내면 안 받는다 · 둘 다 고르면 선다", not half and db.side("b").active == [3, 2]
        and db.phase() == "choose", (half, db.side("b").active))


def review():
    """브랜치 검토(11/25)에서 나온 것들."""
    print("\n== 검토에서 나온 것")
    def zteam():
        db = build([bulky("GARCHOMP", moves=["EARTHQUAKE"], held="GROUNDIUMZ"), bulky()], [bulky(), bulky("BLISSEY")])
        db.zring["me"] = True
        db.start()
        return db
    db = zteam()
    zm = db.view("a")["me"]["acts"][0]["zMoves"]
    chk("광역기로 만든 Z기술은 대상을 고른다 (보기에 고를 자리가 온다)", len(zm) == 1 and zm[0]["key"] == "EARTHQUAKE"
        and zm[0].get("targets") == ["foe0", "foe1", "ally"], zm)
    ev = go(db, [mv(0, "EARTHQUAKE", "foe1", z=True), mv(1, "TACKLE", "foe0")], None)
    chk("  고른 하나만 맞는다 (아군 · 다른 상대는 안 맞는다)", [e["to"] for e in hits(ev, "a0")] == ["b1"]
        and any(e["t"] == "zpower" for e in ev), [(e["t"], e.get("at"), e.get("to")) for e in ev if e.get("at") == "a0"])
    db = zteam()
    ev = go(db, [mv(0, "EARTHQUAKE"), mv(1, "TACKLE", "foe0")], None)
    chk("  Z기술로 안 쓰면 예전처럼 셋을 때린다", sorted(e["to"] for e in hits(ev, "a0")) == ["a1", "b0", "b1"])

    db = build([bulky(), bulky()], [bulky(), bulky()])
    db.start()
    bad = []
    for picks in ([{"pos": 0, "kind": "move", "move": ["x"]}, mv(1, "TACKLE", "foe0")],
                  [{"pos": 1e999, "kind": "move", "move": "TACKLE"}, mv(1, "TACKLE", "foe0")],
                  [{"pos": 0, "kind": "switch", "slot": 1e999}, mv(1, "TACKLE", "foe0")],
                  [{"pos": 0, "kind": "move", "move": "TACKLE", "target": {"a": 1}}, mv(1, "TACKLE", "foe0")],
                  [{"pos": [0], "kind": "move", "move": "TACKLE"}, mv(1, "TACKLE", "foe0")],
                  "TACKLE", [None, 3], [{"pos": 0, "kind": {"x": 1}}, mv(1, "TACKLE", "foe0")]):
        try:
            db.choose("a", "picks", picks)
            bad.append(("받았다", picks))
        except ValueError:
            pass
        except Exception as e:                              # noqa: BLE001
            bad.append((repr(e)[:60], picks))
    chk("이상한 꼴의 고르기는 전부 거절한다 (오류로 터지지 않는다)", not bad and db.side("a").picks is None, bad[:2])

    # (심는 쪽이 풀 타입이면 튕겨 온 씨앗이 안 심긴다 - 잠만보로 본다)
    db = build([bulky(moves=["LEECHSEED"]), bulky()], [bulky("ESPEON", ability="MAGICBOUNCE"), bulky("BLISSEY")])
    db.start()
    f(db, "b0").hp = f(db, "b0").maxhp // 2
    h0 = f(db, "b0").hp
    ev = go(db, [mv(0, "LEECHSEED", "foe0"), mv(1, "SPLASH") if "SPLASH" in f(db, "a1").pp else mv(1, "TACKLE", "foe1")],
            [mv(0, "TACKLE", "foe1"), mv(1, "TACKLE", "foe1")])
    heal = [e for e in ev if e["t"] == "heal" and "흡수" in (e.get("text") or "")]
    chk("매직미러로 튕긴 씨뿌리기: 튕겨 낸 포켓몬이 회복한다", f(db, "a0").seeded and f(db, "a0").seed_by == "b0"
        and len(heal) == 1 and heal[0].get("at") == "b0" and f(db, "b0").hp > h0,
        (f(db, "a0").seeded, f(db, "a0").seed_by, [(e["t"], e.get("at")) for e in ev if e["t"] in ("heal", "chip")]))

    db = build([bulky("GOLEM", moves=["SWIFT"], held="LIFEORB"), bulky()], [bulky(), bulky("BLISSEY")])
    db.start()
    f(db, "a0").hp = max(1, f(db, "a0").maxhp // 20)
    ev = go(db, [mv(0, "SWIFT"), mv(1, "TACKLE", "foe0")], [mv(0, "TACKLE", "foe1"), mv(1, "TACKLE", "foe1")])
    mine = [(e["t"], e.get("to")) for e in ev if e.get("at") == "a0" and e["t"] in ("hit", "chip", "faint")]
    chk("생명의구슬 반동은 다 때린 뒤에 (체력이 얼마 없어도 둘 다 맞힌다)",
        mine == [("hit", "b0"), ("hit", "b1"), ("chip", None), ("faint", None)], mine)

    db = build([bulky(), bulky()], [bulky("CLEFABLE", moves=["FOLLOWME"], ability="MAGICGUARD"),
                                    mon("TOGEKISS", ["FOLLOWME"], evs={"hp": 252, "spe": 252})])
    db.start()
    ev = go(db, [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe0")], [mv(0, "FOLLOWME"), mv(1, "FOLLOWME")])
    chk("둘 다 날따름을 쓰면 먼저 쓴 쪽으로 간다", len(hits(ev, to="b1")) == 2 and not hits(ev, to="b0"),
        [(e.get("at"), e.get("to")) for e in ev if e["t"] in ("hit", "move")])

    db = build([bulky(), bulky()], [bulky(), bulky()])
    db.start()
    f(db, "b0").cond["bound"] = {"by": "foe", "turns": 4, "move": "FIRESPIN"}       # 상대의 아군이 건 것
    f(db, "b1").cond["bound"] = {"by": "me", "turns": 3, "move": "FIRESPIN"}        # 내가 건 것
    team = db.view("a")["foe"]["team"]
    chk("조이기의 남은 턴은 내 편이 건 것만 보인다 (상대끼리 건 것은 끈기갈고리손톱이 드러난다)",
        team[0]["bound"]["turns"] is None and team[1]["bound"]["turns"] == 3
        and db.view("b")["me"]["team"][0]["bound"]["turns"] is None, (team[0]["bound"], team[1]["bound"]))


def gimmicks():
    print("\n== 메가진화는 편마다 한 번")
    db = build([mon("LUCARIO", ["TACKLE"], held="LUCARIONITE"), mon("GARCHOMP", ["TACKLE"], held="GARCHOMPITE")],
               [bulky(), bulky("BLISSEY")])
    db.keystone["me"] = True
    db.start()
    va = db.view("a")
    chk("둘 다 메가진화할 수 있다고 보인다", [a["canMega"] for a in va["me"]["acts"]] == [True, True],
        [a["canMega"] for a in va["me"]["acts"]])
    try:
        db.choose("a", "picks", [mv(0, "TACKLE", "foe0", mega=True), mv(1, "TACKLE", "foe0", mega=True)])
        both = True
    except ValueError:
        both = False
    chk("한 턴에 둘은 못 한다", not both)
    ev = go(db, [mv(0, "TACKLE", "foe0", mega=True), mv(1, "TACKLE", "foe0")], None)
    megas = [e for e in ev if e["t"] == "mega"]
    chk("고른 포켓몬만 메가진화한다", len(megas) == 1 and megas[0].get("at") == "a0" and f(db, "a0").mega
        and not f(db, "a1").mega, [(e["t"], e.get("at")) for e in megas])
    chk("그 뒤로는 그 편이 다시 못 한다", [a["canMega"] for a in db.view("a")["me"]["acts"]] == [False, False])
    chk("키스톤이 없는 편은 못 한다", [a["canMega"] for a in db.view("b")["me"]["acts"]] == [False, False])


POOL = ["SNORLAX", "GARCHOMP", "GYARADOS", "TOGEKISS", "METAGROSS", "ROTOM", "TYRANITAR", "SCIZOR", "VENUSAUR",
        "CLEFABLE", "DRAGONITE", "EXCADRILL", "AMOONGUSS", "INCINEROAR", "PELIPPER", "TORKOAL", "HATTERENE", "RHYDON"]
MOVES = ["EARTHQUAKE", "ROCKSLIDE", "SURF", "PROTECT", "FAKEOUT", "UTURN", "HELPINGHAND", "FOLLOWME", "THUNDERBOLT",
         "TACKLE", "LEECHSEED", "ROAR", "WIDEGUARD", "TRICKROOM", "TAILWIND", "SWORDSDANCE", "HEATWAVE", "DISCHARGE",
         "EXPLOSION", "WILLOWISP", "RAINDANCE", "ALLYSWITCH", "ICYWIND", "DAZZLINGGLEAM", "RECOVER", "KNOCKOFF",
         "VOLTSWITCH", "SPORE", "COUNTER", "PERISHSONG", "HOWL", "LIFEDEW", "OUTRAGE", "STEALTHROCK", "WHIRLWIND"]
ITEMS = [None, None, "LEFTOVERS", "LIFEORB", "FOCUSSASH", "SITRUSBERRY", "CHOICESCARF", "ROCKYHELMET", "WHITEHERB",
         "EJECTBUTTON", "REDCARD", "WEAKNESSPOLICY"]


def random_pick(db, who, rng):
    """보기(view)에 온 것만으로 아무거나 고른다 - 화면이 할 수 있는 일만 한다."""
    v = db.view(who)
    me = v["me"]
    if v["phase"] == "switch":
        left = list(me["switches"])
        rng.shuffle(left)
        return [sw(pos, left.pop()) for pos in me["need"]]
    out, taken = [], set()
    for act in me["acts"]:
        if act is None:
            continue
        free = [s for s in me["switches"] if s not in taken]
        if act["canSwitch"] and free and rng.random() < 0.12:
            s = rng.choice(free)
            taken.add(s)
            out.append(sw(act["pos"], s))
            continue
        if act.get("locked"):
            ok = [m for m in act["moves"] if m["key"] == act["locked"]] or act["moves"]
        else:
            ok = [m for m in act["moves"] if not m["blocked"] and m["pp"] > 0] or act["moves"]
        m = rng.choice(ok)
        out.append(mv(act["pos"], m["key"], rng.choice(m["targets"]) if m["targets"] else None))
    return out


def soak(games=120):
    print("\n== 아무렇게나 %d판 (턴마다 저장했다 되살린다)" % games)
    broke, ended, turns = [], 0, 0
    for g in range(games):
        rng = random.Random(1000 + g)

        def team():
            out = []
            for sp in rng.sample(POOL, 4):
                out.append(mon(sp, rng.sample(MOVES, 4), held=rng.choice(ITEMS),
                               evs={"hp": 252, rng.choice(["atk", "spa", "spe"]): 252}))
            return out
        try:
            db = build(team(), team(), seed=g, turns=60)
            db.start()
            for _ in range(400):
                if db.over:
                    break
                for who in ("a", "b"):
                    if db.can_act(who):
                        db.choose(who, "picks", random_pick(db, who, rng))
                ev = db.resolve()
                for who in ("a", "b"):
                    for e in db.events_for(who, ev):
                        if e.get("who") in ("me", "foe") and e.get("t") not in ("intro", "over", "choose"):
                            assert str(e.get("at", "")).startswith(e["who"]), ("자리와 편이 어긋난다", e)
                db = D.DoubleBattle.load(DEX, json.loads(json.dumps(db.dump())))
                for who in ("a", "b"):
                    db.view(who)
            ended += db.over
            turns += db.turn
            if not db.over:
                broke.append((g, "안 끝났다", db.turn, db.phase()))
        except Exception as e:                                # noqa: BLE001
            import traceback
            broke.append((g, repr(e)[:160], traceback.format_exc().strip().splitlines()[-3][-110:]))
    chk("전부 끝까지 간다 (예외 없음 · 이벤트의 자리와 편이 맞는다)", not broke and ended == games, broke[:4])
    print("       평균 %.1f턴" % (turns / float(games)))


def save_load():
    print("\n== 저장")
    db = build([bulky("GOLEM", moves=["EARTHQUAKE"]), bulky(), bulky("MILTANK")], [bulky(), bulky("BLISSEY")], seed=11)
    db.start()
    go(db, [mv(0, "EARTHQUAKE"), mv(1, "TACKLE", "foe0")], None)
    blob = json.dumps(db.dump())
    twin = D.DoubleBattle.load(DEX, json.loads(blob))
    chk("되살린 판은 같은 판이다", json.dumps(twin.dump(), sort_keys=True) == json.dumps(json.loads(blob), sort_keys=True))
    e1 = go(db, [mv(0, "EARTHQUAKE"), mv(1, "TACKLE", "foe1")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe1")])
    e2 = go(twin, [mv(0, "EARTHQUAKE"), mv(1, "TACKLE", "foe1")], [mv(0, "TACKLE", "foe0"), mv(1, "TACKLE", "foe1")])
    chk("같은 수를 두면 같은 일이 일어난다 (난수까지 이어진다)", json.dumps(e1) == json.dumps(e2))


def main():
    global DEX
    with open(DEX_PATH, encoding="utf-8") as fh:
        DEX = P.Pokedex(json.load(fh))
    basics()
    spread()
    redirect()
    order_and_faint()
    switching()
    more()
    review()
    gimmicks()
    save_load()
    soak()
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
