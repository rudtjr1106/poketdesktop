# -*- coding: utf-8 -*-
"""에메랄드 배틀 화면 - 관장 · 실시간 · 레이드 배틀 창이 같이 쓰는 그림 (시안 A 의 '배틀 (기술 고르기)').

    장면        하늘색 하늘(#a8e0f0) · 연두 땅(#b8e8a0) - 번지지 않는 두 빛 (시안 .bt)
                받침은 초록 타원 (#88c870, 아래쪽 안 그늘 #6aa858, 둘레 #9ad482 - 시안 .pad)
    이름표      GBA 창: 종이 바탕 · 남색 4px 테 · 모서리 깎음. 이름 ♂ · Lv / 주황 'HP' 꼬리표 + 남색 테의 체력 막대 /
                체력 숫자 (체력 빛깔은 그대로)
    글상자      GBA 창 (남색 테 · 안쪽 옅은 줄 · 종이) - 장면의 땅 위에
    아래        남색 바탕. 맨 위 띠에 양쪽 파티의 볼 · 턴 (흰 글씨)
                왼쪽 큰 GBA 창 = 기술 2x2 (고른 칸에 빨간 ▶, 칸마다 타입 꼬리표 · PP)
                오른쪽 GBA 창 = 고른 기술의 PP · 타입 칸 · 위력 / 분류 / 명중 (시안 .pp)
                그 밑에 [포켓몬] [기권] - GBA 창 모양의 글자 단추 (올리면 연노랑 + 빨간 ▶)
                메가진화 · Z기술 켜기는 기술 창 왼쪽 아래 (시안에 특별 단추가 없어 GBA 단추 모양)

흐름은 DP 와 같다 - 내 차례가 오면 기술이 바로 나온다 (시안의 '싸운다' 단계 없음, 시안의 '가방' 은 이 배틀에
없어 뺐고 '도망' 자리는 '기권'). 교체 · 기다림 · 결과 화면도 같은 GBA 창으로 그린다.
"""
import tkinter as tk

from ..dp import DIM, INK, INK2, kit
from ..dp import battle as DPB
from ..dp import raid_battle as DPR
from ..dp.battle import CAT_COLOR, CAT_KR, F, MOVE_Z, U, hp_colors
from . import GRP, NAVY, NAVY_LO, PAPER, RED, SELY
from . import gba

SKY_C, GROUND_C = "#a8e0f0", "#b8e8a0"                         # 시안 .bt
PAD, PAD_SH, PAD_RING = "#88c870", "#6aa858", "#9ad482"        # 시안 .pad
HORIZON_C = 0.62                                               # 시안: 하늘이 장면의 2/3 쯤
HP_TAG = "#f0a030"                                             # 시안 .bar b
BAR_TRACK_C = "#484848"                                        # 시안 .bar i
OFF_FILL, OFF_LINE = "#d8d8d0", "#9aa0a6"


# ---------------------------------------------------------------- 장면 (DP 의 backdrop · platform 자리에 끼운다)
def backdrop(cv, w, h):
    """하늘 · 땅 (시안: 번지지 않는 두 빛)."""
    hz = int(h * HORIZON_C)
    cv.create_rectangle(0, 0, w, hz, fill=SKY_C, outline="")
    cv.create_rectangle(0, hz, w, h, fill=GROUND_C, outline="")


def platform(cv, cx, cy, rx, ry):
    """초록 받침: 둘레 4px · 아래쪽 안 그늘 6px."""
    ring = max(2, U.h(4))
    cv.create_oval(cx - rx - ring, cy - ry - ring, cx + rx + ring, cy + ry + ring, fill=PAD_RING, outline="")
    cv.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill=PAD_SH, outline="")
    cv.create_oval(cx - rx, cy - ry, cx + rx, cy + ry - max(3, U.h(6)), fill=PAD, outline="")


# DP 장면 함수를 이 테마 것으로 (관장 · 실시간은 dp.battle 의 것을, 레이드는 dp.raid_battle 이 가져간 것을 부른다)
DPB.backdrop = backdrop
DPB.platform = platform
DPR.backdrop = backdrop
DPR.platform = platform


def _frame(cv, x1, y1, x2, y2, fill=PAPER, inner=True, line=NAVY, tags=()):
    """배틀 창 배율(Z.U)로 그린 GBA 창."""
    return gba.frame(cv, x1, y1, x2, y2, fill=fill, inner=inner, line=line, tags=tags, s=U.h)


def _inset(inner=True):
    return gba.inset(inner=inner, s=U.h)


class GTouch(DPB.Touch):
    """GBA 창 모양의 글자 단추: 종이 바탕 · 남색 테, 올리면 연노랑 바탕에 빨간 ▶. 누르면 한 칸 내려앉는다.
    (DP 단추와 같은 말을 받는다 - 만든 단추의 class 만 바꿔 끼운다.)"""

    def draw(self):
        cv = self.cv
        try:
            cv.delete(self.tag)
        except tk.TclError:
            return
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        d = U.h(2) if self._down else 0
        self.paint(x1, y1 + d, x2, y2 + d)

    def paint(self, x1, y1, x2, y2):
        cv, s, t = self.cv, U.h, (self.tag,)
        on = self.enabled
        hov = self._hover and on
        fill = (SELY if hov else PAPER) if on else OFF_FILL
        _frame(cv, x1, y1, x2, y2, fill=fill, inner=on, line=NAVY if on else OFF_LINE, tags=t)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv.create_text(cx, cy, text=self.text, fill=INK if on else DIM, font=self.spec, anchor="center", tags=t)
        if hov:
            tw = kit.tkfont_of(cv, self.spec).measure(self.text)
            gba.cursor(cv, max(x1 + s(10), cx - tw // 2 - s(22)), cy, s(6), tags=t, s=s)


class MoveCell(DPB.MoveTouch):
    """기술 창 안의 칸 하나 (테 없음 - 시안 .moves). 윗줄 = ▶ 기술 이름, 아랫줄 = 타입 꼬리표 · PP.
    고른 칸(win._em_cur)에 빨간 ▶. 마우스를 올리면 그 칸을 고르고 (오른쪽 PP · 타입 창이 바뀐다), 설명은 글상자에."""

    def __init__(self, cv, move, command, peek, tag, win, idx):
        DPB.MoveTouch.__init__(self, cv, move, command, peek, tag=tag)
        self.win, self.idx = win, idx

    def draw(self):
        cv = self.cv
        try:
            cv.delete(self.tag)
        except tk.TclError:
            return
        if self.box:
            self.paint(*self.box)

    def paint(self, x1, y1, x2, y2):
        cv, s, t, m = self.cv, U.h, (self.tag,), self.move
        on = self.enabled
        cur = self.win._em_cur == self.idx
        if m.get("z") and on:
            cv.create_rectangle(x1, y1, x2, y2, fill=MOVE_Z, outline="", tags=t)
        elif self._hover and on:
            cv.create_rectangle(x1, y1, x2, y2, fill=SELY, outline="", tags=t)
        else:
            cv.create_rectangle(x1, y1, x2, y2, fill="", outline="", tags=t)      # 누를 자리
        ink = INK if on else DIM
        hgt = y2 - y1
        ny = y1 + int(hgt * 0.36)
        by = y1 + int(hgt * 0.74)
        if cur:
            gba.cursor(cv, x1 + s(4), ny, s(6), tags=t, s=s)
        tx = x1 + s(22)
        cv.create_text(tx, ny, text=self.text, fill=ink, font=F(14), anchor="w", tags=t)
        # 아랫줄: 타입 꼬리표 · PP
        col = U.TYPE_COLOR.get(m.get("type"), "#a8a878")
        tname = m.get("typeKr") or ""
        f = F(9)
        if tname:
            tw = kit.tkfont_of(cv, f).measure(tname) + s(12)
            th = kit.tkfont_of(cv, f).metrics("linespace") + s(2)
            tcol = col if on else "#b0b6be"
            cv.create_rectangle(tx, by - th // 2, tx + tw, by + th // 2, fill=tcol, outline="", tags=t)
            cv.create_text(tx + tw // 2, by, text=tname, fill=kit.look_of(tcol)[3], font=f, anchor="center", tags=t)
            tx += tw + s(8)
        pp, mx = m.get("pp") or 0, m.get("maxpp") or 0
        pcol = "#d02828" if pp <= 0 else ("#c06810" if mx and pp * 4 <= mx else (GRP if on else DIM))
        cv.create_text(tx, by, text="PP %d/%d" % (pp, mx), fill=pcol, font=F(10), anchor="w", tags=t)

    def on_hover(self, on):
        DPB.MoveTouch.on_hover(self, on)
        if on:
            self.win._em_focus(self.idx)


class EPill(DPB.Pill):
    """메가진화 · Z기술 켜기 (시안에 특별 단추가 없다 - GBA 단추 모양: 남색 테 · 그늘, 켜면 그 빛깔)."""

    def __init__(self, parent, text, command, height=34, bg=PAPER):
        DPB.Pill.__init__(self, parent, text, command, height=height, bg=bg)
        self.fill, self._fg, self.hover, self._shadow = PAPER, INK, SELY, NAVY
        self.draw()

    def draw(self):
        cv = self.holder
        try:
            cv.delete("all")
        except tk.TclError:
            return
        w, h, s = int(cv["width"]), self.h, U.h
        body = self.hover if self._in else self.fill
        g = max(2, s(3))
        y1, y2 = s(3), h - s(2)
        cv.create_rectangle(1 + g, y1 + g, w - 1, y2, fill=gba.SHADOW, outline="")
        cv.create_polygon(gba.chamfer(1, y1, w - 1 - g, y2 - g, max(1, s(2))), fill=NAVY, outline="")
        b = max(2, s(2))
        cv.create_rectangle(1 + b, y1 + b, w - 1 - g - b, y2 - g - b, fill=body, outline="")
        ink = self._fg
        if ink.lower() in ("#ffffff", "#fff"):
            ink = kit.look_of(self.fill)[3]
        cv.create_text((w - g) // 2, (y1 + y2 - g) // 2, text=self.text, fill=ink, font=F(12), anchor="center")


class GBALower(object):
    """DP 의 DPLower 앞에 섞는다: 글상자 · 아래 화면을 시안대로 칠한다 (동작은 DP · 기본 창 그대로)."""

    # ---------------- 글상자: GBA 창 (장면의 땅 위)
    def _draw_message(self):
        cv = getattr(self, "mcv", None)
        if cv is None:
            return
        try:
            cv.delete("all")
            cv.configure(bg=GROUND_C)
            self.msg_frame.configure(bg=GROUND_C)
            w = max(int(cv.winfo_width()), int(self.ww - 4)) if cv.winfo_width() > 1 else int(self.ww - 4)
            h = max(int(cv.winfo_height()), 1) if cv.winfo_height() > 1 else U.h(self.ZOOM_MSG)
        except tk.TclError:
            return
        s = U.h
        x1, y1, x2, y2 = s(6), s(2), w - s(6), h - s(3)
        _frame(cv, x1, y1, x2, y2)
        text = self._peeking if self._peeking else getattr(self, "_said", "")
        try:
            from common.korean import natural
            text = natural(text or "")
        except Exception:                                   # noqa: BLE001
            text = text or ""
        ins = _inset()
        kit.text(cv, x1 + ins + s(14), (y1 + y2) // 2, text, F(self.MSG_PT), fill=INK, anchor="w",
                 width=x2 - x1 - 2 * ins - s(28), tags=("msg",))

    # ---------------- 아래 화면
    def _commands(self):
        super(GBALower, self)._commands()
        for b in self._touch:
            b.__class__ = GTouch
        try:
            self.bcv.configure(bg=NAVY)
            self.cmd.configure(bg=NAVY)
        except tk.TclError:
            pass
        self._draw_lower()

    def _pill(self, parent, text, command, height=34, **_kw):
        return EPill(parent, text, command, height=height, bg=PAPER)

    def _draw_lower(self):
        cv = getattr(self, "bcv", None)
        if cv is None:
            return
        try:
            w, h = self._lower_wh()
            cv.delete("all")
        except tk.TclError:
            return
        self._lower_size = (w, h)
        s = U.h
        for b in self._touch:
            b.box = None
            b._hover = b._down = False
        self._move_btns = []
        self._plate_hits = []
        self.lower.reset()
        top = s(8)
        cv.create_rectangle(0, 0, w, h, fill=NAVY, outline="")
        cv.create_rectangle(0, 0, w, top, fill=NAVY_LO, outline="")
        self._draw_strip()
        y0 = top + s(22) + s(2)
        page = self._page
        if page == "moves":
            self._draw_moves(w, h, y0)
        elif page == "switch":
            self._draw_switch(w, h, y0)
        elif page == "result":
            self._draw_result(w, h, y0)
        elif page == "wait":
            self._draw_wait(w, h, y0)

    def _draw_strip(self):
        """맨 위 띠: 남색 위에 양쪽 파티의 볼 · 턴 · 남은 시간 (흰 글씨)."""
        cv = getattr(self, "bcv", None)
        if cv is None:
            return
        try:
            w, _h = self._lower_wh()
            cv.delete("strip")
        except tk.TclError:
            return
        s = U.h
        y, sh = s(8), s(22)
        t = ("strip",)
        cv.create_rectangle(0, y, w, y + sh + s(2), fill=NAVY, outline="", tags=t)
        d, gap = s(14), s(3)
        me, foe = getattr(self, "_teams", ([], []))
        by = y + (sh - d) / 2.0
        for i in range(6):
            x = s(10) + i * (d + gap)
            DPB.ball(cv, x, by, d, self._ball_state(me, i), tags=t)
            if foe is not None:
                x = w - s(10) - d - i * (d + gap)
                DPB.ball(cv, x, by, d, self._ball_state(foe, i), tags=t)
        text = getattr(self, "_turn_text", "")
        timer, danger = getattr(self, "_timer", ("", False))
        tcol = "#c8d0dc" if danger is None else ("#ff8070" if danger else "#ffc060")
        f = F(10)
        tw = kit.tkfont_of(cv, f).measure(text) if text else 0
        mw = kit.tkfont_of(cv, F(11)).measure(timer) if timer else 0
        gp = s(14) if text and timer else 0
        x = w // 2 - (tw + gp + mw) // 2
        if text:
            cv.create_text(x, y + sh // 2, text=text, fill="#ffffff", font=f, anchor="w", tags=t)
        if timer:
            cv.create_text(x + tw + gp, y + sh // 2, text=timer, fill=tcol, font=F(11), anchor="w", tags=t)

    # ---------------- 기술: 기술 창 2x2 + PP · 타입 창 + 단추
    def _em_focus(self, i):
        old = getattr(self, "_em_cur", None)
        if i == old:
            return
        self._em_cur = i
        for b in self._move_btns:
            if b.idx in (old, i):
                b.draw()
        self._em_info()

    def _em_info(self):
        """오른쪽 PP · 타입 창 (고른 기술) - 시안 .pp: PP 15/15 / 타입 [불꽃] / 위력 90 · 특수."""
        cv, s = self.bcv, U.h
        try:
            cv.delete("eminfo")
        except tk.TclError:
            return
        box = getattr(self, "_em_info_box", None)
        if not box:
            return
        x1, y1, x2, y2 = box
        t = ("eminfo",)
        moves = getattr(self, "_moves", [])
        i = getattr(self, "_em_cur", 0)
        if not (0 <= i < len(moves)):
            return
        m = moves[i]
        ins = _inset()
        lx, rx = x1 + ins + s(12), x2 - ins - s(12)
        top, bot = y1 + ins + s(4), y2 - ins - s(4)
        rh = (bot - top) / 3.0
        pp, mx = m.get("pp") or 0, m.get("maxpp") or 0
        pcol = "#d02828" if pp <= 0 else ("#c06810" if mx and pp * 4 <= mx else INK)
        cy = int(top + rh * 0.5)
        cv.create_text(lx, cy, text="PP", fill=INK, font=F(12), anchor="w", tags=t)
        cv.create_text(rx, cy, text="%d/%d" % (pp, mx), fill=pcol, font=F(14), anchor="e", tags=t)
        cy = int(top + rh * 1.5)
        cv.create_text(lx, cy, text="타입", fill=INK, font=F(12), anchor="w", tags=t)
        tname = m.get("typeKr") or "—"
        col = U.TYPE_COLOR.get(m.get("type"), "#a8a878")
        f = F(11)
        tw = kit.tkfont_of(cv, f).measure(tname) + s(16)
        th = kit.tkfont_of(cv, f).metrics("linespace") + s(4)
        b = max(2, s(2))
        cv.create_rectangle(rx - tw, cy - th // 2, rx, cy + th // 2, fill=DPB.mix(col, "#000000", 0.4), outline="",
                            tags=t)
        cv.create_rectangle(rx - tw + b, cy - th // 2 + b, rx - b, cy + th // 2 - b, fill=col, outline="", tags=t)
        cv.create_text(rx - tw // 2, cy, text=tname, fill=kit.look_of(col)[3], font=f, anchor="center", tags=t)
        # 셋째 줄: 위력 · 분류 · 명중 (분류는 빛깔)
        cy = int(top + rh * 2.5)
        f = F(10)
        x = lx
        bits = []
        if m.get("power"):
            bits.append("위력 %d" % m["power"])
        cat = CAT_KR.get(m.get("cat") or "status", "")
        for k, part in enumerate(bits + ([cat] if cat else []) + [("명중 %d" % m["acc"]) if m.get("acc") else "명중 —"]):
            if k:
                cv.create_text(x, cy, text=" · ", fill=GRP, font=f, anchor="w", tags=t)
                x += kit.tkfont_of(cv, f).measure(" · ")
            col = CAT_COLOR.get(m.get("cat") or "status", GRP) if part == cat else GRP
            cv.create_text(x, cy, text=part, fill=col, font=f, anchor="w", tags=t)
            x += kit.tkfont_of(cv, f).measure(part)

    def _draw_moves(self, w, h, y0):
        cv, s = self.bcv, U.h
        moves = getattr(self, "_moves", [])
        cur = getattr(self, "_em_cur", None)
        if cur is None or not (0 <= cur < len(moves)) or not self._usable(moves[cur]):
            cur = next((i for i, m in enumerate(moves[:4]) if self._usable(m)), 0)
        self._em_cur = cur
        gap = s(6)
        top, bot = y0 + s(4), h - s(6)
        rw = max(s(240), int(w * 0.33))
        lx1, lx2 = s(6), w - s(6) - rw - gap
        rx1, rx2 = lx2 + gap, w - s(6)
        # 왼쪽: 기술 창 (메가진화 · Z기술 켜기가 있으면 창 왼쪽 아래)
        _frame(cv, lx1, top, lx2, bot)
        ins = _inset()
        pad = s(6)
        mbot = bot - ins - pad
        self.tbar.configure(bg=PAPER)
        if self.mega.shown or self.gim.z.shown:
            self.tbar.update_idletasks()
            ph = max(self.tbar.winfo_reqheight(), s(36))
            cv.create_window(lx1 + ins + pad, mbot - ph // 2, window=self.tbar, anchor="w")
            mbot -= ph + s(2)
        mtop = top + ins + pad
        cw = (lx2 - lx1 - 2 * ins - 2 * pad - s(8)) // 2
        ch = (mbot - mtop - s(4)) // 2
        for i, m in enumerate(moves[:4]):
            cx1 = lx1 + ins + pad + (i % 2) * (cw + s(8))
            cy1 = mtop + (i // 2) * (ch + s(4))
            b = MoveCell(cv, m, (lambda k=m.get("key"): self.use_move(k)), self._peek, "mv%d" % i, self, i)
            b.layout(cx1, cy1, cx1 + cw, cy1 + ch)
            self._move_btns.append(b)
        # 오른쪽: PP · 타입 창 + 맨 아래 [포켓몬] [기권]
        bh = s(44)
        by1 = bot - bh
        bw = (rx2 - rx1 - gap) // 2
        self.switch_btn.layout(rx1, by1, rx1 + bw, bot)
        self.forfeit_btn.layout(rx2 - bw, by1, rx2, bot)
        iy2 = by1 - gap
        if iy2 - top >= s(60):
            _frame(cv, rx1, top, rx2, iy2)
            self._em_info_box = (rx1, top, rx2, iy2)
        else:
            self._em_info_box = None
        self._em_info()

    @staticmethod
    def _usable(m):
        return (m.get("pp") or 0) > 0 and not m.get("blocked")

    # ---------------- 교체: 파티 판 여섯 (GBA 창)
    def _draw_plate(self, i, m, box, active, hover):
        cv, s = self.bcv, U.h
        tag = "pl%d" % i
        cv.delete(tag)
        x1, y1, x2, y2 = box
        ok = self._plate_ok(i, m)
        if m.get("fainted"):
            fill = OFF_FILL
        elif hover and ok:
            fill = SELY
        else:
            fill = PAPER
        _frame(cv, x1, y1, x2, y2, fill=fill, inner=False, line=RED if active else NAVY, tags=(tag,))
        mid = (y1 + y2) // 2
        isz = DPB.Z.px(32)
        ix = x1 + s(22)
        if hover and ok:
            gba.cursor(cv, x1 + s(7), mid, s(5), tags=(tag,), s=s)
        img = cv.create_image(ix + isz // 2, mid, anchor="center", tags=(tag,))
        self._plate_thumb(img, m)
        tx = ix + isz + s(8)
        ink = INK if ok or active else DIM
        ph = y2 - y1
        ny = y1 + max(s(7), int(ph * 0.12))
        cv.create_text(tx, ny, text=m.get("name") or "", fill=ink, font=F(12), anchor="nw", tags=(tag,))
        cv.create_text(x2 - s(12), ny, text="Lv%d" % (m.get("level") or 0), fill=ink, font=F(10), anchor="ne",
                       tags=(tag,))
        sub = "쓰러짐" if m.get("fainted") else ("싸우는 중" if active else (m.get("statusKr") or ""))
        bx0, bx1 = tx, x2 - s(12)
        by = y1 + int(ph * 0.56)
        frac = (m.get("hp") or 0) / float(m.get("maxhp") or 1)
        b = max(1, s(2))
        cv.create_rectangle(bx0, by - s(4), bx1, by + s(4), fill=NAVY, outline="", tags=(tag,))
        t0, t1 = bx0 + b, bx1 - b
        cv.create_rectangle(t0, by - s(4) + b, t1, by + s(4) - b, fill=BAR_TRACK_C, outline="", tags=(tag,))
        if frac > 0:
            a, bb = hp_colors(frac)
            xe = t0 + int((t1 - t0) * max(0.0, min(1.0, frac)))
            cv.create_rectangle(t0, by - s(4) + b, xe, by, fill=a, outline="", tags=(tag,))
            cv.create_rectangle(t0, by, xe, by + s(4) - b, fill=bb, outline="", tags=(tag,))
        ly = y2 - max(s(6), int(ph * 0.10))
        if sub:
            cv.create_text(tx, ly, text=sub, fill="#d02828" if m.get("fainted") else ("#c06810" if active else ink),
                           font=F(9), anchor="sw", tags=(tag,))
        cv.create_text(bx1, ly, text="%d/%d" % (m.get("hp") or 0, m.get("maxhp") or 0), fill=ink, font=F(9),
                       anchor="se", tags=(tag,))

    # ---------------- 기다림 · 결과: GBA 창
    def _draw_wait(self, w, h, y0):
        cv, s = self.bcv, U.h
        title, note, quiet = getattr(self, "_wait", ("", None, False))
        bw = min(s(230), (w - s(60)) // 3)
        by1, by2 = h - s(56), h - s(10)
        x1, y1, x2, y2 = s(8), y0 + s(6), w - s(8), by1 - s(10)
        _frame(cv, x1, y1, x2, y2)
        width = x2 - x1 - s(48)
        th = kit.text_height(cv, title, F(15), width)
        nh = kit.text_height(cv, note, F(11), width) + s(8) if note else 0
        ty = (y1 + y2) // 2 - (th + nh) // 2
        kit.text(cv, (x1 + x2) // 2, ty, title, F(15), fill=DIM if quiet else "#c06810", anchor="n", width=width,
                 justify="center")
        if note:
            kit.text(cv, (x1 + x2) // 2, ty + th + s(8), note, F(11), anchor="n", width=width, justify="center")
        self.forfeit_btn.layout(w - s(12) - bw, by1, w - s(12), by2)

    def _draw_result(self, w, h, y0):
        cv, s = self.bcv, U.h
        res, title, lines = getattr(self, "_result", ("", "", []))
        x1, y1, x2, y2 = s(8), y0 + s(4), w - s(8), h - s(8)
        _frame(cv, x1, y1, x2, y2)
        ins = _inset()
        bw = max(kit.tkfont_of(cv, self.done_btn.spec).measure(self.done_btn.text) + s(56), s(200))
        self.done_btn.layout(x2 - ins - s(10) - bw, y2 - ins - s(10) - s(44), x2 - ins - s(10), y2 - ins - s(10))
        res = {"win": "won", "lose": "lost"}.get(res, res)
        col = {"won": "#c06810", "lost": "#c02828", "timeout": "#c02828"}.get(res, INK)
        tx = x1 + ins + s(18)
        kit.text(cv, tx, y1 + ins + s(10), title, F(22), fill=col, anchor="nw")
        ty = y1 + ins + s(10) + kit.tkfont_of(cv, F(22)).metrics("linespace") + s(8)
        width = x2 - ins - s(10) - bw - s(16) - tx
        for ln in lines:
            _a, b = kit.text(cv, tx, ty, ln, F(11), anchor="nw", width=width)
            bb = cv.bbox(b)
            ty = (bb[3] if bb else ty + s(18)) + s(4)


class GBADuel(GBALower):
    """1 대 1 창(관장 · 실시간)의 이름표 - 시안 .hp: GBA 창 · 이름 ♂ Lv / 'HP' 꼬리표 + 막대 / 숫자."""

    def _namebox(self, x, y, mine):
        s = U.h
        cv = self.cv
        w, h = s(330), self._plate_h(mine)
        x = (self.sw - w - s(12)) if mine else s(12)        # 장면 안쪽으로 (DP 는 가장자리에 붙인다)
        tag = "plate_%s" % ("me" if mine else "foe")
        _frame(cv, x, y, x + w, y + h, inner=False, tags=(tag,))
        ins = _inset(inner=False)
        left, right = x + ins + s(12), x + w - ins - s(12)
        items = {"x": left, "right": right, "y": y, "h": h, "mine": mine, "tag": tag}
        items["name"] = kit.text(cv, left, y + s(20), "", F(13), anchor="w", tags=(tag,))
        items["gender"] = cv.create_text(left, y + s(20), text="", anchor="w", font=F(13), tags=(tag,))
        items["lv"] = kit.text(cv, right, y + s(20), "", F(13), anchor="e", tags=(tag,))
        items["status_y"] = y + s(40)
        items["ability"] = kit.text(cv, right, y + s(40), "", F(9), fill=INK2, anchor="e", tags=(tag,))
        # 체력 막대: 주황 'HP' 꼬리표 + 남색 테 · 진회색 홈 + 두 빛깔 막대 (체력 빛깔은 그대로)
        by0, bh = y + s(50), s(15)
        f = F(9)
        hw = kit.tkfont_of(cv, f).measure("HP") + s(8)
        cv.create_rectangle(left, by0, left + hw, by0 + bh, fill=HP_TAG, outline="", tags=(tag,))
        cv.create_text(left + hw // 2, by0 + bh / 2.0, text="HP", fill="#ffffff", font=f, anchor="center",
                       tags=(tag,))
        b = max(2, s(2))
        bx0 = left + hw + s(6)
        cv.create_rectangle(bx0, by0, right, by0 + bh, fill=NAVY, outline="", tags=(tag,))
        tx0, tx1 = bx0 + b, right - b
        ty0, ty1 = by0 + b, by0 + bh - b
        cv.create_rectangle(tx0, ty0, tx1, ty1, fill=BAR_TRACK_C, outline="", tags=(tag,))
        mid = (ty0 + ty1) // 2
        items["bar"] = cv.create_rectangle(tx0, ty0, tx1, mid, fill=DPB.HP_COLORS[0][1], outline="", tags=(tag,))
        items["bar2"] = cv.create_rectangle(tx0, mid, tx1, ty1, fill=DPB.HP_COLORS[0][2], outline="", tags=(tag,))
        items["bar_geom"] = (tx0, ty0, tx1 - tx0, ty1 - ty0)
        items["hp"] = (kit.text(cv, right, y + s(80), "", F(13), anchor="e", tags=(tag,))
                       if (mine or self.FOE_HP) else None)
        items["balls"] = []
        return items
