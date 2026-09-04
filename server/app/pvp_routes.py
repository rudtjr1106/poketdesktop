# -*- coding: utf-8 -*-
"""유저 배틀 조회 — 대전 다시보기, 전적, 순위표.

**여기에 전투를 진행시키는 라우트는 없다.** 판은 매칭이 성사되는 순간
서버가 통째로 계산해 끝내 놓는다(pvp.run_match). 그래서 클라이언트가
보낼 수 있는 전투 입력이 존재하지 않고, 속일 대상도 없다.

대전은 **비동기**다. 상대가 접속해 있지 않아도 그 사람의 지금 파티를
가져와 붙인다. 그래서 대기열도 도전장도 수락도 없다 - 누르면 그 자리에서
끝나고, 상대는 다음에 켤 때 결과를 본다.
"""
from fastapi import APIRouter, Depends, HTTPException

from . import deps, pvp, social

router = APIRouter()


def _fight(uid, other, kind):
    """실제로 붙인다. 규칙 확인 -> 계산 -> 횟수 기록."""
    why = pvp.can_fight(uid, other)
    if why:
        raise HTTPException(409, why)
    out = pvp.run_match(uid, other, kind=kind)
    pvp.note_fight(uid)
    # 내 쪽은 지금 봤으니 안 본 것으로 세지 않는다. 상대는 다음에 켤 때
    # 알림으로 받는다.
    pvp.mark_seen(uid, out["matchId"])
    return out


@router.post("/api/pvp/random")
def random_battle(ctx=Depends(deps.current)):
    """아무나 하나 골라 붙는다. 상대는 접속해 있지 않아도 된다.

    레벨대가 비슷한 사람부터 찾고, 없으면 넓혀 간다. 친구 몇 명이 하는
    서버라 '상대가 없습니다' 만 뜨는 것보다는 조금 기울어도 붙는 게 낫다.
    """
    uid = ctx["user"]["id"]
    # 내 쪽 조건을 먼저 본다. 상대까지 골라 놓고 막히면 애먼 사람의
    # 쿨다운만 태우게 된다.
    why = pvp.can_start(uid)
    if why:
        raise HTTPException(409, why)
    other = pvp.find_opponent(uid)
    if other is None:
        raise HTTPException(
            404, "지금 붙을 상대가 없습니다. 조금 뒤에 다시 해주세요.")
    return _fight(uid, other, "random")


@router.post("/api/pvp/challenge/{other}")
def challenge(other: int, ctx=Depends(deps.current)):
    """친구를 지목해서 붙는다. 상대의 수락을 기다리지 않는다."""
    uid = ctx["user"]["id"]
    if not social.is_friend(uid, other):
        raise HTTPException(403, "친구에게만 배틀을 걸 수 있습니다.")
    return _fight(uid, other, "friend")


@router.get("/api/pvp/pending")
def pending(ctx=Depends(deps.current)):
    """아직 안 본 대전. 켜자마자 한 번 보고, 그 뒤에는 sync 에 얹혀 온다."""
    uid = ctx["user"]["id"]
    return {"matches": pvp.unseen(uid), "fight": pvp.fight_status(uid)}


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


@router.delete("/api/pvp/records")
def clear_records(ctx=Depends(deps.current)):
    """전적을 통째로 지운다. 점수와 승패는 그대로 남는다."""
    uid = ctx["user"]["id"]
    return {"ok": True, "removed": pvp.clear_records(uid)}


@router.delete("/api/pvp/records/{rid}")
def clear_record(rid: int, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    if not pvp.clear_records(uid, rid):
        raise HTTPException(404, "그런 기록이 없습니다.")
    return {"ok": True, "removed": 1}


@router.get("/api/pvp/ranking")
def ranking(limit: int = 50, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    return {"ranking": pvp.ranking(max(1, min(100, limit)), uid),
            "me": pvp.summary(uid), "season": pvp.SEASON,
            "placement": pvp.PLACEMENT}
