# -*- coding: utf-8 -*-
"""바탕화면의 빛나는 돌 표식과 메가스톤 알림 창 검사 (시즌 3).

    python client/test_bond_stone.py
    python client/run_as_windows.py client/test_bond_stone.py

**창을 진짜로 띄운다.** 도트는 서버 없이 여기서 그린다.

## 무엇을 못 박나

  1. bond.ready 의 포켓몬에만 '빛나는 돌', bond.claim 에는 '메가스톤 고르기'.
  2. 표식은 이름표 **위**, 도트·이름표 창을 한 픽셀도 덮지 않는다 (겹치면
     검게 나온다). 화면 위에 붙은 도트면 발밑으로 간다.
  3. 도트가 움직이면 따라간다.
  4. 배틀(block_names)·숨김(set_hidden) 동안 숨고, 끝나면 다시 뜬다.
  5. 목록에서 빠지거나 도트가 사라지면 표식 창도 없어진다 (고아 창 없음).
  6. 도트를 새로 만들면(크기 바꾸기) apply 로 다시 붙는다.
  7. 누르면: 빛나는 돌 = 되묻고 시작 -> 관리 창, 고르기 = 바로 관리 창.
  8. 저절로 받은 스톤 알림 창에 눌린 글자가 없다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-bondstone-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

from poketdesktop import bond_stone, config, overlay        # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, n=8):
    for _ in range(n):
        root.update()


def wait(root, cond, sec=5.0):
    """일꾼 스레드(run_async)가 돌아올 때까지. 몇 번 update 로는 모자란다."""
    import time
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


def dot():
    p = os.path.join(os.environ["POKET_HOME"], "dot.png")
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([6, 6, 25, 25], fill=(220, 60, 60, 255))
    im.save(p)
    return p


def mon(pid, name):
    return {"id": pid, "num": 6, "shiny": False,
            "info": {"name": name, "species": "리자몽", "level": 50, "types": ["불꽃"]}}


class FakeApi(object):
    def __init__(self):
        self.calls = []

    def bond_start(self, pid):
        self.calls.append(("start", pid))
        return {"pokemon": pid, "started": True}


class FakeApp(object):
    def __init__(self, root, ov):
        self.root = root
        self.overlay = ov
        self.api = FakeApi()
        self.arena = None
        self.battle = None
        self.box_window = None
        self.opened = []
        self.notes = []
        self.synced = 0

    def pet_open(self, pet):
        self.opened.append(pet.id)

    def notify(self, m):
        self.notes.append(m)

    def request_sync(self):
        self.synced += 1


def geo(w):
    w.update_idletasks()
    return w.winfo_x(), w.winfo_y(), w.winfo_width(), w.winfo_height()


def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def state(w):
    try:
        return w.state()
    except tk.TclError:
        return "gone"


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-300:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))

    settings = dict(config.DEFAULTS)
    settings["showNames"] = True
    ov = overlay.Overlay(root, settings)
    paths = {(6, False): dot()}
    app = FakeApp(root, ov)
    bs = bond_stone.BondStones(app)
    ov.sync([mon(1, "리자몽"), mon(2, "팬텀")], paths)
    settle(root)
    a, b = ov.pets[1], ov.pets[2]

    print("=== 붙이기 ===")
    bs.sync({"ready": [1], "claim": []})
    settle(root)
    chk("bond.ready 의 포켓몬에만 표식", a.stone_badge is not None and b.stone_badge is None)
    chk("  '빛나는 돌'", a.stone_badge.label.cget("text") == "✦ 빛나는 돌",
        a.stone_badge.label.cget("text"))
    x1, y1, x2, y2 = ov.area()
    a.x, a.y = (x1 + x2) // 2, (y1 + y2) // 2
    a.place()
    settle(root)
    g_badge, g_name, g_pet = geo(a.stone_badge.win), geo(a.name_win), geo(a.win)
    chk("이름표 위에 있다", g_badge[1] + g_badge[3] <= g_name[1], (g_badge, g_name))
    chk("  도트·이름표 창을 덮지 않는다", not overlaps(g_badge, g_name)
        and not overlaps(g_badge, g_pet), (g_badge, g_name, g_pet))
    chk("  도트 가운데 줄에", abs((g_badge[0] + g_badge[2] // 2) - (int(a.x) + a.fw // 2)) <= 2,
        (g_badge, a.x, a.fw))

    print("\n=== 움직이면 따라간다 ===")
    a.x += 120
    a.place()
    settle(root)
    g2 = geo(a.stone_badge.win)
    chk("오른쪽으로 120 옮긴다", abs((g2[0] - g_badge[0]) - 120) <= 2, (g_badge[0], g2[0]))

    print("\n=== 화면 위에 붙은 도트 ===")
    a.y = y1
    a.place()
    settle(root)
    g3, gp = geo(a.stone_badge.win), geo(a.win)
    chk("위로 나가면 발밑으로", g3[1] >= gp[1] + gp[3] and not overlaps(g3, gp), (g3, gp))
    a.x, a.y = (x1 + x2) // 2, (y1 + y2) // 2
    a.place()

    print("\n=== 배틀·숨김 ===")
    ov.block_names()
    settle(root)
    chk("배틀 동안 숨는다", state(a.stone_badge.win) == "withdrawn", state(a.stone_badge.win))
    ov.release_names()
    settle(root)
    chk("끝나면 다시 뜬다", state(a.stone_badge.win) == "normal", state(a.stone_badge.win))
    ov.set_hidden(True)
    settle(root)
    chk("숨기면 숨는다", state(a.stone_badge.win) == "withdrawn")
    ov.set_hidden(False)
    settle(root)
    chk("다시 보이면 뜬다", state(a.stone_badge.win) == "normal")

    print("\n=== 고르기 · 떼기 ===")
    old = a.stone_badge.win
    bs.sync({"ready": [], "claim": [1]})
    settle(root)
    chk("다 채우면 '메가스톤 고르기' 로 바뀐다",
        a.stone_badge.label.cget("text") == "✦ 메가스톤 고르기")
    chk("  옛 표식 창은 없앴다", state(old) == "gone", state(old))
    old = a.stone_badge.win
    bs.sync({"ready": [], "claim": []})
    settle(root)
    chk("목록에서 빠지면 뗀다", a.stone_badge is None and state(old) == "gone")
    bs.sync({"ready": [2], "claim": []})
    settle(root)
    old = b.stone_badge.win
    ov.sync([mon(1, "리자몽")], {})             # 팬텀을 박스로 보냈다
    settle(root)
    chk("도트가 사라지면 표식 창도 없어진다", state(old) == "gone", state(old))

    print("\n=== 도트를 새로 만들면 ===")
    bs.sync({"ready": [1], "claim": []})
    ov.refresh_visuals()
    bs.apply()
    settle(root)
    a = ov.pets[1]
    chk("새 도트에 다시 붙는다", a.stone_badge is not None
        and state(a.stone_badge.win) == "normal")

    print("\n=== 누르면 ===")
    asked = []
    real_confirm = ui_box.confirm
    ui_box.confirm = lambda *args, **kw: (asked.append(args[2]), True)[1]
    try:
        a.stone_badge._click()
        wait(root, lambda: app.opened and app.synced)
        chk("되묻는다 (이름과 함께)", asked and "리자몽" in asked[0], asked)
        chk("  시작을 보낸다", ("start", 1) in app.api.calls, app.api.calls)
        chk("  관리 창에서 그 포켓몬을 연다", app.opened == [1], app.opened)
        chk("  표식을 떼고 다시 맞춘다", a.stone_badge is None and app.synced == 1)
        ui_box.confirm = lambda *args, **kw: False
        bs.sync({"ready": [1], "claim": []})
        a.stone_badge._click()
        settle(root, 10)
        chk("아니오면 아무것도 안 한다", len(app.api.calls) == 1 and app.opened == [1])
        bs.sync({"ready": [], "claim": [1]})
        n = len(asked)
        a.stone_badge._click()
        settle(root, 10)
        chk("고르기는 되묻지 않고 관리 창을 연다", app.opened == [1, 1] and len(asked) == n
            and len(app.api.calls) == 1, (app.opened, app.api.calls))
        app.battle = object()
        a.stone_badge._click()
        chk("배틀 중에는 안 받는다", app.opened == [1, 1])
        app.battle = None
    finally:
        ui_box.confirm = real_confirm

    print("\n=== 저절로 받은 스톤 알림 ===")
    win = bond_stone.announce_got(root, [
        {"pokemon": 1, "name": "리자몽", "stone": "CHARIZARDITEY", "stoneKr": "리자몽나이트Y"},
        {"pokemon": 3, "name": "아주길고긴별명의팬텀이", "stone": "GENGARITE",
         "stoneKr": "팬텀나이트"}])
    settle(root)
    t = " ".join(texts(win))
    chk("받은 스톤과 포켓몬 이름", "리자몽나이트Y" in t and "아주길고긴별명의팬텀이" in t, t)
    chk("  눌린 글자가 없다", not squeezed(win), squeezed(win)[:3])
    chk("  창이 화면 안", win.winfo_height() <= root.winfo_screenheight(), win.winfo_height())
    win.destroy()

    ov.clear()
    settle(root)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
