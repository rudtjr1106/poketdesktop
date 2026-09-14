# -*- coding: utf-8 -*-
"""관장 도전 API.

    GET  /api/gym                      256곳 요약 + 내가 이긴 곳
    GET  /api/gym/map                  경계 (gzip, 요약값 머리글)
    GET  /api/gym/trainer/{region}     한 곳의 트레이너와 팀(종·레벨)
    GET  /api/gym/sprite/{key}         트레이너 도트
    POST /api/gym/{region}/start       도전 시작
    GET  /api/gym/battle               진행 중인 판
    POST /api/gym/battle/{bid}/act     한 턴 (기술 / 교체 / 기권)

## 서버가 판정한다

클라이언트가 보내는 것은 '무엇을 할지' 뿐이다. 데미지·명중·AI·보상은 전부
여기서 정한다. 판 전체를 턴마다 DB 에 쓰고(common/trainer_battle.dump),
다음 요청에서 되살린다. 난수 상태까지 남기므로 같은 턴을 다시 보내 결과를
골라 먹을 수 없다.

## 겹친 요청

창을 두 개 띄웠거나 요청이 겹치면 같은 판에 두 턴이 들어온다. rev 로 막는다 -
읽을 때의 rev 로 UPDATE 해서 0줄이면 다른 요청이 먼저 쓴 것이라 409 를 준다.
"""
import datetime
import json
import random

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from common import trainer_battle as TB

from . import auth, battle_routes, config, db, deps, gym, items

router = APIRouter()


class ActIn(BaseModel):
    kind: str                    # move / switch / forfeit
    move: str = ""
    slot: int = -1
    hour: int = -1


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _party(uid):
    return [db.row_to_mon(r) for r in db.q(
        "SELECT * FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY slot, id", (uid,))]


def _expire_old(uid):
    """손 놓은 지 오래된 판을 접는다."""
    cutoff = (_now() - datetime.timedelta(seconds=config.GYM_BATTLE_TTL)).isoformat()
    db.run("UPDATE gym_battle SET state='done', result='expired'"
           " WHERE user_id=? AND state='active' AND updated_at < ?", (uid, cutoff))


def _active(uid):
    _expire_old(uid)
    return db.q1("SELECT * FROM gym_battle WHERE user_id=? AND state='active'"
                  " ORDER BY id DESC LIMIT 1", (uid,))


def _out(row, tb, events=None, extra=None):
    out = {"id": row["id"], "region": row["region"], "rev": row["rev"],
           "battle": tb.view(), "events": events or []}
    if extra:
        out.update(extra)
    return out


# ---------------------------------------------------------------- 보기
@router.get("/api/gym")
def overview(ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    d = deps.dex()
    g = gym.gyms()
    mine = gym.clears(uid)
    regions = []
    for code, t in g["_by_region"].items():
        c = mine.get(code)
        row = gym.public(t, d)
        row["cleared"] = bool(c)
        row["wins"] = c["wins"] if c else 0
        row["bestTurns"] = c["best_turns"] if c else None
        regions.append(row)
    act = _active(uid)
    return {"regions": regions, "cleared": len(mine), "total": len(g["regions"]),
            "tiers": g["tiers"], "digest": g.get("digest"), "mapDigest": gym.korea_map()[1],
            "source": g.get("source"), "active": ({"id": act["id"], "region": act["region"]}
                                                  if act else None)}


@router.get("/api/gym/map")
def korea_map():
    body, digest = gym.korea_map()
    return Response(body, media_type="application/json",
                    headers={"Content-Encoding": "gzip", "X-Digest": digest,
                             "Cache-Control": "public, max-age=604800"})


@router.get("/api/gym/trainer/{region}")
def trainer_card(region: str, ctx=Depends(deps.current)):
    t = gym.trainer_at(region)
    if not t:
        raise HTTPException(404, "그 지역에는 트레이너가 없습니다.")
    out = gym.public(t, deps.dex(), full=True)
    c = gym.clears(ctx["user"]["id"]).get(region)
    out["cleared"] = bool(c)
    out["wins"] = c["wins"] if c else 0
    out["bestTurns"] = c["best_turns"] if c else None
    out["prize"] = t["level"] * (config.GYM_REPEAT_PER_LEVEL if c else config.GYM_PRIZE_PER_LEVEL)
    return out


@router.get("/api/gym/sprite/{key}")
def trainer_sprite(key: str):
    p = gym.sprite_path(key)
    if not p:
        raise HTTPException(404, "도트가 없습니다.")
    with open(p, "rb") as f:
        return Response(f.read(), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=2592000"})


# ---------------------------------------------------------------- 판
@router.post("/api/gym/{region}/start")
def start(region: str, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    t = gym.trainer_at(region)
    if not t:
        raise HTTPException(404, "그 지역에는 트레이너가 없습니다.")
    old = _active(uid)
    if old:
        if old["region"] != region:
            other = gym.trainer_at(old["region"]) or {}
            raise HTTPException(409, "%s 과(와)의 승부가 아직 끝나지 않았습니다."
                                % (other.get("name") or "다른 트레이너"))
        tb = TB.TrainerBattle.load(deps.dex(), json.loads(old["data"]))
        return _out(old, tb, extra={"resumed": True})
    party = _party(uid)
    if not party:
        raise HTTPException(409, "데리고 다니는 포켓몬이 없습니다.")
    tb = TB.TrainerBattle(deps.dex(), party, t, random.Random())
    events = tb.start()
    now = auth.now_iso()
    cur = db.run("INSERT INTO gym_battle (user_id, region, trainer, state, turn, rev, data,"
                 " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                 (uid, region, t["id"], "active", 0, 0, json.dumps(tb.dump()), now,
                  _now().isoformat()))
    row = db.q1("SELECT * FROM gym_battle WHERE id=?", (cur.lastrowid,))
    return _out(row, tb, events)


@router.get("/api/gym/battle")
def current(ctx=Depends(deps.current)):
    row = _active(ctx["user"]["id"])
    if not row:
        raise HTTPException(404, "진행 중인 관장 배틀이 없습니다.")
    return _out(row, TB.TrainerBattle.load(deps.dex(), json.loads(row["data"])))


@router.post("/api/gym/battle/{bid}/act")
def act(bid: int, body: ActIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    _expire_old(uid)
    row = db.q1("SELECT * FROM gym_battle WHERE id=? AND user_id=?", (bid, uid))
    if not row:
        raise HTTPException(404, "그런 배틀이 없습니다.")
    if row["state"] != "active":
        raise HTTPException(409 if row["result"] != "expired" else 410,
                            "시간이 지나 승부가 끝났습니다." if row["result"] == "expired"
                            else "이미 끝난 승부입니다.")
    d = deps.dex()
    tb = TB.TrainerBattle.load(d, json.loads(row["data"]))
    kind = (body.kind or "").lower()
    if kind not in ("move", "switch", "forfeit"):
        raise HTTPException(400, "무엇을 할지 알 수 없습니다.")
    kos_before = len(tb.kos)
    try:
        if kind == "move":
            events = tb.act("move", body.move or "")
        elif kind == "switch":
            events = tb.act("switch", int(body.slot))
        else:
            events = tb.act("forfeit")
    except ValueError as e:
        raise HTTPException(409, str(e))

    state = "done" if tb.over else "active"
    cur = db.run("UPDATE gym_battle SET data=?, turn=?, rev=rev+1, state=?, result=?,"
                 " updated_at=? WHERE id=? AND rev=?",
                 (json.dumps(tb.dump()), tb.turn, state, tb.result, _now().isoformat(),
                  bid, row["rev"]))
    if getattr(cur, "rowcount", 1) == 0:
        raise HTTPException(409, "다른 곳에서 먼저 움직였습니다. 다시 불러오세요.")

    extra = {}
    hour = body.hour if 0 <= body.hour <= 23 else None
    exp = []
    # 쓰러뜨릴 때마다 경험치. 그 순간 나와 있던 포켓몬이 받는다.
    for ko in tb.kos[kos_before:]:
        mine = tb.me_team[ko["by"]]
        pid = mine.mon.get("id")
        if pid:
            exp.extend(battle_routes.award(d, uid, tb.foe_team[ko["foe"]], pid, hour,
                                           rate=config.GYM_EXP_RATE) or [])
    if exp:
        extra["exp"] = exp
    if tb.over and tb.result == "won":
        t = gym.trainer(row["trainer"])
        prize, first = gym.record_win(uid, t, tb.turn, auth.now_iso())
        if prize:
            items.money_add(uid, prize)
        extra["reward"] = {"prize": prize, "first": first, "money": items.money(uid),
                           "cleared": len(gym.clears(uid)), "total": len(gym.gyms()["regions"])}
    row = db.q1("SELECT * FROM gym_battle WHERE id=?", (bid,))
    return _out(row, tb, events, extra)
