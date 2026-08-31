# -*- coding: utf-8 -*-
"""포켓몬 관리 창 — 보유 목록, 상세 능력치, 바탕화면 내보내기."""
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from . import sprite_cache, sprites
from . import ui_common as U
from .ui_common import apply_theme, gender_color, gender_mark, run_async, style_window

STAT_ROWS = [("hp", "HP"), ("atk", "공격"), ("def", "방어"),
             ("spa", "특수공격"), ("spd", "특수방어"), ("spe", "스피드")]


def _recolor(img, key, bg):
    """투명색으로 칠해둔 배경을 창 배경색으로 바꾼다."""
    src = img.tobytes()
    out = bytearray(src)
    kr, kg, kb = key
    br, bgc, bb = bg
    for i in range(0, len(src), 3):
        if src[i] == kr and src[i + 1] == kg and src[i + 2] == kb:
            out[i], out[i + 1], out[i + 2] = br, bgc, bb
    return Image.frombytes("RGB", img.size, bytes(out))


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class BoxWindow(object):
    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.mons = []
        self.sel = None
        self.photos = []
        self.anim_job = None
        self.anim = None
        self.anim_i = 0

        self.win = tk.Toplevel(root)
        style_window(self.win, "포켓 데스크톱 — 포켓몬 관리", 980, 610)
        apply_theme(self.win)
        self.win.minsize(900, 540)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        # ---- 위쪽 막대 ----
        top = ttk.Frame(self.win, padding=(16, 14, 16, 10))
        top.pack(fill="x")
        ttk.Label(top, text="포켓몬 관리", style="Title.TLabel").pack(side="left")
        self.count = ttk.Label(top, text="", style="Dim.TLabel")
        self.count.pack(side="left", padx=(12, 0), pady=(6, 0))
        ttk.Button(top, text="새로고침", style="Ghost.TButton",
                   command=self.reload).pack(side="right")
        self.balls = ttk.Label(top, text="", style="Dim.TLabel")
        self.balls.pack(side="right", padx=(0, 14), pady=(6, 0))

        body = ttk.Frame(self.win, padding=(16, 0, 16, 8))
        body.pack(fill="both", expand=True)

        # ---- 목록 ----
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        cols = ("num", "name", "lv", "type", "nature", "iv", "where")
        self.tree = ttk.Treeview(left, columns=cols, show="headings",
                                 selectmode="browse")
        for c, t, w, anchor in [("num", "도감", 56, "center"),
                                ("name", "이름", 168, "w"),
                                ("lv", "Lv", 44, "center"),
                                ("type", "타입", 120, "w"),
                                ("nature", "성격", 74, "center"),
                                ("iv", "개체값", 68, "center"),
                                ("where", "위치", 82, "center")]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=anchor, stretch=(c == "name"))
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.tag_configure("shiny", foreground=U.SHINY)
        self.tree.tag_configure("desktop", foreground=U.GOOD)

        # ---- 상세 ----
        self.right = ttk.Frame(body, width=340, style="Card.TFrame", padding=16)
        self.right.pack(side="left", fill="y", padx=(14, 0))
        self.right.pack_propagate(False)
        self._build_detail()

        # ---- 아래 버튼 ----
        bot = ttk.Frame(self.win, padding=(16, 0, 16, 14))
        bot.pack(fill="x")
        self.btn_desktop = ttk.Button(bot, text="바탕화면에 내보내기",
                                      command=self.toggle_desktop, state="disabled")
        self.btn_desktop.pack(side="left")
        self.btn_nick = ttk.Button(bot, text="별명 짓기", style="Ghost.TButton",
                                   command=self.do_nickname, state="disabled")
        self.btn_nick.pack(side="left", padx=8)
        self.btn_release = ttk.Button(bot, text="놓아주기", style="Danger.TButton",
                                      command=self.do_release, state="disabled")
        self.btn_release.pack(side="left")
        self.status = ttk.Label(bot, text="", style="Dim.TLabel")
        self.status.pack(side="right")

        self.reload()

    # ---------------- 상세 패널 ----------------
    def _build_detail(self):
        r = self.right
        self.d_sprite = tk.Label(r, bg=U.BG2, height=6)
        self.d_sprite.pack(pady=(2, 8))
        self.d_name = tk.Label(r, text="포켓몬을 고르세요", bg=U.BG2, fg=U.FG,
                               font=U.FONT_T)
        self.d_name.pack()
        self.d_sub = tk.Label(r, text="", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_XS)
        self.d_sub.pack(pady=(2, 8))
        self.d_types = tk.Frame(r, bg=U.BG2)
        self.d_types.pack(pady=(0, 12))

        self.stat_bars = {}
        grid = tk.Frame(r, bg=U.BG2)
        grid.pack(fill="x")
        for i, (k, label) in enumerate(STAT_ROWS):
            tk.Label(grid, text=label, bg=U.BG2, fg=U.FG_DIM, font=U.FONT_XS,
                     width=7, anchor="w").grid(row=i, column=0, sticky="w", pady=2)
            val = tk.Label(grid, text="-", bg=U.BG2, fg=U.FG, font=U.FONT_NUM,
                           width=5, anchor="e")
            val.grid(row=i, column=1, sticky="e")
            cv = tk.Canvas(grid, width=118, height=7, bg=U.BG3,
                           highlightthickness=0, bd=0)
            cv.grid(row=i, column=2, padx=(10, 8))
            iv = tk.Label(grid, text="", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_XS,
                          width=6, anchor="e")
            iv.grid(row=i, column=3, sticky="e")
            self.stat_bars[k] = (val, cv, iv)

        self.d_ability = tk.Label(r, text="", bg=U.BG2, fg=U.FG, font=U.FONT_S,
                                  anchor="w", justify="left", wraplength=300)
        self.d_ability.pack(fill="x", pady=(14, 2))
        tk.Label(r, text="기술", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_XS,
                 anchor="w").pack(fill="x", pady=(10, 3))
        self.d_moves = tk.Label(r, text="-", bg=U.BG2, fg=U.FG, font=U.FONT_S,
                                anchor="w", justify="left", wraplength=300)
        self.d_moves.pack(fill="x")

    # ---------------- 데이터 ----------------
    def say(self, msg, color=None):
        self.status.configure(text=msg, foreground=color or U.FG_DIM)

    def reload(self):
        self.say("불러오는 중...")

        def work():
            mons = self.app.api.pokemon()
            # 바탕화면에 나와 있는 애들 도트는 미리 받아둔다
            sprite_cache.ensure_many(
                self.app.api,
                [(m.get("num"), m.get("shiny")) for m in mons if m.get("onDesktop")])
            return mons
        run_async(self.root, work, self._loaded)

    def _loaded(self, mons, err):
        if err:
            return self.say(getattr(err, "message", str(err)), U.DANGER)
        self.mons = mons or []
        keep = self.sel
        self.tree.delete(*self.tree.get_children())
        dex = self.app.dex
        for m in self.mons:
            info = m.get("info", {})
            tags = []
            if m.get("shiny"):
                tags.append("shiny")
            elif m.get("onDesktop"):
                tags.append("desktop")
            name = info.get("name", m["species"])
            if m.get("shiny"):
                name = "★ " + name
            g = gender_mark(m.get("gender"))
            self.tree.insert("", "end", iid=str(m["id"]), tags=tags, values=(
                "%04d" % m.get("num", 0), (name + " " + g).strip(), m["level"],
                " / ".join(info.get("types", [])),
                info.get("nature", ""),
                "%.0f%%" % info.get("ivPercent", 0),
                "바탕화면" if m.get("onDesktop") else "박스"))
        n_desk = sum(1 for m in self.mons if m.get("onDesktop"))
        self.count.configure(text="보유 %d마리  ·  바탕화면 %d마리"
                                  % (len(self.mons), n_desk))
        self.balls.configure(text="몬스터볼 %d개" % self.app.balls)
        self.say("")
        if keep and self.tree.exists(str(keep)):
            self.tree.selection_set(str(keep))
        elif self.mons:
            self.tree.selection_set(str(self.mons[0]["id"]))

    def current(self):
        for m in self.mons:
            if m["id"] == self.sel:
                return m
        return None

    def on_select(self, _e=None):
        s = self.tree.selection()
        if not s:
            return
        self.sel = int(s[0])
        m = self.current()
        if m:
            self.show_detail(m)
        for b in (self.btn_desktop, self.btn_nick, self.btn_release):
            b.configure(state="normal")
        self.btn_desktop.configure(
            text="바탕화면에서 거두기" if m and m.get("onDesktop")
            else "바탕화면에 내보내기")

    # ---------------- 상세 그리기 ----------------
    def show_detail(self, m):
        info = m.get("info", {})
        dex = self.app.dex

        name = info.get("name", m["species"])
        self.d_name.configure(text=name, fg=U.SHINY if m.get("shiny") else U.FG)
        bits = ["No.%04d" % m.get("num", 0), info.get("species", ""),
                "Lv.%d" % m["level"]]
        g = gender_mark(m.get("gender"))
        if g:
            bits.append(g)
        bits.append(info.get("nature", "") + " 성격")
        if m.get("shiny"):
            bits.append("★ 색이 다른 개체")
        self.d_sub.configure(text="   ·   ".join(x for x in bits if x))

        for w in self.d_types.winfo_children():
            w.destroy()
        sp = dex.get(m["species"]) if dex else None
        if sp:
            for t in sp.get("types", []):
                tk.Label(self.d_types, text=dex.type_name(t),
                         bg=U.TYPE_COLOR.get(t, U.BG3), fg="#14141a",
                         font=U.FONT_XS, padx=10, pady=2).pack(side="left", padx=3)

        stats = info.get("stats", {})
        ivs = m.get("ivs", {})
        mx = max(list(stats.values()) or [1])
        for k, _label in STAT_ROWS:
            val, cv, ivl = self.stat_bars[k]
            v = stats.get(k, 0)
            val.configure(text=str(v))
            cv.delete("all")
            w = int(118 * v / mx) if mx else 0
            iv = ivs.get(k, 0)
            col = U.GOOD if iv == 31 else (U.ACCENT if iv >= 26 else "#63637d")
            cv.create_rectangle(0, 0, w, 7, fill=col, outline="")
            ivl.configure(text="개체 %d" % iv,
                          fg=U.GOOD if iv == 31 else U.FG_DIM)

        ab = info.get("ability", "")
        if info.get("hiddenAbility"):
            ab += "   (숨은 특성)"
        self.d_ability.configure(
            text="특성   %s\n개체값   %d / 186   (%.0f%%)"
                 % (ab, info.get("ivTotal", 0), info.get("ivPercent", 0)))
        self.d_moves.configure(
            text="\n".join("·  " + x for x in info.get("moves", [])) or "-")

        self.load_sprite(m)

    def load_sprite(self, m):
        """도트는 없으면 서버에서 받아온다. 받는 동안 화면은 안 멈춘다."""
        self.stop_anim()
        self.d_sprite.configure(image="", text="...", fg=U.FG_FAINT,
                                font=U.FONT_S)
        want = m["id"]

        def work():
            return sprite_cache.ensure(self.app.api, m.get("num"), m.get("shiny"))

        def done(path, err):
            if err or not path or self.sel != want:
                if self.sel == want:
                    self.d_sprite.configure(text="도트 없음")
                return
            try:
                anim = sprites.load_animation(path, target_height=96,
                                              min_scale=0.2, max_scale=3.0)
                key = anim.key
                bg = _rgb(U.BG2)
                self.photos = [ImageTk.PhotoImage(_recolor(f, key, bg))
                               for f in anim.frames[sprites.RIGHT]]
                self.anim = anim
                self.anim_i = 0
                self.d_sprite.configure(text="", image=self.photos[0])
                self.play_anim()
            except Exception:
                self.d_sprite.configure(text="도트 없음")
        run_async(self.root, work, done)

    def play_anim(self):
        if not self.photos:
            return
        self.anim_i = (self.anim_i + 1) % len(self.photos)
        try:
            self.d_sprite.configure(image=self.photos[self.anim_i])
        except Exception:
            return
        d = self.anim.durations[self.anim_i % len(self.anim.durations)]
        self.anim_job = self.root.after(max(50, d), self.play_anim)

    def stop_anim(self):
        if self.anim_job:
            try:
                self.root.after_cancel(self.anim_job)
            except Exception:
                pass
            self.anim_job = None
        self.photos = []

    # ---------------- 동작 ----------------
    def _after(self, msg):
        def done(_r, err):
            if err:
                self.say(getattr(err, "message", str(err)), U.DANGER)
            else:
                self.say(msg, U.GOOD)
                self.reload()
                self.app.request_sync()
        return done

    def toggle_desktop(self):
        m = self.current()
        if not m:
            return
        on = not m.get("onDesktop")
        self.say("적용하는 중...")
        run_async(self.root, lambda: self.app.api.set_desktop(m["id"], on),
                  self._after("바탕화면에 내보냈습니다." if on else "박스로 거두었습니다."))

    def do_nickname(self):
        m = self.current()
        if not m:
            return
        val = ask_text(self.win, "별명 짓기",
                       "%s 의 별명 (비우면 원래 이름)" % m["info"]["species"],
                       m.get("nickname") or "")
        if val is None:
            return
        run_async(self.root, lambda: self.app.api.set_nickname(m["id"], val),
                  self._after("별명을 바꿨습니다."))

    def do_release(self):
        m = self.current()
        if not m:
            return
        name = m["info"]["name"]
        if not confirm(self.win, "놓아주기",
                       "%s 을(를) 놓아줍니다.\n되돌릴 수 없습니다. 계속할까요?" % name):
            return
        run_async(self.root, lambda: self.app.api.release(m["id"]),
                  self._after("%s 을(를) 보내주었습니다." % name))

    def close(self):
        self.stop_anim()
        self.app.box_window = None
        self.win.destroy()

    def focus(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()


# ---------------------------------------------------------------- 작은 대화상자
def ask_text(parent, title, message, initial=""):
    win = tk.Toplevel(parent)
    style_window(win, title, 360, 190)
    apply_theme(win)
    win.resizable(False, False)
    out = {}
    f = ttk.Frame(win, padding=20)
    f.pack(fill="both", expand=True)
    ttk.Label(f, text=message, wraplength=310, justify="left").pack(anchor="w")
    var = tk.StringVar(value=initial)
    e = ttk.Entry(f, textvariable=var)
    e.pack(fill="x", pady=14)
    e.focus_set()

    def ok():
        out["v"] = var.get().strip()
        win.destroy()
    row = ttk.Frame(f)
    row.pack(fill="x")
    ttk.Button(row, text="취소", style="Ghost.TButton",
               command=win.destroy).pack(side="right")
    ttk.Button(row, text="확인", style="Accent.TButton",
               command=ok).pack(side="right", padx=(0, 8))
    win.bind("<Return>", lambda ev: ok())
    win.grab_set()
    parent.wait_window(win)
    return out.get("v")


def confirm(parent, title, message):
    win = tk.Toplevel(parent)
    style_window(win, title, 360, 185)
    apply_theme(win)
    win.resizable(False, False)
    out = {"v": False}
    f = ttk.Frame(win, padding=20)
    f.pack(fill="both", expand=True)
    ttk.Label(f, text=message, wraplength=310,
              justify="left").pack(anchor="w", pady=(0, 18))

    def ok():
        out["v"] = True
        win.destroy()
    row = ttk.Frame(f)
    row.pack(fill="x")
    ttk.Button(row, text="취소", style="Ghost.TButton",
               command=win.destroy).pack(side="right")
    ttk.Button(row, text="확인", style="Danger.TButton",
               command=ok).pack(side="right", padx=(0, 8))
    win.grab_set()
    parent.wait_window(win)
    return out["v"]


# 예전 이름 (app.py 에서 쓰던 것)
_confirm = confirm
_ask_text = ask_text
