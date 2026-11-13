# -*- coding: utf-8 -*-
"""실시간 배틀 초대 · 새 앱 판 알림을 소켓으로 받는다 (2.5.0).

    python client/test_live_push_ui.py

예전에는 친구 탭을 열어 둔 사람마다 4초에 한 번씩 /api/live 를 물었고, 새 판은 한 시간마다 깃허브에 물어서야
알았다. 이제 서버가 놀러 가기 소켓(앱이 켜져 있는 동안 늘 붙어 있다)으로 민다.

못 박는 것:

  1. 소켓의 hello 에서 push(서버가 밀어 주는 것) · latest(최신 앱 판)를 넘긴다. 옛 서버는 둘 다 없다.
  2. 놀러 가 있지 않아도 open · live · update 가 앱으로 간다.
  3. 붙으면 놓친 초대를 한 번 챙긴다. 'live' 를 밀어 주는 서버에 붙어 있을 때만 폴링을 멈춘다 - 끊겼거나
     옛 서버면 친구 탭이 예전처럼 4초마다 묻는다.
  4. 새 판 알림: 내 판보다 새것일 때만, '나중에' 를 고른 판이 아닐 때만, exe 로 돌 때만 확인한다. 모두가 같은
     순간에 깃허브를 두드리지 않게 조금씩 늦추고, 여러 번 와도 한 번만 잡아 둔다.
"""
import os
import sys
import tempfile
import types

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-live-push"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from common.version import VERSION                          # noqa: E402
from poketdesktop import app as APP                         # noqa: E402
from poketdesktop import ui_friends                         # noqa: E402
from poketdesktop import updater                            # noqa: E402
from poketdesktop import visit as VISIT                     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Root(object):
    def __init__(self):
        self.jobs = []

    def after(self, ms, fn=None):
        self.jobs.append((ms, fn))
        return "job%d" % len(self.jobs)

    def after_cancel(self, _job):
        pass


class Fake(object):
    """App 의 해당 메서드만 빌려 쓴다."""
    on_socket_open = APP.App.on_socket_open
    live_pushed = APP.App.live_pushed
    on_live_push = APP.App.on_live_push
    on_update_hint = APP.App.on_update_hint
    UPDATE_HINT_SPREAD_MS = APP.App.UPDATE_HINT_SPREAD_MS

    def __init__(self):
        self._pushes = set()
        self._update_hint_job = None
        self._quitting = False
        self.settings = {}
        self.visit = None
        self.root = Root()
        self.checked = 0
        self.looked = 0
        self.hints = []

    def check_live(self):
        self.checked += 1

    def _look_for_update(self):
        self.looked += 1


def bump(v, i=1):
    """VERSION 의 마지막 자리를 올린 판."""
    parts = [int(x) for x in v.split(".")]
    parts[-1] += i
    return ".".join(str(x) for x in parts)


def main():
    print("=== 소켓의 hello ===")
    ev = VISIT.VisitSocket._opened(None, {"t": "hello", "userId": 3, "push": ["live"], "latest": "9.9.9"})
    chk("push · latest 를 넘긴다", ev.get("t") == "open" and ev.get("push") == ["live"] and ev.get("latest") == "9.9.9"
        and ev.get("userId") == 3, ev)
    ev = VISIT.VisitSocket._opened(None, {"t": "hello", "userId": 3})
    chk("옛 서버: push 는 빈 목록, latest 는 없음", ev.get("push") == [] and ev.get("latest") is None, ev)

    print("=== 놀러 가 있지 않아도 앱으로 ===")
    app = Fake()
    got = []
    app.on_socket_open = lambda e: got.append(("open", e))
    app.on_live_push = lambda e: got.append(("live", e))
    app.on_update_hint = lambda v: got.append(("update", v))
    fake_visit = types.SimpleNamespace(app=app, active=False)
    VISIT.Visit.on_event(fake_visit, {"t": "open", "push": ["live"]})
    VISIT.Visit.on_event(fake_visit, {"t": "live", "s": "ask", "id": 5})
    VISIT.Visit.on_event(fake_visit, {"t": "update", "v": "9.9.9"})
    chk("open · live · update 가 차례로 간다", [g[0] for g in got] == ["open", "live", "update"] and got[2][1] == "9.9.9", got)

    print("=== 붙었을 때 ===")
    app = Fake()
    app.on_socket_open({"t": "open", "push": ["live"]})
    chk("'live' 를 밀어 주는 서버에 붙으면 놓친 초대를 한 번 챙긴다", app.checked == 1 and "live" in app._pushes, app.checked)
    app.visit = types.SimpleNamespace(sock=types.SimpleNamespace(connected=True))
    chk("  붙어 있으면 폴링하지 않는다", app.live_pushed() is True)
    app.visit.sock.connected = False
    chk("  끊기면 다시 묻는다", app.live_pushed() is False)
    app.visit = None
    chk("  소켓이 없으면 묻는다", app.live_pushed() is False)
    app = Fake()
    app.visit = types.SimpleNamespace(sock=types.SimpleNamespace(connected=True))
    app.on_socket_open({"t": "open", "push": []})
    chk("옛 서버에 붙으면 (push 없음) 예전처럼 묻는다", app.checked == 0 and app.live_pushed() is False, app._pushes)
    app.on_socket_open({"t": "open", "push": ["live"]})
    chk("  새 서버로 다시 붙으면 멈춘다", app.live_pushed() is True)
    c0 = app.checked
    app.on_live_push({"t": "live", "s": "ask", "id": 9})
    chk("초대 알림이 오면 /api/live 를 한 번 묻는다", app.checked == c0 + 1)

    print("=== 친구 탭 ===")
    fw = types.SimpleNamespace(alive=True, app=app, _live_key=None, root=Root(), _live_job=None, drawn=0)
    fw.draw = lambda: setattr(fw, "drawn", fw.drawn + 1)
    fw._watch_live = lambda: None
    c0 = app.checked
    ui_friends.FriendsWindow._watch_live(fw)
    chk("소켓으로 오면 친구 탭이 묻지 않는다", app.checked == c0, app.checked)
    chk("  걸어 둔 초대가 바뀌었나는 4초마다 계속 본다", fw.root.jobs and fw.root.jobs[-1][0] == 4000, fw.root.jobs)
    app.live_pending = {"id": 3}
    ui_friends.FriendsWindow._watch_live(fw)
    chk("  걸어 둔 초대가 생기면 다시 그린다", fw.drawn == 1 and fw._live_key == 3, fw.drawn)
    app.visit.sock.connected = False
    ui_friends.FriendsWindow._watch_live(fw)
    chk("끊기면 친구 탭이 예전처럼 묻는다", app.checked == c0 + 1, app.checked)
    old = types.SimpleNamespace(checked=0, live_pending=None)
    old.check_live = lambda: setattr(old, "checked", old.checked + 1)
    fw.app = old
    ui_friends.FriendsWindow._watch_live(fw)
    chk("live_pushed 가 없는 앱(시험용)이면 묻는다", old.checked == 1)

    print("=== 새 앱 판 알림 ===")
    frozen, supported = updater.is_frozen, updater.supported
    updater.is_frozen = lambda: True
    updater.supported = lambda: True
    try:
        app = Fake()
        new = bump(VERSION)
        chk("내 판보다 새것이면 확인을 잡아 둔다", app.on_update_hint(new) is True and len(app.root.jobs) == 1)
        ms, fn = app.root.jobs[0]
        chk("  모두가 같은 순간에 두드리지 않게 0~%d ms 늦춘다" % app.UPDATE_HINT_SPREAD_MS,
            0 <= ms <= app.UPDATE_HINT_SPREAD_MS and app.UPDATE_HINT_SPREAD_MS >= 5000, ms)
        chk("  여러 번 와도 (hello + update) 한 번만", app.on_update_hint(new) is False and len(app.root.jobs) == 1)
        fn()
        chk("  때가 되면 늘 하던 확인을 한다", app.looked == 1 and app._update_hint_job is None, app.looked)
        chk("같은 판이면 안 한다", app.on_update_hint(VERSION) is False)
        chk("옛 판이면 안 한다", app.on_update_hint("0.0.1") is False)
        chk("없으면 안 한다", app.on_update_hint(None) is False and app.on_update_hint("") is False)
        app.settings["updateSkipped"] = new
        chk("'나중에' 를 고른 판이면 안 한다", app.on_update_hint(new) is False)
        chk("  그보다 새 판이면 한다", app.on_update_hint(bump(VERSION, 2)) is True)
        app = Fake()
        app._quitting = True
        chk("끝내는 중이면 안 한다", app.on_update_hint(new) is False)
        app = Fake()
        app.on_socket_open({"t": "open", "push": ["live"], "latest": new})
        chk("hello 의 latest 로도 한다 (알릴 때 끊겨 있던 앱)", len(app.root.jobs) == 1 and app.checked == 1, app.root.jobs)
        updater.is_frozen = lambda: False
        app = Fake()
        chk("개발 중(파이썬)에는 안 한다", app.on_update_hint(new) is False and not app.root.jobs)
    finally:
        updater.is_frozen, updater.supported = frozen, supported

    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
