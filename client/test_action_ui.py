# -*- coding: utf-8 -*-
"""액션 배틀 (2.6.0) - 앱 쪽: 도전 · 수락 · 창 띄우기.

    python client/test_action_ui.py

판은 서버가 내보내는 웹 화면에서 하고, 앱은 도전 · 수락 · 입장권을 받아 창만 띄운다. 서버는 안 띄운다 -
가짜 api 의 응답 모양은 계획(design-notes/2026-11-18-action-battle-plan.md, Task 2)의 M 과 같다.
**친구 창은 진짜로 띄운다** (화면이 있어야 돈다). App 은 해당 메서드만 빌려 쓴다 (test_live_push_ui 처럼).

못 박는 것:

  1. 접속 중인 친구 줄에 '액션' (꺼진 친구는 없음). 누르면 그 친구에게 건다. 걸어 둔 동안은 '취소' + 기다리는 중.
  2. 받은 도전: 알림(ask) → 한 번 물어서 → 확인 창 → 수락을 서버로 → 입장권 → 그 주소로 창. 같은 판은 한 번만 띄운다.
  3. 막힘: 집중 · 실시간 배틀 · 이미 액션 중이면 걸지 않고, 받은 것은 묻지 않고 거절한다.
     액션 판이 열려 있는 동안은 랜덤 배틀 · 놀러 가기도 막는다. 끝나면(over) 풀린다.
  4. 소켓: 붙자마자 caps 를 먼저 보낸다. 'action' 알림은 앱으로 간다. /api/me 의 action 으로 따라잡는다.
  5. 로그아웃 · 끄기 · 다시 켜기 · 업데이트가 다 거치는 close_windows 가 창을 닫고 상태를 비운다.
  6. action_launch: 윈도우 Edge 찾기(레지스트리 → Program Files) · 명령 줄 · 맥 자식 명령(얼린 앱 / 개발) ·
     못 띄우면(길이 없음 · 실행 실패 · 바로 오류로 끝남) 기본 브라우저.
  7. 맥 자식: 주소는 stdin 한 줄로 (명령 줄에 입장권이 없다). --action-view 는 Tk · 앱 · 웹뷰를 안 불러온다.
  8. 돌아가기: 판이 살아 있는데 창이 없으면(닫음 · 끊김) 그 친구 줄에 '돌아가기' - 누르면 입장권을 새로 받아 다시 띄운다.
     저절로는 다시 안 띄운다 (일부러 닫은 창). 창이 떠 있거나 판이 끝났으면 단추가 없다.
  9. 건 사람의 따라잡기: 소켓이 다시 붙으면 들고 있는 도전 · 판을 한 번 묻는다. 소켓 없이 걸어 둔 동안은 3초마다 묻는다
     (서버는 받은 판을 45초 안에 안 들어오면 접는다). 도전이 없어지면 · 끌 때 멈춘다.
 10. 건 사람에게 판이 열렸다고 한 번 알린다 (창이 뒤에 뜰 수 있다). 받은 사람 · 돌아가기에는 안 알린다.
"""
import os
import subprocess
import sys
import tempfile
import time
import types

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-action"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402
import webbrowser                                           # noqa: E402

from poketdesktop import action_launch as AL                # noqa: E402
from poketdesktop import action_view as AV                  # noqa: E402
from poketdesktop import app as APP                         # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_friends                         # noqa: E402
from poketdesktop import visit as VISIT                     # noqa: E402

App = APP.App
OK = FAIL = 0
URL = "https://posk.example/action/play#m=21&t=tk21"


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def match(mid, state, mine=False, foe=(3, "이슬")):
    """서버의 M 모양 (계획 Task 2)."""
    return {"id": mid, "state": state, "foe": {"id": foe[0], "name": foe[1]}, "mine": mine,
            "result": None, "reason": None, "created": "2026-11-18T12:00:00"}


FRIENDS = [{"id": 2, "name": "지우", "online": True, "ranked": False, "wins": 0, "losses": 0},
           {"id": 5, "name": "알망드", "online": False, "lastSeenAgo": 86400, "ranked": False, "wins": 0, "losses": 0}]


class FakeApi(object):
    base = "https://posk.example"

    def __init__(self):
        self.calls = []
        self.state = {"match": None, "incoming": []}

    def friends(self):
        return {"friends": [dict(f) for f in FRIENDS], "incoming": [], "outgoing": [], "blocked": [],
                "limits": {"maxFriends": 30}}

    def action_state(self):
        self.calls.append(("state",))
        return self.state

    def action_invite(self, uid):
        self.calls.append(("invite", uid))
        m = match(11, "invited", mine=True, foe=(uid, "지우"))
        self.state = {"match": m, "incoming": []}
        return {"match": m}

    def action_answer(self, mid, accept=True):
        self.calls.append(("answer", mid, accept))
        m = match(mid, "open" if accept else "declined")
        self.state = {"match": m if accept else None, "incoming": []}
        return {"match": m}

    def action_cancel(self, mid):
        self.calls.append(("cancel", mid))
        self.state = {"match": None, "incoming": []}
        return {"ok": True}

    def action_ticket(self, mid):
        self.calls.append(("ticket", mid))
        return {"ticket": "tk%d" % mid, "path": "/action/play#m=%d&t=tk%d" % (mid, mid)}


class FakeHandle(object):
    def __init__(self, url):
        self.url = url
        self.closed = 0

    def alive(self):
        return not self.closed

    def close(self):
        self.closed += 1


class Fake(object):
    """App 의 액션 배틀 메서드만 빌려 쓴다."""
    action_block = App.action_block
    action_invite = App.action_invite
    action_cancel = App.action_cancel
    on_action_push = App.on_action_push
    check_action = App.check_action
    note_action = App.note_action
    open_action = App.open_action
    _ask_action = App._ask_action
    _action_seen = App._action_seen
    _set_action_pending = App._set_action_pending
    _friends_pane = App._friends_pane
    _redraw_friends = App._redraw_friends
    action_gone = App.action_gone
    action_rejoin = App.action_rejoin
    action_pushed = App.action_pushed
    action_watch = App.action_watch
    _action_poll = App._action_poll
    on_socket_open = App.on_socket_open
    _pvp = App._pvp
    match_playing = App.match_playing

    def __init__(self, root):
        self.root = root
        self.api = FakeApi()
        self.notes = []
        self.settings = {}
        self._pushes = set()
        self._quitting = False
        self.focus = None
        self.live_battle = None
        self.live_pending = None
        self.hub = None
        self.visit = None
        self.arena = self.battle = None
        self._match_loading = False
        self._pvp_busy = False
        self._action_asking = False
        APP._reset_action(self)

    def notify(self, m):
        self.notes.append(m)

    def check_live(self):
        pass

    def on_update_hint(self, _v):
        pass

    def states(self):
        return len([c for c in self.api.calls if c[0] == "state"])


def pump(root, cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


def labels(w):
    """w 아래 모든 Label (자손까지)."""
    out = []
    for c in w.winfo_children():
        if c.winfo_class() == "Label":
            out.append(c)
        out.extend(labels(c))
    return out


def row_of(fw, name):
    """친구 이름 Label 이 든 줄 (Frame). 없으면 None."""
    for lb in labels(fw.list):
        if lb.cget("text") == name:
            return lb.master
    return None


def row_texts(fw, name):
    row = row_of(fw, name)
    return [lb.cget("text") for lb in labels(row)] if row is not None else []


def press(fw, name, text):
    """그 친구 줄의 단추를 누른다 (PushButton 은 Label 에서 손을 뗄 때 부른다)."""
    for lb in labels(row_of(fw, name)):
        if lb.cget("text") == text:
            lb.event_generate("<ButtonRelease-1>")
            return True
    return False


# ================================================================ 친구 줄
def friends(root):
    print("=== 친구 줄 ===")
    app = Fake(root)
    fw = ui_friends.FriendsWindow(app)
    app.hub = types.SimpleNamespace(panes={"friends": fw})
    pump(root, lambda: "액션" in row_texts(fw, "지우"))
    chk("접속 중인 친구 줄에 '액션' ('실시간' 옆)", "액션" in row_texts(fw, "지우") and "실시간" in row_texts(fw, "지우"),
        row_texts(fw, "지우"))
    chk("꺼진 친구 줄에는 없다", row_of(fw, "알망드") is not None and "액션" not in row_texts(fw, "알망드"),
        row_texts(fw, "알망드"))
    chk("누르면 그 친구에게 건다", press(fw, "지우", "액션")
        and pump(root, lambda: ("invite", 2) in app.api.calls), app.api.calls)
    pump(root, lambda: "취소" in row_texts(fw, "지우"))
    t = row_texts(fw, "지우")
    chk("걸어 둔 동안: '취소' + 기다리는 중 (단추 대신)", "취소" in t and any("기다리는 중" in x for x in t)
        and "액션" not in t, t)
    chk("  걸어 둔 도전을 들고 있다", (app.action_pending or {}).get("id") == 11, app.action_pending)
    chk("  신청했다고 남긴다", any("신청" in n for n in app.notes), app.notes)
    press(fw, "지우", "취소")
    pump(root, lambda: "액션" in row_texts(fw, "지우"))
    chk("'취소' → 서버로, 단추가 돌아온다", ("cancel", 11) in app.api.calls and app.action_pending is None
        and "액션" in row_texts(fw, "지우"), (app.api.calls, row_texts(fw, "지우")))

    app.api.calls = []
    press(fw, "지우", "액션")
    pump(root, lambda: app.action_pending is not None)
    app.api.state = {"match": None, "incoming": []}
    app.on_action_push({"t": "action", "s": "declined", "id": 11})
    pump(root, lambda: app.action_pending is None and "액션" in row_texts(fw, "지우"))
    chk("상대가 거절(declined) → 기다리는 중이 걷히고 거절했다고 남긴다", app.action_pending is None
        and any("거절" in n for n in app.notes) and "액션" in row_texts(fw, "지우"), (app.notes[-1:], row_texts(fw, "지우")))
    press(fw, "지우", "액션")
    pump(root, lambda: app.action_pending is not None)
    app.api.state = {"match": None, "incoming": []}
    app.on_action_push({"t": "action", "s": "over", "id": 11})          # 서버: 만료된 도전은 건 사람에게 over
    pump(root, lambda: app.action_pending is None and "액션" in row_texts(fw, "지우"))
    chk("답이 없어 만료(건 사람에게는 over) → 기다리는 중이 걷히고 끝났다고 남긴다", app.action_pending is None
        and "끝났" in app.notes[-1] and "액션" in row_texts(fw, "지우"), app.notes[-1:])
    fw.close()


# ================================================================ 받은 도전 · 창
def accept(root):
    print("=== 받은 도전 ===")
    app = Fake(root)
    asked, launched = [], []
    keep_confirm, keep_open = APP.confirm, AL.open
    APP.confirm = lambda parent, title, msg, **kw: asked.append((title, msg)) or True
    AL.open = lambda url: launched.append(url) or FakeHandle(url)
    try:
        app.api.state = {"match": None, "incoming": [match(21, "invited")]}
        app.on_action_push({"t": "action", "s": "ask", "id": 21})
        pump(root, lambda: launched)
        chk("알림 ask → 한 번 물어서 확인 창 (누가 걸었는지)", app.states() == 1 and len(asked) == 1
            and "이슬" in asked[0][1], asked)
        chk("수락을 서버로", ("answer", 21, True) in app.api.calls, app.api.calls)
        chk("입장권을 받아 그 주소(서버 + path)로 창을 띄운다", launched == [URL]
            and ("ticket", 21) in app.api.calls, launched)
        chk("띄운 창 · 열린 판을 들고 있다", isinstance(app.action_battle, FakeHandle)
            and (app.action_match or {}).get("id") == 21, (app.action_battle, app.action_match))
        chk("  받은 사람에게는 '수락했다' 를 알리지 않는다 (제가 눌렀다)", not any("수락했" in n for n in app.notes),
            app.notes)
        app.on_action_push({"t": "action", "s": "open", "id": 21})
        pump(root, lambda: app.states() == 2)
        pump(root, lambda: False, 0.3)
        chk("같은 판의 open 이 또 와도 다시 띄우지 않는다 (입장권도 한 번)", launched == [URL]
            and len([c for c in app.api.calls if c[0] == "ticket"]) == 1, (launched, app.api.calls))
        app.api.state = dict(app.api.state, incoming=[match(21, "invited")])
        app.on_action_push({"t": "action", "s": "ask", "id": 21})
        pump(root, lambda: app.states() == 3)
        pump(root, lambda: False, 0.2)
        chk("이미 물어본 도전은 또 묻지 않는다", len(asked) == 1 and app.api.calls.count(("answer", 21, True)) == 1,
            asked)

        print("=== 막힘 ===")
        got = []
        App._pvp(app, lambda: got.append("called"), on_done=lambda r, why: got.append(why))
        chk("액션 판 중에는 랜덤 배틀을 걸지 않는다", got and got[0] != "called" and "액션" in str(got[0]), got)
        busy = VISIT.Visit.busy(types.SimpleNamespace(app=app))
        chk("  놀러 가기도 막는다 (까닭 글이 있다)", busy == "action" and "액션" in VISIT.CANT_GO.get(busy, "")
            and "액션" in VISIT.GAVE_UP.get(busy, ""), busy)
        errs = []
        app.action_invite({"id": 2, "name": "지우"}, on_err=errs.append)
        chk("  이미 액션 중이면 또 걸지 않는다 (까닭은 친구 탭으로)", errs and ("invite", 2) not in app.api.calls, errs)

        app.api.state = {"match": None, "incoming": []}
        app.on_action_push({"t": "action", "s": "over", "id": 21})
        pump(root, lambda: app.action_match is None)
        chk("끝나면(over) 풀린다 (창은 결과를 보여 주게 둔다)", app.action_match is None and app.action_block() is None
            and VISIT.Visit.busy(types.SimpleNamespace(app=app)) is None and not app.action_battle.closed,
            (app.action_match, app.action_block()))

        app.api.state = {"match": None, "incoming": [match(22, "invited")]}
        app.on_action_push({"t": "action", "s": "ask", "id": 22})
        pump(root, lambda: len(launched) == 2)
        chk("다음 판을 띄우면 지난 판의 창은 닫는다", len(launched) == 2 and app.action_battle.url != URL
            and launched[0] == URL, launched)

        asked[:] = []
        app.focus = types.SimpleNamespace(active=lambda: True)
        app.action_match = None
        app.api.state = {"match": None, "incoming": [match(23, "invited")]}
        app.on_action_push({"t": "action", "s": "ask", "id": 23})
        pump(root, lambda: ("answer", 23, False) in app.api.calls)
        chk("집중 중에 온 도전은 묻지 않고 거절한다 (건 사람이 기다리지 않게)", not asked
            and ("answer", 23, False) in app.api.calls and len(launched) == 2, (asked, app.api.calls[-2:]))
        errs = []
        app.action_invite({"id": 2, "name": "지우"}, on_err=errs.append)
        chk("  집중 중에는 걸지도 않는다", errs and "집중" in errs[0] and ("invite", 2) not in app.api.calls, errs)
        app.focus = None
        app.live_battle = object()
        errs = []
        app.action_invite({"id": 2, "name": "지우"}, on_err=errs.append)
        chk("실시간 배틀 창이 떠 있으면 걸지 않는다", errs and "실시간" in errs[0] and ("invite", 2) not in app.api.calls,
            errs)
        app.live_battle = None

        APP.confirm = lambda *a, **kw: False
        app.api.state = {"match": None, "incoming": [match(24, "invited")]}
        app.on_action_push({"t": "action", "s": "ask", "id": 24})
        pump(root, lambda: ("answer", 24, False) in app.api.calls)
        chk("확인 창에서 거절하면 거절을 서버로, 창은 안 띄운다", ("answer", 24, False) in app.api.calls
            and len(launched) == 2, app.api.calls[-2:])

        print("=== 동기화로 따라잡기 (/api/me 의 action) ===")
        n = app.states()
        app.note_action(None)
        chk("들고 있는 것도 없고 서버도 없다고 하면 묻지 않는다", app.states() == n)
        app.api.state = {"match": match(31, "fighting"), "incoming": []}
        app.note_action({"id": 31, "state": "fighting", "s": "open"})
        pump(root, lambda: len(launched) == 3)
        chk("소켓이 끊겨 있던 사이 열린 판 → 물어서 창을 띄운다", app.states() == n + 1
            and launched[-1].endswith("#m=31&t=tk31"), launched[-1:])
        app.api.state = {"match": None, "incoming": []}
        app.note_action(None)
        pump(root, lambda: app.action_match is None)
        chk("들고 있던 판이 서버에서 없어졌으면 한 번 맞춘다", app.states() == n + 2 and app.action_match is None)
    finally:
        APP.confirm, AL.open = keep_confirm, keep_open

    print("=== 창을 못 열었을 때 ===")
    app = Fake(root)

    def no_ticket(mid):
        raise RuntimeError("입장권 없음")
    app.api.action_ticket = no_ticket
    app.open_action(match(41, "open"))
    pump(root, lambda: app._action_opened is None)
    chk("입장권을 못 받으면 알리고 다음 알림에 다시 해 볼 수 있게 비운다", app._action_opened is None
        and app.action_match is None and app.action_battle is None and any("못" in n for n in app.notes), app.notes[-1:])


# ================================================================ 돌아가기
def rejoin(root):
    print("=== 창이 닫힌 판에 돌아가기 ===")
    app = Fake(root)
    launched, tickets = [], []
    keep_open = AL.open
    AL.open = lambda url: launched.append(url) or FakeHandle(url)

    def ticket(mid):
        tickets.append(mid)
        return {"ticket": "x", "path": "/action/play#m=%d&t=tk%d-%d" % (mid, mid, len(tickets))}
    app.api.action_ticket = ticket
    try:
        fw = ui_friends.FriendsWindow(app)
        app.hub = types.SimpleNamespace(panes={"friends": fw})
        pump(root, lambda: "배틀" in row_texts(fw, "지우"))
        app.api.state = {"match": match(51, "fighting", foe=(2, "지우")), "incoming": []}
        app.on_action_push({"t": "action", "s": "open", "id": 51})
        pump(root, lambda: isinstance(app.action_battle, FakeHandle))
        fw.draw()
        pump(root, lambda: "배틀" in row_texts(fw, "지우"))
        chk("창이 떠 있으면 '돌아가기' 가 없다", launched and "돌아가기" not in row_texts(fw, "지우")
            and app.action_gone() is None, row_texts(fw, "지우"))

        app.action_battle.closed = 1                       # 창을 닫았다 · 끊겼다 (F5 · 1006)
        fw._watch_live()                                   # 탭이 4초마다 보는 것 - 바뀌었으면 다시 그린다
        pump(root, lambda: "돌아가기" in row_texts(fw, "지우"))
        chk("판이 살아 있는데 창이 없으면 그 친구 줄에 '돌아가기'", "돌아가기" in row_texts(fw, "지우"),
            row_texts(fw, "지우"))
        chk("  다른 친구 줄에는 없다", "돌아가기" not in row_texts(fw, "알망드"), row_texts(fw, "알망드"))

        n = app.states()
        app.on_action_push({"t": "action", "s": "open", "id": 51})
        pump(root, lambda: app.states() == n + 1)
        pump(root, lambda: False, 0.2)
        chk("저절로는 다시 안 띄운다 (일부러 닫은 창을 되살리지 않는다)", len(launched) == 1 and tickets == [51],
            (launched, tickets))

        press(fw, "지우", "돌아가기")
        app.action_rejoin()                                # 두 번 눌러도 (띄우는 중) 창은 하나
        pump(root, lambda: len(launched) == 2 and isinstance(app.action_battle, FakeHandle))
        pump(root, lambda: False, 0.2)
        chk("누르면 입장권을 새로 받아 그 주소로 다시 띄운다", tickets == [51, 51] and len(launched) == 2
            and launched[-1].endswith("#m=51&t=tk51-2") and app.action_battle.alive(), (tickets, launched))
        pump(root, lambda: "돌아가기" not in row_texts(fw, "지우"))
        chk("  다시 떴으면 '돌아가기' 가 걷힌다", "돌아가기" not in row_texts(fw, "지우")
            and "배틀" in row_texts(fw, "지우"), row_texts(fw, "지우"))

        app.api.state = {"match": None, "incoming": []}
        app.on_action_push({"t": "action", "s": "over", "id": 51})
        pump(root, lambda: app.action_match is None)
        app.action_battle.closed = 1
        fw._watch_live()
        pump(root, lambda: False, 0.2)
        chk("판이 끝났으면 창을 닫아도 '돌아가기' 가 없다", "돌아가기" not in row_texts(fw, "지우")
            and app.action_gone() is None, row_texts(fw, "지우"))
        app.action_rejoin()
        pump(root, lambda: False, 0.2)
        chk("  눌러도(늦게) 아무것도 안 한다", len(launched) == 2 and tickets == [51, 51], tickets)
        fw.close()

        print("=== 건 사람: 판이 열리면 알린다 ===")
        app = Fake(root)
        app.action_invite({"id": 2, "name": "지우"})
        pump(root, lambda: app.action_pending is not None)
        app.api.state = {"match": match(11, "open", mine=True, foe=(2, "지우")), "incoming": []}
        app.on_action_push({"t": "action", "s": "open", "id": 11})
        pump(root, lambda: isinstance(app.action_battle, FakeHandle) and app.action_battle.url.endswith("#m=11&t=tk11"))
        got = [x for x in app.notes if "수락했" in x]
        chk("받아져 창이 뜨면 건 사람에게 한 번 알린다 (누가 · 15초 안에 고르기 - 창이 뒤에 뜰 수 있다)", len(got) == 1
            and "지우" in got[0] and "15초" in got[0], app.notes)
        app.action_battle.closed = 1
        app.action_rejoin()
        pump(root, lambda: app.action_battle is not None and app.action_battle.alive())
        chk("  돌아가기로 다시 띄울 때는 또 알리지 않는다", len([x for x in app.notes if "수락했" in x]) == 1, app.notes)
    finally:
        AL.open = keep_open


# ================================================================ 건 사람의 따라잡기
def catchup(root):
    print("=== 소켓이 다시 붙으면 ===")
    launched = []
    keep_open = AL.open
    AL.open = lambda url: launched.append(url) or FakeHandle(url)
    on = types.SimpleNamespace(sock=types.SimpleNamespace(connected=True))
    off = types.SimpleNamespace(sock=types.SimpleNamespace(connected=False))
    try:
        app = Fake(root)
        app.visit = on
        app.on_socket_open({"t": "open", "push": ["live", "action"]})
        pump(root, lambda: False, 0.1)
        chk("들고 있는 것이 없으면 붙어도 묻지 않는다", app.states() == 0)
        app.action_pending = match(11, "invited", mine=True, foe=(2, "지우"))
        app.api.state = {"match": app.action_pending, "incoming": []}
        app.on_socket_open({"t": "open", "push": ["live", "action"]})
        pump(root, lambda: app.states() == 1)
        chk("걸어 둔 도전이 있으면 다시 붙자마자 한 번 묻는다 (끊긴 사이 받아졌을 수 있다)", app.states() == 1)
        chk("  붙어 있으면 따로 물어볼 예약은 없다 (알림이 온다)", app._action_job is None, app._action_job)
        app.action_pending = None
        app.action_match, app._action_opened = match(31, "fighting"), 31
        app.api.state = {"match": None, "incoming": []}
        app.on_socket_open({"t": "open", "push": ["live", "action"]})
        pump(root, lambda: app.action_match is None)
        chk("판을 들고 있어도 묻는다 - 서버가 다시 켜져 판이 없어졌으면 풀린다", app.states() == 2
            and app.action_match is None and app.action_block() is None, app.action_match)

        print("=== 소켓 없이 걸어 둔 동안 ===")
        app = Fake(root)
        app.visit = off
        app._pushes = {"live", "action"}
        app.action_invite({"id": 2, "name": "지우"})
        pump(root, lambda: app.action_pending is not None)
        chk("소켓이 끊긴 채 걸어 두면 따로 물어볼 예약을 건다", app._action_job is not None, app._action_job)
        n = app.states()
        pump(root, lambda: app.states() > n, 5.0)
        chk("  3초 뒤 묻는다", app.states() == n + 1, app.states())
        pump(root, lambda: app._action_job is not None, 1.0)
        chk("  아직 기다리면 또 예약한다", app._action_job is not None and app.action_pending is not None)
        app.api.state = {"match": match(11, "open", mine=True, foe=(2, "지우")), "incoming": []}
        pump(root, lambda: launched and isinstance(app.action_battle, FakeHandle), 5.0)
        chk("  끊긴 사이 받아졌으면 물어서 창을 띄우고 예약은 멈춘다", launched and launched[-1].endswith("#m=11&t=tk11")
            and app.action_pending is None and app._action_job is None, (launched, app._action_job))

        app = Fake(root)
        app.visit = off
        app.action_invite({"id": 2, "name": "지우"})
        pump(root, lambda: app.action_pending is not None)
        app.action_cancel()
        pump(root, lambda: app.action_pending is None)
        chk("도전을 거두면 예약도 멈춘다", app._action_job is None, app._action_job)
        n = app.states()
        app.action_pending = match(12, "invited", mine=True, foe=(2, "지우"))
        app.action_watch(1000)
        chk("  (예약을 걸고)", app._action_job is not None)
        APP._reset_action(app)
        pump(root, lambda: False, 1.4)
        chk("끌 때(_reset_action) 예약을 지운다", app._action_job is None and app.states() == n, app.states())

        app = Fake(root)
        app.visit = on
        app._pushes = {"live", "action"}
        app.action_invite({"id": 2, "name": "지우"})
        pump(root, lambda: app.action_pending is not None)
        chk("소켓이 붙어 있으면 예약하지 않는다 (알림이 온다)", app._action_job is None, app._action_job)
        app._pushes = {"live"}
        app.action_watch()
        chk("  서버가 액션 알림을 안 밀어 주면 예약한다", app._action_job is not None)
        app._set_action_pending(None)
        chk("  도전이 없어지면 지운다", app._action_job is None)
    finally:
        AL.open = keep_open


# ================================================================ 소켓
def socket_checks():
    print("=== 소켓 ===")
    got = []
    fv = types.SimpleNamespace(send=lambda o: got.append(("send", o)) or True, on_event=lambda e: got.append(("ev", e)))
    VISIT.Visit._from_socket(fv, {"t": "open", "push": ["live", "action"]})
    chk("붙자마자 caps 를 먼저 보내고 open 을 넘긴다", [g[0] for g in got] == ["send", "ev"]
        and got[0][1] == {"t": "caps", "v": ["action"]}, got)
    got[:] = []
    VISIT.Visit._from_socket(fv, {"t": "say", "text": "안녕"})
    chk("  다른 것은 그대로 넘긴다 (caps 는 안 보낸다)", [g[0] for g in got] == ["ev"], got)
    pushed = []
    app = types.SimpleNamespace(on_action_push=pushed.append)
    VISIT.Visit.on_event(types.SimpleNamespace(app=app, active=False), {"t": "action", "s": "ask", "id": 5})
    chk("'action' 알림은 놀러 가 있지 않아도 앱으로", pushed == [{"t": "action", "s": "ask", "id": 5}], pushed)


# ================================================================ 끌 때
def closing():
    print("=== 끌 때 ===")

    class Fk(object):
        hub = None
        _live_job = None
        close_arena = lambda self: None            # noqa: E731
        _drop_pillar = lambda self: None           # noqa: E731
    fk = Fk()
    h = FakeHandle(URL)
    fk.action_battle, fk.action_match, fk.action_pending = h, match(21, "fighting"), match(11, "invited", True)
    fk._action_opened, fk._action_told = 21, {21}
    App.close_windows(fk)
    chk("close_windows 가 창을 닫는다 (로그아웃 · 끄기 · 다시 켜기 · 업데이트가 다 거친다)", h.closed == 1)
    chk("  상태를 비운다 (다른 계정에 남기지 않는다)", fk.action_battle is None and fk.action_match is None
        and fk.action_pending is None and fk._action_opened is None and not fk._action_told)


# ================================================================ action_launch
class FakeReg(object):
    """winreg 대신. paths = {hive: 그 칸의 기본값} (없는 hive 는 OSError)."""
    HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE = "HKCU", "HKLM"

    def __init__(self, paths):
        self.paths = paths
        self.opened = []

    def OpenKey(self, hive, sub):
        self.opened.append((hive, sub))
        if hive not in self.paths:
            raise OSError("없음")
        reg = self

        class Key(object):
            def __enter__(self):
                return (hive, reg)

            def __exit__(self, *a):
                return False
        return Key()

    def QueryValue(self, key, sub):
        return self.paths[key[0]]


def launch_checks():
    print("=== Edge 찾기 ===")
    keep_reg = sys.modules.get("winreg")
    keep_isfile, keep_env = os.path.isfile, dict(os.environ)
    edge_hklm = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    try:
        exists = set()
        os.path.isfile = lambda p: p in exists
        reg = FakeReg({"HKLM": '"%s"' % edge_hklm})
        sys.modules["winreg"] = reg
        exists.add(edge_hklm)
        chk("레지스트리 App Paths (따옴표는 벗긴다)", AL.find_edge() == edge_hklm
            and all(sub == AL.EDGE_KEY for _h, sub in reg.opened), (AL.find_edge(), reg.opened))
        sys.modules["winreg"] = FakeReg({})
        os.environ["ProgramFiles(x86)"] = r"C:\PF86"
        os.environ["ProgramFiles"] = r"C:\PF"
        pf = os.path.join(r"C:\PF", "Microsoft", "Edge", "Application", "msedge.exe")
        exists.clear()
        exists.add(pf)
        chk("레지스트리에 없으면 Program Files(x86) → Program Files", AL.find_edge() == pf, AL.find_edge())
        pf86 = os.path.join(r"C:\PF86", "Microsoft", "Edge", "Application", "msedge.exe")
        exists.add(pf86)
        chk("  둘 다 있으면 (x86) 먼저", AL.find_edge() == pf86, AL.find_edge())
        exists.clear()
        chk("  아무 데도 없으면 None", AL.find_edge() is None)
        sys.modules["winreg"] = FakeReg({"HKCU": r"C:\gone\msedge.exe"})
        chk("  레지스트리가 없는 파일을 가리키면 넘어간다", AL.find_edge() is None)
    finally:
        if keep_reg is None:
            sys.modules.pop("winreg", None)
        else:
            sys.modules["winreg"] = keep_reg
        os.path.isfile = keep_isfile
        os.environ.clear()
        os.environ.update(keep_env)

    print("=== 명령 줄 ===")
    keep = (AL.PLATFORM, AL.find_edge, AL._has_webkit, getattr(sys, "frozen", None))
    try:
        AL.PLATFORM = "win32"
        AL.find_edge = lambda: r"C:\Edge\msedge.exe"
        cmd, feed = AL.command(URL)
        chk("윈도우: Edge 앱 창 (이 판 전용 프로필 · 첫 실행 안내 없음 · 1280x760)",
            cmd == [r"C:\Edge\msedge.exe", "--app=" + URL,
                    "--user-data-dir=" + os.path.join(config.data_dir(), "action-edge"),
                    "--no-first-run", "--no-default-browser-check", "--window-size=1280,760"] and feed is None, cmd)
        AL.find_edge = lambda: None
        chk("  Edge 가 없으면 띄울 길이 없다", AL.command(URL) == (None, None))
        AL.PLATFORM = "darwin"
        AL._has_webkit = lambda: True
        cmd, feed = AL.command(URL)
        chk("맥 (개발): 이 파이썬으로 run.pyw --action-view", cmd == [sys.executable,
                                                                     os.path.join(config.CLIENT_DIR, "run.pyw"),
                                                                     "--action-view"], cmd)
        chk("  주소는 stdin 한 줄로 - 명령 줄에 입장권이 없다", feed == URL + "\n"
            and not any("tk21" in c for c in cmd), (feed, cmd))
        sys.frozen = True
        chk("맥 (얼린 앱): 앱 실행 파일 --action-view", AL.command(URL)[0] == [sys.executable, "--action-view"],
            AL.command(URL))
        del sys.frozen
        AL._has_webkit = lambda: False
        chk("  웹뷰(pyobjc WebKit)가 없으면 띄울 길이 없다", AL.command(URL) == (None, None))
        AL.PLATFORM = "linux"
        chk("그 밖의 운영체제도 길이 없다", AL.command(URL) == (None, None))
    finally:
        AL.PLATFORM, AL.find_edge, AL._has_webkit = keep[:3]
        if keep[3] is not None:
            sys.frozen = keep[3]
        elif hasattr(sys, "frozen"):
            del sys.frozen

    print("=== 띄우기 · 기본 브라우저로 ===")
    opened = []
    keep_browser = webbrowser.open
    keep = (AL.command, AL._spawn, AL._allow_foreground, AL.PLATFORM)
    webbrowser.open = lambda url, *a, **kw: opened.append(url) or True
    try:
        AL.command = lambda url: (None, None)
        h = AL.open(URL)
        chk("띄울 길이 없으면 기본 브라우저 (alive 는 늘 False, 닫아도 탈 없음)", opened == [URL] and not h.alive()
            and h.close() is None)

        def boom(cmd, feed=None):
            raise OSError("실행 못 함")
        AL.command = lambda url: (["x"], None)
        AL._spawn = boom
        h = AL.open(URL)
        chk("실행이 안 되면 기본 브라우저", opened[-1] == URL and len(opened) == 2 and not h.alive())
        AL._spawn = keep[1]
        AL.command = lambda url: ([sys.executable, "-c", "import sys; sys.exit(3)"], None)
        h = AL.open(URL)
        chk("띄운 것이 바로 오류로 끝나면 기본 브라우저", len(opened) == 3 and not h.alive())

        fg = []
        AL._allow_foreground = lambda: fg.append(1)
        AL.PLATFORM = "win32"
        AL.command = lambda url: ([sys.executable, "-c", "import time; time.sleep(30)"], None)
        h = AL.open(URL)
        chk("윈도우: 띄운 창이 앞으로 나올 수 있게 (AllowSetForegroundWindow)", fg == [1] and h.alive()
            and len(opened) == 3, (fg, h.alive()))
        h.close()
        chk("close() 가 창(프로세스)을 끝낸다 · 두 번 불러도 된다", not h.alive() and h.close() is None)
    finally:
        webbrowser.open = keep_browser
        AL.command, AL._spawn, AL._allow_foreground, AL.PLATFORM = keep

    print("=== 맥 자식: stdin 으로 주소 ===")
    r, w = os.pipe()
    os.write(w, (URL + "\n그 뒤는 안 읽는다\n").encode("utf-8"))
    os.close(w)
    chk("read_url: 첫 줄만", AV.read_url(r) == URL, URL)
    os.close(r)
    r, w = os.pipe()
    os.close(w)
    chk("  비었으면 빈 글", AV.read_url(r) == "")
    os.close(r)
    out = os.path.join(config.data_dir(), "action-url.txt")
    if os.path.exists(out):
        os.remove(out)
    script = ("import sys, time; sys.path.insert(0, %r); from poketdesktop.action_view import read_url; "
              "f = open(%r, 'w', encoding='utf-8'); f.write(read_url()); f.close(); time.sleep(30)" % (HERE, out))
    proc = AL._spawn([sys.executable, "-c", script], URL + "\n")
    h = AL.Handle(proc)
    end = time.time() + 15
    while time.time() < end and not (os.path.exists(out) and os.path.getsize(out)):
        time.sleep(0.05)
    with open(out, encoding="utf-8") as f:
        seen = f.read()
    chk("자식 프로세스가 stdin 한 줄로 주소를 받는다", seen == URL, seen)
    chk("  돌고 있다 → close() 로 끝난다", h.alive() and (h.close() or True) and proc.poll() is not None,
        proc.poll())
    chk("이 모듈을 불러도 웹뷰는 안 딸려 온다 (Tk 프로세스에 WebKit 을 들이지 않는다)", "WebKit" not in sys.modules)

    code = ("import runpy, sys\nsys.argv = [%r, '--action-view']\n"
            "try:\n    runpy.run_path(%r, run_name='__main__')\nexcept SystemExit as e:\n    print('exit', e.code)\n"
            "print('loaded=' + ','.join(m for m in ('tkinter', 'poketdesktop.app', 'poketdesktop.single', 'WebKit')"
            " if m in sys.modules))"
            % (os.path.join(HERE, "run.pyw"), os.path.join(HERE, "run.pyw")))
    res = subprocess.run([sys.executable, "-c", code], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                         timeout=60)
    lines = res.stdout.strip().splitlines()
    chk("run.pyw --action-view: 주소가 없으면 2 로 끝난다", lines[:1] == ["exit 2"], (res.stdout, res.stderr[-300:]))
    chk("  Tk · 앱 · 한 번만 실행 잠금 · 웹뷰를 불러오지 않는다", lines[1:] == ["loaded="], lines)


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_err

    friends(root)
    accept(root)
    rejoin(root)
    catchup(root)
    socket_checks()
    closing()
    launch_checks()

    pump(root, lambda: False, 0.2)
    chk("콜백에서 터진 곳 없음", not errors, errors[:1])
    try:
        root.destroy()
    except tk.TclError:
        pass
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
