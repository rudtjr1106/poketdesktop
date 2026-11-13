# -*- coding: utf-8 -*-
"""큰 응답을 jsonable_encoder 없이 바로 JSON 으로 (deps.json_response, 11/14).

    python server/test_json_response.py

상자(/api/pokemon)는 800마리면 1MB 가 넘는다. FastAPI 가 dict 를 받으면 jsonable_encoder 로 통째로 한 번 훑고 나서
dumps 하는데, 그 훑기가 목록을 만드는 것보다 오래 걸렸다 (869마리: 만들기 0.24초, 훑기 0.38초, dumps 0.04초).

못 박는 것:

  1. **나가는 글자가 예전(JSONResponse(jsonable_encoder(x)))과 한 바이트도 다르지 않다** - 한글, 숫자 열쇠, 튜플,
     None, 실수, 중첩, datetime · set 같은 json 이 모르는 것까지.
  2. NaN 은 예전처럼 막힌다 (allow_nan=False).
  3. 진짜 상자 하나(포켓몬 · 알 · 박스 정보)도 똑같다. 그리고 확실히 빠르다.
"""
import datetime
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="poket-json-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi.encoders import jsonable_encoder                # noqa: E402
from fastapi.responses import JSONResponse                   # noqa: E402

from app import db, deps, main                         # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, str(got)[:300]))


def old(x):
    return JSONResponse(jsonable_encoder(x)).body


def new(x):
    r = deps.json_response(x)
    return r.body, r.media_type


def main_():
    print("1. 글자가 똑같다")
    cases = [
        {"pokemon": [{"id": 1, "info": {"name": "피카츄", "stats": {"hp": 35}, "types": ["전기"]}, "shiny": False,
                      "nickname": None, "happiness": 70, "ivPercent": 87.1}], "eggs": []},
        {"boxes": {"names": {0: "첫 상자", 3: "🐉 드래곤"}, "used": {"0": 30}}},
        {"t": (1, 2, 3), "f": 0.1 + 0.2, "neg": -0.0, "big": 10 ** 18, "e": "", "q": "\"따옴표\" \\ /\n\t"},
        {"when": datetime.datetime(2026, 11, 14, 2, 30, tzinfo=datetime.timezone.utc), "s": {7}},
        [1, "둘", None, True, {"a": [{"b": {}}]}],
    ]
    for i, c in enumerate(cases):
        body, mt = new(c)
        chk("경우 %d: 예전 JSONResponse 와 한 바이트도 다르지 않다" % (i + 1), body == old(c), (body[:120], old(c)[:120]))
    chk("media_type 은 application/json", mt == "application/json", mt)
    try:
        deps.json_response({"x": float("nan")})
        nan_blocked = False
    except ValueError:
        nan_blocked = True
    chk("NaN 은 예전처럼 막힌다", nan_blocked)

    print("2. 진짜 상자")
    db.init()
    from app import migrations
    migrations.run()
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                 " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')", ("상자", b"x", b"x")).lastrowid
    for i in range(120):
        main._give_starter(uid, ["PIKACHU", "BULBASAUR", "CHARMANDER", "SQUIRTLE"][i % 4])
    listing = main.box_listing(uid)
    chk("포켓몬이 들어 있다", len(listing["pokemon"]) == 120, len(listing["pokemon"]))
    chk("상자 하나도 예전 글자와 똑같다", new(listing)[0] == old(listing))
    r = main.list_pokemon({"user": {"id": uid}})
    chk("GET /api/pokemon 이 이 응답을 돌려준다", r.body == old(main.box_listing(uid)) and r.media_type == "application/json")
    t0 = time.perf_counter()
    for _ in range(5):
        old(listing)
    t_old = time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(5):
        new(listing)
    t_new = time.perf_counter() - t0
    chk("빠르다 (예전 %.0fms -> %.0fms, 5번)" % (t_old * 1000, t_new * 1000), t_new < t_old / 2, (t_old, t_new))

    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
