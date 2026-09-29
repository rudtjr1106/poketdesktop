# -*- coding: utf-8 -*-
"""PC 박스 검사 — 나눠 담기·옮기기·이름.

    python server/test_boxes.py

서버를 띄우지 않고 app.main 의 함수를 직접 부른다 (test_raid 와 같은 방식).

무엇을 못 박나:
  1. 박스를 처음 쓰는 사람의 포켓몬을 **잡은 순서대로 30마리씩** 나눠 담는다.
     이미 나눠 담았으면 다시 건드리지 않는다.
  2. 옮기면 그 박스에 들어가고, **가득 찬 박스에는 못 넣는다.**
  3. 데리고 다니던 애를 옮기면 바탕화면에서 내려온다.
  4. 이름은 비우면 기본 이름으로 돌아간다. 남의 박스는 못 건드린다.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-box-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                            # noqa: E402

from app import config, db, main                             # noqa: E402

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
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')",
        (name, b"x", b"x"))
    uid = cur.lastrowid
    ids = []
    for i in range(mons):
        cur = db.run(
            "INSERT INTO pokemon (user_id, species, level, exp, nature, ability,"
            " hidden_ability, gender, shiny, happiness, ivs, evs, moves,"
            " on_desktop, slot, met_level, caught_at)"
            " VALUES (?,'PIKACHU',5,0,'HARDY',NULL,0,'M',0,70,?,?,?,0,NULL,5,'')",
            (uid, json.dumps({}), json.dumps({}), json.dumps(["TACKLE"])))
        ids.append(cur.lastrowid)
    return uid, ids


def boxes_of(uid):
    return [r["box"] for r in db.q(
        "SELECT box FROM pokemon WHERE user_id=? ORDER BY id", (uid,))]


class Ctx(dict):
    pass


def ctx(uid):
    return {"user": {"id": uid}}


def main_():
    db.init()
    size = config.BOX_SIZE

    print("=== 처음 쓰는 사람의 포켓몬을 나눠 담는다 ===")
    uid, ids = mkuser("박스가", mons=size * 2 + 5)
    chk("처음에는 다 0번", set(boxes_of(uid)) == {0}, set(boxes_of(uid)))
    chk("나눠 담았다고 알린다", main.assign_boxes(uid) is True)
    got = boxes_of(uid)
    chk("앞 %d마리는 0번" % size, got[:size] == [0] * size, got[:5])
    chk("다음 %d마리는 1번" % size, got[size:size * 2] == [1] * size,
        got[size:size + 3])
    chk("나머지는 2번", got[size * 2:] == [2] * 5, got[size * 2:])
    chk("두 번 하지 않는다", main.assign_boxes(uid) is False)

    small, _ = mkuser("박스나", mons=3)
    chk("한 박스에 들어가면 그냥 둔다", main.assign_boxes(small) is False)
    chk("  그대로 0번", set(boxes_of(small)) == {0})

    print("\n=== 옮기기 ===")
    pid = ids[0]
    main.set_box(pid, main.BoxIn(box=5), ctx(uid))
    r = db.q1("SELECT box, on_desktop FROM pokemon WHERE id=?", (pid,))
    chk("고른 박스로 간다", r["box"] == 5, r["box"])

    db.run("UPDATE pokemon SET on_desktop=1, slot=0 WHERE id=?", (ids[1],))
    main.set_box(ids[1], main.BoxIn(box=5), ctx(uid))
    r = db.q1("SELECT box, on_desktop, slot FROM pokemon WHERE id=?", (ids[1],))
    chk("데리고 다니던 애는 내려온다",
        r["box"] == 5 and not r["on_desktop"] and r["slot"] is None,
        (r["box"], r["on_desktop"], r["slot"]))

    # 0번을 가득 채운 뒤 한 마리 더 넣어 본다
    full, fids = mkuser("박스다", mons=size)
    extra_uid, extra = mkuser("박스라", mons=1)
    db.run("UPDATE pokemon SET user_id=? WHERE id=?", (full, extra[0]))
    db.run("UPDATE pokemon SET box=1 WHERE id=?", (extra[0],))
    try:
        main.set_box(extra[0], main.BoxIn(box=0), ctx(full))
        chk("가득 찬 박스에는 못 넣는다", False, "넣어졌다")
    except HTTPException as e:
        chk("가득 찬 박스에는 못 넣는다", e.status_code == 409, e.status_code)
    chk("  거절해도 제자리", db.q1("SELECT box FROM pokemon WHERE id=?",
                                  (extra[0],))["box"] == 1)

    try:
        main.set_box(pid, main.BoxIn(box=config.BOX_COUNT), ctx(uid))
        chk("없는 박스는 거절", False, "받아들였다")
    except HTTPException as e:
        chk("없는 박스는 거절", e.status_code == 400, e.status_code)

    other, oids = mkuser("남", mons=1)
    try:
        main.set_box(oids[0], main.BoxIn(box=1), ctx(uid))
        chk("남의 포켓몬은 못 옮긴다", False, "옮겨졌다")
    except HTTPException as e:
        chk("남의 포켓몬은 못 옮긴다", e.status_code == 404, e.status_code)

    print("\n=== 박스 이름 ===")
    r = main.set_box_name(main.BoxNameIn(no=2, name="불꽃방"), ctx(uid))
    chk("이름을 붙인다", r["names"].get("2") == "불꽃방", r["names"])
    r = main.set_box_name(main.BoxNameIn(no=2, name="  물방  "), ctx(uid))
    chk("앞뒤 공백은 턴다", r["names"].get("2") == "물방", r["names"])
    r = main.set_box_name(main.BoxNameIn(no=2, name=""), ctx(uid))
    chk("비우면 기본 이름으로 (줄이 사라진다)", "2" not in r["names"], r["names"])
    main.set_box_name(main.BoxNameIn(no=1, name="남의방"), ctx(other))
    chk("남의 이름은 안 섞인다",
        main._box_names(uid).get("1") is None
        and main._box_names(other).get("1") == "남의방",
        (main._box_names(uid), main._box_names(other)))
    try:
        main.set_box_name(main.BoxNameIn(no=config.BOX_COUNT, name="x"), ctx(uid))
        chk("없는 박스 이름은 거절", False, "받아들였다")
    except HTTPException as e:
        chk("없는 박스 이름은 거절", e.status_code == 400, e.status_code)

    print("\n=== 목록에 실려 나간다 ===")
    main.set_box_name(main.BoxNameIn(no=0, name="첫방"), ctx(uid))
    out = main.list_pokemon(ctx(uid))
    b = out.get("boxes") or {}
    chk("박스 정보가 실린다", b.get("size") == size and b.get("count") == config.BOX_COUNT,
        b)
    chk("이름도", (b.get("names") or {}).get("0") == "첫방", b.get("names"))
    chk("박스마다 마릿수", (b.get("used") or {}).get("5") == 2, b.get("used"))
    chk("포켓몬마다 박스 번호",
        all("box" in m for m in out["pokemon"]), out["pokemon"][:1])

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
