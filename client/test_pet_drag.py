# -*- coding: utf-8 -*-
"""포켓몬을 마우스로 들어서 옮기기 (1.9.1, 설정 petDrag).

    python client/test_pet_drag.py

**창을 실제로 만든다.** 가짜 도트 한 장으로 Overlay 에 포켓몬·알·야생을
세우고, Tk 에 '눌렀다 · 끌었다 · 뗐다' 를 넣어 본다. 못 박는 것:

  1. 설정이 꺼져 있으면(기본) 예전과 똑같다 - 아무리 끌어도 안 움직인다.
  2. 켜면 커서를 따라온다. 잡은 자리가 그대로 손에 붙어 있다.
  3. 조금 움직인 것(5px 미만)은 끈 것으로 치지 않는다 - 그냥 누르기·두 번
     누르기가 끌기로 바뀌면 예전에 뺐던 그 불편이 돌아온다.
  4. 활동 영역 밖으로는 못 나간다. 이름표도 같이 따라온다.
  5. 배틀 중인 포켓몬과 야생은 못 옮긴다. 알은 옮길 수 있다 (부화 중 빼고).
  6. 내려놓으면 그 자리에서 다시 걷는다. 맥에서 '뗐다' 가 안 와도 풀린다.
"""
import os
import shutil
import sys
import tempfile
import time

HOME = tempfile.mkdtemp(prefix="poket-pet-drag-")
os.environ["POKET_HOME"] = HOME

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                       # noqa: E402

from PIL import Image                                      # noqa: E402

from poketdesktop import config, eggs_ui, sprites, wild_ui  # noqa: E402
from poketdesktop import overlay as OV                     # noqa: E402
from poketdesktop import platform_os as PLAT               # noqa: E402
from poketdesktop import ui_common as U                    # noqa: E402
from poketdesktop import ui_settings                       # noqa: E402

OK = FAIL = 0
ERRORS = []
AREA = (200, 150, 900, 650)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


class Ev(object):
    """Tk 이 주는 마우스 이벤트에서 우리가 보는 것만."""

    def __init__(self, x, y):
        self.x_root, self.y_root = int(x), int(y)
        self.x = self.y = 3


def dot_path():
    """배틀 도트 한 장 (노란 네모). load_battle_walker 가 읽는다."""
    p = os.path.join(HOME, "dot.png")
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    for x in range(8, 32):
        for y in range(6, 36):
            im.putpixel((x, y), (240, 200, 40, 255))
    im.save(p)
    return p


def mon(pid, name="피카츄"):
    return {"id": pid, "num": 25, "shiny": False,
            "info": {"name": name, "species": name, "level": 12, "types": ["전기"]}}


def press_drag(pet, dx, dy, steps=6, release=True):
    """도트 한가운데를 누르고 (dx, dy) 만큼 끈다. 누른 자리를 돌려준다."""
    sx, sy = int(pet.x + pet.fw // 2), int(pet.y + pet.fh // 2)
    pet.on_press(Ev(sx, sy))
    for i in range(1, steps + 1):
        pet.on_motion(Ev(sx + dx * i / float(steps), sy + dy * i / float(steps)))
    if release:
        pet.on_release(Ev(sx + dx, sy + dy))
    return sx, sy


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda *a: ERRORS.append(a)
    U.init_fonts(root)
    U.apply_theme(root)
    settings = dict(config.DEFAULTS)
    settings["areaRect"] = list(AREA)
    settings["showNames"] = True
    ov = OV.Overlay(root, settings)
    # 화면 크기와 상관없이 같은 영역에서 본다 (작은 CI 화면에서도 같은 숫자)
    ov.area = lambda: AREA
    path = dot_path()
    ov.paths[(25, False)] = path
    m = settings["areaMargin"]
    # **진짜 마우스를 보지 않게 한다.** 맥에서는 눌린 단추와 커서 자리를 직접
    # 묻는데(follow_pointer), 검사를 돌리는 사람이 그때 마우스를 쓰고 있으면
    # 결과가 달라진다. 윈도우처럼 '모른다' 로 두고, 맥의 길은 아래에서 따로 본다.
    real_down, real_xy = PLAT.mouse_buttons_down, root.winfo_pointerxy
    real_track = PLAT.NEEDS_HIT_TRACKING
    PLAT.mouse_buttons_down = lambda: 0
    PLAT.NEEDS_HIT_TRACKING = False

    print("=== 기본값 ===")
    chk("기본은 꺼져 있다", config.DEFAULTS.get("petDrag") is False)
    chk("옛 설정 파일에도 꺼진 채로 채워진다", config.load_settings().get("petDrag") is False)

    ov.sync([mon(1), mon(2, "꼬부기")], {})
    root.update()
    p = ov.pets[1]
    p.x, p.y = 400.0, 300.0
    p.place()
    root.update()

    print("\n=== 꺼져 있으면 예전과 같다 ===")
    chk("옮길 수 없다고 답한다", p.can_drag() is False)
    press_drag(p, 150, 80, release=False)
    chk("끌어도 안 움직인다", (p.x, p.y) == (400.0, 300.0), (p.x, p.y))
    chk("누르고 있는 동안은 서 있다", p.state == "held" and p.dragging is False)
    p.on_release(Ev(0, 0))
    chk("떼면 다시 돌아다닌다", p.state == "idle" and 20 <= p.timer <= 60, (p.state, p.timer))

    print("\n=== 켜면 따라온다 ===")
    settings["petDrag"] = True
    chk("옮길 수 있다고 답한다 (떠 있는 도트에 바로 통한다)", p.can_drag() is True)
    p.x, p.y = 400.0, 300.0
    p.place()
    press_drag(p, 150, 80, release=False)
    chk("끈 만큼 옮겨진다", (round(p.x), round(p.y)) == (550, 380), (p.x, p.y))
    chk("들고 있는 중이다", p.dragging is True and p.state == "held")
    root.update()
    geo = p.win.geometry().split("+")[1:]
    chk("창도 그 자리에 있다", [int(v) for v in geo] == [550, 380], geo)
    chk("이름표가 같이 따라온다", p.name_win is not None
        and int(p.name_win.geometry().split("+")[1]) == 550, p.name_win.geometry())
    p.update(33)
    chk("들고 있는 동안은 제 발로 안 걷는다", (round(p.x), round(p.y)) == (550, 380), (p.x, p.y))
    p.on_release(Ev(0, 0))
    chk("내려놓으면 그 자리에 선다", (round(p.x), round(p.y)) == (550, 380)
        and p.state == "idle" and p.dragging is False and p._grab is None, (p.x, p.y, p.state))
    chk("  조금 더 서 있다가 걷는다", 70 <= p.timer <= 150, p.timer)

    print("\n=== 잡은 자리가 손에 붙어 있다 ===")
    p.x, p.y = 300.0, 300.0
    p.place()
    p.on_press(Ev(302, 304))                 # 왼쪽 위 귀퉁이를 잡았다
    p.on_motion(Ev(502, 404))
    chk("귀퉁이를 잡으면 귀퉁이가 커서에 붙는다", (round(p.x), round(p.y)) == (500, 400), (p.x, p.y))
    # 들고 있는 동안 칸이 달라져도(동작이 바뀌면 fw/fh/ax/ay 가 바뀐다) 손에서 안 미끄러진다
    cx, cy = p.x + p.ax, p.y + p.ay
    p.ax, p.ay = p.ax + 9, p.ay + 5
    p.x, p.y = cx - p.ax, cy - p.ay          # play() 가 하는 것과 같다 (기준점은 그대로)
    p.on_motion(Ev(503, 404))
    chk("  동작이 바뀌어도 기준점이 안 튄다", (round(p.x + p.ax), round(p.y + p.ay))
        == (round(cx) + 1, round(cy)), (p.x + p.ax, p.y + p.ay, cx, cy))
    p.on_release(Ev(503, 404))

    print("\n=== 조금 움직인 것은 끈 것이 아니다 ===")
    p.x, p.y = 400.0, 300.0
    p.place()
    sx, sy = int(p.x + 10), int(p.y + 10)
    p.on_press(Ev(sx, sy))
    p.on_motion(Ev(sx + 3, sy - 4))
    chk("4px 까지는 그대로", (p.x, p.y) == (400.0, 300.0) and p.dragging is False, (p.x, p.y))
    p.on_release(Ev(sx + 3, sy - 4))
    chk("  그냥 누른 것으로 끝난다", 20 <= p.timer <= 60, p.timer)
    p.on_press(Ev(sx, sy))
    p.on_motion(Ev(sx + OV.DRAG_START, sy))
    chk("%dpx 부터 든 것으로 친다" % OV.DRAG_START, p.dragging is True
        and round(p.x) == 400 + OV.DRAG_START, (p.x, p.dragging))
    p.on_motion(Ev(sx + 1, sy))
    chk("  한 번 들면 되돌아와도 계속 따라온다", round(p.x) == 401, p.x)
    p.on_release(Ev(sx + 1, sy))

    print("\n=== 활동 영역 밖으로는 못 나간다 ===")
    p.x, p.y = 400.0, 300.0
    p.place()
    press_drag(p, 5000, 5000, release=False)
    chk("오른쪽 아래 끝에서 멈춘다", (p.x, p.y) == (AREA[2] - p.fw - m, AREA[3] - p.fh - m), (p.x, p.y))
    p.on_motion(Ev(-5000, -5000))
    chk("왼쪽 위 끝에서 멈춘다", (p.x, p.y) == (AREA[0] + m, AREA[1] + m), (p.x, p.y))
    p.on_release(Ev(-5000, -5000))

    print("\n=== 못 옮기는 것 ===")
    p.x, p.y = 400.0, 300.0
    p.place()
    p.battling = True
    press_drag(p, 120, 60)
    chk("배틀 중인 포켓몬", (p.x, p.y) == (400.0, 300.0), (p.x, p.y))
    p.battling = False
    sx, sy = int(p.x + 10), int(p.y + 10)
    p.on_press(Ev(sx, sy))
    p.on_motion(Ev(sx + 40, sy))
    p.battling = True                         # 들고 있는데 배틀이 시작됐다
    p.on_motion(Ev(sx + 300, sy))
    chk("들고 있다가 배틀이 시작되면 거기서 멈춘다", round(p.x) == 440, p.x)
    p.battling = False
    p.on_release(Ev(sx + 300, sy))

    class Ctl(object):
        """WildPet 이 쓰는 것만 (app.overlay, app.battle)."""

        def __init__(self):
            self.app = type("A", (), {"overlay": ov, "battle": None, "root": root})()

    w = ov.make(dict(mon(-1, "구구"), id=-1), cls=lambda o, mm, an: wild_ui.WildPet(Ctl(), mm, an))
    w._go_battle = lambda: None
    w.x, w.y = 500.0, 400.0
    w.place()
    press_drag(w, 100, 100)
    chk("야생 포켓몬", (w.x, w.y) == (500.0, 400.0) and w.can_drag() is False, (w.x, w.y))
    w._cancel_battle_job()
    w.state = "held"
    w._down = (10, 10)
    try:
        w.on_release(None)
        chk("야생: 맥이 대신 풀어 줄 때도 터지지 않는다", w.state == "idle"
            and getattr(w, "_battle_job", None) is None, (w.state,))
    except Exception as e:                                  # noqa: BLE001
        chk("야생: 맥이 대신 풀어 줄 때도 터지지 않는다", False, repr(e))
    w.destroy()

    print("\n=== 알 ===")
    anim = sprites.load_animation(path, 40, 0.5, 4.0)
    egg = eggs_ui.EggPet(ov, {"id": 7, "kind": "legendary", "name": "전설의 포켓몬 알",
                              "gotSec": 10, "needSec": 1000, "leftSec": 990}, anim)
    ov.eggs[7] = egg
    egg.x, egg.y = 300.0, 500.0
    egg.place()
    try:
        egg.on_press(None)
        chk("알: 이벤트 없이 눌러도 그대로 (말풍선만)", egg._grab is None and egg.state == "idle")
    except Exception as e:                                  # noqa: BLE001
        chk("알: 이벤트 없이 눌러도 그대로 (말풍선만)", False, repr(e))
    egg.hide_tip()
    press_drag(egg, 200, -100, release=False)
    chk("알도 옮겨진다", (round(egg.x), round(egg.y)) == (500, 400), (egg.x, egg.y))
    egg.shake([4, -4, 2, -2])                # 들고 있는데 흔들릴 차례가 왔다
    egg.update(33)
    chk("들고 있는 동안에는 안 흔들린다", round(egg.x) == 500, egg.x)
    egg.on_motion(Ev(int(egg.x + egg.fw // 2) + 60, int(egg.y + egg.fh // 2)))
    egg.on_release(Ev(0, 0))
    x_drop = egg.x
    for _ in range(8):
        egg.update(33)
    chk("내려놓은 자리에서 마저 흔들린다 (옛 자리로 안 튕긴다)", egg.x == x_drop
        and egg._shake is None, (egg.x, x_drop))
    egg.hatching = True
    press_drag(egg, 100, 0)
    chk("부화 중인 알은 못 옮긴다", egg.x == x_drop, (egg.x, x_drop))
    egg.hatching = False
    settings["petDrag"] = False
    press_drag(egg, 100, 0)
    chk("설정을 끄면 알도 안 옮겨진다", egg.x == x_drop, (egg.x, x_drop))
    settings["petDrag"] = True

    print("\n=== 맥: '움직였다'·'뗐다' 가 안 올 때 ===")
    OV.PLAT.mouse_buttons_down = lambda: 1
    try:
        p.x, p.y = 400.0, 300.0
        p.place()
        sx, sy = int(p.x + 10), int(p.y + 10)
        p.on_press(Ev(sx, sy))
        ov.root.winfo_pointerxy = lambda: (sx + 90, sy + 40)
        p.update(33)
        chk("단추가 눌려 있으면 커서를 직접 좇는다", (round(p.x), round(p.y)) == (490, 340), (p.x, p.y))
        OV.PLAT.mouse_buttons_down = lambda: 0
        ov.root.winfo_pointerxy = lambda: (sx + 300, sy + 300)
        p.update(33)
        chk("단추 상태를 모르면(윈도우) 좇지 않는다", (round(p.x), round(p.y)) == (490, 340), (p.x, p.y))
        p.on_release(None)                    # app._unstick 이 이렇게 부른다
        chk("이벤트 없이 풀어도 내려놓은 것이 된다", p.state == "idle" and p._grab is None
            and 70 <= p.timer <= 150, (p.state, p.timer))
        # 풀린 뒤에는 다른 데를 눌러도 따라오지 않는다
        OV.PLAT.mouse_buttons_down = lambda: 1
        p.update(33)
        chk("풀린 뒤에는 커서를 안 좇는다", abs(p.x - 490) < 20 and abs(p.y - 340) < 20, (p.x, p.y))

        # 알은 app._unstick 이 보지 않는다 - 스스로 푼다
        eggs_ui.PLAT.NEEDS_HIT_TRACKING = True
        try:
            egg.x, egg.y = 300.0, 500.0
            egg.place()
            ex, ey = int(egg.x + 5), int(egg.y + 5)
            egg.on_press(Ev(ex, ey))
            egg.hide_tip()
            ov.root.winfo_pointerxy = lambda: (ex + 50, ey)
            egg.update(33)
            chk("알도 커서를 좇는다", round(egg.x) == 350, egg.x)
            OV.PLAT.mouse_buttons_down = lambda: 0
            ov.root.winfo_pointerxy = lambda: (ex + 400, ey)
            egg.update(33)
            chk("단추를 뗐으면 알이 스스로 풀린다", egg._grab is None and egg.dragging is False
                and round(egg.x) == 350, (egg._grab, egg.x))
            OV.PLAT.mouse_buttons_down = lambda: 1
            egg.update(33)
            chk("  그 뒤에 다른 데를 눌러도 안 따라온다", round(egg.x) in range(346, 355), egg.x)
        finally:
            eggs_ui.PLAT.NEEDS_HIT_TRACKING = False
    finally:
        OV.PLAT.mouse_buttons_down = lambda: 0
        ov.root.winfo_pointerxy = real_xy

    print("\n=== Tk 이 주는 이벤트로 (바인딩이 걸려 있는가) ===")
    q = ov.pets[2]
    q.x, q.y = 300.0, 250.0
    q.place()
    root.update()
    binds = q.label.bind()
    chk("끌기가 걸려 있다", "<B1-Motion>" in binds, binds)
    calls = []
    q.drag_to = lambda px, py: calls.append((px, py))
    q.label.event_generate("<B1-Motion>", rootx=640, rooty=420, x=5, y=5, when="now")
    root.update()
    chk("움직이면 화면 좌표로 넘어온다", calls == [(640, 420)], calls)
    del q.drag_to

    print("\n=== 설정 창 ===")

    class FakeApp(object):
        def __init__(self):
            self.root = root
            self.settings = settings
            self.overlay = ov
            self.wild = None
            self.trays = 0

        def refresh_tray(self):
            self.trays += 1

        def set_size(self, px):
            pass

    settings["petDrag"] = False
    app = FakeApp()
    sw = ui_settings.SettingsWindow(app)
    root.update()
    chk("손잡이가 꺼진 채로 보인다", sw.drag.get() is False)
    texts = []

    def walk(wd):
        for c in wd.winfo_children():
            if isinstance(c, (tk.Checkbutton, tk.Label)):
                texts.append(c.cget("text"))
            walk(c)
    walk(sw.win)
    chk("'포켓몬 들어서 옮기기' 가 있다", "포켓몬 들어서 옮기기" in texts)
    chk("  무엇을 못 옮기는지 적혀 있다", any("야생 포켓몬과 배틀" in t for t in texts))
    sw.drag.set(True)
    sw._toggle_plain("petDrag", sw.drag)
    chk("켜면 설정에 적힌다", settings["petDrag"] is True
        and config.load_settings().get("petDrag") is True)
    chk("  떠 있는 포켓몬에 바로 통한다", p.can_drag() is True)
    sw.reset()
    chk("'기본값으로' 는 다시 끈다", settings["petDrag"] is False and p.can_drag() is False)
    sw.close()

    ov.clear()
    root.update()
    PLAT.mouse_buttons_down, PLAT.NEEDS_HIT_TRACKING = real_down, real_track
    chk("Tk 콜백에서 예외가 없다", not ERRORS, ERRORS[:1])
    root.destroy()
    shutil.rmtree(HOME, ignore_errors=True)
    print("\n  합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
