# -*- coding: utf-8 -*-
"""정식 도트를 서버에서 받아 이 PC 에 보관한다.

한 번 받은 그림은 %APPDATA%\\poketdesktop\\sprites 에 남아서 다음부터는
바로 쓴다. 받는 일은 반드시 작업 스레드에서 해야 한다(화면이 멈추지 않게).
"""
import os
import threading

from . import config

_lock = threading.Lock()
_missing = set()


def sprite_dir():
    d = os.path.join(config.data_dir(), "sprites")
    os.makedirs(d, exist_ok=True)
    return d


def _stem(num, shiny):
    return "%04d%s" % (int(num), "s" if shiny else "")


def find_local(num, shiny=False):
    d = sprite_dir()
    for ext in (".gif", ".png"):
        p = os.path.join(d, _stem(num, shiny) + ext)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return None


def ensure(api, num, shiny=False):
    """그림 파일 경로를 돌려준다. 없으면 서버에서 받아온다.

    반드시 작업 스레드에서 부를 것. 네트워크를 탄다.
    """
    if not num:
        return None
    p = find_local(num, shiny)
    if p:
        return p
    key = (int(num), bool(shiny))
    if key in _missing:
        return find_local(num, False) if shiny else None
    try:
        data, ext = api.sprite(num, shiny)
    except Exception:
        with _lock:
            _missing.add(key)
        return find_local(num, False) if shiny else None
    if not data:
        with _lock:
            _missing.add(key)
        return None
    path = os.path.join(sprite_dir(), _stem(num, shiny) + (ext or ".gif"))
    tmp = path + ".part"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except OSError:
        return None
    return path


def ensure_many(api, items):
    """[(번호, 이로치), ...] 를 한꺼번에 받아둔다."""
    out = {}
    for num, shiny in items:
        try:
            out[(num, bool(shiny))] = ensure(api, num, shiny)
        except Exception:
            out[(num, bool(shiny))] = None
    return out


def cached_count():
    try:
        return len([f for f in os.listdir(sprite_dir())
                    if f.endswith((".gif", ".png"))])
    except OSError:
        return 0
