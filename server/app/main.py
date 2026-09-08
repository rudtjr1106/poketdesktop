# -*- coding: utf-8 -*-
"""poketdesktop 서버.

야생 포켓몬 생성과 포획 판정은 전부 서버가 한다. 클라이언트는 결과만 받는다.
나중에 붙일 배틀/체육관도 같은 원칙이라야 서로 속이지 못한다.

야생 조우는 백그라운드 작업 없이 '물어볼 때 계산하는' 방식이다.
GET /api/wild 이 불릴 때 시간이 됐으면 풀숲을 만들고, 지났으면 정리한다.
"""
import datetime
import gzip
import hmac
import json
import os
import random
import sys
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(_HERE), os.path.dirname(os.path.dirname(_HERE))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from common import korean                  # noqa: E402
from common import pokelogic as P          # noqa: E402
from . import (auth, battle_routes, config, db, deps, item_routes,  # noqa: E402
               errors, items, migrations, pvp, pvp_routes,
               social_routes, tm_routes, tms, walk)

app = FastAPI(title="poketdesktop", version=config.VERSION)
app.include_router(battle_routes.router)
app.include_router(item_routes.router)
app.include_router(pvp_routes.router)
app.include_router(social_routes.router)
app.include_router(tm_routes.router)

RNG = deps.RNG

# 실패 기록은 DB 에 둔다 (db.py 의 login_fail).
# 메모리에 두면 서버가 재시작할 때마다 초기화되어 방어가 풀린다.
# 비밀번호가 숫자 4자리(만 가지)라 시도 제한이 사실상 유일한 방어선이다.
# 5분에 5번까지만 틀릴 수 있다 — 전부 훑으려면 몇 년이 걸린다.
FAIL_WINDOW = 300
FAIL_LIMIT = 5


def dex():
    return deps.dex()


@app.on_event("startup")
def _startup():
    if config.WARM_SPRITES:
        import threading
        threading.Thread(target=_warm_sprites, daemon=True).start()
    db.init()
    migrations.run()
    auth.purge_expired()
    # 양쪽이 다 본 오래된 대전 로그를 치운다. 한 판에 수십 KB 라
    # 그냥 두면 Turso 용량을 제일 먼저 먹는다. 전적은 그대로 남는다.
    try:
        pvp.prune()
    except Exception as e:                                  # noqa: BLE001
        print("[pvp] 오래된 로그 정리 실패: %s" % e)
    errors.sweep()
    d = dex()
    n = sum(1 for s in d.species if s.get("spawnable"))
    print("[poketdesktop] 도감 %d종 (야생 등장 %d종) 준비 완료" % (len(d.species), n))


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.isoformat()


def _fail_key(username, ip):
    """실패 횟수를 세는 열쇠.

    계정을 찾을 때는 strip() 을 하는데 여기서 안 하면, 아이디 뒤에
    공백만 붙여 보내도 매번 새 열쇠가 되어 시도 제한이 풀린다.
    비밀번호가 숫자 네 자리(만 가지)라 이 제한이 사실상 유일한
    방어선이므로 같은 방식으로 다듬어야 한다.
    """
    return "%s|%s" % ((username or "").strip().lower(), ip)


def _fail_check(username, ip):
    """최근 실패가 너무 많으면 막는다."""
    k = _fail_key(username, ip)
    cut = time.time() - FAIL_WINDOW
    db.run("DELETE FROM login_fail WHERE at < ?", (cut,))
    r = db.q1("SELECT COUNT(*) c FROM login_fail WHERE key=? AND at >= ?", (k, cut))
    if r and r["c"] >= FAIL_LIMIT:
        raise HTTPException(429, "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.")


def _fail_add(username, ip):
    db.run("INSERT INTO login_fail (key, at) VALUES (?,?)",
           (_fail_key(username, ip), time.time()))


def _fail_clear(username, ip):
    db.run("DELETE FROM login_fail WHERE key=?", (_fail_key(username, ip),))


# ---------------------------------------------------------------- 인증
current = deps.current


# ---------------------------------------------------------------- 스키마
class RegisterIn(BaseModel):
    username: str
    password: str
    device: str = ""
    starter: str = ""


class LoginIn(BaseModel):
    username: str
    password: str
    device: str = ""


class AutoIn(BaseModel):
    token: str
    device: str = ""


class DeleteIn(BaseModel):
    password: str


class NicknameIn(BaseModel):
    nickname: str = Field(default="", max_length=12)


class DesktopIn(BaseModel):
    on: bool


class OrderIn(BaseModel):
    # 데리고 다니는 마리 수만큼만 받는다. 그보다 길면 자리 수가 어긋난다.
    ids: list[int] = Field(default_factory=list, max_length=12)


class ExpIn(BaseModel):
    amount: int = Field(ge=0, le=1000000)


class CatchIn(BaseModel):
    ball: str = "POKEBALL"
    hour: int = -1        # 클라이언트의 시각. 다크볼이 밤인지 볼 때 쓴다.


# ---------------------------------------------------------------- 공개
@app.get("/api/health")
def health(request: Request):
    d = dex()
    return {
        "ok": True,
        "version": config.VERSION,
        "species": len(d.species),
        "spawnable": sum(1 for s in d.species if s.get("spawnable")),
        "requireIp": config.REQUIRE_IP,
        "ipVisible": auth.ip_is_real(request),
        "observedIp": auth.client_ip(request),
        "account": {"pinDigits": config.PIN_DIGITS,
                    "minName": config.MIN_USERNAME,
                    "maxName": config.MAX_USERNAME},
        # 최근 한 시간에 오류가 몇 번 났는지. 5분마다 도는 keepalive 가
        # 이걸 보고 많으면 워크플로를 실패시킨다 - 그러면 GitHub 이
        # 알아서 메일을 보낸다. 감시 장치를 새로 둘 필요가 없다.
        # 자세한 내용은 넣지 않는다. 여기는 인증 없이 누구나 본다.
        "errors": errors.summary(60),
    }


@app.get("/api/errors")
def error_log(key: str = "", limit: int = 30):
    """최근 오류를 역추적까지. **열쇠를 아는 사람만.**

    개수는 /api/health 로 누구나 본다. 하지만 역추적은 파일 경로와 코드
    구조를 그대로 드러내므로 아무나 보면 안 된다. 열쇠가 설정되어 있지
    않으면 이 경로는 아예 없는 것처럼 군다.

    비교는 hmac.compare_digest 로 한다. 글자 수가 다르면 바로 틀리는
    보통 비교는 걸린 시간으로 앞자리를 하나씩 맞춰 볼 수 있다.
    """
    if not config.ADMIN_KEY or not hmac.compare_digest(key, config.ADMIN_KEY):
        raise HTTPException(404, "Not Found")
    return {"errors": errors.recent(max(1, min(200, limit)))}


@app.get("/api/dexbook")
def dexbook(ctx=Depends(current)):
    """내 도감 현황. 창을 열 때만 부른다(폴링하지 않는다)."""
    return items.dexbook(ctx["user"]["id"], dex())


@app.get("/api/pokedex/meta")
def pokedex_meta():
    d = dex()
    return {"version": d.raw.get("version"), "digest": d.digest(),
            "counts": d.raw.get("counts"), "source": d.raw.get("source")}


@app.get("/api/pokedex")
def pokedex_full():
    with open(config.POKEDEX_PATH, "rb") as f:
        raw = f.read()
    return Response(gzip.compress(raw, 6), media_type="application/json",
                    headers={"Content-Encoding": "gzip",
                             "Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------- 정식 도트
SPRITE_BASE ="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"
SPRITE_SOURCES = [
    ("other/showdown/%s%d.gif", ".gif"),                       # 움직이는 도트
    ("versions/generation-viii/icons/%s%d.png", ".png"),       # 8세대 아이콘
    ("other/official-artwork/%s%d.png", ".png"),               # 공식 일러스트
]
SPRITE_DIR = os.environ.get("POKET_SPRITE_DIR", "/data/sprites")
CONTENT_TYPE = {".gif": "image/gif", ".png": "image/png"}


def _sprite_path(num, shiny, ext):
    return os.path.join(SPRITE_DIR, "%04d%s%s" % (num, "s" if shiny else "", ext))


def _sprite_cached(num, shiny):
    for _pat, ext in SPRITE_SOURCES:
        p = _sprite_path(num, shiny, ext)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p, ext
    return None, None


def _sprite_fetch(num, shiny):
    """PokeAPI 에서 한 번만 받아 디스크에 남긴다."""
    import urllib.error
    import urllib.request
    os.makedirs(SPRITE_DIR, exist_ok=True)
    sub = "shiny/" if shiny else ""
    for pat, ext in SPRITE_SOURCES:
        url = "%s/%s" % (SPRITE_BASE, pat % (sub, num))
        try:
            # 짧게 잡는다. 세 군데를 도는데 각각 25초면 최악에 75초가 되고,
            # 그 전에 클라이언트가 먼저 포기해서 그림이 안 뜬다.
            with urllib.request.urlopen(url, timeout=8) as r:
                data = r.read()
        except (urllib.error.URLError, OSError):
            continue
        if not data:
            continue
        p = _sprite_path(num, shiny, ext)
        tmp = p + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, p)
        return p, ext
    return None, None


def _warm_sprites():
    """빠진 도트를 뒤에서 천천히 받아 둔다.

    도트는 처음 필요할 때 받아오는데, 그 순간 깃허브가 느리면 화면에
    아무것도 안 뜬다. 그래서 서버가 뜨고 나면 조용히 미리 받아 둔다.
    한 번에 몰아 받으면 깃허브가 막으므로 사이를 띄운다.
    """
    import time
    time.sleep(20)                       # 서버가 자리를 잡은 뒤에
    done = 0
    for num in range(1, 1026):
        for shiny in (False, True):
            if _sprite_cached(num, shiny)[0]:
                continue
            try:
                if _sprite_fetch(num, shiny)[0]:
                    done += 1
            except Exception:
                pass
            time.sleep(0.35)             # 깃허브에 부담을 주지 않는다
    if done:
        print("[sprites] 미리 받아둔 도트 %d개" % done, flush=True)


@app.get("/api/sprite/{num}")
def sprite(num: int, shiny: bool = False):
    """정식 도트를 내려준다. 처음 요청될 때만 받아오고 그 뒤로는 캐시."""
    if not 1 <= num <= 1025:
        raise HTTPException(404, "그런 도감 번호가 없습니다.")
    p, ext = _sprite_cached(num, shiny)
    if not p:
        p, ext = _sprite_fetch(num, shiny)
    if not p and shiny:                       # 이로치가 없으면 일반으로 대체
        p, ext = _sprite_cached(num, False)
        if not p:
            p, ext = _sprite_fetch(num, False)
    if not p:
        raise HTTPException(404, "도트를 찾지 못했습니다.")
    with open(p, "rb") as f:
        data = f.read()
    return Response(data, media_type=CONTENT_TYPE.get(ext, "image/gif"),
                    headers={"Cache-Control": "public, max-age=604800",
                             "X-Sprite-Ext": ext})


ITEM_SPRITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "data", "item_sprites")


@app.get("/api/item-sprite/{item_id}")
def item_sprite(item_id: str):
    """도구 그림. 저장소에 같이 들어 있어서 받아올 일이 없다.

    포켓몬 도트와 달리 개당 1~2KB 라서 전부 담아 뒀다. 그래서 처음
    열 때도 비어 보이지 않는다.
    """
    safe = "".join(c for c in (item_id or "").upper() if c.isalnum())
    if not safe:
        raise HTTPException(404, "그런 도구가 없습니다.")
    path = os.path.join(ITEM_SPRITE_DIR, safe + ".png")
    if not os.path.exists(path):
        raise HTTPException(404, "도구 그림이 없습니다.")
    with open(path, "rb") as f:
        data = f.read()
    return Response(data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=2592000"})


# ---------------------------------------------------------------- 걷는 도트
# 배틀 도트(showdown)는 정면 고정이라 걷는 모습이 없다. 걸어다니게 하려면
# 8방향 × 걷기 프레임이 있는 '오버월드' 도트가 필요하다.
# PMDCollab/SpriteCollab 가 그걸 1025종 중 968종에 대해 갖고 있다.
#   sprite/0025/Walk-Anim.png   가로=프레임, 세로=8방향 스프라이트시트
#   sprite/0025/AnimData.xml    칸 크기와 프레임별 지속시간
# 라이선스는 CC BY-NC 4.0 (비상업 + 출처표기).
#
# **걷기 말고도 많다.** 같은 규격으로 Idle(가만히 숨쉬기), Sleep, Hurt,
# Attack, Charge, Shoot, Hop 이 들어 있어서, 도감 번호와 이름만 바꾸면
# 같은 방식으로 받아 쓸 수 있다. 종마다 있는 것이 다르므로(11~37개)
# 없으면 ok:false 를 남기고 부르는 쪽이 알아서 대신할 것을 고른다.
WALK_BASE = "https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/sprite"
# SpriteCollab 에 없는 종을 메우는 두 번째 출처. HGSS 풍 32x32 라 그림체가
# 다르지만, 걷지도 않는 정면 도트보다는 낫다. **여기에는 걷기밖에 없다.**
FOLLOW_BASE = ("https://raw.githubusercontent.com/baptiste-ro/"
               "pokemon-followers-sprites/main/followsprites")
WALK_DIR = os.environ.get("POKET_WALK_DIR", os.path.join(SPRITE_DIR, "walk"))

# 받아도 되는 애니메이션 이름. **이름이 URL 에서 오므로 반드시 막아야
# 한다** - 안 그러면 남의 저장소 아무 경로나 우리 서버로 받아오게 시킬 수
# 있다(../ 나 다른 파일). 여기 있는 것만 통과시킨다.
#
# 32종을 표본으로 세어 보니 전 종에 있는 것은 Walk/Idle/Sleep/Hurt/
# Attack/Charge/Swing/Hop/Rotate/Double 이고, EventSleep 은 절반쯤,
# Shoot 은 거의 다(31/32) 있었다. 우리가 쓰는 것만 적는다.
ANIM_NAMES = ("Walk", "Idle", "Sleep", "EventSleep", "Wake", "Sit", "Laying",
              "Hurt", "Faint", "Attack", "Charge", "Shoot", "Hop")

# 방향 -> 시트의 몇 번째 행인지. 출처마다 배치가 다르다.
#   SpriteCollab : 8행. 아래에서 시작해 오른쪽으로 돈다.
#   followers    : 4행 (0 아래, 1 왼쪽, 2 오른쪽, 3 위)
#
# 8행 배치는 피카츄 시트로 직접 확인했다. 행 2와 6, 1과 7, 3과 5 를
# 좌우로 뒤집어 비교하면 차이가 정확히 0 이고(대칭쌍), 0과 4는 서로
# 완전히 다르다(앞모습/뒷모습).
ROWMAP_PMD = {"down": 0, "downright": 1, "right": 2, "upright": 3,
              "up": 4, "upleft": 5, "left": 6, "downleft": 7}
ROWMAP_FOLLOW = {"down": 0, "left": 1, "right": 2, "up": 3}


def _anim_paths(num, name):
    d = os.path.join(WALK_DIR, "%04d" % num)
    return (os.path.join(d, "%s.png" % name),
            os.path.join(d, "%s.json" % name))


def _png_size(data):
    """PNG 헤더에서 가로세로를 읽는다. (0, 0) 이면 PNG 가 아니다.

    서버에는 Pillow 가 없다. 시트가 몇 행인지 알려면 높이가 필요한데,
    그것 하나 때문에 의존성을 늘릴 이유가 없다. IHDR 은 항상 파일 맨
    앞 고정 위치에 있다.
    """
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0
    import struct
    w, h = struct.unpack(">II", data[16:24])
    return int(w), int(h)


def _migrate_old_walk(num):
    """예전 이름(sheet.png/anim.json)을 Walk.png/Walk.json 으로 옮긴다.

    걷기만 받던 시절의 캐시다. 그냥 두면 968종을 다시 받게 된다.
    """
    d = os.path.join(WALK_DIR, "%04d" % num)
    old_png, old_meta = os.path.join(d, "sheet.png"), os.path.join(d, "anim.json")
    new_png, new_meta = _anim_paths(num, "Walk")
    if not os.path.exists(old_meta) or os.path.exists(new_meta):
        return
    try:
        with open(old_meta, encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("ok") and meta.get("src") == "pmd":
            # 옛 메타에는 4방향만 적혀 있다. 8방향으로 고쳐 준다.
            meta["rowmap"] = ROWMAP_PMD
            meta["rows"] = 8
        if os.path.exists(old_png):
            os.replace(old_png, new_png)
        with open(new_meta, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        os.remove(old_meta)
    except (OSError, ValueError):
        pass


def _pick_anim(root, name):
    """AnimData.xml 에서 이 이름의 칸 크기와 지속시간을 찾는다.

    돌려주는 값은 (프레임가로, 프레임세로, 지속시간목록, 받을PNG이름).
    못 찾으면 None.

    **CopyOf 를 따라가야 한다.** 예를 들어 파이리의 SpAttack 은
    `<CopyOf>Shoot</CopyOf>` 하나뿐이라 자기 PNG 도 칸 크기도 없다.
    그럴 때는 가리키는 쪽의 것을 쓴다. (한 번만 따라간다 - 사슬이
    돌면 무한히 돌 수 있고, 실제 자료에 그런 것도 없다.)
    """
    def find(nm):
        for a in root.iter("Anim"):
            if (a.findtext("Name") or "") == nm:
                return a
        return None

    a = find(name)
    if a is None:
        return None
    png_name = name
    copy = (a.findtext("CopyOf") or "").strip()
    if copy:
        b = find(copy)
        if b is None or (b.findtext("CopyOf") or "").strip():
            return None
        a, png_name = b, copy
    try:
        fw = int(a.findtext("FrameWidth"))
        fh = int(a.findtext("FrameHeight"))
        durs = [int(x.text) for x in a.find("Durations")]
    except (TypeError, ValueError):
        return None
    if fw <= 0 or fh <= 0 or not durs:
        return None
    return fw, fh, durs, png_name


def _anim_fetch(num, name):
    """스프라이트시트와 메타를 한 번만 받아 디스크에 남긴다.

    걷기가 없는 종(57마리)만 두 번째 출처로 넘어간다. 나머지 동작은
    거기에 아예 없으므로 없다고 적어 둔다.
    """
    import urllib.error
    import urllib.request
    import xml.etree.ElementTree as ET

    png_path, meta_path = _anim_paths(num, name)
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    base = "%s/%04d/" % (WALK_BASE, num)

    def grab(fn):
        with urllib.request.urlopen(base + fn, timeout=12) as r:
            return r.read()

    try:
        root = ET.fromstring(grab("AnimData.xml").decode("utf-8"))
        got = _pick_anim(root, name)
        if got is None:
            raise ValueError("%s 없음" % name)
        fw, fh, durs, png_name = got
        png = grab("%s-Anim.png" % png_name)
        if not png:
            raise ValueError("빈 파일")
    except (urllib.error.URLError, OSError, ValueError, ET.ParseError, TypeError):
        if name == "Walk":
            # 걷기가 없다. 두 번째 출처를 본다.
            return _walk_fetch_follow(num, png_path, meta_path)
        return _mark_missing(meta_path)

    sw, sh = _png_size(png)
    rows = max(1, sh // fh) if sh else 8
    frames = max(1, sw // fw) if sw else len(durs)
    # 지속시간이 프레임 수보다 많으면(자료가 어긋난 종이 있다) 잘라낸다.
    # 없는 칸을 가리키면 클라이언트가 시트 밖을 자르게 된다.
    durs = durs[:frames] or [8]

    tmp = png_path + ".part"
    with open(tmp, "wb") as f:
        f.write(png)
    os.replace(tmp, png_path)
    meta = {"ok": True, "frameW": fw, "frameH": fh,
            "durations": durs, "frames": len(durs), "rows": rows,
            "rowmap": ROWMAP_PMD, "src": "pmd", "anim": name}
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    return meta


def _mark_missing(meta_path):
    """이 종에 이 동작이 없다고 적어 둔다. 다음부터 안 물어본다."""
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"ok": False}, f)
    except OSError:
        pass
    return None


def _walk_fetch_follow(num, png_path, meta_path):
    """SpriteCollab 에 없는 종을 followers 저장소에서 찾는다.

    128x128 한 장에 32x32 칸이 가로 4프레임 x 세로 4행으로 들어 있다.
    모든 종이 같은 규격이라 메타를 받을 필요가 없다.
    **여기에는 걷기밖에 없다.** 이 종들은 다른 동작을 못 쓴다.
    """
    import urllib.error
    import urllib.request
    try:
        url = "%s/%d-b-n.png" % (FOLLOW_BASE, num)
        with urllib.request.urlopen(url, timeout=12) as r:
            png = r.read()
        if not png or len(png) < 100:
            raise ValueError("빈 파일")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            # 저쪽이 잠깐 맛이 간 것이다. 표시를 남기면 안 된다 -
            # 한 번 실패한 종이 영영 안 걷게 된다.
            return None
        # 404 라야 '어느 쪽에도 없는 종' 이다. 그때만 남긴다.
        return _mark_missing(meta_path)
    except (urllib.error.URLError, OSError, ValueError):
        # network 오류·시간초과·깨진 파일. 없는 종인지 알 수 없으므로
        # 아무것도 남기지 않고 다음에 다시 물어본다.
        return None

    tmp = png_path + ".part"
    with open(tmp, "wb") as f:
        f.write(png)
    os.replace(tmp, png_path)
    meta = {"ok": True, "frameW": 32, "frameH": 32,
            "durations": [9, 9, 9, 9], "frames": 4, "rows": 4,   # 1/60초 틱
            "rowmap": ROWMAP_FOLLOW, "src": "follow", "anim": "Walk"}
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    return meta


def _anim_meta(num, name):
    if name == "Walk":
        _migrate_old_walk(num)
    _png, meta_path = _anim_paths(num, name)
    if os.path.exists(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return _anim_fetch(num, name)


def _check_anim(num, name):
    if not 1 <= num <= 1025:
        raise HTTPException(404, "그런 도감 번호가 없습니다.")
    if name not in ANIM_NAMES:
        raise HTTPException(404, "그런 동작이 없습니다.")


def _meta_response(num, name):
    meta = _anim_meta(num, name)
    if meta is None:
        # 지금은 알 수 없다(저쪽이 잠깐 안 된다). 클라이언트가 '없는 종'
        # 으로 굳혀 버리지 않게 구분해서 알려준다.
        return {"ok": False, "retry": True}
    if not meta.get("ok"):
        return {"ok": False}
    return meta


def _sheet_response(num, name):
    png_path, _m = _anim_paths(num, name)
    if not os.path.exists(png_path):
        if not (_anim_meta(num, name) or {}).get("ok"):
            raise HTTPException(404, "그 동작의 도트가 없는 종입니다.")
    if not os.path.exists(png_path):
        raise HTTPException(404, "도트를 받지 못했습니다.")
    with open(png_path, "rb") as f:
        data = f.read()
    return Response(data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=604800"})


@app.get("/api/anim/{num}/{name}.json")
def anim_meta(num: int, name: str):
    """이 종에 이 동작이 있는지, 있으면 어떻게 잘라야 하는지."""
    _check_anim(num, name)
    return _meta_response(num, name)


@app.get("/api/anim/{num}/{name}.png")
def anim_sheet(num: int, name: str):
    """그 동작의 스프라이트시트."""
    _check_anim(num, name)
    return _sheet_response(num, name)


# 아래 둘은 1.0.15 까지의 클라이언트가 부른다. 걷기 전용이던 시절의
# 주소라, 새 주소로 넘겨만 준다. 옛 클라이언트가 다 사라지기 전에는
# 지우면 안 된다 - 지우면 그 사람들 포켓몬이 걷기를 멈춘다.
@app.get("/api/walk/{num}.json")
def walk_meta(num: int):
    _check_anim(num, "Walk")
    return _meta_response(num, "Walk")


@app.get("/api/walk/{num}.png")
def walk_sheet(num: int):
    _check_anim(num, "Walk")
    return _sheet_response(num, "Walk")


@app.get("/api/auth/check")
def check_name(name: str = ""):
    """닉네임을 쓸 수 있는지. 회원가입 화면이 타이핑 중에 물어본다."""
    clean, err = auth.check_username(name)
    if err:
        return {"available": False, "reason": err, "name": name}
    if auth.name_taken(clean):
        return {"available": False, "reason": "이미 쓰고 있는 닉네임입니다.",
                "name": clean}
    return {"available": True, "reason": "쓸 수 있는 닉네임입니다.", "name": clean}


@app.get("/api/starters")
def starters():
    """회원가입 화면에 뿌릴 1~9세대 어태커 목록."""
    d = dex()
    out = []
    for row in config.STARTERS:
        gen, keys = row[0], row[1:]
        mons = []
        for k in keys:
            s = d.get(k)
            if not s:
                continue
            mons.append({"internal": k, "kr": s["kr"], "num": s["num"],
                         "gen": s.get("gen"),
                         "types": [d.type_name(t) for t in s["types"]],
                         "typeIds": s["types"]})
        out.append({"gen": gen, "pokemon": mons})
    return {"generations": out, "level": config.STARTER_LEVEL}


@app.get("/api/whoami")
def whoami(request: Request):
    # 어느 헤더를 믿고 IP 를 골랐는지까지 보여준다.
    # 프록시가 여러 겹인 곳(Render 는 Cloudflare 뒤에 있다)에서 잘못된
    # 주소를 집으면 자동 로그인이 무작위로 풀리는데, 그때 원인을 바로
    # 알 수 있어야 한다.
    ip = auth.client_ip(request)
    return {"ip": ip,
            "raw": request.client.host if request.client else None,
            "forwarded": request.headers.get("x-forwarded-for"),
            "cfConnectingIp": request.headers.get("cf-connecting-ip"),
            "realIp": request.headers.get("x-real-ip"),
            "trustProxy": config.TRUST_PROXY,
            "ipUsable": auth.ip_is_real(request)}


# ---------------------------------------------------------------- 계정
def _give_starter(user_id, which):
    d = dex()
    pick = which if which in config.STARTER_SET else RNG.choice(
        sorted(config.STARTER_SET))
    sp = d.get(pick)
    if not sp:
        return None
    mon = P.make_pokemon(sp, config.STARTER_LEVEL, RNG, shiny_rate=config.SHINY_RATE)
    mid = db.insert_mon(user_id, mon, auth.now_iso())
    db.run("UPDATE pokemon SET on_desktop=1, slot=0 WHERE id=?", (mid,))
    items.mark_seen(user_id, pick, True, auth.now_iso())
    return mid


@app.post("/api/auth/register")
def register(body: RegisterIn, request: Request):
    name, err = auth.check_username(body.username)
    if err:
        raise HTTPException(400, err)
    err = auth.check_password(body.password)
    if err:
        raise HTTPException(400, err)
    if db.q1("SELECT id FROM users WHERE username=?", (name,)):
        raise HTTPException(409, "이미 있는 아이디입니다.")

    h, salt, it = auth.hash_password(body.password)
    ip, ts = auth.client_ip(request), auth.now_iso()
    cur = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls,"
                 " money, created_at, last_login, last_ip)"
                 " VALUES (?,?,?,?,?,?,?,?,?)",
                 (name, h, salt, it, config.BALLS_START, config.MONEY_START,
                  ts, ts, ip))
    uid = cur.lastrowid
    # 첫 풀숲은 조금 빨리 — 다만 정해진 간격보다 늦지는 않게.
    # min 이 없으면 간격을 짧게 잡아 둔 곳(테스트)에서도 첫 판만
    # 60~180초를 기다려야 한다.
    _schedule_next(uid, min(RNG.randint(60, 180), _cooldown()))
    _give_starter(uid, body.starter)
    token, exp = auth.issue_token(uid, ip, body.device, auth.ip_is_real(request))
    user = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    return {"token": token, "expiresAt": exp, "user": auth.user_public(user),
            "balls": config.BALLS_START,
            "message": "%s 님, 반갑습니다!" % name}


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request):
    ip = auth.client_ip(request)
    _fail_check(body.username, ip)
    user = db.q1("SELECT * FROM users WHERE username=?", (body.username.strip(),))
    if not user or not auth.verify_password(body.password, user["pw_hash"],
                                            user["pw_salt"], user["pw_iter"]):
        _fail_add(body.username, ip)
        raise HTTPException(401, "아이디 또는 비밀번호가 맞지 않습니다.")
    _fail_clear(body.username, ip)
    db.run("UPDATE users SET last_login=?, last_ip=? WHERE id=?",
           (auth.now_iso(), ip, user["id"]))
    token, exp = auth.issue_token(user["id"], ip, body.device,
                                  auth.ip_is_real(request))
    return {"token": token, "expiresAt": exp, "user": auth.user_public(user)}


@app.post("/api/auth/auto")
def auto_login(body: AutoIn, request: Request):
    """저장된 토큰으로 자동 로그인. 기기가 같아야 하고, IP 를 알 수 있으면 IP 도 본다."""
    # 세션과 계정을 한 번에 읽는다 (왕복 2회 -> 1회).
    sess, user = auth.lookup_session_with_user(body.token)
    if not sess:
        raise HTTPException(401, "저장된 로그인이 만료되었습니다.")
    # 세션에 기기가 적혀 있으면 **반드시** 같아야 한다.
    # 예전에는 `and body.device` 가 붙어 있어서, 기기를 빈 값으로 보내면
    # 검사를 통째로 건너뛰었다. 토큰만 있으면 아무 데서나 들어올 수 있었다.
    if sess["device"] and sess["device"] != (body.device or ""):
        raise HTTPException(401, "다른 기기입니다. 비밀번호로 로그인해 주세요.")
    # IP 비교는 양쪽 다 진짜 IP 를 알 수 있을 때만 한다.
    # 도커 포트포워딩 뒤에서는 모두가 게이트웨이 IP 로 보여서 비교가 무의미하다.
    ip = auth.client_ip(request)
    now_real = auth.ip_is_real(request)
    if config.REQUIRE_IP and sess["ip_real"] and now_real and sess["ip"] != ip:
        raise HTTPException(
            401, "접속 위치(IP)가 바뀌었습니다. 비밀번호로 다시 로그인해 주세요.")
    auth.touch_session(body.token, ip)
    db.run("UPDATE users SET last_login=?, last_ip=? WHERE id=?",
           (auth.now_iso(), ip, user["id"]))
    return {"token": body.token, "expiresAt": sess["expires_at"],
            "user": auth.user_public(user),
            "ipChecked": bool(sess["ip_real"] and now_real)}


@app.post("/api/auth/logout")
def logout(ctx=Depends(current)):
    auth.revoke_token(ctx["token"])
    return {"ok": True}


@app.delete("/api/auth/account")
def delete_account(body: DeleteIn, ctx=Depends(current)):
    u = ctx["user"]
    if not auth.verify_password(body.password, u["pw_hash"], u["pw_salt"], u["pw_iter"]):
        raise HTTPException(401, "비밀번호가 맞지 않습니다.")
    n = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (u["id"],))["c"]
    db.run("DELETE FROM users WHERE id=?", (u["id"],))
    return {"ok": True, "deletedPokemon": n,
            "message": "계정과 포켓몬 %d마리를 삭제했습니다." % n}


@app.get("/api/me")
def me(ctx=Depends(current)):
    u = ctx["user"]
    uid = u["id"]
    # 두 숫자를 한 번에 센다. Turso 는 원격이라 왕복 한 번이 100ms 다 -
    # 나눠 물어볼 이유가 없다.
    c = db.q1("SELECT COUNT(*) c, SUM(on_desktop) d FROM pokemon"
              " WHERE user_id=?", (uid,))
    box = c["c"] or 0
    desk = c["d"] or 0
    st = db.q1("SELECT * FROM wild_state WHERE user_id=?", (uid,))
    # 걸어다닌 만큼 친밀도를 올린다. 이 라우트가 이미 wild_state 를 읽고
    # 있어서 조회가 늘지 않고, 20분에 한 번만 쓰기 두 문장이 나간다.
    walked = walk.settle(uid, st)
    return {
        "user": auth.user_public(u),
        "walked": walked,
        "balls": u["balls"],
        "money": u["money"],
        # 사용자 행을 이미 들고 있으니 balls 를 넘겨 users 를 다시 안 읽는다.
        "bag": items.bag_get(uid, u["balls"]),
        "box": box, "onDesktop": desk,
        "limits": {"maxBox": config.MAX_BOX, "maxParty": config.MAX_PARTY,
                   "grassTtl": config.GRASS_TTL, "wildTtl": config.WILD_TTL},
        "stats": {"encounters": st["encounters"] if st else 0,
                  "caught": st["caught"] if st else 0,
                  "fled": st["fled"] if st else 0},
        # 아직 안 본 대전 수. 상대가 걸어와서 생긴 것도 여기 들어온다.
        # 이걸 위해 폴링을 새로 두지 않는다 - 어차피 90초마다 도는 sync 가
        # 이 라우트를 부르므로 여기에 얹는다. 쿼리 한 번 는다.
        "pvpUnseen": pvp.unseen_count(uid),
        "session": {"ip": ctx["session"]["ip"], "expiresAt": ctx["session"]["expires_at"]},
    }


# ---------------------------------------------------------------- 포켓몬
def _mons(user_id, only_desktop=False):
    sql = "SELECT * FROM pokemon WHERE user_id=?"
    if only_desktop:
        sql += " AND on_desktop=1"
    sql += " ORDER BY on_desktop DESC, slot ASC, id ASC"
    return [db.row_to_mon(r) for r in db.q(sql, (user_id,))]


_decorate = deps.decorate


@app.get("/api/pokemon")
def list_pokemon(ctx=Depends(current)):
    return {"pokemon": [_decorate(m) for m in _mons(ctx["user"]["id"])]}


@app.get("/api/pokemon/desktop")
def list_desktop(ctx=Depends(current)):
    return {"pokemon": [_decorate(m) for m in _mons(ctx["user"]["id"], True)]}


def _own(uid, pid):
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
    if not r:
        raise HTTPException(404, "그런 포켓몬이 없습니다.")
    return r


@app.post("/api/pokemon/{pid}/desktop")
def set_desktop(pid: int, body: DesktopIn, ctx=Depends(current)):
    uid = ctx["user"]["id"]
    _own(uid, pid)
    if body.on:
        cnt = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=? AND on_desktop=1"
                    " AND id<>?", (uid, pid))["c"]
        if cnt >= config.MAX_PARTY:
            raise HTTPException(409, "데리고 다닐 수 있는 건 최대 %d마리입니다."
                                % config.MAX_PARTY)
        used = set(r["slot"] for r in db.q(
            "SELECT slot FROM pokemon WHERE user_id=? AND on_desktop=1 AND id<>?",
            (uid, pid)))
        # next() 는 빈 자리가 없으면 StopIteration 을 던진다. 그건 잡히지
        # 않고 본문 없는 500 으로 나가서, 사용자는 "서버 응답을 이해할 수
        # 없습니다" 만 본다. 자리 수가 어긋나 있어도 말이 되는 답을 준다.
        slot = next((i for i in range(config.MAX_PARTY) if i not in used), None)
        if slot is None:
            raise HTTPException(409, "데리고 다닐 수 있는 건 최대 %d마리입니다."
                                % config.MAX_PARTY)
        db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=?", (slot, pid))
    else:
        db.run("UPDATE pokemon SET on_desktop=0, slot=NULL WHERE id=?", (pid,))
    return {"ok": True, "pokemon": _decorate(db.row_to_mon(_own(uid, pid)))}


@app.post("/api/pokemon/order")
def set_order(body: OrderIn, ctx=Depends(current)):
    """데리고 다니는 순서를 바꾼다.

    화면에서 끌어다 놓은 순서를 그대로 받는다. 자리(slot)는 0부터 다시
    매긴다 - 빈 번호를 남기면 나중에 한 마리를 넣고 뺄 때 순서가 튄다.

    보내온 목록에 없는 마리는 건드리지 않는다. 목록이 낡았을 수 있어서
    (다른 창에서 방금 바꿨다든지) 없는 것을 지우거나 내리면 안 된다.
    """
    uid = ctx["user"]["id"]
    ids = []
    for pid in body.ids:
        if pid in ids:
            continue                      # 같은 것이 두 번 오면 뒤엣것은 버린다
        ids.append(pid)
    if not ids:
        return {"ok": True, "moved": 0}
    if len(ids) > config.MAX_PARTY:
        raise HTTPException(400, "데리고 다닐 수 있는 건 최대 %d마리입니다."
                            % config.MAX_PARTY)

    # 내 것이고 지금 데리고 다니는 것만 자리를 준다. 남의 것을 섞어 보내도
    # 조용히 무시된다(조건이 WHERE 에 들어 있다).
    moved = 0
    for i, pid in enumerate(ids):
        cur = db.run("UPDATE pokemon SET slot=? WHERE id=? AND user_id=?"
                     " AND on_desktop=1", (i, pid, uid))
        moved += cur.rowcount
    return {"ok": True, "moved": moved}


@app.patch("/api/pokemon/{pid}")
def set_nickname(pid: int, body: NicknameIn, ctx=Depends(current)):
    uid = ctx["user"]["id"]
    _own(uid, pid)
    nick = (body.nickname or "").strip() or None
    db.run("UPDATE pokemon SET nickname=? WHERE id=?", (nick, pid))
    return {"ok": True, "pokemon": _decorate(db.row_to_mon(_own(uid, pid)))}


@app.delete("/api/pokemon/{pid}")
def release(pid: int, ctx=Depends(current)):
    uid = ctx["user"]["id"]
    r = _own(uid, pid)
    name = r["nickname"] or dex().name(r["species"])
    # 지닌 도구는 가방으로 돌려준다. 포켓몬과 같이 사라지면 4000원짜리
    # 구애머리띠가 놓아주기 한 번에 날아간다.
    held = r["held"] if "held" in r.keys() else None
    if held:
        items.bag_add(uid, held, 1)
    db.run("DELETE FROM pokemon WHERE id=?", (pid,))
    msg = "%s 을(를) 보내주었습니다." % name
    if held:
        msg += " 지니고 있던 %s은(는) 가방에 넣었습니다." % items.name_of(held)
    return {"ok": True, "message": msg}


# ---------------------------------------------------------------- 지닌 도구
class HoldIn(BaseModel):
    item: str = ""


def _held_of(row):
    return (row["held"] if "held" in row.keys() else None) or None


def _fighting(uid, pid):
    return db.q1("SELECT id FROM battle WHERE user_id=? AND state='active'"
                 " AND mine_id=?", (uid, pid)) is not None


@app.post("/api/pokemon/{pid}/hold")
def hold(pid: int, body: HoldIn, ctx=Depends(current)):
    """가방의 도구 하나를 이 포켓몬에게 지니게 한다.

    지닐 수 있는지는 분류(cat)가 아니라 common/held.py 의 목록으로 본다 -
    금속코트처럼 진화의 돌이면서 지닐 수도 있는 것이 있다. 이미 무언가를
    지니고 있었으면 그건 가방으로 돌아간다. 한 마리에 하나다.
    """
    from common import held as HELD
    from common import korean
    uid = ctx["user"]["id"]
    r = _own(uid, pid)
    item = HELD.normalize(body.item)
    if not item:
        raise HTTPException(400, "지닐 수 없는 도구입니다.")
    if _fighting(uid, pid):
        raise HTTPException(400, "배틀 중에는 도구를 바꿀 수 없습니다.")
    cur = _held_of(r)
    name = r["nickname"] or dex().name(r["species"])
    if cur == item:
        return {"ok": True, "pokemon": _decorate(db.row_to_mon(r)),
                "bag": items.bag_get(uid),
                "message": korean.natural("%s은(는) 이미 %s을(를) 지니고 있다."
                                          % (name, items.name_of(item)))}
    # 가방에서 먼저 뺀다. 없으면 여기서 끝난다 - 아무것도 안 바뀐다.
    if not items.bag_take(uid, item, 1):
        raise HTTPException(400, "%s이(가) 가방에 없습니다." % items.name_of(item))
    if cur:
        items.bag_add(uid, cur, 1)
    db.run("UPDATE pokemon SET held=? WHERE id=?", (item, pid))
    msg = "%s에게 %s을(를) 지니게 했다." % (name, items.name_of(item))
    if cur:
        msg += " %s은(는) 가방에 넣었다." % items.name_of(cur)
    return {"ok": True, "pokemon": _decorate(db.row_to_mon(_own(uid, pid))),
            "bag": items.bag_get(uid), "message": korean.natural(msg)}


@app.delete("/api/pokemon/{pid}/hold")
def unhold(pid: int, ctx=Depends(current)):
    """지닌 도구를 벗겨 가방에 넣는다."""
    from common import korean
    uid = ctx["user"]["id"]
    r = _own(uid, pid)
    cur = _held_of(r)
    if not cur:
        raise HTTPException(400, "지니고 있는 도구가 없습니다.")
    if _fighting(uid, pid):
        raise HTTPException(400, "배틀 중에는 도구를 바꿀 수 없습니다.")
    # 가방에 먼저 넣고 그다음 비운다. 중간에 죽으면 도구가 둘이 되는데,
    # 그건 사용자에게 이득이라 괜찮다. 반대는 안 된다.
    items.bag_add(uid, cur, 1)
    db.run("UPDATE pokemon SET held=NULL WHERE id=?", (pid,))
    name = r["nickname"] or dex().name(r["species"])
    return {"ok": True, "pokemon": _decorate(db.row_to_mon(_own(uid, pid))),
            "bag": items.bag_get(uid),
            "message": korean.natural("%s의 %s을(를) 가방에 넣었다."
                                      % (name, items.name_of(cur)))}


@app.post("/api/pokemon/{pid}/exp")
def add_exp(pid: int, body: ExpIn, ctx=Depends(current)):
    """경험치 부여.

    **이 경로는 테스트용이다.** 인증만 통과하면 경험치를 마음대로 넣을 수
    있어서, 도구 드랍이나 돈처럼 보상이 걸린 것에는 절대 연결하지 않는다.
    실제 경험치는 배틀 결과에서만 붙는다.
    운영에서는 POKET_ALLOW_ADD_EXP=0 으로 막는다.
    """
    if not config.ALLOW_ADD_EXP:
        raise HTTPException(403, "경험치는 배틀로만 얻을 수 있습니다.")
    uid = ctx["user"]["id"]
    _own(uid, pid)
    got = deps.grant_exp(uid, pid, body.amount)
    if got is None:
        raise HTTPException(500, "도감에 없는 종입니다.")
    out = {"ok": True, "level": got["level"], "leveledUp": got["leveledUp"],
           "learned": got["learned"],
           # 자리가 없어 아직 못 배운 것. 클라이언트가 이걸 보고 물어본다.
           "pending": got.get("pending") or [],
           "pendingIds": got.get("pendingIds") or [],
           "pokemon": _decorate(db.row_to_mon(_own(uid, pid)))}
    if got.get("evolve"):
        out["evolve"] = got["evolve"]
    return out


# ---------------------------------------------------------------- 야생 조우
def _schedule_next(uid, seconds):
    at = iso(now() + datetime.timedelta(seconds=int(seconds)))
    db.run("INSERT INTO wild_state (user_id, next_at) VALUES (?,?)"
           " ON CONFLICT(user_id) DO UPDATE SET next_at=?", (uid, at, at))
    return at


def _bump(uid, field):
    db.run("INSERT INTO wild_state (user_id, %s) VALUES (?,1)"
           " ON CONFLICT(user_id) DO UPDATE SET %s=%s+1" % (field, field, field),
           (uid,))


def _cooldown():
    return RNG.randint(config.WILD_COOLDOWN_MIN, config.WILD_COOLDOWN_MAX)


def _wild_public(row, reveal):
    """풀숲 상태에서는 어떤 포켓몬인지 알려주지 않는다."""
    mon = json.loads(row["data"])
    out = {"id": row["id"], "state": row["state"], "throws": row["throws"],
           "expiresAt": row["expires_at"], "createdAt": row["created_at"]}
    if reveal:
        mon["id"] = row["id"]
        mon["wild"] = True
        out["pokemon"] = _decorate(mon)
    return out


def _sweep(uid):
    """만료된 풀숲/야생 개체를 정리한다."""
    t = iso(now())
    gone = db.q("SELECT * FROM wild WHERE user_id=? AND expires_at < ?", (uid, t))
    for r in gone:
        db.run("DELETE FROM wild WHERE id=?", (r["id"],))
        if r["state"] == "grass":
            _bump(uid, "fled")
            _schedule_next(uid, config.MISS_COOLDOWN)
        else:
            _bump(uid, "fled")
            _schedule_next(uid, _cooldown())
    return [r["id"] for r in gone]


def _active(uid):
    return db.q1("SELECT * FROM wild WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,))


def _wild_levels(uid):
    """야생 레벨은 **바탕화면에 나와 있는 것 중 가장 낮은 레벨과 같게** 맞춘다.

    가장 높은 쪽에 맞추면 새로 잡은 저레벨이 영영 못 따라온다. 가장 낮은
    쪽에 맞추면 제일 약한 애가 항상 제 몫의 상대를 만나고, 학습장치로
    나머지도 같이 오르므로 파티 전체가 뒤처지지 않고 굴러간다.

    바닥이 고정되는 건 아니다 — 그 저레벨이 경험치를 받아 올라가면
    최저 레벨도 같이 올라가고, 야생도 따라 올라간다.

    종족값 상한은 그 레벨 기준으로 잡는다. 레벨만 같고 종족값이 두 배인
    상대가 나오면 레벨을 맞춘 의미가 없어지기 때문이다.
    """
    r = db.q1("SELECT MIN(level) low FROM pokemon WHERE user_id=? AND on_desktop=1",
              (uid,))
    low = (r["low"] if r and r["low"] else config.WILD_MIN_LEVEL)
    lvl = max(config.WILD_MIN_LEVEL, min(config.WILD_MAX_LEVEL, low))
    cap = config.WILD_BST_BASE + lvl * config.WILD_BST_PER_LEVEL
    return lvl, lvl, cap


def _make_grass(uid):
    """풀숲을 만들면서 어떤 포켓몬이 숨어 있을지 미리 정해둔다."""
    lo, hi, cap = _wild_levels(uid)
    mon = dex().roll_wild(lo, hi, RNG, max_bst=cap, shiny_rate=config.SHINY_RATE)
    if mon is None:
        raise HTTPException(500, "등장 가능한 포켓몬이 없습니다.")
    t = now()
    cur = db.run(
        "INSERT INTO wild (user_id, state, species, data, created_at, expires_at)"
        " VALUES (?,?,?,?,?,?)",
        (uid, "grass", mon["species"], json.dumps(mon), iso(t),
         iso(t + datetime.timedelta(seconds=config.GRASS_TTL))))
    _bump(uid, "encounters")
    _schedule_next(uid, config.GRASS_TTL + _cooldown())
    return db.q1("SELECT * FROM wild WHERE id=?", (cur.lastrowid,))


@app.get("/api/wild")
def wild_state(ctx=Depends(current), force: bool = False):
    """지금 상태를 알려주고, 시간이 됐으면 풀숲을 돋운다."""
    uid = ctx["user"]["id"]
    expired = _sweep(uid)
    row = _active(uid)
    st = db.q1("SELECT * FROM wild_state WHERE user_id=?", (uid,))
    next_at = st["next_at"] if st else None

    full = False
    if row is None:
        # force 는 보통 '지금 돋우라' 가 아니라 '지금 다시 봐 달라' 다.
        # 예전에는 force 가 맨 앞에 아무 조건 없이 있어서 뒤를 안 봤고,
        # 그래서 트레이의 '풀숲 찾아보기' 를 누르는 만큼 야생이 나왔다.
        # 5~7분 간격이 아무 의미가 없었다.
        # 지금은 테스트에서 명시적으로 열었을 때만 통한다.
        due = ((force and config.ALLOW_FORCE_WILD)
               or (next_at and auth.parse_iso(next_at) <= now())
               or not next_at)
        if due:
            n = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (uid,))["c"]
            if n < config.MAX_BOX:
                row = _make_grass(uid)
                st = db.q1("SELECT * FROM wild_state WHERE user_id=?", (uid,))
                next_at = st["next_at"] if st else None
            else:
                # 자리가 없어서 안 돋는다. 예전에는 여기서 그냥 지나가고
                # next_at 도 그대로 둬서, 사용자 눈에는 어느 날부터 풀숲이
                # 영영 안 돋는 고장으로만 보였다. 이유를 알려주고 시각도
                # 다시 잡는다(안 그러면 지난 시각에 멈춰 있는다).
                full = True
                next_at = _schedule_next(uid, _cooldown())

    out = {"wild": _wild_public(row, row["state"] == "revealed") if row else None,
           "nextAt": next_at, "balls": ctx["user"]["balls"], "expired": expired}
    if full:
        out["boxFull"] = {"max": config.MAX_BOX,
                          "message": "포켓몬이 %d마리로 가득 차서 풀숲이 돋지"
                                     " 않습니다. 관리 창에서 놓아주거나"
                                     " 정리해 주세요." % config.MAX_BOX}
    if next_at:
        out["nextInSeconds"] = max(
            0, int((auth.parse_iso(next_at) - now()).total_seconds()))
    return out


@app.post("/api/wild/{wid}/reveal")
def wild_reveal(wid: int, ctx=Depends(current)):
    """풀숲을 클릭했다. 숨어 있던 포켓몬이 모습을 드러낸다."""
    uid = ctx["user"]["id"]
    _sweep(uid)
    row = db.q1("SELECT * FROM wild WHERE id=? AND user_id=?", (wid, uid))
    if not row:
        raise HTTPException(404, "풀숲이 이미 사라졌습니다.")
    if row["state"] == "revealed":
        return {"wild": _wild_public(row, True),
                "ballOptions": _ball_options(uid, ctx["user"], row)}
    exp = iso(now() + datetime.timedelta(seconds=config.WILD_TTL))
    db.run("UPDATE wild SET state='revealed', expires_at=? WHERE id=?", (exp, wid))
    # 도감에 '봤다' 로 남긴다. 예전에는 이겼거나 잡았을 때만 남아서,
    # 눈앞에서 도망간 포켓몬은 만난 적이 없는 것이 됐다.
    try:
        items.mark_seen(uid, json.loads(row["data"])["species"], False,
                        auth.now_iso())
    except Exception:                                       # noqa: BLE001
        pass
    row = db.q1("SELECT * FROM wild WHERE id=?", (wid,))
    return {"wild": _wild_public(row, True),
            "ballOptions": _ball_options(uid, ctx["user"], row)}


def _ball_options(uid, user_row, row, body=None):
    """지금 이 야생에게 던질 볼 목록.

    응답에 얹어 보낸다. 우클릭할 때마다 서버를 왕복하면 야생은 60초짜리라
    그 시간을 깎아먹고, 서버가 자다 깨는 중이면 메뉴가 아예 안 뜬다.
    배율이 바뀌는 순간(공개·던진 뒤)의 응답에만 실으면 늘 최신이다.
    """
    try:
        mon = json.loads(row["data"])
    except Exception:                                       # noqa: BLE001
        return []
    lead = db.q1("SELECT * FROM pokemon WHERE user_id=? AND on_desktop=1"
                 " ORDER BY slot, id LIMIT 1", (uid,))
    hour = getattr(body, "hour", None) if body else None
    return items.ball_options(uid, dex(), mon, user_row["balls"],
                              mine=db.row_to_mon(lead) if lead else None,
                              turn=row["throws"] or 0, hour=hour)


def _take_ball(uid, balls, want, mon, row, body):
    """던질 볼을 하나 뺀다. (도구 id, 포획 배율, 남은 몬스터볼) 을 준다.

    몬스터볼은 예전부터 users.balls 로 따로 세고 있어서 그 방식을 유지한다.
    그 밖의 볼은 가방에서 뺀다. 그래야 옛 저장 데이터가 그대로 굴러간다.
    """
    want = (want or "POKEBALL").upper()
    it = items.get(want)
    if it is None or it.get("effect", {}).get("kind") != "ball":
        # 예전에는 조용히 몬스터볼로 바꿨다. 이제 메뉴에서 고르는 만큼
        # '고른 것과 다른 볼이 나갔다' 가 되므로 거절한다. 옛 클라이언트는
        # 늘 POKEBALL 을 보내므로 호환이 깨지지 않는다.
        raise HTTPException(400, "그런 볼이 없습니다.")

    if not items.bag_take(uid, want, 1):
        raise HTTPException(409, "%s 이(가) 없습니다." % it["kr"])
    if want == "POKEBALL":
        balls -= 1

    lead = db.q1("SELECT * FROM pokemon WHERE user_id=? AND on_desktop=1"
                 " ORDER BY slot, id LIMIT 1", (uid,))
    mine = db.row_to_mon(lead) if lead else None
    h = getattr(body, "hour", -1)
    hour = h if isinstance(h, int) and 0 <= h <= 23 else None
    bonus = items.ball_bonus(want, dex(), mon, mine=mine,
                             turn=row["throws"], uid=uid, hour=hour)
    return want, bonus, balls


def _drop(uid, mon, chance):
    """야생 하나를 처리했을 때 도구가 떨어지는지."""
    if chance <= 0 or RNG.random() > chance:
        return None
    item_id = items.roll_drop(RNG, bool(mon.get("shiny")))
    items.bag_add(uid, item_id, 1)
    return items.drop_public(item_id)


def _drop_tm(uid, mon, rng):
    """기술머신이 떨어지는지. **도구 드랍과 따로 굴린다.**

    같은 표에 섞으면 358개가 한꺼번에 들어가서 도구 드랍이 기술머신
    잔치가 된다. 여기서 안 나오면 평소처럼 도구만 나온다.

    이미 가진 것은 안 준다 - 팔 수도 없는 물건이라 중복은 아무 일도
    안 일어난 것과 같다.
    """
    sp = dex().get(mon.get("species"))
    num = (sp or {}).get("num")
    no = tms.roll_drop(rng, species_num=num,
                       shiny=bool(mon.get("shiny")), uid=uid)
    if no is None:
        return None
    if not tms.give(uid, no):
        return None
    return tms.public(no)


@app.post("/api/wild/{wid}/catch")
def wild_catch(wid: int, body: CatchIn, ctx=Depends(current)):
    """몬스터볼을 던진다. 판정은 본가 5세대 이후 공식 그대로."""
    uid = ctx["user"]["id"]
    _sweep(uid)
    row = db.q1("SELECT * FROM wild WHERE id=? AND user_id=?", (wid, uid))
    if not row:
        raise HTTPException(404, "야생 포켓몬이 이미 사라졌습니다.")
    if row["state"] != "revealed":
        raise HTTPException(409, "아직 모습을 드러내지 않았습니다.")

    mon = json.loads(row["data"])
    sp = dex().get(mon["species"])

    # 어떤 볼을 던질지. 기본 몬스터볼은 users.balls 에서, 그 밖의 볼은
    # 가방에서 뺀다. (몬스터볼은 예전부터 따로 세고 있어서 그대로 둔다)
    ball_id, bonus, balls = _take_ball(uid, ctx["user"]["balls"], body.ball,
                                       mon, row, body)
    db.run("UPDATE wild SET throws=throws+1 WHERE id=?", (wid,))

    caught, shakes = P.catch_attempt(sp, mon, RNG, bonus)

    if not caught:
        left = db.q1("SELECT * FROM wild WHERE id=?", (wid,))
        user = db.q1("SELECT * FROM users WHERE id=?", (uid,))
        return {"caught": False, "shakes": shakes, "balls": balls,
                "ball": ball_id,
                "throws": left["throws"], "expiresAt": left["expires_at"],
                # 개수도 턴도 방금 바뀌었다. 갱신된 목록을 같이 준다.
                "ballOptions": _ball_options(uid, user, left, body),
                # 본가와 같은 순서: 적게 흔들릴수록 멀었다는 뜻
                "message": ["앗! 포켓몬이 튀어나와버렸다!",
                            "이런! 포켓몬이 볼에서 나와버렸다!",
                            "아앗! 조금만 더 하면 잡을 수 있었는데!",
                            "아깝다! 다 잡았다고 생각했는데!"][min(shakes, 3)]}

    extra = items.ball_extra(ball_id)
    if extra.get("happiness"):
        mon["happiness"] = extra["happiness"]
    # 럭셔리볼은 친밀도가 두 배로 오른다. 그동안 happinessRate 를
    # 돌려주기만 하고 읽는 쪽이 없어서 아무 일도 안 하고 있었다.
    if extra.get("happinessRate", 1) > 1:
        mon["luxury"] = True
    got, where = battle_routes.store_caught(uid, mon)
    db.run("DELETE FROM wild WHERE id=?", (wid,))
    _bump(uid, "caught")
    _schedule_next(uid, _cooldown())
    items.mark_seen(uid, mon["species"], True, auth.now_iso())
    drop = _drop(uid, mon, config.DROP_ON_CATCH)
    tm_drop = _drop_tm(uid, mon, RNG)
    msg = "신난다! %s 을(를) 잡았다!" % dex().name(mon["species"])
    if where == "box":
        msg += " 자리가 없어서 PC 박스로 보냈다."
    if drop:
        msg += "  %s 을(를) 주웠다!" % drop["kr"]
    if tm_drop:
        msg += "  %s 을(를) 주웠다!" % tm_drop["label"]
    return {"caught": True, "shakes": 4, "balls": balls, "where": where,
            "ball": ball_id,
            "pokemon": got, "drop": drop, "tmDrop": tm_drop,
            "money": items.money(uid),
            "bag": items.bag_get(uid), "message": korean.natural(msg)}


@app.post("/api/wild/{wid}/flee")
def wild_flee(wid: int, ctx=Depends(current)):
    """시간이 다 됐거나 그냥 보내줄 때."""
    uid = ctx["user"]["id"]
    row = db.q1("SELECT * FROM wild WHERE id=? AND user_id=?", (wid, uid))
    if row:
        db.run("DELETE FROM wild WHERE id=?", (wid,))
        _bump(uid, "fled")
        _schedule_next(uid, _cooldown() if row["state"] == "revealed"
                       else config.MISS_COOLDOWN)
    st = db.q1("SELECT * FROM wild_state WHERE user_id=?", (uid,))
    return {"ok": True, "nextAt": st["next_at"] if st else None}


@app.exception_handler(Exception)
def any_error(request: Request, exc: Exception):
    """예상 못 한 오류.

    그냥 두면 본문 없는 500 이 나가서 사용자는 "가끔 오류가 뜬다" 로만
    겪고, 서버 로그에도 무슨 요청이었는지 안 남는다. 어디서 났는지
    남기고, 사람이 읽을 수 있는 말로 돌려준다.
    """
    import traceback
    tb = traceback.format_exc()
    print("[500] %s %s" % (request.method, request.url.path), flush=True)
    print(tb, flush=True)
    # 표에도 남긴다. 그래야 대시보드를 열지 않아도 알 수 있다.
    errors.record(request.method, request.url.path, exc, tb)
    return JSONResponse(
        {"error": "서버에서 문제가 생겼습니다. 잠시 후 다시 시도해 주세요."},
        status_code=500)


@app.exception_handler(HTTPException)
def http_error(request: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
