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

**이로치는 옆 폴더(0025s)에 따로 받는다** (1.4.0). 이로치 시트가 없는 종은
보통 색 시트로 걷는다 - 배틀 도트로 굳는 것보다 낫다. 받은 시트를 담는
사전의 열쇠는 key() 로 만든다. 보통은 번호(25) 그대로, 이로치는 (25, True)
라서 예전 코드가 번호로 찾던 자리는 그대로 돈다.
"""
import json
import os
import threading
import time

from . import config

# 걷기 말고 받아 두는 동작들. **여기가 유일한 목록이다** - app 이
# 받아 오는 것도, overlay 가 칸을 잡을 때 훑는 것도 이걸 본다.
ANIMS = ("Idle", "Sleep", "Sit", "Laying", "Wake", "Hop", "Hurt",
         "Faint", "EventSleep")

_lock = threading.Lock()
_failed = {}
RETRY_AFTER = 300.0        # 못 받았을 때 다시 시도하기까지 (초)


def walk_dir():
    d = os.path.join(config.data_dir(), "walk")
    os.makedirs(d, exist_ok=True)
    return d


def key(num, shiny=False):
    """overlay.walks 의 열쇠. 보통은 번호, 이로치는 (번호, True)."""
    if not num:
        return num
    return (int(num), True) if shiny else int(num)


def sheet_key(num, name, shiny=False):
    """overlay.sheets 의 열쇠. 보통은 (번호, 동작), 이로치는 (번호, 동작, True)."""
    return (num, name, True) if shiny else (num, name)


def _paths(num, name="Walk", shiny=False):
    d = os.path.join(walk_dir(), "%04d%s" % (int(num), "s" if shiny else ""))
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


def local(num, name="Walk", shiny=False):
    """이미 받아둔 게 있으면 (시트경로, meta). 없으면 (None, None).

    meta 가 ok:false 면 '이 종에 이 동작이 없다' 는 뜻이라
    (None, {"ok": False}) 를 준다.
    """
    if name == "Walk" and not shiny:
        _migrate_old(num)
    png, meta_path = _paths(num, name, shiny)
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


def ensure(api, num, name="Walk", shiny=False):
    """그 동작의 도트를 마련한다. **작업 스레드에서 부를 것.**

    돌려주는 값은 (시트경로, meta). 이 종에 그 동작이 없으면 (None, None).
    shiny 인데 이로치 시트가 없으면 보통 색 시트를 준다.
    """
    if not num:
        return None, None
    num = int(num)
    if shiny:
        got = _ensure_one(api, num, name, True)
        if got[0]:
            return got
        return _ensure_one(api, num, name, False)
    return _ensure_one(api, num, name, False)


def _takes_shiny(fn):
    try:
        import inspect
        return "shiny" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _ensure_one(api, num, name, shiny):
    png, meta = local(num, name, shiny)
    if png:
        return png, meta
    if meta is not None and not meta.get("ok"):
        return None, None          # 없다고 이미 확인해 둔 것

    fkey = (num, name, shiny)
    with _lock:
        t = _failed.get(fkey)
        if t is not None:
            if time.time() - t < RETRY_AFTER:
                return None, None
            del _failed[fkey]

    try:
        if shiny:
            if not _takes_shiny(api.anim_meta):
                return None, None          # 시험용 가짜 API 등
            meta = api.anim_meta(num, name, shiny=True)
        else:
            meta = api.anim_meta(num, name)
    except Exception:                                   # noqa: BLE001
        with _lock:
            _failed[fkey] = time.time()
        return None, None

    if shiny and meta and meta.get("ok") and not meta.get("shiny"):
        # 옛 서버는 ?shiny=1 을 모르고 보통 시트를 준다. 그걸 이로치 폴더에
        # 굳혀 두면 서버가 새로 바뀐 뒤에도 영영 보통 색으로 걷는다.
        with _lock:
            _failed[fkey] = time.time()
        return None, None

    png_path, meta_path = _paths(num, name, shiny)
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
        data = (api.anim_sheet(num, name, shiny=True) if shiny
                else api.anim_sheet(num, name))
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
    """여러 종을 한 번에. {key(): (시트경로, meta)} 를 준다.

    nums 에는 번호나 (번호, 이로치) 를 섞어 넣을 수 있다.
    """
    out = {}
    for n in nums:
        shiny = False
        if isinstance(n, (tuple, list)):
            n, shiny = n[0], bool(n[1])
        if not n:
            continue
        k = key(n, shiny)
        if k in out:
            continue
        out[k] = ensure(api, n, name, shiny)
    return out
