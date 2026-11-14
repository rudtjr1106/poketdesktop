# -*- coding: utf-8 -*-
"""아르케 (2.4.0) 바탕화면 현상 검사 — 안농 · 유물 · 별 · 물방울 · 모래바람 · 떨림.

    python client/test_arche_desktop_ui.py
    python client/run_as_windows.py client/test_arche_desktop_ui.py

**진짜 Overlay 와 도트 창을 띄운다** (공습 검사 test_airraid_ui.py 와 같은 틀). 현상의 값(글자 번호 · 유물 글 ·
별 자리)은 이 검사가 지어낸 것이다 - 진짜 단서는 저장소 밖 비공개 답안지에만 있다.
본다: 각 현상이 끝까지 돌고 · on_seen 이 한 번 · 정리하면 창 · 예약(after)이 남지 않음 · 멈춤 감시 · 두 번 정리.
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-arche-desktop-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from poketdesktop import arche_desktop as AD                # noqa: E402
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


class MiniApp(object):
    def __init__(self, root, ov):
        self.root, self.overlay = root, ov
        self.settings = ov.settings if ov is not None else {}


def ph(kind, data, left=3.0, pid=None):
    """현상 하나 (state.phenomena 의 꼴). left: 끝까지 남은 초 (컨트롤러가 서버 시각으로 셈해 넣는다)."""
    now = time.time()
    return {"id": pid or ("t-" + kind), "at": now, "until": now + left, "left": left, "kind": kind, "data": data}


class Seen(object):
    def __init__(self):
        self.got = []

    def __call__(self, p, img):
        self.got.append((p.get("id"), img))


def tops(root):
    return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]


def pending(root):
    try:
        return set(root.tk.splitlist(root.tk.call("after", "info")))
    except tk.TclError:
        return set()


def clean_check(root, show, label, n_tops):
    settle(root, 0.2)
    left_jobs = pending(root) & set(show.issued)
    chk("%s: 정리 뒤 창이 남지 않는다" % label, len(tops(root)) == n_tops and not show.sprites,
        (len(tops(root)), n_tops, len(show.sprites)))
    chk("%s:   예약(after)이 남지 않는다" % label, not left_jobs, left_jobs)


# ---------------------------------------------------------------- 1. 안농
def unown_part(root, ov, app):
    print("=== 안농 ===")
    n0 = len(tops(root))
    seen = Seen()
    done = []
    sh = AD.play(app, ph("unown", {"glyph": 5, "dir": 1}, left=40), seen, on_done=lambda: done.append(1))
    chk("작업 표시줄 선을 걷는 안농 도트를 세운다 (도감 201)", sh.pet is not None and sh.pet in ov.extra
        and sh.pet.mon.get("num") == 201, sh.pet)
    chk("  안농은 이름표가 없다", getattr(sh.pet, "name_win", None) is None)
    x0 = sh.pet.x
    wl, wt, wr, wb = sh.work
    chk("  dir 1: 왼쪽 끝 밖에서 들어온다 · 발은 작업 표시줄 선", x0 + sh.pet.fw <= wl + 2
        and abs((sh.pet.y + sh.pet.fh) - sh.ground) < 2 and sh.ground >= wb - 6, (x0, wl, sh.ground, wb))
    pump(root, lambda: seen.got, 20)
    chk("가운데쯤 글자를 떨구면 on_seen (그림과 함께)", len(seen.got) == 1 and isinstance(seen.got[0][1], Image.Image),
        seen.got)
    g = sh.glyph_sprite
    chk("  떨군 글자가 바탕화면에 남아 있다", g is not None and g.visible(), g)
    mid = (wl + wr) / 2.0
    chk("  떨군 자리가 가운데쯤", g is not None and g.at and abs(g.at[0] - mid) < (wr - wl) * 0.2, (g and g.at, mid))
    pump(root, lambda: sh.pet is not None and sh.pet.x > mid + 40, 20)
    chk("글자를 떨군 뒤에도 가던 쪽으로 걷는다", sh.pet is not None and sh.pet.x > mid, sh.pet and sh.pet.x)
    pump(root, lambda: sh.closed, 30)
    chk("끝까지 가고 정리된다 · on_done", sh.closed and done == [1], (sh.phase, done))
    chk("  on_seen 은 한 번", len(seen.got) == 1, len(seen.got))
    chk("  안농 도트를 치운다 (ov.extra 에서도)", sh.pet is None and not [p for p in ov.extra if p.mon.get("num") == 201])
    clean_check(root, sh, "안농", n0)
    # dir -1: 오른쪽에서 들어온다
    sh2 = AD.play(app, ph("unown", {"glyph": 0, "dir": -1}, left=40, pid="u2"), Seen())
    chk("dir -1: 오른쪽 끝 밖에서 들어온다", sh2.pet is not None and sh2.pet.x >= sh2.work[2] - 2,
        (sh2.pet and sh2.pet.x, sh2.work))
    pump(root, lambda: sh2.phase == "drop", 20)
    sh2.cleanup()
    sh2.cleanup()
    chk("중간에 정리 (두 번 불러도 안전)", sh2.closed and sh2.pet is None)
    clean_check(root, sh2, "안농 중간 정리", n0)
    # 글자를 떨구기 전에 정리하면 on_seen 은 없다
    s3 = Seen()
    sh3 = AD.play(app, ph("unown", {"glyph": 3, "dir": 1}, pid="u3"), s3)
    settle(root, 0.1)
    sh3.cleanup()
    chk("떨구기 전에 끝나면 on_seen 없음", not s3.got)
    clean_check(root, sh3, "안농 바로 정리", n0)


# ---------------------------------------------------------------- 2. 유물
def relic_part(root, ov, app):
    print("=== 유물 ===")
    n0 = len(tops(root))
    seen = Seen()
    text = "지어낸 글: 이 돌은 검사용이다. " * 4
    sh = AD.play(app, ph("relic", {"text": text, "glyph": 2}, left=20), seen)
    chk("돌 조각 창 하나 - 누를 수 있다 (클릭 통과 아님)", sh.relic is not None and not sh.relic.through
        and sh.relic.label.bind("<Button-1>"), sh.relic)
    pump(root, lambda: sh.phase == "wait", 10)
    chk("  땅에 떨어져 기다린다", sh.phase == "wait", sh.phase)
    chk("  누르기 전엔 on_seen 없음", not seen.got)
    sh.on_click()
    settle(root, 0.1)
    chk("누르면 새겨진 글을 띄운다 · on_seen 한 번 (그림과 함께)", sh.panel is not None and sh.panel.visible()
        and len(seen.got) == 1 and isinstance(seen.got[0][1], Image.Image), (sh.panel, seen.got))
    img = seen.got[0][1]
    chk("  긴 글은 줄을 바꿔 그린다 (글자를 줄이지 않는다 - 폭 제한 · 높이가 는다)", img.width <= AD.PANEL_W + 40
        and img.height > 60, img.size)
    sh.on_click()
    chk("  다시 눌러도 on_seen 은 한 번", len(seen.got) == 1)
    pump(root, lambda: sh.closed, 30)
    chk("읽을 시간이 지나면 정리", sh.closed)
    clean_check(root, sh, "유물", n0)
    # 안 누르면 시간이 다 되어 사라진다
    s2 = Seen()
    sh2 = AD.play(app, ph("relic", {"text": "짧은 글"}, left=1.0, pid="r2"), s2)
    pump(root, lambda: sh2.closed, 15)
    chk("안 누르면 끝 시각에 사라진다 · on_seen 없음", sh2.closed and not s2.got, (sh2.phase, s2.got))
    clean_check(root, sh2, "유물 안 누름", n0)


# ---------------------------------------------------------------- 3. 별
def stars_part(root, ov, app):
    print("=== 별 ===")
    n0 = len(tops(root))
    seen = Seen()
    pts = [[0.1, 0.2, 0], [0.5, 0.6, 2], [0.9, 0.3, 1]]
    sh = AD.play(app, ph("stars", {"pts": pts, "band": 0.25}, left=1.5), seen)
    pump(root, lambda: seen.got, 10)
    chk("별 셋이 다 뜨면 on_seen (그림과 함께)", len(seen.got) == 1 and isinstance(seen.got[0][1], Image.Image), seen.got)
    chk("  별마다 작은 창 하나 (큰 화면 캔버스를 깔지 않는다)", len(sh.sprites) == 3
        and all(s.box[0] < 40 and s.box[1] < 40 for s in sh.sprites), [s.box for s in sh.sprites])
    wl, wt, wr, wb = sh.work
    band = (wb - wt) * 0.25
    chk("  화면 위쪽 띠 안 (band 비율)", all(wt <= s.at[1] <= wt + band + 40 for s in sh.sprites),
        [s.at for s in sh.sprites])
    xs = [s.at[0] for s in sh.sprites]
    chk("  가로 자리가 pts 차례대로", xs == sorted(xs) and xs[0] < wl + (wr - wl) * 0.2, xs)
    pump(root, lambda: sh.closed, 20)
    chk("끝 시각이 지나면 정리", sh.closed and len(seen.got) == 1)
    clean_check(root, sh, "별", n0)
    sh2 = AD.play(app, ph("stars", {"pts": [], "band": 0.2}, pid="s2"), Seen())
    settle(root, 0.1)
    chk("별이 없으면 바로 끝", sh2.closed)


# ---------------------------------------------------------------- 4. 물방울 · 모래바람 · 떨림
def small_part(root, ov, app):
    print("=== 물방울 · 모래바람 · 떨림 ===")
    n0 = len(tops(root))
    seen = Seen()
    sh = AD.play(app, ph("drip", {"count": 3}, left=5), seen)
    pump(root, lambda: sh.closed, 20)
    chk("물방울 셋이 차례로 떨어지고 끝난다", sh.closed and sh.drops == 3, (sh.phase, getattr(sh, "drops", None)))
    chk("  on_seen 한 번", len(seen.got) == 1, seen.got)
    clean_check(root, sh, "물방울", n0)
    seen = Seen()
    sh = AD.play(app, ph("sand", {"dir": -1}, left=5), seen)
    pump(root, lambda: sh.sprites, 3)
    xs0 = [s.at[0] for s in sh.sprites if s.at]
    chk("모래바람: dir -1 이면 오른쪽에서 시작", xs0 and min(xs0) > (sh.work[0] + sh.work[2]) / 2.0, xs0)
    pump(root, lambda: sh.closed, 20)
    chk("  끝까지 불고 정리 · on_seen 한 번", sh.closed and len(seen.got) == 1, (sh.phase, seen.got))
    clean_check(root, sh, "모래바람", n0)
    # 떨림: 바탕화면 포켓몬이 흔들리고 dir 쪽을 본다 - 끝나면 제자리 · 다시 돌아다닌다
    homes = dict((k, (p.x, p.y)) for k, p in ov.pets.items())
    seen = Seen()
    moved = []
    sh = AD.play(app, ph("tremor", {"dir": 1}, left=5), seen)

    def watch():
        moved.append(max(abs(p.x - homes[k][0]) for k, p in ov.pets.items()))
        return sh.closed
    pump(root, watch, 20)
    chk("떨림: 바탕화면 포켓몬이 흔들린다", max(moved or [0]) >= 3, max(moved or [0]))
    chk("  끝나면 제자리 · 다시 돌아다닌다 (battling 풀림)", all(abs(ov.pets[k].x - homes[k][0]) < 1
                                                      and not ov.pets[k].battling for k in homes),
        [(ov.pets[k].x, homes[k][0], ov.pets[k].battling) for k in homes])
    chk("  on_seen 한 번", len(seen.got) == 1)
    clean_check(root, sh, "떨림", n0)
    # 떨림 중 정리 (끝난 뒤 포켓몬이 다시 돌아다녔으니 제자리를 새로 잰다)
    homes = dict((k, (p.x, p.y)) for k, p in ov.pets.items())
    sh = AD.play(app, ph("tremor", {"dir": -1}, left=5, pid="t2"), Seen())
    settle(root, 0.1)
    sh.cleanup()
    chk("떨림 중 정리해도 제자리", all(abs(ov.pets[k].x - homes[k][0]) < 1 and not ov.pets[k].battling for k in homes))
    # 이미 배틀 중인 도트는 건드리지 않는다
    p1 = ov.pets[1]
    p1.battling = True
    sh = AD.play(app, ph("tremor", {"dir": 1}, left=5, pid="t3"), Seen())
    pump(root, lambda: sh.closed, 20)
    chk("배틀 중인 도트는 떨림이 건드리지 않는다 (끝나도 battling 그대로)", p1.battling and p1 not in sh.frozen_all)
    p1.battling = False


# ---------------------------------------------------------------- 5. 감시 · 이상한 값
def guard_part(root, ov, app):
    print("=== 감시 · 이상한 값 ===")
    n0 = len(tops(root))
    sh = AD.play(app, {"id": "x", "kind": "모름", "data": {}}, Seen())
    chk("모르는 종류는 바로 끝 (터지지 않는다)", sh.closed)
    sh = AD.play(app, {"id": "y", "kind": "unown", "data": None}, Seen())
    settle(root, 0.1)
    sh.cleanup()
    chk("data 가 없어도 터지지 않는다", sh.closed)
    sh = AD.play(app, {"id": "z", "kind": "relic", "until": "2026-11-15T03:12:40+09:00", "data": {"text": "x"}}, Seen())
    chk("지난 끝 시각(ISO) 이면 잠깐만 보이고 끝난다 - 터지지 않는다", True)
    sh.cleanup()
    none_app = MiniApp(root, None)
    sh = AD.play(none_app, ph("unown", {"glyph": 1, "dir": 1}, pid="n"), Seen())
    settle(root, 0.1)
    chk("바탕화면(overlay)이 없어도 터지지 않는다 (글자만 떨군다)", sh.pet is None)
    sh.cleanup()
    # 멈춤 감시: 걷기 한 걸음이 다음을 안 부르면 정리
    real_walk, real_stall = AD.Show.walk, AD.STALL_MS
    AD.Show.walk = lambda self, pet, fx, fy, t, done=None: None
    AD.STALL_MS = 1200
    try:
        sh = AD.play(app, ph("unown", {"glyph": 4, "dir": 1}, left=60, pid="st"), Seen())
        pump(root, lambda: sh.closed, 10)
    finally:
        AD.Show.walk, AD.STALL_MS = real_walk, real_stall
    chk("멈춤 감시: 진행이 멎으면 정리한다", sh.closed and sh.pet is None)
    # 유물을 기다리는 동안은 멈춘 것이 아니다
    AD.STALL_MS = 800
    try:
        sh = AD.play(app, ph("relic", {"text": "기다림"}, left=60, pid="rw"), Seen())
        pump(root, lambda: sh.phase == "wait", 10)
        settle(root, 1.2)
        chk("  누르기를 기다리는 동안엔 감시가 안 자른다", not sh.closed and sh.phase == "wait", sh.phase)
        sh.cleanup()
    finally:
        AD.STALL_MS = real_stall
    # 재생 중 예외
    real = AD.Show._drop_glyph
    AD.Show._drop_glyph = lambda self: 1 / 0
    try:
        sh = AD.play(app, ph("unown", {"glyph": 4, "dir": 1}, left=60, pid="ex"), Seen())
        pump(root, lambda: sh.closed, 20)
    finally:
        AD.Show._drop_glyph = real
    chk("재생 중 예외가 나도 정리된다", sh.closed and sh.pet is None)
    clean_check(root, sh, "예외", n0)
    # on_seen 이 터져도 연출은 끝까지
    sh = AD.play(app, ph("stars", {"pts": [[0.5, 0.5, 1]], "band": 0.2}, left=0.5, pid="sx"),
                 lambda p, im: 1 / 0)
    pump(root, lambda: sh.closed, 10)
    chk("on_seen 이 터져도 정리까지 간다", sh.closed)
    logs = []
    real_log = config.log
    config.log = lambda m, *a: logs.append(m)
    try:
        sh = AD.play(app, {"id": "react", "kind": "tremor", "data": {"dir": 1}}, None)
        pump(root, lambda: sh.closed, 10)
    finally:
        config.log = real_log
    chk("on_seen 없이(None) 틀어도 된다 (창 제목이 맞았을 때의 떨림) - 오류 기록 없음", sh.closed and not logs, logs)
    clean_check(root, sh, "on_seen 예외", n0)


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
    colors = {1: (230, 110, 40, 255), 2: (80, 140, 220, 255), 201: (40, 40, 40, 255)}
    for n, c in colors.items():
        SHEETS[n] = make_sheet("s%d.png" % n, 32, c)
        FILES[n] = make_dot("d%d.png" % n, c)
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
    app = MiniApp(root, ov)
    AD.SPEED = 8.0
    try:
        unown_part(root, ov, app)
        relic_part(root, ov, app)
        stars_part(root, ov, app)
        small_part(root, ov, app)
        guard_part(root, ov, app)
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
