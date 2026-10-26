# -*- coding: utf-8 -*-
"""DP 틀을 물려받는 테마 (플라티나 · 금은 · 에메랄드 · 블랙화이트 · 소드실드).

DP v2 에서 화면 40여 개를 '단순 · 잘 보임 · 기본 크기' 로 다시 짰다. 다른 세대 테마는 그 틀을 그대로 받고,
그 세대 것으로 바꿀 것만 바꾼다:

    skins/<열쇠>/__init__.py     BASE = "dp" 와 그 테마의 빛깔 · 글꼴
        FONT                      글꼴 이름 (Skin.fonts 에 그 파일을 적는다)
        PALETTE = {상수: 빛깔}    skins/dp/__init__.py 의 상수(INK · CUR · PANEL …)를 바꿔 끼운다
        COLORS = {DP 빛깔: 빛깔}  DP 화면 코드에 박힌 빛깔을 하나하나 옮길 때
        def shade(rgb): ...       표에 없는 DP 빛깔을 옮기는 규칙 (0~1 의 r, g, b -> r, g, b). 없어도 된다
        RADIUS_K                  둥근 모서리 배율 (게임보이처럼 각지게 = 0)
    skins/<열쇠>/<화면>.py         그 세대 방식으로 새로 짠 화면 (없으면 DP 의 것을 쓴다 - skins.view)

빛깔을 옮기는 자리는 tkinter 가 옵션을 Tcl 로 넘기는 한 곳(Misc._options)이다. 위젯을 만들 때 · configure ·
캔버스 도형 · 글 칸 태그가 다 여기를 지난다. **DP 코드에 박힌 빛깔(dp/_literals.py)만** 옮기고, 코드가 셈한 빛깔
(타입 빛깔을 옅게 섞은 기술 단추 같은 것)과 타입 빛깔 · 체력 빛깔은 그대로 둔다 - 뜻이 있는 빛깔이다.
"""
import colorsys
import tkinter as tk

COLOR_KEYS = frozenset((
    "fill", "outline", "activefill", "activeoutline", "disabledfill", "disabledoutline",
    "background", "bg", "foreground", "fg", "activebackground", "activeforeground",
    "highlightbackground", "highlightcolor", "insertbackground", "selectbackground", "selectforeground",
    "disabledforeground", "disabledbackground", "readonlybackground", "troughcolor", "selectcolor",
))

# 어느 테마에서도 옮기지 않는 DP 빛깔 - 장면 · 뜻이 있는 빛깔이다 (배틀 하늘 · 풀밭 · 받침 · 체력 · 성별 · 상태 ·
# 몬스터볼 · 기술 분류, 관장 지도의 바다 · 땅, 길드전 지도의 바다, 악당 칸의 상태). 테마의 KEEP 에 더 적을 수 있다.
KEEP_ALWAYS = frozenset((
    "#5cb9a4", "#8fd4bc", "#c6ecd8", "#a8d67e", "#8cc464",            # 배틀 하늘 · 풀밭
    "#b29862", "#d8c28c", "#ecdeb0",                                  # 배틀 받침
    "#7af09a", "#40c868", "#f8e048", "#d0a810", "#f87060", "#c83838",  # 체력 막대
    "#3070e0", "#e04040",                                             # ♂ ♀
    "#e07030", "#c8a818", "#a040a0", "#802080", "#8c8c70", "#58b0c8",  # 상태 이상
    "#e85050", "#c0501c", "#2860c0",                                  # 몬스터볼 위 · 물리 · 특수
    "#7fb2e5", "#a8d070", "#2f5a2a",                                  # 관장 지도 (바다 · 땅 · 경계)
    "#b4daf2", "#7ab0d6",                                             # 길드전 지도 바다
    "#23813f", "#d02e34",                                             # 악당 칸 (이김 · 도전)
))

_installed = None


def _rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v * 255)))) for v in rgb)


def hsv(c):
    return colorsys.rgb_to_hsv(*_rgb(c))


def from_hsv(h, s, v):
    return _hex(colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v))))


class Recolor(object):
    """DP 빛깔 -> 그 테마 빛깔. 같은 빛깔은 한 번만 셈한다."""

    def __init__(self, theme, literals, keep=()):
        self.colors = dict((k.lower(), v.lower()) for k, v in (getattr(theme, "COLORS", {}) or {}).items())
        self.shade = getattr(theme, "shade", None)
        self.literals = literals
        # 뜻이 있는 빛깔 (타입 · 체력 · 테마 상수의 새 값)은 옮기지 않는다 - 옮긴 빛깔을 또 옮기지 않게도
        self.keep = set(c.lower() for c in keep)
        self.keep.update(KEEP_ALWAYS)
        self.keep.update(c.lower() for c in (getattr(theme, "KEEP", ()) or ()))
        self.keep.update(v.lower() for v in self.colors.values())
        self._memo = {}

    def __call__(self, c):
        if not isinstance(c, str) or len(c) != 7 or c[0] != "#":
            return c
        low = c.lower()
        got = self._memo.get(low)
        if got is not None:
            return got
        out = low
        if low in self.colors:
            out = self.colors[low]
        elif low not in self.keep and low in self.literals and self.shade is not None:
            out = _hex(self.shade(_rgb(low)))
        self._memo[low] = out
        if out != low:
            self._memo.setdefault(out, out)       # 옮겨 간 빛깔은 다시 옮기지 않는다 (cget 으로 읽어 되넘길 때)
        return out


def install(theme, literals, keep=()):
    """tkinter 가 옵션을 넘기는 자리에 빛깔 옮기기를 건다 (한 번만)."""
    global _installed
    if _installed is not None:
        return _installed
    fn = Recolor(theme, literals, keep)
    base = tk.Misc._options

    def _options(self, cnf, kw=None):
        res = base(self, cnf, kw)
        if not res:
            return res
        out = list(res)
        for i in range(0, len(out) - 1, 2):
            k = out[i]
            if isinstance(k, str) and k[1:] in COLOR_KEYS:
                out[i + 1] = fn(out[i + 1])
        return tuple(out)

    tk.Misc._options = _options
    _installed = fn
    return fn
