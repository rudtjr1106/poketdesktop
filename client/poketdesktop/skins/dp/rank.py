# -*- coding: utf-8 -*-
"""DP 테마의 랭킹 - 배틀타워 기록판처럼 (v2: 무늬 · 테두리 글씨 · 겹 판을 걷었다).

    위 띠      보라 띠에 '랭킹 · 시즌 N'(제목만 테두리 글씨), 순위 · 전적 / 랜덤 배틀 · 랭크 팀 · 대전 기록 · 새로고침
    본문       무늬 없는 바탕 위의 흰 판 **한 장** (보이는 줄만 그린다 - kit.VList):
               내 티어 띠(티어 빛 막대 · 볼 꼬리표 · RP · 다음 티어까지) · 규칙과 시즌 보상 · 파란 꼬리표 '순위' ·
               순위 줄 · 지난 시즌 명예의 전당. 내 줄은 크림 바탕에 빨간 ▶ 커서. 1 · 2 · 3 등은 금 · 은 · 동 숫자.
    대전 기록  [전체 | 공격한 판 | 공격받은 판] 탭(빨간 밑줄), 줄마다 승/패 칸 · 공격/방어 꼬리표 · '다시 보기'
    아래 줄    진한 테의 글상자 (알림)

무엇을 보일지(글)는 기본 화면의 _rank_head · _me_data · _rules_data · _row_data · _hall_data · _record_data 그대로다.

이 파일에는 사교 묶음(친구 · 게시판 · 길드)이 같이 쓰는 작은 부품도 있다: chip · tier_chip · head_band ·
paint_msg · flat_button.
"""
import tkinter as tk

from ... import ui_common as U
from ... import ui_rank as R
from ...ui_season import TIER_COLOR, TIER_MARK
from . import (DIM, HOV, INK, INK2, LINE, PANEL, PURPLE, PURPLE_LO, SEL, SEP, WHITE, WIN_BG, font, tone)
from . import kit as K
from .battle import mix

MEDAL = {1: "#c89a00", 2: "#8a96a8", 3: "#b06a32"}
RESULT = {"win": ("승", "#2c8a3c"), "lose": ("패", "#d02828"), "draw": ("무", "#808088")}
T = ("head",)


# ================================================================ 사교 묶음이 같이 쓰는 부품
def chip_w(cv, text, spec):
    return K.tkfont_of(cv, spec).measure(text) + U.h(14)


def chip(cv, x, y, text, col, spec=None, tags=()):
    """꼬리표 (x 에서 오른쪽으로, y 가 세로 가운데). 옅은 바탕 + 진한 같은 빛 글씨 - 테두리 글씨를 쓰지 않는다.
    그린 폭."""
    spec = spec or font(9)
    w = chip_w(cv, text, spec)
    h = K.tkfont_of(cv, spec).metrics("linespace") + U.h(4)
    K.rrect(cv, x, y - h // 2, x + w, y - h // 2 + h, U.h(4), fill=mix(col, "#ffffff", 0.8),
            outline=mix(col, "#ffffff", 0.45), width=1, tags=tags)
    cv.create_text(x + w // 2, y, text=text, fill=mix(col, "#000000", 0.42), font=spec, anchor="center", tags=tags)
    return w


def tier_chip(cv, x, y, tier, tier_kr, spec, tags=(), anchor="w"):
    """볼 빛깔 꼬리표 (진한 글씨). 그린 폭 (모르는 티어면 0)."""
    if not tier or not tier_kr:
        return 0
    text = TIER_MARK.get(tier, "") + tier_kr
    col = TIER_COLOR.get(tier, "#c8ccd4")
    w = chip_w(cv, text, spec)
    h = K.tkfont_of(cv, spec).metrics("linespace") + U.h(4)
    y1 = y - h // 2 if anchor == "w" else y
    K.rrect(cv, x, y1, x + w, y1 + h, U.h(4), fill=col, outline=mix(col, "#000000", 0.3), width=1, tags=tags)
    cv.create_text(x + w // 2, y1 + h // 2, text=text, fill="#202028", font=spec, tags=tags)
    return w


def head_band(cv, w, h, band, line, title, tags=T, ty=None):
    """화면 맨 위 빛깔 띠: 무늬 없이 한 빛깔 + 아래 진한 줄, 제목만 DP 의 흰 테두리 글씨. 제목 오른쪽 끝 x."""
    cv.create_rectangle(0, 0, w, h, fill=band, outline="", tags=tags)
    cv.create_rectangle(0, h - U.h(3), w, h, fill=line, outline="", tags=tags)
    tid = K.outlined(cv, U.h(16), h // 2 - U.h(1) if ty is None else ty, title, font(14), line=line, anchor="w",
                     tags=tags, w=1)
    bb = cv.bbox(tid)
    return bb[2] if bb else U.h(90)


def paint_msg(cv, text, color=None):
    """아래 줄 글상자 (진한 테 · 흰 바탕). 글이 길면 줄을 바꾸고 칸을 그만큼 키운다 (글꼴은 그대로).
    할 말이 없으면 칸을 접는다 - 빈 상자가 늘 자리를 차지하지 않게 (사용자: 필요 없는 건 뺀다)."""
    s = U.h
    try:
        cv.delete("all")
        w = cv.winfo_width()
        if not (text or "").strip():
            if int(cv.cget("height")) != 1:
                cv.configure(height=1)
            return
    except tk.TclError:
        return
    if w <= 1:
        return
    x1, x2 = s(10), w - s(10)
    spec = font(11)
    th = K.text_height(cv, text or " ", spec, max(40, x2 - x1 - s(24)))
    want = max(s(38), th + s(20))
    try:
        if int(cv.cget("height")) != want:
            cv.configure(height=want)
    except tk.TclError:
        return
    cv.create_rectangle(0, 0, w, want, fill=WIN_BG, outline="")
    K.msgbox(cv, x1, s(3), x2, want - s(6), text or "", tone(color) if color else INK)


def flat_button(cv, x1, y1, x2, y2, text, kind="gray", spec=None, tags=(), hover=False):
    """캔버스 목록 줄 위의 납작한 단추 그림 (누름은 그리는 쪽이 자리로 가린다). CButton 과 같은 모양 · 빛깔."""
    body, hi, line, ink = K.KINDS.get(kind, K.KINDS["gray"])
    K.button_shape(cv, x1, y1, x2, y2, hi if hover else body, line, tags=tags)
    cv.create_text((x1 + x2) // 2, (y1 + y2 - 2) // 2, text=text, fill=ink, font=spec or font(9), anchor="center",
                   tags=tags)


# ================================================================ 랭킹
class RankWindow(R.RankWindow):

    # ---------------- 틀
    def _header(self):
        self.win.configure(bg=WIN_BG, highlightthickness=0)
        self.hcv = tk.Canvas(self.win, bg=PURPLE, highlightthickness=0, bd=0, height=U.h(62))
        self.hcv.pack(fill="x")
        self.hcv.bind("<Configure>", lambda _e: self._paint_head())
        self._head = ("랭킹", "")
        self.random_btn = K.CButton(self.hcv, "랜덤 배틀", self._random, "red", font(10))
        self.team_btn = K.CButton(self.hcv, "랭크 팀", self._team, "gray", font(10))
        self.mode_btn = K.CButton(self.hcv, "대전 기록", self._toggle_mode, "blue", font(10))
        self.refresh_btn = K.CButton(self.hcv, "새로고침", self.reload, "gray", font(10))

    def _paint_head(self):
        cv, s = self.hcv, U.h
        try:
            w = cv.winfo_width() if cv.winfo_width() > 1 else U.h(R.W)
            cv.delete("head")
        except tk.TclError:
            return
        # 단추는 오른쪽부터 (자리부터 잰다 - 아래 줄 글이 단추 밑으로 들어가지 않게)
        bh = s(32)
        x2 = w - s(14)
        spots = []
        for btn in (self.refresh_btn, self.mode_btn, self.team_btn, self.random_btn):
            bw = btn.want_width(s(24))
            spots.append((btn, x2 - bw, x2))
            x2 -= bw + s(6)
        title, sub = self._head
        sub_w = max(80, x2 - s(30))
        th = K.text_height(cv, sub, font(10), sub_w) if sub else 0
        h = max(s(62), s(12) + s(22) + s(4) + th + s(10))          # 아래 줄이 두 줄이 되면 띠를 키운다
        try:
            if int(cv.cget("height")) != h:
                cv.configure(height=h)
        except tk.TclError:
            return
        head_band(cv, w, h, PURPLE, PURPLE_LO, title, ty=s(12) + s(11))
        if sub:
            K.text(cv, s(16), s(12) + s(22) + s(4), sub, font(10), fill="#f4f2ff", anchor="nw", width=sub_w,
                   tags=T)
        for btn, bx1, bx2 in spots:
            btn.layout(bx1, (h - bh) // 2, bx2, (h + bh) // 2)
        cv.tag_lower("head")

    def _body(self):
        self.bcv = tk.Canvas(self.win, bg=WIN_BG, highlightthickness=0, bd=0)
        self.bcv.pack(fill="both", expand=True)
        self.bcv.bind("<Configure>", lambda _e: self._paint_body())
        self.vl = K.VList(self.bcv, PANEL, self._draw_row)
        self.vl.on_click = self._click_row
        self.vl.cv.bind("<Configure>", self._list_width, add="+")
        self.cv = self.vl.cv                     # (기본 화면의 _scroll_top 이 이것을 본다)
        self._items = []
        self._lw = 0
        self._win_id = None

    def _paint_body(self):
        cv, s = self.bcv, U.h
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
            cv.delete("body")
        except tk.TclError:
            return
        if w <= 1:
            return
        # 흰 판 한 장 (가는 테) - 그 안이 목록이다
        x1, y1, x2, y2 = s(10), s(8), w - s(10), h - s(2)
        K.panel(cv, x1, y1, x2, y2, tags=("body",))
        cv.tag_lower("body")
        geo = dict(x=x1 + 2, y=y1 + 2, width=x2 - x1 - 4, height=y2 - y1 - 4)
        if self._win_id is None:
            self._win_id = cv.create_window(geo["x"], geo["y"], window=self.vl.frame, anchor="nw",
                                            width=geo["width"], height=geo["height"])
        else:
            cv.coords(self._win_id, geo["x"], geo["y"])
            cv.itemconfigure(self._win_id, width=geo["width"], height=geo["height"])

    def _status(self):
        self.scv = tk.Canvas(self.win, bg=WIN_BG, highlightthickness=0, bd=0, height=U.h(38))
        self.scv.pack(fill="x")
        self.scv.bind("<Configure>", lambda _e: self._paint_status())
        self._status_msg = ("", None)

    def _paint_status(self):
        text, color = self._status_msg
        paint_msg(self.scv, text, color)

    def say(self, text, color=U.GOOD):
        self._status_msg = (text or "", None if color in (U.GOOD, None) else color)
        self._paint_status()

    # ---------------- 기본 화면이 넘겨 주는 것
    def _paint_rank(self, head, keep):
        self._head = head
        self._paint_head()
        items = []
        me = self._me_data()
        if me is not None:
            items.append(("me", me))
        items.append(("rules", self._rules_data()))
        if not self.rows:
            items.append(("empty", self._empty_text()))
        else:
            items.append(("label", "순위"))
            items.extend(("rank", self._row_data(r)) for r in self.rows)
        hall = self._hall_data()
        if hall is not None:
            items.append(("label", hall[0]))
            items.extend(("hall", row) for row in hall[1])
        self._set_items(items, keep)

    def _paint_records(self, head, rows, keep):
        self._head = head
        self._paint_head()
        items = [("tabs", None), ("note", self.REC_NOTE)]
        if not rows:
            items.append(("empty", R.REC_EMPTY.get(self.rec_filter, R.REC_EMPTY["all"])))
        else:
            items.extend(("rec", self._record_data(r)) for r in rows)
        self._set_items(items, keep)

    def _back_to(self, top):
        pass

    # ---------------- 줄
    def _list_width(self, e):
        if e.width != self._lw:
            self._lw = e.width
            self._set_items(self._items, True)

    def _set_items(self, items, keep):
        self._items = list(items)
        w = self._lw or self.vl.cv.winfo_width()
        if w <= 1:
            return
        rows = [(self._height(kind, d, w), (kind, d)) for kind, d in self._items]
        self.vl.set(rows, keep=bool(keep))

    def _inner(self, w):
        return w - U.h(36)

    def _tier_lines(self, cv, tiers, w):
        """규칙 판 맨 위의 티어 꼬리표들 - 폭이 모자라면 다음 줄로. [[(티어, 이름, 필요, 꼬리표 폭, 글 폭)]]."""
        s = U.h
        f8 = K.tkfont_of(cv, font(9))
        lines, cur, used = [], [], 0
        room = self._inner(w)
        for tier, tier_kr, need in tiers:
            if not tier or not tier_kr:
                continue
            cw = chip_w(cv, TIER_MARK.get(tier, "") + tier_kr, font(9))
            nw = f8.measure(need)
            one = cw + s(4) + nw + s(12)
            if cur and used + one > room:
                lines.append(cur)
                cur, used = [], 0
            cur.append((tier, tier_kr, need, cw, nw))
            used += one
        if cur:
            lines.append(cur)
        return lines

    def _rec_text_w(self, cv, d, w):
        s = U.h
        lx = s(14) + s(46)
        right = (chip_w(cv, "다시 보기", font(9)) + s(10) + s(12)) if d.get("watch") else 0
        return max(s(80), w - lx - s(14) - right)

    def _height(self, kind, d, w):
        s = U.h
        cv = self.vl.cv
        inner = self._inner(w)
        if kind == "me":
            hh = s(8) + s(30) + s(6) + K.text_height(cv, d["lines"], font(9), inner)
            if d["short"]:
                hh += s(4) + K.text_height(cv, d["short"], font(9), inner)
            return hh + s(10)
        if kind == "rules":
            if d is None:
                return K.text_height(cv, self.RULES_NOTE, font(9), inner) + s(20)
            hh = s(8) + len(self._tier_lines(cv, d["tiers"], w)) * s(26) + s(4)
            hh += K.text_height(cv, d["text"], font(9), inner)
            if d["rewards"]:
                hh += s(10) + s(22)
                for _t, _k, text, _c in d["rewards"]:
                    hh += max(s(22), K.text_height(cv, text, font(9), inner - s(110)) + s(4))
            return hh + s(10)
        if kind == "label":
            return s(32)
        if kind == "empty":
            return K.text_height(cv, d, font(10), inner) + s(60)
        if kind == "rank":
            return s(52)
        if kind == "hall":
            return s(32)
        if kind == "tabs":
            return s(42)
        if kind == "note":
            return K.text_height(cv, d, font(9), inner) + s(16)
        if kind == "rec":
            return max(s(56), s(32) + K.text_height(cv, d["bits"], font(9), self._rec_text_w(cv, d, w)) + s(12))
        return s(30)

    def _draw_row(self, cv, data, x, y, w, h, tags, hov):
        kind, d = data
        getattr(self, "_row_" + kind)(cv, d, x, y, w, h, tags, hov)

    def _row_me(self, cv, d, x, y, w, h, tags, hov):
        """내 티어 - 티어 빛을 옅게 깐 띠 (판 안에 또 판을 두지 않는다)."""
        s = U.h
        col = TIER_COLOR.get(d["tier"], "#9aa6b6")
        cv.create_rectangle(x, y, x + w, y + h, fill=mix(col, "#ffffff", 0.86), outline="", tags=tags)
        cv.create_rectangle(x, y, x + s(5), y + h, fill=col, outline="", tags=tags)
        cv.create_line(x, y + h - 1, x + w, y + h - 1, fill=LINE, tags=tags)
        lx = x + s(18)
        cy = y + s(8) + s(15)
        tw = tier_chip(cv, lx, cy, d["tier"], d["tierKr"], font(11), tags)
        K.text(cv, lx + tw + (s(10) if tw else 0), cy, d["rp"], font(15), anchor="w", tags=tags)
        if d["title"]:
            K.text(cv, x + w - s(18), cy, d["title"], font(10), fill=tone(d["color"]) if d["color"] else "#c06810",
                   anchor="e", tags=tags)
        yy = y + s(8) + s(30) + s(6)
        _a, b = K.text(cv, lx, yy, d["lines"], font(9), fill=INK2, anchor="nw", width=self._inner(w), tags=tags)
        if d["short"]:
            yy = cv.bbox(b)[3] + s(4)
            K.text(cv, lx, yy, d["short"], font(9), fill="#d02828", anchor="nw", width=self._inner(w), tags=tags)

    def _row_rules(self, cv, d, x, y, w, h, tags, hov):
        s = U.h
        lx = x + s(18)
        cv.create_line(x, y + h - 1, x + w, y + h - 1, fill=LINE, tags=tags)
        if d is None:
            K.text(cv, lx, y + s(10), self.RULES_NOTE, font(9), fill=INK2, anchor="nw", width=self._inner(w),
                   tags=tags)
            return
        yy = y + s(8)
        for line in self._tier_lines(cv, d["tiers"], w):
            xx = lx
            cy = yy + s(12)
            for tier, tier_kr, need, cw, nw in line:
                tier_chip(cv, xx, cy, tier, tier_kr, font(9), tags)
                cv.create_text(xx + cw + s(4), cy, text=need, fill=INK2, font=font(9), anchor="w", tags=tags)
                xx += cw + s(4) + nw + s(12)
            yy += s(26)
        yy += s(4)
        _a, b = K.text(cv, lx, yy, d["text"], font(9), fill=INK, anchor="nw", width=self._inner(w), tags=tags)
        yy = cv.bbox(b)[3]
        if d["rewards"]:
            yy += s(10)
            K.text(cv, lx, yy, d["rewards_title"], font(10), anchor="nw", tags=tags)
            yy += s(22)
            for tier, tier_kr, text, color in d["rewards"]:
                tier_chip(cv, lx, yy + s(2), tier, tier_kr, font(9), tags, anchor="n")
                _a, b = K.text(cv, lx + s(110), yy + s(4), text, font(9), fill=tone(color) if color else INK,
                               anchor="nw", width=self._inner(w) - s(110), tags=tags)
                yy = max(yy + s(22), cv.bbox(b)[3] + s(4))

    def _row_label(self, cv, d, x, y, w, h, tags, hov):
        K.tag(cv, x + U.h(14), y + U.h(8), d, tags=tags)

    def _row_empty(self, cv, d, x, y, w, h, tags, hov):
        K.text(cv, x + w // 2, y + U.h(28), d, font(10), fill=DIM, anchor="n", width=self._inner(w),
               justify="center", tags=tags)

    def _row_rank(self, cv, d, x, y, w, h, tags, hov):
        s = U.h
        mine = d["mine"]
        bg = SEL if mine else (HOV if hov is not None else PANEL)
        cv.create_rectangle(x, y, x + w, y + h, fill=bg, outline="", tags=tags)
        cv.create_line(x + s(10), y + h - 1, x + w - s(10), y + h - 1, fill=SEP, tags=tags)
        if mine:
            K.cursor(cv, x + s(6), y + h // 2, tags=tags)
        rank = d["rank"]
        K.text(cv, x + s(50), y + h // 2, "%d" % rank, font(15), fill=MEDAL.get(rank, INK2), anchor="e", tags=tags)
        lx = x + s(64)
        ty, by = y + s(17), y + s(37)
        right = K.tkfont_of(cv, font(12)).measure(d["score"]) + s(30)
        tw = tier_chip(cv, lx, ty, d["tier"], d["tierKr"], font(9), tags)
        nx = lx + tw + (s(8) if tw else 0)
        col = d["color"] or ("#c06810" if mine else INK)
        nid = K.text(cv, nx, ty, d["name"], font(11), fill=tone(col), anchor="w", tags=tags)[1]
        xx = cv.bbox(nid)[2] + s(8)
        if mine:
            xx += chip(cv, xx, ty, "나", "#e07a28", font(9), tags) + s(8)
        if d["title"] and xx < x + w - right:
            cv.create_text(xx, ty, text=d["title"], fill=tone(d["color"]) if d["color"] else "#c06810",
                           font=font(9), anchor="w", tags=tags)
        cv.create_text(lx, by, text=d["bits"], fill=INK2, font=font(9), anchor="w", tags=tags)
        K.text(cv, x + w - s(18), y + h // 2, d["score"], font(12), anchor="e", tags=tags)

    def _row_hall(self, cv, d, x, y, w, h, tags, hov):
        s = U.h
        rank, name, title, score = d
        cv.create_line(x + s(10), y + h - 1, x + w - s(10), y + h - 1, fill=SEP, tags=tags)
        K.text(cv, x + s(50), y + h // 2, "%d" % rank, font(11), fill=MEDAL.get(rank, INK2), anchor="e", tags=tags)
        nid = K.text(cv, x + s(64), y + h // 2, name, font(11), anchor="w", tags=tags)[1]
        if title:
            cv.create_text(cv.bbox(nid)[2] + s(8), y + h // 2, text=title, fill="#c06810", font=font(9),
                           anchor="w", tags=tags)
        cv.create_text(x + w - s(18), y + h // 2, text=score, fill=INK2, font=font(9), anchor="e", tags=tags)

    def _row_tabs(self, cv, d, x, y, w, h, tags, hov):
        s = U.h
        boxes = K.tabs(cv, x + s(10), y + s(6), s(32), R.REC_FILTERS, self.rec_filter, "rectab", spec=font(10),
                       tags=tags)
        cv.create_line(x + s(10), y + s(38), x + w - s(10), y + s(38), fill=LINE, tags=tags)
        self._tab_boxes = [(b[0] - x, b[2] - x, key) for key, b in boxes]

    def _row_note(self, cv, d, x, y, w, h, tags, hov):
        K.text(cv, x + U.h(18), y + U.h(6), d, font(9), fill=INK2, anchor="nw", width=self._inner(w), tags=tags)

    def _row_rec(self, cv, d, x, y, w, h, tags, hov):
        s = U.h
        cv.create_rectangle(x, y, x + w, y + h, fill=HOV if hov is not None else PANEL, outline="", tags=tags)
        cv.create_line(x + s(10), y + h - 1, x + w - s(10), y + h - 1, fill=SEP, tags=tags)
        mark, col = RESULT.get(d["result"], ("?", "#808088"))
        bx = x + s(14)
        K.rrect(cv, bx, y + s(10), bx + s(34), y + s(10) + s(34), s(6), fill=col, tags=tags)
        cv.create_text(bx + s(17), y + s(27), text=mark, fill=WHITE, font=font(12), anchor="center", tags=tags)
        lx = bx + s(46)
        ty = y + s(19)
        kind = "공격" if d["attack"] else "방어"
        cw = chip(cv, lx, ty, kind, "#e07a28" if d["attack"] else "#2860c0", font(9), tags)
        nid = K.text(cv, lx + cw + s(8), ty, d["foe"], font(11), anchor="w", tags=tags)[1]
        if d["lead"]:
            cv.create_text(cv.bbox(nid)[2] + s(10), ty, text=d["lead"], fill=INK2, font=font(9), anchor="w",
                           tags=tags)
        K.text(cv, lx, y + s(32), d["bits"], font(9), fill=INK2, anchor="nw", width=self._rec_text_w(cv, d, w),
               tags=tags)
        if d["watch"]:
            # '다시 보기' - 줄 오른쪽의 파란 단추 (누름은 _click_row 가 자리로 가린다)
            x2 = x + w - s(14)
            bw = chip_w(cv, "다시 보기", font(9)) + s(10)
            by1 = y + h // 2 - s(15)
            on = hov is not None and hov >= x2 - bw
            flat_button(cv, x2 - bw, by1, x2, by1 + s(30), "다시 보기", "blue", font(9), tags, hover=on)

    def _click_row(self, data, x, y, w):
        kind, d = data
        s = U.h
        if kind == "tabs":
            for a, b, key in getattr(self, "_tab_boxes", []):
                if a <= x <= b:
                    return self._pick_filter(key)
        elif kind == "rec" and d["watch"]:
            bw = chip_w(self.vl.cv, "다시 보기", font(9)) + s(10)
            if x >= w - s(14) - bw:
                return self._watch(d["watch"])
