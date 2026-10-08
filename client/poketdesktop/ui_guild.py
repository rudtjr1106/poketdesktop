# -*- coding: utf-8 -*-
"""길드 창 (1.10.0).

길드가 없으면 **찾기·만들기**, 있으면 다섯 칸이다:

    채팅      길드원끼리 주고받는 말. 띄워 둔 동안 2초마다 새 줄을 받아 온다.
              **길드 친선전도 여기서 한다** (1.10.3): `/친선전` 을 치면 상대를 구하는 카드가
              채팅에 놓이고, 길드원이 그 카드의 [배틀] 을 눌러 받는다. 판이 열리면 같은 카드가
              [관전] 으로 바뀐다 (무엇을 그릴지는 ui_spectate.chat_card)
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
from . import item_icons
from . import ui_common as U
from . import ui_spectate as SP
from .ui_common import run_async

W, H = 760, 680
CHAT_MS = 2000              # 채팅을 물어보는 간격
# 화면에 남겨 두는 줄 수. 넘으면 맨 위부터 걷는다 - 걷힌 줄은 위로 굴리면 다시 받아 온다.
# (1.10.3 전에는 400 이었고, 걷힌 줄은 다시 볼 길이 없었다.)
CHAT_KEEP = 3000
WEEKDAYS = "월화수목금토일"
CARD = "#161b28"
PROFILE_AVATAR = 2                  # 프로필 창의 캐릭터 배율 (32 x 2 = 64)
PROFILE_W, PROFILE_H = 440, 460     # 프로필 창. 높이는 '넘지 않는' 값이다 - 넘치면 안쪽이 굴러간다
PROFILE_BAR = 16                    # 굴러가는 막대의 몫
# 채팅에 놓이는 카드(친선전)는 **내용만큼만 넓고 왼쪽에 붙는다** (채팅의 말 줄처럼). 폭은 아래 둘 사이다.
CHAT_CARD_W = 540           # 상한. 이보다 긴 글은 줄을 바꾼다 (칸이 더 좁으면 칸에 맞춘다)
CHAT_CARD_MIN = 200         # 칸이 아주 좁을 때의 바닥
# 바닥: 이 글과 단추가 한 줄에 들어가는 폭 (글꼴 크기를 따라가게 글로 잰다). **가장 긴 닉네임(12자)**
# 으로 잰다 - 상대를 구하는 카드는 누구 것이든 같은 폭이고, 넉넉해 보인다. (여섯 자로 쟀을 때는
# 좁아 보였다)
CHAT_CARD_SAMPLE = "가나다라마바사아자차카타 님이 친선전 상대를 구합니다."
CHAT_CARD_GAP = 14          # 글과 단추 사이
FRIENDLY_EVERY = 5          # 폴링으로 돌 때 친선전의 지금 모습을 묻는 간격 (채팅 틱 몇 번에 한 번)
TABS = (("chat", "채팅"), ("members", "길드원"), ("mission", "미션"),
        ("shop", "코인 상점"), ("guilds", "다른 길드"), ("manage", "관리"))
SHOP_ICON = 40              # 코인 상점 카드의 도구 그림
SHOP_CARD_W = 232           # 카드 한 칸이 바라는 폭. 칸이 이보다 좁아지면 한 줄에 놓는 수를 줄인다
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


def shop_cols(width):
    """코인 상점의 카드를 한 줄에 몇 장 놓나 (2~4). 아직 폭을 모르면(그리기 전) 석 장."""
    try:
        width = int(width)
    except (TypeError, ValueError):
        return 3
    if width < 50:
        return 3
    return max(2, min(4, width // SHOP_CARD_W))


def shop_match(it, q):
    """찾는 말이 그 도구의 이름에 들어 있나. 띄어쓰기·대소문자는 안 가린다."""
    q = "".join((q or "").lower().split())
    if not q:
        return True
    return q in "".join(str(it.get("kr") or "").lower().split()) or q in str(it.get("id") or "").lower()


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


def chat_day(iso):
    """그 줄이 **내 PC 시각으로** 며칠인가 ('2026-10-06'). 모르면 빈 문자열."""
    try:
        return datetime.datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def day_label(day):
    """'2026-10-06' -> '10월 6일 화요일'. 모르면 빈 문자열."""
    try:
        d = datetime.date.fromisoformat(day)
        return "%d월 %d일 %s요일" % (d.month, d.day, WEEKDAYS[d.weekday()])
    except (TypeError, ValueError):
        return ""


def chat_rows(msgs, prev_day=None):
    """채팅 줄들에 날짜 줄을 끼운다. [("day", 날짜) | ("msg", 줄)] 을 돌려준다.

    채팅을 일주일 치까지 거슬러 볼 수 있어서 (1.10.3) 시각만으로는 언제 한 말인지 모른다.
    날이 바뀌는 자리마다 날짜 줄이 하나 선다. prev_day 는 바로 앞 줄의 날짜다 - 없으면(None)
    첫 줄 앞에도 날짜 줄이 선다.
    """
    out = []
    for m in msgs or []:
        d = chat_day(m.get("at"))
        if d and d != prev_day:
            out.append(("day", d))
        if d:
            prev_day = d
        out.append(("msg", m))
    return out


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
        self.shop_query = ""          # 코인 상점에서 찾는 말 (사고 나서 다시 그려도 남는다)
        self.shop_cards = []
        self.shop_btns = {}
        # 채팅
        self.chat_last = 0
        self.chat_box = None
        self.fr = None                # 길드 친선전 (ui_spectate.Friendly - 앱의 것을 같이 쓴다)
        self.chat_cards = {}          # 채팅에 놓인 카드 {줄 번호: {"frame", "inner", "m", "sig", "view", "btn"}}
        self.chat_hint = None         # 입력 칸 위의 안내 ('/친선전 을 치면 ...')
        self._card_lo = None          # 카드 폭의 바닥 (글꼴로 한 번 잰다)
        self._fr_tick = 0
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

        self._finder(self.body)

    def _finder(self, parent, title="길드 찾기"):
        """길드 찾기 칸: 이름으로 찾기 + 목록 + 쪽 넘기기.

        길드가 없을 때의 첫 화면과, 길드에 든 뒤의 '다른 길드' 칸이 같이 쓴다 (1.10.1).
        """
        bar = tk.Frame(parent, bg=U.BG)
        bar.pack(fill="x", padx=16, pady=(14, 6))
        U.marker_label(bar, title, bg=U.BG, color=U.FG).pack(side="left")
        self.q_var = tk.StringVar(value=self.query)
        U.ghost_button(bar, "찾기", self.do_search, height=30).pack(side="right")
        box = U.entry(bar, self.q_var, width=16)
        box.pack(side="right", padx=(0, 8))
        box.entry.bind("<Return>", lambda _e: self.do_search())
        tk.Label(bar, text="이름 일부만 적어도 됩니다", bg=U.BG, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="right", padx=(0, 10))

        self.pager = tk.Frame(parent, bg=U.BG)
        self.pager.pack(side="bottom", fill="x", padx=16, pady=(6, 0))
        self.list, self.list_fit = self._scroll(parent)
        if self.found is None:
            self.load_list()
        else:
            self._fill_list()

    def finding(self):
        """지금 길드 목록을 보고 있나 (길드가 없을 때의 첫 화면이거나 '다른 길드' 칸)."""
        return self.mode == "none" or (self.mode == "guild" and self.tab == "guilds")

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
            if not self.alive or gen != self._gen or not self.finding():
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
        tk.Label(row, text="누적 %s점" % format(int(g.get("points") or 0), ","), bg=U.BG3,
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left", padx=(10, 0))
        gid = g["id"]
        mine = ((self.data or {}).get("guild") or {}).get("id")
        if mine is not None:
            # 길드에 든 채로 둘러보는 중이다 (1.10.1). 가입은 지금 길드를 나온 뒤에야 된다.
            if gid == mine:
                U.chip(row, "내 길드", U.ACCENT, fg=U.ACCENT_DARK, padx=7).pack(side="right")
        elif g.get("requested"):
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
        self.seg = U.Segmented(bar, TABS, self.tab, self.show_tab)
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
        if key == "guilds":
            self.found = None                 # 칸을 열 때마다 새로 받는다
        self.tab = key
        try:
            self.seg.set(key)
        except Exception:                                   # noqa: BLE001
            pass
        self._draw_tab()

    # ---------------- 친선전 (1.10.3) ----------------
    def friendly(self):
        """길드 친선전의 지금 모습을 들고 있는 것. 앱의 것을 같이 쓴다 (검사용 앱처럼 없으면 만든다)."""
        if self.fr is None:
            fr = getattr(self.app, "friendly", None)
            if fr is None:
                from . import ui_spectate
                fr = ui_spectate.Friendly(self.app)
                try:
                    self.app.friendly = fr
                except Exception:                           # noqa: BLE001
                    pass
            self.fr = fr
            fr.listeners.append(self._friendly_changed)
        return self.fr

    def _friendly_changed(self):
        """친선전의 모습이 바뀌었다 (누가 구한다 / 판이 열렸다 / 끝났다 / 내가 구경을 켜고 껐다)."""
        if not self.alive:
            return
        fr = self.fr
        if fr is not None and fr.error:
            text, fr.error = fr.error, None
            self.say(text, U.DANGER)             # 못 받았다 (이미 3판 진행 중, 그사이 다른 사람이 받았다 ...)
        self._paint_cards()
        if not self.live and self.chat_visible():
            self._poll_chat()                    # 폴링으로 돌 때: 방금 놓인 카드를 2초 기다리지 않고 받는다

    def _draw_tab(self):
        self._clear(self.content)
        self.chat_cards = {}
        self.chat_hint = None
        self.chat_box = None
        self.chat_state = None
        self.chat_ready = False
        self._pending = []
        if self.tab == "chat":
            self.unread = 0
        self._paint_unread()
        getattr(self, "_tab_" + self.tab)()

    # ---------------- 다른 길드 (1.10.1) ----------------
    def _tab_guilds(self):
        """다른 길드 둘러보기. 길드에 들고 나면 목록을 볼 길이 없었다 - 어느 길드가 몇 명이고
        점수가 얼마인지 볼 수 있다. 가입 단추는 없다 (지금 길드를 나온 뒤에야 가입할 수 있다)."""
        self._finder(self.content, title="다른 길드")

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
        foot = tk.Frame(self.content, bg=U.BG)
        foot.pack(side="bottom", fill="x", padx=16, pady=(4, 0))
        # 지금 어느 길로 받고 있나. 말이 늦게 오는 것 같을 때 까닭을 알 수 있다.
        self.chat_state = tk.Label(foot, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="e")
        self.chat_state.pack(side="right", anchor="n")
        # 명령은 눈에 안 보인다 - 무엇을 칠 수 있는지 입력 칸 위에 늘 적어 둔다. '/' 를 치면 전부 보여 준다.
        # (칸이 좁으면 줄을 바꾼다 - 잘리지 않게)
        self.chat_hint = tk.Label(foot, text=SP.CMD_HINT, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w",
                                  justify="left")
        self.chat_hint.pack(side="left", fill="x", expand=True)
        U.wrap_to_width(self.chat_hint)
        self.chat_var.trace_add("write", lambda *_a: self._paint_hint())
        self._paint_state()

        wrap = U.framed(self.content, bg=U.INK)
        wrap.pack(fill="both", expand=True, padx=16, pady=(10, 0))
        sb = tk.Scrollbar(wrap, orient="vertical")

        def on_scroll(lo, hi):
            sb.set(lo, hi)
            try:
                if float(lo) <= 0.001:
                    self._want_older()       # 맨 위까지 굴렸다 - 앞의 줄을 더 받는다 (1.10.3)
            except (TypeError, ValueError):
                pass
        t = tk.Text(wrap, bg=U.INK, fg=U.FG, font=U.FONT, wrap="word", relief="flat", bd=0,
                    highlightthickness=0, padx=12, pady=10, state="disabled", cursor="arrow",
                    yscrollcommand=on_scroll, spacing1=2, spacing3=2, height=6, width=1)
        # (width=1: Text 는 그냥 두면 80자 폭을 바란다 - 칸이 그보다 좁아도 '눌렸다' 가 아니다.
        #  실제 폭은 틀이 준다)
        sb.configure(command=t.yview)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        t.tag_configure("time", foreground=U.FG_FAINT, font=U.FONT_XS)
        t.tag_configure("name", foreground=U.INFO, font=U.FONT_B)
        t.tag_configure("mine", foreground=U.ACCENT, font=U.FONT_B)
        t.tag_configure("body", foreground=U.FG)
        t.tag_configure("system", foreground=U.FG_FAINT, font=U.FONT_S, justify="center")
        # 날짜 줄과, 맨 처음 줄 위에 서는 안내 ('채팅은 7일 동안 보관됩니다')
        t.tag_configure("day", foreground=U.FG_DIM, font=U.FONT_XS, justify="center", spacing1=8,
                        spacing3=4)
        t.tag_configure("head", foreground=U.FG_FAINT, font=U.FONT_XS, justify="center", spacing3=4)
        t.tag_configure("card", justify="left", spacing1=5, spacing3=5)       # 카드가 놓이는 줄 (말 줄처럼 왼쪽에)
        t.wheel_div = 40               # 창의 휠 처리(U.install_wheel)가 이 칸을 굴린다
        t.bind("<Configure>", lambda _e: self._paint_cards(), add="+")       # 칸이 좁아지면 카드도 줄인다
        self.chat_box = t
        self.chat_cards = {}
        fr = self.friendly()
        fr.chat_open = self.chat_visible     # 채팅을 보는 동안에는 화면 구석의 알림을 띄우지 않는다
        fr.refresh()                         # 어느 카드가 살아 있는지 (지금 누가 구하고, 어느 판이 진행 중인지)
        self.chat_last = 0
        self.chat_lines = 0            # 화면에 있는 **말** 줄 수 (날짜 줄·안내 줄은 안 센다)
        self.chat_rows = []            # 화면의 줄 그대로: ("day", 날짜) | ("head", 글) | ("msg", 줄)
        self.chat_first = 0            # 화면에 있는 가장 앞 줄의 번호
        self.chat_more = False         # 그 앞에 받을 줄이 더 있나
        self.chat_days = 0             # 서버가 채팅을 두는 날 수
        self._older_busy = False
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
        if not self.live and any(SP.is_card(m) for m in fresh):
            self.friendly().refresh()            # 폴링으로 받은 새 카드 - 살아 있는지는 지금 모습을 물어야 안다
        return fresh

    def _segments(self, row):
        """줄 하나를 (글, 꼬리표) 토막들로. (카드 줄은 화면에는 카드로 놓인다 - _put_row.
        여기서 주는 글은 그 카드에 적힌 말이다.)"""
        kind, v = row
        if kind == "day":
            return [(day_label(v), ("day",))]
        if kind == "head":
            return [(v, ("head",))]
        if SP.is_card(v):
            return [("[친선전] %s" % self._card_view(v)["text"], ("card",))]
        if v.get("system"):
            return [("— %s —" % v.get("body", ""), ("system",))]
        return [("%s  " % clock(v.get("at")), ("time",)),
                ("%s  " % v.get("name", "?"), ("mine" if v.get("mine") else "name",)),
                (v.get("body", ""), ("body",))]

    def _put_row(self, t, at, row):
        """줄 하나를 at 자리에 놓는다. 카드 줄은 글 대신 **카드 한 장**(끼워 넣은 창)이다 -
        그래도 Text 에서는 한 줄이라, 줄을 세서 걷고 붙이는 것(_trim, _prepend)은 그대로 통한다."""
        if row[0] == "msg" and SP.is_card(row[1]):
            at = t.index(at)
            t.window_create(at, window=self._card_widget(t, row[1]))
            t.tag_add("card", at)
            return
        for text, tags in self._segments(row):
            t.insert(at, text, tags)

    # ---------------- 채팅의 카드: 길드 친선전 (1.10.3) ----------------
    def _card_span(self):
        """카드 폭의 (바닥, 상한). 카드는 내용만큼만 넓다 - 이 둘 사이에서."""
        try:
            pane = int(self.chat_box.winfo_width())
        except Exception:                                   # noqa: BLE001
            pane = 0
        hi = CHAT_CARD_W if pane <= 1 else max(CHAT_CARD_MIN, min(CHAT_CARD_W, pane - 48))
        if self._card_lo is None:
            try:
                from tkinter import font as tkfont
                self._card_lo = (tkfont.Font(root=self.root, font=U.FONT_S).measure(CHAT_CARD_SAMPLE)
                                 + 24 + CHAT_CARD_GAP + 76)          # 안쪽 여백 + 글과 단추 사이 + 단추
            except Exception:                               # noqa: BLE001
                self._card_lo = 320
        return min(self._card_lo, hi), hi

    def _card_view(self, m):
        """그 카드가 지금 어떻게 보여야 하나 (ui_spectate.chat_card)."""
        fr = self.friendly()
        duel = fr.duel.mid if fr.watching() else None
        return SP.chat_card(m.get("card"), int(m.get("id") or 0), fr.view, self.my_id, duel)

    def _card_widget(self, t, m):
        line = int(m.get("id") or 0)
        f = tk.Frame(t, bg=U.LINE2, cursor="arrow")
        inner = tk.Frame(f, bg=CARD)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.chat_cards[line] = {"frame": f, "inner": inner, "m": m, "sig": None, "view": None, "btn": None}
        self._paint_card(line)
        return f

    def _paint_card(self, line):
        """카드 한 장을 지금 모습대로 그린다. **달라졌을 때만** 다시 짓는다."""
        c = self.chat_cards.get(line)
        if c is None:
            return
        v, (lo, hi) = self._card_view(c["m"]), self._card_span()
        sig = (v["tag"], v["text"], v["button"], v["act"], v["arg"], lo, hi)
        if sig == c["sig"]:
            return
        inner = c["inner"]
        try:
            for ch in inner.winfo_children():
                ch.destroy()
            live = v["tone"] in ("seek", "fight")
            tk.Frame(inner, bg=CARD, width=lo, height=1).pack(anchor="w")    # 바닥 폭을 잡아 주는 살
            head = tk.Frame(inner, bg=CARD)
            head.pack(fill="x", padx=12, pady=(6, 0))
            tk.Label(head, text="길드 친선전", bg=CARD, fg=U.ACCENT if live else U.FG_DIM, font=U.FONT_B,
                     anchor="w").pack(side="left")
            if v["tag"]:                         # 진행 중 · 관전 중 · 끝 · 마감 (상대를 구하는 카드에는 없다)
                tk.Label(head, text=v["tag"], bg=CARD, font=U.FONT_XS, anchor="e",
                         fg=U.GOOD if v["tone"] == "fight" else U.FG_FAINT).pack(side="right", padx=(CHAT_CARD_GAP, 0))
            row = tk.Frame(inner, bg=CARD)
            row.pack(fill="x", padx=12, pady=(4, 9))
            btn, used = None, 0
            if v["button"]:
                press = (lambda a=v["act"], g=v["arg"]: self._card_press(a, g))
                if v["act"] in ("accept", "watch"):
                    btn = U.PushButton(row, v["button"], press, height=30, font=U.FONT_B)
                else:
                    btn = U.ghost_button(row, v["button"], press, height=30)
                btn.pack(side="right", padx=(CHAT_CARD_GAP, 0))
                used = int(btn.holder.cget("width")) + CHAT_CARD_GAP
            # 글이 길면 카드가 상한까지 넓어지고, 그래도 넘치면 줄을 바꾼다 (글씨를 줄이지 않는다)
            tk.Label(row, text=v["text"], bg=CARD, fg=U.FG if live else U.FG_DIM, font=U.FONT_S, anchor="w",
                     justify="left", wraplength=max(80, hi - 24 - used)).pack(side="left")
            c["sig"], c["view"], c["btn"] = sig, v, btn
        except tk.TclError:
            pass

    def _paint_cards(self, only=None):
        """카드들을(only 를 주면 그 줄만) 지금 모습대로. 맨 아래를 보고 있었으면 그대로 맨 아래를 본다.

        카드는 단추가 생기고 없어지면서 높이가 바뀐다 - 맨 아래에 놓인 카드가 높아지면 그 아래쪽이
        칸 밖으로 밀려난다. 높이는 **배치가 끝나야** 정해지므로 한 박자 뒤에 맨 아래로 간다.
        """
        t = self.chat_box
        if t is None or not self.chat_cards:
            return
        try:
            at_end = t.yview()[1] >= 0.999
        except tk.TclError:
            return
        for line in ([only] if only is not None else list(self.chat_cards)):
            self._paint_card(line)
        if at_end:
            self._bottom_soon()

    def _bottom_soon(self):
        """맨 아래로 간다 - **카드의 높이가 정해진 뒤에.**

        카드(끼운 창)는 놓거나 다시 짓는 그 순간에는 높이를 모른다: 안의 것들을 늘어놓고(pack) 그
        크기가 Text 에 전해지는 것이 다 '한가할 때' 로 미뤄져 있다. 그 자리에서 see("end") 를 부르면
        납작한 카드를 기준으로 굴러서, 맨 아래 카드의 아래쪽이 칸 밖으로 잘린다. 그래서 한 박자 뒤에,
        밀린 배치를 다 끝내고 간다.
        """
        t = self.chat_box
        if t is None:
            return

        def go():
            try:
                if self.chat_box is t:
                    t.update_idletasks()
                    t.see("end")
            except tk.TclError:
                pass
        try:
            t.after_idle(go)
        except tk.TclError:
            pass

    def _card_press(self, act, arg=None):
        self.friendly().card_do(act, arg)

    def _card_changed(self, line, card, body=None):
        """서버가 '그 줄의 카드가 바뀌었다' 고 알렸다 (상대 구함 -> 진행 중 -> 끝)."""
        if self.chat_box is None:
            return                               # 다른 칸을 보고 있다 - 채팅 칸을 열 때 새로 받는다
        rows = [m for kind, m in self.chat_rows if kind == "msg"] + list(self._pending)
        for m in rows:                           # (아직 못 붙인 줄 - 지난 줄을 받는 중 - 도 고쳐 둔다)
            if int(m.get("id") or 0) == line:
                m["card"] = card
                if body is not None:
                    m["body"] = body
        self._paint_cards(only=line)

    def card_texts(self):
        """화면에 놓인 카드들 {줄 번호: (상태 글, 본문, 단추 글)} (검사용)."""
        return dict((line, (c["view"]["tag"], c["view"]["text"], c["view"]["button"]))
                    for line, c in self.chat_cards.items() if c.get("view"))

    def _paint_hint(self):
        """입력 칸 위의 안내. '/' 로 시작하는 글을 치는 동안에는 쓸 수 있는 명령을 다 보여 준다."""
        lb = self.chat_hint
        if lb is None:
            return
        try:
            typing = (self.chat_var.get() or "").lstrip().startswith("/")
            lb.configure(text=SP.CMD_HELP if typing else SP.CMD_HINT, fg=U.FG_DIM if typing else U.FG_FAINT)
        except tk.TclError:
            pass

    def _last_day(self):
        for kind, v in reversed(self.chat_rows):
            if kind == "msg":
                return chat_day(v.get("at")) or None
        return None

    def _append(self, msgs):
        """새 줄을 아래에 붙인다. 날이 바뀌는 자리에는 날짜 줄이 선다."""
        t = self.chat_box
        if t is None or not msgs:
            return
        try:
            at_end = t.yview()[1] >= 0.999
            t.configure(state="normal")
            for row in chat_rows(msgs, self._last_day()):
                if self.chat_rows:
                    t.insert("end", "\n")
                self._put_row(t, "end-1c", row)
                self.chat_rows.append(row)
                if row[0] == "msg":
                    self.chat_lines += 1
                    if not self.chat_first:
                        self.chat_first = int(row[1].get("id") or 0)
            if at_end and len(self.chat_rows) > CHAT_KEEP:   # 오래 띄워 두면 줄이 끝없이 쌓인다
                self._trim(t, len(self.chat_rows) - CHAT_KEEP)
            t.configure(state="disabled")
            if at_end:
                t.see("end")
                if any(SP.is_card(m) for m in msgs):
                    self._bottom_soon()          # 카드는 높이가 늦게 정해진다 - 정해지면 다시 맨 아래로
        except tk.TclError:
            pass

    def _trim(self, t, cut):
        """맨 위의 cut 줄을 걷는다. 걷힌 줄은 위로 굴리면 다시 받아 온다 (chat_more)."""
        t.delete("1.0", "%d.0" % (cut + 1))
        for kind, v in self.chat_rows[:cut]:                         # 걷힌 줄의 카드 (창은 Text 가 같이 지웠다)
            if kind == "msg":
                self.chat_cards.pop(int(v.get("id") or 0), None)
        del self.chat_rows[:cut]
        while self.chat_rows and self.chat_rows[0][0] != "msg":      # 주인 잃은 날짜 줄
            t.delete("1.0", "2.0")
            del self.chat_rows[0]
        self.chat_lines = sum(1 for r in self.chat_rows if r[0] == "msg")
        if not self.chat_rows:
            self.chat_first = 0
            return
        top = self.chat_rows[0][1]
        self.chat_first, self.chat_more = int(top.get("id") or 0), True
        day = chat_day(top.get("at"))
        if day:                                               # 맨 윗줄 위에는 늘 날짜가 선다
            t.insert("1.0", "\n")
            t.insert("1.0", day_label(day), ("day",))
            self.chat_rows.insert(0, ("day", day))

    def _prepend(self, msgs, more):
        """앞의 줄(더 옛 것)을 위에 붙인다. **보던 자리는 그대로 둔다.**

        맨 위에 서 있던 날짜 줄·안내 줄은 걷고 새로 세운다 - 붙이고 나면 거기는 더 이상
        맨 위가 아니다. 더 받을 것이 없으면(more 가 거짓) 맨 위에 '며칠 동안 보관된다' 를 적는다.
        """
        t = self.chat_box
        if t is None:
            return
        try:
            t.configure(state="normal")
            while self.chat_rows and self.chat_rows[0][0] != "msg":
                t.delete("1.0", "2.0")
                del self.chat_rows[0]
            block = chat_rows(msgs)
            old_day = chat_day(self.chat_rows[0][1].get("at")) if self.chat_rows else ""
            new_day = chat_day(msgs[-1].get("at")) if msgs else None
            again = bool(old_day) and old_day != new_day     # 원래 맨 윗줄의 날짜 줄을 다시 세운다
            if again:
                block.append(("day", old_day))
            if not more:
                days = int(self.chat_days or 0)
                block.insert(0, ("head", "채팅은 %d일 동안 보관됩니다." % days if days
                                 else "여기가 첫 줄입니다."))
            t.mark_set("older", "1.0")
            t.mark_gravity("older", "right")
            for row in block:
                self._put_row(t, "older", row)
                if self.chat_rows or row is not block[-1]:
                    t.insert("older", "\n")
            self.chat_rows[0:0] = block
            self.chat_lines += len(msgs)
            if msgs:
                self.chat_first = int(msgs[0].get("id") or 0) or self.chat_first
            self.chat_more = bool(more)
            t.configure(state="disabled")
            if msgs:
                # 방금까지 맨 위였던 줄(다시 세운 날짜 줄이 있으면 그 줄)이 그대로 맨 위에 온다.
                # yview(줄) 은 **화면에 그려진 뒤에야** 맞는 자리로 간다 - 방금 넣은 줄들의 높이를
                # 아직 모를 때 부르면 한두 줄 어긋난다. 그래서 배치를 끝내고 부른다.
                line = "%d.0" % (len(block) + (0 if again else 1))
                t.update_idletasks()
                t.yview(line)
        except tk.TclError:
            pass

    def _want_older(self):
        """맨 위까지 굴렸다. 앞에 줄이 더 있으면 받아 온다 (굴림 도중이라 한 박자 늦춰서)."""
        if (not self.chat_ready or not self.chat_more or self._older_busy or not self.chat_first
                or self.chat_box is None):
            return
        self._older_busy = True
        try:
            self.root.after_idle(self._load_older)
        except Exception:                                   # noqa: BLE001
            self._older_busy = False

    def _load_older(self):
        box, before, api = self.chat_box, self.chat_first, self.app.api
        if box is None or not self.alive or not before:
            self._older_busy = False
            return

        def done(r, err):
            if not self.alive or self.chat_box is not box:
                self._older_busy = False
                return                       # 그사이 칸을 다시 그렸다 - 이 답은 버린다
            if err:
                self._older_busy = False
                return                       # 조용히 넘긴다. 다시 맨 위로 굴리면 또 묻는다
            r = r or {}
            msgs = [m for m in (r.get("messages") or []) if 0 < int(m.get("id") or 0) < self.chat_first]
            try:
                # **붙이는 동안은 '받는 중' 으로 둔다.** 붙이면서 화면을 한 번 그리는데(_prepend),
                # 그 순간에는 아직 맨 위를 보고 있어서 '맨 위까지 굴렸다' 가 또 울린다 - 그대로
                # 두면 한 번 굴렸는데 일주일 치를 줄줄이 다 받아 온다.
                self._prepend(msgs, bool(r.get("more")) and bool(msgs))
            finally:
                self._older_busy = False
            try:
                if box.yview()[0] <= 0.001:  # 붙이고도 칸이 다 차지 않았다 - 마저 받는다
                    self._want_older()
            except tk.TclError:
                pass
        run_async(self.root, lambda: api.guild_chat(before=before), done)

    def chat_bodies(self):
        """화면에 있는 **말** 줄의 글 (날짜 줄·안내 줄은 뺀다). 검사용."""
        return ["".join(text for text, _tags in self._segments(r)) for r in self.chat_rows if r[0] == "msg"]

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
            # 웹소켓이 없으면 친선전 소식도 밀려오지 않는다 - 채팅을 보는 동안 가끔 물어서 카드를 맞춘다
            self._fr_tick += 1
            if self._fr_tick % FRIENDLY_EVERY == 0:
                self.friendly().refresh()
        if self.pane_visible():
            if self._badged:
                self._badge(False)           # 길드 탭으로 돌아왔다 - 탭의 점은 지운다
            self._tell_app()
        try:
            self._chat_job = self.root.after(CHAT_MS, self._chat_tick)
        except Exception:                                   # noqa: BLE001
            self._chat_job = None

    def _tell_app(self):
        """앱에 알린다: 채팅 칸을 보고 있으면 '여기까지 읽었다', 아니면 '탭을 보고 있다'.

        허브의 길드 탭에 찍는 점은 앱이 그린다 (1.10.1) - 안 읽은 줄이 남았는지는 앱이 안다
        (app.mark_guild_chat_seen / _paint_guild). 검사용 앱처럼 그런 것이 없으면 아무 일도 없다.
        """
        try:
            if self.chat_visible() and self.chat_ready and self.chat_last:
                fn = getattr(self.app, "mark_guild_chat_seen", None)
                if fn is not None:
                    fn(self.chat_last)
            else:
                fn = getattr(self.app, "_paint_guild", None)
                if fn is not None:
                    fn()
        except Exception:                                   # noqa: BLE001
            pass

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
            if first:
                # 앞에 줄이 더 있나 (옛 서버는 이 값을 안 준다 - 그러면 거슬러 받지 않는다)
                self.chat_days = int(r.get("days") or 0)
                self.chat_more = bool(r.get("more"))
                if not self.chat_more and self.chat_rows and r.get("days"):
                    self._prepend([], False)                 # 맨 위에 '며칠 동안 보관된다' 를 적는다
            # 이 답을 기다리는 사이에 웹소켓으로 밀려온 줄. 답보다 먼저 붙이면 답에 든
            # 앞 번호의 줄이 '이미 지난 번호' 로 걸러져 사라진다 - 그래서 답 뒤에 붙인다.
            self.chat_ready = True
            pend, self._pending = self._pending, []
            self._add_lines(pend)
            # 눈앞에 떴으면 그 자리에서 읽은 것이다 (1.10.2). 2초 틱만 믿으면, 채팅을 흘끗
            # 보고 바로 다른 칸으로 간 사람은 안 읽은 채로 남아 나중에 점이 다시 켜진다.
            self._tell_app()
            if first:
                try:
                    box.see("end")
                    # 줄이 적어 칸이 다 차지 않았으면 맨 위가 곧 보이는 자리다 - 앞의 줄을 마저 받는다
                    box.update_idletasks()
                    if box.yview()[0] <= 0.001:
                        self._want_older()
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
        cmd = SP.command(text, (self.data or {}).get("members"), self.my_id)
        if cmd is not None:
            return self._run_command(cmd)        # '/친선전' - 말로 보내지 않는다
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

    def _run_command(self, cmd):
        """채팅에 친 명령 (ui_spectate.command 가 풀어 준 것)."""
        fr = self.friendly()
        if cmd[0] == "error":
            return self.say(cmd[1], U.DANGER)    # 친 글은 그대로 둔다 - 고쳐서 다시 칠 수 있게
        self.chat_var.set("")
        if cmd[0] == "seek":
            if fr.seeking_me():
                return self.say("이미 상대를 구하고 있습니다. 그만두려면 /친선전 취소", U.FG_DIM)
            self.say("길드원이 카드의 [배틀] 을 누르면 바로 시작합니다. 3분 동안 아무도 안 받으면 저절로 닫힙니다.")
            fr.seek(True)
        elif cmd[0] == "cancel":
            if not fr.seeking_me():
                return self.say("상대를 구하고 있지 않습니다.", U.FG_DIM)
            self.say("")
            fr.seek(False)
        elif cmd[0] == "ask":
            self.say("%s 님에게 친선전을 신청했습니다. 상대가 받으면 시작합니다." % cmd[2], U.GOOD)
            fr.ask(cmd[1])

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
            if self.sock is not None:
                # 이 탭이 듣기 시작했다. 탭이 없는 동안 앱이 붙여 둔 것은 끊는다 (1.10.1) -
                # 한 PC 에서 연결을 둘씩 쓰지 않는다.
                stop = getattr(self.app, "_stop_guild_sock", None)
                if stop is not None:
                    try:
                        stop()
                    except Exception:                       # noqa: BLE001
                        pass

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
        if t in ("live", "friendly", "friendly_fight"):
            return self.friendly().on_event(ev)      # 길드 친선전 (ui_spectate)
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
        if t == "card":
            return self._card_changed(int(ev.get("id") or 0), ev.get("card") or {}, ev.get("body"))
        if t == "chat":
            m = ev.get("m") or {}
            if m.get("userId") != self.my_id and not m.get("system"):
                note = getattr(self.app, "note_guild_chat", None)
                if note is not None:
                    note(m.get("id"))        # 안 읽은 줄이 생겼다 (점은 앱이 그린다)
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
            if fresh and self.pane_visible():
                self._tell_app()             # 보고 있는 칸에 떴다 - 바로 읽은 것이다
            elif fresh and m.get("userId") != self.my_id and not m.get("system"):
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
            painter = getattr(self.app, "_paint_guild", None)
            hub = getattr(self.app, "hub", None)
            try:
                if painter is not None:
                    painter()                # 진짜 앱: 점은 앱이 그린다 (1.10.1)
                elif hub is not None:
                    hub.set_badge("guild", on)
            except Exception:                               # noqa: BLE001
                pass
        if not on and self.tab == "chat":
            self.unread = 0

    def _paint_unread(self):
        """'채팅' 칸 이름 옆에 안 읽은 수.

        이 창이 세어 둔 수가 없어도 앱이 '안 읽은 줄이 남았다' 고 알면 점을 찍는다 (1.10.2) -
        허브의 길드 탭에 점이 켜진 까닭이 채팅이라는 것을 여기서 알 수 있어야 한다.
        """
        seg = getattr(self, "seg", None)
        text = "채팅"
        if self.tab != "chat":
            if self.unread:
                text = "채팅 %d" % self.unread
            elif getattr(self.app, "guild_unseen", False):
                text = "채팅 ●"
        try:
            if seg is not None and "chat" in seg.cells:
                seg.cells["chat"].configure(text=text)
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
        # 캐릭터 (1.10.3): 만든 사람이면 이름 왼쪽에 선다. 그만큼 옆의 글이 접히는 폭이 줄어든다.
        host, head_wrap = box, wrap
        from . import ui_avatar
        av = p.get("avatar") if ui_avatar.ENABLED else None      # 캐릭터는 보류 중이라 안 그린다
        if av:
            line = tk.Frame(box, bg=CARD)
            line.pack(fill="x")
            art = tk.Label(line, bg=CARD, bd=0, padx=0, pady=0)
            art.pack(side="left", anchor="n", padx=(12, 0), pady=(10, 0))
            art.image = ui_avatar.portrait(av, PROFILE_AVATAR)    # 직접 그린 도트를 쓰는 사람이면 그 도트
            art.configure(image=art.image)
            host = tk.Frame(line, bg=CARD)
            host.pack(side="left", fill="x", expand=True)
            head_wrap = wrap - (PROFILE_AVATAR * 32 + 12)
        top = tk.Frame(host, bg=CARD)
        top.pack(fill="x", padx=14, pady=(12, 2))
        tk.Label(top, text=u.get("name") or "?", bg=CARD, fg=u.get("frameColor") or U.FG,
                 font=(U.FAMILY_BLACK, U.pt(15))).pack(side="left")
        if u.get("tierKr"):
            U.chip(top, u["tierKr"], U.BG4, fg=U.FG, font=U.FONT_XS, padx=7).pack(
                side="left", padx=(8, 0))
        text, color = seen_text(g)
        if text:
            tk.Label(top, text=text, bg=CARD, fg=color, font=U.FONT_XS).pack(side="right")
        for text, fg, font in profile_head(p):
            tk.Label(host, text=text, bg=CARD, fg=fg, font=font, anchor="w", justify="left",
                     wraplength=head_wrap).pack(fill="x", padx=14, pady=(2, 0))
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
        tk.Label(box, text=mission_note(ms), bg=CARD, fg=U.FG_FAINT,
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
        kind, text = tier_state(t, ms)
        if kind == "claim":
            # 옛 서버(1.10.2 까지)에만 나온다 - 새 서버는 보상을 저절로 넣어 준다
            U.ghost_button(row, text, lambda: self.act(lambda: self.app.api.guild_claim(tier),
                                                       self._after_claim), height=28,
                           fill=U.ACCENT_DARK, fg=U.ACCENT).pack(side="right")
        else:
            tk.Label(row, text=text, bg=CARD, fg=U.GOOD if kind == "claimed" else U.FG_FAINT,
                     font=U.FONT_S if kind == "claimed" else U.FONT_XS).pack(side="right")

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

            def work():
                r = api.guild_shop()
                # 카드의 그림도 여기서(작업 스레드) 받아 크기를 맞춰 둔다. 못 받아도 상점은
                # 뜬다 - 그림 자리만 빈다.
                try:
                    item_icons.prefetch(api, [i["id"] for i in (r or {}).get("items") or []],
                                        sizes=(SHOP_ICON,))
                except Exception:                           # noqa: BLE001
                    pass
                return r

            def done(r, err):
                if not self.alive or gen != self._gen or self.mode != mode \
                        or (mode == "guild" and self.tab != tab):
                    return
                if err:
                    return self.say(_err(err), U.DANGER)
                self.shop = r or {}
                self._clear(self.content)
                self._fill_shop()
            return run_async(self.root, work, done)
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
        # 찾기 (1.10.1). 적는 대로 걸러진다.
        bar = tk.Frame(self.content, bg=U.BG)
        bar.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(bar, text="도구 찾기", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS).pack(side="left")
        self.shop_q = tk.StringVar(value=self.shop_query)
        U.entry(bar, self.shop_q, width=14).pack(side="left", padx=(8, 0))
        self.shop_count = tk.Label(bar, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS)
        self.shop_count.pack(side="left", padx=(10, 0))
        # 카드 격자 (1.10.1). 예전에는 한 줄에 하나씩이라 스무 개를 보려면 한참 내려야 했다.
        inner, fit = self._scroll(self.content)
        self.shop_inner, self.shop_fit = inner, fit
        self.shop_none = tk.Label(inner, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S)
        bag = s.get("bag") or {}
        self.shop_btns = {}           # {(도구, 몇 개): 단추} - 코인이 모자라면 꺼져 있다
        # 카드는 한 번만 만든다. 찾기와 창 크기 바꾸기는 만들어 둔 것을 담았다 뺐다만 한다.
        self.shop_cards = [(it, self._shop_card(inner, it, have, int(bag.get(it["id"]) or 0)))
                           for it in s.get("items") or []]
        self._shop_cols = 0
        # **폭을 듣는 것을 먼저 건다.** 처음 담을 때는 칸의 폭을 아직 모르고(석 장으로 담는다),
        # 진짜 폭은 fit_now 가 밀린 배치를 끝내는 순간에 온다. 담은 뒤에 걸면 그 한 번을
        # 놓쳐서, 넓은 창에서도 석 장으로 굳었다 (CI 가 잡음: 폭 947 에 석 장).
        inner.master.bind("<Configure>", lambda e: self._shop_resized(e.width), add="+")
        self._shop_layout()
        self.shop_q.trace_add("write", lambda *_a: self._shop_search())

    def _shop_card(self, parent, it, have, owned):
        """코인 상점의 카드 한 장: 그림 · 이름 · 값 · 설명 · 사기 단추."""
        c = U.framed(parent, bg=U.BG3)
        price = int(it.get("coin") or 0)
        iid = it["id"]
        # 단추는 바닥에 붙인다 - 같은 줄의 카드는 높이가 같아지므로(설명이 긴 쪽에 맞춘다)
        # 단추가 한 줄로 가지런하다.
        btns = tk.Frame(c, bg=U.BG3)
        btns.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        for n in (1, 10):
            b = U.ghost_button(btns, "%d개 사기" % n, lambda n=n: self.buy(iid, n), height=28)
            b.pack(side="left", padx=(0, 6))
            if have < price * n:
                b.configure(state="disabled")
            self.shop_btns[(iid, n)] = b
        top = tk.Frame(c, bg=U.BG3)
        top.pack(fill="x", padx=10, pady=(10, 4))
        holder = tk.Frame(top, bg=U.BG3, width=SHOP_ICON, height=SHOP_ICON)
        holder.pack_propagate(False)             # 그림이 아직 없어도 자리는 그대로다
        holder.pack(side="left")
        pic = tk.Label(holder, bg=U.BG3, bd=0)
        pic.pack(expand=True)
        ph = item_icons.photo(iid, SHOP_ICON)
        if ph is not None:
            pic.configure(image=ph)
            pic.image = ph                       # 참조를 놓으면 tk 가 그림을 지운다
        txt = tk.Frame(top, bg=U.BG3)
        txt.pack(side="left", fill="x", expand=True, padx=(8, 0))
        name = tk.Label(txt, text=it.get("kr", iid), bg=U.BG3, fg=U.FG, font=U.FONT_B,
                        anchor="w", justify="left")
        name.pack(fill="x")
        U.wrap_to_width(name)
        line = tk.Frame(txt, bg=U.BG3)
        line.pack(fill="x")
        tk.Label(line, text="코인 %d" % price, bg=U.BG3,
                 fg=U.ACCENT if have >= price else U.DANGER, font=U.FONT_B).pack(side="left")
        if owned:
            tk.Label(line, text="가진 것 %d" % owned, bg=U.BG3, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left", padx=(8, 0))
        note = it.get("note") or it.get("heldNote") or it.get("desc") or ""
        if note:
            lb = tk.Label(c, text=natural(note), bg=U.BG3, fg=U.FG_FAINT, font=U.FONT_XS,
                          anchor="nw", justify="left")
            lb.pack(fill="x", padx=10, pady=(0, 8))
            U.wrap_to_width(lb)
        return c

    def shop_shown(self):
        """지금 찾는 말에 맞는 도구들 (화면 순서)."""
        q = self.shop_query
        return [it for it, _c in self.shop_cards if shop_match(it, q)]

    def _shop_layout(self, width=None):
        """카드를 격자에 담는다: 찾는 말에 맞는 것만, 한 줄에 shop_cols 장."""
        try:
            inner = self.shop_inner
            if width is None:
                width = inner.master.winfo_width()
            cols = shop_cols(width)
            q = self.shop_query
            shown = [c for it, c in self.shop_cards if shop_match(it, q)]
            for _it, c in self.shop_cards:
                c.grid_forget()
            self.shop_none.grid_forget()
            for k in range(4):
                inner.grid_columnconfigure(k, weight=1 if k < cols else 0,
                                           uniform="shop" if k < cols else "")
            for i, c in enumerate(shown):
                c.grid(row=i // cols, column=i % cols, sticky="nsew", padx=3, pady=3)
            if not shown:
                self.shop_none.configure(
                    text=("'%s' (이)가 들어간 도구가 없습니다." % q.strip()) if q.strip()
                    else "살 수 있는 도구가 없습니다.")
                self.shop_none.grid(row=0, column=0, columnspan=cols, pady=24)
            self._shop_cols = cols
            self.shop_count.configure(text="%d개" % len(shown) if q.strip() else "")
            self.shop_fit.fit_now()
        except (tk.TclError, AttributeError):
            pass                                 # 그 사이에 칸을 떠났다

    def _shop_search(self):
        try:
            self.shop_query = self.shop_q.get() or ""
        except tk.TclError:
            return
        self._shop_layout()
        try:
            self.shop_inner.master.yview_moveto(0)
        except (tk.TclError, AttributeError):
            pass

    def _shop_resized(self, width):
        """칸의 폭이 바뀌었다. 한 줄에 놓는 수가 달라질 때만 다시 담는다."""
        if self.alive and self.shop_cards and shop_cols(width) != self._shop_cols:
            self._shop_layout(width)

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
        if self.fr is not None:
            try:
                self.fr.listeners.remove(self._friendly_changed)
            except ValueError:
                pass
            if self.fr.chat_open == self.chat_visible:
                self.fr.chat_open = None
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


def mission_note(ms):
    """미션 칸의 안내 한 줄. 보상이 저절로 들어오는 서버(1.10.3~)인지에 따라 다르다."""
    if (ms or {}).get("auto"):
        return ("길드원이 미션을 하면 점수가 길드에 모입니다. 단계를 넘으면, 오늘 미션을 하나라도 한 "
                "길드원에게 보상이 자동으로 들어옵니다. 받기를 누를 필요가 없습니다.")
    return ("길드원이 미션을 하면 점수가 길드에 모입니다. 단계를 넘을 때마다, 오늘 미션을 하나라도 한 "
            "길드원이 보상을 받습니다.")


def tier_state(t, ms):
    """단계 한 줄의 오른쪽에 적을 것. (종류, 글). 종류 = claimed / claim / wait / left.

    보상이 저절로 들어오는 서버에서는 '받기' 가 없다: 넘은 단계는 '받음' 이거나, 아직 오늘 미션을
    하나도 안 해서 기다리는 중이다 (하나를 끝내는 순간 들어온다).
    """
    ms = ms or {}
    if t.get("claimed"):
        return "claimed", "받음 (자동)" if ms.get("auto") else "받음"
    if t.get("canClaim"):
        return "claim", "받기"
    if t.get("reached"):
        return "wait", ("미션을 하나라도 하면 바로 들어옵니다" if ms.get("auto")
                        else "미션을 하나라도 하면 받을 수 있습니다")
    return "left", "%d점 남음" % max(0, int(t.get("need") or 0) - int(ms.get("guildPoints") or 0))


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
