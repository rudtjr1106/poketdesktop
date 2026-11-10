# -*- coding: utf-8 -*-
"""랜덤 배틀 상대 고르기 — 시즌 4: 점수(RP)가 가까운 사람부터.

    python server/test_match_rp.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다. 못 박는 것:

  1. **RP 가 가까운 사람이 먼저다.** 전력이 더 비슷한 사람이 있어도 RP 가 먼 띠에 있으면
     가까운 띠의 사람을 고른다.
  2. 띠는 ±50 -> ±100 -> ±200 -> 전체로 넓어진다. 전체까지 가므로 받을 수 있는 사람이
     하나라도 있으면 붙는다 (전력 띠는 이제 사람을 떨어뜨리지 않는다).
  3. **띠 안에서도 RP 가 가장 가까운 사람부터** (10/17 제보 "4·10점 차이도 있는데 50점 차이와 붙는다").
     하루 안에 만난 사람은 RP 30점 더 먼 것으로 친다. RP 가 거의 같으면(10점 안) 전력이 가까운 몇 명 중에서.
  4. 그대로인 것: 받는 쪽 마릿수, 방금 붙은 사람·차단한 사람 제외.
  5. **RP 띠가 배치보다 먼저다** (10/17). 같은 띠 안에서만 배치를 마친 사람끼리 먼저 붙인다 -
     배치가 같은 사람을 찾느라 RP 가 먼 상대를 고르지 않는다.
  6. **3시간 건너뛰기는 한국 시각 자정에 새로 센다** (11/10). 같은 상대 30분 쿨타임은 자정에도 그대로다.
"""
import datetime
import os
import random
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-matchrp-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import db, deps, pvp  # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name, mons=6, level=50, species="PIKACHU", rp=0, games=10, rating=1000):
    """포켓몬 mons 마리(같은 종·레벨)를 데리고 다니는 사람. 전력은 종과 레벨로만 정해진다."""
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,?,?,'')",
        (name, b"x", b"x", "2026-01-01", "2026-01-01"))
    uid = cur.lastrowid
    d = deps.dex()
    rng = random.Random(zlib.crc32(name.encode("utf-8")))
    for i in range(mons):
        m = d.roll_wild(level, level, rng)
        m["species"] = species
        pid = db.insert_mon(uid, m, "2026-01-01")
        db.run("UPDATE pokemon SET on_desktop=1, slot=?, level=? WHERE id=?", (i, level, pid))
    pvp._rating_row(uid)
    db.run("UPDATE rank_stat SET rp=?, peak_rp=?, games=?, rating=? WHERE user_id=?",
           (rp, rp, games, rating, uid))
    return uid


def picks(uid, n=40):
    return [pvp.find_opponent(uid, random.Random(k)) for k in range(n)]


def wipe():
    for t in ("battle_record", "pvp_match", "match_log", "friend_block", "rank_team",
              "rank_stat", "pokemon", "users"):
        db.run("DELETE FROM %s" % t)


def main():
    db.init()
    # 이 검사는 전력을 '같은 종 여섯 마리' 로 맞춘다. 같은 종은 한 팀에 한 마리(10/22)라 그대로 두면 한 마리만
    # 나가서 랭크전 조건에 못 든다 - 여기서만 그 상한을 푼다 (같은 종 규칙은 test_legend_limit 가 본다).
    pvp.SAME_SPECIES_MAX = 6
    # 3시간 건너뛰기가 자정에 새로 세므로, 검사를 0~3시에 돌리면 '1시간 전' 이 어제가 된다 - 오후 3시로 묶는다
    real_now = pvp._now
    pvp._now = lambda: datetime.datetime(2026, 11, 10, 15, 0, tzinfo=pvp.KST).astimezone(datetime.timezone.utc)

    print("=== 띠 ===")
    chk("RP 띠는 ±50, ±100, ±200, 전체 순", pvp.RP_BANDS == (50, 100, 200, None), pvp.RP_BANDS)

    print("\n=== RP 가 가까운 사람이 먼저 ===")
    me = mkuser("mm_me", rp=300)
    # 랭크전은 Lv.50 이상 여섯 마리만 나간다 (시즌 4) - 전력 차이는 레벨 대신 종족값으로 낸다
    near_rp = mkuser("mm_near_rp", species="RATTATA", rp=320)  # RP 는 가깝고 전력은 30% 쯤 낮다 (253 대 320)
    twin = mkuser("mm_twin", level=50, rp=700)                 # 전력은 똑같고 RP 는 멀다
    got = set(picks(me))
    chk("전력이 똑같은 사람이 있어도 RP 가 가까운 사람을 고른다", got == {near_rp}, got)
    row = db.q1("SELECT stage, band, near FROM match_log WHERE user_id=? ORDER BY id DESC LIMIT 1", (me,))
    chk("±50 띠에서 골랐다고 남는다", row["band"] == 50 and row["near"] == 1, dict(row))

    print("\n=== 띠가 넓어진다 ===")
    wipe()
    me = mkuser("mm_me", rp=300)
    b100 = mkuser("mm_b100", rp=380)
    b200 = mkuser("mm_b200", rp=480)
    far = mkuser("mm_far", rp=900)
    chk("±50 에 없으면 ±100 에서", set(picks(me)) == {b100}, set(picks(me)))
    db.run("DELETE FROM pokemon WHERE user_id=?", (b100,))
    chk("±100 에도 없으면 ±200 에서", set(picks(me)) == {b200}, set(picks(me)))
    db.run("DELETE FROM pokemon WHERE user_id=?", (b200,))
    got = set(picks(me))
    chk("그 밖에만 있으면 전체에서", got == {far}, got)
    row = db.q1("SELECT band FROM match_log WHERE user_id=? ORDER BY id DESC LIMIT 1", (me,))
    chk("전체에서 골랐다고 남는다 (-1)", row["band"] == -1, dict(row))

    print("\n=== 전력은 이제 사람을 떨어뜨리지 않는다 ===")
    wipe()
    me = mkuser("mm_me", species="DRAGONITE", level=50, rp=0)   # 전설은 한 마리만 나가서 랭크전 조건에 못 든다
    weak = mkuser("mm_weak", species="CATERPIE", level=50, rp=0)
    teams = pvp._all_teams()
    gap = abs(pvp.team_power(teams[weak]) / pvp.team_power(teams[me]) - 1)
    chk("전력이 25% 넘게 달라도", gap > pvp.POWER_BANDS[-1], gap)
    chk("RP 가 같으면 붙는다", set(picks(me, 6)) == {weak}, set(picks(me, 6)))

    print("\n=== 띠 안에서도 RP 가 가장 가까운 사람 (10/17 제보) ===")
    wipe()
    me = mkuser("mm_me", rp=100)
    r4, r10, r48 = mkuser("mm_r4", rp=104), mkuser("mm_r10", rp=110), mkuser("mm_r48", rp=148)
    got = set(picks(me, 60))
    chk("4점 · 10점 차이가 있으면 48점 차이와는 안 붙는다", r48 not in got, got)
    chk("  RP 가 거의 같은 둘(10점 안)은 번갈아 나온다 (같은 얼굴만 나오지 않게)", got == {r4, r10}, got)

    def met_hours_ago(foe, hours):
        at = pvp._iso(pvp._now() - datetime.timedelta(hours=hours))
        db.run("INSERT INTO battle_record (user_id, foe_id, foe_name, kind, result, ended_at, started)"
               " VALUES (?,?,?,?,?,?,1)", (me, foe, "x", "random", "win", at))
    met_hours_ago(r4, 5)
    got = set(picks(me, 40))
    chk("오늘 만난 사람은 30점 더 먼 것으로 친다 (4점이 34점이 되어 10점 차이를 고른다)", got == {r10}, got)
    met_hours_ago(r10, 5)
    got = set(picks(me, 40))
    chk("  둘 다 만났어도 48점 차이보다는 가깝다 (34 · 40 < 48)", got == {r4, r10}, got)
    db.run("DELETE FROM battle_record")
    met_hours_ago(r4, 1)                                  # 3시간 안에 붙은 사람은 아예 안 고른다 (그대로)
    got = set(picks(me, 40))
    chk("  3시간 안에 붙은 사람은 RP 가 가까워도 안 고른다", got == {r10}, got)
    db.run("DELETE FROM battle_record")

    print("\n=== 3시간 건너뛰기는 한국 시각 자정에 새로 센다 (11/10) ===")
    # 11/09 0시: 밤에 그날 몫 20판으로 RP 가 가까운 사람을 다 만난 사람이 자정에 20판을 더 치자, 그들이 모두
    # 3시간 건너뛰기에 걸려 RP 가 1,300점 넘게 낮은 사람만 스무 번 만났다.
    wipe()
    me = mkuser("mm_me", rp=1700)
    near = mkuser("mm_near", rp=1720)
    far = mkuser("mm_far", rp=300)

    def kst(day, h, m):
        return datetime.datetime(2026, 11, day, h, m, tzinfo=pvp.KST).astimezone(datetime.timezone.utc)

    def met_at(foe, t, practice=0):
        db.run("INSERT INTO battle_record (user_id, foe_id, foe_name, kind, result, ended_at, started, practice)"
               " VALUES (?,?,?,?,?,?,1,?)", (me, foe, "x", "random", "win", pvp._iso(t), practice))

    met_at(near, kst(8, 23, 10))
    pvp._now = lambda: kst(8, 23, 50)
    got = set(picks(me, 8))
    chk("자정 전(23:50)에는 40분 전(23:10)에 만난 사람을 뺀다", got == {far}, got)
    pvp._now = lambda: kst(9, 0, 1)
    got = set(picks(me, 8))
    chk("**자정이 지나면(0:01) 어제 밤에 만난 RP 가까운 사람을 다시 고른다**", got == {near}, got)
    met_at(near, kst(9, 0, 1))
    pvp._now = lambda: kst(9, 0, 40)
    got = set(picks(me, 8))
    chk("  오늘 만난 사람은 그대로 3시간 동안 안 고른다 (0:01 에 만났으면 0:40 에도)", got == {far}, got)
    db.run("DELETE FROM battle_record")
    met_at(near, kst(8, 23, 55))
    pvp._now = lambda: kst(9, 0, 5)
    got = set(picks(me, 8))
    chk("같은 상대 30분 쿨타임은 자정에도 그대로 (23:55 에 만난 사람은 0:05 에 안 고른다)", got == {far}, got)
    pvp._now = lambda: kst(9, 0, 30)
    got = set(picks(me, 8))
    chk("  30분이 지나면(0:30) 다시 고른다", got == {near}, got)
    pvp._now = lambda: datetime.datetime(2026, 11, 10, 15, 0, tzinfo=pvp.KST).astimezone(datetime.timezone.utc)
    db.run("DELETE FROM battle_record")

    print("\n=== RP 가 같으면 전력이 가까운 사람 ===")
    wipe()
    me = mkuser("mm_me", level=50, rp=100)
    # 피카츄(320) 와 종족값이 가까운 셋 (전력 차 2~7%) / 먼 넷 (전력 차 50% 쯤) - 모두 Lv.50, RP 도 같다
    close = [mkuser("mm_c%d" % i, species=sp, rp=100)
             for i, sp in enumerate(("KRABBY", "CLEFAIRY", "MANKEY"), 1)]
    loose = [mkuser("mm_l%d" % i, species=sp, rp=100)
             for i, sp in enumerate(("CATERPIE", "WEEDLE", "MAGIKARP", "SUNKERN"))]
    got = set(picks(me, 60))
    chk("RP 가 같은 사람이 여럿이면 전력이 가까운 셋 중에서만", got == set(close), (got, close))
    chk("늘 한 사람만 나오지는 않는다", len(got) >= 2, got)

    print("\n=== 그대로인 규칙 ===")
    wipe()
    me = mkuser("mm_me", mons=6, rp=200)
    five = mkuser("mm_five", mons=5, rp=200)                   # 받는 쪽이 더 적다
    six_far = mkuser("mm_six", mons=6, rp=900)
    chk("받는 쪽이 적으면 RP 가 같아도 안 붙인다", set(picks(me, 8)) == {six_far}, set(picks(me, 8)))

    wipe()
    me = mkuser("mm_me", rp=200, games=10)
    rookie = mkuser("mm_rookie", rp=200, games=0)              # 배치 전, RP 는 같다
    vet = mkuser("mm_vet", rp=420, games=30)                   # 배치를 마쳤고 RP 는 ±200 밖
    chk("**RP 띠가 배치보다 먼저** - 배치가 달라도 RP 가 가까운 사람 (10/17)",
        set(picks(me, 8)) == {rookie}, set(picks(me, 8)))
    row = db.q1("SELECT stage, band FROM match_log WHERE user_id=? ORDER BY id DESC LIMIT 1", (me,))
    chk("  ±50 띠의 '전체' 에서 골랐다고 남는다", row["stage"] == "all" and row["band"] == 50, dict(row))
    vet2 = mkuser("mm_vet2", rp=230, games=30)                 # 배치를 마쳤고 같은 ±50 띠
    chk("같은 띠 안에서는 배치를 마친 사람끼리 먼저", set(picks(me, 8)) == {vet2}, set(picks(me, 8)))
    db.run("DELETE FROM pokemon WHERE user_id IN (?,?)", (rookie, vet2))
    chk("가까운 띠에 아무도 없으면 넓혀서 (배치를 마친 RP 420)", set(picks(me, 8)) == {vet}, set(picks(me, 8)))

    wipe()
    me = mkuser("mm_me", rp=200)
    a = mkuser("mm_a", rp=200)
    b = mkuser("mm_b", rp=900)
    pvp.run_match(me, a, kind="random", seed=3)
    db.run("UPDATE rank_stat SET rp=200 WHERE user_id IN (?,?)", (me, a))
    chk("방금 붙은 사람은 RP 가 같아도 다시 안 고른다", set(picks(me, 8)) == {b}, set(picks(me, 8)))

    wipe()
    me = mkuser("mm_me", rp=200)
    a = mkuser("mm_a", rp=200)
    b = mkuser("mm_b", rp=900)
    db.run("INSERT INTO friend_block (user_id, target_id, created_at) VALUES (?,?,?)",
           (a, me, "2026-01-01"))
    chk("나를 차단한 사람은 안 고른다", set(picks(me, 8)) == {b}, set(picks(me, 8)))

    wipe()
    me = mkuser("mm_me", rp=200)
    chk("아무도 없으면 None", pvp.find_opponent(me) is None)
    pvp._now = real_now

    print("\n" + "=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
