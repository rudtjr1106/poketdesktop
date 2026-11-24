# -*- coding: utf-8 -*-
"""11/24 부하 줄이기 - 동작은 그대로 두고 되풀이만 줄인 것.

    cd server && POKET_DB=/tmp/x.db python test_cpu_1124.py

  1. 도감 해시(/api/pokedex/meta)는 한 번만 셈한다 - 값은 예전과 같다
  2. 관장 지난 판 접기(_expire_old)는 사용자마다 1분에 한 번 - 시계가 1분 넘게 가면(검사가 돌려도) 접는다 · 사용자끼리 따로
  3. 실시간 배틀 만료 접기(live.expire_old)는 5초에 한 번 - now 를 앞으로 주면 접는다 · 뒤로 가도 접는다
"""
import datetime
import hashlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("POKET_DB", os.path.join(tempfile.mkdtemp(prefix="poket-cpu-1124-"), "t.db"))
os.environ.setdefault("POKET_POKEDEX", os.path.join(HERE, "data", "pokedex.json"))

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def main():
    from common import pokelogic as P
    with open(os.environ["POKET_POKEDEX"], encoding="utf-8") as f:
        d = P.Pokedex(json.load(f))
    old = hashlib.sha256(json.dumps(d.raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                         .encode("utf-8")).hexdigest()[:16]
    calls = []
    real = json.dumps

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)
    P.json.dumps = counting
    try:
        first, second = d.digest(), d.digest()
    finally:
        P.json.dumps = real
    chk("1. 도감 해시는 예전과 같은 값", first == old == second, (first, old))
    chk("   두 번 물어도 한 번만 셈한다", len(calls) == 1, len(calls))

    from app import db, gym_routes as G, live as L
    db.init()
    runs = []
    real_run = db.run

    def spy(sql, args=()):
        if "UPDATE gym_battle SET state='done', result='expired'" in sql:
            runs.append(("gym", args[0]))
        if "UPDATE live_match SET state='done', result='expired'" in sql:
            runs.append(("live", sql.split("WHERE state='")[1][:7]))
        return real_run(sql, args)
    db.run = spy
    t0 = datetime.datetime(2026, 11, 24, 5, 0, tzinfo=datetime.timezone.utc)
    clock = {"t": t0}
    real_now = G._now
    G._now = lambda: clock["t"]
    G._expired_at.clear()
    try:
        G._expire_old(7)
        G._expire_old(7)
        clock["t"] = t0 + datetime.timedelta(seconds=30)
        G._expire_old(7)
        chk("2. 관장: 1분 안에는 한 번만 접는다", runs == [("gym", 7)], runs)
        G._expire_old(8)
        chk("   다른 사용자는 따로", runs[-1] == ("gym", 8) and len(runs) == 2, runs)
        clock["t"] = t0 + datetime.timedelta(seconds=61)
        G._expire_old(7)
        chk("   1분이 지나면 다시 접는다", runs[-1] == ("gym", 7) and len(runs) == 3, runs)
        clock["t"] = t0 - datetime.timedelta(hours=1)
        G._expire_old(7)
        chk("   시계가 뒤로 가도 접는다 (검사)", len(runs) == 4, runs)
        # 정말 접히나: 1시간 넘게 손 놓은 판
        uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login, last_ip)"
                     " VALUES ('cpu1124', ?, ?, 1, 30, 0, ?, ?, '')",
                     (b"x", b"x", t0.isoformat(), t0.isoformat())).lastrowid
        db.run("INSERT INTO gym_battle (user_id, region, trainer, state, result, turn, rev, data, created_at, updated_at)"
               " VALUES (?, 'r', 't', 'active', NULL, 1, 0, '{}', ?, ?)",
               (uid, (t0 - datetime.timedelta(hours=3)).isoformat(), (t0 - datetime.timedelta(hours=2)).isoformat()))
        clock["t"] = t0 + datetime.timedelta(hours=1)
        G._expire_old(uid)
        st = db.q1("SELECT state, result FROM gym_battle WHERE user_id=?", (uid,))
        chk("   손 놓은 지 오래된 판은 그대로 접힌다", st and st["state"] == "done" and st["result"] == "expired",
            st and dict(st))
    finally:
        G._now = real_now

    runs.clear()
    L._expired["at"] = None
    L.expire_old(t0)
    L.expire_old(t0 + datetime.timedelta(seconds=2))
    chk("3. 실시간: 5초 안에는 한 번만 (초대 · 판 두 줄)", [r[0] for r in runs] == ["live", "live"], runs)
    L.expire_old(t0 + datetime.timedelta(seconds=6))
    chk("   5초가 지나면 다시", len(runs) == 4, runs)
    L.expire_old(t0 - datetime.timedelta(minutes=5))
    chk("   시계가 뒤로 가도 접는다 (검사)", len(runs) == 6, runs)
    db.run = real_run

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
