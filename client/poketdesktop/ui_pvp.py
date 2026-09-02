# -*- coding: utf-8 -*-
"""대전 — 받은 판과 지난 전적을 목록으로.

지금까지는 트레이의 "받은 대전 보기" 가 **가장 최근 한 판**만 틀어 줬다.
여러 판이 밀려 있으면 나머지는 볼 방법이 없었고, 진 판을 다시 붙고
싶어도 친구 창으로 가서 이름을 찾아야 했다.

여기서는 목록으로 보여준다.
  · 안 본 판이 위에 모인다 (금색 점)
  · 아무 판이나 골라서 다시 볼 수 있다
  · **진 판 옆에 "다시 붙기"** 가 뜬다

다시 붙을 수 있는지는 **서버가 판정해서 보내준다**. 화면에서 조건을
다시 따지면(30분 쿨다운·하루 상한·차단) 서버 판정과 어긋난다.
"""
import tkinter as tk

from . import ui_common as U
from . import ui_loading
from .ui_common import run_async

W, H = 900, 660

RESULT = {"win": ("승", U.GOOD), "lose": ("패", U.RED), "draw": ("무", U.FG_DIM)}
KIND = {"random": "랜덤", "friend": "친구"}


def _when(s):
    """2026-09-02T03:22:07+00:00 -> 09-02 03:22."""
    t = (s or "").replace("T", " ")
    return t[5:16] if len(t) >= 16 else t


class PvpWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.rows = []
        self.busy = False
        self.unseen = set()

        self.win = U.panel(parent, self.root, "포스크탑 — 대전",
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
        tk.Label(inner, text="대전", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, 15)).pack(side="left", pady=17)
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
        wait = ui_loading.Overlay(self.win, "대전 기록을 불러오는 중")

        def work():
            api = self.app.api
            # 안 본 판과 전적을 같이 받는다. 전적에는 아직 안 본 것이
            # 무엇인지가 없어서 둘을 맞춰야 금색 점을 찍을 수 있다.
            return api.pvp_records(50), api.pvp_pending()

        def done(r, err):
            self.busy = False
            wait.close()
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            recs, pend = r
            self.rows = recs.get("records") or []
            self.summary = recs.get("summary") or {}
            self.fight = (pend or {}).get("fight") or {}
            self.unseen = set(m.get("id") for m in (pend or {}).get("matches") or [])
            self.draw()
        run_async(self.root, work, done)

    # ---------------- 그리기 ----------------
    def draw(self):
        for w in self.list.winfo_children():
            w.destroy()
        s = self.summary
        left = self.fight.get("left")
        bits = ["%d전 %d승 %d패 %d무" % (s.get("games", 0), s.get("wins", 0),
                                      s.get("losses", 0), s.get("draws", 0))]
        if s.get("ranked"):
            bits.append("점수 %d" % s.get("rating", 0))
        if left is not None:
            bits.append("오늘 %d판 더 걸 수 있음" % left)
        self.sub.configure(text="  ·  ".join(bits))

        if not self.rows:
            tk.Label(self.list, text="아직 대전 기록이 없습니다.\n"
                                     "랜덤 배틀로 한 판 붙어보세요.",
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S,
                     justify="center").pack(pady=48)
            return self.fit_scroll()

        # 안 본 판을 위로. 그 안에서는 최신순(서버가 이미 그 순서로 준다).
        rows = sorted(self.rows,
                      key=lambda r: 0 if r.get("matchId") in self.unseen else 1)
        for r in rows:
            self._card(r)
        self.fit_scroll()

    def _card(self, r):
        new = r.get("matchId") in self.unseen
        box = tk.Frame(self.list, bg=U.BG2 if new else "#161b28",
                       highlightthickness=2,
                       highlightbackground=U.ACCENT if new else U.LINE)
        box.pack(fill="x", pady=(0, 7))
        inner = tk.Frame(box, bg=box["bg"])
        inner.pack(fill="x", padx=13, pady=10)

        # 왼쪽: 승패 · 상대 · 언제
        left = tk.Frame(inner, bg=box["bg"])
        left.pack(side="left", fill="x", expand=True)
        top = tk.Frame(left, bg=box["bg"])
        top.pack(fill="x")
        mark, color = RESULT.get(r.get("result"), ("?", U.FG_DIM))
        tk.Label(top, text=mark, bg=color, fg="#14141a",
                 font=(U.FAMILY_BLACK, 11), width=3).pack(side="left")
        tk.Label(top, text=r.get("foe") or "?", bg=box["bg"], fg=U.FG,
                 font=U.FONT_B).pack(side="left", padx=(9, 0))
        if new:
            tk.Label(top, text="NEW", bg=box["bg"], fg=U.ACCENT,
                     font=U.FONT_XS).pack(side="left", padx=(8, 0))

        bits = [KIND.get(r.get("kind"), r.get("kind") or ""),
                _when(r.get("at")),
                "%d턴" % (r.get("turns") or 0),
                "남은 %d : %d" % (r.get("myLeft") or 0, r.get("foeLeft") or 0)]
        d = r.get("delta") or 0
        if d:
            bits.append("점수 %+d" % d)
        if r.get("reward"):
            bits.append("%s원" % format(r["reward"], ","))
        tk.Label(left, text="  ·  ".join(b for b in bits if b), bg=box["bg"],
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(anchor="w", pady=(4, 0))

        # 오른쪽: 단추
        right = tk.Frame(inner, bg=box["bg"])
        right.pack(side="right")
        if r.get("matchId"):
            U.ghost_button(right, "다시 보기",
                           lambda m=r["matchId"]: self._watch(m),
                           height=30).pack(side="right", padx=(6, 0))
        # 진 판에는 "복수", 그 밖에는 "다시 붙기". 하는 일은 같다.
        if r.get("canFight"):
            label = "복수하기" if r.get("result") == "lose" else "다시 붙기"
            U.ghost_button(right, label,
                           lambda u=r["foeId"]: self._fight(u),
                           height=30).pack(side="right")
        elif r.get("whyNot"):
            tk.Label(right, text=r["whyNot"][:22], bg=box["bg"],
                     fg=U.FG_FAINT, font=U.FONT_XS).pack(side="right")

    # ---------------- 동작 ----------------
    def _watch(self, mid):
        self.app.watch_match(mid)
        # 본 판은 더 이상 새 것이 아니다. 목록을 다시 받아 점을 지운다.
        self.root.after(1200, self.reload)

    def _fight(self, uid):
        if not uid:
            return
        self.say("도전하는 중...")
        self.app.pvp_challenge(uid)
        self.root.after(2500, self.reload)

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
        if getattr(self.app, "pvp_window", None) is self:
            self.app.pvp_window = None
