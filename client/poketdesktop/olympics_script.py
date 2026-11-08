# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 서버 각본(라운드의 조 하나) -> 중계(olympics_show.Show)가 그리는 꼴.

서버는 종목마다 다른 꼴로 결과를 준다 (race · trial · field · bar · rank · match · ski - common/olympics_rounds.py).
중계는 '출전자 8명까지 · 사람마다 시도 목록(tries)' 을 그린다. 여기서 그 사이를 잇는다:

  - **누구를 보여 줄지 고른다** - 조가 커도(봅슬레이 주행은 모든 썰매, 마라톤은 모두) 화면에는 나와 앞선 몇 명만.
  - 결과를 시도 목록으로 (봅슬레이 주행 시간 · 원반 6번 · 장대 마지막 시도들 · 스키점프 비거리).
  - 양궁 랭킹은 '결과만' (resultsOnly) - 출전식과 결과판. 1대1 은 화살을 번갈아 쏘는 시기형으로 (세트 점수판),
    칸 안에 들게 결승은 다섯 세트 · 동메달전 셋 · 그 밖은 마지막 두 세트만 (앞 세트 점수는 판에 먼저 적는다).

라운드 이름 · 조 · 메달 라운드인지 · 진출 표시(Q 는 조 순위로 바로, q 는 서버가 공개한 뒤) · 그 라운드 칸 길이(budget)도 싣는다.
"""
from common import olympics as O
from common import olympics_rounds as OR

SHOW_MAX = 8
FIELD_SHOW = 6              # 시기형(원반 · 장대)은 시도가 많아 6명까지
TRIAL_SHOW = {"*": 2, "run4": 4}     # 봅슬레이: 나 + 선두 (4차는 나 + 마지막 세 대)


def _order(script):
    """조 안 순위 차례의 출전자."""
    fmt, ev = script.get("format"), script["event"]
    ents = list(script.get("entrants") or [])
    if ents and all(e.get("place") for e in ents):           # 서버(엔진)가 센 조 안 순위 - 동점 처리까지 서버와 같다
        return sorted(ents, key=lambda e: e["place"])
    if fmt == "match":
        win = (script.get("match") or {}).get("win")
        return sorted(ents, key=lambda e: e["entryId"] != win)
    if fmt == "bar":
        return sorted(ents, key=lambda e: OR.pole_key(e.get("res") or {}, 0, e["entryId"]))
    if fmt == "trial":
        return sorted(ents, key=lambda e: ((e.get("res") or {}).get("total") or 1e9, e["entryId"]))
    if fmt == "ski":
        return sorted(ents, key=lambda e: -float((e.get("res") or {}).get("total", (e.get("res") or {}).get("pts")) or 0))
    if fmt == "field":
        return sorted(ents, key=lambda e: OR._field_key(ev, (e.get("res") or {}).get("tries") or [], 0, e["entryId"]))
    if fmt == "rank":
        return sorted(ents, key=lambda e: -((e.get("res") or {}).get("v") or 0))
    return sorted(ents, key=lambda e: (O.rank_key(ev, (e.get("res") or {}).get("v")), e["entryId"]))


def _pick(order, n, keep_order=None):
    """앞선 n 명 + 나 (나는 n 명 안에 없으면 마지막 자리 대신)."""
    mine = next((e for e in order if e.get("mine")), None)
    top = order[:n]
    if mine is not None and mine not in top:
        top = top[:max(0, n - 1)] + [mine]
    if keep_order is not None:
        top.sort(key=lambda e: keep_order.index(e))
    return top


MATCH_SETS = {"final": 5, "bronze": 3, "*": 2}       # 1대1 에서 보여 주는 세트 (뒤에서부터 - 칸 안에 들게)


def _match_tries(script):
    """1대1 경기 -> 두 사람의 화살 목록 (번갈아 쏘는 꼴) + 보여 주기 전 세트 점수 · 첫 세트 번호."""
    m = script.get("match") or {}
    key = (script.get("round") or {}).get("key")
    sets = m.get("sets") or []
    n = MATCH_SETS.get(key, MATCH_SETS["*"])
    skip = max(0, len(sets) - n)
    sp = [0, 0]
    for a, b in sets[:skip]:
        if sum(a) > sum(b):
            sp[0] += 2
        elif sum(b) > sum(a):
            sp[1] += 2
        else:
            sp[0] += 1
            sp[1] += 1
    arrows = {0: [], 1: []}
    for a, b in sets[skip:]:
        for side, xs in ((0, a), (1, b)):
            arrows[side] += [{"v": p if p else None, "slip": not p, "set": True} for p in xs]
    if m.get("shoot"):
        for side in (0, 1):
            p = m["shoot"][side]
            arrows[side].append({"v": p if p else None, "slip": not p, "shoot": True})
    return arrows, sp, skip


def _tries(fmt, res):
    if fmt in ("race", "trial"):
        return [{"v": res.get("v"), "slip": bool(res.get("slip")), "at": res.get("at")}]
    if fmt == "field":
        return [{"v": t.get("v"), "slip": bool(t.get("slip"))} for t in res.get("tries") or []]
    if fmt == "bar":                                         # 마지막 시도 셋 (바 높이 · 성공이면 그 높이)
        return [{"v": h if r == "o" else None, "slip": r != "o", "bar": h} for h, r in (res.get("att") or [])[-3:]]
    if fmt == "ski":
        return [{"v": res.get("dist"), "slip": bool(res.get("slip")), "pts": res.get("pts"),
                 "total": res.get("total"), "style": res.get("style")}]
    return []


def legacy(script):
    """서버 각본 -> 중계가 그리는 heat dict (옛 꼴 + round 정보)."""
    ev, fmt = script["event"], script.get("format") or "race"
    rnd = script.get("round") or {}
    order = _order(script)
    place = dict((e["entryId"], i + 1) for i, e in enumerate(order))
    start = list(script.get("entrants") or [])               # 서버가 준 차례 = 레인 · 출발 · 시기 차례
    if fmt == "race" and ev == "marathon":
        shown = _pick(order, SHOW_MAX)                       # 선두 무리 + 나 (나는 무리 밖이면 마지막 자리)
    elif fmt == "trial":
        n = TRIAL_SHOW.get(rnd.get("key"), TRIAL_SHOW["*"])
        if rnd.get("key") == "run4":                         # 마지막에 출발하는 셋 + 실제 1~3위 + 나 (출발 차례 그대로)
            keep = set(id(e) for e in start[-(n - 1):] + order[:3] if e)
            shown = [e for e in start if id(e) in keep or e.get("mine")]
        else:
            shown = _pick(order, n, start)
    elif fmt in ("field", "bar"):
        shown = _pick(order, FIELD_SHOW, start)
    elif fmt == "ski":
        if rnd.get("key") == "final":                        # 결선: 마지막에 뛰는 셋 + 실제 1~3위 + 나 (뛰는 차례 그대로)
            keep = set(id(e) for e in start[-3:] + order[:3])
            shown = [e for e in start if id(e) in keep or e.get("mine")]
        else:
            shown = _pick(order, 4, start)
    else:
        shown = _pick(order, SHOW_MAX, start)
    k = int(rnd.get("k") or 0)
    mt = None
    if fmt == "match":
        mt = _match_tries(script)
        ids = list((script.get("match") or {}).get("ids") or [])
        shown = sorted(shown, key=lambda e: ids.index(e["entryId"]) if e["entryId"] in ids else 9)
    ents = []
    for i, e in enumerate(shown, 1):
        res = e.get("res") or {}
        q = e.get("q")
        if not q and k and place.get(e["entryId"], 99) <= k:
            q = "Q"                                          # 조 순위 진출은 조 안에서 바로 안다 (q 는 공개 뒤)
        ents.append({"entryId": e["entryId"], "lane": e.get("lane") or i, "user": e.get("user"),
                     "mine": bool(e.get("mine")), "pokemon": e.get("pokemon"), "tactic": e.get("tactic"),
                     "record": res.get("dist") if fmt == "ski" else (res.get("v") if fmt in ("race", "trial")
                                                                      else e.get("record")),
                     "text": e.get("text"),
                     "tries": (mt[0][(ids.index(e["entryId"]) if e["entryId"] in ids else 0)] if mt else _tries(fmt, res)),
                     "seed": res.get("seed") or (e["entryId"] * 31 + 7),
                     "rank": place.get(e["entryId"]), "place": place.get(e["entryId"]), "q": q, "res": res,
                     "barBefore": max([h for h, r in (res.get("att") or [])[:-3] if r == "o"] or [None],
                                      key=lambda x: -1 if x is None else x) if fmt == "bar" else None})
    out = {"day": script.get("day"), "dayNo": script.get("dayNo"), "event": ev, "kr": script.get("kr"),
           "heat": script.get("heat"), "heats": script.get("heats"), "total": script.get("total"),
           "cheer": script.get("cheer") or [], "entrants": ents, "format": fmt,
           "roundNo": rnd.get("no"), "roundKey": rnd.get("key"), "roundKr": rnd.get("kr"), "medal": bool(rnd.get("medal")),
           "note": script.get("note") or "", "resultsOnly": fmt == "rank",
           "podium": bool(rnd.get("medal")) and rnd.get("key") != "bronze",
           "budget": OR.slot(ev, rnd.get("key") or "final"), "script": script}
    for kk in ("match", "heights", "after3"):
        if kk in script:
            out[kk] = script[kk]
    out["heatSize"] = len(start)                             # 조 전체 (화면에 고른 사람보다 많을 수 있다)
    if fmt == "trial":                                       # 봅슬레이 '지금 N위': 그때까지 출발한 모든 썰매의 합계로
        out["allTotals"] = [[(e.get("res") or {}).get("order") or (i + 1), (e.get("res") or {}).get("total"),
                             e["entryId"]] for i, e in enumerate(start)]
    if mt:
        out["setStart"] = {"sp": mt[1], "skip": mt[2]}
    if ev == "marathon" and script.get("total"):
        out["note"] = "%d명이 한 번에 출발" % script["total"]
    return out
