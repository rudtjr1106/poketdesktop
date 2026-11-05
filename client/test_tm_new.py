# -*- coding: utf-8 -*-
"""새 기술머신 표시 검사 (1.11.0).

    python client/test_tm_new.py
    python client/run_as_windows.py client/test_tm_new.py

**창을 진짜로 띄운다.** 서버 없이 돈다 (기술머신 목록은 server/data/tms.json 에서 만든다).

잡다가·배틀에서·탐험에서 기술머신을 얻어도 알림 한 줄이 지나가면 끝이었다. 이제 받고
아직 안 본 기술머신에는 노란 점을 찍는다.

  1. 새 것(가진 것 + new) 줄에만 **이름 앞에 노란 점**. 안 가진 줄에는 new 가 와도 안 찍는다.
  2. 아래 줄에 [새 기술머신 N개]. 누르면 **다음 새 것으로 가서 고른다** - 거르기 · 찾는 말(2.2.1)에
     가려져 있으면 그것을 풀고, 목록을 그 줄까지 굴린다.
  3. **줄을 누르면 점이 꺼지고 서버에 적는다** (/api/tms/seen). 다 보면 단추가 사라진다.
  4. 서버에 적기 전에 다시 읽어도 **본 줄의 점이 되살지 않는다.**
  5. 새로 받은 것이 생겨 다시 읽으면 점과 단추가 다시 생긴다.
  6. 가방 탭 머리줄의 [기술머신] 에 점 - 칸이 둘이라 두 칸의 단추를 다 칠한다.
  7. 앱: 수가 늘면 허브의 가방 탭에 점, 떠 있는 기술머신 칸을 다시 읽는다. 0 이면 끈다.
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-tmnew-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import smoke_tms as ST                                      # noqa: E402
import test_bag_tabs as BT                                  # noqa: E402
from poketdesktop import app as APP                         # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_bag_tabs, ui_tms                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

OK = FAIL = 0
NEW = (30, 200)          # 가진 것 (번호가 10의 배수) 중 새 것
NOT_MINE = 35            # 안 가진 것에 new 가 와도 점은 없다


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def wait(root, cond, sec=8.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


class Api(ST.FakeApi):
    """/api/tms 에 new·newCount 를 싣고, /api/tms/seen 을 받는다.

    apply_seen 이 False 면 본 것을 서버에 아직 안 적은 것처럼 군다 (요청이 늦게 닿았다).
    """

    def __init__(self, tms, learners):
        ST.FakeApi.__init__(self, tms, learners)
        self.fresh = set(NEW) | {NOT_MINE}
        self.seen = []
        self.apply_seen = True

    def tms(self):
        out = ST.FakeApi.tms(self)
        for t in out["tms"]:
            t["new"] = t["no"] in self.fresh
        out["newCount"] = sum(1 for t in out["tms"] if t["new"] and t["have"])
        return out

    def tms_seen(self, nos=None):
        self.seen.append(list(nos) if nos is not None else None)
        if self.apply_seen:
            self.fresh -= set(nos or self.fresh)
        return {"newCount": len(self.fresh)}


class App(ST.FakeApp):
    def __init__(self, root, api):
        ST.FakeApp.__init__(self, root, api)
        self.tm_new = 0
        self.noted = []

    def note_tms(self, n, reload=True):
        self.noted.append((n, reload))
        self.tm_new = n


def dot_nos(win):
    return sorted(n for n, d in win.dots.items() if d.winfo_exists())


def btn_shown(win):
    return bool(win.fresh_btn.holder.winfo_manager())


def in_view(win, n):
    """n 번 줄이 목록 화면 안에 보이나."""
    win.list_inner.update_idletasks()
    f = win.rows[n][0]
    top = win.list_canvas.canvasy(0)
    h = win.list_canvas.winfo_height()
    return f.winfo_ismapped() and top <= f.winfo_y() and f.winfo_y() + f.winfo_height() <= top + h


def check_pane(root):
    print("\n=== 기술머신 칸: 노란 점")
    tms = ST.load_tms()
    api = Api(tms, [])
    app = App(root, api)
    win = ui_tms.TmWindow(root, app)
    win.win.geometry("1000x664+40+40")
    chk("다 읽는다", wait(root, lambda: win.tms and not (win._list_job and win._list_job.pending)))
    ST.settle_list(root, win)
    chk("새 것(가진 것)에만 점이 있다", dot_nos(win) == list(NEW), dot_nos(win))
    chk("  안 가진 것에는 new 가 와도 점이 없다", NOT_MINE not in win.dots and NOT_MINE not in win.fresh)
    d = win.dots[NEW[0]]
    chk("  점은 노란색 (금색 ACCENT)", d.cget("fg") == U.ACCENT, d.cget("fg"))
    chk("  점은 이름 앞에 있다", d.winfo_x() < win.rows[NEW[0]][2].winfo_x(),
        (d.winfo_x(), win.rows[NEW[0]][2].winfo_x()))
    chk("  점 바탕이 줄 바탕과 같다", d.cget("bg") == win.rows[NEW[0]][0].cget("bg"))
    chk("아래 줄에 [새 기술머신 2개]", btn_shown(win) and win.fresh_btn.label.cget("text") == "새 기술머신 2개",
        win.fresh_btn.label.cget("text"))
    chk("앱에 수를 알린다 (다시 읽게 하지는 않는다)", app.noted[-1] == (2, False), app.noted)
    chk("눌린 위젯이 없다", not squeezed(win.win), squeezed(win.win)[:3])

    print("\n=== 줄을 누르면 꺼진다")
    win.pick(NEW[0])
    chk("고른 줄의 점이 꺼진다", dot_nos(win) == [NEW[1]], dot_nos(win))
    chk("서버에 적는다", wait(root, lambda: api.seen == [[NEW[0]]]), api.seen)
    chk("단추는 1개", win.fresh_btn.label.cget("text") == "새 기술머신 1개")
    chk("앱의 수도 1", app.tm_new == 1, app.noted)
    win.pick(NEW[0])
    root.update()
    chk("  본 것을 또 눌러도 다시 적지 않는다", api.seen == [[NEW[0]]], api.seen)
    win.pick(10)
    root.update()
    chk("  새 것이 아닌 줄은 적지 않는다", api.seen == [[NEW[0]]], api.seen)

    print("\n=== 서버에 적기 전에 다시 읽어도")
    api.fresh.add(NEW[0])              # 서버는 아직 새 것이라고 한다
    n = api.calls.count("tms")
    win.reload()
    chk("다시 읽는다", wait(root, lambda: api.calls.count("tms") > n and win._wait is None))
    root.update()
    ST.settle_list(root, win)
    chk("본 줄의 점이 되살지 않는다", dot_nos(win) == [NEW[1]], dot_nos(win))
    chk("  단추도 1개", win.fresh_btn.label.cget("text") == "새 기술머신 1개")
    api.fresh.discard(NEW[0])

    print("\n=== [새 기술머신] 단추: 다음 새 것으로")
    win.list_canvas.yview_moveto(0)
    ty = next(t["type"] for t in tms if t["have"] and t["type"] != tms[NEW[1] - 1]["type"])
    win._set_type(ty)
    win.tm_q.set("펀치")                # 찾는 말로도 가린다 (2.2.1, 게시판 #458)
    ST.settle_list(root, win)
    hidden = NEW[1] not in set(t["no"] for t in win._visible())
    chk("(타입 거르기 · 찾는 말로 새 것을 가렸다)", hidden and "펀치" not in tms[NEW[1] - 1]["kr"])
    win.fresh_btn.command()            # [새 기술머신 1개] 를 누른다
    ST.settle_list(root, win)
    root.update_idletasks()
    chk("그 기술머신을 고른다", win.no == NEW[1], win.no)
    chk("  가렸던 거르기를 푼다", win.f_type is None and win.f_cat is None, (win.f_type, win.f_cat))
    chk("  찾는 말도 지운다 (2.2.1)", win.tm_q.get() == "" and win.tm_find.entry.get() == "", win.tm_q.get())
    chk("  목록이 그 줄까지 굴러가 보인다", in_view(win, NEW[1]))
    chk("  오른쪽에 그 기술머신이 뜬다", win.title_lbl.cget("text") == win._cur()["label"])
    chk("다 봤으면 단추가 사라진다", not btn_shown(win))
    chk("  점이 하나도 없다", dot_nos(win) == [], dot_nos(win))
    chk("  앱의 수는 0", app.tm_new == 0, app.noted)
    chk("  서버에 둘 다 적었다", wait(root, lambda: api.seen == [[NEW[0]], [NEW[1]]]), api.seen)

    print("\n=== 새로 받은 것이 생기면")
    for t in api.data:
        if t["no"] == 50:
            t["have"] = True
    api.fresh = {50, 120}
    win.reload()
    chk("다시 읽는다", wait(root, lambda: win._wait is None and 50 in win.fresh))
    ST.settle_list(root, win)
    chk("점이 다시 생긴다 (새로 가진 줄 포함)", dot_nos(win) == [50, 120], dot_nos(win))
    chk("  단추가 다시 뜬다", btn_shown(win) and win.fresh_btn.label.cget("text") == "새 기술머신 2개")
    win.pick(120)
    chk("  고른 줄의 바탕이 점에도 칠해진다 → 꺼졌으니 점이 없다", 120 not in win.dots)
    win.pick(50)
    root.update()
    chk("  하나씩 보면 단추가 사라진다", not btn_shown(win))
    win.close()


def check_bag(root):
    print("\n=== 가방 탭: [기술머신 ●]")
    tms = ST.load_tms()
    api = BT.Api(tms, [])
    app = BT.App(root, api)
    app.tm_new = 2
    top = tk.Toplevel(root)
    top.geometry("1000x664+40+40")
    bag = ui_bag_tabs.BagTabs(root, app, top)
    bag.win.pack(fill="both", expand=True)
    root.update()
    chk("도구 칸의 단추에 점", [tms_cell(s) for s in bag.segs] == ["기술머신 ●"],
        [tms_cell(s) for s in bag.segs])
    chk("  도구 칸에는 안 찍는다", bag.segs[0].cells["items"].cget("text") == "도구"
        and not str(bag.segs[0].cells["items"].cget("image") or ""))
    lb = bag.segs[0].cells["tms"]
    want = U.mark_image(lb, U.FONT_B, U.FG_DIM, "dot", left=U.Segmented.DOT_GAP)
    chk("  점은 그 칸 글자색 (고르지 않은 칸: 흐린 회색)", str(lb.cget("image")) == str(want))
    bag.segs[0]._hover("tms", True)
    hover = U.mark_image(lb, U.FONT_B, U.FG, "dot", left=U.Segmented.DOT_GAP)
    chk("  마우스를 올리면 글자와 같이 밝아진다", str(lb.cget("image")) == str(hover))
    bag.segs[0]._hover("tms", False)
    bag.show("tms")
    root.update()
    chk("기술머신 칸의 단추도 처음부터 점", [tms_cell(s) for s in bag.segs] == ["기술머신 ●"] * 2)
    bag.badge_tms(False)
    chk("끄면 두 칸 다 꺼진다", [tms_cell(s) for s in bag.segs] == ["기술머신"] * 2)
    plain = bag.segs[0].cells["tms"].winfo_reqwidth()
    bag.badge_tms(True)
    dot = bag.segs[0].cells["tms"].winfo_reqwidth()
    pic = int(root.tk.call("image", "width", str(bag.segs[0].cells["tms"].cget("image"))))
    # Tk 은 글자 옆 그림 사이에 padx 를 또 넣어서 점 하나에 칸이 39px 넓어졌다 (사용자 지적)
    chk("점을 달아도 칸은 '점 + 작은 간격' 만큼만 넓어진다 (+%dpx)" % (dot - plain),
        0 < dot - plain <= pic + 3, (plain, dot, pic))
    bag.segs[0]._hover("tms", True)
    chk("  마우스를 올려도 폭이 그대로", bag.segs[0].cells["tms"].winfo_reqwidth() == dot)
    bag.segs[0]._hover("tms", False)
    bag.badge_tms(False)
    chk("  끄면 원래 폭", bag.segs[0].cells["tms"].winfo_reqwidth() == plain)
    bag.badge_tms(True)
    chk("켜면 두 칸 다 켜진다", [tms_cell(s) for s in bag.segs] == ["기술머신 ●"] * 2)
    on = squeezed(top)
    bag.badge_tms(False)
    root.update()
    off = squeezed(top)
    bag.badge_tms(True)
    root.update()
    # 가방 칸 몸통에는 윈도우 배율에서 원래 눌린 줄이 있다 (점과 상관없다) - 점이 늘리지만 않으면 된다
    chk("점을 켜도 눌린 위젯이 늘지 않는다", on == off, (on[:3], off[:3]))
    return top, bag


def tms_cell(seg):
    """[기술머신] 칸을 '이름 + 점' 으로 읽는다 (점은 그림이다 - 그림이 붙어 있으면 ' ●')."""
    lb = seg.cells["tms"]
    return lb.cget("text") + (" ●" if str(lb.cget("image") or "") else "")


def ink(im, cut=60):
    """그림에서 칠해진 곳의 (왼, 위, 오른, 아래). 가장자리의 옅은 것은 뺀다."""
    return im.split()[3].point(lambda v: 255 if v > cut else 0).getbbox()


def check_marks(root):
    print("\n=== 점·화살표 그림의 크기 (1.11.0) ===")
    for font, name in ((U.FONT, "탭 글꼴"), (U.FONT_B, "칸 글꼴"), (U.FONT_XS, "머리글 글꼴")):
        em, line, asc = U.font_px(root, font)
        mid = asc - em * U.MARK_MID_EM
        dot = U.mark_pil(em, line, asc, U.ACCENT, "dot", left=3, right=5)
        l, t, r, b = ink(dot)
        chk("%s (%.1fpx): 점 지름 0.55em (%.1fpx), 글자 ● (0.68em) 보다 작다" % (name, em, (r - l)),
            abs((r - l) - em * U.MARK_DOT_EM) <= 1.0 and abs((b - t) - em * U.MARK_DOT_EM) <= 1.0
            and (r - l) < em * 0.68, (l, t, r, b))
        chk("  점은 한글 가운데 높이에 앉는다", abs((t + b) / 2.0 - mid) <= 1.0, ((t + b) / 2.0, mid))
        chk("  양옆 빈칸이 그대로 붙는다", dot.size == (3 + int(round(em * U.MARK_DOT_EM)) + 5, line), dot.size)
        sizes = []
        for shape in ("up", "down"):
            l, t, r, b = ink(U.mark_pil(em, line, asc, U.ACCENT, shape))
            sizes.append((r - l, b - t))
        chk("  화살표는 위·아래 같은 크기 %r, 폭 0.5em·높이 0.43em" % (sizes[0],),
            sizes[0] == sizes[1] and abs(sizes[0][0] - em * U.MARK_TRI_W_EM) <= 1.0
            and abs(sizes[0][1] - em * U.MARK_TRI_H_EM) <= 1.0, sizes)
    lb = tk.Label(root, text="기술머신", font=U.FONT_B)
    same = U.mark_image(lb, U.FONT_B, U.ACCENT, "dot") is U.mark_image(lb, U.FONT_B, U.ACCENT, "dot")
    chk("같은 그림은 한 번만 만든다", same)
    lb.destroy()


class Hub(object):
    def __init__(self, bag):
        self.badges = {}
        self.panes = {"bag": bag}

    def set_badge(self, key, on):
        self.badges[key] = on


class Host(object):
    """App 의 새 기술머신 메서드만 빌려 쓴다 (트레이·바탕화면 없이)."""
    note_tms = APP.App.note_tms
    got_tm = APP.App.got_tm
    _paint_tms = APP.App._paint_tms
    _tm_pane = APP.App._tm_pane

    def __init__(self, hub):
        self.hub = hub
        self.tm_new = 0


def check_app(root, bag):
    print("\n=== 앱: 허브 탭과 떠 있는 칸")
    pane = bag.tms
    reloads = []
    pane.reload = lambda: reloads.append(1)
    host = Host(Hub(bag))
    host.note_tms(2)
    chk("수가 늘면 가방 탭에 점", host.hub.badges.get("bag") is True, host.hub.badges)
    chk("  [기술머신] 에도", tms_cell(bag.segs[0]) == "기술머신 ●")
    chk("  떠 있는 기술머신 칸을 다시 읽는다", reloads == [1], reloads)
    host.note_tms(2)
    chk("  같은 수면 다시 읽지 않는다", reloads == [1], reloads)
    host.got_tm()
    chk("주우면 바로 하나 는다 (동기화를 안 기다린다)", host.tm_new == 3 and reloads == [1, 1], (host.tm_new, reloads))
    host.note_tms(1, reload=False)
    chk("칸이 알린 수는 다시 읽게 하지 않는다", reloads == [1, 1] and host.tm_new == 1)
    host.note_tms(0)
    chk("0 이면 탭 점이 꺼진다", host.hub.badges.get("bag") is False)
    chk("  [기술머신] 점도 꺼진다", [tms_cell(s) for s in bag.segs] == ["기술머신"] * 2)
    host.note_tms("??")
    chk("이상한 값은 무시한다", host.tm_new == 0)
    host.hub = None
    host.note_tms(4)
    chk("허브가 없어도 수는 적어 둔다 (열 때 칠한다)", host.tm_new == 4)


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))
    try:
        check_marks(root)
        check_pane(root)
        top, bag = check_bag(root)
        check_app(root, bag)
        bag.close()
        top.destroy()
        chk("화면 오류가 없다", not errors, errors[:2])
    finally:
        try:
            root.destroy()
        except Exception:                                   # noqa: BLE001
            pass
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
