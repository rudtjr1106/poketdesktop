# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 하루 한 종목 · 실제 올림픽식 라운드 (순수 규칙, DB 없음).

    python server/test_olympics_rounds.py [이름 ...]      (이름을 주면 그 검사만: schedule sprint ...)

설계: design-notes/2026-11-08-olympics-rounds.md · 계획: design-notes/2026-11-08-olympics-rounds-plan.md
"""
import datetime
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
for k in ("POKET_OLYMPICS_DAYS", "POKET_OLYMPICS_OPEN", "POKET_OLYMPICS_AT"):
    os.environ.pop(k, None)

from common import olympics as O                             # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc


def kst(day, h, mi=0):
    y, mo, d = int(day[0:4]), int(day[5:7]), int(day[8:10])
    return datetime.datetime(y, mo, d, h, mi, tzinfo=O.KST).astimezone(UTC)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


# ---------------------------------------------------------------- Task 1: 일정 · 응원 · 페이즈
def t_schedule():
    print("\n[일정 · 응원 · 페이즈]")
    want = [("sprint", "2026-11-16"), ("bobsled", "2026-11-17"), ("pole", "2026-11-18"), ("archery", "2026-11-19"),
            ("discus", "2026-11-20"), ("ski", "2026-11-23"), ("marathon", "2026-11-24")]
    chk("종목마다 날 하나 (하루 한 종목)", all(O.day_of(e) == d for e, d in want), [(e, O.day_of(e)) for e, _ in want])
    chk("날 -> 종목", all(O.event_of(d) == e for e, d in want) and O.event_of("2026-11-21") is None,
        [(d, O.event_of(d)) for _e, d in want])
    cheer = dict((e, O.cheer_of(d)) for e, d in want)
    chk("응원 짝: 100m 페어리·물 · 봅슬레이 고스트·불꽃 · 마라톤 격투·에스퍼",
        cheer["sprint"] == ("FAIRY", "WATER") and cheer["bobsled"] == ("GHOST", "FIRE")
        and cheer["marathon"] == ("FIGHTING", "PSYCHIC"), cheer)
    clash = [e for e, d in want if set(O.cheer_of(d)) & set(O.EV[e]["types"])]
    chk("응원 타입이 그날 종목의 특기 타입과 안 겹친다", not clash, clash)
    chk("응원 일곱 짝은 예전 것 그대로 (차례만 바뀜)",
        sorted(cheer.values()) == sorted([("GHOST", "FIRE"), ("FAIRY", "WATER"), ("DRAGON", "ELECTRIC"),
                                          ("POISON", "GRASS"), ("DARK", "ICE"), ("NORMAL", "ROCK"),
                                          ("FIGHTING", "PSYCHIC")]), cheer)
    chk("신청: 11/14 23:59 는 아직", not O.entry_open("ski", kst("2026-11-14", 23, 59)))
    chk("신청: 11/15 00:00 부터 일곱 종목 모두",
        all(O.entry_open(e, kst("2026-11-15", 0, 0)) for e, _d in want))
    chk("신청: 스키점프는 11/20 에도 받는다", O.entry_open("ski", kst("2026-11-20", 10)))
    chk("신청: 100m 는 그날 14:00 에 닫힌다",
        O.entry_open("sprint", kst("2026-11-16", 13, 59)) and not O.entry_open("sprint", kst("2026-11-16", 14, 0)))
    chk("신청: 모르는 종목은 False", not O.entry_open("swim", kst("2026-11-15", 10)))
    chk("페이즈: 11/14 before · 11/15 entry",
        O.phase(kst("2026-11-14", 12)) == "before" and O.phase(kst("2026-11-15", 12)) == "entry",
        (O.phase(kst("2026-11-14", 12)), O.phase(kst("2026-11-15", 12))))
    ends = {"2026-11-16": 300}
    chk("페이즈: 14:00 부터 그날 end 까지 live, 그 뒤 entry (다음 종목 신청 중)",
        O.phase(kst("2026-11-16", 14, 1), ends) == "live" and O.phase(kst("2026-11-16", 14, 4), ends) == "live"
        and O.phase(kst("2026-11-16", 14, 6), ends) == "entry",
        [O.phase(kst("2026-11-16", 14, m), ends) for m in (1, 4, 6)])
    chk("live_day: end 를 모르면 DEFAULT_END 까지",
        O.live_day(kst("2026-11-16", 14, 10)) == "2026-11-16"
        and O.live_day(kst("2026-11-16", 14, 0) + datetime.timedelta(seconds=O.DEFAULT_END + 1)) is None)
    chk("end_at(day, end)", O.end_at("2026-11-16", 300) == kst("2026-11-16", 14, 5))
    chk("페이즈: 마지막 날 끝난 뒤 done, 7일 뒤 closed",
        O.phase(kst("2026-11-24", 23), {"2026-11-24": 300}) == "done"
        and O.phase(kst("2026-12-02", 0), {"2026-11-24": 300}) == "closed")
    chk("next_day: 끝나지 않은 첫 경기 날", O.next_day(kst("2026-11-16", 15), {"2026-11-16": 300}) == "2026-11-17")


# ---------------------------------------------------------------- Task 2: 시드 뱀 배정 · 레인 · 진출
def t_seed():
    from common import olympics_rounds as R
    print("\n[시드 · 레인 · 진출]")
    ids = list(range(1, 21))                         # 1 이 가장 세다
    hs = R.serpentine(ids, 3)
    chk("20명 3조 = 7 · 7 · 6", [len(h) for h in hs] == [7, 7, 6], [len(h) for h in hs])
    where = dict((x, i) for i, h in enumerate(hs) for x in h)
    chk("1 · 2 · 3위는 서로 다른 조", len({where[1], where[2], where[3]}) == 3, (where[1], where[2], where[3]))
    chk("4 · 5 · 6위는 거꾸로 (3조 · 2조 · 1조)", (where[4], where[5], where[6]) == (2, 1, 0),
        (where[4], where[5], where[6]))
    chk("조 하나면 그대로", R.serpentine([5, 6, 7], 1) == [[5, 6, 7]])
    ents = [{"id": i, "exp": e} for i, e in ((1, 1.0), (2, 1.2), (3, 1.0), (4, 0.9))]
    o1 = R.strength_order(ents, random.Random(5))
    chk("실력 순 (같은 기대 점수는 씨앗 무작위)", o1[0] == 2 and o1[-1] == 4 and set(o1[1:3]) == {1, 3}, o1)
    chk("  같은 씨앗 같은 순서", o1 == R.strength_order(ents, random.Random(5)))
    ln = R.lanes(list(range(1, 9)), False, random.Random(1))
    chk("결승 레인: 위 넷은 3~6, 다음 둘 7 · 8, 나머지 1 · 2",
        {ln[i] for i in (1, 2, 3, 4)} == {3, 4, 5, 6} and {ln[5], ln[6]} == {7, 8} and {ln[7], ln[8]} == {1, 2}, ln)
    l1 = R.lanes(list(range(1, 9)), True, random.Random(2))
    chk("첫 라운드 레인: 1~8 하나씩", sorted(l1.values()) == list(range(1, 9)), l1)
    l5 = R.lanes([1, 2, 3, 4, 5], True, random.Random(3))
    chk("5명이면 가운데 레인부터 (2~6 또는 3~7)", sorted(l5.values()) in ([2, 3, 4, 5, 6], [3, 4, 5, 6, 7]), l5)

    def heats_of(h, per):
        out, n = [], 0
        for _ in range(h):
            out.append(list(range(n, n + per)))
            n += per
        return out
    for h, per, target, q_n in ((2, 6, 8, 6), (3, 7, 8, 6), (7, 8, 24, 21), (9, 8, 24, 18)):
        hs = heats_of(h, per)
        got = R.advance(hs, target, lambda x: x)       # 번호가 작을수록 빠른 기록
        nq = sum(1 for v in got.values() if v == "Q")
        chk("%d조 -> %d명: Q %d + q %d" % (h, target, q_n, target - q_n),
            len(got) == target and nq == q_n, (len(got), nq))
    got = R.advance([[1, 2, 3, 4], [5, 6, 7, 8]], 5, lambda x: x)
    chk("2조 -> 5명: 조 상위 2 = Q, 남은 자리는 기록 순 q (1조 3위 3 이 2조 3위 7 보다 빠르다)",
        [k for k, v in sorted(got.items()) if v == "Q"] == [1, 2, 5, 6] and got.get(3) == "q" and 7 not in got, got)
    got = R.advance([[4, 1, 3], [2]], 2, lambda x: x)
    chk("조 안 차례는 기록으로 다시 센다 (들어온 차례가 아니다)", got == {1: "Q", 2: "Q"}, got)


# ---------------------------------------------------------------- 대회 공통 도우미
def fake(event, n, seed=1, tactic=None):
    """가짜 신청 n 개와 ctx. 종마다 적성(pct)이 달라 기대 점수가 갈린다. 작전은 번갈아 (tactic 을 주면 그것만)."""
    rng = random.Random(seed)
    pct = {event: {}}
    ents = []
    for i in range(n):
        key = "SP%d" % i
        pct[event][key] = rng.random()
        sp = {"internal": key, "kr": "종%d" % i, "base": {}, "kg": O.EV[event]["kg0"] * rng.uniform(0.5, 2.0),
              "types": []}
        ents.append({"id": 100 + i, "sp": sp, "ability": None,
                     "tactic": tactic or ("safe" if i % 2 else "bold"), "fat": 0.0, "order": i})
    return ents, {"pct": pct, "cheer": (), "seed": seed * 7 + 3}


def wide(fc):
    """기대 점수 폭을 실제처럼 (0.9 ~ 1.2): 셋 중 하나는 그 종목 특기 타입, 응원도 그 타입."""
    ents, ctx = fc
    ev = None
    for e in ents:
        ev = ev or next(k for k in ctx["pct"])
    t = O.EV[ev]["types"][0]
    for k, e in enumerate(ents):
        if k % 3 == 0:
            e["sp"]["types"] = [t]
    ctx["cheer"] = (t, "NORMAL")
    return ents, ctx


def heat_sizes(rnd):
    return [len(h["ids"]) for h in rnd["heats"]]


def standings_ok(comp, n):
    st = comp["standings"]
    return len(st) == n and [s["rank"] for s in st] == list(range(1, n + 1)) and \
        sorted(s["id"] for s in st) == sorted(100 + i for i in range(n))


def same_twice(event, n):
    from common import olympics_rounds as R
    e1, c1 = fake(event, n, 4)
    e2, c2 = fake(event, n, 4)
    return json.dumps(R.run(event, e1, c1), sort_keys=True) == json.dumps(R.run(event, e2, c2), sort_keys=True)


# ---------------------------------------------------------------- Task 3: 100m
def t_sprint():
    from common import olympics_rounds as R
    print("\n[100m]")
    want = {0: [], 1: ["final"], 2: ["final"], 3: ["final"], 8: ["final"], 9: ["r1", "final"], 16: ["r1", "final"],
            17: ["r1", "final"], 24: ["r1", "final"], 25: ["r1", "semi", "final"], 72: ["r1", "semi", "final"],
            73: ["r1", "qf", "semi", "final"], 216: ["r1", "qf", "semi", "final"],
            500: ["r1", "r2", "qf", "semi", "final"]}
    for n, keys in sorted(want.items()):
        plan = R.sprint_plan(n)
        chk("N=%d 라운드 %s" % (n, keys or "없음"), [p["key"] for p in plan] == keys, [p["key"] for p in plan])
    chk("이름: 예선 · 준준결승 · 준결승 · 결승",
        [p["kr"] for p in R.sprint_plan(100)] == ["예선", "준준결승", "준결승", "결승"], [p["kr"] for p in R.sprint_plan(100)])
    for n in (0, 1, 3, 8, 9, 17, 25, 73, 216, 500):
        ents, ctx = fake("sprint", n)
        comp = R.run("sprint", ents, ctx)
        rs = comp["rounds"]
        sizes_ok = all(max(heat_sizes(r) or [0]) <= 8 for r in rs)
        plan = R.sprint_plan(n)
        flow_ok = all(sum(heat_sizes(rs[i + 1])) == plan[i]["target"] and len(set().union(*[h["q"] for h in rs[i]["heats"]]))
                      == plan[i]["target"] for i in range(len(rs) - 1))
        fin = rs[-1]["heats"] if rs else []
        chk("N=%d: 조 ≤ 8명 · 다음 라운드 인원 = 정원 · 결승 1조 ≤ 8명 · 순위 1..N" % n,
            sizes_ok and flow_ok and (not rs or (len(fin) == 1 and len(fin[0]["ids"]) <= 8)) and standings_ok(comp, n),
            ([heat_sizes(r) for r in rs], len(comp["standings"])))
    ents, ctx = fake("sprint", 40)
    comp = R.run("sprint", ents, ctx)
    fin = comp["rounds"][-1]["heats"][0]
    best = sorted(fin["ids"], key=lambda i: fin["res"][i]["v"])
    chk("1~8위 = 결승 기록 순", [s["id"] for s in comp["standings"][:len(best)]] == best)
    semi_out = [i for h in comp["rounds"][1]["heats"] for i in h["ids"] if i not in fin["ids"]]
    chk("9위부터는 준결승에서 떨어진 사람", set(s["id"] for s in comp["standings"][8:8 + len(semi_out)]) == set(semi_out))
    r1 = comp["rounds"][0]
    chk("예선 자막: '조 상위 k명 + 기록 m명'", "조 상위" in r1["note"] and "기록" in r1["note"], r1["note"])
    chk("결승 레인은 3~6 에 준결승 상위 넷", sorted(fin["lanes"][i] for i in sorted(
        fin["ids"], key=lambda i: min(h["res"][i]["v"] for h in comp["rounds"][1]["heats"] if i in h["res"]))[:4])
        == [3, 4, 5, 6], fin["lanes"])
    chk("결과마다 기록 · 실수 · 씨앗", all(set(("v", "slip", "seed")) <= set(x) for x in fin["res"].values()))
    chk("같은 씨앗 = 같은 대회", same_twice("sprint", 30))


# ---------------------------------------------------------------- Task 4: 마라톤
def t_marathon():
    from common import olympics_rounds as R
    print("\n[마라톤]")
    ents, ctx = fake("marathon", 37)
    comp = R.run("marathon", ents, ctx)
    rs = comp["rounds"]
    chk("라운드 하나 · 조 하나 · 37명 다 같이", len(rs) == 1 and len(rs[0]["heats"]) == 1
        and len(rs[0]["heats"][0]["ids"]) == 37 and rs[0]["key"] == "final" and rs[0]["format"] == "race",
        [(r["key"], heat_sizes(r)) for r in rs])
    res = rs[0]["heats"][0]["res"]
    chk("순위 = 기록 순 (시간이 짧은 쪽)", [s["record"] for s in comp["standings"]]
        == sorted(v["v"] for v in res.values()) and standings_ok(comp, 37))
    chk("0명이면 라운드 없음", R.run("marathon", [], ctx)["rounds"] == [])
    chk("같은 씨앗 = 같은 대회", same_twice("marathon", 20))


# ---------------------------------------------------------------- Task 5: 봅슬레이
def t_bobsled():
    from common import olympics_rounds as R
    print("\n[봅슬레이]")
    ents, ctx = fake("bobsled", 25)
    comp = R.run("bobsled", ents, ctx)
    rs = comp["rounds"]
    chk("주행 넷: 1~3차 25대 · 4차 20대", [r["key"] for r in rs] == ["run1", "run2", "run3", "run4"]
        and [len(r["heats"][0]["ids"]) for r in rs] == [25, 25, 25, 20] and rs[0]["kr"] == "1차 주행",
        [(r["key"], heat_sizes(r)) for r in rs])
    tot3 = dict((i, v["total"]) for i, v in rs[2]["heats"][0]["res"].items())
    lead3 = min(tot3, key=lambda i: (tot3[i], i))
    chk("4차 마지막 출발 = 3차까지 1위 (거꾸로)", rs[3]["heats"][0]["ids"][-1] == lead3)
    r1 = rs[0]["heats"][0]["res"]
    order2 = rs[1]["heats"][0]["ids"]
    chk("2차 출발 = 1차 기록 순 (빠른 썰매 먼저)", [r1[i]["v"] for i in order2] == sorted(r1[i]["v"] for i in order2))
    chk("3차 뒤 4차 진출 20대에 표시", len(rs[2]["heats"][0]["q"]) == 20)
    t4 = rs[3]["heats"][0]["res"]
    top = [s for s in comp["standings"][:20]]
    chk("1~20위 = 네 번 합계 순", [s["id"] for s in top] == sorted(t4, key=lambda i: (t4[i]["total"], i))
        and all(abs(s["record"] - t4[s["id"]]["total"]) < 1e-9 for s in top))
    rest = [s["id"] for s in comp["standings"][20:]]
    chk("21위부터 = 3차까지 합계 순", rest == sorted((i for i in tot3 if i not in t4), key=lambda i: (tot3[i], i)))
    chk("합계 = 주행 시간의 합", all(abs(t4[i]["total"] - sum(r["heats"][0]["res"][i]["v"] for r in rs)) < 0.011 for i in t4))
    chk("순위 1..N", standings_ok(comp, 25))
    e5, c5 = fake("bobsled", 5)
    chk("5대면 모두 4차", [len(r["heats"][0]["ids"]) for r in R.run("bobsled", e5, c5)["rounds"]] == [5, 5, 5, 5])
    chk("같은 씨앗 = 같은 대회", same_twice("bobsled", 22))


# ---------------------------------------------------------------- Task 6: 원반던지기
def t_discus():
    from common import olympics_rounds as R
    print("\n[원반던지기]")
    ents, ctx = fake("discus", 30)
    comp = R.run("discus", ents, ctx)
    rs = comp["rounds"]
    chk("예선 2조(15 · 15) -> 결승 12명", [r["key"] for r in rs] == ["qual", "final"]
        and heat_sizes(rs[0]) == [15, 15] and heat_sizes(rs[1]) == [12] and rs[0]["kr"] == "예선",
        [(r["key"], heat_sizes(r)) for r in rs])
    chk("예선은 모두 3번", all(len(v["tries"]) == 3 for h in rs[0]["heats"] for v in h["res"].values()))
    qual = set().union(*[set(h["q"]) for h in rs[0]["heats"]])
    chk("예선 통과 표시 12명 = 결승 12명", qual == set(rs[1]["heats"][0]["ids"]))
    fin = rs[1]["heats"][0]
    n6 = sorted(i for i, v in fin["res"].items() if len(v["tries"]) == 6)
    n3 = [i for i, v in fin["res"].items() if len(v["tries"]) == 3]
    chk("결승: 상위 8명은 6번, 나머지 4명은 3번", len(n6) == 8 and len(n3) == 4, (len(n6), len(n3)))

    def best3(i):
        return max([t["v"] for t in fin["res"][i]["tries"][:3] if t["v"] is not None] or [-1])
    chk("3번 뒤 상위 8명이 6번", sorted(sorted(fin["ids"], key=lambda i: -best3(i))[:8]) == n6 or
        len(set(best3(i) for i in fin["ids"])) < 12)
    chk("4~6번째는 3번째까지 순위의 거꾸로 (선두가 마지막)",
        fin["after3"] and fin["after3"][-1] == sorted(n6, key=lambda i: -best3(i))[0], fin.get("after3"))
    top12 = [s["id"] for s in comp["standings"][:12]]
    chk("1~12위 = 결승 진출자", set(top12) == set(fin["ids"]) and standings_ok(comp, 30))
    chk("결승 순위 = 최고 기록 순", [s["record"] for s in comp["standings"][:12]]
        == sorted((s["record"] for s in comp["standings"][:12]), key=lambda v: -(v if v is not None else -1)))
    e12, c12 = fake("discus", 12)
    chk("12명이면 결승만", [r["key"] for r in R.run("discus", e12, c12)["rounds"]] == ["final"])
    e50, c50 = fake("discus", 50)
    chk("50명이면 예선 3조", len(R.run("discus", e50, c50)["rounds"][0]["heats"]) == 3)
    chk("같은 씨앗 = 같은 대회", same_twice("discus", 30))


# ---------------------------------------------------------------- Task 7: 장대높이뛰기
def att_ok(att):
    """시도 목록이 바 올리기 규칙대로인가: 높이는 늘기만, 한 높이에 최대 3번, 'o' 뒤 그 높이 시도 없음, 3연속 x 면 끝."""
    last_h, n_here, miss_run = None, 0, 0
    for k, (h, r) in enumerate(att):
        if last_h is not None and h < last_h:
            return False
        if h != last_h:
            n_here = 0
        n_here += 1
        if n_here > 3:
            return False
        if last_h == h and att[k - 1][1] == "o":
            return False
        miss_run = miss_run + 1 if r == "x" else 0
        if miss_run >= 3 and k != len(att) - 1:
            return False
        last_h = h
    return True


def t_pole():
    from common import olympics_rounds as R
    print("\n[장대높이뛰기]")
    k = R.pole_key
    a = {"att": [[5.0, "o"], [5.1, "x"], [5.1, "o"], [5.2, "x"], [5.2, "x"], [5.2, "x"]], "v": 5.1}
    b = {"att": [[5.0, "x"], [5.0, "o"], [5.1, "o"], [5.2, "x"], [5.2, "x"], [5.2, "x"]], "v": 5.1}
    c = {"att": [[5.0, "o"], [5.1, "o"], [5.2, "x"], [5.2, "x"], [5.2, "x"]], "v": 5.1}
    d = {"att": [[5.0, "x"], [5.0, "x"], [5.0, "x"]], "v": None}
    chk("순위: 같은 높이면 그 높이 실패 적은 쪽, 다음 전체 실패 적은 쪽, 기록 없음은 맨 뒤",
        k(c, 0, 1) < k(b, 0, 2) < k(a, 0, 3) < k(d, 0, 4), [k(x, 0, 0)[:3] for x in (a, b, c, d)])
    ents, ctx = wide(fake("pole", 40))
    comp = R.run("pole", ents, ctx)
    rs = comp["rounds"]
    chk("40명: 예선 2조 -> 결승 12명", [r["key"] for r in rs] == ["qual", "final"] and heat_sizes(rs[0]) == [20, 20]
        and heat_sizes(rs[1]) == [12] and rs[0]["format"] == "bar", [(r["key"], heat_sizes(r)) for r in rs])
    allres = [v for r in rs for h in r["heats"] for v in h["res"].values()]
    chk("모든 시도가 바 올리기 규칙대로", all(att_ok(v["att"]) for v in allres))
    chk("기록 = 'o' 를 낸 가장 높은 높이", all(v["v"] == max([h for h, r in v["att"] if r == "o"] or [None],
                                                       key=lambda x: -1 if x is None else x) for v in allres))
    fin = rs[1]["heats"][0]
    chk("결승 조에 높이 목록", fin["heights"] and fin["heights"] == sorted(fin["heights"]), fin.get("heights"))
    chk("결승은 예선보다 높은 데서 시작 (또는 같게)", fin["heights"][0] >= rs[0]["heats"][0]["heights"][0])
    chk("결승 끝까지 남은 한 명도 실패 셋으로 끝남", any(v["att"][-3:] == [[v["att"][-1][0], "x"]] * 3
                                              for v in fin["res"].values()))
    top = [s["id"] for s in comp["standings"][:12]]
    chk("1~12위 = 결승 진출자 · 순위 1..N", set(top) == set(fin["ids"]) and standings_ok(comp, 40))
    steps = [round(b - a, 2) for a, b in zip(fin["heights"], fin["heights"][1:])]
    chk("바는 10cm 씩, 남은 선수가 셋 이하가 되면 5cm 씩", set(steps) <= {0.1, 0.05} and steps == sorted(steps, reverse=True),
        steps)
    lens = []
    for sd in range(20):
        e, c = wide(fake("pole", 40, sd))
        lens.append(len(R.run("pole", e, c)["rounds"][-1]["heats"][0]["heights"]))
    chk("결승 높이 수: 기대 점수 폭이 실제만큼 넓어도 평균 ≤ 14 · 최대 ≤ 18", sum(lens) / 20.0 <= 14 and max(lens) <= 18,
        (sum(lens) / 20.0, max(lens)))
    e9, c9 = fake("pole", 9)
    chk("9명이면 결승만", [r["key"] for r in R.run("pole", e9, c9)["rounds"]] == ["final"])
    chk("같은 씨앗 = 같은 대회", same_twice("pole", 30))


# ---------------------------------------------------------------- Task 8: 양궁
def t_archery():
    from common import olympics_rounds as R
    print("\n[양궁]")
    chk("대진 자리 (8강): 1 · 8 · 4 · 5 · 2 · 7 · 3 · 6", R.bracket_order(8) == [1, 8, 4, 5, 2, 7, 3, 6], R.bracket_order(8))
    want = {1: (["rank"], []), 2: (["rank", "final"], [1]), 3: (["rank", "sf", "final"], [1, 1]),
            5: (["rank", "qf", "sf", "bronze", "final"], [1, 2, 1, 1]),
            64: (["rank", "r64", "r32", "r16", "qf", "sf", "bronze", "final"], [32, 16, 8, 4, 2, 1, 1]),
            70: (["rank", "r64", "r32", "r16", "qf", "sf", "bronze", "final"], [32, 16, 8, 4, 2, 1, 1])}
    for n, (keys, matches) in sorted(want.items()):
        ents, ctx = fake("archery", n)
        comp = R.run("archery", ents, ctx)
        rs = comp["rounds"]
        chk("N=%d 라운드 %s · 경기 수 %s" % (n, keys, matches), [r["key"] for r in rs] == keys
            and [len(r["heats"]) for r in rs[1:]] == matches and standings_ok(comp, n),
            ([r["key"] for r in rs], [len(r["heats"]) for r in rs[1:]]))
    ents, ctx = fake("archery", 70)
    comp = R.run("archery", ents, ctx)
    rs = comp["rounds"]
    rk = rs[0]["heats"][0]
    chk("랭킹 라운드: 모두 72발 · 상위 64 만 대진 표시", all(v["arrows"] == 72 for v in rk["res"].values())
        and len(rk["q"]) == 64 and len(set().union(*[set(h["ids"]) for h in rs[1]["heats"]])) == 64)
    seeds = sorted(rk["ids"], key=lambda i: (-rk["res"][i]["v"], -rk["res"][i]["tens"], -rk["res"][i]["x"],
                                              [e["order"] for e in ents if e["id"] == i][0]))
    s1, s2 = seeds[0], seeds[1]
    before = [h for r in rs[1:] if r["key"] not in ("final", "bronze") for h in r["heats"]]
    chk("시드 1 · 2 는 결승 전에 안 만난다", not any(s1 in h["ids"] and s2 in h["ids"] for h in before))
    allm = [h for r in rs[1:] for h in r["heats"]]
    chk("모든 경기: 승자 세트 점수 6 이상, 5:5 면 슛오프", all(
        (max(h["match"]["sp"]) >= 6 and min(h["match"]["sp"]) <= 5) or (h["match"]["sp"] == [5, 5] and h["match"]["shoot"])
        for h in allm), [h["match"]["sp"] for h in allm][:10])
    chk("세트마다 각자 3발 (0~10점)", all(len(a) == 3 and len(b) == 3 and all(0 <= x <= 10 for x in a + b)
                                     for h in allm for a, b in h["match"]["sets"]))
    chk("세트 점수 = 세트 합 비교 (2 · 1 · 0)", all(
        h["match"]["sp"] == [sum(2 if sum(a) > sum(b) else 1 if sum(a) == sum(b) else 0 for a, b in h["match"]["sets"]),
                             sum(2 if sum(b) > sum(a) else 1 if sum(a) == sum(b) else 0 for a, b in h["match"]["sets"])]
        for h in allm))
    fin = rs[-1]["heats"][0]["match"]
    br = rs[-2]["heats"][0]["match"]
    lose = lambda m: [i for i in m["ids"] if i != m["win"]][0]
    chk("1~4위 = 결승 승 · 결승 패 · 동메달전 승 · 동메달전 패",
        [s["id"] for s in comp["standings"][:4]] == [fin["win"], lose(fin), br["win"], lose(br)])
    qf_losers = set(i for h in rs[4]["heats"] for i in h["ids"] if i != h["match"]["win"])
    chk("5~8위 = 8강 패자", set(s["id"] for s in comp["standings"][4:8]) == qf_losers)
    e3, c3 = fake("archery", 3)
    c = R.run("archery", e3, c3)
    sf = c["rounds"][1]["heats"][0]["match"]
    chk("3명: 4강 패자가 3위 (동메달전 없음)", c["standings"][2]["id"] == lose(sf))
    chk("같은 씨앗 = 같은 대회", same_twice("archery", 20))
    share = R.archery_tactic_share(trials=200, seed=11)
    chk("같은 실력이면 작전이 한쪽으로 쏠리지 않는다 (상위 8시드 · 금메달 승부수 비율 35~65%%) %s" % share,
        0.35 <= share["seed8"] <= 0.65 and 0.35 <= share["gold"] <= 0.65, share)


# ---------------------------------------------------------------- Task 9: 스키점프
def t_ski():
    from common import olympics_rounds as R
    print("\n[스키점프]")
    chk("점수: 120m · 자세 18 다섯 = 60 + 54 = 114.0", R.ski_points(120.0, [18, 18, 18, 18, 18]) == (54.0, 114.0),
        R.ski_points(120.0, [18, 18, 18, 18, 18]))
    chk("자세는 가장 높은 것 · 낮은 것을 뺀 셋 (125m, 20 · 19 · 18.5 · 18 · 15)",
        R.ski_points(125.0, [20, 19, 18.5, 18, 15]) == (55.5, 125.5), R.ski_points(125.0, [20, 19, 18.5, 18, 15]))
    chk("아주 짧으면 비거리 점수 0 (모자라도 빼지 않음)", R.ski_points(80.0, [10] * 5)[1] == 30.0,
        R.ski_points(80.0, [10] * 5))
    ents, ctx = wide(fake("ski", 60))
    comp = R.run("ski", ents, ctx)
    rs = comp["rounds"]
    chk("60명: 예선 -> 1라운드 50 -> 결선 30", [r["key"] for r in rs] == ["qual", "r1", "final"]
        and [len(r["heats"][0]["ids"]) for r in rs] == [60, 50, 30] and rs[2]["kr"] == "결선 라운드",
        [(r["key"], heat_sizes(r)) for r in rs])
    r1 = rs[1]["heats"][0]["res"]
    lead = sorted(r1, key=lambda i: (-r1[i]["pts"], i))
    chk("결선은 1라운드 순위 거꾸로 (1위가 마지막)", rs[2]["heats"][0]["ids"][-1] == lead[0]
        and set(rs[2]["heats"][0]["ids"]) == set(lead[:30]))
    jumps = [v for r in rs for v in r["heats"][0]["res"].values()]
    chk("점프마다 비거리 · 심판 다섯 · 자세 · 점수", all(len(v["judges"]) == 5 and v["pts"] == R.ski_points(v["dist"], v["judges"])[1]
                                              for v in jumps))
    falls = [v for v in jumps if v["slip"]]
    chk("넘어진 점프는 자세가 낮다 (< 39)", falls and all(v["style"] < 39 for v in falls), len(falls))
    fin = rs[2]["heats"][0]["res"]
    chk("1~30위 = 두 번 점수 합", [s["id"] for s in comp["standings"][:30]]
        == sorted(fin, key=lambda i: (-(r1[i]["pts"] + fin[i]["pts"]), [e["order"] for e in ents if e["id"] == i][0]))
        and abs(comp["standings"][0]["record"] - (r1[comp["standings"][0]["id"]]["pts"]
                                                  + fin[comp["standings"][0]["id"]]["pts"])) < 0.05)
    chk("31~50위 = 1라운드 점수, 51위부터 예선 점수 · 순위 1..N", standings_ok(comp, 60)
        and set(s["id"] for s in comp["standings"][30:50]) == set(r1) - set(fin))
    e20, c20 = fake("ski", 20)
    chk("20명이면 예선 없이 1라운드 · 결선 (모두)", [(r["key"], len(r["heats"][0]["ids"])) for r in R.run("ski", e20, c20)["rounds"]]
        == [("r1", 20), ("final", 20)])
    chk("같은 씨앗 = 같은 대회", same_twice("ski", 55))


# ---------------------------------------------------------------- Task 10: 중계 시각표
def t_program():
    from common import olympics_rounds as R
    print("\n[중계 시각표]")
    for ev, n, cap in (("sprint", 73, 600), ("sprint", 5, 600), ("bobsled", 25, 600), ("pole", 40, 600),
                       ("archery", 64, 900), ("archery", 2, 600), ("discus", 30, 600), ("ski", 60, 600),
                       ("marathon", 80, 600)):
        ents, ctx = fake(ev, n)
        comp = R.run(ev, ents, ctx)
        prog, end = R.program(comp)
        ats = [p["at"] for p in prog]
        chk("%s N=%d: 라운드마다 칸 하나 · 처음 20초 · 사이 10초 · end = 마지막 끝 ≤ %d" % (ev, n, cap),
            len(prog) == len(comp["rounds"]) and ats[0] == R.FIRST_AT and all(
                b["at"] == a["at"] + a["len"] + R.GAP for a, b in zip(prog, prog[1:]))
            and end == prog[-1]["at"] + prog[-1]["len"] and end <= cap and all(p["len"] > 0 for p in prog),
            (prog, end))
    chk("결승 칸은 시상식만큼 길다", R.slot("sprint", "final") > R.slot("sprint", "r1"))
    chk("0명이면 시각표 없음 · end 0", R.program({"event": "sprint", "rounds": []}) == ([], 0))


TESTS = [("schedule", t_schedule), ("seed", t_seed), ("sprint", t_sprint), ("marathon", t_marathon),
         ("bobsled", t_bobsled), ("discus", t_discus), ("pole", t_pole), ("archery", t_archery), ("ski", t_ski),
         ("program", t_program)]


def main():
    want = set(sys.argv[1:])
    for name, fn in TESTS:
        if not want or name in want:
            fn()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
