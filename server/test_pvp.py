# -*- coding: utf-8 -*-
"""유저 배틀 코어 검사.

    python server/test_pvp.py [http://127.0.0.1:8788]

매칭(대기열/도전장)은 아직 없다. 여기서는 서버 안에서 run_match 를 직접
불러 '판이 제대로 끝나고 뒤처리가 맞는가' 만 본다. 그래서 이 검사는
**서버와 같은 기계에서** 돌려야 한다 - 컨테이너 안에서 돌린다.

돈이 오가고 점수가 움직이는 곳이라 숫자를 하나하나 맞춰 본다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db, items, pvp                        # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name, mons=3, level=30):
    """계정 하나와 바탕화면에 데리고 다니는 포켓몬 몇 마리."""
    import random
    from app import deps
    d = deps.dex()
    rng = random.Random(abs(hash(name)) % (1 << 30))
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,?,?,'')",
        (name, b"x", b"x", pvp._iso(), pvp._iso()))
    uid = cur.lastrowid
    for i in range(mons):
        m = d.roll_wild(level, level, rng)
        db.run(
            "INSERT INTO pokemon (user_id, species, level, exp, nature, ability,"
            " hidden_ability, gender, shiny, happiness, ivs, evs, moves,"
            " on_desktop, slot, met_level, caught_at)"
            " VALUES (?,?,?,?,?,?,0,?,0,?,?,?,?,1,?,?,?)",
            (uid, m["species"], m["level"], m.get("exp", 0), m["nature"],
             m.get("ability"), m.get("gender", "M"), m.get("happiness", 70),
             json.dumps(m["ivs"]), json.dumps(m.get("evs", {})),
             json.dumps(m["moves"]), i, m["level"], pvp._iso()))
    return uid


def money(uid):
    return items.money(uid)


def main():
    db.init()
    print("=== 준비 ===")
    a = mkuser("zz_pvp_a", 3, 30)
    b = mkuser("zz_pvp_b", 3, 30)
    chk("두 계정을 만들었다", a and b and a != b, (a, b))
    chk("돈은 0 에서 시작", money(a) == 0 and money(b) == 0,
        (money(a), money(b)))

    try:
        print("\n=== 한 판 ===")
        r = pvp.run_match(a, b, kind="random", seed=777)
        chk("판이 끝났다", r["matchId"] > 0, r)
        chk("승자가 둘 중 하나이거나 무승부",
            r["winner"] in (a, b, None), r["winner"])
        chk("결과가 서로 반대", {
            ("win", "lose"), ("lose", "win"), ("draw", "draw")
        }.__contains__((r["a"]["result"], r["b"]["result"])),
            (r["a"]["result"], r["b"]["result"]))

        print("\n=== 돈 ===")
        pa, pb = r["a"]["reward"], r["b"]["reward"]
        chk("이긴 쪽이 1000원", (pa if r["a"]["result"] == "win" else pb) == 1000,
            (pa, pb))
        chk("진 쪽도 300원은 받는다",
            (pb if r["a"]["result"] == "win" else pa) in (300, 500), (pa, pb))
        chk("실제 잔액에 반영됐다", money(a) == pa and money(b) == pb,
            (money(a), pa, money(b), pb))

        print("\n=== 점수 ===")
        chk("점수가 움직였다", r["a"]["delta"] != 0 or r["a"]["result"] == "draw",
            r["a"]["delta"])
        chk("두 사람의 점수 변동이 상쇄된다",
            abs(r["a"]["delta"] + r["b"]["delta"]) <= 1,
            (r["a"]["delta"], r["b"]["delta"]))
        sa = pvp.summary(a)
        chk("배치가 남아 있다 (5판 중 1판)", sa["placementLeft"] == 4,
            sa["placementLeft"])
        chk("아직 랭킹에 안 오른다", not sa["ranked"], sa)
        chk("순위표가 비어 있다", pvp.ranking() == [], pvp.ranking())

        print("\n=== 다시보기 ===")
        va = pvp.match_view(a, r["matchId"])
        vb = pvp.match_view(b, r["matchId"])
        chk("양쪽 다 볼 수 있다", va and vb)
        chk("이벤트 수가 같다", len(va["events"]) == len(vb["events"]),
            (len(va["events"]), len(vb["events"])))
        chk("결과가 서로 반대로 보인다",
            {va["result"], vb["result"]} in ({"win", "lose"}, {"draw"}),
            (va["result"], vb["result"]))
        chk("상대 이름이 서로 바뀌어 보인다",
            va["foe"]["name"] == vb["me"]["name"], (va["foe"], vb["me"]))
        m1 = [e for e in va["events"] if e["t"] == "match"][0]
        m2 = [e for e in vb["events"] if e["t"] == "match"][0]
        chk("로그의 승자도 뒤집힌다",
            m2["winner"] == {"me": "foe", "foe": "me", "draw": "draw"}[m1["winner"]],
            (m1["winner"], m2["winner"]))
        c = mkuser("zz_pvp_c", 1, 5)
        chk("남의 대전은 못 본다", pvp.match_view(c, r["matchId"]) is None)

        print("\n=== 전적 ===")
        rec = pvp.records(a)
        chk("전적이 한 줄 남았다", len(rec) == 1, len(rec))
        chk("상대 이름이 남았다", rec[0]["foe"] == "zz_pvp_b", rec[0])
        chk("받은 돈이 남았다", rec[0]["reward"] == pa, rec[0])

        print("\n=== 배치 5판 ===")
        for i in range(4):
            pvp.run_match(a, b, kind="random", seed=100 + i)
        sa = pvp.summary(a)
        chk("5판을 채웠다", sa["games"] == 5, sa["games"])
        chk("랭킹에 올랐다", sa["ranked"], sa)
        board = pvp.ranking()
        chk("순위표에 두 명이 보인다", len(board) == 2, board)
        chk("점수 높은 쪽이 위",
            len(board) < 2 or board[0]["rating"] >= board[1]["rating"], board)

        print("\n=== 하루 상한 ===")
        before = money(a)
        for i in range(20):
            pvp.run_match(a, b, kind="random", seed=500 + i)
        sa = pvp.summary(a)
        chk("하루 상한을 넘지 않는다", sa["earnedToday"] <= pvp.DAILY_CAP,
            sa["earnedToday"])
        chk("상한에 도달했다", sa["earnedToday"] == pvp.DAILY_CAP,
            sa["earnedToday"])
        gained = money(a) - before
        chk("상한 뒤로는 돈이 안 늘어난다",
            money(a) - before <= pvp.DAILY_CAP, gained)

        print("\n=== 친구 배틀 ===")
        d1 = mkuser("zz_pvp_d", 2, 30)
        e1 = mkuser("zz_pvp_e", 2, 30)
        fr = pvp.run_match(d1, e1, kind="friend", seed=900)
        chk("친구 배틀은 점수를 건드리지 않는다",
            fr["a"]["delta"] == 0 and fr["b"]["delta"] == 0,
            (fr["a"]["delta"], fr["b"]["delta"]))
        chk("친구 배틀 상금은 절반",
            max(fr["a"]["reward"], fr["b"]["reward"]) == 500,
            (fr["a"]["reward"], fr["b"]["reward"]))
        sd = pvp.summary(d1)
        chk("배치 판수에는 안 들어간다", sd["games"] == 0, sd["games"])
        chk("친구 전적에는 남는다",
            sd["friendWins"] + sd["friendLosses"] + sd["friendDraws"] == 1, sd)

        print("\n=== 못 붙이는 경우 ===")
        f1 = mkuser("zz_pvp_f", 0)
        try:
            pvp.run_match(a, f1)
            chk("포켓몬이 없으면 거부한다", False, "예외가 안 났다")
        except ValueError:
            chk("포켓몬이 없으면 거부한다", True)

        print("\n=== 로그 정리 ===")
        n0 = db.q1("SELECT COUNT(*) c FROM pvp_match")["c"]
        pvp.prune(days=0)
        n1 = db.q1("SELECT COUNT(*) c FROM pvp_match")["c"]
        chk("아직 안 본 판은 안 지운다", n1 == n0, (n0, n1))
        for m in db.q("SELECT id FROM pvp_match"):
            pvp.mark_seen(a, m["id"])
            pvp.mark_seen(b, m["id"])
        pvp.prune(days=0)
        n2 = db.q1("SELECT COUNT(*) c FROM pvp_match")["c"]
        chk("양쪽이 다 본 판은 지운다", n2 < n1, (n1, n2))
        chk("전적은 그대로 남는다", len(pvp.records(a, 100)) >= 5,
            len(pvp.records(a, 100)))
    finally:
        for n in ("zz_pvp_a", "zz_pvp_b", "zz_pvp_c", "zz_pvp_d",
                  "zz_pvp_e", "zz_pvp_f"):
            db.run("DELETE FROM users WHERE username=?", (n,))

    print("\n======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
