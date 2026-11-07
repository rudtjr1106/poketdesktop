# -*- coding: utf-8 -*-
"""포스크탑 올림픽 화면 검사 — 바탕화면 중계 · 2시 예약 · 겹칠 때 · 올림픽 창.

    python client/test_olympics_ui.py
    python client/run_as_windows.py client/test_olympics_ui.py

**진짜 Overlay 와 도트 창을 띄운다.** 서버 대신 가짜 api 가 server/app/olympics.py 와 같은 모양으로 답한다
(서버 쪽은 server/test_olympics.py). 중계 시계는 빠르게 돌린다 (olympics_show.time 을 바꿔 끼운다).

못 박는 것:
  1. 달리기형(100m · 수영 · 마라톤): 선수가 다 나오고, 기록 차례대로 들어오고, 넘어진 선수 말, 끝나면 선수 창이
     없어지고 바탕화면 포켓몬이 되살아난다. 수영은 반환점에서 몸을 돌리고 창 아래가 잘린다(물).
  2. 시기형(장대 · 역도 · 원반 · 스키점프): 점수판의 최고 기록이 서버 기록과 같다 · 파울을 센다 · 기다리는 선수는
     창을 안 옮긴다(맥 CPU) · 소품 창이 치워진다.
  3. 도트가 없는 선수 · 걷기 그림뿐인 선수도 중계가 끝까지 간다. 응원은 연출뿐이다.
  4. 2시: 지나간 종목은 '다시 보기' 로, 남은 종목은 시간에 맞춰 중계 · 집중 중이면 건너뛴다 · 중계 중에는 풀숲 ·
     집중 시작이 쉰다.
  5. 올림픽 창 · 신청 창(별 · 표시 · 작전 → 신청) · 순위표 · 결과 카드 · 오른쪽 클릭 줄 · 관리 창 리본 글.
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-oly-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from common import olympics as O                            # noqa: E402
from common import tint as T                                # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import olympics as OC                     # noqa: E402
from poketdesktop import olympics_show as OS                # noqa: E402
from poketdesktop import overlay, sprite_cache, walk_cache, wild_ui  # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_olympics as UO                  # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

HOME = os.environ["POKET_HOME"]
OK = FAIL = 0
SHEETS = {}
FILES = {}


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


def pump(root, cond, sec=3.0):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


class FastTime(object):
    """중계 시계를 scale 배 빠르게."""

    def __init__(self, scale):
        self.scale = scale
        self.t0 = time.monotonic()

    def monotonic(self):
        return self.t0 + (time.monotonic() - self.t0) * self.scale

    def __getattr__(self, k):
        return getattr(time, k)


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
            "onDesktop": True, "info": {"name": name, "species": name, "level": 30, "types": []}}


def entrant(i, num, rec, tries=None, mine=False, seed=None, rank=None):
    return {"entryId": 100 + i, "lane": i, "user": "선수%d" % i, "mine": mine,
            "pokemon": {"id": 900 + i, "name": "포켓%d" % i, "species": "S%d" % num, "num": num, "look": num,
                        "shiny": False, "tint": None},
            "tactic": "safe", "record": rec, "text": O.text("sprint", rec) if rec else "기록 없음",
            "tries": tries or [{"v": rec, "slip": False}], "seed": seed or (i * 31 + 7), "rank": rank or (i + 1)}


def heat(event, ents, heat_no=1):
    for e in ents:
        e["text"] = O.text(event, e["record"])
    return {"day": O.DAYS[0], "dayNo": 1, "event": event, "kr": O.EV[event]["kr"], "heat": heat_no, "heats": 2,
            "entrants": ents, "total": 40, "cheer": ["고스트", "불꽃"]}


class FakeApi(object):
    def __init__(self):
        self.calls = []
        self.live = None
        self.heats = {}
        self.state = None
        self.cands = None
        self.board = None

    def olympics_live(self):
        self.calls.append(("live",))
        return self.live

    def olympics_heat(self, eid):
        self.calls.append(("heat", eid))
        return self.heats[eid]

    def olympics(self):
        self.calls.append(("state",))
        return self.state

    def olympics_candidates(self, event):
        self.calls.append(("cands", event))
        return self.cands

    def olympics_enter(self, event, pid, tactic):
        self.calls.append(("enter", event, pid, tactic))
        return {"day": O.DAYS[0], "entry": {}, "message": "나가요"}

    def olympics_cancel(self, event):
        self.calls.append(("cancel", event))
        return {}

    def olympics_board(self, event, day=None):
        self.calls.append(("board", event, day))
        return self.board


class FakeWild(object):
    def __init__(self):
        self.stops = self.starts = 0

    def stop(self):
        self.stops += 1

    def start(self):
        self.starts += 1


class FakeFocus(object):
    def __init__(self):
        self.on = False
        self.pet_id = None

    def active(self):
        return self.on


class MiniApp(object):
    def __init__(self, root, ov):
        self.root, self.overlay = root, ov
        self.settings = ov.settings
        self.api = FakeApi()
        self.wild = FakeWild()
        self.focus = FakeFocus()
        self.battle = self.arena = None
        self.visit = None
        self.syncs = 0
        self.olympics_window = None
        self.olympics = OC.OlympicsController(self)

    def request_sync(self):
        self.syncs += 1

    def refresh_tray(self):
        pass

    def notify(self, m):
        pass


def shown(w):
    try:
        return w.state() != "withdrawn"
    except Exception:                                       # noqa: BLE001
        return False


def run_show(root, app, h, scale, sec=20.0, replay=False):
    OS.time = FastTime(scale)
    got = {}
    s = OS.Show(app, h, on_done=lambda sh, r: got.update(r=r), replay=replay)
    ticks = [0]
    orig = s._tick

    def counted():
        ticks[0] += 1
        orig()
    s._tick = counted
    s.start()
    pump(root, lambda: "r" in got, sec)
    OS.time = time
    return s, got.get("r"), ticks[0]


# ---------------------------------------------------------------- 1. 달리기형
def race_part(root, ov, app):
    print("=== 달리기형 ===")
    recs = [12.31, 11.84, 12.95, 12.02, 13.40, 12.60, 11.97, 12.20]
    ents = [entrant(i, (i % 6) + 1, r, mine=(i == 2)) for i, r in enumerate(recs)]
    ents[2]["tries"] = [{"v": recs[2], "slip": True, "at": 0.5}]
    s0 = [shown(p.win) for p in ov.pets.values()]
    started = {}
    orig_start = OS.Show._race_setup

    def spy(self):
        orig_start(self)
        started["extra"] = len(ov.extra)
        started["hidden"] = all(not shown(p.win) for p in ov.pets.values())
        started["names"] = ov._names_block
    OS.Show._race_setup = spy
    crossed = []
    orig_cross = OS.Show._crossed

    def spy_cross(self, e):
        crossed.append(e["entryId"])
        return orig_cross(self, e)
    OS.Show._crossed = spy_cross
    s, r, ticks = run_show(root, app, heat("sprint", ents), 10)
    OS.Show._race_setup = orig_start
    OS.Show._crossed = orig_cross
    chk("100m: 선수 8마리가 나온다", started.get("extra") == 8, started)
    chk("100m: 그동안 바탕화면 포켓몬은 숨는다 · 이름표도", started.get("hidden") and started.get("names", 0) > 0, started)
    chk("100m: 끝까지 간다", r is not None and not r["aborted"], r)
    want = [e["entryId"] for e in sorted(ents, key=lambda e: e["record"])]
    chk("100m: 기록 차례대로 들어온다 (한 틱에 여럿이어도)", crossed == want, (crossed, want))
    chk("100m: 넘어진 내 선수에게 말", any("넘어졌어요" in x for x in s.said), s.said)
    chk("100m: 결과 - 조 순위", r["heatRank"] == 7 and r["text"] == "12.95초", r)
    chk("100m: 끝나면 선수 창이 없다", not ov.extra and not s.pets)
    chk("100m: 바탕화면 포켓몬이 되살아난다", [shown(p.win) for p in ov.pets.values()] == s0 and ov.only is None)
    chk("100m: 이름표 막음도 풀린다", ov._names_block == 0, ov._names_block)
    chk("100m: 창 옮기기는 틱 x 선수 수 안 (맥 CPU)", s.moves <= ticks * 8 + 16, (s.moves, ticks))

    # 수영: 반환점에서 몸을 돌리고, 창 아래가 잘린다
    ents = [entrant(i, (i % 6) + 1, 28.0 + i * 0.4, mine=(i == 0)) for i in range(4)]
    seen = {"turned": False, "clipped": False}
    orig_put = OS.Show._lane_put

    def spy_put(self, pet, eid, d, done):
        orig_put(self, pet, eid, d, done)
        if d > 0.6 and not done and pet.facing == OS.LEFT:
            seen["turned"] = True
        try:
            if pet.win.winfo_height() < pet.fh - 4:
                seen["clipped"] = True
        except Exception:                                   # noqa: BLE001
            pass
    OS.Show._lane_put = spy_put
    s, r, _t = run_show(root, app, heat("swim", ents), 25)
    OS.Show._lane_put = orig_put
    chk("수영: 끝까지", r is not None and not r["aborted"], r)
    chk("수영: 반환점 뒤에는 왼쪽을 본다", seen["turned"], seen)
    chk("수영: 물에 잠긴 것처럼 창 아래가 잘린다", seen["clipped"], seen)

    # 마라톤: 둘레를 돌고 다 들어온다 (한 마리는 도트가 없다)
    ents = [entrant(i, (i % 6) + 1, 7400 + i * 90, mine=(i == 1)) for i in range(5)]
    ents[4]["pokemon"]["num"] = ents[4]["pokemon"]["look"] = 777          # 도트 없음
    s, r, _t = run_show(root, app, heat("marathon", ents), 40)
    chk("마라톤: 도트 없는 선수가 있어도 끝까지", r is not None and not r["aborted"] and len(s.done_at) == 5, r)
    chk("마라톤: 중간 순위 말", any("지점" in x for x in s.said), s.said)
    # 가장 느린 마라톤(점수 0.58 = 3:44:08)이 있어도 중계가 프로그램 끝 전에 끝난다
    slow = [entrant(i, (i % 6) + 1, rec) for i, rec in enumerate((7400, 13448))]
    sh = OS.Show(app, heat("marathon", slow))
    sh._stage()
    sh.pets = {}
    sh.layer = None
    sh._race_setup()
    longest = max(sh.T.values())
    budget = O.END - O.OFFSET["marathon"] - (OS.INTRO_MS + OS.OUTRO_MS) / 1000.0 - OC.READY_WAIT_MS / 1000.0
    chk("마라톤: 가장 느린 선수도 프로그램 끝 전에 들어온다", longest <= budget, (longest, budget))


# ---------------------------------------------------------------- 2. 시기형
def field_part(root, ov, app):
    print("=== 시기형 ===")
    for ev, vals in (("pole", (5.1, 5.35, None)), ("lift", (150, None, 162)),
                     ("discus", (52.3, None, 55.0)), ("ski", (None, 118.5, 121.0))):
        ents = []
        for i in range(3):
            tries = [{"v": (v + i * 0.1 if isinstance(v, float) else (v + i if v else None)) if v else None,
                      "slip": v is None} for v in vals]
            rec = O.best_of(ev, [t["v"] for t in tries])
            ents.append(entrant(i, i + 1, rec, tries=tries, mine=(i == 0)))
        props_made = []
        orig_prop = OS.Prop.__init__

        def spy_prop(self, *a, **kw):
            orig_prop(self, *a, **kw)
            props_made.append(self)
        OS.Prop.__init__ = spy_prop
        place_counts = {}
        orig_make = OS.Show._make_athletes

        def spy_make(self):
            orig_make(self)
            for eid, p in self.pets.items():
                c = place_counts.setdefault(eid, [0])
                o = p.place

                def place(o=o, c=c):
                    c[0] += 1
                    o()
                p.place = place
        OS.Show._make_athletes = spy_make
        s, r, ticks = run_show(root, app, heat(ev, ents), 14, sec=30)
        OS.Prop.__init__ = orig_prop
        OS.Show._make_athletes = orig_make
        name = O.EV[ev]["kr"]
        chk("%s: 끝까지" % name, r is not None and not r["aborted"], r)
        chk("%s: 점수판 최고 기록 = 서버 기록" % name,
            all(s.best.get(e["entryId"]) == e["record"] for e in ents), (s.best, [e["record"] for e in ents]))
        chk("%s: 파울을 센다" % name, sum(s.fouls.values()) == 3, s.fouls)
        chk("%s: 기다리는 선수는 창을 거의 안 옮긴다 (선수마다 자기 차례 몫만)" % name,
            max(c[0] for c in place_counts.values()) <= ticks * 0.6 + 20, (place_counts, ticks))
        chk("%s: 소품 창이 치워진다" % name, all(not p.win.winfo_exists() for p in props_made) and not ov.extra)
        if ev == "pole":
            chk("장대: 내 차례 말", any("내 차례" in x for x in s.said), s.said)


# ---------------------------------------------------------------- 3. 응원 · 닫기
def cheer_part(root, ov, app):
    print("=== 응원 · 닫기 ===")
    ents = [entrant(i, (i % 6) + 1, 12.0 + i * 0.2, mine=(i == 0)) for i in range(3)]
    OS.time = FastTime(1)
    got = {}
    s = OS.Show(app, heat("sprint", ents), on_done=lambda sh, r: got.update(r=r))
    s.start()
    settle(root, 0.3)
    me = s.pets[ents[0]["entryId"]]
    me.on_press(None)
    chk("응원: 내 포켓몬을 누르면 하트 (기록은 그대로)", "♥" in s.said and ents[0]["record"] == 12.0)
    s.stop()
    settle(root, 0.2)
    OS.time = time
    chk("× 로 닫으면 aborted · 선수 창 없음", got.get("r", {}).get("aborted") and not ov.extra, got)


# ---------------------------------------------------------------- 4. 2시
def live_part(root, ov, app):
    print("=== 2시 ===")
    o = app.olympics
    sp = heat("sprint", [entrant(i, (i % 6) + 1, 12.0 + i * 0.3, mine=(i == 0)) for i in range(3)])
    sw = heat("swim", [entrant(i, (i % 6) + 1, 28.0 + i, mine=(i == 1)) for i in range(3)])
    app.api.live = {"day": O.DAYS[0], "dayNo": 1, "elapsed": 130,
                    "program": [{"event": "sprint", "showIn": -110}, {"event": "swim", "showIn": 0}],
                    "heats": [sp, sw]}
    played = []
    orig = OC.OlympicsController._play

    def spy(self, h, replay=False, ready=None, waited=0):
        if not waited:
            played.append((h["event"], replay))
        return orig(self, h, replay, ready, waited)
    OC.OlympicsController._play = spy
    OS.time = FastTime(30)
    o.note({"phase": "live", "nextDay": O.DAYS[0], "startsIn": -130, "endIn": 500})
    pump(root, lambda: played, 3)
    chk("켰을 때 경기 중이면 바로 받는다", ("live",) in app.api.calls)
    chk("지나간 100m 는 다시 보기로, 남은 수영은 중계", [p[0] for p in played] == ["swim"] and len(o.missed) == 1,
        (played, len(o.missed)))
    chk("지나간 경기 말", any("다시 볼 수 있어요" in x for x in o.said), o.said)
    chk("중계 중에는 풀숲이 쉰다", wild_ui.WildController._focusing(type("W", (), {"app": app})()))
    from poketdesktop.app import App
    chk("중계 중에는 업적 · 부화 · 보따리 알림을 미룬다 (focus_quiet)", App.focus_quiet(app))
    pump(root, lambda: not o.busy(), 8)
    OS.time = time
    chk("중계가 끝나면 풀숲 다시", app.wild.starts >= 1)
    chk("끝나면 알림을 다시 띄운다", not App.focus_quiet(app))
    # 같은 날 동기화가 또 와도 다시 받지 않는다
    n = len([c for c in app.api.calls if c == ("live",)])
    o.note({"phase": "live", "nextDay": O.DAYS[0], "startsIn": -200, "endIn": 400})
    settle(root, 0.2)
    chk("같은 날은 한 번만 받는다", len([c for c in app.api.calls if c == ("live",)]) == n)
    # 집중 중이면 건너뛴다
    o.clear()
    app.focus.on = True
    app.api.live = dict(app.api.live, program=[{"event": "sprint", "showIn": 0}, {"event": "swim", "showIn": 0}])
    played[:] = []
    o.note({"phase": "live", "nextDay": O.DAYS[0], "startsIn": -5, "endIn": 700})
    settle(root, 0.6)
    chk("집중 중이면 중계를 건너뛰고 한 번 알린다", not played and sum("집중하는 중이라" in x for x in o.said) == 1,
        (played, o.said[-2:]))
    app.focus.on = False
    OC.OlympicsController._play = orig
    o.clear()
    # 2시 전: 예약만
    calls = len(app.api.calls)
    o.note({"phase": "entry", "nextDay": O.DAYS[0], "startsIn": 3600, "endIn": 4300, "entries": 7, "dayNo": 1})
    chk("2시 전에는 예약만 (부르지 않는다)", len(app.api.calls) == calls and o._start_job is not None)
    o.clear()
    # 다시 보기
    app.api.heats[555] = sp
    res = {}
    OS.time = FastTime(30)
    o.replay(555, lambda h, err: res.update(h=h, err=err))
    chk("다시 보기를 누른 순간부터 바쁨 (각본을 받는 동안에도)", o.busy())
    pump(root, lambda: o.show is not None and o.show.alive, 3)
    chk("다시 보기: 조 각본을 받아 중계 (다시 보기 띠)", res.get("h") is sp and o.busy() and o.show.replay)
    res2 = {}
    o.replay(555, lambda h, err: res2.update(err=err))
    chk("중계 중에는 다른 다시 보기를 막는다", "중계하고" in (res2.get("err") or ""), res2)
    pump(root, lambda: not o.busy(), 8)
    settle(root, 0.3)
    OS.time = time
    chk("다시 보기 뒤 결과 카드", o.result_card is not None and o.result_card.win.winfo_exists())
    o.clear()
    chk("정리하면 결과 카드도 닫힌다", o.result_card is None)


# ---------------------------------------------------------------- 4b. 겹침 · 정리 (독립 검토)
def guard_part(root, ov, app):
    print("=== 겹침 · 정리 ===")
    o = app.olympics
    o.clear()
    h = heat("sprint", [entrant(i, (i % 6) + 1, 12.0 + i * 0.3, mine=(i == 0)) for i in range(3)])
    app.api.heats[556] = h
    shows, overlap = [], []
    real_start = OS.Show.start

    def spy_start(self):
        if any(x.alive for x in shows):
            overlap.append(self.ev)
        shows.append(self)
        return real_start(self)
    OS.Show.start = spy_start
    OS.time = FastTime(30)
    r1, r2 = {}, {}
    o.replay(556, lambda hh, err: r1.update(h=hh, err=err))
    o.replay(556, lambda hh, err: r2.update(h=hh, err=err))
    chk("다시 보기를 두 번 빨리 눌러도 두 번째는 막힌다", "중계하고" in (r2.get("err") or ""), r2)
    o._due(heat("swim", [entrant(i, (i % 6) + 1, 28.0 + i, mine=(i == 0)) for i in range(3)]))
    chk("다시 보기를 준비하는 사이 정해진 중계가 오면 줄을 선다", len(o.queue) == 1, len(o.queue))
    pump(root, lambda: len(shows) >= 2 and not o.busy(), 12)
    chk("중계가 둘 동시에 돌지 않는다", not overlap and len(shows) == 2, (overlap, len(shows)))
    OS.Show.start = real_start
    o.clear()
    # 준비 중에 오류가 나도 바탕화면이 갇히지 않는다
    real_setup = OS.Show._race_setup

    def boom(self):
        raise RuntimeError("시험")
    OS.Show._race_setup = boom
    o._ready_all = True
    o._play(h)
    settle(root, 0.3)
    OS.Show._race_setup = real_setup
    chk("중계 준비 중 오류: 포켓몬 · 이름표가 돌아온다", ov.only is None and ov._names_block == 0 and not ov.extra,
        (ov.only, ov._names_block, len(ov.extra)))
    chk("중계 준비 중 오류: 바쁨이 풀린다 (집중 · 대전이 안 막힌다)", not o.busy())
    # 로그아웃: 풀숲을 다시 켜지 않고, 카드 · 늦게 온 답을 버린다
    o.card = {"phase": "live"}
    o.replay(556)
    pump(root, lambda: o.show is not None and o.show.alive, 3)
    starts = app.wild.starts
    o.clear()
    settle(root, 0.2)
    chk("로그아웃 정리: 풀숲을 다시 켜지 않는다", app.wild.starts == starts, (starts, app.wild.starts))
    chk("로그아웃 정리: 트레이 줄이 사라진다", not o.on() and o.card is None)
    app.api.live = {"day": O.DAYS[0], "dayNo": 1, "elapsed": 5,
                    "program": [{"event": "sprint", "showIn": 0}], "heats": [h]}
    o.load_live(O.DAYS[0])
    o.clear()                                     # 받는 중에 로그아웃
    settle(root, 0.6)
    chk("로그아웃 뒤 늦게 온 경기 답은 버린다", o.live is None and not o.busy() and not o._jobs, (o.live, o._jobs))
    # 중계 중에 (다른 PC 에서 이어 받은) 집중이 시작되면 끝날 때 집중 포켓몬만 남긴다
    pid = next(iter(ov.pets))
    o.replay(556)
    pump(root, lambda: o.busy() and o.show is not None, 3)
    app.focus.on, app.focus.pet_id = True, pid
    pump(root, lambda: not o.busy(), 10)
    chk("중계 중에 집중이 시작됐으면 끝난 뒤 집중 포켓몬만 보인다", ov.only == pid, ov.only)
    app.focus.on, app.focus.pet_id = False, None
    ov.set_only(None)
    # 대전 상대를 찾는 중 · 대전을 불러오는 중에도 중계를 미룬다
    app._pvp_busy = True
    chk("대전 상대를 찾는 중이면 중계를 건너뛴다", o.blocked() == "pvp", o.blocked())
    app._pvp_busy = False
    app._match_loading = True
    chk("대전을 불러오는 중이어도", o.blocked() == "pvp", o.blocked())
    app._match_loading = False
    OS.time = time
    o.clear()


# ---------------------------------------------------------------- 5. 창
def state_sample():
    evs = []
    for e in O.EVENTS:
        evs.append({"key": e["key"], "kr": e["kr"], "short": e["short"], "statKr": e["statKr"], "kg0": e["kg0"],
                    "types": ["전기"], "abil": ["속보"], "dislike": [], "tries": e["tries"], "entry": None,
                    "best": None, "last": None})
    evs[0]["entry"] = {"id": 1, "event": "sprint", "day": O.DAYS[0], "tactic": "safe", "tacticKr": "안정",
                       "pokemon": {"id": 900, "name": "피카츄", "num": 25}}
    evs[0]["best"] = {"record": 11.84, "text": "11.84초", "rank": 12, "total": 120, "day": O.DAYS[0], "entryId": 7}
    evs[0]["last"] = {"day": O.DAYS[0], "entryId": 7, "text": "11.84초", "heat": 2, "rank": 12, "released": True,
                      "pokemon": {"id": 900, "name": "피카츄", "num": 25}}
    return {"phase": "entry", "days": list(O.DAYS), "at": "14:00", "nextDay": O.DAYS[1], "entryDay": O.DAYS[1],
            "dayNo": 2, "startsIn": 7200, "cheer": [{"type": "GHOST", "kr": "고스트"}, {"type": "FIRE", "kr": "불꽃"}],
            "fatigue": {"sprint": [{"species": "피카츄", "pen": 5}]}, "program": [], "events": evs,
            "tactics": [{"key": "safe", "kr": "안정"}, {"key": "bold", "kr": "승부수"}]}


def inside(win, widget):
    """widget 이 창 안에 다 보이나 (놓여 있고, 아래 끝이 창 아래 끝을 안 넘는다). 재서 본다."""
    try:
        win.update_idletasks()
        if not widget.winfo_ismapped():
            return False
        return widget.winfo_rooty() + widget.winfo_height() <= win.winfo_rooty() + win.winfo_height() + 1
    except Exception:                                       # noqa: BLE001
        return False


def many_cands(n):
    return {"event": "swim", "day": O.DAYS[1], "pokemon": [
        {"id": 2000 + i, "name": "포켓몬%d" % i, "species": "포켓몬%d" % i, "num": 7, "level": 10 + i, "shiny": False,
         "onDesktop": i < 3, "kg": 9.0, "types": ["물"], "stars": 1 + i % 5,
         "hints": ["물 특기", "체형 딱 맞음", "스피드 · 체력 좋음"], "away": False, "usedIn": None, "entered": False}
        for i in range(n)]}


def window_part(root, ov, app):
    print("=== 창 ===")
    app.api.state = state_sample()
    w = UO.open_olympics(app)
    pump(root, lambda: w.st is not None, 2)
    settle(root, 0.2)
    texts = []

    def walk(wd):
        for c in wd.winfo_children():
            try:
                t = c.cget("text")
                if t:
                    texts.append(t)
            except Exception:                               # noqa: BLE001
                pass
            walk(c)
    walk(w.win)
    blob = " | ".join(texts)
    chk("올림픽 창: 2일째 · 오후 2시 · 남은 때", "2일째" in blob and "오후 2시" in blob and "2시간" in blob
        and "14:00" not in blob, blob[:200])
    chk("올림픽 창: 응원 타입 · 지친 포켓몬", "고스트" in blob and "피카츄 −5%" in blob, blob[:300])
    chk("올림픽 창: 종목 7장", sum(1 for e in O.EVENTS if e["kr"] in blob) == 7)
    chk("올림픽 창: 내 신청 · 내 최고 · 다시 보기", "신청: 피카츄 · 안정" in blob and "주간 12위 / 120명" in blob
        and "다시 보기" in blob, blob[:400])
    chk("같은 창을 또 열면 그 창", UO.open_olympics(app) is w)
    chk("올림픽 창(종목 7장): 닫기 · 새로 고침 단추가 창 안에 보인다", inside(w.win, w.close_btn.holder),
        w.win.winfo_height())
    # 신청 창
    app.api.cands = {"event": "swim", "day": O.DAYS[1], "pokemon": [
        {"id": 901, "name": "꼬부기", "species": "꼬부기", "num": 7, "level": 12, "shiny": False, "onDesktop": True,
         "kg": 9.0, "types": ["물"], "stars": 5, "hints": ["물 특기", "오늘 응원 타입!"], "away": False, "usedIn": None,
         "entered": False},
        {"id": 900, "name": "피카츄", "species": "피카츄", "num": 25, "level": 30, "shiny": False, "onDesktop": True,
         "kg": 6.0, "types": ["전기"], "stars": 2, "hints": ["너무 가벼움"], "away": False, "usedIn": "sprint",
         "entered": False}]}
    e = UO.EntryWindow(app, "swim", w)
    pump(root, lambda: e.rows, 2)
    chk("신청 창: 후보 줄 · 별 · 표시", len(e.rows) == 2)
    # 포켓몬이 많아도 (박스 40마리) 작전 · 신청 단추가 창 안에 보인다 - 목록만 굴러간다 (11/06 사용자 제보: 단추가 없다)
    app.api.cands = many_cands(40)
    big = UO.EntryWindow(app, "swim", w)
    pump(root, lambda: len(big.rows) == 40, 3)
    settle(root, 0.3)
    big._choose(2005)
    settle(root, 0.3)
    chk("신청 창(40마리): 신청 단추가 창 안에 보인다", inside(big.win, big.go.holder),
        (big.win.winfo_height(), big.go.holder.winfo_ismapped()))
    chk("신청 창(40마리): 작전 단추도 보인다", inside(big.win, big.tac_btns["bold"]))
    chk("신청 창(40마리): 창은 화면 안 높이", big.win.winfo_height() <= U.h(700) + 4, big.win.winfo_height())
    big.close()
    app.api.cands = {"event": "swim", "day": O.DAYS[1], "pokemon": [
        {"id": 901, "name": "꼬부기", "species": "꼬부기", "num": 7, "level": 12, "shiny": False, "onDesktop": True,
         "kg": 9.0, "types": ["물"], "stars": 5, "hints": ["물 특기", "오늘 응원 타입!"], "away": False, "usedIn": None,
         "entered": False},
        {"id": 900, "name": "피카츄", "species": "피카츄", "num": 25, "level": 30, "shiny": False, "onDesktop": True,
         "kg": 6.0, "types": ["전기"], "stars": 2, "hints": ["너무 가벼움"], "away": False, "usedIn": "sprint",
         "entered": False}]}
    chk("다른 종목에 나가는 포켓몬은 눌러도 안 골라진다 (줄에 누르기가 없다)",
        not e.rows[900].bind("<Button-1>") and e.rows[901].bind("<Button-1>"))
    e._choose(901)
    e._tac("bold")
    e._go()
    pump(root, lambda: not e.alive(), 2)
    chk("신청: 고른 포켓몬 · 작전으로 보낸다", ("enter", "swim", 901, "bold") in app.api.calls, app.api.calls[-3:])
    chk("신청 뒤 창이 닫히고 동기화", not e.alive() and app.syncs >= 1)
    # 순위표
    app.api.board = {"event": "sprint", "day": None, "total": 120, "hidden": False,
                     "rows": [{"rank": 1, "user": "가", "mine": False, "entryId": 5, "day": O.DAYS[0],
                               "pokemon": {"name": "라이츄"}, "record": 11.2, "text": "11.20초"}],
                     "me": {"rank": 12, "user": "나", "mine": True, "entryId": 7, "day": O.DAYS[0],
                            "pokemon": {"name": "피카츄"}, "record": 11.84, "text": "11.84초"}}
    rows50 = [{"rank": i + 1, "user": "사람%d" % i, "mine": False, "entryId": 5 + i, "day": O.DAYS[0],
               "pokemon": {"name": "라이츄"}, "record": 11.2 + i * 0.05, "text": "%.2f초" % (11.2 + i * 0.05)}
              for i in range(50)]
    app.api.board = {"event": "sprint", "day": None, "total": 120, "hidden": False, "rows": rows50, "me": None}
    b50 = UO.BoardWindow(app, "sprint")
    pump(root, lambda: len(b50.inner.winfo_children()) == 50, 3)
    settle(root, 0.3)
    chk("순위표(50줄): 닫기 단추가 창 안에 보인다", inside(b50.win, b50.close_btn.holder), b50.win.winfo_height())
    b50.close()
    app.api.board = {"event": "sprint", "day": None, "total": 120, "hidden": False,
                     "rows": [{"rank": 1, "user": "가", "mine": False, "entryId": 5, "day": O.DAYS[0],
                               "pokemon": {"name": "라이츄"}, "record": 11.2, "text": "11.20초"}],
                     "me": {"rank": 12, "user": "나", "mine": True, "entryId": 7, "day": O.DAYS[0],
                            "pokemon": {"name": "피카츄"}, "record": 11.84, "text": "11.84초"}}
    b = UO.BoardWindow(app, "sprint")
    pump(root, lambda: b.inner.winfo_children(), 2)
    chk("순위표: 1위 줄 + ⋯ + 내 줄", len(b.inner.winfo_children()) == 3, len(b.inner.winfo_children()))
    app.api.board = {"event": "sprint", "day": O.DAYS[0], "rows": [], "me": None, "total": 0, "hidden": True}
    b._tab(O.DAYS[0])
    pump(root, lambda: "공개" in b.note.cget("text"), 2)
    chk("순위표: 공개 전 안내", "공개되지" in b.note.cget("text"), b.note.cget("text"))
    b.close()
    w.close()
    # 오른쪽 클릭 줄
    app.olympics.card = {"phase": "entry"}
    pet = next(iter(ov.pets.values()))
    row = UO.menu_row(app, pet)
    chk("오른쪽 클릭: '올림픽에 출전...'", row and row["text"] == "올림픽에 출전...", row)
    app.olympics.card = {"phase": "closed"}
    chk("기간 밖이면 줄이 없다", UO.menu_row(app, pet) is None)
    app.olympics.card = None
    # 리본 글
    chk("관리 창 리본: 가장 귀한 것과 개수",
        ui_box.ribbon_text({"ribbons": [{"kind": "oly_join", "name": "올림픽 참가 리본"},
                                        {"kind": "oly_gold", "name": "100m 금메달 리본"}]}) == "리본 2개 · 100m 금메달 리본")
    chk("리본 없으면 빈 글", ui_box.ribbon_text({}) == "")


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-500:])
    root.report_callback_exception = on_err
    colors = [(230, 110, 40, 255), (80, 140, 220, 255), (60, 160, 90, 255), (200, 80, 160, 255),
              (220, 200, 60, 255), (120, 120, 200, 255)]
    for n in range(1, 7):
        SHEETS[n] = make_sheet("s%d.png" % n, 32, colors[n - 1])
        FILES[n] = make_dot("d%d.png" % n, colors[n - 1])
    poses = dict(((n, a), make_sheet("p%d_%s.png" % (n, a), 32, (240, 240, 240, 255)))
                 for n in (1, 2, 3) for a in ("Idle", "Hop", "Hurt"))
    sprite_cache.ensure = lambda api, num, shiny=False: FILES.get(num)
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (
        SHEETS.get(num) if name == "Walk" and SHEETS.get(num) else poses.get((num, name), (None, None)))
    settings = dict(config.DEFAULTS)
    settings["megaWalk"] = []
    settings["showNames"] = True
    ov = overlay.Overlay(root, settings)
    ov.paths.update(dict(((n, False), p) for n, p in FILES.items()))
    ov.walks.update(dict(SHEETS))
    for (n, a), v in poses.items():
        ov.sheets[walk_cache.sheet_key(n, a, T.skin({}))] = v
    ov.sync([mon(1, 4 if 4 in SHEETS else 1, 0, "파이리"), mon(2, 2, 1, "꼬부기")], {}, {})
    ov.start()
    settle(root, 0.3)
    app = MiniApp(root, ov)
    try:
        race_part(root, ov, app)
        field_part(root, ov, app)
        cheer_part(root, ov, app)
        live_part(root, ov, app)
        guard_part(root, ov, app)
        window_part(root, ov, app)
    finally:
        app.olympics.clear()
        ov.stop()
        ov.clear()
        settle(root, 0.2)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
