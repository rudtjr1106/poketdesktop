# -*- coding: utf-8 -*-
"""포켓몬 관리 창의 거르기·지닌 도구 칸 — 진짜 Tk 로 확인.

    python client/smoke_box_filter.py

서버 없이 돈다. app 과 api 를 흉내 내고 창을 실제로 띄운 뒤,
  · 타입 드롭다운과 이름 칸이 **PC 박스만** 줄이는지 (파티는 늘 보인다)
  · 지닌 도구가 상세 칸에 뜨는지
  · 도구 고르기 창이 가방의 지닐 수 있는 것만 보여주는지
를 본다. 드롭다운 자체는 안 연다 - 윈도우에서는 tk.Menu 가 모달이라
검사가 멈추고, 맥에서는 PopupMenu 창이 뜬다. 줄 목록(_type_rows)만 본다.

## 줄은 다시 만들지 않는다

목록은 받은 포켓몬마다 줄을 **한 번** 만들어 두고, 거르기는 담았다
뺐다만 한다. 그래서 win.rows 에는 거름망에 걸려 **숨긴 줄도** 들어 있다.
'보이는 것' 은 목록 틀에 담긴(pack) 줄을 화면 순서대로 읽어서 본다(shown).
처음 만들 때는 첫 화면만큼 먼저 만들고 나머지는 나눠 만든다(U.Chunked) -
그 도중에 거르기를 바꾸거나 아직 없는 줄을 골라도 맞아야 한다.
"""
import json
import os
import sys
import tempfile
import threading
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-smoke-box-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import box_filter                         # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import eggs_ui                            # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, n=8):
    for _ in range(n):
        root.update()


def wait_for(root, cond, secs=4):
    end = time.time() + secs
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.02)
    return cond()


def settle_rows(root, win):
    """줄을 나눠 만들고 담는 일까지 다 끝날 때까지 돌린다."""
    wait_for(root, lambda: not (win._rows_job is not None and win._rows_job.pending))
    settle(root)


def shown(win):
    """지금 목록에 담긴 포켓몬 id, 화면 순서대로 (숨긴 줄은 빠진다)."""
    by_frame = dict((str(r.f), pid) for pid, r in win.rows.items())
    return [by_frame[str(s)] for s in win.inner.pack_slaves()
            if str(s) in by_frame]


def layout(win):
    """목록 틀에 담긴 것 전부를 화면 순서대로.

    줄은 id, 줄 아래 선은 '-', 'PC 박스' 머리는 '머리', 그 아래 굵은 선은
    '=', 맞는 게 없을 때의 한 줄은 '없음'. 모르는 것이 끼면 '?'.
    """
    names = {str(win._sep): "머리", str(win._box_top): "=",
             str(win._nomatch): "없음"}
    for pid, r in win.rows.items():
        names[str(r.f)] = pid
        names[str(r.line)] = "-"
    return [names.get(str(s), "?") for s in win.inner.pack_slaves()]


def page_ids(box_ids, page=0):
    """그 박스(쪽)에 담길 id 들. 창은 한 쪽만 그린다 (ui_box.BOX_SIZE)."""
    n = ui_box.BOX_SIZE
    return box_ids[page * n:(page + 1) * n]


def full_layout(party_ids, box_ids):
    out = []
    for pid in party_ids:
        out += [pid, "-"]
    if box_ids:
        out += ["머리", "="]
    for pid in box_ids:
        out += [pid, "-"]
    return out


def picked(win):
    """고른 모습으로 칠해진 줄 id (숨긴 줄 포함)."""
    return sorted(pid for pid, r in win.rows.items()
                  if r.selected or r.f.cget("bg") == "#2b2417")


def mon(dex, num, pid, on=False, nickname=None, held=None):
    sp = dex.get(num)
    m = {"id": pid, "species": sp["internal"], "num": num, "level": 20,
         "nickname": nickname, "onDesktop": on, "gender": "M",
         "ivs": {}, "evs": {}, "moves": [], "exp": 0, "nature": "HARDY"}
    m["info"] = dex.describe(dict(m, exp=P.exp_for_level(sp.get("growth", "medium"), 20)))
    m["info"]["name"] = nickname or sp["kr"]
    if held:
        m["held"] = held
        m["heldKr"] = {"LEFTOVERS": "먹다남은음식", "ORANBERRY": "오랭열매"}[held]
        m["heldDesc"] = "지니게 하면 조금씩 회복된다."
    return m


class FakeApi(object):
    def __init__(self, mons):
        self.box_size = 30
        self.box_names = {}
        self.mons = mons
        self.eggs = []
        self.calls = []
        self.gate = threading.Event()     # pokemon() 을 잠깐 붙잡는다
        self.gate.set()

    def pokemon(self):
        self.gate.wait(10)
        return self.mons

    def pokemon_and_eggs(self):
        return self.pokemon(), list(self.eggs)

    def pokemon_boxes(self):
        """서버 /api/pokemon 과 같은 모양. 박스 정보가 함께 온다."""
        mons = self.pokemon()
        used = {}
        for m in mons:
            if not m.get("onDesktop"):
                k = str(int(m.get("box") or 0))
                used[k] = used.get(k, 0) + 1
        return (mons, list(self.eggs),
                {"size": self.box_size, "count": 32,
                 "names": dict(self.box_names), "used": used})

    def set_box(self, pid, no):
        self.calls.append(("box", pid, no))
        for m in self.mons:
            if m["id"] == pid:
                m["box"] = int(no)
                m["onDesktop"] = False
        return {"ok": True}

    def set_box_name(self, no, name):
        self.calls.append(("boxname", no, name))
        if name:
            self.box_names[str(no)] = name
        else:
            self.box_names.pop(str(no), None)
        return {"ok": True, "names": dict(self.box_names)}

    def set_desktop(self, pid, on):
        self.calls.append(("desktop", pid, on))
        return {"ok": True}

    def set_order(self, ids):
        self.calls.append(("order", list(ids)))
        return {"ok": True}

    def item_sprite(self, item_id):
        p = os.path.join(HERE, "..", "server", "data", "item_sprites", "%s.png" % item_id)
        return open(p, "rb").read() if os.path.exists(p) else None

    def shop(self):
        return {"money": 0, "bag": {"ORANBERRY": 2, "POKEBALL": 5, "FIRESTONE": 1},
                "items": [
                    {"id": "ORANBERRY", "kr": "오랭열매", "cat": "held", "holdable": True,
                     "desc": "HP를 10만큼 회복한다.", "effect": {"kind": "held"}},
                    {"id": "POKEBALL", "kr": "몬스터볼", "cat": "ball", "holdable": False,
                     "effect": {"kind": "ball"}},
                    {"id": "FIRESTONE", "kr": "불꽃의돌", "cat": "stone", "holdable": False,
                     "effect": {"kind": "stone"}},
                    {"id": "LEFTOVERS", "kr": "먹다남은음식", "cat": "held", "holdable": True,
                     "desc": "조금씩 회복", "effect": {"kind": "held"}},
                ]}

    def hold(self, pid, item):
        self.calls.append(("hold", pid, item))
        return {"ok": True}

    def unhold(self, pid):
        self.calls.append(("unhold", pid))
        return {"ok": True}


class FakeApp(object):
    def __init__(self, root, dex, mons):
        self.root = root
        self.dex = dex
        self.api = FakeApi(mons)
        self.balls = 5
        self.box_window = None
        self.synced = 0

    def request_sync(self):
        self.synced += 1


def make_gif(path):
    """두 장짜리 작은 도트. 상세 칸 도트를 네트워크 없이 풀어 보려고."""
    frames = []
    for dx in (0, 3):
        im = Image.new("P", (40, 40), 0)
        im.putpalette([0, 0, 0, 220, 70, 60] + [0] * (254 * 3))
        for y in range(8, 32):
            for x in range(10 + dx, 26 + dx):
                im.putpixel((x, y), 1)
        frames.append(im)
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   transparency=0, duration=90, loop=0, disposal=2)
    return path


def hidden_rows_are_capped(root, dex):
    """박스를 넘기면 지난 박스의 줄은 숨겨만 둔다. **끝없이 쌓이지는 않는다** (1.10.4).

    박스를 다 넘겨 본 사람은 가진 포켓몬 전부의 줄이 쌓였다 - 400마리면 위젯 5,200개, 그 창을
    닫는 데만 0.7초. 숨긴 줄은 두 박스치(ROW_KEEP)까지만 들고, 넘친 것은 오래된 것부터 치운다.
    """
    print()
    print("-- 숨긴 줄은 두 박스치까지만")
    n = ui_box.BOX_SIZE
    party = [mon(dex, 1 + i, 5000 + i, on=True) for i in range(3)]
    box = [mon(dex, 10 + (i % 140), 6000 + i) for i in range(n * 7)]         # 박스 일곱 개
    for i, m in enumerate(box):
        m["box"] = i // n
    app = FakeApp(root, dex, party + box)
    win = ui_box.BoxWindow(root, app)
    try:
        settle_rows(root, win)
        party_ids = [m["id"] for m in party]
        box_ids = [m["id"] for m in box]

        def rest():
            settle_rows(root, win)
            wait_for(root, lambda: not (win._prune_job is not None and win._prune_job.pending))
            settle(root)

        def hidden():
            vis = set(shown(win))
            return [p for p in win.rows if p not in vis]
        chk("처음에는 보이는 줄만 있다 (파티 3 + 첫 박스 %d)" % n, len(win.rows) == 3 + n and not hidden(), len(win.rows))
        for no in range(1, 7):
            win.goto_box(no)
            rest()
        chk("박스 일곱 개를 다 넘겨도 숨긴 줄은 %d줄을 넘지 않는다 (가진 것은 %d마리)" % (ui_box.ROW_KEEP, len(box)),
            len(hidden()) == ui_box.ROW_KEEP and len(win.rows) == 3 + n + ui_box.ROW_KEEP, (len(hidden()), len(win.rows)))
        chk("  남긴 것은 방금 본 두 박스다 (오래된 것부터 치운다)",
            sorted(hidden()) == sorted(page_ids(box_ids, 4) + page_ids(box_ids, 5)), sorted(hidden())[:4])
        chk("  치운 줄의 위젯은 남지 않는다", len(win.inner.winfo_children()) == 2 * len(win.rows) + 3,
            (len(win.inner.winfo_children()), len(win.rows)))
        chk("  지금 보는 박스는 그대로 순서대로 있다", layout(win) == full_layout(party_ids, page_ids(box_ids, 6)), layout(win)[:10])
        keep = dict((p, win.rows[p]) for p in page_ids(box_ids, 5))
        win.goto_box(5)
        rest()
        chk("방금 본 박스로 돌아가면 그 줄을 그대로 쓴다 (새로 안 만든다)",
            all(win.rows[p] is r for p, r in keep.items()) and layout(win) == full_layout(party_ids, page_ids(box_ids, 5)))
        win.goto_box(0)
        rest()
        chk("치운 박스로 돌아가면 다시 만들어 제대로 보인다", layout(win) == full_layout(party_ids, page_ids(box_ids, 0))
            and win.rows[box_ids[0]].name_cell.cget("text") == box[0]["info"]["name"]
            and len(hidden()) <= ui_box.ROW_KEEP, (layout(win)[:8], len(hidden())))
        far = box_ids[n * 3 + 7]
        win.select(far)                              # 치워진 박스의 포켓몬을 고른다 (도트를 두 번 눌러 열 때)
        rest()
        chk("치워진 박스의 포켓몬을 골라도 그 박스가 열리고 골라진다", win.box_no == 3 and win.sel == far and picked(win) == [far]
            and far in shown(win), (win.box_no, win.sel, picked(win)))
        win.f_query.set(box[n * 6 + 3]["info"]["name"][:2])    # 찾기: 박스를 넘어 모은다
        rest()
        found = shown(win)[3:]
        chk("찾기는 치워진 박스의 것도 찾는다 (%d마리)" % len(found), len(found) >= 1
            and all(p in win._by_id for p in found) and box_ids[n * 6 + 3] in found, found[:5])
        win.f_query.set("")
        rest()
        chk("  풀면 보던 박스로 돌아오고, 숨긴 줄은 여전히 %d줄 안쪽이다" % ui_box.ROW_KEEP,
            layout(win) == full_layout(party_ids, page_ids(box_ids, 3)) and len(hidden()) <= ui_box.ROW_KEEP,
            (layout(win)[:8], len(hidden())))
    finally:
        try:
            win.close()
        except Exception:                                   # noqa: BLE001
            pass


def hyper_and_evs(root, dex):
    """병뚜껑과 노력치가 상세 칸에 **보이는가.**

    사용자 제보: "병뚜껑으로 31 로 올려도 반영이 안 되는 것처럼 보인다."
    실제로는 능력치에 제대로 들어가는데(effective_ivs) 화면이 원래 개체값을
    그대로 보여줘서, 올라간 능력치 옆에 '개체 7' 이 그대로 남아 있었다.
    노력치는 아예 보여주는 데가 없었다.
    """
    print()
    print("-- 병뚜껑·노력치 표시")
    sp = dex.get(445)                      # 한카리아스
    m = {"id": 1, "species": sp["internal"], "num": 445, "level": 50,
         "nickname": None, "onDesktop": True, "gender": "M", "shiny": False,
         "ivs": dict((x, 7) for x in P.STATS),
         "evs": {"hp": 6, "atk": 252, "def": 0, "spa": 0, "spd": 0, "spe": 252},
         "hyper": {"atk": True, "spe": True},
         "moves": [], "nature": "JOLLY",
         "exp": P.exp_for_level(sp.get("growth", "medium"), 50)}
    m["info"] = dex.describe(m)
    app = FakeApp(root, dex, [m])
    win = ui_box.BoxWindow(root, app)
    settle_rows(root, win)
    win.select(1)
    settle(root)

    plain = dex.describe(dict(m, hyper={}))
    chk("병뚜껑이 능력치를 실제로 올린다",
        m["info"]["stats"]["atk"] > plain["stats"]["atk"],
        (plain["stats"]["atk"], m["info"]["stats"]["atk"]))
    labels = dict((k, win.bars[k][2].cget("text")) for k, _l in ui_box.STAT_ROWS)
    chk("병뚜껑 쓴 능력은 31 로 보인다",
        labels["atk"].startswith("개체 31") and labels["spe"].startswith("개체 31"),
        labels)
    chk("병뚜껑 표시가 붙는다", "✦" in labels["atk"], labels["atk"])
    chk("안 쓴 능력은 원래대로", labels["def"] == "개체 7", labels["def"])
    total = win.d_ivsum.cget("text")
    chk("합계도 쳐준 값으로", "90 / 186" in total, total)
    chk("합계에 병뚜껑을 알린다", "병뚜껑" in total, total)
    evline = win.d_evsum.cget("text")
    chk("노력치를 보여준다", "510 / 510" in evline, evline)
    chk("어느 능력에 붙었는지 보여준다",
        "공격 252" in evline and "스피드 252" in evline, evline)
    # **능력치 칸만 본다.** 창 전체를 보면 여기서 안 건드린 자리의 2~4px
    # 눌림(윈도우에서만 나는 것)까지 걸려서, 정작 보려는 것이 묻힌다.
    bad = squeezed(win._d_stats)
    chk("능력치 칸에 눌린 위젯 없음", not bad, bad[:3])
    try:
        win.close()
    except Exception:                                       # noqa: BLE001
        pass


def main():
    with open(os.path.join(HERE, "..", "server", "data", "pokedex.json"),
              encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()

    # 파티: 파이리(별명·지닌 도구)·꼬부기·피카츄   박스: 이상해씨·이브이(별명)·리자몽
    mons = [mon(dex, 4, 1, on=True, nickname="불꽃이", held="LEFTOVERS"),
            mon(dex, 7, 2, on=True), mon(dex, 25, 3, on=True),
            mon(dex, 1, 4), mon(dex, 133, 5, nickname="이브"), mon(dex, 6, 6)]
    app = FakeApp(root, dex, mons)
    win = ui_box.BoxWindow(root, app)
    wait_for(root, lambda: getattr(win, "mons", None))
    settle_rows(root, win)

    print("-- 전설·환상 표시")
    # **전설 줄을 실제로 그려 본다.** 표시를 넣을 때 eggs_ui 를 모듈 밖에서
    # 부르는 바람에 전설 포켓몬 줄에서만 터졌는데, 검사 자료에 전설이
    # 없어서 안 걸렸다.
    legend = [mon(dex, 150, 90, on=True),          # 뮤츠 - 전설
              mon(dex, 151, 91),                   # 뮤 - 환상
              mon(dex, 25, 92)]                    # 피카츄 - 아무것도 아님
    lapp = FakeApp(root, dex, legend)
    lwin = ui_box.BoxWindow(root, lapp)
    wait_for(root, lambda: getattr(lwin, "mons", None))
    settle_rows(root, lwin)
    names = dict((pid, r.name_cell.cget("text")) for pid, r in lwin.rows.items())
    kinds = dict((pid, r.legend) for pid, r in lwin.rows.items())
    chk("전설에 표식", names.get(90, "").startswith("◆") and kinds.get(90) == "legendary",
        (names.get(90), kinds.get(90)))
    chk("환상에 표식", names.get(91, "").startswith("✦") and kinds.get(91) == "mythical",
        (names.get(91), kinds.get(91)))
    chk("보통 포켓몬에는 표식이 없다", kinds.get(92) is None and "◆" not in names.get(92, ""),
        (names.get(92), kinds.get(92)))
    lwin.select(92)          # 고른 줄은 글자색이 달라진다 - 피해서 잰다
    settle(root)
    chk("전설·환상 색이 알과 같다",
        lwin.rows[90].name_cell.cget("fg") == eggs_ui.EGG_COLOR["legendary"]
        and lwin.rows[91].name_cell.cget("fg") == eggs_ui.EGG_COLOR["mythical"],
        (lwin.rows[90].name_cell.cget("fg"), lwin.rows[91].name_cell.cget("fg")))
    lwin.select(91)
    settle(root)
    chips = [w.cget("text") for w in lwin.d_types.winfo_children()
             if "text" in w.keys()]
    chk("상세 칸에 '환상' 칩", "환상" in chips, chips)
    lwin.close()

    print("-- 목록과 드롭다운")
    chk("여섯 마리가 다 그려진다 (파티 -> 박스 순)", shown(win) == [1, 2, 3, 4, 5, 6], shown(win))
    chk("줄 사이 선과 'PC 박스' 머리까지 제자리",
        layout(win) == full_layout([1, 2, 3], [4, 5, 6]), layout(win))
    chk("머리 글씨", win._sep_label.cget("text") == "PC 박스 · 3마리",
        win._sep_label.cget("text"))
    chk("드롭다운에는 **박스에 있는** 타입만 (풀·독·노말·불꽃·비행)",
        set(win.type_choices) == {"GRASS", "POISON", "NORMAL", "FIRE", "FLYING"},
        win.type_choices)
    rows = win._type_rows()
    chk("첫 줄은 '전체' 이고 지금 골라져 있다",
        rows[0]["text"] == "전체" and rows[0]["checked"] is True, rows[0])
    chk("구분선 다음에 타입들", rows[1] is None and len(rows) == 2 + len(win.type_choices), len(rows))
    chk("단추 글씨", "전체" in win.btn_type.label.cget("text"), win.btn_type.label.cget("text"))

    print("-- 타입 (박스에만 걸린다)")
    keep = dict(win.rows)
    win._set_type("FIRE")
    settle_rows(root, win)
    chk("파티 셋은 그대로 + 박스는 리자몽만", shown(win) == [1, 2, 3, 6], shown(win))
    chk("머리 글씨가 거른 수를 보여준다",
        win._sep_label.cget("text") == "PC 박스 · 3마리 중 1마리", win._sep_label.cget("text"))
    chk("단추 글씨가 바뀐다", "불꽃" in win.btn_type.label.cget("text"), win.btn_type.label.cget("text"))
    chk("드롭다운에서 불꽃이 체크", next(r for r in win._type_rows() if r and r["text"] == "불꽃")["checked"])
    win._set_type("GRASS")
    settle_rows(root, win)
    chk("풀이면 박스는 이상해씨만", shown(win) == [1, 2, 3, 4], shown(win))
    win._set_type(None)
    settle_rows(root, win)
    chk("전체로 돌리면 여섯", shown(win) == [1, 2, 3, 4, 5, 6], shown(win))
    chk("거르고 풀어도 줄은 다시 만들지 않는다 (같은 줄)",
        all(win.rows[p] is r for p, r in keep.items()), sorted(win.rows))

    print("-- 이름 찾기 (박스에만 걸린다)")
    win.f_query.set("이브")
    settle_rows(root, win)
    chk("별명으로 찾는다 (파티 셋 + 이브)", shown(win) == [1, 2, 3, 5], shown(win))
    win.f_query.set("파이리")
    settle_rows(root, win)
    chk("파이리는 파티라 박스에서는 안 나오고 파티는 그대로", shown(win) == [1, 2, 3], shown(win))
    win.f_query.set("리자몽")
    settle_rows(root, win)
    chk("종 이름으로 박스에서 찾는다", shown(win) == [1, 2, 3, 6], shown(win))
    win.f_query.set("없는이름")
    settle_rows(root, win)
    chk("아무것도 안 맞아도 파티는 남는다", shown(win) == [1, 2, 3], shown(win))
    chk("박스 자리에 '없음' 한 줄", layout(win) == full_layout([1, 2, 3], []) + ["머리", "=", "없음"],
        layout(win))
    chk("숨긴 줄도 들고 있다", sorted(win.rows) == [1, 2, 3, 4, 5, 6], sorted(win.rows))
    win.f_query.set("")
    settle_rows(root, win)
    chk("지우면 전부, 순서와 머리까지 그대로",
        layout(win) == full_layout([1, 2, 3], [4, 5, 6]), layout(win))

    print("-- 타입 + 이름")
    win._set_type("FIRE")
    win.f_query.set("이브")
    settle_rows(root, win)
    chk("둘 다 걸면 박스는 비고 파티만", shown(win) == [1, 2, 3], shown(win))
    win._set_type(None)
    win.f_query.set("")
    settle_rows(root, win)

    print("-- 고르기")
    win.select(5)
    chk("고른 줄만 칠해진다", picked(win) == [5], picked(win))
    win.f_query.set("리자몽")            # 고른 이브이가 숨는다
    settle_rows(root, win)
    chk("고른 게 숨으면 보이는 첫 줄로 옮긴다", win.sel == 1 and picked(win) == [1], (win.sel, picked(win)))
    win.f_query.set("")
    settle_rows(root, win)
    chk("다시 보여도 두 줄이 골라져 보이지 않는다", picked(win) == [1], picked(win))

    print("-- 끌어서 옮기기는 보이는 줄만 찾는다")
    win.f_query.set("리자몽")            # 이상해씨(4)·이브이(5)는 숨는다
    settle_rows(root, win)

    class Ev(object):
        x_root = y_root = 0
    hidden_cell = win.rows[4].cells[1]
    win.win.winfo_containing = lambda x, y: hidden_cell
    chk("숨긴 줄 위라고 해도 못 찾는다", win._row_at(Ev) is None, win._row_at(Ev))
    shown_cell = win.rows[6].cells[1]
    win.win.winfo_containing = lambda x, y: shown_cell
    chk("보이는 줄은 찾는다", win._row_at(Ev) == 6, win._row_at(Ev))
    del win.win.winfo_containing
    win.f_query.set("")
    settle_rows(root, win)

    print("-- 상세 칸 도트 (작업 스레드에서 풀고 만들어 둔 것을 다시 쓴다)")
    gif = make_gif(os.path.join(os.environ["POKET_HOME"], "fake.gif"))
    real_ensure = ui_box.sprite_cache.ensure
    asked = []

    def fake_ensure(api, num, shiny=False):
        asked.append(num)
        return gif
    ui_box.sprite_cache.ensure = fake_ensure
    try:
        win.select(2)
        wait_for(root, lambda: len(win.photos) == 2)
        chk("도트가 붙는다 (두 장)", len(win.photos) == 2 and str(win.d_art.cget("image")),
            len(win.photos))
        win.select(3)
        wait_for(root, lambda: len(win.photos) == 2 and asked.count(25) == 1)
        n = len(asked)
        win.select(2)
        chk("방금 본 포켓몬은 다시 풀지 않고 곧바로 붙는다",
            len(asked) == n and len(win.photos) == 2 and win.d_art.cget("text") == "",
            (asked[n:], win.d_art.cget("text")))
        settle(root)
    finally:
        ui_box.sprite_cache.ensure = real_ensure

    print("-- 지닌 도구 칸")
    win.select(1)
    settle(root)
    chk("지닌 도구 이름이 뜬다", "먹다남은음식" in win.d_held.cget("text"),
        win.d_held.cget("text"))
    chk("벗기기 단추가 산다", win.btn_unhold.enabled is True)
    win.select(2)
    settle(root)
    chk("없는 애는 '없음'", win.d_held.cget("text").startswith("없음"), win.d_held.cget("text"))
    chk("벗기기 단추가 죽는다", win.btn_unhold.enabled is False)

    print("-- 도구 고르기 창")
    win.select(2)
    picker = ui_box.HeldPicker(win, win.current())
    wait_for(root, lambda: len(picker.inner.winfo_children()) > 0)
    settle(root)
    names = [w.winfo_children()[0].winfo_children()[-2].cget("text")
             for w in picker.inner.winfo_children() if w.winfo_children()]
    # 줄마다 [아이콘?, 이름, 개수] 순이라 뒤에서 두 번째가 이름이다
    chk("가진 것 중 지닐 수 있는 것만 (오랭열매)", any("오랭열매" in n for n in names), names)
    chk("몬스터볼·불꽃의돌은 안 나온다", not any(("몬스터볼" in n) or ("불꽃의돌" in n) for n in names), names)
    chk("안 가진 먹다남은음식도 안 나온다", not any("먹다남은음식" in n for n in names), names)
    picker.pick({"id": "ORANBERRY", "kr": "오랭열매"})
    wait_for(root, lambda: app.api.calls)
    settle(root)
    chk("고르면 hold 를 부른다", app.api.calls[:1] == [("hold", 2, "ORANBERRY")], app.api.calls)

    print("-- 벗기기")
    win.select(1)
    settle(root)
    win.do_unhold()
    wait_for(root, lambda: len(app.api.calls) >= 2)
    chk("벗기기가 unhold 를 부른다", ("unhold", 1) in app.api.calls, app.api.calls)
    settle_rows(root, win)

    eggs_in_box(root, win, app)

    try:
        win.close()
    except Exception:                                       # noqa: BLE001
        pass

    many(root, dex)
    hidden_rows_are_capped(root, dex)
    hyper_and_evs(root, dex)
    sort_by_bst(root, dex)

    try:
        root.destroy()
    except Exception:                                       # noqa: BLE001
        pass
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


def sort_by_bst(root, dex):
    """종족값 높은 순으로 보기 (1.10.1, 1.10.0 에서는 개체값 순) - '개체값' 머리글을 누른다."""
    print("-- 종족값 높은 순")
    party = [mon(dex, 7, 5001, on=True), mon(dex, 4, 5002, on=True)]
    box = [mon(dex, n, 6000 + n) for n in range(10, 45)]         # 박스 서른다섯 마리
    for i, m in enumerate(box):
        m["box"] = i // 30                                       # 박스 0 에 서른, 박스 1 에 다섯
        m["info"]["ivPercent"] = float((i * 37) % 101)           # 뒤죽박죽인 개체값
        m["info"]["ivTotal"] = int(m["info"]["ivPercent"] * 186 // 100)
    # 같은 종 둘 (종족값이 같다): 개체값 높은 쪽이 먼저, 그것도 같으면 레벨 높은 쪽
    twin = mon(dex, 36, 6999)                                    # 픽시 한 마리 더
    twin["box"] = 1
    twin["info"]["ivPercent"], box[26]["info"]["ivPercent"] = 90.0, 40.0     # box[26] = 36번
    box.append(twin)
    egg = box_filter.egg_row({"id": 9, "name": "포켓몬 알", "needSec": 100, "gotSec": 10})
    bst = lambda m: box_filter.bst_of(m, dex)                    # noqa: E731
    want = box_filter.sort_bst(box, dex)
    totals = [bst(m) for m in want]
    chk("종족값 합계는 여섯 능력치를 더한 것 (이상해꽃 525, 픽시 483)",
        box_filter.bst_of({"species": "VENUSAUR"}, dex) == 525 and bst(twin) == 483,
        (box_filter.bst_of({"species": "VENUSAUR"}, dex), bst(twin)))
    chk("높은 것부터 낮은 것으로", totals == sorted(totals, reverse=True) and totals[0] > totals[-1],
        totals[:6])
    at = [m["id"] for m in want]
    chk("종족값이 같으면(같은 종) 개체값 높은 쪽이 먼저", at.index(twin["id"]) < at.index(box[26]["id"]),
        (at.index(twin["id"]), at.index(box[26]["id"])))
    chk("개체값 순서와는 다르다 (개체값이 높아도 종족값이 낮으면 뒤)",
        at != [m["id"] for m in sorted(box, key=lambda m: -m["info"]["ivPercent"])])
    chk("받은 목록은 그대로 둔다", [m["id"] for m in box][:35] == [6000 + n for n in range(10, 45)])
    chk("알은 맨 뒤", box_filter.sort_bst([egg] + box[:3], dex)[-1] is egg and box_filter.bst_of(egg, dex) == -1)

    app = FakeApp(root, dex, party + box)
    win = ui_box.BoxWindow(root, app)
    wait_for(root, lambda: getattr(win, "mons", None))
    settle_rows(root, win)
    party_ids = [m["id"] for m in party]
    box_ids = [m["id"] for m in box]
    want_ids = [m["id"] for m in want]
    first_box = [m["id"] for m in box if m["box"] == 0]
    try:
        chk("처음에는 박스 순서 (첫 박스의 서른 마리)", shown(win) == party_ids + first_box,
            shown(win)[:5])
        chk("머리글에 누를 수 있다는 표시(▾)", win.head_iv.cget("text") == "개체값▾"
            and win.head_iv.cget("cursor") == "hand2", win.head_iv.cget("text"))
        top = want[0]
        chk("  그 칸에는 개체값이 적혀 있다", win.rows[first_box[0]].iv_cell.cget("text").endswith("%"),
            win.rows[first_box[0]].iv_cell.cget("text"))
        win.head_iv.event_generate("<Button-1>", x=3, y=3)       # 머리글을 진짜로 누른다
        settle_rows(root, win)
        chk("머리글을 누르면 박스를 넘어 종족값 높은 순", win.sort_bst
            and shown(win) == party_ids + want_ids[:30], shown(win)[:6])
        chk("  데리고 다니는 포켓몬은 그대로 맨 위", shown(win)[:2] == party_ids)
        chk("  머리글이 '종족값▼' 로 바뀐다", win.head_iv.cget("text") == "종족값▼"
            and str(win.head_iv.cget("fg")) == U.ACCENT, win.head_iv.cget("text"))
        chk("  그 칸에 종족값 합계가 적힌다 (데리고 다니는 줄도)",
            win.rows[top["id"]].iv_cell.cget("text") == str(bst(top))
            and win.rows[party_ids[0]].iv_cell.cget("text") == str(bst(party[0])),
            (win.rows[top["id"]].iv_cell.cget("text"), bst(top)))
        chk("  몇 위부터 몇 위까지인지 적힌다", win.lbl_page.cget("text") == "1~30위 / 36",
            win.lbl_page.cget("text"))
        chk("  이름 바꾸기는 꺼지고 ▶ 는 켜진다", win.btn_rename.enabled is False
            and win.btn_next.enabled is True and win.btn_prev.enabled is False)
        chk("  'PC 박스' 줄에도 적힌다", "종족값 높은 순" in win._sep_label.cget("text"),
            win._sep_label.cget("text"))
        root.update_idletasks()
        chk("  머리글의 글자가 칸에 다 들어간다", win.head_iv.winfo_reqwidth() <= win.head_iv.winfo_width(),
            (win.head_iv.winfo_reqwidth(), win.head_iv.winfo_width()))
        cell = win.rows[top["id"]].iv_cell
        chk("  줄의 숫자도 칸에 다 들어간다", cell.winfo_reqwidth() <= cell.winfo_width(),
            (cell.winfo_reqwidth(), cell.winfo_width()))
        win._page(1)
        settle_rows(root, win)
        chk("▶ 를 누르면 다음 순위들", shown(win) == party_ids + want_ids[30:]
            and win.lbl_page.cget("text") == "31~36위 / 36", (shown(win)[2:], win.lbl_page.cget("text")))
        chk("  새로 그려진 줄에도 종족값이 적힌다",
            win.rows[want_ids[-1]].iv_cell.cget("text") == str(bst(want[-1])),
            win.rows[want_ids[-1]].iv_cell.cget("text"))
        chk("  끝에서는 ▶ 가 꺼진다", win.btn_next.enabled is False and win.btn_prev.enabled is True)
        win._page(1)
        chk("  더 넘어가지 않는다", win.rank_page == 1)
        win.open_box_menu()
        chk("박스 고르기는 안 열리고 까닭을 알려 준다", "종족값" in win.status.cget("text"),
            win.status.cget("text"))
        win.f_query.set("이")
        settle_rows(root, win)
        _p, hit = box_filter.apply_box(party + box, dex, None, "이")
        chk("이름으로 걸러도 종족값 순서",
            shown(win) == party_ids + [m["id"] for m in box_filter.sort_bst(hit, dex)] and len(hit) > 1,
            shown(win)[2:8])
        win.f_query.set("")
        settle_rows(root, win)
        chk("  거름망을 지우면 첫 순위부터", win.rank_page == 0 or shown(win)[2:] == want_ids[30:],
            win.rank_page)
        win.toggle_sort()
        settle_rows(root, win)
        chk("다시 누르면 박스 순서로 돌아온다", not win.sort_bst and shown(win) == party_ids + first_box
            and win.head_iv.cget("text") == "개체값▾" and "위" not in win.lbl_page.cget("text"),
            (shown(win)[:4], win.lbl_page.cget("text")))
        chk("  그 칸은 다시 개체값", all(win.rows[i].iv_cell.cget("text").endswith("%") for i in shown(win)),
            [win.rows[i].iv_cell.cget("text") for i in shown(win)][:4])
        win.toggle_sort()
        settle_rows(root, win)
        win._reveal(box_ids[33])                                 # 바탕화면 도트를 두 번 눌러 열었다
        settle_rows(root, win)
        chk("어떤 포켓몬을 찾아 열면 그 포켓몬의 박스가 보인다 (정렬은 풀린다)", not win.sort_bst
            and win.box_no == 1 and box_ids[33] in shown(win) and win.sel == box_ids[33],
            (win.sort_bst, win.box_no, win.sel))
    finally:
        try:
            win.close()
        except Exception:                                   # noqa: BLE001
            pass


def eggs_in_box(root, win, app):
    """알도 포켓몬처럼 - 줄이 서고, 정보 칸, 데리고 다니기/박스 (1.4.1)."""
    from poketdesktop import eggs_ui
    print("-- 알")
    for m, slot in zip(app.api.mons[:3], (0, 2, 3)):
        m["slot"] = slot
    app.api.eggs = [
        {"id": 11, "kind": "legendary", "name": "전설의 포켓몬 알", "gotSec": 12 * 3600,
         "needSec": 48 * 3600, "leftSec": 36 * 3600, "hatched": False,
         "onDesktop": True, "slot": 1, "createdAt": "2026-09-15T16:40:28+00:00"},
        {"id": 12, "kind": "mythical", "name": "환상의 포켓몬 알", "gotSec": 0,
         "needSec": 36 * 3600, "leftSec": 36 * 3600, "hatched": False,
         "onDesktop": False, "slot": None, "createdAt": "2026-09-15T16:40:28+00:00"}]
    win.reload()
    wait_for(root, lambda: -11 in win._by_id)
    settle_rows(root, win)
    chk("알이 자리 순서대로 파티에 끼고, 박스 알은 박스 맨 앞",
        shown(win) == [1, -11, 2, 3, -12, 4, 5, 6], shown(win))
    chk("줄 사이 선과 머리까지 제자리",
        layout(win) == full_layout([1, -11, 2, 3], [-12, 4, 5, 6]), layout(win))
    txt = win.count.cget("text")
    chk("머릿수: 포켓몬 여섯 · 알 둘 · 데리고 다니는 셋 + 알 하나",
        "보유 6마리" in txt and "알 2개" in txt and "3마리 + 알 1개" in txt, txt)
    r = win.rows[-11]
    cells = [c.cget("text") for c in r.cells if isinstance(c, tk.Label)]
    chk("알 줄: 도감 칸 '알', 이름, 레벨 '-'",
        cells[:3] == ["알", "전설의 포켓몬 알", "-"], cells)
    chk("알 줄: 남은 시간 · 자란 정도 · 따라다님", cells[3:] == ["36시간", "25%", "따라다님"], cells)
    chk("알 줄 이름은 알 색", r.name_cell.cget("fg") == eggs_ui.EGG_COLOR["legendary"],
        r.name_cell.cget("fg"))
    chips = [c.cget("text") for c in r.types.winfo_children()]
    chk("타입 칸에 '전설'", chips == ["전설"], chips)
    chk("박스 알 줄은 '박스' · '환상'",
        win.rows[-12].cells[-1].cget("text") == "박스"
        and [c.cget("text") for c in win.rows[-12].types.winfo_children()] == ["환상"])

    win.select(-11)
    settle(root)
    chk("알 정보: 이름 · 자란 정도 · 무엇이 들었는지",
        win.d_name.cget("text") == "전설의 포켓몬 알" and win.d_lv.cget("text") == "25%"
        and "전설의 포켓몬" in win.d_sub.cget("text"),
        (win.d_name.cget("text"), win.d_lv.cget("text"), win.d_sub.cget("text")))
    chk("포켓몬 칸(특성~기술)은 빠지고 알 칸이 담긴다",
        win._d_mon.winfo_manager() == "" and win._d_egg.winfo_manager() == "pack")
    chk("켜 둔 시간", win.d_egg_time.cget("text") == "켜 둔 시간 12시간 / 48시간  (25%)",
        win.d_egg_time.cget("text"))
    chk("부화까지 남은 시간", win.d_egg_left.cget("text") == "부화까지 약 36시간",
        win.d_egg_left.cget("text"))
    chk("데리고 다니면 자란다고 말한다", "데리고 다니는 중" in win.d_egg_where.cget("text"),
        win.d_egg_where.cget("text"))
    chk("받은 날 (이 PC 날짜)", win.d_egg_day.cget("text").startswith("받은 날 2026-09-1"),
        win.d_egg_day.cget("text"))
    chk("알 그림이 붙는다", bool(str(win.d_art.cget("image"))), win.d_art.cget("text"))
    chk("알 상태 한 줄", win.d_egg_mood.cget("text") == eggs_ui.mood(app.api.eggs[0]))
    chk("박스로 보내기는 되고, 별명 · 놓아주기는 안 된다",
        win.btn_party.enabled and not win.btn_nick.enabled and not win.btn_release.enabled
        and win.btn_party.label.cget("text") == "박스로 보내기")
    win.do_release()                     # 알이면 아무 일도 없어야 한다 (확인 창도 안 뜬다)
    win.do_nickname()

    win.select(-12)
    settle(root)
    chk("박스 알은 자라지 않는다고 말한다 (빨간 글씨)",
        "자라지 않습니다" in win.d_egg_where.cget("text")
        and win.d_egg_where.cget("fg") == ui_box.U.DANGER, win.d_egg_where.cget("text"))
    chk("박스 알 단추는 '데리고 다니기'", win.btn_party.label.cget("text") == "데리고 다니기")

    win.select(2)
    settle(root)
    chk("포켓몬을 고르면 포켓몬 칸이 돌아온다",
        win._d_mon.winfo_manager() == "pack" and win._d_egg.winfo_manager() == "")
    chk("별명 · 놓아주기 단추도 돌아온다", win.btn_nick.enabled and win.btn_release.enabled)
    chk("포켓몬 이름 색으로", win.d_name.cget("fg") == ui_box.U.ACCENT_TEXT)

    win._set_type("FIRE")
    settle_rows(root, win)
    chk("타입을 고르면 박스 알은 숨고 파티 알은 그대로",
        shown(win) == [1, -11, 2, 3, 6], shown(win))
    win._set_type(None)
    win.f_query.set("알")
    settle_rows(root, win)
    chk("이름 '알' 로 박스 알을 찾는다", shown(win) == [1, -11, 2, 3, -12], shown(win))
    win.f_query.set("")
    settle_rows(root, win)

    n = len(app.api.calls)
    win.select(-11)
    win.toggle_party()
    wait_for(root, lambda: len(app.api.calls) > n)
    settle(root)
    chk("알을 박스로 보내면 음수 id 로 부른다", app.api.calls[n:n + 1] == [("desktop", -11, False)],
        app.api.calls[n:])
    settle_rows(root, win)

    n = len(app.api.calls)
    win._apply_drop(-12, 2)              # 박스 알 -> 꼬부기 자리
    wait_for(root, lambda: len(app.api.calls) >= n + 3)
    chk("맞바꾸기: 꼬부기를 내리고 알을 올리고 순서 (알은 음수)",
        app.api.calls[n:n + 3] == [("desktop", 2, False), ("desktop", -12, True),
                                   ("order", [1, -11, -12, 3])], app.api.calls[n:])
    settle_rows(root, win)
    app.api.eggs = []
    for m in app.api.mons[:3]:
        m.pop("slot", None)
    win.reload()
    wait_for(root, lambda: -11 not in win._by_id)
    settle_rows(root, win)
    chk("알이 없어지면 (부화) 줄도 없어지고 머릿수가 원래대로",
        -11 not in win.rows and "알" not in win.count.cget("text"), win.count.cget("text"))


def many(root, dex):
    """박스가 차 있을 때 - 줄을 나눠 만드는 중에 거르고, 고르고, 다시 받는다."""
    print("-- 많을 때: 나눠 만드는 중에 거르기")
    # 파티 셋(번호 순이 아닌 순서) + 박스 여든일곱
    party = [mon(dex, 7, 2007, on=True), mon(dex, 4, 2004, on=True),
             mon(dex, 1, 2001, on=True)]
    box = [mon(dex, n, 3000 + n) for n in range(2, 91) if n not in (4, 7)]
    for i, m in enumerate(box):          # 서버가 30마리씩 나눠 담아 준다
        m["box"] = i // 30
    big = party + box
    app = FakeApp(root, dex, big)
    app.api.gate.clear()                # 창이 부르는 목록은 붙잡아 둔다
    win = ui_box.BoxWindow(root, app)
    try:
        return _many(root, dex, app, win, party, box, big)
    finally:
        app.api.gate.set()
        try:
            win.close()
        except Exception:                                   # noqa: BLE001
            pass


def _many(root, dex, app, win, party, box, big):
    party_ids = [m["id"] for m in party]
    box_ids = [m["id"] for m in box]
    last = box_ids[-1]

    # app.pet_open 처럼 목록이 오기 전에 고른다
    win.select(2004)
    ov = win._wait
    chk("불러오는 동안 표시가 떠 있다", ov is not None and not ov.done, ov)
    win._loaded(list(big), None)        # 목록이 막 왔다 (이벤트 루프는 안 돈다)
    chk("첫 묶음만 먼저 만든다", win._rows_job.pending and len(win.rows) < len(big),
        len(win.rows))
    chk("줄을 만드는 동안에는 표시가 아직 있다", not ov.done)
    root.update_idletasks()
    chk("첫 화면을 그린 뒤(idle)에 걷힌다", ov.done)
    chk("받기 전에 고른 것이 그대로 골라져 있다", win.sel == 2004 and picked(win) == [2004],
        (win.sel, picked(win)))
    chk("첫 화면은 파티부터 순서대로",
        shown(win) == (party_ids + box_ids)[:len(shown(win))], shown(win)[:6])

    q = "피"
    _p, want_box = box_filter.apply_box(big, dex, None, q)
    want_ids = [m["id"] for m in want_box]
    win.f_query.set(q)                  # 아직 다 안 만들었는데 거른다
    chk("거른 결과가 곧바로 순서대로", shown(win) == party_ids + want_ids,
        (shown(win), party_ids + want_ids))
    settle_rows(root, win)
    chk("다 만든 뒤에도 거른 결과 그대로", shown(win) == party_ids + want_ids, shown(win))
    # **안 보일 줄은 만들지 않는다.** 예전에는 거름망에 걸러진 것까지 전부
    # 미리 만들어 둬서(거르기를 풀 때 빨리 담으려고) 수백 마리면 느려졌다.
    chk("안 보이는 줄까지 만들지는 않는다", len(win.rows) < len(big), len(win.rows))
    chk("줄이 겹치지 않는다 (만든 줄·선 한 쌍씩 + 머리·굵은 선·없음)",
        len(win.inner.winfo_children()) == 2 * len(win.rows) + 3,
        len(win.inner.winfo_children()))

    win.f_query.set("")
    chk("지우면 첫 묶음부터 곧바로 담긴다", len(shown(win)) > len(party_ids) + len(want_ids),
        len(shown(win)))
    settle_rows(root, win)
    chk("지우면 첫 박스가 순서대로, 'PC 박스' 머리까지",
        layout(win) == full_layout(party_ids, page_ids(box_ids)), layout(win)[:12])
    chk("머리 글씨", win._sep_label.cget("text") == "PC 박스 · %d마리" % len(box),
        win._sep_label.cget("text"))

    # ---- 박스 넘기기·이름·옮기기 ----
    pages = (len(box) + ui_box.BOX_SIZE - 1) // ui_box.BOX_SIZE
    chk("박스 이름표에 이름과 마릿수", win.lbl_page.cget("text") == "박스 1  30/30 ▾",
        win.lbl_page.cget("text"))
    win._page(1)
    settle_rows(root, win)
    chk("다음 박스로 넘어간다",
        layout(win) == full_layout(party_ids, page_ids(box_ids, 1)), layout(win)[:12])
    chk("이름표도 따라온다", win.lbl_page.cget("text").startswith("박스 2"),
        win.lbl_page.cget("text"))
    win._page(-1)
    settle_rows(root, win)
    chk("돌아온다", layout(win) == full_layout(party_ids, page_ids(box_ids)),
        layout(win)[:12])

    # 이름표를 누르면 **박스 고르기** 다 (1.9.2). 전에는 이름 바꾸기가 떴다 -
    # 옆에 그 단추가 따로 있는데도. 끝 박스로 가려면 화살표를 서른 번 눌렀다.
    asked = []
    keep_ask, keep_menu = ui_box.ask_text, win._menu
    ui_box.ask_text = lambda *a, **k: asked.append(a) or None
    opened = []
    win._menu = lambda w, rows, below=False: opened.append((w, rows, below))
    try:
        win.lbl_page.event_generate("<Button-1>", x=4, y=4)
        root.update()
    finally:
        ui_box.ask_text, win._menu = keep_ask, keep_menu
    chk("이름표를 눌러도 이름 바꾸기 창이 안 뜬다", not asked, asked)
    chk("대신 박스 목록이 이름표 밑에 열린다",
        len(opened) == 1 and opened[0][0] is win.lbl_page and opened[0][2] is True,
        [(o[0], o[2]) for o in opened])
    rows = win._box_rows()
    chk("목록에는 박스가 다 있다", len(rows) == win.box_count(), len(rows))
    chk("줄마다 이름과 마릿수", rows[0]["text"] == "박스 1  (30/30)", rows[0]["text"])
    chk("지금 보는 박스에 표시", [i for i, r in enumerate(rows) if r["checked"]] == [0],
        [i for i, r in enumerate(rows) if r["checked"]])
    end = win.box_count() - 1
    rows[end]["command"]()
    settle_rows(root, win)
    chk("고르면 그 박스로 바로 간다", win.box_no == end, win.box_no)
    chk("이름표도 그 박스다",
        win.lbl_page.cget("text").startswith("박스 %d " % (end + 1)),
        win.lbl_page.cget("text"))
    chk("끝 박스에서는 ▶ 가 꺼지고 ◀ 는 켜진다",
        not win.btn_next.enabled and win.btn_prev.enabled,
        (win.btn_next.enabled, win.btn_prev.enabled))
    win._box_rows()[0]["command"]()
    settle_rows(root, win)
    chk("첫 박스로 돌아온다", win.box_no == 0
        and layout(win) == full_layout(party_ids, page_ids(box_ids)), win.box_no)
    # 서른두 줄짜리 목록이다. 화면이 낮으면 한 단으로는 아래 줄이 화면 밖으로
    # 나가 누를 수가 없다 - 단을 나눠 화면 안에 넣는다 (글자는 안 줄인다).
    # 직접 그리는 메뉴는 맥에서만 쓴다 (윈도우는 스스로 굴러가는 tk.Menu).
    if not PLAT.NATIVE_MENU:
        from poketdesktop import ui_common as UC
        real_screen = UC.screen_at
        try:
            for label, scr, want in (("낮은 화면(1024x640)", (0, 0, 1024, 640), 2),
                                     ("넉넉한 화면(1920x1080)", (0, 0, 1920, 1080), 1)):
                UC.screen_at = lambda r, x, y, s=scr: s
                menu = UC.PopupMenu(root, win._box_rows(), 300, 100, width=220)
                root.update()
                chk("%s: 박스 목록이 %d단" % (label, want), menu.cols == want, menu.cols)
                chk("  화면 안에 다 들어온다",
                    menu.win.winfo_rooty() + menu.win.winfo_height() <= scr[3]
                    and menu.win.winfo_rootx() + menu.win.winfo_width() <= scr[2],
                    (menu.win.winfo_rooty(), menu.win.winfo_height(), menu.win.winfo_width()))
                menu.close()
        finally:
            UC.screen_at = real_screen
        root.update()

    asked = []
    ui_box.ask_text = lambda *a, **k: asked.append(a) or None
    try:
        win.btn_rename.command()
    finally:
        ui_box.ask_text = keep_ask
    chk("이름 바꾸기는 그 단추가 한다", len(asked) == 1, asked)

    # 이름 바꾸기
    app.api.set_box_name(0, "불꽃방")
    win.boxes["names"] = dict(app.api.box_names)
    win._paint_page(0)
    chk("박스 이름을 바꾸면 이름표에 나온다",
        win.lbl_page.cget("text").startswith("불꽃방"), win.lbl_page.cget("text"))
    app.api.set_box_name(0, "")
    win.boxes["names"] = dict(app.api.box_names)
    win._paint_page(0)
    chk("비우면 기본 이름", win.lbl_page.cget("text").startswith("박스 1"),
        win.lbl_page.cget("text"))

    # **다른 박스로 옮기기** - 이게 없으면 박스가 있으나 마나다
    movee = box_ids[0]
    win.select(movee)
    settle_rows(root, win)
    win._do_move(movee, 2)
    # 보내기도 다시 불러오기도 비동기다. 창이 그 박스를 보여줄 때까지 기다린다.
    wait_for(root, lambda: ("box", movee, 2) in app.api.calls and win.box_no == 2)
    settle_rows(root, win)
    chk("옮기면 서버에 보낸다", ("box", movee, 2) in app.api.calls, app.api.calls[-2:])
    chk("옮긴 박스를 보여준다", win.box_no == 2, win.box_no)
    chk("옮긴 포켓몬이 그 박스에 있다", movee in shown(win), shown(win)[:6])
    win.box_no = 0
    win._show(win.sel)
    settle_rows(root, win)
    chk("떠난 박스에는 없다", movee not in shown(win), shown(win)[:6])
    win._do_move(movee, 0)
    wait_for(root, lambda: ("box", movee, 0) in app.api.calls and win.box_no == 0)
    settle_rows(root, win)

    # 찾기: 거르기를 걸면 박스를 넘어 다 뒤진다
    win.f_query.set("피")
    settle_rows(root, win)
    chk("찾을 때는 박스를 넘어 다 뒤진다",
        win._searching() and "찾는 중" in win.lbl_page.cget("text"),
        win.lbl_page.cget("text"))
    win.open_box_menu()
    chk("찾는 중에는 박스 목록 대신 안내가 뜬다",
        "박스를 고를 수 없습니다" in win.status.cget("text"), win.status.cget("text"))
    win.f_query.set("")
    settle_rows(root, win)

    # 마지막 박스의 포켓몬을 고르면 그 박스로 옮겨 간다 (바탕화면 도트로 열 때)
    far = box_ids[-1]
    win.select(far)
    settle_rows(root, win)
    chk("다른 박스의 포켓몬을 고르면 그 박스로 간다",
        far in win.rows and picked(win) == [far], (win.box_no, picked(win)))
    chk("  그 박스가 담겨 있다",
        layout(win) == full_layout(party_ids, page_ids(box_ids, pages - 1)),
        layout(win)[:12])
    win.box_no = 0
    win._show(win.sel)
    settle_rows(root, win)

    win.f_query.set(q)
    root.update()
    win.f_query.set("")                 # 담는 도중에 또 바꾼다
    win._set_type("FIRE")
    win._set_type(None)
    settle_rows(root, win)
    chk("담는 도중에 여러 번 바꿔도 첫 박스가 순서대로",
        layout(win) == full_layout(party_ids, page_ids(box_ids)), layout(win)[:12])

    print("-- 많을 때: 아직 없는 줄 고르기")
    other = ui_box.BoxWindow(root, app)
    try:
        ov = other._wait
        other._loaded(None, RuntimeError("서버가 답하지 않습니다"))
        chk("못 받으면 표시는 곧바로 걷히고 까닭을 적는다",
            ov is not None and ov.done and "답하지" in other.status.cget("text"),
            (ov is not None and ov.done, other.status.cget("text")))
        other._loaded(list(big), None)
        chk("끝쪽 줄은 아직 없다", last not in other.rows and other._rows_job.pending,
            len(other.rows))
        other.select(last)
        chk("아직 없는 줄을 고르면 먼저 다 만든다",
            last in other.rows and not other._rows_job.pending, len(other.rows))
        chk("고른 줄만 칠해진다", picked(other) == [last], picked(other))
        chk("상세도 그 포켓몬", other.d_name.cget("text") == box[-1]["info"]["name"],
            other.d_name.cget("text"))
        # 마지막 포켓몬을 골랐으니 그 포켓몬이 있는 박스가 담겨 있다
        chk("고른 포켓몬이 있는 박스가 담겨 있다",
            layout(other) == full_layout(
                party_ids, page_ids(box_ids, (len(box_ids) - 1) // ui_box.BOX_SIZE)),
            layout(other)[:12])
    finally:
        other.close()

    print("-- 많을 때: 다시 받으면 바뀐 줄만 새로 만든다")
    win.select(box_ids[10])
    settle(root)
    before = dict(win.rows)
    gone = box_ids[5]
    renamed = box_ids[20]
    new = [m for m in big if m["id"] != gone]
    new = [dict(m) for m in new]
    for m in new:
        if m["id"] == renamed:
            m["nickname"] = "새별명"
            m["info"] = dict(m["info"], name="새별명")
    # 끌어서 파티 순서를 바꿨다 + 새로 잡은 포켓몬이 박스 끝에
    new = [new[2], new[0], new[1]] + new[3:] + [mon(dex, 133, 9999)]
    app.api.mons = new
    app.api.gate.set()                  # 붙잡아 둔 첫 목록 부탁이 이제 새 목록을 받는다
    wait_for(root, lambda: 9999 in win._by_id)
    settle_rows(root, win)
    new_party = [m["id"] for m in new[:3]]
    new_box = [m["id"] for m in new[3:]]
    chk("파티는 새 순서대로", shown(win)[:3] == new_party, shown(win)[:3])
    # **박스는 번호로 센다.** 앞에서 30마리로 자르면, 놓아주거나 새로 잡아
    # 목록이 바뀐 뒤에는 실제 박스와 어긋난다.
    first_box = [m["id"] for m in new[3:] if int(m.get("box") or 0) == 0]
    chk("첫 박스가 순서대로, 머리까지",
        layout(win) == full_layout(new_party, first_box), layout(win)[:12])
    # (숨겨 둔 줄은 두 박스치까지만 들고 있는다 - ROW_KEEP. 남아 있는 줄을 본다.)
    same = [p for p in box_ids if p in win.rows and p in before and p not in (gone, renamed)]
    chk("그대로인 줄은 같은 줄을 쓴다 (%d줄)" % len(same),
        len(same) >= ui_box.BOX_SIZE and all(win.rows[p] is before[p] for p in same), len(same))
    chk("바뀐 줄은 새로 만든다 (새 별명)", win.rows[renamed] is not before[renamed]
        and "새별명" in win.rows[renamed].name_cell.cget("text"))
    chk("놓아준 줄은 없어진다", gone not in win.rows)
    chk("고르던 것이 그대로 골라져 있다", win.sel == box_ids[10] and picked(win) == [box_ids[10]],
        (win.sel, picked(win)))
    # 새로 잡은 것은 박스 맨 끝 = 마지막 박스에 있다. 그 포켓몬을 고르면
    # 창이 알아서 그 박스로 옮겨 간다.
    win.select(9999)
    settle_rows(root, win)
    chk("새로 잡은 줄이 마지막 박스 끝에 생긴다", shown(win)[-1] == 9999, shown(win)[-3:])
    chk("줄이 남거나 겹치지 않는다",
        len(win.inner.winfo_children()) == 2 * len(win.rows) + 3,
        len(win.inner.winfo_children()))


if __name__ == "__main__":
    sys.exit(main())
