# -*- coding: utf-8 -*-
"""소드·실드 테마 - 포켓몬 (PC 박스). 소드실드의 '박스' 화면을 시안 K 의 언어로:

    ┌ 남색 빗금 바탕 (옅게 - 배틀처럼 눈이 편하게) + 하늘 · 분홍 작은 모서리 ─────────────────────────────┐
    │ ( 파티 1 ▾ )     (◀) (        박스 1    8/30 ▾        ) (▶)  [이름 바꾸기] [새로고침] ┌ 흰 요약 카드 ─────┐ │
    │ ( 타입: 전체 ▾ ) (찾기: ________________ ) (도감)(이름)(Lv)(종족값)                  │ 남색 무대 · 도트  │ │
    │ ╔ 흰 테 ═══╗ ╔ 흰 테 · 남색 벽지(옅은 빗금) ═══════════════════╗                     │ 이름 · (Lv) · 타입 │ │
    │ ║ 파티 6칸 ║ ║  둥근 흰 칸 6 × 5 (빈 칸은 남빛) · 고른 칸 분홍 테 ║                     │ (정보)(능력)(기술)…│ │
    │ ╚══════════╝ ╚══════════════════════════════════════════════════╝                     │ 쪽 내용            │ │
    │ ((박스로 보내기)) [별명 짓기] [박스 옮기기] [색 고르기] [놓아주기]                    │                    │ │
    │ ( 보유 14마리 · 데리고 다니는 중 6마리 )                                              └────────────────────┘ │
    └──────────────────────────────────────────────────────────────────────────────────────────────────────────┘

소드실드 박스처럼 요약은 오른쪽, 파티는 박스 왼쪽 세로 줄, 박스 이름은 위의 긴 알약 (◀ ▶).
판은 시안의 '두꺼운 흰 테 둥근 판', 단추는 알약 (주된 일 분홍 · 흰 테), 쪽 · 줄 세우기는 같은 폭 알약 (고른 것 분홍),
고른 칸은 분홍 테, 끌어 놓을 칸은 하늘 테. 기술은 배틀 기술 목록처럼 왼쪽 타입 빛깔 칸 + 흰 막대.

**동작은 DP 박스(그 밑의 기본 창) 그대로다** - 박스 넘기기 · 고르기 드롭다운 · 거르기 · 찾기 · 줄 세우기 · 파티 프리셋 ·
여러 마리 고르기 · 끌어서 맞바꾸기 · 별명 · 데리고 다니기 · 놓아주기 · 지닌 도구 · 기술 떠올리기 · 유대 미션.
칠하는 고리(_paint · _paint_right · _paint_party_slots · _paint_grid · _paint_detail · _d_*)만 바꾼다.
"""
import tkinter as tk

from common import legends as L
from common import movetext as MT

from ... import box_filter, item_icons
from ... import ui_bond as BD
from ... import ui_common as U
from ..dp import font, tone
from ..dp import box as DPX
from ..dp import kit as K
from ..dp.scene import T
from . import CYAN, CYAN_L, DESC, DIMK, LINE_P, MAG, MAG_HI, NAVY, NAVY2, NAVY3, ON_NAVY_DIM, PAPER, PAPER2
from . import _sw as S

D = DPX.D

WALL = NAVY2                 # 박스 벽지 (남색 - 칸 · 도트가 먼저 보이게)
WALL_BAND = "#2c3160"        # 벽지의 옅은 빗금
EMPTY = "#353b6c"            # 빈 칸 (소드실드 박스의 비치는 빈 칸)
TRACK = "#e2e4ef"            # 막대 홈
SEL_FILL = "#fde8f2"         # 고른 칸 바탕 (옅은 분홍)
GOOD = "#2c8a3c"
MEGA = "#7a4ad0"


def _hand_on(cv, tag):
    cv.tag_bind(tag, "<Enter>", lambda _e: cv.configure(cursor="hand2"))
    cv.tag_bind(tag, "<Leave>", lambda _e: cv.configure(cursor=""))


def _bar(cv, x1, y1, x2, h, ratio, color, tags=D):
    """둥근 막대: 옅은 홈 + 빛깔 (r 은 높이의 반)."""
    K.rrect(cv, x1, y1, x2, y1 + h, h // 3, fill=TRACK, tags=tags)
    fw = int((x2 - x1) * max(0.0, min(1.0, ratio)))
    if fw > 0:
        K.rrect(cv, x1, y1, x1 + max(fw, h), y1 + h, h // 3, fill=color, tags=tags)


def _wall(cv, x1, y1, x2, y2, tags=()):
    """박스 벽지: 남색 + 아주 옅은 빗금 (칸 사이로만 보인다)."""
    cv.create_rectangle(x1, y1, x2, y2, fill=WALL, outline="", tags=tags)
    step = U.h(22)
    w, h = x2 - x1, y2 - y1
    k = -2 * step
    while k < w + h:
        a, b = k + step, k + 2 * step
        clip = K._clip_poly([(a, 0), (b, 0), (b - h, h), (a - h, h)], 0, 0, w, h)
        if len(clip) >= 3:
            flat = []
            for px, py in clip:
                flat += [x1 + px, y1 + py]
            cv.create_polygon(flat, fill=WALL_BAND, outline="", tags=tags)
        k += 2 * step


def _frame(cv, x1, y1, x2, y2, inner=WALL, tags=()):
    """시안의 두꺼운 흰 테 둥근 판 (안은 남색 벽지 자리)."""
    b = U.h(4)
    K.rrect(cv, x1, y1, x2, y2, 10, fill="#ffffff", tags=tags)
    K.rrect(cv, x1 + b, y1 + b, x2 - b, y2 - b, 7, fill=inner, tags=tags)


class SwArt(DPX.ArtSlot):
    """요약 무대(남색)의 도트 자리 - 도트가 없을 때의 글은 남색 위 옅은 글씨로."""

    def configure(self, image=None, text=None, fg=None, **_kw):
        DPX.ArtSlot.configure(self, image=image, text=text, fg=None)
        if self.ids:
            try:
                self.view.dcv.itemconfigure(self.ids[1], fill=ON_NAVY_DIM)
            except tk.TclError:
                pass

    config = configure


class BoxWindow(DPX.BoxWindow):

    DW_PX = 330            # 요약 카드 폭
    PARTY_PX = 150         # 파티 줄 폭

    def _build(self):
        DPX.BoxWindow._build(self)
        self.cv.configure(bg=NAVY)
        self.win.configure(bg=NAVY)
        self.dframe.configure(bg=PAPER, highlightthickness=0)
        self.dcv.configure(bg=PAPER)
        self.dsb.configure(bg=PAPER)
        self.dcv.pack_configure(padx=(U.h(12), U.h(2)), pady=U.h(10))
        self.gframe.configure(bg=WALL)
        self.gcv.configure(bg=WALL)
        self.gsb.configure(bg=WALL)
        S.flat_entry(self.find_box)
        self.d_art = SwArt(self)
        for b, kind in ((self.btn_party, "go"), (self.btn_nick, "white"), (self.btn_move, "white"),
                        (self.btn_tint, "white"), (self.btn_release, "red"),
                        (self.btn_multi_move, "go"), (self.btn_multi_all, "white"),
                        (self.btn_multi_clear, "white"), (self.btn_multi_done, "white"),
                        (self.btn_prev, "navy"), (self.btn_next, "navy"),
                        (self.btn_rename, "white"), (self.btn_party_name, "white"), (self.btn_reload, "white"),
                        (self.btn_hold, "go"), (self.btn_unhold, "white"), (self.btn_remember, "go"),
                        (self.btn_bond, "go")):
            S.restyle(b, kind)

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
        S.backdrop(cv, 0, 0, W, H, tl=s(90), br=s(70), tags=T)
        DW = s(self.DW_PX)
        # 오른쪽 흰 요약 카드 (소드실드 박스의 오른쪽 요약)
        cx1, cx2 = W - s(14) - DW, W - s(14)
        S.card(cv, cx1, s(10), cx2, H - s(10), tags=T)
        b = s(6)
        self._place("detail", self.dframe, cx1 + b, s(10) + b, DW - 2 * b, H - s(20) - 2 * b)
        self._paint_right(cv, s(14), cx1 - s(18), H)

    def _paint_right(self, cv, x0, x2, H):
        """(이름은 DP 그대로 - 요약 카드 왼쪽의 박스 쪽 전부를 그린다.)"""
        s = U.h
        PW = s(self.PARTY_PX)
        gx1 = x0 + PW + s(12)
        y = s(10)
        bh = s(36)
        # 1) 파티 고르기 · (◀ 박스 이름 ▶) · 이름 바꾸기  (새로고침은 아래 글상자 오른쪽 끝)
        self._paint_preset(cv, x0, y, x0 + PW, y + bh)
        aw = s(38)
        rw = self.btn_rename.want_width(s(26))
        self.btn_rename.layout(x2 - rw, y, x2, y + bh)
        self.btn_prev.layout(gx1, y, gx1 + aw, y + bh)
        nx1 = gx1 + aw + s(6)
        nx2 = max(nx1 + s(110), x2 - rw - s(12) - aw)
        self.btn_next.layout(nx2 + s(6), y, nx2 + s(6) + aw, y + bh)
        tg = T + ("page",)
        K.rrect(cv, nx1, y, nx2, y + bh, bh // 3, fill="#ffffff", tags=tg)
        text = DPX._clamp(cv, self._page_text, font(12), nx2 - nx1 - s(20), 1)
        cv.create_text((nx1 + nx2) // 2, y + bh // 2, text=text, fill=NAVY, font=font(12), anchor="center", tags=tg)
        self._boxes["page"] = (nx1, y, nx2, y + bh)
        cv.tag_bind("page", "<Button-1>", lambda _e: self.open_box_menu())
        self._hand("page")
        # 2) 타입 (파티 줄과 같은 폭) · 찾기 · 줄 세우기
        y += bh + s(6)
        th = s(30)
        tt = DPX._clamp(cv, self.btn_type.text, font(10), PW - s(30), 1) + " ▾"
        S.pill(cv, x0, y, x0 + PW, y + th, tt, spec=font(10), tags=T + ("tsel",))
        self._boxes["type"] = (x0, y, x0 + PW, y + th)
        cv.tag_bind("tsel", "<Button-1>", lambda _e: self._open_type_menu())
        self._hand("tsel")
        f10 = K.tkfont_of(cv, font(10))
        seg_w = sum(f10.measure(lb) + s(16) for _k, lb in DPX.SORTS) + s(5) * (len(DPX.SORTS) - 1)
        sx1 = x2 - seg_w
        S.seg(cv, sx1, y, x2, th, DPX.SORTS, self.sort, "bsort", self.set_sort, spec=font(10), hand=self._hand)
        ex = S.field(cv, gx1, y, sx1 - s(8), y + th, "찾기", tags=T)
        self._place("find", self.find_box, ex, y + s(4), max(s(60), sx1 - s(8) - ex - s(16)), th - s(8))
        # 3) 파티 줄 + 박스 칸 (흰 테 판 둘)
        y += th + s(8)
        BOT = s(84)
        gy2 = H - BOT
        self._paint_party_slots(cv, x0, y, x0 + PW, gy2)
        _frame(cv, gx1, y, x2, gy2, tags=T)
        ins = s(6)
        self._place("grid", self.gframe, gx1 + ins, y + ins, x2 - gx1 - 2 * ins, gy2 - y - 2 * ins)
        # 4) 단추 줄 + 글상자
        by = gy2 + s(8)
        bh2 = s(36)
        if self.multi:
            btns = [self.btn_multi_move, self.btn_multi_all, self.btn_multi_clear, self.btn_multi_done]
            hide = [self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release]
        else:
            btns = [self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release]
            hide = [self.btn_multi_move, self.btn_multi_all, self.btn_multi_clear, self.btn_multi_done]
        for b in hide:
            b.hide()
        x = x0
        for b in btns:
            w = b.want_width(s(30))
            b.layout(x, by, x + w, by + bh2)
            x += w + s(6)
        text, color = self.msg
        shown = text or self._count_text
        my1, my2 = by + bh2 + s(5), H - s(8)
        K.rrect(cv, x0, my1, x2, my2, (my2 - my1) // 3, fill="#ffffff", tags=T)
        bw = self.btn_reload.want_width(s(24))
        self.btn_reload.layout(x2 - s(4) - bw, my1 + s(3), x2 - s(4), my2 - s(3))
        self._msg_w = max(40, x2 - x0 - bw - s(40))
        tid = K.text(cv, x0 + s(16), (my1 + my2) // 2, shown or "", font(11),
                     fill=(tone(color) if color else (NAVY if text else DESC)), anchor="w", width=self._msg_w,
                     tags=T)[1]
        self._msg_ids = (None, tid)

    def _paint_preset(self, cv, x1, y1, x2, y2):
        """파티 줄 위: 파티 프리셋 고르기 알약 (프리셋이 없으면 '데리고 다니는' 남색 띠)."""
        s = U.h
        rows = self.party_presets()
        self.btn_party_name.hide()
        if not rows:
            K.rrect(cv, x1, y1, x2, y2, (y2 - y1) // 3, fill=NAVY2, tags=T)
            cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text="데리고 다니는", fill=ON_NAVY_DIM, font=font(10),
                           anchor="center", tags=T)
            self._boxes.pop("preset", None)
            return
        name = next((p.get("name") or "파티 %d" % p.get("no") for p in rows if p.get("no") == self.party_active()),
                    "파티")
        label = DPX._clamp(cv, name, font(10), x2 - x1 - s(34), 1) + " ▾"
        S.pill(cv, x1, y1, x2, y2, label, on=True, spec=font(10), tags=T + ("preset",))
        self._boxes["preset"] = (x1, y1, x2, y2)
        cv.tag_bind("preset", "<Button-1>", lambda _e: self._open_preset_menu())
        self._hand("preset")

    def _paint_party_slots(self, cv, x1, y1, x2, y2):
        """데리고 다니는 포켓몬 여섯 자리 - 흰 테 판 안의 둥근 흰 칸 (소드실드 박스 왼쪽의 파티 줄)."""
        s = U.h
        _frame(cv, x1, y1, x2, y2, tags=T)
        n = 6
        gap = s(4)
        pad = s(7)
        top, bot = y1 + pad, y2 - pad
        sh = (bot - top - gap * (n - 1)) / float(n)
        self._pslots = {}
        for i in range(n):
            sy1 = top + i * (sh + gap)
            sy2 = sy1 + sh
            sx1, sx2 = x1 + pad, x2 - pad
            m = self._party_list[i] if i < len(self._party_list) else None
            mid = (sy1 + sy2) / 2
            if m is None:
                K.rrect(cv, sx1, sy1, sx2, sy2, 7, fill=EMPTY, tags=T)
                cv.create_text((sx1 + sx2) / 2, mid, text="빈 자리", fill=ON_NAVY_DIM, font=font(9), tags=T)
                continue
            pid = m["id"]
            sel, tgt, chk, hov = pid == self.sel, pid == self._target, pid in self.checked, pid == self._hover
            tg = T + ("pslot",)
            self._cell(cv, sx1, sy1, sx2, sy2, sel, tgt, chk, hov, tg)
            ph = self._thumb(m)
            if ph is not None:
                cv.create_image(sx1 + s(22), mid, image=ph, tags=tg)
            info = m.get("info") or {}
            name = "알" if m.get("isEgg") else info.get("name", m.get("species", "?"))
            if m.get("shiny"):
                name = "★" + name
            cv.create_text(sx1 + s(44), mid - s(8), text=DPX._clamp(cv, name, font(10), sx2 - sx1 - s(50), 1),
                           fill=NAVY, font=font(10), anchor="w", tags=tg)
            cv.create_text(sx1 + s(44), mid + s(9), anchor="w", font=font(9), fill=DESC, tags=tg,
                           text=("%d%%" % box_filter.egg_progress(m.get("egg") or {})[0]) if m.get("isEgg")
                           else "Lv.%d" % m.get("level", 0))
            if chk:
                self._check(cv, sx2, sy2, tg)
            self._pslots[pid] = (sx1, sy1, sx2, sy2)
        self._hand("pslot")

    def _cell(self, cv, x1, y1, x2, y2, sel, tgt, chk, hov, tags=()):
        """둥근 흰 칸 하나. 고른 칸 = 분홍 테 + 옅은 분홍, 끌어 놓을 칸 = 하늘 테, 고른(체크) 칸 = 옅은 하늘."""
        fill = SEL_FILL if sel else (CYAN_L if (chk or tgt) else ("#eef0fa" if hov else "#ffffff"))
        if sel or tgt:
            g = U.h(3)
            K.rrect(cv, x1 - 1, y1 - 1, x2 + 1, y2 + 1, 8, fill=MAG if sel else CYAN, tags=tags)
            K.rrect(cv, x1 + g - 1, y1 + g - 1, x2 - g + 1, y2 - g + 1, 6, fill=fill, tags=tags)
        else:
            K.rrect(cv, x1, y1, x2, y2, 7, fill=fill, outline=MAG_HI if hov else "",
                    width=max(1, U.h(2)) if hov else 1, tags=tags)

    def _check(self, cv, x2, y2, tags=()):
        """여러 마리 고르기의 고름 표시 - 칸 오른쪽 아래 분홍 동그라미 · 흰 ✓ (도트 위에 그린다)."""
        r = U.h(8)
        cx, cy = x2 - r - U.h(2), y2 - r - U.h(2)
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=MAG, outline="#ffffff", width=2, tags=tags)
        cv.create_text(cx, cy, text="✓", fill="#ffffff", font=font(9), anchor="center", tags=tags)

    # ---------------- 박스 칸 (6 × 5) ----------------
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
        pad = s(6)
        cw = (w - pad) / float(cols)
        ch = max(s(50), (h - pad) / 5.0)            # 30칸이 한 번에 보이게 (980 x 620 에서도 - 재서 맞춤)
        total = max(h, int(ch * rows + pad))
        cv.configure(scrollregion=(0, 0, w, total))
        _wall(cv, 0, 0, w, total)
        self._cells = {}
        for i in range(rows * cols):
            r, c = divmod(i, cols)
            x1, y1 = pad + c * cw, pad + r * ch
            x2, y2 = x1 + cw - pad, y1 + ch - pad
            if i >= n:
                K.rrect(cv, x1, y1, x2, y2, 7, fill=EMPTY)
                continue
            m = self._page_mons[i]
            pid = m["id"]
            sel, tgt, chk, hov = pid == self.sel, pid == self._target, pid in self.checked, pid == self._hover
            self._cell(cv, x1, y1, x2, y2, sel, tgt, chk, hov)
            ph = self._thumb(m)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if ph is not None:
                cv.create_image(mx, my, image=ph)
            else:
                cv.create_oval(mx - 6, my - 6, mx + 6, my + 6, fill=PAPER2, outline=LINE_P)
            if m.get("shiny"):
                cv.create_text(x1 + s(6), y1 + s(3), text="★", fill="#d0a000", font=font(9), anchor="nw")
            kind = None if m.get("isEgg") else L.kind_of(m.get("num"))
            if kind:
                cv.create_text(x2 - s(5), y1 + s(3), text="◆" if kind == "legendary" else "✦", fill="#a050c0",
                               font=font(8), anchor="ne")
            if m.get("away"):
                cv.create_text(mx, y2 - s(3), text="탐험 중", fill="#2860c0", font=font(8), anchor="s")
            if chk:
                self._check(cv, x2, y2)
            self._cells[pid] = (x1, y1, x2, y2)
        # 마우스가 올라간 포켓몬의 이름 (남색 알약)
        m = self._by_id.get(self._hover) if self._hover else None
        box = self._cells.get(self._hover) if m is not None else None
        if box:
            info = m.get("info") or {}
            name = "알" if m.get("isEgg") else info.get("name", m.get("species", "?"))
            tip = "%s  Lv.%s" % (name, "-" if m.get("isEgg") else m.get("level", "?"))
            f = K.tkfont_of(cv, font(9))
            tw = f.measure(tip) + s(20)
            th = s(22)
            tx = min(max(tw / 2 + 2, (box[0] + box[2]) / 2), w - tw / 2 - 2)
            ty = max(th + 2, box[1] - 2)
            K.rrect(cv, tx - tw / 2, ty - th, tx + tw / 2, ty, th // 3, fill=NAVY, outline="#ffffff", width=2)
            cv.create_text(tx, ty - th / 2, text=tip, fill="#ffffff", font=font(9))

    # ---------------- 요약 카드 ----------------
    def _paint_detail(self, top=False):
        """요약: 남색 무대(도트) · 이름 · Lv 알약 · 타입은 늘 위에, 그 아래는 쪽 하나 (같은 폭 알약으로 고른다)."""
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
            cv.create_text(w // 2, s(80), text="포켓몬을 고르세요", fill=DESC, font=font(12), anchor="n", tags=D)
            return
        y = 0
        # 무대 (가방의 남색 그림 칸처럼)
        sh = s(122)
        K.rrect(cv, x1, y, x2, y + sh, 9, fill=NAVY2, tags=D)
        mid = (x1 + x2) // 2
        cv.create_oval(mid - s(62), y + sh - s(28), mid + s(62), y + sh - s(10), fill="#343a6c", outline="",
                       tags=D)
        num_w = K.tkfont_of(cv, font(9)).measure(d["num"]) + s(18)
        K.rrect(cv, x1 + s(8), y + s(8), x1 + s(8) + num_w, y + s(28), 6, fill=NAVY, tags=D)
        cv.create_text(x1 + s(8) + num_w // 2, y + s(18), text=d["num"], fill=ON_NAVY_DIM, font=font(9),
                       anchor="center", tags=D)
        a = cv.create_image(mid, y + sh // 2 + s(2), image=self.d_art.image or "", tags=D)
        b = cv.create_text(mid, y + sh // 2, text="" if self.d_art.image else self.d_art.text,
                           fill=ON_NAVY_DIM, font=font(11), tags=D)
        self.d_art.ids = (a, b)
        y += sh + s(10)
        # 이름 · 성별 · Lv 알약
        lvf = font(11)
        lw = K.tkfont_of(cv, lvf).measure(d["lv"]) + s(20)
        lh = s(26)
        K.rrect(cv, x2 - lw, y, x2, y + lh, lh // 3, fill=NAVY, tags=D)
        cv.create_text(x2 - lw // 2, y + lh // 2, text=d["lv"], fill="#ffffff", font=lvf, anchor="center", tags=D)
        nm = DPX._clamp(cv, d["name"], font(15), x2 - lw - s(36), 1)
        t = cv.create_text(x1 + s(2), y + lh // 2, text=nm, fill="#b07800" if d["m"].get("shiny") else NAVY,
                           font=font(15), anchor="w", tags=D)
        bb = cv.bbox(t)
        if d.get("gender") and bb:
            cv.create_text(bb[2] + s(6), y + lh // 2, text=d["gender"], fill=d.get("gender_fg", DESC),
                           font=font(12), anchor="w", tags=D)
        y += lh + s(6)
        if d.get("sub"):
            _a, t2 = K.text(cv, x1 + s(2), y, d["sub"], font(9), fill=DESC, tags=D, width=x2 - x1 - s(4))
            y = cv.bbox(t2)[3] + s(6)
        cx = x1
        for label, col in d.get("chips") or []:
            f = K.tkfont_of(cv, font(9))
            cw = f.measure(label) + s(20)
            if cx + cw > x2 and cx > x1:
                cx = x1
                y += s(28)
            K.rrect(cv, cx, y, cx + cw, y + s(22), 7, fill=col, tags=D)
            cv.create_text(cx + cw // 2, y + s(11), text=label, fill=K.look_of(col)[3], font=font(9),
                           anchor="center", tags=D)
            cx += cw + s(5)
        y += s(32)
        if d.get("egg"):
            y = self._d_egg(cv, d, x1, x2, y)
        else:
            pages = [("info", "정보"), ("stats", "능력"), ("moves", "기술")]
            if self.bond.visible:
                pages.append(("mega", "메가진화"))
            if self._dpage not in dict(pages):
                self._dpage = "info"
            S.seg(cv, x1, y, x2, s(30), pages, self._dpage, "dpg", self._pick_dpage, spec=font(10),
                  hand=lambda tag: _hand_on(cv, tag))
            y += s(30) + s(12)
            y = {"info": self._d_info, "stats": self._d_stats, "moves": self._d_moves,
                 "mega": self._d_bond}[self._dpage](cv, d, x1 + s(2), x2 - s(2), y)
        total = y + s(12)
        cv.configure(scrollregion=(0, 0, w, max(total, vh)))
        if top:
            cv.yview_moveto(0)
        for b in (self.btn_hold, self.btn_unhold, self.btn_remember, self.btn_bond):
            if b.box:
                b.draw()

    def _wrap(self, cv, x, y, text, spec, fill=NAVY, width=100):
        t = cv.create_text(x, y, text=K.wrap(cv, text, spec, width), fill=fill, font=spec, anchor="nw", tags=D)
        b = cv.bbox(t)
        return b[3] if b else y

    def _label(self, cv, x, y, text):
        cv.create_text(x, y, text=text, fill=DIMK, font=font(9), anchor="nw", tags=D)

    def _d_info(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        ind = s(42)
        for title, name, note in (("특성", d["ability"], d["ability_note"]), ("성격", d["nature"], d["nature_note"])):
            self._label(cv, x1, y + 1, title)
            y = self._wrap(cv, x1 + ind, y, name, font(10), width=iw - ind)
            y = self._wrap(cv, x1 + ind, y + 2, note, font(9), fill=DESC, width=iw - ind) + s(12)
        # 지닌 도구
        self._label(cv, x1, y + s(7), "도구")
        bw1, bw2 = self.btn_hold.want_width(s(24)), self.btn_unhold.want_width(s(24))
        bh = s(30)
        self.btn_unhold.layout(x2 - bw2, y, x2, y + bh)
        self.btn_hold.layout(x2 - bw2 - s(6) - bw1, y, x2 - bw2 - s(6), y + bh)
        y += bh + s(6)
        if d["held"]:
            ph = item_icons.photo(d["held"], 24)
            if ph is not None:
                cv.create_image(x1 + s(14), y + s(10), image=ph, tags=D)
        y = self._wrap(cv, x1 + ind, y, d["held_text"], font(9), fill=NAVY if d["held"] else DESC,
                       width=iw - ind) + s(12)
        # 경험치
        ratio, text = d["exp"]
        self._label(cv, x1, y, "경험치")
        cv.create_text(x2, y, text=text, fill=DESC, font=font(8), anchor="ne", tags=D)
        y += s(18)
        _bar(cv, x1, y, x2, s(9), ratio, CYAN)
        y += s(18)
        if d.get("friend"):
            hearts, num, msg = d["friend"]
            self._label(cv, x1, y, "친밀도")
            cv.create_text(x1 + s(50), y - 1, text=hearts, fill=MAG, font=font(10), anchor="nw", tags=D)
            cv.create_text(x2, y, text=num, fill=DESC, font=font(9), anchor="ne", tags=D)
            y = self._wrap(cv, x1, y + s(18), msg, font(9), fill=DESC, width=iw) + s(12)
        if d.get("evo"):
            self._label(cv, x1, y, "진화")
            y += s(18)
            for line in d["evo"]:
                y = self._wrap(cv, x1, y, line, font(9), width=iw) + s(3)
        return y

    def _d_stats(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        y = self._wrap(cv, x1, y, d["ivsum"], font(9), fill=GOOD, width=iw) + s(10)
        for label, v, iv, hy, mx in d["rows"]:
            cv.create_text(x1, y, text=label, fill=DESC, font=font(9), anchor="nw", tags=D)
            cv.create_text(x1 + s(84), y, text=str(v), fill=NAVY, font=font(10), anchor="ne", tags=D)
            col = "#3cb868" if iv == 31 else ("#f0a020" if iv >= 26 else "#9aa2c0")
            _bar(cv, x1 + s(92), y + s(4), x2 - s(66), s(9), v / float(mx or 1), col)
            cv.create_text(x2, y, text="개체 %d%s" % (iv, "✦" if hy else ""),
                           fill=GOOD if iv == 31 else DESC, font=font(8), anchor="ne", tags=D)
            y += s(23)
        y = self._wrap(cv, x1, y + s(4), d["evsum"], font(9), fill=DESC, width=iw)
        return y

    def _d_moves(self, cv, d, x1, x2, y):
        """기술 넷 - 배틀 기술 목록처럼: 왼쪽 타입 빛깔 칸(타입 이름) + 흰 막대(이름 · 분류 · 위력). 고른 것은 분홍 테."""
        s = U.h
        iw = x2 - x1
        dex = self.app.dex
        mh = s(46)
        tw = s(54)
        for i, (mv, md) in enumerate(d["moves"]):
            tp = (md or {}).get("type")
            col = U.TYPE_COLOR.get(tp, "#a0a0a8")
            tg = D + ("mv%d" % i,)
            picked = bool(self._move_pick and self._move_pick[0] == i)
            if picked:
                K.rrect(cv, x1, y, x2, y + mh, 8, fill=MAG, tags=tg)
                g = s(3)
                K.rrect(cv, x1 + g, y + g, x2 - g, y + mh - g, 6, fill=SEL_FILL, tags=tg)
                bx1, by1, by2 = x1 + g, y + g, y + mh - g
            else:
                K.rrect(cv, x1, y, x2, y + mh, 7, fill="#ffffff", outline=LINE_P, width=max(1, s(2)), tags=tg)
                bx1, by1, by2 = x1, y, y + mh
            K.rrect(cv, bx1, by1, bx1 + tw, by2, 6, fill=col, tags=tg)
            cv.create_rectangle(bx1 + tw - s(8), by1, bx1 + tw, by2, fill=col, outline="", tags=tg)
            tname = dex.type_name(tp) if (dex and tp) else "?"
            cv.create_text(bx1 + tw // 2, (by1 + by2) // 2, text=tname, fill=K.look_of(col)[3], font=font(9),
                           anchor="center", tags=tg)
            tx = bx1 + tw + s(10)
            cv.create_text(tx, y + s(15), text=DPX._clamp(cv, mv, font(11), x2 - tx - s(6), 1), fill=NAVY,
                           font=font(11), anchor="w", tags=tg)
            sub = DPX._clamp(cv, MT.short_line(md), font(9), x2 - tx - s(6), 1)
            cv.create_text(tx, y + mh - s(13), text=sub, fill=DESC, font=font(9), anchor="w", tags=tg)
            cv.tag_bind("mv%d" % i, "<Button-1>", lambda _e, n=i, dd=md, t=mv: self.pick_move(n, dd, t))
            _hand_on(cv, "mv%d" % i)
            y += mh + s(6)
        if self._move_pick:
            _i, md, name = self._move_pick
            y = self._wrap(cv, x1, y + s(2), MT.stat_line(md, name or "?"), font(9), fill=MAG, width=iw)
            y = self._wrap(cv, x1, y + s(2), MT.desc(md), font(9), fill=DESC, width=iw) + s(6)
        if d.get("pending"):
            y = self._wrap(cv, x1, y + s(2), d["pending"], font(9), fill=GOOD, width=iw) + s(6)
        rw = self.btn_remember.want_width(s(30))
        self.btn_remember.layout(x2 - rw, y + s(4), x2, y + s(38))
        return y + s(42)

    def _d_bond(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        b = self.bond
        if b.btn_spec:
            self.btn_bond.configure(text=b.btn_spec[0], state="normal")
            bw = self.btn_bond.want_width(s(30))
            self.btn_bond.layout(x2 - bw, y, x2, y + s(34))
            y += s(42)
        for row in b.lines:
            if row[0] == "kv":
                _k, label, val, col = row
                self._label(cv, x1, y + 1, label)
                y = self._wrap(cv, x1 + s(48), y, val, font(9), fill=tone(col) if col != BD.MEGA else MEGA,
                               width=iw - s(48)) + s(6)
            elif row[0] == "bar":
                _k, label, num, ratio, col = row
                y2 = self._wrap(cv, x1, y, label, font(9), width=iw - s(60))
                cv.create_text(x2, y, text=num, fill=DESC, font=font(8), anchor="ne", tags=D)
                _bar(cv, x1, y2 + s(4), x2, s(9), ratio, col)
                y = y2 + s(20)
            else:
                _k, text, col = row
                y = self._wrap(cv, x1, y, text, font(9), fill=MEGA if col == BD.MEGA else tone(col), width=iw) + s(6)
        dex = self.app.dex
        for pv in b.previews:
            y += s(6)
            K.rrect(cv, x1, y, x2, y + s(2), 1, fill=LINE_P, tags=D)
            y += s(12)
            t = cv.create_text(x1, y, text=pv["name"], fill=MEGA, font=font(11), anchor="nw", tags=D)
            bb = cv.bbox(t)
            cv.create_text((bb[2] if bb else x1) + s(8), y + 2, text="메가진화하면", fill=DESC, font=font(8),
                           anchor="nw", tags=D)
            y += s(24)
            cx = x1
            for tp in pv["types"]:
                label = dex.type_name(tp) if dex else tp
                f = K.tkfont_of(cv, font(8))
                cw = f.measure(label) + s(16)
                col = U.TYPE_COLOR.get(tp, "#a0a0a8")
                K.rrect(cv, cx, y, cx + cw, y + s(19), 6, fill=col, tags=D)
                cv.create_text(cx + cw // 2, y + s(9) + 1, text=label, fill=K.look_of(col)[3], font=font(8),
                               anchor="center", tags=D)
                cx += cw + s(4)
            y += s(26)
            if pv.get("abilityKr"):
                y = self._wrap(cv, x1, y, "특성 %s (%s)" % (pv["abilityKr"], "바뀜" if pv["abilityChanged"] else "그대로"),
                               font(9), width=iw) + s(4)
            for _k, label, now, after, dlt in pv["rows"]:
                cv.create_text(x1, y, text=label, fill=DESC, font=font(8), anchor="nw", tags=D)
                cv.create_text(x1 + s(110), y, text="%d → %d" % (now, after), fill=NAVY if dlt else DIMK,
                               font=font(8), anchor="ne", tags=D)
                cv.create_text(x2, y, text=BD.delta_text(dlt),
                               fill=GOOD if dlt > 0 else ("#d02828" if dlt < 0 else DIMK), font=font(8),
                               anchor="ne", tags=D)
                y += s(17)
        return y

    def _d_egg(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        self._label(cv, x1, y, "알의 상태")
        y = self._wrap(cv, x1, y + s(18), d["mood"], font(9), width=iw) + s(8)
        _bar(cv, x1, y, x2, s(9), d["ratio"], d["egg_color"])
        y += s(16)
        y = self._wrap(cv, x1, y, d["time"], font(9), fill=DESC, width=iw) + s(4)
        y = self._wrap(cv, x1, y, d["left"], font(10), width=iw) + s(12)
        self._label(cv, x1, y, "자라는 곳")
        y = self._wrap(cv, x1, y + s(18), d["where"], font(9), fill=GOOD if d["where_ok"] else "#d02828",
                       width=iw) + s(6)
        y = self._wrap(cv, x1, y, DPX.natural("알도 데리고 다니는 여섯 자리 중 하나를 차지합니다. 알을 데리고 다니는 "
                                              "동안에는 포켓몬이 그만큼 적게 따라다닙니다."), font(8), fill=DIMK,
                       width=iw) + s(4)
        if d.get("day"):
            y = self._wrap(cv, x1, y, "받은 날 %s" % d["day"], font(8), fill=DIMK, width=iw)
        return y


# ---------------------------------------------------------------- 지닌 도구 고르기
# 스킨은 이 모듈에서 HeldPicker 를 찾는다 (ui_box.HeldPicker -> view("box")) - 이 테마 것 (held.py) 을 내보낸다.
from ..dp.box import HeldPicker as _DPHeldPicker, _clamp  # noqa: E402,F401
from .held import HeldPicker  # noqa: E402,F401
