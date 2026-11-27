# -*- coding: utf-8 -*-
"""열매 텃밭 (다음 시즌, 2026-11-26) 바탕화면 검사 — 화단 · 심기 · 물 · 거두기 · 메뉴 · 먹이 · 친구 화단 · 설정.

    python client/test_garden_ui.py
    python client/run_as_windows.py client/test_garden_ui.py

**진짜 Overlay · 화단 창 · 연못(FishingController) · WildController 를 띄운다.** 서버는 안 띄운다 - 가짜 api 가
API 계약(design-notes/2026-11-26-garden-plan.md 'API 계약') 모양의 카드 · 응답을 준다. 단계 · 남은 초 · 물 · 천장은
서버가 셈하므로 여기서는 '카드대로 그리는가 · 눌렀을 때 무엇을 부르는가' 만 본다. (Task 2 Step 1 의 열여섯 가지)

  1. 카드가 열리면 화단 하나가 연못 '기본' 자리 + 연못 너비 + 64px 에, 바닥에 맞춰. 연못을 옮기거나 숨겨도 그 자리
  2. 영역이 좁으면(200x150) 연못 위 줄
  3. 빈 화분 → 심을 열매 메뉴 (4/8/16시간 머리줄 · 묶음마다 5줄 · 많은 순 · 미끼 표시) → garden_plant
  4. 자라는 화분 → garden_water 한 번 (물뿌리개)       5. 익은 화분 → garden_harvest(True) → '+4 오랭열매 · 다시 심음'
  6. 천장 → 마우스 올림 '오늘은 20개를 …'             7. 단계 그림 다섯 · 물방울 · 젖은 흙 · 익음 반짝이 카드대로
  8. nextIn 에 다시 묻기                               9. 오른클릭(맥 길) 메뉴 넷 · 뽑기 · 옮기기 · 숨기기
 10. 펫 메뉴 '열매 먹이기' (맥 · 윈도 두 갈래 + 맥 길 실제로) · 오늘 줌이면 죽은 줄
 11. 먹이 응답에 evolve 가 있으면 진화 연출 (가방의 진화 도구와 같은 길 - app.show_evolutions)
 12. show_friend(view) → 내 화단 숨고 친구 화단 흐리게, 누르면 visit_water; None → 내 화단
 13. play_water · spot                                14. 풀숲 · 알이 연못과 화단을 둘 다 피한다
 15. 설정 · 트레이 '텃밭 보이기' · 처음 값이 showPond 를 따름 · 안내 셋 순서
 16. 정리 뒤 남는 창 · after 없음, 그리는 중 예외 없음
"""
import os
import random
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-garden-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from common import held as HELD                             # noqa: E402

from poketdesktop import airraid as RC                      # noqa: E402
from poketdesktop import config, eggs_ui, sprites           # noqa: E402
from poketdesktop import fishing as FI                      # noqa: E402
from poketdesktop import fishing_art as FART                # noqa: E402
from poketdesktop import garden as GD                       # noqa: E402
from poketdesktop import garden_art as ART                  # noqa: E402
from poketdesktop import overlay as OV                      # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import sprite_cache, walk_cache, wild_ui  # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop.app import App                            # noqa: E402

HOME = os.environ["POKET_HOME"]
OK = FAIL = 0
AREA = (300, 200, 1100, 700)
KEY = (255, 0, 255)


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


def dot_path():
    p = os.path.join(HOME, "dot.png")
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    for x in range(8, 32):
        for y in range(6, 36):
            im.putpixel((x, y), (240, 120, 40, 255))
    im.save(p)
    return p


# ---------------------------------------------------------------- 계약 모양 카드
def pot(slot, berry=None, stage=0, group=None, grow=None, age=None, left=None, wet=0, fb=0, ripe=False,
        yld=None, needs=False):
    return {"slot": slot, "berry": berry, "group": group, "stage": stage, "grow": grow, "age": age, "left": left,
            "wetMask": wet, "friendBonus": fb, "ripe": ripe, "yield": yld, "needsWater": needs}


def gcard(pots=None, harvested=0, cap=20, next_in=None, fed=(), fw=None):
    ps = list(pots or [])
    while len(ps) < 3:
        ps.append(pot(len(ps)))
    return {"open": True, "pots": ps, "harvested": harvested, "cap": cap, "nextIn": next_in,
            "fedToday": list(fed), "friendWater": fw}


def growing(slot, berry="ORANBERRY", stage=2, wet=0, left=3600, needs=True, fb=0):
    return pot(slot, berry, stage, 4, 14400, 14400 - left, left, wet, fb, False, 1 + bin(wet).count("1") + fb, needs)


def ripe(slot, berry="ORANBERRY", wet=7, fb=0):
    return pot(slot, berry, 4, 4, 14400, 15000, 0, wet, fb, True, 1 + bin(wet).count("1") + fb, False)


def fcard():
    return {"open": True, "state": "idle", "ready": False, "nibbleLeft": None, "strikeLeft": None,
            "bait": None, "baitLeft": 0, "wait": None, "wild": None, "ballOptions": None}


FPOTS = [{"berry": "ORANBERRY", "stage": 2, "friendBonus": 0}, {"berry": None, "stage": 0, "friendBonus": 0},
         {"berry": "CHERIBERRY", "stage": 4, "friendBonus": 0}]
G_CAN = {"canWater": True, "why": None, "pots": FPOTS}
G_DONE = {"canWater": False, "why": "done", "pots": [dict(p, friendBonus=1 if 1 <= p["stage"] <= 3 else 0)
                                                     for p in FPOTS]}


class Err(Exception):
    def __init__(self, status, message="오류"):
        Exception.__init__(self, message)
        self.status, self.message = status, message


class FakeApi(object):
    def __init__(self):
        self.calls = []
        self.gcard = gcard()
        self.fcard = fcard()
        self.bag_r = {"bag": {"ORANBERRY": 12, "SITRUSBERRY": 3, "LUMBERRY": 7, "CHERIBERRY": 2, "PECHABERRY": 5,
                              "RAWSTBERRY": 4, "ASPEARBERRY": 1, "OCCABERRY": 6, "LIECHIBERRY": 2,
                              "POMEGBERRY": 9, "POKEBALL": 5, "LEFTOVERS": 1},
                      "money": 0, "balls": 5}
        self.wild_r = {"wild": None, "nextInSeconds": 300, "balls": 5}
        self.water_r = None
        self.harvest_r = None
        self.feed_r = {"berry": "ORANBERRY", "kr": "오랭열매", "gain": 10, "happiness": 152, "evolve": None}
        self.feed_err = None
        self.feed_delay = 0.0        # feed 가 답하기까지 (그사이 화분을 누르기)
        self.vwater_r = {"ok": True, "bonus": 1, "garden": G_DONE}
        self.err = None              # 다음 텃밭 쓰기 한 번이 낼 오류
        self.pull_refunded = None    # 뽑기 답의 refunded (None 이면 칸이 없는 답 - 옛 서버)
        self.garden_reply = None     # GET /api/garden 이 이것을 답한다 (None 이면 지금 카드) - 동작 전 줄을 읽은 서버
        self.garden_delay = 0.0      # GET 이 답하기까지 (그사이 거두기 · 먹이 답이 먼저 온다)
        self.harvest_delay = 0.0

    def _maybe_err(self):
        if self.err is not None:
            e, self.err = self.err, None
            raise e

    def garden(self):
        self.calls.append(("garden",))
        c = self.garden_reply if self.garden_reply is not None else self.gcard
        if self.garden_delay:
            time.sleep(self.garden_delay)
        return c

    def garden_plant(self, slot, berry):
        self.calls.append(("plant", slot, berry))
        self._maybe_err()
        ps = list(self.gcard["pots"])
        ps[slot] = growing(slot, berry, 1, 0, 14400, True)
        self.gcard = dict(self.gcard, pots=ps)
        return self.gcard

    def garden_water(self):
        self.calls.append(("water",))
        self._maybe_err()
        r = self.water_r or {"watered": 0, "card": self.gcard}
        self.gcard = r["card"]
        return r

    def garden_harvest(self, replant=True):
        self.calls.append(("harvest", replant))
        if self.harvest_delay:
            time.sleep(self.harvest_delay)
        self._maybe_err()
        r = self.harvest_r or {"got": [], "replanted": [], "capped": False, "card": self.gcard}
        self.gcard = r["card"]
        return r

    def garden_pull(self, slot):
        self.calls.append(("pull", slot))
        self._maybe_err()
        ps = list(self.gcard["pots"])
        ps[slot] = pot(slot)
        self.gcard = dict(self.gcard, pots=ps)
        if self.pull_refunded is None:
            return self.gcard
        return dict(self.gcard, refunded=self.pull_refunded)     # 씨앗을 돌려줬는지는 서버가 정한다

    def visit_water(self):
        self.calls.append(("visit_water",))
        return self.vwater_r

    def feed(self, pid, avoid=None):
        self.calls.append(("feed", pid, avoid))
        if self.feed_delay:
            time.sleep(self.feed_delay)
        if self.feed_err is not None:
            e, self.feed_err = self.feed_err, None
            raise e
        return self.feed_r

    def fish(self):
        self.calls.append(("fish",))
        return self.fcard

    def bag(self):
        self.calls.append(("bag",))
        return self.bag_r

    def wild(self, force=False):
        self.calls.append(("wild",))
        return self.wild_r

    def wild_flee(self, wid):
        return {}

    def n(self, name):
        return sum(1 for c in self.calls if c[0] == name)

    def last(self, name):
        got = [c for c in self.calls if c[0] == name]
        return got[-1] if got else None


class FakeVisit(object):
    def __init__(self):
        self.active = False
        self.guest = False


class WaterVisit(FakeVisit):
    """놀러 가기 (Task 3 의 Visit.water) 가 있는 앱 - 친구 화단을 누르면 그 길로 보낸다."""

    def __init__(self):
        FakeVisit.__init__(self)
        self.active = self.guest = True
        self.waters = 0

    def water(self):
        self.waters += 1


class MiniApp(object):
    def __init__(self, root, ov):
        self.root, self.overlay = root, ov
        self.settings = ov.settings
        self.api = FakeApi()
        self.balls = 5
        self.battle = self.arena = None
        self.visit = FakeVisit()
        self.focus = None
        self.olympics = None
        self.alarms = None
        self.arche = None
        self.dex = None
        self.settings_win = None
        self.box_window = None
        self.raid_pillar = None
        self.notes = []
        self.floats = []
        self.evolutions = []
        self.synced = 0
        self.wild = wild_ui.WildController(self)
        self.airraid = RC.AirRaidController(self)
        self.fishing = FI.FishingController(self)
        self.garden = GD.GardenController(self)
        ov.avoid = [self.fishing.rect, self.garden.rect]

    def notify(self, m):
        self.notes.append(m)

    def refresh_tray(self):
        pass

    def request_sync(self):
        self.synced += 1

    def bag_changed(self):
        pass

    def on_session_lost(self):
        pass

    def show_evolutions(self, infos, parent=None):
        self.evolutions.append(list(infos))

    def float_at(self, sx, sy, text, color="#7bffa0", ms=1100):
        self.floats.append((sx, sy, text, color))
        return App.float_at(self, sx, sy, text, color, ms)

    def said(self, text):
        return any(text in f[2] for f in self.floats)

    def open_box(self):
        pass

    def quit(self):
        pass

    def pet_open(self, pet):
        pass

    # 설정 창이 만지는 것 (test_fishing_ui 의 껍데기와 같은 꼴)
    boss_key_error = ""

    def stealth_on(self):
        return False

    def boss_key(self):
        return ""

    def apply_boss_key(self, combo=None):
        return True, ""

    def set_size(self, px):
        pass

    on_fish_push = App.on_fish_push
    set_show_pond = App.set_show_pond
    toggle_pond = App.toggle_pond
    set_show_garden = App.set_show_garden
    toggle_garden = App.toggle_garden
    _area_changed = App._area_changed
    _right_click_at = App._right_click_at
    _pets = App._pets
    _hit = staticmethod(App._hit)
    pet_menu = App.pet_menu
    mega_menu_row = App.mega_menu_row


def mon(pid, name="피카츄"):
    return {"id": pid, "num": 25, "shiny": False,
            "info": {"name": name, "species": name, "level": 12, "types": ["전기"]}}


def top(w):
    return int(w.attributes("-topmost"))


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def pixels(im):
    fn = getattr(im, "get_flattened_data", None) or im.getdata
    return list(fn())


def count(im, color, box=None):
    if box is not None:
        im = im.crop(box)
    return sum(1 for px in pixels(im) if px == color)


def put(app, c):
    """가짜 서버와 앱을 같은 카드로 맞춘다 (나중에 앱이 카드를 다시 물어도 같은 답이 오게)."""
    app.api.gcard = c
    app.garden._apply(c)


def press(root, p, slot):
    p.label.event_generate("<Button-1>", x=ART.pot_x(slot), y=ART.SOIL_Y * ART.SCALE)
    settle(root, 0.05)


class Spy(object):
    """U.PopupMenu 를 바꿔 끼워 열린 메뉴의 줄을 모은다 (맥 길)."""

    def __init__(self):
        self.opened = []
        self.real = U.PopupMenu
        spy = self

        class _P(self.real):
            def __init__(self, root_, rows, x, y, **kw):
                spy.opened.append(rows)
                spy.real.__init__(self, root_, rows, x, y, **kw)
        self.cls = _P

    def __enter__(self):
        self.native = PLAT.NATIVE_MENU
        PLAT.NATIVE_MENU = False
        U.PopupMenu = self.cls
        return self

    def __exit__(self, *a):
        U.PopupMenu = self.real
        PLAT.NATIVE_MENU = self.native
        U.close_all()


def texts(rows):
    return [r.get("text") for r in rows if r]


class Native(object):
    """윈도우 길 (tk.Menu) 을 이 맥에서 돌린다 - tk_popup 만 바꿔 끼워 띄우지 않고 메뉴를 모은다.
    (맥은 tk.Menu 를 '여는' 순간 죽는다. 만들고 항목을 넣는 것은 괜찮다.)"""

    def __init__(self):
        self.menus = []

    def __enter__(self):
        self.native = PLAT.NATIVE_MENU
        self.real = tk.Menu.tk_popup
        PLAT.NATIVE_MENU = True
        tk.Menu.tk_popup = lambda m, x, y, entry="": self.menus.append(m)
        return self

    def __exit__(self, *a):
        tk.Menu.tk_popup = self.real
        PLAT.NATIVE_MENU = self.native
        for m in self.menus:
            try:
                m.destroy()
            except Exception:                               # noqa: BLE001
                pass


def entries(m):
    """tk.Menu 의 줄 [(종류, 글, 상태, 하위 메뉴)]."""
    out = []
    end = m.index("end")
    for i in range(0 if end is None else end + 1):
        kind = m.type(i)
        if kind == "separator":
            out.append((kind, None, None, None))
            continue
        sub = m.nametowidget(m.entrycget(i, "menu")) if kind == "cascade" else None
        out.append((kind, m.entrycget(i, "label"), str(m.entrycget(i, "state")), sub))
    return out


# ---------------------------------------------------------------- 그림
def art_part():
    print("=== 그림 ===")
    w, h = ART.size()
    chk("화단 창 (대략 112x40 화단 + 위로 자라는 줄기 · 열매 높이)", 100 <= w <= 140 and 60 <= h <= 100, (w, h))
    E = (0, None, 0, 0)
    looks = [(E, E, E), ((1, "ORANBERRY", 0, 0),) * 3, ((2, "ORANBERRY", 3, 0),) * 3,
             ((3, "CHERIBERRY", 7, 1),) * 3, ((4, "SITRUSBERRY", 5, 0),) * 3]
    ok = True
    for lk in looks:
        for mode in ("idle", "water"):
            fr = ART.frames(lk, KEY, mode, (0, 1, 2) if mode == "water" else ())
            ok = ok and len(fr) >= 2 and all(f.size == (w, h) and f.mode == "RGB" for f in fr)
    chk("모습마다 같은 크기의 RGB 그림 여러 장 (윈도우 색 열쇠 - 반투명 없음)", ok)
    f0 = ART.frames(looks[3], KEY)[0]
    chk("  2배 도트 (가로 두 칸씩 같은 색)", all(f0.getpixel((x, y)) == f0.getpixel((x + 1, y))
                                       for x in range(0, w, 2) for y in range(0, h, 5)))
    imgs = [ART.frames(lk, KEY)[0].tobytes() for lk in looks]
    chk("단계 다섯 (빈 흙 · 새싹 · 줄기 · 꽃 · 열매) 이 서로 다르다", len(set(imgs)) == 5)
    chk("화분 고르기: 화분 가운데 x 가 그 화분", [ART.slot_at(ART.pot_x(i)) for i in range(3)] == [0, 1, 2])
    chk("  가장자리도 가까운 화분", ART.slot_at(0) == 0 and ART.slot_at(w - 1) == 2)


# ---------------------------------------------------------------- 1. 자리
def place_part(root, ov, app):
    print("=== 1. 화단이 뜬다 · 자리 ===")
    gd = app.garden
    s = app.settings
    s["showPond"], s["showGarden"], s["pondHints"] = False, None, 2
    gd.note(gcard())
    settle(root)
    chk("낚시터를 끈 사람은 처음에 텃밭도 꺼진 채 (showGarden 이 showPond 를 따른다)",
        gd.planter is None and s["showGarden"] is False, s["showGarden"])
    s["showPond"], s["showGarden"] = None, None
    s["showGrass"] = True
    gd.note(gcard())
    settle(root)
    p = gd.planter
    chk("낚시터를 켠 사람(풀숲 켬 → 낚시터 켬)은 화단이 뜬다 · 그 값으로 굳힌다",
        p is not None and s["showGarden"] is True and config.load_settings().get("showGarden") is True,
        s.get("showGarden"))
    app.fishing.note(fcard())
    settle(root)
    pw, ph = FART.size()
    px, py = FI.default_home(ov, pw, ph)
    x1, y1, x2, y2 = AREA
    m = ov.settings["areaMargin"]
    lane = max(64, int(round(ov.settings["targetHeight"] * ov.settings["maxScale"])) + 16)
    chk("연못 기본 자리 + 연못 너비 + 낚인 포켓몬 자리 (max(64, 크기 x maxScale + 16) = %d), 바닥에 맞춰" % lane,
        p.x == px + pw + lane and p.y + p.fh == y2 - m, ((p.x, p.y, p.fw, p.fh), (px, py, pw)))
    chk("  창이 그 자리에 있다", pump(root, lambda: abs(p.win.winfo_x() - p.x) <= 1 and abs(p.win.winfo_y() - p.y) <= 1),
        (p.win.winfo_x(), p.win.winfo_y(), p.x, p.y))
    fz = app.fishing
    chk("  연못(기본 자리)과 안 겹친다 · 낚인 포켓몬이 내려앉는 자리(연못 오른쪽 30px)를 비운다",
        not overlaps(gd.rect(), fz.rect()) and fz.anchor()[0] + 24 < p.x, (gd.rect(), fz.rect(), fz.anchor()))
    chk("rect() 는 화단 자리", gd.rect() == (p.x, p.y, p.x + p.fw, p.y + p.fh), gd.rect())
    at = (p.x, p.y)
    fz.place_at(x1 + 600, y1 + 150)
    app._area_changed()
    settle(root)
    chk("연못을 옮겨도 화단은 제자리", (p.x, p.y) == at and fz.rect()[0] > x1 + 500, ((p.x, p.y), at, fz.rect()))
    app.set_show_pond(False)
    settle(root)
    chk("연못을 숨겨도 화단은 제자리 · 그대로 보인다", gd.planter is p and (p.x, p.y) == at, (p.x, p.y))
    app.settings["pondPos"] = None
    app.set_show_pond(True)
    settle(root)
    fz.reposition()

    print("=== 영역이 _area_changed 없이 바뀌어도 ===")
    other = (200, 150, 1200, 800)
    ov.area = lambda: other
    chk("화단이 스스로 알아채 새 영역의 제자리로", pump(root, lambda: (p.x, p.y) == gd.home(p.fw, p.fh), 3)
        and other[1] <= p.y and p.y + p.fh <= other[3], ((p.x, p.y), gd.home(p.fw, p.fh)))
    ov.area = lambda: AREA
    chk("  돌아오면 다시 따라온다", pump(root, lambda: (p.x, p.y) == at, 3), ((p.x, p.y), at))

    print("=== 포켓몬 크기가 크면 낚인 포켓몬 자리도 넓다 (검토 8) ===")
    th0, ms = ov.settings["targetHeight"], ov.settings["maxScale"]
    ov.settings["targetHeight"] = 120                   # 설정의 가장 큰 크기
    try:
        bpx, _bpy = FI.default_home(ov, pw, ph)
        big = gd.home(p.fw, p.fh)
        lane = max(64, int(round(120 * ms)) + 16)
        chk("크기 120: 화단 = 연못 기본 자리 + 연못 너비 + %d" % lane, big[0] == bpx + pw + lane, (big, bpx, pw))
        wide = int(round(120 * ms))                     # 낚인 포켓몬 창 폭 (크기 x maxScale 까지)
        land_right = bpx + pw + 30 + wide / 2.0         # fishing.anchor: 연못 오른쪽 +30 에 발 가운데
        chk("  내려앉은 낚인 포켓몬(폭 %d)이 첫 화분 · 화단과 안 겹친다" % wide, land_right < big[0], (land_right, big[0]))
        chk("  화단이 스스로 새 자리로 (영역 따라가기와 같은 길)", pump(root, lambda: (p.x, p.y) == big, 3),
            ((p.x, p.y), big))
    finally:
        ov.settings["targetHeight"] = th0
    chk("  크기를 되돌리면 제자리로", pump(root, lambda: (p.x, p.y) == at, 3), ((p.x, p.y), at))


# ---------------------------------------------------------------- 2. 좁은 영역
def narrow_part(root, ov, app):
    print("=== 2. 영역이 좁으면 연못 위 줄 ===")
    gd = app.garden
    p = gd.planter
    small = (300, 200, 500, 350)                 # 200 x 150 (영역의 가장 작은 크기)
    ov.area = lambda: small
    app._area_changed()
    settle(root)
    pw, ph = FART.size()
    px, py = FI.default_home(ov, pw, ph)
    pond = (px, py, px + pw, py + ph)
    chk("200x150: 화단은 연못 기본 자리 위 줄 (안 겹친다 · 영역 안)",
        p.y + p.fh <= py and not overlaps(gd.rect(), pond) and small[0] <= p.x and p.x + p.fw <= small[2]
        and small[1] <= p.y, ((p.x, p.y, p.fw, p.fh), pond))
    mid = (300, 200, 660, 440)                   # '좁게' (360 x 240) - 오른쪽에 자리가 모자란다
    ov.area = lambda: mid
    app._area_changed()
    px, py = FI.default_home(ov, pw, ph)
    chk("360x240 도 오른쪽이 모자라면 연못 위 줄", p.y + p.fh <= py and p.x + p.fw <= mid[2] - ov.settings["areaMargin"],
        (p.x, p.y, py))
    ov.area = lambda: AREA
    app._area_changed()
    settle(root)


# ---------------------------------------------------------------- 3~6. 심기 · 물 · 거두기 · 천장
def plant_part(root, ov, app):
    print("=== 3. 빈 화분 → 심을 열매 메뉴 → garden_plant ===")
    gd = app.garden
    p = gd.planter
    app.settings["lastBait"] = "SITRUSBERRY"
    put(app, gcard())
    with Spy() as spy:
        press(root, p, 0)
        chk("빈 화분을 누르면(<Button-1>) 가방을 물어 메뉴를 연다", pump(root, lambda: len(spy.opened) == 1, 3),
            app.api.calls[-3:])
        rows = spy.opened[-1]
        heads = [r["text"] for r in rows if r and r.get("header")]
        chk("  머리줄 4시간 · 8시간 · 16시간 (가진 묶음만, 그 차례)", heads == ["4시간", "8시간", "16시간"], heads)
        kr = HELD.KR
        four = [r["text"] for r in rows[rows.index(next(r for r in rows if r and r.get("text") == "4시간")) + 1:]
                if r][:5]
        want = ["%s ×12" % kr["ORANBERRY"], "%s ×7" % kr["LUMBERRY"], "%s ×5" % kr["PECHABERRY"],
                "%s ×4" % kr["RAWSTBERRY"], "%s ×3 · 미끼" % kr["SITRUSBERRY"]]
        chk("  4시간: 많은 순 다섯 줄 (넘치는 것은 뺀다) · 지금 미끼에 '· 미끼'", four == want, four)
        berry_rows = [r for r in rows if r and r.get("command")]
        chk("  묶음마다 5줄까지 (4h 다섯 · 8h 하나 · 16h 하나) · 노력치 열매 · 다른 도구 빠짐",
            len(berry_rows) == 7 and not any("×9" in r["text"] for r in berry_rows),     # POMEGBERRY ×9 (노력치 열매)
            [r["text"] for r in berry_rows])
        U.close_all()
        settle(root)
        berry_rows[0]["command"]()
        chk("고르면 garden_plant(0, 'ORANBERRY')", pump(root, lambda: app.api.last("plant") == ("plant", 0, "ORANBERRY")),
            app.api.calls[-2:])
        chk("  카드대로 새싹", pump(root, lambda: gd._pots()[0].get("stage") == 1), gd._pots()[0])
        chk("  '오랭열매를 심었어요'", pump(root, lambda: app.said("오랭열매를 심었어요")), [f[2] for f in app.floats[-3:]])
    rows = gd.plant_rows(1, FI.baits({"bag": {}}))
    chk("가진 지닌 열매가 없으면 그렇다고", texts(rows) == ["가진 지닌 열매가 없습니다"], texts(rows))

    print("=== 4. 자라는 화분 → garden_water 한 번 ===")
    c = gcard([growing(0, stage=1, wet=0, needs=True), growing(1, "CHERIBERRY", stage=2, wet=1, needs=True),
               growing(2, "LUMBERRY", stage=3, wet=7, needs=False)])
    put(app, c)
    after = gcard([growing(0, stage=1, wet=1, needs=False), growing(1, "CHERIBERRY", stage=2, wet=3, needs=False),
                   growing(2, "LUMBERRY", stage=3, wet=7, needs=False)])
    app.api.water_r = {"watered": 2, "card": after}
    n = app.api.n("water")
    press(root, p, 1)
    chk("누르면 garden_water 한 번", pump(root, lambda: app.api.n("water") == n + 1) and settle(root, 0.2) is None
        and app.api.n("water") == n + 1, app.api.n("water") - n)
    chk("  물뿌리개는 물이 필요했던 화분 위 (0 · 1)", p.look is not None and p.look[1] == "water"
        and p.look[2] == (0, 1), p.look and p.look[1:])
    chk("  카드대로 물방울이 찬다", gd._pots()[1]["wetMask"] == 3)
    chk("  물뿌리개가 끝나면 다시 그대로", pump(root, lambda: p.look[1] == "idle", 4), p.look[1:])
    app.api.water_r = {"watered": 0, "card": after}
    press(root, p, 2)
    chk("줄 화분이 없으면(watered 0) '물은 넉넉해요'", pump(root, lambda: app.said("물은 넉넉해요")),
        [f[2] for f in app.floats[-3:]])

    print("=== 5. 익은 화분 → garden_harvest(True) ===")
    put(app, gcard([ripe(0), growing(1, "CHERIBERRY"), ripe(2, "SITRUSBERRY", wet=0)]))
    app.api.harvest_r = {"got": [{"berry": "ORANBERRY", "kr": "오랭열매", "n": 4}], "replanted": [0],
                         "capped": False, "card": gcard([growing(0, stage=1, needs=True), growing(1, "CHERIBERRY"),
                                                         ripe(2, "SITRUSBERRY", wet=0)], harvested=4)}
    press(root, p, 0)
    chk("누르면 garden_harvest(replant=True)", pump(root, lambda: app.api.last("harvest") == ("harvest", True)),
        app.api.calls[-2:])
    chk("  '+4 오랭열매 · 다시 심음'", pump(root, lambda: app.said("+4 오랭열매 · 다시 심음")),
        [f[2] for f in app.floats[-3:]])
    chk("  카드대로 다시 새싹", gd._pots()[0]["stage"] == 1)

    print("=== 6. 하루 천장 ===")
    put(app, gcard([ripe(0), pot(1), pot(2)], harvested=20))
    chk("천장이면 익은 화분 마우스 올림이 '오늘은 20개를 다 거뒀어요 · 0시부터 다시'",
        gd.tip_text(0) == "오늘은 20개를 다 거뒀어요 · 0시부터 다시", gd.tip_text(0))
    app.api.harvest_r = {"got": [], "replanted": [], "capped": True, "card": app.api.gcard}
    press(root, p, 0)
    chk("  눌러도 서버가 capped 면 그 글", pump(root, lambda: app.said("오늘은 20개를 다 거뒀어요")),
        [f[2] for f in app.floats[-3:]])
    # 거두다가 천장에 닿으면 거둔 글과 함께 천장 글도 바로 뜬다 (실제 앱 시험 11/27)
    n0 = len(app.floats)
    put(app, gcard([ripe(0), ripe(1, "SITRUSBERRY"), pot(2)], harvested=18))
    app.api.harvest_r = {"got": [{"berry": "ORANBERRY", "kr": "오랭열매", "n": 4}], "replanted": [0], "capped": True,
                         "card": app.api.gcard}
    press(root, p, 0)
    pump(root, lambda: len(app.floats) >= n0 + 2)
    new = [f[2] for f in app.floats[n0:]]
    chk("  거두다 천장에 닿으면 '+4 오랭열매 …' 와 천장 글 둘 다",
        any("+4 오랭열매" in t for t in new) and any("오늘은 20개를 다 거뒀어요" in t for t in new), new)
    put(app, gcard([ripe(0), growing(1, "ORANBERRY", stage=3, wet=3, left=4200), pot(2)], harvested=4))
    chk("마우스 올림: 빈 화분 '눌러서 열매 심기'", gd.tip_text(2) == "눌러서 열매 심기", gd.tip_text(2))
    chk("  익음 '다 익었어요! 누르면 거둬요'", gd.tip_text(0) == "다 익었어요! 누르면 거둬요", gd.tip_text(0))
    chk("  자라는 중 '오랭열매 · 꽃 · 1시간 10분 남음 · 물 ●●○'",
        gd.tip_text(1) == "오랭열매 · 꽃 · 1시간 10분 남음 · 물 ●●○", gd.tip_text(1))
    p.label.event_generate("<Enter>", x=ART.pot_x(1), y=10)
    settle(root, 0.05)
    chk("  올리면 그 화분 글 창이 뜬다", gd.tip is not None and gd.tip.winfo_exists() and gd._tip_slot == 1)
    p.label.event_generate("<Motion>", x=ART.pot_x(2), y=10)
    settle(root, 0.05)
    chk("  옆 화분으로 옮기면 글이 바뀐다", gd._tip_slot == 2)
    p.label.event_generate("<Leave>")
    settle(root, 0.05)
    chk("  내리면 사라진다", gd.tip is None)

    print("=== 쓰기 오류 ===")
    put(app, gcard())
    app.api.err = Err(409, "이미 심은 화분입니다.")
    n = app.api.n("garden")
    gd.plant(0, "ORANBERRY")
    chk("심기 409 → 그 글 · 카드를 다시 묻는다", pump(root, lambda: app.said("이미 심은 화분입니다") and
                                                    app.api.n("garden") > n), app.api.calls[-3:])


# ---------------------------------------------------------------- 7~8. 카드대로 그림 · nextIn
def look_part(root, ov, app):
    print("=== 7. 카드대로 그린다 (단계 다섯 · 물방울 · 젖은 흙 · 익음 반짝) ===")
    gd = app.garden
    p = gd.planter
    c = gcard([pot(0), growing(1, "ORANBERRY", stage=2, wet=2, needs=False), ripe(2, "CHERIBERRY", wet=5, fb=1)])
    put(app, c)
    settle(root, 0.1)
    want = ((0, None, 0, 0), (2, "ORANBERRY", 2, 0), (4, "CHERIBERRY", 5, 1))
    chk("모습 = 카드의 (단계, 열매, wetMask, friendBonus)", p.look[0] == want and p.look[3] is False, p.look)
    fr = ART.frames(want, KEY)
    s = ART.SCALE

    def drops(slot, color, im):
        cx = ART.POT_CX[slot]
        return count(im, color, ((cx - 6) * s, ART.DROP_Y * s, (cx + 6) * s, (ART.DROP_Y + 3) * s))
    full = drops(1, ART.DROP_C, fr[0])
    chk("물방울 ●○○ 아니고 ○●○ (줄기만 물) - 찬 방울 하나", full > 0 and drops(2, ART.DROP_C, fr[0]) == 2 * full
        and drops(0, ART.DROP_C, fr[0]) == 0, (full, drops(2, ART.DROP_C, fr[0])))
    chk("  지금 단계(줄기)에 물을 줬으면 흙이 짙다", count(fr[0], ART.WET_C) > 0)
    dry = ART.frames(((0, None, 0, 0), (2, "ORANBERRY", 1, 0), (0, None, 0, 0)), KEY)[0]
    chk("  지난 단계에만 줬으면 마른 흙", count(dry, ART.WET_C) == 0)
    chk("  친구 물 보너스면 금빛 별", count(fr[0], ART.GOLD) > 0)
    sp = [count(f, ART.SPARK) for f in fr]
    chk("익은 화분은 반짝인다 (장마다 자리가 다르다)", min(sp) > 0 and len(set(f.tobytes() for f in fr)) >= 3, sp)
    raw = ART.frames(((1, "ORANBERRY", 0, 0),) * 3, KEY)
    chk("  안 익었으면 반짝임 없음", all(count(f, ART.SPARK) == 0 for f in raw))
    berry = ART.berry_color("CHERIBERRY")
    chk("  열매 빛깔은 심은 열매 빛깔", count(fr[0], berry) > 0 and count(fr[0], ART.berry_color("ORANBERRY")) == 0)
    chk("창이 그 그림을 보인다 (장이 바뀐다)", pump(root, lambda: p.frame_i >= 6, 2) and p.look[0] == want)

    print("=== 8. nextIn 에 다시 묻는다 ===")
    gd.NEXT_SLACK_MS = 0
    n = app.api.n("garden")
    put(app, gcard([growing(0, left=1)], next_in=1))
    chk("nextIn 이 지나면 GET /api/garden", pump(root, lambda: app.api.n("garden") == n + 1, 3), app.api.n("garden") - n)
    put(app, gcard([growing(0)], next_in=99999))
    chk("  6시간 넘으면 6시간 뒤로", 0 < gd._next_s <= 6 * 3600, gd._next_s)
    put(app, gcard())
    chk("  nextIn 이 없으면 예약 없음", "next" not in gd._jobs)
    gd.NEXT_SLACK_MS = 1500

    print("=== 동기화 카드 ===")
    put(app, gcard([growing(0, stage=1)]))
    gd._acted = time.time()
    gd.note(gcard([ripe(0)]))
    chk("방금 무엇을 했으면 그 전에 떠난 동기화 카드는 안 믿는다", gd._pots()[0]["stage"] == 1)
    gd._acted = 0
    gd.note(gcard([ripe(0)]))
    chk("  아니면 따른다", gd._pots()[0]["stage"] == 4)
    gd._acted = time.time()
    gd.note(None)
    chk("  닫힘(None)은 그대로 믿는다 - 화단을 걷는다", gd.planter is None and not gd.open)
    gd._acted = 0
    gd.note(gcard())
    settle(root)
    chk("  다시 열리면 다시 뜬다", gd.planter is not None)


# ---------------------------------------------------------------- 9. 오른클릭 메뉴 (맥 길) · 뽑기 · 옮기기 · 숨기기
def menu_part(root, ov, app):
    print("=== 9. 오른쪽 클릭 메뉴 (맥 길) ===")
    gd = app.garden
    p = gd.planter
    for i, pet in enumerate(ov.pets.values()):          # 걸어다니는 도트는 화단에서 멀리
        pet.x, pet.y = AREA[2] - 60 - 50 * i, AREA[1] + 5
        pet.place()
    put(app, gcard([pot(0), growing(1, stage=1, needs=False), ripe(2)]))
    with Spy() as spy:
        num = getattr(p.view, "win_number", None)
        cx, cy = p.x + ART.pot_x(0), p.y + p.fh - 20
        if num is not None:
            app._right_click_at(cx, cy, num)
            chk("창 번호로 화단을 찾아 메뉴를 연다", pump(root, lambda: len(spy.opened) == 1, 2), spy.opened)
            U.close_all()
            settle(root)
        app._right_click_at(cx, cy, -12345)
        chk("테두리 상자로도 찾는다", pump(root, lambda: len(spy.opened) == (2 if num is not None else 1), 2),
            len(spy.opened))
        rows = spy.opened[-1]
        t = texts(rows)
        chk("메뉴 넷: 심을 열매 · 뽑기 · 텃밭 옮기기 · 텃밭 숨기기",
            all(x in t for x in ("심을 열매", "뽑기", "텃밭 옮기기", "텃밭 숨기기")), t)
        chk("  빈 화분: 심을 열매 아래 묶음 · 열매 줄 (누르면 심는다)", any(r and r.get("command") and "×12" in r["text"]
                                                            for r in rows), t)
        pull = next(r for r in rows if r and r.get("text") == "뽑기")
        chk("  빈 화분은 뽑기를 못 누른다", pull.get("enabled") is False)
        U.close_all()
        settle(root)
        # 도트가 화단 위에 겹쳐 있으면 (번호가 안 맞을 때) 도트가 먼저
        dot = type("D", (), {})()
        dot.x, dot.y, dot.fw, dot.fh = cx - 10, cy - 10, 20, 20
        dot.view = type("V", (), {"win_number": -1})()
        got = []
        dot.on_menu = lambda e: got.append(e)
        ov.extra.append(dot)
        try:
            n = len(spy.opened)
            app._right_click_at(cx, cy, -999)
            settle(root, 0.3)
            chk("  테두리 상자로만 맞으면 그 위의 도트에게 양보한다", got and len(spy.opened) == n, (got, len(spy.opened)))
        finally:
            ov.extra.remove(dot)
        # 새싹 화분: 뽑기 → garden_pull(1) → 씨앗을 돌려받는다
        app._right_click_at(p.x + ART.pot_x(1), cy, -12345)
        pump(root, lambda: len(spy.opened) >= 3 and spy.opened[-1] is not rows, 2)
        rows = spy.opened[-1]
        plant = next(r for r in rows if r and r.get("text") == "심을 열매")
        chk("  심은 화분: 심을 열매는 죽은 줄", plant.get("enabled") is False and not plant.get("command"))
        pull = next(r for r in rows if r and r.get("text") == "뽑기")
        U.close_all()
        app.api.pull_refunded = True
        pull["command"]()
        chk("뽑기 → garden_pull(1) → 빈 화분", pump(root, lambda: app.api.last("pull") == ("pull", 1)
                                                and gd._pots()[1]["stage"] == 0), app.api.calls[-2:])
        chk("  서버가 씨앗을 돌려줬으면(refunded) '씨앗을 돌려받았어요'", pump(root, lambda: app.said("씨앗을 돌려받았어요")),
            [f[2] for f in app.floats[-3:]])

    print("=== 뽑기 글은 서버의 refunded 로만 (검토 1) ===")

    def pull_says(local_stage, refunded):
        put(app, gcard([pot(0), growing(1, stage=local_stage, needs=False)]))
        app.api.pull_refunded = refunded
        n = len(app.floats)
        gd.pull(1)
        pump(root, lambda: gd._req is None and len(app.floats) > n, 3)
        return [f[2] for f in app.floats[n:]]
    got = pull_says(1, False)                     # 앱 카드는 새싹인데 서버는 이미 줄기였다 (잠에서 깬 직후)
    chk("앱 카드가 새싹이어도 서버가 안 돌려줬으면 '뽑았어요'", "뽑았어요" in got and "씨앗을 돌려받았어요" not in got, got)
    got = pull_says(2, True)
    chk("앱 카드가 줄기여도 서버가 돌려줬으면 '씨앗을 돌려받았어요'", "씨앗을 돌려받았어요" in got, got)
    got = pull_says(1, None)
    chk("답에 refunded 칸이 없으면 씨앗 글 없이 '뽑았어요'", "뽑았어요" in got and "씨앗을 돌려받았어요" not in got, got)
    app.api.pull_refunded = None

    print("=== 텃밭 옮기기 ===")
    gd.start_move()
    settle(root)
    chk("옮기기 덮개가 뜬다", gd.moving is not None and gd.moving.winfo_exists())
    tx, ty = 800, 380
    gd.moving.event_generate("<Button-1>", x=tx - AREA[0], y=ty - AREA[1], rootx=tx, rooty=ty)
    settle(root)
    chk("누른 곳으로 옮긴다 (가운데가 그 자리)", gd.moving is None and abs(p.x + p.fw // 2 - tx) <= 1
        and abs(p.y + p.fh // 2 - ty) <= 1, (p.x, p.y))
    pos = config.load_settings().get("gardenPos")
    chk("  영역 안 비율로 저장 (gardenPos)", isinstance(pos, list) and len(pos) == 2 and 0 <= pos[0] <= 1, pos)
    new = (100, 100, 1500, 900)
    ov.area = lambda: new
    app._area_changed()
    m = ov.settings["areaMargin"]
    fx = (p.x - (new[0] + m)) / float((new[2] - m - p.fw) - (new[0] + m))
    chk("영역이 바뀌면 같은 비율로 다시 맞춘다 (app._area_changed)", abs(fx - pos[0]) < 0.01, (fx, pos))
    ov.area = lambda: AREA
    app._area_changed()
    gd.start_move()
    settle(root)
    app._right_click_at(p.x + 5, p.y + 5, -777)
    settle(root)
    chk("옮기기 중 오른쪽 클릭은 그만두기", gd.moving is None)
    gd.start_move()
    gd._end_move()
    chk("  덮개 시간 제한도 지운다", "move" not in gd._jobs)
    app.settings["gardenPos"] = None
    gd.reposition()

    print("=== 텃밭 숨기기 ===")
    win = p.win
    gd.hide_garden()
    settle(root)
    chk("숨기면 창이 없다 · 설정에 저장 (showGarden False)", gd.planter is None and not win.winfo_exists()
        and config.load_settings().get("showGarden") is False)
    app.set_show_garden(True)
    settle(root)
    chk("다시 켜면 돌아온다", gd.planter is not None)


# ---------------------------------------------------------------- 10~11. 먹이
def feed_part(root, ov, app):
    print("=== 10. 펫 메뉴 '열매 먹이기' ===")
    import poketdesktop.app as appmod
    src = open(appmod.__file__, encoding="utf-8").read()
    body = src[src.index("    def pet_menu(self, pet, event):"):src.index("    def _recall(self, pid):")]
    mac, win = body.split("        m = tk.Menu(self.root", 1)
    chk("소스: 맥(PopupMenu) 갈래에 먹이 줄", "garden_mod.menu_row(self, pet)" in body and "rows.append(feed)" in mac)
    chk("소스: 윈도(tk.Menu) 갈래에도", 'm.add_command(label=feed["text"]' in win and 'feed.get("command")' in win)
    gd = app.garden
    put(app, gcard())
    pet = ov.pets[1]
    app.settings["lastBait"] = "SITRUSBERRY"
    ev = type("E", (), {"x_root": pet.x + 10, "y_root": pet.y + 10})()
    with Spy() as spy:
        app.pet_menu(pet, ev)
        rows = spy.opened[-1]
        row = next((r for r in rows if r and r.get("text") == "열매 먹이기"), None)
        chk("내 포켓몬 메뉴에 '열매 먹이기'", row is not None and row.get("command"), texts(rows))
        U.close_all()
        row["command"]()
        chk("  누르면 feed(pid, avoid=지금 미끼)", pump(root, lambda: app.api.last("feed") == ("feed", 1, "SITRUSBERRY")),
            app.api.calls[-2:])
        chk("  '오랭열매 냠 ♥ +10 (152/255)' (그 포켓몬 머리 위)", pump(root, lambda: app.said("오랭열매 냠 ♥ +10 (152/255)")),
            [f[2] for f in app.floats[-3:]])
        f = next(f for f in app.floats if "냠" in f[2])
        chk("    그 포켓몬 위", abs(f[0] - (pet.x + pet.fw / 2.0)) <= 2 and f[1] < pet.y + 4, (f[:2], (pet.x, pet.y)))
        chk("  하트 연출", pump(root, lambda: sum(1 for f in app.floats if f[2] == "♥") >= 2, 2),
            [f[2] for f in app.floats[-4:]])
        chk("  오늘 먹였다", gd.fed_today(1))
        app.pet_menu(pet, ev)
        row = next((r for r in spy.opened[-1] if r and "열매 먹이기" in (r.get("text") or "")), None)
        chk("  다시 열면 '열매 먹이기 (오늘 줌)' 죽은 줄", row is not None and row["text"] == "열매 먹이기 (오늘 줌)"
            and row.get("enabled") is False and not row.get("command"), row)
        U.close_all()
        put(app, gcard(fed=[2]))
        app.pet_menu(ov.pets[2], ev)
        row = next((r for r in spy.opened[-1] if r and "열매 먹이기" in (r.get("text") or "")), None)
        chk("카드의 fedToday 면 죽은 줄", row is not None and row.get("enabled") is False, row)
        U.close_all()
        chk("놀러 온 친구 포켓몬 · 야생(id<=0)에는 줄이 없다",
            GD.menu_row(app, type("P", (), {"id": -3})()) is None and GD.menu_row(app, type("P", (), {"id": 0})()) is None)
        app.api.feed_err = Err(409, "오늘은 이미 열매를 먹였습니다.")
        n = app.api.n("garden")
        gd.feed(ov.pets[2])
        chk("먹이 오류 → 그 글 (머리 위) · 카드를 다시 묻는다", pump(root, lambda: app.said("오늘은 이미 열매를 먹였습니다")
                                                        and app.api.n("garden") > n), [f[2] for f in app.floats[-2:]])
        gd._apply(None)
        chk("텃밭이 닫혔으면(시즌 6) 줄이 없다", GD.menu_row(app, pet) is None)
        put(app, gcard())

    print("=== 11. 먹이로 진화 ===")
    evo = {"fromKr": "이브이", "toKr": "에브이", "from": 133, "to": 196}
    app.api.feed_r = {"berry": "ORANBERRY", "kr": "오랭열매", "gain": 10, "happiness": 162, "evolve": evo}
    gd.feed(ov.pets[2])
    chk("응답에 evolve 가 있으면 app.show_evolutions([evolve + pokemonId]) (가방 진화 도구와 같은 길)",
        pump(root, lambda: app.evolutions == [[dict(evo, pokemonId=2)]]), app.evolutions)
    chk("  친밀도 · 도트를 맞추러 동기화를 부른다", app.synced > 0)
    app.api.feed_delay = 0.4
    gd.feed(ov.pets[2])
    settle(root, 0.05)
    gd.plant(1, "ORANBERRY")                     # 먹이 답을 기다리는 사이 화분을 눌렀다
    chk("먹이는 사이 화분 일을 해도 먹이 답(진화)을 버리지 않는다", pump(root, lambda: len(app.evolutions) == 2, 3),
        app.evolutions)
    app.api.feed_delay = 0.0
    app.api.feed_r = {"berry": "ORANBERRY", "kr": "오랭열매", "gain": 10, "happiness": 152, "evolve": None}


# ---------------------------------------------------------------- 윈도우 길 (tk.Menu)
def windows_part(root, ov, app):
    print("=== 윈도우 길: 심을 열매 · 화단 메뉴 · 펫 메뉴 (tk.Menu) ===")
    gd = app.garden
    p = gd.planter
    app.settings["lastBait"] = "SITRUSBERRY"
    put(app, gcard([pot(0), growing(1, stage=1, needs=False), ripe(2)]))
    with Native() as nat:
        press(root, p, 0)
        chk("빈 화분 → tk.Menu 심을 열매", pump(root, lambda: len(nat.menus) == 1, 3), app.api.calls[-2:])
        es = entries(nat.menus[-1])
        heads = [e[1] for e in es if e[2] == "disabled"]
        chk("  머리줄 4시간 · 8시간 · 16시간 은 못 누르는 줄", heads == ["4시간", "8시간", "16시간"], heads)
        live = [e[1].strip() for e in es if e[2] == "normal"]
        chk("  열매 줄 일곱 (묶음마다 다섯까지) · 미끼 표시", len(live) == 7 and live[0] == "오랭열매 ×12"
            and "자뭉열매 ×3 · 미끼" in live, live)
        n = app.api.n("plant")
        nat.menus[-1].invoke(1)
        chk("  누르면 garden_plant", pump(root, lambda: app.api.n("plant") == n + 1 and gd._req is None),
            app.api.calls[-2:])
        put(app, gcard([pot(0), growing(1, stage=1, needs=False), ripe(2)]))
        gd.on_menu(type("E", (), {"x_root": p.x + ART.pot_x(1), "y_root": p.y + 30})())
        es = entries(nat.menus[-1])
        chk("화단 메뉴(심은 화분): 심을 열매(죽음) · 뽑기 · 텃밭 옮기기 · ─ · 텃밭 숨기기",
            [(e[0], e[1], e[2]) for e in es] == [("command", "심을 열매", "disabled"), ("command", "뽑기", "normal"),
                                                ("command", "텃밭 옮기기", "normal"), ("separator", None, None),
                                                ("command", "텃밭 숨기기", "normal")], es)
        gd.on_menu(type("E", (), {"x_root": p.x + ART.pot_x(0), "y_root": p.y + 30})())
        chk("  빈 화분: 심을 열매 ▸ 하위 메뉴 (가방을 물어 만든다)", pump(root, lambda: len(nat.menus) == 3, 3))
        es = entries(nat.menus[-1])
        sub = es[0][3]
        chk("    하위 메뉴에 묶음 · 열매 줄 · 빈 화분은 뽑기를 못 누른다", es[0][0] == "cascade" and es[0][1] == "심을 열매"
            and sub is not None and "4시간" in [e[1] for e in entries(sub)] and es[1][1] == "뽑기"
            and es[1][2] == "disabled", es)
        pet = ov.pets[1]
        put(app, gcard())
        ev = type("E", (), {"x_root": pet.x + 10, "y_root": pet.y + 10})()
        app.pet_menu(pet, ev)
        es = entries(nat.menus[-1])
        row = next((e for e in es if e[1] and "열매 먹이기" in e[1]), None)
        chk("펫 메뉴(tk.Menu): '열매 먹이기'", row is not None and row[1] == "열매 먹이기" and row[2] == "normal", es)
        put(app, gcard(fed=[1]))
        app.pet_menu(pet, ev)
        es = entries(nat.menus[-1])
        row = next((e for e in es if e[1] and "열매 먹이기" in e[1]), None)
        chk("  오늘 줌이면 '열매 먹이기 (오늘 줌)' 죽은 줄 (메뉴가 통째로 안 열리지 않는다)",
            row is not None and row[1] == "열매 먹이기 (오늘 줌)" and row[2] == "disabled", es)
    put(app, gcard())


# ---------------------------------------------------------------- 동작 · 카드 묻기 엇갈림 (검토 5)
def race_part(root, ov, app):
    print("=== 동작 중에 떠난 카드 묻기는 동작의 새 카드를 덮지 않는다 ===")
    gd = app.garden
    api = app.api
    put(app, gcard([ripe(0)]))
    after = gcard([growing(0, stage=1, needs=False)])
    api.harvest_r = {"got": [{"berry": "ORANBERRY", "kr": "오랭열매", "n": 4}], "replanted": [0], "capped": False,
                     "card": after}
    api.harvest_delay = 0.1
    api.garden_reply = gcard([ripe(0)])          # GET 은 거두기 전 줄을 읽었다
    api.garden_delay = 0.5
    try:
        gd.harvest(0)
        gd.refresh()                             # nextIn 타이머 · pushfresh · resume 이 거두는 사이에 묻는다
        pump(root, lambda: gd._req is None and not gd._loading, 3)
        settle(root, 0.1)
        chk("거두기 답 뒤에 온 옛 카드를 버린다 (익은 화분이 되살아나지 않는다)",
            not gd._pots()[0].get("ripe") and gd._pots()[0].get("stage") == 1, gd._pots()[0])
        put(app, gcard())
        api.garden_reply = gcard()                # 먹이기 전 줄 (fedToday 없음)
        gd.refresh()
        gd.feed(ov.pets[1])
        pump(root, lambda: not gd._loading and not gd._feeding, 3)
        settle(root, 0.1)
        chk("먹이 뒤에 온 옛 카드가 '오늘 줌' 을 되돌리지 않는다", gd.fed_today(1), (gd.card or {}).get("fedToday"))
        api.garden_reply, api.garden_delay = None, 0.0
        api.gcard = gcard([pot(0), pot(1), growing(2)])
        n = api.n("garden")
        gd.refresh()
        chk("동작이 없으면 묻은 카드는 그대로 받는다", pump(root, lambda: api.n("garden") > n and not gd._loading
                                                 and gd._pots()[2].get("stage") == 2, 3), gd._pots())
    finally:
        api.garden_reply, api.garden_delay, api.harvest_delay, api.harvest_r = None, 0.0, 0.0, None
    put(app, gcard())


# ---------------------------------------------------------------- 12~13. 친구 화단 · 주인 쪽 물
def friend_part(root, ov, app):
    print("=== 12. show_friend ===")
    gd = app.garden
    put(app, gcard([growing(0)]))
    app.visit.active = app.visit.guest = True
    app.wild.stop()                              # 놀러 갈 때 풀숲과 함께 쉰다 (visit._enter_guest)
    settle(root)
    chk("놀러 가 있으면 내 화단은 숨는다", gd.planter is None and gd.paused)
    gd.show_friend(G_CAN)
    settle(root)
    p = gd.planter
    chk("친구 화단이 내 화단 자리에 흐리게", p is not None and gd.mode == "friend" and p.look[3] is True
        and (p.x, p.y) == gd.home(p.fw, p.fh), p and p.look)
    chk("  친구 화분 모습 (물방울 없이)", p.look[0] == ((2, "ORANBERRY", None, 0), (0, None, None, 0),
                                                  (4, "CHERIBERRY", None, 0)), p.look[0])
    chk("  마우스 올림 '눌러서 화분에 물 주기'", gd.tip_text(0) == "눌러서 화분에 물 주기", gd.tip_text(0))
    n = app.api.n("visit_water")
    press(root, p, 0)
    chk("누르면 visit_water", pump(root, lambda: app.api.n("visit_water") == n + 1), app.api.calls[-2:])
    chk("  답의 view 로 바꾸고 물뿌리개 (자라던 화분)", pump(root, lambda: gd.friend == G_DONE and p.look[1] == "water")
        and p.look[2] == (0,), p.look[1:])
    chk("  친구 물 보너스 별", pump(root, lambda: p.look[0][0] == (2, "ORANBERRY", None, 1)), p.look[0])
    press(root, p, 0)
    settle(root, 0.2)
    chk("이미 받았으면(why done) 서버를 안 부르고 그 까닭", app.api.n("visit_water") == n + 1
        and app.said("오늘은 이미 물을 받았어요"), app.api.n("visit_water") - n)
    chk("  마우스 올림도 그 까닭", gd.tip_text(1) == "오늘은 이미 물을 받았어요", gd.tip_text(1))

    print("=== 친구 화단 오른쪽 클릭: 손님 펫 메뉴와 같은 글 (검토 14 · 3 · 15) ===")
    from poketdesktop import visit as VI
    want = {"empty": "화분에 물 주기 (심은 화분 없음)", "ripe": "화분에 물 주기 (다 익은 화분뿐)",
            "bonus": "화분에 물 주기 (이미 물을 받은 화분뿐)", "done": "화분에 물 주기 (오늘 이미 받음)"}
    ev = type("E", (), {"x_root": p.x + ART.pot_x(0), "y_root": p.y + 30})()
    with Spy() as spy:
        for why, text in sorted(want.items()):
            gd.show_friend({"canWater": False, "why": why, "pots": FPOTS})
            gd.on_menu(ev)
            rows = spy.opened[-1] if spy.opened else []
            chk("why %s → '%s' 죽은 줄" % (why, text), texts(rows) == [text] and rows[0].get("enabled") is False
                and not rows[0].get("command"), texts(rows))
            chk("  펫 메뉴(visit.water_row)와 같은 글", VI.WATER_WHY.get(why) == text, VI.WATER_WHY.get(why))
            chk("  마우스 올림 글도 있다", bool(gd.tip_text(0)), gd.tip_text(0))
            U.close_all()
        gd.show_friend(G_CAN)
        gd.on_menu(ev)
        rows = spy.opened[-1]
        chk("줄 수 있으면 '화분에 물 주기' (누를 수 있다)", texts(rows) == ["화분에 물 주기"] and rows[0].get("command"),
            texts(rows))
        U.close_all()
    gd.show_friend(G_DONE)
    settle(root)
    real_visit = app.visit
    app.visit = WaterVisit()
    gd.show_friend(G_CAN)
    press(root, p, 1)
    chk("놀러 가기(Visit.water)가 있으면 그 길로 (메뉴 줄과 한 길)", app.visit.waters == 1
        and app.api.n("visit_water") == n + 1, (app.visit.waters, app.api.n("visit_water") - n))
    gd.show_friend(G_DONE)                       # Visit.water 의 답이 view 를 다시 넘긴다
    chk("  그 답의 view 가 오면 물뿌리개", p.look[1] == "water", p.look[1:])
    app.visit = real_visit
    gd.show_friend(None)
    app.visit.active = app.visit.guest = False
    app.wild.start()
    chk("None + 돌아오면 내 화단이 돌아온다", pump(root, lambda: gd.planter is not None and gd.mode == "mine"
                                             and gd.planter.look[3] is False), gd.mode)

    print("=== 13. play_water · spot (주인 쪽) ===")
    put(app, gcard([growing(0), pot(1), growing(2, "CHERIBERRY", stage=3)]))
    p = gd.planter
    sx, sy = gd.spot()
    chk("spot(): 화단 옆 발 자리 (바닥 줄 · 화단과 안 겹친다)", sy == p.y + p.fh and (sx >= p.x + p.fw + 10 or sx <= p.x - 10)
        and AREA[0] <= sx <= AREA[2], ((sx, sy), (p.x, p.y, p.fw, p.fh)))
    gd.PUSH_REFRESH_MS = 150
    n = app.api.n("garden")
    chk("play_water('지우') → 물뿌리개 (자라는 화분)", gd.play_water("지우") is True and p.look[1] == "water"
        and p.look[2] == (0, 2), p.look[1:])
    chk("  '지우 님이 화분에 물을 줬어요 +1'", app.said("지우 님이 화분에 물을 줬어요 +1"), [f[2] for f in app.floats[-2:]])
    chk("  조금 뒤 카드를 다시 본다 (친구 물 보너스)", pump(root, lambda: app.api.n("garden") > n, 2))
    app.set_show_garden(False)
    settle(root)
    chk("화단이 숨겨져 있으면 spot() None · play_water False (말풍선은 놀러 가기 몫)",
        gd.spot() is None and gd.play_water("지우") is False)
    app.set_show_garden(True)
    settle(root)


# ---------------------------------------------------------------- 14. 피하기
def avoid_part(root, ov, app):
    print("=== 14. 풀숲 · 알이 연못과 화단을 둘 다 피한다 ===")
    gd = app.garden
    fz = app.fishing
    g_rect, p_rect = gd.rect(), fz.rect()
    chk("연못 · 화단이 다 떠 있다", g_rect is not None and p_rect is not None, (g_rect, p_rect))
    chk("overlay.avoid_rects() 에 둘 다", g_rect in ov.avoid_rects() and p_rect in ov.avoid_rects(), ov.avoid_rects())
    seq = [g_rect[0] + 2, g_rect[1] + 2, p_rect[0] + 2, p_rect[1] + 2, AREA[0] + 400, AREA[1] + 20]
    real = wild_ui.random.randint
    wild_ui.random.randint = lambda a, b: max(a, min(b, seq.pop(0))) if seq else real(a, b)
    try:
        g = wild_ui.GrassPatch(app.wild, {"id": 1})
    finally:
        wild_ui.random.randint = real
    box = (g.x, g.y, g.x + g.fw, g.y + g.fh)
    chk("풀숲은 화단 · 연못 어느 쪽과도 안 겹친다 (화단 → 연못 → 빈 자리)", not overlaps(box, g_rect)
        and not overlaps(box, p_rect) and not seq, (box, g_rect, p_rect, seq))
    g.destroy()
    anim = sprites.load_animation(dot_path(), 40, 0.5, 4.0)
    egg = eggs_ui.EggPet(ov, {"id": 7, "kind": "legendary", "name": "알", "gotSec": 1, "needSec": 9, "leftSec": 8}, anim)
    for r in (g_rect, p_rect):
        egg.x, egg.y = r[0] + 4, r[1] + 4
        ov.dodge(egg)
        e = (egg.x, egg.y, egg.x + egg.fw, egg.y + egg.fh)
        chk("알도 비켜난다 (%s)" % ("화단" if r is g_rect else "연못"), not overlaps(e, g_rect) and not overlaps(e, p_rect),
            (e, r))
    egg.destroy()
    ov.avoid = fz.rect
    chk("avoid 가 하나(옛 모양)여도 된다", ov.avoid_rects() == [p_rect], ov.avoid_rects())
    ov.avoid = [fz.rect, gd.rect]


# ---------------------------------------------------------------- 15. 설정 · 트레이 · 안내
def walk(w):
    yield w
    for c in w.winfo_children():
        for x in walk(c):
            yield x


def settings_part(root, ov, app):
    print("=== 15. 설정 · 트레이 '텃밭 보이기' ===")
    from poketdesktop import tray as TR
    from poketdesktop import ui_settings as ST
    from poketdesktop.skins.dp import settings as DPS
    gd = app.garden
    tray = type("T", (), {"call": lambda self, fn, *a: fn(*a)})()
    gd.open = False
    chk("트레이: 텃밭이 열리기 전엔 줄이 없다", TR.garden_items(tray, app) == [])
    sw = ST.SettingsWindow(app)
    settle(root)
    labels = [w.cget("text") for w in walk(sw.win) if isinstance(w, tk.Checkbutton)]
    chk("설정(기본): 열리기 전엔 줄이 없다", "텃밭 보이기" not in labels, labels)
    sw.close()
    gd.open = True
    items = TR.garden_items(tray, app)
    chk("트레이: 열리면 '텃밭 보이기' (켜짐 표시)", len(items) == 1 and items[0].text == "텃밭 보이기"
        and items[0].checked() is True)
    sub = TR.with_garden(tray, app, ["a", "b"])
    chk("  '바탕화면' 하위 메뉴 끝 (낚시터 보이기 다음)", sub[:2] == ["a", "b"] and sub[2].text == "텃밭 보이기")
    src = open(TR.__file__, encoding="utf-8").read()
    chk("  하위 메뉴가 with_garden 으로 감싸인다 (맥 트레이도 같은 spec)",
        'Item("바탕화면", submenu=with_garden(self, a, [' in src and "] + pond_items(self, a)))" in src)
    sw = ST.SettingsWindow(app)
    app.settings_win = sw
    settle(root)
    labels = [w.cget("text") for w in walk(sw.win) if isinstance(w, tk.Checkbutton)]
    chk("설정(기본): '낚시터 보이기' 바로 아래 '텃밭 보이기'", "텃밭 보이기" in labels
        and labels.index("텃밭 보이기") == labels.index("낚시터 보이기") + 1, labels)
    items[0].action()
    settle(root)
    chk("트레이에서 끄면 화단이 걷히고 저장 · 설정 창 표시도 맞춘다", gd.planter is None
        and config.load_settings()["showGarden"] is False and sw.garden.get() is False)
    sw.garden.set(True)
    sw._toggle_garden("showGarden", sw.garden)
    settle(root)
    chk("설정 창에서 켜면 바로 뜬다", gd.planter is not None and config.load_settings()["showGarden"] is True)
    sw.close()
    app.settings_win = None
    dw = DPS.SettingsWindow(app)
    settle(root)
    names = [r["label"] for r in dw.rows]
    chk("설정(DP): '낚시터 보이기' 바로 아래 '텃밭 보이기'", "텃밭 보이기" in names
        and names.index("텃밭 보이기") == names.index("낚시터 보이기") + 1, names)
    row = dw.rows[names.index("텃밭 보이기")]
    row["put"](False)
    settle(root)
    chk("  DP 에서 끄기", gd.planter is None and row["get"]() is False)
    row["put"](True)
    settle(root)
    chk("  DP 에서 다시 켜면 뜬다", gd.planter is not None and row["get"]() is True)
    dw.close()
    settle(root)
    chk("기본값으로 되돌리기에도 안내 단계(gardenHints)는 남긴다",
        '"lastBait", "pondHints", "gardenHints"' in open(ST.__file__, encoding="utf-8").read())

    print("=== 처음 값 · 안내 셋 ===")
    chk("config.show_garden: 안 정했으면 낚시터 보이기를 따른다",
        config.show_garden({"showGarden": None, "showPond": False}) is False
        and config.show_garden({"showGarden": None, "showPond": None, "showGrass": True}) is True
        and config.show_garden({"showGarden": True, "showPond": False}) is True)
    chk("기본 설정에 showGarden None · gardenPos None · gardenHints 0",
        config.DEFAULTS.get("showGarden", 1) is None and config.DEFAULTS.get("gardenPos", 1) is None
        and config.DEFAULTS.get("gardenHints") == 0)
    from poketdesktop.visit import Bubble as VI_Bubble
    s = app.settings
    fz = app.fishing
    lead = next(iter(ov.pets.values()))
    gh = lambda: int(s.get("gardenHints") or 0)                     # noqa: E731
    s["gardenHints"] = 0
    s["pondHints"] = 0
    s.pop("pondHintAt", None)
    gd.HINT_MS = 50
    gd.HINT_RETRY_MS = 100
    gd.POND_GAP_MS = 10 ** 7
    gd.BUBBLE_GAP_S = 0.0
    gd.BUBBLE_MS = fz.BUBBLE_MS = 150            # 안내 말풍선이 떠 있는 동안은 다음 안내가 기다린다 - 여기서는 짧게
    gd.clear()
    put(app, gcard())
    settle(root, 0.4)
    chk("연못 안내가 아직이면 텃밭 첫 안내는 기다린다", gh() == 0 and fz.pond is not None, (gh(), fz.pond))
    t0 = time.time()
    fz._hint(1, FI.HINT_FIRST)                   # 연못 첫 안내가 떴다
    at = s.get("pondHintAt")
    chk("연못 안내가 뜬 때를 설정에 남긴다 (pondHintAt)", int(s.get("pondHints") or 0) == 1 and isinstance(at, float)
        and t0 <= at <= time.time() and config.load_settings().get("pondHintAt") == at, at)
    gd.POND_GAP_MS = 900                         # 설계 '연못 안내가 끝난 뒤 10분' (여기서는 0.9초)
    settle(root, 0.5)
    chk("  연못 안내 뒤 10분(여기선 0.9초)이 안 지났으면 아직", gh() == 0, gh())
    chk("연못 안내 뒤 10분이 지나면: '화분을 눌러 열매를 심어 보세요'", pump(root, lambda: gh() == 1, 3)
        and time.time() - at >= 0.9 and GD.HINT_FIRST == "화분을 눌러 열매를 심어 보세요", (gh(), time.time() - at))
    s["pondHintAt"] = time.time() - 3600         # 이 뒤로는 연못 간격이 막지 않는다 - 말풍선 간격만 본다
    gd.BUBBLE_GAP_S = 0.9
    VI_Bubble(root, lead, "다른 말풍선", ms=300)    # 같은 포켓몬 위에 방금 다른 말풍선 (놀러 가기 · 알람 · 연못 …)
    gd.plant(0, "ORANBERRY")
    settle(root, 0.5)
    chk("같은 포켓몬 위에 다른 말풍선이 8초(여기선 0.9초) 안에 떴으면 '물' 안내는 기다린다 (단계도 안 남긴다)",
        gh() == 1 and config.load_settings().get("gardenHints") == 1, gh())
    chk("  지나면 '단계마다 물을 주면 열매가 늘어요'", pump(root, lambda: gh() == 2, 3)
        and GD.HINT_WATER == "단계마다 물을 주면 열매가 늘어요", gh())
    gd.BUBBLE_GAP_S = 0.0

    print("=== 처음 켠 PC 에 익은 화분이 있어도 연못 안내가 먼저 (검토 7 · 16) ===")
    s["gardenHints"] = 0
    s["pondHints"] = 0
    s.pop("pondHintAt", None)
    config.save_settings(s)
    gd.POND_GAP_MS = 10 ** 7
    gd.clear()
    put(app, gcard([ripe(0)]))
    settle(root, 0.4)
    chk("연못 안내가 아직이면 '다 익었어요' 도 바로 띄우지 않고 단계도 안 남긴다", gh() == 0
        and config.load_settings().get("gardenHints") == 0, gh())
    fz._hint(1, FI.HINT_FIRST)
    gd.POND_GAP_MS = 700
    settle(root, 0.4)
    chk("  연못 안내 바로 뒤에도 아직 (같은 포켓몬 위에 겹치지 않게)", gh() == 0, gh())
    chk("  10분(여기선 0.7초) 뒤 '다 익었어요! 눌러서 거둬요'", pump(root, lambda: gh() == 3, 3)
        and GD.HINT_RIPE == "다 익었어요! 눌러서 거둬요" and config.load_settings().get("gardenHints") == 3, gh())
    s["gardenHints"] = 1
    s["pondHintAt"] = time.time()
    gd.POND_GAP_MS = 400
    put(app, gcard([ripe(0)]))
    settle(root, 0.1)
    put(app, gcard([growing(0, stage=1)]))         # 기다리는 사이에 거두고 다시 심었다
    chk("기다리는 사이 다 거뒀으면 '다 익었어요' 대신 지금 맞는 안내 ('물')", pump(root, lambda: gh() >= 2, 3) and gh() == 2,
        gh())
    gd.POND_GAP_MS = 10 ** 7


# ---------------------------------------------------------------- 앱 이음
def wiring_part(root, app):
    print("=== 앱 이음 ===")
    import poketdesktop.app as appmod
    src = open(appmod.__file__, encoding="utf-8").read()
    chk("동기화: me['garden'] → garden.note (옛 서버는 칸이 없다)",
        'if "garden" in me and getattr(self, "garden", None) is not None:' in src
        and 'self.garden.note(me.get("garden"))' in src)
    chk("start_ui: 텃밭을 낚시 뒤 · wild.start() 보다 먼저 만든다",
        src.index("FishingController(self)") < src.index("GardenController(self)")
        < src.index("        self.wild.start()\n        self.resume_battle()"))
    chk("  알 · 풀숲이 연못과 화단을 둘 다 피한다 (avoid 목록)",
        "self.overlay.avoid = [self.fishing.rect, self.garden.rect]" in src)
    chk("로그아웃 · 세션 끊김 · 종료가 텃밭을 치운다", src.count("        self._clear_garden()") == 3,
        src.count("        self._clear_garden()"))
    chk("영역이 바뀌면 화단도 다시 놓는다", "self.garden.reposition()" in
        src[src.index("    def _area_changed(self):"):src.index("    def set_show_grass(self, on):")])
    gd = app.garden
    app.wild.stop()
    chk("wild.stop() 이 텃밭도 멈춘다 (화단을 걷는다)", gd.paused and gd.planter is None)
    app.wild.start()
    chk("wild.start() 가 텃밭을 다시 연다 (카드를 묻는다)", pump(root, lambda: gd.planter is not None and not gd.paused))


# ---------------------------------------------------------------- 16. 정리
def clean_part(root, ov, app, errors):
    print("=== 16. 정리 ===")
    gd = app.garden
    put(app, gcard([growing(0), ripe(1)], next_in=600))
    p = gd.planter
    p.label.event_generate("<Enter>", x=ART.pot_x(0), y=10)
    gd.play_water("지우")
    gd.start_move()
    settle(root, 0.3)
    wins = [w for w in (p.win, gd.tip, gd.moving) if w is not None]
    ids = list(gd._jobs.values())
    chk("정리 전: 창 · 타이머가 있다", len(wins) >= 2 and ids, (len(wins), ids))
    gd.clear()
    settle(root, 0.2)
    chk("clear(): 화단 · 글 · 덮개 창이 남지 않는다", not any(w.winfo_exists() for w in wins))
    pending = str(root.tk.call("after", "info"))
    chk("  남은 after 가 없다", not gd._jobs and not any(str(i) in pending.split() for i in ids), (gd._jobs, ids))
    chk("  다시 카드가 오기 전에는 아무것도 안 띄운다", gd.planter is None and not gd.open and gd.friend is None)
    gd.note(gcard())
    settle(root)
    chk("다시 로그인하면 다시 뜬다", gd.planter is not None)
    gd.note(None)
    settle(root)
    chk("카드가 없으면(열리기 전 · 옛 서버) 화단을 걷는다", gd.planter is None and not gd.open)
    chk("그리는 중 예외 없음", gd.errors == 0 and not errors, (gd.errors, errors[:2]))


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-600:])
    root.report_callback_exception = on_err
    U.init_fonts(root)
    U.apply_theme(root)
    settings = dict(config.DEFAULTS)
    settings["areaRect"] = list(AREA)
    ov = OV.Overlay(root, settings)
    ov.area = lambda: AREA
    path = dot_path()
    ov.paths[(25, False)] = path
    ov.sync([mon(1), mon(2, "이브이")], {})
    real_ensure, real_walk = sprite_cache.ensure, walk_cache.ensure
    sprite_cache.ensure = lambda api, num, shiny=False, back=False: path
    walk_cache.ensure = lambda *a, **k: (None, None)
    app = MiniApp(root, ov)
    app.fishing.HINT_MS = 50
    app.garden.HINT_MS = 10 ** 7                 # 안내는 settings_part 에서 따로 본다
    random.seed(5)
    try:
        art_part()
        place_part(root, ov, app)
        narrow_part(root, ov, app)
        plant_part(root, ov, app)
        look_part(root, ov, app)
        menu_part(root, ov, app)
        feed_part(root, ov, app)
        windows_part(root, ov, app)
        race_part(root, ov, app)
        friend_part(root, ov, app)
        avoid_part(root, ov, app)
        settings_part(root, ov, app)
        wiring_part(root, app)
        clean_part(root, ov, app, errors)
    finally:
        sprite_cache.ensure, walk_cache.ensure = real_ensure, real_walk
        try:
            app.wild.stop()
            app.garden.clear()
            app.fishing.clear()
            app.airraid.clear()
        except Exception:                                   # noqa: BLE001
            pass
        settle(root, 0.2)
        root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
