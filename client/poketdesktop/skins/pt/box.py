# -*- coding: utf-8 -*-
"""플라티나 테마 - 포켓몬 (PC 박스). DS 플라티나의 'PC 박스' 를 시안 B 의 말로 그린다.

원작은 위 화면에 고른 포켓몬의 요약, 아래 화면에 박스 이름 띠(◀ 박스 이름 ▶)와 벽지 위의 6 x 5 칸,
데리고 다니는 포켓몬은 따로 꺼내 보는 판이다. 이 창은 그것을 한 화면에 나란히 놓는다:

    강철 바탕(점)
    ┌ 옅은 판: 요약 (원작의 위 화면) ┐ (타입: 전체 ▾) (찾기 ________) (도감|이름|Lv|종족값)
    │ 보라 머리: 무대(하늘 → 연둣빛  │ ┌ 판 ──────────┐ ┌ 판 ───────────────────────────────┐
    │  + 발판) │ No · 이름 · Lv ·    │ │ 머리 띠       │ │ 머리 띠  (◀) ( 박스 1  8/30 ▾ ) (▶) │
    │  분류 · 타입 캡슐              │ │ (파티 1 ▾)    │ │ ┌ 벽지 (박스마다 다른 빛 · 빗금) ┐ │
    │ (정보|능력|기술|메가진화)      │ │ 흰 캡슐 여섯  │ │ │ 흰 칸 6 x 5 - 고르면 하늘색   │ │
    │ 흰 카드들 (굴러간다)           │ │               │ │ │ 테 + 빛 고리                  │ │
    │ ───────────────────────────── │ └───────────────┘ │ └───────────────────────────────┘ │
    │ (  박스로 보내기  ) (놓아주기) │                   └───────────────────────────────────┘
    │ (별명 짓기)(박스 옮기기)(색 …) │ ┌ 흰 글상자: 보유 N마리 · 알림 ────┐ (이름 바꾸기) (새로고침)
    └───────────────────────────────┘

고른 포켓몬에 하는 일(단추 다섯 · 여러 마리 고르기의 넷)은 요약 판 아래 두 줄에 둔다 - 오른쪽 세로를 박스 칸에 다
줘서 작은 창(980 x 620)에서도 30칸이 한 번에 보인다. 이름 바꾸기 · 새로고침은 글상자 옆.
기술은 배틀 화면처럼 타입 빛깔 캡슐, 주된 일은 주황 캡슐, 고른 것은 하늘색. 글은 늘 단색 판 위에 둔다
(벽지 무늬 위에는 칸 · 말풍선만 있다). 아이콘은 포켓몬 도트 · item_icons 뿐. 지닌 도구 고르기 창은 DP 것 그대로다.

동작은 DP 박스(skins/dp/box.py) → 기본 창(ui_box.BoxWindow) 그대로다 - 고르기 · 끌어서 맞바꾸기 · 여러 마리
고르기 · 박스 넘기기 · 거르기 · 줄 세우기 · 별명 · 지닌 도구 · 기술 떠올리기 · 유대 미션. 여기서는 칠하는 고리만 바꾼다.
"""
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from common import legends as L
from common import movetext as MT

from ... import box_filter, item_icons
from ... import ui_bond as BD
from ... import ui_common as U
from ..dp import box as DPX
from ..dp import font, tone
from ..dp import kit as K
from ..dp.scene import T
from . import (BLUE, CYAN, DIM, FAINT, GREEN, GREEN_LINE, INK, LINE2, ORANGE, PANEL,
               PURPLE, PURPLE_SH, PURPLE_TOP, RIM, SEG, STEEL, WHITE)
from . import _pt as P
from .battle import PAD, PAD_SH, SKY_BOT, SKY_TOP

D = DPX.D
SORTS = DPX.SORTS
INK2 = "#4c5866"
LABEL = PURPLE                     # 카드 안 꼬리 글 (특성 · 성격 · 도구 …)
HOVER_FILL = "#f4fbfe"
CHECK_FILL = "#e3f5e8"
EMPTY_LINE = "#9fb0c0"

# 박스 벽지 - 원작처럼 박스마다 다르다 (숲 · 도시 · 사막 · 사바나 · 바위 · 화산 · 눈 · 하늘). 칸 도트가 먼저 보이게
# 옅은 빛에 같은 빛의 빗금만. (바탕, 빗금)
WALLS = [("#cfe6c4", "#c2dcb5"), ("#cfd8e4", "#c3cddb"), ("#ecdcb8", "#e3d0a8"), ("#e2e8b8", "#d7dea8"),
         ("#dcd2c6", "#d0c5b7"), ("#efcfc8", "#e6c0b8"), ("#e4eef6", "#d6e3ee"), ("#cfe6f2", "#c0dbea")]
WALL_FIND = ("#dde2e8", "#d3d9e0")  # 찾는 중 · 줄 세워 보는 중 (박스가 아니다)


def _ink_on(col):
    """타입 빛깔 위의 글자: 밝은 빛이면 진한 글씨(그림자 없음), 진하면 흰 글씨 + 진한 그림자."""
    r, g, b = (int(col[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    if 0.299 * r + 0.587 * g + 0.114 * b > 0.56:
        return INK, None
    return WHITE, P.mix(col, "#000000", 0.6)


class BoxWindow(DPX.BoxWindow):

    DW_PX = 330            # 요약 판 폭
    PARTY_PX = 156         # 데리고 다니는 판 폭
    THUMB = 40             # 칸에 놓는 도트 높이
    BAND_PX = 42           # 판 머리 띠 높이

    def _build(self):
        DPX.BoxWindow._build(self)
        self._walls = {}
        self.win.configure(bg=STEEL)
        self.cv.configure(bg=STEEL)
        self.find_box = P.Entry(self.cv, self.f_query, width=10)
        # 요약 판: 옅은 회색 판 안에 굴러가는 캔버스 (판 테는 바탕 캔버스가 그린다)
        self.dframe.configure(bg=PANEL, highlightthickness=0)
        self.dcv.configure(bg=PANEL)
        self.dcv.pack_configure(padx=(U.h(4), U.h(2)), pady=U.h(4))
        self.dsb.configure(bg=PANEL)
        # 단추를 캡슐로 (주된 일은 주황, 놓아주기는 빨강, 메가진화는 보라)
        for b in (self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release,
                  self.btn_multi_move, self.btn_multi_release, self.btn_multi_all, self.btn_multi_clear,
                  self.btn_multi_done, self.btn_prev, self.btn_next, self.btn_rename, self.btn_party_name,
                  self.btn_reload, self.btn_hold, self.btn_unhold, self.btn_remember):
            P.to_capsule(b)
        P.to_capsule(self.btn_bond, "purple")

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
        s = U.h
        P.steel(cv, 0, 0, W, H, tags=T)
        m = s(10)
        DW = s(self.DW_PX)
        self._paint_left(cv, m, m, m + DW, H - m)
        self._paint_right(cv, m + DW + s(12), W - m, H)

    def _band(self, cv, x1, y1, x2, bh):
        """판 안 위쪽의 머리 띠 (둥근 위 모서리 · 아래 3px 진한 줄). 띠 아래 y."""
        r = U.h(16) - 3
        P.grad_round(cv, x1 + 3, y1 + 3, x2 - 3, y1 + 3 + bh + r, r, P.BAR1, P.BAR2, tags=T)
        cv.create_rectangle(x1 + 3, y1 + 3 + bh, x2 - 3, y1 + 3 + bh + r + 1, fill=PANEL, outline="", tags=T)
        cv.create_rectangle(x1 + 3, y1 + bh, x2 - 3, y1 + 3 + bh, fill=RIM, outline="", tags=T)
        return y1 + 3 + bh

    # ---------------- 왼쪽: 요약 판 + 고른 포켓몬의 단추 ----------------
    def _paint_left(self, cv, x1, y1, x2, y2):
        """원작의 위 화면(요약) 자리. 고른 포켓몬에 하는 일(데리고 다니기 · 별명 · 박스 옮기기 · 색 · 놓아주기)은
        요약 아래에 두 줄로 - 오른쪽은 박스 칸이 30칸을 한 번에 보이도록 세로를 다 쓴다."""
        s = U.h
        P.panel(cv, x1, y1, x2, y2, tags=T)
        bh = s(38)
        gap = s(6)
        ix1, ix2 = x1 + s(12), x2 - s(12)
        r2 = y2 - s(12)
        r1 = r2 - bh - gap
        top_btn = r1 - bh
        line_y = top_btn - s(10)
        cv.create_line(x1 + s(14), line_y, x2 - s(14), line_y, fill=SEG, width=2, tags=T)
        ins = s(9)
        self._place("detail", self.dframe, x1 + ins, y1 + ins, x2 - x1 - 2 * ins, line_y - s(4) - y1 - ins)
        if self.multi:
            row_a = [(self.btn_multi_move, 3), (self.btn_multi_release, 2)]
            row_b = [(self.btn_multi_all, 1), (self.btn_multi_clear, 1), (self.btn_multi_done, 1)]
            hide = [self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release]
        else:
            row_a = [(self.btn_party, 3), (self.btn_release, 2)]
            row_b = [(self.btn_nick, 1), (self.btn_move, 1), (self.btn_tint, 1)]
            hide = [self.btn_multi_move, self.btn_multi_release, self.btn_multi_all, self.btn_multi_clear,
                    self.btn_multi_done]
        for b in hide:
            b.hide()
        for row, (ry1, ry2) in ((row_a, (top_btn, top_btn + bh)), (row_b, (r1 + gap, r1 + gap + bh))):
            room = ix2 - ix1 - gap * (len(row) - 1)
            want = [b.want_width(s(24)) for b, _k in row]
            extra = room - sum(want)
            wsum = float(sum(k for _b, k in row))
            x = ix1
            for (b, k), w in zip(row, want):
                w = w + extra * k / wsum if extra > 0 else room * k / wsum
                b.layout(int(x), ry1, int(x + w), ry2)
                x += w + gap

    # ---------------- 오른쪽: 고르기 줄 · 데리고 다니는 판 · 박스 판 · 글상자 ----------------
    def _paint_right(self, cv, x0, x2, H):
        s = U.h
        y = s(10)
        # 1) 고르기 줄: 타입 · 찾기 · 줄 세우기
        th = s(32)
        tlabel = self.btn_type.text + " ▾"
        tw = K.tkfont_of(cv, font(10)).measure(tlabel) + s(30)
        P.capsule(cv, x0, y, x0 + tw, y + th, "cyan" if self.f_type else "white", tlabel, font(10), rim_w=2,
                  tags=T + ("tsel",))
        self._boxes["type"] = (x0, y, x0 + tw, y + th)
        cv.tag_bind("tsel", "<Button-1>", lambda _e: self._open_type_menu())
        self._hand("tsel")
        sw = P.seg_width(cv, SORTS, font(10), pad=s(18))
        P.seg(cv, x2 - sw, y, sw, th, SORTS, self.sort, "bsort", self.set_sort, spec=font(10))
        self._hand("bsort")
        fx = x0 + tw + s(10)
        P.entry_capsule(self, cv, "find", self.find_box, fx, y, max(s(110), x2 - sw - s(10) - fx), th,
                        label="찾기", tags=T)
        # 2) 데리고 다니는 판 + 박스 판
        y += th + s(10)
        my2 = H - s(10)
        my1 = my2 - s(42)
        gy2 = my1 - s(10)
        PW = s(self.PARTY_PX)
        self._paint_party_slots(cv, x0, y, x0 + PW, gy2)
        self._paint_box_panel(cv, x0 + PW + s(10), y, x2, gy2)
        # 3) 글상자 (보유 N마리 · 알림) + 이름 바꾸기 · 새로고침
        bw = self.btn_reload.want_width(s(26))
        self.btn_reload.layout(x2 - bw, my1 + s(2), x2, my2)
        rw = self.btn_rename.want_width(s(26))
        rx2 = x2 - bw - s(8)
        self.btn_rename.layout(rx2 - rw, my1 + s(2), rx2, my2)
        mx2 = rx2 - rw - s(10)
        P.panel(cv, x0, my1, mx2, my2, r=s(14), fill=WHITE, tags=T)
        text, color = self.msg
        shown = text or self._count_text
        self._msg_w = max(40, mx2 - x0 - s(32))
        _a, tid = K.text(cv, x0 + s(16), (my1 + my2) // 2 + 1, shown, font(11),
                         fill=(tone(color) if color else (INK if text else INK2)), anchor="w",
                         width=self._msg_w, tags=T)
        self._msg_ids = (None, tid)

    def say(self, msg, color=None):
        DPX.BoxWindow.say(self, msg, color)
        if not (msg or "") and self._msg_ids:
            try:
                self.cv.itemconfigure(self._msg_ids[1], fill=INK2)
            except tk.TclError:
                pass

    # ---------------- 박스 판: 머리 띠(◀ 박스 이름 ▶) + 벽지 ----------------
    def _paint_box_panel(self, cv, x1, y1, x2, y2):
        s = U.h
        P.panel(cv, x1, y1, x2, y2, tags=T)
        bh = s(self.BAND_PX)
        top = self._band(cv, x1, y1, x2, bh)
        ab = s(30)
        ay = y1 + 3 + (bh - 3 - ab) // 2 - 1
        aw = s(40)
        f = K.tkfont_of(cv, font(12))
        room = (x2 - x1) - 2 * s(12) - 2 * (aw + s(8))
        nw = min(room, max(s(150), f.measure(self._page_text) + s(44)))
        cx = (x1 + x2) // 2
        nx1, nx2 = cx - nw // 2, cx + nw // 2
        self.btn_prev.layout(nx1 - s(8) - aw, ay, nx1 - s(8), ay + ab + 3)
        self.btn_next.layout(nx2 + s(8), ay, nx2 + s(8) + aw, ay + ab + 3)
        label = DPX._clamp(cv, self._page_text, font(12), nw - s(24), 1)
        P.capsule(cv, nx1, ay, nx2, ay + ab, "white", label, font(12), rim_w=2, tags=T + ("page",))
        self._boxes["page"] = (nx1, ay, nx2, ay + ab)
        cv.tag_bind("page", "<Button-1>", lambda _e: self.open_box_menu())
        self._hand("page")
        # 벽지 칸 (가는 테)
        wx1, wy1, wx2, wy2 = x1 + s(9), top + s(6), x2 - s(9), y2 - s(9)
        P.rpoly(cv, wx1 - 2, wy1 - 2, wx2 + 2, wy2 + 2, s(6), fill=LINE2, tags=T)
        self.gframe.configure(bg=self._wall()[0])
        self.gsb.configure(bg=self._wall()[0])
        self._place("grid", self.gframe, wx1, wy1, wx2 - wx1, wy2 - wy1)

    def _wall(self):
        if self._searching() or self.sort:
            return WALL_FIND
        return WALLS[self.box_no % len(WALLS)]

    def _wall_photo(self, w, h, wall):
        key = (int(w), int(h), wall)
        ph = self._walls.get(key)
        if ph is not None:
            return ph
        base, stripe = wall
        im = Image.new("RGB", (max(1, int(w)), max(1, int(h))), base)
        d = ImageDraw.Draw(im)
        step, sw = max(10, U.h(18)), max(3, U.h(6))
        for x in range(-int(h), int(w) + step, step):
            d.line((x, 0, x + int(h), int(h)), fill=stripe, width=sw)
        if len(self._walls) > 12:
            self._walls.clear()
        ph = ImageTk.PhotoImage(im)
        self._walls[key] = ph
        return ph

    # ---------------- 데리고 다니는 판 ----------------
    def _paint_party_slots(self, cv, x1, y1, x2, y2):
        """데리고 다니는 여섯 자리. 머리 띠에는 파티 고르기(흰 캡슐 ▾) - 파티가 없으면 '데리고 다니는'."""
        s = U.h
        P.panel(cv, x1, y1, x2, y2, tags=T)
        bh = s(self.BAND_PX)
        top = self._band(cv, x1, y1, x2, bh)
        ym = y1 + 3 + (bh - 3) // 2 - 1
        rows = self.party_presets()
        if rows:
            name = next((p.get("name") or "파티 %d" % p.get("no") for p in rows if p.get("no") == self.party_active()),
                        "파티")
            px1, px2 = x1 + s(10), x2 - s(10)
            ph = s(30)
            P.capsule(cv, px1, ym - ph // 2, px2, ym + ph // 2, "white",
                      DPX._clamp(cv, name, font(10), px2 - px1 - s(34), 1) + " ▾", font(10), rim_w=2,
                      tags=T + ("preset",))
            self._boxes["preset"] = (px1, ym - ph // 2, px2, ym + ph // 2)
            cv.tag_bind("preset", "<Button-1>", lambda _e: self._open_preset_menu())
            self._hand("preset")
        else:
            P.band_title(cv, (x1 + x2) // 2, ym, "데리고 다니는", font(11), anchor="center", tags=T)
        top += s(8)
        self.btn_party_name.hide()
        n = 6
        gap = s(5)
        sh = (y2 - s(10) - top - gap * (n - 1)) / float(n)
        self._pslots = {}
        for i in range(n):
            sy1 = top + i * (sh + gap)
            sy2 = sy1 + sh
            sx1, sx2 = x1 + s(8), x2 - s(8)
            m = self._party_list[i] if i < len(self._party_list) else None
            mid = (sy1 + sy2) / 2
            r = min(s(16), int(sh) // 2)
            if m is None:
                P.rpoly(cv, sx1, sy1, sx2, sy2, r, fill="#d8dde4", tags=T)
                P.rpoly(cv, sx1 + 2, sy1 + 2, sx2 - 2, sy2 - 2, max(0, r - 2), fill="#eef1f4", tags=T)
                cv.create_text((sx1 + sx2) / 2, mid, text="빈 자리", fill=FAINT, font=font(9), tags=T)
                continue
            pid = m["id"]
            sel, tgt = pid == self.sel, pid == self._target
            tg = T + ("pslot",)
            self._cell(cv, sx1, sy1, sx2, sy2, r, sel, tgt, pid in self.checked, pid == self._hover, tags=tg)
            ph = self._thumb(m)
            if ph is not None:
                cv.create_image(sx1 + s(24), mid, image=ph, tags=tg)
            info = m.get("info") or {}
            name = "알" if m.get("isEgg") else info.get("name", m.get("species", "?"))
            if m.get("shiny"):
                name = "★" + name
            cv.create_text(sx1 + s(48), mid - s(8), text=DPX._clamp(cv, name, font(10), sx2 - sx1 - s(56), 1),
                           fill=INK, font=font(10), anchor="w", tags=tg)
            cv.create_text(sx1 + s(48), mid + s(9), anchor="w", font=font(9), fill=INK2, tags=tg,
                           text=("%d%%" % box_filter.egg_progress(m.get("egg") or {})[0]) if m.get("isEgg")
                           else "Lv.%d" % m.get("level", 0))
            self._pslots[pid] = (sx1, sy1, sx2, sy2)
        self._hand("pslot")

    def _cell(self, cv, x1, y1, x2, y2, r, sel, tgt, chk, hov, tags=()):
        """칸 하나 (박스 칸 · 파티 줄): 흰 판 + 테. 고르면 하늘색 테 + 빛 고리, 끌어 놓을 자리는 주황 테,
        여러 마리 고르기로 고른 것은 옅은 초록."""
        if sel:
            P.glow(cv, x1, y1, x2, y2, r, tags=tags)
            line, lw, fill = CYAN, 3, HOVER_FILL
        elif tgt:
            line, lw, fill = ORANGE, 3, HOVER_FILL
        elif chk:
            line, lw, fill = GREEN, 2, CHECK_FILL
        elif hov:
            line, lw, fill = EMPTY_LINE, 2, HOVER_FILL
        else:
            line, lw, fill = SEG, 2, WHITE
        P.rpoly(cv, x1, y1, x2, y2, r, fill=line, tags=tags)
        P.rpoly(cv, x1 + lw, y1 + lw, x2 - lw, y2 - lw, max(0, r - lw), fill=fill, tags=tags)

    # ---------------- 박스 칸 (벽지 위 6 x 5) ----------------
    def _paint_grid(self):
        cv = self.gcv
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.delete("all")
        s = U.h
        cols = 6
        n = len(self._page_mons)
        rows = max(5, -(-n // cols))
        pad = s(7)
        cw = (w - pad) / float(cols)
        ch = max(s(50), (h - pad) / 5.0)
        total = max(h, int(ch * rows + pad))
        cv.configure(scrollregion=(0, 0, w, total))
        wall = self._wall()
        cv.configure(bg=wall[0])
        cv.create_image(0, 0, image=self._wall_photo(w, total, wall), anchor="nw")
        empty = P.mix(wall[0], WHITE, 0.5)
        self._cells = {}
        r = s(10)
        for i in range(rows * cols):
            rr, c = divmod(i, cols)
            x1, y1 = pad + c * cw, pad + rr * ch
            x2, y2 = x1 + cw - pad, y1 + ch - pad
            if i >= n:
                P.rpoly(cv, x1, y1, x2, y2, r, fill=empty)
                continue
            m = self._page_mons[i]
            pid = m["id"]
            chk = pid in self.checked
            self._cell(cv, x1, y1, x2, y2, r, pid == self.sel, pid == self._target, chk, pid == self._hover)
            ph = self._thumb(m)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if ph is not None:
                cv.create_image(mx, my, image=ph)
            else:
                cv.create_oval(mx - 6, my - 6, mx + 6, my + 6, fill=PANEL, outline=LINE2)
            if m.get("shiny"):
                cv.create_text(x1 + 6, y1 + 4, text="★", fill="#d0a000", font=font(9), anchor="nw")
            kind = None if m.get("isEgg") else L.kind_of(m.get("num"))
            d = s(9)                                   # 여러 마리 고르기 표시 (오른쪽 위 초록 동그라미)
            if kind:
                cv.create_text(x2 - 5 - (2 * d + 2 if chk else 0), y1 + 4, text="◆" if kind == "legendary" else "✦",
                               fill="#a050c0", font=font(8), anchor="ne")
            if m.get("away"):
                f = K.tkfont_of(cv, font(8))
                aw = f.measure("탐험 중") + s(12)
                ah = f.metrics("linespace") + s(2)
                P.rpoly(cv, mx - aw / 2, y2 - ah - 3, mx + aw / 2, y2 - 3, ah // 2, fill=BLUE)
                cv.create_text(mx, y2 - 3 - ah / 2, text="탐험 중", fill=WHITE, font=font(8))
            if chk:
                bx, by = x2 - d - 3, y1 + d + 3
                cv.create_oval(bx - d, by - d, bx + d, by + d, fill=GREEN, outline=GREEN_LINE, width=1)
                cv.create_text(bx, by, text="✓", fill=WHITE, font=font(10))
            self._cells[pid] = (x1, y1, x2, y2)
        # 마우스가 올라간 포켓몬의 이름 (흰 말풍선)
        m = self._by_id.get(self._hover) if self._hover else None
        box = self._cells.get(self._hover) if m is not None else None
        if box:
            info = m.get("info") or {}
            name = "알" if m.get("isEgg") else info.get("name", m.get("species", "?"))
            tip = "%s  Lv.%s" % (name, "-" if m.get("isEgg") else m.get("level", "?"))
            f = K.tkfont_of(cv, font(9))
            tw = f.measure(tip) + s(20)
            tx = min(max(tw / 2 + 2, (box[0] + box[2]) / 2), w - tw / 2 - 2)
            ty = max(s(24), box[1] - 2)
            P.rpoly(cv, tx - tw / 2, ty - s(22), tx + tw / 2, ty, s(11), fill=RIM)
            P.rpoly(cv, tx - tw / 2 + 2, ty - s(22) + 2, tx + tw / 2 - 2, ty - 2, s(9), fill=WHITE)
            cv.create_text(tx, ty - s(11), text=tip, fill=INK, font=font(9))

    # ---------------- 요약 ----------------
    def _card(self, cv, x1, y1, x2, y2, fill=WHITE, line=SEG):
        """흰 카드 - 글을 다 쓴 뒤 그 뒤에 깐다 (맨 아래로 내린다)."""
        s = U.h
        b = P.rpoly(cv, x1 + 2, y1 + 2, x2 - 2, y2 - 2, s(8), fill=fill, tags=D)
        a = P.rpoly(cv, x1, y1, x2, y2, s(10), fill=line, tags=D)
        cv.tag_lower(b)
        cv.tag_lower(a)

    def _label(self, cv, x, y, text):
        cv.create_text(x, y, text=text, fill=LABEL, font=font(9), anchor="nw", tags=D)

    def _bar(self, cv, x1, y1, x2, y2, ratio, col, groove="#d6dce3"):
        r = (y2 - y1) // 2
        P.rpoly(cv, x1, y1, x2, y2, r, fill=groove, tags=D)
        fw = int((x2 - x1) * max(0.0, min(1.0, ratio)))
        if fw > 0:
            P.rpoly(cv, x1, y1, x1 + max(fw, y2 - y1), y2, r, fill=col, tags=D)

    def _paint_detail(self, top=False):
        """요약: 보라 머리(No · 이름 · Lv) · 무대 · 타입은 늘 위에, 그 아래는 쪽 하나."""
        self._job_d = None
        cv = self.dcv
        try:
            w, vh = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.delete("all")
        for b in (self.btn_hold, self.btn_unhold, self.btn_remember, self.btn_bond):
            b.hide()
        s = U.h
        d = self._d
        x1, x2 = 0, w - s(4)
        if not d:
            cv.create_text(w // 2, s(80), text="포켓몬을 고르세요", fill=INK2, font=font(12), anchor="n", tags=D)
            return
        y = 0
        # 보라 머리 (원작 요약 화면처럼 왼쪽에 무대 · 오른쪽에 No · 이름 · Lv · 분류 · 타입)
        stw = min(s(124), (x2 - x1) * 2 // 5)
        tx1 = x1 + s(10) + stw + s(10)
        tx2 = x2 - s(10)
        tw = tx2 - tx1
        ty = y + s(12)
        cv.create_text(tx1, ty, text=d["num"], fill="#e8e2ff", font=font(9), anchor="w", tags=D)
        lvw = K.tkfont_of(cv, font(12)).measure(d["lv"]) + s(22)
        lvh = K.tkfont_of(cv, font(12)).metrics("linespace") + s(6)
        ty += s(12)
        gw = s(24) if d.get("gender") else 0
        name_fg = d.get("name_fg") if not d.get("egg") else WHITE
        nm = DPX._clamp(cv, d["name"], font(14), tw - gw, 1)
        ny = ty + s(12)
        cv.create_text(tx1, ny + 2, text=nm, fill=PURPLE_SH, font=font(14), anchor="w", tags=D)
        t = cv.create_text(tx1, ny, text=nm, fill=name_fg or WHITE, font=font(14), anchor="w", tags=D)
        bb = cv.bbox(t)
        gender_at = (bb[2] + s(6) + s(9), ny) if (d.get("gender") and bb) else None
        ty = ny + s(14)
        lv_at = (tx1, ty)
        ty += lvh + s(6)
        if d.get("sub"):
            sub = DPX._clamp(cv, d["sub"], font(9), tw, 2)
            t2 = cv.create_text(tx1, ty, text=sub, fill="#efeaff", font=font(9), anchor="nw", tags=D)
            ty = cv.bbox(t2)[3] + s(6)
        ch = s(22)
        chips = []
        cx = tx1
        f9 = K.tkfont_of(cv, font(9))
        for label, col in d.get("chips") or []:
            cw = f9.measure(label) + s(18)
            if cx + cw > tx2 and cx > tx1:
                cx = tx1
                ty += ch + s(4)
            chips.append((cx, ty, cw, label, col))
            cx += cw + s(5)
        if chips:
            ty += ch
        hh = max(s(118), ty + s(10) - y)
        # 판을 먼저 깔고 (뒤로 내린다) 그 위에 글
        P.rpoly(cv, x1, y, x2, y + hh, s(12), fill=PURPLE_SH, tags=D + ("dhead",))
        P.grad_round(cv, x1, y, x2, y + hh - 3, s(12), PURPLE_TOP, PURPLE, tags=D + ("dhead",))
        cv.tag_lower("dhead")
        lx, ly = lv_at
        P.rpoly(cv, lx, ly, lx + lvw, ly + lvh, lvh // 2, fill=P.BAR_SH, tags=D)
        cv.create_text(lx + lvw // 2, ly + lvh // 2, text=d["lv"], fill=WHITE, font=font(12), tags=D)
        if gender_at:
            gx, gy = gender_at
            gr = s(9)
            cv.create_oval(gx - gr, gy - gr, gx + gr, gy + gr, fill=WHITE, outline="", tags=D)
            cv.create_text(gx, gy, text=d["gender"], fill=d.get("gender_fg", INK2), font=font(10), tags=D)
        for cx, cy, cw, label, col in chips:
            P.rpoly(cv, cx, cy, cx + cw, cy + ch, ch // 2, fill=P.mix(col, "#000000", 0.4), tags=D)
            P.rpoly(cv, cx + 2, cy + 2, cx + cw - 2, cy + ch - 2, ch // 2 - 2, fill=col, tags=D)
            ink, shd = _ink_on(col)
            if shd:
                cv.create_text(cx + cw // 2, cy + ch // 2 + 1, text=label, fill=shd, font=font(9), tags=D)
            cv.create_text(cx + cw // 2, cy + ch // 2, text=label, fill=ink, font=font(9), anchor="center", tags=D)
        # 무대: 옅은 하늘 → 연둣빛 + 연둣빛 발판 (배틀 장면과 같은 말)
        sx1, sy1, sx2, sy2 = x1 + s(10), y + s(10), x1 + s(10) + stw, y + hh - s(13)
        P.rpoly(cv, sx1, sy1, sx2, sy2, s(10), fill=P.mix(PURPLE_SH, "#000000", 0.2), tags=D)
        P.grad_round(cv, sx1 + 2, sy1 + 2, sx2 - 2, sy2 - 2, s(8), SKY_TOP, SKY_BOT, tags=D)
        cx, py = (sx1 + sx2) // 2, sy2 - s(16)
        rx, ry = (stw - s(16)) // 2, s(10)
        cv.create_oval(cx - rx, py - ry, cx + rx, py + ry, fill=PAD_SH, outline="", tags=D)
        cv.create_oval(cx - rx, py - ry, cx + rx, py + ry - 3, fill=PAD, outline="", tags=D)
        a = cv.create_image(cx, (sy1 + sy2) // 2, image=self.d_art.image or "", tags=D)
        b = cv.create_text(cx, (sy1 + sy2) // 2, text="" if self.d_art.image else self.d_art.text,
                           fill=tone(self.d_art.fg), font=font(11), tags=D)
        self.d_art.ids = (a, b)
        y += hh + s(10)
        if d.get("egg"):
            y = self._d_egg(cv, d, x1, x2, y)
        else:
            pages = [("info", "정보"), ("stats", "능력"), ("moves", "기술")]
            if self.bond.visible:
                pages.append(("mega", "메가진화"))
            if self._dpage not in dict(pages):
                self._dpage = "info"
            P.seg(cv, x1, y, x2 - x1, s(32), pages, self._dpage, "dpg", self._pick_dpage, spec=font(11))
            cv.tag_bind("dpg", "<Enter>", lambda _e: cv.configure(cursor="hand2"))
            cv.tag_bind("dpg", "<Leave>", lambda _e: cv.configure(cursor=""))
            y += s(32) + s(10)
            y = {"info": self._d_info, "stats": self._d_stats, "moves": self._d_moves,
                 "mega": self._d_bond}[self._dpage](cv, d, x1, x2, y)
        total = y + s(12)
        cv.configure(scrollregion=(0, 0, w, max(total, vh)))
        if top:
            cv.yview_moveto(0)
        for b in (self.btn_hold, self.btn_unhold, self.btn_remember, self.btn_bond):
            if b.box:
                b.draw()

    def _d_info(self, cv, d, x1, x2, y):
        s = U.h
        p = s(10)
        cx1, cx2 = x1 + p, x2 - p
        iw = cx2 - cx1
        for title, name, note in (("특성", d["ability"], d["ability_note"]), ("성격", d["nature"], d["nature_note"])):
            y0 = y
            y += p
            self._label(cv, cx1, y, title)
            yy = self._wrap(cv, cx1 + s(40), y, name, font(10), width=iw - s(40))
            yy = self._wrap(cv, cx1 + s(40), yy + 2, note, font(9), fill=INK2, width=iw - s(40))
            self._card(cv, x1, y0, x2, yy + p)
            y = yy + p + s(6)
        # 지닌 도구
        y0 = y
        y += p
        self._label(cv, cx1, y, "도구")
        bw1, bw2 = self.btn_hold.want_width(s(18)), self.btn_unhold.want_width(s(18))
        self.btn_unhold.layout(cx2 - bw2, y - s(5), cx2, y + s(23))
        self.btn_hold.layout(cx2 - bw2 - s(6) - bw1, y - s(5), cx2 - bw2 - s(6), y + s(23))
        y += s(28)
        if d["held"]:
            ph = item_icons.photo(d["held"], 24)
            if ph is not None:
                cv.create_image(cx1 + s(14), y + s(10), image=ph, tags=D)
        yy = self._wrap(cv, cx1 + s(40), y, d["held_text"], font(9), fill=INK if d["held"] else INK2,
                        width=iw - s(40))
        self._card(cv, x1, y0, x2, yy + p)
        y = yy + p + s(6)
        # 경험치 · 친밀도
        y0 = y
        y += p
        ratio, text = d["exp"]
        self._label(cv, cx1, y, "경험치")
        cv.create_text(cx2, y, text=text, fill=INK2, font=font(8), anchor="ne", tags=D)
        y += s(20)
        self._bar(cv, cx1, y, cx2, y + s(10), ratio, BLUE)
        y += s(16)
        if d.get("friend"):
            hearts, num, msg = d["friend"]
            y += s(4)
            self._label(cv, cx1, y, "친밀도")
            cv.create_text(cx1 + s(48), y - 1, text=hearts, fill="#e04888", font=font(10), anchor="nw", tags=D)
            cv.create_text(cx2, y, text=num, fill=INK2, font=font(9), anchor="ne", tags=D)
            y = self._wrap(cv, cx1, y + s(20), msg, font(9), fill=INK2, width=iw)
        self._card(cv, x1, y0, x2, y + p)
        y += p + s(6)
        if d.get("evo"):
            y0 = y
            y += p
            self._label(cv, cx1, y, "진화")
            y += s(20)
            for line in d["evo"]:
                y = self._wrap(cv, cx1, y, line, font(9), width=iw) + s(3)
            self._card(cv, x1, y0, x2, y + p - s(3))
            y += p
        return y

    def _d_stats(self, cv, d, x1, x2, y):
        s = U.h
        p = s(10)
        cx1, cx2 = x1 + p, x2 - p
        iw = cx2 - cx1
        y0 = y
        y = self._wrap(cv, cx1, y + p, d["ivsum"], font(9), fill="#2c8a3c", width=iw) + s(10)
        for label, v, iv, hy, mx in d["rows"]:
            cv.create_text(cx1, y, text=label, fill=INK2, font=font(9), anchor="nw", tags=D)
            cv.create_text(cx1 + s(84), y, text=str(v), fill=INK, font=font(10), anchor="ne", tags=D)
            col = GREEN if iv == 31 else ("#ffa63a" if iv >= 26 else "#9aa2b0")
            self._bar(cv, cx1 + s(92), y + 3, cx2 - s(66), y + s(13), v / float(mx or 1), col)
            cv.create_text(cx2, y, text="개체 %d%s" % (iv, "✦" if hy else ""),
                           fill="#2c8a3c" if iv == 31 else INK2, font=font(8), anchor="ne", tags=D)
            y += s(24)
        y = self._wrap(cv, cx1, y + s(2), d["evsum"], font(9), fill=INK2, width=iw)
        self._card(cv, x1, y0, x2, y + p)
        return y + p + s(6)

    def _d_moves(self, cv, d, x1, x2, y):
        """기술 넷 - 배틀 화면의 기술 단추처럼 타입 빛깔 캡슐 (이름 / 타입 · 위력 · 명중 · PP)."""
        s = U.h
        dex = self.app.dex
        mh = s(48)
        g = s(3)
        for i, (mv, md) in enumerate(d["moves"]):
            col = U.TYPE_COLOR.get((md or {}).get("type"), "#a0a0a8")
            tg = D + ("mv%d" % i,)
            picked = bool(self._move_pick and self._move_pick[0] == i)
            r = min(s(16), mh // 2)
            mx1, mx2 = x1 + g, x2 - g
            if picked:
                P.glow(cv, mx1, y, mx2, y + mh, r, tags=tg)
            rim = RIM if picked else P.mix(col, "#000000", 0.45)
            P.rpoly(cv, mx1, y + 3, mx2, y + mh, r, fill=P.mix(rim, "#000000", 0.25), tags=tg)
            P.rpoly(cv, mx1, y, mx2, y + mh - 3, r, fill=rim, tags=tg)
            P.grad_round(cv, mx1 + 2, y + 2, mx2 - 2, y + mh - 5, max(0, r - 2), P.mix(col, WHITE, 0.22), col,
                         tags=tg)
            ink, shd = _ink_on(col)
            sub = "%s · %s" % (dex.type_name((md or {}).get("type")) if dex else "", MT.short_line(md))
            sub = DPX._clamp(cv, sub, font(9), mx2 - mx1 - s(32), 1)
            for (tx, ty, text, spec) in ((mx1 + s(16), y + s(15), mv, font(11)),
                                         (mx1 + s(16), y + mh - s(15), sub, font(9))):
                if shd:
                    cv.create_text(tx, ty + 1, text=text, fill=shd, font=spec, anchor="w", tags=tg)
                cv.create_text(tx, ty, text=text, fill=ink, font=spec, anchor="w", tags=tg)
            cv.tag_bind("mv%d" % i, "<Button-1>", lambda _e, n=i, dd=md, t=mv: self.pick_move(n, dd, t))
            cv.tag_bind("mv%d" % i, "<Enter>", lambda _e: cv.configure(cursor="hand2"))
            cv.tag_bind("mv%d" % i, "<Leave>", lambda _e: cv.configure(cursor=""))
            y += mh + s(7)
        p = s(10)
        cx1, cx2 = x1 + p, x2 - p
        iw = cx2 - cx1
        if self._move_pick:
            _i, md, name = self._move_pick
            y0 = y + s(2)
            yy = self._wrap(cv, cx1, y0 + p, MT.stat_line(md, name or "?"), font(9), fill="#b05a10", width=iw)
            yy = self._wrap(cv, cx1, yy + s(3), MT.desc(md), font(9), fill=INK2, width=iw)
            self._card(cv, x1, y0, x2, yy + p)
            y = yy + p + s(8)
        elif d["moves"]:
            y = self._wrap(cv, x1 + s(4), y + s(2), "기술을 누르면 설명이 나옵니다.", font(9), fill=DIM,
                           width=x2 - x1 - s(8)) + s(6)
        if d.get("pending"):
            y0 = y
            yy = self._wrap(cv, cx1, y0 + p, d["pending"], font(9), fill="#2c8a3c", width=iw)
            self._card(cv, x1, y0, x2, yy + p, fill=CHECK_FILL, line="#b8dcc2")
            y = yy + p + s(8)
        rw = self.btn_remember.want_width(s(24))
        self.btn_remember.layout(x2 - rw, y + s(2), x2, y + s(34))
        return y + s(40)

    def _d_bond(self, cv, d, x1, x2, y):
        s = U.h
        p = s(10)
        cx1, cx2 = x1 + p, x2 - p
        iw = cx2 - cx1
        b = self.bond
        if b.btn_spec:
            self.btn_bond.configure(text=b.btn_spec[0], state="normal")
            bw = self.btn_bond.want_width(s(24))
            self.btn_bond.layout(x2 - bw, y, x2, y + s(34))
            y += s(42)
        if b.lines:
            y0 = y
            y += p
            for row in b.lines:
                if row[0] == "kv":
                    _k, label, val, col = row
                    self._label(cv, cx1, y, label)
                    y = self._wrap(cv, cx1 + s(48), y, val, font(9),
                                   fill=tone(col) if col != BD.MEGA else "#6a3ac8", width=iw - s(48)) + s(6)
                elif row[0] == "bar":
                    _k, label, num, ratio, col = row
                    y2 = self._wrap(cv, cx1, y, label, font(9), width=iw - s(60))
                    cv.create_text(cx2, y, text=num, fill=INK2, font=font(8), anchor="ne", tags=D)
                    self._bar(cv, cx1, y2 + 4, cx2, y2 + s(13), ratio, col)
                    y = y2 + s(20)
                else:
                    _k, text, col = row
                    y = self._wrap(cv, cx1, y, text, font(9), fill="#6a3ac8" if col == BD.MEGA else tone(col),
                                   width=iw) + s(6)
            self._card(cv, x1, y0, x2, y + p - s(4))
            y += p + s(4)
        dex = self.app.dex
        for pv in b.previews:
            y0 = y
            y += p
            t = cv.create_text(cx1, y, text=pv["name"], fill="#6a3ac8", font=font(11), anchor="nw", tags=D)
            bb = cv.bbox(t)
            cv.create_text((bb[2] if bb else cx1) + s(8), y + 2, text="메가진화하면", fill=INK2, font=font(8),
                           anchor="nw", tags=D)
            y += s(24)
            cx = cx1
            th = s(20)
            for tp in pv["types"]:
                label = dex.type_name(tp) if dex else tp
                f = K.tkfont_of(cv, font(8))
                cw = f.measure(label) + s(16)
                col = U.TYPE_COLOR.get(tp, "#a0a0a8")
                P.rpoly(cv, cx, y, cx + cw, y + th, th // 2, fill=col, tags=D)
                ink, shd = _ink_on(col)
                if shd:
                    cv.create_text(cx + cw // 2, y + th // 2 + 1, text=label, fill=shd, font=font(8), tags=D)
                cv.create_text(cx + cw // 2, y + th // 2, text=label, fill=ink, font=font(8), anchor="center",
                               tags=D)
                cx += cw + s(4)
            y += th + s(6)
            if pv.get("abilityKr"):
                y = self._wrap(cv, cx1, y, "특성 %s (%s)" % (pv["abilityKr"], "바뀜" if pv["abilityChanged"] else "그대로"),
                               font(9), width=iw) + s(4)
            for _k, label, now, after, dlt in pv["rows"]:
                cv.create_text(cx1, y, text=label, fill=INK2, font=font(8), anchor="nw", tags=D)
                cv.create_text(cx1 + s(110), y, text="%d → %d" % (now, after), fill=INK if dlt else DIM,
                               font=font(8), anchor="ne", tags=D)
                cv.create_text(cx2, y, text=BD.delta_text(dlt),
                               fill="#2c8a3c" if dlt > 0 else ("#d02828" if dlt < 0 else DIM), font=font(8),
                               anchor="ne", tags=D)
                y += s(17)
            self._card(cv, x1, y0, x2, y + p - s(4))
            y += p + s(4)
        return y

    def _d_egg(self, cv, d, x1, x2, y):
        s = U.h
        p = s(10)
        cx1, cx2 = x1 + p, x2 - p
        iw = cx2 - cx1
        from common.korean import natural
        y0 = y
        y += p
        self._label(cv, cx1, y, "알의 상태")
        y = self._wrap(cv, cx1, y + s(20), d["mood"], font(9), width=iw) + s(8)
        self._bar(cv, cx1, y, cx2, y + s(10), d["ratio"], d["egg_color"])
        y += s(16)
        y = self._wrap(cv, cx1, y, d["time"], font(9), fill=INK2, width=iw) + s(4)
        y = self._wrap(cv, cx1, y, d["left"], font(10), width=iw)
        self._card(cv, x1, y0, x2, y + p)
        y += p + s(6)
        y0 = y
        y += p
        self._label(cv, cx1, y, "자라는 곳")
        y = self._wrap(cv, cx1, y + s(20), d["where"], font(9), fill="#2c8a3c" if d["where_ok"] else "#d02828",
                       width=iw) + s(4)
        y = self._wrap(cv, cx1, y, natural("알도 데리고 다니는 여섯 자리 중 하나를 차지합니다. 알을 데리고 다니는 동안에는 "
                                           "포켓몬이 그만큼 적게 따라다닙니다."), font(8), fill=DIM, width=iw) + s(4)
        if d.get("day"):
            y = self._wrap(cv, cx1, y, "받은 날 %s" % d["day"], font(8), fill=DIM, width=iw)
        self._card(cv, x1, y0, x2, y + p)
        return y + p + s(6)


# 지닌 도구 고르기 창은 DP 의 것 (빛깔은 derive 가 플라티나로 옮긴다) - 스킨은 box 모듈에서 HeldPicker 를 찾는다.
from ..dp.box import HeldPicker, _clamp  # noqa: E402,F401
