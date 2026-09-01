# -*- coding: utf-8 -*-
"""가방 · 상점 · 도구 사용 API.

돈이 오가는 곳이라 값은 전부 서버가 정한다. 클라이언트가 보내는 건
'무엇을 몇 개' 뿐이고, 가격·재고·잔액은 여기서만 본다.

가방과 지갑을 깎을 때는 `AND count >= ?` / `AND money >= ?` 를 붙인
UPDATE 한 방으로 처리한다. 읽고-확인하고-쓰면 두 요청이 겹쳤을 때
같은 도구를 두 번 쓸 수 있다.
"""
import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common import korean
from common import pokelogic as P

from . import config, db, deps, evolution, items

router = APIRouter()

MAX_QTY = 999


class BuyIn(BaseModel):
    item: str
    count: int = 1


class SellIn(BaseModel):
    item: str
    count: int = 1


class UseIn(BaseModel):
    item: str
    pokemon: int = 0
    stat: str = ""       # 은색병뚜껑처럼 능력을 골라야 하는 것
    hour: int = -1       # 클라이언트의 시각 (낮/밤 조건용)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()


def _qty(n):
    n = int(n or 0)
    if n < 1 or n > MAX_QTY:
        raise HTTPException(400, "개수는 1~%d 사이여야 합니다." % MAX_QTY)
    return n


def _mon(uid, pid):
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
    if not r:
        raise HTTPException(404, "그런 포켓몬이 없습니다.")
    return db.row_to_mon(r)


def _in_battle(uid, pid):
    return db.q1("SELECT id FROM battle WHERE user_id=? AND state='active'"
                 " AND mine_id=?", (uid, pid)) is not None


def _wallet(uid):
    return {"money": items.money(uid), "bag": items.bag_get(uid)}


# ---------------------------------------------------------------- 가방
@router.get("/api/bag")
def bag(me=Depends(deps.current)):
    # 돈도 볼도 사용자 행에 이미 들어 있다. 여기는 아무것도 바꾸지 않는
    # 순수 조회라 다시 읽을 이유가 없다 - 왕복 두 번이 그냥 날아간다.
    # (사고팔기 뒤에 쓰는 _wallet 은 다르다. 거기서는 값이 방금 바뀌었으므로
    #  반드시 다시 읽어야 한다.)
    u = me["user"]
    return {"bag": items.bag_get(u["id"], u["balls"]), "money": u["money"],
            "balls": u["balls"]}


@router.get("/api/shop")
def shop(me=Depends(deps.current)):
    """상점에 뭐가 있고 얼마인지. 가격은 본가 프렌들리샵 값 그대로."""
    u = me["user"]
    # 돈도 볼도 사용자 행에 이미 들어 있다. 다시 읽으면 왕복이 두 번 는다.
    return {"items": items.public_list(), "money": u["money"],
            "bag": items.bag_get(u["id"], u["balls"]),
            "sellRate": config.SELL_RATE}


# ---------------------------------------------------------------- 사고팔기
@router.post("/api/shop/buy")
def buy(body: BuyIn, me=Depends(deps.current)):
    uid = me["user"]["id"]
    n = _qty(body.count)
    it = items.get(body.item)
    if not it:
        raise HTTPException(404, "그런 도구가 없습니다.")
    price = items.buy_price(it["id"])
    if price <= 0:
        raise HTTPException(400, "%s은(는) 팔지 않는 물건입니다." % it["kr"])
    total = price * n
    if not items.money_take(uid, total):
        raise HTTPException(400, "돈이 모자랍니다. (%d원 필요)" % total)
    items.bag_add(uid, it["id"], n)
    return {"ok": True, "spent": total,
            "message": korean.natural("%s %d개를 샀다!" % (it["kr"], n)),
            **_wallet(uid)}


@router.post("/api/shop/sell")
def sell(body: SellIn, me=Depends(deps.current)):
    uid = me["user"]["id"]
    n = _qty(body.count)
    it = items.get(body.item)
    if not it:
        raise HTTPException(404, "그런 도구가 없습니다.")
    price = items.sell_price(it["id"])
    if price <= 0:
        raise HTTPException(400, "%s은(는) 팔 수 없습니다." % it["kr"])
    if not items.bag_take(uid, it["id"], n):
        raise HTTPException(400, "%s이(가) 모자랍니다." % it["kr"])
    total = price * n
    items.money_add(uid, total)
    return {"ok": True, "earned": total,
            "message": korean.natural("%s %d개를 팔아 %d원을 받았다!"
                                      % (it["kr"], n, total)),
            **_wallet(uid)}


# ---------------------------------------------------------------- 사용
@router.post("/api/bag/use")
def use(body: UseIn, me=Depends(deps.current)):
    uid = me["user"]["id"]
    it = items.get(body.item)
    if not it:
        raise HTTPException(404, "그런 도구가 없습니다.")
    eff = it.get("effect", {})
    kind = eff.get("kind")

    if kind in ("sell", "ball"):
        raise HTTPException(400, "%s은(는) 여기서 쓸 수 없습니다." % it["kr"])
    if items.bag_count(uid, it["id"]) <= 0:
        raise HTTPException(400, "%s이(가) 없습니다." % it["kr"])

    mon = _mon(uid, body.pokemon) if body.pokemon else None
    if mon is None:
        raise HTTPException(400, "어느 포켓몬에게 쓸지 골라 주세요.")
    if _in_battle(uid, mon["id"]):
        raise HTTPException(400, "배틀 중에는 쓸 수 없습니다.")

    hour = body.hour if 0 <= body.hour <= 23 else None
    dex = deps.dex()

    if kind == "ev":
        out = _use_ev(uid, it, eff, mon)
    elif kind == "iv":
        out = _use_iv(uid, it, eff, mon, body.stat)
    elif kind == "level":
        out = _use_level(uid, it, eff, mon, dex, hour)
    elif kind == "stone":
        out = _use_stone(uid, it, mon, dex, hour)
    elif kind == "noevolve":
        out = _use_everstone(uid, it, mon)
    else:
        raise HTTPException(400, "%s은(는) 아직 쓸 수 없습니다." % it["kr"])

    # keep 이면 쓰고도 없어지지 않는다. 변함없는돌은 진화 잠금을 껐다
    # 켰다 하는 표시라서, 잠글 때도 풀 때도 돌이 남아 있어야 한다.
    # 예전에는 이 검사가 없어서 한 번 잠갔다 푸는 데 돌 두 개가 사라졌다.
    if not out.get("keep") and not items.bag_take(uid, it["id"], 1):
        raise HTTPException(400, "%s이(가) 없습니다." % it["kr"])
    fresh = _mon(uid, mon["id"])
    out.update(_wallet(uid))
    out["pokemon"] = deps.decorate(fresh)
    out["message"] = korean.natural(out.get("message", ""))
    return out


def _use_ev(uid, it, eff, mon):
    stat = eff["stat"]
    amount = int(eff["amount"])
    before = items.clamp_evs(mon.get("evs") or {})
    after = items.add_evs(before, {stat: amount})
    got = after[stat] - before[stat]
    if got == 0:
        if amount > 0:
            raise HTTPException(400, "더 올릴 수 없습니다. (스탯당 %d, 총합 %d)"
                                % (config.EV_STAT_MAX, config.EV_TOTAL_MAX))
        raise HTTPException(400, "더 내릴 노력치가 없습니다.")
    db.run("UPDATE pokemon SET evs=? WHERE id=? AND user_id=?",
           (_json(after), mon["id"], uid))
    name = mon.get("nickname") or deps.dex().name(mon["species"])
    word = "올랐다" if got > 0 else "내려갔다"
    return {"ok": True, "evs": after,
            "message": "%s의 %s 노력치가 %d %s!"
                       % (name, _stat_kr(stat), abs(got), word)}


def _use_iv(uid, it, eff, mon, stat):
    if mon["level"] < config.HYPER_MIN_LEVEL:
        raise HTTPException(400, "하이퍼트레이닝은 레벨 %d부터 받을 수 있습니다."
                            % config.HYPER_MIN_LEVEL)
    hyper = dict(mon.get("hyper") or {})
    ivs = mon.get("ivs") or {}
    count = int(eff.get("count", 1))
    if count >= 6:
        targets = [s for s in items.STATS
                   if ivs.get(s, 0) < P.IV_MAX and not hyper.get(s)]
    else:
        if stat not in items.STATS:
            raise HTTPException(400, "어느 능력을 단련할지 골라 주세요.")
        if ivs.get(stat, 0) >= P.IV_MAX or hyper.get(stat):
            raise HTTPException(400, "%s은(는) 이미 최고치입니다." % _stat_kr(stat))
        targets = [stat]
    if not targets:
        raise HTTPException(400, "더 단련할 능력이 없습니다.")
    for s in targets:
        hyper[s] = True
    db.run("UPDATE pokemon SET hyper=? WHERE id=? AND user_id=?",
           (_json(hyper), mon["id"], uid))
    name = mon.get("nickname") or deps.dex().name(mon["species"])
    return {"ok": True, "hyper": hyper,
            "message": "%s의 %s이(가) 최고까지 단련되었다!"
                       % (name, ", ".join(_stat_kr(s) for s in targets))}


def _use_level(uid, it, eff, mon, dex, hour):
    """이상한사탕 — 레벨 +1. 올라간 레벨로 진화 조건도 같이 본다."""
    if mon["level"] >= P.LEVEL_MAX:
        raise HTTPException(400, "이미 최고 레벨입니다.")
    got = deps.set_level(uid, mon["id"],
                         mon["level"] + int(eff.get("amount", 1)), hour)
    if got is None:
        raise HTTPException(500, "도감에 없는 종입니다.")
    name = mon.get("nickname") or dex.name(mon["species"])
    out = {"ok": True, "level": got["level"], "learned": got["learned"],
           "message": "%s의 레벨이 %d이(가) 되었다!" % (name, got["level"])}
    if got.get("evolve"):
        out["evolve"] = got["evolve"]
        out["message"] += "  축하합니다! %s은(는) %s(으)로 진화했다!" % (
            got["evolve"]["fromKr"], got["evolve"]["toKr"])
    return out


def _use_stone(uid, it, mon, dex, hour):
    b = evolution.check_item(dex, mon, it["id"], hour)
    if not b:
        name = mon.get("nickname") or dex.name(mon["species"])
        raise HTTPException(400, "%s에게는 아무 일도 일어나지 않았다." % name)
    before = mon["species"]
    evolution.apply(uid, mon, b, dex, _now())
    info = evolution.public(dex, before, b["to"])
    return {"ok": True, "evolve": info,
            "message": "축하합니다! %s은(는) %s(으)로 진화했다!"
                       % (info["fromKr"], info["toKr"])}


def _use_everstone(uid, it, mon):
    """변함없는돌 — 껐다 켰다 한다. 본가에서는 지닌 물건이지만
    이 게임에는 지닌 물건이 없어서 표시를 뒤집는 방식으로 둔다."""
    on = not mon.get("noEvolve")
    db.run("UPDATE pokemon SET no_evolve=? WHERE id=? AND user_id=?",
           (int(on), mon["id"], uid))
    name = mon.get("nickname") or deps.dex().name(mon["species"])
    return {"ok": True, "noEvolve": on, "keep": True,
            "message": ("%s은(는) 이제 진화하지 않는다." % name) if on
                       else ("%s의 진화를 다시 허락했다." % name)}


# ---------------------------------------------------------------- 거들기
_STAT_KR = {"hp": "HP", "atk": "공격", "def": "방어",
            "spa": "특수공격", "spd": "특수방어", "spe": "스피드"}


def _stat_kr(s):
    return _STAT_KR.get(s, s)


def _json(o):
    import json
    return json.dumps(o)
