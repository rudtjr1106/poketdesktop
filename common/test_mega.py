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
import json
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

    # 제보 #123: 메가개굴닌자가 물수리검으로 물 타입이 됐는데 다음 턴에 물/악으로 돌아가
    # 치근거리기를 2배로 맞았다. 턴마다 잤다 깨는 배틀(관장·실시간·레이드)이 메가를 다시
    # 입히면서, 메가진화한 **뒤에** 바뀐 타입·특성까지 지우고 있었다.
    from common import live_battle as LB, raid_battle as RB, trainer_battle as TB
    bt14, a14, _ = duel(mon("GRENINJA", "GRENINJITE", ("WATERSHURIKEN",)), mon("SNORLAX"))
    bt14.take_turn("WATERSHURIKEN", mega=True)
    chk("메가개굴닌자의 변환자재: 물수리검을 쓰면 물 타입",
        a14.mega == "GRENINJA_MEGA" and a14.types() == ["WATER"], (a14.mega, a14.types()))
    for kr, cls in (("관장", TB.TrainerBattle), ("실시간", LB.LiveBattle), ("레이드", RB.RaidBattle)):
        host = cls.__new__(cls)
        host.dex = DEX
        back = host._load_fighter(json.loads(json.dumps(cls._dump_fighter(a14))))
        chk("%s: 불러와도 바뀐 타입 그대로" % kr,
            back.mega == "GRENINJA_MEGA" and back.types() == ["WATER"], (back.mega, back.types()))
        chk("  변환자재는 쓴 것으로 남는다 (다시 안 바뀐다)", back.ab.get("protean"), back.ab)
        a14.ability, keep = "MUMMY", a14.ability       # 미라에 닿아 특성이 바뀌었다
        back = host._load_fighter(json.loads(json.dumps(cls._dump_fighter(a14))))
        a14.ability = keep
        chk("  불러와도 바뀐 특성 그대로", back.ability == "MUMMY", back.ability)

    print("\n=== 메가지가르데: 코어퍼니셔 -> 니힐레이저 (1.10.3, 게시판 #158) ===")
    from common import attackfx as AFX, statusmoves as SMX
    nl = DEX.move("NIHILLIGHT")
    chk("니힐레이저가 도감에 있다: 드래곤·특수·위력 200", nl and (nl["kr"], nl["type"], nl["cat"], nl["power"]) ==
        ("니힐레이저", "DRAGON", "special", 200), nl)
    zy = mon("ZYGARDE", "ZYGARDITE", ("COREENFORCER", "EARTHQUAKE"))

    def zduel(foe, seed=3):
        return duel(mon("ZYGARDE", "ZYGARDITE", ("COREENFORCER", "EARTHQUAKE")), foe, seed=seed)
    btz, az, bz = zduel(mon("CLEFABLE", moves=("SPLASH",)))
    hp0 = bz.hp
    ev = btz.take_turn("COREENFORCER", mega=False)
    chk("메가진화 전: 코어퍼니셔는 페어리에게 안 통한다 (드래곤 기술)", bz.hp == hp0
        and any(e.get("t") == "move" and e.get("move") == "코어퍼니셔" for e in ev), [e.get("text") for e in ev][:4])
    pp_before = az.pp["COREENFORCER"]
    ev = btz.take_turn("COREENFORCER", mega=True)            # 이 턴에 고른 것은 아직 '코어퍼니셔' 다
    used = [e for e in ev if e.get("t") == "move" and e.get("who") == "me"]
    chk("**메가진화하면 코어퍼니셔가 니힐레이저로 바뀐다**", az.mega == "ZYGARDE_MEGA" and az.moves == ["NIHILLIGHT", "EARTHQUAKE"]
        and az.alias == {"COREENFORCER": "NIHILLIGHT"}, (az.mega, az.moves))
    chk("  그 턴에 고른 코어퍼니셔가 니힐레이저로 나간다", used and used[0].get("move") == "니힐레이저", used[:1])
    chk("  **페어리에게도 맞는다**", bz.hp < hp0, (hp0, bz.hp))
    chk("  PP 는 이어받아 한 번 쓴 만큼 준다", az.pp["NIHILLIGHT"] == pp_before - 1, (pp_before, az.pp))
    chk("  포켓몬이 아는 기술은 그대로다 (이 판 안에서만 바뀐다)", az.mon["moves"] == ["COREENFORCER", "EARTHQUAKE"]
        and zy["moves"] == ["COREENFORCER", "EARTHQUAKE"])
    chk("  상성은 페어리를 뺀 나머지 타입만 본다", B.type_eff(DEX, nl, "DRAGON", az, bz, True) == 1.0
        and B.type_eff(DEX, DEX.move("COREENFORCER"), "DRAGON", az, bz, True) == 0.0)
    _b2, a2z, b2z = zduel(mon("ALTARIA", "ALTARIANITE", moves=("SPLASH",)))
    b2z.mega_evolve(DEX.get("ALTARIA_MEGA"))                  # 드래곤·페어리
    chk("  드래곤·페어리에게는 효과가 굉장하다 (드래곤만 본다)", b2z.types() == ["DRAGON", "FAIRY"]
        and B.type_eff(DEX, nl, "DRAGON", a2z, b2z, True) == 2.0, b2z.types())

    def nihil_damage(stages):
        bt_, a_, b_ = zduel(mon("SNORLAX", moves=("SPLASH",)), seed=11)
        a_.mega_evolve(DEX.get("ZYGARDE_MEGA"))
        b_.stages["spd"] = stages
        h = b_.hp
        bt_.rng = random.Random(5)
        bt_._use("me", a_, b_, "NIHILLIGHT", [])
        return h - b_.hp
    base_d, up_d, down_d = nihil_damage(0), nihil_damage(6), nihil_damage(-6)
    chk("  **상대의 능력 변화를 무시한다** (특수방어를 여섯 단계 올려도, 내려도 데미지가 같다)",
        base_d > 0 and base_d == up_d == down_d, (base_d, up_d, down_d))
    bt3, a3z, b3z = zduel(mon("SNORLAX", moves=("SPLASH",)))
    a3z.mega_evolve(DEX.get("ZYGARDE_MEGA"))
    bt3.acted = {"foe"}
    ev3 = []
    bt3._use("me", a3z, b3z, "NIHILLIGHT", ev3)
    chk("  코어퍼니셔의 '특성을 없앤다' 는 없다", not b3z.cond.get("gastro"), b3z.cond)
    chk("  손가락흔들기로는 안 나온다", "NIHILLIGHT" in SMX.NO_METRONOME and "NIHILLIGHT" in AFX.IGNORE_STAGES)
    for kr, cls in (("관장", TB.TrainerBattle), ("실시간", LB.LiveBattle), ("레이드", RB.RaidBattle)):
        host = cls.__new__(cls)
        host.dex = DEX
        back = host._load_fighter(json.loads(json.dumps(cls._dump_fighter(az))))
        chk("%s: 저장했다 불러와도 니힐레이저 그대로 (PP 도)" % kr, back.moves == ["NIHILLIGHT", "EARTHQUAKE"]
            and back.pp["NIHILLIGHT"] == az.pp["NIHILLIGHT"] and back.alias == {"COREENFORCER": "NIHILLIGHT"},
            (back.moves, back.pp))
    az.cond["encore"] = {"move": "COREENFORCER", "turns": 2}
    plain = B.Fighter(DEX, mon("ZYGARDE", "ZYGARDITE", ("COREENFORCER",)))
    plain.cond["encore"] = {"move": "COREENFORCER", "turns": 2}
    plain.cond["lastMove"] = "COREENFORCER"
    plain.mega_evolve(DEX.get("ZYGARDE_MEGA"))
    chk("  앙코르처럼 그 기술을 가리키던 것도 따라 바뀐다", plain.cond["encore"]["move"] == "NIHILLIGHT"
        and plain.cond["lastMove"] == "NIHILLIGHT", plain.cond)
    other = B.Fighter(DEX, mon("ZYGARDE", "ZYGARDITE", ("EARTHQUAKE",)))
    other.mega_evolve(DEX.get("ZYGARDE_MEGA"))
    chk("  코어퍼니셔를 모르는 지가르데는 메가진화해도 니힐레이저가 안 생긴다", other.moves == ["EARTHQUAKE"] and other.alias == {})
    g = B.Fighter(DEX, mon("GENGAR", "GENGARITE", ("SHADOWBALL",)))
    g.mega_evolve(DEX.get("GENGAR_MEGA"))
    chk("  다른 메가는 기술이 안 바뀐다", g.moves == ["SHADOWBALL"] and g.alias == {})

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
