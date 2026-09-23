# -*- coding: utf-8 -*-
"""레이드 화면 검사 — 탭·배틀 창·바탕화면 기둥.

    python client/test_raid_ui.py

**창을 진짜로 띄운다.** 화면이 있어야 돌아간다(CI 의 맥·윈도우 잡).
서버는 안 띄운다 - 가짜 api 가 서버와 **같은 엔진**(common/raid_battle)을
이 프로세스에서 돌리고, 응답 모양은 server/app/raid.py 의 public() 과 같다.

## 무엇을 못 박나

  1. 배틀 창이 화면(독·작업표시줄을 뺀 자리) 안에 들어온다.
  2. 공용 체력바·보호막 바·참가자 칸이 캔버스 안에 있다 (여섯 명까지).
  3. 눌린 위젯이 없다 - 글자가 잘리면 안 된다.
  4. 기술을 누르면 서버로 가고, **두 번 안 간다** (다른 사람을 기다리는 중).
  5. 라운드가 넘어가면 연출을 틀고 체력바가 서버 값으로 맞는다.
  6. 보호막이 서면 바가 보이고, 깨지면 사라진다.
  7. 끝나면 결과 칸이 뜨고 '닫기' 가 안 눌려 있다. 결과를 봤다고 서버에 알린다.
  8. 레이드 탭: 공개 전에는 보스 이름이 "???", 공개되면 이름·타입이 뜬다.
  9. 로비 칸이 인원수만큼 뜨고 방 코드가 보인다.
 10. 바탕화면 기둥이 **활동 영역 윗변**에 선다 (화면 꼭대기가 아니다).
"""
import io
import json
import os
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-raid"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import random                                               # noqa: E402
import tkinter as tk                                        # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

from common import pokelogic as P                           # noqa: E402
from common import raid_battle as RB                        # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import raid_fx                            # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_raid                            # noqa: E402
from poketdesktop import ui_raid_battle as RUI              # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0
DATA = os.path.join(ROOT, "server", "data")
SESSION = "2026-09-22T11"


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def fake_sprite():
    im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((20, 14, 76, 90), fill=(90, 160, 230, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def mon(dex, species, level, moves, mid):
    return {"id": mid, "species": species, "level": level, "nickname": None,
            "nature": "HARDY", "ability": None, "gender": "M", "shiny": False,
            "held": None, "moves": list(moves),
            "ivs": dict((s, 31) for s in P.STATS),
            "evs": dict((s, 0) for s in P.STATS), "happiness": 70}


class FakeApi(object):
    """서버 대신. 응답 모양은 server/app/raid.py 의 public() 과 같다."""

    def __init__(self, dex, n=4, revealed=True, host=True):
        self.dex = dex
        self.png = fake_sprite()
        self.calls = []
        self.seen = 0
        self.revealed = revealed
        self.n = n
        self.host = host
        self.state = "lobby"
        self.code = "AB12CD"
        self.rb = None
        self.round = 0
        self.events = []

    # ---- 일정 ----
    def _card(self):
        out = {"session": SESSION, "at": "2026-09-22T11:00:00", "leftSec": 240,
               "revealed": self.revealed}
        if self.revealed:
            out.update({"species": "MEWTWO", "num": 150, "kr": "뮤츠",
                        "types": ["에스퍼"], "typeIds": ["PSYCHIC"],
                        "kind": "legendary", "level": 60})
        return out

    def raid(self):
        self.calls.append("raid")
        return {"on": True, "start": "2026-09-22", "end": "2026-10-06",
                "hours": [11, 21], "next": self._card(), "open": True,
                "openSec": 300, "graceSec": 120, "minPlayers": 3, "maxPlayers": 6,
                "minParty": 2, "teamLevel": 50, "bossLevel": 60, "bossEv": 96,
                "revealSec": 3600, "rounds": 15,
                "roundSec": 25, "eggChance": 0.7,
                "upcoming": [self._card() for _ in range(6)],
                "room": self.room() if self.rb or self.state == "lobby" else None,
                "playedToday": False, "party": 4, "unseen": 0}

    def raid_history(self, limit=10):
        return {"raids": [{"session": SESSION, "boss": "MEWTWO", "num": 150,
                           "kr": "뮤츠", "result": "won", "damage": 1234,
                           "prize": 6000, "egg": True}]}

    # ---- 방 ----
    def room(self):
        out = {"id": 1, "session": SESSION, "code": self.code, "host": 1,
               "state": self.state, "result": self.rb.result if self.rb else None,
               "rev": 1, "round": self.round, "boss": self._card(),
               "min": 3, "max": 6, "startsAt": "2026-09-22T11:00:00",
               "startsIn": 240,
               "members": [{"uid": i + 1, "name": "참가자%d" % (i + 1), "pos": i,
                            "left": False, "damage": 0, "prize": 0, "egg": False}
                           for i in range(self.n)],
               "count": self.n}
        enough = self.n >= 3
        out["isHost"] = self.host
        out["canStart"] = bool(self.host and enough and self.state == "lobby")
        out["startNote"] = "" if enough else "3명부터 시작할 수 있습니다. (지금 %d명)" % self.n
        if self.rb:
            out["battle"] = self.rb.view(0)
            out["events"] = self.events
            out["me"] = 0
            out["deadlineIn"] = 25
        if self.state == "done":
            out["reward"] = {"prize": 6000, "egg": True, "damage": 1234}
        return out

    def raid_room(self):
        self.calls.append("room")
        return self.room()

    def raid_join(self, code=""):
        self.calls.append("join")
        self.state = "lobby"
        return self.room()

    def raid_create(self):
        self.calls.append("create")
        return self.room()

    def raid_leave(self):
        self.calls.append("leave")
        return {"ok": True}

    def raid_seen(self):
        self.seen += 1
        return {"ok": True}

    # ---- 판 ----
    def begin(self, hp_mult=40, rounds=15):
        players = []
        for i in range(self.n):
            team = [RB.leveled(mon(self.dex, "SNORLAX", 50,
                                   ["TACKLE", "BODYSLAM", "REST", "YAWN"], 100 + i), 50),
                    RB.leveled(mon(self.dex, "PIKACHU", 50, ["THUNDERBOLT"], 200 + i), 50)]
            players.append((i + 1, "참가자%d" % (i + 1), team))
        boss = mon(self.dex, "MEWTWO", 60,
                   ["PSYCHIC", "SHADOWBALL", "AURASPHERE", "RECOVER"], 1)
        self.rb = RB.RaidBattle(self.dex, boss, players, hp_mult=hp_mult,
                                max_rounds=rounds, rng=random.Random(5))
        self.events = self.rb.start()
        self.round = 0
        self.state = "fighting"
        return self.room()

    def raid_act(self, kind, move="", slot=-1):
        self.calls.append("act:%s" % (move or slot))
        self.rb.choose(0, kind, move if kind == "move" else slot)
        for i in range(1, len(self.rb.players)):
            if self.rb.players[i].playing():
                self.rb.choose(i, *self.rb.auto_choice(i))
        self.events = self.rb.resolve()
        self.round = self.rb.round
        if self.rb.over:
            self.state = "done"
        return self.room()

    def sprite(self, num, shiny=False):
        return self.png, ".png"


class FakeOverlay(object):
    def __init__(self, rect):
        self.key = (255, 0, 255)
        self.rect = rect
        self.settings = {}

    def area(self):
        return self.rect


class FakeApp(object):
    def __init__(self, root, api, dex, overlay=None):
        self.root = root
        self.api = api
        self.dex = dex
        self.overlay = overlay
        self.settings = {}
        self.raid_battle = None
        self.raid_window = None
        self.user_id = 1
        self.notes = []
        self.opened = []

    def notify(self, msg):
        self.notes.append(msg)

    def request_sync(self):
        pass

    def open_raid_battle(self, room):
        self.opened.append(room)


def pump(root, cond, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


def rest(root, sec=0.35):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def inside(cv, item):
    bb = cv.bbox(item)
    return bb is not None and bb[0] >= -1 and bb[2] <= cv.winfo_width() + 1, bb


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-300:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt / 화면 %dx%d"
          % (U.FAMILY, U.FONT[1], root.winfo_screenwidth(), root.winfo_screenheight()))

    # ------------------------------------------------ 레이드 탭
    print("=== 레이드 탭 (공개 전) ===")
    api = FakeApi(dex, n=3, revealed=False)
    api.state = "none"
    api.rb = None
    api.code = None

    def _no_room():
        return None
    api.room = _no_room
    app = FakeApp(root, api, dex)
    w = ui_raid.RaidWindow(app)
    pump(root, lambda: "raid" in api.calls)
    rest(root, 0.5)
    t = " ".join(texts(w.win))
    chk("공개 전에는 이름을 가린다", "???" in t, t[:120])
    chk("공개 안내가 있다", "1시간 전" in t)
    chk("참가 단추가 있다", "참가하기" in t)
    chk("규칙이 보인다", "Lv.50" in t and "70%" in t, t[:200])
    bad = squeezed(w.win)
    chk("눌린 위젯 없음", not bad, bad[:3])
    w.close()

    print("=== 레이드 탭 (아직 기간 전) ===")
    apiq = FakeApi(dex, n=3, revealed=False)

    def _off():
        d = FakeApi.raid(apiq)
        d["on"] = False
        d["open"] = False
        d["room"] = None
        d["next"]["leftSec"] = 3 * 86400 + 7200      # 사흘 뒤
        return d
    apiq.raid = _off
    appq = FakeApp(root, apiq, dex)
    wq = ui_raid.RaidWindow(appq)
    rest(root, 0.6)
    tq = " ".join(texts(wq.win))
    chk("언제 여는지 알려준다", "9월 22일(화) 11시" in tq, tq[:200])
    chk("남은 날을 센다", "3일" in tq, tq[:200])
    chk("기간을 알려준다", "2026-09-22" in tq and "2026-10-06" in tq, tq[:250])
    chk("규칙도 미리 보여준다", "Lv.50" in tq, tq[:250])
    chk("기간 전에는 참가 단추가 없다", "참가하기" not in tq, tq[:200])
    bad = squeezed(wq.win)
    chk("눌린 위젯 없음", not bad, bad[:3])
    wq.close()

    print("=== 레이드 탭 (공개 뒤 · 로비) ===")
    api2 = FakeApi(dex, n=3, revealed=True)
    app2 = FakeApp(root, api2, dex)
    w2 = ui_raid.RaidWindow(app2)
    pump(root, lambda: "raid" in api2.calls)
    rest(root, 0.5)
    t = " ".join(texts(w2.win))
    chk("보스 이름이 뜬다", "뮤츠" in t, t[:120])
    chk("타입이 뜬다", "에스퍼" in t)
    chk("로비가 뜬다", "사람을 기다리는 중" in t)
    chk("인원이 보인다", "3 / 6명" in t, t[:200])
    chk("방 코드가 보인다", "AB12CD" in t)
    chk("빈 자리도 보인다", t.count("비었음") == 3, t.count("비었음"))
    chk("방장에게 시작 단추", "레이드 시작" in t, t[:200])
    chk("정각 이야기를 안 한다", "정각에 시작" not in t)
    bad = squeezed(w2.win)
    chk("눌린 위젯 없음", not bad, bad[:3])
    # 방장이 아니면 시작 단추가 없고 기다리라고만 한다
    api3h = FakeApi(dex, n=3, revealed=True, host=False)
    app3h = FakeApp(root, api3h, dex)
    w3h = ui_raid.RaidWindow(app3h)
    pump(root, lambda: "raid" in api3h.calls)
    rest(root, 0.4)
    th = " ".join(texts(w3h.win))
    chk("방장이 아니면 시작 단추가 없다", "레이드 시작" not in th, th[:200])
    chk("기다리라고 알려준다", "방장이 시작" in th, th[:200])
    w3h.close()

    # 사람이 모자라면 방장도 못 누른다
    api3s = FakeApi(dex, n=2, revealed=True, host=True)
    app3s = FakeApp(root, api3s, dex)
    w3s = ui_raid.RaidWindow(app3s)
    pump(root, lambda: "raid" in api3s.calls)
    rest(root, 0.4)
    ts = " ".join(texts(w3s.win))
    chk("모자라면 까닭을 알려준다", "3명부터" in ts, ts[:200])
    w3s.close()

    print("=== 새로고침 ===")
    t = " ".join(texts(w2.win))
    chk("머리줄에 새로고침이 있다 (다른 탭처럼)", "새로고침" in t, t[:120])
    chk("보스 노력치를 알린다", "노력치 96" in t, t[:300])
    before = api2.calls.count("raid")
    w2.refresh_btn.command()
    pump(root, lambda: api2.calls.count("raid") > before, timeout=5)
    chk("누르면 다시 불러온다", api2.calls.count("raid") > before,
        (before, api2.calls.count("raid")))
    # **여러 번 눌러도 폴링은 한 줄이다.** 예전에는 불러올 때마다 이전
    # 예약을 두고 새로 걸어서, 로비(2초)에서 열 번 누르면 2초에 열 번 갔다.
    for _ in range(6):
        w2.refresh_btn.command()
        pump(root, lambda: not w2._busy, timeout=5)
    rest(root, 0.2)
    n0 = api2.calls.count("raid")
    rest(root, 4.5)
    got = api2.calls.count("raid") - n0
    chk("여러 번 눌러도 폴링이 불어나지 않는다 (4.5초에 2~3번)", got <= 3, got)

    print("=== 깜빡이지 않는다 ===")
    # 로비는 2초마다 방을 물어본다. 예전에는 그때마다 화면을 통째로 지우고
    # 다시 그려서(_clear) 아무도 안 들어와도 눈에 띄게 깜빡였다 (사용자 제보).
    chk("남은 시간만 줄면 모양은 같다",
        ui_raid.shape_of({"a": 1, "next": {"leftSec": 240, "revealed": True}})
        == ui_raid.shape_of({"a": 1, "next": {"leftSec": 3, "revealed": True}}))
    chk("사람이 들어오면 모양이 달라진다",
        ui_raid.shape_of({"room": {"count": 3}}) != ui_raid.shape_of({"room": {"count": 4}}))
    keep = [str(w) for w in w2.body.winfo_children()]
    n_before = api2.calls.count("raid")
    for _ in range(3):
        w2.reload(True)
        pump(root, lambda: api2.calls.count("raid") > n_before, timeout=5)
        n_before = api2.calls.count("raid")
    rest(root, 0.3)
    chk("다시 불러도 그려 둔 것을 안 지운다",
        [str(w) for w in w2.body.winfo_children()] == keep,
        [str(w) for w in w2.body.winfo_children()][:3])
    chk("그래도 인원은 맞다", "3 / 6명" in " ".join(texts(w2.win)))
    # 사람이 들어오면 그때는 다시 그린다
    api2.n = 4
    w2.reload(True)
    pump(root, lambda: "4 / 6명" in " ".join(texts(w2.win)), timeout=10)
    chk("사람이 들어오면 다시 그린다", "4 / 6명" in " ".join(texts(w2.win)),
        " ".join(texts(w2.win))[:120])
    api2.n = 3
    w2.reload(True)
    pump(root, lambda: "3 / 6명" in " ".join(texts(w2.win)), timeout=10)
    # 새로고침은 사람이 누른 것이라 바뀐 게 없어도 한 번은 다시 그린다
    keep2 = [str(w) for w in w2.body.winfo_children()]
    w2.refresh_btn.command()
    pump(root, lambda: [str(x) for x in w2.body.winfo_children()] != keep2, timeout=10)
    chk("새로고침을 누르면 다시 그린다",
        [str(x) for x in w2.body.winfo_children()] != keep2)

    print("=== 경계에서 스스로 다시 부른다 ===")
    chk("경계 계산: 두 시간 앞이면 30분 뒤에 한 번", ui_raid.next_edge(
        7200, {"openSec": 300, "revealSec": 3600, "next": {"revealed": False}}) == 1800)
    chk("경계 계산: 공개 100초 전", ui_raid.next_edge(
        3700, {"openSec": 300, "revealSec": 3600, "next": {"revealed": False}}) == 100)
    chk("경계 계산: 공개됐으면 모집 시작까지", ui_raid.next_edge(
        1000, {"openSec": 300, "revealSec": 3600, "next": {"revealed": True}}) == 700)
    chk("경계 계산: 모집 중이면 정각까지", ui_raid.next_edge(
        200, {"openSec": 300, "next": {"revealed": True}}) == 200)
    chk("경계 계산: 지났으면 없음", ui_raid.next_edge(0, {}) is None)
    # 보스 공개 5초 전에 연 탭 - 예전에는 모집 6분 전 안쪽이 아니면 다시
    # 부르지 않아서, 공개도 '참가하기' 도 탭을 다시 열어야 떴다.
    ape = FakeApi(dex, n=3, revealed=False)
    ape.room = _no_room

    def _far():
        d = FakeApi.raid(ape)
        d["open"] = False
        d["room"] = None
        d["next"]["leftSec"] = 3605
        return d
    ape.raid = _far
    appe = FakeApp(root, ape, dex)
    we = ui_raid.RaidWindow(appe)
    pump(root, lambda: "raid" in ape.calls)
    pump(root, lambda: ape.calls.count("raid") >= 2, timeout=12)
    chk("보스 공개 시각이 되면 저절로 다시 불러온다", ape.calls.count("raid") >= 2,
        ape.calls.count("raid"))
    we.close()

    # 판이 열리면 배틀 창으로 넘긴다
    api2.begin()
    w2.reload(True)
    pump(root, lambda: bool(app2.opened), timeout=10)
    chk("판이 열리면 배틀 창으로 넘긴다", bool(app2.opened))
    w2.close()

    # ------------------------------------------------ 배틀 창
    print("=== 레이드 배틀 창 ===")
    api3 = FakeApi(dex, n=6, revealed=True)
    room = api3.begin()
    app3 = FakeApp(root, api3, dex)
    bw = RUI.RaidBattleWindow(app3, room)
    pump(root, lambda: not bw.busy, timeout=25)
    rest(root, 0.4)
    bw.win.update_idletasks()
    sw_, sh_ = root.winfo_screenwidth(), root.winfo_screenheight()
    try:
        ax1, ay1, ax2, ay2 = PLAT.work_area(sw_, sh_)
    except Exception:                                       # noqa: BLE001
        ax1, ay1, ax2, ay2 = 0, 0, sw_, sh_
    ww, wh = bw.win.winfo_width(), bw.win.winfo_height()
    chk("창이 화면 안에 들어온다", ww <= (ax2 - ax1) and wh <= (ay2 - ay1) + 44,
        (ww, wh, ax2 - ax1, ay2 - ay1))
    ok, bb = inside(bw.cv, bw.hp_text)
    chk("공용 체력바 글씨가 캔버스 안", ok, bb)
    ok, bb = inside(bw.cv, bw.boss_name)
    chk("보스 이름이 캔버스 안", ok, bb)
    ok, bb = inside(bw.cv, bw.round_text)
    chk("라운드 표시가 캔버스 안", ok, bb)
    chk("참가자 칸이 여섯", len(bw.slots) == 6, len(bw.slots))
    outs = [i for i in bw.slots if not inside(bw.cv, bw.slots[i]["name"])[0]]
    chk("참가자 이름이 모두 캔버스 안", not outs, outs)
    chk("여섯 명이면 보스가 두 번 움직인다고 적힌다",
        "보스 2회" in bw.cv.itemcget(bw.round_text, "text"),
        bw.cv.itemcget(bw.round_text, "text"))
    bad = squeezed(bw.win)
    chk("눌린 위젯 없음", not bad, bad[:3])
    t = " ".join(texts(bw.win))
    chk("내 기술 칸이 뜬다", "PP" in t, t[:150])
    chk("기술 이름이 보인다", "몸통박치기" in t or "누르기" in t, t[:200])

    print("=== 좁은 화면 ===")
    # CI 맥에서 잡혔다: 글꼴이 크면 U.h(960) 이 1152 가 되는데 화면이
    # 1024 라 오른쪽이 통째로 밖으로 나갔다. 작업 영역을 좁다고 속여서 본다.
    real_area = PLAT.work_area
    try:
        PLAT.work_area = lambda w, h: (0, 0, 1024, 677)
        api_n = FakeApi(dex, n=6, revealed=True)
        room_n = api_n.begin()
        app_n = FakeApp(root, api_n, dex)
        bw_n = RUI.RaidBattleWindow(app_n, room_n)
        pump(root, lambda: not bw_n.busy, timeout=25)
        rest(root, 0.4)
        bw_n.win.update_idletasks()
        chk("좁은 화면에도 창이 들어간다", bw_n.win.winfo_width() <= 1024,
            bw_n.win.winfo_width())
        outs = [k for k in bw_n.slots if not inside(bw_n.cv, bw_n.slots[k]["name"])[0]]
        chk("참가자 칸이 다 보인다", not outs, outs)
        chk("체력바 글씨도 안에", inside(bw_n.cv, bw_n.hp_text)[0])
        chk("라운드 표시도 안에", inside(bw_n.cv, bw_n.round_text)[0])
        bad = squeezed(bw_n.win)
        chk("눌린 위젯 없음", not bad, bad[:3])
        bw_n.close()
    finally:
        PLAT.work_area = real_area

    print("=== 고르고 보내기 ===")
    before = len([c for c in api3.calls if c.startswith("act")])
    hp0 = bw.view["boss"]["hp"]
    bw.use_move("TACKLE")
    bw.use_move("TACKLE")              # 두 번 눌러도 한 번만 가야 한다
    pump(root, lambda: len([c for c in api3.calls if c.startswith("act")]) > before,
         timeout=15)
    rest(root, 0.3)
    chk("한 번만 보낸다",
        len([c for c in api3.calls if c.startswith("act")]) == before + 1,
        api3.calls)
    pump(root, lambda: not bw.busy, timeout=30)
    rest(root, 0.4)
    chk("라운드가 올라간다", bw.view["round"] >= 1, bw.view["round"])
    chk("보스 체력이 줄었다", bw.view["boss"]["hp"] <= hp0,
        (hp0, bw.view["boss"]["hp"]))
    chk("체력바가 서버 값과 맞는다",
        abs(bw.shown["boss"]["hp"] - bw.view["boss"]["hp"]) <= 1,
        (bw.shown["boss"]["hp"], bw.view["boss"]["hp"]))
    chk("보낸 표시가 풀린다", not bw.sent or bw.busy, bw.sent)

    print("=== 교체 칸 ===")
    bw.open_switch()
    root.update()
    t = " ".join(texts(bw.win))
    chk("교체 칸이 뜬다", "누구로 바꿀까?" in t, t[:120])
    bad = squeezed(bw.win)
    chk("교체 칸에 눌린 위젯 없음", not bad, bad[:3])
    bw.show_commands()
    root.update()

    print("=== 보호막 ===")
    api3.rb.boss.hp = int(api3.rb.boss.maxhp * 0.45)
    bw.sent = False
    bw.use_move("TACKLE")
    pump(root, lambda: not bw.busy and bw.view.get("boss", {}).get("shield"),
         timeout=30)
    rest(root, 0.4)
    sh = bw.view["boss"].get("shield")
    chk("보호막이 선다", bool(sh), sh)
    if sh:
        chk("보호막 바가 보인다",
            bw.cv.itemcget(bw.shield_bar, "state") in ("normal", ""),
            bw.cv.itemcget(bw.shield_bar, "state"))
        chk("보호막 숫자가 캔버스 안", inside(bw.cv, bw.shield_text)[0])

    print("=== 끝 ===")
    api3.rb.shielded_once = True
    api3.rb.shield = None
    api3.rb.boss.hp = 1
    bw.sent = False
    bw.use_move("TACKLE")
    pump(root, lambda: bw._result_shown, timeout=30)
    rest(root, 0.5)
    t = " ".join(texts(bw.win))
    chk("결과 칸이 뜬다", "레이드 성공" in t or "전멸" in t or "시간 초과" in t, t[:150])
    chk("결과를 봤다고 알린다", api3.seen >= 1, api3.seen)
    bad = squeezed(bw.win)
    chk("결과 칸에 눌린 위젯 없음", not bad, bad[:3])
    chk("닫기 단추가 있다", "닫기" in t)
    bw.close()
    chk("창이 닫힌다", not bw.alive)

    # ------------------------------------------------ 바탕화면 기둥
    print("=== 바탕화면 기둥 ===")
    rect = (300, 260, 900, 700)
    ov = FakeOverlay(rect)
    app4 = FakeApp(root, FakeApi(dex), dex, overlay=ov)
    clicks = []
    card = {"session": SESSION, "at": "2026-09-22T11:00:00", "leftSec": 125,
            "revealed": True, "kr": "뮤츠", "kind": "legendary",
            "typeIds": ["PSYCHIC"], "types": ["에스퍼"]}
    pil = raid_fx.RaidPillar(app4, card, lambda: clicks.append(1))
    rest(root, 0.3)
    x, y, w_, h_ = raid_fx.geometry(ov)
    chk("기둥이 영역 윗변에서 시작한다", y == rect[1], (y, rect[1]))
    chk("기둥이 영역 가운데", abs((x + w_ / 2) - (rect[0] + rect[2]) / 2) <= 1,
        (x, w_))
    chk("기둥이 영역보다 넓지 않다", w_ <= rect[2] - rect[0], w_)
    chk("기둥이 영역 높이를 안 넘는다", h_ <= rect[3] - rect[1], h_)
    chk("그림이 여러 장", len(pil.photos) > 1, len(pil.photos))
    chk("보스 이름이 붙는다", "뮤츠" in pil.title.cget("text"), pil.title.cget("text"))
    chk("남은 시간이 붙는다", "뒤 시작" in pil.sub.cget("text"), pil.sub.cget("text"))
    pil._clicked()
    chk("누르면 열린다", clicks == [1], clicks)
    # 영역을 옮기면 따라간다
    ov.rect = (100, 500, 500, 800)
    pil.reposition()
    rest(root, 0.2)
    chk("영역이 바뀌면 따라간다", pil.y == 500, pil.y)
    # 공개 전에는 색을 안 흘린다
    chk("공개 전 색은 회색빛",
        raid_fx.pillar_color({"revealed": False}) == raid_fx.HIDDEN_COLOR)
    chk("공개 뒤에는 타입 색",
        raid_fx.pillar_color(card) != raid_fx.HIDDEN_COLOR)
    pil.destroy()
    rest(root, 0.2)
    chk("기둥이 사라진다", not pil.alive and not pil.win.winfo_exists())

    print("=== 한 번 누르면 그 회차에는 다시 안 뜬다 ===")
    # app.App 의 두 메서드를 그대로 불러 본다 (앱 전체를 띄우지 않고).
    from poketdesktop.app import App
    from poketdesktop import config as CFG

    class Stub(object):
        def __init__(self):
            self.root = root
            self.overlay = FakeOverlay((300, 260, 900, 700))
            self.settings = dict(CFG.DEFAULTS)
            self.raid_pillar = None
            self.raid_battle = None
            self._raid_told = None
            self.said = []
            self.went = 0

        notify = lambda self, m: self.said.append(m)

        def resume_raid(self):
            self.went += 1

        _raise_pillar = App._raise_pillar
        _drop_pillar = App._drop_pillar
        _pillar_clicked = App._pillar_clicked
        announce_raid = App.announce_raid

    st = Stub()
    me_card = {"next": dict(card, leftSec=300), "open": True, "unseen": 0,
               "room": None, "playedToday": False}
    st.announce_raid(me_card)
    rest(root, 0.2)
    chk("회차가 가까우면 기둥이 선다", st.raid_pillar is not None)
    chk("한 번은 알린다", len(st.said) == 1, st.said)
    st._pillar_clicked()
    rest(root, 0.2)
    chk("누르면 사라진다", st.raid_pillar is None)
    chk("누르면 레이드 창으로 간다", st.went == 1, st.went)
    chk("누른 회차를 적어 둔다",
        st.settings.get("raidPillarSeen") == SESSION, st.settings.get("raidPillarSeen"))
    st.announce_raid(me_card)
    rest(root, 0.2)
    chk("다시 안 뜬다", st.raid_pillar is None)
    # 다음 회차가 되면 열쇠가 달라져서 저절로 풀린다
    nxt = dict(me_card, next=dict(card, session="2026-09-22T21", leftSec=300))
    st.announce_raid(nxt)
    rest(root, 0.2)
    chk("다음 회차에는 다시 뜬다", st.raid_pillar is not None)
    st._drop_pillar()
    rest(root, 0.2)

    rest(root, 0.3)
    chk("콜백에서 터진 곳 없음", not errors, errors[:1])
    try:
        root.destroy()
    except tk.TclError:
        pass
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
