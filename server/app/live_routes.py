# -*- coding: utf-8 -*-
"""실시간 1:1 배틀 API.

    GET  /api/live                  지금 내 판 (초대·진행·안 본 결과)
    POST /api/live/invite/{uid}     친구에게 실시간 배틀을 건다
    POST /api/live/{id}/answer      수락 / 거절 (건 사람이 부르면 취소)
    POST /api/live/act              이번 턴에 할 것 (기술 / 교체 / 기권)
    POST /api/live/seen             결과를 봤다
    GET  /api/live/can/{uid}        저 친구에게 지금 걸 수 있나 (단추를 흐리게)

## 턴은 요청이 돌린다

서버에 따로 도는 시계가 없다. 제한 시간이 지났는지는 요청이 올 때 본다
(live.tick). 배틀 창이 열려 있는 동안 1~2초마다 물어보므로, 한쪽이 창을
닫아도 남은 쪽의 폴링이 턴을 넘긴다.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import deps, live

router = APIRouter()


class AnswerIn(BaseModel):
    accept: bool = True


class ActIn(BaseModel):
    kind: str = "move"           # move / switch / forfeit
    move: str = ""
    slot: int = -1


def _mine(uid, tick=True):
    row = live.current(uid)
    if not row:
        return None
    if tick and row["state"] != "done":
        row = live.tick(row) or row
    return row


@router.get("/api/live")
def mine(ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    live.expire_old()
    row = _mine(uid)
    return {"match": live.public(row, uid) if row else None,
            "unseen": live.unseen(uid)}


@router.get("/api/live/can/{other}")
def can(other: int, ctx=Depends(deps.current)):
    why = live.can_invite(ctx["user"]["id"], other)
    return {"ok": why is None, "why": why or ""}


@router.post("/api/live/invite/{other}")
def invite(other: int, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    try:
        row = live.invite(uid, other)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return live.public(row, uid)


@router.post("/api/live/{mid}/answer")
def answer(mid: int, body: AnswerIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    try:
        row = live.answer(uid, mid, bool(body.accept))
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return live.public(row, uid)


@router.post("/api/live/act")
def act(body: ActIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    kind = (body.kind or "").lower()
    if kind not in ("move", "switch", "forfeit"):
        raise HTTPException(400, "무엇을 할지 알 수 없습니다.")
    value = body.move if kind == "move" else (
        int(body.slot) if kind == "switch" else None)
    _mine(uid)                       # 마감이 지났으면 먼저 넘긴다
    try:
        row = live.act(uid, kind, value)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return live.public(row, uid)


@router.post("/api/live/seen")
def seen(ctx=Depends(deps.current)):
    live.mark_seen(ctx["user"]["id"])
    return {"ok": True}
