# -*- coding: utf-8 -*-
"""DP 테마 - 지닌 도구 고르기 (포켓몬 관리의 '도구 지니게 하기' 창).

DP 가방의 도구 주머니처럼 (v2: 줄무늬 · 겹친 테 · 글씨 그림자를 걷고, 줄 높이를 낮춰 한 화면에 더 보인다):

        ┌ 하늘색 띠 [도구 지니게 하기] ──────────────────────┐
        │ ┌ 초록 칸 안의 흰 목록 ─────────────────────────┐ │
        │ │ 꼬부기에게 지니게 할 도구                 3종  │ │
        │ │ ▶ [그림] 오랭열매                   ×    2     │ │   빨간 ▶ 커서 + 크림빛 줄
        │ │   [그림] 금속코트 [진화 도구]       ×    1     │ │
        │ └────────────────────────────────────────────────┘ │
        │ 보라 설명 띠: [그림] 이름 · 종류 · 개수 / 설명 / 진화 경고 │
        │ 메시지 상자 (안내 · 오류)                   [닫기] │

커서는 마우스를 따라오고 위아래 화살표로도 옮긴다 - 가리킨 도구의 설명이 보라 띠에 뜬다 (DP 가방처럼 줄에는
이름 · 개수만). 누르거나 Enter 면 바로 지닌다 (기본 창과 같다). 무엇을 보일지 · 서버 호출 · 닫기는 기본 창
(ui_box.HeldPicker) 그대로다 - 짓는 고리(_build · _paint_note · _paint_rows)만 바꾼다.
창 크기(460 x 560, 도구를 받은 뒤 내용만큼 줄인다)는 기본 창과 같다.

(box.py 의 맨 끝이 이 클래스를 다시 내보낸다 - 스킨은 box 모듈에서 HeldPicker 를 찾는다.)
"""
import tkinter as tk

from common.korean import natural

from ... import item_icons
from ... import ui_bag as BAG
from ... import ui_box as BX
from ... import ui_common as U
from . import DIM, GREEN, INK2, PURPLE, PURPLE_EM, SEL, SEP, WHITE, font
from . import kit as K
from .dialogs import BODY, dialog_bar
from .scene import Scene, T

HOLD_W, HOLD_H = 460, 560          # 기본 창과 같은 크기 (도구를 받은 뒤 내용만큼 줄인다)
HOLD_WARN = "#ffc48a"              # 보라 띠 위의 진화 경고


def _clamp(cv, s, spec, width, n):
    """width 로 접어 n 줄까지만 (넘치면 끝에 …)."""
    lines = K.wrap(cv, s, spec, max(1, width)).split("\n")
    if len(lines) <= n:
        return "\n".join(lines)
    last = lines[n - 1]
    f = K.tkfont_of(cv, spec)
    while last and f.measure(last + "…") > width:
        last = last[:-1]
    return "\n".join(lines[:n - 1] + [last + "…"])


class HeldPicker(Scene, BX.HeldPicker):

    def _build(self):
        s = U.h
        self.win = U.panel(None, self.root, "도구 지니게 하기", HOLD_W, HOLD_H, 380, 400, self.close)
        dialog_bar(self.win, "도구 지니게 하기")
        self._scene_init()
        self.win.configure(bg=BODY)
        self.cv.configure(bg=BODY)
        self.alive = True
        self._items = []             # [(도구, 가진 수)] - 보일 줄
        self._state = "wait"         # wait · list · empty · error
        self._cur = None             # 커서가 가리키는 도구 id
        self._note_fg = None         # 안내 글 빛깔 (한 번 정하면 남는다 - 기본 창의 Label 처럼)
        self._band_cache = None
        self.ROW_H = s(26)
        self.vl = K.VList(self.cv, WHITE, self._draw_row)
        self.vl.on_click = lambda d, _x, _y, _w: self._choose_row(d[0])
        self.vl.on_hover = self._hover_row
        self.close_btn = K.CButton(self.cv, "닫기", self.close, "gray", font(10))
        self.win.bind("<Up>", lambda _e: self._step(-1))
        self.win.bind("<Down>", lambda _e: self._step(1))
        self.win.bind("<Return>", lambda _e: self._enter())
        self.win.bind("<Escape>", lambda _e: self.close())
        self._say("가방을 여는 중...")

    # ---------------- 칠하기 (기본 창이 부른다) ----------------
    def _paint_note(self, text, fg=None):
        if fg is not None:
            self._note_fg = fg
            if fg == U.DANGER and self._state == "wait":
                self._state = "error"
                self._soon()
        self._say(natural(text or ""), self._note_fg)

    def _paint_rows(self, rows, bag):
        self._items = [(it, bag.get(it["id"], 0)) for it in rows]
        self._state = "list" if rows else "empty"
        self._band_cache = None
        if rows and not any(it["id"] == self._cur for it, _n in self._items):
            self._cur = rows[0]["id"]
        self.vl.set([(self.ROW_H, d) for d in self._items], keep=False)
        self._fit()
        self._soon()

    def close(self):
        self.alive = False
        BX.HeldPicker.close(self)

    # ---------------- 커서 ----------------
    def _current(self):
        return next(((it, n) for it, n in self._items if it["id"] == self._cur), (None, 0))

    def _hover_row(self, data):
        if data is None or data[0]["id"] == self._cur:
            return                   # 목록을 벗어나도 커서는 그 자리에 남는다 (DP 처럼)
        self._cur = data[0]["id"]
        self.vl.refresh()
        self._soon()

    def _step(self, d):
        ids = [it["id"] for it, _n in self._items]
        if ids:
            i = ids.index(self._cur) if self._cur in ids else -1
            i = max(0, min(len(ids) - 1, i + d))
            self._cur = ids[i]
            self.vl.see(i)
            self.vl.refresh()
            self._soon()
        return "break"

    def _busy(self):
        return getattr(self, "_wait", None) is not None

    def _choose_row(self, it):
        if not self._busy():
            self.pick(it)

    def _enter(self):
        it, _n = self._current()
        if it is not None:
            self._choose_row(it)
        return "break"

    # ---------------- 크기 ----------------
    def _fit(self):
        """도구를 받은 뒤 창을 내용만큼으로 (많으면 기본 크기까지 - 그 위로는 목록이 굴러간다)."""
        s = U.h
        try:
            self.win.update_idletasks()
            W = self.cv.winfo_width()
            if W < 200:
                return
            n = max(2, len(self._items))
            want = max(s(150), n * self.ROW_H + s(74)) + self._band_need(self.cv, W) + s(62)
            self.cv.configure(height=want)
            U.fit_window(self.win, self.win.winfo_width(), hi=self.win.winfo_height(), keep_pos=True)
        except tk.TclError:
            pass

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
        BH = min(self._band_need(cv, W), max(s(74), H - BOT - s(150)))
        LH = H - BOT - BH
        self._paint_list(cv, W, LH)
        self._paint_band(cv, W, LH, BH)
        self._paint_bottom(cv, 0, W, H - BOT, H, [(self.close_btn, s(60), s(100))])

    def _paint_list(self, cv, W, LH):
        s = U.h
        cv.create_rectangle(0, 0, W, LH, fill=GREEN, outline="", tags=T)
        bx1, by1, bx2, by2 = s(8), s(8), W - s(8), LH - s(8)
        K.panel(cv, bx1, by1, bx2, by2, strong=True, tags=T)
        ix1, iy1, ix2, iy2 = bx1 + s(10), by1 + s(8), bx2 - s(10), by2 - s(6)
        th = s(24)
        m = iy1 + th // 2
        K.text(cv, ix1, m, "%s에게 지니게 할 도구" % self.mon["info"].get("name", ""), font(11), anchor="w", tags=T)
        if self._state == "list":
            cv.create_text(ix2, m, text="%d종" % len(self._items), fill=INK2, font=font(9), anchor="e", tags=T)
        cv.create_line(ix1, iy1 + th + s(2), ix2, iy1 + th + s(2), fill=SEP, width=2, tags=T)
        ly1 = iy1 + th + s(6)
        if self._state == "list":
            self._place("list", self.vl.frame, ix1, ly1, ix2 - ix1, iy2 - ly1)
            return
        self._hide("list")
        note = {"empty": "지닐 수 있는 도구가 없다.", "error": "가방을 열지 못했다."}.get(self._state)
        if note:
            K.text(cv, (ix1 + ix2) // 2, ly1 + s(24), note, font(11), fill=DIM, anchor="n", justify="center",
                   width=ix2 - ix1 - s(20), tags=T)

    def _draw_row(self, cv, data, x, y, w, h, tags, hover=None):
        s = U.h
        it, n = data
        m = y + h // 2
        if it["id"] == self._cur:
            K.rrect(cv, x + 2, y + 1, x + w - 2, y + h - 1, s(4), fill=SEL, tags=tags)
            K.cursor(cv, x + s(8), m, size=s(5), tags=tags)
        icon = item_icons.photo(it["id"], 20)
        ix = x + s(34)
        if icon is not None:
            cv.create_image(ix, m, image=icon, tags=tags)
        else:
            cv.create_rectangle(ix - 3, m - 3, ix + 3, m + 3, fill=BAG.CAT_COLOR.get(it.get("cat"), DIM),
                                outline="", tags=tags)
        _a, t = K.text(cv, x + s(50), m, it["kr"], font(11), anchor="w", tags=tags)
        if it["id"] in self.evo_items:
            # 지니게 하면 진화에 못 쓴다 - 줄에 꼬리표, 자세한 말은 보라 띠에 (기본 창은 줄 밑에 한 줄)
            b = cv.bbox(t)
            cx = (b[2] if b else x + 120) + s(8)
            f = font(8)
            cw = K.tkfont_of(cv, f).measure("진화 도구") + s(12)
            K.rrect(cv, cx, m - s(9), cx + cw, m + s(9), s(4), fill="#fff0cc", outline="#d8a040", width=1, tags=tags)
            cv.create_text(cx + cw // 2, m, text="진화 도구", fill="#a05010", font=f, anchor="center", tags=tags)
        K.text(cv, x + w - s(58), m, "×", font(11), anchor="w", tags=tags)
        K.text(cv, x + w - 12, m, str(n), font(11), anchor="e", tags=tags)

    # ---------------- 보라 설명 띠 ----------------
    def _band_text(self, it, n):
        """(제목, 본문, 경고 또는 None, 그림 도구 id)."""
        if it is None:
            held = self.mon.get("heldKr")
            body = (self.mon.get("heldDesc") or "") if held else "아무것도 지니고 있지 않다."
            return "지금 지닌 도구 · %s" % (held or "없음"), natural(body), None, self.mon.get("held")
        title = "%s · %s · %d개" % (it["kr"], BAG.CAT_KR.get(it.get("cat"), it.get("cat") or ""), n)
        warn = BX.HOLD_EVO_NOTE if it["id"] in self.evo_items else None
        return title, natural(it.get("desc") or ""), warn, it["id"]

    def _band_tw(self, W):
        return W - U.h(14) - U.h(52) - U.h(14) - U.h(16)

    def _band_need(self, cv, W):
        """보라 띠 높이 - 어느 도구를 가리켜도 띠 높이가 안 바뀌게 가장 긴 설명에 맞춘다."""
        if self._band_cache and self._band_cache[0] == W:
            return self._band_cache[1]
        s = U.h
        tw = self._band_tw(W)
        best = s(74)
        for it, n in (self._items or [(None, 0)]):
            title, body, warn, _icon = self._band_text(it, n)
            hh = K.text_height(cv, title, font(11), tw) + s(20)
            if body:
                hh += s(4) + K.text_height(cv, body, font(11), tw)
            if warn:
                hh += s(4) + K.text_height(cv, warn, font(10), tw)
            best = max(best, hh)
        self._band_cache = (W, best)
        return best

    def _paint_band(self, cv, W, y, BH):
        s = U.h
        it, n = self._current()
        title, body, warn, icon_id = self._band_text(it, n)
        cv.create_rectangle(0, y, W, y + BH, fill=PURPLE, outline="", tags=T)
        bs = s(52)
        ix, iy = s(14), y + (BH - bs) // 2
        K.rrect(cv, ix, iy, ix + bs, iy + bs, 8, fill=WHITE, tags=T)
        ph = item_icons.photo(icon_id, 32) if icon_id else None
        if ph is not None:
            cv.create_image(ix + bs // 2, iy + bs // 2, image=ph, tags=T)
        tx, tw = ix + bs + s(14), self._band_tw(W)
        th = K.text_height(cv, title, font(11), tw)
        wh = (K.text_height(cv, warn, font(10), tw) + s(4)) if warn else 0
        if body:
            # 띠가 창보다 클 수는 없다 - 넘치는 설명은 끝을 …로 줄인다
            lh = K.tkfont_of(cv, font(11)).metrics("linespace")
            body = _clamp(cv, body, font(11), tw, max(1, (BH - s(20) - th - s(4) - wh) // max(1, lh)))
        bh = (s(4) + K.text_height(cv, body, font(11), tw)) if body else 0
        # 띠 높이는 가장 긴 설명에 맞춘 것이다 - 짧은 설명은 띠 가운데에 둔다
        ty = y + max(s(10), (BH - th - bh - wh) // 2)
        K.text(cv, tx, ty, title, font(11), fill=PURPLE_EM, tags=T, width=tw)
        ty += th
        if body:
            K.text(cv, tx, ty + s(4), body, font(11), fill=WHITE, tags=T)
            ty += bh
        if warn:
            K.text(cv, tx, ty + s(4), warn, font(10), fill=HOLD_WARN, tags=T, width=tw)
