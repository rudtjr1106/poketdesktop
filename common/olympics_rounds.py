# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 라운드 (서버가 치르고 앱이 그린다). 하루 한 종목, 그날 예선부터 결승까지 (11/08 사용자 결정).

**참가 수에 맞춰 실제 올림픽처럼 서버가 배정한다** - 종목마다 진행 방식이 다르다:

    100m        8명 조. 예선 -> (준준결승) -> 준결승 -> 결승. 조 상위 k명(Q) + 기록 순(q)
    봅슬레이     1~3차 주행 전원, 4차는 3차까지 합계 상위 20대
    장대높이뛰기  바 올리기 (높이마다 3번, 3번 연속 실패면 탈락). 예선 조 -> 결승 12명
    양궁        랭킹 라운드 72발 -> 1대1 세트제 대진(최대 64) -> 동메달전 · 결승
    원반던지기   예선 조(3번) -> 결승 12명 (3번 뒤 상위 8명 3번 더)
    스키점프     (예선 50) -> 1라운드 -> 결선 30 (거꾸로), 점수 = 비거리 점수 + 자세 점수
    마라톤      한 번에 다 같이

한 번의 시도 · 주행 · 화살은 common/olympics.py 의 공식(적성 · 체형 · 특기 · 응원 · 지침 · 작전 · 운 · 실수)을 그대로 쓴다.
**같은 씨앗이면 같은 대회** - 서버는 그날 한 번 치러 남기고, 앱은 그 결과를 그리기만 한다.

설계: design-notes/2026-11-08-olympics-rounds.md · 계획: design-notes/2026-11-08-olympics-rounds-plan.md
"""
import math
import random

from . import olympics as O

# 레인을 고르는 차례 (가운데부터). 8명이 안 되는 첫 라운드는 앞에서부터 그 수만큼 쓴다.
LANE_PREF = (4, 5, 3, 6, 2, 7, 1, 8)


# ---------------------------------------------------------------- 시드 · 레인 · 진출
def strength_order(entries, rng):
    """실력(기대 점수 exp) 센 순서의 id 목록. 같은 기대 점수는 rng 로 (들어온 차례마다 한 번씩 뽑는다 - 같은 씨앗 같은 순서)."""
    keyed = [(-float(e["exp"]), rng.random(), e["id"]) for e in entries]
    keyed.sort()
    return [k[2] for k in keyed]


def serpentine(ids, h):
    """센 순서의 id 들을 h 조로 뱀 모양 (1조 1위 · 2조 2위 … 다음 줄은 거꾸로). 조 크기 차이 ≤ 1."""
    h = max(1, int(h))
    out = [[] for _ in range(h)]
    for i, x in enumerate(ids):
        row, col = divmod(i, h)
        out[col if row % 2 == 0 else h - 1 - col].append(x)
    return [x for x in out if x]


def lanes(ids, first, rng):
    """{id: 레인}. ids = 센 순서. first(첫 라운드)면 가운데 레인들을 무작위로, 그 뒤 라운드는 세계육상 방식
    (위 넷 3~6 · 다음 둘 7 · 8 · 나머지 1 · 2, 무리 안에서는 무작위). 8명이 안 되면 가운데부터 채운다."""
    ids = list(ids)
    if first:
        pool = sorted(LANE_PREF[:len(ids)])
        rng.shuffle(pool)
        return dict(zip(ids, pool))
    out = {}
    for group, lanes_of in ((ids[:4], [3, 4, 5, 6]), (ids[4:6], [7, 8]), (ids[6:8], [1, 2])):
        pool = list(lanes_of)
        rng.shuffle(pool)
        for x, ln in zip(group, pool):
            out[x] = ln
    extra = [x for x in ids if x not in out]                 # 8명이 넘으면 (없어야 한다) 남은 번호
    for i, x in enumerate(extra):
        out[x] = 9 + i
    return out


def advance(heats, target, key):
    """다음 라운드 진출 {id: 'Q'(조 순위) | 'q'(기록)}. 조마다 key 순 상위 k 명이 Q (k = min(3, target // 조 수),
    적어도 1), 남은 자리는 나머지 모두를 key 순으로 채운다. 진출자는 꼭 target 명 (key 가 같으면 key 에 신청 차례를
    넣어 부르는 쪽이 가른다 - 동점으로 정원을 넘기지 않는다)."""
    h = len(heats)
    if h == 0 or target <= 0:
        return {}
    k = max(1, min(3, target // h))
    qual, rest = [], []
    for hh in heats:
        order = sorted(hh, key=key)
        qual += order[:k]
        rest += order[k:]
    qual.sort(key=key)
    out = dict((x, "Q") for x in qual[:target])
    for x in sorted(rest, key=key)[:max(0, target - len(out))]:
        out[x] = "q"
    return out


# ---------------------------------------------------------------- 공통: 한 번 뛰기
def _mods(event, e, ctx):
    return O.mods(event, e["sp"], e.get("ability"), ctx["pct"], ctx.get("cheer") or (), e.get("fat") or 0.0)


def _play(event, e, ctx, seed):
    return O.play(event, e["sp"], e.get("ability"), e.get("tactic") or "safe", ctx["pct"], ctx.get("cheer") or (),
                  e.get("fat") or 0.0, seed=seed)


def _strong(event, ents, ctx, rng):
    """기대 점수(작전 · 운 빼고) 센 순서의 id 목록."""
    return strength_order([{"id": e["id"], "exp": O.expect(_mods(event, e, ctx))} for e in ents], rng)


def _heat(no, ids, ln, res, q=None):
    return {"no": no, "ids": list(ids), "lanes": ln or {}, "res": res, "q": q or {}}


def _round(no, key, kr, fmt, heats, note=""):
    return {"no": no, "key": key, "kr": kr, "format": fmt, "note": note, "heats": heats}


def _standings(groups):
    """groups = 앞 순위부터 [[(id, 기록), ...], ...] (무리 안은 이미 순위 차례). -> [{id, rank, record}]."""
    out = []
    for g in groups:
        for i, v in g:
            out.append({"id": i, "rank": len(out) + 1, "record": v})
    return out


# ---------------------------------------------------------------- 100m (race)
SPRINT_HEAT = 8


def sprint_plan(n):
    """참가 n 명의 라운드 [{key, kr, target(다음 라운드 인원, 결승은 None)}]. 정원은 결승 8 에서 ×3 씩 (24 · 72 · 216 …).
    N ≤ 8 결승만 · ≤ 24 예선 · 결승 · ≤ 72 + 준결승 · ≤ 216 + 준준결승 · 그 위는 한 단계씩."""
    if n <= 0:
        return []
    if n <= SPRINT_HEAT:
        return [{"key": "final", "kr": "결승", "target": None}]
    caps = [SPRINT_HEAT]
    while caps[-1] < n:
        caps.append(caps[-1] * 3)
    m = len(caps) - 1
    out = []
    for i in range(m + 1):
        back = m - i
        if back == 0:
            key, kr = "final", "결승"
        elif i == 0:
            key, kr = "r1", "예선"
        elif back == 1:
            key, kr = "semi", "준결승"
        elif back == 2:
            key, kr = "qf", "준준결승"
        else:
            key, kr = "r%d" % (i + 1), "%d라운드" % (i + 1)
        out.append({"key": key, "kr": kr, "target": caps[m - 1 - i] if back else None})
    return out


def _note(h, target, next_kr):
    k = max(1, min(3, target // h))
    q = max(0, target - k * h)
    if q:
        return "조 상위 %d명 + 기록 %d명 %s" % (k, q, next_kr)
    return "조 상위 %d명 %s" % (k, next_kr)


def _sprint(event, ents, ctx, rng):
    by = dict((e["id"], e) for e in ents)
    plan = sprint_plan(len(ents))
    cur = _strong(event, ents, ctx, rng)
    rounds, elim = [], []
    for ri, p in enumerate(plan):
        hs = serpentine(cur, int(math.ceil(len(cur) / float(SPRINT_HEAT))))
        heats, allres = [], {}
        for hi, ids in enumerate(hs):
            ln = lanes(ids, ri == 0, rng)
            res = {}
            for i in ids:
                seed = rng.randrange(1 << 30)
                got = _play(event, by[i], ctx, seed)
                t = got["tries"][0]
                res[i] = {"v": got["record"], "slip": bool(t["slip"]), "at": t.get("at"), "seed": seed}
            allres.update(res)
            heats.append(_heat(hi + 1, ids, ln, res))

        def key(i, allres=allres):
            return (O.rank_key(event, allres[i]["v"]), by[i]["order"], i)
        if p["target"]:
            q = advance([h["ids"] for h in heats], p["target"], key)
            for h in heats:
                h["q"] = dict((i, q[i]) for i in h["ids"] if i in q)
            note = _note(len(heats), p["target"], plan[ri + 1]["kr"])
            cur = sorted(q, key=key)
            elim.append([(i, allres[i]["v"]) for i in sorted(allres, key=key) if i not in q])
        else:
            note = ""
            elim.append([(i, allres[i]["v"]) for i in sorted(allres, key=key)])
        rnd = _round(ri + 1, p["key"], p["kr"], "race", heats, note)
        if p["target"]:
            rnd["k"] = max(1, min(3, p["target"] // len(heats)))     # 조 상위 k명 = Q (중계 결과판이 바로 표시)
        rounds.append(rnd)
    return rounds, _standings(reversed(elim))


# ---------------------------------------------------------------- 마라톤 (race, 한 번에 다 같이)
def _marathon(event, ents, ctx, rng):
    by = dict((e["id"], e) for e in ents)
    ids = _strong(event, ents, ctx, rng)                    # 출발선 자리 (앞줄 = 센 선수)
    res = {}
    for i in ids:
        seed = rng.randrange(1 << 30)
        got = _play(event, by[i], ctx, seed)
        t = got["tries"][0]
        res[i] = {"v": got["record"], "slip": bool(t["slip"]), "at": t.get("at"), "seed": seed}
    order = sorted(ids, key=lambda i: (O.rank_key(event, res[i]["v"]), by[i]["order"], i))
    heat = _heat(1, ids, {}, res)
    return [_round(1, "final", "결승", "race", [heat], "%d명이 한 번에 출발" % len(ids))], \
        _standings([[(i, res[i]["v"]) for i in order]])


# ---------------------------------------------------------------- 봅슬레이 (trial, 네 번 주행)
BOB_RUNS = 4
BOB_LAST = 20               # 4차를 타는 썰매 (3차까지 합계 상위)
BOB_GROUP = 6               # 1차 출발 순서를 뽑는 묶음 (센 순서로 6대씩, 묶음 안에서 무작위)


def _bobsled(event, ents, ctx, rng):
    by = dict((e["id"], e) for e in ents)
    strong = _strong(event, ents, ctx, rng)
    order = []
    for k in range(0, len(strong), BOB_GROUP):
        g = strong[k:k + BOB_GROUP]
        rng.shuffle(g)
        order += g
    total = dict((i, 0.0) for i in strong)
    rounds, done3 = [], None

    def tkey(i):
        return (round(total[i], 2), by[i]["order"], i)
    for run in range(1, BOB_RUNS + 1):
        res = {}
        for pos, i in enumerate(order):
            seed = rng.randrange(1 << 30)
            got = _play(event, by[i], ctx, seed)
            v = got["record"]
            total[i] = round(total[i] + v, 2)
            res[i] = {"v": v, "total": total[i], "slip": bool(got["tries"][0]["slip"]), "seed": seed, "order": pos + 1}
        q = {}
        if run == BOB_RUNS - 1:
            done3 = dict(total)
            top = sorted(order, key=tkey)[:BOB_LAST]
            q = dict((i, "Q") for i in top)
        rounds.append(_round(run, "run%d" % run, "%d차 주행" % run, "trial", [_heat(1, order, {}, res, q)],
                             "3차까지 합계 상위 %d대가 4차 주행" % BOB_LAST if run == BOB_RUNS - 1 else ""))
        if run == 1:
            order = sorted(order, key=lambda i: (res[i]["v"], by[i]["order"], i))
        elif run == 2:
            order = sorted(order, key=tkey, reverse=True)
        elif run == 3:
            order = sorted(q, key=tkey, reverse=True)
    last = rounds[-1]["heats"][0]["ids"]
    rest = [i for i in strong if i not in set(last)]
    return rounds, _standings([[(i, total[i]) for i in sorted(last, key=tkey)],
                               [(i, done3[i]) for i in sorted(rest, key=lambda i: (done3[i], by[i]["order"], i))]])


# ---------------------------------------------------------------- 원반던지기 (field, 예선 조 -> 결승 12, 3 + 3)
FIELD_FINAL = 12            # 결승 정원 (원반 · 장대)
FIELD_TOP = 8               # 원반 결승 3번 뒤 3번 더 던지는 사람
QUAL_GROUP = 20             # 예선 조 크기 기준 (조 수 = max(2, ceil(N / 20)))


def _field_key(event, tries, order, i):
    """시기형 순위 키: 가장 좋은 기록 → 둘째 → 셋째 … → 신청 차례."""
    vals = sorted(O.rank_key(event, t["v"]) for t in tries if t.get("v") is not None)
    return (vals + [float("inf")] * (6 - len(vals)), order, i)


def _throws(event, e, ctx, rng):
    seed = rng.randrange(1 << 30)
    got = _play(event, e, ctx, seed)
    return [{"v": t["v"], "slip": bool(t["slip"])} for t in got["tries"]], seed


def _groups(strong, n, rng):
    g = max(2, int(math.ceil(n / float(QUAL_GROUP))))
    hs = serpentine(strong, g)
    for h in hs:
        rng.shuffle(h)                                       # 조 안 시기 차례는 추첨
    return hs


def _discus(event, ents, ctx, rng):
    by = dict((e["id"], e) for e in ents)
    strong = _strong(event, ents, ctx, rng)
    rounds, rest = [], []
    finalists = list(strong)
    if len(ents) > FIELD_FINAL:
        heats, qres = [], {}
        for hi, ids in enumerate(_groups(strong, len(ents), rng)):
            res = {}
            for i in ids:
                tr, seed = _throws(event, by[i], ctx, rng)
                res[i] = {"tries": tr, "v": O.best_of(event, [t["v"] for t in tr]), "seed": seed}
            qres.update(res)
            heats.append(_heat(hi + 1, ids, {}, res))

        def qkey(i):
            return _field_key(event, qres[i]["tries"], by[i]["order"], i)
        finalists = sorted(qres, key=qkey)[:FIELD_FINAL]
        for h in heats:
            h["q"] = dict((i, "q") for i in h["ids"] if i in finalists)
        rounds.append(_round(1, "qual", "예선", "field", heats, "상위 %d명 결승" % FIELD_FINAL))
        rest = [(i, qres[i]["v"]) for i in sorted(qres, key=qkey) if i not in finalists]
    order = list(finalists)
    rng.shuffle(order)
    res = {}
    for i in order:
        tr, seed = _throws(event, by[i], ctx, rng)
        res[i] = {"tries": tr, "v": O.best_of(event, [t["v"] for t in tr]), "seed": seed}

    def fkey(i):
        return _field_key(event, res[i]["tries"], by[i]["order"], i)
    after3 = []
    if order:
        top = sorted(order, key=fkey)[:FIELD_TOP]
        after3 = sorted(top, key=fkey, reverse=True)         # 4~6번째: 선두가 마지막
        for i in after3:
            tr, seed = _throws(event, by[i], ctx, rng)
            res[i]["tries"] += tr
            res[i]["seed2"] = seed
            res[i]["v"] = O.best_of(event, [t["v"] for t in res[i]["tries"]])
    heat = _heat(1, order, {}, res)
    heat["after3"] = after3
    rounds.append(_round(len(rounds) + 1, "final", "결승", "field", [heat],
                         "3번 뒤 상위 %d명이 3번 더" % min(FIELD_TOP, len(order))))
    return rounds, _standings([[(i, res[i]["v"]) for i in sorted(order, key=fkey)], rest])


# ---------------------------------------------------------------- 장대높이뛰기 (bar, 바 올리기)
POLE_TRIES = 3              # 한 높이에 시도 (3번 연속 실패면 탈락)
POLE_STEP = (0.10, 0.05)    # 바를 올리는 폭: 남은 선수가 POLE_FEW 명보다 많으면 10cm, 그 아래면 5cm (실제 대회처럼 끝으로 갈수록 잘게)
POLE_FEW = 3
# 첫 높이 = 그 조(결승)의 기대 점수 아래쪽 몫(POLE_START_Q)에서 이만큼 뺀 높이를 10cm 단위로 내린 것.
# 가장 약한 선수에 맞추면 결승이 높이 20개 가까이 이어진다 (11/08 시뮬레이션) - 실제 결승은 8~12개.
POLE_START_Q = {"qual": (0.10, 0.06), "final": (0.25, 0.04)}


def pole_key(res, order, i):
    """장대 순위 키: 넘은 높이 → 그 높이에서 실패 수 → 전체 실패 수 → 신청 차례 (점프오프는 하지 않는다)."""
    v = res.get("v")
    att = res.get("att") or []
    if v is None:
        return (float("inf"), 0, 0, order, i)
    at_v = sum(1 for h, r in att if r == "x" and abs(h - v) < 1e-9)
    return (-v, at_v, sum(1 for _h, r in att if r == "x"), order, i)


def _vault(event, m, tactic, rng):
    """한 번 뛸 때 넘을 수 있는 높이 (실수 = 파울이면 None). 공식은 O.tries 의 한 시도와 같다."""
    t = O.TACTICS.get(tactic) or O.TACTICS["safe"]
    luck = max(-O.LUCK_CAP, min(O.LUCK_CAP, rng.gauss(0, t["sd"])))
    if rng.random() < t["slip"]:
        return None
    return O.record_of(event, O.expect(m) + t["plus"] + luck)


def _start_h(exps, kind):
    q, back = POLE_START_Q[kind]
    v = sorted(exps)[int(q * (len(exps) - 1))]
    return max(3.5, math.floor(O.EV["pole"]["base"] * (v - back) * 10 + 1e-9) / 10.0)


def _bar(event, ids, by, ms, start, rng):
    """한 조의 바 올리기. -> (res {id: {att, v}}, 높이 목록). 모두 탈락할 때까지 (남은 한 명도 끝까지)."""
    res = dict((i, {"att": [], "v": None}) for i in ids)
    alive, heights, h = list(ids), [], start
    while alive and h <= 7.5:
        heights.append(h)
        pending = list(alive)
        for _t in range(POLE_TRIES):
            nxt = []
            for i in pending:
                got = _vault(event, ms[i], by[i].get("tactic"), rng)
                ok = got is not None and got >= h - 1e-9
                res[i]["att"].append([h, "o" if ok else "x"])
                if ok:
                    res[i]["v"] = h
                else:
                    nxt.append(i)
            pending = nxt
        alive = [i for i in alive if i not in pending]
        h = round(h + POLE_STEP[0 if len(alive) > POLE_FEW else 1], 2)
    return res, heights


def _pole(event, ents, ctx, rng):
    by = dict((e["id"], e) for e in ents)
    ms = dict((e["id"], _mods(event, e, ctx)) for e in ents)
    exp = dict((i, O.expect(m)) for i, m in ms.items())
    strong = _strong(event, ents, ctx, rng)
    rounds, rest = [], []
    finalists = list(strong)
    if len(ents) > FIELD_FINAL:
        heats, qres = [], {}
        for hi, ids in enumerate(_groups(strong, len(ents), rng)):
            res, hts = _bar(event, ids, by, ms, _start_h([exp[i] for i in ids], "qual"), rng)
            qres.update(res)
            hh = _heat(hi + 1, ids, {}, res)
            hh["heights"] = hts
            heats.append(hh)

        def qkey(i):
            return pole_key(qres[i], by[i]["order"], i)
        finalists = sorted(qres, key=qkey)[:FIELD_FINAL]
        for h in heats:
            h["q"] = dict((i, "q") for i in h["ids"] if i in finalists)
        rounds.append(_round(1, "qual", "예선", "bar", heats, "상위 %d명 결승" % FIELD_FINAL))
        rest = [(i, qres[i]["v"]) for i in sorted(qres, key=qkey) if i not in finalists]
    order = list(finalists)
    rng.shuffle(order)
    res, hts = _bar(event, order, by, ms, _start_h([exp[i] for i in order], "final"), rng)
    heat = _heat(1, order, {}, res)
    heat["heights"] = hts
    rounds.append(_round(len(rounds) + 1, "final", "결승", "bar", [heat], "높이마다 3번, 3번 연속 실패면 탈락"))

    def fkey(i):
        return pole_key(res[i], by[i]["order"], i)
    return rounds, _standings([[(i, res[i]["v"]) for i in sorted(order, key=fkey)], rest])


# ---------------------------------------------------------------- 양궁 (rank -> match 대진)
ARCHERY_RANK_ARROWS = 72
ARCHERY_BRACKET = 64
ARCHERY_WIN = 6             # 세트 점수 6 을 먼저 내면 승
ARCHERY_SETS = 5            # 5세트 뒤 5:5 면 슛오프
# 양궁 전용 작전 (11/08 검토): 여러 발을 쏘면 운이 고르게 섞여 기대값이 다 정한다 - 다른 종목 값(실수 5% / 15%)을 화살마다
# 쓰면 안정이 늘 이기고, 실수를 빼면 승부수(+3%)가 늘 이긴다. 같은 실력 20명에서 상위 8시드 · 금메달의 승부수 비율을
# 맞춘 값 (archery_tactic_share, tools/olympic_archery_sim.py). 1대1 경기는 흔들림이 큰 쪽에 유리해서 두 비율이 늘
# 0.2 쯤 벌어진다 - 랭킹은 안정이(승부수 0.41), 금메달은 승부수가(0.61) 조금 앞서게 둘 다 가운데 가까이 두었다.
ARCHERY_TACTICS = {"safe": {"plus": 0.0, "sd": 0.05, "slip": 0.0},
                   "bold": {"plus": 0.02, "sd": 0.08, "slip": 0.025}}
ROUND_OF = {64: ("r64", "64강"), 32: ("r32", "32강"), 16: ("r16", "16강"), 8: ("qf", "8강"), 4: ("sf", "준결승")}


def bracket_order(b):
    """b 강 대진표에서 위에서부터의 시드 (1 · b · b/2 · b/2+1 …) - 1 · 2 시드는 결승에서만 만난다."""
    out = [1]
    while len(out) < b:
        k = len(out) * 2
        out = [x for s_ in out for x in (s_, k + 1 - s_)]
    return out


def _arrow(exp, tac, rng):
    """화살 하나 -> (점수 0~10 (빗나감 0), X 인가, 가운데에서의 값 r)."""
    t = ARCHERY_TACTICS.get(tac) or ARCHERY_TACTICS["safe"]
    luck = max(-O.LUCK_CAP, min(O.LUCK_CAP, rng.gauss(0, t["sd"])))
    r = exp + t["plus"] + luck
    if rng.random() < t["slip"]:
        return 0, False, r
    return O.arrow_points(r), r >= O.ARROW_X, r


def _match(a, b, exp, tac, rng):
    sets, sp = [], [0, 0]
    while max(sp) < ARCHERY_WIN and len(sets) < ARCHERY_SETS:
        aa = [_arrow(exp[a], tac[a], rng)[0] for _k in range(3)]
        bb = [_arrow(exp[b], tac[b], rng)[0] for _k in range(3)]
        sets.append([aa, bb])
        if sum(aa) > sum(bb):
            sp[0] += 2
        elif sum(bb) > sum(aa):
            sp[1] += 2
        else:
            sp[0] += 1
            sp[1] += 1
    shoot = None
    if sp[0] == sp[1]:
        while True:                                          # 한 발씩, 가운데에 더 가까운 쪽 (원래 값 r 이 큰 쪽)
            ra, rb = _arrow(exp[a], tac[a], rng), _arrow(exp[b], tac[b], rng)
            ka = ra[2] if ra[0] else -9.0
            kb = rb[2] if rb[0] else -9.0
            if abs(ka - kb) > 1e-9:
                shoot = [ra[0], rb[0]]
                win = a if ka > kb else b
                break
    else:
        win = a if sp[0] > sp[1] else b
    return {"ids": [a, b], "sets": sets, "sp": sp, "shoot": shoot, "win": win}


def _archery(event, ents, ctx, rng):
    by = dict((e["id"], e) for e in ents)
    exp = dict((e["id"], O.expect(_mods(event, e, ctx))) for e in ents)
    tac = dict((e["id"], e.get("tactic") or "safe") for e in ents)
    ids = [e["id"] for e in ents]
    res = {}
    for i in ids:
        tot = tens = xs = 0
        for _k in range(ARCHERY_RANK_ARROWS):
            p_, x_, _r = _arrow(exp[i], tac[i], rng)
            tot += p_
            tens += p_ == 10
            xs += x_
        res[i] = {"v": tot, "tens": tens, "x": xs, "arrows": ARCHERY_RANK_ARROWS}

    def rkey(i):
        return (-res[i]["v"], -res[i]["tens"], -res[i]["x"], by[i]["order"], i)
    seeds = sorted(ids, key=rkey)
    n = len(ids)
    b = ARCHERY_BRACKET if n >= ARCHERY_BRACKET else (2 ** int(math.ceil(math.log(n, 2))) if n > 1 else 1)
    inb = seeds[:b]
    rk = _heat(1, seeds, {}, res, dict((i, "Q") for i in inb) if n > 1 else {})
    rounds = [_round(1, "rank", "랭킹 라운드", "rank", [rk], "%d발 합계로 시드 · 상위 %d명 대진" % (ARCHERY_RANK_ARROWS, b))]
    if n == 1:
        return rounds, _standings([[(ids[0], res[ids[0]]["v"])]])
    seed_of = dict((i, k + 1) for k, i in enumerate(seeds))
    slot = [inb[sd - 1] if sd <= len(inb) else None for sd in bracket_order(b)]
    lost = []                                                # 진 라운드마다 [(id, 세트 점수)]
    size, sf_losers = b, []
    while size >= 2:
        nxt, heats, out = [], [], []
        for k in range(0, size, 2):
            a, c = slot[k], slot[k + 1]
            if a is None or c is None:
                nxt.append(a if a is not None else c)
                continue
            m = _match(a, c, exp, tac, rng)
            hh = _heat(len(heats) + 1, [a, c], {}, {a: {"v": m["sp"][0]}, c: {"v": m["sp"][1]}}, {m["win"]: "Q"})
            hh["match"] = m
            heats.append(hh)
            nxt.append(m["win"])
            loser = c if m["win"] == a else a
            out.append((loser, m["sp"][1] if m["win"] == a else m["sp"][0]))
        if size == 2:
            key, kr = "final", "결승"
        else:
            key, kr = ROUND_OF[size]
        if heats:
            if size == 2:
                for h in heats:
                    h["q"] = {}
            rounds.append(_round(len(rounds) + 1, key, kr, "match", heats))
        if size == 4:
            sf_losers = [x for x, _sp in out]
        if size == 2:
            final_heats = heats
        else:
            lost.append(out)
        slot = nxt
        size //= 2
    places = []
    fm = final_heats[0]["match"]
    places += [(fm["win"], None), ([i for i in fm["ids"] if i != fm["win"]][0], None)]
    if len(sf_losers) == 2:
        bm = _match(sf_losers[0], sf_losers[1], exp, tac, rng)
        bh = _heat(1, list(bm["ids"]), {}, {bm["ids"][0]: {"v": bm["sp"][0]}, bm["ids"][1]: {"v": bm["sp"][1]}})
        bh["match"] = bm
        rounds.insert(len(rounds) - 1, _round(0, "bronze", "동메달 결정전", "match", [bh]))
        places += [(bm["win"], None), ([i for i in bm["ids"] if i != bm["win"]][0], None)]
        lost = lost[:-1]                                     # 4강 패자는 동메달전으로 자리를 정했다
    for r_no, rr in enumerate(rounds):
        rr["no"] = r_no + 1
    groups = [[(i, res[i]["v"]) for i, _v in places]]
    for out in reversed(lost):
        groups.append([(i, res[i]["v"]) for i, _sp in sorted(out, key=lambda x: (-x[1], seed_of[x[0]]))])
    groups.append([(i, res[i]["v"]) for i in seeds[b:]])
    return rounds, _standings(groups)


def archery_tactic_share(trials=200, seed=1, n=20):
    """같은 실력 n 명(작전 반반)으로 trials 번 - 상위 8시드 · 금메달의 승부수 비율 {seed8, gold}."""
    rng = random.Random(seed)
    s8 = gold = 0
    pct = {"archery": {"X": 0.5}}
    for t in range(trials):
        ents = [{"id": k + 1, "sp": {"internal": "X", "kg": 50, "types": []}, "ability": None,
                 "tactic": "bold" if k % 2 else "safe", "fat": 0.0, "order": k} for k in range(n)]
        comp = run("archery", ents, {"pct": pct, "cheer": (), "seed": rng.randrange(1 << 30)})
        rk = comp["rounds"][0]["heats"][0]["ids"]
        s8 += sum(1 for i in rk[:8] if i % 2 == 0)
        gold += comp["standings"][0]["id"] % 2 == 0
    return {"seed8": round(s8 / (8.0 * trials), 3), "gold": round(gold / float(trials), 3)}


# ---------------------------------------------------------------- 스키점프 (ski, 노멀힐 K 120)
SKI_K = 120.0
SKI_METER = 2.0             # 노멀힐: 1m 에 2점, K점에서 60점
SKI_QUAL = 50               # N 이 이보다 많으면 예선으로 50명
SKI_FINAL = 30              # 결선 라운드


def ski_points(dist, judges):
    """(자세 점수, 점프 점수). 자세 = 심판 다섯 가운데 가장 높은 것 · 낮은 것을 뺀 셋의 합. 비거리 점수는 0 아래로 안 간다."""
    js = sorted(float(j) for j in judges)
    style = round(sum(js[1:4]), 1)
    return style, round(max(0.0, 60.0 + (float(dist) - SKI_K) * SKI_METER) + style, 1)


def _half(x):
    return round(x * 2) / 2.0


def _jump(event, e, ms, rng):
    t = O.TACTICS.get(e.get("tactic")) or O.TACTICS["safe"]
    exp = O.expect(ms)
    luck = max(-O.LUCK_CAP, min(O.LUCK_CAP, rng.gauss(0, t["sd"])))
    slip = rng.random() < t["slip"]
    r = exp + t["plus"] + luck - (O.SLIP if slip else 0.0)
    dist = O.record_of(event, r)
    if slip:                                                 # 착지에서 손을 짚거나 넘어짐
        judges = [max(6.0, min(13.0, _half(rng.gauss(10.0, 1.0)))) for _k in range(5)]
    else:
        c = 17.0 + 2.5 * max(0.0, min(1.0, (r - 0.95) / 0.25))
        judges = [max(14.0, min(20.0, _half(rng.gauss(c, 0.5)))) for _k in range(5)]
    style, pts = ski_points(dist, judges)
    return {"dist": dist, "judges": judges, "style": style, "pts": pts, "v": pts, "slip": slip}


def _ski(event, ents, ctx, rng):
    by = dict((e["id"], e) for e in ents)
    ms = dict((e["id"], _mods(event, e, ctx)) for e in ents)
    strong = _strong(event, ents, ctx, rng)
    rounds, groups = [], []

    def jump_all(order):
        res = {}
        for i in order:
            res[i] = _jump(event, by[i], ms[i], rng)
        return res

    def key(res):
        return lambda i: (-res[i]["pts"], by[i]["order"], i)
    field = list(strong)
    if len(field) > SKI_QUAL:
        order = list(reversed(field))                         # 약한 선수부터
        res = jump_all(order)
        keep = sorted(order, key=key(res))[:SKI_QUAL]
        rounds.append(_round(1, "qual", "예선", "ski", [_heat(1, order, {}, res, dict((i, "q") for i in keep))],
                             "상위 %d명 1라운드" % SKI_QUAL))
        groups.append([(i, res[i]["pts"]) for i in sorted(order, key=key(res)) if i not in keep])
        field = sorted(keep, key=lambda i: strong.index(i))
    order = list(reversed(field))
    r1 = jump_all(order)
    fin_ids = sorted(order, key=key(r1))[:SKI_FINAL]
    rounds.append(_round(len(rounds) + 1, "r1", "1라운드", "ski", [_heat(1, order, {}, r1, dict((i, "q") for i in fin_ids))],
                         "상위 %d명 결선 라운드" % SKI_FINAL))
    groups.append([(i, r1[i]["pts"]) for i in sorted(order, key=key(r1)) if i not in fin_ids])
    forder = list(reversed(fin_ids))                         # 1라운드 1위가 마지막
    fres = jump_all(forder)
    for i in forder:
        fres[i]["total"] = round(r1[i]["pts"] + fres[i]["pts"], 1)
    rounds.append(_round(len(rounds) + 1, "final", "결선 라운드", "ski", [_heat(1, forder, {}, fres)],
                         "두 번 점수 합으로 순위"))
    tkey = lambda i: (-fres[i]["total"], by[i]["order"], i)      # noqa: E731
    groups.append([(i, fres[i]["total"]) for i in sorted(forder, key=tkey)])
    return rounds, _standings(reversed(groups))


ENGINES = {"sprint": _sprint, "marathon": _marathon, "bobsled": _bobsled, "discus": _discus, "pole": _pole,
           "archery": _archery, "ski": _ski}


def _place_key(event, fmt, res, order, i):
    """조 안 순위 키 - 엔진이 진출 · 순위를 정할 때 쓰는 것과 같다 (같은 기록이면 먼저 신청한 쪽)."""
    if fmt == "trial":
        return (round(res.get("total") or 1e9, 2), order, i)
    if fmt == "field":
        return _field_key(event, res.get("tries") or [], order, i)
    if fmt == "bar":
        return pole_key(res, order, i)
    if fmt == "rank":
        return (-(res.get("v") or 0), -(res.get("tens") or 0), -(res.get("x") or 0), order, i)
    if fmt == "ski":
        return (-float(res.get("total", res.get("pts")) or 0), order, i)
    return (O.rank_key(event, res.get("v")), order, i)


def _add_places(event, rounds, order_of):
    """조마다 place {id: 조 안 순위} - 앱 · 결과표가 다시 셈하지 않는다 (동점 처리가 서버와 어긋나지 않게)."""
    for rnd in rounds:
        for h in rnd["heats"]:
            if rnd["format"] == "match":
                win = (h.get("match") or {}).get("win")
                order = sorted(h["ids"], key=lambda i: i != win)
            else:
                order = sorted(h["ids"], key=lambda i: _place_key(event, rnd["format"], h["res"].get(i) or {},
                                                                  order_of.get(i, 0), i))
            h["place"] = dict((i, k) for k, i in enumerate(order, 1))


def run(event, entries, ctx):
    """그 종목 대회 하나를 치른다. entries = [{id, sp, ability, tactic, fat, order}], ctx = {pct, cheer, seed}.
    -> {event, n, rounds, standings}. 같은 entries · ctx 면 같은 결과. 조마다 place(조 안 순위)를 싣는다."""
    rng = random.Random(int(ctx.get("seed") or 0))
    ents = sorted(entries, key=lambda e: (e["order"], e["id"]))
    if not ents:
        return {"event": event, "n": 0, "rounds": [], "standings": []}
    rounds, standings = ENGINES[event](event, ents, ctx, rng)
    _add_places(event, rounds, dict((e["id"], e["order"]) for e in ents))
    return {"event": event, "n": len(ents), "rounds": rounds, "standings": standings}


# ---------------------------------------------------------------- 중계 시각표
FIRST_AT = 20               # 14:00 부터 첫 라운드 중계까지 (초)
GAP = 10                    # 라운드 사이 쉬는 틈
PODIUM = 12                 # 메달 라운드에 더하는 시상식
# 라운드 하나의 중계 칸 (초). 한 사람이 보는 것은 '내 조' 하나 - 조가 커도 장면이 내 포켓몬 · 앞선 몇 명만 고르기 때문에
# 칸은 형식 · 라운드로만 정한다. 장면 길이 ≤ 칸 은 앱 검사(budget)가 본다.
SLOTS = {
    "race": {"*": 75, "final": 75},
    "marathon": {"*": 140},
    "trial": {"*": 32, "run4": 60},
    "field": {"qual": 60, "final": 110},
    "bar": {"qual": 70, "final": 110},
    "rank": {"*": 30},
    "match": {"*": 45, "bronze": 60, "final": 80},
    "ski": {"qual": 30, "r1": 45, "final": 85},
}
_FORMAT = {"sprint": "race", "marathon": "marathon", "bobsled": "trial", "discus": "field", "pole": "bar",
           "archery": None, "ski": "ski"}


def slot(event, key):
    """그 라운드의 중계 칸 (초, 메달 라운드는 시상식 포함)."""
    fmt = _FORMAT.get(event)
    if fmt is None:                                          # 양궁: 랭킹은 rank, 나머지는 match
        fmt = "rank" if key == "rank" else "match"
    t = SLOTS[fmt]
    n = t.get(key, t.get("*", 60))
    return n + (PODIUM if key in ("final", "run4") or (event == "marathon") else 0)


def program(comp):
    """(시각표 [{round, at, len}], end) - 14:00 부터 초. 라운드 결과 공개 = 다음 라운드 at (마지막은 end)."""
    out, at = [], FIRST_AT
    for r in comp.get("rounds") or []:
        ln = slot(comp["event"], r["key"])
        out.append({"round": r["no"], "at": at, "len": ln})
        at += ln + GAP
    if not out:
        return [], 0
    return out, out[-1]["at"] + out[-1]["len"]
