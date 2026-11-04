# -*- coding: utf-8 -*-
"""포켓몬과 집중하기 — 시작 창과 집중 창, 오른쪽 클릭 메뉴 줄.

    open_focus(app, pet=None)   집중 중이면 집중 창(FocusPanel), 아니면 시작 창(FocusStartWindow)
    menu_row(app, pet)          포켓몬 오른쪽 클릭 메뉴에 넣을 줄 (없으면 None)

시작 창: 능력 여섯 줄(동작 · 능력 · 지금 노력치 x / 252) 중 하나를 고르고 '시작'. 아래에 합계 y / 510 과
오늘 받은 노력치 z / 40. 노력치가 꽉 찬 능력이나 오늘 40 을 다 받은 날도 고를 수 있다 - "기록만 남아요" 라고
미리 알린다 (설계 '내 판단'). 서버가 거절하면(놀러 가기 중 등) 그 문구를 창에 띄우고 창은 남는다.

집중 창: 이번 세트 남은 시간(1초마다) · 이번 집중 세트 수 · 오늘 노력치, '집중 끝내기' (한 번 묻는다 -
진행 중인 세트는 노력치를 못 받는다).

노력치는 바탕화면 포켓몬의 정보(mon["info"]["evs"])를 쓴다 - 동기화마다 서버가 실어 준다.
"""
import tkinter as tk

from PIL import ImageTk

from common import focus as F

from . import ui_box
from . import ui_common as U
from .focus_act import prop_image
from .ui_common import run_async

ASK = None                   # 확인 창 (검사가 바꿔 끼운다). None 이면 ui_box.confirm
OLD_SERVER_MSG = "서버 업데이트 뒤에 쓸 수 있어요."
END_ASK = "지금 끝내면 진행 중인 세트는 노력치를 못 받아요. 끝낼까요?"
INTRO = ("25분마다 고른 능력의 노력치가 5 오릅니다. '집중 끝내기' 를 누를 때까지 세트가 이어지고, "
         "하루에 40 까지 받습니다. 집중하는 동안은 이 포켓몬만 바탕화면에 남고 풀숲이 쉬어요.")
STAT_MAX, TOTAL_MAX = 252, 510


def _ask(*a, **kw):
    return (ASK or ui_box.confirm)(*a, **kw)


def _err_text(err):
    if getattr(err, "status", 0) == 404:
        return OLD_SERVER_MSG
    return getattr(err, "message", None) or str(err)


def _name(pet):
    info = (pet.mon or {}).get("info") or {}
    return "%s  Lv.%s" % (info.get("name", "?"), info.get("level", "?"))


def menu_row(app, pet):
    """오른쪽 클릭 메뉴 줄. 내 포켓몬이고 놀러 가기 중이 아닐 때만. 집중 중이면 집중 포켓몬에만 '끝내기'."""
    f = getattr(app, "focus", None)
    if f is None or not hasattr(f, "pet_id") or (getattr(pet, "id", 0) or 0) <= 0:
        return None          # (App 메서드를 빌려 쓰는 검사의 가짜 앱 - 집중 기능이 없다)
    v = getattr(app, "visit", None)
    if v is not None and getattr(v, "active", False):
        return None
    if f.active():
        if pet.id == f.pet_id:
            return {"text": "집중 끝내기...", "command": lambda: open_focus(app, pet)}
        return None
    return {"text": "같이 집중하기...", "command": lambda: open_focus(app, pet)}


def open_focus(app, pet=None):
    old = getattr(app, "focus_window", None)
    want_panel = bool(app.focus is not None and app.focus.active())
    if old is not None and old.alive():
        if isinstance(old, FocusPanel) == want_panel and (want_panel or pet is None or old.pet is pet):
            old.lift()
            return old
        old.close()
    w = FocusPanel(app) if want_panel else FocusStartWindow(app, pet)
    app.focus_window = w
    return w


class _Window(object):
    def refit(self, later=True):
        """창 높이를 내용에 맞춘다. 줄바꿈하는 글(wrap_to_width)은 처음 그린 뒤에야 높이가 정해지므로
        한 번 더 늦게 맞춘다 - 안 그러면 아래 단추 줄이 눌린다 (Feedback: 창은 내용만큼)."""
        if not self.alive():
            return
        try:
            self.win.update_idletasks()
            ui_box.fit(self.win, keep_pos=True)
        except Exception:                                   # noqa: BLE001
            pass
        if later:
            self.root.after(80, lambda: self.refit(later=False))

    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except Exception:                                   # noqa: BLE001
            return False

    def lift(self):
        try:
            self.win.deiconify()
            self.win.lift()
        except Exception:                                   # noqa: BLE001
            pass

    def close(self):
        if self.alive():
            try:
                self.win.destroy()
            except Exception:                               # noqa: BLE001
                pass
        if getattr(self.app, "focus_window", None) is self:
            self.app.focus_window = None


class FocusStartWindow(_Window):
    W = 420

    def __init__(self, app, pet=None):
        self.app, self.root = app, app.root
        self.pet = pet or self._first()
        self.today = None
        self.rows = {}
        self._labels = {}
        self._icons = []
        self.win, body = ui_box._shell(app.root, "포켓몬과 집중하기", self.W, U.h(440))
        self.head = tk.Label(body, text="", bg=U.BG, fg=U.FG, font=U.FONT_B, anchor="w")
        self.head.pack(fill="x")
        self._pet_row(body)
        intro = tk.Label(body, text=INTRO, bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS, justify="left", anchor="w")
        intro.pack(fill="x", pady=(4, 10))
        U.wrap_to_width(intro)
        box = tk.Frame(body, bg=U.BG)
        box.pack(fill="x")
        for stat, act, kr in F.ACTS:
            self._row(box, stat, act, kr)
        self.sum = tk.Label(body, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left")
        self.sum.pack(fill="x", pady=(10, 0))
        self.warn = tk.Label(body, text="", bg=U.BG, fg=U.ACCENT, font=U.FONT_XS, anchor="w", justify="left")
        self.warn.pack(fill="x")
        U.wrap_to_width(self.warn)
        self.err = tk.Label(body, text="", bg=U.BG, fg=U.DANGER, font=U.FONT_XS, anchor="w", justify="left")
        self.err.pack(fill="x", pady=(2, 0))
        U.wrap_to_width(self.err)
        bar = tk.Frame(body, bg=U.BG)
        bar.pack(fill="x", pady=(12, 0))
        self.go_btn = U.PushButton(bar, "시작", self.go, height=34, font=U.FONT_B)
        self.go_btn.pack(side="right")
        U.ghost_button(bar, "닫기", self.close, height=34).pack(side="right", padx=(0, 8))
        self.stat = self._default_stat()
        self._paint()
        ui_box.fit(self.win)
        self.refit()
        run_async(self.root, lambda: app.api.focus_state(), self._state)

    # ---------------- 자료
    def _desk_pets(self):
        ov = getattr(self.app, "overlay", None)
        if ov is None:
            return []
        pets = [p for p in ov.pets.values() if (p.id or 0) > 0]
        return sorted(pets, key=lambda p: (p.mon.get("slot") is None, p.mon.get("slot") or 0, p.id))

    def _first(self):
        pets = self._desk_pets()
        return pets[0] if pets else None

    def _evs(self):
        info = ((self.pet.mon if self.pet else {}) or {}).get("info") or {}
        evs = dict((s, int((info.get("evs") or {}).get(s, 0))) for s, _a, _k in F.ACTS)
        total = int(info.get("evTotal", sum(evs.values())))
        return evs, total

    def _default_stat(self):
        evs, total = self._evs()
        for stat, _a, _k in F.ACTS:
            if evs[stat] < STAT_MAX and total < TOTAL_MAX:
                return stat
        return F.ACTS[0][0]

    def _state(self, r, err):
        if not self.alive():
            return
        if err:
            self.err.configure(text=_err_text(err))
            return self.refit()
        self.today = int((r or {}).get("todayEv", 0))
        self._paint()
        self.refit()

    # ---------------- 그리기
    def _pet_row(self, body):
        pets = self._desk_pets()
        self.pet_btns = {}
        if len(pets) < 2:
            return
        row = tk.Frame(body, bg=U.BG)
        row.pack(fill="x", pady=(6, 0))
        for p in pets:
            info = (p.mon or {}).get("info") or {}
            b = tk.Label(row, text=info.get("name", "?"), bg=U.BG4, fg=U.FG, font=U.FONT_XS, padx=8, pady=2,
                         cursor="hand2")
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-1>", lambda _e, p=p: self.choose(p))
            self.pet_btns[p.id] = b

    def _row(self, box, stat, act, kr):
        row = tk.Frame(box, bg=U.BG2, highlightthickness=1, highlightbackground=U.LINE, cursor="hand2")
        row.pack(fill="x", pady=2)
        img = ImageTk.PhotoImage(prop_image(stat, max(14, int(U.h(18)))))
        self._icons.append(img)
        icon = tk.Label(row, image=img, bg=U.BG2)
        icon.pack(side="left", padx=(10, 6), pady=6)
        name = tk.Label(row, text="%s  (%s)" % (act, kr), bg=U.BG2, fg=U.FG, font=U.FONT_S, anchor="w")
        name.pack(side="left")
        ev = tk.Label(row, text="", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S)
        ev.pack(side="right", padx=(6, 10))
        note = tk.Label(row, text="", bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS)
        note.pack(side="right")
        for w in (row, icon, name, ev, note):
            w.bind("<Button-1>", lambda _e, s=stat: self.pick(s))
        self.rows[stat] = row
        self._labels[stat] = (icon, name, ev, note)

    def _paint(self):
        if self.pet is None:
            self.head.configure(text="바탕화면에 데리고 다니는 포켓몬이 없어요")
            self.go_btn_state(False)
            return
        self.head.configure(text=_name(self.pet))
        for pid, b in getattr(self, "pet_btns", {}).items():
            on = pid == self.pet.id
            b.configure(bg=U.ACCENT if on else U.BG4, fg=U.ACCENT_DARK if on else U.FG)
        evs, total = self._evs()
        for stat, _a, _k in F.ACTS:
            row = self.rows[stat]
            on = stat == self.stat
            bg = U.BG4 if on else U.BG2
            row.configure(bg=bg, highlightbackground=U.ACCENT if on else U.LINE)
            icon, name, ev, note = self._labels[stat]
            for w in (icon, name, ev, note):
                w.configure(bg=bg)
            ev.configure(text="%d / %d" % (evs[stat], STAT_MAX))
            full = evs[stat] >= STAT_MAX or total >= TOTAL_MAX
            note.configure(text="꽉 참 · 기록만 남아요" if full else "")
        today = "…" if self.today is None else "%d / %d" % (self.today, F.DAILY_EV)
        self.sum.configure(text="노력치 합계 %d / %d  ·  오늘 받은 집중 노력치 %s" % (total, TOTAL_MAX, today))
        if self.today is not None and self.today >= F.DAILY_EV:
            self.warn.configure(text="오늘 받을 노력치는 다 받았어요 — 집중하면 시간만 기록돼요 (기록만 남아요).")
        else:
            self.warn.configure(text="")
        self.go_btn_state(True)

    def go_btn_state(self, on):
        try:
            self.go_btn.configure(state="normal" if on else "disabled")
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------- 고르기 · 시작
    def pick(self, stat):
        self.stat = stat
        self._paint()

    def choose(self, pet):
        self.pet = pet
        self.stat = self._default_stat()
        self._paint()

    def go(self):
        if self.pet is None:
            return
        self.err.configure(text="")
        self.app.focus.start(self.pet.id, self.stat, done=self._started)

    def _started(self, r, err):
        if not self.alive():
            return
        if err:
            self.err.configure(text=err if isinstance(err, str) else _err_text(err))
            return self.refit()
        self.close()


class FocusPanel(_Window):
    W = 380

    def __init__(self, app):
        self.app, self.root = app, app.root
        self.pet = None
        f = app.focus
        v = f.view or {}
        self.win, body = ui_box._shell(app.root, "포켓몬과 집중하기", self.W, U.h(260))
        act = "%s (%s)" % (v.get("act", "?"), v.get("statKr", "?"))
        who = (v.get("pokemon") or {}).get("name", "?")
        tk.Label(body, text="%s · %s" % (who, act), bg=U.BG, fg=U.FG, font=U.FONT_B, anchor="w").pack(fill="x")
        self.left_lb = tk.Label(body, text="", bg=U.BG, fg=U.ACCENT, font=U.FONT_B, anchor="w")
        self.left_lb.pack(fill="x", pady=(8, 0))
        self.info_lb = tk.Label(body, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left")
        self.info_lb.pack(fill="x", pady=(2, 0))
        note = tk.Label(body, text="세트는 '집중 끝내기' 를 누를 때까지 저절로 이어져요. 게임을 끄거나 컴퓨터가 "
                                   "잠들면 그때 진행 중이던 세트는 인정되지 않아요.",
                        bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left")
        note.pack(fill="x", pady=(8, 0))
        U.wrap_to_width(note)
        self.err = tk.Label(body, text="", bg=U.BG, fg=U.DANGER, font=U.FONT_XS, anchor="w", justify="left")
        self.err.pack(fill="x")
        bar = tk.Frame(body, bg=U.BG)
        bar.pack(fill="x", pady=(12, 0))
        U.danger_button(bar, "집중 끝내기", self.end, height=34).pack(side="right")
        U.ghost_button(bar, "닫기", self.close, height=34).pack(side="right", padx=(0, 8))
        self._job = None
        self._tick()
        ui_box.fit(self.win)
        self.refit()

    def _tick(self):
        self._job = None
        if not self.alive():
            return
        f = self.app.focus
        if not f.active():
            return self.close()
        v = f.view or {}
        self.left_lb.configure(text="이번 세트 남은 시간  %s" % f.left_text())
        self.info_lb.configure(text="이번 집중 %d세트  ·  오늘 노력치 %d / %d"
                               % (int(v.get("sets", 0)), int(v.get("todayEv", 0)), int(v.get("dailyEv", F.DAILY_EV))))
        self._job = self.root.after(1000, self._tick)

    def end(self):
        if not _ask(self.win, "집중 끝내기", END_ASK, danger=False, ok_text="끝내기"):
            return
        self.app.focus.stop(done=self._ended)

    def _ended(self, r, err):
        if err and self.alive():
            self.err.configure(text=err if isinstance(err, str) else _err_text(err))
            return
        self.close()

    def close(self):
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None
        _Window.close(self)
