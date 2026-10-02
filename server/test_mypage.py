# -*- coding: utf-8 -*-
"""마이페이지 검사 (1.9.0).

    python server/test_mypage.py

/api/mypage 가 여기저기 흩어진 내 기록을 한 번에 모아 주는지 본다:
가입일·칭호·티어, 포켓몬·도감 수, 이긴 관장 수, 지금 시즌과 지난 시즌,
레이드, 내가 쓴 글·댓글·받은 좋아요, 알림.
"""
import datetime
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-mypage-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ.pop("POKET_BOARD_ADMINS", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import board, db, deps, gym, mypage, season         # noqa: E402

OK = FAIL = 0
NOW = datetime.datetime(2026, 10, 2, 3, 0, 0, tzinfo=datetime.timezone.utc)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name, created="2026-09-23T03:00:00+00:00"):
    cur = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                 " created_at, last_login, last_ip) VALUES (?,?,?,1,10,1234,?,'','')",
                 (name, b"x", b"x", created))
    return {"id": cur.lastrowid, "username": name}


def mkmon(uid, species, shiny=0, level=10):
    db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, ivs, evs, moves,"
           " met_level, caught_at, shiny) VALUES (?,?,?,0,'HARDY','{}','{}','[]',?,?,?)",
           (uid, species, level, level, "2026-09-23T03:00:00+00:00", shiny))


def main():
    db.init()
    dex = deps.dex()
    me = mkuser("주인공")
    other = mkuser("남")
    uid = me["id"]

    print("=== 아무것도 안 한 사람 ===")
    d = mypage.build(me, dex, NOW)
    chk("이름과 가입 며칠째", d["user"]["name"] == "주인공" and d["user"]["days"] == 10, d["user"])
    chk("0 으로 채워져 온다 (오류 없이)", d["counts"]["pokemon"] == 0 and d["gym"]["cleared"] == 0
        and d["titles"]["count"] == 0 and d["raid"]["games"] == 0 and d["board"]["postCount"] == 0, d["counts"])
    chk("관장 전체 수", d["gym"]["total"] == len(gym.gyms()["regions"]) and d["gym"]["total"] > 0)
    s0 = d["seasons"][0]
    chk("지금 시즌이 맨 앞 (배치 전)", len(d["seasons"]) == 1 and s0["current"] and s0["season"] == season.SEASON
        and s0["ranked"] is False and s0["rank"] is None, s0)

    print("\n=== 기록이 쌓인 사람 ===")
    mkmon(uid, "PIKACHU", level=30)
    mkmon(uid, "CHARIZARD", shiny=1, level=55)
    mkmon(uid, "TOGEKISS")
    for sp, caught in (("PIKACHU", 1), ("CHARIZARD", 1), ("TOGEKISS", 1), ("MEW", 0)):
        db.run("INSERT INTO seen (user_id, species, caught, first_at) VALUES (?,?,?,'')", (uid, sp, caught))
    regions = list(gym.gyms()["regions"].items())[:3]
    for code, tid in regions:
        db.run("INSERT INTO gym_clear (user_id, region, trainer, wins, best_turns, first_at, last_at)"
               " VALUES (?,?,?,2,10,'','')", (uid, code, tid))
    db.run("INSERT INTO friend (a_id, b_id, state, asked_by, created_at) VALUES (?,?,'accepted',?,'')",
           (min(uid, other["id"]), max(uid, other["id"]), uid))
    # 지금 시즌: 배치를 마치고 RP 120. 남은 RP 300 으로 위에 있다.
    # (처음 본 마이페이지가 내 줄을 이미 만들어 뒀다 - 있으면 고친다)
    for who, vals in ((uid, (1040, 9, 6, 3, 120, 130)), (other["id"], (1100, 9, 8, 1, 300, 300))):
        db.run("INSERT INTO rank_stat (user_id, updated_at) VALUES (?, '')"
               " ON CONFLICT(user_id) DO NOTHING", (who,))
        db.run("UPDATE rank_stat SET rating=?, games=?, wins=?, losses=?, ranked=1, rp=?, peak_rp=?"
               " WHERE user_id=?", vals + (who,))
    # 지난 시즌 둘
    tid = sorted(season.TITLES)[0]
    db.run("INSERT INTO season_result (season, user_id, rank, name, rating, rp, tier, games, wins,"
           " losses, draws, title, at) VALUES (2,?,7,'주인공',1100,410,?,40,25,15,0,?,'')",
           (uid, season.TIERS[1][0], tid))
    db.run("INSERT INTO season_result (season, user_id, rank, name, rating, rp, tier, games, wins,"
           " losses, draws, title, at) VALUES (1,?,3,'주인공',1210,0,NULL,30,20,10,0,NULL,'')", (uid,))
    season.grant(uid, "title", tid, 2)
    # 게시판
    p1 = board.create(me, "free", "내 글", "내용", now=NOW)
    board.like(other, p1)
    board.comment(other, p1, "남의 댓글", now=NOW + datetime.timedelta(seconds=60))
    p2 = board.create(other, "free", "남의 글", "내용", now=NOW)
    board.comment(me, p2, "내 댓글", now=NOW + datetime.timedelta(seconds=120))

    d = mypage.build(me, dex, NOW + datetime.timedelta(seconds=200))
    c = d["counts"]
    chk("포켓몬 수·색이 다른 수·가장 높은 레벨", (c["pokemon"], c["shiny"], c["topLevel"]) == (3, 1, 55), c)
    chk("도감: 잡은 종·본 종·전체", (c["dexCaught"], c["dexSeen"]) == (3, 4) and c["dexTotal"] == len(dex.species), c)
    chk("친구 수", c["friends"] == 1, c)
    chk("이긴 관장 수와 이긴 횟수", d["gym"]["cleared"] == 3 and d["gym"]["wins"] == 6, d["gym"])
    chk("가진 칭호와 달고 있는 칭호", d["titles"]["count"] == 1
        and d["titles"]["owned"][0]["name"] == season.TITLES[tid]
        and d["titles"]["equipped"] == season.TITLES[tid] and d["user"]["title"] == season.TITLES[tid]
        and d["titles"]["total"] > 1, d["titles"])
    s = d["seasons"]
    chk("시즌은 지금 → 지난 순서", [x["season"] for x in s] == [season.SEASON, 2, 1], [x["season"] for x in s])
    chk("지금 시즌: 순위·RP·전적", s[0]["ranked"] and s[0]["rank"] == 2 and s[0]["rp"] == 120
        and (s[0]["wins"], s[0]["losses"]) == (6, 3) and s[0]["tierKr"], s[0])
    chk("시즌 2: 순위·티어·RP·받은 칭호", s[1]["rank"] == 7 and s[1]["rp"] == 410
        and s[1]["tierKr"] == season.TIERS[1][1] and s[1]["title"] == season.TITLES[tid], s[1])
    chk("시즌 1 은 RP·티어가 없다 (숨은 점수뿐)", s[2]["rank"] == 3 and s[2]["rp"] is None
        and s[2]["tierKr"] is None and s[2]["rating"] == 1210, s[2])
    b = d["board"]
    chk("내 글·댓글 수와 받은 좋아요", (b["postCount"], b["commentCount"], b["likes"]) == (1, 1, 1), b)
    chk("알림 수와 안 본 수", (b["notifyCount"], b["unseen"]) == (1, 1), b)
    f = b["first"]
    chk("안 본 알림이 있으면 알림 쪽부터 싣는다", f["what"] == "notify" and f["page"] == 1
        and f["items"][0]["actor"] == "남" and f["items"][0]["seen"] is False, f)
    chk("한 쪽 크기를 같이 준다", b["pageSize"] == board.MINE_PAGE == f["size"])
    chk("목록을 통째로 싣지 않는다 (쌓여도 안 길어진다)", "posts" not in b and "comments" not in b
        and "notify" not in d, list(b.keys()))
    board.notify_seen(uid)
    f = mypage.build(me, dex, NOW + datetime.timedelta(seconds=300))["board"]["first"]
    chk("안 본 알림이 없으면 내 글 쪽부터", f["what"] == "posts" and f["items"][0]["id"] == p1
        and f["items"][0]["comments"] == 1 and f["items"][0]["likes"] == 1, f)
    c = board.mine_page(uid, "comments", 1)
    chk("내 댓글은 따로 받는다 (어느 글에 달았는지와 함께)", c["items"][0]["postId"] == p2
        and c["items"][0]["title"] == "남의 글" and c["items"][0]["snippet"] == "내 댓글", c["items"])

    print("\n=== 라우트 ===")
    r = mypage.mypage(ctx={"user": me})
    chk("GET /api/mypage", r["user"]["id"] == uid and r["gym"]["cleared"] == 3)
    from app import main as app_main
    paths = app_main.app.openapi()["paths"]
    chk("서버에 걸려 있다 (게시판의 새 길도)", all(x in paths for x in (
        "/api/mypage", "/api/board/notify", "/api/board/notify/seen", "/api/board/{pid}/like",
        "/api/board/mine")),
        [x for x in paths if "board" in x or "mypage" in x])
    order = [x for x in paths if x.startswith("/api/board/")]
    chk("notify·mine 이 {pid} 보다 먼저 걸려 있다", order.index("/api/board/notify") < order.index("/api/board/{pid}")
        and order.index("/api/board/mine") < order.index("/api/board/{pid}"), order)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
