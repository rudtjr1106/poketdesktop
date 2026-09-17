# -*- coding: utf-8 -*-
"""헤비볼 — 몸무게로 배율이 정해지나. 서버를 띄우지 않는다.

    python server/test_heavy_ball.py

사용자 제보: 몸무게가 반영이 안 되는 것 같다(헤비볼). 헤비볼이 도감의 "weight"
칸을 봤는데, 그 칸은 도감을 만들 때 **야생 등장 가중치**로 덮여 있었다. 잠만보
(460kg)도 무게 4.5kg 으로 읽혀서 늘 가벼운 쪽(-20)이었다. 진짜 몸무게는 "kg" 칸이다.

원작(7세대 이후) 헤비볼: 100kg 미만 -20, 200kg 미만 +0, 300kg 미만 +20, 그 이상 +30.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-heavy-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import deps, items                                # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def main():
    dex = deps.dex()
    ball = next(i for i, it in items.data()["items"].items()
                if (it.get("effect") or {}).get("cond") == "heavy")
    print("=== 헤비볼 (%s)" % ball)

    def mult(species):
        return items.ball_bonus(ball, dex, {"species": species, "level": 30})

    def expect(species, add):
        rate = max(1, dex.get(species).get("catch", 45))
        return max(0.1, (rate + add) / float(rate))

    for species, add, why in (("PIKACHU", -20, "6kg - 가볍다"),
                              ("ONIX", 20, "210kg"),
                              ("SNORLAX", 30, "460kg - 무겁다"),
                              ("RHYDON", 0, "120kg")):
        sp = dex.get(species)
        chk("%s %s: 배율 %.2f" % (sp["kr"], why, expect(species, add)),
            abs(mult(species) - expect(species, add)) < 1e-9, (sp.get("kg"), mult(species)))
    chk("잠만보가 피카츄보다 잘 잡힌다", mult("SNORLAX") > mult("PIKACHU"))
    note = items.ball_why(ball, dex, {"species": "SNORLAX", "level": 30}, mult("SNORLAX"))
    chk("설명에 진짜 몸무게가 나온다 (460.0kg)", "460.0kg" in str(note), note)

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
