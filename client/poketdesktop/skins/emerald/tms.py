# -*- coding: utf-8 -*-
"""에메랄드 테마 - 가방의 기술머신 칸. 도구 칸과 같은 시안 A 의 틀(bag.GBABag)에 그린다.

    머리 띠 '◀ 기술머신 ▶' · 가운데 위 창 (한 줄 안내 · 새로고침) · 오른쪽 위 창 '가진 기술머신  12/358'
    목록 창    [가진 것만][전부] / [타입: 전체][분류: 전체] (줄 세우기 칸) + 기술머신 줄 (고른 줄은 연노랑 + 빨간 ▶)
    설명 창    타입 꼬리표 · 기술 이름 · 분류 · 위력 · 설명
    누구에게   '배울 수 있는 포켓몬' 줄 + 빨간 큰 단추 '가르치기'

동작은 DP 기술머신 칸(skins/dp/tms.py) · 기본 기술머신 칸 그대로다.
"""
import tkinter as tk

from ... import ui_common as U
from ... import ui_tms as TM
from ..dp import DIM, INK, INK2, font
from ..dp import kit as K
from ..dp import tms as DPT
from ..dp.scene import T
from . import PAPER, SELY
from . import gba
from .bag import HOV, GBABag


class TmWindow(GBABag, DPT.TmWindow):

    def _build(self):
        DPT.TmWindow._build(self)
        for vl in (self.tms_vl, self.mons_vl):
            vl.cv.configure(bg=PAPER)
            vl.frame.configure(bg=PAPER)
        self.use_btn.kind = "cta"

    def _money_label(self):
        return "가진 기술머신"

    def _pocket_count_text(self, key):
        return ""                        # 기술머신 칸에서는 다른 주머니에 든 수를 모른다 - 비운다

    def _em_info(self):
        t = self._move_t
        got = self.move_lines(t) if t else None
        title, body, art = self._band_content()
        if not got:
            return {"name": title, "chip": None, "sub": "", "body": body, "art": art}
        name, sub, desc = got
        return {"name": name, "chip": None, "sub": sub, "body": desc, "art": art}

    def _paint(self):
        self._job = None
        if not self.alive:
            return
        cv = self.cv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 200 or H < 200:
            return
        cv.delete("scene")
        self._msg_ids = None
        s = U.h
        c1, c2, top = self._em_layout(W, H)
        self._paint_back(cv, W, H)
        self._paint_top(cv, W, c1, c2, top)
        self._paint_left(cv, H)
        self._paint_tm_list(cv, c1, c2, H)
        g, m = s(4), s(10)
        rx1, rx2 = c2 + g, W - m
        iy1 = top + s(8)
        hint = "이미 배운 포켓몬은 회색" if self._move_t else ""
        need = self._who_need(cv, rx1, rx2, "배울 수 있는 포켓몬", hint, self._mon_note, ())
        ih = self._info_fit(cv, rx1, rx2, H, H - m - iy1 - s(8) - need)
        self._paint_info(cv, rx1, iy1, rx2, iy1 + ih)
        self._paint_who(cv, rx1, iy1 + ih + s(8), rx2, H - m, "배울 수 있는 포켓몬", hint, self._mon_note, (),
                        self.use_btn)
        self._toast_box = (rx1, iy1, rx2, iy1 + ih)
        self._paint_toast()

    def _paint_tm_list(self, cv, x0, x1, LH):
        s = U.h
        _c1, _c2, top = self._em_layout(cv.winfo_width(), LH)
        ix1, iy1, ix2, iy2 = self._list_frame(cv, x0, x1, top, LH)
        th = s(26)
        self._tabs(cv, ix1, iy1, th, [("have", "가진 것만"), ("all", "전부")],
                   "have" if self.only_have else "all", "flt",
                   lambda k: (k == "have") != self.only_have and self._toggle_filter(), span=ix2)
        iy1b = iy1 + th + s(6)
        right = self._tabs(cv, ix1, iy1b, th, [("type", self.type_btn.text + " ▾"), ("cat", self.cat_btn.text + " ▾")],
                           None, "tmf", lambda k: self._open_type_menu() if k == "type" else self._open_cat_menu(),
                           span=ix2)
        self._tab_boxes = dict(right)
        ly1 = iy1b + th + s(6)
        if self._tm_rows:
            self._place("tms", self.tms_vl.frame, ix1 - s(4), ly1, ix2 - ix1 + s(4), iy2 - ly1)
        else:
            self._hide("tms")
            K.text(cv, (ix1 + ix2) // 2, ly1 + s(40),
                   "아직 하나도 없습니다.\n포켓몬을 잡으면 가끔 나옵니다." if self.only_have else "보일 기술머신이 없습니다.",
                   font(11), anchor="n", justify="center", width=ix2 - ix1 - 20, tags=T)

    def _draw_tm_row(self, cv, t, x, y, w, h, tags, hover=None):
        """기술머신 한 줄: 고른 줄은 연노랑 띠 + 빨간 ▶, 새로 받은 것은 노란 점 (번호 앞)."""
        s = U.h
        have = bool(t.get("have"))
        sel = t["no"] == self.no
        if sel:
            cv.create_rectangle(x, y, x + w, y + h, fill=SELY, outline="", tags=tags)
        elif hover is not None and have:
            cv.create_rectangle(x, y, x + w, y + h, fill=HOV, outline="", tags=tags)
        m = y + h // 2
        if sel:
            gba.cursor(cv, x + s(4), m, s(6), tags=tags)
        if t["no"] in self.fresh:
            r = s(4)
            cv.create_oval(x + s(19) - r, m - r, x + s(19) + r, m + r, fill="#f0a800", outline="", tags=tags)
        cv.create_text(x + s(26), m, text="%03d" % t["no"], fill=INK2 if have else DIM, font=font(9),
                       anchor="w", tags=tags)
        cv.create_text(x + s(62), m, text=t["kr"], fill=INK if have else DIM, font=font(11), anchor="w",
                       tags=tags)
        cat = TM.CAT_KR.get(t["cat"], t["cat"])
        cv.create_text(x + w - s(10), m, text=cat, fill=DPT.CAT_COLOR.get(t["cat"], DIM) if have else DIM,
                       font=font(9), anchor="e", tags=tags)
        self._type_chip(cv, x + w - s(46), m, t.get("type"), have, tags)
