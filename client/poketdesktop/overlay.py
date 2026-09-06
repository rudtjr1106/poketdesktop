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

from . import config
from . import platform_os as PLAT
from . import sprites
from .sprites import DOWN, LEFT, RIGHT, UP
from . import ui_common as U


def work_area(fallback_w, fallback_h):
    """작업표시줄(맥은 메뉴 막대와 독)을 뺀 화면 영역."""
    return PLAT.work_area(fallback_w, fallback_h)


# 이만큼 안 건드리면 쉰다.
#
# **틱이 아니라 시간으로 센다.** 틱으로 세면 settings["fps"] 를 낮춘
# 사람은 그만큼 늦게 자게 된다 - 같은 30분이어야 한다.
#
# 30분은 "자리를 떴다" 가 확실해지는 시간이다. 짧게 잡으면 잠깐 딴 창을
# 보다 돌아왔는데 쉬고 있어서, 걸어다니라고 켜 둔 프로그램이 대부분
# 멈춰 있게 된다.
SLEEP_AFTER_MS = 1800000

# 쉴 때 하는 것. 셋 중 하나를 골라 그 자세로 있는다.
#
# 32종을 세어 보니 Sleep 은 전 종에 있고 Sit/Laying 은 절반쯤(17/32)이다.
# 그래서 없는 것은 빼고 있는 것 중에서만 고른다 - 늘 자기만 하지 않게.
REST_POSES = ("Sit", "Laying", "Sleep")


class Pet(object):
    """포켓몬 한 마리."""

    def __init__(self, overlay, mon, anim):
        self.ov = overlay
        self.mon = mon
        self.id = mon.get("id")
        self._first_anim = anim
        self.fw, self.fh = anim.w, anim.h
        key = anim.key                    # 투명색은 그림마다 다르다
        hexkey = "#%02x%02x%02x" % key

        # 걷는 도트면 방향이 4개, 배틀 도트면 좌우 2개다.
        self.walking_sprite = isinstance(anim, sprites.WalkAnimation)

        # **자리를 먼저 정한다.** 창을 만들면 그 순간 화면에 올라가는데
        # (맥은 '항상 위' 를 걸려고 update_idletasks 를 부른다), 자리를
        # 나중에 정하면 엉뚱한 곳에 한 번 떴다가 옮겨가는 것이 보인다.
        x1, y1, x2, y2 = overlay.area()
        m = overlay.settings["areaMargin"]
        self.x = random.randint(x1 + m, max(x1 + m, x2 - self.fw - m))
        self.y = random.randint(y1 + m, max(y1 + m, y2 - self.fh - m))

        self.win = tk.Toplevel(overlay.root)
        self.win.overrideredirect(True)
        self.win.geometry("+%d+%d" % (int(self.x), int(self.y)))
        # 창을 뚫는 방법은 OS 마다 다르다. 윈도우는 투명색을 지정하고,
        # 맥은 창 배경 자체를 투명하게 한다 - platform_os 가 고른다.
        bg = PLAT.transparent_window(self.win, hexkey)
        self.view = PLAT.SpriteView(self.win, bg, self.fw, self.fh)
        self.label = self.view.widget      # 마우스는 이 위젯이 받는다
        # 동작마다 그림을 미리 다 만들지 않는다. 피카츄의 Attack 은
        # 127x106 이 8방향 x 10프레임이라, 한 마리당 그것만 800장이다.
        # 여섯 마리를 띄우는 프로그램에서 그러면 메모리가 감당이 안 된다.
        # **쓰는 순간에 그 방향치만** 만들고 여기에 담아 둔다.
        self.anims = {"Walk": anim}          # 이름 -> WalkAnimation
        self.miss = set()                    # 이 종에 없다고 확인된 동작
        self.photo_cache = {}                # (이름, 방향) -> PhotoImage 목록
        self.anim_name = "Walk"
        self.base_scale = getattr(anim, "scale", None)
        self.ax = getattr(anim, "ax", self.fw / 2.0)
        self.ay = getattr(anim, "ay", self.fh / 2.0)
        self.once = None                     # 한 번만 돌리는 중인 동작
        self.once_then = None
        self.photos = self._photos(anim, key)
        PLAT.raise_above(self.win)

        self.facing = random.choice(list(self.photos.keys()))
        self.frame = random.randrange(anim.count())
        self.elapsed = 0
        self.state = "idle"
        self.timer = random.randint(20, 80)
        self.vx = self.vy = 0.0
        self.walked = 0.0            # 걸은 거리. 걸음 위상을 여기에 묶는다
        self.battling = False        # 배틀 중에는 스스로 돌아다니지 않는다
        self.calm_ms = 0             # 안 건드린 시간(ms). 쌓이면 잠든다
        self.sleeping = False        # 자는 중. 자면 돌아다니지 않는다
        self.rest_pose = None        # 서 있을 때 취할 자세 (앉기/눕기)

        self.label.bind("<Enter>", self.on_enter)
        self.label.bind("<Leave>", self.on_leave)
        # 끌어서 옮기는 기능은 뺐다. 쓰다 보면 쓰다듬으려다 실수로 끌려가서
        # 오히려 불편했다. 누르고 떼는 것만 남긴다 —
        # 야생 포켓몬을 왼쪽 클릭해 배틀을 걸 때 이게 필요하다.
        self.label.bind("<Button-1>", self.on_press)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        PLAT.bind_right(self.label, self.on_menu)
        self.label.bind("<Double-Button-1>", self.on_double)

        self.name_win = None
        self.name_label = None
        self.tip_win = None
        self.tip_job = None
        if overlay.settings.get("showNames"):
            self.make_nameplate()

        self.redraw()
        self.place()

    # ---------------- 이름표 ----------------
    def nameplate_text(self):
        info = self.mon.get("info", {})
        text = "%s Lv.%s" % (info.get("name", "?"), info.get("level", "?"))
        if self.mon.get("shiny"):
            text = "★ " + text
        return text

    def nameplate_color(self):
        return U.TIP_SHINY if self.mon.get("shiny") else U.TIP_FG

    def make_nameplate(self):
        w = tk.Toplevel(self.ov.root)
        w.overrideredirect(True)
        w.attributes("-alpha", 0.88)
        w.configure(bg=U.TIP_BG)
        self.name_label = tk.Label(w, text=self.nameplate_text(), bg=U.TIP_BG,
                                   fg=self.nameplate_color(), font=U.FONT_TIP)
        self.name_label.pack(padx=5, pady=1)
        # 맥에서는 창이 화면에 올라간 뒤에 걸어야 '항상 위' 가 먹는다.
        # 그냥 두면 이름표만 다른 창 뒤로 숨는다.
        PLAT.raise_above(w)
        self.name_win = w

    def set_mon(self, mon):
        """서버가 준 새 값으로 갈아 끼운다. **이름표도 같이 고친다.**

        레벨이 올라도 바탕화면 이름표의 숫자는 그대로였다. 이름표는 만들
        때 글자를 박아 넣고, sync 는 mon 만 바꿔 끼웠기 때문이다. 포켓몬
        관리 창은 열 때마다 새로 그려서 거기서만 올라 보였다. 별명을
        바꿨을 때도 같은 이유로 안 바뀌었다.
        """
        self.mon = mon
        self.refresh_nameplate()

    def refresh_nameplate(self):
        lbl = getattr(self, "name_label", None)
        if not self.name_win or lbl is None:
            return
        try:
            lbl.configure(text=self.nameplate_text(), fg=self.nameplate_color())
        except Exception:                                   # noqa: BLE001
            pass

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
            PLAT.raise_above(w)
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
        self.wake()
        self.state = "held"
        self.hide_tip()

    def on_release(self, e):
        self.state = "idle"
        self.timer = random.randint(20, 60)

    def on_menu(self, e):
        self.wake()
        self.ov.on_pet_menu(self, e)

    def on_double(self, e):
        self.wake()
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

    # ---------------- 동작 갈아끼우기 ----------------
    def _photos(self, anim, key):
        """지금 보고 있는 방향치만 만든다. 나머지는 볼 때 만든다."""
        d = getattr(self, "facing", None)
        if d is None or d not in anim.frames:
            d = list(anim.frames.keys())[0]
        return {d: self.view.frames(anim.frames[d], key)}

    def frames_for(self, d):
        """이 동작 이 방향의 그림. 아직 안 만들었으면 지금 만든다."""
        got = self.photos.get(d)
        if got is not None:
            return got
        anim = self.anims.get(self.anim_name)
        if anim is None or d not in anim.frames:
            return None
        got = self.view.frames(anim.frames[d], anim.key)
        self.photos[d] = got
        return got

    def anim_for(self, name):
        """그 동작의 애니메이션. 아직 안 잘랐으면 지금 자른다. 없으면 None.

        **배율은 걷기에서 정한 것을 물려준다.** 동작마다 목표 높이에
        맞추면 공격할 때만 몸이 작아진다 - 칸 크기가 걷기 32x40,
        공격 80x80 처럼 크게 다르기 때문이다.
        """
        got = self.anims.get(name)
        if got is not None:
            return got
        if not self.walking_sprite:
            return None                   # 배틀 도트로 대신하는 종
        key = (self.mon.get("num"), name)
        if key in self.miss:
            return None
        ent = self.ov.sheets.get(key)
        if ent is None:
            # **아직 안 받았을 뿐이다. 없다고 적어 두면 안 된다.**
            # 시트는 포켓몬이 나온 뒤에 뒷줄에서 받는다. 여기서 굳혀
            # 버리면 다 받고 나서도 영영 걷기만 한다 - 실제로 그랬다.
            return None
        sheet, meta = ent
        if not sheet or not meta:
            self.miss.add(key)            # 이 종에 이 동작이 없다
            return None
        try:
            anim = sprites.load_walk(sheet, meta,
                                     self.ov.settings["targetHeight"],
                                     scale=self.base_scale, name=name)
        except Exception:                                  # noqa: BLE001
            self.miss.add(key)
            return None
        self.anims[name] = anim
        return anim

    def play(self, name, once=False, then=None):
        """동작을 바꾼다. 그 종에 없으면 아무 일도 안 하고 False.

        **기준점을 붙들고 바꾼다.** 동작마다 그림 크기가 달라서, 창
        왼쪽 위를 그대로 두면 몸이 순간이동한다. 칸 한가운데가 화면의
        같은 자리에 오도록 창을 옮긴다 (sprites.WalkAnimation 을 보라).
        """
        if name == self.anim_name and not once:
            return True
        anim = self.anim_for(name)
        if anim is None:
            return False
        cx = self.x + self.ax
        cy = self.y + self.ay
        self.anim_name = name
        self.photo_cache[name] = self.photo_cache.get(name) or {}
        self.photos = self.photo_cache[name]
        self.fw, self.fh = anim.w, anim.h
        self.ax, self.ay = anim.ax, anim.ay
        self.frame = 0
        self.elapsed = 0
        self.walked = 0.0
        self.once = name if once else None
        self.once_then = then if once else None
        self.x = cx - self.ax
        self.y = cy - self.ay
        try:
            self.view.resize(anim.w, anim.h)
        except Exception:                                  # noqa: BLE001
            pass
        self.redraw()
        self.place()
        return True

    def end_once(self):
        """한 번짜리 동작이 끝났다. 원래대로 돌아간다."""
        then, self.once, self.once_then = self.once_then, None, None
        self.play("Walk" if self.state == "walk" else self.rest_anim())
        if then:
            try:
                then()
            except Exception:                              # noqa: BLE001
                pass

    def rest_anim(self):
        """가만히 있을 때 무엇을 돌릴까.

        쉬는 중이면 그때 고른 자세(앉기/눕기/자기)를, 아니면 그냥 숨을
        쉰다. 걷다 잠깐 서는 것과 오래 쉬는 것은 다르다.
        """
        if self.sleeping and self.rest_pose:
            if self.anim_for(self.rest_pose) is not None:
                return self.rest_pose
        return "Idle" if self.anim_for("Idle") is not None else "Walk"

    def wake(self, show=True):
        """깨운다. **일어나서 다시 걷는다.** 안 쉬고 있었으면 시계만 되돌린다.

        show 가 참이면 깨는 모습을 한 번 보여준다. 배틀이 시작돼서 깨는
        경우처럼 바로 다음 연출이 있는 자리에서는 끄고 부른다 - 깨는
        동작이 그 연출을 밀어내면 무슨 일이 난 건지 안 읽힌다.

        깨는 모습(Wake)은 한 번짜리라, 끝나면 end_once() 가 state 를 보고
        걷기로 돌려놓는다. 그래서 여기서 state 를 먼저 walk 로 바꾼다.
        """
        self.calm_ms = 0
        if not self.sleeping:
            return
        self.sleeping = False
        self.rest_pose = None
        self.state = "walk"
        self.timer = random.randint(40, 160)
        self.pick_move()
        if show and self.play("Wake", once=True):
            return
        self.play("Walk")

    def row_for(self, facing):
        """이 방향 그림이 없으면 있는 것 중에서 고른다.

        배틀 도트로 대신하는 종(걷는 도트가 없는 57마리)은 좌우 두 벌뿐이라
        위/아래로 갈 때도 좌우 중 하나를 써야 한다.
        """
        got = self.frames_for(facing)
        if got:
            return got
        if facing == UP:
            return self.frames_for(LEFT) or self.frames_for(RIGHT)
        got = self.frames_for(RIGHT)
        if got:
            return got
        return list(self.photos.values())[0]

    @property
    def anim(self):
        """지금 돌고 있는 동작."""
        return self.anims.get(self.anim_name) or self._first_anim

    def redraw(self):
        row = self.row_for(self.facing)
        if not row:
            return
        self.view.show(row[self.frame % len(row)])

    def stride(self):
        """한 프레임 넘어가는 데 걸어야 하는 거리(px).

        키에 비례한다. 큰 포켓몬은 보폭도 크다.
        """
        return max(3.5, self.fh * 0.14)

    def advance(self, ms):
        """프레임을 넘긴다.

        걷는 도트는 **걸은 거리**에 맞춰 넘긴다. 시간으로 넘기면 느리게
        움직일 때도 발은 같은 속도로 굴러서 빙판 위를 걷는 것처럼 보인다.
        발이 땅을 짚는 속도와 실제로 나아가는 속도가 맞아야 걷는 것으로
        읽힌다.

        서 있을 때는 첫 프레임으로 돌아가 가만히 선다. 제자리에서 발만
        움직이면 오히려 어색하다.

        배틀 도트로 대신하는 종은 원래 제자리 애니메이션이라 시간으로 돌린다.
        """
        # 한 번짜리 동작(공격·맞음·기뻐하기)은 시간으로 돌리고, 끝나면
        # 원래대로 돌아간다.
        if self.once:
            self.elapsed += ms
            d = self.anim.durations[self.frame % len(self.anim.durations)]
            if self.elapsed >= d:
                self.elapsed = 0
                if self.frame + 1 >= self.anim.count():
                    return self.end_once()
                self.frame += 1
                self.redraw()
            return

        if self.walking_sprite and self.anim_name != "Walk":
            # 서 있을 때 돌리는 것(Idle/Sleep)은 제자리 애니메이션이라
            # 시간으로 돌린다. 걸은 거리로 넘기면 영영 안 움직인다.
            self.elapsed += ms
            d = self.anim.durations[self.frame % len(self.anim.durations)]
            if self.elapsed >= d:
                self.elapsed = 0
                self.frame = (self.frame + 1) % self.anim.count()
                self.redraw()
            return

        if self.walking_sprite:
            if self.state != "walk":
                if self.frame != 0:
                    self.frame = 0
                    self.walked = 0.0
                    self.redraw()
                return
            step = self.stride()
            if self.walked >= step:
                n = int(self.walked / step)
                self.walked -= n * step
                self.frame = (self.frame + n) % self.anim.count()
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
        want = (self.dir_for(self.vx, self.vy) if self.walking_sprite
                else (RIGHT if self.vx > 0 else LEFT))
        if want != self.facing:
            self.facing = want
            self.frame = 0
            self.elapsed = 0
        self.redraw()

    def dir_for(self, vx, vy):
        """방향을 고른다. 대각선 그림이 있으면 여덟 방향, 없으면 넷.

        SpriteCollab 시트에는 대각선이 진짜로 들어 있다(행 1/3/5/7).
        followers 로 메운 종은 4행뿐이라 대각선이 없다.
        """
        anim = self.anims.get("Walk") or self._first_anim
        eight = len(getattr(anim, "frames", {}) or {}) >= 8
        if eight and (getattr(anim, "name", "") or "") and self._has_diag():
            return sprites.dir_from(vx, vy)
        return sprites.dir_four(vx, vy)

    def _has_diag(self):
        """대각선 그림이 진짜 따로 있는가.

        4행짜리 출처는 load_walk 가 대각선을 좌우 행으로 때워 두므로
        방향 수만 봐서는 구분이 안 된다. 그림이 같은지 본다.
        """
        got = getattr(self, "_diag", None)
        if got is not None:
            return got
        anim = self.anims.get("Walk") or self._first_anim
        fr = getattr(anim, "frames", None) or {}
        try:
            got = (fr[sprites.DOWNRIGHT][0].tobytes()
                   != fr[sprites.RIGHT][0].tobytes())
        except Exception:                                  # noqa: BLE001
            got = False
        self._diag = got
        return got

    def face_towards(self, x):
        """저쪽을 바라보게 방향을 돌린다."""
        want = RIGHT if x > self.x else LEFT
        if want != self.facing:
            self.facing = want
            self.redraw()

    def turn_to(self, vx, vy):
        """움직이는 방향에 맞춰 몸을 돌린다."""
        want = (self.dir_for(vx, vy) if self.walking_sprite
                else (RIGHT if vx >= 0 else LEFT))
        if want != self.facing:
            self.facing = want
            self.frame = 0
            self.elapsed = 0
            self.redraw()

    def update(self, ms):
        self.advance(ms)
        if self.once:
            return                   # 한 번짜리 동작 중에는 안 움직인다
        if self.state == "held" or self.battling:
            # 붙잡혀 있거나 배틀 중이면 자고 있을 때가 아니다. 깨는
            # 모습은 안 보여준다 - 곧 이어질 연출을 밀어낸다.
            self.wake(show=False)
            return

        # **안 건드린 시간을 잰다.** 걷고 있어도 쌓인다 - 이건 "이 사람이
        # 자리를 비웠나" 를 보는 것이지 "포켓몬이 서 있었나" 가 아니다.
        # 전에는 서 있은 틱을 셌는데, 서 있는 상태가 길어야 150틱이라
        # 900틱이 필요한 잠들기에 **영영 못 닿았다.** 111분을 돌려도
        # 최고 기록이 150틱이었다.
        self.calm_ms += ms
        if not self.sleeping and self.calm_ms > SLEEP_AFTER_MS:
            # 앉기·눕기·자기 중에서 **이 종에 있는 것만** 놓고 고른다.
            have = [n for n in REST_POSES if self.anim_for(n) is not None]
            if not have and self.anim_for("EventSleep") is not None:
                have = ["EventSleep"]
            if have:
                self.sleeping = True
                self.state = "idle"
                self.rest_pose = random.choice(have)

        if self.sleeping:
            # 쉬는 동안은 돌아다니지 않는다. 자면서 걸으면 자는 게 아니다.
            want = self.rest_anim()
            if want != self.anim_name:
                self.play(want)
            return

        s = self.ov.settings
        self.timer -= 1
        if self.timer <= 0:
            if self.state == "walk" and random.random() < 0.4:
                # 걷다 잠깐 서는 것. 이때는 숨만 쉰다 - 앉거나 눕는 것은
                # 오래 안 건드렸을 때만 한다.
                self.state = "idle"
                self.timer = random.randint(40, 150)
            else:
                self.state = "walk"
                self.pick_move()
                self.timer = random.randint(40, 160)
        if self.state != "walk":
            want = self.rest_anim()
            if want != self.anim_name:
                self.play(want)
            return
        if self.anim_name != "Walk":
            self.play("Walk")

        x1, y1, x2, y2 = self.ov.area()
        m = s["areaMargin"]
        speed = s["walkSpeed"]

        # **영역 밖에 나가 있으면 먼저 데려온다.**
        #
        # 활동 영역은 화면이 바뀌면 같이 바뀐다 - 노트북을 닫았다 열거나
        # 모니터를 뺐다 꽂으면 그렇다. 그때 도트가 새 영역 밖에 남는데,
        # 아래 튕기기만으로는 영영 못 돌아온다. vx 를 뒤집어도 여전히
        # 밖이라 다음 틱에 또 튕기고, 그게 끝없이 반복되면서 **제자리에서
        # 좌우로 고개만 흔든다.** 실제로 그랬다.
        if not (x1 + m <= self.x <= x2 - self.fw - m
                and y1 + m <= self.y <= y2 - self.fh - m):
            self.clamp()
            self.place()
            return

        nx = self.x + self.vx * speed
        ny = self.y + self.vy * speed
        bounced = False
        # **나가는 쪽으로 갈 때만** 튕긴다. 방향까지 보지 않으면, 가장자리에
        # 딱 붙었을 때 안으로 들어오려는 걸음까지 되돌려서 그 자리에 갇힌다.
        if ((nx < x1 + m and self.vx < 0)
                or (nx > x2 - self.fw - m and self.vx > 0)):
            self.vx = -self.vx
            bounced = True
        if ((ny < y1 + m and self.vy < 0)
                or (ny > y2 - self.fh - m and self.vy > 0)):
            self.vy = -self.vy
            bounced = True
        if bounced:
            self.turn_to(self.vx, self.vy)
            return
        moved = ((nx - self.x) ** 2 + (ny - self.y) ** 2) ** 0.5
        self.walked += moved
        self.x, self.y = nx, ny
        self.place()

    def destroy(self):
        self.cancel_tip()
        try:
            self.view.destroy()
        except Exception:                                   # noqa: BLE001
            pass
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
        # 서버 목록에 없는, 화면에만 있는 도트들. 투기장에서 상대편 여섯
        # 마리를 여기 넣는다. sync() 는 여기를 건드리지 않으므로 서버가
        # 준 목록과 섞이지 않고, _tick 은 여기도 같이 움직여 준다.
        self.extra = []
        # 투기장이 화면을 쥐고 있는 동안 켠다. 켜져 있으면 sync() 가
        # 도트를 새로 배치하지 않는다 - 싸우는 중에 서버 목록이 와서
        # 자리를 흐트러뜨리면 안 된다.
        self.locked = False
        self.paths = {}
        self.walks = {}          # {번호: (시트경로, meta)} — 걷는 도트
        # 걷기 말고 다른 동작. {(번호, 이름): (시트경로, meta)}
        # 켤 때 다 받으면 첫 화면이 그만큼 늦어지므로, 포켓몬이 나온
        # 뒤에 뒷줄에서 하나씩 받아 채운다 (app._prefetch_anims).
        # (self.extra 는 야생 포켓몬 목록이라 이름을 겹치면 안 된다.)
        self.sheets = {}
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
        if self.locked:
            # 투기장 중. 받아둔 도트 경로만 챙기고 배치는 건드리지 않는다.
            return []
        want = dict((m["id"], m) for m in mons)
        for pid in list(self.pets):
            if pid not in want:
                self.pets.pop(pid).destroy()
        added = []
        for pid, mon in want.items():
            if pid in self.pets:
                self.pets[pid].set_mon(mon)
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
        """화면의 도트를 전부 없앤다.

        extra 도 같이 비운다. 로그아웃/세션만료 때 여기만 부르고 마는
        경로가 여럿이라, 투기장이 남긴 상대편 도트가 여기서 안 지워지면
        주인 없는 창이 바탕화면에 그대로 떠 있게 된다.
        """
        for p in self.pets.values():
            p.destroy()
        self.pets.clear()
        for p in self.extra:
            try:
                p.destroy()
            except Exception:                            # noqa: BLE001
                pass
        self.extra = []
        self.locked = False

    def set_hidden(self, hidden):
        """배틀 중처럼 잠깐 치워야 할 때. 목록은 그대로 두고 창만 감춘다."""
        self.hidden = bool(hidden)
        for p in list(self.pets.values()):
            for w in (p.win, p.name_win):
                if not w:
                    continue
                try:
                    w.withdraw() if hidden else PLAT.show_again(w)
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
        cx = cy = None
        if PLAT.NEEDS_HIT_TRACKING:
            # 맥은 도트가 없는 자리도 창이 클릭을 먹는다. 커서가 어디
            # 있는지 봐서 빈 자리면 통과시켜 준다 (SpriteView.update_hit).
            try:
                cx, cy = self.root.winfo_pointerxy()
            except Exception:                               # noqa: BLE001
                cx = cy = None
        for p in list(self.pets.values()) + list(self.extra):
            try:
                p.update(ms)
                if cx is not None:
                    p.view.update_hit(cx - int(p.x), cy - int(p.y))
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
