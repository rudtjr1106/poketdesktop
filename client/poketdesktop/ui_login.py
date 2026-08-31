# -*- coding: utf-8 -*-
"""로그인 / 회원가입 창.

처음 실행하면 이 창이 먼저 뜬다. 저장된 자동 로그인이 성공하면 안 뜬다.
회원가입에서는 1~9세대 어태커 27마리 중 하나를 골라 시작한다.
"""
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from common.version import VERSION

from . import config, sprite_cache, sprites
from . import ui_common as U
from .api import Api
from .ui_common import apply_theme, run_async, style_window

GEN_LABEL = {1: "관동", 2: "성도", 3: "호연", 4: "신오", 5: "하나",
             6: "칼로스", 7: "알로라", 8: "가라르", 9: "팔데아"}


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _recolor(img, key, bg):
    src = img.tobytes()
    out = bytearray(src)
    kr, kg, kb = key
    br, bgc, bb = bg
    for i in range(0, len(src), 3):
        if src[i] == kr and src[i + 1] == kg and src[i + 2] == kb:
            out[i], out[i + 1], out[i + 2] = br, bgc, bb
    return Image.frombytes("RGB", img.size, bytes(out))


class LoginWindow(object):
    """결과는 self.result 에 담긴다. 취소하면 None."""

    def __init__(self, root, settings):
        self.root = root
        self.settings = settings
        self.result = None
        self.busy = False
        self.gens = []
        self.gen = 1
        self.starter = tk.StringVar(value="")
        self.cards = []
        self.photos = {}

        self.win = tk.Toplevel(root)
        style_window(self.win, "포켓 데스크톱", 460, 660)
        apply_theme(self.win)
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)
        self.win.resizable(False, False)

        wrap = ttk.Frame(self.win, padding=24)
        wrap.pack(fill="both", expand=True)

        ttk.Label(wrap, text="포켓 데스크톱", style="Title.TLabel").pack(anchor="w")
        ttk.Label(wrap, text="바탕화면에서 포켓몬을 만나고 키웁니다   v%s" % VERSION,
                  style="Dim.TLabel").pack(anchor="w", pady=(3, 16))

        ttk.Label(wrap, text="서버 주소", style="Faint.TLabel").pack(anchor="w")
        self.server = tk.StringVar(value=settings.get("server", ""))
        ttk.Entry(wrap, textvariable=self.server).pack(fill="x", pady=(3, 14))

        nb = ttk.Notebook(wrap)
        nb.pack(fill="both", expand=True)
        self.nb = nb
        nb.bind("<<NotebookTabChanged>>", self.on_tab)

        # ---- 로그인 ----
        f1 = ttk.Frame(nb, padding=16)
        nb.add(f1, text="로그인")
        self.li_user = self._field(f1, "아이디")
        self.li_pw = self._field(f1, "비밀번호", show="*")
        ttk.Button(f1, text="로그인", style="Accent.TButton",
                   command=self.do_login).pack(fill="x", pady=(18, 0))

        # ---- 회원가입 ----
        f2 = ttk.Frame(nb, padding=16)
        nb.add(f2, text="회원가입")
        self.rg_user = self._field(f2, "아이디   영문·숫자 3~16자")
        self.rg_pw = self._field(f2, "비밀번호   8자 이상", show="*")
        self.rg_pw2 = self._field(f2, "비밀번호 확인", show="*")

        ttk.Label(f2, text="처음 함께할 포켓몬",
                  style="Faint.TLabel").pack(anchor="w", pady=(14, 4))
        self.genbar = tk.Frame(f2, bg=U.BG)
        self.genbar.pack(fill="x")
        self.cardbar = tk.Frame(f2, bg=U.BG)
        self.cardbar.pack(fill="x", pady=(10, 0))
        self.pick_label = ttk.Label(f2, text="", style="Dim.TLabel")
        self.pick_label.pack(anchor="w", pady=(8, 0))

        ttk.Button(f2, text="가입하고 시작하기", style="Accent.TButton",
                   command=self.do_register).pack(fill="x", side="bottom")

        self.status = ttk.Label(wrap, text="", style="Dim.TLabel", wraplength=400,
                                justify="left")
        self.status.pack(anchor="w", pady=(12, 0))

        self.win.bind("<Return>", lambda e: self._enter())
        self.win.after(60, lambda: self.li_user.focus_set())

    def _field(self, parent, label, show=None):
        ttk.Label(parent, text=label, style="Faint.TLabel").pack(anchor="w",
                                                                 pady=(8, 3))
        var = tk.StringVar()
        e = ttk.Entry(parent, textvariable=var, show=show)
        e.pack(fill="x")
        e.var = var
        return e

    # ---------------- 스타팅 고르기 ----------------
    def on_tab(self, _e=None):
        if self.nb.index(self.nb.select()) == 1 and not self.gens:
            self.load_starters()

    def load_starters(self):
        self.say("스타팅 포켓몬을 불러오는 중...")
        api = Api(self.server.get().strip())

        def done(r, err):
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            self.gens = (r or {}).get("generations", [])
            self.say("")
            self.build_genbar()
            self.show_gen(1)
        run_async(self.root, api.starters, done)

    def build_genbar(self):
        for w in self.genbar.winfo_children():
            w.destroy()
        self.genbtns = {}
        for g in self.gens:
            n = g["gen"]
            b = tk.Label(self.genbar, text="%d" % n, bg=U.BG3, fg=U.FG_DIM,
                         font=U.FONT_XS, padx=9, pady=4, cursor="hand2")
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-1>", lambda e, k=n: self.show_gen(k))
            self.genbtns[n] = b

    def show_gen(self, n):
        self.gen = n
        for k, b in self.genbtns.items():
            on = (k == n)
            b.configure(bg=U.ACCENT if on else U.BG3,
                        fg=U.ACCENT_DARK if on else U.FG_DIM)
        row = next((g for g in self.gens if g["gen"] == n), None)
        if not row:
            return
        for w in self.cardbar.winfo_children():
            w.destroy()
        self.cards = []
        for p in row["pokemon"]:
            self.cards.append(self._card(p))
        if row["pokemon"]:
            self.choose(row["pokemon"][0]["internal"])
        self.fetch_sprites(row["pokemon"])

    def _card(self, p):
        f = tk.Frame(self.cardbar, bg=U.BG2, cursor="hand2", width=124, height=126)
        f.pack(side="left", padx=(0, 8))
        f.pack_propagate(False)
        img = tk.Label(f, bg=U.BG2, text="...", fg=U.FG_FAINT, font=U.FONT_XS,
                       height=4)
        img.pack(pady=(10, 2))
        name = tk.Label(f, text=p["kr"], bg=U.BG2, fg=U.FG, font=U.FONT_B)
        name.pack()
        tp = tk.Label(f, text=" / ".join(p["types"]), bg=U.BG2, fg=U.FG_DIM,
                      font=U.FONT_XS)
        tp.pack(pady=(0, 8))
        for w in (f, img, name, tp):
            w.bind("<Button-1>", lambda e, k=p["internal"]: self.choose(k))
        return {"p": p, "frame": f, "img": img, "widgets": (f, img, name, tp)}

    def fetch_sprites(self, mons):
        api = Api(self.server.get().strip())
        nums = [(m["num"], False) for m in mons]

        def work():
            return sprite_cache.ensure_many(api, nums)

        def done(paths, err):
            if err or not paths:
                return
            bg = _rgb(U.BG2)
            for c in self.cards:
                path = paths.get((c["p"]["num"], False))
                if not path:
                    continue
                try:
                    anim = sprites.load_animation(path, target_height=54,
                                                  min_scale=0.2, max_scale=3.0)
                    ph = ImageTk.PhotoImage(
                        _recolor(anim.frames[sprites.RIGHT][0], anim.key, bg))
                    self.photos[c["p"]["internal"]] = ph
                    c["img"].configure(image=ph, text="")
                except Exception:
                    pass
        run_async(self.root, work, done)

    def choose(self, internal):
        self.starter.set(internal)
        for c in self.cards:
            on = c["p"]["internal"] == internal
            for w in c["widgets"]:
                w.configure(bg=U.BG4 if on else U.BG2)
            c["frame"].configure(
                highlightthickness=2, highlightbackground=U.ACCENT if on else U.BG2)
        p = next((c["p"] for c in self.cards if c["p"]["internal"] == internal), None)
        if p:
            self.pick_label.configure(text="선택: %s   (%s)"
                                           % (p["kr"], " / ".join(p["types"])))

    # ---------------- 동작 ----------------
    def _enter(self):
        if self.nb.index(self.nb.select()) == 0:
            self.do_login()
        else:
            self.do_register()

    def say(self, msg, color=None):
        self.status.configure(text=msg, foreground=color or U.FG_DIM)
        self.win.update_idletasks()

    def _start(self, msg):
        if self.busy:
            return False
        self.busy = True
        self.say(msg)
        return True

    def _finish(self, err):
        self.busy = False
        if err:
            self.say(getattr(err, "message", str(err)), U.DANGER)

    def do_login(self):
        user = self.li_user.var.get().strip()
        pw = self.li_pw.var.get()
        if not user or not pw:
            return self.say("아이디와 비밀번호를 입력해 주세요.", U.DANGER)
        if not self._start("로그인 중..."):
            return
        api = Api(self.server.get().strip())

        def done(r, err):
            self._finish(err)
            if not err:
                self._ok(api, r)
        run_async(self.root, lambda: api.login(user, pw), done)

    def do_register(self):
        user = self.rg_user.var.get().strip()
        pw = self.rg_pw.var.get()
        pw2 = self.rg_pw2.var.get()
        if not user or not pw:
            return self.say("아이디와 비밀번호를 입력해 주세요.", U.DANGER)
        if pw != pw2:
            return self.say("비밀번호가 서로 다릅니다.", U.DANGER)
        if len(pw) < 8:
            return self.say("비밀번호는 8자 이상이어야 합니다.", U.DANGER)
        if not self.starter.get():
            return self.say("처음 함께할 포켓몬을 골라 주세요.", U.DANGER)
        if not self._start("계정을 만드는 중..."):
            return
        api = Api(self.server.get().strip())

        def done(r, err):
            self._finish(err)
            if not err:
                self._ok(api, r)
        run_async(self.root,
                  lambda: api.register(user, pw, self.starter.get()), done)

    def _ok(self, api, r):
        self.settings["server"] = self.server.get().strip()
        config.save_settings(self.settings)
        config.save_session({"token": r["token"], "username": r["user"]["username"],
                             "expiresAt": r.get("expiresAt")})
        self.result = {"api": api, "user": r["user"], "balls": r.get("balls")}
        self.say("환영합니다, %s 님!" % r["user"]["username"], U.GOOD)
        self.win.after(450, self.win.destroy)

    def cancel(self):
        self.result = None
        self.win.destroy()

    def show(self):
        self.win.grab_set()
        self.root.wait_window(self.win)
        return self.result


def ask_password(root, title, message):
    """회원탈퇴처럼 비밀번호를 한 번 더 확인해야 할 때."""
    win = tk.Toplevel(root)
    style_window(win, title, 360, 200)
    apply_theme(win)
    win.resizable(False, False)
    out = {}

    f = ttk.Frame(win, padding=20)
    f.pack(fill="both", expand=True)
    ttk.Label(f, text=message, wraplength=310, justify="left").pack(anchor="w")
    var = tk.StringVar()
    e = ttk.Entry(f, textvariable=var, show="*")
    e.pack(fill="x", pady=14)
    e.focus_set()

    def ok():
        out["pw"] = var.get()
        win.destroy()

    row = ttk.Frame(f)
    row.pack(fill="x")
    ttk.Button(row, text="취소", style="Ghost.TButton",
               command=win.destroy).pack(side="right")
    ttk.Button(row, text="확인", style="Accent.TButton",
               command=ok).pack(side="right", padx=(0, 8))
    win.bind("<Return>", lambda ev: ok())
    win.grab_set()
    root.wait_window(win)
    return out.get("pw")
