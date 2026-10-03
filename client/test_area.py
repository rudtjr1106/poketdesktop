# -*- coding: utf-8 -*-
"""돌아다닐 영역을 화면에 직접 그리는 기능. 진짜 Tk 로 확인한다.

    python client/test_area.py

  1. 끌어서 그린 사각형이 **절대 좌표**로 돌아온다 (모니터가 둘이면 음수도 된다).
     거꾸로 끌어도(오른쪽 아래 -> 왼쪽 위) 같은 사각형이다.
  2. 너무 작게 그리면 창을 닫지 않고 다시 그리라고 적는다.
  3. Esc 로 그만두면 None.
  4. 그린 영역을 설정에 넣으면 Overlay.area 가 그걸 쓴다. 화면 밖으로 나간
     영역(모니터를 뺐다)은 화면 안으로 당기고, 그래도 작으면 기본 영역으로 돌아간다.
  5. 영역을 바꾸면 밖에 있던 포켓몬이 안으로 들어온다.
  6. (1.9.1) **모니터마다 덮개를 하나씩** 깔고, 답은 포인터의 화면 좌표 그대로다
     (덮개 안의 좌표 + 덮개 자리가 아니다 - 배율이 다른 모니터·밀린 창에서 어긋난다).
  7. (1.9.1) 모니터가 둘 이상이면 '왼쪽 화면 / 오른쪽 화면' 을 통째로 고를 수 있다.
"""
import os
import sys
import tempfile
import time
import types

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-area-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import config                             # noqa: E402
from poketdesktop import overlay as OV                      # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_area                            # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def ev(x, y, win_x=None, win_y=None):
    """화면 좌표 (x, y) 에서 난 마우스 사건. 창 안의 좌표(e.x, e.y)는 일부러
    엉뚱한 값을 준다 - 그걸 쓰면 검사가 깨지도록."""
    e = types.SimpleNamespace()
    e.x_root, e.y_root = x, y
    e.x = -9999 if win_x is None else win_x
    e.y = -9999 if win_y is None else win_y
    return e


def drag(p, x1, y1, x2, y2):
    p._press(ev(x1, y1))
    p._drag(ev((x1 + x2) // 2, (y1 + y2) // 2))
    p._release(ev(x2, y2))


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)

    print("=== 끌어서 그리기")
    p = ui_area.AreaPicker(root)
    root.update()
    drag(p, 100, 120, 500, 420)
    chk("그린 사각형이 포인터의 화면 좌표 그대로 온다 (창 안 좌표를 안 쓴다)",
        p.result == (100, 120, 500, 420), p.result)
    chk("  창이 닫힌다", not p.win.winfo_exists())

    p = ui_area.AreaPicker(root)
    root.update()
    drag(p, 600, 500, 200, 150)
    chk("거꾸로 끌어도 같은 사각형", p.result == (200, 150, 600, 500), p.result)

    print("\n=== 너무 작게 그리면")
    p = ui_area.AreaPicker(root)
    root.update()
    drag(p, 100, 100, 100 + ui_area.MIN_W - 20, 100 + ui_area.MIN_H - 20)
    chk("답을 안 준다", p.result is None, p.result)
    chk("  창이 안 닫힌다 (다시 그릴 수 있다)", p.win.winfo_exists())
    chk("  까닭을 적는다", "작습니다" in p.panes[0]["note"].cget("text"),
        p.panes[0]["note"].cget("text"))
    drag(p, 100, 100, 100 + ui_area.MIN_W, 100 + ui_area.MIN_H)
    chk("  제대로 그리면 받는다", p.result is not None, p.result)

    print("\n=== 그리는 동안 덮개가 도트에 안 가린다")
    seen = []
    real = ui_area.PLAT.keep_on_top
    ui_area.PLAT.keep_on_top = lambda w: seen.append(str(w))
    try:
        p = ui_area.AreaPicker(root)
        root.update()
        n0 = len(seen)
        end = time.time() + (ui_area.TOP_EVERY_MS / 1000.0) * 2.5
        while time.time() < end:
            root.update()
            time.sleep(0.02)
        chk("덮개가 스스로 계속 맨 위로 올라온다 (%dms 마다)" % ui_area.TOP_EVERY_MS,
            len(seen) - n0 >= 1, len(seen) - n0)
        chk("  올리는 것은 덮개 창", set(seen) <= set(str(x["win"]) for x in p.panes), seen[:2])
        p._cancel()
        after = len(seen)
        for _ in range(20):
            root.update()
            time.sleep(0.02)
        chk("  닫으면 멈춘다", len(seen) == after, (after, len(seen)))
    finally:
        ui_area.PLAT.keep_on_top = real

    print("\n=== 그만두기")
    p = ui_area.AreaPicker(root)
    root.update()
    p._cancel()
    chk("Esc 로 그만두면 None", p.result is None, p.result)
    chk("  창이 닫힌다", not p.win.winfo_exists())

    print("\n=== 모니터가 둘일 때 (1.9.1)")
    # 왼쪽에 1280x1024 모니터를 하나 더 붙인 꼴. 왼쪽 것은 x 가 음수다.
    two = [(0, 0, 1440, 900), (-1280, 0, 0, 1024)]
    real_screens = ui_area.PLAT.screens
    ui_area.PLAT.screens = lambda w, h: list(two)
    try:
        p = ui_area.AreaPicker(root)
        root.update()
        chk("모니터마다 덮개가 하나씩", len(p.panes) == 2
            and [(x["ox"], x["oy"], x["w"], x["h"]) for x in p.panes]
            == [(0, 0, 1440, 900), (-1280, 0, 1280, 1024)],
            [(x["ox"], x["oy"], x["w"], x["h"]) for x in p.panes])
        chk("안내는 화면마다 있고 어느 모니터에든 그릴 수 있다고 적는다",
            all("어느 모니터" in x["note"].cget("text") for x in p.panes))
        p._press(ev(-900, 200))
        p._drag(ev(-300, 700))
        left, main = p.panes[1], p.panes[0]
        chk("왼쪽 모니터에 그리면 그 덮개에는 제 좌표로 그려진다",
            [int(v) for v in left["cv"].coords(left["rect"])] == [380, 200, 980, 700],
            left["cv"].coords(left["rect"]))
        chk("  주 화면 덮개에는 화면 밖(왼쪽)에 놓인다 (안 보인다)",
            [int(v) for v in main["cv"].coords(main["rect"])] == [-900, 200, -300, 700],
            main["cv"].coords(main["rect"]))
        p._release(ev(-300, 700))
        chk("왼쪽 모니터의 사각형이 음수 좌표로 온다", p.result == (-900, 200, -300, 700), p.result)
        chk("  덮개가 전부 닫힌다", not any(x["win"].winfo_exists() for x in p.panes))
        p = ui_area.AreaPicker(root)
        root.update()
        drag(p, -400, 300, 500, 800)
        chk("두 모니터에 걸쳐 그릴 수 있다", p.result == (-400, 300, 500, 800), p.result)
        p = ui_area.AreaPicker(root)
        root.update()
        p._cancel()
        chk("그만두면 덮개가 전부 닫힌다", p.result is None
            and not any(x["win"].winfo_exists() for x in p.panes))
    finally:
        ui_area.PLAT.screens = real_screens

    print("\n=== 화면을 통째로 고르기 (1.9.1)")
    works = [(0, 25, 1440, 830), (-1280, 0, 0, 984)]
    got = OV.screen_choices(two, works)
    chk("둘이 나란하면 '왼쪽 화면 / 오른쪽 화면' (놓인 자리대로)",
        got == [("왼쪽 화면", (-1280, 0, 0, 984)), ("오른쪽 화면", (0, 25, 1440, 830))], got)
    got = OV.screen_choices([(0, 0, 1920, 1080), (0, -1080, 1920, 0)],
                            [(0, 0, 1920, 1040), (0, -1080, 1920, 0)])
    chk("위아래로 쌓았으면 '위 화면 / 아래 화면'",
        [n for n, _r in got] == ["위 화면", "아래 화면"] and got[0][1] == (0, -1080, 1920, 0), got)
    got = OV.screen_choices([(0, 0, 1920, 1080), (1920, 0, 3840, 1080), (-1920, 0, 0, 1080)],
                            [(0, 0, 1920, 1040), (1920, 0, 3840, 1080), (-1920, 0, 0, 1080)])
    chk("셋이면 왼쪽부터 '화면 1, 2, 3'", [n for n, _r in got] == ["화면 1", "화면 2", "화면 3"]
        and [r[0] for _n, r in got] == [-1920, 0, 1920], got)
    chk("한 대면 고를 것이 없다", OV.screen_choices([(0, 0, 1440, 900)], [(0, 25, 1440, 830)]) == [])
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    scr, wrk = PLAT.screens(sw, sh), PLAT.screen_works(sw, sh)
    chk("이 컴퓨터: 화면 목록의 첫째가 주 화면 (0, 0 을 품는다)",
        len(scr) >= 1 and scr[0][0] <= 0 < scr[0][2] and scr[0][1] <= 0 < scr[0][3], scr)
    chk("이 컴퓨터: 화면마다 작업 영역이 있고 그 화면 안이다", len(wrk) == len(scr) and all(
        s_[0] <= w[0] < w[2] <= s_[2] and s_[1] <= w[1] < w[3] <= s_[3] for s_, w in zip(scr, wrk)),
        (scr, wrk))
    chk("이 컴퓨터: 모니터 전부를 아우르는 사각형이 화면들을 다 품는다", all(
        v[0] <= s_[0] and v[1] <= s_[1] and s_[2] <= v[2] and s_[3] <= v[3]
        for v in [PLAT.virtual_screen(sw, sh)] for s_ in scr))

    print("\n=== 설정 화면의 화면 고르기 단추 (1.9.1)")
    from poketdesktop import ui_settings

    class FakeApp(object):
        def __init__(self, choices):
            self.root = root
            self.settings = dict(config.DEFAULTS)
            self.overlay = None
            self.wild = None
            self.choices = choices
            self.picked = []

        def screen_choices(self):
            return self.choices

        def set_area_screen(self, rect, name=""):
            self.picked.append((name, tuple(rect)))
            self.settings["areaRect"] = list(rect)

        def refresh_tray(self):
            pass

        def set_size(self, px):
            pass

    app2 = FakeApp([("왼쪽 화면", (-1280, 0, 0, 984)), ("오른쪽 화면", (0, 25, 1440, 830))])
    sw_ = ui_settings.SettingsWindow(app2)
    root.update()
    chk("모니터가 둘이면 화면마다 단추가 생긴다", [n for n, _r, _b in sw_.screen_btns]
        == ["왼쪽 화면", "오른쪽 화면"], [n for n, _r, _b in sw_.screen_btns])
    sw_._pick_screen(*[(r, n) for n, r, _b in sw_.screen_btns][0])
    chk("누르면 그 화면 전체가 영역이 된다", app2.picked == [("왼쪽 화면", (-1280, 0, 0, 984))]
        and app2.settings["areaRect"] == [-1280, 0, 0, 984], app2.picked)
    chk("  영역 설명이 따라 바뀐다", "1280 x 984" in sw_.area_note.cget("text"),
        sw_.area_note.cget("text"))
    sw_.close()
    app1 = FakeApp([])
    sw_ = ui_settings.SettingsWindow(app1)
    root.update()
    chk("한 대면 단추가 없다", sw_.screen_btns == [])
    sw_.close()

    print("\n=== 설정에 넣으면 그 영역을 쓴다")
    screen = (0, 0, 1920, 1080)
    chk("그린 영역을 그대로 쓴다",
        OV.drawn_area([300, 200, 900, 600], screen) == (300, 200, 900, 600))
    chk("거꾸로 든 값도 바로잡는다",
        OV.drawn_area([900, 600, 300, 200], screen) == (300, 200, 900, 600))
    chk("화면 밖은 화면 안으로 당긴다",
        OV.drawn_area([1500, 800, 3000, 2000], screen) == (1500, 800, 1920, 1080))
    chk("너무 작아지면 없는 것으로 (기본 영역을 쓴다)",
        OV.drawn_area([1900, 1000, 3000, 2000], screen) is None)
    chk("안 정했으면 없는 것", OV.drawn_area(None, screen) is None)
    chk("이상한 값도 없는 것", OV.drawn_area([1, 2], screen) is None)

    s = dict(config.DEFAULTS)
    chk("기본값에는 그린 영역이 없다", s.get("areaRect") is None, s.get("areaRect"))

    def fake_overlay(settings):
        """Overlay 에서 영역 계산만 떼어 온 것."""
        o = types.SimpleNamespace(root=root, settings=settings)
        o._drawn_area = lambda rect, sw, sh: OV.Overlay._drawn_area(o, rect, sw, sh)
        return o

    ov = fake_overlay(s)
    base = OV.Overlay.area(ov)
    s["areaRect"] = [120, 80, 520, 380]
    chk("그린 영역이 있으면 그것을 쓴다",
        OV.Overlay.area(ov) == (120, 80, 520, 380), OV.Overlay.area(ov))
    s["areaRect"] = None
    chk("지우면 다시 오른쪽 아래", OV.Overlay.area(ov) == base, (OV.Overlay.area(ov), base))

    print("\n=== 매 프레임 불려도 화면을 매번 묻지 않는다")
    s["areaRect"] = [120, 80, 520, 380]
    asked = []
    real_vs = OV.PLAT.virtual_screen
    OV.PLAT.virtual_screen = lambda w, h: asked.append(1) or real_vs(w, h)
    try:
        ov2 = fake_overlay(s)
        for _ in range(200):                 # 여섯 마리가 30fps 로 한 초 남짓
            OV.Overlay.area(ov2)
        chk("이백 번 불러도 화면은 한 번만 묻는다", len(asked) == 1, len(asked))
        s["areaRect"] = [200, 100, 700, 500]
        OV.Overlay.area(ov2)
        chk("영역을 바꾸면 바로 다시 잰다", len(asked) == 2, len(asked))
        chk("  바뀐 영역을 쓴다", OV.Overlay.area(ov2) == (200, 100, 700, 500),
            OV.Overlay.area(ov2))
    finally:
        OV.PLAT.virtual_screen = real_vs

    print("\n=== 영역을 바꾸면 포켓몬이 안으로 들어온다")
    s["areaRect"] = [100, 100, 400, 300]
    s["areaMargin"] = 4
    ov.area = lambda: OV.Overlay.area(ov)
    pet = types.SimpleNamespace(ov=ov, x=1500.0, y=900.0, fw=40, fh=40)
    OV.Pet.clamp(pet)
    chk("밖에 있던 포켓몬이 영역 안으로", 100 <= pet.x <= 400 - 40 and 100 <= pet.y <= 300 - 40,
        (pet.x, pet.y))

    root.destroy()
    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
