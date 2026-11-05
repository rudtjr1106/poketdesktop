# -*- coding: utf-8 -*-
"""기술머신 칸의 '기술 찾기' 검사 (2.2.1, 게시판 #458) - 기본 테마와 DP 계열 테마 여섯을, 보통 글자와
'아주 크게'(POKET_TEXT_SIZE=2)에서 하나씩 따로 띄워 본다.

    python client/test_tm_find.py

**창을 진짜로 띄운다** (가짜 서버 - 기술머신 목록은 server/data/tms.json, 가진 것은 번호가 10의 배수).
찾는 말의 규칙 자체(이름 · 영어 · 번호, 가진 것만 · 타입 · 분류와 같이 걸기, 지우면 돌아오기, 다시 만들기)는
smoke_tms.py 가 기본 창으로 자세히 본다. 여기서 못 박는 것:

  1. 가방 탭 안의 기술머신 칸에 '기술 찾기' 칸이 목록 위에 있다 - 거르기 탭과 안 겹치고, 글을 칠 만큼 넓고,
     칸 안의 글이 눌리지 않는다 (같은 테마 도구 칸의 찾기 칸보다 낮지 않다). 창이 가장 작을 때와 기본 크기,
     보통 글자와 아주 크게. 기본 테마는 칸 전체에 눌린 위젯이 없다 (머리줄 단추까지).
  2. 테마마다: 칸에 치면 그 줄만 남고 (가진 것만이면 '아직 안 가졌다'), 타입과 같이 걸리고, 맞는 것이 없으면
     목록 자리에 그 말을 (목록 폭 안에) 적고, 지우면 돌아온다. 고른 기술머신은 가려져도 그대로다.
"""
import os
import subprocess
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-tmfind-")
SKIN = os.environ.get("POKET_TMFIND_SKIN", "default")
os.environ["POKET_SKIN"] = SKIN
THEMES = ("dp", "pt", "gs", "bw", "swsh", "emerald")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import smoke_tms as ST                                      # noqa: E402
import test_bag_tabs as BT                                  # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_bag_tabs, ui_hub         # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

OK = FAIL = 0
QUAKE = 149                 # 지진 - 안 가진 것


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.005)


def sizes(win):
    """(이름, 폭, 높이): 허브가 가장 작을 때 · 기본 크기의 가방 칸 (허브 머리 60px 을 뺀다), 글자 배율만큼.
    허브처럼 화면(작업 영역)보다 크게는 안 잡는다 - 작은 화면(CI 러너)에서 아주 크게면 화면까지."""
    r = U.text_ratio()
    mw, mh = U.work_size(win)
    out = []
    for label, w, h in (("가장 작은 창", ui_hub.MIN_W, ui_hub.MIN_H), ("기본 크기", ui_hub.W, ui_hub.H)):
        out.append((label, min(mw, int(round(w * r))), min(mh, int(round(h * r))) - 60))
    return out


def rows(tm):
    """지금 목록에 보이는 기술머신 번호."""
    if SKIN == "default":
        ST.settle_list(tm.root, tm)
        return ST.packed_rows(tm)
    return [t["no"] for t in tm._tm_rows]


def put(root, tm, text):
    e = tm.tm_find.entry
    e.delete(0, "end")
    e.insert(0, text)
    settle(root, 0.1)
    return rows(tm)


def note(tm):
    """목록 자리의 안내 글 (기본 창은 라벨, 테마는 판에 그린 글)."""
    if SKIN == "default":
        lb = tm._empty
        return str(lb.cget("text")) if lb is not None and lb.winfo_ismapped() else ""
    cv = tm.cv
    return " ".join(cv.itemcget(i, "text") for i in cv.find_all()
                    if cv.type(i) == "text" and "에 맞는 기술머신" in cv.itemcget(i, "text"))


def win_box(tm, key):
    """판에 올린 위젯의 (x1, y1, x2, y2) - 숨겼으면 None."""
    i = tm._wins.get(key)
    if i is None or tm.cv.itemcget(i, "state") == "hidden":
        return None
    x, y = tm.cv.coords(i)
    return (x, y, x + float(tm.cv.itemcget(i, "width")), y + float(tm.cv.itemcget(i, "height")))


def layout(root, tm, ref_h, label):
    """1. 찾기 칸의 자리 (지금 창 크기에서). ref_h = 같은 크기에서 잰 도구 칸 찾기 칸 글의 높이."""
    e = tm.tm_find.entry
    if SKIN == "default":
        lc = tm.list_canvas
        box = tm.tm_find
        chk("%s: '기술 찾기' 칸이 목록 바로 위" % label,
            box.winfo_ismapped() and box.winfo_rooty() + box.winfo_height() <= lc.winfo_rooty(),
            (box.winfo_rooty(), box.winfo_height(), lc.winfo_rooty()))
        chk("  글을 칠 만큼 넓다 (%dpx)" % e.winfo_width(), e.winfo_width() >= U.h(80), e.winfo_width())
        chk("  눌린 위젯이 없다 (머리줄 단추 · 찾기 칸까지)", not squeezed(tm.win), squeezed(tm.win)[:3])
        return
    cv = tm.cv
    eb = win_box(tm, "tfind")
    chk("%s: '기술 찾기' 칸이 판 위에 있다" % label, eb is not None and e.winfo_ismapped(), eb)
    if eb is None:
        return
    tabs = [cv.bbox(t) for t in ("flt", "tmf") if cv.bbox(t)]
    lab = [cv.bbox(i) for i in cv.find_all()
           if cv.type(i) == "text" and cv.itemcget(i, "text").startswith("기술 찾기")]
    lst = win_box(tm, "tms")
    chk("  거르기 탭 위 (안 겹친다)", len(tabs) == 2 and eb[3] <= min(b[1] for b in tabs) + 1, (eb, tabs))
    chk("  '기술 찾기' 글 바로 오른쪽 (안 겹친다)", len(lab) == 1 and lab[0][2] <= eb[0] + 1
        and lab[0][1] < eb[3] and lab[0][3] > eb[1], (lab, eb))
    chk("  글을 칠 만큼 넓다 (%dpx)" % (eb[2] - eb[0]), eb[2] - eb[0] >= U.h(80), eb)
    chk("  목록 칸 폭 안", lst is not None and eb[0] >= lst[0] - U.h(12) and eb[2] <= lst[2] + U.h(12), (eb, lst))
    chk("  목록은 거르기 탭 아래에서 시작", lst is not None and lst[1] >= max(b[3] for b in tabs) - 1, (lst, tabs))
    chk("  칸 안의 글이 도구 칸 찾기 칸만큼 높다 (%d / %d · 글 %d)" % (e.winfo_height(), ref_h, e.winfo_reqheight()),
        e.winfo_height() >= min(ref_h, e.winfo_reqheight()) and e.winfo_height() >= e.winfo_reqheight() - 4,
        (e.winfo_height(), ref_h, e.winfo_reqheight()))


def behave(root, tm):
    """2. 치면 거르고, 같이 걸고, 없으면 그렇다고, 지우면 돌아온다."""
    every = [t["no"] for t in tm.tms]
    have = [t["no"] for t in tm.tms if t.get("have")]
    tm.pick(have[0])
    settle(root, 0.15)
    picked = tm.no
    chk("(가진 것만에서 시작)", tm.only_have and rows(tm) == have, len(rows(tm)))
    chk("가진 것만: 안 가진 지진은 없다", put(root, tm, "지진") == [], rows(tm))
    settle(root, 0.1)
    flat = " ".join(note(tm).split())                   # (테마가 칸 폭에서 접은 줄바꿈은 빈칸으로 - 윈도우 글꼴은 접는 자리가 다르다)
    chk("  '아직 안 가졌다 · 전부' 라고 적는다", "안 가졌다" in flat and "전부" in flat, note(tm))
    chk("  고른 기술머신은 그대로", tm.no == picked, tm.no)
    tm._toggle_filter()
    settle(root, 0.1)
    chk("전부: 지진 한 줄", rows(tm) == [QUAKE], rows(tm))
    tm._set_type("GROUND")
    settle(root, 0.1)
    chk("  타입(땅)과 같이 건다", rows(tm) == [QUAKE], rows(tm))
    tm._set_type("FIRE")
    settle(root, 0.15)
    chk("  타입(불꽃)이면 없다", rows(tm) == [], rows(tm))
    chk("  목록 자리에 '맞는 기술머신이 없다'", "'지진' 에 맞는 기술머신이 없다." in note(tm), note(tm))
    if SKIN != "default":
        cv = tm.cv
        ids = [i for i in cv.find_all() if cv.type(i) == "text" and "에 맞는 기술머신" in cv.itemcget(i, "text")]
        eb = win_box(tm, "tfind")
        b = cv.bbox(ids[0]) if ids else None
        chk("  그 글은 목록 칸 폭 안 · 찾기 칸 아래", b is not None and eb is not None and b[0] >= eb[0] - U.h(200)
            and b[1] >= eb[3], (b, eb))
    tm._set_type(None)
    chk("영어 이름 'earth quake'", put(root, tm, "earth quake") == [QUAKE], rows(tm))
    chk("번호 'TM149'", put(root, tm, "TM149") == [QUAKE], rows(tm))
    chk("지우면 돌아온다 (전부 %d줄)" % len(every), put(root, tm, "") == every, len(rows(tm)))
    chk("  고른 기술머신 그대로", tm.no == picked, tm.no)
    tm._toggle_filter()
    settle(root, 0.1)


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))
    print("== 테마: %s · 글자 크기 %d" % (SKIN, U.TEXT_SIZE))
    chk("이번 실행의 테마", skins.active() == SKIN, skins.active())
    api = BT.Api(ST.load_tms(), [])
    app = BT.App(root, api)
    top = tk.Toplevel(root)
    (_n, w, h) = sizes(top)[1]
    top.geometry("%dx%d+20+20" % (w, h))
    bag = ui_bag_tabs.BagTabs(root, app, top)
    bag.win.pack(fill="both", expand=True)
    settle(root, 0.2)
    bag.show("tms")
    tm = bag.tms
    BT.wait(root, lambda: bool(tm.tms) and tm._wait is None, 10)
    settle(root, 0.3)
    for label, w, h in sizes(top):
        top.geometry("%dx%d" % (w, h))
        bag.show("items")                   # 같은 크기의 도구 칸 찾기 칸을 잰다 (견줄 높이)
        settle(root, 0.3)
        ref = getattr(bag.bag, "item_find", None)
        ref_h = ref.entry.winfo_height() if ref is not None and ref.entry.winfo_ismapped() else 0
        bag.show("tms")
        settle(root, 0.3)
        layout(root, tm, ref_h, "%s %dx%d" % (label, w, h))
    behave(root, tm)
    chk("그리는 중에 난 예외가 없다", not errors, errors[:3])
    bag.close()
    try:
        root.destroy()
    except tk.TclError:
        pass


if __name__ == "__main__":
    main()
    if SKIN == "default" and not os.environ.get("POKET_TMFIND_CHILD"):
        runs = [("default", "2")] + [(k, z) for k in THEMES for z in ("0", "2")]
        for key, size in runs:
            env = dict(os.environ, POKET_TMFIND_SKIN=key, POKET_TEXT_SIZE=size, POKET_TMFIND_CHILD="1")
            env.pop("POKET_HOME", None)
            out = subprocess.run([sys.executable, os.path.abspath(__file__)], env=env, capture_output=True, text=True)
            for line in out.stdout.splitlines():
                if line.startswith("  ") or line.startswith("=="):
                    print(line)
                if line.startswith("합계"):
                    bits = line.split()
                    OK += int(bits[2])
                    FAIL += int(bits[4])
            if out.returncode != 0 or "합계" not in out.stdout:
                FAIL += 1
                print("  FAIL %s · 글자 %s 검사가 끝나지 않았다\n%s" % (key, size, out.stderr[-1500:]))
    print("합계 OK %d FAIL %d" % (OK, FAIL))
    sys.exit(1 if FAIL else 0)
