# -*- coding: utf-8 -*-
"""화면 테마 'dp' - 이로치 색 고르기 창(skins/dp/tint.py) 검사.

    python client/test_skin_dp_tint.py

창을 진짜로 띄운다 (가짜 서버는 test_tint_ui 의 것). 기본 창의 동작이 DP 판에서도 그대로인가를 본다 (v2: 큰 도트 무대는 없앴다):
  1. POKET_SKIN=dp 면 DP 클래스로 뜬다. 16칸, 미리보기, 지금 색이 골라져 있다.
  2. 칸을 누르면 고른 표시만 바뀐다 (서버엔 안 간다). 바꾼 게 없으면 '이 색으로' 는 안 눌린다.
  3. 화살표 키로 칸을 옮긴다.
  4. 실패하면 창에 까닭이 남는다. 다시 누르면 서버에 그 값으로 간다 · 창이 닫히고 콜백.
  5. 이로치 색(None)으로 되돌릴 수 있다. 그리는 중 예외가 없다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-skin-dp-tint-")
os.environ["POKET_SKIN"] = "dp"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import test_tint_ui as TT                                   # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_tint                            # noqa: E402
from poketdesktop.skins.dp import tint as DT                # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def click(root, w, v):
    x1, y1, x2, y2 = w.rects[v]
    w.cv.event_generate("<Button-1>", x=(x1 + x2) // 2, y=(y1 + y2) // 2)
    root.update()


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append(repr(v))
    api = TT.FakeApi()
    app = TT.MiniApp(root, api)
    m = TT.mon(9, True, "s090", "불꽃이")
    done = []

    w = ui_tint.TintPicker(app, m, on_done=lambda p: done.append(p))
    chk("DP 클래스로 뜬다", type(w) is DT.TintPicker, type(w))
    chk("16칸", len(w.cells) == 16 and None in w.cells and "normal" in w.cells, len(w.cells))
    chk("미리보기가 뜬다", TT.wait(root, lambda: len(w.photos) == 16), len(w.photos))
    TT.settle(root, 0.2)
    chk("지금 색(s090)이 골라져 있다", w.picked == "s090" and w.state["s090"] == (True, True), w.state["s090"])
    chk("바꾼 것이 없으면 '이 색으로' 는 안 눌린다", w.ok_btn.enabled is False)
    chk("상태 글이 비었다", w.status.cget("text") == "", w.status.cget("text"))
    n = len(api.calls)
    click(root, w, "n135")
    chk("칸을 누르면 고른 표시만 바뀐다", w.picked == "n135" and w.state["n135"][0] and not w.state["s090"][0])
    chk("  '이 색으로' 가 눌린다 · 아직 서버에 안 간다", w.ok_btn.enabled and len(api.calls) == n and not done)
    w.win.event_generate("<Left>")
    root.update()
    chk("왼쪽 화살표로 옆 칸", w.picked == "n090", w.picked)
    w.win.event_generate("<Up>")
    root.update()
    chk("위쪽 화살표로 윗줄", w.picked == "s090", w.picked)
    click(root, w, "n135")

    api.fail = "이로치 포켓몬만 색을 고를 수 있습니다."
    w.apply()
    chk("실패하면 창에 까닭이 남는다", TT.wait(root, lambda: "이로치" in w.status.cget("text")), w.status.cget("text"))
    chk("  창은 그대로, 끝났다고 알리지 않는다", w.alive and not done)
    api.fail = None
    w.apply()
    chk("'이 색으로' 가 서버에 간다", TT.wait(root, lambda: done) and api.calls[-1] == ("tint", 9, "n135"),
        api.calls[-1])
    chk("  창이 닫히고 손에 든 값이 바뀐다", not w.alive and m["tint"] == "n135")

    done[:] = []
    w = ui_tint.TintPicker(app, m, on_done=lambda p: done.append(p))
    TT.wait(root, lambda: len(w.photos) == 16)
    w.pick(None)
    w.apply()
    chk("맨 앞 칸(이로치 색)은 None", TT.wait(root, lambda: done) and api.calls[-1] == ("tint", 9, None),
        api.calls[-1])

    w = ui_tint.TintPicker(app, m)
    w.close()
    TT.settle(root, 0.2)
    chk("미리보기를 받기 전에 닫아도 예외가 없다", not errors, errors[:2])
    chk("그리는 중 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n합계 OK %d FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
