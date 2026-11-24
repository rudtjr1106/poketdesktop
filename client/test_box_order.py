# -*- coding: utf-8 -*-
"""박스 안 순서 (2.5.7, 11/24 게시판 #830 정지우 '박스 안에서만 도감순 · 이름순으로') - 화면 없이.

    python client/test_box_order.py

  1. box_filter.box_order: 잡은 순(빈 값)은 받은 그대로 · 도감순 · 이름순 · 레벨순 · 알은 맨 앞 그대로 · 모르는 값은 그대로
  2. 박스 창: 지금 박스의 줄만 그 순서로 (다른 박스 것은 안 섞인다) · 머리글 정렬(전체 보기)은 예전 그대로
  3. 이름표 메뉴: 박스 목록 아래에 '박스 안 순서' 제목 + 네 가지, 지금 것에 표시
  4. 고르면 설정 boxOrder 에 적고 저장 · 다시 그린다 · 이상한 값은 잡은 순
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-box-order-"))

from common import pokelogic as P                           # noqa: E402
from poketdesktop import box_filter as BF                   # noqa: E402
from poketdesktop import config                             # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


with open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8") as f:
    DEX = P.Pokedex(json.load(f))


def mon(pid, num, name, level, box=0, egg=False):
    m = {"id": pid, "num": num, "species": name, "level": level, "box": box, "info": {"name": name}}
    if egg:
        m["isEgg"] = True
    return m


# 잡은 순(id): 피카츄 · 이상해씨 · 갸라도스 · 꼬부기 · (알) · 다른 박스의 뮤
BOX0 = [mon(1, 25, "피카츄", 30), mon(2, 1, "이상해씨", 50), mon(3, 130, "갸라도스", 20),
        mon(4, 7, "꼬부기", 70), mon(-9, 0, "알", 1, egg=True)]
OTHER = [mon(5, 151, "뮤", 99, box=1)]


def ids(ms):
    return [m["id"] for m in ms]


def main():
    print("=== 박스 안 순서 (#830)")
    chk("1. 잡은 순(빈 값)은 받은 그대로", ids(BF.box_order(BOX0, DEX, "")) == [1, 2, 3, 4, -9])
    chk("   도감순 · 알은 맨 앞", ids(BF.box_order(BOX0, DEX, "num")) == [-9, 2, 4, 1, 3],
        ids(BF.box_order(BOX0, DEX, "num")))
    chk("   이름순 (가나다)", ids(BF.box_order(BOX0, DEX, "name")) == [-9, 3, 4, 2, 1],
        ids(BF.box_order(BOX0, DEX, "name")))
    chk("   레벨순 (높은 것부터)", ids(BF.box_order(BOX0, DEX, "level")) == [-9, 4, 2, 1, 3],
        ids(BF.box_order(BOX0, DEX, "level")))
    chk("   모르는 값은 그대로 · 받은 목록은 안 바뀐다", ids(BF.box_order(BOX0, DEX, "zzz")) == [1, 2, 3, 4, -9]
        and ids(BOX0) == [1, 2, 3, 4, -9])
    chk("   기본 설정은 잡은 순", config.DEFAULTS.get("boxOrder") == "")

    from poketdesktop import ui_box as UB
    saved = []

    class Q(object):
        def get(self):
            return ""
    w = UB.BoxWindow.__new__(UB.BoxWindow)
    w.app = type("A", (), {"dex": DEX, "settings": {"boxOrder": "num"}})()
    w.mons = BOX0 + OTHER
    w.f_type, w.f_query, w.sort, w.box_no, w.rank_page = None, Q(), None, 0, 0
    w._paint_page = lambda total: None
    w.box_size = lambda: 30
    w.box_count = lambda: 2
    w.box_name = lambda no: "박스 %d" % (no + 1)
    w.box_used = lambda no: sum(1 for m in w.mons if int(m.get("box") or 0) == no)
    w._save_settings = lambda: saved.append(dict(w.app.settings))
    shown = []
    w._show = lambda keep=None: shown.append(True)
    w.say = lambda *a, **k: None
    w.sel = None
    w._searching = lambda: False

    _p, _b, page, _all, _f = w._view_lists()
    chk("2. 박스 창: 지금 박스의 줄만 도감순", ids(page) == [-9, 2, 4, 1, 3], ids(page))
    w.sort = "level"
    _p, _b, page, _all, _f = w._view_lists()
    chk("   머리글 정렬(전체 보기)은 예전 그대로 - 모든 박스를 레벨순", ids(page)[:2] == [5, 4], ids(page))
    w.sort = None

    rows = w._box_rows()
    head = [i for i, r in enumerate(rows) if r and r.get("header")]
    chk("3. 이름표 메뉴: 박스 둘 · 구분선 · '박스 안 순서' 제목", len(head) == 1 and rows[head[0]]["text"] == "박스 안 순서"
        and rows[head[0] - 1] is None and head[0] == 3, [r and r.get("text") for r in rows])
    opts = rows[head[0] + 1:]
    chk("   잡은 순 · 도감순 · 이름순 · 레벨순, 지금 것(도감순)에 표시",
        [r["text"] for r in opts] == ["잡은 순", "도감순", "이름순", "레벨순"]
        and [r["checked"] for r in opts] == [False, True, False, False], [(r["text"], r["checked"]) for r in opts])

    opts[2]["command"]()
    chk("4. 이름순을 고르면 설정에 적고 저장 · 다시 그린다", w.app.settings["boxOrder"] == "name"
        and saved and saved[-1]["boxOrder"] == "name" and shown, (w.app.settings, saved, shown))
    n = len(saved)
    opts[2]["command"]()
    chk("   같은 것을 또 고르면 아무것도 안 한다", len(saved) == n)
    w.set_box_order("bogus")
    chk("   이상한 값은 잡은 순", w.app.settings["boxOrder"] == "" and w.box_order() == "")
    w.app.settings["boxOrder"] = "weird"
    chk("   설정 파일에 이상한 값이 있어도 잡은 순으로 본다", w.box_order() == "")

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
