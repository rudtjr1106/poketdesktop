# -*- coding: utf-8 -*-
"""관장 지도 배치 검사. 창을 안 띄운다.

    python client/test_gym_map.py

## 무엇을 못 박나

  1. **먼 섬은 원래 있던 쪽으로 당겨진다.** 가장 가까운 빈 바다만 찾게
     두었더니 동해의 울릉군이 경북 서북쪽 구석에 들어갔다.
  2. 당겨 온 섬 상자가 본토나 다른 상자와 겹치지 않는다.
  3. 당겨서 지도가 실제로 커진다 (인천은 백령도 때문에 도심 구가 손톱만 했다).
  4. 옮길 필요 없는 시·도는 그대로다.
  5. 이름표 자리(center)가 그 시·군·구 안에 있다 - 울진군처럼 가늘고 긴
     곳에서 이름이 이웃 칸을 덮지 않게 자료를 만들 때 정했다.
  6. 이름 다듬기 (수원시팔달구 -> 수원시 팔달구 / 팔달구).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from poketdesktop import ui_gym as G                        # noqa: E402

OK = FAIL = 0
MAP = os.path.join(ROOT, "server", "data", "korea_map.json")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def fit_scale(ringsets, cw=640.0, ch=520.0):
    pts = [p for rs in ringsets for r in rs for p in r]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(cw / (max(xs) - min(xs)), ch / (max(ys) - min(ys)))


def main():
    with open(MAP, encoding="utf-8") as f:
        m = json.load(f)
    names = {s["code"]: s["name"] for s in m["sido"]}

    print("=== 먼 섬 당겨 그리기 ===")
    moved_sido = {}
    for code in names:
        regs = [d for d in m["sgg"] if d["sido"] == code]
        shifts, boxes, hidden = G.island_layout(regs)
        if not shifts:
            continue
        moved_sido[code] = (regs, shifts, boxes, hidden)
        # 옮기지 않은 고리 (본토와 가까운 섬)
        still = [(d, i, r) for d in regs for i, r in enumerate(d["rings"])
                 if (d["code"], i) not in shifts and (d["code"], i) not in hidden]
        hit = []
        for b in boxes:
            for d, i, r in still:
                # 상자 안에 본토의 점이 들어오면 겹친 것이다
                if any(b[0] < x < b[2] and b[1] < y < b[3] for x, y in r):
                    hit.append((d["name"], i))
                    break
        chk("%s: 당겨 온 상자가 본토와 안 겹친다" % names[code], not hit, hit[:3])
        pairs = [(a, b) for k, a in enumerate(boxes) for b in boxes[k + 1:] if G._overlap(a, b)]
        chk("%s: 상자끼리 안 겹친다" % names[code], not pairs, len(pairs))
        before = fit_scale([d["rings"] for d in regs])
        after_rings = [[[(p[0] + shifts.get((d["code"], i), (0, 0))[0],
                          p[1] + shifts.get((d["code"], i), (0, 0))[1]) for p in r]
                        for i, r in enumerate(d["rings"]) if (d["code"], i) not in hidden]
                       for d in regs] + [[[(b[0], b[1]), (b[2], b[3])] for b in boxes]]
        after = fit_scale(after_rings)
        print("       %s: 상자 %d · 숨긴 고리 %d · 배율 x%.2f"
              % (names[code], len(boxes), len(hidden), after / before))
        chk("%s: 지도가 커진다" % names[code], after > before * 1.05, (before, after))

    chk("옮기는 곳은 섬이 멀리 떨어진 시·도뿐",
        set(moved_sido) <= {"28", "12", "47", "50", "52"}, sorted(moved_sido))
    for must in ("28", "47", "50"):
        chk("%s 은(는) 당겨 그린다" % names[must], must in moved_sido, sorted(moved_sido))
    for plain in ("11", "41", "51", "48"):
        chk("%s 은(는) 그대로" % names[plain], plain not in moved_sido)

    # 울릉군은 경북 본토의 동쪽에 남아야 한다
    regs, shifts, boxes, hidden = moved_sido["47"]
    main_x = [p[0] for d in regs if d["name"] != "울릉군" for r in d["rings"] for p in r]
    ul = next(d for d in regs if d["name"] == "울릉군")
    ux = [p[0] + shifts.get((ul["code"], i), (0, 0))[0] for i, r in enumerate(ul["rings"]) for p in r]
    chk("울릉군은 옮겨도 경북 본토의 동쪽", min(ux) > (min(main_x) + max(main_x)) / 2,
        (min(ux), min(main_x), max(main_x)))
    # 추자도(제주시)는 제주 본섬의 북쪽
    regs, shifts, boxes, hidden = moved_sido["50"]
    jeju_y = [p[1] for d in regs for i, r in enumerate(d["rings"])
              if (d["code"], i) not in shifts for p in r]
    moved_y = [p[1] + shifts[(d["code"], i)][1] for d in regs for i, r in enumerate(d["rings"])
               if (d["code"], i) in shifts for p in r]
    chk("추자도는 옮겨도 제주 본섬의 북쪽", max(moved_y) < (min(jeju_y) + max(jeju_y)) / 2,
        (max(moved_y), min(jeju_y), max(jeju_y)))
    # 인천: 백령도 쪽은 서쪽
    regs, shifts, boxes, hidden = moved_sido["28"]
    city = [p[0] for d in regs if d["name"] not in ("옹진군", "강화군") for r in d["rings"] for p in r]
    ong = next(d for d in regs if d["name"] == "옹진군")
    far_x = [p[0] + shifts[(ong["code"], i)][0] for i, r in enumerate(ong["rings"])
             if (ong["code"], i) in shifts for p in r]
    chk("인천 옹진군의 먼 섬은 도심의 서쪽", far_x and max(far_x) < min(city), (max(far_x or [0]), min(city)))

    print("\n=== 이름표 자리 ===")
    out = [d["name"] for d in m["sgg"]
           if not G.inside([[v for p in r for v in p] for r in d["rings"]], d["center"][0], d["center"][1])]
    chk("256곳 모두 이름표 자리가 그 안에 있다", not out, out[:5])
    chk("이름표 반지름이 있다", all(d.get("labelR", 0) > 0 for d in m["sgg"]),
        [d["name"] for d in m["sgg"] if not d.get("labelR")][:5])
    uljin = next(d for d in m["sgg"] if d["name"] == "울진군")
    ring = [[v for p in r for v in p] for r in uljin["rings"]]
    cx, cy = uljin["center"]
    r = uljin["labelR"]
    chk("울진군 이름표 둘레가 울진군 안 (가늘고 긴 곳)",
        G.box_inside(ring, cx, cy, r * 1.2, r * 1.2), (cx, cy, r))

    print("\n=== 상자 안에 들어가나 ===")
    sq = [[0, 0, 10, 0, 10, 10, 0, 10]]
    chk("가운데 점은 안", G.inside(sq, 5, 5))
    chk("바깥 점은 밖", not G.inside(sq, 11, 5))
    chk("작은 상자는 들어간다", G.box_inside(sq, 5, 5, 8, 8))
    chk("큰 상자는 안 들어간다", not G.box_inside(sq, 5, 5, 12, 4))
    # ㄷ 자 모양 - 가운데가 비었다
    u = [[0, 0, 3, 0, 3, 7, 7, 7, 7, 0, 10, 0, 10, 10, 0, 10]]
    chk("오목한 곳을 건너는 상자는 안 들어간다", not G.box_inside(u, 5, 5, 8, 2))

    print("\n=== 이름 다듬기 ===")
    for raw, full, short in (("수원시팔달구", "수원시 팔달구", "팔달구"),
                             ("포항시남구", "포항시 남구", "남구"),
                             ("의정부시", "의정부시", "의정부시"),
                             ("중구", "중구", "중구"),
                             ("시흥시", "시흥시", "시흥시"),
                             ("강화군", "강화군", "강화군")):
        chk("%s -> %s" % (raw, full), G.sgg_name(raw) == full, G.sgg_name(raw))
        chk("%s -> %s (지도)" % (raw, short), G.map_label(raw) == short, G.map_label(raw))
    chk("일반구가 있는 곳은 전부 띄어 쓴다",
        all(" " in G.sgg_name(d["name"]) for d in m["sgg"]
            if d["name"].endswith("구") and "시" in d["name"][:-1] and len(d["name"]) > 3),
        [d["name"] for d in m["sgg"] if d["name"].endswith("구") and " " not in G.sgg_name(d["name"])
         and "시" in d["name"][:-1]][:5])

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
