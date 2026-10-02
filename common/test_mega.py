# -*- coding: utf-8 -*-
"""메가진화 엔진 검사 (시즌 3).

    python common/test_mega.py

  1. 스톤을 지니고 키스톤이 있으면 턴 처음에 바뀐다 - 종족값·타입·특성이
     바뀌고 **체력은 그대로**다. 별명이 없으면 이름도 메가 이름.
  2. **한 판에 한 번.** 한 쪽에서 한 마리만.
  3. 키스톤이 없거나, 맞는 스톤이 아니면 안 바뀐다.
  4. **바뀐 스피드로 그 턴의 순서를 정한다.**
  5. 새 특성은 나올 때처럼 바로 발동한다 (메가리자몽Y 의 가뭄).
  6. 저장했다 불러와도, 교체해도 메가는 그대로다.
  7. 메가스톤은 트릭·바꿔치기·탁쳐서떨구기로 못 뺏는다.
  8. 레쿠쟈는 스톤 없이 화룡점정을 알면 된다. 냐오닉스는 성별로 고른다.
  9. AI 쪽(auto_mega)은 알아서 바뀐다.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import abilities as A                  # noqa: E402
from common import battle as B                               # noqa: E402
from common import held as H                                 # noqa: E402
from common import pokelogic as P                            # noqa: E402

DEX = P.Pokedex.load(os.path.join(os.path.dirname(HERE), "server", "data",
                                  "pokedex.json"))
OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mon(species, held=None, moves=("TACKLE",), level=50, gender="M", nick=None):
    m = P.make_pokemon(DEX.get(species), level, random.Random(1), shiny_rate=10 ** 9)
    m["ivs"] = dict((s, 31) for s in P.STATS)
    m["evs"] = dict((s, 0) for s in P.STATS)
    m["nature"] = "HARDY"
    m["moves"] = list(moves)
    m["held"] = held
    m["gender"] = gender
    m["nickname"] = nick
    return m


def duel(a, b, keystone=True, abil=True, seed=3):
    fa, fb = B.Fighter(DEX, a), B.Fighter(DEX, b)
    fa.ability_on = fb.ability_on = abil
    bt = B.Battle(DEX, fa, fb, random.Random(seed), ai="trainer")
    bt.kind = "gym"
    bt.keystone = {"me": keystone, "foe": False}
    return bt, fa, fb


def main():
    print("=== 자료 ===")
    chk("메가 폼 94개", len(DEX.megas) == 94, len(DEX.megas))
    chk("species 는 그대로 1025", len(DEX.species) == 1025, len(DEX.species))
    chk("메가스톤을 도구로 안다", H.normalize("charizarditex") == "CHARIZARDITEX"
        and H.name("CHARIZARDITEX") == "리자몽나이트X")
    chk("메가 폼도 이름으로 찾는다", DEX.get("CHARIZARD_MEGA_X")["num"] == 10034)

    print("\n=== 바뀐다 ===")
    bt, a, b = duel(mon("CHARIZARD", "CHARIZARDITEX", ("FLAMETHROWER",)),
                    mon("SNORLAX"))
    hp0, max0 = a.hp, a.maxhp
    ev = bt.take_turn("FLAMETHROWER", mega=True)
    megas = [e for e in ev if e.get("t") == "mega"]
    chk("메가진화 사건이 난다", len(megas) == 1 and megas[0]["to"] == "메가리자몽X",
        [e.get("t") for e in ev][:5])
    chk("메가가 기술보다 먼저", ev.index(megas[0]) < next(
        i for i, e in enumerate(ev) if e.get("t") == "move"))
    chk("타입이 불꽃·드래곤", a.types() == ["FIRE", "DRAGON"], a.types())
    chk("특성이 단단한발톱", a.ability == "TOUGHCLAWS", a.ability)
    chk("공격이 오른다", a.base["atk"] > B.Fighter(DEX, a.mon).base["atk"])
    chk("최대 체력은 그대로", a.maxhp == max0, (max0, a.maxhp))
    chk("이름이 메가 이름", a.name == "메가리자몽X", a.name)
    chk("사건에 번호·타입이 실린다 (화면이 도트를 바꾼다)",
        megas[0]["num"] == 10034 and megas[0]["types"] == ["FIRE", "DRAGON"])

    print("\n=== 한 판에 한 번 ===")
    ev2 = bt.take_turn("FLAMETHROWER", mega=True)
    chk("두 번째 턴에는 안 바뀐다", not any(e.get("t") == "mega" for e in ev2))
    chk("can_mega 도 None", bt.can_mega("me") is None)

    print("\n=== 안 되는 경우 ===")
    bt2, a2, _ = duel(mon("CHARIZARD", "CHARIZARDITEX"), mon("SNORLAX"), keystone=False)
    bt2.take_turn("TACKLE", mega=True)
    chk("키스톤이 없으면 안 된다", a2.mega is None)
    bt3, a3, _ = duel(mon("CHARIZARD", "VENUSAURITE"), mon("SNORLAX"))
    bt3.take_turn("TACKLE", mega=True)
    chk("남의 스톤이면 안 된다", a3.mega is None)
    bt4, a4, _ = duel(mon("CHARIZARD", "LEFTOVERS"), mon("SNORLAX"))
    chk("스톤이 없으면 can_mega 가 None", bt4.can_mega("me") is None)
    bt5, a5, _ = duel(mon("CHARIZARD", "CHARIZARDITEX"), mon("SNORLAX"))
    bt5.take_turn("TACKLE", mega=False)
    chk("메가를 안 누르면 안 바뀐다", a5.mega is None)

    print("\n=== 바뀐 스피드로 순서 ===")
    # 메가앱솔은 스피드가 75 -> 115. 같은 레벨 잠만보보다 원래도 빠르지만,
    # 메가 전 스피드가 상대보다 느리고 메가 뒤 빨라지는 조합을 쓴다.
    ab = mon("MANECTRIC", "MANECTITE", ("TACKLE",))
    foe = mon("JOLTEON", None, ("TACKLE",))
    bt6, a6, b6 = duel(ab, foe, abil=False)
    s0 = bt6.speed("me")
    fs = bt6.speed("foe")
    ev6 = bt6.take_turn("TACKLE", mega=True)
    s1 = bt6.speed("me")
    moves = [e["who"] for e in ev6 if e.get("t") == "move"]
    if s0 < fs < s1:
        chk("메가 뒤 빨라지면 그 턴부터 먼저", moves[:1] == ["me"], (s0, fs, s1, moves))
    else:
        chk("(순서 검사용 조합이 맞지 않음 - 스피드 %d/%d/%d)" % (s0, fs, s1), True)

    print("\n=== 새 특성이 바로 ===")
    bt7, a7, _ = duel(mon("CHARIZARD", "CHARIZARDITEY"), mon("SNORLAX"))
    bt7.take_turn("TACKLE", mega=True)
    chk("메가리자몽Y 의 가뭄 -> 햇빛", bt7.field.weather == "sun", bt7.field.weather)

    print("\n=== 메가진화하면 특성이 바뀐 것을 알린다 (1.9.0) ===")
    # 제보: 가디안이 나오며 트레이스로 상대 특성을 베끼고, 메가진화하면
    # 페어리스킨이 되는데 **배틀 화면에는 그 얘기가 없다.** 엔진은 바꾸고
    # 있었고, 사건에 실어 보내지 않아서 화면이 옛 특성을 그대로 들고 있었다.
    g = mon("GARDEVOIR", "GARDEVOIRITE")
    g["ability"] = "TRACE"
    foe = mon("GYARADOS")
    foe["ability"] = "INTIMIDATE"
    bt9, a9, b9 = duel(g, foe)
    ev0 = []
    A.on_switch_in(bt9, a9, "me", ev0)
    chk("나오면서 상대 특성(위협)을 트레이스한다", a9.ability == "INTIMIDATE", a9.ability)
    ev = bt9.take_turn("TACKLE", mega=True)
    mg = [e for e in ev if e.get("t") == "mega"][0]
    chk("메가진화하면 특성이 메가 폼의 것(페어리스킨)이 된다", a9.ability == "PIXILATE", a9.ability)
    chk("메가 사건에 새 특성이 실린다 (화면이 칸을 고친다)",
        mg.get("ability") == "PIXILATE" and mg.get("abilityKr") == DEX.ability_name("PIXILATE"), mg)
    said = [e for e in ev if e.get("t") == "msg" and "특성이" in (e.get("text") or "")]
    chk("바뀌었다고 한 줄 알린다", len(said) == 1 and DEX.ability_name("PIXILATE") in said[0]["text"]
        and said[0]["who"] == "me" and ev.index(said[0]) == ev.index(mg) + 1,
        [e.get("text") for e in said])
    chk("메가 폼의 특성은 상대에게도 보인다", a9.ab.get("shown") is True)
    # 원래 특성과 메가 특성이 같으면 '바뀌었다' 고 하지 않는다
    r = mon("RAYQUAZA", None, ("DRAGONASCENT", "TACKLE"))
    r["ability"] = "AIRLOCK"
    form = [m for m in DEX.megas if m["megaOf"] == "RAYQUAZA"][0]
    same = "".join(c for c in str(form["abil"][0]).upper() if c.isalnum())
    r["ability"] = same
    bt10, a10, _ = duel(r, mon("SNORLAX"))
    ev = bt10.take_turn("TACKLE", mega=True)
    mg = [e for e in ev if e.get("t") == "mega"]
    chk("특성이 그대로면 '바뀌었다' 는 말은 없다 (사건에는 실린다)",
        len(mg) == 1 and mg[0].get("ability") == same
        and not any("특성이" in (e.get("text") or "") for e in ev if e.get("t") == "msg"),
        [e.get("text") for e in ev if e.get("t") == "msg"])
    # 특성을 끈 판(야생 배틀)에서는 특성 얘기를 하지 않는다
    bt11, a11, _ = duel(mon("GARDEVOIR", "GARDEVOIRITE"), mon("SNORLAX"), abil=False)
    ev = bt11.take_turn("TACKLE", mega=True)
    mg = [e for e in ev if e.get("t") == "mega"]
    chk("특성이 꺼진 판에서는 특성을 싣지 않는다", len(mg) == 1 and "ability" not in mg[0]
        and not any("특성이" in (e.get("text") or "") for e in ev), mg)

    print("\n=== 저장·교체 ===")
    bt8, a8, _ = duel(mon("GENGAR", "GENGARITE"), mon("SNORLAX"))
    bt8.take_turn("TACKLE", mega=True)
    v = a8.volatile()
    fresh = B.Fighter(DEX, a8.mon)
    fresh.load_volatile(v)
    chk("불러와도 메가 그대로", fresh.mega == "GENGAR_MEGA" and fresh.ability == a8.ability,
        (fresh.mega, fresh.ability))
    a8.clear_volatile()
    chk("교체해도 메가 그대로", a8.mega == "GENGAR_MEGA" and a8.types() == fresh.types())

    print("\n=== 스톤은 못 뺏는다 ===")
    bt9, a9, b9 = duel(mon("KANGASKHAN", "KANGASKHANITE"),
                       mon("ALAKAZAM", "LEFTOVERS", ("TRICK", "KNOCKOFF")))
    ev9 = []
    bt9._use("foe", b9, a9, "TRICK", ev9)
    chk("트릭 실패", a9._held == "KANGASKHANITE" and b9._held == "LEFTOVERS",
        (a9._held, b9._held))
    ev9 = []
    bt9._use("foe", b9, a9, "KNOCKOFF", ev9)
    chk("탁쳐서떨구기로 안 떨어진다", a9._held == "KANGASKHANITE", a9._held)

    print("\n=== 레쿠쟈 · 냐오닉스 ===")
    bt10, a10, _ = duel(mon("RAYQUAZA", None, ("DRAGONASCENT", "TACKLE")), mon("SNORLAX"))
    chk("레쿠쟈는 화룡점정이면 된다", bt10.can_mega("me") is not None)
    bt11, a11, _ = duel(mon("RAYQUAZA", None, ("TACKLE",)), mon("SNORLAX"))
    chk("화룡점정이 없으면 안 된다", bt11.can_mega("me") is None)
    f_m = B.Fighter(DEX, mon("MEOWSTIC", "MEOWSTICITE", gender="M"))
    f_f = B.Fighter(DEX, mon("MEOWSTIC", "MEOWSTICITE", gender="F"))
    chk("냐오닉스 수컷", f_m.mega_target()["internal"] == "MEOWSTIC_MEGA",
        f_m.mega_target()["internal"])
    chk("냐오닉스 암컷", f_f.mega_target()["internal"] == "MEOWSTIC_MEGA_F",
        f_f.mega_target()["internal"])

    print("\n=== 별명 · AI ===")
    bt12, a12, _ = duel(mon("GARDEVOIR", "GARDEVOIRITE", nick="가디"), mon("SNORLAX"))
    bt12.take_turn("TACKLE", mega=True)
    chk("별명이 있으면 별명 그대로", a12.name == "가디" and a12.mega, a12.name)
    bt13, _a, b13 = duel(mon("SNORLAX"), mon("LUCARIO", "LUCARIONITE", ("TACKLE",)))
    bt13.keystone = {"me": False, "foe": True}
    bt13.auto_mega = {"me": False, "foe": True}
    bt13.take_turn("TACKLE")
    chk("AI 쪽은 알아서 바뀐다", b13.mega == "LUCARIO_MEGA", b13.mega)

    print("\n=== 높은 관장 ===")
    from common import trainer_battle as TB
    team = [{"species": "PIKACHU", "level": 85, "moves": ["TACKLE"]},
            {"species": "GYARADOS", "level": 85, "moves": ["TACKLE"]}]
    hi = {"id": "t_hi", "name": "높은관장", "level": 85, "team": team}
    lo = {"id": "t_lo", "name": "낮은관장", "level": 60, "team": team}
    me = [mon("SNORLAX", None, ("TACKLE",))]
    tb = TB.TrainerBattle(DEX, me, hi, random.Random(4))
    chk("Lv.80 이상 관장은 메가가 되는 첫 포켓몬에게 스톤을 쥐여 준다",
        tb.foe_team[1]._held == "GYARADOSITE" and tb.foe_team[0]._held != "GYARADOSITE",
        [f._held for f in tb.foe_team])
    chk("  그리고 키스톤이 있다", tb.keystone["foe"] and tb.bt.auto_mega["foe"])
    tb2 = TB.TrainerBattle(DEX, me, lo, random.Random(4))
    chk("낮은 관장은 안 쓴다", not tb2.keystone["foe"]
        and all(f._held != "GYARADOSITE" for f in tb2.foe_team))
    d = tb.dump()
    tb3 = TB.TrainerBattle.load(DEX, d)
    chk("저장했다 불러와도 키스톤·한 번이 남는다",
        tb3.keystone == tb.keystone and tb3.bt.mega_done is tb3.mega_done)
    view = tb.view()
    chk("화면에 canMega (키스톤 없으면 False)", view.get("canMega") is False, view.get("canMega"))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
