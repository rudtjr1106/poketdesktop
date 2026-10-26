# -*- coding: utf-8 -*-
"""DP 테마의 친구 - 친구수첩 (v2: 테두리 글씨 · 겹 테를 걷고, 줄을 기본 화면만큼 촘촘하게).

DP 의 친구수첩처럼: 귤빛 띠 아래에 줄 쳐진 크림색 공책 한 장.

    위 띠      '친구수첩'(제목만 테두리 글씨) · 몇 명 / 접속 중 몇 명, '새로고침'
    찾기       흰 입력칸 · '찾기' 단추 한 줄, 그 아래 안내 / 찾은 사람 줄
    공책       왼쪽 빨간 여백 줄, 가로 괘선. 받은 신청 · 친구 · 보낸 신청 · 차단이 차례로 (보이는 줄만 그린다)
               친구 줄: 접속 점 · 이름(명패 색) · 칭호 · 마지막 접속 / 티어 · RP · 전적, 오른쪽에 납작한 단추들
               (단추 자리를 먼저 재고 글은 남은 폭에 맞춘다 - 단추 밑으로 글이 들어가지 않는다)
    아래 줄    진한 테의 글상자 (알림)

줄의 단추(배틀 · 차단 · 삭제 · 놀러 가기 · 실시간 · 수락 · 거절 · 취소 · 차단 해제)와 그 차례는 기본 화면의
_friend_actions · _request_actions · _pending_actions · _blocked_actions 가 정한다. 여기서는 줄 위에 그리고,
누른 자리로 어느 단추인지 가린다.
"""
import tkinter as tk

from ... import ui_common as U
from ... import ui_friends as FR
from . import DIM, INK, INK2, LINE, WHITE, WIN_BG, font, tone
from . import kit as K
from .battle import mix
from .rank import chip_w, flat_button, head_band, paint_msg, tier_chip

PAPER, RULE, MARGIN = "#fff8e6", "#eee2c6", "#f0b0a8"
BAND, BAND_LINE = "#c4692c", "#8a4416"          # 귤빛 띠 (흰 글씨가 읽히게 조금 진하게)
KIND = {"ghost": "gray", "red": "red", "accent": "blue"}
T = ("head",)


class _Text(object):
    def __init__(self, on_change):
        self.text = ""
        self.on_change = on_change

    def configure(self, text=None, **_kw):
        if text is not None and text != self.text:
            self.text = text
            self.on_change()

    config = configure


def _fit(cv, s, spec, width):
    """한 줄에 width 까지만 (넘치면 끝에 …). 다 들어가면 그대로."""
    f = K.tkfont_of(cv, spec)
    if f.measure(s) <= width:
        return s
    while s and f.measure(s + "…") > width:
        s = s[:-1]
    return (s + "…") if s else ""


class FriendsWindow(FR.FriendsWindow):

    # ---------------- 틀
    def _header(self):
        self.win.configure(bg=WIN_BG, highlightthickness=0)
        self.hcv = tk.Canvas(self.win, bg=BAND, highlightthickness=0, bd=0, height=U.h(56))
        self.hcv.pack(fill="x")
        self.hcv.bind("<Configure>", lambda _e: self._paint_head())
        self.count = _Text(self._paint_head)
        self.refresh_btn = K.CButton(self.hcv, "새로고침", self.reload, "gray", font(10))

    def _paint_head(self):
        cv, s = self.hcv, U.h
        try:
            w = cv.winfo_width() if cv.winfo_width() > 1 else U.h(FR.W)
            h = cv.winfo_height() if cv.winfo_height() > 1 else s(56)
            cv.delete("head")
        except tk.TclError:
            return
        x = head_band(cv, w, h, BAND, BAND_LINE, "친구수첩")
        bw = self.refresh_btn.want_width(s(24))
        cv.create_text(x + s(14), h // 2 - s(1), text=_fit(cv, self.count.text, font(10), w - bw - x - s(50)),
                       fill=WHITE, font=font(10), anchor="w", tags=T)
        cv.tag_lower("head")
        self.refresh_btn.layout(w - s(14) - bw, (h - s(32)) // 2 - s(1), w - s(14), (h + s(32)) // 2 - s(1))

    def _search(self):
        s = U.h
        self.scv = tk.Canvas(self.win, bg=PAPER, highlightthickness=0, bd=0, height=s(76))
        self.scv.pack(fill="x")
        self.scv.bind("<Configure>", lambda _e: self._paint_search())
        self.q = tk.StringVar()
        self.qbox = K.entry(self.scv, self.q, width=18)
        self.qbox.entry.bind("<Return>", lambda _e: self.do_search())
        self.find_btn = K.CButton(self.scv, "찾기", self.do_search, "blue", font(10))
        self._found = None
        self._found_hits = []
        self.found = tk.Frame(self.win)          # (기본 코드가 쓰지 않게 비워 둔 자리)
        self._qwin = None
        self.scv.bind("<Button-1>", self._found_click)

    def _paint_search(self):
        cv, s = self.scv, U.h
        try:
            cv.delete("srch")
            w = cv.winfo_width()
        except tk.TclError:
            return
        if w <= 1:
            return
        t = ("srch",)
        found = self._found
        y1, y2 = s(10), s(10) + s(32)
        ex = s(16)
        hint = "닉네임으로 찾습니다 · 닉네임이 정확히 맞아야 찾을 수 있습니다."
        base = y2 + s(8) + K.text_height(cv, hint, font(9), w - ex - s(16)) + s(10)
        want = base + (s(50) if found else 0)
        if int(cv["height"]) != want:
            cv.configure(height=want)
        h = want
        cv.create_rectangle(0, 0, w, h, fill=PAPER, outline="", tags=t)
        cv.create_line(0, h - 1, w, h - 1, fill=RULE, width=2, tags=t)
        # 한 줄: 입력칸 · 찾기
        bw = self.find_btn.want_width(s(30))
        geo = (ex, y1, w - s(16) - bw - s(8) - ex, y2 - y1)
        if self._qwin is None:
            self._qwin = cv.create_window(geo[0], geo[1], window=self.qbox, anchor="nw", width=geo[2], height=geo[3])
        else:
            cv.coords(self._qwin, geo[0], geo[1])
            cv.itemconfigure(self._qwin, width=geo[2], height=geo[3])
        self.find_btn.layout(w - s(16) - bw, y1, w - s(16), y2)
        K.text(cv, ex, y2 + s(8), hint, font(9), fill=INK2,
               anchor="nw", width=w - ex - s(16), tags=t)
        self._found_hits = []
        if not found:
            return
        kind, x = found
        fy1, fy2 = base, base + s(42)
        if kind == "note":
            K.text(cv, s(16), (fy1 + fy2) // 2, x, font(10), fill=INK2, anchor="w", tags=t)
            return
        K.rrect(cv, s(12), fy1, w - s(12), fy2, s(8), fill=WHITE, outline=LINE, width=1, tags=t)
        cy = (fy1 + fy2) // 2
        acts = self._search_actions(x)
        room = w - s(24) - self._acts_width(cv, acts) - s(12) - s(42)
        self._dot_at(cv, s(30), cy, x.get("online"), t)
        nid = K.text(cv, s(42), cy, _fit(cv, x["name"], font(11), room), font(11), anchor="w", tags=t)[1]
        if x.get("ranked"):
            cv.create_text(cv.bbox(nid)[2] + s(8), cy, text="%d점" % x.get("rating", 0), fill="#c06810",
                           font=font(9), anchor="w", tags=t)
        self._found_hits = self._draw_actions(cv, w - s(24), cy, acts, t, None, 0)

    def _found_click(self, e):
        for x1, x2, y1, y2, fn in self._found_hits:
            if x1 <= e.x <= x2 and y1 <= e.y <= y2:
                return fn()

    def _body(self):
        self.bcv = tk.Canvas(self.win, bg=PAPER, highlightthickness=0, bd=0)
        self.bcv.pack(fill="both", expand=True)
        self.vl = K.VList(self.bcv, PAPER, self._draw_row)
        self.vl.on_click = self._click_row
        self.vl.cv.bind("<Configure>", self._list_width, add="+")
        self.bcv.bind("<Configure>", lambda _e: self._place_list())
        self.cv = self.vl.cv
        self._items = []
        self._lw = 0
        self._hits = {}
        self._lwin = None

    def _place_list(self):
        cv = self.bcv
        w, h = cv.winfo_width(), cv.winfo_height()
        if w <= 1:
            return
        if self._lwin is None:
            self._lwin = cv.create_window(0, 0, window=self.vl.frame, anchor="nw", width=w, height=h)
        else:
            cv.itemconfigure(self._lwin, width=w, height=h)

    def _status(self):
        self.stcv = tk.Canvas(self.win, bg=WIN_BG, highlightthickness=0, bd=0, height=U.h(38))
        self.stcv.pack(fill="x")
        self.stcv.bind("<Configure>", lambda _e: self._paint_status())
        self._status_msg = ("", None)

    def _paint_status(self):
        text, color = self._status_msg
        paint_msg(self.stcv, text, color)

    def say(self, text, color=U.GOOD):
        self._status_msg = (text or "", None if color in (U.GOOD, None) else color)
        self._paint_status()

    # ---------------- 기본 화면이 넘겨 주는 것
    def _paint_found(self, what):
        self._found = what
        self._paint_search()

    def draw(self):
        count, items = self._list_data()
        self.count.configure(text=count)
        self._items = list(items)
        self._relayout(keep=True)

    # ---------------- 줄
    def _list_width(self, e):
        if e.width != self._lw:
            self._lw = e.width
            self._relayout(keep=True)

    def _relayout(self, keep):
        w = self._lw or self.vl.cv.winfo_width()
        if w <= 1:
            return
        s = U.h
        # 기본 화면의 줄(카드 54 + 틈 6)보다 높지 않게 - 한 화면에 보이는 친구 수가 줄지 않는다
        hts = {"title": s(34), "note": s(40), "request": s(44), "friend": s(48), "pending": s(40),
               "blocked": s(40)}
        self.vl.set([(hts.get(kind, s(40)), (kind, x)) for kind, x in self._items], keep=keep)

    def _draw_row(self, cv, data, x, y, w, h, tags, hov):
        s = U.h
        kind, d = data
        cv.create_rectangle(x, y, x + w, y + h, fill=PAPER, outline="", tags=tags)
        cv.create_line(x, y + h - 1, x + w, y + h - 1, fill=RULE, tags=tags)
        cv.create_line(x + s(32), y, x + s(32), y + h, fill=MARGIN, tags=tags)
        lx = x + s(44)
        cy = y + h // 2
        key = (kind, id(d))
        if kind == "title":
            text, color = d[0], (d[1] if len(d) > 1 else None)
            col = tone(color) if color else BAND
            th = K.tkfont_of(cv, font(10)).metrics("linespace") + U.h(6)
            K.tag(cv, lx - s(4), cy - th // 2, text, tags=tags, fill=col)
            return
        if kind == "note":
            K.text(cv, lx, cy, d, font(10), fill=INK2, anchor="w", width=w - lx - s(16), tags=tags)
            return
        if hov is not None:
            cv.create_rectangle(x + s(33), y, x + w, y + h - 1, fill=mix(PAPER, "#f0c890", 0.3), outline="",
                                tags=tags)
        if kind == "friend":
            acts = self._friend_actions(d)
        elif kind == "request":
            acts = [("button", t_, fn, "accent" if t_ == "수락" else "ghost") for t_, fn in self._request_actions(d)]
        elif kind == "pending":
            acts = [("button", t_, fn, "ghost") for t_, fn in self._pending_actions(d)]
        else:
            acts = [("button", t_, fn, "ghost") for t_, fn in self._blocked_actions(d)]
        # 단추 자리부터 - 글은 그 왼쪽 남은 폭에만
        right = x + w - s(14) - self._acts_width(cv, acts) - s(10)
        if kind == "friend":
            self._friend_text(cv, d, x, lx, y, right, tags)
        elif kind == "request":
            self._name_line(cv, d["name"], font(11), INK, "님이 친구 신청을 보냈습니다", lx, cy, right, tags)
        elif kind == "pending":
            self._name_line(cv, d["name"], font(10), INK2, "답을 기다리는 중", lx, cy, right, tags)
        else:
            self._name_line(cv, d["name"], font(10), DIM, "", lx, cy, right, tags)
        self._hits[key] = self._draw_actions(cv, x + w - s(14), cy, acts, tags, hov, y)

    def _name_line(self, cv, name, spec, fill, note, x, cy, right, tags):
        nid = K.text(cv, x, cy, _fit(cv, name, spec, right - x), spec, fill=fill, anchor="w", tags=tags)[1]
        if note:
            nx = cv.bbox(nid)[2] + U.h(6)
            t = _fit(cv, note, font(9), right - nx)
            if t:
                cv.create_text(nx, cy, text=t, fill=INK2, font=font(9), anchor="w", tags=tags)

    def _friend_text(self, cv, f, x, lx, y, right, tags):
        """친구 줄의 글 두 줄 (이름 · 칭호 · 접속 / 티어 · RP · 전적). right 를 넘는 것은 줄이거나 뺀다."""
        s = U.h
        ty, by = y + s(16), y + s(34)
        self._dot_at(cv, x + s(16), ty, f.get("online"), tags)
        col = f.get("frameColor")
        nid = K.text(cv, lx, ty, _fit(cv, f["name"], font(11), right - lx), font(11),
                     fill=tone(col) if col else INK, anchor="w", tags=tags)[1]
        xx = cv.bbox(nid)[2] + s(8)
        f9 = K.tkfont_of(cv, font(9))
        bits = []
        if f.get("title"):
            bits.append((f["title"], tone(col) if col else "#c06810"))
        text, color = self._seen_text(f)
        if text:
            bits.append((text, tone(color)))
        for t, c in bits:
            if xx + f9.measure(t) > right:
                break
            tid = cv.create_text(xx, ty, text=t, fill=c, font=font(9), anchor="w", tags=tags)
            xx = cv.bbox(tid)[2] + s(8)
        xx = lx
        if f.get("tierKr") and f.get("ranked"):
            if xx + chip_w(cv, f["tierKr"], font(9)) <= right:
                xx += tier_chip(cv, xx, by, f.get("tier"), f["tierKr"], font(9), tags) + s(6)
            line = [("%s RP" % format(int(f.get("rp") or 0), ","), "#c06810")]
        elif f.get("ranked"):
            line = [("%d점" % f.get("rating", 0), "#c06810")]
        else:
            line = []
        wn, ls = f.get("wins", 0), f.get("losses", 0)
        if wn or ls:
            line.append(("%d승 %d패" % (wn, ls), INK2))
        for t, c in line:
            if xx + f9.measure(t) > right:
                break
            tid = cv.create_text(xx, by, text=t, fill=c, font=font(9), anchor="w", tags=tags)
            xx = cv.bbox(tid)[2] + s(8)

    def _dot_at(self, cv, x, y, online, tags):
        r = U.h(5)
        c = "#38b050" if online else "#b8bcc4"
        cv.create_oval(x - r, y - r, x + r, y + r, fill=c, outline=mix(c, "#000000", 0.25), tags=tags)

    def _act_w(self, cv, it):
        if it[0] == "button":
            return K.tkfont_of(cv, font(9)).measure(it[1]) + U.h(20)
        small = it[3] if len(it) > 3 else False
        return K.tkfont_of(cv, font(8 if small else 9)).measure(it[1])

    def _acts_width(self, cv, acts):
        """줄 오른쪽 단추 · 글이 차지하는 폭."""
        return sum(self._act_w(cv, it) for it in acts) + max(0, len(acts) - 1) * U.h(6)

    def _draw_actions(self, cv, x2, cy, acts, tags, hov, top):
        """줄 오른쪽의 단추 · 글 (오른쪽부터). 누를 자리 [(x1, x2, y1, y2, 할 일)] - y 는 줄 안의 자리."""
        s = U.h
        hits = []
        bh = s(28)
        for it in acts:
            bw = self._act_w(cv, it)
            if it[0] == "button":
                _k, text, fn, style = it
                x1 = x2 - bw
                y1 = cy - bh // 2
                on = hov is not None and x1 <= hov <= x2
                flat_button(cv, x1, y1, x2, y1 + bh, text, KIND.get(style, "gray"), font(9), tags, hover=on)
                hits.append((x1, x2, y1 - top, y1 + bh - top, fn))
            else:
                small = it[3] if len(it) > 3 else False
                cv.create_text(x2, cy, text=it[1], fill=tone(it[2]), font=font(8 if small else 9), anchor="e",
                               tags=tags)
            x2 -= bw + s(6)
        return hits

    def _click_row(self, data, x, y, w):
        kind, d = data
        for x1, x2, y1, y2, fn in self._hits.get((kind, id(d)), []):
            if x1 <= x <= x2 and y1 <= y <= y2:
                return fn()
