# -*- coding: utf-8 -*-
"""유저 배틀 조회 — 대전 다시보기, 전적, 순위표.

**여기에 전투를 진행시키는 라우트는 없다.** 판은 매칭이 성사되는 순간
서버가 통째로 계산해 끝내 놓는다(pvp.run_match). 그래서 클라이언트가
보낼 수 있는 전투 입력이 존재하지 않고, 속일 대상도 없다.

대전은 **비동기**다. 상대가 접속해 있지 않아도 그 사람의 지금 파티를
가져와 붙인다. 그래서 대기열도 도전장도 수락도 없다 - 누르면 그 자리에서
끝나고, 상대는 다음에 켤 때 결과를 본다.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import config, db, deps, pvp, season, social

router = APIRouter()


def _fight(uid, other, kind):
    """실제로 붙인다. 규칙 확인 -> 계산 -> 횟수 기록."""
    why = pvp.can_fight(uid, other, kind)
    if why:
        raise HTTPException(409, why)
    out = pvp.run_match(uid, other, kind=kind)
    pvp.note_fight(uid, kind)          # 랜덤 배틀만 하루 상한을 쓴다
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
    why = pvp.can_start(uid, "random")
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
    me = pvp.summary(uid)
    d = season.deco(uid)
    me.update({"title": d.get("title"), "frame": d.get("frame"),
               "frameColor": d.get("frameColor")})
    return {"ranking": pvp.ranking(max(1, min(100, limit)), uid),
            "me": me, "season": pvp.SEASON,
            "placement": pvp.PLACEMENT,
            "rules": dict(season.rules_public(),
                          restrictedMax=pvp.RESTRICTED_MAX),
            # 지난 시즌 명예의 전당. 시즌 1 은 티어가 없던 시즌이라 순위만 있다.
            "hall": {"season": pvp.SEASON - 1,
                     "rows": season.hall(pvp.SEASON - 1)}}


# ---------------------------------------------------------------- 랭크 팀
class TeamIn(BaseModel):
    ids: List[int] = []


def _team_view(uid):
    source = pvp._ranked_source(uid)
    team, dropped = pvp.restrict(source)
    dex = deps.dex()
    return {"registered": bool(pvp.team_ids(uid)),
            # 고르는 창에는 제한 전의 팀을 준다 (등록한 그대로 보여야 한다).
            "ids": [m["id"] for m in source],
            "pokemon": [deps.decorate(m) for m in team],
            "levelCap": season.LEVEL_CAP,
            "maxParty": config.MAX_PARTY,
            # 전설·환상 제한. 창이 두 마리째를 미리 막는다 (서버도 막는다).
            "restrictedMax": pvp.RESTRICTED_MAX,
            "restrictedNums": sorted(dex.get(s)["num"] for s in pvp.restricted_species()
                                     if dex.get(s)),
            "restrictedDropped": dropped}


@router.get("/api/pvp/team")
def get_team(ctx=Depends(deps.current)):
    """랭크 팀. 등록하지 않았으면 바탕화면 파티가 그 자리에 온다."""
    return _team_view(ctx["user"]["id"])


@router.put("/api/pvp/team")
def put_team(body: TeamIn, ctx=Depends(deps.current)):
    """랭크 팀을 등록한다. 빈 목록이면 등록을 풀고 바탕화면 파티로 싸운다."""
    uid = ctx["user"]["id"]
    try:
        pvp.set_team(uid, body.ids or [])
    except ValueError as e:
        raise HTTPException(400, str(e) or "잘못된 팀입니다.")
    return _team_view(uid)


# ---------------------------------------------------------------- 칭호 · 명패
class EquipIn(BaseModel):
    title: Optional[str] = None
    frame: Optional[str] = None


def _rewards_view(uid):
    titles, frames = season.owned(uid)
    u = db.q1("SELECT title, frame FROM users WHERE id=?", (uid,))
    return {"titles": titles, "frames": frames,
            "equipped": {"title": u["title"] if u else None,
                         "frame": u["frame"] if u else None},
            "deco": season.deco(uid)}


@router.get("/api/rewards")
def rewards(ctx=Depends(deps.current)):
    return _rewards_view(ctx["user"]["id"])


@router.post("/api/rewards/equip")
def equip(body: EquipIn, ctx=Depends(deps.current)):
    """칭호·명패를 단다. 보내지 않은 칸은 그대로, 빈 글자는 뗀다."""
    uid = ctx["user"]["id"]
    try:
        season.equip(uid, title=body.title, frame=body.frame)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _rewards_view(uid)
