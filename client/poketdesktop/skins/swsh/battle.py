# -*- coding: utf-8 -*-
"""소드·실드 배틀 화면 - 시안 K 의 배틀 그림 (관장 · 실시간 · 레이드 세 창이 같이 쓴다).

DP 의 위 화면 · 글상자 · 아래 화면 세 캔버스를 그대로 두고, 셋을 한 장의 시안 바탕처럼 칠한다:

    바탕       빗금 없는 차분한 남색 (2026-10-26 사용자: "배경이 눈아프다" - 시안의 빗금 · 큰 모서리는 뺐다).
               위 화면 왼쪽 위 · 아래 화면 오른쪽 아래에 작은 하늘색 · 분홍 모서리 (남색에 섞은 빛깔). 받침 대신 옅은 그림자.
    이름표     .hpk - 남색 판 · 흰 테 2 (r 12), 흰 굵은 이름 · 옅은 Lv, 체력 막대는 남빛 홈 (체력 빛깔은 그대로).
    글상자     남색 판 · 흰 테 (빗금 위의 단색 판 - 글은 판 위에만).
    기술       .mvs - 오른쪽 세로 넷: 왼쪽 타입 빛깔 칸(타입 이름) + 흰 막대(이름 · 분류 · 위력 · 명중, PP)
               남색 테 2, 올리면 분홍 테 3 + 왼쪽으로 조금 나온다 (시안의 고른 기술). 설명은 글상자에 잠깐.
    왼쪽       위: 남색 판에 양쪽 파티의 볼 · 턴 · 남은 시간 /
               아래 왼쪽: 분홍 원 (.dmax 다이맥스 자리) = 메가진화 · Z기술 켜기 / 오른쪽: [포켓몬] [기권] 알약.
    교체       흰 둥근 판 여섯 (싸우는 중은 하늘 테, 올리면 분홍 테) + 아래 줄에 볼 · 턴 · [취소]
    기다림 · 결과   흰 판 (.pn) + 단추 하나

흐름은 DP 와 같다 - 내 차례면 기술이 바로 나오고 [포켓몬] [기권] 이 같은 화면에 있다 ('싸운다' · '가방' 단계 없음,
시안의 '도망치기' 자리는 '기권'). 무엇을 보여 줄지는 창의 동작 코드가 정해서 DP 와 같은 _paint_* 로 넘긴다.
"""
import tkinter as tk

from ..dp import DIM, WHITE, kit
from ..dp import battle as DB
from ..dp.battle import CAT_COLOR, CAT_KR, F, GENDER, HP_COLORS, MOVE_OFF, U, Z, ball, hp_colors
from ..dp.battle import mix
from . import CYAN, CYAN_L, DESC, DIMK, MAG, MAG_HI, NAVY, NAVY2, ON_NAVY_DIM
from . import _sw as S

TRACK = "#3a3f70"             # 이름표 체력 막대 홈 (.hpk .b)
SHADOW = "#171a35"            # 포켓몬 발밑 그림자 (받침 대신 - 옅게)
Z_RING = "#f0c040"            # Z기술 테 (금빛)
GLOW = "#f27db5"              # 분홍 원의 번짐
CORNER_LEG = 72               # 배틀 창 모서리 (위 화면 왼쪽 위 하늘 · 아래 화면 오른쪽 아래 분홍) 다리 길이 - 작게


def ring(cv, x1, y1, x2, y2, r, color=MAG, tags=()):
    """올린 것을 둘러싸는 테 (DP 의 빨간 꺾쇠 자리)."""
    g = U.h(3)
    kit.rrect(cv, x1 - g, y1 - g, x2 + g, y2 + g, r + g, fill="", outline=color, width=max(2, U.h(3)), tags=tags)


def navy_plate(cv, x1, y1, x2, y2, r=None, line="#ffffff", tags=()):
    """.hpk - 남색 판 · 흰 테 2."""
    r = U.h(12) if r is None else r
    kit.rrect(cv, x1, y1, x2, y2, r, fill=line, tags=tags)
    g = max(2, U.h(2))
    return kit.rrect(cv, x1 + g, y1 + g, x2 - g, y2 - g, max(2, r - g), fill=NAVY, tags=tags)


# ---------------------------------------------------------------- 아래 화면 단추
LOOK = {
    # (바깥 테, 흰 테?, 몸, 글자)
    "mon": (NAVY, True, "#ffffff", NAVY),      # 포켓몬 - 흰 알약
    "run": ("#ffffff", False, NAVY2, "#ffffff"),  # 기권 · 취소 · 물러나기 - 남색 알약 · 흰 테
    "off": (NAVY, False, "#d9dbe8", "#9a9fc0"),
}


class SwTouch(DB.Touch):
    """둥근 알약 단추. 올리면 분홍 테 (DP 의 꺾쇠 자리)."""

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
            ring(cv, x1, y1 + d, x2, y2 + d, (y2 - y1) // 2, tags=(self.tag,))

    def paint(self, x1, y1, x2, y2):
        cv, s, t = self.cv, U.h, (self.tag,)
        kind = "off" if not self.enabled else ("run" if self.kind != "mon" else "mon")
        edge, white, body, ink = LOOK[kind]
        if getattr(self, "go", False) and self.enabled:
            edge, white, body, ink = NAVY, True, MAG, "#ffffff"
        r = (y2 - y1) // 2
        g = max(2, s(3))
        kit.rrect(cv, x1, y1, x2, y2, r, fill=edge, tags=t)
        if white:
            kit.rrect(cv, x1 + g, y1 + g, x2 - g, y2 - g, r - g, fill="#ffffff", tags=t)
            if body != "#ffffff":
                kit.rrect(cv, x1 + 2 * g, y1 + 2 * g, x2 - 2 * g, y2 - 2 * g, r - 2 * g, fill=body, tags=t)
        else:
            kit.rrect(cv, x1 + g, y1 + g, x2 - g, y2 - g, r - g, fill=body, tags=t)
        cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=self.text, fill=ink, font=self.spec, anchor="center",
                       tags=t)


class SwMove(DB.MoveTouch):
    """.mvs div - 왼쪽 타입 빛깔 칸(타입 이름) + 흰 막대(이름 · 분류 · 위력 · 명중, 오른쪽 PP). 남색 테 2."""

    def draw(self):
        cv = self.cv
        try:
            cv.delete(self.tag)
        except tk.TclError:
            return
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        hot = self._hover and self.enabled
        dx = -U.h(10) if hot else 0                       # 고른 기술은 왼쪽으로 조금 나온다 (translateX(-10px))
        d = U.h(1) if self._down else 0
        self.paint(x1 + dx, y1 + d, x2 + dx, y2 + d)
        if hot:
            ring(cv, x1 + dx, y1 + d, x2 + dx, y2 + d, U.h(12), tags=(self.tag,))

    def paint(self, x1, y1, x2, y2):
        cv, s, t, m = self.cv, U.h, (self.tag,), self.move
        on = self.enabled
        col = U.TYPE_COLOR.get(m.get("type"), "#a8a878")
        r = s(12)
        g = max(2, s(2))
        kit.rrect(cv, x1, y1, x2, y2, r, fill=(Z_RING if (on and m.get("z")) else NAVY), tags=t)
        body = "#ffffff" if on else MOVE_OFF
        kit.rrect(cv, x1 + g, y1 + g, x2 - g, y2 - g, r - g, fill=body, tags=t)
        # 왼쪽 타입 칸 (.ty: 폭 58, 막대 높이 가득)
        f9, f10, f13 = F(9), F(10), F(13)
        k9, k10, k13 = kit.tkfont_of(cv, f9), kit.tkfont_of(cv, f10), kit.tkfont_of(cv, f13)
        tname = m.get("typeKr") or ""
        tw = max(s(58), k9.measure(tname) + s(16))
        cell = col if on else "#b4b8cc"
        a1, b1, a2, b2 = x1 + g, y1 + g, x1 + g + tw, y2 - g
        kit.rrect(cv, a1, b1, a2 + r, b2, r - g, fill=cell, tags=t)
        cv.create_rectangle(a2, b1, a2 + r + 1, b2, fill=body, outline="", tags=t)
        cv.create_text((a1 + a2) // 2, (b1 + b2) // 2, text=tname, fill=kit.look_of(cell)[3] if on else "#ffffff",
                       font=f9, anchor="center", tags=t)
        # 이름 (굵게) · 아랫줄 분류 · 위력 · 명중 / 오른쪽 PP
        ink = NAVY if on else DIM
        pp, mx = m.get("pp") or 0, m.get("maxpp") or 0
        pp_s = "%d/%d" % (pp, mx)
        pcol = "#d02828" if pp <= 0 else ("#c06810" if mx and pp * 4 <= mx else DIMK)
        px2 = x2 - s(14)
        pw = k10.measure(pp_s)
        cat = CAT_KR.get(m.get("cat") or "status", "")
        bits = []
        if m.get("power"):
            bits.append("위력 %d" % m["power"])
        bits.append(("명중 %d" % m["acc"]) if m.get("acc") else "명중 —")
        bits_s = " · ".join(bits)
        nx = a2 + s(12)
        room = px2 - pw - s(12) - nx
        two_h = k13.metrics("linespace") + k9.metrics("linespace") + s(2)
        mid = (b1 + b2) // 2
        if (b2 - b1) >= two_h + s(4):
            ya = mid - two_h // 2 + k13.metrics("linespace") // 2
            yb = mid + two_h // 2 - k9.metrics("linespace") // 2
            cv.create_text(nx, ya, text=self.text, fill=ink, font=f13, anchor="w", tags=t)
            x = nx
            if cat:
                cv.create_text(x, yb, text=cat, fill=CAT_COLOR.get(m.get("cat") or "status", DESC) if on else DIM,
                               font=f9, anchor="w", tags=t)
                x += k9.measure(cat + " ")
            cv.create_text(x, yb, text=("· " if cat else "") + bits_s, fill=DESC if on else DIM, font=f9,
                           anchor="w", tags=t)
        else:                                                # 낮은 칸: 한 줄 (이름 · 분류 · 위력)
            cv.create_text(nx, mid, text=self.text, fill=ink, font=f13, anchor="w", tags=t)
            rest = room - k13.measure(self.text) - s(10)
            line = (cat + " · " if cat else "") + bits_s
            if k9.measure(line) <= rest:
                cv.create_text(px2 - pw - s(12), mid, text=line, fill=DESC if on else DIM, font=f9, anchor="e",
                               tags=t)
        cv.create_text(px2, mid, text=pp_s, fill=pcol if on else DIM, font=f10, anchor="e", tags=t)


class Orb(DB.Touch):
    """분홍 원 (.dmax - 시안의 다이맥스 단추) = 메가진화 · Z기술 켜기.

    ui_mega.MegaToggle · ui_gimmick.Toggle 이 단추에 바라는 것(fill · _fg · hover · _shadow · holder ·
    configure)을 갖추고, 그림은 아래 화면 캔버스에 직접 그린다 (holder 는 보이지 않는 1px 틀 - 토글이 pack
    으로 '보인다 · 숨는다' 를 적는 자리일 뿐이다). 켜면 그 토글의 빛깔(메가: 보라 · Z: 금빛)로 차고 바깥 테가 생긴다.
    """

    def __init__(self, win, parent, text, command):
        DB.Touch.__init__(self, win.bcv, text, command, "orb", F(10), tag="orb%d" % id(self))
        self.win = win
        self.fill, self._fg, self.hover, self._shadow = MAG, "#ffffff", MAG_HI, "#a3104f"
        self._off_fill = MAG
        self.holder = tk.Frame(parent, width=1, height=1, bg=NAVY, highlightthickness=0, bd=0)

    def configure(self, text=None, state=None, **_kw):
        if text is not None:
            self.text = str(text)
        if self.box:
            self.draw()

    config = configure

    def draw(self):
        cv = self.cv
        try:
            cv.delete(self.tag)
        except tk.TclError:
            return
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        t = (self.tag,)
        s = U.h
        on = self.fill != self._off_fill
        body = (self.hover if self._hover else self.fill)
        d = s(1) if self._down else 0
        y1, y2 = y1 + d, y2 + d
        g = s(3)
        cv.create_oval(x1 - g, y1 - g, x2 + g, y2 + g, fill="", outline=GLOW if not on else self.fill,
                       width=max(2, s(3)), tags=t)                               # 번짐
        cv.create_oval(x1, y1, x2, y2, fill="#ffffff", outline="", tags=t)        # 흰 테 4
        b = s(4)
        cv.create_oval(x1 + b, y1 + b, x2 - b, y2 - b, fill=body, outline="", tags=t)
        if not on:                       # radial-gradient(circle at 40% 35%, #ff6b9e, #c4124f 70%) 를 겹 원으로
            R = (x2 - x1) / 2.0 - b
            hx, hy = x1 + (x2 - x1) * 0.40, y1 + (y2 - y1) * 0.35
            cx0, cy0 = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            steps = 7
            for k in range(steps):
                f = 1.0 - k / float(steps)                  # 1 -> 바깥, 작아질수록 밝은 쪽으로
                col = mix("#ff6b9e", "#c4124f" if not self._hover else "#e0306e", f)
                rr = R * f
                ox, oy = cx0 + (hx - cx0) * (1 - f), cy0 + (hy - cy0) * (1 - f)
                cv.create_oval(ox - rr, oy - rr, ox + rr, oy + rr, fill=col, outline="", tags=t)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        ink = kit.look_of(body)[3] if on else "#ffffff"
        if on:
            cv.create_text(cx, cy - s(7), text=self.text, fill=ink, font=self.spec, anchor="center", tags=t)
            cv.create_text(cx, cy + s(9), text="켜짐", fill=ink, font=F(9), anchor="center", tags=t)
        else:
            cv.create_text(cx, cy, text=self.text, fill=ink, font=self.spec, anchor="center", tags=t)


class SwLower(object):
    """DP 의 DPLower 자리 (관장 · 실시간 · 레이드 창의 앞에 섞는다)."""

    BTN_H = 44

    def _phase(self, which):
        """빗금이 세 캔버스에 이어지게 - 그 캔버스가 창에서 놓인 높이."""
        sh = getattr(self, "sh", 0) or getattr(self, "scene_h", 0)
        if which == "msg":
            return sh
        return sh + U.h(self.ZOOM_MSG)

    # ---------------- 글상자
    def _message(self):
        super(SwLower, self)._message()
        for w in (self.msg_frame, self.mcv):
            try:
                w.configure(bg=NAVY)
            except tk.TclError:
                pass

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
        S.calm(cv, 0, 0, w, h)
        x1, y1, x2, y2 = s(10), s(4), w - s(10), h - s(5)
        navy_plate(cv, x1, y1, x2, y2, s(12))
        text = self._peeking if self._peeking else getattr(self, "_said", "")
        try:
            from common.korean import natural
            text = natural(text or "")
        except Exception:                                   # noqa: BLE001
            text = text or ""
        kit.text(cv, x1 + s(20), (y1 + y2) // 2, text, F(self.MSG_PT), fill=WHITE, anchor="w",
                 width=x2 - x1 - s(40), tags=("msg",))

    # ---------------- 아래 화면
    def _commands(self):
        super(SwLower, self)._commands()              # (레이드 창은 여기서 leave_btn 도 단다)
        try:
            self.cmd.configure(bg=NAVY)
            self.bcv.configure(bg=NAVY)
        except tk.TclError:
            pass
        for b in self._touch:
            if type(b) is DB.Touch:
                b.__class__ = SwTouch            # (DP 가 만든 단추를 시안 알약으로 - 동작은 같다)
        self.done_btn.go = True                  # 결과 칸의 단추는 분홍 (.go)

    def _pill(self, parent, text, command, height=34, **_kw):
        orb = Orb(self, parent, text, command)
        self._touch.append(orb)
        return orb

    def _orbs(self):
        out = []
        mega, gim = getattr(self, "mega", None), getattr(self, "gim", None)
        if mega is not None and mega.shown:
            out.append(mega.btn)
        if gim is not None and gim.z.shown:
            out.append(gim.z.btn)
        return out

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
        S.calm(cv, 0, 0, w, h)
        S.corner(cv, w, h, s(CORNER_LEG), "br")
        y0 = s(10)
        page = self._page
        self._strip_box = None
        if page in ("moves", "busy"):
            self._strip_box = (s(14), y0, self._col_x(w) - s(20), y0 + s(64), "col")
        if page == "moves":
            self._draw_moves(w, h, y0)
        elif page == "switch":
            self._draw_switch(w, h, y0)
        elif page == "result":
            self._draw_result(w, h, y0)
        elif page == "wait":
            self._draw_wait(w, h, y0)
        self._draw_strip()

    @staticmethod
    def _col_x(w):
        """기술 칸의 왼쪽 끝 (그 왼쪽은 볼 · 턴 판 · 분홍 원 · [포켓몬][기권])."""
        return int(w * 0.44)

    def _draw_strip(self):
        """양쪽 파티의 볼 · 턴 · 남은 시간 - 남색 판 위 (빗금 위에 글을 두지 않는다)."""
        cv = getattr(self, "bcv", None)
        if cv is None:
            return
        try:
            cv.delete("strip")
        except tk.TclError:
            return
        box = getattr(self, "_strip_box", None)
        if not box:
            return
        x1, y1, x2, y2, mode = box
        s, t = U.h, ("strip",)
        navy_plate(cv, x1, y1, x2, y2, s(12), tags=t)
        d, gap = s(14), s(3)
        me, foe = getattr(self, "_teams", ([], []))
        text = getattr(self, "_turn_text", "")
        timer, danger = getattr(self, "_timer", ("", False))
        tcol = ON_NAVY_DIM if danger is None else ("#ff6b6b" if danger else "#ffb44a")
        f9, f10, f11 = F(9), F(10), F(11)
        px1, px2 = x1 + s(14), x2 - s(14)

        def balls(x, y, team):
            for i in range(6):
                ball(cv, x + i * (d + gap), y - d / 2.0, d, self._ball_state(team, i), tags=t)
            return x + 6 * (d + gap)

        if mode == "col":
            lw = max(kit.tkfont_of(cv, f9).measure("나"), kit.tkfont_of(cv, f9).measure("상대")) + s(8)
            y = y1 + s(16)
            cv.create_text(px1, y, text="나", fill=ON_NAVY_DIM, font=f9, anchor="w", tags=t)
            bx = balls(px1 + lw, y, me)
            if foe is not None:
                cv.create_text(bx + s(12), y, text="상대", fill=ON_NAVY_DIM, font=f9, anchor="w", tags=t)
                fx = bx + s(12) + lw
                if fx + 6 * (d + gap) <= px2:
                    balls(fx, y, foe)
                else:
                    y += s(20)
                    balls(px1 + lw, y, foe)
            y = y2 - s(18)
            x = px1
            if text:
                _a, tid = kit.text(cv, x, y, text, f10, fill=WHITE, anchor="w", width=px2 - px1, tags=t)
                b = cv.bbox(tid)
                x = (b[2] if b else x) + s(14)
            if timer:
                kit.text(cv, x, y, timer, f11, fill=tcol, anchor="w", tags=t)
            return
        y = (y1 + y2) // 2
        x = balls(px1, y, me) + s(12)
        if text:
            _a, tid = kit.text(cv, x, y, text, f10, fill=WHITE, anchor="w", tags=t)
            b = cv.bbox(tid)
            x = (b[2] if b else x) + s(14)
        if timer:
            _a, tid = kit.text(cv, x, y, timer, f11, fill=tcol, anchor="w", tags=t)
            b = cv.bbox(tid)
            x = (b[2] if b else x) + s(14)
        if foe is not None and x + 6 * (d + gap) <= px2:
            balls(px2 - 6 * (d + gap), y, foe)

    def _draw_moves(self, w, h, y0):
        cv, s = self.bcv, U.h
        moves = getattr(self, "_moves", [])
        gap = s(8)
        top, bottom = y0, h - s(10)
        ph = (bottom - top - 3 * gap) // 4
        x1, x2 = self._col_x(w) + s(4), w - s(14)
        for i, m in enumerate(moves[:4]):
            y1 = top + i * (ph + gap)
            b = SwMove(cv, m, (lambda k=m.get("key"): self.use_move(k)), self._peek, tag="mv%d" % i)
            b.layout(x1, y1, x2, y1 + ph)
            self._move_btns.append(b)
        # 왼쪽 아래: 분홍 원 (메가진화 · Z기술) / 오른쪽: [포켓몬] 위 · [기권] 아래
        lx1, lx2 = s(14), self._col_x(w) - s(20)
        sy2 = self._strip_box[3]
        f = kit.tkfont_of(cv, self.switch_btn.spec)
        bw = max(f.measure(self.switch_btn.text), f.measure(self.forfeit_btn.text)) + s(48)
        bw = max(bw, s(130))
        area1, area2 = sy2 + s(10), h - s(10)
        bh = min(s(self.BTN_H), (area2 - area1 - gap) // 2)
        self.forfeit_btn.layout(lx2 - bw, area2 - bh, lx2, area2)
        self.switch_btn.layout(lx2 - bw, area2 - 2 * bh - gap, lx2, area2 - bh - gap)
        dia = min(area2 - area1, s(78))
        ox = lx1 + s(6)
        for orb in self._orbs():
            if ox + dia > lx2 - bw - s(10):
                break
            orb.layout(ox, area2 - dia, ox + dia, area2)
            ox += dia + s(14)

    def _bottom_row(self, w, h, btn=None):
        """교체 · 기다림 칸의 아래 줄: 왼쪽에 볼 · 턴 판, 오른쪽에 단추 하나. 줄의 위 y."""
        s = U.h
        bh = s(self.BTN_H)
        ry2 = h - s(10)
        ry1 = ry2 - bh
        x2 = w - s(14)
        if btn is not None:
            f = kit.tkfont_of(self.bcv, btn.spec)
            bw = max(s(180), f.measure(btn.text) + s(64))
            btn.layout(x2 - bw, ry1, x2, ry2)
            x2 -= bw + s(16)
        self._strip_box = (s(14), ry1, x2, ry2, "row")
        return ry1

    def _draw_switch(self, w, h, y0):
        s = U.h
        side, forced = getattr(self, "_switch", ({"team": [], "slot": 0}, True))
        team = side.get("team") or []
        gap = s(10)
        ry1 = self._bottom_row(w, h, None if forced else self.cancel_btn)
        cols, rows = 3, 2
        pw = (w - s(28) - gap * (cols - 1)) // cols
        ph = (ry1 - s(10) - y0 - gap * (rows - 1)) // rows
        for i, m in enumerate(team[:6]):
            x1 = s(14) + (i % cols) * (pw + gap)
            y1 = y0 + (i // cols) * (ph + gap)
            box = (x1, y1, x1 + pw, y1 + ph)
            active = i == side.get("slot")
            self._plate_hits.append(DB.PlateHit(self, i, m, box, active, self._plate_ok(i, m)))
            self._draw_plate(i, m, box, active, False)

    def _draw_plate(self, i, m, box, active, hover):
        """교체 판: 흰 둥근 판 (남색 테 2), 싸우는 중은 하늘 테 · 옅은 하늘, 올리면 분홍 테."""
        cv, s = self.bcv, U.h
        tag = "pl%d" % i
        cv.delete(tag)
        x1, y1, x2, y2 = box
        ok = self._plate_ok(i, m)
        r = s(12)
        if m.get("fainted"):
            fill = "#e2e4ee"
        elif active:
            fill = CYAN_L
        elif hover and ok:
            fill = "#fdeef5"
        else:
            fill = "#ffffff"
        kit.rrect(cv, x1, y1, x2, y2, r, fill=CYAN if active else NAVY, tags=(tag,))
        g = max(2, s(3)) if active else max(2, s(2))
        kit.rrect(cv, x1 + g, y1 + g, x2 - g, y2 - g, r - g, fill=fill, tags=(tag,))
        mid = (y1 + y2) // 2
        isz = Z.px(32)
        ix = x1 + s(10)
        img = cv.create_image(ix + isz // 2, mid, anchor="center", tags=(tag,))
        self._plate_thumb(img, m)
        tx = ix + isz + s(8)
        ink = NAVY if ok or active else DIM
        ph = y2 - y1
        ny = y1 + max(s(6), int(ph * 0.12))
        cv.create_text(tx, ny, text=m.get("name") or "", fill=ink, font=F(12), anchor="nw", tags=(tag,))
        cv.create_text(x2 - s(12), ny, text="Lv%d" % (m.get("level") or 0), fill=DIMK, font=F(10), anchor="ne",
                       tags=(tag,))
        sub = "쓰러짐" if m.get("fainted") else ("싸우는 중" if active else (m.get("statusKr") or ""))
        bx0, bx1 = tx, x2 - s(12)
        by = y1 + int(ph * 0.56)
        frac = (m.get("hp") or 0) / float(m.get("maxhp") or 1)
        kit.rrect(cv, bx0, by - s(4), bx1, by + s(4), s(4), fill=TRACK, tags=(tag,))
        if frac > 0:
            a, _b = hp_colors(frac)
            xe = bx0 + s(2) + int((bx1 - bx0 - s(4)) * max(0.0, min(1.0, frac)))
            kit.rrect(cv, bx0 + s(2), by - s(2), max(bx0 + s(6), xe), by + s(2), s(2), fill=a, tags=(tag,))
        ly = y2 - max(s(5), int(ph * 0.10))
        if sub:
            cv.create_text(tx, ly, text=sub, fill="#d02828" if m.get("fainted") else ("#0f86b8" if active else ink),
                           font=F(9), anchor="sw", tags=(tag,))
        cv.create_text(bx1, ly, text="%d/%d" % (m.get("hp") or 0, m.get("maxhp") or 0), fill=ink, font=F(9),
                       anchor="se", tags=(tag,))
        if hover and ok:
            ring(cv, x1, y1, x2, y2, r, tags=(tag,))

    def _draw_wait(self, w, h, y0):
        """상대를 기다린다: 흰 판에 한두 줄, 아래 줄에 볼 · 턴 · [기권]."""
        cv, s = self.bcv, U.h
        title, note, quiet = getattr(self, "_wait", ("", None, False))
        ry1 = self._bottom_row(w, h, self.forfeit_btn)
        x1, y1, x2, y2 = s(16), y0 + s(2), w - s(16), ry1 - s(12)
        S.card(cv, x1, y1, x2, y2)
        width = x2 - x1 - s(48)
        th = kit.text_height(cv, title, F(15), width)
        nh = kit.text_height(cv, note, F(11), width) + s(8) if note else 0
        ty = (y1 + y2) // 2 - (th + nh) // 2
        kit.text(cv, (x1 + x2) // 2, ty, title, F(15), fill=DIMK if quiet else NAVY, anchor="n", width=width,
                 justify="center")
        if note:
            kit.text(cv, (x1 + x2) // 2, ty + th + s(8), note, F(11), fill=DESC, anchor="n", width=width,
                     justify="center")

    def _draw_result(self, w, h, y0):
        """결과: 흰 판 (.pn) + 제목 · 줄 + 분홍 단추 하나."""
        cv, s = self.bcv, U.h
        res, title, lines = getattr(self, "_result", ("", "", []))
        x1, y1, x2, y2 = s(16), y0 + s(2), w - s(16), h - s(12)
        S.card(cv, x1, y1, x2, y2)
        bw = max(kit.tkfont_of(cv, self.done_btn.spec).measure(self.done_btn.text) + s(56), s(210))
        self.done_btn.layout(x2 - s(16) - bw, y2 - s(16) - s(48), x2 - s(16), y2 - s(16))
        res = {"win": "won", "lose": "lost"}.get(res, res)      # (실시간 배틀은 win / lose)
        col = {"won": MAG, "lost": "#c02828", "timeout": "#c02828"}.get(res, NAVY)
        kit.text(cv, x1 + s(24), y1 + s(16), title, F(22), fill=col, anchor="nw")
        ty = y1 + s(16) + kit.tkfont_of(cv, F(22)).metrics("linespace") + s(8)
        width = x2 - s(16) - bw - s(16) - (x1 + s(24))
        for ln in lines:
            _a, b = kit.text(cv, x1 + s(24), ty, ln, F(11), fill=DESC, anchor="nw", width=width)
            bb = cv.bbox(b)
            ty = (bb[3] if bb else ty + s(18)) + s(4)


# ---------------------------------------------------------------- 위 화면 (관장 · 실시간)
def scene_bg(cv, sw, sh, full_h):
    """위 화면 바탕: 빗금 없는 남색 + 왼쪽 위 작은 하늘색 모서리 (2026-10-26 사용자: 배경이 눈아프다 -
    도트 · 이름표 · 기술 목록이 바탕보다 먼저 보이게)."""
    S.calm(cv, 0, 0, sw, sh)
    S.corner(cv, 0, 0, U.h(CORNER_LEG), "tl")


def shadow(cv, cx, cy, rx, ry):
    """받침 대신 발밑의 옅은 그림자."""
    cv.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill=SHADOW, outline="")


class SwDuel(SwLower):
    """1 대 1 배틀 창의 위 화면 (DP DPDuel 의 _scene · _namebox · _show_banner 자리)."""

    def _plate_h(self, mine):
        """이름표 높이 (.hpk 처럼 빽빽하게 - 이름 · 특성 줄 · 막대 · 체력 숫자)."""
        s = U.h
        return s(86) if (mine or self.FOE_HP) else s(66)

    def _full_h(self):
        return self.scene_h + U.h(self.ZOOM_MSG) + U.h(self.ZOOM_CMD)

    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = getattr(self, "cv", None)
        if cv is None:
            cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg=NAVY, highlightthickness=0)
            cv.pack(fill="x")
            self.cv = cv
        else:
            cv.delete("all")
            cv.configure(width=self.sw, height=self.sh, bg=NAVY)
        try:
            self.win.configure(bg=NAVY, highlightbackground=NAVY)
        except tk.TclError:
            pass
        sw, sh = self.sw, self.sh
        scene_bg(cv, sw, sh, self._full_h())
        self.foe_pos = (int(sw * 0.70), int(sh * 0.50))
        self.me_pos = (int(sw * 0.28), int(sh * 0.93))
        fx, fy = self.foe_pos
        mx, my = self.me_pos
        shadow(cv, fx, fy, s(84), s(11))
        shadow(cv, mx, my, s(104), s(14))
        self.trainer_item = cv.create_image(sw - s(70), fy + s(6), anchor="s")
        self.sprite = {"foe": cv.create_image(fx, fy + s(8), anchor="s"),
                       "me": cv.create_image(mx, my + s(10), anchor="s")}
        bw = s(330)
        self.box = {"foe": self._namebox(s(16), s(14), False),
                    "me": self._namebox(sw - bw - s(16), sh - self._plate_h(True) - s(12), True)}
        self.banner = []
        self._paint_watchers()

    def _namebox(self, x, y, mine):
        """.hpk - 남색 판 · 흰 테. 흰 이름 · 옅은 Lv · 특성, 체력 막대 (남빛 홈 · 체력 빛깔), 체력 숫자."""
        s = U.h
        cv = self.cv
        w, h = s(330), self._plate_h(mine)
        tag = "plate_%s" % ("me" if mine else "foe")
        navy_plate(cv, x, y, x + w, y + h, s(12), tags=(tag,))
        left, right = x + s(18), x + w - s(18)
        items = {"x": left, "right": right, "y": y, "h": h, "mine": mine, "tag": tag}
        items["name"] = kit.text(cv, left, y + s(19), "", F(13), fill=WHITE, anchor="w", tags=(tag,))
        items["gender"] = cv.create_text(left, y + s(19), text="", anchor="w", font=F(13), tags=(tag,))
        items["lv"] = kit.text(cv, right, y + s(19), "", F(11), fill=ON_NAVY_DIM, anchor="e", tags=(tag,))
        items["status_y"] = y + s(37)
        items["ability"] = kit.text(cv, right, y + s(37), "", F(9), fill=ON_NAVY_DIM, anchor="e", tags=(tag,))
        bx0, by0 = left, y + s(48)
        bh = s(9)
        kit.rrect(cv, bx0, by0, right, by0 + bh, bh // 2, fill=TRACK, tags=(tag,))
        tx0, tx1 = bx0 + s(2), right - s(2)
        ty0, ty1 = by0 + s(2), by0 + bh - s(2)
        mid = (ty0 + ty1) // 2
        items["bar"] = cv.create_rectangle(tx0, ty0, tx1, mid, fill=HP_COLORS[0][1], outline="", tags=(tag,))
        items["bar2"] = cv.create_rectangle(tx0, mid, tx1, ty1, fill=HP_COLORS[0][2], outline="", tags=(tag,))
        items["bar_geom"] = (tx0, ty0, tx1 - tx0, ty1 - ty0)
        items["hp"] = (kit.text(cv, right, y + s(70), "", F(11), fill=WHITE, anchor="e", tags=(tag,))
                       if (mine or self.FOE_HP) else None)
        items["balls"] = []
        return items

    def _paint_box(self, who, hp=None):
        DB.DPDuel._paint_box(self, who, hp)
        # 성별 기호 · 능력 변화 글은 남색 판 위에서 읽히는 빛깔로
        mon = self.shown.get(who)
        g = GENDER.get((mon or {}).get("gender"))
        if g:
            try:
                self.cv.itemconfigure(self.box[who]["gender"], fill={"M": "#7fb4ff", "F": "#ff8fa8"}[mon["gender"]])
            except (tk.TclError, KeyError):
                pass

    def _show_banner(self, who, text):
        """특성 · 메가진화 · Z기술 같은 알림: 이름표 곁의 남색 판 (흰 테)."""
        s = U.h
        cv = self.cv
        f = F(11)
        tw = kit.tkfont_of(cv, f).measure(text) + s(32)
        th = s(34)
        if who == "foe":
            x, y = s(16), s(14) + self._plate_h(False) + s(8)
        else:
            x, y = self.sw - tw - s(16), self.sh - self._plate_h(True) - s(12) - th - s(8)
        tag = "banner%d" % len(self.banner)
        navy_plate(cv, x, y, x + tw, y + th, th // 2, line=MAG, tags=(tag,))
        kit.text(cv, x + tw // 2, y + th // 2, text, f, fill=WHITE, anchor="center", tags=(tag,))
        self.banner.append(tag)

        def gone():
            try:
                cv.delete(tag)
            except tk.TclError:
                pass
        self.later(1400, gone)

