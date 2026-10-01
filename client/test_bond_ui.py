# -*- coding: utf-8 -*-
"""포켓몬 관리 창의 '메가진화' 칸 검사 (시즌 3 유대 미션).

    python client/test_bond_ui.py
    python client/run_as_windows.py client/test_bond_ui.py

**창을 진짜로 띄운다.** 서버 없이 - 가짜 api 가 server/app/mega.card 와
같은 모양의 카드를 준다.

## 무엇을 못 박나

  1. 메가가 없는 종(피카츄)에는 칸이 없다. 리자몽에는 있다.
  2. 칸은 진화 칸 아래, 능력치 위. 몇 번을 골라도 순서가 안 바뀐다.
  3. 키스톤이 없으면 몇 곳 남았는지. 유대가 덜 찼으면 막대와 안내.
  4. 유대가 차고 키스톤이 있으면 '미션 시작' - 누르면 미션 셋이 뜬다.
  5. 다 채우면 '메가스톤 받기'. X/Y 는 고르게 하고, 고른 것으로 받는다.
  6. 목록을 빨리 넘겨도 늦게 온 옛 응답이 칸을 덮지 않는다.
  7. 레쿠쟈는 화룡점정 한 줄. 눌린 위젯이 없다.
"""
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import smoke_box_filter as SB                               # noqa: E402  (POKET_HOME 도 여기서)
import json                                                 # noqa: E402
import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0
STONES = {"CHARIZARD": [("CHARIZARDITEX", "리자몽나이트X"), ("CHARIZARDITEY", "리자몽나이트Y")],
          "GENGAR": [("GENGARITE", "팬텀나이트")],
          "FLOETTE": [("FLOETTITE", "플라엣테나이트")]}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class BondApi(SB.FakeApi):
    """server/app/mega.card + 키스톤 과 같은 모양."""

    def __init__(self, mons):
        SB.FakeApi.__init__(self, mons)
        self.keystone = {"has": True, "gyms": 9, "need": 8}
        self.happy = {}
        self.bonds = {}                 # pid -> {gym,kos,wild,done,stone}
        self.owned = set()
        self.slow = {}                  # pid -> Event (그 응답을 붙잡는다)

    def _species(self, pid):
        return next(m["species"] for m in self.mons if m["id"] == pid)

    def _card(self, pid):
        sp = self._species(pid)
        stones = STONES.get(sp, [])
        out = {"pokemon": pid, "species": sp, "happiness": self.happy.get(pid, 70),
               "need": 255, "stones": [{"id": s, "kr": kr} for s, kr in stones],
               "missing": [s for s, _kr in stones if s not in self.owned],
               "started": pid in self.bonds}
        b = self.bonds.get(pid)
        if b:
            out.update({"missions": [
                {"key": "gym", "text": "불꽃 또는 비행 타입 관장 1곳에서 이기기",
                 "value": b["gym"], "target": 1},
                {"key": "kos", "text": "직접 30번 쓰러뜨리기", "value": b["kos"], "target": 30},
                {"key": "wild", "text": "데리고 다니는 동안 야생 10마리 잡기",
                 "value": b["wild"], "target": 10}],
                "done": b["done"], "stone": b["stone"],
                "claimable": bool(b["done"] and not b["stone"])})
        return out

    def bond(self, pid):
        self.calls.append(("bond", pid))
        ev = self.slow.get(pid)
        if ev is not None:
            ev.wait(10)
        out = self._card(pid)
        out["keystone"] = dict(self.keystone)
        return out

    def bond_start(self, pid):
        self.calls.append(("start", pid))
        self.bonds[pid] = {"gym": 0, "kos": 0, "wild": 0, "done": False, "stone": None}
        return self._card(pid)

    def bond_claim(self, pid, stone):
        self.calls.append(("claim", pid, stone))
        self.bonds[pid]["stone"] = stone
        self.owned.add(stone)
        return self._card(pid)


def settle(root, sec=0.3):
    import time
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def wait(root, cond, sec=5):
    import time
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


def panel_text(win):
    return " ".join(texts(win.bond.frame))


def order(win):
    """상세 칸에서 진화·메가·능력치 칸의 순서."""
    names = {str(win.d_evo): "진화", str(win.bond.frame): "메가", str(win._d_stats): "능력치"}
    return [names[str(s)] for s in win._d_mon.pack_slaves() if str(s) in names]


def main():
    with open(os.path.join(HERE, "..", "server", "data", "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-300:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))

    # 리자몽(데리고 다님)·팬텀·피카츄·레쿠쟈·파이리(메가 없음, 진화함)·플라엣테(진화도 메가도)
    mons = [SB.mon(dex, 6, 1, on=True), SB.mon(dex, 94, 2, on=True), SB.mon(dex, 25, 3, on=True),
            SB.mon(dex, 384, 4), SB.mon(dex, 4, 5), SB.mon(dex, 670, 6)]
    app = SB.FakeApp(root, dex, mons)
    api = app.api = BondApi(mons)
    win = ui_box.BoxWindow(root, app)
    wait(root, lambda: getattr(win, "mons", None))
    SB.settle_rows(root, win)

    print("=== 메가가 없는 종 ===")
    win.select(3)
    settle(root)
    chk("피카츄에는 메가진화 칸이 없다", not win.bond.frame.winfo_ismapped()
        and not win.bond.frame.winfo_manager())
    win.select(5)
    settle(root)
    chk("파이리(메가는 리자몽만)에도 없다", not win.bond.frame.winfo_manager())

    print("\n=== 키스톤이 없을 때 ===")
    api.keystone = {"has": False, "gyms": 5, "need": 8}
    win.select(1)
    chk("리자몽에는 칸이 뜨고 카드를 받아 온다",
        wait(root, lambda: win.bond.card is not None) and win.bond.frame.winfo_manager(),
        api.calls[-2:])
    settle(root)
    t = panel_text(win)
    chk("키스톤: 관장 5 / 8곳", "관장 5 / 8곳" in t, t)
    chk("스톤 둘의 이름", "리자몽나이트X" in t and "리자몽나이트Y" in t, t)
    chk("키스톤 안내", "관장 8곳을 이기면" in t, t)
    chk("시작 단추는 없다", win.bond.btn is None)
    chk("진화 칸 아래, 능력치 위", order(win) == ["메가", "능력치"] or order(win)[-2:] == ["메가", "능력치"],
        order(win))

    print("\n=== 유대가 덜 찼을 때 ===")
    api.keystone = {"has": True, "gyms": 9, "need": 8}
    api.happy[1] = 200
    win.select(2)
    wait(root, lambda: win.bond.card and win.bond.card["species"] == "GENGAR")
    win.select(1)
    wait(root, lambda: win.bond.card and win.bond.card["species"] == "CHARIZARD")
    settle(root)
    t = panel_text(win)
    chk("유대 200 / 255 와 빛나는 돌 안내", "200 / 255" in t and "빛나는 돌" in t, t)
    chk("  시작 단추는 없다", win.bond.btn is None)

    print("\n=== 유대가 가득 -> 시작 ===")
    api.happy[1] = 255
    win.select(2)
    wait(root, lambda: win.bond.card and win.bond.card["species"] == "GENGAR")
    win.select(1)
    wait(root, lambda: win.bond.card and win.bond.card["species"] == "CHARIZARD")
    settle(root)
    chk("'미션 시작' 단추", win.bond.btn is not None
        and win.bond.btn.label.cget("text") == "미션 시작",
        win.bond.btn and win.bond.btn.label.cget("text"))
    bad = squeezed(win.bond.frame)
    chk("  눌린 위젯이 없다", not bad, bad[:3])
    win.bond.btn.command()
    chk("누르면 서버에 시작을 보낸다", wait(root, lambda: ("start", 1) in api.calls), api.calls[-3:])
    settle(root)
    t = panel_text(win)
    chk("미션 셋이 뜬다", "① 불꽃 또는 비행" in t and "② 직접 30번" in t and "③ 데리고" in t, t)
    chk("  진행 0 / 30", "0 / 30" in t, t)
    chk("  시작하면 바탕화면을 다시 맞춘다", app.synced >= 1, app.synced)
    chk("  단추는 없다 (아직 못 받는다)", win.bond.btn is None)
    bad = squeezed(win.bond.frame)
    chk("  미션 칸에 눌린 위젯이 없다", not bad, bad[:3])

    print("\n=== 다 채움 -> X/Y 골라 받기 ===")
    api.bonds[1].update({"gym": 1, "kos": 30, "wild": 10, "done": True})
    win.select(2)
    wait(root, lambda: win.bond.card and win.bond.card["species"] == "GENGAR")
    win.select(1)
    wait(root, lambda: win.bond.card and win.bond.card.get("claimable"))
    settle(root)
    chk("'메가스톤 받기' 단추", win.bond.btn is not None
        and win.bond.btn.label.cget("text") == "메가스톤 받기")
    menus = []
    win._menu = lambda btn, rows: menus.append(rows)
    win.bond.btn.command()
    chk("둘 중 고르는 목록이 뜬다", menus and [r["text"] for r in menus[0]]
        == ["리자몽나이트X", "리자몽나이트Y"], menus)
    menus[0][1]["command"]()
    chk("고른 Y 로 받는다", wait(root, lambda: ("claim", 1, "CHARIZARDITEY") in api.calls),
        api.calls[-2:])
    settle(root)
    t = panel_text(win)
    chk("받았다고 적는다", "리자몽나이트Y 을(를) 받았습니다" in t, t)
    chk("  스톤 줄에 (받음)", "리자몽나이트Y (받음)" in t, t)
    chk("  창 아래에도 알린다", "받았습니다" in win.status.cget("text"),
        win.status.cget("text"))

    print("\n=== 빨리 넘길 때 ===")
    gate = threading.Event()
    api.slow[2] = gate                     # 팬텀 응답을 붙잡아 둔다
    win.select(2)
    settle(root, 0.1)
    win.select(1)                          # 그사이 리자몽으로
    wait(root, lambda: win.bond.card and win.bond.card["species"] == "CHARIZARD")
    gate.set()                             # 늦게 팬텀 응답이 온다
    settle(root, 0.5)
    chk("늦게 온 옛 응답이 칸을 덮지 않는다", win.bond.card["species"] == "CHARIZARD"
        and "팬텀나이트" not in panel_text(win), win.bond.card["species"])
    api.slow.pop(2)

    print("\n=== 레쿠쟈 ===")
    n = len(api.calls)
    win.select(4)
    settle(root)
    t = panel_text(win)
    chk("화룡점정 한 줄", "화룡점정" in t, t)
    chk("  서버에 묻지 않는다", not any(c[0] == "bond" for c in api.calls[n:]), api.calls[n:])

    print("\n=== 순서가 안 바뀐다 ===")
    for pid in (1, 5, 6, 1, 6, 2, 6):
        win.select(pid)
        settle(root, 0.1)
    wait(root, lambda: win.bond.card is not None)
    o = order(win)
    chk("진화도 메가도 있는 종(플라엣테): 진화 -> 메가 -> 능력치",
        o == ["진화", "메가", "능력치"], o)
    bad = squeezed(win.bond.frame)
    chk("  눌린 위젯이 없다", not bad, bad[:3])

    try:
        win.close()
    except Exception:                                       # noqa: BLE001
        pass
    settle(root, 0.3)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
