# -*- coding: utf-8 -*-
"""블랙·화이트 테마 - 배틀 화면 (관장 · 실시간 · 레이드 세 창이 같이 쓴다). 시안 H 의 '배틀 (기술 고르기)':

    위 화면     어두운 장면 - 위에서 아래로 #20262e -> #15181c, 위 가운데에 하늘빛이 옅게 번진다 (.stage).
                받침은 가운데가 조금 밝은 어두운 타원 (.pad), 이름표는 검정 반투명 판 · 가는 테 (.hp):
                이름 · 성별 · Lv / 상태 · 특성 / 가는 체력 막대 / 체력 숫자 (정보는 DP 와 같다)
    글상자      어두운 판 · 가는 테 · 밝은 글씨
    아래 화면   짙은 회색 바탕 (빗금 · C기어 고리). 맨 위 줄에 양쪽 파티의 볼 · 턴 · 남은 시간.
                기술 넷 = 어두운 카드 2x2, 위에 타입 빛깔 띠 (.mv) - 이름 / 타입(그 빛깔) · 분류 · 위력 · 명중 / PP
                맨 아랫줄 = 알약 세 칸 (.sub): [메가진화 · Z기술] [포켓몬] [기권]
                시안의 '가방' 은 이 앱 배틀에 없어 빼고, '도망치다' 자리가 '기권' 이다. 메가진화 · Z기술 켜기는
                알약 모양 - 켜면 그 빛깔(보라 · 금빛)의 테와 번지는 빛 (시안의 하늘빛 고름 표시와 같은 말).
    고름 표시   마우스를 올린 기술 · 단추는 하늘빛 테 + 번지는 빛 (시안 .mv.sel)

흐름은 DP 와 같다 (skins/dp/battle.py 의 DPLower · DPDuel): 내 차례가 오면 기술 넷이 바로 나오고, 교체 · 기다림 ·
결과 판도 같은 자리다. 타입 빛깔 · 체력 빛깔은 바꾸지 않는다.
"""
import math
import tkinter as tk

from PIL import Image, ImageTk

from ..dp import battle as DB
from ..dp import kit
from . import (BG, CARD, CYAN, DEEP, DIMT, FAINT, GLOW_BG, GLOW_FAR, HP_TRACK, LINE, LINE_HI, PAD_EDGE,
               PANEL, PANEL_HI, PLATE_BG, STAGE_BOT, STAGE_TOP, TEXT, mix)
from . import _art as A

U = DB.U
F = DB.F

BALL_WHITE, BALL_LINE, BALL_OFF = "#f4f5f6", "#2a2e33", "#3a4048"
Z_INK = "#ffd75e"


# ---------------------------------------------------------------- 위 화면 조각
_STAGES = {}


def stage_photo(w, h):
    """시안 .stage 의 바탕 그림 (세로 그라데이션 + 위 가운데 하늘빛). 크기마다 한 번 만든다."""
    key = (int(w), int(h))
    ph = _STAGES.get(key)
    if ph is not None:
        return ph
    sw, sh = max(8, key[0] // 4), max(8, key[1] // 4)          # 1/4 로 셈하고 늘린다 (번지는 빛이라 티가 안 난다)
    top, bot, cyan = DB._rgb(STAGE_TOP), DB._rgb(STAGE_BOT), DB._rgb(CYAN)
    img = Image.new("RGB", (sw, sh))
    px = img.load()
    rx, ry = 0.6 * sw, 0.5 * sh
    for y in range(sh):
        t = y / float(max(1, sh - 1))
        base = [a + (b - a) * t for a, b in zip(top, bot)]
        for x in range(sw):
            d = math.hypot((x - sw / 2.0) / rx, y / ry)
            a = 0.18 * (1.0 - d / 0.7) if d < 0.7 else 0.0
            px[x, y] = tuple(int(round(c + (k - c) * a)) for c, k in zip(base, cyan))
    ph = ImageTk.PhotoImage(img.resize(key, Image.BILINEAR))
    _STAGES[key] = ph
    return ph


def pad(cv, cx, cy, rx, ry, tags=()):
    """시안 .pad: 가운데가 조금 밝은 어두운 타원 + 옅은 테."""
    base = mix(STAGE_BOT, STAGE_TOP, 0.5)
    for k, a in ((1.0, 0.05), (0.72, 0.09), (0.45, 0.14)):
        cv.create_oval(cx - rx * k, cy - ry * k, cx + rx * k, cy + ry * k, fill=mix(base, "#f2f4f6", a),
                       outline=PAD_EDGE if k == 1.0 else "", tags=tags)


def name_plate(cv, x1, y1, x2, y2, edge=LINE, tags=()):
    """시안 .hp: 검정 반투명 판 (장면 위에 미리 섞은 빛깔) · 가는 테 · 둥근 모서리 8."""
    return kit.rrect(cv, x1, y1, x2, y2, U.h(8), fill=PLATE_BG, outline=edge, width=1, tags=tags)


def ball(cv, x, y, d, state, tags=()):
    """작은 몬스터볼 (어두운 바탕에 맞춘 테). state: on · off(쓰러짐) · none(빈자리)."""
    lw = max(1, int(round(d / 7.0)))
    if state == "none":
        cv.create_oval(x, y, x + d, y + d, fill="", outline=LINE, width=lw, tags=tags)
        return
    if state == "off":
        cv.create_oval(x, y, x + d, y + d, fill=BALL_OFF, outline=LINE_HI, width=lw, tags=tags)
        return
    cv.create_oval(x, y, x + d, y + d, fill=BALL_WHITE, outline="", tags=tags)
    cv.create_arc(x, y, x + d, y + d, start=0, extent=180, style="chord", fill=DB.BALL_TOP, outline="", tags=tags)
    cy = y + d / 2.0
    cv.create_line(x, cy, x + d, cy, fill=BALL_LINE, width=lw, tags=tags)
    cv.create_oval(x, y, x + d, y + d, fill="", outline=BALL_LINE, width=lw, tags=tags)
    r = d / 5.0
    cv.create_oval(x + d / 2.0 - r, cy - r, x + d / 2.0 + r, cy + r, fill=BALL_WHITE, outline=BALL_LINE, width=lw,
                   tags=tags)


def readable(col, on=PANEL):
    """타입 빛깔 글씨가 어두운 판에서 안 읽히면 흰빛을 섞는다 (띠는 그 빛깔 그대로)."""
    def lum(c):
        out = []
        for v in DB._rgb(c):
            v /= 255.0
            out.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
    t = 0.0
    c = col
    while (lum(c) + 0.05) / (lum(on) + 0.05) < 4.5 and t < 0.7:
        t += 0.1
        c = mix(col, "#ffffff", t)
    return c


def glow(cv, x1, y1, x2, y2, r, tags=()):
    """고른 것 둘레의 하늘빛 (시안 box-shadow 0 0 12px)."""
    g1, g2 = U.h(5), U.h(2)
    kit.rrect(cv, x1 - g1, y1 - g1, x2 + g1, y2 + g1, r + g1, fill=GLOW_FAR, tags=tags)
    kit.rrect(cv, x1 - g2, y1 - g2, x2 + g2, y2 + g2, r + g2, fill=GLOW_BG, tags=tags)


# ---------------------------------------------------------------- 아래 화면 단추
class BWTouch(DB.Touch):
    """시안 .sub 의 알약 (어두운 판 · 가는 테 · 밝은 글씨). 올리면 하늘빛 테 + 번지는 빛, 누르면 한 칸 내려앉는다."""

    def draw(self):
        cv = self.cv
        try:
            cv.delete(self.tag)
        except tk.TclError:
            return
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        d = U.h(1) if self._down else 0
        self.paint(x1, y1 + d, x2, y2 + d)

    def paint(self, x1, y1, x2, y2):
        cv, t = self.cv, (self.tag,)
        r = (y2 - y1) // 2
        hot = self._hover and self.enabled
        if hot:
            glow(cv, x1, y1, x2, y2, r, tags=t)
        if self.enabled:
            kit.rrect(cv, x1, y1, x2, y2, r, fill=PANEL_HI if hot else PANEL, outline=CYAN if hot else LINE,
                      width=1, tags=t)
        else:
            kit.rrect(cv, x1, y1, x2, y2, r, fill=CARD, outline=PANEL_HI, width=1, tags=t)
        cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=self.text, fill=TEXT if self.enabled else FAINT,
                       font=self.spec, anchor="center", tags=t)


class BWMoveTouch(DB.MoveTouch):
    """시안 .mv: 어두운 카드 · 가는 테, 위에 타입 빛깔 띠 하나. 이름 / 타입 · 분류 · 위력 · 명중 / PP."""

    def draw(self):
        BWTouch.draw(self)

    def paint(self, x1, y1, x2, y2):
        cv, s, t, m = self.cv, U.h, (self.tag,), self.move
        col = U.TYPE_COLOR.get(m.get("type"), "#a8a878")
        on = self.enabled
        z = bool(m.get("z"))
        r = s(8)
        hot = self._hover and on
        if hot:
            glow(cv, x1, y1, x2, y2, r, tags=t)
        body = (mix(PANEL, Z_INK, 0.10) if z else PANEL) if on else CARD
        kit.rrect(cv, x1, y1, x2, y2, r, fill=body, outline=CYAN if hot else (LINE if on else PANEL_HI), width=1,
                  tags=t)
        # 위의 타입 빛깔 띠 (카드의 둥근 위 모서리를 따라 자른다)
        band = s(6)
        pts = kit._clip_poly([(px, py) for px, py in zip(*[iter(kit._round_pts(x1, y1, x2 + 1, y2, r))] * 2)],
                             x1, y1, x2 + 1, y1 + band)
        if len(pts) >= 3:
            cv.create_polygon([v for p in pts for v in p], fill=col if on else BALL_OFF, outline="", tags=t)
        ink = (Z_INK if z else TEXT) if on else FAINT
        h = y2 - y1 - band
        pad_x = s(14)
        cv.create_text(x1 + pad_x, y1 + band + int(h * 0.34), text=self.text, fill=ink, font=F(14), anchor="w",
                       tags=t)
        by = y1 + band + int(h * 0.74)
        tx = x1 + pad_x
        f10 = F(10)
        tname = m.get("typeKr") or ""
        if tname:
            cv.create_text(tx, by, text=tname, fill=readable(col, body) if on else FAINT, font=f10, anchor="w",
                           tags=t)
            tx += kit.tkfont_of(cv, f10).measure(tname + "  ")
        cat = DB.CAT_KR.get(m.get("cat") or "status", "")
        if cat:
            ccol = {"physical": "#f08a5a", "special": "#7aa8f5", "status": DIMT}.get(m.get("cat") or "status", DIMT)
            cv.create_text(tx, by, text="· " + cat, fill=ccol if on else FAINT, font=f10, anchor="w", tags=t)
            tx += kit.tkfont_of(cv, f10).measure("· " + cat + " ")
        bits = []
        if m.get("power"):
            bits.append("위력 %d" % m["power"])
        bits.append(("명중 %d" % m["acc"]) if m.get("acc") else "명중 —")
        cv.create_text(tx, by, text="· " + " · ".join(bits), fill=DIMT if on else FAINT, font=f10, anchor="w",
                       tags=t)
        pp, mx = m.get("pp") or 0, m.get("maxpp") or 0
        pcol = "#ff6b6b" if pp <= 0 else ("#f5aa5e" if mx and pp * 4 <= mx else DIMT)
        cv.create_text(x2 - pad_x, by, text="PP %d/%d" % (pp, mx), fill=pcol if on else FAINT, font=f10, anchor="e",
                       tags=t)


class BWPill(DB.Pill):
    """메가진화 · Z기술 켜기 - 알약. 켜면 그 빛깔(보라 · 금빛)의 테 + 번지는 빛 + 그 빛깔 글씨."""

    def __init__(self, parent, text, command, height=34, bg=BG):
        DB.Pill.__init__(self, parent, text, command, height=height, bg=bg)
        self.fill, self._fg, self.hover, self._shadow = PANEL, TEXT, PANEL_HI, LINE
        self.draw()

    def draw(self):
        cv = self.holder
        try:
            cv.delete("all")
        except tk.TclError:
            return
        w, h, s = int(cv["width"]), self.h, U.h
        y1, y2 = s(5), h - s(5)
        r = (y2 - y1) // 2
        on = (self.fill or "").lower() != PANEL.lower()
        if on:
            col = self.fill
            kit.rrect(cv, 1, y1 - s(3), w - 1, y2 + s(3), r + s(3), fill=mix(BG, col, 0.22))
            kit.rrect(cv, s(3), y1, w - s(3), y2, r, fill=mix(PANEL, col, 0.28 if self._in else 0.2), outline=col,
                      width=2)
            ink = mix(col, "#ffffff", 0.45)
        else:
            kit.rrect(cv, s(3), y1, w - s(3), y2, r, fill=PANEL_HI if self._in else PANEL,
                      outline=CYAN if self._in else LINE, width=1)
            ink = TEXT
        cv.create_text(w // 2, (y1 + y2) // 2, text=self.text, fill=ink, font=F(12), anchor="center")


# ---------------------------------------------------------------- 글상자 · 아래 화면
class BWLower(object):
    """DP 의 DPLower 앞에 섞어 글상자 · 아래 화면을 시안 H 로 칠한다 (흐름 · 교체 · 기다림 · 결과는 DP 그대로)."""

    # ---------------- 글상자
    def _message(self):
        f = tk.Frame(self.win, bg=BG, height=U.h(self.ZOOM_MSG), highlightthickness=0)
        f.pack(fill="x")
        f.pack_propagate(False)
        self.msg_frame = f
        self.mcv = tk.Canvas(f, bg=BG, highlightthickness=0, bd=0, height=U.h(self.ZOOM_MSG))
        self.mcv.pack(fill="both", expand=True)
        self.mcv.bind("<Configure>", lambda _e: self._draw_message())
        self._peeking = None
        self._draw_message()

    def _draw_message(self):
        cv = getattr(self, "mcv", None)
        if cv is None:
            return
        try:
            cv.delete("all")
            w = max(int(cv.winfo_width()), int(self.ww - 4)) if cv.winfo_width() > 1 else int(self.ww - 4)
            h = max(int(cv.winfo_height()), 1) if cv.winfo_height() > 1 else U.h(self.ZOOM_MSG)
        except tk.TclError:
            return
        s = U.h
        x1, y1, x2, y2 = s(10), s(4), w - s(10), h - s(5)
        A.panel(cv, x1, y1, x2, y2)
        text = self._peeking if self._peeking else getattr(self, "_said", "")
        try:
            from common.korean import natural
            text = natural(text or "")
        except Exception:                                   # noqa: BLE001
            text = text or ""
        kit.text(cv, x1 + s(18), (y1 + y2) // 2, text, F(self.MSG_PT), fill=TEXT, anchor="w",
                 width=x2 - x1 - s(36), tags=("msg",))

    # ---------------- 아래 화면
    def _commands(self):
        self.cmd = tk.Frame(self.win, bg=BG)
        self.cmd.pack(fill="both", expand=True)
        self.bcv = tk.Canvas(self.cmd, width=self.ww - 4, height=U.h(self.ZOOM_CMD), bg=BG,
                             highlightthickness=0, bd=0)
        self.bcv.pack(fill="both", expand=True)
        cv = self.bcv
        self.switch_btn = BWTouch(cv, "포켓몬", self.open_switch, "mon", F(15), tag="tomon")
        self.forfeit_btn = BWTouch(cv, self.FORFEIT_TEXT, self._run_action(), "run", F(15), tag="torun")
        self.cancel_btn = BWTouch(cv, "취소", self._dp_cancel, "run", F(14), tag="cancel")    # (교체 화면에만)
        self.done_btn = BWTouch(cv, self.DONE_TEXT, self.close, "run", F(14), tag="done")
        self._touch = [self.switch_btn, self.forfeit_btn, self.cancel_btn, self.done_btn]
        self._move_btns = []
        self._plate_hits = []
        self.lower = DB.LowerScreen(cv, lambda: self._touch + self._move_btns + self._plate_hits)
        self.tbar = tk.Frame(cv, bg=BG)
        self.mega = self._make_mega(self.tbar)
        self.gim = self._make_gim(self.tbar)
        self._page = getattr(self, "_page", "busy")
        self._lower_size = None
        cv.bind("<Configure>", self._lower_configure)
        self._draw_lower()

    def _pill(self, parent, text, command, height=34, **_kw):
        return BWPill(parent, text, command, height=height, bg=BG)

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
        A.backdrop(cv, 0, 0, w, h)
        cv.create_line(0, 0, w, 0, fill=LINE)
        self._draw_strip()
        y0 = s(8) + s(22) + s(2)
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
        """맨 위 줄: 양쪽 파티의 볼 · 턴 · 남은 시간 (바탕 위에 바로 - 띠를 깔지 않는다)."""
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
        cv.create_rectangle(0, y - s(4), w, y + sh + s(2), fill=BG, outline="", tags=t)
        d, gap = s(14), s(3)
        me, foe = getattr(self, "_teams", ([], []))
        by = y + (sh - d) / 2.0
        for i in range(6):
            ball(cv, s(14) + i * (d + gap), by, d, self._ball_state(me, i), tags=t)
            if foe is not None:              # (레이드는 상대 파티가 없다)
                ball(cv, w - s(14) - d - i * (d + gap), by, d, self._ball_state(foe, i), tags=t)
        text = getattr(self, "_turn_text", "")
        timer, danger = getattr(self, "_timer", ("", False))
        tcol = DIMT if danger is None else ("#ff6b6b" if danger else "#f5aa5e")
        f = F(10)
        tw = kit.tkfont_of(cv, f).measure(text) if text else 0
        mw = kit.tkfont_of(cv, F(11)).measure(timer) if timer else 0
        gap = s(14) if text and timer else 0
        x = w // 2 - (tw + gap + mw) // 2
        if text:
            cv.create_text(x, y + sh // 2, text=text, fill=DIMT, font=f, anchor="w", tags=t)
        if timer:
            cv.create_text(x + tw + gap, y + sh // 2, text=timer, fill=tcol, font=F(11), anchor="w", tags=t)

    def _draw_moves(self, w, h, y0):
        cv, s = self.bcv, U.h
        moves = getattr(self, "_moves", [])
        gap = s(10)
        bottom = s(48)
        top = y0 + s(6)
        avail_h = h - top - bottom - s(10)
        mh = (avail_h - gap) // 2
        mw = (w - s(28) - gap) // 2
        for i, m in enumerate(moves[:4]):
            x1 = s(14) + (i % 2) * (mw + gap)
            y1 = top + (i // 2) * (mh + gap)
            b = BWMoveTouch(cv, m, (lambda k=m.get("key"): self.use_move(k)), self._peek, tag="mv%d" % i)
            b.layout(x1, y1, x1 + mw, y1 + mh)
            self._move_btns.append(b)
        # 맨 아랫줄: 시안 .sub 의 알약 세 칸 - [메가진화 · Z기술] [포켓몬] [기권] (두 단추 자리는 늘 같다)
        ry1, ry2 = h - bottom, h - s(10)
        cv.create_window(s(14), (ry1 + ry2) // 2, window=self.tbar, anchor="w")
        self.tbar.update_idletasks()
        tw = self.tbar.winfo_reqwidth() if (self.mega.shown or self.gim.z.shown) else 0
        third = (w - s(28) - 2 * gap) // 3
        left = s(14) + (tw + gap if tw > 2 else 0)
        bw = max(1, min(third, (w - s(14) - gap - left) // 2))
        fx2 = w - s(14)
        self.forfeit_btn.layout(fx2 - bw, ry1, fx2, ry2)
        self.switch_btn.layout(fx2 - bw - gap - bw, ry1, fx2 - bw - gap, ry2)

    # ---------------- 교체 판 (시안 .card 처럼 어두운 카드)
    def _draw_plate(self, i, m, box, active, hover):
        cv, s = self.bcv, U.h
        tag = "pl%d" % i
        cv.delete(tag)
        x1, y1, x2, y2 = box
        ok = self._plate_ok(i, m)
        r = s(8)
        t = (tag,)
        if hover and ok:
            glow(cv, x1, y1, x2, y2, r, tags=t)
        fainted = m.get("fainted")
        fill = "#17191c" if fainted else (PANEL_HI if (hover and ok) else PANEL)
        edge = CYAN if (hover and ok) else (LINE_HI if active else LINE)
        kit.rrect(cv, x1, y1, x2, y2, r, fill=fill, outline=edge, width=2 if active else 1, tags=t)
        mid = (y1 + y2) // 2
        isz = DB.Z.px(32)
        ix = x1 + s(10)
        img = cv.create_image(ix + isz // 2, mid, anchor="center", tags=t)
        self._plate_thumb(img, m)
        tx = ix + isz + s(8)
        ink = TEXT if ok or active else FAINT
        ph = y2 - y1
        ny = y1 + max(s(6), int(ph * 0.12))
        cv.create_text(tx, ny, text=m.get("name") or "", fill=ink, font=F(12), anchor="nw", tags=t)
        cv.create_text(x2 - s(12), ny, text="Lv%d" % (m.get("level") or 0), fill=DIMT if ok or active else FAINT,
                       font=F(10), anchor="ne", tags=t)
        sub = "쓰러짐" if fainted else ("싸우는 중" if active else (m.get("statusKr") or ""))
        bx0, bx1 = tx, x2 - s(12)
        by = y1 + int(ph * 0.56)
        frac = (m.get("hp") or 0) / float(m.get("maxhp") or 1)
        kit.rrect(cv, bx0, by - s(3), bx1, by + s(3), s(3), fill=HP_TRACK, tags=t)
        if frac > 0:
            a, b = DB.hp_colors(frac)
            xe = bx0 + int((bx1 - bx0) * max(0.0, min(1.0, frac)))
            cv.create_rectangle(bx0, by - s(3), xe, by, fill=a, outline="", tags=t)
            cv.create_rectangle(bx0, by, xe, by + s(3), fill=b, outline="", tags=t)
        ly = y2 - max(s(5), int(ph * 0.10))
        if sub:
            cv.create_text(tx, ly, text=sub, fill="#ff6b6b" if fainted else (CYAN if active else ink), font=F(9),
                           anchor="sw", tags=t)
        cv.create_text(bx1, ly, text="%d/%d" % (m.get("hp") or 0, m.get("maxhp") or 0), fill=DIMT, font=F(9),
                       anchor="se", tags=t)


# ---------------------------------------------------------------- 1 대 1 장면 (관장 · 실시간)
class BWDuel(BWLower):
    """DP 의 DPDuel 앞에 섞어 위 화면(장면 · 이름표 · 알림)을 시안 H 로 그린다."""

    def _plate_h(self, mine):
        """이름표 높이 (시안 .hp 처럼 낮게 - 체력 숫자가 있는 판만 한 줄 더)."""
        s = U.h
        return s(84) if (mine or self.FOE_HP) else s(66)

    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = getattr(self, "cv", None)
        if cv is None:
            cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg=STAGE_TOP, highlightthickness=0)
            cv.pack(fill="x")
            self.cv = cv
        else:
            cv.delete("all")
            cv.configure(width=self.sw, height=self.sh)
        try:
            self.win.configure(bg=BG, highlightbackground=DEEP)
        except tk.TclError:
            pass
        sw, sh = self.sw, self.sh
        self._stage = stage_photo(sw, sh)
        cv.create_image(0, 0, image=self._stage, anchor="nw")
        self.foe_pos = (int(sw * 0.70), int(sh * 0.50))
        self.me_pos = (int(sw * 0.28), int(sh * 0.93))
        fx, fy = self.foe_pos
        mx, my = self.me_pos
        pad(cv, fx, fy, s(150), s(26))
        pad(cv, mx, my, s(190), s(32))
        self.trainer_item = cv.create_image(sw - s(70), fy + s(6), anchor="s")
        self.sprite = {"foe": cv.create_image(fx, fy + s(8), anchor="s"),
                       "me": cv.create_image(mx, my + s(10), anchor="s")}
        bw = s(330)
        self.box = {"foe": self._namebox(s(14), s(14), False),
                    "me": self._namebox(sw - bw - s(14), sh - self._plate_h(True) - s(14), True)}
        self.banner = []
        self._paint_watchers()

    def _namebox(self, x, y, mine):
        s = U.h
        cv = self.cv
        w, h = s(330), self._plate_h(mine)
        tag = "plate_%s" % ("me" if mine else "foe")
        name_plate(cv, x, y, x + w, y + h, tags=(tag,))
        left, right = x + s(14), x + w - s(14)
        items = {"x": left, "right": right, "y": y, "h": h, "mine": mine, "tag": tag}
        items["name"] = kit.text(cv, left, y + s(18), "", F(13), fill=TEXT, anchor="w", tags=(tag,))
        items["gender"] = cv.create_text(left, y + s(18), text="", anchor="w", font=F(13), tags=(tag,))
        items["lv"] = kit.text(cv, right, y + s(18), "", F(12), fill=TEXT, anchor="e", tags=(tag,))
        items["status_y"] = y + s(37)
        items["ability"] = kit.text(cv, right, y + s(37), "", F(9), fill=DIMT, anchor="e", tags=(tag,))
        # 체력 막대: 시안 .hp .b - 가는 홈 (빛깔은 DP 의 두 빛깔 그대로)
        bx0, bx1 = left, right
        by0, bh = y + s(50), s(8)
        kit.rrect(cv, bx0, by0, bx1, by0 + bh, s(4), fill=HP_TRACK, tags=(tag,))
        ty0, ty1 = by0 + s(1), by0 + bh - s(1)
        tx0, tx1 = bx0 + s(1), bx1 - s(1)
        mid = (ty0 + ty1) // 2
        items["bar"] = cv.create_rectangle(tx0, ty0, tx1, mid, fill=DB.HP_COLORS[0][1], outline="", tags=(tag,))
        items["bar2"] = cv.create_rectangle(tx0, mid, tx1, ty1, fill=DB.HP_COLORS[0][2], outline="", tags=(tag,))
        items["bar_geom"] = (tx0, ty0, tx1 - tx0, ty1 - ty0)
        items["hp"] = (kit.text(cv, right, y + s(71), "", F(12), fill=TEXT, anchor="e", tags=(tag,))
                       if (mine or self.FOE_HP) else None)
        items["balls"] = []
        return items

    def _show_banner(self, who, text):
        """특성 · 메가진화 · Z기술 같은 알림: 이름표 곁의 어두운 판, 하늘빛 테."""
        s = U.h
        cv = self.cv
        f = F(11)
        tw = kit.tkfont_of(cv, f).measure(text) + s(28)
        th = s(32)
        if who == "foe":
            x, y = s(14), s(14) + self._plate_h(False) + s(8)
        else:
            x, y = self.sw - tw - s(14), self.sh - self._plate_h(True) - s(14) - th - s(8)
        tag = "banner%d" % len(self.banner)
        kit.rrect(cv, x, y, x + tw, y + th, s(8), fill=PLATE_BG, outline=CYAN, width=1, tags=(tag,))
        cv.create_text(x + tw // 2, y + th // 2, text=text, fill=TEXT, font=f, anchor="center", tags=(tag,))
        self.banner.append(tag)

        def gone():
            try:
                cv.delete(tag)
            except tk.TclError:
                pass
        self.later(1400, gone)

