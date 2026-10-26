"""DP 테마의 작은 창들 - 묻는 창 · 고르는 창 · 글 묻는 창, 그리고 모든 작은 창의 틀(_shell).

v2 (2026-10-25): 무늬 · 겹친 테두리 · 테두리 글씨를 걷고 기본 창과 같은 크기로 줄였다.

    틀       납작한 하늘색 띠(기본 머리띠와 같은 높이)에 파란 이름표 (위험한 일이면 분홍 띠 · 빨간 이름표)
    묻는 창  글상자(흰 판 · 진한 테 한 겹)에 물음, 옆(길면 아래)에 '예 / 아니오' 상자 - 빨간 화살표 커서.
             위아래 화살표 · Enter · Esc 로도 고른다. 되돌릴 수 없는 일은 커서가 '취소' 에서 시작한다.
    고르는 창 글상자에 물음, 아래에 고를 것들의 상자 (덧붙임 글은 오른쪽에 흐리게). 많으면 상자 안이 굴러간다.
    글 묻는 창 글상자에 물음 · 덧붙임, 흰 입력칸, '확인 · 취소' 단추

ui_box 의 같은 이름 함수 자리에 들어간다 (skins.skinnable_fn) - 받는 것과 돌려주는 것이 같다.
"""
import tkinter as tk

from common.korean import natural

from ... import ui_box as B
from ... import ui_common as U
from . import CUR, CYAN1, DIM, INK, LINE_D, RED_BTN, RED_LINE, SEL, TAG_LINE, TAGC, WHITE, font
from . import kit as K

BODY = "#eef2f6"                  # 작은 창의 바탕 (위젯 엔진이 기본 창의 U.BG 를 옮기는 빛깔과 같다)
PAD = 18                          # _shell 의 안쪽 여백 (기본과 같다)
BAR_H = 34                        # 머리띠 높이 (기본 U.dialog_bar 와 같다)


def dialog_bar(win, title, danger=False):
    """작은 창의 머리: 납작한 띠에 이름표 (위험한 일이면 분홍 띠 · 빨간 이름표). 무늬 없음."""
    s = U.h
    head = tk.Canvas(win, bg=CYAN1, height=s(BAR_H) + s(2), highlightthickness=0, bd=0)
    head.pack(fill="x")

    def draw(_e=None):
        try:
            ww, hh = head.winfo_width(), head.winfo_height()
            head.delete("all")
        except tk.TclError:
            return
        bg, fill, line = ("#fde8e8", RED_BTN, RED_LINE) if danger else (CYAN1, TAGC, TAG_LINE)
        head.configure(bg=bg)
        head.create_rectangle(0, hh - s(2), ww, hh, fill=line, outline="")
        f = font(11)
        tw = min(ww - s(20), K.tkfont_of(head, f).measure(title) + s(24))
        K.rrect(head, s(10), s(5), s(10) + tw, hh - s(7), s(6), fill=fill)
        head.create_text(s(10) + tw // 2, (hh - s(2)) // 2, text=title, fill="#ffffff", font=f, anchor="center")
    head.bind("<Configure>", draw)
    return head


def heading(cv, x1, x2, y, title, note="", tags=()):
    """단락 제목: 파란 꼬리표 + 오른쪽에 덧붙임 (칸 안의 한 줄). 줄 밑의 y."""
    from . import INK2
    s = U.h
    w, h = K.tag(cv, x1, y, title, tags=tags)
    if note:
        cv.create_text(x1 + w + s(10), y + h // 2, text=note, fill=INK2, font=font(9), anchor="w", tags=tags)
    return y + h + s(8)


def clamp_lines(cv, text, spec, width, n):
    """width 로 접어 n 줄까지만 (넘치면 끝에 …)."""
    lines = K.wrap(cv, text, spec, max(1, width)).split("\n")
    if len(lines) <= n:
        return "\n".join(lines)
    last = lines[n - 1]
    f = K.tkfont_of(cv, spec)
    while last and f.measure(last + "…") > width:
        last = last[:-1]
    return "\n".join(lines[:n - 1] + [last + "…"])


def _shell(parent, title, w, h, danger=False):
    win = tk.Toplevel(parent)
    U.style_window(win, title, w, h)
    U.apply_theme(win)
    win.configure(bg=BODY, highlightthickness=0)
    win.resizable(False, False)
    dialog_bar(win, title, danger)
    body = tk.Frame(win, bg=BODY)
    body.pack(fill="both", expand=True, padx=PAD, pady=16)
    win.shell_w, win.shell_h = w, h
    return win, body


def message_box(cv, x1, y1, x2, text, hint="", min_h=0):
    """DP 글상자: 흰 판 · 진한 테 한 겹에 글. 그린 바닥의 y. min_h 를 주면 그 높이까지 늘린다."""
    s = U.h
    tw = x2 - x1 - s(24)
    th = K.text_height(cv, text, font(11), tw)
    hh = (K.text_height(cv, hint, font(9), tw) + s(4)) if hint else 0
    y2 = y1 + max(min_h, s(10) + th + hh + s(10))
    K.rrect(cv, x1, y1, x2, y2, s(8), fill=WHITE, outline=LINE_D, width=2)
    top = y1 + (y2 - y1 - th - hh) // 2
    K.text(cv, x1 + s(12), top, text, font(11), anchor="nw", width=tw)
    if hint:
        K.text(cv, x1 + s(12), top + th + s(4), hint, font(9), fill=DIM, anchor="nw", width=tw)
    return y2


class ChoiceBox(object):
    """DP 의 고르기 상자 (예 / 아니오 · 고를 것들). 고른 줄 왼쪽에 빨간 화살표.

    items = [(열쇠, 글, 덧붙임 또는 None, 글 빛깔 또는 None)]. 마우스를 올리면 커서가 따라오고, 누르면 고른다.
    """

    def __init__(self, cv, items, on_pick, current=0):
        self.cv = cv
        self.items = items
        self.on_pick = on_pick
        self.cur = current
        self.box = None
        self.row_h = U.h(30)
        cv.bind("<Motion>", self._motion, add="+")
        cv.bind("<Button-1>", self._click, add="+")
        cv.bind("<Leave>", lambda _e: cv.configure(cursor=""), add="+")

    def want_width(self):
        s = U.h
        f, fs = K.tkfont_of(self.cv, font(11)), K.tkfont_of(self.cv, font(9))
        lw = max(f.measure(lb) for _k, lb, _s, _c in self.items)
        sw = max([fs.measure(sub) for _k, _l, sub, _c in self.items if sub] or [0])
        return s(40) + lw + (sw + s(18) if sw else 0) + s(14)

    def height(self):
        return len(self.items) * self.row_h + U.h(16)

    def layout(self, x1, y1, x2):
        self.box = (x1, y1, x2, y1 + self.height())
        self.draw()

    def draw(self):
        cv, s = self.cv, U.h
        cv.delete("choice")
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        tg = ("choice",)
        K.rrect(cv, x1, y1, x2, y2, s(8), fill=WHITE, outline=LINE_D, width=2, tags=tg)
        for i, (_k, label, sub, color) in enumerate(self.items):
            cy = y1 + s(8) + i * self.row_h + self.row_h // 2
            if i == self.cur:
                K.rrect(cv, x1 + s(4), cy - self.row_h // 2, x2 - s(4), cy + self.row_h // 2, s(4), fill=SEL, tags=tg)
                K.cursor(cv, x1 + s(12), cy, size=s(6), tags=tg)
            K.text(cv, x1 + s(30), cy, label, font(11), fill=color or INK, anchor="w", tags=tg)
            if sub:
                cv.create_text(x2 - s(14), cy, text=sub, fill=DIM, font=font(9), anchor="e", tags=tg)

    def index_at(self, y):
        if not self.box:
            return None
        x1, y1, x2, y2 = self.box
        i = int((y - y1 - U.h(8)) // self.row_h)
        return i if 0 <= i < len(self.items) else None

    def _inside(self, e):
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        return (self.box and self.box[0] <= x <= self.box[2] and self.box[1] <= y <= self.box[3]), y

    def _motion(self, e):
        inside, y = self._inside(e)
        i = self.index_at(y) if inside else None
        self.cv.configure(cursor="hand2" if i is not None else "")
        if i is not None and i != self.cur:
            self.cur = i
            self.draw()

    def _click(self, e):
        inside, y = self._inside(e)
        i = self.index_at(y) if inside else None
        if i is not None:
            self.cur = i
            self.pick()

    def move(self, d):
        self.cur = (self.cur + d) % len(self.items)
        self.draw()
        return "break"

    def pick(self):
        self.on_pick(self.items[self.cur][0])
        return "break"


def _keys(win, box, cancel):
    win.bind("<Up>", lambda _e: box.move(-1))
    win.bind("<Down>", lambda _e: box.move(1))
    win.bind("<Return>", lambda _e: box.pick())
    win.bind("<Escape>", lambda _e: cancel())


def _wait(parent, win):
    B.fit(win)
    win.grab_set()
    win.focus_force()
    parent.wait_window(win)


def confirm(parent, title, message, danger=True, ok_text="확인"):
    win, f = B._shell(parent, title, 380, 196, danger=danger)
    out = {"v": False}
    s = U.h
    width = 380 - 2 * PAD
    cv = tk.Canvas(f, bg=BODY, highlightthickness=0, bd=0, width=width, height=10)
    cv.pack(fill="x")

    def pick(v):
        out["v"] = bool(v)
        win.destroy()
    items = [(True, ok_text, None, "#c02020" if danger else None), (False, "취소", None, None)]
    box = ChoiceBox(cv, items, pick, current=1 if danger else 0)    # 되돌릴 수 없는 일은 '취소' 에서 시작
    win.choice = box
    text = natural(message)
    bw = max(box.want_width(), s(104))
    side_w = width - bw - s(8) - s(24)
    if K.text_height(cv, text, font(11), side_w) <= 3 * K.tkfont_of(cv, font(11)).metrics("linespace"):
        # 글상자 옆에 예 / 아니오 상자 (DP 처럼) - 기본 창의 '글 + 단추 줄' 과 같은 높이
        y = message_box(cv, 0, 0, width - bw - s(8), text, min_h=box.height())
        box.layout(width - bw, 0, width)
        cv.configure(height=max(y, box.height()))
    else:
        y = message_box(cv, 0, 0, width, text)
        bw = max(bw, s(130))
        box.layout(width - bw, y + s(8), width)
        cv.configure(height=y + s(8) + box.height())
    _keys(win, box, win.destroy)
    _wait(parent, win)
    return out["v"]


def ask_choice(parent, title, message, options):
    win, f = B._shell(parent, title, 380, 240)
    out = {}
    s = U.h
    width = 380 - 2 * PAD

    def pick(k):
        if k is not None:
            out["v"] = k
        win.destroy()
    items = [(k, lb, sub, None) for k, lb, sub in options] + [(None, "그만두기", None, None)]
    # 물음은 굴러가는 칸 밖에 둔다 - 고를 것이 많아도 물음은 늘 보인다
    top = tk.Canvas(f, bg=BODY, highlightthickness=0, bd=0, width=width, height=10)
    top.pack(fill="x")
    top.configure(height=message_box(top, 0, 0, width, natural(message)) + s(8))
    wrap = tk.Frame(f, bg=BODY)
    wrap.pack(fill="both", expand=True)
    cv = tk.Canvas(wrap, bg=BODY, highlightthickness=0, bd=0, width=width, yscrollincrement=1)
    box = ChoiceBox(cv, items, pick)
    win.choice = box
    box.layout(0, 0, width - (s(16) if len(items) > 8 else 0))
    full = box.height()
    if len(items) > 8:                       # 많으면 상자 안이 굴러간다 (창을 키우지 않는다)
        sb = K.Scroll(wrap, cv, BODY)
        sb.pack(side="right", fill="y")
        cv.configure(yscrollcommand=sb.set, scrollregion=(0, 0, width, full), height=8 * box.row_h + s(16))
        U.scrollable(cv, 3)
        U.install_wheel(win)

        def follow(d):
            box.move(d)
            y = s(8) + box.cur * box.row_h
            lo, hi = cv.yview()
            if y < lo * full or y + box.row_h > hi * full:
                cv.yview_moveto(max(0.0, (y - s(8)) / float(full)))
            return "break"
        win.bind("<Up>", lambda _e: follow(-1))
        win.bind("<Down>", lambda _e: follow(1))
        win.bind("<Return>", lambda _e: box.pick())
        win.bind("<Escape>", lambda _e: win.destroy())
    else:
        cv.configure(height=full)
        _keys(win, box, win.destroy)
    cv.pack(side="left", fill="both", expand=True)
    _wait(parent, win)
    return out.get("v")


def ask_text(parent, title, message, hint="", initial=""):
    win, f = B._shell(parent, title, 380, 216)
    out = {}
    s = U.h
    width = 380 - 2 * PAD
    cv = tk.Canvas(f, bg=BODY, highlightthickness=0, bd=0, width=width, height=10)
    cv.pack(fill="x")
    cv.configure(height=message_box(cv, 0, 0, width, natural(message), hint))
    var = tk.StringVar(value=initial)
    box = K.entry(f, var)
    box.pack(fill="x", pady=(s(10), 0), ipady=s(3))

    def ok():
        out["v"] = var.get().strip()
        win.destroy()
    row = tk.Canvas(f, bg=BODY, highlightthickness=0, bd=0, width=width, height=s(36))
    row.pack(fill="x", pady=(s(12), 0))
    b_ok = K.CButton(row, "확인", ok, "red", font(11))
    b_no = K.CButton(row, "취소", win.destroy, "gray", font(11))
    w1, w2 = b_ok.want_width(s(36)), b_no.want_width(s(36))
    b_ok.layout(width - w1, 0, width, s(34))
    b_no.layout(width - w1 - s(8) - w2, 0, width - w1 - s(8), s(34))
    win.bind("<Return>", lambda _e: ok())
    win.bind("<Escape>", lambda _e: win.destroy())
    win.entry_box, win.buttons = box, (b_ok, b_no)
    win.after(60, lambda: box.entry.focus_set())
    B.fit(win)
    win.grab_set()
    parent.wait_window(win)
    return out.get("v")
