# -*- coding: utf-8 -*-
"""전설·환상 레이드 API.

    GET  /api/raid                 일정 · 다음 회차 보스 · 내 방
    GET  /api/raid/room            지금 들어가 있는 방 (라운드 폴링도 이것)
    POST /api/raid/join            모집 중인 방에 들어간다 (code 로 친구 방)
    POST /api/raid/create          친구끼리 할 방을 만든다 (코드가 나온다)
    POST /api/raid/start           방장이 먼저 시작한다 (코드 방, 3명 이상)
    POST /api/raid/act             이번 라운드에 할 것 (기술 / 교체)
    POST /api/raid/leave           나간다
    POST /api/raid/seen            결과를 봤다
    GET  /api/raid/history         내 레이드 기록

## 라운드는 요청이 돌린다

서버에 따로 도는 시계가 없다. 마감이 지났는지는 **요청이 올 때** 본다
(raid.tick). 레이드 창은 열려 있는 동안 1~2초마다 방을 물어보므로, 누가
창을 닫고 사라져도 남은 사람의 폴링이 라운드를 넘긴다.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import db, deps, pvp, raid

router = APIRouter()


class JoinIn(BaseModel):
    code: str = ""


class LeaveIn(BaseModel):
    # 대기실에서 누른 나가기. 그 사이에 판이 열렸으면 409 로 돌려보낸다 (raid.leave).
    # 1.9.2 까지의 클라는 이 칸을 안 보낸다 - 예전처럼 어느 쪽이든 나간다.
    lobby: bool = False


class ActIn(BaseModel):
    kind: str = "move"           # move / switch
    move: str = ""
    slot: int = -1
    mega: bool = False           # 이 라운드에 메가진화 (시즌 3)


def _name(ctx):
    return ctx["user"].get("username") or "?"


def _mine(uid, tick=True):
    """지금 볼 방. 끝난 판도 결과를 볼 때까지는 같이 본다 (raid.recent_room).

    tick 은 '마감이 지났으면 라운드를 돌린다' 는 뜻이다. 서버에 따로 도는
    시계가 없어서, 창이 열려 있는 사람의 폴링이 판을 밀어 준다.
    """
    row = raid.recent_room(uid)
    if not row:
        return None
    if tick and row["state"] != "done":
        row = raid.tick(row) or row
    return row


@router.get("/api/raid")
def overview(ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    out = raid.schedule()
    row = _mine(uid)
    out["room"] = raid.public(row, uid) if row else None
    played = raid.played_today(uid)
    out["playedToday"] = bool(played)
    # 나가는 팀(전설·환상 한 마리) 수와 데리고 다니는 전부. 둘이 다르면 화면이
    # '왜 못 들어가는지' 를 전설 제한으로 설명한다 (시즌 3).
    team, benched = raid.party_split(uid)
    out["party"] = len(team)
    out["partyAll"] = len(team) + len(benched)
    out["benchNote"] = pvp.bench_note(benched)
    # 아직 결과를 못 본 판. /api/me 가 이걸 보고 알린다.
    out["unseen"] = unseen(uid)
    return out


def unseen(uid, now=None):
    """끝났는데 아직 화면에 안 알린 판의 수."""
    # 끝난 지 오래된 판은 세지 않는다 (raid.recent_room 과 같은 기준).
    r = db.q1("SELECT COUNT(*) c FROM raid_member m JOIN raid_room r ON r.id=m.room_id"
              " WHERE m.user_id=? AND m.seen=0 AND r.state='done'"
              " AND r.result IN ('won','lost','timeout') AND r.updated_at >= ?",
              (uid, raid._result_cut(now)))
    return (r["c"] if r else 0) or 0


@router.get("/api/raid/room")
def my_room(ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    row = _mine(uid)
    if not row:
        raise HTTPException(404, "들어가 있는 레이드 방이 없습니다.")
    return raid.public(row, uid)


@router.post("/api/raid/join")
def join(body: JoinIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    try:
        row = raid.join(uid, _name(ctx), (body.code or "").strip() or None)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    row = raid.tick(row) or row
    return raid.public(row, uid)


@router.post("/api/raid/create")
def create(ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    try:
        row = raid.create_code(uid, _name(ctx))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return raid.public(row, uid)


@router.post("/api/raid/start")
def start(ctx=Depends(deps.current)):
    """**방장이 눌러야 시작한다.** 정각이 됐다고 저절로 열리지 않는다.

    모인 사람끼리 이야기하고 준비를 마친 뒤 시작할 수 있어야 해서다.
    """
    uid = ctx["user"]["id"]
    row = raid.my_room(uid)
    if not row:
        raise HTTPException(404, "들어가 있는 레이드 방이 없습니다.")
    if row["host"] != uid:
        raise HTTPException(403, "방장만 시작할 수 있습니다.")
    ok, why = raid.can_start(row)
    if not ok:
        raise HTTPException(409, why)
    return raid.public(raid.begin(row), uid)


@router.post("/api/raid/act")
def act(body: ActIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    row = _mine(uid)
    if not row:
        raise HTTPException(404, "진행 중인 레이드가 없습니다.")
    kind = (body.kind or "").lower()
    if kind not in ("move", "switch"):
        raise HTTPException(400, "무엇을 할지 알 수 없습니다.")
    value = body.move if kind == "move" else int(body.slot)
    try:
        row = raid.choose(uid, kind, value, mega=bool(body.mega))
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return raid.public(row, uid)


@router.post("/api/raid/leave")
def leave(body: Optional[LeaveIn] = None, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    try:
        row = raid.leave(uid, lobby_only=bool(body and body.lobby))
    except ValueError as e:
        raise HTTPException(409, str(e))
    if not row:
        raise HTTPException(404, "들어가 있는 레이드 방이 없습니다.")
    return {"ok": True}


@router.post("/api/raid/seen")
def seen(ctx=Depends(deps.current)):
    """끝난 판의 결과를 화면에 알렸다. 이제 안 알린다."""
    uid = ctx["user"]["id"]
    db.run("UPDATE raid_member SET seen=1 WHERE user_id=? AND seen=0 AND room_id IN"
           " (SELECT id FROM raid_room WHERE state='done')", (uid,))
    return {"ok": True}


@router.get("/api/raid/past")
def past(limit: int = 10, ctx=Depends(deps.current)):
    """지난 회차 — 내가 안 간 판도 본다. 어떤 전설이 나왔고 누가 잡았는지."""
    return {"raids": raid.past(limit)}


@router.get("/api/raid/history")
def history(limit: int = 10, ctx=Depends(deps.current)):
    return {"raids": raid.history(ctx["user"]["id"], max(1, min(50, limit)))}
