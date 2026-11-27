# -*- coding: utf-8 -*-
"""열매 텃밭 (시즌 7) 서버. 서버를 띄우지 않는다 - 임시 DB 에 모듈을 직접 붙인다 (test_fishing.py 와 같은 꼴).

    python server/test_garden.py

못 박는 것 (design-notes/2026-11-26-garden-plan.md Task 1):

  1. 열리기 전(시즌 6): /api/garden* · /api/visit/water · 먹이는 404, /api/me 의 garden 은 None, 손님 view 의 garden 도 None.
  2. 심기: 씨앗 하나가 빠진다. 지닌 열매만 (노력치 열매 · 없는 열매 400), 찬 칸 409 (씨앗을 안 뺀다).
     바탕화면 파티의 풀 타입 한 마리당 10% 빨리 (셋까지), 상자 속은 안 센다.
  3. 카드는 서버 시계로 센다 - 단계 1→4, left · nextIn(6시간에서 자른다) · needsWater · yield.
  4. 물은 '준 그 순간의 단계' 비트 - 같은 단계에 두 번 줘도 하나, 익은 화분엔 안 준다.
  5. 거두기: 익은 것만, 열매 수 = yield, 가방에 (거두기 전에) 같은 열매가 있으면 그 자리에 다시 심는다, 없으면 빈 칸.
     두 스레드가 동시에 거둬도 한 번만.
  6. 하루(한국 시각) 거둠 천장 20 - 20 미만이면 그 화분은 통째로 (19 → 24), 그다음은 capped, 0시 KST 에 풀린다.
  7. 뽑기: 새싹이면 씨앗을 돌려준다, 줄기부터는 안 돌려준다. 응답 카드에 refunded (서버 시계로 가른 것) - 익은 화분도 뽑힌다.
  8. 친구 물: 지금 그 집에 놀러 가 있는 손님만. 주인은 하루 한 번 (다른 손님도 막힌다). 줄 화분이 없으면 409 이고
     하루를 안 쓴다. 자라는 화분에만 +1. 주인에게 푸시 (카드 · 이름), 손님 view 는 canWater False.
     못 주는 까닭(why)은 view 와 409 가 같은 말: empty (심은 화분 없음) · ripe (익은 화분뿐) · bonus (자라는 화분이 모두
     이미 +1) · done (오늘 이미 받음) · closed.
 11. 주인 화단이 바뀌면 (심기 · 물 · 거두기와 다시 심기 · 뽑기) 지금 놀러 와 있는 손님에게 {t: watered, garden: view} 를
     민다 - 놀러 올 때의 view 가 방문 내내 남지 않게. 손님 자신의 화단 · 손님이 없을 때는 안 민다.
  9. 먹이: 내 것 · 바탕화면 · 하루 한 번 · 가장 많은 지닌 열매 (avoid 빼고, 그것밖에 없으면 그것) · 255 면 409 (열매도 하루도
     안 쓴다) · 친밀 진화(이브이 160)는 그 자리에서 (가방 진화와 같은 evolve 모양).
 10. /api/me: 카드가 터지면 garden 칸을 뺀다 (None 은 '닫힘' 뿐). 지난 날 줄은 집안일이 치운다.
"""
import datetime
import inspect
import json
import os
import random
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-garden-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ.pop("POKET_GARDEN_FROM", None)
os.environ.pop("POKET_GARDEN_SCALE", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_HOUSEKEEP"] = "0"

from common import pokelogic as P                            # noqa: E402
from fastapi import HTTPException                            # noqa: E402

from app import config, db, deps, garden, housekeep, items, main, season, social, visit   # noqa: E402
from app import garden_routes as GR                          # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
KST = datetime.timezone(datetime.timedelta(hours=9))
POT_KEYS = {"slot", "berry", "group", "stage", "grow", "age", "left", "wetMask", "friendBonus", "ripe", "yield",
            "needsWater"}
CARD_KEYS = {"open", "pots", "harvested", "cap", "nextIn", "fedToday", "friendWater"}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


_N = [0]


def mkuser(name=None):
    _N[0] += 1
    name = name or "농부%d_%d" % (_N[0], random.randint(1000, 9999))
    uid = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,30,0,'','','')",
        (name, b"x", b"x")).lastrowid
    return uid


def uname(uid):
    return db.q1("SELECT username FROM users WHERE id=?", (uid,))["username"]


def mkmon(uid, species="PIKACHU", desk=True, happiness=None, evolve=False, slot=0):
    m = P.make_pokemon(deps.dex().get(species), 30, random.Random(3), shiny_rate=10 ** 9)
    m["noEvolve"] = not evolve
    pid = db.insert_mon(uid, m, "")
    if desk:
        db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=?", (slot, pid))
    if happiness is not None:
        db.run("UPDATE pokemon SET happiness=? WHERE id=?", (happiness, pid))
    return pid


def ctx(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def me_ctx(uid):
    c = ctx(uid)
    c["session"] = {"ip": "127.0.0.1", "expires_at": "2099-01-01T00:00:00+00:00", "token_hash": "x"}
    return c


class Season(object):
    """season.SEASON 을 잠깐 바꾼다."""

    def __init__(self, n):
        self.n = n

    def __enter__(self):
        self.old = season.SEASON
        season.SEASON = self.n

    def __exit__(self, *a):
        season.SEASON = self.old


def refused(fn, *a, **k):
    """garden.Refused 의 상태 번호. 안 막혔으면 None."""
    try:
        fn(*a, **k)
    except garden.Refused as e:
        return e.status
    return None


def http_status(fn, *a, **k):
    """HTTPException 이나 JSONResponse 의 상태 번호. 그냥 돌아오면 None."""
    try:
        r = fn(*a, **k)
    except HTTPException as e:
        return e.status_code
    return getattr(r, "status_code", None)


def body_of(r):
    """라우트가 돌려준 dict 또는 JSONResponse 의 본문."""
    if hasattr(r, "body"):
        return json.loads(r.body.decode("utf-8"))
    return r


def bag(uid, item):
    return items.bag_count(uid, item)


def secs(n):
    return datetime.timedelta(seconds=n)


def kst(y, mo, d, h=0, mi=0, s=0):
    return datetime.datetime(y, mo, d, h, mi, s, tzinfo=KST).astimezone(UTC)


def rnow():
    return datetime.datetime.now(UTC).replace(microsecond=0)


def pot(card, slot):
    return card["pots"][slot]


def day_row(uid, now):
    r = db.q1("SELECT harvested FROM garden_day WHERE user_id=? AND day=?", (uid, visit.today(now)))
    return r["harvested"] if r else 0


def befriend_online(a, b):
    """a 와 b 를 친구로 만들고 둘 다 앱이 켜져 있는 것으로 한다 (놀러 가기 소켓)."""
    social.request(a, uname(b))
    social.accept(b, a)
    for u in (a, b):
        if not visit.online(u):
            visit._add(visit.Conn(None, u))


class Pushes(object):
    """visit.push 를 가로챈다."""

    def __enter__(self):
        self.got = []
        self.real = visit.push
        visit.push = lambda u, p: self.got.append((u, p))
        return self

    def __exit__(self, *a):
        visit.push = self.real

    def to(self, uid, t):
        return [p for u, p in self.got if u == uid and p.get("t") == t]


# ---------------------------------------------------------------- 1. 닫혀 있을 때
def test_closed():
    print("\n=== 열리기 전(시즌 %d): 404 · 카드 None · 방문 view garden None ===" % (config.GARDEN_FROM - 1))
    with Season(config.GARDEN_FROM - 1):
        uid = mkuser()
        pid = mkmon(uid, happiness=100)
        items.bag_add(uid, "ORANBERRY", 3)
        c = ctx(uid)
        chk("GET /api/garden 404", http_status(GR.garden_card, c) == 404)
        chk("POST /api/garden/plant 404", http_status(GR.garden_plant, GR.PlantIn(slot=0, berry="ORANBERRY"), c) == 404)
        chk("POST /api/garden/water 404", http_status(GR.garden_water, c) == 404)
        chk("POST /api/garden/harvest 404", http_status(GR.garden_harvest, GR.HarvestIn(replant=True), c) == 404)
        chk("POST /api/garden/pull 404", http_status(GR.garden_pull, GR.SlotIn(slot=0), c) == 404)
        chk("POST /api/pokemon/{pid}/feed 404", http_status(GR.feed_pokemon, pid, GR.FeedIn(hour=12), c) == 404)
        chk("  열매 · 친밀도 그대로 (아무것도 안 했다)", bag(uid, "ORANBERRY") == 3
            and db.q1("SELECT happiness FROM pokemon WHERE id=?", (pid,))["happiness"] == 100
            and db.q1("SELECT COUNT(*) c FROM garden_pot WHERE user_id=?", (uid,))["c"] == 0)
        chk("garden.card 는 None", garden.card(uid) is None)
        me = main._me_data(me_ctx(uid))
        chk("/api/me 의 garden 은 None (칸은 있다)", "garden" in me and me["garden"] is None, me.get("garden"))
        # 놀러 가 있어도 - 물 주기 404 (why closed), 손님 view 의 garden 은 None
        host = mkuser()
        mkmon(uid, "BULBASAUR", slot=1)
        befriend_online(uid, host)
        visit.start(uid, host)
        try:
            r = visit.post_water(ctx(uid))
            chk("POST /api/visit/water 404 · why closed", getattr(r, "status_code", None) == 404
                and body_of(r).get("why") == "closed", body_of(r) if hasattr(r, "body") else r)
            v = visit._visit_of(uid)
            gv = visit.view(v, uid)
            chk("손님 view 의 garden 은 None (칸은 있다)", "garden" in gv and gv["garden"] is None, gv.get("garden"))
            chk("  GET /api/visit 도 같다", visit.state(uid)["visit"]["garden"] is None)
        finally:
            visit.end(uid)


# ---------------------------------------------------------------- 2. 심기
def test_plant():
    print("\n=== 심기 ===")
    t = rnow()
    uid = mkuser()
    items.bag_add(uid, "ORANBERRY", 2)
    items.bag_add(uid, "GREPABERRY", 1)          # 노력치 열매 (cat 'ev')
    c = garden.plant(uid, 0, "ORANBERRY", now=t)
    p0 = pot(c, 0)
    chk("심으면 카드 - 0번 화분 오랭 · 새싹 · 4시간", p0["berry"] == "ORANBERRY" and p0["stage"] == 1
        and p0["group"] == 4 and p0["grow"] == 4 * 3600, p0)
    chk("  씨앗 하나가 빠진다 (2 -> 1)", bag(uid, "ORANBERRY") == 1, bag(uid, "ORANBERRY"))
    chk("노력치 열매 400", refused(garden.plant, uid, 1, "GREPABERRY", now=t) == 400)
    chk("  노력치 열매는 그대로", bag(uid, "GREPABERRY") == 1)
    chk("가방에 없는 지닌 열매 400", refused(garden.plant, uid, 1, "SITRUSBERRY", now=t) == 400)
    chk("있지도 않은 도구 400", refused(garden.plant, uid, 1, "NOPEBERRY", now=t) == 400)
    chk("볼 400", refused(garden.plant, uid, 1, "POKEBALL", now=t) == 400)
    chk("빈 이름 400", refused(garden.plant, uid, 1, "", now=t) == 400)
    chk("찬 칸 409", refused(garden.plant, uid, 0, "ORANBERRY", now=t) == 409)
    chk("  찬 칸이면 씨앗을 안 뺀다", bag(uid, "ORANBERRY") == 1, bag(uid, "ORANBERRY"))
    chk("칸 3 · -1 은 400", refused(garden.plant, uid, 3, "ORANBERRY", now=t) == 400
        and refused(garden.plant, uid, -1, "ORANBERRY", now=t) == 400)
    chk("  그래도 씨앗 그대로", bag(uid, "ORANBERRY") == 1)
    # 라우트 - 소문자도 받는다
    r = GR.garden_plant(GR.PlantIn(slot=2, berry="oranberry"), ctx(uid))
    chk("라우트: 소문자 이름도 심긴다 -> 카드", r["open"] is True and pot(r, 2)["berry"] == "ORANBERRY"
        and bag(uid, "ORANBERRY") == 0, pot(r, 2))
    chk("라우트: 없으면 400", http_status(GR.garden_plant, GR.PlantIn(slot=1, berry="ORANBERRY"), ctx(uid)) == 400)
    chk("라우트: 찬 칸 409", http_status(GR.garden_plant, GR.PlantIn(slot=0, berry="ORANBERRY"), ctx(uid)) == 409)

    print("  -- 풀 타입 빠르기")
    g = mkuser()
    items.bag_add(g, "ORANBERRY", 3)
    mkmon(g, "BULBASAUR", slot=0)                  # 풀 · 독
    mkmon(g, "ODDISH", slot=1)                     # 풀 · 독
    mkmon(g, "PIKACHU", slot=2)                    # 풀 아님
    mkmon(g, "CHIKORITA", desk=False)              # 상자 속 풀은 안 센다
    c = garden.plant(g, 0, "ORANBERRY", now=t)
    chk("바탕화면에 풀 둘: 20% 빠름 (14400 -> 11520)", pot(c, 0)["grow"] == 11520, pot(c, 0)["grow"])
    for sp in ("BELLSPROUT", "TANGELA", "SUNKERN"):
        mkmon(g, sp, slot=3)
    c = garden.plant(g, 1, "ORANBERRY", now=t)
    chk("풀 다섯: 30% 에서 멈춘다 (10080)", pot(c, 1)["grow"] == 10080, pot(c, 1)["grow"])
    real = config.GARDEN_SCALE
    config.GARDEN_SCALE = 0.01
    try:
        c = garden.plant(g, 2, "ORANBERRY", now=t)
        chk("GARDEN_SCALE 0.01 을 곱한다 (10080 x 0.01 = 101)", pot(c, 2)["grow"] == 101, pot(c, 2)["grow"])
    finally:
        config.GARDEN_SCALE = real


# ---------------------------------------------------------------- 3. 단계 · 카드
def test_stage_and_card():
    print("\n=== 단계 · 카드 (시각 주입) ===")
    t = rnow()
    uid = mkuser()
    items.bag_add(uid, "ORANBERRY", 1)
    garden.plant(uid, 0, "ORANBERRY", now=t)
    c = garden.card(uid, now=t)
    chk("카드 칸 (계약)", set(c) == CARD_KEYS, sorted(c))
    chk("  open · harvested 0 · cap 20 · fedToday [] · friendWater None",
        c["open"] is True and c["harvested"] == 0 and c["cap"] == config.GARDEN_CAP == 20
        and c["fedToday"] == [] and c["friendWater"] is None, c)
    chk("화분 셋 · 칸 번호 0 1 2", [p["slot"] for p in c["pots"]] == [0, 1, 2])
    chk("  화분 칸 (계약)", all(set(p) == POT_KEYS for p in c["pots"]), [sorted(p) for p in c["pots"]])
    e = pot(c, 1)
    chk("빈 화분: 0단계 · 나머지는 None/0/False",
        e["berry"] is None and e["group"] is None and e["stage"] == 0 and e["grow"] is None and e["age"] is None
        and e["left"] is None and e["wetMask"] == 0 and e["friendBonus"] == 0 and e["ripe"] is False
        and e["yield"] is None and e["needsWater"] is False, e)
    p = pot(c, 0)
    chk("막 심음: 새싹 · age 0 · left 14400 · 물 필요 · yield 1",
        p["stage"] == 1 and p["age"] == 0 and p["left"] == 14400 and p["needsWater"] is True
        and p["ripe"] is False and p["yield"] == 1, p)
    chk("  nextIn = 4800 (1/3)", c["nextIn"] == 4800, c["nextIn"])
    c = garden.card(uid, now=t + secs(4799))
    chk("4799초: 아직 새싹 · nextIn 1", pot(c, 0)["stage"] == 1 and c["nextIn"] == 1, (pot(c, 0)["stage"], c["nextIn"]))
    c = garden.card(uid, now=t + secs(4800))
    chk("4800초: 줄기 · left 9600 · nextIn 4800",
        pot(c, 0)["stage"] == 2 and pot(c, 0)["left"] == 9600 and c["nextIn"] == 4800, (pot(c, 0), c["nextIn"]))
    c = garden.card(uid, now=t + secs(9600))
    chk("9600초: 꽃", pot(c, 0)["stage"] == 3 and pot(c, 0)["needsWater"] is True, pot(c, 0))
    c = garden.card(uid, now=t + secs(14400))
    p = pot(c, 0)
    chk("14400초: 익음 · ripe · left 0 · 물 필요 없음", p["stage"] == 4 and p["ripe"] is True and p["left"] == 0
        and p["needsWater"] is False and p["yield"] == 1, p)
    chk("  자라는 화분이 없으면 nextIn None", c["nextIn"] is None, c["nextIn"])
    c = garden.card(uid, now=t + secs(10 ** 6))
    chk("밤새 꺼져 있다 켜도 익음 (age 가 그대로 커진다)", pot(c, 0)["stage"] == 4 and pot(c, 0)["age"] == 10 ** 6
        and pot(c, 0)["left"] == 0, pot(c, 0))
    # nextIn 은 가장 가까운 화분 · 6시간에서 자른다
    u2 = mkuser()
    items.bag_add(u2, "LIECHIBERRY", 1)
    items.bag_add(u2, "ORANBERRY", 1)
    real = config.GARDEN_SCALE
    config.GARDEN_SCALE = 2.0                      # 16시간 x 2 = 32시간 - 단계 하나가 10시간 40분
    try:
        garden.plant(u2, 0, "LIECHIBERRY", now=t)
    finally:
        config.GARDEN_SCALE = real
    c = garden.card(u2, now=t)
    chk("다음 단계가 10시간 넘게 남아도 nextIn 은 6시간 (21600)", c["nextIn"] == 21600, c["nextIn"])
    garden.plant(u2, 1, "ORANBERRY", now=t + secs(100))
    c = garden.card(u2, now=t + secs(200))
    chk("  여러 화분이면 가장 가까운 것 (오랭 4700)", c["nextIn"] == 4700, c["nextIn"])
    r = GR.garden_card(ctx(u2))
    chk("GET /api/garden = 카드", set(r) == CARD_KEYS and pot(r, 0)["berry"] == "LIECHIBERRY", sorted(r))


# ---------------------------------------------------------------- 4. 물
def test_water_per_stage():
    print("\n=== 물 - 단계마다 한 번 ===")
    t = rnow()
    uid = mkuser()
    items.bag_add(uid, "ORANBERRY", 2)
    garden.plant(uid, 0, "ORANBERRY", now=t)
    r = garden.water(uid, now=t + secs(10))
    chk("새싹에 물: watered 1 · wetMask 1 · 물 필요 없음", r["watered"] == 1 and pot(r["card"], 0)["wetMask"] == 1
        and pot(r["card"], 0)["needsWater"] is False, r)
    r = garden.water(uid, now=t + secs(20))
    chk("  같은 단계에 또: watered 0 · 비트 그대로", r["watered"] == 0 and pot(r["card"], 0)["wetMask"] == 1, r)
    c = garden.card(uid, now=t + secs(4800))
    chk("줄기가 되면 다시 물 필요", pot(c, 0)["needsWater"] is True, pot(c, 0))
    r = garden.water(uid, now=t + secs(4800))
    chk("줄기에 물: wetMask 3 · yield 3", pot(r["card"], 0)["wetMask"] == 3 and pot(r["card"], 0)["yield"] == 3, r)
    r = garden.water(uid, now=t + secs(9700))
    chk("꽃에 물: wetMask 7 · yield 4 (최대)", pot(r["card"], 0)["wetMask"] == 7 and pot(r["card"], 0)["yield"] == 4, r)
    r = garden.water(uid, now=t + secs(14400))
    chk("익은 화분엔 안 준다: watered 0 · wetMask 7", r["watered"] == 0 and pot(r["card"], 0)["wetMask"] == 7, r)
    # 물이 필요한 화분 모두에 한 번에
    garden.plant(uid, 1, "ORANBERRY", now=t + secs(14400))
    items.bag_add(uid, "LUMBERRY", 1)
    garden.plant(uid, 2, "LUMBERRY", now=t + secs(14400 - 4800))      # 줄기
    r = garden.water(uid, now=t + secs(14400))
    chk("한 번 누르면 필요한 화분 모두 (새싹 1 · 줄기 1 = 2)", r["watered"] == 2
        and pot(r["card"], 1)["wetMask"] == 1 and pot(r["card"], 2)["wetMask"] == 2, r)
    r = GR.garden_water(ctx(uid))
    chk("라우트: {watered, card}", set(r) == {"watered", "card"} and set(r["card"]) == CARD_KEYS, sorted(r))
    e = mkuser()
    chk("빈 화단: watered 0", garden.water(e, now=t)["watered"] == 0)


# ---------------------------------------------------------------- 5. 거두기
def test_harvest():
    print("\n=== 거두기 ===")
    t = rnow()
    uid = mkuser()
    items.bag_add(uid, "ORANBERRY", 3)
    items.bag_add(uid, "LUMBERRY", 1)
    garden.plant(uid, 0, "ORANBERRY", now=t)
    garden.plant(uid, 1, "LUMBERRY", now=t)
    garden.water(uid, now=t + secs(10))                       # 둘 다 새싹 비트
    garden.water(uid, now=t + secs(5000))                     # 둘 다 줄기 비트
    garden.plant(uid, 2, "ORANBERRY", now=t + secs(10000))   # 늦게 심은 것 - 거둘 때 아직 자란다
    chk("거두기 전 가방: 오랭 1 · 리샘 0", bag(uid, "ORANBERRY") == 1 and bag(uid, "LUMBERRY") == 0)
    r = garden.harvest(uid, True, now=t + secs(9000))
    chk("익은 게 없으면 got [] · 아무것도 안 바뀐다", r["got"] == [] and r["replanted"] == [] and r["capped"] is False
        and bag(uid, "ORANBERRY") == 1, r)
    now = t + secs(14400)
    r = garden.harvest(uid, True, now=now)
    chk("응답 칸 {got, replanted, capped, card}", set(r) == {"got", "replanted", "capped", "card"}, sorted(r))
    got = dict((x["berry"], x["n"]) for x in r["got"])
    chk("익은 둘만: 오랭 3 · 리샘 3 (기본 + 물 두 단계)", got == {"ORANBERRY": 3, "LUMBERRY": 3}, r["got"])
    chk("  kr 이름이 같이 온다", all(x["kr"] == items.name_of(x["berry"]) for x in r["got"]), r["got"])
    chk("가방에 있던 오랭으로 0번을 다시 심는다 · 리샘은 없어서 빈 칸", r["replanted"] == [0], r["replanted"])
    c = r["card"]
    chk("  0번: 새로 심은 새싹 (물 · 보너스 비움)", pot(c, 0)["berry"] == "ORANBERRY" and pot(c, 0)["stage"] == 1
        and pot(c, 0)["age"] == 0 and pot(c, 0)["wetMask"] == 0 and pot(c, 0)["friendBonus"] == 0, pot(c, 0))
    chk("  1번: 빈 칸", pot(c, 1)["berry"] is None and pot(c, 1)["stage"] == 0, pot(c, 1))
    chk("  2번: 안 익은 건 그대로", pot(c, 2)["berry"] == "ORANBERRY" and pot(c, 2)["stage"] == 1, pot(c, 2))
    chk("가방: 오랭 1 - 씨앗 1 + 3 = 3 · 리샘 3", bag(uid, "ORANBERRY") == 3 and bag(uid, "LUMBERRY") == 3,
        (bag(uid, "ORANBERRY"), bag(uid, "LUMBERRY")))
    chk("오늘 거둔 수 6 (카드 · 표)", c["harvested"] == 6 and day_row(uid, now) == 6, (c["harvested"], day_row(uid, now)))
    r = garden.harvest(uid, True, now=now)
    chk("곧바로 또 거두면 got [] (두 번 안 준다)", r["got"] == [] and bag(uid, "ORANBERRY") == 3, r)
    r = garden.harvest(uid, False, now=t + secs(10000 + 14400))
    chk("replant False: 가방에 있어도 빈 칸으로", r["replanted"] == [] and pot(r["card"], 2)["berry"] is None
        and dict((x["berry"], x["n"]) for x in r["got"]) == {"ORANBERRY": 1}, r)
    r = GR.garden_harvest(GR.HarvestIn(replant=True), ctx(uid))
    chk("라우트: 같은 모양", set(r) == {"got", "replanted", "capped", "card"}, sorted(r))

    print("  -- 두 스레드가 동시에")
    u = mkuser()
    items.bag_add(u, "ORANBERRY", 1)
    garden.plant(u, 0, "ORANBERRY", now=t)
    out, errs = [], []
    gate = threading.Barrier(2)

    def go():
        try:
            gate.wait(5)
            out.append(garden.harvest(u, True, now=t + secs(14400)))
        except Exception as e:                               # noqa: BLE001
            errs.append(repr(e))
    ths = [threading.Thread(target=go) for _ in range(2)]
    for th in ths:
        th.start()
    for th in ths:
        th.join(20)
    n_got = sorted(sum(x["n"] for x in r["got"]) for r in out)
    chk("둘 다 끝났다 (오류 없음)", len(out) == 2 and not errs, errs)
    chk("  한쪽만 받는다 (1 · 0)", n_got == [0, 1], n_got)
    chk("  가방 +1 · 오늘 1 개", bag(u, "ORANBERRY") == 1 and day_row(u, t + secs(14400)) == 1,
        (bag(u, "ORANBERRY"), day_row(u, t + secs(14400))))


# ---------------------------------------------------------------- 6. 하루 천장
def test_daily_cap():
    print("\n=== 하루 거둠 천장 (한국 시각) ===")
    uid = mkuser()
    items.bag_add(uid, "OCCABERRY", 1)            # 8시간
    items.bag_add(uid, "ORANBERRY", 1)            # 4시간
    t = kst(2030, 6, 3, 10, 0)                    # 6/3 10:00 KST
    garden.plant(uid, 0, "OCCABERRY", now=t)
    garden.plant(uid, 1, "ORANBERRY", now=t)
    garden.water(uid, now=t + secs(10))                     # 둘 다 새싹
    garden.water(uid, now=t + secs(9700))                   # 오카 줄기 · 오랭 꽃
    garden.water(uid, now=t + secs(19300))                  # 오카 꽃 (오랭은 익음 - 안 준다)
    now = kst(2030, 6, 3, 18, 0)
    c = garden.card(uid, now=now)
    chk("오카 5개짜리 (2 + 물 셋)", pot(c, 0)["ripe"] and pot(c, 0)["yield"] == 5, pot(c, 0))
    oran_n = pot(c, 1)["yield"]
    db.run("INSERT INTO garden_day (user_id, day, harvested) VALUES (?,?,?)", (uid, visit.today(now), 19))
    r = garden.harvest(uid, False, now=now)
    chk("19개 거둔 뒤: 오카 5개를 통째로 (19 -> 24)", [(x["berry"], x["n"]) for x in r["got"]] == [("OCCABERRY", 5)]
        and r["card"]["harvested"] == 24, (r["got"], r["card"]["harvested"]))
    chk("  그다음 오랭은 천장에 걸려 기다린다 (capped · 익은 채)", r["capped"] is True and pot(r["card"], 1)["ripe"]
        and bag(uid, "ORANBERRY") == 0, (r["capped"], pot(r["card"], 1)))
    r = garden.harvest(uid, False, now=kst(2030, 6, 3, 23, 59, 59))
    chk("23:59:59 KST: 아직 capped · got []", r["got"] == [] and r["capped"] is True, r)
    r = garden.harvest(uid, False, now=kst(2030, 6, 4, 0, 0, 0))
    chk("0시 KST 에 풀린다: 오랭을 거둔다", [(x["berry"], x["n"]) for x in r["got"]] == [("ORANBERRY", oran_n)]
        and r["capped"] is False and r["card"]["harvested"] == oran_n, r)
    chk("  0시 KST = 전날 15:00 UTC", visit.today(kst(2030, 6, 4)) == "2030-06-04"
        and kst(2030, 6, 4).hour == 15)
    chk("  6/3 줄은 24 그대로", day_row(uid, now) == 24)


# ---------------------------------------------------------------- 7. 뽑기
def test_pull():
    print("\n=== 뽑기 ===")
    t = rnow()
    uid = mkuser()
    items.bag_add(uid, "ORANBERRY", 1)
    garden.plant(uid, 0, "ORANBERRY", now=t)
    chk("심으면 씨앗이 빠진다", bag(uid, "ORANBERRY") == 0)
    c = garden.pull(uid, 0, now=t + secs(60))
    chk("새싹에서 뽑으면 씨앗을 돌려받는다 · 빈 칸", bag(uid, "ORANBERRY") == 1 and pot(c, 0)["berry"] is None, pot(c, 0))
    chk("  응답에 refunded True (서버 시계로 가른다 - 앱의 단계는 늦을 수 있다)", c.get("refunded") is True, c.get("refunded"))
    garden.plant(uid, 0, "ORANBERRY", now=t)
    c = garden.pull(uid, 0, now=t + secs(4800))
    chk("줄기에서 뽑으면 안 돌려준다 · 빈 칸", bag(uid, "ORANBERRY") == 0 and pot(c, 0)["berry"] is None, pot(c, 0))
    chk("  응답에 refunded False", c.get("refunded") is False, c.get("refunded"))
    items.bag_add(uid, "ORANBERRY", 1)
    garden.plant(uid, 0, "ORANBERRY", now=t)
    c = garden.pull(uid, 0, now=t + secs(14400))
    chk("익은 화분도 뽑힌다 (설계) - 열매 · 씨앗 없음 · refunded False", c.get("refunded") is False
        and pot(c, 0)["berry"] is None and bag(uid, "ORANBERRY") == 0, (c.get("refunded"), pot(c, 0)))
    chk("빈 칸 뽑기 409", refused(garden.pull, uid, 0, now=t) == 409)
    chk("칸 5 는 400", refused(garden.pull, uid, 5, now=t) == 400)
    items.bag_add(uid, "ORANBERRY", 1)
    garden.plant(uid, 1, "ORANBERRY")
    r = GR.garden_pull(GR.SlotIn(slot=1), ctx(uid))
    chk("라우트: 카드 + refunded · 씨앗을 돌려받는다", set(r) == CARD_KEYS | {"refunded"} and r["refunded"] is True
        and pot(r, 1)["berry"] is None and bag(uid, "ORANBERRY") == 1, (sorted(r), pot(r, 1)))


# ---------------------------------------------------------------- 8. 친구 물
def test_friend_water():
    print("\n=== 친구 물 (놀러 가기) ===")
    host, a, b, stranger = mkuser(), mkuser(), mkuser(), mkuser()
    for g in (a, b, stranger):
        mkmon(g, "PIKACHU")
    befriend_online(a, host)
    befriend_online(b, host)
    t = rnow()
    with Pushes() as ps:
        chk("놀러 가 있지 않으면 409", http_status(visit.water, stranger, now=t) == 409)
        chk("  라우트도 409", http_status(visit.post_water, ctx(stranger)) == 409)
        visit.start(a, host)
        try:
            chk("주인은 물을 못 준다 (손님만) 409", http_status(visit.water, host, now=t) == 409)
            v = visit._visit_of(a)
            gv = visit.view(v, a)["garden"]
            chk("빈 화단: view canWater False · why empty · 화분 셋", gv["canWater"] is False and gv["why"] == "empty"
                and len(gv["pots"]) == 3 and all(set(p) == {"berry", "stage", "friendBonus"} for p in gv["pots"]), gv)
            chk("  주인 view 에는 garden 이 없다 (내 화단은 카드로)", "garden" not in visit.view(v, host))
            r = visit.post_water(ctx(a))
            chk("빈 화단에 물: 409 · why empty", http_status(visit.post_water, ctx(a)) == 409
                and body_of(r) == {"error": body_of(r)["error"], "why": "empty"} and body_of(r)["error"], body_of(r))
            chk("  하루를 안 쓴다 (garden_water 줄 없음)",
                db.q1("SELECT COUNT(*) c FROM garden_water WHERE host_id=?", (host,))["c"] == 0)
            items.bag_add(host, "ORANBERRY", 2)
            items.bag_add(host, "LUMBERRY", 1)
            garden.plant(host, 0, "ORANBERRY", now=t - secs(20000))      # 이미 익음
            garden.plant(host, 1, "ORANBERRY", now=t - secs(60))
            garden.plant(host, 2, "LUMBERRY", now=t - secs(6000))         # 줄기
            gv = visit.view(v, a)["garden"]
            chk("심은 뒤 view: canWater True · why None · 화분 모습", gv["canWater"] is True and gv["why"] is None
                and [p["berry"] for p in gv["pots"]] == ["ORANBERRY", "ORANBERRY", "LUMBERRY"]
                and [p["stage"] for p in gv["pots"]] == [4, 1, 2], gv)
            del ps.got[:]
            r = visit.post_water(ctx(a))
            chk("물 주기: ok · bonus 2 (자라는 둘만, 익은 건 빼고)", r.get("ok") is True and r["bonus"] == 2, r)
            chk("  응답 garden 은 view: canWater False · why done", r["garden"]["canWater"] is False
                and r["garden"]["why"] == "done", r["garden"])
            c = garden.card(host)
            chk("주인 화분: 익은 0번 그대로 0 · 1번 2번 +1", [p["friendBonus"] for p in c["pots"]] == [0, 1, 1],
                [p["friendBonus"] for p in c["pots"]])
            chk("  yield 에 +1 (오랭 새싹 1 -> 2)", pot(c, 1)["yield"] == 2, pot(c, 1))
            chk("  카드 friendWater = 준 사람 이름", c["friendWater"] == {"from": uname(a)}, c["friendWater"])
            hw = ps.to(host, "water")
            chk("주인에게 푸시 {t: water, from, garden: 카드}", len(hw) == 1 and hw[0]["from"] == uname(a)
                and set(hw[0]["garden"]) == CARD_KEYS and hw[0]["garden"]["friendWater"] == {"from": uname(a)}, hw)
            gw = ps.to(a, "watered")
            chk("손님에게 푸시 {t: watered, garden: view}", len(gw) == 1 and gw[0]["garden"]["canWater"] is False, gw)
            chk("손님 view: canWater False · why done", visit.view(v, a)["garden"]["why"] == "done")
            r = visit.post_water(ctx(a))
            chk("같은 날 또: 409 · why done", http_status(visit.post_water, ctx(a)) == 409
                and body_of(r)["why"] == "done", body_of(r))
            chk("  보너스는 그대로 1 (몇 번이든 +1)", [p["friendBonus"] for p in garden.card(host)["pots"]] == [0, 1, 1])
        finally:
            visit.end(a)
        visit.start(b, host)
        try:
            r = visit.post_water(ctx(b))
            chk("다른 손님도 그날은 막힌다 (받는 쪽 하루 한 번) 409 done", http_status(visit.post_water, ctx(b)) == 409
                and body_of(r)["why"] == "done", body_of(r))
            chk("  garden_water 는 주인 · 날 하나에 한 줄",
                db.q1("SELECT COUNT(*) c FROM garden_water WHERE host_id=?", (host,))["c"] == 1)
        finally:
            visit.end(b)

    print("  -- 다음 날 (시각 주입)")
    h2 = mkuser()
    befriend_online(a, h2)
    befriend_online(b, h2)
    items.bag_add(h2, "ORANBERRY", 2)
    f = kst(2030, 6, 1, 22, 0)                         # 6/1 22:00 KST - 4시간짜리가 자정을 넘겨 자란다
    garden.plant(h2, 0, "ORANBERRY", now=f)
    garden.plant(h2, 1, "ORANBERRY", now=f)
    with Pushes():
        visit.start(a, h2)
        try:
            chk("6/1: 물 · bonus 2", visit.water(a, now=f + secs(60))["bonus"] == 2)
        finally:
            visit.end(a)
        visit.start(b, h2)
        try:
            mid = kst(2030, 6, 2, 0, 0, 1)
            try:
                visit.water(b, now=mid)
                st = None
            except garden.Refused as e:
                st = (e.status, e.why)
            chk("6/2: 자라는 화분이 모두 이미 +1 이면 409 bonus (하루를 안 쓴다)", st == (409, "bonus"), st)
            fv = garden.friend_view(h2, now=mid)
            chk("  friend_view(now) 도 bonus - '심은 화분 없음' 이 아니다", fv["why"] == "bonus"
                and fv["canWater"] is False, fv)
            chk("  6/2 줄 없음", db.q1("SELECT COUNT(*) c FROM garden_water WHERE host_id=? AND day='2030-06-02'",
                                      (h2,))["c"] == 0)
            items.bag_add(h2, "LUMBERRY", 1)
            garden.plant(h2, 2, "LUMBERRY", now=mid)
            chk("  새로 심으면 그날 물: bonus 1", visit.water(b, now=mid + secs(5))["bonus"] == 1)
            fv = garden.friend_view(h2, now=mid + secs(6))
            chk("  friend_view(now) 도 done", fv["why"] == "done" and fv["canWater"] is False, fv)
        finally:
            visit.end(b)


def test_friend_why():
    print("\n=== 친구 물을 못 줄 때의 까닭 - view 의 why 와 409 의 why 가 같은 말 ===")
    host, g = mkuser(), mkuser()
    mkmon(g, "PIKACHU")
    befriend_online(g, host)
    t = rnow()
    items.bag_add(host, "ORANBERRY", 3)

    def ask():
        """(view why, view canWater, 409 상태, 409 why, 409 글). 막히면 하루를 안 쓰므로 몇 번이든 물어볼 수 있다."""
        gv = visit.view(visit._visit_of(g), g)["garden"]
        r = visit.post_water(ctx(g))
        b = body_of(r)
        return gv["why"], gv["canWater"], getattr(r, "status_code", None), b.get("why"), b.get("error")

    def water_rows():
        return db.q1("SELECT COUNT(*) c FROM garden_water WHERE host_id=?", (host,))["c"]
    texts = {}
    with Pushes():
        visit.start(g, host)
        try:
            w = ask()
            chk("아무것도 안 심음: empty (view · 409 같은 말)", w[:4] == ("empty", False, 409, "empty"), w)
            texts["empty"] = w[4]
            garden.plant(host, 0, "ORANBERRY", now=t - secs(20000))       # 이미 익음
            w = ask()
            chk("익은 화분뿐: ripe ('심은 화분 없음' 이 아니다)", w[:4] == ("ripe", False, 409, "ripe"), w)
            texts["ripe"] = w[4]
            garden.plant(host, 1, "ORANBERRY", now=t - secs(60))          # 새싹 - 어제 친구 물을 받았다고 친다
            db.run("UPDATE garden_pot SET friend_bonus=1 WHERE user_id=? AND slot=1", (host,))
            w = ask()
            chk("익은 것 + 자라는 것이 모두 이미 +1: bonus", w[:4] == ("bonus", False, 409, "bonus"), w)
            texts["bonus"] = w[4]
            garden.pull(host, 0, now=t)
            w = ask()
            chk("  자라는 것만 있고 모두 이미 +1 이어도 bonus", w[:4] == ("bonus", False, 409, "bonus"), w)
            chk("막힌 동안 하루를 안 쓴다 (garden_water 줄 없음)", water_rows() == 0, water_rows())
            chk("  409 글이 까닭마다 다르다", len(set(texts.values())) == 3 and all(texts.values()), texts)
            chk("  bonus 글은 '자라는 화분이 없음' 이 아니다", "자라는 화분이 없음" not in texts["bonus"], texts["bonus"])
            garden.plant(host, 2, "ORANBERRY", now=t - secs(30))          # 새싹 · +1 없음
            gv = visit.view(visit._visit_of(g), g)["garden"]
            chk("+1 이 없는 자라는 화분이 생기면 canWater True · why None", gv["canWater"] is True and gv["why"] is None, gv)
            r = visit.post_water(ctx(g))
            chk("  물을 주면 bonus 1 (이미 +1 인 화분은 빼고)", body_of(r).get("bonus") == 1, body_of(r))
            w = ask()
            chk("그다음은 done (view · 409 같은 말)", w[:4] == ("done", False, 409, "done"), w)
        finally:
            visit.end(g)


def test_guest_push():
    print("\n=== 주인 화단이 바뀌면 놀러 와 있는 손님에게 새 view 를 민다 ===")
    host, g = mkuser(), mkuser()
    mkmon(g, "PIKACHU")
    befriend_online(g, host)
    t = rnow()
    items.bag_add(host, "ORANBERRY", 3)
    items.bag_add(host, "LUMBERRY", 1)
    with Pushes() as ps:
        garden.plant(host, 2, "ORANBERRY", now=t)
        chk("놀러 온 손님이 없으면 아무것도 안 민다", ps.got == [], ps.got)
        garden.pull(host, 2, now=t)                                    # 새싹 - 씨앗을 돌려받고 빈 화단으로
        visit.start(g, host)
        try:
            chk("놀러 올 때 빈 화단: view why empty", visit.view(visit._visit_of(g), g)["garden"]["why"] == "empty")
            del ps.got[:]
            garden.plant(host, 0, "ORANBERRY", now=t)
            w = ps.to(g, "watered")
            chk("주인이 심으면 손님에게 {t: watered, garden: view} · canWater True", len(w) == 1
                and w[0]["garden"]["canWater"] is True and w[0]["garden"]["why"] is None
                and [(p["berry"], p["stage"]) for p in w[0]["garden"]["pots"]] == [("ORANBERRY", 1), (None, 0), (None, 0)],
                w)
            chk("  주인 화면에는 안 민다", [u for u, _p in ps.got] == [g], ps.got)
            del ps.got[:]
            garden.water(host, now=t + secs(10))
            chk("주인이 물을 주면 민다", len(ps.to(g, "watered")) == 1, ps.got)
            del ps.got[:]
            garden.water(host, now=t + secs(20))
            chk("  물이 안 갔으면 (같은 단계에 또) 안 민다", ps.got == [], ps.got)
            garden.harvest(host, True, now=t + secs(9000))
            chk("  익은 게 없는 거두기도 안 민다", ps.got == [], ps.got)
            garden.harvest(host, True, now=t + secs(14400))               # 가방의 오랭으로 다시 심는다
            w = ps.to(g, "watered")
            chk("거두고 다시 심으면 민다 - 새싹으로 · canWater True", len(w) == 1
                and w[0]["garden"]["pots"][0]["stage"] == 1 and w[0]["garden"]["canWater"] is True, w)
            del ps.got[:]
            garden.pull(host, 0, now=t + secs(14460))
            w = ps.to(g, "watered")
            chk("뽑으면 민다 - 빈 화단 · why empty", len(w) == 1 and w[0]["garden"]["pots"][0]["berry"] is None
                and w[0]["garden"]["why"] == "empty", w)
            del ps.got[:]
            r = GR.garden_plant(GR.PlantIn(slot=1, berry="LUMBERRY"), ctx(host))
            chk("라우트로 심어도 민다", set(r) == CARD_KEYS and len(ps.to(g, "watered")) == 1, ps.got)
            del ps.got[:]
            visit.water(g)
            chk("친구 물은 손님에게 한 번만 (visit.water 가 미는 것 - 겹치지 않는다)",
                len(ps.to(g, "watered")) == 1 and ps.to(g, "watered")[0]["garden"]["why"] == "done", ps.got)
            del ps.got[:]
            items.bag_add(g, "ORANBERRY", 1)
            garden.plant(g, 0, "ORANBERRY", now=t)
            chk("손님이 제 화단을 바꾸면 아무에게도 안 민다 (손님은 주인이 아니다)", ps.got == [], ps.got)
            # 친구 화단 view 가 터져도 주인의 심기는 된다 (이미 썼다)
            real_fv = garden.friend_view

            def boom(*a, **k):
                raise RuntimeError("시험용 view 실패")
            garden.friend_view = boom
            try:
                items.bag_add(host, "ORANBERRY", 1)
                c = garden.plant(host, 0, "ORANBERRY", now=t + secs(14500))
                chk("view 가 터져도 심기는 된다 (카드)", pot(c, 0)["berry"] == "ORANBERRY", pot(c, 0))
            except Exception as e:                               # noqa: BLE001
                chk("view 가 터져도 심기는 된다 (카드)", False, repr(e))
            finally:
                garden.friend_view = real_fv
        finally:
            visit.end(g)
        del ps.got[:]
        garden.pull(host, 0, now=t + secs(14500))
        chk("방문이 끝난 뒤에는 안 민다", ps.to(g, "watered") == [], ps.got)


# ---------------------------------------------------------------- 9. 먹이
def test_feed():
    print("\n=== 열매 먹이기 ===")
    t = rnow()
    uid, other = mkuser(), mkuser()
    p1 = mkmon(uid, "PIKACHU", happiness=100, slot=0)
    boxed = mkmon(uid, "PIKACHU", desk=False, happiness=100)
    eevee = mkmon(uid, "EEVEE", happiness=155, evolve=True, slot=1)
    # 페어리 기술을 알면 님피아 갈래가 먼저다 (evolution.branches) - 에브이를 보려고 기술을 몸통박치기 하나로
    db.run("UPDATE pokemon SET moves=? WHERE id=?", (json.dumps(["TACKLE"]), eevee))
    full = mkmon(uid, "PIKACHU", happiness=255, slot=2)
    near = mkmon(uid, "PIKACHU", happiness=250, slot=3)
    theirs = mkmon(other, "PIKACHU", happiness=100)
    items.bag_add(uid, "ORANBERRY", 5)
    items.bag_add(uid, "LUMBERRY", 3)
    items.bag_add(uid, "GREPABERRY", 9)           # 노력치 열매 - 지닌 열매가 아니라 안 준다

    def hp(pid):
        return db.q1("SELECT happiness FROM pokemon WHERE id=?", (pid,))["happiness"]

    def fed_rows(pid):
        return db.q1("SELECT COUNT(*) c FROM feed_day WHERE pokemon_id=?", (pid,))["c"]
    chk("상자 속 포켓몬 409", refused(garden.feed, uid, boxed, now=t) == 409)
    chk("  열매 · 친밀도 · 하루 그대로", bag(uid, "ORANBERRY") == 5 and hp(boxed) == 100 and fed_rows(boxed) == 0)
    chk("남의 포켓몬 409", refused(garden.feed, uid, theirs, now=t) == 409 and hp(theirs) == 100)
    chk("없는 포켓몬 409", refused(garden.feed, uid, 10 ** 8, now=t) == 409)
    r = garden.feed(uid, p1, now=t)
    chk("가장 많은 지닌 열매 (오랭 5 > 리샘 3, 노력치 열매는 빼고)", r["berry"] == "ORANBERRY" and r["kr"] == "오랭열매", r)
    chk("  +10 · 110 · evolve None", r["gain"] == 10 and r["happiness"] == 110 and hp(p1) == 110
        and r["evolve"] is None, r)
    chk("  응답 칸 (계약)", set(r) == {"berry", "kr", "gain", "happiness", "evolve"}, sorted(r))
    chk("  열매 하나 (5 -> 4)", bag(uid, "ORANBERRY") == 4 and bag(uid, "GREPABERRY") == 9)
    chk("하루 한 번 409", refused(garden.feed, uid, p1, now=t + secs(60)) == 409)
    chk("  두 번째는 열매를 안 쓴다", bag(uid, "ORANBERRY") == 4 and hp(p1) == 110)
    chk("카드 fedToday 에 실린다", garden.card(uid, now=t)["fedToday"] == [p1], garden.card(uid, now=t)["fedToday"])
    r = garden.feed(uid, eevee, avoid="oranberry", hour=12, now=t)
    chk("avoid(지금 미끼)는 빼고 고른다 -> 리샘", r["berry"] == "LUMBERRY" and bag(uid, "LUMBERRY") == 2
        and bag(uid, "ORANBERRY") == 4, r)
    ev = r["evolve"] or {}
    chk("이브이 155 -> 165, 낮이면 에브이로 그 자리 진화", r["happiness"] == 165 and ev.get("to") == "ESPEON", r)
    chk("  evolve 는 가방 진화와 같은 모양",
        {"from", "fromKr", "fromNum", "to", "toKr", "toNum", "learned", "pending", "pendingIds"} <= set(ev), sorted(ev))
    chk("  DB 의 종도 바뀌었다", db.q1("SELECT species FROM pokemon WHERE id=?", (eevee,))["species"] == "ESPEON")
    before = (bag(uid, "ORANBERRY"), bag(uid, "LUMBERRY"))
    chk("255 면 409", refused(garden.feed, uid, full, now=t) == 409)
    chk("  열매도 하루도 안 쓴다", (bag(uid, "ORANBERRY"), bag(uid, "LUMBERRY")) == before and fed_rows(full) == 0
        and hp(full) == 255)
    r = garden.feed(uid, near, now=t)
    chk("250 이면 +5 에서 멈춘다 (gain 5 · 255)", r["gain"] == 5 and r["happiness"] == 255 and hp(near) == 255, r)
    r = garden.feed(uid, p1, now=t + datetime.timedelta(days=1))
    chk("다음 날은 또 먹일 수 있다", r["happiness"] == 120 and hp(p1) == 120, r)
    # 그것밖에 없으면 avoid 라도 준다 / 하나도 없으면 409 (하루를 안 쓴다)
    u2 = mkuser()
    q = mkmon(u2, "PIKACHU", happiness=70)
    items.bag_add(u2, "ORANBERRY", 1)
    r = garden.feed(u2, q, avoid="ORANBERRY", now=t)
    chk("avoid 밖에 없으면 avoid 를 준다", r["berry"] == "ORANBERRY" and bag(u2, "ORANBERRY") == 0, r)
    q2 = mkmon(u2, "PIKACHU", happiness=70, slot=1)
    chk("줄 열매가 없으면 409", refused(garden.feed, u2, q2, now=t) == 409)
    chk("  하루를 안 쓴다", fed_rows(q2) == 0)
    # 라우트 · 동시에 두 번
    items.bag_add(u2, "SITRUSBERRY", 5)
    r = GR.feed_pokemon(q2, GR.FeedIn(avoid=None, hour=12), ctx(u2))
    chk("라우트: POST /api/pokemon/{pid}/feed", r["berry"] == "SITRUSBERRY" and r["happiness"] == 80, r)
    chk("  라우트: 또 하면 409", http_status(GR.feed_pokemon, q2, GR.FeedIn(), ctx(u2)) == 409)
    q3 = mkmon(u2, "PIKACHU", happiness=70, slot=2)
    out, errs = [], []
    gate = threading.Barrier(2)

    def go():
        try:
            gate.wait(5)
            out.append(garden.feed(u2, q3, now=t))
        except garden.Refused as e:
            errs.append(e.status)
    ths = [threading.Thread(target=go) for _ in range(2)]
    for th in ths:
        th.start()
    for th in ths:
        th.join(20)
    chk("두 스레드가 동시에 먹여도 한 번 (성공 1 · 409 1)", len(out) == 1 and errs == [409], (out, errs))
    chk("  열매 하나 · +10", bag(u2, "SITRUSBERRY") == 3 and hp(q3) == 80, (bag(u2, "SITRUSBERRY"), hp(q3)))


# ---------------------------------------------------------------- 10. /api/me · 집안일
def test_me_card_error():
    print("\n=== /api/me: 텃밭 카드가 터지면 garden 칸을 뺀다 ===")
    uid = mkuser()
    real = garden.card

    def boom(*a, **k):
        raise RuntimeError("시험용 카드 실패")
    garden.card = boom
    try:
        me = main._me_data(me_ctx(uid))
        chk("카드가 터지면 /api/me 에 garden 칸이 없다", "garden" not in me, me.get("garden"))
        chk("  나머지는 그대로 (낚시 · 세션)", "session" in me and "fish" in me, sorted(me))
    except Exception as e:                                   # noqa: BLE001
        chk("카드가 터지면 /api/me 에 garden 칸이 없다", False, repr(e))
    finally:
        garden.card = real
    me = main._me_data(me_ctx(uid))
    chk("열렸으면 garden 은 카드", me.get("garden") and me["garden"]["open"] is True
        and set(me["garden"]) == CARD_KEYS, me.get("garden"))
    # 손님 view 도 터지면 칸을 뺀다 - 놀러 가기 자체는 된다
    host, g = mkuser(), mkuser()
    mkmon(g, "PIKACHU")
    befriend_online(g, host)
    real_fv = garden.friend_view
    garden.friend_view = boom
    try:
        with Pushes():
            v = visit.start(g, host)
            chk("friend_view 가 터져도 놀러 가기는 된다 · view 에 garden 칸 없음", v["role"] == "guest"
                and "garden" not in v, sorted(v))
    finally:
        garden.friend_view = real_fv
        visit.end(g)


def test_prune():
    print("\n=== 집안일: 지난 날 줄 치우기 ===")
    now = kst(2030, 7, 10, 12, 0)
    uid = mkuser()
    pid = mkmon(uid)
    for day in ("2030-07-08", "2030-07-09", "2030-07-10"):
        db.run("INSERT INTO garden_day (user_id, day, harvested) VALUES (?,?,1)", (uid, day))
        db.run("INSERT INTO garden_water (host_id, day, giver_id, at) VALUES (?,?,?,'')", (uid, day, uid))
        db.run("INSERT INTO feed_day (pokemon_id, day, user_id) VALUES (?,?,?)", (pid, day, uid))
    n = garden.prune(now=now)
    left = [r["day"] for r in db.q("SELECT day FROM garden_day WHERE user_id=? ORDER BY day", (uid,))]
    chk("그저께 줄은 지운다 · 어제 · 오늘은 남긴다", left == ["2030-07-09", "2030-07-10"], left)
    chk("  친구 물 · 먹이 표도", [r["day"] for r in db.q("SELECT day FROM garden_water WHERE host_id=? ORDER BY day",
                                                     (uid,))] == ["2030-07-09", "2030-07-10"]
        and [r["day"] for r in db.q("SELECT day FROM feed_day WHERE pokemon_id=? ORDER BY day", (pid,))]
        == ["2030-07-09", "2030-07-10"])
    chk("  지운 줄 수 >= 3", n >= 3, n)
    chk("housekeep 이 한 시간마다 garden.prune 을 부른다", "garden.prune()" in inspect.getsource(housekeep._loop))


def main_():
    db.init()
    test_closed()
    with Season(config.GARDEN_FROM):
        test_plant()
        test_stage_and_card()
        test_water_per_stage()
        test_harvest()
        test_daily_cap()
        test_pull()
        test_friend_water()
        test_friend_why()
        test_guest_push()
        test_feed()
        test_me_card_error()
        test_prune()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
