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

기술 떠올리기도 여기 있다. 레벨업으로 배울 수 있었던 기술을 돈을 내고
다시 배운다 - 한 번 잊은 기술(자력기 포함)을 되찾을 길이 이것뿐이다.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common import korean

from . import config, db, deps, items, tms

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


class RememberIn(BaseModel):
    pokemon: int
    move: str                # 떠올릴 기술
    forget: str = ""         # 잊을 기술 (네 개가 차 있을 때만 필요)


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


# ---------------------------------------------------------------- 기술 떠올리기
def _won(n):
    return "{:,}".format(int(n))


def rememberable(r, sp, d=None):
    """떠올릴 수 있는 기술. [(기술, 레벨)] 을 레벨 순으로.

    **지금 종의 학습표에서 지금 레벨 이하인 것**이다. 레벨 0 은 진화할 때
    배우는 기술이다. 진화 전 종의 표는 따로 안 본다 - 진화형 표에 이미
    레벨 1 로 실려 있다(리자몽 표에 파이리 기술이 다 들어 있다).

    기다리는 기술(pending)도 넣는다. 레벨업 때 자리가 없어 못 배운 것이라
    대부분 이미 위에 들어 있지만, 진화 전에 생긴 것은 지금 표에 없을 수 있다.
    그때는 레벨을 None 으로 둔다.

    이미 아는 기술과 도감에 없는 기술은 뺀다.
    """
    d = d or deps.dex()
    known = set(json.loads(r["moves"]))
    level = int(r["level"])
    best = {}
    for lv, mv in (sp or {}).get("moves", []):
        if lv > level or mv in known or d.move(mv) is None:
            continue
        if mv not in best or lv < best[mv]:
            best[mv] = lv
    out = sorted(best.items(), key=lambda kv: (kv[1], kv[0]))
    for mv in _pending_of(r):
        if mv not in best and mv not in known and d.move(mv) is not None:
            out.append((mv, None))
            best[mv] = None
    return out


@router.get("/api/pokemon/{pid}/remember")
def remember_list(pid: int, me=Depends(deps.current)):
    """이 포켓몬이 떠올릴 수 있는 기술, 값, 가진 돈."""
    uid = me["user"]["id"]
    r = _mon(uid, pid)
    _num, sp = _species_num(r)
    if not sp:
        raise HTTPException(404, "그런 종이 없습니다.")
    d = deps.dex()
    pending = set(_pending_of(r))
    out = [{"move": mv, "kr": d.move_name(mv), "level": lv,
            "free": mv in pending}
           for mv, lv in rememberable(r, sp, d)]
    return {"pokemon": pid, "name": r["nickname"] or sp["kr"],
            "moves": json.loads(r["moves"]), "remember": out,
            "cost": config.REMEMBER_COST, "money": items.money(uid)}


@router.post("/api/pokemon/remember")
def remember(body: RememberIn, me=Depends(deps.current)):
    """떠올린다. 네 개가 차 있으면 forget 없이 부르면 needForget 이 온다.

    **돈은 기술을 바꾸기 직전에 받는다.** 받을 수 없는 요청(못 떠올리는
    기술, 없는 기술을 잊으라는 것, 돈이 모자람)은 그 전에 전부 거른다.
    기술을 바꾸는 UPDATE 는 읽었을 때의 기술·기다리는 목록이 그대로일
    때만 먹는다. 두 번 눌렀거나 그사이 배틀이 기술을 바꿨으면 돈을 돌려준다.
    """
    uid = me["user"]["id"]
    r = _mon(uid, body.pokemon)
    _num, sp = _species_num(r)
    if not sp:
        raise HTTPException(404, "그런 종이 없습니다.")
    d = deps.dex()
    name = r["nickname"] or sp["kr"]
    moves = json.loads(r["moves"])
    pending = _pending_of(r)
    kr = d.move_name(body.move)

    if body.move in moves:
        raise HTTPException(400, korean.natural(
            "이미 %s을(를) 알고 있습니다." % kr))
    if body.move not in dict(rememberable(r, sp, d)):
        raise HTTPException(400, korean.natural(
            "%s은(는) %s을(를) 떠올릴 수 없습니다." % (name, kr)))

    cost = 0 if body.move in pending else config.REMEMBER_COST
    have = items.money(uid)
    if cost > have:
        raise HTTPException(400, "골드가 부족합니다. %s원이 필요한데 %s원 있습니다."
                            % (_won(cost), _won(have)))

    if len(moves) < MAX_MOVES:
        new = moves + [body.move]
        forgot = None
    elif not body.forget:
        return {"ok": False, "needForget": True, "moves": moves,
                "move": body.move, "kr": kr, "cost": cost, "money": have,
                "message": "기술이 네 개라 하나를 잊어야 합니다."}
    elif body.forget not in moves:
        raise HTTPException(400, "그 기술을 갖고 있지 않습니다.")
    else:
        new = [body.move if m == body.forget else m for m in moves]
        forgot = d.move_name(body.forget)

    if cost and not items.money_take(uid, cost):
        raise HTTPException(400, "골드가 부족합니다. %s원이 필요합니다." % _won(cost))
    rest = [m for m in pending if m != body.move]
    cur = db.run("UPDATE pokemon SET moves=?, pending=? WHERE id=? AND user_id=?"
                 " AND moves=? AND pending=?",
                 (json.dumps(new), json.dumps(rest), r["id"], uid,
                  r["moves"], r["pending"]))
    if cur.rowcount == 0:
        items.money_add(uid, cost)
        raise HTTPException(409, "그사이 기술이 바뀌었습니다. 다시 열어 주세요.")

    if forgot:
        msg = "%s이(가) %s을(를) 잊고 %s을(를) 떠올렸다!" % (name, forgot, kr)
    else:
        msg = "%s이(가) %s을(를) 떠올렸다!" % (name, kr)
    return {"ok": True, "moves": new, "pending": rest, "learned": kr,
            "forgot": forgot, "cost": cost, "money": items.money(uid),
            "message": korean.natural(msg)}
