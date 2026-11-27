# -*- coding: utf-8 -*-
"""포켓몬 관리 창: 머리글로 줄 세우기 · 여러 마리 한꺼번에 옮기기 (1.10.6, 제보 #194).

    python client/test_box_multi.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 (smoke_box_filter 의 가짜 api - 옮기기 규칙은 서버와 같다:
다 옮기거나 하나도 안 옮긴다. 서버 쪽은 server/test_boxes.py 가 본다).

  1. 머리글(도감 · 이름 · Lv · 개체값)을 누르면 **박스를 넘어** 그 기준으로 줄 세워 본다.
     다시 누르면 박스 순서로 돌아온다. 한 번에 한 박스 크기만큼만 그린다.
  2. '박스 옮기기' 의 맨 위 줄로 여러 마리 고르기를 켠다. 줄을 누르면 고름이 붙었다 떨어지고,
     Shift 로 사이를 한꺼번에 고른다. 고름은 박스를 넘겨도 남는다.
  3. 고른 것을 한 박스로 한꺼번에 옮긴다. 자리가 모자란 박스는 고를 수 없다. 알과 데리고 다니는
     포켓몬은 못 고른다.
  4. 고르기를 켜도 끄면 바닥의 단추 줄에 눌린 것이 없다.
  5. 상세 칸의 그림은 **바탕화면에서 입고 있는 모습**이다: 메가진화한 모습으로 걷는 포켓몬은 메가 폼으로
     보인다 (제보 #193). 모습이 바뀌면 다시 붙인다.
"""
import json
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-boxmulti-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import box_filter as F                    # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
import smoke_box_filter as SB                               # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

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
    """줄을 누른 마우스 (끌기·누르기 처리가 읽는 것만)."""

    def __init__(self, win, pid, shift=False):
        row = win.rows[pid]
        self.x_root = row.f.winfo_rootx() + 30
        self.y_root = row.f.winfo_rooty() + 5
        self.state = 0x0001 if shift else 0


def click(root, win, pid, shift=False):
    e = E(win, pid, shift)
    win._drag_press(pid, e)
    win._drag_release(e)
    SB.settle(root, 3)


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
    print("글꼴 %s / 본문 %dpt" % (U.FAMILY, U.FONT[1]))

    party = [SB.mon(dex, 7, 5001, on=True), SB.mon(dex, 4, 5002, on=True)]
    nums = [150, 25, 129, 6, 143, 3, 94, 130, 59, 65] + list(range(10, 70))
    box = []
    for i, n in enumerate(nums):                    # 박스 일흔 마리: 0번 서른, 1번 서른, 2번 열
        m = SB.mon(dex, n, 6000 + i)
        m["box"] = i // 30
        m["level"] = 5 + (i * 17) % 90
        m["info"]["level"] = m["level"]
        box.append(m)
    box[3]["info"]["name"] = "가나다"               # 별명 (이름 순에서 맨 앞쪽으로 간다)
    app = SB.FakeApp(root, dex, party + box)
    api = app.api
    api.eggs = [{"id": 9, "name": "포켓몬 알", "needSec": 100, "gotSec": 10, "onDesktop": False}]
    win = ui_box.BoxWindow(root, app)
    win.win.geometry("990x668+20+20")
    SB.wait_for(root, lambda: getattr(win, "mons", None))
    SB.settle_rows(root, win)
    party_ids = [m["id"] for m in party]
    by_id = dict((m["id"], m) for m in box)
    EGG = -9

    def box_shown():
        return [i for i in SB.shown(win) if i not in party_ids]

    def ids_of(key, page=0):
        want = [m["id"] for m in F.sort_by(box, dex, key)]
        return want[page * 30:(page + 1) * 30]

    print("=== 머리글로 줄 세우기 ===")
    heads = dict((k, SB.head(lb)) for k, lb in win.heads.items())
    chk("누를 수 있는 머리글 넷에 ▾ 가 붙는다", heads == {"num": "도감▾", "name": "이름▾", "level": "Lv▾", "bst": "개체값▾"}
        and all(lb.cget("cursor") == "hand2" for lb in win.heads.values()), heads)
    chk("  머리글의 글자가 칸에 다 들어간다", all(lb.winfo_reqwidth() <= lb.winfo_width() for lb in win.heads.values()),
        [(k, lb.winfo_reqwidth(), lb.winfo_width()) for k, lb in win.heads.items()])
    first_box = [EGG] + [m["id"] for m in box if m["box"] == 0]
    chk("처음에는 박스 순서 (0번 박스: 알과 서른 마리)", box_shown() == first_box and win.sort is None, box_shown()[:4])

    win.heads["num"].event_generate("<Button-1>", x=3, y=3)          # '도감' 머리글을 진짜로 누른다
    SB.settle_rows(root, win)
    chk("**'도감' 을 누르면 박스를 넘어 도감 번호 순**", win.sort == "num" and box_shown() == ids_of("num")
        and [by_id[i]["num"] for i in box_shown()][:5] == [3, 6, 10, 11, 12], [by_id[i]["num"] for i in box_shown()][:6])
    chk("  머리글이 금색 '도감▲' 로 바뀐다 (나머지는 그대로)", SB.head(win.heads["num"]) == "도감▲"
        and str(win.heads["num"].cget("fg")) == U.ACCENT and SB.head(win.heads["name"]) == "이름▾"
        and SB.head(win.heads["bst"]) == "개체값▾", SB.head(win.heads["num"]))
    def pic_size(lb):
        n = str(lb.cget("image"))
        return (int(root.tk.call("image", "width", n)), int(root.tk.call("image", "height", n))) if n else None
    chk("  켜진 화살표와 꺼진 화살표가 같은 크기의 그림 (1.11.0: 꺼진 ▾ 는 작고 켜진 ▲ 는 컸다)",
        pic_size(win.heads["num"]) is not None and pic_size(win.heads["num"]) == pic_size(win.heads["name"]),
        (pic_size(win.heads["num"]), pic_size(win.heads["name"])))
    chk("  박스 이름표 자리에 몇 번째인지, 'PC 박스' 줄에 기준이 적힌다",
        win.lbl_page.cget("text") == "1~30 / 71마리" and "도감 번호 순" in win._sep_label.cget("text")
        and "도감 번호 순" in win.status.cget("text"), (win.lbl_page.cget("text"), win._sep_label.cget("text")))
    chk("  개체값 칸은 그대로 개체값이다 (종족값으로 볼 때만 바뀐다)",
        win.rows[box_shown()[0]].iv_cell.cget("text").endswith("%"))
    chk("  머리글이 켜져도 글자가 칸에 든다", all(lb.winfo_reqwidth() <= lb.winfo_width() for lb in win.heads.values()))
    win._page(1)
    SB.settle_rows(root, win)
    chk("  다음 쪽으로 넘기면 31번째부터", box_shown() == ids_of("num", 1) and win.lbl_page.cget("text") == "31~60 / 71마리",
        win.lbl_page.cget("text"))
    win._page(1)
    SB.settle_rows(root, win)
    chk("  알은 맨 끝 쪽의 맨 뒤다", box_shown()[-1] == EGG and len(box_shown()) == 11, box_shown()[-3:])
    win.open_box_menu()
    chk("  줄 세워 보는 중에는 박스 고르기가 안 열리고 까닭을 말한다", "도감 번호 순" in win.status.cget("text"))

    win.set_sort("name")
    SB.settle_rows(root, win)
    names = [F.name_of(by_id[i]) for i in box_shown()]
    chk("**'이름' 을 누르면 가나다 순** (별명 '가나다' 가 맨 앞, 첫 쪽으로 돌아온다)", win.sort == "name"
        and names == sorted(names) and names[0] == "가나다" and win.rank_page == 0
        and SB.head(win.heads["name"]) == "이름▲" and SB.head(win.heads["num"]) == "도감▾", names[:4])
    win.set_sort("level")
    SB.settle_rows(root, win)
    lvs = [by_id[i]["level"] for i in box_shown()]
    chk("**'Lv' 를 누르면 레벨 높은 것부터**", lvs == sorted(lvs, reverse=True) and lvs[0] == max(m["level"] for m in box)
        and SB.head(win.heads["level"]) == "Lv▼" and "레벨 높은 순" in win._sep_label.cget("text"), lvs[:6])
    win.f_query.set("1")                                             # 도감 번호에 1 이 든 것만
    SB.settle_rows(root, win)
    hit = [m for m in box if "1" in str(m["num"]) or "1" in ("%04d" % m["num"])]
    chk("찾으면서도 그 기준으로 선다", box_shown() == [m["id"] for m in F.sort_by(hit, dex, "level")] and len(hit) > 5,
        (len(box_shown()), len(hit)))
    win.f_query.set("")
    SB.settle_rows(root, win)
    win.toggle_sort()                                                # 종족값 (예전부터 있던 것)
    SB.settle_rows(root, win)
    chk("종족값 순은 예전 그대로다 ('개체값' 머리글, 그 칸에 종족값 합계, '위' 로 센다)", win.sort == "bst" and win.sort_bst
        and box_shown() == ids_of("bst") and SB.head(win.heads["bst"]) == "종족값▼"
        and SB.head(win.heads["level"]) == "Lv▾" and "위" in win.lbl_page.cget("text")
        and not win.rows[box_shown()[0]].iv_cell.cget("text").endswith("%"), win.lbl_page.cget("text"))
    win.set_sort("bst")
    SB.settle_rows(root, win)
    chk("같은 머리글을 다시 누르면 박스 순서로 돌아온다", win.sort is None and box_shown() == first_box
        and all(SB.head(lb).endswith("▾") for lb in win.heads.values())
        and win.rows[first_box[1]].iv_cell.cget("text").endswith("%") and "박스 1" in win.lbl_page.cget("text"),
        (win.sort, win.lbl_page.cget("text")))
    win.set_sort("level")
    SB.settle_rows(root, win)
    target = box[45]["id"]                                           # 1번 박스에 있는 포켓몬
    win.select(target) if target in win.rows else win._reveal(target)
    SB.settle_rows(root, win)

    print("\n=== 여러 마리 고르기 ===")
    win.sort = None
    win._paint_sort()
    win.box_no = 0
    win._show(first_box[1])
    SB.settle_rows(root, win)
    menus = []
    real_menu = win._menu
    win._menu = lambda btn, rows, below=False, scroll=None: menus.append(
        (btn, ((scroll or {}).get("head") or []) + ([None] if (scroll or {}).get("head") else []) + rows))
    win.move_box()
    rows = menus[-1][1]
    chk("'박스 옮기기' 의 맨 위 줄이 '여러 마리 한꺼번에 옮기기' 다 (그 아래에 박스들 - 2.5.9 부터 박스 줄만 굴러간다)",
        rows[0]["text"].startswith("여러 마리") and rows[1] is None and len(rows) == 2 + win.box_count()
        and menus[-1][0] is win.btn_move, rows[0]["text"])
    chk("평소에는 평소 단추만 보인다", win.bar_normal.winfo_ismapped() and not win.bar_multi.winfo_ismapped() and not win.multi)
    rows[0]["command"]()
    SB.settle(root)
    chk("**누르면 고르기가 켜진다**: 바닥의 단추가 바뀌고 어떻게 하는지 알려 준다", win.multi
        and win.bar_multi.winfo_ismapped() and not win.bar_normal.winfo_ismapped()
        and "눌러 고르세요" in win.status.cget("text"), win.status.cget("text"))
    chk("  아직 고른 것이 없어 옮기기는 잠겨 있다", win.btn_multi_move.label.cget("text") == "옮기기 (0마리)"
        and not win.btn_multi_move.enabled and not win.btn_multi_clear.enabled and win.btn_multi_done.enabled)
    bar = win.status.master                                          # 바닥의 단추 줄 (바꾼 곳만 본다)
    chk("  고르기 중에 바닥 줄에 눌린 위젯이 없다", not squeezed(bar), squeezed(bar)[:3])

    b0 = [m["id"] for m in box if m["box"] == 0]
    click(root, win, b0[2])
    r = win.rows[b0[2]]
    chk("**줄을 누르면 고름이 붙는다** (도감 번호 자리에 ✓, 왼쪽 막대가 초록)", win.checked == {b0[2]} and r.checked
        and r.num_cell.cget("text") == "✓" and str(r.mark.cget("bg")) == U.GOOD
        and win.btn_multi_move.label.cget("text") == "옮기기 (1마리)" and win.btn_multi_move.enabled,
        (win.checked, r.num_cell.cget("text")))
    chk("  상세 칸도 그 포켓몬을 보여 준다", win.sel == b0[2])
    click(root, win, b0[5])
    chk("  다른 줄을 누르면 앞의 고름은 남는다 (초록 바탕)", win.checked == {b0[2], b0[5]}
        and str(win.rows[b0[2]].f.cget("bg")) == ui_box.CHECK_BG and win.rows[b0[2]].num_cell.cget("text") == "✓",
        str(win.rows[b0[2]].f.cget("bg")))
    click(root, win, b0[5])
    chk("  다시 누르면 떨어진다 (번호가 돌아온다)", win.checked == {b0[2]} and not win.rows[b0[5]].checked
        and win.rows[b0[5]].num_cell.cget("text") == "%04d" % by_id[b0[5]]["num"], win.rows[b0[5]].num_cell.cget("text"))
    click(root, win, b0[9], shift=True)
    # (방금 누른 줄 = 5번째가 한쪽 끝이다. 떼어 낸 줄이어도 거기서부터 센다)
    chk("**Shift 를 누른 채 누르면 방금 누른 줄부터 사이의 것까지** (5~9번째 줄 다섯 마리가 붙는다)",
        win.checked == set([b0[2]] + b0[5:10]) and "6마리" in win.status.cget("text")
        and win.btn_multi_move.label.cget("text") == "옮기기 (6마리)", sorted(win.checked))
    click(root, win, party_ids[0])
    chk("데리고 다니는 포켓몬은 못 고른다 (까닭을 말한다)", party_ids[0] not in win.checked and len(win.checked) == 6
        and "데리고 다니는" in win.status.cget("text") and not win.rows[party_ids[0]].checked, win.status.cget("text"))
    click(root, win, EGG)
    chk("알도 못 고른다", EGG not in win.checked and len(win.checked) == 6)
    n_calls = len(api.calls)
    e1, e2 = E(win, b0[12]), E(win, b0[20])
    win._drag_press(b0[12], e1)
    e_far = E(win, b0[20])
    win._drag_move(e_far)
    win._drag_release(e2)
    SB.settle(root)
    chk("고르기 중에는 끌어도 자리를 안 바꾼다 (서버에 안 간다)", len(api.calls) == n_calls and b0[12] in win.checked,
        api.calls[n_calls:])
    win.check_all_shown()
    SB.settle(root)
    chk("**'이 화면 전부'**: 0번 박스의 서른 마리 (알은 빠진다)", win.checked == set(b0) and len(win.checked) == 30
        and all(win.rows[i].checked for i in b0 if i in win.rows) and not win.rows[EGG].checked, len(win.checked))
    win._page(1)
    SB.settle_rows(root, win)
    b1 = [m["id"] for m in box if m["box"] == 1]
    chk("박스를 넘겨도 고름은 남는다 (새 박스의 줄은 안 골라져 있다)", len(win.checked) == 30
        and box_shown() == b1 and not any(win.rows[i].checked for i in b1), len(win.checked))
    win._page(-1)
    SB.settle_rows(root, win)
    chk("  돌아오면 표시가 그대로다", all(win.rows[i].checked and win.rows[i].num_cell.cget("text") == "✓" for i in b0))

    print("\n=== 한꺼번에 옮긴다 ===")
    win.move_checked()
    rows = menus[-1][1]
    text = dict((i, r_["text"]) for i, r_ in enumerate(rows))
    chk("어디로 보낼지 묻는다: 이미 있는 곳 · 자리가 모자란 곳은 그렇게 적혀 있다", menus[-1][0] is win.btn_multi_move
        and "이미 여기" in text[0] and "자리 부족 (0칸)" in text[1] and "자리 부족 (20칸)" in text[2]
        and text[3].endswith("(0/30)"), [text[i] for i in range(4)])
    n_calls = len(api.calls)
    rows[2]["command"]()
    rows[0]["command"]()
    SB.settle(root)
    chk("  자리가 모자란 박스·이미 있는 박스는 눌러도 아무 일이 없다", len(api.calls) == n_calls and len(win.checked) == 30)
    for i in b0[20:]:
        click(root, win, i)
    chk("열 마리를 빼면 스무 마리", len(win.checked) == 20 and win.btn_multi_move.label.cget("text") == "옮기기 (20마리)")
    win.move_checked()
    rows = menus[-1][1]
    chk("  이제 2번 박스(남은 칸 스물)에 들어간다", rows[2]["text"].endswith("(10/30)"), rows[2]["text"])
    rows[2]["command"]()
    # (옮겼다는 글은 다시 불러온 목록이 화면에 올라온 뒤에 적힌다)
    SB.wait_for(root, lambda: "옮겼습니다" in win.status.cget("text") and win._wait is None)
    SB.settle_rows(root, win)
    chk("**한 번에 옮긴다** (서버에 한 번, 고른 스무 마리를 2번 박스로)", api.calls.count(("boxes", sorted(b0[:20]), 2)) == 1
        and all(by_id[i]["box"] == 2 for i in b0[:20]) and all(by_id[i]["box"] == 0 for i in b0[20:]),
        [c for c in api.calls if c[0] == "boxes"])
    chk("  옮긴 뒤: 고름이 비고, 고르기는 켜진 채, 보던 박스 그대로", win.checked == set() and win.multi and win.box_no == 0
        and box_shown() == [EGG] + b0[20:] and "20마리" in win.status.cget("text")
        and win.btn_multi_move.label.cget("text") == "옮기기 (0마리)" and not win.btn_multi_move.enabled,
        (win.box_no, win.status.cget("text")))
    chk("  남은 줄에 표시가 안 남는다", not any(r_.checked for r_ in win.rows.values()))
    win._page(2)
    SB.settle_rows(root, win)
    chk("  2번 박스가 가득 찼다 (서른 마리, 표시 없음)", len(box_shown()) == 30 and "30/30" in win.lbl_page.cget("text")
        and not any(win.rows[i].checked for i in box_shown()), win.lbl_page.cget("text"))

    # 서버가 거절하면 (그사이 다른 곳에서 박스가 찼다) 까닭을 적고 고름은 그대로 둔다
    win._page(-2)
    SB.settle_rows(root, win)
    click(root, win, b0[20])
    click(root, win, b0[21])
    win._do_move_many(sorted(win.checked), 2)
    SB.wait_for(root, lambda: "자리가 모자랍니다" in win.status.cget("text"))
    chk("서버가 거절하면 까닭을 붉게 적고 고름은 그대로다", "자리가 모자랍니다" in win.status.cget("text")
        and str(win.status.cget("fg")) == U.DANGER and win.checked == {b0[20], b0[21]}
        and by_id[b0[20]]["box"] == 0, win.status.cget("text"))

    print("\n=== 찾아서 고르기 ===")
    win.f_query.set("1")
    SB.settle_rows(root, win)
    found = box_shown()
    win.clear_checks()
    win.check_all_shown()
    chk("찾은 것을 전부 고른다 (박스 여러 개에 흩어진 %d마리)" % len(found), win.checked == set(found)
        and len(set(by_id[i]["box"] for i in found)) >= 2 and 5 < len(found) <= 30, len(found))
    win.move_checked()
    rows = menus[-1][1]
    win.say("")
    rows[5]["command"]()
    SB.wait_for(root, lambda: "옮겼습니다" in win.status.cget("text") and win._wait is None)
    SB.settle_rows(root, win)
    chk("**흩어진 것을 한 박스로 모은다**", all(by_id[i]["box"] == 5 for i in found) and win.checked == set()
        and box_shown() == found, [by_id[i]["box"] for i in found][:5])
    win.f_query.set("")
    SB.settle_rows(root, win)

    print("\n=== 그만 ===")
    click(root, win, box_shown()[1])
    win.exit_multi()
    SB.settle(root)
    chk("'그만' 을 누르면 평소 단추로 돌아오고 고름이 지워진다", not win.multi and win.checked == set()
        and win.bar_normal.winfo_ismapped() and not win.bar_multi.winfo_ismapped()
        and not any(r_.checked for r_ in win.rows.values()) and win.btn_move.enabled, win.checked)
    one = box_shown()[2]
    click(root, win, one)
    chk("  평소처럼 한 줄만 고른다 (✓ 가 안 붙는다)", win.sel == one and win.checked == set()
        and win.rows[one].num_cell.cget("text") != "✓" and SB.picked(win) == [one], SB.picked(win))
    chk("  바닥 줄에 눌린 위젯이 없다", not squeezed(bar), squeezed(bar)[:3])

    print("\n=== 그림은 바탕화면의 모습을 따른다 (메가진화한 모습으로 걷는 중이면 메가) ===")
    gif = SB.make_gif(os.path.join(os.environ["POKET_HOME"], "fake.gif"))
    real_ensure = ui_box.sprite_cache.ensure
    asked, missing = [], set()

    def fake_ensure(_api, num, shiny=False):
        asked.append(num)
        return None if num in missing else gif
    ui_box.sprite_cache.ensure = fake_ensure
    MEGA = 10036                                     # (메가거북왕의 번호라고 친다)
    looks = {party_ids[0]: MEGA}
    app.look_num = lambda m: looks.get(m["id"]) if m.get("onDesktop") else None

    def art_ready():
        """그림이 다 붙었나 (받는 동안은 '...' 이 적혀 있다). 받으러 간 것만 보고 넘어가면, 붙기 전에
        다른 것을 골라 그 그림이 버려진다 - 느린 러너에서 '다시 받지 않는다' 가 그렇게 깨진다."""
        return win.d_art.cget("text") == "" and bool(str(win.d_art.cget("image")))
    try:
        win.select(party_ids[1])
        SB.wait_for(root, lambda: asked[-1:] == [4] and art_ready())
        del asked[:]
        win.select(party_ids[0])                     # 꼬부기 계열 (7번) - 바탕화면에서 메가 모습으로 걷는 중
        SB.wait_for(root, lambda: MEGA in asked and art_ready())
        chk("**메가 모습으로 걷는 포켓몬은 관리 창의 그림도 메가 폼이다** (제 번호의 그림을 받지 않는다)",
            asked == [MEGA] and win.look_num(by_id.get(party_ids[0]) or win.current()) == MEGA
            and str(win.d_art.cget("image")), asked)
        chk("  이름·도감 번호 같은 다른 칸은 그대로다 (그림만 바뀐다)", win.current()["num"] == 7)
        del asked[:]
        win.select(box_shown()[2])
        SB.wait_for(root, lambda: len(asked) == 1 and art_ready())
        chk("  박스의 포켓몬은 제 모습", asked == [win.current()["num"]] and asked[0] < 10000, asked)
        del asked[:]
        win.select(party_ids[0])
        SB.settle(root)
        chk("  방금 본 메가 그림은 다시 받지 않는다", asked == [] and len(win.photos) == 2, asked)
        looks.clear()                                # 바탕화면에서 원래 모습으로 돌아갔다
        win.refresh_look(party_ids[0])
        SB.wait_for(root, lambda: asked == [7] and art_ready())
        chk("**바탕화면의 모습이 바뀌면 그림을 다시 붙인다** (원래 모습으로)", asked == [7], asked)
        del asked[:]
        win.refresh_look(999999)                     # 보고 있지 않은 포켓몬의 모습이 바뀌었다
        SB.settle(root)
        chk("  보고 있지 않은 포켓몬이면 아무 일도 없다", asked == [])
        looks[party_ids[1]] = MEGA + 1
        missing.add(MEGA + 1)                        # 메가 폼의 그림을 못 받는다
        win.select(party_ids[1])
        SB.wait_for(root, lambda: asked[-1:] == [4] and art_ready())
        chk("  메가 폼의 그림을 못 받으면 원래 모습으로라도 보여 준다", asked == [MEGA + 1, 4]
            and str(win.d_art.cget("image")) and win.d_art.cget("text") == "", (asked, win.d_art.cget("text")))
        del app.look_num                             # 옛 앱(그런 것을 모른다)이어도 안 터진다
        del asked[:]
        win._art.clear()
        win.select(party_ids[0])
        SB.wait_for(root, lambda: asked == [7] and art_ready())
        chk("  앱이 모습을 모르면 제 번호로 그린다", asked == [7] and win.look_num(win.current()) == 7, asked)
    finally:
        ui_box.sprite_cache.ensure = real_ensure

    print("\n=== 옛 서버 (한꺼번에 옮기는 길이 없다) ===")
    from poketdesktop import api as A
    a = A.Api("http://x")
    sent = []

    def old_server(method, path, body=None, **_kw):
        sent.append((method, path, body))
        if path.endswith("/boxes/move"):
            raise A.ApiError("Not Found", 404)           # 그 길이 없다
        return {"ok": True}
    a._call = old_server
    chk("그 길이 없으면 한 마리씩 옮긴다 (클라이언트가 먼저 나가도 된다)", a.move_boxes([3, 4, 5], 2) == 3
        and sent[1:] == [("POST", "/api/pokemon/%d/box" % i, {"box": 2}) for i in (3, 4, 5)], sent)

    def new_server(method, path, body=None, **_kw):
        sent.append((method, path, body))
        raise A.ApiError("그런 포켓몬이 없습니다.", 404)
    a._call = new_server
    del sent[:]
    try:
        a.move_boxes([3, 4], 2)
        chk("새 서버가 거절한 것은 한 마리씩 다시 보내지 않는다", False, sent)
    except A.ApiError as e:
        chk("새 서버가 거절한 것은 한 마리씩 다시 보내지 않는다 (까닭을 그대로 올린다)",
            len(sent) == 1 and "없습니다" in e.message, sent)

    print("\n=== 가장 작은 창 ===")
    win.win.geometry("950x620")
    SB.settle(root, 20)
    win.enter_multi()
    win.check_all_shown()
    SB.settle(root, 20)
    kids = [win.btn_multi_move.holder, win.btn_multi_all.holder, win.btn_multi_clear.holder, win.btn_multi_done.holder]
    chk("고르기 단추 넷이 제 크기로 다 보인다 (눌리지 않는다)",
        all(k.winfo_ismapped() and k.winfo_height() >= k.winfo_reqheight() and k.winfo_width() >= k.winfo_reqwidth()
            for k in kids) and kids[-1].winfo_rootx() + kids[-1].winfo_width() <= win.win.winfo_rootx() + win.win.winfo_width(),
        [(k.winfo_width(), k.winfo_reqwidth(), k.winfo_height(), k.winfo_reqheight()) for k in kids])
    chk("  머리글의 글자도 칸에 든다", all(lb.winfo_reqwidth() <= lb.winfo_width() for lb in win.heads.values()))
    win.exit_multi()
    win._menu = real_menu
    win.close()
    SB.settle(root)
    chk("도는 동안 오류 없음", not errors, errors[:2])
    root.destroy()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
