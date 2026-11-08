# -*- coding: utf-8 -*-
"""양궁 작전 값 맞추기 - 같은 실력 20명(안정 · 승부수 반반)에서 상위 8시드 · 금메달의 승부수 비율.

    python3 tools/olympic_archery_sim.py                 지금 값 (common/olympics_rounds.ARCHERY_TACTICS)
    python3 tools/olympic_archery_sim.py search          승부수 실수 확률 · 가산을 바꿔 가며

목표: 둘 다 40~60% (11/08 설계 - 한 작전이 늘 이기지 않게).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import olympics_rounds as R                        # noqa: E402

if __name__ == "__main__":
    if sys.argv[1:] == ["search"]:
        base = dict(R.ARCHERY_TACTICS["bold"])
        for plus in (0.02, 0.03):
            for slip in (0.0, 0.01, 0.02, 0.03, 0.04):
                for sd in (0.06, 0.08):
                    R.ARCHERY_TACTICS["bold"] = {"plus": plus, "sd": sd, "slip": slip}
                    print("plus %.2f sd %.2f slip %.2f  ->  %s" % (plus, sd, slip, R.archery_tactic_share(200, 3)))
        R.ARCHERY_TACTICS["bold"] = base
    else:
        print(R.ARCHERY_TACTICS, R.archery_tactic_share(400, 5))
