# -*- coding: utf-8 -*-
"""화면 테마 '디아루가·펄기아'(skins/dp) 검사 - 뜨는 메뉴(기본 그대로) · 지닌 도구 고르기.

    python client/test_skin_dp_menus.py

**창을 진짜로 띄운다** (가짜 서버). 테마는 칠하기만 새로 하고 동작은 기본 것을 그대로 쓴다.

  1~3. 뜨는 메뉴(U.PopupMenu)는 **DP 테마에서도 기본 테마 그대로**다 (사용자 결정 2026-10-25 - 트레이 메뉴가
     너무 커서 기본 스킨으로 쭉 유지). 기본 클래스로 뜨고, 줄의 모든 키(header · indent · checked · enabled ·
     bold · command 없음 · 구분선)가 기본 빛깔 · 글꼴로 그려지고, 올리면 기본 빛(BG4). 같은 줄 목록을
     기본 테마 프로세스에서도 띄워 창 크기 · 줄 자리 · 빛깔 · 글꼴이 **똑같은지** 맞춘다 (트레이 · 펫 · 볼 ·
     드롭다운이 다 이 클래스다). 닫히는 규칙(바깥 누르기 · Esc · 새 메뉴 · close_all) · 고르면 먼저 닫기 ·
     줄이 많으면 단 나누기는 그대로.
  4. 지닌 도구 고르기(ui_box.HeldPicker)가 DP 클래스로 뜬다. 보이는 도구는 기본과 같은 규칙 (지닐 수 있고
     가진 것 · 맞는 메가스톤만). 커서 · 보라 띠 · 진화 도구 경고, 누르거나 Enter 면 서버에 hold.
     지닐 것이 없을 때 · 가방을 못 받았을 때. 창은 내용만큼 (기본 크기를 넘지 않는다).
  5. 그리는 중에 난 예외가 없다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-skin-dp-menus-")
os.environ["POKET_SKIN"] = "default" if "--probe" in sys.argv else "dp"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import json                                                 # noqa: E402
import tkinter as tk                                        # noqa: E402

import smoke_box_filter as SB                               # noqa: E402
from test_big_lists import settle, wait                     # noqa: E402
from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-skin-dp-menus-")   # (SB 가 바꿨어도 새 임시 폴더)

OK = FAIL = 0
ROOT = os.path.dirname(HERE)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Ev(object):
    def __init__(self, x, y):
        self.x, self.y = x, y


def mid(m, i):
    x1, y1, x2, y2, _row = m._hits[i]
    return Ev((x1 + x2) // 2, (y1 + y2) // 2)


# ---------------------------------------------------------------- 1~3. 뜨는 메뉴
# 뜨는 메뉴는 DP 로 칠하지 않고 **기본 테마 그대로** 둔다 (사용자 결정, 2026-10-25: 트레이 메뉴가 너무 크다 ->
# 기본 스킨으로 쭉 유지). 같은 줄 목록을 이 프로세스(DP)와 기본 테마 프로세스에서 띄워 재서 맞춰 본다.
ROWS = [{"text": "피카츄   Lv.5", "enabled": False},
        None,
        {"text": "정보 보기"},
        {"text": "추천   몬스터볼 5개", "bold": True},
        {"text": "바로 가기", "header": True},
        {"text": "이름표 보이기", "checked": True, "indent": 1},
        {"text": "소리 켜기", "checked": False, "indent": 1},
        {"text": "버전 1.13.4", "enabled": False, "indent": 1},
        {"text": "할 일 없는 줄", "nocmd": True},
        None,
        {"text": "종료"}]
LONG = [{"text": "지금은 몬스터볼보다 하이퍼볼이 훨씬 잘 듣습니다 (없음)", "enabled": False},
        {"text": "정보 보기"}]
MANY = [{"text": "박스 %d   %d / 30마리" % (i + 1, i)} for i in range(48)]


def make_rows(rows, log=None):
    """검사용 줄(명령은 log 에 이름을 남긴다) -> PopupMenu 줄. nocmd 는 command 가 아예 없는 줄."""
    out = []
    for r in rows:
        if r is None or r.get("header"):
            out.append(r)
            continue
        r = dict(r)
        if r.pop("nocmd", False):
            pass
        elif log is not None:
            r["command"] = (lambda t=r["text"]: log.append(t))
        else:
            r["command"] = lambda: None
        out.append(r)
    return out


def font_of(root, spec):
    from tkinter import font as tkfont
    a = tkfont.Font(root=root, font=spec).actual()
    return (a["family"], a["size"], a["weight"], a["slant"])


def labels_of(m):
    """메뉴 창 안의 줄(Label)들 - 단 순서대로, 위에서 아래로."""
    out = []

    def rec(w):
        for c in w.winfo_children():
            if c.winfo_class() == "Label":
                out.append(c)
            rec(c)
    rec(m.win)
    return out


def probe(root):
    """줄 목록마다 메뉴를 띄워 창 크기 · 빛깔 · 글꼴 · 올렸을 때 빛깔을 잰다 (테마끼리 비교용 - JSON 이 되는 값만)."""
    res = {}
    for name, rows, kw in (("rows", ROWS, dict(width=190)), ("long", LONG, dict(width=150)),
                           ("many", MANY, dict(width=180)), ("tray", ROWS, dict(anchor="ne"))):
        m = U.PopupMenu(root, make_rows(rows), 400, 300, **kw)
        root.update()
        root.update_idletasks()
        labs = labels_of(m)
        info = {"size": (m.win.winfo_width(), m.win.winfo_height()), "cols": m.cols, "width": m.width,
                "win": (str(m.win.cget("bg")), str(m.win.cget("highlightbackground")),
                        int(m.win.cget("highlightthickness"))),
                "catcher": str(m.catcher.cget("bg")),
                "labels": [], "seps": []}
        for lab in labs:
            hov = None
            if str(lab.cget("cursor")):
                lab.event_generate("<Enter>")
                root.update()
                on = str(lab.cget("bg"))
                lab.event_generate("<Leave>")
                root.update()
                hov = (on, str(lab.cget("bg")))
            info["labels"].append([lab.cget("text"), str(lab.cget("bg")), str(lab.cget("fg")),
                                   font_of(root, lab.cget("font")), (lab.winfo_width(), lab.winfo_height()),
                                   (lab.winfo_x(), lab.winfo_y()), hov])

        def seps(w):
            for c in w.winfo_children():
                if c.winfo_class() == "Frame" and not c.winfo_children() and int(c.cget("height")) <= 3:
                    info["seps"].append([str(c.cget("bg")), c.winfo_height()])
                seps(c)
        seps(m.win)
        m.close()
        res[name] = info
    return res


def default_probe():
    """기본 테마를 따로 띄워(프로세스) 같은 것을 잰다."""
    import subprocess
    env = dict(os.environ, POKET_SKIN="default")
    env.pop("POKET_SKINS", None)
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "--probe"], env=env, capture_output=True,
                       text=True, timeout=120)
    for line in r.stdout.splitlines():
        if line.startswith("PROBE "):
            return json.loads(line[6:])
    return None


def menus(root):
    print("=== 뜨는 메뉴 (기본 테마 그대로) ===")
    log = []
    m = U.PopupMenu(root, make_rows(ROWS, log), 400, 300, width=190, on_close=lambda: log.append("closed"))
    root.update_idletasks()
    chk("기본 메뉴 클래스로 뜬다 (DP 클래스가 아니다)", type(m) is U.PopupMenu and "skins" not in type(m).__module__,
        (type(m).__module__, type(m).__name__))
    chk("떴다 · 감시 고리가 돈다", m.alive() and m._watch_job is not None)
    labs = labels_of(m)
    chk("줄마다 Label 이 있다 (구분선 둘은 빼고)", len(labs) == len([r for r in ROWS if r]), len(labs))
    chk("창 폭 = 준 폭 + 2 (기본과 같다)", m.win.winfo_width() == 192, m.win.winfo_width())

    # --- 빛깔 · 글꼴이 기본 값 그대로 (DP 갈무리 · 흰 판이 아니다)
    base_f = font_of(root, U.FONT)
    chk("창 바탕 · 테두리가 기본 (BG2 · LINE2)", (str(m.win.cget("bg")), str(m.win.cget("highlightbackground")))
        == (U.BG2, U.LINE2), (m.win.cget("bg"), m.win.cget("highlightbackground")))
    chk("바깥 누름 판은 검정(거의 투명)", str(m.catcher.cget("bg")) == "#000000")
    by = dict((l.cget("text").strip().lstrip("✓").strip(), l) for l in labs)
    chk("줄 바탕이 기본 (BG2)", all(str(l.cget("bg")) == U.BG2 for l in labs), [l.cget("bg") for l in labs])
    chk("보통 줄: 글씨 FG · 기본 글꼴", str(by["정보 보기"].cget("fg")) == U.FG
        and font_of(root, by["정보 보기"].cget("font")) == base_f, (by["정보 보기"].cget("fg"), by["정보 보기"].cget("font")))
    chk("  글꼴이 갈무리가 아니다", "Galmuri" not in font_of(root, by["정보 보기"].cget("font"))[0], font_of(
        root, by["정보 보기"].cget("font")))
    chk("굵은 줄: 기본 굵은 글꼴", font_of(root, by["추천   몬스터볼 5개"].cget("font")) == font_of(root, U.FONT_B),
        font_of(root, by["추천   몬스터볼 5개"].cget("font")))
    chk("꺼 둔 줄: DISABLED_FG", str(by["피카츄   Lv.5"].cget("fg")) == U.DISABLED_FG, by["피카츄   Lv.5"].cget("fg"))
    chk("머리줄: FG_FAINT · 작은 글꼴", str(by["바로 가기"].cget("fg")) == U.FG_FAINT
        and font_of(root, by["바로 가기"].cget("font")) == font_of(root, U.FONT_XS),
        (by["바로 가기"].cget("fg"), by["바로 가기"].cget("font")))
    chk("체크 줄: 기본의 '✓ ' 글씨", by["이름표 보이기"].cget("text").startswith("✓ ")
        and by["소리 켜기"].cget("text").startswith("    "), (by["이름표 보이기"].cget("text"), by["소리 켜기"].cget("text")))
    # --- 올렸을 때
    hov = by["정보 보기"]
    hov.event_generate("<Enter>")
    root.update()
    chk("올리면 기본 빛(BG4)", str(hov.cget("bg")) == U.BG4, hov.cget("bg"))
    hov.event_generate("<Leave>")
    root.update()
    chk("  떼면 BG2 로 돌아온다", str(hov.cget("bg")) == U.BG2, hov.cget("bg"))
    chk("꺼 둔 줄 · 머리줄 · 명령 없는 줄은 올려도 안 바뀐다 (손 모양도 없다)",
        all(not str(by[t].cget("cursor")) for t in ("피카츄   Lv.5", "바로 가기", "버전 1.13.4", "할 일 없는 줄")),
        [(t, by[t].cget("cursor")) for t in ("피카츄   Lv.5", "바로 가기", "할 일 없는 줄")])

    # --- 고르기
    by["이름표 보이기"].event_generate("<Button-1>")
    root.update()
    chk("누르면 닫고 나서 명령", log == ["closed", "이름표 보이기"] and not m.alive(), log)
    chk("  닫히면 감시 고리도 멈춘다", m._watch_job is None)

    del log[:]
    m = U.PopupMenu(root, make_rows(ROWS, log), 400, 300, width=190)
    by = dict((l.cget("text").strip().lstrip("✓").strip(), l) for l in labels_of(m))
    by["버전 1.13.4"].event_generate("<Button-1>")
    by["할 일 없는 줄"].event_generate("<Button-1>")
    root.update()
    chk("꺼 둔 줄 · 명령 없는 줄을 눌러도 아무 일 없다", m.alive() and not log, log)
    U.close_all()

    # --- 기본 테마와 똑같은가 (창 크기 · 빛깔 · 글꼴 · 줄 자리 · 올렸을 때)
    print("\n=== 기본 테마와 똑같은 모양 ===")
    mine = json.loads(json.dumps(probe(root)))
    base = default_probe()
    chk("기본 테마 프로세스에서 잰다", base is not None)
    if base is not None:
        for name in ("rows", "long", "many", "tray"):
            a, b = mine[name], base[name]
            chk("[%s] 창 크기 %s 가 기본과 같다" % (name, tuple(a["size"])), a["size"] == b["size"], (a["size"], b["size"]))
            chk("  단 수 · 폭 · 창 빛깔", (a["cols"], a["width"], a["win"], a["catcher"]) == (b["cols"], b["width"], b["win"], b["catcher"]),
                (a["cols"], a["width"], a["win"]))
            chk("  줄(글 · 바탕 · 글씨빛 · 글꼴 · 크기 · 자리 · 올렸을 때)이 전부 같다", a["labels"] == b["labels"],
                [(x, y) for x, y in zip(a["labels"], b["labels"]) if x != y][:1])
            chk("  구분선이 같다", a["seps"] == b["seps"], (a["seps"], b["seps"]))

    print("\n=== 닫히는 규칙 (기본 그대로) ===")
    rows = make_rows(ROWS)
    real = PLAT.mouse_buttons_down

    def press(mm, down, inside):
        PLAT.mouse_buttons_down = lambda: down
        mm._inside = lambda: inside
        mm._watch()
    try:
        m = U.PopupMenu(root, rows, 400, 300)
        m._was_down = 0
        press(m, 1, inside=True)
        chk("메뉴 안을 누르면 안 닫힌다", m.alive())
        m._was_down = 0
        press(m, 1, inside=False)
        chk("메뉴 밖을 누르면 닫힌다", not m.alive())
        PLAT.mouse_buttons_down = lambda: 2
        m2 = U.PopupMenu(root, rows, 400, 300)
        m2._inside = lambda: False
        m2._watch()
        chk("누른 채로 열려도 그 눌림으론 안 닫힌다", m2.alive())
        PLAT.mouse_buttons_down = lambda: 0
        a = U.PopupMenu(root, rows, 100, 100)
        chk("새로 열면 앞의 것이 닫힌다", not m2.alive() and a.alive())
        a.win.event_generate("<Escape>")
        root.update()
        if a.alive():                                       # 키는 포커스를 가진 창으로 간다
            a.win.focus_force()
            root.update()
            a.win.event_generate("<Escape>")
            root.update()
        chk("Esc 로 닫힌다", not a.alive())
        b = U.PopupMenu(root, rows, 300, 300)
        catcher = b.catcher
        catcher.event_generate("<Button-1>", x=5, y=5)
        root.update()
        chk("화면을 덮은 판을 누르면 닫힌다", not b.alive())
        U.PopupMenu(root, rows, 300, 300)
        U.close_all()
        chk("close_all 로 전부 닫힌다", not U.PopupMenu._open)
    finally:
        PLAT.mouse_buttons_down = real

    print("\n=== 여러 단 (기본 그대로) ===")
    m = U.PopupMenu(root, make_rows(LONG), 400, 300, width=150)
    root.update_idletasks()
    chk("글씨가 길어도 폭은 준 대로 (기본 - 글꼴 · 폭을 키우지 않는다)", m.width == 150 and m.win.winfo_width() == 152,
        (m.width, m.win.winfo_width()))
    chk("  창이 화면 안에 있다", m.win.winfo_x() >= 0 and m.win.winfo_x() + m.win.winfo_width()
        <= U.all_screens(root)[2] + 1, (m.win.winfo_x(), m.win.winfo_width()))
    U.close_all()

    m = U.PopupMenu(root, make_rows(MANY), 400, 300, width=180)
    root.update_idletasks()
    W, H = m.win.winfo_width(), m.win.winfo_height()
    _x1, sy1, _x2, sy2 = U.screen_at(root, 400, 300)
    chk("줄이 화면보다 많으면 단을 나눈다", m.cols > 1 and H <= (sy2 - sy1), (m.cols, H, sy2 - sy1))
    labs = labels_of(m)
    chk("  줄은 다 창 안에", len(labs) == len(MANY) and all(
        l.winfo_rootx() >= m.win.winfo_rootx() and l.winfo_rootx() + l.winfo_width() <= m.win.winfo_rootx() + W
        and l.winfo_rooty() + l.winfo_height() <= m.win.winfo_rooty() + H for l in labs), (W, H))
    cols = sorted(set(l.winfo_rootx() for l in labs))
    chk("  단마다 같은 폭", len(cols) == m.cols and len(set(l.winfo_width() for l in labs)) == 1,
        (cols, set(l.winfo_width() for l in labs)))
    U.close_all()


# ---------------------------------------------------------------- 4. 지닌 도구 고르기
class HoldApi(SB.FakeApi):
    def __init__(self, mons, shop=None, fail=False):
        SB.FakeApi.__init__(self, mons)
        self._shop = shop
        self.fail = fail

    def shop(self):
        if self.fail:
            raise SB._Refused("가방을 받지 못했습니다.", 500)
        if self._shop is not None:
            return self._shop
        r = SB.FakeApi.shop(self)
        r = dict(r, bag=dict(r["bag"], METALCOAT=1, LEFTOVERS=3),
                 items=r["items"] + [{"id": "METALCOAT", "kr": "금속코트", "cat": "held", "holdable": True,
                                      "desc": "강철타입 기술의 위력이 올라간다. 지니게 하면 그 기술을 쓸 때마다 조금 더 "
                                              "세게 친다. 통신교환 대신 가방에서 쓰면 진화하는 포켓몬도 있다.",
                                      "effect": {"kind": "held"}}])
        return r


class FakeBox(object):
    def __init__(self, root, app):
        self.root, self.app = root, app
        self.done = []

    def _after(self, msg):
        return lambda r, err: self.done.append((msg, err))


def held(root, dex):
    print("\n=== 지닌 도구 고르기 ===")
    onix = SB.mon(dex, 95, 7, on=True, held="ORANBERRY")
    squirtle = SB.mon(dex, 7, 2, on=True)
    app = SB.FakeApp(root, dex, [onix, squirtle])
    app.api = HoldApi([onix, squirtle])
    box = FakeBox(root, app)

    pk = ui_box.HeldPicker(box, onix)
    chk("DP 클래스로 뜬다 (skins/dp/held.py, box.py 가 다시 내보낸다)", type(pk).__module__.endswith("skins.dp.held")
        and type(pk) is __import__("poketdesktop.skins.dp.box", fromlist=["HeldPicker"]).HeldPicker, type(pk).__module__)
    chk("다 받기 전에는 기다림 표시", pk._busy())
    wait(root, lambda: pk._state != "wait")
    settle(root)
    names = [it["kr"] for it, _n in pk._items]
    chk("가진 것 중 지닐 수 있는 것만 (기본 규칙)", names == ["금속코트", "먹다남은음식", "오랭열매"], names)
    chk("  맞지 않는 메가스톤은 안 나온다", "리자몽나이트X" not in names)
    chk("  가진 수", dict((it["kr"], n) for it, n in pk._items).get("먹다남은음식") == 3, pk._items)
    chk("커서가 첫 줄에", pk._cur == "METALCOAT", pk._cur)
    chk("진화 도구를 안다", "METALCOAT" in pk.evo_items, pk.evo_items)
    band = " ".join(pk.cv.itemcget(i, "text") for i in pk.cv.find_withtag("scene")
                    if pk.cv.type(i) == "text").replace("\n", " ")
    chk("보라 띠에 이름 · 종류 · 개수", "금속코트 · 지닌 도구 · 1개" in band, band[:200])
    chk("  진화 도구 경고", ui_box.HOLD_EVO_NOTE in band, band[-200:])
    chk("메시지 상자에 지금 지닌 것", "오랭열매를 지니고 있습니다" in pk.msg[0], pk.msg)
    row_txt = [pk.vl.cv.itemcget(i, "text") for i in pk.vl.cv.find_all() if pk.vl.cv.type(i) == "text"]
    chk("줄에 진화 도구 꼬리표", "진화 도구" in row_txt, row_txt)
    chk("고른 줄에 빨간 ▶ 커서 (크림빛 줄)", any(pk.vl.cv.type(i) == "polygon" and pk.vl.cv.itemcget(i, "fill") == "#e83030"
                                       for i in pk.vl.cv.find_all()))
    BH0 = pk._band_need(pk.cv, pk.cv.winfo_width())

    pk.vl._motion(Ev(40, pk.vl.tops[2] + 5))
    settle(root, 0.1)
    chk("마우스를 올리면 커서가 따라온다", pk._cur == "ORANBERRY", pk._cur)
    band = " ".join(pk.cv.itemcget(i, "text") for i in pk.cv.find_withtag("scene")
                    if pk.cv.type(i) == "text").replace("\n", " ")
    chk("  띠가 그 도구로", "오랭열매 · 지닌 도구" in band and ui_box.HOLD_EVO_NOTE not in band, band[:120])
    chk("  띠 높이는 안 바뀐다", pk._band_need(pk.cv, pk.cv.winfo_width()) == BH0)
    pk.vl._left(None)
    chk("목록을 벗어나도 커서는 남는다", pk._cur == "ORANBERRY", pk._cur)
    pk._step(-1)
    chk("위 화살표로 옮긴다", pk._cur == "LEFTOVERS", pk._cur)
    pk._step(-5)
    chk("  맨 위에서 멈춘다", pk._cur == "METALCOAT", pk._cur)
    chk("창은 기본 크기를 넘지 않는다", pk.win.winfo_height() <= U.h(560) + 2, pk.win.winfo_height())
    chk("  내용만큼 줄었다 (세 줄)", pk.win.winfo_height() < U.h(560) - 20, pk.win.winfo_height())

    pk._step(1)
    pk._enter()
    chk("Enter 면 서버에 hold (그 포켓몬 · 그 도구)", app.api.calls[:1] == [("hold", 7, "LEFTOVERS")], app.api.calls)
    pk._enter()
    chk("  기다리는 동안 또 누르면 안 간다", len(app.api.calls) == 1, app.api.calls)
    wait(root, lambda: box.done)
    settle(root, 0.1)
    chk("  끝나면 박스 창에 알리고 닫힌다", box.done and box.done[0][1] is None and not pk.alive
        and not pk.win.winfo_exists(), box.done)

    pk = ui_box.HeldPicker(box, squirtle)
    wait(root, lambda: pk._state != "wait")
    settle(root)
    i = [it["id"] for it, _n in pk._items].index("ORANBERRY")
    y = pk.vl.tops[i] + 4
    pk.vl._click(Ev(40, y))
    wait(root, lambda: len(box.done) > 1)
    chk("누르면 바로 지닌다", app.api.calls[-1] == ("hold", 2, "ORANBERRY"), app.api.calls)
    band_items = [it["kr"] for it, _n in pk._items]
    chk("  진화 도구가 아닌 포켓몬에겐 경고가 없다", "METALCOAT" not in pk.evo_items, band_items)

    print("\n=== 지닐 것이 없을 때 · 못 받았을 때 ===")
    app.api = HoldApi([squirtle], shop={"bag": {"POKEBALL": 3}, "items": [
        {"id": "POKEBALL", "kr": "몬스터볼", "cat": "ball", "holdable": False}]})
    pk = ui_box.HeldPicker(box, squirtle)
    wait(root, lambda: pk._state != "wait")
    settle(root)
    texts = " ".join(pk.cv.itemcget(i, "text") for i in pk.cv.find_withtag("scene") if pk.cv.type(i) == "text")
    chk("지닐 것이 없으면 목록 자리에 그렇게", pk._state == "empty" and "지닐 수 있는 도구가 없다" in texts, texts[:200])
    chk("  메시지 상자는 기본 안내", "상점의 '지닌 도구' 칸" in pk.msg[0], pk.msg)
    chk("  띠는 지금 지닌 도구 (없음)", "지금 지닌 도구 · 없음" in texts, texts[:200])
    pk.close()
    app.api = HoldApi([squirtle], fail=True)
    pk = ui_box.HeldPicker(box, squirtle)
    wait(root, lambda: pk._state != "wait")
    settle(root)
    chk("못 받으면 오류를 빨갛게", pk._state == "error" and pk.msg == ("가방을 받지 못했습니다.", U.DANGER), pk.msg)
    pk.close()


def probe_main():
    """--probe: 이 프로세스의 테마(POKET_SKIN)로 뜨는 메뉴를 재서 한 줄 JSON 으로 낸다 (default_probe 가 부른다)."""
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    out = probe(root)
    root.destroy()
    print("PROBE " + json.dumps(out, ensure_ascii=False))
    return 0


def main():
    with open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errs = []
    root.report_callback_exception = lambda e, v, tb: errs.append("".join(
        __import__("traceback").format_exception(e, v, tb)))
    try:
        menus(root)
        held(root, dex)
    finally:
        settle(root, 0.2)
        chk("그리는 중에 난 예외가 없다", not errs, errs[:2])
        root.destroy()
    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(probe_main() if "--probe" in sys.argv else main())
