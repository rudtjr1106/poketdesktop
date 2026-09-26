# -*- coding: utf-8 -*-
"""가방 · 상점 · 도구 사용 API.

돈이 오가는 곳이라 값은 전부 서버가 정한다. 클라이언트가 보내는 건
'무엇을 몇 개' 뿐이고, 가격·재고·잔액은 여기서만 본다.

가방과 지갑을 깎을 때는 `AND count >= ?` / `AND money >= ?` 를 붙인
UPDATE 한 방으로 처리한다. 읽고-확인하고-쓰면 두 요청이 겹쳤을 때
같은 도구를 두 번 쓸 수 있다.
"""
import datetime
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common import korean
from common import pokelogic as P

from . import config, db, deps, eggs, evolution, items

router = APIRouter()

MAX_QTY = 999
# 한 번에 팔 수 있는 가짓수. 가방에 들어올 수 있는 종류보다 넉넉하다.
MAX_SELL_LINES = 100


class BuyIn(BaseModel):
    item: str
    count: int = 1


class SellIn(BaseModel):
    item: str
    count: int = 1


class SellLine(BaseModel):
    item: str
    count: int = 1


class SellManyIn(BaseModel):
    lines: list = []      # [{"item": "STARDUST", "count": 3}, ...]


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


@router.post("/api/shop/sell-many")
def sell_many(body: SellManyIn, me=Depends(deps.current)):
    """여러 도구를 한 번에 판다. 가방에서 골라 놓고 한 번에 넘긴다.

    **다 되거나 아무것도 안 되거나.** 하나라도 값이 없거나 개수가 모자라면
    아무것도 팔지 않는다. 절반만 팔리고 거절 문구가 뜨면, 무엇이 팔렸는지
    알 수가 없다.

    그래서 먼저 전부 확인하고, 그다음에 꺼낸다. 꺼내다 실패하면(그사이 다른
    창에서 썼다) 꺼낸 것을 도로 넣는다.
    """
    uid = me["user"]["id"]
    lines = body.lines or []
    if not lines:
        raise HTTPException(400, "팔 물건을 고르세요.")
    if len(lines) > MAX_SELL_LINES:
        raise HTTPException(400, "한 번에 %d가지까지 팔 수 있습니다." % MAX_SELL_LINES)

    want = []
    seen = set()
    for raw in lines:
        line = SellLine(**raw) if isinstance(raw, dict) else raw
        it = items.get(line.item)
        if not it:
            raise HTTPException(404, "그런 도구가 없습니다.")
        if it["id"] in seen:
            raise HTTPException(400, "%s이(가) 두 번 들어 있습니다." % it["kr"])
        seen.add(it["id"])
        n = _qty(line.count)
        price = items.sell_price(it["id"])
        if price <= 0:
            raise HTTPException(400, "%s은(는) 팔 수 없습니다." % it["kr"])
        want.append((it, n, price))

    bag = items.bag_get(uid)
    for it, n, _price in want:
        if int(bag.get(it["id"], 0)) < n:
            raise HTTPException(400, "%s이(가) 모자랍니다." % it["kr"])

    took, total, sold = [], 0, []
    for it, n, price in want:
        if not items.bag_take(uid, it["id"], n):
            for back_id, back_n in took:            # 그사이 바뀌었다. 도로 넣는다.
                items.bag_add(uid, back_id, back_n)
            raise HTTPException(400, "%s이(가) 모자랍니다." % it["kr"])
        took.append((it["id"], n))
        total += price * n
        sold.append({"item": it["id"], "kr": it["kr"], "count": n,
                     "earned": price * n})
    items.money_add(uid, total)

    kinds = len(sold)
    pieces = sum(x["count"] for x in sold)
    if kinds == 1:
        msg = "%s %d개를 팔아 %d원을 받았다!" % (sold[0]["kr"], pieces, total)
    else:
        msg = "%s 외 %d가지 %d개를 팔아 %d원을 받았다!" % (
            sold[0]["kr"], kinds - 1, pieces, total)
    return {"ok": True, "earned": total, "sold": sold,
            "message": korean.natural(msg), **_wallet(uid)}


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

    # **뽑기권은 대상이 없다.** 포켓몬을 고르라고 막기 전에 처리한다.
    # 먼저 가방에서 빼고 준다 - 반대로 하면 알을 주고 표가 안 빠질 때
    # 공짜로 계속 뽑을 수 있다. 주는 데서 터지면 표를 돌려준다.
    if kind == "ticket":
        if not items.bag_take(uid, it["id"], 1):
            raise HTTPException(400, "%s이(가) 없습니다." % it["kr"])
        try:
            out = _use_ticket(uid, it, eff)
        except Exception:                                   # noqa: BLE001
            items.bag_add(uid, it["id"], 1)
            raise
        out.update(_wallet(uid))
        out["message"] = korean.natural(out.get("message", ""))
        return out

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
    elif kind == "shiny":
        out = _use_shiny(uid, it, mon)
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


def _use_ticket(uid, it, eff):
    """뽑기권. 정해진 확률로 정해진 종의 알을 준다. 대상 포켓몬이 없다.

    **알은 레이드에서 이겼을 때와 똑같은 길로 준다**(eggs.give) - 무엇이
    들어 있는지 화면에 밝혀지고, 파티에 자리가 있으면 바로 올라간다.
    """
    chance = float(eff.get("chance") or 0)
    species = eff.get("species")
    kind = eff.get("eggKind") or "legendary"
    name = (deps.dex().get(species) or {}).get("kr") or species
    if random.random() >= chance:
        return {"ok": True, "won": False,
                "message": "%s을(를) 썼지만 이번에는 꽝이었다..." % it["kr"]}
    eggs.give(uid, kind, species=species, known=True)
    return {"ok": True, "won": True, "species": species, "eggKr": name,
            "message": "%s 알을 받았다!" % name}


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
    """이상한사탕 — 레벨 +1. 올라간 레벨로 진화 조건도 같이 본다.

    최고 레벨이면 레벨은 못 올리지만 **진화할 수 있으면 진화시킨다** (본가
    8세대부터 같다). Lv.100 으로 잡혀 진화를 못 한 포켓몬을 풀어 주는 길이다.
    진화할 것도 없으면 사탕을 안 쓴다.
    """
    if mon["level"] >= P.LEVEL_MAX:
        b = evolution.check_level(dex, mon, hour)
        if not b:
            raise HTTPException(400, "이미 최고 레벨입니다.")
        before = mon["species"]
        got = evolution.apply(uid, mon, b, dex, _now())
        info = evolution.public(dex, before, b["to"], got.get("learned") or [],
                                got.get("pendingIds") or [])
        return {"ok": True, "level": mon["level"], "learned": [], "evolve": info,
                "message": "축하합니다! %s은(는) %s(으)로 진화했다!"
                           % (info["fromKr"], info["toKr"])}
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
    got = evolution.apply(uid, mon, b, dex, _now())
    info = evolution.public(dex, before, b["to"],
                            got.get("learned") or [], got.get("pendingIds") or [])
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


def _use_shiny(uid, it, mon):
    """이로치사탕 — 몸 색만 이로치로 바꾼다. 능력은 그대로다.

    시즌 보상으로만 준다(상점·드랍에 없다). 이미 이로치면 사탕을 안 쓴다.
    **UPDATE 에 shiny=0 을 건다** - 두 창에서 같은 포켓몬에게 동시에 쓰면
    한쪽만 바뀌고 다른 쪽은 여기서 막혀 사탕이 남는다.
    """
    name = mon.get("nickname") or deps.dex().name(mon["species"])
    if mon.get("shiny"):
        raise HTTPException(400, "%s은(는) 이미 이로치다." % name)
    cur = db.run("UPDATE pokemon SET shiny=1 WHERE id=? AND user_id=? AND shiny=0",
                 (mon["id"], uid))
    if getattr(cur, "rowcount", 1) == 0:
        raise HTTPException(400, "%s은(는) 이미 이로치다." % name)
    return {"ok": True, "shiny": True,
            "message": "%s의 몸 색이 바뀌었다! 반짝이는 이로치가 되었다!" % name}


# ---------------------------------------------------------------- 거들기
_STAT_KR = {"hp": "HP", "atk": "공격", "def": "방어",
            "spa": "특수공격", "spd": "특수방어", "spe": "스피드"}


def _stat_kr(s):
    return _STAT_KR.get(s, s)


def _json(o):
    import json
    return json.dumps(o)
