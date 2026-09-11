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
from poketdesktop import ui_box                             # noqa: E402

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
        self.mons = mons
        self.calls = []
        self.gate = threading.Event()     # pokemon() 을 잠깐 붙잡는다
        self.gate.set()

    def pokemon(self):
        self.gate.wait(10)
        return self.mons

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

    try:
        win.close()
    except Exception:                                       # noqa: BLE001
        pass

    many(root, dex)

    try:
        root.destroy()
    except Exception:                                       # noqa: BLE001
        pass
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


def many(root, dex):
    """박스가 차 있을 때 - 줄을 나눠 만드는 중에 거르고, 고르고, 다시 받는다."""
    print("-- 많을 때: 나눠 만드는 중에 거르기")
    # 파티 셋(번호 순이 아닌 순서) + 박스 여든일곱
    party = [mon(dex, 7, 2007, on=True), mon(dex, 4, 2004, on=True),
             mon(dex, 1, 2001, on=True)]
    box = [mon(dex, n, 3000 + n) for n in range(2, 91) if n not in (4, 7)]
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
    chk("숨긴 줄까지 전부 만들어 둔다", len(win.rows) == len(big), len(win.rows))
    chk("줄이 겹치지 않는다 (줄·선 한 쌍씩 + 머리·굵은 선·없음)",
        len(win.inner.winfo_children()) == 2 * len(big) + 3,
        len(win.inner.winfo_children()))

    win.f_query.set("")
    chk("지우면 첫 묶음부터 곧바로 담긴다", len(shown(win)) > len(party_ids) + len(want_ids),
        len(shown(win)))
    settle_rows(root, win)
    chk("지우면 전체가 순서대로, 'PC 박스' 머리까지",
        layout(win) == full_layout(party_ids, box_ids), layout(win)[:12])
    chk("머리 글씨", win._sep_label.cget("text") == "PC 박스 · %d마리" % len(box),
        win._sep_label.cget("text"))

    win.f_query.set(q)
    root.update()
    win.f_query.set("")                 # 담는 도중에 또 바꾼다
    win._set_type("FIRE")
    win._set_type(None)
    settle_rows(root, win)
    chk("담는 도중에 여러 번 바꿔도 전체가 순서대로",
        layout(win) == full_layout(party_ids, box_ids), layout(win)[:12])

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
        chk("다 담겨 있다", layout(other) == full_layout(party_ids, box_ids),
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
    chk("전체가 순서대로, 머리까지", layout(win) == full_layout(new_party, new_box),
        layout(win)[:12])
    chk("그대로인 줄은 같은 줄을 쓴다",
        all(win.rows[p] is before[p] for p in box_ids if p not in (gone, renamed)))
    chk("바뀐 줄은 새로 만든다 (새 별명)", win.rows[renamed] is not before[renamed]
        and "새별명" in win.rows[renamed].name_cell.cget("text"))
    chk("놓아준 줄은 없어진다", gone not in win.rows)
    chk("새로 잡은 줄이 끝에 생긴다", shown(win)[-1] == 9999, shown(win)[-3:])
    chk("줄이 남거나 겹치지 않는다", len(win.inner.winfo_children()) == 2 * len(new) + 3,
        len(win.inner.winfo_children()))
    chk("고르던 것이 그대로 골라져 있다", win.sel == box_ids[10] and picked(win) == [box_ids[10]],
        (win.sel, picked(win)))


if __name__ == "__main__":
    sys.exit(main())
