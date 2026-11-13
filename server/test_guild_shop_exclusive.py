# -*- coding: utf-8 -*-
"""길드 전용 상품 (시즌 7 부터) - guild.SHOP_EXCLUSIVE · exclusive · coin_price · shop · buy · 표 guild_buy.

    .venv-server/bin/python server/test_guild_shop_exclusive.py

길드전 보상을 코인만으로 바꾸며(11/12 사용자) 코인 상점에 돈 상점에 없는 것을 시즌마다 수를 묶어 판다.
마스터볼 600코인 시즌 1개 · 금색병뚜껑 200코인 시즌 2개 (랜덤 기술머신 뽑기권은 안 넣는다 - 사용자).

  1. 시즌 6: 전용 상품이 없다 (값 0 · 상점 목록 · 묶음 없음 · 사면 404).
  2. 시즌 7: '길드 전용' 묶음이 맨 앞 · 값 · 시즌마다 수 · 남은 수. 뽑기권은 없다.
  3. 사기: 코인이 빠지고 가방에 들어온다 · 남은 수가 준다 · 다 사면 409 (코인 그대로) · 한 번에 수보다 많이 409 ·
     코인이 모자라면 400 이고 산 수도 안 늘어난다.
  4. 다음 시즌이면 다시 살 수 있다.
  5. 되팔면 손해 (금색병뚜껑 판 값 < 코인 값어치) - 코인을 돈으로 바꾸는 창구가 아니다.
서버를 띄우지 않는다. 임시 DB.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

TMP = tempfile.mkdtemp(prefix="poket-gshopx-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                             # noqa: E402

from app import config, db, guild, items, season              # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def code_of(fn):
    try:
        fn()
    except HTTPException as e:
        return e.status_code, e.detail
    return None


def mkuser(name, coins):
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login, last_ip)"
                 " VALUES (?,?,?,1,10,0,'','','')", (name, b"x", b"x")).lastrowid
    guild._coin_add(uid, coins)
    return uid


def bag(uid, iid):
    r = db.q1("SELECT balls FROM users WHERE id=?", (uid,))
    return int(items.bag_get(uid, r["balls"] if r else 0).get(iid, 0) or 0)


def row(sh, iid):
    return next((x for x in sh["items"] if x["id"] == iid), None)


def main():
    db.init()
    real = season.SEASON
    try:
        print("=== 1. 시즌 6: 전용 상품 없음 ===")
        season.SEASON = 6
        u = mkuser("육", 5000)
        sh = guild.shop(u)
        chk("값 0 · 목록에 없음 · '길드 전용' 묶음 없음", guild.coin_price("MASTERBALL") == 0
            and guild.coin_price("GOLDBOTTLECAP") == 0 and row(sh, "MASTERBALL") is None
            and guild.EXCLUSIVE_GROUP not in sh["groups"], sh["groups"])
        c = code_of(lambda: guild.buy(u, "MASTERBALL", 1))
        chk("  사면 404 · 코인 그대로", c and c[0] == 404 and guild.coin(u) == 5000, c)

        print("\n=== 2. 시즌 7: '길드 전용' 묶음 ===")
        season.SEASON = 7
        sh = guild.shop(u)
        mb, gc = row(sh, "MASTERBALL"), row(sh, "GOLDBOTTLECAP")
        chk("묶음이 맨 앞", sh["groups"][0] == guild.EXCLUSIVE_GROUP and sh["groups"][1:] == list(guild.SHOP_GROUPS),
            sh["groups"])
        chk("  마스터볼 600코인 · 시즌 1개 · 남은 1", mb and mb["coin"] == 600 and mb["limit"] == 1 and mb["left"] == 1
            and mb["exclusive"] and mb["group"] == guild.EXCLUSIVE_GROUP, mb)
        chk("  금색병뚜껑 200코인 · 시즌 2개 · 남은 2", gc and gc["coin"] == 200 and gc["limit"] == 2 and gc["left"] == 2, gc)
        chk("  목록 맨 앞이 전용 상품", [x["id"] for x in sh["items"][:2]] == ["MASTERBALL", "GOLDBOTTLECAP"])
        ids = [x["id"] for x in sh["items"]]
        chk("  전용 상품은 '길드 전용' 에만 한 번 (볼 · 성장 묶음에 또 안 나온다 - 11/12 검토)",
            ids.count("MASTERBALL") == 1 and ids.count("GOLDBOTTLECAP") == 1, [x["group"] for x in sh["items"]
                                                                              if x["id"] in ("MASTERBALL", "GOLDBOTTLECAP")])
        chk("  랜덤 기술머신 뽑기권은 없다 (사용자)", row(sh, "RANKTICKETTM") is None
            and guild.coin_price("RANKTICKETTM") == 0)
        chk("  나머지 상품 값은 그대로 (생명의구슬)", guild.coin_price("LIFEORB") > 0
            and row(sh, "LIFEORB")["coin"] == guild.coin_price("LIFEORB"))

        print("\n=== 3. 사기 ===")
        r = guild.buy(u, "GOLDBOTTLECAP", 1)
        chk("금색병뚜껑 1개: 코인 -200 · 가방 +1 · 남은 1", r["spent"] == 200 and guild.coin(u) == 4800
            and bag(u, "GOLDBOTTLECAP") == 1 and row(guild.shop(u), "GOLDBOTTLECAP")["left"] == 1,
            (r, guild.coin(u), bag(u, "GOLDBOTTLECAP")))
        c = code_of(lambda: guild.buy(u, "GOLDBOTTLECAP", 2))
        chk("  남은 1개인데 2개 → 409 · 코인 · 가방 그대로", c and c[0] == 409 and guild.coin(u) == 4800
            and bag(u, "GOLDBOTTLECAP") == 1, c)
        guild.buy(u, "GOLDBOTTLECAP", 1)
        c = code_of(lambda: guild.buy(u, "GOLDBOTTLECAP", 1))
        chk("  2개 다 사면 다음은 409 '다음 시즌' · 남은 0", c and c[0] == 409 and "다음 시즌" in c[1]
            and row(guild.shop(u), "GOLDBOTTLECAP")["left"] == 0 and guild.coin(u) == 4600, c)
        c = code_of(lambda: guild.buy(u, "MASTERBALL", 2))
        chk("  한 번에 시즌 수보다 많이 (마스터볼 2개) → 409", c and c[0] == 409 and guild.coin(u) == 4600, c)
        poor = mkuser("가난", 599)
        c = code_of(lambda: guild.buy(poor, "MASTERBALL", 1))
        chk("  코인이 모자라면 400 · 산 수도 안 늘어남 (남은 1 그대로)", c and c[0] == 400
            and row(guild.shop(poor), "MASTERBALL")["left"] == 1 and guild.coin(poor) == 599, c)
        guild._coin_add(poor, 1)
        guild.buy(poor, "MASTERBALL", 1)
        chk("  모자란 만큼 채우면 산다 (남은 0 · 가방 +1)", bag(poor, "MASTERBALL") == 1 and guild.coin(poor) == 0
            and row(guild.shop(poor), "MASTERBALL")["left"] == 0)
        chk("  사람마다 따로 (육은 마스터볼 남은 1)", row(guild.shop(u), "MASTERBALL")["left"] == 1)

        real_run = db.run
        u2 = mkuser("터짐", 1000)

        def boom(sql, args=()):
            if sql.startswith("UPDATE guild_user SET coin = coin -"):
                raise RuntimeError("database is locked")
            return real_run(sql, args)
        db.run = boom
        try:
            guild.buy(u2, "GOLDBOTTLECAP", 1)
        except RuntimeError:
            pass
        finally:
            db.run = real_run
        chk("  코인 빼기가 터지면 이번 시즌 산 수도 되돌린다 (남은 2 · 코인 그대로) - 11/12 검토",
            row(guild.shop(u2), "GOLDBOTTLECAP")["left"] == 2 and guild.coin(u2) == 1000)

        print("\n=== 4. 다음 시즌 ===")
        season.SEASON = 8
        chk("시즌 8: 다시 2개 · 1개", row(guild.shop(u), "GOLDBOTTLECAP")["left"] == 2
            and row(guild.shop(poor), "MASTERBALL")["left"] == 1)
        guild.buy(u, "GOLDBOTTLECAP", 2)
        chk("  시즌 8 에 2개 더 산다", bag(u, "GOLDBOTTLECAP") == 4)

        print("\n=== 5. 되팔면 손해 ===")
        for iid, price, _n in guild.SHOP_EXCLUSIVE:
            chk("%s: 판 값 %d원 < 코인 값어치 %d원" % (iid, items.sell_price(iid), price * config.GUILD_COIN_WON),
                items.sell_price(iid) < price * config.GUILD_COIN_WON)
    finally:
        season.SEASON = real
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
