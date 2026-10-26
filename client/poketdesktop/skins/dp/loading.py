"""DP 테마의 '불러오는 중' - 창 위에 덮는 판(Overlay)과 작은 창(Popup).

v2 (2026-10-25): 글상자 한 겹 + 앱의 몬스터볼 도구 그림(직접 그리지 않는다)이 통통 튄다.

    덮는 판    DP 글상자에 '불러오는 중...' - 점이 하나씩 늘어난다 (0.4초마다). 위에 몬스터볼이 튄다.
               오래 걸리면 글상자 안쪽 아래에 흐리게 까닭이 붙는다 (기다린 초가 센다).
    작은 창    바탕만 DP 로 (안은 덮는 판이 채운다)

ui_loading 의 같은 이름 클래스 자리에 들어간다 (skins.skinnable) - 시간 · 닫기 · say 는 기본 것 그대로,
테마는 _build · _paint · _set_note 만 덮는다.
"""
import math
import time
import tkinter as tk

from ... import item_icons
from ... import ui_common as U
from ... import ui_loading as base
from . import INK2, LINE_D, font
from . import dialogs as D
from . import poke_icons
from . import kit as K

DOT_STEP = 0.4          # 점이 하나 늘어나는 간격 (초)
BOX_W = 300             # 글상자 폭


def ball(cv, cx, cy, r, spin, tags=()):
    """몬스터볼 그림 (앱이 쓰는 도구 그림, 없으면 본가 몬스터볼 그림) - spin 쪽으로 통통 튄다."""
    px = max(24, (r * 2) // 24 * 24) if r * 2 >= 24 else 24
    keep = getattr(cv, "dp_ball", None)
    if keep is None:
        keep = cv.dp_ball = {}
    ph = keep.get(px)
    if ph is None:
        ph = item_icons.photo("POKEBALL", r * 2) or poke_icons.photo("poke-ball")
        keep[px] = ph
    hop = abs(math.sin(math.radians(spin))) * U.h(8)
    return cv.create_image(cx, cy + U.h(4) - hop, image=ph, tags=tags)


class Overlay(base.Overlay):

    def _build(self, parent, text):
        self._dots = -1
        self._shown_note = None
        self._note = ""
        self._ball_xy = None
        self.box = tk.Canvas(parent, bg=D.BODY, highlightthickness=0, bd=0)
        self.box.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.cv = self.box
        self.box.bind("<Configure>", lambda _e: self._draw())

    def _dot_count(self):
        return int((time.time() - self.t0) / DOT_STEP) % 4

    def _draw(self):
        """글상자 · 몬스터볼을 통째로 다시 그린다 (글이 바뀔 때만 - 공은 _paint 가 따로 돌린다)."""
        cv, s = self.box, U.h
        try:
            ww, hh = cv.winfo_width(), cv.winfo_height()
            cv.delete("all")
        except tk.TclError:
            return
        if ww < 20 or hh < 20:
            self._ball_xy = None
            return
        self._dots = self._dot_count()
        self._shown_note = self._note
        bw = min(ww - s(24), s(BOX_W))
        tw = bw - s(28)
        msg = "%s%s" % (self.text, "." * self._dots)
        # 점이 늘어도 상자가 흔들리지 않게 점 셋 자리를 쳐서 높이를 잰다
        th = K.text_height(cv, self.text + "...", font(11), tw)
        nh = (K.text_height(cv, self._note, font(9), tw) + s(6)) if self._note else 0
        r = s(20)
        total = r * 2 + s(10) + s(10) + th + nh + s(10)
        top = max(s(8), int(hh * 0.45 - total / 2.0))
        self._ball_xy = (ww // 2, top + r, r)
        y = top + r * 2 + s(10)
        x1 = (ww - bw) // 2
        K.rrect(cv, x1, y, x1 + bw, y + s(10) + th + nh + s(10), s(8), fill="#ffffff", outline=LINE_D, width=2)
        K.text(cv, x1 + s(14), y + s(10), msg, font(11), anchor="nw", width=tw)
        if self._note:
            K.text(cv, x1 + s(14), y + s(10) + th + s(6), self._note, font(9), fill=INK2, anchor="nw", width=tw)
        self._ball()

    def _ball(self):
        self.box.delete("ball")
        x, y, r = self._ball_xy
        ball(self.box, x, y, r, self.spin, tags=("ball",))

    def _paint(self):
        if self._ball_xy is None or self._dots != self._dot_count() or self._shown_note != self._note:
            self._draw()
        else:
            self._ball()

    def _set_note(self, text):
        self._note = text

    def say(self, text):
        self.text = text
        self._dots = -1                  # 다음 그리기에서 새 글로 다시 짓는다
        self._draw()


class Popup(base.Popup):

    def _frame(self):
        self.win.configure(bg=D.BODY, highlightthickness=0)
