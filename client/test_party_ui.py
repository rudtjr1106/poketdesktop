# -*- coding: utf-8 -*-
"""파티 프리셋 화면 검사 (1.10.3) — 포켓몬 관리 창의 맨 윗줄.

    python client/test_party_ui.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 - 가짜 api 가 서버의 party.py 와 같은 규칙으로 답한다
(지금 파티가 곧 지금 번호의 파티, 갈아탈 때 적어 둔다, 안 쓴 번호로 가면 들고 간다).

  1. 목록 위에 [파티 1] ... [파티 5] 가 있고, 지금 번호에 금색이 칠해진다.
  2. 누르면 데리고 다니는 파티가 그 번호의 것으로 바뀌고, 바탕화면도 다시 맞춘다 (request_sync).
  3. 돌아오면 원래 파티가 순서대로 나온다. 저장 단추는 없다.
  4. 이름을 붙이면 칸의 글자가 바뀐다. 네 자를 넘으면 보내지 않는다.
  5. 다섯 칸이 한 줄에 다 들어간다 (가장 긴 이름을 다 붙여도). 눌린 위젯이 없다.
  6. 프리셋이 없는 옛 서버에 붙으면 그 줄이 안 보인다 - 나머지는 예전 그대로다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import smoke_box_filter as SB                                # noqa: E402  (POKET_HOME 을 임시 폴더로 잡는다)

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

OK = FAIL = 0
COUNT, NAME_MAX = 5, 4


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class PartyApi(SB.FakeApi):
    """프리셋을 아는 서버 흉내. 규칙은 server/app/party.py 와 같다."""

    def __init__(self, mons):
        SB.FakeApi.__init__(self, mons)
        self.active = 1
        self.stored = {}              # {번호: [id]} - 갈아탈 때 적어 둔 것
        self.names = {}
        self.fail = None

    def live(self):
        return [m["id"] for m in self.mons if m.get("onDesktop")]

    def party(self):
        self.calls.append(("party",))
        out = []
        for no in range(1, COUNT + 1):
            ids = self.live() if no == self.active else self.stored.get(no)
            out.append({"no": no, "name": self.names.get(no) or "파티 %d" % no, "named": no in self.names,
                        "active": no == self.active, "saved": ids is not None,
                        "size": len(ids or []), "ids": list(ids or [])})
        return {"active": self.active, "count": COUNT, "nameMax": NAME_MAX, "max": 6, "presets": out}

    def party_use(self, no):
        self.calls.append(("use", no))
        if self.fail:
            raise RuntimeError(self.fail)
        live = self.live()
        self.stored[self.active] = live
        fresh = no not in self.stored
        want = live if fresh else self.stored[no]
        by = dict((m["id"], m) for m in self.mons)
        for m in self.mons:
            m["onDesktop"] = m["id"] in want
        self.mons.sort(key=lambda m: (not m["onDesktop"], want.index(m["id"]) if m["id"] in want else m["id"]))
        self.active = no
        name = self.names.get(no) or "파티 %d" % no
        return dict(self.party(), ok=True, changed=not fresh, message="파티를 바꿨습니다: [%s]" % name)

    def party_rename(self, no, name):
        self.calls.append(("name", no, name))
        if name:
            self.names[no] = name
        else:
            self.names.pop(no, None)
        return dict(self.party(), ok=True, message="파티 이름을 바꿨습니다: [%s]" % (name or "파티 %d" % no))


def party_ids(win):
    """창이 지금 '데리고 다니는' 것으로 그린 포켓몬 (화면 순서대로)."""
    on = set(m["id"] for m in win.mons if m.get("onDesktop"))
    return [pid for pid in SB.shown(win) if pid in on]


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    with open(os.path.join(HERE, "..", "server", "data", "pokedex.json"), encoding="utf-8") as f:
        import json
        dex = P.Pokedex(json.load(f))
    nums = [25, 6, 94, 133, 143, 445, 448, 1, 4, 7, 150, 151]
    mons = [SB.mon(dex, n, i + 1, on=i < 6) for i, n in enumerate(nums)]
    first = [1, 2, 3, 4, 5, 6]
    app = SB.FakeApp(root, dex, mons)
    app.api = api = PartyApi(mons)
    win = ui_box.BoxWindow(root, app)
    top = win.win.winfo_toplevel()
    top.deiconify()
    SB.settle_rows(root, win)
    SB.settle(root)

    print("=== 프리셋 줄 ===")
    cells = win.party_seg.cells
    chk("목록 위에 다섯 칸이 보인다", win.party_bar.winfo_ismapped() == 1 and sorted(cells) == [1, 2, 3, 4, 5]
        and [cells[i].cget("text") for i in range(1, 6)] == ["파티 %d" % i for i in range(1, 6)],
        [cells[i].cget("text") for i in range(1, 6)])
    chk("  PC 박스 거르기 줄보다 위에 있다", win.party_bar.winfo_rooty() < win.filter_bar.winfo_rooty())
    chk("지금 번호(1)에 금색", win.party_seg.current == 1 and cells[1].cget("bg") == U.ACCENT
        and cells[2].cget("bg") != U.ACCENT)
    chk("저장 단추는 없다 ('이름 바꾸기' 만 있다)", win.btn_party_name.label.cget("text") == "이름 바꾸기"
        and not any("저장" in str(c.cget("text")) for c in win.party_bar.winfo_children() if "text" in c.keys()))
    chk("데리고 다니는 여섯이 그대로 보인다", party_ids(win) == first, party_ids(win))
    # 프리셋 줄만 본다. 그 아래 'PC 박스' 거르기 줄의 이름 칸은 이 줄이 생기기 전부터 맥 글꼴에서
    # 몇 px 눌려 있다 (프리셋이 없는 옛 서버 창에서도 똑같이 걸린다) - 이번에 건드린 것이 아니다.
    bad = squeezed(win.party_bar)
    chk("프리셋 줄에 눌린 위젯 없음", not bad, bad[:3])

    print("\n=== 처음 쓰는 번호로 ===")
    cells[2].event_generate("<Button-1>", x=3, y=3)
    SB.wait_for(root, lambda: ("use", 2) in api.calls and win.party_active() == 2)
    SB.settle_rows(root, win)
    chk("누르면 서버에 그 번호로 갈아탄다고 보낸다", ("use", 2) in api.calls and win.party_active() == 2
        and win.party_seg.current == 2 and cells[2].cget("bg") == U.ACCENT)
    chk("  지금 파티를 그대로 들고 간다", party_ids(win) == first, party_ids(win))
    chk("  무엇으로 바꿨는지 아래에 남는다", "파티 2" in win.status.cget("text"), win.status.cget("text"))
    chk("  바탕화면도 다시 맞춘다", app.synced >= 1, app.synced)

    print("\n=== 2번을 다른 포켓몬으로 ===")
    for m in api.mons:                                           # 박스에 있던 여섯으로 통째로 바꾼다
        m["onDesktop"] = m["id"] > 6
    api.mons.sort(key=lambda m: (not m["onDesktop"], m["id"]))
    win.reload()
    SB.wait_for(root, lambda: party_ids(win) == [7, 8, 9, 10, 11, 12])
    SB.settle_rows(root, win)
    second = [7, 8, 9, 10, 11, 12]
    chk("(준비) 2번 = 박스에 있던 여섯", party_ids(win) == second)

    print("\n=== 오가기 ===")
    cells[1].event_generate("<Button-1>", x=3, y=3)
    SB.wait_for(root, lambda: win.party_active() == 1 and party_ids(win) == first)
    SB.settle_rows(root, win)
    chk("1번으로 돌아오면 원래 여섯이 순서대로 나온다", party_ids(win) == first and cells[1].cget("bg") == U.ACCENT,
        party_ids(win))
    chk("  2번의 여섯은 박스로 갔다 (목록의 박스 쪽에 보인다)", all(pid in SB.shown(win) for pid in second)
        and not any(m["onDesktop"] for m in win.mons if m["id"] in second))
    cells[2].event_generate("<Button-1>", x=3, y=3)
    SB.wait_for(root, lambda: win.party_active() == 2 and party_ids(win) == second)
    SB.settle_rows(root, win)
    chk("2번으로 가면 그 여섯이 나온다", party_ids(win) == second, party_ids(win))
    n = len([c for c in api.calls if c[0] == "use"])
    cells[2].event_generate("<Button-1>", x=3, y=3)
    SB.settle(root)
    chk("지금 번호를 다시 눌러도 서버를 부르지 않는다", len([c for c in api.calls if c[0] == "use"]) == n)

    print("\n=== 실패 ===")
    api.fail = "데리고 다니는 알이 1개 있어서 [파티 1]의 6마리를 다 꺼낼 수 없습니다."
    cells[1].event_generate("<Button-1>", x=3, y=3)
    SB.wait_for(root, lambda: "알" in win.status.cget("text"))
    chk("못 갈아타면 까닭이 보이고 번호는 그대로다", "꺼낼 수 없습니다" in win.status.cget("text")
        and win.party_active() == 2 and win.party_seg.current == 2 and party_ids(win) == second, win.status.cget("text"))
    api.fail = None
    cells[3].event_generate("<Button-1>", x=3, y=3)
    SB.wait_for(root, lambda: win.party_active() == 3)
    SB.settle_rows(root, win)
    chk("  그 뒤에도 다시 누를 수 있다", win.party_active() == 3)

    print("\n=== 이름 ===")
    keep = ui_box.ask_text
    asked = []
    ui_box.ask_text = lambda parent, title, message, hint="", initial="": (asked.append((title, message, hint, initial)), "레이드")[1]
    win.rename_party()
    SB.wait_for(root, lambda: ("name", 3, "레이드") in api.calls and cells[3].cget("text") == "레이드")
    chk("이름을 붙이면 지금 번호의 칸이 그 이름이 된다", cells[3].cget("text") == "레이드" and cells[1].cget("text") == "파티 1"
        and asked and "3번" in asked[0][1] and "4자" in asked[0][2], (cells[3].cget("text"), asked[:1]))
    ui_box.ask_text = lambda *a, **k: "바탕화면용"
    n = len(api.calls)
    win.rename_party()
    SB.settle(root)
    chk("네 자를 넘으면 보내지 않고 알려 준다", len(api.calls) == n and "4자" in win.status.cget("text"), win.status.cget("text"))
    ui_box.ask_text = lambda *a, **k: None
    win.rename_party()
    SB.settle(root)
    chk("취소하면 아무 일도 없다", len(api.calls) == n and cells[3].cget("text") == "레이드")
    asked2 = []
    ui_box.ask_text = lambda parent, title, message, hint="", initial="": (asked2.append(initial), "")[1]
    win.rename_party()
    SB.wait_for(root, lambda: cells[3].cget("text") == "파티 3")
    chk("비우면 기본 이름으로 돌아간다 (묻는 창에는 지금 이름이 적혀 있다)", cells[3].cget("text") == "파티 3"
        and asked2 == ["레이드"], asked2)
    ui_box.ask_text = keep

    print("\n=== 가장 긴 이름을 다 붙여도 ===")
    for no in range(1, 6):
        api.names[no] = "바탕화면"
    win.reload()
    SB.wait_for(root, lambda: cells[5].cget("text") == "바탕화면")
    SB.settle_rows(root, win)
    SB.settle(root)
    seg, bar = win.party_seg.frame, win.party_bar
    btn = win.btn_party_name.holder
    chk("다섯 칸과 '이름 바꾸기' 가 한 줄에 다 들어간다", seg.winfo_width() >= seg.winfo_reqwidth()
        and btn.winfo_rootx() + btn.winfo_width() <= bar.winfo_rootx() + bar.winfo_width()
        and seg.winfo_rootx() + seg.winfo_width() <= btn.winfo_rootx(),
        (seg.winfo_width(), seg.winfo_reqwidth(), btn.winfo_rootx() + btn.winfo_width(), bar.winfo_rootx() + bar.winfo_width()))
    top.geometry("950x620")                                       # 창을 가장 작게
    SB.settle(root, 20)
    chk("  창을 가장 작게 줄여도", btn.winfo_rootx() + btn.winfo_width() <= bar.winfo_rootx() + bar.winfo_width(),
        (btn.winfo_rootx() + btn.winfo_width(), bar.winfo_rootx() + bar.winfo_width()))
    bad = squeezed(win.party_bar)
    chk("  프리셋 줄에 눌린 위젯 없음", not bad, bad[:3])
    win.close()

    print("\n=== 프리셋이 없는 옛 서버 ===")
    old_mons = [SB.mon(dex, n, i + 1, on=i < 3) for i, n in enumerate(nums[:5])]
    app2 = SB.FakeApp(root, dex, old_mons)                        # FakeApi 에는 party() 가 없다
    win2 = ui_box.BoxWindow(root, app2)
    win2.win.winfo_toplevel().deiconify()
    SB.settle_rows(root, win2)
    SB.settle(root)
    chk("프리셋 줄이 안 보인다", win2.party_bar.winfo_ismapped() == 0 and win2.party is None)
    chk("  나머지는 예전 그대로 (파티 셋, 박스 둘)", party_ids(win2) == [1, 2, 3] and len(SB.shown(win2)) == 5)
    win2.close()

    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
