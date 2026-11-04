# -*- coding: utf-8 -*-
"""상점의 랜덤 캡슐 띠 검사 (2.1.2) - 기본 테마와 디아루가·펄기아(DP) 테마. 돈으로 한 번 10,000원 · 10번 100,000원.

    python client/test_shop_capsule_ui.py            (기본 테마 뒤에 DP 테마를 따로 띄워 같이 본다)
    SHOT=폴더 python client/test_shop_capsule_ui.py  (띠 · 뽑기 기계를 찍어 둔다 - 맥 Quartz)

**창을 진짜로 띄운다.** 못 박는 것:

  1. 서버가 capsule 을 주면 상점 머리와 목록 사이에 랜덤 캡슐 띠가 깔리고, 옛 서버(없음)면 안 깔린다.
  2. 띠를 누르면 뽑기 기계가 돈 모드로 열린다: 값 · 글이 '원', 소지금은 상점의 돈, 코인 상점의 기계와 따로 하나.
  3. 돈 모드로 돌리면 /api/shop/capsule 을 부르고 (1회 · 10회), 답의 money 로 소지금을 맞추고 상점을 다시 받는다.
     돈이 모자라면 서버에 묻지 않고 알린다.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-shopcap-")
SKIN = os.environ.get("POKET_SHOPCAP_SKIN", "default")
os.environ["POKET_SKIN"] = SKIN

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_gacha, ui_shop           # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0
DATA = os.path.join(ROOT, "server", "data")
ODDS = [{"key": "lose", "kr": "꽝", "pct": 40.0, "tier": "lose"},
        {"key": "ball", "kr": "몬스터볼", "pct": 14.0, "tier": "common"}]


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def wait(root, cond, sec=12.0):
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


def one(tier="lose", **kw):
    r = {"prize": tier, "kr": tier, "tier": tier, "item": None, "itemKr": None, "count": 0, "deco": None,
         "decoKr": None, "egg": None, "reels": [tier] * 3, "message": "꽝!"}
    r.update(kw)
    return r


class Api(object):
    def __init__(self, money, capsule=True):
        raw = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["items"]
        self.items = [dict(i, buyable=True) for i in raw.values() if i["id"] in ("POKEBALL", "RARECANDY")]
        self.money, self.has_capsule = money, capsule
        self.shops, self.capsules = 0, []

    def shop(self):
        self.shops += 1
        out = {"items": [dict(i) for i in self.items], "bag": {}, "money": self.money, "sellRate": 0.5}
        if self.has_capsule:
            out["capsule"] = {"price": 10000, "counts": [1, 10], "odds": ODDS}
        return out

    def item_sprite(self, item_id):
        return None

    def shop_capsule(self, n):
        self.capsules.append(n)
        time.sleep(0.05)
        self.money -= 10000 * n
        if n == 1:
            r = one("common", item="POKEBALL", itemKr="몬스터볼", count=5)
        else:
            r = {"count": n, "results": [one() for _ in range(n)], "tier": "lose", "message": "10번 뽑았습니다"}
        r.update(ok=True, coin=7, money=self.money, bag={})       # coin 은 길드 코인 - 돈 모드는 안 읽는다
        return r


class App(object):
    def __init__(self, root, api):
        self.root, self.api = root, api
        self.settings = {}
        self.shop_window = None

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


def shot(name, title):
    d = os.environ.get("SHOT")
    if not d:
        return
    try:
        sys.path.insert(0, d)
        import selfshot
        selfshot.shoot(os.path.join(d, "%s_%s.png" % (name, SKIN)), title)
    except Exception as e:                                  # noqa: BLE001
        print("  (찍기 못 함: %s)" % e)


def run(root):
    print("== 테마: %s" % SKIN)
    chk("이번 실행의 테마", skins.active() == SKIN, skins.active())

    print("1. 띠")
    s, app = open_shop(root, Api(50000, capsule=False))
    chk("옛 서버(capsule 없음)면 띠가 없다", s.capsule_banner is None)
    s.close()
    api = Api(150000)
    s, app = open_shop(root, api)
    b = s.capsule_banner
    chk("서버가 주면 띠가 깔린다", b is not None and b.cv.winfo_ismapped() and b.cv.winfo_height() > 30)
    chk("  띠는 돈 모드 · 글에 원", b.money and "10,000원" in b._sub(10000) and "100,000원" in b._sub(10000))
    shot("shopcap_shop", "포스크탑 — 프렌들리샵")

    print("2. 뽑기 기계 (돈 모드)")
    b.open()
    w = getattr(app, "_gacha_money_win", None)
    chk("띠를 누르면 돈 모드 기계 (코인 상점 것과 따로)", w is not None and w.money and w.cost == 10000
        and getattr(app, "_gacha_win", None) is None, w and (w.money, w.cost))
    wait(root, lambda: w.art is not None and w.state == "idle")
    chk("  소지금은 상점의 돈 · 처음 글은 원", w.coin == 150000 and "10,000원" in w.said and "100,000원" in w.said,
        (w.coin, w.said))
    chk("  기계의 값 표시는 '1만'", ui_gacha.price_tag(10000, True) == "1만")
    shot("shopcap_machine", "랜덤 캡슐")

    print("3. 돌리기")
    w.spin()
    chk("1회: 그 자리에서 10,000원이 빠진다", w.state == "coin" and w.coin == 140000, (w.state, w.coin))
    wait(root, lambda: w.state == "ready", 15)
    chk("  서버의 상점 캡슐을 부른다 (1번)", api.capsules == [1], api.capsules)
    chk("  답의 money 로 소지금 (길드 코인 7 을 읽지 않는다)", w.coin == 140000, w.coin)
    shops = api.shops
    w.open_capsule()
    wait(root, lambda: w.state == "reveal", 8)
    wait(root, lambda: api.shops > shops and s._wait is None, 5)
    chk("  열면 상점을 다시 받는다 (소지금 · 가방)", api.shops > shops and s.money == 140000, (api.shops, s.money))
    settle(root, 0.5)                                     # (상품이 뜬 뒤 0.35초 안의 누름은 닫기가 아니다)
    w._overlay_click()
    settle(root, ui_gacha.CALM_SEC + 0.3)

    w.spin(ui_gacha.MULTI)
    wait(root, lambda: w.state == "ready", 15)
    chk("10회: 100,000원, 서버에 10번", api.capsules == [1, 10] and w.coin == 40000, (api.capsules, w.coin))
    w.open_capsule()
    wait(root, lambda: w.state == "reveal", 8)
    settle(root, 0.5)
    w._overlay_click()
    settle(root, ui_gacha.CALM_SEC + 0.3)
    w.spin(ui_gacha.MULTI)
    chk("돈이 모자라면(40,000원) 10회는 묻지 않고 알린다", api.capsules == [1, 10] and w.state == "idle"
        and "돈이 모자랍니다" in w.said and "100,000원" in w.said, w.said)
    w.close()
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
        env = dict(os.environ, POKET_SHOPCAP_SKIN="dp")
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
