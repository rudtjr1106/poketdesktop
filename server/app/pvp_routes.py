# -*- coding: utf-8 -*-
"""유저 배틀 조회 — 대전 다시보기, 전적, 순위표.

**여기에 전투를 진행시키는 라우트는 없다.** 판은 매칭이 성사되는 순간
서버가 통째로 계산해 끝내 놓는다(pvp.run_match). 그래서 클라이언트가
보낼 수 있는 전투 입력이 존재하지 않고, 속일 대상도 없다.

붙이는 순서상 매칭(대기열/도전장)은 다음 단계다. 지금은 계산된 판을
꺼내 보는 쪽만 있다.
"""
from fastapi import APIRouter, Depends, HTTPException

from . import deps, pvp

router = APIRouter()


@router.get("/api/pvp/match/{mid}")
def match(mid: int, ctx=Depends(deps.current)):
    """대전 한 판을 재생용으로 내려준다. 내가 낀 판만 볼 수 있다.

    로그는 a 시점으로 저장되어 있고, 부르는 사람이 b 면 여기서 뒤집어
    준다. 뒤집는 곳을 한 군데로 몰아야 화면마다 어긋나지 않는다.
    """
    out = pvp.match_view(ctx["user"]["id"], mid)
    if not out:
        raise HTTPException(404, "그런 대전이 없습니다.")
    return out


@router.post("/api/pvp/match/{mid}/seen")
def seen(mid: int, ctx=Depends(deps.current)):
    """다 봤다고 표시. 양쪽이 다 보면 나중에 로그를 치울 수 있다."""
    if not pvp.mark_seen(ctx["user"]["id"], mid):
        raise HTTPException(404, "그런 대전이 없습니다.")
    return {"ok": True}


@router.get("/api/pvp/records")
def records(limit: int = 30, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    return {"summary": pvp.summary(uid),
            "records": pvp.records(uid, max(1, min(100, limit)))}


@router.get("/api/pvp/ranking")
def ranking(limit: int = 50, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    return {"ranking": pvp.ranking(max(1, min(100, limit)), uid),
            "me": pvp.summary(uid)}
