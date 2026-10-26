# -*- coding: utf-8 -*-
"""에메랄드 테마 - 허브 창 (시안 A 의 언어로 그린 위 탭 줄 · 하위 탭 줄).

시안에 허브 그림은 없다 - 시안의 바탕 · 창 · 단추 · 고름 표시를 그대로 써서 그린다:

    위 탭 줄     청록 빗금 바탕 위에 GBA 창(남색 테 · 종이 바탕)이 하나씩 - 도구 그림 + 이름.
                 고른 묶음은 빨간 머리 띠(가방 시안의 '◀ 지닌 도구 ▶' 띠)와 같은 빨강에 흰 글씨 · 흰 ▶,
                 올리면 연노랑 (시안의 고른 줄), 새 소식은 빨간 점 (고른 빨간 칸 위에서는 노란 점)
    하위 탭 줄   청록 빗금 위에 시안의 '줄 세우기' 칸 - 흰 바탕 · 남색 2px 테, 고른 탭은 남색 바탕 흰 글씨

창 크기 · 묶음 · 하위 탭 · 탭 화면 · 오가는 동작은 DP 허브 그대로다 (skins/dp/hub.py).
아이콘은 DP 와 같은 포켓몬 도구 그림(poke_icons)이다.
"""
import tkinter as tk

from ... import ui_common as U
from ... import ui_hub
from ..dp import font
from ..dp import hub as DPH
from ..dp import kit as K
from ..dp import poke_icons
from . import INK_A, NAVY, PAPER, RED, RED_D, SELY, WIN
from . import gba

DOT = DPH.DOT
DOT_ON_RED = "#ffe040"      # 고른 빨간 칸 위의 새 소식 점


class HubWindow(DPH.HubWindow):

    def __init__(self, app):
        DPH.HubWindow.__init__(self, app)
        self.bar.configure(bg=gba.BG1)
        for cv in self.subs.values():
            cv.configure(bg=gba.BG1)

    # ---------------- 위 탭 줄 (묶음)
    def _paint_bar(self):
        cv = self.bar
        try:
            cv.delete("all")
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w < 50:
            return
        s = U.h
        gba.stripes(cv, 0, 0, w, h)
        spec = font(11)
        f = K.tkfont_of(cv, spec)
        icons = dict((g, poke_icons.photo(DPH.ICON.get(g, "poke-ball"))) for g in self.groups)
        iw = dict((g, ph.width() if ph is not None else 0) for g, ph in icons.items())
        gap, pad, cur_w = s(6), s(12), s(14)       # cur_w = ▶ 자리 (모든 칸에 둔다 - 고를 때 칸이 안 움직이게)
        between = s(6)
        x0 = s(8)

        def widths(p):
            return [cur_w + iw[g] + gap + f.measure(self.group_labels[g]) + 2 * p for g in self.groups]
        want = widths(pad)
        room = w - 2 * x0 - between * (len(want) - 1)
        if sum(want) > room:                         # 넘치면 여백만 줄인다 (글씨는 그대로)
            cut = (sum(want) - room) / float(2 * len(want))
            pad = max(s(4), int(pad - cut))
            want = widths(pad)
        cur = ui_hub.GROUP_OF.get(self.current)
        x = x0
        self._boxes = {}
        y1, y2 = s(4), h - s(4)
        bw = max(2, s(3))
        for g, tw in zip(self.groups, want):
            on = g == cur
            if on:
                gba.frame(cv, x, y1, x + tw, y2, fill=RED, bw=bw, inner=False)
            else:
                gba.frame(cv, x, y1, x + tw, y2, fill=SELY if g == self._hover else PAPER, bw=bw, inner=False)
            cx = x + pad
            cy = (y1 + y2) // 2
            if on:
                gba.cursor(cv, cx, cy, s(5), fill="#ffffff")
            ix = cx + cur_w
            if icons[g] is not None:
                cv.create_image(ix + iw[g] // 2, cy, image=icons[g])
            tx = ix + iw[g] + gap
            if on:
                d = max(1, s(1))
                cv.create_text(tx + d, cy + d, text=self.group_labels[g], fill=RED_D, font=spec, anchor="w")
            cv.create_text(tx, cy, text=self.group_labels[g], fill="#ffffff" if on else INK_A, font=spec, anchor="w")
            if any(k in self.badges for k in ui_hub.GROUP_TABS[g]):
                d = s(4)
                bx, by = x + tw - s(8), y1 + s(8)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT_ON_RED if on else DOT, outline=NAVY,
                               width=2)
            self._boxes[g] = (x, x + tw)
            x += tw + between

    # ---------------- 하위 탭 줄
    def _make_sub(self, g, gf):
        body = DPH.HubWindow._make_sub(self, g, gf)
        body.configure(bg=WIN)
        return body

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
        s = U.h
        gba.stripes(cv, 0, 0, w, h)
        cv.create_rectangle(0, h - max(2, s(2)), w, h, fill=NAVY, outline="")
        spec = font(11)
        f = K.tkfont_of(cv, spec)
        x = s(14)
        y1, y2 = s(3), h - s(4)
        boxes = []
        cur = self.last.get(g)
        for key in ui_hub.GROUP_TABS[g]:
            lb = self.labels[key]
            bw = f.measure(lb) + s(30)
            tg = ("sub_" + key, "sub_")
            gba.sort_box(cv, x, y1, x + bw, y2, lb, spec, key == cur, tags=tg, hover=self._sub_hover == key)
            if key in self.badges:
                d = s(3)
                bx, by = x + bw - s(6), y1 + s(6)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=DOT, outline=PAPER, width=1, tags=tg)
            boxes.append((key, (x, y1, x + bw, y2)))
            x += bw + s(6)
        self._sub_boxes[g] = boxes
