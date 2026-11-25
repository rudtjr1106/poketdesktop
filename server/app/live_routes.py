# -*- coding: utf-8 -*-
"""실시간 1:1 배틀 API.

    GET  /api/live                  지금 내 판 (초대·진행·안 본 결과)
    POST /api/live/invite/{uid}     친구에게 실시간 배틀을 건다
    POST /api/live/{id}/answer      수락 / 거절 (건 사람이 부르면 취소)
    POST /api/live/act              이번 턴에 할 것 (기술 / 교체 / 기권 · 더블은 picks 로 두 마리 몫을 한 번에)
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
    mega: bool = False           # 이 턴에 메가진화 (시즌 3)
    z: bool = False              # 고른 기술을 Z기술로 (시즌 4)
    tera: bool = False           # 이 턴에 테라스탈 (2.5.0)
    # 더블배틀 (11/25): kind="picks" 로 두 마리 몫을 한 번에. [{pos, kind: move|switch, move, target, slot, mega, z, tera}]
    picks: list = None


def _mine(uid, tick=True):
    row = live.current(uid)
    if not row:
        return None
    if tick and row["state"] != "done":
        row = live.tick(row) or row
    return row


@router.get("/api/live")
def mine(ctx=Depends(deps.current), double: int = 0):
    """double=1: 이 앱은 더블배틀을 그릴 줄 안다 (11/25). 없으면 옛 앱 - 더블 판은 안 준다 (live.old_app)."""
    uid = ctx["user"]["id"]
    live.expire_old()
    row = _mine(uid)
    if row and live.fmt_of(row) == "double" and not double:
        row = live.old_app(row, uid)
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
    if kind not in ("move", "switch", "forfeit", "picks"):
        raise HTTPException(400, "무엇을 할지 알 수 없습니다.")
    value = body.move if kind == "move" else (
        int(body.slot) if kind == "switch" else (list(body.picks or []) if kind == "picks" else None))
    _mine(uid)                       # 마감이 지났으면 먼저 넘긴다
    try:
        row = live.act(uid, kind, value, mega=bool(body.mega), z=bool(body.z), tera=bool(body.tera))
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
