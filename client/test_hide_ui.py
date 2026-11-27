# -*- coding: utf-8 -*-
"""숨바꼭질 (시즌 7, 2026-11-27) 앱 검사 — 숨을 자리 고르기 · 숨은 포켓몬 창(Hider) · 야생 흐름 · 설정 · 정리.

    python client/test_hide_ui.py
    python client/run_as_windows.py client/test_hide_ui.py

서버는 안 띄운다 - 가짜 api 가 API 계약 (design-notes/2026-11-27-hide-and-seek-plan.md 'API 계약') 모양으로 답한다.
**진짜 Overlay · Hider 창 · WildController 를 띄운다.** 화면 · 다른 앱 창 목록 · 겹침 순서 함수는 가짜로 바꿔 끼워
'무엇을 불렀나' 를 본다 (맥이면 끝에서 진짜 겹침 순서도 한 번 건다 - Step 0 시험과 같은 것).

  1. hide_spots: 단일 · 왼쪽(음수) 모니터 · 위 모니터 · 작업표시줄 아래/왼쪽/숨김 · 맥 Dock 왼쪽/아래 ·
     가짜 창 목록으로 규칙 전부 (붙은 변 금지 · 영역 120px · 모서리 160px · 40~55% · 맥 위쪽 금지 · 최대화 창 제외 ·
     보이는 자리만 · 앞 창이 덮은 자리 금지 · DPI 다른 창 제외 · 윈도 오른쪽/작업표시줄 먼저 · 맥 왼쪽/Dock 먼저) + 따라가기
     + 이 앱의 창 · 항상 위 창은 가리는 창으로만 · 같은 앱 창 안의 자식 창/시트에는 안 건다 (검토 #4 · #5 · #6)
  2. hide=1 을 보낼 때 / 안 보낼 때 (설정 · 첫 값 · 놀러 가기 · 집중 · 긴급 숨기기 · 전체 화면)
  3. src hide → peek 도트를 받고 Hider 가 grass 칸에 · 못 받거나 숨을 자리가 없으면 GrassPatch
  4. Hider 는 항상 위가 아니다 (keep_on_top · show_again 뒤에도) · 겹침 함수가 불린다 · 긴급 숨기기 동안은 안 건다
  5. 누르기 → reveal 한 번 → '찾았다!' → 뛰어 들어와 영역 가장자리에 WildPet · 숨겨진 특성이면 '숨겨진 특성!'
  6. 창 뒤 자리: 창이 움직이면 숨었다가 따라감 · 창이 사라지면 다른 자리 · 꼼지락/내밀기가 창 크기를 안 바꿈
     6c. 배율이 다른 모니터면 작업표시줄 자리만 · 창 뒤 자리는 보일 띠를 겹침 함수에 넘긴다 (검토 #3 · #5 · #7)
  7. 4분 만료 (expiresIn 240 · 놓치면 flee) · 안내 셋 · 2분 '?' (이벤트 연출 끔이면 없음) · 맥 오른클릭은 안 받음
  8. 설정 하위 칸 (풀숲 끄면 죽음) · 트레이 · DP 테마 · 정리 뒤 남는 창 · after 없음
  9. 플랫폼: 윈도 창 거르기 · 전체 화면 판정 (가짜), 윈도 창 좌표 · 모니터 DPI · 이 앱의 창 (가짜 Win32),
     맥 창 목록 거르기 (가짜 CGWindowList), 맥 진짜 겹침 순서 · 걸고 나서 띠가 가려졌나 (맥에서만)
"""
import os
import random
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-hide-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from poketdesktop import config                             # noqa: E402
from poketdesktop import hide as HD                         # noqa: E402
from poketdesktop import hide_spots as SP                   # noqa: E402
from poketdesktop import overlay as OV                      # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import sprite_cache, stealth, walk_cache, wild_ui  # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop.app import App                            # noqa: E402

HOME = os.environ["POKET_HOME"]
OK = FAIL = 0
PM = PLAT._M                     # 고른 플랫폼 모듈 (겹침 순서 함수를 바꿔 끼운다)

# 가짜 화면: 1600x1000 하나, 아래 작업표시줄 40. 활동 영역은 오른쪽 아래.
SCREENS = [(0, 0, 1600, 1000)]
WORKS = [(0, 0, 1600, 960)]
AREA = (900, 420, 1400, 820)


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


def top(w):
    return int(w.attributes("-topmost"))


def bubbles(pet):
    """그 도트 위에 지금 떠 있는 말풍선 글."""
    out = []
    for b in getattr(pet, "_bubbles", ()):
        try:
            if not b.dead and b.label.winfo_exists():
                out.append(b.label.cget("text"))
        except tk.TclError:
            pass
    return out


def walk(w):
    yield w
    for c in w.winfo_children():
        for x in walk(c):
            yield x


def dot_path():
    p = os.path.join(HOME, "dot.png")
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    for x in range(8, 32):
        for y in range(6, 36):
            im.putpixel((x, y), (240, 120, 40, 255))
    im.save(p)
    return p


# ================================================================ 1. 자리 고르기 (순수)
def shown(s, w, h, p=None):
    return SP.shown_rect(s["side"], s["line"], s["along"], w, h, s["peek"] if p is None else p)


def rule_errors(s, area, screens, works, windows, w, h, os_name):
    """한 자리가 어긴 규칙 목록."""
    bad = []
    i = SP.monitor_for(area, screens)
    scr, work = screens[i], works[i]
    if s["screen"] != i:
        bad.append("다른 모니터")
    r = shown(s, w, h)
    big = shown(s, w, h, SP.more_px(SP.body_len(s["side"], w, h), s["peek"]))
    if not SP.inside(big, work):
        bad.append("작업 영역 밖 %r" % (big,))
    if SP.overlaps((s["x"], s["y"], s["x"] + w, s["y"] + h), SP.grow(area, SP.AREA_GAP)):
        bad.append("영역 120px 안")
    if any(SP.overlaps(big, c) for c in SP.corners(work)):
        bad.append("모서리 160px 안")
    L = SP.body_len(s["side"], w, h)
    p = s["peek"]
    if not (p >= min(L, SP.SHOW_PX) and p >= int(L * SP.SHOW_MIN) and p <= max(SP.SHOW_PX, L * SP.SHOW_MAX + 0.5)):
        bad.append("보이는 몸 %d/%d" % (p, L))
    if (r[2] - r[0]) * (r[3] - r[1]) <= 0:
        bad.append("안 보임")
    if s["kind"] == "edge":
        if any(SP.touches(scr, o, s["edge"]) for o in screens):
            bad.append("붙은 변")
        if any(SP.overlaps(r, tuple(win["rect"])) for win in windows):
            bad.append("창이 덮은 가장자리")
        if SP.insets(scr, work)[s["edge"]] != 0:
            bad.append("작업표시줄 변의 가장자리")
    if s["kind"] == "bar" and SP.insets(scr, work)[s["edge"]] < SP.BAR_MIN:
        bad.append("작업표시줄 없는 변의 막대 자리")
    if os_name == "mac" and s["edge"] == "top" and s["kind"] != "window":
        bad.append("맥 위쪽")
    if s["kind"] == "window":
        k = next(n for n, win in enumerate(windows) if win.get("id") == s["anchor"])
        win = windows[k]
        if win.get("max") or SP.is_max(tuple(win["rect"]), work) or win.get("odd"):
            bad.append("최대화/DPI 창에 걸었다")
        if any(SP.overlaps(r, tuple(o["rect"])) for o in windows[:k]):
            bad.append("앞 창이 덮은 창 뒤 자리")
        if SP.overlaps(r, tuple(win["rect"])):
            bad.append("보이는 칸이 그 창 안")
    return bad


def many(area, screens, works, windows, os_name, n=300, wh=(50, 50), kinds=SP.KINDS):
    out = []
    for seed in range(n):
        s = SP.pick(area, screens, works, windows, wh, os_name, random.Random(seed), kinds=kinds)
        if s is not None:
            out.append(s)
    return out


def all_ok(name, spots, area, screens, works, windows, os_name, wh=(50, 50)):
    errs = []
    for s in spots:
        e = rule_errors(s, area, screens, works, windows, wh[0], wh[1], os_name)
        if e:
            errs.append((s["kind"], s["edge"], e))
    chk(name, spots and not errs, (len(spots), errs[:3]))


def kinds_of(spots):
    out = {}
    for s in spots:
        k = (s["kind"], s["edge"])
        out[k] = out.get(k, 0) + 1
    return out


def spots_part():
    print("=== 1. 숨을 자리 고르기 (hide_spots) ===")
    w, h = 50, 50
    # place: 네 방향 - 보이는 칸이 경계 바로 바깥에 붙는다
    chk("place top: 경계 위로 p 만큼", SP.shown_rect("top", 500, 100, w, h, 22) == (100, 478, 150, 500))
    chk("place bottom: 경계 아래로 (뒤집은 그림의 아랫줄)", SP.shown_rect("bottom", 0, 100, w, h, 22) == (100, 0, 150, 22)
        and SP.place("bottom", 0, 100, w, h, 22)[2] == (0, 28, 50, 50))
    chk("place left: 경계 왼쪽으로", SP.shown_rect("left", 1600, 300, w, h, 25) == (1575, 300, 1600, 350))
    chk("place right: 경계 오른쪽으로", SP.shown_rect("right", 0, 300, w, h, 25) == (0, 300, 25, 350))
    rng = random.Random(1)
    ps = [SP.peek_px(48, rng) for _ in range(200)]
    chk("보이는 몸 (48px): 22px 이상 · 55% 이하", min(ps) >= 22 and max(ps) <= 26, (min(ps), max(ps)))
    ps = [SP.peek_px(100, rng) for _ in range(200)]
    chk("보이는 몸 (100px): 40~55%", min(ps) >= 40 and max(ps) <= 55, (min(ps), max(ps)))
    # 좁은 종(훔처우 22px · 저리어 20px)이 통째로 보이던 것 (실제 앱 시험 11/27): 55% 를 넘지 않는다
    for n in (20, 22, 30, 36):
        ps = [SP.peek_px(n, rng) for _ in range(200)]
        chk("  좁은 몸 (%dpx) 도 55%% 를 넘지 않는다" % n, max(ps) <= int(n * SP.SHOW_MAX) and min(ps) >= 1, (min(ps), max(ps)))
    chk("더 내밀기 70%", SP.more_px(100, 45) == 70 and SP.more_px(30, 22) == 23)
    # 활동 영역에서 '120px 넘게' - 딱 120 은 안 된다
    a = (1000, 500, 1200, 700)
    sp_ok = {"side": "right", "line": 0, "along": 0, "x": 1200 + SP.AREA_GAP, "y": 600, "peek": 22}
    chk("  영역과 딱 120px 붙은 자리는 안 된다", SP.overlaps((sp_ok["x"], sp_ok["y"], sp_ok["x"] + 10, sp_ok["y"] + 10),
                                                   SP.grow(a, SP.AREA_GAP + 1)))
    chk("  숨은 포켓몬 시계는 서버 기준 (expiresIn 175 → 65초 흐름)", abs(HD.age_of({"expiresIn": 175}) - 65.0) < 1e-6
        and HD.age_of({}) == 0.0 and HD.age_of({"expiresIn": 999}) == 0.0)

    # 단일 모니터 · 아래 작업표시줄 (윈도우)
    sp = many(AREA, SCREENS, WORKS, [], "win")
    all_ok("단일 모니터 (윈도우): 300번 모두 규칙 안", sp, AREA, SCREENS, WORKS, [], "win")
    k = kinds_of(sp)
    chk("  창이 없으면 작업표시줄 · 가장자리만 (창 뒤 없음)", ("bar", "bottom") in k and not any(a == "window" for a, _ in k), k)
    chk("  아래 작업표시줄 변에는 가장자리 자리가 없다", ("edge", "bottom") not in k, k)
    chk("  윈도우는 오른쪽 변 · 작업표시줄을 먼저 (왼쪽 변의 세 배 넘게)",
        k.get(("bar", "bottom"), 0) + k.get(("edge", "right"), 0) > 3 * k.get(("edge", "left"), 0), k)
    chk("  윈도우는 위쪽 변도 쓴다 (위에서 아래로 - 뒤집은 그림)", k.get(("edge", "top"), 0) > 0
        and all(s["side"] == "bottom" for s in sp if s["edge"] == "top"), k)

    # 왼쪽 모니터 (음수 좌표)
    scr2 = [(0, 0, 1920, 1080), (-1920, 0, 0, 1080)]
    wk2 = [(0, 0, 1920, 1040), (-1920, 0, 0, 1040)]
    a1 = (1300, 600, 1820, 1000)
    sp = many(a1, scr2, wk2, [], "win")
    all_ok("왼쪽 모니터가 붙은 주 화면: 규칙 안", sp, a1, scr2, wk2, [], "win")
    chk("  붙은 왼쪽 변은 안 쓴다", ("edge", "left") not in kinds_of(sp), kinds_of(sp))
    a2 = (-1500, 500, -1000, 950)
    sp = many(a2, scr2, wk2, [], "win")
    all_ok("왼쪽(음수) 모니터에 영역: 규칙 안", sp, a2, scr2, wk2, [], "win")
    chk("  자리가 그 모니터 안 (음수 좌표) · 붙은 오른쪽 변은 안 쓴다",
        all(-1920 <= shown(s, w, h)[0] and shown(s, w, h)[2] <= 0 for s in sp)
        and ("edge", "right") not in kinds_of(sp) and ("edge", "left") in kinds_of(sp), kinds_of(sp))

    # 위에 모니터
    scr3 = [(0, 0, 1920, 1080), (0, -1080, 1920, 0)]
    wk3 = [(0, 0, 1920, 1040), (0, -1080, 1920, -40)]
    sp = many(a1, scr3, wk3, [], "win")
    all_ok("위쪽 모니터가 붙은 화면: 규칙 안", sp, a1, scr3, wk3, [], "win")
    chk("  붙은 위쪽 변은 안 쓴다", ("edge", "top") not in kinds_of(sp), kinds_of(sp))

    # 작업표시줄 왼쪽 · 숨김
    wk4 = [(60, 0, 1920, 1080)]
    scr4 = [(0, 0, 1920, 1080)]
    sp = many(a1, scr4, wk4, [], "win")
    all_ok("작업표시줄 왼쪽: 규칙 안", sp, a1, scr4, wk4, [], "win")
    k = kinds_of(sp)
    chk("  왼쪽 막대 자리 (오른쪽으로 빼꼼, 경계 60) · 왼쪽 가장자리 없음 · 아래 가장자리 있음",
        ("bar", "left") in k and all(s["side"] == "right" and s["line"] == 60 for s in sp if s["kind"] == "bar")
        and ("edge", "left") not in k and ("edge", "bottom") in k, k)
    for wk5, why in (([(0, 0, 1920, 1078)], "자동 숨김(2px)"), ([(0, 0, 1920, 1080)], "작업 영역 = 화면")):
        sp = many(a1, scr4, wk5, [], "win")
        all_ok("작업표시줄 %s: 규칙 안" % why, sp, a1, scr4, wk5, [], "win")
        k = kinds_of(sp)
        chk("  막대 자리 없음", not any(a == "bar" for a, _ in k), k)
    chk("  자동 숨김(2px) 변은 가장자리도 안 쓴다", ("edge", "bottom") not in kinds_of(many(a1, scr4, [(0, 0, 1920, 1078)], [], "win")))

    # 맥: Dock 왼쪽 · 아래
    ms = [(0, 0, 1440, 900)]
    mw = [(80, 30, 1440, 900)]
    am = (900, 420, 1380, 860)
    sp = many(am, ms, mw, [], "mac")
    all_ok("맥 Dock 왼쪽: 규칙 안", sp, am, ms, mw, [], "mac")
    k = kinds_of(sp)
    chk("  위쪽(메뉴 막대)은 막대 · 가장자리 둘 다 안 쓴다", not any(e == "top" for _, e in k), k)
    chk("  Dock 자리 (오른쪽으로 빼꼼, 경계 80) 가 가장 많다", k.get(("bar", "left"), 0) == max(k.values())
        and all(s["line"] == 80 for s in sp if s["kind"] == "bar"), k)
    chk("  Dock 자리는 화면 가운데 Dock 두께 x3 안", all(450 - 3 * 80 <= s["along"] and s["along"] + 50 <= 450 + 3 * 80
                                                    for s in sp if s["kind"] == "bar"))
    mw2 = [(0, 30, 1440, 808)]
    am2 = (900, 300, 1380, 640)
    sp = many(am2, ms, mw2, [], "mac")
    all_ok("맥 Dock 아래: 규칙 안", sp, am2, ms, mw2, [], "mac")
    k = kinds_of(sp)
    chk("  맥은 왼쪽 변 · Dock 을 먼저 (오른쪽 변보다 세 배 넘게)",
        k.get(("edge", "left"), 0) + k.get(("bar", "bottom"), 0) > 3 * k.get(("edge", "right"), 0), k)
    chk("  Dock 아래 자리는 가운데 (720 ± 92x3)", all(720 - 276 <= s["along"] and s["along"] + 50 <= 720 + 276
                                                 for s in sp if s["kind"] == "bar"))

    # 다른 앱 창
    wins = [{"rect": (200, 200, 900, 700), "id": 11, "max": False}]
    sp = many(AREA, SCREENS, WORKS, wins, "win")
    all_ok("창 하나: 규칙 안 (창 뒤 자리 포함)", sp, AREA, SCREENS, WORKS, wins, "win")
    ws = [s for s in sp if s["kind"] == "window"]
    chk("  창 뒤 자리가 나온다 (그 창에 걸고, 위 · 옆 가장자리 바깥으로)", ws and all(s["anchor"] == 11 for s in ws)
        and set(s["side"] for s in ws) <= {"top", "left", "right"} and "top" in set(s["side"] for s in ws), len(ws))
    chk("  창 위로 빼꼼이면 보이는 칸 아래 끝이 창 위 변", all(shown(s, w, h)[3] == 200 for s in ws if s["side"] == "top"))
    cover = [{"rect": (1450, 80, 1600, 500), "id": 12}, {"rect": (200, 200, 900, 700), "id": 11}]
    sp = many(AREA, SCREENS, WORKS, cover, "win")
    all_ok("오른쪽 가장자리를 덮은 작은 창: 덮인 가장자리는 안 고른다", sp, AREA, SCREENS, WORKS, cover, "win")
    front = [{"rect": (300, 120, 450, 230), "id": 10}, {"rect": (200, 200, 900, 700), "id": 11}]
    sp = many(AREA, SCREENS, WORKS, front, "win")
    all_ok("앞의 작은 창(150x110 - 걸 수 없음)이 덮은 창 뒤 자리는 안 고른다", sp, AREA, SCREENS, WORKS, front, "win")
    chk("  작은 창에는 걸지 않는다", all(s["anchor"] == 11 for s in sp if s["kind"] == "window")
        and any(s["kind"] == "window" for s in sp))
    mx = [{"rect": (0, 0, 1600, 960), "id": 5, "max": True}, {"rect": (200, 200, 900, 700), "id": 6}]
    sp = many(AREA, SCREENS, WORKS, mx, "win")
    chk("최대화 창이 맨 앞: 창 뒤 · 가장자리 없음, 작업표시줄만", sp and all(s["kind"] == "bar" for s in sp), kinds_of(sp))
    mx2 = [{"rect": (0, 0, 1600, 960), "id": 5}]
    chk("  '최대화' 표시가 없어도 작업 영역을 다 덮으면 최대화로 본다 (맥)",
        all(s["kind"] == "bar" for s in many(AREA, SCREENS, WORKS, mx2, "mac")))
    odd = [{"rect": (200, 200, 900, 700), "id": 7, "odd": True}]
    chk("DPI 가 다른 창(윈도우 odd)에는 걸지 않는다", not any(s["kind"] == "window" for s in many(AREA, SCREENS, WORKS, odd, "win")))
    small = [{"rect": (200, 200, 390, 330), "id": 8}]
    chk("200x150 보다 작은 창에는 걸지 않는다", not any(s["kind"] == "window" for s in many(AREA, SCREENS, WORKS, small, "win")))
    other_mon = [{"rect": (-900, 200, -200, 700), "id": 9}]
    chk("다른 모니터의 창에는 걸지 않는다",
        not any(s["kind"] == "window" for s in many(a1, scr2, wk2, other_mon, "win")))
    chk("고를 종류를 막으면 그 종류만 (kinds)", all(s["kind"] == "edge" for s in many(AREA, SCREENS, WORKS, wins, "win",
                                                                               kinds=("edge",))))
    chk("자리가 하나도 없으면 None", SP.pick(AREA, SCREENS, WORKS, mx, (50, 50), "win", random.Random(1),
                                       kinds=("window", "edge")) is None)

    print("=== 1c. 가리는 창 (이 앱의 창 · 항상 위) · 자식 창 (검토 #4 · #5 · #6) ===")
    cover2 = [{"rect": (1250, 60, 1600, 420), "id": 21, "own": True},      # 이 앱의 PC 박스가 오른쪽 위 가장자리를 덮었다
              {"rect": (40, 300, 340, 600), "id": 22, "top": True},         # 남의 '항상 위' 창이 왼쪽 가장자리를 덮었다
              {"rect": (200, 200, 900, 700), "id": 11}]
    for osn in ("win", "mac"):
        sp = many(AREA, SCREENS, WORKS, cover2, osn)
        all_ok("이 앱의 창 · 항상 위 창이 덮은 가장자리 · 창 뒤 자리는 안 고른다 (%s)" % osn, sp, AREA, SCREENS, WORKS,
               cover2, osn)
        chk("  이 앱의 창 · 항상 위 창에는 걸지 않는다 - 가리는 창으로만 (%s)" % osn,
            all(s["anchor"] == 11 for s in sp if s["kind"] == "window") and any(s["kind"] == "window" for s in sp),
            sorted(set(s["anchor"] for s in sp if s["kind"] == "window")))
    s21 = next((s for s in many(AREA, SCREENS, WORKS, [dict(cover2[0], own=False)], "win") if s["kind"] == "window"), None)
    chk("  이 앱의 창을 따라가지 않는다 (follow 도 own 이면 None)", s21 is not None
        and SP.follow(s21, [cover2[0]], AREA, SCREENS, WORKS, (w, h)) is None, s21)
    kakao = [{"rect": (300, 330, 560, 491), "id": 31, "pid": 7},         # 큰 창 안의 작은 창 (자식 창 · 시트) - 앞에 온다
             {"rect": (230, 160, 630, 800), "id": 32, "pid": 7}]
    ws = [s for s in many(AREA, SCREENS, WORKS, kakao, "mac") if s["kind"] == "window"]
    chk("같은 앱의 더 뒤 창 안에 통째로 든 창(자식 창 · 시트)에는 걸지 않는다 - 그 큰 창에 건다",
        ws and all(s["anchor"] == 32 for s in ws), sorted(set(s["anchor"] for s in ws)))
    ws = [s for s in many(AREA, SCREENS, WORKS, [dict(kakao[0], pid=8), kakao[1]], "mac") if s["kind"] == "window"]
    chk("  다른 앱 창 안에 놓인 창에는 건다 (같은 앱일 때만 자식으로 본다)", any(s["anchor"] == 31 for s in ws),
        sorted(set(s["anchor"] for s in ws)))
    nopid = [{k: v for k, v in win.items() if k != "pid"} for win in kakao]
    ws = [s for s in many(AREA, SCREENS, WORKS, nopid, "win") if s["kind"] == "window"]
    chk("  pid 를 안 주는 OS(윈도우)는 그대로 맨 앞 창에 건다", any(s["anchor"] == 31 for s in ws),
        sorted(set(s["anchor"] for s in ws)))

    print("=== 1b. 창 뒤 자리 따라가기 (follow) ===")
    s = next(s for s in many(AREA, SCREENS, WORKS, wins, "win") if s["kind"] == "window" and s["side"] == "top")
    moved = [{"rect": (300, 250, 1000, 750), "id": 11}]
    f = SP.follow(s, moved, AREA, SCREENS, WORKS, (w, h))
    chk("창이 (+100, +50) 옮기면 같은 자리(창 기준)로", f is not None and f["along"] == s["along"] + 100
        and f["line"] == 250 and f["arect"] == (300, 250, 1000, 750), (s["along"], f and f["along"]))
    chk("  그대로면 같은 값", SP.follow(s, wins, AREA, SCREENS, WORKS, (w, h)) == s)
    chk("  창이 없어지면 None", SP.follow(s, [], AREA, SCREENS, WORKS, (w, h)) is None)
    chk("  최대화하면 None", SP.follow(s, [{"rect": (0, 0, 1600, 960), "id": 11}], AREA, SCREENS, WORKS, (w, h)) is None)
    chk("  활동 영역 옆으로 오면 None", SP.follow(s, [{"rect": (850, 450, 1500, 900), "id": 11}], AREA, SCREENS, WORKS,
                                           (w, h)) is None)
    b = next(s for s in many(AREA, SCREENS, WORKS, [], "win") if s["kind"] == "bar")
    chk("작업표시줄 자리: 그대로면 맞다", SP.still_ok(b, AREA, SCREENS, WORKS, (w, h)))
    chk("  작업표시줄을 왼쪽으로 옮기거나 자동 숨김이면 아니다", not SP.still_ok(b, AREA, SCREENS, [(60, 0, 1600, 1000)], (w, h))
        and not SP.still_ok(b, AREA, SCREENS, [(0, 0, 1600, 998)], (w, h)))
    chk("  영역을 그 자리 옆으로 다시 그리면 아니다",
        not SP.still_ok(b, (b["along"] - 60, 500, b["along"] + 200, 900), SCREENS, WORKS, (w, h)))
    e = next(s for s in many(AREA, SCREENS, WORKS, [], "win") if s["kind"] == "edge")
    chk("가장자리 자리: 그대로면 맞다 · 그 변에 작업표시줄이 오면 아니다", SP.still_ok(e, AREA, SCREENS, WORKS, (w, h))
        and not SP.still_ok(e, AREA, SCREENS, [{"right": (0, 0, 1560, 1000), "top": (0, 40, 1600, 1000),
                                                 "left": (40, 0, 1600, 1000)}[e["edge"]]], (w, h)), e["edge"])
    chk("  앞에 다른 창이 와서 덮어도 그대로 (겹침 순서가 가린다 - 쫓아다니지 않는다)",
        SP.follow(s, [{"rect": (s["along"] - 10, 100, s["along"] + 80, 199), "id": 3}] + wins, AREA, SCREENS, WORKS,
                  (w, h)) == s)


# ================================================================ 2~ 앱
class Err(Exception):
    def __init__(self, status, message="오류"):
        Exception.__init__(self, message)
        self.status, self.message = status, message


def hide_row(wid=501, num=94):
    return {"id": wid, "state": "grass", "src": "hide", "peek": {"num": num, "form": None},
            "expiresIn": 240, "expiresAt": None}


def revealed(wid=501, hidden=True):
    mon = {"id": 0, "num": 94, "shiny": False, "hiddenAbility": hidden,
           "info": {"name": "팬텀", "species": "팬텀", "level": 20, "types": ["고스트", "독"], "hiddenAbility": hidden}}
    return {"wild": {"id": wid, "state": "revealed", "src": "hide", "pokemon": mon, "expiresIn": 60, "expiresAt": None},
            "ballOptions": [{"id": "POKEBALL", "kr": "몬스터볼", "count": 5, "rate": 1.0}]}


class FakeApi(object):
    def __init__(self):
        self.calls = []
        self.wild_r = {"wild": None, "nextInSeconds": 300, "balls": 5}
        self.reveal_r = revealed()

    def wild(self, force=False, hide=False):
        self.calls.append(("wild", bool(hide)))
        return self.wild_r

    def wild_reveal(self, wid):
        self.calls.append(("reveal", wid))
        time.sleep(0.05)
        return dict(self.reveal_r)

    def wild_flee(self, wid):
        self.calls.append(("flee", wid))
        self.wild_r = {"wild": None, "nextInSeconds": 10, "balls": 5}       # 서버: 못 찾고 만료 -> 다음 풀숲은 10초 뒤
        return {}

    def n(self, name):
        return sum(1 for c in self.calls if c[0] == name)


class FakeVisit(object):
    guest = False
    active = False


class FakeFocus(object):
    on = False

    def active(self):
        return self.on


class FakeFishing(object):
    open = True            # 시즌 7 이 열렸다 (숨바꼭질 설정 줄이 보이는 때)

    def rect(self):
        return None

    def resume(self):
        pass

    def pause(self):
        pass

    def nudge(self):
        pass


class MiniApp(object):
    def __init__(self, root, ov):
        self.root, self.overlay = root, ov
        self.settings = ov.settings
        self.api = FakeApi()
        self.balls = 5
        self.battle = self.arena = None
        self.visit = FakeVisit()
        self.focus = FakeFocus()
        self.olympics = None
        self.airraid = None
        self.fishing = FakeFishing()
        self.garden = None
        self.settings_win = None
        self.box_window = None
        self.tray = None
        self.notes = []
        self.floats = []
        self.trays = 0
        self.wild = wild_ui.WildController(self)

    def notify(self, m):
        self.notes.append(m)

    def refresh_tray(self):
        self.trays += 1

    def request_sync(self):
        pass

    def on_session_lost(self):
        pass

    def float_at(self, sx, sy, text, color="#7bffa0", ms=1100):
        self.floats.append((sx, sy, text, color))
        return True

    def said(self, text):
        return any(text in f[2] for f in self.floats)

    boss_key_error = ""

    def stealth_on(self):
        return False

    def boss_key(self):
        return ""

    def apply_boss_key(self, combo=None):
        return True, ""

    def set_size(self, px):
        pass

    set_show_grass = App.set_show_grass
    toggle_grass = App.toggle_grass
    set_hide_seek = App.set_hide_seek
    toggle_hide_seek = App.toggle_hide_seek
    _right_click_at = App._right_click_at
    _pets = App._pets
    _hit = staticmethod(App._hit)


class Rec(object):
    """겹침 순서 · 창 목록 · 전체 화면 함수를 바꿔 끼우고 부른 것을 적는다."""

    def __init__(self):
        self.calls = []
        self.windows = []
        self.busy = False
        self.ok = {"window": True, "bar": True, "edge": True}
        self.saved = {}
        self.screens = (list(SCREENS), list(WORKS))
        self.strips = []           # 창 뒤 자리에 넘긴 (창 번호, 보일 띠)
        self.mismatch = False      # 활동 영역 모니터의 DPI 가 시스템 DPI 와 다르다 (윈도우)

    def install(self):
        for n in ("order_just_below", "order_below_bar", "order_above_desktop", "other_windows", "fullscreen_busy",
                  "monitor_dpi_mismatch"):
            self.saved[n] = getattr(PM, n, None)
        self.saved["screens"] = PLAT.screens
        self.saved["screen_works"] = PLAT.screen_works
        PM.order_just_below = lambda win, other, strip=None: (self.strips.append((other, strip)),
                                                              self._order("window", win, other))[1]
        PM.monitor_dpi_mismatch = lambda rect: self.mismatch
        PM.order_below_bar = lambda win: self._order("bar", win)
        PM.order_above_desktop = lambda win: self._order("edge", win)
        PM.other_windows = lambda: [dict(w) for w in self.windows]
        PM.fullscreen_busy = lambda: self.busy
        PLAT.screens = lambda sw, sh: list(self.screens[0])
        PLAT.screen_works = lambda sw, sh: list(self.screens[1])

    def uninstall(self):
        for n, fn in self.saved.items():
            if n in ("screens", "screen_works"):
                setattr(PLAT, n, fn)
            elif fn is None:
                if hasattr(PM, n):
                    delattr(PM, n)
            else:
                setattr(PM, n, fn)

    def _order(self, kind, win, other=None):
        self.calls.append((kind, str(win), other))
        if not self.ok.get(kind):
            return False
        try:
            win.attributes("-topmost", False)          # 진짜 함수처럼 '항상 위' 를 푼다
        except tk.TclError:
            pass
        return True

    def n(self, kind=None):
        return sum(1 for c in self.calls if kind is None or c[0] == kind)


def wait_hider(root, ctl, sec=3.0):
    return pump(root, lambda: ctl.grass is not None, sec)


def show_hide(root, app, rec, windows=None, kinds=None, wid=501):
    """서버가 숨은 포켓몬을 준 것처럼 apply 하고 창이 뜰 때까지 기다린다."""
    ctl = app.wild
    ctl.clear()
    rec.windows = list(windows or [])
    real = HD.kinds
    if kinds is not None:
        HD.kinds = lambda: tuple(kinds)
    try:
        app.api.wild_r = {"wild": hide_row(wid), "nextInSeconds": None, "balls": 5}
        ctl.apply(app.api.wild_r)
        wait_hider(root, ctl)
    finally:
        HD.kinds = real
    settle(root, 0.1)
    return ctl.grass


def send_part(root, ov, app, rec):
    print("=== 2. hide=1 을 보낼 때 / 안 보낼 때 ===")
    ctl = app.wild
    s = app.settings
    chk("기본값: hideSeek 아직 안 정함(None) · hideHints 0", config.DEFAULTS.get("hideSeek", "x") is None
        and config.DEFAULTS.get("hideHints") == 0)
    chk("첫 값: 풀숲 보이기 · 이벤트 연출이 둘 다 켜져 있을 때만 켜짐",
        config.hide_pref({"hideSeek": None, "showGrass": True, "eventPopups": True}) is True
        and config.hide_pref({"hideSeek": None, "showGrass": True, "eventPopups": False}) is False
        and config.hide_pref({"hideSeek": None, "showGrass": False, "eventPopups": True}) is False
        and config.hide_pref({"hideSeek": True, "showGrass": False}) is True)
    chk("풀숲을 끄면 같이 꺼진다 (hide_seek)", config.hide_seek({"hideSeek": True, "showGrass": False}) is False
        and config.hide_seek({"hideSeek": True, "showGrass": True}) is True)
    s["hideSeek"] = None
    s["eventPopups"] = False
    ctl.start()
    chk("처음 켤 때 그때 값으로 굳힌다 (이벤트 연출 끔 -> 꺼짐) · 저장", s.get("hideSeek") is False
        and config.load_settings().get("hideSeek") is False, s.get("hideSeek"))
    s["eventPopups"] = True
    s["hideSeek"] = True
    ctl.stop_polling()

    def asked(fn):
        app.api.calls = []
        fn()
        pump(root, lambda: app.api.n("wild") > 0, 2.0)
        settle(root, 0.2)                    # 답(apply)까지 받고 넘어간다 - 늦게 온 답이 다음 검사의 야생을 치우지 않게
        got = [c for c in app.api.calls if c[0] == "wild"]
        return got[-1][1] if got else None
    chk("켜져 있으면 GET /api/wild?hide=1", asked(lambda: ctl.check()) is True)
    s["hideSeek"] = False
    chk("설정을 끄면 hide 없이", asked(lambda: ctl.check()) is False)
    s["hideSeek"] = True
    app.visit.guest = True
    chk("놀러 가 있으면 보내지 않는다 (can_hide 거짓)", not ctl.can_hide())
    app.visit.guest = False
    app.focus.on = True
    chk("집중하는 중이면 보내지 않는다", not ctl.can_hide())
    app.focus.on = False
    st = stealth.Stealth(app)
    st.on = True
    stealth._ACTIVE[0] = st
    try:
        chk("긴급 숨기기 중이면 보내지 않는다", not ctl.can_hide())
    finally:
        st.on = False
        stealth._ACTIVE[0] = None
    rec.busy = True
    chk("전체 화면 · 발표 중이면 보내지 않는다 (윈도우 fullscreen_busy)", asked(lambda: ctl.check()) is False)
    rec.busy = False
    real = HD.kinds
    HD.kinds = lambda: ()
    try:
        chk("이 OS 가 숨길 수 없으면 보내지 않는다", not ctl.can_hide())
    finally:
        HD.kinds = real
    chk("다 괜찮으면 보낸다", ctl.can_hide())
    ctl.stop_polling()


def hider_part(root, ov, app, rec):
    print("=== 3. src hide -> 도트를 받고 Hider ===")
    ctl = app.wild
    fetched = []
    real_ensure, real_walk = sprite_cache.ensure, walk_cache.ensure
    path = dot_path()
    sprite_cache.ensure = lambda api, num, shiny=False, back=False: (fetched.append(("sprite", num, shiny)), path)[1]
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (fetched.append(("walk", num, shiny)), (None, None))[1]
    try:
        armed = []
        real_arm = ctl.arm_expiry
        ctl.arm_expiry = lambda at, left=None: (armed.append(left), real_arm(at, left))
        try:
            g = show_hide(root, app, rec)
        finally:
            ctl.arm_expiry = real_arm
        chk("peek 의 종 도트를 보통 색으로 받는다 (걷는 도트 · 배틀 도트)", ("sprite", 94, False) in fetched
            and ("walk", 94, False) in fetched, fetched)
        chk("Hider 가 grass 칸에 들어간다", getattr(g, "is_hider", False) and ctl.src == "hide", type(g))
        chk("  풀숲처럼 생겼다 (x · y · fw · fh · view · center · destroy)", all(hasattr(g, a) for a in
                                                                          ("x", "y", "fw", "fh", "view", "center", "destroy")))
        chk("  만료 240초 (expiresIn)", 240 in armed, armed)
        chk("  겹침 순서 함수를 불렀다 (그 자리 종류)", rec.n(g.spot["kind"]) >= 1, rec.calls)
        chk("  항상 위가 아니다", top(g.win) == 0)
        chk("  _poket_hider 표시", getattr(g.win, "_poket_hider", False) is True)
        chk("  서버에 알리는 글을 남기지 않는다 (풀숲처럼 '흔들리고 있습니다' 없음)",
            not any("풀숲이 흔들리고" in m for m in app.notes), app.notes[-3:])
        size0 = (g.win.winfo_width(), g.win.winfo_height())
        pump(root, lambda: g.p >= g.spot["peek"], 2.0)
        chk("0.6초 스르륵 나와 그 자리에 (보이는 몸 = 고른 값)", g.p == g.spot["peek"], (g.p, g.spot["peek"]))

        print("=== 4. 항상 위가 아니다 ===")
        tops = []
        real_keep = PLAT.keep_on_top
        PLAT.keep_on_top = lambda w: (tops.append(str(w)), real_keep(w))
        try:
            g.win.attributes("-topmost", True)        # 누가 '항상 위' 를 걸었다 (윈도우 작업표시줄 뒤는 정말로 topmost 다)
            ov.keep_on_top()
            settle(root, 0.05)
        finally:
            PLAT.keep_on_top = real_keep
        chk("keep_on_top 이 이 창은 올리지 않는다", str(g.win) not in tops, tops[:3])
        g.win.attributes("-topmost", False)
        n0 = rec.n()
        g.win.withdraw()
        settle(root, 0.05)
        PLAT.show_again(g.win)
        settle(root, 0.1)
        chk("PLAT.show_again 뒤에도 항상 위가 아니고, 겹침 순서를 다시 건다", top(g.win) == 0 and rec.n() > n0
            and g.win.winfo_ismapped(), (top(g.win), rec.n() - n0))
        n0 = rec.n()
        g.follow()
        chk("1초마다 겹침 순서를 다시 건다", rec.n() > n0)
        st = stealth.Stealth(app)
        st.hide()
        try:
            n0 = rec.n()
            g.follow()
            g.reorder()
            chk("긴급 숨기기 동안은 겹침 순서를 안 건다 (맥은 숨긴 창이 도로 뜬다)", rec.n() == n0 and not g.win.winfo_ismapped())
        finally:
            st.show()
        settle(root, 0.1)
        chk("  되돌리면 다시 보이고 항상 위가 아니다", g.win.winfo_ismapped() and top(g.win) == 0)

        print("=== 6. 꼼지락 · 내밀기 - 창 크기는 그대로 ===")
        base = g.spot["peek"]
        L = g.length()
        wig = g._wiggles[0]
        chk("30초까지는 가만", all(g.want(t) == base for t in (1.0, 10.0, 29.9)))
        chk("30~180초: 10~14초 간격 꼼지락 (+3px, 0.4초)", 40.0 <= wig <= 44.0 and g.want(wig + 0.1) == min(L, base + 3)
            and g.want(wig + 0.5) == base and all(10.0 <= b - a <= 14.0 for a, b in zip(g._wiggles, g._wiggles[1:])
                                                  if b < 180), g._wiggles[:4])
        chk("180~240초: 6초마다", [t for t in g._wiggles if t >= 180][:3] == [180.0, 186.0, 192.0])
        chk("200초쯤 한 번 70% 까지 내민다 (1.5초)", g.want(200.5) == SP.more_px(L, base) and g.want(201.6) != g.want(200.5))
        chk("스르륵: 0.3초면 절반쯤", 0 < g.want(0.3) < base)
        sizes = set()
        for p in (0, base, base + 3, SP.more_px(L, base), 1, base):
            g._apply(p)
            settle(root, 0.02)
            sizes.add((g.win.winfo_width(), g.win.winfo_height(), g.view.w, g.view.h))
        chk("보이는 몸이 바뀌어도 창 크기는 하나 (윈도우 검은 번쩍임 없음)", len(sizes) == 1 and size0 == sizes.copy().pop()[:2],
            (sizes, size0))
        sx = []
        for p in (base, SP.more_px(L, base)):
            g._apply(p)
            sx.append(SP.shown_rect(g.spot["side"], g.spot["line"], g.spot["along"], g.bw, g.bh, p))
        chk("  더 내밀어도 가리는 경계는 그대로 (보이는 칸이 경계에서 자란다)",
            (sx[0][3] == sx[1][3]) if g.spot["side"] == "top" else True, sx)
        g._apply(base)
        if PLAT.NEEDS_HIT_TRACKING and getattr(g.view, "layer", None) is not None:
            g._apply(0)                       # 숨긴 채 (창이 움직이는 중) - 앞서 그린 몸 자리도 클릭을 안 먹어야 한다
            g.view.update_hit(g.bw // 2, g.bh // 2)
            chk("맥: 지금 안 그린 몸 자리는 클릭을 밑으로 넘긴다 (장을 합친 판정이 아니다)", g.view._ignoring is True)
            g._apply(base)
            x, y = g.x - g.wx + g.fw // 2, g.y - g.wy + g.fh // 2
            g.view.update_hit(x, y)
            chk("  보이는 몸은 클릭을 받는다", g.view._ignoring is False)
    finally:
        sprite_cache.ensure, walk_cache.ensure = real_ensure, real_walk

    print("=== 3b. 못 받으면 · 숨을 자리가 없으면 풀숲 ===")
    sprite_cache.ensure = lambda api, num, shiny=False, back=False: None
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (None, None)
    try:
        g = show_hide(root, app, rec, wid=502)
        chk("도트를 못 받으면 그 자리에 풀숲 (GrassPatch)", isinstance(g, wild_ui.GrassPatch), type(g))
    finally:
        sprite_cache.ensure, walk_cache.ensure = real_ensure, real_walk
    sprite_cache.ensure = lambda api, num, shiny=False, back=False: path
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (None, None)
    try:
        rec.screens = ([(0, 0, 1600, 1000)], [(0, 0, 1600, 1000)])        # 작업표시줄 없음
        g = show_hide(root, app, rec, windows=[{"rect": (0, 0, 1600, 1000), "id": 1, "max": True}], wid=503)
        chk("숨을 자리가 없으면 (최대화 창 · 작업표시줄 없음) 풀숲", isinstance(g, wild_ui.GrassPatch), type(g))
        rec.screens = (list(SCREENS), list(WORKS))
        rec.ok = {"window": False, "bar": False, "edge": True}
        n0 = rec.n()
        g = show_hide(root, app, rec, windows=[{"rect": (200, 200, 900, 700), "id": 11}], wid=504)
        chk("겹침 순서를 못 거는 종류는 빼고 다른 자리로 (항상 위로 띄우지 않는다)",
            getattr(g, "is_hider", False) and g.spot["kind"] == "edge" and top(g.win) == 0, (type(g), rec.calls[n0:]))
        rec.ok = {"window": False, "bar": False, "edge": False}
        g = show_hide(root, app, rec, wid=505)
        chk("어느 종류도 못 걸면 풀숲 (항상 위 숨은 포켓몬은 없다)", isinstance(g, wild_ui.GrassPatch), type(g))
        rec.ok = {"window": True, "bar": True, "edge": True}
        app.settings["hideSeek"] = False
        g = show_hide(root, app, rec, wid=506)
        chk("숨바꼭질을 끈 사람에게 온 숨은 포켓몬은 풀숲으로", isinstance(g, wild_ui.GrassPatch), type(g))
        app.settings["hideSeek"] = True
        g = show_hide(root, app, rec, wid=507)
        app.set_hide_seek(False)
        settle(root, 0.1)
        chk("떠 있는 동안 끄면 그 자리에 풀숲으로 바뀐다 · 저장 · 트레이", isinstance(ctl.grass, wild_ui.GrassPatch)
            and not g.win.winfo_exists() and config.load_settings()["hideSeek"] is False)
        app.set_hide_seek(True)
        # 긴급 숨기기 중에 온 숨은 포켓몬은 풀숲이 되지 않고, 풀린 뒤에 숨는다 (실제 앱 시험 11/27)
        ctl.clear()
        st = stealth.Stealth(app)
        st.on = True
        stealth._ACTIVE[0] = st
        try:
            app.api.wild_r = {"wild": hide_row(508), "nextInSeconds": None, "balls": 5}
            ctl.apply(app.api.wild_r)
            settle(root, 1.5)
            chk("긴급 숨기기 중엔 풀숲으로 바꾸지 않고 기다린다", ctl.grass is None and ctl._peeking == 508,
                (type(ctl.grass), ctl._peeking))
        finally:
            st.on = False
            stealth._ACTIVE[0] = None
        wait_hider(root, ctl)
        chk("  풀리면 숨은 포켓몬으로 뜬다", getattr(ctl.grass, "is_hider", False), type(ctl.grass))
    finally:
        sprite_cache.ensure, walk_cache.ensure = real_ensure, real_walk
    ctl.clear()


def click_part(root, ov, app, rec):
    print("=== 5. 찾기 ===")
    ctl = app.wild
    path = dot_path()
    real_ensure, real_walk = sprite_cache.ensure, walk_cache.ensure
    sprite_cache.ensure = lambda api, num, shiny=False, back=False: path
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (None, None)
    ov.paths[(94, False)] = path
    try:
        app.settings["hideHints"] = 0
        g = show_hide(root, app, rec, wid=601)
        app.api.calls = []
        app.api.reveal_r = revealed(601, hidden=True)
        floats0 = len(app.floats)
        g.label.event_generate("<Button-1>", x=3, y=3)
        g.label.event_generate("<Button-1>", x=3, y=3)
        settle(root, 0.02)
        pump(root, lambda: app.api.n("reveal") > 0, 2.0)
        say = getattr(ctl, "_say", None)
        chk("누르면 reveal 한 번 (연타해도)", app.api.n("reveal") == 1, app.api.calls)
        ok = pump(root, lambda: ctl.pet is not None, 3.0)
        chk("'찾았다!' 가 숨은 자리에 뜬다", say is not None or getattr(ctl, "_say", None) is not None)
        sw = say or getattr(ctl, "_say", None)
        chk("  글이 맞다", sw is not None and sw.text == HD.SAY_FOUND, getattr(sw, "text", None))
        chk("뛰어 들어와 야생 포켓몬이 된다 (WildPet)", ok and isinstance(ctl.pet, wild_ui.WildPet) and ctl.grass is None)
        p = ctl.pet
        x1, y1, x2, y2 = AREA
        chk("  활동 영역 안", p is not None and x1 <= p.x and p.x + p.fw <= x2 and y1 <= p.y and p.y + p.fh <= y2,
            p and (p.x, p.y))
        gr = (g.wx, g.wy, g.wx + g.bw, g.wy + g.bh)
        fx, fy = HD.edge_point(AREA, app.settings["areaMargin"], gr, p.fw, p.fh)
        chk("  숨은 자리에서 가장 가까운 영역 가장자리에", p is not None and abs((p.x + p.fw / 2.0) - fx) <= p.fw
            and abs((p.y + p.fh) - fy) <= p.fh, ((p.x, p.y), (fx, fy)))
        pump(root, lambda: app.said(HD.SAY_HIDDEN), 2.0)
        chk("숨겨진 특성이면 '숨겨진 특성!'", app.said(HD.SAY_HIDDEN), app.floats[floats0:])
        lead = next(iter(ov.pets.values()))
        pump(root, lambda: HD.HINT_FOUND in bubbles(lead), 2.0)
        texts = bubbles(lead)
        chk("처음 찾으면 안내 '숨바꼭질! …'", HD.HINT_FOUND in texts and int(app.settings["hideHints"]) & HD.HINT_BIT_FOUND,
            texts)
        chk("  띄운 숨은 창 · 뛰는 창이 남지 않는다", not g.win.winfo_exists() and g._leap is None)
        ctl.clear()
        settle(root, 0.05)
        g = show_hide(root, app, rec, wid=602)
        app.api.reveal_r = revealed(602, hidden=False)
        floats0 = len(app.floats)
        g.label.event_generate("<Button-1>", x=3, y=3)
        pump(root, lambda: ctl.pet is not None, 3.0)
        settle(root, 0.9)
        chk("숨겨진 특성이 아니면 그 글은 없다", not any(HD.SAY_HIDDEN in f[2] for f in app.floats[floats0:]))
        ctl.clear()
        g = show_hide(root, app, rec, wid=603)
        g.label.event_generate("<Button-1>", x=3, y=3)
        pump(root, lambda: getattr(g, "_leap", None) is not None or not g.win.winfo_exists(), 2.0)
        ctl.clear()
        settle(root, 0.6)
        chk("뛰는 도중 치우면 (집중 · 놀러 가기) 야생이 안 선다", ctl.pet is None and g._leap is None)
    finally:
        sprite_cache.ensure, walk_cache.ensure = real_ensure, real_walk


def follow_part(root, ov, app, rec):
    print("=== 6. 창 뒤 자리 따라가기 ===")
    ctl = app.wild
    path = dot_path()
    real_ensure, real_walk = sprite_cache.ensure, walk_cache.ensure
    sprite_cache.ensure = lambda api, num, shiny=False, back=False: path
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (None, None)
    try:
        win = {"rect": (200, 200, 900, 700), "id": 11}
        g = show_hide(root, app, rec, windows=[win], kinds=("window",), wid=701)
        chk("창 뒤 자리 (그 창 번호로 겹침 순서)", getattr(g, "is_hider", False) and g.spot["kind"] == "window"
            and ("window", str(g.win), 11) in rec.calls, rec.calls[-2:])
        pump(root, lambda: g.p == g.spot["peek"], 2.0)
        old = dict(g.spot)
        rec.windows = [{"rect": (300, 250, 1000, 750), "id": 11}]
        g.follow()
        chk("창이 움직이면 숨는다 (보이는 몸 0)", g.moving and g.p == 0, (g.moving, g.p))
        g.follow()
        pump(root, lambda: g.p > 0, 2.0)
        chk("멈추면 같은 자리(창 기준)로 따라가 다시 보인다 (스르륵)", not g.moving and g.p > 0
            and g.spot["along"] - old["along"] == (100 if old["side"] == "top" else 50)
            and g.spot["arect"] == (300, 250, 1000, 750), (old["along"], g.spot["along"], g.p))
        n0 = rec.n("window")
        g.follow()
        chk("  그대로면 그 창 바로 뒤로 다시 건다", rec.n("window") > n0)
        rec.windows = []
        g.follow()
        chk("창이 사라지면(닫힘 · 내림) 다른 자리 (작업표시줄 · 가장자리)", g.spot["kind"] in ("bar", "edge") and not g.lost
            and g.p == 0, g.spot["kind"])
        pump(root, lambda: g.p == g.spot["peek"], 2.0)
        chk("  거기서 다시 보인다", g.p == g.spot["peek"])
        rec.screens = ([(0, 0, 1600, 1000)], [(0, 0, 1600, 1000)])
        rec.windows = [{"rect": (0, 0, 1600, 1000), "id": 1}]
        g.repick()
        chk("숨을 데가 없으면 숨긴 채 (항상 위로 안 띄움)", g.lost and g.p == 0 and top(g.win) == 0)
        rec.screens = (list(SCREENS), list(WORKS))
        rec.windows = []
        g.follow()
        chk("  자리가 생기면 다시 숨는다", not g.lost and g.spot is not None)
        for _ in range(200):
            if g.spot["kind"] == "bar":
                break
            g.repick()
        rec.screens = (list(SCREENS), [(60, 0, 1600, 1000)])          # 작업표시줄을 왼쪽으로 옮겼다
        g.follow()
        chk("작업표시줄을 옮기면 다른 자리로 (옛 자리에 떠 있지 않는다)", g.spot["kind"] != "bar" or g.spot["edge"] == "left",
            (g.spot["kind"], g.spot["edge"]))
        rec.screens = (list(SCREENS), list(WORKS))
    finally:
        sprite_cache.ensure, walk_cache.ensure = real_ensure, real_walk
    ctl.clear()


def dpi_part(root, ov, app, rec):
    print("=== 6c. 배율이 다른 모니터 · 걸고 나서 가려졌나 (검토 #3 · #5 · #7) ===")
    ctl = app.wild
    path = dot_path()
    real_ensure, real_walk = sprite_cache.ensure, walk_cache.ensure
    sprite_cache.ensure = lambda api, num, shiny=False, back=False: path
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (None, None)
    wins = [{"rect": (200, 200, 900, 700), "id": 11}]
    try:
        rec.mismatch = True
        g = show_hide(root, app, rec, windows=wins, kinds=("window", "edge"), wid=601)
        chk("활동 영역 모니터의 DPI 가 시스템 DPI 와 다르면 창 뒤 · 가장자리 자리는 안 쓴다 (좌표가 어긋난다)",
            isinstance(g, wild_ui.GrassPatch), type(g))
        n0 = len(rec.calls)
        seen = []
        for k in range(5):
            g = show_hide(root, app, rec, windows=wins, wid=602 + k)
            seen.append(g.spot["kind"] if getattr(g, "is_hider", False) else type(g).__name__)
        chk("  작업표시줄 자리만 쓴다 (겹침 순서도 작업표시줄만)", set(seen) == {"bar"}
            and all(c[0] == "bar" for c in rec.calls[n0:]), (seen, rec.calls[n0:n0 + 4]))
        rec.mismatch = False
        g = show_hide(root, app, rec, windows=wins, kinds=("edge",), wid=610)
        was = g.spot["kind"] if getattr(g, "is_hider", False) else type(g).__name__
        rec.mismatch = True                   # 켜 둔 사이 그 모니터의 배율이 바뀌었다
        g.follow()
        chk("  가장자리에 숨은 동안 그 모니터 배율이 달라지면 작업표시줄 자리로 옮긴다", was == "edge"
            and g.spot["kind"] == "bar", (was, g.spot and g.spot["kind"]))
        rec.mismatch = False
        rec.strips = []
        g = show_hide(root, app, rec, windows=wins, kinds=("window",), wid=611)
        sp = g.spot if getattr(g, "is_hider", False) else None
        want = sp and (11, SP.shown_rect(sp["side"], sp["line"], sp["along"], g.bw, g.bh, sp["peek"]))
        got1 = rec.strips[-1] if rec.strips else None
        g.reorder()
        got2 = rec.strips[-1] if rec.strips else None
        chk("창 뒤 자리는 보일 띠를 겹침 함수에 넘긴다 (맥이 걸고 나서 가려졌나 본다) - 만들 때 · 다시 걸 때",
            sp is not None and got1 == want and got2 == want, (got1, got2, want))
    finally:
        rec.mismatch = False
        sprite_cache.ensure, walk_cache.ensure = real_ensure, real_walk
    ctl.clear()


def expire_part(root, ov, app, rec):
    print("=== 7. 4분 만료 · 안내 ===")
    ctl = app.wild
    path = dot_path()
    real_ensure, real_walk = sprite_cache.ensure, walk_cache.ensure
    sprite_cache.ensure = lambda api, num, shiny=False, back=False: path
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (None, None)
    lead = next(iter(ov.pets.values()))
    try:
        for b in list(getattr(lead, "_bubbles", ())):
            b.close()
        app.settings["hideHints"] = 0
        ctl.HIDE_PEEK_MS, ctl.HIDE_Q_MS = 150, 250
        g = show_hide(root, app, rec, wid=801)
        lead.x = g.x + 400                       # 숨은 자리 오른쪽에 서 있다 - 왼쪽을 보며 말해야 한다
        lead.facing = 0
        pump(root, lambda: HD.HINT_PEEK in bubbles(lead), 2.0)
        texts = bubbles(lead)
        chk("처음 나오면 (60초 뒤) 선두 포켓몬이 '어디선가 누가 훔쳐보고 있어…'", HD.HINT_PEEK in texts, texts)
        chk("  그쪽을 본다", lead.facing == OV.LEFT, lead.facing)
        chk("  한 번만 (hideHints)", int(app.settings["hideHints"]) & HD.HINT_BIT_PEEK)
        app.api.calls = []
        ctl.on_expired()
        settle(root, 0.1)
        chk("못 찾고 만료되면 사라지고 flee (서버가 다음 풀숲을 당긴다)", ctl.grass is None and not g.win.winfo_exists()
            and pump(root, lambda: app.api.n("flee") == 1, 2.0), app.api.calls)
        pump(root, lambda: HD.HINT_MISS in bubbles(lead), 2.0)
        texts = bubbles(lead)
        chk("처음 놓치면 '아까 저쪽에 누가 숨어 있었는데…'", HD.HINT_MISS in texts and int(app.settings["hideHints"])
            & HD.HINT_BIT_MISS, texts)
        for b in list(getattr(lead, "_bubbles", ())):
            b.close()
        app.settings["eventPopups"] = True
        g = show_hide(root, app, rec, wid=802)
        pump(root, lambda: HD.HINT_Q in bubbles(lead), 2.0)
        texts = bubbles(lead)
        chk("그 뒤로는 2분이면 선두 포켓몬 '?' (처음 안내는 다시 안 함)", HD.HINT_Q in texts and HD.HINT_PEEK not in texts,
            texts)
        ctl.clear()
        for b in list(getattr(lead, "_bubbles", ())):
            b.close()
        app.settings["eventPopups"] = False
        g = show_hide(root, app, rec, wid=803)
        settle(root, 0.5)
        chk("이벤트 연출을 끈 사람은 '?' 없음", not bubbles(lead))
        ctl.on_expired()
        settle(root, 0.3)
        chk("두 번째로 놓치면 안내 없음", not bubbles(lead))
        app.settings["eventPopups"] = True
        ctl.HIDE_PEEK_MS, ctl.HIDE_Q_MS = 60000, 120000
        chk("안내 때 (진짜): 60초 · 2분", wild_ui.WildController.HIDE_PEEK_MS == 60000
            and wild_ui.WildController.HIDE_Q_MS == 120000)

        print("=== 7b. 맥 오른클릭 · 치우기 ===")
        g = show_hide(root, app, rec, wid=804)
        app.api.calls = []
        app._right_click_at(g.x + 2, g.y + 2, getattr(g.view, "win_number", None))
        settle(root, 0.2)
        chk("오른클릭은 숨은 포켓몬을 찾지 않는다 (왼클릭만)", app.api.n("reveal") == 0)
        ctl.stop()
        settle(root, 0.05)
        chk("stop() (집중 · 놀러 가기 · 공습 · 올림픽) 이 숨은 포켓몬을 치운다", ctl.grass is None and not g.win.winfo_exists())
    finally:
        sprite_cache.ensure, walk_cache.ensure = real_ensure, real_walk


def settings_part(root, ov, app, rec):
    print("=== 8. 설정 · 트레이 ===")
    from poketdesktop import tray as TR
    from poketdesktop import ui_settings as ST
    from poketdesktop.skins.dp import settings as DPS
    tray = type("T", (), {"call": lambda self, fn, *a: fn(*a)})()
    app.settings["showGrass"] = True
    app.settings["hideSeek"] = True
    app.fishing.open = False
    ctl = app.wild
    ctl._hide_seen = False
    chk("시즌 7 이 안 열렸으면 (낚시 · 텃밭이 닫힘 · 본 적 없음) 줄이 없다", TR.hide_items(tray, app) == [])
    sw = ST.SettingsWindow(app)
    settle(root)
    labels = [w.cget("text") for w in walk(sw.win) if isinstance(w, tk.Checkbutton)]
    chk("  설정 창에도 없다", ST.SettingsWindow.HIDE_LABEL not in labels, labels)
    sw.close()
    app.fishing.open = True
    items = TR.hide_items(tray, app)
    chk("트레이: '숨바꼭질' (켜짐 표시)", len(items) == 1 and items[0].text == "숨바꼭질" and items[0].checked() is True)
    sub = TR.with_garden(tray, app, ["a", "b"])
    chk("  '바탕화면' 하위 메뉴 끝 (낚시터 · 텃밭 다음)", sub[:2] == ["a", "b"] and sub[-1].text == "숨바꼭질", sub)
    sw = ST.SettingsWindow(app)
    app.settings_win = sw
    settle(root)
    labels = [w.cget("text") for w in walk(sw.win) if isinstance(w, tk.Checkbutton)]
    chk("설정(기본): '숨바꼭질' 줄이 풀숲 · 낚시터 · 텃밭 다음", "숨바꼭질" in labels
        and labels.index("숨바꼭질") > labels.index("풀숲 띄우기"), labels)
    chk("  설명은 소리 · 알림 없이, 풀숲을 따른다고", "풀숲" in ST.SettingsWindow.HIDE_NOTE)
    chk("  풀숲이 켜져 있으면 누를 수 있다", str(sw.hide_check.cget("state")) == "normal")
    items[0].action()
    settle(root)
    chk("트레이에서 끄면 저장 · 설정 창 표시도 맞춘다", config.load_settings()["hideSeek"] is False
        and sw.hide.get() is False)
    sw.hide.set(True)
    sw._toggle_hide("hideSeek", sw.hide)
    settle(root)
    chk("설정 창에서 켠다", config.load_settings()["hideSeek"] is True and app.settings["hideSeek"] is True)
    sw.grass.set(False)
    sw._toggle_grass("showGrass", sw.grass)
    settle(root)
    chk("풀숲을 끄면 하위 칸이 죽는다 (누를 수 없음)", str(sw.hide_check.cget("state")) == "disabled"
        and not config.hide_seek(app.settings))
    chk("  트레이 줄도 죽는다", TR.hide_items(tray, app)[0].enabled() is False)
    sw.grass.set(True)
    sw._toggle_grass("showGrass", sw.grass)
    settle(root)
    chk("  풀숲을 다시 켜면 살아난다 (고른 값 그대로)", str(sw.hide_check.cget("state")) == "normal"
        and config.hide_seek(app.settings) is True)
    sw.close()
    app.settings_win = None
    dw = DPS.SettingsWindow(app)
    settle(root)
    names = [r["label"] for r in dw.rows]
    chk("설정(DP): '숨바꼭질' 줄", "숨바꼭질" in names and names.index("숨바꼭질") > names.index("풀숲 띄우기"), names)
    row = dw.rows[names.index("숨바꼭질")]
    row["put"](False)
    settle(root)
    chk("  DP 에서 끄기", app.settings["hideSeek"] is False and row["get"]() is False)
    row["put"](True)
    app.settings["showGrass"] = False
    dis = row.get("disabled")
    chk("  풀숲을 끄면 DP 줄도 죽는다", (dis() if callable(dis) else dis) is True)
    before = app.settings["hideSeek"]
    dw._step(row, 1)
    chk("  죽은 줄은 ◀ ▶ 로 안 바뀐다", app.settings["hideSeek"] == before)
    app.settings["showGrass"] = True
    dw.close()
    settle(root)
    chk("기본값으로 되돌리기에도 안내 단계(hideHints)는 남긴다",
        '"gardenHints", "hideHints"' in open(ST.__file__, encoding="utf-8").read())


class FakeWin32(object):
    """윈도 API 가짜 (이 맥에서는 Win32 를 못 부른다) - platform_win._HIDE · _DPI 자리에 끼운다 (user32 · dwmapi ·
    shcore · gdi32 를 한 몸이 맡는다).

    wins [(hwnd, {pid, cls, style, exstyle, rect(GetWindowRect - 이 시스템 DPI 프로세스가 보는 논리 좌표),
    dwm(EXTENDED_FRAME_BOUNDS - 물리 픽셀), mon, wdpi(GetDpiForWindow - 그 앱의 DPI 인식)})] 앞에서부터.
    mons {모니터: (논리 x 시작, 실제 DPI)}. GetDpiForMonitor 는 **스레드가 '모니터마다' 일 때만** 실제 DPI 를 주고
    아니면 시스템 DPI 를 준다 (문서: 시스템 DPI 앱이 부르면 어느 모니터든 시스템 DPI)."""
    PER_MON = (-3, -4)

    def __init__(self, wins, mons, sys_dpi=144):
        self.wins, self.d, self.mons, self.sys = wins, dict(wins), mons, sys_dpi
        self.ctx = -2                               # DPI_AWARENESS_CONTEXT_SYSTEM_AWARE
        self.ctx_log = []

    def EnumWindows(self, cb, lp):
        for hwnd, _w in self.wins:
            if not cb(hwnd, lp):
                break
        return 1

    def IsWindowVisible(self, h):
        return int(self.d[h].get("visible", True))

    def IsIconic(self, h):
        return 0

    def IsZoomed(self, h):
        return int(self.d[h].get("zoomed", False))

    def GetWindowLongW(self, h, i):
        return self.d[h].get("style", 0x10000000) if i == -16 else self.d[h].get("exstyle", 0)

    def GetWindowThreadProcessId(self, h, ref):
        ref._obj.value = self.d[h]["pid"]
        return 1

    def GetClassNameW(self, h, buf, n):
        buf.value = self.d[h].get("cls", "Chrome_WidgetWin_1")
        return len(buf.value)

    def GetWindowRect(self, h, ref):
        r = ref._obj
        r.left, r.top, r.right, r.bottom = self.d[h]["rect"]
        return 1

    def GetDpiForWindow(self, h):
        return self.d[h].get("wdpi", self.sys)

    def GetDpiForSystem(self):
        return self.sys

    def MonitorFromWindow(self, h, flags):
        return self.d[h]["mon"]

    def MonitorFromPoint(self, pt, flags):
        best = None
        for m, (x0, _dpi) in sorted(self.mons.items(), key=lambda t: t[1][0]):
            if pt.x >= x0:
                best = m
        return best

    def SetThreadDpiAwarenessContext(self, ctx):
        old, self.ctx = self.ctx, int(ctx)
        self.ctx_log.append(int(ctx))
        return old

    def GetDC(self, h):
        return 1

    def ReleaseDC(self, h, dc):
        return 1

    def DwmGetWindowAttribute(self, h, attr, ref, size):
        if attr == 9:
            d = self.d[h].get("dwm")
            if d is None:
                return -1
            r = ref._obj
            r.left, r.top, r.right, r.bottom = d
        elif attr == 14:
            ref._obj.value = self.d[h].get("cloaked", 0)
        return 0

    def GetDpiForMonitor(self, m, kind, rx, ry):
        dpi = self.mons[m][1] if self.ctx in self.PER_MON else self.sys
        rx._obj.value = ry._obj.value = dpi
        return 0

    def GetDeviceCaps(self, dc, idx):
        return self.sys if idx == 88 else 0


def win_dpi_part(PW):
    """윈도 창 목록 · 모니터 DPI (검토 #3 · #4 · #7) - 가짜 Win32 로.

    노트북 150% (시스템 DPI 144, 논리 x 0~1920) + 바깥 모니터 100% (96 DPI, 논리 x 2880~). 우리는 '시스템 DPI' 앱이라
    GetWindowRect · 모니터 · Tk 좌표는 논리 좌표, DWM 테두리는 물리 픽셀이다."""
    print("=== 9a. 윈도 창 좌표 · 모니터 DPI · 이 앱의 창 (가짜 Win32) ===")
    me = os.getpid()
    wins = [
        (101, {"pid": me, "cls": "TkTopLevel", "rect": (1293, 60, 1607, 427), "dwm": (1300, 60, 1600, 420), "mon": 1}),
        (102, {"pid": me, "cls": "TkTopLevel", "exstyle": 0x80 | 0x8, "rect": (500, 500, 560, 560),
               "dwm": (500, 500, 560, 560), "mon": 1}),                       # 이 앱의 테두리 없는 창 (도트 · 숨은 포켓몬)
        (103, {"pid": 50, "exstyle": 0x8, "rect": (33, 300, 347, 607), "dwm": (40, 300, 340, 600), "mon": 1}),
        (104, {"pid": 51, "rect": (3050, 150, 4270, 1060), "dwm": (3000, 100, 3800, 700), "mon": 2,
               "wdpi": 144}),                                                 # 시스템 DPI 앱 창이 바깥 모니터에
        (105, {"pid": 52, "rect": (3500, 300, 4420, 910), "dwm": (3300, 200, 3900, 600), "mon": 2,
               "wdpi": 96}),                                                  # 모니터마다 DPI 앱 창이 바깥 모니터에
        (106, {"pid": 53, "rect": (93, 100, 1007, 711), "dwm": (100, 100, 1000, 704), "mon": 1,
               "wdpi": 96}),                                                  # DPI 모르는 앱 창이 노트북 화면에
        (108, {"pid": 54, "cls": "Progman", "rect": (0, 0, 1920, 1200), "dwm": (0, 0, 1920, 1200), "mon": 1}),
    ]
    fake = FakeWin32(wins, {1: (0, 144), 2: (2880, 96)}, sys_dpi=144)
    saved = (PW._HIDE, getattr(PW, "_DPI", None))
    PW._HIDE = (fake, fake, lambda fn: fn)
    PW._DPI = (fake, fake)
    try:
        got = PW.other_windows()
        mm = getattr(PW, "monitor_dpi_mismatch", None)
        mis = [mm(r) if mm else "없음" for r in ((900, 420, 1400, 820), (3200, 300, 3900, 900))]
        ctx_after = fake.ctx
    finally:
        PW._HIDE, PW._DPI = saved
    by = {w.get("id"): w for w in got}
    chk("창 목록 차례 그대로 · 이 앱의 테두리 있는 창도 든다 (도구 창 · 바탕화면은 빼고)",
        [w.get("id") for w in got] == [101, 103, 104, 105, 106], [w.get("id") for w in got])
    chk("  이 앱의 창은 own (가리는 창으로만 - 검토 #4) · 항상 위 창은 top", by.get(101, {}).get("own") is True
        and not by.get(103, {}).get("own") and by.get(103, {}).get("top") is True, (by.get(101), by.get(103)))
    chk("  시스템 DPI 모니터의 창: DWM 테두리로 안 보이는 크기 조절 테두리를 뺀다 · DPI 모르는 앱 창도 odd 아님",
        by.get(106, {}).get("rect") == (100, 100, 1000, 704) and by.get(106, {}).get("odd") is False
        and by.get(101, {}).get("rect") == (1300, 60, 1600, 420), (by.get(106), by.get(101)))
    chk("  배율이 다른 모니터의 창: 좌표는 논리(GetWindowRect) - 물리 DWM 칸을 쓰지 않는다 (검토 #3)",
        by.get(104, {}).get("rect") == (3050, 150, 4270, 1060) and by.get(105, {}).get("rect") == (3500, 300, 4420, 910),
        (by.get(104), by.get(105)))
    chk("  배율이 다른 모니터의 창은 그 앱의 DPI 인식과 상관없이 odd (모니터 DPI 로 - 검토 #7)",
        by.get(104, {}).get("odd") is True and by.get(105, {}).get("odd") is True, (by.get(104), by.get(105)))
    chk("monitor_dpi_mismatch: 활동 영역 모니터가 시스템 DPI 면 False, 배율이 다른 모니터면 True", mis == [False, True], mis)
    chk("  모니터 DPI 는 스레드를 잠깐 '모니터마다' 로 바꿔 묻고 되돌린다 (그냥 물으면 시스템 DPI 가 온다)",
        any(c in FakeWin32.PER_MON for c in fake.ctx_log) and ctx_after == -2, (fake.ctx_log, ctx_after))
    fr = getattr(PW, "_frame_rect", None)
    cases = [((979, 300, 2021, 1321), (1000, 300, 2000, 1300), 288),   # 300% 화면 - 안 보이는 테두리가 21px
             ((2885, 15, 3505, 475), (2890, 10, 3290, 310), 144)]      # 바깥 모니터 모서리 - DWM 칸이 안에 들어가도 크기가 다르다
    got = [fr(*c) if fr else None for c in cases]
    chk("  테두리 폭은 시스템 배율만큼 넓게 본다 · DWM 칸이 창 안에 들어가도 크기가 다르면 배율이 다른 것",
        got == [((1000, 300, 2000, 1300), False), ((2885, 15, 3505, 475), True)], got)


def platform_part(root):
    print("=== 9. 플랫폼 ===")
    from poketdesktop import platform_base as PB
    from poketdesktop import platform_win as PW
    chk("기본 구현: 숨길 수 없다 (자리 종류 없음 · 겹침 순서 실패 · 창 목록 없음)", PB.HIDE_KINDS == ()
        and PB.other_windows() == [] and PB.order_just_below(None, 1) is False and PB.fullscreen_busy() is False)
    chk("윈도우: 세 종류 다", PW.HIDE_KINDS == ("window", "bar", "edge"))
    base = dict(visible=True, iconic=False, style=0x10000000, exstyle=0, pid=99, me=1, cls="Chrome_WidgetWin_1",
                cloaked=0, rect=(100, 100, 900, 700), zoomed=False, mon_dpi=96, sys_dpi=96)

    def keep(**over):
        try:
            return PW._keep_window(**dict(base, **over))
        except Exception as e:                              # noqa: BLE001
            return "error: %s" % e
    got = keep()
    chk("윈도 창 거르기: 보통 창은 {rect, id, max, top, odd, own} (제목 없음)", isinstance(got, dict)
        and set(got) == {"rect", "max", "top", "odd", "own"} and got["rect"] == (100, 100, 900, 700)
        and got["own"] is False, got)
    for k, v, why in (("visible", False, "안 보임"), ("iconic", True, "최소화"),
                      ("cls", "Progman", "바탕화면"), ("cls", "WorkerW", "바탕화면 일꾼"), ("cls", "Shell_TrayWnd", "작업표시줄"),
                      ("cloaked", 2, "다른 가상 데스크톱 · 숨긴 UWP"), ("exstyle", 0x80, "도구 창"),
                      ("style", 0x40000000, "자식 창"), ("rect", (5, 5, 5, 90), "크기 0")):
        chk("  빼는 것: %s" % why, keep(**{k: v}) is None)
    o = keep(pid=1)
    chk("  이 앱의 테두리 있는 창은 own 으로 남긴다 (가리는 창 - 검토 #4) · 테두리 없는 창(도구 창)은 뺀다",
        isinstance(o, dict) and o["own"] is True and keep(pid=1, exstyle=0x80 | 0x8) is None, o)
    f = [keep(zoomed=True), keep(exstyle=0x8), keep(mon_dpi=144), keep(mon_dpi=0), keep(scaled=True)]
    chk("  최대화 · 항상 위 · 모니터 DPI 다름 · 좌표 배율 다름 표시", all(isinstance(x, dict) for x in f)
        and f[0]["max"] is True and f[1]["top"] is True and f[2]["odd"] is True and f[3]["odd"] is False
        and f[4]["odd"] is True, f)
    win_dpi_part(PW)
    chk("윈도 전체 화면 판정 (SHQueryUserNotificationState 2 · 3 · 4)", [PW._busy_state(n) for n in range(1, 7)]
        == [False, True, True, True, False, False])
    if PLAT.NAME != "platform_mac":
        return
    print("=== 9b. 맥: 진짜 겹침 순서 (Step 0 과 같은 것) ===")
    import Quartz
    from poketdesktop import platform_mac as MAC
    chk("맥: 세 종류 다 (Step 0 에서 확인)", MAC.HIDE_KINDS == ("window", "bar", "edge"))
    wins = MAC.other_windows()
    chk("창 목록: 권한 없이 rect · id · pid 만 (제목 없음)", isinstance(wins, list)
        and all(set(w) >= {"rect", "id"} and "name" not in w and "title" not in w for w in wins), wins[:2])
    mac_rows_part(MAC)
    oth = tk.Toplevel(root)
    oth.geometry("300x200+200+300")
    tk.Canvas(oth, bg="#00c000", highlightthickness=0).pack(fill="both", expand=True)
    settle(root, 0.4)
    me = tk.Toplevel(root)
    me.overrideredirect(True)
    bg = PLAT.transparent_window(me, "#ff00ff")
    v = PLAT.SpriteView(me, bg, 40, 40)
    v.show(v.frames([Image.new("RGB", (40, 40), (220, 0, 0))], (255, 0, 255))[0])
    me.geometry("+%d+%d" % (300, 280))
    settle(root, 0.3)
    on = int(MAC.nswindow(oth).windowNumber())
    mine = MAC.nswindow(me)
    wins = MAC.other_windows()
    chk("진짜 창: 이 앱의 테두리 있는 창은 own 으로 든다 (가리는 창) · 테두리 없는 창(숨은 포켓몬)은 안 든다 (검토 #4 · #6)",
        any(w["id"] == on and w.get("own") is True for w in wins)
        and not any(w["id"] == int(mine.windowNumber()) for w in wins), [w for w in wins if w.get("own")][:3])
    ok = MAC.order_just_below(me, on)
    settle(root, 0.3)
    lst = [int(w["kCGWindowNumber"]) for w in (Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID) or [])]
    my = int(mine.windowNumber())
    chk("order_just_below: 그 창 바로 뒤 (층 0 · 항상 위 아님)", ok and my in lst and on in lst
        and lst.index(my) == lst.index(on) + 1 and mine.level() == 0 and top(me) == 0, (ok, mine.level()))
    ok = MAC.order_below_bar(me)
    settle(root, 0.2)
    dock = Quartz.CGWindowLevelForKey(Quartz.kCGDockWindowLevelKey)
    chk("order_below_bar: 보통 창보다 위 · Dock 보다 아래 층", ok and 0 < mine.level() < dock and top(me) == 0,
        (mine.level(), dock))
    ok = MAC.order_above_desktop(me)
    settle(root, 0.2)
    lst = [(int(w["kCGWindowNumber"]), int(w.get("kCGWindowLayer", 0))) for w in (Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID) or [])]
    normals = [n for n, layer in lst if layer == 0]
    chk("order_above_desktop: 보통 창 가운데 맨 뒤 (바탕화면 바로 위)", ok and normals and normals[-1] == my
        and mine.level() == 0, normals[-3:])
    mac_cover_part(root, MAC, Quartz, me, oth)
    me.withdraw()
    settle(root, 0.2)
    chk("숨긴 창에는 걸지 않는다 (맥은 걸면 창이 도로 뜬다)", MAC.order_just_below(me, on) is False
        and not mine.isVisible())
    chk("맥 전체 화면 판정은 늘 거짓 (전체 화면 앱은 다른 Space)", MAC.fullscreen_busy() is False)
    me.destroy()
    oth.destroy()
    settle(root, 0.1)


def mac_rows_part(MAC):
    """맥 창 목록 거르기 (검토 #4 · #5 · #6) - CGWindowList 를 가짜 줄로 바꿔 끼운다."""
    import Quartz
    me = os.getpid()

    def row(num, pid, layer, r, alpha=1.0):
        return {"kCGWindowNumber": num, "kCGWindowOwnerPID": pid, "kCGWindowLayer": layer, "kCGWindowAlpha": alpha,
                "kCGWindowBounds": {"X": r[0], "Y": r[1], "Width": r[2] - r[0], "Height": r[3] - r[1]}}
    fake = [row(904, 60, 24, (0, 0, 1440, 30)),                 # 메뉴 막대
            row(903, 61, 20, (0, 0, 1440, 900)),                # Dock - 화면 전체 크기 창 하나
            row(902, 50, 3, (40, 300, 340, 600)),               # 남의 떠 있는 창 (항상 위)
            row(900, me, 0, (1250, 60, 1600, 420)),             # 이 앱의 테두리 있는 창 (포켓몬 관리)
            row(901, me, 0, (600, 600, 700, 700)),              # 이 앱의 테두리 없는 창 (도트 · 숨은 포켓몬)
            row(907, 50, 0, (300, 330, 560, 491)),              # 남의 보통 창 - 같은 앱 큰 창 안의 작은 창
            row(905, 50, 0, (230, 160, 630, 800)),              # 남의 보통 창
            row(908, 55, 0, (50, 50, 400, 400), alpha=0.0),     # 다 투명한 창
            row(906, 52, 0, (10, 10, 30, 30))]                  # 작은 띠
    real = Quartz.CGWindowListCopyWindowInfo
    had = "_own_titled" in vars(MAC)
    real_titled = vars(MAC).get("_own_titled")
    try:
        Quartz.CGWindowListCopyWindowInfo = lambda opts, rel: list(fake)
        MAC._own_titled = lambda: {900}
        got = MAC.other_windows()
    finally:
        Quartz.CGWindowListCopyWindowInfo = real
        if had:
            MAC._own_titled = real_titled
        else:
            del MAC._own_titled
    by = {w["id"]: w for w in got}
    chk("맥 창 목록: 남의 보통 창 · 남의 떠 있는 창 · 이 앱의 테두리 있는 창 (Dock · 메뉴 막대 · 테두리 없는 우리 창은 빼고)",
        [w["id"] for w in got] == [902, 900, 907, 905], [w["id"] for w in got])
    chk("  떠 있는 창은 top · 이 앱의 창은 own (가리는 창으로만) · 보통 창은 둘 다 아님",
        by.get(902, {}).get("top") is True and by.get(900, {}).get("own") is True
        and not by.get(905, {}).get("top") and not by.get(905, {}).get("own"), (by.get(902), by.get(900), by.get(905)))
    chk("  주인 pid 를 준다 (같은 앱의 자식 창 · 시트를 가려낸다 - 검토 #5)", by.get(907, {}).get("pid") == 50
        and by.get(905, {}).get("pid") == 50, by.get(907))
    chk("  그래서 큰 창 안의 작은 창이 아니라 큰 창에 건다", SP.anchor_for((0, 0, 1440, 900), (0, 25, 1440, 830), got)[0]
        == [w["id"] for w in got].index(905) if 905 in by else False, SP.anchor_for((0, 0, 1440, 900), (0, 25, 1440, 830), got))


def mac_cover_part(root, MAC, Quartz, me, oth):
    """창 뒤에 걸고 나서 보일 띠를 다른 창이 덮었나 (검토 #5) - 진짜 창으로. 자식 창 바로 뒤를 부탁하면 창 서버가 부모 뒤로
    넣는다 - order_just_below 가 False 를 돌려 부르는 쪽이 다른 자리를 고르게."""
    def rect_of(num):
        for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID) or []:
            if int(w["kCGWindowNumber"]) == num:
                b = w["kCGWindowBounds"]
                return (int(b["X"]), int(b["Y"]), int(b["X"] + b["Width"]), int(b["Y"] + b["Height"]))
        return None

    def call(*a):
        try:
            return MAC.order_just_below(*a)
        except Exception as e:                              # noqa: BLE001
            return "error: %s" % e

    def win(geo, color):
        t = tk.Toplevel(root)
        t.geometry(geo)
        tk.Canvas(t, bg=color, highlightthickness=0).pack(fill="both", expand=True)
        return t
    no = MAC.nswindow(oth)
    no.orderFrontRegardless()
    settle(root, 0.3)
    on = int(no.windowNumber())
    r = rect_of(on)
    strip = (r[0] + 40, r[1] - 24, r[0] + 80, r[1])          # 그 창 위 가장자리 너머로 빼꼼
    ok = call(me, on, strip)
    settle(root, 0.2)
    chk("order_just_below(띠): 그 창 말고 아무도 띠를 안 덮었으면 True", ok is True, ok)
    cov = win("200x200+%d+%d" % (r[0] + 20, r[1] - 150), "#c0c000")
    settle(root, 0.4)
    MAC.nswindow(cov).orderFrontRegardless()
    settle(root, 0.3)
    rc = rect_of(int(MAC.nswindow(cov).windowNumber()))
    ok = call(me, on, strip)
    settle(root, 0.2)
    chk("  앞의 다른 창(이 앱의 창이라도)이 띠를 덮었으면 False", rc is not None and SP.overlaps(rc, strip) and ok is False,
        (rc, strip, ok))
    cov.destroy()
    big = win("400x400+%d+%d" % (r[0] + 500, r[1]), "#00c0c0")
    kid = win("200x150+%d+%d" % (r[0] + 600, r[1] + 120), "#0000c0")
    settle(root, 0.4)
    nb, nk = MAC.nswindow(big), MAC.nswindow(kid)
    nb.addChildWindow_ordered_(nk, 1)                        # NSWindowAbove - 자식 창 (시트 · 붙은 패널)
    nb.orderFrontRegardless()
    settle(root, 0.3)
    rk, rb = rect_of(int(nk.windowNumber())), rect_of(int(nb.windowNumber()))
    ks = (rk[0] + 20, rk[1] - 24, rk[0] + 60, rk[1])         # 자식 창 위 너머 = 부모 창 안
    ok = call(me, int(nk.windowNumber()), ks)
    settle(root, 0.3)
    order = [int(w["kCGWindowNumber"]) for w in Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID) or []]
    my = int(MAC.nswindow(me).windowNumber())
    below_parent = my in order and int(nb.windowNumber()) in order and order.index(my) > order.index(int(nb.windowNumber()))
    chk("  자식 창 바로 뒤를 부탁하면 부모 뒤로 간다 - 띠가 부모에 덮였으니 False (다른 자리를 고른다)",
        SP.inside(ks, rb) and below_parent and ok is False, (ks, rb, below_parent, ok))
    try:
        nb.removeChildWindow_(nk)
    except Exception:                                       # noqa: BLE001
        pass
    kid.destroy()
    big.destroy()
    settle(root, 0.2)


def clean_part(root, ov, app, rec, errors):
    print("=== 8b. 정리 ===")
    ctl = app.wild
    path = dot_path()
    real_ensure, real_walk = sprite_cache.ensure, walk_cache.ensure
    sprite_cache.ensure = lambda api, num, shiny=False, back=False: path
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (None, None)
    try:
        ctl.HIDE_PEEK_MS, ctl.HIDE_Q_MS = 60000, 120000
        g = show_hide(root, app, rec, windows=[{"rect": (200, 200, 900, 700), "id": 11}], wid=901)
        g.label.event_generate("<Enter>")
        settle(root, 0.1)
        jobs = [g._job] + list(ctl._hide_jobs.values())
        wins = [w for w in (g.win, ctl.hint) if w is not None]
        chk("정리 전: 창 · 타이머가 있다", len(wins) >= 2 and all(jobs), (len(wins), jobs))
        ctl.clear()
        settle(root, 0.2)
        chk("clear(): 숨은 창 · 글 창이 남지 않는다", not any(w.winfo_exists() for w in wins))
        pending = str(root.tk.call("after", "info")).split()
        chk("  남은 after 가 없다 (틱 · 안내 예약)", not ctl._hide_jobs and g._job is None
            and not any(str(j) in pending for j in jobs if j), (ctl._hide_jobs, jobs))
        chk("그리는 중 예외 없음", not errors and g.errors == 0, errors[:2])
    finally:
        sprite_cache.ensure, walk_cache.ensure = real_ensure, real_walk


def main():
    spots_part()
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-800:])
    root.report_callback_exception = on_err
    U.init_fonts(root)
    U.apply_theme(root)
    settings = dict(config.DEFAULTS)
    settings["areaRect"] = list(AREA)
    ov = OV.Overlay(root, settings)
    ov.area = lambda: AREA
    path = dot_path()
    ov.paths[(25, False)] = path
    ov.sync([{"id": 1, "num": 25, "shiny": False, "info": {"name": "피카츄", "species": "피카츄", "level": 12}}], {})
    app = MiniApp(root, ov)
    rec = Rec()
    rec.install()
    random.seed(5)
    try:
        send_part(root, ov, app, rec)
        hider_part(root, ov, app, rec)
        click_part(root, ov, app, rec)
        follow_part(root, ov, app, rec)
        dpi_part(root, ov, app, rec)
        expire_part(root, ov, app, rec)
        settings_part(root, ov, app, rec)
        clean_part(root, ov, app, rec, errors)
    finally:
        rec.uninstall()
        try:
            app.wild.stop()
        except Exception:                                   # noqa: BLE001
            pass
        settle(root, 0.2)
    try:
        platform_part(root)
    finally:
        root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
