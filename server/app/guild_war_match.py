# -*- coding: utf-8 -*-
"""길드전 1:1 맞대결 (시즌 7 부터) — 지도 땅따먹기 대신 클래시 오브 클랜식 맞대결.

2026-11-12 사용자: "클래시 오브 클랜처럼 지역전 말고 그냥 1:1 매치로 하는 것 어때? 인원 수 비슷한 길드끼리 가고
공격권은 모두 2회 공평하게 가져가고 인원당." 결정: 인원은 비슷하게 · 전쟁 기간 그대로 · 짝 없는 길드는 삼각 순환전 ·
시즌 7 부터. 설계 design-notes/2026-11-12-guild-war-1v1.md (로컬). guild_war.py 가 시즌 번호로 이쪽으로 갈래를 나눈다
(match_mode) - 시즌 6 까지는 지도전이 그대로다.

## 일정 (그대로)

신청 3일 · 전략 4일 · 전쟁 6일 · 결산 1일. 신청 · 팀 짜기 · 명단 고정(_lock_guild) · 전쟁 시작 때 팀 다시 고정(_freeze)
은 지도전과 같다. 지도를 나누던 자리(_deal)에서 **상대를 정한다** (lock).

## 매칭 (pairing)

출전 인원순으로 세우고 **인원 차의 합이 가장 작게** 이웃끼리 짝짓는다. 길드 수가 홀수면 세 길드를 **삼각형** 하나로
(A 가 B 를 치고, B 가 C 를, C 가 A 를 - 모두 한 길드만 치고 한 길드에게만 맞는다). 인원이 같은 길드끼리는 서로 바꿔
**지난 시즌 상대를 피하고**, 그다음 **방어팀 전력 평균이 가깝게** 한다.

한 판(짝 · 삼각형)에서 큰 길드의 출전 인원은 **가장 작은 길드 x CAP_RATIO (반올림)** 까지 (cap_of). 넘는 길드는
방어팀이 센 사람부터 cap 명이 나가고 나머지는 쉰다 (guild_war_team.bench). 길드장이 전략 기간에 바꿀 수 있다
(set_roster). 쉬는 사람은 공격도 방어도 안 한다.

## 공격

출전한 사람마다 EACH(2)번. 넘겨줄 수 없다. **칠 길드의 출전 명단 누구든**, 단 **내가 같은 사람을 두 번 칠 수는
없다** (여러 길드원이 같은 사람을 치는 것은 된다 · 동시에 여러 판이 열려도 된다). 판은 지도전과 같은 관장 배틀 창 ·
war AI · 관전 · 조커 · 앞 SHOWN 마리 미리보기 · 기여 코인. gym_battle.region = "gw:시즌:u<방어자>".

## 별 · 승패

    ★    상대 방어팀의 절반 이상을 쓰러뜨림 (져도)
    ★★   이김
    ★★★  이기고 내 공격팀이 절반 이상 서 있음

판이 어떻게 끝나든(기권 · 시간 초과) 그때까지 쓰러뜨린 수로 센다. **방어자 한 명당 가장 잘한 공격 하나만**
(별 → 쓰러뜨린 비율). 길드 성적 = 별 % (얻은 별 / 3 x 상대 출전 인원) → 쓰러뜨린 비율(방어자마다 최고 공격의
쓰러뜨린 마릿수 / 방어팀 마릿수, 의 평균). **내 성적(칠 길드에게서) 대 나를 친 길드의 성적(나에게서)** 을 견준다 -
1:1 이면 서로, 삼각형이면 두 상대가 다르다. 같으면 비긴다.

## 보상 = 길드 코인만 (2026-11-12 사용자 - design-notes/2026-11-12-guild-war-rewards.md)

1:1 에서는 모든 길드가 서로 붙지 않아서 '전체 1등' 이 진짜 1등이 아니다 - **순위 보상(순위 코인 · 금관 같은 꾸미기 ·
칭호 · 기술머신 뽑기권)이 없다.** 순위표 대신 이번 시즌 맞대결 목록(matches)을 보여 준다.

    판이 끝날 때    공격한 사람: 그 판의 별 ★ 20 · ★★ 40 · ★★★ 60 (+ 조커를 이기면 GW.CONTRIB_JOKER)
                    지킨 사람: 공격팀을 다 쓰러뜨려 막아 내면 GW.CONTRIB_DEFEND (기권 · 시간 초과는 없음)
                    - 둘 다 한 사람 한 시즌 GW.CONTRIB_MAX(300) 까지 (guild_war_team.earned, 지도전의 기여 보상 자리)
    결산            한 번이라도 공격한 사람: 그 길드의 판 결과로 이김 100 · 비김 60 · 짐 30 (상한 밖)
"""
import hashlib
import json
import random
from fractions import Fraction

from fastapi import HTTPException

from common import trainer_battle as TB

from . import db, deps, friendly, gimmick, guild, mega, pvp, season, watchers
from . import guild_war as GW

EACH = 2                      # 출전한 사람마다 공격 수
CAP_RATIO = 1.2               # 한 판의 출전 상한 = 가장 작은 길드 x 이것 (반올림)
STAR_COINS = (0, 20, 40, 60)  # 판마다 공격한 사람이 받는 길드 코인 (그 판의 별 0~3)
RESULT_COINS = {"win": 100, "draw": 60, "lose": 30}   # 결산 - 한 번이라도 공격한 사람 (그 길드의 판 결과)
STAR_RULES = ["상대 방어팀 절반 이상 쓰러뜨림", "이김", "이기고 내 팀 절반 이상 남음"]
RESULT_KR = {"win": "승리", "lose": "패배", "draw": "무승부"}
ONLY = "이번 시즌 길드전은 1:1 맞대결입니다. 앱을 새 판으로 올려 주세요."


# ---------------------------------------------------------------- 매칭 (순수)
def cap_of(sizes):
    """한 판의 출전 상한. 가장 큰 길드가 넘지 않으면 None."""
    sizes = list(sizes)
    if not sizes:
        return None
    c = int(min(sizes) * CAP_RATIO + 0.5)
    return c if max(sizes) > c else None


def _edges(g):
    """한 판의 맞붙는 길드 쌍 (짝은 하나, 삼각형은 셋)."""
    if len(g) == 2:
        return [(g[0], g[1])]
    return [(g[0], g[1]), (g[1], g[2]), (g[2], g[0])]


def _cost(groups, last):
    """묶음 전체의 값 (작을수록 좋다): (인원 차 합, 지난 시즌 상대와 다시 붙는 수, 전력 차 합)."""
    size = again = gap = 0
    for g in groups:
        ns = [x[1] for x in g]
        size += max(ns) - min(ns)
        again += sum(1 for a, b in _edges(g) if b[0] in last.get(a[0], ()) or a[0] in last.get(b[0], ()))
        ps = [x[2] for x in g]
        gap += max(ps) - min(ps)
    return size, again, round(gap, 6)


def pairing(rows, last=None):
    """rows = [(길드, 출전 인원, 방어팀 전력 평균)], last = {길드: 지난 시즌 상대 집합}.
    -> [[a, b] | [a, b, c]] (각 원소는 rows 의 튜플). 삼각형은 a -> b -> c -> a. 2곳 미만이면 [].

    1) 인원 큰 순(같으면 전력 · 번호)으로 세우고 **연속한 묶음**으로 인원 차 합을 가장 작게 (짝 = 두 길드의 차,
       삼각형 = 셋의 최대 - 최소, 홀수일 때만 삼각형 하나). 인원 차만 보면 연속 묶음이 늘 가장 좋다.
    2) 두 묶음의 길드를 맞바꿔 보며 (인원 차 합, 지난 상대와 다시 붙는 수, 전력 차) 가 나아지면 바꾼다. 1) 이 인원 차
       합의 가장 작은 값이라 인원 차는 늘지 않고, 같은 인원 차 안에서 이웃이 아닌 짝도 견준다 ((8,5)(6,6) 처럼 -
       11/12 검토). 길드가 스무 곳 남짓이라 맞바꾸기 한 바퀴가 수백 번이다."""
    last = last or {}
    n = len(rows)
    if n < 2:
        return []
    order = sorted(rows, key=lambda r: (-r[1], -r[2], r[0]))
    tri = n % 2 == 1
    best = {(0, False): (0, [])}
    for i in range(2, n + 1):
        for t in (False, True):
            cands = []
            if (i - 2, t) in best:
                c, g = best[(i - 2, t)]
                grp = order[i - 2:i]
                cands.append((c + grp[0][1] - grp[1][1], g + [list(grp)]))
            if t and i >= 3 and (i - 3, False) in best:
                c, g = best[(i - 3, False)]
                grp = order[i - 3:i]
                cands.append((c + grp[0][1] - grp[2][1], g + [list(grp)]))
            if cands:
                best[(i, t)] = min(cands, key=lambda x: x[0])
    groups = [list(g) for g in best[(n, tri)][1]]
    # 맞바꾸기 (나아질 때만, 유한 번)
    for _ in range(100):
        now = _cost(groups, last)
        better = None
        for gi in range(len(groups)):
            for ai in range(len(groups[gi])):
                for gj in range(gi + 1, len(groups)):
                    for bj in range(len(groups[gj])):
                        a, b = groups[gi][ai], groups[gj][bj]
                        groups[gi][ai], groups[gj][bj] = b, a
                        c = _cost(groups, last)
                        groups[gi][ai], groups[gj][bj] = a, b
                        if c < now and (better is None or c < better[0]):
                            better = (c, gi, ai, gj, bj)
        if not better:
            break
        _c, gi, ai, gj, bj = better
        groups[gi][ai], groups[gj][bj] = groups[gj][bj], groups[gi][ai]
    return [sorted(g, key=lambda r: (-r[1], -r[2], r[0])) for g in groups]


# ---------------------------------------------------------------- 별 (순수)
def stars(raw, foe_ko, foe_size, me_alive, me_size):
    """한 판의 별. raw = 판의 결과 (won / lost / draw / forfeit / expired)."""
    if raw == "won":
        return 3 if me_size and me_alive * 2 >= me_size else 2
    return 1 if foe_size and foe_ko * 2 >= foe_size else 0


def _count(tb):
    """(쓰러뜨린 상대 수, 상대 마릿수, 서 있는 내 수, 내 마릿수)"""
    foe = tb.foe_team or []
    me = tb.me_team or []
    return (sum(1 for f in foe if not f.alive()), len(foe), sum(1 for f in me if f.alive()), len(me))


# ---------------------------------------------------------------- 표 읽기
def pair_of(gid, s=None):
    return db.q1("SELECT * FROM guild_war_pair WHERE season=? AND guild_id=?", (s or season.SEASON, gid))


def roster(gid, s=None):
    """그 길드의 이번 판 출전 명단 (쉬는 사람 빼고, 번호순 - 가려진 조커의 자리 번호가 이 차례다)."""
    return [r for r in GW.fighters(gid, s) if not r["bench"]]


def _gname(gid, s):
    e = GW.entry(gid, s)
    return e["name"] if e else "?"


def _ratio(r):
    return Fraction(int(r["kos"] or 0), max(1, int(r["def_size"] or 1)))


def _best(s, atk_gid, def_gid):
    """방어자마다 우리 길드의 가장 잘한 공격 {방어자: ((별, 쓰러뜨린 비율), 줄)}."""
    best = {}
    for r in db.q("SELECT * FROM guild_war_attack WHERE season=? AND atk_guild=? AND def_guild=?"
                  " AND result<>'pending' ORDER BY id", (s, atk_gid, def_gid)):
        k = (int(r["stars"] or 0), _ratio(r))
        cur = best.get(r["def_user"])
        if cur is None or k > cur[0]:
            best[r["def_user"]] = (k, r)
    return best


def _side(s, atk_gid, def_gid):
    """atk 길드가 def 길드에게서 얻은 성적 (견주기용 분수 p · k 를 같이)."""
    foes = roster(def_gid, s)
    n = len(foes)
    best = _best(s, atk_gid, def_gid)
    got = sum(best[d["user_id"]][0][0] for d in foes if d["user_id"] in best)
    ko = sum((best[d["user_id"]][0][1] for d in foes if d["user_id"] in best), Fraction(0))
    mine = roster(atk_gid, s)
    used = sum(min(int(r["used"]), int(r["attacks"])) for r in mine)
    total = sum(int(r["attacks"]) for r in mine)
    last = db.q1("SELECT MAX(ended_at) t FROM guild_war_attack WHERE season=? AND atk_guild=? AND def_guild=?"
                 " AND result<>'pending'", (s, atk_gid, def_gid))
    p = Fraction(got, 3 * n) if n else Fraction(0)
    k = ko / n if n else Fraction(0)
    return {"stars": got, "max": 3 * n, "pct": round(float(p) * 100, 1), "ko": round(float(k) * 100, 1),
            "attacks": used, "left": max(0, total - used), "p": p, "k": k, "last": (last["t"] if last else None)}


def _public(side):
    return dict((k, v) for k, v in side.items() if k not in ("p", "k", "last"))


def _cmp(us, them):
    a, b = (us["p"], us["k"]), (them["p"], them["k"])
    return "win" if a > b else ("lose" if a < b else "draw")


def outcome(s, gid):
    """(우리 성적, 상대 성적, 결과) - 짝이 없으면 None."""
    p = pair_of(gid, s)
    if not p:
        return None
    us, them = _side(s, gid, p["target_guild"]), _side(s, p["from_guild"], gid)
    return us, them, _cmp(us, them)


# ---------------------------------------------------------------- 상대 정하기 (전략 기간 시작)
def _last_foes(s):
    out = {}
    for r in db.q("SELECT guild_id, target_guild, from_guild FROM guild_war_pair WHERE season=?", (s - 1,)):
        out[r["guild_id"]] = {r["target_guild"], r["from_guild"]}
    return out


def _plan(s):
    """이번 시즌 맞대결 짜임을 한 번만 셈해 적어 둔다 (meta gw:시즌:pairs) - 다시 부르면 적힌 것을 돌려준다.

    [{"kind", "cap", "gids": [...], "bench": {길드: [쉬는 사람]}}]. **적어 두는 까닭** (11/12 검토): 전력은 고정된
    방어팀에서 세는데, 전략 기간에 팀을 고치면 바뀐다. 짝을 넣다가 끊긴 뒤 다시 셈하면 다른 짝이 나와 한 길드가 두
    길드에게 맞을 수 있었다. 두 요청이 같이 셈해도 먼저 적은 쪽 하나만 쓴다 (_mark)."""
    key = "gw:%d:pairs" % s
    if not GW._meta(key):
        rows = []
        team = {}
        for e in GW.in_war(s):
            f = GW.fighters(e["guild_id"], s)
            team[e["guild_id"]] = f
            powers = [pvp.team_power(json.loads(r["def_team"] or "[]")) for r in f]
            rows.append((e["guild_id"], len(f), sum(powers) / len(powers) if powers else 0.0))
        plan = []
        for g in pairing(rows, _last_foes(s)):
            cap = cap_of(x[1] for x in g)
            bench = {}
            for x in g:
                f = team[x[0]]
                if cap and len(f) > cap:
                    order = sorted(f, key=lambda r: (-pvp.team_power(json.loads(r["def_team"] or "[]")), r["user_id"]))
                    bench[str(x[0])] = [r["user_id"] for r in order[cap:]]
            plan.append({"kind": "pair" if len(g) == 2 else "tri", "cap": cap, "gids": [x[0] for x in g],
                         "bench": bench})
        GW._mark(key, json.dumps(plan))
    return json.loads(GW._meta(key) or "[]")


def lock(s, now=None):
    """참가 길드의 명단이 다 고정된 뒤 상대를 정한다 (GW._lock_all 이 _deal 대신 부른다). 넣은 줄 수.

    짜임은 _plan 이 한 번만 셈해 적어 둔 것이다. 줄 넣기 · 쉬는 사람 · 채팅은 길드마다 표시로 한 번만 한다 - 도중에
    끊겨 다시 불러도 같은 짜임을 마저 넣는다."""
    plan = _plan(s)
    paired = set()
    n = 0
    for g in plan:
        gids, kind, cap = g["gids"], g["kind"], g["cap"]
        for i, gid in enumerate(gids):
            paired.add(gid)
            if len(gids) == 2:
                target = src = gids[1 - i]
            else:
                target, src = gids[(i + 1) % 3], gids[(i - 1) % 3]
            cur = db.run("INSERT INTO guild_war_pair (season, guild_id, target_guild, from_guild, kind, cap)"
                         " VALUES (?,?,?,?,?,?) ON CONFLICT(season, guild_id) DO NOTHING",
                         (s, gid, target, src, kind, cap))
            n += 1 if getattr(cur, "rowcount", 1) > 0 else 0
            out = g["bench"].get(str(gid))
            if out and not GW._meta("gw:%d:bench:%d" % (s, gid)):
                _set_bench(s, gid, set(out))
                GW._mark("gw:%d:bench:%d" % (s, gid), GW._iso(now))
    # 채팅은 쉬는 사람까지 다 정한 뒤 (상대 인원 = 실제로 나오는 사람)
    for g in plan:
        gids = g["gids"]
        for i, gid in enumerate(gids):
            if len(gids) == 2:
                target = src = gids[1 - i]
            else:
                target, src = gids[(i + 1) % 3], gids[(i - 1) % 3]
            if db.q1("SELECT 1 FROM guild WHERE id=?", (gid,)) and GW._mark("gw:%d:paired:%d" % (s, gid),
                                                                           GW._iso(now)):
                names = [r["name"] for r in GW.fighters(gid, s) if r["bench"]]
                guild._say(gid, _lock_text(s, gid, g["kind"], target, src, g["cap"], names), now)
                guild._changed(gid)
    for e in GW.in_war(s):
        gid = e["guild_id"]
        if gid not in paired and GW._mark("gw:%d:alone:%d" % (s, gid), GW._iso(now)):
            if db.q1("SELECT 1 FROM guild WHERE id=?", (gid,)):
                guild._say(gid, "길드전 전략 기간이 시작됐지만 이번에는 함께 나간 길드가 없어 맞대결이 없습니다.", now)
    return n


def _set_bench(s, gid, out):
    """쉬는 사람을 한 문장으로 고친다 (두 길드장이 같이 눌러도 한쪽 것이 통째로 남는다). 쉬면 공격 0 · 조커 풂."""
    out = sorted(int(x) for x in out)
    marks = ",".join("?" * len(out)) or "NULL"
    db.run("UPDATE guild_war_team SET bench=CASE WHEN user_id IN (%s) THEN 1 ELSE 0 END,"
           " attacks=CASE WHEN user_id IN (%s) THEN 0 ELSE ? END,"
           " joker=CASE WHEN user_id IN (%s) THEN 0 ELSE joker END"
           " WHERE season=? AND guild_id=? AND locked=1" % (marks, marks, marks),
           tuple(out) + tuple(out) + (EACH,) + tuple(out) + (s, gid))


def _lock_text(s, gid, kind, target, src, cap, benched):
    me = len(roster(gid, s))
    t_n, f_n = len(roster(target, s)), len(roster(src, s))
    if kind == "pair":
        text = ("길드전 상대가 정해졌습니다! [%s] (%d명) 와(과) 1:1 맞대결입니다 (우리 %d명). 전쟁이 시작되면 출전한 "
                "사람마다 %d번씩 상대 길드원을 칩니다. 지금은 상대 명단과 방어팀 앞 %d마리를 볼 수 있고, 길드장은 "
                "조커를 정할 수 있습니다." % (_gname(target, s), t_n, me, EACH, GW.SHOWN))
    else:
        text = ("길드전 상대가 정해졌습니다! 이번에는 세 길드가 돌아가며 싸웁니다 - 우리는 [%s] (%d명) 를 치고, "
                "[%s] (%d명) 에게 맞습니다. 승패는 우리가 [%s] 에게서 얻은 별 %% 와 [%s] 가 우리에게서 얻은 별 %% 를 "
                "견줍니다. 출전한 사람마다 %d번씩 칩니다."
                % (_gname(target, s), t_n, _gname(src, s), f_n, _gname(target, s), _gname(src, s), EACH))
    if benched:
        text += (" 이번 판은 %d명까지 나갑니다 - 방어팀이 센 %d명이 나가고 %s 님은 쉽니다. 길드장이 전략 기간에 "
                 "바꿀 수 있습니다." % (cap, cap, ", ".join(benched)))
    return text


# ---------------------------------------------------------------- 길드장이 하는 일 (전략 기간)
def set_roster(uid, out_ids, now=None):
    """출전 상한에 걸린 길드의 길드장이 쉴 사람을 고른다 (전략 기간에만). 출전 인원이 꼭 cap 명이 되게."""
    m = guild._need_manager(uid)
    if GW.phase(now)[0] != "plan":
        raise HTTPException(409, "출전 명단은 전략 기간에만 고칠 수 있습니다. 전쟁이 시작되면 바꿀 수 없습니다.")
    s = season.SEASON
    gid = m["guild_id"]
    p = pair_of(gid, s)
    f = GW.fighters(gid, s)
    if not p or not f:
        raise HTTPException(409, "이번 길드전에 나가지 않았습니다.")
    cap = p["cap"]
    if not cap or len(f) <= cap:
        raise HTTPException(409, "우리 길드는 출전 상한에 걸리지 않아 모두 나갑니다.")
    ids = set(r["user_id"] for r in f)
    out = set()
    for x in out_ids or []:
        x = to_id(x)
        if x not in ids:
            raise HTTPException(404, "이번 길드전에 나간 길드원이 아닙니다.")
        out.add(x)
    if len(ids) - len(out) != cap:
        raise HTTPException(409, "이번 판은 %d명이 나갑니다. %d명을 쉬게 골라 주세요 (지금 %d명)."
                            % (cap, len(ids) - cap, len(out)))
    before = set(r["user_id"] for r in f if r["bench"])
    if before == out:
        return False
    _set_bench(s, gid, out)
    names = [r["name"] for r in f if r["user_id"] in out]
    guild._say(gid, "%s 님이 길드전 출전 명단을 정했습니다 - %d명 출전, 쉬는 사람: %s."
               % (guild._name_of(uid), cap, ", ".join(names)), now)
    guild._changed(gid)
    return True


def set_joker(uid, member, on, now=None):
    """길드장이 출전한 길드원을 조커로 숨기거나 푼다 (전략 기간, 길드마다 GW.JOKER_MAX 명). 사람으로 고른다."""
    m = guild._need_manager(uid)
    if GW.phase(now)[0] != "plan":
        raise HTTPException(409, "조커는 전략 기간에만 정할 수 있습니다. 전쟁이 시작되면 바꿀 수 없습니다.")
    s = season.SEASON
    gid = m["guild_id"]
    member = to_id(member)
    who = GW._row(member, s)
    if not who or who["locked"] != 1 or who["guild_id"] != gid:
        raise HTTPException(404, "이번 길드전에 나간 길드원이 아닙니다.")
    if who["bench"]:
        raise HTTPException(409, "이번 판에 쉬는 사람은 조커로 숨길 수 없습니다.")
    want = 1 if on else 0
    if int(who["joker"] or 0) == want:
        return False
    if want:
        cur = db.run("UPDATE guild_war_team SET joker=1 WHERE season=? AND user_id=? AND locked=1 AND joker=0"
                     " AND bench=0 AND (SELECT COUNT(*) FROM guild_war_team WHERE season=? AND guild_id=? AND locked=1"
                     " AND joker=1) < ?", (s, member, s, gid, GW.JOKER_MAX))
        if getattr(cur, "rowcount", 1) == 0:
            raise HTTPException(409, "조커는 길드마다 %d명까지입니다. 다른 조커를 먼저 풀어 주세요." % GW.JOKER_MAX)
    else:
        db.run("UPDATE guild_war_team SET joker=0 WHERE season=? AND user_id=?", (s, member))
    k = GW.joker_count(gid, s)
    guild._say(gid, ("%s 님이 %s 님을 조커로 숨겼습니다 (%d/%d명). 상대 길드에는 이름과 방어팀이 '???' 로 보입니다."
                     if want else "%s 님이 %s 님의 조커를 풀었습니다 (%d/%d명).")
               % (guild._name_of(uid), who["name"], k, GW.JOKER_MAX), now)
    return True


# ---------------------------------------------------------------- 공격
def _attacked_by(s, def_uid, gid):
    return bool(db.q1("SELECT 1 FROM guild_war_attack WHERE season=? AND def_user=? AND atk_guild=? LIMIT 1",
                      (s, def_uid, gid)))


def _veiled(s, d, my_gid, jokers):
    """칠 상대 d 가 우리 길드에게 가려지나 - 조커이고, 우리 길드가 아직 한 번도 안 붙어 봤으면."""
    return d["user_id"] in jokers and d["guild_id"] != my_gid and not _attacked_by(s, d["user_id"], my_gid)


STALE = "맞대결 판이 바뀌었습니다. 다시 불러와 주세요"
MAX_ID = 2 ** 31                       # 화면이 보낸 번호의 범위 (넘으면 400 - sqlite 정수 넘침으로 500 이 나던 것)


def to_id(x, what="누구인지"):
    try:
        x = int(x)
    except (TypeError, ValueError):
        raise HTTPException(400, "%s 알 수 없습니다." % what)
    if abs(x) >= MAX_ID:
        raise HTTPException(400, "%s 알 수 없습니다." % what)
    return x


def _jokers_of(s, gid, jokers):
    """그 길드의 출전한 조커들 - 가려진 조커의 자리 표시(-1, -2 …)가 이 차례다. **번호 차례가 아니다**: 번호 차례면
    보이는 사람들 사이 어디쯤인지로 진짜 번호를 좁힐 수 있었다 (11/12 검토). 시즌 · 사람으로 섞은 차례."""
    out = [d for d in roster(gid, s) if d["user_id"] in jokers]
    return sorted(out, key=lambda d: hashlib.sha256(("gwj:%d:%d" % (s, d["user_id"])).encode()).hexdigest())


def _resolve(uid, target, s):
    """화면이 보낸 칠 상대 -> 방어자 번호 (모르면 None). 가려진 조커는 음수 자리 표시로 온다.

    - 음수: 칠 길드의 조커 차례(_jokers_of)에서 찾고, 그 사람이 지금도 우리에게 가려져 있어야 한다 - 아니면 판이
      바뀐 것(전략 기간에 받은 판 · 조커가 바뀜)이라 409 STALE (엉뚱한 사람을 치지 않게).
    - 양수: 가려진 조커의 진짜 번호면 명단 밖과 똑같이 None (번호를 찔러 조커를 알아내지 못하게)."""
    target = to_id(target, "칠 상대를")
    me = GW._row(uid, s)
    p = pair_of(me["guild_id"], s) if me else None
    if not p:
        return None
    jokers = GW._joker_ids(s)
    if target < 0:
        js = _jokers_of(s, p["target_guild"], jokers)
        i = -target - 1
        if not (0 <= i < len(js)) or not _veiled(s, js[i], me["guild_id"], jokers):
            raise HTTPException(409, STALE + ".")
        return js[i]["user_id"]
    d = GW._row(target, s)
    if d and _veiled(s, d, me["guild_id"], jokers):
        return None
    return target


def why(uid, def_uid, s, now=None, memo=None):
    """이 사람을 지금 내가 칠 수 없는 까닭 (칠 수 있으면 None). 공격할 때도 이것으로 본다."""
    memo = memo if memo is not None else {}
    if "phase" not in memo:
        memo["phase"] = GW.phase(now)[0]
    if memo["phase"] == "plan":
        return "아직 전략 기간이다 (공격은 전쟁이 시작되면)"
    if memo["phase"] != "war":
        return "지금은 전쟁 중이 아니다"
    if "me" not in memo:
        memo["me"] = GW._me_in_war(uid)
        memo["pair"] = pair_of(memo["me"]["guild_id"], s) if memo["me"] else None
        memo["done"] = set(r["def_user"] for r in db.q(
            "SELECT def_user FROM guild_war_attack WHERE season=? AND atk_user=?", (s, uid)))
    me = memo["me"]
    # 치는 사람 쪽을 먼저 본다 - 상대 쪽 까닭이 먼저 나오면 공격권을 안 쓰고 번호를 찔러 명단을 알아낼 수 있다
    if not me:
        return "이번 길드전에 나가지 않았다"
    if me["bench"]:
        return "이번 판에는 쉰다 (출전 상한)"
    p = memo["pair"]
    if not p:
        return "우리 길드는 이번에 상대가 없다"
    if me["used"] >= me["attacks"]:
        return "공격 횟수를 다 썼다"
    d = GW._row(def_uid, s) if def_uid else None
    if not d or d["locked"] != 1 or d["bench"] or d["guild_id"] != p["target_guild"]:
        return "칠 길드의 출전 명단이 아니다"
    if def_uid in memo["done"]:
        return "이미 한 번 친 사람이다 (두 번째 공격은 다른 사람에게)"
    return None


def _trainer(d, s):
    uid = d["user_id"]
    return {"id": "gw:u%d" % uid, "name": d["name"], "role": "[%s]" % _gname(d["guild_id"], s), "sprite": None,
            "level": GW.AI_LEVEL, "team": GW._ready(json.loads(d["def_team"] or "[]")), "noMega": True, "ai": "war",
            "keystone": mega.has_keystone(uid), "zring": gimmick.has_zring(uid)}


def attack(uid, target, now=None):
    """출전 명단의 한 사람에게 승부를 건다. 공격권 하나를 쓰고 관장 배틀 판을 연다 (끝나면 on_end).
    돌려주는 것은 관장 배틀의 시작(gym_routes.start)과 같은 꼴이다."""
    GW._lock(now)
    GW.expire(now)
    if GW.phase(now)[0] != "war":
        raise HTTPException(409, "지금은 전쟁 중이 아닙니다.")
    s = season.SEASON
    me = GW._me_in_war(uid)
    if not me or me["bench"]:
        raise HTTPException(403, "이번 길드전에 나가지 않았습니다.")
    if GW._active_battle(uid):                # 상대를 보기 전에 (위 why 의 까닭과 같다)
        raise HTTPException(409, "아직 끝나지 않은 승부가 있습니다. 그 승부를 먼저 끝내 주세요.")
    if me["used"] >= me["attacks"]:
        raise HTTPException(409, "칠 수 없습니다: 공격 횟수를 다 썼다.")
    def_uid = _resolve(uid, target, s)
    w = why(uid, def_uid, s, now)
    if w:
        raise HTTPException(409, "칠 수 없습니다: %s." % w)
    d = GW._row(def_uid, s)
    trainer = _trainer(d, s)
    if not trainer["team"]:
        raise HTTPException(409, "그 사람의 방어팀이 없습니다.")
    lost = []
    tb = TB.TrainerBattle(deps.dex(), GW._ready(json.loads(me["atk_team"]), lost), trainer, random.Random())
    tb.keystone["me"] = mega.has_keystone(uid)
    tb.zring["me"] = gimmick.has_zring(uid)
    events = tb.start()
    if lost:
        at = 1 if events and events[0].get("t") == "intro" else 0
        events.insert(at, {"t": "note", "text": pvp.strip_note(lost)})
    cur = db.run("UPDATE guild_war_team SET used=used+1 WHERE season=? AND user_id=? AND used < attacks AND bench=0",
                 (s, uid))
    if getattr(cur, "rowcount", 1) == 0:
        raise HTTPException(409, "공격할 수 있는 횟수를 다 썼습니다.")
    stamp = GW._iso(now)
    region = "u%d" % def_uid
    bid = db.run("INSERT INTO gym_battle (user_id, region, trainer, state, turn, rev, data, created_at, updated_at)"
                 " VALUES (?,?,?,?,?,?,?,?,?)",
                 (uid, GW.battle_region(s, region), "gw", "active", 0, 0, json.dumps(tb.dump()), stamp,
                  (now or GW._now()).isoformat())).lastrowid
    # 같은 사람을 두 번 · 쉬게 된 사람을 치지 않는다 - 넣는 문장 안에서 다시 본다 (두 창에서 같이 눌러도)
    cur = db.run(
        "INSERT INTO guild_war_attack (season, region, atk_user, atk_guild, atk_name, def_user, def_guild, def_name,"
        " result, battle_id, created_at) SELECT ?,?,?,?,?,?,?,?,?,?,?"
        " WHERE NOT EXISTS (SELECT 1 FROM guild_war_attack WHERE season=? AND atk_user=? AND def_user=?)"
        " AND EXISTS (SELECT 1 FROM guild_war_team WHERE season=? AND user_id=? AND guild_id=? AND locked=1"
        " AND bench=0)",
        (s, region, uid, me["guild_id"], me["name"], def_uid, d["guild_id"], d["name"], "pending", bid, stamp,
         s, uid, def_uid, s, def_uid, d["guild_id"]))
    if getattr(cur, "rowcount", 1) == 0:
        db.run("DELETE FROM gym_battle WHERE id=?", (bid,))
        db.run("UPDATE guild_war_team SET used=used-1 WHERE season=? AND user_id=?", (s, uid))
        raise HTTPException(409, "그사이 이미 친 사람이 됐거나 출전 명단에서 빠졌습니다. 다른 사람을 고르세요.")
    gname = _gname(d["guild_id"], s)
    war = {"mode": "match", "target": def_uid, "name": d["name"], "guild": gname}
    _watch_open(me, d, gname, bid, tb, events, war)
    return {"id": bid, "region": GW.battle_region(s, region), "rev": 0, "battle": tb.view(), "events": events,
            "watchers": watchers.count(GW.fight_id(bid)), "war": war}


def _watch_open(me, d, gname, bid, tb, events, war):
    try:
        a = {"id": me["user_id"], "name": me["name"]}
        b = {"id": d["user_id"], "name": "[%s] %s" % (gname, d["name"])}
        fid = GW.fight_id(bid)
        friendly.watch_open(me["guild_id"], fid, a, b, "길드전: %s 님이 [%s] %s 님을 칩니다" % (a["name"], gname, d["name"]),
                            war)
        friendly.watch_feed(me["guild_id"], fid, GW.spectate(tb, bid, GW._names(a["name"], b["name"], a["id"], b["id"]),
                                                             events, 0, war))
    except Exception as err:                                  # noqa: BLE001
        from . import errors
        errors.record("GWAR", "guild_war_match._watch_open", err)


def finish(a, raw, turns=0, tb=None, now=None):
    """공격 한 판의 끝을 적는다 (한 번만). (적었나, 결과, 별, 쓰러뜨린 수, 방어팀 마릿수)"""
    res = GW.RESULT_OF.get(raw, "lose")
    if tb is not None:
        ko, size, alive, mine = _count(tb)
    else:
        d = GW._row(a["def_user"], a["season"])
        ko, size, alive, mine = 0, len(pvp.restrict(json.loads(d["def_team"] or "[]"))[0]) if d else 0, 0, 0
    st = stars(raw, ko, size, alive, mine)
    cur = db.run("UPDATE guild_war_attack SET result=?, turns=?, ended_at=?, stars=?, kos=?, def_size=?"
                 " WHERE id=? AND result='pending'", (res, int(turns or 0), GW._iso(now), st, ko, size, a["id"]))
    return getattr(cur, "rowcount", 1) > 0, res, st, ko, size


def _reward(a, res, raw, st):
    """판이 끝났다 (finish 가 적은 뒤에 한 번) - 공격한 사람에게 별 코인(+조커), 막아 낸 사람에게 막기 코인.
    (공격한 사람이 받은 것, 지킨 사람이 받은 것, 조커를 이겼나). 보상이 깨져도 판의 결과는 그대로다."""
    s = a["season"]
    got = kept = 0
    joker = False
    try:
        if st:
            joker = res == "win" and a["def_user"] in GW._joker_ids(s)
            got = GW._pay(s, a["atk_user"], STAR_COINS[min(3, st)] + (GW.CONTRIB_JOKER if joker else 0))
        if res == "lose" and raw == "lost":
            kept = GW._pay(s, a["def_user"], GW.CONTRIB_DEFEND)
        if got or kept:
            db.run("UPDATE guild_war_attack SET coins=?, def_coins=? WHERE id=?", (got, kept, a["id"]))
    except Exception as err:                                  # noqa: BLE001
        from . import errors
        errors.record("GWAR", "guild_war_match._reward %s" % a["id"], err)
    return got, kept, joker


def star_text(n):
    return "★" * n + "☆" * (3 - n)


def on_end(uid, row, tb, events=None, now=None):
    """관장 배틀 창에서 1:1 판이 끝났다 (GW.on_end 가 넘긴다). 결과 창에 적을 줄."""
    a = db.q1("SELECT * FROM guild_war_attack WHERE battle_id=?", (row["id"],))
    if not a or a["atk_user"] != uid:
        return None
    wrote, res, st, ko, size = finish(a, tb.result, tb.turn, tb, now)
    if not wrote:
        return None
    got, kept, joker = _reward(a, res, tb.result, st)
    s = a["season"]
    gname = _gname(a["def_guild"], s)
    mine_name = _gname(a["atk_guild"], s)
    best = _best(s, a["atk_guild"], a["def_guild"]).get(a["def_user"])
    top = best[0][0] if best else st
    us = _side(s, a["atk_guild"], a["def_guild"])
    lines = ["%s  %s 님에게서 별 %d개 (%d마리 중 %d마리 쓰러뜨림)." % (star_text(st), a["def_name"], st, size, ko)]
    if top > st:
        lines.append("우리 길드가 이 사람에게서 얻은 별은 이미 %d개라 그대로다 (방어자마다 가장 잘한 공격만 센다)." % top)
    lines.append("우리 길드 별 %d / %d개 (%.1f%%)." % (us["stars"], us["max"], us["pct"]))
    if st:
        if got:
            lines.append("길드 코인 %d개%s - 이번 시즌 %d / %d개." % (
                got, " (조커를 이겼다!)" if joker else "", GW._earned(s, uid), GW.CONTRIB_MAX))
        else:
            lines.append("판마다 받는 길드 코인은 이번 시즌 상한(%d개)을 다 받았다." % GW.CONTRIB_MAX)
    word = {"win": "이겼습니다", "draw": "비겼습니다"}.get(res, "졌습니다")
    mine_text = "길드전: %s 님이 [%s] %s 님에게 %s %s (별 %.1f%%)" % (
        a["atk_name"], gname, a["def_name"], word, star_text(st), us["pct"])
    foe_text = "길드전: [%s] %s 님이 %s 님을 쳤습니다 - %s %s" % (
        mine_name, a["atk_name"], a["def_name"], star_text(st), "(막아냈습니다!)" if res != "win" else "")
    if kept:
        foe_text += " (막아 낸 사람에게 길드 코인 %d개)" % kept
    guild._say(a["atk_guild"], mine_text, now)
    if db.q1("SELECT 1 FROM guild WHERE id=?", (a["def_guild"],)):
        guild._say(a["def_guild"], foe_text.rstrip(), now)
    war = {"mode": "match", "target": a["def_user"], "name": a["def_name"], "stars": st, "ko": ko, "size": size,
           "result": res, "coins": got}
    GW._watch_end(a, tb, events, (row["rev"] or 0) + 1, res, False, 0, mine_text, war)
    return {"lines": lines, "war": war}


def end_expired(a, b, now=None):
    """시간이 지나 접힌 판 (GW.expire 가 넘긴다). b = gym_battle 줄."""
    tb = None
    try:
        if b["data"]:
            tb = TB.TrainerBattle.load(deps.dex(), json.loads(b["data"]))
    except Exception:                                        # noqa: BLE001
        tb = None
    wrote, res, st, ko, size = finish(a, b["result"], b["turn"], tb, now)
    if wrote:
        _reward(a, res, b["result"], st)
        GW._watch_end(a, None, None, None, res, False, 0,
                      "길드전: %s 님의 공격이 끝났습니다 (시간이 지나 진 것으로) - %s" % (a["atk_name"], star_text(st)),
                      {"mode": "match", "stars": st, "ko": ko, "size": size})


# ---------------------------------------------------------------- 맞대결 목록 · 결산
def scores(s=None):
    """길드마다 이번 판 성적 (GW.scores 가 넘긴다 - 순위가 아니다, 순위 보상이 없다). 길드 이름순.
    result 는 끝났으면 승패, 전쟁 중이면 지금 앞섬 (같은 셈)."""
    s = s or season.SEASON
    rows = []
    for i, e in enumerate(GW.in_war(s)):
        gid = e["guild_id"]
        o = outcome(s, gid)
        us, them, res = o if o else (None, None, None)
        p = pair_of(gid, s)
        rows.append({"guildId": gid, "name": e["name"], "color": i, "result": res,
                     "stars": us["stars"] if us else 0, "max": us["max"] if us else 0,
                     "pct": us["pct"] if us else 0.0, "ko": us["ko"] if us else 0.0,
                     "vs": _gname(p["target_guild"], s) if p else None,           # 우리가 칠 길드
                     "from": _gname(p["from_guild"], s) if p else None,          # 우리를 친 길드 (1:1 이면 vs 와 같다)
                     "vsPct": them["pct"] if them else None,                    # from 이 우리에게서 얻은 별 %
                     "score": us["stars"] if us else 0})
    rows.sort(key=lambda r: (r["name"], r["guildId"]))
    return rows


def matches(s, my_gid=None, ph=None):
    """이번 시즌 맞대결 목록 - 짝(삼각형)마다 한 덩어리. 우리 판이 맨 위, 나머지는 첫 길드 이름순.
    [{"kind", "ours", "final", "guilds": [{guildId, name, stars, max, pct, ko, result, vs, from}]}]"""
    by = dict((r["guildId"], r) for r in scores(s))
    seen, out = set(), []
    for p in db.q("SELECT * FROM guild_war_pair WHERE season=? ORDER BY guild_id", (s,)):
        if p["guild_id"] in seen:
            continue
        group = [p["guild_id"], p["target_guild"]]
        if p["kind"] == "tri":
            group.append(p["from_guild"])
        seen.update(group)
        gs = [dict((k, by[g][k]) for k in ("guildId", "name", "stars", "max", "pct", "ko", "result", "vs", "from"))
              for g in group if g in by]
        gs.sort(key=lambda x: (x["name"], x["guildId"]))
        out.append({"kind": p["kind"], "ours": my_gid in group, "final": ph == "done", "guilds": gs})
    out.sort(key=lambda m: (not m["ours"], m["guilds"][0]["name"] if m["guilds"] else ""))
    return out


def settle(now=None):
    """전쟁이 끝났으면 결산 코인을 준다 (GW.settle 이 넘긴다). 한 번만 돈다 - 지도전의 결산과 같은 표시를 쓴다.
    한 번이라도 공격한 사람에게 그 길드의 판 결과로 RESULT_COINS. 순위 · 꾸미기 · 칭호 · 뽑기권은 없다."""
    s = season.SEASON
    if GW.phase(now)[0] != "done" or GW._meta("gw:%d:settled" % s):
        return False
    GW.expire(now, everything=True)
    table = [r for r in scores(s) if r["result"]]
    if len(table) < 2:
        GW._mark("gw:%d:settled" % s, GW._iso(now))
        return True
    msg_of = {}
    for r in table:
        gid, res = r["guildId"], r["result"]
        n = RESULT_COINS[res]
        db.run("UPDATE guild_war_entry SET score=? WHERE season=? AND guild_id=?", (r["score"], s, gid))
        active = [x["atk_user"] for x in db.q(
            "SELECT DISTINCT atk_user FROM guild_war_attack WHERE season=? AND atk_guild=?", (s, gid))]
        for uid in active:
            # 사람마다 표시를 먼저 적는다 - 도중에 끊겨 다시 돌아도, 두 요청이 같이 돌아도 한 번만
            if GW._mark("gw:%d:paid:%d" % (s, uid), GW._iso(now)):
                guild._coin_add(uid, n)
        us, them, _res = outcome(s, gid)
        p = pair_of(gid, s)
        msg_of[gid] = ("길드전이 끝났습니다. [%s] 별 %.1f%% vs [%s] 별 %.1f%% - %s! 한 번이라도 공격한 길드원에게 "
                       "길드 코인 %d개를 드렸습니다." % (r["name"], us["pct"], _gname(p["from_guild"], s), them["pct"],
                                                    RESULT_KR[res], n))
    for gid, text in msg_of.items():
        if db.q1("SELECT 1 FROM guild WHERE id=?", (gid,)) and GW._mark("gw:%d:said:%d" % (s, gid), GW._iso(now)):
            guild._say(gid, text, now)
            guild._changed(gid)
    GW._mark("gw:%d:settled" % s, GW._iso(now))
    return True


# ---------------------------------------------------------------- 보여주기
def _match_summary(s, gid, ph):
    p = pair_of(gid, s)
    if not p:
        return None
    us, them, res = outcome(s, gid)

    def g(x):
        return {"guildId": x, "name": _gname(x, s), "size": len(roster(x, s))}
    lead = {"win": "us", "lose": "them", "draw": "even"}[res]
    return {"kind": p["kind"], "target": g(p["target_guild"]), "from": g(p["from_guild"]), "own": g(gid),
            "cap": p["cap"],
            "us": _public(us), "them": _public(them), "lead": lead, "result": res if ph == "done" else None}


def state_extra(uid, out, now=None):
    """GW.state 에 1:1 맞대결 것을 얹는다 (GW.state 가 끝에 부른다)."""
    s = season.SEASON
    ph = out["phase"]
    out["mode"] = "match"
    out["each"] = EACH
    out["capRatio"] = CAP_RATIO
    out["starRules"] = list(STAR_RULES)
    out["total"] = EACH
    # 보상은 길드 코인만 - 순위 보상 줄(rewards) · 활약 뽑기권(tmActive) · 순위표(ranking)는 비운다
    out["rewards"] = []
    out["tmActive"] = None
    out["ranking"] = []
    out["coinRules"] = {"stars": list(STAR_COINS[1:]), "joker": GW.CONTRIB_JOKER, "defend": GW.CONTRIB_DEFEND,
                        "max": GW.CONTRIB_MAX, "result": dict(RESULT_COINS)}
    out["match"] = None
    out["can"]["roster"] = False
    m = guild.member(uid)
    out["matches"] = matches(s, m["guild_id"] if m else None, ph) if ph in ("plan", "war", "done") else []
    if not m or ph not in ("plan", "war", "done"):
        return out
    gid = m["guild_id"]
    e = GW.entry(gid, s)
    if not e or e["locked"] != 1:
        return out
    out["match"] = _match_summary(s, gid, ph)
    if ph == "done" and isinstance(out.get("contrib"), dict):
        # 결산으로 받은 코인 (받았으면 그 수, 아니면 0) - 앱이 짐작하지 않게. 공격한 길드의 판 결과로 받는다
        got = 0
        if GW._meta("gw:%d:paid:%d" % (s, uid)):
            a = db.q1("SELECT atk_guild FROM guild_war_attack WHERE season=? AND atk_user=? ORDER BY id LIMIT 1", (s, uid))
            o = outcome(s, a["atk_guild"]) if a else None
            got = RESULT_COINS.get(o[2], 0) if o else 0
        out["contrib"]["settled"] = got
    rows = GW.fighters(gid, s)
    by = dict((r["atk_user"], r) for r in db.q(
        "SELECT atk_user, COALESCE(SUM(stars), 0) st, SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) w"
        " FROM guild_war_attack WHERE season=? AND atk_guild=? GROUP BY atk_user", (s, gid)))
    out["mates"] = [{"userId": r["user_id"], "name": r["name"], "attacks": r["attacks"], "used": r["used"],
                     "bench": bool(r["bench"]), "joker": bool(r["joker"]),
                     "stars": int(by[r["user_id"]]["st"]) if r["user_id"] in by else 0,
                     "wins": int(by[r["user_id"]]["w"] or 0) if r["user_id"] in by else 0} for r in rows]
    p = pair_of(gid, s)
    manager = m["role"] in ("master", "sub")
    out["can"]["roster"] = bool(manager and ph == "plan" and p and p["cap"] and len(rows) > p["cap"])
    return out


def match_view(uid, now=None):
    """맞대결 판: 칠 상대 명단(앞 SHOWN 마리 · 조커는 '???') · 우리 명단(지키는 쪽) · 두 성적."""
    GW._lock(now)
    GW.expire(now)
    s = season.SEASON
    ph = GW.phase(now)[0]
    my = GW._my_gid(uid, s)
    me = GW._row(uid, s)
    gid = my if my is not None else (me["guild_id"] if me else None)
    p = pair_of(gid, s) if gid is not None else None
    if not p:
        raise HTTPException(404, "우리 길드는 이번 길드전 맞대결에 나가지 않았습니다.")
    summary = _match_summary(s, gid, ph)
    jokers = GW._joker_ids(s)
    tries = {}
    for r in db.q("SELECT * FROM guild_war_attack WHERE season=? AND atk_guild=? AND def_guild=? ORDER BY id",
                  (s, gid, p["target_guild"])):
        tries.setdefault(r["def_user"], []).append(r)
    memo = {}
    foes = []
    handle = dict((d["user_id"], -(i + 1)) for i, d in enumerate(_jokers_of(s, p["target_guild"], jokers)))
    seen = [d for d in roster(p["target_guild"], s) if not _veiled(s, d, gid, jokers)]
    veiled = [d for d in _jokers_of(s, p["target_guild"], jokers) if _veiled(s, d, gid, jokers)]
    # 가려진 조커는 맨 끝에 (번호 차례 사이에 끼면 진짜 번호가 좁혀진다 - 11/12 검토)
    vset = set(d["user_id"] for d in veiled)
    for d in seen + veiled:
        team = pvp.restrict(json.loads(d["def_team"] or "[]"))[0]
        hidden = d["user_id"] in vset
        if hidden:
            mons, more = [], len(team)
        else:
            mons, more = GW._hide(team, False)
        mine = tries.get(d["user_id"], [])
        done = [r for r in mine if r["result"] != "pending"]
        best = max(done, key=lambda r: (int(r["stars"] or 0), _ratio(r))) if done else None
        w = why(uid, d["user_id"], s, now, memo)
        foes.append({"userId": handle[d["user_id"]] if hidden else d["user_id"], "name": "???" if hidden else d["name"],
                     "joker": d["user_id"] in jokers, "hidden": hidden, "size": len(team), "team": mons,
                     "more": more,
                     "best": {"stars": int(best["stars"] or 0), "ko": int(best["kos"] or 0), "by": best["atk_name"]}
                     if best else None,
                     "tries": [{"by": r["atk_name"], "stars": None if r["result"] == "pending" else int(r["stars"] or 0),
                                "ko": int(r["kos"] or 0), "result": r["result"]} for r in mine],
                     "mine": any(r["atk_user"] == uid for r in mine), "can": w is None, "why": w})
    hit = {}
    for r in db.q("SELECT * FROM guild_war_attack WHERE season=? AND atk_guild=? AND def_guild=?"
                  " AND result<>'pending' ORDER BY id", (s, p["from_guild"], gid)):
        hit.setdefault(r["def_user"], []).append(r)
    ours = []
    for d in roster(gid, s):
        got = hit.get(d["user_id"], [])
        worst = max(got, key=lambda r: (int(r["stars"] or 0), _ratio(r))) if got else None
        ours.append({"userId": d["user_id"], "name": d["name"], "joker": d["user_id"] in jokers,
                     "size": len(pvp.restrict(json.loads(d["def_team"] or "[]"))[0]),
                     "worst": {"stars": int(worst["stars"] or 0), "ko": int(worst["kos"] or 0), "by": worst["atk_name"]}
                     if worst else None,
                     "tries": len(got), "defends": sum(1 for r in got if r["result"] != "win")})
    out = {"phase": ph, "foes": foes, "ours": ours}
    out.update(summary)
    return out


def log_row(a, base):
    """GW.log 의 한 줄에 1:1 것을 얹는다."""
    base["regionName"] = a["def_name"]
    base["stars"] = None if a["result"] == "pending" or a["stars"] is None else int(a["stars"])
    base["ko"] = int(a["kos"] or 0)
    base["mode"] = "match"
    return base
