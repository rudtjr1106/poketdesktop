# -*- coding: utf-8 -*-
"""1.6.0 에서 채운 특성과 턴제 기술 검사.

    python common/test_new_abilities.py

사용자 제보로 시작했다: "게을킹의 게으름, 킬라플로르의 독치장 같은 게
미구현인 것 같다", "역린 같은 턴제 기술", "속이기의 풀죽음 확률".

확인한 것: **풀죽음 확률과 우선도 자료는 처음부터 맞았다** (속이기 100%·
우선도 3, 스톤샤워 30%, 악의파동 20%). 빠져 있던 것은 속이기가 **나온
첫 턴에만** 쓸 수 있다는 규칙이었다 - 그게 없으면 매 턴 100% 풀죽이는
기술이 된다.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import abilities as A                  # noqa: E402
from common import battle as B                     # noqa: E402
from common import pokelogic as P                  # noqa: E402
from common import statusmoves as SM               # noqa: E402

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


def mon(species, level=50, moves=None, ability=None, gender="M"):
    sp = DEX.get(species)
    m = P.make_pokemon(sp, level, random.Random(1), shiny_rate=10 ** 9)
    m["ivs"] = dict((s, 31) for s in P.STATS)
    m["evs"] = dict((s, 0) for s in P.STATS)
    m["nature"] = "HARDY"
    m["held"] = None
    m["gender"] = gender
    if moves:
        m["moves"] = list(moves)
    if ability:
        m["ability"] = ability
    return m


def duel(a_sp, b_sp, a_moves=("TACKLE",), b_moves=("TACKLE",),
         a_ab=None, b_ab=None, seed=3, a_gender="M", b_gender="F"):
    a = B.Fighter(DEX, mon(a_sp, moves=a_moves, ability=a_ab, gender=a_gender))
    b = B.Fighter(DEX, mon(b_sp, moves=b_moves, ability=b_ab, gender=b_gender))
    a.ability_on = b.ability_on = True
    bt = B.Battle(DEX, a, b, random.Random(seed), ai="trainer")
    bt.kind = "gym"
    bt.max_turns = 10 ** 9
    return bt, a, b


def main():
    global DEX
    DEX = P.Pokedex.load(DEX_PATH)

    print("=== 게으름 (게을킹) ===")
    bt, a, b = duel("SLAKING", "SNORLAX", a_ab="TRUANT")
    a.cond["outTurns"] = 1
    moved = []
    for t in range(4):
        ev = []
        moved.append(bt._can_move("me", a, ev))
    chk("한 턴 쓰고 한 턴 쉰다", moved == [True, False, True, False], moved)
    a.ab.pop("loaf", None)
    ev = []
    A.on_switch_in(bt, a, "me", ev)
    chk("물러났다 나오면 다시 센다", not a.ab.get("loaf"))

    print("=== 독치장 (킬라플로르) ===")
    bt, a, b = duel("GLIMMORA", "SNORLAX", b_moves=("TACKLE",), a_ab="TOXICDEBRIS")
    ev = []
    A.after_hit(bt, b, "foe", a, "me", bt.move_of("TACKLE"), 20, 1.0, False, a.hp + 20, ev)
    chk("물리 기술을 맞으면 독압정이 깔린다",
        bt.field.side("foe").get("toxicspikes") == 1,
        bt.field.side("foe"))
    ev = []
    A.after_hit(bt, b, "foe", a, "me", bt.move_of("TACKLE"), 20, 1.0, False, a.hp + 20, ev)
    chk("두 겹까지만", bt.field.side("foe").get("toxicspikes") == 2)
    ev = []
    A.after_hit(bt, b, "foe", a, "me", bt.move_of("TACKLE"), 20, 1.0, False, a.hp + 20, ev)
    chk("세 겹은 안 된다", bt.field.side("foe").get("toxicspikes") == 2)
    bt2, a2, b2 = duel("GLIMMORA", "SNORLAX", b_moves=("SWIFT",), a_ab="TOXICDEBRIS")
    ev = []
    A.after_hit(bt2, b2, "foe", a2, "me", bt2.move_of("SWIFT"), 20, 1.0, False, 99, ev)
    chk("특수 기술로는 안 깔린다", not bt2.field.side("foe").get("toxicspikes"))

    print("=== 속이기 ===")
    md = DEX.move("FAKEOUT")
    chk("자료의 풀죽음이 100%", md.get("flinch") == 100, md.get("flinch"))
    chk("자료의 우선도가 3", md.get("pri") == 3, md.get("pri"))
    bt, a, b = duel("HITMONTOP", "SNORLAX", a_moves=("FAKEOUT",))
    a.cond["outTurns"] = 1
    chk("나온 첫 턴에는 쓴다", not SM.first_turn_only(a, "FAKEOUT"))
    a.cond["outTurns"] = 2
    chk("둘째 턴부터는 실패", SM.first_turn_only(a, "FAKEOUT"))
    ev = []
    bt._use("me", a, b, "FAKEOUT", ev)
    chk("실패했다고 알린다", any("실패" in (e.get("text") or "") for e in ev),
        [e.get("text") for e in ev])
    chk("풀죽이지 못한다", not b.flinched)
    chk("만나자마자도 같다", SM.first_turn_only(a, "FIRSTIMPRESSION"))
    chk("다른 기술은 그대로", not SM.first_turn_only(a, "TACKLE"))

    print("=== 풀죽음 확률이 자료대로인가 ===")
    want = {"FAKEOUT": 100, "ROCKSLIDE": 30, "IRONHEAD": 30, "AIRSLASH": 30,
            "DARKPULSE": 20, "EXTRASENSORY": 10, "BITE": 30, "HEADBUTT": 30}
    bad = [(k, DEX.move(k).get("flinch"), v) for k, v in want.items()
           if DEX.move(k).get("flinch") != v]
    chk("여덟 기술의 풀죽음 확률이 본가와 같다", not bad, bad)
    bt, a, b = duel("SNORLAX", "SNORLAX", a_moves=("ROCKSLIDE",))
    b.maxhp = 99999                 # 한 방에 쓰러지면 풀죽을 겨를이 없다
    hits = 0
    for i in range(400):
        b.flinched = False
        b.hp = b.maxhp
        bt.rng = random.Random(i)
        bt._use("me", a, b, "ROCKSLIDE", [])
        hits += 1 if b.flinched else 0
    chk("스톤샤워가 30% 쯤 풀죽인다", 20 <= hits * 100 // 400 <= 40, hits / 4.0)

    print("=== 역린 ===")
    bt, a, b = duel("SALAMENCE", "SNORLAX", a_moves=("OUTRAGE",), seed=7)
    b.hp = b.maxhp = 9999
    turns = 0
    for t in range(6):
        bt._use("me", a, b, "OUTRAGE", [])
        turns += 1
        if not a.cond.get("rage"):
            break
    chk("두세 턴 이어진다", 2 <= turns <= 3, turns)
    chk("끝나면 혼란에 빠진다", a.cond.get("confused"), a.cond)
    bt, a, b = duel("SALAMENCE", "SNORLAX", a_moves=("OUTRAGE", "TACKLE"), seed=7)
    b.hp = b.maxhp = 9999
    bt._use("me", a, b, "OUTRAGE", [])
    chk("쓰는 중에는 잠긴다", a.cond.get("rage", {}).get("move") == "OUTRAGE")
    chk("다른 기술은 화면에서 막힌다",
        SM.restricted(bt, a, "TACKLE") and "멈출 수 없다" in SM.restricted(bt, a, "TACKLE"),
        SM.restricted(bt, a, "TACKLE"))
    chk("잠긴 기술을 알려준다", SM.locked_move(a) == "OUTRAGE", SM.locked_move(a))
    ev = []
    bt._use("me", a, b, "TACKLE", ev)          # 딴 것을 써도 역린이 나간다
    chk("딴 것을 골라도 역린이 나간다",
        any("역린" in (e.get("text") or "") for e in ev), [e.get("text") for e in ev][:3])
    chk("소란피기는 혼란이 없다", "UPROAR" in SM.LOCK_MOVES and "UPROAR" not in SM.RAGE_MOVES)

    # **잠긴 기술이 사슬묶기에 걸리면 잠금이 풀린다** (본가와 같다).
    # 안 풀면 잠금이 그 기술을 강요하고 사슬묶기가 그걸 막는다 - 다른 기술도
    # '쓰는 중이라 멈출 수 없다' 로 막혀서 쓸 게 하나도 없었고, 레이드의
    # 고르기는 "사슬묶기로 쓸 수 없다" 로 거절됐다(tools/sim_raid.py 가 터졌다).
    bt, a, b = duel("SALAMENCE", "SNORLAX", a_moves=("OUTRAGE", "TACKLE"), seed=7)
    b.hp = b.maxhp = 9999
    bt._use("me", a, b, "OUTRAGE", [])
    a.cond["disable"] = {"move": "OUTRAGE", "turns": 4}
    chk("잠긴 기술이 막히면 다른 기술은 풀린다", SM.restricted(bt, a, "TACKLE") is None,
        SM.restricted(bt, a, "TACKLE"))
    chk("쓸 수 있는 기술이 생긴다", "TACKLE" in bt.usable(a), bt.usable(a))
    chk("잠금이 풀린다", SM.locked_move(a, bt) is None and not a.cond.get("rage"),
        a.cond.get("rage"))
    before = b.hp
    ev = []
    bt._use("me", a, b, "TACKLE", ev)
    chk("풀린 뒤에는 고른 기술이 나간다", b.hp < before,
        [e.get("text") for e in ev][:3])
    bt, a, b = duel("CHARIZARD", "SNORLAX", a_moves=("FLY", "TACKLE"))
    b.hp = b.maxhp = 9999
    bt._use("me", a, b, "FLY", [])
    a.cond["disable"] = {"move": "FLY", "turns": 4}
    chk("숨은 채 막히면 도로 나온다",
        SM.locked_move(a, bt) is None and SM.hidden_spot(a) is None, a.cond)

    print("=== 두 턴에 걸쳐 쓰는 기술 ===")
    bt, a, b = duel("CHARIZARD", "SNORLAX", a_moves=("FLY", "TACKLE"))
    b.hp = b.maxhp = 9999
    before = b.hp
    ev = []
    bt._use("me", a, b, "FLY", ev)
    chk("첫 턴에는 안 맞는다", b.hp == before, b.hp)
    chk("날아올랐다고 알린다", any("날아올랐다" in (e.get("text") or "") for e in ev))
    chk("공중에 있다", SM.hidden_spot(a) == "fly", a.cond)
    chk("그동안 웬만한 기술은 안 닿는다", SM.hidden_from(a, "TACKLE"))
    chk("번개·회오리는 닿는다",
        not SM.hidden_from(a, "THUNDER") and not SM.hidden_from(a, "GUST"))
    chk("PP 는 첫 턴에 든다", a.pp["FLY"] == (DEX.move("FLY").get("pp") or 15) - 1,
        a.pp["FLY"])
    ev = []
    bt._use("me", a, b, "FLY", ev)
    chk("두 번째 턴에 맞는다", b.hp < before, b.hp)
    chk("내려왔다", not SM.hidden_spot(a))
    chk("PP 가 더 안 든다", a.pp["FLY"] == (DEX.move("FLY").get("pp") or 15) - 1,
        a.pp["FLY"])
    # 솔라빔은 햇빛이면 한 턴
    bt, a, b = duel("VENUSAUR", "SNORLAX", a_moves=("SOLARBEAM",))
    b.hp = b.maxhp = 9999
    bt.field.weather, bt.field.weather_turns = "sun", 5
    ev = []
    bt._use("me", a, b, "SOLARBEAM", ev)
    chk("햇빛이면 솔라빔이 한 턴에 나간다", b.hp < 9999, b.hp)
    # 파워허브
    bt, a, b = duel("VENUSAUR", "SNORLAX", a_moves=("SOLARBEAM",))
    b.hp = b.maxhp = 9999
    a.held = "POWERHERB"
    ev = []
    bt._use("me", a, b, "SOLARBEAM", ev)
    chk("파워허브로도 한 턴에", b.hp < 9999, b.hp)
    chk("파워허브는 없어진다", not a.held)

    print("=== 그 밖에 채운 특성 ===")
    # 무기력
    f = B.Fighter(DEX, mon("ARCHEOPS", ability="DEFEATIST"))
    f.ability_on = True
    full = f.stat("atk")
    f.hp = f.maxhp // 2
    chk("무기력: 절반 아래면 공격이 반", f.stat("atk") <= full // 2 + 1,
        (full, f.stat("atk")))
    # 투쟁심
    bt, a, b = duel("NIDOKING", "SNORLAX", a_ab="RIVALRY", a_gender="M", b_gender="M")
    same = A.attack_mult(a, b, bt.move_of("TACKLE"), "NORMAL", 1.0)
    bt2, a2, b2 = duel("NIDOKING", "SNORLAX", a_ab="RIVALRY", a_gender="M", b_gender="F")
    diff = A.attack_mult(a2, b2, bt2.move_of("TACKLE"), "NORMAL", 1.0)
    chk("투쟁심: 같은 성별이 세다", same > 1.0 > diff, (same, diff))
    # 원격
    f = B.Fighter(DEX, mon("DECIDUEYE", ability="LONGREACH"))
    f.ability_on = True
    chk("원격: 접촉기가 접촉이 아니다",
        A.is_contact(DEX.move("TACKLE")) and not A.is_contact(DEX.move("TACKLE"), f))
    # 서투름
    f = B.Fighter(DEX, mon("LOPUNNY", ability="KLUTZ"))
    f.ability_on = True
    f.held = "LEFTOVERS"
    chk("서투름: 도구를 못 쓴다", f.held is None)
    # 도주
    bt, a, b = duel("RATTATA", "SNORLAX", a_ab="RUNAWAY")
    a.base["spe"] = 1
    b.base["spe"] = 999
    chk("도주: 야생에게서 반드시 도망친다", bt.try_run())
    # 가두기
    bt, a, b = duel("SCIZOR", "MAGNEZONE", b_ab="MAGNETPULL")
    a.side_name, b.side_name = "me", "foe"
    chk("자력: 강철을 붙잡는다", SM.trapped(bt, a))
    bt, a, b = duel("SNORLAX", "MAGNEZONE", b_ab="MAGNETPULL")
    a.side_name, b.side_name = "me", "foe"
    chk("강철이 아니면 안 붙잡힌다", not SM.trapped(bt, a))
    bt, a, b = duel("SCIZOR", "GENGAR", b_ab="SHADOWTAG")
    a.side_name, b.side_name = "me", "foe"
    chk("그림자밟기는 타입을 안 가린다", SM.trapped(bt, a))
    bt, a, b = duel("GENGAR", "WOBBUFFET", b_ab="SHADOWTAG")
    a.side_name, b.side_name = "me", "foe"
    chk("고스트는 안 붙잡힌다", not SM.trapped(bt, a))
    # 습기
    bt, a, b = duel("SNORLAX", "POLIWAG", a_moves=("SELFDESTRUCT",), b_ab="DAMP")
    ev = []
    got = A.blocks(bt, a, "me", b, "foe", bt.move_of("SELFDESTRUCT"), "SELFDESTRUCT", ev)
    chk("습기: 자폭을 못 쓴다", got, ev)
    # 선제기 차단
    bt, a, b = duel("SNORLAX", "BRUXISH", a_moves=("QUICKATTACK",), b_ab="DAZZLING")
    ev = []
    got = A.blocks(bt, a, "me", b, "foe", bt.move_of("QUICKATTACK"), "QUICKATTACK", ev)
    chk("비비드바디: 선제 기술을 막는다", got, ev)
    ev = []
    got = A.blocks(bt, a, "me", b, "foe", bt.move_of("TACKLE"), "TACKLE", ev)
    chk("보통 기술은 그대로", not got)
    # 시간벌기
    bt, a, b = duel("SABLEYE", "SNORLAX", a_ab="STALL")
    a.base["spe"] = 999
    b.base["spe"] = 1
    chk("시간벌기: 빨라도 나중에 움직인다",
        bt._order("TACKLE", "TACKLE", []) == ["foe", "me"],
        bt._order("TACKLE", "TACKLE", []))
    # 나이트메어
    bt, a, b = duel("DARKRAI", "SNORLAX", a_ab="BADDREAMS")
    b.status = "sleep"
    b.sleep_turns = 3
    before = b.hp
    ev = []
    A.end_of_turn(bt, a, "me", ev)
    chk("나이트메어: 잠든 상대를 깎는다", b.hp < before, (before, b.hp))
    # 해감액
    bt, a, b = duel("SNORLAX", "TENTACRUEL", a_moves=("GIGADRAIN",), b_ab="LIQUIDOOZE")
    a.hp = a.maxhp // 2
    before = a.hp
    ev = []
    bt._use("me", a, b, "GIGADRAIN", ev)
    chk("해감액: 빨아들이면 오히려 깎인다", a.hp < before, (before, a.hp))

    print("=== 얼마나 채웠나 ===")
    import collections
    use = collections.Counter()
    for sp in DEX.species:
        for x in (sp.get("abil") or []):
            use[x] += 1
        if sp.get("hidden"):
            use[sp["hidden"]] += 1
    miss = [n for n in use if n not in A.IMPLEMENTED]
    chk("미구현이 55종 아래로", len(miss) < 55, len(miss))
    chk("게으름·독치장이 들어갔다",
        "TRUANT" in A.IMPLEMENTED and "TOXICDEBRIS" in A.IMPLEMENTED)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
