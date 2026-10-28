# -*- coding: utf-8 -*-
"""대전 다시 보기를 × · Esc 로 언제든 끌 수 있는가 (arena.StopPlate · Arena.stop).

## 왜 이 검사가 있나

랭킹 탭 '대전 기록' 의 다시 보기는 30초쯤 가는 재생인데 끌 방법이 없었다. 지금은 재생 위에
'대전 다시 보기 ×' 판이 뜨고, × 나 Esc 가 Arena.cleanup() - 로그아웃·종료와 같은 정리 길 - 로
간다. 여기서는 도트 캐시가 없어도 돌도록 가짜 바탕화면(도트 0마리)으로 투기장을 진짜로 열고,

  - 열면 판이 뜬다 / 닫으면 판 · 효과 레이어 창이 하나도 안 남는다
  - 열고 닫은 뒤 after 예약이 안 남는다 (닫은 뒤에 불려 터지는 콜백이 없다)
  - 두 번 눌러도 · 소집 중에 눌러도 안전하다 / 끝났다는 알림(on_done)은 한 번만
  - 다시 보기를 또 열어도 문제없다

를 본다. 진짜 마우스는 안 움직이고, 키는 묶어 둔 콜백을 이벤트로 보낸다.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-arena-close-"))

import tkinter as tk                                        # noqa: E402

from poketdesktop import arena as A                         # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


class FakeOverlay(object):
    """Arena 가 바탕화면에 요구하는 것만. 도트는 0마리 (캐시된 도트가 없어도 돌게)."""

    def __init__(self):
        self.pets, self.extra = {}, []
        self.locked, self.hidden = False, False
        self.settings = {"targetHeight": 96}
        self.blocked = 0

    def area(self):
        return (900, 500, 1400, 760)

    def block_names(self):
        self.blocked += 1

    def release_names(self):
        self.blocked -= 1

    def make(self, mon, cls=None):
        return None


class FakeApp(object):
    def __init__(self, root):
        self.root = root
        self.dex = None
        self.overlay = FakeOverlay()
        self.arena = None


VIEW = {"id": 1, "foe": {"name": "상대"}, "events": [
    {"t": "teams", "me": [{"num": 25}], "foe": [{"num": 4}]}]}


def pending(root):
    """Tk 에 예약된 after 콜백 수 (tk 가 아는 대로)."""
    return len([x for x in root.tk.call("after", "info")])


def toplevels(root):
    return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]


def spin(root, n=10):
    for _ in range(n):
        root.update()


def open_arena(root, calls):
    app = FakeApp(root)
    ar = A.Arena(app, VIEW, on_done=lambda: calls.append(1))
    app.arena = ar
    ar.start()
    spin(root)
    return app, ar


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    base_after, base_tops = pending(root), len(toplevels(root))

    def clean(tag, app, calls):
        spin(root, 20)
        chk("%s: 투기장이 닫혔다" % tag, app.arena.closed)
        chk("%s: 그만 보기 판 · 효과 레이어 창이 안 남는다" % tag,
            len(toplevels(root)) == base_tops, len(toplevels(root)))
        chk("%s: after 예약이 안 남는다" % tag, pending(root) <= base_after,
            (pending(root), base_after))
        chk("%s: 화면 잠금이 풀리고 이름표 막음도 풀린다" % tag,
            not app.overlay.locked and app.overlay.blocked == 0,
            (app.overlay.locked, app.overlay.blocked))
        chk("%s: 끝났다고 한 번만 알린다" % tag, calls == [1], calls)

    print("=== 열면 판이 뜬다 ===")
    calls = []
    app, ar = open_arena(root, calls)
    chk("그만 보기 판이 떴다", ar.stop_plate is not None and ar.stop_plate.win.winfo_exists())
    chk("판 아래 재생 중이다 (닫히지 않았다)", not ar.closed)

    print("=== × 를 누른다 ===")
    ar.stop_plate.x.event_generate("<Button-1>")
    clean("×", app, calls)
    chk("× 뒤 stop_plate 비움", ar.stop_plate is None)

    print("=== Esc ===")
    calls = []
    app, ar = open_arena(root, calls)
    w = ar.stop_plate.win
    try:
        w.focus_force()                                 # 키 이벤트는 포커스가 있어야 간다
    except tk.TclError:
        pass
    spin(root, 5)
    w.event_generate("<Escape>")
    if not ar.closed:
        # 포커스를 못 얻는 러너(윈도우 CI 등) - 묶어 둔 콜백이 있는지만 본다
        chk("Esc 가 묶여 있다 (키 이벤트는 러너에 포커스가 없어 못 보냈다)", bool(w.bind("<Escape>")))
        ar.stop_plate.stop()
    clean("Esc", app, calls)

    print("=== 소집 중(막 열자마자) · 두 번 눌러도 · 정리를 또 불러도 ===")
    calls = []
    app, ar = open_arena(root, calls)
    plate = ar.stop_plate
    plate.stop()
    plate.stop()
    ar.stop()
    ar.cleanup()
    clean("두 번", app, calls)

    print("=== 중간에 재생을 쉬었다 가도 (몇 번 돌린 뒤) ===")
    calls = []
    app, ar = open_arena(root, calls)
    import time
    t = time.time()
    while time.time() - t < 1.0:
        root.update()
    ar.stop_plate.x.event_generate("<Button-1>")
    clean("1초 뒤", app, calls)

    print("=== 다시 보기를 또 열어도 ===")
    for i in range(3):
        calls = []
        app, ar = open_arena(root, calls)
        chk("%d번째: 새 판이 뜬다" % (i + 1), ar.stop_plate is not None and ar.stop_plate.alive)
        ar.stop_plate.x.event_generate("<Button-1>")
        clean("%d번째" % (i + 1), app, calls)

    print("=== 판이 뜬 자리가 작업 영역 안 ===")
    app, ar = open_arena(root, [])
    win = ar.stop_plate.win
    x, y = win.winfo_rootx(), win.winfo_rooty()
    wl, wt, wr, wb = ar.work
    chk("작업 영역 안에 있다", wl <= x <= wr and wt <= y <= wb, (x, y, ar.work))
    ar.stop()
    spin(root, 20)

    try:
        root.destroy()
    except Exception:                                       # noqa: BLE001
        pass
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
