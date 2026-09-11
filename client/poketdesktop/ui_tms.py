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

## 빨리 그리기

줄은 358개를 **한 번 만들어 두고** '가진 것만/전부' 는 담았다 뺐다만
한다. 예전에는 누를 때마다 줄을 다 부수고 새로 만들어 2.5초씩 멈췄다.
처음 만들 때는 첫 화면만큼 먼저 만들고 나머지는 나눠 만든다(U.Chunked).
"""
import tkinter as tk

from PIL import ImageTk

from common import movetext as MT
from common.korean import natural

from . import sprite_cache, sprites
from . import ui_common as U
from . import ui_loading
from .ui_bag import _scroller
from .ui_learn import ask_forget

LIST_W = 320
ROW_H = U.h(30)
MON_H = U.h(34)
THUMB = 22
# 도트 칸의 폭. **Label 의 width 로 잡으면 안 된다.** width 는 글자일 때는
# 글자 수인데 그림일 때는 픽셀이라, width=3 이 22px 도트를 3px(테두리까지
# 7px)로 잘랐다. 선물 창에서 한 번 겪은 함정이다. 고정 크기 칸(Frame)에
# 넣으면 그림이 오기 전과 후에 이름 자리도 안 흔들린다. 맥은 테두리를
# 1~2px 다르게 셀 수 있어서 넉넉히 잡는다.
SLOT_W = U.h(52)
# 칸에 넣을 도트의 최대 크기. 옆으로 긴 종은 높이를 덜 채우고 작아진다 -
# 잘려서 반만 보이는 것보다 낫다.
THUMB_MAX = (SLOT_W - 2, MON_H - 4)

TYPE_KR = {
    "NORMAL": "노말", "FIRE": "불꽃", "WATER": "물", "GRASS": "풀",
    "ELECTRIC": "전기", "ICE": "얼음", "FIGHTING": "격투", "POISON": "독",
    "GROUND": "땅", "FLYING": "비행", "PSYCHIC": "에스퍼", "BUG": "벌레",
    "ROCK": "바위", "GHOST": "고스트", "DRAGON": "드래곤", "DARK": "악",
    "STEEL": "강철", "FAIRY": "페어리", "STELLAR": "스텔라",
}
# 분류 이름은 common/movetext 가 갖고 있다. 화면마다 따로 적으면
# 한쪽만 고쳐지는 날이 온다.
CAT_KR = MT.CAT_KR


class TmWindow(object):

    def __init__(self, root, app, parent=None):
        self.root = root
        self.app = app
        self.alive = True

        self.tms = []            # 서버가 준 전체 목록
        self.mons = []
        self.photos = {}         # {(도감 번호, 이로치): PhotoImage} — 종마다 한 장
        self.rows = {}           # {번호: (f, no, nm, ty, ct, have)} — 만들어 둔 줄 전부
        self.mon_rows = {}
        self.no = None           # 고른 기술머신 번호
        self.mon_id = None
        self.only_have = True    # 가진 것만 보기
        self._msg = None
        self._wait = None        # 불러오는 중 표시
        self._list_job = None    # 왼쪽 줄을 나눠 만드는 일
        self._list_key = None    # 지금 만들어 둔 줄이 어떤 목록인지
        self._build_have = True  # 줄을 만들기 시작할 때의 '가진 것만'
        self._packed = set()     # 지금 담겨(pack) 있는 줄 번호
        self._show_job = None    # 새로 보일 줄을 나눠 담는 일
        self._empty = None       # '아직 하나도 없습니다'
        self._mon_job = None     # 오른쪽 줄을 나눠 만드는 일
        self._mon_gen = 0        # 오른쪽 목록의 세대. 바뀌면 늦게 온 답은 버린다

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
        # 무엇을 하는 기술인지가 어디에도 없었다. 타입과 분류만 보고
        # 가르칠지 말지를 정해야 했다. 설명은 도감에 이미 들어 있다
        # (t["move"] 가 내부 이름이라 그대로 찾아 쓴다. 서버가 다시
        # 실어 보낼 것이 없다).
        self.desc_lbl = tk.Label(head, text="", bg=U.BG2, fg=U.FG_DIM,
                                 font=U.FONT_S, anchor="w", justify="left",
                                 wraplength=520)
        self.desc_lbl.pack(anchor="w", pady=(6, 0), fill="x")
        U.wrap_to_width(self.desc_lbl)

        tk.Label(right, text="배울 수 있는 포켓몬", bg=U.BG2, fg=U.FG_FAINT,
                 font=U.FONT_XS, anchor="w").pack(anchor="w", padx=18,
                                                  pady=(10, 4))
        holder = tk.Frame(right, bg=U.BG2)
        holder.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.mon_canvas, self.mon_inner = _scroller(holder, U.BG2)

    # ---------------- 불러오기 ----------------
    def reload(self):
        # 기다리는 동안 아무 표시가 없으면 고장 난 줄 안다. 가르친 뒤에
        # 다시 불러올 때는 덮지 않는다 - 결과는 아래 줄에 적는다(가방과 같다).
        if not self._msg and self._wait is None:
            self._wait = ui_loading.Overlay(self.win, "기술머신을 불러오는 중")

        def work():
            return self.app.api.tms()

        def done(r, err):
            w, self._wait = self._wait, None
            if not self.alive:
                if w:
                    w.close()
                return
            if err:
                if w:
                    w.close()
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
            if w:
                # **첫 화면이 그려진 뒤에 걷는다.** 맨 앞에서 걷으면 줄을
                # 만드는 동안 아무 표시 없이 멈춘 것처럼 보인다.
                try:
                    self.root.after_idle(w.close)
                except tk.TclError:
                    w.close()

        U.run_async(self.root, work, done)

    def _toggle_filter(self):
        self.only_have = not self.only_have
        self.filter_btn.configure(
            text="가진 것만" if self.only_have else "전부")
        self._show_rows()

    def _visible(self):
        return [t for t in self.tms if t.get("have") or not self.only_have]

    def _paint_list(self):
        """왼쪽 줄을 만든다.

        **목록이 그대로면 만들어 둔 줄을 그대로 쓴다.** 가르친 뒤에 다시
        불러와도 기술머신 목록은 안 바뀐다 - 358줄을 다시 만들 까닭이 없다.

        새로 만들 때는 **지금 보일 줄부터** 만든다. 그래야 처음 만드는
        묶음이 곧 첫 화면이다. 안 보일 줄은 만들어만 두고 담지 않는다.
        담지 않은 줄은 창(HWND)도 안 생겨서 싸다.
        """
        key = [(t["no"], t["kr"], t["type"], t["cat"], bool(t.get("have")))
               for t in self.tms]
        job = self._list_job
        if key == self._list_key and not (job is not None and job.pending):
            return
        if job is not None:
            job.cancel()            # 옛 목록의 남은 줄이 뒤에 붙지 않게
        self._list_job = None
        if self._show_job is not None:
            self._show_job.cancel()
            self._show_job = None
        for w in self.list_inner.winfo_children():
            w.destroy()
        self.rows = {}
        self._packed = set()
        self._empty = None
        self._list_key = key
        # 담을지 말지는 **만들기 시작할 때의 거르기**로 정한다. 만드는 중에
        # 거르기를 바꾸면 남은 줄이 새 기준으로 끝에 붙어서 순서가 섞인다.
        # 바뀐 거르기는 _show_rows 가 다 만든 뒤에 맞춘다.
        self._build_have = self.only_have
        vis = self._visible()
        rest = [t for t in self.tms if not (t.get("have") or not self.only_have)]
        if not vis:
            self._show_empty(True)
        self._list_job = U.Chunked(self.win, vis + rest, self._row)

    def _wanted(self, t):
        return bool(t.get("have")) or not self._build_have

    def _row(self, t):
        have = bool(t.get("have"))
        # 고름은 만들 때 칠한다. 다 만들고 358줄을 다시 칠하지 않는다.
        on = (t["no"] == self.no)
        bg = U.ACCENT_SOFT if on else U.BG
        f = tk.Frame(self.list_inner, bg=bg, height=ROW_H)
        f.pack_propagate(False)
        no = tk.Label(f, text="%03d" % t["no"], bg=bg,
                      fg=U.FG_FAINT if have else U.LINE2,
                      font=U.FONT_XS, width=4, anchor="w")
        no.pack(side="left", padx=(12, 4))
        nm = tk.Label(f, text=t["kr"], bg=bg,
                      fg=U.ACCENT_TEXT if on else (U.FG if have else U.FG_FAINT),
                      font=U.FONT if have else U.FONT_S, anchor="w")
        nm.pack(side="left")
        ty = tk.Label(f, text=TYPE_KR.get(t["type"], t["type"]), bg=bg,
                      fg=U.FG_FAINT if have else U.LINE2,
                      font=U.FONT_XS, anchor="e")
        ty.pack(side="right", padx=(0, 12))
        # 358개를 훑을 때 타입만으로는 쓸 만한지 모른다. 공격이 높은
        # 포켓몬을 키우는 사람에게 특수기 기술머신은 소용이 없다.
        ct = tk.Label(f, text=CAT_KR.get(t["cat"], t["cat"]), bg=bg,
                      fg=MT.cat_color(t) if have else U.LINE2,
                      font=U.FONT_XS, anchor="e")
        ct.pack(side="right", padx=(0, 8))
        self.rows[t["no"]] = (f, no, nm, ty, ct, have)
        if have:
            for w in (f, no, nm, ty, ct):
                w.bind("<Button-1>", lambda _e, n=t["no"]: self.pick(n))
        # 보일 줄부터 차례로 만들므로 끝에 담으면 순서가 맞는다.
        if self._wanted(t):
            f.pack(fill="x")
            self._packed.add(t["no"])

    def _show_rows(self):
        """거르기를 바꿨다. 줄은 그대로 두고 담았다 뺐다만 한다.

        **보이던 줄은 건드리지 않는다.** 다 빼고 다시 담으면 계속 보일 줄까지
        숨었다 나타나며 깜빡인다. 안 보일 줄만 빼고, 새로 보일 줄은 제자리
        (순서상 바로 앞 줄의 뒤)에 끼운다.

        **새로 담는 것도 나눠 한다.** 줄을 다시 만들지 않아도, 처음 화면에
        나오는 줄은 창을 새로 붙이느라 한 줄에 몇 ms 씩 든다. '전부' 로
        바꾸면 239줄이라 한 번에 담으면 0.7~1.6초 멈췄다. 첫 화면만큼 먼저
        담고 나머지는 이어서 담는다. 도중에 또 바꾸면 남은 것은 버린다 -
        담긴 줄은 늘 번호 순서라 거기서부터 다시 맞추면 된다.
        """
        if self._list_job is not None and self._list_job.pending:
            # 아직 안 만든 줄이 있다. 끼울 자리를 찾으려면 다 있어야 한다.
            self._list_job.flush()
        if self._show_job is not None:
            self._show_job.cancel()
            self._show_job = None
        want = [t["no"] for t in self._visible() if t["no"] in self.rows]
        wanted = set(want)
        for n in [n for n in self._packed if n not in wanted]:
            self.rows[n][0].pack_forget()
            self._packed.discard(n)
        first_kept = next((n for n in want if n in self._packed), None)
        adds = []
        prev = None
        for n in want:
            if n not in self._packed:
                adds.append((n, prev))
            prev = n
        self._show_empty(not want)
        if adds:
            self._show_job = U.Chunked(
                self.win, adds, lambda a: self._pack_row(a[0], a[1], first_kept))

    def _pack_row(self, n, prev, first_kept):
        """n 번 줄을 제자리에 담는다. prev 는 순서상 바로 앞 줄(이미 담겼다)."""
        f = self.rows[n][0]
        if prev is not None:
            f.pack(fill="x", after=self.rows[prev][0])
        elif first_kept is not None:
            f.pack(fill="x", before=self.rows[first_kept][0])
        else:
            f.pack(fill="x")
        self._packed.add(n)

    def _show_empty(self, on):
        if on:
            if self._empty is None:
                self._empty = tk.Label(
                    self.list_inner,
                    text="아직 하나도 없습니다.\n포켓몬을 잡으면 가끔 나옵니다.",
                    bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S, justify="left")
            self._empty.pack(anchor="w", padx=16, pady=16)
        elif self._empty is not None:
            self._empty.pack_forget()

    def _mark(self, n):
        """n 번 줄을 고름에 맞춰 칠한다."""
        got = self.rows.get(n)
        if got is None:
            return
        f, no, nm, ty, ct, have = got
        on = (n == self.no)
        bg = U.ACCENT_SOFT if on else U.BG
        for w in (f, no, nm, ty, ct):
            w.configure(bg=bg)
        nm.configure(fg=U.ACCENT_TEXT if on
                     else (U.FG if have else U.FG_FAINT))

    def pick(self, no):
        prev, self.no = self.no, no
        self.mon_id = None
        if (no not in self.rows and self._list_job is not None
                and self._list_job.pending):
            self._list_job.flush()      # 아직 안 만든 줄이면 먼저 다 만든다
        # 바뀐 두 줄만 칠한다. 고른 줄은 늘 하나다.
        for n in set((prev, no)):
            self._mark(n)
        self._paint_detail()

    # ---------------- 오른쪽 ----------------
    def _cur(self):
        for t in self.tms:
            if t["no"] == self.no:
                return t
        return None

    def _move(self, t):
        """이 기술머신이 가르치는 기술. 도감이 없으면 빈 것."""
        dex = getattr(self.app, "dex", None)
        if dex is None or not t.get("move"):
            return {}
        try:
            return dex.move(t["move"]) or {}
        except Exception:                                   # noqa: BLE001
            return {}

    def _paint_detail(self):
        # 세대를 올린다. 전에 물어 둔 답(배울 포켓몬·도트)이 늦게 와도
        # 새로 그린 목록에 섞이지 않는다. 같은 기술머신을 두 번 눌러도 그렇다.
        self._mon_gen += 1
        if self._mon_job is not None:
            self._mon_job.cancel()
            self._mon_job = None
        for w in self.mon_inner.winfo_children():
            w.destroy()
        self.mon_rows = {}
        t = self._cur()
        if not t:
            self.title_lbl.configure(text="기술머신을 고르세요")
            self.sub_lbl.configure(text="")
            self.desc_lbl.configure(text="")
            return
        self.title_lbl.configure(text=t["label"])
        md = self._move(t)
        bits = [TYPE_KR.get(t["type"], t["type"]),
                CAT_KR.get(t["cat"], t["cat"])]
        # 위력·명중·PP 는 도감에서 온다. 없으면 타입과 분류만 적는다.
        bits += MT.stat_bits(md, with_cat=False) if md else []
        self.sub_lbl.configure(text=MT.SEP.join(b for b in bits if b))
        self.desc_lbl.configure(text=MT.desc(md) if md else "")

        self._fill_mons(t)

    def _fill_mons(self, t):
        """이 기술머신을 배울 수 있는 내 포켓몬을 채운다.

        **서버에 한 번만 묻는다.** 마리마다 물어보면 예순 마리를 가진
        사람은 기술머신을 하나 고를 때마다 예순 번을 두드린다.
        """
        gen = self._mon_gen
        # 묻는 동안 칸이 비어 있으면 '배울 포켓몬이 없다' 로 읽힌다.
        wait = tk.Label(self.mon_inner, text="불러오는 중...", bg=U.BG2,
                        fg=U.FG_FAINT, font=U.FONT_S)
        wait.pack(anchor="w", padx=8, pady=12)

        def work():
            return self.app.api.tm_learners(t["no"])

        def done(r, err):
            if not self.alive or gen != self._mon_gen or self._cur() is not t:
                return
            try:
                wait.destroy()
            except tk.TclError:
                pass
            if err:
                return self.say("포켓몬을 불러오지 못했습니다. %s" % err, U.RED)
            rows = (r or {}).get("learners") or []
            if not rows:
                tk.Label(self.mon_inner,
                         text="이 기술머신을 배울 수 있는 포켓몬이 없습니다.",
                         bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_S).pack(
                             anchor="w", padx=8, pady=12)
                return
            self._thumbs(rows, t, gen)
            self._mon_job = U.Chunked(
                self.win, rows,
                lambda m: self._mon_row(m, m.get("known"), m.get("moves") or []))

        U.run_async(self.root, work, done)

    def _mon_row(self, mon, known, moves):
        f = tk.Frame(self.mon_inner, bg=U.BG2, height=MON_H)
        f.pack(fill="x", pady=1)
        f.pack_propagate(False)
        # 도트는 고정 크기 칸에 넣는다 (SLOT_W 의 설명을 보라).
        slot = tk.Frame(f, bg=U.BG2, width=SLOT_W, height=MON_H)
        slot.pack(side="left", padx=(8, 4))
        slot.pack_propagate(False)
        holder = tk.Label(slot, bg=U.BG2, bd=0, padx=0, pady=0,
                          highlightthickness=0)
        holder.pack(expand=True)
        got = self.photos.get((mon.get("num"), bool(mon.get("shiny"))))
        if got is not None:
            holder.configure(image=got)
        name = tk.Label(f, text="%s Lv.%s" % (mon.get("name", "?"),
                                              mon.get("level", "?")),
                        bg=U.BG2, fg=U.FG, font=U.FONT, anchor="w")
        name.pack(side="left")
        note = tk.Label(f, text="이미 배움" if known else "",
                        bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS, anchor="e")
        note.pack(side="right", padx=(0, 10))
        self.mon_rows[mon["id"]] = (f, holder, name, note, moves, known)
        if not known:
            for w in (f, slot, holder, name, note):
                w.bind("<Button-1>", lambda _e, i=mon["id"]: self.pick_mon(i))

    def _thumbs(self, learners, t, gen):
        """오른쪽 목록의 도트를 **한 번에** 만든다.

        예전에는 마리마다 스레드를 하나씩 띄우고(예순 마리면 예순 개),
        받은 GIF 를 Tk 스레드에서 풀었다. 22px 한 장을 보이려고 모든
        프레임을 파이썬으로 훑어서 한 마리에 25ms, 예순 마리짜리 기술머신을
        고르는 데 2.9초가 들었다.

        목록에는 첫 장만 쓰므로 첫 장만 읽고(max_frames=1), 칸에 맞춰
        줄이는 것까지(max_size) 작업 스레드 하나에서 끝낸다. Tk 스레드는
        PhotoImage 로 감싸기만 한다. 같은 종은 한 번만 만든다.
        """
        want = []
        for m in learners:
            k = (m.get("num"), bool(m.get("shiny")))
            if k[0] and k not in self.photos and k not in want:
                want.append(k)
        if not want:
            return
        api = self.app.api

        def work():
            out = {}
            for num, shiny in want:
                try:
                    path = sprite_cache.ensure(api, num, shiny)
                    if not path:
                        continue
                    anim = sprites.load_animation(path, THUMB, 0.2, 2.0,
                                                  max_frames=1,
                                                  max_size=THUMB_MAX)
                    out[(num, shiny)] = sprites.to_rgba(
                        anim.frames[sprites.RIGHT][0], anim.key)
                except Exception:                          # noqa: BLE001
                    pass
            return out

        def done(imgs, err):
            if not self.alive or err or not imgs:
                return
            for k, img in imgs.items():
                if k not in self.photos:
                    try:
                        self.photos[k] = ImageTk.PhotoImage(img)
                    except Exception:                      # noqa: BLE001
                        pass
            # 그사이 다른 기술머신을 골랐으면 그 줄들은 이미 없다.
            # 만든 그림은 남겨 두고(다음에 그대로 쓴다) 줄에는 안 붙인다.
            if gen != self._mon_gen or self._cur() is not t:
                return
            for m in learners:
                got = self.mon_rows.get(m["id"])
                ph = self.photos.get((m.get("num"), bool(m.get("shiny"))))
                if got is None or ph is None:
                    continue          # 아직 안 만든 줄은 만들 때 붙는다
                try:
                    got[1].configure(image=ph)
                except tk.TclError:
                    pass

        U.run_async(self.root, work, done)

    def pick_mon(self, pid):
        prev, self.mon_id = self.mon_id, pid
        # 바뀐 두 줄만 칠한다.
        for i in set((prev, pid)):
            got = self.mon_rows.get(i)
            if got is None:
                continue
            f, holder, name, note, moves, known = got
            on = (i == pid)
            bg = U.ACCENT_SOFT if on else U.BG2
            for w in (f, holder.master, holder, name, note):
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
        for job in (self._list_job, self._show_job, self._mon_job):
            if job is not None:
                job.cancel()
        try:
            if not U.is_embedded(self.win):
                self.win.destroy()
        except Exception:                                  # noqa: BLE001
            pass
