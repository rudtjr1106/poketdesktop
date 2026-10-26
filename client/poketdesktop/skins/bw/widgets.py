# -*- coding: utf-8 -*-
"""블랙·화이트 테마의 '위젯 빛깔' - 따로 그리지 않은 화면과 작은 창.

DP 의 위젯 옮기기(skins/dp/widgets.py - 기본 화면 코드가 만든 위젯의 빛깔 · 글꼴을 만들 때 · configure 할 때
옮긴다)를 그대로 쓰고, 옮겨 갈 빛깔만 BW 것으로 바꾼다. 기본 테마도 어두운 테마라 거의 그대로 옮긴다:

    바탕   남색 기운의 어두운 빛 -> 시안의 짙은 회색 (창 #15181c · 판 #22262b · 테 #3d444c)
    글씨   밝은 글씨는 그대로, 남색 기운의 흐린 글씨 -> 시안의 #99a2ac, 금빛 강조 -> 하늘빛
    단추   시안의 알약 단추 (주된 일 = 하늘빛 알약에 짙은 글씨, 보조 = 어두운 알약 · 가는 테)
    고르기 단추 줄  고른 칸은 하늘빛 글씨 (시안 .seg)

뜨는 메뉴(U.PopupMenu)는 DP 쪽 규칙대로 옮기지 않는다 - 기본 모습 그대로.
"""
import colorsys
import tkinter as tk

from ... import ui_common as U
from ..dp import font
from ..dp import kit as K
from ..dp import widgets as W
from . import OWN, PALETTE
from . import (BG, CARD, CYAN, CYAN_HI, CYAN_LO, DIMT, FAINT, GO_INK, LINE, LINE_HI, PANEL, PANEL_HI, SEL,
               TEXT, mix)

_done = False

BG_MAP = {
    U.INK: "#101215",          # 입력칸 · 액자 안
    U.BG: BG,                  # 창 바탕
    U.BG2: CARD,               # 패널
    U.BG3: PANEL,              # 올라온 요소
    U.BG4: PANEL_HI,           # 올렸을 때
    U.LINE: LINE,
    U.LINE2: LINE_HI,
    U.ACCENT_DARK: "#12323e",  # 금빛 보조 단추 바탕 -> 짙은 하늘빛
    U.ACCENT_SOFT: SEL,        # 고른 카드
    U.ACCENT_SHADOW: CYAN_LO,
    U.DISABLED_BG: CARD,
    U.DISABLED_SHADOW: "#101215",
    U.TIP_BG: "#101215",
    "#161b28": PANEL,          # 화면들의 카드 (CARD)
}
FG_MAP = {
    U.FG: TEXT,
    U.FG_DIM: DIMT,
    U.FG_FAINT: FAINT,
    U.ACCENT: CYAN,            # 금빛 강조 글씨 -> 하늘빛
    U.ACCENT_TEXT: "#bfeefc",
    U.TIP_FG: TEXT,
    U.DISABLED_FG: "#5f666e",
    U.ACCENT_DARK: CYAN,
}


# 이 테마가 직접 쓰는 빛깔 - 이미 BW 빛깔이므로 다시 옮기지 않는다 (어느 길로 configure 되든)
MINE = frozenset(c.lower() for c in list(OWN.values()) + list(PALETTE.values()))


def _rgb(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def bg(c):
    """기본 테마의 바탕 -> BW. 남색 기운의 어두운 빛만 회색으로 (빨간 단추 · 타입 빛깔은 그대로)."""
    if not W._is_hex(c) or c.lower() in MINE:
        return c
    for k, v in BG_MAP.items():
        if k.lower() == c.lower():
            return v
    h, s, v = colorsys.rgb_to_hsv(*_rgb(c))
    if v < 0.45 and s < 0.6:
        return W._hex(colorsys.hsv_to_rgb(0.58, min(s, 0.12), v))
    return c


def fg(c):
    """기본 테마의 글씨 -> BW. 밝은 글씨는 그대로, 남색 기운의 흐린 회색만 시안의 회색으로."""
    if not W._is_hex(c) or c.lower() in MINE:
        return c
    for k, v in FG_MAP.items():
        if k.lower() == c.lower():
            return v
    h, s, v = colorsys.rgb_to_hsv(*_rgb(c))
    if s < 0.3 and v > 0.3:                        # (어두운 글씨는 밝은 단추 위의 것 - 그대로)
        return W._hex(colorsys.hsv_to_rgb(0.58, min(s, 0.06), v))
    return c


# ---------------------------------------------------------------- 단추 (시안 .go / .sub / .money)
# (몸, 올렸을 때, 테, 글씨)
GO = (CYAN, CYAN_HI, CYAN_LO, GO_INK)
DARK = (PANEL, PANEL_HI, LINE, TEXT)
DARK_CYAN = (PANEL, PANEL_HI, CYAN_LO, CYAN)
OFF = (CARD, CARD, PANEL_HI, "#5f666e")


def look(fill):
    """기본 단추 바탕 -> BW 알약 빛깔."""
    f = (fill or "").lower()
    if f == U.ACCENT.lower():
        return GO
    if f in (U.BG3.lower(), U.BG2.lower(), U.BG.lower(), U.INK.lower(), PANEL.lower()):
        return DARK
    if f == U.ACCENT_DARK.lower():
        return DARK_CYAN
    if f in (U.RED.lower(), U.DANGER_BG.lower()):
        return K.KINDS["red"]
    if not W._is_hex(fill):
        return DARK
    return K.look_of(fill)


def pill(cv, x1, y1, x2, y2, body, line, glow=None, down=False, width=1):
    """시안의 알약: 둥근 끝 · 가는 테. glow 를 주면 둘레에 번지는 빛 (고른 것 · 올린 것). 몸 도형 id."""
    d = 1 if down else 0
    r = (y2 - y1) // 2
    if glow:
        K.rrect(cv, x1 - 2, y1 - 2 + d, x2 + 2, y2 + 2 + d, r + 2, fill=glow)
    return K.rrect(cv, x1, y1 + d, x2, y2 + d, r, fill=body, outline=line, width=width)


class PushButton(W.PushButton):
    """U.PushButton 자리에 들어가는 BW 알약 단추 (쓰는 말은 기본 단추와 같다)."""

    def draw(self):
        cv = self.holder
        try:
            cv.delete("all")
            w = cv.winfo_width() if cv.winfo_width() > 1 else int(cv["width"])
            h = cv.winfo_height() if cv.winfo_height() > 1 else self.h
        except tk.TclError:
            return
        body, hi, line, ink = OFF if not self.enabled else look(self.fill)
        hov = self._in and self.enabled
        pill(cv, 3, 3, w - 3, h - 3, hi if hov else body, CYAN if (hov and body == PANEL) else line,
             down=self._down)
        d = 1 if self._down else 0
        cv.create_text(w // 2, h // 2 + d, text=self.text, fill=ink, font=self.spec, anchor="center")


class Segmented(W._BaseSegmented):
    """고르기 단추 줄 (시안 .seg) - 고른 칸은 하늘빛 글씨 · 옅은 하늘빛 바탕, 나머지는 흐린 글씨."""

    def __init__(self, parent, items, current, on_pick):
        W._BaseSegmented.__init__(self, parent, items, current, on_pick)
        try:
            self.frame.configure(bg=LINE, highlightbackground=LINE)
        except tk.TclError:
            pass

    def _paint(self):
        for key in self.cells:
            on = key == self.current
            self._look(key, SEL if on else CARD, CYAN if on else DIMT, cursor="" if on else "hand2")

    def _hover(self, key, inside):
        if key != self.current:
            self._look(key, PANEL_HI if inside else CARD, TEXT if inside else DIMT)


def install(root, style):
    """처음 한 번: DP 의 위젯 옮기기를 BW 빛깔로 건다. 창마다: ttk 빛깔."""
    global _done
    if not _done:
        _done = True
        W.BG_MAP.clear()
        W.BG_MAP.update(BG_MAP)
        W.FG_MAP.clear()
        W.FG_MAP.update(FG_MAP)
        W.bg = bg
        W.fg = fg
        W.install(root, style)
        U.PushButton = PushButton
        U.Segmented = Segmented
        from . import _fixes
        _fixes.apply()
    try:
        style.configure(".", background=BG, foreground=TEXT, font=font(11))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=font(11))
        style.configure("TEntry", fieldbackground="#101215", foreground=TEXT, insertcolor=TEXT)
        style.map("TEntry", fieldbackground=[("focus", "#101215")])
        style.configure("TScrollbar", background=LINE_HI, troughcolor=CARD, arrowcolor=DIMT)
        style.map("TScrollbar", background=[("active", mix(LINE_HI, TEXT, 0.2))])
        style.configure("TNotebook", background=BG, bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.configure("TNotebook.Tab", background=CARD, foreground=DIMT, font=font(11),
                        bordercolor=BG, darkcolor=BG)
        style.map("TNotebook.Tab", background=[("selected", PANEL), ("active", PANEL_HI)],
                  foreground=[("selected", CYAN), ("active", TEXT)],
                  lightcolor=[("selected", PANEL), ("", CARD)])
    except tk.TclError:
        pass

