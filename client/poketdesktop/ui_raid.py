# -*- coding: utf-8 -*-
"""레이드 — 일정과 로비.

정해진 시각에만 열린다. 이 화면이 하는 일은 셋이다.

  1. 다음 회차가 언제이고 무엇이 나오는지 (보스는 **1시간 전에 공개**된다)
  2. 모이는 시간이면 참가 — 아무나와 함께(자동 매칭) 또는 방 코드로
  3. 로비에서 사람이 차는 것을 보여주고, 판이 열리면 배틀 창으로 넘긴다

판정은 전부 서버가 한다. 여기서는 참가 조건(오늘 이미 했나, 포켓몬을
몇 마리 데리고 있나)도 **서버가 보내준 값**으로만 말한다 - 화면에서 다시
따지면 서버 판정과 어긋난다.

로비에 있는 동안만 2초마다 방을 물어본다. 평소 동기화(90초)는 그대로다.
"""
import datetime
import json
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from common.korean import natural

from . import sprite_cache, sprites
from . import ui_common as U
from .ui_common import run_async

W, H = 900, 680

LOBBY_POLL_MS = 2000        # 로비에서 방을 물어보는 주기
IDLE_POLL_MS = 15000        # 모이는 시간이 가까울 때 일정만 다시 보는 주기

KIND_KR = {"legendary": "전설", "mythical": "환상"}
RESULT_KR = {"won": ("성공", U.GOOD), "lost": ("실패", U.DANGER),
             "timeout": ("시간 초과", U.DANGER), "cancelled": ("취소", U.FG_DIM),
             "expired": ("취소", U.FG_DIM)}


# 시간이 흘러서 저절로 바뀌는 값들. **그림의 모양을 바꾸지 않으므로**
# 다시 그릴지 따질 때는 뺀다 (남은 시간은 시계가 따로 1초마다 적는다).
TICKING = ("leftSec", "startsIn", "deadlineIn", "rev", "unseen", "updated_at")


def shape_of(d):
    """이 자료로 그린 화면의 모양. 이게 같으면 다시 그릴 것이 없다.

    로비에서는 2초마다 방을 물어보는데, 예전에는 그때마다 화면을 통째로
    지우고 다시 그렸다(_clear). 그래서 아무도 안 들어와도 2초에 한 번씩
    **눈에 띄게 깜빡였고**, 보스 도트 라벨도 매번 새로 만들어졌다.
    """
    def strip(o):
        if isinstance(o, dict):
            return dict((k, strip(v)) for k, v in o.items() if k not in TICKING)
        if isinstance(o, list):
            return [strip(v) for v in o]
        return o
    try:
        return json.dumps(strip(d or {}), sort_keys=True, ensure_ascii=False,
                          default=str)
    except (TypeError, ValueError):
        return None


def next_edge(left, d):
    """다음 회차까지 left 초 남았을 때, 몇 초 뒤에 다시 불러야 하나.

    화면이 바뀌는 경계 셋: 보스 공개(revealSec 전) · 모집 시작(openSec 전) ·
    정각. 이미 지난 경계는 뺀다. 30분보다 멀면 30분 뒤에 한 번 본다 -
    창을 며칠 켜 두어도 일정이 어긋나지 않게.
    """
    if left <= 0:
        return None
    edges = [d.get("openSec") or 300, 0]
    if not (d.get("next") or {}).get("revealed"):
        edges.append(d.get("revealSec") or 3600)
    waits = [left - e for e in edges if left - e > 0]
    if not waits:
        return None
    return min(min(waits), 1800)


def hms(sec):
    """남은 시간을 사람 말로. 첫 회차까지 며칠 남았을 수도 있다."""
    sec = max(0, int(sec))
    if sec >= 86400:
        return "%d일 %d시간" % (sec // 86400, (sec % 86400) // 3600)
    if sec >= 3600:
        return "%d시간 %d분" % (sec // 3600, (sec % 3600) // 60)
    if sec >= 60:
        return "%d분 %d초" % (sec // 60, sec % 60)
    return "%d초" % sec


def when(iso):
    """2026-09-22T11:00:00 -> 9월 22일(화) 11시. 서버가 한국시간으로 준다."""
    try:
        dt = datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    days = "월화수목금토일"
    return "%d월 %d일(%s) %d시" % (dt.month, dt.day, days[dt.weekday()], dt.hour)


class RaidWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.alive = True
        self.data = None
        self.photos = {}
        self.jobs = []
        self._busy = False
        self._poll_job = None     # 다음 불러오기 예약 (늘 하나)
        self._shape = None        # 지금 그려 둔 화면의 모양 (shape_of)
        self._left = 0            # 다음 회차까지 남은 초 (받은 순간 기준)
        self._left_at = 0.0
        self.win = U.panel(parent, app.root, "레이드", W, H,
                           minw=760, minh=560, on_close=self.close)
        self.win.configure(bg=U.BG)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)
        self._header()
        # 내용이 창보다 길다 (보스 카드 + 참가 + 규칙 + 다음 회차 + 기록).
        # 굴러가는 칸에 담는다 - 글자를 줄이거나 항목을 빼는 대신.
        self.status = U.status_line(self.win, "불러오는 중...", U.FG_DIM)
        self.status.pack(side="bottom", fill="x")
        holder = tk.Frame(self.win, bg=U.BG)
        holder.pack(fill="both", expand=True)
        self.cv = tk.Canvas(holder, bg=U.BG, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.cv, bg=U.BG)
        self._wid = self.cv.create_window((0, 0), window=self.body, anchor="nw")
        self.fit = U.scroll_fitter(self.cv, self.body, self._wid)
        U.scrollable(self.cv, 60)
        self.reload()
        self._countdown()

    # ---------------- 머리 ----------------
    def _header(self):
        """다른 탭(친구·대전·가방·도감·랭크)과 같은 머리줄. **새로고침이 없었다.**

        레이드 탭만 머리줄이 없어서, 화면이 멈춘 것 같을 때 할 수 있는 게
        탭을 닫았다 다시 여는 것뿐이었다.
        """
        h = tk.Frame(self.win, bg=U.BG2, height=U.h(62))
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)
        tk.Label(inner, text="레이드", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(15))).pack(side="left")
        self.refresh_btn = U.ghost_button(inner, "새로고침",
                                          self.refresh, height=32)
        # **위아래 여백(pady)을 주지 않는다.** 머리줄 높이는 정해져 있고 pack 이
        # 알아서 세로 가운데에 둔다. 다른 탭처럼 pady=15 를 주면 단추(32 +
        # 그림자 4)에 30 을 더해 66 을 달라는데, 윈도우(배율 1.0)의 머리줄은
        # 62 라 단추가 4px 눌렸다. 맥은 머리줄이 74 라 안 보였다.
        self.refresh_btn.pack(side="right")
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

    # ---------------- 틀 ----------------
    def later(self, ms, fn):
        if not self.alive:
            return None
        j = self.root.after(ms, lambda: self.alive and fn())
        self.jobs.append(j)
        return j

    def _poll_later(self, ms):
        """다음 불러오기를 **하나만** 예약한다.

        예전에는 불러올 때마다 이전 예약을 두고 새로 걸어서, 로비에서
        참가·시작을 누르거나 새로고침을 누를 때마다 2초짜리 폴링이 한 줄씩
        늘었다. 열 번 누르면 2초에 열 번 서버를 두드린다.
        """
        if self._poll_job is not None:
            try:
                self.root.after_cancel(self._poll_job)
            except Exception:                               # noqa: BLE001
                pass
            if self._poll_job in self.jobs:
                self.jobs.remove(self._poll_job)
        self._poll_job = self.later(ms, lambda: self.reload(True))
        return self._poll_job

    def say(self, text, color=U.FG_DIM):
        if self.alive:
            U.set_status(self.status, natural(text or ""), color)

    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    # ---------------- 받아오기 ----------------
    def refresh(self):
        """사람이 새로고침을 눌렀다. 바뀐 게 없어도 한 번은 다시 그린다 -
        눌렀는데 아무 일도 안 일어나면 먹통으로 보인다."""
        self._shape = None
        self.reload()

    def reload(self, quiet=False):
        if not self.alive or self._busy:
            return
        self._busy = True
        if not quiet:
            self.say("불러오는 중...")

        def done(r, err):
            self._busy = False
            if not self.alive:
                return
            if err:
                self.say(getattr(err, "message", str(err)), U.DANGER)
                return self._poll_later(5000)
            self.data = r
            self._left = int(((r.get("next") or {}).get("leftSec")) or 0)
            self._left_at = _now()
            # **바뀐 것이 없으면 다시 그리지 않는다.** 남은 시간은 시계가
            # 따로 적고, 그 값은 모양 열쇠에서 빠져 있다.
            shape = shape_of(r)
            if shape is None or shape != self._shape or not self.body.winfo_children():
                self._shape = shape
                self.render()
            else:
                self._paint_clock()
            self._schedule_poll()
        run_async(self.root, lambda: self.app.api.raid(), done)

    def _schedule_poll(self):
        room = (self.data or {}).get("room")
        if room and room.get("state") == "lobby":
            return self._poll_later(LOBBY_POLL_MS)
        if room and room.get("state") == "fighting":
            return self._to_battle(room)
        # 모이는 시간이 가까우면 조금 자주 본다. **모이기 시작하는 순간을
        # 넘기면 안 된다** - 4분 전에 창을 열어 둔 사람의 화면에 '참가하기'
        # 가 저절로 떠야 한다 (안 그러면 탭을 다시 눌러야 나온다).
        left = self._remaining()
        d = self.data or {}
        if d.get("open") or 0 < left <= (d.get("openSec") or 300) + 60:
            return self._poll_later(IDLE_POLL_MS)
        # **멀리 있어도 경계에서는 다시 부른다.** 예전에는 모집 6분 전 안쪽에서
        # 연 탭만 저절로 바뀌었다. 한 시간 전에 열어 두면 시계만 줄다가 "곧
        # 시작" 에서 멈추고, 보스 공개(1시간 전)도 '참가하기' 도 안 떴다 -
        # 탭을 닫았다 다시 열어야 했다.
        wait = next_edge(left, d)
        if wait is not None:
            self._poll_later(int(wait * 1000) + 1500)

    def _remaining(self):
        return max(0, self._left - int(_now() - self._left_at))

    # ---------------- 그리기 ----------------
    def render(self):
        self._clear()
        d = self.data or {}
        if not d.get("on"):
            return self._off(d)
        room = d.get("room")
        head = tk.Frame(self.body, bg=U.BG)
        head.pack(fill="x", padx=16, pady=(14, 6))
        self._boss_card(head, d)
        if room:
            self._lobby(d, room)
        else:
            self._join_box(d)
        self._rules(d)
        self._upcoming(d)
        hours = ["%d시" % h for h in d.get("hours") or []]
        self.say("레이드는 하루 %d번, %s에 열립니다. 기간은 %s ~ %s 입니다."
                 % (len(hours), "와 ".join(hours), d.get("start", ""),
                    d.get("end", "")), U.FG_DIM)

    def _off(self, d):
        """아직(또는 이미) 기간이 아닐 때.

        **언제 열리는지를 말해 준다.** 전에는 "기간이 아닙니다" 한 줄이라,
        시작 전에 받아 본 사람은 무엇을 기다려야 하는지 알 수가 없었다.
        """
        card = d.get("next") or {}
        soon = bool(card.get("at"))
        box = U.framed(self.body, bg=U.BG2, border=U.ACCENT if soon else U.LINE)
        box.pack(fill="x", padx=16, pady=(16, 0))
        inner = tk.Frame(box, bg=U.BG2)
        inner.pack(fill="x", padx=16, pady=14)
        tk.Label(inner, text="전설·환상 레이드" if soon else "레이드 기간이 아닙니다",
                 bg=U.BG2, fg=U.FG, font=U.FONT_H, anchor="w").pack(anchor="w")
        if soon:
            row = tk.Frame(inner, bg=U.BG2)
            row.pack(fill="x", pady=(6, 0))
            tk.Label(row, text="첫 회차", bg=U.BG2, fg=U.ACCENT, font=U.FONT_XS,
                     anchor="w").pack(side="left")
            tk.Label(row, text=when(card.get("at")), bg=U.BG2, fg=U.FG,
                     font=(U.FAMILY_BLACK, U.pt(16)), anchor="w").pack(
                side="left", padx=(8, 0))
            self.clock = tk.Label(row, text="", bg=U.BG2, fg=U.ACCENT,
                                  font=U.FONT_B, anchor="e")
            self.clock.pack(side="right")
            self._paint_clock()
        lab = tk.Label(inner, bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                       justify="left",
                       text="%s ~ %s, 매일 %s에 열립니다. 무엇이 나올지는 회차 시작 "
                            "1시간 전에 공개됩니다."
                            % (d.get("start", ""), d.get("end", ""),
                               "와 ".join("%d시" % h for h in d.get("hours") or [])))
        lab.pack(fill="x", pady=(8, 0))
        U.wrap_to_width(lab)
        if soon:
            self._rules(d)
        self._history()

    def _boss_card(self, parent, d):
        card = d.get("next") or {}
        box = U.framed(parent, bg=U.BG2)
        box.pack(fill="x")
        row = tk.Frame(box, bg=U.BG2)
        row.pack(fill="x", padx=16, pady=14)
        slot = tk.Frame(row, bg=U.BG2, width=U.h(110), height=U.h(110))
        slot.pack(side="left")
        slot.pack_propagate(False)
        art = tk.Label(slot, bg=U.BG2, bd=0)
        art.pack(expand=True)
        txt = tk.Frame(row, bg=U.BG2)
        txt.pack(side="left", fill="both", expand=True, padx=(14, 0))
        if card.get("revealed") and card.get("kr"):
            kind = KIND_KR.get(card.get("kind"), "전설")
            tk.Label(txt, text="%s의 포켓몬 · Lv.%d" % (kind, card.get("level") or 0),
                     bg=U.BG2, fg=U.ACCENT, font=U.FONT_XS, anchor="w").pack(anchor="w")
            tk.Label(txt, text=card["kr"], bg=U.BG2, fg=U.FG,
                     font=(U.FAMILY_BLACK, U.pt(22))).pack(anchor="w")
            tp = tk.Frame(txt, bg=U.BG2)
            tp.pack(anchor="w", pady=(4, 0))
            for name, tid in zip(card.get("types") or [], card.get("typeIds") or []):
                U.chip(tp, name, U.TYPE_COLOR.get(tid, U.BG3)).pack(side="left", padx=(0, 4))
            self._boss_art(art, card.get("num"))
        else:
            tk.Label(txt, text="???", bg=U.BG2, fg=U.FG_FAINT,
                     font=(U.FAMILY_BLACK, U.pt(22))).pack(anchor="w")
            lab = tk.Label(txt, bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                           justify="left",
                           text="무엇이 나올지는 회차 시작 1시간 전에 공개됩니다.")
            lab.pack(fill="x", pady=(4, 0))
            U.wrap_to_width(lab)
            art.configure(text="?", fg=U.FG_FAINT, font=(U.FAMILY_BLACK, U.pt(34)))
        right = tk.Frame(row, bg=U.BG2)
        right.pack(side="right", fill="y")
        tk.Label(right, text=when(card.get("at")), bg=U.BG2, fg=U.FG_DIM,
                 font=U.FONT_XS, anchor="e").pack(anchor="e")
        self.clock = tk.Label(right, text="", bg=U.BG2, fg=U.ACCENT,
                              font=(U.FAMILY_BLACK, U.pt(18)), anchor="e")
        self.clock.pack(anchor="e")
        self._paint_clock()

    def _boss_art(self, label, num):
        if not num:
            return
        key = "b%s" % num
        if key in self.photos:
            return label.configure(image=self.photos[key])

        def work():
            path = sprite_cache.ensure(self.app.api, num, False)
            if not path:
                return None
            anim = sprites.load_animation(path, U.h(100), 0.2, 4.0, max_frames=1,
                                          max_size=(U.h(108), U.h(100)))
            return sprites.to_rgba(anim.frames[sprites.LEFT][0], anim.key)

        def done(img, err):
            if not self.alive or err or img is None:
                return
            ph = ImageTk.PhotoImage(img)
            self.photos[key] = ph
            try:
                label.configure(image=ph)
            except tk.TclError:
                pass
        run_async(self.root, work, done)

    def _paint_clock(self):
        if not self.alive or not hasattr(self, "clock"):
            return
        left = self._remaining()
        d = self.data or {}
        try:
            if d.get("open"):
                self.clock.configure(text="모이는 중", fg=U.GOOD)
            elif left <= 0:
                self.clock.configure(text="곧 시작", fg=U.ACCENT)
            else:
                self.clock.configure(text="%s 뒤" % hms(left), fg=U.ACCENT)
        except tk.TclError:
            pass

    # ---------------- 참가 ----------------
    def _join_box(self, d):
        box = U.framed(self.body, bg=U.BG2)
        box.pack(fill="x", padx=16, pady=(10, 0))
        inner = tk.Frame(box, bg=U.BG2)
        inner.pack(fill="x", padx=16, pady=14)
        why = self._why_not(d)
        if why:
            lab = tk.Label(inner, text=why, bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S,
                           anchor="w", justify="left")
            lab.pack(fill="x")
            U.wrap_to_width(lab)
            return
        tk.Label(inner, text="지금 모이는 중입니다", bg=U.BG2, fg=U.FG,
                 font=U.FONT_H, anchor="w").pack(anchor="w")
        lab = tk.Label(inner, bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                       justify="left",
                       text="%d~%d명이 모이면 방장이 시작합니다. 정각이 지나도 방은 "
                            "그대로 있고, 시작하기 전까지는 오늘 참가 횟수에 "
                            "들어가지 않습니다."
                            % (d.get("minPlayers", 3), d.get("maxPlayers", 6))
                       )
        lab.pack(fill="x", pady=(4, 10))
        U.wrap_to_width(lab)
        btns = tk.Frame(inner, bg=U.BG2)
        btns.pack(fill="x")
        U.PushButton(btns, "참가하기", self.join, height=U.h(40)).pack(side="left")
        U.ghost_button(btns, "방 만들기", self.create, height=U.h(40)).pack(
            side="left", padx=(8, 0))
        code = tk.Frame(btns, bg=U.BG2)
        code.pack(side="right")
        self.code_var = tk.StringVar()
        U.entry(code, self.code_var, width=8).pack(side="left")
        U.ghost_button(code, "코드로 참가", self.join_code, height=U.h(40)).pack(
            side="left", padx=(6, 0))

    def _why_not(self, d):
        """지금 못 들어가는 이유. 들어갈 수 있으면 None."""
        if d.get("playedToday"):
            return "오늘은 이미 레이드에 참가했습니다. 다음 날 다시 도전할 수 있습니다."
        if (d.get("party") or 0) < d.get("minParty", 2):
            return ("포켓몬을 %d마리 이상 데리고 다녀야 참가할 수 있습니다. "
                    "포켓몬 관리 탭에서 바탕화면에 올려 주세요."
                    % d.get("minParty", 2))
        if not d.get("open"):
            card = d.get("next") or {}
            if not card:
                return "남은 회차가 없습니다."
            return ("%s 에 열립니다. 시작 %d분 전부터 참가할 수 있습니다."
                    % (when(card.get("at")), (d.get("openSec") or 300) // 60))
        return None

    # ---------------- 로비 ----------------
    def _lobby(self, d, room):
        box = U.framed(self.body, bg=U.BG2, border=U.ACCENT)
        box.pack(fill="x", padx=16, pady=(10, 0))
        inner = tk.Frame(box, bg=U.BG2)
        inner.pack(fill="x", padx=16, pady=14)
        top = tk.Frame(inner, bg=U.BG2)
        top.pack(fill="x")
        tk.Label(top, text="사람을 기다리는 중", bg=U.BG2, fg=U.FG,
                 font=U.FONT_H).pack(side="left")
        tk.Label(top, text="%d / %d명" % (room.get("count", 0), room.get("max", 6)),
                 bg=U.BG2, fg=U.ACCENT, font=U.FONT_B).pack(side="right")
        if room.get("code"):
            cc = tk.Frame(inner, bg=U.BG2)
            cc.pack(fill="x", pady=(8, 0))
            tk.Label(cc, text="방 코드", bg=U.BG2, fg=U.FG_DIM,
                     font=U.FONT_XS).pack(side="left")
            tk.Label(cc, text=room["code"], bg=U.BG2, fg=U.ACCENT,
                     font=(U.FAMILY_BLACK, U.pt(16))).pack(side="left", padx=(8, 0))
            U.ghost_button(cc, "복사", lambda: self._copy(room["code"]),
                           height=28).pack(side="left", padx=(8, 0))
        seats = tk.Frame(inner, bg=U.BG2)
        seats.pack(fill="x", pady=(10, 0))
        here = [m for m in room.get("members") or [] if not m.get("left")]
        for i in range(room.get("max", 6)):
            m = here[i] if i < len(here) else None
            cell = tk.Frame(seats, bg=U.BG3 if m else U.INK, highlightthickness=1,
                            highlightbackground=U.ACCENT if m else U.LINE)
            cell.grid(row=0, column=i, sticky="nsew", padx=3)
            tk.Label(cell, text=(m or {}).get("name") or "비었음",
                     bg=U.BG3 if m else U.INK,
                     fg=U.FG if m else U.FG_FAINT, font=U.FONT_S,
                     padx=8, pady=8).pack()
        for i in range(room.get("max", 6)):
            seats.grid_columnconfigure(i, weight=1, uniform="seat")
        # 시작은 **방장이 누른다.** 정각이 지나도 방은 그대로 있으므로,
        # 다 모여서 준비가 끝났을 때 누르면 된다.
        if room.get("isHost"):
            msg = ("다 모였습니다. '레이드 시작' 을 누르면 바로 들어갑니다."
                   if room.get("canStart")
                   else "%s 창을 닫아도 자리는 남습니다." % (room.get("startNote") or ""))
        else:
            msg = ("방장이 시작하기를 기다리는 중입니다. 창을 닫아도 자리는 남습니다."
                   if room.get("canStart") is not None and len(here) >= room.get("min", 3)
                   else "%d명이 모이면 방장이 시작합니다. 창을 닫아도 자리는 남습니다."
                        % room.get("min", 3))
        note = tk.Label(inner, bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                        justify="left", text=msg)
        note.pack(fill="x", pady=(10, 8))
        U.wrap_to_width(note)
        btns = tk.Frame(inner, bg=U.BG2)
        btns.pack(fill="x")
        if room.get("isHost"):
            b = U.PushButton(btns, "레이드 시작", self.start, height=U.h(38))
            b.pack(side="left")
            if not room.get("canStart"):
                b.configure(state="disabled")
        U.ghost_button(btns, "나가기", self.leave, height=U.h(38)).pack(side="right")

    def _copy(self, text):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.say("방 코드를 복사했습니다: %s" % text, U.GOOD)
        except tk.TclError:
            pass

    # ---------------- 규칙 · 다음 회차 · 기록 ----------------
    def _rules(self, d):
        box = tk.Frame(self.body, bg=U.BG)
        box.pack(fill="x", padx=16, pady=(12, 0))
        rows = [
            ("인원", "%d~%d명" % (d.get("minPlayers", 3), d.get("maxPlayers", 6))),
            ("레벨", "전원 Lv.%d 로 맞춰서 싸웁니다 (개체값·노력치·기술은 그대로)"
                     % d.get("teamLevel", 50)),
            ("보스", "Lv.%d%s · 인원수만큼 체력이 늘어납니다"
                     % (d.get("bossLevel", 60),
                        (" · 능력마다 노력치 %d" % d["bossEv"]) if d.get("bossEv")
                        else "")),
            ("제한", "%d라운드 안에 쓰러뜨려야 합니다 (한 라운드 %d초)"
                     % (d.get("rounds", 15), d.get("roundSec", 25))),
            ("보상", "성공하면 %d%% 확률로 **그 보스의 알**. 횟수 제한은 없지만 하루 한 번입니다."
                     % int(round((d.get("eggChance") or 0.7) * 100))),
        ]
        for i, (k, v) in enumerate(rows):
            r = tk.Frame(box, bg=U.BG)
            r.pack(fill="x", pady=1)
            tk.Label(r, text=k, bg=U.BG, fg=U.ACCENT, font=U.FONT_XS,
                     width=6, anchor="w").pack(side="left")
            lab = tk.Label(r, text=v.replace("**", ""), bg=U.BG, fg=U.FG_DIM,
                           font=U.FONT_XS, anchor="w", justify="left")
            lab.pack(side="left", fill="x", expand=True)
            U.wrap_to_width(lab)

    def _upcoming(self, d):
        rows = d.get("upcoming") or []
        if not rows:
            return
        box = tk.Frame(self.body, bg=U.BG)
        box.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(box, text="다음 회차", bg=U.BG, fg=U.FG, font=U.FONT_B,
                 anchor="w").pack(anchor="w", pady=(0, 4))
        grid = tk.Frame(box, bg=U.BG)
        grid.pack(fill="x")
        for i, c in enumerate(rows[:6]):
            cell = tk.Frame(grid, bg=U.BG2, highlightthickness=1,
                            highlightbackground=U.LINE)
            cell.grid(row=i // 3, column=i % 3, sticky="nsew", padx=3, pady=3)
            tk.Label(cell, text=when(c.get("at")), bg=U.BG2, fg=U.FG,
                     font=U.FONT_S, anchor="w").pack(anchor="w", padx=10, pady=(6, 0))
            tk.Label(cell, text=(c.get("kr") or "??? (1시간 전 공개)"), bg=U.BG2,
                     fg=U.ACCENT if c.get("kr") else U.FG_FAINT, font=U.FONT_XS,
                     anchor="w").pack(anchor="w", padx=10, pady=(0, 6))
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1, uniform="up")
        self._history()

    def _history(self):
        box = tk.Frame(self.body, bg=U.BG)
        box.pack(fill="x", padx=16, pady=(12, 12))
        tk.Label(box, text="내 레이드 기록", bg=U.BG, fg=U.FG, font=U.FONT_B,
                 anchor="w").pack(anchor="w", pady=(0, 4))
        holder = tk.Frame(box, bg=U.BG)
        holder.pack(fill="x")

        def done(r, err):
            if not self.alive or err:
                return
            rows = (r or {}).get("raids") or []
            if not rows:
                return tk.Label(holder, text="아직 참가한 레이드가 없습니다.", bg=U.BG,
                                fg=U.FG_FAINT, font=U.FONT_XS, anchor="w").pack(anchor="w")
            for x in rows[:6]:
                line = tk.Frame(holder, bg=U.BG)
                line.pack(fill="x", pady=1)
                text, color = RESULT_KR.get(x.get("result"), ("끝", U.FG_DIM))
                tk.Label(line, text=text, bg=U.BG, fg=color, font=U.FONT_XS,
                         width=7, anchor="w").pack(side="left")
                tk.Label(line, text=x.get("kr") or x.get("boss") or "", bg=U.BG,
                         fg=U.FG, font=U.FONT_XS, width=10, anchor="w").pack(side="left")
                bits = []
                if x.get("egg"):
                    bits.append("알 획득")
                if x.get("damage"):
                    bits.append("기여 %s" % format(x["damage"], ","))
                if x.get("prize"):
                    bits.append("%s원" % format(x["prize"], ","))
                tk.Label(line, text="  ·  ".join(bits), bg=U.BG, fg=U.FG_DIM,
                         font=U.FONT_XS, anchor="w").pack(side="left")
        run_async(self.root, lambda: self.app.api.raid_history(6), done)
        self._past()

    def _past(self):
        """지난 회차 — **내가 안 간 판도 보인다.** 어떤 전설이 나왔는지 궁금해한다."""
        box = tk.Frame(self.body, bg=U.BG)
        box.pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(box, text="지난 회차", bg=U.BG, fg=U.FG, font=U.FONT_B,
                 anchor="w").pack(anchor="w", pady=(0, 4))
        holder = tk.Frame(box, bg=U.BG)
        holder.pack(fill="x")

        def done(r, err):
            if not self.alive or err:
                return
            rows = (r or {}).get("raids") or []
            if not rows:
                return tk.Label(holder, text="아직 지나간 회차가 없습니다.", bg=U.BG,
                                fg=U.FG_FAINT, font=U.FONT_XS,
                                anchor="w").pack(anchor="w")
            for x in rows[:8]:
                line = tk.Frame(holder, bg=U.BG)
                line.pack(fill="x", pady=1)
                tk.Label(line, text=when(x.get("at")), bg=U.BG, fg=U.FG_DIM,
                         font=U.FONT_XS, width=15, anchor="w").pack(side="left")
                tk.Label(line, text=x.get("kr") or x.get("boss") or "", bg=U.BG,
                         fg=U.ACCENT, font=U.FONT_XS, width=10,
                         anchor="w").pack(side="left")
                bits = ["·".join(x.get("types") or [])]
                tk.Label(line, text="  ·  ".join(b for b in bits if b),
                         bg=U.BG, fg=U.FG_DIM,
                         font=U.FONT_XS, anchor="w").pack(side="left")
        run_async(self.root, lambda: self.app.api.raid_past(8), done)

    # ---------------- 동작 ----------------
    def _send(self, fn, ok_text=""):
        if self._busy:
            return
        self._busy = True
        self.say("...")

        def done(r, err):
            self._busy = False
            if not self.alive:
                return
            if err:
                self.say(getattr(err, "message", str(err)), U.DANGER)
                return self.reload(True)
            if ok_text:
                self.say(ok_text, U.GOOD)
            self.reload(True)
        run_async(self.root, fn, done)

    def join(self):
        self._send(lambda: self.app.api.raid_join(), "방에 들어갔습니다.")

    def join_code(self):
        code = (self.code_var.get() or "").strip().upper()
        if not code:
            return self.say("방 코드를 입력하세요.", U.DANGER)
        self._send(lambda: self.app.api.raid_join(code), "방에 들어갔습니다.")

    def create(self):
        self._send(lambda: self.app.api.raid_create(), "방을 만들었습니다.")

    def start(self):
        self._send(lambda: self.app.api.raid_start(), "레이드를 시작합니다!")

    def leave(self):
        from .ui_box import confirm
        if not confirm(self.win if not U.is_embedded(self.win) else self.root,
                       "나가기", "이 방에서 나갈까요?", danger=True, ok_text="나가기"):
            return
        self._send(lambda: self.app.api.raid_leave(), "방에서 나왔습니다.")

    def _to_battle(self, room):
        """판이 열렸다. 배틀 창으로 넘긴다."""
        opener = getattr(self.app, "open_raid_battle", None)
        if opener is None:
            return
        try:
            opener(room)
        except Exception:                                   # noqa: BLE001
            from . import config
            import traceback
            config.log("레이드 창을 못 열었습니다:\n%s" % traceback.format_exc())

    def _countdown(self):
        self._paint_clock()
        self.later(1000, self._countdown)

    def close(self):
        if not self.alive:
            return
        self.alive = False
        for j in self.jobs:
            try:
                self.root.after_cancel(j)
            except Exception:                               # noqa: BLE001
                pass
        self.jobs = []
        if not U.is_embedded(self.win):
            try:
                self.win.destroy()
            except Exception:                               # noqa: BLE001
                pass
        if getattr(self.app, "raid_window", None) is self:
            self.app.raid_window = None


def _now():
    import time
    return time.time()
