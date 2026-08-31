# -*- coding: utf-8 -*-
"""창들이 같이 쓰는 것 — 색, 글꼴, 조각 위젯, 비동기 호출.

생김새는 '각진 게임 창' 이다. 둥근 모서리와 그림자 blur 는 쓰지 않는다.
tkinter 가 그대로 그릴 수 있는 것만 쓰기 위해서다.

    테두리      2px 단색 (highlightthickness)
    버튼        아래로 눌린 사각 그림자 (사각형 두 장)
    라벨        왼쪽에 금색 3px 막대
    강조        몬스터볼 빨강은 머리띠와 위험한 동작에만
"""
import threading
import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------- 색
INK = "#0d1017"          # 가장 어두운 바닥 (입력칸, 액자 안)
BG = "#131722"           # 창 바탕
BG2 = "#1b2030"          # 패널
BG3 = "#262d42"          # 올라온 요소 (보조 버튼)
BG4 = "#323b56"          # 눌림/호버
LINE = "#2a3147"         # 약한 경계
LINE2 = "#39415e"        # 진한 경계 (창 테두리)

FG = "#f2f4fb"
FG_DIM = "#8e97b3"
FG_FAINT = "#6f7794"

RED = "#e8483f"          # 몬스터볼 빨강
RED_DARK = "#c93a32"
RED_SHADOW = "#6e211c"
ACCENT = "#ffc043"       # 금색 (주 버튼, 라벨 마커)
ACCENT_DARK = "#2a1f08"
ACCENT_SHADOW = "#7a5410"
ACCENT_SOFT = "#241a08"  # 선택된 카드 바탕
ACCENT_TEXT = "#ffe6b8"

DANGER = "#ff6b6b"
DANGER_BG = "#2a1a1e"
DANGER_LINE = "#5a2f3a"
GOOD = "#5fd97a"
SHINY = "#ffd447"
INFO = "#6fb3ff"
PINK = "#ff8fb1"

TIP_BG = "#0e1219"
TIP_FG = "#f2f4fb"
TIP_SHINY = SHINY

# ---------------------------------------------------------------- 글꼴
_FAMILY_CANDIDATES = ["Noto Sans KR", "Pretendard", "SUIT", "IBM Plex Sans KR",
                      "나눔고딕", "맑은 고딕", "Malgun Gothic", "TkDefaultFont"]
_LIGHT_CANDIDATES = ["Noto Sans KR DemiLight", "Noto Sans KR Light",
                     "맑은 고딕 Semilight"]
_BLACK_CANDIDATES = ["Noto Sans KR Black", "Black Han Sans"]
_MEDIUM_CANDIDATES = ["Noto Sans KR Medium", "Pretendard Medium"]

FAMILY = "맑은 고딕"
FAMILY_LIGHT = FAMILY
FAMILY_MEDIUM = FAMILY
FAMILY_BLACK = FAMILY

FONT = (FAMILY, 10)
FONT_B = (FAMILY, 10, "bold")
FONT_S = (FAMILY, 9)
FONT_XS = (FAMILY, 8)
FONT_T = (FAMILY, 18, "bold")
FONT_H = (FAMILY, 12, "bold")
FONT_TIP = (FAMILY, 9)
FONT_NUM = (FAMILY, 11, "bold")
FONT_BTN = (FAMILY, 11, "bold")
FONT_LABEL = (FAMILY, 8)


def init_fonts(root):
    """설치된 글꼴 중 가장 나은 것을 골라 전역 글꼴을 정한다."""
    global FAMILY, FAMILY_LIGHT, FAMILY_MEDIUM, FAMILY_BLACK
    global FONT, FONT_B, FONT_S, FONT_XS, FONT_T, FONT_H
    global FONT_TIP, FONT_NUM, FONT_BTN, FONT_LABEL
    try:
        import tkinter.font as tkfont
        have = set(tkfont.families(root))
    except Exception:
        have = set()

    def pick(cands, default):
        for c in cands:
            if c in have:
                return c
        return default

    FAMILY = pick(_FAMILY_CANDIDATES, "맑은 고딕")
    FAMILY_LIGHT = pick(_LIGHT_CANDIDATES, FAMILY)
    FAMILY_MEDIUM = pick(_MEDIUM_CANDIDATES, FAMILY)
    FAMILY_BLACK = pick(_BLACK_CANDIDATES, FAMILY)

    FONT = (FAMILY, 10)
    FONT_B = (FAMILY_MEDIUM, 10) if FAMILY_MEDIUM != FAMILY else (FAMILY, 10, "bold")
    FONT_S = (FAMILY, 9)
    FONT_XS = (FAMILY_LIGHT, 8)
    FONT_LABEL = (FAMILY, 8)
    FONT_T = (FAMILY_BLACK, 18) if FAMILY_BLACK != FAMILY else (FAMILY, 18, "bold")
    FONT_H = (FAMILY, 13, "bold")
    FONT_TIP = (FAMILY, 9)
    FONT_NUM = (FAMILY, 11, "bold")
    FONT_BTN = (FAMILY_BLACK, 11) if FAMILY_BLACK != FAMILY else (FAMILY, 11, "bold")

    try:
        import tkinter.font as tkfont
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont",
                     "TkHeadingFont", "TkTooltipFont"):
            tkfont.nametofont(name, root).configure(family=FAMILY, size=10)
    except Exception:
        pass
    return FAMILY


TYPE_COLOR = {
    "NORMAL": "#9099a1", "FIRE": "#ff9d55", "WATER": "#5090d6", "ELECTRIC": "#f4d23c",
    "GRASS": "#63bc5a", "ICE": "#73cec0", "FIGHTING": "#ce4069", "POISON": "#aa6bc8",
    "GROUND": "#d97845", "FLYING": "#8fa9de", "PSYCHIC": "#fa7179", "BUG": "#90c12c",
    "ROCK": "#c5b78c", "GHOST": "#5269ac", "DRAGON": "#0b6dc3", "DARK": "#5a5465",
    "STEEL": "#5a8ea1", "FAIRY": "#ec8fe6", "UNKNOWN": "#68a090", "SHADOW": "#4a4a60",
}


# ---------------------------------------------------------------- 조각 위젯
def framed(parent, bg=BG2, border=LINE, bw=2, **kw):
    """각진 테두리를 두른 프레임."""
    return tk.Frame(parent, bg=bg, highlightthickness=bw,
                    highlightbackground=border, highlightcolor=border, bd=0, **kw)


def marker_label(parent, text, bg=None, color=FG_DIM, mark=ACCENT):
    """왼쪽에 금색 막대가 붙은 작은 라벨."""
    bg = bg or parent["bg"]
    row = tk.Frame(parent, bg=bg)
    tk.Frame(row, bg=mark, width=3, height=11).pack(side="left")
    tk.Label(row, text=text, bg=bg, fg=color, font=FONT_LABEL).pack(side="left", padx=(6, 0))
    return row


def chip(parent, text, bg, fg="#14141a", font=None, padx=6, pady=1):
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=font or FONT_XS,
                    padx=padx, pady=pady)


def type_chip(parent, name, type_id, small=True):
    return chip(parent, name, TYPE_COLOR.get(type_id, BG3),
                font=FONT_XS if small else FONT_S, padx=7 if small else 9)


class PushButton(object):
    """아래로 눌린 사각 그림자가 있는 버튼.

    tkinter 에는 그림자가 없으므로 같은 크기의 사각형을 4px 어긋나게 깔아
    같은 인상을 낸다. 누르면 그림자 쪽으로 살짝 내려앉는다.
    """

    def __init__(self, parent, text, command=None, fill=ACCENT, fg=ACCENT_DARK,
                 shadow=ACCENT_SHADOW, hover=None, height=40, font=None,
                 border=INK, bw=2):
        self.command = command
        self.fill = fill
        self._fg = fg
        self.hover = hover or _lighten(fill)
        bg = parent["bg"]
        self.holder = tk.Frame(parent, bg=bg, height=height + 4)
        self.holder.pack_propagate(False)
        self.shadow = tk.Frame(self.holder, bg=shadow)
        self.shadow.place(x=4, y=4, relwidth=1.0, relheight=1.0, width=-4, height=-4)
        self.box = tk.Frame(self.holder, bg=fill, highlightthickness=bw,
                            highlightbackground=border, highlightcolor=border, bd=0)
        self.box.place(x=0, y=0, relwidth=1.0, relheight=1.0, width=-4, height=-4)
        self.label = tk.Label(self.box, text=text, bg=fill, fg=fg,
                              font=font or FONT_BTN, cursor="hand2")
        self.label.pack(expand=True)
        # pack_propagate 를 꺼놔서 폭을 직접 정해줘야 한다.
        # fill="x" 로 담으면 이 값은 덮어써지고, side="left" 로 담으면 이게 쓰인다.
        self.label.update_idletasks()
        self.holder.configure(width=max(72, self.label.winfo_reqwidth() + 34))
        for w in (self.box, self.label):
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.bind("<Button-1>", self._press)
            w.bind("<ButtonRelease-1>", self._release)
        self.enabled = True

    def pack(self, **kw):
        self.holder.pack(**kw)
        return self

    def grid(self, **kw):
        self.holder.grid(**kw)
        return self

    def configure(self, text=None, state=None):
        if text is not None:
            self.label.configure(text=text)
            self.label.update_idletasks()
            self.holder.configure(width=max(72, self.label.winfo_reqwidth() + 34))
        if state is not None:
            self.enabled = (state == "normal")
            self.label.configure(fg=self._fg if self.enabled else "#6a6a80",
                                 cursor="hand2" if self.enabled else "")

    def _enter(self, _e):
        if self.enabled:
            self._paint(self.hover)

    def _leave(self, _e):
        self._paint(self.fill)
        self.box.place_configure(x=0, y=0)

    def _press(self, _e):
        if self.enabled:
            self.box.place_configure(x=3, y=3)

    def _release(self, _e):
        self.box.place_configure(x=0, y=0)
        if self.enabled and self.command:
            self.command()

    def _paint(self, c):
        self.box.configure(bg=c)
        self.label.configure(bg=c)


def ghost_button(parent, text, command=None, height=36, fg=FG, fill=BG3):
    return PushButton(parent, text, command, fill=fill, fg=fg, shadow="#171c2b",
                      hover=BG4, height=height, font=FONT_S, border=LINE2)


def danger_button(parent, text, command=None, height=36):
    return PushButton(parent, text, command, fill=RED, fg="#ffffff",
                      shadow=RED_SHADOW, hover="#f25c53", height=height,
                      font=FONT_BTN, border=INK)


def _lighten(hexcolor, amount=26):
    try:
        h = hexcolor.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return "#%02x%02x%02x" % (min(255, r + amount), min(255, g + amount),
                                  min(255, b + amount))
    except Exception:
        return hexcolor


def ball_header(parent, width, height, title, subtitle=None, tag=None):
    """몬스터볼이 반쯤 걸친 빨간 머리띠. Canvas 로 직접 그린다."""
    cv = tk.Canvas(parent, width=width, height=height, bg=RED,
                   highlightthickness=0, bd=0)
    r = int(height * 1.35)
    cx, cy = width - 26, -r // 3
    cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=RED_DARK, outline="")
    band = int(height * 0.36)
    cv.create_rectangle(width - 140, band, width + 10, band + 6, fill=BG, outline="")
    br = 17
    bx, by = width - 70, band + 3
    cv.create_oval(bx - br, by - br, bx + br, by + br, fill="#f4f6fb",
                   outline=BG, width=5)
    cv.create_text(22, 24, text=title, anchor="w", fill="#ffffff", font=FONT_T)
    if subtitle:
        cv.create_text(22, 50, text=subtitle, anchor="w", fill="#ffd9d5", font=FONT_S)
    if tag:
        cv.create_text(22, height - 14, text=tag, anchor="w", fill="#ffb9b3",
                       font=FONT_XS)
    return cv


def dot_footer(parent, width, note=""):
    """바닥의 네 점 + 안내문."""
    bar = tk.Frame(parent, bg=INK, height=34, highlightthickness=0)
    bar.pack_propagate(False)
    inner = tk.Frame(bar, bg=INK)
    inner.pack(fill="both", expand=True, padx=20)
    for c in (RED, ACCENT, GOOD, INFO):
        tk.Frame(inner, bg=c, width=6, height=6).pack(side="left", padx=(0, 4),
                                                      pady=14)
    tk.Label(inner, text=note, bg=INK, fg="#4e566f",
             font=FONT_XS).pack(side="right", pady=10)
    return bar


def status_line(parent, text="", color=GOOD, bg=None):
    """왼쪽에 색 막대가 붙은 한 줄 상태 표시."""
    bg = bg or "#0f1420"
    box = tk.Frame(parent, bg=bg)
    bar = tk.Frame(box, bg=color, width=3)
    bar.pack(side="left", fill="y")
    lb = tk.Label(box, text=text, bg=bg, fg=FG_DIM, font=FONT_S,
                  anchor="w", justify="left", padx=10, pady=7)
    lb.pack(side="left", fill="both", expand=True)
    box._bar = bar
    box._label = lb
    return box


def set_status(box, text, color=GOOD, fg=None):
    box._bar.configure(bg=color)
    box._label.configure(text=text, fg=fg or FG_DIM)


def style_window(win, title, w=None, h=None):
    win.title(title)
    win.configure(bg=BG)
    if w and h:
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(0, (sh - h) // 3)))
    return win


def apply_theme(root):
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass
    s.configure(".", background=BG, foreground=FG, font=FONT,
                borderwidth=0, focuscolor=BG)
    s.configure("TFrame", background=BG)
    s.configure("TLabel", background=BG, foreground=FG, font=FONT)
    s.configure("TEntry", fieldbackground=INK, foreground=FG, insertcolor=ACCENT,
                borderwidth=0, padding=9, relief="flat")
    s.map("TEntry", fieldbackground=[("focus", INK)])
    s.configure("TScrollbar", background=BG3, troughcolor=INK, borderwidth=0,
                arrowcolor=FG_DIM, relief="flat")
    s.map("TScrollbar", background=[("active", BG4)])
    return s


def entry(parent, textvariable, show=None, focus_border=LINE2, width=None):
    """각진 테두리를 두른 입력칸. 포커스가 오면 테두리가 금색이 된다."""
    box = tk.Frame(parent, bg=INK, highlightthickness=2,
                   highlightbackground=LINE, highlightcolor=ACCENT, bd=0)
    e = tk.Entry(box, textvariable=textvariable, show=show, bg=INK, fg=FG,
                 insertbackground=ACCENT, relief="flat", bd=0, font=FONT,
                 highlightthickness=0, width=width or 10)
    e.pack(fill="both", expand=True, padx=10, pady=9)

    def on_in(_e):
        box.configure(highlightbackground=ACCENT)

    def on_out(_e):
        box.configure(highlightbackground=LINE)
    e.bind("<FocusIn>", on_in)
    e.bind("<FocusOut>", on_out)
    box.entry = e
    return box


# ---------------------------------------------------------------- 도구
def run_async(root, fn, on_done):
    """네트워크 호출을 딴 스레드로 돌리고 결과를 tk 스레드로 되돌린다."""
    box = {}

    def worker():
        try:
            box["r"] = fn()
        except Exception as e:                   # noqa: BLE001
            box["e"] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    def poll():
        if t.is_alive():
            root.after(60, poll)
            return
        on_done(box.get("r"), box.get("e"))

    root.after(50, poll)


def gender_mark(g):
    return {"M": "♂", "F": "♀"}.get(g, "")


def gender_color(g):
    return {"M": INFO, "F": PINK}.get(g, FG_DIM)
