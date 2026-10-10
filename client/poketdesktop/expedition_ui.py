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

from common.korean import natural

from . import config, effects
from . import platform_os as PLAT
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
            w.geometry("+%d+%d" % (max(0, self.x + self.fw // 2 - w.winfo_width() // 2),
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
            # 가방이 바뀌었다 - 열려 있는 가방·상점·관리 창이 새 값을 보게 한다
            self.app.balls = r.get("balls", self.app.balls)
            self.app.money = r.get("money", self.app.money)
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


def show_loot(parent, app, claimed):
    """탐험에서 가져온 것을 보여 준다. 창은 내용만큼만 크고, 길면 안쪽이 굴러간다."""
    from . import ui_bag, ui_box
    lines = loot_lines(claimed)
    if not lines:
        return
    keep = {}
    win, f = ui_box._shell(parent, "탐험", LOOT_W, U.h(260))
    total = sum(n for _h, _g, _k, rows in lines for _i, _t, n, _tier in rows)
    tk.Label(f, text="탐험에서 돌아왔습니다", bg=U.BG, fg=U.ACCENT_TEXT,
             font=(U.FAMILY_BLACK, U.pt(20))).pack(anchor="w")
    tk.Label(f, text="물건 %d개를 가져왔습니다." % total, bg=U.BG, fg=U.FG_DIM,
             font=U.FONT_S).pack(anchor="w", pady=(4, 0))

    # **바닥 줄(확인 단추)을 먼저 잡는다.** 굴러가는 칸을 먼저 담으면 그 칸이 높이를 다 먹어서,
    # 물건이 많을 때 단추가 창 밖으로 밀려난다.
    foot = tk.Frame(f, bg=U.BG)
    foot.pack(fill="x", pady=(14, 0), side="bottom")
    U.PushButton(foot, "확인", win.destroy, height=34, font=U.FONT_B).pack(side="right")
    tk.Label(foot, text="가방에 넣어 두었습니다.", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(side="left")

    inner, cv = ui_box.scroll_body(f)
    tag = 0
    for head, grade, grade_kr, rows in lines:
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

    win.keep = keep
    # 내용만큼만 키운다. 화면 높이의 2/3 를 넘으면 안쪽이 굴러간다.
    try:
        hi = int(win.winfo_screenheight() * 0.66)
    except tk.TclError:
        hi = None
    ui_box.fit(win, hi=hi, scroll=(cv, inner))
    win.grab_set()
    parent.wait_window(win)
