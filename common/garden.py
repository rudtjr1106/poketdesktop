# -*- coding: utf-8 -*-
"""열매 텃밭 (시즌 7) — 규칙 숫자와 순수 계산 (서버가 쓰고, 앱도 읽는다).

  · 묶음: 지닌 열매 47종(common/held.py 의 표)을 자라는 시간 4 · 8 · 16시간으로 나눈다. 오래 걸릴수록 많이 나온다 -
    밤 · 주말에 심어 두는 열매. 열매 표에서 바로 나누므로 held.py 에 열매가 늘면 검사(test_garden_common)가 먼저 잡는다.
  · 단계: 자라는 시간의 1/3씩 1 새싹 · 2 줄기 · 3 꽃, 다 지나면 4 익음 (0 = 빈 화분). 서버가 읽을 때 시계로 센다.
  · 물: 준 그 순간의 단계 비트 (bit0 새싹 · bit1 줄기 · bit2 꽃). 단계마다 한 번이면 된다.
  · 열매 수 = 기본(4h 1 · 8h 2 · 16h 3) + 물 준 단계 수(0~3) + 친구 보너스(0~1). 안 돌봐도 기본은 나온다 (벌칙 없음).
  · 풀 타입 빠르기: 심을 때 바탕화면 파티의 풀 타입 한 마리당 10%, 셋(30%)에서 멈춘다.

설계: design-notes/2026-11-26-garden.md
"""
from . import held as H

STAGES = 3                  # 자라는 단계 수 (새싹 · 줄기 · 꽃) - 그다음이 익음
RIPE = STAGES + 1
STAGE_KR = {0: "빈 화분", 1: "새싹", 2: "줄기", 3: "꽃", 4: "익음"}
BASE = {4: 1, 8: 2, 16: 3}  # 묶음(시간) -> 기본 열매 수
GRASS_STEP = 10             # 풀 타입 한 마리당 빨라지는 % (정수로 세야 0.7 이 0.69999… 가 되지 않는다)
GRASS_MAX = 3               # 이 수에서 멈춘다 (30%)
MIN_GROW = 3                # 배율이 아무리 작아도 단계마다 1초는 남긴다 (0 으로 나누기 · 한꺼번에 익기 막기)

# 혼란 회복 열매 다섯은 HEAL 표에 있지만 8시간 - 체력 1/3 회복이라 오랭 · 자뭉보다 세다 (설계 수치 표)
CONFUSE_BERRY = frozenset(("FIGYBERRY", "WIKIBERRY", "MAGOBERRY", "AGUAVBERRY", "IAPAPABERRY"))
# 표에 따로 없는 한 번 쓰는 열매들. 과사 · 시몬은 가벼워서 4시간, 나머지는 배틀을 뒤집는 것이라 16시간
_FOUR_EXTRA = ("LEPPABERRY", "PERSIMBERRY")
_SIXTEEN_EXTRA = ("CUSTAPBERRY", "ENIGMABERRY", "JABOCABERRY", "ROWAPBERRY")


def _groups():
    out = {}
    for k in list(H.CURE_BERRY) + [k for k in H.HEAL_BERRY if k not in CONFUSE_BERRY] + list(_FOUR_EXTRA):
        out[k] = 4
    for k in list(H.RESIST_BERRY) + sorted(CONFUSE_BERRY):
        out[k] = 8
    for k in list(H.PINCH_BERRY) + list(H.HIT_CAT_BERRY) + list(_SIXTEEN_EXTRA):
        out[k] = 16
    return out


GROUP = _groups()           # 열매 id -> 4 | 8 | 16


def group_of(berry):
    """그 열매의 묶음 (시간). 심을 수 없는 것(지닌 열매가 아님)이면 None."""
    return GROUP.get(str(berry or "").upper())


def stage_at(age_sec, grow_sec):
    """심은 지 age_sec 초 된 화분의 단계 1..4. 시계가 거꾸로(음수)여도 새싹."""
    age = max(0, int(age_sec))
    grow = max(1, int(grow_sec))
    return min(RIPE, 1 + (STAGES * age) // grow)


def next_change(age_sec, grow_sec):
    """다음 단계까지 남은 초 (앱이 이때 다시 묻는다). 익었으면 None.

    stage_at 과 같은 정수 경계 - 단계 s 는 STAGES*age >= s*grow 인 첫 초에 넘어간다 (올림)."""
    age = max(0, int(age_sec))
    grow = max(1, int(grow_sec))
    s = stage_at(age, grow)
    if s >= RIPE:
        return None
    return -(-s * grow // STAGES) - age


def wet_bit(stage):
    """그 단계의 물 비트 (새싹 1 · 줄기 2 · 꽃 4). 빈 화분 · 익음은 0 - 물을 줄 단계가 아니다."""
    return 1 << (stage - 1) if 1 <= stage <= STAGES else 0


def wet_count(wet_mask):
    """물 준 단계 수 (0~3). 세 단계 밖의 비트는 안 센다."""
    m = int(wet_mask or 0)
    return sum(1 for s in range(1, STAGES + 1) if m & wet_bit(s))


def yield_of(group, wet_mask, friend_bonus):
    """지금 익는다면 나올 열매 수 = 기본 + 물 준 단계 수 + 친구 보너스(많이 받아도 1)."""
    return BASE[int(group)] + wet_count(wet_mask) + min(1, max(0, int(friend_bonus or 0)))


def grow_sec(group, grass_n, scale=1.0):
    """다 자라기까지 초. 풀 타입 n 마리면 n x 10% (셋까지) 빨리, 그리고 배율(시험용 GARDEN_SCALE)을 곱한다."""
    pct = 100 - GRASS_STEP * min(GRASS_MAX, max(0, int(grass_n or 0)))
    return max(MIN_GROW, int(round(int(group) * 3600 * pct / 100.0 * float(scale))))
