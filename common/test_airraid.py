# -*- coding: utf-8 -*-
"""공습 계산 (2.3.0, common/airraid.py) - 뽑기 · 이긴 쪽이 다음 상대 · 같은 시드 = 같은 판.

    python common/test_airraid.py
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import airraid as AR                             # noqa: E402
from common import pokelogic as P                            # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def load_dex():
    with open(os.path.join(HERE, "..", "server", "data", "pokedex.json"), encoding="utf-8") as f:
        return P.Pokedex(json.load(f))


def mons(dex, keys, lv, seed=1):
    rng = random.Random(seed)
    return [P.make_pokemon(dex.get(k), lv, rng, force_shiny=False) for k in keys]


def t_뽑기(dex):
    print("[뽑기]")
    rng = random.Random(3)
    sizes = set(AR.raid_size(n, rng) - n for n in range(1, 7) for _ in range(40))
    chk("마리 수 = 파티 + 2 또는 3", sizes == {2, 3}, sizes)
    lv = [AR.raid_level(50, rng, n_party=4) for _ in range(200)]
    chk("레벨 = 파티 평균 - 2~5 (파티 4마리 이상)", min(lv) == 45 and max(lv) == 48, (min(lv), max(lv)))
    small = dict((n, sorted(set(50 - AR.raid_level(50, rng, n_party=n) for _ in range(300)))) for n in (1, 2, 3))
    chk("파티가 작을수록 더 낮게 (혼자는 서너 마리를 차례로 - 승률을 고르게: 1 -12~15 · 2 -7~10 · 3 -4~7)",
        small[1] == list(range(12, 16)) and small[2] == list(range(7, 11)) and small[3] == list(range(4, 8)), small)
    chk("레벨은 최저(2) 아래로 안 간다", AR.raid_level(3, rng, lo=2) == 2)
    foes = AR.roll_raiders(dex, [40, 50, 60, 50], random.Random(9))
    chk("공습 포켓몬: 파티 4 -> 6~7마리 · 레벨 평균-5 ~ 평균-2 · 이로치 없음 · 전설 없음",
        len(foes) in (6, 7) and all(45 <= m["level"] <= 48 for m in foes)
        and not any(m.get("shiny") for m in foes)
        and not any((dex.get(m["species"]) or {}).get("legendary") for m in foes),
        [(m["species"], m["level"]) for m in foes])
    chk("종족값 상한 = 야생과 같은 식 (330 + 8 x 레벨)", AR.bst_cap(10) == 410 and AR.bst_cap(50) == 730)
    chk("파티가 없으면 공습도 없다", AR.roll_raiders(dex, [], random.Random(1)) == [])


def t_싸움(dex):
    print("[싸움]")
    mine = mons(dex, ["MEWTWO"], 100)
    foes = mons(dex, ["RATTATA", "PIDGEY", "CATERPIE"], 5, seed=2)
    out = AR.AirRaid(dex, mine, foes, seed=7).run()
    ev = out["events"]
    pairs = [e for e in ev if e["t"] == "pair"]
    chk("센 한 마리: 셋을 차례로 이긴다", out["result"] == "win" and [p["fi"] for p in pairs] == [0, 1, 2]
        and all(p["mi"] == 0 for p in pairs), (out["result"], [(p["mi"], p["fi"]) for p in pairs]))
    ends = [e for e in ev if e["t"] == "end"]
    chk("판마다 끝(end) 하나 · 이긴 쪽 me", len(ends) == 3 and all(e["win"] == "me" for e in ends), ends)
    chk("쓰러뜨린 기록(kos): [공습 i, 내 i]", out["kos"] == [[0, 0], [1, 0], [2, 0]], out["kos"])
    chk("맨 앞 teams · 맨 끝 raid", ev[0]["t"] == "teams" and ev[-1]["t"] == "raid"
        and ev[-1]["result"] == "win" and len(ev[0]["foe"]) == 3, (ev[0]["t"], ev[-1]))
    # 체력이 이어진다: 두 번째 짝의 내 체력 = 첫 판 끝의 체력
    mine2 = mons(dex, ["PIKACHU"], 30)
    foes2 = mons(dex, ["RATTATA", "RATTATA", "RATTATA"], 25, seed=5)
    out2 = AR.AirRaid(dex, mine2, foes2, seed=11).run()
    p2 = [e for e in out2["events"] if e["t"] == "pair"]
    chk("이긴 내 포켓몬은 남은 체력으로 다음 상대 (체력이 가득 차지 않는다)",
        len(p2) >= 2 and p2[1]["me"]["hp"] < p2[1]["me"]["maxhp"], [(p["me"]["hp"], p["me"]["maxhp"]) for p in p2])
    # 같은 시드 = 같은 판
    a = AR.AirRaid(dex, mons(dex, ["PIKACHU", "BULBASAUR"], 30), mons(dex, ["RATTATA"] * 4, 26, 3), seed=5).run()
    b = AR.AirRaid(dex, mons(dex, ["PIKACHU", "BULBASAUR"], 30), mons(dex, ["RATTATA"] * 4, 26, 3), seed=5).run()
    chk("같은 시드 = 같은 로그", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
    # 처음엔 동시에: 첫 turn 전에 짝이 min(내, 공습) 개
    first_turn = next(i for i, e in enumerate(a["events"]) if e["t"] == "turn")
    chk("처음엔 내 포켓몬마다 한 마리씩 동시에 (첫 턴 전 짝 2개)",
        sum(1 for e in a["events"][:first_turn] if e["t"] == "pair") == 2)
    chk("이벤트마다 판 번호(d)가 붙는다 (teams · turn · raid 빼고)",
        all("d" in e for e in a["events"] if e["t"] not in ("teams", "turn", "raid")))
    # 진 경우: 약한 내 하나 vs 센 공습 - 이긴 공습 포켓몬이 쉬고 있는 내 포켓몬에게 간다
    weak = mons(dex, ["CATERPIE", "WEEDLE"], 5)
    strong = mons(dex, ["MACHAMP", "GYARADOS", "ARCANINE"], 60, seed=8)
    out3 = AR.AirRaid(dex, weak, strong, seed=3).run()
    chk("지면 result lose · 내 쪽 다 쓰러짐", out3["result"] == "lose"
        and out3["events"][-1]["result"] == "lose", out3["result"])
    p3 = [e for e in out3["events"] if e["t"] == "pair"]
    chk("공습 쪽도 이기면 다음 상대에게 간다 (내 포켓몬 둘을 공습 포켓몬 둘이 맡았다 - 셋째는 기다리다 쉬는 상대가 없다)",
        len(p3) == 2 and sorted(p["mi"] for p in p3) == [0, 1], [(p["mi"], p["fi"]) for p in p3])
    # 둘 다 쓰러지지 않으면 끝나지 않는 판도 상한에서 멈춘다
    out4 = AR.AirRaid(dex, mons(dex, ["CHANSEY"], 50), mons(dex, ["BLISSEY"], 50, 4), seed=1, turn_cap=30).run()
    chk("전역 턴 상한에서 멈추고 결과를 낸다", out4["turns"] <= 30 and out4["result"] in ("win", "lose"), out4["turns"])


def t_끌어내기(dex):
    print("[울부짖기 · 드래곤테일 (독립 검토 Important)]")
    rng = random.Random(5)

    def mk(sp, lv, moves):
        m = P.make_pokemon(dex.get(sp), lv, rng, force_shiny=False)
        m["moves"] = moves
        return m
    out = AR.AirRaid(dex, [mk("DRAGONITE", 50, ["DRAGONTAIL"])], [mk("SNORLAX", 50, ["TACKLE"]) for _ in range(3)],
                     seed=1).run()
    flee = [e for e in out["events"] if e["t"] == "flee"]
    ends = [e for e in out["events"] if e["t"] == "end"]
    first_end_turn = None
    turn = 0
    for e in out["events"]:
        if e["t"] == "turn":
            turn = e["n"]
        if e["t"] == "end" and first_end_turn is None:
            first_end_turn = turn
    chk("드래곤테일: 바꿀 동료가 없으니 데미지만 (날려 보내 짝을 끝내지 않는다)", not flee and first_end_turn > 1,
        (len(flee), first_end_turn))
    chk("  짝 끝은 누가 실제로 쓰러져서만 (faint 사건과 짝이 맞다)",
        all(any(f["t"] == "faint" and f.get("d") == e["d"] for f in out["events"]) for e in ends))
    out2 = AR.AirRaid(dex, [mk("MACHAMP", 50, ["CLOSECOMBAT"])], [mk("PIDGEOT", 30, ["WHIRLWIND"]) for _ in range(4)],
                      seed=2).run()
    chk("날려버리기를 쓰는 공습 포켓몬도 짝을 한 턴에 못 끝낸다 (실패)", not any(e["t"] == "flee" for e in out2["events"])
        and out2["result"] == "win", out2["result"])


def main():
    dex = load_dex()
    t_뽑기(dex)
    t_싸움(dex)
    t_끌어내기(dex)
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
