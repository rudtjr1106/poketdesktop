# -*- coding: utf-8 -*-
"""풀숲 부스트 검사 (2.1.1, app/boosts.py): 타입 스프레이 · 버닝 부스터. 서버를 띄우지 않는다.

    python server/test_boosts.py

못 박는 것:

  1. 도구 둘이 있고 상점(10,000원)에서만 판다 - 길드 코인 상점 · 드랍 표에는 없다.
  2. 타입 스프레이: 타입을 안 골랐거나 없는 타입(스텔라 포함)이면 거절하고 **도구는 그대로**.
     쓰면 1시간, 같은 타입이면 더하고(3시간까지 - 넘으면 거절하고 도구는 그대로), 다른 타입이면 바꾸고 다시 1시간.
  3. 스프레이가 켜져 있으면 실제 풀숲(main._make_grass)에 그 타입이 훨씬 자주 나온다. 끝나면 평소대로.
  4. 버닝 부스터: 쓰면 1시간, 풀숲 간격이 2~3분 (main._cooldown · battle_routes.reschedule 둘 다).
     이미 5~7분 뒤로 잡힌 다음 풀숲을 2~3분 안으로 당긴다. 3시간까지만 쌓인다. 끝나면 5~7분으로 돌아온다.
  5. /api/wild · /api/me · /api/shop 답에 남은 시간이 실린다.
"""
import datetime
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-boosts-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_HOUSEKEEP"] = "0"

from fastapi import HTTPException                                # noqa: E402

from app import auth, battle_routes, boosts, config, db, deps, guild, item_routes, items  # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def now():
    return datetime.datetime.now(UTC)


def iso(t):
    return t.replace(microsecond=0).isoformat()


def mkuser(name):
    cur = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                 " created_at, last_login, last_ip) VALUES (?,?,?,1,30,0,?,?,'')",
                 (name, b"x", b"x", iso(now()), iso(now())))
    return cur.lastrowid


def me(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def use(uid, item, t=""):
    try:
        return item_routes.use(item_routes.UseIn(item=item, type=t), me(uid)), None
    except HTTPException as e:
        return None, e.detail


def next_in(uid):
    r = db.q1("SELECT next_at FROM wild_state WHERE user_id=?", (uid,))
    return (auth.parse_iso(r["next_at"]) - now()).total_seconds() if r and r["next_at"] else None


def catalog():
    print("-- 1. 도구")
    sp, bn = items.get("TYPESPRAY"), items.get("BURNINGBOOST")
    chk("타입 스프레이 · 버닝 부스터가 있다", sp and bn and sp["effect"]["kind"] == "lure"
        and bn["effect"]["kind"] == "burn" and sp["effect"].get("pickType"))
    chk("  상점 값 10,000원 · 되팔면 0원", items.buy_price("TYPESPRAY") == 10000 and items.buy_price("BURNINGBOOST") == 10000
        and sp["sell"] == 0 and bn["sell"] == 0)
    rows = dict((r["id"], r) for r in guild.shop(mkuser("상점구경"))["items"])
    chk("  길드 코인 상점에는 없다 (사용자 결정 - 상점에서만)", "TYPESPRAY" not in rows and "BURNINGBOOST" not in rows
        and guild.coin_price("TYPESPRAY") == 0 == guild.coin_price("BURNINGBOOST"), sorted(rows)[:5])
    drops = set(i for i, _w in items.data()["dropTable"])
    chk("  드랍 표에는 없다", not drops & {"TYPESPRAY", "BURNINGBOOST", "RENAMETICKET"})


def spray():
    print("-- 2. 타입 스프레이")
    uid = mkuser("스프레이")
    items.bag_add(uid, "TYPESPRAY", 5)
    for t, why in (("", "타입을 안 고르면"), ("STELLAR", "스텔라는"), ("BANANA", "없는 타입은")):
        r, err = use(uid, "TYPESPRAY", t)
        chk("%s 거절, 도구는 그대로" % why, r is None and err and items.bag_count(uid, "TYPESPRAY") == 5, err)
    r, err = use(uid, "TYPESPRAY", "water")
    s = boosts.state(uid)
    chk("쓰면 1시간 (타입은 대소문자 안 가린다)", r and s["lureType"] == "WATER" and 3590 <= s["lureLeft"] <= 3600
        and items.bag_count(uid, "TYPESPRAY") == 4, (err, s))
    chk("  말에 시간과 한글 타입", r and "1시간" in r["message"] and "물" in r["message"], r and r["message"])
    chk("  답에 남은 시간과 지갑", r and r["boosts"]["lureType"] == "WATER" and "bag" in r and "money" in r)
    use(uid, "TYPESPRAY", "WATER")
    use(uid, "TYPESPRAY", "WATER")
    s = boosts.state(uid)
    chk("같은 타입이면 더한다 (3시간)", 3 * 3600 - 10 <= s["lureLeft"] <= 3 * 3600 and items.bag_count(uid, "TYPESPRAY") == 2,
        s)
    r, err = use(uid, "TYPESPRAY", "WATER")
    chk("3시간을 넘으면 거절, 도구는 그대로", r is None and "3시간까지만" in err
        and items.bag_count(uid, "TYPESPRAY") == 2, err)
    r, err = use(uid, "TYPESPRAY", "FIRE")
    s = boosts.state(uid)
    chk("다른 타입이면 바꾸고 다시 1시간", r and s["lureType"] == "FIRE" and 3590 <= s["lureLeft"] <= 3600, s)
    later = now() + datetime.timedelta(seconds=3601)
    chk("끝나면 꺼진다", boosts.state(uid, later) == {"burnLeft": 0, "lureLeft": 0, "lureType": None}
        and boosts.spawn_boost(uid, later) is None, boosts.state(uid, later))
    chk("켜져 있는 동안 출현 boost = ((타입,), 0) - 그 타입 종만", boosts.spawn_boost(uid) == (("FIRE",), 0))
    rng = random.Random(9)
    k = sum(1 for _ in range(2000) if boosts.roll_boost(uid, rng))
    chk("  풀숲 둘에 하나만 스프레이 차례 (%d/2000)" % k, 900 <= k <= 1100, k)


def grass():
    print("-- 3. 실제 풀숲")
    from app import main
    d = deps.dex()

    def share(uid, t, n=400):
        got = 0
        for _ in range(n):
            row = main._make_grass(uid)
            if t in d.get(row["species"])["types"]:
                got += 1
            db.run("DELETE FROM wild WHERE id=?", (row["id"],))
        return got
    uid = mkuser("풀숲")
    off = share(uid, "ICE")
    boosts.lure(uid, "ICE", 60)
    on = share(uid, "ICE")
    chk("스프레이 없이 얼음 %d/400 (10%% 아래)" % off, off < 40, off)
    chk("얼음 스프레이를 켜면 %d/400 (45%% 넘게 - 둘에 하나는 얼음 종에서만 뽑는다)" % on, on > 180, on)
    boosts.lure(uid, "DRAGON", 60)
    dr = share(uid, "DRAGON")
    chk("가장 드문 드래곤(평소 2%%)도 %d/400 (45%% 넘게)" % dr, dr > 180, dr)
    db.run("UPDATE wild_state SET lure_type='BANANA' WHERE user_id=?", (uid,))
    try:
        n = share(uid, "BANANA", 20)
        chk("그 타입 종이 없는 표(빈 표)면 평소대로 뽑는다 (풀숲이 안 깨진다)", n == 0)
    except Exception as e:                                  # noqa: BLE001
        chk("그 타입 종이 없는 표(빈 표)면 평소대로 뽑는다 (풀숲이 안 깨진다)", False, e)
    pool, _c, _t = d.spawn_pool(10, 410, (("ICE",), 0))
    chk("배수 0 은 그 타입 종만, 종족값 상한은 그대로", pool and all("ICE" in s["types"] for s in pool)
        and all(d.bst(s) <= 410 for s in pool), len(pool))


def burn():
    print("-- 4. 버닝 부스터")
    uid = mkuser("버닝")
    items.bag_add(uid, "BURNINGBOOST", 4)
    rng = random.Random(3)
    plain = [boosts.cooldown(uid, rng) for _ in range(200)]
    chk("평소 간격 5~7분", min(plain) >= config.WILD_COOLDOWN_MIN and max(plain) <= config.WILD_COOLDOWN_MAX,
        (min(plain), max(plain)))
    db.run("INSERT INTO wild_state (user_id, next_at) VALUES (?,?)",
           (uid, iso(now() + datetime.timedelta(seconds=400))))
    r, err = use(uid, "BURNINGBOOST")
    s = boosts.state(uid)
    chk("쓰면 1시간", r and 3590 <= s["burnLeft"] <= 3600 and items.bag_count(uid, "BURNINGBOOST") == 3, (err, s))
    left = next_in(uid)
    chk("  이미 400초 뒤로 잡힌 다음 풀숲을 2~3분 안으로 당긴다 (%.0f초)" % left,
        left is not None and left <= boosts.BURN_MAX, left)
    from app import main
    fast = [main._cooldown(uid) for _ in range(200)]
    chk("켜져 있는 동안 간격 2~3분 (main._cooldown)", min(fast) >= boosts.BURN_MIN and max(fast) <= boosts.BURN_MAX,
        (min(fast), max(fast)))
    battle_routes.reschedule(uid)
    left = next_in(uid)
    chk("  배틀 · 잡기 뒤에도 2~3분 (battle_routes.reschedule, %.0f초)" % left,
        boosts.BURN_MIN - 2 <= left <= boosts.BURN_MAX, left)
    later = now() + datetime.timedelta(seconds=3601)
    back = [boosts.cooldown(uid, rng, later) for _ in range(100)]
    chk("끝나면 5~7분으로 돌아온다", min(back) >= config.WILD_COOLDOWN_MIN, min(back))

    db.run("UPDATE wild_state SET next_at=? WHERE user_id=?", (iso(now() + datetime.timedelta(seconds=30)), uid))
    use(uid, "BURNINGBOOST")
    left = next_in(uid)
    chk("곧 돋을 풀숲은 뒤로 미루지 않는다 (%.0f초)" % left, left <= 30, left)
    use(uid, "BURNINGBOOST")
    s = boosts.state(uid)
    r, err = use(uid, "BURNINGBOOST")
    chk("3시간까지 쌓이고 넘으면 거절, 도구는 그대로", 3 * 3600 - 10 <= s["burnLeft"] <= 3 * 3600 and r is None
        and "3시간까지만" in err and items.bag_count(uid, "BURNINGBOOST") == 1, (s, err))

    u3 = mkuser("버닝동시")
    for _ in range(5):                                      # 거의 동시에 써서 남은 시간 확인을 모두 지났다고 치고
        boosts.burn(u3, 60, rng)
        boosts.lure(u3, "FIRE", 60)
    s3 = boosts.state(u3)
    chk("확인을 지나쳐 여러 번 켜져도 3시간을 넘지 않는다", s3["burnLeft"] <= 3 * 3600 and s3["lureLeft"] <= 3 * 3600, s3)

    u2 = mkuser("버닝새내기")
    items.bag_add(u2, "BURNINGBOOST", 1)
    r, err = use(u2, "BURNINGBOOST")
    left = next_in(u2)
    chk("풀숲 기록이 없던 사람도 쓴다 (다음 풀숲 %.0f초)" % (left or -1), r and left is not None
        and left <= boosts.BURN_MAX, err)


def answers():
    print("-- 5. 답에 실리는 남은 시간")
    from app import main
    uid = mkuser("답")
    boosts.burn(uid, 60, random.Random(1))
    boosts.lure(uid, "GHOST", 60)
    w = main.wild_state(me(uid))
    chk("/api/wild", w["boosts"]["burnLeft"] > 3500 and w["boosts"]["lureType"] == "GHOST", w.get("boosts"))
    ctx = me(uid)
    ctx["session"] = {"ip": "", "expires_at": None}
    m = main.me(ctx)
    chk("/api/me", (m.get("boosts") or {}).get("lureType") == "GHOST", m.get("boosts"))
    s = item_routes.shop(me(uid))
    chk("/api/shop", s["boosts"]["burnLeft"] > 3500, s.get("boosts"))
    u2 = mkuser("답없음")
    chk("안 쓴 사람은 0", item_routes.shop(me(u2))["boosts"] == {"burnLeft": 0, "lureLeft": 0, "lureType": None})


def main_():
    db.init()
    catalog()
    spray()
    grass()
    burn()
    answers()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
