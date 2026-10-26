# -*- coding: utf-8 -*-
"""소드·실드 테마가 물려받은 DP 화면에서 빛깔 옮기기(COLORS · shade)만으로는 안 되는 곳 (이 테마일 때만, 한 번).

DP 화면 파일은 고치지 않는다 - 이 테마가 켜졌을 때 그 모듈의 이름 몇 개만 이 테마 것으로 바꿔 끼운다
(widgets.install 이 처음 한 번 부른다).

    주된 단추     DP 는 주된 일을 빨간 단추로 했다 (kit.KINDS["red"]). 그 빛깔을 분홍으로 바꿔 끼우고,
                 되돌릴 수 없는 일(놓아주기 · 삭제 · 길드 해산 · 회원탈퇴 …)만 빨간 단추로 남긴다 (DANGER).
    작은 창 머리  DP 는 옅은 하늘색 띠에 파란 이름표였다 (dialogs.dialog_bar). 남색 몸 위에서 밝은 띠만 따로 놀아
                 남색 띠 + 흰 알약 이름표 + 아래 가는 분홍 줄로 (위험한 일은 빨간 이름표 · 빨간 줄).
    캔버스 다시 그리기  U.redraw_canvas 는 '같은 바탕으로 configure' 해서 캔버스를 다시 그린다. 그런데 <Map> 에서
                 불리면 부른 쪽이 기본 화면으로 보여 dp/widgets 가 바탕을 DP 로 옮긴다 - 어두운 바탕(남색)을 밝게
                 섞어 버려 길드 목록 · 길드전 칸 같은 굴러가는 캔버스가 회색이 됐다. 같은 값을 Tcl 로 바로 넘긴다.
"""
import tkinter as tk

from ... import ui_common as U
from ..dp import font
from ..dp import kit as K
from . import MAG, NAVY, NAVY2

RED = ("#d33a3a", "#e25656", "#8e2020", "#ffffff")     # 위험한 일 (PALETTE 의 RED_BTN 과 같은 빛깔 - 옮기지 않는다)
DANGER = frozenset(("놓아주기", "삭제", "길드 해산", "길드 나가기", "회원탈퇴", "탈퇴"))

_done = False


def dialog_bar(win, title, danger=False):
    """작은 창의 머리 (DP dialogs.dialog_bar 와 같은 말 · 같은 높이): 남색 띠 · 흰 알약 이름표 · 아래 가는 분홍 줄."""
    from ..dp import dialogs as D
    s = U.h
    head = tk.Canvas(win, bg=NAVY2, height=s(D.BAR_H) + s(2), highlightthickness=0, bd=0)
    head.pack(fill="x")

    def draw(_e=None):
        try:
            ww, hh = head.winfo_width(), head.winfo_height()
            head.delete("all")
        except tk.TclError:
            return
        line = RED[0] if danger else MAG
        head.create_rectangle(0, hh - s(2), ww, hh, fill=line, outline="")
        f = font(11)
        tw = min(ww - s(20), K.tkfont_of(head, f).measure(title) + s(28))
        ph = hh - s(2) - s(10)
        y1 = s(5)
        fill, ink = (RED[0], "#ffffff") if danger else ("#ffffff", NAVY)
        K.rrect(head, s(10), y1, s(10) + tw, y1 + ph, ph // 2, fill=fill)
        head.create_text(s(10) + tw // 2, y1 + ph // 2, text=title, fill=ink, font=f, anchor="center")
    head.bind("<Configure>", draw)
    return head


def _danger_buttons():
    """'red' 단추(DP 의 주된 일)는 분홍으로, 되돌릴 수 없는 일의 단추만 빨간 단추로."""
    from . import MAG_HI, MAG_LO
    pink = (MAG, MAG_HI, MAG_LO, "#ffffff")
    K.KINDS["red"] = pink
    K.KINDS["danger"] = RED
    base = K.CButton.__init__

    def __init__(self, cv, text, command, kind="blue", spec=None, tag=None):
        if kind == "red" and (text or "").strip() in DANGER:
            kind = "danger"
        base(self, cv, text, command, kind, spec, tag)

    K.CButton.__init__ = __init__
    # 위젯으로 짠 기본 화면의 위험 단추 (U.danger_button) 도 빨갛게
    from ..dp import widgets as DPW
    for key in (U.ACCENT, U.RED):
        DPW.KINDS[key] = pink
    DPW.KINDS[U.DANGER_BG] = RED


def _redraw_canvas(canvas):
    """U.redraw_canvas 와 같은 일 (같은 바탕으로 다시 칠해 다시 그리게) - 빛깔 옮기기를 거치지 않는다."""
    try:
        canvas.tk.call(canvas._w, "configure", "-background", canvas.tk.call(canvas._w, "cget", "-background"))
    except tk.TclError:
        pass


def apply():
    global _done
    if _done:
        return
    _done = True
    _danger_buttons()
    U.redraw_canvas = _redraw_canvas
    from ..dp import dialogs as D
    D.dialog_bar = dialog_bar
    # dialog_bar 를 제 이름으로 받아 간 DP 화면
    import importlib
    for name in ("season", "held"):
        try:
            mod = importlib.import_module("%s.%s" % (D.__name__.rsplit(".", 1)[0], name))
        except ImportError:
            continue
        if hasattr(mod, "dialog_bar"):
            mod.dialog_bar = dialog_bar
