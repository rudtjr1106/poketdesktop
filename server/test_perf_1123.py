# -*- coding: utf-8 -*-
"""11/23 부하 줄이기 검사 (CPU 크레딧이 바닥나 30% 로 묶인 서버에서 1분마다 오는 요청을 덜 들여). 서버를 띄우지 않는다.

    POKET_DB=/tmp/x.db POKET_POKEDEX=data/pokedex.json PYTHONPATH=.. python test_perf_1123.py

  1. 색인: 바탕화면 포켓몬 · 마릿수(pokemon(user_id, on_desktop, slot)), 안 본 대전 수(pvp_match(a_id, a_seen) ·
     (b_id, b_seen)) - 질의 계획이 그 색인을 쓴다 (마릿수는 표를 안 읽는다).
  2. 커넥션 설정: synchronous=NORMAL · cache_size 32MB · temp_store=MEMORY.
  3. json_response (1분마다 오는 넷도 이제 이것으로): JSON 이 받는 값이면 Starlette JSONResponse 와 같은 글자,
     datetime · set 같은 것은 jsonable_encoder.
  4. decorate_row: 행이 그대로면 지난번 결과, 행 · 유대 여부가 바뀌면 새로 센다. 결과는 decorate 와 같다.
     상자 전체(box_listing)도 이것을 쓰되 겉을 복사한다 - 예전 내용과 같고, 뒤처리가 기억해 둔 것을 안 고친다.
  5. 아르케 state 한 번에 secrets.json 을 한 번만 stat 한다 (예전 30번 가까이). 요청 사이에는 손질이 바로 든다.
  6. 아르케 장 시각(window)은 기억하되 POKET_ARCHE_START 를 바꾸면 새로 센다.
"""
import datetime
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
os.environ.setdefault("POKET_DB", os.path.join(tempfile.mkdtemp(), "perf.db"))
os.environ.setdefault("POKET_POKEDEX", os.path.join(HERE, "data", "pokedex.json"))
ARCHE_DIR = os.environ.setdefault("POKET_ARCHE_DIR", tempfile.mkdtemp())

from fastapi.responses import JSONResponse            # noqa: E402

from app import arche, db, deps                      # noqa: E402
from common import arche as A                        # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def plan(sql, args):
    return " | ".join(r[3] for r in db.q("EXPLAIN QUERY PLAN " + sql, args))


def t_indexes():
    print("-- 1. 색인")
    names = set(r["name"] for r in db.q("SELECT name FROM sqlite_master WHERE type='index'"))
    chk("색인 셋이 생긴다", {"idx_pokemon_desk", "idx_pvp_match_a_seen", "idx_pvp_match_b_seen"} <= names, sorted(names)[:8])
    p = plan("SELECT * FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY on_desktop DESC, slot ASC, id ASC", (1,))
    chk("바탕화면 포켓몬은 idx_pokemon_desk 로 찾는다", "idx_pokemon_desk" in p, p)
    p = plan("SELECT COUNT(*) c, SUM(on_desktop) d FROM pokemon WHERE user_id=?", (1,))
    chk("마릿수는 색인만 읽는다 (COVERING)", "COVERING INDEX idx_pokemon_desk" in p, p)
    p = plan("SELECT COUNT(*) c FROM pvp_match WHERE (a_id=? AND a_seen=0) OR (b_id=? AND b_seen=0)", (1, 1))
    chk("안 본 대전 수는 a_seen · b_seen 색인으로 찾는다 (큰 log 칸 앞에서 끝난다)", "idx_pvp_match_a_seen" in p
        and "idx_pvp_match_b_seen" in p, p)


def t_pragmas():
    print("-- 2. 커넥션 설정")
    c = db.connect()
    sync = c.execute("PRAGMA synchronous").fetchone()[0]
    cache = c.execute("PRAGMA cache_size").fetchone()[0]
    temp = c.execute("PRAGMA temp_store").fetchone()[0]
    chk("synchronous=NORMAL(1) · cache_size=-32768 · temp_store=MEMORY(2)", (sync, cache, temp) == (1, -32768, 2),
        (sync, cache, temp))
    chk("WAL 은 그대로", c.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal")


def t_json_response():
    print("-- 3. json_response")
    for content in ({"a": 1, "b": "한글", "c": [1, 2.5, None, True], "d": {"e": "f"}, 3: "x"},
                    {"pokemon": [{"id": 1, "info": {"stats": {"hp": 10}}, "moves": ["TACKLE"]}]}, []):
        mine = deps.json_response(content).body
        theirs = JSONResponse(content).body
        chk("JSON 이 받는 값은 Starlette 와 같은 글자 (%s)" % type(content).__name__, mine == theirs, (mine[:60], theirs[:60]))
    r = deps.json_response({"at": datetime.datetime(2026, 11, 23, 15, 0, tzinfo=datetime.timezone.utc), "s": {1, 2}})
    body = json.loads(r.body)
    chk("datetime · set 은 예전처럼 jsonable_encoder 로", body["at"].startswith("2026-11-23T15:00") and sorted(body["s"]) == [1, 2],
        body)
    chk("media_type application/json", r.media_type == "application/json")
    try:
        deps.json_response({"x": float("nan")})
        nan_raised = False
    except ValueError:
        nan_raised = True
    chk("NaN 은 예전처럼 거절 (allow_nan=False)", nan_raised)


def t_decorate_row():
    print("-- 4. decorate_row")
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login, last_ip)"
                 " VALUES ('데코', ?, ?, 1, 30, 0, '2026-11-23T00:00:00+00:00', '2026-11-23T00:00:00+00:00', '')",
                 (b"x", b"x")).lastrowid
    ivs = json.dumps({"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31})
    db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, ability, gender, shiny, happiness, ivs, evs, moves,"
           " on_desktop, slot, met_level, caught_at) VALUES (?, 'PIKACHU', 20, 8000, 'HARDY', 'STATIC', 'M', 0, 70,"
           " ?, '{}', ?, 1, 0, 5, '2026-11-23T00:00:00+00:00')", (uid, ivs, json.dumps(["THUNDERSHOCK"])))
    row = db.q1("SELECT * FROM pokemon WHERE user_id=?", (uid,))
    a = deps.decorate_row(row)
    b = deps.decorate_row(db.q1("SELECT * FROM pokemon WHERE user_id=?", (uid,)))
    chk("행이 그대로면 지난번 결과를 그대로 (같은 객체)", a is b)
    chk("결과는 decorate(row_to_mon) 와 같다", json.dumps(a, sort_keys=True, default=str)
        == json.dumps(deps.decorate(db.row_to_mon(row)), sort_keys=True, default=str))
    db.run("UPDATE pokemon SET level=21, exp=9300 WHERE user_id=?", (uid,))
    c = deps.decorate_row(db.q1("SELECT * FROM pokemon WHERE user_id=?", (uid,)))
    chk("행이 바뀌면 새로 센다 (레벨 21)", c is not a and c["level"] == 21, c.get("level"))
    # 상자 전체(/api/pokemon)도 기억해 둔 것을 쓰되 겉을 복사해서 뒤처리가 고친다 - 기억해 둔 dict 는 그대로
    from app import main
    want = main._dress(uid, main._mons(uid))
    got = main.box_listing(uid)["pokemon"]
    chk("상자 전체: 예전 _dress(_mons) 와 같은 내용", json.dumps(got, sort_keys=True, default=str)
        == json.dumps(want, sort_keys=True, default=str))
    got[0]["away"] = True
    chk("  돌려준 dict 를 고쳐도 기억해 둔 것은 그대로 (겉 복사)",
        "away" not in deps.decorate_row(db.q1("SELECT * FROM pokemon WHERE user_id=?", (uid,))))
    keep = deps.DECO_KEEP
    deps.DECO_KEEP = 1
    try:
        db.run("UPDATE pokemon SET level=22, exp=10600 WHERE user_id=?", (uid,))
        deps.decorate_row(db.q1("SELECT * FROM pokemon WHERE user_id=?", (uid,)))     # 새 열쇠 하나를 넣으면
        chk("기억해 두는 수를 넘으면 오래된 것부터 뺀다", len(deps._DECO) <= 1, len(deps._DECO))
    finally:
        deps.DECO_KEEP = keep


def t_arche_stat():
    print("-- 5. 아르케 state 의 secrets.json stat")
    path = os.path.join(ARCHE_DIR, "secrets.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"salt": "x" * 20, "chapters": {"1": {"journal": [{"after": 0, "text": "첫 줄"}]}}}, f, ensure_ascii=False)
    real = arche.os.stat
    calls = []

    def counting(p, *a, **k):
        if str(p).endswith("secrets.json"):
            calls.append(p)
        return real(p, *a, **k)
    arche.os.stat = counting
    try:
        now = A.window(1)[0] + datetime.timedelta(hours=1)
        arche.state(1, now=now)
        n1 = len(calls)
    finally:
        arche.os.stat = real
    chk("state 한 번에 stat 한 번 (예전 30번 가까이)", n1 == 1, n1)
    chk("state 가 끝나면 꽂아 둔 자료를 뺀다", getattr(arche._pin, "data", arche._UNPINNED) is arche._UNPINNED)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"salt": "x" * 20, "chapters": {"1": {"journal": [{"after": 0, "text": "고친 줄"}]}}}, f, ensure_ascii=False)
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 5 * 10 ** 9))
    out = arche.state(1, now=A.window(1)[0] + datetime.timedelta(hours=1))
    texts = [j["text"] for j in out["chapters"][0]["journal"]]
    chk("요청 사이에는 손질이 바로 든다 (다음 state 에 고친 줄)", "고친 줄" in texts, texts)


def t_window():
    print("-- 6. 아르케 장 시각 기억")
    w1 = A.window(2)
    chk("같은 장 · 같은 시작 날이면 같은 값", A.window(2) is w1)
    old = os.environ.get("POKET_ARCHE_START")
    os.environ["POKET_ARCHE_START"] = "2026-12-01"
    try:
        w2 = A.window(2)
        chk("POKET_ARCHE_START 를 바꾸면 새로 센다", w2 != w1 and w2[0].date() >= datetime.date(2026, 11, 30), w2)
    finally:
        if old is None:
            os.environ.pop("POKET_ARCHE_START", None)
        else:
            os.environ["POKET_ARCHE_START"] = old
    chk("되돌리면 처음 값", A.window(2) == w1)


def main():
    db.init()
    t_indexes()
    t_pragmas()
    t_json_response()
    t_decorate_row()
    t_arche_stat()
    t_window()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
