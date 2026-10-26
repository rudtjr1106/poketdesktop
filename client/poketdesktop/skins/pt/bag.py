# -*- coding: utf-8 -*-
"""플라티나 테마 - 가방 (도구 칸). 시안 B 의 가방 그림 그대로:

    ┌ 머리 띠: 가방 · N종 모두 M개 ·············· [새로고침] [팔기] [여러 개 팔기] (500,000원) ┐
    │ 강철 바탕(점)                                                                                │
    │ ┌주머니┐ ┌ 옅은 판 ────────────────┐ ┌ 옅은 판: 보라 머리(그림 · 이름 · 분류 · 등급 · 개수) ┐ │
    │ │캡슐  │ │ (찾기  이름 일부      ) │ │ 설명                                                 │ │
    │ │단추가│ │ (이름|종류|등급|개수)   │ └──────────────────────────────────────────────────────┘ │
    │ │세로로│ │ 열매 · 3종              │ ┌ 옅은 판: 누구에게 쓸까? · (찾기) (기본|가나다순|레벨순) ┐ │
    │ │고른 것│ │ (● 오랭열매       ×5)  │ │ 포켓몬 줄 (고른 줄은 하늘색)                         │ │
    │ │하늘색│ │ ((● 먹다남은음식  ×1))  │ └──────────────────────────────────────────────────────┘ │
    │ └──────┘ └─────────────────────────┘ (               주황 캡슐  ○○ 쓰기               )     │

시안과 다른 것: 시안에는 없는 새로고침 · 팔기 · 여러 개 팔기 단추는 머리 띠 오른쪽(돈 캡슐 왼쪽)에 둔다
(DP 는 다이얼 아래에 있었다). 큰 단추 하나는 오른쪽 칸 아래에 칸 폭 가득 (가방 · 기술머신 공통의 틀).
'전체' 주머니와 '모든 주머니에서 찾기' 는 DP 처럼 그대로 있다.

동작은 DP 가방(skins/dp/bag.py) → 기본 가방(ui_bag.BagWindow) 그대로다 - 판을 그리는 자리만 바꾼다.
기술머신 칸(tms.py)도 이 틀(PtBag)을 쓴다.
"""
import tkinter as tk

from common.korean import natural

from ... import box_filter
from ... import item_icons
from ... import ui_bag as B
from ... import ui_common as U
from ..dp import bag as DPB
from ..dp import font, tone
from ..dp import kit as K
from ..dp.scene import POCKETS, T, mid_column
from . import CYAN_SOFT, DIM, FAINT, INK, ON_STEEL_DIM, PANEL, PURPLE, PURPLE_SH, PURPLE_TOP, STEEL, WHITE
from . import _pt as P

RARITY_KR = DPB.RARITY_KR
RARE = {"common": "#5f6b78", "uncommon": "#2e8a46", "rare": "#1f6fb0", "epic": "#7a48c8", "legendary": "#b85a10"}


class PtBag(object):
    """가방 · 기술머신 칸이 같이 쓰는 시안의 틀. 부르는 창이 정하는 것:

        _head_title()          머리 띠 제목 ('가방' · '기술머신')
        _line_text()           제목 옆 작은 글 (몇 종 · 몇 개)
        _lcd_text()            돈 캡슐 (돈 · 가진 수)
        _head_buttons()        머리 띠의 단추들 [Capsule] (오른쪽부터 놓는다)
        _pocket_now · _pocket_count · _pocket_click · _tm_badge   왼쪽 주머니
        _paint_mid(cv, x1, y1, x2, y2)     가운데 판 안
        _info()                (제목, 작은 줄, 설명, 그림 함수 또는 None)
        _who()                 (제목, 안내, 판 대신 글 또는 None, 끼우는 칸들)
        use_btn                아래 큰 단추
    """
    HEAD_PX = 46
    POCKET_PX = 86
    M = 10              # 바깥 여백 (pt)

    def _pt_init(self):
        """DP _build 가 만든 것을 시안 모양으로 바꿔 끼운다."""
        self.cv.configure(bg=STEEL)
        self.win.configure(bg=STEEL)
        self.find.box = P.Entry(self.cv, self.find.q, width=10)
        self.mons_vl.frame.configure(bg=PANEL)
        self.mons_vl.cv.configure(bg=PANEL)
        if self.mons_vl.sb is not None:
            self.mons_vl.sb.configure(bg=PANEL)
        self._who_hover = None

    def _list_bg(self, vl):
        vl.frame.configure(bg=PANEL)
        vl.cv.configure(bg=PANEL)
        if vl.sb is not None:
            vl.sb.configure(bg=PANEL)

    # ---------------- 판 전체 ----------------
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
        HEAD = s(self.HEAD_PX)
        P.steel(cv, 0, HEAD, W, H, tags=T)
        self._paint_head(cv, W, HEAD)
        m = s(self.M)
        top, bot = HEAD + m, H - m
        # 왼쪽 주머니 · 가운데 목록 판 · 오른쪽 (설명 판 + 누구에게 판 + 큰 단추)
        lx2 = m + s(self.POCKET_PX)
        self._paint_pockets(cv, m, top, lx2, bot)
        mx1 = lx2 + s(12)
        mx2 = mid_column(mx1, W - m) - s(6)
        P.panel(cv, mx1, top, mx2, bot, tags=T)
        self._paint_mid(cv, mx1 + s(12), top + s(12), mx2 - s(12), bot - s(8))
        rx1, rx2 = mx2 + s(10), W - m
        btn_h = s(44)
        by2 = bot
        by1 = by2 - btn_h
        self.use_btn.layout(rx1, by1, rx2, by2)
        ih = self._info_height(cv, rx2 - rx1, by1 - top)
        self._paint_info(cv, rx1, top, rx2, top + ih)
        self._paint_who(cv, rx1, top + ih + s(8), rx2, by1 - s(8))
        self._toast_box = (rx1, top, rx2, top + ih)
        self._paint_toast()

    # ---------------- 머리 띠 ----------------
    def _paint_head(self, cv, W, HEAD):
        s = U.h
        P.head_band(cv, 0, 0, W, HEAD, tags=T)
        ym = (HEAD - 3) // 2
        tid = P.band_title(cv, s(18), ym, self._head_title(), font(16), tags=T)
        b = cv.bbox(tid)
        lx = (b[2] if b else s(80)) + s(14)
        x2 = P.money(cv, W - s(18), ym, self._lcd_text(), font(12), tags=T) - s(12)
        bh = s(32)
        for btn in [x for x in self._head_buttons() if x is not None]:
            w = btn.want_width(s(30))
            btn.layout(x2 - w, ym - bh // 2, x2, ym + bh // 2)
            x2 -= w + s(8)
        line = self._line_text()
        if line and lx + K.tkfont_of(cv, font(10)).measure(line) <= x2 - s(6):
            cv.create_text(lx, ym, text=line, fill=ON_STEEL_DIM, font=font(10), anchor="w", tags=T)

    # ---------------- 왼쪽 주머니 (세로 캡슐) ----------------
    def _paint_pockets(self, cv, x1, y1, x2, y2):
        s = U.h
        n = len(POCKETS)
        gap = s(8)
        ph = int(min(s(54), (y2 - y1 - gap * (n - 1)) / float(n)))
        f10 = K.tkfont_of(cv, font(10))
        two = f10.metrics("linespace") * 2 + s(8) <= ph
        now = self._pocket_now()
        y = y1
        for key, label in POCKETS:
            on = key == now
            empty = key not in ("all", "tms") and self._pocket_count(key) == 0
            tg = T + ("ppk", "ppk_" + key)
            text = label if two else label.replace("\n", " ")
            if not two and f10.measure(text) > x2 - x1 - s(10):
                text = label
            P.capsule(cv, x1, y, x2, y + ph, "cyan" if on else "white", r=s(14), tags=tg)
            cv.create_text((x1 + x2) // 2, y + ph // 2, text=text, font=font(10), justify="center",
                           fill=P.LOOKS["cyan"][3] if on else (FAINT if empty else INK), anchor="center", tags=tg)
            if key == "tms" and getattr(self, "_tm_badge", False):
                d = s(5)
                bx, by = x2 - s(8), y + s(8)
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill="#ff4040", outline=WHITE, width=2, tags=tg)
            cv.tag_bind("ppk_" + key, "<Button-1>", lambda _e, k=key: self._pocket_click(k))
            y += ph + gap
        self._hand("ppk")

    # ---------------- 오른쪽 위: 설명 판 (보라 머리) ----------------
    HEAD_H_PX = 62

    def _head_h(self):
        """보라 머리 높이 - 누구에게 판에 능력 · 노력치 칸이 끼면 낮춘다 (포켓몬 줄 자리를 지킨다)."""
        return U.h(50 if self._who()[3] else self.HEAD_H_PX)

    def _info_height(self, cv, width, avail):
        s = U.h
        title, sub, desc, _art = self._info()
        th = K.text_height(cv, desc, font(11), width - s(36)) if desc else 0
        want = self._head_h() + s(6) + th + s(20)
        cap = 0.30 if self._who()[3] else 0.36            # 능력 · 노력치 칸이 끼면 설명 판을 더 낮게
        return int(max(s(96), min(avail * cap, want)))

    def _paint_info(self, cv, x1, y1, x2, y2):
        s = U.h
        title, sub, desc, art = self._info()
        P.panel(cv, x1, y1, x2, y2, tags=T)
        hh = self._head_h()
        r = s(16) - 3
        P.grad_round(cv, x1 + 3, y1 + 3, x2 - 3, y1 + 3 + hh + r, r, PURPLE_TOP, PURPLE, tags=T)
        cv.create_rectangle(x1 + 3, y1 + 3 + hh, x2 - 3, y1 + 3 + hh + r + 1, fill=PANEL, outline="", tags=T)
        cv.create_line(x1 + 3, y1 + 3 + hh, x2 - 3, y1 + 3 + hh, fill="#4f3cc0", width=2, tags=T)
        isz = min(s(52), hh - s(12))
        ix, iy = x1 + s(16), y1 + 3 + (hh - isz) // 2
        P.rpoly(cv, ix, iy, ix + isz, iy + isz, s(12), fill=P.mix(PURPLE_TOP, WHITE, 0.22), tags=T)
        if art is not None:
            art(cv, ix, iy, isz)
        tx = ix + isz + s(14)
        tw = x2 - s(14) - tx
        spec = font(15)
        t = title
        f = K.tkfont_of(cv, spec)
        while len(t) > 1 and f.measure(t) > tw:
            t = t[:-1]
        if t != title:
            t = t[:-1] + "…"
        ty = y1 + 3 + hh // 2 - (s(10) if sub else 0)
        cv.create_text(tx, ty + 2, text=t, fill=PURPLE_SH, font=spec, anchor="w", tags=T)
        cv.create_text(tx, ty, text=t, fill=WHITE, font=spec, anchor="w", tags=T)
        if sub:
            sub = K.wrap(cv, sub, font(9), tw).split("\n")[0]
            cv.create_text(tx, ty + s(20), text=sub, fill="#efeaff", font=font(9), anchor="w", tags=T)
        if desc:
            K.text(cv, x1 + s(18), y1 + 3 + hh + s(12), desc, font(11), fill=INK, width=x2 - x1 - s(36), tags=T)

    # ---------------- 오른쪽 가운데: 누구에게 판 ----------------
    def _paint_who(self, cv, x1, y1, x2, y2):
        s = U.h
        title, hint, note, boxes = self._who()
        P.panel(cv, x1, y1, x2, y2, tags=T)
        ix1, ix2 = x1 + s(14), x2 - s(14)
        hy = y1 + s(10)
        cv.create_text(ix1, hy, text=title, fill=INK, font=font(12), anchor="nw", tags=T)
        fy = hy + s(24)
        if hint:
            tw = K.tkfont_of(cv, font(12)).measure(title)
            hw = K.tkfont_of(cv, font(9)).measure(hint)
            if ix1 + tw + s(16) + hw <= ix2:
                cv.create_text(ix2, hy + s(3), text=hint, fill=DIM, font=font(9), anchor="ne", tags=T)
            else:
                _a, hid = K.text(cv, ix1, fy - s(2), hint, font(9), fill=DIM, width=ix2 - ix1, tags=T)
                b = cv.bbox(hid)
                fy = (b[3] if b else fy + s(16)) + s(6)
        fh = s(28)
        if note is not None and not self.find.searching():
            self._hide("mfind")
            self._paint_who_rest(cv, x1, fy, x2, y2, note, boxes)
            return
        sorts = box_filter.PICK_SORTS
        sw = P.seg_width(cv, sorts, font(9), pad=U.h(12))
        cnt_w = s(60) if self.find.count else 0
        if ix2 - sw - s(10) - cnt_w - ix1 >= s(76):            # 한 줄에 다 든다
            P.seg(cv, ix2 - sw, fy, sw, fh, sorts, self.find.sort, "msrt", self.find.pick_sort, spec=font(9))
            ex2 = ix2 - sw - s(10)
            y = fy + fh + s(6)
        else:                                                   # 고르기 줄은 아래로
            ex2 = ix2
            P.seg(cv, ix1, fy + fh + s(6), min(ix2 - ix1, max(sw, s(200))), fh, sorts, self.find.sort, "msrt",
                  self.find.pick_sort, spec=font(9))
            y = fy + 2 * fh + s(12)
        self._hand("msrt")
        if self.find.count:
            cv.create_text(ex2 - s(4), fy + fh // 2, text=self.find.count, fill=DIM, font=font(9), anchor="e",
                           tags=T)
            ex2 -= cnt_w
        P.entry_capsule(self, cv, "mfind", self.find.box, ix1, fy, ex2 - ix1, fh,
                        label="포켓몬 찾기" if ex2 - ix1 >= s(190) else "찾기")
        self._paint_who_rest(cv, x1, y, x2, y2, note, boxes)

    def _paint_who_rest(self, cv, x1, y, x2, y2, note, boxes):
        s = U.h
        for h, draw in boxes:
            draw(cv, x1 + s(12), y, x2 - s(12))
            y += h + s(6)
        lx1, lx2 = x1 + s(8), x2 - s(8)
        if note is None:
            cols = 2 if (lx2 - lx1) >= s(440) else 1
            if cols != self._plate_cols:
                self._plate_cols = cols
                self._plates_set(self._plate_rows_src, keep=True)
            self._place("mons", self.mons_vl.frame, lx1, y, lx2 - lx1, max(s(40), y2 - y - s(8)))
        else:
            self._hide("mons")
            K.text(cv, (lx1 + lx2) // 2, y + s(18), note, font(11), fill=DIM, anchor="n", justify="center",
                   width=lx2 - lx1 - 40, tags=T)

    # ---------------- 포켓몬 줄 (시안의 .who .mon) ----------------
    def _draw_plate(self, cv, m, x1, y1, x2, y2, tags, hov):
        s = U.h
        info = self._plate_info(m)
        blocked, good = info.get("blocked"), info.get("good")
        sel = m.get("id") == self.mon_id
        r = s(12)
        # 시안 .who .mon: 테 없는 줄, 고른 줄만 옅은 하늘색 바탕 (+ 하늘색 가는 테 - 고른 것이 또렷하게)
        fill = CYAN_SOFT if sel else ("#e2f3e6" if good else ("#f6f8fa" if hov and not blocked else ""))
        if fill:
            P.rpoly(cv, x1 + 2, y1 + 2, x2 - 2, y2 - 2, r, fill=fill, outline=P.CYAN if sel else "",
                    width=2, tags=tags)
        mid = (y1 + y2) // 2
        ph = info.get("photo")
        if ph is not None:
            cv.create_image(x1 + s(28), mid, image=ph, tags=tags)
        name = info.get("name") or "?"
        if info.get("shiny"):
            name = "★ " + name
        tx = x1 + s(54)
        ink = FAINT if blocked else INK
        cv.create_text(tx, y1 + s(8), text=name, fill="#9a6a00" if info.get("shiny") else ink, font=font(11),
                       anchor="nw", tags=tags)
        cv.create_text(tx, y2 - s(8), text=info.get("sub") or "", fill=DIM if not blocked else FAINT, font=font(9),
                       anchor="sw", tags=tags)
        if info.get("note"):
            f9 = K.tkfont_of(cv, font(9))
            nw = f9.measure(info["note"])
            low = tx + f9.measure(info.get("sub") or "") + s(10) <= x2 - s(12) - nw
            col = tone(info.get("color") or U.FG_DIM)
            cv.create_text(x2 - s(12), (y2 - s(8)) if low else (y1 + s(9)), text=info["note"], fill=col, font=font(9),
                           anchor="se" if low else "ne", tags=tags)


class BagWindow(PtBag, DPB.BagWindow):

    def _build(self):
        DPB.BagWindow._build(self)
        self.item_find = P.Entry(self.cv, self.item_q, width=10)
        self._pt_init()
        self._list_bg(self.items_vl)
        self.ROW_H = U.h(30)             # DP · 기술머신 줄과 같은 높이 (목록 줄 수를 지킨다)
        self.HEAD_H = U.h(22)
        P.to_capsule(self.use_btn, "orange")
        P.to_capsule(self.sell_btn, "white")
        P.to_capsule(self.sell_many_btn, "white")
        P.to_capsule(self.close_btn, "white")
        self.use_btn.spec = font(14)
        for b in (self.sell_btn, self.sell_many_btn):
            b.spec = font(10)
        self._reload_btn = P.Capsule(self.cv, "새로고침", self.reload, "gray", font(10))

    # ---------------- 머리 띠 ----------------
    def _head_title(self):
        return "가방"

    def _head_buttons(self):
        return [self.sell_many_btn, self.sell_btn, self._reload_btn]

    # ---------------- 가운데 판 ----------------
    def _paint_mid(self, cv, ix1, iy1, ix2, iy2):
        s = U.h
        th = s(30)
        label = "찾기" if not self.item_q.get().strip() else "모든 주머니에서 찾기"
        sw = P.seg_width(cv, B.ITEM_SORTS, font(10), pad=U.h(16))
        if ix2 - ix1 - sw - s(8) >= s(140):            # 찾기 · 줄 세우기가 한 줄에 든다 (목록 줄을 아낀다)
            P.entry_capsule(self, cv, "ifind", self.item_find, ix1, iy1, ix2 - ix1 - sw - s(8), th, label=label)
            P.seg(cv, ix2 - sw, iy1, sw, th, B.ITEM_SORTS, self.item_sort, "srt", self.set_item_sort,
                  spec=font(10))
            ly1 = iy1 + th + s(6)
        else:                                          # 좁으면 시안처럼 두 줄
            P.entry_capsule(self, cv, "ifind", self.item_find, ix1, iy1, ix2 - ix1, th, label=label)
            sy = iy1 + th + s(6)
            P.seg(cv, ix1, sy, ix2 - ix1, th, B.ITEM_SORTS, self.item_sort, "srt", self.set_item_sort,
                  spec=font(10))
            ly1 = sy + th + s(6)
        self._hand("srt")
        if self._items_state == "list":
            self._place("items", self.items_vl.frame, ix1 - s(4), ly1, ix2 - ix1 + s(8), iy2 - ly1)
        else:
            self._hide("items")
            note = self._items_note if self._items_state == "nomatch" else \
                "가방이 비어 있다.\n야생 포켓몬을 잡거나 배틀에서 도구를 주울 수 있다."
            K.text(cv, (ix1 + ix2) // 2, ly1 + s(40), note, font(11), fill=DIM, anchor="n", justify="center",
                   width=ix2 - ix1 - 20, tags=T)

    def _draw_item_row(self, cv, data, x, y, w, h, tags, hover=None):
        s = U.h
        kind, val = data
        if kind == "head":
            cat, n = val[0], val[1]
            sub = val[2] if len(val) > 2 else None
            label = ("%s · %s · %d종" % (B.CAT_KR.get(cat, cat), sub, n)) if sub else \
                "%s · %d종" % (B.CAT_KR.get(cat, cat), n)
            m = y + h // 2 + s(2)
            cv.create_rectangle(x + s(10), m - 3, x + s(16), m + 3, fill=B.CAT_COLOR.get(cat, DIM), outline="",
                                tags=tags)
            cv.create_text(x + s(22), m, text=label, fill=DIM, font=font(9), anchor="w", tags=tags)
            return
        it = val
        usable = (it.get("effect") or {}).get("kind") in B.USABLE
        sel = it["id"] == self.item_id
        x1, y1, x2, y2 = x + s(5), y + s(2), x + w - s(5), y + h - s(2)
        P.row_capsule(cv, x1, y1, x2, y2, sel=sel, hover=hover is not None, tags=tags)
        m = (y1 + y2) // 2
        icon = item_icons.photo(it["id"], 20)
        ix = x1 + s(18)
        if icon is not None:
            cv.create_image(ix, m, image=icon, tags=tags)
        else:
            cv.create_rectangle(ix - 3, m - 3, ix + 3, m + 3, fill=B.CAT_COLOR.get(it.get("cat"), DIM), outline="",
                                tags=tags)
        fg = INK if usable else FAINT
        nid = cv.create_text(x1 + s(36), m, text=it["kr"], fill=fg, font=font(11), anchor="w", tags=tags)
        cx = x2 - s(14)
        cv.create_text(cx, m, text="×%d" % self.bag.get(it["id"], 0), fill=fg, font=font(11), anchor="e", tags=tags)
        rk = it.get("rarity")
        if rk in RARITY_KR:
            rx = cx - s(46)
            f = K.tkfont_of(cv, font(9))
            b = cv.bbox(nid)
            if not b or b[2] + s(10) <= rx - f.measure(RARITY_KR[rk]):
                cv.create_text(rx, m, text=RARITY_KR[rk], fill=RARE[rk] if usable else FAINT, font=font(9),
                               anchor="e", tags=tags)

    # ---------------- 오른쪽 ----------------
    def _info(self):
        it = self._item
        if not it:
            return ("도구를 고르세요", "",
                    "왼쪽에서 주머니를 고르고, 목록에서 도구를 고르면 여기에 설명이 뜬다.", None)
        bits = [B.CAT_KR.get(it["cat"], it["cat"])]
        if it.get("rarity") in RARITY_KR:
            bits.append(RARITY_KR[it["rarity"]] + " 등급")
        bits.append("%d개" % self.bag.get(it["id"], 0))

        def art(cv, x, y, sz):
            ph = item_icons.photo(it["id"], 32)
            if ph is not None:
                cv.create_image(x + sz // 2, y + sz // 2, image=ph, tags=T)
        return it["kr"], " · ".join(bits), natural(B.item_desc(it)), art

    def _who(self):
        it = self._item
        return ("누구에게 쓸까?", B.target_hint(it) if it else "", self._mon_note,
                self._boxes(self.cv, self._who_width()))

    def _who_width(self):
        try:
            W = self.cv.winfo_width()
        except tk.TclError:
            return 300
        s = U.h
        mx1 = s(self.M) + s(self.POCKET_PX) + s(12)
        mx2 = mid_column(mx1, W - s(self.M)) - s(6)
        return (W - s(self.M)) - (mx2 + s(12)) - s(24)

    # (DP 의 _band_content 를 부르는 곳이 남아 있으면 같은 것을 준다)
    def _band_content(self):
        title, sub, desc, art = self._info()
        return (title + (" · " + sub if sub else "")), desc, art
