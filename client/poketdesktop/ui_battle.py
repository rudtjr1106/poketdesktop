# -*- coding: utf-8 -*-
"""배틀 화면.

서버가 한 턴을 돌리고 '무슨 일이 있었는지'(events)를 순서대로 준다.
이 창은 그걸 하나씩 재생만 한다. 계산은 하나도 안 한다.

연출은 단순하게
    공격   때리는 쪽이 상대 쪽으로 훅 다가갔다 돌아온다
    피격   맞은 쪽이 파르르 떨리고 잠깐 하얗게 번쩍인다
    체력   막대가 스르륵 줄어든다 (색도 초록->노랑->빨강)
    쓰러짐 아래로 미끄러지며 사라진다
    포획   몬스터볼이 날아가 흔들리고, 잡히면 반짝인다
"""
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from . import effects, sprite_cache, sprites
from . import ui_common as U
from .ui_common import apply_theme, run_async, style_window

W, H = 640, 560
ARENA_H = 300

# 연출 속도 (ms)
MSG_MS = 620
LUNGE_MS = 26
SHAKE_MS = 34
HP_MS = 22

BG_SKY = "#2b3a52"
BG_GROUND = "#3c5a3a"


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mask_of(img, key):
    """투명색으로 칠해둔 배경을 알파로 되돌린다."""
    px = img.tobytes()
    mb = bytearray(img.width * img.height)
    kr, kg, kb = key
    for i in range(0, len(px), 3):
        if px[i] != kr or px[i + 1] != kg or px[i + 2] != kb:
            mb[i // 3] = 255
    return Image.frombytes("L", img.size, bytes(mb))


def _to_photo(img, key):
    rgba = img.convert("RGBA")
    rgba.putalpha(_mask_of(img, key))
    return ImageTk.PhotoImage(rgba)


class Combatant(object):
    """화면에 그려지는 한 쪽."""

    def __init__(self, canvas, data, anim, x, y, facing, scale_tag):
        self.cv = canvas
        self.data = data
        self.anim = anim
        self.x, self.y = x, y
        self.home = (x, y)
        self.facing = facing
        self.frames = [_to_photo(f, anim.key) for f in anim.frames[facing]]
        self.i = 0
        self.item = canvas.create_image(x, y, image=self.frames[0], anchor="center")
        self.tag = scale_tag
        self.hp = data["hp"]
        self.maxhp = data["maxhp"]

    def step(self):
        self.i = (self.i + 1) % len(self.frames)
        self.cv.itemconfigure(self.item, image=self.frames[self.i])

    def move_to(self, x, y):
        self.x, self.y = x, y
        self.cv.coords(self.item, x, y)

    def hide(self):
        self.cv.itemconfigure(self.item, state="hidden")

    def show(self):
        self.cv.itemconfigure(self.item, state="normal")


class BattleWindow(object):
    def __init__(self, root, app, battle, intro=None):
        self.root = root
        self.app = app
        self.b = battle
        self.busy = False
        self.closed = False
        self.jobs = []
        self.anim_job = None

        self.win = tk.Toplevel(root)
        style_window(self.win, "포켓 데스크톱 — 배틀", W, H)
        apply_theme(self.win)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.ask_close)
        self.win.attributes("-topmost", True)

        # ---- 무대 ----
        self.cv = tk.Canvas(self.win, width=W, height=ARENA_H, bg=BG_SKY,
                            highlightthickness=0, bd=0)
        self.cv.pack(fill="x")
        self.cv.create_rectangle(0, ARENA_H - 96, W, ARENA_H, fill=BG_GROUND,
                                 outline="")
        self.cv.create_oval(W - 250, 118, W - 70, 158, fill="#4a6a48", outline="")
        self.cv.create_oval(60, ARENA_H - 76, 250, ARENA_H - 30, fill="#4a6a48",
                            outline="")

        self.foe_box = self._hp_box(24, 22, "foe")
        self.me_box = self._hp_box(W - 300, ARENA_H - 96, "me")

        # ---- 메시지 ----
        self.msg = tk.Label(self.win, text="", bg=U.BG2, fg=U.FG, font=U.FONT,
                            anchor="w", justify="left", padx=14, pady=10,
                            height=2, wraplength=W - 40)
        self.msg.pack(fill="x")

        # ---- 명령 ----
        cmd = ttk.Frame(self.win, padding=(14, 10, 14, 12))
        cmd.pack(fill="both", expand=True)
        self.moves_frame = tk.Frame(cmd, bg=U.BG)
        self.moves_frame.pack(side="left", fill="both", expand=True)
        right = tk.Frame(cmd, bg=U.BG)
        right.pack(side="right", fill="y", padx=(12, 0))
        self.btn_ball = ttk.Button(right, text="몬스터볼", style="Accent.TButton",
                                   command=self.throw_ball)
        self.btn_ball.pack(fill="x", pady=(0, 6))
        self.btn_run = ttk.Button(right, text="도망가기", style="Ghost.TButton",
                                  command=self.run_away)
        self.btn_run.pack(fill="x")
        self.balls_label = tk.Label(right, text="", bg=U.BG, fg=U.FG_DIM,
                                    font=U.FONT_XS)
        self.balls_label.pack(pady=(8, 0))

        self.me = None
        self.foe = None
        self.move_btns = []
        self.load_sprites(intro)

    # ---------------- 체력 막대 ----------------
    def _hp_box(self, x, y, who):
        cv = self.cv
        box = {}
        box["bg"] = cv.create_rectangle(x, y, x + 276, y + 62, fill=U.BG2,
                                        outline=U.LINE)
        box["name"] = cv.create_text(x + 14, y + 18, text="", anchor="w",
                                     fill=U.FG, font=U.FONT_B)
        box["lv"] = cv.create_text(x + 262, y + 18, text="", anchor="e",
                                   fill=U.FG_DIM, font=U.FONT_XS)
        box["track"] = cv.create_rectangle(x + 14, y + 34, x + 262, y + 44,
                                           fill=U.BG3, outline="")
        box["bar"] = cv.create_rectangle(x + 14, y + 34, x + 262, y + 44,
                                         fill=U.GOOD, outline="")
        box["hp"] = cv.create_text(x + 262, y + 54, text="", anchor="e",
                                   fill=U.FG_DIM, font=U.FONT_XS)
        box["st"] = cv.create_text(x + 14, y + 54, text="", anchor="w",
                                   fill=U.ACCENT, font=U.FONT_XS)
        box["x0"], box["w"] = x + 14, 248
        box["who"] = who
        return box

    def _paint_hp(self, box, side, show_numbers=True):
        cv = self.cv
        hp, mx = side["hp"], max(1, side["maxhp"])
        ratio = max(0.0, min(1.0, hp / float(mx)))
        color = U.GOOD if ratio > 0.5 else (U.ACCENT if ratio > 0.2 else U.DANGER)
        x0 = box["x0"]
        cv.coords(box["bar"], x0, cv.coords(box["track"])[1],
                  x0 + box["w"] * ratio, cv.coords(box["track"])[3])
        cv.itemconfigure(box["bar"], fill=color)
        name = side["name"]
        if box["who"] == "foe":
            name = "야생 " + name
        if side.get("shiny"):
            name = "★ " + name
        cv.itemconfigure(box["name"], text=name)
        cv.itemconfigure(box["lv"], text="Lv.%d" % side["level"])
        cv.itemconfigure(box["hp"],
                         text="%d / %d" % (hp, mx) if show_numbers else "")
        cv.itemconfigure(box["st"], text=side.get("statusKr") or "")

    # ---------------- 준비 ----------------
    def load_sprites(self, intro):
        self.say("잠시만...")

        def work():
            out = {}
            for who in ("me", "foe"):
                s = self.b[who]
                out[who] = sprite_cache.ensure(self.app.api, s.get("num"),
                                               s.get("shiny"))
            return out

        def done(paths, err):
            if self.closed:
                return
            if err or not paths:
                self.say("도트를 불러오지 못했습니다.")
                return
            try:
                self._build(paths, intro)
            except Exception as e:                       # noqa: BLE001
                self.say("화면을 만들지 못했습니다: %s" % e)
        run_async(self.root, work, done)

    def _build(self, paths, intro):
        s = self.app.settings
        me_anim = sprites.load_animation(paths["me"], target_height=104,
                                         min_scale=0.2, max_scale=3.0)
        foe_anim = sprites.load_animation(paths["foe"], target_height=88,
                                          min_scale=0.2, max_scale=3.0)
        # 서로 마주 보게: 내 쪽은 오른쪽을, 상대는 왼쪽을 본다
        self.me = Combatant(self.cv, self.b["me"], me_anim, 160,
                            ARENA_H - 78, sprites.RIGHT, "me")
        self.foe = Combatant(self.cv, self.b["foe"], foe_anim, W - 160, 130,
                             sprites.LEFT, "foe")
        self.refresh(self.b)
        self.animate()
        if intro:
            self.say(intro)
        else:
            self.say("무엇을 할까?")

    def animate(self):
        if self.closed:
            return
        for c in (self.me, self.foe):
            if c:
                c.step()
        self.anim_job = self.root.after(140, self.animate)

    # ---------------- 갱신 ----------------
    def refresh(self, battle):
        self.b = battle
        self._paint_hp(self.foe_box, battle["foe"], show_numbers=False)
        self._paint_hp(self.me_box, battle["me"])
        if self.me:
            self.me.hp = battle["me"]["hp"]
        if self.foe:
            self.foe.hp = battle["foe"]["hp"]
        self.build_moves()
        self.balls_label.configure(text="남은 볼 %d개" % self.app.balls)

    def build_moves(self):
        for w in self.moves_frame.winfo_children():
            w.destroy()
        self.move_btns = []
        moves = self.b["me"].get("moves") or []
        for i, m in enumerate(moves[:4]):
            color = U.TYPE_COLOR.get(m.get("type"), U.BG3)
            f = tk.Frame(self.moves_frame, bg=color, cursor="hand2")
            f.grid(row=i // 2, column=i % 2, sticky="nsew", padx=3, pady=3)
            name = tk.Label(f, text=m["kr"], bg=color, fg="#14141a",
                            font=U.FONT_B, cursor="hand2")
            name.pack(padx=10, pady=(6, 0))
            sub = "%s · %d" % (m.get("typeKr") or "", m.get("power") or 0) \
                if m.get("power") else (m.get("typeKr") or "변화")
            info = tk.Label(f, text="%s   PP %d/%d" % (sub, m["pp"], m["maxpp"]),
                            bg=color, fg="#2a2a35", font=U.FONT_XS, cursor="hand2")
            info.pack(padx=10, pady=(0, 6))
            dead = m["pp"] <= 0 and m["key"] != "STRUGGLE"
            for w in (f, name, info):
                if dead:
                    w.configure(bg=U.BG3)
                    if w is not f:
                        w.configure(fg=U.FG_FAINT)
                else:
                    w.bind("<Button-1>", lambda e, k=m["key"]: self.use(k))
            self.move_btns.append(f)
        self.moves_frame.grid_columnconfigure(0, weight=1)
        self.moves_frame.grid_columnconfigure(1, weight=1)

    def say(self, text):
        try:
            self.msg.configure(text=text or "")
        except Exception:
            pass

    def lock(self, on):
        self.busy = on
        state = "disabled" if on else "normal"
        for b in (self.btn_ball, self.btn_run):
            b.configure(state=state)

    # ---------------- 명령 ----------------
    def use(self, key):
        if self.busy or self.b.get("over"):
            return
        self.lock(True)
        self.say("...")

        def done(r, err):
            if err:
                self.lock(False)
                return self.say(getattr(err, "message", str(err)))
            self.play(r.get("events") or [], r)
        run_async(self.root,
                  lambda: self.app.api.battle_move(self.b["id"], key), done)

    def throw_ball(self):
        if self.busy or self.b.get("over"):
            return
        if self.app.balls <= 0:
            return self.say("몬스터볼이 없습니다.")
        self.lock(True)

        def done(r, err):
            if err:
                self.lock(False)
                return self.say(getattr(err, "message", str(err)))
            self.app.balls = r.get("balls", self.app.balls)
            self.app.refresh_tray()
            self.play_ball(r)
        run_async(self.root, lambda: self.app.api.battle_ball(self.b["id"]), done)

    def run_away(self):
        if self.busy or self.b.get("over"):
            return
        self.lock(True)

        def done(r, err):
            if err:
                self.lock(False)
                return self.say(getattr(err, "message", str(err)))
            self.play(r.get("events") or [], r)
        run_async(self.root, lambda: self.app.api.battle_run(self.b["id"]), done)

    # ---------------- 연출 ----------------
    def after(self, ms, fn):
        j = self.root.after(ms, fn)
        self.jobs.append(j)
        return j

    def play(self, events, result):
        """이벤트를 하나씩 재생하고 끝나면 결과를 처리한다."""
        queue = list(events)

        def nxt():
            if self.closed:
                return
            if not queue:
                return self.finish(result)
            ev = queue.pop(0)
            self.render(ev, nxt)
        nxt()

    def render(self, ev, done):
        t = ev.get("t")
        text = ev.get("text")
        if text:
            self.say(text)
        who = ev.get("who")
        actor = self.me if who == "me" else self.foe

        if t == "move" and actor:
            return self.lunge(actor, done)
        if t in ("hit", "chip", "recoil"):
            side = "me" if ev.get("target") == "me" or t in ("chip", "recoil") \
                and who == "me" else ("foe" if ev.get("target") == "foe" else who)
            target = self.me if side == "me" else self.foe
            box = self.me_box if side == "me" else self.foe_box
            if target:
                return self.shake(target, lambda: self.drain(
                    box, target, ev.get("hp", 0), ev.get("maxhp", 1), done))
        if t == "heal":
            target = self.me if who == "me" else self.foe
            box = self.me_box if who == "me" else self.foe_box
            if target:
                return self.drain(box, target, ev.get("hp", 0),
                                  ev.get("maxhp", 1), done)
        if t == "faint":
            target = self.me if who == "me" else self.foe
            if target:
                return self.faint(target, done)
        self.after(MSG_MS, done)

    def lunge(self, c, done, back=None):
        """때리는 쪽이 상대 쪽으로 훅 다가갔다 돌아온다."""
        dx = 34 if c is self.me else -34
        dy = -18 if c is self.me else 18
        steps = 6

        def go(i):
            if self.closed:
                return
            if i > steps * 2:
                c.move_to(*c.home)
                return self.after(180, done)
            k = i if i <= steps else steps * 2 - i
            c.move_to(c.home[0] + dx * k / float(steps),
                      c.home[1] + dy * k / float(steps))
            self.after(LUNGE_MS, lambda: go(i + 1))
        go(1)

    def shake(self, c, done):
        """맞은 쪽이 파르르 떨린다."""
        seq = [-7, 7, -5, 5, -3, 3, 0]

        def go(i):
            if self.closed:
                return
            if i >= len(seq):
                c.move_to(*c.home)
                return done()
            c.move_to(c.home[0] + seq[i], c.home[1])
            self.after(SHAKE_MS, lambda: go(i + 1))
        go(0)

    def drain(self, box, c, hp, maxhp, done):
        """체력 막대가 스르륵 줄어든다."""
        start = c.hp
        c.hp = hp
        span = max(1, abs(start - hp))
        steps = min(24, max(6, span))

        def go(i):
            if self.closed:
                return
            if i > steps:
                return self.after(140, done)
            cur = start + (hp - start) * i / float(steps)
            self._paint_hp(box, {"hp": int(round(cur)), "maxhp": maxhp,
                                 "name": box_name(self, box),
                                 "level": box_level(self, box),
                                 "shiny": box_shiny(self, box),
                                 "statusKr": box_status(self, box)},
                           show_numbers=(box is self.me_box))
            self.after(HP_MS, lambda: go(i + 1))
        go(0)

    def faint(self, c, done):
        """아래로 미끄러지며 사라진다."""
        def go(i):
            if self.closed:
                return
            if i > 12:
                c.hide()
                return self.after(300, done)
            c.move_to(c.home[0], c.home[1] + i * 7)
            self.after(28, lambda: go(i + 1))
        go(1)

    # ---------------- 결과 ----------------
    def finish(self, result):
        if self.closed:
            return
        b = result.get("battle")
        if b:
            self.refresh(b)
        self.lock(False)

        if not b or not b.get("over"):
            if not result.get("events"):
                self.say("무엇을 할까?")
            return

        res = b.get("result")
        if res == "won":
            lines = ["야생 포켓몬을 쓰러뜨렸다!"]
            for e in (result.get("exp") or []):
                lines.append("%s 은(는) %d 경험치를 얻었다!%s"
                             % (e["name"], e["gained"],
                                "  (학습장치)" if e.get("shared") else ""))
                if e.get("leveledUp"):
                    lines.append("%s 은(는) 레벨 %d 이 되었다!" % (e["name"], e["level"]))
                for mv in e.get("learned") or []:
                    lines.append("%s 은(는) %s 을(를) 배웠다!" % (e["name"], mv))
            self.roll(lines, self.close)
        elif res == "lost":
            if result.get("canSwitch") and result.get("party"):
                self.ask_switch(result["party"])
            else:
                self.roll(["눈앞이 캄캄해졌다..."], self.close)
        elif res == "fled":
            self.roll(["무사히 도망쳤다."], self.close)
        else:
            self.close()

    def roll(self, lines, done):
        """메시지를 순서대로 보여준다."""
        q = list(lines)

        def nxt():
            if self.closed:
                return
            if not q:
                return self.after(700, done)
            self.say(q.pop(0))
            self.after(MSG_MS + 260, nxt)
        nxt()

    def ask_switch(self, party):
        self.say("%s 은(는) 쓰러졌다! 다음 포켓몬을 고르세요." % self.b["me"]["name"])
        for w in self.moves_frame.winfo_children():
            w.destroy()
        for i, m in enumerate(party[:4]):
            info = m.get("info", {})
            f = tk.Frame(self.moves_frame, bg=U.BG3, cursor="hand2")
            f.grid(row=i // 2, column=i % 2, sticky="nsew", padx=3, pady=3)
            lb = tk.Label(f, text="%s  Lv.%s" % (info.get("name"), m["level"]),
                          bg=U.BG3, fg=U.FG, font=U.FONT_B, cursor="hand2")
            lb.pack(padx=10, pady=8)
            for w in (f, lb):
                w.bind("<Button-1>", lambda e, pid=m["id"]: self.do_switch(pid))

    def do_switch(self, pid):
        self.lock(True)

        def done(r, err):
            if err:
                self.lock(False)
                return self.say(getattr(err, "message", str(err)))
            b = r["battle"]
            self.b = b
            # 새로 나온 포켓몬 그림으로 교체
            self.rebuild_me(b, r.get("events") or [])
        run_async(self.root,
                  lambda: self.app.api.battle_switch(self.b["id"], pid), done)

    def rebuild_me(self, b, events):
        def work():
            return sprite_cache.ensure(self.app.api, b["me"].get("num"),
                                       b["me"].get("shiny"))

        def done(path, err):
            if self.closed:
                return
            if path:
                try:
                    anim = sprites.load_animation(path, target_height=104,
                                                  min_scale=0.2, max_scale=3.0)
                    self.cv.delete(self.me.item)
                    self.me = Combatant(self.cv, b["me"], anim, 160,
                                        ARENA_H - 78, sprites.RIGHT, "me")
                except Exception:
                    pass
            self.lock(False)
            self.refresh(b)
            self.play(events, {"battle": b})
        run_async(self.root, work, done)

    # ---------------- 포획 ----------------
    def play_ball(self, r):
        """볼이 날아가 흔들리고, 잡히면 반짝인다."""
        key = (255, 0, 255)
        shake_imgs = [_to_photo(f, key) for f in effects.ball_shake_frames(30, key)]
        spark = [_to_photo(f, key) for f in effects.sparkle_frames(72, 6, key)]
        item = self.cv.create_image(120, ARENA_H - 40, image=shake_imgs[0])
        self._ball_keep = shake_imgs + spark          # 참조를 잡아둬야 안 지워진다
        tx, ty = self.foe.x, self.foe.y
        sx, sy = 120, ARENA_H - 40
        self.say("몬스터볼을 던졌다!")

        def fly(i, n=16):
            if self.closed:
                return
            if i > n:
                self.foe.hide()
                return shake(0)
            t = i / float(n)
            self.cv.coords(item, sx + (tx - sx) * t,
                           sy + (ty - sy) * t - 110 * (t - t * t) * 4)
            self.cv.itemconfigure(item, image=shake_imgs[i % len(shake_imgs)])
            self.after(24, lambda: fly(i + 1, n))

        total = max(1, r.get("shakes", 1)) * len(shake_imgs)

        def shake(i):
            if self.closed:
                return
            self.cv.coords(item, tx, ty)
            if i >= total:
                return result()
            self.cv.itemconfigure(item, image=shake_imgs[i % len(shake_imgs)])
            self.after(95, lambda: shake(i + 1))

        def result():
            if r.get("caught"):
                return sparkle(0)
            self.foe.show()
            self.cv.delete(item)
            self.say(r.get("message") or "놓쳤다!")
            self.lock(False)
            b = r.get("battle")
            if b:
                self.refresh(b)
                if b.get("over"):
                    return self.after(900, lambda: self.finish(r))
            self.after(900, lambda: self.play(r.get("events") or [], r))

        def sparkle(i):
            if self.closed:
                return
            if i >= len(spark):
                self.cv.delete(item)
                where = r.get("where")
                lines = [r.get("message") or "잡았다!"]
                if where == "box":
                    lines.append("데리고 다니는 자리가 없어 PC 박스로 보냈다.")
                self.app.request_sync()
                if self.app.box_window:
                    self.app.box_window.reload()
                return self.roll(lines, self.close)
            self.cv.itemconfigure(item, image=spark[i])
            self.after(80, lambda: sparkle(i + 1))

        fly(1)

    # ---------------- 종료 ----------------
    def ask_close(self):
        if self.b.get("over") or self.busy:
            return self.close()
        self.run_away()

    def close(self):
        if self.closed:
            return
        self.closed = True
        for j in self.jobs + ([self.anim_job] if self.anim_job else []):
            try:
                self.root.after_cancel(j)
            except Exception:
                pass
        self.jobs = []
        self.app.battle_window = None
        self.app.request_sync()
        if self.app.wild:
            self.app.wild.check()
        try:
            self.win.destroy()
        except Exception:
            pass

    def focus(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()


# 체력 막대를 다시 그릴 때 이름/레벨을 유지하려고 쓰는 작은 도우미들
def box_name(w, box):
    return w.b["foe"]["name"] if box is w.foe_box else w.b["me"]["name"]


def box_level(w, box):
    return w.b["foe"]["level"] if box is w.foe_box else w.b["me"]["level"]


def box_shiny(w, box):
    s = w.b["foe"] if box is w.foe_box else w.b["me"]
    return s.get("shiny")


def box_status(w, box):
    s = w.b["foe"] if box is w.foe_box else w.b["me"]
    return s.get("statusKr")
