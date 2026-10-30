# -*- coding: utf-8 -*-
"""꾸미기 (버전 2) - 가진 장식 · 효과와 포켓몬에 끼운 것. 목록과 규칙은 common/deco.py.

    deco_owned (user_id, deco)   가진 것. deco = common.deco.DECOS 의 열쇠, 또는 PICK(참가 묶음 선택권, count 개)
    pokemon.deco                 그 포켓몬이 쓰고 있는 것 {칸: 열쇠} (JSON)

규칙:
  · 장식 하나는 포켓몬 한 마리만 쓴다 - 다른 포켓몬에 끼우면 먼저 쓰던 포켓몬에서 빠진다
  · 같은 칸에 이미 다른 것이 있으면 바꿔 낀다 (head 에 금관을 쓰고 있다가 은관을 끼우면 금관은 빠진다)
  · 가진 것만 낀다. 놓아준 포켓몬이 쓰던 장식은 다시 낄 수 있게 된다 (행이 지워지니 따로 할 일이 없다)
  · 얻는 길은 선물함(kind 'deco') 뿐 - grant 가 묶음('bundle:rank1') · 하나('crown_gold') · 선택권(PICK)을 받는다
"""
import json
import threading

from fastapi import HTTPException

from common import deco as C

from . import db


def _now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- 가진 것
def owned(uid):
    """{열쇠: 개수}. 장식 · 효과는 1, 참가 묶음 선택권(PICK)은 남은 장수."""
    return dict((r["deco"], int(r["count"] or 0)) for r in db.q(
        "SELECT deco, count FROM deco_owned WHERE user_id=? AND count > 0", (uid,)))


def _give(uid, key, season=0, now=None, n=1):
    db.run("INSERT INTO deco_owned (user_id, deco, count, season, got_at) VALUES (?,?,?,?,?)"
           " ON CONFLICT(user_id, deco) DO UPDATE SET count = CASE WHEN deco_owned.deco = ? THEN"
           " deco_owned.count + excluded.count ELSE 1 END, season = excluded.season",
           (uid, key, n, int(season or 0), now or _now(), C.PICK))


def grant(uid, what, season=0, now=None):
    """선물 하나를 준다. what = 'bundle:<묶음>' · 장식 열쇠 · PICK. 준 것들의 이름 목록 (모르는 것이면 빈 목록).

    장식 · 효과는 하나만 가진다 (이미 있으면 그대로 - 두 시즌 우승해도 금관은 하나). 선택권은 쌓인다.
    """
    what = str(what or "")
    if what.startswith("bundle:"):
        keys = C.BUNDLES.get(what[len("bundle:"):])
        if not keys:
            return []
        for k in keys:
            _give(uid, k, season, now)
        return [C.name(k) for k in keys]
    if what == C.PICK:
        _give(uid, C.PICK, season, now)
        return [C.PICK_KR]
    if what in C.DECOS:
        _give(uid, what, season, now)
        return [C.name(what)]
    return []


def pick(uid, bundle, now=None):
    """참가 묶음 선택권 한 장으로 묶음 하나를 고른다. 고른 묶음의 것들을 준다."""
    if bundle not in C.JOIN_CHOICES:
        raise HTTPException(400, "고를 수 없는 묶음입니다.")
    cur = db.run("UPDATE deco_owned SET count = count - 1 WHERE user_id=? AND deco=? AND count > 0",
                 (uid, C.PICK))
    if getattr(cur, "rowcount", 1) == 0:
        raise HTTPException(409, "참가 묶음 선택권이 없습니다.")
    db.run("DELETE FROM deco_owned WHERE user_id=? AND deco=? AND count <= 0", (uid, C.PICK))
    return grant(uid, "bundle:" + bundle, 0, now)


# ---------------------------------------------------------------- 끼우기
def worn(raw):
    """pokemon.deco 칸 -> {칸: 열쇠} (모르는 것은 버린다)."""
    if not raw:
        return {}
    try:
        return C.clean(json.loads(raw))
    except (TypeError, ValueError):
        return {}


def _save(pid, d):
    db.run("UPDATE pokemon SET deco=? WHERE id=?", (json.dumps(d, sort_keys=True) if d else None, pid))


def equipped(uid):
    """{포켓몬 id: {칸: 열쇠}} - 무엇이든 쓰고 있는 포켓몬만."""
    out = {}
    for r in db.q("SELECT id, deco FROM pokemon WHERE user_id=? AND deco IS NOT NULL", (uid,)):
        d = worn(r["deco"])
        if d:
            out[r["id"]] = d
    return out


# 끼우기는 읽고-고치고-쓰기라 겹치면 꼬인다 (같은 금관이 두 마리에 · 한 마리의 칸 하나가 사라짐). 한 줄로 세운다 -
# 사람이 누르는 일이라 드물고 짧다.
_LOCK = threading.Lock()


def equip(uid, pid, key, on=True):
    """그 포켓몬에 장식을 끼우거나(on) 뺀다. 그 포켓몬이 이제 쓰고 있는 것 {칸: 열쇠} 를 준다."""
    with _LOCK:
        return _equip(uid, pid, key, on)


def _equip(uid, pid, key, on):
    if key not in C.DECOS:
        raise HTTPException(404, "그런 꾸미기가 없습니다.")
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        pid = 0
    if not 0 < pid < 2 ** 62:
        raise HTTPException(404, "내 포켓몬이 아닙니다.")      # sqlite 정수 밖이면 500 이 난다
    row = db.q1("SELECT id, deco FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
    if not row:
        raise HTTPException(404, "내 포켓몬이 아닙니다.")
    mine = worn(row["deco"])
    slot = C.slot_of(key)
    if not on:
        if mine.get(slot) == key:
            mine.pop(slot)
            _save(row["id"], mine)
        return mine
    if key not in owned(uid):
        raise HTTPException(409, "가지고 있지 않은 꾸미기입니다.")
    # 한 마리만 - 다른 포켓몬이 쓰고 있으면 빼 온다
    for other, d in equipped(uid).items():
        if other != row["id"] and d.get(slot) == key:
            d.pop(slot)
            _save(other, d)
    mine[slot] = key
    _save(row["id"], mine)
    return mine


# ---------------------------------------------------------------- 화면에 줄 것
def state(uid):
    """꾸미기 창: 목록 · 가진 것 · 누가 무엇을 쓰고 있나 · 고를 수 있는 참가 묶음."""
    have = owned(uid)
    wear = equipped(uid)
    by = {}
    for pid, d in wear.items():
        for slot, key in d.items():
            by[key] = pid
    items = []
    for key, d in C.DECOS.items():
        items.append({"key": key, "kr": d["kr"], "slot": d["slot"], "slotKr": C.SLOT_KR[d["slot"]],
                      "desc": d.get("desc", ""), "owned": key in have, "wornBy": by.get(key),
                      "effect": d["slot"] in C.EFFECTS})
    return {"items": items, "picks": have.get(C.PICK, 0),
            "choices": [{"key": b, "kr": C.BUNDLE_KR[b], "items": [C.name(k) for k in C.BUNDLES[b]]}
                        for b in C.JOIN_CHOICES],
            "worn": dict((str(k), v) for k, v in wear.items())}
