# -*- coding: utf-8 -*-
"""랭킹 — 점수 순으로 줄 세운 판.

점수는 **내가 건 랜덤 배틀**만 움직인다. 상대는 접속해 있지 않아도 붙는
구조라(자는 사람의 파티를 가져와 돌린다), 걸려온 판까지 점수에 넣으면
자는 동안 남이 몇 번 걸었느냐로 내 등수가 정해진다.

배치(5판)를 마쳐야 표에 오른다. 한 판 이기고 승률 100% 로 1등이 되는
것을 막는다.
"""
import tkinter as tk

from . import ui_common as U
from . import ui_loading
from .ui_common import run_async

W, H = 900, 660

# 1·2·3 등만 색으로 구분한다. 그 아래까지 물들이면 표가 시끄러워진다.
MEDAL = {1: "#ffc043", 2: "#c9d1e6", 3: "#d08a52"}


class RankWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.busy = False
        self.rows = []
        self.me = {}
        self.season = 1
        self.placement = 5

        self.win = U.panel(parent, self.root, "포스크탑 — 랭킹",
                           W, H, 700, 520, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)

        self._header()
        self._body()
        self._status()
        self.reload()

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=62)
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)
        self.title = tk.Label(inner, text="랭킹", bg=U.BG2, fg=U.FG,
                              font=(U.FAMILY_BLACK, 15))
        self.title.pack(side="left", pady=17)
        self.sub = tk.Label(inner, text="", bg=U.BG2, fg=U.FG_DIM,
                            font=U.FONT_XS)
        self.sub.pack(side="left", padx=(12, 0))

        U.ghost_button(inner, "새로고침", self.reload,
                       height=32).pack(side="right", pady=15)
        U.ghost_button(inner, "랜덤 배틀", self._random,
                       height=32).pack(side="right", padx=(0, 8), pady=15)
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x")

    def _body(self):
        wrap = tk.Frame(self.win, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=16, pady=(8, 0))
        cv = tk.Canvas(wrap, bg=U.BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        self.list = tk.Frame(cv, bg=U.BG)
        self._win_id = cv.create_window((0, 0), window=self.list, anchor="nw")
        self.list.bind("<Configure>", lambda _e: self.fit_scroll())
        cv.bind("<Configure>", lambda e: (
            cv.itemconfigure(self._win_id, width=e.width), self.fit_scroll()))
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        U.scrollable(cv, 120)
        self.cv = cv

    def fit_scroll(self):
        """내용이 화면보다 짧으면 스크롤할 게 없어야 한다."""
        try:
            self.cv.update_idletasks()
            h = self.list.winfo_reqheight()
            view = self.cv.winfo_height()
            w = self.cv.winfo_width()
            if h <= view:
                self.cv.configure(scrollregion=(0, 0, w, view))
                self.cv.yview_moveto(0)
            else:
                self.cv.configure(scrollregion=(0, 0, w, h))
        except Exception:                                   # noqa: BLE001
            pass

    def _status(self):
        self.status = U.status_line(self.win, "")
        self.status.pack(fill="x", padx=16, pady=(6, 12))

    def say(self, text, color=U.GOOD):
        U.set_status(self.status, text, color)

    # ---------------- 자료 ----------------
    def reload(self):
        if self.busy:
            return
        self.busy = True
        wait = ui_loading.Overlay(self.win, "랭킹을 불러오는 중")

        def done(r, err):
            self.busy = False
            wait.close()
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            self.rows = r.get("ranking") or []
            self.me = r.get("me") or {}
            self.season = r.get("season", 1)
            self.placement = r.get("placement", 5)
            self.draw()
        run_async(self.root, self.app.api.pvp_ranking, done)

    # ---------------- 그리기 ----------------
    def draw(self):
        for w in self.list.winfo_children():
            w.destroy()

        self.title.configure(text="랭킹  ·  시즌 %d" % self.season)
        me = self.me
        bits = ["내 점수 %d" % me.get("rating", 0)]
        if me.get("ranked"):
            mine = next((x for x in self.rows if x.get("me")), None)
            bits.append("%d위" % mine["rank"] if mine else "순위 밖")
        else:
            left = me.get("placementLeft", self.placement)
            bits.append("배치까지 %d판" % left if left else "곧 오릅니다")
        bits.append("%d전 %d승 %d패" % (me.get("games", 0), me.get("wins", 0),
                                      me.get("losses", 0)))
        self.sub.configure(text="  ·  ".join(bits))

        # 점수가 어떻게 오르는지 한 줄. 규칙이 바뀐 판이라 안 적어 두면
        # "왜 걸려온 판은 안 세지" 를 알 길이 없다.
        note = tk.Label(
            self.list,
            text="점수는 내가 건 랜덤 배틀만 오르내립니다. "
                 "걸려온 판과 친구 배틀은 점수에 들어가지 않습니다.",
            bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w",
            justify="left", wraplength=W - 80)
        note.pack(fill="x", pady=(0, 8))

        if not self.rows:
            tk.Label(self.list,
                     text="아직 순위표가 비어 있습니다.\n"
                          "랜덤 배틀 %d판을 치르면 이름이 올라갑니다."
                          % self.placement,
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S,
                     justify="center").pack(pady=48)
            return self.fit_scroll()

        for r in self.rows:
            self._card(r)
        self.fit_scroll()

    def _card(self, r):
        mine = bool(r.get("me"))
        rank = r.get("rank", 0)
        # 내 줄은 금색 테두리로 찾기 쉽게. 목록이 길어지면 자기 줄을
        # 눈으로 뒤지게 된다.
        box = tk.Frame(self.list, bg=U.BG2 if mine else "#161b28",
                       highlightthickness=2,
                       highlightbackground=U.ACCENT if mine else U.LINE)
        box.pack(fill="x", pady=(0, 7))
        inner = tk.Frame(box, bg=box["bg"])
        inner.pack(fill="x", padx=13, pady=10)

        tk.Label(inner, text="%d" % rank, bg=box["bg"],
                 fg=MEDAL.get(rank, U.FG_DIM),
                 font=(U.FAMILY_BLACK, 13), width=3,
                 anchor="e").pack(side="left")

        left = tk.Frame(inner, bg=box["bg"])
        left.pack(side="left", fill="x", expand=True, padx=(12, 0))
        top = tk.Frame(left, bg=box["bg"])
        top.pack(fill="x")
        tk.Label(top, text=r.get("name", "?"), bg=box["bg"],
                 fg=U.ACCENT if mine else U.FG,
                 font=U.FONT_B).pack(side="left")
        if mine:
            tk.Label(top, text="나", bg=U.ACCENT, fg="#14141a",
                     font=U.FONT_XS, padx=5).pack(side="left", padx=(8, 0))

        streak = r.get("streak", 0)
        bits = ["%d전 %d승 %d패" % (r.get("games", 0), r.get("wins", 0),
                                  r.get("losses", 0))]
        if r.get("draws"):
            bits.append("%d무" % r["draws"])
        if streak >= 2:
            bits.append("%d연승" % streak)
        elif streak <= -2:
            bits.append("%d연패" % abs(streak))
        tk.Label(left, text="  ·  ".join(bits), bg=box["bg"], fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(anchor="w", pady=(4, 0))

        tk.Label(inner, text="%d" % r.get("rating", 0), bg=box["bg"],
                 fg=U.FG, font=U.FONT_NUM).pack(side="right")

    # ---------------- 동작 ----------------
    def _random(self):
        self.say("상대를 찾는 중...")
        self.app.pvp_random()
        self.root.after(2500, self.reload)

    # ---------------- 끝 ----------------
    def focus(self):
        if U.is_embedded(self.win):
            return
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except Exception:                                   # noqa: BLE001
            pass

    def close(self):
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        if getattr(self.app, "rank_window", None) is self:
            self.app.rank_window = None
