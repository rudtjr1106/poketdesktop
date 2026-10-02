# -*- coding: utf-8 -*-
"""게시판 API (1.8.0).

    GET    /api/board?kind=all|notice|free&page=1   목록 한 쪽
    GET    /api/board/{id}                          글과 댓글
    POST   /api/board                               글 쓰기 (공지는 운영자만)
    PUT    /api/board/{id}                          내 글 고치기
    DELETE /api/board/{id}                          글 지우기 (쓴 사람·운영자)
    POST   /api/board/{id}/comments                 댓글·답글
    DELETE /api/board/comments/{cid}                댓글 지우기

창을 열었을 때만 부른다 - 폴링은 없다. 새 공지가 있는지는 /api/me 에
실려 가는 번호 하나로 안다 (board.me_card).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import board, deps

router = APIRouter()


class PostIn(BaseModel):
    kind: str = "free"
    title: str = ""
    body: str = ""


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
def listing(kind: str = "all", page: int = 1, ctx=Depends(deps.current)):
    return board.listing(ctx["user"], kind, page)


@router.post("/api/board")
def create(body: PostIn, ctx=Depends(deps.current)):
    pid = _run(board.create, ctx["user"], (body.kind or "free").lower(),
               body.title, body.body)
    return board.detail(ctx["user"], pid)


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
    _run(board.edit, ctx["user"], pid, body.title, body.body)
    return board.detail(ctx["user"], pid)


@router.delete("/api/board/{pid}")
def remove(pid: int, ctx=Depends(deps.current)):
    _run(board.remove, ctx["user"], pid)
    return {"ok": True}


@router.post("/api/board/{pid}/comments")
def comment(pid: int, body: CommentIn, ctx=Depends(deps.current)):
    _run(board.comment, ctx["user"], pid, body.body, body.parent or None)
    return _run(board.detail, ctx["user"], pid)
