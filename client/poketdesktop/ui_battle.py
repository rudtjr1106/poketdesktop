# -*- coding: utf-8 -*-
"""배틀 — 바탕화면 위에서 그대로 싸운다.

별도 창을 띄우지 않는다. 화면 오른쪽 아래에 테두리 없는 투명 창을 하나 깔고
그 위에 두 포켓몬, 체력바, 기술 이펙트를 그린다. 배경이 투명해서 바탕화면이
그대로 비치고, 아무것도 안 그린 곳은 클릭도 그대로 통과한다.

명령 패널(기술 버튼)만 불투명하게 아래쪽에 붙인다.

서버가 한 턴을 돌리고 '무슨 일이 있었는지'(events)를 순서대로 준다.
여기서는 그걸 재생만 한다. 계산은 하나도 안 한다.
"""
import tkinter as tk

from PIL import Image, ImageTk

from . import battle_fx as FX
from . import effects, sprite_cache, sprites
from . import ui_common as U
from .ui_common import run_async

# 창 배경으로 쓸 투명색. 도트나 이펙트에 나올 일이 없는 색으로 고른다.
KEY = "#fe01fe"

STAGE_W, STAGE_H = 720, 470
PANEL_H = 152
ARENA_H = STAGE_H - PANEL_H
MARGIN_R, MARGIN_B = 16, 12

MSG_MS = 620
HP_MS = 20


def _to_photo(img, key):
    """투명색으로 칠해둔 도트를 알파 있는 그림으로 되돌린다."""
    px = img.tobytes()
    mb = bytearray(img.width * img.height)
    kr, kg, kb = key
    for i in range(0, len(px), 3):
        if px[i] != kr or px[i + 1] != kg or px[i + 2] != kb:
            mb[i // 3] = 255
    rgba = img.convert("RGBA")
    rgba.putalpha(Image.frombytes("L", img.size, bytes(mb)))
    return ImageTk.PhotoImage(rgba)


def work_area(root):
    from .overlay import work_area as wa
    return wa(root.winfo_screenwidth(), root.winfo_screenheight())


class Side(object):
    """배틀에 나와 있는 한 쪽."""

    def __init__(self, cv, anim, x, y, facing):
        self.cv = cv
        self.anim = anim
        self.home = (x, y)
        self.x, self.y = x, y
        self.frames = [_to_photo(f, anim.key) for f in anim.frames[facing]]
        self.i = 0
        self.item = cv.create_image(x, y, image=self.frames[0], anchor="s")
        self.hp = 0

    def step(self):
        self.i = (self.i + 1) % len(self.frames)
        self.cv.itemconfigure(self.item, image=self.frames[self.i])

    def move_to(self, x, y):
        self.x, self.y = x, y
        self.cv.coords(self.item, x, y)

    def center(self):
        return self.x, self.y - self.anim.h * 0.5

    def hide(self):
        self.cv.itemconfigure(self.item, state="hidden")

    def show(self):
        self.cv.itemconfigure(self.item, state="normal")


class BattleWindow(object):
    """이름은 창이지만 실제로는 바탕화면에 깔리는 무대다."""

    def __init__(self, root, app, battle, intro=None):
        self.root = root
        self.app = app
        self.b = battle
        self.busy = False
        self.closed = False
        self.jobs = []
        self.anim_job = None
        self.fx = None

        wl, wt, wr, wb = work_area(root)
        w = min(STAGE_W, wr - wl - 20)
        h = min(STAGE_H, wb - wt - 20)
        self.W, self.H = w, h
        self.arena_h = h - PANEL_H
        x = wr - w - MARGIN_R
        y = wb - h - MARGIN_B

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", KEY)
        self.win.configure(bg=KEY)
        self.win.geometry("%dx%d+%d+%d" % (w, h, x, y))

        self.cv = tk.Canvas(self.win, width=w, height=h, bg=KEY,
                            highlightthickness=0, bd=0)
        self.cv.pack()

        # 그림자 발판 — 바탕화면 위라도 어디에 서 있는지 보이게
        self.cv.create_oval(w - 250, 96, w - 70, 132, fill="#2c3a2c", outline="")
        self.cv.create_oval(70, self.arena_h - 44, 280, self.arena_h - 4,
                            fill="#2c3a2c", outline="")

        self.foe_box = self._hp_box(14, 12, 250)
        self.me_box = self._hp_box(w - 264, self.arena_h - 122, 250)

        self._build_panel()

        self.me = None
        self.foe = None
        self.move_btns = []
        self.load(intro)

    # ---------------- 체력바 ----------------
    def _hp_box(self, x, y, width):
        cv = self.cv
        b = {"x": x, "y": y, "w": width}
        b["bg"] = cv.create_rectangle(x, y, x + width, y + 54, fill="#12141c",
                                      outline="#39405a", width=2)
        b["name"] = cv.create_text(x + 12, y + 16, text="", anchor="w",
                                   fill="#f0f0f6", font=U.FONT_B)
        b["lv"] = cv.create_text(x + width - 12, y + 16, text="", anchor="e",
                                 fill="#9a9ab0", font=U.FONT_XS)
        b["track"] = cv.create_rectangle(x + 12, y + 28, x + width - 12, y + 38,
                                         fill="#2a2e3e", outline="")
        b["bar"] = cv.create_rectangle(x + 12, y + 28, x + width - 12, y + 38,
                                       fill=U.GOOD, outline="")
        b["hp"] = cv.create_text(x + width - 12, y + 47, text="", anchor="e",
                                 fill="#9a9ab0", font=U.FONT_XS)
        b["st"] = cv.create_text(x + 12, y + 47, text="", anchor="w",
                                 fill=U.ACCENT, font=U.FONT_XS)
        b["bw"] = width - 24
        return b

    def _paint(self, box, side, wild=False, numbers=True):
        cv = self.cv
        hp, mx = side["hp"], max(1, side["maxhp"])
        ratio = max(0.0, min(1.0, hp / float(mx)))
        col = U.GOOD if ratio > 0.5 else (U.ACCENT if ratio > 0.2 else U.DANGER)
        y0 = box["y"] + 28
        cv.coords(box["bar"], box["x"] + 12, y0,
                  box["x"] + 12 + box["bw"] * ratio, y0 + 10)
        cv.itemconfigure(box["bar"], fill=col)
        name = ("야생 " if wild else "") + side["name"]
        if side.get("shiny"):
            name = "★ " + name
        cv.itemconfigure(box["name"], text=name)
        cv.itemconfigure(box["lv"], text="Lv.%d" % side["level"])
        cv.itemconfigure(box["hp"], text=("%d / %d" % (hp, mx)) if numbers else "")
        cv.itemconfigure(box["st"], text=side.get("statusKr") or "")

    # ---------------- 명령 패널 ----------------
    def _build_panel(self):
        self.panel = tk.Frame(self.cv, bg="#12141c", highlightthickness=2,
                              highlightbackground="#39405a")
        self.cv.create_window(self.W // 2, self.arena_h + PANEL_H // 2,
                              window=self.panel, width=self.W - 8,
                              height=PANEL_H - 10)
        self.msg = tk.Label(self.panel, text="", bg="#12141c", fg="#f0f0f6",
                            font=U.FONT, anchor="w", justify="left",
                            wraplength=self.W - 40, height=2)
        self.msg.pack(fill="x", padx=12, pady=(8, 4))
        body = tk.Frame(self.panel, bg="#12141c")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.moves_frame = tk.Frame(body, bg="#12141c")
        self.moves_frame.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg="#12141c")
        right.pack(side="right", fill="y", padx=(8, 0))
        self.btn_ball = self._btn(right, "몬스터볼", U.ACCENT, "#241a04",
                                  self.throw_ball)
        self.btn_run = self._btn(right, "도망가기", "#2a2e3e", "#c8c8d6",
                                 self.run_away)
        self.balls_label = tk.Label(right, text="", bg="#12141c", fg="#9a9ab0",
                                    font=U.FONT_XS)
        self.balls_label.pack(pady=(4, 0))

    def _btn(self, parent, text, bg, fg, cmd):
        f = tk.Frame(parent, bg=bg, cursor="hand2")
        f.pack(fill="x", pady=2)
        lb = tk.Label(f, text=text, bg=bg, fg=fg, font=U.FONT_B, cursor="hand2",
                      padx=14, pady=5)
        lb.pack()
        f._cmd = cmd
        for w in (f, lb):
            w.bind("<Button-1>", lambda e: f._cmd and f._cmd())
        f._label = lb
        return f

    def build_moves(self):
        for w in self.moves_frame.winfo_children():
            w.destroy()
        self.move_btns = []
        moves = (self.b.get("me") or {}).get("moves") or []
        for i, m in enumerate(moves[:4]):
            dead = m["pp"] <= 0 and m["key"] != "STRUGGLE"
            col = "#2a2e3e" if dead else U.TYPE_COLOR.get(m.get("type"), "#4a4e60")
            fg = "#6a6a80" if dead else "#14141a"
            f = tk.Frame(self.moves_frame, bg=col, cursor="" if dead else "hand2")
            f.grid(row=i // 2, column=i % 2, sticky="nsew", padx=2, pady=2)
            n = tk.Label(f, text=m["kr"], bg=col, fg=fg, font=U.FONT_B)
            n.pack(pady=(3, 0))
            sub = "%s · %d" % (m.get("typeKr") or "", m["power"]) if m.get("power") \
                else (m.get("typeKr") or "변화")
            s = tk.Label(f, text="%s   %d/%d" % (sub, m["pp"], m["maxpp"]),
                         bg=col, fg=fg, font=U.FONT_XS)
            s.pack(pady=(0, 3))
            if not dead:
                for w in (f, n, s):
                    w.bind("<Button-1>", lambda e, k=m["key"]: self.use(k))
            self.move_btns.append(f)
        for c in (0, 1):
            self.moves_frame.grid_columnconfigure(c, weight=1)
        for r in (0, 1):
            self.moves_frame.grid_rowconfigure(r, weight=1)

    # ---------------- 준비 ----------------
    def load(self, intro):
        self.say("잠시만...")

        def work():
            return dict((w, sprite_cache.ensure(self.app.api,
                                                self.b[w].get("num"),
                                                self.b[w].get("shiny")))
                        for w in ("me", "foe"))

        def done(paths, err):
            if self.closed:
                return
            if err or not paths or not all(paths.values()):
                return self.say("도트를 불러오지 못했습니다.")
            try:
                self.build(paths, intro)
            except Exception as e:                     # noqa: BLE001
                self.say("배틀 화면을 만들지 못했습니다: %s" % e)
        run_async(self.root, work, done)

    def build(self, paths, intro):
        me_a = sprites.load_animation(paths["me"], target_height=112,
                                      min_scale=0.2, max_scale=3.0)
        foe_a = sprites.load_animation(paths["foe"], target_height=94,
                                       min_scale=0.2, max_scale=3.0)
        self.me = Side(self.cv, me_a, 175, self.arena_h - 14, sprites.RIGHT)
        self.foe = Side(self.cv, foe_a, self.W - 160, 128, sprites.LEFT)
        # 도트가 체력바 밑에 깔리지 않게 위로 올린다
        for b in (self.foe_box, self.me_box):
            for k in ("bg", "name", "lv", "track", "bar", "hp", "st"):
                self.cv.tag_raise(b[k])
        self.refresh(self.b)
        self.idle()
        self.say(intro or "무엇을 할까?")
        # 배틀 중에는 돌아다니던 포켓몬을 잠깐 치운다
        if self.app.overlay:
            self.app.overlay.set_hidden(True)
        if self.app.wild:
            self.app.wild.hide_wild_sprite()

    def idle(self):
        if self.closed:
            return
        for s in (self.me, self.foe):
            if s:
                s.step()
        self.anim_job = self.root.after(140, self.idle)

    # ---------------- 갱신 ----------------
    def refresh(self, battle):
        self.b = battle
        self._paint(self.foe_box, battle["foe"], wild=True, numbers=False)
        self._paint(self.me_box, battle["me"])
        if self.me:
            self.me.hp = battle["me"]["hp"]
        if self.foe:
            self.foe.hp = battle["foe"]["hp"]
        self.build_moves()
        self.balls_label.configure(text="볼 %d개" % self.app.balls)

    def say(self, text):
        try:
            self.msg.configure(text=text or "")
        except Exception:
            pass

    def lock(self, on):
        self.busy = on
        for b in (self.btn_ball, self.btn_run):
            b._cmd = None if on else (self.throw_ball if b is self.btn_ball
                                      else self.run_away)

    def after(self, ms, fn):
        j = self.root.after(ms, fn)
        self.jobs.append(j)
        return j

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
        run_async(self.root, lambda: self.app.api.battle_move(self.b["id"], key),
                  done)

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

    # ---------------- 재생 ----------------
    def play(self, events, result):
        q = list(events)

        def nxt():
            if self.closed:
                return
            if not q:
                return self.finish(result)
            self.render(q.pop(0), nxt)
        nxt()

    def render(self, ev, done):
        t = ev.get("t")
        if ev.get("text"):
            self.say(ev["text"])
        who = ev.get("who")

        if t == "move":
            return self.play_move(ev, done)
        if t in ("hit", "chip", "recoil", "heal"):
            side = ev.get("target") or ("me" if t in ("chip", "recoil", "heal")
                                        and who == "me" else
                                        ("foe" if who == "me" else "me"))
            s = self.me if side == "me" else self.foe
            box = self.me_box if side == "me" else self.foe_box
            if s:
                if t == "hit":
                    return self.shake(s, lambda: self.drain(
                        box, s, ev.get("hp", 0), ev.get("maxhp", 1), done))
                return self.drain(box, s, ev.get("hp", 0), ev.get("maxhp", 1), done)
        if t == "faint":
            s = self.me if who == "me" else self.foe
            if s:
                return self.faint(s, done)
        self.after(MSG_MS, done)

    def play_move(self, ev, done):
        """기술 이펙트. 종류는 기술 플래그와 타입으로 정한다."""
        who = ev.get("who")
        src = self.me if who == "me" else self.foe
        dst = self.foe if who == "me" else self.me
        if not src or not dst:
            return self.after(MSG_MS, done)
        move = self.find_move(ev, who)
        self.fx = FX.Effect(self, move, src.center(), dst.center(),
                            lambda: self.after(180, done))
        self.fx.play()

    def find_move(self, ev, who):
        """이벤트에 담긴 기술 이름으로 도감에서 상세를 찾는다."""
        name = ev.get("move")
        dex = self.app.dex
        if dex:
            for key, m in (dex.moves or {}).items():
                if m.get("kr") == name:
                    return m
        return {"type": ev.get("moveType") or "NORMAL",
                "cat": ev.get("cat") or "physical", "flags": []}

    # ---------------- 움직임 ----------------
    def lunge(self, who, done):
        """때리는 쪽이 상대 쪽으로 달려들었다 돌아온다."""
        c = self.me if who == "me" else self.foe
        if not c:
            return done()
        dx = 44 if c is self.me else -44
        dy = -30 if c is self.me else 30
        n = 6

        def go(i):
            if self.closed:
                return
            if i > n * 2:
                c.move_to(*c.home)
                return self.after(90, done)
            k = i if i <= n else n * 2 - i
            c.move_to(c.home[0] + dx * k / float(n), c.home[1] + dy * k / float(n))
            self.after(24, lambda: go(i + 1))
        go(1)

    def shake(self, c, done):
        seq = [-8, 8, -6, 6, -3, 3, 0]

        def go(i):
            if self.closed:
                return
            if i >= len(seq):
                c.move_to(*c.home)
                return done()
            c.move_to(c.home[0] + seq[i], c.home[1])
            self.after(32, lambda: go(i + 1))
        go(0)

    def drain(self, box, c, hp, maxhp, done):
        start, wild = c.hp, (c is self.foe)
        c.hp = hp
        steps = min(22, max(6, abs(start - hp)))
        side = self.b["foe"] if wild else self.b["me"]

        def go(i):
            if self.closed:
                return
            if i > steps:
                return self.after(120, done)
            cur = int(round(start + (hp - start) * i / float(steps)))
            self._paint(box, dict(side, hp=cur, maxhp=maxhp), wild=wild,
                        numbers=not wild)
            self.after(HP_MS, lambda: go(i + 1))
        go(0)

    def faint(self, c, done):
        def go(i):
            if self.closed:
                return
            if i > 12:
                c.hide()
                return self.after(260, done)
            c.move_to(c.home[0], c.home[1] + i * 8)
            self.after(26, lambda: go(i + 1))
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
        q = list(lines)

        def nxt():
            if self.closed:
                return
            if not q:
                return self.after(800, done)
            self.say(q.pop(0))
            self.after(MSG_MS + 240, nxt)
        nxt()

    def ask_switch(self, party):
        self.say("%s 은(는) 쓰러졌다! 다음 포켓몬을 고르세요." % self.b["me"]["name"])
        for w in self.moves_frame.winfo_children():
            w.destroy()
        for i, m in enumerate(party[:4]):
            info = m.get("info", {})
            f = tk.Frame(self.moves_frame, bg="#3a3f56", cursor="hand2")
            f.grid(row=i // 2, column=i % 2, sticky="nsew", padx=2, pady=2)
            lb = tk.Label(f, text="%s  Lv.%s" % (info.get("name"), m["level"]),
                          bg="#3a3f56", fg="#f0f0f6", font=U.FONT_B,
                          cursor="hand2", pady=8)
            lb.pack()
            for w in (f, lb):
                w.bind("<Button-1>", lambda e, pid=m["id"]: self.do_switch(pid))

    def do_switch(self, pid):
        self.lock(True)

        def done(r, err):
            if err:
                self.lock(False)
                return self.say(getattr(err, "message", str(err)))
            self.swap_me(r["battle"], r.get("events") or [])
        run_async(self.root,
                  lambda: self.app.api.battle_switch(self.b["id"], pid), done)

    def swap_me(self, b, events):
        def work():
            return sprite_cache.ensure(self.app.api, b["me"].get("num"),
                                       b["me"].get("shiny"))

        def done(path, err):
            if self.closed:
                return
            if path:
                try:
                    anim = sprites.load_animation(path, target_height=112,
                                                  min_scale=0.2, max_scale=3.0)
                    self.cv.delete(self.me.item)
                    self.me = Side(self.cv, anim, 175, self.arena_h - 14,
                                   sprites.RIGHT)
                    for k in ("bg", "name", "lv", "track", "bar", "hp", "st"):
                        self.cv.tag_raise(self.me_box[k])
                except Exception:
                    pass
            self.lock(False)
            self.refresh(b)
            self.play(events, {"battle": b})
        run_async(self.root, work, done)

    # ---------------- 포획 ----------------
    def play_ball(self, r):
        key = (255, 0, 255)
        shakes = [_to_photo(f, key) for f in effects.ball_shake_frames(30, key)]
        spark = [_to_photo(f, key) for f in effects.sparkle_frames(78, 6, key)]
        self._keep = shakes + spark
        sx, sy = 150, self.arena_h - 60
        tx, ty = self.foe.center()
        item = self.cv.create_image(sx, sy, image=shakes[0])
        self.say("몬스터볼을 던졌다!")

        def fly(i, n=16):
            if self.closed:
                return
            if i > n:
                self.foe.hide()
                return shake(0)
            t = i / float(n)
            self.cv.coords(item, sx + (tx - sx) * t,
                           sy + (ty - sy) * t - 120 * (t - t * t) * 4)
            self.cv.itemconfigure(item, image=shakes[i % len(shakes)])
            self.after(24, lambda: fly(i + 1, n))

        total = max(1, r.get("shakes", 1)) * len(shakes)

        def shake(i):
            if self.closed:
                return
            self.cv.coords(item, tx, ty)
            if i >= total:
                return result()
            self.cv.itemconfigure(item, image=shakes[i % len(shakes)])
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
                lines = [r.get("message") or "잡았다!"]
                if r.get("where") == "box":
                    lines.append("데리고 다니는 자리가 없어 PC 박스로 보냈다.")
                self.app.request_sync()
                if self.app.box_window:
                    self.app.box_window.reload()
                return self.roll(lines, self.close)
            self.cv.itemconfigure(item, image=spark[i])
            self.after(80, lambda: sparkle(i + 1))

        fly(1)

    # ---------------- 종료 ----------------
    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.fx:
            self.fx.stop()
        for j in self.jobs + ([self.anim_job] if self.anim_job else []):
            try:
                self.root.after_cancel(j)
            except Exception:
                pass
        self.jobs = []
        self.app.battle_window = None
        if self.app.overlay:
            self.app.overlay.set_hidden(False)
        self.app.request_sync()
        if self.app.wild:
            self.app.wild.check()
        try:
            self.win.destroy()
        except Exception:
            pass

    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
        except Exception:
            pass
