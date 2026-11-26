# -*- coding: utf-8 -*-
"""이로치 야생의 반짝임 검사 (1.12.1).

    python client/test_shiny_fx.py
    python client/run_as_windows.py client/test_shiny_fx.py

**창을 진짜로 띄운다** (클릭이 통과하는 층). 도트는 x·y·fw·fh 만 가진 가짜다.

## 무엇을 못 박나

  1. 별은 **도트 칸 안**(몸 위)의 서로 다른 자리에서 두 차례 차례로 반짝이고, 커졌다가
     줄어들어 사라진다. 별 크기는 몸집에 맞춘다.
  2. 반짝이는 동안 층에 별이 그려지고(도트 칸 안에), 다 끝나면 층이 닫히고 on_done 이 한 번 불린다.
  3. 도트가 그사이 사라지면(alive 가 거짓) 바로 걷는다.
  4. 색이 다른 야생이 나오면(show_wild) 반짝이고, 보통 야생은 안 반짝인다.
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-shiny-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import shiny_fx                           # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import wild_ui                            # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def pump(root, cond, sec=5.0):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


class Dot(object):
    def __init__(self):
        self.x, self.y, self.fw, self.fh = 300, 300, 64, 64


def plan_part():
    print("=== 별 계획 ===")
    stars = shiny_fx.plan()
    chk("두 차례 열한 개", len(stars) == 11, len(stars))
    first = [x for x in stars if x[0] < shiny_fx.ROUNDS[1][0]]
    second = [x for x in stars if x[0] >= shiny_fx.ROUNDS[1][0]]
    chk("차례 안에서 하나씩 뒤따른다", [x[0] for x in first] == sorted(set(x[0] for x in first))
        and [x[0] for x in second] == sorted(set(x[0] for x in second)), stars)
    chk("**별 자리는 모두 도트 칸 안** (몸 위)", all(0.05 <= u <= 0.95 and 0.05 <= v <= 0.95
                                              for _s, u, v, _k in stars))
    chk("  같은 자리에 두 번 안 뜬다", len(set((u, v) for _s, u, v, _k in stars)) == len(stars))
    chk("커졌다가 줄어든다", shiny_fx.scale_at(0) == 0.0 and shiny_fx.scale_at(shiny_fx.GROW_MS) == 1.0
        and 0 < shiny_fx.scale_at(shiny_fx.GROW_MS + shiny_fx.FADE_MS / 2) < 1
        and shiny_fx.scale_at(-1) is None
        and shiny_fx.scale_at(shiny_fx.GROW_MS + shiny_fx.FADE_MS + 1) is None)
    chk("1.5초 안에 끝난다", shiny_fx.length_ms() <= 1500, shiny_fx.length_ms())
    chk("별 크기는 몸집에 맞춘다 (36px 도트 ~ 큰 도트, 너무 작거나 크지 않게)",
        shiny_fx.star_size(30, 36) < shiny_fx.star_size(40, 48) <= shiny_fx.SIZE_MAX
        and shiny_fx.star_size(8, 8) == shiny_fx.SIZE_MIN and shiny_fx.star_size(300, 300) == shiny_fx.SIZE_MAX,
        (shiny_fx.star_size(30, 36), shiny_fx.star_size(40, 48)))


def play_part(root):
    print("\n=== 한 번 반짝이기 ===")
    area = (0, 0, root.winfo_screenwidth(), root.winfo_screenheight())
    done = []
    t0 = time.time()
    sp = shiny_fx.play(root, area, Dot(), on_done=lambda: done.append(1))
    if sp.layer is None and sp.closed:
        chk("층을 못 열면 그냥 끝낸다 (on_done 한 번)", done == [1], done)
        print("  (이 환경은 클릭 통과 층을 못 연다 - 그리는 검사는 건너뛴다)")
        return
    pump(root, lambda: sp.drawn > 0, 1.0)
    chk("반짝이는 동안 층에 별이 그려진다", sp.drawn > 0 and len(sp.layer.cv.find_all()) > 0, sp.drawn)
    # 별이 도트 칸 위에 있나 (가장자리의 별은 반지름만큼 삐져나올 수 있다)
    d, big = Dot(), shiny_fx.star_size(64, 64) * 1.2 + 2
    ox, oy = sp.layer.to_local(d.x, d.y)
    boxes = [sp.layer.cv.bbox(i) for i in sp.layer.cv.find_all()]
    cx = [((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0) for b in boxes if b]
    chk("  별의 가운데가 모두 도트 칸 안", cx and all(ox <= x <= ox + d.fw and oy <= y <= oy + d.fh for x, y in cx),
        (ox, oy, cx[:3]))
    chk("  별이 도트 칸에서 반지름 넘게 나가지 않는다", all(b[0] >= ox - big and b[2] <= ox + d.fw + big
                                                and b[1] >= oy - big and b[3] <= oy + d.fh + big for b in boxes if b))
    pump(root, lambda: done, 3.0)
    took = time.time() - t0
    chk("다 끝나면 on_done 이 한 번", done == [1], done)
    chk("  제때 끝난다", took < shiny_fx.length_ms() / 1000.0 + 0.6, took)
    chk("  층이 닫혔다", sp.layer is None and sp.closed)

    print("\n=== 도중에 도트가 사라지면 ===")
    gone = {"v": False}
    done2 = []
    sp2 = shiny_fx.play(root, area, Dot(), alive=lambda: not gone["v"], on_done=lambda: done2.append(1))
    pump(root, lambda: sp2.drawn > 0, 1.0)
    gone["v"] = True
    pump(root, lambda: done2, 0.5)
    chk("바로 걷는다", done2 == [1] and sp2.layer is None, (done2, sp2.layer))


class FakeOv(object):
    def __init__(self, root):
        self.root = root

    def area(self):
        return (0, 0, 800, 600)


class FakeApp(object):
    def __init__(self, root):
        self.root = root
        self.overlay = FakeOv(root)
        self.notes = []

    def notify(self, m):
        self.notes.append(m)


def wild_part(root):
    print("\n=== 야생이 나올 때 ===")
    played = []
    real = shiny_fx.play
    shiny_fx.play = lambda root, area, pet, alive=None, on_done=None: played.append((pet, alive))
    try:
        ctl = wild_ui.WildController.__new__(wild_ui.WildController)
        ctl.app = FakeApp(root)
        ctl.pet = Dot()
        ctl.sparkle()
        chk("반짝임을 그 도트에 띄운다 (도트가 살아 있다고 본다)",
            len(played) == 1 and played[0][0] is ctl.pet and played[0][1]() is True, played)
        ctl.pet = Dot()
        chk("  다른 야생으로 바뀌면 옛 반짝임은 죽은 것으로 본다", played[0][1]() is False)
        ctl.pet = None
        ctl.sparkle()
        chk("  도트가 없으면 아무것도 안 한다", len(played) == 1, played)
    finally:
        shiny_fx.play = real
    src = open(wild_ui.__file__, encoding="utf-8").read()
    body = src[src.index("    def show_wild(self, mon"):src.index("    def sparkle(self):")]
    chk("show_wild: 색이 다른 개체일 때만 반짝인다",
        'if mon.get("shiny"):' in body and "self.sparkle()" in body.split('if mon.get("shiny"):', 1)[1]
        .split("self.app.notify", 1)[0])


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    errors = []
    root.report_callback_exception = lambda *a: errors.append(a)
    plan_part()
    play_part(root)
    wild_part(root)
    chk("그리는 중에 난 오류가 없다", not errors, errors[:1])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
