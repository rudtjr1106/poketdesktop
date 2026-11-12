# -*- coding: utf-8 -*-
"""포켓몬 관리 창: 놓아준 뒤에는 아무것도 고르지 않는다 (게시판 #512).

    python client/test_box_release_select.py              # 기본 테마
    POKET_SKIN=dp python client/test_box_release_select.py   # DP 계열 (pt · gs · bw · emerald 도 DP 것을 물려받는다)

예전에는 고른 포켓몬을 놓아주면 다시 불러온 목록의 **맨 앞 줄(파티 첫 칸)을 저절로 골랐다.** 한 마리씩 놓아주다
렉으로 '불러오는 중' 덮개가 다음 클릭을 먹으면, 다음 것을 골랐다고 믿고 [놓아주기]·[확인] 을 같은 박자로 눌러
파티 첫 칸의 메인 포켓몬(미라이돈)이 놓아졌다.

  1. 창을 처음 열면 예전처럼 맨 앞 줄을 고른다 (그대로).
  2. 한 마리를 놓아주면 아무것도 안 고른 모습: 고른 것 없음 · 단추 꺼짐 · 상세 칸 '포켓몬을 고르세요'.
     파티 첫 칸이 골라지지 않는다. 그 상태에서 [놓아주기] 를 또 눌러도 아무 일이 없다.
  3. 다시 누르면 평소처럼 골라지고, 그것을 놓아주면 또 빈 모습.
  4. 놓아주는 요청이 도는 동안 다른 포켓몬을 누르면 그 고름은 그대로 남는다.
  5. 여러 마리 놓아주기로 고른 포켓몬이 놓아져도 빈 모습 (고르기를 끈 뒤에도).
**창을 진짜로 띄운다.** 서버는 안 띄운다 (smoke_box_filter 의 가짜 api).
"""
import json
import os
import sys
import tempfile
import threading

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-boxrelsel-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
import smoke_box_filter as SB                               # noqa: E402

OK = FAIL = 0
DATA = os.path.join(os.path.dirname(HERE), "server", "data")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def enabled(b):
    if hasattr(b, "enabled"):
        return bool(b.enabled)
    return str(b.cget("state")) == "normal"


def empty_detail(root, win):
    """상세 칸이 '포켓몬을 고르세요' 인가 (기본 창은 위젯, DP 계열은 캔버스)."""
    if hasattr(win, "_d"):
        SB.settle(root)
        texts = [win.dcv.itemcget(i, "text") for i in win.dcv.find_all() if win.dcv.type(i) == "text"]
        return win._d is None and "포켓몬을 고르세요" in texts
    return (not win._d_mon.winfo_manager() and not win._d_egg.winfo_manager()
            and win.d_name.cget("text") == "" and win.d_art.cget("text") == "포켓몬을 고르세요")


def shows(root, win, m):
    if hasattr(win, "_d"):
        SB.settle(root)
        return bool(win._d) and win._d["m"]["id"] == m["id"]
    return win._d_mon.winfo_manager() and win.d_name.cget("text") == m["info"]["name"]


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda *a: errors.append(str(a[1]))

    main_mon = SB.mon(dex, 1008, 41614, on=True)            # 미라이돈 - 파티 첫 칸
    party = [main_mon, SB.mon(dex, 25, 5002, on=True)]
    for i, m in enumerate(party):
        m["slot"] = i
    box = []
    for i, n in enumerate([129, 6, 143, 3, 94, 130]):
        m = SB.mon(dex, n, 6000 + i)
        m["box"] = 0
        box.append(m)
    app = SB.FakeApp(root, dex, party + box)
    api = app.api
    gate = {"ev": None}

    def release(pid):
        api.calls.append(("release1", pid))
        if gate["ev"] is not None:
            gate["ev"].wait(5)
        m = next((x for x in api.mons if x["id"] == pid), None)
        if m is None:
            raise RuntimeError("그런 포켓몬이 없습니다.")
        api.mons.remove(m)
        return {"ok": True}
    api.release = release
    ui_box.confirm_release = lambda parent, app_, mon: True          # 확인 창은 [놓아주기] 를 누른 것으로
    ui_box.confirm_release_many = lambda parent, mons, away=(): True

    cls = skins.override(ui_box.BoxWindow)
    print("테마: %s (%s)" % (skins.active() or "기본", cls.__module__))
    win = cls(root, app)
    win.win.geometry("990x668+20+20")
    SB.wait_for(root, lambda: getattr(win, "mons", None))
    SB.settle_rows(root, win)

    def released(pid):
        return SB.wait_for(root, lambda: all(m["id"] != pid for m in win.mons) and win._wait is None, 6)

    print("=== 1. 처음 열면 맨 앞 줄 ===")
    chk("처음에는 파티 첫 칸을 고른다 (예전 그대로)", win.sel == main_mon["id"], win.sel)

    print("\n=== 2. 놓아준 뒤 ===")
    win.select(box[0]["id"])
    SB.settle(root)
    chk("박스 포켓몬을 고르면 상세 칸에 그것", shows(root, win, box[0]))
    win.do_release()
    released(box[0]["id"])
    SB.settle(root)
    chk("놓아준 뒤 **아무것도 안 고른다** (파티 첫 칸이 저절로 골라지지 않는다)", win.sel is None, win.sel)
    chk("  [놓아주기] 단추가 꺼진다", not enabled(win.btn_release))
    chk("  상세 칸은 '포켓몬을 고르세요'", empty_detail(root, win))
    n = len(api.calls)
    win.do_release()
    SB.settle(root)
    chk("  그 상태에서 [놓아주기] 를 또 눌러도 서버에 안 간다", len(api.calls) == n, api.calls[n:])
    chk("  미라이돈은 그대로 있다", any(m["id"] == main_mon["id"] for m in api.mons))
    win._show(win.sel)                                      # 거르기 · 쪽 넘기기처럼 다시 그려도
    SB.settle(root)
    chk("  다시 그려도 저절로 고르지 않는다", win.sel is None, win.sel)

    print("\n=== 3. 다시 누르면 평소대로 ===")
    win.select(box[1]["id"])
    SB.settle(root)
    chk("누르면 골라지고 단추가 켜진다", win.sel == box[1]["id"] and enabled(win.btn_release) and shows(root, win, box[1]))
    win.do_release()
    released(box[1]["id"])
    SB.settle(root)
    chk("그것도 놓아주면 또 빈 모습", win.sel is None and not enabled(win.btn_release) and empty_detail(root, win), win.sel)

    print("\n=== 4. 요청이 도는 동안 다른 것을 누르면 ===")
    win.select(box[2]["id"])
    SB.settle(root)
    gate["ev"] = threading.Event()
    win.do_release()                                        # 서버 답이 늦다 (렉)
    SB.settle(root)
    win.select(party[1]["id"])                              # 그사이 피카츄를 눌렀다
    gate["ev"].set()
    released(box[2]["id"])
    gate["ev"] = None
    SB.settle(root)
    chk("그사이 누른 피카츄가 그대로 골라져 있다", win.sel == party[1]["id"] and shows(root, win, party[1]), win.sel)

    print("\n=== 5. 여러 마리 놓아주기 ===")
    win.select(box[3]["id"])
    SB.settle(root)
    win.enter_multi()
    SB.settle(root)
    for m in box[3:5]:
        win.toggle_check(m["id"])
    win.release_checked()
    SB.wait_for(root, lambda: not getattr(win, "_releasing", False) and win._wait is None
                and all(m["id"] not in (box[3]["id"], box[4]["id"]) for m in win.mons), 6)
    SB.settle(root)
    chk("고른 포켓몬이 여러 마리 놓아주기로 놓아지면 빈 모습", win.sel is None, win.sel)
    win.exit_multi()
    SB.settle(root)
    chk("  고르기를 꺼도 빈 모습 · 단추 꺼짐", win.sel is None and not enabled(win.btn_release) and empty_detail(root, win),
        win.sel)
    chk("  미라이돈은 끝까지 그대로", any(m["id"] == main_mon["id"] for m in api.mons))

    chk("창 오류 없음", not errors, errors[:3])
    try:
        win.close()
    except Exception:                                       # noqa: BLE001
        win.win.destroy()
    root.destroy()
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
