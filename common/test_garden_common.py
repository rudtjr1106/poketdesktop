# -*- coding: utf-8 -*-
"""열매 텃밭 (시즌 7) 의 순수 계산 (common/garden.py).

    python common/test_garden_common.py

못 박는 것:

  1. 지닌 열매 47종(common/held.py 의 KR 가운데 *BERRY)이 정확히 한 묶음씩 (4 · 8 · 16시간). 로셀열매는 8시간,
     혼란 회복 열매 다섯은 HEAL 표에 있어도 8시간. 노력치 열매(items.json cat 'ev')는 어느 묶음에도 없다.
  2. 단계는 자라는 시간의 1/3씩 (1 새싹 · 2 줄기 · 3 꽃), 다 지나면 4 익음. 경계에서 정확히 바뀐다.
     next_change 는 다음 단계까지 남은 초 (익었으면 None).
  3. 열매 수 = 기본(4h 1 · 8h 2 · 16h 3) + 물 준 단계 수(0~3) + 친구 보너스(0~1).
  4. 풀 타입 빠르기: 한 마리당 10%, 셋에서 멈춘다 (30%). 배율(GARDEN_SCALE)을 곱한다.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import garden as G                              # noqa: E402
from common import held as H                                # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def test_groups_cover_47():
    print("[묶음 - 47종이 정확히 한 묶음씩]")
    berries = set(k for k in H.KR if k.endswith("BERRY"))
    chk("held.KR 의 지닌 열매는 47종", len(berries) == 47, len(berries))
    chk("묶음 표의 열매 = 지닌 열매 47종 (빠진 것도 남는 것도 없다)", set(G.GROUP) == berries,
        sorted(set(G.GROUP) ^ berries))
    chk("묶음은 4 · 8 · 16 뿐", set(G.GROUP.values()) == {4, 8, 16}, set(G.GROUP.values()))
    with open(os.path.join(HERE, "..", "server", "data", "items.json"), encoding="utf-8") as f:
        cat = json.load(f)["items"]
    held_cat = set(k for k, v in cat.items() if v.get("cat") == "held" and k.endswith("BERRY"))
    chk("items.json 의 cat 'held' 열매와도 같다", held_cat == set(G.GROUP), sorted(held_cat ^ set(G.GROUP)))
    ev = sorted(k for k, v in cat.items() if k.endswith("BERRY") and v.get("cat") == "ev")
    chk("노력치 열매(cat 'ev')는 어느 묶음에도 없다", ev and not [k for k in ev if k in G.GROUP], ev)
    chk("로셀열매(페어리 반감)는 8시간", G.GROUP.get("ROSELIBERRY") == 8, G.GROUP.get("ROSELIBERRY"))
    confuse = ("FIGYBERRY", "WIKIBERRY", "MAGOBERRY", "AGUAVBERRY", "IAPAPABERRY")
    chk("혼란 회복 열매 다섯은 8시간 (HEAL 표에 있어도)", all(G.GROUP[k] == 8 for k in confuse),
        [(k, G.GROUP.get(k)) for k in confuse])
    chk("오랭 · 자뭉은 4시간", G.GROUP["ORANBERRY"] == 4 and G.GROUP["SITRUSBERRY"] == 4)
    chk("상태이상 회복 여섯 · 과사 · 시몬은 4시간",
        all(G.GROUP[k] == 4 for k in list(H.CURE_BERRY) + ["LEPPABERRY", "PERSIMBERRY"]))
    chk("반감 18종은 8시간", len(H.RESIST_BERRY) == 18 and all(G.GROUP[k] == 8 for k in H.RESIST_BERRY))
    sixteen = list(H.PINCH_BERRY) + list(H.HIT_CAT_BERRY) + ["CUSTAPBERRY", "ENIGMABERRY", "JABOCABERRY", "ROWAPBERRY"]
    chk("핀치 · 맞으면 오르는 · 애슈 · 의문 · 자보 · 애터는 16시간", all(G.GROUP[k] == 16 for k in sixteen),
        [(k, G.GROUP.get(k)) for k in sixteen if G.GROUP.get(k) != 16])
    n = dict((g, sum(1 for v in G.GROUP.values() if v == g)) for g in (4, 8, 16))
    chk("묶음 크기 10 · 23 · 14", n == {4: 10, 8: 23, 16: 14}, n)
    chk("BASE = 4h 1 · 8h 2 · 16h 3", G.BASE == {4: 1, 8: 2, 16: 3}, G.BASE)


def test_stage_split():
    print("[단계 - 1/3씩, 경계]")
    g = 300                                  # 1/3 = 100초
    chk("0초: 새싹(1)", G.stage_at(0, g) == 1)
    chk("99초: 새싹", G.stage_at(99, g) == 1)
    chk("100초: 줄기(2)", G.stage_at(100, g) == 2)
    chk("199초: 줄기", G.stage_at(199, g) == 2)
    chk("200초: 꽃(3)", G.stage_at(200, g) == 3)
    chk("299초: 꽃", G.stage_at(299, g) == 3)
    chk("300초: 익음(4)", G.stage_at(300, g) == 4)
    chk("한참 지나도 익음", G.stage_at(10 ** 7, g) == 4)
    chk("시계가 거꾸로여도(음수) 새싹", G.stage_at(-5, g) == 1)
    g = 100                                  # 3 으로 안 나뉜다 - 34초 · 67초에 바뀐다
    chk("100초짜리: 33초 새싹 · 34초 줄기", G.stage_at(33, g) == 1 and G.stage_at(34, g) == 2,
        (G.stage_at(33, g), G.stage_at(34, g)))
    chk("  66초 줄기 · 67초 꽃 · 100초 익음",
        G.stage_at(66, g) == 2 and G.stage_at(67, g) == 3 and G.stage_at(100, g) == 4)
    g = 300
    chk("next_change 0초 -> 100", G.next_change(0, g) == 100, G.next_change(0, g))
    chk("next_change 150초 -> 50", G.next_change(150, g) == 50, G.next_change(150, g))
    chk("next_change 299초 -> 1", G.next_change(299, g) == 1, G.next_change(299, g))
    chk("next_change 익었으면 None", G.next_change(300, g) is None and G.next_change(999, g) is None)
    g = 100
    chk("next_change 100초짜리 33초 -> 1 (34초에 바뀐다)", G.next_change(33, g) == 1, G.next_change(33, g))
    # 남은 초만큼 지나면 정말로 단계가 바뀐다 (앱이 그때 다시 묻는다)
    bad = [a for a in range(0, 100) if G.stage_at(a + G.next_change(a, g), g) != G.stage_at(a, g) + 1
           or G.stage_at(a + G.next_change(a, g) - 1, g) != G.stage_at(a, g)]
    chk("  모든 초에서: 남은 초 뒤에 바로 다음 단계, 1초 전엔 그대로", not bad, bad[:5])
    chk("물 비트: 새싹 1 · 줄기 2 · 꽃 4", (G.wet_bit(1), G.wet_bit(2), G.wet_bit(3)) == (1, 2, 4))
    chk("  빈 화분 · 익음은 0", G.wet_bit(0) == 0 and G.wet_bit(4) == 0)


def test_yield():
    print("[열매 수]")
    chk("4h: 물 없음 1 · 단계마다 4", G.yield_of(4, 0, 0) == 1 and G.yield_of(4, 7, 0) == 4)
    chk("8h: 2 ~ 5", G.yield_of(8, 0, 0) == 2 and G.yield_of(8, 7, 0) == 5)
    chk("16h: 3 ~ 6", G.yield_of(16, 0, 0) == 3 and G.yield_of(16, 7, 0) == 6)
    chk("물 두 단계(새싹 · 꽃 = 0b101)면 +2", G.yield_of(4, 5, 0) == 3, G.yield_of(4, 5, 0))
    chk("친구 보너스 +1", G.yield_of(4, 0, 1) == 2 and G.yield_of(16, 7, 1) == 7)
    chk("  보너스는 1 을 넘지 않는다", G.yield_of(4, 0, 5) == 2, G.yield_of(4, 0, 5))
    chk("  세 단계 밖의 비트는 안 센다", G.yield_of(4, 0xFF, 0) == 4, G.yield_of(4, 0xFF, 0))


def test_grow_sec_grass():
    print("[풀 타입 빠르기]")
    chk("4h, 풀 0: 14400초", G.grow_sec(4, 0) == 14400, G.grow_sec(4, 0))
    chk("4h, 풀 1: 10% 빠름 12960", G.grow_sec(4, 1) == 12960, G.grow_sec(4, 1))
    chk("4h, 풀 3: 30% 빠름 10080", G.grow_sec(4, 3) == 10080, G.grow_sec(4, 3))
    chk("4h, 풀 5: 셋에서 멈춘다 10080", G.grow_sec(4, 5) == 10080, G.grow_sec(4, 5))
    chk("16h, 풀 2: 20% 빠름 46080", G.grow_sec(16, 2) == 46080, G.grow_sec(16, 2))
    chk("8h, 풀 0: 28800", G.grow_sec(8, 0) == 28800)
    chk("배율 0.01: 4h 가 144초 (2.4분)", G.grow_sec(4, 0, 0.01) == 144, G.grow_sec(4, 0, 0.01))
    chk("  배율 0.01 · 풀 3: 101초", G.grow_sec(4, 3, 0.01) == 101, G.grow_sec(4, 3, 0.01))
    chk("배율이 아주 작아도 3초는 남는다 (단계마다 1초)", G.grow_sec(4, 3, 1e-9) == 3, G.grow_sec(4, 3, 1e-9))
    chk("정수다", isinstance(G.grow_sec(8, 1, 0.37), int))


def main():
    test_groups_cover_47()
    test_stage_split()
    test_yield()
    test_grow_sec_grass()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
