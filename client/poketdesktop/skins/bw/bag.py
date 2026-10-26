# -*- coding: utf-8 -*-
"""블랙·화이트 테마 - 가방 (도구 칸). 시안 H 의 가방을 그대로 옮긴다:

    ┌ 가방   (지닌)(메가)(진화)(볼)(기술)…(새로)            [ 48,200원 ] ┐  ← 짙은 바탕 · 동그란 주머니 단추
    │                                                       460종 · 1380개 │     고른 주머니는 하늘빛 고리 + 번지는 빛
    │ ┌ 어두운 판 ─────────────┐ ┌ 어두운 판 ───────────────────────────┐ │
    │ │ 찾기 ________________ │ │ (◯) 먹다남은음식                       │ │  ← 하늘빛 고리 안에 도구 그림
    │ │ (이름)(종류)(등급)(개수)│ │     지닌 도구 · 영웅 · 1개             │ │
    │ │ 열매 · 3종             │ │ 지니게 하면 매 턴 끝에 …              │ │
    │ │  ● 오랭열매       ×5   │ └──────────────────────────────────────┘ │
    │ │ [● 먹다남은음식   ×1]  │  누구에게 쓸까?   찾기 · 줄 세우기       │
    │ │  …                     │  [리자몽 Lv.50][한카리아스 …]  (2열 카드)│
    │ └────────────────────────┘    [팔기] [여러 개 팔기]  (( 지니게 하기 ))│  ← 하늘빛 알약
    └───────────────────────────────────────────── C기어 고리 ─────────────┘

시안은 주머니를 위 줄에 둔다 - 주머니 11개 + 새로고침이 한 줄에 다 든다 (980 폭에서도). 그래서 DP 의 왼쪽
기둥 자리는 없고, 목록 판이 그만큼 넓다. 팔기 단추는 아래 줄의 큰 단추 왼쪽으로 옮겼다.

동작(주머니 고르기 · 찾기 · 줄 세우기 · 판 고르기 · 쓰기 · 팔기)은 DP 가방(skins/dp/bag.py)과 기본 가방 그대로다 -
여기서는 칠하는 것만 한다. 기술머신 칸(tms.py)도 같은 틀(BWBag)을 쓴다.
"""
import tkinter as tk

from common.korean import natural

from ... import item_icons
from ... import ui_bag as B
from ... import ui_common as U
from ..dp import font, tone
from ..dp import bag as DPB
from ..dp import kit as K
from ..dp.scene import POCKETS, T
from . import (BG, CARD, CYAN, CYAN_HI, CYAN_LO, DESC, DIMT, DOT, FAINT, GLOW_FAR, GO_INK, LINE, LINE_HI,
               PANEL, PANEL_HI, SEL, TEXT, mix)
from . import _art as A

RARE_KR = DPB.RARITY_KR
RING_OUT = mix(PANEL, CYAN, 0.4)            # 도구 그림 고리 바깥 줄 (시안 .ring 의 0 0 0 7px rgba(.4))


class BWButton(K.CButton):
    """시안의 알약 단추. kind: go (하늘빛, 짙은 글씨) · dark (어두운 판, 가는 테) · dark_cyan (하늘빛 글씨)."""

    LOOKS = {
        "go": (CYAN, CYAN_HI, CYAN_LO, GO_INK),
        "dark": (PANEL, PANEL_HI, LINE, TEXT),
        "dark_cyan": (PANEL, PANEL_HI, CYAN_LO, CYAN),
        "off": (CARD, CARD, PANEL_HI, "#5f666e"),
    }

    @classmethod
    def adopt(cls, btn, kind):
        """DP 가 만든 단추를 이 모양으로 (바인딩 · 동작은 그대로)."""
        btn.__class__ = cls
        btn.kind = kind
        return btn

    def _look(self):
        return self.LOOKS["off" if not self.enabled else self.kind]

    def draw(self):
        cv = self.cv
        cv.delete(self.tag)
        self._body_id = None
        self._shift = 0
        self._hover = self._down = False
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        body, _hi, line, ink = self._look()
        m = (self.tag, self.tag + "_m")
        self._body_id = K.rrect(cv, x1, y1, x2, y2, (y2 - y1) // 2, fill=body, outline=line, width=1, tags=m)
        cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=self.text, fill=ink, font=self.spec, anchor="center",
                       tags=m)
        self._state()

    def _state(self):
        if self._body_id is None:
            return
        body, hi, line, _ink = self._look()
        hov = self._hover and self.enabled
        try:
            self.cv.itemconfigure(self._body_id, fill=hi if hov else body,
                                  outline=(CYAN if self.kind != "go" else CYAN_HI) if hov else line)
            want = 1 if (self._down and self.enabled) else 0
            if want != self._shift:
                self.cv.move(self.tag + "_m", 0, want - self._shift)
                self._shift = want
        except tk.TclError:
            pass


class BWBag(object):
    """가방 · 기술머신 칸이 같이 쓰는 시안 H 의 판. 창이 정하는 것:

        _lcd_text() · _line_text() · _pocket_now() · _pocket_count(key) · _pocket_click(key) · _tm_badge
        _bw_list(cv, x1, y1, x2, y2)     왼쪽 목록 판 안
        _detail_content()                (이름, 한 줄, 설명, 그림 그리는 함수(cv, cx, cy) 또는 None)
        _bw_plates()                     (제목, 안내, 판 대신 띄울 글, 끼우는 칸)
        _bw_actions()                    아래 줄 단추 [BWButton] (오른쪽 끝이 큰 단추)
    """
    PLATE_PX = 54          # 카드 높이 (시안 .card 64 - 작은 창에서도 카드가 여섯 장은 보이게 조금 낮췄다)
    TOP_PX = 74            # 위 줄 (제목 · 주머니 · 돈)
    LIST_SHARE = 0.40      # 목록 판 폭 (시안 330 / 760 - 작은 창에서 카드가 두 줄로 서게 조금 좁혔다)
    LIST_MIN, LIST_MAX = 300, 520
    ACT_PX = 40            # 아래 큰 단추 높이

    def _bw_restyle(self):
        """DP 가 만든 입력칸 · 목록 바탕을 시안 것으로 (찾기 칸은 밑줄만 - 시안 .find)."""
        for box, bg in ((getattr(self, "item_find", None), PANEL), (self.find.box, CARD)):
            if box is None:
                continue
            try:
                if bg == PANEL:
                    box.configure(bg=bg, highlightthickness=0)
                else:
                    box.configure(bg=bg, highlightthickness=1, highlightbackground=LINE, highlightcolor=CYAN)
                box.entry.configure(bg=bg, fg=TEXT, insertbackground=TEXT)
                box.entry.bind("<FocusIn>", lambda _e, b=box: b.configure(highlightbackground=CYAN))
                box.entry.bind("<FocusOut>", lambda _e, b=box: b.configure(highlightbackground=LINE))
            except tk.TclError:
                pass
        self.mons_vl.cv.configure(bg=BG)
        self.mons_vl.frame.configure(bg=BG)

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
        m = s(14)
        A.backdrop(cv, 0, 0, W, H, tags=T)
        top = s(self.TOP_PX)
        self._paint_top(cv, W, top)
        lx2 = m + max(s(self.LIST_MIN), min(s(self.LIST_MAX), int(W * self.LIST_SHARE)))
        A.panel(cv, m, top, lx2, H - m, tags=T)
        self._bw_list(cv, m + s(12), top + s(10), lx2 - s(12), H - m - s(8))
        rx1, rx2 = lx2 + s(12), W - m
        dh = self._detail_height(cv, rx2 - rx1, H - top)
        self._bw_detail(cv, rx1, top, rx2, top + dh)
        ay2 = H - m
        ay1 = ay2 - s(self.ACT_PX)
        title, hint, note, boxes = self._bw_plates(rx2 - rx1 - s(24))
        self._paint_plates_area(cv, rx1 - s(8), rx2 + s(8), top + dh + s(6), ay1 - s(8), title, hint, note, boxes)
        self._paint_actions(cv, rx1, ay1, rx2, ay2)
        self._toast_box = (rx1, top, rx2, top + dh)
        self._paint_toast()

    # ---------------- 위 줄: 제목 · 동그란 주머니 단추 · 돈 ----------------
    def _paint_top(self, cv, W, top):
        s = U.h
        m = s(14)
        cv.create_text(s(20), top // 2, text="가방", fill=TEXT, font=font(16), anchor="w", tags=T)
        tw = K.tkfont_of(cv, font(16)).measure("가방")
        # 돈 알약 (시안 .money) + 그 밑에 종류 · 개수
        money = self._lcd_text()
        mw = K.tkfont_of(cv, font(13)).measure(money) + s(30)
        py1, py2 = s(12), s(42)
        A.pill(cv, W - m - mw, py1, W - m, py2, tags=T)
        cv.create_text(W - m - mw // 2, (py1 + py2) // 2, text=money, fill=TEXT, font=font(13), anchor="center",
                       tags=T)
        line = self._line_text()
        lw = K.tkfont_of(cv, font(9)).measure(line) + s(6)
        cv.create_text(W - m - s(6), s(58), text=line, fill=DIMT, font=font(9), anchor="e", tags=T)
        # 주머니 단추 (시안 .pk span: 44px 고리, 사이 10px) - 다 안 들면 사이 · 크기를 줄인다
        cells = [(k, lb) for k, lb in POCKETS] + [("refresh", "새로\n고침")]
        x0 = s(20) + tw + s(26)
        x9 = W - m - max(mw, lw) - s(14)
        n = len(cells)
        d, gap = s(44), s(10)
        if n * d + (n - 1) * gap > x9 - x0:
            gap = s(4)
            d = max(s(36), int((x9 - x0 - (n - 1) * gap) / float(n)))
        now = self._pocket_now()
        cy = top // 2
        for i, (key, label) in enumerate(cells):
            cx = x0 + d // 2 + i * (d + gap)
            r = d // 2
            if key == "refresh":
                tg = T + ("refresh",)
                A.ring(cv, cx, cy, r, fill=CARD, tags=tg)
                ink = DIMT
            else:
                tg = T + ("pk", "pk_" + key)
                on = key == now
                empty = self._pocket_count(key) == 0
                A.ring(cv, cx, cy, r, on=on, tags=tg)
                ink = CYAN if on else (FAINT if empty else TEXT)
            cv.create_text(cx, cy, text=label, fill=ink, font=font(8), justify="center", anchor="center", tags=tg)
            if key == "tms" and getattr(self, "_tm_badge", False):
                dd = s(4)
                bx, by = cx + r * 0.62, cy - r * 0.72
                cv.create_oval(bx - dd, by - dd, bx + dd, by + dd, fill=DOT, outline=BG, width=2, tags=tg)
        for key, _l in POCKETS:
            cv.tag_bind("pk_" + key, "<Button-1>", lambda _e, k=key: self._pocket_click(k))
        cv.tag_bind("refresh", "<Button-1>", lambda _e: self.reload())
        self._hand("pk", "refresh")

    # ---------------- 오른쪽 위: 설명 판 (시안: 고리 · 이름 · 등급 · 설명) ----------------
    RING_R = 33            # 도구 그림 고리 (시안 .ring 66px) - 창이 낮으면 작게 (카드 자리를 남긴다)

    def _ring_r(self):
        try:
            h = self.cv.winfo_height()
        except tk.TclError:
            h = 9999
        return U.h(22 if h < U.h(500) else (27 if h < U.h(560) else self.RING_R))

    def _detail_height(self, cv, width, room):
        s = U.h
        _n, _sub, desc, _art = self._detail_content()
        head = s(14) + 2 * self._ring_r() + s(12)
        dh = K.text_height(cv, desc, font(11), width - s(32)) if desc else 0
        return max(head + s(8), min(int(room * 0.46), head + dh + (s(14) if desc else 0)))

    def _bw_detail(self, cv, x1, y1, x2, y2):
        s = U.h
        name, sub, desc, art = self._detail_content()
        A.panel(cv, x1, y1, x2, y2, tags=T)
        r = self._ring_r()
        cx, cy = x1 + s(16) + r, y1 + s(14) + r
        cv.create_oval(cx - r - s(7), cy - r - s(7), cx + r + s(7), cy + r + s(7), fill=RING_OUT, outline="", tags=T)
        cv.create_oval(cx - r - s(5), cy - r - s(5), cx + r + s(5), cy + r + s(5), fill=PANEL, outline="", tags=T)
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=PANEL, outline=CYAN, width=max(2, s(2)), tags=T)
        if art is not None:
            art(cv, cx, cy)
        tx = cx + r + s(18)
        tw = x2 - s(16) - tx
        _a, nid = K.text(cv, tx, cy - s(4), name, font(16), fill=TEXT, anchor="sw", width=tw, tags=T)
        if sub:
            K.text(cv, tx, cy + s(4), sub, font(10), fill=DIMT, anchor="nw", width=tw, tags=T)
        if desc:
            K.text(cv, x1 + s(16), cy + r + s(12), desc, font(11), fill=DESC, anchor="nw", width=x2 - x1 - s(32),
                   tags=T)

    # ---------------- 아래 줄: 보조 단추 · 하늘빛 큰 단추 ----------------
    def _paint_actions(self, cv, x1, y1, x2, y2):
        s = U.h
        btns = [b for b in self._bw_actions() if b is not None]
        x = x2
        for i, b in enumerate(reversed(btns)):
            big = i == 0
            w = b.want_width(s(48) if big else s(30))
            w = max(w, s(150) if big else s(70))
            w = min(w, x - x1)
            b.layout(x - w, y1, x, y2)
            x -= w + s(8)

    # ---------------- 시안 .seg: 줄 세우기 · 거르기 알약 ----------------
    def _tabs(self, cv, x, y, h, items, current, tag, on_pick, spec=None, align="left", fill_off=None,
              line_off=None, x2=None):
        """작은 알약 줄. x2 를 주면 x..x2 를 같은 폭으로 나눈다 (시안의 flex: 1). 그린 칸들 [(열쇠, 상자)]."""
        spec = spec or font(10)
        f = K.tkfont_of(cv, spec)
        gap = U.h(6)
        if x2 is not None:
            n = max(1, len(items))
            ws = [int((x2 - x - gap * (n - 1)) / float(n))] * n
        else:
            ws = [f.measure(lb) + U.h(22) for _k, lb in items]
            if align == "right":
                x -= sum(ws) + gap * (len(items) - 1)
        out = []
        for (key, lb), w in zip(items, ws):
            on = key == current
            tg = T + (tag, "%s_%s" % (tag, key or "_"))
            A.pill(cv, x, y + 1, x + w, y + h - 1, on=on, tags=tg)
            cv.create_text(x + w // 2, y + h // 2, text=lb, fill=CYAN if on else DIMT, font=spec, anchor="center",
                           tags=tg)
            cv.tag_bind("%s_%s" % (tag, key or "_"), "<Button-1>", lambda _e, k=key: on_pick(k))
            out.append((key, (x, y, x + w, y + h)))
            x += w + gap
        self._hand(tag)
        return out

    def _find_row(self, cv, key, entry, x1, y, x2, h):
        """시안 .find: '찾기' + 밑줄만 있는 입력칸."""
        s = U.h
        cv.create_text(x1 + s(2), y + h // 2, text="찾기:", fill=DIMT, font=font(10), anchor="w", tags=T)
        ex = x1 + K.tkfont_of(cv, font(10)).measure("찾기:") + s(10)
        self._place(key, entry, ex, y, x2 - ex, h - s(3))
        cv.create_line(x1, y + h, x2, y + h, fill=LINE, tags=T)

    # ---------------- 포켓몬 카드 (시안 .card) ----------------
    def _draw_plate(self, cv, m, x1, y1, x2, y2, tags, hov):
        s = U.h
        info = self._plate_info(m)
        blocked, good = info.get("blocked"), info.get("good")
        sel = m.get("id") == self.mon_id
        y1 += s(2)
        y2 -= s(2)
        r = s(8)
        if sel:
            A.lit(cv, x1 + s(3), y1, x2 - s(3), y2, r, SEL, on_bg=True, tags=tags)
        else:
            if blocked:
                fill, line = "#17191c", PANEL_HI
            elif good and not hov:                   # 쓸 수 있는 포켓몬 - 테에 초록 기운만 (시안은 무늬 없는 카드)
                fill, line = CARD, "#33584a"
            else:
                fill, line = (PANEL if hov else CARD), (LINE_HI if hov else LINE)
            K.rrect(cv, x1 + s(3), y1, x2 - s(3), y2, r, fill=fill, outline=line, width=1, tags=tags)
        mid = (y1 + y2) // 2
        ph = info.get("photo")
        if ph is not None:
            cv.create_image(x1 + s(30), mid, image=ph, tags=tags)
        name = info.get("name") or "?"
        if info.get("shiny"):
            name = "★ " + name
        tx = x1 + s(56)
        ink = FAINT if blocked else TEXT
        cv.create_text(tx, mid - s(2), text=name, fill="#f0c75e" if info.get("shiny") and not blocked else ink,
                       font=font(11), anchor="sw", tags=tags)
        sub = info.get("sub") or ""
        cv.create_text(tx, mid + s(3), text=sub, fill=FAINT if blocked else DIMT, font=font(9), anchor="nw",
                       tags=tags)
        if info.get("note"):
            # 좁은 카드에서 아래 줄 글과 닿으면 이름 줄 오른쪽으로 올린다
            f9 = K.tkfont_of(cv, font(9))
            nw = f9.measure(info["note"])
            low = tx + f9.measure(sub) + s(10) <= x2 - s(14) - nw
            cv.create_text(x2 - s(14), (mid + s(3)) if low else (mid - s(2)), text=info["note"],
                           fill=tone(info.get("color") or U.FG_DIM), font=font(9), anchor="ne" if low else "se",
                           tags=tags)


class BagWindow(BWBag, DPB.BagWindow):

    def _build(self):
        DPB.BagWindow._build(self)
        self.PLATE_H = U.h(self.PLATE_PX)
        BWButton.adopt(self.use_btn, "go")
        BWButton.adopt(self.sell_btn, "dark")
        BWButton.adopt(self.sell_many_btn, "dark")
        BWButton.adopt(self.close_btn, "dark")
        self.items_vl.cv.configure(bg=PANEL)
        self.items_vl.frame.configure(bg=PANEL)
        self._bw_restyle()

    def _bw_actions(self):
        return [self.sell_btn, self.sell_many_btn, self.use_btn]

    def _bw_plates(self, width):
        it = self._item
        return "누구에게 쓸까?", (B.target_hint(it) if it else ""), self._mon_note, self._boxes(self.cv, width)

    def _detail_content(self):
        it = self._item
        if not it:
            return ("도구를 고르세요", "",
                    "위에서 주머니를 고르고, 목록에서 도구를 고르면 여기에 설명이 뜬다.", None)
        bits = [B.CAT_KR.get(it["cat"], it["cat"])]
        if it.get("rarity") in RARE_KR:
            bits.append(RARE_KR[it["rarity"]])
        bits.append("%d개" % self.bag.get(it["id"], 0))

        def art(cv, cx, cy):
            ph = item_icons.photo(it["id"], 44)
            if ph is not None:
                cv.create_image(cx, cy, image=ph, tags=T)
        return it["kr"], " · ".join(bits), natural(B.item_desc(it)), art

    # ---------------- 왼쪽 목록 판 ----------------
    def _bw_list(self, cv, ix1, iy1, ix2, iy2):
        s = U.h
        th = s(28)
        self._find_row(cv, "ifind", self.item_find, ix1, iy1, ix2, th)
        sy = iy1 + th + s(10)
        sh = s(26)
        self._tabs(cv, ix1, sy, sh, B.ITEM_SORTS, self.item_sort, "srt", self.set_item_sort, x2=ix2)
        ly1 = sy + sh + s(8)
        if self._items_state == "list":
            self._place("items", self.items_vl.frame, ix1, ly1, ix2 - ix1, iy2 - ly1)
        else:
            self._hide("items")
            note = self._items_note if self._items_state == "nomatch" else \
                "가방이 비어 있다.\n야생 포켓몬을 잡거나 배틀에서 도구를 주울 수 있다."
            K.text(cv, (ix1 + ix2) // 2, ly1 + s(40), note, font(11), fill=DIMT, anchor="n", justify="center",
                   width=ix2 - ix1 - 20, tags=T)

    # ---------------- 목록 한 줄 (시안 .ln · .gh) ----------------
    def _draw_item_row(self, cv, data, x, y, w, h, tags, hover=None):
        s = U.h
        kind, val = data
        if kind == "head":
            cat, n = val[0], val[1]
            sub = val[2] if len(val) > 2 else None
            label = ("%s · %s · %d종" % (B.CAT_KR.get(cat, cat), sub, n)) if sub else \
                "%s · %d종" % (B.CAT_KR.get(cat, cat), n)
            cv.create_text(x + s(6), y + h // 2 + s(2), text=label, fill=DIMT, font=font(9), anchor="w", tags=tags)
            return
        it = val
        usable = (it.get("effect") or {}).get("kind") in B.USABLE
        sel = it["id"] == self.item_id
        x2 = x + w - s(4)
        if sel:
            K.rrect(cv, x, y + 1, x2, y + h - 1, s(7), fill=GLOW_FAR, tags=tags)
            K.rrect(cv, x + 1, y + 2, x2 - 1, y + h - 2, s(6), fill=SEL, outline=CYAN, width=1, tags=tags)
        elif hover is not None:
            K.rrect(cv, x + 1, y + 2, x2 - 1, y + h - 2, s(6), fill=PANEL_HI, tags=tags)
        m = y + h // 2
        icon = item_icons.photo(it["id"], 24)
        if icon is not None:
            cv.create_image(x + s(18), m, image=icon, tags=tags)
        fg = TEXT if usable else FAINT
        nid = cv.create_text(x + s(36), m, text=it["kr"], fill=fg, font=font(11), anchor="w", tags=tags)
        cx = x2 - s(10)
        cv.create_text(cx, m, text="×%d" % self.bag.get(it["id"], 0), fill=fg, font=font(11), anchor="e", tags=tags)
        rk = it.get("rarity")
        if rk in RARE_KR:
            rx = cx - s(46)
            f = K.tkfont_of(cv, font(9))
            b = cv.bbox(nid)
            if not b or b[2] + s(10) <= rx - f.measure(RARE_KR[rk]):
                cv.create_text(rx, m, text=RARE_KR[rk], fill=DPB.RARE[rk] if usable else FAINT, font=font(9),
                               anchor="e", tags=tags)

