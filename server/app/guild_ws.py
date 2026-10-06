# -*- coding: utf-8 -*-
"""길드 채팅을 밀어 주는 웹소켓 (1.10.0).

    WS /ws/guild        머리말 Authorization: Bearer <토큰>

**서버 → 화면으로만 민다.** 말을 보내는 것은 지금처럼 POST /api/guild/chat 이다 -
글자 수·도배 막기 같은 검사를 한 군데(guild.chat_send)에만 두려는 것이다.

    {"t": "hello", "userId": 3, "guild": 1, "last": 120}   붙었다 (last = 지금까지의 마지막 줄 번호)
    {"t": "chat", "m": {...}}                              새 줄
    {"t": "changed"}                                       길드에 바뀐 것이 있다
    {"t": "left"}                                          이 길드에서 나왔다 (그리고 끊는다)

화면이 "ping" 을 보내면 "pong" 을 돌려준다.

## 끊는 번호

    4401    토큰이 틀렸다 - 다시 붙어 봐야 소용없다
    4404    길드에 들어 있지 않다
    4429    한 사람이 너무 많이 붙었다

## 어떻게 미나

서버는 **프로세스 하나**로 돈다 (server/Dockerfile 의 uvicorn 한 줄). 그래서 붙어 있는
연결을 이 모듈의 사전에 들고 있다가 바로 보내면 된다. 워커를 여럿으로 늘리면 다른
워커에 붙은 사람에게는 안 간다 - 그때는 사이에 중계(예: Redis)를 둬야 한다.

길드에 일이 생기는 곳(guild.py)은 **스레드풀의 보통 함수**다. 웹소켓은 이벤트 루프에서
돌므로, guild.listeners 로 불린 쪽에서 run_coroutine_threadsafe 로 루프에 넘긴다.
"""
import asyncio
import json
import threading

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from . import auth, db, guild

router = APIRouter()

MAX_PER_USER = 3            # 한 사람이 동시에 붙을 수 있는 수 (PC 두 대 + 여유)
MAX_TOTAL = 600

_lock = threading.Lock()
_conns = {}                 # {길드 번호: set(Conn)}
_loop = None                # 웹소켓이 도는 이벤트 루프 (처음 붙을 때 잡아 둔다)


class Conn(object):
    __slots__ = ("ws", "uid", "gid")

    def __init__(self, ws, uid, gid):
        self.ws, self.uid, self.gid = ws, uid, gid


def count(gid=None):
    """붙어 있는 연결 수 (검사·점검용)."""
    with _lock:
        if gid is not None:
            return len(_conns.get(gid, ()))
        return sum(len(s) for s in _conns.values())


def _add(c):
    with _lock:
        mine = sum(1 for s in _conns.values() for x in s if x.uid == c.uid)
        total = sum(len(s) for s in _conns.values())
        if mine >= MAX_PER_USER or total >= MAX_TOTAL:
            return False
        _conns.setdefault(c.gid, set()).add(c)
        return True


def _drop(c):
    with _lock:
        s = _conns.get(c.gid)
        if s is not None:
            s.discard(c)
            if not s:
                _conns.pop(c.gid, None)


async def _send(c, text, close=False):
    try:
        await c.ws.send_text(text)
        if close:
            _drop(c)
            await c.ws.close(code=1000)
    except Exception:                                       # noqa: BLE001
        _drop(c)                                            # 이미 끊긴 연결이다


def publish(kind, target, payload):
    """guild.py 가 부른다 (스레드풀에서). 붙어 있는 사람에게 보낸다."""
    loop = _loop
    if loop is None or loop.is_closed():
        return
    with _lock:
        if kind == "guild":
            targets = list(_conns.get(target, ()))
        else:
            targets = [c for s in _conns.values() for c in s if c.uid == target]
    if not targets:
        return
    text = json.dumps(payload, ensure_ascii=False)
    gone = payload.get("t") == "left"
    for c in targets:
        try:
            asyncio.run_coroutine_threadsafe(_send(c, text, close=gone), loop)
        except RuntimeError:
            pass                                            # 루프가 내려가는 중이다


if publish not in guild.listeners:
    guild.listeners.append(publish)


def _who(token):
    """(사람 번호, 길드 번호, 마지막 줄 번호). 스레드풀에서 부른다 (DB 를 읽는다)."""
    sess, user = auth.lookup_session_with_user(token)
    if not sess:
        return None, None, 0
    m = guild.member(user["id"])
    if not m:
        return user["id"], None, 0
    last = db.q1("SELECT MAX(id) x FROM guild_chat WHERE guild_id=?", (m["guild_id"],))
    return user["id"], m["guild_id"], (last["x"] or 0) if last else 0


@router.websocket("/ws/guild")
async def guild_socket(ws: WebSocket):
    global _loop
    _loop = asyncio.get_running_loop()
    head = ws.headers.get("authorization") or ""
    await ws.accept()               # 받아 준 뒤에 끊어야 끊는 번호가 화면까지 간다
    if not head.lower().startswith("bearer "):
        return await ws.close(code=4401)
    uid, gid, last = await run_in_threadpool(_who, head[7:].strip())
    if uid is None:
        return await ws.close(code=4401)
    if gid is None:
        return await ws.close(code=4404)
    c = Conn(ws, uid, gid)
    if not _add(c):
        return await ws.close(code=4429)
    try:
        await ws.send_text(json.dumps({"t": "hello", "userId": uid, "guild": gid, "last": last}))
        while True:
            if await ws.receive_text() == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:                                       # noqa: BLE001
        pass
    finally:
        _drop(c)
