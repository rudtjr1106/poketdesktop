# -*- coding: utf-8 -*-
"""길드 코인 상점 2.1.0 검사 — 늘어난 상점 도구와 슬롯머신.

    python server/test_guild_slot.py

서버를 띄우지 않고 app.guild 의 함수를 직접 부른다 (test_guild 와 같은 방식).

무엇을 못 박나:
  1. 상점에 진화 도구와 배틀용 지닌 도구(SHOP_HELD)가 코인 값을 갖고 들어온다. 금구슬 같은 것은 여전히 없다.
     묶음(group)이 볼 · 성장 · 진화 · 지닌 도구 차례로 붙는다.
  2. 슬롯은 한 번 20 코인. 모자라면 400 이고 아무것도 안 준다.
  3. 확률표의 합은 100% 이고, 많이 돌리면 표대로 나온다. 기대값은 낸 코인보다 적다.
  4. 꾸미기는 후보(C.slot_pool - 왕관 · 순위 효과 뺌) 중 안 가진 것만. 다 가졌으면 이상한사탕 2개.
  5. 알 · 뽑기권 · 이로치 사탕이 실제로 들어간다. 릴 기호 규칙. 한 판마다 기록 줄.
"""
import collections
import math
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-guild-slot-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                            # noqa: E402

from common import deco as C                                 # noqa: E402
from app import config, db, deco, guild, items, season       # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def err(fn, *a, **k):
    try:
        fn(*a, **k)
    except HTTPException as e:
        return e.status_code, e.detail
    return None


def mkuser(name):
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')",
        (name, b"x", b"x"))
    return cur.lastrowid


def logs(uid):
    return db.q("SELECT * FROM guild_slot_log WHERE user_id=? ORDER BY id", (uid,))


def bag(uid):
    return items.bag_get(uid)


def forced(key):
    """slot_roll 을 그 결과로 묶는다 (되돌릴 원래 함수를 돌려준다)."""
    orig = guild.slot_roll
    guild.slot_roll = lambda rng: guild.SLOT_BY[key]
    return orig


def avg_coin(ids):
    return sum(guild.coin_price(i) for i in ids) / float(len(ids))


def main():
    db.init()
    # 길드 전용 상품(시즌 7 부터 - 마스터볼 · 금색병뚜껑, '길드 전용' 묶음)이 없는 상점을 본다. 전용 상품은
    # test_guild_shop_exclusive 가 본다.
    season.SEASON = 6

    print("\n=== 늘어난 상점 도구 ===")
    a = mkuser("가")
    sh = guild.shop(a)
    ids = dict((x["id"], x) for x in sh["items"])
    stones = [it["id"] for it in items.catalog().values()
              if it["cat"] == "stone" and items.buy_price(it["id"]) > 0]
    chk("살 수 있는 진화 도구가 전부 있다 (%d개)" % len(stones), set(stones) <= set(ids),
        sorted(set(stones) - set(ids)))
    chk("  진화의 돌 · 통신 진화 도구 · 족자", {"FIRESTONE", "LINKINGCORD", "SCROLLOFDARKNESS"} <= set(ids))
    chk("SHOP_HELD 는 20개 안팎", 15 <= len(guild.SHOP_HELD) <= 25, len(guild.SHOP_HELD))
    chk("SHOP_HELD 가 전부 코인 값을 갖는다 (상점에서 파는 지닌 도구)",
        all(guild.coin_price(i) > 0 and items.is_holdable(i) for i in guild.SHOP_HELD),
        [i for i in guild.SHOP_HELD if not guild.coin_price(i)])
    chk("생명의구슬 = 상점 값 / %d 올림" % config.GUILD_COIN_WON,
        guild.coin_price("LIFEORB") == int(math.ceil(items.buy_price("LIFEORB") / float(config.GUILD_COIN_WON))),
        guild.coin_price("LIFEORB"))
    chk("팔아서 돈으로 바꾸는 물건은 여전히 없다 (금구슬)", "NUGGET" not in ids and guild.coin_price("NUGGET") == 0)
    chk("안 파는 것도 없다 (금색병뚜껑 · 이로치 사탕 · 뽑기권)",
        not ({"GOLDBOTTLECAP", "SHINYCANDY", "RANKTICKETTM"} & set(ids)))
    chk("SHOP_HELD 에 없는 지닌 도구는 안 판다 (플레이트 등)",
        all(x["id"] in guild.SHOP_HELD for x in sh["items"] if x["cat"] == "held"))
    order = [guild.SHOP_GROUPS.index(x["group"]) for x in sh["items"]]
    chk("묶음 차례: 볼 · 성장 · 진화 · 지닌 도구", order == sorted(order) and sh["groups"] == list(guild.SHOP_GROUPS)
        and set(x["group"] for x in sh["items"]) == set(guild.SHOP_GROUPS), sh["groups"])
    chk("  묶음 안은 값 차례", all(
        sh["items"][i]["coin"] <= sh["items"][i + 1]["coin"] for i in range(len(order) - 1)
        if order[i] == order[i + 1]))
    chk("  왕의징표석(돌이면서 지닐 수 있음)은 진화 묶음", ids["KINGSROCK"]["group"] == "진화")
    chk("  비타민 · 깃털 · 사탕은 성장 묶음", all(ids[i]["group"] == "성장" for i in ("HPUP", "SWIFTWING", "RARECANDY")))

    print("\n=== 확률표 ===")
    tab = guild.SLOT_TABLE
    chk("합이 100%", sum(r[2] for r in tab) == 1000, sum(r[2] for r in tab))
    chk("기호 목록 = 꽝 뺀 결과 열쇠",
        guild.SLOT_SYMBOLS == ("ball", "hyper", "feather", "stone", "vitamin", "cap", "candy", "held", "deco",
                               "ticket", "shiny", "egg"), guild.SLOT_SYMBOLS)
    tiers = dict((r[0], r[3]) for r in tab)
    chk("등급", tiers == {"lose": "lose", "ball": "common", "hyper": "common", "feather": "common",
                          "stone": "common", "vitamin": "rare", "cap": "rare", "candy": "rare", "held": "rare",
                          "deco": "epic", "ticket": "epic", "shiny": "jackpot", "egg": "jackpot"}, tiers)
    for r in tab:
        what = r[4]
        if isinstance(what, str) and what not in ("held", "deco", "egg"):
            chk("  주는 도구가 있다: %s (%s)" % (r[1], what), items.get(what) is not None)
        elif isinstance(what, tuple):
            chk("  후보가 다 있다: %s" % r[1], all(items.get(i) for i in what))
    chk("몬스터볼 = 가방의 POKEBALL, 하이퍼볼 = ULTRABALL",
        items.name_of("POKEBALL") == "몬스터볼" and items.name_of("ULTRABALL") == "하이퍼볼")
    rng = random.Random(1234)
    N = 200000
    got = collections.Counter(guild.slot_roll(rng)[0] for _ in range(N))
    bad = []
    for r in tab:
        p = r[2] / 1000.0
        tol = 4.5 * math.sqrt(p * (1 - p) / N)
        if abs(got[r[0]] / float(N) - p) > tol:
            bad.append((r[0], got[r[0]] / float(N), p))
    chk("%d번 굴리면 비율이 표와 맞는다 (4.5σ 안)" % N, not bad, bad)

    # 기대값: 코인으로 산 값. 상점에 없는 것(뽑기권 · 이로치 사탕 · 알 · 꾸미기)은 넉넉히 비싸게 쳐도 20 아래여야 한다.
    unpriced = {"ticket": 200, "shiny": 500, "egg": 2000, "deco": 2 * guild.coin_price("RARECANDY")}
    ev = 0.0
    for key, _kr, per, _t, what, n in tab:
        if key in unpriced:
            v = unpriced[key]
        elif what is None:
            v = 0
        elif what == "held":
            v = avg_coin(guild.SHOP_HELD) * n
        elif isinstance(what, tuple):
            v = avg_coin(what) * n
        else:
            v = guild.coin_price(what) * n
        ev += per / 1000.0 * v
    chk("기대값 %.2f 코인 < %d 코인 (상점에 없는 것은 비싸게 쳐서: 뽑기권 200 · 이로치 사탕 500 · 알 2000)"
        % (ev, guild.SLOT_COST), ev < guild.SLOT_COST, ev)
    # 판 값으로도: 한 판에 나오는 것을 다 팔아도 낸 코인어치 돈보다 적다 (돈으로 바꾸는 창구가 아니다)
    sell = 0.0
    for key, _kr, per, _t, what, n in tab:
        pool = guild.SHOP_HELD if what == "held" else what if isinstance(what, tuple) else (
            (what,) if isinstance(what, str) and what not in ("deco", "egg") else ())
        if pool:
            sell += per / 1000.0 * n * sum(items.sell_price(i) for i in pool) / float(len(pool))
    chk("팔면 한 판에 %.0f원어치 < %d원" % (sell, guild.SLOT_COST * config.GUILD_COIN_WON),
        sell < guild.SLOT_COST * config.GUILD_COIN_WON, sell)

    print("\n=== 코인 ===")
    b = mkuser("나")
    chk("코인이 한 번도 없던 사람은 400", (err(guild.slot, b) or (0,))[0] == 400 and not logs(b))
    guild._coin_add(b, 19)
    before = bag(b)
    e = err(guild.slot, b, random.Random(1))
    chk("모자라면 400 · 문구", e == (400, "길드 코인이 모자랍니다. (20개 필요)"), e)
    chk("  아무것도 안 준다 · 코인 그대로 · 기록 없음", bag(b) == before and guild.coin(b) == 19 and not logs(b))
    guild._coin_add(b, 41)                       # 60
    r = guild.slot(b, random.Random(2))
    chk("한 번에 20 코인", r["ok"] and guild.coin(b) == 40 and r["coin"] == 40, (guild.coin(b), r))
    chk("응답 꼴", set(r) >= {"ok", "prize", "kr", "tier", "item", "itemKr", "count", "deco", "decoKr", "egg",
                             "reels", "coin", "message"}, sorted(r))
    chk("길드에 안 들어 있어도 돌린다 (코인은 사람 것)", guild.member(b) is None)
    guild.slot(b, random.Random(3))
    guild.slot(b, random.Random(4))
    chk("20 코인이 안 남으면 멈춘다 (음수가 안 된다)", guild.coin(b) == 0
        and (err(guild.slot, b) or (0,))[0] == 400 and guild.coin(b) == 0 and len(logs(b)) == 3)

    print("\n=== 많이 돌려서 ===")
    c = mkuser("다")
    M = 1500
    guild._coin_add(c, guild.SLOT_COST * M)
    rng = random.Random(77)
    outs = [guild.slot(c, rng) for _ in range(M)]
    rows = logs(c)
    chk("한 판마다 기록 줄 하나", len(rows) == M and guild.coin(c) == 0, (len(rows), guild.coin(c)))
    chk("  기록의 결과 = 응답의 결과", [x["prize"] for x in rows] == [o["prize"] for o in outs])
    chk("  기록에 낸 코인 · 도구 · 개수", all(x["cost"] == guild.SLOT_COST for x in rows)
        and all((x["item"], x["count"]) == (o["item"], o["count"]) for x, o in zip(rows, outs)))
    wins = [o for o in outs if o["prize"] != "lose"]
    loses = [o for o in outs if o["prize"] == "lose"]
    chk("당첨은 릴 셋이 그 결과 기호로 같다", all(o["reels"] == [o["prize"]] * 3 for o in wins))
    chk("꽝은 릴 셋이 다 같지는 않다", loses and all(len(set(o["reels"])) > 1 for o in loses))
    chk("  기호는 SLOT_SYMBOLS 중에서", all(s in guild.SLOT_SYMBOLS for o in outs for s in o["reels"]))
    near = sum(1 for o in loses if o["reels"][0] == o["reels"][1])
    chk("  가끔 앞 둘만 같은 '아깝다' 조합 (%d / %d)" % (near, len(loses)), 0 < near < len(loses))
    chk("등급은 표대로", all(o["tier"] == guild.SLOT_BY[o["prize"]][3] for o in outs))
    total = collections.Counter()
    for o in outs:
        if o["item"]:
            total[o["item"]] += o["count"]
    have = bag(c)
    chk("나온 도구가 가방에 그대로 들어갔다", all(have.get(i, 0) - (10 if i == "POKEBALL" else 0) == n
                                     for i, n in total.items()), total.most_common(5))
    chk("  깃털 3 · 돌 1 · 비타민 1 · 볼 5 · 하이퍼볼 3",
        all(o["count"] == {"feather": 3, "stone": 1, "vitamin": 1, "ball": 5, "hyper": 3}[o["prize"]]
            for o in outs if o["prize"] in ("feather", "stone", "vitamin", "ball", "hyper")))
    chk("  돌은 기본 진화의 돌 중에서, 지닌 도구는 SHOP_HELD 중에서",
        all(o["item"] in guild.SLOT_STONES for o in outs if o["prize"] == "stone")
        and all(o["item"] in guild.SHOP_HELD for o in outs if o["prize"] == "held"))
    lose_n = len(loses) / float(M)
    chk("꽝 비율이 40%% 언저리 (%.1f%%)" % (lose_n * 100), abs(lose_n - 0.40) < 0.05)

    print("\n=== 꾸미기 ===")
    pool = C.slot_pool()
    chk("후보에 왕관 · 순위 효과가 없다", pool and not (set(pool) & set(C.RANK_ONLY))
        and not any(k.startswith("crown_") for k in pool)
        and not ({"fx_stars_gold", "fx_stars_silver", "fx_stars_bronze", "fx_glow"} & set(pool)), pool)
    d = mkuser("라")
    deco.grant(d, pool[0])                       # 하나는 이미 가졌다
    guild._coin_add(d, guild.SLOT_COST * (len(pool) + 1))
    orig = forced("deco")
    try:
        got = [guild.slot(d, random.Random(i)) for i in range(len(pool) - 1)]
        chk("안 가진 것만 하나씩 (%d개)" % (len(pool) - 1),
            sorted(o["deco"] for o in got) == sorted(pool[1:]) and all(o["decoKr"] and o["item"] is None for o in got),
            [o["deco"] for o in got])
        chk("  실제로 가졌다", all(deco.owned(d).get(k) for k in pool))
        rc = items.bag_count(d, "RARECANDY")
        last = guild.slot(d, random.Random(99))
        chk("다 가졌으면 대신 이상한사탕 2개", last["prize"] == "deco" and last["deco"] is None
            and last["item"] == "RARECANDY" and last["count"] == 2 and items.bag_count(d, "RARECANDY") == rc + 2,
            last)
        chk("  기록에도 deco 결과에 이상한사탕", logs(d)[-1]["prize"] == "deco" and logs(d)[-1]["item"] == "RARECANDY"
            and logs(d)[-1]["deco"] is None)
        chk("  순위 효과는 그대로 안 가졌다", not any(deco.owned(d).get(k) for k in C.RANK_ONLY))
    finally:
        guild.slot_roll = orig

    print("\n=== 대박 ===")
    e = mkuser("마")
    guild._coin_add(e, guild.SLOT_COST * 12)
    orig = forced("egg")
    try:
        eg = [guild.slot(e, random.Random(i)) for i in range(10)]
    finally:
        guild.slot_roll = orig
    eggs_db = db.q("SELECT id, kind FROM egg WHERE user_id=? ORDER BY id", (e,))
    chk("알이 실제로 들어간다 (10개)", len(eggs_db) == 10 and all(o["egg"] for o in eg), len(eggs_db))
    chk("  전설 · 환상 둘 다 나온다", set(x["kind"] for x in eggs_db) == {"legendary", "mythical"},
        collections.Counter(x["kind"] for x in eggs_db))
    chk("  응답 · 기록의 알이 DB 의 알과 같다", [o["egg"]["kind"] for o in eg] == [x["kind"] for x in eggs_db]
        and [x["egg_id"] for x in logs(e)] == [x["id"] for x in eggs_db] and eg[0]["egg"]["kr"].endswith("알"))
    chk("  등급 jackpot", all(o["tier"] == "jackpot" for o in eg))
    for key, item in (("ticket", "RANKTICKETTM"), ("shiny", "SHINYCANDY")):
        orig = forced(key)
        try:
            o = guild.slot(e, random.Random(5))
        finally:
            guild.slot_roll = orig
        chk("%s 가 가방에 들어간다" % items.name_of(item), o["item"] == item and items.bag_count(e, item) == 1
            and o["count"] == 1, o)

    print("\n=== 주다가 터지면 ===")
    f = mkuser("바")
    guild._coin_add(f, guild.SLOT_COST)
    orig, orig_add = forced("candy"), items.bag_add

    def boom(*a, **k):
        raise RuntimeError("가방이 터졌다")
    items.bag_add = boom
    try:
        try:
            guild.slot(f, random.Random(1))
            blew = False
        except RuntimeError:
            blew = True
    finally:
        guild.slot_roll, items.bag_add = orig, orig_add
    chk("코인을 돌려준다 · 기록 없음", blew and guild.coin(f) == guild.SLOT_COST and not logs(f), guild.coin(f))

    print("\n=== shop 응답의 slot ===")
    s = guild.shop(a)["slot"]
    chk("값 20 · 확률 공개", s["cost"] == 20 and len(s["odds"]) == len(tab)
        and abs(sum(x["pct"] for x in s["odds"]) - 100.0) < 1e-9, s["cost"])
    chk("  열쇠 · 이름 · 퍼센트 · 등급", s["odds"][0] == {"key": "lose", "kr": "꽝", "pct": 40.0, "tier": "lose"}
        and s["odds"][-1] == {"key": "egg", "kr": "전설·환상 알", "pct": 0.1, "tier": "jackpot"}, s["odds"][-1])

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
