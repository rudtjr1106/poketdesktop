# -*- coding: utf-8 -*-
"""기술머신 — 자료, 소유, 배우기, 그리고 기다리는 기술.

여기서 못 박는 것은 다섯이다.

  1. **못 배우는 기술은 못 배운다.** 클라이언트를 믿으면 아무 포켓몬에게
     아무 기술이나 붙일 수 있다.
  2. **안 가진 기술머신은 못 쓴다.**
  3. **써도 없어지지 않는다.** 영구제라 개수를 깎지 않는다.
  4. **팔거나 살 수 없다.** 상점 목록에 아예 없다.
  5. 네 개가 차 있으면 **말없이 밀어내지 않는다.** 기다렸다 물어본다.

서버를 띄우지 않는다. DB 와 모듈만 직접 쓴다.
"""
import io
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-tm-")
os.environ.setdefault("POKET_DB", os.path.join(TMP, "t.db"))
os.environ.setdefault("POKET_POKEDEX", os.path.join(HERE, "data", "pokedex.json"))

from app import db, deps, items, tms                       # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name):
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,?,?,'')",
        (name, b"x", b"x", "2026-01-01", "2026-01-01"))
    return cur.lastrowid


def mkmon(uid, species, moves, level=50):
    return db.insert_mon(uid, {
        "species": species, "level": level, "exp": 0, "nature": "HARDY",
        "ability": "OVERGROW", "hiddenAbility": False, "gender": "M",
        "shiny": False, "happiness": 70, "ivs": {}, "evs": {},
        "moves": list(moves), "hyper": {}, "noEvolve": False,
        "luxury": False, "held": None}, "2026-01-01")


def main():
    db.init()
    d = deps.dex()

    print("=== 자료 ===")
    n = tms.count()
    chk("기술머신이 358개", n == 358, n)
    chk("1번이 있다", tms.get(1) is not None)
    chk("없는 번호는 None", tms.get(9999) is None)
    t1 = tms.get(1)
    chk("기술 내부이름이 도감에 있다", t1["move"] in d.moves, t1["move"])
    bad = [no for no, t in tms.all_tms().items() if t["move"] not in d.moves]
    chk("358개가 전부 도감에 있는 기술", not bad, bad[:5])
    chk("이름이 읽을 만하다", tms.label(1).startswith("기술머신001"), tms.label(1))

    print("\n=== 누가 배울 수 있나 ===")
    # 이상해씨(1) 는 배울 게 많고, 메타몽(132) 은 하나도 못 배운다.
    chk("이상해씨는 배울 게 있다", len(tms.learnable(1)) > 10,
        len(tms.learnable(1)))
    chk("메타몽은 하나도 못 배운다", tms.learnable(132) == [],
        tms.learnable(132))
    chk("모르는 종은 빈 목록", tms.learnable(99999) == [])
    some = tms.learnable(1)[0]
    chk("배울 수 있다고 나온다", tms.can_learn(1, some))
    cant = [n for n in range(1, 359) if n not in set(tms.learnable(1))]
    chk("못 배우는 것은 못 배운다고 나온다", not tms.can_learn(1, cant[0]))

    print("\n=== 갖고 있는가 ===")
    uid = mkuser("tm_a")
    chk("처음에는 하나도 없다", tms.owned(uid) == set())
    chk("주면 True", tms.give(uid, 5) is True)
    chk("갖고 있다", tms.has(uid, 5))
    chk("또 주면 False (두 번 세지 않는다)", tms.give(uid, 5) is False)
    chk("여전히 하나", tms.owned(uid) == {5}, tms.owned(uid))

    print("\n=== 상점에 안 뜬다 ===")
    shop = items.public_list()
    ids = set(x["id"] for x in shop)
    tmish = [i for i in ids if i.upper().startswith("TM")]
    chk("도구 목록에 기술머신이 없다", not tmish, tmish[:5])
    chk("드랍표에도 없다",
        not [i for i, _w in items.data()["dropTable"]
             if i.upper().startswith("TM")])

    print("\n=== 배우기 ===")
    from app import tm_routes as R

    class Body(object):
        def __init__(self, **kw):
            self.__dict__.update(kw)

    me = {"user": {"id": uid}}
    # 이상해씨가 배울 수 있는 것 하나를 고른다
    no = tms.learnable(1)[0]
    tms.give(uid, no)
    mv = tms.get(no)["move"]

    pid = mkmon(uid, "BULBASAUR", ["TACKLE"])
    r = R.use(Body(no=no, pokemon=pid, forget=""), me)
    chk("자리가 있으면 그냥 배운다", r["ok"] and mv in r["moves"], r)
    chk("기술이 두 개가 됐다", len(r["moves"]) == 2, r["moves"])

    # 써도 없어지지 않는다
    chk("쓴 뒤에도 갖고 있다 (영구제)", tms.has(uid, no))

    # 같은 것을 또
    try:
        R.use(Body(no=no, pokemon=pid, forget=""), me)
        ok = False
    except Exception as e:
        ok = "이미" in str(e)
    chk("이미 아는 기술은 막는다", ok)

    print("\n=== 네 개가 차 있으면 물어본다 ===")
    pid2 = mkmon(uid, "BULBASAUR", ["TACKLE", "GROWL", "VINEWHIP", "GROWTH"])
    r = R.use(Body(no=no, pokemon=pid2, forget=""), me)
    chk("바로 안 배우고 물어본다",
        r.get("needForget") is True and not r.get("ok"), r)
    row = db.q1("SELECT moves FROM pokemon WHERE id=?", (pid2,))
    chk("아직 안 바뀌었다", json.loads(row["moves"]) == [
        "TACKLE", "GROWL", "VINEWHIP", "GROWTH"], row["moves"])

    r = R.use(Body(no=no, pokemon=pid2, forget="GROWL"), me)
    chk("고른 것을 잊고 배운다",
        r["ok"] and mv in r["moves"] and "GROWL" not in r["moves"], r["moves"])
    chk("여전히 네 개", len(r["moves"]) == 4, r["moves"])
    chk("고르지 않은 것은 그대로",
        "TACKLE" in r["moves"] and "VINEWHIP" in r["moves"], r["moves"])

    try:
        R.use(Body(no=no, pokemon=pid2, forget="NOSUCHMOVE"), me)
        ok = False
    except Exception:
        ok = True
    chk("갖고 있지 않은 기술은 못 잊는다", ok)

    print("\n=== 서버가 막아야 하는 것 ===")
    # 안 가진 기술머신
    notmine = [n for n in range(1, 359) if n not in tms.owned(uid)][0]
    try:
        R.use(Body(no=notmine, pokemon=pid, forget=""), me)
        ok = False
    except Exception as e:
        ok = "갖고 있지" in str(e)
    chk("안 가진 기술머신은 못 쓴다", ok)

    # 그 종이 못 배우는 기술
    cant_no = [n for n in range(1, 359)
               if not tms.can_learn(1, n)][0]
    tms.give(uid, cant_no)
    try:
        R.use(Body(no=cant_no, pokemon=pid, forget=""), me)
        ok = False
    except Exception as e:
        ok = "배울 수 없" in str(e)
    chk("그 종이 못 배우는 기술은 막는다", ok)

    # 남의 포켓몬
    other = mkuser("tm_b")
    opid = mkmon(other, "BULBASAUR", ["TACKLE"])
    try:
        R.use(Body(no=no, pokemon=opid, forget=""), me)
        ok = False
    except Exception:
        ok = True
    chk("남의 포켓몬에는 못 쓴다", ok)

    print("\n=== 레벨업: 말없이 밀어내지 않는다 ===")
    sp = d.get("BULBASAUR")
    pid3 = mkmon(uid, "BULBASAUR", ["TACKLE", "GROWL", "VINEWHIP", "GROWTH"],
                 level=1)
    moves, learned, pending = deps._learn(
        sp, ["TACKLE", "GROWL", "VINEWHIP", "GROWTH"], 1, 50, [])
    chk("기술은 그대로 네 개", len(moves) == 4, moves)
    chk("아무것도 안 잊었다",
        moves == ["TACKLE", "GROWL", "VINEWHIP", "GROWTH"], moves)
    chk("배울 것이 기다린다", len(pending) > 0, pending)
    chk("방금 배운 것은 없다", learned == [], learned)

    # 자리가 있으면 그냥 배운다
    moves, learned, pending = deps._learn(sp, ["TACKLE"], 1, 50, [])
    chk("자리가 있으면 채운다", len(moves) == 4, moves)
    chk("배운 것을 알려준다", len(learned) == 3, learned)
    chk("네 개를 채운 뒤 남은 것은 기다린다", len(pending) > 0, pending)

    # 같은 기술이 두 번 들어가지 않는다
    moves, learned, pending = deps._learn(sp, ["TACKLE"], 1, 50, [])
    chk("중복이 없다", len(set(moves)) == len(moves), moves)
    chk("기다리는 것에도 중복이 없다", len(set(pending)) == len(pending), pending)
    chk("기다리는 것이 이미 아는 기술이 아니다",
        not (set(pending) & set(moves)), (pending, moves))

    print("\n=== 기다리던 것 고르기 ===")
    db.run("UPDATE pokemon SET moves=?, pending=? WHERE id=?",
           (json.dumps(["TACKLE", "GROWL", "VINEWHIP", "GROWTH"]),
            json.dumps(["SOLARBEAM"]), pid3))
    r = R.learn(Body(pokemon=pid3, move="SOLARBEAM", forget="GROWL",
                     skip=False), me)
    chk("잊고 배운다",
        "SOLARBEAM" in r["moves"] and "GROWL" not in r["moves"], r["moves"])
    chk("기다리는 것이 비었다", r["pending"] == [], r["pending"])

    # 안 배우기
    db.run("UPDATE pokemon SET moves=?, pending=? WHERE id=?",
           (json.dumps(["TACKLE", "GROWL", "VINEWHIP", "GROWTH"]),
            json.dumps(["SOLARBEAM"]), pid3))
    r = R.learn(Body(pokemon=pid3, move="SOLARBEAM", forget="", skip=True), me)
    chk("안 배우면 기술이 그대로",
        r["moves"] == ["TACKLE", "GROWL", "VINEWHIP", "GROWTH"], r["moves"])
    chk("그래도 기다리는 목록에서는 빠진다", r["pending"] == [], r["pending"])

    try:
        R.learn(Body(pokemon=pid3, move="SOLARBEAM", forget="", skip=True), me)
        ok = False
    except Exception:
        ok = True
    chk("기다리지 않는 기술은 못 배운다", ok)

    print("\n=== 배울 수 있는 포켓몬을 한 번에 ===")
    # 마리마다 물어보면 예순 마리면 예순 번이다.
    r = R.learners(no, me)
    ids = [x["id"] for x in r["learners"]]
    chk("배울 수 있는 애만 나온다", pid in ids and pid2 in ids, ids)
    allmons = db.q("SELECT id FROM pokemon WHERE user_id=?", (uid,))
    chk("못 배우는 애는 빠진다", len(ids) <= len(allmons), (len(ids), len(allmons)))
    chk("이미 배웠는지 알려준다",
        any(x["known"] for x in r["learners"]), r["learners"][:2])
    chk("남의 포켓몬은 안 나온다", opid not in ids, ids)
    try:
        R.learners(9999, me)
        ok = False
    except Exception:
        ok = True
    chk("없는 번호는 막는다", ok)

    print("\n=== 드랍 ===")
    rng = random.Random(1)
    uid2 = mkuser("tm_c")
    got = [tms.roll_drop(rng, species_num=1, uid=uid2) for _ in range(4000)]
    hits = [g for g in got if g is not None]
    rate = len(hits) / 4000.0
    chk("확률이 설정값 근처 (%.3f)" % rate,
        abs(rate - tms.DROP_CHANCE) < 0.02, rate)
    allno = set(tms.all_tms())
    chk("358개 전체에서 나온다 (종으로 안 좁힌다)",
        all(h in allno for h in hits) and len(set(hits)) > 60,
        len(set(hits)))
    can = set(tms.learnable(1))
    chk("잡은 종이 못 배우는 것도 나온다",
        any(h not in can for h in hits))

    # 이미 가진 것은 안 나온다
    for h in set(hits):
        tms.give(uid2, h)
    again = [tms.roll_drop(rng, species_num=1, uid=uid2) for _ in range(2000)]
    dup = [g for g in again if g is not None and tms.has(uid2, g)]
    chk("이미 가진 것은 다시 안 나온다", not dup, dup[:5])

    # 다 모으면 안 나온다
    uid3 = mkuser("tm_d")
    for n in tms.all_tms():
        tms.give(uid3, n)
    full = [tms.roll_drop(rng, species_num=1, uid=uid3) for _ in range(500)]
    chk("다 모았으면 안 나온다", all(f is None for f in full))

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
