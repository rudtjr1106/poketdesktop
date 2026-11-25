# -*- coding: utf-8 -*-
"""더블배틀 창 (독도 · 실시간, 2026-11-25) — 편마다 두 마리.

실시간 1:1 창(ui_live_battle.LiveBattleWindow)과 **겉 약속이 같다**: 앱은 app.live_battle 에 이 창을 걸어 두고
focus / request_close / close / set_watchers 만 부른다. 판은 서버(common/double_battle)가 내 쪽으로 뒤집어서 준다 -
자리 이름은 me0 · me1 · foe0 · foe1.

## 화면

    (상대1 이름표)(상대0 이름표)
                              ◇ 상대1     ◇ 상대0        <- 상대의 0번은 내 오른쪽 (마주 본다)
        ◆ 나0     ◆ 나1
                              (나0 이름표)(나1 이름표)
    ------------------------------------------------------------
    ○○의 행동 (1/2)   [기술][기술][기술][기술]      45초 · 3턴
    대상: [상대 망나뇽][상대 토게키스][아군 한카리아스]   [교체][되돌리기][기권]

## 고르기

나와 있는 포켓몬마다 차례로: 기술 → (고를 대상이 둘 이상이면) 대상. 또는 교체. **둘 다 정하면 한 번에 보낸다**
(POST /api/live/act {kind: "picks"}). 보내기 전에는 [되돌리기] 로 앞의 것을 다시 고른다.
쓰러진 자리가 생기면 그 자리마다 다음 포켓몬을 고른다 (상대는 기다린다).

테마 파일은 없다 - 기본 위젯으로 그려서 어느 화면 테마에서나 같은 모습이다. 크기도 고정이다 (v1).
"""
import time
import tkinter as tk

from PIL import ImageTk

from common import tint as T
from common.korean import natural

from . import battle_fx as FX
from . import platform_os as PLAT
from . import sprite_cache, sprites
from . import ui_common as U
from . import ui_gimmick
from .ui_common import run_async
from .ui_gym import shade
from .ui_gym_battle import CAT_COLOR, CAT_KR, FX_SCALE, _FxStage, hp_color
from .ui_live_battle import step_of

W = 940
SCENE_H = 372
MSG_H = 50
CMD_H = 268
STEP_MS = 560
POLL_MS = 1500
FX_ON = True                    # 기술 연출 (검사는 끄고 본다 - 연출을 기다리지 않게)
KEYS = ("me0", "me1", "foe0", "foe1")
MON_H = {"me": 116, "foe": 98}
MON_W = {"me": 190, "foe": 170}
# 도트가 서는 자리 (장면 너비 · 높이의 몫). 상대의 0번은 내 오른쪽이다 - 서로 마주 본다.
SPOT = {"me0": (0.15, 0.95), "me1": (0.36, 0.95), "foe1": (0.60, 0.55), "foe0": (0.82, 0.55)}
STAGE_KR = {"atk": "공", "def": "방", "spa": "특공", "spd": "특방", "spe": "스피드", "acc": "명중", "eva": "회피"}
STATUS_KR = {"burn": "화상", "paralysis": "마비", "poison": "독", "sleep": "잠듦", "freeze": "얼음"}
AIM_KR = {"foes": "상대 둘 다", "all": "나 빼고 전부", "self": "자신", "ally": "아군", "team": "나와 아군",
          "field": "판 전체", "random": "무작위 상대", "back": "나를 때린 상대"}


def side_of(key):
    return "me" if str(key).startswith("me") else "foe"


class DoubleBattleWindow(object):

    def __init__(self, app, data, on_close=None):
        self.app = app
        self.root = app.root
        self.on_close = on_close
        self.alive = True
        self.room = data
        self.view = data.get("battle") or {}
        self.watchers = None
        self.played = step_of(data)
        self.queue = []
        self.busy = False
        self.sent = False
        self._panel = None
        self.photos = {}
        self.anims = {}
        self.anim_jobs = {}
        self.jobs = []
        self.shown = dict((k, None) for k in KEYS)
        self.effects = []
        self.fx = None
        self._fx_actor = None
        self.hiding = FX.Hiding(self._sprite_show)
        self._moves_by_name = None
        self._deadline = 0.0
        self._seen_sent = False
        self._result_shown = False
        self._pending = None
        self._gen = {}
        # 고르는 중인 것: 자리마다 정한 것 · 지금 고르는 자리 · 대상을 기다리는 기술 · 켜 둔 메가/테라/Z
        self.picks = []
        self.await_target = None
        self.flags = {"mega": False, "tera": False, "z": False}
        self.switching = False

        s = U.h
        self.ww, self.wh = s(W), s(SCENE_H + MSG_H + CMD_H)
        self.win = tk.Toplevel(self.root)
        U.style_window(self.win, "챔피언리그 · 독도 (더블) — %s" % (data.get("foeName") or ""), self.ww, self.wh)
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        self.win.protocol("WM_DELETE_WINDOW", self.request_close)
        app.live_battle = self

        self._scene()
        self._message()
        self._commands()

        events = data.get("events") or []
        if self.played == 0 and events:
            self.play(events, data)                 # 새 판 - 네 마리가 나오는 것부터
        elif (data.get("state") or "") == "done" or self.view.get("over"):
            self.sync(data)
            self.show_result()
        else:
            self.sync(data)
            self.show_commands()
        self._poll()
        self.focus()

    # ---------------- 틀 ----------------
    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            PLAT.surface(self.win)
        except Exception:                                   # noqa: BLE001
            pass

    def later(self, ms, fn):
        if not self.alive:
            return None
        j = self.root.after(ms, lambda: self.alive and fn())
        self.jobs.append(j)
        if len(self.jobs) > 600:
            del self.jobs[:300]
        return j

    def say(self, text):
        try:
            self.msg.configure(text=natural(text or ""))
        except tk.TclError:
            pass

    def set_watchers(self, mid, n):
        """더블 판은 관전이 없다 (앱이 부르는 약속만 맞춘다)."""
        return None

    # ---------------- 장면 ----------------
    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, s(SCENE_H)
        cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg="#1b2334", highlightthickness=0)
        cv.pack(fill="x")
        self.cv = cv
        sw, sh = self.sw, self.sh
        cv.create_rectangle(0, int(sh * 0.60), sw, sh, fill="#222b3f", outline="")
        cv.create_line(0, int(sh * 0.60), sw, int(sh * 0.60), fill="#2c3650")
        self.pos, self.sprite, self.box = {}, {}, {}
        for key in ("foe1", "foe0", "me0", "me1"):
            fx, fy = SPOT[key]
            x, y = int(sw * fx), int(sh * fy)
            self.pos[key] = (x, y)
            rx = s(96) if side_of(key) == "me" else s(82)
            cv.create_oval(x - rx, y - s(16), x + rx, y + s(16), fill="#2f3a55", outline="#39466a")
        for key in ("foe1", "foe0", "me0", "me1"):
            x, y = self.pos[key]
            self.sprite[key] = cv.create_image(x, y + s(6), anchor="s")
        bw, bh, gap = s(236), s(64), s(8)
        self.box["foe1"] = self._namebox(s(12), s(10), bw, bh, False)
        self.box["foe0"] = self._namebox(s(12) + bw + gap, s(10), bw, bh, False)
        self.box["me0"] = self._namebox(sw - 2 * bw - gap - s(12), sh - bh - s(10), bw, bh, True)
        self.box["me1"] = self._namebox(sw - bw - s(12), sh - bh - s(10), bw, bh, True)
        # 남은 마릿수 (편마다 동그라미 여섯)
        self.dots = {"foe": [], "me": []}
        for i in range(6):
            x = s(20) + i * s(16)
            self.dots["foe"].append(cv.create_oval(x, s(10) + bh + s(8), x + s(10), s(10) + bh + s(18),
                                                   fill="", outline=""))
            x = sw - s(12) - (6 - i) * s(16)
            self.dots["me"].append(cv.create_oval(x, sh - bh - s(28), x + s(10), sh - bh - s(18),
                                                  fill="", outline=""))
        self.who_tag = {"foe": cv.create_text(s(20) + 6 * s(16) + s(8), s(10) + bh + s(13), anchor="w",
                                              fill="#8e97b3", font=(U.FAMILY, U.pt(8)), text=""),
                        "me": cv.create_text(sw - s(12) - 6 * s(16) - s(8), sh - bh - s(23), anchor="e",
                                             fill="#8e97b3", font=(U.FAMILY, U.pt(8)), text="")}
        self.banner = []

    def _namebox(self, x, y, w, h, mine):
        s = U.h
        cv = self.cv
        it = {"mine": mine}
        it["bg"] = cv.create_rectangle(x, y, x + w, y + h, fill="#141a28", outline="#39415e", width=2)
        it["name"] = cv.create_text(x + s(10), y + s(15), anchor="w", fill="#f2f4fb",
                                    font=(U.FAMILY, U.pt(11), "bold"), text="")
        it["lv"] = cv.create_text(x + w - s(10), y + s(15), anchor="e", fill="#c9cfdf",
                                  font=(U.FAMILY, U.pt(9), "bold"), text="")
        bx0, by0, bw = x + s(10), y + s(28), w - s(20)
        it["bar_bg"] = cv.create_rectangle(bx0, by0, bx0 + bw, by0 + s(9), fill="#2a3147", outline="")
        it["bar"] = cv.create_rectangle(bx0, by0, bx0 + bw, by0 + s(9), fill="#5fd97a", outline="")
        it["bar_geom"] = (bx0, by0, bw, s(9))
        it["status"] = cv.create_text(x + s(10), y + h - s(13), anchor="w", fill="#ffc043",
                                      font=(U.FAMILY, U.pt(8), "bold"), text="")
        it["hp"] = cv.create_text(x + w - s(10), y + h - s(13), anchor="e", fill="#c9cfdf",
                                  font=(U.FAMILY, U.pt(8)), text="")
        return it

    def _message(self):
        f = tk.Frame(self.win, bg="#0f141d", height=U.h(MSG_H), highlightthickness=0)
        f.pack(fill="x")
        f.pack_propagate(False)
        tk.Frame(f, bg=U.ACCENT, width=4).pack(side="left", fill="y")
        self.msg = tk.Label(f, text="", bg="#0f141d", fg=U.FG, font=(U.FAMILY, U.pt(12)),
                            anchor="w", justify="left")
        self.msg.pack(side="left", fill="both", expand=True, padx=14)
        U.wrap_to_width(self.msg)

    def _commands(self):
        self.cmd = tk.Frame(self.win, bg=U.BG)
        self.cmd.pack(fill="both", expand=True, padx=12, pady=(8, 10))
        right = tk.Frame(self.cmd, bg=U.BG, width=U.h(196))
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)
        self.left = tk.Frame(self.cmd, bg=U.BG)
        self.left.pack(side="left", fill="both", expand=True)
        self.timer = tk.Label(right, text="", bg=U.BG, fg=U.ACCENT, font=(U.FAMILY_BLACK, U.pt(16)), anchor="w")
        self.timer.pack(fill="x")
        self.turn_lbl = tk.Label(right, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w")
        self.turn_lbl.pack(fill="x")
        row = tk.Frame(right, bg=U.BG)
        row.pack(fill="x", pady=(6, 0))
        self.switch_btn = U.ghost_button(row, "교체", self.open_switch, height=32)
        self.switch_btn.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.undo_btn = U.ghost_button(row, "되돌리기", self.undo, height=32)
        self.undo_btn.pack(side="left", fill="x", expand=True, padx=(3, 0))
        self.forfeit_btn = U.PushButton(right, "기권", self.forfeit, fill=U.DANGER_BG, fg=U.DANGER,
                                        shadow="#1a1013", hover="#3a2028", height=30,
                                        border=U.DANGER_LINE, font=U.FONT_S)
        self.forfeit_btn.pack(fill="x", pady=(6, 0))
        self.hint = tk.Label(right, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS, anchor="nw", justify="left")
        self.hint.pack(fill="both", expand=True, pady=(8, 0))
        U.wrap_to_width(self.hint)

    # ---------------- 그림 ----------------
    def set_mon(self, key, mon):
        """그 자리에 이 포켓몬을 세운다 (None · 쓰러짐이면 비운다)."""
        self.shown[key] = dict(mon) if mon else None
        self._paint_box(key)
        self._stop_anim(key)
        try:
            self.cv.itemconfigure(self.sprite[key], image="")
            self.hiding.apply(key)
        except tk.TclError:
            return
        if not mon or mon.get("fainted"):
            return
        who = side_of(key)
        num, shiny, tera = mon.get("num"), T.skin(mon), mon.get("tera")
        size = U.h(MON_H[who])
        gen = self._gen[key] = self._gen.get(key, 0) + 1

        def work():
            path = sprite_cache.ensure(self.app.api, num, shiny, True) if who == "me" else None
            back = bool(path)
            if not path:
                path = sprite_cache.ensure(self.app.api, num, shiny)
            if not path:
                return None
            anim = sprites.load_animation(path, size, 0.2, 4.0, max_size=(U.h(MON_W[who]), int(size * 1.4)), body=True)
            # 앞모습 도트는 왼쪽을 본다 - 내 쪽은 뒤집어 상대를 보게 한다 (뒷모습 도트는 그대로)
            frames = anim.frames[sprites.LEFT if (who == "me" and not back) else sprites.RIGHT]
            rgba = ui_gimmick.tera_look([sprites.to_rgba(f, anim.key) for f in frames], tera)
            return rgba, list(anim.durations) or [100]

        def done(res, err):
            if not self.alive or err or res is None or self._gen.get(key) != gen:
                return
            rgba, durs = res
            self.anims[key] = ([ImageTk.PhotoImage(im) for im in rgba], durs)
            self._tick(key, 0)
        run_async(self.root, work, done)

    def _stop_anim(self, key):
        j = self.anim_jobs.get(key)
        if j:
            try:
                self.root.after_cancel(j)
            except Exception:                               # noqa: BLE001
                pass
        self.anim_jobs[key] = None
        self.anims[key] = None

    def _tick(self, key, i):
        a = self.anims.get(key)
        if not self.alive or not a:
            return
        photos, durs = a
        i %= len(photos)
        try:
            self.cv.itemconfigure(self.sprite[key], image=photos[i])
        except tk.TclError:
            return
        if len(photos) > 1:
            d = durs[i % len(durs)] if durs else 100
            self.anim_jobs[key] = self.root.after(max(40, int(d or 100)), lambda: self._tick(key, i + 1))

    def _paint_box(self, key, hp=None, mark=None):
        it, mon, cv = self.box[key], self.shown.get(key), self.cv
        if mark is not None:
            cv.itemconfigure(it["bg"], outline=mark, width=3 if mark != "#39415e" else 2)
        if not mon:
            for k in ("name", "lv", "status", "hp"):
                cv.itemconfigure(it[k], text="")
            x0, y0, _bw, bh = it["bar_geom"]
            cv.coords(it["bar"], x0, y0, x0, y0 + bh)
            return
        gender = {"M": " ♂", "F": " ♀"}.get(mon.get("gender"), "")
        cv.itemconfigure(it["name"], text=(mon.get("name") or "") + gender)
        cv.itemconfigure(it["lv"], text="Lv.%d" % (mon.get("level") or 0))
        bits = []
        if ui_gimmick.tera_tag(mon):
            bits.append(ui_gimmick.tera_tag(mon))
        if mon.get("statusKr"):
            bits.append(mon["statusKr"])
        for k, v in (mon.get("stages") or {}).items():
            bits.append("%s%+d" % (STAGE_KR.get(k, k), v))
        cv.itemconfigure(it["status"], text="  ".join(bits))
        self._bar(key, mon.get("hp") if hp is None else hp, mon.get("maxhp") or 1)

    def _bar(self, key, hp, maxhp):
        it = self.box[key]
        x0, y0, bw, bh = it["bar_geom"]
        frac = max(0.0, min(1.0, float(hp or 0) / float(maxhp or 1)))
        self.cv.coords(it["bar"], x0, y0, x0 + max(0, int(bw * frac)), y0 + bh)
        self.cv.itemconfigure(it["bar"], fill=hp_color(frac))
        self.cv.itemconfigure(it["hp"], text=("%d / %d" % (max(0, int(hp or 0)), maxhp)) if it["mine"]
                              else "%d%%" % int(round(frac * 100)))

    def _animate_bar(self, key, to_hp):
        mon = self.shown.get(key)
        if not mon:
            return
        start, steps = mon.get("hp", 0), 10

        def step(k):
            if not self.alive:
                return
            self._paint_box(key, int(round(start + (to_hp - start) * k / float(steps))))
            if k < steps:
                self.later(26, lambda: step(k + 1))
            else:
                mon["hp"] = to_hp
        step(1)

    def _dots(self):
        for who in ("me", "foe"):
            side = self.view.get(who) or {}
            team = side.get("team") or []
            for i, item in enumerate(self.dots[who]):
                if i >= len(team):
                    self.cv.itemconfigure(item, fill="", outline="")
                elif team[i].get("fainted"):
                    self.cv.itemconfigure(item, fill="#2a3147", outline="#3a4460")
                else:
                    self.cv.itemconfigure(item, fill="#e85b5b" if who == "foe" else "#5fd97a", outline="#10131b")
            tag = "나" if who == "me" else (side.get("name") or "상대")
            if who == "foe" and side.get("chosen"):
                tag += "  ·  고름"
            elif who == "foe" and side.get("need"):
                tag += "  ·  고르는 중"
            self.cv.itemconfigure(self.who_tag[who], text=tag)

    # ---------------- 연출 ----------------
    def _center(self, key):
        bb = self.cv.bbox(self.sprite[key])
        if bb:
            return ((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)
        x, y = self.pos[key]
        return (x, y - U.h(MON_H[side_of(key)]) / 2.0)

    def lunge(self, who, done):
        """battle_fx 가 접촉기에서 부른다."""
        if self._fx_actor:
            self._lunge(self._fx_actor)
        self.later(190, done)

    def _sprite_show(self, key, on):
        item = self.sprite.get(key)
        if item is not None:
            self.cv.itemconfigure(item, state="normal" if on else "hidden")

    def fx_shift(self, key, dx, dy):
        item = self.sprite.get(key)
        if item is not None:
            self.cv.move(item, dx, dy)

    def fx_box(self, key):
        a, item = self.anims.get(key), self.sprite.get(key)
        xy = self.cv.coords(item) if item is not None else ()
        if not a or len(xy) < 2:
            return None
        w, h = a[0][0].width(), a[0][0].height()
        return (xy[0] - w / 2.0, xy[1] - h, xy[0] + w / 2.0, xy[1])

    def _lunge(self, key):
        item = self.sprite[key]
        d = U.h(16) if side_of(key) == "me" else -U.h(16)
        seq = [d / 3.0] * 3 + [-d / 3.0] * 3

        def step(i):
            if not self.alive or i >= len(seq):
                return
            try:
                self.cv.move(item, seq[i], -seq[i] * 0.4)
            except tk.TclError:
                return
            self.later(26, lambda: step(i + 1))
        step(0)

    def _shake(self, key):
        item = self.sprite[key]
        offs = [6, -6, 5, -5, 3, -3, 0, 0]

        def step(i, prev=0):
            if not self.alive or i >= len(offs):
                return
            try:
                self.cv.move(item, offs[i] - prev, 0)
            except tk.TclError:
                return
            self.later(35, lambda: step(i + 1, offs[i]))
        step(0)

    def _faint(self, key):
        item = self.sprite[key]

        def step(i):
            if not self.alive:
                return
            if i >= 8:
                self._stop_anim(key)
                try:
                    self.cv.itemconfigure(item, image="")
                    self.cv.move(item, 0, -U.h(4) * 8)
                except tk.TclError:
                    pass
                return
            try:
                self.cv.move(item, 0, U.h(4))
            except tk.TclError:
                return
            self.later(30, lambda: step(i + 1))
        step(0)

    def _banner(self, key, text):
        s = U.h
        cv = self.cv
        x, y = self.pos[key]
        w = s(220)
        x0 = max(s(6), min(self.sw - w - s(6), x - w // 2))
        y0 = max(s(80), y - U.h(MON_H[side_of(key)]) - s(34))
        r = cv.create_rectangle(x0, y0, x0 + w, y0 + s(28), fill="#2a1f08", outline="#ffc043", width=2)
        t = cv.create_text(x0 + w // 2, y0 + s(14), text=text, fill="#ffe6b8", font=(U.FAMILY, U.pt(10), "bold"))
        self.banner += [r, t]

        def gone():
            for it in (r, t):
                try:
                    cv.delete(it)
                except tk.TclError:
                    pass
        self.later(1300, gone)

    def _play_fx(self, ev, src, dst):
        if self.fx is not None:
            self.fx.stop()
        state = {"done": False}

        def done():
            if state["done"] or not self.alive:
                return
            state["done"] = True
            self.fx = None
            self.later(70, self._next)

        try:
            k = FX_SCALE
            self._fx_actor = src
            (sx, sy), (tx, ty) = self._center(src), self._center(dst)
            self.fx = FX.Effect(_FxStage(self, k), self._find_move(ev), (sx / k, sy / k), (tx / k, ty / k), done,
                                who=side_of(src), ev=ev, keys=(src, dst))
            self.effects = [e for e in self.effects if not e.dead] + [self.fx]
            self.later(2400, done)
            self.fx.play()
        except Exception:                                   # noqa: BLE001
            done()
        return None

    def _find_move(self, ev):
        if self._moves_by_name is None:
            moves = getattr(getattr(self.app, "dex", None), "moves", None) or {}
            self._moves_by_name = {m.get("kr"): m for m in moves.values() if m.get("kr")}
        return self._moves_by_name.get(ev.get("move")) or {
            "type": ev.get("moveType") or "NORMAL", "cat": ev.get("cat") or "physical", "flags": []}

    # ---------------- 재생 ----------------
    def play(self, events, data):
        self.busy = True
        self.hide_commands()
        self.queue = FX.annotate(list(events))
        self._pending = data
        self._next()

    def _next(self):
        if not self.alive:
            return
        if not self.queue:
            return self._finish_play()
        wait = self._apply(self.queue.pop(0))
        if wait is not None:
            self.later(wait, self._next)

    def _apply(self, ev):
        t, key, to, text = ev.get("t"), ev.get("at"), ev.get("to"), ev.get("text")
        here = key in self.shown
        mon = self.shown.get(key) if here else None
        if t == "switch":
            self.say(text)
            if here:
                self.hiding.forget(key)
                self.set_mon(key, ev.get("mon"))
            return STEP_MS
        if t == "recall":
            self.say(text)
            if here:
                self.hiding.forget(key)
                self.set_mon(key, None)
            return STEP_MS - 140
        if t == "swap":                           # 사이드체인지: 두 자리의 포켓몬이 바뀐다
            self.say(text)
            if here and to in self.shown:
                a, b = self.shown.get(key), self.shown.get(to)
                self.set_mon(key, b)
                self.set_mon(to, a)
            return STEP_MS
        if t == "mega":
            self.say(text)
            if mon is not None:
                mon = dict(mon, num=ev.get("num") or mon.get("num"), mega=True,
                           name=ev.get("newName") or mon.get("name"))
                self.set_mon(key, mon)
                self._banner(key, ev.get("label") or "메가진화!")
            return STEP_MS + 300
        if t == "tera":
            self.say(text)
            if mon is not None:
                self.set_mon(key, dict(mon, tera=ev.get("type"), teraKr=ev.get("typeKr")))
                self._banner(key, "테라스탈! (%s)" % (ev.get("typeKr") or ""))
            return STEP_MS + 300
        if t == "zpower":
            self.say(text)
            if here:
                self._banner(key, "Z파워!")
            return STEP_MS + 200
        if t == "msg" and (ev.get("transform") or ev.get("look")):
            self.say(text)
            if mon is not None:
                self.set_mon(key, dict(mon, num=ev.get("transform") or ev["look"]))
            return STEP_MS + 200
        if t == "move":
            self.say(text)
            if FX_ON and mon and to in self.shown and to != key and self.shown.get(to):
                return self._play_fx(ev, key, to)
            return STEP_MS
        if t == "hit":
            if to in self.shown and self.shown.get(to):
                self._shake(to)
                self._animate_bar(to, ev.get("hp", 0))
            return 480
        if t in ("heal", "recoil", "chip"):
            if mon and "hp" in ev:
                self._animate_bar(key, ev["hp"])
            self.say(text)
            return STEP_MS
        if t == "ability":
            if here:
                self._banner(key, (text or "").strip("[]"))
            return 800
        if t == "ailment":
            if mon is not None:
                mon["status"], mon["statusKr"] = ev.get("status"), STATUS_KR.get(ev.get("status"))
                self._paint_box(key)
            self.say(text)
            return STEP_MS
        if t == "cure":
            if mon is not None:
                mon["status"], mon["statusKr"] = None, None
                self._paint_box(key)
            self.say(text)
            return STEP_MS
        if t == "stat":
            if mon is not None:
                st = dict(mon.get("stages") or {})
                k = ev.get("stat")
                st[k] = max(-6, min(6, st.get(k, 0) + int(ev.get("change") or 0)))
                mon["stages"] = dict((a, b) for a, b in st.items() if b)
                self._paint_box(key)
            self.say(text)
            return STEP_MS
        if t == "faint":
            if here:
                self.hiding.forget(key)
                self._faint(key)
                if mon is not None:
                    mon["hp"], mon["fainted"] = 0, True
                    self._bar(key, 0, mon.get("maxhp") or 1)
            self.say(text)
            return STEP_MS + 120
        if t == "over":
            self.hiding.forget_all()
            self.say(text)
            return STEP_MS + 200
        if text:
            self.say(text)
            return STEP_MS + (200 if t == "intro" else 0)
        return 50

    def _finish_play(self):
        data = self._pending or {}
        self._pending = None
        self.busy = False
        self.sync(data)
        if (data.get("state") or "") == "done" or self.view.get("over"):
            return self.show_result()
        self.show_commands()

    # ---------------- 서버 값으로 맞추기 ----------------
    def sync(self, room):
        self.room = room or self.room
        self.view = self.room.get("battle") or self.view
        self.played = max(self.played, step_of(self.room))
        if self.room.get("deadlineIn") is not None:
            self._deadline = time.time() + int(self.room["deadlineIn"])
        for who in ("me", "foe"):
            side = self.view.get(who) or {}
            team = side.get("team") or []
            active = side.get("active") or [None, None]
            for pos in (0, 1):
                key = "%s%d" % (who, pos)
                slot = active[pos] if pos < len(active) else None
                mon = team[slot] if slot is not None and slot < len(team) else None
                if mon and mon.get("fainted"):
                    mon = None
                cur = self.shown.get(key)
                if (cur or {}).get("num") != (mon or {}).get("num") or bool(cur) != bool(mon) \
                        or (cur or {}).get("tera") != (mon or {}).get("tera"):
                    self.set_mon(key, mon)
                else:
                    self.shown[key] = dict(mon) if mon else None
                    self._paint_box(key)
        self._dots()
        self._paint_turn()

    def _paint_turn(self):
        me, foe = self.view.get("me") or {}, self.view.get("foe") or {}
        self.turn_lbl.configure(text="%d턴  ·  남은 포켓몬 %d : %d" % (self.view.get("turn", 0),
                                                                 me.get("left", 0), foe.get("left", 0)))

    # ---------------- 폴링 ----------------
    def _poll(self):
        if not self.alive:
            return
        self._paint_timer()
        if self.busy or self._result_shown:
            self.later(POLL_MS, self._poll)
            return

        def done(r, err):
            if not self.alive:
                return
            m = (r or {}).get("match") if isinstance(r, dict) else None
            if not err and m and m.get("id") == self.room.get("id") and not self._stale(m) and not self.busy:
                got = step_of(m)
                if got > self.played or (m.get("state") == "done" and not self.view.get("over")):
                    self.played = got
                    self.sent = False
                    self.play(m.get("events") or [], m)
                else:
                    self.sync(m)
                    self._refresh()
            self.later(POLL_MS, self._poll)
        run_async(self.root, lambda: self.app.api.live(), done)

    def _stale(self, m):
        try:
            return int(m.get("rev") or 0) < int(self.room.get("rev") or 0)
        except (TypeError, ValueError, AttributeError):
            return False

    def _panel_key(self):
        me = self.view.get("me") or {}
        if not self.view.get("canAct"):
            return ("wait", self.view.get("phase"))
        if self.sent or me.get("chosen"):
            return ("sent",)
        return ("act", self.view.get("phase"), tuple(me.get("active") or ()), tuple(me.get("need") or ()))

    def _refresh(self):
        """서버 값이 바뀌었으면 아래 칸을 다시 그린다 (내가 고르던 것은 그대로 둔다)."""
        me = self.view.get("me") or {}
        want = self._panel_key()
        if want != self._panel:
            if self.view.get("canAct") and not me.get("chosen"):
                self.sent = False
            self.show_commands()

    def _paint_timer(self):
        left = max(0, int(self._deadline - time.time())) if self._deadline else 0
        try:
            if self.busy or self._result_shown:
                self.timer.configure(text="")
            else:
                self.timer.configure(text="%d초" % left, fg=U.DANGER if left <= 5 else U.ACCENT)
        except tk.TclError:
            pass

    # ---------------- 명령 ----------------
    def _clear(self):
        for w in self.left.winfo_children():
            w.destroy()
        for key in KEYS:
            self._paint_box(key, mark="#39415e")

    def hide_commands(self):
        self._panel = None
        self._clear()
        for b in (self.switch_btn, self.undo_btn, self.forfeit_btn):
            b.configure(state="disabled")

    def _acts(self):
        """이번에 고를 자리들 (서버가 준 것 그대로 - 쓰러진 자리는 None)."""
        return [a for a in ((self.view.get("me") or {}).get("acts") or []) if a]

    def _current(self):
        """지금 고를 자리의 것. 다 골랐으면 None."""
        done = set(p["pos"] for p in self.picks)
        return next((a for a in self._acts() if a["pos"] not in done), None)

    def _name_at(self, key):
        return (self.shown.get(key) or {}).get("name") or "?"

    def show_commands(self):
        self._panel = self._panel_key()
        self._paint_timer()
        me, foe = self.view.get("me") or {}, self.view.get("foe") or {}
        foe_name = foe.get("name") or "상대"
        if not self.view.get("canAct"):
            why = ("%s 님이 다음 포켓몬을 고르고 있습니다." % foe_name) if self.view.get("phase") == "switch" \
                else "상대를 기다리는 중입니다."
            self._paint_wait(why, None)
            return self.say(why)
        if self.sent or me.get("chosen"):
            self.sent = True
            self._paint_wait("%s 님을 기다리는 중..." % foe_name,
                             "둘 다 고르면 그 턴이 한꺼번에 진행됩니다. 시간을 넘기면 서버가 대신 골라 줍니다.")
            return self.say("상대를 기다리는 중...")
        if self.view.get("phase") == "switch":
            return self._ask_next()
        act = self._current()
        if act is None:
            return self._send_picks()
        if self.switching:
            return self._paint_switch(act["pos"], forced=False)
        if self.await_target is not None:
            return self._paint_targets(act, self.await_target)
        self._paint_moves(act)

    def _paint_wait(self, title, note):
        self._clear()
        self.forfeit_btn.configure(state="normal")
        self.switch_btn.configure(state="disabled")
        self.undo_btn.configure(state="disabled")
        box = tk.Frame(self.left, bg=U.BG)
        box.pack(fill="both", expand=True)
        tk.Label(box, text=title, bg=U.BG, fg=U.ACCENT, font=U.FONT_H).pack(anchor="w", pady=(16, 4))
        if note:
            lab = tk.Label(box, bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left", text=note)
            lab.pack(fill="x")
            U.wrap_to_width(lab)

    def _head(self, text, sub=None):
        head = tk.Frame(self.left, bg=U.BG)
        head.pack(fill="x")
        tk.Label(head, text=text, bg=U.BG, fg=U.FG, font=U.FONT_B).pack(side="left")
        if sub:
            tk.Label(head, text=sub, bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS).pack(side="left", padx=(10, 0))
        return head

    def _z_of(self, act, key):
        return next((z for z in (act.get("zMoves") or []) if z.get("key") == key), None)

    def _paint_moves(self, act):
        """지금 고르는 포켓몬의 기술 넷 (+ 메가진화 · 테라스탈 · Z기술)."""
        self._clear()
        key = "me%d" % act["pos"]
        self._paint_box(key, mark=U.ACCENT)
        acts = self._acts()
        n = acts.index(act) + 1
        head = self._head("%s의 행동" % self._name_at(key), "(%d/%d)" % (n, len(acts)) if len(acts) > 1 else None)
        used = dict((f, any(p.get(f) for p in self.picks)) for f in ("mega", "tera", "z"))
        for flag, label, ok in (("mega", "메가진화", act.get("canMega")),
                                ("tera", "테라스탈 %s" % (act.get("teraKr") or ""), act.get("canTera")),
                                ("z", "Z기술", bool(act.get("zMoves")))):
            if ok and not used[flag]:
                on = self.flags[flag]
                b = U.ghost_button(head, ("● " if on else "○ ") + label.strip(),
                                   lambda f=flag: self._toggle(f), height=26)
                b.pack(side="right", padx=(6, 0))
        grid = tk.Frame(self.left, bg=U.BG)
        grid.pack(fill="both", expand=True, pady=(4, 0))
        moves = list(act.get("moves") or [])
        if len(moves) > 4:                          # 쓸 기술이 없어 발버둥이 붙었다 - 칸은 넷까지 (발버둥은 꼭 보이게)
            moves = moves[:3] + moves[-1:]
        for i, m in enumerate(moves):
            self._move_cell(grid, i, m, act)
        for c in (0, 1):
            grid.grid_columnconfigure(c, weight=1, uniform="mv")
        self.forfeit_btn.configure(state="normal")
        self.switch_btn.configure(state="normal" if act.get("canSwitch") else "disabled")
        self.undo_btn.configure(state="normal" if self.picks else "disabled")
        self.hint.configure(text=act.get("noSwitch") or "기술에 마우스를 올리면 설명이 나옵니다.")
        self.say("%s은(는) 무엇을 할까?" % self._name_at(key))

    def _toggle(self, flag):
        self.flags[flag] = not self.flags[flag]
        if flag == "mega" and self.flags["mega"]:
            self.flags["tera"] = False              # 메가진화한 포켓몬은 테라스탈하지 못한다
        if flag == "tera" and self.flags["tera"]:
            self.flags["mega"] = False
        self.show_commands()

    def _move_cell(self, grid, i, m, act):
        z = self._z_of(act, m.get("key")) if self.flags["z"] else None
        locked = act.get("locked")
        usable = (m.get("pp") or 0) > 0 and not m.get("blocked") and (not locked or locked == m.get("key"))
        if self.flags["z"] and not z:
            usable = False                          # Z기술을 켜 두면 Z로 쓸 수 있는 기술만
        col = U.TYPE_COLOR.get((z or {}).get("type") or m.get("type"), U.BG3)
        bg = shade(col, 0.42) if usable else "#23283a"
        cell = tk.Frame(grid, bg=bg, highlightthickness=2, highlightbackground=col if usable else U.LINE,
                        cursor="hand2" if usable else "")
        cell.grid(row=i // 2, column=i % 2, sticky="nsew", padx=3, pady=3)
        top = tk.Frame(cell, bg=bg)
        top.pack(fill="x", padx=10, pady=(5, 0))
        name = tk.Label(top, text=(z or {}).get("name") or m.get("kr") or m.get("key"), bg=bg,
                        fg="#ffffff" if usable else U.FG_FAINT, font=(U.FAMILY, U.pt(12), "bold"), anchor="w")
        name.pack(side="left")
        tchip = tk.Label(top, text=m.get("typeKr") or "", bg=col, fg="#10131b", font=U.FONT_XS, padx=6)
        tchip.pack(side="right")
        bottom = tk.Frame(cell, bg=bg)
        bottom.pack(fill="x", padx=10, pady=(1, 5))
        cat = m.get("cat") or "status"
        cl = tk.Label(bottom, text=CAT_KR.get(cat, cat), bg=bg, fg=CAT_COLOR.get(cat, U.FG_DIM),
                      font=(U.FAMILY, U.pt(9), "bold"))
        cl.pack(side="left")
        bits = []
        if m.get("power"):
            bits.append("위력 %d" % m["power"])
        if m.get("aim") and m.get("aim") != "one":
            bits.append(AIM_KR.get(m["aim"], ""))
        el = tk.Label(bottom, text="  ·  ".join(b for b in bits if b), bg=bg,
                      fg="#d7dcea" if usable else U.FG_FAINT, font=U.FONT_XS)
        el.pack(side="left", padx=(8, 0))
        pp = tk.Label(bottom, text="PP %d/%d" % (m.get("pp") or 0, m.get("maxpp") or 0), bg=bg,
                      fg="#ffffff" if usable else U.DANGER, font=(U.FAMILY, U.pt(9), "bold"))
        pp.pack(side="right")
        for w in (cell, top, name, tchip, bottom, cl, el, pp):
            w.bind("<Enter>", lambda _e, mm=m: self.hint.configure(text=mm.get("blocked") or mm.get("desc") or ""))
            if usable:
                w.bind("<Button-1>", lambda _e, mm=m: self.use_move(mm))

    def use_move(self, m):
        """기술을 골랐다. 대상을 고를 것이 둘 이상이면 묻고, 아니면 그대로 정한다."""
        if self.busy or self.sent:
            return
        targets = list(m.get("targets") or [])
        if m.get("aim") == "one" and len(targets) > 1:
            self.await_target = m
            return self.show_commands()
        self._pick_move(m, targets[0] if (m.get("aim") == "one" and targets) else None)

    def _paint_targets(self, act, m):
        """고른 기술의 대상 (상대 0 · 상대 1 · 아군)."""
        self._clear()
        key = "me%d" % act["pos"]
        self._paint_box(key, mark=U.ACCENT)
        self._head("%s — 누구에게?" % (m.get("kr") or m.get("key")))
        row = tk.Frame(self.left, bg=U.BG)
        row.pack(fill="both", expand=True, pady=(6, 0))
        ally = "me%d" % (1 - act["pos"])
        for tok in m.get("targets") or []:
            tk_key = ally if tok == "ally" else tok
            label = ("아군 %s" if tok == "ally" else "상대 %s") % self._name_at(tk_key)
            self._paint_box(tk_key, mark="#ffc043")
            b = U.PushButton(row, label, lambda t=tok: self._pick_move(m, t), height=44)
            b.pack(side="left", fill="x", expand=True, padx=3)
        self.forfeit_btn.configure(state="normal")
        self.switch_btn.configure(state="disabled")
        self.undo_btn.configure(state="normal")
        self.hint.configure(text="[되돌리기] 를 누르면 기술을 다시 고릅니다.")
        self.say("%s을(를) 누구에게 쓸까?" % (m.get("kr") or m.get("key")))

    def _pick_move(self, m, target):
        act = self._current()
        if act is None:
            return
        pick = {"pos": act["pos"], "kind": "move", "move": m.get("key"), "target": target}
        for f in ("mega", "tera", "z"):
            if self.flags[f]:
                pick[f] = True
        self._add(pick)

    def _add(self, pick):
        self.picks.append(pick)
        self.await_target = None
        self.switching = False
        self.flags = {"mega": False, "tera": False, "z": False}
        self.show_commands()

    def undo(self):
        """앞의 것을 다시 고른다 (대상 고르기 · 교체 칸이면 그것만 닫는다)."""
        if self.busy or self.sent:
            return
        if self.await_target is not None or self.switching:
            self.await_target, self.switching = None, False
        elif self.picks:
            self.picks.pop()
        self.show_commands()

    # ---- 교체
    def open_switch(self):
        act = self._current()
        if self.busy or self.sent or act is None or not act.get("canSwitch"):
            return
        self.switching = True
        self.show_commands()

    def _taken(self):
        return set(p["slot"] for p in self.picks if p.get("kind") == "switch")

    def _paint_switch(self, pos, forced):
        self._clear()
        me = self.view.get("me") or {}
        key = "me%d" % pos
        self._paint_box(key, mark=U.ACCENT)
        cur = self.shown.get(key)
        if forced:
            ask = ("%s 대신 누구를 낼까?" % cur["name"]) if cur else "빈 자리에 누구를 낼까?"
        else:
            ask = "%s을(를) 누구로 바꿀까?" % self._name_at(key)
        self._head(ask)
        grid = tk.Frame(self.left, bg=U.BG)
        grid.pack(fill="both", expand=True, pady=(4, 0))
        active = [x for x in (me.get("active") or []) if x is not None]
        ok = [s for s in (me.get("switches") or []) if s not in self._taken()]
        for i, m in enumerate(me.get("team") or []):
            self._party_cell(grid, i, m, i in active, i in ok, pos)
        for c in (0, 1, 2):
            grid.grid_columnconfigure(c, weight=1, uniform="pt")
        self.forfeit_btn.configure(state="normal")
        self.switch_btn.configure(state="disabled")
        self.undo_btn.configure(state="normal" if (self.picks or not forced) else "disabled")
        self.hint.configure(text="쓰러진 포켓몬과 지금 나와 있는 포켓몬은 고를 수 없습니다.")
        self.say(ask)

    def _party_cell(self, grid, i, m, active, ok, pos):
        bg = U.BG2 if ok else "#171b27"
        cell = tk.Frame(grid, bg=bg, highlightthickness=2, highlightbackground=U.ACCENT if active else U.LINE,
                        cursor="hand2" if ok else "")
        cell.grid(row=i // 3, column=i % 3, sticky="nsew", padx=3, pady=3)
        tk.Label(cell, text=m.get("name") or "", bg=bg, fg=U.FG if ok else U.FG_FAINT, font=U.FONT_B,
                 anchor="w").pack(anchor="w", padx=8, pady=(5, 0))
        sub = "Lv.%d" % (m.get("level") or 0)
        if m.get("fainted"):
            sub += "  · 쓰러짐"
        elif active:
            sub += "  · 싸우는 중"
        elif i in self._taken():
            sub += "  · 나갈 차례"
        elif m.get("statusKr"):
            sub += "  · %s" % m["statusKr"]
        tk.Label(cell, text=sub, bg=bg, fg=U.FG_DIM, font=U.FONT_XS, anchor="w").pack(anchor="w", padx=8, pady=(0, 6))
        if ok:
            for w in (cell,) + tuple(cell.winfo_children()):
                w.bind("<Button-1>", lambda _e, s=i: self.do_switch(pos, s))

    def do_switch(self, pos, slot):
        if self.busy or self.sent:
            return
        self._add({"pos": pos, "kind": "switch", "slot": slot})

    def _ask_next(self):
        """쓰러졌거나 물러난 자리마다 다음 포켓몬을 고른다. 다 골랐으면 보낸다."""
        need = list((self.view.get("me") or {}).get("need") or [])
        done = set(p["pos"] for p in self.picks)
        left = [pos for pos in need if pos not in done]
        if not left:
            return self._send_picks()
        self._paint_switch(left[0], forced=True)

    # ---------------- 보내기 ----------------
    def _send_picks(self):
        if self.busy or self.sent:
            return
        picks, self.picks = list(self.picks), []
        self.sent = True
        self.hide_commands()
        self.say("...")

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.sent = False
                self.show_commands()            # 다시 그린 뒤에 거절한 까닭을 띄운다
                return self.say(getattr(err, "message", str(err)))
            self._got(r)
        run_async(self.root, lambda: self.app.api.live_act2(picks), done)

    def _got(self, r):
        got = step_of(r)
        if got > self.played or r.get("state") == "done":
            self.played = got
            self.sent = False
            return self.play(r.get("events") or [], r)
        self.sync(r)
        self.show_commands()

    def forfeit(self):
        from .ui_box import confirm
        if not confirm(self.win, "기권", "이 승부를 포기할까요? 상대의 승리로 기록됩니다.", danger=True, ok_text="기권"):
            return
        self.sent = True
        self.hide_commands()

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.sent = False
                self.show_commands()
                return self.say(getattr(err, "message", str(err)))
            if r.get("state") == "done":
                return self._leave_after_forfeit(r)
            self.sent = False
            self._got(r)
        run_async(self.root, lambda: self.app.api.live_act("forfeit"), done)

    def _leave_after_forfeit(self, room):
        """내가 기권했다 - 결과 창 없이 닫는다. **결과를 봤다고 먼저 알린다** (안 그러면 앱이 창을 다시 연다)."""
        self.played = max(self.played, step_of(room))
        self.sync(room)
        self._result_shown = True
        self.hide_commands()
        self.say("승부를 포기했습니다.")
        self._seen_sent = True
        run_async(self.root, lambda: self.app.api.live_seen(), lambda _r, _e: self.close())

    # ---------------- 끝 ----------------
    def show_result(self):
        self.hiding.forget_all()
        if self._result_shown:
            return
        self._result_shown = True
        self.hide_commands()
        out = self.room.get("outcome") or self.view.get("result")
        title = {"win": "승리!", "lose": "패배...", "draw": "무승부"}.get(out, "끝")
        foe = (self.view.get("foe") or {}).get("name") or "상대"
        reason = self.room.get("reason") or self.view.get("reason")
        lines = []
        if reason == "forfeit":
            lines.append("기권으로 끝났습니다.")
        elif reason == "turns":
            lines.append("%d턴을 넘겨 남은 포켓몬 수로 정했습니다." % (self.view.get("maxTurns") or 0))
        lines.append("%s 님과의 더블배틀 · %d턴" % (foe, self.view.get("turn", 0)))
        me, fo = self.view.get("me") or {}, self.view.get("foe") or {}
        lines.append("남은 포켓몬 %d : %d" % (me.get("left", 0), fo.get("left", 0)))
        lines.append("독도의 더블 전적에 남습니다. 상금과 랭크 점수는 움직이지 않습니다.")
        color = {"win": U.ACCENT, "lose": U.DANGER}.get(out, U.FG)
        panel = tk.Frame(self.left, bg=U.BG2, highlightthickness=2, highlightbackground=color)
        panel.pack(fill="both", expand=True)
        inner = tk.Frame(panel, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16, pady=10)
        side = tk.Frame(inner, bg=U.BG2)
        side.pack(side="right", fill="y", padx=(12, 0))
        U.PushButton(side, "닫기", self.close, height=38).pack(side="bottom")
        body = tk.Frame(inner, bg=U.BG2)
        body.pack(side="left", fill="both", expand=True)
        tk.Label(body, text=title, bg=U.BG2, fg=color, font=(U.FAMILY_BLACK, U.pt(20))).pack(anchor="w")
        for ln in lines:
            lab = tk.Label(body, text=natural(ln), bg=U.BG2, fg=U.FG, font=U.FONT_S, anchor="w", justify="left")
            lab.pack(fill="x", pady=(2, 0))
            U.wrap_to_width(lab)
        self.say(title)
        if not self._seen_sent:
            self._seen_sent = True
            run_async(self.root, lambda: self.app.api.live_seen(), lambda _r, _e: None)

    def request_close(self):
        if self.alive and not (self.view.get("over") or self._result_shown):
            from .ui_box import confirm
            if not confirm(self.win, "창 닫기",
                           "판은 그대로 이어집니다. 시간이 지나면 서버가 대신 골라 주고, "
                           "판이 살아 있으면 창이 저절로 다시 열려요.", danger=False, ok_text="닫기"):
                return
        self.close()

    def close(self):
        if not self.alive:
            return
        self.alive = False
        for e in self.effects + ([self.fx] if self.fx is not None else []):
            try:
                e.stop()
            except Exception:                               # noqa: BLE001
                pass
        self.effects, self.fx = [], None
        for key in KEYS:
            self._stop_anim(key)
        for j in self.jobs:
            try:
                self.root.after_cancel(j)
            except Exception:                               # noqa: BLE001
                pass
        self.jobs = []
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        if getattr(self.app, "live_battle", None) is self:
            self.app.live_battle = None
        if self.on_close:
            try:
                self.on_close()
            except Exception:                               # noqa: BLE001
                pass
