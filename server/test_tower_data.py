# -*- coding: utf-8 -*-
"""배틀타워 층 자료 검사 (시즌 7) — server/data/tower.json 이 약속을 지키는가.

    python server/test_tower_data.py

서버도 DB 도 안 쓴다. 자료는 tools/build_tower.py 가 낸다 - 손으로 고치지 않는다. 못 박는 것:

  1. 1~50층이 빠짐없이 있고, 레벨 · 마릿수 · 관문/층주 · AI · 노력치가 층 번호로 정해진다.
       레벨 = min(100, 28 + 2 x 층) · 1~4층 3마리, 5~9층 4, 10~20층 5, 21층~ 6
       5의 배수는 관문(gate), 10의 배수는 층주(boss) · 1~40층 관장 AI, 41~50층 길드전 AI
  2. 층주 다섯은 프런티어 브레인 (나리 · 다슬 · 하인즈 · 리라 · 종수). 한 사람은 한 번만 나온다.
  3. **상대 팀은 같은 종 · 같은 도구가 겹쳐도 된다** (사용자 결정) - 그런 층이 실제로 다섯 곳 넘게 있다.
  4. 여러 포켓몬을 쓰게 되도록 150종 넘게 나온다.
  5. 보상은 층마다 처음 한 번: 돈 합계 390,000원, 귀한 것의 수, 알은 50층 하나. **칭호는 없다.**
  6. 자료가 스스로의 규칙(build_tower.check: 기술 · 특성 · 도구 · 노력치 · 깃발)을 지키고, 명세에서 다시 내도 같다.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def size_of(n):
    return 3 if n <= 4 else 4 if n <= 9 else 5 if n <= 20 else 6


def held(f):
    return [m["held"] for m in f["trainer"]["team"] if m["held"]]


def main():
    with open(os.path.join(HERE, "data", "tower.json"), encoding="utf-8") as fh:
        T = json.load(fh)
    import build_tower as BT
    F = T["floors"]

    print("=== 층 번호로 정해지는 것 ===")
    chk("50층, 1부터 빠짐없이", [f["floor"] for f in F] == list(range(1, 51)), [f["floor"] for f in F])
    chk("레벨 식", all(m["level"] == min(100, 28 + 2 * f["floor"]) for f in F for m in f["trainer"]["team"]))
    chk("트레이너 레벨 = 상대 레벨 (AI 의 솜씨)", all(f["trainer"]["level"] == min(100, 28 + 2 * f["floor"]) for f in F))
    chk("마릿수", all(len(f["trainer"]["team"]) == size_of(f["floor"]) for f in F),
        [(f["floor"], len(f["trainer"]["team"])) for f in F if len(f["trainer"]["team"]) != size_of(f["floor"])])
    chk("관문 · 층주", all(f["kind"] == ("boss" if n % 10 == 0 else "gate" if n % 5 == 0 else "normal")
                       for f in F for n in [f["floor"]]))
    chk("AI", all(f["trainer"]["ai"] == ("gym" if f["floor"] <= 40 else "war") for f in F))
    chk("트레이너 id", all(f["trainer"]["id"] == "tower-%d" % f["floor"] for f in F))

    print("\n=== 사람 ===")
    chk("층주는 프런티어 브레인", [F[n - 1]["trainer"]["sprite"] for n in (10, 20, 30, 40, 50)]
        == ["greta", "lucy", "tucker", "anabel", "palmer"], [F[n - 1]["trainer"]["sprite"] for n in (10, 20, 30, 40, 50)])
    chk("50층은 타워타이쿤 종수", (F[49]["trainer"]["name"], F[49]["trainer"]["role"]) == ("종수", "타워타이쿤"),
        (F[49]["trainer"]["name"], F[49]["trainer"]["role"]))
    chk("한 사람은 한 번만", len({f["trainer"]["sprite"] for f in F}) == 50,
        [k for k, n in collections.Counter(f["trainer"]["sprite"] for f in F).items() if n > 1])
    chk("층 이름이 다 다르다", len({f["name"] for f in F}) == 50)

    print("\n=== 팀 ===")
    species = {m["species"] for f in F for m in f["trainer"]["team"]}
    chk("150종 이상", len(species) >= 150, len(species))
    dup_sp = [f["floor"] for f in F if len({m["species"] for m in f["trainer"]["team"]}) < len(f["trainer"]["team"])]
    dup_it = [f["floor"] for f in F if len(set(held(f))) < len(held(f))]
    chk("같은 종이 겹친 층 5곳 이상", len(dup_sp) >= 5, dup_sp)
    chk("같은 도구가 겹친 층 5곳 이상", len(dup_it) >= 5, dup_it)
    chk("1구역 보통 층은 도구가 없다", all(not held(f) for f in F if f["floor"] <= 10 and f["kind"] == "normal"),
        [f["floor"] for f in F if f["floor"] <= 10 and f["kind"] == "normal" and held(f)])
    chk("1구역은 노력치 0 · 무보정", all(not any(m["evs"].values()) and m["nature"] == "HARDY"
                                 for f in F if f["floor"] <= 10 for m in f["trainer"]["team"]))
    # 노력치는 구역마다 는다: 0 -> 252(주 능력) -> 378(둘째 능력에 126) -> 378 -> 510. 3 · 4구역을 510 으로 채우면
    # Lv.100 인 36~40층이 5구역 초입보다 어려운 벽이 된다 (11/24 sim_tower: 4~40% -> 노력치를 줄이면 50~92%).
    chk("3 · 4구역의 노력치는 378 (252 + 126)", all(sorted(m["evs"].values())[-2:] == [126, 252] and sum(m["evs"].values()) == 378
                                          for f in F if 21 <= f["floor"] <= 40 for m in f["trainer"]["team"]),
        [(f["floor"], m["species"], sum(m["evs"].values())) for f in F if 21 <= f["floor"] <= 40
         for m in f["trainer"]["team"] if sum(m["evs"].values()) != 378][:5])
    chk("5구역은 노력치를 다 준다 (510)", all(sum(m["evs"].values()) == 510
                                     for f in F if f["floor"] >= 41 for m in f["trainer"]["team"]),
        [(f["floor"], m["species"]) for f in F if f["floor"] >= 41 for m in f["trainer"]["team"]
         if sum(m["evs"].values()) != 510][:5])
    chk("개체값은 전부 31", all(m["iv"] == 31 for f in F for m in f["trainer"]["team"]))
    chk("능력치 배율을 안 쓴다", all(not m.get("boost") for f in F for m in f["trainer"]["team"]))
    megas = [f["floor"] for f in F if f["trainer"]["keystone"]]
    chk("메가진화는 35층부터", megas and min(megas) >= 35, megas)
    chk("Z기술은 40층부터", min(f["floor"] for f in F if f["trainer"]["zring"]) >= 40)
    chk("테라스탈은 45층부터", min(f["floor"] for f in F if f["trainer"]["orb"]) >= 45)

    print("\n=== 보상 ===")
    chk("돈 합계 390,000", sum(f["reward"]["money"] for f in F) == 390000, sum(f["reward"]["money"] for f in F))
    chk("보통 층의 돈은 구역마다 2,000씩", all(f["reward"]["money"] == 2000 * ((f["floor"] - 1) // 10 + 1)
                                    for f in F if f["kind"] == "normal"))
    count = collections.Counter()
    for f in F:
        for iid, n in f["reward"]["items"]:
            count[iid] += n
    chk("귀한 보상 수", (count["GOLDBOTTLECAP"], count["RANKTICKETTM"], count["RANKTICKETTMTYPE"],
                    count["MASTERBALL"], count["SHINYCANDY"]) == (3, 2, 2, 1, 1), dict(count))
    chk("층마다 도구가 하나는 있다", all(f["reward"]["items"] for f in F))
    chk("알은 50층 하나", [f["floor"] for f in F if f["reward"].get("egg")] == [50]
        and F[49]["reward"]["egg"] == "legendary")
    chk("칭호 보상이 없다", all("title" not in f["reward"] for f in F))

    print("\n=== 자료의 규칙 ===")
    errs = BT.check(T)
    chk("자료가 스스로의 규칙을 지킨다", errs == [], errs[:5])
    chk("파일이 명세와 같다 (손으로 고치지 않았다)", BT.build() == T)

    print("\n=== 엔진에 올려 본다 (같은 종 · 같은 도구가 겹친 팀도 판이 된다) ===")
    broke = []
    for f in F:
        try:
            play_a_little(f)
        except Exception as e:                                # noqa: BLE001
            broke.append((f["floor"], repr(e)[:120]))
    chk("50층 전부 판이 열리고 세 턴이 돌고 저장했다 되살아난다", broke == [], broke[:5])

    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


def play_a_little(f):
    """그 층의 트레이너와 판을 열어 세 턴을 두고, 저장본으로 되살려 본다 (서버가 턴마다 하는 일)."""
    import random

    from common import pokelogic as P
    from common import trainer_battle as TB
    dex = play_a_little.dex = getattr(play_a_little, "dex", None) or P.Pokedex.load(
        os.path.join(HERE, "data", "pokedex.json"))
    rng = random.Random(f["floor"])
    party = []
    for species in ("GARCHOMP", "METAGROSS", "GYARADOS", "TOGEKISS", "MAMOSWINE", "ROTOM"):
        m = P.make_pokemon(dex.get(species), f["trainer"]["level"], rng, shiny_rate=10 ** 9)
        m["held"] = None
        party.append(m)
    tb = TB.TrainerBattle(dex, party, f["trainer"], rng)
    tb.start()
    for _turn in range(3):
        if tb.over:
            break
        if tb.need_switch:
            tb.act("switch", tb.valid_switches()[0])
        else:
            tb.act("move", tb.bt.usable(tb.me)[0])
        tb = TB.TrainerBattle.load(dex, json.loads(json.dumps(tb.dump())))
    team = f["trainer"]["team"]
    assert [x.mon["species"] for x in tb.foe_team] == [m["species"] for m in team], "상대 팀이 자료와 다르다"
    # 메가스톤을 쥔 포켓몬이 없는 층에서 엔진이 도구를 메가스톤으로 바꿔 놓지 않았다 (noMega)
    for x, m in zip(tb.foe_team, team):
        if not f["trainer"]["keystone"] and x.alive() and x.mon.get("held") != m["held"]:
            used_up = x.mon.get("held") is None                # 열매 · 기합의띠처럼 쓰고 사라진 것은 괜찮다
            assert used_up, "%s 의 도구가 %s -> %s" % (m["species"], m["held"], x.mon.get("held"))


if __name__ == "__main__":
    sys.exit(main())
