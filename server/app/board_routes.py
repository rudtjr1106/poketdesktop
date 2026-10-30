# -*- coding: utf-8 -*-
"""게시판 API (1.8.0).

    GET    /api/board?kind=all|notice|free&page=1   목록 한 쪽
    GET    /api/board/{id}                          글과 댓글
    POST   /api/board                               글 쓰기 (공지는 운영자만)
    PUT    /api/board/{id}                          내 글 고치기
    DELETE /api/board/{id}                          글 지우기 (쓴 사람·운영자)
    POST   /api/board/{id}/comments                 댓글·답글
    DELETE /api/board/comments/{cid}                댓글 지우기

1.9.0:

    GET    /api/board?...&q=말                      찾기 (제목·내용·쓴 사람)
    POST   /api/board/{id}/like                     좋아요 누르기·취소
    GET    /api/board/notify                        내 알림 목록
    GET    /api/board/mine?what=posts&page=1        내 활동 한 쪽 (마이페이지: 알림·내 글·내 댓글)
    POST   /api/board/notify/seen                   알림을 다 본 것으로

버전 2:

    POST   /api/board/images                        이미지 하나 올리기 {data: base64} -> {id, w, h, fmt, frames}
    GET    /api/board/images/{iid}                  이미지 파일 (붙은 글이 살아 있을 때 · 안 붙었으면 올린 사람만)
    POST/PUT /api/board 의 images: [번호...]         글에 붙일 이미지 (PUT 에서 빼면 그대로 둔다)

창을 열었을 때만 부른다 - 폴링은 없다. 새 공지·패치노트와 안 본 알림은
/api/me 에 실려 간다 (board.me_card).
"""
import base64
import binascii
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from . import board, deps

router = APIRouter()


class PostIn(BaseModel):
    kind: str = "free"
    title: str = ""
    body: str = ""
    images: Optional[List[int]] = None        # 버전 2. 없으면(옛 앱) 고칠 때 그림을 그대로 둔다


class ImageIn(BaseModel):
    data: str = ""                            # base64


class CommentIn(BaseModel):
    body: str = ""
    parent: int = 0            # 답글이면 그 댓글의 id


def _run(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/api/board")
def listing(kind: str = "all", page: int = 1, q: str = "", ctx=Depends(deps.current)):
    return board.listing(ctx["user"], kind, page, q=q)


# **notify 도 {pid} 보다 먼저 건다** (comments/{cid} 와 같은 이유).
@router.get("/api/board/notify")
def notifications(ctx=Depends(deps.current)):
    return board.notifications(ctx["user"]["id"])


@router.get("/api/board/mine")
def mine(what: str = "posts", page: int = 1, ctx=Depends(deps.current)):
    return board.mine_page(ctx["user"]["id"], (what or "posts").lower(), page)


@router.post("/api/board/notify/seen")
def notify_seen(ctx=Depends(deps.current)):
    board.notify_seen(ctx["user"]["id"])
    return board.notifications(ctx["user"]["id"])


@router.post("/api/board")
def create(body: PostIn, ctx=Depends(deps.current)):
    pid = _run(board.create, ctx["user"], (body.kind or "free").lower(),
               body.title, body.body, images=body.images)
    return board.detail(ctx["user"], pid)


# **images 도 {pid} 보다 먼저 건다** (comments/{cid} 와 같은 이유).
@router.post("/api/board/images")
def upload_image(body: ImageIn, ctx=Depends(deps.current)):
    data = body.data or ""
    if len(data) > board.IMG_BYTES_MAX * 4 // 3 + 16:
        raise HTTPException(413, "이미지는 한 장에 %dMB 까지 올릴 수 있습니다." % (board.IMG_BYTES_MAX // (1024 * 1024)))
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "이미지를 읽지 못했습니다.")
    try:
        return _run(board.upload_image, ctx["user"], raw)
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@router.get("/api/board/images/{iid}")
def image(iid: int, ctx=Depends(deps.current)):
    path, mime = _run(board.image_file, ctx["user"], iid)
    with open(path, "rb") as f:
        data = f.read()
    # 번호마다 그림이 바뀌지 않는다 - 앱이 오래 들고 있어도 된다
    return Response(content=data, media_type=mime, headers={"Cache-Control": "private, max-age=604800"})


# **comments/{cid} 를 {pid} 보다 먼저 건다.** 뒤에 걸면 'comments' 가 글 번호
# 자리에 들어가 422 가 난다.
@router.delete("/api/board/comments/{cid}")
def remove_comment(cid: int, ctx=Depends(deps.current)):
    pid = _run(board.remove_comment, ctx["user"], cid)
    return _run(board.detail, ctx["user"], pid)


@router.get("/api/board/{pid}")
def detail(pid: int, ctx=Depends(deps.current)):
    return _run(board.detail, ctx["user"], pid)


@router.put("/api/board/{pid}")
def edit(pid: int, body: PostIn, ctx=Depends(deps.current)):
    _run(board.edit, ctx["user"], pid, body.title, body.body, images=body.images)
    return board.detail(ctx["user"], pid)


@router.delete("/api/board/{pid}")
def remove(pid: int, ctx=Depends(deps.current)):
    _run(board.remove, ctx["user"], pid)
    return {"ok": True}


@router.post("/api/board/{pid}/like")
def like(pid: int, ctx=Depends(deps.current)):
    _run(board.like, ctx["user"], pid)
    return _run(board.detail, ctx["user"], pid)


@router.post("/api/board/{pid}/comments")
def comment(pid: int, body: CommentIn, ctx=Depends(deps.current)):
    _run(board.comment, ctx["user"], pid, body.body, body.parent or None)
    return _run(board.detail, ctx["user"], pid)
