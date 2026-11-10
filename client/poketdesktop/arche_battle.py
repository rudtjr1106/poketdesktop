# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 (2.4.0) — 전설 배틀 창.

관장 배틀 창(ui_gym_battle.GymBattleWindow)을 그대로 물려받는다. 판정 · 재생 · 교체 · 결과는 그 창의 것이고,
여기서 바꾸는 것은 넷이다.

  · **장면 바닥에 장소 그림** (arche_art.scene(place, ..., "inside")). 창 크기를 바꾸면 새 크기로 다시 깐다.
    관장 장면의 바닥 사각형 · 선은 걷고, 받침은 그 장소 빛깔로 칠한다. 도트 · 이름표는 그 위.
  · **입장 장면** (arche_art.entry_frames) 을 창 전체를 덮고 튼다 - 누르면 건너뛴다. 걷히면 전설이 **볼 없이**
    그 자리에 나타나고, 화면이 흔들리며 "<이름>의 울음소리가 <장소>을(를) 울렸다!" (앱에 소리가 없다).
  · 명령 칸 오른쪽에 **'볼 던지기'** - 볼 메뉴(ball_menu, 마스터볼은 맨 아래 따로) → api.arche_ball.
    놓치면 볼이 흔들리다 열리고 서버가 보낸 전설의 턴을 재생한다. 잡으면 결과 칸, 남은 자리가 있으면 '더 안쪽으로'.
  · 기권은 '도망치기' (그 판만 끝 - 이벤트가 끝날 때까지 다시 도전할 수 있다).

일지 창과 **같은 자리 · 크기**로 띄워 한 창처럼 보이게 한다 (geometry "WxH+X+Y").

    ArcheBattleWindow(app, data, place, geometry=None, on_close=None, on_next=None)

  data      /api/arche/battle 의 답 (관장 판 꼴 + place · legend · ballOptions? · next?)
  on_next   '더 안쪽으로' 를 누르면 on_next(next, geometry) - next = {chapter, slot}, geometry = 지금 창 자리.
            **그때는 on_close 를 부르지 않는다** (흐름이 다음 창으로 이어진다 - 일지로 돌아가는 것이 아니다).
"""
import datetime
import math
import re
import tkinter as tk

from PIL import ImageTk

from common.korean import natural

from . import arche_art
from . import ball_menu
from . import battle_zoom as Z
from . import effects, sprites
from .ui_common import run_async
from .ui_gym_battle import STEP_MS, GymBattleWindow

U = Z.U

# 장 이름 · 장소 이름. common/arche.CHAPTERS 가 있으면 그것을 쓴다 (서버가 data 에 실어 주면 그것이 먼저).
_NAMES = {"cave": ("돌의 문", "동굴"), "volcano": ("불의 산", "화산"), "abyss": ("가라앉은 신전", "심해"),
          "sky": ("하늘의 탑", "구름 위"), "castle": ("두 영웅의 성", "모래 속 고성"), "throne": ("거인의 왕좌", "왕좌")}

_GEOM = re.compile(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$")

SKIP_TEXT = "누르면 건너뜁니다"
CRY_TEXT = "%s의 울음소리가 %s 을(를) 울렸다!"
CAUGHT_TEXT = "신난다! %s 을(를) 잡았다!"
MISS_TEXT = "아깝다! 조금만 더 하면 잡을 수 있었는데!"
RETRY_TEXT = "이벤트가 끝날 때까지 일지의 '전설에게 간다' 로 몇 번이든 다시 도전할 수 있다."
WHERE_TEXT = {"party": "데리고 다니는 포켓몬에 들어갔다.", "box": "박스로 보냈다."}


def parse_geometry(g):
    """"WxH+X+Y" -> (w, h, x, y). 못 읽으면 None."""
    m = _GEOM.match(str(g or "").strip())
    if not m:
        return None
    w, h, x, y = (int(v) for v in m.groups())
    return (w, h, x, y) if w > 1 and h > 1 else None


def place_names(place, data=None):
    """(장 이름, 장소 이름) - data(서버 답) · common/arche.CHAPTERS · 기본 표 차례로."""
    data = data or {}
    title, kr = data.get("title"), data.get("placeKr")
    try:
        from common import arche as CA
        for c in getattr(CA, "CHAPTERS", ()):
            if place in (c.get("key"), c.get("place")):
                title = title or c.get("kr")
                kr = kr or c.get("placeKr")
                break
    except Exception:                                       # noqa: BLE001
        pass
    fb = _NAMES.get(place, ("", ""))
    return title or fb[0], kr or fb[1]


def _shade(rgb, k):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * k))) for c in rgb[:3])


class _At(object):
    """ball_menu.popup 이 바라는 사건 (x_root · y_root) - 단추 아래에 띄운다."""

    def __init__(self, x, y):
        self.x_root, self.y_root = int(x), int(y)


class ArcheBattleWindow(GymBattleWindow):
    ZOOM_KIND = "arche"

    def __init__(self, app, data, place, geometry=None, on_close=None, on_next=None):
        self.place = place if place in arche_art.PLACES else "cave"
        self.title_kr, self.place_kr = place_names(self.place, data)
        self._requested = parse_geometry(geometry)
        self.on_next = on_next
        self.next = data.get("next") or None
        self.ball_opts = data.get("ballOptions")
        self.caught = None              # 잡은 답 (결과 칸 · 창 크기를 바꿀 때)
        self.legend_name = ""
        self._caught_ball = "POKEBALL"
        self._ball_state = None         # 볼이 장면에 있다: 'flying' (던지는 중) / 'caught' (잡았다)
        self._revealed = False
        self._arche_entry = None
        self._scene_gen = 0             # 장면을 새로 지을 때마다 +1 (돌던 연출이 옛 장면을 안 건드리게)
        self._menu = None
        self.ball_btn = self.next_btn = None
        GymBattleWindow.__init__(self, app, data, on_close=on_close)
        self.win.title("아르케 — %s" % self.title_kr)

    # ---------------- 자리 ----------------
    def zoom_open(self):
        """일지 창이 준 자리 · 크기가 있으면 그대로 (한 창처럼 보이게). 가장 작은 크기보다는 작게 안 뜬다."""
        g = self._requested
        if not g:
            return GymBattleWindow.zoom_open(self)
        w, h, x, y = g
        lo_w, lo_h = self.zoom_min()
        w, h = max(lo_w, w), max(lo_h, h)
        self.zoom_layout(w, h)
        return w, h, x, y

    def geometry(self):
        """지금 창의 자리 "WxH+X+Y" (다음 창을 같은 자리에 띄운다)."""
        try:
            self.win.update_idletasks()
            return self.win.geometry()
        except tk.TclError:
            g = self._requested
            return "%dx%d+%d+%d" % g if g else ""

    # ---------------- 장면 ----------------
    def _scene(self):
        GymBattleWindow._scene(self)
        self._scene_gen += 1
        self._backdrop()

    def _backdrop(self):
        """장소 그림을 장면 맨 아래에 깐다. 관장 장면의 바닥은 걷고 받침은 그림 빛깔로."""
        cv = self.cv
        sw, sh = max(1, self.sw), max(1, self.sh)
        im = arche_art.scene(self.place, sw, sh, "inside")
        first = self.trainer_item                   # 이것보다 먼저 그린 것이 바닥 · 받침이다
        for it in cv.find_all():
            if it >= first:
                break
            kind = cv.type(it)
            if kind in ("rectangle", "line"):
                cv.delete(it)
            elif kind == "oval":
                x1, y1, x2, y2 = cv.coords(it)
                px = im.getpixel((min(sw - 1, max(0, int((x1 + x2) / 2))), min(sh - 1, max(0, int((y1 + y2) / 2)))))
                cv.itemconfigure(it, fill=_shade(px, 0.55), outline=_shade(px, 1.25))
        ph = ImageTk.PhotoImage(im)
        self.photos["arche_bg"] = ph                # 쥐고 있어야 그림이 안 사라진다
        bg = cv.create_image(0, 0, anchor="nw", image=ph, tags=("arche_bg",))
        cv.tag_lower(bg)

    def _restore(self):
        GymBattleWindow._restore(self)
        e = self._arche_entry
        if e and not e["done"]:
            tk.Misc.tkraise(e["cover"])            # 다시 지은 칸들 위로 (Canvas.lift 는 tag_raise 다)
        if self._ball_state:
            self._sprite_show("foe", False)
        if self._ball_state == "caught":
            self._rest_ball()

    # ---------------- 입장 장면 ----------------
    def _entry_then(self, cont):
        """장소 입장 장면을 창 전체를 덮고 튼 뒤 cont (판의 첫 사건들). 누르면 건너뛴다."""
        self.busy = True
        self.hide_commands()
        w, h = self._zoom_size or (self.ww, self.scene_h + U.h(self.ZOOM_MSG) + U.h(self.ZOOM_CMD) + 4)
        cover = tk.Canvas(self.win, bg="#000000", highlightthickness=0, bd=0, cursor="hand2")
        cover.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        tk.Misc.tkraise(cover)
        cover.create_text(w - U.h(16), h - U.h(14), anchor="se", text=SKIP_TEXT, fill="#c9cfdf",
                          font=(U.FAMILY, U.pt(9)), tags=("hint",))
        cover.bind("<Button-1>", lambda _e: self._entry_finish())
        self._arche_entry = {"cont": cont, "cover": cover, "frames": None, "item": None, "photo": None,
                             "w": w, "h": h, "shown": 0, "done": False}
        place = self.place

        def done(frames, err):
            e = self._arche_entry
            if not self.alive or e is None or e["done"]:
                return
            if err or not frames:
                return self._entry_finish()
            e["frames"] = frames
            self._entry_show(0)
        run_async(self.root, lambda: arche_art.entry_frames(place, w, h), done)

    def _entry_show(self, i):
        e = self._arche_entry
        if not self.alive or e is None or e["done"]:
            return
        if i >= len(e["frames"]):
            return self._entry_finish()
        im, ms = e["frames"][i]
        cover = e["cover"]
        try:
            ph = ImageTk.PhotoImage(im)
            cw, ch = cover.winfo_width(), cover.winfo_height()
            cx, cy = (cw // 2, ch // 2) if cw > 1 and ch > 1 else (e["w"] // 2, e["h"] // 2)
            if e["item"] is None:
                e["item"] = cover.create_image(cx, cy, image=ph)
                cover.tag_raise("hint")
            else:
                cover.coords(e["item"], cx, cy)
                cover.itemconfigure(e["item"], image=ph)
        except tk.TclError:
            return self._entry_finish()
        e["photo"] = ph
        e["shown"] += 1
        self.later(max(1, int(ms or 100)), lambda: self._entry_show(i + 1))

    def _entry_finish(self):
        """덮개를 걷고 판을 시작한다 (한 번만)."""
        e = self._arche_entry
        if e is None or e["done"]:
            return
        e["done"] = True
        try:
            e["cover"].destroy()
        except tk.TclError:
            pass
        e["photo"] = e["frames"] = None
        if self.alive:
            e["cont"]()

    # ---------------- 전설 등장 ----------------
    def _apply(self, ev):
        t = ev.get("t")
        if t == "switch" and ev.get("who") == "foe" and not self._revealed:
            mon = ev.get("mon")
            if mon and not mon.get("fainted"):
                # 전설은 볼에서 나오지 않는다 - 그 자리에 있었다
                self._revealed = True
                self.legend_name = mon.get("name") or ""
                self.hiding.forget("foe")
                self.set_mon("foe", mon)
                self.say(ev.get("text"))
                self.queue.insert(0, {"t": "arche_cry", "name": self.legend_name})
                return STEP_MS
        if t == "arche_cry":
            self._quake()
            self.say(CRY_TEXT % (ev.get("name") or "전설의 포켓몬", self.place_kr))
            return STEP_MS * 2 + 400
        return GymBattleWindow._apply(self, ev)

    def _quake(self, n=12):
        """장면을 통째로 흔든다 (울음소리 대신). 장면을 새로 지으면 멈춘다 - 새 장면은 제자리에 그려진다."""
        gen = self._scene_gen
        amp = U.h(8)
        offs = [int(round((amp if i % 2 == 0 else -amp) * (n - i) / float(n))) for i in range(n)] + [0]
        at = {"x": 0}

        def step(i):
            if not self.alive or self._scene_gen != gen or i >= len(offs):
                return
            dx = offs[i] - at["x"]
            at["x"] = offs[i]
            try:
                self.cv.move("all", dx, 0)
            except tk.TclError:
                return
            self.later(40, lambda: step(i + 1))
        step(0)

    # ---------------- 명령 칸 ----------------
    def _commands(self):
        """관장 창의 명령 칸과 같은 짜임에 '볼 던지기' 한 줄을 더한다. 볼 단추가 한 줄을 더 먹으므로 **'교체 · 도망치기' 는
        창 크기와 상관없이 한 줄에 나란히** (Z.share_row 로 반씩) - 윈도우 글꼴에서 아래 기술 설명 칸이 눌렸고, 줄인 창에서는
        나중에 글자를 '도망치기' 로 바꾸며 반씩 나눈 폭이 풀려 두 단추가 눌렸다 (CI 11/11). 글자는 처음부터 '도망치기'."""
        self.cmd = tk.Frame(self.win, bg=U.BG)
        self.cmd.pack(fill="both", expand=True, padx=12, pady=(8, 10))
        right = tk.Frame(self.cmd, bg=U.BG, width=U.h(200))         # 오른쪽 칸을 먼저 담는다 (관장 창과 같은 까닭)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)
        self.left = tk.Frame(self.cmd, bg=U.BG)
        self.left.pack(side="left", fill="both", expand=True)
        self.turn_lbl = tk.Label(right, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w")
        self.turn_lbl.pack(fill="x")
        small = self.zoom < 1.0
        self.ball_btn = U.PushButton(right, "볼 던지기", self.open_ball_menu, height=34 if small else 40)
        self.ball_btn.pack(fill="x", pady=(Z.px(6), 0))
        row = tk.Frame(right, bg=U.BG)
        row.pack(fill="x", pady=(Z.px(6), 0))
        self.switch_btn = U.ghost_button(row, "포켓몬 교체", self.open_switch, height=34)
        self.switch_btn.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.forfeit_btn = U.PushButton(row, "도망치기", self.forfeit, fill=U.DANGER_BG, fg=U.DANGER,
                                        shadow="#1a1013", hover="#3a2028", height=34,
                                        border=U.DANGER_LINE, font=U.FONT_S)
        self.forfeit_btn.pack(side="left", fill="x", expand=True, padx=(3, 0))
        Z.share_row(self.switch_btn, self.forfeit_btn)
        self.hint = tk.Label(right, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS,
                             anchor="nw", justify="left")
        self.hint.pack(fill="both", expand=True, pady=(Z.px(10), 0))
        U.wrap_to_width(self.hint)

    def _clear_commands(self):
        GymBattleWindow._clear_commands(self)
        if self.ball_btn is not None:
            self.ball_btn.configure(state="disabled")

    def _paint_moves(self, moves, can_switch):
        GymBattleWindow._paint_moves(self, moves, can_switch)
        self.ball_btn.configure(state="normal")

    def _paint_switch(self, side, forced, ask):
        GymBattleWindow._paint_switch(self, side, forced, ask)
        self.ball_btn.configure(state="disabled" if forced else "normal")

    def forfeit(self):
        from .ui_box import confirm
        if confirm(self.win, "도망치기", "전설에게서 도망칠까요? " + RETRY_TEXT, danger=True, ok_text="도망치기"):
            self._send("forfeit")

    def request_close(self):
        if self.alive and not self.view.get("over"):
            from .ui_box import confirm
            if not confirm(self.win, "나가기", "승부는 그대로 남습니다. 일지에서 '전설에게 간다' 를 누르면 이어서 할 수 있어요.",
                           danger=False, ok_text="나가기"):
                return
        self.close()

    # ---------------- 볼 ----------------
    def _ball_options(self):
        """볼 메뉴의 줄. 서버가 안 보냈으면 가진 몬스터볼만."""
        if self.ball_opts is not None:
            return self.ball_opts
        return [{"id": "POKEBALL", "kr": "몬스터볼", "count": int(getattr(self.app, "balls", 0) or 0),
                 "mult": 1.0, "why": "", "best": False}]

    def _can_throw(self):
        return self.alive and not self.busy and not self.view.get("over") and not self.view.get("needSwitch")

    def open_ball_menu(self):
        if not self._can_throw():
            return None
        b = self.ball_btn.holder
        at = _At(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        self._menu = ball_menu.popup(self.root, at, self._ball_options(), self.throw, on_close=self._menu_closed)
        return self._menu

    def _menu_closed(self):
        self._menu = None

    def throw(self, ball):
        """이 볼을 던진다. 결과(잡힘 · 놓침 · 전설의 턴)는 서버가 정한다."""
        if not self._can_throw():
            return
        ball = ball or "POKEBALL"
        kr = next((o.get("kr") for o in self._ball_options() if o.get("id") == ball), None) or "몬스터볼"
        self.busy = True
        self.hide_commands()
        self.say("%s 을(를) 던졌다!" % kr)
        hour = datetime.datetime.now().hour

        def done(r, err):
            if not self.alive:
                return
            if err:
                self.busy = False
                if getattr(err, "status", None) == 410:
                    self.say(getattr(err, "message", str(err)))
                    return self.later(1500, self.close)
                # 볼이 없다 · 이미 끝난 판 ... - 판은 그대로다. 말만 보이고 고르던 칸으로
                self.show_commands()
                return self.say(getattr(err, "message", str(err)))
            r = r or {}
            self._took_ball(r, ball)
            self._play_catch(r, ball, lambda: self._after_ball(r))
        run_async(self.root, lambda: self.app.api.arche_ball(self.bid, ball, hour), done)

    def _took_ball(self, r, ball):
        """볼 개수를 맞춘다 (앱 · 메뉴)."""
        if r.get("balls") is not None:
            self.app.balls = r["balls"]
        if r.get("ballOptions") is not None:
            self.ball_opts = r["ballOptions"]
        elif self.ball_opts is not None:
            self.ball_opts = [dict(o, count=max(0, o["count"] - 1)) if o.get("id") == ball else o
                              for o in self.ball_opts]
        refresh = getattr(self.app, "refresh_tray", None)
        if refresh is not None:
            try:
                refresh()
            except Exception:                              # noqa: BLE001
                pass

    def _after_ball(self, r):
        if not self.alive:
            return
        if r.get("caught"):
            return self._caught(r)
        self.say(r.get("message") or MISS_TEXT)
        data = dict(r)
        if not data.get("battle"):
            data["battle"] = self.view
        # 서버 사건의 첫 줄({"t": "ball"})은 이 창이 방금 직접 연출했다 - 두 번 안 보이게 뺀다
        events = [e for e in (r.get("events") or []) if e.get("t") != "ball"]
        self.later(STEP_MS, lambda: self.play(events, data))

    # ---- 볼 연출 (장면 안: 날아가 → 빨려 들어가 → 떨어져 → 흔들림 → 잡힘 / 열림)
    def _ball_photo(self, ball, tilt):
        key = (255, 0, 255)
        k = "arche_ball/%s/%d/%d" % (ball, tilt, U.h(26))
        if k not in self.photos:
            self.photos[k] = ImageTk.PhotoImage(
                sprites.to_rgba(effects.ball_image(U.h(26), key, tilt=tilt, ball=ball), key))
        return self.photos[k]

    def _ball_rest_xy(self):
        fx, fy = self.foe_pos
        return fx, fy - U.h(14)

    def _rest_ball(self):
        """잡은 볼을 받침 위에 다시 놓는다 (창 크기를 바꿔 장면을 새로 지었을 때)."""
        self.cv.delete("arche_ball")
        x, y = self._ball_rest_xy()
        self.cv.create_image(x, y, image=self._ball_photo(self._caught_ball, 0), tags=("arche_ball",))

    def _play_catch(self, r, ball, done):
        cv = self.cv
        self._ball_state = "flying"
        self._caught_ball = ball
        sx, sy = U.h(36), self.sh - U.h(24)
        tx, ty = self._center("foe")
        rx, ry = self._ball_rest_xy()
        item = cv.create_image(sx, sy, image=self._ball_photo(ball, 0), tags=("arche_ball",))
        steps = []

        def fly(f):
            def go():
                x = sx + (tx - sx) * f
                y = sy + (ty - sy) * f - U.h(90) * math.sin(math.pi * f)
                cv.coords(item, x, y)
                return 30
            return go
        steps += [fly(i / 12.0) for i in range(1, 13)]

        def absorb():
            self._sprite_show("foe", False)            # 붉은 빛에 빨려 들어간다
            s = U.h(34)
            cv.create_oval(tx - s, ty - s, tx + s, ty + s, fill="#ffffff", outline="", tags=("arche_flash",))
            return 160

        def unflash():
            cv.delete("arche_flash")
            return 60

        def fall(f):
            def go():
                cv.coords(item, tx + (rx - tx) * f, ty + (ry - ty) * f)
                return 30
            return go

        def tilt(a, ms):
            def go():
                cv.itemconfigure(item, image=self._ball_photo(ball, a))
                return ms
            return go
        steps += [absorb, unflash] + [fall(i / 6.0) for i in range(1, 7)] + [lambda: 380]
        for _ in range(max(0, min(3, int(r.get("shakes") or 0)))):
            steps += [tilt(-24, 130), tilt(24, 130), tilt(0, 420)]

        def finish():
            if not self.alive:
                return
            if r.get("caught"):
                self._ball_state = "caught"
                self._sprite_show("foe", False)
                self._rest_ball()
                x, y = self._ball_rest_xy()
                for dx, dy in ((-1, -1), (0, -1.3), (1, -1)):       # 반짝
                    cv.create_text(x + dx * U.h(22), y + dy * U.h(20), text="★", fill="#ffe680",
                                   font=(U.FAMILY, U.pt(12), "bold"), tags=("arche_spark",))
                self.later(900, lambda: cv.delete("arche_spark"))
            else:
                self._ball_state = None
                cv.delete("arche_ball")
                self._sprite_show("foe", True)          # 볼이 열려 다시 나온다
                self.hiding.apply("foe")
            done()
        self._run_steps(steps, finish)

    def _run_steps(self, steps, finish):
        """steps (부르면 다음까지 기다릴 ms) 를 차례로. 장면을 새로 지었으면 남은 연출은 건너뛰고 끝만."""
        gen = self._scene_gen

        def go(i):
            if not self.alive:
                return
            if self._scene_gen != gen or i >= len(steps):
                return finish()
            try:
                ms = steps[i]()
            except tk.TclError:
                return finish()
            self.later(ms, lambda: go(i + 1))
        go(0)

    # ---------------- 잡았다 ----------------
    def _caught(self, r):
        self.caught = r
        self.next = r.get("next") or None
        foe = self.shown.get("foe") or {}
        self.legend_name = foe.get("name") or self.legend_name or (self.view.get("trainer") or {}).get("name", "")
        view = dict(r.get("battle") or self.view)
        view["over"], view["result"] = True, "caught"
        self.view = view
        self.exp.extend(r.get("exp") or [])
        self.set_mon("foe", None)                       # 볼 안에 있다
        self._rest_ball()
        self.busy = False
        self.show_result()

    def _paint_result(self):
        self.zoom_use()
        self.hide_commands()
        res = self.view.get("result")
        name = self.legend_name or (self.view.get("trainer") or {}).get("name", "")
        if res == "caught":
            title = "잡았다!"
            lines = [CAUGHT_TEXT % name]
            where = WHERE_TEXT.get((self.caught or {}).get("where"))
            if where:
                lines.append(where)
            if self.next:
                lines.append("%s 안쪽에서 또 다른 기척이 느껴진다..." % self.place_kr)
        elif res == "won":
            title = "쓰러뜨렸다"
            lines = ["%s 을(를) 쓰러뜨렸다! 잡지는 못했다." % name, RETRY_TEXT]
        elif res == "lost":
            title = "패배..."
            lines = ["데리고 다니는 포켓몬이 모두 쓰러졌다.", RETRY_TEXT]
        elif res == "forfeit":
            title = "도망쳤다"
            lines = ["무사히 도망쳤다.", RETRY_TEXT]
        else:
            title, lines = "끝", []
        ups = {}
        for e in self.exp:
            if e.get("leveledUp"):
                ups[e.get("name")] = e.get("level")
        if ups:
            lines.append("레벨 업: " + ", ".join("%s Lv.%d" % (k, v) for k, v in ups.items()))
        self._paint_result_panel("won" if res == "caught" else res, title, [natural(ln) for ln in lines])
        self.say(lines[0] if res == "caught" else title)

    def _paint_result_panel(self, res, title, lines):
        """결과 칸: 제목 · 줄 · '일지로 돌아가기' (+ 남은 자리가 있으면 '더 안쪽으로')."""
        color = {"won": U.ACCENT, "lost": U.DANGER}.get(res, U.FG)
        panel = tk.Frame(self.left, bg=U.BG2, highlightthickness=2, highlightbackground=color)
        panel.pack(fill="both", expand=True)
        inner = tk.Frame(panel, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16, pady=10)
        side = tk.Frame(inner, bg=U.BG2)
        side.pack(side="right", fill="y", padx=(12, 0))
        self.next_btn = None
        if self.view.get("result") == "caught" and self.next:
            U.ghost_button(side, "일지로 돌아가기", self.close, height=Z.base_h(32)).pack(side="bottom")
            self.next_btn = U.PushButton(side, "더 안쪽으로", self.go_deeper, height=Z.base_h(38))
            self.next_btn.pack(side="bottom", pady=(0, 8))
        else:
            U.PushButton(side, "일지로 돌아가기", self.close, height=Z.base_h(38)).pack(side="bottom")
        body = tk.Frame(inner, bg=U.BG2)
        body.pack(side="left", fill="both", expand=True)
        tk.Label(body, text=title, bg=U.BG2, fg=color, font=(U.FAMILY_BLACK, U.pt(20))).pack(anchor="w")
        for ln in lines:
            lab = tk.Label(body, text=ln, bg=U.BG2, fg=U.FG, font=U.FONT_S, anchor="w", justify="left")
            lab.pack(fill="x", pady=(2, 0))
            U.wrap_to_width(lab)

    def go_deeper(self):
        """'더 안쪽으로' - 이 창을 닫고 같은 자리에서 다음 자리의 전설로 (on_next). on_close 는 안 부른다."""
        nxt = self.next
        if not nxt or not self.alive:
            return
        geom = self.geometry()
        cb = self.on_next
        self.on_close = None
        self.close()
        if cb is not None:
            cb(dict(nxt), geom)

    # ---------------- 닫기 ----------------
    def close(self):
        if not self.alive:
            return
        e = self._arche_entry
        if e is not None and not e["done"]:
            e["done"] = True                            # 남은 장 예약이 불려도 아무것도 안 한다
            e["photo"] = e["frames"] = None
        menu, self._menu = self._menu, None
        if menu is not None and hasattr(menu, "close"):
            try:
                menu.close()
            except Exception:                              # noqa: BLE001
                pass
        GymBattleWindow.close(self)
