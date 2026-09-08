# -*- coding: utf-8 -*-
"""기술머신 탭.

왼쪽에 기술머신 358개, 오른쪽에 그걸 배울 수 있는 내 포켓몬.

## 다른 탭과 다른 점

기술머신은 **살 수도 팔 수도 없고 써도 없어지지 않는다.** 그래서 개수도
가격도 안 보여준다. 있으면 쓸 수 있고, 없으면 잡아서 얻는 수밖에 없다.

**안 가진 것도 같이 보여준다.** 358개 중 무엇을 더 모아야 하는지 보이는
편이 모으는 재미가 있다. 안 가진 것은 흐리게 두고 고를 수 없게 한다.

배울 수 있는지는 **서버가 정한다.** 여기서 걸러 보여주는 것은 편의일
뿐이고, 실제 판정은 /api/tms/use 가 한다.
"""
import tkinter as tk

from common.korean import natural

from . import sprite_cache, sprites
from . import ui_common as U
from .ui_bag import _scroller
from .ui_learn import ask_forget

LIST_W = 320
ROW_H = U.h(30)
MON_H = U.h(34)
THUMB = 22

TYPE_KR = {
    "NORMAL": "노말", "FIRE": "불꽃", "WATER": "물", "GRASS": "풀",
    "ELECTRIC": "전기", "ICE": "얼음", "FIGHTING": "격투", "POISON": "독",
    "GROUND": "땅", "FLYING": "비행", "PSYCHIC": "에스퍼", "BUG": "벌레",
    "ROCK": "바위", "GHOST": "고스트", "DRAGON": "드래곤", "DARK": "악",
    "STEEL": "강철", "FAIRY": "페어리", "STELLAR": "스텔라",
}
CAT_KR = {"physical": "물리", "special": "특수", "status": "변화"}


class TmWindow(object):

    def __init__(self, root, app, parent=None):
        self.root = root
        self.app = app
        self.alive = True

        self.tms = []            # 서버가 준 전체 목록
        self.mons = []
        self.photos = {}
        self.rows = {}
        self.mon_rows = {}
        self.no = None           # 고른 기술머신 번호
        self.mon_id = None
        self.only_have = True    # 가진 것만 보기
        self._msg = None

        self.win = U.panel(parent, root, "포스크탑 — 기술머신",
                           1000, 664, 950, 600, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)

        self._header()
        self._bottom()
        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True)
        self._list_pane(body)
        self._detail_pane(body)

        U.scrollable(self.list_canvas, 60)
        U.scrollable(self.mon_canvas, 60)
        self.reload()

    # ---------------- 머리 ----------------
    def _header(self):
        bar = tk.Frame(self.win, bg=U.BG2, height=U.h(44))
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=U.ACCENT, width=3, height=U.h(16)).pack(side="left",
                                                            padx=(14, 10))
        tk.Label(bar, text="기술머신", bg=U.BG2, fg=U.FG,
                 font=U.FONT_T).pack(side="left")
        self.count_lbl = tk.Label(bar, text="", bg=U.BG2, fg=U.FG_DIM,
                                  font=U.FONT_S)
        self.count_lbl.pack(side="left", padx=(10, 0))

        self.filter_btn = U.ghost_button(bar, "가진 것만", self._toggle_filter,
                                         height=28)
        self.filter_btn.pack(side="right", padx=(0, 14))
        tk.Label(bar, text="상점에서 살 수 없습니다. 포켓몬을 잡으면 나옵니다.",
                 bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS).pack(side="right",
                                                               padx=(0, 12))
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

    def _bottom(self):
        f = tk.Frame(self.win, bg=U.BG2, height=U.h(44))
        f.pack(fill="x", side="bottom")
        f.pack_propagate(False)
        self.status = tk.Label(f, text="", bg=U.BG2, fg=U.FG_FAINT,
                               font=U.FONT_S, anchor="w")
        self.status.pack(side="left", padx=14)
        self.use_btn = U.PushButton(f, "가르치기", self.teach, height=30,
                                    font=U.FONT_B)
        self.use_btn.pack(side="right", padx=14, pady=7)
        tk.Frame(self.win, bg=U.LINE, height=U.h(1)).pack(fill="x", side="bottom")

    def say(self, msg, color=None):
        if not self.alive:
            return
        self.status.configure(text=natural(msg or ""),
                              fg=color or U.FG_FAINT)

    # ---------------- 목록 ----------------
    def _list_pane(self, body):
        left = tk.Frame(body, bg=U.BG, width=LIST_W)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self.list_canvas, self.list_inner = _scroller(left, U.BG)

    def _detail_pane(self, body):
        right = tk.Frame(body, bg=U.BG2)
        right.pack(side="left", fill="both", expand=True)
        tk.Frame(right, bg=U.LINE, width=1).pack(side="left", fill="y")

        head = tk.Frame(right, bg=U.BG2)
        head.pack(fill="x", padx=18, pady=(16, 8))
        self.title_lbl = tk.Label(head, text="기술머신을 고르세요",
                                  bg=U.BG2, fg=U.FG, font=U.FONT_H,
                                  anchor="w")
        self.title_lbl.pack(anchor="w")
        self.sub_lbl = tk.Label(head, text="", bg=U.BG2, fg=U.FG_DIM,
                                font=U.FONT_S, anchor="w", justify="left",
                                wraplength=520)
        self.sub_lbl.pack(anchor="w", pady=(4, 0))

        tk.Label(right, text="배울 수 있는 포켓몬", bg=U.BG2, fg=U.FG_FAINT,
                 font=U.FONT_XS, anchor="w").pack(anchor="w", padx=18,
                                                  pady=(10, 4))
        holder = tk.Frame(right, bg=U.BG2)
        holder.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.mon_canvas, self.mon_inner = _scroller(holder, U.BG2)

    # ---------------- 불러오기 ----------------
    def reload(self):
        def work():
            return self.app.api.tms()

        def done(r, err):
            if not self.alive:
                return
            if err:
                return self.say("불러오지 못했습니다. %s" % err, U.RED)
            data = r
            self.tms = data.get("tms") or []
            self.count_lbl.configure(
                text="%d / %d 개" % (data.get("haveCount", 0),
                                     data.get("total", 0)))
            self._paint_list()
            self._paint_detail()
            if self._msg:
                self.say(*self._msg)
                self._msg = None

        U.run_async(self.root, work, done)

    def _toggle_filter(self):
        self.only_have = not self.only_have
        self.filter_btn.configure(
            text="가진 것만" if self.only_have else "전부")
        self._paint_list()

    def _visible(self):
        return [t for t in self.tms if t.get("have") or not self.only_have]

    def _paint_list(self):
        for w in self.list_inner.winfo_children():
            w.destroy()
        self.rows = {}
        rows = self._visible()
        if not rows:
            tk.Label(self.list_inner,
                     text="아직 하나도 없습니다.\n포켓몬을 잡으면 가끔 나옵니다.",
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S,
                     justify="left").pack(anchor="w", padx=16, pady=16)
            return
        for t in rows:
            self._row(t)
        if self.no is not None:
            self._mark()

    def _row(self, t):
        have = bool(t.get("have"))
        f = tk.Frame(self.list_inner, bg=U.BG, height=ROW_H)
        f.pack(fill="x")
        f.pack_propagate(False)
        no = tk.Label(f, text="%03d" % t["no"], bg=U.BG,
                      fg=U.FG_FAINT if have else U.LINE2,
                      font=U.FONT_XS, width=4, anchor="w")
        no.pack(side="left", padx=(12, 4))
        nm = tk.Label(f, text=t["kr"], bg=U.BG,
                      fg=U.FG if have else U.FG_FAINT,
                      font=U.FONT if have else U.FONT_S, anchor="w")
        nm.pack(side="left")
        ty = tk.Label(f, text=TYPE_KR.get(t["type"], t["type"]), bg=U.BG,
                      fg=U.FG_FAINT if have else U.LINE2,
                      font=U.FONT_XS, anchor="e")
        ty.pack(side="right", padx=(0, 12))
        self.rows[t["no"]] = (f, no, nm, ty, have)
        if have:
            for w in (f, no, nm, ty):
                w.bind("<Button-1>", lambda _e, n=t["no"]: self.pick(n))

    def _mark(self):
        for n, (f, no, nm, ty, have) in self.rows.items():
            on = (n == self.no)
            bg = U.ACCENT_SOFT if on else U.BG
            for w in (f, no, nm, ty):
                w.configure(bg=bg)
            nm.configure(fg=U.ACCENT_TEXT if on
                         else (U.FG if have else U.FG_FAINT))

    def pick(self, no):
        self.no = no
        self.mon_id = None
        self._mark()
        self._paint_detail()

    # ---------------- 오른쪽 ----------------
    def _cur(self):
        for t in self.tms:
            if t["no"] == self.no:
                return t
        return None

    def _paint_detail(self):
        for w in self.mon_inner.winfo_children():
            w.destroy()
        self.mon_rows = {}
        t = self._cur()
        if not t:
            self.title_lbl.configure(text="기술머신을 고르세요")
            self.sub_lbl.configure(text="")
            return
        self.title_lbl.configure(text=t["label"])
        self.sub_lbl.configure(
            text="%s · %s" % (TYPE_KR.get(t["type"], t["type"]),
                              CAT_KR.get(t["cat"], t["cat"])))

        self._fill_mons(t)

    def _fill_mons(self, t):
        """이 기술머신을 배울 수 있는 내 포켓몬을 채운다.

        **서버에 한 번만 묻는다.** 마리마다 물어보면 예순 마리를 가진
        사람은 기술머신을 하나 고를 때마다 예순 번을 두드린다.
        """
        def work():
            return self.app.api.tm_learners(t["no"])

        def done(r, err):
            if not self.alive or self._cur() is not t:
                return
            if err:
                return self.say("포켓몬을 불러오지 못했습니다. %s" % err, U.RED)
            rows = (r or {}).get("learners") or []
            if not rows:
                tk.Label(self.mon_inner,
                         text="이 기술머신을 배울 수 있는 포켓몬이 없습니다.",
                         bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_S).pack(
                             anchor="w", padx=8, pady=12)
                return
            for m in rows:
                self._mon_row(m, m.get("known"), m.get("moves") or [])

        U.run_async(self.root, work, done)

    def _mon_row(self, mon, known, moves):
        f = tk.Frame(self.mon_inner, bg=U.BG2, height=MON_H)
        f.pack(fill="x", pady=1)
        f.pack_propagate(False)
        holder = tk.Label(f, bg=U.BG2, width=3)
        holder.pack(side="left", padx=(8, 4))
        name = tk.Label(f, text="%s Lv.%s" % (mon.get("name", "?"),
                                              mon.get("level", "?")),
                        bg=U.BG2, fg=U.FG, font=U.FONT, anchor="w")
        name.pack(side="left")
        note = tk.Label(f, text="이미 배움" if known else "",
                        bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS, anchor="e")
        note.pack(side="right", padx=(0, 10))
        self.mon_rows[mon["id"]] = (f, holder, name, note, moves, known)
        if not known:
            for w in (f, holder, name, note):
                w.bind("<Button-1>", lambda _e, i=mon["id"]: self.pick_mon(i))
        self._thumb(mon, holder)

    def _thumb(self, mon, holder):
        got = self.photos.get(mon["id"])
        if got is not None:
            return holder.configure(image=got)

        def work():
            return sprite_cache.ensure(self.app.api, mon.get("num"),
                                       mon.get("shiny"))

        def done(path, err):
            if not self.alive or err or not path:
                return
            try:
                anim = sprites.load_animation(path, THUMB, 0.2, 2.0)
                img = sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key)
                from PIL import ImageTk
                photo = ImageTk.PhotoImage(img)
            except Exception:                              # noqa: BLE001
                return
            self.photos[mon["id"]] = photo
            try:
                holder.configure(image=photo)
            except Exception:                              # noqa: BLE001
                pass

        U.run_async(self.root, work, done)

    def pick_mon(self, pid):
        self.mon_id = pid
        for i, (f, holder, name, note, moves, known) in self.mon_rows.items():
            on = (i == pid)
            bg = U.ACCENT_SOFT if on else U.BG2
            for w in (f, holder, name, note):
                w.configure(bg=bg)
            name.configure(fg=U.ACCENT_TEXT if on else U.FG)

    # ---------------- 가르치기 ----------------
    def teach(self):
        t = self._cur()
        if not t:
            return self.say("기술머신을 먼저 고르세요.")
        if not self.mon_id:
            return self.say("가르칠 포켓몬을 고르세요.")
        got = self.mon_rows.get(self.mon_id)
        moves = list(got[4]) if got else []
        name = got[2].cget("text").split(" Lv.")[0] if got else "포켓몬"

        forget = ""
        if len(moves) >= 4:
            pick = ask_forget(self.win, name, t["move"], moves,
                              getattr(self.app, "dex", None))
            if pick is None:
                return                       # 창을 닫았다
            if pick == "":
                return self.say("배우지 않았습니다.")
            forget = pick

        def work():
            return self.app.api.tm_use(t["no"], self.mon_id, forget)

        def done(r, err):
            if not self.alive:
                return
            if err:
                return self.say("%s" % err, U.RED)
            if r.get("needForget"):
                return self.say("기술이 네 개입니다. 다시 골라 주세요.")
            self._msg = (r.get("message") or "배웠다!", U.GOOD)
            self.reload()

        self.say("가르치는 중...")
        U.run_async(self.root, work, done)

    # ---------------- 닫기 ----------------
    def close(self):
        self.alive = False
        try:
            if not U.is_embedded(self.win):
                self.win.destroy()
        except Exception:                                  # noqa: BLE001
            pass
