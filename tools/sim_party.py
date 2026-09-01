# -*- coding: utf-8 -*-
"""파티전 엔진을 많이 돌려 보고 이상한 데가 없는지 본다.

    python tools/sim_party.py            1000판
    python tools/sim_party.py 200        200판

이 엔진 위에 서버와 화면 연출이 얹힌다. 여기서 안 돌면 그 위는 볼 것도
없으므로, 서버를 만들기 전에 이것부터 통과시킨다.

특히 **결정론**을 확인한다. 같은 시드로 두 번 돌려 로그가 한 글자도
다르지 않아야 한다. 이게 깨지면 '서버가 한 번 계산해서 저장하고 양쪽이
재생한다' 는 설계 전체가 무너진다.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import party_battle as PB          # noqa: E402
from common import pokelogic as P              # noqa: E402

DEX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "server", "data", "pokedex.json")


def team(dex, rng, n, lo, hi):
    out = []
    for _ in range(n):
        m = dex.roll_wild(lo, hi, rng)
        if m:
            out.append(m)
    return out


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    dex = P.Pokedex.load(DEX)
    rng = random.Random(20260901)

    ok = fail = 0

    def chk(name, cond, got=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print("  OK   %s" % name)
        else:
            fail += 1
            print("  FAIL %s   %s" % (name, got))

    print("=== 가장자리 ===")
    try:
        PB.PartyBattle(dex, [], team(dex, rng, 1, 20, 20))
        chk("빈 팀은 거부한다", False, "예외가 안 났다")
    except ValueError:
        chk("빈 팀은 거부한다", True)

    a1, b1 = team(dex, rng, 1, 20, 20), team(dex, rng, 1, 20, 20)
    r = PB.simulate(dex, a1, b1, seed=1)
    chk("1:1 도 돈다", r["winner"] in ("me", "foe", "draw"), r["winner"])

    a6, b6 = team(dex, rng, 6, 20, 20), team(dex, rng, 6, 20, 20)
    r = PB.simulate(dex, a6, b6, seed=2)
    chk("6:6 도 돈다", r["winner"] in ("me", "foe", "draw"), r["winner"])

    a1, b6 = team(dex, rng, 1, 5, 5), team(dex, rng, 6, 60, 60)
    r = PB.simulate(dex, a1, b6, seed=3)
    chk("1마리 대 6마리는 진다", r["winner"] == "foe", r["winner"])

    print("\n=== 결정론 ===")
    a, b = team(dex, rng, 6, 30, 40), team(dex, rng, 6, 30, 40)
    r1 = PB.simulate(dex, a, b, seed=12345)
    r2 = PB.simulate(dex, a, b, seed=12345)
    chk("같은 시드 -> 같은 로그",
        json.dumps(r1["events"], sort_keys=True) ==
        json.dumps(r2["events"], sort_keys=True),
        "%d vs %d 이벤트" % (len(r1["events"]), len(r2["events"])))
    r3 = PB.simulate(dex, a, b, seed=54321)
    chk("다른 시드 -> 다른 로그",
        json.dumps(r1["events"], sort_keys=True) !=
        json.dumps(r3["events"], sort_keys=True))

    print("\n=== 시점 뒤집기 ===")
    flipped = PB.flip_log(r1["events"])
    back = PB.flip_log(flipped)
    chk("두 번 뒤집으면 원래대로",
        json.dumps(back, sort_keys=True) == json.dumps(r1["events"], sort_keys=True))
    m1 = [e for e in r1["events"] if e["t"] == "match"][0]
    m2 = [e for e in flipped if e["t"] == "match"][0]
    chk("승자가 뒤집힌다",
        m2["winner"] == {"me": "foe", "foe": "me", "draw": "draw"}[m1["winner"]],
        "%s -> %s" % (m1["winner"], m2["winner"]))
    r_round = [e for e in r1["events"] if e["t"] == "round"][0]
    f_round = [e for e in flipped if e["t"] == "round"][0]
    chk("선수 소개도 뒤바뀐다",
        f_round["me"] == r_round["foe"] and f_round["foe"] == r_round["me"])

    print("\n=== %d판 돌리기 ===" % rounds)
    win = collections.Counter()
    turns = []
    sizes = []
    bad = []
    for i in range(rounds):
        n = rng.randint(1, 6)
        lo = rng.randint(5, 70)
        a = team(dex, rng, n, lo, lo + 5)
        b = team(dex, rng, n, lo, lo + 5)
        if not a or not b:
            continue
        try:
            r = PB.simulate(dex, a, b, seed=rng.randrange(1 << 30))
        except Exception as e:                          # noqa: BLE001
            bad.append("%s: %s" % (type(e).__name__, e))
            continue
        win[r["winner"]] += 1
        turns.append(r["turns"])
        sizes.append(len(json.dumps(r["events"], ensure_ascii=False)))

    chk("예외 없음", not bad, bad[:3])
    chk("무승부가 드물다 (5%% 미만)",
        win["draw"] <= max(1, len(turns) * 0.05), dict(win))
    chk("한쪽으로 치우치지 않는다",
        abs(win["me"] - win["foe"]) < len(turns) * 0.15, dict(win))
    if turns:
        turns.sort()
        sizes.sort()
        p50 = turns[len(turns) // 2]
        p95 = turns[int(len(turns) * 0.95)]
        print("\n  턴 수    중앙 %d  95%% %d  최대 %d" % (p50, p95, turns[-1]))
        print("  로그 크기 중앙 %.1f KB  95%% %.1f KB  최대 %.1f KB"
              % (sizes[len(sizes) // 2] / 1024.0,
                 sizes[int(len(sizes) * 0.95)] / 1024.0, sizes[-1] / 1024.0))
        print("  승패      %s" % dict(win))
        # 한 턴을 0.8초로 연출한다고 치면
        print("  연출 시간 중앙 %.0f초  95%% %.0f초 (턴당 0.8초 기준)"
              % (p50 * 0.8, p95 * 0.8))
        chk("95%% 판이 90초 안에 끝난다 (연출 기준)", p95 * 0.8 <= 90,
            "%.0f초" % (p95 * 0.8))
        chk("로그가 200KB 를 넘지 않는다", sizes[-1] < 200 * 1024,
            "%.1f KB" % (sizes[-1] / 1024.0))

    print("\n합계  OK %d  FAIL %d" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
