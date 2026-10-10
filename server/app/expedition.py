# -*- coding: utf-8 -*-
"""탐험 파견 (1.10.4) — 박스의 포켓몬을 몇 시간 보내 두면 도구를 가져온다.

    GET  /api/expedition                 지금 나가 있는 것들과 칸 수
    POST /api/expedition/send            보낸다 {pokemon, place, hours}
    POST /api/expedition/{id}/claim      돌아온 보따리를 받는다
    POST /api/expedition/claim           돌아온 것을 전부 받는다 (바탕화면의 보따리)
    POST /api/expedition/{id}/recall     불러들인다 (빈손으로 돌아온다)

규칙(어디로·얼마나·성공도·물건 수)은 common/expedition.py 에 있다 - 화면도 같은 것을 읽어
보내기 전에 미리 보여 준다. **여기서는 그 규칙대로 굴리고 적는다.**

## 시간은 서버 시계다

보낼 때 돌아올 시각(ends_at)을 적어 둔다. 프로그램을 꺼도 시간은 간다. 화면은 그 시각까지
남은 초를 받아 스스로 센다 (PC 시계가 틀려도 맞다 - '남은 초' 로 준다).

## 무엇을 가져오나는 받을 때 굴린다

미리 굴려 적어 두면 받기 전에 무엇이 들었는지 새어 나갈 길이 생긴다. 받는 순간 state 를
out -> done 으로 **한 문장으로** 바꾸고(같은 보따리를 두 번 못 받는다), 그다음에 굴려 가방에 넣는다.

## 나가 있는 포켓몬

돌아와서 보따리를 받기 전까지 '나가 있는' 것이다 (away_ids). 그동안은
  * 데리고 다닐 수 없다 (main.set_desktop, party.use) - 그래서 배틀에 못 나간다
  * 랭크 팀에 넣을 수 없다 (pvp.set_team). 이미 랭크 팀에 든 포켓몬은 보낼 수 없다
  * 놓아줄 수 없다 (main.release)
도구 쓰기·기술 가르치기·박스 옮기기는 그대로 된다.
"""
import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common import expedition as X
from common import korean

from . import db, deps, items, tms

router = APIRouter()

KEEP_DONE = 30              # 받은 기록을 사람마다 이만큼만 남긴다


def _now(now=None):
    return now or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def _iso(t):
    return t.isoformat()


def _parse(s):
    try:
        t = datetime.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------- 나가 있는 포켓몬
def away_ids(uid):
    """탐험에 나가 있는 포켓몬의 id (돌아왔어도 보따리를 받기 전이면 든다)."""
    return set(r["pokemon_id"] for r in db.q(
        "SELECT pokemon_id FROM expedition WHERE user_id=? AND state='out'", (uid,)))


def is_away(uid, pid):
    return db.q1("SELECT id FROM expedition WHERE user_id=? AND pokemon_id=? AND state='out'",
                 (uid, int(pid))) is not None


def _rows(uid):
    return db.q("SELECT * FROM expedition WHERE user_id=? AND state='out' ORDER BY id", (uid,))


# ---------------------------------------------------------------- 내보이기
def _mon_view(uid, pid):
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
    if r is None:
        return {"id": pid, "name": "?", "num": 0, "level": 0, "shiny": False, "types": []}
    mon = db.row_to_mon(r)
    sp = deps.dex().get(mon["species"]) or {}
    return {"id": pid, "name": mon.get("nickname") or sp.get("kr") or mon["species"],
            "species": mon["species"], "num": sp.get("num", 0), "level": mon["level"],
            "shiny": bool(mon.get("shiny")), "tint": mon.get("tint"),
            "types": list(sp.get("types") or [])}


def _view(uid, r, now):
    ends = _parse(r["ends_at"]) or now
    left = int((ends - now).total_seconds())
    total = max(1, int(r["hours"]) * 3600)
    return {"id": r["id"], "pokemon": _mon_view(uid, r["pokemon_id"]), "place": r["place"],
            "placeKr": (X.place(r["place"]) or {}).get("kr", r["place"]),
            "hours": r["hours"], "grade": r["grade"], "gradeKr": X.GRADE_KR.get(r["grade"], ""),
            "score": r["score"], "items": X.item_count(r["hours"], r["grade"]),
            "startedAt": r["started_at"], "endsAt": r["ends_at"],
            "left": max(0, left), "total": total, "ready": left <= 0}


def state(uid, now=None):
    now = _now(now)
    out = [_view(uid, r, now) for r in _rows(uid)]
    waiting = [o["left"] for o in out if not o["ready"]]
    return {"slots": X.SLOTS, "hours": list(X.HOURS), "out": out,
            "free": max(0, X.SLOTS - len(out)),
            "ready": sum(1 for o in out if o["ready"]),
            # 다음 것이 돌아오기까지 남은 초 (없으면 None). 화면이 이만큼 뒤에 다시 본다.
            "nextIn": min(waiting) if waiting else None}


def me_card(uid, now=None):
    """/api/me 에 얹는 요약. 나가 있는 것이 없으면 질의 한 번으로 끝난다."""
    rows = _rows(uid)
    if not rows:
        return {"out": 0, "ready": 0, "nextIn": None}
    now = _now(now)
    left = [int(((_parse(r["ends_at"]) or now) - now).total_seconds()) for r in rows]
    waiting = [x for x in left if x > 0]
    return {"out": len(rows), "ready": sum(1 for x in left if x <= 0),
            "nextIn": min(waiting) if waiting else None}


# ---------------------------------------------------------------- 보내기
def send(uid, pid, place_id, hours, now=None):
    now = _now(now)
    place = X.place(place_id)
    if place is None:
        raise HTTPException(400, "그런 곳은 없습니다.")
    try:
        hours = int(hours)
    except (TypeError, ValueError):
        hours = 0
    if hours not in X.HOURS:
        raise HTTPException(400, "보낼 시간은 %s 중에서 고릅니다." % " · ".join("%d시간" % h for h in X.HOURS))
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (int(pid), uid))
    if r is None:
        raise HTTPException(404, "그런 포켓몬이 없습니다.")
    if r["on_desktop"]:
        raise HTTPException(409, "데리고 다니는 포켓몬은 보낼 수 없습니다. 먼저 박스에 넣어 주세요.")
    if is_away(uid, pid):
        raise HTTPException(409, "이미 탐험에 나가 있습니다.")
    if db.q1("SELECT pos FROM rank_team WHERE user_id=? AND pokemon_id=?", (uid, int(pid))) is not None:
        raise HTTPException(409, "랭크 팀에 든 포켓몬은 보낼 수 없습니다. 랭크 팀에서 먼저 빼 주세요.")
    if len(_rows(uid)) >= X.SLOTS:
        raise HTTPException(409, "탐험 칸이 꽉 찼습니다 (%d칸). 돌아온 보따리를 먼저 받아 주세요." % X.SLOTS)
    mon = db.row_to_mon(r)
    sp = deps.dex().get(mon["species"]) or {}
    points = X.score(mon["level"], sp.get("types") or [], place_id)
    grade = X.grade(points)
    ends = now + datetime.timedelta(hours=hours)
    db.run("INSERT INTO expedition (user_id, pokemon_id, place, hours, grade, score, started_at, ends_at, state)"
           " VALUES (?,?,?,?,?,?,?,?,'out')",
           (uid, int(pid), place_id, hours, grade, points, _iso(now), _iso(ends)))
    name = mon.get("nickname") or sp.get("kr") or mon["species"]
    out = state(uid, now)
    out.update(ok=True, message=korean.natural("%s 을(를) %s(으)로 보냈습니다. %d시간 뒤에 돌아옵니다."
                                               % (name, place["kr"], hours)))
    return out


# ---------------------------------------------------------------- 굴리기
_POOLS = None


def pools():
    """등급마다의 물건 표 {등급: [(도구 id, 가중치)]} - 탐험 전용 표다 (common/expedition.LOOT).

    야생에서 떨어지는 표는 쓰지 않는다 (지닌 도구가 흔하게 섞여 팔았을 때 값이 너무 컸다 - LOOT 의 설명).
    도구 목록에 없는 id 는 조용히 뺀다 (검사가 잡는다).
    """
    global _POOLS
    if _POOLS is None:
        cat = items.catalog()
        out = dict((t, [(i, float(w)) for i, w in X.LOOT.get(t) or () if i in cat and w > 0])
                   for t in X.TIERS)
        # '지닌 도구' 등급만은 야생에서 떨어지는 것에서 고른다: 지닌 도구이고 흔하지 않은 것, 그 가중치대로
        # (X.HELD 의 설명). 금구슬처럼 팔기만 하는 물건은 지닌 도구가 아니라서 여기 안 든다.
        out["held"] = [(i, float(w)) for i, w in items.data()["dropTable"]
                       if w > 0 and (cat.get(i) or {}).get("cat") == "held"
                       and (cat.get(i) or {}).get("rarity") in X.HELD_RARITIES]
        _POOLS = out
    return _POOLS


def special_pool(place_id, tier):
    """그곳의 특산물 가운데 그 등급인 것 [(도구 id, 가중치)]. 특산물끼리는 같은 확률이다."""
    cat = items.catalog()
    ids = ((X.place(place_id) or {}).get("special") or {}).get(tier) or ()
    return [(i, 1.0) for i in ids if i in cat]


def _pick(rng, table):
    total = sum(w for _i, w in table)
    x = rng.random() * total
    for item_id, w in table:
        x -= w
        if x <= 0:
            return item_id
    return table[-1][0]


def roll_item(rng, place_id, hours, grade):
    """물건 하나. (도구 id, 등급)"""
    x = rng.random()
    tier = X.TIERS[0]
    for name, p in X.tier_odds(hours, grade):
        x -= p
        if x <= 0:
            tier = name
            break
    special = special_pool(place_id, tier)
    if special and rng.random() < X.SPECIAL_RATE:
        return _pick(rng, special), tier
    table = pools().get(tier) or pools()["common"]
    return _pick(rng, table), tier


def roll(rng, uid, place_id, hours, grade):
    """보따리 하나. ([{id, kr, count, rarity, tier}], 기술머신 번호 또는 None)"""
    got, order = {}, []
    for _i in range(X.item_count(hours, grade)):
        item_id, tier = roll_item(rng, place_id, hours, grade)
        if item_id not in got:
            got[item_id] = {"id": item_id, "count": 0, "tier": tier}
            order.append(item_id)
        got[item_id]["count"] += 1
    cat = items.catalog()
    loot = []
    for item_id in order:
        it = cat.get(item_id) or {}
        loot.append(dict(got[item_id], kr=it.get("kr", item_id), rarity=it.get("rarity"),
                         sell=it.get("sell", 0)))
    tm = None
    if rng.random() < X.tm_chance(hours, grade, place_id):
        have = tms.owned(uid)
        left = [n for n in sorted(tms.all_tms()) if n not in have]
        if left:
            tm = rng.choice(left)
    return loot, tm


# ---------------------------------------------------------------- 받기
def _claim_row(uid, r, now, rng):
    """돌아온 보따리 하나를 받는다. 이미 누가 받았으면 None."""
    cur = db.run("UPDATE expedition SET state='done', claimed_at=? WHERE id=? AND user_id=? AND state='out'",
                 (_iso(now), r["id"], uid))
    if not getattr(cur, "rowcount", 1):
        return None
    loot, tm = roll(rng, uid, r["place"], r["hours"], r["grade"])
    for it in loot:
        items.bag_add(uid, it["id"], it["count"])
    tm_pub = None
    if tm is not None and tms.give(uid, tm):
        tm_pub = tms.public(tm)
    db.run("UPDATE expedition SET loot=? WHERE id=?",
           (json.dumps({"items": loot, "tm": tm_pub}, ensure_ascii=False), r["id"]))
    view = _view(uid, r, now)
    return {"id": r["id"], "pokemon": view["pokemon"], "place": r["place"], "placeKr": view["placeKr"],
            "hours": r["hours"], "grade": r["grade"], "gradeKr": view["gradeKr"],
            "items": loot, "tm": tm_pub}


def _trim(uid):
    """받은 기록은 최근 것만 남긴다."""
    db.run("DELETE FROM expedition WHERE user_id=? AND state<>'out' AND id NOT IN ("
           "SELECT id FROM expedition WHERE user_id=? AND state<>'out' ORDER BY id DESC LIMIT ?)",
           (uid, uid, KEEP_DONE))


def claim(uid, eid=None, now=None, rng=None):
    """돌아온 보따리를 받는다. eid 가 없으면 돌아온 것 전부."""
    now = _now(now)
    rng = rng or deps.RNG
    rows = _rows(uid)
    if eid is not None:
        rows = [r for r in rows if r["id"] == int(eid)]
        if not rows:
            raise HTTPException(404, "그런 탐험이 없습니다. (이미 받았을 수 있습니다)")
        if (_parse(rows[0]["ends_at"]) or now) > now:
            raise HTTPException(409, "아직 돌아오지 않았습니다.")
    got = []
    for r in rows:
        if (_parse(r["ends_at"]) or now) > now:
            continue
        one = _claim_row(uid, r, now, rng)
        if one is not None:
            got.append(one)
    if got:
        _trim(uid)
    out = state(uid, now)
    user = db.q1("SELECT balls, money FROM users WHERE id=?", (uid,))
    out.update(ok=True, claimed=got, bag=items.bag_get(uid, user["balls"] if user else None),
               money=user["money"] if user else 0, balls=user["balls"] if user else 0)
    if got:
        n = sum(sum(i["count"] for i in g["items"]) + (1 if g["tm"] else 0) for g in got)
        out["message"] = "탐험에서 돌아왔습니다! 물건 %d개를 받았습니다." % n
    else:
        out["message"] = "아직 돌아온 포켓몬이 없습니다."
    return out


def recall(uid, eid, now=None):
    now = _now(now)
    r = db.q1("SELECT * FROM expedition WHERE id=? AND user_id=? AND state='out'", (int(eid), uid))
    if r is None:
        raise HTTPException(404, "그런 탐험이 없습니다.")
    if (_parse(r["ends_at"]) or now) <= now:
        raise HTTPException(409, "이미 돌아왔습니다. 보따리를 받아 주세요.")
    db.run("UPDATE expedition SET state='recalled', claimed_at=? WHERE id=? AND state='out'",
           (_iso(now), r["id"]))
    name = _mon_view(uid, r["pokemon_id"])["name"]
    _trim(uid)
    out = state(uid, now)
    out.update(ok=True, message=korean.natural("%s 을(를) 불러들였습니다. 빈손으로 돌아왔습니다." % name))
    return out


# ---------------------------------------------------------------- 경로
class SendIn(BaseModel):
    pokemon: int
    place: str
    hours: int


@router.get("/api/expedition")
def get_state(ctx=Depends(deps.current)):
    return state(ctx["user"]["id"])


@router.post("/api/expedition/send")
def post_send(body: SendIn, ctx=Depends(deps.current)):
    return send(ctx["user"]["id"], body.pokemon, body.place, body.hours)


@router.post("/api/expedition/claim")
def post_claim_all(ctx=Depends(deps.current)):
    return claim(ctx["user"]["id"])


@router.post("/api/expedition/{eid}/claim")
def post_claim(eid: int, ctx=Depends(deps.current)):
    return claim(ctx["user"]["id"], eid)


@router.post("/api/expedition/{eid}/recall")
def post_recall(eid: int, ctx=Depends(deps.current)):
    return recall(ctx["user"]["id"], eid)
