# -*- coding: utf-8 -*-
"""탐험 파견 (1.10.4). 서버를 띄우지 않는다.

    python server/test_expedition.py

박스의 포켓몬을 몇 시간 보내 두면 도구를 가져온다 (server/app/expedition.py, 규칙은 common/expedition.py).

## 무엇을 못 박나

  1. 규칙: 성공도는 레벨과 타입으로만 정해진다. 길게·잘 보낼수록 물건이 많고 귀한 것이 잘 나온다.
     특산물로 적은 도구가 전부 실제로 있는 도구다. 열여덟 타입이 한 곳씩 맞는다.
  2. 보내기: 박스의 내 포켓몬만, 칸은 세 개. 데리고 다니는 것·이미 나간 것·랭크 팀에 든 것은 못 보낸다.
  3. **시간은 서버 시계로 흐른다.** 돌아오기 전에는 못 받는다.
  4. 받기: 물건이 가방에 들어간다. **같은 보따리를 두 번 못 받는다.** 받으면 칸이 빈다.
  5. 나가 있는 동안: 데리고 다닐 수 없다 (파티 갈아타기에서도 빠진다), 랭크 팀에 못 넣는다,
     놓아줄 수 없다. 포켓몬 목록에 '나가 있음' 이 실려 간다.
  6. 불러들이면 빈손이다. 돌아온 뒤에는 불러들일 수 없다 (받아야 한다).
  7. 굴리기: 물건 수가 규칙대로고, 등급 비율이 규칙에 가깝고, 특산물이 그곳에서 잘 나온다.
"""
import collections
import datetime
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-expedition-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                            # noqa: E402

from common import expedition as X                           # noqa: E402
from common import pokelogic as P                            # noqa: E402
from app import db, deps, expedition as E, items, main, party, pvp, tms   # noqa: E402

OK = FAIL = 0
T0 = datetime.datetime(2026, 10, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def later(**kw):
    return T0 + datetime.timedelta(**kw)


def mkuser(name):
    return db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')",
        (name, b"x", b"x")).lastrowid


def mkmon(uid, species, level, slot=None, nickname=None):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(3), shiny_rate=10 ** 9)
    m["noEvolve"] = True
    m["nickname"] = nickname
    pid = db.insert_mon(uid, m, "")
    if slot is not None:
        db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=?", (slot, pid))
    return pid


def ctx(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def refused(fn, *a, **kw):
    """거절됐으면 (상태 코드, 까닭), 아니면 None."""
    try:
        fn(*a, **kw)
    except HTTPException as e:
        return e.status_code, str(e.detail)
    except ValueError as e:
        return 400, str(e)
    return None


def bag(uid):
    return dict(items.bag_get(uid))


def main_():
    db.init()
    dex = deps.dex()
    cat = items.catalog()

    print("=== 규칙 ===")
    types = [t for p in X.PLACES for t in p["types"]]
    all_types = set(t for sp in dex.species for t in sp.get("types", []))
    chk("갈 곳이 여섯, 타입 열여덟이 한 곳씩 맞는다", len(X.PLACES) == 6 and len(types) == 18 == len(set(types))
        and set(types) == all_types, sorted(all_types - set(types)))
    loot_ids = [i for t in X.LOOT for i, _w in X.LOOT[t]]
    special_ids = [i for p in X.PLACES for t, ids in p["special"].items() for i in ids]
    missing = [i for i in loot_ids + special_ids if i not in cat]
    chk("탐험에서 나오는 것(전용 표 %d종 + 특산물)이 전부 있는 도구다" % len(set(loot_ids)), not missing
        and set(X.LOOT) == set(X.TIERS) - {"held"} and all(X.LOOT[t] for t in X.LOOT)
        and all(set(p["special"]) <= set(X.LOOT) for p in X.PLACES), missing)
    # **돈벌이가 되면 안 된다** (사용자 결정): 지닌 도구·팔기만 하는 물건은 안 나오고, 비싼 것도 없다.
    pricey = [(i, cat[i]["sell"]) for i in set(loot_ids + special_ids)
              if cat[i]["sell"] > 5000 or cat[i]["cat"] == "held" or (cat[i].get("effect") or {}).get("kind") == "sell"
              and i != "TINYMUSHROOM"]
    chk("  네 등급(평범~특별)에는 지닌 도구·금구슬 같은 것이 없다 (팔아서 5,000원이 넘는 것도 없다)", not pricey, pricey)
    top = dict((t, max(cat[i]["sell"] for i, _w in X.LOOT[t])) for t in X.LOOT)
    chk("  등급마다 팔았을 때의 값: 평범 250원 · 쓸만 500원 · 희귀 2,500원 · 특별 5,000원 안쪽",
        top["common"] <= 250 and top["uncommon"] <= 500 and top["rare"] <= 2500 and top["epic"] <= 5000
        and max(cat[i]["sell"] for i in special_ids) <= 2500, top)
    chk("성공도: Lv.75 에 타입이 맞으면 대성공, 안 맞으면 Lv.100 이어도 성공까지",
        X.grade_of(75, ["GRASS"], "forest") == "great" and X.grade_of(100, ["FIRE"], "forest") == "good"
        and X.grade_of(74, ["GRASS"], "forest") == "good" and X.grade_of(74, ["FIRE"], "forest") == "normal"
        and X.grade_of(25, ["GRASS"], "forest") == "good" and X.grade_of(24, ["GRASS"], "forest") == "normal",
        [X.score(75, ["GRASS"], "forest"), X.score(100, ["FIRE"], "forest")])
    chk("  두 타입이 다 맞으면 더 낮은 레벨로도 대성공 (풀·독 Lv.59)", X.grade_of(59, ["GRASS", "POISON"], "forest") == "great"
        and X.grade_of(58, ["GRASS", "POISON"], "forest") == "good" and X.matches(["GRASS", "GRASS"], "forest") == 1)
    chk("물건 수: 길수록, 잘할수록 많다", [X.item_count(h, g) for h in X.HOURS for g in X.GRADES] == [1, 1, 1, 1, 1, 2, 1, 2, 3])
    for h in X.HOURS:
        for g in X.GRADES:
            odds = X.tier_odds(h, g)
            if abs(sum(p for _t, p in odds) - 1.0) > 1e-9 or min(p for _t, p in odds) < 0:
                chk("등급 확률의 합이 1 (%d시간 %s)" % (h, g), False, odds)
    rare = lambda h, g: dict(X.tier_odds(h, g))["rare"] + dict(X.tier_odds(h, g))["epic"]   # noqa: E731
    chk("귀한 것은 길수록, 잘할수록 잘 나온다", rare(2, "normal") < rare(4, "normal") < rare(8, "normal") < rare(8, "good") < rare(8, "great")
        and rare(8, "great") < 0.2, [round(rare(h, g), 3) for h in X.HOURS for g in X.GRADES])
    chk("기술머신은 유적에서 잘 나온다", X.tm_chance(8, "great", "ruins") > X.tm_chance(8, "great", "forest") > X.tm_chance(2, "normal", "forest") > 0
        and X.tm_chance(8, "great", "ruins") <= 0.5, X.tm_chance(8, "great", "ruins"))
    chk("남은 시간을 사람 말로", [X.hours_text(s) for s in (0, 30, 60, 3599, 3600, 7260, 8 * 3600)]
        == ["돌아옴", "곧", "1분", "59분", "1시간", "2시간 1분", "8시간"], [X.hours_text(s) for s in (0, 30, 60, 3599, 3600, 7260)])

    print("\n=== 보내기 ===")
    uid = mkuser("탐험가")
    lead = mkmon(uid, "SNORLAX", 50, slot=0)
    bulba = mkmon(uid, "VENUSAUR", 80)                       # 풀·독 Lv.80 - 숲에서 대성공
    onix = mkmon(uid, "ONIX", 40)                            # 바위·땅 Lv.40 - 동굴에서 성공
    rat = mkmon(uid, "RATTATA", 10, nickname="꼬마")         # 노말 Lv.10 - 어디서든 보통
    pika = mkmon(uid, "PIKACHU", 30)
    other = mkuser("남")
    theirs = mkmon(other, "EEVEE", 20)
    st = E.state(uid, T0)
    chk("처음에는 세 칸이 다 비어 있다", st["slots"] == 3 and st["free"] == 3 and st["out"] == [] and st["ready"] == 0
        and st["nextIn"] is None and E.me_card(uid, T0) == {"out": 0, "ready": 0, "nextIn": None}, st)
    chk("없는 곳·없는 시간은 거절", refused(E.send, uid, bulba, "moon", 2, T0) and refused(E.send, uid, bulba, "forest", 3, T0)
        and refused(E.send, uid, bulba, "forest", "x", T0))
    chk("남의 포켓몬·없는 포켓몬은 거절", refused(E.send, uid, theirs, "forest", 2, T0) == (404, "그런 포켓몬이 없습니다.")
        and refused(E.send, uid, 99999, "forest", 2, T0)[0] == 404)
    why = refused(E.send, uid, lead, "forest", 2, T0)
    chk("데리고 다니는 포켓몬은 못 보낸다 (박스에 넣으라고 알린다)", why and why[0] == 409 and "박스" in why[1], why)
    pvp.set_team(uid, [pika])
    why = refused(E.send, uid, pika, "sea", 2, T0)
    chk("랭크 팀에 든 포켓몬은 못 보낸다", why and why[0] == 409 and "랭크 팀" in why[1], why)
    pvp.set_team(uid, [])
    out = E.send(uid, bulba, "forest", 8, T0)
    one = out["out"][0]
    chk("보냈다: 성공도는 보낼 때 정해진다 (이상해꽃 Lv.80 풀·독 -> 숲 = 대성공, 물건 3개)",
        out["ok"] and one["grade"] == "great" and one["gradeKr"] == "대성공" and one["score"] == 88 and one["items"] == 3
        and one["pokemon"]["id"] == bulba and one["pokemon"]["level"] == 80 and one["placeKr"] == "숲", one)
    chk("  8시간 뒤에 돌아온다 (남은 초로 알려 준다)", one["left"] == 8 * 3600 and one["total"] == 8 * 3600 and not one["ready"]
        and out["free"] == 2 and out["nextIn"] == 8 * 3600 and "8시간" in out["message"], (one["left"], out["message"]))
    why = refused(E.send, uid, bulba, "cave", 2, T0)
    chk("이미 나가 있으면 또 못 보낸다", why and why[0] == 409 and "이미" in why[1], why)
    E.send(uid, onix, "cave", 2, T0)
    E.send(uid, rat, "ruins", 4, T0)
    st = E.state(uid, T0)
    chk("세 칸을 다 썼다 (동굴의 롱스톤 = 성공, 유적의 꼬마 = 보통)", st["free"] == 0
        and [(o["place"], o["grade"], o["items"]) for o in st["out"]] == [("forest", "great", 3), ("cave", "good", 1), ("ruins", "normal", 1)]
        and st["out"][2]["pokemon"]["name"] == "꼬마" and st["nextIn"] == 2 * 3600, st["out"])
    why = refused(E.send, uid, pika, "sea", 2, T0)
    chk("칸이 꽉 차면 못 보낸다", why and why[0] == 409 and "꽉" in why[1], why)

    print("\n=== 나가 있는 동안 ===")
    chk("나가 있는 포켓몬", E.away_ids(uid) == {bulba, onix, rat} and E.is_away(uid, bulba) and not E.is_away(uid, pika))
    listing = main.list_pokemon(ctx(uid))["pokemon"]
    chk("포켓몬 목록에 '나가 있음' 이 실린다 (그 셋에만)", sorted(m["id"] for m in listing if m.get("away")) == sorted([bulba, onix, rat])
        and all("away" not in m for m in listing if m["id"] in (lead, pika)))
    why = refused(main.set_desktop, bulba, main.DesktopIn(on=True), ctx(uid))
    chk("**데리고 다닐 수 없다** (배틀에 못 나간다)", why and why[0] == 409 and "탐험" in why[1]
        and not db.q1("SELECT on_desktop FROM pokemon WHERE id=?", (bulba,))["on_desktop"], why)
    why = refused(main.release, onix, ctx(uid))
    chk("놓아줄 수 없다", why and why[0] == 409 and db.q1("SELECT id FROM pokemon WHERE id=?", (onix,)) is not None, why)
    why = refused(pvp.set_team, uid, [pika, rat])
    chk("랭크 팀에 넣을 수 없다", why and "탐험" in why[1] and pvp.set_team(uid, [pika]) == [pika], why)
    pvp.set_team(uid, [])
    # 파티 2번에 이상해꽃이 적혀 있다 -> 갈아타면 그 포켓몬만 빠진다
    party._write(uid, 2, [pika, bulba], False)
    r = party.use(uid, 2)
    chk("파티를 갈아타도 나가 있는 포켓몬은 안 나온다 (뺐다고 알린다)", party.desktop_ids(uid) == [pika]
        and "탐험" in r["message"] and "1마리" in r["message"], (party.desktop_ids(uid), r["message"]))
    party.use(uid, 1)
    chk("  원래 파티로 돌아온다", party.desktop_ids(uid) == [lead], party.desktop_ids(uid))

    print("\n=== 시간이 흐른다 (서버 시계) ===")
    why = refused(E.claim, uid, st["out"][1]["id"], later(hours=1, minutes=59))
    chk("돌아오기 전에는 못 받는다", why and why[0] == 409 and "아직" in why[1], why)
    st = E.state(uid, later(hours=1))
    chk("한 시간 뒤: 남은 시간이 줄었다", [o["left"] for o in st["out"]] == [7 * 3600, 3600, 3 * 3600] and st["ready"] == 0
        and st["nextIn"] == 3600 and E.me_card(uid, later(hours=1)) == {"out": 3, "ready": 0, "nextIn": 3600}, st["nextIn"])
    st = E.state(uid, later(hours=2))
    chk("두 시간 뒤: 동굴에서 돌아왔다 (나머지는 아직)", [o["ready"] for o in st["out"]] == [False, True, False] and st["ready"] == 1
        and st["nextIn"] == 2 * 3600 and st["free"] == 0 and E.me_card(uid, later(hours=2))["ready"] == 1, st["ready"])
    chk("  **돌아와도 받기 전까지는 '나가 있는' 것이다** (칸도 안 빈다)", E.is_away(uid, onix))
    why = refused(E.recall, uid, st["out"][1]["id"], later(hours=2))
    chk("  돌아온 뒤에는 불러들일 수 없다 (받아야 한다)", why and why[0] == 409 and "받아" in why[1], why)

    print("\n=== 받기 ===")
    before = bag(uid)
    tm_before = len(tms.owned(uid))
    got = E.claim(uid, st["out"][1]["id"], later(hours=2), rng=random.Random(5))
    one = got["claimed"][0]
    gained = dict((k, v - before.get(k, 0)) for k, v in bag(uid).items() if v != before.get(k, 0))
    n_items = sum(i["count"] for i in one["items"])
    chk("보따리를 받았다: 물건 %d개 (2시간 성공 = 1개)" % n_items, got["ok"] and len(got["claimed"]) == 1 and n_items == 1
        and one["pokemon"]["id"] == onix and one["placeKr"] == "동굴" and one["gradeKr"] == "성공", one)
    chk("  **가방에 그대로 들어갔다**", gained == dict((i["id"], i["count"]) for i in one["items"])
        and got["bag"] == bag(uid), (gained, one["items"]))
    chk("  물건마다 이름·등급이 실린다", all(i["kr"] == cat[i["id"]]["kr"] and i["tier"] in X.TIERS for i in one["items"]), one["items"])
    chk("  칸이 비고, 포켓몬이 돌아왔다", got["free"] == 1 and not E.is_away(uid, onix) and len(got["out"]) == 2
        and "away" not in next(m for m in main.list_pokemon(ctx(uid))["pokemon"] if m["id"] == onix))
    why = refused(E.claim, uid, st["out"][1]["id"], later(hours=2))
    chk("**같은 보따리를 두 번 못 받는다**", why and why[0] == 404 and bag(uid) == dict(got["bag"]), why)
    main.set_desktop(onix, main.DesktopIn(on=True), ctx(uid))
    chk("  돌아온 포켓몬은 다시 데리고 다닐 수 있다", db.q1("SELECT on_desktop FROM pokemon WHERE id=?", (onix,))["on_desktop"] == 1)
    row = db.q1("SELECT state, loot, claimed_at FROM expedition WHERE id=?", (st["out"][1]["id"],))
    chk("  기록이 남는다 (받은 것)", row["state"] == "done" and row["loot"] and row["claimed_at"], dict(row))

    none = E.claim(uid, None, later(hours=3))
    chk("돌아온 것이 없으면 '전부 받기' 는 아무것도 안 한다", none["claimed"] == [] and "아직" in none["message"] and len(none["out"]) == 2)
    before = bag(uid)
    allgot = E.claim(uid, None, later(hours=9), rng=random.Random(11))
    counts = dict((g["place"], sum(i["count"] for i in g["items"])) for g in allgot["claimed"])
    chk("**전부 받기** (바탕화면의 보따리): 숲 3개 + 유적 1개", counts == {"forest": 3, "ruins": 1} and allgot["free"] == 3
        and allgot["out"] == [] and E.away_ids(uid) == set(), counts)
    add = {}
    for g in allgot["claimed"]:
        for i in g["items"]:
            add[i["id"]] = add.get(i["id"], 0) + i["count"]
    now_bag = bag(uid)
    chk("  전부 가방에 들어갔다 (%d개)" % sum(add.values()), all(now_bag.get(k, 0) - before.get(k, 0) == v for k, v in add.items())
        and "받았습니다" in allgot["message"], add)
    tm_got = [g["tm"] for g in allgot["claimed"] + got["claimed"] if g["tm"]]
    chk("  기술머신을 얹어 왔으면 실제로 받았다", len(tms.owned(uid)) == tm_before + len(tm_got), (len(tms.owned(uid)), tm_got))

    print("\n=== 불러들이기 ===")
    out = E.send(uid, bulba, "forest", 4, later(hours=10))
    eid = out["out"][0]["id"]
    before = bag(uid)
    back = E.recall(uid, eid, later(hours=11))
    chk("불러들이면 빈손으로 돌아온다 (칸이 빈다)", back["ok"] and back["free"] == 3 and bag(uid) == before
        and not E.is_away(uid, bulba) and "빈손" in back["message"], back["message"])
    why = refused(E.claim, uid, eid, later(hours=20))
    chk("  불러들인 것은 받을 수 없다", why and why[0] == 404, why)
    why = refused(E.recall, uid, eid, later(hours=11))
    chk("  두 번 불러들일 수 없다", why and why[0] == 404, why)
    chk("남의 탐험은 건드릴 수 없다", refused(E.recall, other, eid, later(hours=11))[0] == 404
        and E.claim(other, None, later(hours=99))["claimed"] == [])

    print("\n=== 굴리기 ===")
    rng = random.Random(2026)
    pools = E.pools()
    chk("등급마다 뽑을 것이 있다 (탐험 전용 표)", all(len(pools[t]) >= 2 for t in X.TIERS)
        and all(pools[t] == [(i, float(w)) for i, w in X.LOOT[t]] for t in X.LOOT), dict((t, len(pools[t])) for t in X.TIERS))
    held_ids = [i for i, _w in pools["held"]]
    hw = float(sum(w for _i, w in pools["held"]))
    top_share = sum(w for i, w in pools["held"] if cat[i]["rarity"] == "epic") / hw
    chk("**'지닌 도구' 등급**: 야생에서 떨어지는 지닌 도구 가운데 흔하지 않은 것 (%d종)" % len(held_ids),
        len(held_ids) >= 60 and all(cat[i]["cat"] == "held" and cat[i]["rarity"] in X.HELD_RARITIES for i in held_ids)
        and "CHOICEBAND" in held_ids and "LIFEORB" in held_ids and "LEFTOVERS" in held_ids, len(held_ids))
    chk("  배틀용 열매(흔한 것)와 금구슬 같은 팔기만 하는 물건은 거기에도 없다",
        not [i for i in held_ids if cat[i]["rarity"] == "common" or (cat[i].get("effect") or {}).get("kind") == "sell"]
        and "ORANBERRY" not in held_ids and "NUGGET" not in held_ids and "BIGNUGGET" not in held_ids)
    chk("  구애 시리즈·생명의구슬 같은 것은 그 안에서도 드물다 (%.1f%%)" % (100 * top_share), top_share < 0.03, top_share)
    odds = dict((hg, dict(X.tier_odds(*hg))["held"]) for hg in ((2, "normal"), (4, "good"), (8, "normal"), (8, "great")))
    chk("  **정말 드물다**: 물건 하나가 지닌 도구일 확률 - 2시간 보통 %.1f%% · 8시간 대성공 %.1f%%"
        % (100 * odds[(2, "normal")], 100 * odds[(8, "great")]),
        0 < odds[(2, "normal")] <= 0.004 and odds[(2, "normal")] < odds[(4, "good")] < odds[(8, "great")] <= 0.02
        and odds[(8, "normal")] < odds[(8, "great")], odds)
    chk("  '특별' 은 병뚜껑뿐이다 (금색은 은색보다 드물다)", dict(pools["epic"]) == {"BOTTLECAP": 10.0, "GOLDBOTTLECAP": 2.0}, pools["epic"])
    n = 6000
    tiers = collections.Counter()
    wings = collections.Counter()
    ruins_rare = collections.Counter()
    for _i in range(n):
        item_id, tier = E.roll_item(rng, "snow", 8, "great")
        tiers[tier] += 1
        if tier == "uncommon":
            wings[item_id in X.place("snow")["special"]["uncommon"]] += 1
        if (item_id in held_ids) != (tier == "held") or item_id not in loot_ids + special_ids + held_ids:
            chk("표에 없는 도구가 나왔다 (또는 지닌 도구가 다른 등급으로 나왔다)", False, (item_id, tier))
        item_id, tier = E.roll_item(rng, "ruins", 8, "great")
        if tier == "rare":
            ruins_rare[item_id in X.place("ruins")["special"]["rare"]] += 1
    want = dict(X.tier_odds(8, "great"))
    off = max(abs(tiers[t] / float(n) - want[t]) for t in X.TIERS)
    chk("등급 비율이 규칙에 가깝다 (8시간 대성공: 희귀 %.1f%% · 특별 %.1f%% · 지닌 도구 %.1f%%)"
        % (100.0 * tiers["rare"] / n, 100.0 * tiers["epic"] / n, 100.0 * tiers["held"] / n),
        off < 0.02 and 0.010 < tiers["held"] / float(n) < 0.030, dict(tiers))
    share = wings[True] / float(max(1, sum(wings.values())))
    chk("  특산물이 그곳에서 잘 나온다 (설산의 '쓸만' 가운데 지력·정신력깃털 %.0f%% - 다른 곳은 28%%)" % (100.0 * share),
        0.45 < share < 0.68, dict(wings))
    share = ruins_rare[True] / float(max(1, sum(ruins_rare.values())))
    chk("  유적의 '희귀' 는 열에 넷이 그곳의 것이다 (영계의천·업그레이드 ..., %.0f%%)" % (100.0 * share), 0.3 < share < 0.5,
        dict(ruins_rare))

    print("\n=== 돈벌이가 아니다 ===")
    wild = sum(cat[i]["sell"] * w for i, w in items.data()["dropTable"]) / float(items.data()["dropTotal"])
    worth = {}
    for place in ("cave", "snow", "ruins"):
        for h, g in ((2, "normal"), (8, "normal"), (8, "great")):
            tot = 0
            for _i in range(2500):
                loot, _tm = E.roll(rng, uid, place, h, g)
                tot += sum(i["sell"] * i["count"] for i in loot)
            worth[(place, h, g)] = tot / 2500.0
    best = max(v for (p_, h, g), v in worth.items() if (h, g) == (8, "great"))
    chk("**8시간 대성공 한 번을 다 팔아도 야생 드랍 하나쯤이다** (가장 값진 곳 %.0f원어치, 야생 드랍 하나 %.0f원)" % (best, wild),
        best < 1300 and best < wild * 1.3, (best, wild))
    chk("  칸 셋을 하루 세 번 다 돌려도 1만 2천 원어치가 안 된다 (%.0f원어치)" % (best * 9), best * 9 < 12000, best * 9)
    low = max(v for (p_, h, g), v in worth.items() if (h, g) == (2, "normal"))
    chk("  2시간 보통은 200원어치 안쪽 (%.0f원어치)" % low, low < 200, low)
    chk("  곳마다 값이 비슷하다 (어디가 유난히 벌이가 좋지 않다)", best < 1.25 * min(v for (p_, h, g), v in worth.items() if (h, g) == (8, "great")),
        dict((k, round(v)) for k, v in worth.items() if k[1:] == (8, "great")))
    uid2 = mkuser("많이받는사람")
    sizes, tm_n = collections.Counter(), 0
    for _i in range(400):
        loot, tm = E.roll(rng, uid2, "ruins", 8, "great")
        sizes[sum(i["count"] for i in loot)] += 1
        tm_n += tm is not None
        if len(set(i["id"] for i in loot)) != len(loot):
            chk("같은 도구가 두 줄로 나왔다", False, loot)
    chk("보따리의 물건 수는 늘 규칙대로다 (8시간 대성공 = 3개)", dict(sizes) == {3: 400}, dict(sizes))
    chk("  기술머신은 유적 8시간 대성공에서 열 번에 세 번쯤 (%d/400)" % tm_n, 75 <= tm_n <= 160, tm_n)
    for no in tms.all_tms():
        tms.give(uid2, no)
    chk("  기술머신을 다 모은 사람에게는 안 나온다", all(E.roll(rng, uid2, "ruins", 8, "great")[1] is None for _i in range(60)))

    print("\n=== 안내서의 확률표 ===")
    # 사이트(docs/guide)에 확률표를 올려 두었다. 규칙을 고치고 안내서를 안 고치면 여기서 걸린다.
    guide_path = os.path.join(os.path.dirname(HERE), "docs", "guide", "index.html")
    with open(guide_path, encoding="utf-8") as f:
        guide = f.read()
    sec = guide[guide.index('<section id="expedition">'):]
    sec = sec[:sec.index("</section>")]

    def pct(x):
        return ("%.3f" % (x * 100.0)).rstrip("0").rstrip(".") + "%"
    bad = []
    for h in X.HOURS:
        for g in X.GRADES:
            cells = "".join('<td class="n">%s</td>' % pct(dict(X.tier_odds(h, g))[t]) for t in X.TIERS)
            if "<td>%s</td>%s</tr>" % (X.GRADE_KR[g], cells) not in sec:
                bad.append((h, g, cells))
    chk("등급 확률 아홉 줄이 게임의 값 그대로다", not bad, bad[:2])
    bad = []
    for place in ("forest", "ruins"):
        for h in X.HOURS:
            cells = "".join('<td class="n">%s</td>' % pct(X.tm_chance(h, g, place)) for g in X.GRADES)
            if "<td>%d시간</td>%s</tr>" % (h, cells) not in sec:
                bad.append((place, h, cells))
    chk("기술머신 확률 여섯 줄 (유적은 따로)", not bad, bad[:2])
    counts = "".join("<tr><td>%d시간</td>%s</tr>" % (h, "".join('<td class="n">%d개</td>' % X.item_count(h, g) for g in X.GRADES))
                     for h in X.HOURS)
    chk("가져오는 물건의 수", counts in "".join(ln.strip() for ln in sec.splitlines()), counts)
    names = [cat[i]["kr"] for p in X.PLACES for t, ids in p["special"].items() for i in ids if t != "common"]
    chk("특산물이 전부 적혀 있고, 특산물 확률도 같다", all(nm in sec for nm in names) and pct(X.SPECIAL_RATE) + " 확률로 특산물" in sec,
        [nm for nm in names if nm not in sec])
    hw = float(sum(w for _i, w in pools["held"]))
    shares = [pct(round(sum(w for i, w in pools["held"] if cat[i]["rarity"] == r_) / hw, 5)) for r_ in X.HELD_RARITIES]
    chk("지닌 도구의 내용 비중 (%s)" % " · ".join(shares), all(x in sec for x in shares), shares)

    print("\n=== 기록 ===")
    for i in range(E.KEEP_DONE + 8):
        o = E.send(uid, pika, "sea", 2, later(days=2, hours=3 * i))
        E.claim(uid, o["out"][0]["id"], later(days=2, hours=3 * i + 2), rng=rng)
    kept = db.q1("SELECT COUNT(*) c FROM expedition WHERE user_id=?", (uid,))["c"]
    chk("받은 기록은 최근 %d개만 남긴다" % E.KEEP_DONE, kept == E.KEEP_DONE, kept)

    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
