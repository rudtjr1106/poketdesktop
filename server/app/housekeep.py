# -*- coding: utf-8 -*-
"""끝난 배틀을 치운다 (2026-10-28, 운영 디스크 조사).

관장 배틀(gym_battle - 관장 · 악당 · 길드전이 같은 표)은 판이 끝나도 상태 전체를 data 칸에
들고 있다. 한 판에 ~18KB, 하루 7천 판이라 하루 130MB 씩 쌓였고 지우는 곳이 하나도 없었다.
10/28 에 DB 3.1GB 중 2.3GB 가 이 표였다. 야생 배틀(battle)도 지우는 곳이 없었다(한 판 ~2KB).

끝난 판을 다시 읽는 곳은 둘뿐이다:
  - 끝난 직후 같은 판에 한 번 더 묻는 것 (gym_routes.act · battle_routes) - 몇 분 안이다.
  - 결과가 아직 안 적힌 길드전 공격 (guild_war.expire 가 battle_id 로 이어서 본다).
그래서 **끝난 지 BATTLE_KEEP_DAYS 일이 지난 판**을 지우고, 길드전 공격이 기다리는 판은 남긴다.
진행 중(active)인 판은 건드리지 않는다 - 그건 각자 TTL 로 접힌다.

표 전체를 created_at 으로 훑지 않는다. 그 칸은 큰 data 칸 **뒤에** 있어서 줄마다 넘침 페이지를
따라가야 읽힌다 - 12만 줄을 훑으면 2GB 를 읽는다. id 는 넣은 순서이고 created_at 도 넣을 때의
시각이라, id 를 반으로 갈라 가며 몇 줄만 보고 경계 번호를 찾고 그 **아래만** 본다. 지울 때
created_at 도 한 번 더 본다 - 순서가 어긋난 줄이 있어도 최근 판은 안 지워지게(경계는 빨리 찾는 길일 뿐).

한 번에 많이 지우면 쓰기 잠금을 오래 쥐어서 다른 요청이 'database is locked' 로 실패한다
(10/21 장애). 그래서 BATCH 줄씩 나눠 지우고 사이에 쉰다. 처음 한 번의 큰 정리는 서버가 요청을
받기 전에 migrations(0330) 가 한다.
"""
import datetime
import threading
import time

from . import config, db

TABLES = ("gym_battle", "battle")
BATCH = 300
PAUSE = 0.05            # 덩어리 사이 (초)
PERIOD = 3600           # 한 시간마다
START_DELAY = 120       # 서버가 뜨고 이만큼 뒤에 처음

# 결과가 안 적힌 길드전 공격이 기다리는 판. battle_id 가 NULL 인 줄이 있으므로 꼭 거른다 -
# NOT IN 목록에 NULL 이 하나라도 섞이면 비교가 전부 NULL 이 되어 아무것도 안 지워진다.
_WAITING = ("SELECT battle_id FROM guild_war_attack"
            " WHERE result='pending' AND battle_id IS NOT NULL")

_started = False
_lock = threading.Lock()


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def cutoff_id(table, cut):
    """이 번호보다 작은 줄은 모두 cut 보다 먼저 만들어졌다. (줄이 없으면 1)

    '첫 줄의 created_at >= cut' 은 번호가 커질수록 거짓 -> 참으로 한 번만 바뀐다.
    그 바뀌는 번호를 반으로 갈라 찾는다. 번호 사이가 비어 있어도(지운 줄) 된다.
    """
    r = db.q1("SELECT min(id) AS lo, max(id) AS hi FROM %s" % table)
    if r is None or r["hi"] is None:
        return 1
    lo, hi = int(r["lo"]), int(r["hi"]) + 1        # hi 너머에는 줄이 없다 = 참
    while lo < hi:
        mid = (lo + hi) // 2
        row = db.q1("SELECT created_at FROM %s WHERE id >= ? ORDER BY id LIMIT 1" % table, (mid,))
        if row is None or row["created_at"] >= cut:
            hi = mid
        else:
            lo = mid + 1
    return lo


def prune_table(table, cut, batch=BATCH, pause=PAUSE):
    """끝난 판 가운데 cut 보다 먼저 시작한 것을 지운다. 지운 줄 수."""
    below = cutoff_id(table, cut)
    waiting = _WAITING if table == "gym_battle" else "SELECT NULL WHERE 0"
    total = 0
    while True:
        cur = db.run("DELETE FROM %s WHERE id IN (SELECT id FROM %s WHERE id < ? AND state='done'"
                     " AND created_at < ? AND id NOT IN (%s) ORDER BY id LIMIT ?)" % (table, table, waiting),
                     (below, cut, batch))
        n = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
        total += n
        if n < batch:
            return total
        if pause:
            time.sleep(pause)


def prune_battles(now=None, keep_days=None, batch=BATCH, pause=PAUSE):
    """두 표를 다 치운다. {표: 지운 줄 수}. 동시에 두 번 돌지 않는다."""
    keep = config.BATTLE_KEEP_DAYS if keep_days is None else keep_days
    cut = ((now or _now()) - datetime.timedelta(days=keep)).replace(microsecond=0).isoformat()
    with _lock:
        return dict((t, prune_table(t, cut, batch, pause)) for t in TABLES)


def _loop():
    time.sleep(START_DELAY)
    while True:
        try:
            done = prune_battles()
            if any(done.values()):
                print("[housekeep] 끝난 배틀 정리: %s" % ", ".join("%s %d" % kv for kv in done.items()))
        except Exception as e:                              # noqa: BLE001
            print("[housekeep] 정리 실패: %r" % (e,))
        time.sleep(PERIOD)


def start():
    """서버가 뜰 때 한 번 부른다. 한 시간마다 도는 배경 스레드 (자기 DB 커넥션을 쓴다)."""
    global _started
    if _started or not config.HOUSEKEEP:
        return
    _started = True
    threading.Thread(target=_loop, name="housekeep", daemon=True).start()
