# -*- coding: utf-8 -*-
"""도감 업적 화면 검사 (시즌 3). 진짜 Tk 로 띄운다.

    python client/test_achievements_ui.py

  1. 달성 알림 창: 하나면 '업적 달성!', 여럿이면 '지금까지의 기록으로' 로
     묶고 여덟 줄 넘게는 '그 밖 N개'. 칭호·볼 보상을 적는다. 눌린 위젯 없음.
  2. 업적 칸: 갈래로 묶고, 안 한 것은 진행 막대, 한 것은 달성 날짜.
     숨은 업적은 서버가 가려 보낸 그대로(???).
  3. 도감 탭의 '업적' 단추로 격자와 번갈아 본다.
  4. 같은 업적이 다음 동기화에 또 실려 와도 **두 번 띄우지 않는다.**
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-ach-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_achievements as UA              # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def pump(root, cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


def ach(key, name, group="도감 수집", title=None, balls=0, got=False, value=0,
        target=50, hidden=False):
    a = {"key": key, "group": group, "name": name, "desc": "%s 설명" % name,
         "target": target, "title": title, "balls": balls, "hidden": hidden}
    if got:
        a["gotAt"] = "2026-10-02T00:10:00+00:00"
    else:
        a["value"] = value
    return a


PUBLIC = {
    "done": 2, "total": 5,
    "unlocks": {"unlock_7": True, "unlock_9": False},
    "achievements": [
        ach("dex_50", "50종", balls=5, got=True),
        ach("dex_400", "400종", title="도감 조사원", value=120, target=400),
        ach("region_1", "관동 도감 완성", group="지방 도감", title="관동 도감 완성",
            value=100, target=146),
        ach("unlock_ultra", "울트라홀 개척자", group="해금", title="울트라홀 개척자",
            got=True, target=49),
        {"key": "hidden_nick", "group": "숨은 업적", "name": "???", "desc": "숨은 업적",
         "target": 1, "title": None, "balls": 0, "hidden": True},
    ],
}


class FakeApi(object):
    def __init__(self):
        self.calls = []

    def achievements(self):
        self.calls.append("list")
        return PUBLIC

    def achievements_seen(self):
        self.calls.append("seen")
        return {"ok": True}


class FakeApp(object):
    def __init__(self, root):
        self.root = root
        self.api = FakeApi()
        self.dex = None
        self.notes = []

    def notify(self, message):
        self.notes.append(message)


def close_toplevels(root):
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            try:
                w.destroy()
            except tk.TclError:
                pass


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    print("글꼴 %s / 본문 %dpt" % (U.FAMILY, U.BASE_PT))
    app = FakeApp(root)

    print("=== 알림 창 — 하나 ===")
    shot = {}
    orig_wait = root.wait_window

    def spy_wait(win):
        root.update()
        win.update_idletasks()
        shot["t"] = " ".join(texts(win))
        shot["bad"] = squeezed(win)
        win.destroy()
    root.wait_window = spy_wait
    UA.announce(root, app, [ach("dex_400", "400종", title="도감 조사원", got=True)])
    chk("'업적 달성!'", "업적 달성!" in shot["t"], shot["t"][:80])
    chk("칭호 보상을 적는다", "도감 조사원" in shot["t"], shot["t"][:120])
    chk("칭호를 어디서 다는지 알려준다", "랭킹 탭" in shot["t"])
    chk("눌린 위젯 없음", not shot["bad"], shot["bad"][:3])

    print("\n=== 알림 창 — 여럿 (처음 켠 사람) ===")
    many = [ach("k%d" % i, "업적%d" % i, balls=5 if i % 2 else 0,
                title=None if i % 2 else "칭호%d" % i, got=True) for i in range(12)]
    UA.announce(root, app, many)
    chk("한 창에 묶는다", "지금까지의 기록으로 업적 12개" in shot["t"], shot["t"][:80])
    chk("여덟 줄 넘게는 '그 밖'", "그 밖 4개" in shot["t"], shot["t"][-120:])
    chk("볼 보상도 적는다", "몬스터볼 5개" in shot["t"])
    chk("눌린 위젯 없음", not shot["bad"], shot["bad"][:3])
    root.wait_window = orig_wait

    print("\n=== 업적 칸 ===")
    host = tk.Toplevel(root)
    host.geometry("900x620+40+40")
    p = UA.AchievementPanel(host, app)
    p.pack(fill="both", expand=True)
    p.reload()
    pump(root, lambda: p.data is not None)
    root.update()
    t = " ".join(texts(host))
    chk("달성 수", "달성 2 / 5" in t, t[:80])
    chk("갈래로 묶는다", "도감 수집  1/2" in t and "지방 도감  0/1" in t, t[:300])
    chk("한 것은 날짜", "2026-10-02 달성" in t, t[:300])
    chk("안 한 것은 진행 수", "120 / 400" in t and "100 / 146" in t, t[:400])
    chk("숨은 업적은 가려진 채로", "???" in t)
    chk("열린 해금을 알려준다", "열림: 울트라홀" in t, t[:200])
    bad = squeezed(host)
    chk("눌린 위젯 없음", not bad, bad[:3])
    host.destroy()

    print("\n=== 도감 탭에서 번갈아 보기 ===")
    from poketdesktop import ui_dex

    class DexApi(FakeApi):
        def dexbook(self):
            return {"seen": [], "caught": [], "gens": {}, "total": 0}
    app2 = FakeApp(root)
    app2.api = DexApi()
    try:
        dw = ui_dex.DexWindow(app2)
    except Exception as e:                                  # noqa: BLE001
        dw = None
        chk("도감 창이 뜬다", False, e)
    if dw is not None:
        root.update()
        chk("처음엔 격자", dw.dex_body.winfo_manager() and dw.ach is None)
        dw.toggle_achievements()
        pump(root, lambda: dw.ach is not None and dw.ach.data is not None)
        root.update()
        chk("누르면 업적 칸", dw.ach.f.winfo_manager() and not dw.dex_body.winfo_manager())
        chk("단추가 '도감으로'", "도감으로" in dw.ach_btn.label.cget("text"),
            dw.ach_btn.label.cget("text"))
        dw.toggle_achievements()
        root.update()
        chk("다시 누르면 격자", dw.dex_body.winfo_manager() and not dw.ach.f.winfo_manager())
        chk("단추에 업적 수", "업적 2/5" in dw.ach_btn.label.cget("text"),
            dw.ach_btn.label.cget("text"))
        bad = squeezed(dw.win)
        chk("머리줄 눌림 없음", not bad, bad[:3])
        dw.close()

    print("\n=== 같은 업적을 두 번 안 띄운다 ===")
    from poketdesktop import app as APP

    class Mini(object):
        announce_achievements = APP.App.announce_achievements
        _show_achievements = APP.App._show_achievements

        def __init__(self, root):
            self.root = root
            self.api = FakeApi()
            self._ach_queue, self._ach_known = [], set()
            self._ach_showing = False
            self._quitting = False
            self._gift_showing = False
            self.battle = self.arena = None
            self.shown = []
    m = Mini(root)
    real = UA.announce
    UA.announce = lambda parent, a, items: m.shown.append([x["key"] for x in items])
    try:
        items = [ach("dex_50", "50종", got=True), ach("dex_100", "100종", got=True)]
        m.announce_achievements(items)
        pump(root, lambda: "seen" in m.api.calls, timeout=5)
        m.announce_achievements(items)          # 다음 동기화에 또 실려 왔다
        root.update()
        chk("한 번만 띄운다", m.shown == [["dex_50", "dex_100"]], m.shown)
        chk("본 뒤 서버에 알린다", "seen" in m.api.calls, m.api.calls)
        m.battle = object()                     # 배틀 중이면 기다린다
        m.announce_achievements([ach("dex_200", "200종", got=True)])
        root.update()
        chk("배틀 중에는 기다린다", m.shown == [["dex_50", "dex_100"]], m.shown)
        m.battle = None
        pump(root, lambda: len(m.shown) == 2, timeout=5)
        chk("끝나면 띄운다", m.shown[-1:] == [["dex_200"]], m.shown)
    finally:
        UA.announce = real

    close_toplevels(root)
    root.destroy()
    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
