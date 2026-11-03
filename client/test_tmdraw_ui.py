# -*- coding: utf-8 -*-
"""상점의 '랜덤 기술머신 뽑기' 띠 검사 (2.1.1, ui_tmdraw) - 기본 테마와 디아루가·펄기아(DP) 테마.

    python client/test_tmdraw_ui.py                  (기본 테마 뒤에 DP 테마를 따로 띄워 같이 본다)
    SHOT=폴더 python client/test_tmdraw_ui.py        (띠 · 결과 창을 찍어 둔다 - 맥 Quartz)

**창을 진짜로 띄운다.** 못 박는 것:

  1. 서버가 tmDraw 를 주면 머리와 목록 사이에 띠가 깔리고, 옛 서버(없음)면 안 깔린다.
  2. 1회 · 10회 값은 서버 값 그대로 (10,000원 · 100,000원). 돈이 모자라거나 남은 기술머신이 모자란 단추는
     눌러도 서버에 묻지 않고 까닭을 알린다.
  3. 1회는 바로, 10회는 한 번 묻고 뽑는다 (그만두면 안 뽑는다). 뽑으면 결과 창(카드 1장 · 10장),
     [기술머신] 노란 점, 상점을 다시 받는다 (돈 · 남은 수).
  4. 그사이 거절되면(돈이 모자람 등) 서버 말을 보여 주고 상점을 다시 받는다.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-tmdraw-")
SKIN = os.environ.get("POKET_TMDRAW_SKIN", "default")
os.environ["POKET_SKIN"] = SKIN

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_box, ui_shop, ui_tmdraw  # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0
DATA = os.path.join(ROOT, "server", "data")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def wait(root, cond, sec=10.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.005)
    return cond()


def settle(root, sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.005)


TMS = [{"no": 42 + i, "kr": kr, "type": t, "cat": "special", "label": "기술머신%03d %s" % (42 + i, kr)}
       for i, (kr, t) in enumerate((("냉동빔", "ICE"), ("10만볼트", "ELECTRIC"), ("화염방사", "FIRE"),
                                    ("파도타기", "WATER"), ("에너지볼", "GRASS"), ("섀도볼", "GHOST"),
                                    ("지진", "GROUND"), ("문포스", "FAIRY"), ("용성군", "DRAGON"), ("사이코키네시스", "PSYCHIC")))]


class Api(object):
    def __init__(self, money, left=300, draw=True):
        raw = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["items"]
        self.items = [dict(i) for i in raw.values() if i["id"] in ("POKEBALL", "RANKTICKETTM", "RARECANDY")]
        for i in self.items:
            i["buyable"] = i.get("cost", 0) > 0
        self.money, self.left, self.has_draw = money, left, draw
        self.shops, self.draws, self.refuse = 0, [], None

    def shop(self):
        self.shops += 1
        out = {"items": [dict(i) for i in self.items], "bag": {}, "money": self.money, "sellRate": 0.5}
        if self.has_draw:
            out["tmDraw"] = {"price": 10000, "counts": [1, 10], "left": self.left}
        return out

    def item_sprite(self, item_id):
        return None

    def shop_tmdraw(self, n):
        self.draws.append(n)
        if self.refuse:
            from poketdesktop.api import ApiError
            raise ApiError(self.refuse, 400)
        self.money -= 10000 * n
        self.left -= n
        return {"ok": True, "count": n, "spent": 10000 * n, "tms": TMS[:n], "tmNew": 3 + n, "money": self.money,
                "bag": {}, "message": "기술머신 %d개를 얻었다!" % n if n > 1 else "기술머신042 냉동빔을 얻었다!"}


class App(object):
    def __init__(self, root, api):
        self.root, self.api = root, api
        self.settings = {}
        self.noted = []
        self.shop_window = None

    def note_tms(self, n, reload=True):
        self.noted.append(n)

    def request_sync(self):
        pass

    def notify(self, *_a):
        pass


def open_shop(root, api):
    app = App(root, api)
    s = ui_shop.ShopWindow(root, app)
    top = s.win.winfo_toplevel()
    top.geometry("1040x700+30+30")
    top.deiconify()
    wait(root, lambda: s.items and s._wait is None)
    settle(root, 0.4)
    return s, app


def status(s):
    if hasattr(s, "msg"):
        return s.msg[0] or ""
    return s.status._label.cget("text")


def pill(s, n):
    """그 단추 가운데를 누른다."""
    x0, y0, x1, y1 = s.tm_banner.pills[n]
    s.tm_banner._click(type("E", (), {"x": (x0 + x1) // 2, "y": (y0 + y1) // 2})())


def shot(win, name):
    d = os.environ.get("SHOT")
    if not d:
        return
    try:
        sys.path.insert(0, d)
        import selfshot
        win.update()
        selfshot.shoot(os.path.join(d, "%s_%s.png" % (name, SKIN)), win.title() if hasattr(win, "title") else None)
    except Exception as e:                                  # noqa: BLE001
        print("  (찍기 못 함: %s)" % e)


def run(root):
    print("== 테마: %s" % SKIN)
    chk("이번 실행의 테마", skins.active() == SKIN, skins.active())

    print("1. 띠")
    s, app = open_shop(root, Api(50000, draw=False))
    chk("옛 서버(tmDraw 없음)면 띠가 없다", not s.tm_banner.shown and not s.tm_banner.cv.winfo_ismapped())
    s.close()

    api = Api(50000)
    s, app = open_shop(root, api)
    b = s.tm_banner
    chk("서버가 주면 띠가 깔린다", b.shown and b.cv.winfo_ismapped() and b.cv.winfo_height() > 30, b.cv.winfo_height())
    chk("  머리 아래 · 목록 위", b.cv.winfo_y() < (s.vl.winfo_rooty() - s.win.winfo_rooty()
                                                  if hasattr(s.vl, "winfo_rooty") else 10 ** 6), b.cv.winfo_y())
    chk("  단추 둘 (1회 왼쪽 · 10회 오른쪽, 띠 안)", set(b.pills) == {1, 10} and b.pills[1][2] < b.pills[10][0]
        and b.pills[10][2] <= b.cv.winfo_width(), b.pills)
    chk("  돈 50,000원: 1회는 되고 10회는 안 된다", b.can(1)[0] and not b.can(10)[0] and "100,000원" in b.can(10)[1],
        (b.can(1), b.can(10)))
    shot(s.win.winfo_toplevel(), "tmdraw_shop")

    print("2. 못 누르는 단추")
    pill(s, 10)
    settle(root, 0.1)
    chk("10회를 누르면 묻지 않고 '돈이 모자랍니다'", api.draws == [] and "모자랍니다" in status(s), status(s))

    print("3. 1회")
    shops = api.shops
    pill(s, 1)
    wait(root, lambda: b.result_win is not None)
    settle(root, 0.4)
    rw = b.result_win
    chk("1회는 묻지 않고 바로 뽑는다", api.draws == [1], api.draws)
    chk("  결과 창 · 노란 점 · 상점 다시 받기", rw and rw.win.winfo_exists() and app.noted == [4] and api.shops > shops,
        (app.noted, api.shops))
    chk("  결과 창 제목", rw.win.title() == "기술머신 뽑기 결과", rw.win.title())
    rw.close()
    wait(root, lambda: s._wait is None and s.money == 40000)
    chk("  돈이 줄어 보인다", s.money == 40000, s.money)

    print("4. 10회")
    api.money = 200000
    s.reload()
    wait(root, lambda: s._wait is None and s.money == 200000)
    settle(root, 0.2)
    real = ui_box.confirm
    asked = []
    ui_box.confirm = lambda *a, **k: asked.append(a) or False
    try:
        pill(s, 10)
        settle(root, 0.2)
        chk("10회는 먼저 묻고, 그만두면 안 뽑는다", asked and "100,000원" in asked[-1][2] and api.draws == [1],
            (asked[-1:], api.draws))
        ui_box.confirm = lambda *a, **k: True
        b.result_win = None
        pill(s, 10)
        wait(root, lambda: b.result_win is not None)
        settle(root, 0.5)
    finally:
        ui_box.confirm = real
    rw = b.result_win
    chk("  예를 누르면 10번 뽑고 카드 열 장", api.draws == [1, 10] and rw and len(rw.ph) >= 12, (api.draws, len(rw.ph)))
    w, h = rw.win.winfo_width(), rw.win.winfo_height()
    sw = rw.win.winfo_screenwidth()
    chk("  결과 창이 화면 안 (%dx%d)" % (w, h), 300 < w <= sw and h > 200, (w, h, sw))
    shot(rw.win, "tmdraw_result")
    rw.close()

    print("5. 남은 기술머신이 모자랄 때 · 거절")
    api.left, api.money = 3, 500000
    s.reload()
    wait(root, lambda: s._wait is None and s.tm_draw and s.tm_draw["left"] == 3)
    chk("남은 3개: 10회는 안 된다 (까닭에 '3개뿐')", not b.can(10)[0] and "3개뿐" in b.can(10)[1], b.can(10))
    api.refuse = "돈이 모자랍니다. (10,000원 필요)"
    shops = api.shops
    pill(s, 1)
    wait(root, lambda: api.shops > shops and s._wait is None)
    settle(root, 0.3)
    chk("거절되면 서버 말을 보여 주고 상점을 다시 받는다", "모자랍니다" in status(s) or api.shops > shops, status(s))
    chk("  단추가 다시 눌린다", not b.busy)
    s.close()


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))
    run(root)
    chk("그리는 중에 난 예외가 없다", not errors, errors[:3])
    try:
        root.destroy()
    except tk.TclError:
        pass


if __name__ == "__main__":
    main()
    if SKIN == "default":
        env = dict(os.environ, POKET_TMDRAW_SKIN="dp")
        env.pop("POKET_HOME", None)
        out = subprocess.run([sys.executable, os.path.abspath(__file__)], env=env, capture_output=True, text=True)
        for line in out.stdout.splitlines():
            if line.startswith("  ") or line.startswith("=="):
                print(line)
            if line.startswith("합계"):
                bits = line.split()
                OK += int(bits[2])
                FAIL += int(bits[4])
        if out.returncode != 0 or "합계" not in out.stdout:
            FAIL += 1
            print("  FAIL DP 테마 검사가 끝나지 않았다\n%s" % out.stderr[-1500:])
    print("합계 OK %d FAIL %d" % (OK, FAIL))
    sys.exit(1 if FAIL else 0)
