# -*- coding: utf-8 -*-
"""가방 탭 안의 [도구 | 기술머신] 검사 (1.8.0).

    python client/test_bag_tabs.py
    python client/run_as_windows.py client/test_bag_tabs.py

**창을 진짜로 띄운다.** 허브 창(탭 열 개)을 실제로 만들고 가방 탭을 연다.

## 무엇을 못 박나

  1. 탭 목록에서 '기술머신' 이 빠지고 '게시판' 이 생겼다. 가방은 그대로 있다.
  2. 가방 탭을 열면 도구 칸이 뜨고, 머리줄에 [도구 | 기술머신] 이 있다.
  3. **기술머신 칸은 처음 눌렀을 때 만든다** (가방만 보는 사람은 목록을 안 받는다).
  4. 두 칸의 고르는 단추가 **같은 자리**에 있다 - 오갈 때 튀지 않는다.
  5. 돌아오면 아까 만든 칸 그대로다 (다시 만들지 않는다).
  6. 눌린 위젯이 없다 - 머리줄에 단추를 끼웠어도.
  7. 탭 이름에 '새 공지' 점을 찍고 지운다.
"""
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-bagtabs-"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import time                                                 # noqa: E402
import tkinter as tk                                        # noqa: E402

import smoke_box_filter as SB                               # noqa: E402
import smoke_tms as ST                                      # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_hub                             # noqa: E402
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


class Api(ST.FakeApi):
    """가방(상점 목록·포켓몬)과 기술머신을 둘 다 답한다."""

    def __init__(self, tms, learners):
        ST.FakeApi.__init__(self, tms, learners)
        self.shop_api = SB.FakeApi([])

    def _call(self, method, path, body=None, **_kw):
        self.calls.append((method, path))
        if path == "/api/shop":
            return self.shop_api.shop()
        return {}

    def pokemon(self):
        self.calls.append("pokemon")
        return []

    def item_sprite(self, item_id):
        return self.shop_api.item_sprite(item_id)


class App(object):
    def __init__(self, root, api):
        self.root = root
        self.api = api
        self.dex = None
        self.settings = {}
        self.balls = 5
        self.money = 0
        self.bag_window = None
        self.tm_window = None

    def request_sync(self):
        pass

    def notify(self, *_a):
        pass


def wait(root, cond, sec=8.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


def settle(root, sec=0.4):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def spot(seg, top):
    """고르는 단추가 창 안에서 어디에 있는지 (x, y)."""
    seg.frame.update_idletasks()
    return (seg.frame.winfo_rootx() - top.winfo_rootx(),
            seg.frame.winfo_rooty() - top.winfo_rooty())


def find_seg(pane):
    """그 칸 머리줄의 Segmented 를 찾는다 (금색으로 칠한 칸이 있는 틀)."""
    def walk(w):
        for c in w.winfo_children():
            kids = c.winfo_children()
            if kids and all(k.winfo_class() == "Label" for k in kids) \
                    and [k.cget("text") for k in kids] == ["도구", "기술머신"]:
                return c
            got = walk(c)
            if got is not None:
                return got
        return None
    return walk(pane.win)


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))

    tms = ST.load_tms()
    api = Api(tms, [])
    app = App(root, api)

    print("=== 탭 목록 ===")
    keys = [t[0] for t in ui_hub.TABS]
    labels = [t[1] for t in ui_hub.TABS]
    chk("기술머신 탭이 없다", "tms" not in keys and "기술머신" not in labels, labels)
    chk("가방·게시판 탭이 있다", "가방" in labels and "게시판" in labels, labels)

    hub = ui_hub.HubWindow(app)
    hub.show("bag")
    tabs = hub.panes.get("bag")
    chk("가방 탭이 뜬다", tabs is not None and tabs.current == "items", tabs)
    wait(root, lambda: ("GET", "/api/shop") in api.calls)
    settle(root)
    chk("도구 칸이 먼저 뜬다 ('가진 도구')", "가진 도구" in texts(hub.win), texts(hub.win)[:12])
    chk("기술머신은 아직 안 받았다", "tms" not in api.calls and tabs.tms is None,
        [c for c in api.calls if c == "tms"])
    seg_a = find_seg(tabs.bag)
    chk("머리줄에 [도구 | 기술머신]", seg_a is not None)
    on = [k.cget("text") for k in seg_a.winfo_children() if k.cget("bg") == U.ACCENT]
    chk("  '도구' 가 골라져 있다", on == ["도구"], on)
    at_a = (seg_a.winfo_rootx() - hub.win.winfo_rootx(),
            seg_a.winfo_rooty() - hub.win.winfo_rooty())
    # **머리줄만 본다.** 창 전체를 보면 여기서 안 건드린 자리의 2~4px 눌림(맥에서
    # 윈도우 배율을 흉내 낼 때 나는 것)까지 걸린다 - 예전 구조도 똑같이 나온다.
    bad = squeezed(seg_a.master.master)
    chk("  머리줄에 눌린 위젯이 없다", not bad, bad[:3])

    print("\n=== 기술머신으로 ===")
    # 단추를 실제로 누른다
    tm_cell = [k for k in seg_a.winfo_children() if k.cget("text") == "기술머신"][0]
    tm_cell.event_generate("<Button-1>")
    chk("누르면 기술머신 칸으로", wait(root, lambda: tabs.current == "tms" and "tms" in api.calls),
        tabs.current)
    settle(root)
    chk("기술머신 목록이 뜬다", any("기술머신" in t for t in texts(tabs.tms.win)),
        texts(tabs.tms.win)[:6])
    chk("도구 칸은 숨는다 (없애지 않는다)", not tabs.holders["items"].winfo_ismapped()
        and tabs.bag is not None)
    seg_b = find_seg(tabs.tms)
    on = [k.cget("text") for k in seg_b.winfo_children() if k.cget("bg") == U.ACCENT]
    chk("이번엔 '기술머신' 이 골라져 있다", on == ["기술머신"], on)
    at_b = (seg_b.winfo_rootx() - hub.win.winfo_rootx(),
            seg_b.winfo_rooty() - hub.win.winfo_rooty())
    chk("고르는 단추가 같은 자리 (오갈 때 안 튄다)",
        abs(at_a[0] - at_b[0]) <= 1 and abs(at_a[1] - at_b[1]) <= 1, (at_a, at_b))
    chk("기술머신의 거르기 단추도 그대로 있다",
        any(t.startswith("타입") for t in texts(tabs.tms.win))
        and any(t.startswith("분류") for t in texts(tabs.tms.win)), texts(tabs.tms.win)[:10])
    bad = squeezed(seg_b.master.master)
    chk("  머리줄에 눌린 위젯이 없다", not bad, bad[:3])

    print("\n=== 다시 도구로 ===")
    bag_before, n_shop = tabs.bag, api.calls.count(("GET", "/api/shop"))
    tabs.show("items")
    settle(root, 0.2)
    chk("아까 그 칸 그대로 (다시 만들지 않는다)", tabs.bag is bag_before
        and api.calls.count(("GET", "/api/shop")) == n_shop)
    chk("도구 칸이 다시 보인다", tabs.holders["items"].winfo_ismapped()
        and not tabs.holders["tms"].winfo_ismapped())

    print("\n=== 새 공지 점 ===")
    idx = hub.order.index("board")
    hub.set_badge("board", True)
    chk("게시판 탭에 점", "●" in hub.nb.tab(idx, "text"), hub.nb.tab(idx, "text"))
    hub.set_badge("board", False)
    chk("끄면 사라진다", "●" not in hub.nb.tab(idx, "text") and "게시판" in hub.nb.tab(idx, "text"))

    hub.close()
    settle(root, 0.3)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
