# -*- coding: utf-8 -*-
"""포켓몬 관리 창: 동작 하나 뒤에 **바뀐 것만** 다시 받는다 (2.5.0, POST /api/pokemon/pick).

    python client/test_box_pick_ui.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 (smoke_box_filter 의 가짜 api 에 서버와 같은 규칙의 pick 을 붙인다 -
물은 번호 가운데 아직 있는 것 + 지금 파티 전부 + 알 전부 + 박스 칸 수).

예전에는 옮기기 · 데리고 다니기 · 별명 하나에도 상자 전체(800마리면 1MB 넘게)를 다시 받았다.

못 박는 것:

  1. 데리고 다니기 · 박스로 보내기 · 파티 안 자리 바꾸기 · 별명 · 지닌 도구 빼기 · 한 마리 놓아주기 · 박스 옮기기 ·
     여러 마리 옮기기 · 여러 마리 놓아주기 · 파티 바꾸기가 **전체를 다시 받지 않는다** (pick 만 한 번).
  2. 묻는 번호는 건드린 것 + 창이 알던 파티다 (알은 음수라 안 묻는다).
  3. 고친 목록이 **전체를 다시 받은 것과 똑같다** - 파티에서 하나가 빠져 다른 것의 자리 번호가 당겨져도,
     파티 바꾸기로 박스에 있던 것이 올라와도. 매 동작 뒤에 전체를 따로 받아 견준다.
  4. 박스 칸 수(머리의 n/30)가 새로 온 것으로 바뀐다. 알림 글이 다시 받은 뒤에도 남는다.
  5. 서버가 pick 을 모르면(옛 서버 · 오류) 예전처럼 전체를 다시 받는다.
"""
import json
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-boxpick-")

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


class Api(SB.FakeApi):
    """서버와 같은 규칙으로 상태를 바꾸고, pick 을 준다. 전체 받기 · pick 횟수를 센다."""

    def __init__(self, mons, dex):
        SB.FakeApi.__init__(self, mons)
        self.dex = dex
        self.full = 0
        self.picks = []
        self.pick_ok = True
        self.presets = {1: [], 2: []}
        self.active = 1

    # ---- 받기
    def pokemon_boxes(self):
        """진짜 서버처럼 **사본**을 준다 - 같은 dict 를 나눠 가지면 창이 받지도 않은 변경이 보여 검사가 속는다."""
        self.full += 1
        mons, eggs, boxes = SB.FakeApi.pokemon_boxes(self)
        return copy(mons), copy(eggs), boxes

    def snapshot(self):
        """전체를 받으면 창이 가질 목록 (세지 않는다)."""
        mons, eggs, _ = SB.FakeApi.pokemon_boxes(self)
        return F.merge_eggs(sorted(copy(mons), key=F.server_order), copy(eggs))

    def pokemon_pick(self, ids):
        if not self.pick_ok:
            raise SB._Refused("없는 주소", 404)
        ids = [int(i) for i in ids]
        self.picks.append(sorted(ids))
        out = [m for m in self.mons if m.get("onDesktop") or m["id"] in ids]
        return {"pokemon": copy(out), "eggs": copy(self.eggs), "boxes": SB.FakeApi.pokemon_boxes(self)[2]}

    def party(self):
        return {"presets": [{"no": 1, "name": "파티 1"}, {"no": 2, "name": "파티 2"}], "active": self.active}

    # ---- 바꾸기 (서버처럼: 파티에서 빼면 뒤의 자리 번호가 당겨진다)
    def _by(self, pid):
        return next(m for m in self.mons if m["id"] == pid)

    def _compact(self):
        party = sorted((m for m in self.mons if m.get("onDesktop")), key=lambda m: m.get("slot") or 0)
        for i, m in enumerate(party):
            m["slot"] = i
        for m in self.mons:
            if not m.get("onDesktop"):
                m["slot"] = None

    def set_desktop(self, pid, on):
        SB.FakeApi.set_desktop(self, pid, on)
        m = self._by(pid)
        if on and not m.get("onDesktop"):
            m["onDesktop"] = True
            m["slot"] = 99
        elif not on:
            m["onDesktop"] = False
        self._compact()
        return {"ok": True}

    def set_order(self, ids):
        """서버처럼 음수는 알이다 (포켓몬과 알이 여섯 자리를 나눠 쓴다)."""
        SB.FakeApi.set_order(self, ids)
        for i, pid in enumerate(ids):
            if pid < 0:
                next(e for e in self.eggs if e["id"] == -pid)["slot"] = i
            else:
                self._by(pid)["slot"] = i
        return {"ok": True}

    def set_box(self, pid, no):
        SB.FakeApi.set_box(self, pid, no)
        self._compact()
        return {"ok": True}

    def set_nickname(self, pid, name):
        m = self._by(pid)
        m["nickname"] = name or None
        m["info"]["name"] = name or m["info"]["species"]
        return {"ok": True}

    def unhold(self, pid):
        SB.FakeApi.unhold(self, pid)
        m = self._by(pid)
        m.pop("held", None)
        m.pop("heldKr", None)
        return {"ok": True}

    def release(self, pid):
        self.mons.remove(self._by(pid))
        self._compact()
        return {"ok": True}

    def party_use(self, no):
        self.presets[self.active] = [m["id"] for m in self.mons if m.get("onDesktop")]
        for m in self.mons:
            m["onDesktop"] = m["id"] in self.presets[no]
            m["slot"] = self.presets[no].index(m["id"]) if m["onDesktop"] else None
        self.active = no
        return dict(self.party(), message="파티 %d 로 바꿨습니다." % no)


def copy(x):
    return json.loads(json.dumps(x))


def shape(mons):
    """견줄 모습: 차례대로 (번호, 파티, 자리, 박스, 이름, 지닌 도구)."""
    return [(m["id"], bool(m.get("onDesktop")), m.get("slot") if m.get("onDesktop") else None,
             int(m.get("box") or 0) if not m.get("onDesktop") else None,
             (m.get("info") or {}).get("name"), m.get("held")) for m in mons]


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

    party = [SB.mon(dex, 7, 5001, on=True), SB.mon(dex, 4, 5002, on=True), SB.mon(dex, 25, 5003, on=True,
                                                                               held="LEFTOVERS")]
    for i, m in enumerate(party):
        m["slot"] = i
    box = []
    for i, n in enumerate([150, 129, 6, 143, 3, 94, 130, 59, 65] + list(range(10, 50))):
        m = SB.mon(dex, n, 6000 + i)
        m["box"] = i // 30
        m["slot"] = None
        box.append(m)
    app = SB.FakeApp(root, dex, party + box)
    api = app.api = Api(party + box, dex)
    api.eggs = [{"id": 9, "name": "포켓몬 알", "needSec": 100, "gotSec": 10, "onDesktop": True, "slot": 3}]
    win = ui_box.BoxWindow(root, app)
    win.win.geometry("990x668+20+20")
    SB.wait_for(root, lambda: getattr(win, "mons", None))
    SB.settle_rows(root, win)
    chk("처음에는 전체를 한 번 받는다", api.full == 1, api.full)

    def act(label, fn, touched, party_before):
        f0, p0 = api.full, len(api.picks)
        fn()
        SB.wait_for(root, lambda: len(api.picks) > p0 or api.full > f0)
        SB.settle_rows(root, win)
        want = sorted(set(touched) | set(party_before))
        chk("%s: 전체를 다시 받지 않고 pick 한 번" % label, api.full == f0 and len(api.picks) == p0 + 1,
            (api.full - f0, len(api.picks) - p0))
        chk("  묻는 것 = 건드린 것 + 창이 알던 파티 (알은 안 묻는다)",
            len(api.picks) > p0 and api.picks[-1] == [i for i in want if i > 0], (api.picks[-1:], want))
        chk("  고친 목록이 전체를 다시 받은 것과 똑같다", shape(win.mons) == shape(api.snapshot()),
            (shape(win.mons)[:6], shape(api.snapshot())[:6]))

    def party_ids():
        return [m["id"] for m in win.mons if m.get("onDesktop")]

    print("=== 데리고 다니기 · 박스로 보내기 ===")
    win.select(6000)
    SB.settle(root)
    act("박스 것을 데리고 다니기", win.toggle_party, [6000], party_ids())
    chk("  포켓몬 중 파티 끝에 붙었다", [i for i in party_ids() if i > 0][-1] == 6000, party_ids())
    chk("  알림 글이 남는다", "데리고 다닙니다" in win.status.cget("text"), win.status.cget("text"))
    win.select(5001)
    SB.settle(root)
    act("파티 첫 칸을 박스로 (뒤의 자리 번호가 당겨진다)", win.toggle_party, [5001], party_ids())
    chk("  파티 차례: 5002, 5003, 6000 (자리가 당겨졌다), 알", party_ids() == [5002, 5003, 6000, -9], party_ids())
    used0 = int((win.boxes.get("used") or {}).get("0") or 0)
    chk("  박스 0 칸 수가 새로 온 것 (%d)" % used0, used0 == sum(1 for m in api.mons if not m.get("onDesktop")
                                                              and int(m.get("box") or 0) == 0), used0)

    print("\n=== 파티 안 자리 바꾸기 ===")
    act("자리 맞바꾸기", lambda: win._apply_drop(5002, 6000),
        [5002, 6000], party_ids())
    chk("  6000 이 맨 앞으로", party_ids()[0] == 6000, party_ids())

    print("\n=== 한 마리 고치기 ===")
    orig_ask = ui_box.ask_text
    ui_box.ask_text = lambda *a, **k: "번개쥐"
    try:
        win.select(5003)
        SB.settle(root)
        act("별명", win.do_nickname, [5003], party_ids())
        chk("  줄의 이름이 바뀌었다", next(m for m in win.mons if m["id"] == 5003)["info"]["name"] == "번개쥐")
    finally:
        ui_box.ask_text = orig_ask
    act("지닌 도구 빼기", win.do_unhold, [5003], party_ids())
    chk("  도구가 빠졌다", not next(m for m in win.mons if m["id"] == 5003).get("held"))

    print("\n=== 박스 옮기기 ===")
    act("한 마리 다른 박스로", lambda: win._do_move(6001, 1), [6001], party_ids())
    chk("  박스 1 로 갔다", next(m for m in win.mons if m["id"] == 6001)["box"] == 1)
    act("여러 마리 한 박스로", lambda: win._do_move_many([6002, 6003, 6004], 1), [6002, 6003, 6004], party_ids())

    print("\n=== 놓아주기 ===")
    orig_cr = ui_box.confirm_release
    ui_box.confirm_release = lambda *a, **k: True
    try:
        win.select(6005)
        SB.settle(root)
        act("한 마리 놓아주기", win.do_release, [6005], party_ids())
        chk("  목록에서 빠졌다", all(m["id"] != 6005 for m in win.mons))
    finally:
        ui_box.confirm_release = orig_cr
    act("여러 마리 놓아주기", lambda: win._do_release_many([6006, 6007]), [6006, 6007], party_ids())
    chk("  둘 다 빠졌다", not [m for m in win.mons if m["id"] in (6006, 6007)])

    print("\n=== 파티 바꾸기 ===")
    api.presets[2] = [6010, 6011]
    before = party_ids()
    act("파티 2 로 (박스에 있던 것이 올라온다 - 서버가 붙여 준다)", lambda: win.use_party(2), [], before)
    chk("  파티가 6010 · 6011 (+ 알)", [i for i in party_ids() if i > 0] == [6010, 6011], party_ids())

    print("\n=== 옛 서버 ===")
    api.pick_ok = False
    win.select(6012)
    SB.settle(root)
    f0 = api.full
    win.toggle_party()
    SB.wait_for(root, lambda: api.full > f0)
    SB.settle_rows(root, win)
    chk("pick 을 모르면 전체를 다시 받는다", api.full == f0 + 1, api.full - f0)
    chk("  목록은 그대로 맞다", shape(win.mons) == shape(api.snapshot()))

    chk("도는 동안 오류 없음", not errors, errors[:3])
    win.close()
    root.destroy()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
