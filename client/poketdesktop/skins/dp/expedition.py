# -*- coding: utf-8 -*-
"""DP 테마의 탐험 - 포켓치.

탐험은 '보내 두고 기다리는 것' 이라 DP 의 포켓치(손목시계)로 그린다.

    위 띠      짙은 회색 몸통에 연두 액정(무늬 없음) '탐험' · 설명, 오른쪽에 '새로고침'
    왼쪽       짙은 회색 몸통에 탐험 칸 셋 = 포켓치 액정 셋. 나가 있는 포켓몬 · 곳 · 시간 · 성공도 · 물건 수,
               남은 시간과 칸 막대(1초마다), '불러들이기'. 돌아오면 '돌아왔습니다!' 와 빨간 '보따리 받기'.
    가운데     ① 어디로 - 흰 판 여섯 (고른 곳은 빨간 커서 · 크림색), 맞는 타입 꼬리표,
               그곳에서 잘 나오는 것(흰 글상자) / ② 얼마나 - 2 · 4 · 8시간 탭과 물건 수
    오른쪽     ③ 누구를 - 흰 목록(고른 줄은 빨간 커서 · 크림색). 이름 · Lv / 타입(그곳과 맞으면 제 빛깔) /
               성공도 · 탐험 레벨. 아래 한 줄에 요약 글과 '성장' · '보내기' (기본 탭과 같은 자리)
    아래 줄    알림 한 줄

규칙과 글(_slots_data · candidates · _summary_data · hours_text · live_of)은 기본 탐험 탭 그대로다.
목록 줄 높이는 기본 탭과 같다 (E.ROW_H) - 한 화면에 보이는 줄 수가 기본보다 줄지 않게.
"""
import tkinter as tk

from PIL import ImageTk

from common import expedition as X
from common import tint as T

from ... import sprite_cache, sprites
from ... import ui_common as U
from ... import ui_expedition as E
from ...ui_common import run_async
from . import CUR, INK, INK2, LINE, PANEL, SEL, WHITE, WIN_BG, font, tone
from . import kit as K

BODY, BODY_HI, BODY_LO = "#3a3f48", "#4a505a", "#23262d"
LCD, LCD_HI, LCD_INK, LCD_DIM = "#a8c890", "#b8d6a0", "#24301c", "#41522f"
GRADE = {"great": "#b05a0a", "good": "#2c8a3c", "normal": INK2}
ORANGE = "#b05a0a"
T_ = ("scene",)


def _lum(color):
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _ink_on(fill):
    return WHITE if _lum(fill) < 0.6 else INK


def _chip(cv, x, ym, name, col, tags, lit=True):
    """타입 꼬리표 (한 겹, 테두리 글씨 없음). 오른쪽 끝 x."""
    s = U.h
    spec = font(8)
    tw = K.tkfont_of(cv, spec).measure(name) + s(12)
    K.rrect(cv, x, ym - s(8), x + tw, ym + s(8), s(4), fill=col, tags=tags)
    cv.create_text(x + tw // 2, ym, text=name, fill=_ink_on(col) if lit else INK2, font=spec, anchor="center",
                   tags=tags)
    return x + tw


class ExpeditionWindow(E.ExpeditionWindow):

    # ---------------- 틀
    def _header(self):
        s = U.h
        self.win.configure(bg=WIN_BG, highlightthickness=0)
        self.hcv = tk.Canvas(self.win, bg=BODY, highlightthickness=0, bd=0, height=s(76))
        self.hcv.pack(fill="x")
        self.hcv.bind("<Configure>", lambda _e: self._paint_head())
        self.reload_btn = K.CButton(self.hcv, "새로고침", self.reload, "gray", font(10))

    def _paint_head(self):
        cv, s = self.hcv, U.h
        try:
            w = cv.winfo_width() if cv.winfo_width() > 1 else s(1020)
            h = cv.winfo_height() if cv.winfo_height() > 1 else s(76)
            cv.delete("head")
        except tk.TclError:
            return
        t = ("head",)
        cv.create_rectangle(0, 0, w, h, fill=BODY, outline="", tags=t)
        # 액정: 제목 · 설명 · 알려 둘 말
        bw = self.reload_btn.want_width(s(28))
        x1, y1, x2, y2 = s(14), s(9), w - s(14) - bw - s(18), h - s(10)
        K.rrect(cv, x1, y1, x2, y2, s(8), fill=LCD, outline=BODY_LO, width=3, tags=t)
        tid = cv.create_text(x1 + s(18), (y1 + y2) // 2 - s(9), text="탐험", fill=LCD_INK, font=font(15), anchor="w",
                             tags=t)
        tx = cv.bbox(tid)[2] + s(14)
        cv.create_text(tx, (y1 + y2) // 2 - s(9), text="박스의 포켓몬을 보내 두면 도구를 가져옵니다", fill=LCD_INK,
                       font=font(9), anchor="w", tags=t)
        cv.create_text(x1 + s(18), (y1 + y2) // 2 + s(12),
                       text="타입이 맞고 레벨이 높을수록 잘 해냅니다 · 꺼 두어도 시간은 흐릅니다 · "
                            "다녀온 포켓몬은 %d시간 쉬고, 탐험 경험치가 쌓입니다" % X.REST_HOURS,
                       fill=LCD_DIM, font=font(8), anchor="w", width=x2 - x1 - s(30), tags=t)
        cv.tag_lower("head")
        bx2 = w - s(14)
        self.reload_btn.layout(bx2 - bw, (h - s(34)) // 2, bx2, (h + s(34)) // 2)

    def _bottom(self):
        s = U.h
        self.stcv = tk.Canvas(self.win, bg=PANEL, highlightthickness=0, bd=0, height=s(36))
        self.stcv.pack(fill="x", side="bottom")
        self.stcv.bind("<Configure>", lambda _e: self._paint_status())
        self._status_msg = ("", None)

    def _paint_status(self):
        cv, s = self.stcv, U.h
        try:
            cv.delete("all")
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.create_rectangle(0, 0, w, h, fill=PANEL, outline="")
        cv.create_line(0, 0, w, 0, fill=LINE)
        tip = "길게, 잘 보낼수록 진화의 돌·병뚜껑 같은 귀한 것이 잘 나온다"
        tw = K.tkfont_of(cv, font(8)).measure(tip)
        cv.create_text(w - s(14), h // 2, text=tip, fill=INK2, font=font(8), anchor="e")
        text, color = self._status_msg
        K.text(cv, s(14), h // 2, text, font(10), fill=tone(color) if color else INK, anchor="w",
               width=max(60, w - tw - s(50)))

    def say(self, msg, color=None):
        from common.korean import natural
        self._status_msg = (natural(msg or ""), None if color in (None, U.FG_FAINT, U.GOOD) else color)
        try:
            self._paint_status()
        except tk.TclError:
            pass

    # ---------------- 몸통 (캔버스 한 장)
    def _slots(self, body):
        s = U.h
        self.cv = tk.Canvas(body, bg=WIN_BG, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda _e: self._soon())
        self._job = None
        self._wins = {}
        self._slot_rows = [(None, False)] * X.SLOTS
        self._slot_note = ""
        self._slot_btns = []
        self.cards = []

    def _send(self, body):
        s = U.h
        cv = self.cv
        self.vl = K.VList(cv, WHITE, self._draw_row)
        self.vl.on_click = lambda data, *_a: self.pick_mon(data[0]["id"])
        self.send_btn = K.CButton(cv, "보내기", self.do_send, "red", font(12))
        self.grow_btn = K.CButton(cv, "성장", self.open_grow, "gray", font(11))
        self._pick_note = ""
        self._empty = None
        self._summary = ("보낼 포켓몬을 고르세요.", U.FG_FAINT)
        self.ROW_H = E.ROW_H
        self._soon()

    def _soon(self):
        if self._job is None and self.alive:
            try:
                self._job = self.cv.after_idle(self._paint)
            except tk.TclError:
                pass

    def _place(self, key, widget, x, y, w, h):
        cv = self.cv
        w, h = max(1, int(w)), max(1, int(h))
        i = self._wins.get(key)
        if i is None:
            self._wins[key] = cv.create_window(x, y, window=widget, anchor="nw", width=w, height=h)
        else:
            cv.coords(i, x, y)
            cv.itemconfigure(i, width=w, height=h, state="normal")

    def _paint(self):
        self._job = None
        cv, s = self.cv, U.h
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
            cv.delete("scene")
        except tk.TclError:
            return
        if w <= 1:
            return
        lw, mw = E.LEFT_W, E.MID_W          # 기본 탭의 폭 그대로 (키우지 않는다)
        self._paint_left(cv, 0, lw, h)
        self._paint_mid(cv, lw, lw + mw, h)
        self._paint_right(cv, lw + mw, w, h)
        cv.tag_lower("scene")

    # ---- 왼쪽: 포켓치 액정 셋
    def _paint_left(self, cv, x1, x2, h):
        s = U.h
        cv.create_rectangle(x1, 0, x2, h, fill=BODY, outline="", tags=T_)
        cv.create_text(x1 + s(16), s(18), text="탐험 칸", fill=WHITE, font=font(11), anchor="w", tags=T_)
        cv.create_text(x2 - s(14), s(18), text=self._slot_note, fill="#d0d4dc", font=font(8), anchor="e", tags=T_)
        for b in self._slot_btns:
            b.dispose()
        self._slot_btns = []
        self.live = []
        gap = s(8)
        top = s(34)
        ch = (h - top - s(10) - gap * (X.SLOTS - 1)) // X.SLOTS
        ch = min(ch, s(120))
        for i, (o, done) in enumerate(self._slot_rows):
            y1 = top + i * (ch + gap)
            self._lcd_card(cv, x1 + s(12), y1, x2 - s(12), y1 + ch, o, done)

    def _lcd_card(self, cv, x1, y1, x2, y2, o, done):
        s = U.h
        # 액정 한 장 (짙은 테 한 겹). 돌아온 칸은 빨간 테.
        K.rrect(cv, x1, y1, x2, y2, s(10), fill=LCD_HI if done else LCD, outline=CUR if done else BODY_LO,
                width=3, tags=T_)
        if o is None:
            cv.create_text((x1 + x2) // 2, (y1 + y2) // 2 - s(8), text="빈 칸", fill=LCD_INK, font=font(12), tags=T_)
            cv.create_text((x1 + x2) // 2, (y1 + y2) // 2 + s(12), text="오른쪽에서 골라 보내세요", fill=LCD_DIM,
                           font=font(8), tags=T_)
            return
        mon = o.get("pokemon") or {}
        ix = x1 + s(12)
        img = cv.create_image(ix + s(21), y1 + s(30), anchor="center", tags=T_)
        self._thumb((cv, img), mon)
        tx = ix + s(48)
        nid = cv.create_text(tx, y1 + s(20), text=("★ " if mon.get("shiny") else "") + (mon.get("name") or "?"),
                             fill=LCD_INK, font=font(11), anchor="w", tags=T_)
        cv.create_text(cv.bbox(nid)[2] + s(6), y1 + s(20), text="Lv.%s" % mon.get("level", "?"), fill=LCD_DIM,
                       font=font(8), anchor="w", tags=T_)
        line = "%s · %s시간 · %s · 물건 %s개" % (o.get("placeKr") or "", o.get("hours"), o.get("gradeKr") or "",
                                            o.get("items", "?"))
        cv.create_text(tx, y1 + s(40), text=line, fill=LCD_INK, font=font(8), anchor="w", width=x2 - tx - s(10),
                       tags=T_)
        fy = y2 - s(22)
        if done:
            b = K.CButton(cv, "보따리 받기", lambda e=o["id"]: self.claim(e), "red", font(9))
            bw = b.want_width(s(22))
            b.layout(x2 - s(10) - bw, fy - s(14), x2 - s(10), fy + s(14))
            self._slot_btns.append(b)
            cv.create_text(x1 + s(14), fy, text="돌아왔습니다!", fill="#a02020", font=font(11), anchor="w", tags=T_)
            return
        b = K.CButton(cv, "불러들이기", lambda e=o: self.recall(e), "gray", font(8))
        bw = b.want_width(s(18))
        b.layout(x2 - s(10) - bw, fy - s(12), x2 - s(10), fy + s(12))
        self._slot_btns.append(b)
        text, frac = self.live_of(o)
        lid = cv.create_text(x1 + s(14), fy, text=text, fill=LCD_INK, font=font(9), anchor="w", tags=T_)
        # 칸 막대
        bx1, bx2 = x1 + s(14), x2 - s(14)
        by = y2 - s(44) + s(4)
        cv.create_rectangle(bx1, by, bx2, by + s(7), fill=LCD_HI, outline=LCD_DIM, tags=T_)
        bar = cv.create_rectangle(bx1 + 1, by + 1, bx1 + 1 + int((bx2 - bx1 - 2) * frac), by + s(7) - 1,
                                  fill=LCD_INK, outline="", tags=T_)
        self.live.append((o, (cv, lid), (cv, bar, bx1 + 1, bx2 - 1)))

    def _paint_live(self, o, label, fill):
        text, frac = self.live_of(o)
        try:
            cv, lid = label
            cv.itemconfigure(lid, text=text)
            cv2, bar, a, b = fill
            c = cv2.coords(bar)
            if c:
                cv2.coords(bar, a, c[1], a + int((b - a) * frac), c[3])
        except tk.TclError:
            pass

    # ---- 가운데: 어디로 · 얼마나
    def _paint_mid(self, cv, x1, x2, h):
        s = U.h
        cv.create_line(x1, 0, x1, h, fill=LINE, width=2, tags=T_)
        lx, rx = x1 + s(14), x2 - s(12)
        K.text(cv, lx, s(18), "\u2460 어디로", font(11), anchor="w", tags=T_)
        cv.create_text(rx, s(18), text="곳마다 잘 맞는 타입이 다릅니다", fill=INK2, font=font(8), anchor="e", tags=T_)
        dex = self.app.dex
        y = s(34)
        ph = E.PLACE_H              # (이미 U.h 로 잰 값 - 한 번 더 s() 하면 줄이 커져 '② 얼마나' 가 밀려 잘렸다)
        for p in X.PLACES:
            on = p["id"] == self.place
            tag = "pl_" + p["id"]
            tg = T_ + ("place", tag)
            K.rrect(cv, lx, y, rx, y + ph, s(8), fill=SEL if on else PANEL, outline=CUR if on else LINE,
                    width=2 if on else 1, tags=tg)
            if on:
                K.cursor(cv, lx + s(8), y + ph // 2, size=s(5), tags=tg)
            cv.create_text(lx + s(22), y + ph // 2, text=p["kr"], fill=INK, font=font(10), anchor="w", tags=tg)
            xx = lx + s(76)
            for t in p["types"]:
                name = dex.type_name(t) if dex is not None else t
                xx = _chip(cv, xx, y + ph // 2, name, U.TYPE_COLOR.get(t, "#9aa2ae"), tg) + s(4)
            cv.tag_bind(tag, "<Button-1>", lambda _e, k=p["id"]: self.set_place(k))
            y += ph + s(4)
        cv.tag_bind("place", "<Enter>", lambda _e: cv.configure(cursor="hand2"))
        cv.tag_bind("place", "<Leave>", lambda _e: cv.configure(cursor=""))
        # 그곳에서 잘 나오는 것 (흰 글상자)
        p = X.place(self.place) or {}
        y += s(2)
        hint = p.get("hint", "")
        th = K.text_height(cv, hint, font(9), rx - lx - s(24))
        bh = s(22) + th + s(10)
        K.panel(cv, lx, y, rx, y + bh, strong=True, tags=T_)
        cv.create_text(lx + s(12), y + s(14), text="%s에서 잘 나오는 것" % p.get("kr", ""), fill=INK2, font=font(8),
                       anchor="w", tags=T_)
        K.text(cv, lx + s(12), y + s(24), hint, font(9), fill=ORANGE, anchor="nw", width=rx - lx - s(24), tags=T_)
        y += bh + s(14)
        # ② 얼마나
        K.text(cv, lx, y + s(14), "\u2461 얼마나", font(11), anchor="w", tags=T_)
        items = [(hh, "%d시간" % hh) for hh in X.HOURS]
        K.tabs(cv, rx, y, s(28), items, self.hours, "hr_", align="right", tags=T_)
        for hh in X.HOURS:
            cv.tag_bind("hr_%d" % hh, "<Button-1>", lambda _e, v=hh: self.set_hours(v))
        cv.tag_bind("hr_", "<Enter>", lambda _e: cv.configure(cursor="hand2"))
        cv.tag_bind("hr_", "<Leave>", lambda _e: cv.configure(cursor=""))
        cv.create_line(lx + s(90), y + s(28), rx, y + s(28), fill=LINE, tags=T_)
        cv.create_text(rx, y + s(44), text=self.hours_text(), fill=INK2, font=font(8), anchor="e", tags=T_)

    # ---- 오른쪽: 누구를
    def _paint_right(self, cv, x1, x2, h):
        s = U.h
        cv.create_line(x1, 0, x1, h, fill=LINE, width=2, tags=T_)
        lx, rx = x1 + s(14), x2 - s(14)
        K.text(cv, lx, s(18), "\u2462 누구를", font(11), anchor="w", tags=T_)
        cv.create_text(rx, s(18), text=self._pick_note, fill=INK2, font=font(8), anchor="e", tags=T_)
        # 아래 한 줄: 요약 글 (왼쪽) · 성장 · 보내기 (오른쪽) - 기본 탭과 같은 자리
        text, color = self._summary
        bw = max(self.send_btn.want_width(s(36)), s(96))
        gw = max(self.grow_btn.want_width(s(30)), s(72))
        tw = rx - lx - bw - gw - s(8) - s(24)
        th = K.text_height(cv, text, font(10), tw)
        fh = max(s(58), th + s(20))
        fy1 = h - fh
        cv.create_rectangle(x1 + 1, fy1, x2, h, fill=PANEL, outline="", tags=T_)
        cv.create_line(x1 + 1, fy1, x2, fy1, fill=LINE, tags=T_)
        by1 = fy1 + (fh - s(40)) // 2
        by2 = by1 + s(40)
        self.send_btn.layout(rx - bw, by1, rx, by2)
        self.grow_btn.layout(rx - bw - s(8) - gw, by1, rx - bw - s(8), by2)
        K.text(cv, lx, (fy1 + h) // 2, text, font(10), fill=tone(color) if color else INK, anchor="w", width=tw,
               tags=T_)
        # 흰 목록
        ly1, ly2 = s(34), fy1 - s(8)
        K.panel(cv, lx, ly1, rx, ly2, tags=T_)
        if self._empty:
            i = self._wins.get("vl")
            if i is not None:
                cv.itemconfigure(i, state="hidden")
            K.text(cv, (lx + rx) // 2, ly1 + s(50), self._empty, font(10), fill=INK2, anchor="n",
                   width=rx - lx - s(30), justify="center", tags=T_)
        else:
            self._place("vl", self.vl.frame, lx + s(2), ly1 + s(2), rx - lx - s(4), ly2 - ly1 - s(4))

    def _draw_row(self, cv, data, x, y, w, h, tags, hov):
        s = U.h
        mon, _pts, grade = data
        st = self.mon_state(mon)
        sel = mon["id"] == self.pick
        dim = st != "ok"
        bg = SEL if sel else ("#eef4fb" if hov is not None else WHITE)
        cv.create_rectangle(x, y, x + w, y + h, fill=bg, outline="", tags=tags)
        cv.create_line(x + s(8), y + h - 1, x + w - s(8), y + h - 1, fill="#e6eaef", tags=tags)
        if sel:
            K.cursor(cv, x + s(5), y + h // 2, size=s(5), tags=tags)
        info = mon.get("info") or {}
        name = ("★ " if mon.get("shiny") else "") + (info.get("name") or mon.get("species") or "?")
        lx = x + s(18)
        ty, by = y + int(h * 0.30), y + int(h * 0.72)
        col = INK2 if dim else ("#8a6a00" if mon.get("shiny") else INK)
        nid = K.text(cv, lx, ty, name, font(11), fill=col, anchor="w", tags=tags)[1]
        cv.create_text(cv.bbox(nid)[2] + s(6), ty, text="Lv.%s" % mon.get("level", ""), fill=INK2, font=font(8),
                       anchor="w", tags=tags)
        dex = self.app.dex
        good = set((X.place(self.place) or {}).get("types") or ())
        xx = lx
        for t in E.types_of(dex, mon):
            lit = t in good and st == "ok"
            tname = dex.type_name(t) if dex is not None else t
            tc = U.TYPE_COLOR.get(t, "#9aa2ae") if lit else "#e3e6eb"
            xx = _chip(cv, xx, by, tname, tc, tags, lit=lit) + s(4)
        g = self.growth_of(mon["id"])
        if st == "rest":
            top_t, top_c = "쉬는 중", INK2
            bot_t, bot_c = "%s 뒤" % X.hours_text(self.rest_left(mon["id"])), INK2
        elif st == "party":
            top_t, top_c = "데리고 다니는 중", INK2
            bot_t, bot_c = E.grow_text(g), ORANGE if g.get("free") else INK2
        else:
            top_t, top_c = X.GRADE_KR.get(grade, ""), GRADE.get(grade, INK2)
            bot_t, bot_c = E.grow_text(g), ORANGE if g.get("free") else INK2
        K.text(cv, x + w - s(12), ty, top_t, font(10), fill=top_c, anchor="e", tags=tags)
        cv.create_text(x + w - s(12), by, text=bot_t, fill=bot_c, font=font(8), anchor="e", tags=tags)

    # ---------------- 기본 탭이 넘겨 주는 것
    def _paint_slot_cards(self, rows, note):
        self._slot_rows = list(rows)
        self._slot_note = note
        self._soon()
        # 1초마다 줄이는 남은 시간은 그린 뒤에 self.live 에 선다 (_lcd_card) - 그리기 전에 tick 이 시작되면
        # 빈 목록이라 아무것도 안 고친다. 다 그린 뒤 한 번 더 맞춘다.
        self.cv.after_idle(self._kick_tick)

    def _kick_tick(self):
        if self.alive and self.live and self._tick_job is None:
            self._tick_job = self.root.after(1000, self._tick)

    def _paint_place(self):
        self._soon()

    def _paint_hours(self):
        self._soon()

    def set_hours(self, hours):
        self.hours = int(hours)
        self._paint_hours()
        self.vl.refresh()
        self._paint_summary()

    def _paint_pick_list(self, rows, keep, note, empty):
        self._pick_note = note
        self._empty = empty
        self.vl.set([(self.ROW_H, r) for r in rows], keep=keep)
        if self.pick is not None and not keep:
            idx = next((i for i, (m, _p, _g) in enumerate(rows) if m["id"] == self.pick), None)
            if idx is not None:
                self.vl.see(idx)
        self._soon()

    def _show_summary(self, grow_text, grow_on, text, color, can_send):
        self.grow_btn.configure(text=grow_text, state="normal" if grow_on else "disabled")
        self.send_btn.configure(state="normal" if can_send else "disabled")
        self._summary = (text, color)
        self._soon()

    def _thumb(self, label, mon):
        cv, item = label
        num, skin = mon.get("num"), T.skin(mon)
        if not num:
            return
        key = (num, skin)
        got = self.thumbs.get(key)
        if got is not None:
            return cv.itemconfigure(item, image=got)
        api = self.app.api
        size = U.h(E.THUMB)

        def work():
            path = sprite_cache.ensure(api, num, skin)
            if not path:
                return None
            anim = sprites.load_animation(path, size, 0.2, 3.0, max_frames=1, max_size=(size, size))
            return sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key)

        def done(img, err):
            if not self.alive or err or img is None:
                return
            try:
                ph = self.thumbs.get(key) or ImageTk.PhotoImage(img)
                self.thumbs[key] = ph
                cv.itemconfigure(item, image=ph)
            except tk.TclError:
                pass
        run_async(self.root, work, done)
