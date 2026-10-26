# -*- coding: utf-8 -*-
"""탐험 파견의 바탕화면 쪽 (1.10.4) — 돌아온 보따리와, 받은 물건을 보여 주는 창.

탐험에서 포켓몬이 돌아오면 **바탕화면에 보따리가 놓인다.** 누르면 돌아온 것을 전부 받는다.
보내고 불러들이는 화면은 허브의 '탐험' 탭이다 (ui_expedition).

## 알리는 길

서버를 새로 두드리지 않는다. 90초마다 도는 동기화(/api/me)에 '돌아온 수 · 다음 것이 돌아오기까지
남은 초' 가 실려 온다 (Desk.note). 남은 초가 오면 그만큼 뒤에 한 번 물어봐서(Desk.check) 딱 그
시각에 보따리가 놓이게 한다 - 동기화를 기다리면 최대 90초 늦는다.

보따리가 처음 놓일 때 한 번만 알린다 (작게 - app.notify). 그 뒤로는 보따리가 거기 있는 것이
알림이다. 탭에도 점이 찍힌다.
"""
import tkinter as tk

from common import expedition as X
from common.korean import natural

from . import config, effects, skins
from . import platform_os as PLAT
from .fx_layer import screen_origin
from . import ui_common as U
from .ui_common import run_async

PANEL = "#101623"
GRADE_COLOR = {"great": U.ACCENT, "good": U.GOOD, "normal": U.FG_DIM}
# 'held' = 지닌 도구 (아주 드물게 나온다 - common/expedition.HELD). 눈에 띄게 금빛으로 적는다.
TIER_COLOR = {"common": U.FG_DIM, "uncommon": U.GOOD, "rare": U.INFO, "epic": "#c08bff", "held": U.ACCENT}
TIER_KR = {"common": "평범", "uncommon": "쓸만", "rare": "희귀", "epic": "특별", "held": "지닌 도구"}
LOOT_W = 440
RECHECK_PAD = 2            # 돌아올 시각보다 이만큼(초) 뒤에 물어본다 (시계가 조금 어긋나도 돌아와 있게)


# ---------------------------------------------------------------- 바탕화면의 보따리
class Bundle(object):
    """바탕화면에 놓인 보따리 (풀숲과 같은 방식의 작은 창). 누르면 받는다."""

    def __init__(self, desk):
        self.desk = desk
        app = desk.app
        ov = app.overlay
        key = ov.key
        size = max(30, int(ov.settings["targetHeight"] * 0.9))
        frames, w, h = effects.bundle_frames(size, 8, key)
        self.fw, self.fh = w, h
        self.frame = 0
        self.hint = None

        self.win = tk.Toplevel(ov.root)
        self.win.overrideredirect(True)
        bg = PLAT.transparent_window(self.win, "#%02x%02x%02x" % key)
        self.view = PLAT.SpriteView(self.win, bg, w, h, cursor="hand2")
        self.label = self.view.widget
        self.photos = self.view.frames(frames, key)
        self.label.bind("<Button-1>", lambda e: desk.claim())
        PLAT.bind_right(self.label, lambda e: desk.claim())
        self.label.bind("<Enter>", lambda e: self.show_hint())
        self.label.bind("<Leave>", lambda e: self.hide_hint())

        # 늘 같은 자리: 돌아다니는 곳의 왼쪽 아래. (오른쪽 아래는 길드 친선전을 구경하는 자리다)
        x1, y1, x2, y2 = ov.area()
        m = ov.settings["areaMargin"]
        self.x = x1 + m + 10
        self.y = max(y1 + m, y2 - h - m)
        self.win.geometry("+%d+%d" % (self.x, self.y))
        self.view.show(self.photos[0])
        PLAT.raise_above(self.win)
        self._job = None
        self.animate()

    def animate(self):
        self.frame = (self.frame + 1) % len(self.photos)
        try:
            self.view.show(self.photos[self.frame])
            if PLAT.NEEDS_HIT_TRACKING:
                cx, cy = self.desk.app.root.winfo_pointerxy()
                self.view.update_hit(cx - int(self.x), cy - int(self.y))
        except Exception:                                   # noqa: BLE001
            pass
        self._job = self.desk.app.root.after(130, self.animate)

    def show_hint(self):
        self.hide_hint()
        n = self.desk.ready
        text = "탐험에서 돌아왔다!\n눌러서 보따리 받기" + (" (%d개)" % n if n > 1 else "")
        try:
            w = tk.Toplevel(self.desk.app.root)
            w.overrideredirect(True)
            w.configure(bg=U.TIP_BG)
            tk.Label(w, text=text, bg=U.TIP_BG, fg=U.GOOD, font=U.FONT_TIP, justify="center",
                     padx=7, pady=3).pack()
            w.update_idletasks()
            # 0 이 아니라 모니터 전부의 왼쪽 끝에서 자른다 - 왼쪽 모니터의 보따리 글이 주 화면으로 튀지 않게 (#268)
            vx, _vy = screen_origin(self.desk.app.root)
            w.geometry("+%d+%d" % (max(vx, self.x + self.fw // 2 - w.winfo_width() // 2),
                                   self.y - w.winfo_height() - 4))
            PLAT.raise_above(w)
            self.hint = w
        except Exception:                                   # noqa: BLE001
            self.hint = None

    def hide_hint(self):
        w, self.hint = self.hint, None
        if w is not None:
            try:
                w.destroy()
            except Exception:                               # noqa: BLE001
                pass

    def destroy(self):
        self.hide_hint()
        if self._job:
            try:
                self.desk.app.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass


class Desk(object):
    """탐험의 바탕화면 쪽 일을 맡는다 (앱이 하나 들고 있다 - app.expedition).

        note(card)     서버가 준 요약(/api/me 의 expedition, 또는 탐험 응답)으로 보따리·점·예약을 맞춘다
        check()        서버에 물어본다 (다음 것이 돌아올 시각에 스스로 부른다)
        claim(eid)     보따리를 받는다. eid 가 없으면 돌아온 것 전부 (바탕화면의 보따리를 눌렀다)
        clear()        로그아웃·종료
    """

    def __init__(self, app):
        self.app = app
        self.ready = 0           # 돌아와서 받기를 기다리는 수
        self.out = 0             # 나가 있는 수 (돌아온 것 포함)
        self.bundle = None
        self.busy = False
        self._job = None
        self._told = 0           # 몇 개째까지 알렸나 (같은 보따리를 동기화마다 다시 알리지 않는다)

    # ---- 맞추기
    def note(self, card):
        if not isinstance(card, dict):
            return
        self.ready = int(card.get("ready") or 0)
        out = card.get("out")
        self.out = len(out) if isinstance(out, list) else int(out or 0)
        if self.ready > 0:
            self._show()
            if self.ready > self._told:
                self.app.notify("탐험에서 돌아왔습니다! 바탕화면의 보따리를 눌러 받으세요.")
        else:
            self._hide()
        self._told = self.ready
        self._badge()
        self._arm(card.get("nextIn"))

    def _show(self):
        if self.bundle is not None or not getattr(self.app, "overlay", None):
            return
        # (긴급 숨기기 중이면 stealth 가 새 창을 알아서 거둔다 - 여기서 따로 가리지 않는다)
        try:
            self.bundle = Bundle(self)
        except Exception as e:                              # noqa: BLE001
            config.log("보따리를 못 놓았습니다: %s" % e)
            self.bundle = None

    def _hide(self):
        b, self.bundle = self.bundle, None
        if b is not None:
            b.destroy()

    def _badge(self):
        hub = getattr(self.app, "hub", None)
        if hub is not None:
            try:
                hub.set_badge("expedition", self.ready > 0)
            except Exception:                               # noqa: BLE001
                pass

    def _arm(self, sec):
        """다음 것이 돌아올 때 한 번 물어본다. 예약은 하나만 둔다."""
        root = self.app.root
        if self._job is not None:
            try:
                root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None
        if sec is None:
            return
        try:
            ms = int((max(0, int(sec)) + RECHECK_PAD) * 1000)
        except (TypeError, ValueError):
            return
        # after 에 너무 큰 수를 주지 않는다 (동기화가 90초마다 다시 맞춰 준다)
        self._job = root.after(min(ms, 6 * 3600 * 1000), self.check)

    def check(self):
        self._job = None
        api = getattr(self.app, "api", None)
        if not api:
            return

        def done(r, err):
            if err or not isinstance(r, dict):
                return
            self.note(r)
            self._refresh_panes(r)
        run_async(self.app.root, api.expedition, done)

    # ---- 받기
    def claim(self, eid=None, parent=None):
        api = getattr(self.app, "api", None)
        if self.busy or not api:
            return
        self.busy = True
        if self.bundle is not None:
            self.bundle.hide_hint()

        def done(r, err):
            self.busy = False
            if err:
                return self.app.notify(natural(getattr(err, "message", None) or str(err)))
            self.note(r)
            self._refresh_panes(r)
            got = r.get("claimed") or []
            if not got:
                return self.app.notify(r.get("message") or "아직 돌아온 포켓몬이 없습니다.")
            if any(isinstance(g.get("friend"), dict) for g in got):
                self._new_mons()             # 친화력으로 포켓몬이 늘었다 - 목록을 새로 받는다
            # 가방이 바뀌었다 - 열려 있는 가방·상점·관리 창이 새 값을 보게 한다
            self.app.balls = r.get("balls", self.app.balls)
            self.app.money = r.get("money", self.app.money)
            tms = sum(1 for g in got if g.get("tm"))
            got_tm = getattr(self.app, "got_tm", None)
            if tms and got_tm:
                got_tm(tms)                  # 가방 탭에 새 기술머신 점 (1.11.0)
            try:
                self.app.request_sync()
            except Exception:                               # noqa: BLE001
                pass
            try:
                PLAT.activate()
                show_loot(parent or self.app.root, self.app, got)
            except Exception as e:                          # noqa: BLE001
                config.log("탐험 결과 창 오류: %s" % e)
                self.app.notify(r.get("message") or "탐험에서 돌아왔습니다!")
        run_async(self.app.root, lambda: api.expedition_claim(eid), done)

    def _refresh_panes(self, state):
        """열려 있는 탐험 탭과 포켓몬 관리 창을 새 모습으로."""
        hub = getattr(self.app, "hub", None)
        pane = hub.panes.get("expedition") if hub is not None else None
        if pane is not None:
            try:
                pane.apply(state)
            except Exception as e:                          # noqa: BLE001
                config.log("탐험 탭 갱신 오류: %s" % e)

    def _new_mons(self):
        """포켓몬이 늘었다 (친화력으로 데려왔다): 탐험 탭의 '누구를' 목록과 포켓몬 관리 창을 새로 받는다."""
        hub = getattr(self.app, "hub", None)
        pane = hub.panes.get("expedition") if hub is not None else None
        for target in (pane, getattr(self.app, "box_window", None)):
            if target is None:
                continue
            try:
                target.reload()
            except Exception as e:                          # noqa: BLE001
                config.log("목록 갱신 오류: %s" % e)

    def clear(self):
        self._hide()
        self._arm(None)
        self.ready = self.out = self._told = 0
        self.busy = False


# ---------------------------------------------------------------- 받은 물건
def loot_lines(claimed):
    """받은 것을 글로: [(머리줄, 성공도, [(도구 id 또는 None, 글, 등급)])]. 창과 검사가 같이 쓴다."""
    out = []
    for g in claimed or []:
        mon = g.get("pokemon") or {}
        head = "%s · %s %s시간" % (mon.get("name") or "?", g.get("placeKr") or "", g.get("hours") or "?")
        rows = []
        for it in g.get("items") or []:
            n = int(it.get("count") or 1)
            rows.append((it.get("id"), it.get("kr") or it.get("id") or "?", n, it.get("tier") or "common"))
        tm = g.get("tm")
        if tm:
            rows.append((None, tm.get("label") or "기술머신", 1, "tm"))
        out.append((head, g.get("grade") or "normal", g.get("gradeKr") or "", rows))
    return out


def growth_note(g):
    """보따리 아래에 적을 성장 두 줄 (1.10.5): (경험치·레벨, 쉬는 시간·더 주워 온 것, 레벨이 올랐나).

    서버가 성장을 안 실어 보냈으면(옛 서버) None.
    """
    gr = (g or {}).get("growth")
    if not isinstance(gr, dict):
        return None
    lv0, lv1 = int(gr.get("levelBefore") or 0), int(gr.get("level") or 0)
    parts = ["탐험 경험치 +%d" % int(gr["xp"])] if gr.get("xp") else []
    if lv1 > lv0:
        parts.append("탐험 Lv.%d → Lv.%d (성장치 +%d점)" % (lv0, lv1, lv1 - lv0))
    elif gr.get("need"):
        parts.append("탐험 Lv.%d (다음 레벨까지 %d)" % (lv1, int(gr["need"]) - int(gr.get("into") or 0)))
    else:
        parts.append("탐험 Lv.%d (가장 높은 레벨)" % lv1)
    tail = []
    bonus = int((g or {}).get("bonus") or 0)
    if bonus:
        tail.append("주머니 덕에 %d개를 더 주워 왔습니다" % bonus)
    rest = int(gr.get("rest") or 0)
    if rest > 0:
        tail.append("%s 동안 쉽니다" % X.hours_text(rest))
    return " · ".join(parts), " · ".join(tail), lv1 > lv0


def friend_line(g):
    """친화력으로 데려온 포켓몬을 한 줄로 (1.10.5): (글, 꼬리표) 또는 None.

    데려오려다 자리가 없어 못 데려왔으면 꼬리표가 None 이다 (글만 흐리게 적는다).
    """
    fr = (g or {}).get("friend")
    if isinstance(fr, dict):
        name = ("★ " if fr.get("shiny") else "") + (fr.get("name") or "?")
        return (natural("Lv.%s %s 을(를) 데려왔습니다!" % (fr.get("level", "?"), name)),
                "도감에 새로 등록" if fr.get("new") else "새 포켓몬")
    if (g or {}).get("friendFull"):
        return "포켓몬이 따라오려 했지만, 박스가 가득 차서 데려오지 못했습니다.", None
    return None


def _mon_thumb(win, app, label, mon, keep, tag, size=30):
    """데려온 포켓몬의 도트를 칸에 넣는다 (없으면 받아서). 창을 늦게 띄우지 않는다 - 오면 채운다."""
    num = mon.get("num")
    if not num:
        return
    from common import tint as T
    from . import sprite_cache, sprites
    from PIL import ImageTk
    skin = T.skin(mon)

    def work():
        path = sprite_cache.ensure(app.api, num, skin)
        if not path:
            return None
        anim = sprites.load_animation(path, size, 0.2, 3.0, max_frames=1, max_size=(size, size))
        return sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key)

    def done(img, err):
        if err or img is None:
            return
        try:
            ph = ImageTk.PhotoImage(img)
            keep[tag] = ph
            label.configure(image=ph)
        except tk.TclError:
            pass                             # 그사이 창을 닫았다
    run_async(win, work, done)


def loot_summary(lines, claimed):
    """창 머리에 적을 한 줄: '물건 N개를 가져왔습니다.' (+ ' 포켓몬 M마리를 데려왔습니다.'). 화면(기본 · 테마)이 같이 쓴다."""
    total = sum(n for _h, _g, _k, rows in lines for _i, _t, n, _tier in rows)
    friends = sum(1 for g in claimed if isinstance((g or {}).get("friend"), dict))
    return "물건 %d개를 가져왔습니다." % total + (" 포켓몬 %d마리를 데려왔습니다." % friends if friends else "")


def loot_max_height(win):
    """받은 것 창의 높이 한계: 화면 높이의 2/3. 넘으면 창을 키우지 않고 안쪽이 굴러간다."""
    try:
        return int(win.winfo_screenheight() * 0.66)
    except tk.TclError:
        return None


@skins.skinnable_fn("announce")
def show_loot(parent, app, claimed):
    """탐험에서 가져온 것을 보여 준다. 창은 내용만큼만 크고, 길면 안쪽이 굴러간다."""
    from . import ui_bag, ui_box
    lines = loot_lines(claimed)
    if not lines:
        return
    keep = {}
    win, f = ui_box._shell(parent, "탐험", LOOT_W, U.h(260))
    tk.Label(f, text="탐험에서 돌아왔습니다", bg=U.BG, fg=U.ACCENT_TEXT,
             font=(U.FAMILY_BLACK, U.pt(20))).pack(anchor="w")
    tk.Label(f, text=loot_summary(lines, claimed),
             bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(anchor="w", pady=(4, 0))

    # **바닥 줄(확인 단추)을 먼저 잡는다.** 굴러가는 칸을 먼저 담으면 그 칸이 높이를 다 먹어서,
    # 물건이 많을 때 단추가 창 밖으로 밀려난다.
    foot = tk.Frame(f, bg=U.BG)
    foot.pack(fill="x", pady=(14, 0), side="bottom")
    U.PushButton(foot, "확인", win.destroy, height=34, font=U.FONT_B).pack(side="right")
    tk.Label(foot, text="가방에 넣어 두었습니다.", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(side="left")

    inner, cv = ui_box.scroll_body(f)
    tag = 0
    for (head, grade, grade_kr, rows), one in zip(lines, claimed):
        box = tk.Frame(inner, bg=PANEL, highlightthickness=2, highlightbackground=U.LINE)
        box.pack(fill="x", pady=(12, 0), padx=(0, 2))
        top = tk.Frame(box, bg=PANEL)
        top.pack(fill="x", padx=14, pady=(9, 3))
        tk.Label(top, text=head, bg=PANEL, fg=U.FG, font=U.FONT_B, anchor="w").pack(side="left")
        if grade_kr:
            tk.Label(top, text=grade_kr, bg=PANEL, fg=GRADE_COLOR.get(grade, U.FG_DIM),
                     font=U.FONT_B).pack(side="right")
        body = tk.Frame(box, bg=PANEL)
        body.pack(fill="x", padx=14, pady=(0, 9))
        if not rows:
            tk.Label(body, text="아무것도 못 찾았다...", bg=PANEL, fg=U.FG_FAINT, font=U.FONT_S).pack(anchor="w")
        # 친화력으로 데려온 포켓몬 (1.10.5). 물건보다 먼저, 금빛으로 적는다.
        came = friend_line(one)
        if came:
            text, badge = came
            row = tk.Frame(body, bg=PANEL)
            row.pack(fill="x", pady=(0, 2))
            if badge:
                slot = tk.Frame(row, bg=PANEL, width=U.h(30), height=max(U.h(30), 32))
                slot.pack(side="left", padx=(0, 8))
                slot.pack_propagate(False)
                art = tk.Label(slot, bg=PANEL, bd=0, highlightthickness=0)
                art.pack(expand=True)
                _mon_thumb(win, app, art, one["friend"], keep, "friend%d" % tag)
                tag += 1
                tk.Label(row, text=badge, bg=PANEL, fg=U.ACCENT, font=U.FONT_XS, anchor="e").pack(side="right")
            lb = tk.Label(row, text=text, bg=PANEL, fg=U.ACCENT_TEXT if badge else U.FG_FAINT,
                          font=U.FONT_B if badge else U.FONT_XS, anchor="w", justify="left",
                          wraplength=LOOT_W - 2 * 18 - 2 * 14 - (U.h(30) + 8 + U.h(90) if badge else 8))
            lb.pack(side="left", fill="x", expand=True)
        for item_id, text, n, tier in rows:
            row = tk.Frame(body, bg=PANEL, height=U.h(32))
            row.pack(fill="x")
            row.pack_propagate(False)
            slot = tk.Frame(row, bg=PANEL, width=U.h(30), height=U.h(30))
            slot.pack(side="left", padx=(0, 8))
            slot.pack_propagate(False)
            icon = tk.Label(slot, bg=PANEL)
            icon.pack(expand=True)
            if item_id:
                ui_bag._gift_icon(win, app, icon, item_id, keep, tag)
                tag += 1
            fg = U.ACCENT_TEXT if tier == "tm" else (U.FG if tier in ("common", "uncommon") else TIER_COLOR.get(tier, U.FG))
            tk.Label(row, text="%s%s" % (text, " × %d" % n if n > 1 else ""), bg=PANEL, fg=fg,
                     font=U.FONT_B, anchor="w").pack(side="left")
            note = "새 기술머신" if tier == "tm" else TIER_KR.get(tier, "")
            tk.Label(row, text=note, bg=PANEL, fg=U.ACCENT if tier == "tm" else TIER_COLOR.get(tier, U.FG_FAINT),
                     font=U.FONT_XS, anchor="e").pack(side="right")
        # 그 포켓몬이 얻은 탐험 경험치와 쉬는 시간 (1.10.5). 레벨이 올랐으면 금빛으로.
        grown = growth_note(one)
        if grown:
            tk.Frame(box, bg=U.LINE, height=1).pack(fill="x", padx=14)
            foot2 = tk.Frame(box, bg=PANEL)
            foot2.pack(fill="x", padx=14, pady=(6, 8))
            for text, color in ((grown[0], U.ACCENT_TEXT if grown[2] else U.FG_DIM), (grown[1], U.FG_FAINT)):
                if text:
                    lb = tk.Label(foot2, text=text, bg=PANEL, fg=color, font=U.FONT_XS, anchor="w", justify="left",
                                  bd=0)
                    lb.pack(fill="x", pady=(1, 0))
                    U.wrap_to_width(lb)

    win.keep = keep
    # 내용만큼만 키운다. 화면 높이의 2/3 를 넘으면 안쪽이 굴러간다.
    ui_box.fit(win, hi=loot_max_height(win), scroll=(cv, inner))
    win.grab_set()
    parent.wait_window(win)
