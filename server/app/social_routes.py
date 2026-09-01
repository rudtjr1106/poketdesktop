# -*- coding: utf-8 -*-
"""친구 라우트.

찾기·신청·수락·삭제·차단·프로필. 전부 창을 열었을 때만 부르는 것들이라
폴링이 붙지 않는다 — Turso 는 왕복 하나가 곧 비용이라, 항상 도는 폴링은
꼭 필요한 하나(다음 단계의 대전 우편함)로 몰기로 했다.
"""
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import deps, social

router = APIRouter()


class NameIn(BaseModel):
    username: str = ""


# 찾기 도배 막기.
#
# login_fail 처럼 DB 에 두지 않고 메모리에 둔다. 서버가 재시작하면 풀리지만
# 여기서 막는 것은 '남의 닉네임을 마구 넣어 보는 것' 뿐이고, 찾기는 이미
# **정확히 일치할 때만** 걸린다. 앞글자로 훑을 수가 없으므로 풀린다고
# 잃는 게 없다. 반대로 이걸 DB 에 두면 찾을 때마다 쓰기가 한 번씩 는다.
_HITS = {}


def _too_fast(uid):
    now = time.time()
    got = [t for t in _HITS.get(uid, []) if now - t < 60]
    got.append(now)
    _HITS[uid] = got
    if len(_HITS) > 500:                    # 오래된 사람 정리
        for k in [k for k, v in _HITS.items() if not v or now - v[-1] > 300]:
            _HITS.pop(k, None)
    return len(got) > social.SEARCH_PER_MIN


@router.get("/api/friends")
def friends(ctx=Depends(deps.current)):
    return social.listing(ctx["user"]["id"])


@router.get("/api/friends/search")
def search(name: str = "", ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    if _too_fast(uid):
        raise HTTPException(429, "너무 자주 찾고 있습니다. 잠시 후에 해주세요.")
    return social.find(uid, name)


@router.post("/api/friends/request")
def request(body: NameIn, ctx=Depends(deps.current)):
    return social.request(ctx["user"]["id"], body.username)


@router.post("/api/friends/{other}/accept")
def accept(other: int, ctx=Depends(deps.current)):
    return social.accept(ctx["user"]["id"], other)


@router.delete("/api/friends/{other}")
def remove(other: int, ctx=Depends(deps.current)):
    """거절 · 취소 · 삭제를 하나로 받는다."""
    return social.remove(ctx["user"]["id"], other)


@router.post("/api/friends/{other}/block")
def block(other: int, ctx=Depends(deps.current)):
    return social.block(ctx["user"]["id"], other)


@router.delete("/api/friends/{other}/block")
def unblock(other: int, ctx=Depends(deps.current)):
    return social.unblock(ctx["user"]["id"], other)


@router.get("/api/users/{other}/profile")
def profile(other: int, ctx=Depends(deps.current)):
    return social.profile(ctx["user"]["id"], other)
