# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 (2.4.0) 화면 검사 — 장소 그림 · 입장 장면 · 발굴 일지 · 컨트롤러(폴링 · 현상 · 의식 → 입장).

    python client/test_arche_ui.py
    python client/run_as_windows.py client/test_arche_ui.py

서버는 가짜(FakeApi)다 - state 모양은 design-notes/2026-11-09-arche-plan.md 의 약속 그대로.
**수수께끼 내용은 지어낸 값이다** (공개 저장소).
"""
import datetime
import os
import sys
import tempfile
import time
import types

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-arche-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from poketdesktop import arche as AC                        # noqa: E402
from poketdesktop import arche_art as A                     # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_arche as J                      # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0


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


def iso(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isoformat()


NOW = time.time()


def state(ritual=False, solvers=0, phenomena=None, chapter=1, ready=True, journal=None, titles=None):
    ch1 = {"n": 1, "title": "돌의 문", "place": "cave", "placeKr": "동굴", "open": chapter == 1, "past": chapter > 1,
           "opensAt": iso(NOW - 3600), "closesAt": iso(NOW + 3600 * 40),
           "journal": journal if journal is not None else [{"at": iso(NOW - 3600), "text": "지어낸 일지 글. 시험용이다."}],
           "hints": [], "marks": [[1], [2], [3]], "ritual": ritual, "solvers": solvers, "first": "누군가" if solvers else None,
           "keys": [], "titleSalt": "s", "titleHashes": titles or [],
           "encounters": [{"slot": i, "state": "ready" if ritual else "locked"} for i in range(3)]}
    rest = [{"n": k, "title": "?", "future": True, "open": False, "past": False,
             "opensAt": iso(NOW + 3600 * 40 * k), "closesAt": iso(NOW + 3600 * 40 * (k + 1))} for k in range(2, 7)]
    return {"active": True, "ready": ready, "now": iso(time.time()), "chapter": chapter, "poll": 60,
            "chapters": [ch1] + rest, "phenomena": phenomena or []}


class Err(Exception):
    def __init__(self, status, message="거절"):
        Exception.__init__(self, message)
        self.status = status
        self.message = message


class FakeApi(object):
    def __init__(self):
        self.calls = []
        self.st = state()
        self.key_reply = {"ok": False}
        self.key_err = None

    def arche_state(self):
        self.calls.append(("state",))
        return self.st

    def arche_check(self):
        self.calls.append(("check",))
        return self.st

    def arche_key(self, n, text, via="type"):
        self.calls.append(("key", n, text, via))
        if self.key_err:
            raise self.key_err
        r = dict(self.key_reply)
        r["state"] = self.st
        return r

    def arche_battle(self, n, slot):
        self.calls.append(("battle", n, slot))
        return {"id": 9, "place": "cave", "battle": {}, "events": []}


class FakeOverlay(object):
    hidden = False
    pets = {}


class MiniApp(object):
    def __init__(self, root):
        self.root = root
        self.api = FakeApi()
        self.settings = dict(config.DEFAULTS)
        self.overlay = FakeOverlay()
        self.airraid = None
        self.notes = []
        self.syncs = 0
        self.arche = AC.ArcheController(self)

    def notify(self, m):
        self.notes.append(m)

    def request_sync(self):
        self.syncs += 1


# ---------------------------------------------------------------- 1. 그림
def art_part():
    print("=== 장소 그림 · 입장 장면 ===")
    for place in A.PLACES:
        for st in ("sealed", "open", "inside"):
            im = A.scene(place, 480, 270, st, 1, [[1], [2], [3]])
            colors = len(set(im.resize((120, 68)).getdata()))
            chk("%s %s: 크기 · 색이 여럿 (빈 그림 아님)" % (place, st), im.size == (480, 270) and colors >= 12, colors)
    sizes = set()
    for place in A.PLACES:
        fr = A.entry_frames(place, 640, 360, [[4], [5]])
        total = sum(ms for _, ms in fr)
        sizes.add(all(im.size == (640, 360) for im, _ in fr))
        chk("%s 입장 장면 5~8초" % place, 5000 <= total <= 8000, total)
    chk("입장 장면 그림 크기가 창 크기와 같다", sizes == {True}, sizes)
    sealed = A.scene("cave", 480, 270, "sealed", 0, [[1], [2], [3]])
    opened = A.scene("cave", 480, 270, "open", 0, [[1], [2], [3]])
    chk("봉인된 입구와 열린 입구가 다르다", sealed.tobytes() != opened.tobytes())
    chk("글자 24개가 서로 다르다", len(set(A.glyph(i, 1).tobytes() for i in range(24))) == 24)


# ---------------------------------------------------------------- 2. 수첩
class FakeCtl(object):
    def __init__(self, seen=None):
        self.seen = seen or []

    def seen_in(self, n):
        return self.seen


def _has_big_title(im):
    """큰 제목(두 배 글자)이 있으면 제목 자리에 두꺼운 잉크 덩어리가 있다 - 2x2 로 꽉 찬 잉크 칸 수로 본다."""
    px = im.load()
    n = 0
    for y in range(J.TEXT_L[1] + 14, J.TEXT_L[1] + 38, 2):
        for x in range(J.TEXT_L[0], J.TEXT_L[0] + 90, 2):
            if all(px[x + dx, y + dy] == J.INK for dx in (0, 1) for dy in (0, 1)):
                n += 1
    return n > 12


def book_part():
    print("=== 수첩 ===")
    im, hits, pages = J.draw_book({"ready": False, "chapters": []}, 1, 0, FakeCtl())
    chk("준비 전: 그려지고 쪽 하나", im.size == (J.LW, J.LH) and pages == 1, pages)
    st = state()
    im, hits, pages = J.draw_book(st, 1, 0, FakeCtl())
    chk("열린 장: 책갈피 여섯 · 사진 자리", all(("tab%d" % i) in hits for i in range(1, 7)) and "photo" in hits, sorted(hits))
    chk("의식 전에는 '전설에게 간다' 없음", "go" not in hits)
    st = state(ritual=True, solvers=4)
    im, hits, pages = J.draw_book(st, 1, 0, FakeCtl())
    chk("의식 뒤: '전설에게 간다'", "go" in hits, sorted(hits))
    simg, sxy = J.stamp_overlay(st["chapters"][0])
    chk("도장: 푼 사람이 있으면 두 줄 (수 · 첫 발견자)", simg is not None and simg.height > J.LINE_H * 2, simg and simg.size)
    im, hits, pages = J.draw_book(st, 3, 0, FakeCtl())
    chk("앞 장: 사진 · 단추 없음", "photo" not in hits and "go" not in hits, sorted(hits))
    long = [{"at": iso(NOW - 3600 * i), "text": "아주 긴 지어낸 일지 " * 20} for i in range(4)]
    im, hits, pages = J.draw_book(state(journal=long), 1, 0, FakeCtl())
    chk("긴 일지는 쪽을 넘긴다 (글자를 줄이지 않는다)", pages >= 2 and "next" in hits, pages)
    one_long = [{"at": iso(NOW - 3600), "text": "한 덩어리로 아주 긴 지어낸 일지 글이다. " * 40}]
    pages = J.paginate(J.left_blocks(state(journal=one_long)["chapters"][0], [], 160), 120, 170)
    chk("글 하나가 한 쪽보다 길면 쪽을 넘어 나눈다 (쪽마다 높이 안)", len(pages) >= 3
        and all(sum(b[2] for b in pg) <= 170 for pg in pages[1:]) and sum(b[2] for b in pages[0]) <= 120,
        [sum(b[2] for b in pg) for pg in pages])
    multi = [{"at": iso(NOW - 3600), "text": "지어낸 첫 문장이 여기서 꽤 길게 이어진다. 둘째 문장도 길게 이어지고 또 이어진다. " * 6}]
    pgs = J.paginate(J.left_blocks(state(journal=multi)["chapters"][0], [], 160), 120, 170)
    ends = [pg[-1][1][1][-1].rstrip() for pg in pgs[:-1] if pg and pg[-1][0] == "entry"]
    chk("쪽은 문장이 끝나는 곳에서 넘어간다 (말 끝이 다음 쪽으로 잘려 넘어가지 않는다)",
        len(pgs) >= 2 and ends and all(e.endswith(".") for e in ends)
        and all(sum(b[2] for b in pg) <= 170 for pg in pgs[1:]) and sum(b[2] for b in pgs[0]) <= 120, ends)
    huge = [{"at": iso(NOW - 3600), "text": "마침표 없이 아주 길게 이어지는 지어낸 한 문장 " * 30}]
    pgs = J.paginate(J.left_blocks(state(journal=huge)["chapters"][0], [], 160), 120, 170)
    chk("빈 쪽보다 긴 한 문장은 줄 단위로 나눈다 (넘쳐 그리지 않는다)", len(pgs) >= 3
        and all(sum(b[2] for b in pg) <= 170 for pg in pgs[1:]), [sum(b[2] for b in pg) for pg in pgs])
    st_long = state(journal=one_long)
    p0 = J.draw_book(st_long, 1, 0, FakeCtl())[0]
    p1 = J.draw_book(st_long, 1, 1, FakeCtl())[0]
    top = (J.TEXT_L[0], J.TEXT_L[1], J.TEXT_L[2], J.TEXT_L[1] + 12)
    chk("2쪽부터는 장 머리줄 · 큰 제목을 다시 안 그린다 (이어진 글과 안 겹친다)",
        p0.crop(top).tobytes() != p1.crop(top).tobytes()
        and J.draw_book(st_long, 1, 1, FakeCtl())[0].crop((J.TEXT_L[0], J.TEXT_L[1] + 14, J.TEXT_L[2], J.TEXT_L[1] + 40)).tobytes()
        != p0.crop((J.TEXT_L[0], J.TEXT_L[1] + 14, J.TEXT_L[2], J.TEXT_L[1] + 40)).tobytes()
        and not _has_big_title(p1))
    lines = J.wrap("가나다라마바사아자차카타파하 " * 6, 160)
    chk("줄바꿈: 모든 줄이 칸 안", all(J.text_w(s) <= 160 for s in lines) and len(lines) >= 3, lines)
    seen = [{"id": "u", "kind": "unown", "at": NOW - 60, "glyph": 5},
            {"id": "s", "kind": "stars", "at": NOW - 30, "pts": [[0.1, 0.2, 1], [0.6, 0.5, 0]]},
            {"id": "r", "kind": "relic", "at": NOW - 10, "text": "지어낸 새김 글"}]
    im, hits, pages = J.draw_book(state(), 1, 0, FakeCtl(seen))
    chk("내가 본 것 셋이 들어간다 (쪽이 늘 수 있다)", pages >= 1)
    par = [{"id": "parade:x", "kind": "parade", "at": NOW - 5, "glyphs": [1, 2, None, 4] * 6}]
    pb = [b for b in J.left_blocks(state()["chapters"][0], par, 160) if b[0] == "seen"]
    chk("안농 행렬은 '내가 본 것' 블록 하나 (본 글자 수 · 쪽 높이 안)", len(pb) == 1
        and "18 / 24" in " ".join(pb[0][1][1]) and pb[0][2] <= 170, pb and (pb[0][1][1], pb[0][2]))
    im, hits, pages = J.draw_book(state(), 1, 0, FakeCtl(par))
    chk("행렬이 든 일지도 그려진다", im.size == (J.LW, J.LH), pages)
    old = state()
    old["chapters"][0]["minClient"] = "9.9.9"
    im, hits, pages = J.draw_book(old, 1, 0, FakeCtl())
    chk("새 판이 필요한 장: 단추 없음", "go" not in hits)


# ---------------------------------------------------------------- 3. 컨트롤러
def hub_part(root, app):
    print("=== 허브 탭 ===")
    holder = tk.Frame(root)
    pane = J.ArchePane(app, holder)
    chk("허브 탭에 win 이 있다 (허브가 pane.win.pack)", hasattr(pane, "win") and pane.win.winfo_manager() == "",
        getattr(getattr(pane, "win", None), "winfo_manager", lambda: "없음")())
    pane.win.pack(fill="both", expand=True)
    pane.on_shown()
    holder.destroy()


def controller_part(root, app):
    print("=== 컨트롤러 ===")
    ctl = app.arche
    played = []

    def fake_play(app_, ph, on_seen):
        played.append(ph)
        if on_seen:
            on_seen(ph, None)
        return types.SimpleNamespace(closed=True, cleanup=lambda: None)

    fake_desktop = types.ModuleType("poketdesktop.arche_desktop")
    fake_desktop.play = fake_play
    sys.modules["poketdesktop.arche_desktop"] = fake_desktop
    import poketdesktop
    poketdesktop.arche_desktop = fake_desktop

    ctl.note({"active": False})
    settle(root, 0.2)
    chk("기간 밖: 폴링 안 함", not app.api.calls, app.api.calls)
    app.api.st = state(phenomena=[{"id": "ph1", "at": iso(time.time() + 0.3), "until": iso(time.time() + 30),
                                    "kind": "unown", "data": {"glyph": 3, "dir": 1}}])
    ctl.note({"active": True})
    chk("기간: 바로 묻는다", pump(root, lambda: ctl.state is not None), app.api.calls)
    chk("새 장 알림 (제1장)", any("제1장" in n for n in app.notes), app.notes)
    chk("현상이 그 시각에 뜬다", pump(root, lambda: played, 3), played)
    chk("본 것이 기록된다", any(r.get("id") == "ph1" for r in ctl.seen_in(1)), ctl.seen)
    for i, g in enumerate([5, 7, 9]):
        ctl._seen({"id": "pp-%d" % i, "kind": "unown", "data": {"glyph": g, "parade": "tp1", "pos": i, "of": 4}})
    ctl._seen({"id": "pp-1b", "kind": "unown", "data": {"glyph": 11, "parade": "tp1", "pos": 1, "of": 4}})
    ctl._seen({"id": "pp-bad", "kind": "unown", "data": {"glyph": 11, "parade": "tp1", "pos": 9, "of": 4}})
    rows = [r for r in ctl.seen if r.get("id") == "parade:tp1"]
    chk("안농 행렬은 한 줄로 모인다 (자리대로 · 같은 자리는 처음 것 · 놓친 자리는 빈칸 · 틀린 자리는 버림)",
        len(rows) == 1 and rows[0]["glyphs"] == [5, 7, 9, None] and rows[0]["kind"] == "parade", rows)
    ctl.poll()
    pump(root, lambda: len([c for c in app.api.calls if c[0] == "state"]) >= 2)
    settle(root, 0.6)
    chk("같은 현상은 한 번만", len(played) == 1, played)
    # 막혀 있으면 미룬다 (끝나기 전이면 다시)
    app.overlay.hidden = True
    ctl.blocked = lambda: "hidden"
    app.api.st = state(phenomena=[{"id": "ph2", "at": iso(time.time()), "until": iso(time.time() + 2),
                                    "kind": "drip", "data": {"count": 3}}])
    ctl.poll()
    settle(root, 1.0)
    chk("막혀 있으면 안 띄운다", not any(p["id"] == "ph2" for p in played), played)
    del ctl.blocked
    app.overlay.hidden = False
    # 의식 → 일지 → 도장 → 배틀. 바탕화면에 놓인 유물(누르기를 기다리는 현상)이 있어도 입장은 막히지 않는다
    lingering = types.SimpleNamespace(closed=False, cleanup=lambda: None, kind="relic")
    ctl.shows.append(lingering)
    chk("놓인 유물은 '바쁨' 이 아니다", not ctl.busy(), ctl.shows)
    walking = types.SimpleNamespace(closed=False, cleanup=lambda: None, kind="unown")
    ctl.shows.append(walking)
    chk("걷는 안농은 '바쁨'", ctl.busy())
    walking.closed = True
    opened = []

    class FakeBattle(object):
        def __init__(self, app_, data, place, geometry=None, on_close=None, on_next=None):
            opened.append((data, place, geometry))
            self.alive = True
            self.on_close = on_close

        def close(self):
            self.alive = False

    fake_battle = types.ModuleType("poketdesktop.arche_battle")
    fake_battle.ArcheBattleWindow = FakeBattle
    sys.modules["poketdesktop.arche_battle"] = fake_battle
    poketdesktop.arche_battle = fake_battle
    app.api.st = state(ritual=True, solvers=1)
    ctl.poll()
    chk("의식이 맞으면 일지가 뜬다", pump(root, lambda: ctl.window is not None and ctl.window.alive, 3))
    chk("…도장 뒤 사진이 커지고 전설 배틀 창이 열린다", pump(root, lambda: opened, 5), app.api.calls[-3:])
    chk("배틀은 1장 첫 자리", ("battle", 1, 0) in app.api.calls, app.api.calls[-3:])
    chk("배틀 창은 일지 자리 그대로", opened and opened[0][2], opened)
    ctl.poll()
    settle(root, 0.5)
    chk("입장 연출은 장마다 한 번만", len(opened) == 1, opened)
    ctl.battle.alive = False
    ctl.battle = None
    n_before = len([c for c in app.api.calls if c[0] == "battle"])
    ctl.open_battle(1, 0)
    ctl.open_battle(1, 0)                                   # 자동 입장과 단추가 겹친 것처럼
    pump(root, lambda: len(opened) >= 2, 2)
    settle(root, 0.3)
    chk("배틀 창을 여는 중에 또 부르면 한 번만 연다", len([c for c in app.api.calls if c[0] == "battle"]) == n_before + 1
        and len(opened) == 2, (app.api.calls[-3:], len(opened)))
    ctl.battle.alive = False
    ctl.battle = None
    # 열쇠 적기
    w = ctl.open_window(1)
    app.api.st = state()
    ctl.state = app.api.st
    w.refresh()
    w.entry.delete(0, "end")
    w.entry.insert(0, "지어낸 말")
    app.api.key_reply = {"ok": False}
    w.send()
    chk("틀린 말: '아무 일도'", pump(root, lambda: "아무 일도" in w.msg.cget("text")), w.msg.cget("text"))
    app.api.key_reply = {"ok": True, "key": "k1"}
    w.entry.insert(0, "맞는 말")
    w.send()
    chk("맞는 말: 빛났다", pump(root, lambda: "빛났다" in w.msg.cget("text")), w.msg.cget("text"))
    app.api.key_err = Err(429)
    w.entry.insert(0, "또")
    w.send()
    chk("너무 많이: 쉬었다가", pump(root, lambda: "쉬었다가" in w.msg.cget("text")), w.msg.cget("text"))
    app.api.key_err = None
    # 책갈피
    w._click(types.SimpleNamespace(x=(J.TABS_X + 4) * w.k, y=(18 + 2 * 32 + 5) * w.k))
    chk("책갈피 3 → 3장 쪽", w.n == 3, w.n)
    # 창 제목 열쇠가 있으면 감시를 켠다 (설정 끄면 끈다)
    started = []

    class FakeWatch(object):
        def __init__(self, root_, get, hit, enabled=None, every_ms=3000):
            started.append(get)

        def start(self):
            pass

        def stop(self):
            started.append("stop")

    fake_title = types.ModuleType("poketdesktop.arche_title")
    fake_title.TitleWatch = FakeWatch
    sys.modules["poketdesktop.arche_title"] = fake_title
    poketdesktop.arche_title = fake_title
    app.api.st = state(titles=["ab" * 32])
    ctl.poll()
    chk("제목 열쇠 → 감시 켬", pump(root, lambda: started), started)
    chk("감시가 받는 것: (장, 소금, 해시들)", started and started[0]() and started[0]()[0][0] == 1, started)
    app.settings["archeTitle"] = False
    ctl.poll()
    chk("설정 끔 → 감시 끔", pump(root, lambda: "stop" in started), started)
    ctl.clear()
    chk("정리: 창 · 예약 없음", ctl.window is None and ctl.job is None and not ctl.pending)
    # 계정마다 따로 남긴다 (같은 PC 다른 계정에 '내가 본 것' · 입장 기록이 섞이지 않게)
    app.username = "다른계정"
    other = AC.ArcheController(app)
    chk("다른 계정은 '내가 본 것' 이 비어 있다", other.seen == [] and other.local.get("entered") == [],
        (other.seen[:1], other.local.get("entered")))


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-800:])
    root.report_callback_exception = on_err
    app = MiniApp(root)
    try:
        art_part()
        book_part()
        hub_part(root, app)
        controller_part(root, app)
    finally:
        app.arche.clear()
        settle(root, 0.2)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
