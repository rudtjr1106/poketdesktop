# -*- coding: utf-8 -*-
"""레이드 — 배틀 창. 여럿이 보스 하나를 상대한다.

## 보여 주기만 한다

관장 배틀과 같다. 데미지·AI·보상은 전부 서버가 정하고(server/app/raid.py),
이 창은 서버가 보낸 일(events)을 순서대로 재생한 뒤 서버가 보낸 판 상태로
화면을 맞춘다.

## 관장 배틀과 다른 점

  · 상대가 **하나**, 우리가 **여럿**이다. 위에 공용 체력바 하나, 아래에
    참가자 칸이 최대 여섯.
  · 한 사람씩 번갈아 두는 것이 아니라 **모두가 동시에 고른다.** 다 고르면
    서버가 그 라운드를 돌리고, 제한 시간을 넘긴 사람은 서버가 대신 고른다.
  · 그래서 **창이 열려 있는 동안 방을 자주 물어본다** (POLL_MS). 서버에
    따로 도는 시계가 없어서, 마감이 지났는지는 요청이 올 때 본다.

## 이벤트에 붙는 p

서버가 보내는 일에는 누구의 것인지(p = 참가자 자리)가 붙어 있다.
who 가 "me" 면 그 사람의 포켓몬, "foe" 면 보스다.
"""
import time
import tkinter as tk

from PIL import ImageTk

from common.korean import natural

from . import battle_fx as FX
from . import sprite_cache, sprites
from . import platform_os as PLAT
from . import ui_common as U
from .ui_common import run_async
from .ui_gym import shade
from .ui_gym_battle import CAT_COLOR, CAT_KR, FX_SCALE, _FxStage, hp_color

W = 960
SCENE_H = 330
MSG_H = 48
CMD_H = 200
MIN_SCENE_H = 250
STEP_MS = 560
POLL_MS = 1500              # 방을 물어보는 주기
BOSS_H = 130                # 보스 도트 높이(px)
BOSS_W = 300
MON_H = 66                  # 참가자 도트 높이
MON_W = 120

BOSS = "boss"


def _key(ev):
    """이 일이 누구 것인가. 보스면 BOSS, 사람이면 자리 번호."""
    if ev.get("who") == "foe":
        return BOSS
    p = ev.get("p")
    return p if isinstance(p, int) else None


class RaidBattleWindow(object):

    def __init__(self, app, data, on_close=None):
        self.app = app
        self.root = app.root
        self.on_close = on_close
        self.alive = True
        self.room = data
        self.view = data.get("battle") or {}
        self.me = data.get("me")
        self.played = int(data.get("round") or 0)
        self.queue = []
        self.busy = False
        self.sent = False           # 이번 라운드에 이미 보냈나
        self.photos = {}
        self.anims = {}
        self.anim_jobs = {}
        self.jobs = []
        self.shown = {}             # 지금 그려 둔 것 (연출용)
        self.effects = []
        self.fx = None
        self._fx_actor = None
        self._moves_by_name = None
        self._poll_job = None
        self._deadline = 0.0
        self._seen_sent = False
        self._result_shown = False

        self.win = tk.Toplevel(self.root)
        ww = U.h(W)
        self.scene_h = U.h(SCENE_H)
        wh = self.scene_h + U.h(MSG_H) + U.h(CMD_H) + 4
        sw_, sh_ = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        try:
            x1, y1, x2, y2 = PLAT.work_area(sw_, sh_)
        except Exception:                                   # noqa: BLE001
            x1, y1, x2, y2 = 0, 0, sw_, sh_
        room = (y2 - y1) - 44
        if wh > room:
            cut = min(wh - room, self.scene_h - U.h(MIN_SCENE_H))
            self.scene_h -= max(0, cut)
            wh -= max(0, cut)
        # **가로도 화면 안에 넣는다.** 글꼴이 큰 화면에서는 U.h(960) 이
        # 1152 까지 커지는데, 노트북 화면이 1024 면 오른쪽이 통째로 밖으로
        # 나간다(참가자 여섯째 칸과 물러나기 단추가 안 보인다).
        ww = min(ww, (x2 - x1) - U.h(16))
        self.ww = ww
        boss = (self.view.get("boss") or {}).get("name") or "레이드"
        U.style_window(self.win, "레이드 — %s" % boss, ww, wh)
        gx = x1 + max(0, ((x2 - x1) - ww) // 2)
        gy = y1 + max(0, ((y2 - y1) - wh - 30) // 3)
        self.win.geometry("%dx%d+%d+%d" % (ww, wh, gx, gy))
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.request_close)
        app.raid_battle = self

        self._scene()
        self._message()
        self._commands()

        events = data.get("events") or []
        if self.played == 0 and events:
            self.play(events, data)         # 시작 연출
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
        return j

    def say(self, text):
        try:
            self.msg.configure(text=natural(text or ""))
        except tk.TclError:
            pass

    def _n(self):
        return len(self.view.get("players") or [])

    # ---------------- 장면 ----------------
    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg="#171326",
                       highlightthickness=0)
        cv.pack(fill="x")
        self.cv = cv
        sw, sh = self.sw, self.sh
        cv.create_rectangle(0, int(sh * 0.62), sw, sh, fill="#1e1a33", outline="")
        cv.create_line(0, int(sh * 0.62), sw, int(sh * 0.62), fill="#2d2749")

        # 공용 체력바 (맨 위, 창 너비만큼)
        bx0, by0 = s(18), s(14)
        bw, bh = sw - s(36), s(18)
        self.hp_geom = (bx0, by0, bw, bh)
        cv.create_rectangle(bx0, by0, bx0 + bw, by0 + bh, fill="#2a2147", outline="")
        self.hp_bar = cv.create_rectangle(bx0, by0, bx0 + bw, by0 + bh,
                                          fill="#5fd97a", outline="")
        self.hp_text = cv.create_text(sw // 2, by0 + bh // 2, fill="#0d1017",
                                      font=(U.FAMILY, U.pt(9), "bold"), text="")
        self.boss_name = cv.create_text(bx0, by0 - s(2), anchor="sw", fill="#f2f4fb",
                                        font=(U.FAMILY, U.pt(11), "bold"), text="")
        self.round_text = cv.create_text(bx0 + bw, by0 - s(2), anchor="se",
                                         fill="#c9cfdf", font=(U.FAMILY, U.pt(9)),
                                         text="")
        # 보호막 바 (체력바 바로 아래, 있을 때만 보인다)
        sy = by0 + bh + s(3)
        self.shield_geom = (bx0, sy, bw, s(7))
        self.shield_bg = cv.create_rectangle(bx0, sy, bx0 + bw, sy + s(7),
                                             fill="#1d2740", outline="", state="hidden")
        self.shield_bar = cv.create_rectangle(bx0, sy, bx0 + bw, sy + s(7),
                                              fill="#6fb3ff", outline="", state="hidden")
        self.shield_text = cv.create_text(bx0 + bw, sy + s(14), anchor="ne",
                                          fill="#6fb3ff", font=U.FONT_XS, text="")

        # 보스
        self.boss_pos = (sw // 2, int(sh * 0.56))
        bxp, byp = self.boss_pos
        cv.create_oval(bxp - s(140), byp - s(20), bxp + s(140), byp + s(20),
                       fill="#2a2449", outline="#3a3160")
        self.sprite = {BOSS: cv.create_image(bxp, byp + s(6), anchor="s")}
        self.status_text = cv.create_text(bxp, byp + s(30), fill="#ffc043",
                                          font=(U.FAMILY, U.pt(9), "bold"), text="")
        # 참가자 칸
        self.slots = {}
        self._seats()
        self.banner = []

    def _seats(self):
        """아래쪽 참가자 칸. 인원수에 맞춰 나눈다."""
        s = U.h
        cv = self.cv
        n = max(1, self._n())
        cell = self.sw / float(n)
        for i in range(n):
            cx = int(cell * (i + 0.5))
            base = int(self.sh * 0.965)
            cv.create_oval(cx - s(42), base - s(9), cx + s(42), base + s(9),
                           fill="#241f3d", outline="#332c55")
            self.sprite[i] = cv.create_image(cx, base + s(4), anchor="s")
            name = cv.create_text(cx, int(self.sh * 0.68), fill="#f2f4fb",
                                  font=(U.FAMILY, U.pt(9), "bold"), text="")
            hp_y = int(self.sh * 0.705)
            w = int(cell * 0.66)
            bg = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7),
                                     fill="#2a3147", outline="")
            bar = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7),
                                      fill="#5fd97a", outline="")
            mark = cv.create_text(cx, hp_y + s(19), fill="#8e97b3", font=U.FONT_XS,
                                  text="")
            self.slots[i] = {"cx": cx, "name": name, "bar": bar, "bg": bg,
                             "mark": mark, "geom": (cx - w // 2, hp_y, w, s(7))}

    def _message(self):
        f = tk.Frame(self.win, bg="#0f141d", height=U.h(MSG_H), highlightthickness=0)
        f.pack(fill="x")
        f.pack_propagate(False)
        tk.Frame(f, bg=U.ACCENT, width=4).pack(side="left", fill="y")
        self.msg = tk.Label(f, text="", bg="#0f141d", fg=U.FG,
                            font=(U.FAMILY, U.pt(12)), anchor="w", justify="left")
        self.msg.pack(side="left", fill="both", expand=True, padx=14)
        U.wrap_to_width(self.msg)

    def _commands(self):
        self.cmd = tk.Frame(self.win, bg=U.BG)
        self.cmd.pack(fill="both", expand=True, padx=12, pady=(8, 10))
        right = tk.Frame(self.cmd, bg=U.BG, width=U.h(210))
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
        self.switch_btn = U.ghost_button(right, "포켓몬 교체", self.open_switch, height=38)
        self.switch_btn.pack(fill="x", pady=(8, 0))
        self.leave_btn = U.PushButton(right, "물러나기", self.leave, fill=U.DANGER_BG,
                                      fg=U.DANGER, shadow="#1a1013", hover="#3a2028",
                                      height=34, border=U.DANGER_LINE, font=U.FONT_S)
        self.leave_btn.pack(fill="x", pady=(8, 0))
        self.hint = tk.Label(right, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS,
                             anchor="nw", justify="left")
        self.hint.pack(fill="both", expand=True, pady=(10, 0))
        U.wrap_to_width(self.hint)

    # ---------------- 그림 ----------------
    def set_mon(self, key, mon, boss=False):
        self.shown[key] = dict(mon) if mon else None
        self._stop_anim(key)
        try:
            self.cv.itemconfigure(self.sprite[key], image="")
        except (KeyError, tk.TclError):
            return
        if not mon or mon.get("fainted"):
            return self._paint(key)
        num, shiny = mon.get("num"), mon.get("shiny")
        size = U.h(BOSS_H if boss else MON_H)
        cap = U.h(BOSS_W if boss else MON_W)

        def work():
            path = sprite_cache.ensure(self.app.api, num, shiny)
            if not path:
                return None
            return sprites.load_animation(path, size, 0.2, 4.0, max_size=(cap, size))

        def done(anim, err):
            if not self.alive or err or anim is None:
                return
            cur = self.shown.get(key) or {}
            if cur.get("num") != num:
                return
            # 쇼다운 도트는 왼쪽을 본다. 우리 쪽은 뒤집어 보스를 보게 한다.
            frames = anim.frames[sprites.RIGHT if boss else sprites.LEFT]
            photos = [ImageTk.PhotoImage(sprites.to_rgba(f, anim.key)) for f in frames]
            self.anims[key] = (photos, list(anim.durations) or [100])
            self._tick(key, 0)
        run_async(self.root, work, done)
        self._paint(key)

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
        except (KeyError, tk.TclError):
            return
        d = durs[i % len(durs)] if durs else 100
        self.anim_jobs[key] = self.root.after(
            max(40, int(d or 100)), lambda: self._tick(key, i + 1))

    def _paint(self, key, hp=None):
        mon = self.shown.get(key)
        cv = self.cv
        if key == BOSS:
            b = self.view.get("boss") or {}
            cv.itemconfigure(self.boss_name,
                             text="%s  Lv.%d" % (b.get("name") or "", b.get("level") or 0))
            bits = []
            if (mon or b).get("statusKr"):
                bits.append((mon or b)["statusKr"])
            for k, v in ((mon or b).get("stages") or {}).items():
                bits.append("%s%+d" % ({"atk": "공", "def": "방", "spa": "특공",
                                        "spd": "특방", "spe": "스피드"}.get(k, k), v))
            if (mon or b).get("raged"):
                bits.append("분노")
            cv.itemconfigure(self.status_text, text="  ".join(bits))
            cur = (mon or b).get("hp") if hp is None else hp
            self._boss_bar(cur, (mon or b).get("maxhp") or 1)
            return
        it = self.slots.get(key)
        if not it:
            return
        p = (self.view.get("players") or [None] * (key + 1))[key] or {}
        who = p.get("name") or ""
        if key == self.me:
            who += " (나)"
        cv.itemconfigure(it["name"], text=who)
        m = mon or p.get("mon") or {}
        self._mon_bar(key, m.get("hp") if hp is None else hp, m.get("maxhp") or 1)
        mark = ""
        color = U.FG_FAINT
        if p.get("left"):
            mark, color = "물러남", U.FG_FAINT
        elif p.get("out"):
            mark, color = "전멸", U.DANGER
        elif p.get("chosen"):
            mark, color = "고름", U.GOOD
        else:
            mark = m.get("name") or ""
            color = U.FG_DIM
        cv.itemconfigure(it["mark"], text=mark, fill=color)

    def _boss_bar(self, hp, maxhp):
        x0, y0, bw, bh = self.hp_geom
        frac = max(0.0, min(1.0, float(hp) / float(maxhp or 1)))
        self.cv.coords(self.hp_bar, x0, y0, x0 + max(0, int(bw * frac)), y0 + bh)
        self.cv.itemconfigure(self.hp_bar, fill=hp_color(frac))
        self.cv.itemconfigure(self.hp_text,
                              text="%s / %s" % (format(max(0, int(hp)), ","),
                                                format(int(maxhp), ",")))

    def _mon_bar(self, key, hp, maxhp):
        it = self.slots.get(key)
        if not it:
            return
        x0, y0, bw, bh = it["geom"]
        frac = max(0.0, min(1.0, float(hp) / float(maxhp or 1)))
        self.cv.coords(it["bar"], x0, y0, x0 + max(0, int(bw * frac)), y0 + bh)
        self.cv.itemconfigure(it["bar"], fill=hp_color(frac))

    def _shield(self, sh):
        x0, y0, bw, bh = self.shield_geom
        if not sh:
            self.cv.itemconfigure(self.shield_bg, state="hidden")
            self.cv.itemconfigure(self.shield_bar, state="hidden")
            self.cv.itemconfigure(self.shield_text, text="")
            return
        frac = max(0.0, min(1.0, sh.get("hp", 0) / float(sh.get("max") or 1)))
        self.cv.itemconfigure(self.shield_bg, state="normal")
        self.cv.itemconfigure(self.shield_bar, state="normal")
        self.cv.coords(self.shield_bar, x0, y0, x0 + max(0, int(bw * frac)), y0 + bh)
        left = sh.get("left")
        note = "보호막 %s" % format(max(0, int(sh.get("hp", 0))), ",")
        if left:
            note += "  ·  %d라운드 안에 깨야 한다" % left
        self.cv.itemconfigure(self.shield_text, text=note)

    def _animate_bar(self, key, to_hp, done=None):
        mon = self.shown.get(key)
        if mon is None:
            return done and done()
        start = mon.get("hp", 0)
        steps = 8

        def step(k):
            if not self.alive:
                return
            v = start + (to_hp - start) * k / float(steps)
            self._paint(key, int(round(v)))
            if k < steps:
                self.later(26, lambda: step(k + 1))
            else:
                mon["hp"] = to_hp
                if done:
                    done()
        step(1)

    # ---------------- 연출 ----------------
    def _center(self, key):
        bb = self.cv.bbox(self.sprite.get(key))
        if bb:
            return ((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)
        if key == BOSS:
            x, y = self.boss_pos
            return (x, y - U.h(BOSS_H) / 2.0)
        it = self.slots.get(key) or {"cx": self.sw // 2}
        return (it["cx"], self.sh * 0.9)

    def lunge(self, who, done):
        """battle_fx 가 접촉기에서 부른다."""
        self._lunge(self._fx_actor if who != "foe" else BOSS)
        self.later(190, done)

    def _lunge(self, key):
        item = self.sprite.get(key)
        if item is None:
            return
        up = key != BOSS
        d = U.h(14) if up else -U.h(14)
        seq = [0, -d / 2.0, -d / 2.0, d / 2.0, d / 2.0]

        def step(i):
            if not self.alive or i >= len(seq):
                return
            try:
                self.cv.move(item, 0, seq[i])
            except tk.TclError:
                return
            self.later(26, lambda: step(i + 1))
        step(0)

    def _shake(self, key, n=6):
        item = self.sprite.get(key)
        if item is None:
            return
        offs = [5, -5, 4, -4, 2, -2, 0][:n] + [0]

        def step(i, prev=0):
            if not self.alive or i >= len(offs):
                return
            try:
                self.cv.move(item, offs[i] - prev, 0)
            except tk.TclError:
                return
            self.later(32, lambda: step(i + 1, offs[i]))
        step(0)

    def _faint(self, key):
        item = self.sprite.get(key)
        if item is None:
            return

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

    def _flash(self, text, color="#ffe6b8"):
        s = U.h
        cv = self.cv
        y = int(self.sh * 0.30)
        r = cv.create_rectangle(self.sw // 2 - s(200), y, self.sw // 2 + s(200),
                                y + s(34), fill="#2a1f08", outline=color, width=2)
        t = cv.create_text(self.sw // 2, y + s(17), text=text, fill=color,
                           font=(U.FAMILY, U.pt(11), "bold"))
        self.banner += [r, t]

        def gone():
            for it in (r, t):
                try:
                    cv.delete(it)
                except tk.TclError:
                    pass
        self.later(1500, gone)

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
            self.fx = FX.Effect(_FxStage(self, k), self._find_move(ev),
                                (sx / k, sy / k), (tx / k, ty / k), done,
                                who="me" if src != BOSS else "foe")
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
        if not self.queue:
            return self._finish_play()
        ev = self.queue.pop(0)
        wait = self._apply(ev)
        if wait is not None:
            self.later(wait, self._next)

    def _apply(self, ev):
        t = ev.get("t")
        key = _key(ev)
        text = ev.get("text")
        if t == "intro":
            self.say(text)
            self._flash(text or "")
            return STEP_MS + 300
        if t == "switch":
            if key is not None:
                self.set_mon(key, ev.get("mon"), boss=(key == BOSS))
            self.say(text)
            return 360
        if t == "recall":
            if key is not None:
                self._stop_anim(key)
                try:
                    self.cv.itemconfigure(self.sprite[key], image="")
                except (KeyError, tk.TclError):
                    pass
            self.say(text)
            return 340
        if t == "move":
            self.say(text)
            other = BOSS if key != BOSS else self._boss_target(ev)
            if key is not None and other is not None \
                    and self.shown.get(key) and self.shown.get(other):
                return self._play_fx(ev, key, other)
            return STEP_MS
        if t == "hit":
            tg = ev.get("target")
            tkey = BOSS if tg == "foe" else ev.get("p")
            if tkey is not None and self.shown.get(tkey) is not None:
                self._shake(tkey)
                self._animate_bar(tkey, ev.get("hp", 0))
            return 460
        if t in ("heal", "recoil", "chip"):
            if key is not None and "hp" in ev and self.shown.get(key) is not None:
                self._animate_bar(key, ev["hp"])
            self.say(text)
            return STEP_MS
        if t == "shield":
            sh = dict((self.view.get("boss") or {}).get("shield") or {})
            sh["hp"] = ev.get("hp", 0)
            sh["max"] = ev.get("maxhp", sh.get("max", 1))
            self._shield(sh)
            self._shake(BOSS, 4)
            self.say(text)
            return 320
        if t == "shieldUp":
            self._shield({"hp": ev.get("hp", 0), "max": ev.get("maxhp", 1),
                          "left": ev.get("left")})
            self._flash(text or "", "#6fb3ff")
            self.say(text)
            return STEP_MS + 250
        if t in ("shieldBreak", "shieldHeld"):
            self._shield(None)
            self._flash(text or "", "#6fb3ff")
            self.say(text)
            return STEP_MS + 250
        if t == "rage":
            self._flash(text or "", U.DANGER)
            self.say(text)
            return STEP_MS + 200
        if t == "roar":
            self._flash(text or "", U.DANGER)
            for i in range(self._n()):
                self._shake(i, 8)
            self.say(text)
            return STEP_MS + 350
        if t == "weather":
            self._flash(text or "")
            self.say(text)
            return STEP_MS
        if t == "ability":
            if key is not None:
                self._flash((text or "").strip("[]"))
            return 800
        if t in ("ailment", "cure", "stat"):
            mon = self.shown.get(key)
            if mon is not None:
                if t == "ailment":
                    mon["status"] = ev.get("status")
                    mon["statusKr"] = {"burn": "화상", "paralysis": "마비",
                                       "poison": "독", "sleep": "잠듦",
                                       "freeze": "얼음"}.get(ev.get("status"))
                elif t == "cure":
                    mon["status"], mon["statusKr"] = None, None
                else:
                    st = dict(mon.get("stages") or {})
                    k2 = ev.get("stat")
                    st[k2] = max(-6, min(6, st.get(k2, 0) + int(ev.get("change") or 0)))
                    mon["stages"] = dict((a, b) for a, b in st.items() if b)
                self._paint(key)
            self.say(text)
            return STEP_MS
        if t == "faint":
            if key is not None:
                self._faint(key)
                mon = self.shown.get(key)
                if mon is not None:
                    mon["hp"] = 0
                    mon["fainted"] = True
                    self._paint(key, 0)
            self.say(text)
            return STEP_MS + 120
        if t in ("leave", "over"):
            self.say(text)
            if t == "over":
                self._flash(text or "", U.GOOD if ev.get("result") == "won" else U.DANGER)
                return STEP_MS + 400
            return STEP_MS
        if text:
            self.say(text)
            return STEP_MS
        return 60

    def _boss_target(self, ev):
        """보스가 누구를 때렸나. 그 일에 붙은 자리를 쓴다."""
        p = ev.get("p")
        return p if isinstance(p, int) else None

    def _finish_play(self):
        data = self._pending or {}
        self._pending = None
        self.busy = False
        self.sync(data)
        if (data.get("state") or "") == "done" or (self.view.get("over")):
            return self.show_result()
        self.show_commands()

    # ---------------- 서버 값으로 맞추기 ----------------
    def sync(self, room):
        self.room = room or self.room
        self.view = self.room.get("battle") or self.view
        if self.room.get("me") is not None:
            self.me = self.room["me"]
        self.played = max(self.played, int(self.room.get("round") or 0))
        if self.room.get("deadlineIn") is not None:
            self._deadline = time.time() + int(self.room["deadlineIn"])
        boss = self.view.get("boss") or {}
        cur = self.shown.get(BOSS)
        if not cur or cur.get("num") != boss.get("num"):
            self.set_mon(BOSS, boss, boss=True)
        else:
            self.shown[BOSS] = dict(boss)
            self._paint(BOSS)
        self._shield(boss.get("shield"))
        for i, p in enumerate(self.view.get("players") or []):
            if i not in self.sprite:
                continue
            mon = p.get("mon") or {}
            cur = self.shown.get(i)
            if not cur or cur.get("num") != mon.get("num") \
                    or cur.get("fainted") != mon.get("fainted"):
                self.set_mon(i, mon)
            else:
                self.shown[i] = dict(mon)
                self._paint(i)
        self.cv.itemconfigure(
            self.round_text,
            text="%d / %d 라운드%s" % (self.view.get("round", 0),
                                      self.view.get("maxRounds", 15),
                                      "  ·  보스 2회 행동"
                                      if self.view.get("bossHits", 1) > 1 else ""))
        self.turn_lbl.configure(text="%d명 참가" % sum(
            1 for p in self.view.get("players") or []
            if not p.get("left") and not p.get("out")))

    # ---------------- 폴링 ----------------
    def _poll(self):
        if not self.alive:
            return
        self._paint_timer()
        if self.busy or self._result_shown:
            self._poll_job = self.later(POLL_MS, self._poll)
            return

        def done(r, err):
            if not self.alive:
                return
            if not err and r:
                got = int(r.get("round") or 0)
                if got > self.played:
                    self.played = got
                    self.sent = False
                    self.play(r.get("events") or [], r)
                else:
                    self.sync(r)
                    if (r.get("state") or "") == "done":
                        return self.show_result()
                    self._refresh_marks()
            self._poll_job = self.later(POLL_MS, self._poll)
        run_async(self.root, lambda: self.app.api.raid_room(), done)

    def _refresh_marks(self):
        for i in range(self._n()):
            self._paint(i)
        me = (self.view.get("me") or {})
        if me.get("choice") and not self.sent:
            self.sent = True
            self.show_commands()

    def _paint_timer(self):
        left = max(0, int(self._deadline - time.time())) if self._deadline else 0
        try:
            if self.busy:
                self.timer.configure(text="", fg=U.ACCENT)
            elif self.sent:
                self.timer.configure(text="%d초" % left, fg=U.FG_DIM)
            else:
                self.timer.configure(text="%d초" % left,
                                     fg=U.DANGER if left <= 5 else U.ACCENT)
        except tk.TclError:
            pass

    # ---------------- 명령 ----------------
    def hide_commands(self):
        for w in self.left.winfo_children():
            w.destroy()
        for b in (self.switch_btn, self.leave_btn):
            b.configure(state="disabled")

    def show_commands(self):
        for w in self.left.winfo_children():
            w.destroy()
        me = self.view.get("me") or {}
        if not me.get("canAct"):
            self.switch_btn.configure(state="disabled")
            self.leave_btn.configure(state="normal")
            mine = (self.view.get("players") or [{}])[self.me or 0]
            why = ("데리고 온 포켓몬이 모두 쓰러졌습니다."
                   if mine.get("out") else "레이드에서 물러났습니다.")
            tk.Label(self.left, text=why, bg=U.BG, fg=U.FG_DIM,
                     font=U.FONT_B).pack(anchor="w", pady=20)
            self.say(why + " 남은 사람들이 싸우고 있습니다.")
            return
        if self.sent or me.get("choice"):
            self.sent = True
            self.switch_btn.configure(state="disabled")
            self.leave_btn.configure(state="normal")
            box = tk.Frame(self.left, bg=U.BG)
            box.pack(fill="both", expand=True)
            tk.Label(box, text="다른 사람을 기다리는 중...", bg=U.BG, fg=U.ACCENT,
                     font=U.FONT_H).pack(anchor="w", pady=(16, 4))
            waiting = [p.get("name") for p in self.view.get("players") or []
                       if not p.get("chosen") and not p.get("left")
                       and not p.get("out")]
            lab = tk.Label(box, text=("아직 안 고른 사람: " + ", ".join(waiting))
                           if waiting else "곧 라운드가 진행됩니다.",
                           bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, anchor="w",
                           justify="left")
            lab.pack(fill="x")
            U.wrap_to_width(lab)
            self.say("고른 것을 보냈습니다. 모두 고르면 라운드가 진행됩니다.")
            return
        grid = tk.Frame(self.left, bg=U.BG)
        grid.pack(fill="both", expand=True)
        for i, m in enumerate((me.get("moves") or [])[:4]):
            self._move_cell(grid, i, m)
        for c in (0, 1):
            grid.grid_columnconfigure(c, weight=1, uniform="mv")
        for r in (0, 1):
            grid.grid_rowconfigure(r, weight=1, uniform="mvr")
        team = me.get("team") or []
        can_switch = any(not x.get("fainted") for i, x in enumerate(team)
                         if i != me.get("slot"))
        self.switch_btn.configure(state="normal" if can_switch else "disabled")
        self.leave_btn.configure(state="normal")
        self.hint.configure(text="모두가 고르면 그 라운드가 한꺼번에 진행됩니다. "
                                 "시간 안에 안 고르면 가장 센 기술로 대신 싸웁니다.")
        mon = (team[me.get("slot", 0)] if team else {}) or {}
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

    def open_switch(self):
        me = self.view.get("me") or {}
        for w in self.left.winfo_children():
            w.destroy()
        head = tk.Frame(self.left, bg=U.BG)
        head.pack(fill="x")
        tk.Label(head, text="누구로 바꿀까?", bg=U.BG, fg=U.FG,
                 font=U.FONT_B).pack(side="left")
        U.ghost_button(head, "돌아가기", self.show_commands, height=28).pack(side="right")
        grid = tk.Frame(self.left, bg=U.BG)
        grid.pack(fill="both", expand=True, pady=(4, 0))
        for i, m in enumerate(me.get("team") or []):
            self._party_cell(grid, i, m, i == me.get("slot"))
        for c in (0, 1, 2):
            grid.grid_columnconfigure(c, weight=1, uniform="pt")
        self.switch_btn.configure(state="disabled")
        self.hint.configure(text="교체한 라운드에는 공격하지 못합니다.")

    def _party_cell(self, grid, i, m, active):
        ok = not m.get("fainted") and not active
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
            got = int(r.get("round") or 0)
            if got > self.played:
                self.played = got
                self.sent = False
                return self.play(r.get("events") or [], r)
            self.sync(r)
            self.show_commands()
        run_async(self.root, lambda: self.app.api.raid_act(kind, move, slot), done)

    def use_move(self, key):
        self._send("move", move=key)

    def do_switch(self, slot):
        self._send("switch", slot=slot)

    def leave(self):
        from .ui_box import confirm
        if not confirm(self.win, "물러나기",
                       "레이드에서 물러날까요? 남은 사람끼리 계속 싸우고, "
                       "물러나면 알은 받을 수 없습니다.",
                       danger=True, ok_text="물러나기"):
            return

        def done(_r, err):
            if not self.alive:
                return
            if err:
                return self.say(getattr(err, "message", str(err)))
            self.close()
        run_async(self.root, lambda: self.app.api.raid_leave(), done)

    # ---------------- 끝 ----------------
    def show_result(self):
        if self._result_shown:
            return
        self._result_shown = True
        self.hide_commands()
        res = self.view.get("result") or self.room.get("result")
        title = {"won": "레이드 성공!", "lost": "전멸...",
                 "timeout": "시간 초과"}.get(res, "끝")
        color = U.ACCENT if res == "won" else U.DANGER
        panel = tk.Frame(self.left, bg=U.BG2, highlightthickness=2,
                         highlightbackground=color)
        panel.pack(fill="both", expand=True)
        inner = tk.Frame(panel, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16, pady=10)
        side = tk.Frame(inner, bg=U.BG2)
        side.pack(side="right", fill="y", padx=(12, 0))
        U.PushButton(side, "닫기", self.close, height=U.h(38)).pack(side="bottom")
        body = tk.Frame(inner, bg=U.BG2)
        body.pack(side="left", fill="both", expand=True)
        tk.Label(body, text=title, bg=U.BG2, fg=color,
                 font=(U.FAMILY_BLACK, U.pt(20))).pack(anchor="w")
        rw = self.room.get("reward") or {}
        lines = []
        boss = (self.view.get("boss") or {}).get("name") or "보스"
        if res == "won":
            lines.append("%s 을(를) 쓰러뜨렸다!" % boss)
            if rw.get("egg"):
                lines.append("%s 의 알을 받았다! 바탕화면에 두면 자라서 부화합니다." % boss)
            else:
                lines.append("이번에는 알이 나오지 않았다. 다음 회차에 다시 도전해 보자.")
        elif res == "timeout":
            lines.append("%s 은(는) 사라져 버렸다. 다음 회차에 다시 도전해 보자." % boss)
        else:
            lines.append("모두 쓰러졌다. 다음 회차에 다시 도전해 보자.")
        if rw.get("prize"):
            lines.append("상금 %s원" % format(rw["prize"], ","))
        if rw.get("damage"):
            lines.append("내 기여 %s" % format(rw["damage"], ","))
        ranks = sorted((self.view.get("players") or []),
                       key=lambda p: -(p.get("damage") or 0))
        if ranks:
            lines.append("기여 순위: " + ", ".join(
                "%d위 %s" % (i + 1, p.get("name")) for i, p in enumerate(ranks[:3])))
        for ln in lines:
            lab = tk.Label(body, text=natural(ln), bg=U.BG2, fg=U.FG, font=U.FONT_S,
                           anchor="w", justify="left")
            lab.pack(fill="x", pady=(2, 0))
            U.wrap_to_width(lab)
        self.say(title)
        self._mark_seen()

    def _mark_seen(self):
        if self._seen_sent:
            return
        self._seen_sent = True
        run_async(self.root, lambda: self.app.api.raid_seen(), lambda _r, _e: None)

    def request_close(self):
        if self.alive and not (self.view.get("over") or self._result_shown):
            from .ui_box import confirm
            if not confirm(self.win, "창 닫기",
                           "판은 그대로 이어집니다. 창을 닫아도 시간이 지나면 "
                           "서버가 대신 싸웁니다. 레이드 탭에서 다시 들어올 수 있어요.",
                           danger=False, ok_text="닫기"):
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
        self.effects = []
        self.fx = None
        for key in list(self.anim_jobs):
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
        if getattr(self.app, "raid_battle", None) is self:
            self.app.raid_battle = None
        if self.on_close:
            try:
                self.on_close()
            except Exception:                               # noqa: BLE001
                pass
