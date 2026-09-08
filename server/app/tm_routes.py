# -*- coding: utf-8 -*-
"""기술머신 API · 기술 배우기.

기술머신은 **쓴다고 없어지지 않는다.** 그래서 여기에는 개수를 깎는
코드가 없다. 대신 두 가지를 꼭 서버에서 본다.

  1. 정말 가진 기술머신인가
  2. **그 종이 배울 수 있는 기술인가**

둘 다 클라이언트를 믿으면 안 된다. 안 그러면 아무 포켓몬에게 아무
기술이나 붙일 수 있다.

기다리는 기술(pending)도 여기서 푼다. 레벨업으로 배울 기술이 생겼는데
자리가 네 개 다 차 있으면, 배틀 중에는 물어볼 수가 없어서 적어만 두고
넘어간다. 사용자가 창에서 고르면 이쪽으로 온다.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common import korean

from . import db, deps, tms

router = APIRouter()

MAX_MOVES = 4


class TeachIn(BaseModel):
    no: int                  # 기술머신 번호
    pokemon: int
    forget: str = ""         # 잊을 기술 (네 개가 차 있을 때만 필요)


class LearnIn(BaseModel):
    pokemon: int
    move: str                # 기다리던 기술 중 하나
    forget: str = ""         # 빈 문자열이면 '안 배운다'
    skip: bool = False


def _mon(uid, pid):
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
    if not r:
        raise HTTPException(404, "그런 포켓몬이 없습니다.")
    return r


def _species_num(r):
    sp = deps.dex().get(r["species"])
    return (sp or {}).get("num"), sp


def _apply(r, moves, pending):
    db.run("UPDATE pokemon SET moves=?, pending=? WHERE id=?",
           (json.dumps(moves), json.dumps(pending), r["id"]))


def _pending_of(r):
    try:
        if "pending" in r.keys() and r["pending"]:
            return json.loads(r["pending"])
    except (AttributeError, TypeError, ValueError):
        pass
    return []


# ---------------------------------------------------------------- 목록
@router.get("/api/tms")
def my_tms(me=Depends(deps.current)):
    """가진 기술머신과, 안 가진 것까지 전부.

    안 가진 것도 같이 보낸다. 무엇을 더 모아야 하는지 보이는 편이
    모으는 재미가 있다. 358개뿐이라 한 번에 보내도 무겁지 않다.
    """
    uid = me["user"]["id"]
    got = tms.owned(uid)
    out = []
    for no, t in sorted(tms.all_tms().items()):
        out.append({
            "no": no, "move": t["move"], "kr": t["kr"],
            "type": t["type"], "cat": t["cat"],
            "label": tms.label(no),
            "have": no in got,
        })
    return {"tms": out, "haveCount": len(got), "total": tms.count()}


@router.get("/api/tms/{pid}")
def for_mon(pid: int, me=Depends(deps.current)):
    """이 포켓몬에게 지금 쓸 수 있는 기술머신."""
    uid = me["user"]["id"]
    r = _mon(uid, pid)
    num, sp = _species_num(r)
    if not sp:
        raise HTTPException(404, "그런 종이 없습니다.")
    got = tms.owned(uid)
    can = set(tms.learnable(num))
    moves = json.loads(r["moves"])
    out = []
    for no in sorted(can & got):
        t = tms.get(no)
        out.append({"no": no, "move": t["move"], "kr": t["kr"],
                    "type": t["type"], "cat": t["cat"],
                    "label": tms.label(no),
                    "known": t["move"] in moves})
    return {"pokemon": pid, "moves": moves, "usable": out,
            "canLearn": len(can), "have": len(can & got)}


@router.get("/api/tms/{no}/learners")
def learners(no: int, me=Depends(deps.current)):
    """이 기술머신을 배울 수 있는 내 포켓몬.

    **한 번에 준다.** 전에는 클라이언트가 포켓몬마다 /api/tms/{pid} 를
    불렀는데, 예순 마리를 가진 사람은 기술머신을 하나 고를 때마다 예순
    번을 두드리게 된다.
    """
    uid = me["user"]["id"]
    t = tms.get(no)
    if not t:
        raise HTTPException(404, "그런 기술머신이 없습니다.")
    d = deps.dex()
    out = []
    rows = db.q("SELECT * FROM pokemon WHERE user_id=? ORDER BY id", (uid,))
    for r in rows:
        sp = d.get(r["species"])
        if not sp or not tms.can_learn(sp["num"], no):
            continue
        moves = json.loads(r["moves"])
        out.append({
            "id": r["id"],
            "name": r["nickname"] or sp["kr"],
            "num": sp["num"],
            "level": r["level"],
            "shiny": bool(r["shiny"]),
            "moves": moves,
            "known": t["move"] in moves,
        })
    return {"no": no, "have": tms.has(uid, no), "learners": out}


# ---------------------------------------------------------------- 쓰기
@router.post("/api/tms/use")
def use(body: TeachIn, me=Depends(deps.current)):
    uid = me["user"]["id"]
    t = tms.get(body.no)
    if not t:
        raise HTTPException(404, "그런 기술머신이 없습니다.")
    if not tms.has(uid, body.no):
        raise HTTPException(400, "%s을(를) 갖고 있지 않습니다."
                            % tms.label(body.no))
    r = _mon(uid, body.pokemon)
    num, sp = _species_num(r)
    if not tms.can_learn(num, body.no):
        raise HTTPException(400, "%s은(는) %s을(를) 배울 수 없습니다."
                            % (r["nickname"] or sp["kr"], t["kr"]))

    moves = json.loads(r["moves"])
    if t["move"] in moves:
        raise HTTPException(400, "이미 %s을(를) 알고 있습니다." % t["kr"])

    if len(moves) < MAX_MOVES:
        moves.append(t["move"])
        _apply(r, moves, _pending_of(r))
        return {"ok": True, "moves": moves, "learned": t["kr"],
                "message": korean.natural("%s이(가) %s을(를) 배웠다!"
                                          % (r["nickname"] or sp["kr"],
                                             t["kr"]))}

    # 네 개가 차 있다. 무엇을 잊을지 받아야 한다.
    if not body.forget:
        return {"ok": False, "needForget": True, "moves": moves,
                "move": t["move"], "kr": t["kr"],
                "message": "기술이 네 개라 하나를 잊어야 합니다."}
    if body.forget not in moves:
        raise HTTPException(400, "그 기술을 갖고 있지 않습니다.")
    moves = [t["move"] if m == body.forget else m for m in moves]
    _apply(r, moves, _pending_of(r))
    d = deps.dex()
    return {"ok": True, "moves": moves, "learned": t["kr"],
            "forgot": d.move_name(body.forget),
            "message": korean.natural(
                "%s이(가) %s을(를) 잊고 %s을(를) 배웠다!"
                % (r["nickname"] or sp["kr"], d.move_name(body.forget),
                   t["kr"]))}


# ---------------------------------------------------------------- 기다리던 것
@router.post("/api/pokemon/learn")
def learn(body: LearnIn, me=Depends(deps.current)):
    """레벨업으로 배우려던 기술을 배우거나 버린다."""
    uid = me["user"]["id"]
    r = _mon(uid, body.pokemon)
    pending = _pending_of(r)
    if body.move not in pending:
        raise HTTPException(400, "기다리는 기술이 아닙니다.")
    d = deps.dex()
    sp = deps.dex().get(r["species"])
    name = r["nickname"] or (sp or {}).get("kr", "포켓몬")
    moves = json.loads(r["moves"])
    pending = [m for m in pending if m != body.move]

    if body.skip or not body.forget:
        _apply(r, moves, pending)
        return {"ok": True, "moves": moves, "pending": pending,
                "learned": None,
                "message": korean.natural("%s은(는) %s을(를) 배우지 않았다."
                                          % (name, d.move_name(body.move)))}

    if body.forget not in moves:
        raise HTTPException(400, "그 기술을 갖고 있지 않습니다.")
    moves = [body.move if m == body.forget else m for m in moves]
    _apply(r, moves, pending)
    return {"ok": True, "moves": moves, "pending": pending,
            "learned": d.move_name(body.move),
            "forgot": d.move_name(body.forget),
            "message": korean.natural(
                "%s이(가) %s을(를) 잊고 %s을(를) 배웠다!"
                % (name, d.move_name(body.forget), d.move_name(body.move)))}
