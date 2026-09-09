# -*- coding: utf-8 -*-
"""기술 한 줄을 어떻게 적을지 한곳에 모아 둔다.

## 왜 모으나

기술은 네 곳에서 보여준다 - 포켓몬 관리, 기술머신 탭, 기술 배우기 창,
그리고 검사. 전에는 포켓몬 관리에만 적는 코드가 있었고, 검사는 그 코드를
**베껴서** 다시 적어 두고 있었다. 화면 쪽을 고치면 검사는 옛 문장을
지키는 꼴이라, 못 박아 둔 보람이 없다.

## 분류를 적는 이유

물리인지 특수인지가 어디에도 없었다. 같은 위력 90짜리 불꽃 기술이라도
공격이 높은 포켓몬이면 물리를, 특수공격이 높으면 특수를 골라야 하는데,
화면만 보고는 고를 수가 없었다.

    10만볼트  ·  특수  ·  위력 90  ·  명중 100  ·  PP 15

## 위력이 없는 기술

  · 변화 기술 271개는 위력 칸을 아예 안 적는다. '변화' 라고 적어 두면
    위력이 없다는 뜻이 이미 들어 있다.
  · 물리·특수인데 위력이 0인 기술이 77개 있다(참기, 집단구타, Z기술).
    자료가 없는 게 아니라 그때그때 달라지는 것이라, '위력 —' 로 둔다.
    '위력 0' 이라고 적으면 때려도 안 아픈 기술로 읽힌다.

명중률도 같다. 288개가 0인데 그건 **반드시 맞는다**는 뜻이다.
"""

CAT_KR = {"physical": "물리", "special": "특수", "status": "변화"}

# 분류마다 색을 달리한다. 글만 있으면 넉 줄을 훑을 때 눈에 안 들어온다.
CAT_COLOR = {"physical": "#e8734a", "special": "#4a9de8", "status": "#9aa3bd"}

SEP = "  ·  "


def cat_name(move):
    """'물리' / '특수' / '변화'. 모르는 값이면 그대로 돌려준다."""
    c = (move or {}).get("cat")
    return CAT_KR.get(c, c or "")


def cat_color(move, default="#9aa3bd"):
    return CAT_COLOR.get((move or {}).get("cat"), default)


def is_status(move):
    return (move or {}).get("cat") == "status"


def power_text(move):
    """위력 칸. 변화 기술이면 빈 글자(칸을 안 만든다)."""
    m = move or {}
    if is_status(m):
        return ""
    p = m.get("power")
    return "위력 %d" % p if p else "위력 —"


def acc_text(move):
    """명중 칸. 0 은 '반드시 맞는다' 라서 숫자로 적지 않는다."""
    a = (move or {}).get("acc")
    return "명중 %d" % a if a else "명중 —"


def stat_bits(move, with_cat=True):
    """분류·위력·명중·PP 를 순서대로. 없는 칸은 빠진다."""
    m = move or {}
    bits = []
    if with_cat and cat_name(m):
        bits.append(cat_name(m))
    p = power_text(m)
    if p:
        bits.append(p)
    bits.append(acc_text(m))
    if m.get("pp"):
        bits.append("PP %d" % m["pp"])
    return bits


def stat_line(move, name=None):
    """`10만볼트  ·  특수  ·  위력 90  ·  명중 100  ·  PP 15`

    name 을 주면 맨 앞에 붙인다. 이름을 따로 크게 적는 화면에서는
    빼고 부르면 된다.
    """
    bits = stat_bits(move)
    if name:
        bits = [name] + bits
    return SEP.join(bits)


def short_line(move):
    """좁은 칸에 넣을 짧은 꼴. `특수 · 90` / `변화`"""
    m = move or {}
    c = cat_name(m)
    if is_status(m):
        return c
    p = m.get("power")
    return "%s · %s" % (c, p) if p else c


def desc(move):
    """설명. 도감 919개에 다 들어 있지만 만에 하나를 대비한다."""
    return (move or {}).get("desc") or "설명이 아직 없는 기술입니다."
