# -*- coding: utf-8 -*-
"""노력치 한 번에 맞추기 검사 (2.1.3, 게시판 #450): POST /api/pokemon/{pid}/evs. 서버를 띄우지 않는다.

    python server/test_ev_plan.py

못 박는 것:

  1. 도구는 items.json 의 효과로 찾는다: 능력마다 영양제(+10) · 깃털(+1) · 열매(-10).
  2. 올리기: 10씩은 영양제, 나머지는 깃털. 내리기: 열매를 목표 이하가 될 때까지, 모자란 만큼 깃털로 다시 올린다.
     내리는 능력 먼저 - 510 을 꽉 채운 채 옮겨도 도중에 막히지 않는다.
  3. 목표 확인: 능력마다 0~252, 총합 510, 정수만, 없는 능력 · 빈 목표는 거절.
  4. 가진 것 먼저 (영양제 → 깃털), 남은 것만 산다. 가진 깃털을 먼저 써도 값은 같고 살 것만 준다.
  5. dry 는 아무것도 안 바꾼다. 모자란데 buy=false 면 409, 돈이 모자라면 400, 앱이 물어본 값(cost)과
     다르면 409 - 모두 그대로.
  6. **값은 하나씩 사서 쓸 때와 똑같다** (같은 계획을 상점 사기 + 도구 쓰기로 돌려 돈 · 노력치 · 가방을 맞대 본다).
  7. 배틀 중 · 남의 포켓몬 · 바꿀 것 없음은 거절. 도중에 어긋나면(그사이 노력치 · 가방이 바뀜) 통째로 되돌린다.
"""
import datetime
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="poket-evplan-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_HOUSEKEEP"] = "0"

from fastapi import HTTPException                                # noqa: E402

from app import db, item_routes, items                          # noqa: E402

OK = FAIL = 0
ZERO = {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def iso(sec=0):
    t = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=sec)
    return t.replace(microsecond=0).isoformat()


def mkuser(name, money=0):
    return db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login, last_ip)"
                  " VALUES (?, x'00', x'00', 1, 10, ?, ?, ?, '')", (name, money, iso(), iso())).lastrowid


def mkmon(uid, evs=None):
    return db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, ability, hidden_ability, gender, shiny,"
                  " happiness, ivs, evs, moves, on_desktop, slot, met_level, caught_at)"
                  " VALUES (?,'PIKACHU',50,0,'HARDY',NULL,0,'M',0,70,?,?,?,0,NULL,5,'')",
                  (uid, json.dumps({}), json.dumps(dict(ZERO, **(evs or {}))), json.dumps(["TACKLE"]))).lastrowid


def me(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def evs_of(pid):
    return json.loads(db.q1("SELECT evs FROM pokemon WHERE id=?", (pid,))["evs"])


def money(uid):
    return items.money(uid)


def call(uid, pid, evs, buy=False, dry=True):
    try:
        return item_routes.set_evs(pid, item_routes.EvsIn(evs=evs, buy=buy, dry=dry), me(uid)), None
    except HTTPException as e:
        return None, (e.status_code, e.detail)


def lines(r):
    return dict((ln["item"], (ln["count"], ln["owned"], ln["buy"])) for ln in (r or {}).get("plan") or [])


def bag_ev(uid):
    ids = set(item_routes.ev_items().values())
    return dict((k, v) for k, v in items.bag_get(uid).items() if k in ids)


def catalog():
    print("-- 1. 도구는 효과로 찾는다")
    ids = item_routes.ev_items()
    chk("능력마다 +10 · +1 · -10 하나씩 (18가지)", len(ids) == 18
        and all((s, a) in ids for s in items.STATS for a in (10, 1, -10)), sorted(ids))
    chk("  공격: 타우린 · 근력깃털 · 시마열매", (ids[("atk", 10)], ids[("atk", 1)], ids[("atk", -10)])
        == ("PROTEIN", "MUSCLEWING", "KELPSYBERRY"), ids.get(("atk", 10)))
    chk("  값: 10,000원 · 1,000원 · 80원", (items.buy_price("PROTEIN"), items.buy_price("MUSCLEWING"),
                                         items.buy_price("KELPSYBERRY")) == (10000, 1000, 80))
    got = [(sorted(r.methods), r.path) for r in item_routes.router.routes
           if getattr(r, "path", "") == "/api/pokemon/{pid}/evs"]
    chk("  길: POST /api/pokemon/{pid}/evs", got == [(["POST"], "/api/pokemon/{pid}/evs")], got)


def plans():
    print("-- 2. 계획")
    p = item_routes.ev_plan(dict(ZERO), dict(ZERO, atk=25), {})
    chk("0 -> 25: 영양제 둘 + 깃털 다섯 (전부 산다)", [(x["item"], x["count"], x["owned"], x["buy"]) for x in p]
        == [("PROTEIN", 2, 0, 2), ("MUSCLEWING", 5, 0, 5)], p)
    p = item_routes.ev_plan(dict(ZERO, atk=252), dict(ZERO, atk=100), {})
    chk("252 -> 100: 열매 16개(92까지) + 깃털 8개", [(x["item"], x["count"]) for x in p]
        == [("KELPSYBERRY", 16), ("MUSCLEWING", 8)], p)
    p = item_routes.ev_plan(dict(ZERO, atk=252), dict(ZERO, atk=0), {})
    chk("252 -> 0: 열매 26개 (0 아래로는 안 간다), 깃털 없음", [(x["item"], x["count"]) for x in p]
        == [("KELPSYBERRY", 26)], p)
    p = item_routes.ev_plan(dict(ZERO, atk=100), dict(ZERO, atk=95), {})
    chk("100 -> 95: 열매 하나 + 깃털 다섯", [(x["item"], x["count"]) for x in p]
        == [("KELPSYBERRY", 1), ("MUSCLEWING", 5)], p)
    full = dict(ZERO, hp=252, atk=252, spe=6)
    want = dict(ZERO, hp=252, atk=6, spe=252)
    p = item_routes.ev_plan(full, want, {})
    chk("510 을 꽉 채운 채 공격 -> 스피드: 내리기(공격) 먼저", [x["stat"] for x in p] == ["atk", "atk", "spe", "spe"],
        [(x["stat"], x["item"], x["count"]) for x in p])
    chk("  하나씩 쓸 때와 똑같이 돌려도 막힘 없이 목표에 닿는다", item_routes.ev_simulate(full, p) == want,
        item_routes.ev_simulate(full, p))
    chk("  거꾸로(올리기 먼저) 돌리면 510 에 막힌다 - 차례가 중요하다",
        item_routes.ev_simulate(full, [x for x in p if x["amount"] > 0] + [x for x in p if x["amount"] < 0]) is None)
    p = item_routes.ev_plan(dict(ZERO), dict(ZERO, atk=25), {"PROTEIN": 1, "MUSCLEWING": 13})
    chk("가진 것 먼저: 영양제 1 + 깃털 13 을 쓰고 깃털 2 개만 산다", [(x["item"], x["count"], x["owned"], x["buy"])
                                                    for x in p] == [("PROTEIN", 1, 1, 0), ("MUSCLEWING", 15, 13, 2)], p)
    p = item_routes.ev_plan(dict(ZERO), dict(ZERO, atk=25), {"PROTEIN": 5, "MUSCLEWING": 9})
    chk("  영양제가 넉넉하면 영양제 둘 + 깃털 다섯 (남는 것은 안 쓴다)",
        [(x["item"], x["count"], x["owned"], x["buy"]) for x in p]
        == [("PROTEIN", 2, 2, 0), ("MUSCLEWING", 5, 5, 0)], p)
    chk("그대로면 빈 계획", item_routes.ev_plan(dict(ZERO, hp=4), dict(ZERO, hp=4), {}) == [])


def targets():
    print("-- 3. 목표 확인")
    uid = mkuser("목표", 10 ** 7)
    pid = mkmon(uid, {"hp": 200, "atk": 200})
    for evs, why in (({"atk": 253}, "253"), ({"atk": -1}, "음수"), ({"spe": 111}, "총합 511"),
                     ({"luck": 4}, "없는 능력"), ({"atk": True}, "참/거짓"), ({"atk": "10"}, "글자"),
                     ({"atk": 4.5}, "소수"), ({}, "빈 목표")):
        r, err = call(uid, pid, evs)
        chk("%s: 거절 (400)" % why, r is None and err and err[0] == 400, err)
    r, err = call(uid, pid, {"spe": 110})
    chk("총합 딱 510 은 된다", r and r["evs"]["spe"] == 110 and sum(r["evs"].values()) == 510, err)
    r, err = call(uid, pid, {"ATK": 0})
    chk("능력 이름은 대소문자 안 가린다 · 안 적은 능력은 그대로", r and r["evs"] == dict(ZERO, hp=200), err)


def dry_and_apply():
    print("-- 4. 미리 보기 · 쓰기")
    uid = mkuser("쓰기", 30000)
    pid = mkmon(uid)
    items.bag_add(uid, "PROTEIN", 1)
    items.bag_add(uid, "MUSCLEWING", 13)
    r, err = call(uid, pid, {"atk": 25})
    chk("dry: 계획 · 살 개수 · 값 · 살 수 있나", r and r["dry"] and lines(r) == {"PROTEIN": (1, 1, 0),
                                                                     "MUSCLEWING": (15, 13, 2)}
        and r["buyCount"] == 2 and r["cost"] == 2000 and r["affordable"] and r["count"] == 16, (r, err))
    chk("  줄마다 이름 · 능력 이름 · 값", r and r["plan"][0]["kr"] == items.name_of("PROTEIN")
        and r["plan"][0]["statKr"] == "공격" and r["plan"][1]["price"] == 1000, r and r["plan"])
    chk("  dry 는 아무것도 안 바꾼다", evs_of(pid) == ZERO and money(uid) == 30000
        and bag_ev(uid) == {"PROTEIN": 1, "MUSCLEWING": 13}, (evs_of(pid), money(uid), bag_ev(uid)))
    r, err = call(uid, pid, {"atk": 25}, buy=False, dry=False)
    chk("모자란데 buy=false 면 409, 그대로", r is None and err[0] == 409 and "2개" in err[1]
        and evs_of(pid) == ZERO and money(uid) == 30000 and bag_ev(uid) == {"PROTEIN": 1, "MUSCLEWING": 13}, err)
    try:
        r, err = item_routes.set_evs(pid, item_routes.EvsIn(evs={"atk": 25}, buy=True, dry=False, cost=1000),
                                     me(uid)), None
    except HTTPException as e:
        r, err = None, (e.status_code, e.detail)
    chk("앱이 확인받은 값(cost)과 다르면 409, 그대로 (그사이 가방이 바뀌었다)", r is None and err[0] == 409
        and "2,000원" in err[1] and evs_of(pid) == ZERO and money(uid) == 30000, err)
    try:
        r, err = item_routes.set_evs(pid, item_routes.EvsIn(evs={"atk": 25}, buy=True, dry=False, cost=2000),
                                     me(uid)), None
    except HTTPException as e:
        r, err = None, (e.status_code, e.detail)
    chk("buy=true: 가진 것을 쓰고 모자란 둘만 산다", r and evs_of(pid)["atk"] == 25 and money(uid) == 28000
        and bag_ev(uid) == {}, (err, evs_of(pid), money(uid), bag_ev(uid)))
    chk("  답: 노력치 · 지갑 · 꾸민 포켓몬 · 말", r and r["evs"]["atk"] == 25 and r["money"] == 28000
        and "bag" in r and r["pokemon"]["info"]["evs"]["atk"] == 25 and "노력치" in r["message"]
        and "2,000원" in r["message"], r and r.get("message"))
    r, err = call(uid, pid, {"atk": 25}, dry=False)
    chk("바꿀 것이 없으면 400", r is None and err[0] == 400 and "없습니다" in err[1], err)

    u2 = mkuser("돈없음", 9000)
    p2 = mkmon(u2)
    r, err = call(u2, p2, {"spe": 10})
    chk("dry: 돈이 모자라면 affordable=false", r and r["cost"] == 10000 and not r["affordable"], r)
    r, err = call(u2, p2, {"spe": 10}, buy=True, dry=False)
    chk("돈이 모자라면 400, 그대로", r is None and err[0] == 400 and "10,000원" in err[1]
        and money(u2) == 9000 and evs_of(p2) == ZERO, err)

    u3 = mkuser("다있음", 0)
    p3 = mkmon(u3, {"def": 40})
    items.bag_add(u3, "QUALOTBERRY", 3)
    items.bag_add(u3, "RESISTWING", 2)
    r, err = call(u3, p3, {"def": 12}, dry=False)
    chk("다 가진 것이면 buy 없이 되고 돈은 0 그대로", r and evs_of(p3)["def"] == 12 and money(u3) == 0
        and bag_ev(u3) == {} and r["buyCount"] == 0, (err, evs_of(p3), bag_ev(u3)))


def same_cost():
    print("-- 5. 하나씩 쓸 때와 같은 값")
    start = {"hp": 252, "atk": 100, "def": 0, "spa": 37, "spd": 0, "spe": 121}
    want = {"hp": 0, "atk": 252, "def": 6, "spa": 0, "spd": 99, "spe": 153}
    a = mkuser("한번에", 10 ** 6)
    b = mkuser("하나씩", 10 ** 6)
    pa, pb = mkmon(a, start), mkmon(b, start)
    for u in (a, b):
        items.bag_add(u, "PROTEIN", 3)
        items.bag_add(u, "POMEGBERRY", 7)
        items.bag_add(u, "ZINC", 2)
    r, err = call(a, pa, want, buy=True, dry=False)
    chk("한 번에 맞췄다", r and evs_of(pa) == want, err)
    # 같은 계획을 하나씩: 모자란 것은 상점에서 사고 /api/bag/use 로 하나씩 쓴다
    for ln in (r or {}).get("plan") or []:
        if ln["buy"]:
            item_routes.buy(item_routes.BuyIn(item=ln["item"], count=ln["buy"]), me(b))
        for _ in range(ln["count"]):
            item_routes.use(item_routes.UseIn(item=ln["item"], pokemon=pb), me(b))
    chk("  하나씩 쓴 쪽도 같은 노력치", evs_of(pb) == want, evs_of(pb))
    chk("  쓴 돈이 같다 (%s원)" % format(10 ** 6 - money(a), ","), money(a) == money(b) and r["cost"] == 10 ** 6 - money(a),
        (money(a), money(b), r and r["cost"]))
    chk("  남은 가방이 같다", bag_ev(a) == bag_ev(b), (bag_ev(a), bag_ev(b)))


def refused():
    print("-- 6. 막는 것 · 되돌리기")
    uid = mkuser("배틀", 10 ** 6)
    pid = mkmon(uid)
    wid = db.run("INSERT INTO wild (user_id, state, species, data, created_at, expires_at)"
                 " VALUES (?,'revealed','PIKACHU','{}',?,?)", (uid, iso(-10), iso(600))).lastrowid
    db.run("INSERT INTO battle (user_id, wild_id, mine_id, state, me, foe, created_at, expires_at)"
           " VALUES (?,?,?,'active','{}','{}',?,?)", (uid, wid, pid, iso(-10), iso(600)))
    r, err = call(uid, pid, {"atk": 10}, buy=True, dry=False)
    chk("배틀 중이면 거절", r is None and err[0] == 400 and "배틀" in err[1] and evs_of(pid) == ZERO, err)
    other = mkuser("남", 10 ** 6)
    op = mkmon(other)
    r, err = call(uid, op, {"atk": 10}, buy=True, dry=False)
    chk("남의 포켓몬은 '없다' (404), 그대로", r is None and err[0] == 404 and evs_of(op) == ZERO
        and money(uid) == 10 ** 6, err)

    # 계획을 짠 뒤 다른 창에서 노력치가 바뀌었다 -> 409, 돈 · 가방 그대로
    u2 = mkuser("겹침", 50000)
    p2 = mkmon(u2)
    items.bag_add(u2, "CARBOS", 1)
    real = items.bag_get

    def sneaky(u, *a, **k):
        db.run("UPDATE pokemon SET evs=? WHERE id=?", (json.dumps(dict(ZERO, hp=4)), p2))
        return real(u, *a, **k)
    items.bag_get = sneaky
    try:
        r, err = call(u2, p2, {"spe": 30}, buy=True, dry=False)
    finally:
        items.bag_get = real
    chk("그사이 노력치가 바뀌면 409 · 덮어쓰지 않는다 · 돈 · 가방 되돌림", r is None and err[0] == 409
        and evs_of(p2) == dict(ZERO, hp=4) and money(u2) == 50000 and bag_ev(u2) == {"CARBOS": 1}, err)

    # 가방이 그사이 줄었다 (돈은 먼저 빠진 뒤) -> 409, 돈도 되돌린다
    u3 = mkuser("가방줄음", 50000)
    p3 = mkmon(u3)
    items.bag_add(u3, "CARBOS", 1)
    real_m = items.money

    def drain(u):
        db.run("UPDATE bag SET count=0 WHERE user_id=? AND item='CARBOS'", (u,))
        return real_m(u)
    items.money = drain
    try:
        r, err = call(u3, p3, {"spe": 30}, buy=True, dry=False)
    finally:
        items.money = real_m
    chk("그사이 가방이 줄면 409 · 먼저 뺀 돈도 되돌린다", r is None and err[0] == 409 and money(u3) == 50000
        and evs_of(p3) == ZERO, (err, money(u3)))
    r, err = call(u3, p3, {"spe": 30}, buy=True, dry=False)
    chk("  다시 하면 된다 (트랜잭션이 남아 잠그지 않는다)", r and evs_of(p3)["spe"] == 30 and money(u3) == 20000,
        (err, money(u3)))


def main_():
    db.init()
    catalog()
    plans()
    targets()
    dry_and_apply()
    same_cost()
    refused()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
