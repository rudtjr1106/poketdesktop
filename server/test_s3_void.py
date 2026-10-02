# -*- coding: utf-8 -*-
"""시즌 3 첫날 0~9시(한국 시각) 랜덤 배틀 지우기 + 하루를 한국 자정에 바꾸기 (1.8.0).

    python server/test_s3_void.py

서버를 띄우지 않는다. 임시 DB 에 그날과 같은 모양의 전적을 넣고 손질
(migrations._s3_void_early)을 돌린다.

## 무엇을 못 박나

  1. 그 시간대에 **건** 랜덤 배틀만 지운다 - 건 쪽·걸린 쪽 전적과 대전 로그.
     9시 이후 판, 그 전(시즌 2) 판, 친구 배틀은 그대로다.
  2. 건 사람의 점수는 **남은 판을 처음부터 다시 쌓은 값**이다: 숨은 점수는
     시즌을 연 직후의 값에서, RP 는 0 에서. 판마다의 변화량은 그대로 쓴다.
     바닥(0, 슈퍼볼에 닿았으면 150)을 다시 적용한다.
  3. 그 시간대에만 친 사람은 시즌을 연 직후로 돌아간다 (0판, 배치 전).
  4. 걸린 쪽(자고 있던 사람)의 점수는 한 글자도 안 바뀐다.
  5. 상금(돈)은 건드리지 않는다. 하루 도전 수도 그대로다.
  6. 두 번 돌아도 같다 (지울 것이 없다).
  7. 하루가 한국 자정에 바뀐다: UTC 로는 아직 어제여도 한국이 오늘이면 오늘이다.
"""
import datetime
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-s3void-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import db, migrations, pvp, season                  # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, str(got)[:300]))


def mkuser(name, rating=1000, money=0):
    uid = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,?,'','','')",
        (name, b"x", b"x", money)).lastrowid
    db.run("INSERT INTO rank_stat (user_id, rating, best, updated_at) VALUES (?,?,?,'')",
           (uid, rating, rating))
    return uid


MID = [100]


def game(a, b, at, result, delta, rp_delta, kind="random", reward=500):
    """a 가 b 에게 건 한 판. 서버가 하는 것처럼 두 사람의 전적과 로그를 남기고,
    건 쪽의 점수를 올린다. at 은 UTC ISO."""
    MID[0] += 1
    mid = MID[0]
    db.run("INSERT INTO pvp_match (id, kind, a_id, b_id, a_name, b_name, winner, turns,"
           " seed, engine, log, created_at) VALUES (?,?,?,?,?,?,?,10,1,'t','x',?)",
           (mid, kind, a, b, "a%d" % a, "b%d" % b, a if result == "win" else b, at))
    row = db.q1("SELECT * FROM rank_stat WHERE user_id=?", (a,))
    rating, rp = row["rating"], row["rp"]
    if kind == "random":
        rating = max(0, rating + delta)
        rp = max(season.floor_rp(row["peak_rp"]), rp + rp_delta)
        won, lost = int(result == "win"), int(result == "lose")
        streak = (max(1, row["streak"] + 1) if won else min(-1, row["streak"] - 1))
        games = row["games"] + 1
        db.run("UPDATE rank_stat SET rating=?, rp=?, peak_rp=?, games=?, wins=wins+?,"
               " losses=losses+?, streak=?, best=?, ranked=? WHERE user_id=?",
               (rating, rp, max(row["peak_rp"], rp), games, won, lost, streak,
                max(row["best"], rating), 1 if games >= pvp.PLACEMENT else 0, a))
    for uid, foe, started, res in ((a, b, 1, result),
                                   (b, a, 0, {"win": "lose", "lose": "win"}[result])):
        db.run("INSERT INTO battle_record (user_id, foe_id, foe_name, kind, result, rating,"
               " delta, reward, turns, match_id, started, ended_at, rp, rp_delta)"
               " VALUES (?,?,?,?,?,?,?,?,10,?,?,?,?,?)",
               (uid, foe, "u%d" % foe, kind, res,
                rating if started else 0, delta if started and kind == "random" else 0,
                reward if started else 0, mid, started, at,
                rp if started else 0, (rp - row["rp"]) if started and kind == "random" else 0))
    return mid


def stat(uid):
    return dict(db.q1("SELECT * FROM rank_stat WHERE user_id=?", (uid,)))


def run_once():
    conn = db.connect()
    note = migrations._s3_void_early(conn)
    conn.commit()
    return note


def main():
    db.init()
    print("=== 그날과 같은 모양 ===")
    heavy = mkuser("많이친사람", 1040, money=9000)     # 0~9시 3판 + 9시 이후 3판
    only = mkuser("그때만친사람", 980)                 # 0~9시 2판뿐
    late = mkuser("아침에친사람", 1000)                # 9시 이후만
    victim = mkuser("자던사람", 1100)                  # 걸리기만 했다
    db.run("UPDATE rank_stat SET rp=77, peak_rp=90, games=9, wins=6, losses=3, ranked=1"
           " WHERE user_id=?", (victim,))
    victim_before = stat(victim)

    old = game(heavy, victim, "2026-10-01T14:30:00+00:00", "win", 12, 20)     # 시즌 2 (자정 전)
    # 시즌을 연 것처럼 점수를 비운다 (0290 이 하는 일)
    db.run("UPDATE rank_stat SET games=0, wins=0, losses=0, draws=0, streak=0, ranked=0,"
           " rp=0, peak_rp=0, win_day='' WHERE user_id IN (?,?,?)", (heavy, only, late))
    db.run("UPDATE rank_stat SET best=rating")
    start_heavy = stat(heavy)["rating"]
    start_only = stat(only)["rating"]

    w1 = game(heavy, victim, "2026-10-01T15:40:08.123456+00:00", "win", 14, 24)
    w2 = game(heavy, late, "2026-10-01T16:00:00+00:00", "win", 12, 150)       # 슈퍼볼에 닿는다
    w3 = game(heavy, victim, "2026-10-01T23:59:59+00:00", "lose", -15, -21)
    o1 = game(only, victim, "2026-10-01T22:45:00+00:00", "lose", -10, 0)
    o2 = game(only, late, "2026-10-01T23:10:00+00:00", "win", 16, 29)
    fr = game(only, victim, "2026-10-01T23:20:00+00:00", "win", 0, 0, kind="friend")
    db.run("UPDATE rank_stat SET fought_day='2026-10-01', fought=3, win_day='2026-10-01'"
           " WHERE user_id=?", (heavy,))
    db.run("UPDATE rank_stat SET fought_day='2026-10-01', fought=2, win_day='2026-10-01'"
           " WHERE user_id=?", (only,))
    # 9시 이후
    a1 = game(heavy, victim, "2026-10-02T00:00:00+00:00", "win", 11, 30)      # 경계: 9시 정각은 남는다
    a2 = game(heavy, late, "2026-10-02T01:00:00+00:00", "lose", -13, -40)
    a3 = game(heavy, victim, "2026-10-02T02:00:00+00:00", "win", 10, 13)
    l1 = game(late, victim, "2026-10-02T03:00:00+00:00", "win", 15, 25)
    db.run("UPDATE rank_stat SET fought_day='2026-10-02', fought=3, win_day='2026-10-02'"
           " WHERE user_id=?", (heavy,))
    late_before = stat(late)
    heavy_was = stat(heavy)
    chk("(전제) 고치기 전에는 0~9시 점수가 얹혀 있다", heavy_was["games"] == 6
        and heavy_was["peak_rp"] >= 150, heavy_was)

    print("\n=== 손질 ===")
    note = run_once()
    print("   ", note)
    left = [r["match_id"] for r in db.q("SELECT match_id FROM battle_record")]
    chk("그 시간대에 건 랜덤 배틀은 양쪽 전적이 다 없다",
        not any(m in left for m in (w1, w2, w3, o1, o2)), left)
    chk("대전 로그도 없다", not db.q("SELECT 1 FROM pvp_match WHERE id IN (?,?,?,?,?)",
                                (w1, w2, w3, o1, o2)))
    chk("시즌 2 판은 그대로", left.count(old) == 2)
    chk("친구 배틀은 그대로", left.count(fr) == 2 and db.q1("SELECT 1 FROM pvp_match WHERE id=?", (fr,)))
    chk("9시 이후 판은 그대로 (정각 포함)", all(left.count(m) == 2 for m in (a1, a2, a3, l1)), left)
    chk("몇 명·몇 판인지 적는다", "2명" in note and "5판" in note, note)

    h = stat(heavy)
    chk("남은 판수·승패로 다시 센다", (h["games"], h["wins"], h["losses"]) == (3, 2, 1), h)
    chk("숨은 점수는 시즌을 연 직후 값에서 남은 판만큼", h["rating"] == start_heavy + 11 - 13 + 10,
        (h["rating"], start_heavy))
    # RP: 0 -> +30 = 30 -> -40 은 0 에서 멈춘다 -> +13 = 13. (슈퍼볼 바닥은 이제 없다)
    chk("RP 는 0 에서 다시 쌓고 바닥 0 을 지킨다", h["rp"] == 13 and h["peak_rp"] == 30, h)
    chk("배치(5판)는 다시 채워야 한다", h["ranked"] == 0, h["ranked"])
    chk("연승·연패도 남은 판으로", h["streak"] == 1, h["streak"])
    chk("가장 높았던 숨은 점수도", h["best"] == start_heavy + 11, (h["best"], start_heavy))
    chk("오늘 첫 승은 남은 판의 한국 날짜", h["win_day"] == "2026-10-02", h["win_day"])
    chk("하루 도전 수는 그대로 (9시 이후 판만 세어져 있다)",
        (h["fought_day"], h["fought"]) == ("2026-10-02", 3), (h["fought_day"], h["fought"]))
    recs = db.q("SELECT rp, rp_delta, rating FROM battle_record WHERE user_id=? AND started=1"
                " AND ended_at>=? ORDER BY id", (heavy, migrations.S3_VOID_TO))
    chk("남은 전적의 '그 판 뒤 RP' 도 새 값", [r["rp"] for r in recs] == [30, 0, 13],
        [r["rp"] for r in recs])
    chk("  바닥에 걸린 판은 실제로 깎인 만큼만 적는다", [r["rp_delta"] for r in recs] == [30, -30, 13],
        [r["rp_delta"] for r in recs])

    o = stat(only)
    chk("그때만 친 사람은 시즌을 연 직후로", (o["games"], o["wins"], o["losses"], o["rp"],
                                   o["peak_rp"], o["ranked"], o["streak"])
        == (0, 0, 0, 0, 0, 0, 0) and o["rating"] == start_only and o["win_day"] == "", o)
    chk("  친구 전적은 그대로", o["fr_wins"] == stat(only)["fr_wins"])
    chk("걸리기만 한 사람은 한 글자도 안 바뀐다", stat(victim) == victim_before,
        (stat(victim), victim_before))
    chk("9시 이후에만 친 사람도 그대로", stat(late) == late_before, (stat(late), late_before))
    chk("상금은 건드리지 않는다",
        db.q1("SELECT money FROM users WHERE id=?", (heavy,))["money"] == 9000)

    print("\n=== 슈퍼볼 바닥 ===")
    sb = mkuser("슈퍼볼", 1000)
    game(sb, victim, "2026-10-01T20:00:00+00:00", "win", 10, 20)
    game(sb, victim, "2026-10-02T04:00:00+00:00", "win", 10, 160)
    game(sb, victim, "2026-10-02T05:00:00+00:00", "lose", -10, -30)
    conn = db.connect()
    conn.execute("DELETE FROM meta WHERE k='mig:0300-s3-void-early'")
    note = run_once()
    s = stat(sb)
    chk("남은 판에서 슈퍼볼(150)에 닿았으면 그 아래로 안 내려간다", s["rp"] == 150
        and s["peak_rp"] == 160 and s["games"] == 2, s)

    print("\n=== 두 번 돌아도 ===")
    before = (stat(heavy), stat(only), stat(sb), len(db.q("SELECT 1 FROM battle_record")))
    note = run_once()
    chk("지울 것이 없고 값도 그대로", "없다" in note and before
        == (stat(heavy), stat(only), stat(sb), len(db.q("SELECT 1 FROM battle_record"))), note)
    chk("차례표에 올라 있다 (서버가 뜰 때 한 번 돈다)",
        ("0300-s3-void-early", migrations._s3_void_early) in migrations.ONCE)
    chk("적어 둔 숫자가 지금 규칙과 같다", migrations.S3_VOID_PLACEMENT == pvp.PLACEMENT
        and migrations.S3_VOID_SAFE_RP == season.SAFE_RP)

    print("\n=== 하루는 한국 자정에 바뀐다 ===")
    real = pvp._now
    try:
        utc = datetime.timezone.utc
        pvp._now = lambda: datetime.datetime(2026, 10, 2, 14, 59, 59, tzinfo=utc)
        chk("한국 23:59 는 아직 그날", pvp._today() == "2026-10-02", pvp._today())
        pvp._now = lambda: datetime.datetime(2026, 10, 2, 15, 0, 0, tzinfo=utc)
        chk("한국 00:00 에 다음 날 (UTC 로는 아직 2일)", pvp._today() == "2026-10-03", pvp._today())
        pvp._now = lambda: datetime.datetime(2026, 10, 3, 0, 0, 0, tzinfo=utc)
        chk("한국 09:00 에는 안 바뀐다 (예전에는 여기서 바뀌었다)", pvp._today() == "2026-10-03",
            pvp._today())
        # 스무 판을 다 쓴 사람: 9시가 지나도 못 걸고, 자정이 지나면 다시 건다
        cap = mkuser("스무판", 1000)
        db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, gender, shiny,"
               " happiness, ivs, evs, moves, on_desktop, slot, met_level, caught_at)"
               " VALUES (?,'PIKACHU',20,0,'HARDY','M',0,70,'{}','{}',?,1,0,5,'')",
               (cap, '["TACKLE"]'))
        db.run("UPDATE rank_stat SET fought_day='2026-10-03', fought=? WHERE user_id=?",
               (pvp.DAILY_BATTLES, cap))
        why = pvp.can_start(cap, "random")
        chk("  한국 09:00 - 아직 오늘 스무 판을 다 썼다", bool(why) and "20" in why, why)
        pvp._now = lambda: datetime.datetime(2026, 10, 3, 15, 0, 1, tzinfo=utc)
        chk("  한국 자정이 지나면 다시 걸 수 있다", pvp.can_start(cap, "random") is None,
            pvp.can_start(cap, "random"))
    finally:
        pvp._now = real

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
