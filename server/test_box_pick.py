# -*- coding: utf-8 -*-
"""상자 창이 바뀐 것만 다시 받는다 - POST /api/pokemon/pick (2.5.0).

    python server/test_box_pick.py

못 박는 것:

  1. 물은 것 가운데 내 것 + 지금 데리고 다니는 것 전부가 온다. 묻지 않은 박스 것 · 남의 것 · 없는 번호는 안 온다.
  2. 한 마리 한 마리의 모습이 전체 목록(GET /api/pokemon)과 **똑같다** - 도감 정보 · 유대 · 탐험 중 · 리본까지.
  3. 알 전부 · 박스 정보(칸 수 · 이름)가 전체 목록과 같다.
  4. 음수(알)는 그냥 뺀다. 숫자가 아닌 것은 400. 한 번에 PICK_MAX 개까지 (넘으면 막힌다 - 창은 전체를 받는다).
  5. 500개가 넘어도 나눠 묻는다 (SQLite 의 IN 칸 수 한도).
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="poket-pick-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                            # noqa: E402
from pydantic import ValidationError                         # noqa: E402

from app import db, main, migrations                         # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, str(got)[:300]))


def mkuser(name):
    return db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                  " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')", (name, b"x", b"x")).lastrowid


def pick(uid, ids):
    r = main.pick_pokemon(main.PickIn(ids=ids), {"user": {"id": uid}})
    return json.loads(r.body)


def main_():
    db.init()
    migrations.run()
    me, other = mkuser("상자주인"), mkuser("남")
    for i in range(620):
        main._give_starter(me, ["PIKACHU", "BULBASAUR", "CHARMANDER", "SQUIRTLE"][i % 4])
    main._give_starter(other, "PIKACHU")
    mine = [r["id"] for r in db.q("SELECT id FROM pokemon WHERE user_id=? ORDER BY id", (me,))]
    theirs = db.q1("SELECT id FROM pokemon WHERE user_id=?", (other,))["id"]
    db.run("UPDATE pokemon SET on_desktop=0, slot=NULL WHERE user_id=?", (me,))
    party = mine[:3]
    for i, pid in enumerate(party):
        db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=?", (i, pid))
    db.run("UPDATE pokemon SET nickname='번개' WHERE id=?", (mine[10],))
    full = main.box_listing(me)
    by_full = dict((m["id"], m) for m in full["pokemon"])

    print("1. 무엇이 오나")
    asked = [mine[10], mine[11], theirs, 999999]
    r = pick(me, asked)
    got = sorted(m["id"] for m in r["pokemon"])
    chk("물은 내 것 + 파티 전부", got == sorted(party + [mine[10], mine[11]]), got)
    chk("남의 것 · 없는 번호는 안 온다", theirs not in got and 999999 not in got)
    chk("묻지 않은 박스 것은 안 온다", mine[12] not in got)

    print("2. 모습이 전체 목록과 똑같다")
    same = all(json.dumps(m, sort_keys=True, ensure_ascii=False) == json.dumps(by_full[m["id"]], sort_keys=True, ensure_ascii=False)
               for m in r["pokemon"])
    chk("한 마리 한 마리가 전체 목록의 것과 같다 (별명 · 도감 정보까지)", same)
    chk("  별명이 실렸다", next(m for m in r["pokemon"] if m["id"] == mine[10])["info"]["name"] == "번개")

    print("3. 알 · 박스 정보")
    chk("알이 전체 목록과 같다", r["eggs"] == json.loads(json.dumps(full["eggs"], ensure_ascii=False)), r["eggs"])
    chk("박스 정보(칸 수 · 이름)가 전체 목록과 같다", r["boxes"] == json.loads(json.dumps(full["boxes"])), (r["boxes"], full["boxes"]))

    print("4. 이상한 것")
    r = pick(me, [-5, mine[20]])
    chk("음수(알)는 그냥 뺀다", sorted(m["id"] for m in r["pokemon"]) == sorted(party + [mine[20]]))
    r = pick(me, [])
    chk("아무것도 안 물으면 파티만", sorted(m["id"] for m in r["pokemon"]) == sorted(party))
    try:
        pick(me, ["가"])
        bad = None
    except HTTPException as e:
        bad = e.status_code
    chk("숫자가 아니면 400", bad == 400, bad)
    try:
        main.PickIn(ids=list(range(1, main.PICK_MAX + 2)))
        over = False
    except ValidationError:
        over = True
    chk("PICK_MAX 개를 넘으면 막힌다 (창은 전체를 받는다)", over)
    chk("  창의 한도와 같다", main.PICK_MAX == 1000)

    print("5. 많이")
    r = pick(me, mine)
    chk("620마리를 물어도 다 온다 (나눠 묻는다)", len(r["pokemon"]) == len(mine), len(r["pokemon"]))

    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
