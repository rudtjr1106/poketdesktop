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

from . import ball_menu, config, effects, sprite_cache, sprites
from . import platform_os as PLAT
from . import walk_cache
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
        self.fw, self.fh = w, h
        self.frame = 0

        self.win = tk.Toplevel(ov.root)
        self.win.overrideredirect(True)
        bg = PLAT.transparent_window(self.win, hexkey)
        self.view = PLAT.SpriteView(self.win, bg, w, h, cursor="hand2")
        self.label = self.view.widget
        self.photos = self.view.frames(frames, key)
        self.label.bind("<Button-1>", lambda e: ctl.on_grass_click())
        PLAT.bind_right(self.label, lambda e: ctl.on_grass_click())
        self.label.bind("<Enter>", lambda e: ctl.show_hint(
            self, "풀숲이 흔들린다!\n눌러서 살펴보기"))
        self.label.bind("<Leave>", lambda e: ctl.hide_hint())

        x1, y1, x2, y2 = ov.area()
        m = ov.settings["areaMargin"]
        self.x = random.randint(x1 + m, max(x1 + m, x2 - w - m))
        self.y = random.randint(y1 + m, max(y1 + m, y2 - h - m))
        self.win.geometry("+%d+%d" % (self.x, self.y))
        self.view.show(self.photos[0])
        PLAT.raise_above(self.win)
        self._job = None
        self.animate()

    def animate(self):
        self.frame = (self.frame + 1) % len(self.photos)
        self.view.show(self.photos[self.frame])
        if PLAT.NEEDS_HIT_TRACKING:
            # 풀숲 창은 절반 넘게 비어 있다. 그 자리가 바탕화면 클릭을
            # 먹지 않도록 커서를 좇는다 (맥에서만 할 일이 있다).
            try:
                cx, cy = self.ctl.app.root.winfo_pointerxy()
                self.view.update_hit(cx - int(self.x), cy - int(self.y))
            except Exception:                               # noqa: BLE001
                pass
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
        # Pet.__init__ 안에서 place() 가 불리고, 그게 place_badge() 를 부른다.
        # 그래서 배지 관련 값은 반드시 그 전에 만들어둬야 한다.
        self.badge_win = None
        self.badge_on = True
        self._blink = None
        Pet.__init__(self, ctl.app.overlay, mon, anim)
        self.make_badge()
        self.blink()

    def make_badge(self):
        info = self.mon.get("info", {})
        shiny = self.mon.get("shiny")
        text = "★ 야생" if shiny else "야생"
        bg = "#d6a828" if shiny else "#e24e4e"
        w = tk.Toplevel(self.ov.root)
        w.overrideredirect(True)
        w.configure(bg=bg)
        tk.Label(w, text="%s  %s Lv.%s" % (text, info.get("species", "?"),
                                           info.get("level", "?")),
                 bg=bg, fg="#ffffff", font=U.FONT_XS,
                 padx=6, pady=1).pack()
        PLAT.raise_above(w)
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
        return (t + "\n\n왼쪽 클릭 = 배틀"
                "\n오른쪽 클릭 = 볼 고르기"
                "\n두 번 클릭 = 바로 던지기")

    def on_press(self, e):
        Pet.on_press(self, e)
        self._down = (e.x_root, e.y_root)

    def on_release(self, e):
        d = getattr(self, "_down", None)
        moved = bool(d) and (abs(e.x_root - d[0]) > 4 or abs(e.y_root - d[1]) > 4)
        Pet.on_release(self, e)
        if moved or self.ctl.app.battle:   # 끌었거나 이미 싸우는 중이면 무시
            return
        # **바로 배틀을 열면 두 번 클릭이 죽는다.** 첫 클릭이 배틀을
        # 시작하면서 throwing 을 잠그는데, 두 번째 클릭은 그때 도착해서
        # "이미 뭔가 하는 중" 으로 걸러진다. 아무 일도 안 일어나고
        # 배틀만 시작된 것처럼 보인다.
        # 두 번째 클릭이 올 만큼만 기다렸다가 연다.
        self._cancel_battle_job()
        self._battle_job = self.ctl.app.root.after(_double_ms(), self._go_battle)

    def _cancel_battle_job(self):
        job = getattr(self, "_battle_job", None)
        if job:
            try:
                self.ctl.app.root.after_cancel(job)
            except Exception:                               # noqa: BLE001
                pass
        self._battle_job = None

    def _go_battle(self):
        self._battle_job = None
        if not self.ctl.app.battle:
            self.ctl.start_battle()

    def on_menu(self, e):
        # 배틀 중이면 배틀 쪽으로 넘긴다 (체력이 깎여 있어 잘 잡힌다).
        # 이벤트를 같이 넘겨야 거기서도 볼 고르는 메뉴가 뜬다.
        if self.ctl.app.battle:
            return self.ctl.app.battle.throw_ball(e)
        self.ctl.ball_menu(e)

    def on_double(self, e):
        # 두 번 누르면 곧바로 마지막에 쓴 볼로 던진다. 한 마리씩 잡을 때
        # 메뉴를 매번 여는 건 번거롭다.
        # 첫 클릭이 예약해 둔 배틀 열기를 먼저 취소한다.
        self._cancel_battle_job()
        if self.ctl.app.battle:
            return self.ctl.app.battle.throw_ball()
        self.ctl.throw_ball()

    def destroy(self):
        self._cancel_battle_job()
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


def _double_ms():
    """이 PC 에서 두 번 클릭으로 치는 간격(ms).

    사람마다 다르게 맞춰 쓴다. 우리가 임의로 정하면 느리게 누르는 사람은
    두 번 클릭이 안 먹고, 빠르게 누르는 사람은 배틀이 늦게 열린다.
    """
    return PLAT.double_click_ms()


class BallThrow(object):
    """볼이 날아가서 흔들리는 연출. 결과는 서버가 이미 정해서 넘겨준다."""

    def __init__(self, ctl, start, target, shakes, caught, on_done,
                 ball="POKEBALL"):
        self.ctl = ctl
        ov = ctl.app.overlay
        key = ov.key
        hexkey = "#%02x%02x%02x" % key
        # 던진 볼에 따라 그림이 달라진다. 스무 가지를 던지는데 전부 같은
        # 빨간 볼이면 뭘 던졌는지 알 수가 없다.
        self.win = tk.Toplevel(ov.root)
        self.win.overrideredirect(True)
        bg = PLAT.transparent_window(self.win, hexkey)
        self.view = PLAT.SpriteView(self.win, bg, 26, 26)
        self.label = self.view.widget
        self.shake_frames = self.view.frames(
            effects.ball_shake_frames(26, key, ball), key)
        self.open_photo = self.view.frames(
            [effects.ball_image(26, key, open_top=True, ball=ball)], key)[0]
        # 반짝임은 볼보다 크다(52px). show() 가 창 크기를 알아서 맞춘다.
        self.sparkles = self.view.frames(effects.sparkle_frames(52, 6, key), key)
        self.view.show(self.shake_frames[0])
        PLAT.raise_above(self.win)

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
        self.view.show(self.shake_frames[self.step % len(self.shake_frames)])
        self.step += 1
        self._after(22, self.fly)

    def shake(self, i):
        """볼에 들어간 뒤 흔들리는 구간. 흔들린 횟수가 곧 아까웠던 정도."""
        self.move(self.tx, self.ty)
        if i == 0:
            self.ctl.hide_wild_sprite()
        if i >= max(1, self.shakes) * len(self.shake_frames):
            return self.finish()
        self.view.show(self.shake_frames[i % len(self.shake_frames)])
        self._after(90, lambda: self.shake(i + 1))

    def finish(self):
        if self.caught:
            self.sparkle(0)
        else:
            self.view.show(self.open_photo)
            self._after(260, self.close)

    def sparkle(self, i):
        if i >= len(self.sparkles):
            return self.close()
        self.view.show(self.sparkles[i])
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
        # 서버가 공개·던지기 응답에 실어 주는 볼 목록. 우클릭 메뉴가 이걸 쓴다.
        self.ball_options = []
        # 박스가 찼다는 말을 한 번만 하려고. 폴링마다 뜨면 성가시다.
        self._said_full = None
        self.app = app
        self.grass = None
        self.pet = None
        self.wild_id = None
        self.throwing = False
        self.revealing = False    # 풀숲을 눌러 응답을 기다리는 중인가
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
        """서버에 지금 상태를 물어본다.

        force 는 사용자가 '풀숲 찾아보기' 를 직접 눌렀다는 뜻이다.
        직접 눌렀는데 아무 일도 안 일어나면 고장으로 보이므로,
        그때는 얼마나 기다려야 하는지 알려준다.
        """
        if not self.app.api:
            return

        def done(r, err):
            if err:
                if getattr(err, "status", 0) == 401:
                    self.app.on_session_lost()
                    return
                if force:
                    self.app.notify("서버에 물어보지 못했습니다.")
                self.schedule(POLL_SAFETY)
                return
            self.apply(r, tell=force)
        run_async(self.app.root, lambda: self.app.api.wild(force), done)

    def _say_wait(self, r):
        """아직 때가 아니면 얼마나 남았는지 알려준다."""
        left = r.get("nextInSeconds")
        if left is None:
            return self.app.notify("아직 풀숲이 돋지 않았습니다.")
        if left <= 0:
            return self.app.notify("곧 풀숲이 돋습니다.")
        if left < 60:
            when = "%d초" % left
        else:
            when = "%d분" % ((left + 59) // 60)
        self.app.notify("아직 풀숲이 돋지 않았습니다. %s 뒤에 다시 살펴보세요."
                        % when)

    def schedule(self, seconds):
        if self._job:
            try:
                self.app.root.after_cancel(self._job)
            except Exception:
                pass
        seconds = max(5, min(3600, int(seconds)))
        self._job = self.app.root.after(seconds * 1000, self.check)

    def apply(self, r, tell=False):
        """서버가 알려준 상태대로 화면을 맞춘다.

        tell 이면 사용자가 직접 눌러서 온 응답이라 결과를 말로도 알려준다.
        """
        self.app.balls = r.get("balls", self.app.balls)
        # 자리가 없어서 안 돋는 것이면 알려준다. 안 그러면 어느 날부터
        # 풀숲이 영영 안 돋는 고장으로만 보인다.
        full = r.get("boxFull")
        if full and full.get("message") != self._said_full:
            self._said_full = full.get("message")
            self.app.notify(full["message"])
        elif not full:
            self._said_full = None
        w = r.get("wild")
        if not w:
            self.clear()
            if tell:
                self._say_wait(r)
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
        if r.get("ballOptions"):
            self.ball_options = r["ballOptions"]

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
        # 싸우는 중이면 만료시키지 않는다.
        #
        # 배틀을 시작하면 서버가 야생의 시간을 넉넉히 늘려 준다
        # (battle_routes.py 의 start). 그런데 이 타이머는 배틀 전에
        # 받아 둔 짧은 시각으로 이미 걸려 있어서, 그대로 두면 싸우는
        # 도중에 터진다. 그러면 상대 도트만 사라지고 배틀은 계속 돌아서
        # "도망갔다는데 계속 싸운다" 가 된다. 게다가 wild_flee 까지
        # 불러서 서버의 야생을 지워 버린다.
        b = self.app.battle
        if b is not None and not getattr(b, "closed", False):
            # 배틀이 끝나면 그쪽에서 다시 맞춰 준다. 그때까지만 미뤄 둔다.
            self._expire_job = self.app.root.after(15000, self.on_expired)
            return
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
        # 만료 타이머도 같이 끈다. 안 끄면 이미 사라진 야생을 두고
        # 나중에 한 번 더 깨어나 쓸데없이 서버를 부른다.
        self.arm_expiry(None)
        if self.grass:
            self.grass.destroy()
            self.grass = None
        if self.pet:
            self.pet.destroy()
            self.pet = None
        self.wild_id = None
        # 야생이 사라졌으면 '보내는 중' 표시도 풀어야 한다.
        # 안 그러면 다음 풀숲을 눌러도 반응하지 않는다.
        self.revealing = False

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
                PLAT.show_again(self.pet.win)
                if self.pet.badge_win:
                    PLAT.show_again(self.pet.badge_win)
            except Exception:
                pass

    def show_hint(self, near, text):
        self.hide_hint()
        try:
            w = tk.Toplevel(self.app.root)
            w.overrideredirect(True)
            w.configure(bg=U.TIP_BG)
            tk.Label(w, text=text, bg=U.TIP_BG, fg=U.GOOD,
                     font=U.FONT_TIP, justify="center",
                     padx=7, pady=3).pack()
            w.update_idletasks()
            w.geometry("+%d+%d" % (near.x + near.fw // 2 - w.winfo_width() // 2,
                                   near.y - w.winfo_height() - 4))
            PLAT.raise_above(w)
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
        # 걷는 도트를 먼저 쓴다. 내 포켓몬은 걸어다니는데 야생만 옛날
        # 배틀 도트로 서 있으면 둘이 다른 게임에서 온 것처럼 보인다.
        # (ov.make 가 하는 것과 같은 순서다)
        anim = None
        sheet, meta = ov.walks.get(mon.get("num")) or (None, None)
        if sheet and meta:
            try:
                anim = sprites.load_walk(sheet, meta, s["targetHeight"],
                                         s["minScale"],
                                         max(2.5, s["maxScale"]))
            except Exception:                              # noqa: BLE001
                anim = None
        if anim is None:
            # 걷는 도트가 없는 종(43마리)은 배틀 도트로 대신한다.
            path = ov.path_for(mon)
            if not path:
                path = (sprite_cache.find_local(mon.get("num"),
                                                mon.get("shiny"))
                        or sprite_cache.find_local(mon.get("num"), False))
            if not path:
                return
            try:
                anim = sprites.load_animation(path, s["targetHeight"],
                                              s["minScale"], s["maxScale"])
            except Exception:                              # noqa: BLE001
                return
        if self.grass:
            gx, gy = self.grass.x, self.grass.y
            self.grass.destroy()
            self.grass = None
        else:
            gx = gy = None
        # 어떤 경로로 들어오든 야생은 한 마리만 있어야 한다.
        # 그냥 덮어쓰면 옛 창이 주인 없이 화면에 남는다.
        if self.pet:
            try:
                self.pet.destroy()
            except Exception:                              # noqa: BLE001
                pass
            self.pet = None
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
        # 이 요청은 비동기다. 응답이 오기 전까지 self.pet 은 그대로 비어 있어서,
        # 이 조건만으로는 연타를 막지 못한다. 실제로 다섯 번 누르면 야생이
        # 다섯 마리 생겼다. 보내는 중인지도 같이 본다.
        if not self.wild_id or self.pet or self.revealing:
            return
        wid = self.wild_id
        self.revealing = True
        self.hide_hint()

        def done(r, err):
            self.revealing = False
            if err:
                self.clear()
                self.check()
                return
            # 던질 볼 목록. 배율이 여기서 처음 정해진다.
            if (r or {}).get("ballOptions"):
                self.ball_options = r["ballOptions"]
            w = (r or {}).get("wild") or {}
            mon = w.get("pokemon")
            if mon:
                path = (r or {}).get("_spritePath")
                if path:
                    self.app.overlay.paths[(mon.get("num"),
                                            bool(mon.get("shiny")))] = path
                sheet, meta = (r or {}).get("_walk") or (None, None)
                if sheet and meta:
                    self.app.overlay.walks[mon.get("num")] = (sheet, meta)
                self.show_wild(mon)
                self.arm_expiry(w.get("expiresAt"))

        def work():
            r = self.app.api.wild_reveal(wid)
            mon = ((r or {}).get("wild") or {}).get("pokemon") or {}
            if mon.get("num"):
                r["_spritePath"] = sprite_cache.ensure(
                    self.app.api, mon["num"], mon.get("shiny"))
                # 걷는 도트도 같이 받는다. overlay.walks 는 내 목록으로만
                # 채워지기 때문에, 이걸 안 하면 야생만 옛날 배틀 도트로
                # 서 있게 된다.
                try:
                    r["_walk"] = walk_cache.ensure(self.app.api, mon["num"])
                except Exception:                          # noqa: BLE001
                    r["_walk"] = (None, None)
            return r
        run_async(self.app.root, work, done)

    def start_battle(self):
        """야생 포켓몬을 눌렀다. 배틀 창을 연다."""
        if self.throwing or not self.pet or not self.wild_id:
            return
        if self.app.battle:
            return self.app.battle.focus()
        wid = self.wild_id
        self.hide_hint()
        self.throwing = True               # 여는 동안 중복 클릭 방지

        def done(r, err):
            self.throwing = False
            if err:
                self.app.notify(getattr(err, "message", str(err)))
                self.check()
                return
            # 바탕화면에서 그대로 싸우므로 야생 도트는 그 자리에 그대로 둔다
            self.app.open_battle(r.get("battle"), r.get("intro"),
                                 r.get("ballOptions"))
        run_async(self.app.root, lambda: self.app.api.battle_start(wid), done)

    def ball_menu(self, e):
        """어떤 볼을 던질지 고른다.

        목록은 서버가 공개·던지기 응답에 실어 준 것을 그대로 쓴다.
        누를 때마다 서버를 왕복하면 야생은 60초짜리라 그 시간을 깎아먹고,
        서버가 자다 깨는 중이면 메뉴가 아예 안 뜬다.
        """
        if self.throwing or not self.pet or not self.wild_id:
            return
        opts = self.ball_options
        if not opts:
            return self.throw_ball()          # 목록이 아직이면 예전처럼
        self.hide_hint()
        ball_menu.popup(self.app.root, e, opts, self.throw_ball,
                        on_shop=self.app.open_shop)

    def last_ball(self):
        """마지막에 쓴 볼. 없으면 몬스터볼."""
        want = (self.app.settings.get("lastBall") or "POKEBALL")
        for o in self.ball_options or ():
            if o["id"] == want and o["count"] > 0:
                return want
        return "POKEBALL"

    def _thrown(self, r):
        """방금 던진 볼. 서버가 실어 보낸 것을 먼저 믿는다.

        설정의 lastBall 은 야생에서 던질 때만 갱신된다. 배틀 중에 던지면
        어긋날 수 있어서, 서버가 알려준 값이 있으면 그쪽을 쓴다.
        """
        return (r or {}).get("ball") or self.last_ball()

    def throw_ball(self, ball=None):
        if self.throwing or not self.pet or not self.wild_id:
            return
        ball = ball or self.last_ball()
        if ball == "POKEBALL" and self.app.balls <= 0:
            self.app.notify("몬스터볼이 없습니다.")
            return
        self.throwing = True
        self.hide_hint()
        wid = self.wild_id
        # 어떤 볼을 썼는지 기억해 둔다. 게임 상태가 아니라 취향이라
        # 서버에 둘 이유가 없다.
        self.app.settings["lastBall"] = ball
        config.save_settings(self.app.settings)

        def done(r, err):
            if err:
                self.throwing = False
                self.app.notify(getattr(err, "message", str(err)))
                self.check()
                return
            self.app.balls = r.get("balls", self.app.balls)
            if r.get("ballOptions"):
                self.ball_options = r["ballOptions"]
            self.app.refresh_tray()
            self.play_throw(r)
        run_async(self.app.root,
                  lambda: self.app.api.wild_catch(wid, ball), done)

    def play_catch(self, r, on_done=None):
        """볼 던지는 연출만 재생한다. 결과 처리는 부르는 쪽에서.

        배틀 중에 던질 때도 이걸 쓴다.
        """
        pet = self.pet
        if not pet:
            if on_done:
                on_done()
            return
        x1, y1, x2, y2 = self.app.overlay.area()
        start = (x2 - 30, y2 - 10)
        target = (pet.x + pet.fw // 2, pet.y + pet.fh // 2)

        def after():
            if r.get("caught"):
                self.clear()
            else:
                self.show_wild_sprite()
            if on_done:
                on_done()
        BallThrow(self, start, target, r.get("shakes", 1),
                  bool(r.get("caught")), after, self._thrown(r))

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
                  bool(r.get("caught")), after, self._thrown(r))
