# -*- coding: utf-8 -*-
"""시즌 3 -> 4 전환 (손질 0320) 과 시즌 4 의 규칙표.

    python server/test_season4.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다. 못 박는 것:

  1. 시즌 3 순위(RP 순)를 명예의 전당에 옮긴다. 배치를 마친 사람만.
  2. 보상은 **도달한 최고 티어**로, 챔피언·사천왕은 끝날 때의 자리로 준다 (선물함).
  3. 그다음에 RP 를 0, 숨은 점수를 1000 쪽으로 절반만 남긴다. 친구 전적은 그대로.
  4. 두 번 돌려도 선물을 또 넣지 않는다.
  5. 시즌 4 칭호가 있다 (지금 시즌의 규칙표는 test_season5.py).
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-season4-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import db, items, migrations, pvp, season  # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name):
    return db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,?,?,'')",
        (name, b"x", b"x", "2026-01-01", "2026-01-01")).lastrowid


def gifts_of(uid, title=migrations.S3_GIFT_TITLE):
    return [(r["kind"], r["item_id"], r["count"]) for r in db.q(
        "SELECT kind, item_id, count FROM gift WHERE user_id=? AND title=? ORDER BY id", (uid, title))]


def main():
    db.init()

    print("=== 시즌 4 ===")
    # 지금 시즌의 날짜 · 규칙표는 test_season5.py 가 본다 (시즌 5, 2026-11-01). 여기는 시즌 4 를 연 손질만.
    chk("티어 경계는 시즌 3 과 같다", [(k, rp) for k, _n, rp in season.TIERS] == migrations.S3_TIER_RP,
        season.TIERS)
    chk("시즌 4 칭호가 정해져 있다 (받으면 달 수 있다)",
        all(k in season.TITLES for k in ("s4_champion", "s4_elite", "s4_master", "s4_hyper", "s4_super")))
    chk("시즌 4 열기 손질이 목록에 있다", ("0320-season4-open", migrations._season4_open) in migrations.ONCE)

    print("\n=== 시즌 3 -> 4 전환 ===")
    # 시즌 3 이 끝난 상태: 마스터볼 여섯(자리는 다섯), 하이퍼·슈퍼·몬스터, 배치 못 마친 사람.
    # 한 명은 한때 마스터볼(peak 620)이었다가 400 으로 내려왔다 - 최고 티어로 받는다.
    s3 = {}
    plan = [("m1", 900, 900), ("m2", 800, 850), ("m3", 700, 700), ("m4", 650, 700),
            ("m5", 640, 640), ("m6", 610, 610), ("fell", 400, 620), ("hy", 360, 380),
            ("su", 200, 240), ("mo", 90, 120)]
    for i, (name, rp, peak) in enumerate(plan):
        u = mkuser("s3_" + name)
        pvp._rating_row(u)
        db.run("UPDATE rank_stat SET rating=?, best=?, games=30, wins=20, losses=10, ranked=1,"
               " rp=?, peak_rp=?, fr_wins=2, earned=500, earned_day='2026-10-16', streak=3,"
               " win_day='2026-10-16' WHERE user_id=?", (1300 - i * 10, 1300 - i * 10, rp, peak, u))
        s3[name] = u
    un = mkuser("s3_unranked")
    pvp._rating_row(un)
    db.run("UPDATE rank_stat SET rating=980, games=2, ranked=0, rp=0 WHERE user_id=?", (un,))
    low = mkuser("s3_low")
    pvp._rating_row(low)
    db.run("UPDATE rank_stat SET rating=801, games=9, ranked=1, rp=10, peak_rp=10 WHERE user_id=?", (low,))
    # 시즌 2 때 받은 선물이 남아 있어도 시즌 3 선물과 헷갈리지 않는다
    db.run("INSERT INTO gift (user_id, kind, item_id, count, title, message, created_at)"
           " VALUES (?,?,?,?,?,?,?)", (s3["m1"], "title", "s2_champion", 1, migrations.S2_GIFT_TITLE, "", ""))

    conn = db.connect()
    note = migrations._season4_open(conn)
    conn.commit()
    print("  (%s)" % note)
    res = dict((r["user_id"], r) for r in db.q("SELECT * FROM season_result WHERE season=3"))
    chk("배치를 마친 11명만 보관", len(res) == 11 and un not in res, len(res))
    chk("RP 1등이 1위 · 챔피언", res[s3["m1"]]["rank"] == 1 and res[s3["m1"]]["tier"] == "champion"
        and res[s3["m1"]]["title"] == "s3_champion", dict(res[s3["m1"]]))
    chk("2~5등은 사천왕 (자리는 넷)", all(res[s3[n]]["tier"] == "elite" for n in ("m2", "m3", "m4", "m5")),
        [res[s3[n]]["tier"] for n in ("m2", "m3", "m4", "m5")])
    chk("여섯째 마스터볼은 자리가 없어 마스터볼", res[s3["m6"]]["tier"] == "master", res[s3["m6"]]["tier"])
    chk("내려온 사람은 최고 티어(마스터볼)로, 순위는 지금 RP 로", res[s3["fell"]]["tier"] == "master"
        and res[s3["fell"]]["rp"] == 400 and res[s3["fell"]]["rank"] == 7, dict(res[s3["fell"]]))
    chk("하이퍼·슈퍼·몬스터", (res[s3["hy"]]["tier"], res[s3["su"]]["tier"], res[s3["mo"]]["tier"],
                          res[low]["tier"]) == ("hyper", "super", "monster", "monster"))
    chk("챔피언: 전설의 알 + 칭호 + 금빛 명패 + 사탕 1",
        gifts_of(s3["m1"]) == [("egg", "legendary", 1), ("title", "s3_champion", 1),
                               ("frame", "gold", 1), ("item", "SHINYCANDY", 1)], gifts_of(s3["m1"]))
    chk("사천왕: 환상의 알 + 칭호 + 은빛 명패 + 사탕 1",
        all(gifts_of(s3[n]) == [("egg", "mythical", 1), ("title", "s3_elite", 1),
                                ("frame", "silver", 1), ("item", "SHINYCANDY", 1)]
            for n in ("m2", "m3", "m4", "m5")), gifts_of(s3["m5"]))
    chk("마스터볼: 칭호 + 마스터볼 명패 + 사탕 1 (알 없음)",
        all(gifts_of(s3[n]) == [("title", "s3_master", 1), ("frame", "master", 1),
                                ("item", "SHINYCANDY", 1)] for n in ("m6", "fell")), gifts_of(s3["fell"]))
    chk("하이퍼볼·슈퍼볼: 칭호만", gifts_of(s3["hy"]) == [("title", "s3_hyper", 1)]
        and gifts_of(s3["su"]) == [("title", "s3_super", 1)], (gifts_of(s3["hy"]), gifts_of(s3["su"])))
    chk("몬스터볼·배치 못 마친 사람은 없음", gifts_of(s3["mo"]) == [] and gifts_of(un) == []
        and gifts_of(low) == [])
    msg = db.q1("SELECT message FROM gift WHERE user_id=? AND title=?",
                (s3["m1"], migrations.S3_GIFT_TITLE))["message"]
    chk("안내: 시즌 3, 자리와 순위, 알", "시즌 3" in msg and "챔피언 자리" in msg and "1위" in msg
        and "켜 둔 시간" in msg, msg)
    msg = db.q1("SELECT message FROM gift WHERE user_id=? AND title=?",
                (s3["fell"], migrations.S3_GIFT_TITLE))["message"]
    chk("안내: 최고 티어", "마스터볼 티어까지" in msg and "7위" in msg, msg)

    print("\n=== 점수 ===")
    st = pvp._rating_row(s3["m1"])
    chk("숨은 점수는 1000 쪽으로 절반 (1300 -> 1150)", st["rating"] == 1150 and st["best"] == 1150,
        (st["rating"], st["best"]))
    st_low = pvp._rating_row(low)
    chk("아래쪽도 절반 (801 -> 901)", st_low["rating"] == 901, st_low["rating"])
    chk("RP · 최고 RP · 판수 · 배치 · 연승 · 첫 승 날짜가 비었다",
        (st["rp"], st["peak_rp"], st["games"], st["wins"], st["losses"], st["ranked"], st["streak"],
         st["win_day"]) == (0, 0, 0, 0, 0, 0, 0, ""), dict(st))
    chk("배치 못 마친 사람의 점수도 같이 넘어간다 (980 -> 990)", pvp._rating_row(un)["rating"] == 990)
    chk("친구 전적·오늘 상금은 그대로", st["fr_wins"] == 2 and st["earned"] == 500)
    chk("자리가 비었다 (마스터볼이 없다)", season.seats() == {})

    print("\n=== 두 번 돌려도 ===")
    n_gift = db.q1("SELECT COUNT(*) c FROM gift")["c"]
    n_res = db.q1("SELECT COUNT(*) c FROM season_result WHERE season=3")["c"]
    migrations._season4_open(conn)
    conn.commit()
    chk("선물을 또 넣지 않는다", db.q1("SELECT COUNT(*) c FROM gift")["c"] == n_gift, n_gift)
    chk("순위표도 그대로다", db.q1("SELECT COUNT(*) c FROM season_result WHERE season=3")["c"] == n_res
        and db.q1("SELECT tier FROM season_result WHERE season=3 AND user_id=?", (s3["m1"],))["tier"] == "champion")

    print("\n=== 받기 ===")
    got = [x for x in items.gift_claim(s3["m1"])]
    kinds = [x["kind"] for x in got]
    chk("챔피언이 켜면 시즌 3 선물 네 줄을 받는다", kinds.count("egg") == 1 and "frame" in kinds
        and "item" in kinds and kinds.count("title") == 2, kinds)
    titles_owned = [t["id"] for t in season.owned(s3["m1"])[0]]
    chk("칭호 '시즌 3 챔피언' 을 가진다", "s3_champion" in titles_owned, titles_owned)
    hall = season.hall(3)
    chk("명예의 전당(시즌 3)", hall[0]["name"] == "s3_m1" and hall[0]["rp"] == 900
        and hall[0]["tierKr"] == "챔피언" and hall[0]["title"] == "시즌 3 챔피언", hall[:1])

    print("\n=== 손질을 통째로 돌려도 ===")
    migrations.run()
    chk("끝났다고 적힌다", db.q1("SELECT v FROM meta WHERE k='mig:0320-season4-open'") is not None)
    chk("선물은 그대로다", db.q1("SELECT COUNT(*) c FROM gift WHERE title=?",
                             (migrations.S3_GIFT_TITLE,))["c"] == n_gift - 1, n_gift)

    print("\n" + "=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
