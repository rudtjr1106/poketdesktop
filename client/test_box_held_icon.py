# -*- coding: utf-8 -*-
"""박스 목록 이름 옆의 지닌 도구 그림 (2.5.8, 게시판 #898 '누구에게 무슨 도구를 지니게 했는지 기억이 안 난다') - 진짜 Tk.

    python client/test_box_held_icon.py

  1. 도구를 지닌 포켓몬 줄에만 그림이 붙는다 (안 지닌 줄 · 알 줄은 없다)
  2. 이름(과 성별 기호) 바로 뒤, 레벨 칸을 넘지 않는 자리
  3. 칸 폭을 바꾸면(relayout) 그림도 따라간다
  4. 지닌 도구가 바뀌면 줄을 새로 그린다 (_row_sig 에 든다)
  5. 그림 파일이 아직 없으면 그리지 않는다 (줄은 그대로) · 박스를 불러올 때 지닌 도구 그림을 받아 둔다
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "server", "data")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-box-held-"))

import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageTk                              # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import item_icons                         # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
import smoke_box_filter as SB                               # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    frame = tk.Frame(root)
    frame.pack()
    keep = {}

    def photo(item_id, size=28):
        if item_id == "NOFILE":
            return None
        ph = keep.get((item_id, size))
        if ph is None:
            ph = keep[(item_id, size)] = ImageTk.PhotoImage(Image.new("RGBA", (size, size), (200, 50, 50, 255)))
        return ph
    real = item_icons.photo
    item_icons.photo = photo
    try:
        print("=== 지닌 도구 그림 (#898)")
        m = SB.mon(dex, 25, 7001)
        m["held"] = "LIGHTBALL"
        row = ui_box.Row(frame, m, dex, lambda i: None)
        bare = ui_box.Row(frame, SB.mon(dex, 25, 7002), dex, lambda i: None)
        egg = dict(SB.mon(dex, 25, 7003), isEgg=True, egg={"kind": "legendary"}, held="LIGHTBALL")
        egg_row = ui_box.Row(frame, egg, dex, lambda i: None)
        root.update_idletasks()
        chk("1. 도구를 지닌 줄에 그림이 붙는다", row.held_icon is not None and row.held_icon in row.cells)
        chk("   안 지닌 줄 · 알 줄에는 없다", bare.held_icon is None and egg_row.held_icon is None)
        x = int(row.held_icon.place_info()["x"])
        name_end = row.cols[1][1] + row._name_px
        chk("2. 이름(과 성별 기호) 바로 뒤", x > name_end and (row.gender is None or x > int(row.gender.place_info()["x"])),
            (x, name_end))
        chk("   레벨 칸을 넘지 않는다", x + U.h(ui_box.HELD_ICON) <= row.cols[2][1], (x, row.cols[2][1]))
        long = SB.mon(dex, 25, 7004)
        long["held"] = "LIGHTBALL"
        long.setdefault("info", {})["name"] = "아주아주긴별명이에요"
        lrow = ui_box.Row(frame, long, dex, lambda i: None)
        lx = int(lrow.held_icon.place_info()["x"])
        chk("   이름이 길어도 레벨 칸 앞에 멈춘다", lx + U.h(ui_box.HELD_ICON) <= lrow.cols[2][1], (lx, lrow.cols[2][1]))

        wide = [list(c) for c in row.cols]
        wide[1][2] += 60
        wide[2][1] += 60
        row.relayout([tuple(c) for c in wide])
        chk("3. 칸 폭을 바꾸면 그림도 따라간다", int(row.held_icon.place_info()["x"]) == row._held_x(),
            (row.held_icon.place_info()["x"], row._held_x()))

        other = dict(m, held="LEFTOVERS")
        none = dict(m, held=None)
        chk("4. 지닌 도구가 바뀌면 줄을 새로 그린다", ui_box._row_sig(m) != ui_box._row_sig(other) != ui_box._row_sig(none))

        nofile = dict(SB.mon(dex, 25, 7005), held="NOFILE")
        nrow = ui_box.Row(frame, nofile, dex, lambda i: None)
        chk("5. 그림 파일이 아직 없으면 그리지 않는다", nrow.held_icon is None)
        import inspect
        src = inspect.getsource(ui_box.BoxWindow.reload)
        chk("   박스를 불러올 때 지닌 도구 그림을 받아 둔다", "item_icons.raw(api, held)" in src)
    finally:
        item_icons.photo = real
        root.destroy()

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
