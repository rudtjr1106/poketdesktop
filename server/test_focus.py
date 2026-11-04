# -*- coding: utf-8 -*-
"""포켓몬과 집중하기 (집중 타이머). 서버를 띄우지 않는다.

    python server/test_focus.py

규칙은 common/focus.py, 서버는 server/app/focus.py. 설계: design-notes/2026-11-04-focus-timer.md

## 무엇을 못 박나

  1. 규칙: 능력 여섯과 동작, KST 날짜, 연속 일수, 달력 칸. 표가 있다.
"""
import datetime
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-focus-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ.pop("POKET_FOCUS_SET_SEC", None)

import json                                                  # noqa: E402

from fastapi import HTTPException                            # noqa: E402

from common import focus as F                                # noqa: E402
from common import pokelogic as P                            # noqa: E402
from app import db, deps, mypage                             # noqa: E402
from app import focus as F_                                  # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
T0 = datetime.datetime(2026, 11, 4, 3, 0, 0, tzinfo=UTC)     # KST 12:00
CREDITS = []                                                  # 맥박 · 끝내기가 돌려준 세트 (차례대로)


def later(**kw):
    return T0 + datetime.timedelta(**kw)


def kst(y, mo, d, h, mi):
    return datetime.datetime(y, mo, d, h, mi, tzinfo=F.KST).astimezone(UTC)


_n = [0]


def mkuser(name=None):
    _n[0] += 1
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'2026-10-01T00:00:00+00:00','','')",
        (name or "사람%d" % _n[0], b"x", b"x"))
    return cur.lastrowid


def mkmon(uid, species="PIKACHU", desk=True):
    m = P.make_pokemon(deps.dex().get(species), 30, random.Random(3), shiny_rate=10 ** 9)
    m["noEvolve"] = True
    m["evs"] = dict((s, 0) for s in P.STATS)
    pid = db.insert_mon(uid, m, "")
    if desk:
        db.run("UPDATE pokemon SET on_desktop=1, slot=0 WHERE id=?", (pid,))
    return pid


def evs(pid):
    return json.loads(db.q1("SELECT evs FROM pokemon WHERE id=?", (pid,))["evs"])


def set_evs(pid, d):
    e = dict((s, 0) for s in P.STATS)
    e.update(d)
    db.run("UPDATE pokemon SET evs=? WHERE id=?", (json.dumps(e), pid))


def refused(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except HTTPException as e:
        return e.status_code, str(e.detail)
    return None


def beat(uid, t):
    r = F_.beat(uid, t)
    CREDITS.extend(r["sets"])
    return r


def pulse(uid, a, b, base=None):
    """a 분부터 b 분까지 1분마다 맥박 (base 부터 센다, 기본 T0)."""
    base = base or T0
    out = []
    for k in range(a, b + 1):
        out.extend(beat(uid, base + datetime.timedelta(minutes=k))["sets"])
    return out


def run_sets(uid, pid, stat, n, base=None):
    """base 에 시작해 n 세트를 채우고 딱 그때 끝낸다 (자투리 없음). 돌려준 세트들."""
    base = base or T0
    F_.start(uid, pid, stat, base)
    got = pulse(uid, 1, n * 25 - 1, base)
    st = F_.stop(uid, base + datetime.timedelta(minutes=n * 25))
    CREDITS.extend(st["sets"])
    return got + st["sets"]


def run_state(uid):
    r = db.q1("SELECT state FROM focus_run WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,))
    return r["state"] if r else None


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def rules_part():
    print("=== 규칙 ===")
    chk("능력 여섯과 동작", [a[0] for a in F.ACTS] == ["atk", "spa", "spe", "hp", "def", "spd"]
        and F.act_of("spa") == ("공부", "특공"), F.ACTS)
    chk("없는 능력", F.act_of("xyz") is None)
    chk("숫자: 25분 · +5 · 하루 40 · 맥박 60초 · 끊김 180초 · 자투리 60초",
        (F.SET_SEC, F.EV_PER_SET, F.DAILY_EV, F.BEAT_SEC, F.GAP_SEC, F.PART_MIN_SEC)
        == (1500, 5, 40, 60, 180, 60))
    chk("KST 날짜: UTC 15:00 은 다음 날",
        F.kst_day(datetime.datetime(2026, 11, 4, 15, 0, tzinfo=UTC)) == "2026-11-05")
    chk("KST 날짜: tz 없는 시각은 UTC 로 본다",
        F.kst_day(datetime.datetime(2026, 11, 4, 14, 59)) == "2026-11-04")
    chk("KST 시: UTC 18:30 은 3시", F.kst_hour(datetime.datetime(2026, 11, 4, 18, 30, tzinfo=UTC)) == 3)
    chk("연속: 오늘까지", F.streaks({"2026-11-02", "2026-11-03", "2026-11-04"}, "2026-11-04") == (3, 3))
    chk("연속: 오늘 아직 안 했으면 어제까지",
        F.streaks(["2026-11-03", "2026-11-02", "2026-11-03"], "2026-11-04") == (2, 2))
    chk("연속: 끊겼으면 0, 최고는 남는다",
        F.streaks({"2026-10-01", "2026-10-02", "2026-10-03", "2026-11-01"}, "2026-11-04") == (0, 3))
    chk("연속: 달을 넘어도 이어진다",
        F.streaks({"2026-10-31", "2026-11-01"}, "2026-11-01") == (2, 2))
    chk("연속: 없으면 0", F.streaks([], "2026-11-04") == (0, 0))
    chk("달력 칸: 2026-11 은 일요일 시작 30일", F.month_grid("2026-11") == (0, 30))
    chk("달력 칸: 2026-10 은 목요일 시작 31일", F.month_grid("2026-10") == (4, 31))
    chk("달력 칸: 2028-02 는 29일", F.month_grid("2028-02")[1] == 29)
    chk("표가 있다", db.q1("SELECT name FROM sqlite_master WHERE name='focus_run'") is not None
        and db.q1("SELECT name FROM sqlite_master WHERE name='focus_set'") is not None)
    chk("진행 중은 한 사람에 하나 (부분 유일 색인)",
        db.q1("SELECT name FROM sqlite_master WHERE name='idx_focus_run_on'") is not None)
    # 독립 검토: 맥박 · /api/me 마다 도는 질의가 표 전체를 훑지 않는다
    for name, sql in (("이번 집중 세트 수", F_.SETS_IN_RUN_SQL), ("마지막 집중", F_.LAST_RUN_SQL)):
        plan = " ".join(str(tuple(r)) for r in db.q("EXPLAIN QUERY PLAN " + sql, (1, 1) if sql.count("?") == 2 else (1,)))
        chk("%s 질의는 색인을 탄다" % name, "USING" in plan and "SCAN focus" not in plan, plan)


def focus_part():
    print("\n=== 집중: 시작 · 세트 · 끊김 · 끝내기 ===")
    uid = mkuser()
    pika = mkmon(uid)
    s = F_.start(uid, pika, "atk", T0)
    chk("시작: 헬스, 이번 세트 25분 남음", s["running"]["act"] == "헬스" and s["running"]["setLeft"] == 1500
        and not s["existing"], s)
    chk("시작하면 집중 중", F_.focusing(uid, later(minutes=1)))
    s2 = F_.start(uid, pika, "spa", later(minutes=1))
    chk("두 번 시작하면 같은 것을 돌려준다", s2["existing"] and s2["running"]["stat"] == "atk", s2)
    chk("진행 중은 한 줄", db.q1("SELECT COUNT(*) c FROM focus_run WHERE user_id=?", (uid,))["c"] == 1)

    other = mkuser()
    boxed = mkmon(other, desk=False)
    chk("데리고 다니지 않는 포켓몬은 거절", (refused(F_.start, other, boxed, "atk", T0) or [0])[0] == 409)
    chk("남의 포켓몬은 거절", (refused(F_.start, other, pika, "atk", T0) or [0])[0] == 404)
    chk("없는 능력은 거절", (refused(F_.start, uid, pika, "luck", T0) or [0])[0] == 400)

    got = pulse(uid, 1, 24)
    chk("25분 전에는 세트가 없다", got == [] and evs(pika)["atk"] == 0)
    b = beat(uid, later(minutes=25))
    chk("25분: 세트 인정 +5", [c["ev"] for c in b["sets"]] == [5] and evs(pika)["atk"] == 5, b)
    chk("세트 답: 동작 · 오늘 몫", b["sets"][0]["act"] == "헬스" and b["sets"][0]["todayEv"] == 5
        and b["sets"][0]["dailyEv"] == 40 and b["sets"][0]["capped"] is None, b["sets"])
    chk("다음 세트가 바로 이어진다 (남은 25분)", b["running"]["setLeft"] == 1500 and b["running"]["sets"] == 1,
        b["running"])
    got = pulse(uid, 26, 50)
    chk("묻지 않고 이어진다: 50분에 둘째 세트", len(got) == 1 and evs(pika)["atk"] == 10, got)
    chk("같은 세트 두 번 인정 안 함", beat(uid, later(minutes=50, seconds=5))["sets"] == [])
    pulse(uid, 51, 60)
    b = beat(uid, later(minutes=70))
    chk("3분 넘게 끊기면 lost, 진행 중 세트 인정 안 함",
        b["ended"] == "lost" and b["sets"] == [] and evs(pika)["atk"] == 10 and b["running"] is None, b)
    chk("lost 문구", "꺼져 있었거나" in (b["message"] or ""), b["message"])
    chk("lost 뒤엔 집중 중 아님", not F_.focusing(uid, later(minutes=70)) and run_state(uid) == "lost")
    chk("lost 뒤 맥박: 다시 lost 라고만", beat(uid, later(minutes=71))["ended"] == "lost")

    u6, m6 = mkuser(), None
    m6 = mkmon(u6)
    F_.start(u6, m6, "atk", T0)
    pulse(u6, 1, 49)
    b = beat(u6, later(minutes=55))
    chk("마지막 맥박(49분)이 세트 끝(50분) 전이면 그 세트는 인정 안 함",
        b["ended"] == "lost" and evs(m6)["atk"] == 5, (b, evs(m6)))
    u9 = mkuser()
    m9 = mkmon(u9)
    F_.start(u9, m9, "atk", T0)
    pulse(u9, 1, 26)
    b = beat(u9, later(minutes=40))
    chk("세트 끝 뒤 맥박(26분)이 있었으면 끊겨도 그 세트는 인정",
        b["ended"] == "lost" and evs(m9)["atk"] == 5, (b, evs(m9)))

    F_.start(uid, pika, "spa", later(minutes=100))
    pulse(uid, 101, 112, T0)
    st = F_.stop(uid, later(minutes=112))
    chk("끝내기: 자투리 12분은 달력에만, 노력치 0",
        st["part"] == 12 and st["ended"] == "done" and evs(pika)["spa"] == 0, st)
    chk("끝내면 집중 중 아님", not F_.focusing(uid, later(minutes=113)) and run_state(uid) == "done")
    chk("진행 중이 없을 때 끝내기", F_.stop(uid, later(minutes=114))["ended"] is None)
    chk("끝낸 뒤 맥박: done", beat(uid, later(minutes=115))["ended"] == "done")
    chk("달력: 오늘 = 25 + 25 + 12", F_.month(uid, "2026-11")["days"].get("2026-11-04") == 62,
        F_.month(uid, "2026-11"))
    rows = F_.day(uid, "2026-11-04")["rows"]
    chk("그날 기록: 세트 둘과 자투리 (KST 시각)",
        [(r["time"], r["act"], r["minutes"], r["ev"], r["full"]) for r in rows]
        == [("12:25", "헬스", 25, 5, True), ("12:50", "헬스", 25, 5, True), ("13:52", "공부", 12, 0, False)],
        rows)
    st = F_.start(uid, pika, "spe", later(minutes=200))
    st = F_.stop(uid, later(minutes=200, seconds=40))
    chk("1분 안 된 자투리는 안 남긴다", st["part"] == 0 and F_.month(uid, "2026-11")["days"]["2026-11-04"] == 62)

    print("\n=== 하루 상한 · 노력치 상한 · 놓아준 포켓몬 ===")
    u3 = mkuser()
    m3 = mkmon(u3)
    got = run_sets(u3, m3, "spe", 9)
    chk("아홉 세트가 다 인정된다", len(got) == 9, len(got))
    chk("하루 40 까지만", sum(r["ev"] for r in F_.day(u3, "2026-11-04")["rows"]) == 40 and evs(m3)["spe"] == 40,
        evs(m3))
    chk("아홉째 세트는 기록만, capped=day", got[-1]["ev"] == 0 and got[-1]["capped"] == "day", got[-1])
    chk("여덟째에 오늘 몫이 꽉 찬다", got[7]["todayEv"] == 40 and got[7]["capped"] is None, got[7])

    u4 = mkuser()
    m4 = mkmon(u4)
    start = kst(2026, 11, 4, 23, 50)
    F_.start(u4, m4, "atk", start)
    pulse(u4, 1, 24, start)
    b = beat(u4, start + datetime.timedelta(minutes=25))
    chk("자정 넘은 세트는 새 날로 (오늘 몫 5)", b["sets"] and b["sets"][0]["todayEv"] == 5
        and "2026-11-05" in F_.month(u4, "2026-11")["days"], b)

    u7 = mkuser()
    m7 = mkmon(u7)
    set_evs(m7, {"atk": 250})
    got = run_sets(u7, m7, "atk", 1)
    chk("한 능력 252 에서 멈춤 (capped=full)", got[-1]["ev"] == 2 and got[-1]["capped"] == "full"
        and evs(m7)["atk"] == 252, got)
    chk("하루 몫도 실제로 들어간 값으로 센다", F_.state(u7, later(minutes=30))["todayEv"] == 2)
    u10 = mkuser()
    m10 = mkmon(u10)
    set_evs(m10, {"atk": 252, "def": 252, "spa": 4})
    got = run_sets(u10, m10, "spe", 1)
    chk("합계 510 에서 멈춤", got[-1]["ev"] == 2 and got[-1]["capped"] == "full", got)

    u8 = mkuser()
    m8 = mkmon(u8)
    F_.start(u8, m8, "atk", T0)
    db.run("DELETE FROM pokemon WHERE id=?", (m8,))
    pulse(u8, 1, 24)
    b = beat(u8, later(minutes=25))
    chk("놓아준 포켓몬: 노력치 없이 기록만 (gone)", b["sets"] and b["sets"][0]["capped"] == "gone"
        and F_.day(u8, "2026-11-04")["rows"][0]["minutes"] == 25, b)

    print("\n=== 동기화 · 마이페이지 · 달력 ===")
    u5 = mkuser()
    m5 = mkmon(u5)
    chk("집중 안 할 때 me_card", F_.me_card(u5, T0) == {"running": None})
    F_.start(u5, m5, "def", T0)
    mc = F_.me_card(u5, later(minutes=2))
    chk("me_card: 진행 중, 남은 초", mc["running"]["setLeft"] == 1380 and not mc["running"]["stale"], mc)
    mc = F_.me_card(u5, later(minutes=10))
    chk("me_card 는 쓰지 않는다: 끊긴 것은 stale 로만", mc["running"]["stale"] and run_state(u5) == "on", mc)
    chk("끊긴 집중은 '집중 중' 이 아니다", not F_.focusing(u5, later(minutes=10))
        and F_.focusing_many([u5, uid], later(minutes=10)) == set())
    F_.start(u5, m5, "spd", later(minutes=11))
    chk("끊긴 것이 남아 있어도 새로 시작하면 옛것을 닫는다",
        db.q1("SELECT COUNT(*) c FROM focus_run WHERE user_id=? AND state='on'", (u5,))["c"] == 1
        and F_.me_card(u5, later(minutes=12))["running"]["stat"] == "spd")
    chk("focusing_many", F_.focusing_many([u5, uid], later(minutes=12)) == {u5})

    me = dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))
    d = mypage.build(me, deps.dex(), later(minutes=300))
    fo = d.get("focus") or {}
    chk("마이페이지 build 엔 집중 기록", fo.get("month", {}).get("ym") == "2026-11"
        and fo["month"]["days"].get("2026-11-04") == 62, fo)
    sm = fo.get("summary") or {}
    chk("요약: 전체 · 이번 달 · 연속 · 오늘 몫", sm.get("totalMin") == 62 and sm.get("monthMin") == 62
        and sm.get("streak") == 1 and sm.get("best") == 1 and sm.get("todayEv") == 10
        and sm.get("dailyEv") == 40, sm)
    chk("남에게 보이는 card 엔 없다", "focus" not in mypage.card(uid, deps.dex(), later(minutes=300)))
    chk("모양이 틀린 달은 400", (refused(F_.month, uid, "2026-13") or [0])[0] == 400)
    chk("모양이 틀린 날은 400", (refused(F_.day, uid, "11/04") or [0])[0] == 400)
    chk("빈 달", F_.month(uid, "2026-09")["days"] == {})
    stt = F_.state(uid, later(minutes=300))
    chk("state: 규칙 숫자", stt["rules"] == {"setSec": 1500, "evPerSet": 5, "dailyEv": 40, "beatSec": 60,
                                         "gapSec": 180} and stt["running"] is None, stt)


def has_ach(uid, key):
    return db.q1("SELECT 1 FROM achievement WHERE user_id=? AND key=?", (uid, key)) is not None


def owns_title(uid, tid):
    return db.q1("SELECT 1 FROM user_reward WHERE user_id=? AND kind='title' AND rid=?", (uid, tid)) is not None


def balls(uid):
    return db.q1("SELECT balls FROM users WHERE id=?", (uid,))["balls"]


def ach_part():
    from app import achievements as A
    print("\n=== 업적 · 칭호 (갈래 '집중') ===")
    mine = [a for a in A.defs() if a["group"] == "집중"]
    chk("'집중' 갈래 19개 · 칭호 16개", len(mine) == 19 and sum(1 for a in mine if a["title"]) == 16,
        [a["key"] for a in mine])
    chk("숨은 것 셋", sorted(a["key"] for a in mine if a["hidden"])
        == ["hidden_allround", "hidden_buddy", "hidden_dawn"])

    u = mkuser()
    m = mkmon(u)
    b0 = balls(u)
    card = dict((c["key"], c) for c in A.public(u)["achievements"])
    chk("숨은 업적은 달성 전 ???", card["hidden_dawn"]["name"] == "???", card.get("hidden_dawn"))
    run_sets(u, m, "atk", 1)
    chk("첫 집중: 볼 5", has_ach(u, "focus_1") and balls(u) == b0 + 5, (balls(u), b0))
    chk("아직 10세트 아님", not has_ach(u, "focus_10"))
    base = kst(2026, 11, 6, 2, 40)
    run_sets(u, m, "spd", 1, base)
    chk("새벽 공부 (KST 3:05 에 세트)", has_ach(u, "hidden_dawn") and owns_title(u, "ach_hidden_dawn"))
    for i, stat in enumerate(("spa", "spe", "hp", "def")):
        run_sets(u, m, stat, 1, base + datetime.timedelta(hours=1 + i))
    chk("만능 트레이너 (여섯 동작)", has_ach(u, "hidden_allround"))
    chk("칭호 목록에 이름이 뜬다 (얻은 것)", any(c["name"] == "새벽 공부" and c["owned"]
                                         for c in A.titles(u)["titles"]))
    chk("칭호 목록: 아직 못 얻은 것은 조건과 진행", any(c["name"] == "공부벌레" and not c["owned"]
                                                and c.get("value") == 1 and c.get("target") == 25
                                                for c in A.titles(u)["titles"]))

    u2 = mkuser()
    m2 = mkmon(u2)
    for dd in range(7):
        run_sets(u2, m2, "atk", 1, T0 + datetime.timedelta(days=dd))
    chk("사흘 연속: 볼 5", has_ach(u2, "streak_3"))
    chk("일주일의 약속 (칭호)", has_ach(u2, "streak_7") and owns_title(u2, "ach_streak_7"))
    chk("한 달은 아직", not has_ach(u2, "streak_30"))

    u3 = mkuser()
    m3 = mkmon(u3)
    run_sets(u3, m3, "spe", 8)
    chk("오늘도 완주 (하루 40 다 받기)", has_ach(u3, "fullday_1") and owns_title(u3, "ach_fullday_1"))
    before = F_.stats(u3).get("focus_sets")
    F_.start(u3, m3, "spe", later(minutes=300))
    pulse(u3, 301, 312)
    F_.stop(u3, later(minutes=312))
    chk("자투리는 세지 않는다", F_.stats(u3).get("focus_sets") == before == 8, F_.stats(u3))
    chk("능력별로 센다", F_.stats(u3).get("focus_spe") == 8 and F_.stats(u3).get("focus_buddy") == 8)


def visit_part():
    """visit.start 는 시계를 안 받는다 - 이 묶음은 실제 시계로 시작한다 (now=None)."""
    from app import social, visit as V
    print("\n=== 집중 중 놀러 가기 막기 ===")
    V.reset()
    names = {}
    ids = {}
    for k in ("a", "b", "c", "d", "e"):
        names[k] = "방문%s%d" % (k, random.randint(1000, 9999))
        ids[k] = mkuser(names[k])
        mkmon(ids[k])
        V._add(V.Conn(None, ids[k]))           # 앱이 켜져 있다 (놀러 가기 소켓)

    def friends(x, y):
        social.request(ids[x], names[y])
        social.accept(ids[y], ids[x])
    for x, y in (("a", "b"), ("b", "c"), ("d", "e")):
        friends(x, y)
    a, b, c, d, e = (ids[k] for k in "abcde")
    ma = db.q1("SELECT id FROM pokemon WHERE user_id=?", (a,))["id"]
    mb = db.q1("SELECT id FROM pokemon WHERE user_id=?", (b,))["id"]
    md = db.q1("SELECT id FROM pokemon WHERE user_id=?", (d,))["id"]

    def row(me, other):
        return [f for f in social.listing(me)["friends"] if f["id"] == other][0]
    chk("집중 전: 놀러 갈 수 있다", row(b, a)["visitable"] and not row(b, a)["visitFocus"], row(b, a))
    F_.start(a, ma, "atk")
    chk("집중 중인 친구에게는 못 간다",
        (refused(V.start, b, a) or [0, ""])[1].startswith("친구가 지금 포켓몬과 집중"), refused(V.start, b, a))
    chk("집중 중에는 내가 못 간다", (refused(V.start, a, b) or [0])[0] == 409 and "집중하는 중" in refused(V.start, a, b)[1])
    r = row(b, a)
    chk("친구 목록: 집중 중 표시", r["visitFocus"] and not r["visitable"], r)
    V.start(c, b)                               # b 가 손님(c)을 맞는 중
    chk("연결돼 있으면 집중을 못 시작", (refused(F_.start, b, mb, "atk") or [0, ""])[1].startswith("친구와 연결돼 있는"))
    V.end(c)
    F_.start(d, md, "atk", datetime.datetime.now(UTC) - datetime.timedelta(minutes=10))   # 맥박이 10분째 없다
    chk("끊긴(stale) 집중은 방문을 막지 않는다", refused(V.start, e, d) is None)
    chk("끊긴 집중은 친구 목록에도 없다", not row(e, d)["visitFocus"])
    V.reset()


def main_():
    db.init()
    rules_part()
    focus_part()
    ach_part()
    visit_part()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
