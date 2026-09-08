# -*- coding: utf-8 -*-
"""창들이 같이 쓰는 것 — 색, 글꼴, 조각 위젯, 비동기 호출.

생김새는 '각진 게임 창' 이다. 둥근 모서리와 그림자 blur 는 쓰지 않는다.
tkinter 가 그대로 그릴 수 있는 것만 쓰기 위해서다.

    테두리      2px 단색 (highlightthickness)
    버튼        아래로 눌린 사각 그림자 (사각형 두 장)
    라벨        왼쪽에 금색 3px 막대
    강조        몬스터볼 빨강은 머리띠와 위험한 동작에만
"""
import sys
import threading
import tkinter as tk
from tkinter import ttk

from . import platform_os as PLAT

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
DISABLED_BG = "#2a2f3f"      # 못 누르는 버튼
DISABLED_SHADOW = "#1a1e2a"
DISABLED_FG = "#6a7183"
SHINY = "#ffd447"
INFO = "#6fb3ff"
PINK = "#ff8fb1"

TIP_BG = "#0e1219"
TIP_FG = "#f2f4fb"
TIP_SHINY = SHINY

# ---------------------------------------------------------------- 글꼴
# 이 OS 의 기본 한글 글꼴은 platform_os 가 뒤에 붙여 준다. 앞쪽은 어느
# OS 에서든 깔아 두면 더 나은 것들이라 순서를 안 바꾼다 - 윈도우에서
# 뽑히는 글꼴이 예전과 같아야 한다.
_FAMILY_CANDIDATES = (["Noto Sans KR", "Pretendard", "SUIT", "IBM Plex Sans KR",
                       "나눔고딕"]
                      + PLAT.font_candidates())
_LIGHT_CANDIDATES = ["Noto Sans KR DemiLight", "Noto Sans KR Light",
                     "맑은 고딕 Semilight"]
_BLACK_CANDIDATES = ["Noto Sans KR Black", "Black Han Sans"]
_MEDIUM_CANDIDATES = ["Noto Sans KR Medium", "Pretendard Medium"]

FAMILY = "맑은 고딕"
FAMILY_LIGHT = FAMILY
FAMILY_MEDIUM = FAMILY
FAMILY_BLACK = FAMILY

# 본문 크기. 나머지는 전부 여기서 몇 pt 위아래로만 잡는다.
#
# 맥은 한 단계 크게 간다. 같은 pt 라도 맥 글꼴이 눈에 더 작게 앉아서,
# 10pt 본문이 한글로는 확실히 작았다. 윈도우(맑은 고딕)는 지금 크기가
# 맞으므로 건드리지 않는다 - 거기서 키우면 반대로 넘친다.
BASE_PT = 12 if sys.platform == "darwin" else 10

FONT = (FAMILY, BASE_PT)
FONT_B = (FAMILY, BASE_PT, "bold")
FONT_S = (FAMILY, BASE_PT - 1)
FONT_XS = (FAMILY, BASE_PT - 2)
FONT_T = (FAMILY, BASE_PT + 8, "bold")
FONT_H = (FAMILY, BASE_PT + 2, "bold")
FONT_TIP = (FAMILY, BASE_PT - 1)
FONT_NUM = (FAMILY, BASE_PT + 1, "bold")
FONT_BTN = (FAMILY, BASE_PT + 1, "bold")
FONT_LABEL = (FAMILY, BASE_PT - 2)


def _system_family(root):
    """아무 후보도 없을 때 쓸, 이 OS 가 실제로 쓰는 글꼴 이름."""
    try:
        import tkinter.font as tkfont
        return tkfont.nametofont("TkDefaultFont", root).actual("family")
    except Exception:                                       # noqa: BLE001
        return FAMILY


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

    # 후보를 하나도 못 찾으면 Tk 이 실제로 쓰는 글꼴을 그대로 쓴다.
    # 없는 이름을 주면 Tk 은 예외 없이 조용히 대체하는데, 그러면
    # "되는 것처럼 보이지만 못생긴" 상태가 되고 알아채기 어렵다.
    FAMILY = pick(_FAMILY_CANDIDATES, _system_family(root))
    FAMILY_LIGHT = pick(_LIGHT_CANDIDATES, FAMILY)
    FAMILY_MEDIUM = pick(_MEDIUM_CANDIDATES, FAMILY)
    FAMILY_BLACK = pick(_BLACK_CANDIDATES, FAMILY)

    # 크기는 한 곳에서 정한다. 여기저기 숫자를 박아 두면 하나만 고쳐도
    # 어긋나고, 무엇보다 "전부 한 단계 키우자" 를 할 수가 없다.
    #
    # **맥에서 한 단계 키운다.** 같은 pt 라도 맥 글꼴이 눈에 더 작게
    # 앉는다. 본문 10pt 는 한글로는 확실히 작았다.
    b = BASE_PT
    FONT = (FAMILY, b)
    FONT_B = ((FAMILY_MEDIUM, b) if FAMILY_MEDIUM != FAMILY
              else (FAMILY, b, "bold"))
    FONT_S = (FAMILY, b - 1)
    FONT_XS = (FAMILY_LIGHT, b - 2)
    FONT_LABEL = (FAMILY, b - 2)
    FONT_T = ((FAMILY_BLACK, b + 8) if FAMILY_BLACK != FAMILY
              else (FAMILY, b + 8, "bold"))
    FONT_H = (FAMILY, b + 3, "bold")
    FONT_TIP = (FAMILY, b - 1)
    FONT_NUM = (FAMILY, b + 1, "bold")
    FONT_BTN = ((FAMILY_BLACK, b + 1) if FAMILY_BLACK != FAMILY
                else (FAMILY, b + 1, "bold"))

    try:
        import tkinter.font as tkfont
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont",
                     "TkHeadingFont", "TkTooltipFont"):
            tkfont.nametofont(name, root).configure(family=FAMILY, size=b)
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
    tk.Frame(row, bg=mark, width=3, height=h(11)).pack(side="left")
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
        self._shadow = shadow
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
            # 글자만 흐리게 하면 금색 바탕이 그대로라 켜진 것처럼 보인다.
            # 못 누르는 버튼은 바탕과 그림자까지 죽여야 눈에 구분된다.
            if self.enabled:
                self.box.configure(bg=self.fill)
                self.shadow.configure(bg=self._shadow)
                self.label.configure(bg=self.fill, fg=self._fg, cursor="hand2")
            else:
                self.box.configure(bg=DISABLED_BG)
                self.shadow.configure(bg=DISABLED_SHADOW)
                self.label.configure(bg=DISABLED_BG, fg=DISABLED_FG, cursor="")

    def _enter(self, _e):
        if self.enabled:
            self._paint(self.hover)

    def _leave(self, _e):
        if not self.enabled:
            return
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
    bar = tk.Frame(parent, bg=INK, height=h(34), highlightthickness=0)
    bar.pack_propagate(False)
    inner = tk.Frame(bar, bg=INK)
    inner.pack(fill="both", expand=True, padx=20)
    for c in (RED, ACCENT, GOOD, INFO):
        tk.Frame(inner, bg=c, width=6, height=h(6)).pack(side="left", padx=(0, 4),
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


_icon_photo = None


def window_icon(win):
    """창(작업표시줄)에 프로그램 아이콘을 붙인다.

    tk 는 이미지를 참조하지 않으면 지워버리므로 한 장을 만들어 두고
    모든 창이 같이 쓴다.
    """
    global _icon_photo
    try:
        from PIL import ImageTk
        from . import appicon
        if _icon_photo is None:
            _icon_photo = ImageTk.PhotoImage(appicon.make(64))
        win.iconphoto(False, _icon_photo)
    except Exception:                                   # noqa: BLE001
        pass


def style_window(win, title, w=None, h=None):
    win.title(title)
    win.configure(bg=BG)
    window_icon(win)
    if w and h:
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(0, (sh - h) // 3)))
    return win


def panel(parent, root, title, w=None, h=None,
          minw=None, minh=None, on_close=None):
    """창 하나, 또는 탭 안의 한 칸을 만들어 준다.

    parent 가 없으면 지금까지처럼 **창**을 띄운다.
    parent 가 있으면 그 안에 **Frame** 을 만든다 (탭 하나로 쓰인다).

    창에만 있는 것 - 제목, 크기, 닫기 단추, 최소 크기 - 은 창일 때만 부른다.
    Frame 에는 title() 도 protocol() 도 없어서 그냥 부르면 AttributeError 로
    즉사한다. 여섯 창이 전부 같은 네 가지에 걸려 있어서 여기 한 군데로 모았다.

    돌려주는 위젯에 `embedded` 를 붙여 둔다. 부르는 쪽에서 창일 때만 해야
    하는 일(띄우기, 포커스 주기)을 가려낼 때 쓴다.
    """
    if parent is None:
        win = tk.Toplevel(root)
        style_window(win, title, w, h)
        apply_theme(win)
        if minw and minh:
            win.minsize(minw, minh)
        if on_close:
            win.protocol("WM_DELETE_WINDOW", on_close)
        win.embedded = False
        return win
    f = tk.Frame(parent, bg=BG)
    f.embedded = True
    return f


def is_embedded(w):
    """이 위젯이 탭 안에 들어 있나. 창이면 False."""
    return bool(getattr(w, "embedded", False))


def install_wheel(top):
    """이 창의 휠을 **한 군데서** 받아서 알맞은 목록으로 보낸다.

    예전에는 창마다 제각각이었다. 어떤 창은 bind_all 로 걸고(창 전체를
    가로챈다), 어떤 창은 자기 창에 걸었다. 문제가 둘이었다:

      1. 닫을 때 부르던 unbind_all 이 **다른 창의 휠까지 통째로 지웠다.**
         포켓몬 관리 창을 열었다 닫으면 도감의 휠이 죽었다.
      2. 창에 건 바인딩은 탭(Frame) 안에서는 오지 않는다. tk 는 이벤트를
         위젯 -> 클래스 -> 창 -> all 순으로만 올려보내는데, 중간 Frame 은
         그 길에 없다. 그래서 탭으로 합치면 가방·상점 휠이 조용히 멎는다.

    그래서 창 하나에 하나만 건다. 목록 쪽은 캔버스에 `wheel_div` 만 붙여
    두면 된다 - 굴릴 게 없으면 굴리지 않는 것도 여기서 한 번에 처리한다.

    **한 칸이 얼마로 오는지는 OS 마다 다르다.** wheel_units 를 보라.
    """
    def on_wheel(e):
        try:
            w = top.winfo_containing(e.x_root, e.y_root)
        except Exception:                                   # noqa: BLE001
            return None
        while w is not None:
            div = getattr(w, "wheel_div", 0)
            if div:
                try:
                    lo, hi = w.yview()
                    if (hi - lo) < 0.999:      # 다 보이면 굴릴 게 없다
                        w.yview_scroll(wheel_units(e.delta, div), "units")
                    after = getattr(w, "wheel_after", None)
                    if after:
                        after()
                except Exception:                           # noqa: BLE001
                    pass
                return "break"
            w = getattr(w, "master", None)
        return None
    top.bind("<MouseWheel>", on_wheel)


def wheel_units(delta, div):
    """휠 이벤트 하나가 몇 줄인가.

    **한 칸이 얼마로 오는지가 OS 마다 다르다.** 윈도우는 120 으로 오는데,
    맥은 1~3 정도로 온다. 예전 코드는 `int(-delta / 60)` 이라 맥에서는
    몫이 0 이 되어 **휠이 아예 안 먹었다.** 화면은 멀쩡해 보이는데 굴러가지만
    않아서, 스크롤바를 손으로 끌기 전까지는 목록이 다인 줄 안다.

    그래서 먼저 '몇 칸인가' 로 바꾼 다음에 div 를 적용한다. 120 언저리로
    오면 윈도우 관례로 보고 나누고, 작게 오면 그대로 칸수로 친다.
    div 는 예전 그대로라 윈도우에서 굴러가는 정도가 안 바뀐다
    (120 / 60 = 2줄).

    트랙패드는 한 번에 잘게 여러 번 오는데, 그때도 **최소 한 줄은
    움직인다.** 0 으로 깎여서 아무 일도 안 일어나느니 조금 빠른 편이 낫다.
    """
    try:
        d = float(delta)
    except (TypeError, ValueError):
        return 0
    if d == 0:
        return 0
    notches = d / 120.0 if abs(d) >= 30 else d
    units = -notches * (120.0 / max(1, div))
    n = int(units)
    if n == 0:                       # 깎여서 0 이 되면 한 줄이라도 움직인다
        n = 1 if units > 0 else -1
    return n


def h(px):
    """글자가 든 칸의 높이. 글꼴이 커지면 같이 커진다.

    막대(bar)와 줄(row) 높이를 픽셀로 박아 두면, 글꼴을 한 단계만 키워도
    글이 세로로 눌린다. 맥에서 본문을 10 -> 12pt 로 올렸더니 헤더와 줄
    마흔 곳이 2~6px 씩 모자랐다.

    **글자를 줄여서 맞추지 않는다.** 칸을 늘린다. 그것이 이 함수다.

    도트나 능력치 막대처럼 글자가 없는 것에는 쓰지 마라 - 그건 커지면
    안 되고, 커지면 오히려 그림이 흐려진다.
    """
    return int(round(px * (BASE_PT / 10.0)))


def wrap_to_width(label, pad=0):
    """라벨이 **자기 실제 폭**에 맞춰 줄을 접게 한다.

    wraplength 를 상수로 박아 두면 안 맞는다. 창 크기, 글꼴, 스크롤바가
    붙었는지에 따라 실제 폭이 달라지기 때문이다. 실제로 상점 상세에서
    라벨 폭이 271인데 286에서 접고 있어서 **매 줄 18px 이 잘려 나갔다** -
    스크롤바를 나중에 붙이면서 상수를 안 고친 탓이었다.

    그려진 뒤에 <Configure> 로 다시 잡으므로 창을 늘였다 줄여도 맞는다.
    """
    def fit(e):
        w = e.width - pad
        if w > 40 and int(label.cget("wraplength")) != w:
            label.configure(wraplength=w)
    label.bind("<Configure>", fit)
    return label


def scrollable(canvas, div=60, after=None):
    """이 캔버스를 휠로 굴릴 수 있다고 표시한다. install_wheel 이 찾아 쓴다."""
    canvas.wheel_div = div
    if after:
        canvas.wheel_after = after
    return canvas


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

    # 허브 창의 탭. 여기서 안 정하면 clam 테마의 회색 탭에 회색 글씨가
    # 그대로 나와서 어느 탭에 있는지도, 무슨 탭인지도 안 읽혔다.
    # 고른 탭은 창 바탕색으로 이어 붙이고 글씨를 금색으로, 나머지는
    # 어두운 띠에 흐린 글씨로 두어 서로 확실히 갈린다.
    # clam 은 탭과 판 둘레에 밝은 회색 선을 그린다(bordercolor·lightcolor·
    # darkcolor). borderwidth=0 으로는 안 지워져서 색을 바탕색에 맞춘다.
    s.configure("TNotebook", background=BG, borderwidth=0,
                bordercolor=BG, lightcolor=BG, darkcolor=BG,
                tabmargins=[6, 6, 6, 0])
    s.configure("TNotebook.Tab", background=BG3, foreground=FG_DIM,
                padding=[12, 7], borderwidth=0, font=FONT,
                bordercolor=BG, darkcolor=BG)
    s.map("TNotebook.Tab",
          background=[("selected", BG), ("active", BG4)],
          foreground=[("selected", ACCENT), ("active", FG)],
          lightcolor=[("selected", BG), ("", BG3)],
          # clam 은 고른 탭만 padding 을 '6 4 6 2' 로 바꿔 다른 크기로
          # 그린다 (style map 은 덮어쓰지 않고 합쳐져서 그 항목이 남는다).
          # 그대로 두면 고른 탭이 좁고 낮아져 누를 때마다 줄이 흔들린다.
          # 전부 같은 값으로 못 박는다.
          padding=[("selected", [12, 7])])
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
        try:
            on_done(box.get("r"), box.get("e"))
        except tk.TclError as e:
            # 답이 오기 전에 창을 닫으면, 그리려던 위젯이 이미 없다.
            # ("invalid command name ...") 고칠 것이 없는 상황이라 조용히
            # 넘긴다 - 다만 무엇이었는지는 남긴다. 탭으로 합치면서 여섯
            # 화면이 한꺼번에 닫히다 보니 더 자주 만난다.
            from . import config
            config.log("창이 닫힌 뒤 도착한 응답을 버립니다: %s" % e)

    root.after(50, poll)


def gender_mark(g):
    return {"M": "♂", "F": "♀"}.get(g, "")


def gender_color(g):
    return {"M": INFO, "F": PINK}.get(g, FG_DIM)


# ---------------------------------------------------------------- 뜨는 메뉴
class PopupMenu(object):
    """tkinter 로 직접 그리는 메뉴.

    맥에서는 `tk.Menu` 를 쓸 수 없다. aqua 에서 그것은 NSMenu 이고, NSMenu 가
    열리면 macOS 가 중첩 런루프를 돌리는데 그 동안 Tk 의 `after` 타이머가
    발화하면서 파이썬이 통째로 죽는다(GIL 오류). 이 게임은 도트를 움직이려고
    `after` 를 쉬지 않고 도니 메뉴를 여는 순간이 곧 마지막이다.

    그래서 창으로 직접 그린다. 생김새는 이 게임의 다른 창과 같다.

    rows 는 이렇게 준다. None 은 구분선이다.

        [None,
         {"text": "정보 보기", "command": fn},
         {"text": "이름표 보이기", "command": fn, "checked": True},
         {"text": "버전 1.0.8", "enabled": False},
         {"text": "바로 가기", "header": True},
         {"text": "가방", "command": fn, "indent": 1}]
    """

    W = 250
    _open = []          # 지금 떠 있는 것들. 새로 열 때 먼저 닫는다.

    def __init__(self, root, rows, x, y, width=None, anchor="nw"):
        self.root = root
        self.win = self.catcher = None
        self.width = width or self.W
        self._watch_job = None
        self._was_down = PLAT.mouse_buttons_down()
        close_all()
        self._build(rows)
        self._place(x, y, anchor)
        PopupMenu._open.append(self)
        self._watch()

    # ---------------- 만들기 ----------------
    def _build(self, rows):
        cat = tk.Toplevel(self.root)
        cat.overrideredirect(True)
        # 바깥을 누르면 닫히게 화면을 덮는다. 거의 안 보이지만 클릭은 받는다.
        cat.attributes("-alpha", 0.01)
        cat.configure(bg="#000000")
        # **모니터 전체를 덮는다.** 주 화면만 덮으면 다른 모니터를 눌렀을
        # 때 메뉴가 안 닫힌다.
        bx1, by1, bx2, by2 = all_screens(self.root)
        cat.geometry("%dx%d+%d+%d" % (bx2 - bx1, by2 - by1, bx1, by1))
        cat.bind("<Button-1>", lambda e: self.close())
        for seq in ("<Button-2>", "<Button-3>"):
            cat.bind(seq, lambda e: self.close())
        cat.attributes("-topmost", True)
        self.catcher = cat

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg=BG2, highlightthickness=1, highlightbackground=LINE2)
        win.bind("<Escape>", lambda e: self.close())
        self.win = win

        body = tk.Frame(win, bg=BG2)
        body.pack(fill="both", expand=True, padx=1, pady=6)
        for row in rows:
            if row is None:
                tk.Frame(body, bg=LINE, height=h(1)).pack(fill="x", padx=8, pady=4)
                continue
            self._row(body, row)

    def _row(self, body, row):
        text = row.get("text", "")
        indent = row.get("indent", 0)
        if row.get("header"):
            tk.Label(body, text=text, bg=BG2, fg=FG_FAINT, anchor="w",
                     font=(FAMILY, 8), bd=0, highlightthickness=0,
                     width=1).pack(fill="x", padx=10 + indent * 12,
                                   pady=(4, 0))
            return
        enabled = row.get("enabled", True) and row.get("command") is not None
        checked = row.get("checked")
        mark = "" if checked is None else ("✓ " if checked else "    ")
        lab = tk.Label(body, text=mark + text, bg=BG2, anchor="w",
                       fg=FG if row.get("enabled", True) else DISABLED_FG,
                       font=(FAMILY, 10, "bold") if row.get("bold")
                       else (FAMILY, 10),
                       bd=0, highlightthickness=0, width=1)
        lab.pack(fill="x", padx=8 + indent * 12, ipady=2)
        if not enabled:
            return
        lab.configure(cursor="pointinghand")
        lab.bind("<Enter>", lambda e, w=lab: w.configure(bg=BG4))
        lab.bind("<Leave>", lambda e, w=lab: w.configure(bg=BG2))

        def click(_e, fn=row["command"]):
            # 메뉴를 먼저 닫는다. 창이 메뉴 뒤로 들어가면 안 보인다.
            self.close()
            fn()

        lab.bind("<Button-1>", click)

    def _place(self, x, y, anchor):
        win = self.win
        win.geometry("%dx10+0+0" % (self.width + 2))   # 너비를 먼저 못박는다
        win.update_idletasks()
        w = self.width + 2
        h = win.winfo_reqheight()
        # **누른 그 화면 안에 가둔다.** 주 화면 크기로만 자르면, 모니터가
        # 두 대일 때 두 번째 화면에서 부른 메뉴가 첫 화면으로 끌려간다 -
        # 사용자 눈에는 "눌렀는데 아무 일도 안 일어난다" 로 보인다.
        sx1, sy1, sx2, sy2 = screen_at(self.root, x, y)
        if "e" in anchor:
            x -= w
        if "s" in anchor:
            y -= h
        x = max(sx1 + 4, min(int(x), sx2 - w - 4))
        y = max(sy1 + 2, min(int(y), sy2 - h - 8))
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        win.attributes("-topmost", True)
        win.lift()

    # ---------------- 닫기 ----------------
    # ---------------- 바깥을 누르면 닫는다 ----------------
    def _watch(self):
        """마우스가 메뉴 **밖에서** 눌리면 닫는다.

        화면을 덮는 catcher 만으로는 맥에서 부족했다. Tk 은 앱이 활성일
        때만 클릭을 받으므로, 다른 앱의 창을 누르면 그 클릭이 우리에게
        오지 않는다. 그래서 메뉴가 그대로 떠 있었다.

        여기서는 Tk 을 거치지 않고 **눌린 단추를 직접 물어본다**
        (NSEvent.pressedMouseButtons). 앱이 비활성이어도 답이 온다.
        우클릭을 받는 것과 같은 방식이다.

        윈도우에서는 mouse_buttons_down() 이 늘 0 이라 이 고리가 아무
        일도 안 한다 - 거기서는 catcher 가 이미 제 몫을 한다.
        """
        if self.win is None:
            return
        try:
            down = PLAT.mouse_buttons_down()
            if down and not self._was_down and not self._inside():
                return self.close()
            self._was_down = down
        except Exception:                                   # noqa: BLE001
            pass
        try:
            self._watch_job = self.root.after(60, self._watch)
        except Exception:                                   # noqa: BLE001
            self._watch_job = None

    def _inside(self):
        """마우스가 메뉴 위에 있나. 모르겠으면 True (섣불리 안 닫는다)."""
        try:
            x, y = self.root.winfo_pointerxy()
            w = self.win
            wx, wy = w.winfo_rootx(), w.winfo_rooty()
            return (wx <= x <= wx + w.winfo_width()
                    and wy <= y <= wy + w.winfo_height())
        except Exception:                                   # noqa: BLE001
            return True

    def close(self):
        if self._watch_job is not None:
            try:
                self.root.after_cancel(self._watch_job)
            except Exception:                               # noqa: BLE001
                pass
            self._watch_job = None
        for w in (self.win, self.catcher):
            try:
                if w is not None:
                    w.destroy()
            except Exception:                               # noqa: BLE001
                pass
        self.win = self.catcher = None
        try:
            PopupMenu._open.remove(self)
        except ValueError:
            pass

    def alive(self):
        return self.win is not None


def close_all():
    """떠 있는 메뉴를 전부 닫는다."""
    for m in list(PopupMenu._open):
        m.close()


def screen_at(root, x, y):
    """그 점이 있는 화면의 Tk 좌표 (x1, y1, x2, y2).

    어느 화면에도 안 들어가면 주 화면을 준다.
    """
    from . import platform_os as PLAT
    got = PLAT.screens(root.winfo_screenwidth(), root.winfo_screenheight())
    for s in got:
        if s[0] <= x < s[2] and s[1] <= y < s[3]:
            return s
    return got[0]


def all_screens(root):
    """모든 화면을 덮는 사각형."""
    from . import platform_os as PLAT
    got = PLAT.screens(root.winfo_screenwidth(), root.winfo_screenheight())
    return (min(s[0] for s in got), min(s[1] for s in got),
            max(s[2] for s in got), max(s[3] for s in got))
