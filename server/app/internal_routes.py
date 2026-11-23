# -*- coding: utf-8 -*-
"""관리자 통로 — **서버 안(127.0.0.1)에서만** 부른다 (2.0.x).

    POST /internal/guild/say    {"guild": 3, "text": "..."}   길드 채팅에 알림 줄(보낸 사람 없음) 하나
    GET  /internal/ping                                        통로가 열려 있나 (관리자 도구가 처음에 본다)
    GET  /internal/profile?secs=20&hz=100                      서버가 CPU 를 어디에 쓰나 - 스레드마다 지금 도는 줄을
                                                               secs 초 동안 hz 번씩 떠서 센다 (11/23 부하 줄이기)

머리말 X-Internal-Key 에 열쇠(KEY_FILE 의 내용)를 넣는다. 관리자 도구(tools/admin_guildchat.py)는 SSH 로 서버
컨테이너에 들어가 이 주소를 부른다 - 다른 관리자 도구처럼 서버 밖에 문을 새로 내지 않는다.

**왜 SSH 로 DB 에 바로 넣지 않나.** 길드 채팅을 화면에 바로 띄우는 웹소켓은 서버 프로세스 안에서만 민다
(guild_ws - 붙어 있는 연결을 이 프로세스의 사전에 들고 있다). 밖에서 guild_chat 에 줄을 넣으면 저장은 되지만
채팅을 보고 있는 사람에게는 안 뜬다. 웹소켓이 붙어 있는 화면은 묻지 않고 밀려오는 것만 받기 때문이다.

막는 것 셋. 하나라도 틀리면 **전부 404** - 이런 주소가 있다는 것도 알려 주지 않는다.
  1. 127.0.0.1 / ::1 에서 온 요청만. 밖의 요청은 전부 Caddy(다른 컨테이너)를 거쳐 와서 여기에 닿지 않는다.
  2. 서버가 뜰 때마다 새로 만드는 열쇠 (KEY_FILE, 0600, make_key). 서버 안에서만 읽을 수 있다.
  3. Caddy 도 /internal/* 를 밖으로 내주지 않는다 (deploy/Caddyfile).
"""
import collections
import hmac
import os
import secrets
import sys
import tempfile
import threading
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from . import config, db, guild

router = APIRouter()

KEY_FILE = os.environ.get("POKET_INTERNAL_KEY_FILE") or os.path.join(tempfile.gettempdir(), "poket-internal.key")
LOCAL = ("127.0.0.1", "::1")


_KEY = None


def make_key():
    """새 열쇠를 만들어 KEY_FILE 에 적는다 (주인만 읽는다). **서버가 뜰 때 한 번** (main._startup).

    불러올 때(import) 만들면 안 된다 - 검사·도구가 app.main 을 불러올 때마다 파일이 새 열쇠로 바뀌어,
    떠 있는 서버가 들고 있는 열쇠와 어긋난다. 못 적으면 통로가 닫힌 채로 둔다.
    """
    global _KEY
    key = secrets.token_hex(24)
    try:
        if os.path.exists(KEY_FILE):
            os.remove(KEY_FILE)
        fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(key)
    except OSError as e:
        print("[internal] 열쇠를 적지 못해 관리자 통로를 닫아 둡니다: %r" % (e,))
        return
    _KEY = key


def _gate(request):
    host = (request.client.host if request.client else "") or ""
    got = request.headers.get("x-internal-key") or ""
    if not _KEY or host not in LOCAL or not hmac.compare_digest(got, _KEY):
        raise HTTPException(404, "Not Found")


class SayIn(BaseModel):
    guild: int
    text: str


@router.get("/internal/ping")
def ping(request: Request):
    _gate(request)
    return {"ok": True}


@router.post("/internal/guild/say")
def say(body: SayIn, request: Request):
    """알림 줄로 보낸다 (guild._say - 길드원이 들어왔다 같은 줄과 같은 모습). 웹소켓으로 바로 밀린다."""
    _gate(request)
    text = " ".join((body.text or "").split())
    if not text:
        raise HTTPException(400, "보낼 말을 적어 주세요.")
    if len(text) > config.GUILD_CHAT_LEN:
        raise HTTPException(400, "한 번에 %d자까지 보낼 수 있습니다." % config.GUILD_CHAT_LEN)
    if not db.q1("SELECT id FROM guild WHERE id=?", (body.guild,)):
        raise HTTPException(404, "그런 길드가 없습니다.")
    return {"ok": True, "id": guild._say(body.guild, text)}


# ---------------------------------------------------------------- CPU 표본 (11/23 부하 줄이기)
# 크레딧이 바닥나 CPU 가 묶였을 때 무엇이 CPU 를 쓰는지 보려고. 운영 서버에서 py-spy 같은 것은 못 붙인다 (ptrace 막힘).
# 다른 스레드의 지금 줄(sys._current_frames)을 떠서, **그 사이 그 스레드가 실제로 쓴 CPU**(/proc/self/task/<id>/stat 의
# utime+stime, 1/100초 단위)만큼 센다 - 자거나 소켓 · DB 를 기다리는 스레드는 CPU 를 안 써서 저절로 빠진다.
# /proc 가 없는 곳(맥)에서는 한 번 뜰 때마다 1 로 센다.
_PROF_LOCK = threading.Lock()


def _where(f):
    co = f.f_code
    path = co.co_filename
    short = path.split("/app/", 1)[-1] if "/app/" in path else path.rsplit("/", 1)[-1]
    return "%s:%s" % (short, co.co_name)


def _cpu_ticks(native_id):
    try:
        with open("/proc/self/task/%d/stat" % native_id) as f:
            parts = f.read().rsplit(")", 1)[1].split()
        return int(parts[11]) + int(parts[12])
    except (OSError, ValueError, IndexError):
        return None


@router.get("/internal/profile")
def profile(request: Request, secs: float = 20.0, hz: float = 100.0, top: int = 40):
    _gate(request)
    secs = max(1.0, min(60.0, float(secs)))
    hz = max(10.0, min(500.0, float(hz)))
    if not _PROF_LOCK.acquire(blocking=False):
        raise HTTPException(409, "이미 재는 중입니다.")
    try:
        me = threading.get_ident()
        leaf = collections.Counter()      # 맨 끝 줄 (실제로 도는 곳)
        incl = collections.Counter()      # 줄 위 어딘가에 있는 함수 (그 함수 아래에서 쓴 몫)
        app = collections.Counter()       # 앱 코드(app/ · common/) 중 맨 끝 함수
        sql = collections.Counter()       # DB 질의가 맨 끝일 때 그 SQL
        sql_by = collections.Counter()    # 그 질의를 부른 앱 함수
        last = {}
        total = 0
        end = time.time() + secs
        gap = 1.0 / hz
        while time.time() < end:
            native = dict((t.ident, t.native_id) for t in threading.enumerate())
            for tid, f in sys._current_frames().items():
                if tid == me:
                    continue
                nid = native.get(tid)
                ticks = _cpu_ticks(nid) if nid else None
                if ticks is None:
                    w = 1
                else:
                    w = ticks - last.get(tid, ticks)
                    last[tid] = ticks
                if w <= 0:
                    continue
                head = f
                stack = []
                while f is not None:
                    stack.append(_where(f))
                    f = f.f_back
                if not stack:
                    continue
                total += w
                leaf[stack[0]] += w
                if stack[0] == "app/db.py:go":
                    # DB 질의가 맨 끝이면 그 SQL (go 는 q · q1 · run 의 안쪽 함수 - sql 을 품고 있다)과 부른 앱 함수
                    text = " ".join(str(head.f_locals.get("sql") or "?").split())[:150]
                    sql[text] += w
                    who = next((x for x in stack if x.startswith("app/") and not x.startswith("app/db.py")), "?")
                    sql_by[who] += w
                for x in set(stack):
                    incl[x] += w
                for x in stack:
                    if x.startswith(("app/", "common/")):
                        app[x] += w
                        break
            time.sleep(gap)

        def rows(c):
            return [{"where": k, "cpu": n, "pct": round(100.0 * n / max(1, total), 1)} for k, n in c.most_common(top)]
        return {"secs": secs, "cpuTicks": total, "leaf": rows(leaf), "app": rows(app), "inclusive": rows(incl),
                "sql": rows(sql), "sqlBy": rows(sql_by)}
    finally:
        _PROF_LOCK.release()
