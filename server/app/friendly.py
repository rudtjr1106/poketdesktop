# -*- coding: utf-8 -*-
"""길드 친선전 (1.10.3) — 길드원끼리의 실시간 배틀을 쉽게 열고, 길드원이 구경한다.

    GET  /api/guild/friendly              상대를 구하는 사람들 · 진행 중인 판
    POST /api/guild/friendly/seek         '상대 구함' 을 켜고 끈다 {on}
    POST /api/guild/friendly/accept/{uid} 상대를 구하는 길드원의 것을 받는다 - 바로 시작
    POST /api/guild/friendly/ask/{uid}    접속 중인 길드원에게 직접 신청한다 (상대가 받아야 시작)

## 왜

실시간 배틀은 있는데 잘 안 쓰였다. 친구 목록에서 한 사람을 골라 신청하고 그 사람이 마침 받을
수 있어야 했고, 해도 둘만 봤다. 여기서는

  * **상대를 찾는 일을 한 번으로 줄인다.** '상대 구함' 을 켜 두면 길드원 누구나 눌러서 바로 싸운다.
  * **길드원이 구경한다.** 판이 넘어갈 때마다 그 모습을 길드 웹소켓으로 민다 - 화면은 그것을
    바탕화면 오른쪽 아래에서 도트로 튼다.
  * **채팅에서 한다.** 상대를 구하면 길드 채팅에 **카드** 한 장이 놓인다. 길드원은 그 카드의
    [배틀] 을 눌러 받고, 판이 열리면 같은 카드가 [관전] 으로 바뀌고, 끝나면 결과가 적힌다.

규칙은 실시간 배틀 그대로다 (레벨 50, 보상·점수 없음). 판 자체는 live.py 가 한다 - 여기는
'누가 상대를 구하나', '어느 판이 길드 것인가' 만 안다.

## 길드원끼리의 실시간 배틀은 전부 길드 것이다

친구 목록으로 열었든 여기서 열었든, **두 사람이 같은 길드면** 그 판은 길드원에게 보인다
(live.listeners 로 판이 열리는 것을 듣고 그때 길드를 본다).

## 채팅의 카드

카드는 채팅 줄 하나다 (guild_chat.card 에 모습을 JSON 으로 적는다). **줄을 새로 적지 않고 그
줄을 고친다** - 한 판에 채팅이 세 줄씩 밀리지 않게.

    {"k": "friendly", "s": "seek",   "a": {id, name}}                          상대 구함
    {"k": "friendly", "s": "fight",  "a": .., "b": {id, name}, "mid": 판}       진행 중
    {"k": "friendly", "s": "over",   "a": .., "b": .., "mid": 판, "result": a|b|draw|None}
    {"k": "friendly", "s": "closed", "a": ..}                                  그만뒀거나 시간이 지났다

카드가 '살아 있는지'(단추를 누를 수 있는지)는 화면이 **지금 모습(view)에 그 줄 번호가 있는지**로
정한다 - 서버가 다시 떠서 메모리를 잃어도 죽은 카드의 단추가 남지 않는다.
길드원끼리 친구 목록으로 연 판처럼 '상대 구함' 없이 열린 판은 그때 카드를 새로 놓는다.

## 들고 있는 것

상대를 구하는 사람과 진행 중인 판은 **메모리에** 둔다 (서버는 프로세스 하나다 - guild_ws 와 같은
전제). 서버가 다시 뜨면 '상대 구함' 은 꺼지고, 진행 중이던 판은 다음에 넘어갈 때 다시 잡힌다.
"""
import threading
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import db, deps, guild, live, pvp

router = APIRouter()

MAX_FIGHTS = 3              # 한 길드에서 동시에 여는 친선전 ('상대 구함' 을 받는 것만 막는다)
SEEK_SEC = 180              # '상대 구함' 은 이만큼 지나면 저절로 꺼진다
SAY_EVERY = 60              # 같은 사람의 카드를 채팅에 새로 놓기까지 (그 안에 다시 구하면 놓았던 카드를 되살린다)
SWEEP_SEC = 15

_lock = threading.RLock()
_seek = {}                  # {길드: {사람: {"name", "until", "card"(채팅 줄 번호)}}}
_fights = {}                # {길드: {판: {"a", "b", "fight"(마지막 겉모습), "card", "who"({쪽: {id, name}})}}}
_said = {}                  # {사람: (길드, 놓은 카드의 줄 번호, 놓은 때)} - 그만뒀다가 금방 다시 구할 때 되살릴 카드
_swept = {}                 # {길드: 마지막으로 판들을 살핀 때}


def reset():
    """들고 있던 것을 다 비운다 (검사용)."""
    with _lock:
        _seek.clear()
        _fights.clear()
        _said.clear()
        _swept.clear()


def _gid(uid):
    m = guild.member(uid)
    return m["guild_id"] if m else None


def _name(uid):
    r = db.q1("SELECT username FROM users WHERE id=?", (uid,))
    return r["username"] if r else "?"


def _scene(fight):
    """판의 '장면' 번호. 이것이 같으면 구경꾼에게 새로 보여 줄 것이 없다."""
    return (fight.get("turn"), fight.get("step"), bool(fight.get("over")))


def full_text():
    return "길드 친선전이 이미 %d판 진행 중입니다. 잠시 후에 다시 해 주세요." % MAX_FIGHTS


# ---------------------------------------------------------------- 채팅의 카드
def _who(uid, name=None):
    return {"id": uid, "name": name if name is not None else _name(uid)}


def _card(state, a, b=None, mid=None, result=None):
    c = {"k": "friendly", "s": state, "a": a}
    if b is not None:
        c["b"] = b
    if mid is not None:
        c["mid"] = mid
    if state == "over":
        c["result"] = result if result in ("a", "b", "draw") else None
    return c


def seek_text(a):
    return "%s 님이 친선전 상대를 구합니다." % a["name"]


def fight_text(a, b):
    return "%s 님과 %s 님의 친선전이 열렸습니다." % (a["name"], b["name"])


def over_text(a, b, result):
    """끝난 판 한 줄. (카드를 모르는 옛 화면은 이 글을 본다)"""
    if result in ("a", "b"):
        return "%s 님과 %s 님의 친선전 - %s 님 승리" % (a["name"], b["name"], (a if result == "a" else b)["name"])
    if result == "draw":
        return "%s 님과 %s 님의 친선전 - 무승부" % (a["name"], b["name"])
    return "%s 님과 %s 님의 친선전이 끝났습니다." % (a["name"], b["name"])


def _close(gid, s):
    """'상대 구함' 이 꺼졌다 (그만뒀다 / 시간이 지났다) - 그 카드를 닫는다."""
    if s and s.get("card"):
        guild.card_set(gid, s["card"], _card("closed", _who(s["uid"], s["name"])))


def _expire(gid, now):
    """시간이 지난 '상대 구함' 을 걷고 그 카드를 닫는다. 걷은 것이 있으면 길드원 화면에도 알린다.

    따로 도는 시계는 없다 - 누가 물어볼 때(view) 본다. 화면들은 남은 시간이 다 되면 한 번 물어 온다.
    """
    with _lock:
        seek = _seek.get(gid) or {}
        gone = [seek.pop(u) for u in [u for u, s in seek.items() if now > s["until"]]]
    for s in gone:
        _close(gid, s)
    if gone:
        _push(gid, now)


def view(gid, now=None):
    """그 길드의 친선전 모습: 상대를 구하는 사람들, 진행 중인 판들."""
    now = time.monotonic() if now is None else now
    _expire(gid, now)
    with _lock:
        seek = _seek.get(gid) or {}
        seeking = [{"id": uid, "name": s["name"], "left": max(0, int(s["until"] - now)), "card": s.get("card")}
                   for uid, s in sorted(seek.items(), key=lambda kv: kv[1]["until"])]
        fights = [f["fight"] for f in (_fights.get(gid) or {}).values() if f.get("fight")]
    return {"seeking": seeking, "fights": fights, "limit": MAX_FIGHTS}


def _push(gid, now=None):
    """길드원 화면에 지금 모습을 민다."""
    guild._emit("guild", gid, dict(view(gid, now), t="friendly"))


def count(gid):
    with _lock:
        return len(_fights.get(gid) or {})


# ---------------------------------------------------------------- 상대 구함
def seek(uid, on, now=None):
    """'상대 구함' 을 켜거나 끈다. 지금 모습을 돌려준다."""
    gid = _gid(uid)
    if gid is None:
        raise LookupError("길드에 들어 있지 않습니다.")
    now = time.monotonic() if now is None else now
    if on:
        if live.my_match(uid):
            raise ValueError("이미 진행 중인 실시간 배틀이 있습니다.")
        if not pvp.ranked_team(uid):
            raise ValueError("데리고 다니는 포켓몬이 없습니다.")
    name = _name(uid)
    me = _who(uid, name)
    with _lock:
        mine = _seek.setdefault(gid, {})
        had = mine.get(uid)
        gone = None
        if not on:
            gone = mine.pop(uid, None)
        elif had:
            had["until"] = now + SEEK_SEC            # 이미 구하는 중이다 - 시간만 다시 센다
        else:
            # 카드를 놓는다. 방금 그만뒀다가 다시 구하는 것이면 **놓았던 카드를 되살린다** -
            # 켰다 껐다 하는 것으로 채팅이 카드로 도배되지 않게.
            old = _said.get(uid)
            again = old is not None and old[0] == gid and now - old[2] < SAY_EVERY
            if again:
                line = old[1]
                guild.card_set(gid, line, _card("seek", me), seek_text(me))
            else:
                line = guild._say(gid, seek_text(me), card=_card("seek", me))
                _said[uid] = (gid, line, now)
            mine[uid] = {"uid": uid, "name": name, "until": now + SEEK_SEC, "card": line}
    _close(gid, gone)
    _push(gid, now)
    return view(gid, now)


def accept(uid, other, now=None):
    """상대를 구하는 길드원(other)의 것을 받는다. 그 자리에서 판이 열린다 (건 쪽이 other 다)."""
    gid = _gid(uid)
    if gid is None:
        raise LookupError("길드에 들어 있지 않습니다.")
    if other == uid:
        raise ValueError("자기 자신과는 싸울 수 없습니다.")
    now = time.monotonic() if now is None else now
    _sweep(gid, now)
    _expire(gid, now)
    with _lock:
        got = (_seek.get(gid) or {}).get(other)
        gone = None
        if got and _gid(other) != gid:
            gone, got = (_seek.get(gid) or {}).pop(other, None), None     # 그사이 길드를 나갔다
        full = len(_fights.get(gid) or {}) >= MAX_FIGHTS
    _close(gid, gone)
    if not got:
        raise ValueError("그 길드원은 지금 상대를 구하고 있지 않습니다.")
    if full:
        raise ValueError(full_text())
    # 판이 열리면 live 가 on_live 를 부른다 - 거기서 두 사람의 '상대 구함' 을 걷고, 건 사람의
    # 카드를 '진행 중' 으로 바꾼다.
    row = live.open_direct(other, uid)       # 안 되면 ValueError (이미 배틀 중, 팀이 없다 ...)
    with _lock:                              # (on_live 가 걷었을 것이다 - 남았으면 여기서 걷는다)
        left = [(_seek.get(gid) or {}).pop(who, None) for who in (other, uid)]
    for s in left:
        _close(gid, s)
    # 판이 열린 것은 live 가 on_live 로 알려 줬다 (길드원에게 나갔다). 건 사람의 화면에는
    # '배틀 창을 띄우라' 고 따로 알린다 - 그쪽은 기다리고 있었을 뿐 아무것도 누르지 않았다.
    guild._emit("user", other, {"t": "live"})
    _push(gid, now)
    return row


def ask(uid, other):
    """접속 중인 길드원에게 직접 신청한다. 평소의 실시간 배틀 초대다 - 상대가 받아야 시작한다."""
    gid = _gid(uid)
    if gid is None or _gid(other) != gid:
        raise LookupError("같은 길드원에게만 신청할 수 있습니다.")
    row = live.invite(uid, other)            # 안 되면 ValueError
    guild._emit("user", other, {"t": "live"})    # 상대 화면이 바로 물어보게 (안 그러면 다음 동기화까지 모른다)
    return row


# ---------------------------------------------------------------- 판이 바뀔 때 (구경)
def on_live(row):
    """실시간 배틀의 판이 바뀌었다 (live.listeners). 길드원끼리의 판이면 길드원에게 민다."""
    if not row:
        return
    mid, state = row["id"], row["state"]
    started = False
    with _lock:                              # (보고 넣는 것을 한 번에 - 두 사람의 요청이 겹쳐도 카드는 하나다)
        hit = [gid for gid, fs in _fights.items() if mid in fs]
        if not hit:
            if state != "fighting":
                return
            ga, gb = _gid(row["a_id"]), _gid(row["b_id"])
            if ga is None or ga != gb:
                return                       # 길드원끼리의 판이 아니다
            who = {"a": _who(row["a_id"]), "b": _who(row["b_id"])}
            # 두 사람이 구하던 것은 걷는다. 그 카드가 있으면 그것이 이 판의 카드가 된다
            # (건 사람의 것 먼저). 없으면 - 친구 목록이나 직접 신청으로 열었다 - 새로 놓는다.
            was = [s for s in ((_seek.get(ga) or {}).pop(u, None) for u in (row["a_id"], row["b_id"]))
                   if s and s.get("card")]
            for u in (row["a_id"], row["b_id"]):
                _said.pop(u, None)           # 이 카드는 이제 판의 것이다 - 되살리지 않는다
            card, text = _card("fight", who["a"], who["b"], mid), fight_text(who["a"], who["b"])
            if was:
                line = was[0]["card"]
                guild.card_set(ga, line, card, text)
            else:
                line = guild._say(ga, text, card=card)
            for s in was[1:]:
                _close(ga, s)                # 둘 다 구하고 있었다 - 남는 카드는 닫는다
            _fights.setdefault(ga, {})[mid] = {"a": row["a_id"], "b": row["b_id"], "fight": None,
                                               "card": line, "who": who}
            hit, started = [ga], True
    for gid in hit:
        fight = live.spectate(row)
        if fight is None and state == "done":
            fight = {"id": mid, "over": True, "result": row["result"], "events": []}
        if fight is None:
            continue
        over = bool(fight.get("over"))
        with _lock:
            f = (_fights.get(gid) or {}).get(mid)
            if f is None:
                continue
            fight["card"] = f.get("card")    # 화면이 채팅의 어느 카드가 이 판인지 안다
            same = bool(f.get("fight")) and _scene(f["fight"]) == _scene(fight)
            f["fight"] = fight
            if over:
                del _fights[gid][mid]
        if over and f.get("card"):
            a, b = f["who"]["a"], f["who"]["b"]
            result = row["result"] if state == "done" else fight.get("result")
            guild.card_set(gid, f["card"], _card("over", a, b, mid, result), over_text(a, b, result))
        # 판은 한쪽이 다음 기술을 고르기만 해도 저장된다 - 장면은 그대로다. 그걸 또 보내면
        # 구경하는 화면이 같은 줄(○○ 의 몸통박치기!)을 두 번 튼다.
        if not same:
            guild._emit("guild", gid, {"t": "friendly_fight", "fight": fight})
        if started or over:
            _push(gid)


if on_live not in live.listeners:
    live.listeners.append(on_live)


def _sweep(gid, now=None, force=False):
    """그 길드의 판들을 한 번 살핀다 (많아야 SWEEP_SEC 에 한 번).

    판은 싸우는 두 사람의 화면이 물어볼 때 넘어간다. 둘 다 자리를 뜨면 아무도 넘기지 않아서
    '진행 중' 이 영영 남는다. 제한 시간이 지난 턴은 여기서 넘기고, 끝난 판은 치운다.
    """
    now = time.monotonic() if now is None else now
    with _lock:
        if not force and now - _swept.get(gid, -10 ** 9) < SWEEP_SEC:
            return
        _swept[gid] = now
        mids = list(_fights.get(gid) or {})
    if not mids:
        return
    live.expire_old()
    for mid in mids:
        row = live.get(mid)
        if row and row["state"] == "fighting":
            row = live.tick(row) or row          # 넘어가면 live 가 on_live 를 부른다
        if not row or row["state"] == "done":
            on_live(row or {"id": mid, "state": "done", "result": "expired", "data": None})


def state(uid):
    gid = _gid(uid)
    if gid is None:
        raise LookupError("길드에 들어 있지 않습니다.")
    _sweep(gid)
    return view(gid)


# ---------------------------------------------------------------- 경로
class SeekIn(BaseModel):
    on: bool = True


def _run(fn, *a):
    try:
        return fn(*a)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.get("/api/guild/friendly")
def friendly_state(ctx=Depends(deps.current)):
    return _run(state, ctx["user"]["id"])


@router.post("/api/guild/friendly/seek")
def friendly_seek(body: SeekIn, ctx=Depends(deps.current)):
    return _run(seek, ctx["user"]["id"], bool(body.on))


@router.post("/api/guild/friendly/accept/{other}")
def friendly_accept(other: int, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    row = _run(accept, uid, other)
    return {"match": live.public(row, uid)}


@router.post("/api/guild/friendly/ask/{other}")
def friendly_ask(other: int, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    row = _run(ask, uid, other)
    return {"match": live.public(row, uid)}
