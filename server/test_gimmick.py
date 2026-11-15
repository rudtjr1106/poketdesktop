# -*- coding: utf-8 -*-
"""Z기술 (시즌 4) · 테라스탈 (2.5.0) 의 계정 쪽 — Z링·테라오브, 테라 타입, Z크리스탈·테라피스.

    python server/test_gimmick.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다. 못 박는 것:

  1. Z링·테라오브는 **관장 8곳** (키스톤과 같다). 그 전에는 배틀에서 아무 일도 없다.
  2. 테라 타입 = 지닌 테라피스의 타입 (2.5.1, 지니는 도구). 안 지녔으면 없다 - 테라스탈 못 한다.
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

    print("\n=== 테라 타입 = 지닌 테라피스 (2.5.1) ===")
    pid = mkmon(vet, "CHARIZARD", ("FLAMETHROWER", "AIRSLASH"))
    dec = deps.decorate(db.row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (pid,))))
    chk("테라피스를 안 지녔으면 테라 타입이 없다 - 화면에 '없음' (11/16 사용자, 처음 판은 그 종의 첫째 타입)",
        dec["teraType"] is None and dec["teraKr"] == "없음" and dec["teraSet"] is False, (dec.get("teraType"), dec.get("teraKr")))
    fairy = mkmon(vet, "CLEFABLE", ("MOONBLAST",), slot=1, held="FAIRYTERASHARD")
    dec = deps.decorate(db.row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (fairy,))))
    chk("페어리 테라피스를 지닌 픽시는 테라 타입 페어리 (페어리 포켓몬에 페어리)",
        dec["teraType"] == "FAIRY" and dec["teraKr"] == "페어리" and dec["teraSet"] is True, dec.get("teraType"))
    orb = mkmon(vet, "GYARADOS", ("WATERFALL",), slot=2, held="LIFEORB")
    db.run("UPDATE pokemon SET tera='WATER' WHERE id=?", (orb,))      # 2.5.0 처음 판에 가방에서 정해 둔 칸
    dec = deps.decorate(db.row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (orb,))))
    chk("다른 도구를 지녔으면 없다 - 2.5.0 에 정해 둔 칸(pokemon.tera)은 이제 안 본다", dec["teraType"] is None, dec)

    print("\n=== 테라피스 (지니는 도구) ===")
    shards = [it for it in items.catalog().values() if it.get("teraType")]
    z_type = [it for it in items.catalog().values() if ZM.is_crystal(it["id"]) and it["cost"] == 20000]
    chk("테라피스 18종, 타입 Z크리스탈과 같은 20,000원 (팔면 10,000원)",
        len(shards) == 18 and all(it["cost"] == 20000 and it["sell"] == 10000 for it in shards) and len(z_type) == 18
        and set(it["teraType"] for it in shards) == set(ZM.TYPE_Z), len(shards))
    chk("지닌 도구 칸 · 지니는 도구 (가방에서 쓰는 도구가 아니다)",
        all(it["cat"] == "held" and it["effect"] == {"kind": "held"} for it in shards))
    chk("주워서는 안 나온다", all(not it.get("weight") and not it.get("chance") for it in shards))
    chk("설명이 있다", all(it.get("desc") for it in shards))
    pub = dict((x["id"], x) for x in items.public_list())
    chk("상점에서 팔고 지닐 수 있고, 하는 일이 덧말로 붙는다",
        pub["FAIRYTERASHARD"]["buyable"] and pub["FAIRYTERASHARD"]["holdable"]
        and "테라스탈" in (pub["FAIRYTERASHARD"]["heldNote"] or ""), pub["FAIRYTERASHARD"])
    from common import held as HELD
    chk("뺏기지도 떨어지지도 않는다 (트릭 · 탁쳐서떨구기 - Z크리스탈과 같다)",
        all(HELD.stuck(it["id"]) for it in shards))
    items.bag_add(vet, "WATERTERASHARD", 1)
    items.bag_add(vet, "FAIRYTERASHARD", 1)
    out = main.hold(pid, main.HoldIn(item="WATERTERASHARD"), ctx=me(vet))
    chk("지니게 하면 테라 타입이 그 타입 (리자몽에게 물)", out["pokemon"]["teraType"] == "WATER"
        and items.bag_count(vet, "WATERTERASHARD") == 0, out["pokemon"].get("teraType"))
    out = main.hold(pid, main.HoldIn(item="FAIRYTERASHARD"), ctx=me(vet))
    chk("다른 테라피스로 바꿔 지니면 그 타입 · 먼저 것은 가방으로", out["pokemon"]["teraType"] == "FAIRY"
        and items.bag_count(vet, "WATERTERASHARD") == 1 and items.bag_count(vet, "FAIRYTERASHARD") == 0,
        (out["pokemon"].get("teraType"), items.bag_count(vet, "WATERTERASHARD")))
    out = main.hold(pid, main.HoldIn(item="FAIRYTERASHARD"), ctx=me(vet))
    chk("같은 것을 또 지니게 하면 그대로", out["pokemon"]["teraType"] == "FAIRY" and "이미" in out.get("message", ""),
        out.get("message"))
    chk("가방에서 '쓰는' 길은 없다 (2.5.0 처음 판의 쓰기)",
        status_of(lambda: item_routes.use(item_routes.UseIn(item="WATERTERASHARD", pokemon=pid), me=me(vet))) == 400)

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
    r = pvp.run_match(rich, poor, kind="random", seed=5)
    ev = pvp.match_view(rich, r["matchId"])["events"]
    who_z = [e["who"] for e in ev if e.get("t") == "zpower"]
    who_t = [e["who"] for e in ev if e.get("t") == "tera"]
    chk("관장 8곳인 쪽은 Z기술을 쓴다", who_z == ["me"], who_z)
    chk("테라피스를 안 지녔으면 테라오브가 있어도 테라스탈하지 않는다 (Z크리스탈을 지녔다)", who_t == [], who_t)
    chk("상대 화면에서는 뒤집혀 보인다",
        [e["who"] for e in pvp.match_view(poor, r["matchId"])["events"] if e.get("t") == "zpower"] == ["foe"])
    db.run("UPDATE pokemon SET held='FIRETERASHARD' WHERE id=?", (rp,))
    r = pvp.run_match(rich, poor, kind="random", seed=5)
    who_t = [e["who"] for e in pvp.match_view(rich, r["matchId"])["events"] if e.get("t") == "tera"]
    chk("테라피스를 지니면 관장 8곳인 쪽은 테라스탈한다", who_t == ["me"], who_t)
    db.run("UPDATE pokemon SET held='FIRIUMZ' WHERE id=?", (rp,))
    mkmon(new, "SNORLAX", ("BODYSLAM",))
    r2 = pvp.run_match(poor, new, kind="friend", seed=5)
    ev2 = pvp.match_view(poor, r2["matchId"])["events"]
    chk("둘 다 없으면 아무 일도 없다 (크리스탈을 지녔어도)",
        not any(e.get("t") in ("zpower", "tera") for e in ev2))

    print("\n=== 관장 배틀: 단추와 누르기 ===")
    trainer = {"id": "t", "name": "시험", "role": "관장", "sprite": "x", "level": 50,
               "team": [{"species": "SNORLAX", "level": 50, "moves": ["TACKLE"], "iv": 31, "evs": {},
                         "nature": "HARDY", "ability": "IMMUNITY", "held": None, "gender": "M"}]}
    mons = [db.row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (rp,)))]       # 불꽃Z 를 지녔다
    tb = TB.TrainerBattle(d, mons, trainer, random.Random(4))
    tb.start()
    g = tb.view()["gimmick"]
    chk("안 가졌으면 단추가 없다", g["canTera"] is None and g["zMoves"] == [], g)
    tb = TB.TrainerBattle(d, mons, trainer, random.Random(4))
    tb.zring["me"], tb.tera_orb["me"] = gimmick.has_zring(rich), gimmick.has_orb(rich)
    tb.start()
    g = tb.view()["gimmick"]
    chk("Z크리스탈을 지녔으면 Z기술 단추만 (테라피스가 없어 테라스탈 단추는 없다)",
        g["canTera"] is None and [z["key"] for z in g["zMoves"]] == ["FLAMETHROWER"], g)
    tb = TB.TrainerBattle.load(d, json.loads(json.dumps(tb.dump())))
    ev = tb.act("move", "FLAMETHROWER", z=True)
    chk("저장했다 불러온 판에서 Z기술을 눌러도 나간다", "zpower" in [e.get("t") for e in ev], [e.get("t") for e in ev])
    chk("관장은 쓰지 않는다", not any(e.get("who") == "foe" and e.get("t") in ("tera", "zpower") for e in ev))
    tmon = dict(mons[0], held="FIRETERASHARD")
    tb = TB.TrainerBattle(d, [tmon], trainer, random.Random(4))
    tb.zring["me"], tb.tera_orb["me"] = gimmick.has_zring(rich), gimmick.has_orb(rich)
    tb.start()
    g = tb.view()["gimmick"]
    chk("테라피스를 지녔으면 테라스탈 단추 (지닌 테라피스의 타입) · Z기술은 없다",
        g["canTera"] == "FIRE" and g["zMoves"] == [], g)
    tb = TB.TrainerBattle.load(d, json.loads(json.dumps(tb.dump())))
    ev = tb.act("move", "FLAMETHROWER", tera=True)
    chk("저장했다 불러온 판에서 테라스탈을 눌러도 나간다", "tera" in [e.get("t") for e in ev], [e.get("t") for e in ev])
    g = TB.TrainerBattle.load(d, json.loads(json.dumps(tb.dump()))).view()["gimmick"]
    chk("쓴 것이 저장된다", g["teraUsed"] and g["canTera"] is None, g)

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
