# -*- coding: utf-8 -*-
"""테라스탈 엔진 검사 (2.5.0) — 본가 스칼렛·바이올렛의 규칙.

    python common/test_tera.py

  1. 테라오브가 있으면 턴 처음에 테라스탈한다. 타입이 **테라 타입 하나**가 된다.
  2. **한 판에 한 번.** 쓰러지거나 판이 끝날 때까지 가고, 저장했다 불러와도 그대로다.
  3. 자속: 테라 타입 기술 1.5배, 원래 타입과 같으면 2배(적응력 2.25배). 원래 타입의 자속은 남는다.
  4. 테라 타입 기술의 위력 60 미만은 60 으로 (연속기·선공기는 빼고).
  5. 테라버스트는 테라 타입이 된다.
  6. 받는 상성이 테라 타입으로 바뀐다.
  7. 메가진화한 포켓몬은 테라스탈하지 못하고, 테라스탈한 포켓몬은 메가진화하지 못한다.
  8. 자동 배틀의 AI 는 이득일 때만 알아서 쓰고, 같은 시드면 로그가 같다.
  9. 테라오브가 없으면 아무 일도 없다 - 그때의 로그는 예전과 한 글자도 안 다르다.
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import battle as B                               # noqa: E402
from common import party_battle as PB                        # noqa: E402
from common import pokelogic as P                            # noqa: E402
from common import tera as TR                                # noqa: E402

DEX = P.Pokedex.load(os.path.join(os.path.dirname(HERE), "server", "data", "pokedex.json"))
OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mon(species, moves=("TACKLE",), tera=None, held=None, level=50, ability=None):
    m = P.make_pokemon(DEX.get(species), level, random.Random(1), shiny_rate=10 ** 9)
    m["ivs"] = dict((s, 31) for s in P.STATS)
    m["evs"] = dict((s, 0) for s in P.STATS)
    m["nature"] = "HARDY"
    m["moves"] = list(moves)
    m["held"] = held
    m["nickname"] = None
    if tera:
        # 2.5.1: 테라 타입 = 지닌 테라피스 (지니는 도구). tera= 는 그 타입 테라피스를 지니게 한다
        assert not held, "테라피스와 다른 도구를 같이 지닐 수 없다"
        m["held"] = tera + "TERASHARD"
    if ability:
        m["ability"] = ability
    return m


def duel(a, b, orb=True, abil=True, seed=3, keystone=False):
    fa, fb = B.Fighter(DEX, a), B.Fighter(DEX, b)
    fa.ability_on = fb.ability_on = abil
    bt = B.Battle(DEX, fa, fb, random.Random(seed), ai="trainer")
    bt.kind = "gym"
    bt.tera_orb = {"me": orb, "foe": False}
    bt.keystone = {"me": keystone, "foe": False}
    return bt, fa, fb


def dmg(bt, user, target, key):
    """난수 없는(가장 큰 난수, 급소 없음) 데미지."""
    return B.damage(DEX, bt.move_of(key), user, target, B.MAX_RNG, crit=False)[0]


def main():
    print("=== 테라 타입 ===")
    chk("타입은 열여덟 (스텔라는 없다)", len(TR.TYPES) == 18 and "STELLAR" not in TR.TYPES)
    chk("테라피스를 안 지녔으면 테라 타입이 없다 (11/16 사용자 - 처음 판은 그 종의 첫째 타입)",
        TR.type_of(DEX, mon("CHARIZARD")) is None and TR.type_of(DEX, mon("CLEFABLE")) is None)
    chk("다른 도구를 지녔거나 2.5.0 에 정해 둔 칸(tera)만 있으면 없다",
        TR.type_of(DEX, mon("CHARIZARD", held="LIFEORB")) is None
        and TR.type_of(DEX, dict(mon("CHARIZARD"), tera="FIRE")) is None)
    chk("테라피스 18종 = 타입 열여덟", len(TR.SHARDS) == 18 and TR.shard_type("FAIRYTERASHARD") == "FAIRY"
        and TR.shard_type("LIFEORB") is None and TR.shard_type(None) is None)
    chk("지닌 테라피스의 타입 (자기 타입과 같아도 - 페어리 포켓몬에 페어리)",
        TR.type_of(DEX, mon("CHARIZARD", tera="GRASS")) == "GRASS"
        and TR.type_of(DEX, mon("CLEFABLE", tera="FAIRY")) == "FAIRY")
    chk("없는 타입은 버린다 (없음)", TR.type_of(DEX, mon("CHARIZARD", tera="STELLAR")) is None)
    bt, a, b = duel(mon("CLEFABLE", ("MOONBLAST",)), mon("SNORLAX"))
    chk("정하지 않은 포켓몬은 테라오브가 있어도 테라스탈 못 한다 (단추가 없다)", bt.can_tera("me") is None, bt.can_tera("me"))
    bt, a, b = duel(mon("CLEFABLE", ("MOONBLAST",), tera="FAIRY"), mon("SNORLAX"))
    chk("페어리 테라피스를 쓴 픽시는 테라스탈 · 페어리", bt.can_tera("me") == "FAIRY", bt.can_tera("me"))

    print("\n=== 바뀐다 ===")
    bt, a, b = duel(mon("CHARIZARD", ("FLAMETHROWER",), tera="GRASS"), mon("SNORLAX"))
    chk("하기 전에는 원래 타입", a.types() == ["FIRE", "FLYING"] and a.tera is None, a.types())
    chk("can_tera 가 타입을 준다", bt.can_tera("me") == "GRASS", bt.can_tera("me"))
    ev = bt.take_turn("FLAMETHROWER", tera=True)
    tv = [e for e in ev if e.get("t") == "tera"]
    chk("테라스탈 사건이 난다", len(tv) == 1 and tv[0]["type"] == "GRASS" and tv[0]["typeKr"] == "풀",
        [e.get("t") for e in ev][:5])
    chk("문구", "풀 타입으로 테라스탈했다" in tv[0]["text"], tv[0]["text"])
    chk("기술보다 먼저", ev.index(tv[0]) < next(i for i, e in enumerate(ev) if e.get("t") == "move"))
    chk("타입이 풀 하나", a.types() == ["GRASS"] and a.tera == "GRASS", a.types())
    chk("원래 타입은 따로 기억한다", a.orig_types() == ["FIRE", "FLYING"], a.orig_types())

    print("\n=== 한 판에 한 번 ===")
    ev2 = bt.take_turn("FLAMETHROWER", tera=True)
    chk("두 번째 턴에는 사건이 없다", not any(e.get("t") == "tera" for e in ev2))
    chk("can_tera 도 None", bt.can_tera("me") is None)
    chk("테라는 그대로다", a.tera == "GRASS")

    print("\n=== 안 되는 경우 ===")
    bt2, a2, _ = duel(mon("CHARIZARD", tera="GRASS"), mon("SNORLAX"), orb=False)
    bt2.take_turn("TACKLE", tera=True)
    chk("테라오브가 없으면 안 된다", a2.tera is None and bt2.can_tera("me") is None)
    bt3, a3, _ = duel(mon("CHARIZARD", tera="GRASS"), mon("SNORLAX"))
    bt3.take_turn("TACKLE")
    chk("누르지 않으면 안 한다", a3.tera is None)

    print("\n=== 자속 ===")
    chk("배율표: 테라 타입이 새 타입이면 1.5", TR.stab(["FIRE", "FLYING"], "GRASS", "GRASS") == 1.5)
    chk("배율표: 테라 타입이 원래 타입이면 2", TR.stab(["FIRE", "FLYING"], "FIRE", "FIRE") == 2.0)
    chk("배율표: 원래 타입의 자속은 남는다", TR.stab(["FIRE", "FLYING"], "GRASS", "FIRE") == 1.5)
    chk("배율표: 상관없는 타입은 1", TR.stab(["FIRE", "FLYING"], "GRASS", "WATER") == 1.0)
    chk("배율표: 적응력은 테라 타입에만 (2 / 2.25)",
        TR.stab(["FIRE"], "GRASS", "GRASS", 2.0) == 2.0 and TR.stab(["FIRE"], "FIRE", "FIRE", 2.0) == 2.25
        and TR.stab(["FIRE"], "GRASS", "FIRE", 2.0) == 1.5)
    # 실제 데미지로: 리자몽(불꽃/비행)이 화염방사를 잠만보에게
    bt, a, b = duel(mon("CHARIZARD", ("FLAMETHROWER", "ENERGYBALL", "SURF"), tera="FIRE"), mon("SNORLAX"))
    fire0, grass0, surf0 = dmg(bt, a, b, "FLAMETHROWER"), dmg(bt, a, b, "ENERGYBALL"), dmg(bt, a, b, "SURF")
    a.tera = "FIRE"
    fire1 = dmg(bt, a, b, "FLAMETHROWER")
    chk("같은 타입 테라: 화염방사가 1.5배 -> 2배 (4/3 배)", abs(fire1 / float(fire0) - 4 / 3.0) < 0.02,
        (fire0, fire1))
    a.tera = "GRASS"
    chk("다른 타입 테라: 풀 기술이 1.5배가 된다", abs(dmg(bt, a, b, "ENERGYBALL") / float(grass0) - 1.5) < 0.02,
        (grass0, dmg(bt, a, b, "ENERGYBALL")))
    chk("그래도 화염방사의 자속은 그대로다", dmg(bt, a, b, "FLAMETHROWER") == fire0,
        (fire0, dmg(bt, a, b, "FLAMETHROWER")))
    chk("상관없는 타입은 그대로", dmg(bt, a, b, "SURF") == surf0)
    a.tera = None

    print("\n=== 위력 60 보정 ===")
    low = {"power": 40, "hits": [1, 1], "pri": 0}
    chk("테라 타입 기술 40 -> 60", TR.floor_power(40, low, "FIRE", "FIRE") == 60)
    chk("다른 타입 기술은 그대로", TR.floor_power(40, low, "WATER", "FIRE") == 40)
    chk("60 이상은 그대로", TR.floor_power(90, low, "FIRE", "FIRE") == 90)
    chk("선공기는 그대로", TR.floor_power(40, dict(low, pri=1), "FIRE", "FIRE") == 40)
    chk("연속기는 그대로", TR.floor_power(25, dict(low, hits=[2, 5]), "FIRE", "FIRE") == 25)
    chk("테라스탈 안 했으면 그대로", TR.floor_power(40, low, "FIRE", None) == 40)
    bt, a, b = duel(mon("CHARIZARD", ("EMBER", "FLAMETHROWER"), tera="FIRE"), mon("SNORLAX"))
    ember0, flame0 = dmg(bt, a, b, "EMBER"), dmg(bt, a, b, "FLAMETHROWER")
    a.tera = "FIRE"
    ember1, flame1 = dmg(bt, a, b, "EMBER"), dmg(bt, a, b, "FLAMETHROWER")
    # 불꽃세례 40 -> 60 (1.5배) x 자속 1.5 -> 2 (4/3 배) = 2배쯤. 화염방사(90)는 4/3 배뿐.
    chk("불꽃세례(위력 40)는 위력까지 올라 2배쯤", 1.85 < ember1 / float(ember0) < 2.15, (ember0, ember1))
    chk("화염방사(위력 90)는 자속만", abs(flame1 / float(flame0) - 4 / 3.0) < 0.02, (flame0, flame1))

    print("\n=== 테라버스트 ===")
    bt, a, b = duel(mon("SNORLAX", ("TERABLAST",), tera="FIGHTING"), mon("TYRANITAR"))
    chk("안 했으면 노말", B.typed(bt.move_of("TERABLAST"), a, b)["type"] == "NORMAL")
    n0 = dmg(bt, a, b, "TERABLAST")
    a.tera = "FIGHTING"
    chk("테라스탈하면 테라 타입", B.typed(bt.move_of("TERABLAST"), a, b)["type"] == "FIGHTING")
    n1 = dmg(bt, a, b, "TERABLAST")
    # 마기라스(바위/악): 노말 0.5배 -> 격투 4배. 자속 1.5(노말) -> 1.5(테라 격투). 8배.
    chk("마기라스에게 반감이던 것이 4배가 된다", 7.0 < n1 / float(n0) < 9.0, (n0, n1))

    # 테라버스트의 타입은 흡수 특성도 본다 (전에는 데미지를 셀 때만 바뀌어 축전이 못 받았다)
    bt, a, b = duel(mon("PORYGONZ", ("TERABLAST",), tera="ELECTRIC"), mon("LANTURN", ("TACKLE",), ability="VOLTABSORB"))
    b.hp = b.maxhp // 2
    a.tera = "ELECTRIC"
    ev = []
    bt._use("me", a, b, "TERABLAST", ev)
    mv = [e for e in ev if e.get("t") == "move"]
    chk("전기 테라버스트는 축전이 받는다 (데미지 없이 회복)", not any(e.get("t") == "hit" for e in ev)
        and b.hp > b.maxhp // 2, ([e.get("t") for e in ev], b.hp, b.maxhp))
    chk("  기술 사건의 타입도 테라 타입", mv and mv[0]["moveType"] == "ELECTRIC", mv[:1])

    print("\n=== 받는 상성 ===")
    bt, a, b = duel(mon("CHARIZARD", ("TACKLE",), tera="WATER"), mon("GOLEM", ("ROCKSLIDE", "THUNDERPUNCH")))
    rock0, elec0 = dmg(bt, b, a, "ROCKSLIDE"), dmg(bt, b, a, "THUNDERPUNCH")
    a.tera = "WATER"
    rock1, elec1 = dmg(bt, b, a, "ROCKSLIDE"), dmg(bt, b, a, "THUNDERPUNCH")
    chk("바위 4배 약점이 사라진다 (물은 바위를 보통으로 받는다)", abs(rock0 / float(rock1) - 4.0) < 0.2,
        (rock0, rock1))
    chk("전기는 그대로 2배 (비행 -> 물)", abs(elec1 / float(elec0) - 1.0) < 0.05, (elec0, elec1))
    # 상태이상 면역도 타입을 따른다: 독 타입으로 테라스탈하면 독에 안 걸린다
    bt, a, b = duel(mon("SNORLAX", ("TACKLE",), tera="POISON"), mon("ARBOK", ("TOXIC",)))
    a.tera = "POISON"
    ev = []
    bt._use("foe", b, a, "TOXIC", ev)
    chk("독 타입으로 테라스탈하면 맹독에 안 걸린다", a.status is None, (a.status, [e.get("text") for e in ev]))

    print("\n=== 타입을 바꾸는 것들 ===")
    bt, a, b = duel(mon("CHARIZARD", ("TACKLE",), tera="FIRE"), mon("BLASTOISE", ("SOAK", "FORESTSCURSE")))
    a.tera = "FIRE"
    ev = []
    bt._use("foe", b, a, "SOAK", ev)
    chk("테라스탈한 포켓몬에게 물붓기는 실패한다", a.types() == ["FIRE"]
        and not any("물 타입이 되었다" in (e.get("text") or "") for e in ev)
        and any("실패" in (e.get("text") or "") for e in ev), [e.get("text") for e in ev])
    ev = []
    bt._use("foe", b, a, "FORESTSCURSE", ev)
    chk("숲의저주도 실패한다", not a.cond.get("extraType") and any("실패" in (e.get("text") or "") for e in ev),
        [e.get("text") for e in ev])
    bt, a, b = duel(mon("GRENINJA", ("ICEBEAM", "SURF"), tera="WATER", ability="PROTEAN"), mon("SNORLAX", ("TACKLE",)))
    a.tera = "WATER"
    ev = []
    bt._use("me", a, b, "ICEBEAM", ev)
    chk("테라스탈한 동안 변환자재는 안 돈다 (한 번뿐인 기회도 그대로)", a.types() == ["WATER"]
        and not a.ab.get("protean") and not any("타입이 되었다" in (e.get("text") or "") for e in ev),
        (a.ab, [e.get("text") for e in ev]))

    print("\n=== 메가진화와 ===")
    # 2.5.1: 테라피스는 지닌 도구 칸을 쓰므로 메가스톤과 같이 못 지닌다 - 스톤 없이 메가진화하는 레쿠쟈(화룡점정)로 본다
    bt, a, b = duel(mon("CHARIZARD", ("FLAMETHROWER",), held="CHARIZARDITEX"), mon("SNORLAX"), keystone=True)
    chk("메가스톤을 지닌 포켓몬은 테라피스가 없어 테라스탈 단추가 없다",
        bt.can_tera("me") is None and bt.can_mega("me") is not None, (bt.can_tera("me"), bt.can_mega("me")))
    bt, a, b = duel(mon("RAYQUAZA", ("DRAGONASCENT",), tera="FLYING"), mon("SNORLAX"), keystone=True)
    chk("레쿠쟈는 테라피스를 지녀도 화룡점정으로 메가진화할 수 있다 (둘 다 열려 있다)",
        bt.can_tera("me") == "FLYING" and bt.can_mega("me") is not None, (bt.can_tera("me"), bt.can_mega("me")))
    ev = bt.take_turn("DRAGONASCENT", mega=True, tera=True)
    chk("같은 턴에 둘 다 누르면 메가진화만 된다",
        a.mega and a.tera is None and not any(e.get("t") == "tera" for e in ev), (a.mega, a.tera))
    chk("메가진화한 뒤에는 테라스탈할 수 없다", bt.can_tera("me") is None)
    bt, a, b = duel(mon("RAYQUAZA", ("DRAGONASCENT",), tera="FLYING"), mon("SNORLAX"), keystone=True)
    bt.take_turn("DRAGONASCENT", tera=True)
    chk("테라스탈한 뒤에는 메가진화할 수 없다", a.tera == "FLYING" and bt.can_mega("me") is None)
    bt.take_turn("DRAGONASCENT", mega=True)
    chk("눌러도 안 바뀐다", a.mega is None)
    bt, a, b = duel(mon("CLEFABLE", ("MOONBLAST",), tera="FAIRY"), mon("SNORLAX", ("KNOCKOFF",)))
    ev = []
    bt._use("foe", b, a, "KNOCKOFF", ev)
    chk("탁쳐서떨구기로도 테라피스는 안 떨어진다 (Z크리스탈과 같다)",
        a.held == "FAIRYTERASHARD" and bt.can_tera("me") == "FAIRY", (a.held, [e.get("text") for e in ev]))

    print("\n=== 저장·교체 ===")
    bt, a, b = duel(mon("CHARIZARD", ("FLAMETHROWER",), tera="GRASS"), mon("SNORLAX"))
    bt.take_turn("FLAMETHROWER", tera=True)
    vol = json.loads(json.dumps(a.volatile()))
    chk("저장할 것에 테라가 들어 있다", vol.get("tera") == "GRASS", vol)
    a2 = B.Fighter(DEX, a.mon)
    a2.load_volatile(vol)
    chk("불러오면 그대로다", a2.tera == "GRASS" and a2.types() == ["GRASS"])
    a.clear_volatile()
    chk("물러나도 안 풀린다 (교체)", a.tera == "GRASS" and a.types() == ["GRASS"])
    b0 = B.Fighter(DEX, mon("SNORLAX"))
    chk("안 한 포켓몬은 저장할 것이 없다", (b0.volatile() or {}).get("tera") is None)

    print("\n=== 자동 배틀 ===")
    bare_a = [mon("CHARIZARD", ("FLAMETHROWER", "AIRSLASH")), mon("GYARADOS", ("WATERFALL", "ICEFANG")),
              mon("SNORLAX", ("BODYSLAM", "EARTHQUAKE"))]
    bare_b = [mon("VENUSAUR", ("ENERGYBALL", "SLUDGEBOMB")), mon("GOLEM", ("ROCKSLIDE", "EARTHQUAKE")),
              mon("ALAKAZAM", ("PSYCHIC", "SHADOWBALL"))]
    both = {"me": True, "foe": True}
    none_set = PB.simulate(DEX, bare_a, bare_b, seed=77, tera_orb=both)
    chk("테라 타입을 정한 포켓몬이 없으면 테라오브가 있어도 AI 가 안 쓴다 (11/16)",
        not any(e.get("t") == "tera" for e in none_set["events"]))
    # 아래부터는 모두 테라피스로 첫째 타입을 정해 둔 팀 (2.5.0 처음 판의 기본값과 같게 - 로그 비교가 그대로 맞는다)
    team_a = [mon("CHARIZARD", ("FLAMETHROWER", "AIRSLASH"), tera="FIRE"),
              mon("GYARADOS", ("WATERFALL", "ICEFANG"), tera="WATER"),
              mon("SNORLAX", ("BODYSLAM", "EARTHQUAKE"), tera="NORMAL")]
    team_b = [mon("VENUSAUR", ("ENERGYBALL", "SLUDGEBOMB"), tera="GRASS"),
              mon("GOLEM", ("ROCKSLIDE", "EARTHQUAKE"), tera="ROCK"),
              mon("ALAKAZAM", ("PSYCHIC", "SHADOWBALL"), tera="PSYCHIC")]
    plain = PB.simulate(DEX, team_a, team_b, seed=77)
    chk("테라오브가 없으면 테라 사건이 없다", not any(e.get("t") == "tera" for e in plain["events"]))
    r1 = PB.simulate(DEX, team_a, team_b, seed=77, tera_orb=both)
    r2 = PB.simulate(DEX, team_a, team_b, seed=77, tera_orb=both)
    teras = [e for e in r1["events"] if e.get("t") == "tera"]
    chk("테라오브가 있으면 AI 가 쓴다", 1 <= len(teras) <= 2, [(e["who"], e["type"]) for e in teras])
    chk("한 쪽에 한 번씩만", len(set(e["who"] for e in teras)) == len(teras), [e["who"] for e in teras])
    chk("같은 시드면 로그가 한 글자도 안 다르다", json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True))
    after = False
    seen = False
    for e in r1["events"]:
        if e.get("t") == "tera" and e["who"] == teras[0]["who"]:
            after = True
        elif after and e.get("t") == "round":
            view = e[teras[0]["who"]]
            if view.get("name") == teras[0]["name"]:
                seen = view.get("tera") == teras[0]["type"]
    chk("테라스탈한 선수가 다시 링에 서면 명단에 타입이 실린다 (또는 다시 안 섰다)",
        seen or not any(e.get("t") == "round" and e[teras[0]["who"]].get("name") == teras[0]["name"]
                        for e in r1["events"][r1["events"].index(teras[0]):]))
    one = PB.simulate(DEX, team_a, team_b, seed=77, tera_orb={"me": True, "foe": False})
    chk("한쪽만 가졌으면 그쪽만", all(e["who"] == "me" for e in one["events"] if e.get("t") == "tera"))
    # AI 는 이득일 때만 쓴다
    bt, a, b = duel(mon("SNORLAX", ("BODYSLAM",), tera="BUG"), mon("ALAKAZAM", ("PSYCHIC",)))
    chk("주는 것도 받는 것도 그대로면 AI 는 안 쓴다 (벌레: 사이코키네시스는 그대로, 몸통박치기도 그대로)",
        bt._tera_worth("me") is False)
    bt, a, b = duel(mon("SNORLAX", ("BODYSLAM",), tera="BUG"), mon("MACHAMP", ("CROSSCHOP",)))
    chk("크게 맞을 것이 확 줄면 쓴다 (벌레: 격투 2배 -> 반감)",
        dmg(bt, b, a, "CROSSCHOP") >= a.hp * 0.5 and bt._tera_worth("me") is True,
        (dmg(bt, b, a, "CROSSCHOP"), a.hp))
    bt, a, b = duel(mon("CHARIZARD", ("FLAMETHROWER",), tera="FIRE"), mon("SNORLAX", ("TACKLE",)))
    chk("가장 센 기술이 4/3 배가 되면 쓴다", bt._tera_worth("me") is True)
    bt, a, b = duel(mon("CHARIZARD", ("FLAMETHROWER",), tera="GRASS"), mon("GOLEM", ("EARTHQUAKE",)))
    chk("얻는 것 없이 약점만 생기면 안 쓴다 (풀: 화염방사는 그대로, 지진은 무효 -> 반감으로 맞게 된다)",
        bt._tera_worth("me") is False)
    rs = random.Random(5)
    before = rs.getstate()
    bt.rng = rs
    bt._tera_worth("me")
    chk("AI 판단은 난수를 안 쓴다", rs.getstate() == before)

    more()

    print("\n" + "=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


def more():
    """2.5.0 에서 다시 넣으며 더한 것."""
    from common import raid_battle as RB
    from common import trainer_battle as TB
    print("\n=== 위력이 상대에 따라 정해지는 기술 (2.5.0) ===")
    chk("로킥처럼 도감 위력 0 인 기술은 60 으로 안 올린다",
        TR.floor_power(20, {"power": 0}, "FIGHTING", "FIGHTING", variable=True) == 20)
    chk("  보통 기술은 올린다", TR.floor_power(40, {"power": 40}, "POISON", "POISON") == 60)
    bt, a, b = duel(mon("SNORLAX", ("LOWKICK",), tera="FIGHTING"), mon("PIKACHU"))
    plain = dmg(bt, a, b, "LOWKICK")
    a.tera = "FIGHTING"
    tera = dmg(bt, a, b, "LOWKICK")
    chk("  가벼운 상대에게 쓴 로킥: 자속 1.5배만 붙고 60 보정은 없다 (%d -> %d)" % (plain, tera),
        plain < tera <= plain * 1.6, (plain, tera))

    print("\n=== 변색 · 멀티타입 (2.5.0) ===")
    bt, a, b = duel(mon("SNORLAX", ("SURF",)), mon("KECLEON", ("TACKLE",), tera="NORMAL", ability="COLORCHANGE"))
    b.tera = "NORMAL"
    ev = bt.take_turn("SURF")
    chk("테라스탈한 켈리몬은 변색으로 타입이 안 바뀐다", b.types() == ["NORMAL"]
        and not any("타입이 되었다" in (e.get("text") or "") for e in ev), [e.get("text") for e in ev][:6])

    print("\n=== 랭크 (양쪽 길드전 AI, 시즌 5 규칙) (2.5.0) ===")
    team_a = [mon("CHARIZARD", ("FLAMETHROWER", "AIRSLASH"), tera="FIRE"),
              mon("SNORLAX", ("BODYSLAM", "EARTHQUAKE"), tera="GHOST"), mon("GENGAR", ("SHADOWBALL",))]
    team_b = [mon("MACHAMP", ("CROSSCHOP", "KNOCKOFF"), tera="FIGHTING"),
              mon("GYARADOS", ("WATERFALL",), tera="WATER"), mon("ALAKAZAM", ("PSYCHIC",))]
    both = {"me": True, "foe": True}
    r1 = PB.simulate(DEX, team_a, team_b, seed=21, tera_orb=both, war_ai=True)
    r2 = PB.simulate(DEX, team_a, team_b, seed=21, tera_orb=both, war_ai=True)
    teras = [(e["who"], e["type"]) for e in r1["events"] if e.get("t") == "tera"]
    chk("같은 시드면 같은 판 (테라스탈 때까지)", json.dumps(r1["events"], sort_keys=True)
        == json.dumps(r2["events"], sort_keys=True), len(r1["events"]))
    chk("한 쪽에 많아야 한 번", all(sum(1 for w, _t in teras if w == s) <= 1 for s in ("me", "foe")), teras)
    chk("  셈이 터진 수가 없다 (거울 판이 테라 상태를 옮겨도)", not r1.get("warStats", {}).get("error"),
        r1.get("warStats"))
    r0 = PB.simulate(DEX, team_a, team_b, seed=21, war_ai=True)
    chk("테라오브가 없으면 테라스탈이 없다", not any(e.get("t") == "tera" for e in r0["events"]))
    # 11/17: 한쪽이 바꾸는 턴(_switch_turn)에도 기술을 쓰는 쪽은 테라스탈한다 (전에는 이 길에 tera_step 이 없었다)
    pb = PB.PartyBattle(DEX, [mon("CHARIZARD", ("FLAMETHROWER",), tera="FIRE"), mon("SNORLAX", ("TACKLE",))],
                        [mon("SNORLAX", ("TACKLE",)), mon("BLISSEY", ("TACKLE",))], seed=5, tera_orb=both, war_ai=True)
    bt = pb._round_battle()
    pb.moved_out = {"me": False, "foe": False}
    ev = pb._switch_turn(bt, {"me": (None, "FLAMETHROWER"), "foe": (1, None)})
    tv = [(e["who"], e["type"]) for e in ev if e.get("t") == "tera"]
    chk("랭크: 상대가 바꾸는 턴에도 기술을 쓰는 쪽은 테라스탈한다 (바꾼 쪽은 안 한다)", tv == [("me", "FIRE")],
        (tv, [e.get("t") for e in ev][:12]))

    print("\n=== 관장 · 레이드 판 저장 (2.5.0) ===")
    trainer = {"id": "t", "name": "시험", "role": "관장", "sprite": "x", "level": 50,
               "team": [{"species": "SNORLAX", "level": 50, "moves": ["TACKLE"]}]}
    tb = TB.TrainerBattle(DEX, [mon("CHARIZARD", ("FLAMETHROWER",), tera="GRASS")], trainer, random.Random(4))
    tb.tera_orb["me"] = True
    tb.start()
    tb.act("move", "FLAMETHROWER", tera=True)
    back = TB.TrainerBattle.load(DEX, json.loads(json.dumps(tb.dump())))
    chk("관장 판: 테라스탈한 채로 저장 · 불러오기", back.me.tera == "GRASS" and "me" in back.tera_done
        and back.view()["me"]["team"][0]["tera"] == "GRASS", (back.me.tera, sorted(back.tera_done)))
    chk("  관장 쪽은 쓰지 않는다", not back.tera_orb["foe"] and not back.bt.auto_tera["foe"])
    # 11/17: 테라오브를 가진 상대(길드전 방어 AI 와 같은 auto_tera)가 바꿔 넣은 포켓몬은 그 턴에 테라스탈하지 않는다
    orb_trainer = dict(trainer, orb=True, team=[
        {"species": "SNORLAX", "level": 50, "moves": ["TACKLE"]},
        {"species": "CHARIZARD", "level": 50, "moves": ["FLAMETHROWER"], "held": "FIRETERASHARD"}])
    tb = TB.TrainerBattle(DEX, [mon("SNORLAX", ("TACKLE",))], orb_trainer, random.Random(4))
    tb.start()
    tb._forced = ("switch", 1)
    ev = tb.act("move", "TACKLE")
    chk("상대가 바꿔 넣은 턴에는 테라스탈하지 않는다 (메가진화와 같다)",
        tb.foe.species["internal"] == "CHARIZARD" and tb.foe.tera is None
        and not any(e.get("t") == "tera" for e in ev), (tb.foe.tera, [e.get("t") for e in ev][:12]))
    tb._forced = ("move", "FLAMETHROWER")
    ev = tb.act("move", "TACKLE")
    chk("  다음 턴, 기술을 쓸 때는 테라스탈한다", tb.foe.tera == "FIRE"
        and any(e.get("t") == "tera" and e.get("who") == "foe" for e in ev), (tb.foe.tera, [e.get("t") for e in ev][:12]))
    players = [(1, "가", [RB.leveled(mon("CHARIZARD", ("FLAMETHROWER",), tera="GRASS"), 50)]),
               (2, "나", [RB.leveled(mon("SNORLAX", ("TACKLE",)), 50)])]
    rb = RB.RaidBattle(DEX, mon("MEWTWO", ("PSYCHIC",), level=60), players, hp_mult=40, max_rounds=5,
                       rng=random.Random(5))
    rb.players[0].tera_orb["me"] = True
    rb.start()
    rb.choose(0, "move", "FLAMETHROWER", tera=True)
    rb.choose(1, *rb.auto_choice(1))
    ev = rb.resolve()
    chk("레이드: 고른 사람만 테라스탈한다", [e.get("p") for e in ev if e.get("t") == "tera"] == [0]
        and rb.players[0].mon.tera == "GRASS" and not rb.players[1].mon.tera,
        [(e.get("t"), e.get("p")) for e in ev if e.get("t") == "tera"])
    rb2 = RB.RaidBattle.load(DEX, json.loads(json.dumps(rb.dump())))
    chk("  저장했다 불러와도 그대로", rb2.players[0].mon.tera == "GRASS" and "me" in rb2.players[0].tera_done)


if __name__ == "__main__":
    sys.exit(main())
