# -*- coding: utf-8 -*-
"""탐험 탭 '누구를' 목록의 찾기 · 줄 세우기 검사.

    python client/test_expedition_find.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 (test_expedition_ui 의 가짜 api). 박스에 수십 마리가 있으면
보낼 포켓몬을 끝까지 굴려 찾아야 했다. 가방·기술머신과 같은 한 줄(ui_monfind.FindBar)을 붙였다. 못 박는 것:

  1. 기본은 예전 그대로 (잘할 차례). 가나다순 · 레벨순(높은 것부터)으로 줄 세운다.
  2. 찾기는 별명 · 종 이름 · 도감 번호 (포켓몬 관리 창과 같은 규칙). 몇 마리인지 적는다.
  3. 고른 포켓몬이 가려지면 보이는 것 중에서(보낼 수 있는 것 먼저) 다시 고른다. 하나도 안 맞으면
     안내가 뜨고 아무도 안 고르며 보내기가 잠긴다 - 안 보이는 포켓몬이 나가면 안 된다.
  4. 찾은 뒤 고른 포켓몬이 서버로 간다 (보낸 포켓몬은 목록에서 빠지고 찾는 말은 남는다).
  5. 곳을 바꿔도 찾는 말 · 순서는 그대로다 (잘할 차례만 바뀐다).
  6. 찾기 줄이 단 안에 다 들어간다 (가장 좁은 창에서도 잘리지 않는다).
"""
import json
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-expfind-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from common import expedition as X                          # noqa: E402
from common import pokelogic as P                           # noqa: E402
from poketdesktop import box_filter                         # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_expedition as UE                # noqa: E402
import test_expedition_ui as TE                             # noqa: E402

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


def ids(w):
    return [m["id"] for m, _p, _g in w._cands]


def names(w):
    return [box_filter.name_of(m) for m, _p, _g in w._cands]


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-500:])
    root.report_callback_exception = on_err

    from poketdesktop import expedition_ui as XU
    api = TE.FakeApi(dex, 40)
    box = [m for m in api.mons if not m.get("onDesktop")]
    pika = next(m for m in box if m["num"] not in (25,))
    pika["nickname"] = pika["info"]["name"] = "번개불"         # 별명을 지은 포켓몬 - 종 이름으로도 찾혀야 한다
    app = TE.FakeApp(root, api, dex)
    app.expedition = XU.Desk(app)
    w = UE.ExpeditionWindow(app)
    w.win.winfo_toplevel().deiconify()
    TE.pump(root, lambda: w.state is not None and w._wait is None and w.vl.shown())
    TE.rest(root, 0.3)
    bar = w.find
    base = UE.candidates(api.pokemon(), dex, w.place)

    print("=== 줄 세우기")
    chk("찾기 칸과 [기본 | 가나다순 | 레벨순] 이 있다",
        [c.cget("text") for c in bar.seg.cells.values()] == ["기본", "가나다순", "레벨순"])
    chk("  처음엔 잘할 차례 그대로 (예전과 같다)", ids(w) == [m["id"] for m, _p, _g in base] and len(base) == 40, ids(w)[:4])
    bar.pick_sort("name")
    TE.rest(root, 0.2)
    chk("가나다순", names(w) == sorted(names(w)) and len(w._cands) == 40, names(w)[:4])
    shown = [r.name.cget("text").replace("★ ", "") for _p, r in w.shown()]
    chk("  보이는 줄도 그 순서", len(shown) >= 4 and shown == names(w)[:len(shown)], shown[:3])
    bar.pick_sort("level")
    TE.rest(root, 0.2)
    lv = [m["level"] for m, _p, _g in w._cands]
    chk("레벨순 (높은 것부터)", lv == sorted(lv, reverse=True) and len(lv) == 40, lv[:5])
    chk("  누른 칸이 칠해진다", bar.seg.current == "level")
    chk("  고른 포켓몬은 보이는 것 중에 있다", w.pick in ids(w), w.pick)

    print("\n=== 찾기")
    bar.pick_sort("")
    bar.q.set("번개불")
    TE.rest(root, 0.2)
    chk("별명으로 찾는다", ids(w) == [pika["id"]] and w.pick == pika["id"], ids(w))
    sp = dex.get(pika["species"])["kr"]
    bar.q.set(sp)
    TE.rest(root, 0.2)
    chk("별명을 지었어도 종 이름으로 찾힌다", pika["id"] in ids(w), (sp, ids(w)))
    chk("  '%d마리' 라고 적는다" % len(ids(w)), bar.count.cget("text") == "%d마리" % len(ids(w)), bar.count.cget("text"))
    chk("  찾은 것은 다 그 종이다", all(m["species"] == pika["species"] for m, _p, _g in w._cands), ids(w))
    num = base[3][0]["num"]
    bar.q.set(str(num))
    TE.rest(root, 0.2)
    want = [m["id"] for m, _p, _g in base if box_filter.pick_view([m], dex, str(num))]
    chk("도감 번호로 찾는다", ids(w) == want and base[3][0]["id"] in ids(w), (ids(w), want))
    chk("  보이는 줄은 찾은 것만 (줄을 다시 만들어 채웠다)", len(w.vl.entries) == len(want), len(w.vl.entries))

    print("\n=== 가려진 것을 골랐을 때")
    bar.q.set("")
    TE.rest(root, 0.2)
    far = base[-1][0]["id"]
    w.pick_mon(far)
    bar.q.set("번개불")
    TE.rest(root, 0.2)
    chk("고른 포켓몬이 가려지면 보이는 것 중에서 다시 고른다", w.pick == pika["id"] and w._picked() is not None, w.pick)
    bar.q.set("")
    TE.rest(root, 0.2)
    w.pick_mon(far)
    bar.q.set(str(num))
    TE.rest(root, 0.2)
    chk("  보이는 것이 여럿이면 보낼 수 있는 것 중 맨 위", w.pick == ids(w)[0], (w.pick, ids(w)))
    bar.q.set("없는포켓몬")
    TE.rest(root, 0.2)
    chk("하나도 안 맞으면 목록 자리에 안내", ids(w) == [] and "없는포켓몬" in w.empty.cget("text")
        and w.empty.winfo_manager() == "place", w.empty.cget("text"))
    chk("  아무도 안 고르고 보내기가 잠긴다", w.pick is None and w._summary_data()[4] is False, (w.pick, w._summary_data()))
    n = len(api.out)
    w.do_send()
    TE.rest(root, 0.3)
    chk("  눌러도 아무도 안 나간다 (안 보이는 포켓몬을 보내지 않는다)", len(api.out) == n, api.calls[-2:])
    chk("  '0마리'", bar.count.cget("text") == "0마리", bar.count.cget("text"))

    print("\n=== 찾은 뒤 보내기")
    bar.q.set("번개불")
    TE.rest(root, 0.2)
    w.do_send()
    TE.pump(root, lambda: any(o["pid"] == pika["id"] for o in api.out))
    TE.rest(root, 0.3)
    chk("찾은 포켓몬이 서버로 간다", any(o["pid"] == pika["id"] for o in api.out)
        and ("send", pika["id"], w.place, w.hours) in api.calls, api.calls[-2:])
    chk("  나간 포켓몬은 목록에서 빠지고, 찾는 말은 그대로", pika["id"] not in ids(w) and bar.q.get() == "번개불"
        and w.empty.winfo_manager() == "place", (ids(w), bar.q.get()))
    bar.q.set("")
    TE.rest(root, 0.2)

    print("\n=== 곳을 바꿔도")
    bar.pick_sort("name")
    bar.q.set("이")
    TE.rest(root, 0.2)
    before = ids(w)
    w.set_place("sea")
    TE.rest(root, 0.2)
    chk("찾는 말 · 순서가 그대로다 (같은 포켓몬이 같은 순서로)", bar.q.get() == "이" and bar.sort == "name"
        and ids(w) == before and w.pick in ids(w), (bar.q.get(), bar.sort))
    chk("  점수는 새 곳 기준으로 다시 셈한다", all(p == X.score(m["level"], UE.types_of(dex, m), "sea") for m, p, _g in w._cands))
    bar.q.set("")
    bar.pick_sort("")
    TE.rest(root, 0.2)
    chk("지우고 기본으로 되돌리면 잘할 차례로 돌아온다",
        ids(w) == [m["id"] for m, _p, _g in UE.candidates(api.pokemon(), dex, w.place)], ids(w)[:3])

    print("\n=== 한 줄이 칸 안에")
    top = w.win.winfo_toplevel()
    for geo in ("1020x664", "980x%d" % (620 - U.h(30))):
        top.geometry(geo)
        TE.rest(root, 0.4)
        f = bar.frame
        cells = list(bar.seg.cells.values())
        fx = f.winfo_rootx()
        ok = (all(c.winfo_width() >= c.winfo_reqwidth() - 1 for c in cells)
              and bar.seg.frame.winfo_rootx() + bar.seg.frame.winfo_width() <= fx + f.winfo_width() + 1
              and bar.box.winfo_rootx() + bar.box.winfo_width() <= fx + f.winfo_width() + 1
              and TE.squeezed(w.body) == [])
        chk("  %s 에서도 찾기 줄이 안 잘리고 눌린 위젯이 없다" % geo, ok,
            (f.winfo_width(), [c.winfo_width() for c in cells], TE.squeezed(w.body)[:3]))
    chk("  가장 낮은 창에서 목록이 네 줄 넘게 보인다 (찾기 줄이 두 줄이라도)",
        len(w.shown()) >= (4 if U.TEXT_SIZE == 0 else 3), len(w.shown()))

    w.close()
    chk("콜백 예외가 없다", not errors, errors[:2])
    try:
        root.destroy()
    except tk.TclError:
        pass
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
