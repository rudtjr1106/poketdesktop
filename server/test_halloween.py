# -*- coding: utf-8 -*-
"""할로윈 이벤트 (2026-10-31 하루, app/halloween.py). 서버를 띄우지 않는다.

    python server/test_halloween.py

못 박는 것:

  1. 날짜는 한국시간이다 - 10/31 00:00 KST(10/30 15:00 UTC)에 켜지고 11/1 00:00 KST 에 꺼진다.
  2. 야생: 이벤트 날에는 고스트 타입이 30% 쯤 나온다 (평소 5% 쯤). 나오는 종 자체는 그대로다.
     평소 표는 이벤트 표와 섞이지 않는다 (캐시 열쇠가 다르다).
  3. 드랍: 이벤트 날에는 이상한사탕이 10배 잘 떨어진다. items.json 의 표는 그대로다 (탐험이 같은 표를 읽는다).
  4. 실제 풀숲(main._make_grass)이 이벤트 날 고스트를 더 낸다.
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

TMP = tempfile.mkdtemp(prefix="poket-halloween-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_HOUSEKEEP"] = "0"

from app import config, db, deps, halloween, items           # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
EVE = datetime.datetime(2026, 10, 30, 14, 59, 59, tzinfo=UTC)      # 10/30 23:59:59 KST
START = datetime.datetime(2026, 10, 30, 15, 0, 0, tzinfo=UTC)      # 10/31 00:00 KST
LAST = datetime.datetime(2026, 10, 31, 14, 59, 59, tzinfo=UTC)     # 10/31 23:59:59 KST
AFTER = datetime.datetime(2026, 10, 31, 15, 0, 0, tzinfo=UTC)      # 11/1 00:00 KST


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def ghost_share(pool, total, mult=1):
    g = sum(s.get("weight", 0) * mult for s in pool if "GHOST" in s["types"])
    return g * 1.0 / total


def dates():
    print("-- 1. 날짜 (KST)")
    chk("10/30 23:59:59 KST 는 아니다", not halloween.on(EVE))
    chk("10/31 00:00 KST 에 켜진다", halloween.on(START))
    chk("10/31 23:59:59 KST 까지", halloween.on(LAST))
    chk("11/1 00:00 KST 에 꺼진다", not halloween.on(AFTER))
    chk("시각대 없는 시각은 UTC 로 본다", halloween.on(START.replace(tzinfo=None))
        and not halloween.on(EVE.replace(tzinfo=None)))
    chk("평소에는 boost 가 없다", halloween.spawn_boost(EVE) is None and halloween.drop_boost(AFTER) == {})
    chk("이벤트 날 boost", halloween.spawn_boost(START) == (("GHOST",), config.HALLOWEEN_GHOST_MULT)
        and halloween.drop_boost(LAST) == {"RARECANDY": config.HALLOWEEN_CANDY_MULT})


def spawn():
    print("-- 2. 야생 비율")
    d = deps.dex()
    boost = halloween.spawn_boost(START)
    for lv in (2, 10, 30, 50, 100):
        cap = config.WILD_BST_BASE + lv * config.WILD_BST_PER_LEVEL
        pool0, _c0, total0 = d.spawn_pool(lv, cap)
        pool1, _c1, total1 = d.spawn_pool(lv, cap, boost)
        again, _c2, total2 = d.spawn_pool(lv, cap)
        a, b = ghost_share(pool0, total0), ghost_share(pool1, total1, boost[1])
        chk("Lv.%d 평소 %.1f%% -> 이벤트 %.1f%% (25~35%%)" % (lv, a * 100, b * 100), a < 0.08 and 0.25 <= b <= 0.35)
        chk("  나오는 종은 같다", [s["internal"] for s in pool0] == [s["internal"] for s in pool1])
        chk("  이벤트 표를 만든 뒤에도 평소 표는 그대로", total2 == total0 and again is pool0)
    rng = random.Random(7)
    lv = 30
    cap = config.WILD_BST_BASE + lv * config.WILD_BST_PER_LEVEL
    n = sum(1 for _ in range(3000) if "GHOST" in d.roll_species(lv, rng, cap, boost)["types"])
    chk("굴려 봐도 30%% 쯤 (%d/3000)" % n, 750 <= n <= 1050, n)
    m = d.roll_wild(lv, lv, random.Random(1), max_bst=cap, boost=boost, shiny_rate=config.SHINY_RATE)
    chk("roll_wild 가 boost 를 받는다 (개체가 나온다)", m and m.get("level") == lv, m and m.get("level"))


def drops():
    print("-- 3. 이상한사탕 드랍")
    base = items.data()["dropTable"]
    w0 = dict(base)["RARECANDY"]
    t0 = items.data()["dropTotal"]
    table, total = items.drop_table(EVE)
    chk("평소에는 표 그대로", table is base and total == t0)
    table, total = items.drop_table(START)
    w1 = dict(table)["RARECANDY"]
    chk("이벤트 날 사탕 가중치 x%d" % config.HALLOWEEN_CANDY_MULT, w1 == w0 * config.HALLOWEEN_CANDY_MULT, w1)
    chk("  합도 맞다", total == t0 + w0 * (config.HALLOWEEN_CANDY_MULT - 1), total)
    chk("  다른 도구는 그대로", all(w == dict(base)[i] for i, w in table if i != "RARECANDY"))
    chk("items.json 표는 안 바뀐다", dict(items.data()["dropTable"])["RARECANDY"] == w0
        and items.data()["dropTotal"] == t0)
    print("     사탕 확률: 평소 %.2f%% -> 이벤트 %.2f%% (도구가 떨어질 때)" % (100.0 * w0 / t0, 100.0 * w1 / total))

    def count(now, n=20000):
        rng = random.Random(3)
        return collections.Counter(items.roll_drop(rng, False, now) for _ in range(n))["RARECANDY"]
    off, on = count(EVE), count(START)
    chk("굴려 봐도 평소 %d -> 이벤트 %d (20000번)" % (off, on), on >= 6 * max(1, off) and 300 <= on <= 500, (off, on))
    # 이로치는 여러 번 뽑아 가장 귀한 것 - 사탕 가중치가 올라도 '귀함' 순서는 도구 목록 값 그대로
    rng = random.Random(5)
    shiny = collections.Counter(items.roll_drop(rng, True, START) for _ in range(3000))
    chk("이로치 드랍도 그대로 돈다", sum(shiny.values()) == 3000)


def grass():
    print("-- 4. 실제 풀숲 (main._make_grass)")
    from app import main
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                 " created_at, last_login, last_ip) VALUES (?,?,?,1,30,0,'','','')",
                 ("유령", b"x", b"x")).lastrowid
    d = deps.dex()
    real = halloween._now

    def run(when, n=400):
        halloween._now = lambda: when
        try:
            g = 0
            for _ in range(n):
                row = main._make_grass(uid)
                if "GHOST" in d.get(row["species"])["types"]:
                    g += 1
                db.run("DELETE FROM wild WHERE id=?", (row["id"],))
            return g
        finally:
            halloween._now = real
    off, on = run(EVE), run(START)
    chk("평소 풀숲 고스트 %d/400 (12%% 아래)" % off, off < 48, off)
    chk("이벤트 날 풀숲 고스트 %d/400 (20%% 넘게)" % on, on > 80, on)


def main_():
    db.init()
    dates()
    spawn()
    drops()
    grass()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
