# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 (2.4.0) 의 길. 본체는 arche.py, 규칙은 common/arche.py.

    GET  /api/arche              장 · 일지 · 의식 · 전설 자리 · 지금 일어날 현상 (열린 장의 의식도 여기서 본다 - 60초 폴링)
    POST /api/arche/key          떠오른 말 {chapter, text, via} -> {ok, key?, new, message, state}  (시간당 20번, 넘으면 429)
    POST /api/arche/check        의식만 다시 본다 (열쇠 아이템을 쓴 직후 · 집중 세트가 끝난 직후) -> state
    POST /api/arche/battle       전설과의 판을 연다 {chapter, slot} - 관장 판 꼴 (진행은 /api/gym/battle/{id}/act, 볼은 kind=ball)
    GET  /arche/p/{slug}         숨은 페이지 (로그인 없음 - 브라우저로 연다). 이름은 [a-z0-9-]{4,40}, 파일은 운영 볼륨에만
    GET  /arche/img/{name}       숨은 페이지 · 게시글이 쓰는 그림 ([a-z0-9-]+.png)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from . import arche, deps

router = APIRouter()


class KeyIn(BaseModel):
    chapter: int = 0
    text: str = ""
    via: str = "type"


class BattleIn(BaseModel):
    chapter: int = 0
    slot: int = 0


@router.get("/api/arche")
def get_state(ctx=Depends(deps.current)):
    arche.ensure_posts()
    return arche.state(ctx["user"]["id"])


@router.post("/api/arche/key")
def post_key(body: KeyIn, request: Request, ctx=Depends(deps.current)):
    from . import auth
    return arche.submit_key(ctx["user"]["id"], body.chapter, body.text, body.via, ip=auth.client_ip(request))


@router.post("/api/arche/check")
def post_check(ctx=Depends(deps.current)):
    return arche.state(ctx["user"]["id"])


@router.post("/api/arche/battle")
def post_battle(body: BattleIn, ctx=Depends(deps.current)):
    return arche.start_battle(ctx["user"]["id"], body.chapter, body.slot)


@router.get("/arche/p/{slug}")
def page(slug: str):
    p = arche.page_path(slug)
    if not p:
        raise HTTPException(404, "페이지를 찾을 수 없습니다.")
    with open(p, encoding="utf-8") as f:
        return HTMLResponse(f.read(), headers={"Cache-Control": "no-cache"})


@router.get("/arche/img/{name}")
def image(name: str):
    p = arche.img_path(name)
    if not p:
        raise HTTPException(404, "그림을 찾을 수 없습니다.")
    with open(p, "rb") as f:
        return Response(f.read(), media_type="image/png", headers={"Cache-Control": "public, max-age=600"})
