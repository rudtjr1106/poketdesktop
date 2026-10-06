# -*- coding: utf-8 -*-
"""길드 창 (1.10.0).

길드가 없으면 **찾기·만들기**, 있으면 다섯 칸이다:

    채팅      길드원끼리 주고받는 말. 띄워 둔 동안 2초마다 새 줄을 받아 온다
    길드원    누가 있고 오늘 얼마나 했나. 프로필 보기, (마스터·부마스터는) 관리
    미션      오늘의 미션과 길드 점수, 단계 보상 받기
    코인 상점 길드 코인으로 사는 곳
    관리      가입 신청 받기, 소개·가입 방식, 나가기·해산

**채팅은 웹소켓으로 받는다** (guild_ws.GuildSocket). 길드에 들어 있는 동안 붙어 있고,
서버가 새 줄과 길드 소식(사람·신청·점수·소개가 바뀜, 내보내짐)을 밀어 준다. 그래서
다른 칸을 보고 있어도 새 말이 오면 '채팅' 옆에 수가 붙고, 다른 탭에 가 있으면 길드 탭에
점이 찍힌다.

**웹소켓이 안 붙으면 폴링으로 돈다** (회사·학교 망, 서버를 새로 올리는 사이). 채팅 칸이
화면에 보이는 동안만 2초마다 '이 번호 뒤의 줄' 을 묻고, 응답의 stamp 가 달라지면 전체를
다시 받는다. 두 길은 줄 번호로 겹치는 것을 걸러서 섞여도 한 줄이 두 번 뜨지 않는다.

머리줄 단추에는 위아래 여백을 주지 않는다 (ui_raid._header 의 설명 - 윈도우에서 눌린다).
"""
import datetime
import tkinter as tk

from common.korean import natural

from . import guild_ws as WS
from . import ui_common as U
from .ui_common import run_async

W, H = 760, 680
CHAT_MS = 2000              # 채팅을 물어보는 간격
CHAT_KEEP = 400             # 화면에 남겨 두는 줄 수
CARD = "#161b28"
PROFILE_W, PROFILE_H = 440, 460     # 프로필 창. 높이는 '넘지 않는' 값이다 - 넘치면 안쪽이 굴러간다
PROFILE_BAR = 16                    # 굴러가는 막대의 몫
TABS = (("chat", "채팅"), ("members", "길드원"), ("mission", "미션"),
        ("shop", "코인 상점"), ("manage", "관리"))
MODE_KR = {"open": "자유 가입", "approve": "승인 필요"}
ROLE_COLOR = {"master": U.ACCENT, "sub": U.INFO}


def _err(e):
    return getattr(e, "message", None) or str(e)


def make_socket(app, on_event):
    """이 앱의 서버에 붙는 웹소켓. 붙을 수 없으면 None (라이브러리가 없거나 시험용 앱).

    None 이면 화면은 그냥 폴링으로 돈다. 검사는 이 함수를 바꿔 끼운다.
    """
    api = getattr(app, "api", None)
    base, token = getattr(api, "base", None), getattr(api, "token", None)
    if not (WS.available() and base and token):
        return None
    return WS.GuildSocket(app.root, base, token, on_event).start()


def span(sec):
    """남은 시간을 말로. 3 * 3600 + 720 -> '3시간 12분'."""
    sec = max(0, int(sec or 0))
    h, m = sec // 3600, (sec % 3600) // 60
    if h:
        return "%d시간 %d분" % (h, m) if m else "%d시간" % h
    return "%d분" % max(1, m)


def clock(iso):
    """'2026-10-06T03:04:05+00:00' -> 내 PC 시각으로 '12:04'. 모르면 빈 문자열."""
    try:
        return datetime.datetime.fromisoformat(iso).astimezone().strftime("%H:%M")
    except (TypeError, ValueError):
        return ""


def seen_text(m):
    """길드원 한 줄의 접속 표시."""
    if m.get("online"):
        return "접속 중", U.GOOD
    ago = m.get("lastSeenAgo")
    if ago is None:
        return "", U.FG_FAINT
    if ago < 3600:
        return "%d분 전" % max(1, ago // 60), U.FG_FAINT
    if ago < 86400:
        return "%d시간 전" % (ago // 3600), U.FG_FAINT
    return "%d일 전" % (ago // 86400), U.FG_FAINT


class GuildWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.alive = True
        self.data = None
        self.tab = "chat"
        self.mode = None              # none / guild / coinshop (길드 없이 코인 상점만)
        self._gen = 0
        self._busy = False
        self.query = ""
        self.page = 1
        self.found = None             # 길드 찾기 결과
        self.shop = None
        # 채팅
        self.chat_last = 0
        self.chat_box = None
        self.chat_var = None
        self._chat_job = None
        self._chat_busy = False
        self._stamp = None
        self.chat_ready = False       # 지난 줄을 처음 한 번 받았나
        self._pending = []            # 지난 줄을 받는 사이에 밀려온 줄
        self.chat_state = None
        # 웹소켓
        self.sock = None
        self.live = False             # 지금 웹소켓이 붙어 있나 (아니면 폴링)
        self.my_id = None
        self.unread = 0               # 채팅 칸을 안 보는 사이에 온 줄 수
        self._reload_job = None
        self._keep = {}               # 관리 칸을 다시 그릴 때 쓰던 글
        self._badged = False          # 허브의 길드 탭에 점을 찍어 두었나

        self.win = U.panel(parent, self.root, "포스크탑 — 길드", W, H, 620, 520, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)
        self._header()
        self.status = U.status_line(self.win, "")
        self.status.pack(side="bottom", fill="x", padx=16, pady=(6, 12))
        self.body = tk.Frame(self.win, bg=U.BG)
        self.body.pack(fill="both", expand=True)
        tk.Label(self.body, text="불러오는 중...", bg=U.BG, fg=U.FG_FAINT,
                 font=U.FONT_S).pack(pady=30)
        self.load()
        self._chat_tick()

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=U.h(62))
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)
        tk.Label(inner, text="길드", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(15))).pack(side="left")
        self.h_name = tk.Label(inner, text="", bg=U.BG2, fg=U.ACCENT_TEXT, font=U.FONT_B)
        self.h_name.pack(side="left", padx=(12, 0))
        # 단추에 pady 를 주지 않는다 (머리말).
        U.ghost_button(inner, "새로고침", self.refresh, height=32).pack(side="right")
        self.h_coin = tk.Label(inner, text="", bg=U.BG2, fg=U.ACCENT, font=U.FONT_S)
        self.h_coin.pack(side="right", padx=(0, 14))
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

    def say(self, text, color=U.GOOD):
        if self.alive:
            U.set_status(self.status, natural(text or ""), color)

    # ---------------- 자료 ----------------
    def refresh(self):
        self.shop = None
        self.found = None
        self.load()

    def load(self, quiet=False):
        """길드 화면에 쓸 것을 다시 받는다. quiet 면 채팅 칸은 건드리지 않는다."""
        self._gen += 1
        gen = self._gen
        api = self.app.api

        def done(r, err):
            if not self.alive or gen != self._gen:
                return
            if err:
                return self.say(_err(err), U.DANGER)
            self.data = r or {}
            self._stamp = self.data.get("stamp")
            self.draw(keep_chat=quiet)
            if not quiet:
                self.say("")
        run_async(self.root, lambda: api.guild(), done)

    def act(self, fn, then=None):
        """서버에 무언가를 시키고, 되면 한마디 띄우고 다시 받는다."""
        if self._busy:
            return
        self._busy = True

        def done(r, err):
            self._busy = False
            if not self.alive:
                return
            if err:
                return self.say(_err(err), U.DANGER)
            self.say((r or {}).get("message") or "", U.GOOD)
            if then:
                then(r or {})
            else:
                self.shop = None
                self.found = None
                self.load()
        run_async(self.root, fn, done)

    # ---------------- 그리기 ----------------
    def _clear(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def in_guild(self):
        return bool((self.data or {}).get("guild"))

    def draw(self, keep_chat=False):
        d = self.data or {}
        g = d.get("guild")
        self.h_coin.configure(text="길드 코인 %s개" % format(int(d.get("coin") or 0), ","))
        self.h_name.configure(text=g["name"] if g else "")
        self.my_id = d.get("me", self.my_id)
        if not g:
            if self.mode != "coinshop":
                self.mode = "none"
            self._stop_socket()
            self.unread = 0
            self._badge(False)
            self.chat_box = None
            self.chat_last = 0
            self._clear(self.body)
            if self.mode == "coinshop":
                return self._draw_coinshop_only()
            return self._draw_none()
        was = self.mode
        self.mode = "guild"
        self._ensure_socket()
        if keep_chat and was == "guild" and self.tab == "chat" and self.chat_box is not None:
            return self._paint_info()         # 채팅 칸은 그대로 두고 머리만 고친다
        if keep_chat and was == "guild" and self.tab == "manage":
            # 소개를 쓰는 도중에 누가 미션을 끝냈다고 쓰던 글이 날아가면 안 된다
            for key in ("intro",):
                var = getattr(self, "v_" + key, None)
                try:
                    if var is not None and var.get() != (g.get(key) or ""):
                        self._keep[key] = var.get()
                except tk.TclError:
                    pass
        self._clear(self.body)
        self.chat_box = None
        self._draw_guild()

    # ================================================================ 길드가 없을 때
    def _draw_none(self):
        d = self.data or {}
        top = U.framed(self.body, bg=CARD)
        top.pack(fill="x", padx=16, pady=(14, 0))
        row = tk.Frame(top, bg=CARD)
        row.pack(fill="x", padx=14, pady=12)
        cost = int(d.get("createCost") or 0)
        wait = int(d.get("cooldown") or 0)
        self.b_create = U.PushButton(row, "길드 만들기", self.create_dialog, height=34,
                                     font=U.FONT_B)
        self.b_create.pack(side="right", padx=(12, 0))
        if wait > 0:
            self.b_create.configure(state="disabled")
        text = ("길드에 들어가면 길드원끼리 채팅하고, 일일 미션을 함께 모아 몬스터볼과 "
                "길드 코인을 받습니다. 길드를 만들려면 %s원이 듭니다 (정원 %d명)."
                % (format(cost, ","), int(d.get("max") or 0)))
        lb = tk.Label(row, text=text, bg=CARD, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                      justify="left")
        lb.pack(side="left", fill="x", expand=True)
        U.wrap_to_width(lb)
        if wait > 0:
            tk.Label(top, text="길드를 나온 지 얼마 안 됐습니다. %s 뒤에 다시 가입하거나 만들 수 "
                               "있습니다." % span(wait), bg=CARD, fg=U.DANGER, font=U.FONT_XS,
                     anchor="w").pack(fill="x", padx=14, pady=(0, 10))
        if int(d.get("coin") or 0) > 0:
            r2 = tk.Frame(top, bg=CARD)
            r2.pack(fill="x", padx=14, pady=(0, 10))
            tk.Label(r2, text="길드 코인이 %d개 남아 있습니다. 길드가 없어도 쓸 수 있습니다."
                              % int(d["coin"]), bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS,
                     anchor="w").pack(side="left")
            U.ghost_button(r2, "코인 상점", self.open_coinshop, height=28).pack(side="right")
        for p in d.get("pending") or []:
            r3 = tk.Frame(top, bg=CARD)
            r3.pack(fill="x", padx=14, pady=(0, 10))
            tk.Label(r3, text="%s 길드에 가입 신청을 넣어 두었습니다. 승인을 기다리는 중입니다."
                              % p["name"], bg=CARD, fg=U.ACCENT_TEXT, font=U.FONT_XS,
                     anchor="w").pack(side="left")
            U.ghost_button(r3, "신청 취소",
                           lambda gid=p["guildId"]: self.act(lambda: self.app.api.guild_cancel(gid)),
                           height=28).pack(side="right")

        # 찾기
        bar = tk.Frame(self.body, bg=U.BG)
        bar.pack(fill="x", padx=16, pady=(14, 6))
        U.marker_label(bar, "길드 찾기", bg=U.BG, color=U.FG).pack(side="left")
        self.q_var = tk.StringVar(value=self.query)
        U.ghost_button(bar, "찾기", self.do_search, height=30).pack(side="right")
        box = U.entry(bar, self.q_var, width=16)
        box.pack(side="right", padx=(0, 8))
        box.entry.bind("<Return>", lambda _e: self.do_search())
        tk.Label(bar, text="이름 일부만 적어도 됩니다", bg=U.BG, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="right", padx=(0, 10))

        self.pager = tk.Frame(self.body, bg=U.BG)
        self.pager.pack(side="bottom", fill="x", padx=16, pady=(6, 0))
        self.list, self.list_fit = self._scroll(self.body)
        if self.found is None:
            self.load_list()
        else:
            self._fill_list()

    def _scroll(self, parent, pad=16):
        """굴러가는 칸 하나. (안쪽 틀, 맞추는 것) 을 돌려준다."""
        wrap = tk.Frame(parent, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=pad, pady=(4, 0))
        cv = tk.Canvas(wrap, bg=U.BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=U.BG)
        wid = cv.create_window((0, 0), window=inner, anchor="nw")
        fit = U.scroll_fitter(cv, inner, wid)
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        U.scrollable(cv, 120)
        return inner, fit

    def do_search(self):
        self.query = (self.q_var.get() or "").strip()
        self.page = 1
        self.load_list()

    def turn(self, delta):
        self.page = max(1, self.page + delta)
        self.load_list()

    def load_list(self):
        gen = self._gen
        api = self.app.api
        q, page = self.query, self.page

        def done(r, err):
            if not self.alive or gen != self._gen or self.mode != "none":
                return
            if err:
                return self.say(_err(err), U.DANGER)
            self.found = r or {}
            self.page = int(self.found.get("page") or 1)
            self._fill_list()
        run_async(self.root, lambda: api.guild_list(q, page), done)

    def _fill_list(self):
        f = self.found or {}
        self._clear(self.list)
        self._clear(self.pager)
        rows = f.get("guilds") or []
        wait = int((self.data or {}).get("cooldown") or 0)
        if not rows:
            tk.Label(self.list, text=("'%s' (이)가 들어간 길드가 없습니다." % f.get("query"))
                     if f.get("query") else "아직 길드가 없습니다. 첫 길드를 만들어 보세요!",
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S).pack(pady=24)
        for g in rows:
            self._guild_card(g, wait)
        pages = int(f.get("pages") or 1)
        if pages > 1:
            b = U.ghost_button(self.pager, "▶", lambda: self.turn(1), height=28)
            b.pack(side="right")
            if self.page >= pages:
                b.configure(state="disabled")
            tk.Label(self.pager, text="%d / %d" % (self.page, pages), bg=U.BG, fg=U.FG_DIM,
                     font=U.FONT_S).pack(side="right", padx=10)
            b = U.ghost_button(self.pager, "◀", lambda: self.turn(-1), height=28)
            b.pack(side="right")
            if self.page <= 1:
                b.configure(state="disabled")
        tk.Label(self.pager, text="길드 %d곳" % int(f.get("total") or 0), bg=U.BG,
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left")
        self.list_fit.fit_now()

    def _guild_card(self, g, wait):
        c = U.framed(self.list, bg=U.BG3)
        c.pack(fill="x", pady=3)
        row = tk.Frame(c, bg=U.BG3)
        row.pack(fill="x", padx=12, pady=(9, 2))
        tk.Label(row, text=g["name"], bg=U.BG3, fg=U.FG, font=U.FONT_B).pack(side="left")
        U.chip(row, MODE_KR.get(g.get("joinMode"), ""), U.BG4, fg=U.FG, padx=7).pack(
            side="left", padx=(8, 0))
        tk.Label(row, text="%d / %d명" % (g.get("members", 0), g.get("max", 0)), bg=U.BG3,
                 fg=U.DANGER if g.get("full") else U.FG_DIM, font=U.FONT_S).pack(
            side="left", padx=(10, 0))
        tk.Label(row, text="마스터 %s" % g.get("masterName", "?"), bg=U.BG3, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="left", padx=(10, 0))
        gid = g["id"]
        if g.get("requested"):
            U.ghost_button(row, "신청 취소",
                           lambda: self.act(lambda: self.app.api.guild_cancel(gid)),
                           height=28).pack(side="right")
        elif g.get("full"):
            tk.Label(row, text="가득 참", bg=U.BG3, fg=U.FG_FAINT, font=U.FONT_S).pack(side="right")
        else:
            label = "가입" if g.get("joinMode") == "open" else "가입 신청"
            b = U.ghost_button(row, label, lambda: self.join(g), height=28,
                               fill=U.ACCENT_DARK, fg=U.ACCENT)
            b.pack(side="right")
            if wait > 0:
                b.configure(state="disabled")
        lb = tk.Label(c, text=g.get("intro") or "소개가 없습니다.", bg=U.BG3,
                      fg=U.FG_DIM if g.get("intro") else U.FG_FAINT, font=U.FONT_XS,
                      anchor="w", justify="left")
        lb.pack(fill="x", padx=12, pady=(0, 9))
        U.wrap_to_width(lb)

    def join(self, g):
        from .ui_box import ask_text, confirm
        gid = g["id"]
        if g.get("joinMode") == "open":
            if not confirm(self.win, "길드 가입", "%s 길드에 들어갈까요?" % g["name"],
                           danger=False, ok_text="가입"):
                return
            return self.act(lambda: self.app.api.guild_join(gid))
        msg = ask_text(self.win, "가입 신청", "%s 길드에 가입 신청을 넣습니다." % g["name"],
                       "마스터에게 남길 한마디 (안 적어도 됩니다)")
        if msg is None:
            return
        self.act(lambda: self.app.api.guild_join(gid, msg))

    def create_dialog(self):
        """길드 만들기: 이름·소개·가입 방식을 묻는다."""
        from .ui_box import _shell, fit
        d = self.data or {}
        cost = int(d.get("createCost") or 0)
        lim = (d.get("limits") or {}).get("name") or [2, 12]
        win, f = _shell(self.win, "길드 만들기", 440, 372)
        name, intro = tk.StringVar(), tk.StringVar()
        mode = {"v": "open"}
        tk.Label(f, text="길드 이름 (%d~%d자)" % (lim[0], lim[1]), bg=U.BG, fg=U.FG_DIM,
                 font=U.FONT_S, anchor="w").pack(fill="x")
        e1 = U.entry(f, name)
        e1.pack(fill="x", pady=(6, 12))
        tk.Label(f, text="소개 (길드 찾기에 보입니다)", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                 anchor="w").pack(fill="x")
        U.entry(f, intro).pack(fill="x", pady=(6, 12))
        r = tk.Frame(f, bg=U.BG)
        r.pack(fill="x")
        tk.Label(r, text="가입 방식", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(side="left")
        seg = U.Segmented(r, [("open", "자유 가입"), ("approve", "승인 필요")], "open", None)

        def pick(k):
            mode["v"] = k
            seg.set(k)
        seg.on_pick = pick
        seg.frame.pack(side="left", padx=(12, 0))
        have = int(d.get("money") or 0)
        note = tk.Label(f, text="만드는 데 %s원이 듭니다. (지금 %s원)"
                        % (format(cost, ","), format(have, ",")), bg=U.BG,
                        fg=U.FG_FAINT if have >= cost else U.DANGER, font=U.FONT_XS, anchor="w")
        note.pack(fill="x", pady=(12, 0))
        warn = tk.Label(f, text="", bg=U.BG, fg=U.DANGER, font=U.FONT_XS, anchor="w",
                        justify="left", wraplength=390)
        warn.pack(fill="x", pady=(4, 0))
        self._dialog = {"win": win, "name": name, "intro": intro, "mode": mode, "warn": warn}

        def complain(text):
            """까닭을 적는다. 두 줄이 되면 창이 그만큼만 늘어난다 (단추가 안 눌리게)."""
            try:
                warn.configure(text=natural(text))
                fit(win, keep_pos=True)
            except tk.TclError:
                pass

        def ok():
            n = name.get().strip()
            if not n:
                return complain("길드 이름을 적어 주세요.")
            api = self.app.api
            i, m = intro.get().strip(), mode["v"]

            def done(res, err):
                if err:
                    return complain(_err(err))
                try:
                    win.destroy()
                except tk.TclError:
                    pass
                self.say((res or {}).get("message") or "", U.GOOD)
                self.found = None
                self.tab = "chat"
                self.load()
                try:
                    self.app.request_sync()        # 돈이 줄었다 - 다른 화면도 맞춘다
                except Exception:                           # noqa: BLE001
                    pass
            run_async(self.root, lambda: api.guild_create(n, i, m), done)
        row = tk.Frame(f, bg=U.BG)
        row.pack(side="bottom", fill="x", pady=(12, 0))
        U.PushButton(row, "만들기", ok, height=34, font=U.FONT_B).pack(side="right")
        U.ghost_button(row, "취소", win.destroy, height=34).pack(side="right", padx=(0, 8))
        self._dialog["ok"] = ok
        win.after(60, lambda: e1.entry.focus_set())
        fit(win)                    # 창은 내용만큼만 (372 로 박아 두면 아래가 비었다)
        return win

    # ---------------- 길드 없이 코인 상점만 ----------------
    def open_coinshop(self):
        self.mode = "coinshop"
        self.draw()

    def _draw_coinshop_only(self):
        bar = tk.Frame(self.body, bg=U.BG)
        bar.pack(fill="x", padx=16, pady=(12, 0))
        U.ghost_button(bar, "← 길드 찾기", self.close_coinshop, height=30).pack(side="left")
        self.content = tk.Frame(self.body, bg=U.BG)
        self.content.pack(fill="both", expand=True)
        self._tab_shop()

    def close_coinshop(self):
        self.mode = "none"
        self.draw()

    # ================================================================ 길드가 있을 때
    def _draw_guild(self):
        self.info = tk.Frame(self.body, bg=U.BG)
        self.info.pack(fill="x", padx=16, pady=(12, 0))
        self._paint_info()
        bar = tk.Frame(self.body, bg=U.BG)
        bar.pack(fill="x", padx=16, pady=(10, 0))
        self.seg = U.Segmented(bar, list(TABS), self.tab, self.show_tab)
        self.seg.frame.pack(side="left")
        self.content = tk.Frame(self.body, bg=U.BG)
        self.content.pack(fill="both", expand=True)
        self._draw_tab()

    def _paint_info(self):
        d = self.data or {}
        g = d.get("guild") or {}
        self._clear(self.info)
        c = U.framed(self.info, bg=CARD)
        c.pack(fill="x")
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(row, text=g.get("name", ""), bg=CARD, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(14))).pack(side="left")
        U.chip(row, d.get("roleKr") or "", ROLE_COLOR.get(d.get("role"), U.BG4),
               fg=U.ACCENT_DARK if d.get("role") in ROLE_COLOR else U.FG, padx=7).pack(
            side="left", padx=(10, 0))
        U.chip(row, MODE_KR.get(g.get("joinMode"), ""), U.BG4, fg=U.FG, padx=7).pack(
            side="left", padx=(6, 0))
        tk.Label(row, text="길드원 %d / %d명" % (g.get("members", 0), g.get("max", 0)), bg=CARD,
                 fg=U.FG_DIM, font=U.FONT_S).pack(side="left", padx=(12, 0))
        tk.Label(row, text="누적 %s점" % format(int(g.get("points") or 0), ","), bg=CARD,
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left", padx=(12, 0))
        n = len(d.get("requests") or [])
        if n:
            tk.Label(row, text="가입 신청 %d건" % n, bg=CARD, fg=U.ACCENT, font=U.FONT_S).pack(
                side="right")
        intro = g.get("intro") or ""
        lb = tk.Label(c, text=intro or "소개가 없습니다.", bg=CARD,
                      fg=U.FG_DIM if intro else U.FG_FAINT, font=U.FONT_S,
                      anchor="w", justify="left")
        lb.pack(fill="x", padx=14, pady=(0, 10))
        U.wrap_to_width(lb)

    def show_tab(self, key):
        if key == self.tab and self.mode == "guild":
            return
        self.tab = key
        try:
            self.seg.set(key)
        except Exception:                                   # noqa: BLE001
            pass
        self._draw_tab()

    def _draw_tab(self):
        self._clear(self.content)
        self.chat_box = None
        self.chat_state = None
        self.chat_ready = False
        self._pending = []
        if self.tab == "chat":
            self.unread = 0
        self._paint_unread()
        getattr(self, "_tab_" + self.tab)()

    # ---------------- 채팅 ----------------
    def _tab_chat(self):
        d = self.data or {}
        limit = int((d.get("limits") or {}).get("chat") or 200)
        send = tk.Frame(self.content, bg=U.BG)
        send.pack(side="bottom", fill="x", padx=16, pady=(8, 0))
        self.chat_var = tk.StringVar()
        U.PushButton(send, "보내기", self.send_chat, height=34, font=U.FONT_B).pack(side="right")
        box = U.entry(send, self.chat_var)
        box.pack(side="left", fill="x", expand=True, padx=(0, 8))
        box.entry.bind("<Return>", lambda _e: self.send_chat())
        self.chat_entry = box.entry
        self.chat_limit = limit
        # 지금 어느 길로 받고 있나. 말이 늦게 오는 것 같을 때 까닭을 알 수 있다.
        self.chat_state = tk.Label(self.content, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS,
                                   anchor="e")
        self.chat_state.pack(side="bottom", fill="x", padx=16, pady=(4, 0))
        self._paint_state()

        wrap = U.framed(self.content, bg=U.INK)
        wrap.pack(fill="both", expand=True, padx=16, pady=(10, 0))
        sb = tk.Scrollbar(wrap, orient="vertical")
        t = tk.Text(wrap, bg=U.INK, fg=U.FG, font=U.FONT, wrap="word", relief="flat", bd=0,
                    highlightthickness=0, padx=12, pady=10, state="disabled", cursor="arrow",
                    yscrollcommand=sb.set, spacing1=2, spacing3=2, height=6)
        sb.configure(command=t.yview)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        t.tag_configure("time", foreground=U.FG_FAINT, font=U.FONT_XS)
        t.tag_configure("name", foreground=U.INFO, font=U.FONT_B)
        t.tag_configure("mine", foreground=U.ACCENT, font=U.FONT_B)
        t.tag_configure("body", foreground=U.FG)
        t.tag_configure("system", foreground=U.FG_FAINT, font=U.FONT_S, justify="center")
        t.wheel_div = 40               # 창의 휠 처리(U.install_wheel)가 이 칸을 굴린다
        self.chat_box = t
        self.chat_last = 0
        self.chat_lines = 0
        self.chat_ready = False
        self._pending = []
        self._poll_chat(first=True)

    def _add_lines(self, msgs):
        """새 줄을 붙인다. **이미 붙인 번호는 건너뛴다** - 웹소켓으로 온 줄과 폴링으로 온 줄이
        겹쳐도 한 번만 뜬다. 줄 번호가 곧 순서다."""
        fresh = []
        for m in msgs or []:
            mid = int(m.get("id") or 0)
            if mid <= self.chat_last:
                continue
            self.chat_last = mid
            if "mine" not in m:
                m = dict(m, mine=(m.get("userId") is not None and m.get("userId") == self.my_id))
            fresh.append(m)
        self._append(fresh)
        return fresh

    def _append(self, msgs):
        t = self.chat_box
        if t is None or not msgs:
            return
        try:
            at_end = t.yview()[1] >= 0.999
            t.configure(state="normal")
            for m in msgs:
                if self.chat_lines:
                    t.insert("end", "\n")
                if m.get("system"):
                    t.insert("end", "— %s —" % m.get("body", ""), ("system",))
                else:
                    t.insert("end", "%s  " % clock(m.get("at")), ("time",))
                    t.insert("end", "%s  " % m.get("name", "?"),
                             ("mine" if m.get("mine") else "name",))
                    t.insert("end", m.get("body", ""), ("body",))
                self.chat_lines += 1
            if self.chat_lines > CHAT_KEEP:              # 오래 띄워 두면 줄이 끝없이 쌓인다
                cut = self.chat_lines - CHAT_KEEP
                t.delete("1.0", "%d.0" % (cut + 1))
                self.chat_lines -= cut
            t.configure(state="disabled")
            if at_end:
                t.see("end")
        except tk.TclError:
            pass

    def chat_text(self):
        """채팅 칸에 지금 적힌 글 (검사용)."""
        try:
            return self.chat_box.get("1.0", "end-1c") if self.chat_box is not None else ""
        except tk.TclError:
            return ""

    def chat_visible(self):
        """채팅 칸이 지금 화면에 보이나. 안 보이면 서버에 묻지 않는다."""
        if not self.alive or self.mode != "guild" or self.tab != "chat" or self.chat_box is None:
            return False
        try:
            return bool(self.chat_box.winfo_viewable())
        except tk.TclError:
            return False

    def _chat_tick(self):
        if not self.alive:
            return
        # 웹소켓이 붙어 있으면 밀려오는 것만 받는다. 끊겨 있을 때만 묻는다.
        if self.chat_visible() and not self.live:
            self._poll_chat()
        if self._badged and self.pane_visible():
            self._badge(False)               # 길드 탭으로 돌아왔다 - 탭의 점은 지운다
        try:
            self._chat_job = self.root.after(CHAT_MS, self._chat_tick)
        except Exception:                                   # noqa: BLE001
            self._chat_job = None

    def _poll_chat(self, first=False):
        if self._chat_busy or self.chat_box is None:
            return
        self._chat_busy = True
        box, after, api = self.chat_box, self.chat_last, self.app.api

        def done(r, err):
            self._chat_busy = False
            if not self.alive or self.chat_box is not box:
                return                       # 그사이 칸을 다시 그렸다 - 이 답은 버린다
            if err:
                if first:
                    self.say(_err(err), U.DANGER)
                return
            r = r or {}
            if r.get("guild") is None:
                return self.load()           # 그사이 길드에서 나왔다 (내보내졌거나 해산)
            self._add_lines(r.get("messages") or [])
            self.chat_last = max(self.chat_last, int(r.get("last") or 0))
            # 이 답을 기다리는 사이에 웹소켓으로 밀려온 줄. 답보다 먼저 붙이면 답에 든
            # 앞 번호의 줄이 '이미 지난 번호' 로 걸러져 사라진다 - 그래서 답 뒤에 붙인다.
            self.chat_ready = True
            pend, self._pending = self._pending, []
            self._add_lines(pend)
            if first:
                try:
                    box.see("end")
                except tk.TclError:
                    pass
            stamp = r.get("stamp")
            if stamp and self._stamp and stamp != self._stamp:
                self.load(quiet=True)        # 사람·신청·점수가 바뀌었다
            elif stamp and not self._stamp:
                self._stamp = stamp
        run_async(self.root, lambda: api.guild_chat(after), done)

    def send_chat(self):
        text = " ".join((self.chat_var.get() or "").split())
        if not text:
            return
        if len(text) > self.chat_limit:
            return self.say("한 번에 %d자까지 보낼 수 있습니다." % self.chat_limit, U.DANGER)
        self.chat_var.set("")
        api = self.app.api

        def done(_r, err):
            if not self.alive:
                return
            if err:
                self.chat_var.set(text)      # 못 보냈으면 쓴 것을 돌려놓는다
                return self.say(_err(err), U.DANGER)
            if not self.live:
                self._poll_chat()            # 웹소켓이 붙어 있으면 내 말도 밀려온다
        run_async(self.root, lambda: api.guild_say(text), done)

    # ---------------- 웹소켓 ----------------
    def _ensure_socket(self):
        """길드에 들어 있는 동안 붙어 있는다. 서버가 '다시 오지 마라' 로 끊었던 것은 새로 만든다
        (길드가 없을 때 붙었다가 4404 로 끊긴 뒤 길드에 들어온 경우)."""
        if self.sock is not None and getattr(self.sock, "gave_up", None):
            self._stop_socket()
        if self.sock is None:
            try:
                self.sock = make_socket(self.app, self._on_ws)
            except Exception:                               # noqa: BLE001
                self.sock = None             # 못 만들면 폴링으로 돈다

    def _stop_socket(self):
        if self.sock is not None:
            try:
                self.sock.stop()
            except Exception:                               # noqa: BLE001
                pass
        self.sock = None
        self.live = False

    def _on_ws(self, ev):
        """웹소켓이 넘겨준 일 하나 (Tk 스레드에서 불린다)."""
        if not self.alive:
            return
        t = ev.get("t")
        if t == "open":
            self.live = True
            self._paint_state()
            if self.chat_box is not None:
                self._poll_chat()            # 끊겨 있던 사이의 줄을 한 번 받아 온다
            return
        if t == "closed":
            self.live = False
            return self._paint_state()
        if t == "left":
            self.live = False
            return self.load()               # 내보내졌거나 해산됐다
        if t == "changed":
            return self._reload_soon()
        if t == "chat":
            m = ev.get("m") or {}
            if self.chat_box is None:
                # 다른 칸을 보고 있다. 줄은 채팅 칸을 열 때 받고, 여기서는 수만 센다.
                if m.get("userId") != self.my_id and not m.get("system"):
                    self.unread += 1
                    self._paint_unread()
                    if not self.pane_visible():
                        self._badge(True)
                return
            if not self.chat_ready or self._chat_busy:
                return self._pending.append(m)       # 지난 줄을 받는 중이다 - 그 뒤에 붙인다
            fresh = self._add_lines([m])
            if fresh and not self.pane_visible() and m.get("userId") != self.my_id \
                    and not m.get("system"):
                self.unread += 1
                self._badge(True)

    def _reload_soon(self):
        """'바뀌었다' 가 연달아 와도 한 번만 다시 받는다."""
        if self._reload_job is not None:
            return

        def go():
            self._reload_job = None
            if self.alive and self.in_guild():
                self.load(quiet=True)
        try:
            self._reload_job = self.root.after(250, go)
        except Exception:                                   # noqa: BLE001
            self._reload_job = None

    def pane_visible(self):
        """길드 탭이 지금 화면에 보이나 (다른 탭에 가 있거나 창을 가리면 False)."""
        try:
            return bool(self.body.winfo_viewable())
        except tk.TclError:
            return False

    def _badge(self, on):
        """허브의 '길드' 탭에 점을 찍거나 지운다. **바뀔 때만** 허브를 건드린다."""
        on = bool(on)
        if on != self._badged:
            self._badged = on
            hub = getattr(self.app, "hub", None)
            if hub is not None:
                try:
                    hub.set_badge("guild", on)
                except Exception:                           # noqa: BLE001
                    pass
        if not on and self.tab == "chat":
            self.unread = 0

    def _paint_unread(self):
        """'채팅' 칸 이름 옆에 안 읽은 수."""
        seg = getattr(self, "seg", None)
        try:
            if seg is not None and "chat" in seg.cells:
                seg.cells["chat"].configure(
                    text="채팅 %d" % self.unread if self.unread and self.tab != "chat" else "채팅")
        except tk.TclError:
            pass

    def _paint_state(self):
        lb = self.chat_state
        if lb is None:
            return
        try:
            if self.live:
                lb.configure(text="● 실시간으로 받는 중", fg=U.GOOD)
            else:
                lb.configure(text="○ 2초마다 받아 오는 중", fg=U.FG_FAINT)
        except tk.TclError:
            pass

    # ---------------- 길드원 ----------------
    def _tab_members(self):
        d = self.data or {}
        inner, fit = self._scroll(self.content)
        for m in d.get("members") or []:
            self._member_row(inner, m, d)
        fit.fit_now()

    def _member_row(self, parent, m, d):
        c = U.framed(parent, bg=U.BG3)
        c.pack(fill="x", pady=3)
        row = tk.Frame(c, bg=U.BG3)
        row.pack(fill="x", padx=12, pady=9)
        dot = tk.Canvas(row, width=10, height=10, bg=U.BG3, highlightthickness=0, bd=0)
        dot.create_oval(1, 1, 9, 9, fill=U.GOOD if m.get("online") else U.BG4, outline="")
        dot.pack(side="left")
        tk.Label(row, text=m["name"], bg=U.BG3, fg=m.get("frameColor") or U.FG,
                 font=U.FONT_B).pack(side="left", padx=(8, 6))
        if m.get("role") in ROLE_COLOR:
            U.chip(row, m.get("roleKr") or "", ROLE_COLOR[m["role"]], fg=U.ACCENT_DARK,
                   padx=6).pack(side="left", padx=(0, 6))
        if m.get("title"):
            tk.Label(row, text=m["title"], bg=U.BG3, fg=m.get("frameColor") or U.ACCENT_TEXT,
                     font=U.FONT_XS).pack(side="left", padx=(0, 6))
        text, color = seen_text(m)
        if text:
            tk.Label(row, text=text, bg=U.BG3, fg=color, font=U.FONT_XS).pack(side="left")
        uid = m["id"]
        can = d.get("can") or {}
        mine = m.get("me")
        manage = (not mine) and m.get("role") != "master" and (
            can.get("master") or (can.get("manage") and m.get("role") == "member"))
        if manage:
            U.ghost_button(row, "관리", lambda: self.manage_dialog(m), height=28).pack(side="right")
        U.ghost_button(row, "프로필", lambda: self.profile_dialog(uid), height=28).pack(
            side="right", padx=(0, 6))
        tk.Label(row, text="오늘 %d점 · 누적 %s점" % (m.get("today", 0),
                                                 format(int(m.get("points") or 0), ",")),
                 bg=U.BG3, fg=U.ACCENT if m.get("today") else U.FG_FAINT,
                 font=U.FONT_S).pack(side="right", padx=(0, 12))

    def member_actions(self, m):
        """이 길드원에게 내가 할 수 있는 일. [(단추 글자, 할 일, 위험한가, 되묻는 말)]"""
        d = self.data or {}
        can = d.get("can") or {}
        api, uid, name = self.app.api, m["id"], m["name"]
        out = []
        if m.get("me") or m.get("role") == "master":
            return out
        if can.get("master"):
            if m.get("role") == "member":
                out.append(("부마스터로 임명", lambda: api.guild_role(uid, "sub"), False,
                            "%s 님을 부마스터로 임명할까요? 부마스터는 가입 신청을 받고 "
                            "길드원을 내보낼 수 있습니다." % name))
            else:
                out.append(("부마스터 해제", lambda: api.guild_role(uid, "member"), False,
                            "%s 님을 일반 길드원으로 되돌릴까요?" % name))
            out.append(("마스터 넘기기", lambda: api.guild_master(uid), True,
                        "%s 님에게 길드 마스터를 넘길까요? 넘기고 나면 되돌릴 수 없습니다 "
                        "(새 마스터가 다시 넘겨줘야 합니다)." % name))
        if can.get("master") or (can.get("manage") and m.get("role") == "member"):
            out.append(("길드에서 내보내기", lambda: api.guild_kick(uid), True,
                        "%s 님을 길드에서 내보낼까요? 내보내진 사람은 %d시간 동안 다른 길드에 "
                        "들어갈 수 없습니다." % (name, int(d.get("rejoinHours") or 24))))
        return out

    def manage_dialog(self, m):
        from .ui_box import _shell, confirm, fit
        acts = self.member_actions(m)
        if not acts:
            return None
        win, f = _shell(self.win, "길드원 관리", 380, 150 + 46 * len(acts))
        tk.Label(f, text="%s  (%s)" % (m["name"], m.get("roleKr") or ""), bg=U.BG, fg=U.FG,
                 font=U.FONT_B, anchor="w").pack(fill="x", pady=(0, 10))

        def run(fn, danger, ask, label):
            try:
                win.destroy()
            except tk.TclError:
                pass
            if confirm(self.win, label, ask, danger=danger, ok_text=label.split()[0]
                       if len(label) > 8 else label):
                self.act(fn)
        for label, fn, danger, ask in acts:
            make = U.danger_button if danger else U.ghost_button
            make(f, label, lambda fn=fn, danger=danger, ask=ask, label=label:
                 run(fn, danger, ask, label), height=34).pack(fill="x", pady=(0, 8))
        U.ghost_button(f, "닫기", win.destroy, height=32).pack(side="bottom", anchor="e",
                                                                 pady=(4, 0))
        fit(win)                    # 단추가 하나든 셋이든 딱 그만큼
        return win

    def profile_dialog(self, uid):
        """길드원 프로필. **마이페이지에 보이는 것**(포켓몬·도감·관장·시즌 기록·칭호)을 보여 준다.

        내용이 길다. 창을 키우지 않고 **안쪽을 굴린다** - 창은 PROFILE_H 를 넘지 않고,
        내용이 그보다 짧으면 그만큼 줄어든다.
        """
        from .ui_box import _shell, fit, scroll_body
        win, f = _shell(self.win, "트레이너 프로필", PROFILE_W, PROFILE_H)
        U.ghost_button(f, "닫기", win.destroy, height=32).pack(side="bottom", anchor="e",
                                                                 pady=(10, 0))
        inner, cv = scroll_body(f)
        wait = tk.Label(inner, text="불러오는 중...", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S)
        wait.pack(pady=20)
        win.profile = None
        api = self.app.api

        def done(p, err):
            try:
                wait.destroy()
                if err:
                    tk.Label(inner, text=natural(_err(err)), bg=U.BG, fg=U.DANGER,
                             font=U.FONT_S, wraplength=PROFILE_W - 80, justify="left").pack(
                        anchor="w")
                else:
                    win.profile = p or {}
                    self._fill_profile(inner, cv, win.profile)
                fit(win, hi=PROFILE_H, scroll=(cv, inner), keep_pos=True)
            except tk.TclError:
                pass                        # 받아 오는 사이에 창을 닫았다
        run_async(self.root, lambda: api.guild_profile(uid), done)
        return win

    def _fill_profile(self, inner, cv, p):
        from . import ui_mypage as MP
        u, g = p.get("user") or {}, p.get("guild") or {}
        # 안쪽 폭. 굴러가는 막대가 뜨면 그만큼 좁아지므로 막대 몫을 미리 빼고 잡는다 -
        # 글이 막대 밑으로 들어가서 잘리는 것보다 오른쪽이 조금 비는 편이 낫다.
        width = PROFILE_W - 4 - 36 - PROFILE_BAR
        pad = (0, 6)
        # 카드 안의 글이 접히는 폭. 카드 오른쪽 여백 6 + 테두리 2 + 안쪽 여백 14x2, 그리고
        # **라벨 자신의 여백 6**(tk 기본 padx 1 + bd 2, 양쪽)을 뺀다. 처음에는 30 만 뺐는데,
        # 윈도우 글꼴에서는 한 줄이 351 로 나와 칸(347)을 4px 넘겼다 (CI 윈도우 잡이 잡음).
        wrap = width - 6 - 2 - 28 - 6 - 2

        box = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=U.ACCENT_SHADOW)
        box.pack(fill="x", padx=pad)
        top = tk.Frame(box, bg=CARD)
        top.pack(fill="x", padx=14, pady=(12, 2))
        tk.Label(top, text=u.get("name") or "?", bg=CARD, fg=u.get("frameColor") or U.FG,
                 font=(U.FAMILY_BLACK, U.pt(15))).pack(side="left")
        if u.get("tierKr"):
            U.chip(top, u["tierKr"], U.BG4, fg=U.FG, font=U.FONT_XS, padx=7).pack(
                side="left", padx=(8, 0))
        text, color = seen_text(g)
        if text:
            tk.Label(top, text=text, bg=CARD, fg=color, font=U.FONT_XS).pack(side="right")
        for line, fg, font in profile_head(p):
            tk.Label(box, text=line, bg=CARD, fg=fg, font=font, anchor="w", justify="left",
                     wraplength=wrap).pack(fill="x", padx=14, pady=(2, 0))
        tk.Frame(box, bg=CARD, height=U.h(10)).pack(fill="x")

        # 숫자 칸. 마이페이지는 셋씩 놓지만 이 창은 좁아서 둘씩 놓는다 (글자를 줄이지 않는다).
        grid = tk.Frame(inner, bg=U.BG)
        grid.pack(fill="x", pady=(8, 0), padx=pad)
        cols = 2
        for i in range(cols):
            grid.columnconfigure(i, weight=1, uniform="tile")
        for i, (name, value, note) in enumerate(MP.tile_items(p)):
            t = tk.Frame(grid, bg=MP.TILE, highlightthickness=1, highlightbackground=U.LINE)
            t.grid(row=i // cols, column=i % cols, sticky="nsew",
                   padx=(0 if i % cols == 0 else 8, 0), pady=(0, 8))
            tk.Label(t, text=name, bg=MP.TILE, fg=U.FG_DIM, font=U.FONT_XS, anchor="w").pack(
                fill="x", padx=12, pady=(8, 0))
            tk.Label(t, text=value, bg=MP.TILE, fg=U.FG, font=U.FONT_H, anchor="w").pack(
                fill="x", padx=12)
            tk.Label(t, text=note or " ", bg=MP.TILE, fg=U.FG_FAINT, font=U.FONT_XS,
                     anchor="w").pack(fill="x", padx=12, pady=(0, 8))

        def section(title, note=""):
            head = tk.Frame(inner, bg=U.BG)
            head.pack(fill="x", pady=(8, 6), padx=pad)
            U.marker_label(head, title, bg=U.BG, color=U.FG).pack(side="left")
            if note:
                tk.Label(head, text=note, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS).pack(
                    side="left", padx=(10, 0))
            b = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=U.LINE)
            b.pack(fill="x", padx=pad)
            return b

        box = section("시즌 기록")
        rows = p.get("seasons") or []
        for i, sn in enumerate(rows):
            head, body = MP.season_line(sn)
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", padx=14, pady=(10 if i == 0 else 0, 10))
            tk.Label(row, text=head, bg=CARD, fg=U.ACCENT if sn.get("current") else U.FG,
                     font=U.FONT_B, anchor="w").pack(fill="x")
            tk.Label(row, text=body, bg=CARD, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                     justify="left", wraplength=wrap).pack(fill="x", pady=(2, 0))
        if not rows:
            tk.Label(box, text="시즌 기록이 없습니다.", bg=CARD, fg=U.FG_FAINT, font=U.FONT_S,
                     anchor="w").pack(fill="x", padx=14, pady=12)

        t = p.get("titles") or {}
        own = t.get("owned") or []
        box = section("칭호", "%d / %d" % (int(t.get("count") or 0), int(t.get("total") or 0)))
        if not own:
            tk.Label(box, text="아직 가진 칭호가 없습니다.", bg=CARD, fg=U.FG_FAINT,
                     font=U.FONT_S, anchor="w").pack(fill="x", padx=14, pady=12)
        else:
            flow = MP.Flow(box, CARD)
            flow.frame.pack(fill="x", padx=14, pady=12)
            for c in own:
                on = c.get("name") == t.get("equipped")
                flow.add(tk.Label(flow.frame, text=c.get("name") or "", font=U.FONT_S, padx=9,
                                  pady=U.h(3), bg=U.ACCENT if on else U.BG4,
                                  fg=U.ACCENT_DARK if on else U.FG))
            # 칩이 몇 줄이 될지는 폭을 알아야 나온다. 창 높이를 재기 전에 여기서 놓는다.
            flow.place(width - 30)
        tk.Frame(inner, bg=U.BG, height=U.h(4)).pack(fill="x")

    # ---------------- 미션 ----------------
    def _tab_mission(self):
        d = self.data or {}
        ms = d.get("mission") or {}
        inner, fit = self._scroll(self.content)

        box = U.framed(inner, bg=CARD)
        box.pack(fill="x", pady=(6, 0))
        head = tk.Frame(box, bg=CARD)
        head.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(head, text="오늘의 길드 점수", bg=CARD, fg=U.FG, font=U.FONT_B).pack(side="left")
        tk.Label(head, text="%d점" % int(ms.get("guildPoints") or 0), bg=CARD, fg=U.ACCENT,
                 font=U.FONT_H).pack(side="left", padx=(10, 0))
        tk.Label(head, text="%s 뒤에 새로 시작합니다" % span(ms.get("resetIn")), bg=CARD,
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(side="right")
        self.bar = tk.Canvas(box, height=U.h(16), bg=CARD, highlightthickness=0, bd=0)
        self.bar.pack(fill="x", padx=14, pady=(0, 4))
        self.bar.bind("<Configure>", lambda _e: self._paint_bar())
        tk.Label(box, text="길드원이 미션을 하면 점수가 길드에 모입니다. 단계를 넘을 때마다, 오늘 "
                           "미션을 하나라도 한 길드원이 보상을 받습니다.", bg=CARD, fg=U.FG_FAINT,
                 font=U.FONT_XS, anchor="w", justify="left", wraplength=640).pack(
            fill="x", padx=14, pady=(0, 6))
        for t in ms.get("tiers") or []:
            self._tier_row(box, t, ms)
        tk.Frame(box, bg=CARD, height=U.h(8)).pack(fill="x")

        head = tk.Frame(inner, bg=U.BG)
        head.pack(fill="x", pady=(16, 6))
        U.marker_label(head, "내 미션", bg=U.BG, color=U.FG).pack(side="left")
        tk.Label(head, text="오늘 %d / %d점" % (int(ms.get("myPoints") or 0),
                                              int(ms.get("myMax") or 0)), bg=U.BG,
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left", padx=(10, 0))
        mine = U.framed(inner, bg=CARD)
        mine.pack(fill="x")
        for i, m in enumerate(ms.get("missions") or []):
            if i:
                tk.Frame(mine, bg=U.LINE, height=U.h(1)).pack(fill="x", padx=14)
            row = tk.Frame(mine, bg=CARD)
            row.pack(fill="x", padx=14, pady=8)
            done = m.get("done")
            tk.Label(row, text="✓" if done else "·", bg=CARD, fg=U.GOOD if done else U.FG_FAINT,
                     font=U.FONT_B, width=2).pack(side="left")
            tk.Label(row, text=m.get("name", ""), bg=CARD, fg=U.FG_DIM if done else U.FG,
                     font=U.FONT_S).pack(side="left")
            tk.Label(row, text="+%d점" % int(m.get("points") or 0), bg=CARD,
                     fg=U.GOOD if done else U.ACCENT, font=U.FONT_S).pack(side="right")
            tk.Label(row, text="%d / %d" % (int(m.get("n") or 0), int(m.get("goal") or 0)),
                     bg=CARD, fg=U.GOOD if done else U.FG_DIM, font=U.FONT_S).pack(
                side="right", padx=(0, 14))
        fit.fit_now()
        self._paint_bar()

    def _paint_bar(self):
        ms = (self.data or {}).get("mission") or {}
        cv = getattr(self, "bar", None)
        if cv is None:
            return
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
            if w <= 4:
                return
            cv.delete("all")
            top = float(ms.get("guildMax") or 1)
            cv.create_rectangle(0, 0, w, h, fill=U.INK, outline=U.LINE)
            fill = min(1.0, float(ms.get("guildPoints") or 0) / top)
            if fill > 0:
                cv.create_rectangle(1, 1, max(2, int((w - 1) * fill)), h - 1, fill=U.ACCENT,
                                    outline="")
            for t in ms.get("tiers") or []:
                x = int((w - 1) * min(1.0, float(t.get("need") or 0) / top))
                cv.create_line(x, 0, x, h, fill=U.FG if t.get("reached") else U.LINE2)
        except tk.TclError:
            pass

    def _tier_row(self, box, t, ms):
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", padx=14, pady=3)
        reached = t.get("reached")
        tk.Label(row, text="%d단계" % t["tier"], bg=CARD, fg=U.FG if reached else U.FG_DIM,
                 font=U.FONT_B, width=5, anchor="w").pack(side="left")
        tk.Label(row, text="%d점" % t["need"], bg=CARD, fg=U.FG_DIM, font=U.FONT_S, width=5,
                 anchor="w").pack(side="left")
        tk.Label(row, text=t.get("reward", ""), bg=CARD, fg=U.ACCENT_TEXT if reached else U.FG_DIM,
                 font=U.FONT_S).pack(side="left", padx=(6, 0))
        tier = t["tier"]
        if t.get("claimed"):
            tk.Label(row, text="받음", bg=CARD, fg=U.GOOD, font=U.FONT_S).pack(side="right")
        elif t.get("canClaim"):
            U.ghost_button(row, "받기", lambda: self.act(lambda: self.app.api.guild_claim(tier),
                                                        self._after_claim), height=28,
                           fill=U.ACCENT_DARK, fg=U.ACCENT).pack(side="right")
        elif reached:
            tk.Label(row, text="미션을 하나라도 하면 받을 수 있습니다", bg=CARD, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="right")
        else:
            tk.Label(row, text="%d점 남음" % max(0, t["need"] - int(ms.get("guildPoints") or 0)),
                     bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS).pack(side="right")

    def _after_claim(self, _r):
        self.shop = None
        self.load()
        try:
            self.app.request_sync()                # 몬스터볼 수가 바뀌었다
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------- 코인 상점 ----------------
    def _tab_shop(self):
        if self.shop is None:
            tk.Label(self.content, text="불러오는 중...", bg=U.BG, fg=U.FG_FAINT,
                     font=U.FONT_S).pack(pady=24)
            gen, api, mode, tab = self._gen, self.app.api, self.mode, self.tab

            def done(r, err):
                if not self.alive or gen != self._gen or self.mode != mode \
                        or (mode == "guild" and self.tab != tab):
                    return
                if err:
                    return self.say(_err(err), U.DANGER)
                self.shop = r or {}
                self._clear(self.content)
                self._fill_shop()
            return run_async(self.root, lambda: api.guild_shop(), done)
        self._fill_shop()

    def _fill_shop(self):
        s = self.shop or {}
        have = int(s.get("coin") or 0)
        self.h_coin.configure(text="길드 코인 %s개" % format(have, ","))
        head = tk.Frame(self.content, bg=U.BG)
        head.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(head, text="길드 코인 %s개" % format(have, ","), bg=U.BG, fg=U.ACCENT,
                 font=U.FONT_B).pack(side="left")
        tk.Label(head, text="일일 미션의 단계 보상으로 모읍니다. 길드를 나가도 남습니다.", bg=U.BG,
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left", padx=(12, 0))
        inner, fit = self._scroll(self.content)
        bag = s.get("bag") or {}
        self.shop_btns = {}           # {(도구, 몇 개): 단추} - 코인이 모자라면 꺼져 있다
        for it in s.get("items") or []:
            self._shop_row(inner, it, have, int(bag.get(it["id"]) or 0))
        fit.fit_now()

    def _shop_row(self, parent, it, have, owned):
        c = U.framed(parent, bg=U.BG3)
        c.pack(fill="x", pady=3)
        row = tk.Frame(c, bg=U.BG3)
        row.pack(fill="x", padx=12, pady=8)
        price = int(it.get("coin") or 0)
        iid = it["id"]
        for n in (10, 1):
            b = U.ghost_button(row, "%d개 사기" % n, lambda n=n: self.buy(iid, n), height=28)
            b.pack(side="right", padx=(6, 0))
            if have < price * n:
                b.configure(state="disabled")
            self.shop_btns[(iid, n)] = b
        tk.Label(row, text="코인 %d" % price, bg=U.BG3, fg=U.ACCENT if have >= price else U.DANGER,
                 font=U.FONT_B, width=8, anchor="e").pack(side="right", padx=(0, 6))
        tk.Label(row, text=it.get("kr", iid), bg=U.BG3, fg=U.FG, font=U.FONT_B).pack(side="left")
        if owned:
            tk.Label(row, text="가진 것 %d" % owned, bg=U.BG3, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left", padx=(8, 0))
        note = it.get("note") or it.get("heldNote") or it.get("desc") or ""
        if note:
            lb = tk.Label(c, text=natural(note), bg=U.BG3, fg=U.FG_FAINT, font=U.FONT_XS,
                          anchor="w", justify="left")
            lb.pack(fill="x", padx=12, pady=(0, 8))
            U.wrap_to_width(lb)

    def buy(self, item, n):
        def after(r):
            self.shop = None
            if self.mode == "guild":
                self._draw_tab()
            else:
                self.data["coin"] = r.get("coin", self.data.get("coin"))
                self.draw()
            try:
                self.app.request_sync()
            except Exception:                               # noqa: BLE001
                pass
        self.act(lambda: self.app.api.guild_buy(item, n), after)

    # ---------------- 관리 ----------------
    def _tab_manage(self):
        d = self.data or {}
        g = d.get("guild") or {}
        can = d.get("can") or {}
        inner, fit = self._scroll(self.content)

        if can.get("manage"):
            self._section(inner, "가입 신청", "%d건" % len(d.get("requests") or []))
            box = U.framed(inner, bg=CARD)
            box.pack(fill="x")
            reqs = d.get("requests") or []
            if not reqs:
                tk.Label(box, text="기다리는 가입 신청이 없습니다." if g.get("joinMode") == "approve"
                         else "자유 가입 길드입니다. 누구나 바로 들어옵니다.", bg=CARD,
                         fg=U.FG_FAINT, font=U.FONT_S, anchor="w").pack(fill="x", padx=14, pady=12)
            for i, r in enumerate(reqs):
                if i:
                    tk.Frame(box, bg=U.LINE, height=U.h(1)).pack(fill="x", padx=14)
                self._request_row(box, r)

        if can.get("master"):
            self._section(inner, "소개", "길드 찾기와 길드 화면 위쪽에 보입니다")
            self.v_intro = tk.StringVar(value=self._keep.pop("intro", g.get("intro") or ""))
            self._edit_row(inner, self.v_intro, self.save_intro)
            self._section(inner, "가입 방식")
            box = U.framed(inner, bg=CARD)
            box.pack(fill="x")
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", padx=14, pady=10)
            self.seg_mode = U.Segmented(row, [("open", "자유 가입"), ("approve", "승인 필요")],
                                        g.get("joinMode") or "open", self.set_mode)
            self.seg_mode.frame.pack(side="left")
            tk.Label(row, text="자유 가입은 누구나 바로 들어오고, 승인 필요는 마스터나 부마스터가 "
                               "받아 줘야 들어옵니다.", bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS,
                     anchor="w", justify="left", wraplength=420).pack(side="left", padx=(12, 0))

        self._section(inner, "길드 나가기")
        box = U.framed(inner, bg=CARD)
        box.pack(fill="x")
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", padx=14, pady=10)
        hours = int(d.get("rejoinHours") or 24)
        if can.get("master") and int(g.get("members") or 0) > 1:
            text = ("길드 마스터는 그냥 나갈 수 없습니다. 길드원 칸에서 마스터를 넘기거나, 아래에서 "
                    "길드를 해산해 주세요.")
        else:
            text = "나가면 %d시간 동안 다른 길드에 들어가거나 새로 만들 수 없습니다. 길드 코인은 남습니다." % hours
            if can.get("master"):
                text = "혼자 남은 마스터가 나가면 길드가 없어집니다. " + text
            self.b_leave = U.danger_button(row, "길드 나가기", self.leave, height=32)
            self.b_leave.pack(side="right", padx=(12, 0))
        lb = tk.Label(row, text=text, bg=CARD, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                      justify="left")
        lb.pack(side="left", fill="x", expand=True)
        U.wrap_to_width(lb)
        if can.get("master"):
            tk.Frame(box, bg=U.LINE, height=U.h(1)).pack(fill="x", padx=14)
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", padx=14, pady=10)
            self.b_disband = U.danger_button(row, "길드 해산", self.disband, height=32)
            self.b_disband.pack(side="right", padx=(12, 0))
            lb = tk.Label(row, text="길드와 채팅, 오늘의 미션 점수가 모두 사라집니다. 되돌릴 수 없습니다. "
                                    "만들 때 낸 돈은 돌아오지 않습니다.", bg=CARD, fg=U.FG_DIM,
                          font=U.FONT_S, anchor="w", justify="left")
            lb.pack(side="left", fill="x", expand=True)
            U.wrap_to_width(lb)
        tk.Frame(inner, bg=U.BG, height=U.h(12)).pack(fill="x")
        fit.fit_now()

    def _section(self, parent, title, note=""):
        head = tk.Frame(parent, bg=U.BG)
        head.pack(fill="x", pady=(14, 6))
        U.marker_label(head, title, bg=U.BG, color=U.FG).pack(side="left")
        if note:
            tk.Label(head, text=note, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS).pack(
                side="left", padx=(10, 0))

    def _edit_row(self, parent, var, save):
        row = tk.Frame(parent, bg=U.BG)
        row.pack(fill="x")
        U.ghost_button(row, "저장", save, height=34).pack(side="right")
        box = U.entry(row, var)
        box.pack(side="left", fill="x", expand=True, padx=(0, 8))
        box.entry.bind("<Return>", lambda _e: save())

    # **칸의 글은 여기(Tk 스레드)서 먼저 읽는다.** act 에 넘기는 함수는 작업 스레드에서
    # 돌기 때문에, 그 안에서 StringVar.get() 을 부르면 'main thread is not in main loop' 로 죽는다.
    def save_intro(self):
        text = self.v_intro.get()
        self.act(lambda: self.app.api.guild_settings(intro=text))

    def _request_row(self, box, r):
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", padx=14, pady=8)
        uid = r["id"]
        tk.Label(row, text=r["name"], bg=CARD, fg=U.FG, font=U.FONT_B).pack(side="left")
        if r.get("tierKr") and r.get("ranked"):
            U.chip(row, r["tierKr"], U.BG4, fg=U.FG, padx=6).pack(side="left", padx=(8, 0))
        if r.get("message"):
            tk.Label(row, text=r["message"], bg=CARD, fg=U.FG_DIM, font=U.FONT_S).pack(
                side="left", padx=(10, 0))
        U.ghost_button(row, "거절", lambda: self.act(lambda: self.app.api.guild_reject(uid)),
                       height=28).pack(side="right")
        U.ghost_button(row, "받기", lambda: self.act(lambda: self.app.api.guild_accept(uid)),
                       height=28, fill=U.ACCENT_DARK, fg=U.ACCENT).pack(side="right", padx=(0, 6))
        U.ghost_button(row, "프로필", lambda: self.profile_dialog(uid), height=28).pack(
            side="right", padx=(0, 6))

    def set_mode(self, mode):
        def after(_r):
            self.load()
        self.act(lambda: self.app.api.guild_settings(mode=mode), after)

    def leave(self):
        from .ui_box import confirm
        d = self.data or {}
        g = d.get("guild") or {}
        if not confirm(self.win, "길드 나가기", "%s 길드에서 나갈까요? %d시간 동안 다른 길드에 "
                       "들어갈 수 없습니다." % (g.get("name", ""), int(d.get("rejoinHours") or 24)),
                       ok_text="나가기"):
            return
        self.tab = "chat"
        self.act(lambda: self.app.api.guild_leave())

    def disband(self):
        from .ui_box import ask_text
        g = (self.data or {}).get("guild") or {}
        # 실수로 눌러 길드가 통째로 사라지지 않게, 이름을 그대로 적어야 한다.
        typed = ask_text(self.win, "길드 해산", "정말 해산하려면 길드 이름을 그대로 적어 주세요.",
                         "길드 이름: %s" % g.get("name", ""))
        if typed is None:
            return
        if typed.strip() != g.get("name"):
            return self.say("길드 이름이 다릅니다. 해산하지 않았습니다.", U.DANGER)
        self.tab = "chat"
        self.act(lambda: self.app.api.guild_disband())

    # ---------------- 끝 ----------------
    def focus(self):
        if U.is_embedded(self.win):
            return
        try:
            self.win.deiconify()
            self.win.lift()
        except Exception:                                   # noqa: BLE001
            pass

    def close(self):
        self.alive = False
        self._stop_socket()
        if self._reload_job is not None:
            try:
                self.root.after_cancel(self._reload_job)
            except Exception:                               # noqa: BLE001
                pass
            self._reload_job = None
        if self._chat_job is not None:
            try:
                self.root.after_cancel(self._chat_job)
            except Exception:                               # noqa: BLE001
                pass
            self._chat_job = None
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        if getattr(self.app, "guild_window", None) is self:
            self.app.guild_window = None


def profile_head(p):
    """프로필 맨 위 카드의 이름 아래 줄들: [(글, 색, 글꼴)]. 화면과 검사가 같이 쓴다."""
    from .ui_mypage import _date
    u, g = p.get("user") or {}, p.get("guild") or {}
    out = []
    if u.get("title"):
        out.append((u["title"], U.ACCENT_TEXT, U.FONT_S))
    bits = []
    if g.get("roleKr"):
        bits.append(g["roleKr"])
    if u.get("days"):
        bits.append("함께한 지 %d일째" % int(u["days"]))
    if _date(u.get("createdAt")):
        bits.append("%s 가입" % _date(u.get("createdAt")))
    if bits:
        out.append(("  ·  ".join(bits), U.FG_DIM, U.FONT_S))
    if g:
        out.append(("길드 미션  오늘 %d점  ·  누적 %s점" % (
            int(g.get("today") or 0), format(int(g.get("points") or 0), ",")),
            U.FG_FAINT, U.FONT_XS))
    return out
