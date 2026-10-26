# -*- coding: utf-8 -*-
"""블랙·화이트 테마 - 지닌 도구 고르기 (포켓몬 관리의 '지니게 하기' 창).

시안 H 의 가방 말을 그대로 쓴다:

        ┌ 머리 띠 [도구 지니게 하기] ───────────────────┐   (작은 창 머리는 다른 작은 창과 같이)
        │ ┌ 어두운 판 ─────────────────────────────┐   │
        │ │ 리자몽에게 지니게 할 도구          3종 │   │
        │ │ [● 먹다남은음식   진화 도구    ×  1 ]  │   │   고른 줄은 하늘빛 테 + 번지는 빛
        │ └────────────────────────────────────────┘   │
        │ ┌ 어두운 판: (◯ 도구 그림 고리) 이름 · 종류 · 개수 / 설명 / 진화 경고 ┐
        │ [ 안내 글 알약 ]                     (닫기)   │
        └───────────────────────────────────────────────┘

고르는 규칙 · 서버 호출 · 창 크기 · 커서(마우스 · 화살표 · Enter)는 DP 창(skins/dp/held.py) 그대로 - 칠하는 것만 바꾼다.
"""
import tkinter as tk

from ... import item_icons
from ... import ui_bag as BAG
from ... import ui_common as U
from ..dp import font
from ..dp import held as DPH
from ..dp import kit as K
from ..dp.scene import T
from . import BG, CARD, CYAN, DESC, DIMT, FAINT, GLOW_FAR, LINE, PANEL, PANEL_HI, SEL, TEXT, mix
from . import _art as A
from .bag import BWButton

_clamp = DPH._clamp
WARN = "#f0a83a"                  # 진화 도구 경고 (bw/box.py 의 WARM 과 같은 빛깔)
RING_OUT = mix(PANEL, CYAN, 0.4)  # 도구 그림 고리 바깥 줄 (가방의 설명 판과 같다)


class HeldPicker(DPH.HeldPicker):

    def _build(self):
        DPH.HeldPicker._build(self)
        self.win.configure(bg=BG)
        self.cv.configure(bg=BG)
        for w in (self.vl.cv, self.vl.frame):
            try:
                w.configure(bg=PANEL)
            except tk.TclError:
                pass
        self.ROW_H = U.h(30)
        BWButton.adopt(self.close_btn, "dark")

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
        cv.create_rectangle(0, 0, W, H, fill=BG, outline="", tags=T)
        BOT = s(62)
        BH = min(self._band_need(cv, W), max(s(74), H - BOT - s(150)))
        LH = H - BOT - BH
        self._paint_list(cv, W, LH)
        self._paint_band(cv, W, LH, BH)
        self._paint_bottom(cv, 0, W, H - BOT, H, [(self.close_btn, s(70), s(110))])

    def _paint_list(self, cv, W, LH):
        s = U.h
        bx1, by1, bx2, by2 = s(10), s(10), W - s(10), LH - s(4)
        A.panel(cv, bx1, by1, bx2, by2, tags=T)
        ix1, iy1, ix2, iy2 = bx1 + s(12), by1 + s(8), bx2 - s(10), by2 - s(8)
        th = s(24)
        m = iy1 + th // 2
        K.text(cv, ix1, m, "%s에게 지니게 할 도구" % self.mon["info"].get("name", ""), font(11), fill=TEXT,
               anchor="w", tags=T)
        if self._state == "list":
            cv.create_text(ix2, m, text="%d종" % len(self._items), fill=DIMT, font=font(9), anchor="e", tags=T)
        cv.create_line(ix1, iy1 + th + s(4), ix2, iy1 + th + s(4), fill=LINE, tags=T)
        ly1 = iy1 + th + s(10)
        if self._state == "list":
            self._place("list", self.vl.frame, ix1 - s(4), ly1, ix2 - ix1 + s(4), iy2 - ly1)
            return
        self._hide("list")
        note = {"empty": "지닐 수 있는 도구가 없다.", "error": "가방을 열지 못했다."}.get(self._state)
        if note:
            K.text(cv, (ix1 + ix2) // 2, ly1 + s(24), note, font(11), fill=DIMT, anchor="n", justify="center",
                   width=ix2 - ix1 - s(20), tags=T)

    def _draw_row(self, cv, data, x, y, w, h, tags, hover=None):
        """시안 가방의 목록 줄 (.ln): 고른 줄은 하늘빛 테 + 번지는 빛."""
        s = U.h
        it, n = data
        m = y + h // 2
        x2 = x + w - s(4)
        if it["id"] == self._cur:
            K.rrect(cv, x, y + 1, x2, y + h - 1, s(7), fill=GLOW_FAR, tags=tags)
            K.rrect(cv, x + 1, y + 2, x2 - 1, y + h - 2, s(6), fill=SEL, outline=CYAN, width=1, tags=tags)
        elif hover is not None:
            K.rrect(cv, x + 1, y + 2, x2 - 1, y + h - 2, s(6), fill=PANEL_HI, tags=tags)
        icon = item_icons.photo(it["id"], 24)
        ix = x + s(18)
        if icon is not None:
            cv.create_image(ix, m, image=icon, tags=tags)
        else:
            cv.create_oval(ix - 4, m - 4, ix + 4, m + 4, fill=BAG.CAT_COLOR.get(it.get("cat"), FAINT), outline="",
                           tags=tags)
        _a, t = K.text(cv, x + s(38), m, it["kr"], font(11), fill=TEXT, anchor="w", tags=tags)
        if it["id"] in self.evo_items:
            b = cv.bbox(t)
            cx = (b[2] if b else x + 120) + s(8)
            f = font(8)
            cw = K.tkfont_of(cv, f).measure("진화 도구") + s(14)
            K.rrect(cv, cx, m - s(9), cx + cw, m + s(9), s(9), fill=CARD, outline=WARN, width=1, tags=tags)
            cv.create_text(cx + cw // 2, m, text="진화 도구", fill=WARN, font=f, anchor="center", tags=tags)
        cv.create_text(x2 - s(10), m, text="×%d" % n, fill=TEXT, font=font(11), anchor="e", tags=tags)

    # ---------------- 설명 판 (가방의 설명 판처럼 하늘빛 고리 안에 도구 그림) ----------------
    def _band_tw(self, W):
        return W - U.h(20) - U.h(24) - U.h(52) - U.h(16)

    def _paint_band(self, cv, W, y, BH):
        s = U.h
        it, n = self._current()
        title, body, warn, icon_id = self._band_text(it, n)
        x1, y1, x2, y2 = s(10), y + s(4), W - s(10), y + BH - s(2)
        A.panel(cv, x1, y1, x2, y2, tags=T)
        r = s(22)
        cx, cy = x1 + s(14) + r, (y1 + y2) // 2
        cv.create_oval(cx - r - s(5), cy - r - s(5), cx + r + s(5), cy + r + s(5), fill=RING_OUT, outline="", tags=T)
        cv.create_oval(cx - r - s(3), cy - r - s(3), cx + r + s(3), cy + r + s(3), fill=PANEL, outline="", tags=T)
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=PANEL, outline=CYAN, width=max(2, s(2)), tags=T)
        ph = item_icons.photo(icon_id, 32) if icon_id else None
        if ph is not None:
            cv.create_image(cx, cy, image=ph, tags=T)
        tx, tw = cx + r + s(16), self._band_tw(W)
        th = K.text_height(cv, title, font(11), tw)
        wh = (K.text_height(cv, warn, font(10), tw) + s(4)) if warn else 0
        if body:
            lh = K.tkfont_of(cv, font(11)).metrics("linespace")
            body = _clamp(cv, body, font(11), tw, max(1, (BH - s(20) - th - s(4) - wh) // max(1, lh)))
        bh = (s(4) + K.text_height(cv, body, font(11), tw)) if body else 0
        ty = y + max(s(10), (BH - th - bh - wh) // 2)
        K.text(cv, tx, ty, title, font(11), fill=CYAN, tags=T, width=tw)
        ty += th
        if body:
            K.text(cv, tx, ty + s(4), body, font(11), fill=DESC, tags=T)
            ty += bh
        if warn:
            K.text(cv, tx, ty + s(4), warn, font(10), fill=WARN, tags=T, width=tw)

    # ---------------- 아래 줄: 안내 글 알약 + 닫기 ----------------
    def _paint_bottom(self, cv, x0, W, y1, H, buttons):
        s = U.h
        bh = s(36)
        by1 = y1 + (H - y1 - bh) // 2
        x2 = W - s(12)
        for btn, lo, hi in buttons:
            w = max(lo, min(hi, btn.want_width(s(30))))
            btn.layout(x2 - w, by1, x2, by1 + bh)
            x2 -= w + s(8)
        mx1, my1, mx2, my2 = x0 + s(10), y1 + s(8), x2 - s(4), H - s(8)
        A.panel(cv, mx1, my1, mx2, my2, r=s(12), tags=T)
        text, c = self.msg
        self._msg_w = max(40, mx2 - mx1 - U.h(28))
        from .box import btone
        self._msg_ids = K.text(cv, mx1 + s(14), (my1 + my2) // 2, text, font(11),
                               fill=btone(c) if c else TEXT, anchor="w", width=self._msg_w, tags=T)

    def _say(self, text, color=None):
        DPH.HeldPicker._say(self, text, color)
        if self._msg_ids and color:
            try:
                from .box import btone
                self.cv.itemconfigure(self._msg_ids[1], fill=btone(color))
            except tk.TclError:
                pass


__all__ = ["HeldPicker", "_clamp"]
