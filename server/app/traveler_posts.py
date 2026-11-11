# -*- coding: utf-8 -*-
"""나그네 예약 글 — 정해 둔 때가 되면 게시판에 '나그네' 계정으로 글을 올린다 (2.4.0, 11/11 사용자).

아르케의 여섯 봉인(전설 스토리 이벤트)은 2.5.0 으로 따로 나간다 (arche 갈래). 2.4.0 서버에는 그 이벤트 전에
게시판에 올라가는 **나그네의 예약 글만** 먼저 넣는다. 하는 일은 아르케 ensure_posts 의 '예약 글' 부분과 같다.

## 글은 저장소에 없다

글 · 시각 · 계정 이름은 운영 볼륨의 비공개 자료(config.ARCHE_DIR/secrets.json - 아르케와 같은 파일)에만 있다:

    "traveler": "계정 이름",
    "npc": "계정 이름",                         (고고학자 - 여기서는 이름을 막는 데만 쓴다)
    "posts": [{"ref": "arche:...", "at": "2026-11-13T21:00:00+09:00", "by": "traveler",
               "title": "...", "body": "...", "images": ["그림.png"]}]

**by 가 traveler 인 것만** 올린다 (고고학자 글 - by npc - 은 이벤트와 같이 2.5.0 에서). 글은 ref 마다 한 번이다
(board_post.ref) - 2.5.0 에서 아르케가 같은 글을 다시 보아도 두 번 안 올라간다. 지운 글도 '있는 것' 으로 친다.
때가 지난 뒤 서버가 처음 올라오면 밀린 글이 그때 한꺼번에 올라간다 (글의 시각은 올린 때다).
파일이 없거나 깨졌으면 아무것도 안 한다.

## 계정

로그인할 수 없는 계정이다 (비밀번호 해시가 비어 있어 auth.verify_password 가 늘 틀린다). 없으면 만들고, 그 이름을
진짜 사람이 쓰고 있으면 올리지 않는다. 운영자가 아니다 (남의 글을 지우거나 공지를 쓸 수 없다).
비공개 자료에 적힌 게시판 계정 이름(traveler · npc)은 가입 · 닉네임 바꾸기에서 막는다 (reserved_name).

## 언제 보나

게시판 목록(GET /api/board)과 /api/me 에서 부른다 - 프로세스 안에서 EVERY 초에 한 번만 (파일은 mtime 으로만 다시 읽는다).
"""
import datetime
import io
import json
import os
import re
import threading
import time

from . import config, db

UTC = datetime.timezone.utc
ROLE = "traveler"
NAME_ROLES = ("traveler", "npc")    # 이름을 막는 게시판 계정 (npc = 고고학자, 2.5.0 이벤트)
EVERY = 30                          # 예약 글을 이만큼(초)에 한 번만 본다
_IMG_RE = re.compile(r"^[a-z0-9-]+\.png$")

_cache = {"key": None, "data": None}
_cache_lock = threading.Lock()
_seen_at = [0.0]
_post_lock = threading.Lock()


def reset():
    """검사용."""
    with _cache_lock:
        _cache["key"] = _cache["data"] = None
    _seen_at[0] = 0.0


def _now(now=None):
    return (now or datetime.datetime.now(UTC)).replace(microsecond=0)


def _iso(t):
    return t.astimezone(UTC).replace(microsecond=0).isoformat()


def _parse(s):
    """'2026-11-13T21:00:00+09:00'. 시간대가 없으면 UTC 로 읽는다 - 같은 파일을 읽는 아르케(arche._parse)와 똑같이
    (지금 자료는 전부 +09:00 이 붙어 있다)."""
    try:
        t = datetime.datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).astimezone(UTC)


def _path(*parts):
    return os.path.join(config.ARCHE_DIR, *parts)


def secrets():
    """비공개 자료 (dict) 또는 None. mtime · 크기가 바뀌면 다시 읽는다."""
    path = _path("secrets.json")
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (path, st.st_mtime_ns, st.st_size)
    with _cache_lock:
        if _cache["key"] == key:
            return _cache["data"]
        data = None
        try:
            with io.open(path, encoding="utf-8") as f:
                raw = json.load(f)
            data = raw if isinstance(raw, dict) else None
        except Exception as e:                                  # noqa: BLE001
            print("[traveler] secrets.json 을 읽지 못했습니다: %r" % e)
        _cache["key"], _cache["data"] = key, data
    return data


def _name(role):
    return str((secrets() or {}).get(role) or "").strip()


def reserved_name(name):
    """게시판 계정 이름(비공개 자료의 traveler · npc)과 같은 닉네임인가 (빈칸 무시). 가입 · 닉네임 바꾸기에서 막는다."""
    key = str(name or "").replace(" ", "")
    if not key:
        return False
    return any(key == _name(r).replace(" ", "") for r in NAME_ROLES if _name(r))


def account(now=None):
    """나그네 계정 (없으면 만든다). 이름이 없거나 진짜 사람이 그 이름을 쓰고 있으면 None."""
    name = _name(ROLE)
    if not name:
        return None
    r = db.q1("SELECT id, username, pw_hash FROM users WHERE username=?", (name,))
    if r is None:
        db.run("INSERT OR IGNORE INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at)"
               " VALUES (?,?,?,1,0,0,?)", (name, b"", b"", _iso(_now(now))))
        r = db.q1("SELECT id, username, pw_hash FROM users WHERE username=?", (name,))
    if r is None or len(r["pw_hash"] or b""):
        print("[traveler] 이름 '%s' 을(를) 진짜 사람이 쓰고 있어 예약 글을 올리지 않습니다" % name)
        return None
    return r


def _attach_images(user, pid, names, now):
    from . import board
    for pos, name in enumerate(names or []):
        name = str(name)
        if not _IMG_RE.match(name):
            continue
        try:
            with open(_path("img", name), "rb") as f:
                data, fmt, w, h, frames = board.encode_image(f.read())
            cur = db.run("INSERT INTO board_image (user_id, post_id, pos, fmt, w, h, bytes, frames, created_at)"
                         " VALUES (?,?,?,?,?,?,?,?,?)", (user["id"], pid, pos, fmt, w, h, len(data), frames, _iso(now)))
            path = board._img_path({"id": cur.lastrowid, "fmt": fmt})
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
        except Exception as e:                                   # noqa: BLE001
            print("[traveler] 게시글 사진 실패 %s: %r" % (name, e))


def _post(user, ref, title, body, images, now):
    """글 하나 (ref 가 이미 있으면 아무것도 안 한다). 올렸으면 True."""
    cur = db.run("INSERT INTO board_post (kind, user_id, author, title, body, created_at, ref)"
                 " SELECT 'free', ?, ?, ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM board_post WHERE ref=?)",
                 (user["id"], user["username"], str(title)[:80], str(body), _iso(now), ref, ref))
    if not getattr(cur, "rowcount", 1):
        return False
    if images:
        _attach_images(user, cur.lastrowid, images, now)
    return True


def due(now=None):
    """지금 올릴 때가 된 나그네 글 [{ref, title, body, images}] (이미 올린 것도 든다 - _post 가 거른다)."""
    now = _now(now)
    out = []
    for p in (secrets() or {}).get("posts") or []:
        if not isinstance(p, dict) or str(p.get("by") or "") != ROLE:
            continue
        ref = str(p.get("ref") or "")
        if not ref.startswith("arche:") or not str(p.get("body") or "").strip():
            continue
        at = _parse(p.get("at"))
        if at is None or now < at:
            continue
        out.append(p)
    return out


def ensure(now=None, force=False):
    """때가 된 나그네 글을 올린다. 올린 글 수. 프로세스 안에서 EVERY 초에 한 번만 (force 면 바로)."""
    if not force and time.monotonic() - _seen_at[0] < EVERY:
        return 0
    if not _post_lock.acquire(blocking=False):
        return 0
    try:
        _seen_at[0] = time.monotonic()
        now = _now(now)
        posts = due(now)
        if not posts:
            return 0
        user = account(now)
        if user is None:
            return 0
        n = 0
        for p in posts:
            try:
                n += bool(_post(user, str(p["ref"]), str(p.get("title") or "")[:80] or "나그네",
                                str(p.get("body") or ""), p.get("images"), now))
            except Exception as e:                               # noqa: BLE001
                print("[traveler] 예약 글 실패 %s: %r" % (p.get("ref"), e))
        return n
    except Exception as e:                                       # noqa: BLE001
        print("[traveler] 예약 글 확인 실패: %r" % e)
        return 0
    finally:
        _post_lock.release()
