# -*- coding: utf-8 -*-
"""마스터볼은 한 번 더 묻는다 (2.5.8, 게시판 #909 '마스터볼이 어느새 사라졌다') - 화면 없이.

    python client/test_master_ball.py

  1. 볼 메뉴의 마스터볼 줄: 확인하면 던지고, 취소하면 아무것도 안 한다 · 다른 볼은 묻지 않는다
  2. 메뉴를 여는 세 곳(야생 · 바탕화면 배틀 · 아르케 배틀)이 다 popup 을 거친다 - popup 이 묻는다
  3. 볼을 안 고르고 던질 때(마지막에 쓴 볼): 마스터볼이었으면 몬스터볼로 (두 개 이상 가졌을 때 말없이 또 나가던 길)
"""
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-master-"))

from poketdesktop import ball_menu as BM                    # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


OPTS = [{"id": "POKEBALL", "kr": "몬스터볼", "count": 5, "mult": 1.0, "cost": 200},
        {"id": "ULTRABALL", "kr": "하이퍼볼", "count": 2, "mult": 2.0, "cost": 800, "best": True},
        {"id": "MASTERBALL", "kr": "마스터볼", "count": 2, "mult": 255, "cost": 0}]


def main():
    print("=== 마스터볼 확인 (#909)")
    thrown, asked = [], []
    for answer in (True, False):
        pick = BM.guard("root", thrown.append, ask=lambda root, a=answer: (asked.append(root), a)[1])
        rows = BM.rows(OPTS, pick)
        master = next(r for r in rows if r and "마스터볼" in r["text"])
        master["command"]()
    chk("1. 마스터볼 줄: 확인하면 던진다 · 취소하면 안 던진다", thrown == ["MASTERBALL"] and asked == ["root", "root"], (thrown, asked))
    thrown[:], asked[:] = [], []
    pick = BM.guard("root", thrown.append, ask=lambda root: (asked.append(root), False)[1])
    for r in BM.rows(OPTS, pick):
        if r and r.get("command") and "마스터볼" not in r["text"]:
            r["command"]()
    chk("   다른 볼(추천 · 몬스터볼 · 하이퍼볼)은 묻지 않고 던진다", not asked and thrown == ["ULTRABALL", "POKEBALL", "ULTRABALL"],
        (thrown, asked))
    chk("   묻는 글", "마스터볼을 던질까요?" in BM.MASTER_ASK and "되돌릴 수 없" in BM.MASTER_ASK)

    import inspect
    src = inspect.getsource(BM.popup)
    chk("2. popup 이 고른 것을 guard 로 감싼다 (메뉴 두 갈래 - 윈도우 tk.Menu · 맥 PopupMenu - 둘 다 그 뒤에 만든다)",
        "on_pick = guard(root, on_pick)" in src and src.index("guard(root, on_pick)") < src.index("rows(options")
        and src.index("guard(root, on_pick)") < src.index("build(root"))
    here = os.path.join(HERE, "poketdesktop")
    users = [f for f in ("wild_ui.py", "desktop_battle.py", "arche_battle.py")
             if "ball_menu.popup(" in open(os.path.join(here, f), encoding="utf-8").read()]
    chk("   야생 · 바탕화면 배틀 · 아르케 배틀이 다 popup 으로 연다", len(users) == 3, users)

    from poketdesktop import wild_ui, desktop_battle
    app = types.SimpleNamespace(settings={"lastBall": "MASTERBALL"})
    cls = next(getattr(wild_ui, n) for n in dir(wild_ui) if hasattr(getattr(wild_ui, n), "last_ball"))
    w = cls.__new__(cls)
    w.app, w.ball_options = app, OPTS
    chk("3. 야생: 마지막에 쓴 볼이 마스터볼(2개 남음)이어도 고르지 않고 던지면 몬스터볼", w.last_ball() == "POKEBALL", w.last_ball())
    app.settings["lastBall"] = "ULTRABALL"
    chk("   다른 볼은 예전처럼 마지막에 쓴 볼", w.last_ball() == "ULTRABALL", w.last_ball())
    dcls = next(getattr(desktop_battle, n) for n in dir(desktop_battle) if hasattr(getattr(desktop_battle, n), "_pick_ball"))
    b = dcls.__new__(dcls)
    b.app, b.ball_opts = types.SimpleNamespace(settings={"lastBall": "MASTERBALL"}), OPTS
    chk("   바탕화면 배틀도 같다", b._pick_ball() == "POKEBALL", b._pick_ball())

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
