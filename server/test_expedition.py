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
  8. **쉬기 (1.10.5)**: 다녀온 포켓몬은 돌아온 때부터 24시간 탐험을 못 나간다 (데리고 다니는 것은 된다).
     불러들인 포켓몬은 쉬지 않는다.
  9. **성장 (1.10.5)**: 받을 때 탐험 경험치가 쌓이고, 레벨마다 성장치 1점을 원하는 데에 찍는다.
     발걸음은 시간을, 눈썰미는 귀한 것을, 주머니는 물건 수를, 호기심은 기술머신을 올린다.
     나가 있는 동안에는 못 바꾼다. 되돌리는 데는 돈이 든다. **다 키워도 하루 최대는 1만 3천 원어치 안쪽이다.**
 10. **친화력 (1.10.5)**: 받을 때 그곳 타입의 포켓몬을 데려온다 (다 찍어도 60%). 풀숲에 나오는 종만,
     지금 풀숲에서 만나는 레벨로. 박스에 들어가고 도감에 오른다. 자리가 없으면 못 데려온다.
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
    types = [t for p in X.ITEM_PLACES for t in p["types"]]
    all_types = set(t for sp in dex.species for t in sp.get("types", []))
    chk("물건을 가져오는 곳이 여섯, 타입 열여덟이 한 곳씩 맞는다 (+ 골드만 가져오는 광산)",
        len(X.ITEM_PLACES) == 6 and len(types) == 18 == len(set(types)) and set(types) == all_types
        and len(X.PLACES) == 7 and [p["id"] for p in X.PLACES if X.is_gold(p["id"])] == ["mine"],
        sorted(all_types - set(types)))
    loot_ids = [i for t in X.LOOT for i, _w in X.LOOT[t]]
    special_ids = [i for p in X.ITEM_PLACES for t, ids in p["special"].items() for i in ids]
    missing = [i for i in loot_ids + special_ids if i not in cat]
    chk("탐험에서 나오는 것(전용 표 %d종 + 특산물)이 전부 있는 도구다" % len(set(loot_ids)), not missing
        and set(X.LOOT) == set(X.TIERS) - {"held"} and all(X.LOOT[t] for t in X.LOOT)
        and all(set(p["special"]) <= set(X.LOOT) for p in X.ITEM_PLACES), missing)
    # 광산 (사용자 결정 11/07: '오직 골드만', 8시간 대성공 4,000원, 강철 · 땅 · 바위, 성장치는 발걸음 · 주머니만)
    mine = X.place("mine") or {}
    chk("광산 = 강철 · 땅 · 바위, 골드만 가져온다 (특산물 · 기술머신 없음)", mine.get("kr") == "광산"
        and mine.get("types") == ["STEEL", "GROUND", "ROCK"] and X.is_gold("mine") and not X.is_gold("cave")
        and not mine.get("special") and X.tm_chance(8, "great", "mine", lore=10) == 0, mine)
    chk("골드 = 8시간 대성공 4,000원, 시간에 비례, 성공 80% · 보통 60%",
        [[X.gold_for(h, g) for g in X.GRADES] for h in X.HOURS] == [[600, 800, 1000], [1200, 1600, 2000], [2400, 3200, 4000]],
        [[X.gold_for(h, g) for g in X.GRADES] for h in X.HOURS])
    chk("  주머니 1점에 골드 +3%, 10점이면 +30% (8시간 대성공 5,200원)",
        X.gold_for(8, "great", haul=1) == 4120 and X.gold_for(8, "great", haul=10) == 5200
        and X.gold_for(2, "normal", haul=10) == 780, (X.gold_for(8, "great", haul=1), X.gold_for(8, "great", haul=10)))
    chk("  물건 곳에서는 골드가 0", X.gold_for(8, "great", place_id="cave") == 0 and X.gold_for(8, "great", place_id="mine") == 4000)
    chk("  성공도는 다른 곳처럼 레벨과 타입 (Lv.75 강철이면 대성공, Lv.100 이어도 안 맞으면 성공)",
        X.grade_of(75, ["STEEL"], "mine") == "great" and X.grade_of(100, ["WATER"], "mine") == "good"
        and X.grade_of(30, ["GROUND", "ROCK"], "mine") == "good")
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
    listing = main.box_listing(uid)["pokemon"]
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
        and "away" not in next(m for m in main.box_listing(uid)["pokemon"] if m["id"] == onix))
    why = refused(E.claim, uid, st["out"][1]["id"], later(hours=2))
    chk("**같은 보따리를 두 번 못 받는다**", why and why[0] == 404 and bag(uid) == dict(got["bag"]), why)
    main.set_desktop(onix, main.DesktopIn(on=True), ctx(uid))
    chk("  돌아온 포켓몬은 다시 데리고 다닐 수 있다", db.q1("SELECT on_desktop FROM pokemon WHERE id=?", (onix,))["on_desktop"] == 1)
    row = db.q1("SELECT state, loot, claimed_at FROM expedition WHERE id=?", (st["out"][1]["id"],))
    chk("  기록이 남는다 (받은 것)", row["state"] == "done" and row["loot"] and row["claimed_at"], dict(row))
    grown = one.get("growth") or {}
    chk("  **탐험 경험치를 받는다** (2시간 성공 = 24) · 돌아온 때부터 24시간 쉰다",
        grown.get("xp") == 24 == X.xp_for(2, "good") and grown.get("level") == 0 and grown.get("levelBefore") == 0
        and grown.get("need") == 100 and grown.get("into") == 24 and grown.get("free") == 0
        and grown.get("rest") == 24 * 3600 and one.get("bonus") == 0, grown)

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
    out = E.send(uid, bulba, "forest", 4, later(hours=40))       # (쉬는 시간이 끝난 뒤다 - 아래 '쉬기')
    eid = out["out"][0]["id"]
    before = bag(uid)
    grow_before = E.state(uid, later(hours=40))["growth"][str(bulba)]
    back = E.recall(uid, eid, later(hours=41))
    chk("불러들이면 빈손으로 돌아온다 (칸이 빈다)", back["ok"] and back["free"] == 3 and bag(uid) == before
        and not E.is_away(uid, bulba) and "빈손" in back["message"], back["message"])
    why = refused(E.claim, uid, eid, later(hours=50))
    chk("  불러들인 것은 받을 수 없다", why and why[0] == 404, why)
    why = refused(E.recall, uid, eid, later(hours=41))
    chk("  두 번 불러들일 수 없다", why and why[0] == 404, why)
    chk("남의 탐험은 건드릴 수 없다", refused(E.recall, other, eid, later(hours=41))[0] == 404
        and E.claim(other, None, later(hours=99))["claimed"] == [])
    g = back["growth"][str(bulba)]
    chk("  **불러들인 포켓몬은 경험치도 없고 쉬지도 않는다** (바로 다시 보낼 수 있다)",
        g["xp"] == grow_before["xp"] and g["runs"] == grow_before["runs"] and g["rest"] == 0, g)

    print("\n=== 쉬기 (1.10.5) ===")
    # 위에서: 롱스톤은 2시간 뒤에 돌아와 바로 받았고, 이상해꽃(8시간)·꼬마(4시간)는 9시간째에 한꺼번에 받았다
    g9 = allgot["growth"]
    chk("받은 답에 포켓몬마다의 성장·쉬는 시간이 실린다 (다녀온 셋만)", set(g9) == {str(bulba), str(onix), str(rat)}, sorted(g9))
    chk("**쉬는 시간은 돌아온 때부터 센다** (8시간에 돌아와 9시간째에 받았다 = 23시간 남음)",
        g9[str(bulba)]["rest"] == 23 * 3600 and g9[str(rat)]["rest"] == 19 * 3600 and g9[str(onix)]["rest"] == 17 * 3600,
        dict((k, v["rest"]) for k, v in g9.items()))
    by_mon = dict((c["pokemon"]["id"], c["growth"]) for c in allgot["claimed"])
    chk("  받은 보따리마다 얻은 경험치와 쉬는 시간이 적혀 온다", by_mon[bulba]["xp"] == 120 and by_mon[bulba]["rest"] == 23 * 3600
        and by_mon[rat]["xp"] == 40 and by_mon[rat]["rest"] == 19 * 3600, by_mon)
    why = refused(E.send, uid, bulba, "forest", 2, later(hours=10))
    chk("**쉬는 동안에는 탐험을 못 나간다** (남은 시간을 알려 준다)", why and why[0] == 409 and "쉬는 중" in why[1]
        and "22시간" in why[1], why)
    why = refused(E.send, uid, bulba, "forest", 2, later(hours=31, minutes=59))
    chk("  24시간이 되기 1분 전에도 못 나간다", why and why[0] == 409 and "쉬는 중" in why[1], why)
    main.set_desktop(bulba, main.DesktopIn(on=True), ctx(uid))
    chk("  쉬는 동안에도 데리고 다닐 수는 있다 (탐험만 못 나간다)",
        db.q1("SELECT on_desktop FROM pokemon WHERE id=?", (bulba,))["on_desktop"] == 1)
    main.set_desktop(bulba, main.DesktopIn(on=False), ctx(uid))
    chk("  쉬는 포켓몬은 칸을 차지하지 않는다 (나가 있는 것이 아니다)", not E.is_away(uid, bulba)
        and E.state(uid, later(hours=10))["free"] == 3)
    ok = E.send(uid, pika, "sea", 2, later(hours=10))
    chk("  다른 포켓몬은 그동안 보낼 수 있다", ok["ok"] and ok["free"] == 2)
    E.recall(uid, ok["out"][0]["id"], later(hours=10, minutes=1))
    chk("  한 번도 안 다녀온 포켓몬은 성장 기록이 없다 (0 에서 시작)", str(pika) not in E.state(uid, later(hours=11))["growth"])
    st = E.state(uid, later(hours=32))
    chk("24시간이 지나면 다시 나갈 수 있다", st["growth"][str(bulba)]["rest"] == 0
        and E.send(uid, bulba, "forest", 2, later(hours=32))["ok"])
    E.recall(uid, E.state(uid, later(hours=32))["out"][0]["id"], later(hours=32, minutes=1))
    # 보따리를 늦게 받아도 손해가 없다: 돌아온 지 24시간이 넘어 받으면 쉴 것이 없다
    uid3 = mkuser("늦게받는사람")
    late = mkmon(uid3, "VENUSAUR", 80)
    eid3 = E.send(uid3, late, "forest", 2, T0)["out"][0]["id"]
    got3 = E.claim(uid3, eid3, later(hours=30), rng=random.Random(1))
    chk("  보따리를 이틀 뒤에 받았으면 이미 다 쉰 것이다", got3["claimed"][0]["growth"]["rest"] == 0
        and E.send(uid3, late, "forest", 2, later(hours=30))["ok"], got3["claimed"][0]["growth"])

    print("\n=== 성장 (1.10.5) ===")
    chk("경험치: 시간 x 성공도 (8시간 대성공 120 · 8시간 보통 80 · 2시간 보통 20)",
        [X.xp_for(h, g) for h, g in ((8, "great"), (8, "normal"), (2, "normal"), (4, "good"))] == [120, 80, 20, 48])
    chk("레벨: 100, 140, 180 ... 으로 오른다 (다 합쳐 2,800 = 8시간 대성공 스물네 번)",
        [X.level_need(n) for n in (1, 2, 10)] == [100, 140, 460] and X.XP_MAX == 2800
        and [X.level_of(x)[0] for x in (0, 99, 100, 239, 240, 2799, 2800, 99999)] == [0, 0, 1, 1, 2, 9, 10, 10]
        and X.level_of(120) == (1, 20, 140) and X.level_of(2800) == (10, 0, None), X.level_of(120))
    now = later(hours=42)
    g = E.state(uid, now)["growth"][str(bulba)]
    chk("이상해꽃: 8시간 대성공 한 번 = 탐험 Lv.1, 성장치 1점", g["xp"] == 120 and g["level"] == 1 and g["into"] == 20
        and g["need"] == 140 and g["free"] == 1 and g["stats"] == dict((k, 0) for k in X.STATS)
        and g["runs"] == 1, g)
    chk("  없는 성장치·음수·0점은 거절", refused(E.grow, uid, bulba, {"power": 1}, now)[0] == 400
        and refused(E.grow, uid, bulba, {"speed": -1}, now)[0] == 400 and refused(E.grow, uid, bulba, {"speed": 0}, now)[0] == 400
        and refused(E.grow, uid, bulba, {}, now)[0] == 400 and refused(E.grow, uid, bulba, {"speed": "x"}, now)[0] == 400)
    why = refused(E.grow, uid, bulba, {"speed": 1, "luck": 1}, now)
    chk("  가진 점수보다 많이는 못 찍는다", why and why[0] == 409 and "모자랍니다" in why[1], why)
    chk("  남의 포켓몬·다녀온 적 없는 포켓몬은 못 찍는다", refused(E.grow, uid, theirs, {"speed": 1}, now)[0] == 404
        and refused(E.grow, uid, pika, {"speed": 1}, now)[0] == 409)
    out = E.grow(uid, bulba, {"speed": 1}, now)
    g = out["growth"][str(bulba)]
    chk("**발걸음에 1점을 찍었다**", out["ok"] and g["stats"]["speed"] == 1 and g["free"] == 0 and "1점" in out["message"], g)
    chk("  다 찍었으면 더 못 찍는다", refused(E.grow, uid, bulba, {"luck": 1}, now)[0] == 409)

    sent = E.send(uid, bulba, "forest", 8, now)
    one = sent["out"][0]
    chk("**발걸음 1점: 8시간이 7시간 48분이 된다** (물건 수·성공도는 그대로)", one["left"] == 28080 == X.duration(8, 1)
        and one["total"] == 28080 and one["hours"] == 8 and one["items"] == 3 and one["grade"] == "great"
        and "7시간 48분" in sent["message"], (one["left"], sent["message"]))
    chk("  나가 있는 동안에는 찍지도 되돌리지도 못한다", refused(E.grow, uid, bulba, {"luck": 1}, now)[0] == 409
        and "나가 있는" in refused(E.reset, uid, bulba, now)[1])
    why = refused(E.claim, uid, one["id"], later(hours=42, minutes=467))
    chk("  7시간 47분에는 아직이다", why and why[0] == 409, why)
    got = E.claim(uid, one["id"], later(hours=42, minutes=468), rng=random.Random(8))
    grown = got["claimed"][0]["growth"]
    chk("  7시간 48분에 받는다. 경험치는 고른 시간(8시간)만큼 = 120", grown["xp"] == 120 and grown["levelBefore"] == 1
        and grown["level"] == 2 and grown["free"] == 1 and grown["rest"] == 24 * 3600, grown)
    now = later(hours=80)

    # 레벨을 끝까지 올려 본다 (경험치를 직접 적는다 - 스물네 번 보내는 대신)
    db.run("UPDATE expedition_mon SET xp=?, rest_until=NULL WHERE pokemon_id=?", (X.XP_MAX - 10, bulba))
    g = E.state(uid, now)["growth"][str(bulba)]
    chk("Lv.9: 다음 레벨까지 460", g["level"] == 9 and g["need"] == 460 and g["into"] == 450 and g["free"] == 8, g)
    eid = E.send(uid, bulba, "forest", 2, now)["out"][0]["id"]
    grown = E.claim(uid, eid, later(hours=82), rng=random.Random(8))["claimed"][0]["growth"]
    chk("**Lv.10 이 끝이다** (경험치는 2,800 에서 멈춘다)", grown["level"] == 10 and grown["need"] is None and grown["xp"] == 10
        and grown["free"] == 9 and db.q1("SELECT xp FROM expedition_mon WHERE pokemon_id=?", (bulba,))["xp"] == X.XP_MAX, grown)
    db.run("UPDATE expedition_mon SET rest_until=NULL WHERE pokemon_id=?", (bulba,))
    now = later(hours=83)
    out = E.grow(uid, bulba, {"luck": 4, "haul": 2, "lore": 2, "charm": 1}, now)
    g = out["growth"][str(bulba)]
    chk("여러 성장치에 한꺼번에 나눠 찍는다 (다섯 가지)", g["stats"] == {"speed": 1, "luck": 4, "haul": 2, "lore": 2, "charm": 1}
        and g["free"] == 0 and X.STATS == ("speed", "luck", "haul", "lore", "charm"), g)
    chk("  성장치는 모두 열 점이다 (레벨 10)", X.spent(g["stats"]) == X.MAX_LEVEL == 10 and X.STAT_CAP == 10)

    print("  -- 되돌리기")
    db.run("UPDATE users SET money=? WHERE id=?", (X.RESET_COST - 1, uid))
    why = refused(E.reset, uid, bulba, now)
    chk("돈이 모자라면 못 되돌린다 (%s원)" % format(X.RESET_COST, ","), why and why[0] == 409 and "돈" in why[1]
        and E.state(uid, now)["growth"][str(bulba)]["free"] == 0, why)
    db.run("UPDATE users SET money=? WHERE id=?", (X.RESET_COST + 500, uid))
    out = E.reset(uid, bulba, now)
    g = out["growth"][str(bulba)]
    chk("**돈을 내고 전부 되돌린다** (레벨과 경험치는 그대로, 다시 찍을 수 있다)", out["ok"] and out["money"] == 500
        and items.money(uid) == 500 and g["stats"] == dict((k, 0) for k in X.STATS) and g["free"] == 10
        and g["level"] == 10, g)
    why = refused(E.reset, uid, bulba, now)
    chk("  되돌릴 것이 없으면 돈을 안 받는다", why and why[0] == 409 and "되돌릴" in why[1] and items.money(uid) == 500, why)
    chk("  남의 포켓몬은 못 되돌린다", refused(E.reset, other, bulba, now)[0] == 404)
    E.grow(uid, bulba, {"speed": 10}, now)
    sent = E.send(uid, bulba, "forest", 8, now)
    chk("**발걸음 10점: 8시간이 6시간이 된다** (2시간은 1시간 30분, 4시간은 3시간)", sent["out"][0]["left"] == 6 * 3600
        and [X.duration(h, 10) for h in X.HOURS] == [5400, 3 * 3600, 6 * 3600] and "6시간" in sent["message"],
        sent["out"][0]["left"])
    E.recall(uid, sent["out"][0]["id"], later(hours=83, minutes=1))
    chk("  한 성장치에 열 점까지 (더는 못 찍는다 - 남은 점수도 없다)", refused(E.grow, uid, bulba, {"speed": 1}, now)[0] == 409)
    db.run("UPDATE expedition_mon SET speed=0, luck=0, haul=0, lore=0, charm=0, xp=? WHERE pokemon_id=?", (120, bulba))

    print("  -- 놓아주면 기록도 지운다")
    main.release(rat, ctx(uid))
    chk("놓아준 포켓몬의 성장 기록이 남지 않는다",
        db.q1("SELECT pokemon_id FROM expedition_mon WHERE pokemon_id=?", (rat,)) is None
        and str(rat) not in E.state(uid, now)["growth"])

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

    print("  -- 성장치가 굴림에 드는 자리 (1.10.5)")
    same = [E.roll(random.Random(k), uid, "snow", 8, "great") == E.roll(random.Random(k), uid, "snow", 8, "great", {})
            == E.roll_more(random.Random(k), uid, "snow", 8, "great", dict((s_, 0) for s_ in X.STATS))[:2] for k in range(40)]
    chk("성장치가 없으면 굴림이 전과 한 치도 다르지 않다", all(same), same.count(False))
    n = 5000
    base_t, luck_t = collections.Counter(), collections.Counter()
    for _i in range(n):
        base_t[E.roll_item(rng, "cave", 8, "great")[1]] += 1
        luck_t[E.roll_item(rng, "cave", 8, "great", 10)[1]] += 1
    fine = lambda c: (c["rare"] + c["epic"] + c["held"]) / float(n)       # noqa: E731
    want0 = sum(p for t, p in X.tier_odds(8, "great") if t in ("rare", "epic", "held"))
    want10 = sum(p for t, p in X.tier_odds(8, "great", 10) if t in ("rare", "epic", "held"))
    chk("**눈썰미 10점: 귀한 것(희귀·특별·지닌 도구)이 1.5배** (%.1f%% -> %.1f%%)" % (100 * fine(base_t), 100 * fine(luck_t)),
        abs(want10 / want0 - 1.5) < 1e-9 and abs(fine(base_t) - want0) < 0.015 and abs(fine(luck_t) - want10) < 0.02
        and dict(X.tier_odds(8, "great", 10))["uncommon"] == dict(X.tier_odds(8, "great"))["uncommon"],
        (fine(base_t), fine(luck_t), want0, want10))
    for h in X.HOURS:
        for g_ in X.GRADES:
            odds = X.tier_odds(h, g_, 10)
            if abs(sum(p for _t, p in odds) - 1.0) > 1e-9 or min(p for _t, p in odds) < 0:
                chk("눈썰미 10점에서도 등급 확률의 합이 1 (%d시간 %s)" % (h, g_), False, odds)
    sizes, extra = collections.Counter(), 0
    for _i in range(3000):
        loot, _tm, bonus = E.roll_more(rng, uid, "forest", 8, "great", {"haul": 10})
        got_n = sum(i["count"] for i in loot)
        sizes[got_n] += 1
        extra += bonus
        if got_n != 3 + bonus:
            chk("더 가져온 수가 물건 수와 안 맞는다", False, (got_n, bonus))
    avg = sum(k * v for k, v in sizes.items()) / 3000.0
    chk("**주머니 10점: 물건마다 30%% 로 하나 더** (8시간 대성공 평균 %.2f개, 많아야 6개)" % avg,
        3.75 < avg < 4.05 and max(sizes) <= 6 and min(sizes) == 3 and X.haul_chance(10) == 0.3, dict(sizes))
    chk("  2시간 보통도 같은 비율이다 (1개 -> 평균 1.3개)",
        1.2 < sum(sum(i["count"] for i in E.roll_more(rng, uid, "forest", 2, "normal", {"haul": 10})[0])
                  for _i in range(2000)) / 2000.0 < 1.4)
    uid4 = mkuser("기술머신찾는사람")
    tm0 = sum(E.roll(rng, uid4, "forest", 8, "great")[1] is not None for _i in range(3000))
    tm10 = sum(E.roll(rng, uid4, "forest", 8, "great", {"lore": 10})[1] is not None for _i in range(3000))
    chk("**호기심 10점: 기술머신이 두 배** (숲 8시간 대성공 %d -> %d / 3000)" % (tm0, tm10),
        X.tm_chance(8, "great", "forest", 10) == 2 * X.tm_chance(8, "great", "forest") and 1.6 < tm10 / float(tm0) < 2.5
        and X.tm_chance(8, "great", "ruins", 10) < 0.6, (tm0, tm10))
    chk("효과를 사람 말로", [X.stat_text(k, n) for k, n in (("speed", 4), ("luck", 10), ("haul", 1), ("lore", 3))]
        == ["탐험 시간 -10%", "귀한 물건 확률 +50%", "물건마다 3% 로 하나 더", "기술머신 확률 +30%"]
        and [X.time_text(X.duration(8, n)) for n in (0, 1, 10)] == ["8시간", "7시간 48분", "6시간"],
        [X.stat_text(k, n) for k, n in (("speed", 4), ("luck", 10), ("haul", 1), ("lore", 3))])

    print("\n=== 친화력: 그곳의 포켓몬을 데려온다 (1.10.5) ===")
    chk("친화력 1점에 6%, 다 찍어도 60% (100% 가 아니다)", X.charm_chance(1) == 0.06 and abs(X.charm_chance(10) - 0.6) < 1e-9
        and X.charm_chance(0) == 0 and X.charm_chance(99) == X.charm_chance(10)
        and X.stat_text("charm", 10) == "포켓몬을 데려올 확률 60%" and X.STAT_KR["charm"] == "친화력", X.charm_chance(10))
    spawn_ok = set(sp["internal"] for sp in dex.species if sp.get("spawnable"))
    frng = random.Random(77)
    seen_sp = {}
    bad = []
    for place in [p_["id"] for p_ in X.ITEM_PLACES]:
        good = set(X.place(place)["types"])
        got_sp = set()
        for _i in range(150):
            m = E.roll_friend(frng, place, 40, 330 + 40 * 8)
            types_ = set(dex.get(m["species"])["types"])
            got_sp.add(m["species"])
            if not (types_ & good) or m["level"] != 40 or dex.get(m["species"]).get("legendary") \
                    or dex.get(m["species"]).get("mega"):
                bad.append((place, m["species"], m["level"]))
        seen_sp[place] = got_sp
    chk("**데려오는 포켓몬은 그곳의 세 타입 가운데 하나다** (여섯 곳 x 150번, 레벨도 준 그대로)", not bad, bad[:5])
    chk("  곳마다 여러 종이 나온다 (%s)" % " · ".join("%s %d종" % (X.place(k)["kr"], len(v)) for k, v in seen_sp.items()),
        all(len(v) >= 12 for v in seen_sp.values()), dict((k, len(v)) for k, v in seen_sp.items()))
    low_lv = [E.roll_friend(frng, "volcano", 5, 330 + 5 * 8) for _i in range(60)]
    chk("  낮은 레벨에서는 그 레벨에 나올 수 있는 종만 (종족값 상한도 풀숲과 같다)",
        all(m["level"] == 5 and sum(dex.get(m["species"])["base"].values()) <= 330 + 5 * 8 for m in low_lv),
        [(m["species"], sum(dex.get(m["species"])["base"].values())) for m in low_lv][:4])
    evolved = [m for m in (E.roll_friend(frng, "forest", 90, None) for _i in range(120))
               if dex.get(m["species"]).get("evolvesFrom") or dex.get(m["species"]).get("prevo")]
    chk("  레벨이 높으면 이미 진화한 모습으로 온다", len(evolved) >= 20, len(evolved))

    fuid = mkuser("친화력")
    f_lead = mkmon(fuid, "SNORLAX", 37, slot=0)
    mkmon(fuid, "PIKACHU", 52, slot=1)
    wild_lv = main._wild_levels(fuid)[1]
    state0 = frng.getstate()
    chk("친화력을 안 찍었으면 주사위도 안 굴린다", E._friend(frng, fuid, "forest", {"charm": 0}, T0) == (None, False)
        and E._friend(frng, fuid, "forest", {}, T0) == (None, False) and frng.getstate() == state0)
    n0 = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (fuid,))["c"]
    came, news = [], 0
    for _i in range(400):
        fr, full = E._friend(frng, fuid, "sea", {"charm": 10}, T0)
        if fr:
            came.append(fr)
            news += fr["new"]
    n1 = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (fuid,))["c"]
    chk("**친화력 10점: 열 번에 여섯 번 데려온다** (%d / 400)" % len(came), 0.52 < len(came) / 400.0 < 0.68
        and n1 - n0 == len(came), (len(came), n1 - n0))
    one = came[0]
    row = db.q1("SELECT * FROM pokemon WHERE id=?", (one["id"],))
    chk("  데려온 포켓몬은 박스에 들어간다 (데리고 다니는 것이 아니다)", row is not None and row["user_id"] == fuid
        and row["on_desktop"] == 0 and row["species"] == one["species"] and row["level"] == one["level"], dict(row) if row else None)
    chk("  화면이 읽는 칸: 이름·도감 번호·레벨·타입·색·처음인지", set(one) == {"id", "name", "species", "num", "level", "shiny",
                                                                 "types", "new"}
        and one["name"] == dex.get(one["species"])["kr"] and set(one["types"]) & set(X.place("sea")["types"]), one)
    chk("  **레벨은 지금 풀숲에서 만나는 레벨이다** (데리고 다니는 것 중 가장 낮은 레벨 = %d)" % wild_lv,
        wild_lv == 37 and all(f["level"] == 37 for f in came), sorted(set(f["level"] for f in came)))
    per_box = [r["n"] for r in db.q("SELECT box, COUNT(*) n FROM pokemon WHERE user_id=? AND on_desktop=0 GROUP BY box", (fuid,))]
    chk("  한 박스에 서른 마리를 넘기지 않는다 (자리 있는 박스로)", max(per_box) <= 30 and len(per_box) >= 2, per_box)
    kinds = set(f["species"] for f in came)
    caught_n = db.q1("SELECT COUNT(*) c FROM seen WHERE user_id=? AND caught=1", (fuid,))["c"]
    chk("  **도감에 오른다** (%d종) · 처음 데려온 종에만 '새로' 가 붙는다" % len(kinds),
        all(items.has_caught(fuid, k) for k in kinds) and news == len(kinds) and caught_n >= len(kinds), (news, len(kinds), caught_n))
    st = db.q1("SELECT * FROM wild_state WHERE user_id=?", (fuid,))
    chk("  잡은 것이 아니다 (잡은 수에는 안 든다)", st is None or not (st["caught"] if "caught" in st.keys() else 0),
        dict(st) if st else None)

    # 받기까지 통째로: 친화력 10점을 찍은 포켓몬을 보내고 받는다
    f_mon = mkmon(fuid, "VENUSAUR", 80)
    db.run("INSERT INTO expedition_mon (pokemon_id, user_id, xp, charm) VALUES (?,?,?,10)", (f_mon, fuid, X.XP_MAX))
    got_friend = None
    for k in range(12):
        t_send = later(days=30 + 2 * k)
        eid = E.send(fuid, f_mon, "forest", 2, t_send)["out"][0]["id"]
        res = E.claim(fuid, eid, t_send + datetime.timedelta(hours=2), rng=random.Random(500 + k))
        c0 = res["claimed"][0]
        if c0["friend"]:
            got_friend = (res, c0)
            break
    res, c0 = got_friend
    saved = __import__("json").loads(db.q1("SELECT loot FROM expedition WHERE id=?", (c0["id"],))["loot"])
    chk("**받을 때 포켓몬을 데려왔다**: 받은 답과 기록에 실리고, 알림 글에 적힌다", c0["friend"]["id"] > 0
        and c0["friendFull"] is False and set(c0["friend"]["types"]) & set(X.place("forest")["types"])
        and "포켓몬 1마리를 데려왔습니다" in res["message"] and saved["friend"]["id"] == c0["friend"]["id"]
        and db.q1("SELECT on_desktop FROM pokemon WHERE id=?", (c0["friend"]["id"],))["on_desktop"] == 0, c0["friend"])
    chk("  물건은 그대로 받는다 (포켓몬은 덤이다)", sum(i["count"] for i in c0["items"]) == X.item_count(2, c0["grade"]), c0["items"])
    none = E.claim(uid, None, later(days=60))
    chk("  친화력이 없는 포켓몬의 보따리에는 포켓몬이 없다", all(c.get("friend") is None for c in allgot["claimed"])
        and "friend" in allgot["claimed"][0] and none["claimed"] == [])

    real_max = E.config.MAX_BOX
    E.config.MAX_BOX = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (fuid,))["c"]
    try:
        n_before = E.config.MAX_BOX
        outs = [E._friend(frng, fuid, "cave", {"charm": 10}, T0) for _i in range(40)]
    finally:
        E.config.MAX_BOX = real_max
    chk("**보유 상한이 찼으면 못 데려온다** (그렇다고 알려 준다, 포켓몬은 안 늘어난다)",
        all(fr is None for fr, _f in outs) and any(f for _fr, f in outs)
        and db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (fuid,))["c"] == n_before, [f for _fr, f in outs][:6])

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
    # **다 키워도 돈벌이가 아니다 (1.10.5).** 굴려서 재면 흔들리니 기대값을 셈한다.
    def item_worth(place, h, g_, luck=0):
        tot = 0.0
        for tier, p_ in X.tier_odds(h, g_, luck):
            table = pools[tier]
            v = sum(cat[i]["sell"] * w for i, w in table) / sum(w for _i, w in table)
            sp_ = E.special_pool(place, tier)
            if sp_:
                v = X.SPECIAL_RATE * sum(cat[i]["sell"] for i, _w in sp_) / len(sp_) + (1 - X.SPECIAL_RATE) * v
            tot += p_ * v
        return tot

    def per_day(place, h, g_, st_):
        """칸 셋을 쉬지 않고 돌릴 때 하루에 가져오는 값 (다 키운 포켓몬이 넉넉하다고 치고)."""
        one_run = X.item_count(h, g_) * item_worth(place, h, g_, st_.get("luck", 0)) * (1 + X.haul_chance(st_.get("haul", 0)))
        return X.SLOTS * 86400.0 / X.duration(h, st_.get("speed", 0)) * one_run

    places = [p_["id"] for p_ in X.ITEM_PLACES]       # 광산(골드)은 아래 '광산' 에서 따로 본다
    base_day = max(per_day(p_, 8, "great", {}) for p_ in places)
    chk("기대값으로 셈한 하루 최대가 굴려서 잰 값과 같다 (%.0f원어치)" % base_day, abs(base_day - best * 9) < best * 9 * 0.08,
        (base_day, best * 9))
    builds = [{"speed": a, "luck": b, "haul": 10 - a - b} for a in range(11) for b in range(11 - a)]
    top_day, top_build = max((per_day(p_, h, "great", st_), (p_, h, st_)) for p_ in places for h in X.HOURS for st_ in builds)
    chk("**성장치 열 점을 어떻게 찍어도 하루 최대는 1만 3천 원어치 안쪽** (%.0f원어치 = 지금의 %.2f배, %s)"
        % (top_day, top_day / base_day, " ".join("%s %d" % (X.STAT_KR[k], v) for k, v in top_build[2].items() if v)),
        top_day < 13000 and top_day / base_day < 1.36, (top_day, top_build))
    solo = dict((k, max(per_day(p_, 8, "great", {k: 10}) for p_ in places) / base_day) for k in ("speed", "luck", "haul"))
    chk("  하나에 다 찍으면: 발걸음 +%.0f%% · 눈썰미 +%.0f%% · 주머니 +%.0f%% (어느 것도 버리는 패가 아니다)"
        % tuple(100 * (solo[k] - 1) for k in ("speed", "luck", "haul")),
        all(1.2 < v < 1.36 for v in solo.values()), solo)
    # 포켓몬이 적으면 쉬는 시간 때문에 전보다 덜 번다: 한 마리는 (탐험 + 24시간)에 한 번 나간다
    one_run = X.item_count(8, "great") * max(item_worth(p_, 8, "great") for p_ in places)
    three = 3 * 24.0 / (8 + X.REST_HOURS) * one_run
    chk("  세 마리만 돌리면 하루 %.0f원어치 (쉬는 시간이 없던 때의 넷에 하나)" % three, three < base_day * 0.26, three)
    chk("  기술머신은 호기심을 다 찍어도 유적 8시간 대성공에서 열에 여섯이 안 된다",
        X.tm_chance(8, "great", "ruins", 10) < 0.6, X.tm_chance(8, "great", "ruins", 10))

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
    names = [cat[i]["kr"] for p in X.ITEM_PLACES for t, ids in p["special"].items() for i in ids if t != "common"]
    chk("특산물이 전부 적혀 있고, 특산물 확률도 같다", all(nm in sec for nm in names) and pct(X.SPECIAL_RATE) + " 확률로 특산물" in sec,
        [nm for nm in names if nm not in sec])
    hw = float(sum(w for _i, w in pools["held"]))
    shares = [pct(round(sum(w for i, w in pools["held"] if cat[i]["rarity"] == r_) / hw, 5)) for r_ in X.HELD_RARITIES]
    chk("지닌 도구의 내용 비중 (%s)" % " · ".join(shares), all(x in sec for x in shares), shares)

    # 쉬기와 성장 (1.10.5)
    num = lambda x: ("%.3f" % x).rstrip("0").rstrip(".")                                      # noqa: E731
    chk("쉬는 시간과 되돌리는 값", "다녀오면 %d시간 쉽니다" % X.REST_HOURS in sec and "돌아온 때부터 %d시간" % X.REST_HOURS in sec
        and "<b>%s원</b>" % format(X.RESET_COST, ",") in sec, (X.REST_HOURS, X.RESET_COST))
    stat_rows = [(X.STAT_KR["speed"], "-%s%%" % num(100 * X.SPEED_PER), "-%s%%" % num(100 * X.SPEED_PER * X.STAT_CAP)),
                 (X.STAT_KR["luck"], "+%s%%" % num(100 * X.LUCK_PER), "+%s%%" % num(100 * X.LUCK_PER * X.STAT_CAP)),
                 (X.STAT_KR["haul"], "%s%%" % num(100 * X.HAUL_PER), "%s%%" % num(100 * X.HAUL_PER * X.STAT_CAP)),
                 (X.STAT_KR["lore"], "+%s%%" % num(100 * X.LORE_PER), "+%s%%" % num(100 * X.LORE_PER * X.STAT_CAP)),
                 (X.STAT_KR["charm"], "%s%%" % num(100 * X.CHARM_PER), "%s%%" % num(100 * X.CHARM_PER * X.STAT_CAP))]
    bad = [r for r in stat_rows if not __import__("re").search(
        r'<tr><td>%s</td><td>[^<]+</td><td class="n">%s</td><td class="n">%s</td></tr>'
        % tuple(__import__("re").escape(x) for x in r), sec)]
    chk("성장치 다섯의 효과 (1점 · %d점)" % X.STAT_CAP, not bad and len(stat_rows) == len(X.STATS)
        and "탐험 레벨은 %d 까지" % X.MAX_LEVEL in sec and "모두 %d점" % X.MAX_LEVEL in sec and "다섯 중" in sec, bad)
    bad = [h for h in X.HOURS if '<tr><td>%d시간</td>%s</tr>' % (h, "".join(
        '<td class="n">%s</td>' % X.time_text(X.duration(h, n)) for n in (0, 2, 4, 6, 8, 10))) not in sec]
    chk("발걸음을 찍었을 때 걸리는 시간 세 줄", not bad, bad)
    gold_rows = "".join("<tr><td>%d시간</td>%s</tr>" % (h, "".join('<td class="n">%s원</td>' % format(X.gold_for(h, g), ",")
                                                                   for g in X.GRADES)) for h in X.HOURS)
    chk("광산에서 가져오는 골드 세 줄 · 광산 줄 · 주머니 덤", gold_rows in "".join(ln.strip() for ln in sec.splitlines())
        and "<tr><td>광산</td><td>강철 · 땅 · 바위</td>" in sec
        and "골드 +%s%%" % num(100 * X.HAUL_PER) in sec, gold_rows)

    print("\n=== 광산: 골드만 가져온다 ===")
    guid = mkuser("광부")
    agg = mkmon(guid, "AGGRON", 80)                  # 강철 · 바위 = 둘 다 맞는다 -> 대성공
    rows_before = db.q1("SELECT money FROM users WHERE id=?", (guid,))["money"]
    # 다 키운 포켓몬: 주머니 4 · 친화력 6 (친화력 · 호기심 · 눈썰미는 광산에서 아무 일도 안 한다)
    db.run("INSERT INTO expedition_mon (pokemon_id, user_id, xp, haul, charm, runs) VALUES (?,?,?,?,?,1)",
           (agg, guid, X.XP_MAX, 4, 6))
    sent = E.send(guid, agg, "mine", 8, T0)
    o = sent["out"][0]
    chk("광산으로 보낼 수 있다 (나가 있는 칸에 물건 대신 골드를 적는다)", sent["ok"] and o["place"] == "mine"
        and o["placeKr"] == "광산" and o["grade"] == "great" and o["items"] == 0 and o["gold"] == 4480, o)

    class Always(random.Random):
        """주사위가 늘 0 - 물건 곳이었다면 기술머신 · 친화력이 반드시 나왔을 굴림."""
        def random(self):
            return 0.0
    bag0 = bag(guid)
    got = E.claim(guid, o["id"], later(hours=8), rng=Always(1))
    c = got["claimed"][0]
    money_after = db.q1("SELECT money FROM users WHERE id=?", (guid,))["money"]
    chk("**받으면 골드만 들어온다** (8시간 대성공 4,000 + 주머니 4점 12% = 4,480원)", c["gold"] == 4480
        and money_after - rows_before == 4480 and got["money"] == money_after, (c.get("gold"), money_after - rows_before))
    chk("  물건 · 기술머신 · 포켓몬은 없다 (주사위가 다 나와도)", c["items"] == [] and c["tm"] is None and c["friend"] is None
        and not c.get("friendFull") and bag(guid) == bag0
        and db.q1("SELECT COUNT(*) n FROM pokemon WHERE user_id=?", (guid,))["n"] == 1, c)
    chk("  알림 글: 골드를 받았다", "4,480원" in got["message"] and "물건" not in got["message"], got["message"])
    chk("  탐험 경험치와 쉬는 시간은 다른 곳과 같다", c["growth"]["rest"] == 24 * 3600 and c["growth"]["xp"] == 0, c["growth"])
    rec = db.q1("SELECT loot FROM expedition WHERE id=?", (o["id"],))["loot"]
    chk("  받은 기록에 골드가 남는다", '"gold": 4480' in rec, rec)
    pika2 = mkmon(guid, "PIKACHU", 30)
    o2 = E.send(guid, pika2, "mine", 2, later(hours=9))["out"][0]
    got2 = E.claim(guid, o2["id"], later(hours=11), rng=random.Random(5))
    chk("  타입이 안 맞는 Lv.30 은 보통 = 2시간 600원 (성장치가 없으면 덤도 없다)", o2["grade"] == "normal"
        and got2["claimed"][0]["gold"] == 600, (o2["grade"], got2["claimed"][0].get("gold")))
    mixed = mkmon(guid, "VENUSAUR", 80)
    E.send(guid, mixed, "forest", 2, later(hours=40))
    o3 = E.send(guid, pika2, "mine", 2, later(hours=40))["out"][-1]
    got3 = E.claim(guid, None, later(hours=43), rng=random.Random(9))
    chk("  물건 곳과 같이 받으면 알림에 둘 다 적는다", "물건" in got3["message"] and "600원" in got3["message"]
        and o3["place"] == "mine", got3["message"])
    bad = [h for h in X.HOURS if '<tr><td>%d시간</td>%s</tr>' % (h, "".join(
        '<td class="n">%d</td>' % X.xp_for(h, g_) for g_ in X.GRADES)) not in sec]
    chk("탐험 경험치 세 줄", not bad, bad)
    acc, tot = 0, []
    for n_ in range(1, X.MAX_LEVEL + 1):
        acc += X.level_need(n_)
        tot.append('<td class="n">%s</td>' % format(acc, ","))
    chk("레벨마다 드는 경험치와 그 합", '<tr><td>이 레벨이 되는 데</td>%s</tr>' % "".join(
        '<td class="n">%d</td>' % X.level_need(n_) for n_ in range(1, X.MAX_LEVEL + 1)) in sec
        and '<tr><td>처음부터 모두</td>%s</tr>' % "".join(tot) in sec, acc)

    print("\n=== 기록 ===")
    for i in range(E.KEEP_DONE + 8):
        # (한 번 다녀오면 24시간 쉰다 - 27시간마다 보낸다)
        o = E.send(uid, pika, "sea", 2, later(days=5, hours=27 * i))
        E.claim(uid, o["out"][0]["id"], later(days=5, hours=27 * i + 2), rng=rng)
    kept = db.q1("SELECT COUNT(*) c FROM expedition WHERE user_id=?", (uid,))["c"]
    chk("받은 기록은 최근 %d개만 남긴다" % E.KEEP_DONE, kept == E.KEEP_DONE, kept)

    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
