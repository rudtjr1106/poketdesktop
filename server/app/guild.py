# -*- coding: utf-8 -*-
"""길드 (1.10.0) — 만들기·가입·관리, 채팅, 일일 미션, 길드 코인 상점.

## 얼개

    guild           길드 하나 (이름, 소개, 가입 방식, 마스터)
    guild_member    누가 어느 길드에 어떤 자리로 있나 (한 사람은 한 길드)
    guild_request   승인이 필요한 길드에 넣어 둔 가입 신청
    guild_chat      채팅과 알림 줄
    guild_mission   그날 그 사람이 한 미션
    guild_user      사람마다: 길드 코인, 마지막으로 나온 때
    guild_claim     그날 받은 단계 보상

## 자리와 권한

    master  한 명. 전부 할 수 있다 (소개·가입 방식, 부마스터 임명, 위임, 해산).
    sub     부마스터. 가입 신청을 받고, 일반 길드원을 내보낸다.
    member  일반 길드원.

마스터는 혼자 남았을 때만 나갈 수 있다(그러면 길드가 없어진다). 사람이 남아
있으면 자리를 넘기거나 해산해야 한다 - 마스터 없는 길드가 생기면 안 된다.

## 일일 미션 (세븐나이츠의 길드 미션 같은 것)

길드원이 저마다 그날의 미션을 하면 점수가 **길드에 모인다.** 길드 점수가
단계(TIERS)를 넘을 때마다 그날 한 점이라도 보탠 길드원이 보상을 받는다.
하루는 한국 시각 자정에 바뀐다 (랭크 배틀과 같다).

보상은 **사람에게** 건다 (guild_claim). 길드를 옮겨 다녀도 같은 날 같은 단계를
두 번 받을 수 없다. 길드 코인도 사람이 갖는다 - 길드를 나가도 남는다.

## 채팅

**웹소켓으로 밀어 준다** (guild_ws.py). 줄이 생기거나 길드에 무슨 일이 있으면 여기서
listeners 에 건 함수를 부르고, 그쪽이 붙어 있는 길드원에게 보낸다.

    {"t": "chat", "m": {...}}   새 줄 (말 또는 알림)
    {"t": "changed"}            사람·신청·점수·소개가 바뀌었다 - 화면을 다시 받아라
    {"t": "left"}               이 길드에서 나왔다 (내보내졌거나 해산)

웹소켓이 막힌 망(회사·학교)도 있어서 **폴링 길도 그대로 둔다**: GET /api/guild/chat?after=
는 '이 번호 뒤의 줄' 을 준다. 화면은 웹소켓이 붙어 있으면 밀려오는 것만 받고, 끊기면
2초마다 이 길로 묻는다. 줄 번호(id)가 곧 순서라 두 길이 섞여도 겹치거나 빠지지 않는다.
"""
import datetime
import math
import sqlite3
import time
import zlib

from fastapi import HTTPException

from . import auth, config, db, items, season, social

KST = datetime.timezone(datetime.timedelta(hours=9))

NAME_MIN, NAME_MAX = 2, 12
INTRO_MAX = 80
MESSAGE_MAX = 60
PAGE = 10
CHAT_FIRST = 50            # 처음 열 때 주는 줄 수
CHAT_STEP = 100            # 한 번에 더 주는 줄 수

ROLE_KR = {"master": "마스터", "sub": "부마스터", "member": "길드원"}
MODES = ("open", "approve")

# 일일 미션: (열쇠, 이름, 목표, 점수). 한 사람이 하루에 다 하면 10점.
MISSIONS = (
    ("attend", "길드에 출석하기", 1, 1),
    ("catch", "야생 포켓몬 잡기", 5, 2),
    ("battle", "야생 포켓몬과 싸워 이기기", 5, 2),
    ("gym", "관장 배틀에서 이기기", 3, 2),
    ("rank", "랜덤 배틀 하기", 10, 3),
)
MISSION = dict((m[0], m) for m in MISSIONS)
DAY_MAX = sum(m[3] for m in MISSIONS)

# 단계 보상: (필요한 길드 점수, 몬스터볼, 길드 코인).
# 혼자서는 1단계(10점)까지, 열 명이 다 하면 끝(100점)까지 간다 - 사람을 모을 까닭이 된다.
TIERS = (
    (10, 5, 0),
    (25, 0, 10),
    (45, 5, 15),
    (70, 0, 20),
    (100, 10, 30),
)

# 코인 상점에 내놓는 것. **상점에서 살 수 있는 것만** 판다 (값은 상점 값에서 나온다).
# 금구슬 같은 '팔아서 돈으로 바꾸는 물건' 은 뺐다 - 코인을 돈으로 바꾸는 창구가 된다.
SHOP_CATS = ("ball",)
SHOP_ITEMS = ("RARECANDY", "BOTTLECAP", "HPUP", "PROTEIN", "IRON", "CALCIUM", "ZINC", "CARBOS",
              "HEALTHWING", "MUSCLEWING", "RESISTWING", "GENIUSWING", "CLEVERWING", "SWIFTWING")
BUY_MAX = 99


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _dup(e):
    """기본키·유일 조건에 걸린 오류인가 (이미 있는 줄을 또 넣으려 했다)."""
    t = ("%s %s" % (type(e).__name__, e)).lower()
    return isinstance(e, sqlite3.IntegrityError) or "unique" in t or "constraint" in t


def _iso(t=None):
    return (t or _now()).isoformat()


def today(now=None):
    """오늘 날짜 (한국 시각). 미션과 보상이 이걸로 나뉜다."""
    return (now or _now()).astimezone(KST).date().isoformat()


def reset_in(now=None):
    """다음 자정(한국 시각)까지 몇 초."""
    t = (now or _now()).astimezone(KST)
    nxt = (t + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(0, int((nxt - t).total_seconds()))


def _ago(iso, now=None):
    if not iso:
        return None
    try:
        return max(0, int(((now or _now()) - datetime.datetime.fromisoformat(iso)).total_seconds()))
    except ValueError:
        return None


# ---------------------------------------------------------------- 읽기
def member(uid):
    """내가 든 길드에서의 내 줄 (guild_id, role ...). 없으면 None."""
    return db.q1("SELECT * FROM guild_member WHERE user_id=?", (uid,))


def guild_of(gid):
    return db.q1("SELECT * FROM guild WHERE id=?", (gid,))


def _count(gid):
    r = db.q1("SELECT COUNT(*) c FROM guild_member WHERE guild_id=?", (gid,))
    return r["c"] if r else 0


def _wallet(uid):
    r = db.q1("SELECT coin, left_at FROM guild_user WHERE user_id=?", (uid,))
    return r or {"coin": 0, "left_at": None}


def coin(uid):
    return int(_wallet(uid)["coin"] or 0)


def cooldown(uid, now=None):
    """길드에 다시 들어갈 수 있을 때까지 남은 초. 바로 되면 0."""
    left = _wallet(uid)["left_at"]
    gone = _ago(left, now)
    if gone is None:
        return 0
    return max(0, config.GUILD_REJOIN_HOURS * 3600 - gone)


def _need(uid):
    m = member(uid)
    if not m:
        raise HTTPException(400, "길드에 들어 있지 않습니다.")
    return m


def _need_manager(uid, master_only=False):
    m = _need(uid)
    if m["role"] != "master" and (master_only or m["role"] != "sub"):
        raise HTTPException(403, "길드 마스터만 할 수 있습니다." if master_only
                            else "길드 마스터나 부마스터만 할 수 있습니다.")
    return m


def _name_of(uid):
    r = db.q1("SELECT username FROM users WHERE id=?", (uid,))
    return r["username"] if r else "?"


def _guild_public(g, n=None, master=None):
    return {"id": g["id"], "name": g["name"], "intro": g["intro"],
            "joinMode": g["join_mode"], "masterId": g["master_id"],
            "masterName": master if master is not None else _name_of(g["master_id"]),
            "members": _count(g["id"]) if n is None else n,
            "max": config.GUILD_MAX_MEMBERS, "points": int(g["points"] or 0),
            "createdAt": g["created_at"]}


# ---------------------------------------------------------------- 밀어 주기
# 길드에 일이 생기면 여기 건 함수가 불린다: fn("guild", 길드 번호, 보낼 것) 또는
# fn("user", 사람 번호, 보낼 것). guild_ws 가 건다. **비어 있으면 아무 일도 없다** -
# 검사와, 웹소켓 없이 뜬 서버에서는 그대로 비어 있다. 여기서 난 오류로 하던 일이 깨지면 안 된다.
listeners = []


def _emit(kind, target, payload):
    for fn in list(listeners):
        try:
            fn(kind, target, payload)
        except Exception:                                   # noqa: BLE001
            pass


def _changed(gid):
    """사람·신청·점수·소개가 바뀌었다. 붙어 있는 길드원의 화면이 다시 받는다."""
    _emit("guild", gid, {"t": "changed"})


def _line(mid, uid, name, body, at):
    """채팅 한 줄을 보낼 꼴로. (mine 은 받는 사람마다 다르므로 화면이 userId 로 정한다)"""
    return {"id": mid, "userId": uid, "name": name, "body": body, "at": at, "system": uid is None}


# ---------------------------------------------------------------- 알림 줄
def _say(gid, text, now=None):
    at = _iso(now)
    cur = db.run("INSERT INTO guild_chat (guild_id, user_id, name, body, at) VALUES (?,NULL,'',?,?)",
                 (gid, text, at))
    _emit("guild", gid, {"t": "chat", "m": _line(cur.lastrowid, None, "", text, at)})


# ---------------------------------------------------------------- 목록
def listing(uid, q="", page=1):
    """길드 찾기. 이름 일부로 찾는다 (사람 찾기와 달리 길드는 드러나 있는 것이다)."""
    q = (q or "").strip()[:NAME_MAX]
    where, args = "", ()
    if q:
        where = " WHERE g.name LIKE ? ESCAPE '\\'"
        args = ("%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",)
    total = db.q1("SELECT COUNT(*) c FROM guild g" + where, args)["c"]
    pages = max(1, int(math.ceil(total / float(PAGE))))
    page = max(1, min(int(page or 1), pages))
    rows = db.q(
        "SELECT g.*, u.username master_name,"
        " (SELECT COUNT(*) FROM guild_member m WHERE m.guild_id=g.id) n"
        " FROM guild g LEFT JOIN users u ON u.id=g.master_id" + where +
        " ORDER BY n DESC, g.points DESC, g.id LIMIT ? OFFSET ?",
        args + (PAGE, (page - 1) * PAGE))
    mine = set(r["guild_id"] for r in db.q(
        "SELECT guild_id FROM guild_request WHERE user_id=?", (uid,)))
    out = []
    for g in rows:
        d = _guild_public(g, n=g["n"], master=g["master_name"] or "?")
        d["requested"] = g["id"] in mine
        d["full"] = g["n"] >= config.GUILD_MAX_MEMBERS
        out.append(d)
    return {"guilds": out, "page": page, "pages": pages, "total": total, "query": q}


# ---------------------------------------------------------------- 만들기
def _clean_name(name):
    name = " ".join((name or "").split())
    if not (NAME_MIN <= len(name) <= NAME_MAX):
        raise HTTPException(400, "길드 이름은 %d~%d자로 지어 주세요." % (NAME_MIN, NAME_MAX))
    if not auth.USERNAME_RE.match(name):
        raise HTTPException(400, "길드 이름에는 한글·영문·숫자와 공백 . _ - 만 쓸 수 있습니다.")
    return name


def _clean_text(text, limit):
    return " ".join((text or "").split())[:limit]


def _clean_mode(mode):
    if mode not in MODES:
        raise HTTPException(400, "가입 방식은 자유 가입과 승인 필요 중에서 고릅니다.")
    return mode


def _free_to_join(uid, now=None):
    if member(uid):
        raise HTTPException(400, "이미 길드에 들어 있습니다.")
    left = cooldown(uid, now)
    if left > 0:
        raise HTTPException(400, "길드를 나온 지 얼마 안 됐습니다. %s 뒤에 다시 해 주세요."
                            % _span(left))


def _span(sec):
    h, m = sec // 3600, (sec % 3600) // 60
    if h:
        return "%d시간 %d분" % (h, m) if m else "%d시간" % h
    return "%d분" % max(1, m)


def create(uid, name, intro="", mode="open", now=None):
    name = _clean_name(name)
    intro = _clean_text(intro, INTRO_MAX)
    mode = _clean_mode(mode)
    _free_to_join(uid, now)
    if db.q1("SELECT 1 x FROM guild WHERE name=?", (name,)):
        raise HTTPException(409, "같은 이름의 길드가 이미 있습니다.")
    cost = config.GUILD_CREATE_COST
    if not items.money_take(uid, cost):
        raise HTTPException(400, "돈이 모자랍니다. 길드를 만들려면 %s원이 필요합니다."
                            % format(cost, ","))
    gid = None
    try:
        cur = db.run("INSERT INTO guild (name, intro, join_mode, master_id, created_at)"
                     " VALUES (?,?,?,?,?)", (name, intro, mode, uid, _iso(now)))
        gid = cur.lastrowid
        db.run("INSERT INTO guild_member (user_id, guild_id, role, joined_at) VALUES (?,?,?,?)",
               (uid, gid, "master", _iso(now)))
    except Exception as e:                                  # noqa: BLE001
        # 그사이 같은 이름이 생겼거나, 다른 창에서 길드에 들어갔다. **돈을 돌려준다.**
        # 무슨 오류든 돈만 빠지고 길드가 없는 채로 끝나면 안 된다.
        if gid is not None:
            db.run("DELETE FROM guild WHERE id=?", (gid,))
        items.money_add(uid, cost)
        if _dup(e):
            raise HTTPException(409, "길드를 만들지 못했습니다. 이름이 겹치거나 이미 길드에 "
                                     "들어 있습니다.")
        raise
    db.run("DELETE FROM guild_request WHERE user_id=?", (uid,))     # 넣어 둔 신청은 거둔다
    _say(gid, "%s 길드가 만들어졌습니다!" % name, now)
    return {"ok": True, "message": "%s 길드를 만들었습니다!" % name, "spent": cost}


# ---------------------------------------------------------------- 가입·탈퇴
def _add_member(gid, uid, now=None):
    """정원 안에서만 넣는다 (한 문장이라 둘이 동시에 들어와도 넘치지 않는다). 넣었으면 True."""
    try:
        cur = db.run(
            "INSERT INTO guild_member (user_id, guild_id, role, joined_at)"
            " SELECT ?,?,'member',? WHERE (SELECT COUNT(*) FROM guild_member"
            " WHERE guild_id=?) < ?",
            (uid, gid, _iso(now), gid, config.GUILD_MAX_MEMBERS))
    except Exception as e:                                  # noqa: BLE001
        if _dup(e):
            return False                    # 그사이 다른 길드에 들어갔다
        raise
    if cur.rowcount <= 0:
        return False
    db.run("DELETE FROM guild_request WHERE user_id=?", (uid,))
    return True


def join(uid, gid, message="", now=None):
    g = guild_of(gid)
    if not g:
        raise HTTPException(404, "그런 길드가 없습니다.")
    _free_to_join(uid, now)
    if _count(gid) >= config.GUILD_MAX_MEMBERS:
        raise HTTPException(409, "정원이 가득 찬 길드입니다.")
    if g["join_mode"] == "open":
        if not _add_member(gid, uid, now):
            raise HTTPException(409, "정원이 가득 찬 길드입니다.")
        _say(gid, "%s 님이 길드에 들어왔습니다." % _name_of(uid), now)
        _changed(gid)
        return {"ok": True, "joined": True, "message": "%s 길드에 들어갔습니다!" % g["name"]}
    if db.q1("SELECT 1 x FROM guild_request WHERE guild_id=? AND user_id=?", (gid, uid)):
        raise HTTPException(409, "이미 가입 신청을 넣어 둔 길드입니다.")
    n = db.q1("SELECT COUNT(*) c FROM guild_request WHERE user_id=?", (uid,))["c"]
    if n >= config.GUILD_MAX_REQUESTS:
        raise HTTPException(400, "가입 신청은 한 번에 %d곳까지 넣을 수 있습니다."
                            % config.GUILD_MAX_REQUESTS)
    db.run("INSERT INTO guild_request (guild_id, user_id, message, created_at) VALUES (?,?,?,?)",
           (gid, uid, _clean_text(message, MESSAGE_MAX), _iso(now)))
    _changed(gid)                           # 마스터의 화면에 신청이 바로 뜬다
    return {"ok": True, "joined": False,
            "message": "%s 길드에 가입 신청을 넣었습니다. 승인을 기다려 주세요." % g["name"]}


def cancel_request(uid, gid):
    db.run("DELETE FROM guild_request WHERE guild_id=? AND user_id=?", (gid, uid))
    _changed(gid)
    return {"ok": True, "message": "가입 신청을 거뒀습니다."}


def decide(uid, target, accept, now=None):
    """가입 신청을 받거나 돌려보낸다 (마스터·부마스터)."""
    m = _need_manager(uid)
    gid = m["guild_id"]
    if not db.q1("SELECT 1 x FROM guild_request WHERE guild_id=? AND user_id=?", (gid, target)):
        raise HTTPException(404, "그런 가입 신청이 없습니다.")
    if not accept:
        db.run("DELETE FROM guild_request WHERE guild_id=? AND user_id=?", (gid, target))
        _changed(gid)
        return {"ok": True, "message": "가입 신청을 돌려보냈습니다."}
    if member(target):
        db.run("DELETE FROM guild_request WHERE guild_id=? AND user_id=?", (gid, target))
        raise HTTPException(409, "그사이 다른 길드에 들어간 사람입니다.")
    if not _add_member(gid, target, now):
        raise HTTPException(409, "정원이 가득 찼습니다.")
    _say(gid, "%s 님이 길드에 들어왔습니다." % _name_of(target), now)
    _changed(gid)
    return {"ok": True, "message": "%s 님을 길드에 받았습니다." % _name_of(target)}


def _mark_left(uid, now=None):
    db.run("INSERT INTO guild_user (user_id, coin, left_at) VALUES (?,0,?)"
           " ON CONFLICT(user_id) DO UPDATE SET left_at=excluded.left_at", (uid, _iso(now)))


def _drop(gid):
    """길드를 없앤다. 딸린 줄을 손으로 지운다 (외래키가 꺼진 연결에서도 남지 않게)."""
    _emit("guild", gid, {"t": "left"})      # 붙어 있던 길드원의 화면이 '길드 없음' 으로 돌아간다
    for t in ("guild_member", "guild_request", "guild_chat", "guild_mission"):
        db.run("DELETE FROM %s WHERE guild_id=?" % t, (gid,))
    db.run("DELETE FROM guild WHERE id=?", (gid,))


def leave(uid, now=None):
    m = _need(uid)
    gid = m["guild_id"]
    g = guild_of(gid)
    if m["role"] == "master":
        if _count(gid) > 1:
            raise HTTPException(400, "길드 마스터는 그냥 나갈 수 없습니다. 자리를 넘기거나 "
                                     "길드를 해산해 주세요.")
        _drop(gid)                          # 혼자 남은 마스터가 나가면 길드가 없어진다
        _mark_left(uid, now)
        return {"ok": True, "message": "%s 길드를 나왔습니다. 남은 사람이 없어 길드가 "
                                       "없어졌습니다." % g["name"]}
    _emit("user", uid, {"t": "left"})       # 다른 기기에 띄워 둔 화면도 닫힌다
    db.run("DELETE FROM guild_member WHERE user_id=?", (uid,))
    _mark_left(uid, now)
    _say(gid, "%s 님이 길드를 나갔습니다." % _name_of(uid), now)
    _changed(gid)
    return {"ok": True, "message": "%s 길드를 나왔습니다." % g["name"]}


def kick(uid, target, now=None):
    m = _need_manager(uid)
    t = member(target)
    if not t or t["guild_id"] != m["guild_id"]:
        raise HTTPException(404, "우리 길드원이 아닙니다.")
    if target == uid:
        raise HTTPException(400, "자기 자신은 내보낼 수 없습니다.")
    if t["role"] == "master" or (m["role"] == "sub" and t["role"] != "member"):
        raise HTTPException(403, "그 길드원은 내보낼 수 없습니다.")
    _emit("user", target, {"t": "left"})    # 내보내진 사람의 화면이 바로 '길드 없음' 이 된다
    db.run("DELETE FROM guild_member WHERE user_id=?", (target,))
    _mark_left(target, now)
    _say(m["guild_id"], "%s 님이 길드에서 내보내졌습니다." % _name_of(target), now)
    _changed(m["guild_id"])
    return {"ok": True, "message": "%s 님을 길드에서 내보냈습니다." % _name_of(target)}


def set_role(uid, target, role, now=None):
    """부마스터로 올리거나 일반 길드원으로 내린다 (마스터만)."""
    m = _need_manager(uid, master_only=True)
    if role not in ("sub", "member"):
        raise HTTPException(400, "부마스터나 길드원으로만 바꿀 수 있습니다.")
    t = member(target)
    if not t or t["guild_id"] != m["guild_id"] or target == uid:
        raise HTTPException(404, "우리 길드원이 아닙니다.")
    if t["role"] == role:
        return {"ok": True, "message": "이미 %s입니다." % ROLE_KR[role]}
    if role == "sub":
        n = db.q1("SELECT COUNT(*) c FROM guild_member WHERE guild_id=? AND role='sub'",
                  (m["guild_id"],))["c"]
        if n >= config.GUILD_MAX_SUBS:
            raise HTTPException(400, "부마스터는 %d명까지 둘 수 있습니다." % config.GUILD_MAX_SUBS)
    db.run("UPDATE guild_member SET role=? WHERE user_id=?", (role, target))
    name = _name_of(target)
    _say(m["guild_id"], "%s 님이 %s가 되었습니다." % (name, ROLE_KR[role])
         if role == "sub" else "%s 님이 부마스터에서 내려왔습니다." % name, now)
    _changed(m["guild_id"])
    return {"ok": True, "message": "%s 님을 %s(으)로 바꿨습니다." % (name, ROLE_KR[role])}


def transfer(uid, target, now=None):
    """마스터 자리를 넘긴다. 넘긴 사람은 부마스터가 된다 (자리가 없으면 길드원)."""
    m = _need_manager(uid, master_only=True)
    t = member(target)
    if not t or t["guild_id"] != m["guild_id"] or target == uid:
        raise HTTPException(404, "우리 길드원이 아닙니다.")
    gid = m["guild_id"]
    db.run("UPDATE guild_member SET role='master' WHERE user_id=?", (target,))
    subs = db.q1("SELECT COUNT(*) c FROM guild_member WHERE guild_id=? AND role='sub'", (gid,))["c"]
    db.run("UPDATE guild_member SET role=? WHERE user_id=?",
           ("sub" if subs < config.GUILD_MAX_SUBS else "member", uid))
    db.run("UPDATE guild SET master_id=? WHERE id=?", (target, gid))
    _say(gid, "%s 님이 새 길드 마스터가 되었습니다." % _name_of(target), now)
    _changed(gid)
    return {"ok": True, "message": "%s 님에게 길드 마스터를 넘겼습니다." % _name_of(target)}


def disband(uid):
    m = _need_manager(uid, master_only=True)
    g = guild_of(m["guild_id"])
    _drop(m["guild_id"])
    return {"ok": True, "message": "%s 길드를 해산했습니다." % g["name"]}


def update(uid, intro=None, mode=None, now=None):
    """소개와 가입 방식. 마스터만 바꾼다."""
    m = _need_manager(uid, master_only=True)
    gid = m["guild_id"]
    g = guild_of(gid)
    said = []
    if intro is not None:
        text = _clean_text(intro, INTRO_MAX)
        if text != g["intro"]:
            db.run("UPDATE guild SET intro=? WHERE id=?", (text, gid))
            said.append("소개")
    if mode is not None and _clean_mode(mode) != g["join_mode"]:
        db.run("UPDATE guild SET join_mode=? WHERE id=?", (mode, gid))
        said.append("가입 방식")
        if mode == "open":
            # 자유 가입으로 바꾸면 기다리던 사람은 그냥 들어올 수 있다 - 신청을 비운다.
            db.run("DELETE FROM guild_request WHERE guild_id=?", (gid,))
    if said:
        _changed(gid)
    return {"ok": True, "message": ("%s을(를) 바꿨습니다." % "·".join(said)) if said
            else "바뀐 것이 없습니다."}


def on_user_deleted(uid, now=None):
    """회원탈퇴 직전에 부른다. 마스터였다면 자리를 넘기고, 혼자였다면 길드를 없앤다."""
    m = member(uid)
    if not m:
        return
    gid = m["guild_id"]
    if m["role"] == "master":
        heir = db.q1("SELECT user_id FROM guild_member WHERE guild_id=? AND user_id<>?"
                     " ORDER BY CASE role WHEN 'sub' THEN 0 ELSE 1 END, joined_at, user_id"
                     " LIMIT 1", (gid, uid))
        if not heir:
            _drop(gid)
            return
        db.run("UPDATE guild_member SET role='master' WHERE user_id=?", (heir["user_id"],))
        db.run("UPDATE guild SET master_id=? WHERE id=?", (heir["user_id"], gid))
        _say(gid, "%s 님이 새 길드 마스터가 되었습니다." % _name_of(heir["user_id"]), now)
    db.run("DELETE FROM guild_member WHERE user_id=?", (uid,))
    _say(gid, "%s 님이 길드를 나갔습니다." % _name_of(uid), now)
    _changed(gid)


# ---------------------------------------------------------------- 채팅
_SENT = {}                  # {uid: [보낸 시각 ...]} - 도배 막기 (메모리. 재시작하면 풀린다)


def _too_fast(uid):
    now = time.time()
    got = [t for t in _SENT.get(uid, []) if now - t < 60]
    if len(got) >= config.GUILD_CHAT_PER_MIN:
        _SENT[uid] = got
        return True
    got.append(now)
    _SENT[uid] = got
    if len(_SENT) > 500:
        for k in [k for k, v in _SENT.items() if not v or now - v[-1] > 300]:
            _SENT.pop(k, None)
    return False


def _stamp(gid):
    """채팅 말고 길드에 바뀐 것이 있나를 가리는 값 (사람 수·신청 수·점수·소개·가입 방식).

    화면은 2초마다 채팅만 물어보는데, 이 값이 달라지면 길드 화면 전체를 다시 받는다.
    """
    g = guild_of(gid)
    if not g:
        return ""
    n = _count(gid)
    r = db.q1("SELECT COUNT(*) c FROM guild_request WHERE guild_id=?", (gid,))["c"]
    intro = zlib.crc32((g["intro"] or "").encode("utf-8"))
    return "%d.%d.%d.%x.%s" % (n, r, g["points"], intro, g["join_mode"])


def chat(uid, after=0, now=None):
    """after 번 뒤의 줄. after 가 0 이면 마지막 CHAT_FIRST 줄.

    **내가 들어온 뒤의 줄만 준다** (1.10.1). 새로 가입한 사람이 그 전에 길드원끼리 나눈
    말을 거슬러 읽을 수 없다 - '○○ 님이 들어왔습니다' 알림 줄부터 보인다. 나갔다가 다시
    들어오면 다시 들어온 때부터다.
    """
    m = member(uid)
    if not m:
        return {"guild": None, "messages": [], "last": 0}
    gid = m["guild_id"]
    since = m["joined_at"] or ""
    after = max(0, int(after or 0))
    if after:
        rows = db.q("SELECT * FROM guild_chat WHERE guild_id=? AND id>? AND at>=?"
                    " ORDER BY id LIMIT ?", (gid, after, since, CHAT_STEP))
    else:
        rows = list(reversed(db.q(
            "SELECT * FROM guild_chat WHERE guild_id=? AND at>=? ORDER BY id DESC LIMIT ?",
            (gid, since, CHAT_FIRST))))
    out = [{"id": r["id"], "userId": r["user_id"], "name": r["name"], "body": r["body"],
            "at": r["at"], "ago": _ago(r["at"], now), "mine": r["user_id"] == uid,
            "system": r["user_id"] is None} for r in rows]
    return {"guild": gid, "messages": out, "last": out[-1]["id"] if out else after,
            "stamp": _stamp(gid)}


def chat_send(uid, body, now=None):
    m = _need(uid)
    text = " ".join((body or "").split())
    if not text:
        raise HTTPException(400, "보낼 말을 적어 주세요.")
    if len(text) > config.GUILD_CHAT_LEN:
        raise HTTPException(400, "한 번에 %d자까지 보낼 수 있습니다." % config.GUILD_CHAT_LEN)
    if _too_fast(uid):
        raise HTTPException(429, "너무 빨리 보내고 있습니다. 잠시 후에 해 주세요.")
    gid = m["guild_id"]
    name, at = _name_of(uid), _iso(now)
    cur = db.run("INSERT INTO guild_chat (guild_id, user_id, name, body, at) VALUES (?,?,?,?,?)",
                 (gid, uid, name, text, at))
    mid = cur.lastrowid
    _emit("guild", gid, {"t": "chat", "m": _line(mid, uid, name, text, at)})
    if mid % 50 == 0:                       # 가끔 옛 줄을 치운다
        db.run("DELETE FROM guild_chat WHERE guild_id=? AND id <= ?",
               (gid, mid - config.GUILD_CHAT_KEEP))
    return {"ok": True, "id": mid}


# ---------------------------------------------------------------- 일일 미션
def _day_points(gid, day):
    """그날 길드가 모은 점수와 사람마다의 점수."""
    by = {}
    for r in db.q("SELECT user_id, key FROM guild_mission WHERE guild_id=? AND day=? AND done=1",
                  (gid, day)):
        spec = MISSION.get(r["key"])
        if spec:
            by[r["user_id"]] = by.get(r["user_id"], 0) + spec[3]
    return sum(by.values()), by


def note(uid, key, n=1, now=None):
    """미션 하나를 n 만큼 했다. 길드에 없으면 아무 일도 없다."""
    spec = MISSION.get(key)
    if not spec or n <= 0:
        return
    m = member(uid)
    if not m:
        return
    gid, day = m["guild_id"], today(now)
    _key, _name, goal, pts = spec
    row = db.q1("SELECT n, done FROM guild_mission WHERE guild_id=? AND day=? AND user_id=?"
                " AND key=?", (gid, day, uid, key))
    if row and row["done"]:
        return
    have = min(goal, (row["n"] if row else 0) + n)
    done = 1 if have >= goal else 0
    db.run("INSERT INTO guild_mission (guild_id, day, user_id, key, n, done) VALUES (?,?,?,?,?,?)"
           " ON CONFLICT(guild_id, day, user_id, key) DO UPDATE SET n=excluded.n,"
           " done=excluded.done", (gid, day, uid, key, have, done))
    if not done:
        return
    db.run("UPDATE guild_member SET points = points + ? WHERE user_id=?", (pts, uid))
    db.run("UPDATE guild SET points = points + ? WHERE id=?", (pts, gid))
    total, _by = _day_points(gid, day)
    for i, (need, _balls, _coin) in enumerate(TIERS):
        if total - pts < need <= total:
            _say(gid, "오늘의 길드 미션 %d단계 달성! (길드 점수 %d) 미션 칸에서 보상을 받으세요."
                 % (i + 1, total), now)
    _changed(gid)                           # 다른 길드원의 미션 칸도 따라 오른다


def note_safe(uid, key, n=1):
    """게임의 다른 곳(잡기·관장·랜덤 배틀)이 부른다. **여기서 난 오류로 그 일이 깨지면 안 된다.**"""
    try:
        note(uid, key, n)
    except Exception as e:                                  # noqa: BLE001
        try:
            from . import errors
            errors.record("HOOK", "guild.note:%s" % key, e)
        except Exception:                                   # noqa: BLE001
            pass


def _reward_text(balls, coins):
    bits = []
    if balls:
        bits.append("몬스터볼 %d개" % balls)
    if coins:
        bits.append("길드 코인 %d개" % coins)
    return " · ".join(bits)


def missions(uid, now=None, m=None):
    """미션 칸에 그릴 것. 길드에 없으면 None."""
    m = m or member(uid)
    if not m:
        return None
    gid, day = m["guild_id"], today(now)
    # 줄(Row)은 dict 가 아닐 수 있다 (로컬 sqlite 는 sqlite3.Row 다) - 값을 꺼내 담는다.
    mine = dict((r["key"], (int(r["n"] or 0), bool(r["done"]))) for r in db.q(
        "SELECT key, n, done FROM guild_mission WHERE guild_id=? AND day=? AND user_id=?",
        (gid, day, uid)))
    total, by = _day_points(gid, day)
    got = set(r["tier"] for r in db.q(
        "SELECT tier FROM guild_claim WHERE user_id=? AND day=?", (uid, day)))
    my = by.get(uid, 0)
    return {
        "day": day, "resetIn": reset_in(now), "myPoints": my, "myMax": DAY_MAX,
        "guildPoints": total, "guildMax": TIERS[-1][0],
        "missions": [{"key": k, "name": name, "goal": goal, "points": pts,
                      "n": min(goal, mine.get(k, (0, False))[0]),
                      "done": mine.get(k, (0, False))[1]}
                     for k, name, goal, pts in MISSIONS],
        "tiers": [{"tier": i + 1, "need": need, "balls": balls, "coin": coins,
                   "reward": _reward_text(balls, coins),
                   "reached": total >= need, "claimed": (i + 1) in got,
                   # 한 점이라도 보탠 사람만 받는다
                   "canClaim": total >= need and (i + 1) not in got and my > 0}
                  for i, (need, balls, coins) in enumerate(TIERS)],
        "byUser": by,
    }


def _coin_add(uid, n):
    db.run("INSERT INTO guild_user (user_id, coin) VALUES (?,?)"
           " ON CONFLICT(user_id) DO UPDATE SET coin = coin + ?", (uid, n, n))


def claim(uid, tier, now=None):
    m = _need(uid)
    tier = int(tier)
    if not (1 <= tier <= len(TIERS)):
        raise HTTPException(404, "그런 보상 단계가 없습니다.")
    gid, day = m["guild_id"], today(now)
    need, balls, coins = TIERS[tier - 1]
    total, by = _day_points(gid, day)
    if total < need:
        raise HTTPException(400, "아직 길드 점수가 모자랍니다. (%d / %d)" % (total, need))
    if by.get(uid, 0) <= 0:
        raise HTTPException(400, "오늘 미션을 하나라도 한 길드원만 받을 수 있습니다.")
    try:
        db.run("INSERT INTO guild_claim (user_id, day, tier, at) VALUES (?,?,?,?)",
               (uid, day, tier, _iso(now)))
    except Exception as e:                                  # noqa: BLE001
        if _dup(e):
            raise HTTPException(409, "이미 받은 보상입니다.")
        raise
    if balls:
        items.bag_add(uid, items.BALL_ITEM, balls)
    if coins:
        _coin_add(uid, coins)
    return {"ok": True, "message": "%d단계 보상을 받았습니다: %s" % (tier, _reward_text(balls, coins)),
            "coin": coin(uid)}


# ---------------------------------------------------------------- 코인 상점
def coin_price(item_id):
    """그 물건의 코인 값. 코인 상점에 없는 것이면 0."""
    it = items.get(item_id)
    if not it or items.buy_price(it["id"]) <= 0:
        return 0
    if it.get("cat") not in SHOP_CATS and it["id"] not in SHOP_ITEMS:
        return 0
    return max(1, int(math.ceil(items.buy_price(it["id"]) / float(config.GUILD_COIN_WON))))


def shop(uid):
    rows = []
    for it in items.public_list():
        price = coin_price(it["id"])
        if price:
            rows.append(dict(it, coin=price))
    rows.sort(key=lambda x: (0 if x["cat"] == "ball" else 1, x["coin"], x["kr"]))
    r = db.q1("SELECT balls FROM users WHERE id=?", (uid,))
    return {"items": rows, "coin": coin(uid), "bag": items.bag_get(uid, r["balls"] if r else 0),
            "inGuild": member(uid) is not None}


def buy(uid, item_id, count=1):
    """길드 코인으로 산다. 코인은 사람이 갖는 것이라 길드를 나온 뒤에도 쓸 수 있다."""
    it = items.get(item_id)
    price = coin_price(it["id"]) if it else 0
    if not price:
        raise HTTPException(404, "코인 상점에 없는 물건입니다.")
    n = max(1, min(BUY_MAX, int(count or 1)))
    total = price * n
    cur = db.run("UPDATE guild_user SET coin = coin - ? WHERE user_id=? AND coin >= ?",
                 (total, uid, total))
    if cur.rowcount <= 0:
        raise HTTPException(400, "길드 코인이 모자랍니다. (%d개 필요)" % total)
    items.bag_add(uid, it["id"], n)
    return {"ok": True, "spent": total, "coin": coin(uid),
            "message": "%s %d개를 길드 코인 %d개로 샀습니다!" % (it["kr"], n, total)}


# ---------------------------------------------------------------- 길드원 프로필
def peer(uid, other, now=None):
    """같은 길드에 있는 사람의 길드 쪽 정보. 같은 길드가 아니면 403.

    프로필 창(GET /api/guild/members/{uid}/profile)이 쓴다. 마이페이지에 보이는 것
    (포켓몬·도감·관장·시즌 기록)을 **같은 길드원에게만** 보여 주려는 것이라, 여기서 먼저 가린다.
    """
    m = _need(uid)
    o = member(other)
    if not o or o["guild_id"] != m["guild_id"]:
        raise HTTPException(403, "같은 길드원의 프로필만 볼 수 있습니다.")
    seen, on = social._online_map([other]).get(other, (None, False))
    _total, by = _day_points(m["guild_id"], today(now))
    return {"role": o["role"], "roleKr": ROLE_KR.get(o["role"], o["role"]),
            "joinedAt": o["joined_at"], "points": int(o["points"] or 0),
            "today": by.get(other, 0), "online": bool(on), "lastSeenAgo": _ago(seen, now),
            "me": other == uid}


# ---------------------------------------------------------------- 화면 하나에 줄 것
def me_card(uid):
    """/api/me 에 얹는 것 (1.10.1): 내 길드 번호와, **남이 쓴** 가장 최근 채팅 줄의 번호.

    화면은 이 번호가 '본 데까지' 보다 크면 길드 탭에 점을 찍는다. 1.10.0 에서는 길드 탭을
    한 번 열어야(웹소켓이 붙어야) 점이 찍혀서, 프로그램을 켜고 다른 탭만 보던 사람은
    채팅이 온 줄 몰랐다. 길드가 없으면 None. 알림 줄(가입·미션)과 내가 쓴 줄은 안 친다.
    """
    m = member(uid)
    if not m:
        return None
    # (guild_id, id) 색인을 뒤에서부터 훑어 처음 맞는 줄에서 멈춘다
    # 들어오기 전의 줄은 내가 볼 수 없는 줄이다 (chat) - 안 읽은 것으로도 치지 않는다.
    r = db.q1("SELECT id FROM guild_chat WHERE guild_id=? AND user_id IS NOT NULL AND user_id<>?"
              " AND at>=? ORDER BY id DESC LIMIT 1", (m["guild_id"], uid, m["joined_at"] or ""))
    return {"id": m["guild_id"], "chat": int(r["id"]) if r else 0}


def state(uid, now=None):
    """길드 탭을 열 때 한 번에 받는 것. 길드가 없으면 만들기·찾기에 쓸 것만."""
    u = db.q1("SELECT money FROM users WHERE id=?", (uid,))
    base = {"me": uid, "coin": coin(uid), "money": u["money"] if u else 0,
            "createCost": config.GUILD_CREATE_COST, "max": config.GUILD_MAX_MEMBERS,
            "rejoinHours": config.GUILD_REJOIN_HOURS, "cooldown": cooldown(uid, now),
            "limits": {"name": [NAME_MIN, NAME_MAX], "intro": INTRO_MAX,
                       "chat": config.GUILD_CHAT_LEN, "subs": config.GUILD_MAX_SUBS}}
    m = member(uid)
    if not m:
        pend = db.q("SELECT r.guild_id, r.created_at, g.name FROM guild_request r"
                    " JOIN guild g ON g.id=r.guild_id WHERE r.user_id=? ORDER BY r.created_at",
                    (uid,))
        base.update({"guild": None, "role": None,
                     "pending": [{"guildId": r["guild_id"], "name": r["name"],
                                  "ago": _ago(r["created_at"], now)} for r in pend]})
        return base
    note(uid, "attend", now=now)            # 길드 화면을 열었다 = 출석
    gid = m["guild_id"]
    g = guild_of(gid)
    rows = db.q("SELECT m.user_id, m.role, m.joined_at, m.points, u.username"
                " FROM guild_member m JOIN users u ON u.id=m.user_id WHERE m.guild_id=?", (gid,))
    ids = [r["user_id"] for r in rows]
    deco = season.deco_map(ids)
    online = social._online_map(ids)
    ms = missions(uid, now, m)
    by = ms.pop("byUser")
    order = {"master": 0, "sub": 1, "member": 2}
    members = []
    for r in rows:
        seen, on = online.get(r["user_id"], (None, False))
        d = deco.get(r["user_id"], {})
        members.append({
            "id": r["user_id"], "name": r["username"], "role": r["role"],
            "roleKr": ROLE_KR.get(r["role"], r["role"]), "online": bool(on),
            "lastSeenAgo": _ago(seen, now), "joinedAt": r["joined_at"],
            "points": int(r["points"] or 0), "today": by.get(r["user_id"], 0),
            "title": d.get("title"), "frameColor": d.get("frameColor"),
            "tier": d.get("tier"), "tierKr": d.get("tierKr"), "ranked": d.get("ranked"),
            "rp": d.get("rp"), "me": r["user_id"] == uid})
    members.sort(key=lambda x: (order.get(x["role"], 9), -x["today"], -x["points"], x["name"]))
    reqs = []
    if m["role"] in ("master", "sub"):
        rr = db.q("SELECT r.user_id, r.message, r.created_at, u.username FROM guild_request r"
                  " JOIN users u ON u.id=r.user_id WHERE r.guild_id=? ORDER BY r.created_at",
                  (gid,))
        rd = season.deco_map([r["user_id"] for r in rr])
        reqs = [{"id": r["user_id"], "name": r["username"], "message": r["message"],
                 "ago": _ago(r["created_at"], now),
                 "tierKr": rd.get(r["user_id"], {}).get("tierKr"),
                 "tier": rd.get(r["user_id"], {}).get("tier"),
                 "ranked": rd.get(r["user_id"], {}).get("ranked"),
                 "title": rd.get(r["user_id"], {}).get("title")} for r in rr]
    last = db.q1("SELECT MAX(id) x FROM guild_chat WHERE guild_id=?", (gid,))
    base.update({
        "guild": _guild_public(g, n=len(rows)), "role": m["role"],
        "roleKr": ROLE_KR.get(m["role"], m["role"]),
        "members": members, "requests": reqs, "mission": ms, "pending": [],
        "chatLast": (last["x"] or 0) if last else 0, "stamp": _stamp(gid),
        "can": {"manage": m["role"] in ("master", "sub"), "master": m["role"] == "master"},
    })
    return base
