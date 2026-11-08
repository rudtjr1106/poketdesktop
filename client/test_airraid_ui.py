# -*- coding: utf-8 -*-
"""공습 (2.3.0) 화면 검사 — 그날 시각 예약 · 막힘 · 낙하산 · 동시 전투 · 이긴 쪽이 다음 상대 · 정리.

    python client/test_airraid_ui.py
    python client/run_as_windows.py client/test_airraid_ui.py

**진짜 Overlay 와 도트 창을 띄운다.** 각본은 진짜 계산(common/airraid.py)으로 만든다 - 서버 응답과 같은 꼴
(server/app/airraid.start: events · ids · result · reward · exp). 중계 간격은 빠르게 (airraid_show.SPEED).
"""
import json
import os
import random
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-airraid-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from common import airraid as CR                            # noqa: E402
from common import pokelogic as P                           # noqa: E402
from common import tint as T                                # noqa: E402
from poketdesktop import airraid as RC                      # noqa: E402
from poketdesktop import airraid_art as ART                 # noqa: E402
from poketdesktop import airraid_show as RS                 # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import overlay, sprite_cache, walk_cache  # noqa: E402
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


def load_dex():
    with open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8") as f:
        return P.Pokedex(json.load(f))


def make_view(dex, mine_keys, lv, n_foe=None, seed=5, ids=(1, 2)):
    rng = random.Random(seed)
    mine = [P.make_pokemon(dex.get(k), lv, rng, force_shiny=False) for k in mine_keys]
    foes = CR.roll_raiders(dex, [m["level"] for m in mine], rng)
    if n_foe:
        foes = foes[:n_foe]
    for f in foes:                                          # 가짜 도트 번호 (1~6) - 진짜 도트는 저장소에 없다
        f["num"] = 1 + (hash(f["species"]) % 6)
    out = CR.AirRaid(dex, mine, foes, seed=seed).run()
    for f in out["events"][0]["foe"]:
        f["num"] = 1 + (hash(f["species"] or "") % 6)
    for f in out["events"][0]["me"]:
        f["num"] = 1
    return {"day": "2026-11-12", "result": out["result"], "events": out["events"], "ids": list(ids)[:len(mine)],
            "reward": {"balls": 3, "money": 5000} if out["result"] == "win" else None, "exp": [], "already": False}


class FakeApi(object):
    def __init__(self):
        self.calls = []
        self.view = None
        self.err = None

    def airraid_start(self, hour=-1):
        self.calls.append(("start", hour))
        if self.err:
            raise self.err
        return self.view

    def airraid_state(self):
        self.calls.append(("state",))
        return {"day": "2026-11-12", "dueIn": 0, "done": False}


class FakeFocus(object):
    def __init__(self):
        self.on = False

    def active(self):
        return self.on


class FakeWild(object):
    def __init__(self):
        self.stops = self.starts = 0
        self.throwing = False
        self.pet = None

    def stop(self):
        self.stops += 1

    def start(self):
        self.starts += 1


class MiniApp(object):
    def __init__(self, root, ov, dex):
        self.root, self.overlay, self.dex = root, ov, dex
        self.settings = ov.settings
        self.api = FakeApi()
        self.focus = FakeFocus()
        self.wild = FakeWild()
        self.battle = self.arena = None
        self.visit = None
        self.olympics = None
        self.syncs = 0
        self.notes = []
        self.airraid = RC.AirRaidController(self)

    def request_sync(self):
        self.syncs += 1

    def notify(self, m):
        self.notes.append(m)

    def want_learn(self, *a):
        pass


class Err409(Exception):
    status = 409


# ---------------------------------------------------------------- 1. 낙하산 그림
def art_part():
    print("=== 낙하산 그림 ===")
    im = ART.parachute(0)
    chk("낙하산: 둥근 천 + 줄 (아래 가운데로 모인다)", im.width >= 30 and im.height >= 24
        and im.getpixel((im.width // 2, im.height - 1))[3] > 0 and im.getpixel((0, im.height - 1))[3] == 0,
        im.size)
    chk("색이 몇 가지 (공습 포켓몬마다 다르게)", len(set(ART.parachute(i).tobytes() for i in range(4))) >= 3)
    fold = ART.folding(0)
    chk("접히는 그림: 점점 낮아진다", len(fold) >= 3 and fold[-1].getbbox() is not None
        and (fold[-1].getbbox()[3] - fold[-1].getbbox()[1]) < (fold[0].getbbox()[3] - fold[0].getbbox()[1]),
        [f.getbbox() for f in fold])


# ---------------------------------------------------------------- 2. 장면
def show_part(root, ov, app, dex):
    print("=== 장면 ===")
    view = make_view(dex, ["MEWTWO", "MEWTWO"], 70, seed=5)
    nfoe = len(view["events"][0]["foe"])
    homes = dict((pid, (p.x, p.y)) for pid, p in ov.pets.items())
    RS.SPEED = 6.0
    done = []
    show = RS.AirRaidShow(app, view, on_done=lambda: done.append(1))
    show.start()
    chk("시작하면 바탕화면을 빌린다 (locked)", ov.locked)
    chk("공습은 그만 보기(×) 판이 없다 - 중간에 취소할 수 없다 (사용자 11/08)", show.stop_plate is None
        and not hasattr(show, "stop"), show.stop_plate)
    chutes = []
    pump(root, lambda: (chutes.append(sum(1 for r in show.raiders if r.chute is not None)) or
                        all(r.pet is not None for r in show.raiders)), 6)
    ground = min(p.y for p in ov.pets.values())
    chk("공습 포켓몬 %d마리가 화면 위 끝에서 나타난다" % nfoe, len(show.raiders) == nfoe
        and all(r.pet is not None and r.top < ground for r in show.raiders),
        [(getattr(r, "top", None), ground) for r in show.raiders])
    chk("  내려오는 동안 낙하산 창이 붙어 있다 (여럿이 같이 내려온다)", max(chutes or [0]) >= 2, max(chutes or [0]))
    pump(root, lambda: show.phase == "fight", 10)
    chk("땅에 닿으면 낙하산을 접어 치운다", all(r.chute is None for r in show.raiders), [r.chute for r in show.raiders])
    first = [l for l in show.lanes.values() if l.active]
    chk("처음엔 내 포켓몬마다 한 마리씩 동시에 (짝 둘)", len(first) == 2, len(first))
    feet = [(l.me.x + l.me.fw / 2.0, l.foe.x + l.foe.fw / 2.0) for l in first]
    chk("  짝마다 마주 선다 (발 사이 60~200px)", all(60 <= abs(a - b) <= 200 for a, b in feet), feet)
    mx = [0]

    def busy():
        mx[0] = max(mx[0], sum(1 for l in show.lanes.values() if l.playing))
        return show.phase in ("result", "done")
    pump(root, busy, 40)
    chk("두 짝이 같은 턴에 같이 싸운다 (동시에 재생 중인 짝 2)", mx[0] >= 2, mx[0])
    chk("결과까지 간다", show.phase in ("result", "done"), show.phase)
    pairs = [e for e in view["events"] if e["t"] == "pair"]
    chk("짝을 다 지났다 (이긴 쪽이 다음 상대에게 걸어갔다)", show.pairs_done == len(pairs), (show.pairs_done, len(pairs)))
    chk("  다음 상대에게 간 자리가 다른 도트와 겹치지 않는다 (발 사이 40px 넘게)",
        all(g > 40 for g in show.gaps), show.gaps)
    chk("  다음 짝은 늘 남은 적이 우리 포켓몬 쪽으로 걸어온다 (사용자 11/08 - 우리 포켓몬이 잡으러 가지 않는다)",
        show.walkers and all(w == "foe" for w in show.walkers), show.walkers)
    pump(root, lambda: done, 15)
    chk("끝나면 on_done", done == [1])
    chk("정리: 공습 포켓몬 창 · 낙하산 · 레이어가 없다 · 바탕화면을 돌려준다", not show.raiders and show.layer is None
        and not ov.locked and all(r.pet not in ov.extra for r in []), (len(show.raiders), show.layer, ov.locked))
    chk("  내 포켓몬은 제자리 · 다시 돌아다닌다", all(abs(ov.pets[k].x - homes[k][0]) < 2 and not ov.pets[k].battling
                                           for k in homes), [(ov.pets[k].x, homes[k][0]) for k in homes])
    # 로그아웃(정리) · 중간에 터짐
    show2 = RS.AirRaidShow(app, make_view(dex, ["PIKACHU", "BULBASAUR"], 30, seed=7), on_done=lambda: None)
    show2.start()
    pump(root, lambda: show2.phase == "fight", 10)
    show2.cleanup()
    settle(root, 0.2)
    chk("로그아웃 정리: 바로 원래대로", show2.closed and not show2.raiders and not ov.locked
        and all(not p.battling for p in ov.pets.values()))
    show3 = RS.AirRaidShow(app, make_view(dex, ["PIKACHU"], 30, seed=9, ids=(1,)), on_done=lambda: None)
    real = RS.Lane.render
    RS.Lane.render = lambda self, ev, d: 1 / 0
    try:
        show3.start()
        pump(root, lambda: show3.closed, 20)
    finally:
        RS.Lane.render = real
    chk("재생 중 예외가 나도 정리된다", show3.closed and not ov.locked and not show3.raiders)
    # 바탕화면에 없는 포켓몬(명단이 바뀜) - 대신 세운 도트로 싸우고 치운다
    view4 = make_view(dex, ["PIKACHU", "EEVEE"], 30, seed=11, ids=(1, 999))
    show4 = RS.AirRaidShow(app, view4, on_done=lambda: None)
    show4.start()
    pump(root, lambda: show4.phase == "fight", 10)
    chk("바탕화면에 없는 포켓몬은 대신 세운다", any(getattr(l.me, "stand_in", False) for l in show4.lanes.values())
        or len(show4.mine) == 2, [type(p).__name__ for p in show4.mine])
    show4.cleanup()
    settle(root, 0.2)
    chk("  대신 세운 도트도 치운다", not [p for p in ov.extra if getattr(p, "stand_in", False)] and not ov.locked)
    # 대신 세울 도트도 못 만들면 그 자리를 비워 둔다 - 번호가 밀리면 한 도트가 두 짝에서 같이 움직인다 (독립 검토)
    real_si = RS.AirRaidShow._stand_in
    RS.AirRaidShow._stand_in = lambda self, ov_, info, i: None
    try:
        show5 = RS.AirRaidShow(app, make_view(dex, ["PIKACHU", "EEVEE"], 30, seed=11, ids=(1, 999)), on_done=lambda: None)
        show5.start()
        pump(root, lambda: show5.phase == "fight", 10)
        chk("대신 세우기 실패: 그 자리는 비우고(None) 다른 짝의 번호는 그대로", len(show5.mine) == 2
            and show5.mine[1] is None and show5.mine[0] is ov.pets[1], [type(p).__name__ for p in show5.mine])
        pump(root, lambda: show5.closed, 30)
        chk("  끝까지 가고 정리된다", show5.closed and not ov.locked)
    finally:
        RS.AirRaidShow._stand_in = real_si
    # 숨는 기술(공중날기)로 숨은 채 이긴 도트는 다음 짝에서 다시 보인다
    show6 = RS.AirRaidShow(app, make_view(dex, ["MEWTWO", "MEWTWO"], 70, seed=5), on_done=lambda: None)
    show6.start()
    pump(root, lambda: show6.phase == "fight", 10)
    p0 = show6.mine[0]
    p0.win.withdraw()
    show6._make_lane({"d": 99, "mi": 0, "fi": len(show6.raiders) - 1, "me": {"hp": 1, "maxhp": 1},
                      "foe": {"hp": 1, "maxhp": 1}})
    settle(root, 0.1)
    chk("숨은 채 이긴 도트는 새 짝에서 다시 보인다", p0.win.state() == "normal", p0.win.state())
    show6.cleanup()
    settle(root, 0.2)
    # 멈춤 감시: 기술 연출이 끝을 안 알려도 정해진 때가 지나면 정리 (바쁨에 갇혀 풀숲 · 집중 · 대전이 막히지 않게)
    real_play, real_stall = RS.Lane.play, RS.STALL_MS
    RS.Lane.play = lambda self, events, done: setattr(self, "playing", True)
    RS.STALL_MS = 1500
    try:
        show7 = RS.AirRaidShow(app, make_view(dex, ["PIKACHU"], 30, seed=9, ids=(1,)), on_done=lambda: None)
        show7.start()
        pump(root, lambda: show7.closed, 20)
    finally:
        RS.Lane.play, RS.STALL_MS = real_play, real_stall
    chk("멈춤 감시: 한 짝이 영영 안 끝나 진행이 멈추면 정리한다", show7.closed and not ov.locked)
    chk("  멈춤 감시는 전체 길이가 아니라 '진행이 멎은 시간' 으로 본다 (긴 공습 · 느린 PC 를 자르지 않게) - 20초",
        RS.STALL_MS >= 20000, RS.STALL_MS)
    # 돌아다닐 영역이 화면 전체면 기다리는 공습 포켓몬 자리가 화면 밖이다 - 그래도 한 점에 겹치지 않게
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    real_area = ov.area
    ov.area = lambda: (0, 40, sw, sh - 60)
    try:
        show8 = RS.AirRaidShow(app, make_view(dex, ["PIKACHU"], 30, seed=13, ids=(1,)), on_done=lambda: None)
        show8.start()
        lands = sorted(r.land for r in show8.raiders)
        close = [(a, b) for i, a in enumerate(lands) for b in lands[i + 1:]
                 if abs(a[0] - b[0]) < 50 and abs(a[1] - b[1]) < 40]
        chk("영역이 화면 전체여도 공습 포켓몬이 한 점에 겹쳐 내리지 않는다", not close, lands)
        show8.cleanup()
        settle(root, 0.2)
    finally:
        ov.area = real_area


# ---------------------------------------------------------------- 3. 예약 · 막힘
def controller_part(root, ov, app, dex):
    print("=== 예약 ===")
    c = app.airraid
    RS.SPEED = 20.0
    c.note({"day": "2026-11-12", "dueIn": 3600, "done": False})
    chk("시각 전: 그 시각 + 30~120초 뒤로 예약", c.job is not None and 3600 + 30 <= c.wait <= 3600 + 120, c.wait)
    c.note({"day": "2026-11-12", "dueIn": 3500, "done": False})
    chk("  다시 받아도 한 번만 예약", c.wait <= 3600 + 120 and c.jobs_made == 1, c.jobs_made)
    c.note({"day": "2026-11-12", "dueIn": 0, "done": True})
    chk("오늘 했으면 예약을 지운다", c.job is None)
    n0 = len(app.notes)
    c.note({"day": "2026-11-12", "dueIn": 0, "done": True, "result": "win"})
    c.note({"day": "2026-11-12", "dueIn": 0, "done": True, "result": "win"})
    chk("다른 PC · 다시 켬: 오늘 공습 결과를 한 번 알린다 (설계 '같은 날 다시 켜면 결과만')",
        len(app.notes) == n0 + 1 and "공습" in app.notes[-1], app.notes[n0:])
    c.note({"day": "2026-11-20", "dueIn": 3600, "done": False})
    c.note({"day": "2026-11-20", "dueIn": 100, "done": False})
    chk("같은 날 시각이 크게 당겨지면(잠자기 뒤) 다시 맞춘다", c.wait < 300, c.wait)
    c.note({"day": "2026-11-21", "dueIn": 0, "done": False, "party": 0})
    chk("바탕화면 파티가 0이면 예약하지 않는다 (10분마다 서버를 두드리지 않게)", c.job is None)
    ov.pets[1].evolving = True
    chk("진화 연출 중이면 미룬다", c.blocked() == "evolve", c.blocked())
    ov.pets[1].evolving = False
    RC.DELAY = (0.05, 0.1)                       # 아래는 빨리
    app.api.view = make_view(dex, ["MEWTWO"], 70, seed=3, ids=(1,))
    app.focus.on = True
    c.note({"day": "2026-11-13", "dueIn": 0, "done": False})
    pump(root, lambda: c.tries >= 1, 3)
    chk("집중 중이면 미룬다 (서버를 안 부른다)", not app.api.calls and c.blocked() == "focus", (app.api.calls, c.blocked()))
    app.focus.on = False
    app.wild.pet = object()
    chk("야생 포켓몬이 나와 있으면(던지는 중 · 누르기 전) 미룬다", c.blocked() == "wild", c.blocked())
    app.wild.pet = None
    w0 = (app.wild.stops, app.wild.starts)
    c.fire()
    pump(root, lambda: c.show is not None, 3)
    chk("막힘이 풀리면 서버에 시작을 부르고 바탕화면에서 튼다", app.api.calls[-1][0] == "start" and c.show is not None)
    chk("  틀기 전에 풀숲을 멈춘다 (공습 중 만료 · 폴링이 예약을 잃지 않게 - 독립 검토 Critical)",
        app.wild.stops == w0[0] + 1, (app.wild.stops, w0))
    chk("  재생하는 동안은 바쁨 (풀숲 · 대전 · 올림픽 중계가 쉰다)", c.busy())
    pump(root, lambda: not c.busy(), 40)
    chk("끝나면 결과 알림 (막았다 · 볼 · 돈)", any("공습" in n and ("막았" in n or "밀렸" in n) for n in app.notes), app.notes[-2:])
    chk("  동기화 한 번 (경험치 · 볼 · 돈)", app.syncs >= 1)
    chk("  끝나면 풀숲을 다시 켠다", app.wild.starts == w0[1] + 1, (app.wild.starts, w0))
    # 이미 한 판 (다른 PC · 다시 켬) - 틀지 않고 알리기만
    app.api.view = dict(make_view(dex, ["MEWTWO"], 70, seed=3, ids=(1,)), already=True)
    n0 = len(app.notes)
    c.note({"day": "2026-11-14", "dueIn": 0, "done": False})
    c.fire()
    pump(root, lambda: len(app.notes) > n0, 3)
    chk("이미 한 판이면 틀지 않고 알리기만", c.show is None and len(app.notes) > n0, app.notes[n0:])
    # 서버가 '아직' / '포켓몬이 없어요' - 나중에 다시
    app.api.err = Err409("아직 오늘 공습 시각이 아니에요.")
    c.note({"day": "2026-11-15", "dueIn": 0, "done": False})
    c.fire()
    pump(root, lambda: c.job is not None and c.wait >= 60, 3)
    chk("서버가 거절하면 나중에 다시 (60초 넘게)", c.job is not None and c.wait >= 60, c.wait)
    app.api.err = None
    # 이상한 답(목록)이 와도 바쁨에 갇히지 않는다
    app.api.view = ["이상한 답"]
    c.note({"day": "2026-11-16", "dueIn": 0, "done": False})
    c.fire()
    pump(root, lambda: not c._prep and c.job is not None, 3)
    chk("이상한 답에도 _prep 이 풀리고 나중에 다시", not c._prep and c.job is not None, (c._prep, c.job))
    # 로그아웃: 서버 답이 오기 전에 치우면 늦게 온 답이 공습을 틀지 않는다
    app.api.view = make_view(dex, ["MEWTWO"], 70, seed=3, ids=(1,))
    c.note({"day": "2026-11-17", "dueIn": 0, "done": False})
    c.fire()
    c.clear()
    settle(root, 1.0)
    chk("로그아웃 뒤 늦게 온 답은 버린다 (장면 X · 바탕화면 잠금 X)", c.show is None and not ov.locked, (c.show, ov.locked))
    # 경험치 알림 묶기: 한 포켓몬의 레벨업 · 배운 기술은 한 줄로
    merged = RC.merge_grants([
        {"id": 1, "name": "피카츄", "leveledUp": True, "level": 31, "learned": ["전기쇼크"], "shared": False},
        {"id": 2, "name": "이브이", "leveledUp": False, "level": 20, "learned": [], "shared": True},
        {"id": 1, "name": "피카츄", "leveledUp": True, "level": 32, "learned": ["번개"], "shared": True},
        {"id": 1, "name": "피카츄", "leveledUp": False, "level": 32, "learned": [], "pending": ["10만볼트"],
         "pendingIds": ["THUNDERBOLT"], "shared": True}])
    pk = [g for g in merged if g["id"] == 1]
    chk("경험치 알림: 포켓몬마다 하나 (마지막 레벨 · 배운 기술 합침 · 배우려는 기술)", len(pk) == 1 and pk[0]["level"] == 32
        and pk[0]["leveledUp"] and pk[0]["learned"] == ["전기쇼크", "번개"] and pk[0]["pendingIds"] == ["THUNDERBOLT"],
        merged)
    # 공습 중 놀러 가기(손님)는 못 한다
    from poketdesktop import visit as VI
    import types as _t
    c._prep = True
    vapp = _t.SimpleNamespace(battle=None, arena=None, wild=app.wild, _pvp_busy=False, friendly=None, airraid=c)
    chk("공습 중엔 놀러 가기를 받지 않는다", VI.Visit.busy(_t.SimpleNamespace(app=vapp)) == "raid"
        and "공습" in VI.CANT_GO["raid"] and "공습" in VI.GAVE_UP["raid"])
    c._prep = False
    # 올림픽 중계 시간(2시 3분 전 ~ 그날 중계 끝)에는 공습을 열지 않는다 - 라운드 사이에 끼면 다음 라운드 중계와 겹친다
    from poketdesktop import olympics as OC
    o = OC.OlympicsController(app)
    app.olympics = o
    o.note({"phase": "entry", "nextDay": "2026-11-16", "startsIn": 120, "endIn": 900})
    chk("올림픽 2시 2분 전: 공습을 미룬다", c.blocked() == "olympics" and o.on_air(), c.blocked())
    o.note({"phase": "entry", "nextDay": "2026-11-16", "startsIn": -300, "endIn": 600})
    chk("  중계 시간 한가운데(라운드 사이)도", c.blocked() == "olympics")
    o.note({"phase": "entry", "nextDay": "2026-11-16", "startsIn": 7200, "endIn": 8100})
    chk("  2시간 전이면 연다", c.blocked() is None, c.blocked())
    o._cancel_all() if hasattr(o, "_cancel_all") else None
    app.olympics = None
    # 공습을 막는 동안: 풀숲 · 집중 알림 · 대전 · 올림픽 중계가 쉰다
    import types
    from poketdesktop import app as A
    from poketdesktop import wild_ui
    c._prep = True
    dummy = types.SimpleNamespace(focus=None, olympics=None, airraid=c)
    chk("공습 중: 앱이 바쁨으로 본다 (대전 걸기 · 보기를 막는 _raid_on) · 알림을 미룬다(focus_quiet)",
        A._raid_on(dummy) and A.App.focus_quiet(dummy))
    chk("  풀숲이 쉰다", wild_ui.WildController._focusing(types.SimpleNamespace(app=dummy)))
    o2 = OC.OlympicsController(app)
    chk("  올림픽 중계는 '공습을 막는 중이라' 로 건너뛴다", o2.blocked() == "raid" and "공습" in OC.SKIP_MSG["raid"],
        o2.blocked())
    from poketdesktop import focus_timer
    fc = focus_timer.FocusController(app)
    said = []
    fc.start(1, "atk", done=lambda r, err: said.append(err))
    chk("  집중 시작을 받지 않는다", said and "공습" in (said[0] or ""), said)
    c._prep = False
    chk("  끝나면 다시 (바쁨 아님)", not A._raid_on(dummy) and o2.blocked() is None)
    c.clear()
    chk("로그아웃: 예약 · 장면을 치운다", c.job is None and c.show is None)


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-600:])
    root.report_callback_exception = on_err
    colors = [(230, 110, 40, 255), (80, 140, 220, 255), (60, 160, 90, 255), (200, 80, 160, 255),
              (220, 200, 60, 255), (120, 120, 200, 255)]
    for n in range(1, 7):
        SHEETS[n] = make_sheet("s%d.png" % n, 32, colors[n - 1])
        FILES[n] = make_dot("d%d.png" % n, colors[n - 1])
    sprite_cache.ensure = lambda api, num, shiny=False: FILES.get(num)
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (
        SHEETS.get(num) if name == "Walk" and SHEETS.get(num) else (None, None))
    settings = dict(config.DEFAULTS)
    settings["megaWalk"] = []
    settings["showNames"] = True
    ov = overlay.Overlay(root, settings)
    ov.paths.update(dict(((n, False), p) for n, p in FILES.items()))
    ov.walks.update(dict(SHEETS))
    ov.sync([mon(1, 1, 0, "피카츄"), mon(2, 2, 1, "이상해씨")], {}, {})
    ov.start()
    settle(root, 0.3)
    dex = load_dex()
    app = MiniApp(root, ov, dex)
    try:
        art_part()
        show_part(root, ov, app, dex)
        controller_part(root, ov, app, dex)
    finally:
        app.airraid.clear()
        ov.stop()
        ov.clear()
        settle(root, 0.2)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
