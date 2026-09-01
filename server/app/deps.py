# -*- coding: utf-8 -*-
"""여러 라우터가 같이 쓰는 것들 — 도감, 로그인 확인, 응답 꾸미기.

main.py 에 두면 battle_routes 가 main 을 import 하고 main 이 다시
battle_routes 를 import 하는 순환이 생겨서 따로 뺐다.
"""
import json
import random

from fastapi import Header, HTTPException, Request

from common import pokelogic as P

from . import auth, config, db, evolution

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
    auth.touch_session(token, auth.client_ip(request), sess["last_seen"])
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


# ---------------------------------------------------------------- 성장
MAX_MOVES = 4


def _learn(sp, moves, before, after):
    """구간에서 배우는 기술을 넣는다.

    본가는 네 개가 차면 '어떤 기술을 잊을까요?' 를 물어본다. 여기서는
    바탕화면에서 자동으로 싸우는 중이라 창을 띄울 수 없어서 가장 오래된
    것부터 밀어낸다. 대신 **무엇을 잊었는지 같이 돌려준다** —
    말없이 사라지면 아끼던 기술이 없어진 걸 나중에야 알게 된다.
    """
    learned = []
    for mlv, mv in sp.get("moves", []):
        if before < mlv <= after and mv not in moves:
            learned.append(mv)
            moves.append(mv)
    kept = moves[-MAX_MOVES:]
    forgot = [m for m in moves[:-MAX_MOVES]] if len(moves) > MAX_MOVES else []
    return kept, learned, forgot


def grant_exp(uid, mon_id, amount, hour=None):
    """경험치를 주고 레벨업 · 기술습득 · 진화까지 한 번에 처리한다.

    예전에는 이 코드가 battle_routes 와 main 두 군데에 복사돼 있었다.
    진화를 붙이면서 한쪽만 고치면 조용히 어긋나므로 여기로 합쳤다.
    """
    d = dex()
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (mon_id, uid))
    if not r or amount <= 0:
        return None
    sp = d.get(r["species"])
    if not sp:
        return None
    curve = sp.get("growth", "medium")
    before = r["level"]
    exp = min(r["exp"] + int(amount), P.exp_for_level(curve, P.LEVEL_MAX))
    lv = P.level_from_exp(curve, exp)
    moves = json.loads(r["moves"])
    learned = []
    forgot = []
    if lv > before:
        moves, learned, forgot = _learn(sp, moves, before, lv)
    db.run("UPDATE pokemon SET exp=?, level=?, moves=? WHERE id=?",
           (exp, lv, json.dumps(moves), mon_id))

    out = {
        "id": mon_id,
        "name": r["nickname"] or sp["kr"],
        "gained": int(amount),
        "level": lv,
        "levelBefore": before,
        "leveledUp": lv > before,
        "learned": [d.move_name(m) for m in learned],
        "forgot": [d.move_name(m) for m in forgot],
    }
    if lv > before:
        ev = try_evolve(uid, mon_id, hour)
        if ev:
            out["evolve"] = ev
    return out


def set_level(uid, mon_id, level, hour=None):
    """레벨을 직접 맞춘다 (이상한사탕). 진화 판정까지 같이 한다."""
    d = dex()
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (mon_id, uid))
    if not r:
        return None
    sp = d.get(r["species"])
    if not sp:
        return None
    curve = sp.get("growth", "medium")
    before = r["level"]
    lv = max(1, min(P.LEVEL_MAX, int(level)))
    exp = P.exp_for_level(curve, lv)
    moves, learned, forgot = _learn(sp, json.loads(r["moves"]), before, lv)
    db.run("UPDATE pokemon SET exp=?, level=?, moves=? WHERE id=?",
           (exp, lv, json.dumps(moves), mon_id))
    out = {"id": mon_id, "level": lv, "levelBefore": before,
           "leveledUp": lv > before,
           "learned": [d.move_name(m) for m in learned],
           "forgot": [d.move_name(m) for m in forgot]}
    if lv > before:
        ev = try_evolve(uid, mon_id, hour)
        if ev:
            out["evolve"] = ev
    return out


def try_evolve(uid, mon_id, hour=None):
    """조건이 되면 바로 진화시킨다. 진화했으면 알림 내용을 돌려준다."""
    if not config.EVOLVE_AUTO:
        return None
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (mon_id, uid))
    if not r:
        return None
    mon = db.row_to_mon(r)
    d = dex()
    b = evolution.check_level(d, mon, hour)
    if not b:
        return None
    before = mon["species"]
    evolution.apply(uid, mon, b, d, "")
    return evolution.public(d, before, b["to"])
