# -*- coding: utf-8 -*-
"""DP 테마의 길드 - 지하통로의 비밀기지 (v2: 무늬 · 테두리 글씨 · 두꺼운 테 · 손으로 그린 아이콘을 걷었다).

길드는 DP 의 비밀기지처럼 짠다: 흙빛 띠 아래, 왼쪽 기둥에 길드 깃발 판과 방 목록, 오른쪽이 그 방.

    위 띠      흙빛 띠(무늬 없이)에 '길드'(제목만 테두리 글씨) · 길드 이름 / 길드 코인 · 새로고침
    왼쪽 기둥  깃발 판(직책 빛 띠 · 길드 이름 · 직책 / 가입 방식 꼬리표 · 길드원 수 · 누적 점수 · 소개)과
               흰 판 한 장의 방 목록 (채팅 · 길드원 · 미션 · 길드전 · 코인 상점 · 다른 길드 · 관리) -
               방마다 본가 도구 그림(poke_icons.py), 고른 방은 크림 바탕에 빨간 ▶. 안 읽은 채팅은 수 / 빨간 점.
               **길드전 방에서는 기둥을 아이콘 줄로 접는다** (지도가 넓어야 한다 - 접지 않으면 기본 창 크기에서
               지도가 손가락 두 개 폭이 됐다).
    채팅       가는 테의 흰 글상자. 이름은 이름판(나는 주황, 남은 파랑), 날짜는 가운데.
               친선전 카드는 흰 판. 아래에 흰 입력칸과 '보내기'.
    길드원     흰 판 한 장의 줄 (직책 빛 막대 · 접속 점 · 이름 · 직책 꼬리표 · 접속 / 칭호 · 오늘 / 누적 점수 ·
               프로필 · 관리) - 기본 화면만큼 촘촘하게
    미션       오늘의 길드 점수 판(주황 막대 · 단계 눈금), 단계 줄(트로피 아이콘), 내 미션 체크 목록(체크 아이콘)
    코인 상점  줄: 도구 그림 · 이름 · 값 · 가진 수 · 설명 / '1개 사기' · '10개 사기'
    다른 길드  길드 판들 (이름 · 가입 방식 · 사람 수 · 마스터 · 점수 · 소개 · 가입)
    관리       가입 신청 · 소개 · 가입 방식 · 나가기 · 해산 (단락 제목은 파란 꼬리표)
    아래 줄    진한 테의 글상자 (알림)

무엇을 보일지 · 서버에 보내는 일은 기본 길드 창 그대로다 (_none_data · _guild_action · member_actions ·
tier_state · shop_match · _leave_data · 채팅의 줄 다루기 · 웹소켓 ...).
"""
import tkinter as tk

from common.korean import natural

from ... import item_icons
from ... import ui_common as U
from ... import ui_guild as G
from ... import ui_spectate as SP
from . import CUR, DIM, HOV, INK, INK2, LINE, SEL, SEP, WHITE, WIN_BG, font, tone
from . import poke_icons
from . import kit as K
from . import widgets as W
from .battle import mix
from .rank import chip as _chip, chip_w as _chip_w, head_band, paint_msg

EARTH, EARTH_LO = "#8c5c2e", "#5e3c1a"    # 위 띠 (흙빛 - 흰 글씨가 읽히게 진하게)
BASE_BG = "#f4ead8"                       # 비밀기지 안 (모래빛)
GLINE = "#dccba8"                         # 모래빛 위 흰 판의 가는 테
ROLE = {"master": "#e07a28", "sub": "#3a72cc", "member": "#4ca83a"}
ROOM_ICON = {"chat": "xtransceiver", "members": "member-card", "mission": "rule-book", "war": "vs-seeker",
             "shop": "coin-case", "guilds": "town-map", "manage": "journal"}      # 본가 4세대 도구 그림
ON_INK = "#b02424"                        # 고른 방 글씨
SIDE_W = 210
RAIL_W = 64                               # 길드전 방에서 접은 기둥 (아이콘 줄)
ROW_LINE = SEP
T = ("head",)


class _Text(object):
    """기본 창이 configure(text=...) 로 고치는 글 (위 띠의 길드 이름 · 코인)."""

    def __init__(self, on_change):
        self.text = ""
        self.on_change = on_change

    def configure(self, text=None, **_kw):
        if text is not None and text != self.text:
            self.text = text
            self.on_change()

    config = configure

    def cget(self, key):
        return self.text if key == "text" else None


class _Cell(object):
    """방 단추 하나의 글 (기본 창이 seg.cells["chat"].configure(text="채팅 3") 로 고친다)."""

    def __init__(self, menu, key, text):
        self.menu, self.key, self.text = menu, key, text

    def configure(self, text=None, **_kw):
        if text is not None and text != self.text:
            self.text = text
            self.menu.win._paint_side()

    config = configure

    def cget(self, key):
        return self.text if key == "text" else None


class _Menu(object):
    """기본 창의 칸 줄(U.Segmented) 자리 - set · cells · badge · has_badge 를 받는다."""

    def __init__(self, win, items, current):
        self.win = win
        self.current = current
        self.cells = dict((k, _Cell(self, k, lb)) for k, lb in items)
        self.order = [k for k, _lb in items]
        self.dots = set()

    def set(self, key):
        self.current = key
        self.win._paint_side()

    def badge(self, key, on):
        if on == (key in self.dots):
            return
        (self.dots.add if on else self.dots.discard)(key)
        self.win._paint_side()

    def has_badge(self, key):
        return key in self.dots


# ---------------------------------------------------------------- 그리는 것
def room_icon(cv, key, cx, cy, tags=()):
    """방의 아이콘 - 본가 4세대 도구 그림 (모든 방에 하나씩, 직접 그리지 않는다)."""
    ph = poke_icons.photo(ROOM_ICON.get(key, "journal"))
    if ph is not None:
        cv.create_image(cx, cy, image=ph, tags=tags)


def card(cv, x1, y1, x2, y2, fill=WHITE, line=GLINE, width=1, r=None, tags=()):
    """흰 판 한 겹 (가는 테)."""
    return K.rrect(cv, x1, y1, x2, y2, U.h(8) if r is None else r, fill=fill, outline=line, width=width, tags=tags)


plate = card                               # (옛 이름)


def chip_w(cv, text, spec=None):
    return _chip_w(cv, text, spec or font(9))


def chip(cv, x, y, text, col, spec=None, tags=()):
    """꼬리표 (x 에서 오른쪽으로, y 가 가운데) - 옅은 바탕에 진한 글씨. 그 폭."""
    return _chip(cv, x, y, text, col, spec or font(9), tags)


def button(cv, x2, y, text, cmd, kind="gray", enabled=True, spec=None, h=None):
    """오른쪽 끝이 x2 · 세로 가운데가 y 인 DP 단추. 단추(.w 가 폭)를 돌려준다.

    그릴 때마다 새로 만든다 - 다시 그리기 전에 drop_buttons(cv) 로 바인딩까지 푼다."""
    b = K.CButton(cv, text, cmd, kind, spec or font(10))
    h = h or U.h(30)
    b.w = b.want_width(U.h(22))
    b.enabled = enabled
    b.layout(x2 - b.w, y - h // 2, x2, y + h // 2)
    if not hasattr(cv, "dp_btns"):
        cv.dp_btns = []
    cv.dp_btns.append(b)
    return b


def drop_buttons(cv):
    for b in getattr(cv, "dp_btns", ()):
        b.dispose()
    cv.dp_btns = []


def section(cv, x1, x2, y, title, note="", tags=()):
    """단락 제목: 파란 꼬리표 + 옆의 짧은 글. 제목 밑의 y."""
    s = U.h
    tw, th = K.tag(cv, x1, y, title, tags=tags)
    if note:
        cv.create_text(x1 + tw + s(10), y + th // 2, text=note, fill=INK2, font=font(9), anchor="w", tags=tags)
    return y + th + s(8)


def clamp_lines(cv, s, spec, width, n):
    """width 로 접어 n 줄까지만 (넘치면 끝에 …)."""
    lines = K.wrap(cv, s, spec, max(1, width)).split("\n")
    if len(lines) <= n:
        return "\n".join(lines)
    last = lines[n - 1]
    f = K.tkfont_of(cv, spec)
    while last and f.measure(last + "…") > width:
        last = last[:-1]
    return "\n".join(lines[:n - 1] + [last + "…"])


class Page(object):
    """굴러가는 캔버스 한 장. draw(cv, 폭) 이 그리고 그린 높이를 돌려준다.

    누를 곳은 cv.hits[꼬리표] = 할 일 로 단다 (캔버스에 한 번 건 누름이 꼬리표를 보고 부른다 -
    그릴 때마다 tag_bind 를 새로 걸지 않는다)."""

    def __init__(self, parent, draw, bg=BASE_BG):
        self.draw = draw
        self.frame = tk.Frame(parent, bg=bg)
        self.cv = tk.Canvas(self.frame, bg=bg, highlightthickness=0, bd=0, yscrollincrement=1)
        self.sb = K.Scroll(self.frame, self.cv, bg)
        self.sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.configure(yscrollcommand=self.sb.set)
        self.cv.hits = {}
        U.scrollable(self.cv, 3)
        self._w = 0
        self._h = 0                                  # 그린 높이
        self.cv.bind("<Configure>", self._conf)
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Motion>", self._motion)

    def _hit(self):
        for t in self.cv.gettags("current"):
            fn = self.cv.hits.get(t)
            if fn is not None:
                return fn
        return None

    def _click(self, _e):
        fn = self._hit()
        if fn is not None:
            fn()

    def _motion(self, _e):
        if any(t.startswith("btn") for t in self.cv.gettags("current")):
            return                                   # 단추는 제가 손가락을 띄운다
        want = "hand2" if self._hit() is not None else ""
        if self.cv.cget("cursor") != want:
            self.cv.configure(cursor=want)

    def _conf(self, e):
        if e.width != self._w:
            self._w = e.width
            self.redraw()
        else:                                        # 높이만 바뀌었다 (위의 판이 늘거나 줄었다) - 굴릴 몫만 다시
            self._region(e.width, e.height)

    def _region(self, w, h):
        try:
            self.cv.configure(scrollregion=(0, 0, w, max(self._h, h)))
        except tk.TclError:
            pass

    def redraw(self, keep=True):
        cv = self.cv
        w = self._w or cv.winfo_width()
        if w <= 1:
            return
        top = cv.yview()[0] if keep else 0.0
        try:
            drop_buttons(cv)
            cv.delete("all")
            cv.hits = {}
            self._h = self.draw(cv, w)
            self._region(w, cv.winfo_height())
            cv.yview_moveto(top)
        except tk.TclError:
            pass


class GuildWindow(G.GuildWindow):

    # ---------------- 위 띠
    def _header(self):
        self.win.configure(bg=BASE_BG, highlightthickness=0)
        self.hcv = tk.Canvas(self.win, bg=EARTH, highlightthickness=0, bd=0, height=U.h(56))
        self.hcv.pack(fill="x")
        self.hcv.bind("<Configure>", lambda _e: self._paint_head())
        self.h_name = _Text(self._paint_head)
        self.h_coin = _Text(self._paint_head)
        self.refresh_btn = K.CButton(self.hcv, "새로고침", self.refresh, "gray", font(10))
        self._status_msg = ("", None)
        self.stcv = None
        self.dpage = None
        self._rail = False
        self._side_hover = None

    def _paint_head(self):
        cv, s = self.hcv, U.h
        try:
            w = cv.winfo_width() if cv.winfo_width() > 1 else U.h(G.W)
            h = cv.winfo_height() if cv.winfo_height() > 1 else s(56)
            cv.delete("head")
        except tk.TclError:
            return
        x = head_band(cv, w, h, EARTH, EARTH_LO, "길드")
        bw = self.refresh_btn.want_width(s(24))
        right = w - s(14) - bw - s(14)
        if self.h_coin.text:
            cid = cv.create_text(right, h // 2 - s(1), text=self.h_coin.text, fill=WHITE, font=font(10), anchor="e",
                                 tags=T)
            right = cv.bbox(cid)[0] - s(14)
        if self.h_name.text:
            cv.create_text(x + s(14), h // 2 - s(1), text=clamp_lines(cv, self.h_name.text, font(12),
                                                                     max(40, right - x - s(14)), 1),
                           fill="#ffe9a8", font=font(12), anchor="w", tags=T)
        self.refresh_btn.layout(w - s(14) - bw, (h - s(32)) // 2 - s(1), w - s(14), (h + s(32)) // 2 - s(1))
        cv.tag_lower("head")

    # ---------------- 아래 글상자
    def _ensure_status(self):
        if self.stcv is not None:
            return
        try:
            self.status.pack_forget()
        except (AttributeError, tk.TclError):
            pass
        self.stcv = tk.Canvas(self.win, bg=WIN_BG, highlightthickness=0, bd=0, height=U.h(38))
        self.stcv.bind("<Configure>", lambda _e: self._paint_status())
        self.stcv.pack(side="bottom", fill="x", before=self.body)

    def say(self, text, color=U.GOOD):
        if not self.alive:
            return
        self._ensure_status()
        self._status_msg = (natural(text or ""), None if color in (U.GOOD, None) else color)
        self._paint_status()

    def _paint_status(self):
        text, color = self._status_msg
        paint_msg(self.stcv, text, color)

    def _page(self, parent, draw):
        s = U.h
        self.dpage = Page(parent, draw)
        self.dpage.frame.pack(fill="both", expand=True, padx=(s(10), 0), pady=s(8))
        return self.dpage

    # ---------------- 길드가 있을 때: 왼쪽 기둥 + 방
    def _draw_guild(self):
        s = U.h
        self._ensure_status()
        self.body.configure(bg=BASE_BG)
        side = tk.Frame(self.body, bg=GLINE, width=s(RAIL_W if self.tab == "war" else SIDE_W))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self.side_cv = tk.Canvas(side, bg=BASE_BG, highlightthickness=0, bd=0)
        self.side_cv.pack(fill="both", expand=True, padx=(0, 1))          # 오른쪽 1px = 기둥과 방 사이 금
        self.side_cv.bind("<Configure>", lambda _e: self._paint_side())
        self.side_cv.bind("<Button-1>", self._side_click)
        self.side_cv.bind("<Motion>", self._side_motion)
        self.side_cv.bind("<Leave>", self._side_leave)
        self.info = side
        self.seg = _Menu(self, self.tabs(), self.tab)
        self.content = tk.Frame(self.body, bg=BASE_BG)
        self.content.pack(fill="both", expand=True)
        self._draw_tab()

    def _draw_tab(self):
        self.dpage = None
        self._set_rail(self.tab == "war")
        G.GuildWindow._draw_tab(self)

    def _set_rail(self, on):
        """길드전 방에서는 기둥을 아이콘 줄로 접는다 (지도 자리)."""
        self._rail = on
        side = getattr(self, "info", None)
        if side is None:
            return
        try:
            side.configure(width=U.h(RAIL_W if on else SIDE_W))
        except tk.TclError:
            return
        self._paint_side()

    def _room_at(self):
        for t in self.side_cv.gettags("current"):
            if t.startswith("room_"):
                return t[5:]
        return None

    def _side_click(self, _e):
        key = self._room_at()
        if key:
            self.show_tab(key)

    def _side_motion(self, _e):
        key = self._room_at()
        want = "hand2" if key else ""
        if self.side_cv.cget("cursor") != want:
            self.side_cv.configure(cursor=want)
        if key != self._side_hover:
            self._side_hover = key
            self._paint_side()

    def _side_leave(self, _e):
        if self._side_hover is not None:
            self._side_hover = None
            self._paint_side()

    def _paint_info(self):
        self._paint_side()

    def _paint_side(self):
        cv = getattr(self, "side_cv", None)
        if cv is None:
            return
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
            cv.delete("all")
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.create_rectangle(0, 0, w, h, fill=BASE_BG, outline="")
        if self._rail:
            return self._paint_rail(cv, w, h)
        s = U.h
        d = self.data or {}
        g = d.get("guild") or {}
        # 깃발 판 - 방 목록이 다 들어가게: 모자라면 소개를 한 줄로, 그래도 모자라면 빼고, 그다음 줄을 낮춘다
        x1, x2 = s(10), w - s(10)
        inner = x2 - x1 - s(24)
        menu = self.seg
        n = len(menu.order)
        name = clamp_lines(cv, g.get("name", ""), font(13), inner, 2)
        nh = K.text_height(cv, name, font(13), inner)
        reqs = len(d.get("requests") or [])
        rh = s(34)
        intro = ih = None
        for lines in (3, 1, 0):
            intro = clamp_lines(cv, g.get("intro") or "소개가 없습니다.", font(9), inner, lines) if lines else ""
            ih = (K.text_height(cv, intro, font(9), inner) + s(8)) if lines else 0
            ph = s(5) + s(10) + nh + s(8) + s(22) + s(8) + s(18) + (s(18) if reqs else 0) + ih + s(8)
            if s(10) + ph + s(10) + n * rh + s(8) <= h:
                break
        room = h - (s(10) + ph + s(10)) - s(8) - s(4)
        if n * rh > room:
            rh = max(s(26), room // n)
        y = s(10)
        role = d.get("role")
        rc = ROLE.get(role, EARTH)
        K.rrect(cv, x1, y, x2, y + s(24), s(8), fill=rc)                      # 직책 빛 띠 (판 위 가장자리)
        card(cv, x1, y + s(5), x2, y + ph)
        yy = y + s(5) + s(10)
        K.text(cv, x1 + s(12), yy, name, font(13), anchor="nw")
        yy += nh + s(8)
        xx = x1 + s(12)
        if d.get("roleKr"):
            xx += chip(cv, xx, yy + s(11), d["roleKr"], ROLE.get(role, "#7a8698")) + s(4)
        if G.MODE_KR.get(g.get("joinMode")):
            chip(cv, xx, yy + s(11), G.MODE_KR[g["joinMode"]], "#7a8698")
        yy += s(22) + s(8)
        cv.create_text(x1 + s(12), yy + s(9), text="길드원 %d / %d명" % (g.get("members", 0), g.get("max", 0)),
                       fill=INK, font=font(10), anchor="w")
        cv.create_text(x2 - s(12), yy + s(9), text="누적 %s점" % format(int(g.get("points") or 0), ","), fill=INK2,
                       font=font(9), anchor="e")
        yy += s(18)
        if reqs:
            cv.create_text(x1 + s(12), yy + s(9), text="가입 신청 %d건" % reqs, fill="#c06810", font=font(9),
                           anchor="w")
            yy += s(18)
        yy += s(6)
        if intro:
            cv.create_text(x1 + s(12), yy, text=intro, fill=INK2 if g.get("intro") else DIM, font=font(9),
                           anchor="nw")
        # 방 목록 - 흰 판 한 장
        y += ph + s(10)
        card(cv, x1, y, x2, y + n * rh + s(8))
        y += s(4)
        for key in menu.order:
            cell = menu.cells[key]
            on = key == menu.current
            tg = ("room", "room_" + key)
            fill = SEL if on else (HOV if key == self._side_hover else WHITE)
            K.rrect(cv, x1 + s(4), y, x2 - s(4), y + rh, s(6), fill=fill, tags=tg)
            if on:
                K.cursor(cv, x1 + s(9), y + rh // 2, size=s(5), tags=tg)
            room_icon(cv, key, x1 + s(30), y + rh // 2, tags=tg)
            K.text(cv, x1 + s(46), y + rh // 2, cell.text, font(11), fill=ON_INK if on else INK, anchor="w",
                   tags=tg)
            if key in menu.dots:
                cv.create_oval(x2 - s(22), y + rh // 2 - s(5), x2 - s(12), y + rh // 2 + s(5), fill=CUR,
                               outline=WHITE, width=2, tags=tg)
            y += rh

    def _paint_rail(self, cv, w, h):
        """접은 기둥: 방마다 아이콘 + 작은 이름 (길드전 방)."""
        s = U.h
        menu = self.seg
        n = len(menu.order)
        top = s(8)
        rh = s(52)
        if top + n * rh > h:
            rh = max(s(40), (h - top) // n)
        y = top
        for key in menu.order:
            on = key == menu.current
            tg = ("room", "room_" + key)
            fill = SEL if on else (HOV if key == self._side_hover else BASE_BG)
            K.rrect(cv, s(4), y + s(2), w - s(4), y + rh - s(2), s(6), fill=fill, tags=tg)
            if on:
                cv.create_rectangle(s(4), y + s(10), s(4) + 3, y + rh - s(10), fill=CUR, outline="", tags=tg)
            room_icon(cv, key, w // 2, y + s(18), tags=tg)
            cv.create_text(w // 2, y + rh - s(13), text=menu.cells[key].text, fill=ON_INK if on else INK2,
                           font=font(9), anchor="center", tags=tg)
            if key in menu.dots:
                cx = w // 2 + 14
                cv.create_oval(cx - s(4), y + s(6), cx + s(4), y + s(6) + s(8), fill=CUR, outline=WHITE, width=2,
                               tags=tg)
            y += rh

    # ---------------- 채팅
    def _build_chat(self):
        s = U.h
        send = tk.Frame(self.content, bg=BASE_BG)
        send.pack(side="bottom", fill="x", padx=s(12), pady=(s(6), s(8)))
        self.chat_var = tk.StringVar()
        U.PushButton(send, "보내기", self.send_chat, height=32, font=font(11)).pack(side="right")
        box = K.entry(send, self.chat_var)
        box.pack(side="left", fill="both", expand=True, padx=(0, s(8)))
        box.entry.bind("<Return>", lambda _e: self.send_chat())
        self.chat_entry = box.entry
        foot = tk.Frame(self.content, bg=BASE_BG)
        foot.pack(side="bottom", fill="x", padx=s(14), pady=(s(4), 0))
        self.chat_state = tk.Label(foot, text="", bg=BASE_BG, fg=INK2, font=font(9), anchor="e")
        self.chat_state.pack(side="right", anchor="n")
        self.chat_hint = tk.Label(foot, text=SP.CMD_HINT, bg=BASE_BG, fg=INK2, font=font(9), anchor="w",
                                  justify="left")
        self.chat_hint.pack(side="left", fill="x", expand=True)
        U.wrap_to_width(self.chat_hint)
        # 대화 글상자: 가는 테 · 흰 바탕
        wrap = tk.Frame(self.content, bg=WHITE, highlightthickness=1, highlightbackground=GLINE,
                        highlightcolor=GLINE, bd=0)
        wrap.pack(fill="both", expand=True, padx=s(12), pady=(s(10), 0))
        t = tk.Text(wrap, bg=WHITE, fg=INK, font=font(11), wrap="word", relief="flat", bd=0,
                    highlightthickness=0, padx=s(12), pady=s(10), state="disabled", cursor="arrow",
                    spacing1=s(4), spacing3=s(3), height=6, width=1)
        sb = K.Scroll(wrap, t, WHITE)

        def on_scroll(lo, hi):
            sb.set(lo, hi)
            self._on_chat_scroll(lo)
        t.configure(yscrollcommand=on_scroll)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        t.tag_configure("time", foreground=INK2, font=font(9))
        # 이름은 보통 채팅처럼 글씨만 (이름판을 깔지 않는다) - 남은 파랑, 나는 주황
        t.tag_configure("name", foreground="#2a56b8", font=font(11))
        t.tag_configure("mine", foreground="#c06810", font=font(11))
        t.tag_configure("body", foreground=INK, font=font(11))
        t.tag_configure("system", foreground=INK2, font=font(9), justify="center")
        t.tag_configure("day", foreground="#a85a20", font=font(9), justify="center", spacing1=s(10), spacing3=s(4))
        t.tag_configure("head", foreground=INK2, font=font(9), justify="center", spacing3=s(4))
        t.tag_configure("card", justify="left", spacing1=s(5), spacing3=s(5))
        t.wheel_div = 40
        t.bind("<Configure>", lambda _e: self._paint_cards(), add="+")
        self.chat_box = t

    def _segments(self, row):
        kind, v = row
        if kind == "day":
            return [("— %s —" % G.day_label(v), ("day",))]
        if kind == "msg" and not SP.is_card(v) and not v.get("system"):
            return [("%s  " % G.clock(v.get("at")), ("time",)),
                    ("%s  " % v.get("name", "?"), ("mine" if v.get("mine") else "name",)),
                    (v.get("body", ""), ("body",))]
        return G.GuildWindow._segments(self, row)

    def _card_widget(self, t, m):
        line = int(m.get("id") or 0)
        f = tk.Canvas(t, bg=WHITE, highlightthickness=0, bd=0, width=U.h(320), height=U.h(70), cursor="arrow")
        self.chat_cards[line] = {"frame": f, "inner": f, "m": m, "sig": None, "view": None, "btn": None}
        self._paint_card(line)
        return f

    def _paint_card(self, line):
        """친선전 카드 - 흰 판: 제목 · 상태 꼬리표 / 글 · 단추. **달라졌을 때만** 다시 그린다."""
        c = self.chat_cards.get(line)
        if c is None:
            return
        v, (lo, hi) = self._card_view(c["m"]), self._card_span()
        sig = (v.get("title"), v["tag"], v["text"], v["button"], v["act"], v["arg"], lo, hi)
        if sig == c["sig"]:
            return
        cv = c["frame"]
        s = U.h
        try:
            drop_buttons(cv)
            cv.delete("all")
            live = v["tone"] in ("seek", "fight")
            f10 = K.tkfont_of(cv, font(10))
            bw = (f10.measure(v["button"]) + s(22)) if v["button"] else 0
            used = bw + s(12) if bw else 0
            need = f10.measure(v["text"]) + s(30) + used
            w = int(max(lo, min(hi, need)))
            text_w = max(s(80), w - s(30) - used)
            th = K.text_height(cv, v["text"], font(10), text_w)
            ty = s(12) + s(20) + s(6)
            h = ty + max(th, s(32) if bw else 0) + s(14)
            cv.configure(width=w, height=h)
            card(cv, 1, 1, w - 2, h - 2, fill="#fff8ec" if live else "#f6f8fb",
                 line="#e0a060" if live else LINE, width=2 if live else 1)
            K.text(cv, s(14), s(12) + s(10), v.get("title") or "길드 친선전", font(11),
                   fill="#c06810" if live else INK2, anchor="w")
            if v["tag"]:
                chip(cv, w - s(14) - chip_w(cv, v["tag"]), s(12) + s(10), v["tag"],
                     "#2c9a4c" if v["tone"] == "fight" else "#7a8698")
            K.text(cv, s(14), ty, v["text"], font(10), fill=INK if live else INK2, anchor="nw", width=text_w)
            btn = None
            if v["button"]:
                press = (lambda a=v["act"], g=v["arg"]: self._card_press(a, g))
                btn = button(cv, w - s(12), ty + s(16), v["button"], press,
                             "red" if v["act"] in ("accept", "watch") else "gray", h=s(32))
            c["sig"], c["view"], c["btn"] = sig, v, btn
        except tk.TclError:
            pass

    # ---------------- 길드원
    def _tab_members(self):
        self._page(self.content, self._draw_members)

    def _draw_members(self, cv, w):
        """흰 판 한 장의 줄: 직책 빛 막대 · 접속 점 · 이름 · 직책 · 접속 / 칭호 · 점수, 오른쪽에 단추."""
        s = U.h
        d = self.data or {}
        can = d.get("can") or {}
        members = d.get("members") or []
        x1, x2 = s(2), w - s(10)
        rh = s(54)
        top = s(2)
        total = max(1, len(members)) * rh + s(4)
        card(cv, x1, top, x2, top + total)
        y = top + s(2)
        f9 = K.tkfont_of(cv, font(9))
        for i, m in enumerate(members):
            if i:
                cv.create_line(x1 + s(12), y, x2 - s(12), y, fill=ROW_LINE)
            col = ROLE.get(m.get("role"), ROLE["member"])
            cv.create_rectangle(x1 + s(6), y + s(10), x1 + s(6) + 3, y + rh - s(10), fill=col, outline="")
            ty, by = y + s(18), y + s(37)
            cv.create_oval(x1 + s(16), ty - s(5), x1 + s(26), ty + s(5),
                           fill="#38b050" if m.get("online") else "#b8bcc4",
                           outline=mix("#38b050" if m.get("online") else "#b8bcc4", "#000000", 0.25))
            # 단추 (오른쪽) 먼저 - 남은 폭에 글을 맞춘다
            manage = (not m.get("me")) and m.get("role") != "master" and (
                can.get("master") or (can.get("manage") and m.get("role") == "member"))
            bx = x2 - s(12)
            cy = y + rh // 2
            if manage:
                bx -= button(cv, bx, cy, "관리", lambda mm=m: self.manage_dialog(mm), "blue", h=s(28)).w + s(6)
            bx -= button(cv, bx, cy, "프로필", lambda u=m["id"]: self.profile_dialog(u), "gray", h=s(28)).w
            right = bx - s(12)
            lx = x1 + s(34)
            fc = m.get("frameColor")
            ink = W.fg(fc) if fc else INK
            role_w = (chip_w(cv, m.get("roleKr") or "") + s(8)) if m.get("role") in ("master", "sub") else 0
            name = clamp_lines(cv, m["name"], font(11), max(s(40), right - lx - role_w), 1)
            nid = K.text(cv, lx, ty, name, font(11), fill=ink, anchor="w")[1]
            xx = cv.bbox(nid)[2] + s(8)
            if role_w:
                xx += chip(cv, xx, ty, m.get("roleKr") or "", col) + s(8)
            text, color = G.seen_text(m)
            if text and xx + f9.measure(text) <= right:
                cv.create_text(xx, ty, text=text, fill=tone(color), font=font(9), anchor="w")
            bits = []
            if m.get("title"):
                bits.append((m["title"], ink if fc else "#c06810"))
            bits.append(("오늘 %d점 · 누적 %s점" % (m.get("today", 0), format(int(m.get("points") or 0), ",")),
                         "#c06810" if m.get("today") else INK2))
            xx = lx
            for t, c in bits:
                t = clamp_lines(cv, t, font(9), max(s(20), right - xx), 1)
                tid = cv.create_text(xx, by, text=t, fill=c, font=font(9), anchor="w")
                xx = cv.bbox(tid)[2] + s(12)
                if xx >= right:
                    break
            y += rh
        return top + total + s(8)

    # ---------------- 미션
    def _tab_mission(self):
        self._page(self.content, self._draw_mission)

    def _paint_bar(self):
        if self.dpage is not None and self.tab == "mission":
            self.dpage.redraw()

    def _draw_mission(self, cv, w):
        s = U.h
        ms = (self.data or {}).get("mission") or {}
        x1, x2 = s(2), w - s(10)
        inner = x2 - x1 - s(32)
        note = G.mission_note(ms)
        nh = K.text_height(cv, note, font(9), inner)
        tiers = ms.get("tiers") or []
        ph = s(14) + s(26) + s(10) + s(14) + s(10) + nh + s(8) + len(tiers) * s(28) + s(8)
        y = s(2)
        card(cv, x1, y, x2, y + ph)
        yy = y + s(14)
        f11 = K.tkfont_of(cv, font(11))
        K.text(cv, x1 + s(16), yy + s(13), "오늘의 길드 점수", font(11), anchor="w")
        K.text(cv, x1 + s(16) + f11.measure("오늘의 길드 점수") + s(12), yy + s(13),
               "%d점" % int(ms.get("guildPoints") or 0), font(15), fill="#c06810", anchor="w")
        cv.create_text(x2 - s(16), yy + s(13), text="%s 뒤에 새로 시작합니다" % G.span(ms.get("resetIn")), fill=INK2,
                       font=font(9), anchor="e")
        yy += s(26) + s(10)
        # 막대: 옅은 홈 · 주황 막대 · 단계마다 눈금
        bx1, bx2, bh = x1 + s(16), x2 - s(16), s(14)
        top = float(ms.get("guildMax") or 1)
        K.rrect(cv, bx1, yy, bx2, yy + bh, bh // 2, fill="#efe4cc", outline=GLINE, width=1)
        frac = min(1.0, float(ms.get("guildPoints") or 0) / top)
        if frac > 0:
            fx = bx1 + max(bh, int((bx2 - bx1) * frac))
            K.rrect(cv, bx1, yy, fx, yy + bh, bh // 2, fill="#e8892c")
        for t in tiers:
            x = bx1 + int((bx2 - bx1) * min(1.0, float(t.get("need") or 0) / top))
            if bx1 + s(4) < x < bx2 - s(4):
                cv.create_line(x, yy + s(2), x, yy + bh - s(2), fill="#2c8a3c" if t.get("reached") else "#b8a888",
                               width=2)
        yy += bh + s(10)
        K.text(cv, x1 + s(16), yy, note, font(9), fill=INK2, anchor="nw", width=inner)
        yy += nh + s(8)
        for t in tiers:
            reached = t.get("reached")
            cy = yy + s(14)
            K.text(cv, x1 + s(16), cy, "%d단계" % t["tier"], font(10), fill=INK if reached else INK2, anchor="w")
            cv.create_text(x1 + s(104), cy, text="%d점" % t["need"], fill=INK2, font=font(10), anchor="w")
            kind, text = G.tier_state(t, ms)
            if kind == "claim":
                tier = t["tier"]
                # 옛 서버(1.10.2 까지)에만 나온다 - 새 서버는 보상을 저절로 넣어 준다
                rid = button(cv, x2 - s(16), cy, text,
                             lambda tier=tier: self.act(lambda: self.app.api.guild_claim(tier), self._after_claim),
                             "blue", h=s(26))
                rx = rid.box[0]
            else:
                rid = cv.create_text(x2 - s(16), cy, text=text, fill="#2c8a3c" if kind == "claimed" else INK2,
                                     font=font(9), anchor="e")
                rx = cv.bbox(rid)[0]
            cv.create_text(x1 + s(156), cy, text=clamp_lines(cv, t.get("reward", ""), font(9),
                                                             max(s(40), rx - s(10) - x1 - s(156)), 1),
                           fill="#a05010" if reached else INK2, font=font(9), anchor="w")
            yy += s(28)
        y += ph + s(14)
        y = section(cv, x1, x2, y, "내 미션", "오늘 %d / %d점" % (int(ms.get("myPoints") or 0),
                                                            int(ms.get("myMax") or 0)))
        missions = ms.get("missions") or []
        lh = s(36)
        total = max(1, len(missions)) * lh + s(8)
        card(cv, x1, y, x2, y + total)
        yy = y + s(4)
        f10 = K.tkfont_of(cv, font(10))
        for i, m in enumerate(missions):
            cy = yy + lh // 2
            if i:
                cv.create_line(x1 + s(14), yy, x2 - s(14), yy, fill=ROW_LINE)
            done = m.get("done")
            cv.create_text(x1 + s(16) + 10, cy, text="☑" if done else "☐", fill="#2c8a3c" if done else "#9aa6b6",
                           font=font(14))
            bx = x1 + s(16)
            pts = "+%d점" % int(m.get("points") or 0)
            cnt = "%d / %d" % (int(m.get("n") or 0), int(m.get("goal") or 0))
            right = f10.measure(pts) + f10.measure(cnt) + s(30)
            K.text(cv, bx + s(28), cy, clamp_lines(cv, m.get("name", ""), font(10), x2 - bx - s(44) - right, 1),
                   font(10), fill=INK2 if done else INK, anchor="w")
            pid = cv.create_text(x2 - s(16), cy, text=pts, fill="#2c8a3c" if done else "#c06810", font=font(10),
                                 anchor="e")
            cv.create_text(cv.bbox(pid)[0] - s(14), cy, text=cnt, fill="#2c8a3c" if done else INK2,
                           font=font(10), anchor="e")
            yy += lh
        return y + total + s(12)

    # ---------------- 코인 상점
    def _fill_shop(self):
        s = U.h
        sh = self.shop or {}
        have = int(sh.get("coin") or 0)
        self.h_coin.configure(text="길드 코인 %s개" % format(have, ","))
        self.shop_q = tk.StringVar(value=self.shop_query)
        self.shop_cards = [(it, None) for it in sh.get("items") or []]
        self.shop_btns = {}
        # 머리 (찾는 칸은 굴러가는 목록 밖에 둔다 - 적는 동안 목록만 다시 그린다)
        self.shop_head = tk.Canvas(self.content, bg=BASE_BG, highlightthickness=0, bd=0, height=s(56))
        self.shop_head.pack(fill="x", padx=(s(12), s(22)), pady=(s(8), 0))
        self.shop_box = K.entry(self.shop_head, self.shop_q, width=14)
        self._shop_win = self.shop_head.create_window(0, 0, window=self.shop_box, anchor="ne")
        self.shop_head.bind("<Configure>", lambda _e: self._paint_shop_head())
        self._page(self.content, self._draw_shop)
        self.shop_q.trace_add("write", lambda *_a: self._shop_search())

    def _paint_shop_head(self):
        cv, s = self.shop_head, U.h
        try:
            w = cv.winfo_width()
            cv.delete("bg")
        except tk.TclError:
            return
        if w <= 1:
            return
        sh = self.shop or {}
        tg = ("bg",)
        bw = s(170)
        ph = poke_icons.photo("amulet-coin")
        cv.create_image(11, s(15), image=ph, tags=tg)
        K.text(cv, 22 + s(8), s(15), "길드 코인 %s개" % format(int(sh.get("coin") or 0), ","), font(12),
               fill="#c06810", anchor="w", tags=tg)
        note = "일일 미션의 단계 보상으로 모읍니다. 길드를 나가도 남습니다."
        nw = max(60, w - bw - s(30))
        K.text(cv, 0, s(32), note, font(9), fill=INK2, anchor="nw", width=nw, tags=tg)
        want = max(s(52), s(32) + K.text_height(cv, note, font(9), nw) + s(8))
        if int(cv.cget("height")) != want:
            cv.configure(height=want)
        cv.coords(self._shop_win, w, s(1))
        cv.itemconfigure(self._shop_win, width=bw, height=s(30))
        cv.create_text(w - bw - s(8), s(16), text="찾기", fill=INK2, font=font(10), anchor="e", tags=tg)
        if self.shop_query.strip():
            cv.create_text(w, s(44), text="%d개" % len(self.shop_shown()), fill=INK2, font=font(9), anchor="e",
                           tags=tg)

    def _shop_layout(self, width=None):
        if self.dpage is not None:
            self.dpage.redraw()

    def _shop_search(self):
        try:
            self.shop_query = self.shop_q.get() or ""
        except tk.TclError:
            return
        self._paint_shop_head()
        if self.dpage is not None:
            self.dpage.redraw(keep=False)

    def _shop_resized(self, width):
        pass

    def _draw_shop(self, cv, w):
        s = U.h
        sh = self.shop or {}
        have = int(sh.get("coin") or 0)
        bag = sh.get("bag") or {}
        x1, x2 = s(2), w - s(10)
        q = self.shop_query
        shown = self.shop_shown()
        y = s(2)
        if not shown:
            K.text(cv, (x1 + x2) // 2, y + s(30), ("'%s' (이)가 들어간 도구가 없습니다." % q.strip()) if q.strip()
                   else "살 수 있는 도구가 없습니다.", font(10), fill=INK2, anchor="n")
            return y + s(80)
        f10 = K.tkfont_of(cv, font(10))
        f9 = K.tkfont_of(cv, font(9))
        # 단추 자리 (줄마다 같다) - 글은 남은 폭에 맞추고, 설명은 줄을 바꿔 다 보인다 (줄 높이가 그만큼 는다)
        bws = [f10.measure("%d개 사기" % n) + s(22) for n in (10, 1)]
        tx = x1 + s(64)
        room = x2 - s(14) - sum(bws) - s(6) * 2 - tx - s(8)

        def note_of(it):
            return natural(it.get("note") or it.get("heldNote") or it.get("desc") or "")
        hts = [max(s(66), s(32) + (K.text_height(cv, note_of(it), font(9), room) if note_of(it) else 0) + s(12))
               for it in shown]
        card(cv, x1, y, x2, y + sum(hts) + s(8))
        yy = y + s(4)
        for i, it in enumerate(shown):
            iid = it["id"]
            rh = hts[i]
            price = int(it.get("coin") or 0)
            if i:
                cv.create_line(x1 + s(12), yy, x2 - s(12), yy, fill=ROW_LINE)
            ph = item_icons.photo(iid, G.SHOP_ICON)
            if ph is not None:
                cv.create_image(x1 + s(34), yy + rh // 2, image=ph)
            bx = x2 - s(14)
            for n in (10, 1):
                b = button(cv, bx, yy + rh // 2, "%d개 사기" % n, (lambda n=n, iid=iid: self.buy(iid, n)), "blue",
                           enabled=have >= price * n, h=s(30))
                self.shop_btns[(iid, n)] = b
                bx -= b.w + s(6)
            price_t = "코인 %d" % price
            owned = int(bag.get(iid) or 0)
            own_t = ("가진 것 %d" % owned) if owned else ""
            extra = f10.measure(price_t) + s(10) + (f9.measure(own_t) + s(10) if owned else 0)
            name = clamp_lines(cv, it.get("kr", iid), font(11), max(s(60), room - extra), 1)
            nid = K.text(cv, tx, yy + s(19), name, font(11), anchor="w")[1]
            pid = cv.create_text(cv.bbox(nid)[2] + s(10), yy + s(19), text=price_t,
                                 fill="#c06810" if have >= price else "#d02828", font=font(10), anchor="w")
            if owned:
                cv.create_text(cv.bbox(pid)[2] + s(10), yy + s(19), text=own_t, fill=INK2, font=font(9), anchor="w")
            note = note_of(it)
            if note:
                K.text(cv, tx, yy + s(32), note, font(9), fill=INK2, anchor="nw", width=room)
            yy += rh
        return y + sum(hts) + s(20)

    # ---------------- 다른 길드 · 길드 찾기
    def _finder(self, parent, title="길드 찾기"):
        s = U.h
        self.q_var = tk.StringVar(value=self.query)
        self._finder_title = title
        head = tk.Canvas(parent, bg=BASE_BG, highlightthickness=0, bd=0, height=s(70))
        head.pack(fill="x", padx=(s(12), s(22)), pady=(s(8), 0))
        self.find_head = head
        self.find_box = K.entry(head, self.q_var, width=16)
        self.find_box.entry.bind("<Return>", lambda _e: self.do_search())
        self._find_win = head.create_window(0, 0, window=self.find_box, anchor="nw")
        self.find_btn = K.CButton(head, "찾기", self.do_search, "blue", font(10))
        head.bind("<Configure>", lambda _e: self._paint_find_head())
        self._page(parent, self._draw_finder)
        self.list = self.dpage.frame
        self.list_fit = None
        self.pager = None
        if self.found is None:
            self.load_list()
        else:
            self._fill_list()

    def _paint_find_head(self):
        cv, s = self.find_head, U.h
        try:
            w = cv.winfo_width()
            cv.delete("bg")
        except tk.TclError:
            return
        if w <= 1:
            return
        y = section(cv, 0, w, 0, self._finder_title, "이름 일부만 적어도 됩니다", tags=("bg",))
        bw = self.find_btn.want_width(s(24))
        self.find_btn.layout(w - bw - 1, y, w - 1, y + s(30))
        cv.coords(self._find_win, 0, y)
        cv.itemconfigure(self._find_win, width=w - bw - s(8), height=s(30))
        want = y + s(30) + s(4)
        if int(cv.cget("height")) != want:
            cv.configure(height=want)

    def _fill_list(self):
        if self.dpage is not None:
            self.dpage.redraw(keep=False)

    def _draw_finder(self, cv, w):
        s = U.h
        f = self.found or {}
        x1, x2 = s(2), w - s(10)
        y = s(2)
        if self.found is None:
            K.text(cv, (x1 + x2) // 2, y + s(20), "불러오는 중...", font(10), fill=INK2, anchor="n")
            return y + s(60)
        rows = f.get("guilds") or []
        wait = int((self.data or {}).get("cooldown") or 0)
        if not rows:
            K.text(cv, (x1 + x2) // 2, y + s(20), ("'%s' (이)가 들어간 길드가 없습니다." % f.get("query"))
                   if f.get("query") else "아직 길드가 없습니다. 첫 길드를 만들어 보세요!", font(10), fill=INK2,
                   anchor="n")
            y += s(60)
        inner = x2 - x1 - s(32)
        for g in rows:
            intro = g.get("intro") or "소개가 없습니다."
            ih = K.text_height(cv, intro, font(9), inner)
            ph = s(12) + s(24) + s(4) + s(16) + s(8) + ih + s(12)
            card(cv, x1, y, x2, y + ph, line="#e0a060" if g.get("requested") else GLINE,
                 width=2 if g.get("requested") else 1)
            cy = y + s(12) + s(12)
            act = self._guild_action(g, wait)
            right = 0
            if act[0] == "mine":
                right = chip_w(cv, act[1])
                chip(cv, x2 - s(16) - right, cy, act[1], "#e07a28")
            elif act[0] == "cancel":
                right = button(cv, x2 - s(14), cy, act[1], act[2], "gray", h=s(28)).w
            elif act[0] == "full":
                right = K.tkfont_of(cv, font(9)).measure(act[1])
                cv.create_text(x2 - s(16), cy, text=act[1], fill=INK2, font=font(9), anchor="e")
            elif act[0] == "join":
                right = button(cv, x2 - s(14), cy, act[1], act[2], "red", enabled=act[3], h=s(28)).w
            mode = G.MODE_KR.get(g.get("joinMode"), "")
            room = x2 - x1 - s(30) - right - s(12) - (chip_w(cv, mode) + s(8) if mode else 0)
            nid = K.text(cv, x1 + s(16), cy, clamp_lines(cv, g["name"], font(12), room, 1), font(12), anchor="w")[1]
            if mode:
                chip(cv, cv.bbox(nid)[2] + s(8), cy, mode, "#7a8698")
            ly = cy + s(12) + s(4) + s(8)
            pid = cv.create_text(x1 + s(16), ly, text="%d / %d명" % (g.get("members", 0), g.get("max", 0)),
                                 fill="#d02828" if g.get("full") else INK, font=font(9), anchor="w")
            cv.create_text(cv.bbox(pid)[2] + s(12), ly, text="마스터 %s  ·  누적 %s점" % (
                g.get("masterName", "?"), format(int(g.get("points") or 0), ",")), fill=INK2, font=font(9),
                anchor="w")
            K.text(cv, x1 + s(16), ly + s(8) + s(8), intro, font(9), fill=INK2 if g.get("intro") else DIM,
                   anchor="nw", width=inner)
            y += ph + s(8)
        # 쪽 넘기기
        pages = int(f.get("pages") or 1)
        cy = y + s(18)
        cv.create_text(x1 + s(4), cy, text="길드 %d곳" % int(f.get("total") or 0), fill=INK2, font=font(9), anchor="w")
        if pages > 1:
            bx = x2 - button(cv, x2, cy, "▶", lambda: self.turn(1), "gray", enabled=self.page < pages, h=s(28)).w
            tid = cv.create_text(bx - s(10), cy, text="%d / %d" % (self.page, pages), fill=INK, font=font(10),
                                 anchor="e")
            button(cv, cv.bbox(tid)[0] - s(10), cy, "◀", lambda: self.turn(-1), "gray", enabled=self.page > 1, h=s(28))
        return y + s(44)

    # ---------------- 길드가 없을 때
    def _draw_none(self):
        s = U.h
        self._ensure_status()
        self.body.configure(bg=BASE_BG)
        n = self._none_data()
        top = tk.Canvas(self.body, bg=BASE_BG, highlightthickness=0, bd=0, height=s(90))
        top.pack(fill="x", padx=(s(12), s(22)), pady=(s(10), 0))
        self.none_cv = top
        self.b_create = None

        def draw(_e=None):
            try:
                w = top.winfo_width()
            except tk.TclError:
                return
            if w <= 1:
                return
            drop_buttons(top)
            top.delete("all")
            bw = K.tkfont_of(top, font(12)).measure("길드 만들기") + s(22)
            inner = w - s(40) - bw - s(16)
            th = K.text_height(top, n["text"], font(10), inner)
            extra = [(n["wait"], "#d02828", None, None)] if n["wait"] else []
            if n["coin"]:
                extra.append((n["coin"], INK2, "코인 상점", self.open_coinshop))
            extra += [(t, "#a05010", "신청 취소", fn) for t, fn in n["pending"]]
            body_h = max(th, s(44))
            hh = s(18) + body_h + s(14) + len(extra) * s(38) + s(6)
            if int(top.cget("height")) != hh:
                top.configure(height=hh)
            K.rrect(top, 1, 1, w - 2, s(24), s(8), fill=EARTH)                   # 흙빛 띠 (비밀기지 문패)
            card(top, 1, s(5), w - 2, hh - 2)
            K.text(top, s(18), s(18), n["text"], font(10), fill=INK, anchor="nw", width=inner)
            self.b_create = button(top, w - s(18), s(18) + s(22), "길드 만들기", self.create_dialog, "red",
                                   enabled=n["can"], spec=font(12), h=s(42))
            y = s(18) + body_h + s(14)
            for text, col, label, fn in extra:
                bw2 = 0
                if label:
                    bw2 = button(top, w - s(18), y + s(15), label, fn, "gray", h=s(28)).w
                K.text(top, s(18), y + s(15), clamp_lines(top, text, font(9), w - s(50) - bw2, 2), font(9), fill=col,
                       anchor="w")
                y += s(38)
        top.bind("<Configure>", draw)
        self._finder(self.body)

    def _draw_coinshop_only(self):
        s = U.h
        self._ensure_status()
        self.body.configure(bg=BASE_BG)
        bar = tk.Canvas(self.body, bg=BASE_BG, highlightthickness=0, bd=0, height=s(46))
        bar.pack(fill="x")
        b = K.CButton(bar, "← 길드 찾기", self.close_coinshop, "gray", font(10))
        bar.bind("<Configure>", lambda _e: b.layout(s(12), s(8), s(12) + b.want_width(s(24)), s(40)))
        self.content = tk.Frame(self.body, bg=BASE_BG)
        self.content.pack(fill="both", expand=True)
        self._tab_shop()

    # ---------------- 관리
    def _tab_manage(self):
        d = self.data or {}
        g = d.get("guild") or {}
        self.v_intro = tk.StringVar(value=self._keep.pop("intro", g.get("intro") or ""))
        self._page(self.content, self._draw_manage)
        # 입력칸은 목록 캔버스의 자식이다 (create_window). 다시 그려도 칸은 그대로라 쓰던 글이 남는다.
        self.intro_box = K.entry(self.dpage.cv, self.v_intro)
        self.intro_box.entry.bind("<Return>", lambda _e: self.save_intro())

    def _draw_manage(self, cv, w):
        s = U.h
        d = self.data or {}
        g = d.get("guild") or {}
        can = d.get("can") or {}
        x1, x2 = s(2), w - s(10)
        inner = x2 - x1 - s(32)
        y = s(2)
        if can.get("manage"):
            reqs = d.get("requests") or []
            y = section(cv, x1, x2, y, "가입 신청", "%d건" % len(reqs))
            rh = s(44)
            h = max(1, len(reqs)) * rh + s(8)
            card(cv, x1, y, x2, y + h)
            if not reqs:
                cv.create_text(x1 + s(16), y + h // 2, text="기다리는 가입 신청이 없습니다." if g.get("joinMode") == "approve"
                               else "자유 가입 길드입니다. 누구나 바로 들어옵니다.", fill=INK2, font=font(9), anchor="w")
            yy = y + s(4)
            for i, r in enumerate(reqs):
                cy = yy + rh // 2
                if i:
                    cv.create_line(x1 + s(12), yy, x2 - s(12), yy, fill=ROW_LINE)
                uid = r["id"]
                bx = x2 - s(14)
                bx -= button(cv, bx, cy, "거절", lambda u=uid: self.act(lambda: self.app.api.guild_reject(u)), "gray",
                             h=s(28)).w + s(6)
                bx -= button(cv, bx, cy, "받기", lambda u=uid: self.act(lambda: self.app.api.guild_accept(u)), "blue",
                             h=s(28)).w + s(6)
                bx -= button(cv, bx, cy, "프로필", lambda u=uid: self.profile_dialog(u), "gray", h=s(28)).w + s(10)
                tier = r.get("tierKr") if r.get("ranked") else ""
                tier_w = (chip_w(cv, tier) + s(8)) if tier else 0
                nid = K.text(cv, x1 + s(16), cy, clamp_lines(cv, r["name"], font(11), bx - x1 - s(30) - tier_w, 1),
                             font(11), anchor="w")[1]
                xx = cv.bbox(nid)[2] + s(8)
                if tier:
                    xx += chip(cv, xx, cy, tier, "#7a8698") + s(8)
                if r.get("message") and bx - xx > s(30):
                    cv.create_text(xx, cy, text=clamp_lines(cv, r["message"], font(9), bx - xx, 1), fill=INK2,
                                   font=font(9), anchor="w")
                yy += rh
            y += h + s(14)
        if can.get("master"):
            y = section(cv, x1, x2, y, "소개", "길드 찾기와 길드 화면에 보입니다")
            bw = button(cv, x2, y + s(16), "저장", self.save_intro, "blue", h=s(32)).w
            cv.create_window(x1, y + s(1), window=self.intro_box, anchor="nw", width=x2 - x1 - bw - s(8),
                             height=s(30))
            y += s(46)
            y = section(cv, x1, x2, y, "가입 방식")
            nh = K.text_height(cv, self.MODE_NOTE, font(9), inner)
            mh = s(12) + s(30) + s(10) + nh + s(12)
            card(cv, x1, y, x2, y + mh)
            xx = x1 + s(16)
            cur = g.get("joinMode") or "open"
            f = K.tkfont_of(cv, font(10))
            for key, lb in (("open", "자유 가입"), ("approve", "승인 필요")):
                tw = f.measure(lb) + s(26)
                on = key == cur
                tag = "mode_" + key
                K.rrect(cv, xx, y + s(12), xx + tw, y + s(42), s(6), fill=WHITE if on else "#f2f4f7",
                        outline=CUR if on else LINE, width=2 if on else 1, tags=(tag,))
                cv.create_text(xx + tw // 2, y + s(27), text=lb, fill=CUR if on else INK, font=font(10),
                               tags=(tag,))
                if not on:
                    cv.hits[tag] = (lambda k=key: self.set_mode(k))
                xx += tw + s(8)
            K.text(cv, x1 + s(16), y + s(52), self.MODE_NOTE, font(9), fill=INK2, anchor="nw", width=inner)
            y += mh + s(14)
        y = section(cv, x1, x2, y, "길드 나가기")
        text, can_leave, can_disband = self._leave_data()
        rows = [(text, "길드 나가기" if can_leave else None, self.leave)]
        if can_disband:
            rows.append((self.DISBAND_NOTE, "길드 해산", self.disband))
        f10 = K.tkfont_of(cv, font(10))
        laid = []
        for t, label, fn in rows:
            bw = (f10.measure(label) + s(22)) if label else 0
            tw = inner - (bw + s(12) if bw else 0)
            laid.append((t, label, fn, tw, max(K.text_height(cv, t, font(9), tw), s(32)) + s(20)))
        h = sum(r[4] for r in laid)
        card(cv, x1, y, x2, y + h)
        yy = y
        self.b_leave = self.b_disband = None
        for i, (t, label, fn, tw, rh) in enumerate(laid):
            if i:
                cv.create_line(x1 + s(12), yy, x2 - s(12), yy, fill=ROW_LINE)
            if label:
                b = button(cv, x2 - s(14), yy + rh // 2, label, fn, "red", h=s(32))
                if fn == self.leave:
                    self.b_leave = b
                else:
                    self.b_disband = b
            K.text(cv, x1 + s(16), yy + rh // 2, t, font(9), fill=INK, anchor="w", width=tw)
            yy += rh
        return y + h + s(16)
