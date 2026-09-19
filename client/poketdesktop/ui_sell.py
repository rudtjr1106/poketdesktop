# -*- coding: utf-8 -*-
"""여러 도구를 한 번에 파는 창.

가방은 한 번에 한 개씩만 팔았다. 별가루가 서른 개 쌓이면 서른 번을 눌러야
하고, 그때마다 "되돌릴 수 없습니다" 를 확인해야 했다.

여기서는 팔 수 있는 것을 한 줄씩 늘어놓고, 줄마다 몇 개를 팔지 정한다.
합계를 아래에 계속 적어 두고, 한 번만 확인하면 서버에 **한 번** 보낸다
(/api/shop/sell-many - 다 되거나 아무것도 안 되거나).

## 무엇을 못 팔게 하나

  · 값이 없는 물건 (기술머신처럼 팔 수 없는 것)
  · 몬스터볼 — 이게 없으면 게임이 안 돌아간다 (가방의 '팔기' 와 같은 규칙)

## 고르는 법

숫자 칸을 직접 고치게 하면 키보드를 오가야 한다. `-` 와 `+`, 그리고 '전부'
로 정한다. 줄을 누르면 하나 올라간다 - 몇 개씩만 파는 것이 흔해서다.
"""
import tkinter as tk

from common.korean import natural

from . import item_icons
from . import ui_common as U
from . import ui_loading
from .ui_bag import _scroller

W, H = 520, 620
ROW_H = 44
KEEP = ("POKEBALL",)     # 이건 안 판다 (가방의 팔기와 같다)


def won(n):
    try:
        return "{:,}".format(int(n))
    except (TypeError, ValueError):
        return str(n)


def sellable(items, bag):
    """가방에 있고 값이 붙은 것만. 비싼 것부터 (팔 만한 것이 위로)."""
    out = []
    for it in items or []:
        have = int((bag or {}).get(it["id"], 0))
        price = int(it.get("sell") or 0)
        if have > 0 and price > 0 and it["id"] not in KEEP:
            out.append((it, have, price))
    out.sort(key=lambda x: (-x[2] * x[1], x[0]["kr"]))
    return out


class SellMany(object):
    """고른 것을 (도구, 개수) 목록으로 돌려준다. 그만두면 None."""

    def __init__(self, parent, root, items, bag, money=0):
        self.root = root
        self.result = None
        self.rows = {}           # 도구 id -> (틀, 개수 라벨, 있는 수, 값)
        self.pick = {}           # 도구 id -> 팔 개수
        self.lines = sellable(items, bag)
        self.money = int(money or 0)

        self.win = tk.Toplevel(parent)
        U.style_window(self.win, "여러 개 팔기", W, H)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        self.parent = parent

        bar = tk.Frame(self.win, bg=U.BG2, height=U.h(34))
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=U.ACCENT, width=3, height=U.h(13)).pack(side="left",
                                                                 padx=(12, 8))
        tk.Label(bar, text="여러 개 팔기", bg=U.BG2, fg=U.FG,
                 font=U.FONT_B).pack(side="left")
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

        f = tk.Frame(self.win, bg=U.BG)
        f.pack(fill="both", expand=True, padx=16, pady=(12, 12))
        tk.Label(f, text="팔 물건과 개수를 고르세요. 판 물건은 되돌릴 수 없습니다.",
                 bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, anchor="w").pack(fill="x")

        # 단추를 먼저 담는다 (굴러가는 칸이 자리를 다 먹지 않게 - ui_learn 과 같다).
        foot = tk.Frame(f, bg=U.BG)
        foot.pack(side="bottom", fill="x", pady=(12, 0))
        self.ok_btn = U.PushButton(foot, "팔기", self._ok, height=34, font=U.FONT_B)
        self.ok_btn.pack(side="right")
        U.ghost_button(foot, "닫기", self._cancel, height=34).pack(side="right",
                                                                 padx=(0, 8))
        self.total = tk.Label(foot, text="", bg=U.BG, fg=U.FG, font=U.FONT_B,
                              anchor="w", justify="left")
        self.total.pack(side="left", fill="x", expand=True)

        head = tk.Frame(f, bg=U.BG)
        head.pack(fill="x", pady=(10, 4))
        U.ghost_button(head, "전부 고르기", self._all, height=28).pack(side="left")
        U.ghost_button(head, "고른 것 지우기", self._none, height=28).pack(
            side="left", padx=(8, 0))
        self.hint = tk.Label(head, text="", bg=U.BG, fg=U.FG_FAINT,
                             font=U.FONT_XS, anchor="e")
        self.hint.pack(side="right")

        self.canvas, self.box = _scroller(f, U.BG)
        U.scrollable(self.canvas, 60)
        U.install_wheel(self.win)
        if self.lines:
            for it, have, price in self.lines:
                self._row(it, have, price)
        else:
            tk.Label(self.box, text="팔 수 있는 물건이 없습니다.",
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S).pack(anchor="w",
                                                                 pady=10)
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self._paint()

    # ---------------- 그리기 ----------------
    def _row(self, it, have, price):
        f = tk.Frame(self.box, bg=U.BG2, height=U.h(ROW_H),
                     highlightthickness=1, highlightbackground=U.LINE)
        f.pack(fill="x", pady=2)
        f.pack_propagate(False)

        ph = item_icons.photo(it["id"], 20)
        if ph is not None:
            icon = tk.Label(f, image=ph, bg=U.BG2, bd=0)
            icon.image = ph
            icon.pack(side="left", padx=(10, 6))
        name = tk.Label(f, text=it["kr"], bg=U.BG2, fg=U.FG, font=U.FONT_S,
                        anchor="w")
        name.pack(side="left")
        note = tk.Label(f, text="%d개 있음 · 개당 %s원" % (have, won(price)),
                        bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w")
        note.pack(side="left", padx=(8, 0))

        U.ghost_button(f, "전부", (lambda i=it["id"]: self._set(i, None)),
                       height=26).pack(side="right", padx=(6, 10))
        U.ghost_button(f, "+", (lambda i=it["id"]: self._add(i, 1)),
                       height=26).pack(side="right")
        cnt = tk.Label(f, text="0", bg=U.BG2, fg=U.FG, font=U.FONT_B, width=4)
        cnt.pack(side="right", padx=2)
        U.ghost_button(f, "−", (lambda i=it["id"]: self._add(i, -1)),
                       height=26).pack(side="right")

        # 줄을 누르면 하나씩 올라간다. 몇 개만 파는 일이 흔하다.
        for w in (f, name, note):
            w.bind("<Button-1>", lambda _e, i=it["id"]: self._add(i, 1))
        self.rows[it["id"]] = (f, cnt, have, price)

    def _paint(self):
        total, pieces = 0, 0
        for iid, n in self.pick.items():
            _f, _c, _have, price = self.rows[iid]
            total += price * n
            pieces += n
        for iid, (f, cnt, _have, _price) in self.rows.items():
            n = self.pick.get(iid, 0)
            cnt.configure(text=str(n), fg=U.ACCENT_TEXT if n else U.FG_FAINT)
            f.configure(highlightbackground=U.ACCENT if n else U.LINE)
        if pieces:
            self.total.configure(
                text="%d가지 %d개  ·  %s원" % (len(self.pick), pieces, won(total)),
                fg=U.ACCENT_TEXT)
        else:
            self.total.configure(text="고른 것이 없습니다.", fg=U.FG_DIM)
        self.hint.configure(text="가진 돈 %s원" % won(self.money))
        self.ok_btn.configure(text="팔기" if not pieces else "%s원에 팔기" % won(total))

    # ---------------- 고르기 ----------------
    def _add(self, iid, d):
        got = self.rows.get(iid)
        if not got:
            return
        have = got[2]
        n = max(0, min(have, self.pick.get(iid, 0) + d))
        self._put(iid, n)

    def _set(self, iid, n):
        got = self.rows.get(iid)
        if not got:
            return
        self._put(iid, got[2] if n is None else max(0, min(got[2], n)))

    def _put(self, iid, n):
        if n <= 0:
            self.pick.pop(iid, None)
        else:
            self.pick[iid] = n
        self._paint()

    def _all(self):
        for iid, (_f, _c, have, _p) in self.rows.items():
            self.pick[iid] = have
        self._paint()

    def _none(self):
        self.pick.clear()
        self._paint()

    # ---------------- 답 ----------------
    def _ok(self):
        if not self.pick:
            self.total.configure(text="팔 물건을 골라 주세요.", fg=U.ACCENT)
            return
        self.result = [{"item": i, "count": n} for i, n in sorted(self.pick.items())]
        self.win.destroy()

    def _cancel(self):
        self.result = None
        self.win.destroy()

    def show(self):
        try:
            self.win.transient(self.parent.winfo_toplevel())
        except tk.TclError:
            pass
        self.win.lift()
        try:
            self.win.focus_force()
        except tk.TclError:
            pass
        self.parent.wait_window(self.win)
        return self.result


def ask_sell_many(parent, root, items, bag, money=0):
    """고른 것을 [{"item", "count"}] 로 돌려준다. 그만두면 None."""
    return SellMany(parent, root, items, bag, money).show()


def summary(lines, items):
    """확인 창에 보여줄 글. '별가루 30개, 진주 2개 · 합계 12,300원'."""
    by = dict((i["id"], i) for i in items or [])
    bits, total = [], 0
    for line in lines:
        it = by.get(line["item"]) or {"kr": line["item"], "sell": 0}
        bits.append("%s %d개" % (it["kr"], line["count"]))
        total += int(it.get("sell") or 0) * int(line["count"])
    return natural("%s 을(를) 팔아 %s원을 받습니다. 되돌릴 수 없습니다."
                   % (", ".join(bits), won(total)))
