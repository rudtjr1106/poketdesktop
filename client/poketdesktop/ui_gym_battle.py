# -*- coding: utf-8 -*-
"""관장 도전 — 배틀 창.

## 보여 주기만 한다

데미지·명중·AI·보상은 전부 서버가 정한다(server/app/gym_routes.py). 이 창은
서버가 보낸 이벤트를 **순서대로 재생**하고, 다 틀면 서버가 보낸 판 상태로
화면을 맞춘다. 재생 중에 계산한 체력은 연출용일 뿐이다 - 마지막에 서버
값으로 덮는다. 어긋날 틈을 안 만든다.

## 사람이 고르는 것

  · 기술 네 칸 (타입 색, 물리/특수/변화, 위력, PP)
  · 포켓몬 교체 (쓰러지면 교체만 고를 수 있다)
  · 기권

## 창을 닫으면

판은 서버에 남는다. 지도에서 그 지역을 다시 누르면 이어서 한다. 한 시간
손을 놓으면 서버가 접는다.
"""
import tkinter as tk

from PIL import ImageTk

from common.korean import natural

from . import battle_fx as FX
from . import effects, sprite_cache, sprites
from . import platform_os as PLAT
from . import ui_common as U
from .ui_common import run_async
from .ui_gym import level_color, shade, trainer_photo

# 설계 크기. 글꼴이 커지는 맥에서는 U.h 로 창과 장면이 **같이** 커진다.
# 장면만 키우고 창을 그대로 두면 오른쪽 이름표가 창 밖으로 잘린다.
#
# 높이는 장면 + 말풍선 + 명령 칸이다. 예전 700(맥에서 840)은 맥북 화면에서
# 독에 가려 기술 칸 아랫줄이 잘렸다. 기술 칸의 여백을 줄여 전체를 줄였고,
# 그래도 독을 뺀 화면보다 크면 장면을 줄인다(글자 칸은 그대로).
W = 860
SCENE_H = 296
MSG_H = 56
CMD_H = 212
MIN_SCENE_H = 220
STEP_MS = 650
# 포켓몬 도트 높이(px). 글자가 아니므로 글꼴 배율을 타지 않는다.
MON_H = {"me": 132, "foe": 108}
# 도트 폭 상한 (받침 폭쯤, 장면 좌표라 U.h 를 탄다). 높이만 맞추면 옆으로 긴 도트가
# 받침 밖으로 넘친다 - 스토마(98x15)는 4배로 커져 392px, 갈모매(143x24)는 572px 였다.
MON_W = {"me": 360, "foe": 290}

CAT_KR = {"physical": "물리", "special": "특수", "status": "변화"}
CAT_COLOR = {"physical": "#ff8a5b", "special": "#6fa8ff", "status": "#b7bfd6"}


# 기술 연출 배율. battle_fx 는 바탕화면 포켓몬(키 48px)에 맞춘 크기로 그린다.
# 이 창의 도트는 키가 110~130px 라 그대로 두면 연출이 손톱만 했다.
FX_SCALE = 2.0


class _ScaledCanvas(object):
    """좌표·선 굵기·글자 크기를 FX_SCALE 배로 늘려 진짜 캔버스에 그린다.

    battle_fx 를 고치지 않고 크기만 바꾸려는 것이다 (야생 배틀·투기장이 같은
    코드를 쓴다). 연출에게는 좌표를 1/배율로 줄여 넘기고, 그리는 순간 다시
    곱한다 - 그래서 날아가는 길과 크기가 함께 커지고 자리는 제자리다.
    """

    def __init__(self, cv, k):
        self._cv = cv
        self.k = k

    def _pts(self, args):
        flat = []
        for a in args:
            if isinstance(a, (list, tuple)):
                for b in a:
                    flat.extend(b if isinstance(b, (list, tuple)) else [b])
            else:
                flat.append(a)
        return [v * self.k for v in flat]

    def _kw(self, kw):
        kw = dict(kw)
        if "width" in kw:
            kw["width"] = max(1, int(round(float(kw["width"]) * self.k)))
        f = kw.get("font")
        if isinstance(f, tuple) and len(f) >= 2 and isinstance(f[1], int):
            kw["font"] = (f[0], int(round(f[1] * self.k))) + tuple(f[2:])
        return kw

    def create_line(self, *a, **kw):
        return self._cv.create_line(*self._pts(a), **self._kw(kw))

    def create_oval(self, *a, **kw):
        return self._cv.create_oval(*self._pts(a), **self._kw(kw))

    def create_polygon(self, *a, **kw):
        return self._cv.create_polygon(*self._pts(a), **self._kw(kw))

    def create_arc(self, *a, **kw):
        return self._cv.create_arc(*self._pts(a), **self._kw(kw))

    def create_rectangle(self, *a, **kw):
        return self._cv.create_rectangle(*self._pts(a), **self._kw(kw))

    def create_text(self, *a, **kw):
        return self._cv.create_text(*self._pts(a), **self._kw(kw))

    def coords(self, item, *a):
        if not a:
            return [v / self.k for v in self._cv.coords(item)]
        return self._cv.coords(item, *self._pts(a))

    def move(self, item, dx, dy):
        return self._cv.move(item, dx * self.k, dy * self.k)

    def __getattr__(self, name):
        return getattr(self._cv, name)


class _FxStage(object):
    """battle_fx.Effect 가 바라는 무대: cv, root, lunge(who, done)."""

    def __init__(self, win, k):
        self.win = win
        self.cv = _ScaledCanvas(win.cv, k)
        self.root = win.root

    def lunge(self, who, done):
        self.win.lunge(who, done)


def hp_color(frac):
    if frac > 0.5:
        return "#5fd97a"
    if frac > 0.2:
        return "#f4c542"
    return "#ff6b6b"


class GymBattleWindow(object):

    def __init__(self, app, data, on_close=None):
        self.app = app
        self.root = app.root
        self.on_close = on_close
        self.alive = True
        self.bid = data["id"]
        self.view = data["battle"]
        self.queue = []
        self.busy = False
        self.exp = []
        self.reward = None
        self.photos = {}
        self.anims = {"me": None, "foe": None}
        self.anim_jobs = {"me": None, "foe": None}
        self.jobs = []
        self.shown = {"me": None, "foe": None}      # 지금 그려 둔 포켓몬 (연출용 상태)
        self.mode = "moves"
        self.after_flow_done = False

        self.fx = None
        self.effects = []            # 돌고 있는 연출 전부 (닫을 때 모두 멈춘다)
        self._moves_by_name = None
        t = self.view["trainer"]
        self.win = tk.Toplevel(self.root)
        ww = U.h(W)
        self.scene_h = U.h(SCENE_H)
        wh = self.scene_h + U.h(MSG_H) + U.h(CMD_H) + 4
        sw_, sh_ = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        try:
            x1, y1, x2, y2 = PLAT.work_area(sw_, sh_)
        except Exception:                                  # noqa: BLE001
            x1, y1, x2, y2 = 0, 0, sw_, sh_
        room = (y2 - y1) - 44                              # 제목 막대와 약간의 여백
        if wh > room:
            cut = min(wh - room, self.scene_h - U.h(MIN_SCENE_H))
            self.scene_h -= max(0, cut)
            wh -= max(0, cut)
        # 세로만 줄이고 가로는 안 봤다. 글꼴이 큰 화면에서는 U.h(860) 이
        # 1032 까지 커져서, 1024 짜리 화면에서는 오른쪽 이름표가 밖으로 나간다.
        ww = min(ww, (x2 - x1) - U.h(16))
        self.ww = ww
        U.style_window(self.win, "관장 도전 — %s" % t.get("name", ""), ww, wh)
        # 독·작업표시줄을 뺀 자리 안에 놓는다 (style_window 는 화면 전체 기준이다)
        gx = x1 + max(0, ((x2 - x1) - ww) // 2)
        gy = y1 + max(0, ((y2 - y1) - wh - 30) // 3)
        self.win.geometry("%dx%d+%d+%d" % (ww, wh, gx, gy))
        U.apply_theme(self.win)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.request_close)
        app.gym_battle = self

        self._scene()
        self._message()
        self._commands()
        self._load_trainer()

        events = data.get("events") or []
        if events:
            # 시작 연출: 아직 아무도 안 나와 있다
            self.play(events, data)
        else:
            self.sync_view(self.view)
            # 쓰러진 채로 창을 닫았다가 다시 들어오면 교체부터 해야 한다. 기술 칸을
            # 보여 주면 누를 때마다 서버가 거절한다.
            if self.view.get("needSwitch"):
                self.open_switch(forced=True)
                self.say("승부를 이어서 합니다. 다음 포켓몬을 고르세요.")
            else:
                self.show_commands()
                self.say("승부를 이어서 합니다.")
        self.focus()

    # ---------------- 틀 ----------------
    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            PLAT.surface(self.win)
        except Exception:                                  # noqa: BLE001
            pass

    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg="#1b2334", highlightthickness=0)
        cv.pack(fill="x")
        self.cv = cv
        sw, sh = self.sw, self.sh
        cv.create_rectangle(0, int(sh * 0.56), sw, sh, fill="#222b3f", outline="")
        cv.create_line(0, int(sh * 0.56), sw, int(sh * 0.56), fill="#2c3650")
        # 받침
        self.foe_pos = (int(sw * 0.70), int(sh * 0.50))
        self.me_pos = (int(sw * 0.28), int(sh * 0.93))
        fx, fy = self.foe_pos
        mx, my = self.me_pos
        cv.create_oval(fx - s(150), fy - s(24), fx + s(150), fy + s(24), fill="#2f3a55", outline="#39466a")
        cv.create_oval(mx - s(185), my - s(30), mx + s(185), my + s(30), fill="#2f3a55", outline="#39466a")
        self.trainer_item = cv.create_image(sw - s(70), fy + s(6), anchor="s")
        self.sprite = {"foe": cv.create_image(fx, fy + s(8), anchor="s"),
                       "me": cv.create_image(mx, my + s(10), anchor="s")}
        # 이름표 둘
        # 내 이름표는 바닥에 맞춘다 (장면이 줄어도 아래가 안 잘리게)
        self.box = {"foe": self._namebox(s(18), s(14), False),
                    "me": self._namebox(sw - s(338), sh - s(104) - s(12), True)}
        self.banner = []
        self._ball_photos()

    def _namebox(self, x, y, mine):
        s = U.h
        cv = self.cv
        w, h = s(320), s(104 if mine else 86)
        items = {}
        items["bg"] = cv.create_rectangle(x, y, x + w, y + h, fill="#141a28", outline="#39415e", width=2)
        items["name"] = cv.create_text(x + s(14), y + s(18), anchor="w", fill="#f2f4fb",
                                       font=(U.FAMILY, U.pt(12), "bold"), text="")
        items["lv"] = cv.create_text(x + w - s(14), y + s(18), anchor="e", fill="#c9cfdf",
                                     font=(U.FAMILY, U.pt(10), "bold"), text="")
        items["status"] = cv.create_text(x + s(14), y + s(40), anchor="w", fill="#ffc043",
                                         font=(U.FAMILY, U.pt(8), "bold"), text="")
        items["ability"] = cv.create_text(x + w - s(14), y + s(40), anchor="e", fill="#8e97b3",
                                          font=(U.FAMILY, U.pt(8)), text="")
        bx0, by0 = x + s(14), y + s(52)
        bw = w - s(28)
        items["bar_bg"] = cv.create_rectangle(bx0, by0, bx0 + bw, by0 + s(10), fill="#2a3147", outline="")
        items["bar"] = cv.create_rectangle(bx0, by0, bx0 + bw, by0 + s(10), fill="#5fd97a", outline="")
        items["bar_geom"] = (bx0, by0, bw, s(10))
        # 체력 숫자. 상대 이름표는 낮아서 몬스터볼 줄 오른쪽 끝에 둔다.
        items["hp"] = cv.create_text(x + w - s(14), y + (s(76) if mine else h - s(14)), anchor="e",
                                     fill="#c9cfdf", font=(U.FAMILY, U.pt(9)), text="")
        items["balls"] = []
        for i in range(6):
            cx = x + s(22) + i * s(20)
            cy = y + h - s(14)
            items["balls"].append(cv.create_image(cx, cy, anchor="center"))
        return items

    def _ball_photos(self):
        """남은 포켓몬을 몬스터볼 그림으로. 쓰러진 것은 회색 볼."""
        from PIL import Image, ImageEnhance
        size = U.h(16)
        key = (255, 0, 255)
        ball = sprites.to_rgba(effects.ball_image(size, key), key)
        grey = ImageEnhance.Brightness(ball.convert("LA").convert("RGBA")).enhance(0.55)
        grey.putalpha(ball.split()[3])
        self.photos["ball"] = ImageTk.PhotoImage(ball)
        self.photos["ball_out"] = ImageTk.PhotoImage(grey)
        self.photos["ball_none"] = ImageTk.PhotoImage(Image.new("RGBA", (1, 1), (0, 0, 0, 0)))

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
        # 오른쪽 칸을 **먼저** 담는다. pack 은 먼저 담은 것부터 자리를 주므로,
        # 왼쪽(교체 칸 셋)이 넓게 달라고 하면 오른쪽 칸이 95px 로 눌렸다.
        right = tk.Frame(self.cmd, bg=U.BG, width=U.h(200))
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)
        self.left = tk.Frame(self.cmd, bg=U.BG)
        self.left.pack(side="left", fill="both", expand=True)
        self.turn_lbl = tk.Label(right, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w")
        self.turn_lbl.pack(fill="x")
        self.switch_btn = U.ghost_button(right, "포켓몬 교체", self.open_switch, height=40)
        self.switch_btn.pack(fill="x", pady=(8, 0))
        self.forfeit_btn = U.PushButton(right, "기권", self.forfeit, fill=U.DANGER_BG, fg=U.DANGER,
                                        shadow="#1a1013", hover="#3a2028", height=36,
                                        border=U.DANGER_LINE, font=U.FONT_S)
        self.forfeit_btn.pack(fill="x", pady=(10, 0))
        self.hint = tk.Label(right, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS,
                             anchor="nw", justify="left")
        self.hint.pack(fill="both", expand=True, pady=(12, 0))
        U.wrap_to_width(self.hint)

    def say(self, text):
        try:
            self.msg.configure(text=natural(text or ""))
        except tk.TclError:
            pass

    def later(self, ms, fn):
        if not self.alive:
            return
        j = self.root.after(ms, lambda: self.alive and fn())
        self.jobs.append(j)
        return j

    # ---------------- 그림 ----------------
    def _load_trainer(self):
        key = self.view["trainer"].get("battleSprite") or self.view["trainer"].get("sprite")

        def done(img, err):
            if not self.alive or err or img is None:
                return
            ph = ImageTk.PhotoImage(img)
            self.photos["trainer"] = ph
            self.cv.itemconfigure(self.trainer_item, image=ph)
        run_async(self.root, lambda: trainer_photo(self.app.api, key), done)

    def set_mon(self, who, mon):
        """그 쪽에 이 포켓몬을 세운다. 도트는 뒤에서 받아 온다."""
        self.shown[who] = dict(mon) if mon else None
        self._paint_box(who)
        self._stop_anim(who)
        self.cv.itemconfigure(self.sprite[who], image="")
        if not mon or mon.get("fainted"):
            return
        num, shiny = mon.get("num"), mon.get("shiny")
        size = MON_H[who]

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
            # 쇼다운 도트는 왼쪽을 본다. 내 쪽은 뒤집어 상대를 보게 한다.
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
            except Exception:                              # noqa: BLE001
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
        self.anim_jobs[who] = self.root.after(max(40, int(d or 100)), lambda: self._tick(who, i + 1))

    def _paint_box(self, who, hp=None):
        items = self.box[who]
        mon = self.shown.get(who)
        cv = self.cv
        if not mon:
            for k in ("name", "lv", "status", "ability"):
                cv.itemconfigure(items[k], text="")
            return
        gender = {"M": " ♂", "F": " ♀"}.get(mon.get("gender"), "")
        cv.itemconfigure(items["name"], text=(mon.get("name") or "") + gender)
        cv.itemconfigure(items["lv"], text="Lv.%d" % (mon.get("level") or 0))
        st = mon.get("statusKr") or ""
        stages = mon.get("stages") or {}
        bits = [st] if st else []
        kr = {"atk": "공", "def": "방", "spa": "특공", "spd": "특방", "spe": "스피드", "acc": "명중", "eva": "회피"}
        for k, v in stages.items():
            bits.append("%s%+d" % (kr.get(k, k), v))
        cv.itemconfigure(items["status"], text="  ".join(bits))
        cv.itemconfigure(items["ability"], text=mon.get("abilityKr") or "")
        self._bar(who, mon.get("hp") if hp is None else hp, mon.get("maxhp") or 1)

    def _bar(self, who, hp, maxhp):
        items = self.box[who]
        x0, y0, bw, bh = items["bar_geom"]
        frac = max(0.0, min(1.0, float(hp) / float(maxhp or 1)))
        self.cv.coords(items["bar"], x0, y0, x0 + max(0, int(bw * frac)), y0 + bh)
        self.cv.itemconfigure(items["bar"], fill=hp_color(frac))
        if items.get("hp"):
            self.cv.itemconfigure(items["hp"], text="%d / %d" % (max(0, hp), maxhp))

    def _animate_bar(self, who, to_hp, done=None):
        mon = self.shown.get(who)
        if not mon:
            return done and done()
        start = mon.get("hp", 0)
        maxhp = mon.get("maxhp") or 1
        steps = 10

        def step(k):
            if not self.alive:
                return
            v = start + (to_hp - start) * k / float(steps)
            self._bar(who, int(round(v)), maxhp)
            if k < steps:
                self.later(28, lambda: step(k + 1))
            else:
                mon["hp"] = to_hp
                if done:
                    done()
        step(1)

    def _balls(self, view):
        for who in ("me", "foe"):
            team = view[who]["team"]
            for i, item in enumerate(self.box[who]["balls"]):
                if i >= len(team):
                    ph = self.photos["ball_none"]
                elif team[i].get("fainted"):
                    ph = self.photos["ball_out"]
                else:
                    ph = self.photos["ball"]      # 아직 안 나온 상대도 볼로 보인다 (본가와 같다)
                self.cv.itemconfigure(item, image=ph)

    # ---------------- 기술 연출 ----------------
    # 야생 배틀·투기장과 같은 battle_fx 를 쓴다. 기술의 타입과 갈래(접촉·광선·
    # 포물선·음파·가루·자기 강화 ...)로 캔버스에 그린다. 크기는 _FxStage 가 키운다.
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

        try:
            k = FX_SCALE
            (sx, sy), (tx, ty) = self._center(who), self._center(other)
            self.fx = FX.Effect(_FxStage(self, k), self._find_move(ev), (sx / k, sy / k), (tx / k, ty / k),
                                done, who=who)
            # 안전 타이머가 먼저 다음으로 넘기면 self.fx 는 비지만 연출은 아직 돈다.
            # 참조를 따로 들고 있어야 창을 닫을 때 멈출 수 있다 (안 멈추면 없어진
            # 캔버스를 지우려다 TclError 가 난다).
            self.effects = [e for e in self.effects if not e.dead] + [self.fx]
            # 연출이 어디서 멈춰도 판은 흘러가야 한다
            self.later(2600, done)
            self.fx.play()
        except Exception:                                  # noqa: BLE001
            done()
        return None

    def _find_move(self, ev):
        if self._moves_by_name is None:
            moves = getattr(getattr(self.app, "dex", None), "moves", None) or {}
            self._moves_by_name = {m.get("kr"): m for m in moves.values() if m.get("kr")}
        return self._moves_by_name.get(ev.get("move")) or {
            "type": ev.get("moveType") or "NORMAL", "cat": ev.get("cat") or "physical", "flags": []}

    def _center(self, who):
        bb = self.cv.bbox(self.sprite[who])
        if bb:
            return ((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)
        x, y = self.foe_pos if who == "foe" else self.me_pos
        return (x, y - MON_H[who] / 2.0)

    def lunge(self, who, done):
        """battle_fx 가 접촉기에서 부른다."""
        self._lunge(who)
        self.later(190, done)

    def _shake(self, who, n=6):
        item = self.sprite[who]
        offs = [6, -6, 5, -5, 3, -3, 0][:n] + [0]

        def step(i, prev=0):
            if not self.alive or i >= len(offs):
                return
            dx = offs[i] - prev
            self.cv.move(item, dx, 0)
            self.later(35, lambda: step(i + 1, offs[i]))
        step(0)

    def _lunge(self, who):
        item = self.sprite[who]
        d = U.h(18) if who == "me" else -U.h(18)
        seq = [d / 3.0] * 3 + [-d / 3.0] * 3

        def step(i):
            if not self.alive or i >= len(seq):
                return
            self.cv.move(item, seq[i], -seq[i] * 0.4 if who == "me" else seq[i] * 0.4)
            self.later(26, lambda: step(i + 1))
        step(0)

    def _faint(self, who):
        item = self.sprite[who]

        def step(i):
            if not self.alive:
                return
            if i >= 8:
                self._stop_anim(who)
                self.cv.itemconfigure(item, image="")
                self.cv.move(item, 0, -U.h(4) * 8)
                return
            self.cv.move(item, 0, U.h(4))
            self.later(30, lambda: step(i + 1))
        step(0)

    def _show_banner(self, who, text):
        s = U.h
        cv = self.cv
        y = s(118) if who == "foe" else int(self.sh * 0.52)
        x = s(24) if who == "foe" else self.sw - s(360)
        r = cv.create_rectangle(x, y, x + s(330), y + s(30), fill="#2a1f08", outline="#ffc043", width=2)
        t = cv.create_text(x + s(14), y + s(15), anchor="w", text=text, fill="#ffe6b8",
                           font=(U.FAMILY, U.pt(10), "bold"))
        self.banner += [r, t]

        def gone():
            for it in (r, t):
                try:
                    cv.delete(it)
                except tk.TclError:
                    pass
        self.later(1400, gone)

    # ---------------- 재생 ----------------
    def play(self, events, data):
        self.busy = True
        self.hide_commands()
        self.queue = list(events)
        self._pending_data = data
        self._next()

    def _next(self):
        if not self.alive:
            return
        if not self.queue:
            return self._finish_play()
        ev = self.queue.pop(0)
        wait = self._apply(ev)
        if wait is not None:              # None 이면 연출이 끝날 때 스스로 다음으로 넘긴다
            self.later(wait, self._next)

    def _apply(self, ev):
        t = ev.get("t")
        who = ev.get("who")
        text = ev.get("text")
        if t == "intro":
            self.say(text)
            return STEP_MS + 250
        if t == "switch":
            self.set_mon(who, ev.get("mon"))
            self.say(text)
            return STEP_MS
        if t == "recall":
            self._stop_anim(who)
            self.cv.itemconfigure(self.sprite[who], image="")
            self.say(text)
            return 420
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
                    self._paint_box(who)
                self._show_banner(who, text.strip("[]"))
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
                st[ev.get("stat")] = max(-6, min(6, st.get(ev.get("stat"), 0) + int(ev.get("change") or 0)))
                mon["stages"] = dict((k, v) for k, v in st.items() if v)
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
            return STEP_MS
        if text:
            self.say(text)
            return STEP_MS
        return 60

    def _finish_play(self):
        data = self._pending_data or {}
        self._pending_data = None
        self.view = data.get("battle") or self.view
        self.exp.extend(data.get("exp") or [])
        if data.get("reward"):
            self.reward = data["reward"]
        self.busy = False
        self.sync_view(self.view)
        if self.view.get("over"):
            return self.show_result()
        if self.view.get("needSwitch"):
            return self.open_switch(forced=True)
        self.show_commands()

    def sync_view(self, view):
        """서버 값으로 화면을 맞춘다. 재생 중 연출로 바뀐 체력도 여기서 덮인다."""
        for who in ("me", "foe"):
            side = view[who]
            mon = side["team"][side["slot"]]
            cur = self.shown.get(who)
            if not cur or cur.get("num") != mon.get("num") or cur.get("fainted") != mon.get("fainted"):
                self.set_mon(who, mon)
            else:
                self.shown[who] = dict(mon)
                self._paint_box(who)
        self._balls(view)
        self.turn_lbl.configure(text="%d턴 · %s" % (view.get("turn", 0), view["trainer"].get("name", "")))

    # ---------------- 명령 ----------------
    def hide_commands(self):
        for w in self.left.winfo_children():
            w.destroy()
        for b in (self.switch_btn, self.forfeit_btn):
            b.configure(state="disabled")

    def show_commands(self):
        self.mode = "moves"
        for w in self.left.winfo_children():
            w.destroy()
        side = self.view["me"]
        mon = side["team"][side["slot"]]
        grid = tk.Frame(self.left, bg=U.BG)
        grid.pack(fill="both", expand=True)
        moves = mon.get("moves") or []
        for i, m in enumerate(moves[:4] if len(moves) <= 4 else moves[-1:]):
            self._move_cell(grid, i, m)
        for c in (0, 1):
            grid.grid_columnconfigure(c, weight=1, uniform="mv")
        for r in (0, 1):
            grid.grid_rowconfigure(r, weight=1, uniform="mvr")
        can_switch = any(not x.get("fainted") for i, x in enumerate(side["team"]) if i != side["slot"])
        self.switch_btn.configure(state="normal" if can_switch else "disabled")
        self.forfeit_btn.configure(state="normal")
        self.hint.configure(text="기술에 마우스를 올리면 설명이 나옵니다.")
        self.say("%s 은(는) 무엇을 할까?" % mon.get("name", ""))

    def _move_cell(self, grid, i, m):
        col = U.TYPE_COLOR.get(m.get("type"), U.BG3)
        usable = (m.get("pp") or 0) > 0
        bg = shade(col, 0.42) if usable else "#23283a"
        cell = tk.Frame(grid, bg=bg, highlightthickness=2, highlightbackground=col if usable else U.LINE,
                        cursor="hand2" if usable else "")
        cell.grid(row=i // 2, column=i % 2, sticky="nsew", padx=3, pady=3)
        # 칸이 창 높이만큼 늘어나므로 내용은 세로 가운데에 둔다 (위에 붙이면 아래가 텅 빈다)
        body = tk.Frame(cell, bg=bg)
        body.pack(fill="x", expand=True)
        top = tk.Frame(body, bg=bg)
        top.pack(fill="x", padx=12, pady=(6, 0))
        name = tk.Label(top, text=m.get("kr") or m.get("key"), bg=bg, fg="#ffffff" if usable else U.FG_FAINT,
                        font=(U.FAMILY, U.pt(13), "bold"), anchor="w")
        name.pack(side="left")
        tchip = tk.Label(top, text=m.get("typeKr") or "", bg=col, fg="#10131b", font=U.FONT_XS, padx=6)
        tchip.pack(side="right")
        bottom = tk.Frame(body, bg=bg)
        bottom.pack(fill="x", padx=12, pady=(2, 6))
        cat = m.get("cat") or "status"
        cl = tk.Label(bottom, text=CAT_KR.get(cat, cat), bg=bg, fg=CAT_COLOR.get(cat, U.FG_DIM),
                      font=(U.FAMILY, U.pt(9), "bold"))
        cl.pack(side="left")
        extra = []
        if m.get("power"):
            extra.append("위력 %d" % m["power"])
        extra.append(("명중 %d" % m["acc"]) if m.get("acc") else "명중 —")
        el = tk.Label(bottom, text="  ·  ".join(extra), bg=bg, fg="#d7dcea" if usable else U.FG_FAINT,
                      font=U.FONT_XS)
        el.pack(side="left", padx=(8, 0))
        pp = tk.Label(bottom, text="PP %d/%d" % (m.get("pp") or 0, m.get("maxpp") or 0), bg=bg,
                      fg="#ffffff" if usable else U.DANGER, font=(U.FAMILY, U.pt(9), "bold"))
        pp.pack(side="right")
        parts = (cell, body, top, name, tchip, bottom, cl, el, pp)
        for w in parts:
            w.bind("<Enter>", lambda _e, mm=m: self.hint.configure(text=mm.get("desc") or ""))
            if usable:
                w.bind("<Button-1>", lambda _e, k=m.get("key"): self.use_move(k))

    def open_switch(self, forced=False):
        # 쓰러져서 바꿔야 하는 순간에는 어디서 열어도 '돌아가기' 가 없어야 한다
        forced = forced or bool(self.view.get("needSwitch"))
        self.mode = "switch"
        for w in self.left.winfo_children():
            w.destroy()
        side = self.view["me"]
        head = tk.Frame(self.left, bg=U.BG)
        head.pack(fill="x")
        tk.Label(head, text="누구로 바꿀까?" if not forced else "다음 포켓몬을 고르세요",
                 bg=U.BG, fg=U.FG, font=U.FONT_B).pack(side="left")
        if not forced:
            U.ghost_button(head, "돌아가기", self.show_commands, height=28).pack(side="right")
        grid = tk.Frame(self.left, bg=U.BG)
        grid.pack(fill="both", expand=True, pady=(4, 0))
        for i, m in enumerate(side["team"]):
            self._party_cell(grid, i, m, i == side["slot"])
        for c in (0, 1, 2):
            grid.grid_columnconfigure(c, weight=1, uniform="pt")
        self.switch_btn.configure(state="disabled")
        self.forfeit_btn.configure(state="normal")
        self.hint.configure(text="쓰러진 포켓몬과 지금 나와 있는 포켓몬은 고를 수 없습니다.")
        if forced:
            self.say("다음 포켓몬을 고르세요.")

    def _party_cell(self, grid, i, m, active):
        ok = not m.get("fainted") and not active
        bg = U.BG2 if ok else "#171b27"
        cell = tk.Frame(grid, bg=bg, highlightthickness=2,
                        highlightbackground=U.ACCENT if active else U.LINE, cursor="hand2" if ok else "")
        cell.grid(row=i // 3, column=i % 3, sticky="nsew", padx=3, pady=3)
        row = tk.Frame(cell, bg=bg)
        row.pack(fill="x", padx=8, pady=(5, 1))
        # 빈 Label 의 width/height 는 글자 수라서 그림이 오기 전엔 칸이 거대해진다.
        # 크기를 픽셀로 고정한 틀 안에 둔다.
        slot = tk.Frame(row, bg=bg, width=36, height=36)
        slot.pack(side="left")
        slot.pack_propagate(False)
        thumb = tk.Label(slot, bg=bg, bd=0)
        thumb.pack(expand=True)
        txt = tk.Frame(row, bg=bg)
        txt.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tk.Label(txt, text=m.get("name") or "", bg=bg, fg=U.FG if ok else U.FG_FAINT, font=U.FONT_B,
                 anchor="w").pack(anchor="w")
        sub = "Lv.%d" % (m.get("level") or 0)
        if m.get("fainted"):
            sub += "  · 쓰러짐"
        elif active:
            sub += "  · 싸우는 중"
        elif m.get("statusKr"):
            sub += "  · %s" % m["statusKr"]
        tk.Label(txt, text=sub, bg=bg, fg=U.FG_DIM, font=U.FONT_XS, anchor="w").pack(anchor="w")
        bar = tk.Canvas(cell, height=U.h(8), bg="#2a3147", highlightthickness=0)
        bar.pack(fill="x", padx=10, pady=(2, 6))
        frac = (m.get("hp") or 0) / float(m.get("maxhp") or 1)

        def draw(_e=None, c=bar, f=frac):
            c.delete("all")
            c.create_rectangle(0, 0, int(c.winfo_width() * f), c.winfo_height(), fill=hp_color(f), outline="")
        bar.bind("<Configure>", draw)
        self._party_thumb(thumb, m)
        if ok:
            for w in (cell, row, slot, thumb, txt) + tuple(txt.winfo_children()):
                w.bind("<Button-1>", lambda _e, s=i: self.do_switch(s))

    def _party_thumb(self, label, m):
        key = "p%s" % m.get("num")
        if key in self.photos:
            return label.configure(image=self.photos[key])

        def work():
            path = sprite_cache.ensure(self.app.api, m.get("num"), m.get("shiny"))
            if not path:
                return None
            anim = sprites.load_animation(path, 32, 0.2, 2.0, max_frames=1)
            return sprites.to_rgba(anim.frames[sprites.LEFT][0], anim.key)

        def done(img, err):
            if not self.alive or err or img is None:
                return
            ph = ImageTk.PhotoImage(img)
            self.photos[key] = ph
            try:
                label.configure(image=ph)
            except tk.TclError:
                pass
        run_async(self.root, work, done)

    # ---------------- 보내기 ----------------
    def _send(self, kind, move="", slot=-1):
        if self.busy:
            return
        self.busy = True
        self.hide_commands()
        self.say("...")

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.busy = False
                code = getattr(err, "status", None)
                if code == 410:
                    self.say(getattr(err, "message", str(err)))
                    return self.later(1500, self.close)
                self.say(getattr(err, "message", str(err)))
                return self._reload()
            self.play(r.get("events") or [], r)

        run_async(self.root, lambda: self.app.api.gym_act(self.bid, kind, move, slot), done)

    def _reload(self):
        def done(r, err):
            if not self.alive:
                return
            if err:
                return self.later(1500, self.close)
            self.view = r["battle"]
            self.sync_view(self.view)
            if self.view.get("needSwitch"):
                self.open_switch(forced=True)
            else:
                self.show_commands()
        run_async(self.root, lambda: self.app.api.gym_battle(), done)

    def use_move(self, key):
        self._send("move", move=key)

    def do_switch(self, slot):
        self._send("switch", slot=slot)

    def forfeit(self):
        from .ui_box import confirm
        if confirm(self.win, "기권", "이 승부를 포기할까요? 상금은 없습니다.", danger=True, ok_text="기권"):
            self._send("forfeit")

    # ---------------- 끝 ----------------
    def show_result(self):
        # **결과가 뜨는 순간 진화 연출을 시작한다.** 전에는 창을 닫아야
        # 시작해서, 결과를 보는 동안에는 아무 일도 없어 진화 연출이 안 뜨는
        # 것처럼 보였다. 기술 배우기 창은 앱이 이 창이 닫힐 때까지 기다린다.
        self.root.after(600, self._after_flow)
        self.hide_commands()
        res = self.view.get("result")
        title = {"won": "승리!", "lost": "패배...", "draw": "무승부", "forfeit": "기권"}.get(res, "끝")
        color = {"won": U.ACCENT, "lost": U.DANGER}.get(res, U.FG)
        panel = tk.Frame(self.left, bg=U.BG2, highlightthickness=2, highlightbackground=color)
        panel.pack(fill="both", expand=True)
        inner = tk.Frame(panel, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16, pady=10)
        # 단추는 오른쪽 아래에 **먼저** 붙인다. 줄 아래에 두면 창 높이를 그만큼 더 먹는다.
        side = tk.Frame(inner, bg=U.BG2)
        side.pack(side="right", fill="y", padx=(12, 0))
        U.PushButton(side, "지도로 돌아가기", self.close, height=U.h(38)).pack(side="bottom")
        body = tk.Frame(inner, bg=U.BG2)
        body.pack(side="left", fill="both", expand=True)
        tk.Label(body, text=title, bg=U.BG2, fg=color, font=(U.FAMILY_BLACK, U.pt(20))).pack(anchor="w")
        t = self.view["trainer"]
        lines = []
        if res == "won":
            lines.append("%s %s 을(를) 이겼다!" % (t.get("role", ""), t.get("name", "")))
            rw = self.reward or {}
            if rw.get("first"):
                lines.append("처음 이긴 곳이다! 상금 %s원" % format(rw.get("prize", 0), ","))
            elif rw.get("prize"):
                lines.append("상금 %s원 (다시 이긴 상금은 하루 한 번)" % format(rw.get("prize", 0), ","))
            else:
                lines.append("오늘은 이미 이 곳의 상금을 받았다.")
            if rw.get("cleared") is not None:
                lines.append("이긴 곳 %d / %d" % (rw["cleared"], rw.get("total", 256)))
        elif res == "lost":
            lines.append("데리고 다니는 포켓몬이 모두 쓰러졌다. 다시 도전해 보자.")
        ups = {}
        for e in self.exp:
            if e.get("leveledUp"):
                ups[e.get("name")] = e.get("level")
        if ups:
            lines.append("레벨 업: " + ", ".join("%s Lv.%d" % (k, v) for k, v in ups.items()))
        for ln in lines:
            lab = tk.Label(body, text=natural(ln), bg=U.BG2, fg=U.FG, font=U.FONT_S, anchor="w", justify="left")
            lab.pack(fill="x", pady=(2, 0))
            U.wrap_to_width(lab)
        self.say(title)

    def request_close(self):
        if self.alive and not self.view.get("over"):
            from .ui_box import confirm
            if not confirm(self.win, "나가기", "승부는 그대로 남습니다. 지도에서 그 지역을 누르면 이어서 할 수 있어요.",
                           danger=False, ok_text="나가기"):
                return
        self.close()

    def _after_flow(self):
        """레벨업으로 생긴 '기술 배우기' 와 진화를 앱에 넘긴다 (한 번만)."""
        if self.after_flow_done:
            return
        self.after_flow_done = True
        for e in self.exp:
            if e.get("pendingIds"):
                try:
                    self.app.want_learn(e.get("id"), e.get("name"))
                except Exception:                          # noqa: BLE001
                    pass
        evolves = [dict(e["evolve"], pokemonId=e.get("id")) for e in self.exp if e.get("evolve")]
        if evolves:
            show = getattr(self.app, "show_evolutions", None)
            if show is not None:
                self.root.after(400, lambda: show(evolves))
            else:
                from .desktop_battle import play_evolutions
                self.root.after(400, lambda: play_evolutions(self.app, evolves))
        elif self.exp:
            try:
                self.app.request_sync()
            except Exception:                              # noqa: BLE001
                pass

    def close(self):
        if not self.alive:
            return
        self.alive = False
        for e in self.effects + ([self.fx] if self.fx is not None else []):
            try:
                e.stop()
            except Exception:                              # noqa: BLE001
                pass
        self.effects = []
        self.fx = None
        for who in ("me", "foe"):
            self._stop_anim(who)
        for j in self.jobs:
            try:
                self.root.after_cancel(j)
            except Exception:                              # noqa: BLE001
                pass
        self.jobs = []
        try:
            self.win.destroy()
        except Exception:                                  # noqa: BLE001
            pass
        if getattr(self.app, "gym_battle", None) is self:
            self.app.gym_battle = None
        self._after_flow()
        if self.on_close:
            try:
                self.on_close()
            except Exception:                              # noqa: BLE001
                pass
