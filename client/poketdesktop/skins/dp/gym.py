# -*- coding: utf-8 -*-
"""DP 테마의 관장 탭 - 타운맵.

DP 의 타운맵(아래 화면)처럼 그린다.

    위 띠      풀빛 띠(무늬 없음)에 흰 글씨 '관장', 이긴 곳 수 / '전국 지도' · '악당 출현' 단추
    지도       무늬 없는 바다 위의 땅. 땅 빛깔(트레이너 레벨 · 이긴 곳의 금색 · 악당의 검정)은 기본 탭 그대로라
               뜻이 같다. 올린 곳 · 고른 곳의 테두리는 DP 커서처럼 빨갛다. 이름표는 갈무리 글씨이고,
               어두운 땅 위의 이름은 흰 글씨로 바꿔 읽히게 한다.
    오른쪽     무늬 없는 바탕 위에:
               경로 꼬리표(파란 둥근 띠) · 흰 이름판(제목 · 세 칸) · 시·도 바로 가기(황토 단추) 또는
               트레이너 목록(흰 줄 - 레벨 빛 막대 · 이름 · 역할 · Lv / 지역 · 오늘 상태)
               트레이너를 고르면 흰 카드(도트 · 이름 · Lv · 보라 띠 아래 데리고 있는 포켓몬)와 빨간 '도전하기'

지도의 모양 · 확대 · 이름표 자리 잡기와 무엇을 보일지(_summary_data · _list_data · _card_data)는 기본 탭의 것이다.
"""
import tkinter as tk

from PIL import ImageTk

from ... import ui_common as U
from ... import ui_gym as G
from ...ui_gym import CLEAR, FILTERS, STATE_TEXT, TODAY, level_color, region_state
from . import (BTN_LINE, BTN_TAN, CUR, FONT, HOV, INK, INK2, LINE, PURPLE, SEL, SEP, TAGC, WHITE, WIN_BG, font,
               tone)
from . import kit as K
from .battle import mix

SEA = "#7fb2e5"
LAND = "#a8d070"
GRASS, GRASS_LO = "#3d8a3e", "#2c6a2e"
T = ("side",)


def _lum(color):
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _ink_on(fill):
    """그 바탕 위에서 읽히는 글자색 (어두운 바탕이면 흰 글씨)."""
    return "#ffffff" if _lum(fill) < 0.5 else INK


class _Text(object):
    """기본 탭이 Label 처럼 부르는 것 (configure(text=)) 을 받아 캔버스에 다시 그린다."""

    def __init__(self, on_change):
        self.text = ""
        self.on_change = on_change

    def configure(self, text=None, **_kw):
        if text is not None and text != self.text:
            self.text = text
            self.on_change()

    config = configure

    def cget(self, key):
        return self.text if key == "text" else None


class GymWindow(G.GymWindow):
    MAP = {"bg": SEA, "legend_bg": "#f4f4ee", "hint_bg": WHITE, "sido": LAND, "edge": "#2f5a2a", "hot": CUR,
           "label": INK, "label_sub": "#505058", "ink": "#202028", "island": WHITE,
           "legend": INK, "legend_dim": INK2, "link": "#c06810", "hint_line": "#8a96a8"}
    ROW_H = None

    # ---------------- 지도의 글꼴 · 바다
    def _map_family(self):
        return FONT

    def _map_bold(self):
        return "normal"

    def _map_xs(self):
        return font(8)

    def _sido_fill(self, won, total):
        """이긴 곳이 많을수록 풀빛 땅이 금빛으로 (어두운 갈색이 되면 이름이 안 읽힌다)."""
        if not won:
            return LAND
        return mix(LAND, CLEAR, 0.3 + 0.7 * won / float(total or 1))

    def _map_backdrop(self):
        """바다는 무늬 없는 한 빛깔 (캔버스 바탕)이다."""

    def _draw_nation(self):
        G.GymWindow._draw_nation(self)
        self._dress_labels()

    def _draw_sido(self, code):
        G.GymWindow._draw_sido(self, code)
        self._dress_labels()

    def _dress_labels(self):
        """지도의 이름표를 읽히게: 어두운 땅 위의 이름은 흰 글씨로, 그리고 이름 둘레를 땅 빛깔로 한 칸 둘러
        밑으로 지나가는 경계선이 글씨를 가르지 않게 한다 (테두리 글씨가 아니라 땅 빛깔의 받침이다)."""
        cv, d = self.cv, max(1, U.h(1))
        try:
            for i in cv.find_withtag("label"):
                if cv.type(i) != "text" or cv.itemcget(i, "text") == "\u2713":
                    continue
                x, y = cv.coords(i)
                under = [j for j in cv.find_overlapping(x, y, x, y) if "region" in cv.gettags(j)]
                if not under:
                    continue
                ground = cv.itemcget(under[-1], "fill")
                cv.itemconfigure(i, fill=_ink_on(ground))
                for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d), (d, d), (-d, -d), (d, -d), (-d, d)):
                    h = cv.create_text(x + dx, y + dy, text=cv.itemcget(i, "text"), fill=ground,
                                       font=cv.itemcget(i, "font"), anchor=cv.itemcget(i, "anchor"),
                                       tags=("label", "map"))
                    cv.tag_lower(h, i)
        except tk.TclError:
            pass

    # ---------------- 위 띠
    def _header(self):
        self.win.configure(bg=WIN_BG, highlightthickness=0)
        self.hcv = tk.Canvas(self.win, bg=GRASS, highlightthickness=0, bd=0, height=U.h(58))
        self.hcv.pack(fill="x")
        self.hcv.bind("<Configure>", lambda _e: self._paint_head())
        self.sub = _Text(self._paint_head)
        self.sub.text = "불러오는 중..."
        self.back_btn = K.CButton(self.hcv, "전국 지도", self.to_nation, "gray", font(10))
        self.boss_btn = K.CButton(self.hcv, "악당 출현", self.open_boss, "red", font(10))
        self._boss_on = False

    def _paint_head(self):
        cv, s = self.hcv, U.h
        try:
            w = cv.winfo_width() if cv.winfo_width() > 1 else U.h(G.W)
            h = cv.winfo_height() if cv.winfo_height() > 1 else s(58)
            cv.delete("head")
        except tk.TclError:
            return
        t = ("head",)
        cv.create_rectangle(0, 0, w, h, fill=GRASS, outline="", tags=t)
        cv.create_rectangle(0, h - s(3), w, h, fill=GRASS_LO, outline="", tags=t)
        tid = cv.create_text(s(18), h // 2, text="관장", font=font(17), fill=WHITE, anchor="w", tags=t)
        bb = cv.bbox(tid)
        cv.create_text((bb[2] if bb else s(80)) + s(14), h // 2, text=self.sub.text, font=font(10), fill=WHITE,
                       anchor="w", tags=t)
        cv.tag_lower("head")
        bh = s(34)
        x2 = w - s(14)
        for btn, on in ((self.back_btn, True), (self.boss_btn, self._boss_on)):
            if not on:
                btn.hide()
                continue
            bw = btn.want_width(s(30))
            btn.layout(x2 - bw, (h - bh) // 2 - s(1), x2, (h + bh) // 2 - s(1))
            x2 -= bw + s(8)

    def _paint_boss(self):
        b = self.boss or {}
        self._boss_on = bool(b.get("active"))
        if self._boss_on:
            self.boss_btn.text = "악당 출현 · %s" % (b.get("team") or "")
        self._paint_head()

    # ---------------- 아래 줄 (상태)
    def _status(self, parent):
        self.stcv = tk.Canvas(parent, bg=WHITE, height=U.h(30), highlightthickness=0, bd=0)
        self.stcv.pack(fill="x", side="bottom")
        self.stcv.bind("<Configure>", lambda _e: self._paint_status())
        self._status_msg = ("", None)
        self.source = _Text(self._paint_status)

    def _paint_status(self):
        cv, s = self.stcv, U.h
        try:
            cv.delete("all")
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.create_rectangle(0, 0, w, h, fill=WHITE, outline="")
        cv.create_line(0, 0, w, 0, fill=LINE)
        text, color = self._status_msg
        src = self.source.text
        sw = K.tkfont_of(cv, font(8)).measure(src) + s(24) if src else 0
        K.text(cv, s(12), h // 2 + 1, text, font(9), fill=tone(color) if color else INK, anchor="w",
               width=max(40, w - sw - s(24)))
        if src:
            cv.create_text(w - s(12), h // 2 + 1, text=src, fill=INK2, font=font(8), anchor="e")

    def say(self, text, color=None):
        self._status_msg = (text or "", color)
        self._paint_status()

    # ---------------- 오른쪽
    def _side(self, body):
        s = U.h
        self.ROW_H = s(50)
        self.side = tk.Frame(body, bg=WIN_BG, width=s(G.SIDE_W))
        self.side.pack(side="right", fill="y")
        self.side.pack_propagate(False)
        tk.Frame(body, bg=LINE, width=2).pack(side="right", fill="y")
        self.scv = tk.Canvas(self.side, bg=WIN_BG, highlightthickness=0, bd=0)
        self.scv.pack(fill="both", expand=True)
        self.scv.bind("<Configure>", lambda _e: self._side_soon())
        self._side_job = None
        self._wins = {}
        self._sum = None
        self._list = ([], "", None)
        self._card = None
        self._crumb_parts = ([], None)
        self._row_hot = None
        self.vl = K.VList(self.scv, WHITE, self._draw_row)
        self.vl.on_click = lambda data, *_a: self.pick_row(data[0]["region"])
        self.vl.on_hover = self._row_hover
        self.ccv = tk.Canvas(self.scv, bg=WHITE, highlightthickness=0, bd=0)
        U.scrollable(self.ccv, 30)
        self.go_btn = K.CButton(self.scv, "도전하기", None, "red", font(14))
        self.list_btn = K.CButton(self.scv, "‹ 목록", None, "gray", font(10))
        self._show("list")

    def _side_soon(self):
        if self._side_job is None and self.alive:
            try:
                self._side_job = self.scv.after_idle(self._side_paint)
            except tk.TclError:
                pass

    def _place(self, key, widget, x, y, w, h):
        w, h = max(1, int(w)), max(1, int(h))
        i = self._wins.get(key)
        if i is None:
            self._wins[key] = self.scv.create_window(x, y, window=widget, anchor="nw", width=w, height=h)
        else:
            self.scv.coords(i, x, y)
            self.scv.itemconfigure(i, width=w, height=h, state="normal")

    def _unplace(self, key):
        i = self._wins.get(key)
        if i is not None:
            self.scv.itemconfigure(i, state="hidden")

    def _hand(self, tag):
        self.scv.tag_bind(tag, "<Enter>", lambda _e: self.scv.configure(cursor="hand2"))
        self.scv.tag_bind(tag, "<Leave>", lambda _e: self.scv.configure(cursor=""))

    # ---- 기본 탭이 넘겨 주는 것
    def _show(self, mode):
        self._mode = mode
        self._side_soon()

    def _fit_card(self, again=True):
        pass

    def _crumbs(self, parts, back=None):
        self._crumb_parts = (list(parts), back)
        self._side_soon()

    def _paint_summary(self, d):
        self._sum = d
        if d is not None:
            self._crumbs(d["crumbs"])
            if not d["sido"]:
                self._fill_list()
        self._side_soon()

    def _paint_list(self, rows, keep, note, empty):
        self._list = (rows, note, empty)
        self.vl.set([(self.ROW_H, r) for r in rows], keep=keep)
        self._side_soon()

    def _paint_rows(self):
        self.vl.refresh()

    def _hot_row(self, code):
        """지도에서 올린 곳의 줄을 밝히고, 목록 밖에 있으면 보이게 굴린다."""
        if code == self.hot:
            return
        self.hot = code
        if self._mode != "list":
            return
        if code is not None:
            idx = next((i for i, (_h, d) in enumerate(self.vl.rows) if d[0].get("region") == code), None)
            if idx is not None:
                self.vl.see(idx)
        self.vl.refresh()

    def set_filter(self, which):
        self.which = which
        self._fill_list(keep=False)

    def _row_hover(self, data):
        code = data[0].get("region") if data else None
        old, self._row_hot = self._row_hot, code
        if old is not None and old != code:
            self.hover_row(old, False)
        if code is not None and code != old:
            self.hover_row(code, True)

    def _clear_card(self):
        self._card = None
        try:
            self.ccv.delete("all")
            self.ccv.yview_moveto(0)
        except tk.TclError:
            pass
        self.go_btn.hide()

    def _card_loading(self):
        self._card = "loading"
        self._side_soon()

    def _paint_card(self, code, d, img, thumbs):
        self._card = (code, d, img, thumbs)
        self.go_btn.command = lambda: self.challenge(code)
        self.go_btn.configure(text=d["button"], state="normal" if d["can"] else "disabled")
        self._side_soon()

    # ---- 그리기
    def _side_paint(self):
        self._side_job = None
        cv, s = self.scv, U.h
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
            cv.delete("side")
        except tk.TclError:
            return
        if w <= 1:
            return
        y = self._paint_crumbs(cv, w, s(10))
        if self._mode == "card":
            self._unplace("vl")
            self._paint_card_view(cv, w, h, y)
        else:
            self._unplace("card")
            self.go_btn.hide()
            self._paint_list_view(cv, w, h, y)

    def _paint_crumbs(self, cv, w, y):
        s = U.h
        parts, back = self._crumb_parts
        h = s(28)
        x1, x2 = s(12), w - s(12)
        if back is not None:
            self.list_btn.command = back
            bw = self.list_btn.want_width(s(24))
            self.list_btn.layout(x2 - bw, y, x2, y + h + s(2))
            x2 -= bw + s(8)
        else:
            self.list_btn.hide()
        K.rrect(cv, x1, y, x2, y + h, h // 2, fill=TAGC, tags=T)
        x = x1 + s(14)
        for i, (text, cb) in enumerate(parts):
            if i:
                a = cv.create_text(x, y + h // 2, text="\u203a", font=font(10), fill="#bcd4f2", anchor="w", tags=T)
                x = cv.bbox(a)[2] + s(6)
            tag = "crumb%d" % i
            tid = cv.create_text(x, y + h // 2, text=text, font=font(10), fill="#ffe9a0" if cb else WHITE,
                                 anchor="w", tags=T + (tag,))
            if cb:
                cv.tag_bind(tag, "<Button-1>", lambda _e, f=cb: f())
                self._hand(tag)
            x = cv.bbox(tid)[2] + s(6)
        return y + h + s(10)

    def _tabs(self, cv, x, y, items, current, tag, on_pick):
        """탭 줄 (고른 탭은 빨간 글씨 + 밑줄) - 아래에 가는 줄."""
        s = U.h
        h = s(30)
        K.tabs(cv, x, y, h, items, current, tag, tags=T)
        for key, _lb in items:
            cv.tag_bind(tag + str(key), "<Button-1>", lambda _e, k=key: on_pick(k))
        self._hand(tag)
        cv.create_line(x, y + h, cv.winfo_width() - s(12), y + h, fill=LINE, tags=T)
        return y + h

    def _paint_list_view(self, cv, w, h, y):
        s = U.h
        d = self._sum
        if d is None:
            self._unplace("vl")
            return
        x1, x2 = s(12), w - s(12)
        inner = x2 - x1 - s(28)
        th = K.text_height(cv, d["title"], font(16), inner)
        dh = K.text_height(cv, d["desc"], font(9), inner) if d["desc"] else 0
        stats_h = s(46)
        ph = s(12) + th + (s(4) + dh if dh else 0) + s(10) + stats_h + s(12)
        K.panel(cv, x1, y, x2, y + ph, strong=True, tags=T)
        K.text(cv, x1 + s(14), y + s(12), d["title"], font(16), anchor="nw", width=inner, tags=T)
        yy = y + s(12) + th
        if dh:
            K.text(cv, x1 + s(14), yy + s(4), d["desc"], font(9), fill=INK2, anchor="nw", width=inner, tags=T)
            yy += s(4) + dh
        yy += s(10)
        gap = s(6)
        cw = (inner - 2 * gap) / 3.0
        for i, (k, v, color) in enumerate(d["stats"]):
            cx1 = x1 + s(14) + i * (cw + gap)
            K.rrect(cv, cx1, yy, cx1 + cw, yy + stats_h, s(6), fill="#f4f7fa", outline=LINE, width=1, tags=T)
            cv.create_text(cx1 + s(9), yy + s(13), text=k, font=font(8), fill=INK2, anchor="w", tags=T)
            K.text(cv, cx1 + s(9), yy + s(32), v, font(11), fill=tone(color) if color else INK, anchor="w", tags=T)
        y += ph + s(10)
        if d["nation"]:
            y = self._tabs(cv, x1, y, [("sido", "시·도"), ("trainer", "트레이너")], self.nation_view, "nv",
                           self.set_nation_view) + s(10)
        if d["sido"]:
            self._unplace("vl")
            self._paint_sido_grid(cv, x1, x2, y)
            return
        # 트레이너 목록: 머리 · 거르기 · 흰 줄
        rows, note, empty = self._list
        K.text(cv, x1 + s(2), y + s(10), "트레이너", font(11), anchor="w", tags=T)
        K.text(cv, x2 - s(2), y + s(10), note, font(9), fill=INK2, anchor="e", tags=T)
        y += s(22)
        y = self._tabs(cv, x1, y, FILTERS, self.which, "flt", self.set_filter) + s(8)
        ly2 = h - s(12)
        K.panel(cv, x1, y, x2, ly2, tags=T)
        if rows:
            self._place("vl", self.vl.frame, x1 + s(2), y + s(2), x2 - x1 - s(4), ly2 - y - s(4))
        else:
            self._unplace("vl")
            K.text(cv, (x1 + x2) // 2, y + s(40), empty or "", font(10), fill=INK2, anchor="n",
                   width=x2 - x1 - s(30), justify="center", tags=T)

    def _paint_sido_grid(self, cv, x1, x2, y):
        s = U.h
        K.text(cv, x1 + s(2), y + s(10), "시·도 바로 가기", font(11), anchor="w", tags=T)
        y += s(24)
        cols, gap = 4, s(5)
        cw = (x2 - x1 - gap * (cols - 1)) / float(cols)
        ch = s(46)
        for i, (code, label, won, total, done) in enumerate(self._sido_cells()):
            cx1 = x1 + (i % cols) * (cw + gap)
            cy1 = y + (i // cols) * (ch + gap)
            tag = "sd%s" % code
            tg = T + ("sdcell", tag)
            K.rrect(cv, cx1, cy1, cx1 + cw, cy1 + ch, s(8), fill="#ffd860" if done else BTN_TAN, outline=BTN_LINE,
                    width=1, tags=tg)
            cv.create_text(cx1 + cw / 2.0, cy1 + ch * 0.36, text=label, fill=INK, font=font(10), tags=tg)
            cv.create_text(cx1 + cw / 2.0, cy1 + ch * 0.72, text="%d/%d" % (won, total), fill=INK2, font=font(8),
                           tags=tg)
            cv.tag_bind(tag, "<Button-1>", lambda _e, c=code: self.enter_sido(c))
        self._hand("sdcell")

    def _draw_row(self, cv, data, x, y, w, h, tags, hov):
        s = U.h
        t, where = data
        hot = hov is not None or (t.get("region") is not None and t.get("region") == self.hot)
        cv.create_rectangle(x, y, x + w, y + h, fill=HOV if hot else WHITE, outline="", tags=tags)
        cv.create_line(x + s(8), y + h - 1, x + w - s(8), y + h - 1, fill=SEP, tags=tags)
        cv.create_rectangle(x + s(4), y + s(8), x + s(9), y + h - s(8), fill=level_color(t.get("level", 20)),
                            outline="", tags=tags)
        nx = x + s(18)
        ty, by = y + int(h * 0.32), y + int(h * 0.72)
        name = t.get("name") or "?"
        K.text(cv, nx, ty, name, font(11), anchor="w", tags=tags)
        rx = nx + K.tkfont_of(cv, font(11)).measure(name) + s(7)
        cv.create_text(rx, ty, text=t.get("role") or "", fill=INK2, font=font(9), anchor="w", tags=tags)
        K.text(cv, x + w - s(12), ty, "Lv.%d" % t.get("level", 0), font(10), fill=INK2, anchor="e", tags=tags)
        cv.create_text(nx, by, text=where, fill=INK2, font=font(9), anchor="w", tags=tags)
        text, color = STATE_TEXT[region_state(t)]
        cv.create_text(x + w - s(12), by, text=text, fill=tone(color), font=font(9), anchor="e", tags=tags)
        if hot:
            K.rrect(cv, x + s(2), y + s(2), x + w - s(2), y + h - s(3), s(6), outline=CUR, width=2, tags=tags)

    def _paint_card_view(self, cv, w, h, y):
        s = U.h
        x1, x2 = s(12), w - s(12)
        card = self._card
        d = card[1] if isinstance(card, tuple) else None
        bottom = h - s(12)
        if d is not None:
            if d.get("other"):
                K.text(cv, x1 + s(2), bottom - s(8), d["other"], font(8), fill=INK2, anchor="sw",
                       width=x2 - x1, tags=T)
                bottom -= s(26)
            self.go_btn.layout(x1, bottom - s(42), x2, bottom)
            bottom -= s(42) + s(8)
        else:
            self.go_btn.hide()
        K.panel(cv, x1, y, x2, bottom, strong=True, tags=T)
        self._place("card", self.ccv, x1 + s(4), y + s(4), x2 - x1 - s(8), bottom - y - s(8))
        self.ccv.after_idle(self._paint_card_canvas)

    def _paint_card_canvas(self):
        cv, s = self.ccv, U.h
        try:
            cv.delete("all")
            w = cv.winfo_width()
        except tk.TclError:
            return
        if w <= 1:
            return
        card = self._card
        if card == "loading":
            K.text(cv, s(10), s(14), "트레이너를 불러오는 중...", font(10), fill=INK2, anchor="nw")
            return
        if not isinstance(card, tuple):
            return
        _code, d, img, thumbs = card
        x, y = s(8), s(6)
        ix = x
        img_bottom = y
        if img is not None:
            ph = ImageTk.PhotoImage(img)
            self.photos["trainer"] = ph
            cv.create_image(x, y, image=ph, anchor="nw")
            ix = x + img.width + s(10)
            img_bottom = y + img.height
        iw = max(s(80), w - ix - s(8))
        cv.create_text(ix, y + s(2), text=d["role"], fill=INK2, font=font(9), anchor="nw")
        ny = y + s(2) + K.tkfont_of(cv, font(9)).metrics("linespace") + s(2)
        K.text(cv, ix, ny, d["name"], font(17), anchor="nw", width=iw)
        cy = ny + K.text_height(cv, d["name"], font(17), iw) + s(6)
        # 꼬리표: Lv (레벨 빛) · 오늘 상태
        f = font(10)
        lv = "Lv.%d" % d["level"]
        lcol = level_color(d["level"])
        lw = K.tkfont_of(cv, f).measure(lv) + s(14)
        chh = K.tkfont_of(cv, f).metrics("linespace") + s(6)
        K.rrect(cv, ix, cy, ix + lw, cy + chh, s(4), fill=lcol)
        cv.create_text(ix + lw // 2, cy + chh // 2, text=lv, fill=_ink_on(lcol), font=f)
        if d["state"] != "new":
            text, color = STATE_TEXT[d["state"]]
            done = d["state"] == "done"
            sx = ix + lw + s(6)
            sw = K.tkfont_of(cv, f).measure(text) + s(14)
            K.rrect(cv, sx, cy, sx + sw, cy + chh, s(4), fill=TODAY if done else WHITE,
                    outline="" if done else "#c06810", width=2)
            cv.create_text(sx + sw // 2, cy + chh // 2, text=text, fill=INK if done else tone(color), font=f)
        yy = cy + chh + s(6)
        if d["type"]:
            cv.create_text(ix, yy, text=d["type"], fill=INK2, font=font(8), anchor="nw")
            yy += K.tkfont_of(cv, font(8)).metrics("linespace") + s(4)
        _a, b = K.text(cv, ix, yy, d["record"], font(9), fill="#2c8a3c" if d["cleared"] else INK2,
                       anchor="nw", width=iw)
        yy = cv.bbox(b)[3] + s(2)
        _a, b = K.text(cv, ix, yy, d["prize"], font(8), fill=INK2, anchor="nw", width=iw)
        yy = max(cv.bbox(b)[3], img_bottom) + s(8)
        if d["why"]:
            _a, b = K.text(cv, x, yy, d["why"], font(9), fill="#c06810", anchor="nw", width=w - x - s(8))
            yy = cv.bbox(b)[3] + s(8)
        # 데리고 있는 포켓몬 - 보라 띠 (한 겹)
        bh = s(26)
        K.rrect(cv, x, yy, w - s(8), yy + bh, s(6), fill=PURPLE)
        cv.create_text(x + s(12), yy + bh // 2, text="데리고 있는 포켓몬", fill=WHITE, font=font(10), anchor="w")
        yy += bh + s(4)
        row_h = max(s(30), 32)
        for i, m in enumerate(d["team"]):
            ace = i == len(d["team"]) - 1
            if ace:
                K.rrect(cv, x, yy, w - s(8), yy + row_h, s(6), fill=SEL, outline=LINE, width=1)
            th = thumbs.get(m["num"])
            if th is not None:
                ph = ImageTk.PhotoImage(th)
                self.photos["t%d" % i] = ph
                cv.create_image(x + s(20), yy + row_h // 2, image=ph, anchor="center")
            name = m.get("kr") or m.get("species") or ""
            K.text(cv, x + s(42), yy + row_h // 2, name, font(11), anchor="w")
            if ace:
                ax = x + s(42) + K.tkfont_of(cv, font(11)).measure(name) + s(8)
                cv.create_text(ax, yy + row_h // 2, text="에이스", fill="#c06810", font=font(8), anchor="w")
            cv.create_text(w - s(16), yy + row_h // 2, text="Lv.%d" % m["level"], fill=INK, font=font(10),
                           anchor="e")
            lvw = K.tkfont_of(cv, font(10)).measure("Lv.%d" % m["level"])
            cv.create_text(w - s(16) - lvw - s(10), yy + row_h // 2, text="/".join(m.get("types") or []),
                           fill=INK2, font=font(8), anchor="e")
            yy += row_h + s(1)
        cv.configure(scrollregion=(0, 0, w, yy + s(4)))
