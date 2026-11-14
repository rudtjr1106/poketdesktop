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

## 판매 제외 (2.1.1, 게시판 #426)

줄마다 [−] 왼쪽의 별(☆/★)을 누르면 그 도구는 '판매 제외' 다. '전부 고르기' 에서 빠지고, 별을 풀기 전에는
+ · 전부 · 줄 누르기도 안 먹는다 (아끼는 도구가 한꺼번에 팔릴까 봐 일일이 확인하던 것). 목록은 앱 설정
sellKeep 에 남는다 - 서버는 모른다 (취향이다).

## 분류 (2.5.0, 게시판 #522)

목록 위의 칩(전체 · 지닌 도구 · 열매 · 폼 도구 · 진화의 돌 …)으로 그 분류만 본다. 가방에 있는 분류만 나온다.
**열매는 따로 뺀다** - 가방의 분류로는 지닌 도구(오랭열매)와 노력치(시몬열매)에 섞여 있다. '전부 고르기' 는
**지금 보이는 분류만** 고른다 (지닌 도구만 정리하려다 다른 것까지 다 고르지 않게). 고른 것과 합계는 분류를
바꿔도 그대로 남는다.
"""
import tkinter as tk
import tkinter.font as tkfont

from common.korean import natural

from . import item_icons
from . import skins
from . import ui_common as U
from . import ui_loading
from .ui_bag import CAT_KR, _scroller

W, H = 520, 620
ROW_H = 44
KEEP = ("POKEBALL",)     # 이건 안 판다 (가방의 팔기와 같다)

# 분류 칩의 차례와 이름 (2.5.0). 가방의 분류(CAT_KR)에 '열매' 를 더한다.
GROUP_ORDER = ["held", "berry", "form", "stone", "megastone", "zcrystal", "ev", "iv", "ball", "misc", "deco"]
GROUP_KR = dict(CAT_KR, berry="열매", all="전체")


def group_of(it):
    """여러 개 팔기의 분류. 열매는 지닌 도구 · 노력치에 섞여 있어서 따로 뺀다. 모르는 분류는 기타."""
    if str(it.get("id") or "").endswith("BERRY"):
        return "berry"
    cat = it.get("cat") or "misc"
    return cat if cat in GROUP_ORDER else "misc"


def groups(lines):
    """칩으로 보일 분류 [(열쇠, 이름)] - 전체 + 목록에 있는 것만 (GROUP_ORDER 차례). 분류가 하나뿐이면 전체만."""
    have = set(group_of(it) for it, _h, _p in lines or [])
    out = [(g, GROUP_KR.get(g, g)) for g in GROUP_ORDER if g in have]
    return [("all", GROUP_KR["all"])] + (out if len(out) > 1 else [])


class _Chips(object):
    """분류 칩 (기본 테마). 창 폭에 맞춰 줄을 바꾼다. 고른 칩은 Segmented 처럼 금색."""

    def __init__(self, parent, items, current, on_pick, width):
        self.frame = tk.Frame(parent, bg=U.BG)
        self.cells = {}
        fnt = tkfont.Font(root=parent, font=U.FONT_XS)
        pad, gap = U.h(10), U.h(6)
        row, used = None, 0
        for key, label in items:
            w = fnt.measure(label) + 2 * pad + gap + 4
            if row is None or used + w > width:
                row = tk.Frame(self.frame, bg=U.BG)
                row.pack(fill="x", pady=(0, U.h(4)))
                used = 0
            lb = tk.Label(row, text=label, font=U.FONT_XS, padx=pad, pady=U.h(2), bd=0)
            lb.pack(side="left", padx=(0, gap))
            lb.bind("<Button-1>", lambda _e, k=key: on_pick(k))
            self.cells[key] = lb
            used += w
        self.set(current)

    def set(self, key):
        for k, lb in self.cells.items():
            on = k == key
            lb.configure(bg=U.ACCENT if on else U.INK, fg=U.ACCENT_DARK if on else U.FG_DIM,
                         cursor="" if on else "hand2")


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


@skins.skinnable
class SellMany(object):
    """고른 것을 (도구, 개수) 목록으로 돌려준다. 그만두면 None."""

    KEEP_TEXT = "★ 를 누르면 판매 제외 - '전부 고르기' 에서 빠지고 못 팝니다."
    KEPT_SAY = "판매 제외한 도구입니다. ★ 를 다시 누르면 팔 수 있습니다."

    def __init__(self, parent, root, items, bag, money=0, keep=None, on_keep=None):
        self.root = root
        self.result = None
        self.rows = {}           # 도구 id -> (틀, 개수 라벨, 있는 수, 값)
        self.pick = {}           # 도구 id -> 팔 개수
        self.keep = set(keep or ())  # 판매 제외 (별표) 도구 id
        self.on_keep = on_keep       # 별을 켜고 끌 때 (판매 제외 집합) - 설정에 적는다
        self.stars = {}              # 도구 id -> 별 라벨 (기본 테마)
        self.lines = sellable(items, bag)
        self.money = int(money or 0)
        self.group = "all"           # 지금 보는 분류 (2.5.0, 게시판 #522)
        self.chips = None

        self.win = tk.Toplevel(parent)
        U.style_window(self.win, "여러 개 팔기", W, H)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        self.parent = parent
        self._build()
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self._paint()

    # ---------------- 그리기 ----------------
    def _build(self):
        """창 안의 것들 (테마마다 짓는 곳): 안내 · 고르기 단추 · 줄들 · 합계 · 팔기 단추.
        self.ok_btn · total · hint · rows 를 둔다 (rows[도구] = (틀, 개수 칸, 있는 수, 값))."""
        U.dialog_bar(self.win, "여러 개 팔기")

        f = tk.Frame(self.win, bg=U.BG)
        f.pack(fill="both", expand=True, padx=16, pady=(12, 12))
        tk.Label(f, text="팔 물건과 개수를 고르세요. 판 물건은 되돌릴 수 없습니다.",
                 bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, anchor="w").pack(fill="x")
        tk.Label(f, text=self.KEEP_TEXT, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS,
                 anchor="w").pack(fill="x")

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

        # 분류 칩 (2.5.0). 분류가 둘 이상일 때만
        items = groups(self.lines)
        if len(items) > 1:
            self.chips = _Chips(f, items, self.group, self.set_group, U.h(W) - U.h(36))
            self.chips.frame.pack(fill="x", pady=(2, 2))

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
        star = tk.Label(f, text="☆", bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_B, cursor="hand2", padx=6)
        star.pack(side="right", padx=(0, 4))
        star.bind("<Button-1>", lambda _e, i=it["id"]: self.toggle_keep(i))
        self.stars[it["id"]] = star

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
            star = self.stars.get(iid)
            if star is not None:
                kept = iid in self.keep
                star.configure(text="★" if kept else "☆", fg=U.ACCENT if kept else U.FG_FAINT)
        if pieces:
            self.total.configure(
                text="%d가지 %d개  ·  %s원" % (len(self.pick), pieces, won(total)),
                fg=U.ACCENT_TEXT)
        else:
            self.total.configure(text="고른 것이 없습니다.", fg=U.FG_DIM)
        self.hint.configure(text="가진 돈 %s원" % won(self.money))
        self.ok_btn.configure(text="팔기" if not pieces else "%s원에 팔기" % won(total))

    # ---------------- 분류 (2.5.0) ----------------
    def visible(self):
        """지금 보이는 도구 id (목록 차례). 전체면 다."""
        return [it["id"] for it, _h, _p in self.lines if self.group == "all" or group_of(it) == self.group]

    def set_group(self, key):
        """그 분류만 본다. 고른 것과 합계는 그대로."""
        if key == self.group:
            return
        self.group = key
        if self.chips is not None:
            self.chips.set(key)
        self._show_group()
        self._paint()

    def _show_group(self):
        """보이는 줄만 담는다 (기본 테마 - 줄 틀을 빼고 다시 담는다). 맨 위로 굴린다."""
        show = set(self.visible())
        for iid, (f, _c, _h, _p) in self.rows.items():
            f.pack_forget()
        for it, _h, _p in self.lines:
            if it["id"] in show:
                self.rows[it["id"]][0].pack(fill="x", pady=2)
        try:
            self.canvas.yview_moveto(0)
        except (tk.TclError, AttributeError):
            pass

    # ---------------- 고르기 ----------------
    def toggle_keep(self, iid):
        """판매 제외 별을 켜고 끈다. 켜면 그 도구는 고른 것에서도 빠진다."""
        if iid not in self.rows:
            return
        if iid in self.keep:
            self.keep.discard(iid)
        else:
            self.keep.add(iid)
            self.pick.pop(iid, None)
        if self.on_keep:
            try:
                self.on_keep(frozenset(self.keep))
            except Exception:                               # noqa: BLE001
                pass
        self._paint()

    def _kept(self, iid):
        """판매 제외면 알리고 True (고르기가 안 먹는다)."""
        if iid in self.keep:
            self.total.configure(text=self.KEPT_SAY, fg=U.ACCENT)
            return True
        return False

    def _add(self, iid, d):
        got = self.rows.get(iid)
        if not got:
            return
        if d > 0 and self._kept(iid):
            return
        have = got[2]
        n = max(0, min(have, self.pick.get(iid, 0) + d))
        self._put(iid, n)

    def _set(self, iid, n):
        got = self.rows.get(iid)
        if not got:
            return
        if (n is None or n > 0) and self._kept(iid):
            return
        self._put(iid, got[2] if n is None else max(0, min(got[2], n)))

    def _put(self, iid, n):
        if n <= 0:
            self.pick.pop(iid, None)
        else:
            self.pick[iid] = n
        self._paint()

    def _all(self):
        """지금 보이는 분류만 다 고른다 (2.5.0 - 전체를 보고 있으면 전부). 판매 제외는 빼고."""
        for iid in self.visible():
            _f, _c, have, _p = self.rows[iid]
            if iid in self.keep:                 # 판매 제외는 빼고
                self.pick.pop(iid, None)
                continue
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


def ask_sell_many(parent, root, items, bag, money=0, keep=None, on_keep=None):
    """고른 것을 [{"item", "count"}] 로 돌려준다. 그만두면 None. keep = 판매 제외 도구 id,
    on_keep(집합) = 별을 켜고 끌 때 (설정에 적는다)."""
    return SellMany(parent, root, items, bag, money, keep=keep, on_keep=on_keep).show()


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
