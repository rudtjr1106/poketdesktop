# -*- coding: utf-8 -*-
"""로그인 / 회원가입.

계정은 최대한 간단하게 — **닉네임 + 숫자 4자리**.
닉네임은 타이핑하는 동안 서버에 물어봐서 쓸 수 있는지 바로 알려준다.

회원가입에서는 1~9세대 어태커 27마리 중 하나를 고른다.
카드에 뜨는 그림은 **실제 도트**다(서버에서 받아 캐시한 움직이는 GIF).
"""
import tkinter as tk

from PIL import ImageTk

from common.korean import fmt as kfmt
from common.version import VERSION

from . import config, sprite_cache, sprites
from . import ui_common as U
from .api import Api

CHECK_DELAY = 420          # 타이핑이 멈추고 이만큼 뒤에 닉네임을 확인한다 (ms)
CARD_W, CARD_H = 116, 114


class PinEntry(object):
    """숫자 4칸짜리 비밀번호 입력.

    한 칸에 한 자씩. 숫자를 누르면 다음 칸으로, 지우면 앞 칸으로 간다.
    """

    def __init__(self, parent, digits=4, on_done=None):
        self.digits = digits
        self.on_done = on_done
        self.frame = tk.Frame(parent, bg=parent["bg"])
        self.boxes = []
        self.entries = []
        for i in range(digits):
            box = tk.Frame(self.frame, bg=U.INK, highlightthickness=2,
                           highlightbackground=U.LINE, highlightcolor=U.ACCENT,
                           width=42, height=44, bd=0)
            box.pack_propagate(False)
            box.pack(side="left", padx=(0, 7))
            e = tk.Entry(box, bg=U.INK, fg=U.FG, insertbackground=U.ACCENT,
                         relief="flat", bd=0, justify="center",
                         font=(U.FAMILY, 16, "bold"), highlightthickness=0,
                         show="●", width=2)
            e.pack(expand=True)
            e.bind("<KeyRelease>", lambda ev, k=i: self._typed(ev, k))
            e.bind("<FocusIn>",
                   lambda ev, b=box: b.configure(highlightbackground=U.ACCENT))
            e.bind("<FocusOut>",
                   lambda ev, b=box: b.configure(highlightbackground=U.LINE))
            self.boxes.append(box)
            self.entries.append(e)

    def pack(self, **kw):
        self.frame.pack(**kw)
        return self

    def _typed(self, ev, i):
        e = self.entries[i]
        if ev.keysym == "BackSpace":
            if not e.get() and i > 0:
                self.entries[i - 1].focus_set()
                self.entries[i - 1].delete(0, "end")
            return
        v = "".join(c for c in e.get() if c.isdigit())[:1]
        e.delete(0, "end")
        e.insert(0, v)
        if v and i + 1 < self.digits:
            self.entries[i + 1].focus_set()
        elif v and self.on_done:
            self.on_done()

    def get(self):
        return "".join(e.get() for e in self.entries)

    def clear(self):
        for e in self.entries:
            e.delete(0, "end")

    def focus(self):
        try:
            self.entries[0].focus_set()
        except Exception:
            pass


class StarterCard(object):
    """스타팅 포켓몬 카드 한 장. 실제 도트가 제자리에서 움직인다."""

    def __init__(self, parent, mon, on_pick):
        self.mon = mon
        self.on_pick = on_pick
        self.photos = []
        self.durations = [140]
        self.i = 0
        base = "#101623"

        self.box = tk.Frame(parent, bg=base, highlightthickness=2,
                            highlightbackground=U.LINE, highlightcolor=U.LINE,
                            width=CARD_W, height=CARD_H, cursor="hand2", bd=0)
        self.box.pack_propagate(False)
        self.tag = tk.Label(self.box, text="선택", bg=U.ACCENT, fg=U.ACCENT_DARK,
                            font=U.FONT_XS, padx=5)
        self.art = tk.Label(self.box, bg=base, text="", fg=U.FG_FAINT,
                            font=U.FONT_XS, height=4)
        self.art.pack(pady=(8, 0))
        self.name = tk.Label(self.box, text=mon["kr"], bg=base, fg=U.FG_DIM,
                             font=U.FONT_S)
        self.name.pack(pady=(3, 0))
        self.types = tk.Frame(self.box, bg=base)
        self.types.pack(pady=(4, 0))
        ids = mon.get("typeIds") or []
        for i, t in enumerate(mon.get("types") or []):
            tid = ids[i] if i < len(ids) else ""
            U.chip(self.types, t, U.TYPE_COLOR.get(tid, U.BG3),
                   padx=5).pack(side="left", padx=2)
        for w in (self.box, self.art, self.name, self.types):
            w.bind("<Button-1>", lambda e: self.on_pick(self.mon["internal"]))

    def pack(self, **kw):
        self.box.pack(**kw)
        return self

    def set_frames(self, photos, durations):
        self.photos = photos
        self.durations = durations or [140]
        if photos:
            self.art.configure(image=photos[0], text="", height=0)

    def step(self):
        if not self.photos:
            return 140
        self.i = (self.i + 1) % len(self.photos)
        try:
            self.art.configure(image=self.photos[self.i])
        except Exception:
            return 140
        return max(60, self.durations[self.i % len(self.durations)])

    def set_selected(self, on):
        bg = U.ACCENT_SOFT if on else "#101623"
        self.box.configure(bg=bg, highlightbackground=U.ACCENT if on else U.LINE,
                           highlightcolor=U.ACCENT if on else U.LINE)
        for w in (self.art, self.name, self.types):
            w.configure(bg=bg)
        self.name.configure(fg=U.ACCENT_TEXT if on else U.FG_DIM,
                            font=U.FONT_B if on else U.FONT_S)
        if on:
            self.tag.place(x=0, y=0, anchor="nw")
        else:
            self.tag.place_forget()


class LoginWindow(object):
    """결과는 self.result 에 담긴다. 취소하면 None."""

    def __init__(self, root, settings):
        self.root = root
        self.settings = settings
        self.result = None
        self.busy = False
        self.tab = "login"
        self.gens = []
        self.gen = 1
        self.cards = []
        self.genbtns = {}
        self.picked = None
        self.name_ok = False
        self._check_job = None
        self._anim_job = None

        self.win = tk.Toplevel(root)
        U.style_window(self.win, "포켓 데스크톱", 460, 748)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)
        self.win.resizable(False, False)

        U.ball_header(self.win, 460, 96, "포켓 데스크톱",
                      "바탕화면에서 포켓몬을 만나고 키웁니다",
                      "v" + VERSION).pack(fill="x")
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x")

        U.dot_footer(self.win, 460, "Enter 로 확인").pack(fill="x", side="bottom")

        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True, padx=20, pady=(15, 0))

        # 서버 주소는 평소에 보일 필요가 없다. 어디에 붙는지만 작게 알려주고,
        # 눌렀을 때만 고칠 수 있게 접어 둔다. (개발할 때 로컬 서버를 가리키거나,
        # 나중에 서버를 옮겼을 때만 쓴다)
        self.server = tk.StringVar(value=settings.get("server", ""))
        self.server_open = False

        self.server_bar = tk.Frame(body, bg=U.BG)
        self.server_bar.pack(fill="x", pady=(0, 2))
        self.server_label = tk.Label(
            self.server_bar, text=self._server_text(), bg=U.BG, fg=U.FG_FAINT,
            font=U.FONT_XS, cursor="hand2", anchor="w")
        self.server_label.pack(side="left")
        self.server_label.bind("<Button-1>", lambda _e: self._toggle_server())

        self.server_box = tk.Frame(body, bg=U.BG)
        U.entry(self.server_box, self.server).pack(fill="x", pady=(4, 0))
        self.server.trace_add("write", lambda *_a: self._server_changed())

        tabs = tk.Frame(body, bg=U.BG)
        tabs.pack(fill="x", pady=(11, 0))
        self.tab_login = self._tab(tabs, "로그인", "login")
        self.tab_signup = self._tab(tabs, "회원가입", "signup")
        tk.Frame(body, bg=U.LINE, height=2).pack(fill="x")

        self.panel = tk.Frame(body, bg=U.BG2, highlightthickness=2,
                              highlightbackground=U.LINE, bd=0)
        self.panel.pack(fill="both", expand=True)

        self.status = U.status_line(body, "", U.LINE)
        self.status.pack(fill="x", pady=(13, 13))

        self.show_login()
        self.win.bind("<Return>", lambda e: self._enter())

    # ---------------- 탭 ----------------
    def _server_text(self):
        """접속할 곳을 짧게. 주소 전체는 길어서 호스트만 보여준다."""
        raw = (self.server.get() or "").strip()
        host = raw.split("://")[-1].rstrip("/")
        return "서버: %s  (누르면 바꿀 수 있어요)" % (host or "정해지지 않음")

    def _server_changed(self):
        self.server_label.configure(text=self._server_text())

    def _toggle_server(self):
        self.server_open = not self.server_open
        if self.server_open:
            self.server_box.pack(fill="x", after=self.server_bar)
        else:
            self.server_box.pack_forget()

    def _tab(self, parent, text, key):
        f = tk.Frame(parent, bg=U.BG, cursor="hand2", bd=0)
        f.pack(side="left")
        lb = tk.Label(f, text=text, bg=U.BG, fg=U.FG_FAINT, font=U.FONT,
                      padx=22, pady=9, cursor="hand2")
        lb.pack()
        f._label = lb
        for w in (f, lb):
            w.bind("<Button-1>", lambda e, k=key: self.switch(k))
        return f

    def paint_tabs(self):
        for f, key in ((self.tab_login, "login"), (self.tab_signup, "signup")):
            on = (self.tab == key)
            f.configure(bg=U.BG2 if on else U.BG,
                        highlightthickness=2 if on else 0,
                        highlightbackground=U.LINE)
            f._label.configure(bg=U.BG2 if on else U.BG,
                               fg=U.ACCENT if on else U.FG_FAINT,
                               font=U.FONT_B if on else U.FONT)

    def switch(self, key):
        if self.tab == key or self.busy:
            return
        self.tab = key
        self.say("")
        self.show_login() if key == "login" else self.show_signup()

    def clear_panel(self):
        self.stop_anim()
        for w in self.panel.winfo_children():
            w.destroy()

    # ---------------- 로그인 ----------------
    def show_login(self):
        self.clear_panel()
        self.paint_tabs()
        p = tk.Frame(self.panel, bg=U.BG2)
        p.pack(fill="both", expand=True, padx=18, pady=18)

        U.marker_label(p, "닉네임", bg=U.BG2).pack(anchor="w", pady=(0, 5))
        self.li_name = tk.StringVar(value=config.load_session().get("username", ""))
        box = U.entry(p, self.li_name)
        box.pack(fill="x")

        U.marker_label(p, "비밀번호   숫자 4자리", bg=U.BG2).pack(anchor="w",
                                                           pady=(16, 6))
        self.li_pin = PinEntry(p, 4, on_done=self.do_login)
        self.li_pin.pack(anchor="w")

        U.PushButton(p, "로그인", self.do_login, height=44).pack(fill="x",
                                                              pady=(24, 0))
        row = tk.Frame(p, bg=U.BG2)
        row.pack(pady=(12, 0))
        tk.Label(row, text="처음이신가요?", bg=U.BG2, fg=U.FG_FAINT,
                 font=U.FONT_S).pack(side="left")
        link = tk.Label(row, text="회원가입", bg=U.BG2, fg=U.ACCENT,
                        font=U.FONT_B, cursor="hand2")
        link.pack(side="left", padx=(6, 0))
        link.bind("<Button-1>", lambda e: self.switch("signup"))
        self.win.after(80, lambda: box.entry.focus_set())

    # ---------------- 회원가입 ----------------
    def show_signup(self):
        self.clear_panel()
        self.paint_tabs()
        p = tk.Frame(self.panel, bg=U.BG2)
        p.pack(fill="both", expand=True, padx=16, pady=(13, 12))

        head = tk.Frame(p, bg=U.BG2)
        head.pack(fill="x")
        U.marker_label(head, "닉네임", bg=U.BG2).pack(side="left")
        self.name_hint = tk.Label(head, text="2~12자", bg=U.BG2, fg=U.FG_FAINT,
                                  font=U.FONT_XS)
        self.name_hint.pack(side="right")

        self.rg_name = tk.StringVar()
        self.rg_name.trace_add("write", lambda *a: self.schedule_check())
        self.name_box = U.entry(p, self.rg_name)
        self.name_box.pack(fill="x", pady=(5, 0))

        U.marker_label(p, "비밀번호   숫자 4자리", bg=U.BG2).pack(anchor="w",
                                                           pady=(12, 5))
        self.rg_pin = PinEntry(p, 4)
        self.rg_pin.pack(anchor="w")

        srow = tk.Frame(p, bg=U.BG2)
        srow.pack(fill="x", pady=(13, 7))
        U.marker_label(srow, "처음 함께할 포켓몬", bg=U.BG2,
                       color=U.FG).pack(side="left")
        tk.Label(srow, text="1~9세대 27마리", bg=U.BG2, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="right")

        self.genbar = tk.Frame(p, bg=U.BG2)
        self.genbar.pack(fill="x")
        self.cardbar = tk.Frame(p, bg=U.BG2)
        self.cardbar.pack(fill="x", pady=(9, 0))

        self.btn_signup = U.PushButton(p, "포켓몬을 골라 주세요", self.do_register,
                                       height=42)
        self.btn_signup.pack(fill="x", side="bottom", pady=(12, 0))

        if self.gens:
            self.build_genbar()
            self.show_gen(self.gen)
        else:
            self.load_starters()
        self.win.after(80, lambda: self.name_box.entry.focus_set())

    # ---------------- 닉네임 중복 확인 ----------------
    def schedule_check(self):
        if self._check_job:
            try:
                self.root.after_cancel(self._check_job)
            except Exception:
                pass
        self.name_ok = False
        self.refresh_signup_button()
        self._paint_name(None, "확인 중...")
        self._check_job = self.root.after(CHECK_DELAY, self.do_check)

    def do_check(self):
        self._check_job = None
        name = self.rg_name.get().strip()
        if not name:
            return self._paint_name(None, "2~12자")
        api = Api(self.server.get().strip())

        def done(r, err):
            if self.tab != "signup" or name != self.rg_name.get().strip():
                return
            if err:
                return self._paint_name(None, "확인할 수 없음")
            self.name_ok = bool(r.get("available"))
            self._paint_name(self.name_ok, r.get("reason", ""))
            self.refresh_signup_button()
        U.run_async(self.root, lambda: api.check_name(name), done)

    def _paint_name(self, ok, text):
        color = U.FG_FAINT if ok is None else (U.GOOD if ok else U.DANGER)
        mark = "" if ok is None else ("✓ " if ok else "✕ ")
        try:
            self.name_hint.configure(text=mark + text, fg=color)
            self.name_box.configure(
                highlightbackground=U.LINE if ok is None
                else (U.GOOD if ok else U.DANGER_LINE))
        except Exception:
            pass

    def refresh_signup_button(self):
        if not hasattr(self, "btn_signup"):
            return
        name = next((c.mon["kr"] for c in self.cards
                     if c.mon["internal"] == self.picked), None)
        if not name:
            return self.btn_signup.configure(text="포켓몬을 골라 주세요")
        self.btn_signup.configure(text=kfmt("{name}{와} 함께 시작하기", name))

    # ---------------- 스타팅 목록 ----------------
    def load_starters(self):
        self.say("스타팅 포켓몬을 불러오는 중...", U.ACCENT)
        api = Api(self.server.get().strip())

        def done(r, err):
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            self.gens = (r or {}).get("generations", [])
            self.say("")
            if self.tab == "signup":
                self.build_genbar()
                self.show_gen(1)
            self.prefetch_starters()
        U.run_async(self.root, api.starters, done)

    def prefetch_starters(self):
        """9세대 27마리 도트를 한 번에 받아 둔다.

        예전에는 세대를 넘길 때마다 그 세대 3마리를 그때 받았다. 그래서
        세대를 바꿀 때마다 카드가 비어 있다가 뒤늦게 채워졌다.
        어차피 다 둘러볼 거라 처음에 한 번에 받아두는 편이 낫다.
        """
        if getattr(self, "_prefetched", False) or not self.gens:
            return
        self._prefetched = True
        want = []
        for g in self.gens:
            for m in g.get("pokemon", []):
                if m.get("num"):
                    want.append((m["num"], False))
        if not want:
            return
        api = Api(self.server.get().strip())
        total = len(want)

        def work():
            got = 0
            for pair in want:
                if sprite_cache.ensure(api, pair[0], pair[1]):
                    got += 1
                # 몇 마리까지 받았는지 화면에 알린다 (로딩 중인 티를 낸다)
                self.root.after(0, self._prefetch_progress, got, total)
            return got

        def done(got, err):
            if self.tab == "signup":
                self.say("")
            config.log("스타팅 도트 미리 받기: %s/%s" % (got, total))
        U.run_async(self.root, work, done)

    def _prefetch_progress(self, got, total):
        try:
            if self.tab == "signup" and got < total:
                self.say("스타팅 포켓몬을 준비하는 중... %d/%d" % (got, total),
                         U.FG_FAINT)
        except Exception:                                  # noqa: BLE001
            pass

    def build_genbar(self):
        for w in self.genbar.winfo_children():
            w.destroy()
        self.genbtns = {}
        for g in self.gens:
            n = g["gen"]
            b = tk.Label(self.genbar, text="%d" % n, bg=U.BG3, fg=U.FG_DIM,
                         font=U.FONT_XS, width=2, pady=4, cursor="hand2",
                         highlightthickness=2, highlightbackground=U.BG2)
            b.pack(side="left", padx=(0, 3))
            b.bind("<Button-1>", lambda e, k=n: self.show_gen(k))
            self.genbtns[n] = b

    def show_gen(self, n):
        self.gen = n
        for k, b in self.genbtns.items():
            on = (k == n)
            b.configure(bg=U.ACCENT if on else U.BG3,
                        fg=U.ACCENT_DARK if on else U.FG_DIM,
                        font=U.FONT_B if on else U.FONT_XS,
                        highlightbackground=U.INK if on else U.BG2)
        row = next((g for g in self.gens if g["gen"] == n), None)
        if not row:
            return
        self.stop_anim()
        for w in self.cardbar.winfo_children():
            w.destroy()
        self.cards = [StarterCard(self.cardbar, m, self.pick)
                      for m in row["pokemon"]]
        for i, c in enumerate(self.cards):
            c.pack(side="left", padx=(0, 8) if i < len(self.cards) - 1 else 0)
        if row["pokemon"]:
            self.pick(row["pokemon"][0]["internal"])
        self.load_art(row["pokemon"])

    def pick(self, internal):
        self.picked = internal
        for c in self.cards:
            c.set_selected(c.mon["internal"] == internal)
        self.refresh_signup_button()

    def load_art(self, mons):
        """카드에 올릴 **실제 도트**를 받아온다."""
        api = Api(self.server.get().strip())
        want = [(m["num"], False) for m in mons]

        def work():
            return sprite_cache.ensure_many(api, want)

        def done(paths, err):
            if err or not paths or self.tab != "signup":
                return
            for c in self.cards:
                path = paths.get((c.mon["num"], False))
                if not path:
                    continue
                try:
                    anim = sprites.load_animation(path, target_height=54,
                                                  min_scale=0.2, max_scale=3.0)
                    photos = [ImageTk.PhotoImage(sprites.to_rgba(f, anim.key))
                              for f in anim.frames[sprites.RIGHT]]
                    c.set_frames(photos, anim.durations)
                except Exception:
                    pass
            self.animate()
        U.run_async(self.root, work, done)

    def animate(self):
        if self.tab != "signup" or not self.cards:
            return
        delay = 140
        for c in self.cards:
            delay = min(delay, c.step())
        self._anim_job = self.root.after(delay, self.animate)

    def stop_anim(self):
        if self._anim_job:
            try:
                self.root.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None

    # ---------------- 동작 ----------------
    def _enter(self):
        self.do_login() if self.tab == "login" else self.do_register()

    def say(self, msg, color=None):
        U.set_status(self.status, msg, color or U.LINE, fg=color or U.FG_DIM)

    def _start(self, msg):
        if self.busy:
            return False
        self.busy = True
        self.say(msg, U.ACCENT)
        return True

    def _finish(self, err):
        self.busy = False
        if err:
            self.say(getattr(err, "message", str(err)), U.DANGER)

    def do_login(self):
        name = self.li_name.get().strip()
        pin = self.li_pin.get()
        if not name:
            return self.say("닉네임을 입력해 주세요.", U.DANGER)
        if len(pin) != 4:
            return self.say("비밀번호 4자리를 입력해 주세요.", U.DANGER)
        if not self._start("로그인 중..."):
            return
        api = Api(self.server.get().strip())

        def done(r, err):
            self._finish(err)
            if err:
                self.li_pin.clear()
                self.li_pin.focus()
            else:
                self._ok(api, r)
        U.run_async(self.root, lambda: api.login(name, pin), done)

    def do_register(self):
        name = self.rg_name.get().strip()
        pin = self.rg_pin.get()
        if not name:
            return self.say("닉네임을 입력해 주세요.", U.DANGER)
        if not self.name_ok:
            return self.say("쓸 수 있는 닉네임인지 확인해 주세요.", U.DANGER)
        if len(pin) != 4:
            return self.say("비밀번호 4자리를 입력해 주세요.", U.DANGER)
        if not self.picked:
            return self.say("처음 함께할 포켓몬을 골라 주세요.", U.DANGER)
        if not self._start("계정을 만드는 중..."):
            return
        api = Api(self.server.get().strip())

        def done(r, err):
            self._finish(err)
            if not err:
                self._ok(api, r)
        U.run_async(self.root, lambda: api.register(name, pin, self.picked), done)

    def _ok(self, api, r):
        self.settings["server"] = self.server.get().strip()
        config.save_settings(self.settings)
        config.save_session({"token": r["token"], "username": r["user"]["username"],
                             "expiresAt": r.get("expiresAt")})
        self.result = {"api": api, "user": r["user"], "balls": r.get("balls")}
        self.say("환영합니다, %s 님!" % r["user"]["username"], U.GOOD)
        self.win.after(450, self.close)

    def close(self):
        self.stop_anim()
        try:
            self.win.destroy()
        except Exception:
            pass

    def cancel(self):
        self.result = None
        self.close()

    def show(self):
        self.win.grab_set()
        self.root.wait_window(self.win)
        return self.result


def ask_password(root, title, message):
    """회원탈퇴처럼 비밀번호를 한 번 더 확인해야 할 때."""
    win = tk.Toplevel(root)
    U.style_window(win, title, 360, 220)
    U.apply_theme(win)
    win.configure(highlightthickness=2, highlightbackground=U.LINE2)
    win.resizable(False, False)
    out = {}

    bar = tk.Frame(win, bg=U.BG2, height=34)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    tk.Frame(bar, bg=U.ACCENT, width=3, height=13).pack(side="left", padx=(12, 8))
    tk.Label(bar, text=title, bg=U.BG2, fg=U.FG, font=U.FONT_B).pack(side="left")
    tk.Frame(win, bg=U.LINE2, height=2).pack(fill="x")

    f = tk.Frame(win, bg=U.BG)
    f.pack(fill="both", expand=True, padx=18, pady=16)
    tk.Label(f, text=message, bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
             wraplength=300, justify="left").pack(anchor="w")

    pin = PinEntry(f, 4)
    pin.pack(anchor="w", pady=(14, 0))

    def ok():
        out["pw"] = pin.get()
        win.destroy()

    pin.on_done = ok
    row = tk.Frame(f, bg=U.BG)
    row.pack(fill="x", pady=(16, 0))
    U.PushButton(row, "확인", ok, height=36, font=U.FONT_B).pack(side="right")
    U.ghost_button(row, "취소", win.destroy, height=36).pack(side="right",
                                                           padx=(0, 8))

    win.bind("<Return>", lambda ev: ok())
    win.after(60, pin.focus)
    win.grab_set()
    root.wait_window(win)
    return out.get("pw")
