# -*- coding: utf-8 -*-
"""끝난 야생 배틀이 '배틀 중' 으로 남지 않는다 (1.10.4). 서버를 띄우지 않는다.

    python server/test_stale_battle.py

게시판 #174 "퀵볼로 야생 포켓몬을 잡으면 전투 중 판정이 유지되는 것 같습니다."

배틀이 걸린 야생을 **배틀 밖의 볼 던지기**(/api/wild/{id}/catch)로 잡으면 야생 줄만 지워지고
배틀 줄은 active 로 남았다. 그 뒤로는 내 포켓몬에게 도구를 쓰거나 지닌 도구를 바꾸려 할 때마다
"배틀 중에는 쓸 수 없습니다" 가 떴다 - 다음 야생 배틀을 걸 때까지 (시간이 지나도 안 풀렸다).

  1. 배틀 밖에서 잡으면 걸려 있던 배틀도 끝난다 (result = caught).
  2. 야생이 떠나거나(flee) 시간이 다 되어 치워져도(_sweep) 끝난다 (result = fled).
  3. **이미 그렇게 남아 있는 줄**(야생이 없거나 제한 시간이 지난 줄)은 '배틀 중' 으로 세지 않고,
     물어본 김에 닫는다. 살아 있는 배틀은 그대로 '배틀 중' 이다.
"""
import datetime
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-stale-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                            # noqa: E402

from common import pokelogic as P                            # noqa: E402
from app import battle_routes as BR                          # noqa: E402
from app import auth, db, deps, item_routes, items, main     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mkuser(name):
    return db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')",
        (name, b"x", b"x")).lastrowid


def mkmon(uid, species, level, slot):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(3), shiny_rate=10 ** 9)
    m["noEvolve"] = True
    pid = db.insert_mon(uid, m, "")
    db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=?", (slot, pid))
    return pid


def mkwild(uid, species="RATTATA", level=5, minutes=5):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(9), shiny_rate=10 ** 9)
    later = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes)).isoformat()
    return db.run("INSERT INTO wild (user_id, state, species, data, throws, created_at, expires_at)"
                  " VALUES (?,?,?,?,0,?,?)", (uid, "revealed", species, json.dumps(m), auth.now_iso(), later)).lastrowid


def ctx(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def battle_of(bid):
    return dict(db.q1("SELECT state, result, wild_id FROM battle WHERE id=?", (bid,)))


def main_():
    db.init()
    uid = mkuser("퀵볼러")
    lead = mkmon(uid, "SNORLAX", 40, 0)
    items.bag_add(uid, "MASTERBALL", 5)
    items.bag_add(uid, "RARECANDY", 3)

    print("=== 배틀이 걸린 야생을 배틀 밖에서 잡는다 ===")
    wid = mkwild(uid)
    r = BR.start(wid, ctx(uid))
    bid = r["battle"]["id"]
    chk("배틀을 걸면 내 포켓몬은 배틀 중이다", deps.in_battle(uid, lead) and battle_of(bid)["state"] == "active")
    try:
        item_routes.use(item_routes.UseIn(item="RARECANDY", pokemon=lead), ctx(uid))
        blocked = False
    except HTTPException as e:
        blocked = e.status_code == 400 and "배틀 중" in str(e.detail)
    chk("  배틀 중에는 도구를 못 쓴다 (원래 그렇다)", blocked)
    got = main.wild_catch(wid, main.CatchIn(ball="MASTERBALL"), ctx(uid))
    chk("배틀 밖의 볼 던지기로 잡혔다", got["caught"] and db.q1("SELECT id FROM wild WHERE id=?", (wid,)) is None)
    chk("**걸려 있던 배틀도 끝났다** (caught)", battle_of(bid) == {"state": "done", "result": "caught", "wild_id": wid}, battle_of(bid))
    chk("  내 포켓몬은 더는 배틀 중이 아니다", not deps.in_battle(uid, lead))
    lv = db.q1("SELECT level FROM pokemon WHERE id=?", (lead,))["level"]
    out = item_routes.use(item_routes.UseIn(item="RARECANDY", pokemon=lead), ctx(uid))
    chk("  바로 도구를 쓸 수 있다 (이상한사탕)", out.get("ok") and db.q1("SELECT level FROM pokemon WHERE id=?", (lead,))["level"] == lv + 1,
        out.get("message"))

    print("\n=== 야생이 떠나거나 시간이 다 됐다 ===")
    wid = mkwild(uid)
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    main.wild_flee(wid, ctx(uid))
    chk("보내 주면 배틀도 끝난다 (fled)", battle_of(bid)["state"] == "done" and battle_of(bid)["result"] == "fled"
        and not deps.in_battle(uid, lead), battle_of(bid))
    wid = mkwild(uid)
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).isoformat()
    db.run("UPDATE wild SET expires_at=? WHERE id=?", (past, wid))
    main._sweep(uid)
    chk("시간이 다 되어 치워져도 배틀이 끝난다", db.q1("SELECT id FROM wild WHERE id=?", (wid,)) is None
        and battle_of(bid)["state"] == "done" and not deps.in_battle(uid, lead), battle_of(bid))

    print("\n=== 이미 남아 있는 줄 (옛 판이 남긴 것) ===")
    wid = mkwild(uid)
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    db.run("DELETE FROM wild WHERE id=?", (wid,))                 # 옛 서버: 야생 줄만 지워졌다
    chk("야생이 없는 배틀은 '배틀 중' 으로 세지 않는다", battle_of(bid)["state"] == "active" and not deps.in_battle(uid, lead))
    chk("  물어본 김에 닫는다", battle_of(bid)["state"] == "done", battle_of(bid))
    wid = mkwild(uid)
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    db.run("UPDATE battle SET expires_at=? WHERE id=?", (past, bid))
    chk("제한 시간이 지난 배틀도 세지 않고 닫는다", not deps.in_battle(uid, lead) and battle_of(bid)["state"] == "done", battle_of(bid))
    db.run("DELETE FROM wild WHERE id=?", (wid,))
    wid = mkwild(uid)
    bid = BR.start(wid, ctx(uid))["battle"]["id"]
    other = mkmon(uid, "ONIX", 30, 1)
    chk("살아 있는 배틀은 그대로 배틀 중이다 (싸우는 포켓몬만)", deps.in_battle(uid, lead) and not deps.in_battle(uid, other)
        and battle_of(bid)["state"] == "active")

    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
