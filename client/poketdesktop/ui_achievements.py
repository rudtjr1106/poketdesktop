# -*- coding: utf-8 -*-
"""도감 업적 (시즌 3) — 달성 알림 창과 도감 탭의 업적 칸.

## 알림

**운영체제 알림은 쓰지 않는다.** 게임 안의 일이라서다(app.toast 의 규칙).
선물과 같은 작은 창으로, 배틀·진화 연출이 끝난 뒤에 띄운다. 여럿이면 한
창에 묶는다 - 처음 켠 사람은 쌓인 기록으로 열 몇 개가 한꺼번에 달성된다.

## 업적 칸

도감 탭 머리의 '업적' 단추로 격자와 번갈아 본다. 갈래마다 묶고, 줄마다
진행 막대와 보상(칭호·볼)을 적는다. 숨은 업적은 서버가 이름을 가려 보낸다.
"""
import tkinter as tk
from tkinter import ttk

from common.korean import natural

from . import ui_common as U
from .ui_common import run_async

PANEL = "#101623"
BAR_BG = "#1b2233"
MAX_LINES = 8           # 알림 창에 이만큼만 적고 나머지는 '그 밖 N개'
BULK = 4                # 이보다 많으면 '지금까지의 기록으로' 로 묶는다


def reward_text(a):
    """보상 한 줄. 칭호가 먼저다."""
    if a.get("title"):
        return "칭호 「%s」" % a["title"]
    if a.get("balls"):
        return "몬스터볼 %d개" % a["balls"]
    return ""


def announce(parent, app, items):
    """업적 달성 창. 여럿이면 한 창에 모은다."""
    if not items:
        return
    from . import ui_box
    n = len(items)
    height = U.h(230) + min(n, MAX_LINES) * U.h(40)
    win, f = ui_box._shell(parent, "업적", 440, height)

    head = ("지금까지의 기록으로 업적 %d개를 달성했습니다" % n if n >= BULK
            else "업적 달성!")
    tk.Label(f, text=head, bg=U.BG, fg=U.ACCENT_TEXT, wraplength=390,
             justify="left", font=(U.FAMILY_BLACK, U.pt(17))).pack(anchor="w")

    box = tk.Frame(f, bg=PANEL, highlightthickness=2, highlightbackground=U.LINE)
    box.pack(fill="x", pady=(12, 0))
    inner = tk.Frame(box, bg=PANEL)
    inner.pack(fill="x", padx=14, pady=10)
    for a in items[:MAX_LINES]:
        row = tk.Frame(inner, bg=PANEL)
        row.pack(fill="x", pady=2)
        tk.Label(row, text="★", bg=PANEL, fg=U.ACCENT, font=U.FONT_B).pack(side="left")
        tk.Label(row, text=a.get("name", ""), bg=PANEL, fg=U.FG,
                 font=U.FONT_B).pack(side="left", padx=(6, 0))
        rw = reward_text(a)
        if rw:
            tk.Label(row, text=rw, bg=PANEL, fg=U.FG_DIM,
                     font=U.FONT_XS).pack(side="right")
    if n > MAX_LINES:
        tk.Label(inner, text="그 밖 %d개" % (n - MAX_LINES), bg=PANEL,
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(anchor="w", pady=(4, 0))

    bits = []
    if any(a.get("title") for a in items):
        bits.append("칭호는 랭킹 탭에서 달 수 있습니다.")
    if any(a.get("balls") for a in items):
        bits.append("몬스터볼은 가방에 넣어 두었습니다.")
    bits.append("모든 업적은 도감 탭의 '업적' 에서 봅니다.")
    tk.Label(f, text=" ".join(bits), bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
             wraplength=390, justify="left").pack(anchor="w", pady=(10, 0))

    row = tk.Frame(f, bg=U.BG)
    row.pack(fill="x", pady=(14, 0))
    U.PushButton(row, "확인", win.destroy, height=34, font=U.FONT_B).pack(side="right")

    # 다 담고 나서 창을 내용에 맞춘다 (선물 창과 같은 까닭 - 글꼴이 OS 마다
    # 달라서 줄 수로만 잡으면 모자란다. 글자를 줄이지 않고 칸을 늘린다).
    try:
        win.update_idletasks()
        need = win.winfo_reqheight()
        if need > win.winfo_height():
            win.geometry("%dx%d" % (win.winfo_width() or 440, need))
    except Exception:                                      # noqa: BLE001
        pass
    win.grab_set()
    parent.wait_window(win)


class AchievementPanel(object):
    """도감 탭 안의 업적 칸. 격자 자리에 들어간다."""

    def __init__(self, parent, app, on_count=None):
        self.app = app
        self.root = app.root
        self.on_count = on_count      # (달성, 전체) 를 머리줄에 알린다
        self.alive = True
        self.data = None
        self.f = tk.Frame(parent, bg=U.BG)
        top = tk.Frame(self.f, bg=U.BG)
        top.pack(fill="x", padx=14, pady=(10, 4))
        self.summary = tk.Label(top, text="불러오는 중...", bg=U.BG, fg=U.FG,
                                font=U.FONT_B, anchor="w")
        self.summary.pack(side="left")
        self.unlock = tk.Label(top, text="", bg=U.BG, fg=U.FG_DIM,
                               font=U.FONT_XS, anchor="e")
        self.unlock.pack(side="right")
        wrap = tk.Frame(self.f, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        self.cv = tk.Canvas(wrap, bg=U.BG, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.cv, bg=U.BG)
        wid = self.cv.create_window((0, 0), window=self.body, anchor="nw")
        self.fit = U.scroll_fitter(self.cv, self.body, wid)
        U.scrollable(self.cv, 60)

    def pack(self, **kw):
        self.f.pack(**kw)

    def pack_forget(self):
        self.f.pack_forget()

    def reload(self):
        def done(r, err):
            if not self.alive:
                return
            if err:
                self.summary.configure(text=getattr(err, "message", str(err)),
                                       fg=U.DANGER)
                return
            self.data = r or {}
            self.draw()
        run_async(self.root, lambda: self.app.api.achievements(), done)

    def draw(self):
        for w in self.body.winfo_children():
            w.destroy()
        d = self.data or {}
        items = d.get("achievements") or []
        done, total = d.get("done", 0), d.get("total", len(items))
        self.summary.configure(text="달성 %d / %d" % (done, total), fg=U.FG)
        if self.on_count:
            self.on_count(done, total)
        ul = d.get("unlocks") or {}
        opened = [name for key, name in (("unlock_7", "울트라홀"),
                                          ("unlock_9", "패러독스")) if ul.get(key)]
        self.unlock.configure(
            text=("열림: " + " · ".join(opened)) if opened
            else "해금 업적을 달성하면 새 포켓몬이 나타납니다")
        groups = []
        for a in items:
            if a["group"] not in groups:
                groups.append(a["group"])
        for g in groups:
            rows = [a for a in items if a["group"] == g]
            n_done = sum(1 for a in rows if a.get("gotAt"))
            head = tk.Frame(self.body, bg=U.BG)
            head.pack(fill="x", pady=(10, 4))
            U.marker_label(head, "%s  %d/%d" % (g, n_done, len(rows)),
                           bg=U.BG).pack(side="left")
            for a in rows:
                self._row(a)
        self.fit.schedule()

    def _row(self, a):
        got = bool(a.get("gotAt"))
        bg = "#182033" if got else PANEL
        row = tk.Frame(self.body, bg=bg, highlightthickness=1,
                       highlightbackground=U.ACCENT if got else U.LINE)
        row.pack(fill="x", pady=2)
        inner = tk.Frame(row, bg=bg)
        inner.pack(fill="x", padx=12, pady=7)
        top = tk.Frame(inner, bg=bg)
        top.pack(fill="x")
        tk.Label(top, text=("★ " if got else "") + a.get("name", ""), bg=bg,
                 fg=U.ACCENT_TEXT if got else U.FG, font=U.FONT_B).pack(side="left")
        rw = reward_text(a)
        if rw:
            tk.Label(top, text=rw, bg=bg, fg=U.ACCENT if got else U.FG_FAINT,
                     font=U.FONT_XS).pack(side="right")
        desc = tk.Label(inner, text=natural(a.get("desc", "")), bg=bg,
                        fg=U.FG_DIM, font=U.FONT_XS, anchor="w", justify="left")
        desc.pack(fill="x")
        U.wrap_to_width(desc)
        if got:
            when = (a.get("gotAt") or "")[:10]
            tk.Label(inner, text="%s 달성" % when, bg=bg, fg=U.GOOD,
                     font=U.FONT_XS, anchor="w").pack(fill="x")
        elif "value" in a:
            self._bar(inner, bg, a["value"], a["target"])

    def _bar(self, parent, bg, value, target):
        line = tk.Frame(parent, bg=bg)
        line.pack(fill="x", pady=(4, 0))
        cv = tk.Canvas(line, height=U.h(8), bg=BAR_BG, highlightthickness=0, bd=0)
        cv.pack(side="left", fill="x", expand=True)
        tk.Label(line, text="%d / %d" % (value, target), bg=bg, fg=U.FG_FAINT,
                 font=U.FONT_XS, width=10, anchor="e").pack(side="right")
        ratio = max(0.0, min(1.0, value / float(target or 1)))

        def paint(_e=None):
            try:
                w = cv.winfo_width()
                cv.delete("fill")
                cv.create_rectangle(0, 0, int(w * ratio), U.h(8), fill=U.ACCENT,
                                    width=0, tags="fill")
            except tk.TclError:
                pass
        cv.bind("<Configure>", paint)

    def close(self):
        self.alive = False
