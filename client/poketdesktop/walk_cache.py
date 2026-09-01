# -*- coding: utf-8 -*-
"""걷는 도트(오버월드 스프라이트)를 서버에서 받아 이 PC 에 보관한다.

배틀 도트는 정면 고정이라 걷는 모습이 없다. 이건 4방향에 걷기 프레임이
있어서, 위로 가면 등이 보이고 걸을 때 발이 바뀐다.

한 종에 파일 두 개다.
    0025.png    스프라이트시트 (가로=프레임, 세로=8방향)
    0025.json   칸 크기와 프레임별 지속시간

**걷는 도트가 없는 종도 있다**(1025 중 57마리, 대부분 9세대).
그건 meta 에 ok:false 로 적어 두고 배틀 도트로 대신한다. 없다는 사실도
파일로 남겨야 켤 때마다 다시 물어보지 않는다.
"""
import json
import os
import threading
import time

from . import config

_lock = threading.Lock()
_failed = {}
RETRY_AFTER = 300.0        # 못 받았을 때 다시 시도하기까지 (초)


def walk_dir():
    d = os.path.join(config.data_dir(), "walk")
    os.makedirs(d, exist_ok=True)
    return d


def _paths(num):
    d = walk_dir()
    return (os.path.join(d, "%04d.png" % int(num)),
            os.path.join(d, "%04d.json" % int(num)))


def local(num):
    """이미 받아둔 게 있으면 (시트경로, meta). 없으면 (None, None).

    meta 가 ok:false 면 '이 종은 걷는 도트가 없다' 는 뜻이라
    (None, {"ok": False}) 를 준다.
    """
    png, meta_path = _paths(num)
    if not os.path.exists(meta_path):
        return None, None
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None, None
    if not meta.get("ok"):
        return None, meta
    if os.path.exists(png) and os.path.getsize(png) > 0:
        return png, meta
    return None, None


def ensure(api, num):
    """걷는 도트를 마련한다. **작업 스레드에서 부를 것.**

    돌려주는 값은 (시트경로, meta). 이 종에 걷는 도트가 없으면 (None, None).
    """
    if not num:
        return None, None
    num = int(num)
    png, meta = local(num)
    if png:
        return png, meta
    if meta is not None and not meta.get("ok"):
        return None, None          # 없는 종이라고 이미 확인해 둔 것

    with _lock:
        t = _failed.get(num)
        if t is not None:
            if time.time() - t < RETRY_AFTER:
                return None, None
            del _failed[num]

    try:
        meta = api.walk_meta(num)
    except Exception:                                   # noqa: BLE001
        with _lock:
            _failed[num] = time.time()
        return None, None

    png_path, meta_path = _paths(num)
    if meta and meta.get("retry"):
        # 서버도 지금은 모른다고 한다. 영구 표시를 남기면 안 된다 -
        # 저쪽이 잠깐 맛이 간 사이에 물어본 종이 영영 안 걷게 된다.
        with _lock:
            _failed[num] = time.time()
        return None, None
    if not meta or not meta.get("ok"):
        # 없는 종이라는 사실을 남겨 둔다. 다음부터 안 물어본다.
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"ok": False}, f)
        except OSError:
            pass
        return None, None

    try:
        data = api.walk_sheet(num)
    except Exception:                                   # noqa: BLE001
        data = None
    if not data:
        with _lock:
            _failed[num] = time.time()
        return None, None

    tmp = png_path + ".part"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, png_path)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)
    except OSError:
        return None, None
    return png_path, meta


def ensure_many(api, nums):
    """여러 종을 한 번에. {번호: (시트경로, meta)} 를 준다."""
    out = {}
    for n in nums:
        if not n or n in out:
            continue
        out[n] = ensure(api, n)
    return out
