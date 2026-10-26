# -*- coding: utf-8 -*-
"""DP 테마 - 프렌들리숍 (v2).

DP 의 프렌들리숍처럼 파란 가게 · 소지금 · 분류 메뉴(빨간 ▶ 커서) · 흰 목록 · 보라 설명 띠 · 개수 · 글상자를 두되,
줄무늬 · 테두리 글씨 · 겹친 테두리는 걷고 한 겹의 흰 판으로 단순하게 했다.

    ┌ 프렌들리숍 [그림] ┐┌ 찾기 [        ]                        12개 [새로고침] ┐
    │ 소지금  12,000원   ││  도구        등급   사는 값  파는 값  보유                │
    │ ▶ 전체            ││ ▶ [그림] 이름   귀함   8,000원  4,000원  × 3             │
    │   지닌 도구        │└───────────────────────────────────────────────────────────┘
    │   …               │┌ 보라 설명 띠 (그림 · 이름 · 등급 · 효과 · 덧말) ────────────┐
    │ 돈 버는 법 한 줄    ││ [− ×01 +] [1][10][99]   사면 ○원 · 팔면 ○원   [사기][팔기] │
    └───────────────────┘└ 글상자 ────────────────────────────────────────────────────┘

목록 줄 높이 · 보이는 줄 수는 기본 상점 이상이다 (기본 30 → 같은 30, 바닥을 한 줄로 줄여 줄이 더 보인다).
그림은 직접 그리지 않는다 - 가게 · 소지금은 본가 도구 그림(poke_icons.py), 도구는 앱의 도구 그림. -/+ 는 글자.
동작은 기본 상점(ui_shop.ShopWindow)의 것을 그대로 쓴다 - 값 · 잔고 · 가방은 서버가 준 대로, 사고팔기도 서버가 정한다.
"""
import tkinter as tk

from common.korean import natural

from ... import item_icons
from ... import ui_common as U
from ... import ui_shop as SH
from . import CUR, DIM, FAINT, INK, INK2, LINE, LINE_D, SEL, SEP, TAGC_D, WIN_BG, font, tone
from . import poke_icons
from . import kit as K
from . import PURPLE, PURPLE_HI, PURPLE_LO, PURPLE_EM, PURPLE_SH
from .scene import Band, Scene, T

RARE = {"common": "#6a6a74", "uncommon": "#2c8a3c", "rare": "#2860c0", "epic": "#8a4ad0",
        "legendary": "#c06810"}
LW_PX = 230                  # 왼쪽 기둥 폭
BOT_PX = 84                  # 아래 (개수 줄 + 글상자)
PAD = 12


class ShopWindow(Scene, Band, SH.ShopWindow):

    def _build(self):
        self._sub = ""
        self._shown = []
        self.ROW_H = U.h(31)              # 기본 상점의 줄 높이(30 + 줄 사이 금 1)와 같다
        self._scene_init()
        self.q = tk.StringVar()
        self.find_box = K.entry(self.cv, self.q, width=12)
        self.q.trace_add("write", lambda *_a: self.render())
        self.vl = K.VList(self.cv, "#ffffff", self._draw_row)
        self.vl.on_click = lambda it, *_a: self.select(it["id"])
        self.btn_buy = K.CButton(self.cv, "사기", self.do_buy, "blue", font(13))
        self.btn_sell = K.CButton(self.cv, "팔기", self.do_sell, "gray", font(12))
        self.btn_reload = K.CButton(self.cv, "새로고침", self.reload, "gray", font(9))
        self.btn_q = [K.CButton(self.cv, str(n), (lambda v=n: self.set_qty(v)), "gray", font(10))
                      for n in (1, 10, 99)]
        self._hand("cat", "qm", "qp")
        self.cv.tag_bind("qm", "<Button-1>", lambda _e: self.add_qty(-1))
        self.cv.tag_bind("qp", "<Button-1>", lambda _e: self.add_qty(1))

    # ---------------- 기본 상점의 칠하는 자리 ----------------
    def say(self, msg, color=U.GOOD):
        self._say(natural(msg or ""), color if color in (U.DANGER, U.GOOD) else None)

    def _paint_sub(self, text):
        self._sub = text
        self._soon()

    def _paint_cats(self):
        self._soon()

    def _paint_cat_counts(self):
        self._soon()

    def _show_items(self, shown, keep):
        self._shown = list(shown)
        self.vl.set([(self.ROW_H, it) for it in shown], keep=keep)
        self._soon()

    def _repaint_rows(self):
        self.vl.refresh()
        idx = next((i for i, it in enumerate(self._shown) if it["id"] == self.sel), None)
        if idx is not None:
            self.vl.see(idx)

    def _clear_detail(self):
        self._paint_buttons()
        self._soon()

    def show_detail(self):
        self._paint_buttons()
        self._soon()

    def _paint_money(self):
        self._soon()

    def _paint_totals(self):
        self._soon()

    def shown_rows(self):
        return [(it["id"], None) for it in self.vl.visible()]

    # ---------------- 목록 한 줄 ----------------
    def _cols(self, w):
        """(이름 x, 등급 가운데, 사는 값 오른쪽, 파는 값 오른쪽, 보유 오른쪽)."""
        return (U.h(42), w - U.h(340), w - U.h(236), w - U.h(124), w - U.h(14))

    def _draw_row(self, cv, it, x, y, w, h, tags, hover=None):
        sel = it["id"] == self.sel
        if sel:
            cv.create_rectangle(x, y, x + w, y + h, fill=SEL, outline="", tags=tags)
        elif hover is not None:
            cv.create_rectangle(x, y, x + w, y + h, fill="#f4f7fb", outline="", tags=tags)
        cv.create_line(x, y + h - 1, x + w, y + h - 1, fill=SEP, tags=tags)
        m = y + h // 2
        if sel:
            K.cursor(cv, x + U.h(6), m, size=U.h(5), tags=tags)
        ph = item_icons.photo(it["id"], SH.ICON)
        if ph is not None:
            cv.create_image(x + U.h(26), m, image=ph, tags=tags)
        cols = self._cols(w)
        K.text(cv, cols[0] + U.h(8), m, it.get("kr", it["id"]), font(11), anchor="w", tags=tags)
        cv.create_text(cols[1], m, text=SH.RARITY_KR.get(it.get("rarity"), "-"),
                       fill=RARE.get(it.get("rarity"), DIM), font=font(10), anchor="center", tags=tags)
        buyable = bool(it.get("buyable")) and int(it.get("cost") or 0) > 0
        cv.create_text(cols[2], m, text=(SH.won(it.get("cost")) + "원") if buyable else "안 판다",
                       fill=INK if buyable else FAINT, font=font(10), anchor="e", tags=tags)
        sell = int(it.get("sell") or 0)
        cv.create_text(cols[3], m, text=(SH.won(sell) + "원") if sell else "—", fill=INK2 if sell else FAINT,
                       font=font(10), anchor="e", tags=tags)
        n = int(self.bag.get(it["id"], 0) or 0)
        cv.create_text(cols[4], m, text=("× %d" % n) if n else "—", fill="#c06810" if n else FAINT,
                       font=font(10), anchor="e", tags=tags)
        if sel:
            cv.create_rectangle(x, y, x + w - 1, y + h - 1, outline=CUR, width=2, tags=tags)

    # ---------------- 보라 띠 ----------------
    def _band_content(self):
        it = self.current()
        if not it:
            return "도구를 고르세요", "목록에서 도구를 고르면 설명이 여기에 나옵니다.", None
        cat = dict(SH.CATS).get(it.get("cat"), it.get("cat", ""))
        title = "%s · %s · %s" % (it.get("kr", it["id"]), SH.RARITY_KR.get(it.get("rarity"), "등급 없음"), cat)
        body = SH.effect_text(it)
        note = SH.effect_note(it)
        if note:
            body += "\n" + note

        def art(cv, x, y, s):
            ph = item_icons.photo(it["id"], 32)
            if ph is not None:
                cv.create_image(x + s // 2, y + s // 2, image=ph, tags=T)
        return title, natural(body), art

    PRICE_W = 190                       # 보라 띠 오른쪽의 값 상자 폭

    def _price_lines(self):
        """값 상자의 줄들 [(글, 빨강인가)] - 개수를 바꾸면 따라 바뀐다 (가진 개수는 목록의 '보유' 칸)."""
        it = self.current()
        if not it:
            return []
        out = []
        buyable = bool(it.get("buyable")) and int(it.get("cost") or 0) > 0
        cost = int(it.get("cost") or 0) * self.qty
        if buyable:
            out.append(("사면 %s원" % SH.won(cost), False))
        if int(it.get("sell") or 0):
            out.append(("팔면 %s원" % SH.won(int(it["sell"]) * self.qty), False))
        if not out:
            out.append(("사고팔 수 없는 물건", False))
        if buyable and cost > self.money:
            out.append(("%s원 모자랍니다" % SH.won(cost - self.money), True))
        return out

    def _band_height(self, cv, x0, W, H):
        """보라 띠 높이 - 그림 칸(52)이 들어가는 만큼까지 줄여 목록에 자리를 준다 (scene.Band 의 최소 74 보다 낮게)."""
        tw = (W - x0) - U.h(96) - U.h(self.PRICE_W)
        title, body, _art = self._band_content()
        th = K.text_height(cv, title, font(11), tw) + U.h(4) + K.text_height(cv, body, font(11), tw)
        lh = K.tkfont_of(cv, font(10)).metrics("linespace")
        box = len(self._price_lines()) * (lh + U.h(2)) + U.h(14)
        return max(U.h(66), min(int(H * 0.36), max(th + U.h(18), box + U.h(12))))

    def _paint_band(self, cv, x0, W, y, BH):
        """보라 띠: 그림 · 이름 · 효과 + 오른쪽에 값 상자 (사면 · 팔면 · 모자란 돈)."""
        pw = U.h(self.PRICE_W)
        tw = (W - x0) - U.h(96) - pw
        title, body, art = self._band_content()
        cv.create_rectangle(x0, y, W, y + BH, fill=PURPLE, outline="", tags=T)
        cv.create_rectangle(x0, y, W, y + 3, fill=PURPLE_HI, outline="", tags=T)
        cv.create_rectangle(x0, y + BH - 3, W, y + BH, fill=PURPLE_LO, outline="", tags=T)
        s = U.h(52)
        ix, iy = x0 + U.h(14), y + (BH - s) // 2
        K.rrect(cv, ix, iy, ix + s, iy + s, 8, fill="#ffffff", outline="#a2a2b2", width=2, tags=T)
        if art is not None:
            art(cv, ix, iy, s)
        tx = ix + s + U.h(14)
        ty = y + U.h(10)
        _a, t1 = K.text(cv, tx, ty, title, font(11), fill=PURPLE_EM, shadow=PURPLE_SH, tags=T, width=tw)
        b = cv.bbox(t1)
        K.text(cv, tx, (b[3] if b else ty + U.h(18)) + U.h(4), body, font(11), fill="#ffffff", shadow=PURPLE_SH,
               tags=T, width=tw)
        lines = self._price_lines()
        if lines:
            lh = K.tkfont_of(cv, font(10)).metrics("linespace") + U.h(2)
            bh = len(lines) * lh + U.h(14)
            bx2 = W - U.h(12)
            by1 = y + (BH - bh) // 2
            K.rrect(cv, bx2 - pw + U.h(12), by1, bx2, by1 + bh, 8, fill="#ffffff", outline="#a2a2b2", width=2,
                    tags=T)
            for i, (txt, red) in enumerate(lines):
                cv.create_text(bx2 - U.h(10), by1 + U.h(7) + i * lh + lh // 2, text=txt,
                               fill="#d02828" if red else INK, font=font(10), anchor="e", tags=T)

    # ---------------- 판 전체 ----------------
    def _paint(self):
        self._job = None
        cv = self.cv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 200 or H < 200:
            return
        cv.delete("scene")
        self._msg_ids = None
        cv.create_rectangle(0, 0, W, H, fill=WIN_BG, outline="", tags=T)
        LW = U.h(LW_PX)
        self._paint_left(cv, LW, H)
        x0 = LW
        BH = self._band_height(cv, x0, W, H)
        LH = max(U.h(200), H - U.h(BOT_PX) - BH)
        self._paint_list(cv, x0, W, LH)
        self._paint_band(cv, x0, W, LH, BH)
        self._paint_qty(cv, x0, W, LH + BH, H)

    def _paint_left(self, cv, LW, H):
        pad = U.h(PAD)
        x1, x2 = pad, LW - pad
        y = pad
        # 가게 이름 + 파는 값 비율
        sub = self._sub or "도구를 사고팝니다"
        th = K.text_height(cv, sub, font(9), x2 - x1 - U.h(24))
        ih = U.h(24)
        sh = U.h(12) + ih + U.h(6) + th + U.h(12)
        K.panel(cv, x1, y, x2, y + sh, tags=T)
        cv.create_image(x1 + U.h(12), y + U.h(12) + ih // 2, image=poke_icons.photo("coin-case"), anchor="w",
                        tags=T)
        K.text(cv, x1 + U.h(12) + ih + U.h(8), y + U.h(12) + ih // 2, "프렌들리숍", font(12), anchor="w", tags=T)
        K.text(cv, x1 + U.h(12), y + U.h(12) + ih + U.h(6), sub, font(9), fill=INK2, width=x2 - x1 - U.h(24),
               tags=T)
        y += sh + U.h(8)
        # 소지금
        mh = U.h(56)
        K.panel(cv, x1, y, x2, y + mh, tags=T)
        coin = poke_icons.photo("amulet-coin")
        cv.create_image(x1 + U.h(12), y + U.h(16), image=coin, anchor="w", tags=T)
        K.text(cv, x1 + U.h(12) + coin.width() + U.h(8), y + U.h(16), "소지금", font(10), fill=INK2, anchor="w", tags=T)
        K.text(cv, x2 - U.h(12), y + mh - U.h(16), SH.won(self.money) + "원", font(13), anchor="e", tags=T)
        y += mh + U.h(8)
        # 분류 메뉴
        rh = U.h(30)
        my2 = y + U.h(6) * 2 + rh * len(SH.CATS)
        K.panel(cv, x1, y, x2, my2, tags=T)
        ry = y + U.h(6)
        for key, label in SH.CATS:
            on = key == self.cat
            n = len(self.items) if key == "all" else len([i for i in self.items if i.get("cat") == key])
            tg = T + ("cat", "cat_" + key)
            if on:
                K.rrect(cv, x1 + U.h(4), ry, x2 - U.h(4), ry + rh, 5, fill=SEL, tags=tg)
                K.cursor(cv, x1 + U.h(10), ry + rh // 2, size=U.h(5), tags=tg)
            else:
                cv.create_rectangle(x1 + U.h(4), ry, x2 - U.h(4), ry + rh, fill="", outline="", tags=tg)
            cv.create_text(x1 + U.h(26), ry + rh // 2, text=label, fill=CUR if on else INK, font=font(11),
                           anchor="w", tags=tg)
            cv.create_text(x2 - U.h(14), ry + rh // 2, text=str(n), fill=INK2, font=font(9), anchor="e", tags=tg)
            cv.tag_bind("cat_" + key, "<Button-1>", lambda _e, k=key: self.set_cat(k))
            ry += rh
        y = my2 + U.h(10)
        # 돈 버는 법
        if H - y > U.h(80):
            w, _h = K.tag(cv, x1, y, "돈 버는 법", tags=T)
            K.text(cv, x1 + U.h(2), y + U.h(32),
                   "돈이 모자라면 가방에서 안 쓰는 도구를 팔아 보세요. 랜덤 대전에서 이겨도 돈이 들어옵니다.",
                   font(9), fill=INK2, width=x2 - x1 - U.h(4), tags=T)

    def _paint_list(self, cv, x0, W, LH):
        pad = U.h(PAD)
        px1, py1, px2, py2 = x0 + pad, U.h(8), W - pad, LH - U.h(6)
        K.panel(cv, px1, py1, px2, py2, tags=T)
        ix1, iy1, ix2, iy2 = px1 + U.h(12), py1 + U.h(8), px2 - U.h(10), py2 - U.h(4)
        th = U.h(26)
        K.text(cv, ix1, iy1 + th // 2, "찾기", font(10), anchor="w", tags=T)
        rw = self.btn_reload.want_width(U.h(16))
        self.btn_reload.layout(ix2 - rw, iy1, ix2, iy1 + th)
        cv.create_text(ix2 - rw - U.h(10), iy1 + th // 2, text="%d개" % len(self._shown), fill=INK2,
                       font=font(9), anchor="e", tags=T)
        ex = ix1 + U.h(40)
        self._place("find", self.find_box, ex, iy1, max(U.h(80), ix2 - rw - U.h(70) - ex), th)
        hy = iy1 + th + U.h(6)
        w = ix2 - ix1
        cols = self._cols(w - U.h(12))
        for label, cx, anchor in (("도구", cols[0] + U.h(8), "w"), ("등급", cols[1], "center"),
                                  ("사는 값", cols[2], "e"), ("파는 값", cols[3], "e"), ("보유", cols[4], "e")):
            cv.create_text(ix1 + cx, hy + U.h(7), text=label, fill=INK2, font=font(9), anchor=anchor, tags=T)
        cv.create_line(ix1, hy + U.h(17), ix2, hy + U.h(17), fill=LINE, tags=T)
        ly1 = hy + U.h(18)
        if self._shown:
            self._place("items", self.vl.frame, ix1, ly1, ix2 - ix1, iy2 - ly1)
        else:
            self._hide("items")
            K.text(cv, (ix1 + ix2) // 2, ly1 + U.h(40), "찾는 도구가 없습니다.", font(11), anchor="n", tags=T)

    def _qty_button(self, cv, x, y, w, h, name, tag):
        body, _hi, line, _ink = K.KINDS["gray"]
        K.rrect(cv, x, y, x + w, y + h, 6, fill=body, outline=line, width=1, tags=T + (tag,))
        cv.create_text(x + w // 2, y + h // 2, text="−" if name == "minus" else "+", fill=INK, font=font(14),
                       tags=T + (tag,))

    def _paint_qty(self, cv, x0, W, y1, H):
        """개수 · 값 · 사기/팔기 한 줄 + 글상자."""
        pad = U.h(PAD)
        bh = U.h(36)
        y = y1 + U.h(6)
        # 사기 · 팔기 자리를 먼저 잡는다
        sw = max(U.h(76), self.btn_sell.want_width(U.h(28)))
        bw = max(U.h(100), self.btn_buy.want_width(U.h(36)))
        sell_x1 = W - pad - sw
        buy_x1 = sell_x1 - U.h(8) - bw
        self.btn_sell.layout(sell_x1, y, W - pad, y + bh)
        self.btn_buy.layout(buy_x1, y, sell_x1 - U.h(8), y + bh)
        # 개수 (− ×01 +) 와 빠른 개수
        x = x0 + pad
        mb = U.h(34)
        self._qty_button(cv, x, y + U.h(2), mb, bh - U.h(4), "minus", "qm")
        cw = U.h(68)
        K.panel(cv, x + mb + U.h(4), y + U.h(2), x + mb + U.h(4) + cw, y + bh - U.h(2), tags=T)
        K.text(cv, x + mb + U.h(4) + cw // 2, y + bh // 2, "× %02d" % self.qty if self.qty < 100 else "× %d" % self.qty,
               font(13), anchor="center", tags=T)
        self._qty_button(cv, x + mb + cw + U.h(8), y + U.h(2), mb, bh - U.h(4), "plus", "qp")
        x += mb + cw + U.h(8) + mb + U.h(12)
        for b in self.btn_q:
            w = max(U.h(34), b.want_width(U.h(18)))
            b.layout(x, y + U.h(2), x + w, y + bh - U.h(2))
            x += w + U.h(6)
        # 글상자
        my1 = y + bh + U.h(6)
        self._msg_ids = (None, K.msgbox(cv, x0 + pad, my1, W - pad, H - U.h(6), self.msg[0],
                                        tone(self.msg[1]) if self.msg[1] else None, tags=T))
