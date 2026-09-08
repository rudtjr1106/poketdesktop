# -*- coding: utf-8 -*-
"""도감이 한국어로 되어 있는가.

찌리비의 특성 '풍력발전' 을 눌렀더니 설명이 영어로 나왔다. PokeAPI 의
`ability_flavor_text.csv` 에 **9세대 특성 47개는 한국어 줄이 아예 없어서**
영어가 그대로 화면에 실렸다.

손으로 적어 넣었으니(common/ability_kr.py), 도감을 다시 만들 때 그게
빠지면 여기서 걸린다. 네트워크를 안 쓴다 - 파일만 본다.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common.ability_kr import DESC as HAND                  # noqa: E402
from common.move_kr import DESC as MOVE_HAND                # noqa: E402

DEX = os.environ.get("POKET_POKEDEX",
                     os.path.join(ROOT, "server", "data", "pokedex.json"))

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def hangul(s):
    return bool(re.search(r"[가-힣]", s or ""))


def main():
    d = json.load(io.open(DEX, encoding="utf-8"))
    ab, mv = d["abilities"], d["moves"]

    # 종이 실제로 쓰는 특성만 본다. 아무도 안 쓰는 것까지 볼 이유가 없다.
    used = set()
    for sp in d["species"]:
        used.update(sp.get("abil") or [])
        if sp.get("hidden"):
            used.add(sp["hidden"])

    print("=== 특성 이름 ===")
    noname = [k for k in used if not hangul((ab.get(k) or {}).get("kr"))]
    chk("쓰이는 특성 %d개가 전부 한국어 이름" % len(used), not noname,
        sorted(noname)[:8])

    print("\n=== 특성 설명 ===")
    eng = [k for k in used
           if (ab.get(k) or {}).get("desc")
           and not hangul(ab[k]["desc"])]
    chk("영어로 남은 설명이 없다", not eng, sorted(eng)[:8])
    blank = [k for k in used if not ((ab.get(k) or {}).get("desc") or "").strip()]
    chk("설명이 빈 것도 없다", not blank, sorted(blank)[:8])

    # 찌리비가 이 문제를 처음 드러낸 종이다. 이름으로 못 박아 둔다.
    w = ab.get("WINDPOWER") or {}
    chk("찌리비의 풍력발전에 한국어 설명이 있다", hangul(w.get("desc")),
        (w.get("desc") or "")[:40])

    print("\n=== 손으로 적은 것이 실제로 쓰이는가 ===")
    stale = [k for k in HAND if k not in ab]
    chk("도감에 없는 키를 적어 두지 않았다", not stale, stale[:8])
    unused = [k for k in HAND if k in ab and k not in used]
    # 안 쓰는 것을 적어 둬도 해롭지는 않다. 세어만 둔다.
    print("     (어느 종도 안 쓰는 것 %d개 — 해롭지는 않다)" % len(unused))
    for k, v in HAND.items():
        if not hangul(v):
            chk("%s 설명이 한국어" % k, False, v[:30])
    chk("손으로 적은 %d개가 전부 한국어" % len(HAND),
        all(hangul(v) for v in HAND.values()))
    chk("문장이 마침표로 끝난다",
        all(v.rstrip().endswith(".") for v in HAND.values()),
        [k for k, v in HAND.items() if not v.rstrip().endswith(".")][:5])

    print("\n=== 기술 ===")
    mnoname = [k for k, v in mv.items() if not hangul(v.get("kr"))]
    chk("기술 %d개가 전부 한국어 이름" % len(mv), not mnoname,
        sorted(mnoname)[:8])
    meng = [k for k, v in mv.items()
            if v.get("desc") and not hangul(v["desc"])]
    chk("영어로 남은 기술 설명이 없다", not meng, sorted(meng)[:8])
    mblank = [k for k, v in mv.items() if not (v.get("desc") or "").strip()]
    chk("설명이 빈 기술도 없다", not mblank, sorted(mblank)[:8])

    stale = [k for k in MOVE_HAND if k not in mv]
    chk("도감에 없는 기술 키를 적어 두지 않았다", not stale, stale[:8])
    chk("손으로 적은 기술 %d개가 전부 한국어" % len(MOVE_HAND),
        all(hangul(v) for v in MOVE_HAND.values()),
        [k for k, v in MOVE_HAND.items() if not hangul(v)][:5])
    chk("기술 문장이 마침표로 끝난다",
        all(v.rstrip().endswith(".") for v in MOVE_HAND.values()),
        [k for k, v in MOVE_HAND.items()
         if not v.rstrip().endswith(".")][:5])
    # 설명이 이름을 그대로 되풀이하는 것은 번역을 빠뜨린 표시다
    lazy = [k for k, v in MOVE_HAND.items()
            if v.strip().rstrip(".") == (mv.get(k) or {}).get("kr", "")]
    chk("이름만 적어 둔 것이 없다", not lazy, lazy[:5])

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
