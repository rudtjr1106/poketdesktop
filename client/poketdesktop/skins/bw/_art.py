# -*- coding: utf-8 -*-
"""블랙·화이트 테마의 그리기 조각 (시안 H 의 바탕 · 테 · 고름 표시).

    backdrop   창 바탕: 짙은 회색 + 옅은 빗금 한 줄 + 오른쪽 아래 C기어 고리 두 겹 (판 바깥에만 보인다)
    panel      판: #22262b 바탕 · #3d444c 가는 테 · 둥근 모서리 10
    lit        고른 것: 하늘빛 테 + 둘레에 번지는 빛 (시안의 box-shadow 를 미리 섞은 빛깔 두 겹)
    pill       알약 (테 한 겹), 고르면 lit 처럼
    ring       동그란 고리 단추 (주머니 · 도구 그림 고리)

빛깔은 skins/bw/__init__.py 의 시안 빛깔만 쓴다. 글씨는 늘 단색 판 위에 둔다 - 무늬는 바탕에만.
"""
import math

from ... import ui_common as U
from ..dp import kit as K
from . import (BG, CYAN, GLOW, GLOW_BG, GLOW_FAR, LINE, LINE_HI, PANEL, PANEL_HI, RING_FAR, STRIPE)


def _clip(poly, x1, y1, x2, y2):
    return K._clip_poly(poly, x1, y1, x2, y2)


def stripe(cv, x1, y1, x2, y2, fill=STRIPE, a=0.62, b=0.72, deg=115, tags=()):
    """CSS linear-gradient(115deg, … 62% … 72% …) 의 옅은 띠 한 줄."""
    w, h = float(x2 - x1), float(y2 - y1)
    rad = math.radians(deg)
    dx, dy = math.sin(rad), -math.cos(rad)            # 번지는 방향 (화면 좌표, y 아래)
    L = abs(w * dx) + abs(h * dy)
    cx, cy = w / 2.0, h / 2.0

    def line_at(t):
        # d·(p - c) = t*L - L/2 인 직선이 y=0, y=h 에서 지나는 x
        k = t * L - L / 2.0
        xs = []
        for yy in (0.0, h):
            xs.append((k - dy * (yy - cy)) / dx + cx)
        return xs
    (ta, tb), (ua, ub) = line_at(a), line_at(b)
    poly = [(ta, 0.0), (ua, 0.0), (ub, h), (tb, h)]
    pts = _clip(poly, 0, 0, w, h)
    if len(pts) >= 3:
        flat = []
        for px, py in pts:
            flat += [x1 + px, y1 + py]
        cv.create_polygon(flat, fill=fill, outline="", tags=tags)


def rings(cv, x1, y1, x2, y2, tags=(), scale=1.0):
    """C기어 고리 두 겹 - 시안의 radial-gradient(circle at 96% 104%, … 84-88px, … 136-140px)."""
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w * 0.96, y1 + h * 1.04
    for r0, r1, col in ((84, 88, GLOW_FAR), (136, 140, RING_FAR)):
        r = U.h((r0 + r1) / 2.0 * scale)
        lw = max(2, U.h(4 * scale))
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=col, width=lw, tags=tags)


def backdrop(cv, x1, y1, x2, y2, tags=(), with_rings=True, with_stripe=True):
    cv.create_rectangle(x1, y1, x2, y2, fill=BG, outline="", tags=tags)
    if with_stripe:
        stripe(cv, x1, y1, x2, y2, tags=tags)
    if with_rings:
        rings(cv, x1, y1, x2, y2, tags=tags)


def panel(cv, x1, y1, x2, y2, r=10, fill=PANEL, line=LINE, tags=()):
    return K.rrect(cv, x1, y1, x2, y2, U.h(r), fill=fill, outline=line, width=1, tags=tags)


def lit(cv, x1, y1, x2, y2, r, fill, on_bg=False, tags=(), width=2):
    """고른 것: 둘레 빛 두 겹 + 하늘빛 테. 몸 도형 id."""
    g1, g2 = U.h(5), U.h(2)
    K.rrect(cv, x1 - g1, y1 - g1, x2 + g1, y2 + g1, r + g1, fill=GLOW_FAR, tags=tags)
    K.rrect(cv, x1 - g2, y1 - g2, x2 + g2, y2 + g2, r + g2, fill=GLOW_BG if on_bg else GLOW, tags=tags)
    return K.rrect(cv, x1, y1, x2, y2, r, fill=fill, outline=CYAN, width=width, tags=tags)


def pill(cv, x1, y1, x2, y2, on=False, hover=False, fill=None, tags=(), on_bg=False):
    """알약 (시안 .seg · .sub · .money). 몸 도형 id."""
    r = (y2 - y1) // 2
    body = fill or (PANEL_HI if hover and not on else PANEL)
    if on:
        return lit(cv, x1, y1, x2, y2, r, body, on_bg=on_bg, tags=tags, width=1)
    return K.rrect(cv, x1, y1, x2, y2, r, fill=body, outline=LINE_HI if hover else LINE, width=1, tags=tags)


def ring(cv, cx, cy, rad, on=False, hover=False, fill=PANEL, tags=(), width=None):
    """동그란 고리 단추 (시안 .pk span · .ring). on 이면 하늘빛 테 + 번지는 빛."""
    lw = width or max(2, U.h(2))
    if on:
        for g, col in ((U.h(8), GLOW_FAR), (U.h(4), GLOW_BG)):
            cv.create_oval(cx - rad - g, cy - rad - g, cx + rad + g, cy + rad + g, fill=col, outline="", tags=tags)
    edge = CYAN if on else (LINE_HI if hover else LINE)
    body = PANEL_HI if (hover and not on) else fill
    return cv.create_oval(cx - rad, cy - rad, cx + rad, cy + rad, fill=body, outline=edge, width=lw, tags=tags)
