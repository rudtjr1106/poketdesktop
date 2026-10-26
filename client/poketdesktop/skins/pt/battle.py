# -*- coding: utf-8 -*-
"""플라티나 배틀 화면 - 관장 · 실시간 · 레이드 배틀 창이 같이 쓰는 그림 (시안 B 의 '배틀 (기술 고르기)').

    위 장면     옅은 하늘(#cfe9f7) → 연둣빛(#e9f4d8) 으로 번지는 바탕, 연둣빛 발판(아래로 그늘),
                이름표는 옅은 흰 판(#f6f7f9) · 3px 진한 테 · 왼쪽 아래만 각진 둥근 10, 체력은 진회색 홈.
    글상자      강철 바탕 위의 옅은 판 (둥근 16 · 3px 진한 테) - 이 창의 말은 전부 여기에 나온다.
    아래 화면   강철 바탕(점). 맨 위는 머리 띠(양쪽 파티의 볼 · 턴 · 남은 시간, 흰 글씨).
                기술 → 타입 빛깔의 큰 캡슐 넷 (2x2: 이름 / 타입 · 분류 · 위력 · 명중 · PP),
                맨 아래 캡슐 셋 = 시안의 [가방 빨강 · 포켓몬 초록 · 도망치기 파랑] 자리에
                       [메가진화 · Z기술 (시안의 빨간 '가방' 자리 모양) · 포켓몬(초록) · 기권(파랑)]
                교체 → 옅은 판 여섯 (나와 있는 것은 하늘색 테) + 파란 캡슐 '취소'
                결과 → 옅은 판 + 단추 하나
                올리면 하늘색 빛 고리 (시안의 '고른 것'), 누르면 2px 내려앉는다.

흐름은 DP 그대로다 (skins/dp/battle.py) - 내 차례면 기술 넷 + [포켓몬][기권]이 바로 나오고, 기술에 올리면
글상자에 설명이 나온다. 시안의 '가방' 단추는 이 앱 배틀에 없어서 그 자리를 메가진화 · Z기술 켜기가 쓴다
(켜면 그 빛깔 - 보라 · 금빛 - 로 바뀌고 빛 고리를 두른다). 타입 빛깔 · 체력 빛깔은 그대로다.
"""
import tkinter as tk

from ..dp import battle as DB
from ..dp import kit
from ..dp.battle import CAT_KR, HP_COLORS, F, U, Z, ball, hp_colors, mix
from . import BAR_SH, CYAN, CYAN_SOFT, DIM, FAINT, INK, RIM, STEEL, STEEL2, WHITE
from . import _pt as P

SKY_TOP, SKY_BOT = "#cfe9f7", "#e9f4d8"        # 위 장면 (시안 .scene)
PAD, PAD_SH = "#c9dca0", "#a7bd7a"             # 발판
BOX_FILL = "#f6f7f9"                           # 이름표 · 글상자
GROOVE = "#3a414c"                             # 체력 홈


def backdrop(cv, w, h):
    """위 장면: 옅은 하늘 → 연둣빛, 아래 4px 진한 줄 (시안의 border-bottom)."""
    P.gradient(cv, 0, 0, w, h - 4, SKY_TOP, SKY_BOT, band=4)
    cv.create_rectangle(0, h - 4, w, h, fill=RIM, outline="")


def platform(cv, cx, cy, rx, ry):
    """연둣빛 발판 (inset 0 -5px 0 #a7bd7a - 아래쪽에 그늘)."""
    g = max(3, int(ry * 0.22))
    cv.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill=PAD_SH, outline="")
    cv.create_oval(cx - rx, cy - ry, cx + rx, cy + ry - g, fill=PAD, outline="")


def hp_box(cv, x1, y1, x2, y2, tags=(), edge=RIM):
    """이름표: 옅은 흰 판 · 3px 테 · 둥근 10 (왼쪽 아래만 각졌다)."""
    r = U.h(10)
    for (a, b, c, d, f) in ((x1, y1, x2, y2, edge), (x1 + 3, y1 + 3, x2 - 3, y2 - 3, BOX_FILL)):
        rr = r if f == edge else max(0, r - 3)
        pts = kit._round_pts(a, b, c, d, rr)
        cv.create_polygon(pts, fill=f, outline="", tags=tags)
        cv.create_rectangle(a, d - rr, a + rr, d, fill=f, outline="", tags=tags)      # 왼쪽 아래 귀


def hp_groove(cv, x1, y1, x2, y2, tags=()):
    """체력 홈 (#3a414c, 둥근 4)."""
    return P.rpoly(cv, x1, y1, x2, y2, (y2 - y1) // 2, fill=GROOVE, tags=tags)


# ---------------------------------------------------------------- 아래 화면 단추
class PtTouch(DB.Touch):
    """아래 화면의 캡슐 단추 (시안 .sub span): 빛깔 캡슐, 흰 글씨에 진한 그림자. 올리면 하늘색 빛 고리."""

    LOOK = {"mon": "green", "run": "blue"}

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
        if self._hover and self.enabled:
            P.glow(cv, x1, y1 + d, x2, y2 - U.h(4) + d, (y2 - U.h(4) - y1) // 2, tags=(self.tag,))

    def paint(self, x1, y1, x2, y2):
        cv, t = self.cv, (self.tag,)
        look = "off" if not self.enabled else self.LOOK.get(self.kind, "white")
        sh = U.h(4)
        P.rpoly(cv, x1, y1 + sh, x2, y2, (y2 - y1 - sh) // 2, fill=mix(P.LOOKS[look][2], "#000000", 0.2), tags=t)
        P.capsule(cv, x1, y1, x2, y2 - sh, look, self.text, self.spec, tags=t)


class PtMove(DB.MoveTouch):
    """기술 단추 (시안 .mv): 타입 빛깔 캡슐 - 위가 밝은 그라데이션, 반투명 검은 테, 위쪽 흰 빛 줄.
    이름(크게) / 타입 · 분류 · 위력 · 명중 (작게) / PP (오른쪽 아래). 밝은 타입은 진한 글씨 (그림자 없이)."""

    def draw(self):
        PtTouch.draw(self)

    def paint(self, x1, y1, x2, y2):
        cv, s, t, m = self.cv, U.h, (self.tag,), self.move
        col = U.TYPE_COLOR.get(m.get("type"), "#a8a878")
        on = self.enabled
        sh = s(4)
        r = min(s(18), (y2 - y1) // 2)
        if on:
            top, bot = mix(col, "#ffffff", 0.22), col
            rim = "#d0a000" if m.get("z") else mix(col, "#000000", 0.45)
        else:
            top, bot, rim = "#e2e6ea", "#cfd4da", "#9aa3ad"
        P.rpoly(cv, x1, y1 + sh, x2, y2, r, fill=mix(rim, "#000000", 0.25) if on else rim, tags=t)
        b2 = y2 - sh
        P.rpoly(cv, x1, y1, x2, b2, r, fill=rim, tags=t)
        e = s(3)
        P.grad_round(cv, x1 + e, y1 + e, x2 - e, b2 - e, max(0, r - e), top, bot, tags=t)
        if on:
            rr = max(0, r - e)
            cv.create_line(x1 + e + rr * 0.8, y1 + e + 2, x2 - e - rr * 0.8, y1 + e + 2, fill=mix(top, "#ffffff", 0.5),
                           width=2, tags=t)
        # 밝은 타입(노말 · 불꽃 · 전기 · 얼음 · 비행 …)은 진한 글씨, 진한 타입은 흰 글씨에 진한 그림자 - 늘 읽히게
        r_, g_, b_ = (int(col[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        lum = 0.299 * r_ + 0.587 * g_ + 0.114 * b_ > 0.56
        ink = (INK if lum else WHITE) if on else FAINT
        shadow = mix(col, "#000000", 0.6) if (on and not lum) else None
        def say(x, y, text, spec, anchor, fill=None):
            if shadow:
                cv.create_text(x, y + 2, text=text, fill=shadow, font=spec, anchor=anchor, tags=t)
            cv.create_text(x, y, text=text, fill=fill or ink, font=spec, anchor=anchor, tags=t)

        h = b2 - y1
        lx = x1 + s(18)
        say(lx, y1 + int(h * 0.34), self.text, F(15), "w")
        by = y1 + int(h * 0.74)
        bits = [m.get("typeKr") or ""]
        cat = CAT_KR.get(m.get("cat") or "status", "")
        if cat:
            bits.append(cat)
        if m.get("power"):
            bits.append("위력 %d" % m["power"])
        bits.append(("명중 %d" % m["acc"]) if m.get("acc") else "명중 —")
        say(lx, by, " · ".join(b for b in bits if b), F(10), "w")
        pp, mx = m.get("pp") or 0, m.get("maxpp") or 0
        pfill = None
        if on and pp <= 0:
            pfill = "#ffd0c8" if not lum else "#b02020"
        elif on and mx and pp * 4 <= mx:
            pfill = "#ffe08a" if not lum else "#9a4a00"
        say(x2 - s(18), by, "PP %d/%d" % (pp, mx), F(11), "e", fill=pfill)


class PtPill(DB.Pill):
    """메가진화 · Z기술 켜기 - 시안의 빨간 '가방' 자리 모양 (큰 캡슐). 켜면 그 기능의 빛깔 + 빛 고리.

    ui_mega.MegaToggle · ui_gimmick.Toggle 은 fill · _fg · hover · _shadow 를 바꿔 끼우고 configure(state=) 를
    부른다 - 꺼진 것은 fill 이 OFF 그대로다."""

    OFF = "#e04a3c"

    def __init__(self, parent, text, command, height=34, bg=STEEL2):
        DB.Pill.__init__(self, parent, text, command, height=height, bg=bg)
        self.fill, self._fg, self.hover, self._shadow = self.OFF, WHITE, "#ff6a5a", "#7a1c14"
        self.draw()

    def set_size(self, w, h):
        try:
            if int(self.holder["width"]) != int(w) or self.h != int(h):
                self.h = int(h)
                self.holder.configure(width=int(w), height=int(h))
                self.draw()
        except tk.TclError:
            pass

    def draw(self):
        cv = self.holder
        try:
            cv.delete("all")
        except tk.TclError:
            return
        w, h = int(cv["width"]), self.h
        sh = U.h(4)
        on = self.fill != self.OFF
        body = self.fill if not self._in else self.hover
        top = mix(body, "#ffffff", 0.35)
        rim = self._shadow
        g = U.h(3) if on else 0
        x1, y1, x2, y2 = g, g, w - g, h - g
        if on:
            P.rpoly(cv, 0, 0, w, h - sh + g, (h - sh) // 2 + g, fill="", outline=P.GLOW, width=g)
        P.rpoly(cv, x1, y1 + sh, x2, y2, (y2 - y1 - sh) // 2, fill=mix(rim, "#000000", 0.2))
        P.rpoly(cv, x1, y1, x2, y2 - sh, (y2 - sh - y1) // 2, fill=rim)
        e = 3
        P.grad_round(cv, x1 + e, y1 + e, x2 - e, y2 - sh - e, max(0, (y2 - sh - y1) // 2 - e), top, body)
        ink = self._fg if kit.look_of(self.fill)[3] == "#ffffff" else INK
        cy = (y1 + y2 - sh) // 2
        if ink == WHITE:
            cv.create_text(w // 2, cy + 2, text=self.text, fill=mix(rim, "#000000", 0.2), font=F(14), anchor="center")
        cv.create_text(w // 2, cy, text=self.text, fill=ink, font=F(14), anchor="center")

    def configure(self, text=None, state=None, **_kw):
        if text is not None:
            self.text = str(text)
        self.draw()

    config = configure


# ---------------------------------------------------------------- 글상자 · 아래 화면 (세 배틀 창)
class PtLower(object):
    """DP 배틀 창(DB.DPLower)의 글상자 · 아래 화면을 시안으로 그린다. 창 클래스 앞에 섞는다:

        class GymBattleWindow(PtDuel, DPG.GymBattleWindow)
    """

    # ---------------- 글상자
    def _message(self):
        f = tk.Frame(self.win, bg=STEEL, height=U.h(self.ZOOM_MSG), highlightthickness=0)
        f.pack(fill="x")
        f.pack_propagate(False)
        self.msg_frame = f
        self.mcv = tk.Canvas(f, bg=STEEL, highlightthickness=0, bd=0, height=U.h(self.ZOOM_MSG))
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
        P.steel(cv, 0, 0, w, h)
        x1, y1, x2, y2 = s(8), s(5), w - s(8), h - s(4)
        P.panel(cv, x1, y1, x2, y2, r=s(16), fill=BOX_FILL)
        text = self._peeking if self._peeking else getattr(self, "_said", "")
        try:
            from common.korean import natural
            text = natural(text or "")
        except Exception:                                   # noqa: BLE001
            text = text or ""
        kit.text(cv, x1 + s(18), (y1 + y2) // 2, text, F(self.MSG_PT), fill=INK, anchor="w",
                 width=x2 - x1 - s(36), tags=("msg",))

    # ---------------- 아래 화면
    def _commands(self):
        self.cmd = tk.Frame(self.win, bg=STEEL)
        self.cmd.pack(fill="both", expand=True)
        self.bcv = tk.Canvas(self.cmd, width=self.ww - 4, height=U.h(self.ZOOM_CMD), bg=STEEL,
                             highlightthickness=0, bd=0)
        self.bcv.pack(fill="both", expand=True)
        cv = self.bcv
        self.switch_btn = PtTouch(cv, "포켓몬", self.open_switch, "mon", F(15), tag="tomon")
        self.forfeit_btn = PtTouch(cv, self.FORFEIT_TEXT, self._run_action(), "run", F(15), tag="torun")
        self.cancel_btn = PtTouch(cv, "취소", self._dp_cancel, "run", F(14), tag="cancel")
        self.done_btn = PtTouch(cv, self.DONE_TEXT, self.close, "run", F(14), tag="done")
        self._touch = [self.switch_btn, self.forfeit_btn, self.cancel_btn, self.done_btn]
        self._move_btns = []
        self._plate_hits = []
        self.lower = DB.LowerScreen(cv, lambda: self._touch + self._move_btns + self._plate_hits)
        self.tbar = tk.Frame(cv, bg=STEEL2)       # (아래 화면 맨 아래 줄의 강철 빛)
        self.mega = self._make_mega(self.tbar)
        self.gim = self._make_gim(self.tbar)
        self._page = getattr(self, "_page", "busy")
        self._lower_size = None
        cv.bind("<Configure>", self._lower_configure)
        self._draw_lower()

    def _pill(self, parent, text, command, height=34, **_kw):
        return PtPill(parent, text, command, height=height)

    STRIP_PX = 28

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
        P.steel(cv, 0, 0, w, h)
        self._draw_strip()
        y0 = s(self.STRIP_PX) + s(2)
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
        cv = getattr(self, "bcv", None)
        if cv is None:
            return
        try:
            w, _h = self._lower_wh()
            cv.delete("strip")
        except tk.TclError:
            return
        s = U.h
        sh = s(self.STRIP_PX)
        t = ("strip",)
        P.head_band(cv, 0, 0, w, sh, tags=t)
        d, gap = s(15), s(3)
        me, foe = getattr(self, "_teams", ([], []))
        by = (sh - 3 - d) / 2.0
        for i in range(6):
            x = s(12) + i * (d + gap)
            ball(cv, x, by, d, self._ball_state(me, i), tags=t)
            if foe is not None:
                x = w - s(12) - d - i * (d + gap)
                ball(cv, x, by, d, self._ball_state(foe, i), tags=t)
        text = getattr(self, "_turn_text", "")
        timer, danger = getattr(self, "_timer", ("", False))
        tcol = "#c8d0da" if danger is None else ("#ff9a8a" if danger else "#ffd27a")
        f = F(11)
        tw = kit.tkfont_of(cv, f).measure(text) if text else 0
        mw = kit.tkfont_of(cv, F(11)).measure(timer) if timer else 0
        g = s(14) if text and timer else 0
        x = w // 2 - (tw + g + mw) // 2
        ym = (sh - 3) // 2
        if text:
            P.band_title(cv, x, ym, text, f, anchor="w", tags=t)
        if timer:
            cv.create_text(x + tw + g, ym + 2, text=timer, fill=BAR_SH, font=F(11), anchor="w", tags=t)
            cv.create_text(x + tw + g, ym, text=timer, fill=tcol, font=F(11), anchor="w", tags=t)

    def _draw_moves(self, w, h, y0):
        """시안 .touch: 2x2 기술 캡슐 + 맨 아래 캡슐 셋 (사이 10)."""
        cv, s = self.bcv, U.h
        moves = getattr(self, "_moves", [])
        gap = s(10)
        side = s(14)
        bottom_h = s(48)
        top = y0 + s(8)
        avail = h - top - bottom_h - s(10) - gap
        mh = (avail - gap) // 2
        mw = (w - 2 * side - gap) // 2
        for i, m in enumerate(moves[:4]):
            x1 = side + (i % 2) * (mw + gap)
            y1 = top + (i // 2) * (mh + gap)
            b = PtMove(cv, m, (lambda k=m.get("key"): self.use_move(k)), self._peek, tag="mv%d" % i)
            b.layout(x1, y1, x1 + mw, y1 + mh)
            self._move_btns.append(b)
        ry2 = h - s(10)
        ry1 = ry2 - bottom_h
        tw = (w - 2 * side - 2 * gap) // 3
        # 왼쪽 칸: 메가진화 · Z기술 (시안의 빨간 '가방' 자리) - 보일 때만
        shown = [p for p in (self.mega, self.gim.z) if p.shown]
        if shown:
            pw = max(s(60), (tw - s(20) * len(shown)) // len(shown))
            for p in shown:
                set_size = getattr(p.btn, "set_size", None)
                if set_size is not None:
                    set_size(pw, bottom_h)
        cv.create_window(side, (ry1 + ry2) // 2, window=self.tbar, anchor="w")
        self.tbar.update_idletasks()
        x2 = w - side
        self.forfeit_btn.layout(x2 - tw, ry1, x2, ry2)
        self.switch_btn.layout(x2 - 2 * tw - gap, ry1, x2 - tw - gap, ry2)

    def _draw_switch(self, w, h, y0):
        cv, s = self.bcv, U.h
        side, forced = getattr(self, "_switch", ({"team": [], "slot": 0}, True))
        team = side.get("team") or []
        gap = s(10)
        bottom = 0 if forced else s(54)
        cols, rows = 3, 2
        pw = (w - s(28) - gap * (cols - 1)) // cols
        ph = (h - y0 - s(12) - bottom - s(10) - gap * (rows - 1)) // rows
        for i, m in enumerate(team[:6]):
            x1 = s(14) + (i % cols) * (pw + gap)
            y1 = y0 + s(10) + (i // cols) * (ph + gap)
            box = (x1, y1, x1 + pw, y1 + ph)
            active = i == side.get("slot")
            self._plate_hits.append(DB.PlateHit(self, i, m, box, active, self._plate_ok(i, m)))
            self._draw_plate(i, m, box, active, False)
        if not forced:
            self.cancel_btn.layout(s(14), h - bottom, w - s(14), h - s(10))

    def _draw_plate(self, i, m, box, active, hover):
        cv, s = self.bcv, U.h
        tag = "pl%d" % i
        cv.delete(tag)
        x1, y1, x2, y2 = box
        ok = self._plate_ok(i, m)
        t = (tag,)
        r = s(16)
        if hover and ok:
            P.glow(cv, x1, y1, x2, y2, r, tags=t)
        fill = "#d6dbe1" if m.get("fainted") else (CYAN_SOFT if (hover and ok) else BOX_FILL)
        P.panel(cv, x1, y1, x2, y2, r=r, fill=fill, rim=CYAN if active else RIM, tags=t)
        mid = (y1 + y2) // 2
        isz = Z.px(32)
        ix = x1 + s(12)
        img = cv.create_image(ix + isz // 2, mid, anchor="center", tags=t)
        self._plate_thumb(img, m)
        tx = ix + isz + s(8)
        ink = INK if ok or active else FAINT
        ph = y2 - y1
        ny = y1 + max(s(7), int(ph * 0.13))
        cv.create_text(tx, ny, text=m.get("name") or "", fill=ink, font=F(12), anchor="nw", tags=t)
        cv.create_text(x2 - s(14), ny, text="Lv%d" % (m.get("level") or 0), fill=ink, font=F(10), anchor="ne",
                       tags=t)
        sub = "쓰러짐" if m.get("fainted") else ("싸우는 중" if active else (m.get("statusKr") or ""))
        bx0, bx1 = tx, x2 - s(14)
        by = y1 + int(ph * 0.56)
        frac = (m.get("hp") or 0) / float(m.get("maxhp") or 1)
        hp_groove(cv, bx0, by - s(4), bx1, by + s(4), tags=t)
        if frac > 0:
            a, b = hp_colors(frac)
            t0, t1 = bx0 + s(2), bx1 - s(2)
            xe = t0 + int((t1 - t0) * max(0.0, min(1.0, frac)))
            cv.create_rectangle(t0, by - s(2), xe, by, fill=a, outline="", tags=t)
            cv.create_rectangle(t0, by, xe, by + s(2), fill=b, outline="", tags=t)
        ly = y2 - max(s(6), int(ph * 0.11))
        if sub:
            cv.create_text(tx, ly, text=sub, fill="#d0342a" if m.get("fainted") else ("#127ea8" if active else ink),
                           font=F(9), anchor="sw", tags=t)
        cv.create_text(bx1, ly, text="%d/%d" % (m.get("hp") or 0, m.get("maxhp") or 0), fill=ink, font=F(9),
                       anchor="se", tags=t)

    def _draw_wait(self, w, h, y0):
        cv, s = self.bcv, U.h
        title, note, quiet = getattr(self, "_wait", ("", None, False))
        bw = min(s(240), (w - s(60)) // 3)
        by1, by2 = h - s(58), h - s(12)
        x1, y1, x2, y2 = s(14), y0 + s(10), w - s(14), by1 - s(12)
        P.panel(cv, x1, y1, x2, y2, fill=BOX_FILL)
        width = x2 - x1 - s(48)
        th = kit.text_height(cv, title, F(15), width)
        nh = kit.text_height(cv, note, F(11), width) + s(8) if note else 0
        ty = (y1 + y2) // 2 - (th + nh) // 2
        kit.text(cv, (x1 + x2) // 2, ty, title, F(15), fill=DIM if quiet else "#b85a10", anchor="n", width=width,
                 justify="center")
        if note:
            kit.text(cv, (x1 + x2) // 2, ty + th + s(8), note, F(11), fill=INK, anchor="n", width=width,
                     justify="center")
        self.forfeit_btn.layout(w - s(14) - bw, by1, w - s(14), by2)

    def _draw_result(self, w, h, y0):
        cv, s = self.bcv, U.h
        res, title, lines = getattr(self, "_result", ("", "", []))
        x1, y1, x2, y2 = s(14), y0 + s(10), w - s(14), h - s(12)
        P.panel(cv, x1, y1, x2, y2, fill=BOX_FILL)
        bw = max(kit.tkfont_of(cv, self.done_btn.spec).measure(self.done_btn.text) + s(56), s(210))
        self.done_btn.layout(x2 - s(14) - bw, y2 - s(14) - s(50), x2 - s(14), y2 - s(14))
        res = {"win": "won", "lose": "lost"}.get(res, res)
        col = {"won": "#b85a10", "lost": "#c02828", "timeout": "#c02828"}.get(res, INK)
        kit.text(cv, x1 + s(24), y1 + s(16), title, F(22), fill=col, anchor="nw")
        ty = y1 + s(16) + kit.tkfont_of(cv, F(22)).metrics("linespace") + s(8)
        width = x2 - s(14) - bw - s(16) - (x1 + s(24))
        for ln in lines:
            _a, b = kit.text(cv, x1 + s(24), ty, ln, F(11), fill=INK, anchor="nw", width=width)
            bb = cv.bbox(b)
            ty = (bb[3] if bb else ty + s(18)) + s(4)


# ---------------------------------------------------------------- 1 대 1 장면 (관장 · 실시간)
class PtDuel(PtLower):
    """1 대 1 배틀 창의 위 장면 - 시안의 하늘 · 발판 · 이름표. 창 클래스(DP 창) 앞에 섞는다."""

    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = getattr(self, "cv", None)
        if cv is None:
            cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg=SKY_TOP, highlightthickness=0)
            cv.pack(fill="x")
            self.cv = cv
        else:
            cv.delete("all")
            cv.configure(width=self.sw, height=self.sh)
        try:
            self.win.configure(bg=STEEL, highlightbackground=RIM)
        except tk.TclError:
            pass
        sw, sh = self.sw, self.sh
        backdrop(cv, sw, sh)
        self.foe_pos = (int(sw * 0.70), int(sh * 0.50))
        self.me_pos = (int(sw * 0.28), int(sh * 0.93))
        fx, fy = self.foe_pos
        mx, my = self.me_pos
        platform(cv, fx, fy, s(150), s(26))
        platform(cv, mx, my, s(190), s(32))
        self.trainer_item = cv.create_image(sw - s(70), fy + s(6), anchor="s")
        self.sprite = {"foe": cv.create_image(fx, fy + s(8), anchor="s"),
                       "me": cv.create_image(mx, my + s(10), anchor="s")}
        bw = s(330)
        self.box = {"foe": self._namebox(s(16), s(14), False),
                    "me": self._namebox(sw - bw - s(16), sh - self._plate_h(True) - s(16), True)}
        self.banner = []
        self._paint_watchers()

    def _namebox(self, x, y, mine):
        s = U.h
        cv = self.cv
        w, h = s(330), self._plate_h(mine)
        tag = "plate_%s" % ("me" if mine else "foe")
        hp_box(cv, x, y, x + w, y + h, tags=(tag,))
        left, right = x + s(16), x + w - s(16)
        items = {"x": left, "right": right, "y": y, "h": h, "mine": mine, "tag": tag}
        items["name"] = kit.text(cv, left, y + s(20), "", F(13), fill=INK, anchor="w", tags=(tag,))
        items["gender"] = cv.create_text(left, y + s(20), text="", anchor="w", font=F(13), tags=(tag,))
        items["lv"] = kit.text(cv, right, y + s(20), "", F(12), fill=INK, anchor="e", tags=(tag,))
        items["status_y"] = y + s(40)
        items["ability"] = kit.text(cv, right, y + s(40), "", F(9), fill=DIM, anchor="e", tags=(tag,))
        # 체력: 진회색 홈 (둥근) + 두 빛깔 막대 (체력 빛깔은 그대로)
        bx0, by0 = left, y + s(53)
        bh = s(12)
        hp_groove(cv, bx0, by0, right, by0 + bh, tags=(tag,))
        tx0, tx1 = bx0 + s(3), right - s(3)
        ty0, ty1 = by0 + s(3), by0 + bh - s(3)
        mid = (ty0 + ty1) // 2
        items["bar"] = cv.create_rectangle(tx0, ty0, tx1, mid, fill=HP_COLORS[0][1], outline="", tags=(tag,))
        items["bar2"] = cv.create_rectangle(tx0, mid, tx1, ty1, fill=HP_COLORS[0][2], outline="", tags=(tag,))
        items["bar_geom"] = (tx0, ty0, tx1 - tx0, ty1 - ty0)
        items["hp"] = (kit.text(cv, right, y + s(80), "", F(12), fill=INK, anchor="e", tags=(tag,))
                       if (mine or self.FOE_HP) else None)
        items["balls"] = []
        return items

    def _show_banner(self, who, text):
        """특성 · 메가진화 · Z기술 같은 알림: 이름표 곁의 작은 흰 판 (이름표와 같은 모양)."""
        s = U.h
        cv = self.cv
        f = F(11)
        tw = kit.tkfont_of(cv, f).measure(text) + s(32)
        th = s(34)
        if who == "foe":
            x, y = s(16), s(14) + self._plate_h(False) + s(8)
        else:
            x, y = self.sw - tw - s(16), self.sh - self._plate_h(True) - s(16) - th - s(8)
        tag = "banner%d" % len(self.banner)
        hp_box(cv, x, y, x + tw, y + th, tags=(tag,))
        kit.text(cv, x + tw // 2, y + th // 2, text, f, fill=INK, anchor="center", tags=(tag,))
        self.banner.append(tag)

        def gone():
            try:
                cv.delete(tag)
            except tk.TclError:
                pass
        self.later(1400, gone)

