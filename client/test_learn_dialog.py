# -*- coding: utf-8 -*-
"""기술 배우기 창 검사.

    python client/test_learn_dialog.py

**창을 진짜로 띄운다.** 화면이 있어야 돌아간다(CI 의 맥·윈도우 잡).

## 무엇을 못 박나

기술 다섯 개를 늘어놓고 하나를 버리게 하는 창이다. 여기서 잘리면
사용자는 **무엇을 버리는지 모른 채** 버리게 된다.

  1. 눌린 위젯이 없다 - 설명이 몇 줄로 접힐지는 글꼴에 달렸고 글꼴은
     OS 마다 다르다. 맥에서 맞춘 높이가 윈도우(맑은 고딕)에서 맞으리라는
     보장이 없다. 선물 창이 실제로 그 이유로 잘렸었다.
  2. 다섯 줄 모두에 이름·분류·설명이 있다.
  3. 창이 화면 안에 들어온다. 넘치면 굴릴 수 있어야 한다.
  4. 고르고 누른 답이 맞다 (새 기술을 고르면 '안 배운다').

## 왜 가장 긴 설명으로 재나

설명은 15~68자로 제각각이다. 짧은 것만 넣어 보면 늘 통과한다.
그래서 도감에서 **가장 긴 것 다섯 개**를 골라 한 창에 몰아넣는다.
"""
import json
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-test-learn"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from common import movetext as MT                           # noqa: E402
from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_learn                           # noqa: E402

OK = FAIL = 0
DEX_PATH = os.path.join(ROOT, "server", "data", "pokedex.json")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def squeezed(win):
    """필요한 크기보다 작게 그려진 위젯. 있으면 글이 잘려 있다는 뜻이다."""
    out = []

    def walk(w):
        for c in w.winfo_children():
            try:
                rw, rh = c.winfo_reqwidth(), c.winfo_reqheight()
                aw, ah = c.winfo_width(), c.winfo_height()
                # 1x1 은 아직 안 그려진 것이다. 굴러가는 칸(Canvas)은
                # 원래 내용보다 작게 잘라 보여주는 것이라 뺀다.
                if aw > 1 and ah > 1 and c.winfo_class() != "Canvas":
                    if rh > ah + 1:
                        out.append(("세로", c.winfo_class(),
                                    str(c.cget("text"))[:18]
                                    if "text" in c.keys() else "", rh, ah))
                    if rw > aw + 1:
                        out.append(("가로", c.winfo_class(),
                                    str(c.cget("text"))[:18]
                                    if "text" in c.keys() else "", rw, aw))
            except Exception:                               # noqa: BLE001
                pass
            walk(c)
    walk(win)
    return out


def texts(win):
    """창 안의 모든 글."""
    out = []

    def walk(w):
        for c in w.winfo_children():
            try:
                if "text" in c.keys():
                    t = str(c.cget("text"))
                    if t:
                        out.append(t)
            except Exception:                               # noqa: BLE001
                pass
            walk(c)
    walk(win)
    return out


def build(root, dex, new_move, known, hold=500):
    """창을 띄우고 재고 닫는다. (눌린 것, 크기, 글, 창) 을 돌려준다."""
    box = {}

    def snap():
        d = box.get("ask")
        if d is None or not d.win.winfo_exists():
            return
        root.update_idletasks()
        box["sq"] = squeezed(d.win)
        box["size"] = (d.win.winfo_width(), d.win.winfo_height())
        box["texts"] = texts(d.win)
        box["rows"] = dict(d.rows)
        # 굴러가는 칸이 내용을 다 보여주고 있나
        box["seen"] = d.canvas.winfo_height()
        box["need"] = d.box.winfo_reqheight()
        d.win.destroy()

    d = ui_learn.ForgetAsk(root, "피카츄", new_move, known, dex)
    box["ask"] = d
    root.after(hold, snap)
    d.show()
    return (box.get("sq", []), box.get("size", (0, 0)),
            box.get("texts", []), box.get("rows", {}),
            box.get("seen", 0), box.get("need", 0))


def main():
    if not os.path.exists(DEX_PATH):
        print("도감 파일이 없습니다:", DEX_PATH)
        return 1
    with open(DEX_PATH, encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)"
          % (U.FAMILY, U.FONT[1], U.BASE_PT))

    moves = dex.moves
    # 가장 긴 설명 다섯 개. 짧은 것만 넣어 보면 늘 통과한다.
    longest = sorted(moves, key=lambda k: -len(moves[k].get("desc") or ""))[:5]
    print("\n=== 가장 긴 설명 다섯 개 (%s)"
          % ", ".join("%s %d자" % (moves[k]["kr"], len(moves[k]["desc"]))
                      for k in longest))
    sq, size, tx, rows, seen, need = build(root, dex, longest[0], longest[1:])
    chk("창이 떴다", size[0] > 100 and size[1] > 100, size)
    chk("눌린 것이 없다", not sq, sq[:4])
    chk("다섯 줄이 다 있다", len(rows) == 5, list(rows))
    for k in longest:
        chk("%s 설명이 실렸다" % moves[k]["kr"],
            moves[k]["desc"] in tx, moves[k]["kr"])
    chk("창이 화면 안에 있다", size[1] <= root.winfo_screenheight(),
        (size[1], root.winfo_screenheight()))
    # **창이 내용만큼 커져야 한다.** 굴러가는 칸에 담아 두면 창은 그 안에
    # 무엇이 얼마나 들었는지 모른다. 안 키우면 두 줄만 보이고 나머지는
    # 굴려야 나오는데, 비교하라고 만든 창에서 그러면 안 된다.
    room = root.winfo_screenheight() - ui_learn.SCREEN_PAD
    if need <= room:
        chk("다섯 줄이 다 보인다 (굴릴 필요 없다)", seen >= need,
            "보이는 %d < 필요한 %d" % (seen, need))
    else:
        print("  건너뜀 화면이 작아 굴려야 한다 (필요 %d > 자리 %d)"
              % (need, room))

    print("\n=== 분류가 보인다 (물리·특수·변화 한 창에)")
    # 분류가 다른 것만 골라 담는다. 셋이 다 나와야 한다.
    trio = ["SCRATCH", "THUNDERBOLT", "SWORDSDANCE", "SURF"]
    sq, size, tx, rows, seen, need = build(root, dex, "FLAMETHROWER", trio)
    chk("눌린 것이 없다", not sq, sq[:4])
    for want in ("물리", "특수", "변화"):
        chk("'%s' 가 화면에 있다" % want, want in tx, want)
    # 위력·명중·PP 도 같은 줄에 있어야 고를 수 있다.
    chk("위력이 보인다", any("위력" in t for t in tx), tx[:6])
    chk("PP 가 보인다", any("PP" in t for t in tx), tx[:6])
    chk("'위력 0' 이 없다", not any("위력 0" in t for t in tx), tx)
    chk("'명중 0' 이 없다", not any("명중 0" in t for t in tx), tx)
    # 변화 기술 줄에 위력 칸이 생기면 안 된다.
    sd = MT.stat_line(moves["SWORDSDANCE"])
    chk("검무 줄에 위력이 없다", "위력" not in sd, sd)

    print("\n=== 고른 답 ===")
    d = ui_learn.ForgetAsk(root, "피카츄", "FLAMETHROWER", trio, dex)
    root.after(300, lambda: (d._pick("SCRATCH"), d._ok()))
    chk("고른 기술을 돌려준다", d.show() == "SCRATCH", d.result)

    d = ui_learn.ForgetAsk(root, "피카츄", "FLAMETHROWER", trio, dex)
    root.after(300, lambda: (d._pick("FLAMETHROWER"), d._ok()))
    chk("새 기술을 고르면 '안 배운다'", d.show() == "", repr(d.result))

    d = ui_learn.ForgetAsk(root, "피카츄", "FLAMETHROWER", trio, dex)
    root.after(300, d._cancel)
    chk("그냥 닫으면 아무것도 안 한다", d.show() is None, repr(d.result))

    d = ui_learn.ForgetAsk(root, "피카츄", "FLAMETHROWER", trio, dex)
    root.after(300, lambda: (d._ok(), d._cancel()))
    chk("아무것도 안 고르고 누르면 안 닫힌다", d.show() is None, repr(d.result))

    print("\n=== 도감이 없어도 뜬다 ===")
    # 도감을 아직 못 받은 채로 레벨업이 끝날 수 있다.
    sq, size, tx, rows, seen, need = build(root, None, "FLAMETHROWER", trio)
    chk("창이 떴다", size[0] > 100, size)
    chk("눌린 것이 없다", not sq, sq[:4])
    chk("다섯 줄이 다 있다", len(rows) == 5, list(rows))

    root.destroy()
    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
