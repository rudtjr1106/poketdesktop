# -*- coding: utf-8 -*-
"""바탕화면 위를 돌아다니는 포켓몬.

포켓몬 한 마리가 창(Toplevel) 하나다. 테두리 없는 항상 위 창에
투명색을 지정해서 도트만 남긴다.

그림은 정식 도트(움직이는 GIF)라서 제자리 애니메이션이 이미 들어 있다.
걸을 때는 진행 방향에 맞춰 좌우만 뒤집는다.

활동 범위는 작업표시줄을 뺀 작업 영역의 오른쪽 아래 구석으로 제한한다.
"""
import random
import tkinter as tk

from PIL import ImageTk

from . import config
from . import sprites
from .sprites import DOWN, LEFT, RIGHT, UP
from . import ui_common as U


def work_area(fallback_w, fallback_h):
    """작업표시줄을 뺀 화면 영역."""
    try:
        import ctypes

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        r = RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    return 0, 0, fallback_w, fallback_h


class Pet(object):
    """포켓몬 한 마리."""

    def __init__(self, overlay, mon, anim):
        self.ov = overlay
        self.mon = mon
        self.id = mon.get("id")
        self.anim = anim
        self.fw, self.fh = anim.w, anim.h
        key = anim.key                    # 투명색은 그림마다 다르다
        hexkey = "#%02x%02x%02x" % key

        # 걷는 도트면 방향이 4개, 배틀 도트면 좌우 2개다.
        self.walking_sprite = isinstance(anim, sprites.WalkAnimation)
        self.photos = dict(
            (d, [ImageTk.PhotoImage(f) for f in frames])
            for d, frames in anim.frames.items())

        self.win = tk.Toplevel(overlay.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", hexkey)
        self.win.configure(bg=hexkey)
        self.label = tk.Label(self.win, bd=0, highlightthickness=0, bg=hexkey)
        self.label.pack()

        x1, y1, x2, y2 = overlay.area()
        m = overlay.settings["areaMargin"]
        self.x = random.randint(x1 + m, max(x1 + m, x2 - self.fw - m))
        self.y = random.randint(y1 + m, max(y1 + m, y2 - self.fh - m))
        self.facing = random.choice(list(self.photos.keys()))
        self.frame = random.randrange(anim.count())
        self.elapsed = 0
        self.state = "idle"
        self.timer = random.randint(20, 80)
        self.vx = self.vy = 0.0
        self.battling = False        # 배틀 중에는 스스로 돌아다니지 않는다

        self.label.bind("<Enter>", self.on_enter)
        self.label.bind("<Leave>", self.on_leave)
        # 끌어서 옮기는 기능은 뺐다. 쓰다 보면 쓰다듬으려다 실수로 끌려가서
        # 오히려 불편했다. 누르고 떼는 것만 남긴다 —
        # 야생 포켓몬을 왼쪽 클릭해 배틀을 걸 때 이게 필요하다.
        self.label.bind("<Button-1>", self.on_press)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        self.label.bind("<Button-3>", self.on_menu)
        self.label.bind("<Double-Button-1>", self.on_double)

        self.name_win = None
        self.tip_win = None
        self.tip_job = None
        if overlay.settings.get("showNames"):
            self.make_nameplate()

        self.redraw()
        self.place()

    # ---------------- 이름표 ----------------
    def make_nameplate(self):
        info = self.mon.get("info", {})
        text = "%s Lv.%s" % (info.get("name", "?"), info.get("level", "?"))
        if self.mon.get("shiny"):
            text = "★ " + text
        w = tk.Toplevel(self.ov.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-alpha", 0.88)
        w.configure(bg=U.TIP_BG)
        tk.Label(w, text=text, bg=U.TIP_BG,
                 fg=U.TIP_SHINY if self.mon.get("shiny") else U.TIP_FG,
                 font=U.FONT_TIP).pack(padx=5, pady=1)
        self.name_win = w

    # ---------------- 마우스를 올리면 이름 ----------------
    def tip_text(self):
        info = self.mon.get("info", {})
        name = info.get("name") or "?"
        species = info.get("species") or ""
        line = "%s   Lv.%s" % (name, info.get("level", "?"))
        if species and species != name:
            line += "   (%s)" % species
        types = " / ".join(info.get("types", []))
        if types:
            line += "\n" + types
        if self.mon.get("shiny"):
            line = "★ 색이 다른 개체\n" + line
        return line

    def on_enter(self, _e=None):
        self.cancel_tip()
        self.tip_job = self.ov.root.after(280, self.show_tip)

    def on_leave(self, _e=None):
        self.cancel_tip()
        self.hide_tip()

    def cancel_tip(self):
        if self.tip_job:
            try:
                self.ov.root.after_cancel(self.tip_job)
            except Exception:
                pass
            self.tip_job = None

    def show_tip(self):
        self.tip_job = None
        self.hide_tip()
        try:
            w = tk.Toplevel(self.ov.root)
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            w.configure(bg=U.TIP_BG)
            tk.Label(w, text=self.tip_text(), bg=U.TIP_BG,
                     fg=U.TIP_SHINY if self.mon.get("shiny") else U.TIP_FG,
                     font=U.FONT_TIP, justify="center",
                     padx=9, pady=4).pack()
            w.update_idletasks()
            x = int(self.x) + self.fw // 2 - w.winfo_width() // 2
            y = int(self.y) - w.winfo_height() - 5
            x1, y1, _x2, _y2 = self.ov.area()
            if y < y1:
                y = int(self.y) + self.fh + 5
            w.geometry("+%d+%d" % (x, y))
            self.tip_win = w
        except Exception:
            self.tip_win = None

    def hide_tip(self):
        if self.tip_win:
            try:
                self.tip_win.destroy()
            except Exception:
                pass
            self.tip_win = None

    # ---------------- 입력 ----------------
    def on_press(self, e):
        # 누르고 있는 동안만 잠깐 멈춘다. 위치는 건드리지 않는다.
        self.state = "held"
        self.hide_tip()

    def on_release(self, e):
        self.state = "idle"
        self.timer = random.randint(20, 60)

    def on_menu(self, e):
        self.ov.on_pet_menu(self, e)

    def on_double(self, e):
        self.ov.on_pet_open(self)

    # ---------------- 움직임 ----------------
    def clamp(self):
        x1, y1, x2, y2 = self.ov.area()
        m = self.ov.settings["areaMargin"]
        self.x = max(x1 + m, min(self.x, x2 - self.fw - m))
        self.y = max(y1 + m, min(self.y, y2 - self.fh - m))

    def place(self):
        self.win.geometry("+%d+%d" % (int(self.x), int(self.y)))
        if self.name_win:
            self.name_win.geometry("+%d+%d" % (int(self.x), int(self.y) - 17))
        if self.tip_win:
            self.hide_tip()

    def row_for(self, facing):
        """이 방향 그림이 없으면 있는 것 중에서 고른다.

        배틀 도트로 대신하는 종(걷는 도트가 없는 57마리)은 좌우 두 벌뿐이라
        위/아래로 갈 때도 좌우 중 하나를 써야 한다.
        """
        if facing in self.photos:
            return self.photos[facing]
        if facing == UP:
            return self.photos.get(LEFT) or self.photos[RIGHT]
        return self.photos.get(RIGHT) or list(self.photos.values())[0]

    def redraw(self):
        row = self.row_for(self.facing)
        self.label.configure(image=row[self.frame % len(row)])

    def advance(self, ms):
        """프레임을 넘긴다.

        걷는 도트는 **걸을 때만** 넘긴다. 서 있는데 발이 움직이면
        제자리걸음처럼 보여서 오히려 어색하다. 서 있을 때는 첫 프레임으로
        돌아가 가만히 선다.
        배틀 도트로 대신하는 종은 원래 제자리 애니메이션이라 늘 돌린다.
        """
        if self.walking_sprite and self.state != "walk":
            if self.frame != 0:
                self.frame = 0
                self.elapsed = 0
                self.redraw()
            return
        self.elapsed += ms
        d = self.anim.durations[self.frame % len(self.anim.durations)]
        if self.elapsed >= d:
            self.elapsed = 0
            self.frame = (self.frame + 1) % self.anim.count()
            self.redraw()

    def pick_move(self):
        """새 목적지 방향을 고른다. 대각선도 섞어서 자연스럽게."""
        import math
        ang = random.uniform(0, 2 * math.pi)
        self.vx = math.cos(ang)
        self.vy = math.sin(ang) * 0.65        # 세로로는 덜 움직이게
        want = (sprites.dir_from(self.vx, self.vy) if self.walking_sprite
                else (RIGHT if self.vx > 0 else LEFT))
        if want != self.facing:
            self.facing = want
            self.frame = 0
            self.elapsed = 0
        self.redraw()

    def face_towards(self, x):
        """저쪽을 바라보게 방향을 돌린다."""
        want = RIGHT if x > self.x else LEFT
        if want != self.facing:
            self.facing = want
            self.redraw()

    def turn_to(self, vx, vy):
        """움직이는 방향에 맞춰 몸을 돌린다."""
        want = (sprites.dir_from(vx, vy) if self.walking_sprite
                else (RIGHT if vx >= 0 else LEFT))
        if want != self.facing:
            self.facing = want
            self.frame = 0
            self.elapsed = 0
            self.redraw()

    def update(self, ms):
        self.advance(ms)
        if self.state == "held" or self.battling:
            return
        s = self.ov.settings
        self.timer -= 1
        if self.timer <= 0:
            if self.state == "walk" and random.random() < 0.4:
                self.state = "idle"
                self.timer = random.randint(40, 150)
            else:
                self.state = "walk"
                self.pick_move()
                self.timer = random.randint(40, 160)
        if self.state != "walk":
            return

        x1, y1, x2, y2 = self.ov.area()
        m = s["areaMargin"]
        speed = s["walkSpeed"]
        nx = self.x + self.vx * speed
        ny = self.y + self.vy * speed
        bounced = False
        if nx < x1 + m or nx > x2 - self.fw - m:
            self.vx = -self.vx
            bounced = True
        if ny < y1 + m or ny > y2 - self.fh - m:
            self.vy = -self.vy
            bounced = True
        if bounced:
            self.turn_to(self.vx, self.vy)
            return
        self.x, self.y = nx, ny
        self.place()

    def destroy(self):
        self.cancel_tip()
        for w in (self.tip_win, self.name_win, self.win):
            try:
                if w:
                    w.destroy()
            except Exception:
                pass


class Overlay(object):
    """화면에 나와 있는 포켓몬 전체를 관리한다."""

    def __init__(self, root, settings, on_pet_menu=None, on_pet_open=None):
        self.root = root
        self.settings = settings
        # 풀숲·몬스터볼처럼 직접 그리는 그림에만 쓰는 고정 투명색
        self.key = (255, 0, 255)
        self.pets = {}
        self.paths = {}
        self.walks = {}          # {번호: (시트경로, meta)} — 걷는 도트
        self._menu_cb = on_pet_menu
        self._open_cb = on_pet_open
        self._running = False
        self.hidden = False

    # ---------------- 영역 ----------------
    def area(self):
        s = self.settings
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        wl, wt, wr, wb = work_area(sw, sh)
        x2 = wr - s["areaMarginR"]
        y2 = wb - s["areaMarginB"]
        x1 = max(wl, x2 - s["areaW"])
        y1 = max(wt, y2 - s["areaH"])
        return x1, y1, x2, y2

    # ---------------- 콜백 ----------------
    def on_pet_menu(self, pet, e):
        if self._menu_cb:
            self._menu_cb(pet, e)

    def on_pet_open(self, pet):
        if self._open_cb:
            self._open_cb(pet)

    # ---------------- 목록 맞추기 ----------------
    def sync(self, mons, paths, walks=None):
        """서버가 알려준 '바탕화면에 있어야 할 목록' 과 화면을 일치시킨다.

        paths 는 {(번호, 이로치): 파일경로} — 미리 받아둔 배틀 도트.
        walks 는 {번호: (시트경로, meta)} — 걷는 도트가 있는 종만.
        """
        self.paths.update(paths or {})
        if walks:
            self.walks.update(walks)
        want = dict((m["id"], m) for m in mons)
        for pid in list(self.pets):
            if pid not in want:
                self.pets.pop(pid).destroy()
        added = []
        for pid, mon in want.items():
            if pid in self.pets:
                self.pets[pid].mon = mon
                continue
            pet = self.make(mon)
            if pet:
                self.pets[pid] = pet
                added.append(mon)
                if self.hidden:
                    try:
                        pet.win.withdraw()
                    except Exception:
                        pass
        return added

    def path_for(self, mon):
        k = (mon.get("num"), bool(mon.get("shiny")))
        return self.paths.get(k) or self.paths.get((mon.get("num"), False))

    def make(self, mon, cls=None):
        s = self.settings
        anim = None

        # 걷는 도트가 있으면 그걸 먼저 쓴다. 4방향에 걷기 프레임이 있어서
        # 위로 가면 등이 보이고 걸을 때 발이 바뀐다.
        sheet, meta = self.walks.get(mon.get("num")) or (None, None)
        if sheet and meta:
            try:
                anim = sprites.load_walk(sheet, meta, s["targetHeight"],
                                         s["minScale"], max(2.5, s["maxScale"]))
            except Exception:                              # noqa: BLE001
                anim = None

        # 없는 종(1025 중 57마리)은 배틀 도트로 대신한다. 정면 고정이지만
        # 아무것도 안 뜨는 것보다는 낫다.
        if anim is None:
            path = self.path_for(mon)
            if not path:
                return None
            try:
                anim = sprites.load_animation(path, s["targetHeight"],
                                              s["minScale"], s["maxScale"])
            except Exception:                              # noqa: BLE001
                return None
        return (cls or Pet)(self, mon, anim)

    def clear(self):
        for p in self.pets.values():
            p.destroy()
        self.pets.clear()

    def set_hidden(self, hidden):
        """배틀 중처럼 잠깐 치워야 할 때. 목록은 그대로 두고 창만 감춘다."""
        self.hidden = bool(hidden)
        for p in list(self.pets.values()):
            for w in (p.win, p.name_win):
                if not w:
                    continue
                try:
                    w.withdraw() if hidden else w.deiconify()
                except Exception:
                    pass
            p.hide_tip()

    def refresh_visuals(self):
        """설정(크기/이름표)이 바뀌면 전부 다시 만든다."""
        mons = [p.mon for p in self.pets.values()]
        self.clear()
        sprites.clear_cache()
        self.sync(mons, {})

    # ---------------- 루프 ----------------
    def start(self):
        if self._running:
            return
        self._running = True
        self._tick()

    def stop(self):
        self._running = False

    def _tick(self):
        if not self._running:
            return
        ms = int(1000 / max(1, self.settings["fps"]))
        for p in list(self.pets.values()):
            try:
                p.update(ms)
            except Exception as e:                       # noqa: BLE001
                # 예전에는 그냥 pass 였다. 그러면 매 틱마다 터져도 아무도
                # 모르고, 화면에서는 "포켓몬이 가만히 있다" 로만 보인다.
                # 한 마리당 한 번만 남긴다(초당 30번 로그를 쌓지 않게).
                if not getattr(p, "_logged_error", False):
                    p._logged_error = True
                    import traceback
                    config.log("포켓몬 %s 움직임 오류: %s\n%s"
                               % (p.id, e, traceback.format_exc()))
        self.root.after(ms, self._tick)
