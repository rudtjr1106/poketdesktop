# -*- coding: utf-8 -*-
"""구경꾼 세기 (길드 친선전 · 길드전 공격). 싸우는 사람이 '관전 N명' 을 본다.

구경은 화면 쪽 일이라(바탕화면에서 도트로 튼다) 서버는 누가 보는지 모른다. 그래서 구경하는 화면이
보기 시작할 때·그만둘 때 알리고, 보는 동안에는 PING_SEC 마다 '아직 본다' 고 알린다 (ping).
TTL 동안 소식이 없으면 빠진 것으로 친다 - 창을 닫지 않고 앱을 끄거나 인터넷이 끊겨도 언젠가는 준다.

판의 이름(key)은 화면이 쓰는 판 번호 그대로를 글로 쓴다: 친선전은 실시간 배틀 번호 ("123"),
길드전 공격은 'w' + 관장 배틀 번호 ("w45").

**메모리에 둔다** (서버는 프로세스 하나다 - friendly · guild_ws 와 같은 전제). 서버가 다시 뜨면 0 에서
다시 센다 (구경하는 화면이 다음 알림에서 다시 들어온다).
"""
import threading
import time

TTL = 45.0                   # 이만큼 '아직 본다' 가 없으면 빠진 것으로 친다
PING_SEC = 20                # 구경하는 화면이 '아직 본다' 를 보내는 간격 (화면에 알려 준다)

_lock = threading.Lock()
_seen = {}                   # {판: {사람: 마지막으로 들은 때}}


def _now(now=None):
    return time.monotonic() if now is None else now     # (검사는 time 을 바꿔 끼운다 - friendly 와 같은 시계)


def _clean(key, now):
    got = _seen.get(key)
    if not got:
        return {}
    for uid in [u for u, t in got.items() if now - t > TTL]:
        del got[uid]
    if not got:
        _seen.pop(key, None)
    return got


def ping(key, uid, on=True, now=None):
    """그 사람이 그 판을 보기 시작했다 / 아직 본다 (on) · 그만 봤다. 바뀐 뒤의 구경꾼 수."""
    key, now = str(key), _now(now)
    with _lock:
        got = _clean(key, now)
        if on:
            _seen.setdefault(key, {})[uid] = now
        elif uid in got:
            del got[uid]
            if not got:
                _seen.pop(key, None)
        return len(_seen.get(key) or {})


def count(key, now=None):
    """지금 그 판을 보는 사람 수."""
    with _lock:
        return len(_clean(str(key), _now(now)))


def who(key, now=None):
    """지금 그 판을 보는 사람들 (챔피언리그는 판이 넘어갈 때마다 이 사람들에게 민다)."""
    with _lock:
        return list(_clean(str(key), _now(now)))


def drop(key):
    """판이 끝났다 - 센 것을 버린다."""
    with _lock:
        _seen.pop(str(key), None)


def reset():
    """다 비운다 (검사용)."""
    with _lock:
        _seen.clear()
