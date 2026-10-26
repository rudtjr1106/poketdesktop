# -*- coding: utf-8 -*-
"""DP 테마의 로그인 · 회원가입 - DS 를 켰을 때의 첫 화면과 마카오 박사의 가방처럼.

    위 화면   밤하늘 빛 타이틀 화면: 흰 글씨 '포스크탑' · 한 줄 소개 · 오른쪽에 몬스터볼 도구 그림,
              아래 띠에 접속할 서버(누르면 그 자리에 흰 입력칸이 펴진다)와 판 번호
    아래 화면 위에 '로그인 / 회원가입' 터치 탭 (고른 탭은 흰 바탕 · 빨간 테 · 빨간 화살표),
              파란 꼬리표(닉네임 · 비밀번호)와 흰 입력칸, 비밀번호는 DS 자판 같은 칸 넷 (고른 칸은 빨간 테)
              과 화면 자판
    회원가입  보라 띠 '처음 함께할 포켓몬', 세대 탭 1~9, 가죽 가방 안의 카드 셋 (DP 첫 포켓몬 고르기) -
              카드마다 몬스터볼 · 받침 위의 움직이는 도트 · 이름 · 타입 표, 고른 카드는 빨간 테 · 빨간 화살표
    글상자    맨 아래 DP 글상자에 진행 · 오류 글 (아무 말 없을 때는 'Enter 로 확인')

v2 (2026-10-25): 아래 화면의 몬스터볼 무늬 · 위 화면의 별 · 테두리 글씨 · 겹겹의 테 · 글상자 오른쪽 줄무늬를
걷었다. 몬스터볼은 직접 그리지 않고 앱의 도구 그림을 쓴다 (아직 못 받았으면 그리지 않는다).

서버에 묻는 일(닉네임 확인 · 스타팅 목록 · 도트 받기 · 로그인 · 가입), 입력 검사, 오류 문구는 기본 창
(ui_login.LoginWindow) 그대로다. 여기서는 짓는 고리(_build · _build_login · _build_signup · paint_tabs ·
_paint_server · _paint_name · build_genbar · _paint_gens · say)와 카드 · 비밀번호 칸의 모양만 바꾼다.
"""
import tkinter as tk

from common.korean import natural
from common.version import VERSION

from ... import item_icons
from ... import ui_box as B
from ... import ui_common as U
from ... import ui_login as L
from . import BEZEL, CELL, CUR, DIM, INK, INK2, LINE_D, PLATE_LINE, PURPLE, WHITE, font, tone
from . import kit as K
from .dialogs import BODY, PAD, message_box

W = 460                                    # 창 폭 (기본 창과 같다)
LOW = "#eef2f6"                            # 아래 화면 바탕 (무늬 없음)
SKY = ((0.0, "#0e173f"), (0.6, "#22357c"), (1.0, "#3a4ea6"))   # 위 화면 (DP 타이틀의 밤하늘)
CASE, CASE_LINE, CASE_IN, CASE_IN_LINE = "#c0843c", "#6a4520", "#f6e8c8", "#b08850"   # 마카오 박사의 가방
LINK = "#2860c0"
OFF, OFF_LINE = "#f4f6f9", "#a8b4c4"       # 고르지 않은 탭
GOLD = "#f0c040"
CELL_LINE = "#7a8698"                      # 비밀번호 칸 테


# ---------------------------------------------------------------- 그리는 것
def _rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(ra, rb))


def _ramp(stops, t):
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if a <= t <= b:
            return mix(ca, cb, (t - a) / float((b - a) or 1))
    return stops[-1][1]


def _lh(widget, n):
    return K.tkfont_of(widget, font(n)).metrics("linespace")


def tag(cv, x, y, h, text, tags=()):
    """파란 꼬리표 (흰 보통 글씨). x, y 는 왼쪽 위, h 는 높이. 그 폭."""
    s = U.h
    spec = font(10)
    w = K.tkfont_of(cv, spec).measure(text) + s(20)
    K.rrect(cv, x, y, x + w, y + h, s(6), fill="#3a78c8", tags=tags)
    cv.create_text(x + w // 2, y + h // 2, text=text, fill=WHITE, font=spec, anchor="center", tags=tags)
    return w


def section(cv, x1, x2, y, title, note=""):
    """보라 띠 (단락 제목) - 한 겹, 흰 보통 글씨. 띠 밑의 y."""
    s = U.h
    bh = s(28)
    K.rrect(cv, x1, y, x2, y + bh, s(6), fill=PURPLE)
    cv.create_text(x1 + s(14), y + bh // 2, text=title, fill=WHITE, font=font(10), anchor="w")
    if note:
        cv.create_text(x2 - s(14), y + bh // 2, text=note, fill="#e4e0ff", font=font(9), anchor="e")
    return y + bh


def ball(cv, x, y, d, tags=()):
    """작은 몬스터볼 - 앱의 도구 그림 (왼쪽 위 x, y · 크기 d). 아직 못 받았으면 그리지 않는다."""
    ph = item_icons.photo("POKEBALL", d)
    if ph is not None:
        cv.create_image(x + d // 2, y + d // 2, image=ph, tags=tags)


def type_chip(cv, x, y, text, col, tags=()):
    """타입 표 (왼쪽 x · 가운데 y) - 보통 글씨 (밝은 빛깔이면 진한 글씨). 그 폭."""
    s = U.h
    spec = font(9)
    w = K.tkfont_of(cv, spec).measure(text) + s(14)
    h = _lh(cv, 9) + s(4)
    K.rrect(cv, x, y - h // 2, x + w, y + h // 2, s(4), fill=col, tags=tags)
    cv.create_text(x + w // 2, y, text=text, fill=K.look_of(col)[3], font=spec, anchor="center", tags=tags)
    return w


def chips_width(cv, names):
    s = U.h
    f = K.tkfont_of(cv, font(9))
    return sum(f.measure(t) + s(14) for t in names) + s(4) * max(0, len(names) - 1)


def clamp_line(cv, text, spec, width):
    """한 줄로 - 넘치면 끝에 …"""
    f = K.tkfont_of(cv, spec)
    if f.measure(text) <= width:
        return text
    while text and f.measure(text + "…") > width:
        text = text[:-1]
    return text + "…"


class _Pic(object):
    """기본 카드가 art.configure(image=) 로 도트를 붙인다 - 캔버스의 그 자리(발밑 가운데)에 그림을 놓는다."""

    def __init__(self, cv, x, y, tg):
        self.cv, self.x, self.y, self.tag = cv, x, y, tg

    def configure(self, image=None, **_kw):
        if image is None:
            return
        try:
            self.cv.delete(self.tag)
            self.cv.create_image(self.x, self.y, image=image, anchor="s", tags=(self.tag,))
        except tk.TclError:
            pass

    config = configure


# ---------------------------------------------------------------- 비밀번호 칸
class PinEntry(L.PinEntry):
    """DS 자판의 칸처럼 - 흰 칸에 테 한 겹, 아래 줄 하나. 고른 칸은 빨간 테 · 크림빛 · 빨간 줄.

    press() 는 화면 자판(로그인 칸)이 부른다 - 칸에 숫자를 치는 것과 같다 (빈 첫 칸에 넣고 다음 칸으로,
    마지막 칸이면 on_done. "BS" 는 마지막 숫자를 지우고 그 칸으로)."""

    def _cell(self, i):
        s = U.h
        w, h = s(40), s(44)
        cv = tk.Canvas(self.frame, width=w, height=h, bg=self.frame.cget("bg"), highlightthickness=0, bd=0)
        cv.pack(side="left", padx=(0, s(8)))
        e = tk.Entry(cv, bg=WHITE, fg=INK, insertbackground=INK, relief="flat", bd=0, justify="center",
                     font=font(14), highlightthickness=0, show="●", width=2, disabledbackground=WHITE)
        cv.create_window(w // 2, (h - s(6)) // 2, window=e, width=w - s(14), height=_lh(cv, 14) + s(2))

        def draw(on):
            try:
                cv.delete("key")
                body = CELL if on else WHITE
                K.rrect(cv, 1, 1, w - 1, h - 1, s(6), fill=body, outline=CUR if on else CELL_LINE, width=2,
                        tags=("key",))
                cv.create_rectangle(s(9), h - s(9), w - s(9), h - s(7), fill=CUR if on else "#c4ccd8",
                                    outline="", tags=("key",))
                cv.tag_lower("key")
                e.configure(bg=body)
            except tk.TclError:
                pass
        draw(False)
        e.bind("<FocusIn>", lambda _e: draw(True))
        e.bind("<FocusOut>", lambda _e: draw(False))
        return cv, e

    def press(self, key):
        vals = [e.get() for e in self.entries]
        if key == "BS":
            for i in range(len(vals) - 1, -1, -1):
                if vals[i]:
                    self.entries[i].delete(0, "end")
                    self.entries[i].focus_set()
                    return
            self.focus()
            return
        i = next((k for k, v in enumerate(vals) if not v), None)
        if i is None:
            return
        self.entries[i].insert(0, key)
        if i + 1 < self.digits:
            self.entries[i + 1].focus_set()
        elif self.on_done:
            self.on_done()


# ---------------------------------------------------------------- 카드
class StarterCard(L.StarterCard):
    """가방 안의 카드 한 장 (DP 첫 포켓몬 고르기). 몬스터볼 · 황토 받침 위의 도트 · 이름 · 타입 표.

    고르면 빨간 테 · 크림빛 바탕, 카드 위에 빨간 화살표가 내려온다. 크기는 부모(cardbar)가 알려 준다."""

    def _build(self, parent):
        s = U.h
        self.sel = False
        self.cw = getattr(parent, "card_w", s(120))
        self.ch = getattr(parent, "card_h", s(150))
        self.box = tk.Canvas(parent, width=self.cw, height=self.ch, bg=parent.cget("bg"), highlightthickness=0,
                             bd=0, cursor="hand2")
        self.top = s(11)                                    # 화살표 자리
        self.foot = self.top + s(62)                        # 도트 발밑
        self.art = _Pic(self.box, self.cw // 2, self.foot, "art")
        self.box.bind("<Button-1>", lambda _e: self.on_pick(self.mon["internal"]))
        self._draw()

    def set_selected(self, on):
        self.sel = bool(on)
        self._draw()

    def _draw(self):
        cv, s, w, h = self.box, U.h, self.cw, self.ch
        try:
            cv.delete("card")
        except tk.TclError:
            return
        T = ("card",)
        on = self.sel
        y1 = self.top
        if on:
            cx = w // 2
            cv.create_polygon(cx - s(8), 0, cx + s(8), 0, cx, s(10), fill=CUR, outline="", tags=T)
        # 카드 (테 한 겹 - 고르면 빨간 테 · 크림빛)
        K.rrect(cv, 1, y1, w - 1, h - 1, s(8), fill=CELL if on else WHITE, outline=CUR if on else PLATE_LINE,
                width=3 if on else 2, tags=T)
        ball(cv, s(7), y1 + s(6), 15, tags=T)
        rx, ry = int(w * 0.3), s(7)
        fy = self.foot - s(3)
        cv.create_oval(w // 2 - rx, fy - ry, w // 2 + rx, fy + ry, fill="#e4cc96", outline="", tags=T)
        ny = self.foot + s(4)
        name = clamp_line(cv, self.mon.get("kr") or "", font(11), w - s(12))
        cv.create_text(w // 2, ny, text=name, fill="#a02020" if on else INK, font=font(11), anchor="n", tags=T)
        types = list(self.mon.get("types") or [])
        ids = self.mon.get("typeIds") or []
        cy = ny + _lh(cv, 11) + s(4) + (_lh(cv, 9) + s(4)) // 2
        x = (w - chips_width(cv, types)) // 2
        for i, t in enumerate(types):
            tid = ids[i] if i < len(ids) else ""
            x += type_chip(cv, x, cy, t, U.TYPE_COLOR.get(tid, "#a0a0a8"), tags=T) + s(4)
        cv.tag_raise("art")


# ---------------------------------------------------------------- 창
class LoginWindow(L.LoginWindow):

    # ---------------- 틀
    def _metrics(self):
        s = U.h
        w = self.win
        self.P = s(18)
        self.TOP_H = s(108)
        self.STRIP = s(30)                                 # 위 화면 아래 띠 (서버 · 판)
        self.TABS_H = s(44)
        self.TAG_H = _lh(w, 10) + s(10)
        self.EH = _lh(w, 11) + s(16)                       # 입력칸
        self.PIN_H = s(46)
        self.KEY_H = s(32)                                 # 화면 자판 한 줄
        self.GEN_H = _lh(w, 10) + s(12)
        self.CARD_H = s(11) + s(62) + s(4) + _lh(w, 11) + s(4) + _lh(w, 9) + s(4) + s(8)
        self.CASE_PAD = s(8)
        self.CASE_H = s(8) + self.CASE_PAD * 2 + self.CARD_H
        self.BTN_H = s(44)
        self.MSG_H = 2 * _lh(w, 11) + s(30)
        f = K.tkfont_of(w, font(10))
        self.LABEL_W = max(f.measure(t) for t in ("닉네임", "비밀번호")) + s(24)
        self.FX = self.P + self.LABEL_W + s(12)            # 입력칸이 시작하는 x
        self.FORM_H = self._signup_ys()["end"]

    def _signup_ys(self):
        """회원가입 칸의 줄 자리 (위에서부터). 그리는 곳과 창 높이가 같이 쓴다."""
        s = U.h
        ys = {}
        y = s(12)
        ys["name"] = y
        y += self.EH
        ys["hint"] = y + s(4)
        y += _lh(self.win, 9) + s(10)
        ys["pin"] = y
        y += self.PIN_H + s(12)
        ys["sec"] = y
        y += s(26) + s(8)
        ys["gen"] = y
        y += self.GEN_H + s(8)
        ys["case"] = y
        y += self.CASE_H + s(12)
        ys["btn"] = y
        y += self.BTN_H + s(12)
        ys["end"] = y
        return ys

    def _build(self):
        self.msg = ("", None)
        self._srv_win = None
        self._fcv = None
        self.win = tk.Toplevel(self.root)
        U.style_window(self.win, "포스크탑", W, 748)
        U.apply_theme(self.win)
        self.win.configure(bg=BEZEL, highlightthickness=0)
        self.win.resizable(False, False)
        self._metrics()
        s = U.h

        # 위 화면 (타이틀)
        self.top = tk.Canvas(self.win, bg=SKY[0][1], width=W, height=self.TOP_H, highlightthickness=0, bd=0)
        self.top.pack(fill="x")
        self.server_box = K.entry(self.top, self.server)
        self.top.tag_bind("srv", "<Button-1>", lambda _e: self._toggle_server())
        self.top.tag_bind("srv", "<Enter>", lambda _e: self.top.configure(cursor="hand2"))
        self.top.tag_bind("srv", "<Leave>", lambda _e: self.top.configure(cursor=""))
        tk.Frame(self.win, bg=BEZEL, height=s(6)).pack(fill="x")

        # 아래 화면 (탭 · 칸 · 글상자)
        self.tabs = tk.Canvas(self.win, bg=LOW, width=W, height=self.TABS_H, highlightthickness=0, bd=0)
        self.tabs.pack(fill="x")
        for key in ("login", "signup"):
            self.tabs.tag_bind("tab_" + key, "<Button-1>", lambda _e, k=key: self.switch(k))
        self.tabs.tag_bind("tab", "<Enter>", lambda _e: self.tabs.configure(cursor="hand2"))
        self.tabs.tag_bind("tab", "<Leave>", lambda _e: self.tabs.configure(cursor=""))
        self.panel = tk.Frame(self.win, bg=LOW, width=W, height=self.FORM_H)
        self.panel.pack_propagate(False)
        self.panel.pack(fill="x")
        self.status = tk.Canvas(self.win, bg=LOW, width=W, height=self.MSG_H, highlightthickness=0, bd=0)
        self.status.pack(fill="x")
        self._paint_top()
        self._paint_msg()
        U.fit_window(self.win, W)

    # ---------------- 위 화면
    def _paint_top(self):
        cv, s, H = self.top, U.h, self.TOP_H
        T = ("paint",)
        try:
            cv.delete("paint")
        except tk.TclError:
            return
        band = 3
        y = 0
        while y < H:
            cv.create_rectangle(0, y, W, min(H, y + band), fill=_ramp(SKY, y / float(H)), outline="", tags=T)
            y += band
        # 오른쪽에 몬스터볼 (앱의 도구 그림 - 아직 못 받았으면 없다)
        ph = item_icons.photo("POKEBALL", 60)              # (원본 30px 의 두 배 - 점이 고르게)
        if ph is not None:
            cv.create_image(W - s(64), (H - self.STRIP) // 2, image=ph, tags=T)
        # 글씨 (v2: 테두리 없이)
        cv.create_text(s(24), s(32), text="포스크탑", fill=WHITE, font=font(24), anchor="w", tags=T)
        cv.create_rectangle(s(26), s(52), s(26) + s(64), s(54), fill=GOLD, outline="", tags=T)
        cv.create_text(s(26), s(66), text="바탕화면에서 포켓몬을 만나고 키웁니다", fill="#d6def6", font=font(10),
                       anchor="w", tags=T)
        # 아래 띠: 서버 · 판. 펴면 '서버 [입력칸] 접기'
        sy = H - self.STRIP
        my = sy + self.STRIP // 2
        cv.create_rectangle(0, sy, W, H, fill="#0a1234", outline="", tags=T)
        cv.create_line(0, sy, W, sy, fill="#34469a", width=2, tags=T)
        ver = cv.create_text(W - self.P, my, text="v" + VERSION, fill="#7d8cc4", font=font(9), anchor="e", tags=T)
        vx = cv.bbox(ver)[0]
        if self.server_open:
            lb = cv.create_text(self.P, my, text="서버", fill="#a9b8e8", font=font(9), anchor="w", tags=T)
            fold = cv.create_text(vx - s(14), my, text="접기", fill=GOLD, font=font(9), anchor="e",
                                  tags=T + ("srv",))
            self._srv_box = (cv.bbox(lb)[2] + s(8), cv.bbox(fold)[0] - s(10))
        else:
            room = vx - self.P - s(14)
            cv.create_text(self.P, my, text=clamp_line(cv, self._server_text(), font(9), room), fill="#a9b8e8",
                           font=font(9), anchor="w", tags=T + ("srv",))

    def _server_changed(self):
        self._paint_top()

    def _paint_server(self):
        self._paint_top()
        try:
            if self.server_open:
                x1, x2 = self._srv_box
                h = _lh(self.top, 11) + U.h(8)
                y = self.TOP_H - self.STRIP + (self.STRIP - h) // 2
                if self._srv_win is None:
                    self._srv_win = self.top.create_window(x1, y, window=self.server_box, anchor="nw",
                                                           width=x2 - x1, height=h)
                else:
                    self.top.coords(self._srv_win, x1, y)
                    self.top.itemconfigure(self._srv_win, state="normal", width=x2 - x1, height=h)
                # 맥 Tk 는 캔버스에 막 올린 입력칸의 글을 가끔 안 그린다 (아래 글상자를 막 칠한 뒤면 빈칸으로 남았다) -
                # 조금 뒤에 한 번 더 칠하게 한다
                e = self.server_box.entry
                self.win.after(30, lambda: e.winfo_exists() and e.configure(fg=e.cget("fg")))
            elif self._srv_win is not None:
                self.top.itemconfigure(self._srv_win, state="hidden")
        except tk.TclError:
            pass

    # ---------------- 탭
    def paint_tabs(self):
        cv, s = self.tabs, U.h
        try:
            cv.delete("paint")
        except tk.TclError:
            return
        T = ("paint",)
        H = self.TABS_H
        cv.create_rectangle(0, 0, W, H, fill="#dfe4ea", outline="", tags=T)
        cv.create_line(0, H - 1, W, H - 1, fill="#b8c0cc", width=2, tags=T)
        gap = s(8)
        half = (W - 2 * self.P - gap) // 2
        for i, (key, label) in enumerate((("login", "로그인"), ("signup", "회원가입"))):
            x1 = self.P + i * (half + gap)
            x2 = x1 + half
            y1, y2 = s(8), H - s(6)
            on = self.tab == key
            tg = T + ("tab", "tab_" + key)
            K.rrect(cv, x1, y1, x2, y2, s(8), fill=WHITE if on else OFF, outline=CUR if on else OFF_LINE,
                    width=2 if on else 1, tags=tg)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            if on:
                tw = K.tkfont_of(cv, font(12)).measure(label)
                K.cursor(cv, cx - tw // 2 - s(20), cy, size=s(7), tags=tg)
            cv.create_text(cx, cy, text=label, fill="#c02020" if on else INK, font=font(12), anchor="center",
                           tags=tg)

    # ---------------- 아래 칸 (로그인 · 회원가입이 같이 쓴다)
    def _form(self):
        cv = tk.Canvas(self.panel, bg=LOW, width=W, height=self.FORM_H, highlightthickness=0, bd=0)
        cv.pack(fill="both", expand=True)
        cv.tag_bind("link", "<Enter>", lambda _e: cv.configure(cursor="hand2"))
        cv.tag_bind("link", "<Leave>", lambda _e: cv.configure(cursor=""))
        self._fcv = cv
        return cv

    def _label(self, cv, y, h, text, note=None):
        """왼쪽 이름표 (그 줄의 높이 h 가운데). note 가 있으면 이름표 밑에 흐리게."""
        s = U.h
        if note:
            nh = _lh(cv, 9)
            top = y + (h - self.TAG_H - nh - s(3)) // 2
            tag(cv, self.P, top, self.TAG_H, text)
            cv.create_text(self.P + s(2), top + self.TAG_H + s(3), text=note, fill=INK2, font=font(9), anchor="nw")
        else:
            tag(cv, self.P, y + (h - self.TAG_H) // 2, self.TAG_H, text)

    def _field(self, cv, var):
        """흰 입력칸. state 가 None 이면 고를 때 빨간 테, True · False 면 초록 · 빨간 테 (닉네임 확인)."""
        box = K.entry(cv, var)
        box.state = None
        box.focused = False
        e = box.entry

        def paint(focus=None):
            if focus is not None:
                box.focused = focus
            col = ("#e83030" if box.focused else "#a8b0bc") if box.state is None else (
                "#2c9a4c" if box.state else "#d02828")
            try:
                box.configure(highlightbackground=col, highlightcolor=col)
            except tk.TclError:
                pass
        box.paint = paint
        e.bind("<FocusIn>", lambda _e: paint(True))
        e.bind("<FocusOut>", lambda _e: paint(False))
        return box

    def _put(self, cv, widget, x, y, w=None, h=None):
        kw = {"window": widget, "anchor": "nw"}
        if w:
            kw["width"] = w
        if h:
            kw["height"] = h
        return cv.create_window(x, y, **kw)

    # ---------------- 로그인
    def _build_login(self):
        cv = self._form()
        s = U.h
        lh = _lh(cv, 10)
        keys_h = 2 * self.KEY_H + s(6)
        total = self.EH + s(18) + self.PIN_H + s(10) + keys_h + s(24) + self.BTN_H + s(18) + lh
        y = max(s(16), (self.FORM_H - total) // 2)
        fw = W - self.P - self.FX
        # 닉네임
        self._label(cv, y, self.EH, "닉네임")
        box = self._field(cv, self.li_name)
        self._put(cv, box, self.FX, y, fw, self.EH)
        y += self.EH + s(18)
        # 비밀번호
        self._label(cv, y, self.PIN_H, "비밀번호", "숫자 4자리")
        self.li_pin = PinEntry(cv, 4, on_done=self.do_login)
        self._put(cv, self.li_pin.frame, self.FX, y)
        y += self.PIN_H + s(10)
        self._keypad(cv, self.FX, y, W - self.P, self.li_pin)
        y += keys_h + s(24)
        self.btn_login = K.CButton(cv, "로그인", self.do_login, "red", font(12))
        self.btn_login.layout(self.P, y, W - self.P, y + self.BTN_H)
        y += self.BTN_H + s(18)
        # 처음이신가요? 회원가입
        f = K.tkfont_of(cv, font(10))
        t1, t2 = "처음이신가요?", "회원가입"
        w1, w2 = f.measure(t1), f.measure(t2)
        x = (W - (w1 + s(8) + w2)) // 2
        K.text(cv, x, y, t1, font(10), fill=INK2)
        x2 = x + w1 + s(8)
        K.text(cv, x2, y, t2, font(10), fill=LINK, tags=("link",))
        cv.create_line(x2, y + lh, x2 + w2, y + lh, fill=LINK, width=max(1, s(1)), tags=("link",))
        cv.tag_bind("link", "<Button-1>", lambda _e: self.switch("signup"))
        return box

    def _keypad(self, cv, x1, y, x2, pin):
        """DS 아래 화면의 숫자 자판 (1~5 / 6~0, 오른쪽에 두 줄 높이의 지우기). 누르면 비밀번호 칸에 친 것과 같다."""
        s = U.h
        gap = s(6)
        kw = (x2 - x1 - 5 * gap) / 6.0
        self.keys = {}
        for i, d in enumerate("1234567890"):
            r, c = divmod(i, 5)
            kx = x1 + c * (kw + gap)
            ky = y + r * (self.KEY_H + gap)
            b = K.CButton(cv, d, lambda d=d: pin.press(d), "gray", font(11))
            b.layout(int(kx), ky, int(kx + kw), ky + self.KEY_H)
            self.keys[d] = b
        kx = x1 + 5 * (kw + gap)
        b = K.CButton(cv, "지움", lambda: pin.press("BS"), "blue", font(9))
        b.layout(int(kx), y, x2, y + 2 * self.KEY_H + gap)
        self.keys["BS"] = b

    # ---------------- 회원가입
    def _build_signup(self):
        cv = self._form()
        s = U.h
        ys = self._signup_ys()
        fw = W - self.P - self.FX
        # 닉네임 + 확인 글
        self._label(cv, ys["name"], self.EH, "닉네임")
        self.name_box = self._field(cv, self.rg_name)
        self._put(cv, self.name_box, self.FX, ys["name"], fw, self.EH)
        self.name_hint = cv.create_text(self.FX + s(2), ys["hint"], text="2~12자", fill=INK2, font=font(9),
                                        anchor="nw")
        # 비밀번호
        self._label(cv, ys["pin"], self.PIN_H, "비밀번호", "숫자 4자리")
        self.rg_pin = PinEntry(cv, 4)
        self._put(cv, self.rg_pin.frame, self.FX, ys["pin"])
        # 처음 함께할 포켓몬
        section(cv, self.P, W - self.P, ys["sec"], "처음 함께할 포켓몬", "1~9세대 27마리")
        self.genbar = None
        self.genbtns = {}
        # 가방
        x1, x2 = self.P, W - self.P
        y = ys["case"]
        top = y + s(8)
        hx, hw = W // 2, s(44)
        K.rrect(cv, hx - hw, y - s(4), hx + hw, top + s(10), s(8), fill=CASE_LINE)       # 손잡이
        K.rrect(cv, hx - hw + s(6), y + s(2), hx + hw - s(6), top + s(10), s(4), fill=LOW)
        y2 = top + self.CASE_PAD * 2 + self.CARD_H
        K.rrect(cv, x1, top, x2, y2, s(12), fill=CASE, outline=CASE_LINE, width=2)        # 가방 (테 한 겹)
        for cx in (x1 + s(46), x2 - s(46)):                                              # 걸쇠
            cv.create_rectangle(cx - s(9), top - s(3), cx + s(9), top + s(6), fill=GOLD, outline=CASE_LINE)
        p = self.CASE_PAD
        K.rrect(cv, x1 + p - s(2), top + p - s(2), x2 - p + s(2), y2 - p + s(2), s(8), fill=CASE_IN,
                outline=CASE_IN_LINE, width=1)
        gap = 8                                             # 기본 창이 카드 사이에 두는 틈 (padx 8)
        inner = x2 - x1 - 2 * p - s(8)
        cw = (inner - 2 * gap) // 3
        self.cardbar = tk.Frame(cv, bg=CASE_IN, width=3 * cw + 2 * gap, height=self.CARD_H)
        self.cardbar.pack_propagate(False)
        self.cardbar.card_w, self.cardbar.card_h = cw, self.CARD_H
        self._put(cv, self.cardbar, (W - (3 * cw + 2 * gap)) // 2, top + p, 3 * cw + 2 * gap, self.CARD_H)
        # 가입 단추
        self.btn_signup = K.CButton(cv, "포켓몬을 골라 주세요", self.do_register, "red", font(12))
        self.btn_signup.layout(self.P, ys["btn"], W - self.P, ys["btn"] + self.BTN_H)

    def _paint_name(self, ok, text):
        color = U.FG_FAINT if ok is None else (U.GOOD if ok else U.DANGER)
        mark = "" if ok is None else ("✓ " if ok else "✕ ")
        try:
            cv = self._fcv
            cv.itemconfigure(self.name_hint, text=clamp_line(cv, mark + text, font(9), W - self.P - self.FX),
                             fill=tone(color))
            self.name_box.state = ok
            self.name_box.paint()
        except (tk.TclError, AttributeError):
            pass

    def build_genbar(self):
        cv, s = self._fcv, U.h
        self.genbtns = {}
        n = max(1, len(self.gens))
        gap = s(5)
        y = self._signup_ys()["gen"]
        w = (W - 2 * self.P - gap * (n - 1)) / float(n)
        for i, g in enumerate(self.gens):
            k = g["gen"]
            x = self.P + i * (w + gap)
            self.genbtns[k] = (int(x), y, int(x + w), y + self.GEN_H)
            cv.tag_bind("gen_%d" % k, "<Button-1>", lambda _e, k=k: self.show_gen(k))
        cv.tag_bind("gens", "<Enter>", lambda _e: cv.configure(cursor="hand2"))
        cv.tag_bind("gens", "<Leave>", lambda _e: cv.configure(cursor=""))
        self._paint_gens()

    def _paint_gens(self):
        cv, s = self._fcv, U.h
        try:
            cv.delete("gens")
        except (tk.TclError, AttributeError):
            return
        for k, (x1, y1, x2, y2) in self.genbtns.items():
            on = k == self.gen
            tg = ("gens", "gen_%d" % k)
            K.rrect(cv, x1, y1, x2, y2, s(6), fill=WHITE if on else OFF, outline=CUR if on else OFF_LINE,
                    width=2 if on else 1, tags=tg)
            cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text="%d" % k, font=font(11 if on else 10),
                           fill="#c02020" if on else INK, anchor="center", tags=tg)

    # ---------------- 글상자
    def say(self, msg, color=None):
        self.msg = (msg or "", color)
        self._paint_msg()

    def _paint_msg(self):
        cv, s = self.status, U.h
        try:
            cv.delete("all")
        except tk.TclError:
            return
        x1, y1, x2, y2 = self.P, s(8), W - self.P, self.MSG_H - s(12)
        K.rrect(cv, x1, y1, x2, y2, s(8), fill=WHITE, outline=LINE_D, width=2)      # (v2: 줄무늬 없이)
        text, color = self.msg
        room = x2 - x1 - s(28)
        if text:
            lines = K.wrap(cv, text, font(11), room).split("\n")
            if len(lines) > 2:
                lines = lines[:1] + [clamp_line(cv, " ".join(lines[1:]), font(11), room)]
            cv.create_text(x1 + s(14), (y1 + y2) // 2, text="\n".join(lines), fill=tone(color) if color else INK,
                           font=font(11), anchor="w")
        else:
            cv.create_text(x1 + s(14), (y1 + y2) // 2, text="Enter 로 확인", fill=DIM, font=font(10), anchor="w")


# ---------------------------------------------------------------- 비밀번호 다시 묻기
def ask_password(root, title, message):
    """DP 글상자에 물음, 그 아래 비밀번호 칸 넷, '확인 · 취소' 단추. 확인하면 숫자 네 자리, 닫으면 None."""
    win, f = B._shell(root, title, 360, 220)               # 기본 창과 같은 크기
    out = {}
    s = U.h
    width = 360 - 2 * PAD
    cv = tk.Canvas(f, bg=BODY, highlightthickness=0, bd=0, width=width, height=10)
    cv.pack(fill="x")
    cv.configure(height=message_box(cv, 1, 1, width - 2, natural(message)) + 2)
    pin = PinEntry(f, 4)
    pin.frame.pack(pady=(s(10), 0))

    def ok():
        out["pw"] = pin.get()
        win.destroy()

    pin.on_done = ok
    row = tk.Canvas(f, bg=BODY, highlightthickness=0, bd=0, width=width, height=s(36))
    row.pack(fill="x", pady=(s(12), 0))
    b_ok = K.CButton(row, "확인", ok, "red", font(11))
    b_no = K.CButton(row, "취소", win.destroy, "gray", font(11))
    w1, w2 = b_ok.want_width(s(36)), b_no.want_width(s(36))
    b_ok.layout(width - 2 - w1, 0, width - 2, s(36))
    b_no.layout(width - 2 - w1 - s(8) - w2, 0, width - 2 - w1 - s(8), s(36))
    win.bind("<Return>", lambda _e: ok())
    win.bind("<Escape>", lambda _e: win.destroy())
    win.pin, win.buttons = pin, (b_ok, b_no)
    win.after(60, pin.focus)
    B.fit(win)
    win.grab_set()
    root.wait_window(win)
    return out.get("pw")
