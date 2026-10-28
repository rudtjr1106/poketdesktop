# -*- coding: utf-8 -*-
"""여러 마리 한꺼번에 놓아주기 검사 (POST /api/pokemon/release-many).

    python server/test_release_many.py

서버를 띄우지 않고 app.main 의 함수를 직접 부른다 (test_boxes 와 같은 방식).

무엇을 못 박나:
  1. 고른 것을 한 번에 놓아준다. 지니던 도구는 가방으로, 탐험 성장 기록은 지운다 (한 마리 놓아주기와 같다).
  2. **한 마리씩 따로 본다** - 막힌 것만 남기고 나머지는 놓아준다. 못 놓은 것은 까닭과 함께 돌려준다:
     탐험 중 · 배틀 중 · 남의 것/없는 번호.
  3. 같은 번호를 두 번 적어도 한 번, 글자 번호도 받는다. 고른 것이 없으면 400.
  4. 한 마리 놓아주기는 예전 그대로다 (같은 뒷정리 함수를 쓰게 바꿨다). 배틀 중이면 한 마리 길도 409 (두 길이 같다).
  5. 같은 놓아주기가 겹쳐 와도 도구는 한 번만 가방에 (지우기가 먼저, 지운 쪽만 도구를 돌려준다).
  6. 한 마리가 터져도 나머지는 놓아주고, 터진 것은 '다시 해 주세요' 로 돌려준다.
  7. 번호: True·3.5·None 은 400, 3.0 은 3번.
"""
import datetime
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-release-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                            # noqa: E402

from app import db, items, main                              # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name, mons=0):
    uid = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')",
        (name, b"x", b"x")).lastrowid
    ids = []
    for _ in range(mons):
        ids.append(db.run(
            "INSERT INTO pokemon (user_id, species, level, exp, nature, ability,"
            " hidden_ability, gender, shiny, happiness, ivs, evs, moves,"
            " on_desktop, slot, met_level, caught_at)"
            " VALUES (?,'PIKACHU',5,0,'HARDY',NULL,0,'M',0,70,?,?,?,0,NULL,5,'')",
            (uid, json.dumps({}), json.dumps({}), json.dumps(["TACKLE"]))).lastrowid)
    return uid, ids


def ctx(uid):
    return {"user": {"id": uid}}


def alive(ids):
    if not ids:
        return set()
    return set(r["id"] for r in db.q("SELECT id FROM pokemon WHERE id IN (%s)" % ",".join("?" * len(ids)),
                                       tuple(ids)))


def iso(delta_sec):
    t = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=delta_sec)
    return t.isoformat()


def refused(code, ids, uid):
    try:
        main.release_many(main.ReleaseManyIn(ids=ids), ctx(uid))
    except HTTPException as e:
        return e.status_code == code and e.detail
    return False


def main_():
    db.init()

    print("=== 한 번에 놓아준다 ===")
    uid, ids = mkuser("여럿", 10)
    db.run("UPDATE pokemon SET held='LEFTOVERS' WHERE id=?", (ids[0],))
    db.run("UPDATE pokemon SET nickname='번개' WHERE id=?", (ids[1],))
    db.run("INSERT INTO expedition_mon (pokemon_id, user_id, xp) VALUES (?,?,50)", (ids[2], uid))
    bag0 = items.bag_count(uid, "LEFTOVERS")
    r = main.release_many(main.ReleaseManyIn(ids=ids[:4]), ctx(uid))
    chk("네 마리가 다 사라진다", r["ok"] and alive(ids[:4]) == set() and alive(ids[4:]) == set(ids[4:]), r)
    chk("  놓아준 것의 번호·이름을 돌려준다 (별명이면 별명)", [x["id"] for x in r["released"]] == ids[:4]
        and r["released"][1]["name"] == "번개" and r["released"][0]["name"] == "피카츄" and r["failed"] == [],
        r["released"])
    chk("  지니던 도구는 가방으로 (한 마리 놓아주기와 같다)", items.bag_count(uid, "LEFTOVERS") == bag0 + 1
        and r["heldToBag"] == [items.name_of("LEFTOVERS")] and "가방" in r["message"], r)
    chk("  탐험 성장 기록도 지운다", db.q1("SELECT 1 FROM expedition_mon WHERE pokemon_id=?", (ids[2],)) is None)
    chk("  알림 글에 몇 마리인지", "4마리" in r["message"], r["message"])

    print("\n=== 막힌 것만 남긴다 ===")
    other, oids = mkuser("남", 1)
    # ids[4] = 탐험 중, ids[5] = 야생 배틀 중, ids[6] = 놓아줄 수 있다, oids[0] = 남의 것, 999999 = 없는 번호
    db.run("INSERT INTO expedition (user_id, pokemon_id, place, hours, grade, score, started_at, ends_at, state)"
           " VALUES (?,?,'forest',1,'C',0,?,?,'out')", (uid, ids[4], iso(-60), iso(3600)))
    wid = db.run("INSERT INTO wild (user_id, state, species, data, created_at, expires_at)"
                 " VALUES (?,'revealed','PIKACHU','{}',?,?)", (uid, iso(-10), iso(600))).lastrowid
    db.run("INSERT INTO battle (user_id, wild_id, mine_id, state, me, foe, created_at, expires_at)"
           " VALUES (?,?,?,'active','{}','{}',?,?)", (uid, wid, ids[5], iso(-10), iso(600)))
    r = main.release_many(main.ReleaseManyIn(ids=[ids[4], ids[5], ids[6], oids[0], 999999]), ctx(uid))
    why = dict((x["id"], x["reason"]) for x in r["failed"])
    chk("**놓아줄 수 있는 것만 놓아준다** (하나가 막혔다고 다 되돌리지 않는다)",
        [x["id"] for x in r["released"]] == [ids[6]] and alive([ids[6]]) == set(), r["released"])
    chk("  탐험 중이면 못 놓는다 (한 마리 길과 같은 말)", "탐험" in why.get(ids[4], "")
        and alive([ids[4]]) == {ids[4]}, why)
    chk("  야생 배틀 중이면 못 놓는다", "배틀 중" in why.get(ids[5], "") and alive([ids[5]]) == {ids[5]}, why)
    chk("  남의 것은 안 건드리고 '없다' 고만 한다 (남의 포켓몬 이름을 흘리지 않는다)",
        why.get(oids[0]) == "그런 포켓몬이 없습니다." and alive(oids) == set(oids)
        and "name" not in [x for x in r["failed"] if x["id"] == oids[0]][0], r["failed"])
    chk("  없는 번호도 같은 까닭", why.get(999999) == "그런 포켓몬이 없습니다.", why)
    chk("  막힌 내 포켓몬은 이름도 같이 온다 (화면이 무엇이 남았는지 적는다)",
        [x for x in r["failed"] if x["id"] == ids[4]][0].get("name") == "피카츄", r["failed"])
    chk("  알림 글: 놓아준 수와 못 보낸 수", "1마리를 보내주었습니다" in r["message"] and "4마리는 못 보냈습니다" in r["message"],
        r["message"])
    r = main.release_many(main.ReleaseManyIn(ids=[ids[4], oids[0]]), ctx(uid))
    chk("하나도 못 놓으면 그렇게 말한다 (오류가 아니라 까닭 목록)", r["released"] == [] and len(r["failed"]) == 2
        and "한 마리도" in r["message"] and "2마리 모두 막혔습니다" in r["message"], r)
    # 끝난 채 남은 배틀 줄(야생이 사라졌다)은 세지 않는다 - deps.in_battle 과 같다
    db.run("DELETE FROM wild WHERE id=?", (wid,))
    r = main.release_many(main.ReleaseManyIn(ids=[ids[5]]), ctx(uid))
    chk("  끝난 채 남은 배틀 줄은 막지 않는다", [x["id"] for x in r["released"]] == [ids[5]], r)

    print("\n=== 받는 모양 ===")
    r = main.release_many(main.ReleaseManyIn(ids=[ids[7], ids[7], str(ids[8])]), ctx(uid))
    chk("같은 것을 두 번 적어도 한 번, 글자 번호도 받는다", [x["id"] for x in r["released"]] == [ids[7], ids[8]]
        and r["failed"] == [], r)
    chk("고른 것이 없으면 400", refused(400, [], uid) and refused(400, [0, -3], uid))
    chk("번호가 아니면 400", refused(400, ["x"], uid))
    chk("True 는 1번이 아니라 400 (bool 은 번호가 아니다)", refused(400, [True], uid))
    chk("소수는 400 (3.5 가 3번이 되지 않게), None·묶음도 400",
        refused(400, [3.5], uid) and refused(400, [None], uid) and refused(400, [{"id": 1}], uid))
    spare, sids = mkuser("실수", 1)
    r = main.release_many(main.ReleaseManyIn(ids=[float(sids[0])]), ctx(spare))
    chk("정수 값인 실수(3.0)는 받는다", [x["id"] for x in r["released"]] == sids and alive(sids) == set(), r)
    try:
        main.ReleaseManyIn(ids=list(range(1, 202)))
        chk("한 번에 200마리까지 (그 넘게는 받지 않는다)", False, "받았다")
    except Exception:                                       # noqa: BLE001 - pydantic ValidationError
        chk("한 번에 200마리까지 (그 넘게는 받지 않는다)", True)

    print("\n=== 겹쳐 온 놓아주기 ===")
    twice, tids = mkuser("두번", 3)
    db.run("UPDATE pokemon SET held='LEFTOVERS' WHERE id=?", (tids[0],))
    bag0 = items.bag_count(twice, "LEFTOVERS")
    row = db.q1("SELECT * FROM pokemon WHERE id=?", (tids[0],))
    # 두 요청이 같은 줄을 먼저 읽어 둔 상태 - 예전 차례(도구 먼저)면 둘 다 도구를 넣었다
    a, b = main._release_row(twice, row), main._release_row(twice, row)
    chk("**도구는 한 번만 가방에** (먼저 지운 요청만 돌려준다)", a == ("피카츄", "LEFTOVERS") and b is None
        and items.bag_count(twice, "LEFTOVERS") == bag0 + 1, (a, b, items.bag_count(twice, "LEFTOVERS") - bag0))
    other_row = db.q1("SELECT * FROM pokemon WHERE id=?", (tids[1],))
    chk("  남의 번호로는 안 지운다 (user_id 도 본다)", main._release_row(uid, other_row) is None
        and alive([tids[1]]) == {tids[1]})

    print("\n=== 한 마리가 터져도 나머지는 ===")
    real_away = main.expedition.is_away

    def boom(u, pid):
        if pid == tids[1]:
            raise RuntimeError("database is locked")
        return real_away(u, pid)
    main.expedition.is_away = boom
    try:
        r = main.release_many(main.ReleaseManyIn(ids=[tids[1], tids[2]]), ctx(twice))
    finally:
        main.expedition.is_away = real_away
    chk("터진 것만 failed, 나머지는 놓아준다", [x["id"] for x in r["released"]] == [tids[2]]
        and [x["id"] for x in r["failed"]] == [tids[1]] and "다시 해 주세요" in r["failed"][0]["reason"]
        and alive([tids[1]]) == {tids[1]}, r)

    print("\n=== 한 마리 놓아주기는 그대로 ===")
    db.run("UPDATE pokemon SET held='LEFTOVERS' WHERE id=?", (ids[9],))
    bag0 = items.bag_count(uid, "LEFTOVERS")
    r = main.release(ids[9], ctx(uid))
    chk("한 마리 놓아주기: 사라지고 도구는 가방으로, 글도 예전 그대로", alive([ids[9]]) == set()
        and items.bag_count(uid, "LEFTOVERS") == bag0 + 1 and r["message"].startswith("피카츄 을(를) 보내주었습니다.")
        and "가방에 넣었습니다" in r["message"], r)
    try:
        main.release(ids[4], ctx(uid))
        chk("  탐험 중이면 409 (예전 그대로)", False, "놓아졌다")
    except HTTPException as e:
        chk("  탐험 중이면 409 (예전 그대로)", e.status_code == 409 and "탐험" in e.detail, e.detail)
    # 배틀 중: 여러 마리 길과 같은 409·같은 말 (예전에는 한 마리 길로는 놓아졌다)
    fid = db.run("INSERT INTO wild (user_id, state, species, data, created_at, expires_at)"
                 " VALUES (?,'revealed','PIKACHU','{}',?,?)", (twice, iso(-10), iso(600))).lastrowid
    db.run("INSERT INTO battle (user_id, wild_id, mine_id, state, me, foe, created_at, expires_at)"
           " VALUES (?,?,?,'active','{}','{}',?,?)", (twice, fid, tids[1], iso(-10), iso(600)))
    many = main.release_many(main.ReleaseManyIn(ids=[tids[1]]), ctx(twice))["failed"]
    try:
        main.release(tids[1], ctx(twice))
        chk("  배틀 중이면 409 (여러 마리 길과 같은 말)", False, "놓아졌다")
    except HTTPException as e:
        chk("  배틀 중이면 409 (여러 마리 길과 같은 말)", e.status_code == 409 and many
            and e.detail == many[0]["reason"] and alive([tids[1]]) == {tids[1]}, (e.detail, many))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
