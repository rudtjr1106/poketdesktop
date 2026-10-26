# -*- coding: utf-8 -*-
"""소드·실드 테마의 그리기 조각 - 시안 K (concepts.html '.k') 의 바탕 · 칸 · 알약 · 단추.

    backdrop     남색 빗금 바탕 (135° 24px 띠: #1c1f3d / #272b55) + 왼쪽 위 하늘색 · 오른쪽 아래 분홍 모서리
                 (시안: linear-gradient(135deg, cyan 0 13%, … mag 87% 100%) - 모서리 꼭짓점에서 x + y 가 13% 안쪽)
    card         흰 판 .pn: 남색 바깥 테 3 · 흰 테 4 · #f6f7fb 판 (r 14)
    pill         알약 .tabs span: 흰 바탕 · 남색 글씨, 고른 것은 분홍 바탕 · 흰 글씨 (r 16)
    seg          같은 폭 알약 줄 .seg: 옅은 남회색 · 흐린 글씨, 고른 것은 분홍
    field        찾기 칸 .find: 옅은 남회색 둥근 칸 + 앞의 흐린 글 (입력칸 위젯은 그 위에 같은 빛깔로 올린다)
    SwButton     큰 단추 .go: 분홍 · 흰 테 3 · 남색 바깥 테 3 (kit.CButton 과 같은 말을 받는다)

빗금은 판 바깥 바탕에만 깐다 - 글은 늘 단색 판 · 알약 위에 놓는다.
"""
import tkinter as tk

from ... import ui_common as U
from ..dp import font
from ..dp import kit as K
from . import CYAN, DIMK, MAG, MAG_HI, NAVY, NAVY2, NAVY3, PAPER, PAPER2

STRIPE = 34                  # 빗금 띠의 가로 폭 (시안 24px 띠를 135° 로 - 가로로 재면 24·√2)
CORNER = 0.045               # 모서리 빛깔이 차지하는 몫 (시안은 13% - 눈이 아파 작게, 2026-10-26 사용자)

# 눈이 편하게 (2026-10-26 사용자: "배경이 눈아프다"). 시안의 빗금 #1c1f3d / #272b55 · 쨍한 하늘 · 분홍 모서리는
# 너무 세다 - 빗금은 바탕과 거의 같은 빛깔로 결만 남기고, 모서리는 작고 남색에 섞은 빛깔로. 판 · 글 · 도트가 먼저 보인다.
BAND = "#20234a"             # 빗금의 짙은 띠 (바탕 #1c1f3d 와 아주 조금만 다르다)
CYAN_SOFT = "#1f6896"        # 모서리 하늘색 (CYAN 을 남색에 반쯤 섞음)
MAG_SOFT = "#83245f"         # 모서리 분홍 (MAG 을 남색에 반쯤 섞음)


def stripes(cv, x1, y1, x2, y2, phase=0, tags=()):
    """남색 빗금 (옅게). phase = 이 칸이 큰 바탕에서 놓인 자리 (x + y) - 여러 캔버스에 나눠 그려도 띠가 이어진다."""
    cv.create_rectangle(x1, y1, x2, y2, fill=NAVY, outline="", tags=tags)
    step = U.h(STRIPE)
    w, h = x2 - x1, y2 - y1
    # 띠 i: (x + y + phase) 가 [2i·step, 2i·step + step) 인 곳 - 기울기 -1 의 평행 띠 ('/' 방향)
    start = -((phase % (2 * step)) + 2 * step)
    k = start
    while k < w + h:
        a, b = k + step, k + 2 * step               # (앞 step 은 바탕 남색, 뒤 step 이 짙은 띠)
        poly = [(a, 0), (b, 0), (b - h, h), (a - h, h)]
        clip = K._clip_poly(poly, 0, 0, w, h)
        if len(clip) >= 3:
            flat = []
            for px, py in clip:
                flat += [x1 + px, y1 + py]
            cv.create_polygon(flat, fill=BAND, outline="", tags=tags)
        k += 2 * step


def corner(cv, x, y, leg, where, tags=()):
    """모서리 삼각형 (남색에 섞은 옅은 빛깔). where='tl' 이면 (x, y) 가 왼쪽 위 꼭짓점 (하늘색),
    'br' 이면 오른쪽 아래 꼭짓점 (분홍)."""
    if leg <= 0:
        return
    if where == "tl":
        cv.create_polygon(x, y, x + leg, y, x, y + leg, fill=CYAN_SOFT, outline="", tags=tags)
    else:
        cv.create_polygon(x, y, x - leg, y, x, y - leg, fill=MAG_SOFT, outline="", tags=tags)


def calm(cv, x1, y1, x2, y2, tags=()):
    """빗금 없는 남색 바탕 (배틀 장면 · 아래 칸 - 도트 · 이름표 · 기술이 먼저 보이게)."""
    cv.create_rectangle(x1, y1, x2, y2, fill=NAVY, outline="", tags=tags)


def backdrop(cv, x1, y1, x2, y2, phase=0, tl=None, br=None, tags=()):
    """시안 바탕 한 장: 빗금 + 모서리. tl · br = 모서리 다리 길이 (None 이면 시안 비율, 0 이면 없음)."""
    stripes(cv, x1, y1, x2, y2, phase, tags)
    leg = int(CORNER * ((x2 - x1) + (y2 - y1)))
    corner(cv, x1, y1, leg if tl is None else tl, "tl", tags)
    corner(cv, x2, y2, leg if br is None else br, "br", tags)


def card(cv, x1, y1, x2, y2, fill=PAPER, r=14, tags=()):
    """흰 판 (.pn): 남색 바깥 테 3 + 흰 테 4 + 판. (x1..x2) 가 흰 테의 바깥 - 남색 테는 그 바깥에 두른다."""
    g, b = U.h(3), U.h(4)
    K.rrect(cv, x1 - g, y1 - g, x2 + g, y2 + g, r + 3, fill=NAVY, tags=tags)
    K.rrect(cv, x1, y1, x2, y2, r, fill="#ffffff", tags=tags)
    K.rrect(cv, x1 + b, y1 + b, x2 - b, y2 - b, max(2, r - 4), fill=fill, tags=tags)


def pill_w(cv, text, spec, pad=None, icon=None):
    pad = U.h(12) if pad is None else pad
    iw = (icon.width() + U.h(6)) if icon is not None else 0
    return K.tkfont_of(cv, spec).measure(text) + iw + 2 * pad


def pill(cv, x1, y1, x2, y2, text, on=False, hover=False, spec=None, tags=(), icon=None, off_fill="#ffffff",
         off_ink=NAVY, ring=None, dim=False):
    """알약 하나 (.tabs span). on = 분홍 바탕 · 흰 글씨, 아니면 흰 바탕 · 남색 글씨 (올리면 옅은 분홍 테)."""
    spec = spec or font(10)
    h = y2 - y1
    if on:
        K.rrect(cv, x1, y1, x2, y2, h // 2, fill=MAG, tags=tags)
        ink = "#ffffff"
    else:
        K.rrect(cv, x1, y1, x2, y2, h // 2, fill=off_fill, outline=(ring or (MAG_HI if hover else "")),
                width=max(2, U.h(2)) if (ring or hover) else 1, tags=tags)
        ink = DIMK if dim else off_ink
    cx = (x1 + x2) // 2
    if icon is not None:
        tw = K.tkfont_of(cv, spec).measure(text)
        iw = icon.width() + U.h(6)
        sx = cx - (iw + tw) // 2
        cv.create_image(sx + icon.width() // 2, (y1 + y2) // 2, image=icon, tags=tags)
        cv.create_text(sx + iw, (y1 + y2) // 2, text=text, fill=ink, font=spec, anchor="w", tags=tags)
    else:
        cv.create_text(cx, (y1 + y2) // 2, text=text, fill=ink, font=spec, anchor="center", tags=tags)


def seg(cv, x1, y, x2, h, items, current, tag, on_pick, spec=None, hand=None):
    """같은 폭 알약 줄 (.seg): 옅은 남회색 · 흐린 글씨, 고른 것은 분홍 · 흰 글씨 (r 10). 그린 칸들 [(열쇠, 상자)]."""
    spec = spec or font(10)
    n = max(1, len(items))
    gap = U.h(5)
    w = (x2 - x1 - gap * (n - 1)) / float(n)
    out = []
    for i, (key, lb) in enumerate(items):
        a = int(x1 + i * (w + gap))
        b = int(x1 + i * (w + gap) + w)
        on = key == current
        tg = ("scene", tag, "%s_%s" % (tag, key or "_"))
        K.rrect(cv, a, y, b, y + h, U.h(7), fill=MAG if on else PAPER2, tags=tg)
        cv.create_text((a + b) // 2, y + h // 2, text=lb, fill="#ffffff" if on else DIMK, font=spec,
                       anchor="center", tags=tg)
        cv.tag_bind("%s_%s" % (tag, key or "_"), "<Button-1>", lambda _e, k=key: on_pick(k))
        out.append((key, (a, y, b, y + h)))
    if hand is not None:
        hand(tag)
    return out


def field(cv, x1, y1, x2, y2, label, tags=()):
    """찾기 칸 (.find): 옅은 남회색 둥근 칸 + 앞의 흐린 글. 입력칸 위젯을 올릴 x (글 다음)를 돌려준다."""
    K.rrect(cv, x1, y1, x2, y2, U.h(7), fill=PAPER2, tags=tags)
    tx = x1 + U.h(12)
    if label:
        cv.create_text(tx, (y1 + y2) // 2, text=label, fill=DIMK, font=font(10), anchor="w", tags=tags)
        tx += K.tkfont_of(cv, font(10)).measure(label) + U.h(8)
    return tx


def flat_entry(box):
    """kit.entry 가 만든 입력칸을 찾기 칸 빛깔로 (테 없이, 고르면 분홍 밑줄 대신 글자 빛깔만)."""
    try:
        box.configure(bg=PAPER2, highlightthickness=0)
        box.entry.configure(bg=PAPER2, fg=NAVY, insertbackground=NAVY, readonlybackground=PAPER2)
    except tk.TclError:
        pass
    return box


def paper_list(vl):
    """kit.VList 의 바탕을 판 빛깔로 (목록 · 스크롤 막대)."""
    for w in (vl.frame, vl.cv, vl.sb):
        if w is not None:
            try:
                w.configure(bg=PAPER)
            except tk.TclError:
                pass
    return vl


def chip(cv, x, y, text, fill=MAG, ink="#ffffff", spec=None, tags=()):
    """꼬리표 (.chip): 분홍 둥근 띠에 흰 글씨. (x, y) = 왼쪽 위. (폭, 높이)."""
    spec = spec or font(9)
    f = K.tkfont_of(cv, spec)
    w = f.measure(text) + U.h(16)
    h = f.metrics("linespace") + U.h(4)
    K.rrect(cv, x, y, x + w, y + h, U.h(5), fill=fill, tags=tags)
    cv.create_text(x + w // 2, y + h // 2, text=text, fill=ink, font=spec, anchor="center", tags=tags)
    return w, h


# ---------------------------------------------------------------- 단추
LOOKS = {
    # (몸, 올렸을 때, 글자, 흰 테를 두르나)
    "go": (MAG, MAG_HI, "#ffffff", True),         # 주된 일 (.go)
    "white": ("#ffffff", "#fde8f2", NAVY, False),  # 흰 알약 (남색 바깥 테만)
    "navy": (NAVY2, NAVY3, "#ffffff", True),       # 남색 알약 · 흰 테 (.money)
    "red": ("#d33a3a", "#e25656", "#ffffff", True),   # (kit 의 빨강 #d8463e 는 이 테마에서 분홍으로 옮겨진다)
    "off": ("#d9dbe8", "#d9dbe8", "#9a9fc0", False),
}


class SwButton(K.CButton):
    """시안의 단추 - 남색 바깥 테 + (흰 테) + 몸 + 글씨. 동작 · 말은 kit.CButton 그대로 (올림 · 누름은 지우지 않고 칠만)."""

    def __init__(self, cv, text, command, kind="go", spec=None, tag=None):
        K.CButton.__init__(self, cv, text, command, kind, spec, tag)

    def draw(self):
        cv = self.cv
        cv.delete(self.tag)
        self._body_id = None
        self._shift = 0
        self._hover = self._down = False
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        body, _hi, ink, white = LOOKS["off" if not self.enabled else self.kind]
        m = (self.tag, self.tag + "_m")
        g = U.h(3)
        r = (y2 - y1) // 2
        K.rrect(cv, x1, y1, x2, y2, r, fill=NAVY, tags=(self.tag,))                        # 남색 바깥 테
        if white:
            K.rrect(cv, x1 + g, y1 + g, x2 - g, y2 - g, r - g, fill="#ffffff", tags=m)     # 흰 테
            self._body_id = K.rrect(cv, x1 + 2 * g, y1 + 2 * g, x2 - 2 * g, y2 - 2 * g, r - 2 * g, fill=body, tags=m)
        else:
            self._body_id = K.rrect(cv, x1 + g, y1 + g, x2 - g, y2 - g, r - g, fill=body, tags=m)
        cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=self.text, fill=ink, font=self.spec, anchor="center",
                       tags=m)
        self._state()

    def _state(self):
        if self._body_id is None:
            return
        body, hi, _ink, _w = LOOKS["off" if not self.enabled else self.kind]
        try:
            self.cv.itemconfigure(self._body_id, fill=hi if (self._hover and self.enabled) else body)
            want = 1 if (self._down and self.enabled) else 0
            if want != self._shift:
                self.cv.move(self.tag + "_m", 0, want - self._shift)
                self._shift = want
        except tk.TclError:
            pass


def restyle(btn, kind):
    """DP 가 만든 kit.CButton 을 시안 단추로 (같은 물건 - 동작 · 바인딩 그대로)."""
    btn.__class__ = SwButton
    btn.kind = kind
    if btn.box:
        btn.draw()
    return btn

