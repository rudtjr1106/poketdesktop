# -*- coding: utf-8 -*-
"""소드·실드 테마 - 지닌 도구 고르기 (포켓몬 관리의 '지니게 하기' 창). 시안 K 의 가방 언어로:

        ┌ 남색 머리 [도구 지니게 하기] (분홍 줄) ─────────┐
        │ ┌ 흰 판 ─────────────────────────────────────┐ │
        │ │ 리자몽에게 지니게 할 도구            (239종) │ │
        │ │▌[그림] 가벼운돌 (남색 줄 · 흰 글씨)    × 3  │ │   고른 줄 = 남색 + 왼쪽 분홍 띠 (가방 목록과 같다)
        │ │  [그림] 강철주얼                       × 3  │ │
        │ └────────────────────────────────────────────┘ │
        │ ┌ 흰 판: [남색 그림 칸] 이름 · 종류 · 개수 / 설명 / 진화 경고 ┐ │
        │ ( 안내 · 오류 글 )                      [닫기] │
        └────────────────────────────────────────────────┘

동작 · 크기 · 키(위아래 · Enter · Esc)는 DP 창(그 밑의 기본 창) 그대로 - 칠하는 고리만 바꾼다.
"""
import tkinter as tk

from ... import item_icons
from ... import ui_bag as BAG
from ... import ui_common as U
from ..dp import font, tone
from ..dp import held as DPH
from ..dp import kit as K
from ..dp.scene import T
from . import DESC, DIMK, MAG, NAVY, NAVY2
from . import _sw as S

_clamp = DPH._clamp
WARN = "#c06810"


class HeldPicker(DPH.HeldPicker):

    def _build(self):
        DPH.HeldPicker._build(self)
        self.win.configure(bg=NAVY)
        self.cv.configure(bg=NAVY)
        S.paper_list(self.vl)
        S.restyle(self.close_btn, "white")
        self.ROW_H = U.h(26)

    # ---------------- 크기 (흰 판 테만큼 띠를 늘린다) ----------------
    def _band_tw(self, W):
        s = U.h
        return W - 2 * s(16) - s(56) - s(14) - s(14)

    def _band_need(self, cv, W):
        return DPH.HeldPicker._band_need(self, cv, W) + U.h(16)

    # ---------------- 판 ----------------
    def _paint(self):
        self._job = None
        if not self.alive:
            return
        cv, s = self.cv, U.h
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 200 or H < 200:
            return
        cv.delete("scene")
        self._msg_ids = None
        BOT = s(62)
        BH = min(self._band_need(cv, W), max(s(90), H - BOT - s(150)))
        LH = H - BOT - BH
        cv.create_rectangle(0, 0, W, H, fill=NAVY, outline="", tags=T)
        self._paint_list(cv, W, LH)
        self._paint_band(cv, W, LH, BH)
        # 아래: 흰 글상자 (안내 · 오류) + [닫기]
        y1, y2 = H - BOT + s(8), H - s(12)
        bw = max(s(70), self.close_btn.want_width(s(34)))
        self.close_btn.layout(W - s(16) - bw, y1, W - s(16), y2)
        mx2 = W - s(16) - bw - s(10)
        K.rrect(cv, s(16), y1, mx2, y2, (y2 - y1) // 3, fill="#ffffff", tags=T)
        text, c = self.msg
        self._msg_w = max(40, mx2 - s(16) - s(28))
        self._msg_ids = K.text(cv, s(30), (y1 + y2) // 2, text, font(11), fill=tone(c) if c else NAVY, anchor="w",
                               width=self._msg_w, tags=T)

    def _paint_list(self, cv, W, LH):
        s = U.h
        bx1, by1, bx2, by2 = s(16), s(14), W - s(16), LH - s(6)
        S.card(cv, bx1, by1, bx2, by2, tags=T)
        ix1, iy1, ix2, iy2 = bx1 + s(14), by1 + s(10), bx2 - s(12), by2 - s(8)
        th = s(26)
        m = iy1 + th // 2
        name = "%s에게 지니게 할 도구" % self.mon["info"].get("name", "")
        if self._state == "list":
            S.chip(cv, ix2 - K.tkfont_of(cv, font(9)).measure("%d종" % len(self._items)) - s(16), m - s(10),
                   "%d종" % len(self._items), fill=NAVY2, tags=T)
        cv.create_text(ix1, m, text=_clamp(cv, name, font(11), ix2 - ix1 - s(70), 1), fill=NAVY, font=font(11),
                       anchor="w", tags=T)
        ly1 = iy1 + th + s(8)
        if self._state == "list":
            self._place("list", self.vl.frame, ix1 - s(6), ly1, ix2 - ix1 + s(6), iy2 - ly1)
            return
        self._hide("list")
        note = {"empty": "지닐 수 있는 도구가 없다.", "error": "가방을 열지 못했다."}.get(self._state)
        if note:
            K.text(cv, (ix1 + ix2) // 2, ly1 + s(24), note, font(11), fill=DIMK, anchor="n", justify="center",
                   width=ix2 - ix1 - s(20), tags=T)

    def _draw_row(self, cv, data, x, y, w, h, tags, hover=None):
        """가방 목록의 줄과 같다: 고른 줄은 남색 바탕 + 흰 글씨 + 왼쪽 분홍 띠."""
        s = U.h
        it, n = data
        m = y + h // 2
        sel = it["id"] == self._cur
        r = s(8)
        if sel:
            K.rrect(cv, x + s(2), y + s(1), x + w - s(4), y + h - s(1), r, fill=MAG, tags=tags)
            K.rrect(cv, x + s(8), y + s(1), x + w - s(4), y + h - s(1), r, fill=NAVY, tags=tags)
        fg = "#ffffff" if sel else NAVY
        icon = item_icons.photo(it["id"], 22)
        ix = x + s(28)
        if icon is not None:
            cv.create_image(ix, m, image=icon, tags=tags)
        else:
            cv.create_oval(ix - s(4), m - s(4), ix + s(4), m + s(4), fill=BAG.CAT_COLOR.get(it.get("cat"), DIMK),
                           outline="", tags=tags)
        t = cv.create_text(x + s(46), m, text=it["kr"], fill=fg, font=font(11), anchor="w", tags=tags)
        if it["id"] in self.evo_items:
            b = cv.bbox(t)
            cx = (b[2] if b else x + 120) + s(8)
            f = font(8)
            cw = K.tkfont_of(cv, f).measure("진화 도구") + s(14)
            K.rrect(cv, cx, m - s(9), cx + cw, m + s(9), s(5), fill="#fff0dc", tags=tags)
            cv.create_text(cx + cw // 2, m, text="진화 도구", fill=WARN, font=f, anchor="center", tags=tags)
        cv.create_text(x + w - s(16), m, text="×%d" % n, fill=fg, font=font(11), anchor="e", tags=tags)

    def _paint_band(self, cv, W, y, BH):
        """설명 판 (가방의 설명 판처럼): 남색 그림 칸 · 이름 · 종류 · 개수 / 설명 / 진화 경고."""
        s = U.h
        it, n = self._current()
        title, body, warn, icon_id = self._band_text(it, n)
        x1, y1, x2, y2 = s(16), y + s(6), W - s(16), y + BH - s(4)
        S.card(cv, x1, y1, x2, y2, tags=T)
        bs = s(56)
        ix, iy = x1 + s(14), y1 + (y2 - y1 - bs) // 2
        K.rrect(cv, ix, iy, ix + bs, iy + bs, 9, fill=NAVY, tags=T)
        ph = item_icons.photo(icon_id, 32) if icon_id else None
        if ph is not None:
            cv.create_image(ix + bs // 2, iy + bs // 2, image=ph, tags=T)
        tx, tw = ix + bs + s(14), self._band_tw(W)
        th = K.text_height(cv, title, font(11), tw)
        wh = (K.text_height(cv, warn, font(10), tw) + s(4)) if warn else 0
        inner = (y2 - y1) - s(16)
        if body:
            lh = K.tkfont_of(cv, font(11)).metrics("linespace")
            body = _clamp(cv, body, font(11), tw, max(1, (inner - th - s(4) - wh) // max(1, lh)))
        bh = (s(4) + K.text_height(cv, body, font(11), tw)) if body else 0
        ty = y1 + max(s(8), ((y2 - y1) - th - bh - wh) // 2)
        K.text(cv, tx, ty, title, font(11), fill=NAVY, tags=T, width=tw)
        ty += th
        if body:
            K.text(cv, tx, ty + s(4), body, font(11), fill=DESC, tags=T, width=tw)
            ty += bh
        if warn:
            K.text(cv, tx, ty + s(4), warn, font(10), fill=WARN, tags=T, width=tw)
