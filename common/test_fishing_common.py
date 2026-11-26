# -*- coding: utf-8 -*-
"""낚시 (시즌 7) 의 순수 계산 (common/fishing.py) 과 종 표 나누기 (pokelogic.Pokedex).

    python common/test_fishing_common.py

못 박는 것:

  1. 풀숲 표에서 뺄 종(exclude)은 표에 하나도 없다. 뺀 표와 안 뺀 표는 캐시 열쇠가 달라 섞이지 않는다.
     exclude 가 비면 지금 표와 똑같다 (열리기 전 풀숲은 바이트 단위로 그대로).
  2. 낚시 표 (roll_fish): 물 타입만, 전설 없음, 낚시 위주 종(FISH_ONLY)은 가중치 x3.
  3. 크기 배율: 보통 0.80~1.20, 대물 4% / 8% / 12%, 왕대물은 대물의 열에 하나. 배지 1.3 big · 1.6 huge.
  4. 주 열쇠: 한국 시각 월요일 0시에 바뀐다 (일 23:59 KST 는 그 주 월요일).
"""
import collections
import datetime
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import fishing as F                             # noqa: E402
from common import pokelogic as P                            # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc


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


def cap(lv):
    return 330 + lv * 8                      # 서버 풀숲과 같은 종족값 상한 (config.WILD_BST_*)


def t_fish_only(dex):
    print("[낚시 위주 종]")
    chk("frozenset 이다 (캐시 열쇠가 된다)", isinstance(F.FISH_ONLY, frozenset), type(F.FISH_ONLY))
    chk("38종 (설계 목록)", len(F.FISH_ONLY) == 38, len(F.FISH_ONLY))
    missing = sorted(k for k in F.FISH_ONLY if not dex.get(k))
    chk("모두 도감에 있다", not missing, missing)
    dry = sorted(k for k in F.FISH_ONLY if dex.get(k) and "WATER" not in dex.get(k)["types"])
    chk("모두 물 타입이다", not dry, dry)
    chk("대쓰여너는 들고 장침바루(악 · 독)는 뺀다", "BASCULEGION" in F.FISH_ONLY and "OVERQWIL" not in F.FISH_ONLY)
    chk("잉어킹 · 갸라도스 · 싸리용이 있다", {"MAGIKARP", "GYARADOS", "TATSUGIRI"} <= F.FISH_ONLY)


def t_pool_exclude(dex):
    print("[풀숲 표에서 빼기 - test_pool_exclude]")
    lv = 50
    base, _c, total = dex.spawn_pool(lv, cap(lv))
    chk("빼기 전 표에는 낚시 위주 종이 있다", any(s["internal"] in F.FISH_ONLY for s in base))
    ref = [s for s in dex.species if s.get("spawnable") and s.get("minLevel", 1) <= lv and dex.bst(s) <= cap(lv)]
    chk("exclude 가 비면 지금 표와 같다 (종 · 가중치 합)",
        [s["internal"] for s in base] == [s["internal"] for s in ref] and total == sum(s.get("weight", 0) for s in ref),
        (len(base), len(ref)))
    same = dex.spawn_pool(lv, cap(lv), exclude=frozenset())
    chk("  빈 exclude 를 넘겨도 같은 표 (같은 캐시)", same[0] is base)
    cut, _c2, total2 = dex.spawn_pool(lv, cap(lv), exclude=F.FISH_ONLY)
    chk("뺀 표에는 낚시 위주 종이 0", not [s["internal"] for s in cut if s["internal"] in F.FISH_ONLY],
        [s["internal"] for s in cut if s["internal"] in F.FISH_ONLY])
    gone = sum(s.get("weight", 0) for s in base if s["internal"] in F.FISH_ONLY)
    chk("  가중치 합은 그만큼 준다", total2 == total - gone and gone > 0, (total, total2, gone))
    again, _c3, total3 = dex.spawn_pool(lv, cap(lv))
    chk("캐시 열쇠가 다르다 - 다시 부른 평소 표는 그대로", again is base and total3 == total
        and any(s["internal"] in F.FISH_ONLY for s in again))
    keys = [k for k in dex._pool_cache if k[:2] == (lv, cap(lv))]
    chk("  캐시에 열쇠가 둘", len(set(keys)) == 2, keys)
    # 이벤트(할로윈) · 타입 스프레이 표에도 같이 얹힌다
    halloween = (("GHOST",), 8)
    hb, _h, _ht = dex.spawn_pool(lv, cap(lv), halloween, exclude=F.FISH_ONLY)
    chk("할로윈 표에서도 빠진다", hb and not any(s["internal"] in F.FISH_ONLY for s in hb))
    lure, _l, _lt = dex.spawn_pool(lv, cap(lv), (("WATER",), 0), exclude=F.FISH_ONLY)
    chk("물 타입 스프레이 표에서도 빠진다 (다른 물 타입은 남는다)",
        lure and all("WATER" in s["types"] for s in lure) and not any(s["internal"] in F.FISH_ONLY for s in lure),
        len(lure))
    tight, _t, _tt = dex.spawn_pool(5, 1, exclude=F.FISH_ONLY)
    chk("너무 좁아 상한을 풀어 줄 때도 뺀 채로", tight and not any(s["internal"] in F.FISH_ONLY for s in tight))
    rng = random.Random(7)
    got = collections.Counter()
    for i in range(3000):
        lvl = (5, 20, 35, 60)[i % 4]
        m = dex.roll_wild(lvl, lvl, rng, max_bst=cap(lvl), exclude=F.FISH_ONLY)
        got[m["species"] in F.FISH_ONLY] += 1
    chk("roll_wild(exclude=...) 3000번에 낚시 위주 종 0 (진화한 모습 포함)", got[True] == 0, got)
    rng_a, rng_b = random.Random(11), random.Random(11)
    a = [dex.roll_wild(30, 30, rng_a, max_bst=cap(30)) for _ in range(50)]
    b = [dex.roll_wild(30, 30, rng_b, max_bst=cap(30), exclude=frozenset()) for _ in range(50)]
    chk("빈 exclude 는 같은 씨앗에 같은 개체 (굴림 순서가 안 바뀐다)", a == b)


def t_roll_fish(dex):
    print("[낚시 표 - test_roll_fish_water_only]")
    rng = random.Random(5)
    out = []
    for i in range(2000):
        lv = (5, 15, 30, 50, 80)[i % 5]
        m = dex.roll_fish(lv, lv, rng, max_bst=cap(lv))
        out.append((lv, m))
    chk("2000번 모두 나온다", all(m for _lv, m in out))
    dry = sorted(set(m["species"] for _lv, m in out if "WATER" not in dex.get(m["species"])["types"]))
    chk("전부 물 타입 (진화한 모습도)", not dry, dry)
    legend = sorted(set(m["species"] for _lv, m in out if dex.get(m["species"]).get("legendary")))
    chk("전설 · 환상 0", not legend, legend)
    chk("레벨은 준 범위 그대로", all(m["level"] == lv for lv, m in out))
    # 낚시 위주 종 가중치 x3 - 한 레벨에서 표를 따로 셈해 견준다
    lv = 30
    water = [s for s in dex.species if s.get("spawnable") and "WATER" in (s.get("types") or ())
             and s.get("minLevel", 1) <= lv and dex.bst(s) <= cap(lv)]
    w_f = sum(s["weight"] for s in water if s["internal"] in F.FISH_ONLY) * F.FISH_ONLY_MULT
    w_o = sum(s["weight"] for s in water if s["internal"] not in F.FISH_ONLY)
    want = w_f * 1.0 / (w_f + w_o)
    rng = random.Random(9)
    n = 4000
    hit = sum(1 for _ in range(n) if dex.roll_fish(lv, lv, rng, max_bst=cap(lv))["species"] in F.FISH_ONLY)
    chk("낚시 위주 종 몫 %.3f ≈ 가중치 x3 로 셈한 %.3f (±0.03)" % (hit * 1.0 / n, want),
        abs(hit * 1.0 / n - want) <= 0.03, (hit, n, want))
    chk("  x3 이 아니면 나올 몫(%.3f)보다 크다" % (w_f / 3.0 / (w_f / 3.0 + w_o)),
        hit * 1.0 / n > w_f / 3.0 / (w_f / 3.0 + w_o) + 0.05)
    pool, _cum, _total = dex.fish_pool(lv, cap(lv))
    chk("낚시 표는 종족값 상한을 지킨다", pool and all(dex.bst(s) <= cap(lv) for s in pool))
    chk("  풀숲 표와 캐시가 섞이지 않는다", dex.spawn_pool(lv, cap(lv))[0] is not pool
        and any("WATER" not in s["types"] for s in dex.spawn_pool(lv, cap(lv))[0]))
    m = dex.roll_fish(10, 20, random.Random(1), max_bst=cap(20), shiny_rate=1)
    chk("shiny_rate 를 넘기면 쓴다 (1 이면 늘 이로치)", m["shiny"] is True and 10 <= m["level"] <= 20, m.get("shiny"))
    m = dex.roll_fish(10, 10, random.Random(1), max_bst=cap(10), shiny_rate=10 ** 9)
    chk("  10억이면 이로치 아님", m["shiny"] is False)
    surskit = dex.get("SURSKIT")
    chk("물을 떠나는 진화(비구술 -> 비나방)는 하지 않는다 (물 타입만)",
        all("WATER" in dex.get(dex.roll_fish(60, 60, random.Random(i), max_bst=10 ** 4)["species"])["types"]
            for i in range(300)) and surskit is not None)


def t_ratio(dex):
    print("[크기 배율 - test_ratio_distribution]")
    chk("대물 확률 = 0.04 + 미끼 0.04 + 완벽 0.04",
        (F.big_chance(), F.big_chance(bait=True), F.big_chance(bait=True, perfect=True), F.big_chance(perfect=True))
        == (0.04, 0.08, 0.12, 0.08), (F.big_chance(), F.big_chance(True), F.big_chance(True, True)))
    n = 100000
    for chance in (0.04, 0.08, 0.12):
        rng = random.Random(int(chance * 1000))
        rs = [F.roll_ratio(rng, chance) for _ in range(n)]
        normal = [r for r in rs if r < 1.3]
        big = [r for r in rs if r >= 1.3]
        huge = [r for r in rs if r >= 1.6]
        chk("대물 %.0f%%: 보통은 0.80~1.20" % (chance * 100), min(normal) >= 0.80 and max(normal) <= 1.20,
            (min(normal), max(normal)))
        chk("  보통의 가운데가 많다 (0.95~1.05 가 1/4 넘게, 평균 ≈ 1.00)",
            sum(1 for r in normal if 0.95 <= r <= 1.05) > len(normal) * 0.25
            and abs(sum(normal) / len(normal) - 1.0) < 0.005)
        chk("  대물 몫 %.4f ≈ %.2f (±0.005)" % (len(big) * 1.0 / n, chance),
            abs(len(big) * 1.0 / n - chance) <= 0.005, len(big))
        chk("  대물 1.30~2.00, 왕대물 1.60~2.00", min(big) >= 1.30 and max(big) <= 2.00 and min(huge) >= 1.60,
            (min(big), max(big)))
        chk("  왕대물은 대물의 %.3f ≈ 0.10 (±0.02)" % (len(huge) * 1.0 / len(big)),
            abs(len(huge) * 1.0 / len(big) - 0.10) <= 0.02, (len(huge), len(big)))
    chk("배지: 1.29 없음 · 1.30 big · 1.59 big · 1.60 huge · 2.0 huge · 0.8 없음",
        [F.badge(r) for r in (1.29, 1.30, 1.59, 1.60, 2.0, 0.8)] == [None, "big", "big", "huge", "huge", None],
        [F.badge(r) for r in (1.29, 1.30, 1.59, 1.60, 2.0, 0.8)])
    chk("그램 = round(kg x 1000 x 배율) - 종의 kg (출현 weight 아님)",
        F.grams(10.0, 1.31) == 13100 and F.grams(0.3, 1.333) == 400 and F.grams(398.0, 0.8) == 318400,
        (F.grams(10.0, 1.31), F.grams(0.3, 1.333)))


def t_week():
    print("[주 열쇠 - test_week_key]")
    sun_late = datetime.datetime(2026, 12, 6, 14, 59, tzinfo=UTC)     # 12/6(일) 23:59 KST
    mon_zero = datetime.datetime(2026, 12, 6, 15, 0, tzinfo=UTC)      # 12/7(월) 00:00 KST
    chk("일 23:59 KST -> 그 주 월요일 (11/30)", F.week_key(sun_late) == "2026-11-30", F.week_key(sun_late))
    chk("월 00:00 KST -> 새 주 (12/7)", F.week_key(mon_zero) == "2026-12-07", F.week_key(mon_zero))
    tue = datetime.datetime(2026, 11, 30, 15, 0, tzinfo=UTC)          # 12/1(화) 00:00 KST - 낚시가 여는 날
    chk("첫 주(12/1 화)의 열쇠는 11/30 월요일", F.week_key(tue) == "2026-11-30", F.week_key(tue))
    mon_utc = datetime.datetime(2026, 12, 7, 3, 0, tzinfo=UTC)        # UTC 로는 월요일이지만 KST 12:00 도 월요일
    chk("UTC 월요일 03:00 = KST 월 12:00 -> 12/7", F.week_key(mon_utc) == "2026-12-07")
    sun_utc = datetime.datetime(2026, 12, 13, 16, 0, tzinfo=UTC)      # UTC 일요일 16:00 = KST 월 01:00
    chk("UTC 일요일 16:00 = KST 월 01:00 -> 12/14", F.week_key(sun_utc) == "2026-12-14", F.week_key(sun_utc))
    chk("시간대 없는 값은 UTC 로 본다", F.week_key(datetime.datetime(2026, 12, 6, 15, 0)) == "2026-12-07")
    chk("다른 시간대도 맞춘다 (KST 로 받은 값)",
        F.week_key(datetime.datetime(2026, 12, 7, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=9))))
        == "2026-12-07")
    st = F.week_start_utc("2026-12-07")
    chk("week_start_utc = 월 00:00 KST = 일 15:00 UTC", st == mon_zero and st.tzinfo is not None, st)
    chk("  되돌리면 같은 열쇠", F.week_key(st) == "2026-12-07"
        and F.week_key(st - datetime.timedelta(seconds=1)) == "2026-11-30")


def main():
    dex = load_dex()
    t_fish_only(dex)
    t_pool_exclude(dex)
    t_roll_fish(dex)
    t_ratio(dex)
    t_week()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
