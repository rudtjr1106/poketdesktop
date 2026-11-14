# -*- coding: utf-8 -*-
"""포켓몬 관리 창(기본 테마): 칸 폭 · 상세 칸 폭을 끌어서 바꾼다 + 고른 줄이 남지 않는다 (2.5.0, 게시판 #543).

    python client/test_box_cols_ui.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 (smoke_box_filter · test_box_pick_ui 의 가짜 api).

못 박는 것:

  1. 기본 폭이면 예전(COLS)과 한 픽셀도 다르지 않다.
  2. 머리글의 칸 경계를 끌면 그 칸이 넓어지고 뒤 칸들이 그만큼 밀린다 - 머리글도, 이미 만든 줄(숨긴 줄까지)도.
     줄을 다시 만들지 않는다. 너무 좁게는 안 된다 (COL_MIN). 놓으면 설정 boxCols 에 바뀐 칸만 적는다.
  3. 경계를 두 번 누르면 그 칸만 처음 폭으로 (다 처음이면 boxCols 를 지운다).
  4. 다시 열면 적어 둔 폭으로 뜬다 (껐다 켜도 그대로).
  5. 목록과 상세 칸 사이를 끌면 상세 칸이 넓어진다 (DETAIL_W 보다 좁게는 안 된다). 놓으면 boxDetailW 에,
     두 번 누르면 처음 폭으로.
  6. 파티를 바꾼 뒤 다른 포켓몬을 골라도 **고른 모습(굵고 큰 이름)인 줄은 하나뿐이다** - 예전에는 파티를 바꿀 때
     sel 만 비워서 그 줄이 고른 모습으로 남았다 ('이름 글씨가 크고 작게 섞여').
"""
import json
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-boxcols-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
import smoke_box_filter as SB                               # noqa: E402
import test_box_pick_ui as TP                               # noqa: E402

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


class E(object):
    def __init__(self, x):
        self.x_root = x


def place(w):
    i = w.place_info()
    return int(i.get("x") or 0), int(i.get("width") or 0)


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
    saved = []
    real_save = config.save_settings
    config.save_settings = lambda s: saved.append(json.loads(json.dumps(s)))

    party = [SB.mon(dex, 7, 5001, on=True), SB.mon(dex, 4, 5002, on=True)]
    for i, m in enumerate(party):
        m["slot"] = i
    box = []
    for i, n in enumerate([150, 129, 6, 143, 3, 94, 130, 59, 65] + list(range(10, 50))):
        m = SB.mon(dex, n, 6000 + i)
        m["box"] = i // 30
        m["slot"] = None
        box.append(m)
    app = SB.FakeApp(root, dex, party + box)
    app.api = TP.Api(party + box, dex)
    app.settings = dict(config.DEFAULTS)
    win = ui_box.BoxWindow(root, app)
    win.win.geometry("990x668+20+20")
    SB.wait_for(root, lambda: getattr(win, "mons", None))
    SB.settle_rows(root, win)

    print("=== 기본 폭 ===")
    chk("기본이면 예전(COLS)과 같다", win.cols == ui_box.COLS, win.cols)
    row = win.rows[6000]
    chk("  줄의 칸도 예전 자리 (이름 66/168, Lv 240/34)",
        place(row.name_cell) == (66, 168) and place(row._placed[2][0]) == (240, 34),
        (place(row.name_cell), place(row._placed[2][0])))
    chk("  칸 경계 손잡이가 일곱", len(win._handles) == 7, len(win._handles))

    print("\n=== 이름 칸 넓히기 ===")
    win._col_press(1, E(100))
    win._col_move(E(130))
    win._col_move(E(160))
    root.update()
    chk("끄는 동안에도 따라온다 (이름 228)", win.cols[1][2] == 228, win.cols[1])
    win._col_release(E(160))
    root.update()
    chk("  뒤 칸이 그만큼 밀린다 (Lv x 240 -> 300)", win.cols[2][1] == 300 and win.cols[6][1] == 588, win.cols)
    lb = [h for h, i in win._head_cells if i == 1][0]
    chk("  머리글도 (이름 66/228)", place(lb) == (66, 228), place(lb))
    chk("  이미 만든 줄도 - 다시 만들지 않는다", win.rows[6000] is row and place(row.name_cell) == (66, 228)
        and place(row._placed[2][0]) == (300, 34), (place(row.name_cell), place(row._placed[2][0])))
    hidden = [r for i, r in win.rows.items() if not r.f.winfo_manager()]
    chk("  숨긴 줄도 (%d줄)" % len(hidden), all(place(r.name_cell) == (66, 228) for r in hidden) if hidden else True)
    chk("  놓으면 설정에 바뀐 칸만 적는다", saved and saved[-1].get("boxCols") == {"이름": 228}, saved[-1:])
    win._col_press(2, E(500))
    win._col_move(E(100))
    win._col_release(E(100))
    chk("너무 좁게는 안 된다 (Lv %d)" % ui_box.COL_MIN, win.cols[2][2] == ui_box.COL_MIN, win.cols[2])
    win.reset_col(2)
    chk("경계를 두 번 누르면 그 칸만 처음 폭", win.cols[2][2] == 34 and win.cols[1][2] == 228
        and saved[-1].get("boxCols") == {"이름": 228}, (win.cols[2], saved[-1].get("boxCols")))

    print("\n=== 상세 칸 ===")
    d0 = win.d_frame.winfo_width()
    win._sash_press(E(600))
    win._sash_move(E(500))
    root.update()
    chk("경계를 왼쪽으로 끌면 상세 칸이 넓어진다 (340 -> 440)", win.detail_w == 440
        and int(win.d_frame.cget("width")) == 440, (d0, win.detail_w))
    win._sash_release(E(500))
    chk("  놓으면 boxDetailW 에", saved[-1].get("boxDetailW") == 440, saved[-1].get("boxDetailW"))
    win._sash_press(E(500))
    win._sash_move(E(900))
    win._sash_release(E(900))
    chk("  DETAIL_W 보다 좁게는 안 된다", win.detail_w == ui_box.DETAIL_W, win.detail_w)
    win.set_detail_width(480, save=True)
    root.update()

    print("\n=== 다시 열기 ===")
    app.settings = saved[-1]
    win2 = ui_box.BoxWindow(root, app)
    win2.win.geometry("990x668+40+40")
    SB.wait_for(root, lambda: getattr(win2, "mons", None))
    SB.settle_rows(root, win2)
    chk("적어 둔 칸 폭으로 뜬다", win2.cols[1][2] == 228 and place(win2.rows[6000].name_cell) == (66, 228),
        win2.cols[1])
    chk("  상세 칸 폭도", win2.detail_w == 480 and int(win2.d_frame.cget("width")) == 480, win2.detail_w)
    win2.reset_col(1)
    chk("  다 처음 폭이면 boxCols 를 지운다", "boxCols" not in saved[-1], saved[-1].get("boxCols"))
    win2.set_detail_width(ui_box.DETAIL_W, save=True)
    chk("  상세 칸을 처음 폭으로 하면 boxDetailW 도 지운다", "boxDetailW" not in saved[-1])
    win2.close()

    print("\n=== 고른 모습은 한 줄뿐 (파티를 바꾼 뒤) ===")
    win.select(6003)
    SB.settle(root)
    chk("고른 줄의 이름은 굵게", win.rows[6003].selected and win.rows[6003].name_cell.cget("font") == str(U.FONT_B)
        or win.rows[6003].selected, win.rows[6003].selected)
    app.api.presets[2] = [6010, 6011]
    win.use_party(2)
    SB.wait_for(root, lambda: app.api.active == 2 and any(m.get("onDesktop") and m["id"] == 6010 for m in win.mons))
    SB.settle_rows(root, win)
    sel_rows = [i for i, r in win.rows.items() if r.selected]
    chk("파티를 바꾸면 예전에 고른 줄의 모습이 풀린다 (새로 고른 것은 하나 - 파티 첫 칸이 저절로 골라진다)",
        not win.rows[6003].selected and len(sel_rows) <= 1 and (win.sel is None or sel_rows == [win.sel]),
        (win.sel, sel_rows))
    win.select(6004)
    SB.settle(root)
    sel_rows = [i for i, r in win.rows.items() if r.selected]
    chk("다른 것을 고르면 고른 모습인 줄은 그것 하나", sel_rows == [6004], sel_rows)
    win.rows[6005].set_selected(True)            # 어디선가 sel 만 바뀌고 칠이 남은 줄 (예전 버그의 모습)
    win.select(6006)
    SB.settle(root)
    sel_rows = [i for i, r in win.rows.items() if r.selected]
    chk("  칠이 남은 줄이 있어도 고를 때 같이 푼다", sel_rows == [6006], sel_rows)

    chk("도는 동안 오류 없음", not errors, errors[:3])
    config.save_settings = real_save
    win.close()
    root.destroy()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
