# -*- coding: utf-8 -*-
"""마이페이지 (1.9.0) — 내 정보와 내가 한 일을 한 화면에.

'설정' 탭이 있던 자리다. 설정은 없어진 것이 아니라 **머리줄의 톱니바퀴**
안으로 들어갔다 - 누르면 이 칸이 설정 화면으로 바뀌고, '← 마이페이지' 로
돌아온다. 설정 화면은 예전 클래스(ui_settings.SettingsWindow)를 그대로 쓴다.

보여 주는 것 (서버의 GET /api/mypage 한 번):

  · 나         이름·칭호·티어, 가입한 지 며칠째. **닉네임 왼쪽에 내 캐릭터** (1.10.3) -
               누르거나 '캐릭터 만들기' 를 누르면 꾸미기 창(ui_avatar)이 뜬다
  · 모은 것    포켓몬, 색이 다른 포켓몬, 도감, 이긴 관장, 친구, 레이드
  · 칭호       가진 칭호들 (달고 있는 것은 금색). '칭호·명패 바꾸기' 로 단다 (1.12.1 - 랭킹 탭에서 옮겨 왔다)
  · 시즌 기록  지금 시즌과 지난 시즌들의 순위·티어·전적
  · 게시판     [알림 | 내 글 | 내 댓글] 중 하나를 한 쪽(다섯 줄)씩 - 누르면 그 글로 간다.
               활동이 아무리 쌓여도 이 칸의 높이는 같다 (쪽은 ◀ ▶ 로 넘긴다)
  · 계정       로그아웃 · 회원탈퇴 (1.9.2 - 트레이 메뉴에서 여기로 옮겼다)

창을 열 때와 '새로고침' 을 누를 때만 서버를 부른다.
"""
import tkinter as tk
from tkinter import ttk

from common.korean import ago, natural

from . import skins
from . import ui_box
from . import ui_common as U
from .ui_common import run_async
from .ui_settings import SettingsWindow

W, H = 760, 680
CARD = "#161b28"
TILE = "#10141e"
KIND_COLOR = {"notice": U.ACCENT, "free": U.INFO, "qna": U.GOOD, "patch": U.PINK}
RELOAD_MS = 1500              # 알림을 눌러 글을 연 뒤 알림 쪽을 다시 받기까지
# 게시판 활동의 탭. 서버의 board.MINE_WHAT 과 같은 열쇠다.
TABS = ("notify", "posts", "comments")
EMPTY = {"notify": "새 알림이 없습니다. 내 글에 댓글이, 내 댓글에 답글이 달리면 여기에 모이고, "
                   "그 글을 열어 보면 사라집니다.",
         "posts": "아직 쓴 글이 없습니다.",
         "comments": "아직 단 댓글이 없습니다."}


# 이메일 (2.1.1) - 계정 칸 맨 위 줄. 비밀번호를 잊었을 때 운영자가 계정에서 보는 연락처 (확인 메일은 없다)
EMAIL_BTN = "이메일 등록"


def email_text(user):
    """계정 칸 이메일 줄의 설명."""
    if user.get("email"):
        return "등록한 이메일: %s\n비밀번호를 잊었을 때 운영진이 계정을 확인하는 데 씁니다. 다른 사람에게는 보이지 않습니다." \
            % user["email"]
    return "이메일을 등록해 두면 비밀번호를 잊었을 때 운영진이 계정을 확인하는 데 씁니다. 다른 사람에게는 보이지 않습니다."


def _err(e):
    return getattr(e, "message", None) or str(e)


def _date(iso):
    """'2026-09-23T03:00:00+00:00' -> '2026.09.23'. 모르면 빈 문자열."""
    s = (iso or "")[:10]
    return s.replace("-", ".") if len(s) == 10 else ""


def record_text(s):
    """한 시즌의 전적 한 줄. '9전 6승 3패'."""
    bits = ["%d전" % int(s.get("games") or 0), "%d승" % int(s.get("wins") or 0),
            "%d패" % int(s.get("losses") or 0)]
    if int(s.get("draws") or 0):
        bits.append("%d무" % int(s["draws"]))
    return " ".join(bits)


def season_line(s):
    """시즌 한 줄에 적을 (머리, 본문). 화면과 검사가 같이 쓴다."""
    head = "시즌 %s" % s.get("season")
    if s.get("current"):
        head += " (진행 중)"
        if not s.get("ranked"):
            left = int(s.get("placementLeft") or 0)
            if not int(s.get("games") or 0):
                return head, "아직 랭크 배틀을 하지 않았습니다."
            return head, "배치 중 - %d판 더 하면 순위에 오릅니다 · %s" % (left, record_text(s))
    bits = []
    if s.get("rank"):
        bits.append("%d위" % s["rank"])
    if s.get("tierKr"):
        bits.append(s["tierKr"])
    if s.get("rp") is not None:
        bits.append("RP %d" % int(s.get("rp") or 0))
    elif s.get("rating"):
        bits.append("점수 %d" % int(s["rating"]))
    bits.append(record_text(s))
    if s.get("title"):
        bits.append("칭호 '%s'" % s["title"])
    return head, " · ".join(bits)


# ---------------------------------------------------------------- 집중 기록 (집중 타이머)
# 서버 mypage 의 focus = {"summary": {...}, "month": {"ym", "days": {날: 분}}}. 다른 달은 /api/focus/month,
# 날을 누르면 /api/focus/day. 기본 화면과 DP 테마(skins/dp/mypage)가 이 도우미를 같이 쓴다.
WEEK = "일월화수목금토"
HEAT = (0, 50, 100, 200)      # 분: 1~49 / 50~99 / 100~199 / 200+ 이 한 단계씩 진하다


def hm(minutes):
    """62 -> '1:02' (달력 칸)."""
    h, m = divmod(max(0, int(minutes)), 60)
    return "%d:%02d" % (h, m)


def span_text(minutes):
    """87 -> '1시간 27분', 25 -> '25분'."""
    h, m = divmod(max(0, int(minutes)), 60)
    if not h:
        return "%d분" % m
    return "%d시간 %d분" % (h, m) if m else "%d시간" % h


def shift_ym(ym, delta):
    y, m = int(ym[:4]), int(ym[5:7]) - 1 + int(delta)
    y, m = y + m // 12, m % 12
    return "%04d-%02d" % (y, m + 1)


def month_title(ym):
    return "%d년 %d월" % (int(ym[:4]), int(ym[5:7]))


def heat_level(minutes):
    m = int(minutes or 0)
    return sum(1 for t in HEAT if m > t) if m > 0 else 0


def focus_cells(ym, days):
    """달력 칸: [{"day", "date", "col", "row", "min", "level"}] (일요일이 0 번째 칸)."""
    from common import focus as FOCUS
    first, n = FOCUS.month_grid(ym)
    out = []
    for d in range(1, n + 1):
        i = first + d - 1
        date = "%s-%02d" % (ym, d)
        m = int((days or {}).get(date, 0))
        out.append({"day": d, "date": date, "col": i % 7, "row": i // 7, "min": m, "level": heat_level(m)})
    return out


def cell_text(c):
    return "%d\n%s" % (c["day"], hm(c["min"])) if c["min"] else str(c["day"])


def day_line(r):
    """그날 기록 한 줄: '12:25 · 꼬부기 · 공부 · 25분 · +5' / 자투리는 '자투리 12분'."""
    if r.get("full"):
        tail = "%d분 · +%d" % (int(r.get("minutes", 0)), int(r.get("ev", 0)))
    else:
        tail = "자투리 %d분" % int(r.get("minutes", 0))
    return "%s · %s · %s · %s" % (r.get("time", ""), r.get("pokemon", "?"), r.get("act", "?"), tail)


def focus_summary(sm):
    return "이번 달 %s  ·  전체 %s  ·  연속 %d일 (최고 %d일)  ·  오늘 노력치 %d/%d" % (
        span_text(sm.get("monthMin", 0)), span_text(sm.get("totalMin", 0)), int(sm.get("streak", 0)),
        int(sm.get("best", 0)), int(sm.get("todayEv", 0)), int(sm.get("dailyEv", 40)))


def blend(a, b, t):
    """두 빛깔 사이 (t=0 이면 a, 1 이면 b)."""
    a, b = a.lstrip("#"), b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(ca, cb))


HEAT_MIX = (0.0, 0.3, 0.5, 0.72, 1.0)     # 단계마다 강조색을 얼마나 섞나


def tile_items(d):
    """(이름, 값, 덧붙임) 목록. 화면과 검사가 같이 쓴다."""
    c, g, r = d.get("counts") or {}, d.get("gym") or {}, d.get("raid") or {}
    return [
        ("포켓몬", "%d마리" % int(c.get("pokemon") or 0),
         "가장 높은 레벨 %d" % int(c.get("topLevel") or 0) if c.get("topLevel") else ""),
        ("색이 다른 포켓몬", "%d마리" % int(c.get("shiny") or 0), ""),
        ("도감", "%d / %d" % (int(c.get("dexCaught") or 0), int(c.get("dexTotal") or 0)),
         "본 종 %d" % int(c.get("dexSeen") or 0)),
        ("이긴 관장", "%d / %d" % (int(g.get("cleared") or 0), int(g.get("total") or 0)),
         "모두 %d번 승리" % int(g.get("wins") or 0) if g.get("wins") else ""),
        ("레이드", "%d승" % int(r.get("wins") or 0),
         "%d판 참가" % int(r.get("games") or 0) if r.get("games") else ""),
        ("친구", "%d명" % int(c.get("friends") or 0), ""),
    ]


class Flow(object):
    """칩을 왼쪽부터 채우고 넘치면 다음 줄로. Tk 에는 이런 배치가 없다.

    칩을 다 만든 뒤 한 번, 그리고 폭이 바뀔 때마다 다시 놓는다. 줄 수에
    맞춰 높이를 스스로 정한다 - 글자를 줄이지 않고 줄을 늘린다.
    """

    def __init__(self, parent, bg, gap=6):
        self.frame = tk.Frame(parent, bg=bg)
        self.gap = gap
        self.items = []
        self._w = None
        self.frame.bind("<Configure>", self._on_size)

    def add(self, widget):
        self.items.append(widget)

    def _on_size(self, e):
        if e.width != self._w:
            self.place(e.width)

    def place(self, width=None):
        try:
            self.frame.update_idletasks()
            width = width or self.frame.winfo_width()
            if width <= 1:
                return 0
            self._w = width
            x = y = row_h = 0
            for w in self.items:
                ww, hh = w.winfo_reqwidth(), w.winfo_reqheight()
                if x and x + ww > width:
                    x, y, row_h = 0, y + row_h + self.gap, 0
                w.place(x=x, y=y)
                x += ww + self.gap
                row_h = max(row_h, hh)
            total = y + row_h
            self.frame.configure(height=max(1, total))
            return total
        except tk.TclError:
            return 0


@skins.skinnable
class MyPageWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.alive = True
        self.data = None
        self.view = "page"            # page / settings
        self.settings = None          # 설정 화면 (처음 눌렀을 때 만든다)
        self.editor = None            # 캐릭터 꾸미기 창 (떠 있을 때만)
        self._gen = 0
        self.cv = None
        self.fit = None
        self.flows = []

        self.win = U.panel(parent, self.root, "포스크탑 — 마이페이지",
                           W, H, 560, 480, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)

        self._build()
        self.load()

    # 화면 테마(skins/)는 _build 와 칠하는 자리(_fill · _fill_tab · show_page · show_settings · say)만 갈아 끼운다.
    def _build(self):
        self._header()
        self.status = U.status_line(self.win, "")
        self.status.pack(side="bottom", fill="x", padx=16, pady=(6, 12))
        self.page = tk.Frame(self.win, bg=U.BG)
        self.page.pack(fill="both", expand=True)
        self.set_box = tk.Frame(self.win, bg=U.BG)        # 설정 화면이 들어갈 칸
        self._build_scroll()

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=U.h(62))
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)
        # 사람 그림 — 머리와 어깨
        cv = tk.Canvas(inner, width=28, height=28, bg=U.BG2, highlightthickness=0, bd=0)
        cv.pack(side="left")
        cv.create_oval(9, 3, 19, 13, fill="#f4f6fb", outline=U.INK, width=2)
        cv.create_arc(3, 13, 25, 37, start=0, extent=180, fill="#f4f6fb",
                      outline=U.INK, width=2)
        self.title = tk.Label(inner, text="마이페이지", bg=U.BG2, fg=U.FG,
                              font=(U.FAMILY_BLACK, U.pt(15)))
        self.title.pack(side="left", padx=(12, 12))
        # 톱니바퀴 = 설정. 그림만 있으면 무엇인지 모를 수 있어 글자를 같이 둔다.
        gear = tk.Frame(inner, bg=U.BG2, cursor="hand2")
        gear.pack(side="right")
        self.gear = U.gear_icon(gear, U.h(22), U.FG_DIM, U.BG2)
        self.gear.pack(side="left")
        self.gear_lbl = tk.Label(gear, text="설정", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S,
                                 cursor="hand2")
        self.gear_lbl.pack(side="left", padx=(5, 0))
        for w in (gear, self.gear, self.gear_lbl):
            w.bind("<Button-1>", lambda _e: self.toggle_settings())
            w.bind("<Enter>", lambda _e: self._paint_gear(True))
            w.bind("<Leave>", lambda _e: self._paint_gear(False))
        self.refresh_btn = U.ghost_button(inner, "새로고침", self.load, height=32)
        self.refresh_btn.pack(side="right", padx=(0, 14))
        self.back_btn = U.ghost_button(inner, "← 마이페이지", self.show_page, height=32)
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

    def _paint_gear(self, hot):
        on = hot or self.view == "settings"
        col = U.ACCENT if on else U.FG_DIM
        try:
            self.gear.itemconfigure(self.gear.gear, fill=col, outline=col)
            self.gear_lbl.configure(fg=col)
        except tk.TclError:
            pass

    def say(self, text, color=U.GOOD):
        if self.alive:
            U.set_status(self.status, natural(text or ""), color)

    # ---------------- 설정 화면 ----------------
    def toggle_settings(self):
        if self.view == "settings":
            return self.show_page()
        self.show_settings()

    def show_settings(self):
        """톱니바퀴를 눌렀다. 이 칸을 설정 화면으로 바꾼다."""
        if self.settings is None:
            self.settings = SettingsWindow(self.app, self.set_box, header=False)
            self.settings.win.configure(highlightthickness=0)
            self.settings.win.pack(fill="both", expand=True)
            self.app.settings_win = self.settings
        self.view = "settings"
        self.page.pack_forget()
        self.status.pack_forget()         # 설정 화면에는 자기 상태 줄이 있다
        self.set_box.pack(fill="both", expand=True)
        self.title.configure(text="설정")
        self.refresh_btn.pack_forget()
        self.back_btn.pack(side="right", padx=(0, 14))
        self._paint_gear(False)

    def show_page(self):
        self.view = "page"
        self.set_box.pack_forget()
        self.status.pack(side="bottom", fill="x", padx=16, pady=(6, 12))
        self.page.pack(fill="both", expand=True)
        self.title.configure(text="마이페이지")
        self.back_btn.pack_forget()
        self.refresh_btn.pack(side="right", padx=(0, 14))
        self._paint_gear(False)

    # ---------------- 굴러가는 칸 ----------------
    def _build_scroll(self):
        holder = tk.Frame(self.page, bg=U.BG)
        holder.pack(fill="both", expand=True, padx=16, pady=(12, 0))
        cv = tk.Canvas(holder, bg=U.BG, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(cv, bg=U.BG)
        wid = cv.create_window((0, 0), window=self.inner, anchor="nw")
        self.fit = U.scroll_fitter(cv, self.inner, wid)
        U.scrollable(cv, 60)
        self.cv = cv
        tk.Label(self.inner, text="불러오는 중...", bg=U.BG, fg=U.FG_FAINT,
                 font=U.FONT_S).pack(pady=30)

    def load(self):
        # 대전을 재생하는 동안에는 읽지 않는다 - 서버에는 점수가 이미 들어가 있다 (1.13.4)
        later = getattr(self.app, "scores_after_match", None)
        if later is not None and later(self.load):
            return self.say("대전이 끝나면 불러옵니다. 점수는 대전을 다 본 뒤에 바뀝니다.", U.FG_FAINT)
        self._gen += 1
        gen = self._gen
        api = self.app.api

        def done(r, err):
            if not self.alive or gen != self._gen:
                return
            if err:
                return self.say(_err(err), U.DANGER)
            self.data = r or {}
            self._focus_init(self.data)
            self._fill(self.data)
            note, self._note_after = getattr(self, "_note_after", None), None
            self.say(*(note or ("",)))                  # 다시 읽게 한 일의 결과 글은 남긴다 (이메일 등록)
        run_async(self.root, lambda: api.mypage(), done)

    def refresh(self):
        self.load()

    # ---------------- 그리기 ----------------
    def _section(self, title, note="", action=None):
        """제목 줄과 그 아래 칸. 칸을 돌려준다. action=(글, 함수) 면 제목 줄 오른쪽에 단추."""
        head = tk.Frame(self.inner, bg=U.BG)
        head.pack(fill="x", pady=(16, 6), padx=(0, 8))
        U.marker_label(head, title, bg=U.BG, color=U.FG).pack(side="left")
        if note:
            tk.Label(head, text=note, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS).pack(
                side="left", padx=(10, 0))
        if action:
            U.ghost_button(head, action[0], action[1], height=28).pack(side="right")
        box = tk.Frame(self.inner, bg=CARD, highlightthickness=1, highlightbackground=U.LINE)
        box.pack(fill="x", padx=(0, 8))
        return box

    def _fill(self, d):
        for w in self.inner.winfo_children():
            w.destroy()
        self.flows = []
        self._profile(d)
        self._tiles(d)
        self._focus(d)
        self._titles(d)
        self._seasons(d)
        self._board(d)
        self._account()
        tk.Frame(self.inner, bg=U.BG, height=U.h(12)).pack(fill="x")
        self.root.after_idle(self._reflow)

    def _reflow(self):
        if not self.alive:
            return
        for f in self.flows:
            f.place()
        try:
            self.fit.fit_now()
        except Exception:                                   # noqa: BLE001
            pass

    def _profile(self, d):
        u = d.get("user") or {}
        box = tk.Frame(self.inner, bg=CARD, highlightthickness=1,
                       highlightbackground=U.ACCENT_SHADOW)
        box.pack(fill="x", padx=(0, 8))
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", padx=16, pady=14)
        # 캐릭터 (1.10.3): 닉네임 왼쪽. 아직 안 만들었으면 그림자가 서 있다. 누르면 꾸미기 창.
        # **지금은 보류 중이라 안 보인다** (ui_avatar.ENABLED).
        from . import ui_avatar
        self.av_art = self.av_btn = self.av_swap = None
        if ui_avatar.ENABLED:
            self.av_art = tk.Label(row, bg=TILE, bd=0, padx=0, pady=0, cursor="hand2", highlightthickness=1,
                                   highlightbackground=U.LINE)
            self.av_art.pack(side="left", anchor="n", padx=(0, 14))
            self.av_art.bind("<Button-1>", lambda _e: self.open_avatar())
        col = tk.Frame(row, bg=CARD)
        col.pack(side="left", fill="x", expand=True)
        top = tk.Frame(col, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text=u.get("name") or "?", bg=CARD, fg=u.get("frameColor") or U.FG,
                 font=(U.FAMILY_BLACK, U.pt(17))).pack(side="left")
        if u.get("admin"):
            U.chip(top, "운영자", U.ACCENT, font=U.FONT_XS, padx=6).pack(side="left", padx=(8, 0))
        if u.get("tierKr"):
            U.chip(top, u["tierKr"], U.BG4, fg=U.FG, font=U.FONT_XS, padx=7).pack(
                side="left", padx=(8, 0))
        if u.get("title"):
            tk.Label(top, text=u["title"], bg=CARD, fg=U.ACCENT_TEXT, font=U.FONT_S).pack(
                side="left", padx=(10, 0))
        bits = []
        if u.get("days"):
            bits.append("함께한 지 %d일째" % int(u["days"]))
        if _date(u.get("createdAt")):
            bits.append("%s 가입" % _date(u.get("createdAt")))
        if u.get("money") is not None:
            bits.append("소지금 {:,}원".format(int(u.get("money") or 0)))
        lb = tk.Label(col, text="  ·  ".join(bits), bg=CARD, fg=U.FG_DIM, font=U.FONT_S,
                      anchor="w", justify="left")
        lb.pack(fill="x", pady=(4, 0))
        U.wrap_to_width(lb)
        if ui_avatar.ENABLED:
            btns = tk.Frame(col, bg=CARD)
            btns.pack(anchor="w", pady=(10, 0))
            self.av_btn = U.ghost_button(btns, "캐릭터 만들기", self.open_avatar, height=30)
            self.av_btn.pack(side="left")
            self.av_swap = U.ghost_button(btns, "직접 그린 도트 쓰기", self.swap_avatar, height=30)
            self._paint_avatar()

    # ---------------- 캐릭터 (1.10.3) ----------------
    def avatar(self):
        """서버가 준 내 캐릭터 ({"spec": 고른 것, "image": 직접 그린 도트 ...}). 안 만들었으면 None."""
        return (self.data or {}).get("avatar") or None

    def _paint_avatar(self):
        if getattr(self, "av_art", None) is None:
            return                           # 보류 중이라 캐릭터 칸이 없다
        av = self.avatar()
        try:
            from . import ui_avatar
            self._av_photo = ui_avatar.portrait(av) if av else ui_avatar.placeholder()
            self.av_art.configure(image=self._av_photo)
            self.av_btn.configure(text="캐릭터 바꾸기" if av else "캐릭터 만들기")
            # 직접 그린 도트를 넣어 둔 사람에게만: 그 도트와 꾸민 캐릭터 사이를 오가는 단추
            if av and av.get("hasImage"):
                self.av_swap.configure(text="꾸민 캐릭터 쓰기" if av.get("image") else "직접 그린 도트 쓰기")
                if not self.av_swap.holder.winfo_ismapped():
                    self.av_swap.pack(side="left", padx=(8, 0))
            else:
                self.av_swap.pack_forget()
        except tk.TclError:
            pass

    def swap_avatar(self):
        """넣어 둔 '직접 그린 도트' 와 꾸민 캐릭터 사이를 오간다."""
        av = self.avatar() or {}
        if not av.get("hasImage"):
            return
        on = not av.get("image")
        api = self.app.api

        def done(r, err):
            if not self.alive:
                return
            if err:
                return self.say(_err(err), U.DANGER)
            self._avatar_saved((r or {}).get("avatar") or av, (r or {}).get("message"))
        run_async(self.root, lambda: api.avatar_image(on), done)

    def open_avatar(self):
        from . import ui_avatar
        ed = self.editor
        if ed is not None and ed.alive:             # 이미 떠 있다 - 하나 더 띄우지 않는다
            try:
                ed.win.lift()
                return ed
            except tk.TclError:
                pass
        self.editor = ui_avatar.open_editor(self.win, self.app, self.avatar(), self._avatar_saved)
        return self.editor

    def _avatar_saved(self, av, message=None):
        if not self.alive:
            return
        if self.data is not None:
            self.data["avatar"] = av
        self._paint_avatar()
        self.say(message or "캐릭터를 저장했습니다.")

    def tiles(self, d):
        return tile_items(d)

    def _tiles(self, d):
        grid = tk.Frame(self.inner, bg=U.BG)
        grid.pack(fill="x", pady=(10, 0), padx=(0, 8))
        items = self.tiles(d)
        cols = 3
        for i in range(cols):
            grid.columnconfigure(i, weight=1, uniform="tile")
        for i, (name, value, note) in enumerate(items):
            t = tk.Frame(grid, bg=TILE, highlightthickness=1, highlightbackground=U.LINE)
            t.grid(row=i // cols, column=i % cols, sticky="nsew",
                   padx=(0 if i % cols == 0 else 8, 0), pady=(0, 8))
            tk.Label(t, text=name, bg=TILE, fg=U.FG_DIM, font=U.FONT_XS, anchor="w").pack(
                fill="x", padx=12, pady=(9, 0))
            tk.Label(t, text=value, bg=TILE, fg=U.FG, font=U.FONT_H, anchor="w").pack(
                fill="x", padx=12)
            tk.Label(t, text=note or " ", bg=TILE, fg=U.FG_FAINT, font=U.FONT_XS,
                     anchor="w").pack(fill="x", padx=12, pady=(0, 9))

    # ---------------- 집중 기록 (집중 타이머) ----------------
    # 상태: f_ym 보는 달 · f_this 이번 달 · f_days {날: 분} · f_day 고른 날 · f_rows 그날 기록.
    # 달 넘기기 · 날 고르기는 서버에 따로 묻고, 바뀌면 _focus_changed (기본은 이 칸만 다시, DP 는 쪽 전체를 다시).
    def _focus_init(self, d):
        f = (d or {}).get("focus")
        self.focus_data = f or None
        self.f_cells = {}
        self.f_day = None
        self.f_rows = None
        self._f_gen = getattr(self, "_f_gen", 0) + 1
        if f:
            m = f.get("month") or {}
            self.f_ym = self.f_this = m.get("ym") or ""
            self.f_days = dict(m.get("days") or {})

    def focus_can_next(self):
        return bool(getattr(self, "focus_data", None)) and self.f_ym < self.f_this

    def focus_turn(self, delta):
        if not getattr(self, "focus_data", None):
            return
        ym = shift_ym(self.f_ym, delta)
        if ym > self.f_this:
            return
        self._f_gen += 1
        gen = self._f_gen
        api = self.app.api

        def done(r, err):
            if not self.alive or gen != self._f_gen:
                return
            if err:
                return self.say(_err(err), U.DANGER)
            self.f_ym = (r or {}).get("ym") or ym
            self.f_days = dict((r or {}).get("days") or {})
            self.f_day = self.f_rows = None
            self._focus_changed()
        run_async(self.root, lambda: api.focus_month(ym), done)

    def focus_pick(self, date):
        self._f_gen += 1
        gen = self._f_gen
        api = self.app.api

        def done(r, err):
            if not self.alive or gen != self._f_gen:
                return
            if err:
                return self.say(_err(err), U.DANGER)
            self.f_day = date
            self.f_rows = list((r or {}).get("rows") or [])
            self._focus_changed()
        run_async(self.root, lambda: api.focus_day(date), done)

    def _focus_changed(self):
        self._paint_focus()

    def _focus(self, d):
        self.f_box = None
        if not getattr(self, "focus_data", None):
            return
        self.f_box = self._section("집중 기록", "포켓몬과 집중한 시간")
        self._paint_focus()

    def _paint_focus(self):
        box = getattr(self, "f_box", None)
        if box is None or not self.alive:
            return
        for w in box.winfo_children():
            w.destroy()
        self.f_cells = {}
        sm = (self.focus_data or {}).get("summary") or {}
        lb = tk.Label(box, text=focus_summary(sm), bg=CARD, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                      justify="left")
        lb.pack(fill="x", padx=14, pady=(12, 6))
        U.wrap_to_width(lb)
        nav = tk.Frame(box, bg=CARD)
        nav.pack(fill="x", padx=14)
        prev = U.ghost_button(nav, "◀", lambda: self.focus_turn(-1), height=26)
        prev.pack(side="left")
        tk.Label(nav, text=month_title(self.f_ym), bg=CARD, fg=U.FG, font=U.FONT_B).pack(side="left", padx=10)
        nxt = U.ghost_button(nav, "▶", lambda: self.focus_turn(1), height=26)
        nxt.pack(side="left")
        if not self.focus_can_next():
            nxt.configure(state="disabled")
        grid = tk.Frame(box, bg=CARD)
        grid.pack(fill="x", padx=14, pady=(8, 4))
        for i, ch in enumerate(WEEK):
            grid.grid_columnconfigure(i, weight=1, uniform="fday")
            tk.Label(grid, text=ch, bg=CARD, fg=U.DANGER if i == 0 else U.FG_FAINT, font=U.FONT_XS).grid(
                row=0, column=i, sticky="ew")
        import time as _t
        today = _t.strftime("%Y-%m-%d")
        for c in focus_cells(self.f_ym, self.f_days):
            lv = c["level"]
            bg = blend(TILE, U.ACCENT, HEAT_MIX[lv])
            fg = U.ACCENT_DARK if lv >= 3 else (U.FG if lv else U.FG_DIM)
            cell = tk.Label(grid, text=cell_text(c), bg=bg, fg=fg, font=U.FONT_XS, height=2, justify="center",
                            cursor="hand2", highlightthickness=1,
                            highlightbackground=U.ACCENT if c["date"] == today else (
                                U.FG if c["date"] == self.f_day else bg))
            cell.grid(row=c["row"] + 1, column=c["col"], sticky="nsew", padx=2, pady=2)
            cell.bind("<Button-1>", lambda _e, dt=c["date"]: self.focus_pick(dt))
            self.f_cells[c["day"]] = cell
        if self.f_day:
            tk.Label(box, text="%d월 %d일" % (int(self.f_day[5:7]), int(self.f_day[8:10])), bg=CARD, fg=U.FG,
                     font=U.FONT_S, anchor="w").pack(fill="x", padx=14, pady=(6, 2))
            rows = self.f_rows or []
            if not rows:
                tk.Label(box, text="이날은 집중한 기록이 없습니다.", bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS,
                         anchor="w").pack(fill="x", padx=14)
            for r in rows:
                line = tk.Label(box, text=day_line(r), bg=CARD, fg=U.FG_DIM if r.get("full") else U.FG_FAINT,
                                font=U.FONT_XS, anchor="w", justify="left")
                line.pack(fill="x", padx=14)
                U.wrap_to_width(line)
            tk.Frame(box, bg=CARD, height=U.h(10)).pack(fill="x")
        else:
            tk.Label(box, text="날을 누르면 그날 기록이 보여요.", bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS,
                     anchor="w").pack(fill="x", padx=14, pady=(2, 12))
        self.root.after_idle(self._reflow)

    def _titles(self, d):
        t = d.get("titles") or {}
        box = self._section("내 칭호", "%d / %d" % (int(t.get("count") or 0),
                                                 int(t.get("total") or 0)),
                            action=("칭호·명패 바꾸기", self.open_rewards))
        own = t.get("owned") or []
        if not own:
            tk.Label(box, text="아직 가진 칭호가 없습니다. 도감 탭의 '칭호' 에서 얻는 방법을 "
                               "볼 수 있습니다.", bg=CARD, fg=U.FG_FAINT, font=U.FONT_S,
                     anchor="w", justify="left").pack(fill="x", padx=14, pady=12)
            return
        flow = Flow(box, CARD)
        flow.frame.pack(fill="x", padx=14, pady=12)
        for c in own:
            on = c.get("name") == t.get("equipped")
            lb = tk.Label(flow.frame, text=c.get("name") or "", font=U.FONT_S, padx=9,
                          pady=U.h(3), bg=U.ACCENT if on else U.BG4,
                          fg=U.ACCENT_DARK if on else U.FG)
            flow.add(lb)
        self.flows.append(flow)
        if t.get("equipped"):
            tk.Label(box, text="금색이 지금 달고 있는 칭호입니다. '칭호·명패 바꾸기' 에서 바꿀 수 있습니다.",
                     bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w").pack(
                fill="x", padx=14, pady=(0, 10))

    def open_rewards(self):
        """가진 칭호·명패 중에서 하나씩 단다 (1.12.1 - 랭킹 탭에 있던 창). 달면 이 쪽을 다시 받는다."""
        from .ui_season import RewardsWindow
        RewardsWindow(self.app, on_saved=self.load)

    def _seasons(self, d):
        box = self._section("시즌 기록")
        rows = d.get("seasons") or []
        for i, s in enumerate(rows):
            head, body = season_line(s)
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", padx=14, pady=(10 if i == 0 else 0, 10))
            tk.Label(row, text=head, bg=CARD, fg=U.ACCENT if s.get("current") else U.FG,
                     font=U.FONT_B, anchor="w", width=13).pack(side="left", anchor="n")
            lb = tk.Label(row, text=body, bg=CARD, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                          justify="left")
            lb.pack(side="left", fill="x", expand=True)
            U.wrap_to_width(lb)
        if not rows:
            tk.Label(box, text="시즌 기록이 없습니다.", bg=CARD, fg=U.FG_FAINT,
                     font=U.FONT_S, anchor="w").pack(fill="x", padx=14, pady=12)

    # ---------------- 게시판 활동 ----------------
    # 활동은 계속 쌓인다. 다 늘어놓으면 마이페이지가 끝없이 길어지므로
    # **한 번에 한 종류, 한 쪽(다섯 줄)만** 그린다. [알림 | 내 글 | 내 댓글] 로
    # 고르고 ◀ ▶ 로 넘긴다. 글이 천 개여도 이 칸의 높이는 같다.
    def tab_label(self, what, counts):
        if what == "notify":
            n = int(counts.get("unseen") or 0)
            return "알림 %d" % n if n else "알림"
        if what == "posts":
            return "내 글 %d" % int(counts.get("postCount") or 0)
        return "내 댓글 %d" % int(counts.get("commentCount") or 0)

    def _board(self, d):
        b = d.get("board") or {}
        first = b.get("first") or {}
        self.b_counts = dict(b)
        self.b_what = first.get("what") or "posts"
        self.b_page = int(first.get("page") or 1)
        self.b_pages = int(first.get("pages") or 1)
        self.b_gen = 0
        self.b_min_h = 0
        box = self._section("게시판 활동", "받은 좋아요 %d" % int(b.get("likes") or 0))
        bar = tk.Frame(box, bg=CARD)
        bar.pack(fill="x", padx=14, pady=(12, 8))
        self.b_seg = U.Segmented(bar, [(k, self.tab_label(k, b)) for k in TABS],
                                 self.b_what, self.pick_tab)
        self.b_seg.pack(side="left")
        nav = tk.Frame(bar, bg=CARD)
        nav.pack(side="right")
        # 알림을 하나씩 열어 보지 않고 한꺼번에 치운다 (알림 탭에 알림이 있을 때만 보인다)
        self.b_clear = U.ghost_button(nav, "모두 읽음", self.clear_notify, height=28)
        self.b_prev = U.ghost_button(nav, "◀", lambda: self.turn(-1), height=28)
        self.b_prev.pack(side="left")
        self.b_lbl = tk.Label(nav, text="", bg=CARD, fg=U.FG_DIM, font=U.FONT_S)
        self.b_lbl.pack(side="left", padx=10)
        self.b_next = U.ghost_button(nav, "▶", lambda: self.turn(1), height=28)
        self.b_next.pack(side="left")
        tk.Frame(box, bg=U.LINE, height=U.h(1)).pack(fill="x", padx=14)
        hold = tk.Frame(box, bg=CARD)
        hold.pack(fill="x", padx=14, pady=(8, 10))
        # 버팀대: 쪽마다 줄 수가 달라도(마지막 쪽) 칸 높이가 출렁이지 않게
        self.b_strut = tk.Frame(hold, bg=CARD, width=1, height=1)
        self.b_strut.pack(side="left")
        self.b_list = tk.Frame(hold, bg=CARD)
        self.b_list.pack(side="left", fill="x", expand=True, anchor="n")
        self._fill_tab(first)

    def pick_tab(self, what):
        self.b_what, self.b_page = what, 1
        self.b_seg.set(what)
        self.load_tab()

    def turn(self, delta):
        page = max(1, min(self.b_pages, self.b_page + delta))
        if page != self.b_page:
            self.b_page = page
            self.load_tab()

    def clear_notify(self):
        """'모두 읽음' - 알림을 다 지운다."""
        self.b_gen += 1
        gen, page_gen = self.b_gen, self._gen
        api = self.app.api

        def done(_r, err):
            if not self.alive or gen != self.b_gen or page_gen != self._gen:
                return
            if err:
                return self.say(_err(err), U.DANGER)
            self.b_page = 1
            self.load_tab()
            self.say("알림을 모두 읽은 것으로 했습니다.")
        run_async(self.root, lambda: api.board_notify_seen(), done)

    def load_tab(self):
        self.b_gen += 1
        gen, page_gen = self.b_gen, self._gen
        what, page = self.b_what, self.b_page
        api = self.app.api

        def done(r, err):
            if not self.alive or gen != self.b_gen or page_gen != self._gen:
                return                       # 그사이 다른 탭·쪽을 골랐거나 새로 그렸다
            if err:
                return self.say(_err(err), U.DANGER)
            self._fill_tab(r or {})
            self.say("")
        run_async(self.root, lambda: api.board_mine(what, page), done)

    def _fill_tab(self, r):
        what = r.get("what") or self.b_what
        self.b_what = what
        self.b_page = int(r.get("page") or 1)
        self.b_pages = int(r.get("pages") or 1)
        if r.get("counts"):
            self.b_counts.update(r["counts"])
        try:
            for k in TABS:
                self.b_seg.cells[k].configure(text=self.tab_label(k, self.b_counts))
            self.b_seg.set(what)
            for w in self.b_list.winfo_children():
                w.destroy()
        except tk.TclError:
            return
        items = r.get("items") or []
        for x in items:
            if what == "notify":
                # 여기 있는 것은 다 아직 안 본 알림이다 (본 것은 서버가 지운다)
                kind = "답글" if x.get("kind") == "reply" else "댓글"
                self._line("%s 님의 %s" % (x.get("actor") or "?", kind),
                           "%s — %s" % (x.get("title") or "", x.get("snippet") or ""),
                           ago(x.get("agoSec")), x.get("postId"), U.ACCENT)
            elif what == "posts":
                tail = []
                if int(x.get("likes") or 0):
                    tail.append("좋아요 %d" % int(x["likes"]))
                if int(x.get("comments") or 0):
                    tail.append("댓글 %d" % int(x["comments"]))
                tail.append(ago(x.get("agoSec")))
                self._line(x.get("kindKr") or "", x.get("title") or "",
                           " · ".join(t for t in tail if t), x.get("postId") or x.get("id"),
                           KIND_COLOR.get(x.get("kind"), U.FG_DIM), chip=True)
            else:
                self._line("", x.get("snippet") or "",
                           "%s · %s" % (x.get("title") or "", ago(x.get("agoSec"))),
                           x.get("postId"), U.FG_DIM)
        if not items:
            tk.Label(self.b_list, text=EMPTY[what], bg=CARD, fg=U.FG_FAINT, font=U.FONT_S,
                     anchor="w").pack(fill="x", pady=(2, 5))
        try:
            if what == "notify" and items:
                self.b_clear.pack(side="left", padx=(0, 10), before=self.b_prev.holder)
            else:
                self.b_clear.pack_forget()
        except tk.TclError:
            pass
        # 탭의 점과 트레이의 수도 방금 들은 값으로 맞춘다 (다음 동기화를 안 기다린다)
        sync = getattr(self.app, "set_board_unseen", None)
        if sync and r.get("counts"):
            sync(self.b_counts.get("unseen"))
        self.b_lbl.configure(text="%d / %d" % (self.b_page, self.b_pages))
        self.b_prev.configure(state="normal" if self.b_page > 1 else "disabled")
        self.b_next.configure(state="normal" if self.b_page < self.b_pages else "disabled")
        try:
            self.b_list.update_idletasks()
            self.b_min_h = max(self.b_min_h, self.b_list.winfo_reqheight())
            self.b_strut.configure(height=self.b_min_h)
            self.fit.fit_now()
        except Exception:                                   # noqa: BLE001
            pass

    def _line(self, tag, text, tail, pid, color, chip=False):
        """글 하나를 가리키는 한 줄. 누르면 게시판의 그 글로 간다."""
        row = tk.Frame(self.b_list, bg=CARD, cursor="hand2")
        row.pack(fill="x", pady=(0, 5))
        parts = [row]
        if tag and chip:
            t = U.chip(row, tag, color, font=U.FONT_XS, padx=6)
            t.pack(side="left", anchor="n", pady=(1, 0))
            parts.append(t)
        elif tag:
            t = tk.Label(row, text=tag, bg=CARD, fg=color, font=U.FONT_S)
            t.pack(side="left", anchor="n")
            parts.append(t)
        tl = tk.Label(row, text=tail, bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS)
        tl.pack(side="right", anchor="n", padx=(8, 0), pady=(1, 0))
        lb = tk.Label(row, text=text, bg=CARD, fg=U.FG, font=U.FONT_S, anchor="w",
                      justify="left")
        lb.pack(side="left", fill="x", expand=True, padx=(8 if tag else 0, 0))
        U.wrap_to_width(lb)
        parts += [tl, lb]
        for w in parts:
            w.bind("<Button-1>", lambda _e, i=pid: self.open_post(i))
            w.bind("<Enter>", lambda _e, w2=lb: w2.configure(fg=U.ACCENT_TEXT))
            w.bind("<Leave>", lambda _e, w2=lb: w2.configure(fg=U.FG))

    def open_post(self, pid):
        if not pid:
            return
        self.app.open_board(post=pid)
        if getattr(self, "b_what", None) == "notify":
            # 그 글을 열면 서버가 그 알림을 지운다. 돌아왔을 때 이미 본 알림이
            # 남아 있지 않게, 게시판이 글을 받아 온 뒤에 이 쪽을 다시 받는다.
            self.root.after(RELOAD_MS, self._reload_notify)

    def _reload_notify(self):
        if self.alive and getattr(self, "b_what", None) == "notify":
            self.load_tab()

    # ---------------- 끝 ----------------
    # ---------------- 계정 ----------------
    # 로그아웃과 회원탈퇴는 트레이 메뉴의 '종료' 바로 위에 있었다. 끄려다
    # 잘못 누를까 겁난다는 말이 있어 여기 맨 아래로 옮겼다 (1.9.2).
    # 하는 일은 그대로다 - 둘 다 확인 창을 거치고, 탈퇴는 비밀번호까지
    # 묻는다 (app.logout / app.delete_account).
    def account_rows(self):
        """(설명, 단추 글자, 할 일, 위험한가). 화면과 검사가 같이 쓴다.
        **단추 글자는 늘 같다** - DP 테마가 창을 열 때 단추를 한 번 만들어 둔다 (설명 글만 자료에 따라 바뀐다)."""
        a = self.app
        return [
            (email_text((self.data or {}).get("user") or {}), EMAIL_BTN, self.edit_email, False),
            ("이 기기에 저장된 로그인을 지우고 로그인 화면으로 돌아갑니다.",
             "로그아웃", a.logout, False),
            ("계정과 가진 포켓몬이 모두 지워집니다. 되돌릴 수 없습니다.",
             "회원탈퇴", a.delete_account, True),
        ]

    def edit_email(self):
        """이메일 적기 · 바꾸기 · 지우기 (빈 칸으로 확인하면 지운다)."""
        if getattr(self, "_email_busy", False):
            return
        now = ((self.data or {}).get("user") or {}).get("email") or ""
        email = ui_box.ask_text(self.win, "이메일 등록",
                                "비밀번호를 잊었을 때 운영진이 계정을 확인하는 데 쓰는 이메일입니다. "
                                "다른 사람에게는 보이지 않습니다.",
                                hint="지우려면 칸을 비우고 확인을 누르세요.", initial=now)
        if email is None or email.strip() == now:
            return
        api = self.app.api
        self._email_busy = True
        self.say("저장하는 중...", U.FG_FAINT)

        def done(r, err):
            self._email_busy = False
            if not self.alive:
                return
            if err:
                return self.say(_err(err), U.DANGER)
            msg = (r or {}).get("message") or "저장했습니다."
            self.say(msg, U.GOOD)
            self._note_after = (msg, U.GOOD)     # 다시 읽어도 이 글이 남게 (load 가 아래 줄을 비운다)
            self.refresh()
        run_async(self.root, lambda: api.set_email(email.strip()), done)

    def _account(self):
        box = self._section("계정")
        self.account_btns = {}
        for i, (text, label, fn, danger) in enumerate(self.account_rows()):
            if i:
                tk.Frame(box, bg=U.LINE, height=U.h(1)).pack(fill="x", padx=14)
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", padx=14, pady=10)
            make = U.danger_button if danger else U.ghost_button
            btn = make(row, label, fn, height=32)
            btn.pack(side="right", padx=(12, 0))
            self.account_btns[label] = btn
            lb = tk.Label(row, text=text, bg=CARD, fg=U.FG_DIM, font=U.FONT_S,
                          anchor="w", justify="left")
            lb.pack(side="left", fill="x", expand=True)
            U.wrap_to_width(lb)

    def close(self):
        self.alive = False
        self._gen += 1
        if self.editor is not None:
            try:
                self.editor.close()
            except Exception:                               # noqa: BLE001
                pass
            self.editor = None
        if self.settings is not None:
            try:
                self.settings.close()
            except Exception:                               # noqa: BLE001
                pass
            self.settings = None
        if getattr(self.app, "mypage_window", None) is self:
            self.app.mypage_window = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def focus(self):
        if U.is_embedded(self.win):
            return
        try:
            self.win.deiconify()
            self.win.lift()
        except tk.TclError:
            pass
