# -*- coding: utf-8 -*-
"""Z기술 (시즌 4) · 테라스탈 (2.5.0) — 누가 쓸 수 있나, 테라 타입 바꾸기.

배틀 안의 규칙은 common/zmoves.py 와 common/tera.py 에 있다. 여기는 계정 쪽이다.

## Z링 · 테라오브

메가진화의 키스톤과 **같은 조건**이다 (관장 8곳, mega.has_keystone). 따로 적어 두지 않고
관장 기록으로 센다 - 이미 8곳을 넘긴 사람은 그 판이 열리는 순간 가진다 (Z링은 시즌 4, 테라오브는 2.5.0).

## 테라 타입

포켓몬마다 하나. 정하지 않았으면 그 종의 첫째 타입이다 (common.tera.default_type).
'테라피스'(타입마다 하나씩 18종) 하나를 쓰면 그 타입으로 바뀐다 (item_routes._use_tera 가
가방에서 뺀다). 이미 그 타입이면 안 쓴다.
"""
from common import tera as TR

from . import db, deps, mega


def has_zring(uid):
    return mega.has_keystone(uid)


def has_orb(uid):
    return mega.has_keystone(uid)


def flags(a_uid, b_uid=None):
    """배틀 엔진에 넘길 꼴: {"me": Z링, "foe": Z링}."""
    return {"me": has_zring(a_uid), "foe": has_zring(b_uid) if b_uid is not None else False}


def orbs(a_uid, b_uid=None):
    """배틀 엔진에 넘길 꼴: {"me": 테라오브, "foe": 테라오브} (2.5.0)."""
    return {"me": has_orb(a_uid), "foe": has_orb(b_uid) if b_uid is not None else False}


def card(uid):
    """화면에 줄 것: 가졌나, 관장을 몇 곳 더 이겨야 하나."""
    k = mega.keystone_card(uid)
    return {"zring": k["has"], "teraOrb": k["has"], "gyms": k["gyms"], "need": k["need"]}


def tera_of(mon):
    return TR.type_of(deps.dex(), mon)


def set_tera(uid, pid, tera_type):
    """이 포켓몬의 테라 타입을 바꾼다. 바뀌었으면 True, 이미 그 타입이면 False.

    **조건을 건 UPDATE 다** - 지금 테라 타입이 다를 때만 바꾼다. 두 창에서 같은 테라피스를 동시에 써도
    한쪽만 바뀌고(True), 다른 쪽은 False 를 받아 테라피스를 안 쓴다.
    """
    t = str(tera_type or "").upper()
    if not TR.valid(t):
        raise ValueError("그런 테라 타입은 없습니다.")
    r = db.q1("SELECT * FROM pokemon WHERE id=? AND user_id=?", (pid, uid))
    if not r:
        raise LookupError("그 포켓몬이 없습니다.")
    if tera_of(db.row_to_mon(r)) == t:
        return False
    old = r["tera"] if "tera" in r.keys() else None
    cur = db.run("UPDATE pokemon SET tera=? WHERE id=? AND user_id=? AND tera IS ?", (t, pid, uid, old))
    return cur.rowcount > 0
