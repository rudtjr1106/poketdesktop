# -*- coding: utf-8 -*-
"""블랙·화이트 테마 - 포켓몬 관리 (PC 박스).

BW 의 PC 박스(어두운 바탕 · 박스 이름 알약 양옆의 ◀ ▶ · 어두운 칸 6 × 5 · 고른 칸의 하늘빛 빛 고리 · 옆의 파티 판)를
시안 H 의 말(짙은 회색 · 하늘빛 빛 테 · C기어 고리 · 어두운 판 · 알약 단추)로 그린다:

    ┌ 어두운 판: 요약 ─────────┐┌ 어두운 판: (타입 ▾)  찾기: ____     (도감)(이름)(Lv)(종족값)  (새로고침) ┐
    │ 도트 무대 (C기어 받침 고리) ││┌ 파티 판 ──┐┌ 박스 판 ──────────────────────────────────────────┐ │
    │ 이름 · Lv · 타입            │││ (파티 1 ▾)││   (◀)  (   박스 1   10/30 ▾   )  (▶)   (이름 바꾸기)   │ │
    │ (정보)(능력)(기술)(메가진화) │││ [카드] ×6 ││   빗금 벽지 위의 어두운 칸 6 × 5 - 고르면 하늘빛 빛 고리 │ │
    │ 쪽 내용                     ││└──────────┘└────────────────────────────────────────────────────┘ │
    └────────────────────────────┘ (( 데리고 다니기 )) (별명 짓기) (박스 옮기기) (색 고르기) (놓아주기)
                                   [ 보유 N마리 · 데리고 다니는 중 N마리 ]                  C기어 고리 ─┘

동작 · 정보는 DP 박스(skins/dp/box.py) 그대로 - 칠하는 메서드만 바꾼다. 글은 늘 단색 판 위, 무늬는 판 바깥 바탕과
박스 벽지의 옅은 빗금뿐이다 (칸은 단색이라 도트가 먼저 보인다). 아이콘은 도트 · item_icons 만.
"""
import tkinter as tk

from common import legends as L
from common import movetext as MT
from common.korean import natural

from ... import box_filter, item_icons
from ... import ui_bond as BD
from ... import ui_common as U
from ..dp import box as DPX
from ..dp import font, tone
from ..dp import kit as K
from ..dp.scene import T
from . import (BG, CARD, CYAN, CYAN_LO, DIMT, DESC, FAINT, GLOW, GLOW_FAR, HP_TRACK, LINE, LINE_HI, PANEL,
               PANEL_HI, SEL, TEXT)
from . import _art as A
from .bag import BWButton

D = DPX.D
SORTS = DPX.SORTS

# 이 화면이 더 쓰는 빛깔 (DP 빛깔 표에 없는 것 - 빛깔 고리가 건드리지 않는다)
WALL_LINE = "#272b31"     # 박스 벽지의 옅은 빗금 (판 위)
EMPTY = "#1d2125"         # 빈 칸
EMPTY_LINE = "#2c3137"
GOOD = "#5fd38a"          # 좋은 것 · 다 찬 것
BAD = "#ff7b72"
GOLD = "#f0c75e"          # 색이 다른 개체
WARM = "#f0a83a"          # 개체값 26~30 · 끌어 놓을 자리
LEGEND = "#c58af0"        # 전설 · 환상 표시
MEGA = "#b494ff"          # 메가진화 글씨
CHK = "#1c3328"           # 여러 마리 고르기에서 고른 칸
CHK_LINE = "#3f9e6a"
DANGER_LINE = "#7a3434"
DANGER_INK = "#ff8a80"
MUTED = "#5d6670"         # 개체값이 낮은 막대
PINK = "#ff7eb6"          # 친밀도 하트
TIP_BG = PANEL_HI         # 칸 위 이름 풍선


def btone(color):
    """기본 테마의 뜻 색 -> 어두운 판에서 읽히는 빛깔."""
    m = {U.GOOD: GOOD, U.DANGER: BAD, U.RED: BAD, U.INFO: CYAN, U.FG_DIM: DIMT, U.FG_FAINT: FAINT, U.FG: TEXT,
         U.SHINY: GOLD, U.ACCENT: WARM, U.ACCENT_TEXT: WARM, U.PINK: PINK, BD.MEGA: MEGA}
    return m.get(color) or tone(color)


class BoxButton(BWButton):
    """시안의 알약 단추 + 놓아주기(위험)."""
    LOOKS = dict(BWButton.LOOKS, danger=(PANEL, PANEL_HI, DANGER_LINE, DANGER_INK))


class BoxWindow(DPX.BoxWindow):

    THUMB = 40
    TOOL_PX = 36           # 위 도구 줄 (거르기 · 찾기 · 줄 세우기)
    HEAD_PX = 30           # 박스 판 머리 (◀ 이름 ▶)
    BOT_PX = 88            # 아래 단추 줄 + 글상자
    CELL_MIN = 48          # 칸 높이 하한 (도트 40 + 둘레) - 작은 창(980 × 620)에서도 다섯 줄이 다 보이게

    def _build(self):
        DPX.BoxWindow._build(self)
        self.win.configure(bg=BG)
        self.cv.configure(bg=BG)
        # 요약 · 박스 칸은 둥근 판 안에 앉힌다 (판은 캔버스에 그린다 - 틀의 네모 테는 걷는다)
        self.dframe.configure(bg=PANEL, highlightthickness=0)
        self.dcv.configure(bg=PANEL)
        self.gframe.configure(bg=PANEL, highlightthickness=0)
        self.gcv.configure(bg=PANEL)
        for sb in (self.dsb, self.gsb):
            try:
                sb.configure(bg=PANEL)
            except tk.TclError:
                pass
        # 찾기 칸은 밑줄만 (시안 .find)
        box = self.find_box
        try:
            box.configure(bg=PANEL, highlightthickness=0)
            box.entry.configure(bg=PANEL, fg=TEXT, insertbackground=TEXT)
        except tk.TclError:
            pass
        kinds = ((self.btn_party, "go"), (self.btn_nick, "dark"), (self.btn_move, "dark"), (self.btn_tint, "dark"),
                 (self.btn_release, "danger"), (self.btn_multi_move, "go"), (self.btn_multi_all, "dark"),
                 (self.btn_multi_clear, "dark"), (self.btn_multi_done, "dark"), (self.btn_prev, "dark"),
                 (self.btn_next, "dark"), (self.btn_rename, "dark"), (self.btn_party_name, "dark"),
                 (self.btn_reload, "dark"), (self.btn_hold, "go"), (self.btn_unhold, "dark"),
                 (self.btn_remember, "go"), (self.btn_bond, "go"))
        for b, kind in kinds:
            BoxButton.adopt(b, kind)
        self._find_line = None

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
        A.backdrop(cv, 0, 0, W, H, tags=T)
        DW = s(self.DW_PX)
        m = s(12)
        # 요약 판 (왼쪽 기둥)
        A.panel(cv, m, m, m + DW, H - m, tags=T)
        self._place("detail", self.dframe, m + s(4), m + s(6), DW - s(8), H - 2 * m - s(12))
        self._paint_right(cv, m + DW + s(12), W - m, H)

    def _paint_right(self, cv, x0, x2, H):
        s = U.h
        m = s(12)
        # 1) 도구 줄: 타입 · 찾기 · 줄 세우기 · 새로고침 (한 장의 판 위)
        y = m
        th = s(self.TOOL_PX)
        A.panel(cv, x0, y, x2, y + th, tags=T)
        ph = s(28)
        py = y + (th - ph) // 2
        ix1, ix2 = x0 + s(10), x2 - s(10)
        f10 = K.tkfont_of(cv, font(10))
        label = self.btn_type.text + " ▾"
        rw = self.btn_reload.want_width(s(24))
        # 좁은 창에서 찾기 칸이 모자라면 알약 안쪽 여백만 줄인다 (글씨는 그대로)
        pad, tpad = s(22), s(28)
        need = sum(f10.measure(lb) for _k, lb in SORTS) + f10.measure(label) + f10.measure("찾기:") + rw
        if ix2 - ix1 - need - 4 * pad - tpad - s(70) < s(140):
            pad, tpad = s(14), s(20)
        self.btn_reload.layout(ix2 - rw, py, ix2, py + ph)
        right = self._seg(cv, ix2 - rw - s(12), py, ph, SORTS, self.sort, "bsort", self.set_sort, align="right",
                          pad=pad)
        tw = f10.measure(label) + tpad
        on = bool(self.f_type)
        A.pill(cv, ix1, py, ix1 + tw, py + ph, on=on, tags=T + ("tsel",))
        cv.create_text(ix1 + tw // 2, py + ph // 2, text=label, fill=CYAN if on else TEXT, font=font(10),
                       anchor="center", tags=T + ("tsel",))
        self._boxes["type"] = (ix1, py, ix1 + tw, py + ph)
        cv.tag_bind("tsel", "<Button-1>", lambda _e: self._open_type_menu())
        self._hand("tsel")
        fx1 = ix1 + tw + s(12)
        fx2 = right[0][1][0] - s(12)
        cv.create_text(fx1, py + ph // 2, text="찾기:", fill=DIMT, font=font(10), anchor="w", tags=T)
        ex = fx1 + f10.measure("찾기:") + s(6)
        self._place("find", self.find_box, ex, py + s(1), max(s(40), fx2 - ex), ph - s(4))
        cv.create_line(fx1, py + ph, max(fx2, ex + s(40)), py + ph,
                       fill=CYAN if self.f_query.get() else LINE_HI, tags=T)
        # 2) 데리고 다니는 판 + 박스 판
        y += th + s(7)
        BOT = s(self.BOT_PX)
        gy2 = H - BOT
        PW = s(self.PARTY_PX)
        self._paint_party_slots(cv, x0, y, x0 + PW, gy2)
        gx1 = x0 + PW + s(10)
        A.panel(cv, gx1, y, x2, gy2, tags=T)
        hy2 = self._paint_box_head(cv, gx1 + s(10), y + s(5), x2 - s(10), y + s(5 + self.HEAD_PX))
        self._place("grid", self.gframe, gx1 + s(4), hy2 + s(1), x2 - gx1 - s(8), gy2 - hy2 - s(5))
        # 3) 단추 줄 + 글상자
        by = gy2 + s(9)
        bh2 = s(34)
        if self.multi:
            btns = [self.btn_multi_move, self.btn_multi_all, self.btn_multi_clear, self.btn_multi_done]
            hide = [self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release]
        else:
            btns = [self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release]
            hide = [self.btn_multi_move, self.btn_multi_all, self.btn_multi_clear, self.btn_multi_done]
        for b in hide:
            b.hide()
        x = x0
        for i, b in enumerate(btns):
            w = b.want_width(s(36) if i == 0 else s(28))
            b.layout(x, by, x + w, by + bh2)
            x += w + s(8)
        text, color = self.msg
        shown = text or self._count_text
        my1, my2 = by + bh2 + s(7), H - s(9)
        A.panel(cv, x0, my1, x2, my2, r=(my2 - my1) // 2, tags=T)
        self._msg_w = x2 - x0 - s(36)
        tid = K.text(cv, x0 + s(18), (my1 + my2) // 2, shown, font(11),
                     fill=(btone(color) if color else (TEXT if text else DIMT)), anchor="w",
                     width=self._msg_w, tags=T)[1]
        self._msg_ids = (None, tid)

    def say(self, msg, color=None):
        DPX.BoxWindow.say(self, msg, color)
        # DP 는 뜻 색을 밝은 판용(tone)으로 칠한다 - 어두운 판에서 읽히는 빛깔로 다시
        if self._msg_ids and self.msg[0]:
            try:
                c = self.msg[1]
                self.cv.itemconfigure(self._msg_ids[1], fill=btone(c) if c else TEXT)
            except tk.TclError:
                pass

    def _seg(self, cv, x, y, h, items, current, tag, on_pick, align="left", pad=None):
        """시안 .seg - 작은 알약 줄. 그린 칸들 [(열쇠, 상자)]."""
        spec = font(10)
        f = K.tkfont_of(cv, spec)
        gap = U.h(5)
        pad = U.h(22) if pad is None else pad
        ws = [f.measure(lb) + pad for _k, lb in items]
        if align == "right":
            x -= sum(ws) + gap * (len(items) - 1)
        out = []
        for (key, lb), w in zip(items, ws):
            on = key == current
            tg = T + (tag, "%s_%s" % (tag, key or "_"))
            A.pill(cv, x, y, x + w, y + h, on=on, tags=tg)
            cv.create_text(x + w // 2, y + h // 2, text=lb, fill=CYAN if on else DIMT, font=spec, anchor="center",
                           tags=tg)
            cv.tag_bind("%s_%s" % (tag, key or "_"), "<Button-1>", lambda _e, k=key: on_pick(k))
            out.append((key, (x, y, x + w, y + h)))
            x += w + gap
        self._hand(tag)
        return out

    def _paint_box_head(self, cv, x1, y1, x2, y2):
        """박스 판 머리: (◀) (박스 이름 알약 ▾) (▶) · 이름 바꾸기. 머리 아래 끝 y."""
        s = U.h
        bh = y2 - y1
        f12 = K.tkfont_of(cv, font(12))
        text = (self._page_text or "").replace("   ", "  ")
        tw = f12.measure(text)
        # 좁으면 단추 안쪽 여백 · 사이만 줄인다 (글씨는 그대로)
        rw = self.btn_rename.want_width(s(24))
        gap = s(6)
        if (x2 - x1) - rw - s(10) - 2 * (bh + gap) < tw + s(40):
            rw, gap = self.btn_rename.want_width(s(14)), s(4)
        self.btn_rename.layout(x2 - rw, y1 + s(2), x2, y2 - s(2))
        room = x2 - rw - s(8) - x1
        nw = min(room - 2 * (bh + gap), max(s(150), tw + s(48)))
        cx = x1 + room // 2
        nx1 = cx - nw // 2
        nx2 = nx1 + nw
        self.btn_prev.layout(nx1 - gap - bh, y1, nx1 - gap, y2)
        self.btn_next.layout(nx2 + gap, y1, nx2 + gap + bh, y2)
        # 박스 이름 알약 - BW PC 박스처럼 하늘빛 테 (지금 보는 박스). 그래도 넘치는 긴 이름만 줄여 쓴다
        A.lit(cv, nx1, y1, nx2, y2, bh // 2, CARD, tags=T + ("page",), width=1)
        if tw > nw - s(16):
            text = DPX._clamp(cv, text, font(12), nw - s(16), 1)
        cv.create_text((nx1 + nx2) // 2, (y1 + y2) // 2, text=text, fill=TEXT, font=font(12),
                       anchor="center", tags=T + ("page",))
        self._boxes["page"] = (nx1, y1, nx2, y2)
        cv.tag_bind("page", "<Button-1>", lambda _e: self.open_box_menu())
        self._hand("page")
        return y2

    # ---------------- 데리고 다니는 판 ----------------
    def _paint_party_slots(self, cv, x1, y1, x2, y2):
        s = U.h
        A.panel(cv, x1, y1, x2, y2, tags=T)
        hy = y1 + s(10)
        cv.create_text(x1 + s(12), hy + s(9), text="데리고 다니는", fill=DIMT, font=font(9), anchor="w", tags=T)
        rows = self.party_presets()
        top = hy + s(24)
        if rows:
            name = next((p.get("name") or "파티 %d" % p.get("no") for p in rows if p.get("no") == self.party_active()),
                        "파티")
            px1, px2 = x1 + s(8), x2 - s(8)
            A.pill(cv, px1, top, px2, top + s(26), tags=T + ("preset",))
            cv.create_text((px1 + px2) // 2, top + s(13),
                           text=DPX._clamp(cv, name, font(10), px2 - px1 - s(30), 1) + " ▾",
                           fill=TEXT, font=font(10), anchor="center", tags=T + ("preset",))
            self._boxes["preset"] = (px1, top, px2, top + s(26))
            cv.tag_bind("preset", "<Button-1>", lambda _e: self._open_preset_menu())
            self._hand("preset")
            top += s(34)
        self.btn_party_name.hide()
        n = 6
        gap = s(6)
        sh = (y2 - top - s(10) - gap * (n - 1)) / float(n)
        self._pslots = {}
        r = s(8)
        for i in range(n):
            sy1 = top + i * (sh + gap)
            sy2 = sy1 + sh
            sx1, sx2 = x1 + s(8), x2 - s(8)
            m = self._party_list[i] if i < len(self._party_list) else None
            mid = (sy1 + sy2) / 2
            if m is None:
                K.rrect(cv, sx1, sy1, sx2, sy2, r, fill=EMPTY, outline=EMPTY_LINE, tags=T)
                cv.create_text((sx1 + sx2) / 2, mid, text="빈 자리", fill=FAINT, font=font(9), tags=T)
                continue
            pid = m["id"]
            sel, tgt, chk, hov = pid == self.sel, pid == self._target, pid in self.checked, pid == self._hover
            tg = T + ("pslot",)
            if sel:
                A.lit(cv, sx1, sy1, sx2, sy2, r, SEL, tags=tg)
            elif tgt:
                K.rrect(cv, sx1, sy1, sx2, sy2, r, fill=PANEL_HI, outline=WARM, width=2, tags=tg)
            elif chk:
                K.rrect(cv, sx1, sy1, sx2, sy2, r, fill=CHK, outline=GOOD, width=2, tags=tg)
            else:
                K.rrect(cv, sx1, sy1, sx2, sy2, r, fill=PANEL_HI if hov else CARD, outline=LINE_HI if hov else LINE,
                        tags=tg)
            ph = self._thumb(m)
            if ph is not None:
                cv.create_image(sx1 + s(28), mid, image=ph, tags=tg)
            info = m.get("info") or {}
            name = "알" if m.get("isEgg") else info.get("name", m.get("species", "?"))
            if m.get("shiny"):
                name = "★" + name
            cv.create_text(sx1 + s(56), mid - s(8), text=DPX._clamp(cv, name, font(10), sx2 - sx1 - s(60), 1),
                           fill=GOLD if m.get("shiny") else (CYAN if sel else TEXT), font=font(10), anchor="w",
                           tags=tg)
            cv.create_text(sx1 + s(56), mid + s(9), anchor="w", font=font(9), fill=DIMT, tags=tg,
                           text=("%d%%" % box_filter.egg_progress(m.get("egg") or {})[0]) if m.get("isEgg")
                           else "Lv.%d" % m.get("level", 0))
            if chk:
                cv.create_text(sx2 - s(6), sy2 - s(3), text="✓", fill=GOOD, font=font(11), anchor="se", tags=tg)
            self._pslots[pid] = (sx1, sy1, sx2, sy2)
        self._hand("pslot")

    # ---------------- 박스 칸 (빗금 벽지 위의 6 × 5) ----------------
    def _wall(self, cv, w, h):
        """박스 벽지: 단색 판 + 옅은 빗금 (칸 사이로만 보인다)."""
        cv.create_rectangle(0, 0, w, h, fill=PANEL, outline="")
        step = U.h(14)
        for k in range(-h, w + step, step):
            cv.create_line(k, h, k + h, 0, fill=WALL_LINE, width=1)

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
        ch = max(s(self.CELL_MIN), (h - pad) / 5.0)
        total = max(h, int(ch * rows + pad))
        cv.configure(scrollregion=(0, 0, w, total))
        self._wall(cv, w, total)
        self._cells = {}
        r = s(8)
        for i in range(rows * cols):
            rr, c = divmod(i, cols)
            x1, y1 = pad + c * cw, pad + rr * ch
            x2, y2 = x1 + cw - pad, y1 + ch - pad
            if i >= n:
                K.rrect(cv, x1, y1, x2, y2, r, fill=EMPTY, outline=EMPTY_LINE)
                continue
            m = self._page_mons[i]
            pid = m["id"]
            sel, tgt, chk, hov = pid == self.sel, pid == self._target, pid in self.checked, pid == self._hover
            if sel:
                A.lit(cv, x1, y1, x2, y2, r, SEL)
            elif tgt:
                K.rrect(cv, x1, y1, x2, y2, r, fill=PANEL_HI, outline=WARM, width=2)
            elif chk:
                K.rrect(cv, x1, y1, x2, y2, r, fill=CHK, outline=GOOD, width=2)
            else:
                K.rrect(cv, x1, y1, x2, y2, r, fill=PANEL_HI if hov else CARD, outline=LINE_HI if hov else LINE)
            ph = self._thumb(m)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if ph is not None:
                cv.create_image(mx, my, image=ph)
            else:
                cv.create_oval(mx - 6, my - 6, mx + 6, my + 6, fill=PANEL, outline=LINE)
            if m.get("shiny"):
                cv.create_text(x1 + s(5), y1 + s(3), text="★", fill=GOLD, font=font(9), anchor="nw")
            kind = None if m.get("isEgg") else L.kind_of(m.get("num"))
            if kind:
                # 고른 표시(✓)가 오른쪽 위를 쓰면 그 왼쪽으로
                cv.create_text(x2 - s(22 if chk else 5), y1 + s(3), text="◆" if kind == "legendary" else "✦",
                               fill=LEGEND, font=font(8), anchor="ne")
            if m.get("away"):
                # 칸 아래에 작은 단색 알약 (글은 도트 위가 아니라 알약 위)
                f = K.tkfont_of(cv, font(8))
                tw = f.measure("탐험 중") + s(10)
                th = f.metrics("linespace") + s(2)
                K.rrect(cv, mx - tw / 2, y2 - th - s(2), mx + tw / 2, y2 - s(2), th // 2, fill=BG, outline=CYAN_LO)
                cv.create_text(mx, y2 - s(2) - th / 2, text="탐험 중", fill=CYAN, font=font(8))
            if chk:
                # 고른 표시: 칸 오른쪽 위 모서리에 초록 동그라미 안의 ✓ (알림 점처럼 - 아래의 '탐험 중' 과 안 겹친다)
                rd = s(8)
                bx_, by_ = x2 - s(5), y1 + s(5)
                cv.create_oval(bx_ - rd, by_ - rd, bx_ + rd, by_ + rd, fill=CHK_LINE, outline=CHK, width=2)
                cv.create_text(bx_, by_, text="✓", fill=TEXT, font=font(10))
            self._cells[pid] = (x1, y1, x2, y2)
        # 마우스가 올라간 포켓몬의 이름
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
            K.rrect(cv, tx - tw / 2, ty - s(22), tx + tw / 2, ty, s(11), fill=TIP_BG, outline=LINE_HI, width=1)
            cv.create_text(tx, ty - s(11), text=tip, fill=TEXT, font=font(9))

    # ---------------- 요약 ----------------
    def _paint_detail(self, top=False):
        """요약: 도트 무대 · 이름 · 타입은 늘 위에, 그 아래 쪽 하나 (정보 · 능력 · 기술 · 메가진화 / 알)."""
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
        x1, x2 = s(2), w - s(4)
        if not d:
            cv.create_text(w // 2, s(80), text="포켓몬을 고르세요", fill=DIMT, font=font(12), anchor="n", tags=D)
            return
        y = s(2)
        # 도트 무대: 어두운 카드 + C기어 받침 고리 (시안 배틀의 받침처럼)
        sh = s(122)
        K.rrect(cv, x1, y, x2, y + sh, s(10), fill=CARD, outline=LINE, tags=D)
        cx = (x1 + x2) // 2
        py = y + sh - s(22)
        for rx, ry, col, lw in ((s(70), s(14), GLOW_FAR, max(2, s(4))), (s(60), s(11), GLOW, 2),
                                (s(60), s(11), CYAN_LO, 1)):
            cv.create_oval(cx - rx, py - ry, cx + rx, py + ry, outline=col, width=lw, tags=D)
        f9 = K.tkfont_of(cv, font(9))
        nw = f9.measure(d["num"]) + s(18)
        K.rrect(cv, x1 + s(8), y + s(8), x1 + s(8) + nw, y + s(28), s(10), fill=PANEL, outline=LINE, tags=D)
        cv.create_text(x1 + s(8) + nw // 2, y + s(18), text=d["num"], fill=DIMT, font=font(9), anchor="center",
                       tags=D)
        a = cv.create_image(cx, y + sh // 2 - s(2), image=self.d_art.image or "", tags=D)
        b = cv.create_text(cx, y + sh // 2, text="" if self.d_art.image else self.d_art.text,
                           fill=btone(self.d_art.fg), font=font(11), tags=D)
        self.d_art.ids = (a, b)
        y += sh + s(10)
        # 이름 · 성별 · Lv
        shiny = d["m"].get("shiny") and not d.get("egg")
        t = cv.create_text(x1 + s(4), y + s(12), text=d["name"], fill=GOLD if shiny else TEXT, font=font(14),
                           anchor="w", tags=D)
        bb = cv.bbox(t)
        if d.get("gender") and bb:
            cv.create_text(bb[2] + s(6), y + s(12), text=d["gender"], fill=d.get("gender_fg", DIMT), font=font(12),
                           anchor="w", tags=D)
        lw_ = K.tkfont_of(cv, font(11)).measure(d["lv"]) + s(20)
        A.pill(cv, x2 - lw_, y, x2, y + s(24), tags=D)
        cv.create_text(x2 - lw_ // 2, y + s(12), text=d["lv"], fill=TEXT, font=font(11), anchor="center", tags=D)
        y += s(30)
        if d.get("sub"):
            _a, t2 = K.text(cv, x1 + s(4), y, d["sub"], font(9), fill=DIMT, tags=D, width=x2 - x1 - s(8))
            y = cv.bbox(t2)[3] + s(6)
        cx_ = x1 + s(4)
        for label, col in d.get("chips") or []:
            f = K.tkfont_of(cv, font(9))
            cw = f.measure(label) + s(18)
            K.rrect(cv, cx_, y, cx_ + cw, y + s(22), s(11), fill=col, tags=D)
            cv.create_text(cx_ + cw // 2, y + s(11), text=label, fill=K.look_of(col)[3], font=font(9),
                           anchor="center", tags=D)
            cx_ += cw + s(5)
        y += s(32)
        if d.get("egg"):
            y = self._d_egg(cv, d, x1, x2, y)
        else:
            pages = [("info", "정보"), ("stats", "능력"), ("moves", "기술")]
            if self.bond.visible:
                pages.append(("mega", "메가진화"))
            if self._dpage not in dict(pages):
                self._dpage = "info"
            self._dtabs(cv, x1, y, x2, s(28), pages)
            y += s(28) + s(14)
            y = {"info": self._d_info, "stats": self._d_stats, "moves": self._d_moves,
                 "mega": self._d_bond}[self._dpage](cv, d, x1 + s(4), x2 - s(4), y)
        total = y + s(12)
        cv.configure(scrollregion=(0, 0, w, max(total, vh)))
        if top:
            cv.yview_moveto(0)
        for b in (self.btn_hold, self.btn_unhold, self.btn_remember, self.btn_bond):
            if b.box:
                b.draw()

    def _dtabs(self, cv, x1, y, x2, h, pages):
        """쪽 고르기 - 시안 .seg 처럼 같은 폭 알약 (고른 쪽은 하늘빛 테 · 글씨)."""
        gap = U.h(5)
        n = len(pages)
        w = (x2 - x1 - gap * (n - 1)) / float(n)
        for i, (key, lb) in enumerate(pages):
            on = key == self._dpage
            a, b = x1 + i * (w + gap), x1 + i * (w + gap) + w
            tg = D + ("dpg" + key,)
            A.pill(cv, int(a), y, int(b), y + h, on=on, tags=tg)
            cv.create_text((a + b) / 2, y + h // 2, text=lb, fill=CYAN if on else DIMT, font=font(10),
                           anchor="center", tags=tg)
            cv.tag_bind("dpg" + key, "<Button-1>", lambda _e, k=key: self._pick_dpage(k))
            cv.tag_bind("dpg" + key, "<Enter>", lambda _e: cv.configure(cursor="hand2"))
            cv.tag_bind("dpg" + key, "<Leave>", lambda _e: cv.configure(cursor=""))

    def _wrap(self, cv, x, y, text, spec, fill=TEXT, width=100):
        return DPX.BoxWindow._wrap(self, cv, x, y, text, spec, fill=fill, width=width)

    def _label(self, cv, x, y, text):
        cv.create_text(x, y, text=text, fill=DIMT, font=font(9), anchor="nw", tags=D)

    def _bar(self, cv, x1, y, x2, ratio, col, hh=None):
        hh = hh or U.h(8)
        K.rrect(cv, x1, y, x2, y + hh, hh // 2, fill=HP_TRACK, tags=D)
        fw = int((x2 - x1) * max(0.0, min(1.0, ratio)))
        if fw >= hh:
            K.rrect(cv, x1, y, x1 + fw, y + hh, hh // 2, fill=col, tags=D)
        elif fw > 0:
            cv.create_rectangle(x1, y, x1 + fw, y + hh, fill=col, outline="", tags=D)

    def _rule(self, cv, x1, x2, y):
        cv.create_line(x1, y, x2, y, fill=LINE, tags=D)

    def _d_info(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        lx = s(44)
        for title, name, note in (("특성", d["ability"], d["ability_note"]), ("성격", d["nature"], d["nature_note"])):
            self._label(cv, x1, y + s(1), title)
            y = self._wrap(cv, x1 + lx, y, name, font(10), width=iw - lx)
            y = self._wrap(cv, x1 + lx, y + 2, note, font(9), fill=DESC, width=iw - lx) + s(10)
        self._rule(cv, x1, x2, y)
        y += s(10)
        # 지닌 도구 - 하늘빛 고리 안에 도구 그림 (시안 가방의 .ring)
        self._label(cv, x1, y + s(1), "도구")
        bw1, bw2 = self.btn_hold.want_width(s(20)), self.btn_unhold.want_width(s(20))
        self.btn_unhold.layout(x2 - bw2, y - s(3), x2, y + s(23))
        self.btn_hold.layout(x2 - bw2 - s(6) - bw1, y - s(3), x2 - bw2 - s(6), y + s(23))
        y += s(30)
        rr = s(15)
        cx, cy = x1 + rr + s(2), y + rr
        if d["held"]:
            cv.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=CARD, outline=CYAN, width=max(2, s(2)), tags=D)
            ph = item_icons.photo(d["held"], 24)
            if ph is not None:
                cv.create_image(cx, cy, image=ph, tags=D)
        else:
            cv.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=CARD, outline=LINE, width=max(2, s(2)), tags=D)
        tx = x1 + lx
        y = max(cy + rr, self._wrap(cv, tx, y + s(2), d["held_text"], font(9), fill=TEXT if d["held"] else DIMT,
                                    width=iw - lx)) + s(10)
        self._rule(cv, x1, x2, y)
        y += s(10)
        # 경험치
        ratio, text = d["exp"]
        self._label(cv, x1, y, "경험치")
        cv.create_text(x2, y, text=text, fill=DIMT, font=font(8), anchor="ne", tags=D)
        y += s(18)
        self._bar(cv, x1, y, x2, ratio, CYAN)
        y += s(18)
        if d.get("friend"):
            hearts, num, msg = d["friend"]
            self._label(cv, x1, y, "친밀도")
            cv.create_text(x1 + s(52), y - 1, text=hearts, fill=PINK, font=font(10), anchor="nw", tags=D)
            cv.create_text(x2, y, text=num, fill=DIMT, font=font(9), anchor="ne", tags=D)
            y = self._wrap(cv, x1, y + s(18), msg, font(9), fill=DESC, width=iw) + s(10)
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
            cv.create_text(x1, y, text=label, fill=DIMT, font=font(9), anchor="nw", tags=D)
            cv.create_text(x1 + s(84), y, text=str(v), fill=TEXT, font=font(10), anchor="ne", tags=D)
            bx1, bx2 = x1 + s(92), x2 - s(66)
            col = GOOD if iv == 31 else (WARM if iv >= 26 else MUTED)
            self._bar(cv, bx1, y + s(3), bx2, v / float(mx or 1), col, U.h(9))
            cv.create_text(x2, y, text="개체 %d%s" % (iv, "✦" if hy else ""),
                           fill=GOOD if iv == 31 else DIMT, font=font(8), anchor="ne", tags=D)
            y += s(24)
        self._rule(cv, x1, x2, y + s(2))
        y = self._wrap(cv, x1, y + s(10), d["evsum"], font(9), fill=DESC, width=iw)
        return y

    def _d_moves(self, cv, d, x1, x2, y):
        """기술 카드 - 시안 배틀의 기술 카드처럼 위에 타입 빛깔 띠를 두른 어두운 카드."""
        s = U.h
        iw = x2 - x1
        dex = self.app.dex
        mh = s(48)
        r = s(8)
        for i, (mv, md) in enumerate(d["moves"]):
            col = U.TYPE_COLOR.get((md or {}).get("type"), "#a0a0a8")
            tg = D + ("mv%d" % i,)
            picked = bool(self._move_pick and self._move_pick[0] == i)
            if picked:
                A.lit(cv, x1 + s(2), y, x2 - s(2), y + mh, r, SEL, tags=tg)
            else:
                K.rrect(cv, x1 + s(2), y, x2 - s(2), y + mh, r, fill=CARD, outline=LINE, tags=tg)
            K.rrect(cv, x1 + s(3), y + 1, x2 - s(3), y + s(5), s(2), fill=col, tags=tg)
            cv.create_text(x1 + s(14), y + s(18), text=mv, fill=CYAN if picked else TEXT, font=font(11), anchor="w",
                           tags=tg)
            tname = dex.type_name((md or {}).get("type")) if dex else ""
            t = cv.create_text(x1 + s(14), y + mh - s(12), text=tname, fill=col, font=font(9), anchor="w", tags=tg)
            bb = cv.bbox(t)
            cv.create_text((bb[2] if bb else x1 + s(40)) + s(8), y + mh - s(12), text=MT.short_line(md),
                           fill=DIMT, font=font(9), anchor="w", tags=tg)
            cv.tag_bind("mv%d" % i, "<Button-1>", lambda _e, n=i, dd=md, t=mv: self.pick_move(n, dd, t))
            cv.tag_bind("mv%d" % i, "<Enter>", lambda _e: cv.configure(cursor="hand2"))
            cv.tag_bind("mv%d" % i, "<Leave>", lambda _e: cv.configure(cursor=""))
            y += mh + s(8)
        if self._move_pick:
            _i, md, name = self._move_pick
            y = self._wrap(cv, x1, y + s(2), MT.stat_line(md, name or "?"), font(9), fill=WARM, width=iw)
            y = self._wrap(cv, x1, y + s(2), MT.desc(md), font(9), fill=DESC, width=iw) + s(6)
        if d.get("pending"):
            y = self._wrap(cv, x1, y + s(2), d["pending"], font(9), fill=GOOD, width=iw) + s(6)
        rw = self.btn_remember.want_width(s(28))
        self.btn_remember.layout(x2 - rw, y + s(4), x2, y + s(32))
        return y + s(36)

    def _d_bond(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        b = self.bond
        if b.btn_spec:
            self.btn_bond.configure(text=b.btn_spec[0], state="normal")
            bw = self.btn_bond.want_width(s(28))
            self.btn_bond.layout(x2 - bw, y, x2, y + s(28))
            y += s(38)
        for row in b.lines:
            if row[0] == "kv":
                _k, label, val, col = row
                self._label(cv, x1, y, label)
                y = self._wrap(cv, x1 + s(52), y, val, font(9), fill=btone(col), width=iw - s(52)) + s(6)
            elif row[0] == "bar":
                _k, label, num, ratio, col = row
                y2 = self._wrap(cv, x1, y, label, font(9), width=iw - s(60))
                cv.create_text(x2, y, text=num, fill=DIMT, font=font(8), anchor="ne", tags=D)
                full = ratio >= 1.0
                self._bar(cv, x1, y2 + s(4), x2, ratio, GOOD if full else MEGA)
                y = y2 + s(18)
            else:
                _k, text, col = row
                y = self._wrap(cv, x1, y, text, font(9), fill=btone(col), width=iw) + s(6)
        dex = self.app.dex
        for pv in b.previews:
            self._rule(cv, x1, x2, y + s(4))
            y += s(14)
            t = cv.create_text(x1, y, text=pv["name"], fill=MEGA, font=font(11), anchor="nw", tags=D)
            bb = cv.bbox(t)
            cv.create_text((bb[2] if bb else x1) + s(8), y + 2, text="메가진화하면", fill=DIMT, font=font(8),
                           anchor="nw", tags=D)
            y += s(24)
            cx = x1
            for tp in pv["types"]:
                label = dex.type_name(tp) if dex else tp
                f = K.tkfont_of(cv, font(8))
                cw = f.measure(label) + s(16)
                col = U.TYPE_COLOR.get(tp, "#a0a0a8")
                K.rrect(cv, cx, y, cx + cw, y + s(18), s(9), fill=col, tags=D)
                cv.create_text(cx + cw // 2, y + s(9), text=label, fill=K.look_of(col)[3], font=font(8),
                               anchor="center", tags=D)
                cx += cw + s(4)
            y += s(26)
            if pv.get("abilityKr"):
                y = self._wrap(cv, x1, y, "특성 %s (%s)" % (pv["abilityKr"], "바뀜" if pv["abilityChanged"] else "그대로"),
                               font(9), width=iw) + s(4)
            for _k, label, now, after, dlt in pv["rows"]:
                cv.create_text(x1, y, text=label, fill=DIMT, font=font(8), anchor="nw", tags=D)
                cv.create_text(x1 + s(110), y, text="%d → %d" % (now, after), fill=TEXT if dlt else FAINT,
                               font=font(8), anchor="ne", tags=D)
                cv.create_text(x2, y, text=BD.delta_text(dlt), fill=GOOD if dlt > 0 else (BAD if dlt < 0 else FAINT),
                               font=font(8), anchor="ne", tags=D)
                y += s(16)
        return y

    def _d_egg(self, cv, d, x1, x2, y):
        s = U.h
        x1, x2 = x1 + s(4), x2 - s(4)
        iw = x2 - x1
        self._label(cv, x1, y, "알의 상태")
        y = self._wrap(cv, x1, y + s(18), d["mood"], font(9), width=iw) + s(8)
        self._bar(cv, x1, y, x2, d["ratio"], d["egg_color"])
        y += s(16)
        y = self._wrap(cv, x1, y, d["time"], font(9), fill=DIMT, width=iw) + s(4)
        y = self._wrap(cv, x1, y, d["left"], font(10), width=iw) + s(10)
        self._rule(cv, x1, x2, y)
        y += s(10)
        self._label(cv, x1, y, "자라는 곳")
        y = self._wrap(cv, x1, y + s(18), d["where"], font(9), fill=GOOD if d["where_ok"] else BAD, width=iw) + s(4)
        y = self._wrap(cv, x1, y, natural("알도 데리고 다니는 여섯 자리 중 하나를 차지합니다. 알을 데리고 다니는 동안에는 "
                                          "포켓몬이 그만큼 적게 따라다닙니다."), font(8), fill=FAINT, width=iw) + s(4)
        if d.get("day"):
            y = self._wrap(cv, x1, y, "받은 날 %s" % d["day"], font(8), fill=FAINT, width=iw)
        return y

# ---------------------------------------------------------------- 지닌 도구 고르기
# ui_box.HeldPicker 가 view("box") 에서 이 이름을 찾는다 - 이 테마의 것(held.py)을 내보낸다.
from .held import HeldPicker, _clamp  # noqa: E402,F401
