# -*- coding: utf-8 -*-
"""에메랄드 테마의 그리기 부품 - 시안 A 의 GBA 창 (concepts.html 의 .a .fr · .pocket · .sorts · .btn).

    frame      GBA 창: 남색 테(4px) + 안쪽 옅은 하늘빛 줄(3px) + 종이 바탕, 모서리 4px 깎음
    stripes    청록 빗금 바탕 (판 바깥에만 - 글 밑에 깔지 않는다)
    header     빨간 머리 띠 '◀ 글 ▶' (가방의 주머니 띠 · 허브의 고른 탭)
    sort_box   줄 세우기 칸 (흰 바탕 · 남색 2px 테, 고른 것 = 남색 바탕 흰 글씨)
    cursor     빨간 ▶
    patch_kit  DP 부품(kit)을 이 모양으로 바꿔 끼운다 - DP 배치 그대로인 화면들(길드 · 게시판 · 박스 …)도
               판 · 글상자 · 단추 · 입력칸이 GBA 창이 된다. widgets.install 이 처음 한 번 부른다.

DP 파일은 고치지 않는다 - 에메랄드 테마로 켰을 때만 이 모듈이 읽혀서 바꿔 끼운다.
"""
import tkinter as tk

from ... import ui_common as U
from . import BG1, BG2, GRP, LIGHT, NAVY, NAVY_HI, NAVY_LO, PAPER, RED, RED_D, SELY

SHADOW = "#a9adb4"        # 큰 단추 그늘 (시안: rgba(40,48,72,.35) 을 종이 위에 편 빛)
OFF_FILL, OFF_LINE, OFF_INK = "#e4e4dc", "#a0a4a8", "#8c949c"


def chamfer(x1, y1, x2, y2, c):
    """모서리를 c 만큼 깎은 네모의 점 (시안의 clip-path)."""
    c = max(0, min(c, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    return [x1 + c, y1, x2 - c, y1, x2, y1 + c, x2, y2 - c, x2 - c, y2, x1 + c, y2, x1, y2 - c, x1, y1 + c]


def frame(cv, x1, y1, x2, y2, fill=PAPER, bw=None, inner=True, line=NAVY, tags=(), s=None):
    """GBA 창 하나. bw = 남색 테 두께 (기본 4px), inner = 안쪽 옅은 하늘빛 줄. 바탕 도형 id."""
    s = s or U.h
    b = bw if bw is not None else max(3, s(4))
    cv.create_polygon(chamfer(x1, y1, x2, y2, b), fill=line, outline="", tags=tags)
    if inner:
        i = max(2, s(3))
        cv.create_polygon(chamfer(x1 + b, y1 + b, x2 - b, y2 - b, 0), fill=LIGHT, outline="", tags=tags)
        return cv.create_polygon(chamfer(x1 + b + i, y1 + b + i, x2 - b - i, y2 - b - i, 0), fill=fill, outline="",
                                 tags=tags)
    return cv.create_polygon(chamfer(x1 + b, y1 + b, x2 - b, y2 - b, 0), fill=fill, outline="", tags=tags)


def inset(bw=None, inner=True, s=None):
    """frame 의 테 + 안쪽 줄 두께 (글을 그 안쪽에 둘 때)."""
    s = s or U.h
    b = bw if bw is not None else max(3, s(4))
    return b + (max(2, s(3)) if inner else 0)


def stripes(cv, x1, y1, x2, y2, tags=(), s=None):
    """청록 빗금 바탕 (135도, 14px 씩)."""
    from ..dp import kit as K
    s = s or U.h
    K.dstripes(cv, x1, y1, x2, y2, BG1, BG2, max(6, s(14)), tags=tags)


def cursor(cv, x, ym, size=None, fill=RED, tags=(), s=None):
    """빨간 ▶ (x = 왼쪽 끝, ym = 세로 가운데). 시안: 높이 12 · 폭 9."""
    s = s or U.h
    k = size or s(6)
    return cv.create_polygon(x, ym - k, x + int(k * 1.5), ym, x, ym + k, fill=fill, outline="", tags=tags)


def header(cv, x1, y1, x2, y2, text, spec, arrows=True, tags=(), arrow_tags=None, s=None):
    """빨간 머리 띠: GBA 창 모양(남색 테 · 안쪽 줄) 안을 빨강으로 채우고 흰 글씨 (빨간 그늘 2px).
    arrows 면 양 끝에 흰 ◀ ▶ - arrow_tags(d) 가 그 화살표의 태그 (누르기는 부르는 쪽이 건다)."""
    s = s or U.h
    frame(cv, x1, y1, x2, y2, fill=RED, tags=tags, s=s)
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    d = max(1, s(2))
    cv.create_text(cx + d, cy + d, text=text, fill=RED_D, font=spec, anchor="center", tags=tags)
    cv.create_text(cx, cy, text=text, fill="#ffffff", font=spec, anchor="center", tags=tags)
    if arrows:
        k = s(7)
        aw = s(34)
        for dd, ax in ((-1, x1 + s(10)), (1, x2 - s(10) - aw)):
            tg = tuple(tags) + (tuple(arrow_tags(dd)) if arrow_tags else ())
            cv.create_rectangle(ax, y1, ax + aw, y2, fill="", outline="", tags=tg)       # 누를 자리
            mx = ax + aw // 2
            if dd < 0:
                pts = (mx + k // 2 + 2, cy - k, mx - k, cy, mx + k // 2 + 2, cy + k)
            else:
                pts = (mx - k // 2 - 2, cy - k, mx + k, cy, mx - k // 2 - 2, cy + k)
            cv.create_polygon(pts, fill="#ffffff", outline="", tags=tg)


def sort_box(cv, x1, y1, x2, y2, text, spec, on, tags=(), s=None, hover=False):
    """줄 세우기 칸 (시안 .sorts span): 흰 바탕 · 남색 2px 테, 고른 것은 남색 바탕에 흰 글씨."""
    s = s or U.h
    b = max(2, s(2))
    cv.create_rectangle(x1, y1, x2, y2, fill=NAVY, outline="", tags=tags)
    cv.create_rectangle(x1 + b, y1 + b, x2 - b, y2 - b, fill=NAVY if on else (SELY if hover else "#ffffff"),
                        outline="", tags=tags)
    cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=text, fill="#ffffff" if on else NAVY, font=spec,
                   anchor="center", tags=tags)


def group_head(cv, x, ym, text, spec, tags=()):
    """목록의 단락 머리 (시안 .grp: 회청색 글씨)."""
    return cv.create_text(x, ym, text=text, fill=GRP, font=spec, anchor="w", tags=tags)


# ---------------------------------------------------------------- 단추
# (몸, 올렸을 때, 테, 글자, 테 두께 배율)
KINDS = {
    "blue": (NAVY, NAVY_HI, NAVY_LO, "#ffffff", 1),       # 주된 일 - 남색 (시안의 고른 줄 세우기 칸)
    "gray": ("#ffffff", SELY, NAVY, NAVY, 1),             # 보통 - 흰 바탕 · 남색 테
    "red": (RED, "#e65a52", NAVY, "#ffffff", 1),          # 위험 · 큰 일 (올림 빛은 DP 빨간 단추와 같다)
    "cta": (RED, "#e65a52", NAVY, "#ffffff", 2),          # 시안의 '지니게 하기' - 빨강 · 남색 4px 테 · 그늘
    "off": (OFF_FILL, OFF_FILL, OFF_LINE, OFF_INK, 1),
}


def button(cv, x1, y1, x2, y2, body, line, lw, tags=(), down=False, shadow=True):
    """GBA 단추 모양: 오른쪽 아래 그늘 + 남색 테의 네모 몸. 누르면 그늘 쪽으로 내려앉는다. 몸 도형 id."""
    g = max(2, U.h(3)) if shadow else 0
    d = g if down else 0
    if g:
        cv.create_rectangle(x1 + g, y1 + g, x2, y2, fill=SHADOW, outline="", tags=tags)
    cv.create_polygon(chamfer(x1 + d, y1 + d, x2 - g + d, y2 - g + d, max(1, U.h(2))), fill=line, outline="",
                      tags=tags)
    return cv.create_rectangle(x1 + d + lw, y1 + d + lw, x2 - g + d - lw, y2 - g + d - lw, fill=body, outline="",
                               tags=tags)


# ---------------------------------------------------------------- DP 부품 바꿔 끼우기
_patched = False


def patch_kit():
    """DP 의 kit 부품을 GBA 모양으로 (처음 한 번). 부르는 쪽 코드는 그대로 - 같은 이름 · 같은 말을 받는다."""
    global _patched
    if _patched:
        return
    _patched = True
    from ..dp import kit as K
    import functools

    count = [0]

    def panel(cv, x1, y1, x2, y2, strong=False, fill=None, tags=()):
        """흰 판 -> GBA 창. strong(지금 손대는 판 · 글상자) = 남색 4px 테 + 안쪽 줄, 아니면 남색 2px 테.

        GBA 창은 도형 여럿(테 · 안쪽 줄 · 바탕)이라 그 판만의 태그를 달아 돌려준다 - 부르는 쪽이
        cv.tag_lower(판) 으로 내리면 겹친 순서 그대로 다 같이 내려간다 (도형 하나만 내리면 바탕이 테 밑으로 숨는다)."""
        count[0] += 1
        own = "gbapanel%d" % count[0]
        tg = tuple(tags) + (own,)
        if strong:
            frame(cv, x1, y1, x2, y2, fill=fill or PAPER, tags=tg)
        else:
            frame(cv, x1, y1, x2, y2, fill=fill or PAPER, bw=max(2, U.h(2)), inner=False, tags=tg)
        return own
    K.panel = panel

    base_tabs = K.tabs

    @functools.wraps(base_tabs)
    def tabs(cv, x, y, h, items, current, tag_prefix, spec=None, align="left", hover=None, tags=()):
        """탭 줄: DP 그대로 (빨간 글씨 · 빨간 밑줄) + 고른 탭 앞에 빨간 ▶ (시안의 커서)."""
        out = base_tabs(cv, x, y, h, items, current, tag_prefix, spec=spec, align=align, hover=hover, tags=tags)
        f = K.tkfont_of(cv, spec or K.font(10))
        for key, (bx1, by1, bx2, by2) in out:
            if key == current:
                lb = dict(items).get(key, "")
                tx = (bx1 + bx2) // 2 - f.measure(lb) // 2
                k = max(3, U.h(4))
                cursor(cv, tx - k * 2 - U.h(3), (by1 + by2) // 2 - 1, k,
                       tags=tuple(tags) + (tag_prefix + str(key), tag_prefix))
        return out
    K.tabs = tabs

    def button_shape(cv, x1, y1, x2, y2, body, line, tags=(), down=False):
        """단추 모양 (기본 코드 위젯 단추 · DP 단추가 같이 쓴다) -> GBA 단추."""
        return button(cv, x1, y1, x2, y2, body, NAVY if line else line, max(2, U.h(2)), tags=tags, down=down)
    K.button_shape = button_shape

    def cbutton_draw(self):
        cv = self.cv
        cv.delete(self.tag)
        self._body_id = None
        self._shift = 0
        self._hover = self._down = False
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        body, hi, line, ink, k = KINDS.get("off" if not self.enabled else self.kind, KINDS["gray"])
        m = (self.tag, self.tag + "_m")
        g = max(2, U.h(3))
        cv.create_rectangle(x1 + g, y1 + g, x2, y2, fill=SHADOW, outline="", tags=(self.tag,))      # 그늘
        lw = max(2, U.h(2)) * k
        cv.create_polygon(chamfer(x1, y1, x2 - g, y2 - g, max(1, U.h(2))), fill=line, outline="", tags=m)
        self._body_id = cv.create_rectangle(x1 + lw, y1 + lw, x2 - g - lw, y2 - g - lw, fill=body, outline="",
                                            tags=m)
        cv.create_text((x1 + x2 - g) // 2, (y1 + y2 - g) // 2, text=self.text, fill=ink, font=self.spec,
                       anchor="center", tags=m)
        self._state()

    def cbutton_state(self):
        if self._body_id is None:
            return
        body, hi, _line, _ink, _k = KINDS.get("off" if not self.enabled else self.kind, KINDS["gray"])
        try:
            self.cv.itemconfigure(self._body_id, fill=hi if (self._hover and self.enabled) else body)
            g = max(2, U.h(3))
            want = g if (self._down and self.enabled) else 0          # 누르면 그늘 쪽(오른쪽 아래)으로
            if want != self._shift:
                self.cv.move(self.tag + "_m", want - self._shift, want - self._shift)
                self._shift = want
        except tk.TclError:
            pass
    K.CButton.draw = cbutton_draw
    K.CButton._state = cbutton_state

    def entry(parent, var, width=12):
        """입력칸: 흰 바탕 · 남색 2px 테, 고르면 빨간 테 (시안 .find .box)."""
        box = tk.Frame(parent, bg="#ffffff", highlightthickness=2, highlightbackground=NAVY,
                       highlightcolor=RED, bd=0)
        e = tk.Entry(box, textvariable=var, bg="#ffffff", fg=K.INK, insertbackground=K.INK, relief="flat", bd=0,
                     font=K.font(11), highlightthickness=0, width=width)
        e.pack(fill="both", expand=True, padx=6, pady=2)
        e.bind("<FocusIn>", lambda _e: box.configure(highlightbackground=RED))
        e.bind("<FocusOut>", lambda _e: box.configure(highlightbackground=NAVY))
        box.entry = e
        return box
    K.entry = entry

    def scroll_draw(self):
        """굴림 막대: 옅은 하늘빛 홈에 남색 손잡이 (네모)."""
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or self.hi - self.lo >= 0.999:
            return
        self.create_rectangle(2, 2, w - 2, h - 2, fill="#dce8f0", outline=LIGHT)
        y1 = 2 + (h - 4) * self.lo
        y2 = max(y1 + 16, 2 + (h - 4) * self.hi)
        self.create_rectangle(2, y1, w - 2, y2, fill=NAVY, outline="")
        self.create_rectangle(4, y1 + 2, w - 5, y2 - 3, fill="#56648a", outline="")
    K.Scroll.draw = scroll_draw
