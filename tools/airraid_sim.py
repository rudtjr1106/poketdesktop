# -*- coding: utf-8 -*-
"""공습 승률 재기 (2.3.0) - 파티 크기 x 레벨 x 파티 세기마다 N판.

    python tools/airraid_sim.py [N]

파티 두 가지:
  야생급  그 레벨 야생 표에서 뽑은 것 (막 잡아 키운 파티)
  주력급  종족값 480~600 의 비전설 + 개체값 최고 (오래 키운 파티)
"""
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import airraid as AR                             # noqa: E402
from common import pokelogic as P                            # noqa: E402


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    with open(os.path.join(HERE, "..", "server", "data", "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    strong_pool = [s for s in dex.species if not s.get("legendary") and s.get("spawnable", True)
                   and 480 <= sum((s.get("base") or {}).values()) <= 600]
    rng = random.Random(1)
    t0 = time.time()
    rows = []
    for kind in ("야생급", "주력급"):
        for lv in (15, 40, 70, 100):
            for size in (1, 3, 6):
                win = turns = 0
                for i in range(n):
                    if kind == "야생급":
                        party = [dex.roll_wild(lv, lv, rng, max_bst=AR.bst_cap(lv), force_shiny=False)
                                 for _ in range(size)]
                    else:
                        party = [P.make_pokemon(rng.choice(strong_pool), lv, rng, force_shiny=False,
                                                ivs=dict((k, 31) for k in ("hp", "atk", "def", "spa", "spd", "spe")))
                                 for _ in range(size)]
                    foes = AR.roll_raiders(dex, [m["level"] for m in party], rng)
                    out = AR.AirRaid(dex, party, foes, seed=rng.randrange(1 << 30)).run()
                    win += out["result"] == "win"
                    turns += out["turns"]
                rows.append((kind, lv, size, win * 100.0 / n, turns / float(n)))
                print("%s Lv%-3d 파티 %d: 승률 %5.1f%%  전역 턴 %.1f" % rows[-1], flush=True)
    print("%d판 x %d 칸, %.1f초" % (n, len(rows), time.time() - t0))


if __name__ == "__main__":
    main()
