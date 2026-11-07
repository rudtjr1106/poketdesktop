# -*- coding: utf-8 -*-
"""탐험 파견 (1.10.4) — 박스의 포켓몬을 몇 시간 보내 두면 도구를 가져온다.

    GET  /api/expedition                 지금 나가 있는 것들과 칸 수, 포켓몬마다의 성장·쉬는 시간
    POST /api/expedition/send            보낸다 {pokemon, place, hours}
    POST /api/expedition/{id}/claim      돌아온 보따리를 받는다
    POST /api/expedition/claim           돌아온 것을 전부 받는다 (바탕화면의 보따리)
    POST /api/expedition/{id}/recall     불러들인다 (빈손으로 돌아온다)
    POST /api/expedition/grow            성장치를 찍는다 {pokemon, add: {speed: 1, ...}}   (1.10.5)
    POST /api/expedition/reset           성장치를 전부 되돌린다 {pokemon} - 돈이 든다       (1.10.5)

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

## 쉬기와 성장 (1.10.5)

보따리를 받는 순간 그 포켓몬에게 탐험 경험치를 주고, **돌아온 때(ends_at)부터 24시간** 쉬게 한다
(expedition_mon). 쉬는 동안에는 탐험만 못 나간다 - 데리고 다니고 싸우는 것은 된다. 받는 것을
미뤄도 쉬는 시간은 돌아온 때부터 흐른다. 불러들인 포켓몬은 경험치도 없고 쉬지도 않는다.

성장치(발걸음·눈썰미·주머니·호기심·친화력)는 **보낼 때와 받을 때의 값이 같다** - 나가 있는 동안에는
찍지도 되돌리지도 못하게 막는다. 발걸음은 보낼 때 돌아올 시각에 녹이고, 나머지는 받을 때 굴림에 쓴다.

**친화력**: 받을 때 한 번 굴려서 그곳 타입의 포켓몬을 데려온다 (friend). 풀숲에 나오는 포켓몬 가운데
그곳의 세 타입인 것을 풀숲과 같은 가중치로 뽑고, 레벨도 지금 풀숲에서 만나는 레벨이다 (main._wild_levels -
규칙을 따로 두지 않는다). 박스에 넣고 도감에 올린다. 잡은 것이 아니라서 잡기 미션·잡은 수에는 안 든다.
보유 상한(MAX_BOX)이 찼으면 못 데려온다 (그렇다고 알린다).
"""
import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common import expedition as X
from common import korean

from common import pokelogic as P

from . import achievements, config, db, deps, items, tms

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
    # 걸리는 시간은 보낼 때 정해졌다 (발걸음만큼 짧다) - 적어 둔 두 시각에서 읽는다
    began = _parse(r["started_at"])
    total = max(1, int((ends - began).total_seconds()) if began else int(r["hours"]) * 3600)
    gold = X.is_gold(r["place"])
    # 광산은 물건 대신 골드 (주머니 덤까지 - 나가 있는 동안에는 성장치를 못 바꾸니 받을 때와 같다)
    haul = _stats(_grow_row(uid, r["pokemon_id"]))["haul"] if gold else 0
    return {"id": r["id"], "pokemon": _mon_view(uid, r["pokemon_id"]), "place": r["place"],
            "placeKr": (X.place(r["place"]) or {}).get("kr", r["place"]),
            "hours": r["hours"], "grade": r["grade"], "gradeKr": X.GRADE_KR.get(r["grade"], ""),
            "score": r["score"], "items": 0 if gold else X.item_count(r["hours"], r["grade"]),
            "gold": X.gold_for(r["hours"], r["grade"], haul, r["place"]),
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
            "nextIn": min(waiting) if waiting else None,
            # 포켓몬마다의 탐험 성장과 쉬는 시간 {포켓몬 id(글자): {...}} - 다녀온 적 있는 것만 (1.10.5)
            "growth": growth_all(uid, now)}


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


# ---------------------------------------------------------------- 쉬기와 성장 (1.10.5)
def _grow_row(uid, pid):
    return db.q1("SELECT * FROM expedition_mon WHERE pokemon_id=? AND user_id=?", (int(pid), uid))


def _stats(row):
    return dict((k, int(row[k] or 0) if row is not None else 0) for k in X.STATS)


def _rest_left(row, now):
    until = _parse(row["rest_until"]) if row is not None and row["rest_until"] else None
    return max(0, int((until - now).total_seconds())) if until else 0


def growth_view(row, now):
    """그 포켓몬의 탐험 성장. 줄이 없으면(다녀온 적이 없으면) 0 에서 시작한다."""
    xp = int(row["xp"] or 0) if row is not None else 0
    lv, into, need = X.level_of(xp)
    stats = _stats(row)
    return {"xp": xp, "level": lv, "into": into, "need": need, "stats": stats,
            "free": X.free_points(xp, stats), "rest": _rest_left(row, now),
            "runs": int(row["runs"] or 0) if row is not None else 0}


def growth_all(uid, now):
    return dict((str(r["pokemon_id"]), growth_view(r, now))
                for r in db.q("SELECT * FROM expedition_mon WHERE user_id=?", (uid,)))


def forget(uid, pid):
    """놓아준 포켓몬의 성장 기록을 지운다."""
    db.run("DELETE FROM expedition_mon WHERE pokemon_id=? AND user_id=?", (int(pid), uid))


def _came_back(uid, r, now):
    """보따리를 받았다: 경험치를 주고 쉬게 한다. 화면에 보여 줄 것을 돌려준다."""
    pid = int(r["pokemon_id"])
    row = _grow_row(uid, pid)
    before = int(row["xp"] or 0) if row is not None else 0
    gain = X.xp_for(r["hours"], r["grade"])
    after = min(X.XP_MAX, before + gain)
    # 쉬는 시간은 **돌아온 때부터** 센다. 보따리를 이틀 뒤에 받았으면 이미 다 쉰 것이다.
    until = (_parse(r["ends_at"]) or now) + datetime.timedelta(hours=X.REST_HOURS)
    if row is None:
        db.run("INSERT INTO expedition_mon (pokemon_id, user_id, xp, rest_until, runs) VALUES (?,?,?,?,1)",
               (pid, uid, after, _iso(until)))
    else:
        db.run("UPDATE expedition_mon SET xp=?, rest_until=?, runs=runs+1 WHERE pokemon_id=? AND user_id=?",
               (after, _iso(until), pid, uid))
    view = growth_view(_grow_row(uid, pid), now)
    return {"xp": after - before, "levelBefore": X.level_of(before)[0], "level": view["level"],
            "into": view["into"], "need": view["need"], "free": view["free"], "rest": view["rest"]}


def _own_mon(uid, pid):
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (int(pid), uid))
    if r is None:
        raise HTTPException(404, "그런 포켓몬이 없습니다.")
    return r


def _mon_name(r):
    mon = db.row_to_mon(r)
    sp = deps.dex().get(mon["species"]) or {}
    return mon.get("nickname") or sp.get("kr") or mon["species"]


def grow(uid, pid, add, now=None):
    """성장치를 찍는다. add = {성장치: 몇 점}."""
    now = _now(now)
    r = _own_mon(uid, pid)
    if is_away(uid, pid):
        raise HTTPException(409, "탐험에 나가 있는 동안에는 성장치를 찍을 수 없습니다. 돌아온 뒤에 해 주세요.")
    want = {}
    for k, v in (add or {}).items():
        if k not in X.STATS:
            raise HTTPException(400, "그런 성장치는 없습니다.")
        try:
            n = int(v)
        except (TypeError, ValueError):
            n = -1
        if n < 0:
            raise HTTPException(400, "성장치는 올릴 수만 있습니다.")
        if n:
            want[k] = n
    total = sum(want.values())
    if total <= 0:
        raise HTTPException(400, "찍을 성장치를 골라 주세요.")
    row = _grow_row(uid, pid)
    view = growth_view(row, now)
    if total > view["free"]:
        raise HTTPException(409, "남은 성장치가 모자랍니다 (남은 것 %d점)." % view["free"])
    over = [k for k, n in want.items() if view["stats"][k] + n > X.STAT_CAP]
    if over:
        raise HTTPException(409, "%s 은(는) %d점까지 찍을 수 있습니다." % (X.STAT_KR[over[0]], X.STAT_CAP))
    # 한 문장으로: 그사이 다른 요청이 먼저 찍었으면 (합이 레벨을 넘으면) 0줄이다
    # (칸 이름은 X.STATS 의 상수다 - 사람이 보낸 글이 SQL 에 들어가지 않는다)
    cur = db.run("UPDATE expedition_mon SET %s WHERE pokemon_id=? AND user_id=? AND %s+? <= ?"
                 % (", ".join("%s=%s+?" % (k, k) for k in X.STATS), "+".join(X.STATS)),
                 tuple(want.get(k, 0) for k in X.STATS) + (int(pid), uid, total, view["level"]))
    if not getattr(cur, "rowcount", 1):
        raise HTTPException(409, "남은 성장치가 모자랍니다. 다시 불러와 주세요.")
    out = state(uid, now)
    out.update(ok=True, message=korean.natural("%s 의 성장치를 %d점 찍었습니다." % (_mon_name(r), total)))
    return out


def reset(uid, pid, now=None):
    """찍은 성장치를 전부 되돌린다 (다시 찍을 수 있다). 돈이 든다."""
    now = _now(now)
    r = _own_mon(uid, pid)
    if is_away(uid, pid):
        raise HTTPException(409, "탐험에 나가 있는 동안에는 성장치를 되돌릴 수 없습니다. 돌아온 뒤에 해 주세요.")
    row = _grow_row(uid, pid)
    if X.spent(_stats(row)) <= 0:
        raise HTTPException(409, "되돌릴 성장치가 없습니다.")
    if not items.money_take(uid, X.RESET_COST):
        raise HTTPException(409, "돈이 모자랍니다 (%s원)." % format(X.RESET_COST, ","))
    db.run("UPDATE expedition_mon SET %s WHERE pokemon_id=? AND user_id=?" % ", ".join("%s=0" % k for k in X.STATS),
           (int(pid), uid))
    out = state(uid, now)
    out.update(ok=True, money=items.money(uid),
               message=korean.natural("%s 의 성장치를 되돌렸습니다. 다시 찍을 수 있습니다." % _mon_name(r)))
    return out


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
    grow_row = _grow_row(uid, pid)
    rest = _rest_left(grow_row, now)
    if rest > 0:
        raise HTTPException(409, "아직 쉬는 중입니다. %s 뒤에 다시 나갈 수 있습니다." % X.hours_text(rest))
    mon = db.row_to_mon(r)
    sp = deps.dex().get(mon["species"]) or {}
    points = X.score(mon["level"], sp.get("types") or [], place_id)
    grade = X.grade(points)
    took = X.duration(hours, _stats(grow_row)["speed"])       # 발걸음만큼 빨리 돌아온다
    ends = now + datetime.timedelta(seconds=took)
    db.run("INSERT INTO expedition (user_id, pokemon_id, place, hours, grade, score, started_at, ends_at, state)"
           " VALUES (?,?,?,?,?,?,?,?,'out')",
           (uid, int(pid), place_id, hours, grade, points, _iso(now), _iso(ends)))
    name = mon.get("nickname") or sp.get("kr") or mon["species"]
    out = state(uid, now)
    out.update(ok=True, message=korean.natural("%s 을(를) %s(으)로 보냈습니다. %s 뒤에 돌아옵니다."
                                               % (name, place["kr"], X.time_text(took))))
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


def roll_item(rng, place_id, hours, grade, luck=0):
    """물건 하나. (도구 id, 등급). luck = 그 포켓몬의 눈썰미."""
    x = rng.random()
    tier = X.TIERS[0]
    for name, p in X.tier_odds(hours, grade, luck):
        x -= p
        if x <= 0:
            tier = name
            break
    special = special_pool(place_id, tier)
    if special and rng.random() < X.SPECIAL_RATE:
        return _pick(rng, special), tier
    table = pools().get(tier) or pools()["common"]
    return _pick(rng, table), tier


def roll(rng, uid, place_id, hours, grade, stats=None):
    """보따리 하나. ([{id, kr, count, rarity, tier}], 기술머신 번호 또는 None)"""
    loot, tm, _bonus = roll_more(rng, uid, place_id, hours, grade, stats)
    return loot, tm


def roll_more(rng, uid, place_id, hours, grade, stats=None):
    """보따리 하나와, 주머니로 더 가져온 수. (물건들, 기술머신 번호 또는 None, 더 가져온 수)

    stats = 그 포켓몬의 성장치 (1.10.5). 눈썰미는 등급 확률에, 주머니는 물건 수에, 호기심은 기술머신에 든다.
    """
    stats = stats or {}
    luck, haul = stats.get("luck", 0), X.haul_chance(stats.get("haul", 0))
    got, order = {}, []
    bonus = 0

    def add(item_id, tier):
        if item_id not in got:
            got[item_id] = {"id": item_id, "count": 0, "tier": tier}
            order.append(item_id)
        got[item_id]["count"] += 1

    for _i in range(X.item_count(hours, grade)):
        add(*roll_item(rng, place_id, hours, grade, luck))
        # 주머니: 물건마다 하나를 더 주워 온다 (새로 한 번 굴린다). 안 찍었으면 주사위도 안 굴린다 -
        # 성장치가 없는 포켓몬의 굴림은 1.10.4 와 한 치도 다르지 않다.
        if haul and rng.random() < haul:
            add(*roll_item(rng, place_id, hours, grade, luck))
            bonus += 1
    cat = items.catalog()
    loot = []
    for item_id in order:
        it = cat.get(item_id) or {}
        loot.append(dict(got[item_id], kr=it.get("kr", item_id), rarity=it.get("rarity"),
                         sell=it.get("sell", 0)))
    tm = None
    if rng.random() < X.tm_chance(hours, grade, place_id, stats.get("lore", 0)):
        have = tms.owned(uid)
        left = [n for n in sorted(tms.all_tms()) if n not in have]
        if left:
            tm = rng.choice(left)
    return loot, tm, bonus


# ---------------------------------------------------------------- 친화력: 포켓몬을 데려온다
def roll_friend(rng, place_id, level, max_bst=None):
    """그곳 타입의 야생 포켓몬 하나 (없으면 None). 풀숲과 같은 표·같은 가중치에서 타입만 거른다.

    풀숲에 안 나오는 것(전설·환상, 업적으로 풀리는 울트라비스트·패러독스, 이벤트 포켓몬)은 여기서도
    안 나온다. 레벨로 이미 진화했을 모습으로 나오는데(grown_form), 진화하면서 타입이 바뀌어 그곳과
    안 맞게 된 것은 다시 뽑는다.
    """
    d = deps.dex()
    good = set((X.place(place_id) or {}).get("types") or ())
    level = max(1, int(level))

    def cands(cap):
        pool, _cum, _total = d.spawn_pool(level, cap)
        return [(s, s.get("weight", 0)) for s in pool if s.get("weight", 0) > 0 and good & set(s.get("types") or ())]
    table = cands(max_bst) or (cands(None) if max_bst else [])
    if not table:
        return None
    total = sum(w for _s, w in table)
    form = None
    for _try in range(8):
        x = rng.random() * total
        pick = table[-1][0]
        for s, w in table:
            x -= w
            if x <= 0:
                pick = s
                break
        form = d.grown_form(pick, level, rng)
        if good & set(form.get("types") or ()):
            break
    return P.make_pokemon(form, level, rng, shiny_rate=config.SHINY_RATE)


def _friend(rng, uid, place_id, stats, now):
    """(데려온 포켓몬 또는 None, 자리가 없어 못 데려왔나). 친화력을 안 찍었으면 주사위도 안 굴린다."""
    chance = X.charm_chance((stats or {}).get("charm", 0))
    if not chance or rng.random() >= chance:
        return None, False
    if db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (uid,))["c"] >= config.MAX_BOX:
        return None, True
    from . import main                       # 야생 레벨 규칙 (main 이 이 모듈을 불러오므로 여기서 부른다)
    _lo, level, cap = main._wild_levels(uid)
    mon = roll_friend(rng, place_id, level, cap)
    if mon is None:
        return None, False
    new = not items.has_caught(uid, mon["species"])
    pid = db.insert_mon(uid, mon, _iso(now))
    deps.to_box(uid, pid)                    # 자리 있는 박스로
    items.mark_seen(uid, mon["species"], True, _iso(now))
    achievements.on_obtain(uid, mon, "expedition")       # 도감 업적 (잡기 미션·잡은 수에는 안 든다)
    sp = deps.dex().get(mon["species"]) or {}
    return {"id": pid, "name": sp.get("kr") or mon["species"], "species": mon["species"], "num": sp.get("num", 0),
            "level": mon["level"], "shiny": bool(mon.get("shiny")), "types": list(sp.get("types") or []),
            "new": new}, False


# ---------------------------------------------------------------- 받기
def _claim_row(uid, r, now, rng):
    """돌아온 보따리 하나를 받는다. 이미 누가 받았으면 None."""
    cur = db.run("UPDATE expedition SET state='done', claimed_at=? WHERE id=? AND user_id=? AND state='out'",
                 (_iso(now), r["id"], uid))
    if not getattr(cur, "rowcount", 1):
        return None
    stats = _stats(_grow_row(uid, r["pokemon_id"]))
    loot, tm_pub, bonus, friend, full, gold = [], None, 0, None, False, 0
    if X.is_gold(r["place"]):
        # 광산: 골드만 (물건 · 기술머신 · 포켓몬은 굴리지도 않는다). 주머니만 골드를 늘린다.
        gold = X.gold_for(r["hours"], r["grade"], stats["haul"], r["place"])
        items.money_add(uid, gold)
    else:
        loot, tm, bonus = roll_more(rng, uid, r["place"], r["hours"], r["grade"], stats)
        for it in loot:
            items.bag_add(uid, it["id"], it["count"])
        if tm is not None and tms.give(uid, tm):
            tm_pub = tms.public(tm)
        friend, full = _friend(rng, uid, r["place"], stats, now)      # 친화력: 그곳의 포켓몬을 데려온다
    db.run("UPDATE expedition SET loot=? WHERE id=?",
           (json.dumps({"items": loot, "tm": tm_pub, "friend": friend, "gold": gold}, ensure_ascii=False), r["id"]))
    grown = _came_back(uid, r, now)                       # 경험치를 주고 쉬게 한다 (1.10.5)
    view = _view(uid, r, now)
    return {"id": r["id"], "pokemon": view["pokemon"], "place": r["place"], "placeKr": view["placeKr"],
            "hours": r["hours"], "grade": r["grade"], "gradeKr": view["gradeKr"],
            "items": loot, "tm": tm_pub, "bonus": bonus, "growth": grown,
            "friend": friend, "friendFull": full, "gold": gold}


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
        friends = sum(1 for g in got if g.get("friend"))
        gold = sum(g.get("gold") or 0 for g in got)
        took = ([("물건 %d개" % n)] if n or not gold else []) + (["골드 %s원" % format(gold, ",")] if gold else [])
        out["message"] = "탐험에서 돌아왔습니다! %s을(를) 받았습니다." % "와(과) ".join(took) + (
            " 포켓몬 %d마리를 데려왔습니다." % friends if friends else "")
        out["message"] = korean.natural(out["message"])
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


class GrowIn(BaseModel):
    pokemon: int
    add: dict = {}


class ResetIn(BaseModel):
    pokemon: int


@router.post("/api/expedition/grow")
def post_grow(body: GrowIn, ctx=Depends(deps.current)):
    return grow(ctx["user"]["id"], body.pokemon, body.add)


@router.post("/api/expedition/reset")
def post_reset(body: ResetIn, ctx=Depends(deps.current)):
    return reset(ctx["user"]["id"], body.pokemon)


@router.post("/api/expedition/{eid}/claim")
def post_claim(eid: int, ctx=Depends(deps.current)):
    return claim(ctx["user"]["id"], eid)


@router.post("/api/expedition/{eid}/recall")
def post_recall(eid: int, ctx=Depends(deps.current)):
    return recall(ctx["user"]["id"], eid)
