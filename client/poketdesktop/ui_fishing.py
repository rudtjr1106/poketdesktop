# -*- coding: utf-8 -*-
"""낚시 기록 (시즌 7) — 주간 대물 순위. 연못 오른쪽 클릭 '낚시 기록' 과 허브 '이벤트' 묶음의 '낚시' 탭.

    ┌ 낚시 기록  11/30(월) ~ 12/6(일)                       끝나기까지 3일 5시간  [새로 고침] ┐
    │ [이번 주 | 지난주 | 내 기록]                                                          │
    │  순위       포켓몬                    무게      배율    트레이너                        │
    │     1  (●)  잉어킹 [왕대물]           18.4kg   1.84배   지우                            │
    │   ...  (30위까지)                                                                     │
    │  ──────────────── 내 자리 ────────────────                                            │
    │    41  (●)  콘치                       1.10kg   1.02배   나                             │
    │  순위는 같은 종의 표준 무게보다 몇 배 큰지(배율)로 … · 보상 …                              │
    └──────────────────────────────────────────────────────────────────────────────────────┘

  · 순위는 무게가 아니라 **배율**이다 (고래왕 398kg 이 늘 이기지 않게 - 설계). 1.3배 이상 금색 '대물', 1.6배 이상 '왕대물'
    (fish_text.badge - 서버와 같은 문턱).
  · 서버는 한 번에 이번 주 30줄 · 내 자리 · 지난주 1~3위 · 내 기록을 다 준다 (`fish_board("this")`) - 탭을 바꿔도
    다시 묻지 않는다.
  · 낚시를 모르는 옛 서버와 아직 안 연 시즌은 둘 다 404 다 - 오류 대신 '시즌 7에 열립니다' 한 줄 (배틀타워와 같다).
  · 화면 테마 전용 파일은 없다 - 기본 위젯으로만 그려 테마의 widgets.py 가 입힌다 (설계: 테마별 전용 창 없음).
"""
import datetime
import time
import tkinter as tk

from PIL import ImageTk

from . import config, fish_text, sprite_cache, sprites
from . import ui_box
from . import ui_common as U
from .ui_common import run_async

W, H = 760, 640
THUMB = 32                      # 도트 칸 (px - 글자 크기를 따라 U.h 로 키운다)
STALE_SEC = 60                  # 탭을 다시 골랐을 때 이보다 오래된 것이면 다시 불러온다
TICK_MS = 30 * 1000             # 띄워 둔 동안 '끝나기까지' 를 고쳐 적는 간격
FROM_DEFAULT = 7                # 옛 서버(404)는 언제 여는지 못 알려 준다 - 시즌 7 이다 (server config.FISH_FROM)
CLOSED_TEXT = "낚시는 시즌 %d에 열립니다."
TABS = (("this", "이번 주"), ("last", "지난주"), ("mine", "내 기록"))
MEDAL = {1: "#ffc043", 2: "#c9d1e6", 3: "#d08a52"}      # 1·2·3위 (ui_rank 와 같은 빛깔)
HUGE_FG = "#ff8a4c"             # 왕대물 - 대물(금색)보다 한 단계 뜨겁게
MINE_BG = U.ACCENT_SOFT         # 내 줄
ROW_BG = U.BG2
WEEK = "월화수목금토일"

# (열쇠, 머리글, 폭 px - 0 이면 남는 폭을 다 받는다, 글 자리)
RANK_COLS = (("rank", "순위", 44, "e"), ("pic", "", THUMB + 6, "center"), ("name", "포켓몬", 0, "w"),
             ("kg", "무게", 84, "e"), ("ratio", "배율", 72, "e"), ("who", "트레이너", 140, "w"))
MINE_COLS = (("pic", "", THUMB + 6, "center"), ("name", "포켓몬", 0, "w"),
             ("kg", "무게", 84, "e"), ("ratio", "배율", 72, "e"), ("at", "잡은 날", 80, "e"))

# 서버 정산(fishing.settle)과 같은 표 - 설계 '순위 (주간 대물)'. 서버 숫자가 바뀌면 같이 고친다.
RULES = ("순위는 같은 종의 표준 무게보다 몇 배 큰지(배율)로 매겨요. 그 주에 낚아서 잡은 포켓몬만, 한 사람에 한 줄. "
         "매주 월요일 0시에 새로 시작해요.\n"
         "보상 (월요일 0시 20분 뒤 선물함): 1위 큰금구슬 · 2~3위 금구슬 2개 · 4~10위 금구슬 · 11~30위 큰진주")


def ends_text(sec):
    """남은 초 -> '끝나기까지 3일 5시간' / '끝나기까지 5시간 2분' / '끝나기까지 10분'."""
    sec = int(sec or 0)
    if sec <= 0:
        return "새 주를 준비하는 중"
    d, rest = divmod(sec, 86400)
    h, rest = divmod(rest, 3600)
    m = rest // 60
    if d:
        return "끝나기까지 %d일 %d시간" % (d, h)
    if h:
        return "끝나기까지 %d시간 %d분" % (h, m)
    return "끝나기까지 %d분" % max(1, m)


def week_text(key, back=0):
    """주 열쇠(그 주 월요일 '2026-11-30') -> '11/30(월) ~ 12/6(일)'. back=1 이면 그 앞 주."""
    try:
        y, m, d = (int(x) for x in str(key).split("-"))
        a = datetime.date(y, m, d) - datetime.timedelta(days=7 * back)
    except (TypeError, ValueError):
        return ""
    b = a + datetime.timedelta(days=6)
    return "%d/%d(%s) ~ %d/%d(%s)" % (a.month, a.day, WEEK[a.weekday()], b.month, b.day, WEEK[b.weekday()])


def day_text(iso):
    """'2026-12-02T03:22:07+00:00' -> '12/2' (이 PC 의 시간대로). 서버는 UTC 로 보낸다."""
    try:
        t = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return ""
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    t = t.astimezone()
    return "%d/%d" % (t.month, t.day)


def thumb(api, num, shiny, size):
    """목록 칸의 작은 도트 (PIL). 작업 스레드에서 - 받은 적 없으면 서버에서 받는다 (sprite_cache)."""
    path = sprite_cache.ensure(api, num, bool(shiny))
    if not path:
        return None
    anim = sprites.load_animation(path, size, 0.2, 2.0, max_frames=1, max_size=(size, size))
    return sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key)


def open_records(app):
    """낚시 기록을 연다 (연못 오른쪽 클릭 '낚시 기록'). 이미 열려 있으면 그것을 앞으로 꺼내고 새로 불러온다.

    앱이면 허브 '이벤트' 묶음의 '낚시' 탭으로 연다 - 올림픽 · 아르케처럼 창을 하나 더 늘리지 않는다 (app._tab).
    허브가 없는 앱(검사의 가짜 앱)이면 창 하나로 띄운다.
    """
    tab = getattr(app, "_tab", None)
    if tab is not None:
        try:
            pane = tab("fishing")
        except Exception as e:                              # noqa: BLE001
            config.log("낚시 기록 탭 열기 실패: %s" % e)
            return None
        if pane is not None:
            pane.reload()           # 방금 만든 탭이면 이미 불러오는 중이라 그냥 지나간다
        return pane
    old = getattr(app, "fish_records", None)
    if old is not None and old.alive:
        old.focus()
        old.reload()
        return old
    w = FishRecords(app)
    app.fish_records = w
    return w


class FishRecords(object):
    """낚시 기록 창 · 탭. parent 를 주면(허브) 창 대신 그 안의 판으로 그린다 (U.panel)."""

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.alive = True
        self.data = None             # 서버가 준 순위 (열려 있을 때만)
        self.closed = False          # 옛 서버 · 아직 안 연 시즌 (404)
        self.tab = "this"
        self.rows = []               # 지금 그린 줄 [{"kind", "data", "cells", "mine"}] - kind: top · me · last · mine
        self.pics = []               # 지금 그린 도트 칸 [(라벨, 번호, 이로치)]
        self.photos = {}             # (번호, 이로치) -> PhotoImage (탭을 오가도 다시 안 받는다)
        self._pending = set()
        self._loading = False
        self._loaded_at = 0.0
        self._ends_at = None         # 이번 주가 끝나는 때 (time.time() 기준 - 서버 시계로 센 endsIn 을 더했다)
        self._tick_job = None

        self.win = U.panel(parent, self.root, "포스크탑 — 낚시 기록", W, H, 620, 480, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)
        self._header()
        # 아래 알림 줄을 몸통보다 먼저 담는다 - 창이 작아지면 나중에 담은 것부터 잘린다
        self.status = tk.Label(self.win, text=" ", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w",
                               justify="left")
        self.status.pack(side="bottom", fill="x", padx=16, pady=(0, 8))
        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 6))
        self.inner, self.cv = ui_box.scroll_body(body)
        tk.Label(self.inner, text="불러오는 중...", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(pady=24)
        self.reload()

    # ---------------- 틀 ----------------
    def _header(self):
        head = tk.Frame(self.win, bg=U.BG)
        head.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(head, text="낚시 기록", bg=U.BG, fg=U.FG, font=(U.FAMILY_BLACK, U.pt(18))).pack(side="left")
        self.week = tk.Label(head, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S)
        self.week.pack(side="left", padx=(12, 0))
        U.ghost_button(head, "새로 고침", self.reload, height=30).pack(side="right")
        self.ends = tk.Label(head, text="", bg=U.BG, fg=U.ACCENT, font=U.FONT_B)
        self.ends.pack(side="right", padx=(0, 12))
        bar = tk.Frame(self.win, bg=U.BG)
        bar.pack(fill="x", padx=16, pady=(0, 8))
        self.seg = U.Segmented(bar, TABS, self.tab, self.pick)
        self.seg.frame.pack(side="left")

    def say(self, text, color=None):
        try:
            self.status.configure(text=text or " ", fg=color or U.FG_FAINT)
        except tk.TclError:
            pass

    def _clear(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows, self.pics = [], []

    def _fit(self):
        try:
            self.inner.update_idletasks()
            self.cv.configure(scrollregion=self.cv.bbox("all"))
            self.cv.yview_moveto(0)
        except tk.TclError:
            pass

    # ---------------- 불러오기 ----------------
    def reload(self):
        if self._loading or not self.alive:
            return
        self._loading = True

        def done(r, err):
            self._loading = False
            if not self.alive:
                return
            if err is not None:
                if getattr(err, "status", None) == 404:
                    self._loaded_at = time.time()
                    return self._show_closed()             # 옛 서버 · 아직 안 연 시즌 (머리말)
                # 불러온 때를 적지 않는다 - 탭을 다시 고르면 바로 다시 묻는다 (배틀타워 탭과 같다)
                return self._show_error("불러오지 못했습니다. %s" % getattr(err, "message", err))
            self._loaded_at = time.time()
            self.closed = False
            self.data = r or {}
            self._ends_at = time.time() + max(0, int(self.data.get("endsIn") or 0))
            self.say("")
            self._paint()
            self._schedule_tick()
        run_async(self.root, lambda: self.app.api.fish_board("this"), done)

    def on_shown(self):
        """허브에서 이 탭을 다시 골랐다. 불러온 지 오래면 다시 불러온다 (그사이 누가 더 큰 것을 낚았을 수 있다)."""
        if self.alive and not self._loading and time.time() - self._loaded_at > STALE_SEC:
            self.reload()

    def _show_error(self, text):
        """불러오지 못했다. 그려 둔 기록이 있으면 그대로 두고 아래 줄에만 알린다 - 없으면 몸통에 까닭을 적는다."""
        self.say(text, U.RED)
        if self.data is not None or self.closed:
            return
        self._clear()
        tk.Label(self.inner, text=text, bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, justify="left",
                 wraplength=U.wide(W) - 80).pack(pady=(24, 4))
        tk.Label(self.inner, text="새로 고침을 누르면 다시 불러옵니다.", bg=U.BG, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack()
        self._fit()

    def _show_closed(self):
        self.closed = True
        self.data = None
        self._ends_at = None
        self.say("")
        self._paint()

    # ---------------- 탭 ----------------
    def pick(self, key):
        if key == self.tab:
            return
        self.tab = key
        self.seg.set(key)
        self._paint()

    def _paint(self):
        self._clear()
        d = self.data
        if self.closed or d is None:
            self.week.configure(text="")
            self.ends.configure(text="")
            if self.closed:
                self._closed_box()
            return self._fit()
        # 지난주 탭은 지난주 날짜를 적고 '끝나기까지' 는 지운다 (실제 앱 시험 11/27 - 이번 주 머리말이 남아 있었다)
        last = self.tab == "last"
        self.week.configure(text=week_text(d.get("week"), back=1 if last else 0))
        if last:
            self.ends.configure(text="")
        else:
            self._paint_ends()
        {"this": self._paint_this, "last": self._paint_last, "mine": self._paint_mine}[self.tab](d)
        self._fit()
        self._fetch_sprites()

    def _closed_box(self):
        box = tk.Frame(self.inner, bg=U.BG2, highlightthickness=2, highlightbackground=U.LINE)
        box.pack(fill="x", pady=(8, 0), padx=(0, 4))
        tk.Label(box, text=CLOSED_TEXT % FROM_DEFAULT, bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY, U.BASE_PT + 2, "bold"), anchor="w").pack(fill="x", padx=16, pady=(14, 2))
        tk.Label(box, text="바탕화면 연못에 찌를 던져 두면 가끔 입질이 와요. 낚아서 잡은 포켓몬의 크기로 "
                           "매주 대물 순위를 겨뤄요.",
                 bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left",
                 wraplength=U.wide(W) - 80).pack(fill="x", padx=16, pady=(0, 14))

    def _paint_this(self, d):
        top, me = d.get("top") or [], d.get("me")
        my_rank = (me or {}).get("rank")
        inside = bool(me) and any(r.get("rank") == my_rank for r in top)
        if not top and not me:
            self._empty("이번 주에는 아직 낚아서 잡은 사람이 없어요.\n연못에 찌를 던져 첫 기록을 남겨 보세요.")
        else:
            t = self._table(RANK_COLS)
            gi = 1
            for r in top:
                self._row(t, gi, RANK_COLS, "top", r, mine=bool(me) and r.get("rank") == my_rank)
                gi += 1
            if me and not inside:
                self._band(t, gi, len(RANK_COLS), "내 자리")
                self._row(t, gi + 1, RANK_COLS, "me", me, mine=True)
            elif not me:
                tk.Label(self.inner, text="이번 주에 낚아서 잡은 포켓몬이 아직 없어요 - 잡으면 여기에 내 자리가 보여요.",
                         bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w").pack(fill="x", pady=(8, 0))
        note = tk.Label(self.inner, text=RULES, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w",
                        justify="left", wraplength=U.wide(W) - 80)
        note.pack(fill="x", pady=(12, 4))
        U.wrap_to_width(note)

    def _paint_last(self, d):
        rows = d.get("last") or []
        span = week_text(d.get("week"), back=1)
        if not rows:
            return self._empty("지난주에는 낚시 기록이 없어요.")
        tk.Label(self.inner, text="지난주 1~3위" + ("  ·  %s" % span if span else ""), bg=U.BG, fg=U.FG_DIM,
                 font=U.FONT_S, anchor="w").pack(fill="x", pady=(0, 6))
        t = self._table(RANK_COLS)
        for gi, r in enumerate(rows[:3], 1):
            self._row(t, gi, RANK_COLS, "last", r)

    def _paint_mine(self, d):
        rows = d.get("mine") or []
        if not rows:
            return self._empty("아직 낚아서 잡은 포켓몬이 없어요.\n잡으면 종마다 가장 큰 기록이 여기에 남아요.")
        tk.Label(self.inner, text="낚아 본 종마다 가장 큰 것 (모든 주)", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                 anchor="w").pack(fill="x", pady=(0, 6))
        t = self._table(MINE_COLS)
        for gi, r in enumerate(rows, 1):
            self._row(t, gi, MINE_COLS, "mine", r)

    def _empty(self, text):
        tk.Label(self.inner, text=text, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S, justify="center").pack(pady=36)

    # ---------------- 표 ----------------
    def _table(self, cols):
        """머리글 한 줄을 단 표. 줄은 grid 로 칸을 맞춘다 (줄마다 Frame 이면 칸 폭이 줄마다 달라진다)."""
        t = tk.Frame(self.inner, bg=U.BG)
        t.pack(fill="x", padx=(0, 4))
        for ci, (_k, title, px, anchor) in enumerate(cols):
            t.columnconfigure(ci, minsize=U.h(px) if px else 0, weight=0 if px else 1)
            tk.Label(t, text=title, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor=anchor,
                     padx=U.h(6)).grid(row=0, column=ci, sticky="nsew", pady=(0, 4))
        return t

    def _row(self, t, gi, cols, kind, r, mine=False):
        bg = MINE_BG if mine else ROW_BG
        ratio = r.get("ratio")
        b = fish_text.badge(ratio)
        hot = {"huge": HUGE_FG, "big": U.ACCENT}.get(b)
        cells = {}
        for ci, (key, _title, _px, anchor) in enumerate(cols):
            if key == "pic":
                box = tk.Frame(t, bg=bg, width=U.h(THUMB), height=U.h(THUMB))
                box.grid(row=gi, column=ci, sticky="nsew", pady=(0, 1))
                pic = tk.Label(box, bg=bg, bd=0, padx=0, pady=0, highlightthickness=0)
                pic.place(relx=0.5, rely=0.5, anchor="center")
                self.pics.append((pic, r.get("num"), bool(r.get("shiny"))))
                cells[key] = pic
                continue
            if key == "name":
                f = tk.Frame(t, bg=bg)
                f.grid(row=gi, column=ci, sticky="nsew", pady=(0, 1))
                tk.Label(f, text=r.get("kr") or r.get("species") or "?", bg=bg, fg=U.FG,
                         font=U.FONT_B).pack(side="left", padx=(U.h(6), 0))
                if r.get("shiny"):
                    tk.Label(f, text="★", bg=bg, fg=U.SHINY, font=U.FONT_S).pack(side="left", padx=(3, 0))
                if b:
                    U.chip(f, fish_text.BADGE_KR[b], hot, fg=U.ACCENT_DARK, font=U.FONT_XS, padx=5,
                           pady=0).pack(side="left", padx=(6, 0))
                cells[key] = f
                continue
            if key == "rank":
                text, fg, font = str(r.get("rank") or ""), MEDAL.get(r.get("rank"), U.FG_DIM), U.FONT_B
            elif key == "kg":
                text, fg, font = fish_text.kg_text(r.get("g")), hot or U.FG, U.FONT_B if hot else U.FONT_S
            elif key == "ratio":
                text, fg, font = fish_text.ratio_text(ratio), hot or U.FG_DIM, U.FONT_S
            elif key == "who":
                text, fg, font = r.get("name") or "", U.ACCENT_TEXT if mine else U.FG_DIM, U.FONT_S
            else:                                           # at
                text, fg, font = day_text(r.get("at")), U.FG_FAINT, U.FONT_XS
            lb = tk.Label(t, text=text, bg=bg, fg=fg, font=font, anchor=anchor, padx=U.h(6))
            lb.grid(row=gi, column=ci, sticky="nsew", pady=(0, 1))
            cells[key] = lb
        self.rows.append({"kind": kind, "data": r, "cells": cells, "mine": mine})

    def _band(self, t, gi, ncols, text):
        """30줄과 내 줄 사이의 띠 (─── 내 자리 ───)."""
        f = tk.Frame(t, bg=U.BG)
        f.grid(row=gi, column=0, columnspan=ncols, sticky="ew", pady=(U.h(8), U.h(4)))
        tk.Frame(f, bg=U.LINE2, height=1).pack(side="left", fill="x", expand=True)
        tk.Label(f, text=text, bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS, padx=8).pack(side="left")
        tk.Frame(f, bg=U.LINE2, height=1).pack(side="left", fill="x", expand=True)

    # ---------------- 도트 ----------------
    def _fetch_sprites(self):
        """보이는 줄의 도트를 붙인다. 이미 받은 것은 바로, 없는 것만 작업 스레드에서 받는다."""
        self._put_sprites()
        want = sorted(set((n, s) for _lb, n, s in self.pics
                          if n and (n, s) not in self.photos and (n, s) not in self._pending))
        if not want:
            return
        self._pending.update(want)
        api = self.app.api
        size = U.h(THUMB) - 4

        def work():
            out = {}
            for n, s in want:
                try:
                    out[(n, s)] = thumb(api, n, s, size)
                except Exception:                           # noqa: BLE001
                    out[(n, s)] = None                       # 못 받아도 줄은 그대로다
            return out

        def done(out, err):
            self._pending.difference_update(want)
            if not self.alive or err or not out:
                return
            for k, img in out.items():
                if img is not None and k not in self.photos:
                    try:
                        self.photos[k] = ImageTk.PhotoImage(img)
                    except tk.TclError:
                        pass
            self._put_sprites()
        run_async(self.root, work, done)

    def _put_sprites(self):
        for lb, n, s in self.pics:
            ph = self.photos.get((n, s))
            if ph is None:
                continue
            try:
                lb.configure(image=ph)
            except tk.TclError:
                pass

    # ---------------- 남은 시간 ----------------
    def _paint_ends(self):
        if self._ends_at is None or self.tab == "last":
            return
        try:
            self.ends.configure(text=ends_text(self._ends_at - time.time()))
        except tk.TclError:
            pass

    def _tick(self):
        """띄워 둔 동안 '끝나기까지' 를 고쳐 적는다. 주가 끝났으면 다시 불러온다 (지난주 1~3위가 바뀐다)."""
        self._cancel_tick()
        if not self.alive:
            return
        self._paint_ends()
        if self._ends_at is not None and time.time() >= self._ends_at and not self._loading \
                and time.time() - self._loaded_at > STALE_SEC:
            self.reload()
        self._schedule_tick()

    def _schedule_tick(self):
        if self._tick_job is None and self.alive:
            try:
                self._tick_job = self.win.after(TICK_MS, self._tick)
            except tk.TclError:
                pass

    def _cancel_tick(self):
        job, self._tick_job = self._tick_job, None
        if job is not None:
            try:
                self.win.after_cancel(job)
            except tk.TclError:
                pass

    # ---------------- 끝 ----------------
    def focus(self):
        try:
            if not U.is_embedded(self.win):
                self.win.deiconify()
                self.win.lift()
                self.win.focus_force()
        except tk.TclError:
            pass

    def close(self):
        self.alive = False
        self._cancel_tick()
        if getattr(self.app, "fish_records", None) is self:
            self.app.fish_records = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
