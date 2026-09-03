# -*- coding: utf-8 -*-
"""맥 메뉴 막대 아이콘 검사.

    python client/test_tray_mac.py

화면이 필요하다(메뉴 막대에 아이콘을 잠깐 올렸다 내린다).

여기서 지키려는 것 둘.

1. **상태 아이콘에 NSMenu 를 붙이면 안 된다.** 붙이면 메뉴를 여는 순간
   중첩 런루프가 돌고, 그 안에서 Tk 의 after 타이머가 발화하면서 파이썬이
   통째로 죽는다. 이 게임은 도트를 움직이려고 after 를 쉬지 않고 돈다.
2. **'종료' 가 절대 사라지면 안 된다.** 맥에서는 메뉴 막대가 이 프로그램의
   유일한 입구라, 메뉴가 반쯤 만들어진 채로 남으면 프로그램을 끌 방법이
   없어진다.
"""
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-test-tray"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def section(t):
    print("-- %s" % t)


class FakeApp(object):
    """트레이가 물어보는 것만 있는 가짜 앱."""

    def __init__(self, root, logged_in=True):
        self.root = root
        self.api = object() if logged_in else None
        self.username = "시험이" if logged_in else None
        self.overlay = None
        self.balls = 3
        self.money = 100
        self.pvp_unseen = 2
        self.settings = {"targetHeight": 48, "areaW": 520, "areaH": 360,
                         "showNames": True, "autostart": False}
        self.called = []

    def quit(self):
        self.called.append("quit")

    def __getattr__(self, name):
        if name.startswith(("open_", "set_", "toggle_", "pvp_", "recall_",
                            "send_")) or name in ("logout", "delete_account"):
            return lambda *a, **kw: self.called.append(name)
        raise AttributeError(name)


def rows(win):
    """메뉴 창 안의 글자들을 전부 모은다."""
    out = []

    def walk(w):
        for c in w.winfo_children():
            t = ""
            try:
                t = c.cget("text")
            except Exception:                               # noqa: BLE001
                t = ""
            if t:
                out.append(str(t))
            walk(c)
    walk(win)
    return out


def find_row(win, text):
    """그 글자를 가진 위젯."""
    hit = []

    def walk(w):
        for c in w.winfo_children():
            try:
                if text in str(c.cget("text")):
                    hit.append(c)
            except Exception:                               # noqa: BLE001
                pass
            walk(c)
    walk(win)
    return hit[0] if hit else None


def main():
    if sys.platform != "darwin":
        print("맥에서만 하는 검사입니다.")
        return 0

    from poketdesktop import platform_os as PLAT
    from poketdesktop import platform_mac as M
    if not M.available():
        print("pyobjc 가 없습니다.")
        return 1

    try:
        import Quartz
        if (Quartz.CGSessionCopyCurrentDictionary() or {}).get(
                "CGSSessionScreenIsLocked"):
            print("화면이 잠겨 있습니다. 메뉴 막대에 아이콘이 실제로")
            print("올라갔는지를 보는 검사라, 잠금을 풀고 다시 돌려 주세요.")
            return 0
    except Exception:                                       # noqa: BLE001
        pass

    import tkinter as tk
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()

    from poketdesktop import tray_mac
    from poketdesktop import ui_common as U
    U.init_fonts(root)

    app = FakeApp(root)
    t = tray_mac.Tray(app)

    section("아이콘이 메뉴 막대에 올라간다")
    t.start()
    chk("상태 항목이 생겼다", t.item is not None)
    chk("메뉴 막대에 실제로 올라가 있다", bool(t.item.isVisible()))
    chk("아이콘 그림이 붙었다", t.item.button().image() is not None)
    reps = t.item.button().image().representations()
    chk("보통 화면과 레티나용 그림을 둘 다 넣는다", len(reps) >= 2, len(reps))
    chk("설명에 사용자 이름이 들어간다", "시험이" in str(t.item.button().toolTip() or ""))

    section("NSMenu 를 붙이지 않는다 (붙이면 여는 순간 앱이 죽는다)")
    chk("상태 항목에 메뉴가 없다", t.item.menu() is None, t.item.menu())
    chk("단추에 동작이 걸려 있다", str(t.item.button().action()) == "clicked:",
        t.item.button().action())

    section("아이콘을 누르면 tkinter 로 그린 메뉴가 열린다")
    # objc 쪽에서 하는 일을 그대로 흉내낸다 (tkinter 는 안 부른다)
    t._target.clicked_(None)
    chk("눌린 것이 적힌다", t.pending_toggle is True)
    root.update()                      # _pump 가 Tk 쪽에서 꺼내 간다
    for _ in range(20):
        if t.popup is not None:
            break
        root.update()
        root.after(30)
    chk("메뉴 창이 떴다", t.popup is not None and t.popup.alive())
    if t.popup is None or not t.popup.alive():
        return 1
    chk("바깥을 눌러 닫을 창도 같이 뜬다", t.popup.catcher is not None)
    chk("메뉴가 항상 위에 있다", bool(t.popup.win.attributes("-topmost")))

    section("메뉴 내용")
    ts = rows(t.popup.win)
    chk("항목이 여럿 있다", len(ts) > 8, len(ts))
    chk("'종료' 가 있다", any(x.strip() == "종료" for x in ts), ts)
    chk("'열기...' 가 있다", any("열기" in x for x in ts), ts)
    chk("받은 대전 개수가 붙는다", any("받은 대전" in x and "2" in x for x in ts), ts)
    chk("'바로 가기' 는 뺐다", not any("바로 가기" in x for x in ts), ts)
    chk("하위 메뉴 제목이 펼쳐진다", any("포켓몬 크기" in x for x in ts), ts)
    chk("체크 표시가 붙는다", any(x.startswith("✓") for x in ts),
        [x for x in ts if x.startswith("✓")])

    section("누르면 실행되고 메뉴가 닫힌다")
    quit_row = find_row(t.popup.win, "종료")
    chk("'종료' 줄을 찾았다", quit_row is not None)
    if quit_row is not None:
        quit_row.event_generate("<Button-1>")
        root.update()
        chk("앱의 quit 이 불린다", "quit" in app.called, app.called)
        chk("메뉴가 닫힌다", t.popup is None or not t.popup.alive())

    section("갱신해도 '종료' 가 사라지지 않는다")
    t.toggle()
    root.update()
    before = rows(t.popup.win)
    for _ in range(3):
        t.refresh()
        root.update()
    after = rows(t.popup.win)
    chk("갱신 뒤에도 항목 수가 그대로다", len(after) == len(before),
        "%d -> %d" % (len(before), len(after)))
    chk("갱신 뒤에도 '종료' 가 있다", any(x.strip() == "종료" for x in after))

    section("아무도 안 눌렀는데 메뉴가 저절로 열리면 안 된다")
    # 메뉴는 스스로도 닫힌다 - 항목을 누르거나, 바깥을 누르거나, 다른
    # 메뉴가 열릴 때. 그때 죽은 참조를 '열려 있다' 로 읽으면 다음
    # refresh() 가 메뉴를 다시 연다. 설정을 바꿀 때마다 그랬다.
    t.close()
    root.update()
    chk("닫힌 상태에서 시작", not t.is_open())
    for _ in range(3):
        t.refresh()
        root.update()
    chk("갱신해도 안 열린다", not t.is_open())
    chk("갱신해도 창이 안 생긴다", t.popup is None, t.popup)

    # 항목을 눌러서 닫힌 뒤 (메뉴가 스스로 닫는 길)
    t.open()
    root.update()
    row = find_row(t.popup.win, "종료")
    if row is not None:
        row.event_generate("<Button-1>")
        root.update()
    chk("항목을 누르면 닫힌다", not t.is_open())
    for _ in range(3):
        t.refresh()
        root.update()
    chk("그 뒤 갱신해도 저절로 안 열린다", not t.is_open())

    # 바깥을 눌러서 닫힌 뒤
    t.open()
    root.update()
    if t.popup is not None and t.popup.catcher is not None:
        t.popup.catcher.event_generate("<Button-1>")
        root.update()
    chk("바깥을 누르면 닫힌다", not t.is_open())
    t.refresh()
    root.update()
    chk("그 뒤 갱신해도 저절로 안 열린다", not t.is_open())

    # 다른 메뉴가 열려서 닫힌 뒤 (ui_common.close_all)
    t.open()
    root.update()
    U.PopupMenu(root, [{"text": "딴 메뉴", "enabled": False}], 100, 100)
    root.update()
    chk("다른 메뉴가 열리면 닫힌다", not t.is_open())
    t.refresh()
    root.update()
    chk("그 뒤 갱신해도 저절로 안 열린다", not t.is_open())
    U.close_all()
    root.update()

    section("열려 있을 때는 갱신이 내용을 새로 그린다")
    t.open()
    root.update()
    chk("열려 있다", t.is_open())
    app.pvp_unseen = 7
    t.refresh()
    root.update()
    chk("갱신 뒤에도 열려 있다", t.is_open())
    chk("바뀐 값이 반영된다",
        any("받은 대전" in x and "7" in x for x in rows(t.popup.win)),
        rows(t.popup.win))
    app.pvp_unseen = 2
    t.close()

    section("메뉴를 만들다 터져도 앱이 안 죽는다")
    boom = [0]

    def bad_spec():
        boom[0] += 1
        raise RuntimeError("일부러 터뜨림")

    real_spec = t.spec
    t.spec = bad_spec
    try:
        t.close()
        t.open()                       # 예외를 삼키고 넘어가야 한다
    finally:
        t.spec = real_spec
    chk("터뜨려도 죽지 않는다", boom[0] >= 1)
    chk("반쯤 만든 메뉴를 남기지 않는다",
        t.popup is None or not t.popup.alive())

    section("바깥을 누르면 닫힌다")
    t.open()
    root.update()
    chk("다시 열렸다", t.popup is not None and t.popup.alive())
    if t.popup is not None and t.popup.catcher is not None:
        t.popup.catcher.event_generate("<Button-1>")
        root.update()
        chk("바깥 클릭으로 닫힌다", not t.popup.alive())

    section("로그인 전 메뉴")
    app2 = FakeApp(root, logged_in=False)
    t2 = tray_mac.Tray(app2)
    t2.start()
    t2.open()
    root.update()
    ts4 = rows(t2.popup.win) if (t2.popup and t2.popup.alive()) else []
    chk("연결 중이라고 말한다", any("연결" in x for x in ts4), ts4)
    chk("로그인 전에도 '종료' 는 있다", any(x.strip() == "종료" for x in ts4), ts4)
    t2.stop()
    chk("내리면 상태 항목이 없어진다", t2.item is None)
    chk("내리면 메뉴 창도 없어진다", t2.popup is None or not t2.popup.alive())

    t.stop()
    try:
        root.destroy()
    except Exception:                                       # noqa: BLE001
        pass

    print()
    print("=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
