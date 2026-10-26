# -*- coding: utf-8 -*-
"""금·은 테마 - 허브 창. 시안 G 에 허브 그림은 없어서 시안의 말(바탕 · 상자 · ▶ 커서)로 짰다:

    바탕         금빛 크림 + 옅은 점 (시안 .g .win)
    위 탭 줄     두 겹 테 상자(진한 테 · 금빛 안쪽 줄) **하나** 안에 묶음 여섯을 글자 메뉴로 고르게 놓는다
                 (게임보이 시작 메뉴처럼). 고른 묶음은 빨간 ▶ + 진한 글씨 + 옅은 금빛 칸, 나머지는 덜 진한 글씨
    하위 탭 줄   종이빛 띠 (아래에 진한 줄 2) 위의 글자 메뉴 - 고른 탭 앞에 빨간 ▶, 진한 글씨
    새 소식      빨간 점

창 크기 · 탭 줄 높이 · 묶음 · 하위 탭 · 탭을 오가는 일은 DP · 기본 허브 그대로다 (skins/dp/hub.py).
"""
import tkinter as tk

from ... import ui_hub
from ...ui_common import h as px
from ..dp import font
from ..dp import hub as DPH
from ..dp import kit as K
from . import G_BG, HOV, INK, INK2, PAPER, SEL
from ._gbc import arrow, dot_bg, gbox

DOT = "#e02820"


class HubWindow(DPH.HubWindow):

    def __init__(self, app):
        DPH.HubWindow.__init__(self, app)
        for g, cv in self.subs.items():
            try:
                cv.configure(bg=PAPER)
            except tk.TclError:
                pass
        try:
            self.bar.configure(bg=G_BG)
        except tk.TclError:
            pass

    # ---------------- 위 탭 줄 (상자 하나 안의 글자 메뉴) ----------------
    def _paint_bar(self):
        cv = self.bar
        try:
            cv.delete("all")
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w < 50:
            return
        dot_bg(cv, 0, 0, w, h)
        spec = font(11)
        f = K.tkfont_of(cv, spec)
        ix1, iy1, ix2, iy2 = gbox(cv, px(6), px(3), w - px(6), h - px(1))
        n = len(self.groups)
        cw = (ix2 - ix1) / float(n)
        cur = ui_hub.GROUP_OF.get(self.current)
        ym = (iy1 + iy2) // 2
        self._boxes = {}
        for i, g in enumerate(self.groups):
            x1 = int(ix1 + i * cw)
            x2 = int(ix1 + (i + 1) * cw)
            on = g == cur
            if on:
                cv.create_rectangle(x1, iy1, x2, iy2, fill=SEL, outline="")
            elif g == self._hover:
                cv.create_rectangle(x1, iy1, x2, iy2, fill=HOV, outline="")
            label = self.group_labels[g]
            tw = f.measure(label)
            tx = (x1 + x2) // 2 - tw // 2 + px(8)
            if on:
                arrow(cv, tx - px(16), ym, px(5))
            cv.create_text(tx, ym, text=label, fill=INK if on else INK2, font=spec, anchor="w")
            if any(k in self.badges for k in ui_hub.GROUP_TABS[g]):
                d = px(4)
                bx, by = min(x2 - px(8), tx + tw + px(8)), iy1 + px(6)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT, outline=PAPER, width=1)
            if i:
                cv.create_line(x1, iy1 + px(5), x1, iy2 - px(5), fill="#e6d4a0")
            self._boxes[g] = (x1, x2)

    # ---------------- 하위 탭 줄 (종이빛 띠의 글자 메뉴 + ▶) ----------------
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
        cv.create_rectangle(0, 0, w, h, fill=PAPER, outline="")
        cv.create_rectangle(0, h - 2, w, h, fill=INK, outline="")
        spec = font(11)
        f = K.tkfont_of(cv, spec)
        cur = self.last.get(g)
        x = px(14)
        boxes = []
        ym = (h - 2) // 2
        for key in ui_hub.GROUP_TABS[g]:
            label = self.labels[key]
            bw = f.measure(label) + px(36)
            on = key == cur
            if on:
                cv.create_rectangle(x + 1, px(2), x + bw - 1, h - 3, fill=SEL, outline="")
            elif self._sub_hover == key:
                cv.create_rectangle(x + 1, px(2), x + bw - 1, h - 3, fill=HOV, outline="")
            if on:
                arrow(cv, x + px(7), ym, px(4))
            cv.create_text(x + px(20), ym, text=label, fill=INK if on else INK2, font=spec, anchor="w")
            if key in self.badges:
                d = px(3)
                bx, by = x + bw - px(6), px(7)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT, outline="")
            boxes.append((key, (x, 0, x + bw, h)))
            x += bw + px(4)
        self._sub_boxes[g] = boxes
