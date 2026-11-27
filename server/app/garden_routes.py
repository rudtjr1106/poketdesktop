# -*- coding: utf-8 -*-
"""열매 텃밭 (시즌 7) 의 길. 규칙은 garden.py 에 있다.

    GET  /api/garden                  카드 {open, pots[3], harvested, cap, nextIn, fedToday, friendWater}
    POST /api/garden/plant            {"slot": 0~2, "berry": "ORANBERRY"} 빈 화분에 심는다 -> 카드
    POST /api/garden/water            물이 필요한 화분 모두에 -> {watered, card}
    POST /api/garden/harvest          {"replant": true} 익은 화분을 모두 거둔다 -> {got, replanted, capped, card}
    POST /api/garden/pull             {"slot": 0~2} 화분을 비운다 (새싹이면 씨앗을 돌려준다) -> 카드 + refunded (돌려줬나 - 서버 시계로)
    POST /api/pokemon/{pid}/feed      {"avoid": 지금 미끼 | null, "hour": h} 열매 먹이기 -> {berry, kr, gain, happiness, evolve}

친구 물(POST /api/visit/water)은 놀러 가기 쪽에 있다 (visit.py - 손님 · 주인을 거기서 안다).
열리기 전(시즌 < GARDEN_FROM)에는 모두 404 - 앱은 카드가 없으면 화단을 안 띄우고 먹이 줄도 안 만든다.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import deps, garden

router = APIRouter()


class PlantIn(BaseModel):
    slot: int
    berry: str = ""


class SlotIn(BaseModel):
    slot: int


class HarvestIn(BaseModel):
    replant: bool = True


class FeedIn(BaseModel):
    avoid: Optional[str] = None     # 지금 낚시 미끼 - 그것은 빼고 고른다 (그것밖에 없으면 그것)
    hour: int = -1                  # 앱의 시각 - 이브이처럼 낮 · 밤을 보는 친밀 진화


def _gate():
    if not garden.is_open():
        raise HTTPException(404, garden.closed_text())


def _do(fn, *a, **k):
    _gate()
    try:
        return fn(*a, **k)
    except garden.Refused as e:
        raise HTTPException(e.status, e.text)


@router.get("/api/garden")
def garden_card(ctx=Depends(deps.current)):
    return _do(garden.card, ctx["user"]["id"])


@router.post("/api/garden/plant")
def garden_plant(body: PlantIn, ctx=Depends(deps.current)):
    return _do(garden.plant, ctx["user"]["id"], body.slot, body.berry)


@router.post("/api/garden/water")
def garden_water(ctx=Depends(deps.current)):
    return _do(garden.water, ctx["user"]["id"])


@router.post("/api/garden/harvest")
def garden_harvest(body: HarvestIn, ctx=Depends(deps.current)):
    return _do(garden.harvest, ctx["user"]["id"], body.replant)


@router.post("/api/garden/pull")
def garden_pull(body: SlotIn, ctx=Depends(deps.current)):
    return _do(garden.pull, ctx["user"]["id"], body.slot)


@router.post("/api/pokemon/{pid}/feed")
def feed_pokemon(pid: int, body: FeedIn, ctx=Depends(deps.current)):
    return _do(garden.feed, ctx["user"]["id"], pid, body.avoid, body.hour)
