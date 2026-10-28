# -*- coding: utf-8 -*-
"""친구 집에 놀러 가기 - 도구 고르는 창 (1.11.0). **가방 창(ui_bag)의 생김새를 그대로 빌린다.**

두 가지로 쓴다 (10/15 사용자 교정 - 처음 만든 창은 디자인이 구렸고, 줄 것은 보낼 때가 아니라 친구 집에서
고르는 것이었다):

    carry  친구 목록의 '놀러 가기'. 가방에서 **들고 갈 도구**를 고른다 - 볼·지닌 도구 중 귀함까지만, 볼 5개·
           지닌 도구 1개까지 (10/15 사용자 결정, 서버 visit.carryable 과 같은 규칙). 아무것도 안 옮긴다.
    drop   친구 집에서 내 포켓몬 우클릭 '여기에 두기'. 들고 온 것 중 고른 만큼 **보따리**로 싸서 둔다
           (그 순간 내 가방에서 빠진다). 친구가 보따리를 누르면 받는다. 받는 것은 하루 한 번 - 친구가 오늘
           이미 받았으면 둘 수 없다 (canGive).

왼쪽은 가방과 같은 '가진 도구' 목록 (분류 머리줄 + 줄, 보이는 줄만 만든다). 줄을 누르면 하나씩 담긴다.
오른쪽은 담은 것 (줄마다 -, +, 빼기). 아래 띠에 알림과 단추.
"""
import tkinter as tk

from PIL import ImageTk

from common import tint as T
from common.korean import natural

from . import item_icons, skins, sprite_cache, sprites
from . import ui_bag
from . import ui_common as U
from .ui_common import run_async

W, H = 760, 540              # 가방(1000x664)보다 작게 - 목록 폭은 가방과 같다
CARRY_CATS = ("ball", "held")                   # 서버 visit.CARRY_CATS 와 같다
CARRY_RARITY = ("common", "uncommon", "rare")   # 서버가 state.rarities 로도 준다 (흔함·조금귀함·귀함)
THUMB = 44                   # 놀러 가는 포켓몬 그림 높이


def _rgb(hexcolor):
    h = hexcolor.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class PickRow(ui_bag.ItemRow):
    """왼쪽 목록 한 줄 (가방의 줄 그대로). 담은 것은 고른 줄처럼 칠하고 '담음 / 가진 수' 를 쓴다."""

    def bind(self, item):
        ui_bag.ItemRow.bind(self, item)
        self.usable = True                           # 무엇이든 들고 갈 수 있다 (가방처럼 흐리게 두지 않는다)
        have = self.win.bag.get(item["id"], 0)
        n = self.win.plan.get(item["id"], 0)
        self.selected = n > 0
        self.count.configure(text=("%d / %d개" % (n, have)) if n else ("%d개" % have),
                             fg=U.ACCENT if n else U.FG_DIM)
        self._look()


@skins.skinnable
class ItemPicker(object):
    """들고 갈 도구 (carry) · 보따리에 쌀 도구 (drop) 고르는 창.

    고르기 · 한도 · 서버 호출은 여기 그대로 두고, 화면 테마는 **짓는 고리(_build)와 칠하는 고리**
    (_show_limit · _set_go · _paint_status · _show_who · _set_thumb · _set_entries · _refresh_list ·
    _set_empty_text · _show_empty · _paint_picked) 만 덮어쓴다.
    """
    WIN_SIZE = (W, H)             # 테마가 크기를 바꾸려면 이 둘을 덮는다
    WIN_MIN = (640, 460)

    def __init__(self, app, mode, friend=None):
        self.app, self.mode = app, mode
        self.root = app.root
        self.friend = friend or {}
        self.alive = True
        self.items = []               # 도구 명세 (분류·이름) - 가방과 같은 /api/shop
        self.bag = {}                 # {도구: 고를 수 있는 수} - carry 는 가방, drop 은 들고 온 것
        self.plan = {}                # {도구: 담은 수}
        self.order = []               # 담은 차례
        self.state = {}
        self.item_id = None           # ItemRow 가 읽는다 (마지막으로 누른 것)
        self.keep = {}                # PhotoImage 를 붙들어 둔다
        self.picked_rows = {}         # {도구: (줄, 개수 글)}
        carry = self.carry = (mode == "carry")
        self.win = U.panel(None, self.root, "포스크탑 — 놀러 가기" if carry else "포스크탑 — 여기에 두기",
                           self.WIN_SIZE[0], self.WIN_SIZE[1], self.WIN_MIN[0], self.WIN_MIN[1], self.close)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        U.install_wheel(self.win)
        self._build()
        self.load()

    # ---------------- 짓기 (테마마다 짓는 곳) ----------------
    def _build(self):
        """창 안의 것들. 테마는 이것을 통째로 덮는다 - self.limit · go_btn · status · who · who_sub ·
        picked_note 에 해당하는 자리를 두고 아래 칠하는 고리(_show_limit …)를 받아야 한다."""
        self._header()
        self._bottom()
        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True)
        self._list_pane(body)
        self._picked_pane(body)

    # ---------------- 칠하는 고리 (테마가 덮는 곳) ----------------
    def _show_limit(self, text, fg=None):
        """머리의 한도 칸 ('볼 2/5 · 지닌 도구 0/1' · '받을 수 있음')."""
        if fg is None:
            self.limit.configure(text=text)
        else:
            self.limit.configure(text=text, fg=fg)

    def _set_go(self, enabled):
        self.go_btn.configure(state="normal" if enabled else "disabled")

    def _paint_status(self, text, color, fg):
        U.set_status(self.status, text, color, fg)

    def _show_who(self, title, sub):
        self.who.configure(text=title)
        self.who_sub.configure(text=sub)

    def _set_thumb(self, img):
        self.keep["thumb"] = ImageTk.PhotoImage(img)
        self.thumb.configure(image=self.keep["thumb"])

    def _set_entries(self, entries):
        self.vl.set(entries)

    def _refresh_list(self):
        self.vl.refresh()

    def _set_empty_text(self, text):
        self.empty_text.configure(text=text)

    # ---------------- 머리 ----------------
    def _header(self):
        from . import visit as V
        h = tk.Frame(self.win, bg=U.BG2, height=U.h(62))
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)
        try:
            img = V.bundle_image(U.h(30), key=_rgb(U.BG2))
            self.keep["head"] = ImageTk.PhotoImage(img)
            tk.Label(inner, image=self.keep["head"], bg=U.BG2, bd=0).pack(side="left")
        except Exception:                                   # noqa: BLE001
            pass
        tk.Label(inner, text="놀러 가기" if self.carry else "여기에 두기", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(15))).pack(side="left", padx=(10, 10))
        tk.Label(inner, text=self._whose_home(),
                 bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_S).pack(side="left")
        purse = tk.Frame(inner, bg=U.INK, highlightthickness=2, highlightbackground=U.LINE)
        purse.pack(side="right")
        tk.Label(purse, text="들고 갈 도구" if self.carry else "친구가 오늘", bg=U.INK, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="left", padx=(10, 6), pady=4)
        self.limit = tk.Label(purse, text="", bg=U.INK, fg=U.ACCENT, font=U.FONT_B)
        self.limit.pack(side="left", padx=(0, 10))
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

    def _whose_home(self):
        """머리의 '○○ 님의 집으로' (놀러 갈 때) · '○○ 님의 집에' (둘 때)."""
        who = self.friend.get("name") or ((self.app.visit.v or {}).get("partner") if self.app.visit else "")
        return ("%s 님의 집으로" if self.carry else "%s 님의 집에") % (who or "친구")

    def _how_text(self):
        """오른쪽 아래 안내글."""
        if self.carry:
            return ("들고 갈 수 있는 것은 볼과 지닌 도구 중 귀함까지 (볼 5개 · 지닌 도구 1개). 들고 간 도구는 "
                    "보여 주기만 한다. 친구 집에서 내 포켓몬을 우클릭해 '여기에 두기' 를 하면 보따리에 싸서 친구에게 "
                    "줄 수 있다 (친구는 하루 한 번 받는다). 안 준 것은 그대로 내 가방에 남는다.")
        return ("두는 순간 내 가방에서 빠진다. 친구가 보따리를 누르면 친구 가방으로 들어가고, 안 받은 채 "
                "끝나면 돌려받는다. 보따리를 받는 것은 하루 한 번이다.")

    # ---------------- 왼쪽: 고를 수 있는 것 (가방의 목록) ----------------
    def _list_pane(self, parent):
        wrap = tk.Frame(parent, bg=U.BG, width=ui_bag.LIST_W)
        wrap.pack(side="left", fill="y")
        wrap.pack_propagate(False)
        head = tk.Frame(wrap, bg=U.INK, height=U.h(26))
        head.pack(fill="x")
        head.pack_propagate(False)
        U.marker_label(head, "가진 도구" if self.carry else "들고 온 도구", bg=U.INK).pack(
            side="left", padx=12)                    # pady 없이 세로 가운데 (26 에 6+6 이면 윈도우에서 눌린다)
        tk.Frame(wrap, bg=U.LINE, height=U.h(2)).pack(fill="x")
        self.vl = U.VirtualList(wrap, {
            "head": (ui_bag.HEAD_H + U.h(1), ui_bag.HeadRow),
            "item": (ui_bag.ITEM_H + U.h(1), lambda p: PickRow(p, self))}, bg=U.BG)
        self.vl.pack(fill="both", expand=True)
        self.empty = tk.Frame(wrap, bg=U.BG)
        self.empty_text = tk.Label(self.empty, text="불러오는 중...", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S,
                                   justify="center")
        self.empty_text.pack(pady=(34, 4))

    # ---------------- 오른쪽: 담은 것 ----------------
    def _picked_pane(self, parent):
        d = tk.Frame(parent, bg=U.BG2)
        d.pack(side="right", fill="both", expand=True)
        tk.Frame(d, bg=U.LINE2, width=2).place(x=0, y=0, relheight=1.0)
        p = tk.Frame(d, bg=U.BG2)
        p.pack(fill="both", expand=True, padx=(18, 16), pady=13)
        top = tk.Frame(p, bg=U.BG2)
        top.pack(fill="x")
        self.thumb = tk.Label(top, bg=U.BG2, bd=0)
        self.thumb.pack(side="left", padx=(0, 10))
        words = tk.Frame(top, bg=U.BG2)
        words.pack(side="left", fill="x", expand=True)
        self.who = tk.Label(words, text="", bg=U.BG2, fg=U.ACCENT_TEXT, font=(U.FAMILY_BLACK, U.pt(14)),
                            anchor="w")
        self.who.pack(fill="x")
        self.who_sub = tk.Label(words, text="", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                                justify="left")
        self.who_sub.pack(fill="x")
        U.wrap_to_width(self.who_sub)
        lhead = tk.Frame(p, bg=U.BG2)
        lhead.pack(fill="x", pady=(14, 5))
        U.marker_label(lhead, "들고 갈 도구" if self.carry else "보따리에 쌀 도구", bg=U.BG2).pack(side="left")
        tk.Label(lhead, text="왼쪽 줄을 누르면 하나씩 담긴다", bg=U.BG2, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="right")
        frame = U.framed(p, bg=ui_bag.ROW_BG, border=U.LINE)
        frame.pack(fill="both", expand=True)
        self.picked = tk.Frame(frame, bg=ui_bag.ROW_BG)
        self.picked.pack(fill="both", expand=True)
        self.picked_note = tk.Label(self.picked, text="", bg=ui_bag.ROW_BG, fg=U.FG_FAINT, font=U.FONT_S,
                                    justify="center", pady=30)
        self.how = tk.Label(p, text=self._how_text(), bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left")
        self.how.pack(fill="x", pady=(10, 0))
        U.wrap_to_width(self.how)

    def _bottom(self):
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x", side="bottom")
        bar = tk.Frame(self.win, bg=U.INK, height=U.h(58))
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        inner = tk.Frame(bar, bg=U.INK)
        inner.pack(fill="both", expand=True, padx=16)
        # **단추에 pady 를 주지 않는다** - 띠(58) 에 단추(34+그림자)+22 면 윈도우에서 2px 눌린다.
        # 여백 없이도 pack 이 띠 안의 세로 가운데에 놓는다 (가방 머리줄과 같은 수).
        self.go_btn = U.PushButton(inner, "놀러 가기" if self.carry else "보따리 두기", self.go, height=34)
        self.go_btn.pack(side="right")
        U.ghost_button(inner, "닫기", self.close, height=34).pack(side="right", padx=(0, 8))
        self.status = U.status_line(inner, "", bg=U.INK)
        self.status.pack(side="left", fill="x", expand=True, pady=11)

    # ---------------- 거들기 ----------------
    def say(self, text, color=U.GOOD, fg=None):
        try:
            self._paint_status(natural(text or ""), color, fg)
        except tk.TclError:
            pass

    def ball_max(self):
        return int(self.state.get("ballMax") or 5)

    def held_max(self):
        return int(self.state.get("heldMax") or 1)

    def can_give(self):
        """drop: 친구가 오늘 한 번을 아직 안 썼나 (서버가 view.canGive 로 준다)."""
        return bool(((self.state.get("visit") or {}).get("canGive", True)) if self.state else True)

    def cat_of(self, iid):
        return next((it.get("cat") for it in self.items if it["id"] == iid), None)

    def cat_total(self, cat):
        return sum(n for iid, n in self.plan.items() if self.cat_of(iid) == cat)

    def total(self):
        return sum(self.plan.values())

    # ---------------- 불러오기 ----------------
    def load(self):
        api = self.app.api
        vis = getattr(self.app, "visit", None)
        lead = vis.my_lead_pet() if (vis is not None and self.carry) else None
        mon = dict(lead.mon or {}) if lead is not None else None
        look = getattr(lead, "look", None) if lead is not None else None

        def work():
            shop = ui_bag.fetch_shop(api)
            st = api.visit_state()
            if self.carry:
                have = dict((k, int(v)) for k, v in ((shop or {}).get("bag") or {}).items() if int(v or 0) > 0)
            else:
                v = (st or {}).get("visit") or {}
                have = dict((x["id"], int(x["count"])) for x in v.get("carry") or [] if int(x.get("count") or 0) > 0)
            try:
                item_icons.prefetch(api, list(have), sizes=(20, 26))
            except Exception:                               # noqa: BLE001
                pass
            thumb = None
            if mon:
                try:
                    path = sprite_cache.ensure(api, (look if (look or 0) >= 10000 else mon.get("num")), T.skin(mon))
                    anim = sprites.load_animation(path, target_height=THUMB, min_scale=0.2, max_scale=3.0,
                                                  max_frames=1, max_size=(THUMB + 12, THUMB + 6))
                    thumb = sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key)
                except Exception:                           # noqa: BLE001
                    thumb = None
            return shop, st, have, thumb

        def done(r, err):
            if not self.alive:
                return
            if err:
                self._set_empty_text("불러오지 못했다.\n%s" % getattr(err, "message", err))
                self._show_empty(True)
                return
            shop, st, have, thumb = r
            self.state = st or {}
            names = dict((it["id"], it) for it in (shop or {}).get("items") or [])
            if self.carry:                                  # 들고 갈 수 있는 것만 (볼·지닌 도구, 귀함까지)
                ok = tuple(self.state.get("rarities") or CARRY_RARITY)
                have = dict((k, n) for k, n in have.items()
                            if (names.get(k) or {}).get("cat") in CARRY_CATS and (names.get(k) or {}).get("rarity") in ok)
            self.bag = have
            carried = dict((x["id"], x) for x in ((self.state.get("visit") or {}).get("carry") or []))
            self.items = []
            for iid in have:
                it = names.get(iid) or {"id": iid, "kr": (carried.get(iid) or {}).get("kr") or iid, "cat": "misc"}
                self.items.append(it)
            self.items.sort(key=lambda i: (ui_bag.CAT_ORDER.index(i.get("cat"))
                                           if i.get("cat") in ui_bag.CAT_ORDER else 99, i.get("kr") or ""))
            if thumb is not None:
                try:
                    self._set_thumb(thumb)
                except Exception:                           # noqa: BLE001
                    pass
            self._fill()
            self.paint()
        run_async(self.root, work, done)

    def _show_empty(self, on):
        if on:
            self.vl.holder.pack_forget()
            self.empty.pack(fill="both", expand=True)
        else:
            self.empty.pack_forget()
            self.vl.pack(fill="both", expand=True)

    def _fill(self):
        if not self.items:
            self._set_empty_text("들고 갈 수 있는 도구가 없다.\n(볼 · 지닌 도구 중 귀함까지)\n도구 없이도 놀러 "
                                 "갈 수 있다." if self.carry
                                 else "들고 온 도구가 없다.\n다음에 놀러 갈 때 들고 와서 둘 수 있다.")
            self._show_empty(True)
            return
        self._show_empty(False)
        counts, entries, last = {}, [], None
        for x in self.items:
            counts[x.get("cat")] = counts.get(x.get("cat"), 0) + 1
        for it in self.items:
            if it.get("cat") != last:
                last = it.get("cat")
                entries.append(("head", (last, counts[last])))
            entries.append(("item", it))
        self._set_entries(entries)

    # ---------------- 고르기 ----------------
    def pick_item(self, iid):
        """왼쪽 줄을 눌렀다 - 하나 더 담는다."""
        self.item_id = iid
        self.bump(iid, 1)

    def bump(self, iid, d):
        have = self.bag.get(iid, 0)
        n = self.plan.get(iid, 0)
        if d > 0:
            if n >= have:
                return self.say("가진 만큼 다 담았다.", U.FG_FAINT)
            cat = self.cat_of(iid)
            if self.carry and cat == "ball" and self.cat_total("ball") + 1 > self.ball_max():
                return self.say("볼은 %d개까지 들고 갈 수 있다." % self.ball_max(), U.DANGER, U.DANGER)
            if self.carry and cat == "held" and self.cat_total("held") + 1 > self.held_max():
                return self.say("지닌 도구는 %d개까지 들고 갈 수 있다." % self.held_max(), U.DANGER, U.DANGER)
            if not self.carry and not self.can_give():
                return self.say(self._no_give_text(), U.DANGER, U.DANGER)
        n = max(0, min(have, n + d))
        if n:
            if iid not in self.plan:
                self.order.append(iid)
            self.plan[iid] = n
        else:
            self.remove(iid)
            return
        self.say("")
        self.paint()

    def remove(self, iid):
        self.plan.pop(iid, None)
        if iid in self.order:
            self.order.remove(iid)
        self.say("")
        self.paint()

    def items_out(self):
        return [{"id": iid, "count": self.plan[iid]} for iid in self.order if self.plan.get(iid)]

    # ---------------- 그리기 ----------------
    def paint(self):
        if not self.alive:
            return
        try:
            self._refresh_list()
        except tk.TclError:
            pass
        self._paint_who()
        self._paint_picked()
        if self.carry:
            self._show_limit("볼 %d/%d · 지닌 도구 %d/%d" % (
                self.cat_total("ball"), self.ball_max(), self.cat_total("held"), self.held_max()))
            self._set_go(True)
        else:
            give = self.can_give()
            self._show_limit("받을 수 있음" if give else "이미 받음", U.ACCENT if give else U.DANGER)
            self._set_go(give and self.total() > 0)
            if not give:
                self.say(self._no_give_text(), U.DANGER, U.DANGER)
        self._grow()

    def _grow(self):
        """내용이 창보다 크면 그만큼 창을 늘린다 (줄이지는 않는다, 화면 작업 영역까지).

        글자 크기 '크게·아주 크게' 에서는 오른쪽 칸(포켓몬 · 담은 줄 · 안내글)이 540 보다 길어
        맨 아래 안내글이 눌려 잘렸다. 글씨를 줄이지 않고 창을 내용만큼 키운다 - 보통 크기는
        내용이 창 안에 들어가 그대로다.
        """
        try:
            if U.is_embedded(self.win):
                return
            self.win.update_idletasks()
            have = self.win.winfo_height()
            if have > 1 and self.win.winfo_reqheight() > have:
                U.fit_window(self.win, self.win.winfo_width(), lo=have, keep_pos=True)
        except tk.TclError:
            pass

    def _no_give_text(self):
        who = (self.state.get("visit") or {}).get("partner") or "친구"
        return "%s 님은 오늘 이미 보따리를 받았다 (하루 한 번)." % who

    def _paint_who(self):
        vis = getattr(self.app, "visit", None)
        if self.carry:
            lead = vis.my_lead_pet() if vis is not None else None
            info = ((lead.mon or {}).get("info") or {}) if lead is not None else {}
            self._show_who(("%s  Lv.%s" % (info.get("name"), info.get("level", "?")))
                           if info.get("name") else "파티 맨 앞 포켓몬",
                           "이(가) 친구 바탕화면으로 놀러 간다. 화면 오른쪽에서 걸어 들어가 오른쪽 "
                           "아래에 선다.")
        else:
            self._show_who("보따리 %d개" % self.total() if self.total() else "보따리",
                           "내 포켓몬 옆에 보따리를 둔다. 친구가 누르면 받는다.")

    def _paint_picked(self):
        for iid in list(self.picked_rows):
            if iid not in self.plan:
                self.picked_rows.pop(iid)[0].destroy()
        if not self.plan:
            self.picked_note.configure(text="왼쪽에서 도구를 누르면 여기에 담긴다." if self.carry
                                       else "왼쪽에서 보따리에 쌀 도구를 누른다.")
            self.picked_note.pack(fill="both", expand=True)
            return
        self.picked_note.pack_forget()
        names = dict((it["id"], it.get("kr") or it["id"]) for it in self.items)
        for iid in self.order:
            got = self.picked_rows.get(iid)
            if got is None:
                got = self.picked_rows[iid] = self._picked_row(iid, names.get(iid, iid))
            got[1].configure(text="%d" % self.plan.get(iid, 0))

    def _picked_row(self, iid, name):
        bg = ui_bag.ROW_BG
        # 줄 높이는 박지 않는다 - 단추·글꼴 높이는 OS 마다 달라서 박으면 윈도우에서 눌렸다. 아래 1px 이 금.
        outer = tk.Frame(self.picked, bg=ui_bag.SEP)
        outer.pack(fill="x")
        row = tk.Frame(outer, bg=bg)
        row.pack(fill="x", pady=(0, 1))
        slot = tk.Frame(row, bg=bg, width=U.h(30), height=U.h(30))
        slot.pack(side="left", padx=(10, 6), pady=5)
        slot.pack_propagate(False)
        ph = item_icons.photo(iid, 26)
        icon = tk.Label(slot, bg=bg, bd=0)
        if ph is not None:
            icon.configure(image=ph)
            icon.image = ph
        icon.pack(expand=True)
        U.ghost_button(row, "빼기", lambda: self.remove(iid), height=26).pack(side="right", padx=(6, 10))
        U.ghost_button(row, "+", lambda: self.bump(iid, 1), height=26).pack(side="right")
        val = tk.Label(row, text="0", bg=bg, fg=U.ACCENT, font=U.FONT_B, width=3)
        val.pack(side="right")
        U.ghost_button(row, "-", lambda: self.bump(iid, -1), height=26).pack(side="right")
        tk.Label(row, text=name, bg=bg, fg=U.FG, font=U.FONT_S, anchor="w").pack(side="left", fill="x",
                                                                               expand=True)
        return outer, val

    # ---------------- 보내기 ----------------
    def go(self):
        if self.carry:
            return self._go_carry()
        return self._go_drop()

    def _go_carry(self):
        vis = getattr(self.app, "visit", None)
        if vis is None:
            return
        self._set_go(False)
        self.say("가는 중...", U.FG_FAINT)

        def done(r, err):
            if not self.alive:
                return
            if err:
                self._set_go(True)
                return self.say(getattr(err, "message", None) or str(err), U.DANGER, U.DANGER)
            self.close()
        vis.go(self.friend["id"], self.items_out(), done)

    def _go_drop(self):
        items = self.items_out()
        if not items:
            return
        self._set_go(False)
        self.say("보따리를 싸는 중...", U.FG_FAINT)
        api = self.app.api

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.paint()
                return self.say(getattr(err, "message", None) or str(err), U.DANGER, U.DANGER)
            try:
                self.app.request_sync()                   # 내 가방에서 빠졌다
            except Exception:                               # noqa: BLE001
                pass
            self.close()
        run_async(self.root, lambda: api.visit_drop(items), done)

    def close(self):
        self.alive = False
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass


def SendDialog(app, friend):
    """친구 목록의 '놀러 가기' (들고 갈 도구 고르기)."""
    return ItemPicker(app, "carry", friend)


def DropDialog(app):
    """친구 집에서 '여기에 두기' (보따리에 쌀 도구 고르기)."""
    return ItemPicker(app, "drop")
