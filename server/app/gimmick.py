# -*- coding: utf-8 -*-
"""Z기술 (시즌 4) · 테라스탈 (2.5.0) — 누가 쓸 수 있나, 테라 타입 바꾸기.

배틀 안의 규칙은 common/zmoves.py 와 common/tera.py 에 있다. 여기는 계정 쪽이다.

## Z링 · 테라오브

메가진화의 키스톤과 **같은 조건**이다 (관장 8곳, mega.has_keystone). 따로 적어 두지 않고
관장 기록으로 센다 - 이미 8곳을 넘긴 사람은 그 판이 열리는 순간 가진다 (Z링은 시즌 4, 테라오브는 2.5.0).

## 테라 타입

**테라피스는 지니는 도구다** (2.5.1, Z크리스탈과 같다) - 지닌 테라피스의 타입이 테라 타입이고, 테라피스를 지닌
포켓몬만 테라스탈한다 (common.tera.type_of · 지니게 하기는 main.hold). 안 지녔으면 테라 타입이 없다.
2.5.0 처음 판은 가방에서 한 번 써서 pokemon.tera 칸에 정하는 소모품이었다 - 그 칸은 이제 안 본다 (11/16 사용자).
"""

from . import mega


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
