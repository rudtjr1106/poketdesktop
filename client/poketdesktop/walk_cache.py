# -*- coding: utf-8 -*-
"""오버월드 도트(걷기와 그 밖의 동작)를 서버에서 받아 이 PC 에 보관한다.

배틀 도트는 정면 고정이라 걷는 모습이 없다. 이건 8방향에 프레임이
있어서, 위로 가면 등이 보이고 비스듬히 가면 몸도 비스듬해진다.

한 동작에 파일 두 개다.
    0025/Walk.png    스프라이트시트 (가로=프레임, 세로=방향)
    0025/Walk.json   칸 크기와 프레임별 지속시간

**걷기 말고도 있다.** Idle(가만히 숨쉬기), Sleep, Hurt, Faint, Attack,
Charge, Shoot, Hop. 종마다 있는 것이 다르므로(11~37개) 없는 동작은
ok:false 로 적어 두고 부르는 쪽이 대신할 것을 고른다.

**걷는 도트가 아예 없는 종도 있다**(1025 중 57마리, 대부분 9세대).
그건 배틀 도트로 대신하고, 다른 동작도 쓸 수 없다.
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


def _paths(num, name="Walk"):
    d = os.path.join(walk_dir(), "%04d" % int(num))
    return (os.path.join(d, "%s.png" % name),
            os.path.join(d, "%s.json" % name))


def _migrate_old(num):
    """예전 이름(0025.png / 0025.json)을 0025/Walk.* 로 옮긴다.

    걷기만 받던 시절의 캐시다. 그냥 두면 켤 때 다시 받는다 - 쓰는
    사람 입장에서는 갈아탄 날 포켓몬이 잠깐 안 걷는 것으로 보인다.
    """
    d = walk_dir()
    old_png = os.path.join(d, "%04d.png" % int(num))
    old_meta = os.path.join(d, "%04d.json" % int(num))
    if not os.path.exists(old_meta):
        return
    png, meta_path = _paths(num, "Walk")
    if os.path.exists(meta_path):
        return
    try:
        os.makedirs(os.path.dirname(png), exist_ok=True)
        with open(old_meta, encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("ok") and meta.get("src") == "pmd":
            # 옛 메타에는 4방향만 적혀 있다. 8방향으로 고쳐 준다.
            meta["rowmap"] = {"down": 0, "downright": 1, "right": 2,
                              "upright": 3, "up": 4, "upleft": 5,
                              "left": 6, "downleft": 7}
            meta["rows"] = 8
        if os.path.exists(old_png):
            os.replace(old_png, png)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        os.remove(old_meta)
    except (OSError, ValueError):
        pass


def local(num, name="Walk"):
    """이미 받아둔 게 있으면 (시트경로, meta). 없으면 (None, None).

    meta 가 ok:false 면 '이 종에 이 동작이 없다' 는 뜻이라
    (None, {"ok": False}) 를 준다.
    """
    if name == "Walk":
        _migrate_old(num)
    png, meta_path = _paths(num, name)
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


def ensure(api, num, name="Walk"):
    """그 동작의 도트를 마련한다. **작업 스레드에서 부를 것.**

    돌려주는 값은 (시트경로, meta). 이 종에 그 동작이 없으면 (None, None).
    """
    if not num:
        return None, None
    num = int(num)
    png, meta = local(num, name)
    if png:
        return png, meta
    if meta is not None and not meta.get("ok"):
        return None, None          # 없다고 이미 확인해 둔 것

    fkey = (num, name)
    with _lock:
        t = _failed.get(fkey)
        if t is not None:
            if time.time() - t < RETRY_AFTER:
                return None, None
            del _failed[fkey]

    try:
        meta = api.anim_meta(num, name)
    except Exception:                                   # noqa: BLE001
        with _lock:
            _failed[fkey] = time.time()
        return None, None

    png_path, meta_path = _paths(num, name)
    try:
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
    except OSError:
        return None, None
    if meta and meta.get("retry"):
        # 서버도 지금은 모른다고 한다. 영구 표시를 남기면 안 된다 -
        # 저쪽이 잠깐 맛이 간 사이에 물어본 종이 영영 안 걷게 된다.
        with _lock:
            _failed[fkey] = time.time()
        return None, None
    if not meta or not meta.get("ok"):
        # 없다는 사실을 남겨 둔다. 다음부터 안 물어본다.
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"ok": False}, f)
        except OSError:
            pass
        return None, None

    try:
        data = api.anim_sheet(num, name)
    except Exception:                                   # noqa: BLE001
        data = None
    if not data:
        with _lock:
            _failed[fkey] = time.time()
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


def ensure_many(api, nums, name="Walk"):
    """여러 종을 한 번에. {번호: (시트경로, meta)} 를 준다."""
    out = {}
    for n in nums:
        if not n or n in out:
            continue
        out[n] = ensure(api, n, name)
    return out
