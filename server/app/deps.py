# -*- coding: utf-8 -*-
"""여러 라우터가 같이 쓰는 것들 — 도감, 로그인 확인, 응답 꾸미기.

main.py 에 두면 battle_routes 가 main 을 import 하고 main 이 다시
battle_routes 를 import 하는 순환이 생겨서 따로 뺐다.
"""
import random

from fastapi import Header, HTTPException, Request

from common import pokelogic as P

from . import auth, config, db

RNG = random.SystemRandom()

_DEX = None


def dex():
    global _DEX
    if _DEX is None:
        _DEX = P.Pokedex.load(config.POKEDEX_PATH)
    return _DEX


def current(request: Request, authorization: str = Header(default="")):
    """Bearer 토큰을 확인하고 사용자를 돌려준다."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "로그인이 필요합니다.")
    token = authorization[7:].strip()
    sess = auth.lookup_session(token)
    if not sess:
        raise HTTPException(401, "세션이 만료되었습니다. 다시 로그인해 주세요.")
    user = db.q1("SELECT * FROM users WHERE id=?", (sess["user_id"],))
    if not user:
        raise HTTPException(401, "계정을 찾을 수 없습니다.")
    auth.touch_session(token, auth.client_ip(request))
    return {"user": user, "session": sess, "token": token}


def decorate(mon):
    """포켓몬 한 마리에 도감 정보를 붙여서 내려보낸다."""
    d = dex()
    out = dict(mon)
    out["info"] = d.describe(mon)
    sp = d.get(mon["species"])
    if sp:
        out["num"] = sp["num"]
        out["gen"] = sp.get("gen")
    return out


def party_count(uid):
    return db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=? AND on_desktop=1",
                 (uid,))["c"]


def free_slot(uid, exclude=None):
    """비어 있는 파티 자리 번호. 자리가 없으면 None."""
    used = set(r["slot"] for r in db.q(
        "SELECT slot FROM pokemon WHERE user_id=? AND on_desktop=1 AND id IS NOT ?",
        (uid, exclude)))
    for i in range(config.MAX_PARTY):
        if i not in used:
            return i
    return None
