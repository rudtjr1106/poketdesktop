# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 서버 쪽 (하루 한 종목 · 그날 예선부터 결승까지, 11/08 사용자 결정).

    GET  /api/olympics                        종목 일곱 줄(날 · 상태 · 내 신청 · 내 결과) · 응원 · 다음 종목 · 메달
    GET  /api/olympics/candidates?event       신청 창: 내 포켓몬마다 별과 표시 · 지금 신청자의 종 몫(지침)
    POST /api/olympics/enter                  신청 {event, pokemon, tactic} - 같은 종목에 다시 내면 바뀐다
    POST /api/olympics/cancel                 신청 취소 {event}
    GET  /api/olympics/live                   오늘 종목의 시각표 + 첫 라운드 내 조 각본 (앱이 2시에 부른다)
    GET  /api/olympics/show?round=            그 라운드에 내가 볼 조 각본 (내 조, 아니면 메달 라운드) - 그 중계 직전부터
    GET  /api/olympics/heat?event&round&heat  조 하나의 각본 (다시 보기 - 내 조이거나 공개된 것)
    GET  /api/olympics/board?event            라운드별 결과(공개된 것) · 최종 순위(그날 중계가 끝난 뒤)

규칙 · 공식은 common/olympics.py, 라운드 · 종목 엔진 · 시각표는 common/olympics_rounds.py (앱도 같은 것을 읽는다).
설계: design-notes/2026-11-08-olympics-rounds.md

## 경기는 그 종목 날 2시에 한 번

경기 날 14:00 KST 가 지나면, 그 뒤 처음 오는 요청(/api/me · /api/olympics*)이 그날 종목의 **모든 라운드를** 치른다
(ensure_ran). **olympic_day 줄을 넣는 것과 결과(olympic_heat · olympic_slot · olympic_entry)를 적는 것이 한 트랜잭션** -
두 요청이 겹쳐도 한 번만 돌고, 그 사이에 들어온 신청은 olympic_day 줄을 보고 들어가지 않는다.

## 공개 (중계보다 결과가 먼저 새지 않게)

- 첫 라운드 내 조 각본은 경기를 치른 뒤 바로 준다 (/live). 두 번째 라운드부터는 **그 라운드 중계 직전**(앞 라운드
  중계가 끝나는 때)부터 /show 로 준다 - 미리 주면 '준결승에 나간다' 가 예선 중계 전에 드러난다.
- 진출 표시(Q/q) · 남의 조 = 다음 라운드 중계가 시작할 때. 최종 순위 · 메달 = 그날 중계(시상식 포함)가 끝날 때.

## 정산 (그 종목 중계가 끝난 뒤)

최종 순위 1~3위 메달 꾸미기(선물함) · 그 종목 칭호(O.TITLE) · 리본 · 볼, 4~8위 결선 진출 칭호 · 리본 · 볼, 종족 1위
리본(그 종 출전 ≥ 3). **olympic_final 줄을 먼저 넣은 쪽만 볼 · 메달 선물을 준다** - 정산을 두 번 돌려도 한 번.
돈 · 코인 · 팔 수 있는 도구는 주지 않는다.
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
from common import olympics_rounds as OR

from . import db, deps, season

router = APIRouter()

TITLES = {"oly_final": "올림픽 결선 진출"}
for _e in O.EVENTS:
    TITLES["oly_%s" % _e["key"]] = O.TITLE[_e["key"]]          # 1~3위 - 종목 특징 이름 (금 · 은 · 동 같이)
season.TITLES.update(TITLES)
BALLS = {1: 20, 2: 15, 3: 10}
FINAL_BALLS = 5
RIBBON = {"oly_gold": "금메달 리본", "oly_silver": "은메달 리본", "oly_bronze": "동메달 리본",
          "oly_final": "결선 리본", "oly_species": "종족 1위 리본", "oly_join": "올림픽 참가 리본"}
BOARD_TOP = 50
SHARE_SHOW = 5              # 신청 창에 보여 주는 '지금 몫' 상위 종 수
MEDAL_KEYS = ("final", "bronze")     # 떨어졌어도 보여 주는 라운드 (결승 · 양궁 동메달전) - 마지막 라운드도 늘 포함

_lock = threading.Lock()
_ran = set()                 # 이 프로세스가 이미 확인한 '치른 날'
_settled = set()             # 이 프로세스가 이미 확인한 '정산한 종목'
_info = {}                   # 날 -> 그날 정보 (치른 뒤에는 바뀌지 않는다)
_heats = {}                  # (종목, 라운드, 조) -> 조 JSON
_pct_cache = {}


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


def _cheer(day):
    return [{"type": t, "kr": _type_kr(t)} for t in O.cheer_of(day)] if day else []


# ---------------------------------------------------------------- 그날 정보
def day_info(day):
    """치른 날의 {event, n, program, end, rounds}. 아직 안 치렀으면 None."""
    got = _info.get(day)
    if got is not None:
        return got
    r = db.q1("SELECT * FROM olympic_day WHERE day=?", (day,))
    if r is None:
        return None
    data = json.loads(r["data"] or "{}")
    got = {"event": r["event"] or O.event_of(day), "n": int(r["n"] or 0), "program": data.get("program") or [],
           "end": int(data.get("end") or 0), "rounds": data.get("rounds") or []}
    _info[day] = got
    return got


def _ends():
    """{치른 날: 그날 end} - 페이즈 · 중계 중 판정에 쓴다 (안 치른 날은 O.DEFAULT_END)."""
    out = {}
    for d in O.DAYS:
        if d in _ran or ran(d):
            out[d] = day_info(d)["end"]
    return out


def _end_t(day):
    info = day_info(day)
    return O.end_at(day, info["end"] if info else None)


def _round_at(day, round_no):
    """그 라운드 중계가 시작하는 때."""
    info = day_info(day)
    return O.start_at(day) + datetime.timedelta(seconds=info["program"][round_no - 1]["at"])


def released(day, round_no, now):
    """그 라운드 결과(진출 표시 · 남의 조)를 여는 때 = 다음 라운드 중계 시작 (마지막은 그날 끝)."""
    info = day_info(day)
    if info is None:
        return False
    if round_no < len(info["program"]):
        return now >= _round_at(day, round_no + 1)
    return now >= _end_t(day)


def _medal_round(info, round_no):
    r = info["rounds"][round_no - 1]
    return round_no == len(info["rounds"]) or r["key"] in MEDAL_KEYS


# ---------------------------------------------------------------- 지침
def fatigue_live(event):
    """(그 종목 지금 신청자의 {종: 수}, {종: 깎는 몫}) - 2시에 확정된 신청으로 경기를 치른다."""
    counts = {}
    for r in db.q("SELECT species, COUNT(*) c FROM olympic_entry WHERE event=? AND day=? GROUP BY species",
                  (event, O.day_of(event))):
        counts[r["species"]] = int(r["c"])
    return counts, O.fatigue_map(counts)


# ---------------------------------------------------------------- 신청
def _closed_msg(event, now):
    if now < O.open_at():
        return "올림픽 신청은 %s 부터 받아요." % O.OPEN[5:].replace("-", "/")
    day = O.day_of(event)
    return "%s 신청은 %d/%d %s에 마감됐어요." % (O.EV[event]["kr"], int(day[5:7]), int(day[8:10]), O.at_text())


def enter(uid, event, pid, tactic, now=None):
    now = _now(now)
    if event not in O.EV:
        raise HTTPException(400, "그런 종목은 없습니다.")
    if tactic not in O.TACTICS:
        raise HTTPException(400, "작전은 안정이나 승부수입니다.")
    if not O.entry_open(event, now):
        raise HTTPException(409, _closed_msg(event, now))
    day = O.day_of(event)
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (int(pid), uid))
    if r is None:
        raise HTTPException(404, "그런 포켓몬이 없습니다.")
    from . import expedition                     # 탐험이 포켓몬 목록을 부른다 - 서로 부르지 않게 여기서
    if expedition.is_away(uid, pid):
        raise HTTPException(409, "탐험에 나가 있는 포켓몬은 출전할 수 없어요.")
    mon = db.row_to_mon(r)
    dec = deps.decorate(mon)
    sp = _sp(mon["species"])
    name = mon.get("nickname") or sp.get("kr") or mon["species"]
    args = (day, event, uid, int(pid), mon["species"], int(dec.get("num") or sp.get("num") or 0),
            dec.get("formNum"), 1 if mon.get("shiny") else 0, mon.get("tint"), name, mon.get("ability"),
            tactic, _iso(now), day)
    cur = db.run(
        "INSERT INTO olympic_entry (day, event, user_id, pokemon_id, species, num, look, shiny, tint, name,"
        " ability, tactic, entered_at) SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?"
        " WHERE NOT EXISTS (SELECT 1 FROM olympic_day WHERE day=?)"
        " ON CONFLICT(day, event, user_id) DO UPDATE SET pokemon_id=excluded.pokemon_id,"
        " species=excluded.species, num=excluded.num, look=excluded.look, shiny=excluded.shiny,"
        " tint=excluded.tint, name=excluded.name, ability=excluded.ability, tactic=excluded.tactic,"
        " entered_at=excluded.entered_at WHERE olympic_entry.seed IS NULL", args)
    if not getattr(cur, "rowcount", 1):
        raise HTTPException(409, "경기가 시작돼서 신청을 받지 않아요.")
    row = db.q1("SELECT * FROM olympic_entry WHERE day=? AND event=? AND user_id=?", (day, event, uid))
    return {"day": day, "entry": _entry_view(row),
            "message": korean.natural("%s이(가) %s에 나가요! (%d/%d %s, %s)" % (
                name, O.EV[event]["kr"], int(day[5:7]), int(day[8:10]), O.at_text(), O.TACTICS[tactic]["kr"]))}


def cancel(uid, event, now=None):
    now = _now(now)
    if event not in O.EV:
        raise HTTPException(400, "그런 종목은 없습니다.")
    if not O.entry_open(event, now):
        raise HTTPException(409, _closed_msg(event, now))
    day = O.day_of(event)
    db.run("DELETE FROM olympic_entry WHERE day=? AND event=? AND user_id=? AND seed IS NULL"
           " AND NOT EXISTS (SELECT 1 FROM olympic_day WHERE day=?)", (day, event, uid, day))
    return {"day": day, "event": event}


def _entry_view(r):
    if r is None:
        return None
    return {"id": r["id"], "event": r["event"], "day": r["day"], "pokemon": _mon_view(r),
            "tactic": r["tactic"], "tacticKr": O.TACTICS.get(r["tactic"], {}).get("kr", r["tactic"])}


def candidates(uid, event, now=None):
    """신청 창: 내 포켓몬마다 별과 알기 쉬운 표시 (그 종목 날의 응원 · 지금 신청자 몫으로 센 지침)."""
    now = _now(now)
    if event not in O.EV:
        raise HTTPException(400, "그런 종목은 없습니다.")
    day = O.day_of(event)
    cheer = O.cheer_of(day)
    counts, fat = fatigue_live(event)
    tot = sum(counts.values())
    share = [{"species": _sp(k).get("kr") or k, "pct": int(round(100.0 * c / tot))}
             for k, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:SHARE_SHOW]] if tot else []
    pct = _pct()
    from . import expedition
    away = expedition.away_ids(uid)
    other = {}
    for r in db.q("SELECT event, pokemon_id FROM olympic_entry WHERE user_id=? AND seed IS NULL", (uid,)):
        other.setdefault(r["pokemon_id"], []).append(r["event"])
    out = []
    for r in db.q("SELECT * FROM pokemon WHERE user_id=? ORDER BY on_desktop DESC, slot, id", (uid,)):
        mon = db.row_to_mon(r)
        sp = _sp(mon["species"])
        if not sp:
            continue
        m = O.mods(event, sp, mon.get("ability"), pct, cheer, fat.get(mon["species"], 0.0))
        evs = other.get(mon["id"]) or []
        out.append({"id": mon["id"], "name": mon.get("nickname") or sp.get("kr"), "species": sp.get("kr"),
                    "num": sp.get("num"), "level": mon["level"], "shiny": bool(mon.get("shiny")),
                    "onDesktop": bool(mon.get("onDesktop")), "kg": sp.get("kg"),
                    "types": [_type_kr(t) for t in sp.get("types") or ()],
                    "stars": O.stars(m), "hints": O.hints(event, sp, m, _type_kr, _ability_kr(mon.get("ability"))),
                    "away": mon["id"] in away, "entered": event in evs,
                    "alsoIn": [O.EV[e]["short"] for e in evs if e != event]})
    out.sort(key=lambda c: (c["away"], -c["stars"], not c["onDesktop"]))
    return {"event": event, "day": day, "pokemon": out, "share": share, "total": tot}


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


def _compute(day, event, rows):
    """그날 신청 줄들 -> (대회 comp, 시각표, end, 씨앗, {신청 id: 몫}). DB 를 안 건드린다."""
    pct = _pct()
    cheer = O.cheer_of(day)
    counts = {}
    for r in rows:
        counts[r["species"]] = counts.get(r["species"], 0) + 1
    fat = O.fatigue_map(counts)
    order = sorted(rows, key=lambda r: (r["entered_at"], r["id"]))
    ents, mods = [], {}
    for k, r in enumerate(order):
        sp = _sp(r["species"])
        f = fat.get(r["species"], 0.0)
        ents.append({"id": r["id"], "sp": sp, "ability": r["ability"], "tactic": r["tactic"], "fat": f, "order": k})
        mods[r["id"]] = dict((a, round(b, 4)) for a, b in O.mods(event, sp, r["ability"], pct, cheer, f).items())
    seed = random.SystemRandom().randrange(1 << 30)
    comp = OR.run(event, ents, {"pct": pct, "cheer": cheer, "seed": seed})
    prog, end = OR.program(comp)
    return comp, prog, end, seed, mods


def _writes(day, event, rows, comp, prog, end, seed, mods, at):
    """치른 결과를 적는 문장들 [(sql, args)]. 한 트랜잭션으로 돈다."""
    out = []
    reached = {}
    for rnd in comp["rounds"]:
        for h in rnd["heats"]:
            out.append(("INSERT INTO olympic_heat (event, round, heat, data) VALUES (?,?,?,?)",
                        (event, rnd["no"], h["no"], json.dumps(h, ensure_ascii=False))))
            for i in h["ids"]:
                out.append(("INSERT OR IGNORE INTO olympic_slot (event, entry_id, round, heat) VALUES (?,?,?,?)",
                            (event, i, rnd["no"], h["no"])))
                reached[i] = max(reached.get(i, 0), rnd["no"])
    for s in comp["standings"]:
        out.append(("UPDATE olympic_entry SET seed=?, record=?, rank=?, reached=?, detail=? WHERE id=?",
                    (seed, s["record"], s["rank"], reached.get(s["id"]),
                     json.dumps({"mods": mods.get(s["id"], {})}, ensure_ascii=False), s["id"])))
    for r in rows:
        out.append(("INSERT OR IGNORE INTO pokemon_ribbon (pokemon_id, user_id, kind, event, at)"
                    " SELECT ?, ?, 'oly_join', '', ? WHERE EXISTS (SELECT 1 FROM pokemon WHERE id=? AND user_id=?)",
                    (r["pokemon_id"], r["user_id"], at, r["pokemon_id"], r["user_id"])))
    meta = [{"no": r["no"], "key": r["key"], "kr": r["kr"], "format": r["format"], "note": r["note"],
             "heats": len(r["heats"]), "k": r.get("k", 0)} for r in comp["rounds"]]
    out.append(("INSERT INTO olympic_day (day, ran_at, n, event, data) VALUES (?,?,?,?,?)",
                (day, at, len(rows), event, json.dumps({"program": prog, "end": end, "rounds": meta},
                                                       ensure_ascii=False))))
    return out


def run_day(day, now=None):
    """그날 종목을 치른다 (모든 라운드). 이미 치렀으면 아무것도 안 하고 False."""
    now = _now(now)
    event = O.event_of(day)
    if not event:
        return False
    if db.using_turso():                        # 운영은 sqlite 다. 시험용 Turso 는 문장 하나씩 (먼저 줄을 잡는다)
        return _run_day_simple(day, event, now)
    conn = db.connect()
    try:
        if conn.in_transaction:
            conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM olympic_day WHERE day=?", (day,)).fetchone():
            conn.rollback()
            return False
        rows = conn.execute("SELECT * FROM olympic_entry WHERE day=? AND event=?", (day, event)).fetchall()
        comp, prog, end, seed, mods = _compute(day, event, rows)
        for sql, args in _writes(day, event, rows, comp, prog, end, seed, mods, _iso(now)):
            conn.execute(sql, args)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:                                   # noqa: BLE001
            pass
        raise
    _ran.add(day)
    print("[olympics] %s %s 경기 %d건" % (day, event, len(rows)))
    return True


def _run_day_simple(day, event, now):
    cur = db.run("INSERT INTO olympic_day (day, ran_at, n, event, data) VALUES (?,?,0,?,NULL)"
                 " ON CONFLICT(day) DO NOTHING", (day, _iso(now), event))
    if not getattr(cur, "rowcount", 1):
        return False
    rows = db.q("SELECT * FROM olympic_entry WHERE day=? AND event=?", (day, event))
    comp, prog, end, seed, mods = _compute(day, event, rows)
    for sql, args in _writes(day, event, rows, comp, prog, end, seed, mods, _iso(now)):
        if sql.startswith("INSERT INTO olympic_day"):
            db.run("UPDATE olympic_day SET n=?, data=? WHERE day=?", (args[2], args[4], day))
        else:
            db.run(sql, args)
    _ran.add(day)
    return True


def ensure_ran(now=None):
    """경기 시각이 지난 날을 모두 치르고, 중계가 끝난 종목은 정산한다. 요청마다 불러도 싸다 (치른 날은 기억한다)."""
    now = _now(now)
    todo = [d for d in O.ran_days(now) if d not in _ran]
    if todo:
        with _lock:
            for d in todo:
                if not ran(d):
                    run_day(d, now)
    for d in O.ran_days(now):
        ev = O.event_of(d)
        if ev and ev not in _settled and ran(d) and now >= _end_t(d):
            settle(ev, d, now)


def safe_ensure(now=None):
    """/api/me 에서 부른다 - 실패해도 동기화를 깨지 않는다."""
    try:
        ensure_ran(now)
    except Exception as e:                                   # noqa: BLE001
        from . import errors
        errors.record("OLY", "olympics.ensure_ran", e)


# ---------------------------------------------------------------- 조 각본
def _heat(event, round_no, heat_no):
    k = (event, int(round_no), int(heat_no))
    got = _heats.get(k)
    if got is None:
        r = db.q1("SELECT data FROM olympic_heat WHERE event=? AND round=? AND heat=?", k)
        if r is None:
            return None
        got = json.loads(r["data"])
        _heats[k] = got
    return got


def _rows(ids):
    ids = [int(i) for i in ids]
    if not ids:
        return {}
    return dict((r["id"], r) for r in db.q(
        "SELECT e.*, u.username FROM olympic_entry e JOIN users u ON u.id=e.user_id WHERE e.id IN (%s)"
        % ",".join("?" * len(ids)), tuple(ids)))


def _res_text(event, fmt, res):
    if not res:
        return ""
    if fmt == "rank":
        return "%d점" % int(res.get("v") or 0)
    if fmt == "match":
        return "세트 %d" % int(res.get("v") or 0)
    if fmt == "ski":
        return "%.1f점" % float(res.get("total", res.get("pts")) or 0)
    if fmt == "trial":
        return O.text(event, res.get("total", res.get("v")))
    return O.text(event, res.get("v"))


def final_text(event, rec):
    """최종 순위의 기록 글 (양궁은 순위만 - 기록은 랭킹 점수라 헷갈린다)."""
    if event == "archery":
        return ""
    if event == "ski":
        return "%.1f점" % rec if rec is not None else "기록 없음"
    return O.text(event, rec)


def heat_script(day, event, round_no, heat_no, uid, now):
    """조 하나의 각본. 진출 표시(q)는 그 라운드 결과를 연 뒤에만 싣는다."""
    info = day_info(day)
    h = _heat(event, round_no, heat_no)
    if info is None or h is None:
        raise HTTPException(404, "그런 경기가 없습니다.")
    meta = info["rounds"][round_no - 1]
    rel = released(day, round_no, now)
    rows = _rows(h["ids"])
    ents = []
    for i in h["ids"]:
        r = rows.get(int(i))
        if r is None:
            continue                                         # 계정을 지운 사람
        k = str(i)
        res = (h.get("res") or {}).get(k) or {}
        ents.append({"entryId": int(i), "lane": (h.get("lanes") or {}).get(k), "user": r["username"],
                     "mine": r["user_id"] == uid, "pokemon": _mon_view(r), "tactic": r["tactic"], "res": res,
                     "place": (h.get("place") or {}).get(k),
                     "record": res.get("total", res.get("v")), "text": _res_text(event, meta["format"], res),
                     "q": (h.get("q") or {}).get(k) if rel else None})
    out = {"day": day, "dayNo": O.day_no(day), "event": event, "kr": O.EV[event]["kr"],
           "round": {"no": round_no, "key": meta["key"], "kr": meta["kr"], "of": len(info["rounds"]),
                     "medal": _medal_round(info, round_no), "k": meta.get("k", 0)},
           "heat": heat_no, "heats": meta["heats"], "format": meta["format"], "note": meta["note"],
           "entrants": ents, "total": info["n"], "cheer": [c["kr"] for c in _cheer(day)], "released": rel}
    for k in ("match", "after3", "heights"):
        if k in h:
            out[k] = h[k]
    return out


def _mine(event, uid):
    return db.q1("SELECT * FROM olympic_entry WHERE event=? AND day=? AND user_id=?", (event, O.day_of(event), uid))


def _my_heat(event, entry_id, round_no):
    r = db.q1("SELECT heat FROM olympic_slot WHERE event=? AND entry_id=? AND round=?", (event, entry_id, round_no))
    return r["heat"] if r else None


def _today(now):
    days = [d for d in O.ran_days(now) if ran(d)]
    return days[-1] if days else None


def live(uid, now=None):
    """오늘(가장 최근) 경기 날의 시각표와 첫 라운드 내 조 각본. 앱이 2시에 부른다 (뒤 라운드는 /show)."""
    now = _now(now)
    ensure_ran(now)
    day = _today(now)
    if not day:
        return {"day": None, "program": [], "first": None}
    info = day_info(day)
    event = info["event"]
    start = O.start_at(day)
    prog = []
    for p, r in zip(info["program"], info["rounds"]):
        rel = O.start_at(day) + datetime.timedelta(seconds=(info["program"][r["no"]]["at"] if r["no"] < len(
            info["program"]) else info["end"]))
        prog.append({"round": r["no"], "key": r["key"], "kr": r["kr"], "format": r["format"], "len": p["len"],
                     "showIn": _secs(start + datetime.timedelta(seconds=p["at"]), now), "releaseIn": _secs(rel, now),
                     "medal": _medal_round(info, r["no"])})
    me = _mine(event, uid)
    first = None
    if me is not None and me["seed"] is not None and info["rounds"]:
        h = _my_heat(event, me["id"], 1)
        if h:
            first = heat_script(day, event, 1, h, uid, now)
    _ach(uid)
    return {"day": day, "dayNo": O.day_no(day), "event": event, "kr": O.EV[event]["kr"],
            "entered": me is not None, "elapsed": _secs(now, start), "endIn": _secs(_end_t(day), now),
            "program": prog, "first": first}


def show(uid, round_no, now=None):
    """그 라운드에 내가 볼 조: 내가 뛴 조, 아니면 메달 라운드(결승 · 동메달전)의 조. 신청한 사람만.
    **앞 라운드 중계가 끝나는 때부터** 준다 - 그 전에 주면 다음 라운드에 나간다는 것이 먼저 드러난다."""
    now = _now(now)
    ensure_ran(now)
    day = _today(now)
    info = day_info(day) if day else None
    round_no = int(round_no)
    if info is None or not (1 <= round_no <= len(info["rounds"])):
        raise HTTPException(404, "그런 경기가 없습니다.")
    event = info["event"]
    me = _mine(event, uid)
    if me is None:
        return {"script": None}
    if round_no > 1 and now < _round_at(day, round_no) - datetime.timedelta(seconds=OR.GAP):
        raise HTTPException(409, "아직 이 라운드 중계 전이에요.")
    h = _my_heat(event, me["id"], round_no)
    if h is None and _medal_round(info, round_no):
        h = 1
    if h is None:
        return {"script": None}
    return {"script": heat_script(day, event, round_no, h, uid, now)}


def heat(uid, event, round_no, heat_no, now=None):
    """다시 보기: 내가 뛴 조(그 중계가 시작한 뒤), 메달 라운드(그 중계가 시작한 뒤), 그 밖에는 결과를 연 뒤."""
    now = _now(now)
    ensure_ran(now)
    if event not in O.EV:
        raise HTTPException(400, "그런 종목은 없습니다.")
    day = O.day_of(event)
    info = day_info(day) if ran(day) else None
    round_no, heat_no = int(round_no), int(heat_no)
    if info is None or not (1 <= round_no <= len(info["rounds"])) or _heat(event, round_no, heat_no) is None:
        raise HTTPException(404, "그런 경기가 없습니다.")
    if not released(day, round_no, now):
        me = _mine(event, uid)
        started = now >= _round_at(day, round_no)
        mine = me is not None and _my_heat(event, me["id"], round_no) == heat_no
        if not (started and (mine or _medal_round(info, round_no))):
            raise HTTPException(403, "이 경기는 중계가 끝난 뒤에 볼 수 있어요.")
    return heat_script(day, event, round_no, heat_no, uid, now)


# ---------------------------------------------------------------- 결과표
def _names(uids):
    ids = sorted(set(int(x) for x in uids))
    if not ids:
        return {}
    return dict((x["id"], x["username"]) for x in db.q(
        "SELECT id, username FROM users WHERE id IN (%s)" % ",".join("?" * len(ids)), tuple(ids)))


def _heat_order(event, fmt, h):
    """조 안의 차례 (조 순위). 엔진이 적은 place 가 있으면 그대로 (동점 처리까지 엔진과 같다)."""
    res = h.get("res") or {}
    ids = [str(i) for i in h["ids"]]
    pl = h.get("place") or {}
    if pl and all(k in pl for k in ids):
        return sorted(ids, key=lambda k: pl[k])
    if fmt == "match":
        win = str((h.get("match") or {}).get("win"))
        return sorted(ids, key=lambda k: k != win)
    if fmt == "bar":
        return sorted(ids, key=lambda k: OR.pole_key(res.get(k) or {}, 0, 0))
    if fmt == "trial":
        return sorted(ids, key=lambda k: (res.get(k) or {}).get("total") or 1e9)
    if fmt == "ski":
        return sorted(ids, key=lambda k: -float((res.get(k) or {}).get("total", (res.get(k) or {}).get("pts")) or 0))
    if fmt == "field":
        return sorted(ids, key=lambda k: OR._field_key(event, (res.get(k) or {}).get("tries") or [], 0, 0))
    return sorted(ids, key=lambda k: O.rank_key(event, (res.get(k) or {}).get("v")) if fmt != "rank"
                  else -((res.get(k) or {}).get("v") or 0))


def board(uid, event, now=None):
    now = _now(now)
    if event not in O.EV:
        raise HTTPException(400, "그런 종목은 없습니다.")
    ensure_ran(now)
    day = O.day_of(event)
    info = day_info(day) if ran(day) else None
    out = {"event": event, "kr": O.EV[event]["kr"], "day": day, "rounds": [], "standings": [], "me": None,
           "total": info["n"] if info else 0, "hidden": True}
    if info is None:
        return out
    my_id = _mine_id(event, uid)
    for meta in info["rounds"]:
        if not released(day, meta["no"], now):
            break
        heats = []
        all_ids = []
        hs = [_heat(event, meta["no"], k) for k in range(1, meta["heats"] + 1)]
        for h in hs:                                         # 줄로 쓸 사람만 읽는다 (위 BOARD_TOP + 나)
            all_ids += _heat_order(event, meta["format"], h)[:BOARD_TOP] + [str(i) for i in h["ids"] if i == my_id]
        rows = _rows(all_ids)
        for h in hs:
            lines = []
            for place, k in enumerate(_heat_order(event, meta["format"], h), 1):
                r = rows.get(int(k))
                if r is None:
                    continue
                if place > BOARD_TOP and r["user_id"] != uid:
                    continue                                 # 조가 하나인 종목은 수백 줄 - 위 BOARD_TOP 줄 + 내 줄만
                res = (h.get("res") or {}).get(k) or {}
                lines.append({"place": place, "entryId": int(k), "user": r["username"], "mine": r["user_id"] == uid,
                              "pokemon": _mon_view(r), "text": _res_text(event, meta["format"], res),
                              "q": (h.get("q") or {}).get(k)})
            heats.append({"no": h["no"], "rows": lines, "match": h.get("match")})
        out["rounds"].append({"no": meta["no"], "key": meta["key"], "kr": meta["kr"], "format": meta["format"],
                              "note": meta["note"], "heats": heats})
    if now >= _end_t(day):
        out["hidden"] = False
        rows = db.q("SELECT e.*, u.username FROM olympic_entry e JOIN users u ON u.id=e.user_id"
                    " WHERE e.event=? AND e.day=? AND e.rank IS NOT NULL ORDER BY e.rank", (event, day))
        names = _names([r["user_id"] for r in rows[:BOARD_TOP]] + [uid])
        line = lambda r: {"rank": r["rank"], "user": names.get(r["user_id"]) or r["username"],            # noqa: E731
                          "mine": r["user_id"] == uid, "entryId": r["id"], "pokemon": _mon_view(r),
                          "text": final_text(event, r["record"]), "reached": _round_kr(info, r["reached"])}
        out["standings"] = [line(r) for r in rows[:BOARD_TOP]]
        me = next((r for r in rows if r["user_id"] == uid), None)
        out["me"] = line(me) if me is not None else None
    return out


def _mine_id(event, uid):
    r = _mine(event, uid)
    return r["id"] if r is not None else None


def _round_kr(info, no):
    if not no or not info or no > len(info["rounds"]):
        return ""
    return info["rounds"][no - 1]["kr"]


# ---------------------------------------------------------------- 정산 (그 종목 중계가 끝난 뒤)
def _prize(rank, ev):
    """(칭호 id, 리본 종류, 볼)."""
    if rank <= 3:
        return "oly_%s" % ev, ("oly_gold", "oly_silver", "oly_bronze")[rank - 1], BALLS[rank]
    return "oly_final", "oly_final", FINAL_BALLS


def _medal_gift(ev, rank, at):
    """1~3위 메달 꾸미기 선물 (kind, item_id, count, title, message, created_at) - 받으면 deco.grant 가 꾸미기 주머니에."""
    medal = dict((r, kr) for r, _k, kr in O.MEDALS)[rank]
    kr = O.EV[ev]["kr"]
    msg = ("포스크탑 올림픽 %s %s 축하해요! 꾸미기 '%s'을 드려요. 가방의 '꾸미기' 주머니에 들어가고, 바탕화면 "
           "포켓몬 우클릭 '꾸미기...' 에서 목에 걸어 줄 수 있어요. 칭호 '%s'도 함께 받았어요."
           % (kr, medal, medal, O.TITLE[ev]))
    return ("deco", O.MEDAL_DECO[rank], 1, "올림픽 %s %s" % (kr, medal), msg, at)


def _final_and_balls(ev, top, at):
    """최종 순위 줄과 볼 · 메달 선물을 **한 트랜잭션으로** 넣는다 (줄을 먼저 커밋하고 볼을 나중에 주면 실패 뒤 다시
    돌려도 볼을 영영 못 받는다). 칭호 · 리본은 '이미 있으면 그만' 이라 따로."""
    sql_f = ("INSERT INTO olympic_final (event, user_id, rank, entry_id, pokemon_id, record, at)"
             " VALUES (?,?,?,?,?,?,?) ON CONFLICT(event, user_id) DO NOTHING")
    sql_b = "UPDATE users SET balls=balls+? WHERE id=?"
    sql_g = "INSERT INTO gift (user_id, kind, item_id, count, title, message, created_at) VALUES (?,?,?,?,?,?,?)"
    if db.using_turso():
        for r in top:
            cur = db.run(sql_f, (ev, r["user_id"], r["rank"], r["id"], r["pokemon_id"], r["record"], at))
            if getattr(cur, "rowcount", 1):
                db.run(sql_b, (_prize(r["rank"], ev)[2], r["user_id"]))
                if r["rank"] <= 3:
                    db.run(sql_g, (r["user_id"], ) + _medal_gift(ev, r["rank"], at))
        return
    conn = db.connect()
    try:
        if conn.in_transaction:
            conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        for r in top:
            cur = conn.execute(sql_f, (ev, r["user_id"], r["rank"], r["id"], r["pokemon_id"], r["record"], at))
            if cur.rowcount:
                conn.execute(sql_b, (_prize(r["rank"], ev)[2], r["user_id"]))
                if r["rank"] <= 3:
                    conn.execute(sql_g, (r["user_id"], ) + _medal_gift(ev, r["rank"], at))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:                                   # noqa: BLE001
            pass
        raise


def settle(event, day, now=None):
    """그 종목 정산. 두 번 돌려도 한 번이다 (볼은 olympic_final 줄과 한 트랜잭션 · 칭호 · 리본은 '이미 있으면 그만')."""
    now = _now(now)
    key = "olympics:settled:%s" % event
    if event in _settled:
        return False
    with _lock:
        if db.q1("SELECT 1 FROM meta WHERE k=?", (key,)) is not None:
            _settled.add(event)
            return False
        at = _iso(now)
        rows = db.q("SELECT * FROM olympic_entry WHERE event=? AND day=? AND rank IS NOT NULL ORDER BY rank",
                    (event, day))
        top = [r for r in rows if r["rank"] <= O.FINAL_TO]
        _final_and_balls(event, top, at)
        for r in top:
            tid, kind, _balls = _prize(r["rank"], event)
            season.grant(r["user_id"], "title", tid, 0, equip_if_empty=False, now=at)
            _ribbon(r["pokemon_id"], r["user_id"], kind, event, at)
        people, best = {}, {}
        for r in rows:                                       # 순위 차례라 처음 본 줄이 그 종 1위
            people.setdefault(r["species"], set()).add(r["user_id"])
            best.setdefault(r["species"], r)
        for spk, r in best.items():
            if len(people[spk]) >= O.SPECIES_MIN:
                _ribbon(r["pokemon_id"], r["user_id"], "oly_species", event, at)
        db.run("INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT(k) DO NOTHING", (key, at))
        _settled.add(event)
    print("[olympics] %s 정산 끝" % event)
    return True


def _ribbon(pid, uid, kind, event, at):
    db.run("INSERT OR IGNORE INTO pokemon_ribbon (pokemon_id, user_id, kind, event, at)"
           " SELECT ?, ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM pokemon WHERE id=? AND user_id=?)",
           (pid, uid, kind, event, at, pid, uid))


def medals(now=None):
    """정산한 종목마다 1~3위."""
    out = {}
    for e in O.EVENTS:
        rows = db.q("SELECT f.rank, f.user_id, f.record, e.*, u.username FROM olympic_final f"
                    " JOIN olympic_entry e ON e.id=f.entry_id JOIN users u ON u.id=f.user_id"
                    " WHERE f.event=? AND f.rank<=3 ORDER BY f.rank", (e["key"],))
        if rows:
            out[e["key"]] = [{"rank": r["rank"], "user": r["username"], "pokemon": _mon_view(r),
                              "text": final_text(e["key"], r["record"])} for r in rows]
    return out


def my_medals(uid):
    rows = db.q("SELECT f.*, e.name, e.num, e.look, e.shiny, e.tint, e.species, e.pokemon_id"
                " FROM olympic_final f JOIN olympic_entry e ON e.id=f.entry_id WHERE f.user_id=? ORDER BY f.rank",
                (uid,))
    return [{"event": r["event"], "kr": O.EV[r["event"]]["kr"], "rank": r["rank"],
             "text": final_text(r["event"], r["record"]), "pokemon": _mon_view(r)} for r in rows]


def title_rows(now=None):
    """도감 탭 '칭호' 목록에 올릴 올림픽 칭호와 얻는 법. (id, 묶음, 조건, 지금 얻을 수 있나)"""
    is_open = not O.finished(_now(now), _ends())
    group = "포스크탑 올림픽" if is_open else "지난 이벤트 (다시 얻을 수 없음)"
    out = [("oly_%s" % e["key"], group, "올림픽 %s 1~3위 (메달)" % e["kr"], is_open) for e in O.EVENTS]
    out += [("oly_final", group, "올림픽 한 종목에서 4~8위", is_open)]
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


def _ach(uid):
    from . import achievements                 # 업적이 이 모듈의 stats 를 읽는다 - 서로 부르므로 여기서
    achievements.safe_check(uid)


# ---------------------------------------------------------------- 상태 (이벤트 탭)
def _status(event, now):
    day = O.day_of(event)
    if O.entry_open(event, now):
        return "entry"
    if now < O.open_at():
        return "before"
    if ran(day):
        return "live" if now < _end_t(day) else "done"
    return "live" if now >= O.start_at(day) else "before"


def state(uid, now=None):
    now = _now(now)
    if O.DAYS:
        ensure_ran(now)
    ends = _ends() if O.DAYS else {}
    ph = O.phase(now, ends)
    nday = O.next_day(now, ends) if O.DAYS else None
    mine = dict((r["event"], r) for r in db.q("SELECT * FROM olympic_entry WHERE user_id=?", (uid,)))
    events = []
    for e in O.EVENTS:
        ev = e["key"]
        day = O.day_of(ev)
        st = _status(ev, now) if day else "before"
        r = mine.get(ev)
        info = day_info(day) if day and ran(day) else None
        result = None
        if r is not None and info is not None and now >= _end_t(day) and r["rank"]:
            result = {"rank": r["rank"], "total": info["n"], "text": final_text(ev, r["record"]),
                      "reached": _round_kr(info, r["reached"]), "medal": r["rank"] <= 3,
                      "watch": {"round": r["reached"], "heat": _my_heat(ev, r["id"], r["reached"])}
                      if r["reached"] else None}
        events.append({
            "key": ev, "kr": e["kr"], "short": e["short"], "day": day, "status": st, "canEnter": st == "entry",
            "statKr": e["statKr"], "kg0": e["kg0"], "types": [_type_kr(t) for t in e["types"]],
            "abil": [_ability_kr(a) for a in e["abil"]], "cheer": _cheer(day),
            "startsIn": _secs(O.start_at(day), now) if day else None,
            "entry": _entry_view(r) if r is not None else None, "ran": info is not None,
            "entrants": info["n"] if info else None, "result": result})
    out = {"phase": ph, "days": list(O.DAYS), "at": O.AT, "nextDay": nday,
           "today": O.event_of(nday) if nday else None, "dayNo": O.day_no(nday) if nday else len(O.DAYS),
           "startsIn": _secs(O.start_at(nday), now) if nday else None,
           "openIn": _secs(O.open_at(), now) if ph == "before" and O.DAYS else None,
           "events": events,
           "tactics": [{"key": k, "kr": O.TACTICS[k]["kr"]} for k in ("safe", "bold")],
           "medals": medals(now), "myMedals": my_medals(uid)}
    _ach(uid)
    return out


def me_card(uid, now=None):
    """/api/me 에 싣는 짧은 것. 기간 밖이면 None (질의도 없다). 앱이 2시 중계를 예약하는 데 쓴다.
    경기 날을 비워 두면(POKET_OLYMPICS_DAYS='') 늘 None - 여기서 터지면 모든 사람의 동기화가 멈춘다."""
    if not O.DAYS:
        return None
    now = _now(now)
    if now < O.open_at() and (O.open_at() - now).total_seconds() > 3 * 86400:
        return None
    safe_ensure(now)
    ends = _ends()
    ph = O.phase(now, ends)
    if ph in ("before", "closed"):
        return {"phase": ph, "openIn": _secs(O.open_at(), now) if ph == "before" else None}
    nday = O.next_day(now, ends)
    out = {"phase": ph, "nextDay": nday, "event": O.event_of(nday) if nday else None,
           "dayNo": O.day_no(nday) if nday else None,
           "startsIn": _secs(O.start_at(nday), now) if nday else None,
           "endIn": _secs(O.end_at(nday, ends.get(nday)), now) if nday else None,
           "entries": db.q1("SELECT COUNT(*) c FROM olympic_entry WHERE user_id=? AND seed IS NULL", (uid,))["c"],
           "entered": bool(nday) and db.q1("SELECT 1 FROM olympic_entry WHERE user_id=? AND day=?", (uid, nday))
           is not None}
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


@router.get("/api/olympics/show")
def get_show(round: int, ctx=Depends(deps.current)):          # noqa: A002 - 쿼리 이름
    return show(ctx["user"]["id"], round)


@router.get("/api/olympics/heat")
def get_heat(event: str, round: int, heat: int, ctx=Depends(deps.current)):     # noqa: A002
    return globals()["heat"](ctx["user"]["id"], event, round, heat)


@router.get("/api/olympics/board")
def get_board(event: str, ctx=Depends(deps.current)):
    return board(ctx["user"]["id"], event)
