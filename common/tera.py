# -*- coding: utf-8 -*-
"""테라스탈 (2.5.0) — 본가 스칼렛·바이올렛의 규칙.

    · 한 판에 한 번. 쓰러지거나 판이 끝날 때까지 간다 (교체해도 안 풀린다).
    · 타입이 **테라 타입 하나**로 바뀐다 (받는 상성이 통째로 바뀐다).
    · 자속: 테라 타입 기술은 1.5배, 테라 타입이 원래 타입 중 하나면 2배 (적응력은 2 / 2.25배).
      **원래 타입 기술의 자속 1.5배는 그대로 남는다** - 타입이 바뀌어도 잃지 않는다.
    · 테라 타입 기술의 위력이 60 미만이면 60 으로 친다 (연속기·선공기·Z기술, 위력이 상대·체력에 따라
      정해지는 기술 가운데 도감 위력이 0·150 인 것은 빼고 - 본가와 같다).
    · 테라버스트는 테라 타입 기술이 되고, 공격·특수공격 중 높은 쪽으로 친다
      (높은 쪽으로 치는 것은 attackfx.HIGHER_STAT 이 이미 하고 있다).
    · 테라스탈한 포켓몬의 타입은 다른 것이 못 바꾼다 (물붓기·변환자재·불태우기 ...).

안 넣은 것: 스텔라 타입, 오거폰·테라파고스의 전용 처리.

**테라피스는 지니는 도구다 (2.5.1, Z크리스탈과 같다)** - 테라피스를 지닌 포켓몬만 테라스탈하고, 지닌 테라피스의
타입이 테라 타입이다 (11/16 사용자 "테라피스가 있어야 되는 거 아니야? · 지닌도구류로 해줘"). 지니지 않은 포켓몬은
테라 타입이 없다 - 테라오브가 있어도 단추가 안 뜨고 AI 도 안 쓴다. 테라피스는 뺏기거나 떨어지지 않는다 (held.stuck).
2.5.0 처음 판은 가방에서 한 번 써서 정하는 소모품이었고(mon["tera"] 칸 - 이제 안 본다), 정하지 않은 포켓몬은 그 종의
첫째 타입으로 쳤다. 메가진화한 포켓몬은 테라스탈하지 못하고, 테라스탈한
포켓몬은 메가진화하지 못한다 - 본가에 없는 조합이라 이 게임이 정한 것이다 (battle.Battle.can_tera).
처음 넣은 것은 시즌 4 (1.11.0) 준비 때이고, 그때는 내지 않고 뺐다가 2.5.0 에서 다시 넣었다.
"""

TYPES = ("NORMAL", "FIRE", "WATER", "ELECTRIC", "GRASS", "ICE", "FIGHTING", "POISON", "GROUND",
         "FLYING", "PSYCHIC", "BUG", "ROCK", "GHOST", "DRAGON", "DARK", "STEEL", "FAIRY")
FLOOR = 60                 # 테라 타입 기술의 최저 위력
STAB = 1.5


def valid(t):
    return t in TYPES


# 테라피스 18종 - 도구 열쇠 'FAIRYTERASHARD' -> 'FAIRY' (스텔라는 없다)
SHARDS = dict((t + "TERASHARD", t) for t in TYPES)


def is_shard(item):
    return bool(item) and item in SHARDS


def shard_type(item):
    """지닌 도구가 테라피스면 그 타입, 아니면 None."""
    return SHARDS.get(item) if item else None


def type_of(dex, mon):
    """이 포켓몬의 테라 타입 = 지닌 테라피스의 타입. 안 지녔으면 None (테라스탈하지 못한다).
    dex 는 예전 꼴(정하지 않으면 첫째 타입)과 부르는 곳을 맞추려고 남겨 둔다."""
    return shard_type((mon or {}).get("held"))


def stab(orig, tera, mtype, base=STAB):
    """테라스탈한 포켓몬이 mtype 기술을 쓸 때의 자속 배율. 자속이 아니면 1.

    orig 는 테라스탈하기 전의 타입들, base 는 보통의 자속 배율이다 (적응력이면 2.0 이 온다).
    """
    adapt = base > STAB
    if mtype == tera:
        if tera in (orig or ()):
            return 2.25 if adapt else 2.0
        return 2.0 if adapt else STAB
    if mtype in (orig or ()):
        return STAB                       # 원래 타입의 자속은 남는다 (적응력은 테라 타입에만 붙는다)
    return 1.0


def floor_power(power, move, mtype, tera, variable=False):
    """테라 타입 기술의 위력 보정. 연속기·선공기·Z기술은 그대로 둔다.

    variable: 위력이 상대·체력에 따라 정해지고 도감 위력이 0·150 인 기술 (로킥·분화 ...) - 본가처럼 그대로 둔다.
    """
    if not tera or mtype != tera or not 0 < power < FLOOR or (move or {}).get("_z") or variable:
        return power
    hits = ((move or {}).get("hits") or [1, 1]) + [1, 1]
    if hits[1] > 1 or ((move or {}).get("pri") or 0) > 0:
        return power
    return FLOOR
