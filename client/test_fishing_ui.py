# -*- coding: utf-8 -*-
"""낚시 (다음 시즌, 2026-11-26) 바탕화면 검사 — 연못 · 던지기 · 입질 · 챔질 · 낚인 야생 · 메뉴 · 옮기기 · 숨기기.

    python client/test_fishing_ui.py
    python client/run_as_windows.py client/test_fishing_ui.py

**진짜 Overlay · 연못 창 · WildController 를 띄운다.** 서버는 안 띄운다 - 가짜 api 가 API 계약
(design-notes/2026-11-26-fishing-plan.md 'API 계약') 모양의 카드 · 챔질 응답을 준다. 판정은 서버가 하므로
여기서는 '카드대로 보여 주는가 · 눌렀을 때 무엇을 부르는가' 만 본다.

  1. 카드가 열리면 연못이 영역 왼쪽 아래(탐험 보따리 오른쪽, 바닥에 맞춰)에 뜨고 idle 은 낚싯대가 눕는다.
     낚시터 보이기(showPond) 는 처음에 풀숲 보이기(showGrass) 값을 따른다.
  2. 누르면(뗌 아니고 누름) fish_cast(lastBait) - 찌 그림 · 마우스 올림 글 (미끼: 오랭열매 ×11).
  3. 밀어 보낸 '입질 준비' → 막힌 것이 없으면 fish_bite → 콕콕 → 쭉 ('!' 깜빡임). 입질 동안만 앞으로 (petBehind).
  4. 콕콕 중 누르기 → '아직! …' 글.
  5. 쭉 중 누르기 → hooked → show_hooked → 연못 옆에 야생 · 무게 · '대물!' · '완벽한 챔질!'.
     쭉이 끝난 뒤 여유(late, 서버 FISH_GRACE) 동안 누르면 던지지 않고 챔질. 던지기 409 는 카드를 다시 묻는다.
     연못보다 먼저 아무 데나 선 낚인 야생은 카드가 오면 연못 옆으로 한 번 옮기고, 번호만 있고 도트가 없으면 띄운다.
  6. 풀숲을 꺼도(showGrass False) 낚인 야생은 보이고 check · set_enabled(False) · apply 가 안 지운다.
  7. 막힘(blocked 'visit')이면 bite 를 안 부르고, 풀린 뒤에 부른다. 공습 쪽 blocked() 는 입질 중이면 'fishing'.
  8. 맥 길: app._right_click_at 이 연못 메뉴를 연다 (창 번호 먼저 · 테두리 상자는 도트 다음). 미끼는 지닌 열매만.
  9. 옮기기 → 누른 곳으로 · pondPos 저장 · 영역이 바뀌면 다시 맞춘다 (_area_changed 없이 바뀌어도 스스로).
     옮기는 동안 맥 오른쪽 클릭은 그만두기 (밑의 도트에 안 넘긴다).
 10. 숨기기 → 창 없음 · 설정 저장 · 다시 켜면 돌아온다. 던져 둔(cast) 채 숨기면 줄을 거둔다 (입질 중이면 그대로).
 11. 정리 뒤 남는 창 · after 가 없다. 그리는 중 예외 없음. 풀숲 · 알은 연못 자리를 피한다.
"""
import os
import random
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-fishing-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from poketdesktop import airraid as RC                      # noqa: E402
from poketdesktop import config, eggs_ui, sprites           # noqa: E402
from poketdesktop import fishing as FI                      # noqa: E402
from poketdesktop import fishing_art as ART                 # noqa: E402
from poketdesktop import overlay as OV                      # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import sprite_cache, walk_cache, wild_ui  # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import visit as visit_mod                 # noqa: E402
from poketdesktop.app import App                            # noqa: E402

HOME = os.environ["POKET_HOME"]
OK = FAIL = 0
AREA = (300, 200, 1000, 700)


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


def card(state="idle", **kw):
    c = {"open": True, "state": state, "ready": False, "nibbleLeft": None, "strikeLeft": None,
         "bait": None, "baitLeft": 0, "wait": None, "wild": None, "ballOptions": None}
    c.update(kw)
    return c


BALLS = [{"id": "POKEBALL", "kr": "몬스터볼", "count": 5, "rate": 1.0}]


def fish_wild(wid=901, g=84200, ratio=1.31, badge="big", num=129):
    mon = {"id": 0, "num": num, "shiny": False, "fishG": g, "fishRatio": ratio, "fishSpecies": "MAGIKARP",
           "fishWeek": "2026-11-30", "fishBadge": badge,
           "info": {"name": "잉어킹", "species": "잉어킹", "level": 12, "types": ["물"]}}
    return {"id": wid, "state": "revealed", "src": "fish", "pokemon": mon, "expiresIn": 60, "expiresAt": None}


def hooked(wid=901, perfect=True, **kw):
    w = fish_wild(wid, **kw)
    return {"result": "hooked", "perfect": perfect, "src": "fish", "wild": w, "ballOptions": BALLS,
            "card": card("hooked", wild=w, ballOptions=BALLS)}


class Err(Exception):
    def __init__(self, status, message="오류"):
        Exception.__init__(self, message)
        self.status, self.message = status, message


class FakeApi(object):
    def __init__(self):
        self.calls = []
        self.card = card("idle")
        self.bite_card = card("bite", nibbleLeft=0.6, strikeLeft=4.0)
        self.hooks = []
        self.bag_r = {"bag": {"ORANBERRY": 12, "SITRUSBERRY": 3, "POMEGBERRY": 9, "POKEBALL": 5, "LEFTOVERS": 1},
                      "money": 0, "balls": 5}
        self.wild_r = {"wild": None, "nextInSeconds": 300, "balls": 5}
        self.cast_err = None        # 다음 fish_cast 한 번이 낼 오류 (409 - 다른 PC 에서 던짐 · 상자 가득)
        self.cast_delay = 0.0       # fish_cast 가 답하기까지 (요청이 오가는 중에 숨기기)

    def fish(self):
        self.calls.append(("fish",))
        return self.card

    def fish_cast(self, bait=None):
        self.calls.append(("cast", bait))
        if self.cast_delay:
            time.sleep(self.cast_delay)
        if self.cast_err is not None:
            err, self.cast_err = self.cast_err, None
            raise err
        self.card = card("cast", bait=bait, baitLeft=11 if bait else 0)
        return self.card

    def fish_bite(self):
        self.calls.append(("bite",))
        self.card = self.bite_card
        return self.card

    def fish_hook(self):
        self.calls.append(("hook",))
        r = self.hooks.pop(0)
        self.card = r.get("card") or self.card
        return r

    def fish_reel(self):
        self.calls.append(("reel",))
        self.card = card("idle")
        return self.card

    def bag(self):
        self.calls.append(("bag",))
        return self.bag_r

    def wild(self, force=False):
        self.calls.append(("wild",))
        return self.wild_r

    def wild_flee(self, wid):
        self.calls.append(("flee", wid))
        return {}

    def n(self, name):
        return sum(1 for c in self.calls if c[0] == name)


class FakeVisit(object):
    def __init__(self):
        self.active = False
        self.guest = False


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
        self.settings_win = None
        self.box_window = None
        self.raid_pillar = None
        self.notes = []
        self.floats = []
        self.wild = wild_ui.WildController(self)
        self.airraid = RC.AirRaidController(self)
        self.fishing = FI.FishingController(self)
        ov.avoid = self.fishing.rect

    def notify(self, m):
        self.notes.append(m)

    def refresh_tray(self):
        pass

    def request_sync(self):
        pass

    def on_session_lost(self):
        pass

    def float_at(self, sx, sy, text, color="#7bffa0", ms=1100):
        self.floats.append((sx, sy, text, color))
        return App.float_at(self, sx, sy, text, color, ms)

    def said(self, text):
        return any(text in f[2] for f in self.floats)

    # 설정 창이 만지는 것 (test_catch_pick_ui 의 껍데기와 같은 꼴)
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
    _area_changed = App._area_changed
    _right_click_at = App._right_click_at
    _pets = App._pets
    _hit = staticmethod(App._hit)


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


def put(app, c):
    """가짜 서버와 앱을 같은 카드로 맞춘다 (나중에 앱이 카드를 다시 물어도 같은 답이 오게)."""
    app.api.card = c
    app.fishing._apply(c)


def press(root, widget):
    widget.event_generate("<Button-1>", x=40, y=30)
    settle(root, 0.05)


# ---------------------------------------------------------------- 그림
def art_part():
    print("=== 그림 ===")
    key = (255, 0, 255)
    w, h = ART.size()
    chk("연못 창은 작다 (대략 96x40 연못 + 낚싯대 · 말풍선 자리)", 90 <= w <= 140 and 50 <= h <= 80, (w, h))
    states = ("idle", "cast", "nibble", "strike", "splash")
    ok = True
    for s in states:
        fr = ART.frames(s, key)
        ok = ok and len(fr) >= 2 and all(f.size == (w, h) and f.mode == "RGB" for f in fr)
    chk("상태마다 같은 크기의 RGB 그림 여러 장 (윈도우 색 열쇠 - 반투명 없음)", ok)
    chk("  2배 도트 (가로 두 칸씩 같은 색)", all(
        ART.frames("cast", key)[0].getpixel((x, y)) == ART.frames("cast", key)[0].getpixel((x + 1, y))
        for x in range(0, w, 2) for y in range(0, h, 7)))

    def red(fr):
        return sum(1 for px in pixels(fr) if px == ART.BOB_RED)
    chk("idle 은 낚싯대가 눕고 찌가 없다 · cast 는 찌가 뜬다",
        red(ART.frames("idle", key)[0]) == 0 and red(ART.frames("cast", key)[0]) > 0)
    st = ART.frames("strike", key)
    bang = [sum(1 for px in pixels(f) if px == ART.BANG) for f in st]
    chk("strike 는 '!' 가 깜빡인다 (있는 장 · 없는 장)", max(bang) > 0 and min(bang) == 0, bang)
    nb = ART.frames("nibble", key)
    chk("nibble 은 찌가 흔들린다 (장마다 다르다)", len(set(f.tobytes() for f in nb)) >= 2)
    chk("무게 글: 10kg 아래 소수 둘째 · 이상 첫째", FI.weight_text(84200) == "84.2kg"
        and FI.weight_text(400) == "0.40kg", (FI.weight_text(84200), FI.weight_text(400)))
    b = FI.baits({"bag": {"ORANBERRY": 12, "SITRUSBERRY": 3, "POMEGBERRY": 9, "POKEBALL": 5, "LEFTOVERS": 1,
                          "LUMBERRY": 0}})
    chk("미끼는 지닌 열매만 (노력치 열매 · 볼 · 다른 도구 · 0개 빼고) 많은 순",
        [i for i, _kr, _n in b] == ["ORANBERRY", "SITRUSBERRY"] and b[0][1] == "오랭열매", b)


# ---------------------------------------------------------------- 1~2. 연못 · 던지기
def pond_part(root, ov, app):
    print("=== 1. 연못이 뜬다 ===")
    fz = app.fishing
    app.settings["showGrass"] = False
    app.settings["showPond"] = None
    fz.note(card("idle"))
    settle(root)
    chk("풀숲을 끈 사람은 처음에 낚시터도 꺼진 채 (showPond 가 showGrass 를 따른다)",
        fz.pond is None and app.settings["showPond"] is False, app.settings["showPond"])
    app.settings["showGrass"] = True
    app.settings["showPond"] = None
    fz.note(card("idle"))
    settle(root)
    p = fz.pond
    chk("풀숲을 켠 사람은 연못이 뜬다 · 그 값으로 굳힌다", p is not None and app.settings["showPond"] is True)
    x1, y1, x2, y2 = AREA
    m = ov.settings["areaMargin"]
    bw = int(max(30, int(ov.settings["targetHeight"] * 0.9)) * 1.1)
    chk("영역 왼쪽 아래 - 탐험 보따리(%dpx) 오른쪽, 바닥에 맞춰" % bw,
        p.x >= x1 + m + 10 + bw and p.x < x1 + 260 and p.y + p.fh == y2 - m, (p.x, p.y, p.fw, p.fh))
    chk("  창이 그 자리에 있다", pump(root, lambda: abs(p.win.winfo_x() - p.x) <= 1 and abs(p.win.winfo_y() - p.y) <= 1),
        (p.win.winfo_x(), p.win.winfo_y(), p.x, p.y))
    chk("idle: 낚싯대가 눕는다", fz.phase == "idle" and p.state == "idle", (fz.phase, p.state))
    chk("rect() 는 연못 자리", fz.rect() == (p.x, p.y, p.x + p.fw, p.y + p.fh), fz.rect())
    chk("마우스 올림 글 (idle)", fz.tip_text().startswith("눌러서 찌 던지기 · 오른쪽 클릭: 미끼"), fz.tip_text())
    chk("처음 한 번 안내: 선두 포켓몬 말풍선", pump(root, lambda: int(app.settings.get("pondHints") or 0) >= 1, 3))
    chk("  안내 글", FI.HINT_FIRST == "연못을 눌러 찌를 던져 보세요")

    print("=== 2. 누르면 던진다 ===")
    app.settings["lastBait"] = "ORANBERRY"
    press(root, p.label)
    chk("누름(<Button-1>)으로 fish_cast(lastBait)",
        pump(root, lambda: ("cast", "ORANBERRY") in app.api.calls), app.api.calls)
    chk("cast 그림 (찌)", pump(root, lambda: fz.phase == "cast" and p.state == "cast"), (fz.phase, p.state))
    chk("마우스 올림 글: 입질을 기다리는 중 · 미끼: 오랭열매 ×11",
        fz.tip_text().startswith("입질을 기다리는 중") and "미끼: 오랭열매 ×11" in fz.tip_text(), fz.tip_text())
    p.label.event_generate("<Enter>")
    settle(root, 0.05)
    chk("  올리면 글 창이 뜬다", fz.tip is not None and fz.tip.winfo_exists())
    p.label.event_generate("<Leave>")
    settle(root, 0.05)
    chk("  내리면 사라진다", fz.tip is None)
    n = app.api.n("cast")
    press(root, p.label)
    settle(root, 0.2)
    chk("던져 둔 동안 또 눌러도 다시 던지지 않는다", app.api.n("cast") == n)

    # 마지막 미끼가 떨어졌으면 미끼 없이 던진다
    put(app, card("idle", bait="ORANBERRY", baitLeft=0))
    chk("  미끼가 떨어졌으면(baitLeft 0) 미끼 없이 던진다", fz._bait() is None)
    # 마지막 하나를 달고 던졌으면 '×0' 이 아니라 '마지막 하나' (실제 앱 시험 11/27)
    put(app, card("cast", bait="ORANBERRY", baitLeft=0))
    tip = fz.tip_text()
    chk("  마지막 미끼를 달았으면 마우스 올림이 '(마지막 하나)'", "(마지막 하나)" in tip and "×0" not in tip, tip)
    put(app, card("cast", bait="ORANBERRY", baitLeft=11))


# ---------------------------------------------------------------- 3~5. 입질 · 챔질
def bite_part(root, ov, app):
    print("=== 3. 입질 준비 → 콕콕 → 쭉 ===")
    fz = app.fishing
    p = fz.pond
    ov.settings["petBehind"] = True
    settle(root, 0.4)
    chk("petBehind: 기다리는 동안 연못은 다른 창 뒤로", top(p.win) == 0 and getattr(p.win, "_poket_behind", False),
        top(p.win))
    stub = type("V", (), {"app": app, "active": False})()
    visit_mod.Visit.on_event(stub, {"t": "fish", "s": "ready"})          # 알림 소켓 → app.on_fish_push
    chk("밀어 보낸 '입질 준비' → 막힌 것이 없으면 fish_bite", pump(root, lambda: app.api.n("bite") == 1), app.api.calls)
    chk("콕콕 (찌가 흔들린다)", pump(root, lambda: fz.phase == "nibble" and p.state == "nibble"), (fz.phase, p.state))
    chk("  입질 동안은 앞으로 (항상 위)", pump(root, lambda: top(p.win) == 1), top(p.win))
    chk("  처음 입질 안내 (찌가 쏙 잠기면 그때 눌러요!)", int(app.settings.get("pondHints") or 0) >= 2
        and FI.HINT_BITE == "찌가 쏙 잠기면 그때 눌러요!")
    chk("  공습은 입질 중에 안 연다 (blocked 'fishing')", app.airraid.blocked() == "fishing", app.airraid.blocked())
    chk("  마우스 올림 글은 아직 '기다리는 중'", fz.tip_text().startswith("입질을 기다리는 중"), fz.tip_text())

    print("=== 4. 콕콕 중에 누르면 ===")
    app.api.hooks.append({"result": "early", "card": app.api.bite_card})
    press(root, p.label)
    chk("'아직! 찌가 쏙 잠기면 누르세요'", pump(root, lambda: app.said("아직! 찌가 쏙 잠기면 누르세요")),
        [f[2] for f in app.floats])
    chk("  그대로 입질 중", fz.phase in ("nibble", "strike"), fz.phase)

    chk("쭉: 찌가 잠기고 '!' 가 깜빡인다", pump(root, lambda: fz.phase == "strike" and p.state == "strike", 3),
        (fz.phase, p.state))
    seen = set()
    pump(root, lambda: (seen.add(p.frame_i % len(ART.frames("strike", ov.key))) or len(seen) >= 4), 2)
    chk("  장이 바뀐다 (깜빡임)", len(seen) >= 4, seen)
    chk("  마우스 올림 글: 지금 눌러!", fz.tip_text().startswith("지금 눌러!"), fz.tip_text())

    print("=== 5. 쭉 중에 누르면 낚인다 ===")
    app.api.hooks.append(hooked(901, perfect=True))
    press(root, p.label)
    chk("hooked → 낚인 야생이 뜬다", pump(root, lambda: app.wild.pet is not None, 4))
    pet = app.wild.pet
    chk("  야생의 출처는 낚시 · 그 번호", app.wild.src == "fish" and app.wild.wild_id == 901,
        (app.wild.src, app.wild.wild_id))
    ax, ay = fz.anchor()

    def landed():
        return pet.x + pet.fw / 2.0 > p.x + p.fw - 4 or pet.x + pet.fw / 2.0 < p.x + 4
    pump(root, lambda: landed() and abs(pet.y + pet.fh - ay) <= 2 and "hop" not in fz._jobs, 3)
    chk("  연못 옆에 내려앉는다 (발이 연못 바닥 줄)", landed() and abs(pet.y + pet.fh - ay) <= 2,
        ((pet.x, pet.y, pet.fw, pet.fh), (p.x, p.y, p.fw, p.fh), (ax, ay)))
    chk("  '완벽한 챔질!'", app.said("완벽한 챔질!"), [f[2] for f in app.floats])
    chk("  머리 위에 무게 · 1.3배 넘으면 금색 '대물!'", pump(root, lambda: app.said("대물!") and app.said("84.2kg")),
        [f[2] for f in app.floats])
    gold = [f for f in app.floats if "대물!" in f[2]]
    chk("    금색", gold and gold[-1][3] == FI.GOLD, gold)
    chk("  연못은 다시 낚싯대가 눕는다 (물보라 뒤)", pump(root, lambda: p.state == "idle", 3), p.state)
    chk("  낚인 야생이 있는 동안 busy · 공습 막힘", fz.busy() and app.airraid.blocked() == "fishing")
    chk("  입질이 끝나면 다시 뒤로 (petBehind)", pump(root, lambda: top(p.win) == 0), top(p.win))
    ov.settings["petBehind"] = False
    pump(root, lambda: top(p.win) == 1)
    chk("  설정을 끄면 다시 항상 위", top(p.win) == 1)
    n = app.api.n("cast")
    press(root, p.label)
    settle(root, 0.2)
    chk("  낚인 야생이 있는 동안 연못을 눌러도 안 던진다", app.api.n("cast") == n)

    print("=== 6. 풀숲을 꺼도 낚인 야생은 남는다 ===")
    app.settings["showGrass"] = False
    n_wild = app.api.n("wild")
    app.wild.check()
    settle(root)
    chk("check() 가 안 지운다", app.wild.pet is pet, app.wild.pet)
    app.wild.set_enabled(False)
    settle(root)
    chk("set_enabled(False) 가 안 지운다", app.wild.pet is pet)
    app.wild.apply({"balls": 5, "wild": fish_wild(901)})
    chk("apply 도 안 지운다", app.wild.pet is pet)
    chk("  풀숲을 껐으면 GET /api/wild 를 안 부른다 (거기는 풀숲을 돋운다)", app.api.n("wild") == n_wild,
        app.api.n("wild") - n_wild)
    # 배틀이 끝나 서버에서 야생이 사라졌다 - 낚시 카드로 알고 치운다
    app.api.card = card("idle")
    app.wild.check()
    chk("야생이 서버에서 끝났으면(카드 idle) 낚시 카드로 알고 치운다", pump(root, lambda: app.wild.pet is None, 3))
    chk("  연못은 다시 던질 수 있다", pump(root, lambda: fz.phase == "idle"), fz.phase)

    print("=== 재시작 되살리기 · 풀숲 폴링의 fish 야생 ===")
    w2 = fish_wild(902, g=4000, ratio=1.7, badge="huge")
    app.api.card = card("hooked", wild=w2, ballOptions=BALLS)
    app.wild.stop()
    chk("wild.stop() 이 낚시도 멈춘다 (연못을 걷는다)", fz.paused and fz.pond is None)
    app.wild.start()
    chk("wild.start() 가 낚시를 다시 연다 (카드를 묻는다)", pump(root, lambda: fz.pond is not None and not fz.paused))
    chk("hooked 카드 → 풀숲을 꺼도 낚인 야생을 되살린다", pump(root, lambda: app.wild.pet is not None
                                                     and app.wild.wild_id == 902, 4), app.wild.wild_id)
    p = fz.pond                                  # 멈췄다 다시 열면 연못 창도 새로 선다
    app.settings["showGrass"] = True
    app.wild.apply({"balls": 5, "wild": None}, asked=app.wild._fish_at - 1)
    app.wild.stop_polling()
    chk("낚기 전에 떠난 풀숲 확인의 '야생 없음' 은 방금 낚은 야생을 안 지운다", app.wild.pet is not None
        and app.wild.wild_id == 902)
    app.wild.apply({"balls": 5, "wild": None}, asked=time.time())
    app.wild.stop_polling()
    chk("  낚은 뒤에 떠난 답이면 지운다 (야생이 끝났다)", app.wild.pet is None)
    app.wild.clear()
    app.settings["showGrass"] = True
    app.wild.apply({"balls": 5, "wild": fish_wild(903), "ballOptions": BALLS})
    settle(root, 0.4)
    pet3 = app.wild.pet
    chk("풀숲 폴링(apply)에 온 fish 야생도 연못 옆", pet3 is not None and app.wild.src == "fish"
        and abs(pet3.y + pet3.fh - fz.anchor()[1]) <= 2, pet3 and (pet3.x, pet3.y))
    app.wild.clear()
    put(app, card("idle"))
    settle(root, 0.3)

    print("=== 입질 중에 멈췄다 다시 열면 ===")
    put(app, card("bite", nibbleLeft=0.3, strikeLeft=8.0))
    chk("콕콕", fz.phase == "nibble", fz.phase)
    app.wild.stop()
    chk("멈추면 입질 타이머를 걷고 바쁘지 않다 (공습 등이 막히지 않게)", not fz.busy() and "strike" not in fz._jobs,
        (fz.phase, list(fz._jobs)))
    app.api.card = card("bite", nibbleLeft=0.0, strikeLeft=0.5)
    app.wild.start()
    chk("다시 열면 카드대로 입질을 다시 시작한다 (타이머가 다시 걸린다)",
        pump(root, lambda: fz.phase == "strike" and "strike" in fz._jobs), (fz.phase, list(fz._jobs)))
    chk("  그 쭉도 끝나면 놓친다", pump(root, lambda: fz.phase == "idle", 3), fz.phase)
    app.api.card = card("idle")
    p = fz.pond

    print("=== 놓침 · 헛챔질 ===")
    put(app, card("bite", nibbleLeft=0.0, strikeLeft=0.4))
    chk("쭉이 이미면 바로 strike", fz.phase == "strike", fz.phase)
    chk("쭉이 지나면 '놓쳤다…'", pump(root, lambda: app.said("놓쳤다…") and fz.phase == "idle", 3), fz.phase)
    app.api.card = card("idle")                 # 서버도 여유 5초 뒤에는 idle
    put(app, card("bite", nibbleLeft=2.0, strikeLeft=6.0))
    app.api.hooks.append({"result": "spooked", "card": card("idle")})
    press(root, p.label)
    chk("헛챔질 → '너무 일찍 당겼다…' · idle", pump(root, lambda: app.said("너무 일찍 당겼다…") and fz.phase == "idle"),
        fz.phase)
    chk("  입질 타이머가 남지 않는다", "nibble" not in fz._jobs and "strike" not in fz._jobs, list(fz._jobs))


# ---------------------------------------------------------------- 쭉 뒤 여유 · 던지기 409
def late_part(root, ov, app):
    """서버는 쭉이 끝나고도 여유(FISH_GRACE 5초) 동안 bite 로 읽는다 - 그 사이 누름은 던지기가 아니라 챔질이다."""
    print("=== 쭉 뒤 여유 (late) ===")
    fz = app.fishing
    late_ms = fz.LATE_MS
    fz.LATE_MS = 3000
    try:
        put(app, card("bite", nibbleLeft=0.0, strikeLeft=0.3))
        app.api.card = card("idle")              # 여유 뒤 서버 (놓침 확인이 와도 다시 입질을 걸지 않게)
        chk("쭉이 끝나면 '놓쳤다…' · late (서버는 아직 bite 로 읽는다)",
            pump(root, lambda: fz.phase == "late" and app.said("놓쳤다…"), 3), fz.phase)
        n_cast, n_hook = app.api.n("cast"), app.api.n("hook")
        app.api.hooks.append({"result": "missed", "card": card("idle")})
        press(root, fz.pond.label)
        chk("  late 에 누르면 던지지 않고 챔질 (낚임 · 놓침은 서버가 정한다)",
            pump(root, lambda: app.api.n("hook") == n_hook + 1) and app.api.n("cast") == n_cast,
            app.api.calls[-3:])
        chk("  놓침 답 → idle · late 타이머가 남지 않는다", pump(root, lambda: fz.phase == "idle")
            and "late" not in fz._jobs, (fz.phase, list(fz._jobs)))
        put(app, card("bite", nibbleLeft=0.0, strikeLeft=0.2))
        app.api.card = card("idle")
        pump(root, lambda: fz.phase == "late", 3)
        app.api.hooks.append(hooked(907, perfect=False))
        press(root, fz.pond.label)
        chk("  late 에 눌러 서버가 낚였다고 하면 낚인 야생", pump(root, lambda: app.wild.pet is not None
                                                     and app.wild.wild_id == 907, 4), app.wild.wild_id)
        pump(root, lambda: "hop" not in fz._jobs, 2)
        app.wild.clear()
        put(app, card("idle"))
        settle(root, 0.2)
        # 다시 연 앱 · 멈췄다 다시 열기가 여유 안에 왔다 - 카드는 bite 인데 남은 초가 0
        put(app, card("bite", nibbleLeft=0.0, strikeLeft=0.0))
        chk("카드가 bite · 남은 초 0 이면 idle 이 아니라 late", fz.phase == "late", fz.phase)
        n_cast = app.api.n("cast")
        app.api.hooks.append({"result": "missed", "card": card("idle")})
        press(root, fz.pond.label)
        chk("  눌러도 던지지 않는다 (챔질)", pump(root, lambda: fz.phase == "idle") and app.api.n("cast") == n_cast,
            app.api.calls[-3:])
        fz.LATE_MS = 200
        put(app, card("bite", nibbleLeft=0.0, strikeLeft=0.2))
        app.api.card = card("idle")
        chk("late 가 끝나면 idle", pump(root, lambda: fz.phase == "idle", 3), fz.phase)
        n_cast = app.api.n("cast")
        press(root, fz.pond.label)
        chk("  그 뒤 누르면 다시 던진다", pump(root, lambda: app.api.n("cast") == n_cast + 1 and fz.phase == "cast"),
            app.api.calls[-3:])
    finally:
        fz.LATE_MS = late_ms
    put(app, card("idle"))

    print("=== 던지기 409 ===")
    app.api.card = card("cast", bait=None)       # 다른 PC 에서 던져 두었다 - 이 앱은 아직 idle
    app.api.cast_err = Err(409, "이미 찌를 던져 두었습니다.")
    n_fish, nf, nn = app.api.n("fish"), len(app.floats), len(app.notes)
    press(root, fz.pond.label)
    chk("던지기가 409 면 카드를 다시 물어 맞춘다 (cast)", pump(root, lambda: app.api.n("fish") > n_fish
                                                   and fz.phase == "cast"), (fz.phase, app.api.calls[-3:]))
    chk("  서버의 날 글을 띄우지 않는다", not any("이미 찌를" in f[2] for f in app.floats[nf:])
        and not any("이미 찌를" in m for m in app.notes[nn:]), ([f[2] for f in app.floats[nf:]], app.notes[nn:]))
    put(app, card("idle"))
    app.api.cast_err = Err(409, "포켓몬이 가득 차서 낚시를 할 수 없습니다.")
    n_fish = app.api.n("fish")
    press(root, fz.pond.label)
    chk("  다시 물어도 idle 이면 상태 탓이 아니다 (상자 가득) - 그 글은 띄운다",
        pump(root, lambda: app.said("가득 차서") and app.api.n("fish") > n_fish) and fz.phase == "idle",
        ([f[2] for f in app.floats[-3:]], fz.phase))
    put(app, card("idle"))
    settle(root, 0.2)


# ---------------------------------------------------------------- 재시작 되살리기 (연못보다 먼저 뜬 야생)
def restore_part(root, ov, app):
    print("=== 재시작: 연못보다 먼저 뜬 낚인 야생 ===")
    fz = app.fishing
    w = app.wild
    w.clear()
    app.settings["showGrass"] = True
    app.set_show_pond(False)                     # 연못이 아직 없다 (카드 · 설정이 늦게 왔다)
    settle(root)
    w.apply({"balls": 5, "wild": fish_wild(904), "ballOptions": BALLS})
    w.stop_polling()
    pet = w.pet
    chk("연못이 없으면 풀숲 폴링의 낚인 야생은 아무 데나 선다", pet is not None and w.src == "fish" and fz.pond is None,
        (pet, w.src))
    far = (AREA[0] + 420.0, AREA[1] + 30.0)
    pet.x, pet.y = far
    pet.place()
    app.set_show_pond(True)
    settle(root)
    a = fz.anchor()
    c = card("hooked", wild=fish_wild(904), ballOptions=BALLS)
    w.show_hooked(c, a)
    chk("연못이 생긴 뒤 카드가 오면 연못 옆으로 옮긴다", w.pet is pet and abs(pet.y + pet.fh - a[1]) <= 2
        and abs(pet.x + pet.fw / 2.0 - a[0]) <= 2, ((pet.x, pet.y, pet.fw, pet.fh), a))
    pet.x, pet.y = far
    pet.place()
    w.show_hooked(c, a)
    chk("  한 번만 (다음 동기화 카드가 또 끌어오지 않는다)", (pet.x, pet.y) == far, (pet.x, pet.y))
    w.clear()
    # 번호만 알고 도트가 없다 (apply 때 그림이 아직 없어 show_wild 가 그냥 돌아갔다)
    w.wild_id, w.src = 905, "fish"
    ok = w.show_hooked(card("hooked", wild=fish_wild(905), ballOptions=BALLS), fz.anchor())
    chk("같은 번호인데 도트가 없으면 받아서 띄운다", ok and pump(root, lambda: w.pet is not None and w.wild_id == 905, 4),
        (ok, w.pet, w.wild_id))
    chk("  연못 옆", w.pet is not None and abs(w.pet.y + w.pet.fh - fz.anchor()[1]) <= 2)
    w.clear()
    put(app, card("idle"))
    settle(root, 0.2)


# ---------------------------------------------------------------- 7. 막힘
def blocked_part(root, ov, app):
    print("=== 7. 막혀 있으면 입질을 미룬다 ===")
    fz = app.fishing
    fz.RETRY_MS = 150
    put(app, card("cast"))
    app.visit.active = True                      # 친구가 놀러 와 있다 (공습 쪽 blocked 'visit')
    chk("blocked() 가 visit", fz.blocked() == "visit", fz.blocked())
    n = app.api.n("bite")
    app.on_fish_push({"t": "fish", "s": "ready"})
    settle(root, 0.5)
    chk("막힌 동안 bite 를 안 부른다", app.api.n("bite") == n, app.api.calls[-3:])
    app.visit.active = False
    app.api.bite_card = card("bite", nibbleLeft=0.3, strikeLeft=1.0)
    chk("풀리면 부른다", pump(root, lambda: app.api.n("bite") == n + 1, 2), app.api.calls[-3:])
    chk("  콕콕", pump(root, lambda: fz.phase in ("nibble", "strike")), fz.phase)
    pump(root, lambda: fz.phase == "idle", 3)
    app.api.card = card("idle")
    # 화면에 야생이 있으면 미룬다 (서버도 wait 'wild')
    app.wild.grass = type("G", (), {"destroy": lambda self: None, "x": 0, "y": 0, "fw": 1, "fh": 1})()
    put(app, card("cast", ready=True))
    settle(root, 0.4)
    chk("화면에 풀숲 · 야생이 있으면 미룬다", fz.blocked() == "wild" and app.api.n("bite") == n + 1, fz.blocked())
    app.wild.grass = None
    app.api.bite_card = card("cast", wait="wild")
    pump(root, lambda: app.api.n("bite") == n + 2, 2)
    settle(root, 0.6)
    chk("서버가 wait 'wild' 면 한참 뒤에 다시 (바로 되묻지 않는다)", app.api.n("bite") == n + 2, app.api.n("bite"))
    # 그런데 화면의 야생이 사라지면(WildController.clear) 30초를 기다리지 않고 곧 다시 본다 (실제 앱 시험 11/27)
    app.api.bite_card = card("bite", nibbleLeft=0.3, strikeLeft=1.0)
    app.wild.clear()
    chk("  야생이 사라지면 3초 안에 다시 묻는다", pump(root, lambda: app.api.n("bite") == n + 3, 4.5), app.api.n("bite"))
    pump(root, lambda: fz.phase == "idle", 3)
    put(app, card("idle"))


# ---------------------------------------------------------------- 8. 메뉴 (맥 길)
def menu_part(root, ov, app):
    print("=== 8. 오른쪽 클릭 메뉴 (맥 길) ===")
    fz = app.fishing
    p = fz.pond
    opened = []
    real = U.PopupMenu

    class Spy(real):
        def __init__(self, root_, rows, x, y, **kw):
            opened.append(rows)
            real.__init__(self, root_, rows, x, y, **kw)
    U.PopupMenu = Spy
    for i, pet in enumerate(ov.pets.values()):     # 걸어다니는 도트는 연못에서 멀리 (테두리 상자 검사가 흔들리지 않게)
        pet.x, pet.y = AREA[2] - 60 - 50 * i, AREA[1] + 5
        pet.place()
    native = PLAT.NATIVE_MENU
    PLAT.NATIVE_MENU = False                       # 맥 흉내 (tk.Menu 를 안 쓴다)
    try:
        num = getattr(p.view, "win_number", None)
        cx, cy = p.x + p.fw // 2, p.y + p.fh - 6
        if num is not None:
            app._right_click_at(cx, cy, num)
            chk("창 번호로 연못을 찾아 메뉴를 연다", pump(root, lambda: len(opened) == 1, 2), opened)
            U.close_all()
            settle(root)
        app._right_click_at(cx, cy, -12345)
        chk("테두리 상자로도 찾는다 (번호가 어긋날 때)", pump(root, lambda: len(opened) == (2 if num is not None else 1), 2),
            len(opened))
        rows = opened[-1]
        texts = [r.get("text") for r in rows if r]
        chk("메뉴: 미끼 · 줄 거두기 · 낚시터 옮기기 · 낚시 기록 · 낚시터 숨기기",
            all(t in texts for t in ("미끼", "줄 거두기", "낚시터 옮기기", "낚시 기록", "낚시터 숨기기")), texts)
        bait_rows = [r for r in rows if r and r.get("indent")]
        chk("  미끼 줄: 지닌 열매만 많은 순 (노력치 열매 · 다른 도구 빼고) + 미끼 없이",
            [r["text"] for r in bait_rows] == ["오랭열매 ×12", "자뭉열매 ×3", "미끼 없이"], [r["text"] for r in bait_rows])
        chk("  지금 단 미끼에 표시", [r.get("checked") for r in bait_rows] == [True, False, False],
            [r.get("checked") for r in bait_rows])
        reel = next(r for r in rows if r and r.get("text") == "줄 거두기")
        chk("  안 던졌으면 줄 거두기는 못 누른다", reel.get("enabled") is False)
        U.close_all()
        settle(root)
        next(r for r in bait_rows if r["text"].startswith("자뭉"))["command"]()
        chk("미끼를 고르면 다음 던지기에 단다 (lastBait 저장)", app.settings["lastBait"] == "SITRUSBERRY"
            and config.load_settings()["lastBait"] == "SITRUSBERRY")
        # 도트가 연못 위에 겹쳐 있으면 (번호가 안 맞을 때) 도트가 먼저
        dot = type("D", (), {})()
        dot.x, dot.y, dot.fw, dot.fh = cx - 10, cy - 10, 20, 20
        dot.view = type("V", (), {"win_number": -1})()
        got = []
        dot.on_menu = lambda e: got.append(e)
        ov.extra.append(dot)
        try:
            n = len(opened)
            app._right_click_at(cx, cy, -999)
            settle(root, 0.3)
            chk("  테두리 상자로만 맞으면 그 위의 도트에게 양보한다", got and len(opened) == n, (got, len(opened)))
        finally:
            ov.extra.remove(dot)
        # 줄 거두기
        put(app, card("cast", bait="ORANBERRY", baitLeft=11))
        app._right_click_at(cx, cy, -12345)
        pump(root, lambda: len(opened) >= 3 and opened[-1] is not rows, 2)
        reel = next(r for r in opened[-1] if r and r.get("text") == "줄 거두기")
        U.close_all()
        reel["command"]()
        chk("던져 둔 동안 줄 거두기 → fish_reel → idle", pump(root, lambda: app.api.n("reel") == 1 and fz.phase == "idle"),
            fz.phase)
        recs = []
        import types
        import poketdesktop as pkg
        fake = types.SimpleNamespace(open_records=lambda a: recs.append(a))
        had_mod = sys.modules.get("poketdesktop.ui_fishing")
        had_attr = getattr(pkg, "ui_fishing", None)
        sys.modules["poketdesktop.ui_fishing"], pkg.ui_fishing = fake, fake      # 기록 창은 따로 만든다 (Task 4)
        try:
            fz.open_records()
        finally:
            if had_mod is not None:
                sys.modules["poketdesktop.ui_fishing"] = had_mod
            else:
                sys.modules.pop("poketdesktop.ui_fishing", None)
            if had_attr is not None:
                pkg.ui_fishing = had_attr
            else:
                delattr(pkg, "ui_fishing")
        chk("낚시 기록 → ui_fishing.open_records(app)", recs == [app], recs)
    finally:
        U.PopupMenu = real
        PLAT.NATIVE_MENU = native
        U.close_all()


# ---------------------------------------------------------------- 9~10. 옮기기 · 숨기기
def move_part(root, ov, app):
    print("=== 9. 낚시터 옮기기 ===")
    fz = app.fishing
    p = fz.pond
    fz.start_move()
    settle(root)
    chk("옮기기 덮개가 뜬다", fz.moving is not None and fz.moving.winfo_exists())
    tx, ty = 700, 400
    fz.moving.event_generate("<Button-1>", x=tx - AREA[0], y=ty - AREA[1], rootx=tx, rooty=ty)
    settle(root)
    chk("누른 곳으로 옮긴다 (가운데가 그 자리)", fz.moving is None and abs(p.x + p.fw // 2 - tx) <= 1
        and abs(p.y + p.fh // 2 - ty) <= 1, (p.x, p.y))
    pos = config.load_settings().get("pondPos")
    chk("  영역 안 비율로 저장 (pondPos)", isinstance(pos, list) and len(pos) == 2 and 0 <= pos[0] <= 1
        and 0 <= pos[1] <= 1, pos)
    chk("  창도 그 자리", pump(root, lambda: abs(p.win.winfo_x() - p.x) <= 1), (p.win.winfo_x(), p.x))
    new = (100, 100, 1500, 900)
    ov.area = lambda: new
    app._area_changed()
    m = ov.settings["areaMargin"]
    fx = (p.x - (new[0] + m)) / float((new[2] - m - p.fw) - (new[0] + m))
    chk("영역이 바뀌면 같은 비율로 다시 맞춘다", abs(fx - pos[0]) < 0.01 and new[0] <= p.x and p.x + p.fw <= new[2],
        (fx, pos))
    ov.area = lambda: AREA
    app._area_changed()

    print("=== 영역이 _area_changed 없이 바뀌어도 (모니터 빼기 · 해상도 · 작업 표시줄) ===")
    other = (200, 150, 1200, 800)
    ov.area = lambda: other
    chk("연못이 스스로 알아채 새 영역의 제자리로 (1초 남짓)", pump(root, lambda: (p.x, p.y) == fz.home(p.fw, p.fh), 3)
        and other[0] <= p.x and p.x + p.fw <= other[2] and other[1] <= p.y and p.y + p.fh <= other[3],
        ((p.x, p.y), fz.home(p.fw, p.fh)))
    ov.area = lambda: AREA
    chk("  돌아오면 다시 따라온다", pump(root, lambda: (p.x, p.y) == fz.home(p.fw, p.fh), 3),
        ((p.x, p.y), fz.home(p.fw, p.fh)))
    at = (p.x, p.y)
    settle(root, 1.2)
    chk("  영역이 그대로면 안 움직인다", (p.x, p.y) == at, ((p.x, p.y), at))

    print("=== 옮기는 동안 오른쪽 클릭 (맥 길) ===")
    fz.start_move()
    settle(root)
    dot = type("D", (), {})()
    dot.x, dot.y, dot.fw, dot.fh = AREA[0] + 300, AREA[1] + 100, 30, 30
    dot.view = type("V", (), {"win_number": -777})()
    got = []
    dot.on_menu = lambda e: got.append(e)
    ov.extra.append(dot)
    try:
        app._right_click_at(dot.x + 5, dot.y + 5, -777)
        settle(root)
        chk("옮기기 중 오른쪽 클릭은 그만두기 - 밑의 도트에 안 넘긴다", fz.moving is None and not got,
            (fz.moving, got))
    finally:
        ov.extra.remove(dot)

    fz.start_move()
    settle(root)
    fz.moving.focus_force()
    settle(root)
    fz.moving.event_generate("<Escape>", when="now")
    settle(root)
    chk("Esc 면 그만둔다", fz.moving is None)
    fz.start_move()
    fz._end_move()
    chk("  덮개 시간 제한도 지운다", "move" not in fz._jobs)

    print("=== 10. 낚시터 숨기기 ===")
    win = p.win
    fz.hide_pond()
    settle(root)
    chk("숨기면 창이 없다", fz.pond is None and not win.winfo_exists())
    chk("  설정에 저장 (showPond False)", config.load_settings().get("showPond") is False)
    app.set_show_pond(True)
    settle(root)
    chk("다시 켜면 돌아온다", fz.pond is not None)

    print("=== 숨기면 던져 둔 줄을 거둔다 ===")
    put(app, card("cast", bait="ORANBERRY", baitLeft=11))
    n, nf = app.api.n("reel"), len(app.floats)
    app.set_show_pond(False)
    chk("던져 둔 채(cast) 숨기면 fish_reel · 연못 없음", pump(root, lambda: app.api.n("reel") == n + 1
                                                    and fz.phase == "idle") and fz.pond is None,
        (app.api.n("reel") - n, fz.phase, fz.pond))
    settle(root, 0.3)
    chk("  한 번만 · 띄우는 글 없음", app.api.n("reel") == n + 1 and len(app.floats) == nf,
        (app.api.n("reel") - n, app.floats[nf:]))
    app.set_show_pond(True)
    settle(root)
    app.api.cast_delay = 0.3
    try:
        press(root, fz.pond.label)
        app.set_show_pond(False)                 # 던지는 요청이 오가는 중
        chk("던지는 중에 숨겨도 그 답이 오면 거둔다", pump(root, lambda: app.api.n("reel") == n + 2
                                                 and fz.phase == "idle", 3), (app.api.n("reel") - n, fz.phase))
    finally:
        app.api.cast_delay = 0.0
    app.set_show_pond(True)
    settle(root)
    put(app, card("bite", nibbleLeft=0.2, strikeLeft=0.3))
    app.api.card = card("idle")
    app.set_show_pond(False)
    settle(root, 0.3)
    chk("입질 중(콕콕 · 쭉)에 숨기면 거두지 않고 연못만 걷는다", app.api.n("reel") == n + 2 and fz.pond is None,
        (app.api.n("reel") - n, fz.pond))
    chk("  쭉이 끝나면 저절로 idle (서버 쪽 놓침)", pump(root, lambda: fz.phase == "idle", 3), fz.phase)
    app.set_show_pond(True)
    settle(root)
    chk("  다시 켜면 돌아온다", fz.pond is not None and app.api.n("reel") == n + 2)


# ---------------------------------------------------------------- 앱 이음
def wiring_part():
    print("=== 앱 이음 ===")
    import poketdesktop.app as appmod
    src = open(appmod.__file__, encoding="utf-8").read()
    chk("동기화: me['fish'] → fishing.note (옛 서버는 칸이 없다)",
        'if "fish" in me and getattr(self, "fishing", None) is not None:' in src
        and 'self.fishing.note(me.get("fish"))' in src)
    chk("start_ui: 낚시를 wild.start() 보다 먼저 만든다 (start 가 낚시를 연다)",
        src.index("FishingController(self)") < src.index("        self.wild.start()\n        self.resume_battle()"))
    chk("로그아웃 · 세션 끊김 · 종료가 낚시를 치운다", src.count("        self._clear_fishing()") == 3,
        src.count("        self._clear_fishing()"))
    vsrc = open(visit_mod.__file__, encoding="utf-8").read()
    chk("알림 소켓 t='fish' 는 놀러 가 있든 아니든 app.on_fish_push 로",
        vsrc.index('elif t == "fish":') < vsrc.index("elif not self.active:"))


# ---------------------------------------------------------------- 설정 · 트레이
def walk(w):
    yield w
    for c in w.winfo_children():
        for x in walk(c):
            yield x


def settings_part(root, ov, app):
    print("=== 설정 · 트레이 '낚시터 보이기' ===")
    from poketdesktop import tray as TR
    from poketdesktop import ui_settings as ST
    from poketdesktop.skins.dp import settings as DPS
    fz = app.fishing
    tray = type("T", (), {"call": lambda self, fn, *a: fn(*a)})()
    fz.open = False
    chk("트레이: 낚시가 열리기 전엔 줄이 없다", TR.pond_items(tray, app) == [])
    sw = ST.SettingsWindow(app)
    settle(root)
    labels = [w.cget("text") for w in walk(sw.win) if isinstance(w, tk.Checkbutton)]
    chk("설정(기본): 열리기 전엔 줄이 없다", "낚시터 보이기" not in labels and "풀숲 띄우기" in labels, labels)
    sw.close()
    fz.open = True
    items = TR.pond_items(tray, app)
    chk("트레이 '바탕화면': 열리면 '낚시터 보이기' (켜짐 표시)", len(items) == 1 and items[0].text == "낚시터 보이기"
        and items[0].checked() is True)
    src = open(TR.__file__, encoding="utf-8").read()
    chk("  '바탕화면' 하위 메뉴에 붙는다 (맥 트레이도 같은 spec)", "] + pond_items(self, a))" in src)
    sw = ST.SettingsWindow(app)
    app.settings_win = sw
    settle(root)
    labels = [w.cget("text") for w in walk(sw.win) if isinstance(w, tk.Checkbutton)]
    chk("설정(기본): '풀숲 띄우기' 바로 아래 '낚시터 보이기'", "낚시터 보이기" in labels
        and labels.index("낚시터 보이기") == labels.index("풀숲 띄우기") + 1, labels)
    chk("  설명: 끄면 던져 둔 줄을 거둔다 (그대로 둔다고 하지 않는다)", "거둡니다" in ST.SettingsWindow.POND_NOTE
        and "그대로" not in ST.SettingsWindow.POND_NOTE, ST.SettingsWindow.POND_NOTE)
    items[0].action()
    settle(root)
    chk("트레이에서 끄면 연못이 걷히고 저장 · 설정 창 표시도 맞춘다", fz.pond is None
        and config.load_settings()["showPond"] is False and sw.pond.get() is False)
    sw.pond.set(True)
    sw._toggle_pond("showPond", sw.pond)
    settle(root)
    chk("설정 창에서 켜면 바로 뜬다", fz.pond is not None and config.load_settings()["showPond"] is True)
    sw.close()
    app.settings_win = None
    dw = DPS.SettingsWindow(app)
    settle(root)
    names = [r["label"] for r in dw.rows]
    chk("설정(DP): '풀숲 띄우기' 바로 아래 '낚시터 보이기'", "낚시터 보이기" in names
        and names.index("낚시터 보이기") == names.index("풀숲 띄우기") + 1, names)
    row = dw.rows[names.index("낚시터 보이기")]
    row["put"](False)
    settle(root)
    chk("  DP 에서 끄기 · 켜기", fz.pond is None and row["get"]() is False)
    row["put"](True)
    settle(root)
    chk("  DP 에서 다시 켜면 뜬다", fz.pond is not None and row["get"]() is True)
    dw.close()
    settle(root)


# ---------------------------------------------------------------- 11. 피하기 · 정리
def avoid_part(root, ov, app):
    print("=== 11. 풀숲 · 알은 연못 자리를 피한다 ===")
    fz = app.fishing
    rect = fz.rect()
    seq = [rect[0] + 2, rect[1] + 2, AREA[0] + 400, AREA[1] + 20]
    real = wild_ui.random.randint
    wild_ui.random.randint = lambda a, b: max(a, min(b, seq.pop(0))) if seq else real(a, b)
    try:
        g = wild_ui.GrassPatch(app.wild, {"id": 1})
    finally:
        wild_ui.random.randint = real
    chk("풀숲은 연못과 안 겹친다", not overlaps((g.x, g.y, g.x + g.fw, g.y + g.fh), rect), (g.x, g.y, rect))
    g.destroy()
    path = dot_path()
    anim = sprites.load_animation(path, 40, 0.5, 4.0)
    egg = eggs_ui.EggPet(ov, {"id": 7, "kind": "legendary", "name": "알", "gotSec": 1, "needSec": 9, "leftSec": 8}, anim)
    egg.x, egg.y = rect[0] + 4, rect[1] + 4
    ov.dodge(egg)
    chk("알도 연못과 안 겹친다", not overlaps((egg.x, egg.y, egg.x + egg.fw, egg.y + egg.fh), rect), (egg.x, egg.y))
    egg.destroy()


def clean_part(root, ov, app, errors):
    print("=== 11. 정리 ===")
    fz = app.fishing
    put(app, card("bite", nibbleLeft=1.0, strikeLeft=5.0))
    p = fz.pond
    p.label.event_generate("<Enter>")
    fz.start_move()
    settle(root, 0.3)
    wins = [w for w in (p.win, fz.tip, fz.moving) if w is not None]
    ids = list(fz._jobs.values())
    chk("정리 전: 창 · 타이머가 있다", len(wins) >= 2 and ids, (len(wins), ids))
    fz.clear()
    settle(root, 0.2)
    chk("clear(): 연못 · 글 · 덮개 창이 남지 않는다", not any(w.winfo_exists() for w in wins))
    pending = str(root.tk.call("after", "info"))
    chk("  남은 after 가 없다", not fz._jobs and not any(str(i) in pending.split() for i in ids), (fz._jobs, ids))
    chk("  다시 카드가 오기 전에는 아무것도 안 띄운다", fz.pond is None and fz.phase == "off" and not fz.busy())
    fz.note(card("idle"))
    settle(root)
    chk("다시 로그인하면 다시 뜬다", fz.pond is not None)
    fz.note(None)
    settle(root)
    chk("카드가 없으면(열리기 전 · 옛 서버) 연못을 걷는다", fz.pond is None and not fz.open)
    chk("그리는 중 예외 없음", fz.errors == 0 and not errors, (fz.errors, errors[:2]))


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
    ov.paths[(129, False)] = path
    ov.sync([mon(1), mon(2, "꼬부기")], {})
    real_ensure, real_walk = sprite_cache.ensure, walk_cache.ensure
    sprite_cache.ensure = lambda api, num, shiny=False, back=False: path
    walk_cache.ensure = lambda *a, **k: (None, None)
    app = MiniApp(root, ov)
    app.fishing.HINT_MS = 50
    app.fishing.LATE_MS = 300            # 쭉 뒤 여유 (진짜는 5초) - 놓침을 기다리는 검사가 늘어지지 않게
    random.seed(3)
    try:
        art_part()
        pond_part(root, ov, app)
        bite_part(root, ov, app)
        late_part(root, ov, app)
        restore_part(root, ov, app)
        blocked_part(root, ov, app)
        menu_part(root, ov, app)
        move_part(root, ov, app)
        settings_part(root, ov, app)
        wiring_part()
        avoid_part(root, ov, app)
        clean_part(root, ov, app, errors)
    finally:
        sprite_cache.ensure, walk_cache.ensure = real_ensure, real_walk
        try:
            app.wild.stop()
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
