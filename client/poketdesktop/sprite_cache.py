# -*- coding: utf-8 -*-
"""정식 도트를 서버에서 받아 이 PC 에 보관한다.

한 번 받은 그림은 %APPDATA%\\poketdesktop\\sprites 에 남아서 다음부터는
바로 쓴다. 받는 일은 반드시 작업 스레드에서 해야 한다(화면이 멈추지 않게).
"""
import os
import threading
import time

from common import sprite_fix as SF
from common import tint as T

from . import config

_lock = threading.Lock()

# 못 받은 것을 영영 포기하면 안 된다.
# 예전에는 그냥 set 이었는데, 잠깐 느리거나 끊겨서 한 번 실패하면 그
# 포켓몬은 프로그램을 끌 때까지 계속 안 보였다. "가끔 보면 이미지가 없는
# 애들이 많다" 는 게 이 때문이다.
# 그래서 '언제 실패했는지' 를 같이 적어 두고 조금 있다가 다시 해 본다.
_missing = {}
RETRY_AFTER = 30.0          # 초. 이만큼 지나면 다시 받아 본다.


def _give_up_for_now(key):
    with _lock:
        _missing[key] = time.time()


def _still_giving_up(key):
    with _lock:
        t = _missing.get(key)
        if t is None:
            return False
        if time.time() - t < RETRY_AFTER:
            return True
        del _missing[key]        # 시간이 지났으니 다시 해 본다
        return False


# 폴더를 이미 만든 곳. 도트를 찾을 때마다 os.makedirs 를 부르면 가방을
# 열 때만 1,400번이 불려 0.2초가 들었다. POKET_HOME 이 바뀌면 자리가
# 달라지므로 그 값을 열쇠로 둔다.
_made = {}


def sprite_dir():
    home = os.environ.get("POKET_HOME")
    d = _made.get(home)
    if d is None:
        d = os.path.join(config.data_dir(), "sprites")
        os.makedirs(d, exist_ok=True)
        _made[home] = d
    return d


def _stem(num, shiny):
    # 서버에서 도트를 바꾼 종(common/sprite_fix)은 이름에 판을 붙인다. 안 붙이면
    # 이미 받아 둔 옛 그림(납작한 스토마)을 계속 쓴다.
    r = SF.rev(num)
    return "%04d%s%s" % (int(num), "s" if shiny else "", ("-" + r) if r else "")


def _tinted_path(num, skin):
    """색조를 돌린 그림을 둘 자리 (이로치가 고른 색, common/tint)."""
    base, _hue = T.split(skin)
    return os.path.join(sprite_dir(), _stem(num, base) + T.suffix(skin) + ".png")


def find_local(num, shiny=False):
    """shiny 는 skin 이다: False(기본) / True(이로치) / "s090"(색조를 돌린 것)."""
    shiny = T.norm(shiny)
    d = sprite_dir()
    if isinstance(shiny, str):
        p = _tinted_path(num, shiny)
        return p if os.path.exists(p) and os.path.getsize(p) > 0 else None
    for ext in (".gif", ".png"):
        p = os.path.join(d, _stem(num, shiny) + ext)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return None


def _ensure_tinted(api, num, skin):
    """밑그림(이로치/기본)을 마련하고 색조를 돌린 파일을 만든다."""
    from . import sprite_tint
    p = find_local(num, skin)
    if p:
        return p
    base, hue = T.split(skin)
    src = ensure(api, num, base)
    if not src:
        # 이로치 도트가 없다. 기본 도트라도 준다 (색은 안 입힌다).
        return ensure(api, num, False) if base else None
    # 이로치 도트를 못 받아서 기본 도트가 대신 왔으면 색을 입히지 않는다.
    # 그걸 이로치 색조 파일로 굳히면 나중에 제대로 받아도 틀린 색이 남는다.
    if base and not os.path.basename(src).startswith(_stem(num, True)):
        return src
    dst = _tinted_path(num, skin)
    with _tint_lock:
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            return dst
        return dst if sprite_tint.make(src, dst, hue) else src


_tint_lock = threading.Lock()


def ensure(api, num, shiny=False):
    """그림 파일 경로를 돌려준다. 없으면 서버에서 받아온다.

    shiny 는 skin 이다 (common/tint): False / True / "s090" 같은 색조 값.
    반드시 작업 스레드에서 부를 것. 네트워크를 탄다.
    """
    if not num:
        return None
    shiny = T.norm(shiny)
    if isinstance(shiny, str):
        return _ensure_tinted(api, num, shiny)
    p = find_local(num, shiny)
    if p:
        return p
    key = (int(num), bool(shiny))
    if _still_giving_up(key):
        return find_local(num, False) if shiny else None
    try:
        data, ext = api.sprite(num, shiny)
    except Exception:
        _give_up_for_now(key)
        return find_local(num, False) if shiny else None
    if not data:
        _give_up_for_now(key)
        return None
    path = os.path.join(sprite_dir(), _stem(num, shiny) + (ext or ".gif"))
    tmp = path + ".part"
    try:
        # 쓰는 것은 드물다. 그사이 누가 폴더를 지웠어도 여기서 다시 만든다.
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except OSError:
        return None
    return path


def ensure_many(api, items):
    """[(번호, skin), ...] 를 한꺼번에 받아둔다. 열쇠는 (번호, T.norm(skin))."""
    out = {}
    for num, shiny in items:
        k = (num, T.norm(shiny))
        try:
            out[k] = ensure(api, num, shiny)
        except Exception:
            out[k] = None
    return out


def cached_count():
    try:
        return len([f for f in os.listdir(sprite_dir())
                    if f.endswith((".gif", ".png"))])
    except OSError:
        return 0
