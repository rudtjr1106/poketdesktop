# -*- coding: utf-8 -*-
"""낚시 (시즌 7) 의 길. 규칙은 fishing.py 에 있다.

    GET  /api/fish               카드 {open, state, ready, nibbleLeft, strikeLeft, bait, baitLeft, wait, wild, ballOptions}
    POST /api/fish/cast          {"bait": "ORANBERRY"|null} 찌를 던진다 -> 카드
    POST /api/fish/bite          앱이 지금 입질을 보여 줄 수 있다 -> 카드 (아직이면 state 가 그대로)
    POST /api/fish/hook          {"hour": h} 챔질 -> {result, card, (hooked 면) perfect, src, wild, ballOptions}
    POST /api/fish/reel          줄을 거둔다 (입질 전이면 미끼를 돌려준다) -> 카드
    GET  /api/fish/board?week=   주간 대물 순위 (this | last)

열리기 전(시즌 < FISH_FROM)에는 모두 404 - 앱은 카드가 없으면 연못을 안 띄운다 (낚시를 모르는 옛 서버와 같게).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import deps, fishing

router = APIRouter()


class CastIn(BaseModel):
    bait: Optional[str] = None


class HookIn(BaseModel):
    hour: int = -1          # 앱의 시각 - 다크볼처럼 밤을 보는 볼의 배율 (볼 목록)


def _gate():
    if not fishing.is_open():
        raise HTTPException(404, fishing.closed_text())


def _do(fn, *a, **k):
    _gate()
    try:
        return fn(*a, **k)
    except fishing.Refused as e:
        raise HTTPException(e.status, e.text)


@router.get("/api/fish")
def fish_card(ctx=Depends(deps.current)):
    return _do(fishing.card, ctx["user"]["id"], ctx["user"])


@router.post("/api/fish/cast")
def fish_cast(body: CastIn, ctx=Depends(deps.current)):
    return _do(fishing.cast, ctx["user"]["id"], body.bait)


@router.post("/api/fish/bite")
def fish_bite(ctx=Depends(deps.current)):
    return _do(fishing.bite, ctx["user"]["id"])


@router.post("/api/fish/hook")
def fish_hook(body: HookIn, ctx=Depends(deps.current)):
    return _do(fishing.hook, ctx["user"]["id"], ctx["user"], body.hour)


@router.post("/api/fish/reel")
def fish_reel(ctx=Depends(deps.current)):
    return _do(fishing.reel, ctx["user"]["id"])


@router.get("/api/fish/board")
def fish_board(week: str = "this", ctx=Depends(deps.current)):
    _gate()
    # 순위 창을 여는 사람이 있으면 그때도 정산을 챙긴다 (한 시간마다 도는 집안일이 늦을 때) - 여기서 터져도 순위는 보인다
    try:
        fishing.settle()
    except Exception as e:                                  # noqa: BLE001
        print("[fishing] 정산 실패: %r" % (e,))
    return fishing.board(ctx["user"]["id"], "last" if week == "last" else "this")
