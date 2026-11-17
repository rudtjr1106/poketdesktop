# -*- coding: utf-8 -*-
"""밖에 보여 주는 숫자 셋 (app/stats.py, GET /api/stats). 서버를 띄우지 않는다.

    python server/test_stats.py

포트폴리오 사이트가 인증 없이 읽는 자리다. 그래서 본다:

  1. 가입자 수 · 지금 접속 중 (같은 사람의 세션 둘은 한 명, 3분 넘게 조용한 사람은 뺀다).
  2. 최대 동시 접속은 넘을 때만 적히고 **내려가지 않는다.** 서버를 다시 켜도, 손으로 넣어 둔 값도 그대로다.
  3. 나가는 것은 숫자 셋뿐이다 (닉네임 · 버전 · IP 같은 것이 없다).
  4. 물을 때마다 DB 를 읽지 않는다 (인증 없는 자리라 두드리는 만큼 읽으면 안 된다).
  5. 세다가 터져도 500 이 아니다 - 마지막으로 센 것을 주고, 한 번도 못 셌으면 503.
"""
import datetime
import json
import os
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-stats-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_STATS_SAMPLE"] = "0"

from fastapi import HTTPException                           # noqa: E402

from app import db, social, stats                           # noqa: E402

OK = FAIL = 0
NOW = datetime.datetime(2026, 11, 17, 12, 0, tzinfo=datetime.timezone.utc)
_tok = [0]


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mkuser(name):
    return db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, created_at) VALUES (?,?,?,1,'')",
                  (name, b"x", b"x")).lastrowid


def session(uid, secs_ago):
    """secs_ago 초 전에 마지막으로 말을 건 세션 하나. 시각 꼴은 auth.now_iso 와 같다 (초까지)."""
    _tok[0] += 1
    seen = (NOW - datetime.timedelta(seconds=secs_ago)).replace(microsecond=0).isoformat()
    db.run("INSERT INTO sessions (token_hash, user_id, ip, created_at, last_seen, expires_at)"
           " VALUES (?,?,'',?,?,?)", ("tok%d" % _tok[0], uid, seen, seen, "2999-01-01T00:00:00+00:00"))


def quiet():
    """모두를 조용하게 (한 시간 전으로)."""
    old = (NOW - datetime.timedelta(hours=1)).replace(microsecond=0).isoformat()
    db.run("UPDATE sessions SET last_seen=?", (old,))


def peak_row():
    r = db.q1("SELECT v FROM meta WHERE k=?", (stats.PEAK_KEY,))
    return None if r is None else r["v"]


def main_():
    db.init()
    stats._now = lambda: NOW                        # 경로가 스스로 셀 때도 같은 시각으로 (세션을 NOW 기준으로 넣었다)

    print("\n=== 1. 가입자 수 · 지금 접속 중 ===")
    s = stats.sample(now=NOW)
    chk("빈 서버는 전부 0", s == {"users": 0, "online": 0, "peakOnline": 0}, s)
    a, b, c, d = (mkuser(n) for n in ("가", "나", "다", "라"))
    session(a, 10)
    session(a, 40)                                  # 같은 사람이 PC 두 대
    session(b, social.ONLINE_WINDOW - 5)            # 창 안쪽 끝
    session(c, social.ONLINE_WINDOW + 60)           # 3분 넘게 조용하다
    s = stats.sample(now=NOW)                       # d 는 세션이 없다
    chk("가입자 수", s["users"] == 4, s)
    chk("접속 중: 세션 둘인 사람은 한 명, 조용한 사람 · 세션 없는 사람은 뺀다", s["online"] == 2, s)
    real_now = social._now
    social._now = lambda: NOW
    try:
        lit = [u for u in (a, b, c, d) if social.is_online(u)]
    finally:
        social._now = real_now
    chk("친구 목록의 접속 표시와 같은 사람들을 센다", lit == [a, b] and s["online"] == len(lit), lit)

    print("\n=== 2. 최대 동시 접속 ===")
    chk("처음 센 값이 기록이 된다", s["peakOnline"] == 2 and peak_row() == "2", (s, peak_row()))
    quiet()
    s = stats.sample(now=NOW)
    chk("사람이 빠져도 기록은 그대로", s["online"] == 0 and s["peakOnline"] == 2 and peak_row() == "2", (s, peak_row()))
    for u in (a, b, c):
        session(u, 5)
    s = stats.sample(now=NOW)
    chk("넘으면 새 기록", s["online"] == 3 and s["peakOnline"] == 3 and peak_row() == "3", (s, peak_row()))
    at = db.q1("SELECT v FROM meta WHERE k=?", (stats.PEAK_AT_KEY,))
    chk("언제 세운 기록인지도 남는다", at is not None and at["v"].startswith("2026-11-17T12:00"), at and at["v"])
    quiet()
    stats.forget()                                  # 서버를 다시 켠 것과 같다 (메모리가 빈다)
    s = stats.sample(now=NOW)
    chk("서버를 다시 켜도 기록은 그대로", s["peakOnline"] == 3, s)
    db.run("UPDATE meta SET v='300' WHERE k=?", (stats.PEAK_KEY,))      # 운영자가 예전 기록을 손으로 넣었다
    session(a, 5)
    s = stats.sample(now=NOW)
    chk("손으로 넣은 더 큰 값을 덮지 않는다", s["peakOnline"] == 300 and peak_row() == "300", (s, peak_row()))
    db.run("UPDATE meta SET v='이상한 값' WHERE k=?", (stats.PEAK_KEY,))
    s = stats.sample(now=NOW)
    chk("칸이 망가져 있어도 센다", s["online"] == 1 and s["peakOnline"] == 1 and peak_row() == "1", (s, peak_row()))

    def locked(n, now):
        raise RuntimeError("database is locked")
    real_raise = stats._raise_peak
    stats._raise_peak = locked
    try:
        for u in (b, c):
            session(u, 5)
        s = stats.sample(now=NOW)
        chk("기록을 적다가 터져도 센 것은 나온다", s["online"] == 3 and s["peakOnline"] == 3 and peak_row() == "1",
            (s, peak_row()))
    finally:
        stats._raise_peak = real_raise
    s = stats.sample(now=NOW)
    chk("다음 차례에 적힌다", s["peakOnline"] == 3 and peak_row() == "3", (s, peak_row()))
    quiet()
    session(a, 5)
    db.run("UPDATE meta SET v='1' WHERE k=?", (stats.PEAK_KEY,))

    print("\n=== 3. 나가는 것은 숫자 셋뿐 ===")
    stats.forget()
    res = stats.public_stats()
    body = json.loads(res.body)
    chk("칸 셋", sorted(body) == ["online", "peakOnline", "users"], body)
    chk("전부 0 이상의 정수", all(type(v) is int and v >= 0 for v in body.values()), body)
    chk("가입자 넷 · 접속 하나 · 기록 하나", body == {"users": 4, "online": 1, "peakOnline": 1}, body)
    chk("남이 잠깐 담아 둬도 된다고 알린다 (Cache-Control)", "max-age=" in res.headers.get("cache-control", ""),
        dict(res.headers))

    print("\n=== 4. 물을 때마다 읽지 않는다 ===")
    mkuser("마")
    chk("방금 센 것이 있으면 그것을 준다", stats.snapshot()["users"] == 4, stats.snapshot())
    chk("다시 세면 보인다", stats.sample(now=NOW)["users"] == 5)
    calls = []
    real = stats._count
    stats._count = lambda now=None: calls.append(1) or real(now)
    try:
        for _ in range(50):
            stats.public_stats()
        chk("50번 물어도 한 번도 다시 세지 않는다", calls == [], len(calls))
        stats._snap_at -= stats.STALE_SEC + 1      # 센 지 오래됐다 (배경 스레드가 멈춘 셈)
        for _ in range(50):
            stats.public_stats()
        chk("오래됐으면 그때 한 번만 센다", len(calls) == 1, len(calls))
    finally:
        stats._count = real

    print("\n=== 5. 세다가 터져도 ===")
    def boom(now=None):
        raise RuntimeError("database is locked")
    stats._count = boom
    try:
        stats._snap_at -= stats.STALE_SEC + 1
        got = stats.snapshot()
        chk("마지막으로 센 것을 준다", got is not None and got["users"] == 5, got)
        stats.forget()
        chk("한 번도 못 셌으면 없다고 한다", stats.snapshot() is None)
        try:
            stats.public_stats()
            chk("그때는 503", False, "예외가 안 났다")
        except HTTPException as e:
            chk("그때는 503", e.status_code == 503, e.status_code)
    finally:
        stats._count = real

    print("\n=== 배경 스레드 ===")
    stats.start()
    chk("POKET_STATS_SAMPLE=0 이면 스레드를 안 띄운다",
        not any(t.name == "stats" for t in threading.enumerate()))

    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
