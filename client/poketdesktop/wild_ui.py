# -*- coding: utf-8 -*-
"""야생 조우 — 풀숲, 야생 포켓몬, 몬스터볼 던지기.

흐름
    1. 서버가 정한 시각이 되면 바탕화면에 풀숲이 돋는다 (흔들리는 애니메이션)
    2. 풀숲을 왼쪽 클릭하면 숨어 있던 야생 포켓몬이 튀어나온다
    3. 야생 포켓몬을 오른쪽 클릭하면 몬스터볼을 던진다
    4. 시간 안에 클릭하지 않거나 못 잡으면 사라진다

어떤 포켓몬이 나올지, 잡혔는지는 전부 서버가 정한다.
클라이언트는 보여주기만 한다.
"""
import random
import tkinter as tk

from PIL import ImageTk

from . import effects, sprite_cache, sprites
from . import ui_common as U
from .overlay import Pet
from .ui_common import run_async

POLL_SAFETY = 300          # 아무 일 없어도 이 주기로는 한 번 확인 (초)
BADGE_BLINK = 500          # 야생 표식 깜빡임 (ms)


class GrassPatch(object):
    """흔들리는 풀숲 창."""

    def __init__(self, ctl, wild):
        self.ctl = ctl
        self.wild = wild
        ov = ctl.app.overlay
        key = ov.key
        hexkey = "#%02x%02x%02x" % key

        size = max(28, int(ov.settings["targetHeight"]))
        frames, w, h = effects.grass_frames(size, 6, key)
        self.photos = [ImageTk.PhotoImage(f) for f in frames]
        self.fw, self.fh = w, h
        self.frame = 0

        self.win = tk.Toplevel(ov.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", hexkey)
        self.win.configure(bg=hexkey)
        self.label = tk.Label(self.win, bd=0, highlightthickness=0, bg=hexkey,
                              cursor="hand2")
        self.label.pack()
        self.label.bind("<Button-1>", lambda e: ctl.on_grass_click())
        self.label.bind("<Button-3>", lambda e: ctl.on_grass_click())
        self.label.bind("<Enter>", lambda e: ctl.show_hint(
            self, "풀숲이 흔들린다!\n눌러서 살펴보기"))
        self.label.bind("<Leave>", lambda e: ctl.hide_hint())

        x1, y1, x2, y2 = ov.area()
        m = ov.settings["areaMargin"]
        self.x = random.randint(x1 + m, max(x1 + m, x2 - w - m))
        self.y = random.randint(y1 + m, max(y1 + m, y2 - h - m))
        self.win.geometry("+%d+%d" % (self.x, self.y))
        self.label.configure(image=self.photos[0])
        self._job = None
        self.animate()

    def animate(self):
        self.frame = (self.frame + 1) % len(self.photos)
        self.label.configure(image=self.photos[self.frame])
        self._job = self.ctl.app.root.after(110, self.animate)

    def center(self):
        return self.x + self.fw // 2, self.y + self.fh // 2

    def destroy(self):
        if self._job:
            try:
                self.ctl.app.root.after_cancel(self._job)
            except Exception:
                pass
        try:
            self.win.destroy()
        except Exception:
            pass


class WildPet(Pet):
    """야생 포켓몬. 내 포켓몬과 달리 표식이 붙고, 오른쪽 클릭이 볼 던지기다."""

    def __init__(self, ctl, mon, anim):
        self.ctl = ctl
        Pet.__init__(self, ctl.app.overlay, mon, anim)
        self.badge_win = None
        self.badge_on = True
        self._blink = None
        self.make_badge()
        self.blink()

    def make_badge(self):
        info = self.mon.get("info", {})
        shiny = self.mon.get("shiny")
        text = "★ 야생" if shiny else "야생"
        bg = "#d6a828" if shiny else "#e24e4e"
        w = tk.Toplevel(self.ov.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=bg)
        tk.Label(w, text="%s  %s Lv.%s" % (text, info.get("species", "?"),
                                           info.get("level", "?")),
                 bg=bg, fg="#ffffff", font=U.FONT_XS,
                 padx=6, pady=1).pack()
        self.badge_win = w
        self.place_badge()

    def place_badge(self):
        if not self.badge_win:
            return
        try:
            self.badge_win.update_idletasks()
            bw = self.badge_win.winfo_width()
            self.badge_win.geometry(
                "+%d+%d" % (int(self.x) + self.fw // 2 - bw // 2,
                            int(self.y) - self.badge_win.winfo_height() - 3))
        except Exception:
            pass

    def blink(self):
        """야생이라는 걸 알아채기 쉽게 표식을 깜빡인다."""
        if not self.badge_win:
            return
        try:
            self.badge_on = not self.badge_on
            self.badge_win.attributes("-alpha", 1.0 if self.badge_on else 0.45)
        except Exception:
            return
        self._blink = self.ov.root.after(BADGE_BLINK, self.blink)

    def place(self):
        Pet.place(self)
        self.place_badge()

    def tip_text(self):
        info = self.mon.get("info", {})
        t = "야생의 %s  Lv.%s" % (info.get("species", "?"), info.get("level", "?"))
        types = " / ".join(info.get("types", []))
        if types:
            t += "\n" + types
        if self.mon.get("shiny"):
            t = "★ 색이 다른 개체!\n" + t
        return t + "\n\n왼쪽 클릭 = 배틀\n오른쪽 클릭 = 바로 몬스터볼"

    def on_press(self, e):
        Pet.on_press(self, e)
        self._down = (e.x_root, e.y_root)

    def on_release(self, e):
        d = getattr(self, "_down", None)
        moved = bool(d) and (abs(e.x_root - d[0]) > 4 or abs(e.y_root - d[1]) > 4)
        Pet.on_release(self, e)
        if not moved:                      # 끌지 않고 그냥 눌렀으면 배틀
            self.ctl.start_battle()

    def on_menu(self, e):
        self.ctl.throw_ball()

    def on_double(self, e):
        self.ctl.throw_ball()

    def destroy(self):
        if self._blink:
            try:
                self.ov.root.after_cancel(self._blink)
            except Exception:
                pass
        if self.badge_win:
            try:
                self.badge_win.destroy()
            except Exception:
                pass
            self.badge_win = None
        Pet.destroy(self)


class BallThrow(object):
    """볼이 날아가서 흔들리는 연출. 결과는 서버가 이미 정해서 넘겨준다."""

    def __init__(self, ctl, start, target, shakes, caught, on_done):
        self.ctl = ctl
        ov = ctl.app.overlay
        key = ov.key
        hexkey = "#%02x%02x%02x" % key
        self.shake_frames = [ImageTk.PhotoImage(f)
                             for f in effects.ball_shake_frames(26, key)]
        self.open_photo = ImageTk.PhotoImage(
            effects.ball_image(26, key, open_top=True))
        self.sparkles = [ImageTk.PhotoImage(f)
                         for f in effects.sparkle_frames(52, 6, key)]

        self.win = tk.Toplevel(ov.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", hexkey)
        self.win.configure(bg=hexkey)
        self.label = tk.Label(self.win, bd=0, highlightthickness=0, bg=hexkey,
                              image=self.shake_frames[0])
        self.label.pack()

        self.sx, self.sy = start
        self.tx, self.ty = target
        self.shakes = shakes
        self.caught = caught
        self.on_done = on_done
        self.step = 0
        self.jobs = []
        self.fly()

    def _after(self, ms, fn):
        self.jobs.append(self.ctl.app.root.after(ms, fn))

    def move(self, x, y):
        try:
            self.win.geometry("+%d+%d" % (int(x) - 13, int(y) - 13))
        except Exception:
            pass

    def fly(self):
        """포물선을 그리며 날아간다."""
        n = 16
        if self.step > n:
            return self.shake(0)
        t = self.step / float(n)
        x = self.sx + (self.tx - self.sx) * t
        y = self.sy + (self.ty - self.sy) * t - 70 * (t - t * t) * 4
        self.move(x, y)
        self.label.configure(image=self.shake_frames[self.step % len(self.shake_frames)])
        self.step += 1
        self._after(22, self.fly)

    def shake(self, i):
        """볼에 들어간 뒤 흔들리는 구간. 흔들린 횟수가 곧 아까웠던 정도."""
        self.move(self.tx, self.ty)
        if i == 0:
            self.ctl.hide_wild_sprite()
        if i >= max(1, self.shakes) * len(self.shake_frames):
            return self.finish()
        self.label.configure(image=self.shake_frames[i % len(self.shake_frames)])
        self._after(90, lambda: self.shake(i + 1))

    def finish(self):
        if self.caught:
            self.sparkle(0)
        else:
            self.label.configure(image=self.open_photo)
            self._after(260, self.close)

    def sparkle(self, i):
        if i >= len(self.sparkles):
            return self.close()
        self.label.configure(image=self.sparkles[i])
        self._after(70, lambda: self.sparkle(i + 1))

    def close(self):
        for j in self.jobs:
            try:
                self.ctl.app.root.after_cancel(j)
            except Exception:
                pass
        self.jobs = []
        try:
            self.win.destroy()
        except Exception:
            pass
        if self.on_done:
            self.on_done()


class WildController(object):
    """야생 조우 전체를 맡는다."""

    def __init__(self, app):
        self.app = app
        self.grass = None
        self.pet = None
        self.wild_id = None
        self.throwing = False
        self.hint = None
        self._job = None
        self._expire_job = None

    # ---------------- 서버와 맞추기 ----------------
    def start(self):
        self.check(force=False)

    def stop(self):
        for j in (self._job, self._expire_job):
            if j:
                try:
                    self.app.root.after_cancel(j)
                except Exception:
                    pass
        self._job = self._expire_job = None
        self.clear()

    def check(self, force=False):
        if not self.app.api:
            return

        def done(r, err):
            if err:
                if getattr(err, "status", 0) == 401:
                    self.app.on_session_lost()
                    return
                self.schedule(POLL_SAFETY)
                return
            self.apply(r)
        run_async(self.app.root, lambda: self.app.api.wild(force), done)

    def schedule(self, seconds):
        if self._job:
            try:
                self.app.root.after_cancel(self._job)
            except Exception:
                pass
        seconds = max(5, min(3600, int(seconds)))
        self._job = self.app.root.after(seconds * 1000, self.check)

    def apply(self, r):
        """서버가 알려준 상태대로 화면을 맞춘다."""
        self.app.balls = r.get("balls", self.app.balls)
        w = r.get("wild")
        if not w:
            self.clear()
            self.schedule(r.get("nextInSeconds") or POLL_SAFETY)
            return

        if w["id"] != self.wild_id:
            self.clear()
            self.wild_id = w["id"]

        if w["state"] == "grass":
            if not self.grass:
                self.grass = GrassPatch(self, w)
                self.app.notify("풀숲이 흔들리고 있습니다. 눌러보세요!")
        elif w.get("pokemon") and not self.pet:
            self.show_wild(w["pokemon"])

        self.arm_expiry(w.get("expiresAt"))
        self.schedule(POLL_SAFETY)

    def arm_expiry(self, expires_at):
        """서버가 정한 만료 시각에 맞춰 스스로 정리한다."""
        if self._expire_job:
            try:
                self.app.root.after_cancel(self._expire_job)
            except Exception:
                pass
            self._expire_job = None
        if not expires_at:
            return
        import datetime
        try:
            dt = datetime.datetime.fromisoformat(expires_at)
        except ValueError:
            return
        left = (dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        self._expire_job = self.app.root.after(
            int(max(1.0, left + 1) * 1000), self.on_expired)

    def on_expired(self):
        if self.wild_id and not self.throwing:
            was_wild = self.pet is not None
            wid = self.wild_id
            self.clear()
            self.app.notify("야생 포켓몬이 도망가 버렸습니다..." if was_wild
                            else "풀숲이 잠잠해졌습니다.")
            run_async(self.app.root, lambda: self.app.api.wild_flee(wid),
                      lambda r, e: self.check())
        else:
            self.check()

    # ---------------- 화면 ----------------
    def clear(self):
        self.hide_hint()
        if self.grass:
            self.grass.destroy()
            self.grass = None
        if self.pet:
            self.pet.destroy()
            self.pet = None
        self.wild_id = None

    def hide_wild_sprite(self):
        """볼에 들어간 순간 포켓몬을 감춘다."""
        if self.pet:
            try:
                self.pet.win.withdraw()
                if self.pet.badge_win:
                    self.pet.badge_win.withdraw()
            except Exception:
                pass

    def show_wild_sprite(self):
        if self.pet:
            try:
                self.pet.win.deiconify()
                if self.pet.badge_win:
                    self.pet.badge_win.deiconify()
            except Exception:
                pass

    def show_hint(self, near, text):
        self.hide_hint()
        try:
            w = tk.Toplevel(self.app.root)
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            w.configure(bg=U.TIP_BG)
            tk.Label(w, text=text, bg=U.TIP_BG, fg=U.GOOD,
                     font=U.FONT_TIP, justify="center",
                     padx=7, pady=3).pack()
            w.update_idletasks()
            w.geometry("+%d+%d" % (near.x + near.fw // 2 - w.winfo_width() // 2,
                                   near.y - w.winfo_height() - 4))
            self.hint = w
        except Exception:
            self.hint = None

    def hide_hint(self):
        if self.hint:
            try:
                self.hint.destroy()
            except Exception:
                pass
            self.hint = None

    def show_wild(self, mon):
        ov = self.app.overlay
        s = ov.settings
        path = ov.path_for(mon)
        if not path:
            path = (sprite_cache.find_local(mon.get("num"), mon.get("shiny"))
                    or sprite_cache.find_local(mon.get("num"), False))
        if not path:
            return
        try:
            anim = sprites.load_animation(path, s["targetHeight"],
                                          s["minScale"], s["maxScale"])
        except Exception:
            return
        if self.grass:
            gx, gy = self.grass.x, self.grass.y
            self.grass.destroy()
            self.grass = None
        else:
            gx = gy = None
        self.pet = WildPet(self, mon, anim)
        if gx is not None:
            self.pet.x, self.pet.y = gx, gy
            self.pet.clamp()
            self.pet.place()
        info = mon.get("info", {})
        msg = "야생의 %s (Lv.%s) 이(가) 나타났다!" % (info.get("species"),
                                             info.get("level"))
        if mon.get("shiny"):
            msg = "★ " + msg + " 색이 다르다!"
        self.app.notify(msg)

    # ---------------- 조작 ----------------
    def on_grass_click(self):
        if not self.wild_id or self.pet:
            return
        wid = self.wild_id
        self.hide_hint()

        def done(r, err):
            if err:
                self.clear()
                self.check()
                return
            w = (r or {}).get("wild") or {}
            mon = w.get("pokemon")
            if mon:
                path = (r or {}).get("_spritePath")
                if path:
                    self.app.overlay.paths[(mon.get("num"),
                                            bool(mon.get("shiny")))] = path
                self.show_wild(mon)
                self.arm_expiry(w.get("expiresAt"))

        def work():
            r = self.app.api.wild_reveal(wid)
            mon = ((r or {}).get("wild") or {}).get("pokemon") or {}
            if mon.get("num"):
                r["_spritePath"] = sprite_cache.ensure(
                    self.app.api, mon["num"], mon.get("shiny"))
            return r
        run_async(self.app.root, work, done)

    def start_battle(self):
        """야생 포켓몬을 눌렀다. 배틀 창을 연다."""
        if self.throwing or not self.pet or not self.wild_id:
            return
        if self.app.battle_window:
            return self.app.battle_window.focus()
        wid = self.wild_id
        self.hide_hint()
        self.throwing = True               # 여는 동안 중복 클릭 방지

        def done(r, err):
            self.throwing = False
            if err:
                self.app.notify(getattr(err, "message", str(err)))
                self.check()
                return
            self.hide_wild_sprite()          # 무대에 따로 그리므로 원본은 감춘다
            self.app.open_battle(r.get("battle"), r.get("intro"))
        run_async(self.app.root, lambda: self.app.api.battle_start(wid), done)

    def throw_ball(self):
        if self.throwing or not self.pet or not self.wild_id:
            return
        if self.app.balls <= 0:
            self.app.notify("몬스터볼이 없습니다.")
            return
        self.throwing = True
        self.hide_hint()
        wid = self.wild_id

        def done(r, err):
            if err:
                self.throwing = False
                self.app.notify(getattr(err, "message", str(err)))
                self.check()
                return
            self.app.balls = r.get("balls", self.app.balls)
            self.app.refresh_tray()
            self.play_throw(r)
        run_async(self.app.root, lambda: self.app.api.wild_catch(wid), done)

    def play_throw(self, r):
        pet = self.pet
        if not pet:
            self.throwing = False
            return
        x1, y1, x2, y2 = self.app.overlay.area()
        start = (x2 - 30, y2 - 10)
        target = (pet.x + pet.fw // 2, pet.y + pet.fh // 2)

        def after():
            self.throwing = False
            if r.get("caught"):
                self.clear()
                info = (r.get("pokemon") or {}).get("info", {})
                self.app.notify(r.get("message") or "잡았다!")
                self.app.request_sync()
                if self.app.box_window:
                    self.app.box_window.reload()
                self.check()
            else:
                self.show_wild_sprite()
                left = "  (남은 볼 %d개)" % self.app.balls
                self.app.notify((r.get("message") or "놓쳤다!") + left)
                if self.app.balls <= 0:
                    self.app.notify("몬스터볼이 다 떨어졌습니다.")

        BallThrow(self, start, target, r.get("shakes", 1),
                  bool(r.get("caught")), after)
