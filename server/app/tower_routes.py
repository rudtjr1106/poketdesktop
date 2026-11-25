# -*- coding: utf-8 -*-
"""배틀타워 (시즌 7) 의 길. 규칙은 tower.py 에 있다.

    GET  /api/tower              층 목록과 내 진행 (닫혀 있으면 {"open": false, "from": 7})
    GET  /api/tower/floor/{n}    한 층의 트레이너와 팀(종 · 레벨) · 보상 - 다음 층과 이미 이긴 층만
    POST /api/tower/{n}/start    그 층과 판을 연다. 하던 타워 판이 있으면 (다른 층이어도) 그 판을 이어서 준다.

판은 관장 배틀과 같은 것이다 - 진행은 /api/gym/battle/{id}/act 로 하고, 창도 같은 창을 쓴다. 이겼을 때의
기록 · 보상은 gym_routes.act 가 tower.on_win 으로 넘긴다.
"""
import datetime
import json

from fastapi import APIRouter, Depends, HTTPException

from common import trainer_battle as TB

from . import arche, auth, db, deps, gimmick, gym_routes, mega, pvp, tower

router = APIRouter()


@router.get("/api/tower")
def overview(ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    out = tower.overview(uid)
    if out["open"]:
        act = gym_routes._active(uid)
        n = tower.parse(act["region"]) if act else None
        out["active"] = {"id": act["id"], "floor": n} if n else None
    return out


@router.get("/api/tower/floor/{n}")
def card(n: int, ctx=Depends(deps.current)):
    try:
        return tower.card(ctx["user"]["id"], n)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/api/tower/{n}/start")
def start(n: int, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    if not tower.floor(n):
        raise HTTPException(404, "그런 층이 없습니다.")
    if not tower.is_open():
        raise HTTPException(409, tower.closed_text())
    old = gym_routes._active(uid)
    if old:
        if not tower.is_tower(old["region"]):
            # 관장 · 악당 · 길드전 · 아르케 판이 남아 있다 - 판은 하나뿐이라 그쪽부터 끝낸다
            raise HTTPException(409, "%s 과(와)의 승부가 아직 끝나지 않았습니다. 그 승부부터 마쳐 주세요."
                                % arche._busy_name(old["region"]))
        tb = TB.TrainerBattle.load(deps.dex(), json.loads(old["data"]))
        return gym_routes._out(old, tb, extra={"resumed": True})
    # 전설·환상은 한 마리만, 같은 종도 한 마리만 나간다 (관장과 같다). 나머지는 이번 판에서 쉰다.
    # 상대 팀에는 이 규칙이 없다 - 같은 종 · 같은 도구가 겹쳐 나온다 (tower.py).
    party, benched = pvp.split_restricted(gym_routes._party(uid))
    if not party:
        raise HTTPException(409, "데리고 다니는 포켓몬이 없습니다.")
    try:
        region, tid, tb, events = tower.start(
            uid, party, n, zring=gimmick.has_zring(uid), keystone=mega.has_keystone(uid), orb=gimmick.has_orb(uid))
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    if benched:
        at = 1 if events and events[0].get("t") == "intro" else 0
        events.insert(at, {"t": "note", "text": pvp.bench_note(benched, party)})
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = db.run("INSERT INTO gym_battle (user_id, region, trainer, state, turn, rev, data,"
                 " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                 (uid, region, tid, "active", 0, 0, json.dumps(tb.dump()), auth.now_iso(), now))
    row = db.q1("SELECT * FROM gym_battle WHERE id=?", (cur.lastrowid,))
    return gym_routes._out(row, tb, events)
