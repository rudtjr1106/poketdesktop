# -*- coding: utf-8 -*-
"""액션 배틀 (2.6.0) 의 길. 본체는 action.py, 판(소켓)은 action_ws.py.

    GET  /api/action                 내 판 · 받은 도전 -> {"match": M|null, "incoming": [M..]}
    GET  /api/action/can/{uid}       저 사람에게 지금 걸 수 있나 -> {"ok", "why"} (단추를 흐리게)
    POST /api/action/invite/{uid}    건다 -> {"match": M} (상대에게 ask)
    POST /api/action/{id}/answer     {"accept": bool} -> {"match": M}. 건 사람이 거절을 부르면 거두기
    POST /api/action/{id}/cancel     거둔다 -> {"match": M}. 받은 사람이 부르면 거절
    POST /api/action/{id}/ticket     한 번 쓰는 입장권 -> {"ticket", "path"}. 앱이 서버 주소 + path 로 창을 띄운다
    GET  /action/play                웹 화면 (index.html). 로그인 없음 - 입장권이 주소 조각(#)으로 온다
    GET  /action/static/{path}       웹 화면의 js · css (main.py 가 static_files() 를 건다)

M = {"id", "state", "foe": {"id", "name"}, "mine", "result", "reason", "created"} (action.public).
틀리면: 없는 판 404 · 남의 판 403 · 지금 안 되는 것 409 (까닭은 detail).

웹 화면은 고칠 때 앱을 다시 내지 않아도 되게 서버가 내보낸다 (도트 /api/anim 도 같은 출처에서 받는다).
늘 되묻게(no-cache) 둔다 - 바뀌지 않았으면 304 다.
"""
import mimetypes
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import action, config, deps

router = APIRouter()

# 웹 화면은 ES 모듈이다 - 브라우저는 모듈 스크립트의 종류를 엄격히 보고 (Caddy 는 nosniff 도 건다), 기계에 따라
# .js 가 text/plain 으로 잡히기도 한다 (윈도우 레지스트리 · mime.types 없는 이미지). 이 서버가 내보내는 것은 정해 둔다.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")


class AnswerIn(BaseModel):
    accept: bool = True


def _run(fn, *a):
    """action 의 예외를 HTTP 번호로: 없다 404 · 남의 것 403 · 지금 안 된다 409."""
    try:
        return fn(*a)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.get("/api/action")
def mine(ctx=Depends(deps.current)):
    action.expire_old()
    return action.state(ctx["user"]["id"])


@router.get("/api/action/can/{other}")
def can(other: int, ctx=Depends(deps.current)):
    why = action.can_invite(ctx["user"]["id"], other)
    return {"ok": why is None, "why": why or ""}


@router.post("/api/action/invite/{other}")
def invite(other: int, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    return {"match": action.public(_run(action.invite, uid, other), uid)}


@router.post("/api/action/{mid}/answer")
def answer(mid: int, body: AnswerIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    return {"match": action.public(_run(action.answer, uid, mid, bool(body.accept)), uid)}


@router.post("/api/action/{mid}/cancel")
def cancel(mid: int, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    return {"match": action.public(_run(action.cancel, uid, mid), uid)}


@router.post("/api/action/{mid}/ticket")
def ticket(mid: int, ctx=Depends(deps.current)):
    t, path = _run(action.ticket, ctx["user"]["id"], mid)
    return {"ticket": t, "path": path}


@router.get("/action/play")
def page():
    try:
        with open(os.path.join(config.ACTION_WEB, "index.html"), encoding="utf-8") as f:
            return HTMLResponse(f.read(), headers={"Cache-Control": "no-cache"})
    except OSError:
        raise HTTPException(404, "액션 배틀 화면을 찾을 수 없습니다.")


class _Static(StaticFiles):
    """웹 화면의 js · css. 늘 되묻게 둔다 - 서버를 올리면 고친 화면이 바로 간다."""

    def file_response(self, *a, **kw):
        resp = super().file_response(*a, **kw)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


def static_files():
    """main.py 가 /action/static 에 건다 (APIRouter 에는 mount 를 못 건다). 폴더가 없어도 서버는 뜬다 - 그때는 404."""
    return _Static(directory=config.ACTION_WEB, check_dir=False)
