# -*- coding: utf-8 -*-
"""DP 배틀 화면 - 관장 · 실시간 · 레이드 배틀 창이 같이 쓰는 그림.

    DPLower   글상자와 아래 화면 (세 창 모두)
    DPDuel    1 대 1 위 화면 (관장 · 실시간). 레이드의 위 화면은 raid_battle.py

DS 처럼 위아래 두 화면이다.

    위 화면     민트빛 하늘 · 풀밭 · 황토 받침 둘. 상대 이름표는 왼쪽 위(오른쪽만 둥글다),
                내 이름표는 오른쪽 아래(왼쪽만 둥글다). 체력 막대는 진회색 통에 주황 'HP' 글씨.
                체력 숫자는 기본 창과 같이 보인다 (관장: 둘 다, 실시간: 내 것만 - FOE_HP).
                그 밑에 흰 글상자 - 이 창의 말은 전부 여기에 나온다.
    경첩        두 화면 사이의 검은 띠
    아래 화면   무늬 없는 밝은 바탕. 맨 위 띠에 양쪽 파티의 볼(왼쪽 나, 오른쪽 상대)과 턴.
                기술 → 타입 색 테의 단추 넷(속은 그 타입의 옅은 빛), 맨 아랫줄에
                       (메가진화 · Z기술) · 초록 '포켓몬' · 파란 '기권'
                교체 → 파티 판 여섯 + '취소' (기술 화면으로 돌아간다)
                결과 → 흰 판 + 단추 하나

v2 (2026-10-25): 하늘의 흰 가로줄 · 글상자 오른쪽 빗금 · 아래 화면 몬스터볼 무늬 · 단추의 겹 테(넷 겹) ·
흰 테두리 글씨를 걷었다. 단추는 테 한 겹 + 밝은 윗단, 글씨는 보통 글씨. 창 크기 · 자리는 1차 그대로.

내 차례가 오면 **기술이 바로 나온다** ('싸운다' 를 한 번 더 누르는 단계는 2026-10-25 에 걷었다 - 기본 창처럼
기술 · 교체 · 기권이 한 화면에 있다). 기술 설명은 단추에 마우스를 올리면 위 화면의 글상자에 나온다
(내려 놓으면 하던 말로 돌아간다).

그리는 것만 여기서 한다. 무엇을 보여 줄지(기술 · 교체할 수 있는지 · 결과의 줄)는 창의 동작 코드가 정해서
_paint_moves · _paint_switch · _paint_result_panel 로 넘겨 준다.
"""
import math
import tkinter as tk

from PIL import ImageTk

from common import tint as T

from ... import battle_zoom as Z
from ... import sprite_cache, sprites
from ...ui_common import run_async
from . import BEZEL, CUR, DIM, FONT, INK, INK2, MSG_FRAME, WHITE, kit
from . import PLATE_BOT, PLATE_HOVER_BOT, PLATE_HOVER_TOP, PLATE_LINE, PLATE_OFF_BOT, PLATE_OFF_TOP, PLATE_SEL, PLATE_TOP

U = Z.U


def F(n):
    """갈무리11. 배틀 창은 창 크기 배율을 탄다 (Z.U.pt)."""
    return (FONT, U.pt(n))


# ---------------------------------------------------------------- 색
SKY = ((0.0, "#5cb9a4"), (0.34 / 0.55, "#8fd4bc"), (1.0, "#c6ecd8"))
GROUND = ((0.0, "#a8d67e"), (1.0, "#8cc464"))
HORIZON = 0.55
PLAT = ("#b29862", "#d8c28c", "#ecdeb0")         # 받침: 바깥 · 가운데 · 안
PLATE_FILL, PLATE_EDGE = "#f6f6ee", "#3c4048"     # 이름표
BAR_CASE, BAR_TRACK, BAR_LABEL = "#44484e", "#1c1e20", "#f6b42a"
HP_COLORS = ((0.5, "#7af09a", "#40c868"), (0.2, "#f8e048", "#d0a810"), (0.0, "#f87060", "#c83838"))
GENDER = {"M": ("♂", "#3070e0"), "F": ("♀", "#e04040")}
STATUS = {"화상": "#e07030", "마비": "#c8a818", "독": "#a040a0", "맹독": "#802080", "잠듦": "#8c8c70",
          "얼음": "#58b0c8"}
HINGE = "#121418"
LOW_BG = "#ecece8"                                 # 아래 화면 바탕 (v2: 몬스터볼 무늬 없이)
STRIP, STRIP_SH = "#d6d6d0", "#bcbcb4"
BALL_LINE, BALL_TOP, BALL_OFF, BALL_OFF_LINE = "#55555a", "#e85050", "#bcbcb8", "#9c9c98"
MOVE_OFF, MOVE_OFF_EDGE, MOVE_Z = "#e5e8ec", "#b8bec8", "#fff0b0"

# 아래 화면 단추: (테 · 바닥 그늘, 윗단, 몸, 글자). v2 - 테 한 겹, 글씨는 테두리 없이.
TOUCH = {
    "run": ("#1f4890", "#4c82d8", "#3a6fc8", "#ffffff"),
    "mon": ("#24601c", "#4c9e3c", "#3a8a2c", "#ffffff"),
    "off": ("#b8bec8", "#e5e8ec", "#e5e8ec", "#9aa1ab"),
}

CAT_KR = {"physical": "물리", "special": "특수", "status": "변화"}
CAT_COLOR = {"physical": "#c0501c", "special": "#2860c0", "status": "#606068"}   # 기본 창처럼 분류에 빛깔


def _rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(ra, rb))


def ramp(stops, t):
    """stops = ((위치 0~1, 색), ...) 에서 t 의 색."""
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if a <= t <= b:
            return mix(ca, cb, (t - a) / float((b - a) or 1))
    return stops[-1][1]


def gradient(cv, x1, y1, x2, y2, stops, band=4, tags=()):
    """세로로 번지는 색 (가로띠를 촘촘히 깐다). 띠는 높이를 고르게 나눈다 - band 씩 깔고 남는 것을 끝에
    따로 깔면, 높이가 band 의 배수가 아닐 때(글자를 키워 창 높이가 바뀌면) 1~2px 짜리 줄이 한 가닥 생겼다."""
    h = max(1, y2 - y1)
    n = max(1, h // band)
    for i in range(n):
        a, b = y1 + h * i // n, y1 + h * (i + 1) // n
        cv.create_rectangle(x1, a, x2, b, fill=ramp(stops, (a - y1) / float(h)), outline="", tags=tags)


def side_round(x1, y1, x2, y2, r, right=True):
    """한쪽만 둥근 네모의 점 (이름표). right=True 면 오른쪽 두 모서리가 둥글다."""
    r = max(0, min(r, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    steps = max(2, int(r / 2))
    pts = []
    if right:
        pts += [x1, y1]
        for cx, cy, a0 in ((x2 - r, y1 + r, -90), (x2 - r, y2 - r, 0)):
            for k in range(steps + 1):
                a = math.radians(a0 + 90.0 * k / steps)
                pts += [round(cx + r * math.cos(a)), round(cy + r * math.sin(a))]
        pts += [x1, y2]
    else:
        # 오른쪽 위에서 시작해 위 → 왼쪽 위 귀 → 왼쪽 아래 귀 → 아래로 돈다
        pts += [x2, y1]
        for cx, cy, a0 in ((x1 + r, y1 + r, -90), (x1 + r, y2 - r, 180)):
            for k in range(steps + 1):
                a = math.radians(a0 - 90.0 * k / steps)
                pts += [round(cx + r * math.cos(a)), round(cy + r * math.sin(a))]
        pts += [x2, y2]
    return pts


def backdrop(cv, w, h):
    """위 화면 바탕: 하늘 · 풀밭 (v2: 하늘의 흰 가로줄은 뺐다 - 번지는 빛깔만)."""
    hz = int(h * HORIZON)
    gradient(cv, 0, 0, w, hz, SKY)
    gradient(cv, 0, hz, w, h, GROUND)


def platform(cv, cx, cy, rx, ry):
    """황토 받침 (가운데가 밝다)."""
    outer, mid, inner = PLAT
    cv.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill=outer, outline="")
    cv.create_oval(cx - rx * 0.78, cy - ry * 0.82, cx + rx * 0.78, cy + ry * 0.66, fill=mid, outline="")
    cv.create_oval(cx - rx * 0.52, cy - ry * 0.62, cx + rx * 0.52, cy + ry * 0.36, fill=inner, outline="")


def hp_colors(frac):
    for lim, top, bot in HP_COLORS:
        if frac > lim:
            return top, bot
    return HP_COLORS[-1][1:]


def ball(cv, x, y, d, state, tags=()):
    """작은 몬스터볼. state: 'on' 남은 것 · 'off' 쓰러진 것 · 'none' 빈자리."""
    lw = max(1, int(round(d / 7.0)))
    if state == "none":
        cv.create_oval(x, y, x + d, y + d, fill="", outline=BALL_OFF_LINE, width=lw, tags=tags)
        return
    if state == "off":
        cv.create_oval(x, y, x + d, y + d, fill=BALL_OFF, outline=BALL_OFF_LINE, width=lw, tags=tags)
        return
    cv.create_oval(x, y, x + d, y + d, fill=WHITE, outline="", tags=tags)
    cv.create_arc(x, y, x + d, y + d, start=0, extent=180, style="chord", fill=BALL_TOP, outline="", tags=tags)
    cy = y + d / 2.0
    cv.create_line(x, cy, x + d, cy, fill=BALL_LINE, width=lw, tags=tags)
    cv.create_oval(x, y, x + d, y + d, fill="", outline=BALL_LINE, width=lw, tags=tags)
    r = d / 5.0
    cv.create_oval(x + d / 2.0 - r, cy - r, x + d / 2.0 + r, cy + r, fill=WHITE, outline=BALL_LINE, width=lw,
                   tags=tags)


def corners(cv, x1, y1, x2, y2, tags=()):
    """빨간 꺾쇠 커서 (고른 단추의 네 귀퉁이)."""
    s = U.h
    L, w = s(16), max(2, s(4))
    for (cx, cy, dx, dy) in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
        cv.create_rectangle(min(cx, cx + dx * L), min(cy, cy + dy * w), max(cx, cx + dx * L), max(cy, cy + dy * w),
                            fill=CUR, outline="", tags=tags)
        cv.create_rectangle(min(cx, cx + dx * w), min(cy, cy + dy * L), max(cx, cx + dx * w), max(cy, cy + dy * L),
                            fill=CUR, outline="", tags=tags)


# ---------------------------------------------------------------- 아래 화면 단추
class Touch(object):
    """아래 화면의 단추 (테 한 겹 · 밝은 윗단 · 바닥 그늘, 보통 흰 글씨). 올리면 빨간 꺾쇠가 둘러싼다.

    configure(text=, state=) · cget · invoke 는 기본 단추와 같은 말을 받는다 - 창의 동작 코드가 그대로 부른다.

    **마우스는 단추가 받지 않는다.** 캔버스 하나가 움직임 · 누름을 받아 자리(box)로 단추를 찾는다
    (LowerScreen). 단추마다 태그에 묶으면, 올렸을 때 다시 그리느라 마우스 밑의 도형을 지우고 새로 만들어
    Leave/Enter 가 또 오고 또 그리는 일이 난다.
    """

    def __init__(self, cv, text, command, kind="run", spec=None, tag=None, pad=3):
        self.cv = cv
        self.text = text
        self.command = command
        self.kind = kind
        self.spec = spec or F(14)
        self.tag = tag or ("tb%d" % id(self))
        self.pad = pad
        self.enabled = True
        self.box = None
        self._hover = False
        self._down = False

    def layout(self, x1, y1, x2, y2):
        self.box = (int(x1), int(y1), int(x2), int(y2))
        self.draw()

    def hide(self):
        self.box = None
        self._hover = self._down = False
        try:
            self.cv.delete(self.tag)
        except tk.TclError:
            pass

    def draw(self):
        cv = self.cv
        try:
            cv.delete(self.tag)
        except tk.TclError:
            return
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        d = U.h(2) if self._down else 0
        y1, y2 = y1 + d, y2 + d
        self.paint(x1, y1, x2, y2)
        if self._hover and self.enabled:
            g = U.h(7)
            corners(cv, x1 - g, y1 - g, x2 + g, y2 + g, tags=(self.tag,))

    def paint(self, x1, y1, x2, y2):
        """테 한 겹(바닥은 두껍게 - 눌리는 단추) + 몸 + 밝은 윗단 + 보통 글씨."""
        cv, s, t = self.cv, U.h, (self.tag,)
        edge, top, body, ink = TOUCH["off" if not self.enabled else self.kind]
        r = min(s(12), (y2 - y1) // 3)
        e, eb = max(1, s(2)), max(2, s(4))
        kit.rrect(cv, x1, y1, x2, y2, r, fill=edge, tags=t)
        a1, b1, a2, b2 = x1 + e, y1 + e, x2 - e, y2 - eb
        rr = max(0, r - e)
        kit.rrect(cv, a1, b1, a2, b2, rr, fill=body, tags=t)
        if self.enabled:
            band = b1 + max(s(3), int((b2 - b1) * 0.30))
            kit.rrect(cv, a1, b1, a2, band + rr, rr, fill=top, tags=t)
            cv.create_rectangle(a1, band, a2, min(b2, band + rr + 1), fill=body, outline="", tags=t)
        cv.create_text((x1 + x2) // 2, (b1 + b2) // 2, text=self.text, fill=ink, font=self.spec, anchor="center",
                       tags=t)

    def configure(self, text=None, state=None, **_kw):
        changed = False
        if text is not None and str(text) != self.text:
            self.text = str(text)
            changed = True
        if state is not None and (state == "normal") != self.enabled:
            self.enabled = (state == "normal")
            changed = True
        if changed and self.box:
            self.draw()

    config = configure

    def cget(self, key):
        return {"text": self.text, "state": "normal" if self.enabled else "disabled"}.get(key)

    def set_hover(self, on):
        if on == self._hover:
            return
        self._hover = on
        if not on:
            self._down = False
        self.draw()
        self.on_hover(on)

    def on_hover(self, on):
        pass

    def set_down(self, on):
        if self.enabled and on != self._down:
            self._down = on
            self.draw()

    def invoke(self):
        if self.enabled and self.command:
            self.command()


class LowerScreen(object):
    """아래 화면 캔버스 하나가 마우스를 받아 그 자리의 단추(box 가 있는 것)에 나눠 준다."""

    def __init__(self, cv, items):
        self.cv = cv
        self.items = items              # () -> [단추] (지금 그려져 있는 것들)
        self.hot = None
        self.down = None
        cv.bind("<Motion>", self._motion)
        cv.bind("<Leave>", self._leave)
        cv.bind("<ButtonPress-1>", self._press)
        cv.bind("<ButtonRelease-1>", self._release)

    def reset(self):
        """다시 그렸다 - 올려 둔 것 · 누른 것을 잊는다."""
        self.hot = self.down = None

    def at(self, x, y):
        for b in reversed(self.items()):
            if b.box and b.box[0] <= x <= b.box[2] and b.box[1] <= y <= b.box[3]:
                return b
        return None

    def _motion(self, e):
        b = self.at(e.x, e.y)
        if b is self.hot:
            return
        old, self.hot = self.hot, b
        if old is not None:
            old.set_hover(False)
        if b is not None:
            b.set_hover(True)
        try:
            self.cv.configure(cursor="hand2" if b is not None and b.enabled else "")
        except tk.TclError:
            pass

    def _leave(self, _e):
        if self.hot is not None:
            self.hot.set_hover(False)
        self.hot = self.down = None
        try:
            self.cv.configure(cursor="")
        except tk.TclError:
            pass

    def _press(self, e):
        b = self.at(e.x, e.y)
        if b is not None and b.enabled:
            self.down = b
            b.set_down(True)

    def _release(self, e):
        b, self.down = self.down, None
        if b is None:
            return
        b.set_down(False)
        if b is self.at(e.x, e.y):
            b.invoke()


class PlateHit(object):
    """교체 칸의 파티 판 하나 (LowerScreen 이 단추처럼 다룬다)."""

    def __init__(self, win, i, m, box, active, ok):
        self.win, self.i, self.m, self.box, self.active = win, i, m, box, active
        self.enabled = ok
        self._hover = False

    def set_hover(self, on):
        if on != self._hover:
            self._hover = on
            self.win._draw_plate(self.i, self.m, self.box, self.active, on)

    def set_down(self, on):
        pass

    def invoke(self):
        if self.enabled:
            self.win.do_switch(self.i)


class MoveTouch(Touch):
    """기술 단추: 타입 색 테 · 그 타입의 옅은 속 · 이름 / 타입 꼬리표 · 분류 · 위력 · 명중 / PP."""

    def __init__(self, cv, move, command, peek, tag=None):
        self.move = move
        self.peek = peek
        usable = (move.get("pp") or 0) > 0 and not move.get("blocked")
        Touch.__init__(self, cv, move.get("kr") or move.get("key") or "", command, tag=tag)
        self.enabled = usable

    def paint(self, x1, y1, x2, y2):
        """테 한 겹(타입 색, 바닥은 두껍게) + 속(그 타입의 옅은 빛). 글씨는 진한 보통 글씨."""
        cv, s, t, m = self.cv, U.h, (self.tag,), self.move
        col = U.TYPE_COLOR.get(m.get("type"), "#a8a878")
        on = self.enabled
        r = min(s(12), (y2 - y1) // 3)
        e, eb = max(2, s(3)), max(3, s(5))
        edge = col if on else MOVE_OFF_EDGE
        inner = MOVE_OFF if not on else (MOVE_Z if m.get("z") else mix(col, "#ffffff", 0.84))
        kit.rrect(cv, x1, y1, x2, y2, r, fill=mix(edge, "#000000", 0.12) if on else edge, tags=t)
        kit.rrect(cv, x1 + e, y1 + e, x2 - e, y2 - eb, max(0, r - e), fill=inner, tags=t)
        ink = INK if on else DIM
        h = y2 - eb - y1
        cv.create_text((x1 + x2) // 2, y1 + int(h * 0.36), text=self.text, fill=ink, font=F(14), anchor="center",
                       tags=t)
        # 아랫줄: 타입 꼬리표 · 분류(빛깔) · 위력 · 명중 / PP
        by = y1 + int(h * 0.74)
        tx = x1 + s(16)
        tname = m.get("typeKr") or ""
        if tname:
            f = F(9)
            tw = kit.tkfont_of(cv, f).measure(tname) + s(12)
            th = kit.tkfont_of(cv, f).metrics("linespace") + s(2)
            tcol = col if on else "#b0b6be"
            kit.rrect(cv, tx, by - th // 2, tx + tw, by + th // 2, s(4), fill=tcol, tags=t)
            cv.create_text(tx + tw // 2, by, text=tname, fill=kit.look_of(tcol)[3], font=f, anchor="center", tags=t)
            tx += tw + s(8)
        f = F(10)
        cat = CAT_KR.get(m.get("cat") or "status", "")
        if cat:
            cv.create_text(tx, by, text=cat, fill=CAT_COLOR.get(m.get("cat") or "status", INK2) if on else DIM,
                           font=f, anchor="w", tags=t)
            tx += kit.tkfont_of(cv, f).measure(cat + " ")
        bits = []
        if m.get("power"):
            bits.append("위력 %d" % m["power"])
        bits.append(("명중 %d" % m["acc"]) if m.get("acc") else "명중 —")
        cv.create_text(tx, by, text=("· " if cat else "") + " · ".join(bits), fill=INK2 if on else DIM, font=f,
                       anchor="w", tags=t)
        pp, mx = m.get("pp") or 0, m.get("maxpp") or 0
        pcol = "#d02828" if pp <= 0 else ("#c06810" if mx and pp * 4 <= mx else ink)
        cv.create_text(x2 - s(16), by, text="PP %d/%d" % (pp, mx), fill=pcol, font=f, anchor="e", tags=t)

    def on_hover(self, on):
        self.peek((self.move.get("blocked") or self.move.get("desc")) if on else None)


class Pill(object):
    """메가진화 · Z기술처럼 켜고 끄는 작은 단추 (ui_mega.MegaToggle · ui_gimmick.Toggle 이 부른다).

    그 둘은 단추에 fill · _fg · hover · _shadow 를 바꿔 쓰고 configure(state=) 로 다시 칠하게 한다 -
    같은 이름을 갖춘다. holder 는 그 둘이 pack 하는 위젯이다.
    """

    def __init__(self, parent, text, command, height=34, bg=LOW_BG):
        self.text = text
        self.command = command
        self.fill, self._fg, self.hover, self._shadow = "#f4f6f9", INK, "#ffffff", "#8a96a8"   # (kit 의 회색 단추)
        self._in = False
        f = F(12)
        w = kit.tkfont_of(parent, f).measure(text) + U.h(30)
        self.h = U.h(36)
        self.holder = tk.Canvas(parent, width=w, height=self.h, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.holder.bind("<Enter>", lambda _e: self._set_in(True))
        self.holder.bind("<Leave>", lambda _e: self._set_in(False))
        self.holder.bind("<ButtonRelease-1>", lambda _e: self.command and self.command())
        self.draw()

    def _set_in(self, on):
        self._in = on
        self.draw()

    def draw(self):
        """알약 하나: 테 · 바닥 그늘(_shadow) + 몸. 글씨는 보통 글씨 (켜진 빛깔이 밝으면 진하게)."""
        cv = self.holder
        try:
            cv.delete("all")
        except tk.TclError:
            return
        w, h, s = int(cv["width"]), self.h, U.h
        body = self.hover if self._in else self.fill
        y1, y2 = s(4), h - s(3)
        kit.rrect(cv, 1, y1, w - 1, y2, (y2 - y1) // 2, fill=self._shadow)
        kit.rrect(cv, 2, y1 + 1, w - 2, y2 - s(3), (y2 - s(3) - y1 - 1) // 2, fill=body)
        ink = self._fg
        if ink.lower() in ("#ffffff", "#fff"):
            ink = kit.look_of(self.fill)[3]
        cv.create_text(w // 2, (y1 + y2 - s(3)) // 2 + 1, text=self.text, fill=ink, font=F(12), anchor="center")

    def configure(self, text=None, state=None, **_kw):
        if text is not None:
            self.text = str(text)
            try:
                self.holder.configure(width=kit.tkfont_of(self.holder, F(12)).measure(self.text) + U.h(30))
            except tk.TclError:
                return
        self.draw()

    config = configure


# ---------------------------------------------------------------- 글상자 · 아래 화면 (세 배틀 창이 같이 쓴다)
class DPLower(object):
    """DP 배틀 창의 글상자와 아래 화면 (관장 · 실시간 · 레이드가 같이 쓴다).

    창의 동작 코드가 무엇을 보여 줄지 정해서 _paint_moves · _paint_switch · _paint_wait ·
    _paint_result_panel · _paint_timer_text 로 넘긴다. 이 쪽은 그리기만 한다.

    창이 갖출 것: view, app, alive, busy, photos, root, win, ww, ZOOM_MSG · ZOOM_CMD,
    show_commands · open_switch · use_move · do_switch · close, 그리고 '기권' 자리의 동작(_run_action).
    """

    MSG_PT = 12
    FORFEIT_TEXT = "기권"
    DONE_TEXT = "지도로 돌아가기"
    SWITCH_ASK = "누구로 바꿀까?"

    def _run_action(self):
        """아래 화면 오른쪽 아래 파란 단추가 하는 일 (관장 · 실시간: 기권)."""
        return self.forfeit

    # ---------------- 글상자
    def _message(self):
        f = tk.Frame(self.win, bg=GROUND[-1][1], height=U.h(self.ZOOM_MSG), highlightthickness=0)
        f.pack(fill="x")
        f.pack_propagate(False)
        self.msg_frame = f
        self.mcv = tk.Canvas(f, bg=GROUND[-1][1], highlightthickness=0, bd=0, height=U.h(self.ZOOM_MSG))
        self.mcv.pack(fill="both", expand=True)
        self.mcv.bind("<Configure>", lambda _e: self._draw_message())
        self._peeking = None
        self._draw_message()

    def _draw_message(self):
        cv = getattr(self, "mcv", None)
        if cv is None:
            return
        try:
            cv.delete("all")
            w = max(int(cv.winfo_width()), int(self.ww - 4)) if cv.winfo_width() > 1 else int(self.ww - 4)
            h = max(int(cv.winfo_height()), 1) if cv.winfo_height() > 1 else U.h(self.ZOOM_MSG)
        except tk.TclError:
            return
        s = U.h
        x1, y1, x2, y2 = s(6), s(3), w - s(6), h - s(4)
        # DP 글상자: 진한 테 한 겹 + 흰 바탕 (v2: 오른쪽 끝의 파란 빗금은 뺐다 - 글 자리가 그만큼 넓다)
        kit.rrect(cv, x1, y1, x2, y2, s(8), fill=MSG_FRAME)
        kit.rrect(cv, x1 + s(3), y1 + s(3), x2 - s(3), y2 - s(3), s(6), fill=WHITE)
        text = self._peeking if self._peeking else getattr(self, "_said", "")
        try:
            from common.korean import natural
            text = natural(text or "")
        except Exception:                                   # noqa: BLE001
            text = text or ""
        kit.text(cv, x1 + s(16), (y1 + y2) // 2, text, F(self.MSG_PT), anchor="w",
                 width=x2 - s(3) - (x1 + s(16)) - s(16), tags=("msg",))

    def say(self, text):
        self._said = text or ""
        self._draw_message()

    def _peek(self, text):
        """잠깐 다른 말을 보인다 (기술 설명). None 이면 하던 말로 돌아간다."""
        self._peeking = text or None
        self._draw_message()

    # ---------------- 아래 화면
    def _commands(self):
        self.cmd = tk.Frame(self.win, bg=BEZEL)
        self.cmd.pack(fill="both", expand=True)
        self.bcv = tk.Canvas(self.cmd, width=self.ww - 4, height=U.h(self.ZOOM_CMD), bg=LOW_BG,
                             highlightthickness=0, bd=0)
        self.bcv.pack(fill="both", expand=True)
        cv = self.bcv
        self.switch_btn = Touch(cv, "포켓몬", self.open_switch, "mon", F(15), tag="tomon")
        self.forfeit_btn = Touch(cv, self.FORFEIT_TEXT, self._run_action(), "run", F(15), tag="torun")
        self.cancel_btn = Touch(cv, "취소", self._dp_cancel, "run", F(14), tag="cancel")    # (교체 화면에만)
        self.done_btn = Touch(cv, self.DONE_TEXT, self.close, "run", F(14), tag="done")
        self._touch = [self.switch_btn, self.forfeit_btn, self.cancel_btn, self.done_btn]
        self._move_btns = []
        self._plate_hits = []
        self.lower = LowerScreen(cv, lambda: self._touch + self._move_btns + self._plate_hits)
        self.tbar = tk.Frame(cv, bg=LOW_BG)
        self.mega = self._make_mega(self.tbar)
        self.gim = self._make_gim(self.tbar)
        self._page = getattr(self, "_page", "busy")
        self._lower_size = None
        cv.bind("<Configure>", self._lower_configure)
        self._draw_lower()

    def _make_mega(self, bar):
        from ...ui_mega import MegaToggle
        return MegaToggle(bar, make=self._pill)

    def _make_gim(self, bar):
        from ... import ui_gimmick
        return ui_gimmick.GimmickBar(bar, make=self._pill, on_change=self._gim_changed,
                                     prev=getattr(self, "gim", None))

    def _pill(self, parent, text, command, height=34, **_kw):
        return Pill(parent, text, command, height=height)

    def _lower_configure(self, e):
        if (e.width, e.height) != self._lower_size and self.alive:
            self.root.after_idle(lambda: self.alive and self._draw_lower())

    def _lower_wh(self):
        cv = self.bcv
        w = cv.winfo_width() if cv.winfo_width() > 1 else int(cv["width"])
        h = cv.winfo_height() if cv.winfo_height() > 1 else int(cv["height"])
        return int(w), int(h)

    def _dp_cancel(self):
        """교체 화면의 '취소' - 기술 화면으로 돌아간다."""
        self._peek(None)
        return self.show_commands()

    # ---- 명령 칸에 넘겨 주는 것 (창의 동작 코드가 부른다)
    def _clear_commands(self):
        self._page = "busy"
        self._peek(None)
        for b in (self.switch_btn, self.forfeit_btn):
            b.configure(state="disabled")
        self._draw_lower()

    def _paint_moves(self, moves, can_switch):
        self._moves = list(moves)
        self.switch_btn.configure(state="normal" if can_switch else "disabled")
        self.forfeit_btn.configure(state="normal")
        self._page = "moves"
        self._draw_lower()

    def _paint_switch(self, side, forced, ask):
        self._switch = (side, forced)
        self.switch_btn.configure(state="disabled")
        self.forfeit_btn.configure(state="normal")
        if not forced:
            self._peek(self.SWITCH_ASK)
        self._page = "switch"
        self._draw_lower()

    def _paint_wait(self, title, note, quiet=False):
        """고를 것이 없다 (실시간: 상대를 기다린다). 기권은 누를 수 있다. quiet = 흐린 글 (레이드: 전멸)."""
        self._wait = (title, note, quiet)
        self.switch_btn.configure(state="disabled")
        self.forfeit_btn.configure(state="normal")
        self._page = "wait"
        self._draw_lower()

    def _paint_timer_text(self, text, danger):
        self._timer = (text, danger)
        self._draw_strip()

    def _paint_result_panel(self, res, title, lines):
        self._result = (res, title, list(lines))
        self._page = "result"
        self._draw_lower()

    def _paint_turn(self):
        view = self.view
        self._turn_text = self.turn_text(view)
        self._draw_strip()

    def turn_text(self, view):
        return "%d턴" % (view.get("turn", 0))

    def _balls(self, view=None):
        view = view or self.view
        self._teams = ((view.get("me") or {}).get("team") or [], (view.get("foe") or {}).get("team") or [])
        self._draw_strip()

    # ---- 그리기
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
        s = U.h
        for b in self._touch:
            b.box = None
            b._hover = b._down = False
        self._move_btns = []
        self._plate_hits = []
        self.lower.reset()
        # 바탕: 경첩 · 무늬 없는 밝은 바탕 · 위 띠 (v2: 몬스터볼 무늬는 뺐다)
        top = s(8)
        cv.create_rectangle(0, 0, w, h, fill=LOW_BG, outline="")
        cv.create_rectangle(0, 0, w, top, fill=HINGE, outline="")
        self._draw_strip()
        y0 = top + s(22) + s(2)            # 띠 밑
        page = self._page
        if page == "moves":
            self._draw_moves(w, h, y0)
        elif page == "switch":
            self._draw_switch(w, h, y0)
        elif page == "result":
            self._draw_result(w, h, y0)
        elif page == "wait":
            self._draw_wait(w, h, y0)

    def _draw_strip(self):
        cv = getattr(self, "bcv", None)
        if cv is None:
            return
        try:
            w, _h = self._lower_wh()
            cv.delete("strip")
        except tk.TclError:
            return
        s = U.h
        y, sh = s(8), s(22)
        t = ("strip",)
        cv.create_rectangle(0, y, w, y + sh, fill=STRIP, outline="", tags=t)
        cv.create_rectangle(0, y + sh, w, y + sh + s(2), fill=STRIP_SH, outline="", tags=t)
        d, gap = s(14), s(3)
        me, foe = getattr(self, "_teams", ([], []))
        by = y + (sh - d) / 2.0
        for i in range(6):
            x = s(10) + i * (d + gap)
            ball(cv, x, by, d, self._ball_state(me, i), tags=t)
            if foe is not None:              # (레이드는 상대 파티가 없다)
                x = w - s(10) - d - i * (d + gap)
                ball(cv, x, by, d, self._ball_state(foe, i), tags=t)
        text = getattr(self, "_turn_text", "")
        timer, danger = getattr(self, "_timer", ("", False))
        tcol = DIM if danger is None else ("#d02828" if danger else "#c06810")
        f = F(10)
        tw = kit.tkfont_of(cv, f).measure(text) if text else 0
        mw = kit.tkfont_of(cv, F(11)).measure(timer) if timer else 0
        gap = s(14) if text and timer else 0
        x = w // 2 - (tw + gap + mw) // 2
        if text:
            kit.text(cv, x, y + sh // 2, text, f, anchor="w", tags=t)
        if timer:
            kit.text(cv, x + tw + gap, y + sh // 2, timer, F(11), fill=tcol, anchor="w", tags=t)

    @staticmethod
    def _ball_state(team, i):
        if i >= len(team or []):
            return "none"
        return "off" if team[i].get("fainted") else "on"

    def _draw_moves(self, w, h, y0):
        cv, s = self.bcv, U.h
        moves = getattr(self, "_moves", [])
        # 줄 사이를 빨간 꺾쇠(단추 밖 s(7))가 들어갈 만큼 띄운다 - 올린 기술의 꺾쇠가 아랫줄 · 위 띠를 덮지 않게
        gap = s(14)
        bottom = s(44)
        top = y0 + s(8)
        avail_h = h - top - bottom - s(10)
        mh = (avail_h - gap) // 2
        mw = (w - s(24) - gap) // 2
        for i, m in enumerate(moves[:4]):
            x1 = s(12) + (i % 2) * (mw + gap)
            y1 = top + (i // 2) * (mh + gap)
            b = MoveTouch(cv, m, (lambda k=m.get("key"): self.use_move(k)), self._peek, tag="mv%d" % i)
            b.layout(x1, y1, x1 + mw, y1 + mh)
            self._move_btns.append(b)
        # 맨 아래 줄: 왼쪽에 (메가진화 · Z기술), 오른쪽 끝에 '포켓몬' · '기권'. 두 단추는 긴 글씨에 맞춘 같은 폭이고
        # 자리가 늘 같다 (알약이 있든 없든). 사이는 꺾쇠(s(7))가 옆 단추에 닿지 않게 띄운다.
        ry1, ry2 = h - bottom, h - s(8)
        cv.create_window(s(12), (ry1 + ry2) // 2, window=self.tbar, anchor="w")
        self.tbar.update_idletasks()
        tw = self.tbar.winfo_reqwidth() if (self.mega.shown or self.gim.z.shown) else 0
        f = kit.tkfont_of(cv, self.switch_btn.spec)
        bw = max(f.measure(self.switch_btn.text), f.measure(self.forfeit_btn.text)) + s(64)
        bw = max(bw, s(130))
        left = s(12) + (tw + s(16) if tw > 2 else 0)      # (알약 끝 - 좁은 창에서도 단추가 알약을 덮지 않게)
        bw = max(min(bw, (w - s(12) - gap - left) // 2), 1)
        fx2 = w - s(12)
        self.forfeit_btn.layout(fx2 - bw, ry1, fx2, ry2)
        self.switch_btn.layout(fx2 - bw - gap - bw, ry1, fx2 - bw - gap, ry2)

    def _draw_switch(self, w, h, y0):
        cv, s = self.bcv, U.h
        side, forced = getattr(self, "_switch", ({"team": [], "slot": 0}, True))
        team = side.get("team") or []
        gap = s(8)
        bottom = 0 if forced else s(44)
        cols = 3
        rows = 2
        pw = (w - s(24) - gap * (cols - 1)) // cols
        ph = (h - y0 - s(6) - bottom - s(8) - gap * (rows - 1)) // rows
        for i, m in enumerate(team[:6]):
            x1 = s(12) + (i % cols) * (pw + gap)
            y1 = y0 + s(4) + (i // cols) * (ph + gap)
            box = (x1, y1, x1 + pw, y1 + ph)
            active = i == side.get("slot")
            self._plate_hits.append(PlateHit(self, i, m, box, active, self._plate_ok(i, m)))
            self._draw_plate(i, m, box, active, False)
        if not forced:
            self.cancel_btn.layout(s(12), h - bottom, w - s(12), h - s(8))

    def _plate_ok(self, i, m):
        side, _forced = self._switch
        return not m.get("fainted") and i != side.get("slot")

    def _draw_plate(self, i, m, box, active, hover):
        cv, s = self.bcv, U.h
        tag = "pl%d" % i
        cv.delete(tag)
        x1, y1, x2, y2 = box
        ok = self._plate_ok(i, m)
        c = s(10)
        line = PLATE_SEL if active else PLATE_LINE
        kit.clipped(cv, x1, y1, x2, y2, c, line, tags=(tag,))
        g = s(3) if active else s(2)
        if m.get("fainted"):
            top, bot = PLATE_OFF_TOP, PLATE_OFF_BOT
        elif hover and ok:
            top, bot = PLATE_HOVER_TOP, PLATE_HOVER_BOT
        else:
            top, bot = PLATE_TOP, PLATE_BOT
        kit.clipped(cv, x1 + g, y1 + g, x2 - g, y2 - g, max(0, c - g), bot, tags=(tag,))
        mid = (y1 + y2) // 2
        cv.create_polygon(x1 + g + max(0, c - g), y1 + g, x2 - g, y1 + g, x2 - g, mid, x1 + g, mid,
                          x1 + g, y1 + g + max(0, c - g), fill=top, outline="", tags=(tag,))
        # 그림 · 이름 · Lv / 체력 막대 / 상태(왼쪽) · 체력 숫자(오른쪽) - 세 줄을 판 높이에 고르게 놓는다
        isz = Z.px(32)
        ix = x1 + s(10)
        img = cv.create_image(ix + isz // 2, mid, anchor="center", tags=(tag,))
        self._plate_thumb(img, m)
        tx = ix + isz + s(8)
        ink = INK if ok or active else DIM
        ph = y2 - y1
        ny = y1 + max(s(6), int(ph * 0.12))
        cv.create_text(tx, ny, text=m.get("name") or "", fill=ink, font=F(12), anchor="nw", tags=(tag,))
        cv.create_text(x2 - s(12), ny, text="Lv%d" % (m.get("level") or 0), fill=ink, font=F(10), anchor="ne",
                       tags=(tag,))
        sub = "쓰러짐" if m.get("fainted") else ("싸우는 중" if active else (m.get("statusKr") or ""))
        bx0, bx1 = tx, x2 - s(12)
        by = y1 + int(ph * 0.56)
        frac = (m.get("hp") or 0) / float(m.get("maxhp") or 1)
        kit.rrect(cv, bx0, by - s(5), bx1, by + s(5), s(3), fill=BAR_CASE, tags=(tag,))
        t0, t1 = bx0 + s(3), bx1 - s(3)
        cv.create_rectangle(t0, by - s(2), t1, by + s(2), fill=BAR_TRACK, outline="", tags=(tag,))
        if frac > 0:
            a, b = hp_colors(frac)
            xe = t0 + int((t1 - t0) * max(0.0, min(1.0, frac)))
            cv.create_rectangle(t0, by - s(2), xe, by, fill=a, outline="", tags=(tag,))
            cv.create_rectangle(t0, by, xe, by + s(2), fill=b, outline="", tags=(tag,))
        ly = y2 - max(s(5), int(ph * 0.10))
        if sub:
            cv.create_text(tx, ly, text=sub, fill="#d02828" if m.get("fainted") else ("#c06810" if active else ink),
                           font=F(9), anchor="sw", tags=(tag,))
        cv.create_text(bx1, ly, text="%d/%d" % (m.get("hp") or 0, m.get("maxhp") or 0), fill=ink, font=F(9),
                       anchor="se", tags=(tag,))
        if hover and ok:
            g = U.h(4)
            corners(cv, x1 - g, y1 - g, x2 + g, y2 + g, tags=(tag,))

    def _plate_thumb(self, item, m):
        size = Z.px(32)
        key = "p%s/%s/%d" % (m.get("num"), T.skin(m), size)
        cv = self.bcv
        if key in self.photos:
            try:
                cv.itemconfigure(item, image=self.photos[key])
            except tk.TclError:
                pass
            return
        api = self.app.api

        def work():
            path = sprite_cache.ensure(api, m.get("num"), T.skin(m))
            if not path:
                return None
            anim = sprites.load_animation(path, size, 0.2, 2.0, max_frames=1)
            return sprites.to_rgba(anim.frames[sprites.LEFT][0], anim.key)

        def done(img, err):
            if not self.alive or err or img is None:
                return
            ph = ImageTk.PhotoImage(img)
            self.photos[key] = ph
            try:
                cv.itemconfigure(item, image=ph)
            except tk.TclError:
                pass
        run_async(self.root, work, done)

    def _draw_wait(self, w, h, y0):
        """상대를 기다린다: 흰 판에 한두 줄, 오른쪽 아래 '기권'."""
        cv, s = self.bcv, U.h
        title, note, quiet = getattr(self, "_wait", ("", None, False))
        bw = min(s(230), (w - s(60)) // 3)
        by1, by2 = h - s(56), h - s(10)
        x1, y1, x2, y2 = s(12), y0 + s(6), w - s(12), by1 - s(10)
        kit.rrect(cv, x1, y1, x2, y2, s(12), fill=MSG_FRAME)
        kit.rrect(cv, x1 + s(3), y1 + s(3), x2 - s(3), y2 - s(3), s(10), fill=WHITE)
        width = x2 - x1 - s(48)
        th = kit.text_height(cv, title, F(15), width)
        nh = kit.text_height(cv, note, F(11), width) + s(8) if note else 0
        ty = (y1 + y2) // 2 - (th + nh) // 2
        kit.text(cv, (x1 + x2) // 2, ty, title, F(15), fill=DIM if quiet else "#c06810", anchor="n", width=width,
                 justify="center")
        if note:
            kit.text(cv, (x1 + x2) // 2, ty + th + s(8), note, F(11), anchor="n", width=width, justify="center")
        self.forfeit_btn.layout(w - s(16) - bw, by1, w - s(16), by2)

    def _draw_result(self, w, h, y0):
        cv, s = self.bcv, U.h
        res, title, lines = getattr(self, "_result", ("", "", []))
        x1, y1, x2, y2 = s(12), y0 + s(4), w - s(12), h - s(8)
        kit.rrect(cv, x1, y1, x2, y2, s(12), fill=MSG_FRAME)
        kit.rrect(cv, x1 + s(3), y1 + s(3), x2 - s(3), y2 - s(3), s(10), fill=WHITE)
        bw = max(kit.tkfont_of(cv, self.done_btn.spec).measure(self.done_btn.text) + s(48), s(200))
        self.done_btn.layout(x2 - s(12) - bw, y2 - s(12) - s(44), x2 - s(12), y2 - s(12))
        res = {"win": "won", "lose": "lost"}.get(res, res)      # (실시간 배틀은 win / lose)
        col = {"won": "#c06810", "lost": "#c02828", "timeout": "#c02828"}.get(res, INK)
        kit.text(cv, x1 + s(22), y1 + s(14), title, F(22), fill=col, anchor="nw")
        ty = y1 + s(14) + kit.tkfont_of(cv, F(22)).metrics("linespace") + s(8)
        width = x2 - s(12) - bw - s(16) - (x1 + s(22))
        for ln in lines:
            _a, b = kit.text(cv, x1 + s(22), ty, ln, F(11), anchor="nw", width=width)
            bb = cv.bbox(b)
            ty = (bb[3] if bb else ty + s(18)) + s(4)


# ---------------------------------------------------------------- 1 대 1 장면 (관장 · 실시간)
class DPDuel(DPLower):
    """1 대 1 배틀 창(관장 · 실시간)의 DP 그림. 기본 창(ui_gym_battle.GymBattleWindow 같은 것) 앞에 섞는다.

    글상자 · 아래 화면은 DPLower 가 그리고, 여기서는 위 화면(두 포켓몬 · 이름표)만 그린다.
    """

    # 상대 이름표에 체력 숫자를 적나 (기본 창과 같게: 관장 창은 적고, 실시간 창은 상대 체력을 숨긴다)
    FOE_HP = True

    def _plate_h(self, mine):
        s = U.h
        return s(96) if (mine or self.FOE_HP) else s(80)

    # ---------------- 위 화면
    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = getattr(self, "cv", None)
        if cv is None:
            cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg=SKY[0][1], highlightthickness=0)
            cv.pack(fill="x")
            self.cv = cv
        else:
            cv.delete("all")
            cv.configure(width=self.sw, height=self.sh)
        try:
            self.win.configure(bg=BEZEL, highlightbackground=HINGE)
        except tk.TclError:
            pass
        sw, sh = self.sw, self.sh
        backdrop(cv, sw, sh)
        self.foe_pos = (int(sw * 0.70), int(sh * 0.50))
        self.me_pos = (int(sw * 0.28), int(sh * 0.93))
        fx, fy = self.foe_pos
        mx, my = self.me_pos
        platform(cv, fx, fy, s(150), s(26))
        platform(cv, mx, my, s(190), s(32))
        self.trainer_item = cv.create_image(sw - s(70), fy + s(6), anchor="s")
        self.sprite = {"foe": cv.create_image(fx, fy + s(8), anchor="s"),
                       "me": cv.create_image(mx, my + s(10), anchor="s")}
        bw = s(330)
        self.box = {"foe": self._namebox(-s(3), s(14), False),
                    "me": self._namebox(sw - bw + s(3), sh - s(96) - s(12), True)}
        self.banner = []
        self._paint_watchers()

    def _ball_photos(self):
        pass                                  # 볼은 아래 화면 띠에 직접 그린다

    def _namebox(self, x, y, mine):
        s = U.h
        cv = self.cv
        w, h = s(330), self._plate_h(mine)
        tag = "plate_%s" % ("me" if mine else "foe")
        pts = side_round(x, y, x + w, y + h, s(18), right=not mine)
        cv.create_polygon(pts, fill=PLATE_EDGE, outline="", tags=(tag,))
        g = s(3)
        cv.create_polygon(side_round(x + (0 if not mine else g), y + g, x + w - (g if not mine else 0), y + h - g,
                                     s(15), right=not mine), fill=PLATE_FILL, outline="", tags=(tag,))
        left = x + (s(16) if not mine else s(22))
        right = x + w - (s(20) if not mine else s(14))
        items = {"x": left, "right": right, "y": y, "h": h, "mine": mine, "tag": tag}
        items["name"] = kit.text(cv, left, y + s(20), "", F(13), anchor="w", tags=(tag,))
        items["gender"] = cv.create_text(left, y + s(20), text="", anchor="w", font=F(13), tags=(tag,))
        items["lv"] = kit.text(cv, right, y + s(20), "", F(11), anchor="e", tags=(tag,))
        items["status_y"] = y + s(40)
        items["ability"] = kit.text(cv, right, y + s(40), "", F(9), fill=INK2, anchor="e", tags=(tag,))
        # 체력 막대: 진회색 통 + 'HP' + 검은 홈 + 두 빛깔 막대
        bx0, by0 = left, y + s(52)
        bw = right - left
        bh = s(13)
        kit.rrect(cv, bx0, by0, bx0 + bw, by0 + bh, s(3), fill=BAR_CASE, tags=(tag,))
        cv.create_text(bx0 + s(5), by0 + bh / 2.0, text="HP", anchor="w", fill=BAR_LABEL, font=F(7), tags=(tag,))
        tx0, tx1 = bx0 + s(26), bx0 + bw - s(3)
        ty0, ty1 = by0 + s(3), by0 + bh - s(3)
        cv.create_rectangle(tx0, ty0, tx1, ty1, fill=BAR_TRACK, outline="", tags=(tag,))
        mid = (ty0 + ty1) // 2
        items["bar"] = cv.create_rectangle(tx0, ty0, tx1, mid, fill=HP_COLORS[0][1], outline="", tags=(tag,))
        items["bar2"] = cv.create_rectangle(tx0, mid, tx1, ty1, fill=HP_COLORS[0][2], outline="", tags=(tag,))
        items["bar_geom"] = (tx0, ty0, tx1 - tx0, ty1 - ty0)
        items["hp"] = (kit.text(cv, right, y + s(80), "", F(11), anchor="e", tags=(tag,))
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
        name = mon.get("name") or ""
        for i in items["name"]:
            if i:
                cv.itemconfigure(i, text=name)
        g = GENDER.get(mon.get("gender"))
        nx = items["x"] + kit.tkfont_of(cv, F(13)).measure(name) + U.h(4)
        cv.coords(items["gender"], nx, cv.coords(items["gender"])[1])
        cv.itemconfigure(items["gender"], text=g[0] if g else "", fill=g[1] if g else INK)
        for i in items["lv"]:
            if i:
                cv.itemconfigure(i, text="Lv%d" % (mon.get("level") or 0))
        for i in items["ability"]:
            if i:
                cv.itemconfigure(i, text=self._plate_note(who, mon))
        # 상태 이상 꼬리표 + 능력 변화
        x, y = items["x"], items["status_y"]
        st = mon.get("statusKr") or ""
        f = F(9)
        if st:
            col = STATUS.get(st, "#808080")
            tw = kit.tkfont_of(cv, f).measure(st) + U.h(12)
            th = kit.tkfont_of(cv, f).metrics("linespace") + U.h(2)
            kit.rrect(cv, x, y - th // 2, x + tw, y + th // 2, U.h(4), fill=col, tags=("st_" + who, items["tag"]))
            cv.create_text(x + tw // 2, y, text=st, fill=kit.look_of(col)[3], font=f, anchor="center",
                           tags=("st_" + who, items["tag"]))
            x += tw + U.h(6)
        kr = {"atk": "공", "def": "방", "spa": "특공", "spd": "특방", "spe": "스피드", "acc": "명중", "eva": "회피"}
        bits = ["%s%+d" % (kr.get(k, k), v) for k, v in (mon.get("stages") or {}).items()]
        if bits:
            kit.text(cv, x, y, "  ".join(bits), f, fill="#2860c0", anchor="w", tags=("st_" + who, items["tag"]))
        self._bar(who, mon.get("hp") if hp is None else hp, mon.get("maxhp") or 1)

    def _plate_note(self, who, mon):
        """이름표 오른쪽 둘째 줄 (관장: 특성)."""
        return mon.get("abilityKr") or ""

    def _bar(self, who, hp, maxhp):
        items = self.box[who]
        x0, y0, bw, bh = items["bar_geom"]
        frac = max(0.0, min(1.0, float(hp) / float(maxhp or 1)))
        top, bot = hp_colors(frac)
        x1 = x0 + max(0, int(bw * frac))
        mid = y0 + bh // 2
        self.cv.coords(items["bar"], x0, y0, x1, mid)
        self.cv.coords(items["bar2"], x0, mid, x1, y0 + bh)
        self.cv.itemconfigure(items["bar"], fill=top, state="normal" if x1 > x0 else "hidden")
        self.cv.itemconfigure(items["bar2"], fill=bot, state="normal" if x1 > x0 else "hidden")
        if items.get("hp"):
            for i in items["hp"]:
                if i:
                    self.cv.itemconfigure(i, text="%d/%d" % (max(0, hp), maxhp))

    def _show_banner(self, who, text):
        """특성 · 메가진화 · Z기술 같은 알림: 이름표 곁의 작은 흰 판."""
        s = U.h
        cv = self.cv
        f = F(11)
        tw = kit.tkfont_of(cv, f).measure(text) + s(28)
        th = s(32)
        if who == "foe":
            x, y = s(14), s(14) + self._plate_h(False) + s(8)
        else:
            x, y = self.sw - tw - s(14), self.sh - s(96) - s(12) - th - s(8)
        tag = "banner%d" % len(self.banner)
        kit.rrect(cv, x, y, x + tw, y + th, s(8), fill=PLATE_EDGE, tags=(tag,))
        kit.rrect(cv, x + s(3), y + s(3), x + tw - s(3), y + th - s(3), s(6), fill=PLATE_FILL, tags=(tag,))
        kit.text(cv, x + tw // 2, y + th // 2, text, f, anchor="center", tags=(tag,))
        self.banner.append(tag)

        def gone():
            try:
                cv.delete(tag)
            except tk.TclError:
                pass
        self.later(1400, gone)
