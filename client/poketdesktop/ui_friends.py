# -*- coding: utf-8 -*-
"""친구 창.

찾기 · 신청 · 수락 · 삭제 · 차단이 전부 여기서 끝난다.

**폴링하지 않는다.** 창을 열 때와 무언가를 한 뒤에만 목록을 다시 받는다.
Turso 는 왕복 하나가 곧 비용이라, 항상 도는 폴링은 꼭 필요한 하나로
몰기로 했다. 대신 '새로고침' 을 눈에 잘 띄는 자리에 둔다.

목록은 세 덩이다 — 받은 신청(먼저 처리해야 하니 맨 위), 친구, 그리고
보낸 신청과 차단(접었다 펴는 자리). 아무것도 없을 때가 대부분일 화면이라
빈 상태에서 무엇을 해야 하는지가 잘 보여야 한다.
"""
import tkinter as tk

from . import ui_common as U
from . import ui_loading
from .ui_common import run_async

W, H = 560, 620


class FriendsWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.data = None
        self.busy = False

        # parent 가 있으면 탭 안의 한 칸으로, 없으면 지금까지처럼 창으로.
        self.win = U.panel(parent, self.root, "포스크탑 — 친구",
                           W, H, 500, 480, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            # 탭으로 들어갈 때는 허브가 이미 걸어 두었다.
            U.install_wheel(self.win)

        self._header()
        self._search()
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

        cv = tk.Canvas(inner, width=28, height=28, bg=U.BG2,
                       highlightthickness=0, bd=0)
        cv.pack(side="left", pady=17)
        cv.create_oval(2, 2, 26, 26, fill="#f4f6fb", outline=U.INK, width=3)
        cv.create_arc(2, 2, 26, 26, start=0, extent=180, fill=U.RED,
                      outline=U.INK, width=3)
        cv.create_rectangle(2, 12, 26, 16, fill=U.INK, outline="")
        cv.create_oval(10, 10, 18, 18, fill="#f4f6fb", outline=U.INK, width=2)

        tk.Label(inner, text="친구", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, 15)).pack(side="left", padx=(12, 12))
        self.count = tk.Label(inner, text="", bg=U.BG2, fg=U.FG_FAINT,
                              font=U.FONT_S)
        self.count.pack(side="left")
        U.ghost_button(inner, "새로고침", self.reload,
                       height=32).pack(side="right", pady=15)
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x")

    # ---------------- 찾기 ----------------
    def _search(self):
        box = tk.Frame(self.win, bg=U.BG)
        box.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(box, text="닉네임으로 찾기", bg=U.BG, fg=U.FG_DIM,
                 font=U.FONT_S, anchor="w").pack(fill="x")
        row = tk.Frame(box, bg=U.BG)
        row.pack(fill="x", pady=(6, 0))
        self.q = tk.StringVar()
        e = U.entry(row, self.q)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda _e: self.do_search())
        U.ghost_button(row, "찾기", self.do_search, height=34).pack(
            side="left", padx=(8, 0))
        # 정확히 맞아야 찾아진다는 걸 미리 알려준다. 안 그러면 "왜 안 나오지"
        # 하면서 앞글자만 넣어 보게 된다.
        tk.Label(box, text="닉네임이 정확히 맞아야 찾을 수 있습니다.",
                 bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w").pack(
            fill="x", pady=(5, 0))
        self.found = tk.Frame(box, bg=U.BG)
        self.found.pack(fill="x", pady=(8, 0))

    # ---------------- 목록 ----------------
    def _body(self):
        wrap = tk.Frame(self.win, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=16, pady=(6, 0))
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
        # 서버가 자고 있으면 깨는 데 1분까지 걸린다. 그동안 빈 창을
        # 보여주면 고장으로 오해한다.
        wait = ui_loading.Overlay(self.win, "친구 목록을 불러오는 중")

        def done(r, err):
            self.busy = False
            wait.close()
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            self.data = r
            self.draw()
        run_async(self.root, lambda: self.app.api.friends(), done)

    def act(self, fn, ok_msg=None):
        """무언가를 하고 목록을 다시 받는다."""
        if self.busy:
            return
        self.busy = True

        def done(r, err):
            self.busy = False
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            self.say((r or {}).get("message") or ok_msg or "됐습니다.")
            self.q.set("")
            for w in self.found.winfo_children():
                w.destroy()
            self.reload()
        run_async(self.root, fn, done)

    # ---------------- 찾기 결과 ----------------
    def do_search(self):
        name = self.q.get().strip()
        for w in self.found.winfo_children():
            w.destroy()
        if not name:
            return

        def done(r, err):
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            if not r.get("found"):
                return self._note(self.found, "그런 닉네임의 트레이너가 없습니다.")
            self._search_card(r)
        run_async(self.root, lambda: self.app.api.friend_search(name), done)

    def _search_card(self, r):
        rel = r.get("relation")
        card = U.framed(self.found, bg=U.BG3)
        card.pack(fill="x")
        row = tk.Frame(card, bg=U.BG3)
        row.pack(fill="x", padx=12, pady=10)
        self._dot(row, r.get("online"))
        tk.Label(row, text=r["name"], bg=U.BG3, fg=U.FG,
                 font=U.FONT_B).pack(side="left", padx=(8, 8))
        if r.get("ranked"):
            tk.Label(row, text="%d점" % r.get("rating", 0), bg=U.BG3,
                     fg=U.ACCENT, font=U.FONT_S).pack(side="left")

        uid = r["id"]
        if rel == "none":
            U.ghost_button(row, "친구 신청",
                           lambda: self.act(
                               lambda: self.app.api.friend_request(r["name"])),
                           height=30).pack(side="right")
        elif rel == "incoming":
            U.ghost_button(row, "수락",
                           lambda: self.act(
                               lambda: self.app.api.friend_accept(uid)),
                           height=30).pack(side="right")
        else:
            tk.Label(row, text={"self": "나 자신입니다",
                                "friend": "이미 친구입니다",
                                "outgoing": "신청을 보내 두었습니다",
                                "rejected": "거절된 신청이 있습니다",
                                "blocked": "신청할 수 없습니다"}.get(rel, ""),
                     bg=U.BG3, fg=U.FG_FAINT, font=U.FONT_S).pack(side="right")

    # ---------------- 그리기 ----------------
    def draw(self):
        for w in self.list.winfo_children():
            w.destroy()
        d = self.data or {}
        fr = d.get("friends") or []
        inc = d.get("incoming") or []
        out = d.get("outgoing") or []
        blk = d.get("blocked") or []
        on = sum(1 for f in fr if f.get("online"))
        lim = (d.get("limits") or {}).get("maxFriends", 30)
        self.count.configure(text="%d / %d명  ·  접속 중 %d명"
                                  % (len(fr), lim, on))

        if inc:
            self._title("받은 신청 %d" % len(inc), U.ACCENT)
            for x in inc:
                self._request_row(x)

        self._title("친구 %d" % len(fr))
        if not fr:
            self._note(self.list,
                       "아직 친구가 없습니다. 위에서 닉네임으로 찾아보세요.")
        for f in fr:
            self._friend_row(f)

        if out:
            self._title("보낸 신청 %d" % len(out), U.FG_DIM)
            for x in out:
                self._pending_row(x)
        if blk:
            self._title("차단 %d" % len(blk), U.FG_FAINT)
            for x in blk:
                self._blocked_row(x)
        # 목록이 줄었을 수 있다. 스크롤 위치가 남아 빈 화면이 보이지 않게.
        self.fit_scroll()

    def _title(self, text, color=U.FG_DIM):
        tk.Label(self.list, text=text, bg=U.BG, fg=color, font=U.FONT_S,
                 anchor="w").pack(fill="x", pady=(12, 5))

    def _note(self, parent, text):
        tk.Label(parent, text=text, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S,
                 anchor="w", justify="left", wraplength=W - 70).pack(
            fill="x", pady=6)

    def _dot(self, parent, online):
        cv = tk.Canvas(parent, width=10, height=10, bg=parent["bg"],
                       highlightthickness=0, bd=0)
        cv.pack(side="left")
        cv.create_oval(2, 2, 9, 9, fill=U.GOOD if online else U.FG_FAINT,
                       outline="")

    def _card(self):
        c = U.framed(self.list, bg=U.BG3)
        c.pack(fill="x", pady=3)
        row = tk.Frame(c, bg=U.BG3)
        row.pack(fill="x", padx=12, pady=9)
        return row

    def _friend_row(self, f):
        row = self._card()
        self._dot(row, f.get("online"))
        tk.Label(row, text=f["name"], bg=U.BG3, fg=U.FG,
                 font=U.FONT_B).pack(side="left", padx=(8, 8))
        if f.get("ranked"):
            tk.Label(row, text="%d점" % f.get("rating", 0), bg=U.BG3,
                     fg=U.ACCENT, font=U.FONT_S).pack(side="left")
        w, l = f.get("wins", 0), f.get("losses", 0)
        if w or l:
            tk.Label(row, text="%d승 %d패" % (w, l), bg=U.BG3, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left", padx=(8, 0))
        uid = f["id"]
        U.ghost_button(row, "삭제",
                       lambda: self.act(
                           lambda: self.app.api.friend_remove(uid),
                           "친구를 삭제했습니다."), height=28).pack(side="right")
        U.ghost_button(row, "차단",
                       lambda: self.act(
                           lambda: self.app.api.friend_block(uid)),
                       height=28).pack(side="right", padx=(0, 6))
        # 접속해 있지 않아도 걸린다 - 그 사람의 지금 파티를 가져와 싸운다.
        U.ghost_button(row, "배틀", lambda: self.app.pvp_challenge(uid),
                       height=28, fill=U.RED).pack(side="right", padx=(0, 6))

    def _request_row(self, x):
        row = self._card()
        tk.Label(row, text=x["name"], bg=U.BG3, fg=U.FG,
                 font=U.FONT_B).pack(side="left")
        tk.Label(row, text="님이 친구 신청을 보냈습니다", bg=U.BG3,
                 fg=U.FG_DIM, font=U.FONT_S).pack(side="left", padx=(6, 0))
        uid = x["id"]
        U.ghost_button(row, "거절",
                       lambda: self.act(
                           lambda: self.app.api.friend_remove(uid),
                           "신청을 거절했습니다."), height=28).pack(side="right")
        U.ghost_button(row, "수락",
                       lambda: self.act(
                           lambda: self.app.api.friend_accept(uid)),
                       height=28).pack(side="right", padx=(0, 6))

    def _pending_row(self, x):
        row = self._card()
        tk.Label(row, text=x["name"], bg=U.BG3, fg=U.FG_DIM,
                 font=U.FONT_S).pack(side="left")
        tk.Label(row, text="답을 기다리는 중", bg=U.BG3, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="left", padx=(6, 0))
        uid = x["id"]
        U.ghost_button(row, "취소",
                       lambda: self.act(
                           lambda: self.app.api.friend_remove(uid),
                           "신청을 취소했습니다."), height=28).pack(side="right")

    def _blocked_row(self, x):
        row = self._card()
        tk.Label(row, text=x["name"], bg=U.BG3, fg=U.FG_FAINT,
                 font=U.FONT_S).pack(side="left")
        uid = x["id"]
        U.ghost_button(row, "차단 해제",
                       lambda: self.act(
                           lambda: self.app.api.friend_unblock(uid),
                           "차단을 풀었습니다."), height=28).pack(side="right")

    # ---------------- 끝 ----------------
    def focus(self):
        if U.is_embedded(self.win):
            return          # 탭이면 허브가 앞으로 꺼내 준다
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
        if getattr(self.app, "friends_win", None) is self:
            self.app.friends_win = None
