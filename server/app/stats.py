# -*- coding: utf-8 -*-
"""밖에 보여 주는 숫자 셋 (2026-11-17, 포트폴리오 사이트가 읽는다).

    GET /api/stats   ->   {"users": 1234, "online": 87, "peakOnline": 312}

**인증 없이 누구나 보는 자리다.** 그래서:

  - 합계만 나간다. 닉네임 · 누가 접속 중인지 · 버전 · IP 같은 것은 없다 (/api/health 보다도 적다).
  - 물을 때마다 DB 를 읽지 않는다. 배경 스레드가 SAMPLE_SEC 초마다 한 번 세어 메모리에 두고, 경로는 그것을 읽기만
    한다 - 밖에서 아무리 두드려도 DB 가 하는 일은 1분에 조회 셋이다.

'접속 중' 은 친구 목록과 같은 기준이다 (social.ONLINE_WINDOW - 3분 안에 서버에 말을 건 사람). 앱은 켜져 있는 동안
90초마다 서버를 두드리므로 '앱을 켜 둔 사람 수' 에 가깝다. 한 사람이 PC 두 대를 켜도 한 명이다.

**최대 동시 접속은 그동안 어디에도 안 남았다.** 세션에는 마지막으로 말을 건 시각만 있어서 지난 날의 수는 되살릴 수
없다. 그래서 여기서부터 센다 - 셀 때마다 기록(meta 의 stats:peak_online)과 견주어 넘으면 적는다. 1분에 한 번 보는
것이라 그 사이에 잠깐 솟았다 꺼진 것은 놓치지만, 접속 판정의 여유가 3분이라 실제로는 거의 안 놓친다. 기록은 내려가지
않는다. 이 판이 나가기 전의 기록을 넣고 싶으면 그 칸에 숫자를 넣으면 된다 (더 큰 값은 덮지 않는다).

**세다가 터지면 안 된다.** 스레드는 실패를 삼키고 다음 차례에 다시 세고, 경로는 마지막으로 센 것을 준다 (한 번도 못
셌으면 503 - 500 이 아니라서 server_error 에 안 남고 keepalive 도 안 운다).
"""
import datetime
import threading
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from . import config, db, social

router = APIRouter()

SAMPLE_SEC = 60                         # 스레드가 이만큼마다 한 번 센다
STALE_SEC = SAMPLE_SEC * 2 + 30         # 센 것이 이보다 묵었으면 (스레드가 꺼졌거나 멈췄다) 경로가 그 자리에서 센다
PEAK_KEY = "stats:peak_online"          # meta: 최대 동시 접속
PEAK_AT_KEY = "stats:peak_online_at"    # meta: 그 기록을 세운 시각 (UTC)

_lock = threading.Lock()                # 세는 것은 한 번에 하나만
_snap = None                            # 마지막으로 센 것 {"users", "online", "peakOnline"}
_snap_at = None                         # 마지막으로 세어 본 때 (time.monotonic, 실패한 때도 든다)
_started = False


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _count(now=None):
    """(가입자 수, 지금 접속 중). 조회 둘."""
    cut = ((now or _now()) - datetime.timedelta(seconds=social.ONLINE_WINDOW)).isoformat()
    users = db.q1("SELECT COUNT(*) AS n FROM users")
    online = db.q1("SELECT COUNT(DISTINCT user_id) AS n FROM sessions WHERE last_seen >= ?", (cut,))
    return int(users["n"] or 0), int(online["n"] or 0)


def _peak():
    """적혀 있는 기록. 없거나 숫자가 아니면 0 (다음에 센 값이 기록이 된다)."""
    r = db.q1("SELECT v FROM meta WHERE k=?", (PEAK_KEY,))
    try:
        return max(0, int(r["v"])) if r is not None else 0
    except (TypeError, ValueError):
        return 0


def _raise_peak(n, now):
    """기록을 n 으로 올린다. 읽은 뒤에 더 큰 값이 들어와 있으면 그대로 둔다 (문장 하나로 견주고 쓴다)."""
    db.run("INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v"
           " WHERE CAST(meta.v AS INTEGER) < CAST(excluded.v AS INTEGER)", (PEAK_KEY, str(n)))
    db.run("INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
           (PEAK_AT_KEY, now.replace(microsecond=0).isoformat()))


def sample(now=None):
    """지금 세고, 기록을 넘었으면 적는다. 센 것을 메모리에 두고 돌려준다."""
    global _snap, _snap_at
    now = now or _now()
    users, online = _count(now)
    peak = _peak()
    if online > peak:
        peak = online
        try:
            _raise_peak(online, now)
        except Exception as e:                              # noqa: BLE001
            # 적지 못해도 센 것은 내보낸다 (DB 가 잠겨 쓰기만 안 되는 때). 다음 차례에도 넘어 있으면 그때 적힌다.
            print("[stats] 기록을 적지 못했습니다: %r" % (e,))
    _snap = {"users": users, "online": online, "peakOnline": peak}
    _snap_at = time.monotonic()
    return _snap


def _fresh():
    return _snap_at is not None and time.monotonic() - _snap_at < STALE_SEC


def snapshot():
    """마지막으로 센 것. 너무 묵었으면 그 자리에서 한 번 센다.

    세다가 터지면 묵은 것을 그대로 준다 (한 번도 못 셌으면 None). 터진 때도 '세어 본 때' 로 치므로, DB 가 아픈 동안
    요청마다 다시 세러 가지 않는다.
    """
    global _snap_at
    if _fresh():
        return _snap
    with _lock:
        if _fresh():                    # 기다리는 사이에 다른 쪽이 셌다
            return _snap
        try:
            return sample()
        except Exception as e:                              # noqa: BLE001
            print("[stats] 세지 못했습니다: %r" % (e,))
            _snap_at = time.monotonic()
            return _snap


def forget():
    """메모리에 둔 것을 비운다 (검사용 - 서버를 다시 켠 것과 같다. 기록은 DB 에 있어서 그대로다)."""
    global _snap, _snap_at
    with _lock:
        _snap, _snap_at = None, None


@router.get("/api/stats")
def public_stats():
    """가입자 수 · 지금 접속 중 · 최대 동시 접속. 인증 없이 누구나 본다 - 숫자 셋 말고는 넣지 않는다."""
    snap = snapshot()
    if snap is None:
        raise HTTPException(503, "잠시 후 다시 시도해 주세요.")
    return JSONResponse(snap, headers={"Cache-Control": "public, max-age=%d" % SAMPLE_SEC})


def _loop():
    while True:
        try:
            with _lock:
                sample()
        except Exception as e:                              # noqa: BLE001
            print("[stats] 세지 못했습니다: %r" % (e,))
        time.sleep(SAMPLE_SEC)


def start():
    """서버가 뜰 때 한 번 부른다. SAMPLE_SEC 초마다 세는 배경 스레드 (자기 DB 커넥션을 쓴다)."""
    global _started
    if _started or not config.STATS_SAMPLE:
        return
    _started = True
    threading.Thread(target=_loop, name="stats", daemon=True).start()
