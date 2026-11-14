# -*- coding: utf-8 -*-
"""여러 개 팔기의 분류 칩 (2.5.0, 게시판 #522). 진짜 Tk 로 확인한다.

    python client/test_sell_groups.py        기본 테마
    python client/test_sell_groups.py dp     DP 테마

못 박는 것:

  1. 칩은 전체 + 가방에 있는 분류만, 정해 둔 차례로 (지닌 도구 · 열매 · 폼 도구 · 진화의 돌 …).
     **열매는 따로** - 지닌 도구(오랭열매)든 노력치(시몬열매)든 '열매' 칩으로 간다. 모르는 분류는 기타.
  2. 칩을 누르면 그 분류의 줄만 보인다. 전체를 누르면 다시 다 보인다.
  3. '전부 고르기' 는 **지금 보이는 분류만** 고른다. 판매 제외(★)는 여전히 빠진다.
  4. 고른 것과 합계는 분류를 바꿔도 남는다. 팔기는 보이지 않는 분류에서 고른 것까지 다 보낸다.
  5. 분류가 하나뿐이면 칩을 안 그린다 (전체 하나만 있는 칩은 쓸모가 없다).
"""
import os
import sys
import tempfile

SKIN = sys.argv[1] if len(sys.argv) > 1 else ""
os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-sellgroups-")
if SKIN:
    os.environ["POKET_SKIN"] = SKIN
else:
    os.environ.pop("POKET_SKIN", None)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_common as U, ui_sell     # noqa: E402

OK = FAIL = 0
ITEMS = [
    {"id": "LEFTOVERS", "kr": "먹다남은음식", "cat": "held", "sell": 2000},
    {"id": "CHOICEBAND", "kr": "구애머리띠", "cat": "held", "sell": 3000},
    {"id": "ORANBERRY", "kr": "오랭열매", "cat": "held", "sell": 50},
    {"id": "POMEGBERRY", "kr": "시몬열매", "cat": "ev", "sell": 100},
    {"id": "HPUP", "kr": "맥스업", "cat": "ev", "sell": 4900},
    {"id": "GRACIDEA", "kr": "그라시데아꽃", "cat": "form", "sell": 500},
    {"id": "FIRESTONE", "kr": "불꽃의돌", "cat": "stone", "sell": 1500},
    {"id": "STARDUST", "kr": "별가루", "cat": "etc", "sell": 1000},
    {"id": "POKEBALL", "kr": "몬스터볼", "cat": "ball", "sell": 100},
]
BAG = dict((it["id"], 3) for it in ITEMS)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def shown(d):
    """화면에 보이는 줄 (테마마다 다르게 담는다)."""
    if hasattr(d, "vl"):
        return [iid for _h, iid in d.vl.rows if iid]
    return [iid for iid, (f, _c, _h, _p) in d.rows.items() if f.winfo_manager()]


def main():
    PLAT.before_tk()
    if SKIN:
        skins.register_fonts()
    root = tk.Tk()
    errs = []
    root.report_callback_exception = lambda e, v, tb: errs.append(repr(v))
    U.init_fonts(root)
    U.apply_theme(root)
    host = tk.Toplevel(root)
    host.geometry("300x200+20+20")
    root.update()
    print("테마:", SKIN or "기본")

    print("=== 칩 ===")
    G = ui_sell.group_of
    chk("열매는 지닌 도구든 노력치든 '열매'", G(ITEMS[2]) == "berry" and G(ITEMS[3]) == "berry")
    chk("모르는 분류(etc)는 기타", G(ITEMS[7]) == "misc")
    d = ui_sell.SellMany(host, root, ITEMS, BAG, money=0, keep={"CHOICEBAND"})
    root.update()
    keys = [k for k, _l in ui_sell.groups(d.lines)]
    chk("칩: 전체 + 있는 분류만, 정한 차례 (몬스터볼은 안 팔아서 볼 칩 없음)",
        keys == ["all", "held", "berry", "form", "stone", "ev", "misc"], keys)
    names = dict(ui_sell.groups(d.lines))
    chk("이름: 지닌 도구 · 열매 · 폼 도구 · 진화의 돌 · 노력치 · 기타",
        [names[k] for k in keys[1:]] == ["지닌 도구", "열매", "폼 도구", "진화의 돌", "노력치", "기타"], names)
    if SKIN:
        chk("DP: 칩 단추가 머리에 그려진다", len(d.chip_btns) == len(keys) and all(b.box for b in d.chip_btns),
            [(b.text, b.box) for b in d.chip_btns])
        chk("  고른 칩(전체)만 파랑", [b.key for b in d.chip_btns if b.kind == "blue"] == ["all"])
    else:
        chk("기본: 칩이 담겼다", d.chips is not None and set(d.chips.cells) == set(keys))
        chk("  고른 칩(전체)만 금색", [k for k, lb in d.chips.cells.items() if lb.cget("bg") == U.ACCENT] == ["all"])
    all_ids = shown(d)
    chk("처음엔 다 보인다 (8줄)", sorted(all_ids) == sorted(i["id"] for i in ITEMS if i["id"] != "POKEBALL"), all_ids)

    print("=== 분류 고르기 ===")
    d.set_group("held")
    root.update()
    chk("지닌 도구: 열매는 빠지고 둘만", sorted(shown(d)) == ["CHOICEBAND", "LEFTOVERS"], shown(d))
    if SKIN:
        chk("  칩 빛깔이 바뀐다", [b.key for b in d.chip_btns if b.kind == "blue"] == ["held"])
    else:
        chk("  칩 빛깔이 바뀐다", [k for k, lb in d.chips.cells.items() if lb.cget("bg") == U.ACCENT] == ["held"])
    d._all()
    chk("'전부 고르기' 는 보이는 것만, 판매 제외(구애머리띠)는 빼고", d.pick == {"LEFTOVERS": 3}, d.pick)
    d.set_group("berry")
    root.update()
    chk("열매: 오랭열매 · 시몬열매", sorted(shown(d)) == ["ORANBERRY", "POMEGBERRY"], shown(d))
    chk("  분류를 바꿔도 고른 것은 남는다", d.pick == {"LEFTOVERS": 3}, d.pick)
    d._all()
    chk("  열매에서 '전부 고르기'", d.pick == {"LEFTOVERS": 3, "ORANBERRY": 3, "POMEGBERRY": 3}, d.pick)
    chk("  합계는 다른 분류에서 고른 것까지", "3가지 9개" in d.total.cget("text"), d.total.cget("text"))
    d.set_group("all")
    root.update()
    chk("전체로 돌아오면 다 보인다", sorted(shown(d)) == sorted(all_ids), shown(d))
    d.set_group("form")
    root.update()
    d._ok()
    chk("팔기는 보이지 않는 분류에서 고른 것까지 다 보낸다",
        d.result == [{"item": "LEFTOVERS", "count": 3}, {"item": "ORANBERRY", "count": 3},
                     {"item": "POMEGBERRY", "count": 3}], d.result)

    print("=== 분류가 하나 ===")
    one = [it for it in ITEMS if it["cat"] == "held" and not it["id"].endswith("BERRY")]
    d2 = ui_sell.SellMany(host, root, one, BAG, money=0)
    root.update()
    if SKIN:
        chk("칩을 안 그린다", d2.chip_btns == [])
    else:
        chk("칩을 안 그린다", d2.chips is None)
    d2._all()
    chk("  '전부 고르기' 는 예전처럼 다", d2.pick == {"LEFTOVERS": 3, "CHOICEBAND": 3}, d2.pick)
    d2._cancel()

    chk("도는 동안 오류 없음", not errs, errs[:3])
    root.destroy()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
