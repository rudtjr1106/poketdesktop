# -*- coding: utf-8 -*-
"""가방이 낡은 개수를 보여 주지 않는가 (게시판 #711 사뚱).

    python client/test_bag_stale.py

가방 탭의 도구 칸은 처음 열 때 읽은 개수를 계속 보여 줬다 - 볼을 다 던져도 열어 둔 가방에는 볼이 남아 보였다.
이제 가방 속이 바뀌면 앱이 칸에 표시(stale)하고(app.bag_changed), 다시 볼 때 가방 탭이 읽는다(BagTabs.on_shown).

Tk 창은 안 띄운다: 칸 · 허브 · after 를 가짜로 끼우고 판단만 본다 (진짜 Tk 로 읽는지는 test_bag_tabs).

  1. BagTabs.on_shown: 바뀌었거나 오래됐을 때만, 도구 칸만, 읽는 중이면 안 읽는다. 테마 가방 탭도 같은 것을 쓴다.
  2. app.bag_changed: 표시는 늘, 다시 읽기는 보고 있을 때만 - 예약은 한 번만 (이어 던지기 30번에 30번 읽지 않게).
  3. BagWindow.reload · _loaded: 조용히 읽기 (여는 중 표시 · 빨간 말 없음), 앞서 보낸 것의 늦은 답은 버린다.
     조용히 읽어 성공하면 앞서 실패한 새로고침의 빨간 말은 지운다.
"""
import importlib
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-bag-stale-"))

from poketdesktop import app as APP                         # noqa: E402
from poketdesktop import ui_bag                             # noqa: E402
from poketdesktop import ui_bag_tabs as BT                  # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Pane(object):
    """도구 칸 (BagWindow) 의 다시 읽기에 쓰는 것만."""

    def __init__(self, loaded_at=None):
        self.alive = True
        self.stale = False
        self._loading = False
        self._loaded_at = time.time() if loaded_at is None else loaded_at
        self._stale_job = None
        self.reloads = []

    def reload(self, quiet=False):
        self.reloads.append(quiet)


class TmPane(object):
    """기술머신 칸 - _loaded_at 이 없다 (358줄)."""

    def __init__(self):
        self.alive = True
        self.reloads = []

    def reload(self, quiet=False):
        self.reloads.append(quiet)


class Holder(object):
    def __init__(self):
        self.packed = False

    def winfo_manager(self):
        return "pack" if self.packed else ""

    def pack(self, **_kw):
        self.packed = True

    def pack_forget(self):
        self.packed = False


def tabs_with(items, tms=None, current="items"):
    t = BT.BagTabs.__new__(BT.BagTabs)
    t.panes = {"items": items}
    if tms is not None:
        t.panes["tms"] = tms
    t.holders = {"items": Holder(), "tms": Holder()}
    t.holders[current].packed = True
    t.current = current
    return t


def check_on_shown():
    print("=== 1. 다시 볼 때 (BagTabs.on_shown)")
    p = Pane()
    t = tabs_with(p)
    t.on_shown()
    chk("방금 읽었고 바뀐 것이 없으면 안 읽는다", p.reloads == [], p.reloads)
    p.stale = True
    t.on_shown()
    chk("가방 속이 바뀌었으면(stale) 다시 읽는다 - 조용히", p.reloads == [True], p.reloads)

    p = Pane(loaded_at=time.time() - BT.STALE_SEC - 1)
    tabs_with(p).on_shown()
    chk("읽은 지 %d초가 넘었으면 다시 읽는다" % BT.STALE_SEC, p.reloads == [True], p.reloads)
    p = Pane(loaded_at=0.0)
    tabs_with(p).on_shown()
    chk("  아직 다 읽은 적이 없어도 (처음 읽기가 실패했다)", p.reloads == [True], p.reloads)

    p = Pane()
    p.stale, p._loading = True, True
    tabs_with(p).on_shown()
    chk("읽는 중이면 또 읽지 않는다 (bag_changed 의 예약과 겹칠 때)", p.reloads == [], p.reloads)

    p = Pane()
    p.stale, p.alive = True, False
    tabs_with(p).on_shown()
    chk("닫힌 칸은 안 읽는다", p.reloads == [], p.reloads)

    p, tm = Pane(loaded_at=0.0), TmPane()
    p.stale = True
    t = tabs_with(p, tm, current="tms")
    t.on_shown()
    chk("기술머신 칸을 보고 있으면 아무것도 안 읽는다 (358줄 - 돌아올 때마다 받지 않는다)",
        p.reloads == [] and tm.reloads == [], (p.reloads, tm.reloads))
    t.show("items")
    chk("  기술머신에서 도구로 돌아오면 그때 읽는다", t.current == "items" and p.reloads == [True]
        and tm.reloads == [], (t.current, p.reloads))
    t.show("tms")
    chk("  다시 기술머신으로 가도 기술머신은 안 읽는다", t.current == "tms" and tm.reloads == [], tm.reloads)

    t = tabs_with(None)
    t.panes = {}
    t.on_shown()
    chk("칸이 아직 없어도 괜찮다", True)

    for key in ("dp", "gs", "emerald", "pt", "bw", "swsh"):
        m = importlib.import_module("poketdesktop.skins.%s.bag_tabs" % key)
        chk("테마 %s 의 가방 탭도 같은 on_shown 을 쓴다" % key, m.BagTabs.on_shown is BT.BagTabs.on_shown
            and issubclass(m.BagTabs.CLASSES["items"], ui_bag.BagWindow), m.BagTabs)


class Root(object):
    def __init__(self):
        self.jobs = []

    def after(self, ms, fn):
        self.jobs.append((ms, fn))
        return len(self.jobs)

    def after_cancel(self, job):
        pass


class Hub(object):
    def __init__(self, tabs, current="bag"):
        self.panes = {"bag": tabs}
        self.current = current


class Host(object):
    """App 의 bag_changed 만 빌려 쓴다 (트레이 · 바탕화면 없이)."""
    bag_changed = APP.App.bag_changed
    BAG_RELOAD_MS = APP.App.BAG_RELOAD_MS
    BAG_RELOAD_GAP = APP.App.BAG_RELOAD_GAP

    def __init__(self, hub):
        self.hub = hub
        self.root = Root()


def check_bag_changed():
    print("\n=== 2. 가방 속이 바뀌었다 (app.bag_changed)")
    p = Pane(loaded_at=0.0)
    host = Host(Hub(tabs_with(p)))
    host.bag_changed()
    host.bag_changed()
    host.bag_changed()
    chk("보고 있으면 표시하고 다시 읽기를 예약한다 - 세 번 불러도 예약은 하나", p.stale and len(host.root.jobs) == 1
        and p._stale_job == 1, (p.stale, host.root.jobs))
    chk("  바로 읽지 않고 %dms 기다린다 (바뀐 것을 모아 한 번에)" % APP.App.BAG_RELOAD_MS,
        host.root.jobs[0][0] == APP.App.BAG_RELOAD_MS and p.reloads == [], host.root.jobs[0][0])
    host.root.jobs[0][1]()
    chk("  때가 되면 한 번 조용히 읽고 예약을 지운다", p.reloads == [True] and p._stale_job is None, p.reloads)
    host.bag_changed()
    chk("  읽은 뒤 또 바뀌면 다시 예약한다", len(host.root.jobs) == 2 and p._stale_job == 2, host.root.jobs)

    p = Pane()                                      # 방금 다 읽었다
    host = Host(Hub(tabs_with(p)))
    host.bag_changed()
    ms = host.root.jobs[0][0] if host.root.jobs else None
    chk("방금 읽었으면 %d초가 차기를 기다린다 (이어 던지기 - 저절로 읽기는 그보다 자주 안 한다)"
        % APP.App.BAG_RELOAD_GAP, ms is not None and APP.App.BAG_RELOAD_MS < ms <= APP.App.BAG_RELOAD_GAP * 1000, ms)

    p = Pane(loaded_at=0.0)
    host = Host(Hub(tabs_with(p)))
    host.bag_changed()
    p._loading = True                               # 그사이 팔기 · 쓰기로 읽기 시작했다
    host.root.jobs[0][1]()
    chk("때가 됐는데 읽는 중이면 끝난 뒤에 다시 본다 (지금은 안 읽는다)", p.reloads == [] and len(host.root.jobs) == 2
        and p._stale_job == 2, (p.reloads, host.root.jobs))
    p._loading, p.stale = False, False              # 그 읽기가 바뀐 것까지 담아 왔다
    host.root.jobs[1][1]()
    chk("  그 읽기가 끝났고 더 바뀐 것이 없으면 안 읽는다", p.reloads == [] and p._stale_job is None, p.reloads)

    p = Pane(loaded_at=0.0)
    host = Host(Hub(tabs_with(p), current="box"))
    host.bag_changed()
    chk("다른 탭을 보고 있으면 표시만 한다 (가방 탭으로 오면 on_shown 이 읽는다)", p.stale and not host.root.jobs,
        host.root.jobs)
    p = Pane(loaded_at=0.0)
    host = Host(Hub(tabs_with(p, TmPane(), current="tms")))
    host.bag_changed()
    chk("기술머신 칸을 보고 있어도 표시만 한다", p.stale and not host.root.jobs, host.root.jobs)

    p = Pane(loaded_at=0.0)
    host = Host(Hub(tabs_with(p)))
    host.bag_changed()
    p.alive = False                                 # 예약한 뒤 허브를 닫았다
    host.root.jobs[0][1]()
    chk("예약한 뒤 칸이 닫혔으면 안 읽는다", p.reloads == [], p.reloads)

    host = Host(None)
    host.bag_changed()
    chk("허브가 없으면 아무 일도 없다", not host.root.jobs)
    t = tabs_with(None)
    t.panes = {}
    host = Host(Hub(t))
    host.bag_changed()
    chk("가방 탭에 도구 칸이 아직 없어도", not host.root.jobs)


class Overlay(object):
    made = []

    def __init__(self, win, text):
        Overlay.made.append(text)
        self.closed = False

    def close(self):
        self.closed = True


class Err(Exception):
    message = "서버가 답하지 않습니다"


def bag_window():
    w = ui_bag.BagWindow.__new__(ui_bag.BagWindow)
    w.app = type("A", (), {"api": object()})()
    w.root = Root()
    w.win = None
    w.alive = True
    w._pending = None
    w._wait = None
    w.stale = True
    w._loaded_at = 0.0
    w._loading = False
    w._load_n = 0
    w._stale_job = None
    w.said = []
    w.say = lambda text, *a: w.said.append(text)
    return w


def filled(w):
    """읽기가 성공했을 때 그리는 것 (목록 · 돈 · 고른 도구) 은 건너뛴다 - 아래 줄의 말만 본다."""
    w._said_err = False
    w.item_id = None
    w._paint_money = lambda *a: None
    w._fill_items = w._fill_mons = lambda: None
    w._first_item = lambda: None
    w.pick_item = lambda _t: None
    return w


def 가방_답():
    return ({"items": [], "bag": {"POKEBALL": 3}, "money": 100}, [], {}, None)


def check_reload():
    print("\n=== 3. 가방 칸의 다시 읽기 (BagWindow.reload · _loaded)")
    calls = []
    real_async, real_overlay = ui_bag.U.run_async, ui_bag.ui_loading.Overlay
    ui_bag.U.run_async = lambda root, work, cb: calls.append(cb)
    ui_bag.ui_loading.Overlay = Overlay
    try:
        w = bag_window()
        w.reload(quiet=True)
        chk("조용히 읽으면 여는 중 표시도 '여는 중...' 말도 없다", not Overlay.made and w.said == [] and w._wait is None,
            (Overlay.made, w.said))
        chk("  읽기 시작할 때 stale 을 끈다 (읽는 사이 또 바뀌면 다시 켜진다)", w.stale is False and w._loading is True)
        calls[-1](None, Err())
        chk("  조용히 읽은 것이 실패하면 빨간 말 없이 stale 로 남긴다 (다시 볼 때 또 읽는다)",
            w.stale is True and w._loading is False and w.said == [], (w.stale, w.said))

        w = bag_window()
        w.reload()
        chk("새로고침 단추 (조용히가 아님): 예전처럼 여는 중 표시", Overlay.made == ["가방을 여는 중"]
            and w.said == ["가방을 여는 중..."], (Overlay.made, w.said))
        first = calls[-1]
        w.reload(quiet=True)
        chk("  표시는 하나만 (겹쳐 띄우지 않는다)", len(Overlay.made) == 1)
        first(None, Err())
        chk("  앞서 보낸 것의 늦은 답은 버린다 - 표시도 나중 답이 걷는다", w._loading is True and w._wait is not None
            and w.said == ["가방을 여는 중..."], (w._loading, w.said))
        ov = w._wait
        calls[-1](None, Err())
        chk("  나중 답이 오면 끝 - 표시를 걷는다", w._loading is False and w._wait is None and ov.closed)

        w = bag_window()
        w.alive = False
        w.reload(quiet=True)
        calls[-1](None, Err())
        chk("창을 닫은 뒤 온 답은 아무것도 안 그린다", w.said == [], w.said)

        # 게시판 #711 검토: 처음 (조용하지 않게) 읽기가 실패해 빨간 말이 떴는데, 다시 볼 때 조용히 읽어 성공해도 지우지
        # 않았다 - 목록 · 개수는 채워졌는데 '서버에 연결할 수 없습니다' 가 그대로 남았다
        w = filled(bag_window())
        w.reload()
        calls[-1](None, Err())
        chk("새로고침이 실패하면 빨간 말을 띄우고 적어 둔다", w.said[-1:] == ["서버가 답하지 않습니다"]
            and w._said_err is True and w.stale is True, (w.said, getattr(w, "_said_err", None)))
        w.reload(quiet=True)
        calls[-1](가방_답(), None)
        chk("  다시 볼 때 조용히 읽어 성공하면 그 빨간 말을 지운다", w.said[-1:] == [""] and w._said_err is False
            and w.stale is False and w._loaded_at > 0, (w.said, w._said_err))
        n = len(w.said)
        w.reload(quiet=True)
        calls[-1](가방_답(), None)
        chk("  오류가 없었으면 조용히 읽기는 아래 줄을 그대로 둔다 (판 말 · 쓴 말을 안 지운다)", len(w.said) == n, w.said)

        w = filled(bag_window())
        w.reload(quiet=True)
        calls[-1](None, Err())
        w.reload(quiet=True)
        calls[-1](가방_답(), None)
        chk("조용히 읽기만 실패했으면(빨간 말 없음) 성공해도 아래 줄을 안 건드린다", w.said == [], w.said)
    finally:
        ui_bag.U.run_async, ui_bag.ui_loading.Overlay = real_async, real_overlay


def main():
    check_on_shown()
    check_bag_changed()
    check_reload()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
