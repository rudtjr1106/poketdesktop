# -*- coding: utf-8 -*-
"""낚아서 잡은 포켓몬의 잰 무게를 글로 (시즌 7 낚시). 관리 창 상세 일곱 곳 · 낚시 기록 창이 같이 쓴다.

서버가 공개 포켓몬에 싣는 `fish` = {"g": 그램, "ratio": 같은 종 표준 무게의 몇 배, "species": 잰 때의 종, "kr": 그 한글 이름}.
**잰 때의 종으로 적는다** - 잉어킹일 때 낚아 갸라도스로 진화해도 '잉어킹일 때 84.2kg' (진화하면 표준 무게가 달라져
배율이 뜻을 잃는다). 보여 주기만 한다 - 배틀 능력 · 헤비볼 · 무게 기술과는 상관없다.
"""
from decimal import ROUND_FLOOR, Decimal

# 배지 문턱 - 서버(common/fishing.badge)와 같다. 1.3배 이상 대물, 1.6배 이상 왕대물.
BIG, HUGE = 1.3, 1.6
BADGE_KR = {"big": "대물", "huge": "왕대물"}


def kg_text(g):
    """그램 -> '84.2kg' (10kg 이상은 소수 첫째 자리) / '0.40kg' (10kg 미만은 둘째 자리 - 작은 종도 차이가 보이게)."""
    kg = max(0, int(g or 0)) / 1000.0
    return ("%.2fkg" if round(kg, 2) < 10 else "%.1fkg") % kg


def ratio_text(ratio):
    """1.3149 -> '1.31배'. **내려서 적는다** (1.5973 -> '1.59배').

    반올림하면 1.5973 이 '1.60배' 로 보이는데 배지는 원래 값으로 '대물'(왕대물 아님)이라 서로 어긋난다.
    내리면 '1.60배' 는 늘 1.6 이상이다. 배지(badge)는 원래 값을 그대로 쓴다.
    부동소수를 100 배 해서 내리면 1.15 가 114.999… 로 '1.14배' 가 된다 - 짧은 십진 표기(repr)로 셈한다
    (서버가 JSON 으로 보낸 글 그대로다).
    """
    try:
        d = Decimal(repr(float(ratio or 0))).quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
    except (TypeError, ValueError, ArithmeticError):
        return "%.2f배" % float(ratio or 0)
    return "%s배" % d


def badge(ratio):
    """'huge' (왕대물) · 'big' (대물) · None."""
    r = float(ratio or 0)
    if r >= HUGE:
        return "huge"
    return "big" if r >= BIG else None


def line(mon):
    """관리 창 상세의 한 줄 - '낚시 · 잉어킹일 때 84.2kg · 표준의 1.31배'. 낚아서 잡은 포켓몬이 아니면 None."""
    f = (mon or {}).get("fish")
    if not isinstance(f, dict) or not f.get("g"):
        return None
    name = f.get("kr") or f.get("species") or ""
    when = ("%s일 때 " % name) if name else ""
    return "낚시 · %s%s · 표준의 %s" % (when, kg_text(f["g"]), ratio_text(f.get("ratio")))
