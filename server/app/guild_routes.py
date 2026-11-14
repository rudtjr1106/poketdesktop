# -*- coding: utf-8 -*-
"""길드 라우트 (1.10.0).

    GET    /api/guild                       내 길드 화면에 쓸 것 전부 (없으면 만들기·찾기에 쓸 것)
    GET    /api/guild/list?q=&page=         길드 찾기
    POST   /api/guild                       만들기 (돈이 든다)
    DELETE /api/guild                       해산 (마스터)
    POST   /api/guild/settings              소개·가입 방식 (마스터)
    POST   /api/guild/leave                 나가기
    POST   /api/guild/{gid}/join            가입 (자유 가입이면 바로, 아니면 신청)
    DELETE /api/guild/{gid}/join            신청 거두기
    POST   /api/guild/requests/{uid}/accept 신청 받기      DELETE 는 돌려보내기
    POST   /api/guild/members/{uid}/kick    내보내기
    POST   /api/guild/members/{uid}/role    부마스터로 올리기·내리기
    POST   /api/guild/members/{uid}/master  마스터 넘기기
    GET    /api/guild/members/{uid}/profile 길드원 프로필 (마이페이지에 보이는 것 - 같은 길드원만)
    GET    /api/guild/chat?after=           채팅 (처음 열 때, 그리고 웹소켓이 끊겼을 때 2초마다)
    GET    /api/guild/chat?before=          그 번호 앞의 줄 (거슬러 올라가기. 일주일 치까지)
    POST   /api/guild/chat                  한 줄 보내기
    POST   /api/guild/mission/{tier}/claim  단계 보상 받기
    GET    /api/guild/shop                  코인 상점        POST /api/guild/shop/buy
    POST   /api/guild/flag                  길드 깃발 그리기 {"pixels"} (2.5.0 - 마스터·부마스터 + 길드 깃발을 가진 사람)
    DELETE /api/admin/guild/{gid}/flag      길드 깃발 내리기 (운영진)

**새 줄은 웹소켓(guild_ws.py 의 /ws/guild)이 밀어 준다.** 여기의 채팅 GET 은 처음 열 때
지난 줄을 받는 데 쓰고, 웹소켓이 막힌 망에서는 2초마다 묻는 예비 길이 된다. 그 응답에
'길드에 바뀐 것이 있나' 를 가리는 값(stamp)을 실어서, 폴링하는 화면은 그 값이 달라질
때만 전체를 다시 받는다.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import deps, guild, mypage

router = APIRouter()


class CreateIn(BaseModel):
    name: str = ""
    intro: str = ""
    mode: str = "open"


class SettingsIn(BaseModel):
    intro: str = None
    mode: str = None


class JoinIn(BaseModel):
    message: str = ""


class RoleIn(BaseModel):
    role: str = "member"


class ChatIn(BaseModel):
    body: str = ""


class BuyIn(BaseModel):
    item: str = ""
    count: int = 1


class FlagIn(BaseModel):
    pixels: str = ""        # common/flag.py 꼴 (24 x 24 = 576자). 빈 그림 = 깃발 내리기


def _uid(ctx):
    return ctx["user"]["id"]


@router.get("/api/guild")
def state(ctx=Depends(deps.current)):
    return guild.state(_uid(ctx))


@router.get("/api/guild/list")
def listing(q: str = "", page: int = 1, ctx=Depends(deps.current)):
    return guild.listing(_uid(ctx), q, page)


@router.post("/api/guild")
def create(body: CreateIn, ctx=Depends(deps.current)):
    return guild.create(_uid(ctx), body.name, body.intro, body.mode)


@router.delete("/api/guild")
def disband(ctx=Depends(deps.current)):
    return guild.disband(_uid(ctx))


@router.post("/api/guild/settings")
def settings(body: SettingsIn, ctx=Depends(deps.current)):
    return guild.update(_uid(ctx), body.intro, body.mode)


@router.post("/api/guild/leave")
def leave(ctx=Depends(deps.current)):
    return guild.leave(_uid(ctx))


# 고정 경로(/chat, /shop ...)를 {gid} 보다 **먼저** 건다. 순서가 바뀌면 "chat" 을
# 길드 번호로 읽으려다 422 가 난다.
@router.get("/api/guild/chat")
def chat(after: int = 0, before: int = 0, ctx=Depends(deps.current)):
    return guild.chat(_uid(ctx), after, before=before)


@router.post("/api/guild/chat")
def chat_send(body: ChatIn, ctx=Depends(deps.current)):
    return guild.chat_send(_uid(ctx), body.body)


@router.get("/api/guild/shop")
def shop(ctx=Depends(deps.current)):
    return guild.shop(_uid(ctx))


@router.post("/api/guild/shop/buy")
def buy(body: BuyIn, ctx=Depends(deps.current)):
    return guild.buy(_uid(ctx), body.item, body.count)


class SlotIn(BaseModel):
    count: int = 1          # 1 또는 10 (2.1.1 - 10회 뽑기)


@router.post("/api/guild/shop/slot")
def slot(body: Optional[SlotIn] = None, ctx=Depends(deps.current)):
    """랜덤 캡슐 (2.1.0, 서버 이름은 slot). 몸이 없거나 {} 이면 한 번 (2.1.0 앱), {"count": 10} 이면 열 번."""
    return guild.slot(_uid(ctx), count=(body.count if body else 1))


@router.post("/api/guild/flag")
def flag(body: FlagIn, ctx=Depends(deps.current)):
    """길드 깃발 그리기 (2.5.0). 돌려주는 것은 GET /api/guild 와 같은 꼴 + ok · message.
    576자보다 긴 그림은 set_flag 가 길드를 읽기 전에 400 으로 막는다."""
    return guild.set_flag(_uid(ctx), body.pixels)


@router.delete("/api/admin/guild/{gid}/flag")
def clear_flag(gid: int, ctx=Depends(deps.current)):
    """운영진이 길드 깃발을 내린다 (부적절한 그림). 그 길드 채팅에 알림."""
    return guild.clear_flag(_uid(ctx), gid)


@router.post("/api/guild/mission/{tier}/claim")
def claim(tier: int, ctx=Depends(deps.current)):
    return guild.claim(_uid(ctx), tier)


@router.post("/api/guild/requests/{target}/accept")
def accept(target: int, ctx=Depends(deps.current)):
    return guild.decide(_uid(ctx), target, True)


@router.delete("/api/guild/requests/{target}")
def reject(target: int, ctx=Depends(deps.current)):
    return guild.decide(_uid(ctx), target, False)


@router.post("/api/guild/members/{target}/kick")
def kick(target: int, ctx=Depends(deps.current)):
    return guild.kick(_uid(ctx), target)


@router.post("/api/guild/members/{target}/role")
def role(target: int, body: RoleIn, ctx=Depends(deps.current)):
    return guild.set_role(_uid(ctx), target, body.role)


@router.post("/api/guild/members/{target}/master")
def master(target: int, ctx=Depends(deps.current)):
    return guild.transfer(_uid(ctx), target)


@router.get("/api/guild/members/{target}/profile")
def profile(target: int, ctx=Depends(deps.current)):
    """길드원 프로필: 마이페이지에 보이는 것 중 남에게 보여 줘도 되는 부분 + 길드 쪽 정보."""
    g = guild.peer(_uid(ctx), target)       # 같은 길드가 아니면 여기서 403
    out = mypage.card(target, deps.dex())
    if out is None:
        raise HTTPException(404, "그런 트레이너가 없습니다.")
    out["guild"] = g
    return out


@router.post("/api/guild/{gid}/join")
def join(gid: int, body: JoinIn, ctx=Depends(deps.current)):
    return guild.join(_uid(ctx), gid, body.message)


@router.delete("/api/guild/{gid}/join")
def cancel(gid: int, ctx=Depends(deps.current)):
    return guild.cancel_request(_uid(ctx), gid)
