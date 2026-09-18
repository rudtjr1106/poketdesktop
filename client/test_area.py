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


def ev(x, y):
    e = types.SimpleNamespace()
    e.x, e.y = x, y
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
    ox, oy = p.ox, p.oy
    drag(p, 100, 120, 500, 420)
    chk("그린 사각형이 절대 좌표로 온다",
        p.result == (ox + 100, oy + 120, ox + 500, oy + 420), p.result)
    chk("  창이 닫힌다", not p.win.winfo_exists())

    p = ui_area.AreaPicker(root)
    root.update()
    drag(p, 600, 500, 200, 150)
    chk("거꾸로 끌어도 같은 사각형",
        p.result == (ox + 200, oy + 150, ox + 600, oy + 500), p.result)

    print("\n=== 너무 작게 그리면")
    p = ui_area.AreaPicker(root)
    root.update()
    drag(p, 100, 100, 100 + ui_area.MIN_W - 20, 100 + ui_area.MIN_H - 20)
    chk("답을 안 준다", p.result is None, p.result)
    chk("  창이 안 닫힌다 (다시 그릴 수 있다)", p.win.winfo_exists())
    chk("  까닭을 적는다", "작습니다" in p.note.cget("text"), p.note.cget("text"))
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
        chk("  올리는 것은 덮개 창", all(t == str(p.win) for t in seen), seen[:2])
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
