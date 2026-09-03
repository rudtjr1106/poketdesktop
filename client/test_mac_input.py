# -*- coding: utf-8 -*-
"""맥 입력 처리 검사 — 우클릭이 어디로 가는가, 눌린 채 굳지 않는가.

    python client/test_mac_input.py

창을 안 띄운다. 붙이는 규칙만 본다.

## 왜 이 검사가 있나

맥에서 이 셋이 차례로 물렸다.

  1. 맥 Tk 은 오른쪽 단추가 **2번**이다. 3번은 가운데 단추라
     `<Button-3>` 만 걸어 두면 오른쪽 클릭이 통째로 안 먹는다.
  2. 고쳐도 **앱이 활성이 아니면** Tk 이 오른쪽 클릭을 위젯까지 전달하지
     않는다. Dock 에 안 뜨는 앱이라 거의 늘 비활성이다. 그래서 포켓몬을
     한 번 왼쪽 클릭해 앱을 깨우기 전에는 우클릭이 안 됐다.
     -> Cocoa 단계에서 직접 받는다 (platform_mac.watch_right_click).
  3. 같은 이유로 '뗐다'(ButtonRelease)도 못 받아서 도트가 눌린 채로
     굳었다. -> 맥에 "지금 눌린 단추가 있냐" 를 직접 묻는다.
"""
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-test-input"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def section(t):
    print("-- %s" % t)


class FakePet(object):
    def __init__(self, x, y, w, h, num=None):
        self.x, self.y, self.fw, self.fh = x, y, w, h
        self.state = "idle"
        self.called = []
        self.view = type("V", (), {"win_number": num})()

    def on_menu(self, e):
        self.called.append(("menu", e.x_root, e.y_root))

    def on_release(self, e):
        self.state = "idle"
        self.called.append("release")


def main():
    if sys.platform != "darwin":
        print("맥에서만 하는 검사입니다.")
        return 0

    from poketdesktop import platform_os as PLAT
    from poketdesktop import platform_mac as M
    from poketdesktop import app as appmod

    section("오른쪽 클릭은 2번 단추다")
    chk("<Button-2> 가 목록에 있다", "<Button-2>" in M.RIGHT_CLICK, M.RIGHT_CLICK)
    chk("Control+왼쪽 클릭도 친다",
        "<Control-Button-1>" in M.RIGHT_CLICK, M.RIGHT_CLICK)

    section("맥에서는 Tk 에 우클릭을 걸지 않는다 (두 번 처리 방지)")
    marks = []

    class W(object):
        def bind(self, seq, fn):
            marks.append(seq)

    PLAT.bind_right(W(), lambda e: None)
    chk("Tk 바인딩을 안 건다", marks == [], marks)
    chk("대신 감시자가 있다", callable(PLAT.watch_right_click))

    section("감시자로 받은 우클릭을 알맞은 도트에게 넘긴다")
    a = appmod.App.__new__(appmod.App)      # __init__ 없이 껍데기만
    mine = FakePet(100, 100, 40, 40, num=11)
    wildp = FakePet(300, 300, 40, 40, num=22)
    grass = FakePet(500, 500, 40, 40, num=33)

    class FakeWild(object):
        pet = wildp
        grass_hit = []

        def __init__(self):
            self.grass = grass

        def on_grass_click(self):
            FakeWild.grass_hit.append(1)

    class FakeOv(object):
        pets = {}
        extra = []

    a.wild = FakeWild()
    a.overlay = FakeOv()
    a.overlay.pets = {1: mine}

    a._right_click_at(110, 110, 11)
    chk("내 포켓몬 자리는 내 포켓몬에게", mine.called and mine.called[0][0] == "menu",
        mine.called)
    a._right_click_at(310, 310, 22)
    chk("야생 자리는 야생에게 (볼 던지기)",
        wildp.called and wildp.called[0][0] == "menu", wildp.called)
    a._right_click_at(510, 510, 33)
    chk("풀숲 자리는 풀숲에게", FakeWild.grass_hit == [1], FakeWild.grass_hit)

    n_before = len(mine.called) + len(wildp.called)
    a._right_click_at(900, 900, 99)
    chk("아무것도 없는 자리는 아무 일도 안 한다",
        len(mine.called) + len(wildp.called) == n_before)

    section("야생이 먼저다 (위에 있다)")
    both = FakePet(100, 100, 40, 40, num=11)
    a.wild.pet = both
    mine.called = []
    both.called = []
    a._right_click_at(110, 110, 11)
    chk("겹치면 야생이 받는다", both.called and not mine.called,
        (both.called, mine.called))
    a.wild.pet = wildp

    section("눌린 채로 굳지 않는다")
    mine.state = "held"
    wildp.state = "held"
    real = PLAT.mouse_buttons_down
    try:
        appmod.PLAT.mouse_buttons_down = lambda: 1     # 누르고 있는 중
        a._unstick()
        chk("누르고 있는 동안은 그대로", mine.state == "held")
        appmod.PLAT.mouse_buttons_down = lambda: 0     # 뗐다
        a._unstick()
        chk("떼면 내 포켓몬이 풀린다", mine.state == "idle")
        chk("떼면 야생도 풀린다", wildp.state == "idle")
    finally:
        appmod.PLAT.mouse_buttons_down = real

    section("맥에 직접 물어본 값")
    chk("눌린 단추를 물어볼 수 있다",
        isinstance(PLAT.mouse_buttons_down(), int))
    chk("지금은 아무것도 안 눌려 있다", PLAT.mouse_buttons_down() == 0,
        PLAT.mouse_buttons_down())

    print()
    print("=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
