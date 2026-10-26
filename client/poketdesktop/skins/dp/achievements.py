# -*- coding: utf-8 -*-
"""DP 테마 - 업적 · 칭호 (도감 탭 안의 칸)와 업적 달성 알림 창.

DP 도감의 빨간 몸체 안에 배지 케이스를 놓는다 (v2, 2026-10-25 - 무늬 · 겹 테 · 테두리 글씨를 걷었다):

    ┌ 빨간 판: 업적  [액정: 달성 12 / 40]  ▓▓▓▓▓░░░░ ──────────────── 열림: 울트라홀 ┐
    │ ┌ 화면 (테 한 겹, 굴러간다) ──────────────────────────────────────────────────┐ │
    │ │ ▐ 도감 수집  1/2 ▌  (보라 띠)                                               │ │
    │ │ ┌──────────────────────────────────────────────────────────────────────┐  │ │
    │ │ │ 400종                                             [칭호 「도감 조사원」] │  │ │
    │ │ │ 도감에서 400종을 잡는다.                    2026-10-02 달성            │  │ │
    │ │ └──────────────────────────────────────────────────────────────────────┘  │ │

이룬 것은 크림 판에 금테, 못 이룬 것은 흰 판 + 진행 막대. 칭호 목록도 같은 틀이다.
아이콘은 쓰지 않는다 (이룬 것은 판 빛깔 · 금테로 갈린다 - 아이콘을 직접 그리지 않는다).

받기 · 갈래 묶기 · 수 세기는 기본 칸(ui_achievements.AchievementPanel)의 것 그대로다 - 짓는 고리(_build)와
칠하는 고리(_set_summary · _set_unlock · _paint_groups)만 바꾼다.

"""
import tkinter as tk

from common.korean import natural

from ... import ui_achievements as UA
from ... import ui_box
from ... import ui_common as U
from . import DIM, INK, INK2, LINE, PURPLE, RED_BTN, WHITE, font
from . import dialogs as D
from . import kit as K
from .scene import T

RED, RED_D = "#d83c3c", "#a42424"
SCREEN, FRAME = "#eef4e8", "#3a1414"           # 도감 화면 (테 한 겹)
LCD, LCD_LINE, LCD_INK = "#a8d09e", "#3b3b40", "#2f4a30"
GOLD, GOLD_D = "#e0a020", "#a06a10"
GOT_FILL, GOT_LINE = "#fff3dc", "#d89a20"      # 이룬 판
OFF_FILL, OFF_LINE = WHITE, "#c4ccd6"           # 못 이룬 판
GOT_INK, OFF_INK = "#8a4a10", INK


def _mix(a, b, t):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(ca, cb))


# ---------------------------------------------------------------- 그리는 것
def chip_w(cv, text, spec=None):
    return K.tkfont_of(cv, spec or font(9)).measure(text) + U.h(14)


def chip(cv, x, y, text, col, spec=None, tags=()):
    """빛깔 꼬리표 (x 에서 오른쪽으로, y 가 가운데) - 보통 글씨 (밝은 빛깔이면 진한 글씨). 그 폭."""
    spec = spec or font(9)
    w = chip_w(cv, text, spec)
    h = K.tkfont_of(cv, spec).metrics("linespace") + U.h(4)
    K.rrect(cv, x, y - h // 2, x + w, y + h // 2, U.h(4), fill=col, tags=tags)
    cv.create_text(x + w // 2, y, text=text, fill=K.look_of(col)[3], font=spec, anchor="center", tags=tags)
    return w


def section(cv, x1, x2, y, title, tags=()):
    """보라 띠 (갈래 제목) - 한 겹, 흰 보통 글씨. 띠의 높이."""
    bh = U.h(24)
    K.rrect(cv, x1, y, x2, y + bh, U.h(5), fill=PURPLE, tags=tags)
    cv.create_text(x1 + U.h(12), y + bh // 2, text=title, fill=WHITE, font=font(10), anchor="w", tags=tags)
    return bh


def bar(cv, x1, y1, x2, y2, frac, tags=()):
    """DS 풍 진행 막대 - 어두운 홈에 초록 (한 겹)."""
    K.rrect(cv, x1, y1, x2, y2, 4, fill="#4a4e56", tags=tags)
    w = int((x2 - x1 - 4) * max(0.0, min(1.0, frac)))
    if w >= 3:
        cv.create_rectangle(x1 + 2, y1 + 2, x1 + 2 + w, y2 - 2, fill="#58c878", outline="", tags=tags)


def lcd(cv, x, y1, y2, text, spec, tags=()):
    """포켓치 같은 액정 칸 (짙은 테 · 연두 화면). 그 폭."""
    w = K.tkfont_of(cv, spec).measure(text) + U.h(28)
    K.rrect(cv, x, y1, x + w, y2, 6, fill=LCD, outline=LCD_LINE, width=3, tags=tags)
    cv.create_text(x + w // 2, (y1 + y2) // 2, text=text, fill=LCD_INK, font=spec, tags=tags)
    return w


# ---------------------------------------------------------------- 칸
class _Board(object):
    """업적 칸 · 칭호 칸이 같이 쓰는 DP 판. 어떤 줄을 그릴지(_spec)만 갈린다."""
    LABEL = "업적"
    RIBBON = False

    def _build(self):
        self.f.configure(bg=RED)
        self.sum_text, self.sum_fg = "불러오는 중...", U.FG
        self.note_text = ""
        self._frac = None
        self._groups = []
        self._built_w = 0
        self._job = None
        self.cv = tk.Canvas(self.f, bg=RED, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda _e: self._soon())
        self.vl = K.VList(self.cv, SCREEN, self._draw_row)
        self.vl.cv.bind("<Configure>", lambda _e: self._relayout(), add="+")
        self._win = None

    # ---------------- 칠하는 고리 (기본 칸이 부른다) ----------------
    def _set_summary(self, text, fg):
        self.sum_text, self.sum_fg = text, fg
        self._soon()

    def _set_unlock(self, text):
        self.note_text = text
        self._soon()

    def _paint_groups(self, groups, row_fn):
        self._groups = list(groups)
        total = sum(len(rows) for _g, rows, _n in self._groups)
        self._frac = (sum(n for _g, _r, n in self._groups) / float(total)) if total else None
        self._built_w = 0
        self._relayout()
        self._soon()

    # ---------------- 줄 짜기 (폭이 정해져야 높이를 안다) ----------------
    def _spec(self, a):
        """한 줄의 내용: name · desc · chip=(글, 빛깔) · got · closed · hidden · foot · bar=(값, 목표)."""
        raise NotImplementedError

    def _measure(self, a, w):
        s = U.h
        vc = self.vl.cv
        sp = self._spec(a)
        x1, x2 = s(6), w - s(6)
        tx = x1 + s(16)
        right = x2 - s(12)
        cw = chip_w(vc, sp["chip"][0]) if sp["chip"] else 0
        name_w = max(s(60), right - tx - ((cw + s(10)) if cw else 0))
        desc_w = max(s(60), right - tx)
        sp["name_t"] = K.wrap(vc, sp["name"], font(11), name_w)
        sp["desc_t"] = K.wrap(vc, sp["desc"], font(10), desc_w)
        sp["tx"], sp["right"], sp["cw"] = tx, right, cw
        nh = K.text_height(vc, sp["name_t"], font(11), 0)
        dh = K.text_height(vc, sp["desc_t"], font(10), 0) if sp["desc_t"] else 0
        foot = s(16) if (sp["bar"] or sp["foot"]) else 0
        h = s(7) + nh + (s(2) + dh if dh else 0) + (s(4) + foot if foot else 0) + s(7)
        sp["h"] = max(s(44), h) + s(5)
        return sp

    def _relayout(self):
        try:
            w = self.vl.cv.winfo_width()
        except tk.TclError:
            return
        if w <= 1 or w == self._built_w:
            return
        self._built_w = w
        rows = []
        for g, items, n_done in self._groups:
            rows.append((U.h(30), ("sec", "%s  %d/%d" % (g, n_done, len(items)))))
            for a in items:
                sp = self._measure(a, w)
                rows.append((sp["h"], ("card", sp)))
        self.vl.set(rows, keep=True)

    # ---------------- 판 ----------------
    def _soon(self):
        if self._job is None and self.alive:
            try:
                self._job = self.cv.after_idle(self._paint)
            except tk.TclError:
                pass

    def _paint(self):
        self._job = None
        cv = self.cv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 200 or H < 120:
            return
        s = U.h
        cv.delete("scene")
        cv.create_rectangle(0, 0, W, H, fill=RED, outline="", tags=T)           # (v2: 줄무늬 없이)
        pad = s(14)
        # 머리: 이름 · 액정 · 막대 · 안내 (한 줄)
        hh = s(44)
        ly1, ly2 = s(8), s(8) + s(32)
        cv.create_text(pad, (ly1 + ly2) // 2, text=self.LABEL, fill=WHITE, font=font(15), anchor="w", tags=T)
        x = pad + K.tkfont_of(cv, font(15)).measure(self.LABEL) + s(14)
        err = self.sum_fg == U.DANGER
        if err:
            y = D.message_box(cv, x, ly1 - s(2), W - pad, self.sum_text)
            hh = max(hh, y + s(4))
        else:
            x += lcd(cv, x, ly1, ly2, self.sum_text, font(11), tags=T) + s(12)
            nw = max(s(120), min(s(220), (W - pad - x) // 2))
            if self._frac is not None and W - pad - x > s(280):
                bar(cv, x, ly1 + s(10), x + nw, ly2 - s(10), self._frac, tags=T)
                x += nw + s(14)
            if self.note_text:
                K.text(cv, W - pad, (ly1 + ly2) // 2, self.note_text, font(10), fill=WHITE, anchor="e",
                       justify="right", width=max(s(120), W - pad - x), tags=T)
        # 화면 (테 한 겹)
        top, bottom = hh + s(4), H - s(12)
        x1, x2 = pad, W - pad
        K.rrect(cv, x1, top, x2, bottom, 10, fill=SCREEN, outline=FRAME, width=3, tags=T)
        self._place(x1 + s(8), top + s(8), x2 - x1 - s(16), bottom - top - s(16))
        if not self._groups and not err and self.sum_text != "불러오는 중...":
            cv.create_text((x1 + x2) // 2, top + s(60), text="아직 보여 줄 것이 없다.", fill=DIM, font=font(11),
                           tags=T)

    def _place(self, x, y, w, h):
        w, h = max(1, int(w)), max(1, int(h))
        if self._win is None:
            self._win = self.cv.create_window(x, y, window=self.vl.frame, anchor="nw", width=w, height=h)
        else:
            self.cv.coords(self._win, x, y)
            self.cv.itemconfigure(self._win, width=w, height=h)

    # ---------------- 줄 그리기 ----------------
    def _draw_row(self, cv, data, x, y, w, h, tags, hover=None):
        s = U.h
        kind, val = data
        if kind == "sec":
            section(cv, x + s(4), x + w - s(4), y + s(4), val, tags)
            return
        sp = val
        got = sp["got"]
        cx1, cy1, cx2, cy2 = x + s(6), y + s(2), x + w - s(6), y + h - s(3)
        K.rrect(cv, cx1, cy1, cx2, cy2, s(8), fill=GOT_FILL if got else OFF_FILL,
                outline=GOT_LINE if got else OFF_LINE, width=2 if got else 1, tags=tags)
        tx = sp["tx"]
        ty = cy1 + s(7)
        t1 = cv.create_text(tx, ty, text=sp["name_t"], fill=GOT_INK if got else OFF_INK, font=font(11),
                            anchor="nw", tags=tags)
        b = cv.bbox(t1)
        yy = (b[3] if b else ty + s(18)) + s(2)
        if sp["chip"]:
            chip(cv, sp["right"] - sp["cw"], ty + s(9), sp["chip"][0], sp["chip"][1], tags=tags)
        if sp["desc_t"]:
            t2 = cv.create_text(tx, yy, text=sp["desc_t"], fill=INK2, font=font(10), anchor="nw", tags=tags)
            b = cv.bbox(t2)
            yy = (b[3] if b else yy + s(14))
        yy += s(4)
        if sp["bar"]:
            value, target = sp["bar"]
            label = "%d / %d" % (value, target)
            lw = K.tkfont_of(cv, font(9)).measure(label)
            bx2 = sp["right"] - lw - s(10)
            bar(cv, tx, yy + s(3), max(tx + s(40), bx2), yy + s(13), value / float(target or 1), tags)
            cv.create_text(sp["right"], yy + s(8), text=label, fill=INK2, font=font(9), anchor="e", tags=tags)
        elif sp["foot"]:
            cv.create_text(tx, yy + s(8), text=sp["foot"], fill="#2c8a3c", font=font(9), anchor="w", tags=tags)


class AchievementPanel(_Board, UA.AchievementPanel):
    LABEL = "업적"
    RIBBON = False

    def _spec(self, a):
        got = bool(a.get("gotAt"))
        rw = UA.reward_text(a)
        col = ("#7a58d8" if a.get("title") else RED_BTN) if got else "#9aa2ae"
        hidden = (a.get("name") or "").strip("?") == ""
        return {"name": a.get("name", ""), "desc": natural(a.get("desc", "")), "got": got, "closed": False,
                "hidden": hidden and not got, "chip": (rw, col) if rw else None,
                "foot": ("%s 달성" % (a.get("gotAt") or "")[:10]) if got else None,
                "bar": (a["value"], a["target"]) if (not got and "value" in a) else None}


class TitlePanel(_Board, UA.TitlePanel):
    LABEL = "칭호"
    RIBBON = True

    def _spec(self, c):
        got = bool(c.get("owned"))
        closed = not got and not c.get("open", True)
        chip_ = ("가지고 있음", "#3a9a4a") if got else (("지금은 얻을 수 없음", "#9aa2ae") if closed else None)
        return {"name": "「%s」" % c.get("name", ""), "desc": natural(c.get("how", "")), "got": got,
                "closed": closed, "hidden": not got and (c.get("name") or "").strip("?") == "", "chip": chip_, "foot": None,
                "bar": (c["value"], c["target"]) if (not got and "value" in c) else None}


# ---------------------------------------------------------------- 달성 알림
def announce(parent, app, items):
    """업적 달성 창 - DP 의 '메달을 받았다' 글상자. 여럿이면 한 창에 모은다 (창 폭은 기본과 같은 440)."""
    if not items:
        return
    s = U.h
    head, shown, more, note = UA.announce_lines(items)
    win, f = ui_box._shell(parent, "업적", 440, 360)
    width = 440 - 2 * D.PAD
    cv = tk.Canvas(f, bg=D.BODY, highlightthickness=0, bd=0, width=width, height=10)
    cv.pack(fill="x")
    x1, x2 = 1, width - 2                       # 테가 캔버스 끝에 잘리지 않게 한 칸 안쪽
    y = D.message_box(cv, x1, 1, x2, head) + s(10)
    # 받은 것들 (흰 판 한 겹, 한 줄에 하나)
    rh = s(32)
    ph = len(shown) * rh + (s(22) if more else 0) + s(12)
    K.rrect(cv, x1, y, x2, y + ph, s(8), fill=WHITE, outline=LINE, width=1)
    ry = y + s(6)
    for a in shown:
        cy = ry + rh // 2
        rw = UA.reward_text(a)
        cw = chip_w(cv, rw) if rw else 0
        K.text(cv, x1 + s(16), cy, a.get("name", ""), font(11), fill=GOT_INK, anchor="w",
               width=max(s(60), x2 - x1 - s(16) - s(12) - (cw + s(10) if cw else 0)))
        if rw:
            chip(cv, x2 - s(12) - cw, cy, rw, "#7a58d8" if a.get("title") else RED_BTN)
        ry += rh
    if more:
        cv.create_text(x1 + s(16), ry + s(8), text="그 밖 %d개" % more, fill=DIM, font=font(9), anchor="w")
    y += ph + s(10)
    K.text(cv, x1, y, note, font(10), fill=INK2, anchor="nw", width=x2 - x1)
    y += K.text_height(cv, note, font(10), x2 - x1) + s(14)
    ok = K.CButton(cv, "확인", win.destroy, "red", font(12))
    bw = max(ok.want_width(s(36)), s(110))
    ok.layout(x2 - bw, y, x2, y + s(38))
    cv.configure(height=y + s(40))
    win.ok_btn = ok
    win.bind("<Return>", lambda _e: win.destroy())
    win.bind("<Escape>", lambda _e: win.destroy())
    D._wait(parent, win)
