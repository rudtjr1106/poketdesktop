# -*- coding: utf-8 -*-
"""열매 텃밭 x 놀러 가기 화면 검사 (다음 시즌 - 손님 메뉴 · 주인 쪽 물 주기 연출).

    python client/test_garden_visit_ui.py
    python client/run_as_windows.py client/test_garden_visit_ui.py

**진짜 Overlay 와 도트 창을 띄운다.** 서버 대신 가짜 api · 소켓, 텃밭(app.garden)도 가짜다 - 부른 것만 적어 둔다
(화단 그림 · 누르기는 test_garden_ui 가 본다). 도트 · 가짜 앱 틀은 test_visit_ui 것을 같이 쓴다.

못 박는 것:

  1. 손님 메뉴 '화분에 물 주기' 줄 셋: 줄 수 있음 / (심은 화분 없음) / (오늘 이미 받음). 주인 텃밭이 닫혔거나
     옛 서버라 view 에 garden 이 없으면 줄이 없다 (시즌 6 은 그대로). 맥 · 윈도우 메뉴 둘 다.
  2. 누르면 visit_water 를 한 번만 (답을 기다리는 동안 또 눌러도), 결과 글이 내 포켓몬 위에, 줄이 죽고, 친구 화단을
     새 view 로 그린다. 409 면 그 글을 띄우고 놀러 가기 상태를 다시 물어 줄을 맞춘다. 끝난 뒤 온 답은 버린다.
  3. 손님: view 가 오거나(들어올 때 · 다시 붙을 때 · watered · bundles 푸시) 바뀌면 app.garden.show_friend(view.garden),
     끝나면 show_friend(None).
  4. 주인: t='water' 를 받으면 놀러 온 포켓몬이 spot 으로 걸어가 play_water(이름) · 카드 적용 · 제자리로 돌아온다.
     멀어도 몇 초 안에 닿는다. spot 이 None(화단 숨김)이면 말풍선만 (카드는 적용). 걷는 중에 끝나거나 크기를
     바꿔도 카드는 적용된다.
  5. 안내 글: 친구 텃밭이 있으면 '화분에 물 주기' 도 알려 준다, 없으면 예전 글 그대로.
  6. app.garden 이 없거나 터져도 놀러 가기는 그대로 돈다.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import test_visit_ui as TV                                  # noqa: E402  (POKET_HOME · 도트 · 가짜 앱 틀을 같이 쓴다)

import tkinter as tk                                        # noqa: E402

from poketdesktop import config, overlay                    # noqa: E402
from poketdesktop import sprite_cache, walk_cache           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import visit as V                         # noqa: E402
from poketdesktop.api import ApiError                       # noqa: E402

OK = FAIL = 0
settle, wait, btext = TV.settle, TV.wait, TV.btext


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


POTS = [{"berry": "ORANBERRY", "stage": 2, "friendBonus": 0}, {"berry": None, "stage": 0, "friendBonus": 0},
        {"berry": "SITRUSBERRY", "stage": 1, "friendBonus": 0}]
G_CAN = {"canWater": True, "why": None, "pots": POTS}
G_EMPTY = {"canWater": False, "why": "empty", "pots": [dict(p, berry=None, stage=0) for p in POTS]}
G_DONE = {"canWater": False, "why": "done", "pots": [dict(p, friendBonus=1 if p["berry"] else 0) for p in POTS]}
G_RIPE = {"canWater": False, "why": "ripe", "pots": [dict(p, stage=4) if p["berry"] else p for p in POTS]}
G_BONUS = {"canWater": False, "why": "bonus", "pots": [dict(p, friendBonus=1) if p["berry"] else p for p in POTS]}
CARD = {"open": True, "pots": [], "harvested": 0, "cap": 20, "nextIn": 60, "fedToday": [],
        "friendWater": {"from": "손님"}}
WATER_ROW = "화분에 물 주기"


class FakeGarden(object):
    """app.garden (GardenController) 대신: Task 3 이 부르는 것만 있다. 부른 것을 차례로 적어 둔다."""

    def __init__(self, spot=None, boom=False):
        self.calls = []
        self.where = spot
        self.boom = boom
        self.plays = True            # play_water 의 답 - False 면 화단이 연출을 못 했다 (걷는 사이 숨김 · 없어짐)

    def show_friend(self, view):
        self.calls.append(("show_friend", view))
        if self.boom:
            raise RuntimeError("화단이 터졌다")

    def spot(self):
        self.calls.append(("spot",))
        if self.boom:
            raise RuntimeError("화단이 터졌다")
        return self.where

    def play_water(self, name):
        self.calls.append(("play_water", name))
        if self.boom:
            raise RuntimeError("화단이 터졌다")
        return self.plays

    def note(self, card):
        self.calls.append(("note", card))
        if self.boom:
            raise RuntimeError("화단이 터졌다")

    def fed_today(self, _pid):
        return False

    def named(self, name):
        return [c for c in self.calls if c[0] == name]

    def last(self, name):
        got = self.named(name)
        return got[-1] if got else None


class Api(TV.Api):
    def __init__(self):
        TV.Api.__init__(self)
        self.water_reply = {"ok": True, "bonus": 2, "garden": G_DONE}
        self.water_error = None

    def visit_water(self):
        self.calls.append(("water",))
        if self.water_error is not None:
            raise self.water_error
        return self.water_reply

    def visit_state(self):
        self.calls.append(("state",))
        return TV.Api.visit_state(self)


def waters(app):
    return [c for c in app.api.calls if c[0] == "water"]


def water_row(vis, pet):
    return next((r for r in vis.menu_rows(pet) if r and WATER_ROW in (r.get("text") or "")), None)


def row_dead(row, text):
    return row is not None and row.get("text") == text and row.get("enabled") is False and not row.get("command")


def foot(p):
    return (p.x + p.fw / 2.0, p.y + p.fh)


def guest_part(root, ov, app, logs):
    print("\n=== 손님: 친구 텃밭이 있는 집에 놀러 왔다 ===")
    g = FakeGarden()
    app.garden = g
    vis = V.Visit(app)
    vis.sock = TV.Sock()
    app.visit = vis
    pets = dict((p.id, p) for p in ov.pets.values())
    lead = pets[1]
    vis.enter(TV.guest_view(garden=G_CAN))
    root.update()
    chk("들어오면 친구 화단을 그리게 한다 (view.garden 그대로)", g.last("show_friend") == ("show_friend", G_CAN),
        g.calls)
    wait(root, lambda: vis.bubbles.get(id(lead)) is not None, 3)
    chk("안내 글에 '화분에 물 주기' 도 (말하기 · 두기 · 돌아오기와 함께)", btext(vis, lead) == V.GUEST_GARDEN_HINT
        and WATER_ROW in V.GUEST_GARDEN_HINT and "여기에 두기" in V.GUEST_GARDEN_HINT
        and "집으로 돌아오기" in V.GUEST_GARDEN_HINT and V.GUEST_GARDEN_HINT.startswith(V.TALK_HINT), btext(vis, lead))

    print("\n=== 손님 메뉴 '화분에 물 주기' ===")
    row = water_row(vis, lead)
    chk("줄 수 있으면 누를 수 있는 줄", row is not None and row.get("text") == WATER_ROW
        and row.get("enabled", True) and callable(row.get("command")), row)
    texts_, _rows = TV.menu_of(app, lead)
    chk("  맥 메뉴: '여기에 두기' 다음, 돌아오기 앞", WATER_ROW in texts_
        and texts_.index("여기에 두기...") < texts_.index(WATER_ROW) < texts_.index("집으로 돌아오기"), texts_)
    ntexts, nrows, popped, err = TV.native_menu_of(app, lead)
    nrow = next((r for r in nrows if r and r["text"] == WATER_ROW), None)
    chk("  윈도우 메뉴: 누를 수 있다", err is None and popped and nrow is not None and nrow["state"] == "normal"
        and callable(nrow["command"]), (err, ntexts))
    chk("  남의 포켓몬 메뉴에는 없다", not any(WATER_ROW in (r.get("text") or "") for r in vis.menu_rows(None) if r))
    vis.v["garden"] = G_EMPTY
    chk("자라는 화분이 없으면 '(심은 화분 없음)' 으로 죽어 있다",
        row_dead(water_row(vis, lead), WATER_ROW + " (심은 화분 없음)"), water_row(vis, lead))
    vis.v["garden"] = G_RIPE
    chk("다 익은 화분뿐이면 '(다 익은 화분뿐)' 으로 죽어 있다 (검토 3)",
        row_dead(water_row(vis, lead), WATER_ROW + " (다 익은 화분뿐)"), water_row(vis, lead))
    vis.v["garden"] = G_BONUS
    chk("자라는 화분이 다 친구 물을 받았으면 '(이미 물을 받은 화분뿐)' 으로 죽어 있다 (검토 15)",
        row_dead(water_row(vis, lead), WATER_ROW + " (이미 물을 받은 화분뿐)"), water_row(vis, lead))
    vis.v["garden"] = G_DONE
    chk("오늘 이미 받았으면 '(오늘 이미 받음)' 으로 죽어 있다",
        row_dead(water_row(vis, lead), WATER_ROW + " (오늘 이미 받음)"), water_row(vis, lead))
    ntexts, nrows, popped, err = TV.native_menu_of(app, lead)
    nrow = next((r for r in nrows if r and r["text"] == WATER_ROW + " (오늘 이미 받음)"), None)
    chk("  윈도우 메뉴에서도 죽어 있다 (메뉴가 멈추지 않는다)", err is None and popped and nrow is not None
        and nrow["state"] == "disabled" and nrow["command"] is None and "집으로 돌아오기" in ntexts, (err, ntexts))
    vis.v["garden"] = None
    chk("주인 텃밭이 닫혔으면 줄이 없다", water_row(vis, lead) is None, vis.menu_rows(lead))
    vis.v.pop("garden", None)
    chk("  옛 서버(garden 칸 없음)도 줄이 없다", water_row(vis, lead) is None, vis.menu_rows(lead))

    print("\n=== 누르기 ===")
    vis.v["garden"] = G_CAN
    s0 = len(g.named("show_friend"))
    row = water_row(vis, lead)
    row["command"]()
    row["command"]()
    chk("답을 기다리는 동안 줄은 죽어 있다", row_dead(water_row(vis, lead), WATER_ROW), water_row(vis, lead))
    wait(root, lambda: not vis._watering, 3)
    settle(root, 0.1)
    chk("두 번 눌러도 visit_water 는 한 번", len(waters(app)) == 1, app.api.calls[-3:])
    chk("  결과 글이 내 포켓몬 위에 (누구 화분 · 열매 몇 개 더)", btext(vis, lead) == V.WATER_GAVE % "집주인" + " · 열매 +2",
        btext(vis, lead))
    chk("  줄이 '(오늘 이미 받음)' 으로 죽는다", row_dead(water_row(vis, lead), WATER_ROW + " (오늘 이미 받음)"),
        water_row(vis, lead))
    chk("  친구 화단을 새 view 로 다시 그린다", len(g.named("show_friend")) == s0 + 1
        and g.last("show_friend") == ("show_friend", G_DONE), g.calls[-2:])
    vis.v["garden"] = G_CAN
    app.api.water_reply = {"ok": True, "bonus": 0}
    water_row(vis, lead)["command"]()
    wait(root, lambda: not vis._watering, 3)
    settle(root, 0.1)
    chk("붙은 화분이 없으면 '+' 없이, view 가 안 와도 줄은 죽는다", btext(vis, lead) == V.WATER_GAVE % "집주인"
        and row_dead(water_row(vis, lead), WATER_ROW + " (오늘 이미 받음)"), (btext(vis, lead), water_row(vis, lead)))

    print("\n=== 못 줬을 때 ===")
    vis.v["garden"] = G_CAN                               # 늦게 받은 view - 그새 다른 손님이 물을 줬다
    app.api.water_error = ApiError("오늘은 이미 친구에게 물을 받았어요.", 409)
    app.api.state_visit = TV.guest_view(garden=G_DONE)
    n_state = app.api.calls.count(("state",))
    water_row(vis, lead)["command"]()
    wait(root, lambda: app.api.calls.count(("state",)) > n_state and not vis._watering, 3)
    wait(root, lambda: row_dead(water_row(vis, lead), WATER_ROW + " (오늘 이미 받음)"), 3)
    chk("409: 서버 글을 띄운다", btext(vis, lead) == "오늘은 이미 친구에게 물을 받았어요.", btext(vis, lead))
    chk("  놀러 가기 상태를 다시 물어 줄을 맞춘다", row_dead(water_row(vis, lead), WATER_ROW + " (오늘 이미 받음)")
        and g.last("show_friend") == ("show_friend", G_DONE), water_row(vis, lead))
    vis.v["garden"] = G_CAN
    app.api.water_error = ApiError("서버에 연결할 수 없습니다.", 0)
    n_state = app.api.calls.count(("state",))
    water_row(vis, lead)["command"]()
    wait(root, lambda: not vis._watering, 3)
    settle(root, 0.2)
    chk("연결 오류: 글만 띄우고 줄은 그대로 (다시 누를 수 있다)", btext(vis, lead) == "서버에 연결할 수 없습니다."
        and app.api.calls.count(("state",)) == n_state and water_row(vis, lead).get("command") is not None,
        (btext(vis, lead), water_row(vis, lead)))
    app.api.water_error = None

    print("\n=== 친구 화단 view 가 바뀌면 ===")
    vis.on_event({"t": "watered", "garden": G_EMPTY})
    chk("watered 푸시: 줄과 친구 화단을 바꾼다", vis.v["garden"] == G_EMPTY
        and g.last("show_friend") == ("show_friend", G_EMPTY)
        and row_dead(water_row(vis, lead), WATER_ROW + " (심은 화분 없음)"), g.calls[-1:])
    vis.on_event({"t": "bundles", "bundles": [], "carry": vis.v.get("carry"), "garden": G_CAN})
    chk("bundles 푸시에 실려 와도", vis.v["garden"] == G_CAN and g.last("show_friend") == ("show_friend", G_CAN))
    n = len(g.named("show_friend"))
    vis.on_event({"t": "bundles", "bundles": [], "carry": vis.v.get("carry")})
    chk("  garden 이 안 실린 bundles 는 친구 화단을 건드리지 않는다", len(g.named("show_friend")) == n
        and vis.v["garden"] == G_CAN)
    vis.on_event({"t": "visit", "visit": TV.guest_view(garden=G_DONE)})
    chk("다시 붙어 같은 놀러 가기가 오면 그 view 로", vis.v["garden"] == G_DONE
        and g.last("show_friend") == ("show_friend", G_DONE))
    n = len(g.named("show_friend"))
    vis.on_event({"t": "visit", "visit": TV.guest_view()})          # 서버가 화단 view 를 못 만들어 칸째 뺐다
    chk("다시 붙은 view 에 garden 칸이 없으면 친구 화단 · 줄을 그대로 둔다 (검토 12)", len(g.named("show_friend")) == n
        and vis.v.get("garden") == G_DONE and row_dead(water_row(vis, lead), WATER_ROW + " (오늘 이미 받음)"),
        (g.calls[-1:], vis.v.get("garden"), water_row(vis, lead)))
    vis.on_event({"t": "watered"})
    chk("  garden 이 안 실린 watered 푸시도 그대로 둔다", len(g.named("show_friend")) == n
        and vis.v.get("garden") == G_DONE, g.calls[-1:])
    vis.on_event({"t": "visit", "visit": TV.guest_view(garden=None)})
    chk("  garden: None 이 오면 (주인 텃밭이 닫혔다) 걷는다", g.last("show_friend") == ("show_friend", None)
        and water_row(vis, lead) is None, g.calls[-1:])
    vis.on_event({"t": "visit", "visit": TV.guest_view(garden=G_DONE)})

    print("\n=== 놀러 가 있는 동안 친구 화단을 다시 묻는다 (5분마다 · 0시 바로 뒤, 검토 2 · 4 · 9 · 13) ===")
    import calendar
    eve = calendar.timegm((2026, 11, 27, 14, 59, 50))            # 2026-11-27 23:59:50 KST
    noon = calendar.timegm((2026, 11, 27, 3, 0, 0))              # 12:00 KST
    chk("다음 0시(KST)까지 초", abs(V.kst_midnight_in(eve) - 10.0) < 1e-6
        and abs(V.kst_midnight_in(noon) - 12 * 3600) < 1e-6, (V.kst_midnight_in(eve), V.kst_midnight_in(noon)))
    chk("  다시 묻는 때: 낮에는 5분, 0시 바로 앞이면 0시 바로 뒤", vis._garden_wait(noon) == 5 * 60 * 1000
        and 10 * 1000 < vis._garden_wait(eve) <= 30 * 1000, (vis._garden_wait(noon), vis._garden_wait(eve)))
    chk("들어올 때 다시 묻기를 걸어 둔다", vis._garden_poll is not None)
    vis.GARDEN_POLL_MS = 300
    vis._take_garden(G_EMPTY)                    # 들어올 때는 심은 화분이 없었다
    app.api.state_visit = TV.guest_view(garden=G_CAN)                # 그사이 주인이 심었다
    n_state = app.api.calls.count(("state",))
    vis._arm_garden_poll()
    wait(root, lambda: app.api.calls.count(("state",)) >= n_state + 2, 4)
    settle(root, 0.05)
    chk("때가 되면 놀러 가기 상태를 다시 물어 줄과 친구 화단을 맞춘다 (그 뒤에도 다시 건다)",
        app.api.calls.count(("state",)) >= n_state + 2 and vis.v["garden"] == G_CAN
        and g.last("show_friend") == ("show_friend", G_CAN) and water_row(vis, lead).get("command") is not None,
        (app.api.calls.count(("state",)) - n_state, vis.v.get("garden"), water_row(vis, lead)))
    del vis.GARDEN_POLL_MS
    vis._arm_garden_poll()
    app.api.state_visit = None

    print("\n=== 끝나면 ===")
    vis.v["garden"] = G_CAN
    water_row(vis, lead)["command"]()
    vis.on_event({"t": "end", "id": 7, "by": "guest", "text": "돌아왔다"})
    root.update()
    chk("show_friend(None) - 내 화단으로", g.last("show_friend") == ("show_friend", None), g.calls[-2:])
    chk("  다시 묻기도 멈춘다", vis._garden_poll is None, vis._garden_poll)
    settle(root, 0.4)
    chk("  끝난 뒤 온 물 답은 버린다 (말풍선 · 화단 그대로)", g.last("show_friend") == ("show_friend", None)
        and not vis._watering and btext(vis, lead) is None, (g.calls[-2:], btext(vis, lead)))
    wait(root, lambda: vis._home is None and not ov.locked, 10)

    print("\n=== 친구 텃밭이 없는 집 (시즌 6 · 옛 서버) ===")
    g.calls = []
    vis.enter(TV.guest_view(id=8))
    wait(root, lambda: vis.bubbles.get(id(lead)) is not None, 3)
    chk("안내 글은 예전 그대로 ('화분에 물 주기' 없음)", btext(vis, lead) == V.GUEST_HINT
        and WATER_ROW not in V.GUEST_HINT, btext(vis, lead))
    chk("  줄도 없다", water_row(vis, lead) is None)
    vis.leave(None, tell=False, walk=False)
    settle(root, 0.2)

    print("\n=== 텃밭이 없는 앱 · 터지는 텃밭 ===")
    app.garden = None
    vis.enter(TV.guest_view(id=9, garden=G_CAN))
    root.update()
    chk("app.garden 이 없어도 들어간다, 줄은 view 대로", vis.active and water_row(vis, lead) is not None)
    vis.on_event({"t": "watered", "garden": G_DONE})
    chk("  푸시도 view 만 바꾼다", vis.v["garden"] == G_DONE)
    vis.leave(None, tell=False, walk=False)
    settle(root, 0.2)
    app.garden = FakeGarden(boom=True)
    n_log = len(logs)
    vis.enter(TV.guest_view(id=10, garden=G_CAN))
    root.update()
    chk("show_friend 가 터져도 놀러 가기는 들어간다 (기록에 남긴다)", vis.active and vis.guest
        and len(logs) > n_log, logs[n_log:])
    vis.leave(None, tell=False, walk=False)
    chk("  끝내기도", not vis.active and not ov.locked)
    settle(root, 0.2)
    app.visit = None


def host_part(root, ov, app, logs):
    print("\n=== 주인: 손님이 내 화분에 물을 줬다 ===")
    g = FakeGarden()
    app.garden = g
    vis = V.Visit(app)
    vis.sock = TV.Sock()
    app.visit = vis
    vis.enter(TV.host_view())
    root.update()
    vp = vis.visitor
    wait(root, lambda: getattr(vp, "_stroll", None) is None, 10)
    corner, facing0 = (vp.x, vp.y), vp.facing
    chk("놀러 온 포켓몬이 구석에 섰다 (준비)", TV.at_corner(ov, vp), corner)

    g.where = None
    vis.on_event({"t": "water", "from": "손님", "garden": CARD})
    root.update()
    chk("화단이 숨겨져 있으면(spot None) 말풍선만", btext(vis, vp) == V.WATERED % "손님"
        and not g.named("play_water") and getattr(vp, "_stroll", None) is None and (vp.x, vp.y) == corner,
        (btext(vis, vp), g.calls))
    chk("  카드는 적용한다", g.last("note") == ("note", CARD), g.calls)
    chk("  말풍선 글", V.WATERED % "손님" == "손님 님이 화분에 물을 줬어요 +1")

    g.calls = []
    sx, sy = foot(vp)
    spot = (sx - U.h(120), sy)
    g.where = spot
    card2 = dict(CARD, harvested=1)
    vis.on_event({"t": "water", "from": "손님", "garden": card2})
    settle(root, 0.3)
    chk("화단이 보이면 놀러 온 포켓몬이 화단 쪽으로 걷는다", vp.state == "walk" and vp.x < corner[0]
        and getattr(vp, "_stroll", None) is not None, (vp.x, corner[0], vp.state))
    chk("  닿기 전에는 물 연출도 카드도 아직", not g.named("play_water") and not g.named("note"), g.calls)
    wait(root, lambda: g.named("play_water"), 8)
    fx, fy = foot(vp)
    chk("닿으면 play_water(손님 이름)", g.named("play_water") == [("play_water", "손님")], g.calls)
    chk("  발이 spot 에 있다", abs(fx - spot[0]) < 2 and abs(fy - spot[1]) < 2, ((fx, fy), spot))
    chk("  그다음 카드 적용", [c[0] for c in g.calls if c[0] != "spot"] == ["play_water", "note"]
        and g.last("note") == ("note", card2), g.calls)
    settle(root, 0.3)
    chk("  잠깐 화단 앞에 서 있는다", abs(foot(vp)[0] - spot[0]) < 2 and vp.state == "idle")
    wait(root, lambda: vis._water_job is None and getattr(vp, "_stroll", None) is None
         and (vp.x, vp.y) == corner, 10)
    chk("그다음 제자리(구석)로 돌아온다", (vp.x, vp.y) == corner and TV.at_corner(ov, vp) and vp.state == "idle",
        ((vp.x, vp.y), corner))
    chk("  들어왔을 때처럼 왼쪽을 보고 선다", vp.facing == facing0, (vp.facing, facing0))

    g.calls = []
    x1, _y1, _W, _H = TV.area_of(ov)
    g.where = (x1 + 40, sy)
    t0 = time.time()
    vis.on_event({"t": "water", "from": "손님", "garden": CARD})
    wait(root, lambda: g.named("play_water"), V.WATER_WALK_SEC + 4)
    took = time.time() - t0
    chk("멀리 있어도 %.0f초 남짓에 닿는다" % V.WATER_WALK_SEC, g.named("play_water")
        and took < V.WATER_WALK_SEC + 1.5, took)
    wait(root, lambda: vis._water_job is None and getattr(vp, "_stroll", None) is None
         and (vp.x, vp.y) == corner, V.WATER_WALK_SEC + 6)
    chk("  돌아오는 것도", (vp.x, vp.y) == corner, (vp.x, vp.y))

    print("\n=== 닿았는데 화단이 연출을 못 하면 말풍선 (걷는 사이 숨김 · 없어짐, 검토 6 · 10 · 17) ===")
    g.calls = []
    g.where = spot
    g.plays = False
    vis._close_bubbles()
    vis.on_event({"t": "water", "from": "손님", "garden": card2})
    wait(root, lambda: g.named("play_water"), 8)
    root.update()
    chk("play_water 가 False 면 놀러 온 포켓몬 위에 '손님 님이 화분에 물을 줬어요 +1' · 카드는 적용",
        btext(vis, vp) == V.WATERED % "손님" and g.last("note") == ("note", card2), (btext(vis, vp), g.calls))
    g.plays = True
    wait(root, lambda: vis._water_job is None and getattr(vp, "_stroll", None) is None
         and (vp.x, vp.y) == corner, 10)
    vis._close_bubbles()

    print("\n=== 걷는 중에 바뀌면 ===")
    g.calls = []
    g.where = spot
    vis.on_event({"t": "water", "from": "손님", "garden": card2})
    settle(root, 0.2)
    size0 = int(ov.settings["targetHeight"])
    app.set_size(size0 + 8)
    settle(root, 0.3)
    nvp = vis.visitor
    chk("크기를 바꾸면 (도트를 새로 만든다) 카드는 바로 적용하고 물 연출도 한다, 새 도트는 구석에",
        g.last("note") == ("note", card2) and g.named("play_water") == [("play_water", "손님")]
        and vis._water_job is None and nvp is not None and nvp is not vp and TV.at_corner(ov, nvp), g.calls)
    app.set_size(size0)
    settle(root, 0.3)
    vp = vis.visitor
    corner = (vp.x, vp.y)
    g.calls = []
    vis.on_event({"t": "water", "from": "손님", "garden": card2})
    settle(root, 0.2)
    vis.on_event({"t": "water", "from": "손님2", "garden": CARD})
    settle(root, 0.2)
    chk("걷는 중에 또 오면 앞의 것은 바로 마무리 (카드 둘 다 적용)", [c for c in g.calls if c[0] == "note"]
        == [("note", card2)] and g.named("play_water")[:1] == [("play_water", "손님")], g.calls)
    wait(root, lambda: len(g.named("play_water")) == 2 and len(g.named("note")) == 2, 8)
    chk("  뒤의 것도 걸어가서 한다", g.named("play_water")[-1] == ("play_water", "손님2")
        and g.last("note") == ("note", CARD), g.calls)
    wait(root, lambda: vis._water_job is None and (vp.x, vp.y) == corner, 10)
    g.calls = []
    vis.on_event({"t": "water", "from": "손님", "garden": card2})
    settle(root, 0.2)
    vis.on_event({"t": "end", "id": 7, "by": "guest", "text": "돌아갔다"})
    root.update()
    chk("걷는 중에 놀러 가기가 끝나도 카드는 적용된다", g.last("note") == ("note", card2)
        and vis._water_job is None, g.calls)
    settle(root, 0.4)
    chk("  놀러 온 포켓몬은 그대로 걸어 나간다", vp.state == "walk" and vp in vis._leaving, (vp.x, vp.state))
    wait(root, lambda: not ov.extra, 10)

    print("\n=== 놀러 온 손님이 없을 때 · 텃밭이 없는 앱 ===")
    g.calls = []
    g.where = spot
    lead1 = vis.my_lead_pet()
    vis.on_event({"t": "water", "from": "손님", "garden": CARD})
    root.update()
    chk("놀러 가기가 이미 끝났으면 걷지 않고 화단 연출 + 카드 (말풍선은 화단 몫)",
        [c[0] for c in g.calls if c[0] != "spot"] == ["play_water", "note"] and btext(vis, lead1) is None
        and vis._water_job is None, (g.calls, btext(vis, lead1)))
    g.calls = []
    g.plays = False
    vis.on_event({"t": "water", "from": "손님", "garden": CARD})
    root.update()
    chk("  화단이 연출을 못 하면(play_water False) 내 맨 앞 포켓몬 위에 말풍선 (검토 6)",
        g.named("play_water") and btext(vis, lead1) == V.WATERED % "손님" and g.last("note") == ("note", CARD),
        (g.calls, btext(vis, lead1)))
    g.plays = True
    vis._close_bubbles()
    g.calls = []
    g.where = None
    vis.on_event({"t": "water", "from": "손님", "garden": CARD})
    root.update()
    chk("  화단도 숨겨져 있으면 카드 적용 + 내 맨 앞 포켓몬 위에 말풍선",
        g.last("note") == ("note", CARD) and not g.named("play_water") and btext(vis, lead1) == V.WATERED % "손님",
        (g.calls, btext(vis, lead1)))
    vis._close_bubbles()
    app.garden = None
    vis.enter(TV.host_view(id=12))
    vp = vis.visitor
    wait(root, lambda: getattr(vp, "_stroll", None) is None, 10)
    n_log = len(logs)
    vis.on_event({"t": "water", "from": "손님", "garden": CARD})
    root.update()
    chk("app.garden 이 없으면 말풍선만 (오류 없음)", btext(vis, vp) == V.WATERED % "손님"
        and getattr(vp, "_stroll", None) is None and len(logs) == n_log, logs[n_log:])
    app.garden = FakeGarden(spot=spot, boom=True)
    vis.on_event({"t": "water", "from": "손님", "garden": CARD})
    root.update()
    chk("  텃밭이 터져도 말풍선은 뜬다", btext(vis, vp) == V.WATERED % "손님" and vis.active, btext(vis, vp))
    vis.leave(None, tell=False, walk=False)
    settle(root, 0.2)

    print("\n=== 걸어 들어오는 중에 물이 오면 (검토 11) ===")
    g = FakeGarden()
    app.garden = g
    vis.enter(TV.host_view(id=13))
    vp = vis.visitor
    root.update()
    cx, cy = vis._corner(vp)
    chk("(준비) 놀러 온 포켓몬이 걸어 들어오는 중", vp is not None and getattr(vp, "_stroll", None) is not None,
        vp and (vp.x, cx))
    spot = (cx + vp.fw / 2.0 - U.h(120), cy + vp.fh)
    g.where = spot
    vis.on_event({"t": "water", "from": "손님", "garden": CARD})
    settle(root, 0.1)
    st = getattr(vp, "_stroll", None)
    chk("들어오는 걸음은 그대로 (구석으로) · 물은 아직", st is not None and (st.tx, st.ty) == (cx, cy)
        and not g.named("play_water") and not g.named("note"), (st and (st.tx, st.ty), (cx, cy), g.calls))
    wait(root, lambda: g.named("play_water"), 20)
    fx, fy = foot(vp)
    chk("구석에 닿으면 '손님 님이 놀러 왔어요!' 가 뜬다 (물 걸음이 덮지 않는다)", vis.v is not None
        and any(b.label.cget("text") == V.ARRIVED % "손님" for b in vis._stack_of(vp)),
        [b.label.cget("text") for b in vis._stack_of(vp)])
    chk("  그다음 화단으로 걸어가 물 · 카드", g.named("play_water") == [("play_water", "손님")]
        and abs(fx - spot[0]) < 2 and abs(fy - spot[1]) < 2 and g.last("note") == ("note", CARD),
        ((fx, fy), spot, g.calls))
    wait(root, lambda: vis._water_job is None and getattr(vp, "_stroll", None) is None
         and (vp.x, vp.y) == (cx, cy), 10)
    chk("  제자리(구석)로 돌아온다", (vp.x, vp.y) == (cx, cy), (vp.x, vp.y))
    vis.leave(None, tell=False, walk=False)
    settle(root, 0.2)
    g.calls = []
    vis.enter(TV.host_view(id=14))
    root.update()
    vis.on_event({"t": "water", "from": "손님", "garden": CARD})
    root.update()
    vis.on_event({"t": "end", "id": 14, "by": "guest", "text": "돌아갔다"})
    root.update()
    chk("들어오는 중에 물이 오고 바로 끝나도 화단 연출 · 카드는 한다", g.named("play_water") == [("play_water", "손님")]
        and g.last("note") == ("note", CARD) and vis._water_job is None, g.calls)
    wait(root, lambda: not ov.extra, 10)
    app.visit = None


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors, logs = [], []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_err
    real_log = config.log

    def log(msg, *a, **k):
        logs.append(msg)
        return real_log(msg, *a, **k)
    config.log = log
    for n, col in ((TV.PIKA, (240, 210, 40, 255)), (TV.BLAST, (60, 90, 200, 255)), (4, (230, 110, 40, 255)),
                   (7, (80, 140, 220, 255)), (TV.SAUR, (60, 160, 90, 255))):
        TV.SHEETS[n] = TV.make_sheet("g%d.png" % n, 32, col)
        TV.FILES[n] = TV.make_dot("gd%d.png" % n, col)
    sprite_cache.ensure = lambda api, num, shiny=False: TV.FILES.get(num)
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (
        TV.SHEETS.get(num) if name == "Walk" and TV.SHEETS.get(num) else (None, None))
    settings = dict(config.DEFAULTS)
    settings["megaWalk"] = []
    ov = overlay.Overlay(root, settings)
    ov.paths.update(dict(((n, False), p) for n, p in TV.FILES.items()))
    ov.walks.update(dict(TV.SHEETS))
    ov.sync([TV.mon(1, 4, 0, "파이리"), TV.mon(2, 7, 1, "꼬부기"), TV.mon(3, TV.SAUR, 2, "이상해씨")], {}, {})
    ov.start()
    settle(root, 0.3)
    app = TV.MiniApp(root, ov)
    app.api = Api()
    try:
        guest_part(root, ov, app, logs)
        host_part(root, ov, app, logs)
    finally:
        ov.stop()
        ov.clear()
        settle(root, 0.2)
        config.log = real_log
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    bad = [m for m in logs if "놀러 가기 오류" in str(m)]
    chk("놀러 가기 소켓 처리에서 난 오류가 없다", not bad, bad[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
