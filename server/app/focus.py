# -*- coding: utf-8 -*-
"""포켓몬과 집중하기 — 집중 타이머의 서버 쪽.

    GET  /api/focus                 지금 집중 중인 것 · 오늘 받은 노력치 · 규칙 숫자
    POST /api/focus/start           시작 {pokemon, stat} - 진행 중인 것이 있으면 그것을 돌려준다
    POST /api/focus/beat            맥박 (앱이 1분마다). 지난 세트를 인정하고, 끊겼으면 집중을 끝낸다
    POST /api/focus/stop            집중 끝내기. 진행 중이던 세트는 노력치 0, 자투리는 달력에만
    GET  /api/focus/month?ym=       달력 한 달 {날: 분}
    GET  /api/focus/day?d=          그날의 기록

규칙 숫자는 common/focus.py (앱도 같은 것을 읽는다). 설계: design-notes/2026-11-04-focus-timer.md

## 시간은 서버 시계다

집중 한 번이 focus_run 한 줄이다. 시작할 때 '이번 세트 시작(set_at)' 과 '마지막 맥박(beat_at)' 을 적는다.
세트는 **set_at + 25분이 지나고, 그때까지 맥박이 끊기지 않았을 때** 인정한다. 인정하면 set_at 을 25분 민다 -
그래서 세트는 '집중 끝내기' 를 누를 때까지 저절로 이어진다 (사용자 결정 11/04).

## 끊김 = 게임이 꺼졌거나 컴퓨터가 잠들었다

맥박 사이가 GAP_SEC(3분)를 넘으면 그 집중을 lost 로 닫는다. **마지막 맥박 전에 끝난 세트는 인정하고, 그 뒤의
세트는 인정하지 않는다** (사용자 결정 11/04 - 꺼져 있던 동안의 시간은 세지 않는다). 끊김은 맥박 · 끝내기 · 새로
시작할 때 본다. /api/me 에 싣는 me_card 는 **쓰지 않는다** - 끊긴 것은 stale 로만 알리고, 앱이 맥박을 보내 닫는다.

## 같은 세트를 두 번 주지 않는다 · 하루 40 을 넘기지 않는다

세트 하나는 `UPDATE focus_run SET set_at=<다음> WHERE id=? AND set_at=<지금> AND state='on'` 한 문장으로 차지한다
(두 요청이 겹쳐도 rowcount 가 1 인 쪽만 준다). 노력치는 먼저 세트 줄을 0 으로 적고, '그날 합 + 이번 몫 <= 40' 을
조건으로 단 UPDATE 로 몫을 적은 뒤 포켓몬에 넣는다 - 두 PC 의 맥박이 겹쳐도 하루 40 을 못 넘는다.
지닌 도구(파워 시리즈 · 교정깁스)는 여기서 노력치를 늘리지 않는다.
"""
import datetime
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common import focus as F
from common import korean

from . import db, deps, items

router = APIRouter()

LOST_MSG = "게임이 꺼져 있었거나 컴퓨터가 잠들어서 집중이 끝났어요. 마지막 세트는 인정되지 않았어요."
# 맥박 · /api/me 마다 도는 질의 (색인을 타는지 server/test_focus.py 가 본다)
SETS_IN_RUN_SQL = "SELECT COUNT(*) c FROM focus_set WHERE user_id=? AND run_id=? AND full=1"
LAST_RUN_SQL = "SELECT state FROM focus_run WHERE user_id=? ORDER BY id DESC LIMIT 1"
YM_RE = re.compile(r"^(\d{4})-(\d{2})$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------- 시간
def _now(now=None):
    return now or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def _iso(t):
    return t.isoformat()


def _parse(s):
    try:
        t = datetime.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)


def _secs(a, b):
    return (a - b).total_seconds()


# ---------------------------------------------------------------- 읽기
def _on(uid):
    """진행 중(state='on')인 집중. 끊겼는지는 따지지 않는다."""
    return db.q1("SELECT * FROM focus_run WHERE user_id=? AND state='on'", (uid,))


def _stale(run, now):
    return _secs(now, _parse(run["beat_at"]) or now) > F.GAP_SEC


def focusing(uid, now=None):
    """지금 집중 중인가 (진행 중이고 맥박이 끊기지 않았다). 놀러 가기를 막는 데 쓴다."""
    run = _on(uid)
    return run is not None and not _stale(run, _now(now))


def focusing_many(ids, now=None):
    """여러 사람 중 지금 집중 중인 사람 (친구 목록 - 질의 한 번)."""
    ids = [int(i) for i in ids]
    if not ids:
        return set()
    now = _now(now)
    rows = db.q("SELECT user_id, beat_at FROM focus_run WHERE state='on' AND user_id IN (%s)"
                % ",".join("?" * len(ids)), tuple(ids))
    return set(r["user_id"] for r in rows if _secs(now, _parse(r["beat_at"]) or now) <= F.GAP_SEC)


def _today_ev(uid, day):
    r = db.q1("SELECT COALESCE(SUM(ev), 0) n FROM focus_set WHERE user_id=? AND day=?", (uid, day))
    return int(r["n"] or 0)


def _mon_name(r):
    if r is None:
        return "놓아준 포켓몬"
    mon = db.row_to_mon(r)
    sp = deps.dex().get(mon["species"]) or {}
    return mon.get("nickname") or sp.get("kr") or mon["species"]


def _mon_view(uid, pid):
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
    if r is None:
        return {"id": pid, "name": _mon_name(None), "num": 0, "shiny": False}
    mon = db.row_to_mon(r)
    sp = deps.dex().get(mon["species"]) or {}
    return {"id": pid, "name": _mon_name(r), "num": sp.get("num", 0), "shiny": bool(mon.get("shiny"))}


def view(uid, run, now):
    """앱에 보내는 진행 중인 집중. setLeft = 이번 세트 남은 초 (앱은 이것으로 센다 - PC 시계가 틀려도 맞다)."""
    set_at = _parse(run["set_at"]) or now
    left = int(round(F.SET_SEC - _secs(now, set_at)))
    act, stat_kr = F.act_of(run["stat"]) or ("?", "?")
    n = db.q1(SETS_IN_RUN_SQL, (uid, run["id"]))["c"]
    return {"id": run["id"], "pokemon": _mon_view(uid, run["pokemon_id"]), "stat": run["stat"],
            "act": act, "statKr": stat_kr, "startedAt": run["started_at"],
            "setLeft": max(0, left), "setSec": F.SET_SEC, "sets": int(n),
            "todayEv": _today_ev(uid, F.kst_day(now)), "dailyEv": F.DAILY_EV,
            "stale": _stale(run, now)}


def rules():
    return {"setSec": F.SET_SEC, "evPerSet": F.EV_PER_SET, "dailyEv": F.DAILY_EV,
            "beatSec": F.BEAT_SEC, "gapSec": F.GAP_SEC}


def state(uid, now=None):
    now = _now(now)
    run = _on(uid)
    return {"running": view(uid, run, now) if run else None,
            "todayEv": _today_ev(uid, F.kst_day(now)), "dailyEv": F.DAILY_EV, "rules": rules()}


def me_card(uid, now=None):
    """/api/me 에 싣는다. **쓰지 않는다** - 끊긴 집중은 stale 로만 알린다. 없으면 질의 한 번."""
    run = _on(uid)
    if run is None:
        return {"running": None}
    return {"running": view(uid, run, _now(now))}


# ---------------------------------------------------------------- 세는 값 (업적)
def _stat_add(uid, key, by=1):
    db.run("INSERT INTO user_stat (user_id, key, n) VALUES (?,?,?)"
           " ON CONFLICT(user_id, key) DO UPDATE SET n=n+excluded.n", (uid, key, int(by)))


def _stat_max(uid, key, n):
    db.run("INSERT INTO user_stat (user_id, key, n) VALUES (?,?,?)"
           " ON CONFLICT(user_id, key) DO UPDATE SET n=MAX(n, excluded.n)", (uid, key, int(n)))


def stats(uid):
    """업적이 세는 값 {focus_...: n}. 한 번에 읽는다."""
    return dict((r["key"], int(r["n"])) for r in db.q(
        "SELECT key, n FROM user_stat WHERE user_id=? AND key LIKE 'focus\\_%' ESCAPE '\\'", (uid,)))


def _bump_stats(uid, stat, pid, at, today_before, today_after):
    _stat_add(uid, "focus_sets")
    _stat_add(uid, "focus_%s" % stat)
    if today_before < F.DAILY_EV <= today_after:
        _stat_add(uid, "focus_fullday")
    days = [r["day"] for r in db.q("SELECT DISTINCT day FROM focus_set WHERE user_id=? AND full=1", (uid,))]
    _stat_max(uid, "focus_streak_best", F.streaks(days, F.kst_day(at))[1])
    if F.kst_hour(at) < 5:
        _stat_max(uid, "focus_dawn", 1)
    buddy = db.q1("SELECT COUNT(*) c FROM focus_set WHERE user_id=? AND pokemon_id=? AND full=1", (uid, pid))
    _stat_max(uid, "focus_buddy", buddy["c"])
    kinds = db.q1("SELECT COUNT(DISTINCT stat) c FROM focus_set WHERE user_id=? AND full=1", (uid,))
    _stat_max(uid, "focus_allround", kinds["c"])


# ---------------------------------------------------------------- 세트 인정
def _credit(uid, run, at):
    """세트 하나를 인정한다 (이미 차지한 세트). 돌려주는 것은 앱이 말풍선으로 알린다."""
    stat, pid = run["stat"], run["pokemon_id"]
    day = F.kst_day(at)
    act = (F.act_of(stat) or ("?", "?"))[0]
    before_day = _today_ev(uid, day)
    cur = db.run("INSERT INTO focus_set (user_id, run_id, pokemon_id, stat, at, day, minutes, full, ev)"
                 " VALUES (?,?,?,?,?,?,?,1,0)", (uid, run["id"], pid, stat, _iso(at), day, F.SET_SEC // 60))
    set_id = cur.lastrowid
    mon = db.q1("SELECT evs FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
    gain = 0
    if mon is not None:
        # 하루 몫을 먼저 적는다 - '그날 합 + 이번 몫 <= 40' 이 맞을 때만 들어간다 (겹친 요청이 넘기지 못한다)
        for _ in range(3):
            room = F.DAILY_EV - _today_ev(uid, day)
            gain = max(0, min(F.EV_PER_SET, room))
            if not gain:
                break
            c = db.run("UPDATE focus_set SET ev=? WHERE id=? AND (SELECT COALESCE(SUM(ev), 0) FROM focus_set"
                       " WHERE user_id=? AND day=?) + ? <= ?", (gain, set_id, uid, day, gain, F.DAILY_EV))
            if getattr(c, "rowcount", 1):
                break
            gain = 0
    actual = 0
    if gain:
        before = items.clamp_evs(json.loads(mon["evs"]))
        after = items.add_evs(before, {stat: gain})
        actual = after[stat] - before[stat]
        if actual:
            db.run("UPDATE pokemon SET evs=? WHERE id=?", (json.dumps(after), pid))
        if actual != gain:
            db.run("UPDATE focus_set SET ev=? WHERE id=?", (actual, set_id))
    if mon is None:
        capped = "gone"
    elif actual >= F.EV_PER_SET:
        capped = None
    elif gain < F.EV_PER_SET and actual == gain:
        capped = "day"
    else:
        capped = "full"
    today = _today_ev(uid, day)
    _bump_stats(uid, stat, pid, at, before_day, today)
    from . import achievements                 # 업적이 이 모듈의 stats 를 읽는다 - 서로 부르므로 여기서
    achievements.safe_check(uid, _iso(at))
    return {"stat": stat, "act": act, "ev": actual, "capped": capped, "todayEv": today,
            "dailyEv": F.DAILY_EV, "at": _iso(at)}


def _settle(uid, run, now, alive):
    """지난 세트를 인정하고, 맥박이 끊겼으면 집중을 닫는다. (인정한 세트들, 끊겼나).

    alive = 지금 이 요청이 앱이 살아 있다는 증거인가 (맥박 · 끝내기). 그러면 맥박 시각을 지금으로 적고
    지금까지 끝난 세트를 인정한다. 끊겼으면 **마지막 맥박 전에 끝난 세트만** 인정하고 lost 로 닫는다.
    """
    beat = _parse(run["beat_at"]) or now
    lost = _secs(now, beat) > F.GAP_SEC
    if alive and not lost:
        db.run("UPDATE focus_run SET beat_at=? WHERE id=? AND state='on'", (_iso(now), run["id"]))
        limit = now
    else:
        limit = beat
    sets = []
    set_at = _parse(run["set_at"]) or now
    while set_at + datetime.timedelta(seconds=F.SET_SEC) <= limit:
        nxt = set_at + datetime.timedelta(seconds=F.SET_SEC)
        c = db.run("UPDATE focus_run SET set_at=? WHERE id=? AND set_at=? AND state='on'",
                   (_iso(nxt), run["id"], _iso(set_at)))
        if not getattr(c, "rowcount", 1):
            break                               # 다른 요청이 먼저 차지했다
        sets.append(_credit(uid, run, nxt))
        set_at = nxt
    if lost:
        db.run("UPDATE focus_run SET state='lost', ended_at=? WHERE id=? AND state='on'",
               (_iso(beat), run["id"]))
    return sets, lost


def _last_end(uid):
    """진행 중인 것이 없을 때 마지막 집중이 어떻게 끝났나 ('lost' / 'done' / None)."""
    r = db.q1(LAST_RUN_SQL, (uid,))
    return r["state"] if r and r["state"] in ("lost", "done") else None


# ---------------------------------------------------------------- 시작 · 맥박 · 끝내기
def start(uid, pid, stat, now=None):
    now = _now(now)
    if F.act_of(stat) is None:
        raise HTTPException(400, "그런 능력은 없습니다.")
    mon = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (int(pid), uid))
    if mon is None:
        raise HTTPException(404, "그런 포켓몬이 없습니다.")
    run = _on(uid)
    if run is not None:
        _sets, lost = _settle(uid, run, now, alive=False)
        if not lost:
            return {"running": view(uid, _on(uid), now), "existing": True, "message": "이미 집중하는 중입니다."}
    if not mon["on_desktop"]:
        raise HTTPException(409, "데리고 다니는 포켓몬과만 집중할 수 있습니다.")
    from . import visit                        # 놀러 가기와 서로 부르므로 여기서
    if visit.busy(uid):
        raise HTTPException(409, "친구와 연결돼 있는 동안에는 집중을 시작할 수 없습니다. 돌아온 뒤 시작해 주세요.")
    t = _iso(now)
    try:
        db.run("INSERT INTO focus_run (user_id, pokemon_id, stat, started_at, set_at, beat_at, state)"
               " VALUES (?,?,?,?,?,?,'on')", (uid, int(pid), stat, t, t, t))
    except Exception as e:                                   # noqa: BLE001
        if "UNIQUE" not in str(e).upper():
            raise
        # 다른 PC 가 막 시작했다 (진행 중은 한 사람에 하나 - idx_focus_run_on)
        return {"running": view(uid, _on(uid), now), "existing": True, "message": "이미 집중하는 중입니다."}
    act, stat_kr = F.act_of(stat)
    name = _mon_name(mon)
    msg = korean.natural("%s 와(과) %s을(를) 시작했어요. 25분마다 %s 노력치가 %d 오릅니다."
                         % (name, act, stat_kr, F.EV_PER_SET))
    return {"running": view(uid, _on(uid), now), "existing": False, "message": msg}


def beat(uid, now=None):
    now = _now(now)
    run = _on(uid)
    if run is None:
        end = _last_end(uid)
        return {"running": None, "sets": [], "ended": end, "message": LOST_MSG if end == "lost" else None}
    sets, lost = _settle(uid, run, now, alive=True)
    if lost:
        return {"running": None, "sets": sets, "ended": "lost", "message": LOST_MSG}
    return {"running": view(uid, _on(uid), now), "sets": sets, "ended": None, "message": None}


def stop(uid, now=None):
    now = _now(now)
    run = _on(uid)
    if run is None:
        return {"running": None, "sets": [], "part": 0, "ended": None, "message": "진행 중인 집중이 없습니다."}
    sets, lost = _settle(uid, run, now, alive=True)
    if lost:
        return {"running": None, "sets": sets, "part": 0, "ended": "lost", "message": LOST_MSG}
    run = db.q1("SELECT * FROM focus_run WHERE id=?", (run["id"],))
    c = db.run("UPDATE focus_run SET state='done', ended_at=? WHERE id=? AND state='on'", (_iso(now), run["id"]))
    part = 0
    if getattr(c, "rowcount", 1):
        sec = _secs(now, _parse(run["set_at"]) or now)
        if sec >= F.PART_MIN_SEC:
            part = int(sec // 60)
            db.run("INSERT INTO focus_set (user_id, run_id, pokemon_id, stat, at, day, minutes, full, ev)"
                   " VALUES (?,?,?,?,?,?,?,0,0)",
                   (uid, run["id"], run["pokemon_id"], run["stat"], _iso(now), F.kst_day(now), part))
    mins = db.q1("SELECT COALESCE(SUM(minutes), 0) m FROM focus_set WHERE user_id=? AND day=?",
                 (uid, F.kst_day(now)))["m"]
    return {"running": None, "sets": sets, "part": part, "ended": "done",
            "message": "집중 끝! 오늘 %d분 집중했어요." % int(mins)}


# ---------------------------------------------------------------- 달력
def _ym_ok(ym):
    m = YM_RE.match(ym or "")
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise HTTPException(400, "달은 YYYY-MM 으로 적습니다.")
    return ym


def month(uid, ym):
    ym = _ym_ok(ym)
    rows = db.q("SELECT day, SUM(minutes) m FROM focus_set WHERE user_id=? AND day LIKE ? GROUP BY day",
                (uid, ym + "-%"))
    return {"ym": ym, "days": dict((r["day"], int(r["m"])) for r in rows)}


def day(uid, d):
    try:
        if not DAY_RE.match(d or ""):
            raise ValueError
        datetime.date(int(d[0:4]), int(d[5:7]), int(d[8:10]))
    except ValueError:
        raise HTTPException(400, "날짜는 YYYY-MM-DD 로 적습니다.")
    out = []
    names = {}
    for r in db.q("SELECT * FROM focus_set WHERE user_id=? AND day=? ORDER BY at, id", (uid, d)):
        pid = r["pokemon_id"]
        if pid not in names:
            names[pid] = _mon_name(db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (pid, uid)))
        at = _parse(r["at"])
        out.append({"time": at.astimezone(F.KST).strftime("%H:%M") if at else "",
                    "pokemon": names[pid], "stat": r["stat"], "act": (F.act_of(r["stat"]) or ("?",))[0],
                    "minutes": int(r["minutes"]), "ev": int(r["ev"]), "full": bool(r["full"])})
    return {"day": d, "rows": out}


def summary(uid, now=None):
    now = _now(now)
    today = F.kst_day(now)
    total = db.q1("SELECT COALESCE(SUM(minutes), 0) m FROM focus_set WHERE user_id=?", (uid,))["m"]
    mon_min = db.q1("SELECT COALESCE(SUM(minutes), 0) m FROM focus_set WHERE user_id=? AND day LIKE ?",
                    (uid, today[:7] + "-%"))["m"]
    days = [r["day"] for r in db.q("SELECT DISTINCT day FROM focus_set WHERE user_id=? AND full=1", (uid,))]
    cur, best = F.streaks(days, today)
    return {"totalMin": int(total), "monthMin": int(mon_min), "streak": cur, "best": best,
            "todayEv": _today_ev(uid, today), "dailyEv": F.DAILY_EV}


def mypage_card(uid, now=None):
    """마이페이지(본인만)의 '집중 기록': 요약과 이번 달. 다른 달은 넘길 때 /api/focus/month 로."""
    now = _now(now)
    return {"summary": summary(uid, now), "month": month(uid, F.kst_day(now)[:7])}


# ---------------------------------------------------------------- 라우트
class StartIn(BaseModel):
    pokemon: int
    stat: str


@router.get("/api/focus")
def get_state(ctx=Depends(deps.current)):
    return state(ctx["user"]["id"])


@router.post("/api/focus/start")
def post_start(body: StartIn, ctx=Depends(deps.current)):
    return start(ctx["user"]["id"], body.pokemon, body.stat)


@router.post("/api/focus/beat")
def post_beat(ctx=Depends(deps.current)):
    return beat(ctx["user"]["id"])


@router.post("/api/focus/stop")
def post_stop(ctx=Depends(deps.current)):
    return stop(ctx["user"]["id"])


@router.get("/api/focus/month")
def get_month(ym: str, ctx=Depends(deps.current)):
    return month(ctx["user"]["id"], ym)


@router.get("/api/focus/day")
def get_day(d: str, ctx=Depends(deps.current)):
    return day(ctx["user"]["id"], d)
