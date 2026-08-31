# -*- coding: utf-8 -*-
"""poketdesktop 서버.

야생 포켓몬 생성과 포획 판정은 전부 서버가 한다. 클라이언트는 결과만 받는다.
나중에 붙일 배틀/체육관도 같은 원칙이라야 서로 속이지 못한다.

야생 조우는 백그라운드 작업 없이 '물어볼 때 계산하는' 방식이다.
GET /api/wild 이 불릴 때 시간이 됐으면 풀숲을 만들고, 지났으면 정리한다.
"""
import collections
import datetime
import gzip
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

from common import pokelogic as P          # noqa: E402
from . import auth, battle_routes, config, db, deps   # noqa: E402

app = FastAPI(title="poketdesktop", version=config.VERSION)
app.include_router(battle_routes.router)

RNG = deps.RNG

_fails = collections.defaultdict(list)
FAIL_WINDOW = 300
FAIL_LIMIT = 8


def dex():
    return deps.dex()


@app.on_event("startup")
def _startup():
    db.init()
    auth.purge_expired()
    d = dex()
    n = sum(1 for s in d.species if s.get("spawnable"))
    print("[poketdesktop] 도감 %d종 (야생 등장 %d종) 준비 완료" % (len(d.species), n))


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.isoformat()


def _fail_key(username, ip):
    return "%s|%s" % ((username or "").lower(), ip)


def _fail_check(username, ip):
    k = _fail_key(username, ip)
    t = time.time()
    _fails[k] = [x for x in _fails[k] if t - x < FAIL_WINDOW]
    if len(_fails[k]) >= FAIL_LIMIT:
        raise HTTPException(429, "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.")


def _fail_add(username, ip):
    _fails[_fail_key(username, ip)].append(time.time())


def _fail_clear(username, ip):
    _fails.pop(_fail_key(username, ip), None)


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


class ExpIn(BaseModel):
    amount: int = Field(ge=0, le=1000000)


class CatchIn(BaseModel):
    ball: str = "POKEBALL"


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
    }


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
            with urllib.request.urlopen(url, timeout=25) as r:
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
    return {"ip": auth.client_ip(request),
            "raw": request.client.host if request.client else None,
            "forwarded": request.headers.get("x-forwarded-for"),
            "trustProxy": config.TRUST_PROXY}


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
                 " created_at, last_login, last_ip) VALUES (?,?,?,?,?,?,?,?)",
                 (name, h, salt, it, config.BALLS_START, ts, ts, ip))
    uid = cur.lastrowid
    _schedule_next(uid, RNG.randint(60, 180))     # 첫 풀숲은 조금 빨리
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
    sess = auth.lookup_session(body.token)
    if not sess:
        raise HTTPException(401, "저장된 로그인이 만료되었습니다.")
    if sess["device"] and body.device and sess["device"] != body.device:
        raise HTTPException(401, "다른 기기입니다. 비밀번호로 로그인해 주세요.")
    # IP 비교는 양쪽 다 진짜 IP 를 알 수 있을 때만 한다.
    # 도커 포트포워딩 뒤에서는 모두가 게이트웨이 IP 로 보여서 비교가 무의미하다.
    ip = auth.client_ip(request)
    now_real = auth.ip_is_real(request)
    if config.REQUIRE_IP and sess["ip_real"] and now_real and sess["ip"] != ip:
        raise HTTPException(
            401, "접속 위치(IP)가 바뀌었습니다. 비밀번호로 다시 로그인해 주세요.")
    user = db.q1("SELECT * FROM users WHERE id=?", (sess["user_id"],))
    if not user:
        raise HTTPException(401, "계정을 찾을 수 없습니다.")
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
    box = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (uid,))["c"]
    desk = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=? AND on_desktop=1",
                 (uid,))["c"]
    st = db.q1("SELECT * FROM wild_state WHERE user_id=?", (uid,))
    return {
        "user": auth.user_public(u),
        "balls": u["balls"],
        "box": box, "onDesktop": desk,
        "limits": {"maxBox": config.MAX_BOX, "maxParty": config.MAX_PARTY,
                   "grassTtl": config.GRASS_TTL, "wildTtl": config.WILD_TTL},
        "stats": {"encounters": st["encounters"] if st else 0,
                  "caught": st["caught"] if st else 0,
                  "fled": st["fled"] if st else 0},
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
        slot = next(i for i in range(config.MAX_PARTY + 1) if i not in used)
        db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=?", (slot, pid))
    else:
        db.run("UPDATE pokemon SET on_desktop=0, slot=NULL WHERE id=?", (pid,))
    return {"ok": True, "pokemon": _decorate(db.row_to_mon(_own(uid, pid)))}


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
    db.run("DELETE FROM pokemon WHERE id=?", (pid,))
    return {"ok": True, "message": "%s 을(를) 보내주었습니다." % name}


@app.post("/api/pokemon/{pid}/exp")
def add_exp(pid: int, body: ExpIn, ctx=Depends(current)):
    """경험치 부여. 배틀이 붙으면 이 경로는 막고 전투 결과에서만 부르게 바꾼다."""
    uid = ctx["user"]["id"]
    r = _own(uid, pid)
    sp = dex().get(r["species"])
    if not sp:
        raise HTTPException(500, "도감에 없는 종입니다.")
    curve = sp.get("growth", "medium")
    before = r["level"]
    exp = min(r["exp"] + body.amount, P.exp_for_level(curve, P.LEVEL_MAX))
    lv = P.level_from_exp(curve, exp)
    moves = json.loads(r["moves"])
    learned = []
    if lv > before:
        for mlv, mv in sp.get("moves", []):
            if before < mlv <= lv and mv not in moves:
                learned.append(mv)
                moves.append(mv)
        moves = moves[-4:]
    db.run("UPDATE pokemon SET exp=?, level=?, moves=? WHERE id=?",
           (exp, lv, json.dumps(moves), pid))
    return {"ok": True, "level": lv, "leveledUp": lv > before,
            "learned": [dex().move_name(m) for m in learned],
            "pokemon": _decorate(db.row_to_mon(_own(uid, pid)))}


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
    """파티 수준에 맞춘 야생 레벨 범위.

    Lv.5 스타팅으로 시작했는데 Lv.12 짜리가 나오면 이길 방법이 없다.
    반대로 계속 Lv.2 만 나오면 금방 질린다. 그래서 파티 선두를 기준으로
    조금 낮은 것부터 조금 높은 것까지 나오게 한다.
    """
    r = db.q1("SELECT MAX(level) top FROM pokemon WHERE user_id=? AND on_desktop=1",
              (uid,))
    top = (r["top"] if r and r["top"] else config.WILD_MIN_LEVEL)
    lo = max(config.WILD_MIN_LEVEL, top - config.WILD_BELOW)
    hi = max(lo, min(config.WILD_MAX_LEVEL, top + config.WILD_ABOVE))
    cap = config.WILD_BST_BASE + top * config.WILD_BST_PER_LEVEL
    return lo, hi, cap


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

    if row is None:
        due = force or (next_at and auth.parse_iso(next_at) <= now()) or not next_at
        if due:
            n = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (uid,))["c"]
            if n < config.MAX_BOX:
                row = _make_grass(uid)
                st = db.q1("SELECT * FROM wild_state WHERE user_id=?", (uid,))
                next_at = st["next_at"] if st else None

    out = {"wild": _wild_public(row, row["state"] == "revealed") if row else None,
           "nextAt": next_at, "balls": ctx["user"]["balls"], "expired": expired}
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
        return {"wild": _wild_public(row, True)}
    exp = iso(now() + datetime.timedelta(seconds=config.WILD_TTL))
    db.run("UPDATE wild SET state='revealed', expires_at=? WHERE id=?", (exp, wid))
    row = db.q1("SELECT * FROM wild WHERE id=?", (wid,))
    return {"wild": _wild_public(row, True)}


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

    balls = ctx["user"]["balls"]
    if balls <= 0:
        raise HTTPException(409, "몬스터볼이 없습니다.")
    ball = body.ball if body.ball in P.BALL_BONUS else "POKEBALL"
    db.run("UPDATE users SET balls=balls-1 WHERE id=? AND balls>0", (uid,))
    db.run("UPDATE wild SET throws=throws+1 WHERE id=?", (wid,))
    balls -= 1

    mon = json.loads(row["data"])
    sp = dex().get(mon["species"])
    caught, shakes = P.catch_attempt(sp, mon, RNG, ball)

    if not caught:
        left = db.q1("SELECT * FROM wild WHERE id=?", (wid,))
        return {"caught": False, "shakes": shakes, "balls": balls,
                "throws": left["throws"], "expiresAt": left["expires_at"],
                # 본가와 같은 순서: 적게 흔들릴수록 멀었다는 뜻
                "message": ["앗! 포켓몬이 튀어나와버렸다!",
                            "이런! 포켓몬이 볼에서 나와버렸다!",
                            "아앗! 조금만 더 하면 잡을 수 있었는데!",
                            "아깝다! 다 잡았다고 생각했는데!"][min(shakes, 3)]}

    got, where = battle_routes.store_caught(uid, mon)
    db.run("DELETE FROM wild WHERE id=?", (wid,))
    _bump(uid, "caught")
    _schedule_next(uid, _cooldown())
    msg = "신난다! %s 을(를) 잡았다!" % dex().name(mon["species"])
    if where == "box":
        msg += " 자리가 없어서 PC 박스로 보냈다."
    return {"caught": True, "shakes": 4, "balls": balls, "where": where,
            "pokemon": got, "message": msg}


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


@app.exception_handler(HTTPException)
def http_error(request: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
