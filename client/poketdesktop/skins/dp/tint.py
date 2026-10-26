"""DP 테마의 이로치 색 고르기 창 (ui_tint.TintPicker).

v2 (2026-10-25): 기본 창과 같은 크기 안에서, 무늬 · 겹친 테 · 큰 도트 무대를 걷고 단순하게 다시 짰다.

    ┌ 글상자 ─────────────────────────────────────────┐
    │ ★ 리자몽 의 색을 고릅니다                          │
    │ 고른 색은 친구와 상대의 화면에도 ...               │
    └─────────────────────────────────────────────────┘
    [이로치 색 계열]  맨 앞이 이로치 색, 나머지는 ...       (파란 꼬리표)
    [ ][ ][ ][ ][ ][ ][ ][ ]        색 견본 칸 (고른 칸 = 빨간 테 · 크림빛 · 빨간 화살표)
    [기본 색 계열] ...
    [ ][ ][ ][ ][ ][ ][ ][ ]
    상태 글                                  [닫기] [이 색으로]

칸 하나가 캔버스 위의 도형이다. 누르면 고른 표시만 바뀌고, '이 색으로' 를 눌러야 서버에 간다
(기본 창과 같다). 화살표 키로 칸을 옮기고 Enter 로 정한다. 동작(미리보기 받기 · 고르기 · 보내기 · 닫기 · 창 크기 맞추기)은
기본 창(ui_tint.TintPicker) 그대로 - 짓는 고리(_build · _set_art · _paint_cell · _set_ready · _say)만 바꾼다.
"""
import tkinter as tk

from common import tint as T
from common.korean import natural

from ... import ui_common as U
from ... import ui_tint as B
from . import CUR, DIM, INK, INK2, LINE, LINE_D, SEL, TAGC, WHITE, font, tone
from . import kit as K
from .dialogs import BODY, PAD, heading


class _Text(object):
    """상태 글 - 기본 창의 Label 처럼 cget("text") 로 읽힌다."""

    def __init__(self, text=""):
        self.text = text

    def cget(self, key):
        return self.text if key == "text" else None


class TintPicker(B.TintPicker):

    # ---------------- 짓는 고리 ----------------
    def _build(self, box):
        s = U.h
        self.box = box
        self.cw = box + s(14)                               # 칸 하나 (정사각)
        gap = s(B.GAP)
        self.gap = gap
        cw = self.cw
        W = 8 * cw + 7 * gap
        self.W = W
        self.order = []                                     # 칸을 늘어놓은 차례 (화살표 키)
        self.rects = {}                                     # 값 -> (x1, y1, x2, y2)
        self.art = {}                                       # 값 -> 미리보기 PhotoImage
        self.state = {}                                     # 값 -> (고른 것, 지금 색)
        self.say_bad = False

        self.win.configure(bg=BODY, highlightthickness=0)     # (기본 창의 2px 테는 안 쓴다 - 칸이 그만큼 잘린다)
        f = tk.Frame(self.win, bg=BODY)
        f.pack(fill="both", expand=True, padx=PAD, pady=14)
        cv = tk.Canvas(f, bg=BODY, highlightthickness=0, bd=0, width=W + 2, height=10)
        cv.pack()
        self.cv = cv
        self.status = _Text()

        # 위: 글상자 (한 판 - 제목 · 덧붙임)
        head = natural("★ %s 의 색을 고릅니다" % self.name)
        self.head, self.note = _Text(head), _Text(B.NOTE)
        tw = W - s(24)
        th = K.text_height(cv, head, font(11), tw)
        nh = K.text_height(cv, B.NOTE, font(9), tw)
        bh = s(10) + th + s(4) + nh + s(10)
        K.panel(cv, 0, 0, W, bh, strong=True)
        K.text(cv, s(12), s(10), head, font(11), fill=tone(U.SHINY), anchor="nw", width=tw)
        K.text(cv, s(12), s(10) + th + s(4), B.NOTE, font(9), fill=INK2, anchor="nw", width=tw)
        y = bh + s(12)

        # 가운데: 색 견본 두 줄
        for title, name, base in B.ROWS:
            y = heading(cv, 0, W, y, title, "맨 앞이 %s, 나머지는 그 색조를 돌린 것" % name)
            for i, hue in enumerate((0,) + T.HUES):
                v = B.value_of(base, hue)
                x = i * (cw + gap)
                self.rects[v] = (x, y, x + cw, y + cw)
                self.order.append(v)
                ref = _Cell(v)
                self.cells[v] = (ref, ref)
                self.state[v] = (False, False)
            y += cw + s(12)

        # 아래: 상태 글 · 단추
        self.btn_y = y
        self.ok_btn = K.CButton(cv, "이 색으로", self.apply, "red", font(11))
        self.no_btn = K.CButton(cv, "닫기", self.close, "gray", font(11))
        w1, w2 = self.ok_btn.want_width(s(36)), self.no_btn.want_width(s(36))
        bth = s(34)
        self.ok_btn.layout(W - w1, y, W, y + bth)
        self.no_btn.layout(W - w1 - s(8) - w2, y, W - w1 - s(8), y + bth)
        self.say_w = W - w1 - w2 - s(8) - s(24)
        self.ok_btn.configure(state="disabled")
        cv.configure(height=y + bth + s(4))
        self.bth = bth
        self._say("불러오는 중...")
        for v in self.order:
            self._draw_cell(v)

        cv.bind("<Motion>", self._motion)
        cv.bind("<Leave>", lambda _e: cv.configure(cursor=""))
        cv.bind("<Button-1>", self._click)
        for key, d in (("Left", -1), ("Right", 1), ("Up", -8), ("Down", 8)):
            self.win.bind("<%s>" % key, lambda _e, d=d: self._step(d))
        self.win.bind("<Return>", lambda _e: self.apply() if self.ok_btn.enabled else None)
        self.win.bind("<Escape>", lambda _e: self.close())
        self.win.after(80, self._focus)
        return W + 2 + PAD * 2

    def _focus(self):
        try:
            self.cv.focus_set()
        except tk.TclError:
            pass

    def _set_art(self, v, ph):
        self.art[v] = ph
        self._draw_cell(v)

    def _paint_cell(self, v, on, current):
        if self.state.get(v) != (on, current):
            self.state[v] = (on, current)
            self._draw_cell(v)

    def _set_ready(self, ready):
        self.ok_btn.configure(state="normal" if ready else "disabled")

    def _say(self, text, bad=False):
        self.status.text = text
        self.say_bad = bad
        cv = self.cv
        s = U.h
        cv.delete("say")
        if not text:
            return
        spec = font(9)
        txt = K.wrap(cv, text, spec, self.say_w)
        lines = txt.split("\n")
        if len(lines) > 2:                                  # 두 줄까지만 (넘치면 끝에 …)
            last = lines[1]
            f = K.tkfont_of(cv, spec)
            while last and f.measure(last + "…") > self.say_w:
                last = last[:-1]
            txt = "\n".join([lines[0], last + "…"])
        K.text(cv, 0, self.btn_y + self.bth // 2, txt, spec, fill=tone(U.DANGER) if bad else INK2, anchor="w",
               tags=("say",))

    # ---------------- 그리기 ----------------
    def _draw_cell(self, v):
        cv, s = self.cv, U.h
        tag = "cell_%s" % v
        cv.delete(tag)
        on, current = self.state.get(v, (False, False))
        x1, y1, x2, y2 = self.rects[v]
        tg = ("cell", tag)
        K.rrect(cv, x1 + 1, y1 + 1, x2 - 1, y2 - 1, s(6), fill=SEL if on else WHITE,
                outline=CUR if on else (TAGC if current else LINE), width=2 if (on or current) else 1, tags=tg)
        ph = self.art.get(v)
        if ph is not None:
            cv.create_image((x1 + x2) // 2, (y1 + y2) // 2, image=ph, tags=tg)
        if on:                                              # 빨간 화살표 커서 (칸 왼쪽 위)
            K.cursor(cv, x1 + s(7), y1 + s(12), size=s(5), tags=tg)
        if current and not on:                              # 지금 서버에 적힌 색
            cv.create_oval(x2 - s(13), y2 - s(13), x2 - s(7), y2 - s(7), fill=TAGC, outline="", tags=tg)

    # ---------------- 고르기 ----------------
    def _at(self, e):
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        for v, (x1, y1, x2, y2) in self.rects.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return v
        return None

    def _motion(self, e):
        v = self._at(e)
        self.cv.configure(cursor="hand2" if v is not None and v in self.photos else "")

    def _click(self, e):
        v = self._at(e)
        if v is not None:
            self.pick(v)

    def _step(self, d):
        if self.picked not in self.order:
            return "break"
        i = self.order.index(self.picked) + d
        if 0 <= i < len(self.order):
            self.pick(self.order[i])
        return "break"


class _Cell(object):
    """칸 하나의 이름표 (기본 창의 cells 와 같은 모양으로 값 열쇠에 건다)."""

    def __init__(self, v):
        self.v = v
