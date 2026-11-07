# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 서버 쪽.

    GET  /api/olympics                  일정 · 응원 타입 · 지친 포켓몬 · 내 신청 · 내 기록 · (끝났으면) 메달
    GET  /api/olympics/candidates?event 신청 창: 내 포켓몬마다 별(1~5)과 알기 쉬운 표시
    POST /api/olympics/enter            신청 {event, pokemon, tactic} - 같은 종목에 다시 내면 바뀐다
    POST /api/olympics/cancel           신청 취소 {event}
    GET  /api/olympics/live             그날 경기(2시에 치른 것)와 내 조 각본 - 앱이 바탕화면에서 중계한다
    GET  /api/olympics/heat?id=         한 신청이 뛴 조의 각본 (다시 보기)
    GET  /api/olympics/board?event&day  순위표 (day 가 없으면 주간 = 사람마다 최고 기록)

규칙 숫자 · 공식은 common/olympics.py (앱도 같은 것을 읽는다). 계획: design-notes/2026-11-06-olympics-plan.md

## 경기는 2시에 한 번 (사용자 결정 11/06)

평일 경기 날 14:00 KST 가 지나면, 그 뒤 처음 오는 요청(/api/me · /api/olympics*)이 그날 경기를 치른다
(ensure_ran). **olympic_day 줄을 넣는 것과 그날 결과를 적는 것이 한 트랜잭션이다** - 두 요청이 겹쳐도 한 번만
돌고, 그 사이에 들어온 신청은 olympic_day 줄을 보고 들어가지 않는다 (enter 의 INSERT ... WHERE NOT EXISTS).

기록은 서버만 정한다. 앱이 보내는 것은 종목 · 포켓몬 · 작전뿐이다. 신청할 때 포켓몬 모습을 적어 두고 그것으로 뛴다.

## 공개

내 조 각본은 경기를 치른 뒤 바로 받는다 (앱이 그 종목 차례에 중계한다). 순위표 · 남의 조는 그 종목 중계가 끝나는
때(common.olympics.release_at)부터 보인다 - 중계를 보기 전에 결과가 먼저 새지 않게.

## 폐막 (마지막 경기 날 프로그램이 끝난 뒤)

종목마다 사람마다 최고 기록으로 최종 순위를 매기고(동점은 먼저 낸 쪽), 1~3위 메달 · 4~8위 결선 진출 칭호 · 리본 ·
볼을 준다. **olympic_final 줄을 먼저 넣은 쪽만 볼을 준다** - 정산을 두 번 돌려도 한 번이다. 칭호 · 리본은 원래
'이미 있으면 그만' 이다. 돈 · 코인 · 팔 수 있는 도구는 주지 않는다.
"""
import datetime
import json
import random
import threading
import zlib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common import korean
from common import olympics as O

from . import db, deps, season

router = APIRouter()

TITLES = {"oly_silver": "올림픽 은메달리스트", "oly_bronze": "올림픽 동메달리스트", "oly_final": "올림픽 결선 진출"}
for _e in O.EVENTS:
    TITLES["oly_gold_%s" % _e["key"]] = "올림픽 %s 금메달" % (_e["short"] if _e["key"] in ("sprint", "swim") else _e["kr"])
season.TITLES.update(TITLES)
BALLS = {1: 20, 2: 15, 3: 10}
FINAL_BALLS = 5
RIBBON = {"oly_gold": "금메달 리본", "oly_silver": "은메달 리본", "oly_bronze": "동메달 리본",
          "oly_final": "결선 리본", "oly_species": "종족 1위 리본", "oly_join": "올림픽 참가 리본"}
BOARD_TOP = 50
FATIGUE_SHOW = 5

_lock = threading.Lock()
_ran = set()                 # 이 프로세스가 이미 확인한 '치른 날' (매 요청 질의를 줄인다)
_closed = [False]
_pct_cache = {}
_boards_cache = {}


# ---------------------------------------------------------------- 시간 · 도감
def _now(now=None):
    return (now or datetime.datetime.now(datetime.timezone.utc)).replace(microsecond=0)


def _iso(t):
    return t.isoformat()


def _secs(a, b):
    return int(round((a - b).total_seconds()))


def _pct():
    d = deps.dex()
    if _pct_cache.get("dex") is not d:
        _pct_cache.clear()
        _pct_cache.update({"dex": d, "pct": O.build_pct(d.species)})
    return _pct_cache["pct"]


def _type_kr(t):
    try:
        return deps.dex().type_name(t)
    except Exception:                                       # noqa: BLE001
        return t


def _ability_kr(a):
    try:
        return ((deps.dex().abilities or {}).get(a) or {}).get("kr") or a
    except Exception:                                       # noqa: BLE001
        return a


def _sp(species):
    return deps.dex().get(species) or {}


def _mon_view(r):
    """신청 줄의 포켓몬 모습."""
    return {"id": r["pokemon_id"], "name": r["name"], "species": r["species"], "num": r["num"],
            "look": r["look"] or r["num"], "shiny": bool(r["shiny"]), "tint": r["tint"]}


# ---------------------------------------------------------------- 지침
def fatigue_of(day):
    """{종목: {종: 깎는 몫}} - 앞 경기 날 출전자로 셈한다 (첫 날은 없다)."""
    prev = O.prev_day(day) if day else None
    if not prev:
        return {}
    out = {}
    for r in db.q("SELECT event, species, COUNT(*) c FROM olympic_entry WHERE day=? AND seed IS NOT NULL"
                  " GROUP BY event, species", (prev,)):
        out.setdefault(r["event"], {})[r["species"]] = int(r["c"])
    return dict((ev, O.fatigue_map(c)) for ev, c in out.items())


# ---------------------------------------------------------------- 신청
def _closed_msg(now):
    ph = O.phase(now)
    if ph == "before":
        return "올림픽 신청은 %s 부터 받아요." % O.OPEN[5:].replace("-", "/")
    if ph == "live":
        return "지금은 경기 중이에요. 오늘 경기가 끝나면 다음 경기 신청을 받아요."
    return "올림픽이 끝났어요."


def enter(uid, event, pid, tactic, now=None):
    now = _now(now)
    if event not in O.EV:
        raise HTTPException(400, "그런 종목은 없습니다.")
    if tactic not in O.TACTICS:
        raise HTTPException(400, "작전은 안정이나 승부수입니다.")
    day = O.entry_day(now)
    if day is None:
        raise HTTPException(409, _closed_msg(now))
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (int(pid), uid))
    if r is None:
        raise HTTPException(404, "그런 포켓몬이 없습니다.")
    from . import expedition                     # 탐험이 포켓몬 목록을 부른다 - 서로 부르지 않게 여기서
    if expedition.is_away(uid, pid):
        raise HTTPException(409, "탐험에 나가 있는 포켓몬은 출전할 수 없어요.")
    other = db.q1("SELECT event FROM olympic_entry WHERE day=? AND user_id=? AND pokemon_id=? AND event<>?",
                  (day, uid, int(pid), event))
    if other is not None:
        raise HTTPException(409, "이 포켓몬은 이번 경기에 %s에 나가요. 한 마리는 한 종목만 나갈 수 있어요."
                            % O.EV[other["event"]]["kr"])
    mon = db.row_to_mon(r)
    dec = deps.decorate(mon)
    sp = _sp(mon["species"])
    name = mon.get("nickname") or sp.get("kr") or mon["species"]
    args = (day, event, uid, int(pid), mon["species"], int(dec.get("num") or sp.get("num") or 0),
            dec.get("formNum"), 1 if mon.get("shiny") else 0, mon.get("tint"), name, mon.get("ability"),
            tactic, _iso(now), day)
    try:
        cur = db.run(
            "INSERT INTO olympic_entry (day, event, user_id, pokemon_id, species, num, look, shiny, tint, name,"
            " ability, tactic, entered_at) SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?"
            " WHERE NOT EXISTS (SELECT 1 FROM olympic_day WHERE day=?)"
            " ON CONFLICT(day, event, user_id) DO UPDATE SET pokemon_id=excluded.pokemon_id,"
            " species=excluded.species, num=excluded.num, look=excluded.look, shiny=excluded.shiny,"
            " tint=excluded.tint, name=excluded.name, ability=excluded.ability, tactic=excluded.tactic,"
            " entered_at=excluded.entered_at WHERE olympic_entry.seed IS NULL", args)
    except Exception as e:                                   # noqa: BLE001
        if "UNIQUE" not in str(e).upper():
            raise
        raise HTTPException(409, "이 포켓몬은 이번 경기에 다른 종목에 나가요.")
    if not getattr(cur, "rowcount", 1):
        raise HTTPException(409, "경기가 시작돼서 신청을 받지 않아요.")
    row = db.q1("SELECT * FROM olympic_entry WHERE day=? AND event=? AND user_id=?", (day, event, uid))
    return {"day": day, "entry": _entry_view(row),
            "message": korean.natural("%s이(가) %s에 나가요! (%s)" % (name, O.EV[event]["kr"],
                                                                O.TACTICS[tactic]["kr"]))}


def cancel(uid, event, now=None):
    now = _now(now)
    day = O.entry_day(now)
    if day is None or event not in O.EV:
        raise HTTPException(409, _closed_msg(now) if day is None else "그런 종목은 없습니다.")
    db.run("DELETE FROM olympic_entry WHERE day=? AND event=? AND user_id=? AND seed IS NULL"
           " AND NOT EXISTS (SELECT 1 FROM olympic_day WHERE day=?)", (day, event, uid, day))
    return {"day": day, "event": event}


def _entry_view(r):
    if r is None:
        return None
    return {"id": r["id"], "event": r["event"], "day": r["day"], "pokemon": _mon_view(r),
            "tactic": r["tactic"], "tacticKr": O.TACTICS.get(r["tactic"], {}).get("kr", r["tactic"])}


def candidates(uid, event, now=None):
    """신청 창: 내 포켓몬마다 별과 알기 쉬운 표시. 신청 받는 날 기준 (응원 · 지침)."""
    now = _now(now)
    if event not in O.EV:
        raise HTTPException(400, "그런 종목은 없습니다.")
    day = O.entry_day(now) or O.next_day(now)
    cheer = O.cheer_of(day) if day else ()
    fat = fatigue_of(day).get(event, {}) if day else {}
    pct = _pct()
    from . import expedition
    away = expedition.away_ids(uid)
    used = {}
    if day:
        for r in db.q("SELECT event, pokemon_id FROM olympic_entry WHERE day=? AND user_id=?", (day, uid)):
            used[r["pokemon_id"]] = r["event"]
    out = []
    for r in db.q("SELECT * FROM pokemon WHERE user_id=? ORDER BY on_desktop DESC, slot, id", (uid,)):
        mon = db.row_to_mon(r)
        sp = _sp(mon["species"])
        if not sp:
            continue
        m = O.mods(event, sp, mon.get("ability"), pct, cheer, fat.get(mon["species"], 0.0))
        out.append({"id": mon["id"], "name": mon.get("nickname") or sp.get("kr"), "species": sp.get("kr"),
                    "num": sp.get("num"), "level": mon["level"], "shiny": bool(mon.get("shiny")),
                    "onDesktop": bool(mon.get("onDesktop")), "kg": sp.get("kg"),
                    "types": [_type_kr(t) for t in sp.get("types") or ()],
                    "stars": O.stars(m), "hints": O.hints(event, sp, m, _type_kr, _ability_kr(mon.get("ability"))),
                    "away": mon["id"] in away,
                    "usedIn": used.get(mon["id"]) if used.get(mon["id"]) != event else None,
                    "entered": used.get(mon["id"]) == event})
    out.sort(key=lambda c: (c["away"], c["usedIn"] is not None, -c["stars"], not c["onDesktop"]))
    return {"event": event, "day": day, "pokemon": out}


# ---------------------------------------------------------------- 2시 경기
def ran(day):
    if day in _ran:
        return True
    if db.q1("SELECT 1 FROM olympic_day WHERE day=?", (day,)) is not None:
        _ran.add(day)
        return True
    return False


def _seed(*parts):
    return zlib.crc32(("|".join(str(p) for p in parts)).encode("utf-8")) & 0x7fffffff


def _compute(day, rows):
    """그날 신청 줄들 -> 적을 값들 [(seed, record, detail, heat, lane, rank, id)]. DB 를 안 건드린다."""
    pct = _pct()
    cheer = O.cheer_of(day)
    fat = fatigue_of(day)
    by_ev = {}
    for r in rows:
        by_ev.setdefault(r["event"], []).append(r)
    rng = random.SystemRandom()
    out = []
    for ev, lst in by_ev.items():
        res = {}
        for r in lst:
            sp = _sp(r["species"])
            seed = rng.randrange(1 << 30)
            if not sp:
                res[r["id"]] = (seed, None, {"tries": [], "mods": {}})
                continue
            got = O.play(ev, sp, r["ability"], r["tactic"], pct, cheer,
                         (fat.get(ev) or {}).get(r["species"], 0.0), seed=seed)
            res[r["id"]] = (seed, got["record"], {"tries": got["tries"], "mods": got["mods"]})
        heat_of = {}
        for hi, ids in enumerate(O.heats(sorted(res), _seed(day, ev))):
            for lane, i in enumerate(ids):
                heat_of[i] = (hi + 1, lane)
        order = sorted(lst, key=lambda r: (O.rank_key(ev, res[r["id"]][1]), r["entered_at"], r["id"]))
        for rank, r in enumerate(order, 1):
            seed, rec, det = res[r["id"]]
            h, lane = heat_of[r["id"]]
            out.append((seed, rec, json.dumps(det, ensure_ascii=False), h, lane, rank, r["id"]))
    return out


def run_day(day, now=None):
    """그날 경기를 치른다. 이미 치렀으면 아무것도 안 하고 False."""
    now = _now(now)
    if db.using_turso():                        # 운영은 sqlite 다. 시험용 Turso 는 문장 하나씩
        return _run_day_simple(day, now)
    conn = db.connect()
    try:
        if conn.in_transaction:
            conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM olympic_day WHERE day=?", (day,)).fetchone():
            conn.rollback()
            return False
        rows = conn.execute("SELECT * FROM olympic_entry WHERE day=?", (day,)).fetchall()
        upd = _compute(day, rows)
        conn.executemany("UPDATE olympic_entry SET seed=?, record=?, detail=?, heat=?, lane=?, rank=? WHERE id=?",
                         upd)
        at = _iso(now)
        conn.executemany(
            "INSERT OR IGNORE INTO pokemon_ribbon (pokemon_id, user_id, kind, event, at)"
            " SELECT ?, ?, 'oly_join', '', ? WHERE EXISTS (SELECT 1 FROM pokemon WHERE id=? AND user_id=?)",
            [(r["pokemon_id"], r["user_id"], at, r["pokemon_id"], r["user_id"]) for r in rows])
        conn.execute("INSERT INTO olympic_day (day, ran_at, n) VALUES (?,?,?)", (day, at, len(rows)))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:                                   # noqa: BLE001
            pass
        raise
    _ran.add(day)
    _boards_cache.clear()
    print("[olympics] %s 경기 %d건" % (day, len(rows)))
    return True


def _run_day_simple(day, now):
    cur = db.run("INSERT INTO olympic_day (day, ran_at, n) VALUES (?,?,0) ON CONFLICT(day) DO NOTHING",
                 (day, _iso(now)))
    if not getattr(cur, "rowcount", 1):
        return False
    rows = db.q("SELECT * FROM olympic_entry WHERE day=?", (day,))
    for u in _compute(day, rows):
        db.run("UPDATE olympic_entry SET seed=?, record=?, detail=?, heat=?, lane=?, rank=? WHERE id=?", u)
    for r in rows:
        db.run("INSERT OR IGNORE INTO pokemon_ribbon (pokemon_id, user_id, kind, event, at)"
               " SELECT ?, ?, 'oly_join', '', ? WHERE EXISTS (SELECT 1 FROM pokemon WHERE id=? AND user_id=?)",
               (r["pokemon_id"], r["user_id"], _iso(now), r["pokemon_id"], r["user_id"]))
    _ran.add(day)
    _boards_cache.clear()
    return True


def ensure_ran(now=None):
    """경기 시각이 지난 날을 모두 치르고, 다 끝났으면 폐막 정산까지. 요청마다 불러도 싸다 (치른 날은 기억한다)."""
    now = _now(now)
    todo = [d for d in O.ran_days(now) if d not in _ran]
    if todo:
        with _lock:
            for d in todo:
                if not ran(d):
                    run_day(d, now)
    if O.finished(now) and not _closed[0]:
        close(now)


def safe_ensure(now=None):
    """/api/me 에서 부른다 - 실패해도 동기화를 깨지 않는다."""
    try:
        ensure_ran(now)
    except Exception as e:                                   # noqa: BLE001
        from . import errors
        errors.record("OLY", "olympics.ensure_ran", e)


# ---------------------------------------------------------------- 순위표
def _released(day, event, now):
    return now >= O.release_at(day, event)


def _day_rows(event, day):
    return db.q("SELECT e.*, u.username FROM olympic_entry e JOIN users u ON u.id=e.user_id"
                " WHERE e.event=? AND e.day=? AND e.seed IS NOT NULL ORDER BY e.rank", (event, day))


def _weekly(event, now):
    """주간 순위 [(줄, 순위)] - 사람마다 공개된 날의 최고 기록 하나. 같으면 앞선 날 · 먼저 낸 쪽."""
    days = tuple(d for d in O.ran_days(now) if ran(d) and _released(d, event, now))
    key = (event, days)
    got = _boards_cache.get(key)
    if got is not None:
        return got
    best = {}
    for d in days:
        for r in _day_rows(event, d):
            if r["record"] is None:
                continue
            k = (O.rank_key(event, r["record"]), r["day"], r["entered_at"], r["id"])
            cur = best.get(r["user_id"])
            if cur is None or k < cur[0]:
                best[r["user_id"]] = (k, r)
    rows = [r for _k, r in sorted(best.values(), key=lambda x: x[0])]
    out = [(r, i) for i, r in enumerate(rows, 1)]
    _boards_cache[key] = out
    return out


def _names(rows):
    """{user_id: 지금 닉네임}. 순위 캐시의 줄에 든 이름은 옛것일 수 있다 (닉네임 변경권) - 그릴 때 새로 읽는다."""
    ids = sorted(set(int(r["user_id"]) for r in rows))
    if not ids:
        return {}
    return dict((x["id"], x["username"]) for x in db.q(
        "SELECT id, username FROM users WHERE id IN (%s)" % ",".join("?" * len(ids)), tuple(ids)))


def _board_row(r, rank, uid, names=None):
    user = (names or {}).get(r["user_id"]) or r["username"]
    return {"rank": rank, "user": user, "mine": r["user_id"] == uid, "entryId": r["id"],
            "day": r["day"], "pokemon": _mon_view(r), "record": r["record"], "text": O.text(r["event"], r["record"]),
            "tactic": r["tactic"]}


def board(uid, event, day=None, now=None):
    now = _now(now)
    if event not in O.EV:
        raise HTTPException(400, "그런 종목은 없습니다.")
    ensure_ran(now)
    if day:
        if day not in O.DAYS:
            raise HTTPException(400, "그런 경기 날은 없습니다.")
        if not ran(day) or not _released(day, event, now):
            return {"event": event, "day": day, "rows": [], "me": None, "total": 0, "hidden": True}
        ranked = [(r, r["rank"]) for r in _day_rows(event, day)]
    else:
        ranked = _weekly(event, now)
    top = ranked[:BOARD_TOP]
    mine = [(r, k) for r, k in ranked if r["user_id"] == uid]
    names = _names([r for r, _k in top + mine])
    me = next((_board_row(r, k, uid, names) for r, k in mine), None)
    return {"event": event, "day": day, "rows": [_board_row(r, k, uid, names) for r, k in top],
            "me": me, "total": len(ranked), "hidden": False}


# ---------------------------------------------------------------- 조 각본
def _heat_script(day, event, heat, uid, now):
    """한 조의 각본. 전체 순위(rank)는 그 종목 결과를 공개한 뒤에만 싣는다 - 중계 직후 결과 카드 · 다른 조 결과가
    순위표보다 먼저 새지 않게 (독립 검토 #2). 조 안의 순위는 기록으로 앱이 센다."""
    released = _released(day, event, now)
    rows = db.q("SELECT e.*, u.username FROM olympic_entry e JOIN users u ON u.id=e.user_id"
                " WHERE e.day=? AND e.event=? AND e.heat=? ORDER BY e.lane", (day, event, heat))
    ents = []
    for r in rows:
        det = json.loads(r["detail"] or "{}")
        ents.append({"entryId": r["id"], "lane": r["lane"], "user": r["username"], "mine": r["user_id"] == uid,
                     "pokemon": _mon_view(r), "tactic": r["tactic"], "record": r["record"],
                     "text": O.text(event, r["record"]), "tries": det.get("tries") or [], "seed": r["seed"],
                     "rank": r["rank"] if released else None})
    total = db.q1("SELECT COUNT(*) c FROM olympic_entry WHERE day=? AND event=?", (day, event))["c"]
    return {"day": day, "dayNo": O.day_no(day), "event": event, "kr": O.EV[event]["kr"], "heat": heat,
            "heats": db.q1("SELECT MAX(heat) h FROM olympic_entry WHERE day=? AND event=?", (day, event))["h"],
            "entrants": ents, "total": total, "cheer": [_type_kr(t) for t in O.cheer_of(day)]}


def heat(uid, entry_id, now=None):
    now = _now(now)
    ensure_ran(now)
    r = db.q1("SELECT * FROM olympic_entry WHERE id=?", (int(entry_id),))
    if r is None or r["seed"] is None:
        raise HTTPException(404, "그런 경기가 없습니다.")
    if r["user_id"] != uid:
        mine = db.q1("SELECT 1 FROM olympic_entry WHERE day=? AND event=? AND heat=? AND user_id=?",
                     (r["day"], r["event"], r["heat"], uid))
        if mine is None and not _released(r["day"], r["event"], now):
            raise HTTPException(403, "이 경기는 중계가 끝난 뒤에 볼 수 있어요.")
    return _heat_script(r["day"], r["event"], r["heat"], uid, now)


def live(uid, now=None):
    """오늘(또는 가장 최근) 경기 날의 프로그램과 내 조 각본. 앱이 2시에 부른다."""
    now = _now(now)
    ensure_ran(now)
    days = [d for d in O.ran_days(now) if ran(d)]
    if not days:
        return {"day": None, "heats": [], "program": []}
    day = days[-1]
    start = O.start_at(day)
    prog = [{"event": ev, "kr": O.EV[ev]["kr"], "showIn": _secs(O.show_at(day, ev), now),
             "releaseIn": _secs(O.release_at(day, ev), now)} for ev, _o in O.PROGRAM]
    heats = []
    for r in db.q("SELECT * FROM olympic_entry WHERE day=? AND user_id=? AND seed IS NOT NULL", (day, uid)):
        heats.append(_heat_script(day, r["event"], r["heat"], uid, now))
    order = dict((ev, i) for i, (ev, _o) in enumerate(O.PROGRAM))
    heats.sort(key=lambda h: order[h["event"]])
    _ach(uid)
    return {"day": day, "dayNo": O.day_no(day), "elapsed": _secs(now, start), "endIn": _secs(O.end_at(day), now),
            "program": prog, "heats": heats}


def _ach(uid):
    from . import achievements                 # 업적이 이 모듈의 stats 를 읽는다 - 서로 부르므로 여기서
    achievements.safe_check(uid)


# ---------------------------------------------------------------- 폐막
def _final_rows(event, now):
    return _weekly(event, now)


def _prize(rank, ev):
    """(칭호 id, 리본 종류, 볼)."""
    if rank <= 3:
        tid = "oly_gold_%s" % ev if rank == 1 else ("oly_silver" if rank == 2 else "oly_bronze")
        return tid, ("oly_gold", "oly_silver", "oly_bronze")[rank - 1], BALLS[rank]
    return "oly_final", "oly_final", FINAL_BALLS


def _final_and_balls(ev, top, at):
    """최종 순위 줄과 볼을 **한 트랜잭션으로** 넣는다. 줄을 먼저 커밋하고 볼을 나중에 주면, 그 사이에 실패했을 때
    다시 돌려도 '이미 줄이 있다' 로 볼을 영영 못 받는다 (독립 검토 #7). 칭호 · 리본은 '이미 있으면 그만' 이라 따로."""
    sql_f = ("INSERT INTO olympic_final (event, user_id, rank, entry_id, pokemon_id, record, at)"
             " VALUES (?,?,?,?,?,?,?) ON CONFLICT(event, user_id) DO NOTHING")
    sql_b = "UPDATE users SET balls=balls+? WHERE id=?"
    if db.using_turso():                         # 시험용 Turso: 문장 하나씩 (운영은 sqlite)
        for r, rank in top:
            cur = db.run(sql_f, (ev, r["user_id"], rank, r["id"], r["pokemon_id"], r["record"], at))
            if getattr(cur, "rowcount", 1):
                db.run(sql_b, (_prize(rank, ev)[2], r["user_id"]))
        return
    conn = db.connect()
    try:
        if conn.in_transaction:
            conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        for r, rank in top:
            cur = conn.execute(sql_f, (ev, r["user_id"], rank, r["id"], r["pokemon_id"], r["record"], at))
            if cur.rowcount:
                conn.execute(sql_b, (_prize(rank, ev)[2], r["user_id"]))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:                                   # noqa: BLE001
            pass
        raise


def close(now=None):
    """폐막 정산. 두 번 돌려도 한 번이다 (볼은 olympic_final 줄과 한 트랜잭션 · 칭호 · 리본은 '이미 있으면 그만').
    요청마다 겹쳐 돌지 않게 _lock 안에서 (경기 날 치르기와 같은 자물쇠)."""
    now = _now(now)
    if not O.finished(now):
        return False
    with _lock:
        return _close(now)


def _close(now):
    if db.q1("SELECT 1 FROM meta WHERE k='olympics:closed'") is not None:
        _closed[0] = True                       # 이미 정산했다 (서버를 다시 켠 뒤)
        return False
    at = _iso(now)
    for e in O.EVENTS:
        ev = e["key"]
        top = _final_rows(ev, now)[:O.FINAL_TO]
        _final_and_balls(ev, top, at)
        for r, rank in top:
            tid, kind, _balls = _prize(rank, ev)
            season.grant(r["user_id"], "title", tid, 0, equip_if_empty=False, now=at)
            _ribbon(r["pokemon_id"], r["user_id"], kind, ev, at)
        # 종족 1위: 그 종을 낸 사람이 SPECIES_MIN 명 이상인 종마다, 그 종 기록 중 가장 좋은 것.
        # 시기 셋을 다 파울한 사람(기록 없음)도 '낸 사람' 으로 센다 (기획: 그 종 출전자 3명 이상 - 독립 검토 #8)
        best, people = {}, {}
        for d in O.ran_days(now):
            for r in _day_rows(ev, d):
                people.setdefault(r["species"], set()).add(r["user_id"])
                if r["record"] is None:
                    continue
                k = (O.rank_key(ev, r["record"]), r["day"], r["entered_at"], r["id"])
                if r["species"] not in best or k < best[r["species"]][0]:
                    best[r["species"]] = (k, r)
        for spk, (_k, r) in best.items():
            if len(people.get(spk, ())) >= O.SPECIES_MIN:
                _ribbon(r["pokemon_id"], r["user_id"], "oly_species", ev, at)
    db.run("INSERT INTO meta (k, v) VALUES ('olympics:closed', ?) ON CONFLICT(k) DO NOTHING", (at,))
    _closed[0] = True
    print("[olympics] 폐막 정산 끝")
    return True


def _ribbon(pid, uid, kind, event, at):
    db.run("INSERT OR IGNORE INTO pokemon_ribbon (pokemon_id, user_id, kind, event, at)"
           " SELECT ?, ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM pokemon WHERE id=? AND user_id=?)",
           (pid, uid, kind, event, at, pid, uid))


def medals(now):
    """종목마다 1~3위 (끝났을 때만)."""
    out = {}
    for e in O.EVENTS:
        top = _weekly(e["key"], now)[:3]
        names = _names([r for r, _k in top])
        out[e["key"]] = [dict(_board_row(r, k, 0, names), rank=k) for r, k in top]
    return out


def my_medals(uid):
    rows = db.q("SELECT f.*, e.name, e.num, e.look, e.shiny, e.tint, e.species, e.pokemon_id"
                " FROM olympic_final f JOIN olympic_entry e ON e.id=f.entry_id WHERE f.user_id=? ORDER BY f.rank",
                (uid,))
    return [{"event": r["event"], "kr": O.EV[r["event"]]["kr"], "rank": r["rank"],
             "text": O.text(r["event"], r["record"]), "pokemon": _mon_view(r)} for r in rows]


def title_rows(now=None):
    """도감 탭 '칭호' 목록에 올릴 올림픽 칭호와 얻는 법. (id, 묶음, 조건, 지금 얻을 수 있나)"""
    is_open = not O.finished(_now(now))
    group = "포스크탑 올림픽" if is_open else "지난 이벤트 (다시 얻을 수 없음)"
    out = [("oly_gold_%s" % e["key"], group, "올림픽 %s 최종 1위" % e["kr"], is_open) for e in O.EVENTS]
    out += [("oly_silver", group, "올림픽 한 종목에서 최종 2위", is_open),
            ("oly_bronze", group, "올림픽 한 종목에서 최종 3위", is_open),
            ("oly_final", group, "올림픽 한 종목에서 최종 4~8위", is_open)]
    return out


# ---------------------------------------------------------------- 리본 (포켓몬 목록)
def ribbons_of(uid):
    """{포켓몬 id: [{kind, event, name}]} - 관리 창 상세가 한 줄로 그린다."""
    out = {}
    for r in db.q("SELECT pokemon_id, kind, event FROM pokemon_ribbon WHERE user_id=? ORDER BY id", (uid,)):
        name = RIBBON.get(r["kind"], r["kind"])
        if r["event"] in O.EV:
            name = "%s %s" % (O.EV[r["event"]]["short"], name)
        out.setdefault(r["pokemon_id"], []).append({"kind": r["kind"], "event": r["event"], "name": name})
    return out


# ---------------------------------------------------------------- 업적이 세는 값
def stats(uid):
    """{oly_entries, oly_events, oly_days, oly_species} - 경기를 치른 신청만 센다."""
    r = db.q1("SELECT COUNT(*) n, COUNT(DISTINCT event) ev, COUNT(DISTINCT day) d FROM olympic_entry"
              " WHERE user_id=? AND seed IS NOT NULL", (uid,))
    sp = db.q1("SELECT COUNT(*) n FROM pokemon_ribbon WHERE user_id=? AND kind='oly_species'", (uid,))
    return {"oly_entries": int(r["n"] or 0), "oly_events": int(r["ev"] or 0), "oly_days": int(r["d"] or 0),
            "oly_species": int(sp["n"] or 0)}


# ---------------------------------------------------------------- 상태
def _cheer(day):
    return [{"type": t, "kr": _type_kr(t)} for t in O.cheer_of(day)] if day else []


def _fatigue_view(day):
    out = {}
    for ev, m in fatigue_of(day).items():
        top = sorted(m.items(), key=lambda kv: -kv[1])[:FATIGUE_SHOW]
        out[ev] = [{"species": _sp(k).get("kr") or k, "pen": int(round(v * 100))} for k, v in top if v >= 0.01]
    return out


def state(uid, now=None):
    now = _now(now)
    ensure_ran(now)
    ph = O.phase(now)
    nday = O.next_day(now)
    eday = O.entry_day(now)
    mine = {}
    if nday:
        for r in db.q("SELECT * FROM olympic_entry WHERE day=? AND user_id=?", (nday, uid)):
            mine[r["event"]] = r
    last = [d for d in O.ran_days(now) if ran(d)]
    lday = last[-1] if last else None
    last_rows = {}
    if lday:
        for r in db.q("SELECT * FROM olympic_entry WHERE day=? AND user_id=? AND seed IS NOT NULL", (lday, uid)):
            last_rows[r["event"]] = r
    events = []
    for e in O.EVENTS:
        ev = e["key"]
        wk = _weekly(ev, now)
        best = next(((r, k) for r, k in wk if r["user_id"] == uid), None)
        lr = last_rows.get(ev)
        events.append({
            "key": ev, "kr": e["kr"], "short": e["short"], "statKr": e["statKr"], "kg0": e["kg0"],
            "types": [_type_kr(t) for t in e["types"]], "abil": [_ability_kr(a) for a in e["abil"]],
            "dislike": [_type_kr(t) for t in e["dislike"]], "tries": e["tries"],
            "entry": _entry_view(mine.get(ev)) if (nday and mine.get(ev) is not None
                                                   and mine[ev]["seed"] is None) else None,
            "best": ({"record": best[0]["record"], "text": O.text(ev, best[0]["record"]), "rank": best[1],
                      "total": len(wk), "day": best[0]["day"], "entryId": best[0]["id"]} if best else None),
            # 중계가 끝나기 전에는 기록도 감춘다 (창에서 먼저 보면 중계가 김빠진다 - 데모 11/06)
            "last": ({"day": lr["day"], "entryId": lr["id"], "heat": lr["heat"],
                      "text": O.text(ev, lr["record"]) if _released(lr["day"], ev, now) else None,
                      "pokemon": _mon_view(lr),
                      "rank": lr["rank"] if _released(lr["day"], ev, now) else None,
                      "released": _released(lr["day"], ev, now)} if lr else None),
        })
    out = {"phase": ph, "days": list(O.DAYS), "at": O.AT, "nextDay": nday, "entryDay": eday,
           "dayNo": O.day_no(nday) if nday else len(O.DAYS),
           "startsIn": _secs(O.start_at(nday), now) if nday else None,
           "openIn": _secs(O.open_at(O.DAYS[0]), now) if ph == "before" and O.DAYS else None,
           "cheer": _cheer(nday), "fatigue": _fatigue_view(eday or nday) if nday else {},
           "program": [{"event": ev, "kr": O.EV[ev]["kr"], "offset": off} for ev, off in O.PROGRAM],
           "lastDay": lday, "events": events,
           "tactics": [{"key": k, "kr": v["kr"]} for k, v in (("safe", O.TACTICS["safe"]),
                                                              ("bold", O.TACTICS["bold"]))]}
    if O.finished(now):
        out["medals"] = medals(now)
        out["myMedals"] = my_medals(uid)
    _ach(uid)
    return out


def me_card(uid, now=None):
    """/api/me 에 싣는 짧은 것. 기간 밖이면 None (질의도 없다). 앱이 2시 중계를 예약하는 데 쓴다.
    경기 날을 비워 두면(POKET_OLYMPICS_DAYS='') 늘 None - 여기서 터지면 모든 사람의 동기화가 멈춘다 (독립 검토 #10)."""
    if not O.DAYS:
        return None
    now = _now(now)
    ph = O.phase(now)
    if ph in ("before", "closed"):
        if ph == "before" and (O.open_at(O.DAYS[0]) - now).total_seconds() > 3 * 86400:
            return None
        return {"phase": ph, "openIn": _secs(O.open_at(O.DAYS[0]), now) if ph == "before" else None}
    safe_ensure(now)
    nday = O.next_day(now)
    out = {"phase": ph, "nextDay": nday, "dayNo": O.day_no(nday) if nday else None,
           "startsIn": _secs(O.start_at(nday), now) if nday else None,
           "endIn": _secs(O.end_at(nday), now) if nday else None}
    if nday:
        out["entries"] = db.q1("SELECT COUNT(*) c FROM olympic_entry WHERE day=? AND user_id=?", (nday, uid))["c"]
    if ph == "done":
        out["medals"] = len(db.q("SELECT 1 FROM olympic_final WHERE user_id=? AND rank<=3", (uid,)))
    return out


# ---------------------------------------------------------------- 라우트
class EnterIn(BaseModel):
    event: str
    pokemon: int
    tactic: str = "safe"


class CancelIn(BaseModel):
    event: str


@router.get("/api/olympics")
def get_state(ctx=Depends(deps.current)):
    return state(ctx["user"]["id"])


@router.get("/api/olympics/candidates")
def get_candidates(event: str, ctx=Depends(deps.current)):
    return candidates(ctx["user"]["id"], event)


@router.post("/api/olympics/enter")
def post_enter(body: EnterIn, ctx=Depends(deps.current)):
    return enter(ctx["user"]["id"], body.event, body.pokemon, body.tactic)


@router.post("/api/olympics/cancel")
def post_cancel(body: CancelIn, ctx=Depends(deps.current)):
    return cancel(ctx["user"]["id"], body.event)


@router.get("/api/olympics/live")
def get_live(ctx=Depends(deps.current)):
    return live(ctx["user"]["id"])


@router.get("/api/olympics/heat")
def get_heat(id: int, ctx=Depends(deps.current)):         # noqa: A002 - 쿼리 이름
    return heat(ctx["user"]["id"], id)


@router.get("/api/olympics/board")
def get_board(event: str, day: str = "", ctx=Depends(deps.current)):
    return board(ctx["user"]["id"], event, day or None)
