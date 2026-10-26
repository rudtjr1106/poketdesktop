# -*- coding: utf-8 -*-
"""플라티나 테마의 '위젯 빛깔' - DP 의 것(skins/dp/widgets.py)에 하나를 더한다.

플라티나의 판 바깥은 강철 바탕(어두운 회색)이다. DP 틀을 물려받은 화면(박스 · 상점 · 관장 · 탐험 …)은
판 바깥 바탕에 바로 쓴 글(머리 줄의 정렬 탭 · '시·도 바로 가기' 같은 이름 · 아래 안내 글)이 있는데, DP 는
그 바탕이 밝아서 진한 글씨였다 - 강철 위에서는 안 읽힌다.

그래서 **캔버스에 진한 글을 쓸 때, 그 글 밑의 바탕(맨 위에 칠한 도형, 없으면 캔버스 바탕)이 강철이면**
글 빛깔을 강철 위에서 읽히는 밝은 빛으로 옮긴다 (Canvas._create 를 감싼다). 밝은 판 위의 글은 그대로다.
이 테마가 따로 그린 화면(가방 · 배틀 · 허브)은 글을 늘 단색 판 · 띠 위에 두므로 걸리지 않는다.
"""
import tkinter as tk

from ..dp import widgets as DPW
from . import BAR2, CYAN_TOP, ON_STEEL, ON_STEEL_DIM, RIM, STEEL, STEEL1, STEEL2
from . import _pt as P

_done = False
_FILLED = ("rectangle", "polygon", "oval", "arc", "image")
# 판 바깥 바탕 빛깔 (이것 위의 진한 글만 밝힌다 - 띠 · 단추 위의 글 그림자는 건드리지 않는다)
_STEELS = frozenset(c.lower() for c in (STEEL, STEEL1, STEEL2, RIM))


def _lum(c):
    r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b


def on_steel(c):
    """판 바깥(강철) 위에 바로 쓰는 글 빛깔: 어두운 글은 밝게, 빛깔 있는 글은 밝게 섞는다."""
    if not isinstance(c, str) or len(c) != 7 or not c.startswith("#"):
        return c
    lum = _lum(c)
    if lum >= 0.62:
        return c                                   # 이미 밝다 (흰 글씨 등)
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    if max(r, g, b) - min(r, g, b) < 40:           # 회색 글씨 -> 강철 위의 흰 · 옅은 회색
        return ON_STEEL if lum < 0.4 else ON_STEEL_DIM
    if c.lower() in ("#127ea8",):                  # 고른 탭 (하늘색 글자)
        return CYAN_TOP
    return P.mix(c, "#ffffff", 0.55)


def _on_steel_bg(cv, x, y):
    """(x, y) 둘레 2px 밑이 강철 바탕뿐인가 - 칠한 도형이 모두 강철 빛이고(없으면 캔버스 바탕이 강철),
    그림이 없을 때만 그렇다 (판 · 띠 · 단추가 하나라도 걸리면 아니다)."""
    try:
        found = False
        for i in cv.find_overlapping(x - 2, y - 2, x + 2, y + 2):
            t = cv.type(i)
            if t not in _FILLED or cv.itemcget(i, "state") == "hidden":
                continue
            if t == "image":
                return False
            f = str(cv.itemcget(i, "fill")).lower()
            if not f:
                continue
            if f not in _STEELS:
                return False
            found = True
        return found or str(cv.cget("bg")).lower() in _STEELS
    except tk.TclError:
        return False


def _hook():
    base = tk.Canvas._create

    def _create(self, itemType, args, kw):
        if itemType == "text":
            cnf = dict(args[-1]) if args and isinstance(args[-1], dict) else {}
            cnf.update(kw or {})
            fill = cnf.get("fill")
            coords = [a for a in args if not isinstance(a, dict)]
            if len(coords) == 1 and isinstance(coords[0], (tuple, list)):
                coords = list(coords[0])
            if isinstance(fill, str) and len(fill) == 7 and fill.startswith("#") and len(coords) >= 2 \
                    and _lum(fill) < 0.5:
                try:
                    x, y = float(coords[0]), float(coords[1])
                except (TypeError, ValueError):
                    x = None
                if x is not None and _on_steel_bg(self, x, y):
                    new = on_steel(fill)
                    if new != fill:
                        kw = dict(kw or {})
                        kw["fill"] = new
                        if args and isinstance(args[-1], dict) and "fill" in args[-1]:
                            args = tuple(args[:-1]) + (dict(args[-1], fill=new),)
        return base(self, itemType, args, kw)

    tk.Canvas._create = _create


def head_band(cv, w, h, band, line, title, tags=("head",), ty=None):
    """사교 묶음(친구 · 길드 · 게시판 · 랭킹)의 맨 위 띠 - DP 는 화면마다 빛깔 띠(귤빛 · 흙빛 · 파랑 · 보라)에
    흰 테두리 글씨 제목이다. 플라티나는 허브와 같은 머리 띠(강철 그라데이션 + 아래 3px 진한 줄)에
    흰 제목(아래 그림자)으로 맞춘다. 자리 · 크기 · 돌려주는 값(제목 오른쪽 끝 x)은 DP 의 것과 같다."""
    from ... import ui_common as U
    from ..dp import font
    try:
        if str(cv.cget("bg")).lower() != BAR2.lower():
            cv.configure(bg=BAR2)                  # 띠를 다시 그리기 전 잠깐 보이는 캔버스 바탕도 같은 빛
    except tk.TclError:
        pass
    P.head_band(cv, 0, 0, w, h, tags=tags)
    tid = P.band_title(cv, U.h(16), h // 2 - U.h(1) if ty is None else ty, title, font(14), tags=tags)
    bb = cv.bbox(tid)
    return bb[2] if bb else U.h(90)


def _patch_bands():
    """DP 의 사교 화면들이 쓰는 head_band 를 위의 것으로 (테마는 켤 때 하나뿐이라 이 실행에서만 바뀐다).
    rank 의 것을 바꾸고, 이미 `from .rank import head_band` 로 가져간 화면이 있으면 그것도 바꾼다."""
    import sys
    from ..dp import rank as DR
    base = DR.head_band
    DR.head_band = head_band
    pre = __name__.rsplit(".", 2)[0] + ".dp."
    for name, mod in list(sys.modules.items()):
        if name.startswith(pre) and mod is not None and getattr(mod, "head_band", None) is base:
            mod.head_band = head_band


def install(root, style):
    global _done
    DPW.install(root, style)
    if not _done:
        _done = True
        _hook()
        _patch_bands()
