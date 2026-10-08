# -*- coding: utf-8 -*-
"""실시간 1:1 배틀 창 — 상대도 사람이다.

## 관장 배틀과 다른 점

관장은 내가 고르면 그 자리에서 한 턴이 끝났다. 여기서는 **상대도 고른다.**
내가 보낸 뒤에는 '상대가 고르는 중' 으로 기다리고, 둘 다 들어오면 서버가
그 턴을 돌려 준다. 그래서 창이 열려 있는 동안 방을 자주 물어본다(POLL_MS).

    고르는 단계   기술 네 칸 · 교체 · 기권. 제한 시간이 돈다.
    기다리는 중   내 것은 보냈고 상대를 기다린다.
    교체 단계     쓰러진 쪽만 다음 포켓몬을 고른다. 상대는 그냥 기다린다.

## 시점

서버가 **이미 내 쪽으로 뒤집어서** 준다 (live_battle.events_for). 그래서
이 창은 관장 배틀과 똑같이 who="me" 를 내 쪽으로 그리면 된다.

## 창을 닫으면

판은 서버에 남는다. 제한 시간이 지나면 서버가 대신 골라 주므로 상대가
하염없이 기다리지는 않는다. 판이 살아 있으면 창이 저절로 다시 열린다
(app.announce_live 가 폴링으로 본다).
"""
import time
import tkinter as tk

from PIL import ImageTk

from common import tint as T
from common.korean import natural

from . import battle_fx as FX
from . import effects, sprite_cache, sprites
from . import battle_zoom as Z
from . import platform_os as PLAT
from .ui_common import run_async
from .ui_gym import shade
from .ui_gym_battle import CAT_COLOR, CAT_KR, FX_SCALE, _FxStage, hp_color
from . import ui_mega
from .ui_mega import MegaToggle

# **이 창은 가장자리를 끌어서 크기를 바꾼다** (battle_zoom.Resizable). 창 크기에서 배율이 나오고,
# U 는 ui_common 그대로인데 h · pt · FONT_* · 단추 높이가 그 배율을 탄다 - 그래서 아래 코드는
# 평소처럼 U.h(...) 로 적는다. 픽셀로 적어 둔 값(도트 높이처럼 글꼴 배율을 안 타는 것)에는 Z.px 를 건다.
U = Z.U

# 설계 크기. 창 높이 = 장면 + 말풍선 + 명령 칸.
#
# **명령 칸(기술 카드)은 필요한 만큼만** (1.10.3). 예전 278 은 카드 하나가 안에 든 글의 두 배
# 높이였고, 그만큼 장면이 좁았다. 줄인 만큼(30)은 장면에 줬다 (창 높이는 그대로다).
# 더 줄이면 오른쪽 줄의 기술 설명이 눌린다: 윈도우에서 가장 긴 설명이 다섯 줄(80px)인데,
# 남은 시간(27)·턴(16)·단추 둘(40 + 36)·사이 여백(20)과 위아래 여백(18)을 빼면 그 칸에
# 248 - 157 = 91 이 남는다. (그래서 단추와 여백도 조금씩 줄였다 - _commands)
#
# **가장 낮은 장면(MIN_SCENE_H)은 포켓몬이 이름표에 안 가려지는 높이다.** 창을 가장 작게 줄이면
# 장면이 이 비율이 된다. 225 였을 때는 내 포켓몬의 머리가 상대 이름표 뒤로 들어갔다:
# 내 도트의 꼭대기는 0.93 x 장면 + 10 - 128, 상대 이름표의 바닥은 12 + 104 → 장면이 256 은 돼야 한다
# (상대 도트의 발과 내 이름표도 같은 식으로 244).
W = 880
SCENE_H = 336
MSG_H = 54
CMD_H = 248
MIN_SCENE_H = 261
STEP_MS = 600
POLL_MS = 1500
MON_H = {"me": 128, "foe": 108}
MON_W = {"me": 340, "foe": 280}


def step_of(m):
    """판이 몇 걸음 나아갔나.

    **옛 서버(1.6.1 이하)는 step 을 안 준다.** 그때는 turn 으로 돌아간다 -
    안 그러면 step 이 늘 0 이라 화면이 한 턴도 재생하지 않는다. 교체를
    못 알아채는 옛 동작으로 돌아갈 뿐, 판은 돌아간다.
    """
    return int((m or {}).get("step") or (m or {}).get("turn") or 0)


class LiveBattleWindow(Z.Resizable):
    ZOOM_KIND = "live"
    ZOOM_W, ZOOM_SCENE, ZOOM_MSG, ZOOM_CMD, ZOOM_MIN_SCENE = W, SCENE_H, MSG_H, CMD_H, MIN_SCENE_H

    def __init__(self, app, data, on_close=None):
        self.app = app
        self.root = app.root
        self.on_close = on_close
        self.alive = True
        self.room = data
        self.view = data.get("battle") or {}
        # **turn 이 아니라 step 을 센다.** 교체는 턴을 안 올리므로 turn 만
        # 보면 상대가 다음 포켓몬을 내보낸 것을 못 알아채고, 제한 시간이
        # 다 갈 때까지 "고르고 있습니다" 인 채로 앉아 있게 된다.
        self.played = step_of(data)
        self.queue = []
        self.busy = False
        self.sent = False
        self._panel = None
        self.photos = {}
        self.anims = {"me": None, "foe": None}
        self.anim_jobs = {"me": None, "foe": None}
        self.jobs = []
        self.shown = {"me": None, "foe": None}
        self.effects = []
        self.fx = None
        self._moves_by_name = None
        self._deadline = 0.0
        self._seen_sent = False
        self._result_shown = False
        self._result_painted = False  # 결과 칸을 그려 뒀나 (기권하고 나갈 때는 안 그린다)
        self._switching = False       # 스스로 교체 칸을 열어 뒀나
        self._pending = None

        # 처음 크기: 지난번에 끌어 놓은 크기(없으면 기본 크기). 배율도 여기서 잡힌다.
        ww, wh, gx, gy = self.zoom_open()
        self.win = tk.Toplevel(self.root)
        U.style_window(self.win, "실시간 배틀 — %s" % (data.get("foeName") or ""),
                       ww, wh)
        self.win.geometry("%dx%d+%d+%d" % (ww, wh, gx, gy))
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        self.win.protocol("WM_DELETE_WINDOW", self.request_close)
        app.live_battle = self

        self._scene()
        self._message()
        self._commands()
        self._ball_photos()
        self.zoom_watch()                    # 이제부터 창을 끌어 크기를 바꾸면 따라간다

        events = data.get("events") or []
        if self.played == 0 and events:
            self.play(events, data)
        else:
            self.sync(data)
            self.show_commands()
        self._poll()
        self._enter()
        self.focus()

    def _enter(self):
        """창이 불쑥 뜨지 않게 한다: 비치는 데서 또렷해지고, 검은 띠가 걷히며 장면이 드러난다 (enter_fx)."""
        from . import enter_fx as EF
        try:
            self.win.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        fx = EF.Blinds(self.cv)
        t0 = time.monotonic()

        def done():
            fx.close()
            try:
                self.win.attributes("-alpha", 1.0)
            except tk.TclError:
                pass

        def step():
            if not self.alive:
                return fx.close()
            t = time.monotonic() - t0
            k = 1.0 - (t - EF.FADE_S * 0.6) / EF.OPEN_S
            if k <= 0.0:
                return done()
            try:
                self.win.attributes("-alpha", max(0.0, min(1.0, t / EF.FADE_S)))
            except tk.TclError:
                pass
            fx.draw(0, 0, self.sw, self.sh, k)
            self.later(16, step)
        fx.draw(0, 0, self.sw, self.sh, 1.0)
        step()

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
        return j

    def say(self, text):
        self._said = text or ""              # (창 크기를 바꿔 다시 지을 때 되돌린다)
        try:
            self.msg.configure(text=natural(text or ""))
        except tk.TclError:
            pass

    # ---------------- 장면 ----------------
    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = getattr(self, "cv", None)
        if cv is None:
            cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg="#1b2334",
                           highlightthickness=0)
            cv.pack(fill="x")
            self.cv = cv
        else:
            # 창 크기를 바꿨다 - **같은 캔버스를 비우고** 새 크기로 다시 그린다 (battle_zoom)
            cv.delete("all")
            cv.configure(width=self.sw, height=self.sh)
        sw, sh = self.sw, self.sh
        cv.create_rectangle(0, int(sh * 0.56), sw, sh, fill="#222b3f", outline="")
        cv.create_line(0, int(sh * 0.56), sw, int(sh * 0.56), fill="#2c3650")
        self.foe_pos = (int(sw * 0.72), int(sh * 0.50))
        self.me_pos = (int(sw * 0.28), int(sh * 0.93))
        fx, fy = self.foe_pos
        mx, my = self.me_pos
        cv.create_oval(fx - s(140), fy - s(22), fx + s(140), fy + s(22),
                       fill="#2f3a55", outline="#39466a")
        cv.create_oval(mx - s(170), my - s(28), mx + s(170), my + s(28),
                       fill="#2f3a55", outline="#39466a")
        self.sprite = {"foe": cv.create_image(fx, fy + s(8), anchor="s"),
                       "me": cv.create_image(mx, my + s(10), anchor="s")}
        self.box = {"foe": self._namebox(s(16), s(12), False),
                    "me": self._namebox(sw - s(316), sh - s(104) - s(10), True)}
        self.banner = []

    def _namebox(self, x, y, mine):
        s = U.h
        cv = self.cv
        # 상대 칸도 내 칸과 같은 높이로 둔다. 88 로 두면 남은 마릿수를
        # 나타내는 몬스터볼 줄이 체력바와 겹친다.
        w, h = s(300), s(104)
        it = {}
        it["bg"] = cv.create_rectangle(x, y, x + w, y + h, fill="#141a28",
                                       outline="#39415e", width=2)
        it["who"] = cv.create_text(x + s(14), y + s(16), anchor="w", fill="#8e97b3",
                                   font=(U.FAMILY, U.pt(8)), text="")
        it["name"] = cv.create_text(x + s(14), y + s(36), anchor="w", fill="#f2f4fb",
                                    font=(U.FAMILY, U.pt(12), "bold"), text="")
        it["lv"] = cv.create_text(x + w - s(14), y + s(36), anchor="e", fill="#c9cfdf",
                                  font=(U.FAMILY, U.pt(10), "bold"), text="")
        it["status"] = cv.create_text(x + s(14), y + s(56), anchor="w", fill="#ffc043",
                                      font=(U.FAMILY, U.pt(8), "bold"), text="")
        bx0, by0 = x + s(14), y + s(68)
        bw = w - s(28)
        it["bar_bg"] = cv.create_rectangle(bx0, by0, bx0 + bw, by0 + s(10),
                                           fill="#2a3147", outline="")
        it["bar"] = cv.create_rectangle(bx0, by0, bx0 + bw, by0 + s(10),
                                        fill="#5fd97a", outline="")
        it["bar_geom"] = (bx0, by0, bw, s(10))
        it["hp"] = cv.create_text(x + w - s(14), y + h - s(14), anchor="e",
                                  fill="#c9cfdf", font=(U.FAMILY, U.pt(9)),
                                  text="" if mine else None)
        it["balls"] = []
        for i in range(6):
            it["balls"].append(cv.create_image(x + s(22) + i * s(20),
                                               y + h - s(14), anchor="center"))
        return it

    def _ball_photos(self):
        from PIL import Image, ImageEnhance
        size = U.h(16)
        key = (255, 0, 255)
        ball = sprites.to_rgba(effects.ball_image(size, key), key)
        grey = ImageEnhance.Brightness(ball.convert("LA").convert("RGBA")).enhance(0.55)
        grey.putalpha(ball.split()[3])
        self.photos["ball"] = ImageTk.PhotoImage(ball)
        self.photos["ball_out"] = ImageTk.PhotoImage(grey)
        self.photos["ball_none"] = ImageTk.PhotoImage(
            Image.new("RGBA", (1, 1), (0, 0, 0, 0)))

    def _message(self):
        f = tk.Frame(self.win, bg="#0f141d", height=U.h(MSG_H), highlightthickness=0)
        f.pack(fill="x")
        f.pack_propagate(False)
        self.msg_frame = f
        tk.Frame(f, bg=U.ACCENT, width=4).pack(side="left", fill="y")
        self.msg = tk.Label(f, text="", bg="#0f141d", fg=U.FG,
                            font=(U.FAMILY, U.pt(12)), anchor="w", justify="left")
        self.msg.pack(side="left", fill="both", expand=True, padx=14)
        U.wrap_to_width(self.msg)
        self.mega = MegaToggle(f, before=self.msg, make=U.ghost_button)   # 시즌 3, 고를 때만 보인다

    def _commands(self):
        self.cmd = tk.Frame(self.win, bg=U.BG)
        self.cmd.pack(fill="both", expand=True, padx=12, pady=(8, 10))
        right = tk.Frame(self.cmd, bg=U.BG, width=U.h(200))
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)
        self.left = tk.Frame(self.cmd, bg=U.BG)
        self.left.pack(side="left", fill="both", expand=True)
        self.timer = tk.Label(right, text="", bg=U.BG, fg=U.ACCENT,
                              font=(U.FAMILY_BLACK, U.pt(16)), anchor="w")
        self.timer.pack(fill="x")
        self.turn_lbl = tk.Label(right, text="", bg=U.BG, fg=U.FG_FAINT,
                                 font=U.FONT_XS, anchor="w")
        self.turn_lbl.pack(fill="x")
        # (단추와 여백은 조금씩 줄여 뒀다 - 명령 칸을 낮추고도 아래의 기술 설명이 안 눌리게. CMD_H 의 설명)
        # 창을 줄였으면 단추 둘을 옆으로 나란히 놓는다 - 아래의 기술 설명이 잘리지 않게 (Z.button_box)
        box, kw_a, kw_b, same = Z.button_box(self.zoom, right)
        self.switch_btn = U.ghost_button(box, "포켓몬 교체", self.open_switch, height=same or 36)
        self.switch_btn.pack(**(kw_a or {"fill": "x", "pady": (6, 0)}))
        self.forfeit_btn = U.PushButton(box, "기권", self.forfeit, fill=U.DANGER_BG,
                                        fg=U.DANGER, shadow="#1a1013", hover="#3a2028",
                                        height=same or 32, border=U.DANGER_LINE, font=U.FONT_S)
        self.forfeit_btn.pack(**(kw_b or {"fill": "x", "pady": (6, 0)}))
        self.hint = tk.Label(right, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS,
                             anchor="nw", justify="left")
        self.hint.pack(fill="both", expand=True, pady=(Z.px(8) if same else 8, 0))
        U.wrap_to_width(self.hint)

    # ---------------- 그림 ----------------
    def set_mon(self, who, mon):
        self.zoom_use()
        self.shown[who] = dict(mon) if mon else None
        self._paint_box(who)
        self._stop_anim(who)
        try:
            self.cv.itemconfigure(self.sprite[who], image="")
        except tk.TclError:
            return
        if not mon or mon.get("fainted"):
            return
        num, shiny = mon.get("num"), T.skin(mon)       # 이로치가 고른 색까지
        size = U.h(MON_H[who])

        def work():
            path = sprite_cache.ensure(self.app.api, num, shiny)
            if not path:
                return None
            return sprites.load_animation(path, size, 0.2, 4.0,
                                          max_size=(U.h(MON_W[who]), size))

        def done(anim, err):
            if not self.alive or err or anim is None:
                return
            cur = self.shown.get(who) or {}
            if cur.get("num") != num:
                return
            frames = anim.frames[sprites.LEFT if who == "me" else sprites.RIGHT]
            photos = [ImageTk.PhotoImage(sprites.to_rgba(f, anim.key)) for f in frames]
            self.anims[who] = (photos, list(anim.durations) or [100])
            self._tick(who, 0)
        run_async(self.root, work, done)

    def _stop_anim(self, who):
        j = self.anim_jobs.get(who)
        if j:
            try:
                self.root.after_cancel(j)
            except Exception:                               # noqa: BLE001
                pass
        self.anim_jobs[who] = None
        self.anims[who] = None

    def _tick(self, who, i):
        a = self.anims.get(who)
        if not self.alive or not a:
            return
        photos, durs = a
        i %= len(photos)
        try:
            self.cv.itemconfigure(self.sprite[who], image=photos[i])
        except tk.TclError:
            return
        d = durs[i % len(durs)] if durs else 100
        self.anim_jobs[who] = self.root.after(
            max(40, int(d or 100)), lambda: self._tick(who, i + 1))

    def _paint_box(self, who, hp=None):
        it = self.box[who]
        mon = self.shown.get(who)
        side = (self.view.get(who) or {})
        cv = self.cv
        tag = "나" if who == "me" else (side.get("name") or "상대")
        if who == "foe" and side.get("chosen"):
            tag += "  ·  고름"
        elif who == "foe" and side.get("needSwitch"):
            tag += "  ·  고르는 중"
        cv.itemconfigure(it["who"], text=tag)
        if not mon:
            for k in ("name", "lv", "status"):
                cv.itemconfigure(it[k], text="")
            return
        gender = {"M": " ♂", "F": " ♀"}.get(mon.get("gender"), "")
        cv.itemconfigure(it["name"], text=(mon.get("name") or "") + gender)
        cv.itemconfigure(it["lv"], text="Lv.%d" % (mon.get("level") or 0))
        bits = []
        if mon.get("statusKr"):
            bits.append(mon["statusKr"])
        kr = {"atk": "공", "def": "방", "spa": "특공", "spd": "특방",
              "spe": "스피드", "acc": "명중", "eva": "회피"}
        for k, v in (mon.get("stages") or {}).items():
            bits.append("%s%+d" % (kr.get(k, k), v))
        cv.itemconfigure(it["status"], text="  ".join(bits))
        self._bar(who, mon.get("hp") if hp is None else hp, mon.get("maxhp") or 1)

    def _bar(self, who, hp, maxhp):
        it = self.box[who]
        x0, y0, bw, bh = it["bar_geom"]
        frac = max(0.0, min(1.0, float(hp) / float(maxhp or 1)))
        self.cv.coords(it["bar"], x0, y0, x0 + max(0, int(bw * frac)), y0 + bh)
        self.cv.itemconfigure(it["bar"], fill=hp_color(frac))
        if who == "me":
            self.cv.itemconfigure(it["hp"], text="%d / %d" % (max(0, int(hp)), maxhp))

    def _animate_bar(self, who, to_hp, done=None):
        mon = self.shown.get(who)
        if not mon:
            return done and done()
        start = mon.get("hp", 0)
        steps = 10

        def step(k):
            if not self.alive:
                return
            v = start + (to_hp - start) * k / float(steps)
            self._paint_box(who, int(round(v)))
            if k < steps:
                self.later(28, lambda: step(k + 1))
            else:
                mon["hp"] = to_hp
                if done:
                    done()
        step(1)

    def _balls(self):
        for who in ("me", "foe"):
            team = (self.view.get(who) or {}).get("team") or []
            for i, item in enumerate(self.box[who]["balls"]):
                if i >= len(team):
                    ph = self.photos["ball_none"]
                elif team[i].get("fainted"):
                    ph = self.photos["ball_out"]
                else:
                    ph = self.photos["ball"]
                self.cv.itemconfigure(item, image=ph)

    # ---------------- 연출 ----------------
    def _center(self, who):
        bb = self.cv.bbox(self.sprite[who])
        if bb:
            return ((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)
        x, y = self.foe_pos if who == "foe" else self.me_pos
        return (x, y - U.h(MON_H[who]) / 2.0)

    def lunge(self, who, done):
        self._lunge(who)
        self.later(190, done)

    def _lunge(self, who):
        item = self.sprite[who]
        d = U.h(18) if who == "me" else -U.h(18)
        seq = [d / 3.0] * 3 + [-d / 3.0] * 3

        def step(i):
            if not self.alive or i >= len(seq):
                return
            try:
                self.cv.move(item, seq[i], -seq[i] * 0.4 if who == "me" else seq[i] * 0.4)
            except tk.TclError:
                return
            self.later(26, lambda: step(i + 1))
        step(0)

    def _shake(self, who, n=6):
        item = self.sprite[who]
        offs = [6, -6, 5, -5, 3, -3, 0][:n] + [0]

        def step(i, prev=0):
            if not self.alive or i >= len(offs):
                return
            try:
                self.cv.move(item, offs[i] - prev, 0)
            except tk.TclError:
                return
            self.later(35, lambda: step(i + 1, offs[i]))
        step(0)

    def _faint(self, who):
        item = self.sprite[who]

        def step(i):
            if not self.alive:
                return
            if i >= 8:
                self._stop_anim(who)
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

    def _mega(self, ev):
        """메가진화 - 빛에 싸였다가 도트와 이름이 메가 폼으로 바뀐다. 체력은 그대로다.

        연출이 끝나면 스스로 다음 사건으로 넘긴다 (_apply 는 None 을 돌려준다).
        """
        who = ev.get("who")
        mon = self.shown.get(who) if who in ("me", "foe") else None
        self.say(ev.get("text"))
        if mon is None:
            return self.later(STEP_MS, self._next)
        mon = dict(mon)
        mon["num"] = ev.get("num") or mon.get("num")
        mon["name"] = ev.get("newName") or ev.get("to") or mon.get("name")
        mon["mega"] = True
        # 특성도 메가 폼의 것으로 바뀐다 (1.9.0). 안 고치면 칸에 옛 특성이 남는다.
        if ev.get("abilityKr"):
            mon["abilityKr"] = ev["abilityKr"]
        ui_mega.warm(self, mon["num"], T.skin(mon))

        def swap():
            self.set_mon(who, mon)
            self._banner(who, "메가진화!")
        ui_mega.play_in(self, self._center(who), swap, size=Z.px(MON_H[who]) * 0.55)

    def _banner(self, who, text):
        s = U.h
        cv = self.cv
        y = s(118) if who == "foe" else int(self.sh * 0.52)
        x = s(24) if who == "foe" else self.sw - s(340)
        r = cv.create_rectangle(x, y, x + s(310), y + s(30), fill="#2a1f08",
                                outline="#ffc043", width=2)
        t = cv.create_text(x + s(14), y + s(15), anchor="w", text=text,
                           fill="#ffe6b8", font=(U.FAMILY, U.pt(10), "bold"))
        self.banner += [r, t]

        def gone():
            for it in (r, t):
                try:
                    cv.delete(it)
                except tk.TclError:
                    pass
        self.later(1400, gone)

    def _play_fx(self, ev, who, other):
        if self.fx is not None:
            self.fx.stop()
        state = {"done": False}

        def done():
            if state["done"] or not self.alive:
                return
            state["done"] = True
            self.fx = None
            self.later(90, self._next)

        self._fx_done = done                  # (창 크기를 바꾸면 이 연출을 끝내고 다음으로 넘긴다)
        try:
            k = FX_SCALE * Z.K
            (sx, sy), (tx, ty) = self._center(who), self._center(other)
            self.fx = FX.Effect(_FxStage(self, k), self._find_move(ev),
                                (sx / k, sy / k), (tx / k, ty / k), done, who=who)
            self.effects = [e for e in self.effects if not e.dead] + [self.fx]
            self.later(2600, done)
            self.fx.play()
        except Exception:                                   # noqa: BLE001
            done()
        return None

    def _find_move(self, ev):
        if self._moves_by_name is None:
            moves = getattr(getattr(self.app, "dex", None), "moves", None) or {}
            self._moves_by_name = {m.get("kr"): m for m in moves.values() if m.get("kr")}
        return self._moves_by_name.get(ev.get("move")) or {
            "type": ev.get("moveType") or "NORMAL",
            "cat": ev.get("cat") or "physical", "flags": []}

    # ---------------- 재생 ----------------
    def play(self, events, data):
        self.busy = True
        self.hide_commands()
        self.queue = list(events)
        self._pending = data
        self._next()

    def _next(self):
        if not self.alive:
            return
        self.zoom_use()
        if not self.queue:
            return self._finish_play()
        ev = self.queue.pop(0)
        wait = self._apply(ev)
        if wait is not None:
            self.later(wait, self._next)

    def _apply(self, ev):
        t = ev.get("t")
        who = ev.get("who")
        text = ev.get("text")
        if t == "intro":
            self.say(text)
            return STEP_MS + 200
        if t == "switch":
            self.set_mon(who, ev.get("mon"))
            self.say(text)
            return STEP_MS
        if t == "recall":
            self._stop_anim(who)
            try:
                self.cv.itemconfigure(self.sprite[who], image="")
            except tk.TclError:
                pass
            self.say(text)
            return 420
        if t == "mega":
            self._mega(ev)
            return None
        if t == "move":
            self.say(text)
            other = "foe" if who == "me" else "me"
            if who in ("me", "foe") and self.shown.get(who) and self.shown.get(other):
                return self._play_fx(ev, who, other)
            return STEP_MS
        if t == "hit":
            target = ev.get("target")
            if target in ("me", "foe") and self.shown.get(target):
                self._shake(target)
                self._animate_bar(target, ev.get("hp", 0))
            return 520
        if t in ("heal", "recoil", "chip"):
            if who in ("me", "foe") and self.shown.get(who) and "hp" in ev:
                self._animate_bar(who, ev["hp"])
            self.say(text)
            return STEP_MS
        if t == "ability":
            if who in ("me", "foe"):
                mon = self.shown.get(who)
                if mon is not None and ev.get("abilityKr"):
                    mon["abilityKr"] = ev["abilityKr"]
                self._banner(who, (text or "").strip("[]"))
            return 900
        if t == "ailment":
            mon = self.shown.get(who)
            if mon is not None:
                mon["status"] = ev.get("status")
                mon["statusKr"] = {"burn": "화상", "paralysis": "마비", "poison": "독",
                                   "sleep": "잠듦", "freeze": "얼음"}.get(ev.get("status"))
                self._paint_box(who)
            self.say(text)
            return STEP_MS
        if t == "cure":
            mon = self.shown.get(who)
            if mon is not None:
                mon["status"], mon["statusKr"] = None, None
                self._paint_box(who)
            self.say(text)
            return STEP_MS
        if t == "stat":
            mon = self.shown.get(who)
            if mon is not None:
                st = dict(mon.get("stages") or {})
                k = ev.get("stat")
                st[k] = max(-6, min(6, st.get(k, 0) + int(ev.get("change") or 0)))
                mon["stages"] = dict((a, b) for a, b in st.items() if b)
                self._paint_box(who)
            self.say(text)
            return STEP_MS
        if t == "faint":
            if who in ("me", "foe"):
                self._faint(who)
                mon = self.shown.get(who)
                if mon is not None:
                    mon["hp"] = 0
                    mon["fainted"] = True
                    self._bar(who, 0, mon.get("maxhp") or 1)
            self.say(text)
            return STEP_MS + 150
        if t == "over":
            self.say(text)
            return STEP_MS + 200
        if text:
            self.say(text)
            return STEP_MS
        return 60

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
            slot = side.get("slot", 0)
            mon = team[slot] if slot < len(team) else None
            cur = self.shown.get(who)
            if not cur or cur.get("num") != (mon or {}).get("num") \
                    or cur.get("fainted") != (mon or {}).get("fainted"):
                self.set_mon(who, mon)
            else:
                self.shown[who] = dict(mon)
                self._paint_box(who)
        self._balls()
        self._paint_turn()

    def _paint_turn(self):
        me = self.view.get("me") or {}
        foe = self.view.get("foe") or {}
        self.turn_lbl.configure(
            text="%d턴  ·  %s  %d : %d" % (self.view.get("turn", 0),
                                           foe.get("name") or "상대",
                                           me.get("left", 0), foe.get("left", 0)))

    def _restore(self):
        """창 크기를 바꿔 다시 지은 화면을, 들고 있던 것으로 되돌린다 (battle_zoom.Resizable)."""
        self._ball_photos()
        for who in ("me", "foe"):
            self.set_mon(who, self.shown.get(who))
        self._balls()
        self._paint_turn()
        self._paint_timer()
        switching = self._switching
        if self._result_painted:
            self._paint_result()
        elif self.busy or self._result_shown:
            self.hide_commands()             # 재생 중이거나 나가는 중이다 - 고를 것이 없다
        elif switching and self.view.get("canAct") and not self.sent:
            self.open_switch()
        else:
            self.show_commands()

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
            if not err and m and not self._stale(m):
                got = step_of(m)
                if got > self.played or (m.get("state") == "done"
                                         and not self.view.get("over")):
                    self.played = got
                    self.sent = False
                    self.play(m.get("events") or [], m)
                else:
                    self.sync(m)
                    self._refresh()
            self.later(POLL_MS, self._poll)
        run_async(self.root, lambda: self.app.api.live(), done)

    def _stale(self, m):
        """이미 본 것보다 옛 응답인가 (rev 가 더 작다).

        폴링은 따로 돌아서, 떠날 때 읽은 옛 상태가 더 새 상태를 받은 **뒤에**
        도착할 수 있다. 아래 칸은 상태를 따라 다시 그리므로, 그대로 받으면
        화면이 한 번 옛날로 돌아갔다가 다음 폴링에서 돌아온다.
        """
        try:
            return (m.get("id") == self.room.get("id")
                    and int(m.get("rev") or 0) < int(self.room.get("rev") or 0))
        except (TypeError, ValueError, AttributeError):
            return False

    def _refresh(self):
        """서버 값이 바뀌었으면 아래 칸을 다시 그린다.

        예전에는 `self.sent`(내가 보냈던가) 일 때만 다시 그렸다. 그래서 **내가
        아무것도 안 보낸 채 기다리던 쪽**은, 상대가 다음 포켓몬을 내보내
        내 차례가 되어도 화면이 그대로였다 - "님이 다음 포켓몬을 고르고
        있습니다" 를 띄운 채 제한 시간을 다 기다렸다.

        그래서 보낸 적이 있는지가 아니라 **지금 무엇을 그려야 하는지**로 본다.
        """
        for who in ("me", "foe"):
            self._paint_box(who)
        me = self.view.get("me") or {}
        want = self._panel_key(me)
        if want != self._panel:
            if self.view.get("canAct") and not me.get("chosen"):
                self.sent = False
            self.show_commands()

    def _panel_key(self, me=None):
        """아래 칸이 무엇을 보여야 하는가. 이게 바뀌면 다시 그린다."""
        me = self.view.get("me") or {} if me is None else me
        if not self.view.get("canAct"):
            return ("wait", self.view.get("phase"))
        if self.sent or me.get("chosen"):
            return ("sent",)
        return ("act", self.view.get("phase"), me.get("slot"))

    def _paint_timer(self):
        left = max(0, int(self._deadline - time.time())) if self._deadline else 0
        try:
            if self.busy or self._result_shown:
                self.timer.configure(text="")
            else:
                self.timer.configure(text="%d초" % left,
                                     fg=U.DANGER if left <= 5 else U.ACCENT)
        except tk.TclError:
            pass

    # ---------------- 명령 ----------------
    def hide_commands(self):
        self._panel = None
        self._switching = False
        for w in self.left.winfo_children():
            w.destroy()
        for b in (self.switch_btn, self.forfeit_btn):
            b.configure(state="disabled")
        self.mega.show(False)

    def show_commands(self):
        self.zoom_use()
        self._switching = False
        self._panel = self._panel_key()
        for w in self.left.winfo_children():
            w.destroy()
        # 남은 시간은 폴링이 1.5초마다 다시 적는데, 연출이 끝난 직후에는
        # 그 사이 비어 있다. 고를 수 있게 된 순간 바로 적는다.
        self._paint_timer()
        me = self.view.get("me") or {}
        foe = self.view.get("foe") or {}
        self.forfeit_btn.configure(state="normal")
        # 폴링이 명령 칸을 다시 그려도 켜 둔 메가는 그대로다 (이미 보이면 안 건드린다)
        self.mega.show(self.view.get("canMega") and not (self.sent or me.get("chosen")))
        if not self.view.get("canAct"):
            self.switch_btn.configure(state="disabled")
            why = ("%s 님이 다음 포켓몬을 고르고 있습니다."
                   % (foe.get("name") or "상대")) if self.view.get("phase") == "switch" \
                else "상대를 기다리는 중입니다."
            tk.Label(self.left, text=why, bg=U.BG, fg=U.ACCENT,
                     font=U.FONT_H).pack(anchor="w", pady=(16, 4))
            self.say(why)
            return
        if self.sent or me.get("chosen"):
            self.sent = True
            self.switch_btn.configure(state="disabled")
            box = tk.Frame(self.left, bg=U.BG)
            box.pack(fill="both", expand=True)
            tk.Label(box, text="%s 님을 기다리는 중..." % (foe.get("name") or "상대"),
                     bg=U.BG, fg=U.ACCENT, font=U.FONT_H).pack(anchor="w", pady=(16, 4))
            lab = tk.Label(box, bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                           justify="left",
                           text="둘 다 고르면 그 턴이 한꺼번에 진행됩니다. 상대가 "
                                "시간을 넘기면 서버가 대신 골라 줍니다.")
            lab.pack(fill="x")
            U.wrap_to_width(lab)
            self.say("고른 것을 보냈습니다.")
            return
        if self.view.get("phase") == "switch":
            return self.open_switch(forced=True)
        grid = tk.Frame(self.left, bg=U.BG)
        grid.pack(fill="both", expand=True)
        for i, m in enumerate((me.get("moves") or [])[:4]):
            self._move_cell(grid, i, m)
        for c in (0, 1):
            grid.grid_columnconfigure(c, weight=1, uniform="mv")
        for r in (0, 1):
            grid.grid_rowconfigure(r, weight=1, uniform="mvr")
        self.switch_btn.configure(
            state="normal" if me.get("switches") else "disabled")
        self.hint.configure(text="기술에 마우스를 올리면 설명이 나옵니다.")
        team = me.get("team") or []
        mon = team[me.get("slot", 0)] if team else {}
        self.say("%s 은(는) 무엇을 할까?" % (mon.get("name") or ""))

    def _move_cell(self, grid, i, m):
        col = U.TYPE_COLOR.get(m.get("type"), U.BG3)
        usable = (m.get("pp") or 0) > 0 and not m.get("blocked")
        bg = shade(col, 0.42) if usable else "#23283a"
        cell = tk.Frame(grid, bg=bg, highlightthickness=2,
                        highlightbackground=col if usable else U.LINE,
                        cursor="hand2" if usable else "")
        cell.grid(row=i // 2, column=i % 2, sticky="nsew", padx=3, pady=3)
        body = tk.Frame(cell, bg=bg)
        body.pack(fill="x", expand=True)
        top = tk.Frame(body, bg=bg)
        top.pack(fill="x", padx=12, pady=(6, 0))
        name = tk.Label(top, text=m.get("kr") or m.get("key"), bg=bg,
                        fg="#ffffff" if usable else U.FG_FAINT,
                        font=(U.FAMILY, U.pt(13), "bold"), anchor="w")
        name.pack(side="left")
        tchip = tk.Label(top, text=m.get("typeKr") or "", bg=col, fg="#10131b",
                         font=U.FONT_XS, padx=6)
        tchip.pack(side="right")
        bottom = tk.Frame(body, bg=bg)
        bottom.pack(fill="x", padx=12, pady=(2, 6))
        cat = m.get("cat") or "status"
        cl = tk.Label(bottom, text=CAT_KR.get(cat, cat), bg=bg,
                      fg=CAT_COLOR.get(cat, U.FG_DIM), font=(U.FAMILY, U.pt(9), "bold"))
        cl.pack(side="left")
        extra = []
        if m.get("power"):
            extra.append("위력 %d" % m["power"])
        extra.append(("명중 %d" % m["acc"]) if m.get("acc") else "명중 —")
        el = tk.Label(bottom, text="  ·  ".join(extra), bg=bg,
                      fg="#d7dcea" if usable else U.FG_FAINT, font=U.FONT_XS)
        el.pack(side="left", padx=(8, 0))
        pp = tk.Label(bottom, text="PP %d/%d" % (m.get("pp") or 0, m.get("maxpp") or 0),
                      bg=bg, fg="#ffffff" if usable else U.DANGER,
                      font=(U.FAMILY, U.pt(9), "bold"))
        pp.pack(side="right")
        for w in (cell, body, top, name, tchip, bottom, cl, el, pp):
            w.bind("<Enter>", lambda _e, mm=m: self.hint.configure(
                text=mm.get("blocked") or mm.get("desc") or ""))
            if usable:
                w.bind("<Button-1>", lambda _e, k=m.get("key"): self.use_move(k))

    def open_switch(self, forced=False):
        forced = forced or self.view.get("phase") == "switch"
        self.zoom_use()
        self._switching = not forced         # (스스로 연 교체 칸은 창 크기를 바꿔도 그대로 둔다)
        me = self.view.get("me") or {}
        for w in self.left.winfo_children():
            w.destroy()
        head = tk.Frame(self.left, bg=U.BG)
        head.pack(fill="x")
        tk.Label(head, text="다음 포켓몬을 고르세요" if forced else "누구로 바꿀까?",
                 bg=U.BG, fg=U.FG, font=U.FONT_B).pack(side="left")
        if not forced:
            U.ghost_button(head, "돌아가기", self.show_commands, height=28).pack(side="right")
        grid = tk.Frame(self.left, bg=U.BG)
        grid.pack(fill="both", expand=True, pady=(4, 0))
        for i, m in enumerate(me.get("team") or []):
            self._party_cell(grid, i, m, i == me.get("slot"),
                             i in (me.get("switches") or []))
        for c in (0, 1, 2):
            grid.grid_columnconfigure(c, weight=1, uniform="pt")
        self.switch_btn.configure(state="disabled")
        self.mega.show(False)
        self.hint.configure(text="쓰러진 포켓몬과 지금 나와 있는 포켓몬은 고를 수 없습니다.")

    def _party_cell(self, grid, i, m, active, ok):
        bg = U.BG2 if ok else "#171b27"
        cell = tk.Frame(grid, bg=bg, highlightthickness=2,
                        highlightbackground=U.ACCENT if active else U.LINE,
                        cursor="hand2" if ok else "")
        cell.grid(row=i // 3, column=i % 3, sticky="nsew", padx=3, pady=3)
        tk.Label(cell, text=m.get("name") or "", bg=bg,
                 fg=U.FG if ok else U.FG_FAINT, font=U.FONT_B,
                 anchor="w").pack(anchor="w", padx=8, pady=(5, 0))
        sub = "Lv.%d" % (m.get("level") or 0)
        if m.get("fainted"):
            sub += "  · 쓰러짐"
        elif active:
            sub += "  · 싸우는 중"
        elif m.get("statusKr"):
            sub += "  · %s" % m["statusKr"]
        tk.Label(cell, text=sub, bg=bg, fg=U.FG_DIM, font=U.FONT_XS,
                 anchor="w").pack(anchor="w", padx=8, pady=(0, 6))
        if ok:
            for w in (cell,) + tuple(cell.winfo_children()):
                w.bind("<Button-1>", lambda _e, s=i: self.do_switch(s))

    # ---------------- 보내기 ----------------
    def _send(self, kind, move="", slot=-1):
        if self.busy or self.sent:
            return
        mega = self.mega.take() if kind == "move" else False
        self.sent = True
        self.hide_commands()
        self.say("...")

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.sent = False
                self.say(getattr(err, "message", str(err)))
                return self.show_commands()
            got = step_of(r)
            if kind == "forfeit" and r.get("state") == "done":
                return self._leave_after_forfeit(r)
            if got > self.played or (r.get("state") == "done"):
                self.played = got
                self.sent = False
                return self.play(r.get("events") or [], r)
            self.sync(r)
            self.show_commands()
        run_async(self.root, lambda: self.app.api.live_act(kind, move, slot, mega=mega), done)

    def _leave_after_forfeit(self, room):
        """내가 기권했다 - 결과 창을 따로 띄우지 않고 닫는다 (제보, 1.9.2).

        그만두겠다고 한 사람에게 '패배... [닫기]' 를 한 번 더 누르게 할 까닭이
        없다. **결과를 봤다고 서버에 먼저 알리고** 닫는다 - 순서가 바뀌면 그
        사이에 도는 확인(app.check_live)이 '안 본 결과가 있다' 며 창을 다시 연다.
        """
        self.played = max(self.played, step_of(room))
        self.sync(room)
        self._result_shown = True
        self.hide_commands()
        self.say("승부를 포기했습니다.")
        self._seen_sent = True

        def bye(_r, _e):
            self.close()
        run_async(self.root, lambda: self.app.api.live_seen(), bye)

    def use_move(self, key):
        self._send("move", move=key)

    def do_switch(self, slot):
        self._send("switch", slot=slot)

    def forfeit(self):
        from .ui_box import confirm
        if not confirm(self.win, "기권",
                       "이 승부를 포기할까요? 상대의 승리로 기록됩니다.",
                       danger=True, ok_text="기권"):
            return
        self.sent = False
        self._send("forfeit")

    # ---------------- 끝 ----------------
    def show_result(self):
        if self._result_shown:
            return
        self._result_shown = True
        self._paint_result()
        self._mark_seen()

    def _paint_result(self):
        """결과 칸을 그린다 (창 크기를 바꿔 다시 지을 때도 부른다 - 한 번만 할 일은 show_result 에)."""
        self.zoom_use()
        self._result_painted = True
        self.hide_commands()
        out = self.room.get("outcome") or self.view.get("result")
        title = {"win": "승리!", "lose": "패배...", "draw": "무승부"}.get(out, "끝")
        color = {"win": U.ACCENT, "lose": U.DANGER}.get(out, U.FG)
        panel = tk.Frame(self.left, bg=U.BG2, highlightthickness=2,
                         highlightbackground=color)
        panel.pack(fill="both", expand=True)
        inner = tk.Frame(panel, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16, pady=10)
        side = tk.Frame(inner, bg=U.BG2)
        side.pack(side="right", fill="y", padx=(12, 0))
        U.PushButton(side, "닫기", self.close, height=Z.base_h(38)).pack(side="bottom")
        body = tk.Frame(inner, bg=U.BG2)
        body.pack(side="left", fill="both", expand=True)
        tk.Label(body, text=title, bg=U.BG2, fg=color,
                 font=(U.FAMILY_BLACK, U.pt(20))).pack(anchor="w")
        foe = (self.view.get("foe") or {}).get("name") or "상대"
        reason = self.room.get("reason") or self.view.get("reason")
        lines = []
        if reason == "forfeit":
            lines.append("기권으로 끝났습니다.")
        elif reason == "turns":
            lines.append("%d턴을 넘겨 남은 포켓몬 수로 정했습니다."
                         % (self.view.get("maxTurns") or 0))
        lines.append("%s 님과의 실시간 배틀 · %d턴" % (foe, self.view.get("turn", 0)))
        me = self.view.get("me") or {}
        fo = self.view.get("foe") or {}
        lines.append("남은 포켓몬 %d : %d" % (me.get("left", 0), fo.get("left", 0)))
        lines.append("전적에 남습니다. 상금과 랭크 점수는 움직이지 않습니다.")
        for ln in lines:
            lab = tk.Label(body, text=natural(ln), bg=U.BG2, fg=U.FG, font=U.FONT_S,
                           anchor="w", justify="left")
            lab.pack(fill="x", pady=(2, 0))
            U.wrap_to_width(lab)
        self.say(title)

    def _mark_seen(self):
        if self._seen_sent:
            return
        self._seen_sent = True
        run_async(self.root, lambda: self.app.api.live_seen(), lambda _r, _e: None)

    def request_close(self):
        if self.alive and not (self.view.get("over") or self._result_shown):
            from .ui_box import confirm
            if not confirm(self.win, "창 닫기",
                           "판은 그대로 이어집니다. 시간이 지나면 서버가 대신 골라 주고, "
                           "판이 살아 있으면 창이 저절로 다시 열려요.",
                           danger=False, ok_text="닫기"):
                return
        self.close()

    def close(self):
        if not self.alive:
            return
        self.alive = False
        self.zoom_close()
        for e in self.effects + ([self.fx] if self.fx is not None else []):
            try:
                e.stop()
            except Exception:                               # noqa: BLE001
                pass
        self.effects = []
        self.fx = None
        for who in ("me", "foe"):
            self._stop_anim(who)
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
