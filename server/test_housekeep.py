# -*- coding: utf-8 -*-
"""끝난 배틀을 치운다 (10/28, app/housekeep.py). 서버를 띄우지 않는다.

    python server/test_housekeep.py

운영 DB 3.1GB 중 2.3GB 가 끝난 관장 배틀(gym_battle)이었다 - 지우는 곳이 없었다.

  1. 끝난 지 BATTLE_KEEP_DAYS 일 지난 판만 지운다. 진행 중 · 최근 판은 남긴다.
  2. 결과를 기다리는 길드전 공격의 판은 남긴다. **battle_id 가 NULL 인 공격이 있어도** 지운다
     (NOT IN 목록에 NULL 이 섞이면 아무것도 안 지워지는 함정).
  3. 경계 번호는 번호 사이가 비어 있어도 맞게 찾는다. 덩어리로 나눠도 다 지운다.
  4. 처음 한 번(migrations 0330)은 지우고 VACUUM 해서 파일이 실제로 줄어든다. 두 번 돌지 않는다.
"""
import datetime
import os
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-housekeep-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_HOUSEKEEP"] = "0"

from app import config, db, housekeep, migrations          # noqa: E402

OK = FAIL = 0
NOW = datetime.datetime(2026, 10, 28, 12, 0, tzinfo=datetime.timezone.utc)
BIG = "x" * 18000                       # 운영의 관장 판 하나만큼 (넘침 페이지가 생긴다)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def ago(days):
    return (NOW - datetime.timedelta(days=days)).isoformat()


def mkuser(name):
    return db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, created_at) VALUES (?,?,?,1,'')",
                  (name, b"x", b"x")).lastrowid


def gym(uid, days, state="done", data=BIG):
    return db.run("INSERT INTO gym_battle (user_id, region, trainer, state, result, turn, rev, data,"
                  " created_at, updated_at) VALUES (?,?,?,?,?,1,1,?,?,?)",
                  (uid, "11110", "t1", state, "won" if state == "done" else None, data, ago(days), ago(days))
                  ).lastrowid


def wild(uid, days, state="done"):
    return db.run("INSERT INTO battle (user_id, wild_id, mine_id, state, result, turn, me, foe, created_at,"
                  " expires_at) VALUES (?,1,1,?,?,1,'{}','{}',?,?)",
                  (uid, state, "won" if state == "done" else None, ago(days), ago(days))).lastrowid


def attack(bid, result):
    db.run("INSERT INTO guild_war_attack (season, region, atk_user, atk_guild, atk_name, def_user, def_guild,"
           " def_name, result, battle_id, created_at) VALUES (1,'c01',1,1,'a',2,2,'b',?,?,?)",
           (result, bid, ago(0)))


def ids(table):
    return set(r["id"] for r in db.q("SELECT id FROM %s" % table))


def main_():
    db.init()
    uid = mkuser("치우기")

    print("\n=== 1~2. 무엇을 지우고 무엇을 남기나 ===")
    old = [gym(uid, 5) for _ in range(6)]
    db.run("DELETE FROM gym_battle WHERE id IN (?, ?)", (old[1], old[2]))       # 번호 사이를 비운다
    old = [old[0]] + old[3:]
    stale = gym(uid, 5, state="active")            # 진행 중은 오래돼도 TTL 이 접는다 - 여기선 안 건드린다
    waiting = gym(uid, 5)                          # 길드전 공격이 결과를 기다린다
    settled = gym(uid, 5)                          # 길드전 공격이 이미 끝났다 -> 지워도 된다
    recent = gym(uid, 1)
    edge = gym(uid, config.BATTLE_KEEP_DAYS - 0.01)
    attack(waiting, "pending")
    attack(settled, "win")
    attack(None, "pending")                        # battle_id 가 없는 공격 (NULL)
    w_old = [wild(uid, 4) for _ in range(3)]
    w_act = wild(uid, 4, state="active")
    w_new = wild(uid, 0.5)

    done = housekeep.prune_battles(now=NOW, pause=0)
    left = ids("gym_battle")
    chk("관장: 3일 지난 끝난 판을 지운다", not (set(old) | {settled}) & left, sorted(left))
    chk("관장: 진행 중인 판은 남긴다", stale in left)
    chk("관장: 결과를 기다리는 길드전 공격의 판은 남긴다 (NULL 공격이 섞여 있어도)", waiting in left)
    chk("관장: 최근 판 · 경계 바로 안쪽 판은 남긴다", {recent, edge} <= left, sorted(left))
    chk("관장: 지운 수", done["gym_battle"] == len(old) + 1, done)
    wl = ids("battle")
    chk("야생: 지난 끝난 판만 지운다", wl == {w_act, w_new}, sorted(wl))
    chk("야생: 지운 수", done["battle"] == 3, done)
    again = housekeep.prune_battles(now=NOW, pause=0)
    chk("다시 돌면 지울 것이 없다", again == {"gym_battle": 0, "battle": 0}, again)

    print("\n=== 3. 경계 번호 · 덩어리 ===")
    db.run("DELETE FROM gym_battle")
    chk("빈 표", housekeep.cutoff_id("gym_battle", ago(3)) == 1)
    a = [gym(uid, 10, data="{}") for _ in range(5)]
    b = [gym(uid, 0, data="{}") for _ in range(5)]
    db.run("DELETE FROM gym_battle WHERE id IN (?, ?, ?)", (a[3], a[4], b[0]))   # 경계 양쪽을 비운다
    cid = housekeep.cutoff_id("gym_battle", ago(3))
    chk("경계 번호: 오래된 줄은 모두 그 아래, 새 줄은 모두 그 위", max(a[:3]) < cid <= min(b[1:]), (a, b, cid))
    chk("전부 오래됐으면 맨 끝 다음 번호", housekeep.cutoff_id("gym_battle", ago(-1)) == max(b) + 1)
    chk("전부 새것이면 맨 앞 번호", housekeep.cutoff_id("gym_battle", ago(30)) == min(a))
    for _ in range(20):
        gym(uid, 10, data="{}")
    n = housekeep.prune_table("gym_battle", ago(3), batch=3, pause=0)
    chk("덩어리 3줄씩이어도 다 지운다", n == 23 and ids("gym_battle") == set(b[1:]), (n, sorted(ids("gym_battle"))))

    print("\n=== 4. 처음 한 번: 지우고 VACUUM ===")
    for _ in range(1500):
        gym(uid, 10)                               # 27MB 쯤
    conn = db.connect()
    for name, _fn in migrations.ONCE:              # 다른 손질은 끝난 것으로 둔다
        if name != "0330-prune-battles":
            conn.execute("INSERT OR IGNORE INTO meta (k, v) VALUES (?, 'test')", ("mig:" + name,))
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = migrations._db_bytes()
    real_now = housekeep._now
    housekeep._now = lambda: NOW
    try:
        migrations.run()
    finally:
        housekeep._now = real_now
    after = migrations._db_bytes()
    chk("손질이 끝났다고 적힌다", db.q1("SELECT v FROM meta WHERE k='mig:0330-prune-battles'") is not None)
    chk("오래된 판이 다 지워졌다", ids("gym_battle") == set(b[1:]), len(ids("gym_battle")))
    chk("파일이 실제로 줄었다 (VACUUM)", after < before / 4, (before, after))
    for _ in range(50):
        gym(uid, 10)
    migrations.run()
    chk("두 번째 서버 시작에는 다시 돌지 않는다", len(ids("gym_battle")) == len(b[1:]) + 50)

    print("\n=== 배경 스레드 ===")
    housekeep.start()
    chk("POKET_HOUSEKEEP=0 이면 스레드를 안 띄운다",
        not any(t.name == "housekeep" for t in threading.enumerate()))

    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
