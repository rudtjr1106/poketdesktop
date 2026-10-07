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


def counts(uid):
    return dict((r["box"], r["n"]) for r in db.q(
        "SELECT box, COUNT(*) n FROM pokemon WHERE user_id=? AND on_desktop=0 GROUP BY box", (uid,)))


def t_191(size):
    """1.9.1: 가득 찬 박스에 포켓몬이 계속 들어가던 문제 (제보).

    새로 얻은 포켓몬이 늘 0번 박스로 갔다 - 30마리가 차도, 다른 박스에 자리가
    있어도. 운영에서 39명이 한 박스에 최대 202마리를 담고 있었다.
    """
    from app import battle_routes, deps, migrations
    from common import pokelogic as P
    import random
    print("\n=== 새로 얻은 포켓몬은 자리 있는 박스로 (1.9.1) ===")
    uid, ids = mkuser("가득", size)                  # 0번 박스가 꼭 찼다
    for slot in range(config.MAX_PARTY):            # 파티도 꽉 찼다
        db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, ability,"
               " hidden_ability, gender, shiny, happiness, ivs, evs, moves, on_desktop, slot,"
               " met_level, caught_at) VALUES (?,'EEVEE',5,0,'HARDY',NULL,0,'M',0,70,'{}','{}','[]',"
               "1,?,5,'')", (uid, slot))
    chk("0번 박스가 가득 (30)", counts(uid) == {0: size}, counts(uid))
    chk("자리 있는 박스는 1번", deps.box_for(uid) == 1, deps.box_for(uid))
    mon = P.make_pokemon(deps.dex().get("PIKACHU"), 5, random.Random(1), shiny_rate=10 ** 9)
    got, where = battle_routes.store_caught(uid, mon)
    chk("잡은 포켓몬이 박스로 가면 **1번 박스**에 들어간다", where == "box" and got["box"] == 1
        and counts(uid) == {0: size, 1: 1}, (where, got.get("box"), counts(uid)))
    for _ in range(3):
        battle_routes.store_caught(uid, dict(mon))
    chk("계속 잡아도 0번은 30마리 그대로", counts(uid) == {0: size, 1: 4}, counts(uid))
    # 1번 박스도 채우면 2번으로
    db.run("UPDATE pokemon SET box=1 WHERE id IN (SELECT id FROM pokemon WHERE user_id=?"
           " AND on_desktop=0 AND box=0 LIMIT 0)", (uid,))
    for _ in range(size - 4):
        battle_routes.store_caught(uid, dict(mon))
    got, _w = battle_routes.store_caught(uid, dict(mon))
    chk("1번도 차면 2번으로", got["box"] == 2 and counts(uid) == {0: size, 1: size, 2: 1}, counts(uid))
    # 가운데 박스에 빈 자리가 생기면 거기부터
    one = db.q1("SELECT id FROM pokemon WHERE user_id=? AND on_desktop=0 AND box=0 LIMIT 1", (uid,))["id"]
    db.run("DELETE FROM pokemon WHERE id=?", (one,))
    got, _w = battle_routes.store_caught(uid, dict(mon))
    chk("번호가 낮은 박스의 빈 자리부터 채운다", got["box"] == 0, got["box"])

    print("\n=== 데리고 다니던 포켓몬을 거둘 때 ===")
    desk = db.q1("SELECT id FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY slot LIMIT 1", (uid,))["id"]
    db.run("UPDATE pokemon SET box=0 WHERE id=?", (desk,))     # 원래 0번 박스에 있던 애
    r = main.set_desktop(desk, main.DesktopIn(on=False), ctx(uid))
    chk("원래 박스가 찼으면 자리 있는 박스로 간다 (0번에 31마리가 되지 않는다)",
        r["pokemon"]["box"] == 2 and counts(uid)[0] == size, (r["pokemon"]["box"], counts(uid)))
    desk2 = db.q1("SELECT id FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY slot LIMIT 1", (uid,))["id"]
    db.run("UPDATE pokemon SET box=2 WHERE id=?", (desk2,))
    r = main.set_desktop(desk2, main.DesktopIn(on=False), ctx(uid))
    chk("원래 박스에 자리가 있으면 그 박스로 돌아간다", r["pokemon"]["box"] == 2, r["pokemon"]["box"])
    # 자기 자신은 세지 않는다
    solo, sids = mkuser("혼자", size)
    chk("자기를 뺀 수로 센다 (30마리 중 하나를 다시 넣어도 그 박스)",
        deps.box_for(solo, prefer=0, exclude=sids[0]) == 0 and deps.box_for(solo, prefer=0) == 1)

    print("\n=== 알에서 태어날 때 ===")
    from app import eggs
    def party():
        return db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=? AND on_desktop=1", (uid,))["c"]
    n0, p0 = sum(counts(uid).values()), party()
    eggs._make_mon(uid, "MEW", random.Random(2), "2026-10-04T00:00:00+00:00")
    chk("파티에 자리가 있으면 파티로 태어난다", p0 < config.MAX_PARTY and party() == p0 + 1
        and sum(counts(uid).values()) == n0, (p0, party()))
    while party() < config.MAX_PARTY:                # 파티를 다시 꽉 채운다
        eggs._make_mon(uid, "MEW", random.Random(3), "2026-10-04T00:00:00+00:00")
    n0 = sum(counts(uid).values())
    eggs._make_mon(uid, "MEW", random.Random(4), "2026-10-04T00:00:00+00:00")
    n1 = counts(uid)
    chk("파티가 찼으면 자리 있는 박스로 태어난다", sum(n1.values()) == n0 + 1
        and all(v <= size for v in n1.values()), n1)

    print("\n=== 이미 넘친 박스 풀기 (한 번 도는 손질) ===")
    # 운영에서 본 모양 둘: ① 박스를 나눠 쓰는데 0번만 넘친 사람 ② 전부 0번에 든 사람
    a, a_ids = mkuser("넘침", 0)
    for box, n in ((0, 58), (1, size), (2, 29), (3, size)):
        for _ in range(n):
            db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, ability,"
                   " hidden_ability, gender, shiny, happiness, ivs, evs, moves, on_desktop, slot,"
                   " met_level, caught_at, box) VALUES (?,'PIKACHU',5,0,'HARDY',NULL,0,'M',0,70,"
                   "'{}','{}','[]',0,NULL,5,'',?)", (a, box))
    first30 = [r["id"] for r in db.q("SELECT id FROM pokemon WHERE user_id=? AND box=0 ORDER BY id LIMIT ?", (a, size))]
    b, _ = mkuser("한박스", 202)
    desk_id = db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, ability,"
                     " hidden_ability, gender, shiny, happiness, ivs, evs, moves, on_desktop, slot,"
                     " met_level, caught_at, box) VALUES (?,'EEVEE',5,0,'HARDY',NULL,0,'M',0,70,"
                     "'{}','{}','[]',1,0,5,'',0)", (a,)).lastrowid
    ok_user, _ = mkuser("멀쩡", 12)
    before_ok = boxes_of(ok_user)
    conn = db.connect()
    note = migrations._box_overflow(conn)
    conn.commit()
    ca, cb = counts(a), counts(b)
    chk("넘친 박스가 30마리가 된다", ca[0] == size and all(v <= size for v in ca.values()), ca)
    chk("넘친 28마리는 번호가 낮은 빈 자리부터 (2번에 1, 나머지는 4번)", ca == {0: size, 1: size, 2: size, 3: size, 4: 27}, ca)
    chk("먼저 들어온 30마리는 제 박스에 그대로", [r["id"] for r in db.q(
        "SELECT id FROM pokemon WHERE user_id=? AND box=0 AND on_desktop=0 ORDER BY id", (a,))] == first30)
    chk("전부 한 박스에 있던 사람은 30마리씩 나뉜다 (202마리 -> 7박스)",
        cb == {0: 30, 1: 30, 2: 30, 3: 30, 4: 30, 5: 30, 6: 22}, cb)
    chk("데리고 다니는 포켓몬은 건드리지 않는다",
        db.q1("SELECT on_desktop, slot, box FROM pokemon WHERE id=?", (desk_id,))["on_desktop"] == 1)
    chk("안 넘친 사람은 그대로", boxes_of(ok_user) == before_ok)
    chk("한 마리도 사라지지 않는다", sum(ca.values()) == 58 + size + 29 + size and sum(cb.values()) == 202)
    chk("몇 명·몇 마리를 옮겼는지 남긴다", "포켓몬" in note and "200" in note.replace("2명, 포켓몬 ", ""), note)
    note2 = migrations._box_overflow(conn)
    conn.commit()
    chk("두 번 돌려도 더 옮길 것이 없다", "0마리" in note2, note2)
    chk("손질 목록에 올라 있다", ("0310-box-overflow", migrations._box_overflow) in migrations.ONCE)


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

    t_191(size)

    print("\n=== 풀숲: 박스에 자리가 남았으면 돋는다 (보유 상한 = 박스 용량) ===")
    # 보유 상한이 박스가 생기기 전의 300 으로 남아 있었다. 300마리를 채운 사람은 박스가
    # 스물두 개 비어 있는데도 풀숲이 돋지 않았고, 까닭도 화면에 보이지 않았다.
    cap = config.BOX_SIZE * config.BOX_COUNT
    chk("보유 상한이 박스 용량과 같다 (30 x 32 = 960)", config.MAX_BOX == cap == 960, config.MAX_BOX)
    many, _ids = mkuser("many300", 300)
    r = main.wild_state({"user": {"id": many, "balls": 10}})
    chk("300마리를 가져도 풀숲이 돋는다", bool(r.get("wild")) and r["wild"].get("state") == "grass"
        and "boxFull" not in r, dict((k, r.get(k)) for k in ("wild", "boxFull", "nextInSeconds")))
    packed, _ids = mkuser("packed", cap)
    r = main.wild_state({"user": {"id": packed, "balls": 10}})
    chk("박스가 다 찼을 때만 안 돋고, 까닭과 다음 시각을 알린다", r.get("wild") is None
        and ("%d마리" % cap) in (r.get("boxFull") or {}).get("message", "") and r.get("nextInSeconds", 0) > 0,
        dict((k, r.get(k)) for k in ("wild", "boxFull", "nextInSeconds")))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
