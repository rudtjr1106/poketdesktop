# -*- coding: utf-8 -*-
"""DP 테마의 여러 개 팔기 창. 진짜 Tk 로 확인한다.

    python client/test_skin_dp_sell.py
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-dpsell-")
os.environ["POKET_SKIN"] = "dp"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_common as U, ui_sell     # noqa: E402

OK = FAIL = 0
ITEMS = [
    {"id": "STARDUST", "kr": "별가루", "cat": "etc", "sell": 1000, "cost": 2000},
    {"id": "PEARL", "kr": "진주", "cat": "etc", "sell": 700, "cost": 1400},
    {"id": "POKEBALL", "kr": "몬스터볼", "cat": "ball", "sell": 100, "cost": 200},
    {"id": "TM_LIKE", "kr": "못파는것", "cat": "etc", "sell": 0, "cost": 0},
]
BAG = {"STARDUST": 3, "PEARL": 5, "POKEBALL": 9, "TM_LIKE": 1}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def click(d, iid, part):
    """줄의 칸(dn/up/all/row)을 실제 클릭 경로로 누른다."""
    from poketdesktop.skins.dp import sell as DS
    w = d.vl.cv.winfo_width()
    dn, cnt, up, allb = DS._geo(w)
    x = {"dn": dn, "up": up, "all": allb}.get(part)
    x = (x[0] + x[1]) // 2 if x else 40
    d.vl._click_at = None
    d._click(iid, x, 10, w)


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    errs = []
    root.report_callback_exception = lambda e, v, tb: errs.append(repr(v))
    U.init_fonts(root)
    U.apply_theme(root)
    host = tk.Toplevel(root)
    host.geometry("300x200+20+20")
    root.update()

    from poketdesktop.skins.dp import sell as DS
    d = ui_sell.SellMany(host, root, ITEMS, BAG, money=1234)
    root.update()
    chk("DP 클래스로 뜬다", isinstance(d, DS.SellMany) and isinstance(d, ui_sell.SellMany), type(d))
    chk("팔 수 있는 두 줄 (진주 · 별가루)", list(d.rows) == ["PEARL", "STARDUST"] or set(d.rows) == {"PEARL", "STARDUST"},
        list(d.rows))
    chk("처음엔 고른 것 없음", "고른 것이 없습니다" in d.total.cget("text"), d.total.cget("text"))
    chk("가진 돈", "1,234" in d.hint.cget("text"), d.hint.cget("text"))
    chk("줄이 그려진다", len(d.vl.cv.find_withtag("row")) > 10)
    chk("줄 높이는 기본 창과 같다 (44)", d.vl.rows[0][0] == U.h(44), d.vl.rows[0][0])
    chk("단추 − + 는 글자 (줄마다 둘, pixelarticons 를 쓰지 않는다)",
        len([i for i in d.vl.cv.find_all() if d.vl.cv.type(i) == "text"
             and d.vl.cv.itemcget(i, "text") in ("−", "+")]) >= 4)
    chk("테두리 글씨가 없다 (같은 글을 여덟 겹 찍지 않는다)",
        len([i for i in d.vl.cv.find_all() if d.vl.cv.type(i) == "text"
             and d.vl.cv.itemcget(i, "text") == "전부"]) == 2)

    click(d, "STARDUST", "row")
    click(d, "STARDUST", "up")
    root.update()
    chk("줄 누르기 + (+) = 둘", d.pick.get("STARDUST") == 2, d.pick)
    chk("합계 2,000원", "2,000원" in d.total.cget("text"), d.total.cget("text"))
    chk("팔기 단추에 값", "2,000원" in d.ok_btn.text, d.ok_btn.text)
    click(d, "STARDUST", "dn")
    chk("(−) 는 하나 내린다", d.pick.get("STARDUST") == 1, d.pick)
    click(d, "PEARL", "all")
    chk("전부 = 가진 수", d.pick.get("PEARL") == 5, d.pick)
    for _ in range(6):
        click(d, "STARDUST", "up")
    chk("가진 수를 넘지 않는다", d.pick.get("STARDUST") == 3, d.pick)
    for _ in range(9):
        click(d, "STARDUST", "dn")
    chk("0 이면 고른 것에서 빠진다", "STARDUST" not in d.pick, d.pick)
    d.all_btn.invoke()
    chk("전부 고르기", d.pick == {"PEARL": 5, "STARDUST": 3}, d.pick)
    chk("  합계 6,500원", "6,500원" in d.total.cget("text"), d.total.cget("text"))
    d.none_btn.invoke()
    chk("고른 것 지우기", d.pick == {}, d.pick)

    d.ok_btn.invoke()
    chk("안 고르고 팔기: 창 안 닫힘 + 안내", d.win.winfo_exists() and d.result is None
        and "골라" in d.total.cget("text"), d.total.cget("text"))
    click(d, "PEARL", "up")
    click(d, "PEARL", "up")
    click(d, "STARDUST", "row")
    d.ok_btn.invoke()
    chk("고른 것을 돌려준다", d.result == [{"item": "PEARL", "count": 2}, {"item": "STARDUST", "count": 1}], d.result)
    chk("  창이 닫힌다", not d.win.winfo_exists())

    d2 = ui_sell.SellMany(host, root, ITEMS, BAG, money=0)
    root.update()
    d2.cancel_btn.invoke()
    chk("닫기는 None", d2.result is None and not d2.win.winfo_exists(), d2.result)

    d3 = ui_sell.SellMany(host, root, [], {}, money=0)
    root.update()
    texts = [d3.vl.cv.itemcget(i, "text") for i in d3.vl.cv.find_all() if d3.vl.cv.type(i) == "text"]
    chk("팔 것이 없으면 그렇게 말한다", any("팔 수 있는 물건이 없습니다" in t for t in texts), texts)
    d3._cancel()

    many = [{"id": "IT%d" % i, "kr": "물건%d" % i, "cat": "etc", "sell": 100 + i, "cost": 1} for i in range(50)]
    bag = dict(("IT%d" % i, 9) for i in range(50))
    real = PLAT.work_area
    try:
        PLAT.work_area = lambda w, h: (0, 0, 1024, 600)
        d4 = ui_sell.SellMany(host, root, many, bag, money=9999)
        root.update()
        root.update_idletasks()
        chk("창이 작업 영역에 맞는다", d4.win.winfo_height() <= 560, d4.win.winfo_height())
        fy = d4.foot.winfo_rooty() + d4.foot.winfo_height() - d4.win.winfo_rooty()
        chk("팔기 단추 줄이 창 안에 있다", fy <= d4.win.winfo_height(), (fy, d4.win.winfo_height()))
        chk("목록은 굴러간다", d4.vl.total > d4.vl.cv.winfo_height(), (d4.vl.total, d4.vl.cv.winfo_height()))
        d4._add("IT3", 1)
        d4._cancel()
    finally:
        PLAT.work_area = real

    chk("그리는 중 예외 없음", not errs, errs)
    print("\n합계 OK %d FAIL %d" % (OK, FAIL))
    root.destroy()


main()
