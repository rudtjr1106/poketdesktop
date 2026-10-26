# -*- coding: utf-8 -*-
"""금·은 테마의 배틀 그림 - 관장 · 실시간 · 레이드 세 창이 같이 쓴다. 시안 G 의 '배틀 (명령 고르기)' 그대로:

    한 화면    DS 의 위아래 두 화면 · 경첩 · 하늘 · 풀밭 · 받침 대신 종이빛(#fffaf0) 한 장 (시안 .g .bt)
    이름표     상자가 아니라 ㄴ자 선(진한 3)으로 받친 글 (.g .fi): 상대는 왼쪽 위 (왼쪽 · 아래 선),
               나는 오른쪽 아래 (오른쪽 · 아래 선, 글은 오른쪽 맞춤).
               이름 / '♂ :L50' / 금빛 'HP' 꼬리표 + 진한 테의 흰 막대 / 체력 숫자
    아래       왼쪽 글상자 + 그 오른쪽 위에 겹친 명령 상자 (둘 다 두 겹 금빛 테 - _gbc.gbox).
               말은 글상자에, 고를 것은 명령 상자에 (시안의 '싸운다 · 포켓몬 · 가방 · 도망친다' 자리)

흐름은 DP 그대로다: 내 차례면 명령 상자에 **바로 기술 넷** (▶ 가 붙는 글자 줄 - 이름 · 타입 꼬리표 · 분류 ·
위력 · 명중 · PP) + 맨 아랫줄 '포켓몬' · '기권' (시안의 '가방' 은 이 앱 배틀에 없어 뺐고, '도망친다' 자리가
'기권'). 메가진화 · Z기술 켜기는 아랫줄 왼쪽의 작은 칩 (시안에 특별 단추가 없어 칩 모양).
교체 → 명령 상자에 파티 줄 여섯 + 취소, 기다림 · 결과도 명령 상자 안에.
재생 중(고를 것이 없을 때)은 명령 상자 없이 글상자가 폭 가득 (게임보이처럼).

체력 · 타입 · 성별 · 상태 빛깔은 그대로 (뜻이 있는 빛깔). 이 창들은 글상자 줄(msg_frame)을 따로 두지 않고
아래 캔버스(bcv) 하나에 글상자와 명령 상자를 함께 그린다 - 창 높이(장면 + 말 + 명령)는 기본 창 그대로.
"""
import tkinter as tk

from ..dp import battle as DB
from ..dp import kit
from ..dp.battle import CAT_COLOR, CAT_KR, F, GENDER, HP_COLORS, MOVE_Z, STATUS, U, Z, ball, hp_colors
from . import AMBER, BROWN, DIM, INK, INK2, PAPER, SEL, SEP
from ._gbc import arrow, gbox

LINE_W = 3                 # 이름표 ㄴ자 선 (시안 3)
BAR_BG = "#ffffff"          # 체력 막대 속 (시안 .hpl i 의 흰 바탕)


def bk():
    """테 두께 배율 (배틀 창은 창 크기 배율을 탄다)."""
    return max(0.6, U.h(100) / 100.0)


def hp_bar(cv, x1, y1, x2, y2, tags=()):
    """시안의 체력 줄 (.g .hpl): 금빛 'HP' 꼬리표 + 진한 테 2 의 흰 막대. (막대 속 x0, y0, 폭, 높이)."""
    s = U.h
    tw = s(24)
    cv.create_rectangle(x1, y1, x1 + tw, y2, fill=AMBER, outline="", tags=tags)
    cv.create_text(x1 + tw // 2, (y1 + y2) // 2, text="HP", fill=PAPER, font=F(7), anchor="center", tags=tags)
    bx = x1 + tw + s(5)
    lw = max(2, s(2))
    cv.create_rectangle(bx, y1 + 1, x2, y2 - 1, fill=BAR_BG, outline=INK, width=lw, tags=tags)
    i = lw
    return bx + i, y1 + 1 + i, (x2 - i) - (bx + i), (y2 - 1 - i) - (y1 + 1 + i)


# ---------------------------------------------------------------- 명령 상자의 단추 (글자 메뉴)
class GBTouch(DB.Touch):
    """시안의 명령 글자 (.g .ln): 올리면 빨간 ▶ + 옅은 금빛 줄. primary 면 ▶ 가 늘 붙는다 (결과의 '돌아가기')."""

    primary = False

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
        cv, s, t = self.cv, U.h, (self.tag,)
        on = self.enabled
        hot = self._hover and on
        cv.create_rectangle(x1, y1, x2, y2, fill=SEL if hot else PAPER, outline="", tags=t)
        ym = (y1 + y2) // 2
        if on and (hot or self.primary):
            arrow(cv, x1 + s(6), ym, s(6), tags=t)
        cv.create_text(x1 + s(24), ym, text=self.text, fill=INK if on else DIM, font=self.spec, anchor="w", tags=t)


class GBMoveRow(GBTouch, DB.MoveTouch):
    """기술 한 줄: ▶ · 이름 · 타입 꼬리표(타입 빛깔) · 분류 · 위력 · 명중 / PP. 폭이 모자라면 두 줄
    (이름 / 나머지). 마우스를 올리면 설명이 글상자에 뜬다 (DP 와 같다 - MoveTouch.on_hover)."""

    name_w = 0

    def paint(self, x1, y1, x2, y2):
        cv, s, t, m = self.cv, U.h, (self.tag,), self.move
        on = self.enabled
        hot = self._hover and on
        fill = SEL if hot else (MOVE_Z if (m.get("z") and on) else PAPER)
        cv.create_rectangle(x1, y1, x2, y2, fill=fill, outline="", tags=t)
        if hot:
            arrow(cv, x1 + s(6), (y1 + y2) // 2, s(6), tags=t)
        ink = INK if on else DIM
        f14, f10, f9 = kit.tkfont_of(cv, F(14)), kit.tkfont_of(cv, F(10)), kit.tkfont_of(cv, F(9))
        tname = m.get("typeKr") or ""
        cat = CAT_KR.get(m.get("cat") or "status", "")
        bits = []
        if m.get("power"):
            bits.append("위력 %d" % m["power"])
        bits.append(("명중 %d" % m["acc"]) if m.get("acc") else "명중 —")
        rest = ("· " if cat else "") + " · ".join(bits)
        pp, mx = m.get("pp") or 0, m.get("maxpp") or 0
        ptext = "PP %d/%d" % (pp, mx)
        nx = x1 + s(24)
        name_w = max(self.name_w, f14.measure(self.text))
        tw = (f9.measure(tname) + s(12)) if tname else 0
        need = name_w + s(14) + tw + s(8) + f10.measure(cat + " ") + f10.measure(rest) + s(16) + f10.measure(ptext)
        one = nx + need <= x2 - s(12)
        if one:
            ym = (y1 + y2) // 2
            cv.create_text(nx, ym, text=self.text, fill=ink, font=F(14), anchor="w", tags=t)
            tx, by = nx + name_w + s(14), ym
        else:
            hh = y2 - y1
            cv.create_text(nx, y1 + int(hh * 0.30), text=self.text, fill=ink, font=F(14), anchor="w", tags=t)
            tx, by = nx, y1 + int(hh * 0.74)
        if tname:
            col = U.TYPE_COLOR.get(m.get("type"), "#a8a878")
            tcol = col if on else "#d8d0bc"
            th = f9.metrics("linespace") + s(2)
            cv.create_rectangle(tx, by - th // 2, tx + tw, by + th // 2, fill=tcol, outline="", tags=t)
            cv.create_text(tx + tw // 2, by, text=tname, fill=kit.look_of(tcol)[3], font=F(9), anchor="center",
                           tags=t)
            tx += tw + s(8)
        if cat:
            cv.create_text(tx, by, text=cat, fill=CAT_COLOR.get(m.get("cat") or "status", INK2) if on else DIM,
                           font=F(10), anchor="w", tags=t)
            tx += f10.measure(cat + " ")
        cv.create_text(tx, by, text=rest, fill=INK2 if on else DIM, font=F(10), anchor="w", tags=t)
        pcol = "#d02828" if pp <= 0 else ("#c06810" if mx and pp * 4 <= mx else ink)
        cv.create_text(x2 - s(12), by, text=ptext, fill=pcol, font=F(10), anchor="e", tags=t)


class GBPill(DB.Pill):
    """메가진화 · Z기술 켜기 (ui_mega · ui_gimmick 이 fill · _fg · hover 를 바꿔 쓴다): 진한 테 2 의 네모 칩.
    켜면 그 기믹의 빛깔로 채운다 (꺼짐 = 종이빛)."""

    def draw(self):
        cv = self.holder
        try:
            cv.delete("all")
        except tk.TclError:
            return
        w, h, s = int(cv["width"]), self.h, U.h
        body = self.hover if self._in else self.fill
        y1, y2 = s(5), h - s(5)
        cv.create_rectangle(2, y1, w - 2, y2, fill=body, outline=INK, width=2)
        ink = self._fg
        if ink.lower() in ("#ffffff", "#fff", PAPER):
            ink = kit.look_of(self.fill)[3]
        cv.create_text(w // 2, (y1 + y2) // 2, text=self.text, fill=ink, font=F(12), anchor="center")


# ---------------------------------------------------------------- 아래 (세 창)
class GBLower(object):
    """글상자 + 명령 상자 (창 클래스에서 DP 창 클래스 **앞에** 섞는다)."""

    CMD_SHARE = 0.60            # 명령 상자 폭 (아래 칸 폭에 대한 몫)

    # ---------------- 틀
    def _message(self):
        """글상자 줄은 따로 두지 않는다 (아래 캔버스에 함께 그린다). 틀만 만들어 둔다 - 끼우지 않는다."""
        self.msg_frame = tk.Frame(self.win, height=1, bg=PAPER)
        self.mcv = None
        self._peeking = None
        self._msg_rect = None

    def _commands(self):
        super(GBLower, self)._commands()
        self.mcv = self.bcv                       # 말은 아래 캔버스의 'msg' 꼬리표 (검사 · 다른 코드가 읽는다)
        try:
            self.cmd.configure(bg=PAPER)
            self.bcv.configure(bg=PAPER, height=U.h(self.ZOOM_MSG) + U.h(self.ZOOM_CMD))
            self.tbar.configure(bg=PAPER)
        except tk.TclError:
            pass
        for b in self._touch:
            b.__class__ = GBTouch
            b.primary = b is self.done_btn
        self._draw_lower()

    def _pill(self, parent, text, command, height=34, **_kw):
        return GBPill(parent, text, command, height=height, bg=PAPER)

    # ---------------- 자리
    def _layout(self, w, h):
        """(글상자 x1, y1, x2, y2, 글 오른쪽 끝, 명령 상자 또는 None)."""
        s = U.h
        x1, x2 = s(8), w - s(8)
        y1, y2 = s(30), h - s(8)
        if self._page in ("moves", "switch", "wait", "result"):
            cw = int((x2 - x1) * (0.66 if self._page == "result" else self.CMD_SHARE))
            cw = min(cw, (x2 - x1) - s(200))
            cmd = (x2 - cw, y1, x2, y2)
            return x1, y1, x2, y2, x2 - cw - s(10), cmd
        return x1, y1, x2, y2, x2 - s(20), None

    # ---------------- 글상자
    def _draw_message(self):
        cv = getattr(self, "bcv", None)
        rect = getattr(self, "_msg_rect", None)
        if cv is None or rect is None:
            return
        try:
            cv.delete("msg")
        except tk.TclError:
            return
        s = U.h
        x1, y1, x2, y2, tr = rect
        ix1, iy1, _ix2, _iy2 = gbox(cv, x1, y1, x2, y2, tags=("msg",), k=bk())
        text = self._peeking if self._peeking else getattr(self, "_said", "")
        try:
            from common.korean import natural
            text = natural(text or "")
        except Exception:                                   # noqa: BLE001
            text = text or ""
        kit.text(cv, ix1 + s(14), iy1 + s(10), text, F(self.MSG_PT + 1), anchor="nw",
                 width=max(s(80), tr - ix1 - s(24)), tags=("msg",))
        try:
            cv.tag_raise("msg", "bg")                     # 명령 상자 밑으로 (시안: 명령 상자가 글상자 위에 겹친다)
        except tk.TclError:
            pass

    # ---------------- 아래 칸
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
        for b in self._touch:
            b.box = None
            b._hover = b._down = False
        self._move_btns = []
        self._plate_hits = []
        self.lower.reset()
        cv.create_rectangle(0, 0, w, h, fill=PAPER, outline="", tags=("bg",))
        self._draw_strip()
        x1, y1, x2, y2, tr, cmd = self._layout(w, h)
        self._msg_rect = (x1, y1, x2, y2, tr)
        self._draw_message()
        if cmd is None:
            return
        ix1, iy1, ix2, iy2 = gbox(cv, *cmd, tags=("cmdbox",), k=bk())
        box = (ix1 + U.h(2), iy1 + U.h(2), ix2 - U.h(2), iy2 - U.h(2))
        page = self._page
        if page == "moves":
            self._draw_moves(box)
        elif page == "switch":
            self._draw_switch(box)
        elif page == "result":
            self._draw_result(box)
        elif page == "wait":
            self._draw_wait(box)

    def _draw_strip(self):
        """맨 윗줄: 양쪽 파티의 볼 (왼쪽 나 · 오른쪽 상대) · 가운데 턴 · 남은 시간."""
        cv = getattr(self, "bcv", None)
        if cv is None:
            return
        try:
            w, _h = self._lower_wh()
            cv.delete("strip")
        except tk.TclError:
            return
        s = U.h
        y, sh = s(5), s(22)
        t = ("strip",)
        cv.create_rectangle(0, 0, w, y + sh + s(2), fill=PAPER, outline="", tags=t)
        d, gap = s(14), s(3)
        me, foe = getattr(self, "_teams", ([], []))
        by = y + (sh - d) / 2.0
        for i in range(6):
            x = s(12) + i * (d + gap)
            ball(cv, x, by, d, self._ball_state(me, i), tags=t)
            if foe is not None:
                x = w - s(12) - d - i * (d + gap)
                ball(cv, x, by, d, self._ball_state(foe, i), tags=t)
        text = getattr(self, "_turn_text", "")
        timer, danger = getattr(self, "_timer", ("", False))
        tcol = DIM if danger is None else ("#d02828" if danger else "#c06810")
        f = F(10)
        tw = kit.tkfont_of(cv, f).measure(text) if text else 0
        mw = kit.tkfont_of(cv, F(11)).measure(timer) if timer else 0
        g2 = s(14) if text and timer else 0
        x = w // 2 - (tw + g2 + mw) // 2
        if text:
            kit.text(cv, x, y + sh // 2, text, f, fill=INK2, anchor="w", tags=t)
        if timer:
            kit.text(cv, x + tw + g2, y + sh // 2, timer, F(11), fill=tcol, anchor="w", tags=t)

    def _bottom_row(self, box, buttons, bh):
        """명령 상자 맨 아랫줄의 글자 단추 (오른쪽부터). 왼쪽 끝 x."""
        cv, s = self.bcv, U.h
        ix1, _iy1, ix2, iy2 = box
        y2 = iy2 - s(2)
        y1 = y2 - bh
        x2 = ix2 - s(4)
        for b in buttons:
            bw = kit.tkfont_of(cv, b.spec).measure(b.text) + s(40)
            b.layout(x2 - bw, y1, x2, y2)
            x2 -= bw + s(6)
        return x2

    def _draw_moves(self, box):
        """기술 넷 (글자 줄) + 맨 아랫줄 (메가진화 · Z기술 칩) · '포켓몬' · '기권'."""
        cv, s = self.bcv, U.h
        ix1, iy1, ix2, iy2 = box
        moves = getattr(self, "_moves", [])[:4]
        bh = s(34)
        rows = [GBMoveRow(cv, m, (lambda k=m.get("key"): self.use_move(k)), self._peek, tag="mv%d" % i)
                for i, m in enumerate(moves)]
        f14 = kit.tkfont_of(cv, F(14))
        name_w = max([f14.measure(r.text) for r in rows] or [0])
        top, bot = iy1, iy2 - bh - s(6)
        rh = (bot - top) // 4 if rows else 0
        for i, r in enumerate(rows):
            r.name_w = name_w
            r.layout(ix1, top + i * rh, ix2, top + (i + 1) * rh)
            self._move_btns.append(r)
        cv.create_line(ix1 + s(6), bot + s(3), ix2 - s(6), bot + s(3), fill=SEP, width=2)
        self._bottom_row(box, [self.forfeit_btn, self.switch_btn], bh)
        ym = iy2 - s(2) - bh // 2
        cv.create_window(ix1 + s(4), ym, window=self.tbar, anchor="w")
        self.tbar.update_idletasks()

    def _draw_switch(self, box):
        """파티 줄 여섯 (두 줄로 셋씩) + 취소."""
        cv, s = self.bcv, U.h
        ix1, iy1, ix2, iy2 = box
        side, forced = getattr(self, "_switch", ({"team": [], "slot": 0}, True))
        team = side.get("team") or []
        bh = 0 if forced else s(32)
        cols, rows = 2, 3
        gap = s(4)
        bot = iy2 - (bh + s(4) if bh else 0)
        pw = (ix2 - ix1 - gap) // cols
        ph = (bot - iy1 - gap * (rows - 1)) // rows
        for i, m in enumerate(team[:6]):
            x1 = ix1 + (i % cols) * (pw + gap)
            y1 = iy1 + (i // cols) * (ph + gap)
            pbox = (x1, y1, x1 + pw, y1 + ph)
            active = i == side.get("slot")
            self._plate_hits.append(DB.PlateHit(self, i, m, pbox, active, self._plate_ok(i, m)))
            self._draw_plate(i, m, pbox, active, False)
        if not forced:
            self._bottom_row(box, [self.cancel_btn], bh)

    def _draw_plate(self, i, m, box, active, hover):
        """파티 한 칸: ▶(올렸을 때) · 도트 · 이름 · Lv / 'HP' 막대 / 상태 · 체력 숫자. 싸우는 중은 갈색 글,
        쓰러진 것은 흐리게."""
        cv, s = self.bcv, U.h
        tag = "pl%d" % i
        cv.delete(tag)
        x1, y1, x2, y2 = box
        ok = self._plate_ok(i, m)
        hot = hover and ok
        cv.create_rectangle(x1, y1, x2, y2, fill=SEL if hot else PAPER, outline=SEP if not active else BROWN,
                            width=2 if active else 1, tags=(tag,))
        mid = (y1 + y2) // 2
        if hot:
            arrow(cv, x1 + s(4), mid, s(5), tags=(tag,))
        isz = Z.px(32)
        ix = x1 + s(16)
        img = cv.create_image(ix + isz // 2, mid, anchor="center", tags=(tag,))
        self._plate_thumb(img, m)
        tx = ix + isz + s(6)
        ink = INK if ok or active else DIM
        ph = y2 - y1
        ny = y1 + max(s(3), int(ph * 0.08))
        cv.create_text(tx, ny, text=m.get("name") or "", fill=ink, font=F(12), anchor="nw", tags=(tag,))
        cv.create_text(x2 - s(8), ny, text=":L%d" % (m.get("level") or 0), fill=ink, font=F(10), anchor="ne",
                       tags=(tag,))
        by = y1 + int(ph * 0.52)
        bx1 = x2 - s(8)
        gx, gy, gw, gh = hp_bar(cv, tx, by - s(5), bx1, by + s(5), tags=(tag,))
        frac = (m.get("hp") or 0) / float(m.get("maxhp") or 1)
        if frac > 0:
            a, b = hp_colors(frac)
            xe = gx + int(gw * max(0.0, min(1.0, frac)))
            cv.create_rectangle(gx, gy, xe, gy + gh // 2, fill=a, outline="", tags=(tag,))
            cv.create_rectangle(gx, gy + gh // 2, xe, gy + gh, fill=b, outline="", tags=(tag,))
        sub = "쓰러짐" if m.get("fainted") else ("싸우는 중" if active else (m.get("statusKr") or ""))
        ly = y2 - max(s(3), int(ph * 0.06))
        if sub:
            cv.create_text(tx, ly, text=sub, fill="#d02828" if m.get("fainted") else (BROWN if active else ink),
                           font=F(9), anchor="sw", tags=(tag,))
        cv.create_text(bx1, ly, text="%d/%d" % (m.get("hp") or 0, m.get("maxhp") or 0), fill=ink, font=F(9),
                       anchor="se", tags=(tag,))

    def _draw_wait(self, box):
        cv, s = self.bcv, U.h
        ix1, iy1, ix2, iy2 = box
        title, note, quiet = getattr(self, "_wait", ("", None, False))
        bh = s(34)
        width = ix2 - ix1 - s(32)
        th = kit.text_height(cv, title, F(15), width)
        nh = kit.text_height(cv, note, F(11), width) + s(8) if note else 0
        ty = (iy1 + iy2 - bh) // 2 - (th + nh) // 2
        kit.text(cv, (ix1 + ix2) // 2, ty, title, F(15), fill=DIM if quiet else "#a05a10", anchor="n", width=width,
                 justify="center")
        if note:
            kit.text(cv, (ix1 + ix2) // 2, ty + th + s(8), note, F(11), fill=INK2, anchor="n", width=width,
                     justify="center")
        self._bottom_row(box, [self.forfeit_btn], bh)

    def _draw_result(self, box):
        cv, s = self.bcv, U.h
        ix1, iy1, ix2, iy2 = box
        res, title, lines = getattr(self, "_result", ("", "", []))
        bh = s(34)
        self._bottom_row(box, [self.done_btn], bh)
        res = {"win": "won", "lose": "lost"}.get(res, res)
        col = {"won": "#a05a10", "lost": "#c02828", "timeout": "#c02828"}.get(res, INK)
        kit.text(cv, ix1 + s(14), iy1 + s(8), title, F(20), fill=col, anchor="nw")
        ty = iy1 + s(8) + kit.tkfont_of(cv, F(20)).metrics("linespace") + s(6)
        width = ix2 - ix1 - s(28)
        for ln in lines:
            if ty > iy2 - bh - s(4):
                break
            _a, b = kit.text(cv, ix1 + s(14), ty, ln, F(11), anchor="nw", width=width)
            bb = cv.bbox(b)
            ty = (bb[3] if bb else ty + s(18)) + s(3)


# ---------------------------------------------------------------- 1 대 1 장면 (관장 · 실시간)
class GBDuel(GBLower):
    """종이빛 한 장의 장면 + ㄴ자 이름표 (시안 .g .fi)."""

    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = getattr(self, "cv", None)
        if cv is None:
            cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg=PAPER, highlightthickness=0)
            cv.pack(fill="x")
            self.cv = cv
        else:
            cv.delete("all")
            cv.configure(width=self.sw, height=self.sh, bg=PAPER)
        try:
            self.win.configure(bg=INK, highlightbackground=INK)
        except tk.TclError:
            pass
        sw, sh = self.sw, self.sh
        cv.create_rectangle(0, 0, sw, sh, fill=PAPER, outline="")
        self.foe_pos = (int(sw * 0.70), int(sh * 0.50))
        self.me_pos = (int(sw * 0.28), int(sh * 0.93))
        fx, fy = self.foe_pos
        mx, my = self.me_pos
        self.trainer_item = cv.create_image(sw - s(70), fy + s(6), anchor="s")
        self.sprite = {"foe": cv.create_image(fx, fy + s(8), anchor="s"),
                       "me": cv.create_image(mx, my + s(10), anchor="s")}
        bw = s(330)
        self.box = {"foe": self._namebox(s(16), s(12), False),
                    "me": self._namebox(sw - bw - s(16), sh - self._plate_h(True) - s(12), True)}
        self.banner = []
        self._paint_watchers()

    def _namebox(self, x, y, mine):
        """ㄴ자 선 (상대: 왼쪽 · 아래, 나: 오른쪽 · 아래) + 글. 글자 · 막대 항목은 DP 와 같은 이름."""
        s = U.h
        cv = self.cv
        w, h = s(330), self._plate_h(mine)
        tag = "plate_%s" % ("me" if mine else "foe")
        lw = max(2, s(LINE_W))
        cv.create_rectangle(x, y + h - lw, x + w, y + h, fill=INK, outline="", tags=(tag,))
        if mine:
            cv.create_rectangle(x + w - lw, y + s(4), x + w, y + h, fill=INK, outline="", tags=(tag,))
            left, right = x + s(4), x + w - lw - s(12)
        else:
            cv.create_rectangle(x, y + s(4), x + lw, y + h, fill=INK, outline="", tags=(tag,))
            left, right = x + lw + s(12), x + w - s(4)
        items = {"x": left, "right": right, "y": y, "h": h, "mine": mine, "tag": tag}
        items["name"] = kit.text(cv, right if mine else left, y + s(16), "", F(13), anchor="e" if mine else "w",
                                 tags=(tag,))
        items["ability"] = kit.text(cv, left if mine else right, y + s(16), "", F(9), fill=INK2,
                                    anchor="w" if mine else "e", tags=(tag,))
        ry = y + s(38)
        items["row2"] = ry
        items["lv"] = kit.text(cv, (right - s(8)) if mine else (left + s(30)), ry, "", F(12),
                               anchor="e" if mine else "w", tags=(tag,))
        items["gender"] = cv.create_text(left, ry, text="", anchor="w", font=F(12), tags=(tag,))
        items["status_y"] = ry
        hy = y + s(60)
        gx, gy, gw, gh = hp_bar(cv, left, hy - s(7), right, hy + s(7), tags=(tag,))
        mid = gy + gh // 2
        items["bar"] = cv.create_rectangle(gx, gy, gx + gw, mid, fill=HP_COLORS[0][1], outline="", tags=(tag,))
        items["bar2"] = cv.create_rectangle(gx, mid, gx + gw, gy + gh, fill=HP_COLORS[0][2], outline="", tags=(tag,))
        items["bar_geom"] = (gx, gy, gw, gh)
        items["hp"] = (kit.text(cv, right, y + s(82), "", F(12), anchor="e", tags=(tag,))
                       if (mine or self.FOE_HP) else None)
        items["balls"] = []
        return items

    def _paint_box(self, who, hp=None):
        items = self.box[who]
        mon = self.shown.get(who)
        cv = self.cv
        cv.delete("st_" + who)
        if not mon:
            for k in ("name", "lv", "ability", "hp"):
                if items.get(k):
                    for i in items[k]:
                        if i:
                            cv.itemconfigure(i, text="")
            cv.itemconfigure(items["gender"], text="")
            return
        s = U.h
        mine = items["mine"]
        for i in items["name"]:
            if i:
                cv.itemconfigure(i, text=mon.get("name") or "")
        for i in items["ability"]:
            if i:
                cv.itemconfigure(i, text=self._plate_note(who, mon))
        # 둘째 줄: '♂ :L50' (상대는 왼쪽에서 들여, 나는 오른쪽 맞춤) + 상태 꼬리표 · 능력 변화
        lv = ":L%d" % (mon.get("level") or 0)
        for i in items["lv"]:
            if i:
                cv.itemconfigure(i, text=lv)
        g = GENDER.get(mon.get("gender"))
        f12 = kit.tkfont_of(cv, F(12))
        ry = items["row2"]
        if mine:
            lx2 = items["right"] - s(8) - f12.measure(lv)
            gx = lx2 - s(4) - (f12.measure(g[0]) if g else 0)
            sx = items["x"]
        else:
            gx = items["x"] + s(14)
            sx = items["x"] + s(30) + f12.measure(lv) + s(12)
        cv.coords(items["gender"], gx, ry)
        cv.itemconfigure(items["gender"], text=g[0] if g else "", fill=g[1] if g else INK)
        st = mon.get("statusKr") or ""
        f = F(9)
        tg = ("st_" + who, items["tag"])
        x = sx
        if st:
            col = STATUS.get(st, "#808080")
            tw = kit.tkfont_of(cv, f).measure(st) + s(12)
            th = kit.tkfont_of(cv, f).metrics("linespace") + s(2)
            cv.create_rectangle(x, ry - th // 2, x + tw, ry + th // 2, fill=col, outline="", tags=tg)
            cv.create_text(x + tw // 2, ry, text=st, fill=kit.look_of(col)[3], font=f, anchor="center", tags=tg)
            x += tw + s(6)
        kr = {"atk": "공", "def": "방", "spa": "특공", "spd": "특방", "spe": "스피드", "acc": "명중", "eva": "회피"}
        bits = ["%s%+d" % (kr.get(k, k), v) for k, v in (mon.get("stages") or {}).items()]
        if bits:
            kit.text(cv, x, ry, "  ".join(bits), f, fill="#2860c0", anchor="w", tags=tg)
        self._bar(who, mon.get("hp") if hp is None else hp, mon.get("maxhp") or 1)

    def _show_banner(self, who, text):
        """특성 · 메가진화 · Z기술 알림: 이름표 곁의 작은 두 겹 테 상자."""
        s = U.h
        cv = self.cv
        f = F(11)
        tw = kit.tkfont_of(cv, f).measure(text) + s(40)
        th = s(36)
        if who == "foe":
            x, y = s(16), s(12) + self._plate_h(False) + s(10)
        else:
            x, y = self.sw - tw - s(16), self.sh - self._plate_h(True) - s(12) - th - s(10)
        tag = "banner%d" % len(self.banner)
        ix1, iy1, ix2, iy2 = gbox(cv, x, y, x + tw, y + th, tags=(tag,), k=bk())
        kit.text(cv, (ix1 + ix2) // 2, (iy1 + iy2) // 2, text, f, anchor="center", tags=(tag,))
        self.banner.append(tag)

        def gone():
            try:
                cv.delete(tag)
            except tk.TclError:
                pass
        self.later(1400, gone)

