# -*- coding: utf-8 -*-
"""포켓몬과 집중하기 — 바탕화면 포켓몬의 집중 동작과 그 밑의 시간표.

    a = Activity(pet, "spa")      pet.drive = a   -> Pet.update 가 a.update(pet, ms) 로 넘긴다
    a.stop(pet)                   원래대로 (스스로 돌아다닌다)
    t = Tag(root, pet, "spa")     도트 밑 작은 창: [소품] 공부 12:34
    t.set(남은 초, 오늘 노력치, 하루 상한) · t.destroy()

동작은 **이미 받아 두는 동작 그림**(walk_cache.ANIMS: Idle · Sit · Hop · Sleep · Laying …)에 작은 움직임을 얹어
만든다. 새 그림을 받지 않는다. 그 종에 그 그림이 없으면 다음 것으로, 끝내 없으면 걷기 그림의 첫 칸으로 선다
(걷기 그림뿐인 종 - walk_cache.WALK_ONLY 출처 - 도 어색하지 않게).

    헬스(공격)     서서 600ms 마다 몸을 4px 들었다 놓는다
    공부(특공)     앉는다 (Sit → Idle). 제자리
    달리기(스피드)  걷기 그림으로 닻에서 좌우로 왕복 (걷는 속도의 두 배)
    스트레칭(체력)  서서 1.5초마다 좌우로 돌아보고, 4.5초마다 한 번 깡충 (Hop 이 있으면)
    버티기(방어)    서서 2초마다 0.3초 부르르 떤다 (±2px)
    명상(특방)     앉기 → 눕기 → 자기 → 서기 중 있는 것. 제자리

**맥 CPU**: 맥 Tk 는 창을 옮길 때마다 다시 칠한다. 그래서 자리가 바뀐 틱에만 place() 를 부른다 - 공부 · 명상은
처음 한 번 말고는 창을 옮기지 않는다 (client/test_focus_ui.py 가 잰다).

소품(아령 · 책 · 운동화 · 머리띠 · 방패 · 반짝임)은 8x8 도트를 코드로 그려 키운다 - 바깥 그림 파일이 없다.
"""
import random
import tkinter as tk

from PIL import Image, ImageTk

from common import focus as F

from . import platform_os as PLAT
from . import ui_common as U
from .sprites import LEFT, RIGHT

# 능력마다 쓸 동작 그림 (앞에서부터 그 종에 있는 것). 끝내 없으면 Walk.
POSES = {"atk": ("Idle",), "spa": ("Sit", "Idle"), "spe": ("Walk",), "hp": ("Idle",),
         "def": ("Idle",), "spd": ("Sit", "Laying", "Sleep", "Idle")}
LIFT_MS, LIFT_PX = 600, 4                  # 헬스
TURN_MS, HOP_MS = 1500, 4500               # 스트레칭
SHAKE_EVERY, SHAKE_MS, SHAKE_PX = 2000, 300, 2    # 버티기
RUN_SPEED = 2.0                            # 달리기: 걷는 속도의 몇 배


class Activity(object):
    """집중하는 동안 그 포켓몬을 움직인다 (Pet.drive).

    **닻은 발 기준점(창 왼쪽 위 + ax, ay)이다** (독립 검토 #1). 동작마다 칸 크기 · 기준점이 달라서 창 왼쪽 위를
    닻으로 삼으면 깡충(Hop) 한 번마다 몸이 (Idle.ay - Hop.ay) 만큼 떠오르고, 그것이 세트마다 쌓였다. Pet.play 도
    발 기준점을 붙들고 창을 옮기므로, 여기서도 틱마다 지금 동작의 ax/ay 로 창 자리를 셈한다.
    """

    def __init__(self, pet, stat):
        self.stat = stat
        self.t = 0
        self.dir = 1
        self.last_hop = 0
        self.run = 0.0                     # 달리기: 닻에서 옆으로 간 거리 (발 기준)
        self.off = (0, 0)                  # 지난 틱에 얹은 움직임 (들썩 · 떨림)
        pet.wake(show=False)
        pet.sleeping = False
        pet.rest_pose = None
        pet.calm_ms = 0
        self.pose = self._pose(pet)
        pet.play(self.pose)
        pet.state = "walk" if stat == "spe" else "idle"
        if stat != "spe" and pet.anim_name == "Walk" and pet.frame:
            pet.frame = 0                  # 걷기 그림으로 서 있을 때는 첫 칸
            pet.redraw()
        self._anchor(pet)

    def half(self, pet):
        """달리기 폭의 절반 (px)."""
        return max(40, 1.5 * pet.fw)

    def _pose(self, pet):
        for n in POSES.get(self.stat, ("Idle",)):
            if n == "Walk" or pet.anim_for(n) is not None:
                return n
        return "Walk"

    @staticmethod
    def _foot(pet):
        return pet.x + getattr(pet, "ax", pet.fw / 2.0), pet.y + getattr(pet, "ay", pet.fh / 2.0)

    def _anchor(self, pet):
        """지금 발 자리를 닻으로 삼는다 (얹어 둔 움직임은 뺀다). 달리기는 좌우로 뛸 자리가 활동 범위 안에 들게 당긴다."""
        fx, fy = self._foot(pet)
        self.fx, self.fy = fx - self.off[0], fy - self.off[1]
        self.run, self.off = 0.0, (0, 0)
        if self.stat == "spe":
            try:
                x1, _y1, x2, _y2 = pet.ov.area()
                m = pet.ov.settings.get("areaMargin", 4)
                ax = getattr(pet, "ax", pet.fw / 2.0)
                lo = x1 + m + ax + self.half(pet)
                hi = x2 - m - (pet.fw - ax) - self.half(pet)
                if lo <= hi and not lo <= self.fx <= hi:
                    self.fx = min(max(self.fx, lo), hi)
                    self._put(pet, self.fx, self.fy)
            except Exception:                               # noqa: BLE001
                pass
        self._at = (pet.x, pet.y)

    def _put(self, pet, fx, fy):
        """발을 (fx, fy) 에 두는 창 자리로 옮긴다. 자리가 같으면 안 옮긴다 (맥 CPU)."""
        x = fx - getattr(pet, "ax", pet.fw / 2.0)
        y = fy - getattr(pet, "ay", pet.fh / 2.0)
        if (x, y) != (pet.x, pet.y):
            pet.x, pet.y = x, y
            pet.place()

    def update(self, pet, ms):
        foot = self._foot(pet)
        want = (self.fx + self.run + self.off[0], self.fy + self.off[1])
        if abs(foot[0] - want[0]) > 1 or abs(foot[1] - want[1]) > 1:
            self._anchor(pet)              # 사용자가 끌어 옮겼다 - 거기가 새 닻
        pet.advance(ms)
        if pet.once:
            self._at = (pet.x, pet.y)
            return                         # 깡충 같은 한 번짜리 동작 중 (Pet.play 가 발을 붙들고 있다)
        if pet.anim_name != self.pose:
            pet.play(self.pose)
        self.t += ms
        dx = dy = 0
        s = self.stat
        if s == "spe":
            pet.state = "walk"
            speed = float(pet.ov.settings.get("walkSpeed", 1.0)) * RUN_SPEED
            nr = self.run + self.dir * speed
            if abs(nr) > self.half(pet):
                self.dir = -self.dir
                pet.turn_to(self.dir, 0)
                nr = self.run
            pet.walked += abs(nr - self.run)
            self.run = nr
        elif s == "atk":
            if (self.t // LIFT_MS) % 2:
                dy = -LIFT_PX
        elif s == "hp":
            want_face = LEFT if (self.t // TURN_MS) % 2 else RIGHT
            if pet.facing != want_face and want_face in getattr(pet, "photos", {}):
                pet.facing = want_face
                pet.redraw()
            if self.t - self.last_hop >= HOP_MS:
                self.last_hop = self.t
                if pet.anim_for("Hop") is not None:
                    pet.play("Hop", once=True)
                    self._at = (pet.x, pet.y)
                    return
        elif s == "def":
            ph = self.t % SHAKE_EVERY
            if ph < SHAKE_MS:
                dx = SHAKE_PX if (ph // 50) % 2 else -SHAKE_PX
        self.off = (dx, dy)
        self._put(pet, self.fx + self.run + dx, self.fy + dy)
        self._at = (pet.x, pet.y)

    def stop(self, pet):
        """원래대로: 들었던 · 떨던 몸을 닻에 내려놓고 다시 스스로 돌아다니게 한다."""
        if getattr(pet, "drive", None) is self:
            pet.drive = None
        pet.state = "idle"
        pet.timer = random.randint(20, 60)
        try:
            pet.play(pet.rest_anim())
            self._put(pet, self.fx + self.run, self.fy)
        except Exception:                                   # noqa: BLE001
            pass


# ---------------------------------------------------------------- 소품 그림
_PROPS = {
    "atk": ({"P": (84, 88, 104), "b": (170, 174, 186)},          # 아령
            ["........", "PP....PP", "PP....PP", "PPbbbbPP", "PP....PP", "PP....PP", "........", "........"]),
    "spa": ({"C": (66, 110, 210), "w": (245, 242, 230)},          # 펼친 책
            ["........", "CCC..CCC", "CwwCCwwC", "CwwCCwwC", "CwwCCwwC", "CCCCCCCC", "........", "........"]),
    "spe": ({"R": (226, 72, 64), "w": (240, 240, 240)},           # 운동화
            ["........", "........", "..RR....", "..RRR...", "..RRRRR.", ".RRRRRRR", ".wwwwwww", "........"]),
    "hp": ({"G": (72, 186, 110), "g": (190, 240, 200)},           # 머리띠
           ["........", "........", "GGGGGGGG", "GgGgGgGG", "GGGGGGGG", "........", "........", "........"]),
    "def": ({"S": (120, 140, 168), "h": (210, 222, 236)},         # 방패
            [".SSSSSS.", ".ShhhhS.", ".ShSShS.", ".SSSSSS.", "..SSSS..", "..SSSS..", "...SS...", "........"]),
    "spd": ({"Y": (255, 214, 70)},                                # 반짝임
            ["...Y....", "...Y....", "..YYY...", "YYYYYYY.", "..YYY...", "...Y....", "...Y....", "........"]),
}


def prop_image(stat, px):
    """그 능력의 소품 (px x px, 투명 바탕)."""
    colors, rows = _PROPS.get(stat, _PROPS["spd"])
    im = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in colors:
                im.putpixel((x, y), colors[ch] + (255,))
    return im.resize((int(px), int(px)), Image.NEAREST)


# ---------------------------------------------------------------- 시간표
class Tag(object):
    """도트 밑의 작은 창: [소품] 동작 mm:ss. 집중하는 동안 그 도트의 이름표 자리를 대신한다."""

    FOLLOW_MS = 120

    def __init__(self, root, pet, stat):
        self.root, self.pet, self.stat = root, pet, stat
        self.act = (F.act_of(stat) or ("?", "?"))[0]
        self._pos = None
        self._job = None
        self.dead = False
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        try:
            self.win.attributes("-alpha", 0.92)
        except Exception:                                   # noqa: BLE001
            pass
        self.win.configure(bg=U.TIP_BG)
        self.img = ImageTk.PhotoImage(prop_image(stat, max(12, int(U.h(16)))))
        self.label = tk.Label(self.win, image=self.img, compound="left", text=self.act, bg=U.TIP_BG,
                              fg=U.TIP_FG, font=U.FONT_TIP, padx=6, pady=1)
        self.label.pack()
        PLAT.raise_above(self.win)
        self._hide_name()
        self._loop()

    def _hide_name(self):
        w = getattr(self.pet, "name_win", None)
        if w is not None:
            try:
                w.withdraw()
            except Exception:                               # noqa: BLE001
                pass

    def set(self, left_sec, today_ev=None, daily_ev=None):
        """남은 초를 적는다 (None 이면 동작 이름만)."""
        if left_sec is None:
            text = self.act
        else:
            left = max(0, int(left_sec))
            text = "%s  %02d:%02d" % (self.act, left // 60, left % 60)
        if text != self.label.cget("text"):
            self.label.configure(text=text)
            self._pos = None
            self.follow()

    def follow(self):
        """도트 밑 가운데로. 화면(작업 영역) 아래로 넘치면 도트 위로. 자리가 바뀌었을 때만 옮긴다."""
        if self.dead:
            return
        p = self.pet
        try:
            w = self.win.winfo_reqwidth()
            h = self.win.winfo_reqheight()
            cx = p.x + getattr(p, "ax", p.fw / 2.0)
            x = int(round(cx - w / 2.0))
            y = int(p.y + p.fh + 2)
            try:
                _x1, _y1, _x2, y2 = p.ov.area()
                if y + h > y2:
                    y = int(p.y) - h - 2
            except Exception:                               # noqa: BLE001
                pass
            if (x, y) != self._pos:
                self._pos = (x, y)
                self.win.geometry("+%d+%d" % (x, y))
        except Exception:                                   # noqa: BLE001
            pass

    def _loop(self):
        if self.dead:
            return
        self.follow()
        self._job = self.root.after(self.FOLLOW_MS, self._loop)

    def destroy(self):
        if self.dead:
            return
        self.dead = True
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        w = getattr(self.pet, "name_win", None)
        if w is not None and getattr(self.pet.ov, "names_visible", lambda: False)():
            try:
                PLAT.show_again(w)
            except Exception:                               # noqa: BLE001
                pass
