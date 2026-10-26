# -*- coding: utf-8 -*-
"""플라티나 화면들이 같이 쓰는 그리기 부품 (시안 B 의 CSS 를 캔버스로 옮긴 것).

    steel        강철 바탕 - 세로 그라데이션 + 10px 마다 옅은 흰 점 (그림 한 장으로 깐다)
    head_band    머리 띠 - 그라데이션 + 아래 3px 진한 줄
    panel        옅은 회색 판 - 3px 진한 테 · 둥근 16 · 안쪽 위 흰 빛 줄
    capsule      위가 밝은 입체 캡슐 (빛깔 이름: orange · white · cyan · red · green · blue · purple · off)
    seg          고르기 줄 - 회색 홈 안에 고른 것만 흰 알약
    row_capsule  목록 한 줄 - 흰 캡슐, 고르면 하늘색 테 + 빛 고리
    money        진한 캡슐에 흰 글씨 (돈 · 개수)
    Capsule      kit.CButton 을 캡슐로 그리는 단추 (configure · invoke 는 같다)
    entry        테 없는 입력칸 - 캔버스에 그린 흰 캡슐 안에 올린다

모서리 반지름은 이 파일이 **그대로** 쓴다 (kit.rrect 는 테마의 RADIUS_K 를 곱한다 - 시안 값을 그대로 옮기려고
여기서는 kit._round_pts 로 직접 그린다). 글씨는 늘 단색 위에 둔다 (점 무늬 위에 두지 않는다).
"""
import tkinter as tk

from PIL import Image, ImageTk

from ... import ui_common as U
from ..dp import kit as K
from ..dp import font
from . import (BAR1, BAR2, BAR_SH, BLUE, BLUE_LINE, BLUE_TOP, BTN_BOT, BTN_TOP, CYAN, CYAN_INK, CYAN_TOP,
               GLOW, GREEN, GREEN_LINE, GREEN_TOP, INK, LINE2, ORANGE, ORANGE_LINE, ORANGE_TOP, PANEL, PANEL_HI,
               PURPLE, PURPLE_SH, PURPLE_TOP, RED, RED_LINE, RED_TOP, RIM, SEG, STEEL1, STEEL2, WHITE)

# 캡슐 빛깔: (위, 아래, 테, 글자, 글자 그림자 또는 None)
LOOKS = {
    "orange": (ORANGE_TOP, ORANGE, ORANGE_LINE, WHITE, "#9a4410"),
    "white": (BTN_TOP, BTN_BOT, RIM, INK, None),
    "cyan": (CYAN_TOP, CYAN, RIM, CYAN_INK, None),
    "red": (RED_TOP, RED, RED_LINE, WHITE, "#8a2a20"),
    "green": (GREEN_TOP, GREEN, GREEN_LINE, WHITE, "#1c5e2c"),
    "blue": (BLUE_TOP, BLUE, BLUE_LINE, WHITE, "#1c3c7a"),
    "purple": (PURPLE_TOP, PURPLE, PURPLE_SH, WHITE, PURPLE_SH),
    "off": ("#e2e6ea", "#cfd4da", "#9aa3ad", "#8a929c", None),
}
# DP 단추 이름 -> 캡슐 빛깔 (기본 · DP 코드가 만든 단추를 그대로 받는다)
KIND_OF = {"blue": "orange", "gray": "white", "red": "red"}


def _rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(ra, rb))


# ---------------------------------------------------------------- 모양
def rpoly(cv, x1, y1, x2, y2, r, fill="", outline="", width=1, tags=()):
    """둥근 네모 (반지름을 그대로)."""
    return cv.create_polygon(K._round_pts(x1, y1, x2, y2, r), fill=fill, outline=outline,
                             width=width if outline else 0, tags=tags)


def _inset(y, y1, y2, r):
    """둥근 네모의 y 줄에서 양옆이 들어간 만큼."""
    import math
    if y < y1 + r:
        d = y1 + r - y
    elif y > y2 - r:
        d = y - (y2 - r)
    else:
        return 0
    return r - math.sqrt(max(0.0, r * r - d * d))


def grad_round(cv, x1, y1, x2, y2, r, top, bot, tags=(), band=2):
    """위에서 아래로 번지는 빛깔의 둥근 네모 (가로띠를 모양에 맞게 잘라 깐다)."""
    h = max(1, y2 - y1)
    r = max(0, min(r, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    y = y1
    while y < y2:
        yy = min(y2, y + band)
        d = max(_inset(y, y1, y2, r), _inset(yy, y1, y2, r))
        cv.create_rectangle(x1 + d, y, x2 - d, yy, fill=mix(top, bot, (y - y1) / float(h)), outline="", tags=tags)
        y = yy


def gradient(cv, x1, y1, x2, y2, top, bot, tags=(), band=3):
    h = max(1, y2 - y1)
    y = y1
    while y < y2:
        cv.create_rectangle(x1, y, x2, min(y2, y + band), fill=mix(top, bot, (y - y1) / float(h)), outline="",
                            tags=tags)
        y += band


# ---------------------------------------------------------------- 강철 바탕
_STEEL = {}


def steel_photo(w, h):
    """강철 바탕 그림 (세로 그라데이션 + 10px 점). 크기마다 한 번 만든다."""
    w, h = max(1, int(w)), max(1, int(h))
    key = (w, h)
    ph = _STEEL.get(key)
    if ph is not None:
        return ph
    from PIL import ImageDraw
    a, b = _rgb(STEEL1), _rgb(STEEL2)
    col = Image.new("RGB", (1, h))
    col.putdata([tuple(int(round(p + (q - p) * y / float(max(1, h - 1)))) for p, q in zip(a, b)) for y in range(h)])
    im = col.resize((w, h), Image.NEAREST)
    step = max(6, U.h(10))
    dot = max(1, U.h(1))
    mid = tuple((p + q) // 2 for p, q in zip(a, b))
    c = tuple(int(round(v + (255 - v) * 0.09)) for v in mid)
    d = ImageDraw.Draw(im)
    for y in range(step // 2, h, step):
        for x in range(step // 2, w, step):
            d.rectangle((x, y, x + dot - 1, y + dot - 1), fill=c)
    if len(_STEEL) > 24:
        _STEEL.clear()
    ph = ImageTk.PhotoImage(im)
    _STEEL[key] = ph
    return ph


def steel(cv, x1, y1, x2, y2, tags=()):
    """판 바깥의 강철 바탕 (그 칸 크기의 그림 한 장)."""
    ph = steel_photo(x2 - x1, y2 - y1)
    return cv.create_image(x1, y1, image=ph, anchor="nw", tags=tags)


def head_band(cv, x1, y1, x2, y2, tags=()):
    """시안의 머리 띠: #5b6676 → #465060, 아래 3px 진한 줄."""
    gradient(cv, x1, y1, x2, y2 - 3, BAR1, BAR2, tags=tags)
    cv.create_rectangle(x1, y2 - 3, x2, y2, fill=RIM, outline="", tags=tags)


def band_title(cv, x, y, s, spec, anchor="w", tags=()):
    """머리 띠 위의 흰 제목 (아래로 2px 진한 그림자)."""
    cv.create_text(x, y + 2, text=s, fill=BAR_SH, font=spec, anchor=anchor, tags=tags)
    return cv.create_text(x, y, text=s, fill=WHITE, font=spec, anchor=anchor, tags=tags)


# ---------------------------------------------------------------- 판
def panel(cv, x1, y1, x2, y2, r=16, fill=PANEL, rim=RIM, w=3, tags=()):
    """옅은 회색 판: 진한 테 · 둥근 · 안쪽 위의 흰 빛 줄."""
    rpoly(cv, x1, y1, x2, y2, r, fill=rim, tags=tags)
    rpoly(cv, x1 + w, y1 + w, x2 - w, y2 - w, max(0, r - w), fill=fill, tags=tags)
    rr = max(0, r - w)
    cv.create_line(x1 + w + rr * 0.7, y1 + w + 1, x2 - w - rr * 0.7, y1 + w + 1, fill=PANEL_HI, width=2, tags=tags)


def money(cv, x2, ym, s, spec=None, tags=()):
    """진한 캡슐에 흰 글씨 - 오른쪽 끝이 x2. (왼쪽 x)."""
    spec = spec or font(12)
    f = K.tkfont_of(cv, spec)
    h = f.metrics("linespace") + U.h(8)
    w = f.measure(s) + U.h(28)
    rpoly(cv, x2 - w, ym - h // 2, x2, ym + h // 2, h // 2, fill=BAR_SH, tags=tags)
    cv.create_text(x2 - w // 2, ym, text=s, fill=WHITE, font=spec, anchor="center", tags=tags)
    return x2 - w


def capsule(cv, x1, y1, x2, y2, look="white", text="", spec=None, r=None, rim_w=3, tags=(), hover=False,
            lines=None):
    """입체 캡슐: 진한 테 + 위가 밝은 그라데이션 + 위쪽 흰 빛 줄 + 글씨. 글자 id."""
    top, bot, rim, ink, sh = LOOKS.get(look, LOOKS["white"])
    if hover and look != "off":
        top, bot = mix(top, WHITE, 0.25), mix(bot, WHITE, 0.18)
    h = y2 - y1
    r = h // 2 if r is None else r
    rpoly(cv, x1, y1, x2, y2, r, fill=rim, tags=tags)
    e = rim_w
    grad_round(cv, x1 + e, y1 + e, x2 - e, y2 - e, max(0, r - e), top, bot, tags=tags)
    # 위쪽 흰 빛 줄 (inset 0 3px 0 rgba(255,255,255,.35))
    if look != "off":
        rr = max(0, r - e)
        cv.create_line(x1 + e + rr * 0.8, y1 + e + 2, x2 - e - rr * 0.8, y1 + e + 2, fill=mix(top, WHITE, 0.45),
                       width=2, tags=tags)
    if not text:
        return None
    spec = spec or font(12)
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    if sh:
        cv.create_text(cx, cy + 2, text=text, fill=sh, font=spec, anchor="center", justify="center", tags=tags)
    return cv.create_text(cx, cy, text=text, fill=ink, font=spec, anchor="center", justify="center", tags=tags)


def glow(cv, x1, y1, x2, y2, r, tags=()):
    """고른 것의 하늘색 빛 고리 (box-shadow 0 0 0 3px rgba(47,187,230,.35))."""
    g = U.h(3)
    rpoly(cv, x1 - g, y1 - g, x2 + g, y2 + g, r + g, fill="", outline=GLOW, width=g, tags=tags)


def seg(cv, x, y, w, h, items, current, tag, on_pick, spec=None, hover=None):
    """고르기 줄 (시안의 .seg): 회색 홈 안에 고른 것만 흰 알약. 칸 폭은 고르게. [(열쇠, 상자)]."""
    spec = spec or font(10)
    tg = ("scene", tag) if tag else ("scene",)
    rpoly(cv, x, y, x + w, y + h, h // 2, fill=SEG, tags=tg)
    n = max(1, len(items))
    p = U.h(3)
    cw = (w - 2 * p - (n - 1) * p) / float(n)
    out = []
    for i, (key, lb) in enumerate(items):
        x1 = x + p + i * (cw + p)
        x2 = x1 + cw
        t = tg + ("%s_%s" % (tag, key or "_"),) if tag else tg
        on = key == current
        if on:
            rpoly(cv, x1, y + p + 1, x2, y + h - p + 1, (h - 2 * p) // 2, fill=LINE2, tags=t)
            rpoly(cv, x1, y + p, x2, y + h - p, (h - 2 * p) // 2, fill=WHITE, tags=t)
        elif hover == key:
            rpoly(cv, x1, y + p, x2, y + h - p, (h - 2 * p) // 2, fill="#d6dce3", tags=t)
        else:
            cv.create_rectangle(x1, y + p, x2, y + h - p, fill="", outline="", tags=t)
        cv.create_text((x1 + x2) / 2.0, y + h / 2.0, text=lb, fill=INK, font=spec, anchor="center", tags=t)
        if tag and on_pick is not None:
            cv.tag_bind("%s_%s" % (tag, key or "_"), "<Button-1>", lambda _e, k=key: on_pick(k))
        out.append((key, (x1, y, x2, y + h)))
    return out


def seg_width(cv, items, spec=None, pad=None):
    """seg 가 글씨를 다 담는 최소 폭 (칸은 고르게 나누므로 가장 긴 글씨 기준)."""
    spec = spec or font(10)
    f = K.tkfont_of(cv, spec)
    p = U.h(3)
    pad = U.h(20) if pad is None else pad
    cw = max([f.measure(lb) for _k, lb in items] or [0]) + pad
    return int(cw * len(items) + p * (len(items) + 1))


def row_capsule(cv, x1, y1, x2, y2, sel=False, hover=False, fill=WHITE, tags=()):
    """목록 한 줄의 흰 캡슐 (시안의 .cap2): 2px 테, 고르면 하늘색 테 + 빛 고리."""
    r = (y2 - y1) // 2
    if sel:
        glow(cv, x1, y1, x2, y2, r, tags=tags)
    line = CYAN if sel else ("#9fb0c0" if hover else SEG)
    rpoly(cv, x1, y1, x2, y2, r, fill=line, tags=tags)
    rpoly(cv, x1 + 2, y1 + 2, x2 - 2, y2 - 2, max(0, r - 2), fill=fill, tags=tags)


# ---------------------------------------------------------------- 단추
class Capsule(K.CButton):
    """kit.CButton 을 캡슐로 그린다. 올리면 밝아지고, 누르면 2px 내려앉는다 (도형을 지우지 않고 옮긴다)."""

    LOOK = None

    def _look(self):
        if not self.enabled:
            return "off"
        return self.LOOK or KIND_OF.get(self.kind, self.kind)

    def draw(self):
        cv = self.cv
        cv.delete(self.tag)
        self._body_id = None
        self._shift = 0
        self._hover = self._down = False
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        m = (self.tag, self.tag + "_m")
        look = self._look()
        # 바닥 그늘 (box-shadow 0 4px 0) - 누르면 몸이 그 위로 내려앉는다
        sh = LOOKS[look][2]
        rpoly(cv, x1, y1 + 3, x2, y2, (y2 - y1 - 3) // 2, fill=sh, tags=(self.tag,))
        self._hl = self.tag + "_hl"
        capsule(cv, x1, y1, x2, y2 - 3, look, self.text, self.spec, tags=m)
        # 올렸을 때 두르는 하늘색 빛 고리 (평소엔 숨김 - 글씨를 덮지 않는 테만)
        g = U.h(3)
        self._body_id = rpoly(cv, x1 - g, y1 - g, x2 + g, y2 - 3 + g, (y2 - 3 - y1) // 2 + g, fill="",
                              outline=GLOW, width=g, tags=m)
        cv.itemconfigure(self._body_id, state="hidden")
        self._state()

    def _state(self):
        if self._body_id is None:
            return
        try:
            self.cv.itemconfigure(self._body_id,
                                  state="normal" if (self._hover and self.enabled and not self._down) else "hidden")
            want = 2 if (self._down and self.enabled) else 0
            if want != self._shift:
                self.cv.move(self.tag + "_m", 0, want - self._shift)
                self._shift = want
        except tk.TclError:
            pass


def to_capsule(btn, look=None):
    """DP 코드가 만든 kit.CButton 을 그 자리에서 캡슐 단추로 바꾼다 (만든 뒤 한 번). look 을 주면 그 빛깔."""
    if btn is None:
        return btn
    btn.__class__ = Capsule
    if look:
        btn.LOOK = look
    btn._body_id = None
    if btn.box:
        btn.draw()
    return btn


# ---------------------------------------------------------------- 입력칸
class Entry(tk.Frame):
    """테 없는 흰 입력칸 - 캔버스에 그린 흰 캡슐 안에 올린다 (kit.entry 와 같게 .entry 를 갖는다)."""

    def __init__(self, parent, var, width=12):
        tk.Frame.__init__(self, parent, bg=WHITE, highlightthickness=0, bd=0)
        self.entry = tk.Entry(self, textvariable=var, bg=WHITE, fg=INK, insertbackground=INK, relief="flat", bd=0,
                              font=font(11), highlightthickness=0, width=width)
        self.entry.pack(fill="both", expand=True)


def entry_capsule(win, cv, key, widget, x, y, w, h, label=None, tags=("scene",)):
    """흰 캡슐(2px 테)을 그리고 그 안에 입력칸을 올린다. label 이 있으면 캡슐 안 왼쪽에 흐린 글씨."""
    rpoly(cv, x, y, x + w, y + h, h // 2, fill=LINE2, tags=tags)
    rpoly(cv, x + 2, y + 2, x + w - 2, y + h - 2, h // 2 - 2, fill=WHITE, tags=tags)
    ex = x + h // 2
    if label:
        cv.create_text(ex, y + h // 2, text=label, fill="#8a929c", font=font(10), anchor="w", tags=tags)
        ex += K.tkfont_of(cv, font(10)).measure(label) + U.h(8)
    win._place(key, widget, ex, y + 3, max(10, x + w - h // 2 - ex), h - 6)
