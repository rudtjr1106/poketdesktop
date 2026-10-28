# -*- coding: utf-8 -*-
"""DP 테마의 그리기 부품 - 캔버스 위에 직접 그린다.

Tk 의 Label 은 글자에 그림자도 테두리도 못 단다. DP 화면의 인상은 거의 그 둘(진회색 글자의 옅은
그림자, 흰 단추 글씨의 진한 테두리)과 둥근 칸 · 줄무늬에서 오므로, DP 화면은 **캔버스 한 장에 직접
그린다** (scene). 입력칸처럼 진짜 위젯이 필요한 것만 캔버스 위에 올린다 (create_window).

    text / outlined   그림자 글자 · 테두리 글자
    rrect             둥근 네모 (모서리를 점으로 찍어 또렷하게 - 부드럽게 뭉개지 않는다)
    clipped           모서리를 깎은 판 (파티 판)
    CButton           캔버스에 그린 단추 (configure(text=, state=) 는 기본 단추와 같다)
    VList             보이는 줄만 그리는 캔버스 목록 (수백 줄이어도 그릴 것은 화면만큼)
"""
import math
import tkinter as tk
import tkinter.font as tkfont

from ... import ui_common as U
from . import CUR, INK, RADIUS_K, SH, font

_FONTS = {}


def tkfont_of(widget, spec):
    key = tuple(spec)
    f = _FONTS.get(key)
    if f is None:
        f = tkfont.Font(widget, font=spec)
        _FONTS[key] = f
    return f


def shadow_dx(spec):
    """글자 크기에 맞는 그림자 거리 (DS 한 칸)."""
    return max(1, int(round(abs(int(spec[1])) / 9.0)))


# ---------------------------------------------------------------- 글자
def wrap(cv, s, spec, width):
    """**띄어쓰기에서** 줄을 바꾼다 (keep-all). Tk 는 한글을 아무 글자에서나 끊어서 '공격한/다' 가 된다.

    한 낱말이 폭보다 길면 그 낱말만 글자 단위로 끊는다.
    """
    if not s or not width or width <= 0:
        return s or ""
    f = tkfont_of(cv, spec)
    out = []
    for para in str(s).split("\n"):
        line = ""
        for word in para.split(" "):
            cand = word if not line else line + " " + word
            if f.measure(cand) <= width:
                line = cand
                continue
            if line:
                out.append(line)
            # 낱말 하나가 폭보다 길다 - 그 낱말만 글자로 끊는다
            while f.measure(word) > width and len(word) > 1:
                k = len(word)
                while k > 1 and f.measure(word[:k]) > width:
                    k -= 1
                out.append(word[:k])
                word = word[k:]
            line = word
        out.append(line)
    return "\n".join(out)


def text(cv, x, y, s, spec, fill=INK, shadow=None, anchor="nw", tags=(), width=None, justify="left"):
    """글자. width 를 주면 띄어쓰기에서 접는다. (그림자 id, 글자 id) - 그림자는 shadow 빛깔을 줄 때만
    (v2: 기본은 그림자 없음 - 작은 글씨가 번져 보였다)."""
    d = shadow_dx(spec)
    if width:
        s = wrap(cv, s, spec, width)
    kw = {"anchor": anchor, "font": spec, "tags": tags, "justify": justify}
    a = cv.create_text(x + d, y + d, text=s, fill=shadow, **kw) if shadow else None
    b = cv.create_text(x, y, text=s, fill=fill, **kw)
    return a, b


def outlined(cv, x, y, s, spec, fill="#ffffff", line="#3a4250", anchor="nw", tags=(), w=None):
    """진한 테두리를 두른 흰 글자 (DP 의 단추 · 이름표). 마지막이 글자 id."""
    d = w or shadow_dx(spec)
    for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d), (d, d), (-d, -d), (d, -d), (-d, d)):
        cv.create_text(x + dx, y + dy, text=s, fill=line, font=spec, anchor=anchor, tags=tags)
    return cv.create_text(x, y, text=s, fill=fill, font=spec, anchor=anchor, tags=tags)


def text_height(cv, s, spec, width):
    """width 로 접었을 때의 높이 (재고 지운다)."""
    i = cv.create_text(-9999, -9999, text=wrap(cv, s, spec, width), font=spec, anchor="nw")
    try:
        b = cv.bbox(i)
        return (b[3] - b[1]) if b else 0
    finally:
        cv.delete(i)


# ---------------------------------------------------------------- 모양
def _round_pts(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    if r < 1:
        return [x1, y1, x2, y1, x2, y2, x1, y2]
    pts = []
    steps = max(2, int(r / 2))
    for cx, cy, a0 in ((x2 - r, y1 + r, -90), (x2 - r, y2 - r, 0), (x1 + r, y2 - r, 90), (x1 + r, y1 + r, 180)):
        for k in range(steps + 1):
            a = math.radians(a0 + 90.0 * k / steps)
            pts += [round(cx + r * math.cos(a)), round(cy + r * math.sin(a))]
    return pts


def rrect(cv, x1, y1, x2, y2, r, fill="", outline="", width=1, tags=()):
    """둥근 네모. 테두리 두께는 안쪽으로 먹지 않고 선 가운데로 그린다 (Tk 다각형).
    모서리는 테마의 RADIUS_K 배 (게임보이 테마처럼 각진 테마는 0 - 그러면 네모)."""
    r = int(round(r * RADIUS_K))
    if r <= 0:
        return cv.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width if outline else 0,
                                   tags=tags)
    return cv.create_polygon(_round_pts(x1, y1, x2, y2, r), fill=fill, outline=outline,
                             width=width if outline else 0, tags=tags)


def framed(cv, x1, y1, x2, y2, r, fill, line, inner=None, lw=3, iw=2, tags=()):
    """DP 의 칸: 진한 테두리 + 안쪽 옅은 줄 + 바탕."""
    rrect(cv, x1, y1, x2, y2, r, fill=line, tags=tags)
    if inner:
        rrect(cv, x1 + lw, y1 + lw, x2 - lw, y2 - lw, max(0, r - lw), fill=inner, tags=tags)
        rrect(cv, x1 + lw + iw, y1 + lw + iw, x2 - lw - iw, y2 - lw - iw, max(0, r - lw - iw), fill=fill, tags=tags)
    else:
        rrect(cv, x1 + lw, y1 + lw, x2 - lw, y2 - lw, max(0, r - lw), fill=fill, tags=tags)


def clipped(cv, x1, y1, x2, y2, c, fill, tags=()):
    """왼쪽 위 · 오른쪽 아래 모서리를 깎은 판 (DP 파티 판)."""
    return cv.create_polygon(x1 + c, y1, x2, y1, x2, y2 - c, x2 - c, y2, x1, y2, x1, y1 + c,
                             fill=fill, outline="", tags=tags)


def hstripes(cv, x1, y1, x2, y2, c1, c2, band, tags=()):
    cv.create_rectangle(x1, y1, x2, y2, fill=c1, outline="", tags=tags)
    y = y1 + band
    while y < y2:
        cv.create_rectangle(x1, y, x2, min(y2, y + band), fill=c2, outline="", tags=tags)
        y += 2 * band


def dstripes(cv, x1, y1, x2, y2, c1, c2, step, tags=()):
    """빗금 바탕 (DP 파티 화면). 띠를 다각형으로 그려 칸 밖으로 안 나가게 자른다."""
    cv.create_rectangle(x1, y1, x2, y2, fill=c1, outline="", tags=tags)
    w, h = x2 - x1, y2 - y1
    k = -h
    while k < w:
        # 기울기 -1 인 띠: 위쪽 가장자리에서 x = x1 + k .. k+step, 아래로 갈수록 왼쪽
        a, b = k, k + step
        poly = []
        for (px, py) in ((a, 0), (b, 0), (b - h, h), (a - h, h)):
            poly.append((px, py))
        clip = _clip_poly(poly, 0, 0, w, h)
        if len(clip) >= 3:
            flat = []
            for px, py in clip:
                flat += [x1 + px, y1 + py]
            cv.create_polygon(flat, fill=c2, outline="", tags=tags)
        k += 2 * step


def _clip_poly(poly, x1, y1, x2, y2):
    """다각형을 사각형으로 자른다 (Sutherland-Hodgman)."""
    def clip(pts, inside, cross):
        out = []
        for i in range(len(pts)):
            cur, prev = pts[i], pts[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(cross(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cross(prev, cur))
        return out

    def xcross(x):
        return lambda p, q: (x, p[1] + (q[1] - p[1]) * (x - p[0]) / float((q[0] - p[0]) or 1e-9))

    def ycross(y):
        return lambda p, q: (p[0] + (q[0] - p[0]) * (y - p[1]) / float((q[1] - p[1]) or 1e-9), y)
    pts = poly
    for inside, cross in ((lambda p: p[0] >= x1, xcross(x1)), (lambda p: p[0] <= x2, xcross(x2)),
                          (lambda p: p[1] >= y1, ycross(y1)), (lambda p: p[1] <= y2, ycross(y2))):
        pts = clip(pts, inside, cross)
        if not pts:
            break
    return pts


# ---------------------------------------------------------------- 단추
# 단추 빛깔: (몸, 올렸을 때, 테 · 바닥 그늘, 글자). v2 - 납작한 둥근 단추, 글씨에 테두리를 두르지 않는다.
KINDS = {
    "blue": ("#3570d0", "#4682e2", "#1f4890", "#ffffff"),
    "gray": ("#f4f6f9", "#ffffff", "#8a96a8", "#2c3038"),
    "red": ("#d8463e", "#e65a52", "#962822", "#ffffff"),
    "off": ("#e5e8ec", "#e5e8ec", "#c2c8d0", "#9aa1ab"),
}


def look_of(fill):
    """아무 빛깔 -> 단추 빛깔 넷 (몸, 올렸을 때, 테, 글자). 밝은 빛깔이면 글자를 진하게."""
    import colorsys
    c = fill.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    lum = 0.299 * r + 0.587 * g + 0.114 * b

    def mixc(t, to):
        tr, tg, tb = (int(to[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        return "#%02x%02x%02x" % tuple(int(round((x + (y - x) * t) * 255)) for x, y in ((r, tr), (g, tg), (b, tb)))
    _h, _s, _v = colorsys.rgb_to_hsv(r, g, b)
    return fill, mixc(0.15, "#ffffff"), mixc(0.45, "#000000"), "#2c3038" if lum > 0.62 else "#ffffff"


def button_shape(cv, x1, y1, x2, y2, body, line, tags=(), down=False):
    """납작한 단추 모양: 바닥 그늘 2px + 테 1px 의 몸. 누르면 1px 내려앉는다. 몸 도형 id."""
    r = min(7, (y2 - y1) // 3)
    d = 1 if down else 0
    rrect(cv, x1, y1 + 2, x2, y2, r, fill=line, tags=tags)
    return rrect(cv, x1, y1 + d, x2, y2 - 2 + d, r, fill=body, outline=line, width=1, tags=tags)


class CButton(object):
    """캔버스에 그린 DP 단추. 자리는 layout() 으로, 글씨 · 켜짐은 configure() 로 (기본 단추와 같은 말).

    누르면 아래로 한 칸 내려앉는다. 못 누르면 회색 · 흐린 글씨.

    **올리고 누를 때는 도형을 지우지 않는다** (빛깔을 바꾸고 옮기기만 한다). 마우스 밑의 도형을 지우고 새로
    그리면 Tk 가 마우스 밑을 다시 찾아 새 도형에 <Enter> 를 또 보내고, 그러면 또 그리고 - 끝없이 돈다
    (root.update() 가 안 돌아온다). 지우고 다시 그리는 것은 layout() · configure() 뿐이다.
    """

    def __init__(self, cv, text, command, kind="blue", spec=None, tag=None):
        self.cv = cv
        self.text = text
        self.command = command
        self.kind = kind
        self.spec = spec or font(12)
        self.tag = tag or ("btn%d" % id(self))
        self.enabled = True
        self.box = None
        self._hover = False
        self._down = False
        self._body_id = None
        self._shift = 0
        self._binds = [(seq, cv.tag_bind(self.tag, seq, fn)) for seq, fn in (
            ("<Enter>", self._enter), ("<Leave>", self._leave), ("<Button-1>", self._press),
            ("<ButtonRelease-1>", self._release))]

    def want_width(self, pad=28):
        return tkfont_of(self.cv, self.spec).measure(self.text) + pad

    def layout(self, x1, y1, x2, y2):
        self.box = (x1, y1, x2, y2)
        self.draw()

    def hide(self):
        self.box = None
        self.cv.delete(self.tag)

    def dispose(self):
        """지우고 바인딩도 푼다 (그릴 때마다 단추를 새로 만드는 칸이 다시 그리기 전에 부른다)."""
        self.hide()
        for seq, fid in self._binds:
            try:
                self.cv.tag_unbind(self.tag, seq, fid)
            except tk.TclError:
                pass
        self._binds = []

    def draw(self):
        cv = self.cv
        cv.delete(self.tag)
        self._body_id = None
        self._shift = 0
        # 새 도형이다 - 마우스가 아직 위에 있으면 다음 움직임에 <Enter> 가 다시 온다 (지운 도형의 <Leave> 는
        # 안 오므로, 들고 있던 올림을 그대로 두면 마우스가 나간 뒤에도 밝은 채 남는다)
        self._hover = self._down = False
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        body, hi, line, ink = KINDS["off" if not self.enabled else self.kind]
        m = (self.tag, self.tag + "_m")              # 누르면 내려앉는 것 (바닥 그늘만 빼고)
        r = min(7, (y2 - y1) // 3)
        rrect(cv, x1, y1 + 2, x2, y2, r, fill=line, tags=(self.tag,))              # 바닥 그늘
        self._body_id = rrect(cv, x1, y1, x2, y2 - 2, r, fill=body, outline=line, width=1, tags=m)
        cv.create_text((x1 + x2) // 2, (y1 + y2 - 2) // 2, text=self.text, fill=ink, font=self.spec,
                       anchor="center", tags=m)
        self._state()

    def _state(self):
        """올림 · 누름을 그려 둔 도형에 입힌다 (지우지 않는다)."""
        if self._body_id is None:
            return
        body, hi, _line, _ink = KINDS["off" if not self.enabled else self.kind]
        try:
            self.cv.itemconfigure(self._body_id, fill=hi if (self._hover and self.enabled) else body)
            want = 1 if (self._down and self.enabled) else 0
            if want != self._shift:
                self.cv.move(self.tag + "_m", 0, want - self._shift)
                self._shift = want
        except tk.TclError:
            pass

    # 기본 단추(U.PushButton)와 같은 말을 받는다 - 가방 창의 동작 코드가 그대로 부른다.
    def configure(self, text=None, state=None):
        changed = False
        if text is not None and str(text) != self.text:
            self.text = str(text)
            changed = True
        if state is not None and (state == "normal") != self.enabled:
            self.enabled = (state == "normal")
            changed = True
        if changed:
            self.draw()

    config = configure

    def cget(self, key):
        return {"text": self.text, "state": "normal" if self.enabled else "disabled"}.get(key)

    def _enter(self, _e):
        self._hover = True
        self.cv.configure(cursor="hand2" if self.enabled else "")
        self._state()

    def _leave(self, _e):
        self._hover = self._down = False
        self.cv.configure(cursor="")
        self._state()

    def _press(self, _e):
        if self.enabled:
            self._down = True
            self._state()

    def _release(self, _e):
        was = self._down
        self._down = False
        self._state()
        if was and self.enabled and self.command:
            self.command()

    def invoke(self):
        if self.enabled and self.command:
            self.command()


# ---------------------------------------------------------------- 목록
class VList(object):
    """보이는 줄만 그리는 캔버스 목록.

        vl = VList(parent, bg, draw)        draw(cv, 자료, x, y, w, h, tag) 가 그 줄을 그린다
        vl.set([(높이, 자료), ...], keep=True)
        vl.refresh()                        보이는 줄을 다시 그린다 (고름 · 상태가 바뀌었을 때)

    휠은 창이 한 군데서 받아 보내 준다 (U.install_wheel - 캔버스에 wheel_div 만 단다).
    """

    def __init__(self, parent, bg, draw, scrollbar=True, on_click=None):
        self.draw_row = draw
        self.on_click = on_click          # on_click(자료, x, 줄 안의 y, 폭)
        self.on_hover = None              # on_hover(자료 또는 None) - 마우스가 다른 줄로 옮겨 갔을 때
        self._hover = None                # (줄 번호, x) - 마우스가 올라간 줄
        self.rows = []
        self.tops = []
        self.total = 0
        self.frame = tk.Frame(parent, bg=bg, bd=0, highlightthickness=0)
        self.cv = tk.Canvas(self.frame, bg=bg, highlightthickness=0, bd=0, yscrollincrement=1)
        self.sb = None
        if scrollbar:
            self.sb = Scroll(self.frame, self.cv, bg)
            self.sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.configure(yscrollcommand=self._scrolled)
        U.scrollable(self.cv, 3)
        self._job = None
        self._w = 0
        self.cv.bind("<Configure>", self._configure)
        # 줄마다 바인딩을 걸지 않는다 - 줄을 다시 그릴 때마다 항목이 바뀌어 '들어옴/나감' 이 꼬인다.
        # 캔버스 하나가 받아서 몇 번째 줄인지 센다.
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<Leave>", self._left)
        self.cv.bind("<Button-1>", self._click)

    def set(self, rows, keep=True):
        self.rows = list(rows)
        self.tops = []
        y = 0
        for hgt, _d in self.rows:
            self.tops.append(y)
            y += hgt
        self.total = y
        self.cv.configure(scrollregion=(0, 0, max(1, self._w), max(1, self.total)))
        if not keep:
            self.cv.yview_moveto(0)
        self.refresh()

    def _configure(self, e):
        if e.width != self._w:
            self._w = e.width
            self.cv.configure(scrollregion=(0, 0, max(1, self._w), max(1, self.total)))
        self.refresh()

    def _scrolled(self, lo, hi):
        if self.sb is not None:
            self.sb.set(lo, hi)
        self._soon()
        fn = getattr(self, "on_scroll", None)
        if fn is not None:
            try:
                self.cv.after_idle(fn)
            except tk.TclError:
                pass

    def _soon(self):
        if self._job is None:
            self._job = self.cv.after_idle(self.refresh)

    def refresh(self):
        self._job = None
        cv = self.cv
        try:
            cv.delete("row")
            w = cv.winfo_width()
            h = cv.winfo_height()
            top = cv.canvasy(0)
        except tk.TclError:
            return
        if w <= 1:
            return
        bottom = top + h
        import bisect
        i = max(0, bisect.bisect_right(self.tops, top) - 1)
        while i < len(self.rows) and self.tops[i] < bottom:
            hgt, data = self.rows[i]
            tag = "row%d" % i
            hov = self._hover[1] if (self._hover and self._hover[0] == i) else None
            self.draw_row(cv, data, 0, self.tops[i], w, hgt, ("row", tag), hov)
            i += 1

    def index_at(self, y):
        """캔버스 위 y(화면 기준)가 몇 번째 줄인가. 없으면 None."""
        import bisect
        try:
            cy = self.cv.canvasy(y)
        except tk.TclError:
            return None
        i = bisect.bisect_right(self.tops, cy) - 1
        if 0 <= i < len(self.rows) and cy < self.tops[i] + self.rows[i][0]:
            return i
        return None

    def _motion(self, e):
        i = self.index_at(e.y)
        new = (i, e.x) if i is not None else None
        old = self._hover
        self._hover = new
        # 줄이 바뀌었을 때만 다시 그린다 (판 목록은 한 줄에 둘이라 x 도 본다 - 다시 그리는 쪽이 판단)
        if (old is None) != (new is None) or (old and new and (old[0] != new[0] or self._col(old[1]) != self._col(new[1]))):
            self.refresh()
        if self.on_hover and (old and old[0]) != (new and new[0]):
            self.on_hover(self.rows[i][1] if i is not None else None)
        self.cv.configure(cursor="hand2" if new else "")

    def _col(self, x):
        """줄 안에서 칸이 바뀌는 곳 (판이 둘인 줄). 그리는 쪽이 알려 주지 않으면 줄 하나가 한 칸."""
        fn = getattr(self, "col_of", None)
        return fn(x) if fn else 0

    def _left(self, _e):
        if self._hover is not None:
            self._hover = None
            self.refresh()
            if self.on_hover:
                self.on_hover(None)
        self.cv.configure(cursor="")

    def _click(self, e):
        i = self.index_at(e.y)
        if i is None or not self.on_click:
            return
        hgt, data = self.rows[i]
        self.on_click(data, e.x, self.cv.canvasy(e.y) - self.tops[i], self.cv.winfo_width())

    def see(self, index):
        """그 줄이 보이게 굴린다."""
        if not (0 <= index < len(self.rows)) or self.total <= 0:
            return
        top = self.cv.canvasy(0)
        h = self.cv.winfo_height()
        y, hgt = self.tops[index], self.rows[index][0]
        if y < top:
            self.cv.yview_moveto(y / float(self.total))
        elif y + hgt > top + h:
            self.cv.yview_moveto(max(0, y + hgt - h) / float(self.total))

    def visible(self):
        """화면에 걸친 줄의 자료들."""
        try:
            top = self.cv.canvasy(0)
            bottom = top + self.cv.winfo_height()
        except tk.TclError:
            return []
        return [d for (hgt, d), y in zip(self.rows, self.tops) if y < bottom and y + hgt > top]


class Scroll(tk.Canvas):
    """DP 풍 막대 - 옅은 홈에 둥근 손잡이. 끌거나 홈을 누르면 굴린다.

    orient="horizontal" 이면 가로 막대 (글자를 키워 판이 창보다 넓을 때 - scene.SceneCanvas)."""

    def __init__(self, parent, target, bg, width=None, orient="vertical"):
        self.horiz = orient == "horizontal"
        size = width or U.h(12)
        if self.horiz:
            tk.Canvas.__init__(self, parent, height=size, bg=bg, highlightthickness=0, bd=0)
        else:
            tk.Canvas.__init__(self, parent, width=size, bg=bg, highlightthickness=0, bd=0)
        self.target = target
        self.lo, self.hi = 0.0, 1.0
        self._drag = None
        self.bind("<Configure>", lambda _e: self.draw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_drag", None))

    def set(self, lo, hi):
        self.lo, self.hi = float(lo), float(hi)
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or self.hi - self.lo >= 0.999:
            return
        if self.horiz:
            rrect(self, 2, 2, w - 2, h - 2, (h - 4) // 2, fill="#d8dde4")
            x1 = 2 + (w - 4) * self.lo
            x2 = max(x1 + 16, 2 + (w - 4) * self.hi)
            rrect(self, x1, 2, x2, h - 2, (h - 4) // 2, fill="#8a96a8")
            rrect(self, x1 + 2, 4, x2 - 3, h - 5, (h - 8) // 2, fill="#b8c2d0")
            return
        rrect(self, 2, 2, w - 2, h - 2, (w - 4) // 2, fill="#d8dde4")
        y1 = 2 + (h - 4) * self.lo
        y2 = max(y1 + 16, 2 + (h - 4) * self.hi)
        rrect(self, 2, y1, w - 2, y2, (w - 4) // 2, fill="#8a96a8")
        rrect(self, 4, y1 + 2, w - 5, y2 - 3, (w - 8) // 2, fill="#b8c2d0")

    def _len(self):
        return max(1, self.winfo_width() if self.horiz else self.winfo_height())

    def _goto(self, f):
        if self.horiz:
            self.target.xview_moveto(max(0.0, f))
        else:
            self.target.yview_moveto(max(0.0, f))

    def _press(self, e):
        p = (e.x if self.horiz else e.y) / float(self._len())
        if self.lo <= p <= self.hi:
            self._drag = (e.x if self.horiz else e.y, self.lo)
        else:
            self._goto(p - (self.hi - self.lo) / 2)

    def _move(self, e):
        if not self._drag:
            return
        p0, lo0 = self._drag
        self._goto(lo0 + ((e.x if self.horiz else e.y) - p0) / float(self._len()))


# ---------------------------------------------------------------- 입력칸
def entry(parent, var, width=12):
    """DP 의 흰 입력칸 (회색 테두리, 고르면 빨간 테두리). (테두리 틀, Entry)."""
    box = tk.Frame(parent, bg="#ffffff", highlightthickness=2, highlightbackground="#a8b0bc",
                   highlightcolor="#e83030", bd=0)
    e = tk.Entry(box, textvariable=var, bg="#ffffff", fg=INK, insertbackground=INK, relief="flat", bd=0,
                 font=font(11), highlightthickness=0, width=width)
    e.pack(fill="both", expand=True, padx=6, pady=2)
    e.bind("<FocusIn>", lambda _e: box.configure(highlightbackground="#e83030"))
    e.bind("<FocusOut>", lambda _e: box.configure(highlightbackground="#a8b0bc"))
    box.entry = e
    return box


# ---------------------------------------------------------------- v2 부품 (단순 · 잘 보임)
# 화면들은 이 다섯 가지로만 꾸민다: 판(panel) · 단락 꼬리표(tag) · 빨간 커서(cursor) · 탭 줄(tabs) · 글상자(msgbox).
# 바탕 무늬 · 그림자 글씨 · 테두리 글씨는 쓰지 않는다.
def panel(cv, x1, y1, x2, y2, strong=False, fill=None, tags=()):
    """흰 판. strong 이면 진한 테(지금 손대는 판 · 글상자), 아니면 옅은 테."""
    from . import LINE, LINE_D, LINE_K, PANEL
    return rrect(cv, x1, y1, x2, y2, 8, fill=fill or PANEL, outline=LINE_D if strong else LINE,
                 width=max(1, int(round((2 if strong else 1) * LINE_K))), tags=tags)


def tag(cv, x, y, s, tags=(), spec=None, fill=None):
    """단락 꼬리표: 파란 둥근 띠에 흰 글씨. (x, y) = 왼쪽 위. (폭, 높이)."""
    from . import TAGC
    spec = spec or font(10)
    f = tkfont_of(cv, spec)
    w = f.measure(s) + U.h(16)
    h = f.metrics("linespace") + U.h(6)
    rrect(cv, x, y, x + w, y + h, 5, fill=fill or TAGC, tags=tags)
    cv.create_text(x + w // 2, y + h // 2, text=s, fill="#ffffff", font=spec, anchor="center", tags=tags)
    return w, h


def cursor(cv, x, ym, size=None, tags=()):
    """DP 의 빨간 화살표 커서 (▶). x 가 왼쪽 끝, ym 이 세로 가운데."""
    s = size or U.h(6)
    return cv.create_polygon(x, ym - s, x + s + 2, ym, x, ym + s, fill=CUR, outline="", tags=tags)


def tabs(cv, x, y, h, items, current, tag_prefix, spec=None, align="left", hover=None, tags=()):
    """탭 줄: 고른 탭은 빨간 글씨 + 빨간 밑줄, 나머지는 회색 글씨 (올리면 옅은 바탕).
    items = [(열쇠, 글)]. 누르기는 부르는 쪽이 'tag_prefix + 열쇠' 꼬리표로 받는다. 그린 칸들 [(열쇠, 상자)]."""
    from . import HOV, INK2
    spec = spec or font(10)
    f = tkfont_of(cv, spec)
    pad = U.h(10)
    ws = [f.measure(lb) + 2 * pad for _k, lb in items]
    if align == "right":
        x -= sum(ws)
    out = []
    for (key, lb), w in zip(items, ws):
        tg = tuple(tags) + (tag_prefix + str(key), tag_prefix)
        on = key == current
        if hover == key and not on:
            rrect(cv, x + 1, y + 1, x + w - 1, y + h - 1, 5, fill=HOV, tags=tg)
        else:
            cv.create_rectangle(x, y, x + w, y + h, fill="", outline="", tags=tg)    # 누를 자리
        cv.create_text(x + w // 2, y + h // 2 - 1, text=lb, fill=CUR if on else INK2, font=spec, anchor="center",
                       tags=tg)
        if on:
            cv.create_rectangle(x + pad // 2, y + h - 3, x + w - pad // 2, y + h, fill=CUR, outline="", tags=tg)
        out.append((key, (x, y, x + w, y + h)))
        x += w
    return out


def msgbox(cv, x1, y1, x2, y2, s, color=None, tags=()):
    """DP 글상자 (한두 줄 알림): 흰 바탕 · 진한 테 · 글자. 글자 id."""
    panel(cv, x1, y1, x2, y2, strong=True, tags=tags)
    return text(cv, x1 + U.h(12), (y1 + y2) // 2, s or "", font(11), fill=color or INK, anchor="w",
                width=max(40, x2 - x1 - U.h(24)), tags=tags)[1]
