# -*- coding: utf-8 -*-
"""랭크 시즌 보상 도구 검사 (1.13.1): 기술머신 뽑기권.

    python server/test_tm_ticket.py

시즌 4 부터 1등(챔피언)은 타입 확정 기술머신 뽑기권 + 관장 등록, 2~5등(사천왕)은 랜덤 기술머신
뽑기권을 더 받는다 (2026-10-18 사용자 결정). 관장 등록은 도구가 아니다 - 운영자가 구글폼으로 따로
신청받는다. 못 박는 것:

  1. 도구 둘이 있고 상점 · 드랍 · 되팔기에 없다. 관장 등록권이라는 도구는 없다.
  2. 랭킹 화면의 보상 표에 그 자리마다 실린다 (season.rules_public) - 관장 등록은 글로만.
  3. 뽑기권은 **아직 없는 기술머신만** 준다. 타입 확정은 고른 타입에서만.
  4. 뽑을 것이 없거나 타입을 안 골랐거나 없는 타입이면 거절하고 **표는 그대로 남는다.**
  5. 받은 기술머신은 '새 기술머신' (노란 점) 이다.
  6. 상점 답에 타입마다 아직 없는 수(tmLeft)가 실린다 - 기술머신 뽑기권이 있을 때만.
  7. 거의 동시에 같은 기술머신을 받으면(다른 요청이 먼저 넣었다) 뽑기권은 돌려준다 - tms.give 가 실제로
     넣었는지로 답한다.
  8. 시즌을 닫을 때 넣는 선물 줄(item)로 실제로 가방에 들어온다.
"""
import datetime
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-tmticket-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                                # noqa: E402

from app import db, item_routes, items, season, tms              # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def mkuser(name):
    cur = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                 " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,?,?,'')",
                 (name, b"x", b"x", now(), now()))
    return cur.lastrowid


def me(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def use(uid, item, tm_type=""):
    """/api/bag/use 를 그대로 부른다. (답, 거절 문구)."""
    try:
        return item_routes.use(item_routes.UseIn(item=item, type=tm_type), me(uid)), None
    except HTTPException as e:
        return None, e.detail


def own_all_but(uid, keep):
    for no in tms.all_tms():
        if no not in keep:
            tms.give(uid, no)
    tms.mark_seen(uid)


def main():
    db.init()
    every = tms.all_tms()
    by_type = {}
    for no, t in every.items():
        by_type.setdefault(t["type"], []).append(no)

    print("=== 도구")
    for iid, kind in (("RANKTICKETTM", "tmticket"), ("RANKTICKETTMTYPE", "tmticket")):
        it = items.get(iid) or {}
        chk("%s (%s) 이 있다" % (iid, it.get("kr")), (it.get("effect") or {}).get("kind") == kind, it)
        chk("  상점 · 드랍 · 되팔기에 없다", not it.get("buyable") and not it.get("weight")
            and items.sell_price(iid) <= 0 and items.buy_price(iid) <= 0, it)
    chk("타입 확정만 타입을 고른다", items.get("RANKTICKETTMTYPE")["effect"].get("pickType")
        and not items.get("RANKTICKETTM")["effect"].get("pickType"))
    chk("이름은 사용자가 정한 대로",
        [items.get(i)["kr"] for i in ("RANKTICKETTM", "RANKTICKETTMTYPE")]
        == ["랜덤 기술머신 뽑기권", "타입 확정 기술머신 뽑기권"])
    chk("관장 등록권은 도구가 아니다 (구글폼으로 따로 신청)", items.get("GYMPASS") is None
        and not any((it.get("effect") or {}).get("kind") == "voucher" for it in items.catalog().values()))

    print("\n=== 랭킹 화면의 보상 표")
    rows = dict((r["tier"], r) for r in season.rules_public()["rewards"])
    ids = dict((t, [(i["id"], i["count"]) for i in r["items"]]) for t, r in rows.items())
    perks = dict((t, r["perks"]) for t, r in rows.items())
    chk("챔피언: 타입 확정 뽑기권 + 관장 등록(글로만)", ids["champion"] == [("RANKTICKETTMTYPE", 1)]
        and perks["champion"] == ["관장 등록"], (ids, perks))
    chk("사천왕: 랜덤 뽑기권 1개", ids["elite"] == [("RANKTICKETTM", 1)] and perks["elite"] == [], (ids, perks))
    chk("마스터볼 아래는 더 주는 것이 없다", ids["master"] == ids["hyper"] == ids["super"] == []
        and perks["master"] == perks["hyper"] == perks["super"] == [], (ids, perks))
    chk("  이름이 한글로 실린다", [i["kr"] for i in rows["champion"]["items"]] == ["타입 확정 기술머신 뽑기권"])
    chk("  알 · 칭호 · 이로치사탕은 그대로", rows["champion"]["egg"] == "전설의 포켓몬 알"
        and rows["elite"]["egg"] == "환상의 포켓몬 알" and rows["champion"]["shiny"] == 1)

    print("\n=== 랜덤 뽑기권")
    a = mkuser("뽑기가")
    keep = sorted(every)[:2]
    own_all_but(a, keep)
    items.bag_add(a, "RANKTICKETTM", 2)
    r, err = use(a, "RANKTICKETTM")
    got = (r or {}).get("tm", {}).get("no")
    chk("아직 없는 것 둘 중 하나가 나온다", err is None and got in keep, (err, r and r.get("tm")))
    chk("  실제로 가졌다 · 새 기술머신(노란 점)", got and tms.has(a, got) and got in tms.unseen(a))
    chk("  답에 '새 기술머신' 수 · 남은 표 · 문구", r and r.get("tmNew") == 1 and r["bag"].get("RANKTICKETTM") == 1
        and "얻었다" in r["message"] and tms.label(got) in r["message"], r and (r.get("tmNew"), r["message"]))
    r, err = use(a, "RANKTICKETTM")
    chk("남은 하나가 나온다", err is None and r["tm"]["no"] in keep and r["tm"]["no"] != got, (err, r))
    items.bag_add(a, "RANKTICKETTM", 1)
    r, err = use(a, "RANKTICKETTM")
    chk("다 모았으면 거절한다", r is None and "다 모아서" in (err or ""), err)
    chk("  표는 그대로 남는다", items.bag_count(a, "RANKTICKETTM") == 1, items.bag_count(a, "RANKTICKETTM"))

    print("\n=== 타입 확정 뽑기권")
    b = mkuser("타입가")
    fairy, fire = by_type["FAIRY"], by_type["FIRE"]
    for no in fairy + fire[:-3]:
        tms.give(b, no)
    items.bag_add(b, "RANKTICKETTMTYPE", 1)
    r, err = use(b, "RANKTICKETTMTYPE")
    chk("타입을 안 고르면 거절", r is None and "골라" in (err or ""), err)
    r, err = use(b, "RANKTICKETTMTYPE", "SHADOW")
    chk("없는 타입이면 거절", r is None and "없습니다" in (err or ""), err)
    r, err = use(b, "RANKTICKETTMTYPE", "FAIRY")
    chk("그 타입을 다 모았으면 거절 (한글 타입 이름으로)", r is None and "페어리" in (err or "")
        and "다 모았습니다" in (err or ""), err)
    chk("  거절하는 동안 표는 그대로", items.bag_count(b, "RANKTICKETTMTYPE") == 1)
    r, err = use(b, "RANKTICKETTMTYPE", "fire")
    chk("고른 타입 가운데 아직 없는 것이 나온다 (소문자도 받는다)", err is None and r["tm"]["no"] in fire[-3:]
        and r["tm"]["type"] == "FIRE", (err, r and r.get("tm")))
    chk("  표가 빠졌다", items.bag_count(b, "RANKTICKETTMTYPE") == 0)
    r, err = use(b, "RANKTICKETTMTYPE", "FIRE")
    chk("표가 없으면 거절", r is None and "없습니다" in (err or ""), err)

    print("\n=== 거의 동시에 받을 때")
    e = mkuser("동시가")
    last = sorted(every)[-1]
    own_all_but(e, [last])
    real_has, real_owned = tms.has, tms.owned
    tms.give(e, last)                       # 다른 요청(드랍 · 다른 PC 의 뽑기권)이 먼저 넣었다
    tms.has = lambda uid, no: False         # 이 요청은 그 전에 읽었다 (has · owned 를 지난 뒤에 끼어들었다)
    tms.owned = lambda uid: real_owned(uid) - {last}
    try:
        chk("tms.give: 이미 들어간 줄이면 False (넣은 것이 없다)", tms.give(e, last) is False)
        items.bag_add(e, "RANKTICKETTM", 1)
        r, err = use(e, "RANKTICKETTM")
        chk("뽑기권: 줄 기술머신이 없어졌으면 거절하고", r is None and "다 모아서" in (err or ""), err)
        chk("  뽑기권은 돌려준다", items.bag_count(e, "RANKTICKETTM") == 1, items.bag_count(e, "RANKTICKETTM"))
        items.bag_add(e, "RANKTICKETTMTYPE", 1)
        r, err = use(e, "RANKTICKETTMTYPE", every[last]["type"])
        chk("타입 확정도 돌려주고, 문구는 '그 타입'", r is None and "그 타입" in (err or "")
            and items.bag_count(e, "RANKTICKETTMTYPE") == 1, err)
    finally:
        tms.has, tms.owned = real_has, real_owned
    chk("새로 넣을 때는 True", tms.give(mkuser("처음가"), last) is True)

    print("\n=== 상점 답의 tmLeft")
    s = item_routes.shop(me(b))
    chk("뽑기권이 없으면 안 싣는다", "tmLeft" not in s, sorted(s))
    items.bag_add(b, "RANKTICKETTMTYPE", 1)
    s = item_routes.shop(me(b))
    left = s.get("tmLeft") or {}
    chk("있으면 타입마다 아직 없는 수", left.get("FIRE") == 2 and left.get("WATER") == len(by_type["WATER"]), left)
    chk("  다 모은 타입은 안 적는다", "FAIRY" not in left, left)
    c = mkuser("랜덤만")
    items.bag_add(c, "RANKTICKETTM", 1)
    chk("  랜덤 뽑기권만 있어도 싣는다 (다 모았는지 보려고)", "tmLeft" in item_routes.shop(me(c)))

    print("\n=== 시즌을 닫을 때 넣는 선물 줄로 받는다")
    d = mkuser("챔피언")
    for iid, n in season.S4_ITEMS["champion"]:
        db.run("INSERT INTO gift (user_id, kind, item_id, count, title, message, created_at)"
               " VALUES (?,?,?,?,?,?,?)", (d, "item", iid, n, "시즌 4 보상", "", now()))
    got = items.gift_claim(d)
    chk("선물로 가방에 들어온다", items.bag_count(d, "RANKTICKETTMTYPE") == 1, [(g["item"], g["name"]) for g in got])
    chk("  알림 이름이 한글", [g["name"] for g in got] == ["타입 확정 기술머신 뽑기권"], [g["name"] for g in got])
    try:
        item_routes.sell(item_routes.SellIn(item="RANKTICKETTMTYPE"), me(d))
        sold = True
    except HTTPException:
        sold = False
    chk("  뽑기권은 팔 수 없다", not sold and items.bag_count(d, "RANKTICKETTMTYPE") == 1)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
