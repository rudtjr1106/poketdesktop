# -*- coding: utf-8 -*-
"""DP 테마의 '위젯 빛깔' - 따로 그리지 않은 화면과 작은 창이 DP 의 밝은 빛깔을 입게 한다.

화면 하나하나는 캔버스에 따로 그린다 (bag.py, battle.py ...). 그런데 묻는 창 · 길드의 칸들처럼 위젯으로
짠 것은 기본 테마의 어두운 빛깔(ui_common 의 BG · FG ...)을 그대로 쓴다. 그 빛깔은 만들 때 박히고,
마우스를 올릴 때 다시 칠하고, 함수의 기본값에도 박혀 있어서 상수만 바꿔서는 다 못 바꾼다.

그래서 **위젯을 만들 때와 configure 할 때 빛깔 · 글꼴을 옮긴다** (tkinter 의 BaseWidget.__init__ 과
Misc.configure 를 감싼다):

    바탕 쪽 (bg · highlightbackground ...)   어둡고 빛이 옅은 것 -> 밝은 바탕 (표에 있으면 그 값)
    글자 쪽 (fg · insertbackground ...)      밝은 회색 -> 진회색, 어두운 바탕용 밝은 빛 -> 진하게
    글꼴                                       기본 글꼴 -> 갈무리11 (크기는 그대로)

옮기는 것은 **기본 화면의 코드가 만든 위젯뿐이다** - DP 화면(skins/...)이 만든 위젯은 제 빛깔 그대로 둔다
(누가 불렀는지 호출 줄을 거슬러 본다). 캔버스 위의 도형(create_* · itemconfigure)은 건드리지 않는다.
뜨는 메뉴(U.PopupMenu)가 만들고 바꾸는 위젯도 옮기지 않는다 - 메뉴는 기본 테마와 똑같이 유지한다.

단추(U.PushButton)와 고르기 단추(U.Segmented)는 DP 모양으로 바꿔 끼운다 (윗단이 밝은 볼록 단추 · 빨간 커서).
기본 테마에서는 이 파일을 아예 읽지 않는다 (skins.theme 이 테마의 widgets 를 찾을 때만).
"""
import colorsys
import sys
import tkinter as tk

from ... import ui_common as U
from . import CUR, DIM, FONT, INK, font
from . import kit as K

_installed = False

# ---------------------------------------------------------------- 빛깔 표
# 기본 테마 값 -> DP 값. 표에 없는 것은 규칙(_bg · _fg)으로 옮긴다.
BG_MAP = {
    U.INK: "#ffffff",         # 입력칸 · 액자 안
    U.BG: "#eef2f6",          # 창 바탕
    U.BG2: "#f6f8fb",         # 패널
    U.BG3: "#ffffff",         # 올라온 요소
    U.BG4: "#dbe8f6",         # 올렸을 때
    U.LINE: "#c8d0dc",
    U.LINE2: "#8a96a8",
    U.ACCENT_DARK: "#fff0cc",
    U.ACCENT_SOFT: "#fff4d8",
    U.ACCENT_SHADOW: "#d8a040",
    U.DANGER_BG: "#fde4e4",
    U.DANGER_LINE: "#e0a0a0",
    U.DISABLED_BG: "#d6d9de",
    U.DISABLED_SHADOW: "#b8bcc4",
    U.TIP_BG: "#fffbe6",
    "#161b28": "#ffffff",     # 화면들의 카드 (ui_guild_war · bond_stone ... 의 CARD) - DP 의 흰 판
}
FG_MAP = {
    U.FG: INK,
    U.FG_DIM: "#606068",
    U.FG_FAINT: DIM,
    U.ACCENT: "#c06810",
    U.ACCENT_TEXT: "#a05010",
    U.GOOD: "#2c8a3c",
    U.DANGER: "#d02828",
    U.INFO: "#2860c0",
    U.PINK: "#c83a78",
    U.SHINY: "#b88a00",
    U.RED: "#c83030",
    U.TIP_FG: INK,
    U.DISABLED_FG: "#9aa0aa",
    U.ACCENT_DARK: "#7a4a10",
}
BG_KEYS = ("bg", "background", "highlightbackground", "activebackground", "selectcolor",
           "disabledbackground", "readonlybackground", "troughcolor")
FG_KEYS = ("fg", "foreground", "highlightcolor", "insertbackground", "disabledforeground", "activeforeground")


def _rgb(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v * 255)))) for v in rgb)


def _mix(c, d, t):
    a, b = _rgb(c), _rgb(d)
    return _hex(tuple(x + (y - x) * t for x, y in zip(a, b)))


def _is_hex(c):
    return isinstance(c, str) and c.startswith("#") and len(c) in (4, 7)


def bg(c):
    """바탕 빛깔을 DP 로. 어둡고 빛이 옅은 것만 밝힌다 (빨간 단추 · 타입 빛깔은 그대로)."""
    if not _is_hex(c):
        return c
    low = c.lower()
    for k, v in BG_MAP.items():
        if k.lower() == low:
            return v
    h, s, v = colorsys.rgb_to_hsv(*_rgb(c))
    if v < 0.45 and s < 0.6:
        return _mix(c, "#ffffff", 0.88)
    return c


def fg(c):
    """글자 빛깔을 DP 로. 어두운 바탕에 맞춘 밝은 글자를 진하게."""
    if not _is_hex(c):
        return c
    low = c.lower()
    for k, v in FG_MAP.items():
        if k.lower() == low:
            return v
    h, s, v = colorsys.rgb_to_hsv(*_rgb(c))
    if v > 0.6 and s < 0.3:
        return INK if v > 0.85 else "#606068"
    if v > 0.75:
        return _mix(c, "#000000", 0.42)
    return c


_BASE_FAMILIES = set()


def _font(f):
    """기본 글꼴 -> 갈무리11 (크기는 그대로, 굵기는 뺀다 - 갈무리는 굵은 꼴이 없다)."""
    if isinstance(f, (tuple, list)) and len(f) >= 2 and f[0] in _BASE_FAMILIES:
        return (FONT, f[1]) + tuple(x for x in f[2:] if x not in ("bold", "normal"))
    return f


def _translate(opts):
    if not opts:
        return opts
    out = dict(opts)
    for k, v in opts.items():
        k2 = k.lstrip("-")
        if k2 in BG_KEYS:
            out[k] = bg(v)
        elif k2 in FG_KEYS:
            out[k] = fg(v)
        elif k2 == "font":
            out[k] = _font(v)
    return out


_SKINS = __name__.rsplit(".", 2)[0]          # poketdesktop.skins
_PKG = _SKINS.rsplit(".", 1)[0]               # poketdesktop
# 부품만 만드는 곳 - 이것들을 부른 쪽을 본다 (기본 화면이 U.chip 을 부르면 옮기고, DP 의 고르기 단추가
# U.Segmented._look 으로 칠하면 그대로 둔다)
_HELPERS = (_PKG + ".ui_common", _PKG + ".battle_zoom")


def _in_popup(f):
    """이 줄이 뜨는 메뉴(U.PopupMenu)의 메서드 안인가 - 메뉴 줄에 마우스를 올릴 때 칠하는 람다까지 포함."""
    q = getattr(f.f_code, "co_qualname", None)
    if q is not None:
        return q.startswith("PopupMenu.")
    return isinstance(f.f_locals.get("self"), U.PopupMenu)


def _from_base():
    """이 위젯을 만든(바꾼) 것이 기본 화면의 코드인가. tkinter 안쪽 · 부품 함수는 건너뛰고 첫 호출자를 본다.

    **뜨는 메뉴(트레이 · 펫 우클릭 · 볼 · 드롭다운)는 기본 모습 그대로다** (사용자 결정, 2026-10-25) -
    PopupMenu 가 만들고 바꾸는 위젯은 옮기지 않는다 (누가 메뉴를 열었든 같다).
    """
    f = sys._getframe(2)
    while f is not None:
        mod = f.f_globals.get("__name__", "")
        if mod == _PKG + ".ui_common" and _in_popup(f):
            return False
        if mod.startswith("tkinter") or mod in _HELPERS:
            f = f.f_back
            continue
        return not mod.startswith(_SKINS)
    return True


def _wrap_widgets():
    base_init = tk.BaseWidget.__init__
    base_configure = tk.Misc.configure

    def __init__(self, master, widgetName, cnf={}, kw={}, extra=()):      # noqa: B006 (tkinter 와 같은 꼴)
        if _from_base():
            cnf, kw = _translate(cnf), _translate(kw)
        return base_init(self, master, widgetName, cnf, kw, extra)

    def configure(self, cnf=None, **kw):
        if (cnf or kw) and _from_base():
            cnf = _translate(cnf) if isinstance(cnf, dict) else cnf
            kw = _translate(kw)
        return base_configure(self, cnf, **kw)

    tk.BaseWidget.__init__ = __init__
    tk.Misc.configure = configure
    tk.Misc.config = configure

    # 글 칸(Text)의 태그 빛깔 · 글꼴 (길드 채팅의 이름 · 말 줄은 태그로 칠한다)
    base_tag = tk.Text.tag_configure

    def tag_configure(self, tagName, cnf=None, **kw):
        if (cnf or kw) and _from_base():
            cnf = _translate(cnf) if isinstance(cnf, dict) else cnf
            kw = _translate(kw)
        return base_tag(self, tagName, cnf, **kw)

    tk.Text.tag_configure = tag_configure
    tk.Text.tag_config = tag_configure


# ---------------------------------------------------------------- 단추
# 기본 단추의 바탕 -> DP 단추의 빛깔 (몸, 올렸을 때, 테두리, 윗단)
KINDS = {
    U.ACCENT: K.KINDS["red"],       # 주 단추 (금색) -> 빨간 단추
    U.RED: K.KINDS["red"],
    U.BG3: K.KINDS["gray"],         # 보조 단추 (ghost)
    U.ACCENT_DARK: K.KINDS["blue"],   # 금 글씨 보조 단추 (놀러 가기 · 실시간 ...)
    U.DANGER_BG: K.KINDS["red"],
}


def _look_of(fill):
    """단추 바탕 빛깔 -> (몸, 올렸을 때, 테두리, 윗단). 표에 없으면 그 빛깔로 만든다 (메가진화의 보라 ...)."""
    if fill in KINDS:
        return KINDS[fill]
    for k, v in KINDS.items():
        if (k or "").lower() == (fill or "").lower():
            return v
    if not _is_hex(fill):
        return K.KINDS["gray"]
    return K.look_of(fill)


class PushButton(object):
    """U.PushButton 자리에 들어가는 DP 단추 (캔버스 위젯 하나). 쓰는 말은 기본 단추와 같다:
    holder · pack · grid · pack_forget · configure(text=, state=) · fill · _fg · hover · _shadow · enabled · command.
    """

    def __init__(self, parent, text, command=None, fill=U.ACCENT, fg=U.ACCENT_DARK,
                 shadow=U.ACCENT_SHADOW, hover=None, height=40, font=None, border=U.INK, bw=2):
        self.command = command
        self.fill, self._fg, self.hover, self._shadow = fill, fg, hover, shadow
        self.text = str(text)
        self.spec = _font(font) if font else globals()["font"](11)
        if self.spec and len(self.spec) >= 2 and isinstance(self.spec[1], int) and self.spec[1] < 0:
            self.spec = (self.spec[0], abs(self.spec[1]))
        self.enabled = True
        self._in = self._down = False
        self.h = int(height) + 4
        try:
            pbg = parent["bg"]
        except (tk.TclError, KeyError):
            pbg = "#eef2f6"
        self.holder = tk.Canvas(parent, bg=pbg, height=self.h, highlightthickness=0, bd=0, cursor="hand2")
        self.holder.configure(width=self._want())
        self.holder.bind("<Configure>", lambda _e: self.draw())
        self.holder.bind("<Enter>", lambda _e: self._set(True, self._down))
        self.holder.bind("<Leave>", lambda _e: self._set(False, False))
        self.holder.bind("<ButtonPress-1>", lambda _e: self._set(self._in, True))
        self.holder.bind("<ButtonRelease-1>", self._release)
        self.label = self                   # (기본 단추의 label.cget("text") 을 부르는 곳이 있다)

    def _want(self):
        # 기본 단추와 같은 규칙(글자 폭 + 34, 바닥 72). 갈무리는 기본 글꼴보다 넓다 - 둘 중 넓은 쪽으로 재서
        # 글씨는 안 잘리고, 기본 화면의 배치는 되도록 그대로 둔다.
        f = K.tkfont_of(self.holder, self.spec).measure(self.text)
        return max(72, f + 24)

    def cget(self, key):
        return {"text": self.text, "state": "normal" if self.enabled else "disabled"}.get(key)

    def _set(self, inside, down):
        self._in, self._down = inside, down and self.enabled
        self.draw()

    def _release(self, _e):
        was = self._down
        self._down = False
        self.draw()
        if was and self._in and self.enabled and self.command:
            self.command()

    def draw(self):
        cv = self.holder
        try:
            cv.delete("all")
            w = cv.winfo_width() if cv.winfo_width() > 1 else int(cv["width"])
            h = cv.winfo_height() if cv.winfo_height() > 1 else self.h
        except tk.TclError:
            return
        body, hi, line, ink = K.KINDS["off"] if not self.enabled else _look_of(self.fill)
        if self._in and self.enabled:
            body = hi
        K.button_shape(cv, 1, 1, w - 1, h - 1, body, line, down=self._down)
        d = 1 if self._down else 0
        cv.create_text(w // 2, (h - 2) // 2 + d, text=self.text, fill=ink, font=self.spec, anchor="center")

    def pack(self, **kw):
        self.holder.pack(**kw)
        return self

    def grid(self, **kw):
        self.holder.grid(**kw)
        return self

    def pack_forget(self):
        self.holder.pack_forget()

    def configure(self, text=None, state=None, **_kw):
        changed = False
        if text is not None and str(text) != self.text:
            self.text = str(text)
            try:
                self.holder.configure(width=self._want())
            except tk.TclError:
                return
            changed = True
        if state is not None:
            self.enabled = (state == "normal")
            try:
                self.holder.configure(cursor="hand2" if self.enabled else "")
            except tk.TclError:
                return
            changed = True
        if changed or state is not None:
            self.draw()

    config = configure


_BaseSegmented = U.Segmented            # (아래에서 U.Segmented 를 이것으로 바꿔 끼운다 - 원래 것을 쥐어 둔다)


class Segmented(_BaseSegmented):
    """고르기 단추 줄 - 고른 칸은 흰 바탕에 빨간 글씨, 둘레는 회청색 (DP 의 탭)."""

    def __init__(self, parent, items, current, on_pick):
        _BaseSegmented.__init__(self, parent, items, current, on_pick)
        try:
            self.frame.configure(bg="#9aa6b6", highlightbackground="#8a96a8")
        except tk.TclError:
            pass

    def _paint(self):
        for key in self.cells:
            on = key == self.current
            self._look(key, "#ffffff" if on else "#eef2f6", CUR if on else INK, cursor="" if on else "hand2")

    def _hover(self, key, inside):
        if key != self.current:
            self._look(key, "#dbe8f6" if inside else "#eef2f6", INK)


# ---------------------------------------------------------------- 걸기
def install(root, style):
    """처음 한 번: 위젯 옮기기 · 단추 바꿔 끼우기. 창마다: ttk 빛깔."""
    global _installed
    if not _installed:
        _installed = True
        _BASE_FAMILIES.update(x for x in (U.FAMILY, U.FAMILY_LIGHT, U.FAMILY_MEDIUM, U.FAMILY_BLACK) if x)
        _wrap_widgets()
        U.PushButton = PushButton
        U.Segmented = Segmented
    try:
        style.configure(".", background="#eef2f6", foreground=INK, font=font(11))
        style.configure("TFrame", background="#eef2f6")
        style.configure("TLabel", background="#eef2f6", foreground=INK, font=font(11))
        style.configure("TEntry", fieldbackground="#ffffff", foreground=INK, insertcolor=INK)
        style.map("TEntry", fieldbackground=[("focus", "#ffffff")])
        style.configure("TScrollbar", background="#b8c2d0", troughcolor="#d8dde4", arrowcolor="#606068")
        style.map("TScrollbar", background=[("active", "#8a96a8")])
        style.configure("TNotebook", background="#eef2f6", bordercolor="#eef2f6", lightcolor="#eef2f6",
                        darkcolor="#eef2f6")
        style.configure("TNotebook.Tab", background="#dfe4ea", foreground="#606068", font=font(11),
                        bordercolor="#eef2f6", darkcolor="#eef2f6")
        style.map("TNotebook.Tab", background=[("selected", "#ffffff"), ("active", "#dbe8f6")],
                  foreground=[("selected", CUR), ("active", INK)],
                  lightcolor=[("selected", "#ffffff"), ("", "#dfe4ea")])
    except tk.TclError:
        pass
