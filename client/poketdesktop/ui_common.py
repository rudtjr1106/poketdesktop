# -*- coding: utf-8 -*-
"""창들이 같이 쓰는 것들 — 색, 글꼴, 비동기 호출 헬퍼."""
import threading
import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------- 색
BG = "#15151b"
BG2 = "#1d1d25"
BG3 = "#262631"
BG4 = "#32323f"
LINE = "#33333f"
FG = "#ececf2"
FG_DIM = "#9494a6"
FG_FAINT = "#6b6b7d"
ACCENT = "#ffb02e"
ACCENT_DARK = "#2a1f08"
DANGER = "#ff6b6b"
GOOD = "#5fd97a"
SHINY = "#ffd447"
INFO = "#6fb3ff"

TIP_BG = "#0e0e13"
TIP_FG = "#f2f2f7"
TIP_SHINY = SHINY

# ---------------------------------------------------------------- 글꼴
# Noto Sans KR 이 있으면 그걸 쓰고, 없으면 시스템 기본으로 내려간다.
_FAMILY_CANDIDATES = [
    "Noto Sans KR", "Pretendard", "SUIT", "IBM Plex Sans KR",
    "나눔고딕", "맑은 고딕", "Malgun Gothic", "TkDefaultFont",
]
_LIGHT_CANDIDATES = ["Noto Sans KR DemiLight", "Noto Sans KR Light",
                     "Pretendard Light", "맑은 고딕 Semilight"]
_MEDIUM_CANDIDATES = ["Noto Sans KR Medium", "Pretendard Medium"]

FAMILY = "맑은 고딕"
FAMILY_LIGHT = FAMILY
FAMILY_MEDIUM = FAMILY

FONT = (FAMILY, 10)
FONT_B = (FAMILY, 10, "bold")
FONT_S = (FAMILY, 9)
FONT_XS = (FAMILY, 8)
FONT_T = (FAMILY, 16, "bold")
FONT_H = (FAMILY, 12, "bold")
FONT_TIP = (FAMILY, 9)
FONT_NUM = (FAMILY, 11, "bold")


def init_fonts(root):
    """설치된 글꼴 중 가장 예쁜 것을 골라 전역 글꼴을 정한다."""
    global FAMILY, FAMILY_LIGHT, FAMILY_MEDIUM
    global FONT, FONT_B, FONT_S, FONT_XS, FONT_T, FONT_H, FONT_TIP, FONT_NUM
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

    FONT = (FAMILY, 10)
    FONT_B = (FAMILY_MEDIUM, 10) if FAMILY_MEDIUM != FAMILY else (FAMILY, 10, "bold")
    FONT_S = (FAMILY, 9)
    FONT_XS = (FAMILY_LIGHT, 8)
    FONT_T = (FAMILY, 17, "bold")
    FONT_H = (FAMILY, 12, "bold")
    FONT_TIP = (FAMILY, 9)
    FONT_NUM = (FAMILY, 11, "bold")

    # 기본 위젯 글꼴까지 바꿔둔다 (메뉴, 대화상자 등)
    try:
        import tkinter.font as tkfont
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont",
                     "TkHeadingFont", "TkTooltipFont"):
            f = tkfont.nametofont(name, root)
            f.configure(family=FAMILY, size=10)
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
    s.configure("Card.TFrame", background=BG2)
    s.configure("Line.TFrame", background=LINE)
    s.configure("TLabel", background=BG, foreground=FG, font=FONT)
    s.configure("Card.TLabel", background=BG2, foreground=FG, font=FONT)
    s.configure("Dim.TLabel", background=BG, foreground=FG_DIM, font=FONT_S)
    s.configure("Faint.TLabel", background=BG, foreground=FG_FAINT, font=FONT_XS)
    s.configure("Title.TLabel", background=BG, foreground=FG, font=FONT_T)
    s.configure("Head.TLabel", background=BG, foreground=FG, font=FONT_H)

    s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
    s.configure("TNotebook.Tab", background=BG, foreground=FG_DIM,
                padding=(18, 9), font=FONT, borderwidth=0)
    s.map("TNotebook.Tab", background=[("selected", BG2)],
          foreground=[("selected", ACCENT)])

    s.configure("TEntry", fieldbackground=BG3, foreground=FG, insertcolor=ACCENT,
                borderwidth=0, padding=8, relief="flat")
    s.map("TEntry", fieldbackground=[("focus", BG4)])

    s.configure("TButton", background=BG3, foreground=FG, borderwidth=0,
                padding=(14, 8), font=FONT, relief="flat")
    s.map("TButton", background=[("active", BG4), ("disabled", BG2)],
          foreground=[("disabled", FG_FAINT)])
    s.configure("Accent.TButton", background=ACCENT, foreground=ACCENT_DARK,
                font=FONT_B, padding=(14, 9))
    s.map("Accent.TButton", background=[("active", "#ffc356"),
                                        ("disabled", "#6a5220")])
    s.configure("Ghost.TButton", background=BG2, foreground=FG_DIM)
    s.map("Ghost.TButton", background=[("active", BG3)])
    s.configure("Danger.TButton", background="#3a2028", foreground=DANGER)
    s.map("Danger.TButton", background=[("active", "#552e39")])

    s.configure("Treeview", background=BG2, fieldbackground=BG2, foreground=FG,
                borderwidth=0, rowheight=27, font=FONT_S)
    s.configure("Treeview.Heading", background=BG3, foreground=FG_DIM,
                borderwidth=0, font=FONT_XS, padding=(4, 6))
    s.map("Treeview.Heading", background=[("active", BG4)])
    s.map("Treeview", background=[("selected", "#3b3b58")],
          foreground=[("selected", FG)])

    s.configure("TScrollbar", background=BG3, troughcolor=BG, borderwidth=0,
                arrowcolor=FG_DIM)
    s.map("TScrollbar", background=[("active", BG4)])
    s.configure("TRadiobutton", background=BG, foreground=FG, font=FONT_S)
    s.map("TRadiobutton", background=[("active", BG)])
    s.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=BG3,
                borderwidth=0)
    return s


def run_async(root, fn, on_done):
    """네트워크 호출을 딴 스레드로 돌리고 결과를 tk 스레드로 되돌린다.

    on_done(result, error) 형태로 부른다. 창이 멈추지 않게 하려는 것.
    """
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
    return {"M": INFO, "F": "#ff8fb1"}.get(g, FG_DIM)
