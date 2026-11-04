# -*- coding: utf-8 -*-
"""포켓몬과 집중하기 화면 검사 (집중 타이머).

    python client/test_focus_ui.py
    python client/run_as_windows.py client/test_focus_ui.py

**진짜 Overlay 와 도트 창을 띄운다.** 서버 대신 가짜 api 가 server/app/focus.py 와 같은 모양으로 답한다
(서버 쪽은 server/test_focus.py). 설계: design-notes/2026-11-04-focus-timer.md

못 박는 것:

  1. 동작: 여섯 능력마다 닻(시작한 자리)에서 멀리 안 가고, 달리기는 좌우로 왕복하고, 공부는 제자리
     (창을 거의 안 옮긴다 - 맥 CPU). 걷기 그림뿐인 종도 된다. 시간표에 동작 이름과 mm:ss.
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-focus-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from common import focus as FOCUS                          # noqa: E402
from common import tint as T                                # noqa: E402
from poketdesktop import api as api_mod                     # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import focus_act as FA                    # noqa: E402
from poketdesktop import focus_timer                        # noqa: E402
from poketdesktop import overlay, sprite_cache, tray, walk_cache, wild_ui  # noqa: E402
from poketdesktop import ui_focus as UF                     # noqa: E402
from poketdesktop.app import App                            # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

HOME = os.environ["POKET_HOME"]
OK = FAIL = 0
SHEETS = {}
FILES = {}
POSES = {}          # {번호: [걷기 말고 있는 동작]}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, sec=0.15):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def make_sheet(name, cell, color):
    path = os.path.join(HOME, name)
    im = Image.new("RGBA", (cell * 2, cell * 8), (0, 0, 0, 0))
    for row in range(8):
        for col in range(2):
            im.paste(Image.new("RGBA", (cell // 3, cell - 10), color), (col * cell + cell // 3, row * cell + 5))
    im.save(path)
    return path, {"ok": True, "frameW": cell, "frameH": cell, "durations": [8, 8]}


def make_dot(name, color):
    path = os.path.join(HOME, name)
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (18, 24), color), (11, 8))
    im.save(path)
    return path


def mon(pid, num, slot, name):
    return {"id": pid, "num": num, "species": "X", "shiny": False, "slot": slot, "level": 30,
            "onDesktop": True, "info": {"name": name, "species": name, "level": 30, "types": [],
                                        "evs": {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0},
                                        "evTotal": 0}}


def give_poses(ov, pet, names):
    """그 도트에 걷기 말고 다른 동작 시트를 붙인다 (앱은 뒷줄에서 받아 overlay.sheets 에 넣는다)."""
    for n in names:
        ov.sheets[walk_cache.sheet_key(pet.look, n, T.skin(pet.mon))] = make_sheet(
            "p%d_%s.png" % (pet.look, n), 32, (200, 100, 200, 255))


def counting_place(pet):
    calls = [0]
    orig = pet.place

    def place():
        calls[0] += 1
        orig()
    pet.place = place
    return calls, orig


# ---------------------------------------------------------------- 1. 동작
def act_part(root, ov):
    print("=== 동작 ===")
    p = ov.pets[1]
    give_poses(ov, p, ("Idle", "Sit", "Hop", "Sleep", "Laying"))
    for stat in ("atk", "spa", "spe", "hp", "def", "spd"):
        a = FA.Activity(p, stat)
        p.drive = a
        settle(root, 1.6)
        half = max(40, 1.5 * p.fw)
        chk("%s: 닻에서 멀리 안 간다" % stat,
            abs(p.x + p.ax - a.fx) <= half + 4 and abs(p.y + p.ay - a.fy) <= 6, (p.x + p.ax, a.fx, p.y + p.ay, a.fy))
        a.stop(p)
    chk("움직임 오류 없음", not getattr(p, "_logged_error", False))

    a = FA.Activity(p, "spa")
    p.drive = a
    settle(root, 0.3)
    chk("공부: 앉는다 (Sit)", p.anim_name == "Sit", p.anim_name)
    calls, orig = counting_place(p)
    settle(root, 2.0)
    p.place = orig
    chk("공부는 제자리 (창을 거의 안 옮긴다)", calls[0] <= 2, calls[0])
    a.stop(p)

    a = FA.Activity(p, "spe")
    p.drive = a
    xs = []
    end = time.time() + 4.0
    while time.time() < end:
        root.update()
        xs.append(p.x)
        time.sleep(0.01)
    fx0 = a.fx - p.ax
    chk("달리기는 실제로 좌우로 왕복", min(xs) < fx0 - 10 and max(xs) > fx0 + 10, (min(xs), fx0, max(xs)))
    chk("달리기는 걷기 그림", p.anim_name == "Walk")
    a.stop(p)

    q = ov.pets[2]                          # 걷기 그림뿐인 종
    for stat in ("spa", "spd", "atk"):
        a = FA.Activity(q, stat)
        q.drive = a
        settle(root, 0.5)
        a.stop(q)
    chk("걷기 그림뿐인 종도 동작이 된다", not getattr(q, "_logged_error", False) and q.drive is None)

    for stat in ("atk", "spa", "spe", "hp", "def", "spd"):
        im = FA.prop_image(stat, 16)
        chk("소품 그림 %s (16px, 비지 않음)" % stat, im.size == (16, 16) and im.getbbox() is not None)

    # 검토 #1: 동작마다 칸 크기 · 기준점(ax, ay)이 다르다 (Idle 32 · Hop 48). 깡충을 여러 번 해도 발이 떠오르지 않는다
    q = ov.pets[3]
    for name, cell in (("Idle", 32), ("Hop", 48)):
        ov.sheets[walk_cache.sheet_key(q.look, name, T.skin(q.mon))] = make_sheet(
            "q_%s.png" % name, cell, (90, 200, 120, 255))
    for stat in ("atk", "hp", "spe", "def"):
        a = FA.Activity(q, stat)
        q.drive = a
        fx, fy = q.x + q.ax, q.y + q.ay
        for _ in range(5):
            q.play("Hop", once=True)
            pump(root, lambda: not q.once, 3.0)
        settle(root, 0.3)
        chk("%s: 깡충 다섯 번 뒤에도 발이 제자리 (떠오르지 않는다)" % stat,
            abs((q.y + q.ay) - fy) <= 6 and (stat == "spe" or abs((q.x + q.ax) - fx) <= 4),
            ((q.x + q.ax) - fx, (q.y + q.ay) - fy))
        a.stop(q)
        chk("%s: 끝내면 발이 닻에 내려앉는다" % stat, abs((q.y + q.ay) - fy) <= 1, (q.y + q.ay) - fy)

    # 검토 #4: 배틀 · 진화 연출 중에는 drive 가 몸을 움직이지 않는다
    calls = []
    rec = type("Rec", (), {"update": lambda self_, pet, ms: calls.append(ms), "stop": lambda self_, pet: None})()
    p.drive = rec
    p.battling = True
    settle(root, 0.3)
    p.battling = False
    p.evolving = True
    settle(root, 0.3)
    p.evolving = False
    chk("배틀 · 진화 중에는 집중 동작을 쉰다", calls == [], len(calls))
    p.drive = None

    t = FA.Tag(root, p, "spa")
    t.set(754, 10, 40)
    settle(root, 0.3)
    chk("시간표: 12:34 와 동작 이름", any("12:34" in s for s in texts(t.win))
        and any("공부" in s for s in texts(t.win)), texts(t.win))
    chk("시간표 글자가 눌리지 않는다", not squeezed(t.win), squeezed(t.win))
    tx, ty = t.win.winfo_x(), t.win.winfo_y()
    th = t.win.winfo_reqheight()
    room = int(p.y + p.fh + 2) + th <= ov.area()[3]
    chk("시간표는 도트 밑 가운데 (밑에 자리가 없으면 위)",
        (ty >= int(p.y + p.fh) if room else ty + th <= int(p.y))
        and abs(tx + t.win.winfo_width() / 2.0 - (p.x + p.ax)) < 6, (room, tx, ty, p.x, p.y, p.fh))
    p.y = ov.area()[3] - p.fh - 1
    p.place()
    settle(root, 0.3)
    # (맥은 창 자리를 한두 px 반올림한다 - 4px 까지는 봐준다)
    chk("화면 아래 끝이면 도트 위로", t.win.winfo_y() + th <= int(p.y) + 4, (t.win.winfo_y(), th, p.y, t._pos))
    t.destroy()
    a = FA.Activity(p, "spa")
    p.drive = a
    a.stop(p)
    chk("멈추면 drive 가 떨어진다", p.drive is None)


# ---------------------------------------------------------------- 2. 모드 (가짜 서버)
LOST = "게임이 꺼져 있었거나 컴퓨터가 잠들어서 집중이 끝났어요. 마지막 세트는 인정되지 않았어요."


def run_view(pet=2, stat="spa", rid=7, left=1500, stale=False, sets=0, today=0):
    act, stat_kr = FOCUS.act_of(stat)
    return {"id": rid, "pokemon": {"id": pet, "name": "꼬부기", "num": 7, "shiny": False}, "stat": stat,
            "act": act, "statKr": stat_kr, "startedAt": "", "setLeft": left, "setSec": 1500, "sets": sets,
            "todayEv": today, "dailyEv": 40, "stale": stale}


def credit(stat="spa", ev=5, today=5, capped=None):
    return {"stat": stat, "act": FOCUS.act_of(stat)[0], "ev": ev, "capped": capped, "todayEv": today,
            "dailyEv": 40, "at": ""}


class FakeApi(object):
    def __init__(self):
        self.calls = []
        self.stops = 0
        self.wilds = 0
        self.beat_error = None
        self.start_error = None
        self.state_error = None
        self.next_beat = None
        self.next_start = None
        self.today = 10

    def _err(self, status, msg="서버 오류"):
        return api_mod.ApiError(msg, status)

    def focus_state(self):
        self.calls.append(("state",))
        if self.state_error:
            raise self._err(self.state_error, "Not Found")
        return {"running": None, "todayEv": self.today, "dailyEv": 40,
                "rules": {"setSec": 1500, "evPerSet": 5, "dailyEv": 40, "beatSec": 60, "gapSec": 180}}

    def focus_start(self, pid, stat):
        self.calls.append(("start", pid, stat))
        if self.start_error:
            raise self._err(*self.start_error)
        return self.next_start or {"running": run_view(pet=pid, stat=stat), "existing": False, "message": "시작"}

    def focus_beat(self):
        self.calls.append(("beat",))
        if self.beat_error:
            raise self._err(self.beat_error)
        r = self.next_beat or {"running": run_view(), "sets": [], "ended": None, "message": None}
        self.next_beat = None
        return r

    def focus_stop(self):
        self.calls.append(("stop",))
        self.stops += 1
        return {"running": None, "sets": [], "part": 3, "ended": "done", "message": "집중 끝! 오늘 28분 집중했어요."}

    def wild(self, force=False):
        self.wilds += 1
        return {}


class FakeWild(object):
    def __init__(self):
        self.stops = self.starts = 0

    def stop(self):
        self.stops += 1

    def start(self):
        self.starts += 1


class MiniApp(object):
    def __init__(self, root, ov):
        self.root, self.overlay = root, ov
        self.settings = ov.settings
        self.api = FakeApi()
        self.wild = FakeWild()
        self.battle = self.arena = None
        self.visit = None
        self.notes, self.syncs, self.lost = [], 0, 0
        self._match_loading = False
        self.balls = 0
        self.focus = focus_timer.FocusController(self)

    def notify(self, m):
        self.notes.append(m)

    def request_sync(self):
        self.syncs += 1

    def refresh_tray(self):
        pass

    def on_session_lost(self):
        self.lost += 1

    focus_quiet = App.focus_quiet
    match_playing = App.match_playing


def shown(p):
    try:
        return p.win.state() != "withdrawn"
    except Exception:                                       # noqa: BLE001
        return False


def pump(root, cond, sec=3.0):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def mode_part(root, ov, three):
    print("\n=== 모드 ===")
    app = MiniApp(root, ov)
    f = app.focus
    chk("처음엔 집중 아님", not f.active() and not app.focus_quiet())
    f.start(2, "spa")
    pump(root, f.active)
    settle(root, 0.4)
    chk("시작: 서버에 spa 로", ("start", 2, "spa") in app.api.calls, app.api.calls)
    chk("고른 포켓몬만 보인다", shown(ov.pets[2]) and not shown(ov.pets[1]) and not shown(ov.pets[3]))
    chk("집중 포켓몬이 동작 중 (공부)", ov.pets[2].drive is not None and ov.pets[2].drive.stat == "spa")
    chk("시간표가 떴다", f.tag is not None and any("공부" in s for s in texts(f.tag.win)))
    chk("풀숲을 멈춘다", app.wild.stops == 1)
    wc = wild_ui.WildController(app)
    wc.check(force=True)
    settle(root, 0.3)
    chk("집중 중엔 풀숲 확인이 막힌다", app.api.wilds == 0)
    chk("집중 중이면 알림을 미룬다 (focus_quiet)", app.focus_quiet())
    ov.sync(three, {}, {})
    settle(root, 0.2)
    chk("동기화가 다른 도트를 되살리지 않는다", not shown(ov.pets[1]) and shown(ov.pets[2]))
    ov.set_hidden(True)
    ov.set_hidden(False)
    settle(root, 0.2)
    chk("배틀 숨김에서 돌아와도 집중 포켓몬만", not shown(ov.pets[1]) and shown(ov.pets[2]))
    chk("집중 포켓몬의 이름표는 다시 안 뜬다", ov.pets[2].name_win is None or not shown_name(ov.pets[2]))

    app.api.next_beat = {"sets": [credit(ev=5, today=15)], "running": run_view(left=1500, sets=1, today=15),
                         "ended": None, "message": None}
    f.beat()
    pump(root, lambda: f.said)
    chk("세트 말풍선 (+5, 오늘 15/40)", f.said and f.said[-1].startswith("특공 노력치 +5") and "15/40" in f.said[-1],
        f.said)
    chk("묻지 않고 이어진다", f.active() and f.left() > 1490)
    app.api.next_beat = {"sets": [credit(ev=0, today=40, capped="day")], "running": run_view(),
                         "ended": None, "message": None}
    f.beat()
    pump(root, lambda: len(f.said) >= 2)
    chk("오늘 몫이 꽉 찼을 때 문구", "다 받았어요" in f.said[-1], f.said)
    app.api.beat_error = 500
    n0 = len(app.api.calls)
    f.beat()
    settle(root, 0.4)
    chk("RF4: 맥박이 실패해도 모드 유지", f.active() and len(app.api.calls) == n0 + 1)
    chk("RF4: 다음 맥박이 걸려 있다", f._beat_job is not None)
    app.api.beat_error = None
    n0 = app.api.calls.count(("beat",))
    f.note({"running": None})           # 시작보다 먼저 읽힌 옛 동기화 - 서버에는 아직 진행 중
    settle(root, 0.4)
    chk("검토 #2: 옛 동기화가 '없다' 고 해도 바로 풀지 않고 맥박으로 확인한다",
        f.active() and app.api.calls.count(("beat",)) == n0 + 1, app.api.calls[-3:])
    app.api.beat_error = 500
    f._set_view(run_view(left=0))       # 세트가 끝나는 무렵에 서버가 죽었다
    n0 = app.api.calls.count(("beat",))
    settle(root, 4.5)
    chk("맥박이 실패하면 2초마다 몰아치지 않는다 (다음 정규 맥박에)", app.api.calls.count(("beat",)) - n0 <= 1,
        app.api.calls.count(("beat",)) - n0)
    app.api.beat_error = None
    f._set_view(run_view())
    app.api.next_beat = {"running": None, "ended": "done", "sets": [], "message": None}
    f.note({"running": None})
    settle(root, 0.4)
    chk("RF3: 다른 곳에서 끝냄 → 조용히 풀림", not f.active() and "다른 곳" in f.said[-1], f.said)
    chk("끝나면 다 되살아난다", all(shown(p) for p in ov.pets.values()))
    chk("끝나면 풀숲 다시 · 동기화 한 번", app.wild.starts >= 1 and app.syncs >= 1)
    chk("끝나면 집중 동작이 풀린다", all(p.drive is None for p in ov.pets.values()))
    chk("끝나면 시간표가 없다", f.tag is None)

    # RF2: 꺼졌다 켠 앱 (끊긴 집중이 /api/me 에 아직 실려 온다)
    app2 = MiniApp(root, ov)
    g = app2.focus
    app2.api.next_beat = {"ended": "lost", "message": LOST, "running": None, "sets": []}
    stale = {"running": run_view(rid=9, stale=True)}
    g.note(stale)
    pump(root, lambda: g.said)
    g.note(stale)                       # 맥박보다 먼저 받아 둔 옛 동기화가 또 온다
    settle(root, 0.4)
    g.note({"running": None})
    settle(root, 0.2)
    chk("RF2: lost 를 한 번만 알린다", g.said.count(LOST) == 1 and not g.active(), g.said)
    chk("RF2: 같은 집중으로 다시 들어가지 않는다", app2.api.calls.count(("beat",)) == 1, app2.api.calls)

    # RF5: 집중 포켓몬이 바탕화면에서 빠진다
    f.start(2, "atk")
    pump(root, f.active)
    ov.sync([m for m in three if m["id"] != 2], {}, {})
    f.on_pets_synced()
    pump(root, lambda: not f.active())
    chk("RF5: 포켓몬이 빠지면 끝내고 까닭을 말한다", app.api.stops == 1 and not f.active()
        and "빠져서" in f.said[-1], f.said)
    ov.sync(three, {}, {})
    settle(root, 0.2)

    # 시작 거절 · 끝내기
    app.api.start_error = (409, "친구와 연결돼 있는 동안에는 집중을 시작할 수 없습니다. 돌아온 뒤 시작해 주세요.")
    got = []
    f.start(2, "spa", done=lambda r, err: got.append(err))
    pump(root, lambda: got)
    chk("시작이 거절되면 모드에 안 들어가고 까닭을 돌려준다", not f.active() and got and "돌아온 뒤" in str(got[0]))
    app.api.start_error = None
    app.battle = type("B", (), {"closed": False})()
    got = []
    n0 = len(app.api.calls)
    f.start(2, "spa", done=lambda r, err: got.append(err))
    pump(root, lambda: got)
    chk("배틀 중에는 시작하지 않는다 (서버도 안 부른다)", not f.active() and "배틀" in str(got[0])
        and len(app.api.calls) == n0, (got, app.api.calls[n0:]))
    app.battle = None
    f.start(2, "spa")
    pump(root, f.active)
    f.stop()
    pump(root, lambda: not f.active())
    chk("끝내기: 서버에 알리고 풀린다", app.api.stops == 2 and not f.active() and "집중 끝" in f.said[-1], f.said)
    chk("left_text 는 mm:ss", focus_timer.mmss(754) == "12:34")
    f.start(2, "spa")
    pump(root, f.active)
    f.clear()
    chk("clear: 서버를 안 부르고 모드만 푼다", not f.active() and app.api.stops == 2
        and all(shown(p) for p in ov.pets.values()))

    # 검토 #5: 집중 전에 보낸 풀숲 확인의 답이 늦게 와도 풀숲을 돋우지 않는다
    f.start(2, "spa")
    pump(root, f.active)
    wc = wild_ui.WildController(app)
    wc.apply({"wild": None, "nextInSeconds": 60})
    chk("검토 #5: 늦게 온 풀숲 답은 집중 중이면 버린다 (다음 확인 예약도 안 건다)", wc._job is None and wc.grass is None)
    # 검토 #4: 집중 중에는 대전을 걸거나 보지 않는다 (투기장이 바탕화면을 쥔다)
    App.watch_match(app, 5)
    chk("검토 #4: 집중 중 대전 보기는 막고 까닭을 말한다", app.notes and "집중" in app.notes[-1]
        and not getattr(app.api, "matches", None), app.notes[-1:])
    got = []
    App._pvp(app, lambda: got.append("called"), on_done=lambda r, why: got.append(why))
    chk("검토 #4: 집중 중 대전 걸기도 막는다", got and got[0] != "called" and "집중" in str(got[0]), got)
    # 검토 #3: 로그아웃 · 회원탈퇴 (_restart_login) 는 집중 화면을 다 치운다
    UF.open_focus(app)
    app.alarms = type("A", (), {"stop": lambda self_: None})()
    app.alarm_window = type("W", (), {"closed": 0, "alive": lambda self_: True,
                                      "close": lambda self_: setattr(self_, "closed", 1)})()
    aw = app.alarm_window
    App.close_focus(app)
    chk("검토 #3: 로그아웃하면 집중 모드 · 집중 창 · 알림 창을 치운다", not f.active()
        and getattr(app, "focus_window", None) is None and aw.closed == 1 and app.alarm_window is None)
    ov.set_only(2)
    ov.clear()
    chk("검토 #3: 바탕화면을 비우면 '이것만' 도 풀린다", ov.only is None)
    ov.sync(three, {}, {})
    settle(root, 0.3)


# ---------------------------------------------------------------- 3. 창 · 메뉴 줄
def win_texts(w):
    return " ".join(texts(w))


def window_part(root, ov):
    print("\n=== 창 · 메뉴 줄 ===")
    app = MiniApp(root, ov)
    f = app.focus
    p = ov.pets[2]
    p.mon["info"]["evs"] = {"hp": 0, "atk": 252, "def": 0, "spa": 10, "spd": 0, "spe": 0}
    p.mon["info"]["evTotal"] = 262
    w = UF.FocusStartWindow(app, p)
    pump(root, lambda: w.today is not None)
    settle(root, 0.2)
    t = win_texts(w.win)
    chk("여섯 동작이 다 있다", all(k in t for k in ("헬스", "공부", "달리기", "스트레칭", "버티기", "명상")), t)
    chk("능력마다 지금 노력치", "252 / 252" in " ".join(texts(w.rows["atk"])) and "10 / 252" in " ".join(texts(w.rows["spa"])))
    chk("꽉 찬 능력에 '기록만'", "기록만" in " ".join(texts(w.rows["atk"])), texts(w.rows["atk"]))
    chk("합계와 오늘 몫", "262 / 510" in t and "10 / 40" in t, t)
    chk("글자가 눌리지 않는다", not squeezed(w.win), squeezed(w.win))
    w.pick("spa")
    w.go()
    pump(root, f.active)
    chk("시작하면 서버에 spa 로, 창이 닫힌다", ("start", 2, "spa") in app.api.calls and not w.alive())
    f.clear()

    app.api.today = 40
    w = UF.FocusStartWindow(app, p)
    pump(root, lambda: w.today is not None)
    settle(root, 0.2)
    chk("오늘 40 이면 알린다", "다 받았어요" in win_texts(w.win), win_texts(w.win))
    app.api.today = 10
    app.api.start_error = (409, "친구와 연결돼 있는 동안에는 집중을 시작할 수 없습니다. 돌아온 뒤 시작해 주세요.")
    w.pick("atk")
    w.go()
    pump(root, lambda: "돌아온 뒤" in w.err.cget("text"))
    chk("거절 문구를 창에 띄우고 창은 남는다", "돌아온 뒤" in w.err.cget("text") and w.alive() and not f.active())
    app.api.start_error = None
    w.close()

    app.api.state_error = 404
    w = UF.FocusStartWindow(app, p)
    pump(root, lambda: "업데이트" in w.err.cget("text"))
    chk("옛 서버면 '서버 업데이트 뒤'", "업데이트" in w.err.cget("text"), w.err.cget("text"))
    app.api.state_error = None
    w.close()

    w = UF.FocusStartWindow(app, None)
    pump(root, lambda: w.today is not None)
    chk("포켓몬 없이 열면 바탕화면 맨 앞이 골라진다", w.pet is not None and w.pet.id in ov.pets, w.pet)
    w.choose(ov.pets[3])
    chk("포켓몬을 바꿀 수 있다", w.pet is ov.pets[3])
    w.close()

    chk("메뉴 줄: 같이 집중하기...", (UF.menu_row(app, p) or {}).get("text") == "같이 집중하기...")
    f.start(2, "spa")
    pump(root, f.active)
    chk("집중 중엔 그 포켓몬에 '집중 끝내기...'", (UF.menu_row(app, ov.pets[2]) or {}).get("text") == "집중 끝내기...")
    chk("다른 포켓몬엔 줄이 없다", UF.menu_row(app, ov.pets[1]) is None)
    app.visit = type("V", (), {"active": True})()
    chk("놀러 가기 중엔 줄이 없다", UF.menu_row(app, ov.pets[2]) is None)
    app.visit = None
    chk("앱에 visit · focus 가 없어도 깨지지 않는다", UF.menu_row(object(), p) is None)

    panel = UF.open_focus(app)
    settle(root, 1.2)
    t = win_texts(panel.win)
    chk("집중 창: 남은 시간 · 오늘 몫", "남은 시간" in t and "/ 40" in t and "공부" in t, t)
    chk("집중 창 글자가 눌리지 않는다", not squeezed(panel.win), squeezed(panel.win))
    asked = []
    UF.ASK = lambda *a, **kw: asked.append(a) or True
    stops = app.api.stops
    panel.end()
    pump(root, lambda: not f.active())
    chk("끝내기: 확인을 묻고 서버에 알린다", asked and "노력치를 못 받아요" in asked[0][2]
        and app.api.stops == stops + 1 and not f.active(), asked)
    chk("끝나면 집중 창이 닫힌다", not panel.alive())
    UF.ASK = lambda *a, **kw: False
    f.start(2, "spa")
    pump(root, f.active)
    panel = UF.open_focus(app)
    panel.end()
    settle(root, 0.3)
    chk("확인에서 취소하면 그대로", f.active() and app.api.stops == stops + 1)
    panel.close()
    f.clear()
    chk("트레이 줄: 집중 아님", tray.focus_label(app) == "포켓몬과 집중하기...")
    f.start(2, "spa")
    pump(root, f.active)
    chk("트레이 줄: 집중 중", tray.focus_label(app) == "집중 중 · 공부", tray.focus_label(app))
    f.clear()

    import types
    from poketdesktop import ui_friends
    fake = types.SimpleNamespace(app=types.SimpleNamespace(live_pending=None, visit=None, api=None))
    acts = ui_friends.FriendsWindow._friend_actions(fake, {"id": 5, "online": True, "visitable": False,
                                                           "visitFocus": True})
    chk("친구 줄: 집중 중인 친구는 '집중 중' (놀러 가기 단추 없음)",
        any(a[0] == "label" and a[1] == "집중 중" for a in acts) and not any(a[1] == "놀러 가기" for a in acts), acts)


def shown_name(p):
    try:
        return p.name_win.state() != "withdrawn"
    except Exception:                                       # noqa: BLE001
        return False


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
    for n, col in ((4, (230, 110, 40, 255)), (7, (80, 140, 220, 255)), (1, (60, 160, 90, 255))):
        SHEETS[n] = make_sheet("s%d.png" % n, 32, col)
        FILES[n] = make_dot("d%d.png" % n, col)
    sprite_cache.ensure = lambda api, num, shiny=False: FILES.get(num)
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (
        SHEETS.get(num) if name == "Walk" and SHEETS.get(num) else (None, None))
    settings = dict(config.DEFAULTS)
    settings["megaWalk"] = []
    ov = overlay.Overlay(root, settings)
    ov.paths.update(dict(((n, False), p) for n, p in FILES.items()))
    ov.walks.update(dict(SHEETS))
    three = [mon(1, 4, 0, "파이리"), mon(2, 7, 1, "꼬부기"), mon(3, 1, 2, "이상해씨")]
    settings["showNames"] = True
    ov.sync(three, {}, {})
    ov.start()
    settle(root, 0.3)
    try:
        act_part(root, ov)
        mode_part(root, ov, three)
        window_part(root, ov)
    finally:
        ov.stop()
        ov.clear()
        settle(root, 0.2)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
