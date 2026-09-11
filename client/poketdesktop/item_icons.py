# -*- coding: utf-8 -*-
"""도구 그림을 받아서 이 PC 에 보관하고, tk 이미지로 만들어 준다.

포켓몬 도트와 다르게 도구 그림은 개당 1~2KB 라서 서버가 전부 들고 있다.
그래서 실패할 일이 거의 없지만, 그래도 한 번 못 받았다고 영영 포기하지는
않는다(도트 쪽에서 그 문제로 그림이 안 뜬 적이 있다).

tk 이미지는 **반드시 tk 스레드에서** 만들어야 한다. 그래서 받아오는 일과
만드는 일을 나눠 뒀다.

    raw(api, item_id)             작업 스레드에서 — 파일 경로를 돌려준다
    prefetch(api, ids, sizes)     작업 스레드에서 — 받고 **풀어서 맞춰 둔다**
    photo(item_id, size)          tk 스레드에서 — PhotoImage 를 돌려준다

PNG 를 풀고 칸에 맞춰 늘리는 일은 작업 스레드(prefetch)에서 끝내 둔다.
tk 스레드에서 줄마다 하면 한 장에 몇 ms 씩, 상점 목록 한 번에 0.3초가
들었다. photo() 는 풀어 둔 것이 있으면 감싸기만 한다.
"""
import os
import threading
import time

from . import config

_lock = threading.Lock()
_failed = {}
_photos = {}
_rgba = {}          # {도구: 풀어 둔 RGBA 원본}        — 작업 스레드가 채운다
_fitted = {}        # {(도구, 크기): 칸에 맞춘 RGBA}   — 작업 스레드가 채운다
_no_file = {}       # {도구: 파일이 없다고 본 시각}
_made = {}          # {POKET_HOME: 만들어 둔 폴더}
RETRY_AFTER = 30.0


def icon_dir():
    # 폴더는 한 번만 만든다. 그림을 찾을 때마다 os.makedirs 를 부르면
    # 목록 한 번에 수백 번이 불린다. POKET_HOME 이 바뀌면 자리가 달라지므로
    # 그 값을 열쇠로 둔다.
    home = os.environ.get("POKET_HOME")
    d = _made.get(home)
    if d is None:
        d = os.path.join(config.data_dir(), "items")
        os.makedirs(d, exist_ok=True)
        _made[home] = d
    return d


def local_path(item_id):
    p = os.path.join(icon_dir(), "%s.png" % item_id)
    return p if os.path.exists(p) and os.path.getsize(p) > 0 else None


def _found(item_id):
    """이제 파일이 있다. '없다' 고 적어 둔 것을 지운다."""
    with _lock:
        _no_file.pop(item_id, None)


def raw(api, item_id):
    """그림 파일 경로. 없으면 서버에서 받아온다. **작업 스레드에서 부를 것.**"""
    if not item_id:
        return None
    p = local_path(item_id)
    if p:
        _found(item_id)
        return p
    with _lock:
        t = _failed.get(item_id)
        if t is not None:
            if time.time() - t < RETRY_AFTER:
                return None
            del _failed[item_id]
    data = None
    try:
        data = api.item_sprite(item_id)
    except Exception:
        data = None
    if not data:
        with _lock:
            _failed[item_id] = time.time()
        return None
    path = os.path.join(icon_dir(), "%s.png" % item_id)
    tmp = path + ".part"
    try:
        # 쓰는 것은 드물다. 그사이 누가 폴더를 지웠어도 여기서 다시 만든다.
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except OSError:
        return None
    # **선물 창이 이것에 기댄다.** 그림이 없어 photo() 가 '없다' 고 적어
    # 둔 뒤에 받아 오면, 여기서 지우지 않는 한 30초 동안 계속 없다고 한다.
    _found(item_id)
    return path


def pil(item_id):
    """받아 둔 그림을 PIL(RGBA) 로. 없으면 None.

    photo() 는 tk 이미지라 tk 스레드에서만 쓸 수 있고, 돌리거나 색을
    섞을 수도 없다. 몬스터볼을 던지는 연출은 그림을 기울여 가며 써야
    해서(effects.ball_frames) PIL 그대로가 필요하다.

    **네트워크를 타지 않는다.** 이미 받아 둔 것만 준다 - 던지는 순간에
    서버를 기다리면 그 사이 화면이 얼어붙는다. 아직 없으면 None 을
    돌려주고, 부르는 쪽이 직접 그린 볼로 넘어간다.
    """
    p = local_path(item_id)
    if not p:
        return None
    try:
        from PIL import Image
        return Image.open(p).convert("RGBA")
    except Exception:                                       # noqa: BLE001
        return None


def _fit(img, size):
    """size x size 칸 가운데에 맞춘다.

    도트 그림이라 부드럽게 늘리면 뭉개진다. 가까운 점을 그대로.
    원본은 건드리지 않고 새 그림을 돌려준다(같은 크기면 그대로).
    """
    if img.width == size and img.height == size:
        return img
    from PIL import Image
    scale = min(size / float(img.width), size / float(img.height))
    w = max(1, int(round(img.width * scale)))
    h = max(1, int(round(img.height * scale)))
    small = img.resize((w, h), Image.NEAREST)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(small, ((size - w) // 2, (size - h) // 2))
    return canvas


def _decode(item_id):
    """파일을 풀어 RGBA 원본으로. 풀어 둔 것이 있으면 그것을 쓴다."""
    img = _rgba.get(item_id)
    if img is not None:
        return img
    p = local_path(item_id)
    if not p:
        return None
    from PIL import Image
    img = Image.open(p).convert("RGBA")
    _rgba[item_id] = img
    return img


def photo(item_id, size=28):
    """tk 에 붙일 이미지. 없으면 None. **tk 스레드에서 부를 것.**

    같은 그림을 여러 줄이 함께 쓰므로 만들어 둔 것을 재사용한다.
    (파이썬이 참조를 놓으면 tk 가 그림을 지워 버려서 빈칸이 된다)

    **파일이 없던 것도 기억한다.** 상점은 목록을 그릴 때마다 줄마다
    부르는데, 없는 그림을 매번 디스크에서 다시 찾았다. 없다고 본 뒤
    RETRY_AFTER 동안은 바로 None 을 준다(raw() 가 받아 오면 곧바로 풀린다).
    """
    key = (item_id, size)
    if key in _photos:
        return _photos[key]
    img = _fitted.get(key)
    if img is None:
        with _lock:
            t = _no_file.get(item_id)
        if t is not None and time.time() - t < RETRY_AFTER:
            return None
        try:
            base = _decode(item_id)
            if base is None:
                with _lock:
                    _no_file[item_id] = time.time()
                return None
            img = _fit(base, size)
        except Exception:
            return None
    try:
        from PIL import ImageTk
        ph = ImageTk.PhotoImage(img)
    except Exception:
        return None
    _photos[key] = ph
    return ph


def prefetch(api, item_ids, sizes=()):
    """여러 개를 미리 받아 둔다. **작업 스레드에서.**

    받은 것은 여기서 풀어 둔다. sizes 를 주면 그 크기 칸에 맞추는
    것까지 해 둔다 - 그러면 photo() 는 PhotoImage 로 감싸기만 한다.
    """
    got = 0
    for i in item_ids:
        if not raw(api, i):
            continue
        got += 1
        try:
            base = _decode(i)
            if base is None:
                continue
            for s in sizes:
                if (i, s) not in _fitted:
                    _fitted[(i, s)] = _fit(base, s)
        except Exception:                                   # noqa: BLE001
            pass
    return got
