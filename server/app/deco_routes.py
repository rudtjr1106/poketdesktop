# -*- coding: utf-8 -*-
"""꾸미기 (버전 2) 의 길. 규칙은 deco.py 와 common/deco.py 에 있다.

    GET  /api/deco           목록 · 가진 것 · 누가 무엇을 쓰고 있나 · 참가 묶음 선택권
    POST /api/deco/equip     {pokemonId, deco, on} - 끼우기 · 빼기 (장식 하나는 한 마리만)
    POST /api/deco/pick      {bundle} - 참가 묶음 선택권으로 묶음 하나 고르기
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from . import deco, deps

router = APIRouter()


class EquipIn(BaseModel):
    pokemonId: int = 0
    deco: str = ""
    on: bool = True


class PickIn(BaseModel):
    bundle: str = ""


@router.get("/api/deco")
def state(ctx=Depends(deps.current)):
    return deco.state(ctx["user"]["id"])


@router.post("/api/deco/equip")
def equip(body: EquipIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    worn = deco.equip(uid, body.pokemonId, (body.deco or "")[:32], bool(body.on))
    out = deco.state(uid)
    out["pokemonId"] = body.pokemonId
    out["deco"] = worn
    return out


@router.post("/api/deco/pick")
def pick(body: PickIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    got = deco.pick(uid, (body.bundle or "")[:32])
    out = deco.state(uid)
    out["got"] = got
    return out
