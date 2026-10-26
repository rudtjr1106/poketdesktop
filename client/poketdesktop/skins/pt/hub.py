# -*- coding: utf-8 -*-
"""플라티나 테마 - 허브 창 (시안 B 의 말로 그린 탭 줄).

시안에 허브 그림은 없다 - 가방 시안의 말을 그대로 쓴다:

    위 탭 줄     머리 띠(#5b6676 → #465060, 아래 3px 진한 줄) 위에 묶음마다 입체 캡슐 단추
                 (도구 그림 + 이름). 보통은 흰 회색 캡슐, 고른 묶음은 하늘색 캡슐 (시안의 '지닌 도구' 주머니),
                 올리면 하늘색 빛 고리, 새 소식은 빨간 점.
    하위 탭 줄   강철 바탕 위에 시안의 고르기 줄(.seg) - 회색 홈 안에 고른 탭만 흰 알약.
    몸           강철 바탕 (각 탭 화면이 그 위에 판을 놓는다).

창 크기 · 묶음 · 하위 탭 · 점 · 오가는 일(_open)은 DP 허브(skins/dp/hub.py) 그대로다 - 칠하는 것만 바꾼다.
아이콘은 직접 그리지 않는다 (DP 의 poke_icons).
"""
import tkinter as tk

from ... import ui_common as U
from ... import ui_hub
from ..dp import font
from ..dp import hub as DPH
from ..dp import kit as K
from ..dp import poke_icons
from . import RIM, STEEL, WHITE
from . import _pt as P

BAR_H = 44          # 묶음 탭 줄 (머리 띠) - 검사: 46 을 넘지 않는다
SUB_H = 34          # 하위 탭 줄 (고르기 줄 30 + 위아래 여백)
DOT = "#ff3b3b"


class HubWindow(DPH.HubWindow):

    def __init__(self, app):
        DPH.HubWindow.__init__(self, app)
        self.bar.configure(height=U.h(BAR_H), bg=STEEL)
        for cv in self.subs.values():
            cv.configure(height=U.h(SUB_H), bg=STEEL)

    # ---------------- 위 탭 줄 (묶음) ----------------
    def _paint_bar(self):
        cv = self.bar
        try:
            cv.delete("all")
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w < 50:
            return
        P.head_band(cv, 0, 0, w, h)
        spec = font(11)
        f = K.tkfont_of(cv, spec)
        icons = dict((g, poke_icons.photo(DPH.ICON.get(g, "poke-ball"))) for g in self.groups)
        iw = dict((g, ph.width() if ph is not None else 0) for g, ph in icons.items())
        gap, pad, sp = U.h(6), U.h(14), U.h(6)
        x0 = U.h(8)
        room = w - 2 * x0 - sp * (len(self.groups) - 1)
        want = [iw[g] + gap + f.measure(self.group_labels[g]) + 2 * pad for g in self.groups]
        if sum(want) > room:                      # 넘치면 여백만 줄인다 (글씨는 그대로)
            cut = (sum(want) - room) / float(2 * len(want))
            pad = max(U.h(4), int(pad - cut))
            want = [iw[g] + gap + f.measure(self.group_labels[g]) + 2 * pad for g in self.groups]
        cur = ui_hub.GROUP_OF.get(self.current)
        y1, y2 = U.h(5), h - 3 - U.h(5)
        x = x0
        self._boxes = {}
        for g, tw in zip(self.groups, want):
            on = g == cur
            hov = g == self._hover and not on
            P.capsule(cv, x, y1, x + tw, y2, "cyan" if on else "white", hover=hov, rim_w=2)
            if hov:
                P.glow(cv, x, y1, x + tw, y2, (y2 - y1) // 2)
            cx, cy = x + pad, (y1 + y2) // 2
            if icons[g] is not None:
                cv.create_image(cx + iw[g] // 2, cy, image=icons[g])
            cv.create_text(cx + iw[g] + gap, cy, text=self.group_labels[g], font=spec, anchor="w",
                           fill=P.LOOKS["cyan" if on else "white"][3])
            if any(k in self.badges for k in ui_hub.GROUP_TABS[g]):
                d = U.h(4)
                bx, by = x + tw - U.h(9), y1 + U.h(7)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT, outline=WHITE, width=2)
            self._boxes[g] = (x, x + tw)
            x += tw + sp

    # ---------------- 하위 탭 줄 ----------------
    def _paint_sub(self, g):
        cv = self.subs.get(g)
        if cv is None:
            return
        try:
            cv.delete("all")
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w < 50:
            return
        P.steel(cv, 0, 0, w, h)
        items = [(k, self.labels[k]) for k in ui_hub.GROUP_TABS[g]]
        sh = h - U.h(6)
        sw = P.seg_width(cv, items, font(11), pad=U.h(34))
        x, y = U.h(10), U.h(4)
        boxes = P.seg(cv, x, y, sw, sh, items, self.last.get(g), None, None, spec=font(11), hover=self._sub_hover)
        cv.create_line(0, h - 1, w, h - 1, fill=RIM)
        self._sub_boxes[g] = boxes
        d = U.h(3)
        for key, (_x1, y1, x2, _y2) in boxes:
            if key in self.badges:
                bx, by = x2 - U.h(6), y1 + U.h(8)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT, outline=WHITE, width=1)
