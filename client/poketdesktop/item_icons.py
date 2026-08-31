# -*- coding: utf-8 -*-
"""도구 그림을 받아서 이 PC 에 보관하고, tk 이미지로 만들어 준다.

포켓몬 도트와 다르게 도구 그림은 개당 1~2KB 라서 서버가 전부 들고 있다.
그래서 실패할 일이 거의 없지만, 그래도 한 번 못 받았다고 영영 포기하지는
않는다(도트 쪽에서 그 문제로 그림이 안 뜬 적이 있다).

tk 이미지는 **반드시 tk 스레드에서** 만들어야 한다. 그래서 받아오는 일과
만드는 일을 나눠 뒀다.

    raw(api, item_id)        작업 스레드에서 — 파일 경로를 돌려준다
    photo(item_id, size)     tk 스레드에서 — PhotoImage 를 돌려준다
"""
import os
import threading
import time

from . import config

_lock = threading.Lock()
_failed = {}
_photos = {}
RETRY_AFTER = 30.0


def icon_dir():
    d = os.path.join(config.data_dir(), "items")
    os.makedirs(d, exist_ok=True)
    return d


def local_path(item_id):
    p = os.path.join(icon_dir(), "%s.png" % item_id)
    return p if os.path.exists(p) and os.path.getsize(p) > 0 else None


def raw(api, item_id):
    """그림 파일 경로. 없으면 서버에서 받아온다. **작업 스레드에서 부를 것.**"""
    if not item_id:
        return None
    p = local_path(item_id)
    if p:
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
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except OSError:
        return None
    return path


def photo(item_id, size=28):
    """tk 에 붙일 이미지. 없으면 None. **tk 스레드에서 부를 것.**

    같은 그림을 여러 줄이 함께 쓰므로 만들어 둔 것을 재사용한다.
    (파이썬이 참조를 놓으면 tk 가 그림을 지워 버려서 빈칸이 된다)
    """
    key = (item_id, size)
    if key in _photos:
        return _photos[key]
    p = local_path(item_id)
    if not p:
        return None
    try:
        from PIL import Image, ImageTk
        img = Image.open(p).convert("RGBA")
        if img.width != size or img.height != size:
            # 도트 그림이라 부드럽게 늘리면 뭉개진다. 가까운 점을 그대로.
            scale = min(size / float(img.width), size / float(img.height))
            w = max(1, int(round(img.width * scale)))
            h = max(1, int(round(img.height * scale)))
            img = img.resize((w, h), Image.NEAREST)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.paste(img, ((size - w) // 2, (size - h) // 2))
            img = canvas
        ph = ImageTk.PhotoImage(img)
    except Exception:
        return None
    _photos[key] = ph
    return ph


def prefetch(api, item_ids):
    """여러 개를 미리 받아 둔다. **작업 스레드에서.**"""
    got = 0
    for i in item_ids:
        if raw(api, i):
            got += 1
    return got
