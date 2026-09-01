# -*- coding: utf-8 -*-
"""야생 배틀 API.

판정은 전부 서버가 한다. 클라이언트는 '무슨 기술을 썼다'만 보내고
결과(events)를 받아서 그림만 그린다. 나중에 유저끼리 붙일 때도
같은 원칙이라야 서로 속이지 못한다.

경험치는 학습장치 방식이다.
    싸운 포켓몬        100%
    파티의 나머지       50%   (POKET_EXP_SHARE_RATE 로 조절)
"""
import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common import battle as B
from common import pokelogic as P

from . import auth, config, db, deps, items, walk

router = APIRouter()


class MoveIn(BaseModel):
    move: str = ""
    hour: int = -1        # 클라이언트의 시각 (이브이 낮/밤 진화용)


class SwitchIn(BaseModel):
    pokemon: int


class BallIn(BaseModel):
    ball: str = "POKEBALL"
    hour: int = -1


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


# ---------------------------------------------------------------- 도구
def _party(uid):
    return [db.row_to_mon(r) for r in db.q(
        "SELECT * FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY slot, id",
        (uid,))]


def _first_healthy(uid, hp_map):
    for m in _party(uid):
        if hp_map.get(m["id"], 1) > 0:
            return m
    return None


def _load(ctx, bid=None):
    """진행 중인 배틀 행을 가져온다."""
    uid = ctx["user"]["id"]
    if bid:
        row = db.q1("SELECT * FROM battle WHERE id=? AND user_id=?", (bid, uid))
    else:
        row = db.q1("SELECT * FROM battle WHERE user_id=? AND state='active'"
                    " ORDER BY id DESC LIMIT 1", (uid,))
    if not row:
        raise HTTPException(404, "진행 중인 배틀이 없습니다.")
    if row["state"] != "active":
        raise HTTPException(409, "이미 끝난 배틀입니다.")
    exp = auth.parse_iso(row["expires_at"])
    if exp and exp < _now():
        db.run("UPDATE battle SET state='done', result='fled' WHERE id=?", (row["id"],))
        raise HTTPException(410, "배틀이 시간 초과로 끝났습니다.")
    return row


def _fighters(dex, row):
    """저장해둔 상태로 배틀을 복원한다."""
    me_raw = json.loads(row["me"])
    foe_raw = json.loads(row["foe"])
    me = B.Fighter(dex, me_raw["mon"], me_raw["hp"], me_raw["pp"], me_raw["status"])
    me.stages = me_raw.get("stages") or me.stages
    me.sleep_turns = me_raw.get("sleep", 0)
    foe = B.Fighter(dex, foe_raw["mon"], foe_raw["hp"], foe_raw["pp"],
                    foe_raw["status"])
    foe.stages = foe_raw.get("stages") or foe.stages
    foe.sleep_turns = foe_raw.get("sleep", 0)
    return me, foe


def _dump(f):
    return {"mon": f.mon, "hp": f.hp, "pp": f.pp, "status": f.status,
            "stages": f.stages, "sleep": f.sleep_turns}


def _save(row_id, bt, result=None, state=None):
    db.run("UPDATE battle SET turn=?, me=?, foe=?, state=?, result=? WHERE id=?",
           (bt.turn_no, json.dumps(_dump(bt.me)), json.dumps(_dump(bt.foe)),
            state or ("done" if bt.over else "active"),
            result or bt.result, row_id))


def _side(dex, f, reveal_pp=True):
    sp = dex.get(f.mon["species"]) or {}
    out = {
        "id": f.mon.get("id"),
        "species": f.mon["species"],
        "num": sp.get("num"),
        "name": f.name,
        "kr": sp.get("kr"),
        "level": f.level,
        "hp": f.hp, "maxhp": f.maxhp,
        "status": f.status,
        "statusKr": B.STATUS_KR.get(f.status),
        "shiny": bool(f.mon.get("shiny")),
        "gender": f.mon.get("gender"),
        "types": [dex.type_name(t) for t in sp.get("types", [])],
        "typeIds": sp.get("types", []),
        "stages": dict((k, v) for k, v in f.stages.items() if v),
    }
    if reveal_pp:
        out["moves"] = [{
            "key": m, "kr": dex.move_name(m),
            "type": (dex.move(m) or {}).get("type"),
            "typeKr": dex.type_name((dex.move(m) or {}).get("type")),
            "cat": (dex.move(m) or {}).get("cat"),
            "power": (dex.move(m) or {}).get("power"),
            "acc": (dex.move(m) or {}).get("acc"),
            "pp": f.pp.get(m, 0),
            "maxpp": (dex.move(m) or {}).get("pp", 0),
        } for m in f.moves]
        if not any(x["pp"] > 0 for x in out["moves"]):
            out["moves"].append({"key": B.STRUGGLE, "kr": "몸부림", "type": "NORMAL",
                                 "typeKr": "노말", "cat": "physical", "power": 50,
                                 "acc": 0, "pp": 1, "maxpp": 1})
    return out


def _view(dex, row, bt):
    return {
        "id": row["id"],
        "wildId": row["wild_id"],
        "turn": bt.turn_no,
        "over": bt.over,
        "result": bt.result,
        "me": _side(dex, bt.me, True),
        "foe": _side(dex, bt.foe, False),
    }


# ---------------------------------------------------------------- 경험치
def grant_exp(dex, uid, mon_id, amount, hour=None):
    """경험치 주기. 실제 처리는 deps 에 모아 뒀다 (main 과 같은 코드를 쓴다)."""
    return deps.grant_exp(uid, mon_id, amount, hour)


def _take_ball(uid, balls, want, wild, mine, turn, hour):
    """던질 볼을 하나 뺀다. (도구 id, 포획 배율, 남은 몬스터볼).

    몬스터볼만 users.balls 에서 세고 나머지는 가방에서 뺀다. main.py 의
    _take_ball 과 같은 규칙이다 — 한쪽만 고치지 않도록 주의.
    """
    want = (want or "POKEBALL").upper()
    it = items.get(want)
    if it is None or it.get("effect", {}).get("kind") != "ball":
        want, it = "POKEBALL", items.get("POKEBALL")
    if not items.bag_take(uid, want, 1):
        raise HTTPException(409, "%s 이(가) 없습니다." % it["kr"])
    if want == "POKEBALL":
        balls -= 1
    bonus = items.ball_bonus(want, deps.dex(), wild, mine=mine, turn=turn,
                             uid=uid, hour=hour)
    return want, bonus, balls


def _drop(uid, mon, chance):
    """야생 하나를 처리했을 때 도구가 떨어지는지."""
    if chance <= 0 or deps.RNG.random() > chance:
        return None
    item_id = items.roll_drop(deps.RNG, bool(mon.get("shiny")))
    items.bag_add(uid, item_id, 1)
    return items.drop_public(item_id)


def give_evs(uid, mon_id, yields):
    """쓰러뜨린 종이 주는 노력치를 더한다.

    종마다 '쓰러뜨리면 무슨 노력치를 얼마나 주는지' 가 본가에 정해져 있고
    (도감의 ev 칸), 합계는 1~3 이다. 스탯당 252 · 총합 510 을 넘지 않는다.
    """
    if not yields:
        return None
    r = db.q1("SELECT evs FROM pokemon WHERE id=? AND user_id=?", (mon_id, uid))
    if not r:
        return None
    before = items.clamp_evs(json.loads(r["evs"]))
    after = items.add_evs(before, yields)
    if after == before:
        return None
    db.run("UPDATE pokemon SET evs=? WHERE id=?", (json.dumps(after), mon_id))
    return dict((k, after[k] - before[k]) for k in after
                if after[k] != before[k])


def award(dex, uid, foe, participant_id, hour=None):
    """싸운 포켓몬은 전부, 파티의 나머지는 학습장치 몫."""
    out = []
    foe_sp = dex.get(foe.mon["species"]) or {}
    ev_yield = foe_sp.get("ev") or {}

    part = db.q1("SELECT level FROM pokemon WHERE id=?", (participant_id,))
    lv = part["level"] if part else 5
    main = B.exp_gain(dex, foe, lv)
    got_ev = give_evs(uid, participant_id, ev_yield)
    g = grant_exp(dex, uid, participant_id, main, hour)
    if g:
        g["shared"] = False
        if got_ev:
            g["evs"] = got_ev
        out.append(g)
    if config.EXP_SHARE:
        for m in _party(uid):
            if m["id"] == participant_id:
                continue
            amt = B.exp_gain(dex, foe, m["level"], shared=True)
            amt = int(amt * config.EXP_SHARE_RATE / 50.0)   # 기본 50% 기준
            share_ev = give_evs(uid, m["id"], ev_yield) if config.EV_SHARE else None
            g = grant_exp(dex, uid, m["id"], amt, hour)
            if g:
                g["shared"] = True
                if share_ev:
                    g["evs"] = share_ev
                out.append(g)
    return out


def foe_only_turn(d, me, foe, ev):
    """볼을 던지거나 도망에 실패했을 때 상대만 한 번 움직인다."""
    bt = B.Battle(d, me, foe, deps.RNG)
    key = bt.choose_ai()
    if key and foe.alive():
        bt._use("foe", foe, me, key, ev)
    return key


def store_caught(uid, mon):
    """잡은 포켓몬을 파티에 넣는다. 꽉 찼으면 PC 박스로."""
    mid = db.insert_mon(uid, mon, auth.now_iso())
    slot = deps.free_slot(uid)
    if slot is not None:
        db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=?", (slot, mid))
        where = "party"
    else:
        where = "box"
    got = db.row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (mid,)))
    return deps.decorate(got), where


def reschedule(uid):
    """다음 풀숲 시각을 다시 잡는다."""
    secs = deps.RNG.randint(config.WILD_COOLDOWN_MIN, config.WILD_COOLDOWN_MAX)
    at = (_now() + datetime.timedelta(seconds=secs)).isoformat()
    db.run("INSERT INTO wild_state (user_id, next_at) VALUES (?,?)"
           " ON CONFLICT(user_id) DO UPDATE SET next_at=?", (uid, at, at))


# ---------------------------------------------------------------- 엔드포인트
@router.post("/api/wild/{wid}/battle")
def start(wid: int, ctx=Depends(deps.current)):
    """야생 포켓몬에게 배틀을 건다. 파티 선두가 나간다."""
    uid = ctx["user"]["id"]
    d = deps.dex()

    old = db.q1("SELECT * FROM battle WHERE user_id=? AND state='active'"
                " ORDER BY id DESC LIMIT 1", (uid,))
    if old:
        if old["wild_id"] == wid:
            me, foe = _fighters(d, old)
            bt = B.Battle(d, me, foe)
            bt.turn_no = old["turn"]
            return {"battle": _view(d, old, bt), "resumed": True}
        db.run("UPDATE battle SET state='done', result='fled' WHERE id=?",
               (old["id"],))

    w = db.q1("SELECT * FROM wild WHERE id=? AND user_id=?", (wid, uid))
    if not w:
        raise HTTPException(404, "야생 포켓몬이 이미 사라졌습니다.")
    if w["state"] != "revealed":
        raise HTTPException(409, "아직 모습을 드러내지 않았습니다.")

    party = _party(uid)
    if not party:
        raise HTTPException(409, "데리고 있는 포켓몬이 없습니다.")
    mine = party[0]

    me = B.Fighter(d, mine)
    foe = B.Fighter(d, json.loads(w["data"]))
    t = _now()
    later = (t + datetime.timedelta(seconds=config.BATTLE_TTL)).isoformat()
    cur = db.run(
        "INSERT INTO battle (user_id, wild_id, mine_id, state, turn, me, foe,"
        " created_at, expires_at) VALUES (?,?,?,'active',0,?,?,?,?)",
        (uid, wid, mine["id"], json.dumps(_dump(me)), json.dumps(_dump(foe)),
         auth.now_iso(), later))
    # 배틀 중에는 야생이 도망가지 않게 시간을 넉넉히 준다
    db.run("UPDATE wild SET expires_at=? WHERE id=?", (later, wid))
    db.run("INSERT INTO wild_state (user_id, battles) VALUES (?,1)"
           " ON CONFLICT(user_id) DO UPDATE SET battles=battles+1", (uid,))

    row = db.q1("SELECT * FROM battle WHERE id=?", (cur.lastrowid,))
    bt = B.Battle(d, me, foe)
    return {"battle": _view(d, row, bt), "resumed": False,
            "intro": "앗! 야생 %s 이(가) 튀어나왔다!" % foe.name}


@router.get("/api/battle")
def current_battle(ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    row = db.q1("SELECT * FROM battle WHERE user_id=? AND state='active'"
                " ORDER BY id DESC LIMIT 1", (uid,))
    if not row:
        return {"battle": None}
    d = deps.dex()
    me, foe = _fighters(d, row)
    bt = B.Battle(d, me, foe)
    bt.turn_no = row["turn"]
    return {"battle": _view(d, row, bt)}


@router.post("/api/battle/{bid}/move")
def use_move(bid: int, body: MoveIn, ctx=Depends(deps.current)):
    """기술을 쓴다. 한 턴이 진행되고 일어난 일 목록을 돌려준다."""
    uid = ctx["user"]["id"]
    d = deps.dex()
    row = _load(ctx, bid)
    me, foe = _fighters(d, row)
    bt = B.Battle(d, me, foe, deps.RNG)
    bt.turn_no = row["turn"]

    # 기술을 안 보내면(자동 전투) 서버가 골라준다.
    pick = body.move
    if not pick or pick == "AUTO":
        pick = bt.choose_mine()
    out = {"myMove": pick, "myMoveKr": bt.move_name(pick),
           "events": bt.take_turn(pick)}

    if bt.over and bt.result == "won":
        db.run("INSERT INTO wild_state (user_id, wins) VALUES (?,1)"
               " ON CONFLICT(user_id) DO UPDATE SET wins=wins+1", (uid,))
        hour = body.hour if 0 <= body.hour <= 23 else None
        out["exp"] = award(d, uid, foe, row["mine_id"], hour)
        items.mark_seen(uid, foe.mon["species"], False, auth.now_iso())
        # 쓰러뜨려도 도구가 떨어진다. 포획보다는 덜 나온다.
        # 볼이 다 떨어져도 배틀로는 다시 일어설 수 있어야 하기 때문이다.
        drop = _drop(uid, foe.mon, config.DROP_ON_WIN)
        if drop:
            out["drop"] = drop
        out["money"] = items.money(uid)
        out["bag"] = items.bag_get(uid)
        db.run("DELETE FROM wild WHERE id=?", (row["wild_id"],))
        reschedule(uid)
    elif bt.over and bt.result == "lost":
        # 쓰러진 그 한 마리만 조금 깎인다. 본가와 같은 방향이되 훨씬 약하다.
        walk.on_faint(uid, row["mine_id"])
        nxt = [m for m in _party(uid) if m["id"] != row["mine_id"]]
        out["canSwitch"] = bool(nxt)
        out["party"] = [deps.decorate(m) for m in nxt]
        if not nxt:
            db.run("DELETE FROM wild WHERE id=?", (row["wild_id"],))
            reschedule(uid)
    elif bt.over and bt.result == "fled":
        db.run("DELETE FROM wild WHERE id=?", (row["wild_id"],))
        reschedule(uid)

    _save(row["id"], bt)
    row = db.q1("SELECT * FROM battle WHERE id=?", (row["id"],))
    out["battle"] = _view(d, row, bt)
    return out


@router.post("/api/battle/{bid}/switch")
def switch(bid: int, body: SwitchIn, ctx=Depends(deps.current)):
    """쓰러졌을 때 다음 포켓몬을 내보낸다.

    이 게임에는 자유 교체가 없다. 내 포켓몬이 쓰러졌을 때만 다음 애가
    나온다. 그래서 여기서 되살려도 되는 배틀은 'lost' 로 끝난 것뿐이다.

    예전에는 이 검사가 없어서 도망쳤거나(fled) 잡고 끝난(caught) 배틀도
    되살아났다. 그때는 야생이 이미 지워진 뒤라, 되살려 다시 이기면
    경험치와 노력치와 도구를 한 번 더 받을 수 있었다. 아직 안 끝난
    배틀(active)도 마찬가지로 막는다 - 그걸 허용하면 턴을 쓰지 않고
    체력만 가득 채우는 수가 된다.
    """
    uid = ctx["user"]["id"]
    d = deps.dex()
    row = db.q1("SELECT * FROM battle WHERE id=? AND user_id=?", (bid, uid))
    if not row:
        raise HTTPException(404, "그런 배틀이 없습니다.")
    if row["state"] != "done" or row["result"] != "lost":
        raise HTTPException(409, "지금은 교체할 수 없습니다.")
    exp = auth.parse_iso(row["expires_at"])
    if exp and exp < _now():
        raise HTTPException(410, "배틀이 시간 초과로 끝났습니다.")
    if not db.q1("SELECT id FROM wild WHERE id=?", (row["wild_id"],)):
        raise HTTPException(410, "야생 포켓몬은 이미 떠났습니다.")
    if body.pokemon == row["mine_id"]:
        raise HTTPException(409, "방금 쓰러진 포켓몬입니다.")
    mine = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=? AND on_desktop=1",
                 (body.pokemon, uid))
    if not mine:
        raise HTTPException(404, "데리고 있는 포켓몬이 아닙니다.")

    _me, foe = _fighters(d, row)
    if not foe.alive():
        raise HTTPException(409, "상대가 이미 쓰러졌습니다.")
    new_me = B.Fighter(d, db.row_to_mon(mine))
    bt = B.Battle(d, new_me, foe, deps.RNG)
    bt.turn_no = row["turn"]
    db.run("UPDATE battle SET mine_id=?, me=?, state='active', result=NULL"
           " WHERE id=?", (mine["id"], json.dumps(_dump(new_me)), row["id"]))
    row = db.q1("SELECT * FROM battle WHERE id=?", (row["id"],))
    return {"battle": _view(d, row, bt),
            "events": [{"t": "send", "who": "me", "name": new_me.name,
                        "text": "가라, %s!" % new_me.name}]}


@router.post("/api/battle/{bid}/ball")
def throw_ball(bid: int, body: BallIn, ctx=Depends(deps.current)):
    """배틀 중에 몬스터볼을 던진다. 체력을 깎아뒀으면 훨씬 잘 잡힌다."""
    uid = ctx["user"]["id"]
    d = deps.dex()
    row = _load(ctx, bid)
    me, foe = _fighters(d, row)

    hour = body.hour if 0 <= body.hour <= 23 else None
    # 드림볼처럼 상대의 상태를 보는 볼이 있다. 지금 모습을 같이 넘긴다.
    wild_view = dict(foe.mon)
    wild_view["status"] = "SLP" if foe.status == "sleep" else (foe.status or "")
    ball, bonus, balls = _take_ball(uid, ctx["user"]["balls"], body.ball,
                                    wild_view, me.mon, row["turn"], hour)

    sp = d.get(foe.mon["species"])
    hp_ratio = foe.hp / float(foe.maxhp) if foe.maxhp else 1.0
    # 잠들거나 얼면 2배, 그 밖의 상태이상은 1.5배 (본가와 같다)
    status_bonus = 2.0 if foe.status in ("sleep", "freeze") else \
        (1.5 if foe.status in ("paralysis", "poison", "burn") else 1.0)
    caught, shakes = P.catch_attempt(sp, foe.mon, deps.RNG, bonus,
                                     hp_ratio, status_bonus)

    out = {"caught": caught, "shakes": shakes, "balls": balls,
           "hpRatio": round(hp_ratio, 3)}
    if not caught:
        out["message"] = ["앗! 포켓몬이 튀어나와버렸다!",
                          "이런! 포켓몬이 볼에서 나와버렸다!",
                          "아앗! 조금만 더 하면 잡을 수 있었는데!",
                          "아깝다! 다 잡았다고 생각했는데!"][min(shakes, 3)]
        ev = []
        foe_only_turn(d, me, foe, ev)          # 볼을 던진 턴에도 상대는 움직인다
        out["events"] = ev
        bt = B.Battle(d, me, foe, deps.RNG)
        bt.turn_no = row["turn"] + 1
        if not me.alive():
            bt.over, bt.result = True, "lost"
            ev.append({"t": "faint", "who": "me",
                       "text": "%s 은(는) 쓰러졌다!" % me.name})
        _save(row["id"], bt)
        row = db.q1("SELECT * FROM battle WHERE id=?", (row["id"],))
        out["battle"] = _view(d, row, bt)
        return out

    extra = items.ball_extra(ball)
    if extra.get("happiness"):
        foe.mon["happiness"] = extra["happiness"]
    caught_mon, where = store_caught(uid, foe.mon)
    db.run("UPDATE battle SET state='done', result='caught' WHERE id=?", (row["id"],))
    db.run("DELETE FROM wild WHERE id=?", (row["wild_id"],))
    db.run("INSERT INTO wild_state (user_id, caught) VALUES (?,1)"
           " ON CONFLICT(user_id) DO UPDATE SET caught=caught+1", (uid,))
    items.mark_seen(uid, foe.mon["species"], True, auth.now_iso())
    drop = _drop(uid, foe.mon, config.DROP_ON_CATCH)
    if drop:
        out["drop"] = drop
    out["money"] = items.money(uid)
    out["bag"] = items.bag_get(uid)
    reschedule(uid)
    out["pokemon"] = caught_mon
    out["where"] = where
    out["message"] = "신난다! %s 을(를) 잡았다!" % foe.name
    if where == "box":
        out["message"] += " 자리가 없어서 PC 박스로 보냈다."
    return out


@router.post("/api/battle/{bid}/run")
def run_away(bid: int, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    d = deps.dex()
    row = _load(ctx, bid)
    me, foe = _fighters(d, row)
    bt = B.Battle(d, me, foe, deps.RNG)
    bt.turn_no = row["turn"]

    if bt.try_run():
        bt.over, bt.result = True, "fled"
        _save(row["id"], bt)
        db.run("DELETE FROM wild WHERE id=?", (row["wild_id"],))
        reschedule(uid)
        row = db.q1("SELECT * FROM battle WHERE id=?", (row["id"],))
        return {"escaped": True,
                "events": [{"t": "flee", "who": "me", "text": "무사히 도망쳤다!"}],
                "battle": _view(d, row, bt)}

    ev = [{"t": "msg", "text": "도망칠 수 없었다!"}]
    foe_only_turn(d, me, foe, ev)
    bt.turn_no += 1
    if not me.alive():
        bt.over, bt.result = True, "lost"
        ev.append({"t": "faint", "who": "me", "text": "%s 은(는) 쓰러졌다!" % me.name})
    _save(row["id"], bt)
    row = db.q1("SELECT * FROM battle WHERE id=?", (row["id"],))
    return {"escaped": False, "events": ev, "battle": _view(d, row, bt)}
