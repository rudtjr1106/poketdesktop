# -*- coding: utf-8 -*-
"""길드전 (시즌 4) 의 길. 규칙은 guild_war.py 에 있다.

    GET    /api/guild/war                 지금 단계, 내 팀, 순위표, 내 공격권, 길드원들
    POST   /api/guild/war/apply           참가 신청 (마스터·부마스터)   DELETE 로 취소
    POST   /api/guild/war/team            방어팀·공격팀 짜기 {kind: def/atk, ids: [...]}
    GET    /api/guild/war/map?have=요약값   지도에 칠할 것 (칸마다 주인, 길드마다 색·칸 수, 원형 지도 그림)
    GET    /api/guild/war/tile/{region}   칸 하나: 지키는 사람과 방어팀 미리보기, 우리 승수, 칠 수 있는지
    POST   /api/guild/war/attack          {region: 칸} - 관장 배틀 판이 열린다 (관장 배틀 창이 그대로 한다)
    POST   /api/guild/war/attacks         길드장: 공격 횟수 나누기 {plan: {사람: 횟수}}
    POST   /api/guild/war/guard           길드장: 길드원을 우리 칸에 배치 {region, userId}
    POST   /api/guild/war/joker           길드장: 그 칸을 지키는 길드원을 조커로 숨기기·풀기 {region, on} (시즌 5)
    GET    /api/guild/war/log             내 길드가 낀 판들
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import deps, guild_war

router = APIRouter()


class TeamIn(BaseModel):
    kind: str = "def"
    ids: list = []


class AttackIn(BaseModel):
    region: str = ""


class PlanIn(BaseModel):
    plan: dict = {}


class GuardIn(BaseModel):
    region: str = ""
    userId: int = 0


class JokerIn(BaseModel):
    region: str = ""
    on: bool = True


def _uid(ctx):
    return ctx["user"]["id"]


@router.get("/api/guild/war")
def state(ctx=Depends(deps.current)):
    return guild_war.state(_uid(ctx))


@router.post("/api/guild/war/apply")
def apply(ctx=Depends(deps.current)):
    guild_war.apply(_uid(ctx))
    return guild_war.state(_uid(ctx))


@router.delete("/api/guild/war/apply")
def withdraw(ctx=Depends(deps.current)):
    guild_war.withdraw(_uid(ctx))
    return guild_war.state(_uid(ctx))


@router.post("/api/guild/war/team")
def team(body: TeamIn, ctx=Depends(deps.current)):
    if len(body.ids or []) > 12:
        raise HTTPException(400, "한 번에 너무 많이 보냈습니다.")
    guild_war.set_team(_uid(ctx), (body.kind or "").lower(), body.ids)
    return guild_war.state(_uid(ctx))


@router.get("/api/guild/war/map")
def war_map(have: str = "", ctx=Depends(deps.current)):
    """have = 화면이 이미 가진 지도 그림의 요약값. 같으면 그림(geo)은 다시 안 싣는다 (30초마다 묻는다)."""
    return guild_war.map_view(_uid(ctx), have=have[:32] or None)


@router.get("/api/guild/war/tile/{region}")
def tile(region: str, ctx=Depends(deps.current)):
    return guild_war.tile_view(_uid(ctx), region[:16])


@router.post("/api/guild/war/attack")
def attack(body: AttackIn, ctx=Depends(deps.current)):
    return guild_war.attack(_uid(ctx), (body.region or "")[:16])


@router.post("/api/guild/war/attacks")
def attacks(body: PlanIn, ctx=Depends(deps.current)):
    if len(body.plan or {}) > 30:
        raise HTTPException(400, "한 번에 너무 많이 보냈습니다.")
    guild_war.set_attacks(_uid(ctx), body.plan)
    return guild_war.state(_uid(ctx))


@router.post("/api/guild/war/guard")
def guard(body: GuardIn, ctx=Depends(deps.current)):
    guild_war.place(_uid(ctx), body.userId, (body.region or "")[:16])
    return guild_war.tile_view(_uid(ctx), (body.region or "")[:16])


@router.post("/api/guild/war/joker")
def joker(body: JokerIn, ctx=Depends(deps.current)):
    guild_war.set_joker(_uid(ctx), (body.region or "")[:16], bool(body.on))
    return guild_war.tile_view(_uid(ctx), (body.region or "")[:16])


@router.get("/api/guild/war/log")
def log(ctx=Depends(deps.current)):
    return {"log": guild_war.log(_uid(ctx))}
