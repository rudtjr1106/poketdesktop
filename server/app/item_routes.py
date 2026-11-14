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

from . import boosts, config, db, deps, eggs, evolution, guild, items, rename, tms

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


class EvsIn(BaseModel):
    evs: dict = {}        # {능력: 맞출 값} - 안 적은 능력은 그대로 (2.1.3, 게시판 #450)
    buy: bool = False     # 모자란 도구를 상점 값에 사서 쓴다 (앱이 묻고 나서만 켠다)
    dry: bool = True      # 계획만 본다 (아무것도 안 바뀐다)
    cost: int = -1        # 앱이 물어보고 받은 값 (-1 = 안 봄). 그사이 가방이 바뀌어 값이 달라졌으면 쓰지 않는다


class UseIn(BaseModel):
    item: str
    pokemon: int = 0
    stat: str = ""       # 은색병뚜껑처럼 능력을 골라야 하는 것
    hour: int = -1       # 클라이언트의 시각 (낮/밤 조건용)
    form: str = ""       # 폼 도구로 고르는 모습 (로토무카탈로그·운석, 1.13). 빈 글자 = 원래 모습
    type: str = ""       # 타입 확정 기술머신 뽑기권 · 타입 스프레이(2.1.1)로 고른 타입
    name: str = ""       # 닉네임 변경권으로 바꿀 닉네임 (2.1.1)


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
    return deps.in_battle(uid, pid)         # 끝난 채 남은 줄은 세지 않는다 (1.10.4)


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
    bag = items.bag_get(u["id"], u["balls"])
    out = {"items": items.public_list(), "money": u["money"], "bag": bag,
           "sellRate": config.SELL_RATE}
    # 기술머신 뽑기권이 있으면 타입마다 아직 없는 기술머신 수 (1.13.1). 타입 확정 뽑기권을 쓸 때 고르는
    # 창이 '다 모은 타입' 을 빼고 남은 수를 적는다. 표가 없는 사람에게는 안 싣는다 - 묻는 값이 아니다.
    if any(bag.get(i, 0) > 0 for i, it in items.catalog().items()
           if (it.get("effect") or {}).get("kind") == "tmticket"):
        out["tmLeft"] = tm_left(u["id"])
    # 타입 스프레이가 켜져 있으면 가방 설명에 남은 시간을 적는다 (2.1.1)
    out["boosts"] = boosts.state(u["id"])
    # 랜덤 캡슐을 돈으로 (2.1.2 앱의 상점 맨 위 띠). 확률표는 길드 코인 상점의 것과 같다
    out["capsule"] = {"price": guild.SLOT_WON, "counts": list(guild.SLOT_COUNTS), "odds": guild.slot_odds()}
    return out


# ---------------------------------------------------------------- 랜덤 캡슐 - 돈으로 (2.1.1 서버 · 2.1.2 앱)
# 한 번 10,000원 · 10번 100,000원 (사용자 결정 11/04). 상품 · 확률은 길드 코인으로 돌리는 것과 같다 (guild.slot).
# (11/04 처음에는 '랜덤 뽑기권' 을 랜덤 '기술머신' 뽑기권으로 잘못 읽어 돈으로 기술머신을 뽑는 띠와 뽑기권 판매를
#  냈다가 5분 만에 서버를 닫고 뺐다 - 사용자가 말한 것은 랜덤 캡슐이다.)
class CapsuleIn(BaseModel):
    count: int = 1


@router.get("/api/capsule/history")
def capsule_history(me=Depends(deps.current)):
    """내가 최근 뽑은 랜덤 캡슐 10번 (2.1.2 - 뽑기 기계 오른쪽 위, 코인 판 · 돈 판 함께)."""
    return {"history": guild.slot_history(me["user"]["id"])}


@router.post("/api/shop/capsule")
def capsule(body: CapsuleIn, me=Depends(deps.current)):
    uid = me["user"]["id"]
    out = guild.slot(uid, count=int(body.count), pay="money")
    out.update(_wallet(uid))
    return out


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

    if kind == "tmticket":
        out = _use_tm_ticket(uid, it, eff, body.type)
        out.update(_wallet(uid))
        out["message"] = korean.natural(out.get("message", ""))
        return out

    # 아르케 열쇠 아이템 (2.4.0) - 대상이 없고 없어지지 않는다. 쓴 때를 적고 의식을 본다 (조건 itemUsed)
    if kind == "arche":
        from . import arche
        out = arche.use_item(uid, it["id"])
        out.update(_wallet(uid))
        return out

    # 풀숲 부스트 · 닉네임 변경권 (2.1.1) - 이것도 대상이 없다
    if kind in ("lure", "rename"):
        out = {"lure": _use_lure, "rename": _use_rename}[kind](uid, it, eff, body)
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
    elif kind == "form":
        out = _use_form(uid, it, mon, dex, body.form)
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


# ---------------------------------------------------------------- 폼 도구 (1.13)
# 도구 -> (원래 모습으로 되돌리는 종). 다홍꿀은 춤추새를 원래 모습(이글이글스타일)으로 돌린다.
BASE_ITEM = {"REDNECTAR": "ORICORIO"}
NECTARS = {"REDNECTAR", "YELLOWNECTAR", "PINKNECTAR", "PURPLENECTAR"}
# 로토무: 폼마다 그 폼의 기술 (도감 forms 의 formMoves.sig). 원래 모습으로 돌아오면 다 잊는다.
ROTOM_SIGS = ("OVERHEAT", "HYDROPUMP", "BLIZZARD", "AIRSLASH", "LEAFSTORM")


def _name(mon, dex):
    return mon.get("nickname") or dex.name(mon["species"])


def _use_form(uid, it, mon, dex, choice):
    """폼 도구를 쓴다. 켜고 끄는 것(그라시데아꽃·비추는거울·굴레의항아리·지가르데큐브), 고르는 것
    (로토무카탈로그·운석), 꽃꿀(쓰면 없어진다). 합체 도구는 넣지 않았다 (2026-10-17 사용자 결정)."""
    iid = it["id"]
    forms = [m for m in (dex.forms_of.get(mon["species"]) or []) if m.get("useItem") == iid]
    if not forms and BASE_ITEM.get(iid) != mon["species"]:
        raise HTTPException(400, "%s은(는) %s에게 쓸 수 없습니다." % (it["kr"], _name(mon, dex)))
    cur = mon.get("form")
    if iid in BASE_ITEM:
        want = None                                        # 다홍꿀: 원래 모습으로
    elif len(forms) == 1:
        # 켜고 끄기. 꽃꿀은 그 모습으로만 바꾼다 (이미 그 모습이면 쓸 필요가 없다)
        want = forms[0]["form"] if (cur != forms[0]["form"] or iid in NECTARS) else None
    else:
        keys = [m["form"] for m in forms]
        want = (choice or "").upper() or None
        if want is not None and want not in keys:
            raise HTTPException(400, "고를 수 있는 모습이 아닙니다.")
    if want == cur:
        raise HTTPException(409, "이미 그 모습입니다.")
    moves = list(mon.get("moves") or [])
    pending = list(mon.get("pending") or [])
    learned = None
    if mon["species"] == "ROTOM":
        moves, pending, learned = _rotom_moves(moves, pending, forms, want, dex)
    db.run("UPDATE pokemon SET form=?, moves=?, pending=? WHERE id=? AND user_id=?",
           (want, _json(moves), _json(pending), mon["id"], uid))
    name = _name(mon, dex)
    if want:
        fk = next((m.get("formKr") for m in forms if m["form"] == want), want)
        msg = "%s은(는) %s(으)로 모습이 바뀌었다!" % (name, fk)
    else:
        msg = "%s은(는) 원래 모습으로 돌아왔다!" % name
    if learned:
        msg += " %s을(를) 배웠다!" % dex.move_name(learned)
    return {"ok": True, "form": want, "keep": iid not in NECTARS, "message": msg}


def _rotom_moves(moves, pending, forms, want, dex):
    """로토무가 모습을 바꾸면 그 폼의 기술로 갈아 끼운다 (본가와 같다). 자리가 없으면 배우려고 기다린다."""
    sig = next(((m.get("formMoves") or {}).get("sig") for m in forms if m["form"] == want), None)
    slot = next((i for i, k in enumerate(moves) if k in ROTOM_SIGS), None)
    moves = [k for k in moves if k not in ROTOM_SIGS or k == sig]
    pending = [k for k in pending if k not in ROTOM_SIGS]
    if not sig or sig in moves or not dex.move(sig):
        return moves or ["THUNDERSHOCK"], pending, None
    if len(moves) < 4:
        moves.insert(min(slot if slot is not None else len(moves), len(moves)), sig)
        return moves, pending, sig
    return moves, pending + [sig], None


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


def tm_left(uid):
    """아직 없는 기술머신 수, 타입마다 {타입: 개수}. 다 모은 타입은 안 적는다."""
    have = tms.owned(uid)
    out = {}
    for no, t in tms.all_tms().items():
        if no not in have:
            out[t["type"]] = out.get(t["type"], 0) + 1
    return out


def _left_kr(secs):
    m = int((secs + 59) // 60)
    return ("%d시간 %d분" % (m // 60, m % 60) if m % 60 else "%d시간" % (m // 60)) if m >= 60 else "%d분" % m


def _use_lure(uid, it, eff, body):
    """타입 스프레이 (2.1.1, 게시판 #426): 고른 타입이 풀숲에 훨씬 자주 나온다 (boosts). 거절할 일을 다 본 뒤 뺀다."""
    want = (body.type or "").strip().upper()
    types = deps.dex().raw.get("types") or {}
    if not want:
        raise HTTPException(400, "어느 타입을 부를지 골라 주세요.")
    if want not in types or want == "STELLAR":
        raise HTTPException(400, "그런 타입은 없습니다.")
    minutes = int(eff.get("minutes") or 60)
    s = boosts.state(uid)
    if s["lureType"] == want and not boosts.room(s["lureLeft"], minutes):
        raise HTTPException(409, "이미 %s 남아 있습니다 (%d시간까지만 쌓입니다)."
                            % (_left_kr(s["lureLeft"]), boosts.MAX_LEFT_MIN // 60))
    if not items.bag_take(uid, it["id"], 1):
        raise HTTPException(400, "%s이(가) 없습니다." % it["kr"])
    try:
        secs = boosts.lure(uid, want, minutes)
    except Exception:                                       # noqa: BLE001
        items.bag_add(uid, it["id"], 1)
        raise
    kr = types.get(want, {}).get("kr") or want
    return {"ok": True, "won": True, "boosts": boosts.state(uid),
            "message": "앞으로 %s 동안 %s 타입 포켓몬이 풀숲에 훨씬 자주 나타난다!" % (_left_kr(secs), kr)}


def _use_rename(uid, it, eff, body):
    """닉네임 변경권 (2.1.1). 검사 · 표 빼기 · 이름 바꾸기가 한 트랜잭션이다 (rename.apply)."""
    got = rename.apply(uid, body.name)
    return {"ok": True, "won": True, "username": got["username"],
            "message": "닉네임이 '%s' 이(가) 되었습니다. 다음에 로그인할 때는 새 닉네임을 쓰세요 (비밀번호는 그대로)."
                       % got["username"]}


def _use_tm_ticket(uid, it, eff, want):
    """기술머신 뽑기권 (1.13.1, 랭크 시즌 보상). 아직 없는 기술머신 하나를 무작위로 준다.

    · 랜덤: 358개 가운데 아직 없는 것 전부에서.
    · 타입 확정(pickType): 고른 타입 가운데 아직 없는 것에서.

    **가진 것은 안 준다** - 살 수도 팔 수도 없는 물건이라 가진 것이 나오면 표만 날아간 것과 같다
    (드랍과 같은 규칙, tms.roll_drop). 그래서 뽑을 것이 없으면 **표를 빼기 전에** 거절한다.
    표는 먼저 빼고 준다 - 주는 데서 터지면 돌려준다 (알 뽑기권과 같은 순서).
    """
    typed = bool(eff.get("pickType"))
    want = (want or "").strip().upper()
    every = tms.all_tms()
    if typed:
        kinds = set(t["type"] for t in every.values())
        if not want:
            raise HTTPException(400, "어느 타입의 기술머신을 받을지 골라 주세요.")
        if want not in kinds:
            raise HTTPException(400, "그런 타입의 기술머신은 없습니다.")
    have = tms.owned(uid)
    pool = [no for no, t in sorted(every.items())
            if no not in have and (not typed or t["type"] == want)]
    if not pool:
        if typed:
            kr = (deps.dex().raw.get("types") or {}).get(want, {}).get("kr") or want
            raise HTTPException(400, "%s 타입 기술머신은 이미 다 모았습니다. 다른 타입을 골라 주세요." % kr)
        raise HTTPException(400, "기술머신을 이미 다 모아서 뽑을 것이 없습니다.")
    if not items.bag_take(uid, it["id"], 1):
        raise HTTPException(400, "%s이(가) 없습니다." % it["kr"])
    try:
        random.shuffle(pool)
        no = next((n for n in pool if tms.give(uid, n)), None)
    except Exception:                                       # noqa: BLE001
        items.bag_add(uid, it["id"], 1)
        raise
    if no is None:                      # 그사이 다른 창에서 다 받았다 - 표를 돌려준다
        items.bag_add(uid, it["id"], 1)
        if typed:
            raise HTTPException(400, "그 타입 기술머신은 이미 다 모았습니다. 다른 타입을 골라 주세요.")
        raise HTTPException(400, "기술머신을 이미 다 모아서 뽑을 것이 없습니다.")
    return {"ok": True, "won": True, "tm": tms.public(no), "tmNew": tms.new_count(uid),
            "message": "%s을(를) 얻었다!" % tms.label(no)}


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


# ---------------------------------------------------------------- 노력치 한 번에 맞추기 (2.1.3, 게시판 #450)
# 능력마다 맞출 값을 적으면, 지금 도구를 하나씩 쓸 때와 **똑같은 도구 · 똑같은 값**으로 한 번에 맞춘다.
# 깎아 주는 것도 공짜도 없다 - 모자란 도구는 상점 값 그대로 사서 바로 쓴다 (앱이 묻고 나서만).
#
# 능력 하나를 e 에서 t 로 (도구는 items.json 의 효과로 찾는다 - 붙박이 id 없이):
#   내릴 때  열매(-10)를 t 이하가 될 때까지 (0 아래로는 안 간다), 모자란 만큼 깃털(+1)로 다시 올린다
#   올릴 때  가진 영양제(+10) → 가진 깃털(+1) 순으로 먼저 쓰고, 남은 만큼만 산다 (10씩은 영양제, 나머지는 깃털)
#           - 영양제 하나(10,000원) = 깃털 열 개(1,000원 × 10)라 가진 깃털을 먼저 써도 값은 같고 살 것만 준다
#   내리는 능력을 먼저, 올리는 능력을 나중에 쓴다 - 그래야 도중에 총합 510 을 넘지 않는다 (하나씩 쓸 때 막히는 길이 없다)
EV_UP, EV_ONE, EV_DOWN = 10, 1, -10


def ev_items():
    """{(능력, 양): 도구 id}. 같은 (능력, 양)이 둘이면 싼 것."""
    out = {}
    for iid, it in sorted(items.catalog().items()):
        eff = it.get("effect") or {}
        if eff.get("kind") != "ev":
            continue
        key = (eff.get("stat"), int(eff.get("amount") or 0))
        if key not in out or 0 < items.buy_price(iid) < items.buy_price(out[key]):
            out[key] = iid
    return out


def ev_targets(raw, before):
    """보내온 {능력: 값} 을 확인해 여섯 능력 전부의 목표로. 안 적은 능력은 지금 값."""
    if not isinstance(raw, dict) or not raw:
        raise HTTPException(400, "맞출 노력치를 적어 주세요.")
    out = dict(before)
    for k, v in raw.items():
        s = str(k).strip().lower()
        if s not in items.STATS:
            raise HTTPException(400, "그런 능력은 없습니다.")
        if isinstance(v, bool) or not isinstance(v, int):
            raise HTTPException(400, "노력치는 정수로 적어 주세요.")
        if not 0 <= v <= config.EV_STAT_MAX:
            raise HTTPException(400, "노력치는 능력마다 0~%d 사이입니다." % config.EV_STAT_MAX)
        out[s] = v
    total = sum(out.values())
    if total > config.EV_TOTAL_MAX:
        raise HTTPException(400, "노력치 총합은 %d까지입니다. (지금 %d)" % (config.EV_TOTAL_MAX, total))
    return out


def ev_plan(before, target, bag):
    """before -> target 에 쓸 도구들, 쓰는 차례대로. [{item, stat, amount, count, owned, buy}]

    owned = 가방에서 꺼내 쓸 개수, buy = 사서 쓸 개수 (count = owned + buy). 도구 하나는 한 줄에만 나온다
    (능력마다 도구가 따로이고, 한 능력은 올리거나 내리거나 한쪽뿐이다).
    """
    ids = ev_items()
    downs, ups = [], []

    def line(out, stat, amount, owned, buy):
        if owned + buy <= 0:
            return
        iid = ids.get((stat, amount))
        if not iid:
            raise HTTPException(500, "노력치 도구 목록이 맞지 않습니다.")
        out.append({"item": iid, "stat": stat, "amount": amount,
                    "count": owned + buy, "owned": owned, "buy": buy})

    def have(stat, amount):
        return int(bag.get(ids.get((stat, amount)), 0) or 0)

    for s in items.STATS:
        e, t = int(before.get(s, 0)), int(target.get(s, 0))
        if t < e:
            n = (e - t + 9) // 10                      # 열매: t 이하가 될 때까지
            up = t - max(0, e - 10 * n)                # 0~9: 깃털로 다시 올린다
            own = min(have(s, EV_DOWN), n)
            line(downs, s, EV_DOWN, own, n - own)
            own = min(have(s, EV_ONE), up)
            line(downs, s, EV_ONE, own, up - own)
        elif t > e:
            d = t - e
            own_v = min(have(s, EV_UP), d // 10)
            rest = d - 10 * own_v
            own_w = min(have(s, EV_ONE), rest)
            rest -= own_w
            line(ups, s, EV_UP, own_v, rest // 10)
            line(ups, s, EV_ONE, own_w, rest % 10)
    return downs + ups


def ev_simulate(before, plan):
    """계획을 **하나씩 쓸 때와 똑같이** (items.add_evs) 돌려 본다. 아무 일도 안 하는 도구가 끼면 None
    (하나씩 쓰면 '더 올릴 수 없습니다' 로 막히는 길이다)."""
    cur = items.clamp_evs(before)
    for ln in plan:
        for _ in range(ln["count"]):
            nxt = items.add_evs(cur, {ln["stat"]: ln["amount"]})
            if nxt[ln["stat"]] == cur[ln["stat"]]:
                return None
            cur = nxt
    return cur


@router.post("/api/pokemon/{pid}/evs")
def set_evs(pid: int, body: EvsIn, me=Depends(deps.current)):
    """노력치 한 번에 맞추기 (2.1.3, 게시판 #450). dry 면 계획만, 아니면 한 트랜잭션으로 쓴다:
    모자란 도구 값(돈) · 가방의 도구 · 노력치 - 하나라도 어긋나면 아무것도 안 바뀐다."""
    uid = me["user"]["id"]
    row = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
    if not row:
        raise HTTPException(404, "그런 포켓몬이 없습니다.")
    mon, raw = db.row_to_mon(row), row["evs"]        # raw: 쓸 때 그사이 바뀌었는지 본다
    if _in_battle(uid, mon["id"]):
        raise HTTPException(400, "배틀 중에는 노력치를 바꿀 수 없습니다.")
    before = items.clamp_evs(mon.get("evs") or {})
    target = ev_targets(body.evs, before)
    plan = ev_plan(before, target, items.bag_get(uid))
    after = ev_simulate(before, plan)
    if after is None or after != target:
        raise HTTPException(500, "노력치 계획이 어긋났습니다. 운영자에게 알려 주세요.")
    cost = 0
    sellable = True
    for ln in plan:
        price = items.buy_price(ln["item"])
        ln.update(kr=items.name_of(ln["item"]), statKr=_stat_kr(ln["stat"]), price=price)
        if ln["buy"] and price <= 0:
            sellable = False
        cost += price * ln["buy"]
    used = sum(ln["count"] for ln in plan)
    owned = sum(ln["owned"] for ln in plan)
    short = used - owned
    money = items.money(uid)
    out = {"ok": True, "dry": bool(body.dry), "before": before, "evs": target, "plan": plan,
           "count": used, "owned": owned, "buyCount": short, "cost": cost,
           "buyable": sellable, "affordable": sellable and money >= cost, "money": money}
    if body.dry:
        return out

    if not plan:
        raise HTTPException(400, "바꿀 노력치가 없습니다.")
    if short and not sellable:
        raise HTTPException(400, "상점에서 팔지 않는 도구가 모자랍니다.")
    if short and not body.buy:
        raise HTTPException(409, "도구가 %d개 모자랍니다. 사서 쓰려면 확인해 주세요. (%s원)" % (short, format(cost, ",")))
    if body.cost >= 0 and body.cost != cost:
        raise HTTPException(409, "그사이 가방이 바뀌어 값이 %s원이 되었습니다. 다시 확인해 주세요." % format(cost, ","))
    if money < cost:
        raise HTTPException(400, "돈이 모자랍니다. (%s원 필요)" % format(cost, ","))
    conn = db.connect()
    try:
        if cost and conn.execute("UPDATE users SET money = money - ? WHERE id=? AND money >= ?",
                                 (cost, uid, cost)).rowcount <= 0:
            raise HTTPException(400, "돈이 모자랍니다. (%s원 필요)" % format(cost, ","))
        for ln in plan:
            if ln["owned"] and conn.execute(
                    "UPDATE bag SET count = count - ? WHERE user_id=? AND item=? AND count >= ?",
                    (ln["owned"], uid, ln["item"], ln["owned"])).rowcount <= 0:
                raise HTTPException(409, "그사이 %s이(가) 줄었습니다. 다시 해 주세요." % ln["kr"])
        # 계획을 짠 뒤 다른 창에서 노력치가 바뀌었으면(하나씩 쓰기 · 배틀) 덮어쓰지 않는다
        if conn.execute("UPDATE pokemon SET evs=? WHERE id=? AND user_id=? AND evs=?",
                        (_json(target), mon["id"], uid, raw)).rowcount <= 0:
            raise HTTPException(409, "그사이 노력치가 바뀌었습니다. 다시 해 주세요.")
        conn.commit()
    except Exception:
        try:
            conn.rollback()                                 # 열린 트랜잭션을 남기지 않는다 (쓰기 잠금, db.run 주석)
        except Exception:                                   # noqa: BLE001
            pass
        raise
    name = mon.get("nickname") or deps.dex().name(mon["species"])
    msg = "%s의 노력치를 맞췄다! 도구 %d개를 썼다." % (name, used)
    if short:
        msg += " (모자란 %d개는 %s원에 샀다)" % (short, format(cost, ","))
    out.update(_wallet(uid))
    out["pokemon"] = deps.decorate(_mon(uid, mon["id"]))
    out["message"] = korean.natural(msg)
    return out


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
            why = evolution.why_not(dex, mon, hour)
            raise HTTPException(400, korean.natural("이미 최고 레벨입니다." + (
                " %s. 조건이 맞을 때 쓰면 진화합니다." % why if why else "")))
        before = mon["species"]
        got = evolution.apply(uid, mon, b, dex, _now())
        info = evolution.public(dex, before, b["to"], got.get("learned") or [],
                                got.get("pendingIds") or [], form=b.get("form"))
        return {"ok": True, "level": mon["level"], "learned": [], "evolve": info,
                "message": "축하합니다! %s은(는) %s(으)로 진화했다!"
                           % (info["fromKr"], evolution.name_kr(info))}
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


def _use_swap(uid, it, eff, mon, dex):
    """변경권 - 정해진 종을 짝이 되는 종으로 바꾼다 (루나아라 변경권, 게시판 #370).

    코스모움이 밤에도 솔가레오로만 진화하던 버그의 보상. 진화와 같은 길(evolution.apply)로 바꾼다 -
    레벨 · 개체값 · 성격 · 친밀도는 그대로, 경험치는 새 곡선, 특성은 같은 자리, 도감에 올림.
    **도감의 진화표에는 안 넣는다.** 솔가레오가 '진화 전' 이 되면 진화의휘석이 붙는 등 다른 데가 틀어진다.
    전용기와 전용 Z크리스탈은 짝으로 갈아 준다 (메테오드라이브를 든 루나아라가 생기지 않게).
    """
    if mon["species"] not in (eff.get("from") or []):
        raise HTTPException(400, "%s은(는) %s에게 쓸 수 없습니다." % (it["kr"], _name(mon, dex)))
    sw = eff.get("moves") or {}
    mon = dict(mon, moves=[sw.get(m, m) for m in mon.get("moves") or []],
               pending=[sw.get(m, m) for m in mon.get("pending") or []])
    before, name = mon["species"], _name(mon, dex)
    got = evolution.apply(uid, mon, {"to": eff["swap"]}, dex, _now())
    held = (eff.get("held") or {}).get(mon.get("held") or "")
    if held:
        db.run("UPDATE pokemon SET held=? WHERE id=? AND user_id=?", (held, mon["id"], uid))
    info = evolution.public(dex, before, eff["swap"], got.get("learned") or [],
                            got.get("pendingIds") or [])
    return {"ok": True, "evolve": info,
            "message": "%s은(는) %s(으)로 바뀌었다!" % (name, info["toKr"])}


def _use_stone(uid, it, mon, dex, hour):
    eff = it.get("effect") or {}
    if eff.get("swap"):
        return _use_swap(uid, it, eff, mon, dex)
    b = evolution.check_item(dex, mon, it["id"], hour)
    if not b:
        name = mon.get("nickname") or dex.name(mon["species"])
        raise HTTPException(400, "%s에게는 아무 일도 일어나지 않았다." % name)
    before = mon["species"]
    got = evolution.apply(uid, mon, b, dex, _now())
    info = evolution.public(dex, before, b["to"],
                            got.get("learned") or [], got.get("pendingIds") or [], form=b.get("form"))
    return {"ok": True, "evolve": info,
            "message": "축하합니다! %s은(는) %s(으)로 진화했다!"
                       % (info["fromKr"], evolution.name_kr(info))}


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
