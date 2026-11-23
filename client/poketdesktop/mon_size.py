# -*- coding: utf-8 -*-
"""배틀 창에서 포켓몬 도트의 키를 도감의 실제 키로 정한다 (2.5.5, 11/23 게시판 #777 댕댕킴).

예전에는 관장 · 실시간 · 레이드 배틀 창이 모든 도트를 같은 높이(내 쪽 132px · 상대 108px ...)로 늘리거나 줄였다.
그래서 따라큐(0.2m, 도트 66px)는 두 배로 커지고 리자몽(1.7m, 127px)은 그대로라 키가 같아 보였다. 쇼다운 도트의
원래 크기도 실제 키와 잘 안 맞는다 (따라큐 66px > 피카츄 59px, 고래왕 80px < 리자몽 127px - 823종을 재 보니 상관
0.63) - 그래서 도트 크기가 아니라 **도감의 키**로 정한다.

키를 그대로 비율로 쓰면 0.1m ~ 14.5m 라 너무 벌어진다. 로그로 눌러서 SMALL_M 이하는 칸 높이의 MIN_RATIO,
BIG_M 이상은 칸을 다 쓰고 그 사이는 완만하게 커진다:

    따라큐 · 파쪼옥 0.45 · 피카츄 0.51 · 이상해씨 0.64 · 리자몽 0.84 · 잠만보 0.89 · 그란돈 · 고래왕 1.0

도트는 지금처럼 발을 바닥에 붙여 세운다 (anchor "s") - 작아져도 떠 보이지 않는다. 메가 · 폼은 그 모습의 키
(도감 megas · forms 에 있다), 없으면 원래 종의 키. 키를 모르면 예전처럼 칸을 다 쓴다.
"""
import math

SMALL_M = 0.3           # 이 키(m) 이하는 가장 작게
BIG_M = 3.5             # 이 키 이상은 칸을 다 쓴다
MIN_RATIO = 0.45        # 가장 작은 포켓몬은 칸 높이의 이만큼


def ratio(height_m):
    """실제 키(m) -> 칸 높이에 곱할 몫 (MIN_RATIO ~ 1.0). 모르면 1.0 (예전과 같다)."""
    try:
        h = float(height_m)
    except (TypeError, ValueError):
        return 1.0
    if not h > 0:
        return 1.0
    t = (math.log(h) - math.log(SMALL_M)) / (math.log(BIG_M) - math.log(SMALL_M))
    t = max(0.0, min(1.0, t))
    return MIN_RATIO + (1.0 - MIN_RATIO) * t


def height_of(dex, num):
    """도감 번호의 키(m). 메가 · 폼에 키가 없으면 원래 종의 키. 모르면 None."""
    if dex is None or not num:
        return None
    try:
        sp = dex.get(int(num))
    except Exception:                                       # noqa: BLE001
        return None
    if not sp:
        return None
    h = sp.get("height")
    if h:
        return h
    base = sp.get("megaOf") or sp.get("formOf")
    if base:
        try:
            b = dex.get(base)
        except Exception:                                   # noqa: BLE001
            b = None
        if b and b.get("height"):
            return b["height"]
    return None


def fit(dex, num, size):
    """칸 높이 size(px) 를 이 포켓몬의 키에 맞춘 높이 (1px 이상)."""
    return max(1, int(round(size * ratio(height_of(dex, num)))))
