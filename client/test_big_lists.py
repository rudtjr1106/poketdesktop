# -*- coding: utf-8 -*-
"""가방·상점의 긴 목록 검사 (보이는 줄만 만든다 - U.VirtualList).

    python client/test_big_lists.py

**창을 진짜로 띄운다.** 포켓몬 400마리, 도구 306종을 다 가진 계정으로 가방과 상점을 연다.

포켓몬과 도구가 많은 사람은 가방이 몇 초씩 끊겼다: 줄마다 위젯을 대여섯 개씩 만들어 5,600개가
되고, 도구를 하나 쓸 때마다 그것을 전부 부수고 다시 만들었다 (3초). 굴릴 때도 줄 수만큼 느렸다.

  1. **목록이 몇 줄이든 위젯은 화면만큼이다.** 굴리면 나간 줄을 들어온 자리에 다시 쓴다.
  2. 다시 쓰는 줄에 **지난 자료의 흔적이 남지 않는다**: 이름·개수·도트·고름·쓸 수 있는지.
  3. 도구를 고르면 보이는 포켓몬 줄이 그 도구 기준으로 다시 칠해지고, 굴려서 들어오는 줄도 그렇다.
  4. **도구를 써도 목록을 다시 만들지 않는다** - 개수만 바뀌고 보던 자리는 그대로다.
  5. 상점: 분류·찾기·사고팔기가 같은 줄 위에서 돈다.
"""
import io
import json
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-biglists-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_bag, ui_shop                    # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
import smoke_box_filter as SB                               # noqa: E402
from test_learn_dialog import texts                         # noqa: E402

OK = FAIL = 0
N_MONS = 400
DATA = os.path.join(ROOT, "server", "data")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def png(color):
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((10, 8, 54, 60), fill=color + (255,))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


class Api(SB.FakeApi):
    """도구를 전부 가진 계정. 응답 모양은 서버의 /api/shop · /api/pokemon 과 같다."""

    def __init__(self, mons, items):
        SB.FakeApi.__init__(self, mons)
        self.items = items
        self.bag = dict((it["id"], 3) for it in items)
        self.money = 500000
        self.png = png((90, 160, 230))
        self.used = []

    def shop(self):
        return {"money": self.money, "bag": dict((k, v) for k, v in self.bag.items() if v > 0),
                "items": [dict(i) for i in self.items], "sellRate": 0.5}

    def sprite(self, num, shiny=False):
        return self.png, ".png"

    def item_sprite(self, item_id):
        return None

    def use_item(self, item, pid, stat="", hour=None):
        self.used.append((item, pid))
        self.bag[item] = self.bag.get(item, 0) - 1
        for m in self.mons:
            if m["id"] == pid and item == "RARECANDY":
                m["level"] += 1
        return {"ok": True, "message": "썼다."}

    def hold(self, pid, item):
        self.used.append(("hold", item, pid))
        self.bag[item] = self.bag.get(item, 0) - 1
        return {"ok": True, "message": "지니게 했다."}

    def buy(self, item, n=1):
        self.bag[item] = self.bag.get(item, 0) + n
        return {"ok": True, "money": self.money, "bag": dict(self.bag), "message": "샀다."}

    def sell(self, item, n=1):
        self.bag[item] = self.bag.get(item, 0) - n
        return {"ok": True, "money": self.money, "bag": dict((k, v) for k, v in self.bag.items() if v > 0),
                "message": "팔았다."}


class App(object):
    def __init__(self, root, api, dex):
        self.root, self.api, self.dex = root, api, dex
        self.settings, self.balls, self.money = {}, 5, 0
        self.bag_window = self.shop_window = self.tm_window = None

    def request_sync(self):
        pass

    def notify(self, *_a):
        pass


def wait(root, cond, sec=20.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.005)
    return cond()


def settle(root, sec=0.25):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.005)


def widgets(w):
    n, stack = 0, [w]
    while stack:
        kids = stack.pop().winfo_children()
        n += len(kids)
        stack.extend(kids)
    return n


def cut(rows):
    """줄 안의 글자가 줄 밖으로 나간 것. 세로로 넘치면 글자가 위아래로 잘려 보인다.

    목록 바깥(단추·머리글)은 이 검사가 볼 것이 아니다 - 바뀐 것은 목록의 줄이다.
    """
    bad = []
    for key, r in rows:
        h = r.body.winfo_height()
        for c in r.body.winfo_children():
            if c.winfo_class() != "Label" or not c.winfo_ismapped():
                continue
            if c.winfo_reqheight() > h + 1 or c.winfo_y() < -1 or c.winfo_y() + c.winfo_height() > h + 1:
                bad.append((key, c.cget("text")[:12], c.winfo_reqheight(), c.winfo_y(), h))
    return bad


def sweep(root, vl, look, step=6):
    """목록을 위에서 아래까지 훑으며 보이는 줄마다 look(번호, 줄) 을 부른다. 끝나면 맨 위로."""
    seen = set()
    n = len(vl.entries)
    for i in list(range(0, n, step)) + [n - 1]:              # 마지막 줄까지 (see 는 그 줄만 보이게 굴린다)
        vl.see(i)
        root.update()
        for j, r in vl.shown():
            if j not in seen:
                seen.add(j)
                look(j, r)
    vl.canvas.yview_moveto(0.0)
    root.update()
    return seen


def wheel(root, top, canvas, n=4):
    """진짜 휠 사건을 그 목록의 줄 위에서 낸다 (U.install_wheel 이 받아 목록을 찾는다)."""
    x, y = canvas.winfo_rootx() + 60, canvas.winfo_rooty() + 50
    for _ in range(n):
        top.event_generate("<MouseWheel>", delta=-120, rootx=x, rooty=y)
        root.update()


class Line(object):
    """VirtualList 를 재는 가장 단순한 줄."""
    made = 0

    def __init__(self, parent, color="#223"):
        Line.made += 1
        self.f = tk.Frame(parent, bg=color)
        self.label = tk.Label(self.f, text="", bg=color, fg="#fff")
        self.label.place(x=4, rely=0.5, anchor="w")
        self.data = None
        self.binds = 0

    def bind(self, data):
        self.data = data
        self.binds += 1
        self.label.configure(text=str(data))


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    raw = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["items"]
    items = [dict(i, buyable=(int(i.get("cost") or 0) > 0 and i.get("cat") != "megastone"))
             for i in (raw.values() if isinstance(raw, dict) else raw)]
    nums = [s["num"] for s in dex.species if not s.get("mega")][:120]
    mons = [SB.mon(dex, nums[i % len(nums)], 1000 + i, on=(i < 6)) for i in range(N_MONS)]
    for i, m in enumerate(mons):
        m["level"] = 5 + (i % 90)
    mons[3]["shiny"] = True

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
    print("글꼴 %s / 본문 %dpt" % (U.FAMILY, U.FONT[1]))

    # ------------------------------------------------------------ VirtualList
    print("=== 보이는 줄만 만드는 목록 ===")
    top = tk.Toplevel(root)
    top.geometry("320x300+80+80")
    U.install_wheel(top)
    vl = U.VirtualList(top, {"line": (30, Line), "head": (20, lambda p: Line(p, "#532"))}, bg="#111")
    vl.pack(fill="both", expand=True)
    entries = []
    for i in range(1000):
        if i % 100 == 0:
            entries.append(("head", "머리 %d" % (i // 100)))
        entries.append(("line", "줄 %d" % i))
    vl.set(entries)
    settle(root)
    per_view = 300 // 30 + 2
    chk("천 줄이어도 만든 줄은 화면만큼이다 (%d개)" % Line.made, 0 < Line.made <= per_view + 2 * vl.MARGIN + 2
        and vl.made == Line.made, (Line.made, vl.made))
    shown = vl.shown()
    chk("  위에서부터 차례대로 보인다 (머리줄 다음에 줄 0, 1, 2 ...)", [r.data for _i, r in shown][:4] == ["머리 0", "줄 0", "줄 1", "줄 2"]
        and [i for i, _r in shown] == list(range(len(shown))), [r.data for _i, r in shown][:5])
    ys = [r.f.winfo_y() for _i, r in shown]
    chk("  줄은 제 높이만큼씩 내려간다 (머리줄 20, 줄 30)", ys[:4] == [0, 20, 50, 80] and shown[1][1].f.winfo_height() == 30
        and shown[0][1].f.winfo_height() == 20, ys[:5])
    chk("  폭은 목록 폭에 맞춘다", all(abs(r.f.winfo_width() - vl.canvas.winfo_width()) <= 1 for _i, r in shown))
    total = 1000 * 30 + 10 * 20
    chk("  굴릴 범위는 전체 높이다", vl.tops[-1] == total and vl.canvas.yview()[1] < 0.02, (vl.tops[-1], vl.canvas.yview()))
    made0 = Line.made
    vl.canvas.yview_moveto(0.5)
    settle(root, 0.15)
    mid = vl.shown()
    first = mid[0][0]
    chk("**굴리면 그 자리의 줄이 보인다** (만든 줄은 그대로다 - 나간 줄을 다시 쓴다)", entries[first][1] == mid[0][1].data
        and all(entries[i][1] == r.data for i, r in mid) and 480 < first < 530 and Line.made <= made0 + vl.MARGIN + 2,
        (first, mid[0][1].data, Line.made, made0))
    vl.canvas.yview_moveto(1.0)
    settle(root, 0.15)
    last = vl.shown()
    chk("  맨 아래: 마지막 줄까지 보인다", last[-1][0] == len(entries) - 1 and last[-1][1].data == "줄 999"
        and last[-1][1].f.winfo_y() + 30 <= vl.canvas.winfo_height() + 1, (last[-1][0], last[-1][1].data))
    for _ in range(60):
        vl.canvas.yview_scroll(-3, "units")
        vl.sync()
    settle(root, 0.1)
    chk("  한참 굴려도 만든 줄이 늘지 않는다", Line.made <= per_view + 2 * vl.MARGIN + 6, Line.made)
    vl.see(700)
    settle(root, 0.1)
    chk("  see(i) 는 그 줄이 보이게 굴린다", 700 in [i for i, _r in vl.shown()], [i for i, _r in vl.shown()][:3])
    at = vl.canvas.yview()[0]
    entries2 = [(k, d + "!") if k == "line" else (k, d) for k, d in entries]
    vl.set(entries2)
    settle(root, 0.1)
    chk("목록을 통째로 갈아도 보던 자리는 그대로다 (새 자료로 칠해진다)", abs(vl.canvas.yview()[0] - at) < 0.002
        and all(entries2[i][1] == r.data for i, r in vl.shown()) and Line.made <= per_view + 2 * vl.MARGIN + 6, vl.canvas.yview())
    vl.set(entries2[:5], keep=False)
    settle(root, 0.1)
    chk("화면보다 짧으면 굴릴 것이 없다 (맨 위에 붙는다)", vl.canvas.yview() == (0.0, 1.0) and len(vl.shown()) == 5
        and vl.shown()[0][1].f.winfo_y() == 0, vl.canvas.yview())
    binds = sum(r.binds for _i, r in vl.shown())
    vl.refresh()
    chk("refresh 는 보이는 줄만 다시 칠한다", sum(r.binds for _i, r in vl.shown()) == binds + 5)
    vl.set([])
    settle(root, 0.05)
    chk("빈 목록", vl.shown() == [] and vl.index(lambda k, d: True) is None)
    top.destroy()

    # ------------------------------------------------------------ 가방
    print("\n=== 가방: 포켓몬 %d마리 · 도구 %d종 ===" % (N_MONS, len(items)))
    api = Api(mons, items)
    app = App(root, api, dex)
    t0 = time.time()
    w = ui_bag.BagWindow(root, app)
    w.win.winfo_toplevel().deiconify()
    wait(root, lambda: bool(w.mons) and w._wait is None and w.mon_vl.shown())
    settle(root, 0.3)
    took = time.time() - t0
    n_w = widgets(w.win)
    chk("**위젯이 줄 수만큼 늘지 않는다**: 줄 %d + %d개에 위젯 %d개 (예전에는 5,600개), 여는 데 %.1f초"
        % (len(w.item_vl.entries), len(w.mon_vl.entries), n_w, took), n_w < 700 and w.mon_vl.made <= 30 and w.item_vl.made <= 40
        and len(w.mon_vl.entries) == N_MONS, (n_w, w.item_vl.made, w.mon_vl.made))
    heads = [d for k, d in w.item_vl.entries if k == "head"]
    chk("도구 목록: 분류마다 머리줄 하나 (가진 종 수와 함께), 그 아래 도구들", [c for c, _n in heads] == [c for c in ui_bag.CAT_ORDER if any(i["cat"] == c for i in items)]
        and sum(n for _c, n in heads) == len(items) == len([1 for k, _d in w.item_vl.entries if k == "item"]), heads)
    first = w.item_vl.shown()
    chk("  첫 줄은 분류 머리줄, 다음부터 도구 (이름과 개수)", isinstance(first[0][1], ui_bag.HeadRow)
        and first[0][1].label.cget("text") == "%s · %d종" % (ui_bag.CAT_KR[heads[0][0]], heads[0][1])
        and first[1][1].name.cget("text") == w._owned()[0]["kr"] and first[1][1].count.cget("text") == "3개",
        (first[0][1].label.cget("text"), first[1][1].name.cget("text")))
    sel = [iid for iid, r in w.shown_items() if r.selected]
    chk("  고른 도구 한 줄만 칠해져 있다", sel == [w.item_id] and w.item_id is not None, (sel, w.item_id))
    rows = w.shown_mons()
    chk("포켓몬 목록: 위에서부터 차례대로, 이름·레벨·도트가 그 포켓몬의 것이다", [pid for pid, _r in rows][:3] == [1000, 1001, 1002]
        and all(r.lv.cget("text") == "Lv.%d" % r.mon["level"] and str(r.art.cget("image")) for _p, r in rows)
        and rows[3][1].name.cget("text").startswith("★ "), [(p, r.lv.cget("text")) for p, r in rows[:3]])
    bad = cut(w.shown_items()) + cut(w.shown_mons())
    chk("  줄 안의 글자가 줄 높이를 넘지 않는다 (도구 %d줄, 포켓몬 %d줄)" % (len(w.shown_items()), len(rows)), not bad, bad[:3])
    over, wrong = [], []

    def look_item(j, r):
        kind, d = w.item_vl.entries[j]
        if kind != "item":
            return
        if r.name.cget("text") != d["kr"] or r.item is not d:
            wrong.append((j, d["kr"], r.name.cget("text")))
        if r.name.winfo_x() + r.name.winfo_reqwidth() > r.count.winfo_x():
            over.append((d["kr"], r.name.winfo_x() + r.name.winfo_reqwidth(), r.count.winfo_x()))
    seen = sweep(root, w.item_vl, look_item)
    chk("**도구 목록을 끝까지 훑어도 줄마다 제 도구다** (%d줄 전부, 만든 줄은 %d개)" % (len(seen), w.item_vl.made),
        not wrong and len(seen) == len(w.item_vl.entries) and w.item_vl.made <= 40, (wrong[:3], len(seen), w.item_vl.made))
    chk("  긴 이름도 개수와 겹치지 않는다", not over, over[:3])
    wrong = []

    def look_mon(j, r):
        m = w.mon_vl.entries[j][1]
        want = ("★ " if m.get("shiny") else "") + (m.get("info") or {}).get("name", m.get("species", "?"))
        if r.mon is not m or r.name.cget("text") != want or r.lv.cget("text") != "Lv.%d" % m["level"]:
            wrong.append((j, want, r.name.cget("text"), r.lv.cget("text")))
    seen = sweep(root, w.mon_vl, look_mon)
    chk("**포켓몬 목록도 끝까지 훑어 줄마다 제 포켓몬이다** (%d줄 전부, 만든 줄은 %d개)" % (len(seen), w.mon_vl.made),
        not wrong and len(seen) == N_MONS and w.mon_vl.made <= 30, (wrong[:3], len(seen), w.mon_vl.made))

    top_w = w.win.winfo_toplevel()
    for label, vl in (("포켓몬 목록", w.mon_vl), ("도구 목록", w.item_vl)):
        wheel(root, top_w, vl.canvas)
        settle(root, 0.1)
        first = vl.shown()
        chk("**%s 위에서 휠을 내리면 굴러가고, 들어온 줄이 칠해져 있다**" % label, vl.canvas.yview()[0] > 0.0 and first[0][0] > 0
            and all(vl.entries[i][1] is (r.mon if hasattr(r, "mon") else getattr(r, "item", None))
                    for i, r in first if vl.entries[i][0] != "head"), (vl.canvas.yview(), first[0][0]))
        vl.canvas.yview_moveto(0.0)
    settle(root, 0.1)

    print("\n=== 도구를 고르면 ===")
    w.pick_item("RARECANDY")
    root.update()
    rows = w.shown_mons()
    chk("이상한사탕: 보이는 줄마다 'Lv.n → Lv.n+1' 이 붙는다", all(r.note.cget("text") == "Lv.%d → Lv.%d" % (r.mon["level"], r.mon["level"] + 1)
                                                      for _p, r in rows) and len(rows) >= 8, [r.note.cget("text") for _p, r in rows[:3]])
    w.mon_canvas.yview_moveto(1.0)
    settle(root, 0.15)
    rows = w.shown_mons()
    chk("  **굴려서 들어온 줄도 그 도구 기준으로 칠해져 있다** (맨 아래 = 마지막 포켓몬)", rows[-1][0] == mons[-1]["id"]
        and all(r.note.cget("text") == "Lv.%d → Lv.%d" % (r.mon["level"], r.mon["level"] + 1) for _p, r in rows)
        and w.mon_vl.made <= 30, (rows[-1][0], [r.note.cget("text") for _p, r in rows[-2:]]))
    target = rows[-2][0]
    rows[-2][1]._click(None)
    root.update()
    chk("  줄을 누르면 그 포켓몬이 골라진다 (그 줄만 칠해진다)", w.mon_id == target
        and [p for p, r in w.shown_mons() if r.selected] == [target], (w.mon_id, target))
    stone = next(i for i in items if (i.get("effect") or {}).get("kind") == "stone" and i.get("evolves"))
    w.pick_item(stone["id"])
    root.update()
    rows = w.shown_mons()
    chk("진화의 돌: 통하는 포켓몬 줄만 밝게 (줄의 상태가 자료와 같다)", all(r.good == w._states[p][0] and r.note.cget("text") == w._states[p][2]
                                                         for p, r in rows) and not any("Lv." in r.note.cget("text") for _p, r in rows))
    ball = next(i["id"] for i in items if i["cat"] == "ball")
    at = w.mon_canvas.yview()[0]
    w.pick_item(ball)
    root.update()
    chk("쓸 수 없는 도구(볼)를 고르면 목록 자리에 안내가 선다", w.mon_note.winfo_ismapped() and not w.mon_vl.holder.winfo_ismapped())
    w.pick_item("RARECANDY")
    settle(root, 0.1)
    chk("  다시 쓸 수 있는 도구를 고르면 목록이 돌아온다 (보던 자리 그대로)", w.mon_vl.holder.winfo_ismapped() and not w.mon_note.winfo_ismapped()
        and abs(w.mon_canvas.yview()[0] - at) < 0.01 and len(w.shown_mons()) >= 8, w.mon_canvas.yview())
    w.item_canvas.yview_moveto(1.0)
    settle(root, 0.15)
    tail = w.shown_items()
    chk("도구 목록을 맨 아래까지 굴리면 마지막 도구가 보인다 (볼)", tail[-1][0] == w._owned()[-1]["id"]
        and tail[-1][1].name.cget("text") == w._owned()[-1]["kr"] and w.item_vl.made <= 40, tail[-1][0])
    r0 = tail[-1][1]
    r0._in(None)
    hov = r0.body.cget("bg")
    r0._out(None)
    chk("  마우스를 올리면 그 줄이 밝아졌다 돌아온다", hov == U.BG2 and r0.body.cget("bg") == ui_bag.ROW_BG, hov)

    print("\n=== 도구를 쓴다 ===")
    w.pick_item("RARECANDY")
    w.pick_mon(target)
    root.update()
    made = (w.item_vl.made, w.mon_vl.made, widgets(w.win))
    at_m, at_i = w.mon_canvas.yview()[0], w.item_canvas.yview()[0]
    lv0 = next(m for m in mons if m["id"] == target)["level"]
    t0 = time.time()
    w.do_use()
    wait(root, lambda: api.used and w._wait is None and next(m for m in w.mons if m["id"] == target)["level"] == lv0 + 1
         and w.bag.get("RARECANDY") == 2)
    settle(root, 0.2)
    took = time.time() - t0
    row = dict(w.shown_mons()).get(target)
    chk("**써도 목록을 다시 만들지 않는다** (줄 위젯 그대로, %.2f초)" % took, (w.item_vl.made, w.mon_vl.made) == made[:2]
        and abs(widgets(w.win) - made[2]) <= 4 and api.used == [("RARECANDY", target)], (made, w.item_vl.made, w.mon_vl.made, widgets(w.win)))
    chk("  보던 자리 그대로다", abs(w.mon_canvas.yview()[0] - at_m) < 0.005 and abs(w.item_canvas.yview()[0] - at_i) < 0.005,
        (w.mon_canvas.yview()[0], at_m))
    chk("  그 포켓몬의 줄이 새 레벨로, 그대로 골라진 채 칠해져 있다", row is not None and row.lv.cget("text") == "Lv.%d" % (lv0 + 1)
        and row.selected and row.note.cget("text") == "Lv.%d → Lv.%d" % (lv0 + 1, lv0 + 2), row and row.lv.cget("text"))
    w.item_vl.see(w.item_vl.index(lambda k, d: k == "item" and d["id"] == "RARECANDY"))
    settle(root, 0.1)
    cnt = dict(w.shown_items())["RARECANDY"].count.cget("text")
    chk("  도구의 개수가 줄었다 (3 → 2)", cnt == "2개" and w.i_count.cget("text") == "2개", cnt)
    for _ in range(2):
        w.do_use()
        wait(root, lambda: len(api.used) >= 2 and w._wait is None and "RARECANDY" not in [i["id"] for i in w._owned()] or w.bag.get("RARECANDY") == 1, 10)
        settle(root, 0.15)
    wait(root, lambda: w.bag.get("RARECANDY", 0) == 0 and w._wait is None, 10)
    settle(root, 0.2)
    chk("다 쓰면 그 도구 줄이 목록에서 빠지고 다른 도구가 골라진다", "RARECANDY" not in [d["id"] for k, d in w.item_vl.entries if k == "item"]
        and w.item_id not in (None, "RARECANDY") and len(api.used) == 3, (w.item_id, len(api.used)))
    bad = cut(w.shown_items()) + cut(w.shown_mons())
    chk("  줄 안의 글자가 줄 높이를 넘지 않는다", not bad, bad[:3])
    api.bag = {}
    w.reload()
    wait(root, lambda: w._wait is None and not w._owned(), 10)
    settle(root, 0.2)
    chk("가방이 비면 목록 대신 그렇다고 적는다", "가방이 비어 있다." in texts(w.win) and not w.item_vl.holder.winfo_ismapped())
    api.bag = {"RARECANDY": 1}
    api.mons = []
    w.reload()
    wait(root, lambda: w._wait is None and w._owned() and not w.mons, 10)
    settle(root, 0.2)
    chk("포켓몬이 없으면 대상 목록 자리에 그렇다고 적는다 (도구 목록은 돌아온다)", w.item_vl.holder.winfo_ismapped()
        and "가진 포켓몬이 없다." in texts(w.win) and len(w.shown_items()) == 1, texts(w.win)[-4:])
    w.close()
    root.update()

    # ------------------------------------------------------------ 상점
    print("\n=== 상점: 도구 %d종 ===" % len([i for i in items if i["cat"] != "megastone"]))
    api = Api(mons, items)
    app = App(root, api, dex)
    s = ui_shop.ShopWindow(root, app)
    s.win.winfo_toplevel().deiconify()
    wait(root, lambda: bool(s.items) and s._wait is None and s.vl.shown())
    settle(root, 0.3)
    sold = [i for i in items if i["cat"] != "megastone"]
    n_w = widgets(s.win)
    chk("**위젯이 줄 수만큼 늘지 않는다**: %d줄에 위젯 %d개 (예전에는 2,000개)" % (len(s.vl.entries), n_w), n_w < 500
        and len(s.vl.entries) == len(sold) and s.vl.made <= 30, (n_w, s.vl.made))
    rows = s.shown_rows()
    chk("위에서부터 차례대로: 이름·등급·값·가진 개수", [iid for iid, _r in rows][:3] == [i["id"] for i in sold[:3]]
        and rows[0][1].name_cell.cget("text") == sold[0]["kr"] and rows[0][1].have_cell.cget("text") == "3개",
        (rows[0][0], rows[0][1].name_cell.cget("text")))
    chk("  첫 도구가 골라져 있고 오른쪽에 설명이 뜬다", s.sel == sold[0]["id"] and [i for i, r in rows if r.selected] == [s.sel]
        and s.d_name.cget("text") == sold[0]["kr"], (s.sel, s.d_name.cget("text")))
    wheel(root, s.win.winfo_toplevel(), s.canvas)
    settle(root, 0.1)
    first = s.shown_rows()
    chk("**목록 위에서 휠을 내리면 굴러가고, 들어온 줄이 칠해져 있다**", s.canvas.yview()[0] > 0.0 and first[0][0] != sold[0]["id"]
        and all(r.name_cell.cget("text") == r.it["kr"] for _i, r in first), (s.canvas.yview(), first[0][0]))
    s.canvas.yview_moveto(0.0)
    settle(root, 0.1)
    made = s.vl.made
    s.set_cat("ball")
    settle(root, 0.1)
    balls = [i for i in sold if i["cat"] == "ball"]
    rows = s.shown_rows()
    chk("분류를 누르면 그 분류만 (%d종). 줄을 새로 만들지 않는다" % len(balls), len(s.vl.entries) == len(balls)
        and [iid for iid, _r in rows] == [i["id"] for i in balls][:len(rows)] and s.vl.made <= made + 2
        and s.found.cget("text") == "%d개" % len(balls) and s.sel == balls[0]["id"], (len(s.vl.entries), s.vl.made, made))
    s.set_cat("all")
    s.q.set("열매")
    settle(root, 0.1)
    berries = [i for i in sold if "열매" in i["kr"]]
    chk("이름으로 찾기: '열매' (%d종)" % len(berries), len(s.vl.entries) == len(berries) > 5
        and all("열매" in r.name_cell.cget("text") for _i, r in s.shown_rows()), len(s.vl.entries))
    s.q.set("없는도구이름")
    settle(root, 0.1)
    chk("맞는 것이 없으면 그렇다고 적는다", s._nomatch.winfo_ismapped() and s.vl.shown() == [] and s.sel is None)
    s.q.set("")
    settle(root, 0.1)
    chk("  지우면 전부 돌아온다", not s._nomatch.winfo_ismapped() and len(s.vl.entries) == len(sold) and s.sel == sold[0]["id"])
    s.canvas.yview_moveto(1.0)
    settle(root, 0.15)
    rows = s.shown_rows()
    chk("맨 아래까지 굴리면 마지막 도구가 보인다", rows[-1][0] == sold[-1]["id"] and rows[-1][1].name_cell.cget("text") == sold[-1]["kr"]
        and s.vl.made <= 32, (rows[-1][0], s.vl.made))
    pick = rows[-3][0]
    rows[-3][1]._click(None)
    root.update()
    chk("줄을 누르면 그 도구가 골라진다 (그 줄만 칠해지고 설명이 바뀐다)", s.sel == pick and [i for i, r in s.shown_rows() if r.selected] == [pick]
        and s.d_name.cget("text") == next(i["kr"] for i in sold if i["id"] == pick), (s.sel, pick))
    buy = next((iid for iid, r in s.shown_rows() if r.it.get("buyable")), None)
    if buy is None:
        s.canvas.yview_moveto(0.0)
        settle(root, 0.1)
        buy = next(iid for iid, r in s.shown_rows() if r.it.get("buyable"))
    s.select(buy)
    root.update()
    at = s.canvas.yview()[0]
    made = s.vl.made
    s.do_buy()
    wait(root, lambda: api.bag.get(buy) == 4 and not s.busy, 10)
    settle(root, 0.15)
    row = dict(s.shown_rows()).get(buy)
    chk("**사면 그 줄의 가진 개수만 바뀐다** (3 → 4. 목록은 그대로, 보던 자리도 그대로)", row is not None and row.have_cell.cget("text") == "4개"
        and s.vl.made == made and abs(s.canvas.yview()[0] - at) < 0.005 and s.d_have.cget("text").startswith("4"),
        (row and row.have_cell.cget("text"), s.d_have.cget("text")))
    bad = cut(s.shown_rows())
    chk("줄 안의 글자가 줄 높이를 넘지 않는다", not bad, bad[:3])
    s.set_cat("all")
    settle(root, 0.1)
    wrong = []

    def look_shop(j, r):
        d = s.vl.entries[j][1]
        if r.it is not d or r.name_cell.cget("text") != d["kr"] or r.have_cell.cget("text") != "%d개" % api.bag.get(d["id"], 0):
            wrong.append((j, d["kr"], r.name_cell.cget("text"), r.have_cell.cget("text")))
    seen = sweep(root, s.vl, look_shop)
    chk("**상점 목록을 끝까지 훑어도 줄마다 제 도구다** (%d줄 전부, 만든 줄은 %d개)" % (len(seen), s.vl.made),
        not wrong and len(seen) == len(sold) and s.vl.made <= 32, (wrong[:3], len(seen), s.vl.made))
    s.close()
    root.update()
    chk("도는 동안 오류 없음", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
