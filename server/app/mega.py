# -*- coding: utf-8 -*-
"""메가진화 (시즌 3) — 키스톤과 유대 미션.

## 키스톤

메가진화 자체를 여는 열쇠. **관장 8곳을 이긴 트레이너**가 가진다. 따로
적어 두지 않고 관장 기록(gym_clear)으로 센다 - 이미 8곳 넘게 이긴 사람은
시즌 3 가 열리는 순간 바로 가진다.

## 메가스톤

유대 미션을 마쳐야 받는다 (아래 bond 절). 한 번 받으면 친밀도가 떨어져도
계속 가진다 (사용자가 정했다).
"""
from . import config, db, gym

KEYSTONE_GYMS = 8


def has_keystone(uid):
    try:
        return len(gym.clears(uid)) >= KEYSTONE_GYMS
    except Exception:                                        # noqa: BLE001
        return False


def keystone_card(uid):
    """화면에 줄 것: 가졌나, 몇 곳 남았나."""
    n = len(gym.clears(uid))
    return {"has": n >= KEYSTONE_GYMS, "gyms": n, "need": KEYSTONE_GYMS}


# ---------------------------------------------------------------- 유대 미션
# 메가진화할 수 있는 포켓몬을 데리고 다녀 친밀도가 끝까지 차면, 바탕화면에
# '빛나는 돌' 이 나타난다. 누르면 그 **개체**와의 미션 셋이 시작된다:
#
#   ① 그 포켓몬 타입의 관장 1곳에서 이기기 (파티에 넣고, 재도전 포함)
#   ② 그 개체가 직접 30번 쓰러뜨리기 (야생·관장)
#   ③ 데리고 다니는 동안 야생 10마리 잡기
#
# 다 채우면 그 종의 메가스톤. X/Y 로 갈리는 종은 받을 때 고르고, 나머지는
# 같은 종 다른 개체로 한 번 더 하면 받는다. 한 종의 스톤은 계정에 하나씩이다.
BOND_HAPPINESS = 255
BOND_GYM = 1
BOND_KOS = 30
BOND_WILD = 10


def _now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def stones_for(species):
    """이 종이 될 수 있는 메가의 스톤 id 목록 (레쿠쟈처럼 기술로 되면 빈 목록)."""
    from . import deps
    forms = (getattr(deps.dex(), "mega_of", None) or {}).get(species) or []
    out = []
    for m in forms:
        s = m.get("megaStone")
        if s and s not in out:
            out.append(s)
    return out


def owned_stones(uid):
    """가방에 있거나 누군가 지니고 있는 메가스톤."""
    from common import held as H
    from . import items
    have = set(k for k, n in (items.bag_get(uid) or {}).items()
               if n and H.is_mega_stone(k))
    for r in db.q("SELECT held FROM pokemon WHERE user_id=? AND held IS NOT NULL", (uid,)):
        if H.is_mega_stone(r["held"]):
            have.add(r["held"])
    return have


def missing_stones(uid, species):
    have = owned_stones(uid)
    return [s for s in stones_for(species) if s not in have]


def _row(pid):
    return db.q1("SELECT * FROM bond WHERE pokemon_id=?", (pid,))


def ready(uid):
    """빛나는 돌을 띄울 포켓몬 id. 데리고 다니고, 친밀도가 끝까지 찼고,
    아직 미션을 시작 안 했고, 그 종의 스톤 중 아직 없는 것이 있을 때."""
    if not has_keystone(uid):
        return []
    rows = db.q("SELECT id, species, happiness FROM pokemon WHERE user_id=?"
                " AND on_desktop=1 AND happiness>=?", (uid, BOND_HAPPINESS))
    started = set(r["pokemon_id"] for r in db.q(
        "SELECT pokemon_id FROM bond WHERE user_id=?", (uid,)))
    out = []
    for r in rows:
        if r["id"] in started:
            continue
        if missing_stones(uid, r["species"]):
            out.append(r["id"])
    return out


def start(uid, pid, now=None):
    """빛나는 돌을 눌렀다 - 미션을 연다."""
    r = db.q1("SELECT id, species, happiness, on_desktop FROM pokemon"
              " WHERE id=? AND user_id=?", (pid, uid))
    if not r:
        raise LookupError("그런 포켓몬이 없습니다.")
    if not has_keystone(uid):
        raise ValueError("키스톤이 없습니다. 관장 %d곳을 이기면 받습니다." % KEYSTONE_GYMS)
    if not stones_for(r["species"]):
        raise ValueError("이 포켓몬은 메가스톤으로 메가진화하지 않습니다.")
    if (r["happiness"] or 0) < BOND_HAPPINESS:
        raise ValueError("아직 유대가 부족합니다. 더 오래 데리고 다녀 주세요.")
    if not missing_stones(uid, r["species"]):
        raise ValueError("이 종의 메가스톤은 이미 모두 가지고 있습니다.")
    db.run("INSERT INTO bond (pokemon_id, user_id, species, started_at)"
           " VALUES (?,?,?,?) ON CONFLICT(pokemon_id) DO NOTHING",
           (pid, uid, r["species"], now or _now_iso()))
    return card(uid, pid)


def _types_of(species):
    from . import deps
    return list((deps.dex().get(species) or {}).get("types") or [])


def _complete(uid, pid, now=None):
    """세 미션을 다 채웠으면 끝을 적고, 고를 것 없이 받을 스톤이면 준다."""
    b = _row(pid)
    if not b or b["done_at"]:
        return
    if b["gym"] < BOND_GYM or b["kos"] < BOND_KOS or b["wild"] < BOND_WILD:
        return
    db.run("UPDATE bond SET done_at=? WHERE pokemon_id=? AND done_at IS NULL",
           (now or _now_iso(), pid))
    miss = missing_stones(uid, b["species"])
    if len(miss) == 1:
        # 배틀·잡기 도중에 저절로 받는다 - 본 적이 없으니 나중에 알린다(seen=0).
        claim(uid, pid, miss[0], now, seen=False)


def claim(uid, pid, stone, now=None, seen=True):
    """스톤을 받는다. X/Y 로 갈리는 종은 여기서 고른다.

    seen: 사람이 직접 고른 것이면 이미 본 것이다. 저절로 받은 것만 False.
    """
    from . import items
    b = _row(pid)
    if not b or b["user_id"] != uid:
        raise LookupError("그런 미션이 없습니다.")
    if not b["done_at"]:
        raise ValueError("아직 미션을 다 채우지 못했습니다.")
    if b["stone"]:
        raise ValueError("이미 받았습니다.")
    miss = missing_stones(uid, b["species"])
    if stone not in miss:
        raise ValueError("그 스톤은 받을 수 없습니다.")
    # **먼저 적고 그다음에 준다.** 두 요청이 겹쳐도 한 번만 받는다.
    cur = db.run("UPDATE bond SET stone=?, seen=? WHERE pokemon_id=? AND stone IS NULL",
                 (stone, 1 if seen else 0, pid))
    if getattr(cur, "rowcount", 1) == 0:
        raise ValueError("이미 받았습니다.")
    items.bag_add(uid, stone, 1)
    return card(uid, pid)


# ---- 진행 (배틀·잡기에서 부른다. 실패해도 부른 쪽을 깨지 않는다) ----
def _safe(fn):
    def run(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as e:                               # noqa: BLE001
            from . import errors
            errors.record("BOND", fn.__name__, e)
    return run


@_safe
def on_gym_win(uid, team_ids, gym_type, now=None):
    """관장을 이겼다. 파티에 있던 개체 중 타입이 맞는 미션을 채운다."""
    for pid in team_ids or []:
        b = _row(pid)
        if not b or b["done_at"] or b["gym"] >= BOND_GYM:
            continue
        if gym_type in _types_of(b["species"]):
            db.run("UPDATE bond SET gym=gym+1 WHERE pokemon_id=?", (pid,))
            _complete(uid, pid, now)


@_safe
def on_ko(uid, pid, n=1, now=None):
    """그 개체가 상대를 쓰러뜨렸다."""
    b = _row(pid)
    if not b or b["done_at"]:
        return
    db.run("UPDATE bond SET kos=kos+? WHERE pokemon_id=?", (int(n), pid))
    _complete(uid, pid, now)


@_safe
def on_catch(uid, now=None):
    """야생을 잡았다. 데리고 다니는 개체의 미션 ③ 을 채운다."""
    rows = db.q("SELECT b.pokemon_id FROM bond b JOIN pokemon p ON p.id=b.pokemon_id"
                " WHERE b.user_id=? AND b.done_at IS NULL AND p.on_desktop=1", (uid,))
    for r in rows:
        db.run("UPDATE bond SET wild=wild+1 WHERE pokemon_id=?", (r["pokemon_id"],))
        _complete(uid, r["pokemon_id"], now)


# ---- 보여주기 ----
def card(uid, pid):
    """한 개체의 미션 카드."""
    from . import deps
    b = _row(pid)
    r = db.q1("SELECT species, happiness FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
    if not r:
        return None
    d = deps.dex()
    types = _types_of(r["species"])
    out = {"pokemon": pid, "species": r["species"], "name": _name(pid),
           "happiness": r["happiness"], "need": BOND_HAPPINESS,
           "stones": [{"id": s, "kr": d and _stone_kr(s)} for s in stones_for(r["species"])],
           "missing": missing_stones(uid, r["species"]),
           "started": bool(b)}
    if b:
        out.update({
            "missions": [
                {"key": "gym", "text": "%s 타입 관장 1곳에서 이기기"
                         % " 또는 ".join(d.type_name(t) for t in types),
                 "value": min(b["gym"], BOND_GYM), "target": BOND_GYM},
                {"key": "kos", "text": "직접 %d번 쓰러뜨리기" % BOND_KOS,
                 "value": min(b["kos"], BOND_KOS), "target": BOND_KOS},
                {"key": "wild", "text": "데리고 다니는 동안 야생 %d마리 잡기" % BOND_WILD,
                 "value": min(b["wild"], BOND_WILD), "target": BOND_WILD},
            ],
            "done": bool(b["done_at"]), "stone": b["stone"],
            "claimable": bool(b["done_at"] and not b["stone"]),
        })
    return out


def _name(pid):
    """알림에 쓸 이름 - 별명이 있으면 별명."""
    from . import deps
    r = db.q1("SELECT species, nickname FROM pokemon WHERE id=?", (pid,))
    if not r:
        return ""
    return r["nickname"] or (deps.dex().get(r["species"]) or {}).get("kr") or r["species"]


def mark_seen(uid, pid):
    db.run("UPDATE bond SET seen=1 WHERE pokemon_id=? AND user_id=?", (pid, uid))


def _stone_kr(stone):
    from common import held as H
    return H.name(stone)


def me_card(uid):
    """/api/me 에 싣는다: 키스톤, 빛나는 돌을 띄울 개체, 받을 스톤이 남은 개체."""
    try:
        # 포켓몬 표와 맞댄다 - 놓아준 개체의 줄이 남아 있어도 안 보이게
        claim_ready = [r["pokemon_id"] for r in db.q(
            "SELECT b.pokemon_id FROM bond b JOIN pokemon p ON p.id=b.pokemon_id"
            " WHERE b.user_id=? AND b.done_at IS NOT NULL AND b.stone IS NULL", (uid,))]
        # 저절로 받고 아직 못 알린 스톤
        got = [{"pokemon": r["pokemon_id"], "name": _name(r["pokemon_id"]),
                "stone": r["stone"], "stoneKr": _stone_kr(r["stone"])}
               for r in db.q(
                   "SELECT b.pokemon_id, b.stone FROM bond b JOIN pokemon p"
                   " ON p.id=b.pokemon_id WHERE b.user_id=? AND b.stone IS NOT NULL"
                   " AND b.seen=0", (uid,))]
        return {"keystone": keystone_card(uid), "ready": ready(uid),
                "claim": claim_ready, "got": got}
    except Exception as e:                                   # noqa: BLE001
        from . import errors
        errors.record("BOND", "mega.me_card", e)
        return {"keystone": {"has": False, "gyms": 0, "need": KEYSTONE_GYMS},
                "ready": [], "claim": [], "got": []}
