# -*- coding: utf-8 -*-
"""DP 테마의 여러 개 팔기 창 (v2) - DP 상점의 '팔기' 화면처럼, 단순하게.

    안내 한 줄 + [전부 고르기] [고른 것 지우기]
    ┌ 흰 판 (굴러간다) ───────────────────────────┐
    │ ▶ [도구 그림] 별가루      [−] ×03 [+] [전부]  │   고른 줄은 크림빛 + 빨간 ▶ 커서
    │               3개 있음 · 개당 1,000원         │
    └──────────────────────────────────────────────┘
    합계 / 가진 돈                       [닫기] [팔기]

v2: 줄무늬 · 겹친 테두리 · 테두리 글씨를 걷고, 흰 판 한 겹에 줄 한 켜씩. 줄 높이 · 창 크기는 기본 창과 같다
(기본 줄 44 + 틈 2). −/+ 는 글자.
고르기 · 합계 · 답 · 창 크기는 기본 창(ui_sell.SellMany) 그대로다 - 짓는 고리(_build)와 칠하는 고리(_paint)만 바꾼다.
줄을 누르면 하나 올라간다 (기본과 같다).
"""
import tkinter as tk

from ... import item_icons
from ... import ui_common as U
from ... import ui_sell as S
from . import CUR, DIM, FAINT, INK, INK2, LINE, SEL, SEP, WHITE, font, tone
from . import dialogs as D
from . import kit as K

ROW = 44                      # 기본 창의 줄 높이와 같다
BTN_H = 28


class _Line(object):
    """합계 · 가진 돈 글 - configure(text=, fg=) 를 받고 바뀌면 제 자리만 다시 그리게 한다."""

    def __init__(self, redraw, fg=INK):
        self.text = ""
        self.fg = fg
        self._redraw = redraw

    def configure(self, text=None, fg=None, **_kw):
        if text is not None:
            self.text = str(text)
        if fg is not None:
            self.fg = fg
        self._redraw()

    config = configure

    def cget(self, key):
        return {"text": self.text, "fg": self.fg, "foreground": self.fg}.get(key)


def _geo(w):
    """줄 오른쪽의 칸들 (− 칸 · 개수 · + 칸 · 전부 칸)의 가로 자리."""
    s = U.h
    r = w - s(10)
    allb = (r - s(44), r)
    up = (allb[0] - s(6) - s(28), allb[0] - s(6))
    cnt = (up[0] - s(4) - s(46), up[0] - s(4))
    dn = (cnt[0] - s(4) - s(28), cnt[0] - s(4))
    return dn, cnt, up, allb


class SellMany(S.SellMany):
    # ---------------- 짓기 ----------------
    def _build(self):
        s = U.h
        win = self.win
        win.configure(bg=D.BODY, highlightthickness=0)
        U.dialog_bar(win, "여러 개 팔기")
        body = tk.Frame(win, bg=D.BODY)
        body.pack(fill="both", expand=True, padx=D.PAD, pady=(s(12), s(12)))

        # 아래 (합계 + 단추) - 먼저 담아야 굴러가는 판이 자리를 다 먹지 않는다
        self.total = _Line(self._draw_foot)
        self.hint = _Line(self._draw_foot, INK2)
        lh1 = K.tkfont_of(win, font(12)).metrics("linespace")
        lh2 = K.tkfont_of(win, font(9)).metrics("linespace")
        self._foot_h = max(s(40), lh1 + s(4) + lh2) + s(2)
        self.foot = tk.Canvas(body, bg=D.BODY, highlightthickness=0, bd=0, height=self._foot_h)
        self.foot.pack(side="bottom", fill="x", pady=(s(6), 0))
        self.ok_btn = K.CButton(self.foot, "팔기", self._ok, "red", font(12))
        self.cancel_btn = K.CButton(self.foot, "닫기", self._cancel, "gray", font(12))
        self.foot.bind("<Configure>", lambda _e: self._draw_foot())

        # 위 (안내 + 고르기 단추)
        self.head = tk.Canvas(body, bg=D.BODY, highlightthickness=0, bd=0, height=s(64))
        self.head.pack(side="top", fill="x")
        self.all_btn = K.CButton(self.head, "전부 고르기", self._all, "gray", font(10))
        self.none_btn = K.CButton(self.head, "고른 것 지우기", self._none, "gray", font(10))
        self.head.bind("<Configure>", lambda _e: self._draw_head())

        # 가운데 (흰 판 한 겹 안의 줄들)
        panel = tk.Frame(body, bg=WHITE, highlightthickness=1, highlightbackground=LINE, bd=0)
        panel.pack(side="top", fill="both", expand=True, pady=(s(6), 0))
        self.vl = K.VList(panel, WHITE, self._draw_row, on_click=self._click)
        self.vl.frame.pack(fill="both", expand=True, padx=s(1), pady=s(1))
        self.canvas = self.vl.cv
        self.box = self.vl.frame
        U.install_wheel(win)
        win.bind("<Escape>", lambda _e: self._cancel())
        if self.lines:
            for it, have, price in self.lines:
                self.rows[it["id"]] = (None, None, have, price)
            self._items = dict((it["id"], it) for it, _h, _p in self.lines)
            self.vl.set([(s(ROW), it["id"]) for it, _h, _p in self.lines], keep=False)
        else:
            self._items = {}
            self.vl.set([(s(ROW), None)], keep=False)

    # ---------------- 안내 · 아래쪽 ----------------
    def _draw_head(self):
        cv, s = self.head, U.h
        w = cv.winfo_width()
        if w <= 1:
            return
        cv.delete("all")
        msg = "팔 물건과 개수를 고르세요. 판 물건은 되돌릴 수 없습니다."
        th = K.text_height(cv, msg, font(10), w)
        K.text(cv, 0, 0, msg, font(10), fill=INK2, width=w)
        by = th + s(6)
        w1, w2 = self.all_btn.want_width(s(24)), self.none_btn.want_width(s(24))
        self.all_btn.layout(0, by, w1, by + s(BTN_H) + 2)
        self.none_btn.layout(w1 + s(8), by, w1 + s(8) + w2, by + s(BTN_H) + 2)
        want = by + s(BTN_H) + 4
        if int(cv.cget("height")) != want:
            cv.configure(height=want)

    def _layout_foot_buttons(self):
        cv, s = self.foot, U.h
        w = cv.winfo_width()
        if w <= 1:
            return
        h = self._foot_h
        y1 = (h - s(38)) // 2
        w1 = max(self.ok_btn.want_width(s(36)), s(110))
        w2 = max(self.cancel_btn.want_width(s(36)), s(80))
        self.ok_btn.layout(w - w1, y1, w, y1 + s(38))
        self.cancel_btn.layout(w - w1 - s(8) - w2, y1, w - w1 - s(8), y1 + s(38))

    def _draw_foot(self):
        self._draw_total()
        self._layout_foot_buttons()

    def _draw_total(self):
        cv, s = self.foot, U.h
        w = cv.winfo_width()
        if w <= 1:
            return
        cv.delete("tot")
        tg = ("tot",)
        room = max(s(80), w - s(110) - s(80) - s(40))        # 단추들 왼쪽
        lh1 = K.tkfont_of(cv, font(12)).metrics("linespace")
        K.text(cv, 0, s(2), self.total.text, font(12), fill=tone(self.total.fg), tags=tg, width=room)
        K.text(cv, 0, s(2) + lh1 + s(4), self.hint.text, font(9), fill=tone(self.hint.fg), tags=tg)

    # ---------------- 줄 ----------------
    def _draw_row(self, cv, iid, x, y, w, h, tags, hov):
        s = U.h
        if iid is None:
            K.text(cv, s(16), y + h // 2, "팔 수 있는 물건이 없습니다.", font(11), fill=DIM, anchor="w", tags=tags)
            return
        it = self._items[iid]
        _f, _c, have, price = self.rows[iid]
        n = self.pick.get(iid, 0)
        on = n > 0
        if on:
            cv.create_rectangle(x, y, x + w, y + h, fill=SEL, outline="", tags=tags)
        elif hov is not None:
            cv.create_rectangle(x, y, x + w, y + h, fill="#f4f7fb", outline="", tags=tags)
        cv.create_line(x, y + h - 1, x + w, y + h - 1, fill=SEP, tags=tags)
        cy = y + h // 2
        if on:
            K.cursor(cv, x + s(8), cy, tags=tags)
        left = x + s(24)
        ph = item_icons.photo(iid, 24)
        if ph is not None:
            cv.create_image(left, cy, image=ph, anchor="w", tags=tags)
        tx = left + (s(32) if ph is not None else 0)
        dn, cnt, up, allb = _geo(w)
        tw = max(s(40), dn[0] - s(8) - tx)
        name = K.wrap(cv, it["kr"], font(11), tw).split("\n")
        K.text(cv, tx, cy - s(2), name[0] + ("…" if len(name) > 1 else ""), font(11),
               fill=INK, anchor="sw", tags=tags)
        K.text(cv, tx, cy + s(2), "%d개 있음 · 개당 %s원" % (have, S.won(price)), font(9), fill=INK2,
               anchor="nw", tags=tags, width=tw)
        by1, by2 = cy - s(BTN_H) // 2, cy + s(BTN_H) // 2
        for box, name, ok in ((dn, "minus", n > 0), (up, "plus", n < have)):
            self._flat(cv, box, by1, by2, ok, tags)
            cv.create_text((box[0] + box[1]) // 2, cy, text="−" if name == "minus" else "+",
                           fill=INK if ok else FAINT, font=font(14), tags=tags)
        K.panel(cv, cnt[0], by1, cnt[1], by2, tags=tags)
        K.text(cv, (cnt[0] + cnt[1]) // 2, cy, "×%02d" % n, font(11), fill=CUR if on else DIM, anchor="center",
               tags=tags)
        ok = n < have
        self._flat(cv, allb, by1, by2, ok, tags)
        cv.create_text((allb[0] + allb[1]) // 2, cy, text="전부", fill=INK if ok else FAINT, font=font(9),
                       anchor="center", tags=tags)

    @staticmethod
    def _flat(cv, box, y1, y2, ok, tags):
        body, _hi, line, _ink = K.KINDS["gray" if ok else "off"]
        K.rrect(cv, box[0], y1, box[1], y2, 6, fill=body, outline=line, width=1, tags=tags)

    def _click(self, iid, x, _y, w):
        if iid is None:
            return
        dn, cnt, up, allb = _geo(w)
        if dn[0] <= x <= dn[1]:
            self._add(iid, -1)
        elif allb[0] <= x <= allb[1]:
            self._set(iid, None)
        else:
            self._add(iid, 1)       # + 나 줄 아무 데나 - 하나 올라간다 (기본과 같다)

    # ---------------- 칠하기 ----------------
    def _paint(self):
        total, pieces = 0, 0
        for iid, n in self.pick.items():
            total += self.rows[iid][3] * n
            pieces += n
        if pieces:
            self.total.configure(
                text="%d가지 %d개  ·  %s원" % (len(self.pick), pieces, S.won(total)), fg=U.ACCENT_TEXT)
        else:
            self.total.configure(text="고른 것이 없습니다.", fg=U.FG_DIM)
        self.hint.configure(text="가진 돈 %s원" % S.won(self.money))
        self.ok_btn.configure(text="팔기" if not pieces else "%s원에 팔기" % S.won(total))
        self._layout_foot_buttons()
        self.vl.refresh()
