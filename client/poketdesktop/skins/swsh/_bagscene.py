# -*- coding: utf-8 -*-
"""소드·실드 테마 - 가방의 도구 칸 · 기술머신 칸이 같이 쓰는 판 (시안 K 의 가방 그림).

    ┌ 하늘 모서리 ───────────────────────────────────────────────────────────────────┐
    │ 가방  (전체)(지닌 도구)(메가스톤) … (기술머신)        ┌([새로고침]  500,000원)┐   │  머리: 흰 큰 글씨 · 주머니 알약 (고른 것 분홍)
    │                                                     └  460종 · 모두 1380개  ┘   │        · 남색 판 하나에 새로고침 · 돈 · 개수 줄
    │ ┌ 흰 판 ─────────────────────────┐ ┌ 흰 판 ────────────────────────────┐           │
    │ │ (찾기: ______ ) (이름)(종류)(등급)(개수)│ │ [남색 그림 칸] 먹다남은음식 (분홍 꼬리표) │           │
    │ │ ● 열매 · 3종                    │ │               지니게 하면 …              │           │
    │ │   오랭열매                 ×5   │ └──────────────────────────────────┘           │
    │ │▌먹다남은음식 (남색 · 흰 글씨) ×1 │ ┌ 흰 판: 누구에게 쓸까? · 찾기 · 판 목록 ─┐       │
    │ └────────────────────────────────┘ │ (한 줄 판 - 고른 것은 하늘 테)          │       │
    │                                    └────────────────────────────────────┘       │
    │                                     [팔기] [여러 개 팔기]     (( 지니게 하기 ))  분홍 모서리
    └──────────────────────────────────────────────────────────────────────────────────┘

창이 좁아 주머니 알약이 머리 한 줄에 다 안 들면 왼쪽 기둥 (가방 · 돈 판 · 알약 · 새로고침) 으로 놓고, 판들은
창 위까지 올린다 - 목록 · 포켓몬 판의 줄 수가 기본 테마보다 적어지지 않게 (재서 맞췄다: 1040x700 · 980x620).

바탕은 남색 빗금 + 모서리 (판 바깥에만 - 글은 늘 판 · 알약 위). 판은 남색 바깥 테 · 흰 테 · #f6f7fb.
알릴 말은 오른쪽 위 판 자리에 잠깐 뜬다 (DP _toast 그대로). 동작은 DP 칸(그 밑의 기본 창) 그대로다.

부르는 창이 정하는 것:
    _lcd_text · _line_text · _pocket_now · _pocket_count · _pocket_click · _dial_buttons · _tm_badge   (DP 와 같다)
    _sw_list(cv, x1, y1, x2, y2)       왼쪽 판 안 (찾기 · 줄 세우기 · 목록)
    _sw_desc() -> (제목, 꼬리표 글 또는 None, 본문, 그림 그리기(cv, x, y, s) 또는 None)
    _sw_who() -> (제목, 안내, 판 대신 놓을 글 또는 None, 끼우는 칸들)
    _sw_action() -> 아래 큰 단추
"""
import tkinter as tk

from ... import box_filter
from ... import ui_common as U
from ..dp import font, tone
from ..dp import kit as K
from ..dp.scene import POCKET_NAME, POCKETS, T
from . import CYAN, CYAN_L, DESC, DIMK, MAG, NAVY, ON_NAVY_DIM, PAPER2
from . import _sw as S


LABEL = dict((k, POCKET_NAME.get(k, lb.replace("\n", ""))) for k, lb in POCKETS)


class SwScene(object):
    """도구 칸 · 기술머신 칸의 판 (DP scene 의 PocketDial · Band · Plates 를 시안 모양으로 바꿔 그린다)."""

    ACTION_H = 56
    PLATE_ROW_PX = 40        # 포켓몬 판 한 줄 (.m - 그림 · 이름 · Lv · 상태를 한 줄에)
    PAD = 10                 # 판 안 여백 (pt)

    def _sw_restyle(self):
        """DP 가 만든 부품을 시안 모양으로 (같은 물건 - 동작 · 바인딩은 그대로)."""
        try:
            self.cv.configure(bg=NAVY)
            self.win.configure(bg=NAVY)
        except tk.TclError:
            pass
        S.flat_entry(self.find.box)
        S.paper_list(self.mons_vl)
        self.PLATE_H = U.h(self.PLATE_ROW_PX)

    # ---------------- 판 전체 ----------------
    COUNT_IN_HEAD = True     # 개수 줄을 머리에 (도구 칸). 기술머신 칸은 목록 판 안에 둔다

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
        s = U.h
        cv.delete("scene")
        self._msg_ids = None
        S.backdrop(cv, 0, 0, W, H, tags=T)
        top, side = self._paint_head(cv, W, H)
        bottom = H - s(10)
        pad = s(self.PAD)
        # 왼쪽 판: 목록 (주머니 알약이 머리 한 줄에 다 안 들면 그 왼쪽에 기둥 - 가방 · 돈 · 알약 · 새로고침)
        lx1 = s(16) + (side + s(14) if side else 0)
        lx2 = lx1 + max(s(290), min(s(470), int((W - lx1 - s(16)) * 0.47)))
        rx1, rx2 = lx2 + s(16), W - s(16)
        act = s(self.ACTION_H)
        # 머리에 못 둔 개수 줄은 아래 단추 줄의 빈 자리 (남색 알약) - 그것도 안 되면 목록 판 안
        self._line_in_act = (not self.COUNT_IN_HEAD) and self._act_room(cv, rx2 - rx1) >= self._line_chip_w(cv)
        S.card(cv, lx1, top, lx2, bottom, tags=T)
        self._sw_list(cv, lx1 + pad + s(2), top + pad, lx2 - pad - s(2), bottom - pad + s(4))
        # 오른쪽: 설명 판 / 누구에게 판 / 아래 단추 줄
        dh = self._desc_height(cv, rx2 - rx1, H)
        S.card(cv, rx1, top, rx2, top + dh, tags=T)
        self._paint_desc(cv, rx1, top, rx2, top + dh)
        wy1 = top + dh + s(14)
        S.card(cv, rx1, wy1, rx2, bottom - act, tags=T)
        self._who_w = (rx2 - rx1) - 2 * (pad + s(2))     # 끼우는 칸(능력 · 노력치)의 폭
        self._paint_who(cv, rx1 + pad + s(2), wy1 + pad, rx2 - pad - s(2), bottom - act - s(6))
        self._paint_actions(cv, rx1, bottom - act + s(12), rx2, bottom)
        self._toast_box = (rx1, top, rx2, top + dh)
        self._paint_toast()

    # ---------------- 머리: 가방 · 주머니 알약 · [새로고침] · 돈 ----------------
    def _paint_head(self, cv, W, H):
        """(판이 시작하는 y, 왼쪽 기둥의 폭 또는 0).

        넓으면 시안 그대로 머리 한 줄: '가방' (하늘 모서리 위) · 주머니 알약 · [새로고침] · 돈 알약.
        알약이 한 줄에 다 안 들면 왼쪽 기둥: '가방' · 돈 판 (개수 줄 함께) · 주머니 알약 · [새로고침] -
        그러면 판들은 창 위까지 올라간다 (목록 · 포켓몬 판 줄 수를 기본 테마만큼 지킨다)."""
        s = U.h
        tf = font(21)
        ft = K.tkfont_of(cv, tf)
        tw = ft.measure("가방")
        money = self._lcd_text()
        mf, rf, spec = font(12), font(9), font(10)
        sub = self._line_text() if self.COUNT_IN_HEAD else None
        f9 = K.tkfont_of(cv, font(9))
        rw = K.tkfont_of(cv, rf).measure("새로고침") + s(18)
        # 오른쪽 덩이: 남색 판 (.money) 하나에 [새로고침] · 돈, 그 밑 줄에 개수 줄
        mw1 = K.tkfont_of(cv, mf).measure(money) + s(26)
        bw = max(rw + s(6) + mw1, (f9.measure(sub) + s(28)) if sub else 0) + s(8)
        mh = s(32) + ((f9.metrics("linespace") + s(2)) if sub else 0)
        items = [(key, LABEL.get(key, key)) for key, _l in POCKETS]
        ws = [S.pill_w(cv, lb, spec, s(11)) for _k, lb in items]
        gap = s(5)
        x0 = s(22) + tw + s(20)
        x_end = W - s(16) - bw - s(12)
        now = self._pocket_now()
        cv.create_text(s(22), s(4), text="가방", fill="#ffffff", font=tf, anchor="nw", tags=T)
        if x0 + sum(ws) + gap * (len(ws) - 1) <= x_end:
            # ---- 머리 한 줄 (시안)
            my1 = s(6)
            self._money_block(cv, W - s(16) - bw, my1, W - s(16), my1 + mh, money, sub, rw)
            head_h = max(my1 + mh, s(4) + ft.metrics("linespace")) + s(8)
            ph = s(30)
            boxes = []
            x = x0
            py = my1 + (mh - ph) // 2
            for w in ws:
                boxes.append((x, py, x + w, py + ph))
                x += w + gap
            side = 0
            top = head_h + s(2)
        else:
            # ---- 왼쪽 기둥
            # (도구 칸 · 기술머신 칸이 같은 폭 - 칸을 오갈 때 판이 옆으로 밀리지 않게)
            side = max(max(ws), mw1, K.tkfont_of(cv, mf).measure("9,999,999원") + s(26), rw) + s(10)
            cx1, cx2 = s(16), s(16) + side
            y = s(4) + ft.metrics("linespace") + s(6)
            if sub:                                   # 개수 줄은 기둥 폭 안에서 접는다
                mh = s(32) + K.text_height(cv, sub, font(9), side - s(24)) + s(4)
            self._money(cv, cx1, y, cx2, y + mh, money, sub)
            y += mh + s(10)
            rh = s(26)
            n = len(items)
            ph = max(s(22), min(s(30), (H - s(10) - rh - s(8) - y) // n - gap))
            boxes = []
            for _w in ws:
                boxes.append((cx1, y, cx2, y + ph))
                y += ph + gap
            self._refresh(cv, cx1, y + s(3), cx2, y + s(3) + rh)
            top = s(10)
        self._count_shown = bool(sub)
        for (key, lb), (x1, y1, x2, y2) in zip(items, boxes):
            tg = T + ("pk", "pk_" + key)
            S.pill(cv, x1, y1, x2, y2, lb, on=key == now, spec=spec, tags=tg, dim=self._pocket_count(key) == 0)
            if key == "tms" and getattr(self, "_tm_badge", False):
                r = s(5)
                cv.create_oval(x2 - s(6) - r, y1 - r, x2 - s(6) + r, y1 + r, fill="#ff3b3b",
                               outline="#ffffff", width=2, tags=tg)
        for key, _l in POCKETS:
            cv.tag_bind("pk_" + key, "<Button-1>", lambda _e, k=key: self._pocket_click(k))
        self._hand("pk", "refresh")
        return top, side

    def _money(self, cv, x1, y1, x2, y2, money, sub):
        """.money - 남색 알약 · 흰 테 2. sub 가 있으면 그 밑에 흐린 둘째 줄 (개수 줄)."""
        s = U.h
        r = min((y2 - y1) // 2, s(16))
        K.rrect(cv, x1, y1, x2, y2, r, fill="#ffffff", tags=T)
        K.rrect(cv, x1 + s(2), y1 + s(2), x2 - s(2), y2 - s(2), r - s(2), fill=NAVY, tags=T)
        if not sub:
            cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=money, fill="#ffffff", font=font(12),
                           anchor="center", tags=T)
            return
        cv.create_text((x1 + x2) // 2, y1 + s(15), text=money, fill="#ffffff", font=font(12), anchor="center",
                       tags=T)
        K.text(cv, (x1 + x2) // 2, y1 + s(27), sub, font(9), fill=ON_NAVY_DIM, anchor="n", justify="center",
               width=x2 - x1 - s(24), tags=T)

    def _money_block(self, cv, x1, y1, x2, y2, money, sub, rw):
        """머리 오른쪽: 남색 판 · 흰 테 하나에 윗줄 [새로고침] (흰 알약) · 돈, 아랫줄 개수 줄."""
        s = U.h
        r = min((y2 - y1) // 2, s(16))
        K.rrect(cv, x1, y1, x2, y2, r, fill="#ffffff", tags=T)
        K.rrect(cv, x1 + s(2), y1 + s(2), x2 - s(2), y2 - s(2), r - s(2), fill=NAVY, tags=T)
        row = s(32)
        rh = s(22)
        ry = y1 + (row - rh) // 2 + s(1)
        self._refresh(cv, x1 + s(7), ry, x1 + s(7) + rw, ry + rh)
        cv.create_text((x1 + s(7) + rw + x2) // 2, y1 + row // 2 + s(1), text=money, fill="#ffffff", font=font(12),
                       anchor="center", tags=T)
        if sub:
            cv.create_text((x1 + x2) // 2, y1 + row - s(2), text=sub, fill=ON_NAVY_DIM, font=font(9), anchor="n",
                           tags=T)

    def _refresh(self, cv, x1, y1, x2, y2):
        tg = T + ("refresh",)
        S.pill(cv, x1, y1, x2, y2, "새로고침", spec=font(9), tags=tg)
        cv.tag_bind("refresh", "<Button-1>", lambda _e: self.reload())

    def _count_text(self, cv, x2, ym):
        """개수 줄 (DP 이름표 밑 한 줄)을 찾기 칸 오른쪽 안에 흐린 글로. 그 글의 왼쪽 x."""
        s = U.h
        t = self._line_text()
        cv.create_text(x2 - s(12), ym, text=t, fill=DIMK, font=font(9), anchor="e", tags=T)
        return x2 - s(12) - K.tkfont_of(cv, font(9)).measure(t)

    # ---------------- 오른쪽 위: 설명 판 ----------------
    SQ = 56

    def _desc_lay(self, cv, width):
        """(이름 높이, 꼬리표가 이름 옆인가, 머리 높이, 본문 높이, 글 폭)."""
        s = U.h
        title, tag, body, _art = self._sw_desc()
        sq = s(self.SQ)
        tw = width - 2 * s(16) - sq - s(14)
        th = K.text_height(cv, title, font(15), tw)
        beside = False
        head = th
        if tag:
            f15, f9 = K.tkfont_of(cv, font(15)), K.tkfont_of(cv, font(9))
            beside = th <= f15.metrics("linespace") + 2 and \
                f15.measure(title) + s(10) + f9.measure(tag) + s(16) <= tw
            if not beside:
                head = th + s(4) + f9.metrics("linespace") + s(4)
        bh = K.text_height(cv, body, font(11), tw) if body else 0
        return th, beside, head, bh, tw

    def _desc_height(self, cv, width, H):
        s = U.h
        _th, _b, head, bh, _tw = self._desc_lay(cv, width)
        inner = max(s(self.SQ), head + (s(6) + bh if bh else 0))
        return max(s(84), min(int(H * 0.42), s(14) + inner + s(14)))

    def _paint_desc(self, cv, x1, y1, x2, y2):
        """.sq 남색 그림 칸 · 이름 (굵게) · 분홍 꼬리표 (이름 옆, 안 들면 밑) · 설명 (그림 칸 오른쪽)."""
        s = U.h
        title, tag, body, art = self._sw_desc()
        th, beside, head, bh, tw = self._desc_lay(cv, x2 - x1)
        sq = s(self.SQ)
        ix, iy = x1 + s(16), y1 + s(14)
        K.rrect(cv, ix, iy, ix + sq, iy + sq, s(12), fill=NAVY, tags=T)
        if art is not None:
            art(cv, ix, iy, sq)
        tx = ix + sq + s(14)
        total = head + (s(6) + bh if bh else 0)
        ty = iy + max(0, (sq - total) // 2)
        _a, tid = K.text(cv, tx, ty, title, font(15), fill=NAVY, width=tw, tags=T)
        if tag:
            if beside:
                b = cv.bbox(tid)
                S.chip(cv, (b[2] if b else tx) + s(10), ty + (th - K.tkfont_of(cv, font(9)).metrics("linespace")
                                                             - s(4)) // 2, tag, tags=T)
            else:
                S.chip(cv, tx, ty + th + s(4), tag, tags=T)
        if body:
            K.text(cv, tx, ty + head + s(6), body, font(11), fill=DESC, width=tw, tags=T)

    # ---------------- 오른쪽 가운데: 누구에게 판 ----------------
    def _paint_who(self, cv, x1, y1, x2, y2):
        """제목 · 안내 / 포켓몬 찾기 · 줄 세우기 / 끼우는 칸 / 판 목록 (또는 안내 글)."""
        s = U.h
        title, hint, note, boxes = self._sw_who()
        cv.create_text(x1 + s(2), y1 + s(2), text=title, fill=NAVY, font=font(12), anchor="nw", tags=T)
        fy = y1 + s(26)
        if hint:
            tw = K.tkfont_of(cv, font(12)).measure(title)
            hw = K.tkfont_of(cv, font(9)).measure(hint)
            if x1 + tw + s(16) + hw <= x2:
                cv.create_text(x2, y1 + s(5), text=hint, fill=DIMK, font=font(9), anchor="ne", tags=T)
            else:
                _a, hid = K.text(cv, x1 + s(2), fy - s(4), hint, font(9), fill=DIMK, width=x2 - x1, tags=T)
                b = cv.bbox(hid)
                fy = (b[3] if b else fy + s(16)) + s(6)
        fh = s(28)
        if note is not None and not self.find.searching():
            self._hide("mfind")
            self._who_rest(cv, x1, x2, fy, y2, note, boxes)
            return
        sorts = box_filter.PICK_SORTS
        f9 = K.tkfont_of(cv, font(9))
        tabs_w = sum(f9.measure(lb) + s(20) for _k, lb in sorts) + s(4) * (len(sorts) - 1)
        cnt_w = s(60) if self.find.count else 0
        if x2 - tabs_w - s(10) - cnt_w - x1 >= s(150):                  # 한 줄에 다 든다
            tx = x2 - tabs_w
            self._sort_pills(cv, tx, fy + s(3), fh - s(6), sorts)
            y = fy + fh + s(8)
            fx2 = tx - s(10)
        else:                                                             # 줄 세우기는 아래 줄로
            self._sort_pills(cv, x1, fy + fh + s(6), fh - s(6), sorts)
            y = fy + 2 * fh + s(12)
            fx2 = x2
        ex = S.field(cv, x1, fy, fx2, fy + fh, "포켓몬 찾기", tags=T)
        self._place("mfind", self.find.box, ex, fy + s(4), max(s(60), fx2 - ex - s(10) - cnt_w), fh - s(8))
        if self.find.count:
            cv.create_text(fx2 - s(10), fy + fh // 2, text=self.find.count, fill=DIMK, font=font(9), anchor="e",
                           tags=T)
        self._who_rest(cv, x1, x2, y, y2, note, boxes)

    def _sort_pills(self, cv, x, y, h, sorts):
        spec = font(9)
        for key, lb in sorts:
            w = K.tkfont_of(cv, spec).measure(lb) + U.h(20)
            on = key == self.find.sort
            tg = T + ("msrt", "msrt_%s" % (key or "_"))
            K.rrect(cv, x, y, x + w, y + h, h // 2, fill=MAG if on else PAPER2, tags=tg)
            cv.create_text(x + w // 2, y + h // 2, text=lb, fill="#ffffff" if on else DIMK, font=spec,
                           anchor="center", tags=tg)
            cv.tag_bind("msrt_%s" % (key or "_"), "<Button-1>", lambda _e, k=key: self.find.pick_sort(k))
            x += w + U.h(4)
        self._hand("msrt")

    def _who_rest(self, cv, x1, x2, y, y2, note, boxes):
        s = U.h
        for h, draw in boxes:
            draw(cv, x1, y, x2)
            y += h + s(6)
        if note is None:
            cols = 2 if (x2 - x1) >= s(440) else 1
            if cols != self._plate_cols:
                self._plate_cols = cols
                self._plates_set(self._plate_rows_src, keep=True)
            self._place("mons", self.mons_vl.frame, x1 - s(6), y, x2 - x1 + s(10), max(s(40), y2 - y))
        else:
            self._hide("mons")
            K.text(cv, (x1 + x2) // 2, y + s(16), note, font(11), fill=DESC, anchor="n", justify="center",
                   width=x2 - x1 - s(20), tags=T)

    # ---------------- 포켓몬 판 (.m - 고른 것은 하늘 테 · 옅은 하늘 바탕) ----------------
    def _draw_plate(self, cv, m, x1, y1, x2, y2, tags, hov):
        """한 줄: 그림 · 이름 · 흐린 Lv … 오른쪽 상태 (시안 .m). 칸이 좁아 안 들면 이름 밑에 Lv 를 놓는다."""
        s = U.h
        info = self._plate_info(m)
        blocked, good = info.get("blocked"), info.get("good")
        sel = m.get("id") == self.mon_id
        if sel:
            fill = CYAN_L
        elif blocked:
            fill = "#e2e4ee"
        elif good:
            fill = "#e7f7ee"
        elif hov:
            fill = "#eef0fa"
        else:
            fill = "#ffffff"
        r = s(10)
        if sel:
            K.rrect(cv, x1, y1, x2, y2, r, fill=CYAN, tags=tags)
            g = max(2, s(3))
            K.rrect(cv, x1 + g, y1 + g, x2 - g, y2 - g, r - g, fill=fill, tags=tags)
        else:
            K.rrect(cv, x1, y1, x2, y2, r, fill=fill, tags=tags)          # (.m - 테 없는 줄)
        mid = (y1 + y2) // 2
        ph = info.get("photo")
        if ph is not None:
            cv.create_image(x1 + s(22), mid, image=ph, tags=tags)
        name = info.get("name") or "?"
        if info.get("shiny"):
            name = "★ " + name
        ncol = "#9a6a00" if info.get("shiny") else NAVY
        tx = x1 + s(44)
        f11, f9 = K.tkfont_of(cv, font(11)), K.tkfont_of(cv, font(9))
        sub, note = info.get("sub") or "", info.get("note") or ""
        ncolor = tone(info.get("color") or U.FG_DIM)
        need = f11.measure(name) + s(8) + f9.measure(sub) + (s(14) + f9.measure(note) if note else 0)
        if tx + need <= x2 - s(12):
            cv.create_text(tx, mid, text=name, fill=ncol, font=font(11), anchor="w", tags=tags)
            cv.create_text(tx + f11.measure(name) + s(8), mid + s(1), text=sub, fill=DIMK, font=font(9),
                           anchor="w", tags=tags)
            if note:
                cv.create_text(x2 - s(12), mid + s(1), text=note, fill=ncolor, font=font(9), anchor="e", tags=tags)
            return
        cv.create_text(tx, y1 + s(4), text=name, fill=ncol, font=font(11), anchor="nw", tags=tags)
        cv.create_text(tx, y2 - s(4), text=sub, fill=DIMK, font=font(9), anchor="sw", tags=tags)
        if note:
            low = tx + f9.measure(sub) + s(10) <= x2 - s(12) - f9.measure(note)
            cv.create_text(x2 - s(12), (y2 - s(4)) if low else (y1 + s(6)), text=note, fill=ncolor, font=font(9),
                           anchor="se" if low else "ne", tags=tags)

    # ---------------- 아래 단추 줄 ----------------
    def _line_chip_w(self, cv):
        return K.tkfont_of(cv, font(9)).measure(self._line_text()) + U.h(28)

    def _act_room(self, cv, width):
        """아래 단추 줄에서 작은 단추 · 큰 단추를 놓고 남는 폭."""
        s = U.h
        used = sum(b.want_width(s(30)) + s(8) for b in self._dial_buttons() if b is not None)
        return width - used - max(s(220), self._sw_action().want_width(s(70))) - s(10)

    def _paint_actions(self, cv, x1, y1, x2, y2):
        """왼쪽에 작은 흰 알약 (팔기 · 새 기술머신) [· 개수 줄 남색 알약], 오른쪽에 큰 분홍 단추 (.go)."""
        s = U.h
        btns = [b for b in self._dial_buttons() if b is not None]
        x = x1
        for b in btns:
            w = b.want_width(s(30))
            b.layout(x, y1 + s(4), x + w, y2 - s(4))
            x += w + s(8)
        if getattr(self, "_line_in_act", False):
            w = self._line_chip_w(cv)
            ya, yb = y1 + s(6), y2 - s(6)
            K.rrect(cv, x, ya, x + w, yb, (yb - ya) // 2, fill="#ffffff", tags=T)
            K.rrect(cv, x + s(2), ya + s(2), x + w - s(2), yb - s(2), (yb - ya) // 2 - s(2), fill=NAVY, tags=T)
            cv.create_text(x + w // 2, (ya + yb) // 2, text=self._line_text(), fill=ON_NAVY_DIM, font=font(9),
                           anchor="center", tags=T)
            x += w + s(8)
        main = self._sw_action()
        want = max(s(220), main.want_width(s(70)))
        left = x + (s(8) if btns else 0)
        main.layout(max(left, x2 - want), y1, x2, y2)


def type_art(cv, x, y, sz, typ, tags=T):
    """기술머신 칸의 그림 자리: 남색 칸 가운데 타입 빛깔 원 + 타입 이름 (그림을 따로 그리지 않는다)."""
    from ... import ui_tms as TM
    name = TM.TYPE_KR.get(typ, typ or "")
    col = U.TYPE_COLOR.get(typ, "#a0a0a8")
    r = int(sz * 0.36)
    cx, cy = x + sz // 2, y + sz // 2
    cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=col, outline="#ffffff", width=2, tags=tags)
    cv.create_text(cx, cy, text=name, fill=K.look_of(col)[3], font=font(9), anchor="center", tags=tags)

