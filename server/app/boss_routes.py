# -*- coding: utf-8 -*-
"""악당 출현 (시즌 4) 의 길. 규칙은 boss.py 에 있다.

    GET  /api/boss          오늘의 악당과 내 진행 (아직 안 나타났으면 {"active": false})
    POST /api/boss/start    다음 상대(간부 또는 전설)와 판을 연다. 하던 판이 있으면 이어서 준다.

판은 관장 배틀과 같은 것이다 - 진행은 /api/gym/battle/{id}/act 로 하고, 창도 같은 창을 쓴다.
"""
import datetime
import json

from fastapi import APIRouter, Depends, HTTPException

from common import trainer_battle as TB

from . import auth, boss, db, deps, gimmick, gym_routes, mega, pvp

router = APIRouter()


@router.get("/api/boss")
def card(ctx=Depends(deps.current)):
    return boss.card(ctx["user"]["id"])


@router.post("/api/boss/start")
def start(ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    old = gym_routes._active(uid)
    if old:
        if not boss.is_boss(old["region"]):
            raise HTTPException(409, "관장과의 승부가 아직 끝나지 않았습니다. 그 승부부터 마쳐 주세요.")
        tb = TB.TrainerBattle.load(deps.dex(), json.loads(old["data"]))
        return gym_routes._out(old, tb, extra={"resumed": True})
    # 전설·환상은 한 마리만, 같은 종도 한 마리만 나간다 (관장과 같다). 나머지는 이번 판에서 쉰다.
    party, benched = pvp.split_restricted(gym_routes._party(uid))
    if not party:
        raise HTTPException(409, "데리고 다니는 포켓몬이 없습니다.")
    try:
        region, tid, tb, events = boss.start(
            uid, party, zring=gimmick.has_zring(uid), keystone=mega.has_keystone(uid))
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
