# -*- coding: utf-8 -*-
"""Z기술 (시즌 4) · 테라스탈 (2.5.0) 의 계정 쪽 — Z링·테라오브, 테라 타입, Z크리스탈·테라피스.

    python server/test_gimmick.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다. 못 박는 것:

  1. Z링·테라오브는 **관장 8곳** (키스톤과 같다). 그 전에는 배틀에서 아무 일도 없다.
  2. 테라 타입: 정하지 않았으면 그 종의 첫째 타입. 테라피스를 쓰면 바뀌고 하나가 든다.
     이미 그 타입이면 안 쓴다 (가방에서 안 빠진다).
  3. Z크리스탈은 상점에서 사서 지니게 할 수 있다 (타입 20,000원, 전용 30,000원).
  4. 랜덤 배틀: 가진 사람만 AI 가 알아서 쓴다.
  5. 관장 배틀: 가진 사람에게만 단추가 뜨고, 눌러서 쓴다.
"""
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-gimmick-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                             # noqa: E402

from app import db, deps, gimmick, item_routes, items, main, pvp  # noqa: E402
from common import pokelogic as P                             # noqa: E402
from common import trainer_battle as TB                       # noqa: E402
from common import zmoves as ZM                               # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name, gyms=0, money=0):
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,?,'','','')",
        (name, b"x", b"x", money))
    uid = cur.lastrowid
    for i in range(gyms):
        db.run("INSERT INTO gym_clear (user_id, region, trainer, wins, best_turns,"
               " first_at, last_at) VALUES (?,?,?,1,5,'','')", (uid, "region_%d" % i, "t%d" % i))
    return uid


def mkmon(uid, species, moves, slot=0, held=None, level=50):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(1), shiny_rate=10 ** 9)
    m["moves"] = list(moves)
    pid = db.insert_mon(uid, m, "2026-01-01")
    db.run("UPDATE pokemon SET on_desktop=1, slot=?, held=? WHERE id=?", (slot, held, pid))
    return pid


def me(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def status_of(fn):
    try:
        fn()
    except HTTPException as e:
        return e.status_code
    return None


def main_():
    db.init()
    d = deps.dex()

    print("=== Z링·테라오브 ===")
    new, vet = mkuser("gm_new", gyms=7), mkuser("gm_vet", gyms=8)
    chk("관장 7곳이면 없다", not gimmick.has_zring(new) and not gimmick.has_orb(new))
    chk("관장 8곳이면 둘 다 있다", gimmick.has_zring(vet) and gimmick.has_orb(vet))
    chk("엔진에 넘기는 꼴", gimmick.flags(vet, new) == {"me": True, "foe": False}
        and gimmick.orbs(vet, new) == {"me": True, "foe": False}, (gimmick.flags(vet, new), gimmick.orbs(vet, new)))
    chk("  상대가 없으면 상대 쪽은 꺼진다", gimmick.orbs(vet) == {"me": True, "foe": False})
    c = gimmick.card(new)
    chk("화면에 줄 것: 몇 곳 남았나", c == {"zring": False, "teraOrb": False, "gyms": 7, "need": 8}, c)

    print("\n=== 테라 타입 ===")
    pid = mkmon(vet, "CHARIZARD", ("FLAMETHROWER", "AIRSLASH"))
    row = db.row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (pid,)))
    chk("새 포켓몬의 칸은 비어 있다", row["tera"] is None, row["tera"])
    dec = deps.decorate(row)
    chk("화면에는 그 종의 첫째 타입으로 간다",
        dec["teraType"] == "FIRE" and dec["teraKr"] == "불꽃" and dec["teraSet"] is False, dec.get("teraType"))
    chk("없는 타입은 거절", _raises(lambda: gimmick.set_tera(vet, pid, "STELLAR"), ValueError))
    chk("남의 포켓몬은 못 바꾼다", _raises(lambda: gimmick.set_tera(new, pid, "GRASS"), LookupError))
    chk("이미 그 타입이면 False (바뀐 것이 없다)", gimmick.set_tera(vet, pid, "FIRE") is False)
    chk("다른 타입이면 바뀐다", gimmick.set_tera(vet, pid, "grass") is True
        and db.q1("SELECT tera FROM pokemon WHERE id=?", (pid,))["tera"] == "GRASS")
    dec = deps.decorate(db.row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (pid,))))
    chk("바꾼 뒤의 화면 값", dec["teraType"] == "GRASS" and dec["teraKr"] == "풀" and dec["teraSet"] is True)

    print("\n=== 테라피스 ===")
    shards = [it for it in items.catalog().values() if (it.get("effect") or {}).get("kind") == "tera"]
    z_type = [it for it in items.catalog().values() if ZM.is_crystal(it["id"]) and it["cost"] == 20000]
    chk("테라피스 18종, 타입 Z크리스탈과 같은 20,000원 (팔면 10,000원)",
        len(shards) == 18 and all(it["cost"] == 20000 and it["sell"] == 10000 for it in shards) and len(z_type) == 18
        and set(it["effect"]["type"] for it in shards) == set(ZM.TYPE_Z), len(shards))
    chk("주워서는 안 나온다", all(not it.get("weight") and not it.get("chance") for it in shards))
    chk("설명이 있다", all(it.get("desc") for it in shards))
    items.bag_add(vet, "WATERTERASHARD", 2)
    out = item_routes.use(item_routes.UseIn(item="WATERTERASHARD", pokemon=pid), me=me(vet))
    chk("쓰면 테라 타입이 바뀐다", out["pokemon"]["teraType"] == "WATER" and "물" in out["message"], out["message"])
    chk("하나가 든다", items.bag_count(vet, "WATERTERASHARD") == 1)
    code = status_of(lambda: item_routes.use(item_routes.UseIn(item="WATERTERASHARD", pokemon=pid), me=me(vet)))
    chk("이미 그 타입이면 거절하고", code == 400, code)
    chk("테라피스는 그대로 남는다", items.bag_count(vet, "WATERTERASHARD") == 1)
    pid2 = mkmon(vet, "BLASTOISE", ("SURF",), slot=1)
    code = status_of(lambda: item_routes.use(item_routes.UseIn(item="WATERTERASHARD", pokemon=pid2), me=me(vet)))
    chk("정하지 않은 포켓몬에게 그 종의 첫째 타입 테라피스도 거절 (거북왕에게 물)", code == 400, code)
    code = status_of(lambda: item_routes.use(item_routes.UseIn(item="FIRETERASHARD", pokemon=pid), me=me(vet)))
    chk("가방에 없으면 못 쓴다", code == 400, code)
    # 두 창에서 같은 포켓몬에 쓰는 경우 (2.5.0): 테라피스를 먼저 빼고, 못 바꾸면 돌려준다
    items.bag_add(vet, "ICETERASHARD", 1)
    real_set = gimmick.set_tera
    gimmick.set_tera = lambda *a: False           # 앞 창이 먼저 바꿔 버렸다
    try:
        code = status_of(lambda: item_routes.use(item_routes.UseIn(item="ICETERASHARD", pokemon=pid), me=me(vet)))
    finally:
        gimmick.set_tera = real_set
    chk("못 바꾸면 거절하고 테라피스를 돌려준다", code == 400 and items.bag_count(vet, "ICETERASHARD") == 1,
        (code, items.bag_count(vet, "ICETERASHARD")))
    real_q1 = gimmick.db.q1

    def stale_q1(sql, args=()):
        row = real_q1(sql, args)                   # 이 창이 읽은 뒤에
        db.run("UPDATE pokemon SET tera='ROCK' WHERE id=?", (pid2,))   # 다른 창이 먼저 바꿨다
        return row
    gimmick.db.q1 = stale_q1
    try:
        got = gimmick.set_tera(vet, pid2, "GHOST")
    finally:
        gimmick.db.q1 = real_q1
    chk("조건을 건 UPDATE: 읽은 뒤 다른 창이 바꿨으면 False 이고 덮어쓰지 않는다",
        got is False and db.q1("SELECT tera FROM pokemon WHERE id=?", (pid2,))["tera"] == "ROCK", got)

    print("\n=== Z크리스탈 ===")
    zs = [it for it in items.catalog().values() if ZM.is_crystal(it["id"])]
    chk("Z크리스탈 32종 (타입 18 + 전용 14)", len(zs) == 32 and sum(1 for it in zs if it.get("zType")) == 18,
        len(zs))
    chk("타입 20,000원 · 전용 30,000원",
        all(it["cost"] == (20000 if it.get("zType") else 30000) for it in zs))
    pub = dict((x["id"], x) for x in items.public_list())
    chk("상점에서 팔고 지닐 수 있다 (분류는 'zcrystal' - 지닌 도구 121종의 표와 따로다)",
        pub["FIRIUMZ"]["buyable"] and pub["FIRIUMZ"]["holdable"] and pub["FIRIUMZ"]["cat"] == "zcrystal"
        and pub["FIRIUMZ"]["effect"] == {"kind": "held"}, pub["FIRIUMZ"])
    chk("무엇을 하는지 적혀 있다", "Z기술" in pub["FIRIUMZ"]["heldNote"] and pub["FIRIUMZ"]["desc"],
        pub["FIRIUMZ"]["heldNote"])
    chk("도구 그림이 다 있다", all(os.path.exists(os.path.join(HERE, "data", "item_sprites", it["id"] + ".png"))
                              for it in zs + shards))
    rich = mkuser("gm_rich", gyms=8, money=50000)
    rp = mkmon(rich, "CHARIZARD", ("FLAMETHROWER", "AIRSLASH"))
    item_routes.buy(item_routes.BuyIn(item="FIRIUMZ", count=1), me=me(rich))
    chk("사면 돈이 든다", items.money(rich) == 30000 and items.bag_count(rich, "FIRIUMZ") == 1, items.money(rich))
    out = main.hold(rp, main.HoldIn(item="FIRIUMZ"), ctx=me(rich))
    chk("지니게 할 수 있다", out["pokemon"]["held"] == "FIRIUMZ" and out["pokemon"]["heldKr"] == "불꽃Z"
        and items.bag_count(rich, "FIRIUMZ") == 0, out["pokemon"].get("held"))

    print("\n=== 랜덤 배틀: 가진 사람만 AI 가 쓴다 ===")
    poor = mkuser("gm_poor", gyms=0)
    pp = mkmon(poor, "VENUSAUR", ("ENERGYBALL", "SLUDGEBOMB"), held="GRASSIUMZ")
    db.run("UPDATE pokemon SET tera='GRASS' WHERE id=?", (pp,))
    db.run("UPDATE pokemon SET tera='FIRE' WHERE id=?", (rp,))
    r = pvp.run_match(rich, poor, kind="random", seed=5)
    ev = pvp.match_view(rich, r["matchId"])["events"]
    who_z = [e["who"] for e in ev if e.get("t") == "zpower"]
    who_t = [e["who"] for e in ev if e.get("t") == "tera"]
    chk("관장 8곳인 쪽은 Z기술을 쓴다", who_z == ["me"], who_z)
    chk("관장 8곳인 쪽은 테라스탈한다", who_t == ["me"], who_t)
    chk("상대 화면에서는 뒤집혀 보인다",
        [e["who"] for e in pvp.match_view(poor, r["matchId"])["events"] if e.get("t") == "zpower"] == ["foe"])
    mkmon(new, "SNORLAX", ("BODYSLAM",))
    r2 = pvp.run_match(poor, new, kind="friend", seed=5)
    ev2 = pvp.match_view(poor, r2["matchId"])["events"]
    chk("둘 다 없으면 아무 일도 없다 (크리스탈을 지녔어도)",
        not any(e.get("t") in ("zpower", "tera") for e in ev2))

    print("\n=== 관장 배틀: 단추와 누르기 ===")
    trainer = {"id": "t", "name": "시험", "role": "관장", "sprite": "x", "level": 50,
               "team": [{"species": "SNORLAX", "level": 50, "moves": ["TACKLE"], "iv": 31, "evs": {},
                         "nature": "HARDY", "ability": "IMMUNITY", "held": None, "gender": "M"}]}
    mons = [db.row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (rp,)))]
    tb = TB.TrainerBattle(d, mons, trainer, random.Random(4))
    tb.start()
    g = tb.view()["gimmick"]
    chk("안 가졌으면 단추가 없다", g["canTera"] is None and g["zMoves"] == [], g)
    tb = TB.TrainerBattle(d, mons, trainer, random.Random(4))
    tb.zring["me"], tb.tera_orb["me"] = gimmick.has_zring(rich), gimmick.has_orb(rich)
    tb.start()
    g = tb.view()["gimmick"]
    chk("가졌으면 뜬다", g["canTera"] == "FIRE" and [z["key"] for z in g["zMoves"]] == ["FLAMETHROWER"], g)
    tb = TB.TrainerBattle.load(d, json.loads(json.dumps(tb.dump())))
    ev = tb.act("move", "FLAMETHROWER", tera=True, z=True)
    kinds = [e.get("t") for e in ev]
    chk("저장했다 불러온 판에서 눌러도 나간다", "tera" in kinds and "zpower" in kinds, kinds)
    g = TB.TrainerBattle.load(d, json.loads(json.dumps(tb.dump()))).view()["gimmick"]
    chk("쓴 것이 저장된다", g["teraUsed"] and g["zUsed"] and g["canTera"] is None and g["zMoves"] == [], g)
    chk("관장은 쓰지 않는다", not any(e.get("who") == "foe" and e.get("t") in ("tera", "zpower") for e in ev))

    print("\n" + "=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


def _raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception:                                         # noqa: BLE001
        return False
    return False


if __name__ == "__main__":
    sys.exit(main_())
