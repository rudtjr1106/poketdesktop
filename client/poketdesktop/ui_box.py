# -*- coding: utf-8 -*-
"""포켓몬 관리 창.

목록은 ttk.Treeview 가 아니라 직접 그린다. 타입을 색칩으로 보여주고
'데리고 다니는 6마리' 와 'PC 박스' 사이에 구분선을 넣으려면 그래야 한다.

오른쪽 상세에는 **실제 도트**가 제자리에서 움직인다.
"""
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from common.korean import natural

from . import sprite_cache, sprites
from . import ui_common as U
from . import ui_loading

ROW_H = 30
DETAIL_W = 340

# (제목, x, 너비, 정렬)
COLS = [("도감", 12, 50, "w"), ("이름", 66, 168, "w"), ("Lv", 240, 34, "center"),
        ("타입", 282, 118, "w"), ("성격", 404, 56, "center"),
        ("개체값", 464, 58, "center"), ("위치", 528, 74, "center")]

STAT_ROWS = [("hp", "HP"), ("atk", "공격"), ("def", "방어"),
             ("spa", "특수공격"), ("spd", "특수방어"), ("spe", "스피드")]


class Row(object):
    """목록 한 줄."""

    def __init__(self, parent, mon, dex, on_pick, dnd=None):
        self.mon = mon
        self.on_pick = on_pick
        # 끌어서 옮기기. 창이 넘겨준 세 가지를 그대로 부른다.
        # 누르자마자 고르지 않고 **놓을 때** 고른다 - 그래야 끌기 시작한
        # 것인지 그냥 누른 것인지 구분할 수 있다.
        self.dnd = dnd or {}
        self.selected = False
        info = mon.get("info", {})
        self.party = bool(mon.get("onDesktop"))
        base = U.BG if self.party else "#10131c"
        self.base = base

        self.f = tk.Frame(parent, bg=base, height=ROW_H, cursor="hand2")
        self.f.pack_propagate(False)
        self.mark = tk.Frame(self.f, bg=base, width=3)
        self.mark.place(x=0, y=0, relheight=1.0)

        dim = U.FG_DIM if self.party else U.FG_FAINT
        name = info.get("name", mon["species"])
        shiny = mon.get("shiny")
        if shiny:
            name = "★ " + name
        g = U.gender_mark(mon.get("gender"))

        self.cells = []
        self._cell("%04d" % mon.get("num", 0), COLS[0], U.FG_FAINT, U.FONT_XS)
        self.name_cell = self._cell(name, COLS[1],
                                    U.SHINY if shiny else (U.FG if self.party else dim),
                                    U.FONT_S)
        if g:
            # 글자 수로 어림하면 한글에서 어긋난다. 글꼴에 실제 폭을 물어본다.
            try:
                import tkinter.font as tkfont
                wpx = tkfont.Font(font=U.FONT_S).measure(name)
            except Exception:
                wpx = len(name) * 11
            gx = min(COLS[1][1] + wpx + 6, COLS[2][1] - 14)
            self.gender = tk.Label(self.f, text=g, bg=base,
                                   fg=U.gender_color(mon.get("gender")),
                                   font=U.FONT_S)
            self.gender.place(x=gx, rely=0.5, anchor="w")
            self.cells.append(self.gender)
        else:
            self.gender = None
        self._cell(str(mon.get("level", "")), COLS[2],
                   U.FG if self.party else dim, U.FONT_B)

        self.types = tk.Frame(self.f, bg=base)
        self.types.place(x=COLS[3][1], rely=0.5, anchor="w")
        sp = dex.get(mon["species"]) if dex else None
        for i, t in enumerate((sp or {}).get("types", [])):
            U.chip(self.types, dex.type_name(t), U.TYPE_COLOR.get(t, U.BG3),
                   padx=6).pack(side="left", padx=(0, 3))
        self.cells.append(self.types)

        self._cell(info.get("nature", ""), COLS[4], dim, U.FONT_XS)
        iv = info.get("ivPercent", 0)
        self._cell("%.0f%%" % iv, COLS[5],
                   U.GOOD if iv >= 75 else (U.FG if self.party else dim), U.FONT_XS)
        self._cell("따라다님" if self.party else "박스", COLS[6],
                   U.GOOD if self.party else U.FG_FAINT, U.FONT_XS)

        pid = self.mon["id"]
        press = self.dnd.get("press")
        move = self.dnd.get("move")
        release = self.dnd.get("release")
        for w in [self.f] + self.cells:
            if press:
                w.bind("<ButtonPress-1>", lambda e, i=pid: press(i, e))
                w.bind("<B1-Motion>", lambda e: move(e))
                w.bind("<ButtonRelease-1>", lambda e: release(e))
            else:
                w.bind("<Button-1>", lambda e, i=pid: self.on_pick(i))
            w.bind("<Enter>", self._hover_in)
            w.bind("<Leave>", self._hover_out)

    def _cell(self, text, col, fg, font):
        title, x, w, anchor = col
        lb = tk.Label(self.f, text=text, bg=self.base, fg=fg, font=font,
                      anchor=anchor if anchor != "center" else "center")
        lb.place(x=x if anchor == "w" else x, y=0, width=w, relheight=1.0)
        self.cells.append(lb)
        return lb

    def pack(self, **kw):
        self.f.pack(fill="x", **kw)
        return self

    def _paint(self, bg, mark):
        self.f.configure(bg=bg)
        self.mark.configure(bg=mark)
        for w in self.cells:
            try:
                w.configure(bg=bg)
            except Exception:
                pass
        for c in self.types.winfo_children():
            pass

    def _hover_in(self, _e):
        if not self.selected:
            self._paint(U.BG2, U.LINE)

    def _hover_out(self, _e):
        if not self.selected:
            self._paint(self.base, self.base)

    def set_selected(self, on):
        self.selected = on
        if on:
            self._paint("#2b2417", U.ACCENT)
            self.name_cell.configure(fg=U.ACCENT_TEXT, font=U.FONT_B)
        else:
            self._paint(self.base, self.base)
            self.name_cell.configure(
                fg=U.SHINY if self.mon.get("shiny")
                else (U.FG if self.party else U.FG_DIM),
                font=U.FONT_S)


class BoxWindow(object):
    def __init__(self, root, app, parent=None):
        self.root = root
        self.app = app
        self.mons = []
        self.rows = {}
        self.sel = None
        # 끌어서 옮기기 상태. Row 가 이 세 가지를 부른다.
        self._drag = None
        self._line = None
        self._dnd = {"press": self._drag_press,
                     "move": self._drag_move,
                     "release": self._drag_release}
        self.photos = []
        self.anim = None
        self.anim_i = 0
        self.anim_job = None

        # parent 가 있으면 탭 안의 한 칸으로, 없으면 지금까지처럼 창으로.
        self.win = U.panel(parent, root, "포스크탑 — 포켓몬 관리",
                           990, 668, 950, 620, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            # 탭으로 들어갈 때는 허브가 이미 걸어 두었다.
            U.install_wheel(self.win)

        self._header()
        self._bottom()

        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True)
        self._list(body)
        self._detail(body)

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

        tk.Label(inner, text="포켓몬 관리", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, 15)).pack(side="left", padx=(12, 12))
        self.count = tk.Label(inner, text="", bg=U.BG2, fg=U.FG_FAINT,
                              font=U.FONT_S)
        self.count.pack(side="left")

        U.ghost_button(inner, "새로고침", self.reload,
                       height=32).pack(side="right", pady=15)
        ball = tk.Frame(inner, bg=U.INK, highlightthickness=2,
                        highlightbackground=U.LINE)
        ball.pack(side="right", padx=(0, 10), pady=17)
        bcv = tk.Canvas(ball, width=14, height=14, bg=U.INK,
                        highlightthickness=0, bd=0)
        bcv.pack(side="left", padx=(8, 5), pady=4)
        bcv.create_oval(1, 1, 13, 13, fill="#f4f6fb", outline=U.INK, width=2)
        bcv.create_arc(1, 1, 13, 13, start=0, extent=180, fill=U.RED,
                       outline=U.INK, width=2)
        self.balls = tk.Label(ball, text="0", bg=U.INK, fg=U.ACCENT,
                              font=U.FONT_B, padx=(0))
        self.balls.pack(side="left", padx=(0, 10))
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x")

    # ---------------- 목록 ----------------
    def _list(self, parent):
        wrap = tk.Frame(parent, bg=U.BG)
        wrap.pack(side="left", fill="both", expand=True)

        head = tk.Frame(wrap, bg=U.INK, height=26)
        head.pack(fill="x")
        head.pack_propagate(False)
        for title, x, w, anchor in COLS:
            tk.Label(head, text=title, bg=U.INK, fg=U.FG_FAINT, font=U.FONT_XS,
                     anchor=anchor if anchor != "center" else "center"
                     ).place(x=x, y=0, width=w, relheight=1.0)
        tk.Frame(wrap, bg=U.LINE, height=2).pack(fill="x")

        holder = tk.Frame(wrap, bg=U.BG)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg=U.BG, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=U.BG)
        self._win = self.canvas.create_window((0, 0), window=self.inner,
                                              anchor="nw")
        self.scroller = sb
        self.inner.bind("<Configure>", lambda _e: self.fit_scroll())
        self.canvas.bind("<Configure>", lambda e: (
            self.canvas.itemconfigure(self._win, width=e.width),
            self.fit_scroll()))
        U.scrollable(self.canvas, 60)

    def fit_scroll(self):
        """스크롤 영역을 내용에 맞춘다.

        내용이 화면보다 짧으면 **스크롤할 게 없어야 한다.** 예전에는
        bbox 를 그대로 넣기만 해서, 목록이 줄어들어도 스크롤 위치가
        남아 있었다. 그러면 두 마리밖에 없는데 빈 화면이 보이고 스크롤바가
        움직인다.
        """
        try:
            self.canvas.update_idletasks()
            h = self.inner.winfo_reqheight()
            view = self.canvas.winfo_height()
            w = self.canvas.winfo_width()
            if h <= view:
                # 내용이 다 들어간다. 스크롤 영역을 화면 크기로 두면
                # 스크롤바가 꽉 차서 움직이지 않는다.
                self.canvas.configure(scrollregion=(0, 0, w, view))
                self.canvas.yview_moveto(0)
            else:
                self.canvas.configure(scrollregion=(0, 0, w, h))
        except Exception:                                   # noqa: BLE001
            pass

    def _detail(self, parent):
        d = tk.Frame(parent, bg=U.BG2, width=DETAIL_W, highlightthickness=0)
        d.pack(side="right", fill="y")
        d.pack_propagate(False)
        tk.Frame(d, bg=U.LINE2, width=2).place(x=0, y=0, relheight=1.0)

        p = tk.Frame(d, bg=U.BG2)
        p.pack(fill="both", expand=True, padx=(16, 14), pady=12)

        # 도트 액자
        art = tk.Frame(p, bg="#101623", highlightthickness=2,
                       highlightbackground=U.LINE, height=112)
        art.pack(fill="x")
        art.pack_propagate(False)
        self.d_num = tk.Label(art, text="", bg="#101623", fg="#4e566f",
                              font=U.FONT_XS)
        self.d_num.place(x=8, y=6)
        self.d_art = tk.Label(art, bg="#101623", text="포켓몬을 고르세요",
                              fg=U.FG_FAINT, font=U.FONT_S)
        self.d_art.place(relx=0.5, rely=0.55, anchor="center")

        row = tk.Frame(p, bg=U.BG2)
        row.pack(fill="x", pady=(12, 0))
        self.d_name = tk.Label(row, text="", bg=U.BG2, fg=U.ACCENT_TEXT,
                               font=(U.FAMILY_BLACK, 16))
        self.d_name.pack(side="left")
        self.d_gender = tk.Label(row, text="", bg=U.BG2, fg=U.INFO, font=U.FONT_H)
        self.d_gender.pack(side="left", padx=(6, 0))
        self.d_lv = tk.Label(row, text="", bg=U.BG3, fg=U.FG, font=U.FONT_B,
                             padx=9, pady=2, highlightthickness=2,
                             highlightbackground=U.LINE2)
        self.d_lv.pack(side="right")

        self.d_sub = tk.Label(p, text="", bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS,
                              anchor="w", justify="left")
        self.d_sub.pack(fill="x", pady=(3, 0))
        self.d_types = tk.Frame(p, bg=U.BG2)
        self.d_types.pack(anchor="w", pady=(8, 0))

        # 경험치. 레벨 숫자만 있으면 방금 올랐는지 다음 레벨이 코앞인지
        # 알 수가 없다. 바로 한눈에, 숫자로 정확히, %로 그 둘을 잇는다.
        exp = tk.Frame(p, bg=U.BG2)
        exp.pack(fill="x", pady=(10, 0))
        er = tk.Frame(exp, bg=U.BG2)
        er.pack(fill="x")
        tk.Label(er, text="경험치", bg=U.BG2, fg=U.FG_DIM,
                 font=U.FONT_XS).pack(side="left")
        self.d_exp_num = tk.Label(er, text="", bg=U.BG2, fg=U.FG_FAINT,
                                  font=U.FONT_XS)
        self.d_exp_num.pack(side="right")
        self._exp_ratio = 0.0
        self.d_exp_bar = tk.Canvas(exp, height=8, bg="#232b3d",
                                   highlightthickness=0, bd=0)
        self.d_exp_bar.pack(fill="x", pady=(3, 0))
        # 너비가 fill="x" 로 정해지므로 처음 그릴 때는 아직 1px 이다.
        # 자리가 잡힐 때 다시 그린다.
        self.d_exp_bar.bind("<Configure>", lambda _e: self._draw_exp_bar())

        # 친밀도 (친밀도로 진화하는 종에만 뜬다)
        self.d_friend = tk.Frame(p, bg=U.BG2)

        # 능력치
        stats = tk.Frame(p, bg="#101623", highlightthickness=2,
                         highlightbackground=U.LINE)
        stats.pack(fill="x", pady=(11, 0))
        sh = tk.Frame(stats, bg="#101623")
        sh.pack(fill="x", padx=11, pady=(9, 6))
        U.marker_label(sh, "능력치", bg="#101623").pack(side="left")
        self.d_ivsum = tk.Label(sh, text="", bg="#101623", fg=U.GOOD,
                                font=U.FONT_XS)
        self.d_ivsum.pack(side="right")

        grid = tk.Frame(stats, bg="#101623")
        grid.pack(fill="x", padx=11, pady=(0, 10))
        self.bars = {}
        for i, (k, label) in enumerate(STAT_ROWS):
            tk.Label(grid, text=label, bg="#101623", fg=U.FG_DIM, font=U.FONT_XS,
                     anchor="w", width=7).grid(row=i, column=0, sticky="w", pady=1)
            val = tk.Label(grid, text="-", bg="#101623", fg=U.FG, font=U.FONT_NUM,
                           anchor="e", width=4)
            val.grid(row=i, column=1, sticky="e")
            cv = tk.Canvas(grid, width=116, height=7, bg="#232b3d",
                           highlightthickness=0, bd=0)
            cv.grid(row=i, column=2, padx=(9, 8))
            iv = tk.Label(grid, text="", bg="#101623", fg=U.FG_DIM, font=U.FONT_XS,
                          anchor="e", width=6)
            iv.grid(row=i, column=3, sticky="e")
            self.bars[k] = (val, cv, iv)

        U.marker_label(p, "기술", bg=U.BG2).pack(anchor="w", pady=(11, 5))
        self.d_moves = tk.Frame(p, bg=U.BG2)
        self.d_moves.pack(fill="x")

    # ---------------- 바닥 ----------------
    def _bottom(self):
        tk.Frame(self.win, bg=U.LINE2, height=2).pack(fill="x", side="bottom")
        bar = tk.Frame(self.win, bg=U.INK, height=58)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        inner = tk.Frame(bar, bg=U.INK)
        inner.pack(fill="both", expand=True, padx=16)

        self.btn_party = U.PushButton(inner, "데리고 다니기", self.toggle_party,
                                      height=34)
        self.btn_party.pack(side="left", pady=11)
        self.btn_nick = U.ghost_button(inner, "별명 짓기", self.do_nickname,
                                       height=34)
        self.btn_nick.pack(side="left", padx=8, pady=11)
        self.btn_release = U.PushButton(inner, "놓아주기", self.do_release,
                                        fill=U.DANGER_BG, fg=U.DANGER,
                                        shadow="#1a1013", hover="#3a2028",
                                        height=34, border=U.DANGER_LINE,
                                        font=U.FONT_S)
        self.btn_release.pack(side="left", pady=11)
        self.status = tk.Label(inner, text="", bg=U.INK, fg=U.FG_FAINT,
                               font=U.FONT_S)
        self.status.pack(side="right")
        self.set_buttons(False)

    def set_buttons(self, on):
        for b in (self.btn_party, self.btn_nick, self.btn_release):
            b.configure(state="normal" if on else "disabled")

    # ---------------- 데이터 ----------------
    def say(self, msg, color=None):
        self.status.configure(text=natural(msg or ""), fg=color or U.FG_FAINT)

    def reload(self):
        self.say("불러오는 중...")
        # 서버가 자고 있으면 깨는 데 1분까지 걸린다. 빈 창을 보여주면
        # 고장으로 오해하고 다시 누르거나 닫아 버린다.
        self._wait = ui_loading.Overlay(self.win, "포켓몬을 불러오는 중")

        def work():
            mons = self.app.api.pokemon()
            sprite_cache.ensure_many(
                self.app.api,
                [(m.get("num"), m.get("shiny")) for m in mons if m.get("onDesktop")])
            return mons
        U.run_async(self.root, work, self._loaded)

    def _loaded(self, mons, err):
        w = getattr(self, "_wait", None)
        if w:
            w.close()
            self._wait = None
        if err:
            return self.say(getattr(err, "message", str(err)), U.DANGER)
        self.mons = mons or []
        keep = self.sel
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows = {}

        party = [m for m in self.mons if m.get("onDesktop")]
        box = [m for m in self.mons if not m.get("onDesktop")]
        for m in party:
            self.rows[m["id"]] = Row(self.inner, m, self.app.dex,
                                     self.select, self._dnd).pack()
            tk.Frame(self.inner, bg="#1a1f2e", height=1).pack(fill="x")
        if box:
            sep = tk.Frame(self.inner, bg=U.INK, height=28)
            sep.pack(fill="x")
            sep.pack_propagate(False)
            U.marker_label(sep, "PC 박스 · %d마리" % len(box), bg=U.INK,
                           mark=U.FG_FAINT).pack(side="left", padx=12, pady=7)
            tk.Frame(self.inner, bg=U.LINE, height=2).pack(fill="x")
            for m in box:
                self.rows[m["id"]] = Row(self.inner, m, self.app.dex,
                                         self.select, self._dnd).pack()
                tk.Frame(self.inner, bg="#161a24", height=1).pack(fill="x")

        # 행이 줄었을 수 있다. 스크롤 위치가 남아 빈 화면이 보이지 않게
        # 여기서 다시 맞춘다.
        self.fit_scroll()
        self.count.configure(text="보유 %d마리  ·  데리고 다니는 중 %d마리"
                                  % (len(self.mons), len(party)))
        self.balls.configure(text=str(self.app.balls))
        self.say("")
        if keep and keep in self.rows:
            self.select(keep)
        elif self.mons:
            self.select(self.mons[0]["id"])

    # ---------------- 끌어서 옮기기 ----------------
    # 누른 채로 이만큼 움직여야 '끄는 것' 으로 본다. 이게 없으면 클릭할 때
    # 손이 조금만 떨려도 순서가 바뀐다.
    DRAG_SLOP = 6

    def _drag_press(self, pid, e):
        self._drag = {"pid": pid, "y": e.y_root, "moved": False}

    def _drag_move(self, e):
        d = getattr(self, "_drag", None)
        if not d:
            return
        if not d["moved"]:
            if abs(e.y_root - d["y"]) < self.DRAG_SLOP:
                return
            d["moved"] = True
            try:
                self.win.configure(cursor="hand2")
            except Exception:                               # noqa: BLE001
                pass
        self._show_line(self._row_at(e))

    def _drag_release(self, e):
        d = getattr(self, "_drag", None)
        self._drag = None
        self._hide_line()
        try:
            self.win.configure(cursor="")
        except Exception:                                   # noqa: BLE001
            pass
        if not d:
            return
        if not d["moved"]:
            # 그냥 누른 것이다. 예전처럼 고르기만 한다.
            return self.select(d["pid"])
        dst = self._row_at(e)
        if dst is None or dst == d["pid"]:
            return
        self._apply_drop(d["pid"], dst)

    def _row_at(self, e):
        """지금 손가락이 올라가 있는 줄의 id. 없으면 None."""
        try:
            w = self.win.winfo_containing(e.x_root, e.y_root)
        except Exception:                                   # noqa: BLE001
            return None
        while w is not None:
            for pid, row in self.rows.items():
                if w is row.f or w in row.cells:
                    return pid
            w = getattr(w, "master", None)
        return None

    def _show_line(self, pid):
        """바꿀 상대를 짚어 준다.

        예전에는 줄 아래에 선을 그었는데, 그건 "여기 끼워 넣는다" 는
        뜻이다. 지금은 **맞바꾸기**라 그 줄 전체를 테두리로 감싼다 -
        누구와 바꾸는지가 보여야 한다.
        """
        self._hide_line()
        row = self.rows.get(pid)
        if not row or (self._drag or {}).get("pid") == pid:
            return                         # 자기 자신에게는 표시하지 않는다
        try:
            f = tk.Frame(row.f, bg=U.ACCENT)
            f.place(x=0, y=0, relwidth=1.0, relheight=1.0)
            f.lower()                      # 글자를 가리지 않게 뒤로
            inner = tk.Frame(f, bg=row.base)
            inner.place(x=2, y=2, relwidth=1.0, relheight=1.0,
                        width=-4, height=-4)
            self._line = f
        except Exception:                                   # noqa: BLE001
            self._line = None

    def _hide_line(self):
        ln = getattr(self, "_line", None)
        if ln is not None:
            try:
                ln.destroy()
            except Exception:                               # noqa: BLE001
                pass
        self._line = None

    def _apply_drop(self, src, dst):
        """src 와 dst 가 **자리를 맞바꾼다.**

        끼워 넣기가 아니라 맞바꾸기다. 두 마리를 집어서 서로 바꿔 든다고
        생각하면 된다.

          파티 안에서    -> 둘의 순서가 서로 바뀐다
          박스 것 -> 파티 -> 박스 것이 그 자리로, 파티에 있던 것이 박스로
          파티 것 -> 박스 -> 파티 것이 박스로, 박스에 있던 것이 그 자리로
          박스 안에서    -> 아무 일도 없다 (박스에는 순서가 없다)
        """
        a = next((m for m in self.mons if m["id"] == src), None)
        b = next((m for m in self.mons if m["id"] == dst), None)
        if not a or not b or src == dst:
            return
        a_party = bool(a.get("onDesktop"))
        b_party = bool(b.get("onDesktop"))
        party = [m["id"] for m in self.mons if m.get("onDesktop")]

        if a_party and b_party:
            # 둘 다 파티. 자리를 맞바꾼다.
            ia, ib = party.index(src), party.index(dst)
            party[ia], party[ib] = party[ib], party[ia]
            plan = [("order", party)]
            msg = "자리를 바꿨습니다."
        elif a_party != b_party:
            # 하나는 파티, 하나는 박스. 파티에 있던 것이 내려가고 그 자리로
            # 박스에 있던 것이 올라온다.
            # **내리고 나서 올려야** 한다 - 파티가 꽉 차 있으면 먼저
            # 올리려다 "최대 6마리" 로 막힌다.
            up, down = (src, dst) if b_party else (dst, src)
            at = party.index(down)
            order = list(party)
            order[at] = up                 # 내려간 자리에 올라온 것을 넣는다
            plan = [("down", down), ("up", up), ("order", order)]
            msg = "자리를 바꿨습니다."
        else:
            return                         # 박스끼리는 순서가 없다

        self.say("옮기는 중...")

        def work():
            api = self.app.api
            for kind, arg in plan:
                if kind == "down":
                    api.set_desktop(arg, False)
                elif kind == "up":
                    api.set_desktop(arg, True)
                elif kind == "order":
                    api.set_order(arg)

        U.run_async(self.root, work, self._after(msg))

    def current(self):
        return next((m for m in self.mons if m["id"] == self.sel), None)

    def select(self, pid):
        self.sel = pid
        for i, r in self.rows.items():
            r.set_selected(i == pid)
        m = self.current()
        if m:
            self.show_detail(m)
            self.set_buttons(True)
            self.btn_party.configure(
                text="박스로 보내기" if m.get("onDesktop") else "데리고 다니기")

    # ---------------- 상세 그리기 ----------------
    def _draw_exp_bar(self):
        cv = getattr(self, "d_exp_bar", None)
        if cv is None:
            return
        try:
            cv.delete("all")
            w = cv.winfo_width()
            if w <= 1:
                return              # 아직 자리가 안 잡혔다. Configure 때 다시.
            fill = int(w * self._exp_ratio)
            if fill > 0:
                cv.create_rectangle(0, 0, fill, 8, fill=U.ACCENT, outline="")
        except Exception:                                   # noqa: BLE001
            pass

    def _exp(self, info):
        """다음 레벨까지 얼마나 남았는지."""
        got, need = info.get("expInLevel"), info.get("expToNext")
        if got is None or need is None:
            # 옛 서버는 이 값을 안 보낸다. 0/0 으로 그리면 "다 찼다" 처럼
            # 보이므로 아예 비운다 - 틀린 것을 보여주느니 낫다.
            self._exp_ratio = 0.0
            self.d_exp_num.configure(text="")
        elif not need:
            # 최대 레벨. 0/0 으로 두면 "0%" 가 되어 다 잃은 것처럼 보인다.
            self._exp_ratio = 1.0
            self.d_exp_num.configure(text="최대 레벨")
        else:
            self._exp_ratio = max(0.0, min(1.0, got / float(need)))
            self.d_exp_num.configure(
                text="%s / %s  ·  다음까지 %s  (%.0f%%)"
                     % (format(got, ","), format(need, ","),
                        format(max(0, need - got), ","), 100.0 * got / need))
        self._draw_exp_bar()

    def _friendship(self, m):
        """친밀도로 진화하는 종이면 얼마나 남았는지 보여준다.

        숫자만 있으면 그게 뭘 향해 가는지 알 수가 없다. 하트로 대강을
        보이고, 남은 시간을 함께 적는다 - 바탕화면에 데리고 다니는
        시간으로 오르기 때문에 '얼마나 더 켜 두면 되는지' 가 곧 답이다.
        """
        box = getattr(self, "d_friend", None)
        if box is None:
            return
        for w in box.winfo_children():
            w.destroy()
        f = m.get("friendship")
        if not f:
            box.pack_forget()
            return
        box.pack(fill="x", pady=(8, 0))
        now, need = f["now"], f["need"]
        hearts = int(round(5.0 * min(1.0, now / float(need or 1))))
        line = tk.Frame(box, bg=U.BG2)
        line.pack(fill="x")
        tk.Label(line, text="친밀도", bg=U.BG2, fg=U.FG_DIM,
                 font=U.FONT_XS).pack(side="left")
        tk.Label(line, text="  " + "♥" * hearts + "♡" * (5 - hearts),
                 bg=U.BG2, fg=U.PINK, font=U.FONT_S).pack(side="left")
        tk.Label(line, text="  %d / %d" % (now, need), bg=U.BG2,
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left")
        if now >= need:
            msg = "곧 진화합니다"
        elif f["hours"] >= 1:
            msg = "%.0f시간쯤 더 데리고 다니면 진화합니다" % f["hours"]
        else:
            msg = "조금만 더 데리고 다니면 진화합니다"
        if f.get("luxury"):
            msg += "  (럭셔리볼 2배)"
        tk.Label(box, text=msg, bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS,
                 anchor="w").pack(fill="x", pady=(2, 0))

    def show_detail(self, m):
        info = m.get("info", {})
        dex = self.app.dex
        self.d_num.configure(text="No.%04d" % m.get("num", 0))
        self.d_name.configure(text=info.get("name", m["species"]),
                              fg=U.SHINY if m.get("shiny") else U.ACCENT_TEXT)
        g = U.gender_mark(m.get("gender"))
        self.d_gender.configure(text=g, fg=U.gender_color(m.get("gender")))
        self.d_lv.configure(text="Lv.%d" % m["level"])

        sp = dex.get(m["species"]) if dex else None
        bits = [(sp or {}).get("kind", ""), info.get("nature", "") + " 성격",
                "특성 " + (info.get("ability") or "")]
        if m.get("shiny"):
            bits.append("★ 색이 다른 개체")
        self.d_sub.configure(text="  ·  ".join(x for x in bits if x.strip()))

        for w in self.d_types.winfo_children():
            w.destroy()
        for t in (sp or {}).get("types", []):
            U.chip(self.d_types, dex.type_name(t), U.TYPE_COLOR.get(t, U.BG3),
                   font=U.FONT_S, padx=10, pady=2).pack(side="left", padx=(0, 4))

        self._exp(info)

        stats = info.get("stats", {})
        ivs = m.get("ivs", {})
        mx = max(list(stats.values()) or [1])
        for k, _l in STAT_ROWS:
            val, cv, ivl = self.bars[k]
            v = stats.get(k, 0)
            iv = ivs.get(k, 0)
            val.configure(text=str(v))
            cv.delete("all")
            col = U.GOOD if iv == 31 else (U.ACCENT if iv >= 26 else "#63637d")
            cv.create_rectangle(0, 0, int(116 * v / mx) if mx else 0, 7,
                                fill=col, outline="")
            ivl.configure(text="개체 %d" % iv,
                          fg=U.GOOD if iv == 31 else U.FG_DIM)
        # 종족값 합계를 같이 보여준다. 이게 없으면 "600족" 인지 아닌지
        # 화면에서 알 수가 없다 - 개체값(0~31 씩 굴리는 것)과 종족값(종마다
        # 정해진 것)은 다른 값인데, 능력치가 낮으면 둘 다 뭉뚱그려
        # "개체값이 낮다" 로 보인다.
        bst = sum((sp or {}).get("base", {}).get(k, 0)
                  for k in ("hp", "atk", "def", "spa", "spd", "spe"))
        self.d_ivsum.configure(
            text="종족값 %d  ·  개체값 %d / 186  (%.0f%%)"
                 % (bst, info.get("ivTotal", 0), info.get("ivPercent", 0)))
        self._friendship(m)

        for w in self.d_moves.winfo_children():
            w.destroy()
        moves = info.get("moves", [])
        for i, mv in enumerate(moves[:4]):
            md = None
            if dex:
                md = next((x for x in (dex.moves or {}).values()
                           if x.get("kr") == mv), None)
            col = U.TYPE_COLOR.get((md or {}).get("type"), U.BG3)
            cell = tk.Frame(self.d_moves, bg=col)
            cell.grid(row=i // 2, column=i % 2, sticky="nsew", padx=2, pady=2)
            tk.Label(cell, text=mv, bg=col, fg="#14141a",
                     font=U.FONT_B).pack(pady=(4, 0))
            sub = "%s · %s" % (dex.type_name((md or {}).get("type")) if dex else "",
                               (md or {}).get("power") or "변화")
            tk.Label(cell, text=sub, bg=col, fg="#2a2a35",
                     font=U.FONT_XS).pack(pady=(0, 4))
        for c in (0, 1):
            self.d_moves.grid_columnconfigure(c, weight=1)

        self.load_art(m)

    def load_art(self, m):
        self.stop_anim()
        self.d_art.configure(image="", text="...", fg=U.FG_FAINT)
        want = m["id"]

        def work():
            return sprite_cache.ensure(self.app.api, m.get("num"), m.get("shiny"))

        def done(path, err):
            if err or not path or self.sel != want:
                if self.sel == want:
                    self.d_art.configure(text="도트 없음")
                return
            try:
                anim = sprites.load_animation(path, target_height=92,
                                              min_scale=0.2, max_scale=3.0)
                self.photos = [ImageTk.PhotoImage(sprites.to_rgba(f, anim.key))
                               for f in anim.frames[sprites.RIGHT]]
                self.anim = anim
                self.anim_i = 0
                self.d_art.configure(text="", image=self.photos[0])
                self.play_anim()
            except Exception:
                self.d_art.configure(text="도트 없음")
        U.run_async(self.root, work, done)

    def play_anim(self):
        if not self.photos:
            return
        self.anim_i = (self.anim_i + 1) % len(self.photos)
        try:
            self.d_art.configure(image=self.photos[self.anim_i])
        except Exception:
            return
        d = self.anim.durations[self.anim_i % len(self.anim.durations)]
        self.anim_job = self.root.after(max(60, d), self.play_anim)

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

    def toggle_party(self):
        m = self.current()
        if not m:
            return
        on = not m.get("onDesktop")
        self.say("적용하는 중...")
        U.run_async(self.root, lambda: self.app.api.set_desktop(m["id"], on),
                    self._after("데리고 다닙니다." if on else "박스로 보냈습니다."))

    def do_nickname(self):
        m = self.current()
        if not m:
            return
        val = ask_text(self.win, "별명 짓기",
                       "%s 의 별명을 지어주세요." % m["info"]["species"],
                       "비우면 원래 이름으로 돌아갑니다",
                       m.get("nickname") or "")
        if val is None:
            return
        U.run_async(self.root, lambda: self.app.api.set_nickname(m["id"], val),
                    self._after("별명을 바꿨습니다."))

    def do_release(self):
        m = self.current()
        if not m:
            return
        if not confirm_release(self.win, self.app, m):
            return
        name = m["info"]["name"]
        U.run_async(self.root, lambda: self.app.api.release(m["id"]),
                    self._after("%s 을(를) 보내주었습니다." % name))

    def close(self):
        # 휠은 이제 창 하나가 받아서 나눠 준다(U.install_wheel). 예전에는
        # 여기서 unbind_all 을 불렀는데, 그건 **다른 창의 휠까지 지웠다.**
        self.stop_anim()
        self.app.box_window = None
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass

    def focus(self):
        if U.is_embedded(self.win):
            return          # 탭이면 허브가 앞으로 꺼내 준다
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()


# ---------------------------------------------------------------- 대화상자
def _shell(parent, title, w, h, danger=False):
    win = tk.Toplevel(parent)
    U.style_window(win, title, w, h)
    U.apply_theme(win)
    win.configure(highlightthickness=2,
                  highlightbackground=U.DANGER_LINE if danger else U.LINE2)
    win.resizable(False, False)
    bar = tk.Frame(win, bg=U.DANGER_BG if danger else U.BG2, height=34)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    tk.Frame(bar, bg=U.DANGER if danger else U.ACCENT, width=3,
             height=13).pack(side="left", padx=(12, 8))
    tk.Label(bar, text=title, bg=U.DANGER_BG if danger else U.BG2,
             fg="#ffb3b3" if danger else U.FG, font=U.FONT_B).pack(side="left")
    tk.Frame(win, bg=U.DANGER_LINE if danger else U.LINE2, height=2).pack(fill="x")
    body = tk.Frame(win, bg=U.BG)
    body.pack(fill="both", expand=True, padx=18, pady=16)
    return win, body


def ask_text(parent, title, message, hint="", initial=""):
    win, f = _shell(parent, title, 380, 216)
    out = {}
    tk.Label(f, text=natural(message), bg=U.BG, fg=U.FG, font=U.FONT_S,
             wraplength=320, justify="left").pack(anchor="w")
    if hint:
        tk.Label(f, text=hint, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS,
                 wraplength=320, justify="left").pack(anchor="w", pady=(3, 0))
    var = tk.StringVar(value=initial)
    box = U.entry(f, var)
    box.pack(fill="x", pady=(12, 0))

    def ok():
        out["v"] = var.get().strip()
        win.destroy()
    row = tk.Frame(f, bg=U.BG)
    row.pack(fill="x", pady=(16, 0))
    U.PushButton(row, "확인", ok, height=34, font=U.FONT_B).pack(side="right")
    U.ghost_button(row, "취소", win.destroy, height=34).pack(side="right",
                                                           padx=(0, 8))
    win.bind("<Return>", lambda ev: ok())
    win.after(60, lambda: box.entry.focus_set())
    win.grab_set()
    parent.wait_window(win)
    return out.get("v")


def confirm(parent, title, message, danger=True, ok_text="확인"):
    """예/아니오 확인.

    danger=True 면 머리띠와 확인 버튼이 빨강이 된다. 되돌릴 수 없는 동작
    (회원탈퇴 같은)에만 쓴다. 그냥 되묻는 정도면 danger=False.
    """
    win, f = _shell(parent, title, 380, 196, danger=danger)
    out = {"v": False}
    tk.Label(f, text=natural(message), bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
             wraplength=320, justify="left").pack(anchor="w", pady=(0, 16))

    def ok():
        out["v"] = True
        win.destroy()
    row = tk.Frame(f, bg=U.BG)
    row.pack(fill="x")
    if danger:
        U.danger_button(row, ok_text, ok, height=34).pack(side="right")
    else:
        U.PushButton(row, ok_text, ok, height=34, font=U.FONT_B).pack(side="right")
    U.ghost_button(row, "취소", win.destroy, height=34).pack(side="right",
                                                           padx=(0, 8))
    win.grab_set()
    parent.wait_window(win)
    return out["v"]


def confirm_release(parent, app, mon):
    """놓아주기 확인. 어떤 포켓몬인지 **실제 도트**를 같이 보여준다."""
    info = mon.get("info", {})
    win, f = _shell(parent, "놓아주기", 380, 232, danger=True)
    out = {"v": False}

    row = tk.Frame(f, bg=U.BG)
    row.pack(fill="x")
    art = tk.Label(row, bg=U.BG, width=8, height=4)
    art.pack(side="left", padx=(0, 12), anchor="n")
    txt = tk.Frame(row, bg=U.BG)
    txt.pack(side="left", fill="x", expand=True)
    tk.Label(txt, text="%s  Lv.%d" % (info.get("name", "?"), mon.get("level", 0)),
             bg=U.BG, fg=U.FG, font=U.FONT_B, anchor="w").pack(anchor="w")
    tk.Label(txt, text="%s · 개체값 %.0f%%" % (info.get("species", ""),
                                             info.get("ivPercent", 0)),
             bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w").pack(anchor="w")
    tk.Label(txt, text="정말 놓아줄까요?\n되돌릴 수 없습니다.", bg=U.BG, fg=U.DANGER,
             font=U.FONT_S, justify="left").pack(anchor="w", pady=(8, 0))

    keep = {}

    def work():
        return sprite_cache.ensure(app.api, mon.get("num"), mon.get("shiny"))

    def done(path, err):
        if err or not path:
            return
        try:
            anim = sprites.load_animation(path, target_height=62,
                                          min_scale=0.2, max_scale=3.0)
            keep["p"] = ImageTk.PhotoImage(
                sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key))
            art.configure(image=keep["p"], width=0, height=0)
        except Exception:
            pass
    U.run_async(parent, work, done)

    def ok():
        out["v"] = True
        win.destroy()
    brow = tk.Frame(f, bg=U.BG)
    brow.pack(fill="x", pady=(16, 0))
    U.danger_button(brow, "놓아주기", ok, height=34).pack(side="right")
    U.ghost_button(brow, "취소", win.destroy, height=34).pack(side="right",
                                                            padx=(0, 8))
    win.grab_set()
    parent.wait_window(win)
    return out["v"]


_confirm = confirm
_ask_text = ask_text
