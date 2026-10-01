# -*- coding: utf-8 -*-
"""메가진화 서버 검사 (시즌 3) — 키스톤과 유대 미션.

    python server/test_mega.py

  1. 키스톤은 관장 8곳. 7곳이면 없다.
  2. 빛나는 돌은 데리고 다니고 + 친밀도 255 + 키스톤 + 아직 없는 스톤이 있을 때.
  3. 미션 셋(타입 관장·KO 30·야생 10)을 다 채우면 끝.
     스톤이 하나뿐인 종은 저절로 받고, X/Y 는 골라서 받는다.
  4. **두 번 받지 못한다.** 한 종의 스톤은 계정에 하나씩.
  5. 메가스톤을 지닐 수 있다 (held.normalize 가 버리지 않는다).
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-mega-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import db, deps, items, mega                        # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name, gyms=0):
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')",
        (name, b"x", b"x"))
    uid = cur.lastrowid
    for i in range(gyms):
        db.run("INSERT INTO gym_clear (user_id, region, trainer, wins, best_turns,"
               " first_at, last_at) VALUES (?,?,?,1,5,'','')",
               (uid, "region_%d" % i, "t%d" % i))
    return uid


def mkmon(uid, species, happiness=255, on=1, held=None):
    cur = db.run(
        "INSERT INTO pokemon (user_id, species, level, exp, nature, ability,"
        " hidden_ability, gender, shiny, happiness, ivs, evs, moves,"
        " on_desktop, slot, met_level, caught_at, held)"
        " VALUES (?,?,50,0,'HARDY',NULL,0,'M',0,?,'{}','{}','[\"TACKLE\"]',?,0,5,'',?)",
        (uid, species, happiness, on, held))
    return cur.lastrowid


def bond(pid):
    return db.q1("SELECT * FROM bond WHERE pokemon_id=?", (pid,))


def finish(uid, pid, gym_type):
    mega.on_gym_win(uid, [pid], gym_type)
    for _ in range(mega.BOND_KOS):
        mega.on_ko(uid, pid)
    for _ in range(mega.BOND_WILD):
        mega.on_catch(uid)


def main():
    db.init()
    deps.dex()                    # 메가스톤을 held 에 알린다

    print("=== 키스톤 ===")
    u7 = mkuser("일곱", gyms=7)
    u8 = mkuser("여덟", gyms=8)
    chk("관장 7곳이면 없다", not mega.has_keystone(u7))
    chk("관장 8곳이면 있다", mega.has_keystone(u8))
    chk("몇 곳 남았는지 알려준다", mega.keystone_card(u7) == {"has": False, "gyms": 7, "need": 8},
        mega.keystone_card(u7))

    print("\n=== 빛나는 돌 ===")
    liz = mkmon(u8, "CHARIZARD")
    low = mkmon(u8, "GENGAR", happiness=254)
    box = mkmon(u8, "GENGAR", on=0)
    pika = mkmon(u8, "PIKACHU")
    r = mega.ready(u8)
    chk("255 + 데리고 다님 + 메가 종이면 뜬다", liz in r, r)
    chk("254 면 아직", low not in r)
    chk("박스에 있으면 안 뜬다", box not in r)
    chk("메가가 없는 종은 안 뜬다", pika not in r)
    liz7 = mkmon(u7, "CHARIZARD")
    chk("키스톤이 없으면 안 뜬다", mega.ready(u7) == [])
    try:
        mega.start(u7, liz7)
        chk("키스톤 없이 시작 못 한다", False, "시작됐다")
    except ValueError:
        chk("키스톤 없이 시작 못 한다", True)

    print("\n=== 미션 ===")
    card = mega.start(u8, liz)
    chk("시작하면 미션 셋", len(card["missions"]) == 3 and card["started"], card)
    chk("리자몽의 타입 관장은 불꽃 또는 비행", "불꽃" in card["missions"][0]["text"]
        and "비행" in card["missions"][0]["text"], card["missions"][0]["text"])
    chk("시작하면 빛나는 돌은 사라진다", liz not in mega.ready(u8))
    mega.on_gym_win(u8, [liz], "WATER")
    chk("타입이 안 맞는 관장은 안 센다", bond(liz)["gym"] == 0)
    mega.on_gym_win(u8, [liz], "FLYING")
    chk("두 번째 타입(비행) 관장도 센다", bond(liz)["gym"] == 1)
    for _ in range(mega.BOND_KOS - 1):
        mega.on_ko(u8, liz)
    for _ in range(mega.BOND_WILD):
        mega.on_catch(u8)
    chk("하나라도 모자라면 아직", bond(liz)["done_at"] is None,
        dict(bond(liz)))
    mega.on_ko(u8, liz)
    b = bond(liz)
    chk("다 채우면 끝", b["done_at"] is not None, dict(b))
    chk("X/Y 는 저절로 안 준다", b["stone"] is None
        and not items.bag_get(u8).get("CHARIZARDITEX"))
    card = mega.card(u8, liz)
    chk("받을 수 있다고 알린다", card["claimable"] and set(card["missing"]) ==
        {"CHARIZARDITEX", "CHARIZARDITEY"}, card)
    chk("/api/me 에 받을 스톤이 실린다", liz in mega.me_card(u8)["claim"])
    mega.claim(u8, liz, "CHARIZARDITEX")
    chk("고른 스톤이 가방에", items.bag_get(u8).get("CHARIZARDITEX") == 1)
    try:
        mega.claim(u8, liz, "CHARIZARDITEY")
        chk("두 번 못 받는다", False, "또 받았다")
    except ValueError:
        chk("두 번 못 받는다", True)

    print("\n=== 두 번째 리자몽은 나머지 스톤 ===")
    liz2 = mkmon(u8, "CHARIZARD")
    chk("아직 Y 가 없으니 뜬다", liz2 in mega.ready(u8))
    mega.start(u8, liz2)
    finish(u8, liz2, "FIRE")
    chk("남은 게 하나면 저절로 받는다", items.bag_get(u8).get("CHARIZARDITEY") == 1
        and bond(liz2)["stone"] == "CHARIZARDITEY", dict(bond(liz2)))
    got = mega.me_card(u8)["got"]
    chk("저절로 받은 스톤은 /api/me 로 알린다", [g["pokemon"] for g in got] == [liz2]
        and got[0]["stoneKr"] == "리자몽나이트Y" and got[0]["name"] == "리자몽", got)
    chk("  직접 고른 X 는 알릴 것에 없다 (이미 봤다)",
        liz not in [g["pokemon"] for g in got])
    mega.mark_seen(u8, liz2)
    chk("  알렸다고 하면 빠진다", mega.me_card(u8)["got"] == [], mega.me_card(u8)["got"])
    chk("카드에 이름이 실린다 (알림 창용)", mega.card(u8, liz2)["name"] == "리자몽")
    liz3 = mkmon(u8, "CHARIZARD")
    chk("둘 다 있으면 더는 안 뜬다", liz3 not in mega.ready(u8))
    try:
        mega.start(u8, liz3)
        chk("둘 다 있으면 시작도 못 한다", False)
    except ValueError:
        chk("둘 다 있으면 시작도 못 한다", True)

    print("\n=== 스톤 하나짜리 · 지니고 있어도 가진 것 ===")
    gen = mkmon(u8, "GENGAR")
    mega.start(u8, gen)
    finish(u8, gen, "GHOST")
    chk("팬텀나이트를 저절로 받는다", items.bag_get(u8).get("GENGARITE") == 1)
    # 가방에서 꺼내 누가 지니고 있어도 '가진 것' 이다
    items.bag_take(u8, "GENGARITE", 1)
    db.run("UPDATE pokemon SET held='GENGARITE' WHERE id=?", (low,))
    gen2 = mkmon(u8, "GENGAR")
    chk("지니고 있는 스톤도 가진 것으로 친다", gen2 not in mega.ready(u8))

    print("\n=== 지닐 수 있다 ===")
    from common import held as H
    chk("held.normalize 가 메가스톤을 버리지 않는다", H.normalize("gengarite") == "GENGARITE")
    chk("이름도", H.name("GENGARITE") == "팬텀나이트", H.name("GENGARITE"))
    chk("레쿠쟈는 스톤이 없다 (화룡점정)", mega.stones_for("RAYQUAZA") == [])

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
